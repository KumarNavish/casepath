"""Read text from uploaded case files and say exactly how much was readable.

Supported: plain text, e-mail (.eml), PDF with a text layer, Word (.docx) and
images (kept as originals, not read). Scanned PDF pages without a text layer
are counted, never guessed; OCR belongs to an approved internal service.
"""
from email import policy
from email.parser import BytesParser
import io
import re
import zipfile
import xml.etree.ElementTree as ET

KINDS = {
    "application/pdf": "pdf", "message/rfc822": "email", "text/plain": "text", "text/markdown": "text",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "word",
    "image/jpeg": "image", "image/png": "image", "image/heic": "image", "image/webp": "image",
}
EXTENSIONS = {".pdf": "application/pdf", ".eml": "message/rfc822", ".txt": "text/plain", ".md": "text/markdown",
              ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
              ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".heic": "image/heic", ".webp": "image/webp"}


def media_type(name, declared, data):
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    suffix = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if data.startswith(b"PK\x03\x04") and suffix == ".docx":
        return EXTENSIONS[".docx"]
    if suffix in EXTENSIONS and EXTENSIONS[suffix] not in {"application/pdf", "image/jpeg", "image/png"}:
        return EXTENSIONS[suffix]
    declared = (declared or "").split(";")[0].strip().lower()
    return declared if declared in KINDS else "application/octet-stream"


def normalise(text):
    return re.sub(r"\s+", " ", text).strip()


def _pdf(data):
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    parts, empty = [], []
    for number, page in enumerate(reader.pages, 1):
        text = (page.extract_text() or "").strip()
        if text:
            parts.append(f"[page {number}]\n{text}")
        else:
            empty.append(number)
    return "\n\n".join(parts), {"pages": len(reader.pages), "pages_without_text": empty}


def _email(data):
    message = BytesParser(policy=policy.default).parsebytes(data)
    header = "\n".join(f"{key}: {message[key]}" for key in ("From", "To", "Date", "Subject") if message[key])
    body, attachments = [], []
    for part in message.walk():
        if part.is_multipart():
            continue
        if part.get_filename():
            attachments.append(part.get_filename())
        elif part.get_content_type() == "text/plain":
            body.append(part.get_content())
    return header + "\n\n" + "\n".join(body).strip(), {"attachments": attachments}


def _word(data):
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if archive.getinfo("word/document.xml").file_size > 50_000_000:
            raise ValueError("Word document body is too large")
        root = ET.fromstring(archive.read("word/document.xml"))
    paragraphs = ["".join(node.text or "" for node in p.iter(namespace + "t")) for p in root.iter(namespace + "p")]
    return "\n".join(p for p in paragraphs if p.strip()), {}


def extract(name, declared, data):
    kind_type = media_type(name, declared, data)
    kind = KINDS.get(kind_type, "other")
    result = {"media_type": kind_type, "kind": kind, "text": "", "readable": False, "note": None}
    try:
        if kind == "pdf":
            text, details = _pdf(data)
            result.update(details)
            if details["pages_without_text"]:
                result["note"] = f"{len(details['pages_without_text'])} of {details['pages']} pages have no text layer and were not read."
        elif kind == "email":
            text, details = _email(data)
            result.update(details)
        elif kind == "word":
            text, _ = _word(data)
        elif kind == "text":
            text = data.decode("utf-8", errors="replace")
        else:
            text = ""
            result["note"] = "Kept as an original; images and other files are not read as text."
    except Exception as error:  # A damaged file is reported, never guessed.
        text = ""
        result["note"] = f"The file could not be read ({type(error).__name__})."
    result["text"] = text
    result["readable"] = bool(text.strip())
    return result
