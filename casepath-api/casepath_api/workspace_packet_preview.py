"""Bounded, read-only packet previews. No preview admits evidence or changes a finding."""
from __future__ import annotations
from io import BytesIO
from contextlib import contextmanager
from threading import RLock
from pathlib import PurePosixPath
from typing import Any, Callable
from zipfile import ZipFile, BadZipFile
from xml.etree import ElementTree as ET
import hashlib
import re
from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from PIL import Image, ImageOps, UnidentifiedImageError
import fitz
MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_ZIP_BYTES = 24 * 1024 * 1024
MAX_ZIP_ENTRIES = 1500
MAX_PIXELS = 32_000_000
MAX_PAGES = 400
MAX_TEXT = 80_000
MAX_CELLS = 1500
XML_W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
XML_S = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
PDF_RENDER_LOCK = RLock()
HEADERS = {'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'}


class PreviewError(ValueError):
    """Unsupported, malformed, stale or over-limit input: no preview is returned."""

def _check_bytes(raw: bytes, row: dict[str, Any]) -> None:
    if not raw or len(raw) > MAX_SOURCE_BYTES:
        raise PreviewError('This file is outside the preview size limit.')
    if len(raw) != row.get('size_bytes') or hashlib.sha256(raw).hexdigest() != row.get('sha256'):
        raise PreviewError('The source no longer matches its saved record.')


def _xml(raw: bytes) -> ET.Element:
    if b'\x00' in raw or len(raw) > MAX_ZIP_BYTES or re.search(br'<!\s*(?:DOCTYPE|ENTITY)', raw, re.I):
        raise PreviewError('This document contains an unsupported XML declaration.')
    try:
        return ET.fromstring(raw)
    except ET.ParseError as exc:
        raise PreviewError('Document content could not be read.') from exc


def _office(raw: bytes) -> ZipFile:
    try:
        archive = ZipFile(BytesIO(raw)); entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if (len(entries) > MAX_ZIP_ENTRIES or len(set(names)) != len(names)
                or sum(entry.file_size for entry in entries) > MAX_ZIP_BYTES
                or any(entry.flag_bits & 1 for entry in entries)
                or any(PurePosixPath(n).is_absolute() or '..' in PurePosixPath(n).parts or '\\' in n for n in names)
                or any(n.lower().endswith('vbaproject.bin') for n in names)):
            archive.close()
            raise PreviewError('This document is outside the safe preview profile.')
        return archive
    except (BadZipFile, OSError) as exc:
        raise PreviewError('This office file could not be opened.') from exc

def _read_member(archive: ZipFile, name: str) -> bytes:
    try:
        return archive.read(name)
    except (KeyError, BadZipFile, RuntimeError) as exc:
        raise PreviewError('Required document content is unavailable.') from exc


@contextmanager
def _pdf(raw: bytes):
    # MuPDF document work is serialized. No document objects are shared.
    with PDF_RENDER_LOCK:
        document = None
        try:
            document = fitz.open(stream=raw, filetype='pdf')
            if document.is_encrypted or not 1 <= len(document) <= MAX_PAGES:
                raise PreviewError('This PDF is locked or outside the page limit.')
            yield document
        except (RuntimeError, ValueError) as exc:
            if isinstance(exc, PreviewError):
                raise
            raise PreviewError('This PDF could not be previewed.') from exc
        finally:
            if document is not None:
                document.close()


def _image(raw: bytes) -> Image.Image:
    try:
        image = Image.open(BytesIO(raw))
        if image.width * image.height > MAX_PIXELS:
            image.close()
            raise PreviewError('This image is too large for an inline preview.')
        return image
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as exc:
        raise PreviewError('This image could not be previewed.') from exc

def preview_metadata(raw: bytes, row: dict[str, Any]) -> dict[str, Any]:
    _check_bytes(raw, row)
    media = str(row.get('media_type', '')).split(';')[0].strip().lower()
    result = {'contract': 'casepath.source-preview/1.0.0', 'source_sha256': row['sha256'],
              'artifact_id': row.get('artifact_id'), 'size_bytes': len(raw),
              'kind': 'other', 'renderable': False, 'page_count': None,
              'content': None, 'truncated': False, 'is_evidence_admission': False}
    if media == 'application/pdf':
        with _pdf(raw) as doc:
            result.update(kind='pdf', renderable=True, page_count=len(doc))
    elif media in {'image/jpeg', 'image/png', 'image/webp', 'image/gif', 'image/tiff', 'image/bmp'}:
        with _image(raw) as image:
            result.update(kind='image', renderable=True, page_count=1,
                          width=image.width, height=image.height)
    elif media == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
        with _office(raw) as archive:
            doc = _xml(_read_member(archive, 'word/document.xml'))
            paragraphs = [''.join(t.text or '' for t in p.iter(XML_W + 't'))
                          for p in doc.iter(XML_W + 'p')]
            text = '\n\n'.join(paragraphs)
            result.update(kind='word', content={'paragraphs': text[:MAX_TEXT].split('\n\n')},
                          truncated=len(text) > MAX_TEXT)
    elif media == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
        result.update(_spreadsheet(raw))
    return result


def _spreadsheet(raw: bytes) -> dict[str, Any]:
    with _office(raw) as archive:
        shared = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            shared = [''.join(t.text or '' for t in si.iter(XML_S + 't'))
                      for si in _xml(_read_member(archive, 'xl/sharedStrings.xml')).iter(XML_S + 'si')]
        relations = _xml(_read_member(archive, 'xl/_rels/workbook.xml.rels'))
        targets = {r.get('Id'): r.get('Target') for r in relations
                   if r.get('TargetMode', '') != 'External'}
        workbook = _xml(_read_member(archive, 'xl/workbook.xml'))
        sheets, used, truncated = [], 0, False
        for sheet in workbook.iter(XML_S + 'sheet'):
            if len(sheets) >= 10 or used >= MAX_CELLS:
                truncated = True
                break
            rid = sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
            target = targets.get(rid, '')
            if target.startswith('/xl/'):
                name = target.lstrip('/')
            elif target and not PurePosixPath(target).is_absolute() and '..' not in PurePosixPath(target).parts:
                name = 'xl/' + target
            else:
                raise PreviewError('This workbook uses an unsupported sheet relationship.')
            rows = []
            for r in _xml(_read_member(archive, name)).iter(XML_S + 'row'):
                cells = []
                for cell in r.findall(XML_S + 'c'):
                    if used >= MAX_CELLS:
                        truncated = True
                        break
                    used += 1
                    address, ctype = cell.get('r', ''), cell.get('t', '')
                    if not re.fullmatch(r'[A-Z]{1,3}[1-9][0-9]{0,6}', address):
                        raise PreviewError('A spreadsheet cell address is invalid.')
                    text = cell.findtext(XML_S + 'v', '')
                    if ctype == 's':
                        try:
                            index = int(text)
                            if index < 0:
                                raise ValueError()
                            text = shared[index]
                        except (ValueError, IndexError) as exc:
                            raise PreviewError('A spreadsheet string reference is invalid.') from exc
                    elif ctype == 'inlineStr':
                        text = ''.join(t.text or '' for t in cell.iter(XML_S + 't'))
                    formula = cell.findtext(XML_S + 'f')
                    cells.append({'address': address, 'value': text[:2000],
                                  'formula': formula[:2000] if formula else None,
                                  'cached_value': formula is not None})
                if cells:
                    rows.append(cells)
                if used >= MAX_CELLS:
                    break
            sheets.append({'name': sheet.get('name', 'Worksheet'), 'rows': rows})
    return {'kind': 'spreadsheet', 'content': {'sheets': sheets, 'formulas_recalculated': False},
            'truncated': truncated}


def preview_page(raw: bytes, row: dict[str, Any], page: int, width: int) -> bytes:
    _check_bytes(raw, row)
    if not 1 <= page <= MAX_PAGES or not 120 <= width <= 1600:
        raise PreviewError('The requested page or image size is invalid.')
    media = str(row.get('media_type', '')).split(';')[0].strip().lower()
    if media == 'application/pdf':
        with _pdf(raw) as doc:
            if page > len(doc):
                raise PreviewError('This page is outside the document.')
            source = doc[page - 1]
            scale = min(width / max(1, source.rect.width), 1800 / max(1, source.rect.height))
            return source.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False).tobytes('png')
    if media in {'image/jpeg', 'image/png', 'image/webp', 'image/gif', 'image/tiff', 'image/bmp'} and page == 1:
        with _image(raw) as image:
            output = ImageOps.exif_transpose(image).convert('RGB')
            output.thumbnail((width, 1800), Image.Resampling.LANCZOS)
            stream = BytesIO()
            output.save(stream, 'PNG')
            return stream.getvalue()
    raise PreviewError('This file type has no page image preview.')

def create_packet_preview_router(workspace_service_getter: Callable[[], Any]) -> APIRouter:
    router = APIRouter(prefix='/api/claim-loops/v1/workspace/claims')
    def resolve(claim_id: str, artifact_id: str, source_sha256: str):
        try:
            raw, row = workspace_service_getter().corpus.artifact(claim_id, artifact_id)
            if row.get('sha256') != source_sha256:
                raise HTTPException(409, 'This preview belongs to a different source version.')
            _check_bytes(raw, row)
            return raw, row
        except HTTPException:
            raise
        except ValueError as exc:
            raise HTTPException(404, 'This source is unavailable in the claim packet.') from exc

    @router.get('/{claim_id}/artifacts/{artifact_id}/preview')
    def metadata(claim_id: str, artifact_id: str,
                 source_sha256: str = Query(pattern=r'^[a-f0-9]{64}$')):
        raw, row = resolve(claim_id, artifact_id, source_sha256)
        try:
            value = preview_metadata(raw, row)
            value['claim_id'] = claim_id
            return JSONResponse(value, headers={**HEADERS, 'X-Source-SHA256': row['sha256']})
        except PreviewError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.get('/{claim_id}/artifacts/{artifact_id}/preview/page')
    def page_image(claim_id: str, artifact_id: str,
                   source_sha256: str = Query(pattern=r'^[a-f0-9]{64}$'),
                   page: int = Query(1, ge=1, le=MAX_PAGES),
                   width: int = Query(900, ge=120, le=1600)):
        raw, row = resolve(claim_id, artifact_id, source_sha256)
        try:
            png = preview_page(raw, row, page, width)
            return Response(png, media_type='image/png', headers={**HEADERS, 'X-Source-SHA256': row['sha256']})
        except PreviewError as exc:
            raise HTTPException(422, str(exc)) from exc
    return router
