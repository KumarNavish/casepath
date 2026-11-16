"""Background runs on the development workspace: the case service's side of the agent core's contract.

A run evaluates the files present when it starts. Its status always says what happened: completed, failed (with the
reason), or interrupted by a restart. The run service builds a job from the store (case, files, catalogue, active
Knowledge, edits), hands it to the agent core (``core.prepare``) on a worker thread and saves the outcome: each
file's reading as soon as it is done, the result, each applied Knowledge item's statistics on its current version,
and the result checker's proposals as candidate Knowledge. A re-check after a process edit runs only the document
finder and the source checker on the needs the edit added. An update («Aktualisieren», run kind «update») reads only the
files added since the latest completed run and builds on it (``builds_on``); its tokens and seconds are its own, it
learns no Knowledge, and a stopped update keeps nothing but the new files' reading (status «discarded»). In an operated
deployment, a queue worker calls the same core functions with the same job, and the case service saves the outcome the
same way.

Every update is capped by its own token budget (``update_token_budget``, within the run's). Where the deployment starts
updates by itself (``auto_update``: an upload into a prepared case starts one, web/app.py), an update started so is
followed by one more, once, when a file came in while it ran; and an update interrupted by a restart is started again,
once, when the case still has unread files and nothing ran after it (``update.started`` {auto, run, resumed} in the
case's log). A failed or capped update is never retried by itself. Nothing already read is read again: the new files'
pages read before the interruption were saved with their reading.

An update reads exactly the inputs admitted when it was created (``update.admitted`` among its events: the files the run
it builds on did not read, and their pages, checked against the page cap when it starts by itself); a file that comes
later waits for the next update, also when the update is started again after a restart: the resumed update reads only the
inputs the interrupted one admitted, and a later arrival stays pending with «Aktualisieren» and its reason. An update
interrupted before this record existed is started again only when the case's actual unread set is within the cap.
"""
from concurrent.futures import ThreadPoolExecutor

from . import core
from ..process import knowledge as kb, workflows
from .azure_model import ModelError
from ..web.store import ACTIVE, Conflict, now


ADMITTED = "update.admitted"  # an update's own event: the inputs it reads ({files, pages}), recorded when it is created


class TooLarge(Conflict):
    """An update that would start by itself while the unread files have more pages than the deployment's cap."""


def pages_of(files, ids=None):
    """The pages of these files (all, or those of ``ids``); a file without pages counts as one."""
    ids = None if ids is None else set(ids)
    return sum(len((f.get("extraction") or {}).get("kept_pages") or ()) or int((f.get("extraction") or {}).get("pages") or 0) or 1
               for f in files or () if ids is None or f["id"] in ids)


def unread_pages(files, run):
    """The pages of the case's files a run did not read (a file without pages counts as one), for the cap of an update
    an upload starts by itself."""
    return pages_of(files, core.unread(files, run))


def admitted(run):
    """The file ids an update admitted when it was created (its ``update.admitted`` event), or None for an update made
    before updates recorded them."""
    return next((list(e.get("files") or ()) for e in (run or {}).get("events") or () if e.get("kind") == ADMITTED), None)


def auto_update_reason(store, case_id, max_pages):
    """Why an update cannot start by itself now, as the upload answers it («zu_gross», «lauf_aktiv», a blocked reason of
    core.update_blocked, «studienkopie»), or None when it can (the deployment's setting is checked by the caller)."""
    case = store.get_case(case_id)
    if (case.get("intake") or {}).get("study"):
        return "studienkopie"
    latest = store.latest_run(case_id)
    if latest and latest["status"] in ACTIVE:
        return "lauf_aktiv"
    base, files = store.latest_run(case_id, "completed"), store.list_files(case_id)
    blocked = core.update_blocked(case, files, base)
    if blocked:
        return blocked[0]
    if max_pages and unread_pages(files, base) > max_pages:
        return "zu_gross"
    return None


def case_files(store, case_id):
    return core.case_files(store.list_files(case_id, with_text=True))


def case_state(store, catalogue, case_id, knowledge=None, study=None):
    """The case's current process and evaluation, from the latest completed run plus later edits.

    knowledge: a Knowledge version to apply instead of the store's active items (for a model-free replay).
    study: evaluate by the account rules of the frozen expert study (core.evaluate); None: as the case is, a study copy
    by them, any other case by the current ones. The frozen-run checks pass True, so a source case is frozen and compared
    on the rules its copies are evaluated by."""
    case = store.get_case(case_id)
    study_copy = (case.get("intake") or {}).get("study")  # a study copy shows its source's frozen run, never one of its own
    if study_copy:
        run = store.get_run(study_copy["frozen_run_id"])
    else:  # a run stopped by a person shows what it established until a later run completes
        done, paused = store.latest_run(case_id, "completed"), store.latest_run(case_id, "paused")
        run = paused if paused and (not done or paused["created_at"] > done["created_at"]) else done
    result = (run or {}).get("result") or {}
    if run and not study_copy and (result.get("brief") or {}).get("claims"):
        # the costs claimed, each with its id and current version and the handler's answers to unclear ones in force
        from ..process import claims
        result = {**result, "brief": {**result["brief"], "claims": claims.effective(result["brief"]["claims"], store.list_edits(case_id))}}
        run = {**run, "result": result}
    workflow = None
    # A run names the workflow version it used; when that version is no longer shipped, the latest one of the same workflow governs.
    if case.get("workflow_id"):
        workflow = catalogue.get(case["workflow_id"], case.get("workflow_version")) or catalogue.get(case["workflow_id"])
    elif run and run.get("workflow_id"):
        workflow = catalogue.get(run["workflow_id"], run.get("workflow_version")) or catalogue.get(run["workflow_id"])
    if workflow is None:
        return {"case": case, "workflow": None, "process": None, "evaluation": None, "run": run}
    if knowledge is None:
        knowledge = store.list_knowledge(workflow["id"], {"active"})  # only what a person has activated shapes a case
    else:
        knowledge = [k for k in knowledge if workflow["id"] in (k["family"] if isinstance(k["family"], list) else [k["family"]])]
    state = core.evaluate(workflow, knowledge, store.list_edits(case_id), result, case_id, files=store.list_files(case_id),
                          study=bool(study_copy) if study is None else bool(study))
    ran = (run or {}).get("workflow_version")
    versions = {"run_version": ran, "governing_version": workflow["version"]} if ran and ran != workflow["version"] else {}
    return {"case": case, "workflow": workflows.ref(workflow), **state, "run": run, "knowledge": knowledge, **versions}


class RunService:
    def __init__(self, store, catalogue, model_factory, *, max_workers=2, effort="medium", read_scans=True, reading_workers=1, page_image_side=1700,
                 token_budget=0, voice=None, speed_trials=(), auto_update=False, auto_update_max_pages=20, update_token_budget=0,
                 model_as_user=False, parity_sha=None):
        """``auto_update``: updates start by themselves (an upload, a file that came during an update, a restart);
        ``update_token_budget``: the cap of every update; ``model_as_user``: the model is called as the person who started
        a run, so nothing can start without that person (an interrupted update then waits for «Erneut aktualisieren»)."""
        self.store, self.catalogue, self.model_factory, self.effort = store, catalogue, model_factory, effort
        self.read_scans, self.reading_workers, self.page_image_side = read_scans, reading_workers, page_image_side
        self.token_budget, self.voice, self.speed_trials = token_budget, voice or {}, tuple(speed_trials)
        self.auto_update, self.auto_update_max_pages, self.update_token_budget = auto_update, auto_update_max_pages, update_token_budget
        self.model_as_user = model_as_user
        self._parity = parity_sha  # the source's hash the service's own log lines carry: given by the app, else computed once (_source)
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="casepath-run")
        self._stops = set()  # runs a person asked to stop ("Anhalten"); checked between turns
        self.resumed = self._resume(self.store.interrupt_unfinished())

    def start(self, case_id, user, token=None):
        """``token``: the person's own model token, when the model is called as the person who started the run."""
        run = self.store.create_run(case_id, user)
        self._pool.submit(self._execute, run["id"], case_id, token)
        return run

    def update(self, case_id, user, token=None, auto=False, budget=None, follow=None, max_pages=0, only=None):
        """«Aktualisieren»: a run that reads only what came in since the latest completed run and builds on it. Conflict,
        with the reason in the handler's words, when it cannot (core.update_blocked). ``auto``: started by an upload (or by
        a restart), so one more update follows, once, when a file came in while it ran (``follow`` False for that one);
        ``budget``: its token cap, else the deployment's update cap, never above the run's. The files it reads are admitted
        now and recorded with the run (``update.admitted``): the unread files (``only``: of these, as a resumed update
        reads only what the interrupted one admitted), within ``max_pages`` pages when given (TooLarge otherwise); a file
        that comes later waits for the next update."""
        base = self.store.latest_run(case_id, "completed")
        files = self.store.list_files(case_id)
        blocked = core.update_blocked(self.store.get_case(case_id), files, base)
        if blocked:
            raise Conflict(blocked[1])
        inputs = [f for f in core.unread(files, base) if only is None or f in set(only)]
        if not inputs:
            raise Conflict(core.NOTHING_NEW)
        pages = pages_of(files, inputs)
        if max_pages and pages > max_pages:
            raise TooLarge("zu_gross")
        run = self.store.create_run(case_id, user, kind="update", builds_on=base["id"])
        self.store.append_event(run["id"], {"agent": "runner", "kind": ADMITTED, "files": inputs, "pages": pages})
        limits = [x for x in (budget or self.update_token_budget, self.token_budget) if x]
        again = bool(auto) if follow is None else bool(follow)
        self._pool.submit(self._update, run["id"], case_id, base["id"], token, min(limits) if limits else 0, again, inputs)
        return run

    def _update(self, run_id, case_id, base_id, token=None, budget=0, again=False, inputs=None):
        try:
            self.store.update_run(run_id, status="running")
            prior = self.store.get_run(base_id)
            outcome = core.update(self.job(case_id, budget, admitted=(prior, inputs) if inputs is not None else None), prior,
                                  self._model(run_id, token), core.StoreBlobs(self.store),
                                  on_event=lambda e: self._event(run_id, e),
                                  on_extraction=lambda file_id, extraction: self.store.update_extraction(file_id, extraction),
                                  should_stop=lambda: run_id in self._stops, edits_now=lambda: self.store.list_edits(case_id))
            self.save(run_id, case_id, outcome)
        except ModelError as error:
            self.store.update_run(run_id, status="failed", error=f"{error.reason}: {error}", finished_at=now())
        except Exception as error:  # Every failure ends the run with a stated reason.
            self.store.update_run(run_id, status="failed", error=f"internal: {type(error).__name__}: {error}", finished_at=now())
        finally:
            self._stops.discard(run_id)
            if again:
                self._again(run_id, case_id, token, budget)

    def _again(self, run_id, case_id, token, budget):
        """After an update started by itself completed: a file that came in while it ran gets one more update, once (it
        is started with the same cap, and nothing follows it). A failed, stopped or capped update starts nothing."""
        try:
            run = self.store.get_run(run_id)
            if run["status"] != "completed" or not self.auto_update or auto_update_reason(self.store, case_id, self.auto_update_max_pages):
                return
            self._source()  # before the follow-on starts: its log line is written at once, never after it finished
            later = self.update(case_id, run["created_by"], token, auto=True, budget=budget, follow=False, max_pages=self.auto_update_max_pages)
            self.log(case_id, run["created_by"], "update.started", auto=True, run=later["id"], follows=run_id)
        except Exception:  # noqa: BLE001  the case keeps its «Aktualisieren»: the arrival is shown, nothing is lost
            return

    def _resume(self, interrupted):
        """After a restart: each update the restart interrupted is started again, once, by itself, when the deployment
        starts updates by itself, the model is not called as a person, the case still has files its last preparation did
        not read and nothing ran after the interrupted update. It reads only the inputs the interrupted update admitted
        (``update.admitted``); what came later stays pending with «Aktualisieren» and its reason. An interrupted update
        without that record is started again only when the case's actual unread files are within the page cap. An update
        that was itself such a restart is not started again. Returns the new runs' ids."""
        out = []
        if not self.auto_update or self.model_as_user:
            return out
        for run_id in interrupted:
            try:
                run = self.store.get_run(run_id)
                case_id = run["case_id"]
                if run.get("kind") != "update" or (self.store.latest_run(case_id) or {}).get("id") != run_id:
                    continue
                logged = [e for e in self.store.list_case_events(case_id) if e.get("kind") == "update.started"]
                if any(e.get("run") == run_id and e.get("resumed") for e in logged) or any(e.get("resumed") == run_id for e in logged):
                    continue  # a restart's own update, or one already started again: at most once
                inputs = admitted(run)
                # unread files and nothing blocking; without the admitted inputs, the actual unread set within the cap
                if auto_update_reason(self.store, case_id, 0 if inputs is not None else self.auto_update_max_pages):
                    continue
                self._source()
                again = self.update(case_id, run["created_by"], None, auto=True, only=inputs)
                self.log(case_id, run["created_by"], "update.started", auto=True, run=again["id"], resumed=run_id)
                out.append(again["id"])
            except Exception:  # noqa: BLE001  the case shows «unterbrochen» with «Erneut aktualisieren»
                continue
        return out

    def _source(self):
        """The hash of the source the service runs (parity.source_tree), computed at most once. Hashing the tree can take
        seconds on a slow disk, so whoever starts a run and then logs it asks for it before starting the run."""
        if not getattr(self, "_parity", None):
            from ..parity import source_tree
            self._parity = source_tree()[0]
        return self._parity

    def log(self, case_id, who, kind, **fields):
        """An event of the case's log written by the run service itself (casepath.study.event/1, as web/app.py writes)."""
        self._source()
        completed = self.store.latest_run(case_id, "completed")
        return self.store.append_case_event(case_id, {"schema": "casepath.study.event/1", "session_id": None, "expert": who, "case_copy": case_id,
                                                      "source_case": None, "frozen_run_id": (completed or {}).get("id"), "kind": kind,
                                                      "parity_sha": self._parity, "item_id": None, **fields})

    def recheck(self, case_id, document_ids, user, token=None):
        run = self.store.create_run(case_id, user)
        self._pool.submit(self._recheck, run["id"], case_id, list(document_ids), token)
        return run

    def resume(self, paused, user, token=None):
        """'Weiter': a new run that continues a paused one from what it established."""
        run = self.store.create_run(paused["case_id"], user)
        case = self.store.get_case(paused["case_id"])
        chosen = case.get("workflow_id")  # "anderer Prozess": a workflow chosen while paused governs the continued run
        changed = bool(chosen) and chosen != paused["workflow_id"]
        result = paused["result"]
        if changed:  # the reading stays; what depended on the old process is done again
            result = {**result, "facts": [], "documents": [], "done": [d for d in result.get("done") or [] if d == "0:claim_reader"]}
        job = {**self.job(paused["case_id"]), "resume": {
            "run": paused["id"], "result": result, "changed": changed,
            "workflow_id": chosen if changed else paused["workflow_id"],
            "workflow_version": case.get("workflow_version") if changed else paused.get("workflow_version")}}
        self._pool.submit(self._execute, run["id"], paused["case_id"], token, job)
        return run

    def stop(self, run_id):
        self._stops.add(run_id)

    def shutdown(self):
        self._pool.shutdown(wait=False, cancel_futures=True)

    def job(self, case_id, budget=None, admitted=None):
        """The agent core's job for this case, from the store; ``budget``: this run's token cap instead of the run's;
        ``admitted``: (the run an update builds on, the file ids it admitted): the files that run read and these only, so a
        file that came after the update was created is not among its new files."""
        files = self.store.list_files(case_id, with_text=True)
        if admitted is not None:
            prior, inputs = admitted
            unread, inputs = set(core.unread(files, prior)), set(inputs)
            files = [f for f in files if f["id"] not in unread or f["id"] in inputs]
        return {"format": core.JOB, "case": self.store.get_case(case_id), "files": files,
                "workflows": list(self.catalogue.workflows), "knowledge": self.store.list_knowledge(None, {"active"}),
                "edits": self.store.list_edits(case_id),
                "options": {"effort": self.effort, "read_scans": self.read_scans, "reading_workers": self.reading_workers,
                            "page_image_side": self.page_image_side, "token_budget": budget or self.token_budget, "voice": self.voice,
                            **({"speed_trials": list(self.speed_trials)} if self.speed_trials else {})}}

    def _event(self, run_id, data):
        self.store.append_event(run_id, data)

    def _model(self, run_id, token=None):
        # None when no deployment is configured; the core then fails the run with that reason
        model = self.model_factory(token) if token is not None else self.model_factory()
        if model is not None:
            self.store.update_run(run_id, deployment=model.settings.deployment)
        return model

    def _execute(self, run_id, case_id, token=None, job=None):
        try:
            self.store.update_run(run_id, status="running")
            outcome = core.prepare(job or self.job(case_id), self._model(run_id, token), core.StoreBlobs(self.store),
                                   on_event=lambda e: self._event(run_id, e),
                                   on_extraction=lambda file_id, extraction: self.store.update_extraction(file_id, extraction),
                                   should_stop=lambda: run_id in self._stops, edits_now=lambda: self.store.list_edits(case_id))
            self.save(run_id, case_id, outcome)
        except ModelError as error:
            self.store.update_run(run_id, status="failed", error=f"{error.reason}: {error}", finished_at=now())
        except Exception as error:  # Every failure ends the run with a stated reason.
            self.store.update_run(run_id, status="failed", error=f"internal: {type(error).__name__}: {error}", finished_at=now())
        finally:
            self._stops.discard(run_id)  # a stop pressed too late for this run must not linger

    def save(self, run_id, case_id, outcome):
        """Persist an agent outcome: readings, routing, result, Knowledge statistics and proposals."""
        for file_id, extraction in outcome["extractions"].items():
            self.store.update_extraction(file_id, extraction)
        if outcome["status"] == "stopped":  # an update stopped by a person keeps nothing: the case shows the run it built on
            self.store.update_run(run_id, status="discarded", error="stopped: Aktualisierung angehalten; nichts übernommen", finished_at=now())
            return
        if outcome["status"] == "paused":  # stopped by a person: the partial result is kept for "Weiter"
            self.store.update_run(run_id, status="paused", result=outcome["result"], finished_at=now(),
                                  **({"workflow_id": outcome["workflow"]["id"], "workflow_version": outcome["workflow"]["version"]} if outcome.get("workflow") else {}))
            return
        if outcome["status"] != "completed":
            self.store.update_run(run_id, status="failed", error=outcome["error"], finished_at=now())
            return
        if outcome["routing"] is not None:
            self.store.update_run(run_id, routing=outcome["routing"])
        workflow = outcome["workflow"]
        if workflow is None:
            self.store.update_run(run_id, status="completed", result=outcome["result"], finished_at=now())
            return
        self.store.update_run(run_id, workflow_id=workflow["id"], workflow_version=workflow["version"])
        result = outcome["result"]
        if "recheck_of" not in result and "update" not in result:  # an update learns nothing: the run it builds on did
            result["learned"] = self._learn(case_id, run_id, outcome)
        self.store.update_run(run_id, status="completed", result=result, finished_at=now())

    def _learn(self, case_id, run_id, outcome):
        outcomes = []
        for row in outcome["knowledge_outcomes"]:
            item = self.store.get_knowledge(row["item"])  # the current version, whatever other runs changed meanwhile
            updated = kb.record_outcome(item, case_id=case_id, run_id=run_id, document_status=row["document_status"],
                                        contradicted=row["contradicted"], reason=row["reason"])
            self.store.save_knowledge(updated)
            label = "contradicted" if row["contradicted"] else row["document_status"] or "applied"
            self.store.record_use(item["id"], run_id, case_id, label)
            outcomes.append({"item": item["id"], "outcome": label})
        proposals = []
        for row in outcome["knowledge_proposals"]:
            item = {**row["item"], "origin": {**row["item"]["origin"], "run_id": run_id}}
            self.store.save_knowledge(item)
            proposals.append({"item": item["id"], "action": row["action"], "refines": row.get("refines")})
        return {"outcomes": outcomes, "proposals": proposals}

    def _recheck(self, run_id, case_id, document_ids, token=None):
        try:
            self.store.update_run(run_id, status="running")
            previous = self.store.latest_run(case_id, "completed")
            if previous is None or not previous.get("workflow_id"):
                self.store.update_run(run_id, status="failed", error="no_assessment: The case needs a completed run before a re-check.",
                                      finished_at=now())
                return
            outcome = core.recheck(self.job(case_id), previous, document_ids, self._model(run_id, token), on_event=lambda e: self._event(run_id, e))
            self.save(run_id, case_id, outcome)
        except ModelError as error:
            self.store.update_run(run_id, status="failed", error=f"{error.reason}: {error}", finished_at=now())
        except Exception as error:
            self.store.update_run(run_id, status="failed", error=f"internal: {type(error).__name__}: {error}", finished_at=now())
