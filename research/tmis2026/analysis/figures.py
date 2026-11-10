"""Figures for the paper (vector PDF), generated from the evidence files.

The six figures of the TMIS paper (fig_hero, fig_reconverge, fig_fate,
fig_outcomes, fig_trace, fig_models) share one palette with fixed roles:
requested / held / handed over / missed / unnecessary keep the same colour (and,
for greyscale print, the same mark shape) everywhere, and so do the two ways of
applying rules (model-applied, code-executed). Every plotted number is read from
the evidence files below; schematic content is labelled as such.
Usage: python figures.py [--legacy] [--png DIR]  (no model calls)."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("pdf")
import matplotlib.pyplot as plt
from matplotlib import font_manager

HERE = Path(__file__).resolve().parent
FIG = HERE.parent / "paper" / "figures"
FIG.mkdir(parents=True, exist_ok=True)
for f in font_manager.findSystemFonts():
    if "Biolinum" in f or "Libertine" in f:
        font_manager.fontManager.addfont(f)
plt.rcParams.update({"font.family": "Linux Biolinum O", "font.size": 7.5, "axes.titlesize": 8, "axes.labelsize": 7.5,
                     "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7, "axes.linewidth": 0.6,
                     "xtick.major.width": 0.6, "ytick.major.width": 0.6, "pdf.fonttype": 42, "hatch.linewidth": 0.5})
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
W = 5.3  # acmsmall text width in inches


def clean(ax, xgrid=True):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(MUTED)
    ax.tick_params(axis="y", length=0, colors=INK)
    ax.tick_params(axis="x", colors=MUTED)
    if xgrid:
        ax.grid(axis="x", color=GRID, linewidth=0.5)
        ax.set_axisbelow(True)


def load(name):
    p = HERE / name
    return json.loads(p.read_text()) if p.exists() else None


# ------------------------------------------------------------------ Figure: tenancy outcomes
def fig_tenancy():
    rows = [("B1", "Rules in context"), ("B1-SC3", "Rules in context, majority of 3"), ("B2", "Model executes rules"),
            ("CP-kleene", "CasePath, product engine (Kleene)"), ("CP-exact", "CasePath, exact deferral"),
            ("CP-exact-noverifier", "CasePath, exact deferral, no verifier")]
    panels = [(tag, name) for tag, name in (("gpt-6.1-terra", "gpt-6.1-terra"), ("gpt-6-luna", "gpt-6-luna"))
              if load(f"results_{tag}.json") and "tenancy" in load(f"results_{tag}.json")]
    fig, axes = plt.subplots(1, len(panels), figsize=(W, 2.15), sharey=True, squeeze=False)
    for ax, (tag, title) in zip(axes[0], panels):
        t = load(f"results_{tag}.json")["tenancy"]
        shown = rows  # identical rows in every panel so shared labels stay aligned
        ys = list(range(len(shown)))[::-1]
        for y, (k, lab) in zip(ys, shown):
            if k not in t:
                ax.text(2, y, "not run with this model", va="center", ha="left", color=MUTED, fontsize=6.3, style="italic")
                continue
            v = t[k]
            req, hld, hnd, mis = v["recall"], v["held_rate"], v["handed_rate"], v["silent_miss_rate"]
            ax.barh(y, 100 * req, color=BLUE, height=0.62, edgecolor="white", linewidth=0.8)
            ax.barh(y, 100 * hld, left=100 * req, color=AQUA, height=0.62, hatch="////", edgecolor="white", linewidth=0.8)
            ax.barh(y, 100 * hnd, left=100 * (req + hld), color=MUTED, height=0.62, hatch="....", edgecolor="white", linewidth=0.8)
            ax.barh(y, 100 * mis, left=100 * (req + hld + hnd), color=ORANGE, height=0.62, hatch="xxxx", edgecolor="white", linewidth=0.8)
            ax.text(100 * req - 1.5, y, f"{100 * req:.0f}", va="center", ha="right", color="white", fontsize=6.5)
            if hld > 0.06:
                ax.text(100 * (req + hld) - 1.5, y, f"{100 * hld:.0f}", va="center", ha="right", color=INK, fontsize=6.5)
            ax.text(103, y, f"{100 * v['unnecessary_rate']:.1f}", va="center", ha="left", color=INK, fontsize=6.5)
        ax.set_yticks(ys)
        ax.set_yticklabels([lab for _, lab in shown])
        ax.set_xlim(0, 112)
        ax.set_xticks([0, 25, 50, 75, 100])
        ax.set_xlabel("Share of required documents (%)")
        ax.set_title(title, loc="left", color=INK)
        ax.text(103, len(shown) - 0.35, "Unnec.\n(%)", fontsize=6, color=MUTED, va="bottom")
        clean(ax)
    from matplotlib.patches import Patch
    handles = [Patch(facecolor=BLUE, label="Requested"), Patch(facecolor=AQUA, hatch="////", edgecolor="white", label="Held behind a question"),
               Patch(facecolor=MUTED, hatch="....", edgecolor="white", label="Handed to a person (whole claim)"),
               Patch(facecolor=ORANGE, hatch="xxxx", edgecolor="white", label="Silently missed")]
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False, bbox_to_anchor=(0.55, -0.02), columnspacing=1.0,
               handletextpad=0.4)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(FIG / "fig_tenancy.pdf")
    plt.close(fig)


# ------------------------------------------------------------------ Figure: theft across models
def fig_theft():
    o = load("original_study.json")["table"]  # gpt-5.6-terra, preregistered single run, as frozen (all routes)
    orig = {"D": (o["D"]["wrong_per_pair"], o["D"]["missed_per_pair"]), "R": (o["R"]["wrong_per_pair"], o["R"]["missed_per_pair"]),
            "CP": (o["CP-allroutes"]["wrong_per_pair"], o["CP-allroutes"]["missed_per_pair"])}
    models = [("gpt-5.6-terra (original study, 1 run)", None, "D", "none"), ("gpt-6.1-terra (3 runs)", "gpt-6.1-terra", "o", "full"),
              ("gpt-6-luna (3 runs)", "gpt-6-luna", "s", "full")]
    designs = [("D", "Direct"), ("R", "Rules in context"), ("CP", "CasePath")]
    fig, axes = plt.subplots(1, 3, figsize=(W, 2.0), sharey=True)
    ys = {"D": 2, "R": 1, "CP": 0}
    offs = {0: 0.27, 1: -0.03, 2: -0.23}  # the original single run sits apart, above the two three-run markers
    colors = [MUTED, BLUE, ORANGE]
    for i, (mlabel, tag, marker, fill) in enumerate(models):
        res = load(f"results_{tag}.json") if tag else None
        for key, _ in designs:
            if tag is None:
                wrong, missed, unstable = orig[key][0], orig[key][1], None
            else:
                if not res or "theft" not in res or key not in res["theft"]:
                    continue
                v = res["theft"][key]
                wrong, missed = v["on"]["wrong_per_pair"], v["on"]["missed_per_pair"]
                unstable = 100 - 100 * v["unresolved"]["stable_rate"]
            y = ys[key] + offs[i]
            kw = dict(marker=marker, s=22, linewidths=0.9, edgecolors=colors[i],
                      facecolors=(colors[i] if fill == "full" else "white"), zorder=3)
            axes[0].scatter(wrong, y, **kw)
            axes[1].scatter(missed, y, **kw)
            if unstable is not None:
                axes[2].scatter(unstable, y, **kw)
    axes[0].set_xlabel("Wrong changes per pair\n\u2190 lower is better")
    axes[1].set_xlabel("Missed changes per pair\n\u2190 lower is better")
    axes[2].set_xlabel("Unresolved pairs with a change (%)\n\u2190 lower is better")
    for y in (0.5, 1.5):  # separate the designs
        for ax in axes:
            ax.axhline(y, color=GRID, linewidth=0.5, zorder=1)
    axes[0].set_yticks([2, 1, 0])
    axes[0].set_yticklabels([d for _, d in designs])
    axes[0].set_xlim(0, 1.7); axes[1].set_xlim(0, 0.7); axes[2].set_xlim(0, 75)
    for ax in axes:
        clean(ax)
        ax.set_ylim(-0.6, 2.6)
    from matplotlib.lines import Line2D
    handles = [Line2D([], [], marker=mk, linestyle="none", markersize=5.5, markeredgewidth=0.9, markeredgecolor=colors[i],
                      markerfacecolor=(colors[i] if fl == "full" else "white"), label=lab)
               for i, (lab, _, mk, fl) in enumerate(models)]
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.55, -0.03), handletextpad=0.2)
    fig.tight_layout(rect=(0, 0.13, 1, 1))
    fig.savefig(FIG / "fig_theft.pdf")
    plt.close(fig)


# ------------------------------------------------------------------ Figure: semantics under judgment errors
def fig_propagation():
    s1 = json.loads((HERE.parent / "scicore" / "out_local" / "s1_propagation.json").read_text())
    g = {(r["eps"], r["rho"]): r for r in s1}
    eps = 0.2
    base = g[(0.0, 1.0)]
    sems = [("exact", "Exact"), ("kleene", "Kleene"), ("closed", "Open\nas false"), ("eager", "Open\nas true")]
    panels = [(1.0, "All judgment errors are 'unresolved'"), (0.5, "Half unresolved, half wrong"), (0.0, "All errors are wrong verdicts")]
    fig, axes = plt.subplots(1, 3, figsize=(W, 1.95), sharey=True)
    n = base["required_total"] / 100.0
    for ax, (rho, title) in zip(axes, panels):
        r = g[(eps, rho)]
        for i, (s, lab) in enumerate(sems):
            unn = (r[f"{s}_unnecessary"] - base[f"{s}_unnecessary"]) / n
            mis = r[f"{s}_missed"] / n
            dfr = r[f"{s}_deferred"] / n
            ax.bar(i, unn, color=ORANGE, width=0.66, edgecolor="white", linewidth=0.8)
            ax.bar(i, mis, bottom=unn, color="#b44a20", hatch="xxxx", width=0.66, edgecolor="white", linewidth=0.8)
            ax.bar(i, dfr, bottom=unn + mis, color=AQUA, hatch="////", width=0.66, edgecolor="white", linewidth=0.8)
        ax.set_xticks(range(4))
        ax.set_xticklabels([lab for _, lab in sems], fontsize=6.5)
        ax.set_title(title, loc="left", fontsize=7, color=INK)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.spines["left"].set_color(MUTED); ax.spines["bottom"].set_color(MUTED)
        ax.grid(axis="y", color=GRID, linewidth=0.5); ax.set_axisbelow(True)
        ax.tick_params(axis="x", length=0)
    axes[0].set_ylabel("Per 100 required documents")
    from matplotlib.patches import Patch
    handles = [Patch(facecolor=ORANGE, label="Unnecessary requests"), Patch(facecolor="#b44a20", hatch="xxxx", edgecolor="white", label="Silent misses"),
               Patch(facecolor=AQUA, hatch="////", edgecolor="white", label="Deferrals")]
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.55, -0.03))
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    fig.savefig(FIG / "fig_propagation.pdf")
    plt.close(fig)




# ====================================================================== TMIS figures (2026-11)
# Every figure below draws only through analysis/figtheme.py (one palette, three type sizes, two line
# weights, one mark family, one legend grammar). Explanations, sample sizes and evidence status
# (schematic / engine output / exact computation / measured) live in the captions.
import sys as _sys
import figtheme as th

PREVIEW = None     # directory for print-size PNG previews (set by --png)
LEGEND_Y = 0.10    # legend row: distance below the top edge, same in every figure
LEGEND_X = 0.06    # legend row: left margin, same in every figure


def _save(fig, name):
    th.save(fig, FIG / f"{name}.pdf", PREVIEW)


OUTCOME_DESIGNS = [("model", "B1", "Rules in context"),
                   ("code", "tv:closed", "Two-valued,\nopen read as false"),
                   ("code", "tv:eager", "Two-valued,\nopen read as true"),
                   ("code", "CP-kleene", "CasePath,\nstrong Kleene"),
                   ("code", "CP-exact", "CasePath,\nexact deferral")]

# ---------------------------------------------------------------------- data (unchanged evidence paths)
STEP_SHORT = {"dh_intake": "Capture defect", "dh_safety": "Escalate health risk", "dh_scope": "Dated defect timeline",
              "dh_notice": "Landlord notice", "dh_cause": "Keep causation open", "dh_evidence": "Objective evidence",
              "dh_response": "Landlord response", "dh_specialist": "Technical inspection",
              "dh_deposit": "Rent-deposit safeguards", "dh_resolution": "Record outcome", "dh_close": "Close or hand off"}


DOC_SHORT = {"medical_confirmation": "medical confirmation", "lease_contract": "lease", "defect_notification": "defect notice",
             "proof_of_notification": "proof of notice", "caretaker_correspondence": "caretaker letters",
             "dated_photos": "photos", "humidity_temperature_log": "humidity log",
             "heating_service_report": "heating report", "landlord_response_history": "landlord replies",
             "technical_inspection": "inspection report", "written_repair_deadline": "repair deadline"}


def reconverge_data():
    """Run the production engine (strong Kleene) and exact deferral (supervaluation) on the tenancy
    defect process (family defect_mold_heating) with health_effects unresolved, mold true and the
    other flags false; also evaluate the two completions of health_effects. No model call."""
    root = HERE.parent
    for p in (root / "harness", root.parents[1] / "casepath-api"):
        if str(p) not in _sys.path:
            _sys.path.insert(0, str(p))
    import casepath_tenancy as ct
    from casepath_api.autonomous_policy_v1 import compile_process
    from casepath_api.causal_process_v1 import evaluate
    from tenancy_data import templates
    flags = {"health_effects": "unresolved", "mold": "true", "heating": "false", "specialist_needed": "false",
             "deposit_considered": "false"}
    v = {"category": {"family": "defect_mold_heating", "summary": "s", "citations": []},
         "conditions": [{"flag": f, "verdict": x, "summary": "s", "citations": []} for f, x in flags.items()],
         "documents": [], "steps": [], "item_rejections": []}
    g, _, _ = compile_process(templates(), "fig", v)
    kl = evaluate(g)
    out = {"graph": g, "flags": flags,
           "kleene_nodes": {n["node_id"]: n["activation"] for n in kl["nodes"]},
           "kleene_docs": {d["document_type"]: d["route_state"] for d in kl["documents"]},
           "exact_docs": ct.supervaluate(g)["states"], "worlds": {}}
    for h in ("true", "false"):
        w = evaluate(g, conditions={"health_effects": h})
        out["worlds"][h] = {"nodes": {n["node_id"]: n["activation"] for n in w["nodes"]},
                            "docs": {d["document_type"]: d["route_state"] for d in w["documents"]}}
    out["classes"] = {d["document_type"]: d["requirement_class"] for d in g["document_catalog"]}
    return out


FATE_EPS = 0.1   # error probability per condition (macro propEps)


SEMANTICS = [("kleene", "Strong Kleene"), ("exact", "Exact deferral"), ("closed", "Open read as false"),
             ("eager", "Open read as true")]


def fate_data(eps=FATE_EPS):
    """The exact computation of scicore/s1_propagation.py (all 150 claims, every judgment vector): each
    condition is judged wrongly with probability eps; rho = 1 makes every error 'unresolved', rho = 0 a
    confident wrong verdict. Per 100 required documents; unnecessary requests in excess of eps = 0."""
    s1 = {(r["eps"], r["rho"]): r for r in
          json.loads((HERE.parent / "scicore" / "out_local" / "s1_propagation.json").read_text())}
    base, n = s1[(0.0, 1.0)], s1[(0.0, 1.0)]["required_total"]
    per100 = {}
    for kind, rho in (("unresolved", 1.0), ("wrong", 0.0)):
        r = s1[(eps, rho)]
        per100[kind] = {s: {"deferred": 100 * r[f"{s}_deferred"] / n, "missed": 100 * r[f"{s}_missed"] / n,
                            "unnecessary": 100 * (r[f"{s}_unnecessary"] - base[f"{s}_unnecessary"]) / n,
                            "deferred_beyond_exact": 100 * (r[f"{s}_deferred"] - r["exact_deferred"]) / n}
                        for s, _ in SEMANTICS}
    return {"per100": per100, "required": n, "claims": base["claims"], "eps": eps}


MODELS = [("gpt-6.1-terra", "Primary analysis", "gpt-6.1-terra"), ("gpt-6-luna", "Secondary analysis", "gpt-6-luna")]


def largest_remainder(values, total=100):
    floors = [int(v) for v in values]
    rest = total - sum(floors)
    order = sorted(range(len(values)), key=lambda i: values[i] - floors[i], reverse=True)
    for i in order[:rest]:
        floors[i] += 1
    return floors


def outcomes_data():
    tv = load("two_valued.json")
    out = {}
    for tag, _, _ in MODELS:
        t = load(f"results_{tag}.json")["tenancy"]
        for _, key, _ in OUTCOME_DESIGNS:
            v = tv[tag][f"tenancy_{key[3:]}"] if key.startswith("tv:") else t.get(key)
            if v is None:
                out[(tag, key)] = None
                continue
            n = v["nR"]
            parts = [100 * v["tp"] / n, 100 * v["held"] / n, 100 * v["handed"] / n, 100 * v["miss"] / n]
            assert abs(sum(parts) - 100) < 1e-6, (tag, key)
            out[(tag, key)] = {"pct": parts, "units": largest_remainder(parts), "unnec_per100": 100 * v["fp"] / n,
                               "unnec_share_of_requests": v["unnecessary_rate"], "nR": n, "fp": v["fp"]}
    return out


IMPLICATED = ["overlay_rule_042", "overlay_rule_003", "overlay_rule_084", "overlay_rule_074", "overlay_rule_010"]


RULE_SHORT = {"overlay_rule_042": "Assign third-party claims", "overlay_rule_003": "Preserve traces and items",
              "overlay_rule_084": "SIM-card misuse losses", "overlay_rule_074": "Listed valuables \u2265 CHF 1,000",
              "overlay_rule_010": "Date, place, circumstances", "overlay_rule_004": "Mitigate loss after event"}


DOC_TRACE = [("Written assignment to the insurer", "written assignment"),
             ("Insurer's consent to alteration", "insurer's consent"),
             ("Police consent to the removal", "police consent"),
             ("Bank statement showing the misuse", "bank statement"),
             ("Expert's valuation of the scheduled valuable", "expert valuation"),
             ("Insurer's instruction (Weisung", "insurer's instruction"),
             ("The experts' findings", "experts' findings")]


def trace_data(tag="gpt-6.1-terra"):
    """Every wrong change on the held-out changed-fact theft pairs (three runs), for CasePath and Rules in
    context. CasePath's are attributed to the rules whose requirement produced them (the logic of
    theft_error_origin.py, which wrote error_causes.json); Rules in context records no rule."""
    root = HERE.parent
    if str(root / "harness") not in _sys.path:
        _sys.path.insert(0, str(root / "harness"))
    import theft_methods as tm
    from theft_data import pairs, best_realization
    from theft_score import delta
    P = json.loads((root / "runs" / f"plans_theft_{tag}.json").read_text())

    def short(atom):
        for prefix, s in DOC_TRACE:
            if atom[1:].startswith(prefix):
                return s
        raise KeyError(atom)

    cp, rc = [], []
    for p in pairs():
        if p["split"] != "heldout" or p["kind"] != "on":
            continue
        for r in range(3):
            a, b = P[f"CP|{p['off']}|{r}"], P[f"CP|{p['variant']}|{r}"]
            nu0, nu1 = a["judgments"], b["judgments"]
            changed = {g for g in tm.GUARDS if nu0[g] != nu1[g]}
            pred = delta(set(tm.plan(nu0)["requests"]), set(tm.plan(nu1)["requests"]))
            assert pred == delta(set(a["plan"]["requests"]), set(b["plan"]["requests"]))  # recorded plans agree
            sel, _ = best_realization(pred, p["reference"])
            for atom in sorted(set(pred) - set(sel)):
                prod = (tm.trace(nu1) if atom[0] == "+" else tm.trace(nu0)).get(atom[1:], [])
                rules = sorted({o["rule"] for o in prod if o["guard"] in changed or o["guard"] is None})
                cp.append({"run": r, "sign": atom[0], "doc": short(atom), "rules": rules, "condition": p["condition"]})
            ra = (P.get(f"R|{p['off']}|{r}") or {}).get("plan") or {"requests": []}
            rb = (P.get(f"R|{p['variant']}|{r}") or {}).get("plan") or {"requests": []}
            pred = delta(set(ra["requests"]), set(rb["requests"]))
            sel, _ = best_realization(pred, p["reference"])
            for atom in sorted(set(pred) - set(sel)):
                rc.append({"run": r, "sign": atom[0], "doc": short(atom), "condition": p["condition"]})
    res = load(f"results_{tag}.json")["theft"]
    assert len(cp) == res["CP"]["on"]["wrong"] and len(rc) == res["R"]["on"]["wrong"]
    rv = load("rule_verification.json")
    return {"cp": cp, "rc": rc, "verifier": rv,
            "flagged": sum(1 for v in rv["results"].values() if v["result"] and v["result"]["verdict"] == "flag"),
            "rules_total": len(rv["results"])}


def models_data():
    o = load("original_study.json")["table"]
    out = []
    # ordered by release; no capability order is implied
    for tag, label, sub in (("gpt-5.6-terra", "gpt-5.6-terra", "original study, 1 run"),
                            ("gpt-6-luna", "gpt-6-luna", ""), ("gpt-6.1-terra", "gpt-6.1-terra", "")):
        if tag == "gpt-5.6-terra":
            row = {"R": {"wpp": o["R"]["wrong_per_pair"], "wrong": o["R"]["wrong"], "ci": None, "dedup": None},
                   "CP": {"wpp": o["CP-oneroute"]["wrong_per_pair"], "wrong": o["CP-oneroute"]["wrong"], "ci": None,
                          "dedup": None}, "single": True}
        else:
            th = load(f"results_{tag}.json")["theft"]
            row = {k: {"wpp": th[k]["on"]["wrong_per_pair"], "wrong": th[k]["on"]["wrong"],
                       "ci": th[k]["on"]["wrong_per_pair_ci"], "dedup": th[k]["sensitivity_offplan_dedup"]["wrong_per_pair"]}
                   for k in ("R", "CP")}
            row["single"] = False
        row.update(tag=tag, label=label, sub=sub)
        out.append(row)
    return out



# ---------------------------------------------------------------------- real-screen figures (Fig. 1, knowledge)
# Crops of real CasePath screens (round 2: English cases, 2x captures, gpt-6-luna; see
# figures/ui_used/MANIFEST.md). Crops are faithful: pixels embedded unresampled, nothing retouched.
# Each entry: source file, crop box (capture px), measured ascender-to-descender height of the crop's
# smallest text line (capture px). Every crop is scaled so that this line prints at the same height.
UI = HERE.parent / "paper" / "figures" / "ui_used" / "en2"
UI_BAND = 6.0 / 72          # printed ascender-to-descender height of the smallest kept text, in
UI_CROPS = {
    "claim_yes": ("A-yes-1-claim-reader.png", (636, 1653, 1872, 1800), 30),
    "claim_open": ("B-open-1-claim-reader.png", (636, 1653, 1872, 1800), 30),
    "step_yes": ("A-yes-3-process-builder-crop1.png", (1168, 10, 1872, 230), 27),
    "step_open": ("B-open-3-process-builder-crop1.png", (1168, 10, 1872, 230), 27),
    "out_yes": ("A-yes-5-result-checker.png", (620, 572, 1400, 776), 27),
    "out_open": ("B-open-5-result-checker.png", (620, 572, 1400, 776), 27),
    "k_added": ("k1-after-correction-4-document-finder.png", (590, 1136, 1712, 1264), 27),
    "k_active": ("k2-knowledge-active-card1.png", (28, 28, 488, 148), 28),
    "k_used": ("case2-4-document-finder.png", (1922, 984, 2792, 1160), 27),
    "k_refine": ("k3-knowledge-refinement-card2.png", (28, 28, 812, 182), 28),
}
UI_TEXT_PT = {}


def screen(ax, key, x, top):
    """Place one faithful crop (left edge x, top edge `top`), scaled so its smallest text line prints
    UI_BAND high; thin neutral frame. Returns (x0, y0, x1, y1, scale) with scale in inches per pixel."""
    import numpy as _np
    from PIL import Image as _Image
    f, box, band = UI_CROPS[key]
    img = _np.asarray(_Image.open(UI / f).convert("RGB").crop(box))
    s = UI_BAND / band
    w, h = img.shape[1] * s, img.shape[0] * s
    ax.imshow(img, extent=(x, x + w, top - h, top), interpolation="none", zorder=1, aspect="auto")
    ax.add_patch(th.Rectangle((x, top - h), w, h, fc="none", ec=th.NEUTRAL, lw=th.THIN, zorder=2))
    UI_TEXT_PT[key] = round(band * s * 72, 1)
    return x, top - h, x + w, top, s


def trace(ax, pts, dots=(0, -1)):
    """The one trace per row: an ochre polyline through the gutters, dots where it meets a crop."""
    xs, ys = zip(*pts)
    ax.plot(xs, ys, color=th.HELD, lw=th.THICK, solid_joinstyle="round", solid_capstyle="round", zorder=3)
    for x, y in [pts[j] for j in dots]:
        ax.add_patch(th.Circle((x, y), 0.022, fc=th.HELD, ec="none", zorder=4))


def fig_hero():
    """Two aligned rows (the claim states the fact / leaves it open), same columns and the same printed
    text height: claim quotation -> recorded judgment -> process -> outcome, one ochre trace per row."""
    W, H = th.WIDTH, 3.62
    fig, ax = th.canvas(H)
    x0, gut = 0.04, 0.30
    top = H - 0.12
    rows = [("yes", "The claim states the fact", "true", "active"),
            ("open", "The claim leaves the fact open", "unresolved", "unresolved")]
    for i, (k, title, val, node) in enumerate(rows):
        th.text(ax, x0, top, title, "label", bold=True)
        A = screen(ax, f"claim_{k}", x0, top - 0.13)
        C = screen(ax, f"step_{k}", x0, A[1] - 0.40)
        D = screen(ax, f"out_{k}", C[2] + gut, C[3])
        xj, yj = x0 + 0.42, (A[1] + C[3]) / 2
        th.node(ax, xj, yj, node)
        th.text(ax, xj + 0.10, yj, "health effects: " + val, "label")
        if i == 0:
            th.text(ax, A[2], A[3] + 0.05, "claim", "note", ha="right", va="bottom")
            th.text(ax, xj + 0.10 + th.width(ax, "health effects: " + val) + 0.14, yj, "(recorded judgment)",
                    "note")
            th.text(ax, C[2], C[3] + 0.05, "process", "note", ha="right", va="bottom")
            th.text(ax, D[2], D[3] + 0.05, "outcome", "note", ha="right", va="bottom")
        trace(ax, [(xj, A[1]), (xj, yj + 0.05)], dots=(0,))
        trace(ax, [(xj, yj - 0.05), (xj, C[3])], dots=(-1,))
        ys = D[3] - 0.30 * (D[3] - D[1])
        trace(ax, [(C[2], ys), (D[0], ys)])
        top = C[1] - 0.24
    _save(fig, "fig_hero")


def fig_knowledge():
    """Two rows of two equal-height-text crops joined by one trace: the handler adds a document need ->
    the item, approved, is active (v1) -> the next case requests it from Knowledge -> refinement proposed."""
    W, H = th.WIDTH, 1.62
    fig, ax = th.canvas(H)
    x0, gut = 0.03, 0.25
    top = H - 0.20
    K1 = screen(ax, "k_added", x0, top)
    w2 = (UI_CROPS["k_active"][1][2] - UI_CROPS["k_active"][1][0]) * UI_BAND / UI_CROPS["k_active"][2]
    K2 = screen(ax, "k_active", W - 0.03 - w2, top)
    r2 = min(K1[1], K2[1]) - 0.36
    K3 = screen(ax, "k_used", x0, r2)
    w4 = (UI_CROPS["k_refine"][1][2] - UI_CROPS["k_refine"][1][0]) * UI_BAND / UI_CROPS["k_refine"][2]
    K4 = screen(ax, "k_refine", W - 0.03 - w4, r2)
    for P, s in ((K1, "handler adds"), (K2, "approved, active"), (K3, "next case: from Knowledge"),
                 (K4, "refinement proposed")):
        th.text(ax, P[2], P[3] + 0.05, s, "note", ha="right", va="bottom")
    ya = (K1[3] + K1[1]) / 2 + 0.10
    trace(ax, [(K1[2], ya), (K2[0], ya)])
    xb = K2[0] + 0.35
    yg = (K2[1] + K3[3]) / 2 + 0.02
    trace(ax, [(xb, K2[1]), (xb, yg), (K3[0] + 1.6, yg), (K3[0] + 1.6, K3[3])])
    yd = (K3[3] + K3[1]) / 2
    trace(ax, [(K3[2], yd), (K4[0], yd)])
    _save(fig, "fig_knowledge")



# ---------------------------------------------------------------------- Fig. 2 (engine output)
def fig_reconverge():
    """Mirrored panels around one column of step names: strong Kleene floods everything downstream of
    the open branch; exact deferral runs the two completions as two traversals of the same graph."""
    D = reconverge_data()
    g = D["graph"]
    nodes = {n["node_id"]: n for n in g["nodes"]}
    order = ["dh_intake", "dh_safety", "dh_scope", "dh_notice", "dh_cause", "dh_evidence", "dh_response",
             "dh_specialist", "dh_deposit", "dh_resolution", "dh_close"]
    side = {"dh_safety", "dh_specialist", "dh_deposit"}
    H, dy = 2.95, 0.205
    fig, ax = th.canvas(H)
    W = th.WIDTH
    top = H - LEGEND_Y
    th.legend(ax, LEGEND_X, top, ["requested", "held", "inactive"])
    yt = top - 0.62
    yof = {n: yt - i * dy for i, n in enumerate(order)}
    xm = W / 2
    lanes = {0: (xm - 0.56, xm - 0.72), 1: (xm + 0.56, xm + 0.74)}
    docx = {0: xm - 0.84, 1: xm + 0.86}
    th.text(ax, 0, top - 0.32, "Strong Kleene", "title", bold=True)
    th.text(ax, W, top - 0.32, "Exact deferral", "title", bold=True, ha="right")

    def lane(p, n):
        return lanes[p][1] if n in side else lanes[p][0]

    def state(p, d):
        st = D["kleene_docs" if p == 0 else "exact_docs"][d]
        return {"needed_later": "requested", "held_behind_question": "held", "not_needed": "inactive"}[st]

    for p in (0, 1):
        for e in g["edges"]:
            a, b = e["source_node_id"], e["target_node_id"]
            th.line(ax, [lane(p, a), lane(p, b)], [yof[a], yof[b]], color=th.NEUTRAL, zorder=1)
        if p == 0:
            act = D["kleene_nodes"]
            for e in g["edges"]:
                a, b = e["source_node_id"], e["target_node_id"]
                if act[b] == "unresolved" and act[a] in ("true", "unresolved"):
                    th.line(ax, [lane(0, a), lane(0, b)], [yof[a], yof[b]], "thick", th.HELD, zorder=2)
        else:
            for h, off in (("true", 0.035), ("false", -0.035)):
                act = D["worlds"][h]["nodes"]
                for e in g["edges"]:
                    a, b = e["source_node_id"], e["target_node_id"]
                    if act[a] == "true" and act[b] == "true":
                        th.line(ax, [lane(1, a) + off, lane(1, b) + off], [yof[a], yof[b]], "thick", th.INK, zorder=2)
                x = lane(1, "dh_intake") + off
                th.line(ax, [x, x], [yof["dh_intake"], yof["dh_intake"] + 0.16], "thick", th.INK, zorder=2)
                th.text(ax, x, yof["dh_intake"] + 0.25, "yes" if h == "true" else "no", "note",
                        ha="left" if h == "true" else "right")
            th.text(ax, lane(1, "dh_intake"), yof["dh_intake"] + 0.40, "health effects", "note", ha="center")
        for n in order:
            x, y = lane(p, n), yof[n]
            if p == 0:
                k = {"true": "active", "unresolved": "unresolved", "false": "inactive"}[D["kleene_nodes"][n]]
            else:
                hits = sum(D["worlds"][h]["nodes"][n] == "true" for h in ("true", "false"))
                k = ["inactive", "unresolved", "active"][hits]
            th.node(ax, x, y, k)
            xx = docx[p]
            for d in nodes[n].get("document_types", []):
                if D["classes"][d] == "optional":
                    continue        # optional documents are never requested; omitted
                if p == 0:
                    xx = th.doc(ax, xx, y, DOC_SHORT[d], state(0, d), anchor="right") - 0.08
                else:
                    xx = th.doc(ax, xx, y, DOC_SHORT[d], state(1, d)) + 0.08
    for n in order:
        th.text(ax, xm, yof[n], STEP_SHORT[n], color=th.NEUTRAL if D["kleene_nodes"][n] == "false" else th.INK,
                ha="center")
    _save(fig, "fig_reconverge")


# ---------------------------------------------------------------------- Fig. 3 (exact computation)
def fig_fate():
    """Rows: kind of judgment error x semantics; columns: outcome, one shared scale. A staircase for
    unresolved judgments, a stripe for confidently wrong ones."""
    F = fate_data()
    P = F["per100"]
    H = 2.15
    fig, ax = th.canvas(H)
    W = th.WIDTH
    top = H - LEGEND_Y
    th.legend(ax, LEGEND_X, top, ["held", "missed", "unnecessary"])
    xcol = [2.42, 3.47, 4.47]
    scale = 0.80 / 15.0
    rh, gap, bh = 0.165, 0.20, th.MS
    y = top - 0.42
    for kind, name in (("unresolved", "Unresolved"), ("wrong", "Confidently wrong")):
        th.text(ax, 0, y - 1.5 * rh, name, "label", bold=True)
        for i, (s, sname) in enumerate(SEMANTICS):
            yy = y - i * rh
            th.text(ax, 1.15, yy, sname)
            for (k, x) in zip(("deferred", "missed", "unnecessary"), xcol):
                th.line(ax, [x, x], [yy - rh / 2, yy + rh / 2], color=th.NEUTRAL)
                v = P[kind][s][k]
                if abs(v) < 0.05:
                    continue
                wv = max(v, 0) * scale
                if k == "deferred":
                    extra = P[kind][s]["deferred_beyond_exact"] if s == "kleene" else 0.0
                    ax.add_patch(th.FancyBboxPatch((x, yy - bh / 2), (v - extra) * scale, bh, fc=th.HELD, ec="none",
                                                   boxstyle=f"round,pad=0,rounding_size={th.RADIUS}", zorder=2))
                    if extra > 0.05:
                        ax.add_patch(th.FancyBboxPatch((x + (v - extra) * scale, yy - bh / 2), extra * scale, bh,
                                                       fc=th.HELD, alpha=0.38, ec="none", zorder=2,
                                                       boxstyle=f"round,pad=0,rounding_size={th.RADIUS}"))
                elif k == "missed":
                    ax.add_patch(th.FancyBboxPatch((x, yy - bh / 2), wv, bh, fc=th.MISSED, ec="none", zorder=2,
                                                   boxstyle=f"round,pad=0,rounding_size={th.RADIUS}"))
                else:
                    ax.add_patch(th.FancyBboxPatch((x, yy - bh / 2 + 0.006), wv, bh - 0.012, fc="white", ec=th.MISSED,
                                                   lw=th.THICK * 0.85, zorder=2,
                                                   boxstyle=f"round,pad=0,rounding_size={th.RADIUS}"))
                th.text(ax, x + wv + 0.05, yy, f"{v:.1f}", "note")
        y -= 4 * rh + gap
    _save(fig, "fig_fate")


# ---------------------------------------------------------------------- Fig. 4 (measured)
def fig_outcomes():
    """Two calm blocks (one per model), five aligned design rows, 100 unit marks per row in a 25 x 4
    grid filled column by column. Unnecessary requests: one hollow mark and the count per 100, shown
    only where it reaches 1 per 100."""
    D = outcomes_data()
    H = 2.55
    fig, ax = th.canvas(H)
    W = th.WIDTH
    top = H - LEGEND_Y
    th.legend(ax, LEGEND_X, top, ["requested", "held", "handed", "missed", "unnecessary"])
    p, g5 = th.MS + 0.012, 0.032
    bw = 25 * p + 4 * g5
    x1 = 1.02
    x2 = W - bw - 0.27
    rows_h = 4 * p
    y = top - 0.38
    for (tag, _, mname), x0 in zip(MODELS, (x1, x2)):
        th.text(ax, x0, y, mname, "label", bold=True)
    y -= 0.12
    kinds = ["requested", "held", "handed", "missed"]
    for role, key, name in OUTCOME_DESIGNS:
        yc = y - rows_h / 2
        th.text(ax, 0, yc, name, linespacing=1.15)
        for (tag, _, _), x0 in zip(MODELS, (x1, x2)):
            v = D[(tag, key)]
            seq = [k for k, n in zip(kinds, v["units"]) for _ in range(n)]
            for i, k in enumerate(seq):
                c, r = divmod(i, 4)
                th.mark(ax, x0 + p / 2 + c * p + (c // 5) * g5, y - p / 2 - r * p, k)
            if v["unnec_per100"] >= 1:
                xu = x0 + bw + 0.07
                th.mark(ax, xu + th.MS / 2, yc, "unnecessary")
                th.text(ax, xu + th.MS + 0.04, yc, f"{v['unnec_per100']:.0f}", "note")
        y -= rows_h + 0.11
    _save(fig, "fig_outcomes")


# ---------------------------------------------------------------------- Fig. 5 (measured)
def fig_trace():
    """One mark per wrong change. CasePath's marks hang from the rule that produced them through a light
    join (rule -> verifier -> document -> marks); Rules in context's marks attach only to a document."""
    D = trace_data()
    cp, rc, rv = D["cp"], D["rc"], D["verifier"]
    by_rule = {}
    for m in cp:
        by_rule.setdefault(m["rules"][0], []).append(m)
    rules = sorted(by_rule, key=lambda k: -len(by_rule[k]))
    rows = []
    for k in rules:
        docs = []
        for m in by_rule[k]:
            if m["doc"] not in docs:
                docs.append(m["doc"])
        rows += [(k, d) for d in docs]
    rows += [(None, d) for d in sorted({m["doc"] for m in rc} - {d for _, d in rows})]
    rowh = 0.20
    H = 0.62 + rowh * len(rows) + 0.10
    fig, ax = th.canvas(H)
    W = th.WIDTH
    top = H - LEGEND_Y
    th.legend(ax, LEGEND_X, top, ["missed", "unnecessary"])
    xr, xv, xd, xc, xi = 0.0, 1.62, 2.26, 3.30, 4.30
    pitch = th.MS + 0.014
    yh = top - 0.32
    th.text(ax, xr, yh, "Rule", bold=True)
    th.text(ax, xv, yh, "Verifier", bold=True)
    th.text(ax, xd, yh, "Document", bold=True)
    th.design(ax, xc + 0.04, yh, "code"); th.text(ax, xc + 0.12, yh, "CasePath", bold=True)
    th.design(ax, xi + 0.04, yh, "model"); th.text(ax, xi + 0.12, yh, "Rules in context", bold=True)
    y = yh - 0.25
    ys = {}
    prev = "start"
    for k, d in rows:
        ys[(k, d)] = y
        if k != prev:
            if k is None:
                th.text(ax, xr, y, "no rule", color=th.NEUTRAL)
            else:
                res = rv["results"][k]["result"]
                th.text(ax, xr, y, k[-3:], bold=True)
                th.text(ax, xr + 0.30, y, RULE_SHORT[k])
                th.text(ax, xv, y, "flagged" if res["verdict"] == "flag" else "passed", "note")
            prev = k
        if k is not None:   # the join: rule -> document
            yr = ys[(k, next(dd for kk, dd in rows if kk == k))]
            th.line(ax, [xv + 0.42, xd - 0.06], [yr, y], color=th.NEUTRAL)
        th.text(ax, xd, y, d)
        for col, lst in ((xc, [m for m in by_rule.get(k, []) if m["doc"] == d] if k else []),
                         (xi, [m for m in rc if m["doc"] == d])):
            lst = sorted(lst, key=lambda m: (m["sign"] == "-", m["run"]))
            for i, m in enumerate(lst):
                th.mark(ax, col + th.MS / 2 + i * pitch, y, "unnecessary" if m["sign"] == "+" else "missed")
        y -= rowh
    # the Rules-in-context errors that fall on the documents of rules 084 and 074
    hit = [(k, d) for k, d in rows if k in ("overlay_rule_084", "overlay_rule_074")]
    n_hit = sum(1 for m in rc for k, d in hit if m["doc"] == d)
    ya, yb = ys[hit[0]] + rowh / 2, ys[hit[-1]] - rowh / 2
    th.band(ax, xr - 0.04, yb + 0.01, W - xr + 0.04, ya - yb - 0.02)
    th.text(ax, xi, ya + rowh / 2, f"{n_hit} of {len(rc)}", "note")
    _save(fig, "fig_trace")


# ---------------------------------------------------------------------- Fig. 6 (measured)
def fig_models():
    """A dot plot per model: filled circle = CasePath, hollow = Rules in context, joined within a model
    only; thin intervals; the counted-once sensitivity as a small secondary tick."""
    M = models_data()
    H = 1.80
    fig, axc = th.canvas(H)
    W = th.WIDTH
    top = H - LEGEND_Y

    def tick(a, x, y):
        a.plot([x, x], [y - 0.045, y + 0.045], color=th.INK, lw=th.THICK, solid_capstyle="butt")

    th.legend(axc, LEGEND_X, top, [], extra=[(lambda a, x, y: th.design(a, x, y, "code"), "CasePath"),
                                      (lambda a, x, y: th.design(a, x, y, "model"), "Rules in context"),
                                      (tick, "each repeated error counted once")])
    ax = fig.add_axes([1.30 / W, 0.36 / H, (W - 1.50) / W, (H - 0.36 - 0.42) / H])
    ax.set_xlim(0, 1.6); ax.set_ylim(-0.62, 2.55)
    ys = {r["tag"]: 2 - i for i, r in enumerate(M)}
    for r in M:
        y0 = ys[r["tag"]]
        pos = {"CP": y0 + 0.13, "R": y0 - 0.13}
        ax.plot([r["CP"]["wpp"], r["R"]["wpp"]], [pos["CP"], pos["R"]], color=th.NEUTRAL, lw=th.THICK, zorder=1)
        for d in ("CP", "R"):
            v, yy = r[d], pos[d]
            right = v["wpp"]
            if v["ci"]:
                ax.plot(v["ci"], [yy, yy], color=th.INK, lw=th.THIN, zorder=2)
                right = v["ci"][1]
            if v["dedup"] is not None and abs(v["dedup"] - v["wpp"]) > 1e-9:
                ax.plot([v["dedup"]] * 2, [yy - 0.09, yy + 0.09], color=th.INK, lw=th.THICK, zorder=3,
                        solid_capstyle="butt")
            ax.scatter([v["wpp"]], [yy], s=34, marker="o", zorder=4, linewidths=th.THICK * 0.85, edgecolors=th.INK,
                       facecolors=th.INK if d == "CP" else "white")
            ax.text(v["wpp"], yy + (0.17 if d == "CP" else -0.17), f"{v['wpp']:.2f}", fontsize=th.NOTE, ha="center",
                    va="bottom" if d == "CP" else "top", color=th.INK)
    ax.set_yticks(list(ys.values()))
    ax.set_yticklabels([r["label"] + ("\noriginal study, 1 run" if r["single"] else "") for r in M], fontsize=th.LABEL,
                       linespacing=1.1)
    ax.set_xticks([0, 0.5, 1.0, 1.5])
    ax.set_xlabel("Wrong changes per pair, lower is better", fontsize=th.LABEL)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_linewidth(th.THIN)
    ax.tick_params(axis="y", length=0, pad=6)
    ax.tick_params(axis="x", length=3, width=th.THIN, labelsize=th.NOTE)
    _save(fig, "fig_models")


# ---------------------------------------------------------------------- Study 2 (measured)
S2_TEN = [("gpt-6-luna", [("CPv1", "code_v1"), ("CPv2p", "code"), ("B1v2p", "model")]),
          ("gpt-6.1-terra", [("CPv2p", "code"), ("B1v2p", "model")])]
S2_THEFT = [("gpt-6-luna", [("CPv2p", "code"), ("Rv2p", "model"), ("R", "model_orig")]),
            ("gpt-6.1-terra", [("CPv2p", "code"), ("Rv2p", "model"), ("R", "model_orig")])]


def study2_data():
    """Point values from analysis/study2_results.json. Theft intervals: 95% cluster bootstrap over the 9 changed
    facts (10,000 resamples, seeded as in study2.py) of each design's errors per pair, recomputed with study2.py's
    own scoring from the recorded plans (runs/v2); the point estimate is asserted equal to the results file."""
    import random as _r
    r = load("study2_results.json")
    import study2 as s2
    import theft_fresh
    on_pairs = [p for p in theft_fresh.pairs() if p["kind"] == "on"]
    T = theft_fresh.texts()
    theft = {}
    for model, designs in S2_THEFT:
        plans = s2.load_plans("theft", model)
        for d, _ in designs:
            key = f"{d}|{model}"
            rows = s2.theft_rows(T, on_pairs, plans[d])
            cl = s2.by_cluster(rows, "condition", lambda rs: sum(x["errors"] for x in rs) / len(rs))
            keys = sorted(cl)
            point = sum(cl.values()) / len(cl)
            assert abs(point - r["theft"][key]["errors_per_pair"]) < 1e-9, key
            g = _r.Random(f"{s2.SEED}|fig_study2|{key}")
            boot = sorted(sum(cl[g.choice(keys)] for _ in keys) / len(keys) for _ in range(s2.B))
            theft[key] = {"errors": point, "ci": [s2.quantile(boot, 0.025), s2.quantile(boot, 0.975)],
                          "dedup": r["theft"][key]["errors_dedup_per_pair"]}
    ten = {f"{d}|{m}": {"held": r["tenancy"][f"{d}|{m}"]["held_required_now_per_claim"],
                        "unsafe": r["tenancy"][f"{d}|{m}"]["strict_unsafe_per_claim"]}
           for m, ds in S2_TEN for d, _ in ds}
    return {"tenancy": ten, "theft": theft}


def fig_study2():
    """Measured. Left: tenancy (held required documents per claim; strict unsafe errors per claim). Right: theft
    (wrong + missed changes per pair, 95% interval, counted-once tick). Shape = design, colour = outcome counted."""
    D = study2_data()
    W, H = th.WIDTH, 2.10
    fig, base = th.canvas(H)
    top = H - LEGEND_Y
    th.legend(base, LEGEND_X, top, [], extra=[
        (lambda a, x, y: th.design(a, x, y, "code_v1"), "CasePath v1"),
        (lambda a, x, y: th.design(a, x, y, "code"), "CasePath v2"),
        (lambda a, x, y: th.design(a, x, y, "model"), "Rules in context"),
        (lambda a, x, y: th.design(a, x, y, "model_orig"), "same, original pack"),
        (lambda a, x, y: a.plot([x, x], [y - 0.045, y + 0.045], color=th.INK, lw=th.THICK, solid_capstyle="butt"),
         "repeated error counted once")])
    yb, hh = 0.42, H - 0.42 - 0.50

    def axis(x0, w, xlim, ticks, xlabel, nrows):
        ax = fig.add_axes([x0 / W, yb / H, w / W, hh / H])
        ax.set_xlim(*xlim); ax.set_ylim(nrows - 0.4, -0.6)
        ax.set_xticks(ticks); ax.set_yticks([])
        for sp in ("top", "right", "left"):
            ax.spines[sp].set_visible(False)
        ax.spines["bottom"].set_linewidth(th.THIN)
        ax.tick_params(axis="x", length=3, width=th.THIN, labelsize=th.NOTE, colors=th.INK)
        ax.set_xlabel(xlabel, fontsize=th.NOTE, labelpad=3)
        return ax

    def rows(groups):
        out, y = [], 0
        for m, ds in groups:
            for j, (d, mk) in enumerate(ds):
                out.append((y, m, d, mk, j == 0))
                y += 1
            y += 0.5
        return out, y - 0.5

    # ---- tenancy
    R1, n1 = rows(S2_TEN)
    a1 = axis(0.80, 1.05, (-0.1, 3.6), [0, 1, 2, 3], "held per claim, lower is better", n1)
    a2 = axis(2.02, 0.95, (0, 0.30), [0, 0.1, 0.2, 0.3], "strict unsafe per claim, lower is better", n1)
    for y, m, d, mk, first in R1:
        v = D["tenancy"][f"{d}|{m}"]
        th.design_scatter(a1, v["held"], y, mk, th.HELD)
        th.design_scatter(a2, v["unsafe"], y, mk, th.MISSED)
        a1.text(v["held"] + 0.16, y, f"{v['held']:.2f}", fontsize=th.NOTE, va="center", color=th.INK)
        a2.text(v["unsafe"] + 0.013, y, f"{v['unsafe']:.2f}", fontsize=th.NOTE, va="center", color=th.INK)
    for m, ds in S2_TEN:
        ys = [y for y, mm, *_ in R1 if mm == m]
        a1.text(-0.12, sum(ys) / len(ys), m, transform=a1.get_yaxis_transform(), fontsize=th.LABEL, ha="right",
                va="center", color=th.INK)
    th.text(base, 0.80, top - 0.30, "Tenancy, 72 claims", "label", bold=True)
    # ---- theft
    R2, n2 = rows(S2_THEFT)
    a3 = axis(3.95, 1.40, (0, 2.4), [0, 1, 2], "wrong + missed per pair, lower is better", n2)
    for y, m, d, mk, first in R2:
        v = D["theft"][f"{d}|{m}"]
        a3.plot(v["ci"], [y, y], color=th.MISSED, lw=th.THIN, zorder=2)
        if abs(v["dedup"] - v["errors"]) > 1e-9:
            a3.plot([v["dedup"]] * 2, [y - 0.32, y + 0.32], color=th.INK, lw=th.THICK, solid_capstyle="butt", zorder=3)
        th.design_scatter(a3, v["errors"], y, mk, th.MISSED)
        a3.text(v["ci"][1] + 0.06, y, f"{v['errors']:.2f}", fontsize=th.NOTE, va="center", color=th.INK)
    for m, ds in S2_THEFT:
        ys = [y for y, mm, *_ in R2 if mm == m]
        a3.text(-0.06, sum(ys) / len(ys), m, transform=a3.get_yaxis_transform(), fontsize=th.LABEL, ha="right",
                va="center", color=th.INK)
    th.text(base, 3.95, top - 0.30, "Theft, 36 changed-fact pairs", "label", bold=True)
    _save(fig, "fig_study2")


if __name__ == "__main__":
    args = _sys.argv[1:]
    if "--png" in args:
        PREVIEW = args[args.index("--png") + 1]
        Path(PREVIEW).mkdir(parents=True, exist_ok=True)
    if "--legacy" in args:
        fig_tenancy(); fig_theft(); fig_propagation()
    only = [a for a in args if a.startswith("fig_")]
    for f in only or ["fig_hero", "fig_reconverge", "fig_fate", "fig_outcomes", "fig_trace", "fig_models", "fig_knowledge", "fig_study2"]:
        if f in globals():
            globals()[f]()
    print("figures written to", FIG)
