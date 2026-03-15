import json
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# ── Colours ──────────────────────────────────────────────────────────────────
AMBER_DARK   = colors.HexColor("#412402")
AMBER_MID    = colors.HexColor("#BA7517")
AMBER_LIGHT  = colors.HexColor("#FAEEDA")
TEAL_DARK    = colors.HexColor("#04342C")
TEAL_MID     = colors.HexColor("#1D9E75")
TEAL_LIGHT   = colors.HexColor("#E1F5EE")
GREEN_DARK   = colors.HexColor("#173404")
GREEN_LIGHT  = colors.HexColor("#EAF3DE")
GRAY_LIGHT   = colors.HexColor("#F1EFE8")
GRAY_MID     = colors.HexColor("#888780")
BORDER       = colors.HexColor("#D3D1C7")
BLACK        = colors.HexColor("#2C2C2A")
WHITE        = colors.white

W, H = A4  # 595 x 842 pts

def _wrap(c, text, font_name, font_size, max_width):
    """Wrap text using actual glyph widths. Returns list of lines."""
    words = text.split()
    lines, line = [], ""
    for word in words:
        test = (line + " " + word).strip()
        if c.stringWidth(test, font_name, font_size) <= max_width:
            line = test
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def draw_certificate(c: canvas, r: dict, cert_num: int):
    c.setPageSize(A4)

    # ── Outer border ────────────────────────────────────────────────────────
    c.setStrokeColor(BORDER)
    c.setLineWidth(0.5)
    c.roundRect(15, 15, W-30, H-30, 4, stroke=1, fill=0)
    c.setDash(4, 3)
    c.roundRect(22, 22, W-44, H-44, 3, stroke=1, fill=0)
    c.setDash()

    # ── Header band ─────────────────────────────────────────────────────────
    c.setFillColor(AMBER_LIGHT)
    c.roundRect(15, H-110, W-30, 95, 4, stroke=0, fill=1)
    c.setFillColor(AMBER_LIGHT)
    c.rect(15, H-110, W-30, 20, stroke=0, fill=1)

    c.setFillColor(AMBER_DARK)
    c.setFont("Helvetica", 8)
    c.drawCentredString(W/2, H-42, "BARREN WUFFET CAPITAL RESEARCH")

    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(W/2, H-68, "Dividend Intelligence Certificate")

    # ── Cert number + date strip ─────────────────────────────────────────────
    c.setFillColor(GRAY_LIGHT)
    c.rect(15, H-132, W-30, 26, stroke=0, fill=1)
    c.setFillColor(GRAY_MID)
    c.setFont("Helvetica", 8)
    c.drawString(30, H-122, f"Certificate No. BW-2026-{cert_num:04d}")
    from datetime import date
    c.drawRightString(W-30, H-122, f"Issued: {date.today().strftime('%d %B %Y')}")

    # ── Company name ─────────────────────────────────────────────────────────
    c.setFillColor(BLACK)
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(W/2, H-168, r.get("name", r["ticker"]))

    c.setFillColor(GRAY_MID)
    c.setFont("Helvetica", 9)
    meta = f"{r['ticker']} · {r.get('sector','—')} · {r.get('country','—')} · {r.get('currency','—')}"
    c.drawCentredString(W/2, H-184, meta)

    # ── Conviction badge ──────────────────────────────────────────────────────
    conviction = r.get("conviction_rating", "WATCH")
    badge_colors = {
        "STRONG BUY": (TEAL_LIGHT, TEAL_DARK),
        "BUY":        (TEAL_LIGHT, TEAL_DARK),
        "WATCH":      (AMBER_LIGHT, AMBER_DARK),
        "AVOID":      (colors.HexColor("#FCEBEB"), colors.HexColor("#501313")),
    }
    bg, fg = badge_colors.get(conviction, (GRAY_LIGHT, BLACK))
    bw = 110
    c.setFillColor(bg)
    c.roundRect(W/2-bw/2, H-212, bw, 20, 10, stroke=0, fill=1)
    c.setFillColor(fg)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(W/2, H-199, conviction)

    # ── Divider ───────────────────────────────────────────────────────────────
    y = H-224
    c.setStrokeColor(BORDER)
    c.setLineWidth(0.5)
    c.line(30, y, W-30, y)

    # ── Barren score circle ───────────────────────────────────────────────────
    cx, cy = W/2, H-268
    score = r.get("barren_score", 0)
    c.setFillColor(AMBER_LIGHT)
    c.circle(cx, cy, 34, stroke=0, fill=1)
    c.setStrokeColor(AMBER_MID)
    c.setLineWidth(1)
    c.circle(cx, cy, 34, stroke=1, fill=0)
    c.setFillColor(AMBER_DARK)
    c.setFont("Helvetica-Bold", 26)
    c.drawCentredString(cx, cy+6, str(score))
    c.setFont("Helvetica", 7)
    c.drawCentredString(cx, cy-10, "BARREN SCORE")

    # ── Sub scores ────────────────────────────────────────────────────────────
    c.setFillColor(GRAY_MID)
    c.setFont("Helvetica", 8)
    sub = (f"Dividend {r.get('dividend_score','—')}  ·  "
           f"Balance Sheet {r.get('balance_sheet_score','—')}  ·  "
           f"Sector Safety {r.get('sector_safety_score','—')}  ·  "
           f"Value {r.get('value_score','—')}  ·  "
           f"Growth {r.get('growth_score','—')}")
    c.drawCentredString(W/2, H-316, sub)

    # ── Divider ───────────────────────────────────────────────────────────────
    y = H-328
    c.setStrokeColor(BORDER)
    c.line(30, y, W-30, y)

    # ── Yield projections ─────────────────────────────────────────────────────
    c.setFillColor(BLACK)
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(W/2, H-346, "Projected Annual Yield (APY)")
    c.setFillColor(GRAY_MID)
    c.setFont("Helvetica", 8)
    c.drawCentredString(W/2, H-360, "Based on current price, dividend history and growth modelling")

    yields = [
        ("1 yr",  r.get("projected_yield_1y",  0)),
        ("3 yr",  r.get("projected_yield_3y",  0)),
        ("5 yr",  r.get("projected_yield_5y",  0)),
        ("10 yr", r.get("projected_yield_10y", 0)),
        ("20 yr", r.get("projected_yield_20y", 0)),
    ]

    box_w, box_h = 88, 58
    gap = 8
    total = len(yields) * box_w + (len(yields)-1) * gap
    start_x = (W - total) / 2
    y_top = H-440

    for i, (label, val) in enumerate(yields):
        bx = start_x + i * (box_w + gap)
        is_primary = (i == 2)  # 5yr is the hero
        bh = box_h + (10 if is_primary else 0)
        by = y_top - (10 if is_primary else 0)
        fill  = TEAL_LIGHT  if is_primary else GREEN_LIGHT
        txt   = TEAL_DARK   if is_primary else GREEN_DARK
        sw    = 1.0         if is_primary else 0.5
        c.setFillColor(fill)
        c.setStrokeColor(TEAL_MID if is_primary else colors.HexColor("#639922"))
        c.setLineWidth(sw)
        c.roundRect(bx, by, box_w, bh, 6, stroke=1, fill=1)
        c.setFillColor(txt)
        c.setFont("Helvetica", 8)
        c.drawCentredString(bx+box_w/2, by+bh-14, label)
        c.setFont("Helvetica-Bold", 18 if is_primary else 15)
        c.drawCentredString(bx+box_w/2, by+bh/2-4, f"{val:.1f}%")
        if is_primary:
            c.setFont("Helvetica", 7)
            c.drawCentredString(bx+box_w/2, by+10, "primary target")

    # ── Divider ───────────────────────────────────────────────────────────────
    y = H-458
    c.setStrokeColor(BORDER)
    c.setLineWidth(0.5)
    c.line(30, y, W-30, y)

    # ── Key metrics row ───────────────────────────────────────────────────────
    c.setFillColor(BLACK)
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(W/2, H-476, "Key Metrics")

    metrics = [
        ("Current yield",  f"{r.get('dividend_yield', 0):.2f}%"),
        ("5yr div CAGR",   f"{r.get('div_cagr_5y', 0):.1f}%"),
        ("P/E ratio",      f"{float(r.get('pe_ratio',0)):.1f}x" if r.get('pe_ratio') else "—"),
        ("Payout ratio",   f"{r.get('payout_ratio', 0):.0f}%"),
        ("ROE",            f"{r.get('roe', 0):.1f}%"),
    ]
    col_w = (W-60) / len(metrics)
    for i, (label, val) in enumerate(metrics):
        mx = 30 + i*col_w + col_w/2
        c.setFillColor(GRAY_MID)
        c.setFont("Helvetica", 8)
        c.drawCentredString(mx, H-496, label)
        c.setFillColor(BLACK)
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(mx, H-512, val)

    # ── Divider ───────────────────────────────────────────────────────────────
    y = H-526
    c.setStrokeColor(BORDER)
    c.line(30, y, W-30, y)

    # ── Thesis ────────────────────────────────────────────────────────────────
    TEXT_W   = W - 60          # usable text width (30 pt margins each side)
    LINE_H   = 13              # line height in points
    FOOTER_Y = 70              # keep content above this y to clear footer

    c.setFillColor(BLACK)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(30, H-544, "Barren's Thesis")

    thesis = r.get("thesis", "")
    thesis_lines = _wrap(c, thesis, "Helvetica", 8.5, TEXT_W)
    c.setFont("Helvetica", 8.5)
    c.setFillColor(BLACK)
    y = H - 560
    for ln in thesis_lines:
        if y < FOOTER_Y:
            break
        c.drawString(30, y, ln)
        y -= LINE_H

    # ── Risk ──────────────────────────────────────────────────────────────────
    y -= 10   # gap between thesis and risk
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(BLACK)
    c.drawString(30, y, "Key Risk")

    risk = r.get("key_risk", "")
    risk_lines = _wrap(c, risk, "Helvetica", 8.5, TEXT_W)
    c.setFont("Helvetica", 8.5)
    c.setFillColor(GRAY_MID)
    y -= 14
    for ln in risk_lines:
        if y < FOOTER_Y:
            break
        c.drawString(30, y, ln)
        y -= LINE_H

    # ── Barren quip box ───────────────────────────────────────────────────────
    quip = f"\"{r.get('barren_quip', '')}\""
    quip_lines = _wrap(c, quip, "Helvetica-Oblique", 8, TEXT_W - 20)
    QUIP_PAD  = 10
    quip_h    = len(quip_lines) * LINE_H + QUIP_PAD * 2

    y -= 12   # gap between risk text and quip box
    quip_box_bottom = max(y - quip_h, FOOTER_Y)

    c.setStrokeColor(BORDER)
    c.setDash(4, 3)
    c.setLineWidth(0.5)
    c.roundRect(30, quip_box_bottom, W-60, quip_h, 5, stroke=1, fill=0)
    c.setDash()

    c.setFont("Helvetica-Oblique", 8)
    c.setFillColor(GRAY_MID)
    text_y = quip_box_bottom + quip_h - QUIP_PAD - LINE_H + 3
    for ln in quip_lines:
        if text_y < quip_box_bottom + QUIP_PAD:
            break
        c.drawCentredString(W/2, text_y, ln)
        text_y -= LINE_H

    # ── Footer ────────────────────────────────────────────────────────────────
    c.setStrokeColor(BORDER)
    c.setLineWidth(0.5)
    c.line(30, 52, W-30, 52)
    c.setFillColor(GRAY_MID)
    c.setFont("Helvetica", 7)
    c.drawString(30, 40, "For informational purposes only. Not financial advice. Barren Wuffet is an autonomous AI research agent.")
    c.drawRightString(W-30, 40, "barrenwuffet.com")
    c.drawCentredString(W/2, 28, "© 2026 Barren Wuffet Capital Research · Powered by Claude AI · Data: Yahoo Finance")

def generate_all_certificates(json_file="scan_results.json", output_dir="certificates"):
    os.makedirs(output_dir, exist_ok=True)
    with open(json_file) as f:
        results = json.load(f)

    generated = []
    for i, r in enumerate(results):
        name  = r.get("name", r["ticker"]).replace(" ", "_").replace("/", "-")
        fname = f"{output_dir}/BW_{r['ticker'].replace('.','_')}_{name}.pdf"
        cv    = canvas.Canvas(fname, pagesize=A4)
        draw_certificate(cv, r, cert_num=i+1)
        cv.save()
        print(f"✅ Certificate generated: {fname}")
        generated.append(fname)

    print(f"\n🎉 {len(generated)} certificates saved to ./{output_dir}/")
    return generated

if __name__ == "__main__":
    print("=" * 60)
    print("  BARREN WUFFET — Certificate Generator")
    print("  'Every stock deserves its moment of glory!'")
    print("=" * 60)
    generate_all_certificates()