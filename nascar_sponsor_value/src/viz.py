"""Shared chart style for scripts and notebooks.

Layout follows the seaborn-on-FiveThirtyEight look: tinted plot panels on a white
page, centered regular-weight titles, visible grid, no spines, thick lines, and
ordered series drawn as a light -> dark ramp of one family (see ordinal()).
A source line sits at the bottom.
Colors come from a muted plum / rose / cream palette (593E51, 7B4C5B, A26871,
CF9294, E9D69F): plum = the field, gold = the No. 44, rose = a third series,
pale rose = de-emphasized context. The cream is too light to read as a mark on
the light ground, so the No. 44 uses a deeper gold from the same family. Checked
with a CVD validator: every pair of series colors stays distinguishable under
protanopia, deuteranopia and normal vision. Gold sits below 3:1 contrast on the
ground, so No. 44 marks are always direct-labeled. Text uses ink colors, never
series colors.
"""
import matplotlib
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

FIELD = "#593e51"      # categorical slot 1: plum
NY = "#b8913c"         # categorical slot 2 (the No. 44): gold, deepened from the palette's E9D69F
THIRD = "#a26871"      # categorical slot 3: rose
INK = "#2e2230"
INK_2 = "#6e5c66"
GRID = "#ddd3c8"
SURFACE = "#ffffff"      # page
PANEL = "#f4efe8"        # plot area
CONTEXT = "#cf9294"    # de-emphasized marks: pale rose

# Sequential ramp for heatmaps: the palette itself, light -> dark (lightness is monotone).
SEQ = LinearSegmentedColormap.from_list("palette_seq", ["#e9d69f", "#cf9294", "#a26871", "#7b4c5b", "#593e51"])


TRACK_SHORT = {"Circuit of The Americas": "COTA", "World Wide Technology Raceway": "Gateway",
               "Autódromo Hermanos Rodríguez": "Mexico City", "Charlotte Motor Speedway Road Course": "Charlotte Roval",
               "Chicago Street Race": "Chicago", "Homestead-Miami Speedway": "Homestead"}


def short_track(name):
    """Readable short track name for axis labels: 'Las Vegas Motor Speedway' -> 'Las Vegas'."""
    if name in TRACK_SHORT:
        return TRACK_SHORT[name]
    for suffix in (" Motor Speedway", " International Speedway", " Superspeedway", " Speedway", " Raceway", " International"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def use_style():
    plt.style.use("fivethirtyeight")
    plt.rcParams.update({
        "figure.dpi": 80, "savefig.dpi": 160, "savefig.bbox": "tight", "savefig.pad_inches": 0.25,
        "figure.facecolor": SURFACE, "axes.facecolor": PANEL, "savefig.facecolor": SURFACE,
        "font.family": "DejaVu Sans", "font.size": 11, "axes.labelsize": 11, "axes.labelcolor": INK_2,
        "axes.titlesize": 14, "axes.titleweight": "normal", "axes.titlelocation": "center", "axes.titlecolor": INK,
        "xtick.labelsize": 10, "ytick.labelsize": 10, "xtick.color": INK_2, "ytick.color": INK_2,
        "axes.edgecolor": PANEL, "grid.color": GRID, "grid.linewidth": 1.0, "axes.grid": True, "axes.axisbelow": True,
        "lines.linewidth": 3, "legend.frameon": True, "legend.facecolor": PANEL, "legend.edgecolor": GRID, "legend.framealpha": 0.9,
        "legend.fontsize": 10, "legend.title_fontsize": 10, "legend.labelcolor": INK,
        "axes.prop_cycle": matplotlib.cycler(color=[FIELD, NY, THIRD]),
    })
    # In notebooks, draw charts at 2x pixels but display them at figure.dpi size,
    # so text stays sharp on high-resolution screens. No-op outside IPython.
    try:
        from matplotlib_inline.backend_inline import set_matplotlib_formats
        set_matplotlib_formats("retina")
    except Exception:
        pass


def ordinal(n, lo=0.25, hi=1.0):
    """n colors stepped light -> dark along SEQ, for series with a natural order
    (a parameter swept low -> high). The lightest step starts past the cream so
    it still reads on the panel."""
    return [SEQ(x) for x in np.linspace(lo, hi, n)]


def headline(fig, title, subtitle=None):
    """Regular-weight headline and muted subtitle, centered over the chart (tick labels included)."""
    fig.subplots_adjust(top=0.80 if subtitle else 0.86)
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    boxes = [ax.get_tightbbox(r).transformed(fig.transFigure.inverted()) for ax in fig.axes]
    xc = (min(b.x0 for b in boxes) + max(b.x1 for b in boxes)) / 2
    fig.text(xc, 0.97, title, ha="center", va="top", fontsize=17, color=INK)
    if subtitle:
        fig.text(xc, 0.905, subtitle, ha="center", va="top", fontsize=11.5, color=INK_2)


def source(fig, text=None):
    """Uppercase source line placed just below the lowest element of the figure.
    Charts built from NASCAR's race data carry no footer, so with no text this does nothing."""
    if not text:
        return
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    boxes = [ax.get_tightbbox(r).transformed(fig.transFigure.inverted()) for ax in fig.axes]
    x0 = min(0.01, min(b.x0 for b in boxes))
    y0 = min(0.0, min(b.y0 for b in boxes))
    fig.text(x0, y0 - 0.025, text.upper(), ha="left", va="top", fontsize=8, color=INK_2)


def money_axis(ax, axis="y", unit="K"):
    div = 1e3 if unit == "K" else 1e6
    f = matplotlib.ticker.FuncFormatter(lambda x, _: f"${x/div:,.0f}{unit}" if unit == "K" else f"${x/div:,.1f}M")
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(f)
