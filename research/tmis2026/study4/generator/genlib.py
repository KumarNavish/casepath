"""Shared, model-free helpers of the Study 4 file generator (SPEC.md, step 2c).

Everything regime-specific is read from `rules/<regime>/rules.json` and
`rules/<regime>/workflow/<type>.json`; nothing here names a fact, a document or
a type. Standard library only. No network, no model calls, no product code
(the product's evaluator is loaded only by reference.py).
"""
import hashlib
import itertools
import json
import re
from pathlib import Path

GEN = Path(__file__).resolve().parent
STUDY4 = GEN.parent
RULES = STUDY4 / "rules"
DEV = STUDY4 / "dev"

STATES = ("stated_true", "stated_false", "open", "not_mentioned")
REF_STATES = ("request", "hold", "not_needed", "present_sufficient", "present_insufficient")

# Keys and words that belong to the rule machinery and must never reach a writer or a blind checker.
MACHINERY_KEYS = ("needed_when", "reached_when", "required_when", "applies_when", "presumption", "source_ref",
                  "source_id", "locator", "passage", "basis", "inference", "workflow", "casepath", "defining_event",
                  "always_stated", "reference", "hold", "not_needed", "present_sufficient", "present_insufficient")


# ----------------------------------------------------------------- hashing and canonical JSON
def canon(obj):
    """Canonical JSON text (sorted keys, two-space indent, UTF-8, trailing newline)."""
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(path):
    return sha256_bytes(Path(path).read_bytes())


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canon(obj), encoding="utf-8")
    return sha256_file(path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sub_seed(*parts):
    """A deterministic integer seed from any parts (independent of PYTHONHASHSEED)."""
    h = hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()
    return int(h[:16], 16)


# ----------------------------------------------------------------- conditions (casepath.workflow/1 language)
def cond_eval(c, values):
    """Three-valued evaluation over a dict fact -> True/False/None. Same semantics as the workflow format."""
    if c is True:
        return True
    if "all" in c:
        vs = [cond_eval(x, values) for x in c["all"]]
        return False if False in vs else None if None in vs else True
    if "any" in c:
        vs = [cond_eval(x, values) for x in c["any"]]
        return True if True in vs else None if None in vs else False
    if "not" in c:
        v = cond_eval(c["not"], values)
        return None if v is None else not v
    fact = c.get("fact")
    if "known" in c:
        return (values.get(fact) is not None) == bool(c["known"])
    v = values.get(fact)
    if v is None:
        return None
    if "is" in c:
        return v == c["is"]
    if "in" in c:
        return v in c["in"]
    raise ValueError(f"unsupported condition {c!r}")


def cond_facts(c):
    if c is True or c is None:
        return set()
    out = set()
    for k in ("all", "any"):
        for x in c.get(k, ()):
            out |= cond_facts(x)
    if "not" in c:
        out |= cond_facts(c["not"])
    if "fact" in c:
        out.add(c["fact"])
    return out


# ----------------------------------------------------------------- regime loading
class Regime:
    """A regime as the generator sees it: rules.json plus each type's workflow presumptions."""

    def __init__(self, name, rules_dir=None):
        self.name = name
        self.dir = Path(rules_dir) if rules_dir else RULES / name
        self.rules_path = self.dir / "rules.json"
        self.rules = read_json(self.rules_path)
        self.rules_sha256 = sha256_file(self.rules_path)
        self.types = {t["id"]: t for t in self.rules["types"]}
        self.type_ids = [t["id"] for t in self.rules["types"]]
        self.workflows, self.workflow_sha256 = {}, {}
        for tid in self.type_ids:
            p = self.dir / "workflow" / f"{tid}.json"
            if p.exists():
                self.workflows[tid] = read_json(p)
                self.workflow_sha256[tid] = sha256_file(p)

    # facts ------------------------------------------------------------------------------------
    def facts(self, tid):
        return [f["id"] for f in self.types[tid]["facts"]]

    def fact(self, tid, fid):
        return next(f for f in self.types[tid]["facts"] if f["id"] == fid)

    def defining_event(self, tid):
        return self.types[tid]["defining_event"]

    def always_stated(self, tid):
        return {f["id"] for f in self.types[tid]["facts"] if f.get("always_stated")}

    def presumptions(self, tid):
        """Fact -> value an unmentioned fact takes. Read from the type's workflow (`applies: unstated`), which
        encodes the statutory presumptions and the intake convention (SPEC 6a); falls back to the statutory
        presumptions of rules.json when no workflow exists."""
        out = {}
        wf = self.workflows.get(tid)
        if wf is not None:
            for p in wf.get("presumptions", []):
                if p.get("applies") == "unstated":
                    out[p["fact"]] = p["value"]
        else:
            for p in self.types[tid].get("presumptions", []):
                out[p["fact"]] = p["value"]
        return out

    def routing_fact(self, tid):
        """The fact the workflow routes on (its `applies_when`), with the value for this type."""
        wf = self.workflows.get(tid)
        aw = (wf or {}).get("applies_when") or {}
        return (aw.get("fact"), aw.get("is")) if "fact" in aw else (None, None)

    # documents --------------------------------------------------------------------------------
    def documents(self, tid):
        return self.types[tid]["documents"]

    def doc(self, tid, did):
        return next(d for d in self.types[tid]["documents"] if d["id"] == did)

    def optional(self, tid, did):
        """A document the rule set marks not mandatory (`mandatory: false`, workflow `optional: true`): not needed
        unless the file contains it, then assessed; never a gap (theft's `reading_of_optional`)."""
        d = self.doc(tid, did)
        if d.get("mandatory") is False:
            return True
        wf = self.workflows.get(tid)
        if wf:
            w = next((x for x in wf["documents"] if x["id"] == did), {})
            return bool(w.get("optional") or w.get("suggested"))
        return False

    def stops(self, tid):
        out = []
        for i, s in enumerate(self.types[tid]["stops"]):
            out.append({"id": s.get("id") or f"stop_{i + 1}", "when": s["when"]})
        return out

    def single_fact_stops(self, tid):
        """Fact -> value such that some stop fires on that one fact's value (with the defining event true):
        the stop's condition has exactly one leaf besides the defining event, outside any `not`."""
        ev = self.defining_event(tid)
        out = {}
        for s in self.types[tid]["stops"]:
            plain, negated = _leaves(s["when"])
            rest = [c for c in plain if c.get("fact") != ev]
            if len(rest) == 1 and not negated and "is" in rest[0]:
                out[rest[0]["fact"]] = rest[0]["is"]
        return out

    def catalogue(self):
        """Every document id in the regime with its title (first type that lists it)."""
        cat = {}
        for t in self.rules["types"]:
            for d in t["documents"]:
                cat.setdefault(d["id"], d["title"])
        return cat


def _leaves(c, neg=False):
    """(leaves outside a `not`, leaves inside one) of a condition."""
    if not isinstance(c, dict):
        return [], []
    if "all" in c or "any" in c:
        a, b = [], []
        for x in c.get("all", []) + c.get("any", []):
            p, q = _leaves(x, neg)
            a += p
            b += q
        return a, b
    if "not" in c:
        p, q = _leaves(c["not"], not neg)
        return p, q
    return ([], [c]) if neg else ([c], [])


# ----------------------------------------------------------------- rules-based evaluation (model-free, product-free)
def resolve(regime, tid, fact_states):
    """Designed states -> values the rules work with under the intake convention: stated -> its value; not
    mentioned -> the workflow's presumption, or unresolved (None) where there is none; open -> unresolved."""
    pres = regime.presumptions(tid)
    vals = {}
    for f in regime.facts(tid):
        s = fact_states[f]
        if s == "stated_true":
            vals[f] = True
        elif s == "stated_false":
            vals[f] = False
        elif s == "not_mentioned":
            vals[f] = pres.get(f)
        else:
            vals[f] = None
    return vals


def rules_outcome(regime, tid, values, supplied=None):
    """Exact deferral over rules.json: walk every completion of the unresolved facts that any condition uses.
    Returns per document a state in REF_STATES (with `waits_for`), and the stop status.

    `supplied` maps document id -> True (sufficient) / False (insufficient). Mapping (same as the product's
    evaluator and the earlier study's scorer): needed + not supplied -> request; needed + insufficient ->
    present_insufficient (requested again); needed + sufficient -> present_sufficient; needed under some
    completions -> hold (whether or not supplied); needed under none -> not_needed; an optional document is
    not_needed unless supplied, then present_* (never a request)."""
    t = regime.types[tid]
    supplied = supplied or {}
    used = set()
    for s in t["steps"]:
        used |= cond_facts(s["reached_when"])
    for d in t["documents"]:
        used |= cond_facts(d["needed_when"])
    for s in t["stops"]:
        used |= cond_facts(s["when"])
    unknown = sorted(f for f in used if values.get(f) is None)
    stops = regime.stops(tid)
    comps = []
    for combo in itertools.product([True, False], repeat=len(unknown)):
        v = dict(values)
        v.update(zip(unknown, combo))
        fired = [s["id"] for s in stops if cond_eval(s["when"], v) is True]
        # A stop ends the process after the steps its `reached_when` conditions still reach: rules.json encodes
        # every stop in the conditions of the steps after it (a step before a stop, such as the one that collects
        # the documents needed to decide the stop, stays reached). So steps are read from reached_when alone.
        steps = {s["id"] for s in t["steps"] if cond_eval(s["reached_when"], v) is True}
        docs = {d["id"] for d in t["documents"] if d["step"] in steps and cond_eval(d["needed_when"], v) is True}
        comps.append((combo, frozenset(fired), steps, docs))

    def changed_by(pred):
        out = set()
        for i, f in enumerate(unknown):
            groups = {}
            for combo, fired, steps, docs in comps:
                key = combo[:i] + combo[i + 1:]
                groups.setdefault(key, set()).add(pred(fired, steps, docs))
            if any(len(g) > 1 for g in groups.values()):
                out.add(f)
        return sorted(out)

    res = {"unresolved": unknown, "documents": {}}
    any_stop = [bool(c[1]) for c in comps]
    if all(any_stop) and len({c[1] for c in comps}) == 1:
        # stopped by the same stop(s) under every completion; if the stop that ends it depends on an open answer,
        # it is "pending", as the product's evaluator reports it
        fired = set().union(*(c[1] for c in comps))
        res["stop"] = {"state": "stopped", "stops": sorted(fired)}
    elif any(any_stop):
        res["stop"] = {"state": "pending", "stops": sorted(set().union(*(c[1] for c in comps))),
                       "waits_for": changed_by(lambda fired, s, d: bool(fired))}
    else:
        res["stop"] = {"state": "none", "stops": []}
    for d in t["documents"]:
        did = d["id"]
        need = [did in c[3] for c in comps]
        opt = regime.optional(tid, did)
        sup = supplied.get(did)
        base = {"always": all(need), "some": any(need)}
        if opt:
            if any(need) and sup is not None:
                st = "present_sufficient" if sup else "present_insufficient"
            else:
                st = "not_needed"
            res["documents"][did] = {"state": st, "optional": True, "request": False, **base}
            continue
        if all(need):
            st = "request" if sup is None else "present_sufficient" if sup else "present_insufficient"
            res["documents"][did] = {"state": st, "request": st in ("request", "present_insufficient"), **base}
        elif any(need):
            res["documents"][did] = {"state": "hold", "request": False, **base,
                                     "waits_for": changed_by(lambda fired, s, dd, x=did: x in dd)}
        else:
            res["documents"][did] = {"state": "not_needed", "request": False, **base}
    return res


def fact_step_reachable(regime, tid, values, fact):
    """Whether a step that uses `fact` can still be reached in a file, with `fact` itself unresolved: a step whose
    `reached_when` names it and is not false; a document whose `needed_when` names it, on a step not ruled out,
    and not false; or a stop whose `when` names it and is not false. Other facts take `values` (None:
    unresolved)."""
    v = dict(values)
    v[fact] = None
    t = regime.types[tid]
    step_cond = {s["id"]: s["reached_when"] for s in t["steps"]}
    for s in t["steps"]:
        if fact in cond_facts(s["reached_when"]) and cond_eval(s["reached_when"], v) is not False:
            return True
    for d in t["documents"]:
        if fact in cond_facts(d["needed_when"]) and cond_eval(step_cond[d["step"]], v) is not False \
                and cond_eval(d["needed_when"], v) is not False:
            return True
    for s in t["stops"]:
        if fact in cond_facts(s["when"]) and cond_eval(s["when"], v) is not False:
            return True
    return False


# ----------------------------------------------------------------- must_show items
CONDITIONAL_ITEM = re.compile(r"^(any|where|if|for an?|for the|when)\b|\bif any\b|\(or that", re.I)


def conditional_item(item):
    """A must_show item that applies only in some files ("any ... clause", "where ...", "if ...", "..., if any").
    Such an item is never drawn as the missing item of an insufficient attachment."""
    return bool(CONDITIONAL_ITEM.search(item.strip()))


# ----------------------------------------------------------------- durations in questions (date consistency)
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
                "ten": 10, "eleven": 11, "twelve": 12, "fourteen": 14, "sixteen": 16, "twenty": 20, "thirty": 30}
DURATION = re.compile(r"\b(\d+|" + "|".join(NUMBER_WORDS) + r")\s+(day|week|month|year)s?\b", re.I)
UNIT_DAYS = {"day": 1, "week": 7, "month": 30, "year": 365}


def durations(question):
    """Durations (in days) a question names, e.g. "within 180 days" -> [180]."""
    out = []
    for n, unit in DURATION.findall(question):
        k = int(n) if n.isdigit() else NUMBER_WORDS[n.lower()]
        out.append(k * UNIT_DAYS[unit.lower()])
    return sorted(set(out))


def level_counts(n, share):
    """Round half up: the number of files out of n for a share (0.1 of 15 -> 2, 0.25 of 15 -> 4, 0.5 of 15 -> 8)."""
    return int(n * share + 0.5 + 1e-9)
