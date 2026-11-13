"""The one visual system of FIGURE_BRIEF.md (same values in f4, f5, f7)."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

PAPER = "#FBF8F1"
INK = "#1F2A44"
SAND = "#C9BFA8"
TEAL = "#008571"     # request now
AMBER = "#D9962B"    # open fact / held request with its question
RUST = "#B5482F"     # requested too early (error)
INDIGO = "#4B4A9C"   # dropped (error)
BLUE = "#4A8FD6"     # a model's reading

plt.rcParams.update({
    "font.family": "Inter", "font.size": 7.5, "axes.edgecolor": INK, "axes.labelcolor": INK,
    "xtick.color": INK, "ytick.color": INK, "text.color": INK, "axes.linewidth": 0.6,
    "xtick.major.width": 0.6, "ytick.major.width": 0.6, "xtick.labelsize": 7, "ytick.labelsize": 7,
    "svg.fonttype": "none", "pdf.fonttype": 42, "figure.dpi": 100, "savefig.dpi": 300,
    "axes.spines.top": False, "axes.spines.right": False,
})


def save(fig, stem, folder, png_only=False):
    fig.savefig(folder / f"{stem}.png", facecolor=PAPER, dpi=300)
    if not png_only:
        fig.savefig(folder / f"{stem}.svg", facecolor="white")
        fig.savefig(folder / f"{stem}.pdf", facecolor="white")
