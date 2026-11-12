"""Export, per file, the bundle a writing session gets and nothing else (SPEC.md step 2c item 3).

Run:  python3 -I -B study4/generator/writer_bundle.py --regime tenancy
Writes study4/dev/<regime>/writer_bundles/<file_id>.json and, for the operator only, writer_bundles/KEYS.json
(label -> fact / document per file; never given to a writer or a blind checker) and MANIFEST.json.

A bundle holds: the designed answers phrased as the condition questions (verbatim questions, neutral labels Q1..Qn
in a per-file shuffled order) with an instruction per answer and each condition's `not_this` line beside its question
(from 2026-11-12, revision 2: a writer who does not see what a question excludes writes wordings that fall under it);
any `generator_note` the rule set attaches to a fact; in a file whose central event is designed "no", the other
types' central-event questions (with their not_this lines), none of which the file may state (STYLE.md, message
item 14); the story seed; the language; the attachments to write with what each must show, must leave out and must
not show; the topic order; the style sheet (STYLE.md, verbatim). It holds no fact or step ids, no rule text beyond the
questions, their not_this lines and the catalogue's titles and must_show items, no passages, no workflow, no
reference, no product code, no prompt of any design, no level.
"""
import argparse
import random
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import genlib as G  # noqa: E402

ANSWER = {"stated_true": "yes", "stated_false": "no", "open": "open", "not_mentioned": "not mentioned"}
INSTRUCTION = {
    "stated_true": "Make it clear, in the claimant's own words, that the answer to this question is yes. A careful "
                   "reader must be able to answer yes without guessing (style sheet, message item 9).",
    "stated_false": "Make it clear that the answer to this question is no: say so once, or tell something that "
                    "unmistakably excludes it (style sheet, message item 8).",
    "open": "Raise this matter and leave it unsettled: the claimant mentions it but does not know, has not decided, "
            "or the parties disagree and nothing settles it. A careful reader must see that the matter is raised and "
            "must not be able to answer yes or no. No attachment may settle it (style sheet, message item 10).",
    "not_mentioned": "Do not touch this topic at all: no sentence, aside or attachment content that would let a "
                     "reader answer this question yes, no or open, and no statement that it is not the case "
                     "(style sheet, message item 7).",
}
DENIED = ("This question's designed answer is \"no\" and it asks about the central event of the claim: the claimant says that "
          "this event did not take place at all. The message and the attachments state none of the events asked about "
          "under `must_not_state` either (not as what happened instead, not as a correction, not as a possibility): the "
          "claim is not \"not this, but that\". What the claimant does write about is free, as long as it is none of "
          "those events (style sheet, message item 14).")
LANG = {"de": "German (Swiss Standard German: write ss, never the sharp s)", "en": "English"}


def labels(design):
    """Per-file neutral labels: questions Q1..Qn in a shuffled order, attachments A1..Am."""
    rng = random.Random(G.sub_seed(design["story"]["topic_order_seed"], "labels"))
    facts = list(design["facts"])
    rng.shuffle(facts)
    q = {f"Q{i + 1}": f for i, f in enumerate(facts)}
    sup = [a for a in design["attachments"] if a["supplied"]]
    att = {f"A{i + 1}": a["document"] for i, a in enumerate(sup)}
    return q, att


def build_one(regime, design, style_text, notes=None, facts=None, rnd=1):
    """`facts` overrides the design's fact states (a rewrite target); `notes` are the item notes; `rnd` the writing
    round the bundle is for (it names the output file)."""
    notes = notes or G.ItemNotes(regime.name)
    if facts is not None:
        design = dict(design, facts=facts)
    tid = design["type"]
    qmap, amap = labels(design)
    inv = {f: lab for lab, f in qmap.items()}
    story = {k: v for k, v in design["story"].items() if k not in ("time_spans", "topic_order_seed")}
    spans = {}
    for s in design["story"].get("time_spans", []):
        spans.setdefault(s["fact"], []).append(s)
    questions = []
    for lab, f in qmap.items():
        st = design["facts"][f]
        fdef = regime.fact(tid, f)
        e = {"label": lab, "question": fdef["question"], "not_this": fdef.get("not_this", ""),
             "designed_answer": ANSWER[st], "instruction": INSTRUCTION[st]}
        if fdef.get("generator_note"):
            e["note"] = fdef["generator_note"]
        if f in spans and st != "not_mentioned":
            e["time_span"] = [{"days": s["days"],
                               "date_if_span_has_run": s["date_if_span_has_run"],
                               "date_if_span_not_run": s["date_if_span_not_run"],
                               "use": ("leave the date that would decide this unclear" if st == "open" else
                                       "use the date that makes the designed answer true")} for s in spans[f]]
        questions.append(e)
    not_touch = [lab for lab, f in qmap.items() if design["facts"][f] == "not_mentioned"]
    open_l = [lab for lab, f in qmap.items() if design["facts"][f] == "open"]
    stated = [lab for lab, f in qmap.items() if design["facts"][f] in ("stated_true", "stated_false")]
    denied = G.denied_event(regime, design)
    attachments = []
    by_doc = {a["document"]: a for a in design["attachments"]}
    for lab, did in amap.items():
        d = regime.doc(tid, did)
        a = by_doc[did]
        states = design["facts"]
        applies = {i: notes.applies(tid, did, i, states) for i in d["must_show"]}
        glosses = [{"item": i, "checkable_as": notes.gloss(tid, did, i)} for i in d["must_show"]
                   if notes.gloss(tid, did, i) and applies[i] is not False]
        missing = regime.current_item(tid, did, a.get("missing"))  # a design may name the item by an earlier wording
        attachments.append({
            "label": lab, "document_title": d["title"],
            "must_show": [i for i in d["must_show"] if applies[i] is True and i != missing],
            "show_only_if_it_applies": [i for i in d["must_show"] if applies[i] is None],
            "does_not_apply_leave_out": [i for i in d["must_show"] if applies[i] is False],
            "checkable_as": glosses,
            "leave_out": missing,
            "must_not_show": ([f"anything that would answer {x}" for x in not_touch] +
                              [f"anything that would settle {x}" for x in open_l] +
                              [f"anything that contradicts the designed answer to {x}" for x in stated] +
                              (["any event asked about under central_event_denied.must_not_state"] if denied else [])),
        })
    # topics: every question that is answered or open, and each attachment; shuffled per file
    topics = [lab for lab in qmap if design["facts"][qmap[lab]] != "not_mentioned"] + \
             [f"mention of attachment {lab}" for lab in amap]
    random.Random(design["story"]["topic_order_seed"]).shuffle(topics)
    bundle = {
        "schema": "study4.writer-bundle/1",
        "file_id": design["file_id"],
        "language": LANG[design["language"]],
        "length_words": design["words"],
        "story": story,
        "questions": questions,
        "topics_in_order": topics,
        "attachments": attachments,
        "output": {"path": f"written/{design['file_id']}.json" if rnd == 1 else f"written/{design['file_id']}.r{rnd}.json",
                   "format": "see WRITER_TASK.md: {file_id, round, language, text, attachments: [{label, text}]}"},
        "style_sheet": style_text,
    }
    if denied:
        bundle["central_event_denied"] = {
            "label": inv[denied], "instruction": DENIED,
            "must_not_state": [{"question": q, "not_this": nt} for _, _, q, nt in G.other_events(regime, design)]}
    return bundle, {"questions": qmap, "attachments": amap}


def build(regime_name, rules_dir=None, out=None, force=False):
    regime = G.Regime(regime_name, rules_dir)
    out = Path(out) if out else G.DEV / regime_name
    designs = [G.read_json(p) for p in sorted((out / "designs").glob("*.json")) if p.name != "MANIFEST.json"]
    style = (G.GEN / "STYLE.md").read_text(encoding="utf-8")
    notes = G.ItemNotes(regime_name)
    b = out / "writer_bundles"
    if (out / "written").exists() and any((out / "written").iterdir()) and not force:
        raise SystemExit(f"{out} already holds written files; refusing to rebuild the bundles they were written "
                         "from (use --force or another --out)")
    if b.exists():
        shutil.rmtree(b)
    b.mkdir(parents=True)
    keys, files = {}, []
    for d in designs:
        bundle, key = build_one(regime, d, style, notes)
        h = G.write_json(b / f"{d['file_id']}.json", bundle)
        keys[d["file_id"]] = key
        files.append({"file_id": d["file_id"], "sha256": h})
    G.write_json(b / "KEYS.json", {"note": "operator only: never give this file to a writer or a blind checker",
                                   "keys": keys})
    G.write_json(b / "MANIFEST.json", {"regime": regime_name, "style_sha256": G.sha256_file(G.GEN / "STYLE.md"),
                                       "writer_task_sha256": G.sha256_file(G.GEN / "WRITER_TASK.md"),
                                       "builder_sha256": G.sha256_file(Path(__file__)), "files": files,
                                       "item_notes_sha256": notes.sha256,
                                       "keys_sha256": G.sha256_file(b / "KEYS.json")})
    return b


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--regime", required=True)
    ap.add_argument("--rules-dir")
    ap.add_argument("--out")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    b = build(a.regime, a.rules_dir, a.out, a.force)
    print(f"writer bundles written to {b}")


if __name__ == "__main__":
    main()
