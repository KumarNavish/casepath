"""The case report: what CasePath found for a case, as a Word document for the case file.

Everything in it comes from the case's last prepared run and its current process: where the case stands, the summary,
deadlines, the document checklist and the accepted facts, each with the exact passage and page it rests on, the open
points, the Knowledge used and the reply draft. It is marked as AI-assisted and still to be reviewed.
"""
import io
import zipfile
from xml.sax.saxutils import escape

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

LABELS = {
    "de": {"title": "Fallbericht", "notice": "Mit CasePath KI-gestützt erstellt. Jede Feststellung nennt die Stelle in den Dokumenten, auf der sie beruht. "
           "Eine fachliche Prüfung bleibt nötig; nichts wurde versendet.", "case": "Fall", "prepared": "Vorbereitet am", "process": "Prozess",
           "position": "Stand im Prozess", "end": "Prozessende", "current": "Aktueller Schritt", "waiting": "Wartet auf", "next": "Nächste Schritte",
           "summary": "Fallzusammenfassung", "deadlines": "Fristen", "documents": "Dokumenten-Checkliste", "facts": "Belegte Fakten",
           "open": "Offene Punkte", "assessment": "Kurzeinschätzung (Entwurf)", "knowledge": "Aus früheren Fällen (Wissen)",
           "reply": "Antwortentwurf — nicht versendet", "files": "Dokumente des Falls", "document": "Dokument", "status": "Status",
           "source": "Fundstelle", "question": "Frage", "answer": "Antwort", "checked": "Prüfung", "page": "S.", "none": "—",
           "present": "vorhanden", "missing": "fehlt", "unusable": "unbrauchbar", "unchecked": "nicht geprüft", "open_need": "offen",
           "accepted": "belegt", "rejected": "nicht belegt", "not_checked": "nicht geprüft", "conflicting": "widersprüchlich",
           "yes": "ja", "no": "nein", "used": "genutzt", "suggested": "vom Wissen vorgeschlagen", "optional": "freiwillig",
           "depends": "hängt von einer offenen Antwort ab", "obtain": "Einholen", "resolve": "Nicht erfüllt", "ask": "Klären",
           "attached": "Anhang von", "scanned": "gescannte Seiten vom Modell gelesen", "pages": "Seiten", "page_one": "Seite", "by_law": "nach Gesetz verlangt:", "not_prepared": "Der Fall ist noch nicht vorbereitet.",
           "suggested_case": "für diesen Fall vorgeschlagen", "basis": "Grundlage:", "applies_if": "gilt, falls:", "doubt": "die Prüfung zweifelt:",
           "warnings": "Hinweise zur Vorbereitung",
           "checklist_only": "Nur Checkliste: Zusammenfassung, Einschätzung und Antwortentwurf wurden nicht erstellt.",
           "result_checker_stopped": "Nicht abgeschlossen: Die Checkliste beruht auf den belegten Feststellungen; siehe Checkliste und offene Punkte.",
           "stop_document_finder": "Die Dokumentensuche brach vorzeitig ab; nicht erreichte Dokumente bleiben angefordert und sind als nicht geprüft markiert.",
           "stop_claim_reader": "Das Lesen der Fakten brach vorzeitig ab; nicht erfasste Fakten bleiben offen.",
           "stop_process_builder": "Die Ergänzung des Prozesses brach vorzeitig ab; die Anforderungen des Prozesses selbst sind vollständig.",
           "stop_result_checker": "Die Zusammenfassung brach vorzeitig ab; es wurde kein Antwortentwurf erstellt.",
           "reading_failed": "Ein Lesedurchgang der Fakten schlug fehl; die Fakten, die er bestätigen sollte, bleiben offen.",
           "document_check_failed": "Die zweite Prüfung der vorhandenen Dokumente schlug fehl; sie bleiben angefordert.",
           "instruction_like_text": "Ein Dokument enthält Text, der sich an die KI richtet; er wurde als Inhalt behandelt und nicht befolgt.",
           "routing_contradicted": "Die Lesungen der Dokumente widersprechen der Bedingung des gewählten Prozesses; der Prozess bleibt, eine Person prüft.",
           "rerouted": "Die Lesungen der Dokumente widersprachen der ersten Zuordnung ({first}); der Fall wurde neu zugeordnet.",
           "handed_over": "Die Lesungen der Dokumente widersprechen der Zuordnung ({first}); eine Person wählt den Prozess.",
           "admitted": "von den Lesungen belegt"},
    "en": {"title": "Case report", "notice": "Prepared with CasePath's AI assistance. Every finding names the passage it rests on. "
           "Qualified review is still required; nothing was sent.", "case": "Case", "prepared": "Prepared on", "process": "Process",
           "position": "Where the case stands", "end": "End of the process", "current": "Current step", "waiting": "Waiting for", "next": "Next steps",
           "summary": "Case summary", "deadlines": "Deadlines", "documents": "Document checklist", "facts": "Accepted facts",
           "open": "Open points", "assessment": "Short assessment (draft)", "knowledge": "From earlier cases (Knowledge)",
           "reply": "Reply draft — not sent", "files": "Files of the case", "document": "Document", "status": "Status",
           "source": "Source", "question": "Question", "answer": "Answer", "checked": "Check", "page": "p.", "none": "—",
           "present": "present", "missing": "missing", "unusable": "unusable", "unchecked": "not checked", "open_need": "open",
           "accepted": "supported", "rejected": "not supported", "not_checked": "not checked", "conflicting": "conflicting",
           "yes": "yes", "no": "no", "used": "used", "suggested": "suggested by Knowledge", "optional": "optional",
           "depends": "depends on an open answer", "obtain": "Obtain", "resolve": "Not met", "ask": "Answer",
           "attached": "Attached to", "scanned": "scanned pages read by the model", "pages": "pages", "page_one": "page", "by_law": "required by law:", "not_prepared": "The case is not prepared yet.",
           "suggested_case": "suggested for this case", "basis": "basis:", "applies_if": "applies if:", "doubt": "the check doubts it:",
           "warnings": "Notes on the preparation",
           "checklist_only": "Checklist only: no summary, assessment or reply draft was prepared.",
           "result_checker_stopped": "Not finished: the checklist rests on the accepted findings; see the checklist and the open points.",
           "stop_document_finder": "The document search stopped early; documents it did not reach stay requested and are marked not checked.",
           "stop_claim_reader": "The reading of the facts stopped early; facts it did not record stay open.",
           "stop_process_builder": "Adding to the process stopped early; the process's own requirements are complete.",
           "stop_result_checker": "The summary stopped early; no reply draft was prepared.",
           "reading_failed": "One reading of the facts failed; the facts it should have confirmed stay open.",
           "document_check_failed": "The second check of the documents found present failed; they stay requested.",
           "instruction_like_text": "A document contains text addressed to an AI; it was treated as evidence and not followed.",
           "routing_contradicted": "The readings of the files contradict the chosen process's condition; the process stays and a person checks it.",
           "rerouted": "The readings of the files contradicted the first routing ({first}); the case was routed again.",
           "handed_over": "The readings of the files contradict the routing ({first}); a person chooses the process.",
           "admitted": "admitted by the readings"},
}


def _run(text, bold=False, size=None, color=None, italic=False):
    props = "".join([("<w:b/>" if bold else ""), ("<w:i/>" if italic else ""), (f'<w:color w:val="{color}"/>' if color else ""),
                     (f'<w:sz w:val="{size}"/>' if size else "")])
    parts = str(text).split("\n")
    body = '<w:br/>'.join(f'<w:t xml:space="preserve">{escape(p)}</w:t>' for p in parts)
    return f"<w:r>{f'<w:rPr>{props}</w:rPr>' if props else ''}{body}</w:r>"


def _para(*runs, space_after=120):
    return f'<w:p><w:pPr><w:spacing w:after="{space_after}"/></w:pPr>{"".join(runs)}</w:p>'


def _heading(text):
    return f'<w:p><w:pPr><w:keepNext/><w:spacing w:before="280" w:after="100"/></w:pPr>{_run(text, bold=True, size=26, color="82072A")}</w:p>'


def _table(header, rows, widths):
    grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in widths)
    borders = "".join(f'<w:{side} w:val="single" w:sz="4" w:space="0" w:color="BBBBBB"/>' for side in ("top", "left", "bottom", "right", "insideH", "insideV"))

    def cell(content, width, bold=False, shade=None):
        fill = f'<w:shd w:val="clear" w:color="auto" w:fill="{shade}"/>' if shade else ""
        return (f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>{fill}</w:tcPr>'
                f'{_para(_run(content, bold=bold, size=18), space_after=40)}</w:tc>')
    out = [f'<w:tbl><w:tblPr><w:tblW w:w="{sum(widths)}" w:type="dxa"/><w:tblBorders>{borders}</w:tblBorders></w:tblPr><w:tblGrid>{grid}</w:tblGrid>']
    out.append('<w:tr><w:trPr><w:tblHeader/></w:trPr>' + "".join(cell(h, w, True, "F6EFF0") for h, w in zip(header, widths)) + "</w:tr>")
    for row in rows:
        out.append("<w:tr>" + "".join(cell(c, w) for c, w in zip(row, widths)) + "</w:tr>")
    out.append("</w:tbl>")
    return "".join(out) + _para(space_after=60)


def _docx(body):
    document = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="{W}"><w:body>{body}'
                '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" '
                'w:header="567" w:footer="567" w:gutter="0"/></w:sectPr></w:body></w:document>')
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                         '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                         '<Default Extension="xml" ContentType="application/xml"/>'
                         '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        archive.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                         '<Relationship Id="r1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        archive.writestr("word/document.xml", document)
    return out.getvalue()


def _value(value, L):
    return L["yes"] if value is True else L["no"] if value is False else L["none"] if value is None else str(value)


def build(case, state, files, lang="de", knowledge=()):
    """The report as .docx bytes. ``state``: the case state (process, evaluation, run with its result)."""
    L = LABELS.get(lang, LABELS["de"])
    run = state.get("run") or {}
    result = run.get("result") or {}
    names = {f["id"]: f["name"] for f in files}

    def where(citation):
        page = f", {L['page']} {citation['page']}" if citation.get("page") else ""
        return f"«{citation.get('quote', '')}» — {names.get(citation.get('file'), citation.get('file', ''))}{page}"
    body = [_para(_run(f"{L['title']}: {case['title']}", bold=True, size=36)),
            _para(_run(L["notice"], italic=True, size=18, color="61636B"))]
    meta = [f"{L['case']}: {case['id'][-8:].upper()}"]
    if run.get("finished_at"):
        meta.append(f"{L['prepared']}: {str(run['finished_at'])[:10]}")
    if state.get("workflow"):
        meta.append(f"{L['process']}: {state['workflow'].get('title', state['workflow'].get('id'))}")
    body.append(_para(_run(" · ".join(meta), size=18)))
    if not result:
        body.append(_para(_run(L["not_prepared"])))
        return _docx("".join(body))
    evaluation = state.get("evaluation") or result.get("evaluation") or {}
    questions = {f["id"]: f["question"] for f in (state.get("process") or {}).get("facts", [])}
    questions.update(result.get("questions") or {})

    def warning_key(w):  # a stop is described by the part that stopped, so the note is true for it
        return f"stop_{w.get('agent')}" if w.get("kind") in {"turn_limit", "no_report"} else w.get("kind")
    warnings = list(dict.fromkeys(L[warning_key(w)] for w in result.get("warnings") or [] if warning_key(w) in L))
    routing = result.get("routing") or {}
    for key, entry in (("rerouted", routing.get("rerouted")), ("handed_over", routing.get("conflict"))):
        if entry:  # a reroute or a hand-over after the readings, with the values they admitted and the passages
            first = (entry.get("routed_to") or {}).get("id", "")
            admitted = "; ".join(f"{a['fact']} = {a['value']} ({L['admitted']}: " + ", ".join(where(c) for c in a.get("citations") or []) + ")"
                                 for a in entry.get("admitted") or [])
            warnings.append(L[key].format(first=first) + (f" {admitted}" if admitted else ""))
    if warnings:
        body.append(_heading(L["warnings"]))
        for text_ in warnings:
            body.append(_para(_run(f"• {text_}"), space_after=40))

    body.append(_heading(L["position"]))
    if evaluation.get("outcome"):
        body.append(_para(_run(f"{L['end']}: ", bold=True), _run(evaluation["outcome"].get("title", ""))))
    elif evaluation.get("current"):
        body.append(_para(_run(f"{L['current']}: ", bold=True), _run(evaluation["current"].get("title", ""))))
    if evaluation.get("waiting_for"):
        body.append(_para(_run(f"{L['waiting']}: ", bold=True), _run("; ".join(w["question"] for w in evaluation["waiting_for"]))))
    actions = evaluation.get("next_actions") or []
    if actions:
        body.append(_para(_run(L["next"], bold=True), space_after=40))
        kinds = {"answer": L["ask"], "resolve": L["resolve"], "obtain": L["obtain"]}
        for action in actions:
            body.append(_para(_run(f"• {kinds.get(action['kind'], '')}: {action['text']}"), space_after=40))

    if result.get("case_summary"):
        body.append(_heading(L["summary"]))
        body.append(_table([L["summary"], ""], [[row["label"], row["text"]] for row in result["case_summary"]], [2600, 7038]))
    if result.get("deadlines"):
        body.append(_heading(L["deadlines"]))
        body.append(_table([L["deadlines"], L["question"]], [[d["date"], d["question"]] for d in result["deadlines"]], [2000, 7638]))

    findings = {d["document"]: d for d in result.get("documents", [])}
    checklist = evaluation.get("documents") or []
    if checklist:
        body.append(_heading(L["documents"]))
        rows = []
        for need in checklist:
            status = L.get(need["status"], need["status"]) + (f" ({L['unchecked']})" if need.get("not_checked") else "")
            definition = next((d for d in (state.get("process") or {}).get("documents", []) if d["id"] == need["document"]), {}) or {}
            suggested = L["suggested"] if definition.get("knowledge") else L["suggested_case"]
            note = {"suggested": suggested, "optional": L["optional"], "depends": L["depends"]}.get(need.get("required"))
            basis = definition.get("legal_basis")
            if basis:  # a statute named by a suggestion is its basis, not a requirement
                note = f"{note}; {L['basis']} {basis}" if need.get("required") == "suggested" else f"{L['by_law']} {basis}" + (f"; {note}" if note else "")
            if need.get("required") == "suggested" and need.get("questions"):
                note += f"; {L['applies_if']} " + " / ".join(q["question"] for q in need["questions"])
            cites = (findings.get(need["document"]) or {}).get("citations") or need.get("citations") or []
            rows.append([need["title"] + (f" ({note})" if note else ""), status, "\n".join(where(c) for c in cites) or L["none"]])
        body.append(_table([L["document"], L["status"], L["source"]], rows, [2900, 1300, 5438]))

    facts = [f for f in result.get("facts", []) if f.get("status") in ("established", "conflicting")]
    if facts:
        body.append(_heading(L["facts"]))
        rows = [[questions.get(f["fact"], f["fact"]), _value(f.get("value"), L), L.get(f.get("verdict") or "not_checked", f.get("verdict") or "")
                 + (f"\n{L['doubt']} {f['flag'].get('reason', '')}" if f.get("flag") else ""),
                 "\n".join(where(c) for c in f.get("citations", [])) or L["none"]] for f in facts]
        body.append(_table([L["question"], L["answer"], L["checked"], L["source"]], rows, [2600, 1500, 1200, 4338]))

    if result.get("open_points"):
        body.append(_heading(L["open"]))
        body += [_para(_run(f"• {point}"), space_after=40) for point in result["open_points"]]
    if result.get("answer") or result.get("summary"):
        body.append(_heading(L["assessment"]))
        if result.get("answer_code") in L:  # written by the product, not by an agent: in the reader's language
            body.append(_para(_run(L[result["answer_code"]], bold=True)))
        elif result.get("answer"):
            body.append(_para(_run(result["answer"], bold=True)))
        if result.get("summary") and not result.get("answer_code"):
            body.append(_para(_run(result["summary"])))

    applied = [k for k in ((state.get("provenance") or {}).get("knowledge") or []) if k.get("applied")]
    if applied:
        items = {k["id"]: k for k in knowledge}
        body.append(_heading(L["knowledge"]))
        for k in applied:
            content = (items.get(k["item"]) or {}).get("content") or {}
            title = content.get("title") or content.get("question") or content.get("text") or k["item"]
            body.append(_para(_run(f"• {title} — v{k.get('version', '?')} {L['used']}"), space_after=40))

    reply = result.get("reply") or {}
    if reply.get("needed") and reply.get("clauses"):
        body.append(_heading(L["reply"]))
        if reply.get("subject"):
            body.append(_para(_run(reply["subject"], bold=True)))
        body += [_para(_run(c["text"])) for c in reply["clauses"]]

    body.append(_heading(L["files"]))
    for f in files:
        extraction = f.get("extraction") or {}
        details = []
        shown = len(extraction["kept_pages"]) if extraction.get("kept_pages") else extraction.get("pages")  # a cut file: its kept pages
        if shown:
            details.append(f"{shown} {L['pages'] if shown != 1 else L['page_one']}")
        if extraction.get("pages_transcribed"):
            details.append(f"{len(extraction['pages_transcribed'])} {L['scanned']}")
        if extraction.get("attached_to"):
            details.append(f"{L['attached']} {extraction['attached_to']}")
        body.append(_para(_run(f"• {f['name']}" + (f" ({'; '.join(details)})" if details else "")), space_after=40))
    return _docx("".join(body))
