"""
Atlas equity research PDF renderer — NFLX
High-quality, bank-style layout using ReportLab + Matplotlib.
"""

import json, math, os, io
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import numpy as np

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image as RLImage, HRFlowable, KeepTogether, PageBreak
)
from reportlab.platypus.flowables import Flowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib.colors import HexColor

# ── Palette ──────────────────────────────────────────────────────────────────
INK       = HexColor("#0D1117")   # near-black body text
SLATE     = HexColor("#1C2B3A")   # dark navy — headers, dividers
ACCENT    = HexColor("#C8102E")   # deep red — SELL rating, accents
GOLD      = HexColor("#B8860B")   # dark gold — highlights
MUTED     = HexColor("#5A6474")   # mid-grey — captions, secondary
RULE      = HexColor("#D4D8DE")   # light grey — horizontal rules
CREAM     = HexColor("#F8F6F0")   # warm off-white — table rows
WHITE     = HexColor("#FFFFFF")
NAVY_LIGHT = HexColor("#EEF2F7")  # section header bg
GREEN     = HexColor("#1A6B3C")   # bull
BEAR_RED  = HexColor("#A01020")   # bear

# chart palette
C_BLUE    = "#1C2B3A"
C_RED     = "#C8102E"
C_GOLD    = "#B8860B"
C_GREY    = "#8A94A0"
C_GREEN   = "#1A6B3C"
C_LIGHT   = "#EEF2F7"

W, H = A4
MARGIN_L = 18*mm
MARGIN_R = 18*mm
MARGIN_T = 16*mm
MARGIN_B = 16*mm
CONTENT_W = W - MARGIN_L - MARGIN_R

# ── Load data ─────────────────────────────────────────────────────────────────
BASE = Path(__file__).parent.parent / "output" / "NFLX"
with open(BASE / "NFLX.json") as f:
    R = json.load(f)
with open(BASE / "NFLX_headline.json") as f:
    HL = json.load(f)
with open(BASE / "NFLX_valuation.json") as f:
    VAL = json.load(f)

# ── Font setup ────────────────────────────────────────────────────────────────
def register_fonts():
    """Use built-in Helvetica family — clean, professional, universally available."""
    pass  # reportlab ships Helvetica; we'll use it throughout

register_fonts()

# ── Style factory ─────────────────────────────────────────────────────────────
def S(name="body", **kw):
    base = {
        "fontName": "Helvetica",
        "fontSize": 9,
        "leading": 13,
        "textColor": INK,
        "alignment": TA_JUSTIFY,
        "spaceAfter": 0,
        "spaceBefore": 0,
    }
    presets = {
        "h1": {"fontName": "Helvetica-Bold", "fontSize": 18, "leading": 22, "textColor": SLATE, "alignment": TA_LEFT, "spaceBefore": 0, "spaceAfter": 2},
        "h2": {"fontName": "Helvetica-Bold", "fontSize": 11, "leading": 14, "textColor": WHITE, "alignment": TA_LEFT, "spaceBefore": 6, "spaceAfter": 3},
        "h3": {"fontName": "Helvetica-Bold", "fontSize": 9.5, "leading": 12, "textColor": SLATE, "alignment": TA_LEFT, "spaceBefore": 4, "spaceAfter": 2},
        "body": {"fontName": "Helvetica", "fontSize": 8.5, "leading": 12.5, "textColor": INK, "alignment": TA_JUSTIFY, "spaceAfter": 4},
        "body_sm": {"fontName": "Helvetica", "fontSize": 7.5, "leading": 11, "textColor": MUTED, "alignment": TA_LEFT},
        "caption": {"fontName": "Helvetica-Oblique", "fontSize": 7, "leading": 9.5, "textColor": MUTED, "alignment": TA_CENTER},
        "label": {"fontName": "Helvetica-Bold", "fontSize": 7.5, "leading": 10, "textColor": MUTED, "alignment": TA_LEFT},
        "number": {"fontName": "Helvetica-Bold", "fontSize": 14, "leading": 17, "textColor": SLATE, "alignment": TA_CENTER},
        "number_sm": {"fontName": "Helvetica-Bold", "fontSize": 10, "leading": 13, "textColor": SLATE, "alignment": TA_CENTER},
        "tag_sell": {"fontName": "Helvetica-Bold", "fontSize": 8.5, "leading": 11, "textColor": WHITE, "alignment": TA_CENTER},
        "thesis": {"fontName": "Helvetica-Oblique", "fontSize": 8.5, "leading": 13, "textColor": SLATE, "alignment": TA_JUSTIFY},
        "verdict": {"fontName": "Helvetica-Bold", "fontSize": 8, "leading": 11, "textColor": INK, "alignment": TA_LEFT},
        "cell": {"fontName": "Helvetica", "fontSize": 7.5, "leading": 10.5, "textColor": INK, "alignment": TA_LEFT},
        "cell_bold": {"fontName": "Helvetica-Bold", "fontSize": 7.5, "leading": 10.5, "textColor": INK, "alignment": TA_LEFT},
        "cell_r": {"fontName": "Helvetica", "fontSize": 7.5, "leading": 10.5, "textColor": INK, "alignment": TA_RIGHT},
        "cell_bold_r": {"fontName": "Helvetica-Bold", "fontSize": 7.5, "leading": 10.5, "textColor": INK, "alignment": TA_RIGHT},
        "footer": {"fontName": "Helvetica", "fontSize": 6.5, "leading": 9, "textColor": MUTED, "alignment": TA_CENTER},
    }
    cfg = {**base, **presets.get(name, {}), **kw}
    return ParagraphStyle(name=name + str(id(kw)), **cfg)

def P(text, style="body", **kw):
    return Paragraph(str(text), S(style, **kw))

def SP(h=4):
    return Spacer(1, h*mm)

def HR(color=RULE, thickness=0.5):
    return HRFlowable(width="100%", thickness=thickness, color=color, spaceAfter=3, spaceBefore=3)

# ── Section header ─────────────────────────────────────────────────────────────
class SectionHeader(Flowable):
    def __init__(self, text, width=CONTENT_W):
        super().__init__()
        self.text = text
        self.width = width
        self.height = 7*mm

    def draw(self):
        c = self.canv
        c.setFillColor(SLATE)
        c.rect(0, 0, self.width, self.height, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(4*mm, 2.2*mm, self.text.upper())

# ── Chart helpers ─────────────────────────────────────────────────────────────
def fig_to_rl(fig, width_mm, dpi=160):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    img = RLImage(buf)
    img.drawWidth  = width_mm * mm
    img.drawHeight = width_mm * mm * (fig.get_figheight() / fig.get_figwidth())
    return img

def style_ax(ax, title=None, ylabel=None, xlabel=None):
    ax.set_facecolor("white")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#D4D8DE")
    ax.spines["bottom"].set_color("#D4D8DE")
    ax.tick_params(axis="both", labelsize=7.5, colors="#5A6474")
    ax.yaxis.set_tick_params(labelcolor="#5A6474")
    ax.xaxis.set_tick_params(labelcolor="#5A6474")
    if title:
        ax.set_title(title, fontsize=8.5, fontweight="bold", color=C_BLUE, pad=6, loc="left")
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=7.5, color="#5A6474")
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=7.5, color="#5A6474")
    ax.grid(axis="y", color="#EEEEEE", linewidth=0.7, linestyle="--")
    ax.grid(axis="x", visible=False)

# ── Chart 1: Revenue & EBIT margin bar+line ───────────────────────────────────
def chart_financials():
    hist = R["historical_financials"]
    years = [h["fy"].replace("FY","") for h in hist]
    revs  = [h["revenue_b"] for h in hist]
    margs = [h["ebit_margin_pct"] for h in hist]
    fcfs  = [h["fcf_b"] for h in hist]

    fig, ax1 = plt.subplots(figsize=(5.2, 2.9))
    x = np.arange(len(years))
    w = 0.35

    bars1 = ax1.bar(x - w/2, revs, w, color=C_BLUE, alpha=0.85, label="Revenue ($B)", zorder=3)
    bars2 = ax1.bar(x + w/2, fcfs, w, color=C_GOLD, alpha=0.85, label="FCF ($B)", zorder=3)

    ax2 = ax1.twinx()
    ax2.plot(x, margs, color=C_RED, marker="o", markersize=4, linewidth=1.8,
             label="EBIT margin (%)", zorder=4)
    ax2.set_ylim(0, 45)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_color("#D4D8DE")
    ax2.tick_params(axis="y", labelsize=7.5, colors=C_RED)
    ax2.set_ylabel("EBIT margin %", fontsize=7, color=C_RED)

    for bar in bars1:
        h = bar.get_height()
        ax1.text(bar.get_x()+bar.get_width()/2, h+0.3, f"${h:.0f}B", ha="center", va="bottom", fontsize=6.5, color=C_BLUE, fontweight="bold")

    ax1.set_xticks(x)
    ax1.set_xticklabels(years, fontsize=8)
    ax1.set_ylim(0, 58)
    style_ax(ax1, title="Revenue, FCF & EBIT Margin  |  FY2022–FY2025", ylabel="$B")

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1+lines2, labels1+labels2, fontsize=6.5, loc="upper left",
               framealpha=0.9, edgecolor="#D4D8DE", ncol=3)

    fig.patch.set_facecolor("white")
    fig.tight_layout(pad=0.6)
    return fig_to_rl(fig, 88)

# ── Chart 2: Subscriber growth by region ─────────────────────────────────────
def chart_subscribers():
    geo = R["business_overview"]["geographic"]
    regions = [g["region"].split(" ")[0] for g in geo]
    members = [g["paid_memberships_m"] for g in geo]
    arpus   = [g["arpu_monthly_2025_usd"] for g in geo]
    colors_bar = [C_BLUE, "#2E5FA3", C_GOLD, C_GREEN]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(5.2, 2.6))

    bars = ax1.bar(regions, members, color=colors_bar, alpha=0.88, zorder=3)
    for bar, v in zip(bars, members):
        ax1.text(bar.get_x()+bar.get_width()/2, v+1, f"{v:.0f}M",
                 ha="center", va="bottom", fontsize=6.5, fontweight="bold", color=C_BLUE)
    style_ax(ax1, title="Paid Members by Region", ylabel="Millions")
    ax1.set_ylim(0, 130)

    bars2 = ax2.bar(regions, arpus, color=colors_bar, alpha=0.88, zorder=3)
    for bar, v in zip(bars2, arpus):
        ax2.text(bar.get_x()+bar.get_width()/2, v+0.2, f"${v:.2f}",
                 ha="center", va="bottom", fontsize=6.5, fontweight="bold", color=C_BLUE)
    style_ax(ax2, title="Monthly ARPU by Region", ylabel="USD/month")
    ax2.set_ylim(0, 22)

    for ax in [ax1, ax2]:
        ax.set_facecolor("white")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(axis="y", color="#EEEEEE", linewidth=0.7, linestyle="--")

    fig.patch.set_facecolor("white")
    fig.tight_layout(pad=0.8)
    return fig_to_rl(fig, 88)

# ── Chart 3: Scenario waterfall ───────────────────────────────────────────────
def chart_scenarios():
    price  = 77.84
    fv     = 55.52
    bull   = 96.05
    bear   = 31.51
    target = 59.95

    fig, ax = plt.subplots(figsize=(5.0, 2.8))

    labels = ["Current\nPrice", "Bear\nCase", "Base\nFair Value", "12m\nTarget", "Bull\nCase"]
    values = [price, bear, fv, target, bull]
    bar_colors = [C_GREY, C_RED, C_BLUE, C_BLUE, C_GREEN]
    alphas = [0.7, 0.85, 0.95, 0.75, 0.85]

    bars = ax.bar(labels, values, color=bar_colors,
                  width=0.55, alpha=0.9, zorder=3, edgecolor="white", linewidth=0.8)

    for bar, v, col in zip(bars, values, bar_colors):
        ax.text(bar.get_x()+bar.get_width()/2, v+1.2, f"${v:.2f}",
                ha="center", va="bottom", fontsize=7.5, fontweight="bold", color=col)

    # price line
    ax.axhline(price, color=C_GREY, linewidth=1.0, linestyle="--", alpha=0.6)

    ax.set_ylim(0, 115)
    style_ax(ax, title="Scenario Range vs. Current Price", ylabel="$ per share")

    fig.patch.set_facecolor("white")
    fig.tight_layout(pad=0.6)
    return fig_to_rl(fig, 85)

# ── Chart 4: Sensitivity heatmap ─────────────────────────────────────────────
def chart_sensitivity():
    grid = VAL["sensitivity_matrix"]["cells"]
    margins = [30, 32, 34, 36, 38]
    ad_revs = [4.0, 5.5, 7.2, 9.0, 10.0]

    data = np.array([[float(grid[str(m)][str(a)]) for a in ad_revs] for m in margins])

    fig, ax = plt.subplots(figsize=(4.8, 2.8))

    vmin, vmax = 44, 62
    im = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=vmin, vmax=vmax, origin="lower")

    ax.set_xticks(range(len(ad_revs)))
    ax.set_xticklabels([f"${a}B" for a in ad_revs], fontsize=7)
    ax.set_yticks(range(len(margins)))
    ax.set_yticklabels([f"{m}%" for m in margins], fontsize=7)
    ax.set_xlabel("Advertising revenue 2030 ($B)", fontsize=7.5, color="#5A6474")
    ax.set_ylabel("Operating margin 2030 (%)", fontsize=7.5, color="#5A6474")
    ax.set_title("Sensitivity Matrix — Fair Value ($/share)  |  g_LT=5% fixed", fontsize=8.5, fontweight="bold", color=C_BLUE, pad=6, loc="left")

    for i, m in enumerate(margins):
        for j, a in enumerate(ad_revs):
            val = data[i, j]
            is_base = (a == 7.2 and m == 36)
            color = "white" if (val < 48 or val > 58 or is_base) else "black"
            weight = "bold" if is_base else "normal"
            ax.text(j, i, f"${val:.0f}", ha="center", va="center",
                    fontsize=6.5, color=color, fontweight=weight)
            if is_base:
                rect = plt.Rectangle((j-0.5, i-0.5), 1, 1, fill=False,
                                      edgecolor="black", linewidth=2)
                ax.add_patch(rect)

    cbar = plt.colorbar(im, ax=ax, pad=0.02, fraction=0.035)
    cbar.ax.tick_params(labelsize=6.5)
    cbar.set_label("Fair Value $", fontsize=7, color="#5A6474")

    fig.patch.set_facecolor("white")
    fig.tight_layout(pad=0.6)
    return fig_to_rl(fig, 83)

# ── Chart 5: Advertising revenue ramp ────────────────────────────────────────
def chart_ad_ramp():
    years_hist = [2022, 2023, 2024, 2025]
    ad_hist    = [0.0, 0.0, 0.3, 1.5]  # approximate history
    years_fwd  = [2025, 2026, 2027, 2028, 2029, 2030]
    base_fwd   = [1.5, 3.0, 4.5, 5.5, 6.4, 7.2]
    bull_fwd   = [1.5, 3.0, 5.0, 6.5, 8.2, 10.0]
    bear_fwd   = [1.5, 2.5, 2.5, 3.0, 3.5, 4.0]

    fig, ax = plt.subplots(figsize=(5.0, 2.8))

    ax.bar(years_hist, ad_hist, color=C_GREY, alpha=0.55, width=0.6, label="Historical", zorder=2)
    ax.plot(years_fwd, base_fwd, color=C_BLUE, linewidth=2.0, marker="o", markersize=4, label="Base ($7.2B)", zorder=4)
    ax.plot(years_fwd, bull_fwd, color=C_GREEN, linewidth=1.6, marker="^", markersize=3.5, linestyle="--", label="Bull ($10.0B)", zorder=3)
    ax.plot(years_fwd, bear_fwd, color=C_RED, linewidth=1.6, marker="v", markersize=3.5, linestyle="--", label="Bear ($4.0B)", zorder=3)

    ax.fill_between(years_fwd, bear_fwd, bull_fwd, alpha=0.07, color=C_BLUE, zorder=1)

    ax.axvline(2025.5, color="#D4D8DE", linewidth=1, linestyle=":")
    ax.text(2025.55, 9.5, "Forecast →", fontsize=6.5, color=C_GREY)

    ax.set_xlim(2021.5, 2030.5)
    ax.set_ylim(0, 11.5)
    ax.set_xticks(list(range(2022, 2031)))
    ax.set_xticklabels([str(y) for y in range(2022, 2031)], fontsize=7)

    style_ax(ax, title="Advertising Revenue Trajectory  |  THE CRUX", ylabel="$ Billions")
    ax.legend(fontsize=6.5, loc="upper left", framealpha=0.9, edgecolor="#D4D8DE")

    fig.patch.set_facecolor("white")
    fig.tight_layout(pad=0.6)
    return fig_to_rl(fig, 85)

# ── Chart 6: Peer comparison ──────────────────────────────────────────────────
def chart_peers():
    peers = R["peers"]
    names = ["NFLX"] + [p["ticker"] for p in peers]
    pe    = [21.7] + [p["pe_ntm"] for p in peers]
    rev_g = [15.9] + [p["rev_growth_ttm"] for p in peers]

    x = np.arange(len(names))
    colors_p = [C_RED] + [C_BLUE]*len(peers)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(5.2, 2.6))

    bars1 = ax1.bar(x, pe, color=colors_p, alpha=0.85, width=0.55, zorder=3)
    for bar, v in zip(bars1, pe):
        ax1.text(bar.get_x()+bar.get_width()/2, v+0.3, f"{v:.1f}x",
                 ha="center", va="bottom", fontsize=6.5, fontweight="bold",
                 color=C_RED if bar == bars1[0] else C_BLUE)
    ax1.set_xticks(x); ax1.set_xticklabels(names, fontsize=7.5)
    style_ax(ax1, title="NTM P/E", ylabel="Multiple")
    ax1.set_ylim(0, 40)

    bars2 = ax2.bar(x, rev_g, color=colors_p, alpha=0.85, width=0.55, zorder=3)
    for bar, v in zip(bars2, rev_g):
        col = C_GREEN if v > 0 else C_RED
        ax2.text(bar.get_x()+bar.get_width()/2, v+0.2 if v>=0 else v-1.5,
                 f"{v:.1f}%", ha="center", va="bottom" if v>=0 else "top",
                 fontsize=6.5, fontweight="bold", color=col)
    ax2.set_xticks(x); ax2.set_xticklabels(names, fontsize=7.5)
    ax2.axhline(0, color="#D4D8DE", linewidth=0.8)
    style_ax(ax2, title="Revenue Growth (TTM)", ylabel="%")
    ax2.set_ylim(-8, 22)

    for ax in [ax1, ax2]:
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.set_facecolor("white")
        ax.grid(axis="y", color="#EEEEEE", linewidth=0.7, linestyle="--")

    fig.patch.set_facecolor("white")
    fig.tight_layout(pad=0.8)
    return fig_to_rl(fig, 88)


# ── Page header/footer canvas callbacks ───────────────────────────────────────
def on_page(canvas, doc):
    canvas.saveState()
    W, H = A4

    # Top stripe
    canvas.setFillColor(SLATE)
    canvas.rect(0, H - 10*mm, W, 10*mm, fill=1, stroke=0)

    # Header text
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica-Bold", 8.5)
    canvas.drawString(MARGIN_L, H - 6.5*mm, "NETFLIX INC. (NFLX)  |  EQUITY RESEARCH")
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(W - MARGIN_R, H - 6.5*mm, "ATLAS RESEARCH  |  JUNE 17, 2026")

    # Bottom stripe
    canvas.setFillColor(HexColor("#F0F2F5"))
    canvas.rect(0, 0, W, 8*mm, fill=1, stroke=0)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 6.5)
    canvas.drawCentredString(W/2, 2.8*mm,
        f"Page {doc.page}  |  For institutional use only. Not investment advice. "
        "Past performance is not a guarantee of future results.")
    canvas.setFont("Helvetica-Bold", 6.5)
    canvas.setFillColor(ACCENT)
    canvas.drawString(MARGIN_L, 2.8*mm, "SELL")
    canvas.setFillColor(MUTED)
    canvas.drawRightString(W - MARGIN_R, 2.8*mm, "Target: $59.95  |  FV: $55.52  |  Price: $77.84")

    canvas.restoreState()

def on_first_page(canvas, doc):
    on_page(canvas, doc)

# ── Callout box flowable ──────────────────────────────────────────────────────
class CalloutBox(Flowable):
    def __init__(self, text, bg=NAVY_LIGHT, border=SLATE, width=CONTENT_W, padding=4):
        super().__init__()
        self.text = text
        self.bg = bg
        self.border = border
        self._width = width
        self.padding = padding
        self._style = ParagraphStyle("callout", fontName="Helvetica-Oblique",
                                     fontSize=8.5, leading=13, textColor=SLATE,
                                     alignment=TA_JUSTIFY)
        self._para = Paragraph(text, self._style)
        w, h = self._para.wrapOn(None, width - 2*padding*mm, 9999)
        self.height = h + 2*padding*mm + 2

    def draw(self):
        c = self.canv
        c.setFillColor(self.bg)
        c.setStrokeColor(self.border)
        c.setLineWidth(0.5)
        c.roundRect(0, 0, self._width, self.height, 2, fill=1, stroke=1)
        # left accent bar
        c.setFillColor(self.border)
        c.rect(0, 0, 2.5, self.height, fill=1, stroke=0)
        self._para.drawOn(c, self.padding*mm + 3, self.padding*mm)


# ── Rating badge flowable ─────────────────────────────────────────────────────
class RatingBadge(Flowable):
    def __init__(self, rating="SELL", conviction="MEDIUM", width=CONTENT_W):
        super().__init__()
        self.rating = rating
        self.conviction = conviction
        self._width = width
        self.height = 20*mm

    def draw(self):
        c = self.canv
        # Background
        c.setFillColor(HexColor("#FDF1F1"))
        c.setStrokeColor(ACCENT)
        c.setLineWidth(1)
        c.roundRect(0, 0, self._width, self.height, 3, fill=1, stroke=1)

        # Rating pill
        pill_w = 28*mm
        c.setFillColor(ACCENT)
        c.roundRect(4*mm, 4*mm, pill_w, 12*mm, 2, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(4*mm + pill_w/2, 8.5*mm, self.rating)

        # Conviction
        c.setFillColor(SLATE)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(38*mm, 11*mm, "CONVICTION")
        c.setFont("Helvetica", 8)
        c.drawString(38*mm, 6*mm, self.conviction)

        # Four numbers
        numbers = [
            ("FAIR VALUE TODAY", "$55.52", "18.5x EV/NTM NOPAT"),
            ("12M TARGET", "$59.95", "16.7x fwd P/E"),
            ("CURRENT PRICE", "$77.84", "25.8x EV/NTM NOPAT"),
            ("IMPLIED RETURN", "–23.0%", "to 12m target"),
        ]
        x_start = 68*mm
        col_w   = (self._width - x_start - 4*mm) / len(numbers)
        for i, (lbl, val, sub) in enumerate(numbers):
            xp = x_start + i * col_w
            c.setFillColor(MUTED)
            c.setFont("Helvetica", 6.5)
            c.drawString(xp, 13.5*mm, lbl)
            val_color = ACCENT if "%" in val and val.startswith("–") else SLATE
            c.setFillColor(val_color)
            c.setFont("Helvetica-Bold", 10.5)
            c.drawString(xp, 7.5*mm, val)
            c.setFillColor(MUTED)
            c.setFont("Helvetica", 6.5)
            c.drawString(xp, 3.5*mm, sub)


# ── Debate card flowable ──────────────────────────────────────────────────────
class DebateCard(Flowable):
    def __init__(self, debate, number, width=CONTENT_W):
        super().__init__()
        self.d = debate
        self.number = number
        self._width = width
        self.height = 52*mm

    def draw(self):
        c = self.canv
        d = self.d
        w = self._width
        h = self.height
        p = 3.5*mm

        # outer border
        c.setStrokeColor(RULE)
        c.setLineWidth(0.5)
        is_crux = d.get("is_crux", False)
        bg = HexColor("#F8F5EF") if is_crux else WHITE
        c.setFillColor(bg)
        c.roundRect(0, 0, w, h, 2, fill=1, stroke=1)

        # top bar
        bar_col = GOLD if is_crux else SLATE
        c.setFillColor(bar_col)
        c.rect(0, h - 7*mm, w, 7*mm, fill=1, stroke=0)

        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 8.5)
        label = f"DEBATE {self.number}{'  ★ THE CRUX' if is_crux else ''}"
        c.drawString(p, h - 4.8*mm, label)

        # Worth badge
        worth = d.get("worth_per_share", 0)
        worth_color = C_GREEN if worth > 0 else C_RED
        worth_str = f"+${worth:.0f}/sh" if worth > 0 else f"${worth:.0f}/sh"
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 7.5)
        c.drawRightString(w - p, h - 4.8*mm, worth_str)

        # Title
        c.setFillColor(SLATE)
        c.setFont("Helvetica-Bold", 8)
        title = d["debate"][:85] + "…" if len(d["debate"]) > 85 else d["debate"]
        c.drawString(p, h - 11*mm, title)

        # Two columns: bull / bear
        col_w = (w - 3*p) / 2
        # Bull
        c.setFillColor(HexColor("#E8F5ED"))
        c.roundRect(p, 20*mm, col_w, h - 32*mm, 2, fill=1, stroke=0)
        c.setFillColor(HexColor("#1A6B3C"))
        c.setFont("Helvetica-Bold", 7)
        c.drawString(p + 2*mm, h - 17*mm, "▲ BULL")

        # Bear
        bx = p + col_w + p
        c.setFillColor(HexColor("#FDE8E8"))
        c.roundRect(bx, 20*mm, col_w, h - 32*mm, 2, fill=1, stroke=0)
        c.setFillColor(HexColor("#A01020"))
        c.setFont("Helvetica-Bold", 7)
        c.drawString(bx + 2*mm, h - 17*mm, "▼ BEAR")

        # Verdict
        c.setFillColor(SLATE)
        c.setFont("Helvetica-Bold", 7)
        c.drawString(p, 17*mm, "OUR VERDICT")

        # Evidence
        eq = d.get("evidence_quality", "")
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 6.5)
        eq_short = eq.split("(")[0].strip()
        c.drawRightString(w - p, 3*mm, f"Evidence: {eq_short}")


# ── Build story ───────────────────────────────────────────────────────────────
def build():
    out = BASE / "NFLX_report.pdf"
    doc = SimpleDocTemplate(
        str(out),
        pagesize=A4,
        leftMargin=MARGIN_L, rightMargin=MARGIN_R,
        topMargin=MARGIN_T + 10*mm, bottomMargin=MARGIN_B + 10*mm,
        title="Netflix Inc. — Atlas Equity Research",
        author="Atlas Research Engine",
    )

    story = []

    # ── PAGE 1: Cover / Summary ───────────────────────────────────────────────
    # Company title block
    story.append(SP(2))
    story.append(P("Netflix Inc. (NASDAQ: NFLX)", "h1", fontSize=20, leading=24, textColor=SLATE))
    story.append(P("Streaming Entertainment  ·  Communication Services  ·  US Equity", "body_sm",
                   fontName="Helvetica", fontSize=8.5, textColor=MUTED, alignment=TA_LEFT))
    story.append(SP(1))
    story.append(HR(SLATE, 1.5))
    story.append(SP(2))

    # Rating badge
    story.append(RatingBadge("SELL", "MEDIUM"))
    story.append(SP(4))

    # Thesis
    story.append(CalloutBox(
        "<b>Investment thesis:</b> " + R["our_view"],
        bg=NAVY_LIGHT, border=SLATE
    ))
    story.append(SP(4))

    # The Crux box
    story.append(CalloutBox(
        "<b>The Crux:</b> " + R["crux"]["one_line"],
        bg=HexColor("#FFF8E8"), border=GOLD
    ))
    story.append(SP(5))

    # Scenario strip
    story.append(SectionHeader("SCENARIO RANGE"))
    story.append(SP(2))
    sc_data = [
        [P("BEAR", "label", textColor=BEAR_RED),
         P("BASE (FAIR VALUE)", "label", textColor=SLATE),
         P("12M TARGET", "label", textColor=SLATE),
         P("BULL", "label", textColor=GREEN)],
        [P("$31.51", "number", textColor=BEAR_RED, fontSize=16),
         P("$55.52", "number", textColor=SLATE, fontSize=16),
         P("$59.95", "number", textColor=SLATE, fontSize=16),
         P("$96.05", "number", textColor=GREEN, fontSize=16)],
        [P("–59% vs price", "body_sm", alignment=TA_CENTER, textColor=BEAR_RED),
         P("–29% vs price", "body_sm", alignment=TA_CENTER, textColor=MUTED),
         P("–23% vs price", "body_sm", alignment=TA_CENTER, textColor=MUTED),
         P("+23% vs price", "body_sm", alignment=TA_CENTER, textColor=GREEN)],
        [P("g_LT=3.5%, ads $4B,\nmargin 30%", "body_sm", alignment=TA_CENTER, textColor=MUTED),
         P("g_LT=5.0%, ads $7.2B,\nmargin 36%", "body_sm", alignment=TA_CENTER, textColor=MUTED),
         P("16.7x fwd P/E on\n$3.59 FY26E EPS", "body_sm", alignment=TA_CENTER, textColor=MUTED),
         P("g_LT=6.0%, ads $10B,\nmargin 38%", "body_sm", alignment=TA_CENTER, textColor=MUTED)],
    ]
    sc_col = CONTENT_W / 4
    sc_tbl = Table(sc_data, colWidths=[sc_col]*4)
    sc_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (0,-1), HexColor("#FDE8E8")),
        ("BACKGROUND", (1,0), (1,-1), NAVY_LIGHT),
        ("BACKGROUND", (2,0), (2,-1), NAVY_LIGHT),
        ("BACKGROUND", (3,0), (3,-1), HexColor("#E8F5ED")),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LINEBEFORE", (1,0), (1,-1), 0.5, RULE),
        ("LINEBEFORE", (2,0), (2,-1), 0.5, RULE),
        ("LINEBEFORE", (3,0), (3,-1), 0.5, RULE),
        ("BOX", (0,0), (-1,-1), 0.5, RULE),
    ]))
    story.append(sc_tbl)
    story.append(SP(5))

    # Quick snapshot strip
    snap_items = {d["label"]: d for d in R["snapshot"]} if isinstance(R["snapshot"], list) else {}
    # Build a flat key-value from snapshot
    snap_kv = {}
    if isinstance(R["snapshot"], list):
        for item in R["snapshot"]:
            snap_kv[item.get("label","?")] = item.get("value","—")
    elif isinstance(R["snapshot"], dict):
        snap_kv = R["snapshot"]

    snap_pairs = list(snap_kv.items())[:12]
    cols = 4
    rows_snap = [snap_pairs[i:i+cols] for i in range(0, len(snap_pairs), cols)]

    story.append(SectionHeader("COMPANY SNAPSHOT"))
    story.append(SP(1))
    for row in rows_snap:
        row_data = []
        for label, val in row:
            row_data.append([P(label, "label"), P(str(val), "cell_bold")])
        # pad
        while len(row_data) < cols:
            row_data.append([P("", "label"), P("", "cell_bold")])
        tbl_row = Table([[cell for pair in row_data for cell in pair]],
                        colWidths=[28*mm, 20*mm]*cols)
        tbl_row.setStyle(TableStyle([
            ("TOPPADDING", (0,0), (-1,-1), 3),
            ("BOTTOMPADDING", (0,0), (-1,-1), 3),
            ("BACKGROUND", (0,0), (-1,-1), CREAM),
            ("LINEBELOW", (0,0), (-1,-1), 0.3, RULE),
        ]))
        story.append(tbl_row)

    story.append(PageBreak())

    # ── PAGE 2: Business Overview + Financials ────────────────────────────────
    story.append(SectionHeader("§1  THE BUSINESS"))
    story.append(SP(2))
    story.append(P(R["business_overview"]["summary"], "body"))
    story.append(SP(2))
    story.append(P(R["business_overview"]["business_model"], "body"))
    story.append(SP(3))

    # Segments table
    segs = R["business_overview"]["segments"]
    seg_data = [[
        P("Segment", "cell_bold"), P("2025 Revenue", "cell_bold"),
        P("Rev Share", "cell_bold"), P("Growth", "cell_bold"), P("Nature", "cell_bold")
    ]]
    for seg in segs:
        seg_data.append([
            P(seg["name"], "cell"),
            P(f"${seg['revenue_2025_b']:.1f}B" if seg['revenue_2025_b'] else "—", "cell_r"),
            P(f"{seg['revenue_share_pct']:.1f}%", "cell_r"),
            P(f"{seg['revenue_growth_pct']:.0f}%" if seg['revenue_growth_pct'] else "—", "cell_r"),
            P(seg["nature"].title(), "cell"),
        ])
    seg_widths = [70*mm, 25*mm, 22*mm, 20*mm, 22*mm]
    seg_tbl = Table(seg_data, colWidths=seg_widths)
    seg_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), SLATE),
        ("TEXTCOLOR", (0,0), (-1,0), WHITE),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 7.5),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [WHITE, CREAM]),
        ("TOPPADDING", (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("LINEBELOW", (0,0), (-1,-1), 0.3, RULE),
        ("BOX", (0,0), (-1,-1), 0.5, RULE),
        ("ALIGN", (1,0), (-1,-1), "RIGHT"),
        ("ALIGN", (0,0), (0,-1), "LEFT"),
    ]))
    story.append(seg_tbl)
    story.append(SP(3))

    # Geographic table
    geo = R["business_overview"]["geographic"]
    geo_data = [[
        P("Region", "cell_bold"), P("Revenue", "cell_bold"),
        P("Share", "cell_bold"), P("Members", "cell_bold"),
        P("ARPU/mo", "cell_bold"), P("Growth", "cell_bold")
    ]]
    for g in geo:
        geo_data.append([
            P(g["region"], "cell"),
            P(f"${g['revenue_2025_b']:.1f}B", "cell_r"),
            P(f"{g['revenue_share_pct']:.1f}%", "cell_r"),
            P(f"{g['paid_memberships_m']:.1f}M", "cell_r"),
            P(f"${g['arpu_monthly_2025_usd']:.2f}", "cell_r"),
            P(f"{g['growth_pct_2025']:.0f}%", "cell_r"),
        ])
    geo_widths = [48*mm, 24*mm, 20*mm, 22*mm, 22*mm, 18*mm]
    geo_tbl = Table(geo_data, colWidths=geo_widths)
    geo_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), SLATE),
        ("TEXTCOLOR", (0,0), (-1,0), WHITE),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 7.5),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [WHITE, CREAM]),
        ("TOPPADDING", (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("LINEBELOW", (0,0), (-1,-1), 0.3, RULE),
        ("BOX", (0,0), (-1,-1), 0.5, RULE),
        ("ALIGN", (1,0), (-1,-1), "RIGHT"),
        ("ALIGN", (0,0), (0,-1), "LEFT"),
    ]))
    story.append(geo_tbl)
    story.append(SP(4))

    # Historical financials
    story.append(SectionHeader("§2  FINANCIAL HISTORY  (FY2022–FY2025)"))
    story.append(SP(2))
    story.append(P(R["historical_financials_read"], "body"))
    story.append(SP(3))

    hist = R["historical_financials"]
    fin_headers = ["", "FY2022", "FY2023", "FY2024", "FY2025"]
    metrics = [
        ("Revenue ($B)", "revenue_b", "${:.1f}B"),
        ("Revenue Growth", "revenue_growth_pct", "{:.1f}%"),
        ("Gross Profit ($B)", "gross_profit_b", "${:.1f}B"),
        ("Gross Margin", "gross_margin_pct", "{:.1f}%"),
        ("EBIT ($B)", "ebit_b", "${:.1f}B"),
        ("EBIT Margin", "ebit_margin_pct", "{:.1f}%"),
        ("FCF ($B)", "fcf_b", "${:.1f}B"),
        ("EPS (post-split)", "eps", "${:.2f}"),
        ("Paid Members (M)", "paid_members_m", "{:.0f}M"),
    ]
    fin_data = [fin_headers]
    for label, key, fmt in metrics:
        row = [P(label, "cell_bold")]
        for h in hist:
            val = h.get(key)
            row.append(P(fmt.format(val) if val is not None else "—", "cell_r"))
        fin_data.append(row)

    fin_col = [50*mm] + [(CONTENT_W - 50*mm)/4]*4
    fin_tbl = Table(fin_data, colWidths=fin_col)
    fin_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), SLATE),
        ("TEXTCOLOR", (0,0), (-1,0), WHITE),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 7.5),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [WHITE, CREAM]),
        ("TOPPADDING", (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("LINEBELOW", (0,0), (-1,-1), 0.3, RULE),
        ("BOX", (0,0), (-1,-1), 0.5, RULE),
        ("ALIGN", (1,0), (-1,-1), "RIGHT"),
        ("FONTNAME", (0,3), (0,3), "Helvetica-Bold"),
        ("FONTNAME", (0,5), (0,5), "Helvetica-Bold"),
    ]))
    story.append(fin_tbl)
    story.append(SP(3))

    # Charts: financials + subscribers side by side
    c_fin = chart_financials()
    c_sub = chart_subscribers()
    chart_tbl = Table([[c_fin, SP(3), c_sub]],
                       colWidths=[88*mm, 6*mm, 88*mm])
    chart_tbl.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("TOPPADDING", (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
        ("LEFTPADDING", (0,0), (-1,-1), 0),
        ("RIGHTPADDING", (0,0), (-1,-1), 0),
    ]))
    story.append(chart_tbl)
    story.append(P("Source: Netflix 10-K FY2025, Q1 2026 10-Q, Atlas analysis", "caption"))

    story.append(PageBreak())

    # ── PAGE 3: Valuation ─────────────────────────────────────────────────────
    story.append(SectionHeader("§3  VALUATION  —  EXIT MULTIPLE ON 2030 NORMALIZED NOPAT"))
    story.append(SP(2))
    story.append(P(R["valuation_method"]["why_it_fits"], "body"))
    story.append(SP(3))

    # Four levers table
    levers = R["four_levers"]
    lev_order = [
        ("Growth Rate & Duration", "growth_rate_and_duration"),
        ("Economics (Margin & ROIC)", "economics"),
        ("Discount Rate (WACC)", "wacc"),
        ("Exit Multiple", "exit_multiple"),
    ]
    lev_data = [[P("Lever", "cell_bold"), P("Assumption", "cell_bold"), P("Argument", "cell_bold")]]
    for name, key in lev_order:
        lev = levers[key]
        lev_data.append([
            P(name, "cell_bold"),
            P(lev["assumption"], "cell"),
            P(lev["argument"][:300] + ("…" if len(lev["argument"]) > 300 else ""), "cell"),
        ])
    lev_widths = [35*mm, 40*mm, CONTENT_W - 75*mm]
    lev_tbl = Table(lev_data, colWidths=lev_widths)
    lev_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), SLATE),
        ("TEXTCOLOR", (0,0), (-1,0), WHITE),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 7.5),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [WHITE, CREAM]),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LINEBELOW", (0,0), (-1,-1), 0.3, RULE),
        ("BOX", (0,0), (-1,-1), 0.5, RULE),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
    ]))
    story.append(lev_tbl)
    story.append(SP(3))

    # Scenario assumptions table
    story.append(P("SCENARIO ASSUMPTIONS", "h3"))
    story.append(SP(1))
    sa = R["scenario_assumptions"]
    rows_key = ["Revenue 2030", "Advertising revenue 2030", "Operating margin 2030",
                "NOPAT 2030 (T-normalized)", "g_LT (terminal growth after 2030)",
                "WACC (r)", "Exit multiple (Gordon)", "Interim FCF PV (2026-2030)",
                "Implied fair value per share"]
    def lookup(case, driver):
        for row in case.get("rows", []):
            if row["driver"].startswith(driver[:20]):
                return row["value"]
        return "—"

    sa_data = [[P("Driver", "cell_bold"), P("Base", "cell_bold"), P("Bull", "cell_bold"), P("Bear", "cell_bold")]]
    for drv in rows_key:
        bv = lookup(sa["base"], drv)
        buv = lookup(sa["bull"], drv)
        bev = lookup(sa["bear"], drv)
        is_val = "fair value" in drv.lower()
        bold = "cell_bold" if is_val else "cell"
        sa_data.append([
            P(drv, bold),
            P(bv, bold + ("_r" if not is_val else "_r"), textColor=SLATE if is_val else INK),
            P(buv, bold + "_r", textColor=GREEN if is_val else INK),
            P(bev, bold + "_r", textColor=BEAR_RED if is_val else INK),
        ])
    sa_col = [65*mm] + [(CONTENT_W - 65*mm)/3]*3
    sa_tbl = Table(sa_data, colWidths=sa_col)
    sa_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), SLATE),
        ("TEXTCOLOR", (0,0), (-1,0), WHITE),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 7.5),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [WHITE, CREAM]),
        ("TOPPADDING", (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("LINEBELOW", (0,0), (-1,-1), 0.3, RULE),
        ("BOX", (0,0), (-1,-1), 0.5, RULE),
        ("ALIGN", (1,0), (-1,-1), "RIGHT"),
        ("BACKGROUND", (0,-1), (-1,-1), NAVY_LIGHT),
        ("FONTNAME", (0,-1), (-1,-1), "Helvetica-Bold"),
        ("TEXTCOLOR", (1,-1), (1,-1), SLATE),
        ("TEXTCOLOR", (2,-1), (2,-1), GREEN),
        ("TEXTCOLOR", (3,-1), (3,-1), BEAR_RED),
    ]))
    story.append(sa_tbl)
    story.append(SP(3))

    # Bias audit
    ba = R["bias_audit"]
    if isinstance(ba, dict):
        verdict = ba.get("verdict", "")
        story.append(CalloutBox(f"<b>Bias Audit:</b> {verdict}", bg=HexColor("#EEF7EE"), border=GREEN))
    story.append(SP(3))

    # Charts: scenario waterfall + ad ramp
    c_sc = chart_scenarios()
    c_ad = chart_ad_ramp()
    ch_tbl2 = Table([[c_sc, SP(3), c_ad]], colWidths=[85*mm, 6*mm, 85*mm])
    ch_tbl2.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("TOPPADDING", (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
        ("LEFTPADDING", (0,0), (-1,-1), 0),
        ("RIGHTPADDING", (0,0), (-1,-1), 0),
    ]))
    story.append(ch_tbl2)
    story.append(P("Source: Atlas exit-multiple model; Theia demand.json; MoffettNathanson $9.6B 2030 projection cited as benchmark", "caption"))

    story.append(PageBreak())

    # ── PAGE 4: Sensitivity + Key Debates ────────────────────────────────────
    story.append(SectionHeader("§4  SENSITIVITY ANALYSIS"))
    story.append(SP(2))
    story.append(P(
        "<b>Critical finding:</b> No cell in this sensitivity matrix (g_LT held fixed at 5%) reaches "
        "the current price of $77.84. Even at the maximum cell (38% margin, $10B ad revenue), fair "
        "value is $60.17. To justify $77.84, the market requires g_LT ≈ 7% — i.e., the full bull "
        "advertising thesis PLUS sustained above-GDP growth well beyond 2030. Base cell highlighted "
        "in bold border.", "body"))
    story.append(SP(2))

    sm = VAL["sensitivity_matrix"]
    heat_data = [[P("Margin \\ Ad Rev", "cell_bold")] + [P(f"${v}B", "cell_bold", alignment=TA_RIGHT) for v in sm["x_values"]]]
    for m in sm["y_values"]:
        row = [P(f"{m}%", "cell_bold")]
        for a in sm["x_values"]:
            val = sm["cells"][str(m)][str(a)]
            is_base = (a == sm["base_cell"]["ad_rev_b"] and m == sm["base_cell"]["margin_pct"])
            is_above = val >= 77.84
            color = GREEN if is_above else (ACCENT if val < 50 else INK)
            row.append(P(f"${val:.0f}", "cell_r" if not is_base else "cell_bold_r", textColor=color))
        heat_data.append(row)

    sm_col = [22*mm] + [(CONTENT_W - 22*mm) / len(sm["x_values"])] * len(sm["x_values"])
    sm_tbl = Table(heat_data, colWidths=sm_col)
    sm_style = [
        ("BACKGROUND", (0,0), (-1,0), SLATE),
        ("TEXTCOLOR", (0,0), (-1,0), WHITE),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [WHITE, CREAM]),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LINEBELOW", (0,0), (-1,-1), 0.3, RULE),
        ("BOX", (0,0), (-1,-1), 0.5, RULE),
        ("ALIGN", (1,0), (-1,-1), "CENTER"),
    ]
    # highlight base cell
    base_row = sm["y_values"].index(sm["base_cell"]["margin_pct"]) + 1
    base_col = sm["x_values"].index(sm["base_cell"]["ad_rev_b"]) + 1
    sm_style += [
        ("BACKGROUND", (base_col, base_row), (base_col, base_row), NAVY_LIGHT),
        ("BOX", (base_col, base_row), (base_col, base_row), 1.5, SLATE),
        ("FONTNAME", (base_col, base_row), (base_col, base_row), "Helvetica-Bold"),
    ]
    sm_tbl.setStyle(TableStyle(sm_style))
    story.append(sm_tbl)
    story.append(SP(1))
    story.append(P("Base cell (boxed): $7.2B advertising, 36% margin = $55.52/share. Green = above current price ($77.84). Red = below $50.", "caption"))
    story.append(SP(1))
    story.append(chart_sensitivity())
    story.append(P("Source: Atlas sensitivity engine; g_LT=5%, ROIC=40%, r=10.3% held fixed", "caption"))
    story.append(SP(4))

    # Key debates
    story.append(SectionHeader("§5  THE KEY DEBATES"))
    story.append(SP(2))
    story.append(P(
        "The crux debate (★) is the advertising revenue trajectory — everything else is secondary. "
        "Each debate is quantified in $/share and graded by evidence quality.", "body"))
    story.append(SP(3))

    for i, debate in enumerate(R["key_debates"]):
        story.append(DebateCard(debate, i+1))
        story.append(SP(2))

        # Inline bull/bear text in two columns
        bull_txt = debate["bull_view"][:400] + ("…" if len(debate["bull_view"]) > 400 else "")
        bear_txt = debate["bear_view"][:400] + ("…" if len(debate["bear_view"]) > 400 else "")
        verdict_txt = debate["our_verdict"][:350] + ("…" if len(debate["our_verdict"]) > 350 else "")
        flip_txt = debate.get("what_would_change_our_mind", "")[:200]

        bb_tbl = Table([
            [P("▲  " + bull_txt, "body", textColor=HexColor("#1A6B3C")),
             P("▼  " + bear_txt, "body", textColor=HexColor("#A01020"))],
        ], colWidths=[CONTENT_W/2 - 2*mm, CONTENT_W/2 - 2*mm])
        bb_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (0,0), HexColor("#F0FAF2")),
            ("BACKGROUND", (1,0), (1,0), HexColor("#FEF0F0")),
            ("TOPPADDING", (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
            ("LEFTPADDING", (0,0), (-1,-1), 5),
            ("RIGHTPADDING", (0,0), (-1,-1), 5),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("LINEAFTER", (0,0), (0,0), 0.5, RULE),
        ]))
        story.append(bb_tbl)
        story.append(SP(1))
        story.append(CalloutBox(
            f"<b>Our verdict:</b> {verdict_txt}<br/>"
            f"<b>What would change our mind:</b> {flip_txt}",
            bg=NAVY_LIGHT, border=SLATE
        ))
        story.append(SP(4))

    story.append(PageBreak())

    # ── PAGE 5: Industry + Management + Market View ───────────────────────────
    story.append(SectionHeader("§6  INDUSTRY, COMPETITION & MARKET VIEW"))
    story.append(SP(2))

    ind = R["industry_position"]
    story.append(P(ind.get("summary", ind.get("description", "")), "body"))
    story.append(SP(2))

    # Peers table
    story.append(P("PEER VALUATION CONTEXT", "h3"))
    story.append(SP(1))
    peer_data = [[
        P("Ticker", "cell_bold"), P("Company", "cell_bold"),
        P("NTM P/E", "cell_bold"), P("EV/EBITDA", "cell_bold"),
        P("Rev Growth", "cell_bold"), P("Highlight", "cell_bold")
    ]]
    # Netflix first
    peer_data.append([
        P("NFLX ★", "cell_bold", textColor=ACCENT),
        P("Netflix", "cell_bold"),
        P("21.7x", "cell_bold_r", textColor=ACCENT),
        P("—", "cell_r"),
        P("15.9%", "cell_r"),
        P("Subject of this report. SELL at $77.84 / FV $55.52", "cell"),
    ])
    for peer in R["peers"]:
        peer_data.append([
            P(peer["ticker"], "cell"),
            P(peer["name"], "cell"),
            P(f"{peer['pe_ntm']:.1f}x", "cell_r"),
            P(f"{peer['ev_ebitda']:.1f}x", "cell_r"),
            P(f"{peer['rev_growth_ttm']:.1f}%", "cell_r"),
            P(peer["highlight"][:90]+"…" if len(peer["highlight"])>90 else peer["highlight"], "cell"),
        ])
    peer_widths = [18*mm, 36*mm, 18*mm, 18*mm, 18*mm, CONTENT_W - 108*mm]
    peer_tbl = Table(peer_data, colWidths=peer_widths)
    peer_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), SLATE),
        ("TEXTCOLOR", (0,0), (-1,0), WHITE),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 7.5),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [WHITE, CREAM]),
        ("TOPPADDING", (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("LINEBELOW", (0,0), (-1,-1), 0.3, RULE),
        ("BOX", (0,0), (-1,-1), 0.5, RULE),
        ("ALIGN", (2,0), (4,-1), "RIGHT"),
        ("BACKGROUND", (0,1), (-1,1), HexColor("#FDE8E8")),
        ("FONTNAME", (0,1), (-1,1), "Helvetica-Bold"),
    ]))
    story.append(peer_tbl)
    story.append(SP(3))

    # Market view
    story.append(P("MARKET VIEW & STREET RECONSTRUCTION", "h3"))
    story.append(SP(1))
    mv = R["market_view"]
    if isinstance(mv, str):
        story.append(P(mv, "body"))
    elif isinstance(mv, dict):
        story.append(P(mv.get("summary", mv.get("description", str(mv))), "body"))
    story.append(SP(2))
    sr = R["street_reconstruction"]
    recon_txt = (sr if isinstance(sr, str) else
                 sr.get("summary", sr.get("what_price_implies","") + " " + sr.get("what_street_implies","")))
    story.append(P(recon_txt, "body"))
    story.append(SP(3))

    # Peer chart
    story.append(chart_peers())
    story.append(P("Source: Atlas comps model; Bloomberg consensus; databundle.json", "caption"))
    story.append(SP(4))

    # Management
    story.append(SectionHeader("§7  MANAGEMENT & CAPITAL ALLOCATION"))
    story.append(SP(2))
    mgmt = R["management"]
    story.append(P(f"<b>Co-CEOs:</b> {mgmt['ceo']['name']}", "body"))
    story.append(SP(1))
    story.append(P(mgmt["ceo"]["track_record"], "body"))
    story.append(SP(2))
    story.append(P(f"<b>CFO:</b> {mgmt['cfo']['name']} — {mgmt['cfo']['track_record']}", "body"))
    story.append(SP(2))
    story.append(P(f"<b>Capital Allocation:</b> {mgmt['capital_allocation_history']}", "body"))
    story.append(SP(2))
    # Insider activity
    insiders = mgmt.get("recent_insider_activity", [])
    if insiders:
        story.append(P("RECENT INSIDER ACTIVITY", "h3"))
        story.append(SP(1))
        ins_data = [[P("Date", "cell_bold"), P("Person", "cell_bold"),
                     P("Transaction", "cell_bold"), P("Amount", "cell_bold"), P("Note", "cell_bold")]]
        for ins in insiders:
            ins_data.append([
                P(ins.get("date",""), "cell"),
                P(ins.get("person",""), "cell"),
                P(ins.get("transaction",""), "cell"),
                P(f"${ins['amount_usd']:,}" if ins.get("amount_usd") else "—", "cell_r"),
                P(ins.get("note",""), "cell"),
            ])
        ins_widths = [18*mm, 38*mm, 22*mm, 22*mm, CONTENT_W - 100*mm]
        ins_tbl = Table(ins_data, colWidths=ins_widths)
        ins_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), SLATE),
            ("TEXTCOLOR", (0,0), (-1,0), WHITE),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 7.5),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [WHITE, CREAM]),
            ("TOPPADDING", (0,0), (-1,-1), 3),
            ("BOTTOMPADDING", (0,0), (-1,-1), 3),
            ("LINEBELOW", (0,0), (-1,-1), 0.3, RULE),
            ("BOX", (0,0), (-1,-1), 0.5, RULE),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
        ]))
        story.append(ins_tbl)

    story.append(PageBreak())

    # ── PAGE 6: Conclusion ────────────────────────────────────────────────────
    story.append(SectionHeader("§8  CONCLUSION & RISK/REWARD"))
    story.append(SP(2))
    story.append(CalloutBox(R["conclusion"], bg=HexColor("#FDF1F1"), border=ACCENT))
    story.append(SP(4))

    # Risk / reward summary table
    rr_data = [
        [P("", "cell_bold"),
         P("Bear", "cell_bold", textColor=BEAR_RED, alignment=TA_CENTER),
         P("Base", "cell_bold", textColor=SLATE, alignment=TA_CENTER),
         P("Bull", "cell_bold", textColor=GREEN, alignment=TA_CENTER)],
        [P("Fair Value", "cell_bold"),
         P("$31.51", "cell_r", textColor=BEAR_RED),
         P("$55.52", "cell_r", textColor=SLATE),
         P("$96.05", "cell_r", textColor=GREEN)],
        [P("vs. Price ($77.84)", "cell_bold"),
         P("–59.5%", "cell_r", textColor=BEAR_RED),
         P("–28.7%", "cell_r", textColor=ACCENT),
         P("+23.4%", "cell_r", textColor=GREEN)],
        [P("Advertising 2030", "cell_bold"),
         P("$4.0B", "cell_r"), P("$7.2B", "cell_r"), P("$10.0B", "cell_r")],
        [P("g_LT", "cell_bold"),
         P("3.5%", "cell_r"), P("5.0%", "cell_r"), P("6.0%", "cell_r")],
        [P("Exit Multiple", "cell_bold"),
         P("12.3x", "cell_r"), P("16.5x", "cell_r"), P("22.8x", "cell_r")],
        [P("Operating Margin", "cell_bold"),
         P("30%", "cell_r"), P("36%", "cell_r"), P("38%", "cell_r")],
        [P("Evidence grade", "cell_bold"),
         P("MECHANISM /\nUNFIRED", "cell_r", textColor=BEAR_RED),
         P("EXTRAPOLATED\n(2026 CONTRACTED)", "cell_r", textColor=SLATE),
         P("EXTRAPOLATED\n(MoffettNathanson)", "cell_r", textColor=GREEN)],
    ]
    rr_col = [52*mm] + [(CONTENT_W - 52*mm)/3]*3
    rr_tbl = Table(rr_data, colWidths=rr_col)
    rr_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), SLATE),
        ("TEXTCOLOR", (0,0), (-1,0), WHITE),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [WHITE, CREAM]),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LINEBELOW", (0,0), (-1,-1), 0.3, RULE),
        ("BOX", (0,0), (-1,-1), 0.5, RULE),
        ("ALIGN", (1,0), (-1,-1), "CENTER"),
        ("BACKGROUND", (0,2), (-1,2), HexColor("#FDE8E8")),
        ("FONTNAME", (0,2), (-1,2), "Helvetica-Bold"),
    ]))
    story.append(rr_tbl)
    story.append(SP(4))

    # Catalysts to watch
    cats = R.get("catalysts_to_watch", [])
    if cats:
        story.append(P("CATALYSTS TO WATCH", "h3"))
        story.append(SP(1))
        cat_data = [[P("Theme", "cell_bold"), P("Horizon", "cell_bold"),
                     P("What to watch", "cell_bold"), P("Bull/Bear tell", "cell_bold")]]
        for cat in cats[:5]:
            if isinstance(cat, dict):
                cat_data.append([
                    P(cat.get("theme",""), "cell_bold"),
                    P(cat.get("horizon",""), "cell"),
                    P(cat.get("what_to_watch","")[:120], "cell"),
                    P(cat.get("bull_or_bear_tell","")[:80], "cell"),
                ])
        if len(cat_data) > 1:
            cat_widths = [30*mm, 18*mm, 70*mm, CONTENT_W - 118*mm]
            cat_tbl = Table(cat_data, colWidths=cat_widths)
            cat_tbl.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), SLATE),
                ("TEXTCOLOR", (0,0), (-1,0), WHITE),
                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                ("FONTSIZE", (0,0), (-1,-1), 7.5),
                ("ROWBACKGROUNDS", (0,1), (-1,-1), [WHITE, CREAM]),
                ("TOPPADDING", (0,0), (-1,-1), 3),
                ("BOTTOMPADDING", (0,0), (-1,-1), 3),
                ("LINEBELOW", (0,0), (-1,-1), 0.3, RULE),
                ("BOX", (0,0), (-1,-1), 0.5, RULE),
                ("VALIGN", (0,0), (-1,-1), "TOP"),
            ]))
            story.append(cat_tbl)
        story.append(SP(3))

    # Sources
    sources = R.get("sources", [])
    if sources:
        story.append(HR())
        story.append(P("SOURCES", "label"))
        def _src_str(s):
            return s if isinstance(s, str) else s.get("name", s.get("title", str(s)))
        src_list = sources if isinstance(sources, list) else list(sources)
        src_text = "  ·  ".join(_src_str(s) for s in src_list[:15])
        story.append(P(src_text, "body_sm"))
        story.append(SP(2))

    # Disclaimer
    story.append(HR())
    story.append(P(
        "<b>IMPORTANT DISCLAIMER:</b> This report was generated by the Atlas automated research "
        "engine (v3.0) on June 17, 2026. It is intended for institutional use only and does not "
        "constitute investment advice. All figures are based on publicly available information and "
        "Atlas's proprietary analytical framework. Past performance is not indicative of future "
        "results. Equity investments involve risk, including the possible loss of principal. "
        "The 10:1 stock split executed in mid-2025 is reflected throughout; all per-share figures "
        "are on a post-split basis.",
        "footer", alignment=TA_JUSTIFY, textColor=MUTED, fontSize=7
    ))

    # Build
    doc.build(story, onFirstPage=on_first_page, onLaterPages=on_page)
    print(f"PDF written: {out}")
    return str(out)

if __name__ == "__main__":
    build()
