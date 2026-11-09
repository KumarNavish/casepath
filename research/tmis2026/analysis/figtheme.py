"""One visual theme for the six TMIS figures. Every figure draws only through this module.

Colour: four outcome hues with fixed roles (validated as a categorical set with the dataviz
validator: lightness band, chroma floor, CVD and normal-vision separation pass for all pairs on
white; the held ochre and handed-over green are below 3:1 contrast, so they never carry text and always appears with a
label or a shape), one ink for text and structure, one light neutral for inactive elements and
rules, and one pale accent tint for "the thing to look at". Unsafe errors share the vermilion and
differ by shape: a cross is a missed document, a hollow square an unnecessary request.
Designs, where a figure must tell them apart, are told apart by fill, never by hue:
filled circle = code executes the rules (CasePath), hollow circle = model applies the rules.

Type: Linux Biolinum O (sits beside Libertine body text), three sizes, one emphasis weight, no
italics. Geometry: two line weights, one corner radius, one mark size, a 1/16-inch spacing grid.
"""
from pathlib import Path

import matplotlib
matplotlib.use("pdf")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle
from matplotlib.backends.backend_agg import RendererAgg

# ---------------------------------------------------------------- colour (roles, nothing else)
REQUESTED = "#33679f"   # a required document requested now
HELD = "#dba23a"        # held behind a question; also the colour of an unresolved value
HANDED = "#45b096"      # handed over to a person (whole claim)
MISSED = "#c4503a"      # missed (cross); unnecessary request (hollow square) shares the hue
INK = "#262626"         # all text and structure
NEUTRAL = "#cfccc6"     # inactive elements, not-needed documents, rules
ACCENT = "#f4efe4"      # pale tint behind the one thing to look at
PALETTE = [REQUESTED, HELD, HANDED, MISSED]

# ---------------------------------------------------------------- type
FAMILY = "Linux Biolinum O"
TITLE, LABEL, NOTE = 8.0, 7.0, 6.3      # pt at print width
BOLD = "bold"                           # the only emphasis

# ---------------------------------------------------------------- geometry
WIDTH = 5.4                             # in; ACM single-column text width ~5.5 in
G = 1 / 16                              # spacing grid, in
THIN, THICK = 0.5, 1.2                  # pt
MS = 0.058                              # unit/document mark size, in
RADIUS = 0.012                          # corner radius of marks and bands, in
PITCH = MS + 0.014                      # spacing of unit marks

ORDER = ["requested", "held", "handed", "missed", "unnecessary", "inactive"]
NAMES = {"requested": "requested", "held": "held", "handed": "handed over", "missed": "missed",
         "unnecessary": "unnecessary request", "inactive": "not needed"}

_fonts_ready = False


def setup():
    global _fonts_ready
    if not _fonts_ready:
        for f in font_manager.findSystemFonts():
            if "Biolinum" in f or "Libertine" in f:
                font_manager.fontManager.addfont(f)
        _fonts_ready = True
    plt.rcParams.update({"font.family": FAMILY, "font.size": LABEL, "pdf.fonttype": 42, "axes.linewidth": THIN,
                         "text.color": INK, "axes.edgecolor": INK, "xtick.color": INK, "ytick.color": INK,
                         "axes.labelcolor": INK, "xtick.labelsize": LABEL, "ytick.labelsize": LABEL,
                         "axes.labelsize": LABEL, "xtick.major.width": THIN, "ytick.major.width": THIN})


def canvas(h, w=WIDTH):
    """A figure whose data coordinates are inches from the lower-left corner."""
    setup()
    fig = plt.figure(figsize=(w, h))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, w); ax.set_ylim(0, h); ax.axis("off")
    return fig, ax


def save(fig, path_pdf, preview_dir=None):
    fig.savefig(path_pdf)
    if preview_dir:
        fig.savefig(Path(preview_dir) / (Path(path_pdf).stem + ".png"), dpi=300)
    plt.close(fig)


SIZES = {"title": TITLE, "label": LABEL, "note": NOTE}


def text(ax, x, y, s, role="label", color=INK, ha="left", va="center", bold=False, **kw):
    return ax.text(x, y, s, fontsize=SIZES[role], color=color, ha=ha, va=va, fontweight=BOLD if bold else "normal",
                   **kw)


def width(ax, s, role="label", bold=False):
    fig = ax.figure
    t = ax.text(0, 0, s, fontsize=SIZES[role], fontweight=BOLD if bold else "normal")
    w = t.get_window_extent(renderer=RendererAgg(*(fig.get_size_inches() * fig.dpi), fig.dpi)).width / fig.dpi
    t.remove()
    return w


def line(ax, xs, ys, weight="thin", color=INK, **kw):
    return ax.plot(xs, ys, color=color, lw=THIN if weight == "thin" else THICK, solid_capstyle="round", **kw)


def band(ax, x, y, w, h):
    """The accent: a pale tint behind the one thing to look at."""
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={RADIUS * 3}", fc=ACCENT,
                                ec="none", zorder=0))


def mark(ax, x, y, kind, s=MS):
    """One document in an outcome, centred at (x, y)."""
    h = s / 2
    if kind == "missed":
        d = h * 0.92
        for a, b in (((x - d, y - d), (x + d, y + d)), ((x - d, y + d), (x + d, y - d))):
            ax.plot([a[0], b[0]], [a[1], b[1]], color=MISSED, lw=THICK, solid_capstyle="round", zorder=3)
        return
    if kind == "unnecessary":
        k = s - 0.012
        ax.add_patch(FancyBboxPatch((x - k / 2, y - k / 2), k, k, boxstyle=f"round,pad=0,rounding_size={RADIUS}",
                                    fc="white", ec=MISSED, lw=THICK * 0.85, zorder=3))
        return
    fc = {"requested": REQUESTED, "held": HELD, "handed": HANDED, "inactive": NEUTRAL}[kind]
    ax.add_patch(FancyBboxPatch((x - h, y - h), s, s, boxstyle=f"round,pad=0,rounding_size={RADIUS}", fc=fc, ec="none",
                                zorder=3))


def doc(ax, x, y, name, kind, anchor="left", color=None):
    """A named document: its outcome mark followed (or preceded) by its name. Returns the far x."""
    gap = 0.045
    c = color or (NEUTRAL if kind == "inactive" else INK)
    if anchor == "left":
        mark(ax, x + MS / 2, y, kind)
        text(ax, x + MS + gap, y, name, "label", c)
        return x + MS + gap + width(ax, name)
    mark(ax, x - MS / 2, y, kind)
    text(ax, x - MS - gap, y, name, "label", c, ha="right")
    return x - MS - gap - width(ax, name)


def node(ax, x, y, kind, r=0.034):
    """A process step: active (ink), unresolved (held), inactive (neutral ring)."""
    fc, ec = {"active": (INK, INK), "unresolved": (HELD, HELD), "inactive": ("white", NEUTRAL)}[kind]
    ax.add_patch(Circle((x, y), r, fc=fc, ec=ec, lw=THICK if kind == "inactive" else THIN, zorder=3))


def design(ax, x, y, which, r=0.036, color=INK):
    """Design marker: filled circle = code executes the rules; hollow circle = model applies them."""
    ax.add_patch(Circle((x, y), r, fc=color if which == "code" else "white", ec=color, lw=THICK * 0.85, zorder=4))


def legend(ax, x, y, kinds, extra=()):
    """The one legend grammar: a single row, outcomes in the fixed ORDER, swatch = the mark itself,
    labels at label size; `extra` appends (drawer, label) pairs for non-outcome encodings."""
    for k in [k for k in ORDER if k in kinds]:
        mark(ax, x + MS / 2, y, k)
        text(ax, x + MS + 0.05, y, NAMES[k])
        x += MS + 0.05 + width(ax, NAMES[k]) + 0.20
    for draw, lab in extra:
        draw(ax, x + 0.04, y)
        text(ax, x + 0.11, y, lab)
        x += 0.11 + width(ax, lab) + 0.20
    return x
