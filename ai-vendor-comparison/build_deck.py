#!/usr/bin/env python3
"""Builds the AI vendor comparison deck (PPTX) with matplotlib charts.

Run:  python3 build_deck.py
Out:  charts/*.png  +  AI_Vendor_Comparison_Biomedicine.pptx
All figures are sourced; see README.md and the final slide of the deck.
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

HERE = os.path.dirname(os.path.abspath(__file__))
CHARTS = os.path.join(HERE, "charts")
os.makedirs(CHARTS, exist_ok=True)
OUT = os.path.join(HERE, "AI_Vendor_Comparison_Biomedicine.pptx")

INK    = RGBColor(0x1F, 0x2A, 0x33)
DARK   = RGBColor(0x0B, 0x3D, 0x2E)
ACCENT = RGBColor(0x15, 0x80, 0x3D)
GREY   = RGBColor(0x64, 0x74, 0x8B)
LIGHT  = RGBColor(0xF1, 0xF5, 0xF2)
WHITE  = RGBColor(0xFF, 0xFF, 0xFF)
ANTH   = "#D97757"
OPENAI = "#10A37F"
MSFT   = "#2563EB"
MISTR  = "#F97316"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.edgecolor": "#94A3B8",
    "axes.labelcolor": "#1F2A33",
    "text.color": "#1F2A33",
    "xtick.color": "#475569",
    "ytick.color": "#475569",
    "figure.facecolor": "white",
    "axes.facecolor": "white",
})

# ---------------------------------------------------------------- charts
def chart_dc_electricity():
    fig, ax = plt.subplots(figsize=(6.4, 3.5), dpi=200)
    years = ["2024", "2030 (base case)", "2035 (base case)"]
    total = [415, 945, 1200]
    ai = [118, 267, 380]
    x = range(len(years))
    ax.bar(x, total, width=0.55, color="#0B3D2E", label="All data centres")
    ax.bar(x, ai, width=0.55, color="#F97316", label="of which AI-optimised")
    for i, (t, a) in enumerate(zip(total, ai)):
        ax.text(i, t + 25, f"{t} TWh", ha="center", fontsize=10, fontweight="bold", color="#0B3D2E")
        ax.text(i, a / 2, f"AI: {a}", ha="center", va="center", fontsize=9, color="white", fontweight="bold")
    ax.text(1, 945 + 95, "= Japan's total electricity today", ha="center", fontsize=8.5, color="#475569", style="italic")
    ax.set_xticks(list(x)); ax.set_xticklabels(years)
    ax.set_ylabel("TWh / year")
    ax.set_ylim(0, 1400)
    ax.legend(loc="upper left", frameon=False, fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    p = os.path.join(CHARTS, "dc_electricity.png"); fig.savefig(p); plt.close(fig); return p

def chart_per_query():
    fig, ax = plt.subplots(figsize=(6.4, 3.5), dpi=200)
    labels = [
        "Median frontier text prompt\n(Google Gemini, Aug 2025)",
        "GPT-4o estimate (Epoch AI, 2025)",
        "ChatGPT average (CEO figure, Jun 2025)",
        "Legacy 2023 estimate (outdated)",
        "Reasoning / 'thinking' query\n(range 4-40 Wh)",
    ]
    vals = [0.24, 0.3, 0.34, 2.9, 20]
    colors = [OPENAI, OPENAI, OPENAI, "#94A3B8", ANTH]
    y = list(range(len(labels)))[::-1]
    ax.barh(y, vals, color=colors, height=0.6)
    for yi, v in zip(y, vals):
        ax.text(v * 1.15, yi, f"{v:g} Wh", va="center", fontsize=10, fontweight="bold")
    ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=8.5)
    ax.set_xscale("log")
    ax.set_xlim(0.1, 200)
    ax.set_xlabel("Energy per query (Wh, log scale)")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    p = os.path.join(CHARTS, "per_query.png"); fig.savefig(p); plt.close(fig); return p

def chart_footprint():
    q_year = (50 * 150 + 90 * 20) * 250
    kwh_base = q_year * 0.5 / 1000
    kwh_heavy = (50 * 150 * 5 + 90 * 20 * 0.4) * 250 / 1000
    grids = {"US grid\n(~380 g)": 380, "EU avg\n(~210 g)": 210, "Germany\n(~380 g)": 380,
             "France\n(~50 g)": 50, "Sweden\n(~40 g)": 40}
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.6, 3.4), dpi=200)
    a1.bar(["Base scenario\n(0.5 Wh/query)", "Heavy scenario\n(agentic/thinking mix)"],
           [kwh_base, kwh_heavy], color=["#15803D", "#0B3D2E"], width=0.5)
    for i, v in enumerate([kwh_base, kwh_heavy]):
        a1.text(i, v + 180, f"{v:,.0f} kWh/yr", ha="center", fontweight="bold", fontsize=10)
    a1.set_title("Annual inference energy (2.33 M queries/yr)", fontsize=11, fontweight="bold")
    a1.set_ylabel("kWh / year"); a1.set_ylim(0, 11500)
    a1.spines[["top", "right"]].set_visible(False)
    x = range(len(grids)); w = 0.38
    base = [kwh_base * g / 1000 for g in grids.values()]
    heavy = [kwh_heavy * g / 1000 for g in grids.values()]
    a2.bar([i - w/2 for i in x], base, width=w, color="#7DD3A8", label="Base scenario")
    a2.bar([i + w/2 for i in x], heavy, width=w, color="#0B3D2E", label="Heavy scenario")
    for i, (b, h) in enumerate(zip(base, heavy)):
        a2.text(i - w/2, b + 60, f"{b:,.0f}", ha="center", fontsize=8.5)
        a2.text(i + w/2, h + 60, f"{h:,.0f}", ha="center", fontsize=8.5, fontweight="bold")
    a2.set_xticks(list(x)); a2.set_xticklabels(list(grids.keys()), fontsize=8.5)
    a2.set_title("Annual CO2e by hosting region (kg)", fontsize=11, fontweight="bold")
    a2.set_ylabel("kg CO2e / year"); a2.set_ylim(0, 4300)
    a2.legend(frameon=False, fontsize=9)
    a2.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    p = os.path.join(CHARTS, "footprint.png"); fig.savefig(p); plt.close(fig); return p

def chart_swe():
    fig, ax = plt.subplots(figsize=(6.2, 3.6), dpi=200)
    models = ["Claude Opus 4.5\n(Anthropic)", "Claude Sonnet 4.5\n(Anthropic)", "GPT-5\n(OpenAI)", "Mistral Large 3\n(Mistral, base)"]
    vals = [80.9, 77.2, 72.8, 40]
    colors = [ANTH, ANTH, OPENAI, MISTR]
    bars = ax.bar(models, vals, color=colors, width=0.55)
    for b, v in zip(bars, vals):
        lbl = f"{v:.1f}%" if v != 40 else "~40%*"
        ax.text(b.get_x() + b.get_width()/2, v + 1.5, lbl, ha="center", fontweight="bold", fontsize=10)
    ax.set_ylabel("SWE-bench Verified solve rate (%)")
    ax.set_ylim(0, 95)
    ax.tick_params(axis="x", labelsize=8.5)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    p = os.path.join(CHARTS, "swe.png"); fig.savefig(p); plt.close(fig); return p

def chart_med():
    import numpy as np
    fig, ax = plt.subplots(figsize=(5.9, 3.4), dpi=200)
    models = ["GPT-5.2 (OpenAI)", "Claude Opus 4.6 (Anthropic)"]
    medqa = [94.2, 90.2]
    healthbench = [88.0, 77.0]
    x = np.arange(2); w = 0.34
    b1 = ax.bar(x - w/2, medqa, width=w, color=OPENAI, label="MedQA (USMLE-style)")
    b2 = ax.bar(x + w/2, healthbench, width=w, color=ANTH, label="HealthBench (physician rubrics)")
    for bars in (b1, b2):
        for b in bars:
            ax.text(b.get_x() + b.get_width()/2, b.get_height() + 1.2, f"{b.get_height():.1f}",
                    ha="center", fontsize=9.5, fontweight="bold")
    ax.set_xticks(x); ax.set_xticklabels(models, fontsize=9)
    ax.set_ylabel("Score (%)"); ax.set_ylim(0, 108)
    ax.legend(frameon=False, fontsize=8.5, loc="lower right")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    p = os.path.join(CHARTS, "med.png"); fig.savefig(p); plt.close(fig); return p

def chart_general():
    import numpy as np
    fig, ax = plt.subplots(figsize=(5.9, 3.4), dpi=200)
    models = ["GPT-5 (OpenAI)", "Claude Sonnet 4.5 (Anthropic)", "Mistral Large 3 (Mistral)"]
    mmlu = [94.2, 89.0, 85.5]
    gpqa = [85.7, 83.4, 43.9]
    x = np.arange(3); w = 0.34
    b1 = ax.bar(x - w/2, mmlu, width=w, color="#0B3D2E", label="MMLU (broad knowledge)")
    b2 = ax.bar(x + w/2, gpqa, width=w, color="#F97316", label="GPQA Diamond (expert science)")
    for bars in (b1, b2):
        for b in bars:
            ax.text(b.get_x() + b.get_width()/2, b.get_height() + 1.2, f"{b.get_height():.1f}",
                    ha="center", fontsize=9, fontweight="bold")
    ax.set_xticks(x); ax.set_xticklabels(models, fontsize=8.5)
    ax.set_ylabel("Score (%)"); ax.set_ylim(0, 108)
    ax.legend(frameon=False, fontsize=8.5, loc="lower right")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    p = os.path.join(CHARTS, "general.png"); fig.savefig(p); plt.close(fig); return p

def chart_cost():
    import numpy as np
    fig, ax = plt.subplots(figsize=(11.6, 3.4), dpi=200)
    labels = [
        "GitHub Copilot Business\n140 dev seats @ $19/mo",
        "M365 Copilot\n350 seats @ $21/mo",
        "Claude Team\n140 seats @ $20/mo",
        "API: Claude Sonnet 4.5\n$3/$15 per M tok (base/heavy)",
        "API: Mistral Large 3\n$0.50/$1.50 per M tok (base/heavy)",
    ]
    base = [140*19*12/1000, 350*21*12/1000, 140*20*12/1000, 20.9, 2.3]
    heavy = [140*19*12/1000, 350*21*12/1000, 140*20*12/1000, 55.8, 7.0]
    x = np.arange(len(labels)); w = 0.38
    a = ax.bar(x - w/2, base, width=w, color="#7DD3A8", label="Base usage scenario")
    b = ax.bar(x + w/2, heavy, width=w, color="#0B3D2E", label="Heavy usage scenario")
    for bars in (a, b):
        for bb in bars:
            ax.text(bb.get_x() + bb.get_width()/2, bb.get_height() + 1.2, f"${bb.get_height():,.1f}k",
                    ha="center", fontsize=8.5, fontweight="bold")
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=8.3)
    ax.set_ylabel("Annual cost (US$ thousands)")
    ax.set_ylim(0, 105)
    ax.legend(frameon=False, fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    p = os.path.join(CHARTS, "cost.png"); fig.savefig(p); plt.close(fig); return p

# ---------------------------------------------------------------- deck helpers
prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]
SW, SH = prs.slide_width, prs.slide_height

def add_slide():
    return prs.slides.add_slide(BLANK)

def rect(slide, x, y, w, h, fill, line=None):
    from pptx.enum.shapes import MSO_SHAPE
    sh = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    sh.fill.solid(); sh.fill.fore_color.rgb = fill
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = line
    sh.shadow.inherit = False
    return sh

def textbox(slide, x, y, w, h, runs, size=13, color=INK, bold=False, align=PP_ALIGN.LEFT,
            space_after=6, line_spacing=1.0):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    if isinstance(runs, str):
        runs = [runs]
    for i, item in enumerate(runs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(space_after)
        p.line_spacing = line_spacing
        if isinstance(item, tuple):
            text, kw = item
        else:
            text, kw = item, {}
        r = p.add_run(); r.text = text
        f = r.font
        f.size = Pt(kw.get("size", size)); f.bold = kw.get("bold", bold)
        f.color.rgb = kw.get("color", color); f.name = "Calibri"
        if kw.get("italic"): f.italic = True
    return tb

def bullets(slide, x, y, w, h, items, size=13, gap=6):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame; tf.word_wrap = True
    for i, item in enumerate(items):
        lvl = 0; kw = {}
        if isinstance(item, tuple):
            if len(item) == 3:
                text, lvl, kw = item
            else:
                text, kw = item
        else:
            text = item
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(gap); p.line_spacing = 1.04
        p.level = lvl
        r = p.add_run()
        r.text = ("\u2022  " if lvl == 0 else "\u2013  ") + text
        f = r.font
        f.size = Pt(kw.get("size", size - (1 if lvl else 0)))
        f.bold = kw.get("bold", False)
        f.color.rgb = kw.get("color", INK); f.name = "Calibri"
    return tb

def header(slide, title, kicker=None, num=None):
    rect(slide, 0, 0, SW, Inches(0.92), DARK)
    rect(slide, 0, Inches(0.92), SW, Inches(0.045), ACCENT)
    textbox(slide, Inches(0.45), Inches(0.10), Inches(11.6), Inches(0.75),
            [(title, {"size": 24, "bold": True, "color": WHITE})], space_after=0)
    if kicker:
        textbox(slide, Inches(0.45), Inches(0.60), Inches(11.6), Inches(0.3),
                [(kicker, {"size": 11, "color": RGBColor(0xBB, 0xD8, 0xC9)})], space_after=0)
    if num is not None:
        textbox(slide, Inches(12.55), Inches(0.28), Inches(0.6), Inches(0.4),
                [(str(num), {"size": 13, "color": RGBColor(0xBB, 0xD8, 0xC9), "bold": True})],
                align=PP_ALIGN.RIGHT, space_after=0)
    textbox(slide, Inches(0.45), Inches(7.12), Inches(12.4), Inches(0.3),
            [("AI vendor comparison - internal draft - figures sourced, see final slide",
              {"size": 8.5, "color": GREY})], space_after=0)

def table(slide, x, y, w, h, rows, col_widths, font=10, header_font=10.5):
    n_r, n_c = len(rows), len(rows[0])
    gfx = slide.shapes.add_table(n_r, n_c, x, y, w, h)
    tbl = gfx.table
    tbl.first_row = True
    tbl.horz_banding = True
    total = sum(col_widths)
    for j, cw in enumerate(col_widths):
        tbl.columns[j].width = Emu(int(w * cw / total))
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            cell = tbl.cell(i, j)
            cell.margin_left = Inches(0.06); cell.margin_right = Inches(0.06)
            cell.margin_top = Inches(0.03); cell.margin_bottom = Inches(0.03)
            cell.vertical_anchor = MSO_ANCHOR.TOP
            tf = cell.text_frame; tf.word_wrap = True
            p = tf.paragraphs[0]
            r = p.add_run(); r.text = str(val)
            f = r.font; f.name = "Calibri"
            if i == 0:
                f.size = Pt(header_font); f.bold = True; f.color.rgb = WHITE
                cell.fill.solid(); cell.fill.fore_color.rgb = DARK
            else:
                f.size = Pt(font); f.color.rgb = INK
                cell.fill.solid()
                cell.fill.fore_color.rgb = WHITE if i % 2 else LIGHT
    return tbl

def pic(slide, path, x, y, w=None, h=None):
    return slide.shapes.add_picture(path, x, y, width=w, height=h)

# ================================================================ SLIDES
# 1 - title
s = add_slide()
rect(s, 0, 0, SW, SH, DARK)
rect(s, 0, Inches(4.62), SW, Inches(0.06), ACCENT)
textbox(s, Inches(0.9), Inches(2.0), Inches(11.5), Inches(2.2), [
    ("Choosing an AI provider for a European biomedicine company", {"size": 40, "bold": True, "color": WHITE}),
    ("Environment - data residency & law - ethics & existential risk - performance - cost",
     {"size": 19, "color": RGBColor(0xBB, 0xD8, 0xC9)}),
], space_after=14)
textbox(s, Inches(0.9), Inches(4.95), Inches(11.5), Inches(1.6), [
    ("Anthropic (Claude)  |  OpenAI (GPT)  |  Microsoft Copilot (platform)  |  Mistral AI",
     {"size": 16, "bold": True, "color": WHITE}),
    ("Comparison for a ~350-employee company using Copilot and Claude today - with estimated local footprint,",
     {"size": 13, "color": RGBColor(0xBB, 0xD8, 0xC9)}),
    ("global context, and biomedicine / office / coding performance. Internal draft - figures sourced on the last slide.",
     {"size": 13, "color": RGBColor(0xBB, 0xD8, 0xC9)}),
], space_after=6)

# 2 - scope & assumptions
s = add_slide()
header(s, "Scope, method and our assumptions", "What we compare, and the usage model behind the local footprint estimate", 2)
bullets(s, Inches(0.45), Inches(1.25), Inches(6.3), Inches(5.6), [
    "Context: biomedicine company, 350 employees, green profile, mission of improving the world; mindful of where data is stored and where inference runs (US vs EU).",
    "Currently using Microsoft Copilot (office + code) and Claude; no self-deployed AI yet.",
    "Compared dimensions: environmental impact (global + local), societal / moral / ethical posture, existential-risk stance, data residency & law, model performance (office work, coding, biomedicine), and cost.",
    "Benchmarks are proxies, not clinical validation: for patient-facing or diagnostic use the EU AI Act treats AI as high-risk regardless of vendor.",
    ("All numbers are public figures (IEA, Ember/EPA, LBNL, vendor disclosures, peer-reviewed LCAs, benchmark leaderboards); sources and assumptions on the final slide.", {"size": 12, "color": GREY}),
], size=13.5)
rect(s, Inches(7.0), Inches(1.25), Inches(5.9), Inches(5.55), LIGHT)
textbox(s, Inches(7.25), Inches(1.45), Inches(5.4), Inches(0.4),
        [("Usage model used for the local footprint", {"size": 14, "bold": True, "color": DARK})])
bullets(s, Inches(7.25), Inches(1.95), Inches(5.45), Inches(4.7), [
    "140 of 350 employees AI-active (40%)",
    "50 heavy users x 150 queries/day (code + agentic)",
    "90 light users x 20 queries/day",
    "250 working days -> 2.33 M queries / year",
    "Base scenario: 0.5 Wh per query (typical text)",
    "Heavy scenario: 5 Wh for heavy users (reasoning/agentic), 0.4 Wh light -> ~9.6 MWh/yr",
    "Water: ~30 mL per query (lifecycle incl. cooling)",
    ("Grid intensity used: US ~380, EU avg ~210, Germany ~380, France ~50, Sweden ~40 g CO2e/kWh", {"size": 11.5, "color": GREY}),
], size=12.5)

# 3 - players
s = add_slide()
header(s, "The four players at a glance", "Two model labs, one platform, one European challenger", 3)
table(s, Inches(0.45), Inches(1.25), Inches(12.45), Inches(5.5), [
    ["Vendor", "HQ / legal form", "What you actually buy", "Stated mission / identity", "Key structural fact"],
    ["Anthropic (Claude family)", "San Francisco, US - Public Benefit Corp", "Claude API / claude.ai, Claude Code; also via AWS Bedrock, GCP Vertex, Azure Foundry", "\"AI systems that people can rely on\"; Constitutional AI; safety-first brand", "PBC charter legally prioritises safety over shareholder returns; heaviest public safety investment"],
    ["OpenAI (GPT family)", "San Francisco, US - nonprofit parent, capped-profit arm", "ChatGPT, GPT API; enterprise via Azure OpenAI (exclusive cloud partner: Microsoft)", "\"Ensure AGI benefits all of humanity\"", "Largest compute buildout in the industry (Stargate, 10 GW target); no group-wide climate pledge"],
    ["Microsoft Copilot (platform)", "Redmond, US", "M365 Copilot (Word/Excel/Teams) + GitHub Copilot (code) - a multi-model platform (GPT, Claude, Gemini...) plus harness", "\"Empower every person and organisation\"", "Not a model maker: performance = chosen model + harness; strongest EU residency machinery (EU Data Boundary)"],
    ["Mistral AI", "Paris, France - EU company", "la Plateforme API, Le Chat; open weights (Apache-2.0) for self-hosting; Mistral Compute (EU GPUs)", "Open, portable, efficient AI; \"frontier AI in your hands\"", "Only EU-incorporated player -> no US CLOUD Act exposure; EU-hosted inference; mixture-of-experts efficiency"],
], [1.6, 1.7, 3.0, 2.6, 3.4], font=10)

# 4 - residency & law
s = add_slide()
header(s, "Data residency & legal exposure - storage and inference in the US vs EU",
       "GDPR + CLOUD Act + EU AI Act: where your prompts physically and legally go", 4)
table(s, Inches(0.45), Inches(1.2), Inches(12.45), Inches(4.6), [
    ["Route", "Default processing", "EU-only option today", "No training on your data", "US CLOUD Act exposure", "Notes"],
    ["M365 Copilot (EU tenant)", "EU Data Boundary - prompts/responses stored & processed in EU", "Yes (EUDB service since 2024)", "Yes (contractual)", "Residual - Microsoft is a US parent", "Exceptions: Bing web-search queries leave EUDB; Anthropic models in Copilot are currently excluded from EUDB"],
    ["GitHub Copilot Business/Enterprise", "US processing; no EU residency guarantee", "No - content controls & IP indemnity only", "Yes (Business/Enterprise)", "Yes", "Good for code; keep sensitive repos out or use self-hosted models"],
    ["OpenAI API / ChatGPT direct", "US", "No first-party EU region; via Azure OpenAI EU regions (Sweden, France, Germany...)", "Yes (API); zero-data-retention option", "Yes", "EU-US Data Privacy Framework certified; SCCs + TIA still needed"],
    ["Anthropic API direct", "US storage by default", "Only via AWS Bedrock EU inference profile (Frankfurt, Paris, Stockholm...) or Vertex EU - hyperscaler becomes the processor", "Yes; ZDR option", "Yes - Anthropic is a US company", "On Bedrock EU, data stays in EU geography and is not shared with Anthropic; ZDR standard"],
    ["Mistral la Plateforme", "EU (France / Sweden; check subprocessor list - US added for some features in 2025)", "Yes; or self-host open weights on your own/EU hardware = full control", "Yes; ZDR on request", "No - EU-incorporated operator", "Strongest sovereignty posture of the four; DPA under GDPR Art. 28"],
], [2.0, 2.2, 2.6, 1.7, 1.6, 2.6], font=9)
bullets(s, Inches(0.45), Inches(6.05), Inches(12.4), Inches(1.0), [
    ("Key point: EU hosting changes where data sits, not which jurisdiction the operating company answers to - AWS, Google and Microsoft are all US companies, so CLOUD Act risk remains (reduced, not eliminated) on hyperscaler EU regions. Only an EU-incorporated operator (Mistral) or self-hosting removes it.", {"bold": True, "size": 12}),
    ("Biomedicine: patient data is GDPR Art. 9 special-category data - a DPIA and EU processing are effectively mandatory; never enter patient data into any consumer AI tool.", {"size": 12}),
], size=12)

# 5 - global env
s = add_slide()
header(s, "Environment - the global picture", "Data-centre electricity is the fastest-growing load on power systems", 5)
pic(s, chart_dc_electricity(), Inches(0.45), Inches(1.3), w=Inches(6.6))
bullets(s, Inches(7.35), Inches(1.35), Inches(5.55), Inches(5.5), [
    "Data centres used ~415 TWh in 2024 = 1.5% of global electricity; IEA base case: ~945 TWh by 2030 (<3%), ~1,200 TWh by 2035. US (45%) + China (25%) drive ~80% of growth; Europe ~15%.",
    "AI-optimised servers were ~15% of data-centre energy in 2024 (~118 TWh), projected 239-295 TWh by 2030 - ~1% of global electricity.",
    "US data centres alone: ~176 TWh in 2023 (4.4% of US power), projected 325-580 TWh by 2028 (LBNL). Water: US data centres used ~17 billion gallons in 2023 (3x 2014).",
    "Training dominates one-off cost (GPT-3 = 1,287 MWh; Mistral Large 2 LCA: 20.4 kt CO2e + 281,000 m3 water over 18 months); inference is the recurring cost - that is what your usage adds to.",
    ("Takeaway: the footprint of one company's usage is small; the footprint of the industry is material and growing - vendor choice (region, efficiency, transparency) is where a buyer can act.", {"bold": True}),
], size=12.5)

# 6 - per-query env
s = add_slide()
header(s, "Environment - what one query costs", "Per-prompt energy has fallen ~30x in a year; reasoning modes erase the gains", 6)
pic(s, chart_per_query(), Inches(0.45), Inches(1.3), w=Inches(6.6))
bullets(s, Inches(7.35), Inches(1.35), Inches(5.55), Inches(5.5), [
    "Median frontier text prompt: 0.24 Wh, 0.03 g CO2e, 0.26 mL water (Google, comprehensive methodology, Aug 2025) = 9 seconds of TV. Epoch AI: ~0.3 Wh for GPT-4o; CEO figure for ChatGPT: ~0.34 Wh.",
    "Reasoning / extended-thinking queries cost ~10-100x more (~4-40 Wh) - heavy agentic coding sessions are the expensive case.",
    "Mistral's peer-reviewed LCA (ADEME/Carbone 4, 2025): one 400-token (~1 page) Le Chat reply = 1.14 g CO2e + 45 mL water including upstream hardware - the only full lifecycle disclosure by a frontier lab; MoE architecture activates few parameters per token.",
    "Water per query is small (0.26-45 mL depending on boundary and region) but concentrates in water-stressed regions (e.g. Texas, where Stargate sits).",
    ("Rule of thumb for procurement: model choice and mode (thinking on/off) matter more than vendor brand; pick EU regions with low-carbon grids (France ~50, Sweden ~40 g CO2/kWh vs US ~380).", {"bold": True}),
], size=12.5)

# 7 - local footprint
s = add_slide()
header(s, "Environment - our estimated footprint (350 employees)",
       "2.33 M queries/yr -> 1.2-9.6 MWh/yr -> 0.05-3.6 t CO2e depending on hosting region", 7)
pic(s, chart_footprint(), Inches(0.45), Inches(1.25), w=Inches(12.4))
bullets(s, Inches(0.45), Inches(5.05), Inches(12.4), Inches(2.0), [
    "Base scenario (1,163 kWh/yr): 0.06 t CO2e in France/Sweden vs 0.44 t on the US grid - about the same as driving 2,600 km in a petrol car (at 170 g/km). Heavy scenario (9,555 kWh/yr): 0.4-0.5 t in France/Sweden vs 3.6 t on the US grid = two round-trip transatlantic flights.",
    "Water: ~70 L/yr (base) to ~350 L/yr (heavy) at ~30 mL/query - negligible locally, but it lands where the data centre sits, not where you sit.",
    ("Hosting the same workload in France/Sweden instead of the US cuts CO2e by ~85-90%. Choosing la Plateforme (EU), Azure EU regions, or Bedrock EU inference profiles achieves this today.", {"bold": True}),
    ("Context: even the heavy scenario is ~0.01 t CO2e per employee per year - small next to commuting or flights; the leverage is in region + model choice, and in not feeding patient data to US-default tools.", {"size": 11.5, "color": GREY}),
], size=12.5)

# 8 - green profiles
s = add_slide()
header(s, "Green profiles - claims vs reported reality", "Who publishes numbers, who publishes pledges, and what the pledges look like in practice", 8)
table(s, Inches(0.45), Inches(1.2), Inches(12.45), Inches(5.3), [
    ["Company", "Public commitments", "Reported reality (latest reports)", "Transparency of footprint data"],
    ["Microsoft (Copilot platform)", "Carbon negative, water positive, zero waste by 2030; 100% renewable electricity matching (met FY2025); fleet WUE 0.27 L/kWh; zero-water cooling in all new designs from Aug 2024", "Total emissions +29% vs 2020 baseline (FY2023), ~+58% by FY2025 (20.3 Mt CO2e) - driven by AI data-centre construction; shifted from 24/7 carbon-free matching to annual matching", "Annual verified sustainability report; EU Data Boundary data-centre investment - the most mature of the four, with visible strain"],
    ["OpenAI", "No group-wide net-zero pledge; Stargate: $100B->$500B, 10 GW of US AI compute; Abilene TX campus 1.2 GW (~900k homes) in a water-stressed area", "Limited disclosure; only a CEO-stated ~0.34 Wh/query; compute concentrated in US (high-carbon grid, water stress)", "Minimal - system cards only; no per-model LCA"],
    ["Anthropic", "No public climate pledge; safety-first positioning; inference runs on AWS/GCP (renewable-matched, carbon-neutral-by-2040 / 24/7 CFE-by-2030 pledges)", "No per-model energy disclosure; footprint inherits hyperscaler grids - EU regions available via Bedrock/Vertex", "System cards + Responsible Scaling Policy; S-1 lists climate among systemic risks but no quantified footprint"],
    ["Mistral AI", "First peer-reviewed full LCA of a frontier model (ADEME/Carbone 4, 2025): training Large 2 = 20.4 kt CO2e, 281k m3 water; 1.14 g CO2e + 45 mL per 400-token reply; results published in ADEME Base Empreinte; advocates an industry eco-score", "Inference hosted in EU (France ~50 g, Sweden ~40 g CO2/kWh - ~70% nuclear French grid); own EU data centres (Paris campus); MoE models use less compute per token", "Highest of the four - only one with published lifecycle numbers; smallest absolute footprint"],
], [1.7, 3.6, 3.7, 3.4], font=9)

# 9 - societal / ethical
s = add_slide()
header(s, "Societal, moral and ethical aspects", "Governance, transparency, litigation and dual-use - from a human perspective", 9)
table(s, Inches(0.45), Inches(1.2), Inches(12.45), Inches(5.3), [
    ["Dimension", "Anthropic", "OpenAI", "Microsoft Copilot", "Mistral"],
    ["Mission & governance", "PBC charter: safety over profit; Constitutional AI; public model spec", "Nonprofit-origin charter; 2023 board crisis and safety-staff exits signal governance tension", "Commercial platform; Responsible AI Standard, ISO/IEC 42001, red-teaming (PyRIT)", "EU champion; open weights maximise portability and community oversight"],
    ["Transparency", "System cards, RSP, interpretability research, public risk estimates", "System cards, Preparedness Framework; less granular", "Copilot transparency notes; EUDB commitments; usage audit via Purview", "LCA + training-data summaries; GPAI Code of Practice signatory; open weights = inspectable"],
    ["Copyright / training-data litigation", "Author/publisher suits apply to all labs", "NYT v. OpenAI and others ongoing - unresolved precedent", "Copilot Business/Enterprise offers IP indemnity for output; still sued over training data", "Publishes training-data approach; Apache-2.0 weights shift responsibility to deployer"],
    ["Dual-use & misuse (bio/cyber)", "ASL-3 gates for CBRN uplift; evals before release", "Preparedness Framework tracks bio/cyber/self-improvement; may relax if rival ships first", "Usage policy + abuse monitoring; opted Copilot out of human abuse review (privacy trade-off)", "Open weights = no central kill switch; mitigated by EU AI Act duties and your own access controls"],
    ["Regulatory alignment (EU)", "Signed GPAI Code of Practice (Jul 2025); Art. 55 systemic-risk duties apply to its models", "Signed GPAI Code of Practice; Art. 55 duties apply", "Signed; EUDB + DPA machinery most mature", "Signed; as an EU company, directly subject to GDPR & AI Act - simplest compliance chain"],
], [1.7, 2.7, 2.7, 2.7, 2.6], font=9)

# 10 - x-risk
s = add_slide()
header(s, "Existential risk - what the labs themselves say, and what protects you",
       "\"Ending humanity\" talk taken seriously: safety frameworks, risk estimates, and your levers as a buyer", 10)
table(s, Inches(0.45), Inches(1.2), Inches(7.6), Inches(3.6), [
    ["Vendor", "Published safety framework", "Leadership risk statements"],
    ["Anthropic", "Responsible Scaling Policy v3.x: ASL-3 safeguards for frontier models (Opus 4.1+), CBRN/uplift evals, defined capability thresholds", "CEO p(doom) 10-25% (\"25% chance things go really, really badly\", 2025); S-1 warns of catastrophic/existential risk; co-signed \"Pacing the Frontier\""],
    ["OpenAI", "Preparedness Framework v2 (2025): tracks bio/chemical, cyber, self-improvement; halts at \"Critical\" until safeguards exist - but explicitly adjustable if a rival ships first", "CEO p(doom) ~2% (2025); AGI-race rhetoric; safety researchers have publicly left over pace (2024)"],
    ["Microsoft", "Frontier Governance Framework + Responsible AI Standard; co-founded Frontier Model Forum; Copilot guardrails & monitoring", "Corporate Responsible AI reporting; commercial pressure acknowledged internally"],
    ["Mistral", "GPAI Code of Practice signatory; model cards & evals; below the EU systemic-risk compute threshold, no ASL-style public framework yet", "Positions open weights + EU regulation as the governance model"],
], [1.15, 3.6, 2.85], font=9)
bullets(s, Inches(0.45), Inches(5.0), Inches(7.6), Inches(2.0), [
    ("EU AI Act Art. 55: models trained with >10^25 FLOPs are \"systemic risk\" - mandatory evaluations, risk mitigation, serious-incident reporting to the AI Office, cybersecurity; fines up to EUR 15M / 3% of turnover (enforcement from Aug 2026). Covers OpenAI's and Anthropic's frontier models.", {"size": 11.5}),
    ("Honest caveat: safety plans are mostly self-regulation; labs admit plans may not prevent extinction and may be relaxed under competitive pressure.", {"size": 11.5, "color": GREY}),
], size=11.5)
rect(s, Inches(8.3), Inches(1.2), Inches(4.6), Inches(5.7), LIGHT)
textbox(s, Inches(8.5), Inches(1.4), Inches(4.2), Inches(0.4),
        [("What this means for us as a buyer", {"size": 14, "bold": True, "color": DARK})])
bullets(s, Inches(8.5), Inches(1.9), Inches(4.25), Inches(4.9), [
    "In biomedicine, the near-term risk is dual-use biology (CBRN uplift) and patient harm - prefer vendors with published evals + ASL-style gating (Anthropic) and Art. 55 compliance.",
    "Keep a human in the loop: no autonomous clinical, diagnostic or treatment decisions (EU AI Act high-risk anyway).",
    "Procurement is a lever: contract for incident notification, no-training, residency SLAs; prefer vendors with published safety frameworks.",
    "Do not deploy agentic systems unsupervised on sensitive data; log and review (Art. 12 records).",
    "Support the slower lane: \"Pacing the Frontier\" signatories, EU AI Act enforcement, and efficient models (less compute = less risk surface).",
], size=11.5)

# 11 - coding perf
s = add_slide()
header(s, "Performance - coding and agentic work", "SWE-bench Verified: real GitHub issues, tests must pass; Copilot is the harness, not the model", 11)
pic(s, chart_swe(), Inches(0.45), Inches(1.3), w=Inches(6.3))
bullets(s, Inches(7.0), Inches(1.35), Inches(5.9), Inches(5.6), [
    "Claude leads agentic coding: Opus 4.5 ~81%, Sonnet 4.5 77.2% (82% with parallel compute) on SWE-bench Verified; GPT-5 ~73%; Mistral Large 3 (open-weight base) ~40%* (third-party evals; reasoning variants score higher but still trail).",
    "HumanEval (synthetic function writing) is saturated: all four >90% (Claude 4.x ~96%, Mistral Large 3 ~92%) - not a differentiator anymore.",
    "Harder agentic sets tell the truth: on SWE-bench Pro, even the best systems reach only ~23-46% - plan for human review of agent PRs.",
    "Copilot as platform: GitHub Copilot lets you pick the model (GPT-5.x, Claude Sonnet/Opus, Gemini...) and adds the harness (issue->PR agent, code review). Performance = chosen model + harness quality; Business $19/seat includes 1,900 AI credits/mo.",
    ("For biomedical code (bioinformatics pipelines, R/Python, clinical data formats): Claude and GPT-5 are strongest; Mistral Large 3 is credible for cost-sensitive batch work; self-hosted Mistral/Codestral keeps code on-prem.", {"bold": True}),
    ("*Mistral Large 3 SWE-bench figure is an approximate third-party estimate for the base model; the vendor has not published a Verified score.", {"size": 10, "color": GREY}),
], size=12.5)

# 12 - bio + office perf
s = add_slide()
header(s, "Performance - biomedicine and office work", "Medical knowledge is saturated; realistic clinical behaviour is not - and that is what matters", 12)
pic(s, chart_med(), Inches(0.45), Inches(1.35), w=Inches(6.1))
pic(s, chart_general(), Inches(6.85), Inches(1.35), w=Inches(6.1))
bullets(s, Inches(0.45), Inches(5.0), Inches(12.4), Inches(2.0), [
    "MedQA (USMLE-style): GPT-5.2 94.2%, Claude Opus 4.6 90.2% (independent Nature Medicine eval, 2026; vendor-reported highs up to ~96%). HealthBench (5,000 physician-written conversations, rubric-scored): GPT-5.2 88.0, Claude 77.0; HealthBench Hard: best model 46.2% - frontier models still fail hard clinical cases.",
    "Office / knowledge work (MMLU, GPQA expert science): GPT-5 94.2 / 85.7, Sonnet 4.5 ~89 / 83.4, Mistral Large 3 85.5 / 43.9 (base model, no reasoning mode). Computer-use (OSWorld): Claude models currently lead - relevant for Excel/ERP automation via agents.",
    "Mistral publishes no medical benchmark scores - treat biomedical claims as unverified; validate on your own de-identified cases.",
    ("Caveat for a biomedicine company: none of these are medical devices; EU AI Act classifies clinical decision support as high-risk (Annex III) - accuracy benchmarks do not equal clinical validation, and patient data must stay in the EU.", {"bold": True}),
], size=12)

# 13 - cost
s = add_slide()
header(s, "Cost for a 350-employee company", "Seats are predictable; API cost scales with tokens - Mistral is 5-6x cheaper per token", 13)
pic(s, chart_cost(), Inches(0.45), Inches(1.25), w=Inches(12.4))
bullets(s, Inches(0.45), Inches(5.0), Inches(12.4), Inches(2.0), [
    "Seat prices (list, late 2026): GitHub Copilot Business $19 / Enterprise $39 per user/mo; M365 Copilot ~$21-30 per user/mo add-on; Claude Team $20-25 per seat/mo; ChatGPT Business $25/seat.",
    "API usage (our model, 2.33 M queries/yr): Claude Sonnet 4.5 at $3/$15 per M tokens = ~$21k/yr base, ~$56k/yr heavy; Mistral Large 3 at $0.50/$1.50 = ~$2k-$7k/yr for the same workload - the cheapest frontier-class route, especially on EU hosting.",
    "Heavy agentic users blow through seat credits fast (credits = $0.01 each); budget overage or route heavy users to API with caps.",
    "Self-hosting Mistral open weights on own/EU GPUs: highest control and EU-only footprint, but hardware + ops cost - realistic for sensitive pipelines, not for 350 desktops.",
], size=12)

# 14 - scorecard
s = add_slide()
header(s, "Scorecard", "FULL = strong   HALF = partial / conditional   EMPTY = weak   -  scored for our profile (green, EU-minded, biomedicine)", 14)
table(s, Inches(0.45), Inches(1.25), Inches(12.45), Inches(5.4), [
    ["Dimension", "M365 / GitHub Copilot (Microsoft)", "OpenAI (direct / Azure)", "Anthropic (direct / Bedrock EU)", "Mistral (la Plateforme / self-hosted)"],
    ["EU residency by default", "FULL M365 (EUDB); HALF GitHub Copilot (US)", "HALF only via Azure EU regions", "HALF only via Bedrock/Vertex EU", "FULL EU-hosted; FULL self-hosted"],
    ["CLOUD Act exposure", "HALF (US parent)", "EMPTY (US company)", "EMPTY (US company)", "FULL none (EU company)"],
    ["No training on our data", "FULL", "FULL (API + ZDR option)", "FULL (ZDR option)", "FULL (ZDR on request)"],
    ["Environmental transparency", "HALF (pledges, emissions rising)", "EMPTY (minimal disclosure)", "EMPTY (system cards only)", "FULL (peer-reviewed LCA)"],
    ["Low-carbon inference region", "FULL EU Azure regions (e.g. Sweden)", "FULL via Azure EU / EMPTY direct US", "FULL via Bedrock EU (Frankfurt)", "FULL France/Sweden grid (~40-50 g)"],
    ["Safety / x-risk posture", "HALF (framework + monitoring)", "HALF (framework, race clause)", "FULL (RSP/ASL-3, most vocal)", "HALF (CoP signatory, open weights)"],
    ["Coding / agentic performance", "FULL (multi-model + harness)", "FULL (GPT-5/Codex)", "FULL (best Verified scores)", "HALF (good, trails frontier)"],
    ["Biomedicine performance", "FULL via model choice", "FULL (MedQA/HealthBench lead)", "FULL (close second)", "HALF (not published - verify)"],
    ["Office / knowledge work", "FULL (native M365 integration)", "FULL", "FULL", "HALF-FULL"],
    ["Price for 350 employees", "HALF ($32k-$126k/yr seats)", "HALF (seats + tokens)", "HALF (seats + tokens)", "FULL (cheapest API; free self-host licence)"],
    ["EU AI Act alignment", "FULL (EUDB, CoP signatory)", "HALF (CoP + Art. 55 duties)", "HALF (CoP + Art. 55 duties)", "FULL (EU-native)"],
], [2.3, 2.6, 2.4, 2.6, 2.6], font=9)

# 15 - recommendation
s = add_slide()
header(s, "Recommendation", "Layered setup: keep what works, pin everything to the EU, and measure", 15)
bullets(s, Inches(0.45), Inches(1.3), Inches(12.4), Inches(5.6), [
    ("1. Office work - keep M365 Copilot on an EU tenant: it is inside the EU Data Boundary, not used for training, GDPR DPA + ISO 42001. Configure it: disable Bing web grounding and disable Anthropic models inside Copilot (currently outside the EUDB), set Purview retention, and never enter patient data.", {"bold": True}),
    "2. Coding - keep GitHub Copilot Business ($19/seat) for everyday development (accept US processing under DPA/SCCs, or restrict sensitive repos); route frontier agentic work on sensitive biomedical code through Claude on AWS Bedrock with the EU inference profile (Frankfurt/Paris/Stockholm, zero retention) - best capability with EU processing.",
    "3. Highest sovereignty + lowest carbon - use Mistral la Plateforme (EU-hosted, French/Swedish low-carbon grid, ~$0.50/$1.50 per M tokens) for internal tools and batch workloads; for the most sensitive data, self-host Mistral open weights on your own or EU hardware - the only option with zero CLOUD Act exposure and zero data leaving.",
    "4. Guardrails for biomedicine - patient data (GDPR Art. 9) only in EU-processed, contractually no-training environments with a DPIA; human-in-the-loop for anything clinical (EU AI Act high-risk); require incident notification in contracts; prefer vendors with published safety frameworks (Anthropic RSP/ASL-3, OpenAI Preparedness Framework) and Art. 55 compliance.",
    "5. Reduce footprint by behaviour - default to smaller/faster models (Haiku / Mistral Small) for trivial tasks, keep thinking/reasoning mode off unless needed (10-100x energy per query), and pick EU inference regions: same workload, ~85-90% less CO2e.",
    "6. Measure instead of assuming - track tokens per user per month (Copilot/API dashboards), replace the 140-user assumption with real data, and re-run the footprint calc quarterly; estimated impact today: ~1.2-9.6 MWh and ~0.05-3.6 t CO2e/yr depending on region.",
], size=13, gap=10)

# 16 - sources
s = add_slide()
header(s, "Sources and assumptions", "Figures as published; prices and benchmarks change - re-check before external use", 16)
bullets(s, Inches(0.45), Inches(1.2), Inches(12.4), Inches(5.9), [
    "IEA, \"Energy and AI\" special report (Apr 2025): 415 TWh data centres 2024 (1.5% global), ~945 TWh by 2030; US 45% / China 25% / Europe 15% share - iea.org/reports/energy-and-ai",
    "Communications Sustainability (Nature Portfolio, 2026): AI-optimised data centres ~118 TWh (2024) -> 239-295 TWh (2030)",
    "Lawrence Berkeley National Laboratory, 2024 US Data Center Energy Usage Report: 176 TWh (2023), 325-580 TWh by 2028; ~17 billion gallons water (2023)",
    "Google technical paper (Aug 2025, arXiv:2508.15734): median Gemini prompt 0.24 Wh / 0.03 g CO2e / 0.26 mL; Epoch AI ~0.3 Wh (GPT-4o); S. Altman ~0.34 Wh per ChatGPT query (Jun 2025); Patterson et al. 2021: GPT-3 training 1,287 MWh",
    "Mistral AI LCA with ADEME / Carbone 4 / Resilio / Hubblo (Jul 2025): Large 2 training 20.4 kt CO2e, 281,000 m3 water; 1.14 g CO2e + 45 mL per 400-token response - mistral.ai/news",
    "Grid carbon intensity (Ember 2025 / EPA eGRID 2023 / ADEME): world ~473, US ~350-390, EU-27 ~180-230, France ~41-52, Sweden ~25-45, Germany ~350-400 g CO2e/kWh",
    "Microsoft 2024/2025 Environmental Sustainability Reports: emissions +29.1% vs 2020 (FY2023), ~20.3 Mt CO2e FY2025; 100% renewable matching met; fleet WUE 0.27 L/kWh; zero-water cooling in new builds",
    "Microsoft Learn: M365 Copilot privacy / EU Data Boundary; Anthropic models excluded from EUDB; Bing web queries outside EUDB - learn.microsoft.com/microsoft-365/copilot",
    "Anthropic via AWS Bedrock EU inference profiles / Vertex EU regions; first-party API stores in US; ZDR - docs.aws.amazon.com/bedrock, cloud.google.com/vertex-ai; Anthropic data-residency docs",
    "Mistral: EU hosting (France/Sweden), DPA, ZDR on request, Apache-2.0 open weights, US added to subprocessor list for some features (Feb 2025) - docs.mistral.ai; EU AI Act GPAI Code of Practice signatories (EC, Jul 2025): OpenAI, Anthropic, Microsoft, Mistral, Google...; Art. 55 systemic-risk duties (>10^25 FLOPs), fines EUR 15M / 3%",
    "Benchmarks: SWE-bench Verified (swebench.com; Opus 4.5 ~80.9%, Sonnet 4.5 77.2%, GPT-5 ~72.8%; SWE-bench Pro ~23-46%); HumanEval (Claude 4.x ~96%, Mistral Large 3 ~92%); Nature Medicine 2026 independent eval: MedQA GPT-5.2 94.2 / Claude Opus 4.6 90.2; HealthBench GPT-5.2 88.0 / Claude 77.0, Hard 46.2%; MMLU/GPQA vendor model cards (GPT-5 94.2/85.7, Sonnet 4.5 ~89/83.4, Mistral Large 3 85.5/43.9)",
    "Safety / x-risk: Anthropic RSP v3.x & ASL-3 (Opus 4.1+); Axios (Sep 2025) Amodei p(doom) 10-25%; OpenAI Preparedness Framework v2 (Apr 2025); EA Forum comparison of lab safety plans (2025)",
    "Prices (list, ~Nov 2026): GitHub Copilot Pro $10, Business $19, Enterprise $39 /user/mo (AI credits $0.01); M365 Copilot ~$21-30 /user/mo; Claude Team $20-25 /seat/mo, Sonnet 4.5 $3/$15 per M tokens; GPT-5 $1.25/$10; Mistral Large 3 $0.50/$1.50 - github.com/features/copilot/plans, console.anthropic.com, openai.com, docs.mistral.ai",
    ("Assumptions (ours, editable in build_deck.py): 140/350 AI-active staff; 50 heavy x 150 and 90 light x 20 queries/day; 250 workdays; 0.5 Wh/query base, 5 Wh heavy-agentic; ~30 mL water/query; 3k-in/1k-out tokens per heavy query for API cost; seat counts as above.", {"size": 11, "color": GREY}),
], size=10.5, gap=5)

prs.save(OUT)
print("saved", OUT, "slides:", len(prs.slides._sldIdLst))
