"""Preview tests use source bytes; they never admit new evidence."""
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
from types import SimpleNamespace
import hashlib
import pytest
import fitz
from PIL import Image
from fastapi import FastAPI
from fastapi.testclient import TestClient
from casepath_api.workspace_packet_preview import preview_metadata, preview_page, create_packet_preview_router, PreviewError


def record(raw, media):
    return {'artifact_id':'file-1','media_type':media,'size_bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def pdf():
    with fitz.open() as doc:
        for text in ('Incoming statement','Supporting receipt'):
            page=doc.new_page(width=595,height=842)
            page.insert_text((45,65),text,fontsize=18)
        return doc.tobytes()


def office(files):
    stream=BytesIO()
    with ZipFile(stream,'w',ZIP_DEFLATED) as z:
        for name,text in files.items(): z.writestr(name,text)
    return stream.getvalue()


def test_pdf_preview_is_an_actual_raster_of_original_bytes():
    raw=pdf();row=record(raw,'application/pdf')
    metadata=preview_metadata(raw,row)
    assert metadata['page_count']==2 and metadata['is_evidence_admission'] is False
    with Image.open(BytesIO(preview_page(raw,row,2,300))) as image:
        assert 299<=image.width<=301 and image.convert('L').getextrema()[0]<100
    assert hashlib.sha256(raw).hexdigest()==row['sha256']

@pytest.mark.parametrize('page,width',[(0,300),(3,300),(1,10),(1,2000)])
def test_page_bounds(page,width):
    raw=pdf()
    with pytest.raises(PreviewError): preview_page(raw,record(raw,'application/pdf'),page,width)


@pytest.mark.parametrize('drift',['hash','size','bytes'])
def test_source_drift_never_yields_a_preview(drift):
    raw=pdf();row=record(raw,'application/pdf')
    if drift=='hash': row['sha256']='0'*64
    if drift=='size': row['size_bytes']+=1
    if drift=='bytes': raw=b'altered'
    with pytest.raises(PreviewError): preview_metadata(raw,row)


def test_image_dimensions_and_scaling():
    stream=BytesIO();Image.new('RGB',(640,480),(120,80,50)).save(stream,'JPEG')
    raw=stream.getvalue();row=record(raw,'image/jpeg')
    assert preview_metadata(raw,row)['width']==640
    with Image.open(BytesIO(preview_page(raw,row,1,160))) as image: assert image.size==(160,120)


def test_word_returns_text_not_executable_markup():
    raw=office({'word/document.xml':'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Original &amp; unmodified</w:t></w:r></w:p></w:body></w:document>'})
    value=preview_metadata(raw,record(raw,'application/vnd.openxmlformats-officedocument.wordprocessingml.document'))
    assert value['kind']=='word' and value['content']['paragraphs']==['Original & unmodified']
    assert value['renderable'] is False


@pytest.mark.parametrize('attack',['macro','entity','utf16','traversal','huge'])
def test_office_unsafe_input_fails_closed(attack):
    files={'word/document.xml':'<root/>'}
    if attack=='macro': files['word/vbaProject.bin']=b'not executable'
    if attack=='entity': files['word/document.xml']='<!DOCTYPE x [<!ENTITY y "z">]><root>&y;</root>'
    if attack=='utf16': files['word/document.xml']='<root/>'.encode('utf-16')
    if attack=='traversal': files['../document.xml']='outside'
    if attack=='huge': files['word/document.xml']='x'*(25*1024*1024)
    raw=office(files)
    with pytest.raises(PreviewError): preview_metadata(raw,record(raw,'application/vnd.openxmlformats-officedocument.wordprocessingml.document'))

def test_spreadsheet_preserves_addresses_and_does_not_recalculate():
    raw=office({
      'xl/workbook.xml':'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Payments" r:id="r1"/></sheets></workbook>',
      'xl/_rels/workbook.xml.rels':'<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>',
      'xl/worksheets/sheet1.xml':'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>Amount</t></is></c><c r="D1"><f>B1*2</f><v>247</v></c></row></sheetData></worksheet>'})
    value=preview_metadata(raw,record(raw,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'))
    cells=value['content']['sheets'][0]['rows'][0]
    assert cells[1]=={'address':'D1','value':'247','formula':'B1*2','cached_value':True}
    assert value['content']['formulas_recalculated'] is False


def test_preview_routes_are_read_only_and_claim_scoped():
    raw=pdf();row=record(raw,'application/pdf')
    class Corpus:
        def artifact(self,claim_id,artifact_id):
            if (claim_id,artifact_id)!=('claim-a','file-1'): raise ValueError('not in claim')
            return raw,row
    app=FastAPI();app.include_router(create_packet_preview_router(lambda:SimpleNamespace(corpus=Corpus())))
    client=TestClient(app);url='/api/claim-loops/v1/workspace/claims/claim-a/artifacts/file-1/preview'
    params={'source_sha256':row['sha256']}
    response=client.get(url,params=params)
    assert response.status_code==200 and response.json()['claim_id']=='claim-a'
    assert response.headers['cache-control']=='no-store'
    assert client.get(url,params={'source_sha256':'0'*64}).status_code==409
    assert client.get(url.replace('claim-a','claim-b'),params=params).status_code==404
    assert client.post(url,params=params).status_code==405
    assert client.get(url).status_code==422
    page=client.get(url+'/page',params={**params,'width':160})
    assert page.status_code==200 and page.headers['content-type']=='image/png'
    assert page.headers['x-source-sha256']==row['sha256']


def test_product_app_exposes_only_get_preview_routes():
    from casepath_api.app import app
    routes={r.path:r.methods for r in app.routes if hasattr(r,'methods') and '/preview' in r.path}
    assert routes['/api/claim-loops/v1/workspace/claims/{claim_id}/artifacts/{artifact_id}/preview']=={'GET'}
    assert routes['/api/claim-loops/v1/workspace/claims/{claim_id}/artifacts/{artifact_id}/preview/page']=={'GET'}
