"""Background runs on the development workspace: the case service's side of the agent core's contract.

A run evaluates the files present when it starts. Its status always says what happened: completed, failed (with the
reason), or interrupted by a restart. The run service builds a job from the store (case, files, catalogue, active
Knowledge, edits), hands it to the agent core (``core.prepare``) on a worker thread and saves the outcome: each
file's reading as soon as it is done, the result, each applied Knowledge item's statistics on its current version,
and the result checker's proposals as candidate Knowledge. A re-check after a process edit runs only the document
finder and the source checker on the needs the edit added. In an operated deployment, a queue worker calls the same
core functions with the same job, and the case service saves the outcome the same way.
"""
from concurrent.futures import ThreadPoolExecutor

from . import core
from ..process import knowledge as kb, workflows
from .azure_model import ModelError
from ..web.store import now


def case_files(store, case_id):
    return core.case_files(store.list_files(case_id, with_text=True))


def case_state(store, catalogue, case_id, knowledge=None):
    """The case's current process and evaluation, from the latest completed run plus later edits.

    knowledge: a Knowledge version to apply instead of the store's active items (for a model-free replay)."""
    case = store.get_case(case_id)
    study = (case.get("intake") or {}).get("study")  # a study copy shows its source's frozen run, never one of its own
    run = store.get_run(study["frozen_run_id"]) if study else store.latest_run(case_id, "completed")
    result = (run or {}).get("result") or {}
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
    state = core.evaluate(workflow, knowledge, store.list_edits(case_id), result, case_id)
    ran = (run or {}).get("workflow_version")
    versions = {"run_version": ran, "governing_version": workflow["version"]} if ran and ran != workflow["version"] else {}
    return {"case": case, "workflow": workflows.ref(workflow), **state, "run": run, "knowledge": knowledge, **versions}


class RunService:
    def __init__(self, store, catalogue, model_factory, *, max_workers=2, effort="medium", read_scans=True, reading_workers=1, page_image_side=1700,
                 token_budget=0, voice=None):
        self.store, self.catalogue, self.model_factory, self.effort = store, catalogue, model_factory, effort
        self.read_scans, self.reading_workers, self.page_image_side = read_scans, reading_workers, page_image_side
        self.token_budget, self.voice = token_budget, voice or {}
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="casepath-run")
        self.store.interrupt_unfinished()

    def start(self, case_id, user, token=None):
        """``token``: the person's own model token, when the model is called as the person who started the run."""
        run = self.store.create_run(case_id, user)
        self._pool.submit(self._execute, run["id"], case_id, token)
        return run

    def recheck(self, case_id, document_ids, user, token=None):
        run = self.store.create_run(case_id, user)
        self._pool.submit(self._recheck, run["id"], case_id, list(document_ids), token)
        return run

    def shutdown(self):
        self._pool.shutdown(wait=False, cancel_futures=True)

    def job(self, case_id):
        """The agent core's job for this case, from the store."""
        return {"format": core.JOB, "case": self.store.get_case(case_id), "files": self.store.list_files(case_id, with_text=True),
                "workflows": list(self.catalogue.workflows), "knowledge": self.store.list_knowledge(None, {"active"}),
                "edits": self.store.list_edits(case_id),
                "options": {"effort": self.effort, "read_scans": self.read_scans, "reading_workers": self.reading_workers,
                            "page_image_side": self.page_image_side, "token_budget": self.token_budget, "voice": self.voice}}

    def _event(self, run_id, data):
        self.store.append_event(run_id, data)

    def _model(self, run_id, token=None):
        # None when no deployment is configured; the core then fails the run with that reason
        model = self.model_factory(token) if token is not None else self.model_factory()
        if model is not None:
            self.store.update_run(run_id, deployment=model.settings.deployment)
        return model

    def _execute(self, run_id, case_id, token=None):
        try:
            self.store.update_run(run_id, status="running")
            outcome = core.prepare(self.job(case_id), self._model(run_id, token), core.StoreBlobs(self.store),
                                   on_event=lambda e: self._event(run_id, e),
                                   on_extraction=lambda file_id, extraction: self.store.update_extraction(file_id, extraction))
            self.save(run_id, case_id, outcome)
        except ModelError as error:
            self.store.update_run(run_id, status="failed", error=f"{error.reason}: {error}", finished_at=now())
        except Exception as error:  # Every failure ends the run with a stated reason.
            self.store.update_run(run_id, status="failed", error=f"internal: {type(error).__name__}: {error}", finished_at=now())

    def save(self, run_id, case_id, outcome):
        """Persist an agent outcome: readings, routing, result, Knowledge statistics and proposals."""
        for file_id, extraction in outcome["extractions"].items():
            self.store.update_extraction(file_id, extraction)
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
        if "recheck_of" not in result:
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
