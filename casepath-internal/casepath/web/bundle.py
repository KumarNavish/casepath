"""The Versandpaket: what «Freigeben» stores on the server, in the same request, as the record of what was approved.

One zip, one folder per recipient (``<Empfänger>/Brief.docx``: the exact approved text; ``<Empfänger>/<Titel>.docx``:
each enclosure for that recipient), ``Beilagen.txt`` (what goes to whom), ``Aktennotiz.txt`` (the file note of the
version), ``Wiedervorlage.txt`` (the date and what is awaited) and ``manifest.json`` (format ``casepath.versandpaket/1``:
the version, the form, the recipients, who approved when, the reply date, the options chosen, the run and the files it
rests on, the code, and each member's SHA-256). Deterministic: the members sorted, every timestamp 1980-01-01, also
inside each .docx, so the same approval gives the same bytes. The stored blob is the record: it is never rebuilt to be
compared (the note would include later events). Nothing is sent from here: the handler sends, and confirms it.
"""
import io
import json
import re
import zipfile

from .report import W, _para, _run

FORMAT = "casepath.versandpaket/1"
STAMP = (1980, 1, 1, 0, 0, 0)
FOLDERS = {"kunde": "Kundschaft", "gegenpartei": "Gegenpartei", "kanzlei": "Kanzlei", "behoerde": "Behörde", "andere": "Andere"}
CONTENT_TYPES = ('<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                 '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                 '<Default Extension="xml" ContentType="application/xml"/>'
                 '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
RELS = ('<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="r1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _write(archive, name, data):
    info = zipfile.ZipInfo(name, date_time=STAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    archive.writestr(info, data if isinstance(data, bytes) else data.encode("utf-8"))


def _zip(members):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        for name, data in sorted(members.items()):
            _write(archive, name, data)
    return out.getvalue()


def docx(text):
    """A Word document holding exactly ``text``, one paragraph per line; the same text always gives the same bytes."""
    body = "".join(_para(_run(line), space_after=0) if line.strip() else _para(space_after=0) for line in str(text or "").split("\n"))
    document = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="{W}"><w:body>{body}'
                '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" '
                'w:header="567" w:footer="567" w:gutter="0"/></w:sectPr></w:body></w:document>')
    return _zip({"[Content_Types].xml": CONTENT_TYPES, "_rels/.rels": RELS, "word/document.xml": document})


def safe(name):
    """A folder's or a file's name in the zip: no path separators or characters a file system refuses."""
    return re.sub(r"\s+", " ", re.sub(r'[\\/:*?"<>|\x00-\x1f]', "-", str(name or ""))).strip(" .") or "Dokument"


def _day(iso):
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(iso or ""))
    return f"{m.group(3)}.{m.group(2)}.{m.group(1)}" if m else ""


def members(draft):
    """The documents of the approved version, by folder: [(path, kind, title, text)], the letter first."""
    form = draft.get("form") or draft.get("kind")
    also = {a["kind"]: a for a in draft.get("also") or () if a.get("text")}
    out, used = [], set()
    for row in draft.get("recipients") or ():
        folder = safe(FOLDERS.get(row["to"], row.get("title") or row["to"]))
        for kind in row.get("forms") or ():
            if kind == form:
                name, title, text = "Brief.docx", draft.get("title") or "Brief", draft.get("text") or ""
            else:
                a = also.get(kind) or {}
                title = a.get("name") or a.get("title") or kind
                name, text = f"{safe(title)}.docx", a.get("text") or ""
            path = f"{folder}/{name}"
            while path in used:
                path = path[:-5] + " (2).docx"
            used.add(path)
            out.append((path, kind, title, text))
    return out


def when_line(respond_by, follow_up):
    """The Wiedervorlage's first line: the reply date the letter sets; else the clock's days counted from the dispatch (the
    date for a dispatch on the approval day); else the case's follow-up. The file note's «Erwartet» says the same."""
    if respond_by:  # the letter sets the date itself: it holds whenever the letter goes out
        return f"Antwort erwartet bis {_day(respond_by)}"
    if isinstance(follow_up, dict) and follow_up.get("days"):  # counted from the dispatch: the date for a dispatch on the approval day
        return (f"Wiedervorlage {follow_up['days']} Tage nach dem Versand: {_day(follow_up.get('due'))} bei Versand am {_day(follow_up.get('if_sent'))}"
                if follow_up.get("due") else f"Wiedervorlage {follow_up['days']} Tage nach dem Versand")
    due = follow_up.get("due") if isinstance(follow_up, dict) else follow_up
    return f"Wiedervorlage {_day(due)}" if due else "Wiedervorlage nach Versand"


def build(draft, approval, note, awaited, follow_up=None, parity_sha=None):
    """The Versandpaket of an approved version: (zip bytes, manifest). ``draft``: the prepared letter as approved (its text,
    enclosures and recipients, completion.prepare); ``approval``: the «action.approved» event; ``note``: the file note of
    the version; ``awaited``: what the letter asks, in words; ``follow_up``: the case's follow-up date."""
    files = {}
    parts = []
    for path, kind, title, text in members(draft):
        files[path] = docx(text)
        parts.append({"name": path, "kind": kind, "title": title})
    beilagen = []
    for row in draft.get("recipients") or ():
        names = [p["title"] for p in parts if p["name"].startswith(safe(FOLDERS.get(row["to"], row["to"])) + "/")]
        beilagen.append(f"{FOLDERS.get(row['to'], row['to'])} ({row.get('recipient')}): " + "; ".join(names))
    files["Beilagen.txt"] = "\n".join(beilagen) + "\n"
    files["Aktennotiz.txt"] = (note or "").strip() + "\n"
    respond_by = approval.get("respond_by")
    files["Wiedervorlage.txt"] = f"{when_line(respond_by, follow_up)}\nErwartet: {', '.join(awaited) if awaited else 'Rückmeldung'}\n"
    for p in parts:
        p["sha256"] = _sha(files[p["name"]])
    for name in ("Beilagen.txt", "Aktennotiz.txt", "Wiedervorlage.txt"):
        parts.append({"name": name, "kind": None, "title": name[:-4], "sha256": _sha(files[name])})
    look = follow_up if isinstance(follow_up, dict) else {"due": follow_up} if follow_up else None
    manifest = {"format": FORMAT, "version": approval.get("version"), "form": approval.get("form"), "title": approval.get("title"),
                "approval": approval.get("event_id"), "follow_up": look, "relies": approval.get("relies") or [],
                "recipients": [{k: r.get(k) for k in ("to", "recipient", "forms")} for r in approval.get("recipients") or ()],
                "approved_by": approval.get("expert"), "approved_at": approval.get("at"), "respond_by": respond_by,
                "chosen": approval.get("chosen"), "options_sha256": approval.get("options_sha256"), "run_id": approval.get("run_id"),
                "files_digest": approval.get("files_digest"), "parity_sha": parity_sha, "parts": sorted(parts, key=lambda p: p["name"])}
    files["manifest.json"] = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=1) + "\n"
    return _zip(files), manifest


def _sha(data):
    import hashlib
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode("utf-8")).hexdigest()


def manifest_of(blob):
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        return json.loads(archive.read("manifest.json"))


def text_of(docx_bytes):
    """The text a Brief.docx of a Versandpaket holds, one line per paragraph (docx() wrote it so)."""
    import html
    xml = zipfile.ZipFile(io.BytesIO(docx_bytes)).read("word/document.xml").decode("utf-8")
    lines = []
    for para in re.findall(r"<w:p>(.*?)</w:p>", xml):
        lines.append(html.unescape("".join(re.findall(r'<w:t xml:space="preserve">([^<]*)</w:t>', para))))
    return "\n".join(lines)


def member(blob, kind):
    """One document of a stored Versandpaket by its kind (the letter's form or an enclosure's): (name, bytes) or None."""
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        row = next((p for p in json.loads(archive.read("manifest.json"))["parts"] if p.get("kind") == kind), None)
        return (row["name"].rsplit("/", 1)[-1], archive.read(row["name"])) if row else None


def file_name(case, approved_at):
    """«Versandpaket_<Referenz oder Fall>_<TT.MM.JJJJ>.zip»."""
    ref = re.search(r"\d{4}\.\d{4}\.\d{4}", f"{(case or {}).get('title', '')} {(case or {}).get('intake', '')}")
    who = ref.group(0) if ref else re.sub(r"[^\w.-]+", "-", str((case or {}).get("title") or (case or {}).get("id") or "Fall"))[:60].strip("-")
    from ..process.completion import swiss_day
    return f"Versandpaket_{who}_{_day(swiss_day(approved_at))}.zip"  # the Swiss day of the approval
