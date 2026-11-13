#!/usr/bin/env python3
"""Price the planned Study 4 with the stored-ledger cost model (rebuild/plan/cost_model.py and COST_MODEL.json).
No model calls, no network, no spending. The design is data (DESIGN below): change a number and re-run.

    python3 rebuild/plan/study4_cost.py      # writes STUDY4_COST.json and STUDY4_COST.md next to this file

Per-file prices come from cost_model.estimate's token models:
- core = the product core with three readings (cost_model.core_cost); self-consistency = as many Rules-in-context samples
  as the core's cost per file buys, priced equal to the core's cost per file (the sample count m is reported);
- prompt that may hold, Model executes rules, ReAct = cost_model.single_cost; ReAct on the frontier model has no stored
  run: the cost-efficient model's tokens at the frontier model's token prices (marked as an estimate);
- short = the benchmark's stored files (study4/dev/<regime>/final, text plus attachments): their mean words, priced at
  each stored attachment count and weighted by the stored attachment mix; medium = 800 words, 3 attachments; long =
  2,500 words, 6 attachments.
Low = central estimate. High = output grows with words (core: per-stage output fitted with words; single prompts: the
fitted output-per-word slope applied from the measured mean words) and +25 % on every extrapolated cell.
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cost_model as cm  # noqa: E402

LUNA, TERRA = cm.LUNA, cm.TERRA
MODELS = (LUNA, TERRA)
DESIGNS = ("core", "hold_prompt", "self_consistency", "mer", "react")
LABEL = {"core": "Product core (three readings)", "hold_prompt": "Prompt that may hold",
         "self_consistency": "Self-consistency (cost-matched to the core)", "mer": "Model executes rules", "react": "ReAct"}
BASELINES = ("hold_prompt", "self_consistency", "mer", "react")

# ======================================================================= the design (edit here)
DESIGN = {
    "levels": {"medium": {"words": 800, "attachments": 3}, "long": {"words": 2500, "attachments": 6}},  # short: stored files
    "facts_read": None,          # None = the benchmark's median facts read
    "extrapolation_margin": 0.25,
    "sealed": {
        "regimes": 3,
        "cells": {   # per regime: files (or runs) per cell; "repeat_runs" gives the extra runs per model
            "open_share": {"level": "short", "files": 160},
            "length_medium": {"level": "medium", "files": 40},
            "length_long": {"level": "long", "files": 40},
            "catalogue_3": {"level": "short", "files": 40, "catalogue_regimes": 3},
            "catalogue_4": {"level": "short", "files": 40, "catalogue_regimes": 4},
            "twins": {"level": "short", "files": 30},
            "repeats": {"level": "short", "files": 20, "repeat_runs": {LUNA: 9, TERRA: 2}},
            "rule_change": {"level": "short", "files": 160, "core_share_of_files": 1 / 3, "core_readings": 3},
        },
    },
    "fourth_regime": {"level": "short", "files": 120},
    "development": {
        "pilot": {"models": [LUNA, TERRA], "designs": ["core", "hold_prompt"], "files": {"medium": 12, "long": 12}, "rounds": 1},
        "luna_core": {"models": [LUNA], "designs": ["core"], "files": {"short": 173, "medium": 30, "long": 15}, "rounds": 8},
        "luna_baselines": {"models": [LUNA], "designs": list(BASELINES), "files": {"short": 173, "medium": 30, "long": 15}, "rounds": 3},
        "terra_gates": {"models": [TERRA], "designs": ["core", "hold_prompt", "mer"], "files": {"short": 60, "medium": 12, "long": 6}, "rounds": 3},
    },
    "options": {
        "A": {"frontier_file_factor": 1.0, "frontier_skip": []},
        "B": {"frontier_file_factor": 0.5, "frontier_skip": []},
        "C": {"frontier_file_factor": 0.5, "frontier_skip": ["self_consistency", "react"]},
    },
}


# ======================================================================= per-file prices
def short_mix():
    """Mean words and attachment mix of the benchmark's stored files (text.txt plus attachments/*.txt, not *.clean.txt)."""
    words, atts = [], []
    for regime in ("tenancy", "theft", "dismissal"):
        for d in sorted((cm.DEV / regime / "final").iterdir()):
            if d.is_dir():
                w, a, _ = cm.dev_size(regime, d.name)
                if w is not None:
                    words.append(w)
                    atts.append(a)
    mix = Counter(atts)
    return {"files": len(words), "mean_words": statistics.mean(words), "attachment_mix": {a: n / len(atts) for a, n in sorted(mix.items())}}


def single_high(key, model, words, rule_tokens, calls=None):
    """single_cost with output per call growing with words by the fitted slope (from the measured mean words)."""
    P = cm._params()
    base, scaled, s = cm.single_cost(key, model, words, rule_tokens, calls)
    sp = json.loads(cm.OUT_JSON.read_text())["single_prompts"]
    fk = f"{key}/{model}" if f"{key}/{model}" in sp else f"{key}/{LUNA}"
    slope = max(0.0, sp[fk]["output_fit"]["coef"]["output_per_word"])
    mean_w = MEAN_WORDS_SINGLE
    n = (calls if calls is not None else s["calls_per_file"]) if key != "react" else s["calls_per_file"]
    extra_out = n * slope * max(0.0, words - mean_w)
    return base + cm.usd_of(model, 0, 0, extra_out)


MEAN_WORDS_SINGLE = 183.0   # mean words of Study 3's files (single prompts' fit data), set in main()


def price(design, model, level, catalogue_regimes=1):
    """(low, high, extrapolated, note) USD per file."""
    P = cm._params()
    nf = DESIGN["facts_read"] or P["core_ranges_benchmark"]["facts_read_median"]
    R1 = P["rule_text_tokens_one_regime"]
    if level == "short":
        pts = [(SHORT["mean_words"], a, w) for a, w in SHORT["attachment_mix"].items()]
    else:
        L = DESIGN["levels"][level]
        pts = [(L["words"], L["attachments"], 1.0)]
    low = high = 0.0
    extr, notes = False, set()
    for words, att, wt in pts:
        if design in ("core", "self_consistency"):
            e = cm.estimate("core_three", model, words, att, nf, None)
            c_low = e["usd"]
            c_high = cm.core_cost(model, words, att, nf, None, "three", output_scales_with_words=True)[0]
            x = e["extrapolated"]
            if catalogue_regimes > 1:  # routing over more workflows: one more routing-sized call
                r = e["by_stage"].get("routing", 0.0)
                c_low += r
                c_high += cm.core_cost(model, words, att, nf, None, "three", output_scales_with_words=True)[1].get("routing", 0.0)
                notes.add("one routing-sized call added for the larger catalogue")
            if design == "self_consistency":
                one = cm.single_cost("sc_sample", model, words, R1 * catalogue_regimes, calls=1)[0]
                notes.add(f"m = {int(c_low // one) if one else 0} samples at short/this level" if level != "short" else
                          f"m about {int(c_low // one) if one else 0} samples")
                if model == TERRA:
                    notes.add("no stored frontier run of self-consistency; priced equal to the core by construction")
        else:
            rt = R1 * catalogue_regimes if catalogue_regimes > 1 else None
            e = cm.estimate(design, model, words, att, nf, rt)
            c_low = e["usd"]
            c_high = single_high(design, model, words, rt)
            x = e["extrapolated"]
            if design == "react" and model == TERRA:
                notes.add("estimate: cost-efficient ReAct tokens at frontier token prices")
        extr = extr or x
        low += wt * c_low
        high += wt * c_high
    if extr:
        high *= 1 + DESIGN["extrapolation_margin"]
    return low, high, extr, sorted(notes)


def reading_call(model):
    """USD of one fact-reading call: the benchmark's first-reading stage cost per file / its calls per file."""
    st = json.loads(cm.OUT_JSON.read_text())["core_stage_split"][f"lint/clean/ALL/{model}"]["by_stage"]["fact reading 1"]
    return st["usd_per_file"] / st["calls_per_file"]


# ======================================================================= line items
def line_items(option, core_factor=1.0):
    opt = DESIGN["options"][option]
    items = []

    def add(phase, item, design, model, n, level, cat=1, unit=None):
        if model == TERRA and design in opt["frontier_skip"] and phase in ("sealed test", "fourth regime"):
            return
        if unit is None:
            lo, hi, ex, notes = price(design, model, level, cat)
        else:
            lo, hi, ex, notes = unit
        f = core_factor if design in ("core", "self_consistency") else 1.0
        items.append({"phase": phase, "item": item, "design": design, "model": model, "runs": n, "level": level,
                      "usd_per_run_low": lo * f, "usd_per_run_high": hi * f, "extrapolated": ex, "notes": notes,
                      "low": n * lo * f, "high": n * hi * f})

    S = DESIGN["sealed"]
    for model in MODELS:
        k = opt["frontier_file_factor"] if model == TERRA else 1.0
        for name, c in S["cells"].items():
            files = c["files"] * k * S["regimes"]
            if name == "repeats":
                for d in DESIGNS:
                    add("sealed test", name, d, model, files * c["repeat_runs"][model], c["level"])
            elif name == "rule_change":
                for d in BASELINES:
                    add("sealed test", name, d, model, files, c["level"])
                rc = reading_call(model)
                n = files * c["core_share_of_files"] * c["core_readings"]
                add("sealed test", name + " (core: 3 readings of the added fact, a third of the files)", "core", model, n,
                    "short", unit=(rc, rc, False, ["priced as one first-reading call of the benchmark"]))
            else:
                for d in DESIGNS:
                    add("sealed test", name, d, model, files, c["level"], c.get("catalogue_regimes", 1))
        fr = DESIGN["fourth_regime"]
        for d in DESIGNS:
            add("fourth regime", "fourth regime", d, model, fr["files"] * k, fr["level"])
    for name, dv in DESIGN["development"].items():
        for model in dv["models"]:
            for d in dv["designs"]:
                for level, n in dv["files"].items():
                    add("development", f"{name} ({level})", d, model, n * dv["rounds"], level)
    return items


def totals(items):
    t = {"low": sum(i["low"] for i in items), "high": sum(i["high"] for i in items)}
    for key in ("model", "design", "phase"):
        g = defaultdict(lambda: [0.0, 0.0])
        for i in items:
            g[i[key]][0] += i["low"]
            g[i[key]][1] += i["high"]
        t[f"by_{key}"] = {k: {"low": v[0], "high": v[1]} for k, v in g.items()}
    return t


def top(items, n=5):
    g = defaultdict(lambda: [0.0, 0.0, 0.0])
    for i in items:
        k = (i["phase"], i["item"].split(" (core")[0], i["design"], i["model"])
        g[k][0] += i["low"]
        g[k][1] += i["high"]
        g[k][2] += i["runs"]
    rows = sorted(g.items(), key=lambda kv: -kv[1][0])[:n]
    return [{"phase": k[0], "item": k[1], "design": k[2], "model": k[3], "runs": v[2], "low": v[0], "high": v[1]} for k, v in rows]


SHORT = None


def main():
    global SHORT, MEAN_WORDS_SINGLE
    cm._params()
    SHORT = short_mix()
    MEAN_WORDS_SINGLE = 183.0
    res = {"generated_by": "rebuild/plan/study4_cost.py", "model_calls": 0, "design": DESIGN, "short_files": SHORT,
           "unit_prices": {}, "options": {}}
    for model in MODELS:
        for d in DESIGNS:
            for level in ("short", "medium", "long"):
                lo, hi, ex, notes = price(d, model, level)
                res["unit_prices"][f"{d}/{model}/{level}"] = {"low": lo, "high": hi, "extrapolated": ex, "notes": notes}
            for cat in (3, 4):
                lo, hi, ex, notes = price(d, model, "short", cat)
                res["unit_prices"][f"{d}/{model}/short, {cat}-regime catalogue"] = {"low": lo, "high": hi, "extrapolated": ex, "notes": notes}
        res["unit_prices"][f"core reading call/{model}"] = {"low": reading_call(model), "high": reading_call(model), "extrapolated": False, "notes": []}
    for opt in DESIGN["options"]:
        it = line_items(opt)
        res["options"][opt] = {"totals": totals(it), "top5": top(it), "items": it}
    half = line_items("A", core_factor=0.5)
    res["option_A_core_halved"] = {"totals": totals(half), "top5": top(half),
                                   "note": "every core cost per run x 0.5 (rule-change readings and development included); "
                                           "self-consistency follows by construction"}
    (HERE / "STUDY4_COST.json").write_text(json.dumps(res, indent=1, default=float) + "\n")
    (HERE / "STUDY4_COST.md").write_text(markdown(res) + "\n")
    print("written", HERE / "STUDY4_COST.json", "and", HERE / "STUDY4_COST.md")


def u(x):
    return f"{x:,.2f}"


def markdown(res):
    L = ["# Study 4: priced design (stored-ledger cost model, no model calls)", "",
         "Generated by `rebuild/plan/study4_cost.py` from `COST_MODEL.json` (token prices: cost-efficient model 0.125 / 0.01 / "
         "0.50, frontier model 1.25 / 0.05 / 5.00 USD per million uncached input / cached input / output tokens). The design is "
         "the `DESIGN` dictionary at the top of the script. Low = central estimate; high = output growing with words, and +25 % "
         "on every extrapolated cell (medium, long, larger catalogues for prompts, frontier ReAct). Self-consistency is priced "
         "equal to the core per file by construction.", "",
         f"Short files: {res['short_files']['files']} stored benchmark files, mean {res['short_files']['mean_words']:.0f} words, "
         "attachment mix " + ", ".join(f"{a}: {100 * s:.0f} %" for a, s in res["short_files"]["attachment_mix"].items()) + ".", "",
         "## Option totals (USD)", "",
         "| Option | Cost-efficient model | Frontier model | Total | of which development |", "|---|---|---|---|---|"]
    for k, o in list(res["options"].items()) + [("A, core halved", res["option_A_core_halved"])]:
        t = o["totals"]
        bm, bp = t["by_model"], t["by_phase"]
        g = lambda d: f"{u(d['low'])} – {u(d['high'])}" if d else "–"
        L.append(f"| {k} | {g(bm.get(LUNA))} | {g(bm.get(TERRA))} | {u(t['low'])} – {u(t['high'])} | {g(bp.get('development'))} |")
    L += ["", "## Totals by design (USD, low – high)", "", "| Option | " + " | ".join(LABEL[d] for d in DESIGNS) + " |",
          "|---" * (len(DESIGNS) + 1) + "|"]
    for k, o in list(res["options"].items()) + [("A, core halved", res["option_A_core_halved"])]:
        bd = o["totals"]["by_design"]
        L.append(f"| {k} | " + " | ".join(f"{u(bd[d]['low'])} – {u(bd[d]['high'])}" if d in bd else "–" for d in DESIGNS) + " |")
    L += ["", "## Largest line items, option A", "", "| Phase | Item (all regimes) | Design | Model | Runs | USD low – high |", "|---|---|---|---|---|---|"]
    for r in res["options"]["A"]["top5"]:
        L.append(f"| {r['phase']} | {r['item']} | {LABEL[r['design']]} | {r['model']} | {r['runs']:,.0f} | {u(r['low'])} – {u(r['high'])} |")
    L += ["", "## Price per run (USD, low – high; * extrapolated)", "", "| Design | Model | Level | USD per run | Notes |", "|---|---|---|---|---|"]
    for k, v in res["unit_prices"].items():
        parts = k.split("/")
        L.append(f"| {LABEL.get(parts[0], parts[0])} | {parts[1]} | {parts[2] if len(parts) > 2 else '–'} | "
                 f"{v['low']:.5f} – {v['high']:.5f}{'*' if v['extrapolated'] else ''} | {'; '.join(v['notes'])} |")
    L += ["", "## Line items, option A", "", "| Phase | Item | Design | Model | Runs | USD per run | USD low – high |", "|---|---|---|---|---|---|---|"]
    for i in res["options"]["A"]["items"]:
        L.append(f"| {i['phase']} | {i['item']} | {LABEL[i['design']]} | {i['model']} | {i['runs']:,.0f} | "
                 f"{i['usd_per_run_low']:.5f}{'*' if i['extrapolated'] else ''} | {u(i['low'])} – {u(i['high'])} |")
    L += ["", "## Assumptions and limits", "",
          "- Per-file prices are the cost model's (see COST_MODEL.md): the core fitted on 173 benchmark files of 183-575 words, "
          "0-4 attachments; medium and long files are extrapolations (the core's calls x per-call tokens grow linearly with words).",
          "- One estimator for all regimes: per-regime differences in the stored files are not carried into the sealed test.",
          "- Catalogue sweep: the core adds one routing-sized call; prompts carry 3x or 4x one regime's rule text "
          f"({cm._params()['rule_text_tokens_one_regime']:,.0f} tokens), beyond any measured prompt.",
          "- Rule change: each baseline reruns the 160 short files per regime; the core reads the added fact three times in a "
          "third of them, each reading priced as one benchmark first-reading call (whole file in the prompt).",
          "- Frontier ReAct and self-consistency were never run: ReAct = cost-efficient tokens at frontier prices; "
          "self-consistency = the core's cost per file.",
          "- Prefix caching as measured in the stored runs; without it single prompts cost several times more.",
          "- Repeated runs priced as fresh runs (no cache reuse)."]
    return "\n".join(L)


if __name__ == "__main__":
    main()
