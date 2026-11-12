"""Draw the designed state of development files for one regime (SPEC.md step 2c, items 1, 2 and 6).

Run:  python3 -I -B study4/generator/design.py --regime tenancy [--seed 20261112] [--per-level 15]
Writes study4/dev/<regime>/designs/<file_id>.json, MANIFEST.json and MARGINALS.json (or under --out).

Model-free, network-free, product-free: reads rules.json and the type's workflow presumptions only.
Every parameter is a command-line option; the defaults are explained in README.md.
"""
import argparse
import datetime as dt
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import genlib as G  # noqa: E402
import lexicon as L  # noqa: E402

DEFAULTS = {
    "seed": 20261112,
    "per_level": 15,
    "levels": [0, 10, 25, 50],          # percent of files with at least one open fact
    "open_facts_per_open_file": 1,
    "denied_share": 0.10,               # of every level, defining event stated false, disjoint from open-fact files
    "p_branch_true": 0.35,              # a non-open branch fact (not always_stated) is stated true ...
    "p_branch_false": 0.20,             # ... stated false ...
    "p_branch_not_mentioned": 0.45,     # ... or not mentioned
    "p_always_stated_true": 0.50,       # an always_stated fact: stated true, else stated false
    "stop_lean_factor": 0.25,           # a fact whose one value alone fires a stop: that stated value's weight x this
    "always_stated_where_reachable": True,  # an always_stated fact is stated only where a step using it can be reached
    "denied_branch": "false_or_not_mentioned",  # branch facts in a denied-event file (see README)
    "p_supply": 0.35,                   # a mandatory document needed under the design is supplied
    "p_supply_optional": 0.30,          # an optional document whose need holds under the design is supplied
    "p_sufficient": 0.50,               # a supplied document shows every must_show item (else one is missing)
    "allow_irrelevant_attachments": False,  # only documents the design definitely needs are ever supplied
    "german_share": 0.50,               # exact count per level, round half up
    "noise_share": 0.20,                # exact count per level, round half up
    "words": [150, 400],
}


def iso(d):
    return d.isoformat()


def draw_story(rng, lang, regime, tid, facts_state, constraints=()):
    sex, why = claimant_sex(constraints, facts_state, rng)
    first_c = L.first_names(lang, sex)
    first = L.FIRST_DE if lang == "de" else L.FIRST_EN
    suffix = L.ORG_SUFFIX_DE if lang == "de" else L.ORG_SUFFIX_EN
    city, canton = rng.choice(L.PLACES)
    start = dt.date(2026, 2, 1)
    written = start + dt.timedelta(days=rng.randrange(0, 272))      # 2026-02-01 .. 2026-10-30
    event = written - dt.timedelta(days=rng.randrange(6, 76))
    earlier = sorted(event - dt.timedelta(days=rng.randrange(20, 1500)) for _ in range(3))
    surnames = rng.sample(L.SURNAMES, 3)
    story = {
        "claimant": f"{rng.choice(first_c)} {surnames[0]}",
        "claimant_sex": sex,
        "other_party_person": f"{rng.choice(first)} {surnames[1]}",
        "other_party_organisation": f"{rng.choice(L.ORG_WORDS)} {rng.choice(suffix)}",
        "third_person": f"{rng.choice(first)} {surnames[2]}",
        "place": city, "canton": canton,
        "street": f"{rng.choice(L.STREETS)} {rng.randrange(1, 140)}",
        "date_written": iso(written), "date_main_event": iso(event),
        "earlier_dates": [iso(d) for d in earlier],
        "amounts_chf": {"monthly": rng.randrange(950, 3410, 10), "small": rng.randrange(120, 2405, 5),
                        "large": rng.randrange(2400, 12050, 50)},
        "topic_order_seed": rng.randrange(1, 2 ** 31),
    }
    spans = []
    for f in regime.facts(tid):
        q = regime.fact(tid, f)["question"]
        for days in G.durations(q):
            spans.append({"fact": f, "days": days,
                          "date_if_span_not_run": iso(written - dt.timedelta(days=max(1, round(days * 0.4)))),
                          "date_if_span_has_run": iso(written - dt.timedelta(days=round(days * 1.6) + 1))})
    story["time_spans"] = spans
    return story


FACT_KINDS = (None, "stated_only_if", "stated_if")


def apply_constraints(regime, tid, states, protected, constraints, log, drawn=None, pinned=None):
    """Fact-level dependency rules from the regime's constraints file (see README, "Dependency rules"):
    - (no kind) {"if": cond, "then": {"fact", "in": [...], "set": state}, "reset_if"?}: when `if` holds and the
      `then` fact's state is not in `in`, it is set to `set`; if that fact is protected (defining event, open fact)
      the single `if` fact is reset to `reset_if` (default not_mentioned; stated_false for an always_stated fact);
    - {"kind": "stated_only_if", "fact", "if"}: the fact is not mentioned unless `if` holds;
    - {"kind": "stated_if", "fact", "if", "set": state | "drawn"}: when `if` holds, the fact may not be "not
      mentioned"; it takes its drawn value (if that was a stated one) or `set_default` (default stated_false).
    `cond` is a condition over designed states (genlib.state_match). Facts a rule sets are recorded in `pinned`, so
    that the reachability rule does not undo them."""
    facts = set(regime.facts(tid))
    always = regime.always_stated(tid)
    drawn = drawn or {}
    pinned = pinned if pinned is not None else set()

    def set_state(f, new, c):
        log.append({"constraint": c.get("note", ""), "changed": f, "from": states[f], "to": new})
        states[f] = new
        pinned.add(f)

    for _ in range(20):
        changed = False
        for c in constraints:
            kind = c.get("kind")
            if kind not in FACT_KINDS:
                continue
            ifs = G.state_facts(c["if"])
            if any(x not in facts for x in ifs):
                continue
            if kind == "stated_only_if":
                f = c["fact"]
                if f in facts and f not in protected and states[f] != "not_mentioned" and not G.state_match(c["if"], states):
                    set_state(f, "not_mentioned", c)
                    changed = True
                continue
            if kind == "stated_if":
                f = c["fact"]
                if f in facts and f not in protected and states[f] == "not_mentioned" and G.state_match(c["if"], states):
                    want = c.get("set", "drawn")
                    if want == "drawn":
                        want = drawn.get(f) if drawn.get(f) in ("stated_true", "stated_false") else c.get("set_default", "stated_false")
                    set_state(f, want, c)
                    changed = True
                continue
            b = c["then"]["fact"]
            if b not in facts or not G.state_match(c["if"], states) or states[b] in c["then"]["in"]:
                continue
            if b not in protected:
                new, target = c["then"]["set"], b
            elif len(ifs) == 1 and ifs[0] not in protected:
                new, target = c.get("reset_if", "not_mentioned"), ifs[0]
            else:
                raise SystemExit(f"constraint {c} cannot be met: its facts are protected in {tid}")
            if new == "not_mentioned" and target in always:
                new = "stated_false"
            if new == "open":
                raise SystemExit("a constraint may not set a fact open")
            set_state(target, new, c)
            changed = True
        if not changed:
            return
    raise SystemExit("constraints do not converge")


def apply_attachment_rules(regime, tid, states, protected, constraints, attachments, log, notes, drawn):
    """{"kind": "attachment_implies", "document", "item"?: must_show item (absent: the document itself), "fact",
    "implies": [states], "set": state | "drawn"}: an attachment that is supplied and shows the item answers the
    fact. If the fact's designed state is not in `implies`: a not-protected fact takes `set` (the question takes the
    implied state); a protected fact (open fact, defining event) keeps its state and the attachment is not supplied
    (it would settle or contradict it). Returns the facts changed."""
    facts = set(regime.facts(tid))
    changed = set()
    for c in constraints:
        if c.get("kind") != "attachment_implies" or c["fact"] not in facts:
            continue
        for a in attachments:
            if not a["supplied"] or a["document"] != c["document"]:
                continue
            item = c.get("item")
            if item is not None:
                doc = regime.doc(tid, a["document"])
                if item not in doc["must_show"] or a.get("missing") == item or notes.applies(tid, a["document"], item, states) is False:
                    continue
            f = c["fact"]
            if states[f] in c["implies"]:
                continue
            if f in protected or states[f] not in ("not_mentioned",):
                log.append({"constraint": c.get("note", ""), "attachment_withdrawn": a["document"], "because": f,
                            "state": states[f]})
                a.update(supplied=False, withdrawn=True)
                a.pop("sufficient", None)
                a.pop("missing", None)
                continue
            want = c.get("set", "drawn")
            if want == "drawn":
                want = drawn.get(f) if drawn.get(f) in c["implies"] else c["implies"][0]
            log.append({"constraint": c.get("note", ""), "changed": f, "from": states[f], "to": want,
                        "implied_by": {"document": a["document"], "item": item}})
            states[f] = want
            changed.add(f)
    return changed


def claimant_sex(constraints, states, rng):
    """{"kind": "claimant_sex", "if": cond, "sex": "female" | "male"}: the first matching rule fixes the claimant's
    sex; otherwise it is drawn 50/50. The draw is always made, so later draws do not shift."""
    u = rng.random()
    for c in constraints:
        if c.get("kind") == "claimant_sex" and all(f in states for f in G.state_facts(c["if"])) \
                and G.state_match(c["if"], states):
            return c["sex"], c.get("note", "")
    return ("female" if u < 0.5 else "male"), None


def draw_file(regime, P, rng, role, constraints, notes=None):
    """role: 'open', 'denied' or 'plain'."""
    notes = notes or G.ItemNotes(regime.name)
    tid = rng.choice(regime.type_ids)
    facts = regime.facts(tid)
    ev = regime.defining_event(tid)
    always = regime.always_stated(tid)
    states = {}
    open_fact = rng.choice(facts) if role == "open" else None
    pf = [P["p_branch_true"], P["p_branch_false"], P["p_branch_not_mentioned"]]
    lean = regime.single_fact_stops(tid)
    k = P["stop_lean_factor"]
    for f in facts:
        if f == open_fact:
            states[f] = "open"
        elif f == ev:
            states[f] = "stated_false" if role == "denied" else "stated_true"
        elif role == "denied" and f not in always:
            states[f] = rng.choices(["stated_false", "not_mentioned"], weights=pf[1:])[0]
        elif f in always:
            pt, pfa = P["p_always_stated_true"], 1 - P["p_always_stated_true"]
            if f in lean:
                pt, pfa = (pt * k, pfa) if lean[f] else (pt, pfa * k)
            states[f] = "stated_true" if rng.random() < pt / (pt + pfa) else "stated_false"
        else:
            w = list(pf)
            if f in lean:
                w[0 if lean[f] else 1] *= k
            states[f] = rng.choices(["stated_true", "stated_false", "not_mentioned"], weights=w)[0]
    drawn = dict(states)
    log, pinned = [], set()
    protected = {ev} | ({open_fact} if open_fact else set())
    apply_constraints(regime, tid, states, protected, constraints, log, drawn, pinned)
    # An always_stated fact is stated only in files where a step that uses it can be reached; elsewhere it is not
    # mentioned (it has no presumption, so it is unresolved, and being unreachable it changes nothing). A fact a
    # dependency rule has set (pinned) is left as the rule set it.
    unreachable, open_unreachable = [], False

    def reachability():
        nonlocal open_unreachable
        if not P["always_stated_where_reachable"]:
            return
        for _ in range(10):
            vals = G.resolve(regime, tid, states)
            changed = False
            for f in sorted(always):
                reach = G.fact_step_reachable(regime, tid, vals, f)
                if f in protected:
                    open_unreachable = open_unreachable or (f == open_fact and not reach)
                    continue
                if f in pinned:
                    continue
                want = drawn[f] if reach else "not_mentioned"
                if states[f] != want:
                    states[f], changed = want, True
            if not changed:
                return
        raise SystemExit(f"{tid}: always_stated reachability does not settle")

    reachability()
    apply_constraints(regime, tid, states, protected, constraints, log, drawn, pinned)
    assert sum(s == "open" for s in states.values()) == (1 if role == "open" else 0)

    # attachments: only documents the design definitely needs (or, optional ones, whose need definitely holds)
    vals = G.resolve(regime, tid, states)
    out = G.rules_outcome(regime, tid, vals)
    attachments = []
    for d in regime.documents(tid):
        did = d["id"]
        info = out["documents"][did]
        opt = regime.optional(tid, did)
        eligible = info["always"] if opt else info["state"] == "request"
        if P["allow_irrelevant_attachments"]:
            eligible = True
        rate = P["p_supply_optional"] if opt else P["p_supply"]
        u_supply, u_suff = rng.random(), rng.random()      # always drawn, so later draws do not shift
        supplied = eligible and u_supply < rate
        entry = {"document": did, "supplied": supplied, "optional": opt}
        if supplied:
            # the missing item of an insufficient copy is one that must be shown in this file (never an item that
            # does not apply, nor one left to the story)
            items = notes.required_items(tid, did, d["must_show"], states)
            if u_suff < P["p_sufficient"] or not items:
                entry.update(sufficient=True, missing=None)
            else:
                entry.update(sufficient=False, missing=rng.choice(items))
        attachments.append(entry)
    # attachments that answer a question: the question takes the implied state (or the attachment is withdrawn);
    # then the fact rules once more, and a check that every supplied document is still definitely needed
    hit = apply_attachment_rules(regime, tid, states, protected, constraints, attachments, log, notes, drawn)
    pinned |= hit
    apply_constraints(regime, tid, states, protected, constraints, log, drawn, pinned)
    o2 = G.rules_outcome(regime, tid, G.resolve(regime, tid, states))
    for a in attachments:
        if a["supplied"]:
            info = o2["documents"][a["document"]]
            if not (info["always"] if a["optional"] else info["state"] == "request"):
                log.append({"attachment_withdrawn": a["document"], "because": "no longer definitely needed"})
                a.update(supplied=False, withdrawn=True)
                a.pop("sufficient", None)
                a.pop("missing", None)
            elif a.get("missing") and a["missing"] not in notes.required_items(tid, a["document"],
                                                                              regime.doc(tid, a["document"])["must_show"], states):
                raise SystemExit(f"{tid}: missing item {a['missing']!r} no longer applies")
    if P["always_stated_where_reachable"]:
        unreachable = [{"fact": f, "drawn": drawn[f]} for f in sorted(always) if states[f] == "not_mentioned"]
    assert sum(s == "open" for s in states.values()) == (1 if role == "open" else 0)
    return tid, states, open_fact, log, attachments, unreachable, open_unreachable


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--regime", required=True)
    ap.add_argument("--rules-dir", help="folder holding rules.json and workflow/ (default study4/rules/<regime>)")
    ap.add_argument("--out", help="output folder (default study4/dev/<regime>)")
    ap.add_argument("--constraints", help="constraints JSON (default <out>/constraints.json if present)")
    for k, v in DEFAULTS.items():
        if isinstance(v, bool):
            ap.add_argument("--" + k.replace("_", "-"), type=lambda s: s.lower() in ("1", "true", "yes"), default=v)
        elif isinstance(v, list):
            ap.add_argument("--" + k.replace("_", "-"), type=lambda s: [int(x) for x in s.split(",")], default=v)
        else:
            ap.add_argument("--" + k.replace("_", "-"), type=type(v), default=v)
    ap.add_argument("--items", help="item notes JSON (default generator/items/<regime>.json if present)")
    ap.add_argument("--force", action="store_true", help="redraw even if written files exist in --out")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    P = {k: getattr(a, k) for k in DEFAULTS}
    if abs(P["p_branch_true"] + P["p_branch_false"] + P["p_branch_not_mentioned"] - 1) > 1e-9:
        raise SystemExit("the three branch probabilities must sum to 1")
    if P["open_facts_per_open_file"] != 1:
        raise SystemExit("only one open fact per open-fact file is implemented (SPEC 2c item 2 as instructed)")
    regime = G.Regime(a.regime, a.rules_dir)
    missing_wf = [t for t in regime.type_ids if t not in regime.workflows]
    if missing_wf:
        print(f"warning: no workflow for {missing_wf}; presumptions taken from rules.json only", file=sys.stderr)
    out = Path(a.out) if a.out else G.DEV / a.regime
    cpath = Path(a.constraints) if a.constraints else out / "constraints.json"
    constraints = G.read_json(cpath)["constraints"] if cpath.exists() else []
    notes = G.ItemNotes(a.regime, a.items)
    ddir = out / "designs"
    if (out / "written").exists() and any((out / "written").iterdir()) and not a.force:
        raise SystemExit(f"{out} already holds written files for these designs; refusing to redraw (use --force "
                         "or another --out)")
    ddir.mkdir(parents=True, exist_ok=True)
    for old in ddir.glob("*.json"):
        old.unlink()

    rows = []
    for level in P["levels"]:
        n = P["per_level"]
        n_open = G.level_counts(n, level / 100)
        n_denied = G.level_counts(n, P["denied_share"])
        if n_open + n_denied > n:
            raise SystemExit(f"level {level}: {n_open} open + {n_denied} denied files exceed {n}")
        lrng = random.Random(G.sub_seed(P["seed"], a.regime, "level", level))
        idx = list(range(n))
        lrng.shuffle(idx)
        role = {i: "open" for i in idx[:n_open]}
        role.update({i: "denied" for i in idx[n_open:n_open + n_denied]})
        langs = ["de"] * G.level_counts(n, P["german_share"])
        langs += ["en"] * (n - len(langs))
        lrng.shuffle(langs)
        noise = [True] * G.level_counts(n, P["noise_share"]) + [False] * (n - G.level_counts(n, P["noise_share"]))
        lrng.shuffle(noise)
        for i in range(n):
            r = role.get(i, "plain")
            rng = random.Random(G.sub_seed(P["seed"], a.regime, "file", level, i))
            tid, states, open_fact, log, att, unreach, open_unreach = draw_file(regime, P, rng, r, constraints, notes)
            story = draw_story(rng, langs[i], regime, tid, states, constraints)
            fid = f"{a.regime[:3]}_{G.sub_seed(P['seed'], a.regime, 'id', level, i):016x}"[:16]
            design = {
                "schema": "study4.design/1",
                "file_id": fid, "regime": a.regime, "rules_version": regime.rules.get("version"),
                "rules_sha256": regime.rules_sha256, "seed": P["seed"], "level": level, "index": i,
                "type": tid, "types_drawn_from": regime.type_ids,
                "defining_event": regime.defining_event(tid),
                "facts": {f: states[f] for f in regime.facts(tid)},
                "open_facts": [open_fact] if open_fact else [],
                "denied_event": r == "denied",
                "constraint_adjustments": log,
                "always_stated_not_mentioned": unreach,
                "open_fact_step_unreachable": open_unreach,
                "attachments": att,
                "language": langs[i], "scan_noise": noise[i], "words": P["words"],
                "story": story,
            }
            h = G.write_json(ddir / f"{fid}.json", design)
            rows.append((design, h))

    gen_files = sorted(p.name for p in G.GEN.glob("*.py"))
    manifest = {
        "schema": "study4.design-manifest/1", "regime": a.regime, "seed": P["seed"], "parameters": P,
        "rules_sha256": regime.rules_sha256, "workflow_sha256": regime.workflow_sha256,
        "constraints": {"path": str(cpath.relative_to(G.STUDY4)) if cpath.exists() and cpath.is_relative_to(G.STUDY4)
                        else (str(cpath) if cpath.exists() else None),
                        "sha256": G.sha256_file(cpath) if cpath.exists() else None},
        "generator_sha256": {n: G.sha256_file(G.GEN / n) for n in gen_files},
        "item_notes": {"path": str(notes.path) if notes.path else None, "sha256": notes.sha256},
        "rounding": "per level, round half up: open files = round(n * level), denied = round(n * denied_share)",
        "files": [{"file_id": d["file_id"], "level": d["level"], "index": d["index"], "type": d["type"],
                   "sha256": h} for d, h in rows],
    }
    G.write_json(ddir / "MANIFEST.json", manifest)
    marg = marginals(regime, [d for d, _ in rows])
    G.write_json(out / "MARGINALS_design.json", marg)
    if not a.quiet:
        print_marginals(marg)
    return manifest


def marginals(regime, designs):
    """Counts over the designs; document states and stops from the rules-based evaluation (genlib.rules_outcome)."""
    m = {"files": len(designs), "per_level": Counter(), "types": Counter(), "open_files_per_level": Counter(),
         "denied_per_level": Counter(), "languages": Counter(), "noise": Counter(), "open_fact": Counter(),
         "facts": defaultdict(Counter), "documents": defaultdict(Counter), "stops": Counter(),
         "supplied": Counter(), "constraint_adjustments": len([x for d in designs for x in d["constraint_adjustments"]])}
    for d in designs:
        lv = str(d["level"])
        m["per_level"][lv] += 1
        m["types"][d["type"]] += 1
        m["open_files_per_level"][lv] += bool(d["open_facts"])
        m["denied_per_level"][lv] += d["denied_event"]
        m["languages"][d["language"]] += 1
        m["noise"][str(d["scan_noise"])] += 1
        for f in d["open_facts"]:
            m["open_fact"][f"{d['type']}.{f}"] += 1
        for f, s in d["facts"].items():
            m["facts"][f"{d['type']}.{f}"][s] += 1
        sup = {a["document"]: a["sufficient"] for a in d["attachments"] if a["supplied"]}
        for a in d["attachments"]:
            if a["supplied"]:
                m["supplied"]["sufficient" if a["sufficient"] else "insufficient"] += 1
        o = G.rules_outcome(regime, d["type"], G.resolve(regime, d["type"], d["facts"]), sup)
        if o["stop"]["state"] == "stopped":
            for s in o["stop"]["stops"]:
                m["stops"][f"{d['type']}.{s}"] += 1
        elif o["stop"]["state"] == "pending":
            m["stops"][f"{d['type']}.(pending: " + ",".join(o["stop"]["stops"]) + ")"] += 1
        else:
            m["stops"][f"{d['type']}.(none)"] += 1
        for did, info in o["documents"].items():
            m["documents"][f"{d['type']}.{did}"][info["state"]] += 1
    # every type's stops and documents appear, even at zero
    for tid in regime.type_ids:
        for s in regime.stops(tid):
            m["stops"].setdefault(f"{tid}.{s['id']}", 0)
        for doc in regime.documents(tid):
            m["documents"].setdefault(f"{tid}.{doc['id']}", Counter())
    return json_ready(m)


def json_ready(x):
    if isinstance(x, dict):
        return {k: json_ready(v) for k, v in sorted(x.items())}
    return x


def print_marginals(m):
    print(f"files {m['files']}; per level {dict(m['per_level'])}")
    print(f"types {dict(m['types'])}")
    print(f"open-fact files per level {dict(m['open_files_per_level'])}; denied per level {dict(m['denied_per_level'])}")
    print(f"languages {dict(m['languages'])}; scan noise {dict(m['noise'])}; supplied {dict(m['supplied'])}; "
          f"constraint adjustments {m['constraint_adjustments']}")
    print("fact states (true / false / open / not mentioned):")
    for k, c in m["facts"].items():
        print(f"  {k:55s} {c.get('stated_true', 0):3d} {c.get('stated_false', 0):3d} {c.get('open', 0):3d} "
              f"{c.get('not_mentioned', 0):3d}")
    print("open fact: " + ", ".join(f"{k} {v}" for k, v in m["open_fact"].items()))
    print("stops (rules-based): " + ", ".join(f"{k} {v}" for k, v in m["stops"].items()))
    print("documents (rules-based; " + " / ".join(G.REF_STATES) + "):")
    for k, c in m["documents"].items():
        print(f"  {k:55s} " + " ".join(f"{c.get(s, 0):3d}" for s in G.REF_STATES))


if __name__ == "__main__":
    main()
