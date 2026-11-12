"""Export, per file, the bundle a writing session gets and nothing else (SPEC.md step 2c item 3).

Run:  python3 -I -B study4/generator/writer_bundle.py --regime tenancy
Writes study4/dev/<regime>/writer_bundles/<file_id>.json and, for the operator only, writer_bundles/KEYS.json
(label -> fact / document per file; never given to a writer or a blind checker) and MANIFEST.json.

A bundle holds: the designed answers phrased as the condition questions (verbatim questions, neutral labels Q1..Qn
in a per-file shuffled order) with an instruction per answer; any `generator_note` the rule set attaches to a
fact; the story seed; the language; the attachments to write with what each must show, must leave out and must not
show; the topic order; the style sheet (STYLE.md, verbatim). It holds no fact or step ids, no rule text beyond the
questions and the catalogue's titles and must_show items, no not_this lines, no passages, no workflow, no
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


def build_one(regime, design, style_text):
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
        e = {"label": lab, "question": fdef["question"], "designed_answer": ANSWER[st], "instruction": INSTRUCTION[st]}
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
    attachments = []
    by_doc = {a["document"]: a for a in design["attachments"]}
    for lab, did in amap.items():
        d = regime.doc(tid, did)
        a = by_doc[did]
        must = [i for i in d["must_show"] if not G.conditional_item(i)]
        cond = [i for i in d["must_show"] if G.conditional_item(i)]
        attachments.append({
            "label": lab, "document_title": d["title"],
            "must_show": [i for i in must if i != a.get("missing")],
            "show_only_if_it_applies": cond,
            "leave_out": a.get("missing"),
            "must_not_show": ([f"anything that would answer {x}" for x in not_touch] +
                              [f"anything that would settle {x}" for x in open_l] +
                              [f"anything that contradicts the designed answer to {x}" for x in stated]),
        })
    # topics: every question that is answered or open, and each attachment; shuffled per file
    topics = [lab for lab in qmap if design["facts"][qmap[lab]] != "not_mentioned"] + \
             [f"mention of attachment {lab}" for lab in amap]
    random.Random(design["story"]["topic_order_seed"]).shuffle(topics)
    return {
        "schema": "study4.writer-bundle/1",
        "file_id": design["file_id"],
        "language": LANG[design["language"]],
        "length_words": design["words"],
        "story": story,
        "questions": questions,
        "topics_in_order": topics,
        "attachments": attachments,
        "output": {"path": f"written/{design['file_id']}.json",
                   "format": "see WRITER_TASK.md: {file_id, language, text, attachments: [{label, text}]}"},
        "style_sheet": style_text,
    }, {"questions": qmap, "attachments": amap}


def build(regime_name, rules_dir=None, out=None):
    regime = G.Regime(regime_name, rules_dir)
    out = Path(out) if out else G.DEV / regime_name
    designs = [G.read_json(p) for p in sorted((out / "designs").glob("*.json")) if p.name != "MANIFEST.json"]
    style = (G.GEN / "STYLE.md").read_text(encoding="utf-8")
    b = out / "writer_bundles"
    if b.exists():
        shutil.rmtree(b)
    b.mkdir(parents=True)
    keys, files = {}, []
    for d in designs:
        bundle, key = build_one(regime, d, style)
        h = G.write_json(b / f"{d['file_id']}.json", bundle)
        keys[d["file_id"]] = key
        files.append({"file_id": d["file_id"], "sha256": h})
    G.write_json(b / "KEYS.json", {"note": "operator only: never give this file to a writer or a blind checker",
                                   "keys": keys})
    G.write_json(b / "MANIFEST.json", {"regime": regime_name, "style_sha256": G.sha256_file(G.GEN / "STYLE.md"),
                                       "writer_task_sha256": G.sha256_file(G.GEN / "WRITER_TASK.md"),
                                       "builder_sha256": G.sha256_file(Path(__file__)), "files": files,
                                       "keys_sha256": G.sha256_file(b / "KEYS.json")})
    return b


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--regime", required=True)
    ap.add_argument("--rules-dir")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    b = build(a.regime, a.rules_dir, a.out)
    print(f"writer bundles written to {b}")


if __name__ == "__main__":
    main()
