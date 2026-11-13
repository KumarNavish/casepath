"""Figure 7 drawing from f7_data.json.

    python3 -I f7_plot.py    # f7.svg/.pdf/.png (kept: a), f7_b.png (rejected: aligned rows)

a: left, error per file against cost per file (log), one mark per design and model, direct labels; thin ink lines
   are the stored budget curves (F4). Right, per design with three stored runs: share of the 96 claims whose
   checklist is identical in all three runs (dot) and the mean number of checklist lines that differ between two
   runs (dot), rows in the order of Figures 4 and 5.
b: one row per design, four aligned dot columns (error, cost, identical share, lines differing).
Marker shape: circle = cost-efficient model, square = frontier model. Ink only: no state colour is involved.
"""
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "f4"))
from theme import INK, PAPER, SAND, plt, save  # noqa: E402

J = json.loads((HERE / "f7_data.json").read_text())
DS = J["designs"]
TAG = {"cost-efficient": "c", "frontier": "f"}


SHORT = {"CasePath, full": "CasePath, full", "CasePath, checklist only": "CasePath core",
         "Self-consistency (5 votes)": "Self-consistency"}


def nm(d):
    return f"{SHORT.get(d['name'], d['name'])} ({TAG[d['model']]})"


def mk(d):
    return "o" if d["model"] == "cost-efficient" else "s"


FOCUS = {"casepath_checklist", "casepath_frontier_checklist", "hold_prompt", "hold_prompt_frontier"}


def bold(d):
    return d["key"] in FOCUS


# label offsets (points), placed by eye at print size; a leader is drawn when the label is far from its mark
OFF = {"casepath_checklist": (-14, 26), "casepath_frontier_checklist": (7, 0), "casepath": (0, 12),
       "hold_prompt_frontier": (12, -16), "mer_hold_frontier": (12, -28), "hold_prompt": (6, 0),
       "ric_frontier": (6, 0), "ric": (6, -8), "self_consistency": (0, 9), "model_executes_rules": (6, 0),
       "react": (6, 0)}
HA = {"casepath_checklist": "right", "casepath": "center", "self_consistency": "center"}


def scatter(ax):
    sc = J["budget_self_consistency"]
    ax.plot([x["usd_per_file"] for x in sc], [x["all_dev_per_file"] for x in sc], color=INK, lw=0.6, zorder=2)
    for x in sc:
        ax.plot(x["usd_per_file"], x["all_dev_per_file"], marker="o", ms=1.6, color=INK, zorder=2)
    ax.annotate("1 to 15 samples", (sc[-1]["usd_per_file"], sc[-1]["all_dev_per_file"]), xytext=(5, 0),
                textcoords="offset points", fontsize=7, ha="left", va="center")
    rd = J["readings_casepath_checklist"]
    ax.plot([x["usd_per_file"] for x in rd], [x["all_dev_per_file"] for x in rd], color=INK, lw=0.6, zorder=2)
    for x in rd:
        ax.plot(x["usd_per_file"], x["all_dev_per_file"], marker="o", ms=1.6, color=INK, zorder=2)
    ax.annotate("1 reading", (rd[0]["usd_per_file"], rd[0]["all_dev_per_file"]), xytext=(-4, 0),
                textcoords="offset points", fontsize=7, ha="right", va="center")
    ax.annotate("3", (rd[-1]["usd_per_file"], rd[-1]["all_dev_per_file"]), xytext=(5, -6),
                textcoords="offset points", fontsize=7, ha="left", va="center")
    for d in DS:
        ax.plot(d["usd_per_file"], d["all_dev_per_file"], marker=mk(d), ms=5.6 if bold(d) else 3.6, color=INK,
                mec=PAPER, mew=0.6, zorder=4)
        dx, dy = OFF.get(d["key"], (5, 0))
        ax.annotate(nm(d), (d["usd_per_file"], d["all_dev_per_file"]), xytext=(dx, dy), textcoords="offset points",
                    fontsize=7, va="center", ha=HA.get(d["key"], "left"), fontweight="semibold" if bold(d) else "normal",
                    arrowprops=dict(arrowstyle="-", color=SAND, lw=0.5, shrinkA=4, shrinkB=3) if abs(dy) > 15 else None)
    ax.set_xscale("log")
    ax.set_xlim(4.5e-4, 8e-2)
    ax.set_xticks([0.001, 0.003, 0.01, 0.03], ["0.001", "0.003", "0.01", "0.03"])
    ax.minorticks_off()
    ax.set_ylim(0, 2.55)
    ax.set_xlabel("cost per file, USD (ledgers; log scale)", fontsize=7.5)
    ax.set_ylabel("errors per file (all deviations)", fontsize=7.5)
    ax.set_facecolor(PAPER)


def repeat(axl, axr):
    R = [d for d in DS if "repeat" in d]
    ys = list(range(len(R)))[::-1]
    for d, y in zip(R, ys):
        r = d["repeat"]
        axl.plot([0, 100 * r["identical_share"]], [y, y], color=SAND, lw=0.6, zorder=1)
        axl.plot(100 * r["identical_share"], y, marker=mk(d), ms=4.5 if bold(d) else 3.8, color=INK, mec=PAPER, mew=0.5)
        axr.plot([0, 100 * r["share_lines_differing_per_pair"]], [y, y], color=SAND, lw=0.6, zorder=1)
        axr.plot(100 * r["share_lines_differing_per_pair"], y, marker=mk(d), ms=4.5 if bold(d) else 3.8, color=INK, mec=PAPER, mew=0.5)
    axl.set_yticks(ys, [nm(d) for d in R], fontsize=7)
    for t, d in zip(axl.get_yticklabels(), R):
        if bold(d):
            t.set_fontweight("semibold")
    axr.set_yticks(ys, [""] * len(R))
    axl.set_xlim(0, 100), axr.set_xlim(0, 20)
    axl.set_xticks([0, 50, 100])
    axr.set_xticks([0, 10, 20])
    axl.set_xlabel("same checklist\nin 3 runs, %", fontsize=7)
    axr.set_xlabel("lines that differ\nbetween 2 runs, %", fontsize=7)
    for a in (axl, axr):
        a.set_ylim(-0.6, len(R) - 0.4)
        a.set_facecolor(PAPER)
        a.tick_params(length=2.5, pad=1.5)
    axl.text(-2, len(R) - 0.25, "3 runs per file; 10 not yet run", fontsize=7, style="italic", va="bottom", ha="right")


def draw_a():
    fig = plt.figure(figsize=(5.5, 3.5))
    ax = fig.add_axes([0.08, 0.20, 0.44, 0.76])
    scatter(ax)
    axl = fig.add_axes([0.725, 0.26, 0.115, 0.62])
    axr = fig.add_axes([0.87, 0.26, 0.115, 0.62])
    repeat(axl, axr)
    fig.text(0.08, 0.02, "circle: cost-efficient model (c)    square: frontier model (f)    "
             "thin line: stored budget curve", fontsize=7)
    return fig


def draw_b():
    fig, axs = plt.subplots(1, 4, figsize=(5.5, 3.0), sharey=True)
    ys = list(range(len(DS)))[::-1]
    for d, y in zip(DS, ys):
        axs[0].plot(d["all_dev_per_file"], y, marker=mk(d), color=INK)
        axs[1].plot(d["usd_per_file"], y, marker=mk(d), color=INK)
        if "repeat" in d:
            axs[2].plot(100 * d["repeat"]["identical_share"], y, marker=mk(d), color=INK)
            axs[3].plot(d["repeat"]["mean_lines_differing_per_pair"], y, marker=mk(d), color=INK)
    axs[1].set_xscale("log")
    axs[0].set_yticks(ys, [nm(d) for d in DS], fontsize=7)
    for a, t in zip(axs, ["errors per file", "USD per file", "same in 3 runs, %", "lines differing"]):
        a.set_title(t, fontsize=7.5, loc="left")
        a.set_facecolor(PAPER)
    fig.subplots_adjust(left=0.32, right=0.98, bottom=0.1, top=0.9, wspace=0.25)
    return fig


if __name__ == "__main__":
    save(draw_a(), "f7", HERE)
    save(draw_b(), "f7_b", HERE, png_only=True)
    print("ok")
