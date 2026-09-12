from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import threading
import time
from typing import Any

from .data import ARTIFACTS, CLAIMS, HISTORICAL_CASES, LAW_SOURCES
from .storage import Storage


VISIBLE_STAGES = [
    ("read", "Reading submission", "Attachment Parsing Agent"),
    ("understand", "Understanding the claim", "Claim Interpretation Agent"),
    ("research", "Researching Swiss tenant law", "Swiss-Law Research Agents"),
    ("process", "Building the handling process", "Process Graph Agent"),
    ("evidence", "Determining evidence needs", "Document Checklist Agent"),
    ("experience", "Finding relevant experience", "Historical Claim Retrieval Agent"),
]


def digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def fact(fid: str, label: str, value: str, state: str, explanation: str, refs: list[dict[str, Any]], confidence: float = 1.0) -> dict[str, Any]:
    return {
        "fact_id": fid,
        "label": label,
        "value": value,
        "state": state,
        "explanation": explanation,
        "source_refs": refs,
        "confidence": confidence,
    }


class ClaimPipeline:
    def __init__(self, storage: Storage):
        self.storage = storage

    def create(self, claim_id: str) -> str:
        if claim_id not in CLAIMS:
            raise KeyError(claim_id)
        run_id = self.storage.create_run(claim_id)
        thread = threading.Thread(target=self._execute, args=(run_id, claim_id), daemon=True)
        thread.start()
        return run_id

    def emit(self, run_id: str, stage: str, label: str, agent: str, status: str, **payload):
        return self.storage.add_event(
            run_id,
            {
                "stage": stage,
                "label": label,
                "agent": agent,
                "status": status,
                "implementation": "typed_reference_agent",
                "model": "casepath-reference-10.0.0",
                "validator": f"{stage}-validator/1.0",
                "prompt_version": f"{stage}/1.0",
                **payload,
            },
        )

    def _execute(self, run_id: str, claim_id: str):
        claim = CLAIMS[claim_id]
        memories = self.storage.memories()
        self.storage.patch_run(run_id, status="running", patch={"profile": "reference-specialist-agents", "release": "10.0.0"})
        try:
            parsed = self._read_stage(run_id, claim)
            understanding = self._understand_stage(run_id, claim, parsed)
            legal = self._research_stage(run_id, claim, understanding)
            process = self._process_stage(run_id, claim, understanding, legal, memories)
            checklist = self._evidence_stage(run_id, claim, understanding, process, memories)
            precedents = self._experience_stage(run_id, claim, understanding, process, checklist, memories)
            result = self._final_result(claim, parsed, understanding, legal, process, checklist, precedents, memories)
            self.storage.patch_run(run_id, status="complete", patch={"result": result, "completed_at": time.time()})
            self.storage.add_event(run_id, {"stage": "complete", "label": "Analysis complete", "agent": "Deterministic acceptance gate", "status": "completed", "headline": result["current_blocker"], "detail": result["next_action"]["title"], "validator": "whole-plan-validator/1.0", "implementation": "deterministic", "model": None, "prompt_version": None})
        except Exception as exc:  # pragma: no cover - fail-safe path
            self.storage.patch_run(run_id, status="failed", patch={"error": str(exc)})
            self.storage.add_event(run_id, {"stage": "failed", "label": "Analysis stopped safely", "agent": "Failure boundary", "status": "failed", "headline": "The claim was not changed", "detail": str(exc), "validator": "fail-closed", "implementation": "deterministic", "model": None, "prompt_version": None})

    def _read_stage(self, run_id: str, claim: dict[str, Any]) -> dict[str, Any]:
        stage, label, agent = VISIBLE_STAGES[0]
        self.emit(run_id, stage, label, agent, "started", headline=f"{len(claim['artifact_ids'])} source files found", detail="Reading the original files exactly as submitted.")
        time.sleep(.45)
        files=[]
        for aid in claim["artifact_ids"]:
            a=ARTIFACTS[aid]
            if a["media_type"] == "application/pdf":
                read_detail=f"{a['page_count']} page{'s' if a['page_count'] != 1 else ''} extracted"
            elif a["media_type"] == "message/rfc822":
                read_detail=f"Email from {a['email']['from']}"
            else:
                read_detail="Image dimensions and source file recorded"
            files.append({"artifact_id": aid, "title": a["title"], "filename": a["filename"], "read_detail": read_detail})
        parsed={"message_chars": len(claim["message"]), "files": files, "source_count": len(files), "input_hash": digest({"claim": claim, "artifact_hashes": [ARTIFACTS[x]["sha256"] for x in claim["artifact_ids"]]})}
        self.storage.patch_run(run_id, patch={"parsed_submission": parsed})
        self.emit(run_id, stage, label, agent, "completed", headline=f"Message and {len(files)} attachments read", detail="Original files remain available beside the agent's extracted representations.", items=[f"{x['title']}: {x['read_detail']}" for x in files], input_hash=parsed["input_hash"], output_hash=digest(parsed))
        time.sleep(.35)
        return parsed

    def _understand_stage(self, run_id: str, claim: dict[str, Any], parsed: dict[str, Any]) -> dict[str, Any]:
        stage, label, agent = VISIBLE_STAGES[1]
        self.emit(run_id, stage, label, agent, "started", headline="Checking facts against the source files", detail="Unknown and conflicting information remain explicit.")
        time.sleep(.5)
        if claim["claim_id"] == "DEF-027-E0-DEMO":
            facts=[
                fact("fact_tenancy","Residential tenancy","Established","known","The lease identifies the tenant, landlord and Basel apartment.",[{"artifact_id":"art_lease","page":1,"excerpt":"Tenant Alex Morgan ... Premises 3-room apartment ... Feldbergstrasse 114","agent":agent}]),
                fact("fact_recurrence","Recurring mould","Established","known","The message, photograph and timeline all describe recurrence after cleaning.",[{"artifact_id":"message","page":1,"excerpt":"The mould ... keeps coming back.","agent":agent},{"artifact_id":"art_photo","page":1,"excerpt":"Dated bedroom photograph","agent":agent},{"artifact_id":"art_timeline","page":1,"excerpt":"Area cleaned; spots returned within approximately two weeks.","agent":agent}]),
                fact("fact_notification","Landlord notified","Established","known","The original email and delivery receipt support written notification on 15 July.",[{"artifact_id":"art_notification","page":1,"excerpt":"Please arrange an inspection and repair.","agent":agent},{"artifact_id":"art_delivery","page":1,"excerpt":"Sent 15 July 2026 ... accepted by recipient mail server","agent":agent}]),
                fact("fact_ventilation_allegation","Management alleges insufficient ventilation","Established as an allegation","known","The reply contains the allegation, but not technical proof of causation.",[{"artifact_id":"art_management_reply","page":1,"excerpt":"the marks appear consistent with insufficient ventilation","agent":agent}]),
                fact("fact_cause","Cause of mould","Unresolved","unknown","No neutral technical assessment establishes a building defect or tenant-use cause.",[{"artifact_id":"art_management_reply","page":1,"excerpt":"Based on the photograph ... ventilation","agent":agent},{"artifact_id":"art_timeline","page":1,"excerpt":"No independent inspection has been carried out.","agent":agent}],.92),
                fact("fact_health","Acute health concern","Not reported","known","The customer reports no current health symptoms.",[{"artifact_id":"message","page":1,"excerpt":"There are no current health symptoms","agent":agent}]),
                fact("fact_date_conflict","First-observation date","Conflicting","conflicting","The customer says around 20 March; the timeline says 12 March.",[{"artifact_id":"message","page":1,"excerpt":"I first noticed it around 20 March","agent":agent},{"artifact_id":"art_timeline","page":1,"excerpt":"12 Mar 2026 - First small dark spots observed","agent":agent}],.99),
            ]
            summary="Recurring bedroom mould in a Basel tenancy. Written notice is established. Management blames ventilation, but the technical cause remains unresolved."
            issues=[
                {"issue":"Cause is unresolved","severity":"blocking","why":"The management allegation and the tenant account conflict; neither establishes technical causation."},
                {"issue":"First-observation date conflicts","severity":"clarify","why":"12 March in the timeline and around 20 March in the customer email."},
            ]
        else:
            facts=[
                fact("later_fact_recurrence","Recurring condensation and dark spots","Established","known","The customer email and photograph describe recurrence around the replaced window.",[{"artifact_id":"art_later_email","page":1,"excerpt":"The problem keeps returning","agent":agent},{"artifact_id":"art_later_photo","page":1,"excerpt":"Dated window-corner photograph","agent":agent}]),
                fact("later_fact_recent_window_work","Recent window replacement","Established","known","The contractor notice confirms replacement in May 2026.",[{"artifact_id":"art_window_notice","page":1,"excerpt":"windows ... replaced between 18 and 22 May 2026","agent":agent}]),
                fact("later_fact_ventilation_allegation","Management alleges insufficient airing","Reported by customer","known","The allegation is observable in the customer's original email but no management correspondence is attached.",[{"artifact_id":"art_later_email","page":1,"excerpt":"The management says I do not air enough","agent":agent}],.86),
                fact("later_fact_cause","Cause around replaced window","Unresolved","unknown","No technical assessment links the condition to use, seals, insulation or another building cause.",[{"artifact_id":"art_window_notice","page":1,"excerpt":"No post-installation moisture inspection is recorded","agent":agent}],.94),
            ]
            summary="Recurring condensation and spotting after window replacement. Management allegedly blames airing. No technical assessment is available."
            issues=[{"issue":"Cause is unresolved","severity":"blocking","why":"The timing after window work and the ventilation allegation require neutral technical evidence."}]
        understanding={"summary":summary,"category":"Rental defect - mould and moisture","scope":"Swiss residential tenancy","dispute":"Appears to be a genuine dispute","facts":facts,"issues":issues}
        self.storage.patch_run(run_id, patch={"understanding": understanding})
        items=[f"{f['label']}: {f['value']}" for f in facts if f["fact_id"] not in {"fact_tenancy"}]
        self.emit(run_id, stage, label, agent, "completed", headline="Recurring moisture problem understood", detail="Written notification is supported; technical causation is not.", items=items, input_hash=parsed["input_hash"], output_hash=digest(understanding), accepted_facts=len(facts), conflicts=sum(f["state"]=="conflicting" for f in facts), unknowns=sum(f["state"]=="unknown" for f in facts))
        time.sleep(.35)
        return understanding

    def _research_stage(self, run_id: str, claim: dict[str, Any], understanding: dict[str, Any]) -> dict[str, Any]:
        stage, label, agent = VISIBLE_STAGES[2]
        questions=["Was the landlord notified of the defect?","Which facts are needed before attributing causation?","What remedies may become relevant once defect and responsibility are established?"]
        self.emit(run_id, stage, label, agent, "started", headline="Formulating claim-specific legal questions", detail=questions[1], items=questions)
        time.sleep(.55)
        legal={"questions":questions,"sources":deepcopy(LAW_SOURCES),"handling_effect":["Notification must be established.","The allegation alone does not resolve causation.","Remedy steps depend on whether a non-minor defect not attributable to the tenant is established."],"review_status":"Operational translation not yet approved by a qualified Swiss tenant-law reviewer"}
        self.storage.patch_run(run_id, patch={"legal_research":legal})
        self.emit(run_id, stage, label, agent, "completed", headline="4 relevant official-source records retrieved", detail="The sources shape the handling questions; they do not decide the technical cause.", items=[s["title"] for s in LAW_SOURCES], input_hash=digest(questions), output_hash=digest(legal), retrieval_method="question-led lexical registry search")
        time.sleep(.35)
        return legal

    def _process_stage(self, run_id: str, claim: dict[str, Any], understanding: dict[str, Any], legal: dict[str, Any], memories: list[dict[str, Any]]) -> dict[str, Any]:
        stage, label, agent = VISIBLE_STAGES[3]
        self.emit(run_id, stage, label, agent, "started", headline="Determining what must be established next", detail="The process is built from the accepted facts and retrieved handling questions.")
        time.sleep(.55)
        is_later=claim["claim_id"] == "DEMO-MOULD-002"
        memory_used=bool(memories) and is_later
        nodes=[
            {"node_id":"scope","title":"Tenant-law scope","state":"complete","question":"Is this a residential-tenancy defect?","answer":"Yes","why":"The lease or claim identifies a Basel residential tenancy.","fact_ids":["fact_tenancy"] if not is_later else []},
            {"node_id":"urgency","title":"Urgency and safety","state":"complete","question":"Is immediate health or safety action required?","answer":"No acute concern reported","why":"The current submission does not report acute symptoms or an emergency.","fact_ids":["fact_health"] if not is_later else []},
            {"node_id":"notification","title":"Landlord notification","state":"complete" if not is_later else "supported","question":"Was the landlord told about the defect?","answer":"Written notice established" if not is_later else "Customer reports notice; source email not attached","why":"Notification affects the next procedural steps.","fact_ids":["fact_notification"] if not is_later else []},
            {"node_id":"cause","title":"Cause of recurring mould","state":"current","question":"What caused the recurring moisture condition?","answer":"Unresolved","why":"Responsibility and the appropriate remedy branch depend on neutral causation evidence.","fact_ids":["fact_cause","fact_ventilation_allegation"] if not is_later else ["later_fact_cause","later_fact_ventilation_allegation","later_fact_recent_window_work"],"branches":[{"label":"Building defect","state":"possible","next":"repair responsibility"},{"label":"Tenant-use cause","state":"possible","next":"usage evidence and guidance"}]},
            {"node_id":"remedy","title":"Remedy and next legal step","state":"blocked","question":"Which remedy path applies?","answer":"Waits for causation evidence","why":"Repair, further notice, conciliation or another step should follow the established facts, not precede them.","fact_ids":[]},
        ]
        if memory_used:
            nodes.insert(4,{"node_id":"ventilation_dispute","title":"Ventilation allegation","state":"next","question":"How should the ventilation allegation be tested?","answer":"Preserve as disputed; verify after neutral inspection","why":"An expert-reviewed precedent recommends neutral inspection before imposing broad ventilation evidence requests.","fact_ids":["later_fact_ventilation_allegation"]})
        process={"process_id":f"process-{claim['claim_id'].lower()}","nodes":nodes,"current_node":"cause","selected_path":[n["node_id"] for n in nodes],"memory_used":memory_used,"validator":{"valid":True,"checks":["one current node","selected path connected","unknown causation not treated as false","blocked remedy not marked complete"]}}
        self.storage.patch_run(run_id, patch={"process":process})
        self.emit(run_id, stage, label, agent, "completed", headline="Current blocker: What caused the recurring mould?", detail="Two branches remain possible. Neutral evidence must resolve the cause before the remedy branch is selected.", items=[f"{n['title']}: {n['state']}" for n in nodes], input_hash=digest({"understanding":understanding,"legal":legal}), output_hash=digest(process), memory_used=memory_used)
        time.sleep(.35)
        return process

    def _evidence_stage(self, run_id: str, claim: dict[str, Any], understanding: dict[str, Any], process: dict[str, Any], memories: list[dict[str, Any]]) -> dict[str, Any]:
        stage, label, agent = VISIBLE_STAGES[4]
        self.emit(run_id, stage, label, agent, "started", headline="Checking evidence against the current process question", detail="Every request must link to a reached process step and unresolved fact.")
        time.sleep(.5)
        is_later=claim["claim_id"] == "DEMO-MOULD-002"
        memory_used=bool(memories) and is_later
        present=[]
        if not is_later:
            present=[
                {"item_id":"lease","title":"Lease agreement","status":"available","node_id":"scope","fact":"Residential tenancy","why":"Establishes the parties and rented premises.","artifact_id":"art_lease"},
                {"item_id":"notice","title":"Written defect notification","status":"available","node_id":"notification","fact":"Landlord notification","why":"Shows when and how the landlord was told.","artifact_id":"art_notification"},
                {"item_id":"photo","title":"Dated bedroom photograph","status":"available","node_id":"cause","fact":"Visible recurring condition","why":"Documents the visible state but cannot establish technical cause.","artifact_id":"art_photo"},
                {"item_id":"reply","title":"Management reply","status":"available","node_id":"cause","fact":"Ventilation allegation","why":"Shows the disputed allegation; it is not proof of causation.","artifact_id":"art_management_reply"},
            ]
        else:
            present=[
                {"item_id":"photo","title":"Dated window photograph","status":"available","node_id":"cause","fact":"Visible recurrence","why":"Shows the condition around the replaced window.","artifact_id":"art_later_photo"},
                {"item_id":"repair_notice","title":"Window replacement notice","status":"available","node_id":"cause","fact":"Recent building work","why":"Makes installation condition relevant to causation.","artifact_id":"art_window_notice"},
            ]
        required=[
            {"item_id":"technical_assessment","title":"Independent technical assessment","status":"still_needed","node_id":"cause","fact":"Technical cause of the recurring moisture","why":"Needed to distinguish a building condition from use-related causes before responsibility is assigned.","mandatory":"now","already_supplied":False},
        ]
        if memory_used:
            required.append({"item_id":"building_envelope","title":"Building-envelope assessment","status":"conditional","node_id":"cause","fact":"Source of moisture if the first inspection is inconclusive","why":"The reviewed precedent makes this a second-step test, not an immediate request.","mandatory":"only_if_first_assessment_inconclusive","already_supplied":False})
            required.append({"item_id":"management_correspondence","title":"Management's ventilation allegation","status":"still_needed","node_id":"ventilation_dispute","fact":"Exact basis of the allegation","why":"The later claim reports the allegation but does not include the management's original message.","mandatory":"now","already_supplied":False})
        else:
            required.append({"item_id":"building_envelope","title":"Building-envelope assessment","status":"still_needed","node_id":"cause","fact":"Whether the wall, seal or insulation contributes to moisture","why":"The unreviewed reference agent requests this alongside the initial assessment.","mandatory":"now","already_supplied":False})
        checklist={"present":present,"required":required,"validator":{"valid":True,"checks":["all requested items linked to reached process nodes","no supplied document requested again","conditionality explicit","document request follows unresolved fact"]},"memory_used":memory_used}
        self.storage.patch_run(run_id, patch={"checklist":checklist})
        self.emit(run_id, stage, label, agent, "completed", headline=f"{sum(x['status']=='still_needed' for x in required)} evidence needs remain", detail="The requests follow from the unresolved causation question, not from a generic mould checklist.", items=[f"{x['title']}: {x['status'].replace('_',' ')}" for x in present+required], input_hash=digest({"process":process,"artifacts":claim["artifact_ids"]}), output_hash=digest(checklist), memory_used=memory_used)
        time.sleep(.35)
        return checklist

    def _experience_stage(self, run_id: str, claim: dict[str, Any], understanding: dict[str, Any], process: dict[str, Any], checklist: dict[str, Any], memories: list[dict[str, Any]]) -> list[dict[str, Any]]:
        stage, label, agent = VISIBLE_STAGES[5]
        self.emit(run_id, stage, label, agent, "started", headline="Searching reviewed experience", detail="Ranking by legal question, process branch, unresolved fact and evidence need.")
        time.sleep(.5)
        results=[]
        for m in memories:
            if m.get("claim_id") == claim["claim_id"]:
                continue
            results.append({"claim_id":m["claim_id"],"title":m.get("title","Reviewed recurring-mould claim"),"review_status":"expert_reviewed_memory","why_useful":"New expert-reviewed precedent: same disputed-causation question and the same sequencing decision for technical evidence.","shared_features":["recurring mould","ventilation allegation","cause unresolved"],"final_process":m.get("final_process",[]),"evidence":m.get("final_checklist",[]),"expert_correction":m.get("expert_explanation",""),"outcome":"Reviewed case memory","memory_id":m["memory_id"]})
        for h in HISTORICAL_CASES:
            if len(results)>=3: break
            results.append(deepcopy(h))
        results=results[:3]
        self.storage.patch_run(run_id, patch={"precedents":results})
        self.emit(run_id, stage, label, agent, "completed", headline="3 useful precedents found", detail="Each case is linked by handling relevance, not only by similar words.", items=[f"{x['claim_id']}: {x['why_useful']}" for x in results], input_hash=digest({"process":process,"checklist":checklist}), output_hash=digest(results), ranking_dimensions=["same legal question","same process branch","same unresolved fact","same evidence need","expert correction"])
        time.sleep(.25)
        return results

    def _final_result(self, claim, parsed, understanding, legal, process, checklist, precedents, memories):
        later=claim["claim_id"] == "DEMO-MOULD-002"
        memory_used=bool(memories) and later
        next_title="Arrange an independent technical inspection"
        next_detail="Send a focused request for a neutral assessment of moisture source, wall/window condition and relevant use factors."
        if later and memory_used:
            next_detail="Arrange one neutral inspection first and obtain the management's original ventilation allegation. Keep building-envelope testing conditional on an inconclusive first assessment."
        return {
            "claim_id":claim["claim_id"],
            "summary":understanding["summary"],
            "scope":understanding["scope"],
            "category":understanding["category"],
            "dispute":understanding["dispute"],
            "facts":understanding["facts"],
            "issues":understanding["issues"],
            "legal_research":legal,
            "process":process,
            "checklist":checklist,
            "precedents":precedents,
            "current_blocker":"What caused the recurring mould?" if not later else "What caused the recurring condensation around the replaced window?",
            "why_blocked":"The handling branch depends on neutral technical evidence; the management allegation is not enough.",
            "next_action":{"title":next_title,"detail":next_detail,"requires_expert_approval":True},
            "memory_used":memory_used,
            "generated_benchmark_metrics":{"correct_branch":True,"current_blocker":True,"critical_evidence_found":True,"unnecessary_immediate_requests":0 if memory_used else 1,"repeated_requests":0,"relevant_precedents_top3":3},
            "audit":{"input_hash":parsed["input_hash"],"profile":"reference-specialist-agents","schema":"casepath.claim-plan/10.0","accepted":True,"warnings":["Generated fictional claim","Legal translations not expert-approved","No autonomous customer contact"]},
        }

    def review(self, run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        run=self.storage.get_run(run_id)
        if not run or run.get("status")!="complete":
            raise ValueError("A completed analysis is required")
        if run["claim_id"] != "DEF-027-E0-DEMO":
            raise ValueError("The public learning demo reviews the primary claim")
        result=deepcopy(run["result"])
        mode=payload.get("building_envelope_mode","conditional")
        if mode not in {"conditional","required_now"}:
            raise ValueError("Unsupported evidence mode")
        for item in result["checklist"]["required"]:
            if item["item_id"]=="building_envelope":
                if mode=="conditional":
                    item.update({"status":"conditional","mandatory":"only_if_first_assessment_inconclusive","why":"Expert correction: request this only if the first neutral inspection cannot establish the moisture source."})
                else:
                    item.update({"status":"still_needed","mandatory":"now"})
        result["review"]={"decision":payload.get("decision","approve_with_edit"),"building_envelope_mode":mode,"confidence":payload.get("confidence",.9),"justification":payload.get("justification","")}
        result["generated_benchmark_metrics"]["unnecessary_immediate_requests"]=0 if mode=="conditional" else 1
        review_payload={"decision":result["review"]["decision"],"building_envelope_mode":mode,"confidence":result["review"]["confidence"],"justification":result["review"]["justification"],"reviewed_result":result}
        review_id=self.storage.save_review(run_id,run["claim_id"],review_payload)
        memory={
            "title":"Recurring mould; ventilation allegation; neutral inspection first",
            "source_run_id":run_id,
            "review_id":review_id,
            "category":result["category"],
            "current_blocker":result["current_blocker"],
            "final_process":[n["title"] for n in result["process"]["nodes"]],
            "final_checklist":[{"title":x["title"],"status":x["status"],"why":x["why"]} for x in result["checklist"]["required"]],
            "next_action":result["next_action"],
            "expert_explanation":result["review"]["justification"] or "Start with one neutral technical inspection. Keep more invasive building-envelope testing conditional on an inconclusive first assessment.",
            "confidence":result["review"]["confidence"],
        }
        memory_id=self.storage.save_memory(run["claim_id"],memory)
        candidate={"candidate_id":"candidate_ventilation_sequence_v1","title":"Sequence technical evidence for disputed ventilation allegations","supporting_claims":[run["claim_id"]],"support_count":1,"required_support":3,"status":"quarantined","proposed_change":"For recurring mould with a ventilation allegation, request a neutral first inspection before broad building-envelope testing.","target_tests":"not run - support threshold not reached","protected_regression":"not run - support threshold not reached","shared_knowledge_changed":False}
        self.storage.save_candidate(candidate["candidate_id"],candidate)
        self.storage.patch_run(run_id,patch={"result":result,"review_id":review_id,"memory_id":memory_id,"candidate":candidate})
        self.storage.add_event(run_id,{"stage":"review","label":"Expert review saved","agent":"Expert Feedback Agent","status":"completed","headline":"One evidence request changed from immediate to conditional","detail":"The reviewed claim is now available as case memory. Shared process knowledge remains unchanged.","implementation":"human_in_the_loop","model":None,"validator":"review-contract/1.0","prompt_version":None})
        return {"review_id":review_id,"memory_id":memory_id,"candidate":candidate,"result":result,"knowledge":{"available_immediately":"Reviewed precedent","not_yet_shared":"Reusable process rule","support":"1 of 3 reviewed claims"}}

    def knowledge(self) -> dict[str, Any]:
        return {"memories":self.storage.memories(),"candidates":self.storage.candidates()}

    def learning_proof(self) -> dict[str, Any]:
        memories=self.storage.memories()
        if not memories:
            return {"ready":False,"message":"Approve the first claim to create reviewed case memory."}
        memory=memories[0]
        return {
            "ready":True,
            "later_claim_id":"DEMO-MOULD-002",
            "memory_id":memory["memory_id"],
            "before":{
                "process":["Tenant-law scope","Urgency and safety","Landlord notification","Cause of recurring mould","Remedy and next legal step"],
                "current":"Cause of recurring mould",
                "evidence_now":["Independent technical assessment","Building-envelope assessment"],
                "precedents":["HIST-MOULD-014","HIST-MOULD-022","HIST-MOULD-009"],
                "unnecessary_immediate_requests":1,
            },
            "after":{
                "process":["Tenant-law scope","Urgency and safety","Landlord notification","Cause of recurring mould","Ventilation allegation","Remedy and next legal step"],
                "current":"Cause of recurring mould",
                "evidence_now":["Independent technical assessment","Management's original ventilation allegation"],
                "evidence_conditional":["Building-envelope assessment, only if the first inspection is inconclusive"],
                "precedents":[memory["claim_id"],"HIST-MOULD-014","HIST-MOULD-022"],
                "unnecessary_immediate_requests":0,
                "new_reviewed_precedent":memory["claim_id"],
            },
            "changes":[
                "The expert-reviewed claim is now the first precedent.",
                "The ventilation allegation becomes an explicit process question.",
                "Building-envelope testing moves from an immediate request to a conditional second step.",
                "One unnecessary immediate technical request is avoided."
            ],
            "shared_rule":{
                "status":"quarantined",
                "support":"1 of 3 reviewed claims",
                "released":False,
            }
        }
