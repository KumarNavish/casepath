"""Figure 7, revision 2: the price. Reads f7_data.json only.

    python3 -I f7_plot.py    # f7.{png,svg,pdf} (kept: a), f7_b.png (rejected: strips of the median file)

Left: errors per file against USD per file (log), four points: CasePath (core) and the prompt that may hold on each
model (circle: cost-efficient, square: frontier); one arrow per model from the prompt to CasePath.
Right (a): the 96 claims as a 4 x 24 grid per design (cost-efficient model), same claim at the same place in both
grids (claim-id order); ink filled = the three stored runs gave the same checklist, ink outline = they did not.
Right (b, rejected): the claim at each design's median number of differing lines, its three stored checklists as
strips (Figure 1's strip). The median is 0 for both, so the strips are identical.
"""
import json
import sys
from itertools import combinations
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "common"))
import style as S  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

J = json.loads((HERE / "f7_data.json").read_text())
D = {d["key"]: d for d in J["designs"]}
PAIRS = [("cost-efficient", "hold_prompt", "casepath_checklist", "o"),
         ("frontier", "hold_prompt_frontier", "casepath_frontier_checklist", "s")]
W, H = 5.5, 2.55


def same_flags(key):
    """Per claim in claim-id order: True when the three stored runs gave the same checklist (f7_data.json)."""
    return D[key]["repeat"]["identical_by_claim_id_order"]


def scatter(fig):
    ax = fig.add_axes([0.095, 0.22, 0.40, 0.70])
    ax.set_xscale("log")
    ax.set_xlim(4e-4, 4e-2)
    ax.set_xticks([1e-3, 1e-2], ["0.001", "0.01"])
    ax.minorticks_off()
    ax.set_ylim(0, 1.0)
    ax.set_yticks([0, 0.5, 1.0], ["0", "0.5", "1"])
    for model, kp, kc, mk in PAIRS:
        p, c = D[kp], D[kc]
        ax.annotate("", xy=(c["usd_per_file"], c["all_dev_per_file"]), xytext=(p["usd_per_file"], p["all_dev_per_file"]),
                    arrowprops=dict(arrowstyle="-|>,head_length=0.5,head_width=0.25", color=S.INK, lw=1.0,
                                    shrinkA=5, shrinkB=5))
        for d in (p, c):
            ax.plot(d["usd_per_file"], d["all_dev_per_file"], mk, ms=6, color=S.INK, zorder=3)
        if model == "cost-efficient":
            ax.annotate("prompt that may hold", (p["usd_per_file"], p["all_dev_per_file"]), xytext=(-4, 10),
                        textcoords="offset points", fontsize=S.SIZE_LABEL, ha="left", va="center")
            ax.annotate("CasePath", (c["usd_per_file"], c["all_dev_per_file"]), xytext=(7, 0),
                        textcoords="offset points", fontsize=S.SIZE_LABEL, ha="left", va="center", fontweight="semibold")
        xm = (p["usd_per_file"] * c["usd_per_file"]) ** 0.5
        ym = (p["all_dev_per_file"] + c["all_dev_per_file"]) / 2
        ax.text(xm, ym + (-0.19 if model == "cost-efficient" else -0.13), model, ha="center", va="center",
                fontsize=S.SIZE_LABEL)
    ax.set_xlabel("USD per file")
    ax.set_ylabel("errors per file")
    return ax


def grids(fig):
    ax = fig.add_axes([0.56, 0, 0.44, 1])
    w = 0.44 * W
    ax.set_xlim(0, w), ax.set_ylim(0, H), ax.axis("off")
    x0 = 0.20
    for i, (key, name) in enumerate((("casepath_checklist", "CasePath"), ("hold_prompt", "prompt that may hold"))):
        flags = same_flags(key)
        top = H - 0.55 - i * 0.90
        ax.text(x0, top + 0.13, name, fontsize=S.SIZE_LABEL, fontweight="semibold" if i == 0 else "normal", va="center")
        for k, same in enumerate(flags):
            col, row = divmod(k, 4)
            cx, cy = x0 + col * S.PITCH + S.MARK / 2, top - row * S.PITCH - S.MARK / 2
            if same:
                S.checklist_mark(ax, cx, cy, S.INK)
            else:
                S.checklist_mark(ax, cx, cy, "left", outline=S.INK)
        r = D[key]["repeat"]
        ax.text(x0 + 24 * S.PITCH + 0.08, top - 2 * S.PITCH, f"{r['identical_all_runs']}/{r['claims']}",
                fontsize=S.SIZE_NUMBER, va="center")
        assert sum(flags) == r["identical_all_runs"]
    yl = H - 0.55 - 0.90 - 4 * S.PITCH - 0.30
    S.legend(ax, x0, yl, [(("ink", None), "same checklist in all three runs")])
    S.legend(ax, x0, yl - 0.16, [(("ink-outline", None), "not the same")])
    return ax


def strips(fig):
    ax = fig.add_axes([0.56, 0, 0.44, 1])
    w = 0.44 * W
    ax.set_xlim(0, w), ax.set_ylim(0, H), ax.axis("off")
    st = {"request": "requested", "hold": "held", "neither": "left"}
    for i, (key, name) in enumerate((("casepath_checklist", "CasePath"), ("hold_prompt", "prompt that may hold"))):
        s = J["strips"][key]
        top = H - 0.55 - i * 0.90
        ax.text(0.20, top + 0.13, name, fontsize=S.SIZE_LABEL, va="center")
        for r, run in enumerate(s["runs"]):
            for k, v in enumerate(run):
                S.checklist_mark(ax, 0.20 + k * S.PITCH * 1.2 + S.MARK / 2, top - r * S.PITCH * 1.2 - S.MARK / 2, st[v])
    return ax


def draw(kind):
    fig = plt.figure(figsize=(W, H))
    scatter(fig)
    grids(fig) if kind == "a" else strips(fig)
    return fig


if __name__ == "__main__":
    S.save(draw("a"), HERE, "f7")
    S.save_png(draw("b"), HERE, "f7_b")
    for model, kp, kc, _ in PAIRS:
        p, c = D[kp], D[kc]
        print(model, "prompt", round(p["usd_per_file"], 5), round(p["all_dev_per_file"], 3), "-> CasePath",
              round(c["usd_per_file"], 5), round(c["all_dev_per_file"], 3), "cost x", round(c["usd_per_file"] / p["usd_per_file"], 1))
