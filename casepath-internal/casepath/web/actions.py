"""The routes that carry the handler's decision through (process/completion.py):

- ``PUT /api/cases/{id}/drafts/{form}``: the handler's text of the letter (or an enclosure), saved per part while
  typing; a second writer gets 409 «Inzwischen von … geändert: neu laden»; ``…/resolve`` settles a part changed on both
  sides.
- ``POST /api/cases/{id}/actions/approve``: «Freigeben» approves the current version and stores its Versandpaket in the
  same request, or says why not.
- ``POST /api/cases/{id}/actions/dispatch``: «Versandt am», the handler's attributed confirmation of the sending, per
  recipient, written into the account once.
- ``POST /api/cases/{id}/actions/reconcile``: «Abgleich erledigt», the handler checked a letter that went out against
  what changed since (a fact it rests on, a jurist's mark on its legal content) and it stands.
- ``GET /api/cases/{id}/actions/{version}/bundle`` and ``…/docx/{kind}``: the stored Versandpaket and one document of it.

``approved_letter(store, case_id)`` is the one place every export takes the approved letter from once a letter is
approved (the Versandpaket's own Brief.docx, never a run's stored reply or a fresh rendering): the report and the draft
download call it (slice C's routes, NEEDS_B.md). Nothing is sent from here and nothing is paid: a dispatch is only an
attributed record. A frozen study copy refuses all of them and records nothing.
"""
from datetime import date
import threading
from typing import Literal
import uuid

from fastapi import Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from ..process import completion, letters
from . import bundle as versandpaket
from .store import Conflict, NotFound

STUDY = "Eine Studienkopie wird nicht bearbeitet: sie zeigt den eingefrorenen Lauf."
VERSION = r"^[0-9a-f]{64}$"
OP = r"^[A-Za-z0-9_.:-]{6,64}$"


class DraftPart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    part: str = Field(pattern=r"^(head|tail|text|p\d{1,3})$")
    base_sha256: str = Field(pattern=VERSION)  # the text the handler's edit started from
    text: str = Field(max_length=20000)


class DraftSave(BaseModel):
    model_config = ConfigDict(extra="forbid")
    parts: list[DraftPart] = Field(min_length=1, max_length=60)
    parent_id: str | None = Field(None, max_length=40)  # the form's latest save the handler's text builds on
    op_id: str = Field(pattern=OP)


class DraftResolve(BaseModel):
    model_config = ConfigDict(extra="forbid")
    part: str = Field(pattern=r"^(head|tail|text|p\d{1,3})$")
    keep: Literal["mine", "new"]


class Approve(BaseModel):
    model_config = ConfigDict(extra="forbid")
    form: str = Field(min_length=1, max_length=80)
    version: str = Field(pattern=VERSION)
    op_id: str = Field(pattern=OP)


class Reconcile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: str = Field(pattern=VERSION)
    op_id: str = Field(pattern=OP)


class Dispatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: str = Field(pattern=VERSION)
    recipients: list[Literal["kunde", "gegenpartei", "kanzlei", "behoerde", "andere"]] | None = None
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    channel: Literal["post", "email", "portal", "andere"]
    op_id: str = Field(pattern=OP)


def register(app, store, catalogue, mirror, record, state, user, case_view=None, parity_sha=None, marks=None):
    """The routes above, on ``app``. ``case_view``: the case view (web/app.py get_case), so the draft, its version and its
    state are exactly what the handler sees; ``record``: one event in the case's log, as every route writes it;
    ``marks``: the jurists' marks that hold now (web/app.py review_marks)."""
    approving = threading.Lock()  # one approval per version, also when two handlers press «Freigeben» at once

    def marks_now():
        return (marks() or {}) if marks else {}

    def case(case_id):
        try:
            return store.get_case(case_id)
        except NotFound:
            raise HTTPException(404, "Not found.") from None

    def refuse_study(row, message=STUDY):
        if (row.get("intake") or {}).get("study"):
            raise HTTPException(409, message)

    def sync():
        if mirror is not None:  # a copy on the volume, without holding up the handler
            threading.Thread(target=lambda: _quietly(mirror.sync), name="casepath-mirror-now", daemon=True).start()

    def document(view, form):
        draft = view.get("draft") or {}
        if (draft.get("form") or draft.get("kind")) == form and draft.get("text") is not None:
            return draft
        doc = next((a for a in draft.get("also") or () if a.get("kind") == form and a.get("text") is not None), None)
        if doc is None:
            raise HTTPException(422, "Dieses Schreiben gehört nicht zum vorbereiteten Schritt; bitte neu laden.")
        return doc

    def answer(case_id, form, who, saved=None):
        view = case_view(case_id, who=who)
        doc = document(view, form)
        return {**({"id": saved["id"], "by": saved["by"], "at": saved["at"]} if saved else {}), "draft_id": doc.get("draft_id"),
                "version": (view.get("draft") or {}).get("version"), "conflicts": doc.get("conflicts") or [], "parts": doc.get("parts") or [],
                "text": doc.get("text"), "line_parts": doc.get("line_parts"), "completion": view.get("completion")}

    @app.put("/api/cases/{case_id}/drafts/{form}")
    def save_draft(case_id: str, form: str, body: DraftSave, who=Depends(user)):
        """The handler's text of the prepared letter or one of its enclosures (``form``), saved per part while typing. It
        survives a reload, a handoff and a restart; a part re-rendered later keeps the handler's text where its base did
        not change. 409 «Inzwischen von … geändert: neu laden» when ``parent_id`` is not the latest save of the form; an
        ``op_id`` already stored returns its first result."""
        row = case(case_id)
        refuse_study(row)
        doc = document(case_view(case_id, who=who), form)
        current = {p["part"]: p for p in doc.get("parts") or ()}
        parts = [{"part": p.part, "base_sha256": p.base_sha256, "text": p.text,
                  "base": current[p.part]["base"] if p.part in current and current[p.part]["base_sha256"] == p.base_sha256 else ""} for p in body.parts]
        try:
            saved = store.add_draft(case_id, form, parts, who, parent_id=body.parent_id, op_id=body.op_id)
        except Conflict as error:
            raise HTTPException(409, str(error)) from None
        return answer(case_id, form, who, saved)

    @app.post("/api/cases/{case_id}/drafts/{form}/resolve")
    def resolve_draft(case_id: str, form: str, body: DraftResolve, who=Depends(user)):
        """A part the handler had edited and the case changed meanwhile: «meine Fassung behalten» (``mine``) or «neue
        Fassung übernehmen» (``new``); saved like the handler's text."""
        row = case(case_id)
        refuse_study(row)
        doc = document(case_view(case_id, who=who), form)
        clash = next((c for c in doc.get("conflicts") or () if c["part"] == body.part), None)
        if clash is None:
            raise HTTPException(422, "In diesem Absatz ist nichts zu klären.")
        now = next((p for p in doc.get("parts") or () if p["part"] == body.part and not clash.get("gone")), None)
        base = now["base"] if now else ""
        text = clash["mine"] if body.keep == "mine" else base
        saved = store.add_draft(case_id, form, [{"part": body.part, "base_sha256": completion.sha(base), "base": base, "text": text}], who,
                                parent_id=doc.get("draft_id"), op_id=f"resolve-{uuid.uuid4().hex[:12]}")
        return answer(case_id, form, who, saved)

    @app.post("/api/cases/{case_id}/actions/approve")
    def approve(case_id: str, body: Approve, who=Depends(user)):
        """«Freigeben»: approve the prepared letter's current version and store its Versandpaket (the exact text, the
        enclosures, the file note and the follow-up, one folder per recipient) in the same request. Refused while the
        version changed, new files are unread, a gap or a required part is open, a decision is open, or a part the handler
        edited changed meanwhile. The same request again, or the same version while its approval still holds, returns
        that record; a version whose approval no longer holds (a file came, a jurist marked what it rests on) is approved
        anew, with its own package («Erneut freigeben»)."""
        row = case(case_id)
        refuse_study(row, "Eine Studienkopie wird nicht freigegeben.")
        with approving:
            events = store.list_case_events(case_id)
            view = case_view(case_id, who=who)
            draft = view.get("draft") or {}
            done = view.get("completion") or {}
            existing = next((e for e in reversed(completion.approvals(events)) if e.get("op_id") == body.op_id), None)
            holding = (done.get("approved") or {}).get("version") == body.version and done.get("valid") and done.get("state") == "freigegeben"
            if existing is None and holding:
                existing = next((e for e in reversed(completion.approvals(events)) if e.get("event_id") == done["approved"].get("event")), None)
            if existing is None:
                if (draft.get("form") or draft.get("kind")) != body.form:
                    raise HTTPException(409, "Der Entwurf hat sich seit dem Laden geändert; bitte neu laden.")
                why = completion.refusal(row, draft, body.version, done.get("decisions") or [], bool(view.get("draft_stale")))
                if why:
                    raise HTTPException(*why)
                act = next((i for i in view.get("items") or () if i["kind"] == "next_action"), None) or {}
                prepared = store.latest_run(case_id, "completed")
                relies = completion.relied_elements(draft, view.get("assessment"), view.get("process"), view.get("items") or [], events)
                fields = completion.approval_record(draft, done.get("premise_now") or {}, view.get("assessment"), run_id=(prepared or {}).get("id"),
                                                    files_digest=store.files_digest(case_id), op_id=body.op_id, deadline=act.get("deadline"),
                                                    relies=relies, marks=marks_now(), file_ids=[f["id"] for f in store.list_files(case_id)])
                existing = record(case_id, who, "action.approved", **fields)
            saved = completion._bundle(store.list_case_events(case_id), existing)
            if saved is None:  # the Versandpaket, from the same state: the exact text, enclosures, note and next date
                saved = store_bundle(case_id, existing, view, who)
        sync()
        return {"approval": existing, "bundle": saved}

    def store_bundle(case_id, approval, view, who):
        draft = view.get("draft") or {}
        if draft.get("version") != approval["version"]:
            return None  # the version is no longer the one prepared: its package cannot be built from the same state
        events = store.list_case_events(case_id)
        package = [(draft["form"], draft["title"])] + [(a["kind"], a["title"]) for a in draft.get("also") or ()] if draft.get("also") else None
        stage = (((view.get("evaluation") or {}).get("current")) or {}).get("step")
        # what the letter asks and the follow-up as the case will count it: the reply date the letter sets; else the clock's
        # days from the dispatch (for a dispatch on the day of the approval: that date); else the case's follow-up
        clock = view.get("follow_up") or {}
        awaited, follow = completion.expected(approval.get("form"), approval.get("action_kind"), view.get("items") or [], events, view.get("assessment"),
                                              view.get("process"), stage, completion.swiss_day(approval.get("at")), approval.get("respond_by"),
                                              fallback=clock.get("due"), set_date=clock.get("due") if clock.get("set_by") else None)
        # the note says what the Wiedervorlage says: the letter's asks and the same date, never the documents of an earlier request
        took = completion.addressed(approval.get("action_kind"), approval.get("form"), view.get("assessment"), events)
        note = letters.file_note(view["case"], view.get("items") or [], events, view.get("follow_up"), store.list_files(case_id), package=package,
                                 awaited={"what": awaited, "when": versandpaket.when_line(approval.get("respond_by"), follow), "approved": True},
                                 approval_holds=True, answered={"title": draft.get("title"), "rows": took} if took else None)
        blob, _ = versandpaket.build(draft, approval, note, awaited, follow_up=follow, parity_sha=parity_sha)
        digest = store.put_blob(blob)
        return record(case_id, who, "bundle.saved", version=approval["version"], approval=approval.get("event_id"), sha256=digest, bytes=len(blob))

    @app.post("/api/cases/{case_id}/actions/dispatch")
    def dispatch(case_id: str, body: Dispatch, who=Depends(user)):
        """«Versandt am»: the handler confirms that an approved version went out, on a day and by a channel, per recipient
        (all of the version's by default). Each recipient is written once into the account (an entry of the form's record
        kind and code, with what it asked and the questions it answered); a version that no longer holds is accepted and
        flagged. The day is not after today and not before the approval (or a copy of the same text)."""
        row = case(case_id)
        refuse_study(row, "Eine Studienkopie wird nicht versandt.")
        events = store.list_case_events(case_id)
        approval = next((a for a in reversed(completion.approvals(events)) if a.get("version") == body.version), None)
        if approval is None:
            raise HTTPException(422, "Diese Fassung ist nicht freigegeben.")
        repeated = [e for e in events if e.get("kind") == "action.dispatched" and e.get("op_id") == body.op_id]
        if repeated:
            return {"dispatched": repeated}
        roles = list(dict.fromkeys(body.recipients or [r.get("to") for r in approval.get("recipients") or ()]))
        unknown = [r for r in roles if r not in {x.get("to") for x in approval.get("recipients") or ()}]
        if unknown:
            raise HTTPException(422, "Diese Empfänger gehören nicht zur freigegebenen Fassung.")
        day = date.fromisoformat(body.date)
        if day > completion.swiss_today():  # the handler's day: Swiss time
            raise HTTPException(422, "Das Versanddatum liegt in der Zukunft.")
        first = completion.earliest(approval, events, approval.get("form"))
        if first and body.date < first:
            raise HTTPException(422, f"Das Versanddatum liegt vor der Freigabe ({completion._day(first)}).")
        view = case_view(case_id, who=who)
        done = view.get("completion") or {}
        current = (view.get("draft") or {}).get("form") or (view.get("draft") or {}).get("kind")
        rest = done.get("rest") or {}
        stale = (done.get("stale") if (done.get("approved") or {}).get("version") == body.version
                 else rest.get("stale") or [] if rest.get("version") == body.version  # the rest of a package sent in part: what it rests on
                 else ["Schritt geändert" if approval.get("form") != current else "Text geändert"])
        prepared = store.latest_run(case_id, "completed")
        written = []
        for role in roles:
            args = completion.dispatch_args(approval, role, body.date, body.channel, view.get("items") or [], events, view.get("assessment"))
            # the questions the letter took up, conditional answers included: the file note and «Als Nächstes» no longer
            # list them as open at the insurer once it went out
            answered = completion.addressed(approval.get("action_kind"), args["form"], view.get("assessment"), events) if args["form"] == approval.get("form") else []
            event = {"schema": "casepath.study.event/1", "session_id": None, "expert": who, "case_copy": case_id, "source_case": None,
                     "frozen_run_id": (prepared or {}).get("id"), "kind": "action.dispatched", "parity_sha": parity_sha, "item_id": None,
                     "version": body.version, "recipient": role, "date": body.date, "channel": body.channel, "op_id": body.op_id,
                     "asks": [a["what"] for a in args["asks"]], **({"answered": answered} if answered else {}), **({"stale": stale} if stale else {})}
            edit, logged = store.dispatch_once(case_id, body.version, role, args, who, "Versandt (Bestätigung der Fallbearbeitung)", event)
            written.append(logged or {"kind": "action.dispatched", "version": body.version, "recipient": role, "edit_id": edit["id"],
                                      "date": edit["args"].get("date"), "channel": edit["args"].get("channel"), "repeated": True})
        sync()
        return {"dispatched": written}

    @app.post("/api/cases/{case_id}/actions/reconcile")
    def reconcile(case_id: str, body: Reconcile, who=Depends(user)):
        """«Abgleich erledigt»: a letter that went out rests on a fact that changed since, or on legal content a jurist
        marked since; the handler checked it against the case as it stands and it stays as sent (a correction would be its
        own letter). Records the premise and the marks it was checked against; a later change flags it again. The letter
        that went out keeps its version: nothing is unsent."""
        row = case(case_id)
        refuse_study(row, "Eine Studienkopie wird nicht bearbeitet.")
        events = store.list_case_events(case_id)
        repeated = next((e for e in events if e.get("kind") == "action.reconciled" and e.get("op_id") == body.op_id), None)
        if repeated:
            return {"reconciled": repeated}
        approval = next((a for a in reversed(completion.approvals(events)) if a.get("version") == body.version), None)
        if approval is None or not any(d["version"] == body.version for d in completion.dispatches(events, store.list_edits(case_id, active_only=False))):
            raise HTTPException(422, "Diese Fassung ist nicht versandt.")
        view = case_view(case_id, who=who)
        last = (view.get("completion") or {}).get("last") or {}
        meaning = last.get("consequence") or {}
        if last.get("version") != body.version or not (meaning.get("kind") == "contradiction" or last.get("stale")):
            raise HTTPException(422, "Für diese Fassung ist nichts abzugleichen.")
        premise = last.get("premise_now") or {}  # the premise as the state reads it now (the case's facts, else the assessment's)
        logged = record(case_id, who, "action.reconciled", version=body.version, premise=premise, changed=meaning.get("text"),
                        relies_marks=completion.marks_of(approval.get("relies"), marks_now()), op_id=body.op_id)
        sync()
        return {"reconciled": logged}

    def stored(case_id, version):
        events = store.list_case_events(case_id)
        approval = next((a for a in reversed(completion.approvals(events)) if a.get("version") == version), None)
        saved = completion._bundle(events, approval) if approval else None
        if approval is None or saved is None:
            raise HTTPException(404, "Für diese Fassung ist kein Versandpaket gespeichert.")
        return approval, store.blob(saved["sha256"])

    @app.get("/api/cases/{case_id}/actions/{version}/bundle")
    def get_bundle(case_id: str, version: str, who=Depends(user)):
        """The Versandpaket stored when the version was approved: «Versandpaket_<Referenz oder Fall>_<TT.MM.JJJJ>.zip»."""
        row = case(case_id)
        approval, blob = stored(case_id, version)
        name = versandpaket.file_name(row, approval.get("at"))
        return Response(blob, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{name}"',
                                                                     "Cache-Control": "private, no-store"})

    @app.get("/api/cases/{case_id}/actions/{version}/docx/{kind}")
    def get_docx(case_id: str, version: str, kind: str, who=Depends(user)):
        """One document of a stored Versandpaket (the letter's form or an enclosure's kind), as .docx."""
        case(case_id)
        _, blob = stored(case_id, version)
        found = versandpaket.member(blob, kind)
        if found is None:
            raise HTTPException(404, "Dieses Dokument ist nicht im Versandpaket.")
        name, data = found
        from urllib.parse import quote
        return Response(data, media_type=versandpaket.DOCX, headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name, safe='')}",
                                                                     "Cache-Control": "private, no-store"})

    return app


def approved_letter(store, case_id, version=None):
    """The letter as approved, for every export once a letter is approved: {version, form, title, approved_at,
    approved_by, name, docx (the Versandpaket's own Brief.docx bytes), text (its paragraphs), bundle (sha256)} of the
    latest approval whose Versandpaket is stored, or None before any approval. The report and the draft download serve
    this, never a run's stored reply or a fresh rendering (slice C's routes; NEEDS_B.md). ``version``: the letter the
    case shows now; only an approval of that version counts, so a correction that changed the letter after its approval
    is never answered with the letter as it was approved (the version itself stays in its Versandpaket)."""
    events = store.list_case_events(case_id)
    for approval in reversed(completion.approvals(events)):
        if version is not None and approval.get("version") != version:
            continue
        saved = completion._bundle(events, approval)
        if saved is None:
            continue
        blob = store.blob(saved["sha256"])
        found = versandpaket.member(blob, approval.get("form"))
        if found is None:
            continue
        name, data = found
        main = next((r for r in approval.get("recipients") or () if approval.get("form") in (r.get("forms") or ())), None) or {}
        return {"version": approval.get("version"), "form": approval.get("form"), "title": approval.get("title"), "approved_at": approval.get("at"),
                "approved_by": approval.get("expert"), "to": main.get("title") or main.get("to"), "recipient": main.get("recipient"),
                "name": name, "docx": data, "text": versandpaket.text_of(data), "bundle": saved.get("sha256")}
    return None


def _quietly(call):
    try:
        call()
    except Exception:  # noqa: BLE001  the mirror retries on its own interval
        pass
