from __future__ import annotations

import json
import mimetypes
import os
from pathlib import Path
import time
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / 'casepath'
API_LOCAL = 'http://127.0.0.1:8123'
OUT = ROOT / 'reports' / 'screenshots'
OUT.mkdir(parents=True, exist_ok=True)

results=[]
errors=[]

def check(name, condition, detail=''):
    results.append({'name':name,'passed':bool(condition),'detail':detail})
    if not condition: print('FAIL',name,detail)


def proxy(route):
    req=route.request
    parsed=urlparse(req.url)
    path=parsed.path
    if path.startswith('/api-proxy'):
        target=API_LOCAL+path[len('/api-proxy'):]
        if parsed.query: target += '?' + parsed.query
        headers={k:v for k,v in req.headers.items() if k.lower() not in {'host','content-length','origin','referer'}}
        body=req.post_data_buffer
        request=Request(target,data=body,headers=headers,method=req.method)
        try:
            with urlopen(request,timeout=60) as resp:
                content=resp.read(); status=resp.status; rh=dict(resp.headers)
        except HTTPError as exc:
            content=exc.read(); status=exc.code; rh=dict(exc.headers)
        route.fulfill(status=status,body=content,headers={k:v for k,v in rh.items() if k.lower() not in {'content-encoding','transfer-encoding','connection'}})
        return
    local_path = STATIC / (path.lstrip('/') or 'index.html')
    if local_path.is_dir(): local_path /= 'index.html'
    if local_path.exists() and local_path.is_file():
        mime=mimetypes.guess_type(local_path.name)[0] or 'application/octet-stream'
        route.fulfill(status=200,body=local_path.read_bytes(),content_type=mime)
    else:
        route.fulfill(status=404,body=b'not found',content_type='text/plain')


def proxy_api(route):
    req=route.request
    parsed=urlparse(req.url)
    target=API_LOCAL+parsed.path
    if parsed.query: target += '?' + parsed.query
    headers={k:v for k,v in req.headers.items() if k.lower() not in {'host','content-length','origin','referer'}}
    body=req.post_data_buffer
    request=Request(target,data=body,headers=headers,method=req.method)
    try:
        with urlopen(request,timeout=60) as resp:
            content=resp.read(); status=resp.status; rh=dict(resp.headers)
    except HTTPError as exc:
        content=exc.read(); status=exc.code; rh=dict(exc.headers)
    clean={k:v for k,v in rh.items() if k.lower() not in {'content-encoding','transfer-encoding','connection','access-control-allow-origin'}}
    clean['Access-Control-Allow-Origin']='*'
    route.fulfill(status=status,body=content,headers=clean)


def run_viewport(browser,width,height,label):
    context=browser.new_context(viewport={'width':width,'height':height},accept_downloads=True)
    page=context.new_page()
    page.on('console',lambda m: errors.append({'type':'console','text':m.text}) if m.type=='error' else None)
    page.on('pageerror',lambda e: errors.append({'type':'pageerror','text':str(e)}))
    page.route('https://api.casepath.test/**', proxy_api)
    html=(STATIC/'index.html').read_text(encoding='utf-8')
    css=(STATIC/'assets'/'styles.css').read_text(encoding='utf-8')
    js=(STATIC/'assets'/'app.js').read_text(encoding='utf-8')
    html=html.replace('<link rel="stylesheet" href="assets/styles.css">', '<style>'+css+'</style>')
    html=html.replace('<script src="assets/app.js"></script>', '<script>window.CASEPATH_API="https://api.casepath.test";</script><script>'+js+'</script>')
    page.set_content(html, wait_until='domcontentloaded')
    page.wait_for_selector('#customerMessage .email-body')
    check(f'{label}: title',page.locator('h1').inner_text().startswith('Recurring mould'))
    check(f'{label}: six attachments',page.locator('.attachment-row').count()==6,str(page.locator('.attachment-row').count()))
    overflow=page.evaluate('document.documentElement.scrollWidth-document.documentElement.clientWidth')
    check(f'{label}: no horizontal overflow',overflow==0,str(overflow))
    page.screenshot(path=str(OUT/f'01-submission-{label}.png'),full_page=True)
    if width>=1000:
        page.locator('.attachment-row').filter(has_text='Residential lease agreement').click()
        page.wait_for_selector('#artifactViewer[open]')
        page.screenshot(path=str(OUT/'02-actual-pdf-open.png'))
        check('actual PDF page visible',page.locator('#pdfPageImage').is_visible())
        page.locator('[data-pdf-page="next"]').click()
        check('PDF page navigation works',page.locator('#pdfCurrentPage').inner_text()=='2')
        page.locator('[data-pdf-zoom="in"]').click()
        pdf_transform=page.locator('#pdfPageImage').evaluate('el=>getComputedStyle(el).transform')
        check('PDF zoom works',pdf_transform!='none',pdf_transform)
        page.locator('#closeViewer').click()
        page.locator('.attachment-row').filter(has_text='Bedroom photograph').click()
        page.wait_for_selector('#sourceImage')
        page.screenshot(path=str(OUT/'03-actual-image-open.png'))
        check('actual image visible',page.locator('#sourceImage').is_visible())
        page.locator('[data-image-zoom="in"]').click()
        transform=page.locator('#sourceImage').evaluate('el=>getComputedStyle(el).transform')
        check('image zoom works',transform!='none',transform)
        page.locator('#closeViewer').click()
        page.locator('#analyseBtn').click()
        page.wait_for_selector('#analysis:not([hidden])')
        page.wait_for_timeout(1000)
        page.screenshot(path=str(OUT/'04-agents-processing.png'),full_page=True)
        page.wait_for_selector('#result:not([hidden])',timeout=30000)
        page.screenshot(path=str(OUT/'05-final-process-evidence.png'),full_page=True)
        page.locator('#result').scroll_into_view_if_needed()
        page.screenshot(path=str(OUT/'05b-final-process-evidence-viewport.png'))
        check('current blocker visible','What caused the recurring mould?' in page.locator('#decisionSummary').inner_text())
        check('process nodes render',page.locator('.process-node').count()>=5)
        check('process-derived evidence renders',page.locator('.evidence-item').count()>=3)
        page.locator('#precedentList').scroll_into_view_if_needed()
        page.screenshot(path=str(OUT/'06-three-precedents.png'))
        check('exactly three precedents',page.locator('.precedent-row').count()==3)
        page.locator('.fact-source-button').filter(has_text='View source').first.click()
        page.wait_for_selector('#artifactViewer[open]')
        check('fact opens source viewer',page.locator('#sourceFacts').inner_text().find('Opened from')>=0)
        page.locator('#closeViewer').click()
        page.locator('#review').scroll_into_view_if_needed()
        page.screenshot(path=str(OUT/'07-expert-correction.png'))
        page.locator('#reviewForm button[type="submit"]').click()
        page.wait_for_selector('#learning:not([hidden])',timeout=15000)
        page.screenshot(path=str(OUT/'08-what-was-learned.png'),full_page=True)
        check('reviewed memory shown','Saved as a reviewed precedent' in page.locator('#learning').inner_text())
        check('shared rule quarantined','1 of 3' in page.locator('#learning').inner_text())
        page.locator('#tryLearningBtn').click()
        page.wait_for_selector('#laterClaim:not([hidden])',timeout=10000)
        page.screenshot(path=str(OUT/'09-later-claim-improved.png'),full_page=True)
        page.locator('#laterClaim').scroll_into_view_if_needed()
        page.screenshot(path=str(OUT/'09b-later-claim-improved-viewport.png'))
        later=page.locator('#laterClaim').inner_text()
        check('later claim uses reviewed precedent','Expert-reviewed precedent used' in later)
        check('later claim shows conditional evidence','only if the first inspection is inconclusive' in later)
        page.locator('#openAuditTop').click()
        check('audit trail lists underlying agents','Claim Interpretation Agent' in page.locator('#auditContent').inner_text())
        page.screenshot(path=str(OUT/'10-audit-trail.png'))
        page.locator('#closeAudit').click()
    context.close()


def main():
    # reset before the deterministic journey
    req=Request(API_LOCAL+'/api/demo/reset',data=b'',method='POST')
    urlopen(req).read()
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
        run_viewport(browser,1440,900,'1440x900')
        run_viewport(browser,390,844,'390x844')
        run_viewport(browser,320,700,'320x700')
        browser.close()
    clean=[e for e in errors if 'favicon' not in e.get('text','').lower()]
    check('no browser console or page errors',len(clean)==0,json.dumps(clean))
    report={'passed':sum(r['passed'] for r in results),'failed':sum(not r['passed'] for r in results),'checks':results,'errors':clean,'generated_at':time.time()}
    (ROOT/'reports'/'browser-qa.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'failed':report['failed'],'errors':len(clean)},indent=2))
    if report['failed']:
        raise SystemExit(1)

if __name__=='__main__': main()
