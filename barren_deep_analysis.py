"""
barren_deep_analysis.py
────────────────────────────────────────────────────────────────────────────
Barren Wuffett's deep intrinsic value research engine.
Runs all 5 valuation models, Norwegian tax analysis, annual report deep read,
enhanced conviction scoring, and a 2-page deep PDF certificate.

Usage:
    python barren_deep_analysis.py DNB.OL
    python barren_deep_analysis.py EQNR.OL
    python barren_deep_analysis.py ORK.OL
"""

import os, sys, json, re, math
import yfinance as yf
import pandas as pd
from datetime import date, datetime
from anthropic import Anthropic
from dotenv import load_dotenv
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

load_dotenv()
_client = Anthropic()

BASE      = os.path.dirname(os.path.abspath(__file__))
DEEP_DIR  = os.path.join(BASE, "certificates", "deep")
REPORTS   = os.path.join(BASE, "reports")
os.makedirs(DEEP_DIR,  exist_ok=True)
os.makedirs(REPORTS,   exist_ok=True)

W, H = A4   # 595 × 842 pts

# ── Colour palette (shared with barren_certificate.py) ───────────────────────
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
RED_LIGHT    = colors.HexColor("#FCEBEB")
RED_DARK     = colors.HexColor("#501313")
BLUE_LIGHT   = colors.HexColor("#EBF3FC")
BLUE_DARK    = colors.HexColor("#1A3D6E")

# ── Norwegian market constants ────────────────────────────────────────────────
# Update NORWAY_RF annually: 10yr Norwegian government bond yield
NORWAY_RF       = 0.041   # ~4.1% as of early 2026
EQUITY_RP       = 0.050   # Equity risk premium for Norwegian stocks
CORP_TAX        = 0.22    # Norwegian corporate tax rate
TERMINAL_G      = 0.025   # DCF terminal growth (long-run Norwegian GDP)

# Fritaksmetoden: 3% of dividends are included in taxable income
FRITAKS_TAXABLE    = 0.03
FRITAKS_EFFECTIVE  = FRITAKS_TAXABLE * CORP_TAX   # 0.0066 effective tax rate
WITHHOLDING_STD    = 0.15  # Standard withholding tax (foreign investors)

# Norwegian market sector medians (P/E, P/B, EV/EBITDA, yield %)
SECTOR_MEDIANS = {
    "Energy":             {"pe": 10.5, "pb": 1.6, "ev_ebitda": 5.5,  "yield": 5.5},
    "Financial Services": {"pe": 11.0, "pb": 1.4, "ev_ebitda": None, "yield": 5.5},
    "Banking":            {"pe": 11.0, "pb": 1.4, "ev_ebitda": None, "yield": 5.5},
    "Insurance":          {"pe": 13.0, "pb": 1.8, "ev_ebitda": 9.0,  "yield": 4.5},
    "Consumer Staples":   {"pe": 16.0, "pb": 3.0, "ev_ebitda": 11.0, "yield": 3.5},
    "Communication Services": {"pe": 14.0, "pb": 2.5, "ev_ebitda": 8.0, "yield": 5.0},
    "Materials":          {"pe": 12.0, "pb": 1.5, "ev_ebitda": 7.0,  "yield": 4.5},
    "Aquaculture":        {"pe": 14.0, "pb": 2.0, "ev_ebitda": 9.0,  "yield": 4.0},
    "Industrials":        {"pe": 15.0, "pb": 2.5, "ev_ebitda": 10.0, "yield": 3.0},
    "Technology":         {"pe": 25.0, "pb": 4.0, "ev_ebitda": 15.0, "yield": 1.5},
    "Real Estate":        {"pe": 20.0, "pb": 1.0, "ev_ebitda": 16.0, "yield": 4.0},
    "Shipping":           {"pe": 7.0,  "pb": 0.9, "ev_ebitda": 5.0,  "yield": 8.0},
    "Oil Services":       {"pe": 12.0, "pb": 1.5, "ev_ebitda": 7.0,  "yield": 5.5},
    "default":            {"pe": 14.0, "pb": 2.0, "ev_ebitda": 10.0, "yield": 4.0},
}


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — DATA FETCHING
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_deep_data(ticker: str) -> dict:
    """Fetch comprehensive yfinance data including financial statement history."""
    stock = yf.Ticker(ticker)
    info  = stock.info

    try:
        financials = stock.financials        # Annual income statement
        cashflow   = stock.cashflow          # Annual cash flow
        balance    = stock.balance_sheet     # Annual balance sheet
    except Exception:
        financials = cashflow = balance = pd.DataFrame()

    dividends = stock.dividends              # All historical dividend payments
    price_hist = stock.history(period="5y")  # 5yr price history

    # Aggregate dividends by calendar year
    div_by_year = {}
    if len(dividends) > 0:
        for ts, amt in dividends.items():
            yr = ts.year if hasattr(ts, "year") else int(str(ts)[:4])
            div_by_year[yr] = round(div_by_year.get(yr, 0) + amt, 4)

    return {
        "info":        info,
        "financials":  financials,
        "cashflow":    cashflow,
        "balance":     balance,
        "dividends":   div_by_year,
        "price_hist":  price_hist,
    }


def _row(df: pd.DataFrame, *keys) -> list:
    """Pull a row from a financial DataFrame by trying multiple row names."""
    for key in keys:
        if df is not None and not df.empty and key in df.index:
            vals = df.loc[key].dropna().tolist()
            return [float(v) for v in vals if v is not None]
    return []


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — VALUATION MODELS
# ═══════════════════════════════════════════════════════════════════════════════

def _calc_cost_of_equity(info: dict) -> float:
    beta = info.get("beta") or 1.0
    beta = max(0.5, min(beta, 2.5))   # clamp to sensible range
    return NORWAY_RF + beta * EQUITY_RP


def _calc_wacc(info: dict, cashflow: pd.DataFrame) -> float:
    ke         = _calc_cost_of_equity(info)
    market_cap = info.get("marketCap") or 1
    total_debt = info.get("totalDebt") or 0

    # Cost of debt: interest expense / total debt (or 4.5% fallback)
    interest = _row(cashflow, "Interest Expense", "InterestExpense")
    if interest and total_debt > 0:
        kd = abs(interest[0]) / total_debt
        kd = max(0.01, min(kd, 0.12))   # clamp 1–12%
    else:
        kd = 0.045

    D, E  = total_debt, market_cap
    total = D + E
    wacc  = (E / total) * ke + (D / total) * kd * (1 - CORP_TAX) if total > 0 else ke
    return round(max(wacc, 0.04), 4)    # floor at 4%


def _ddm(info: dict, ke: float) -> dict:
    """Dividend Discount Model: Gordon Growth + simple 2-stage."""
    div_rate    = info.get("dividendRate") or 0
    price       = info.get("currentPrice") or info.get("regularMarketPrice") or 1
    if div_rate <= 0:
        return {"gordon": None, "multistage": None, "note": "No dividend"}

    payout   = info.get("payoutRatio") or 0.5
    roe      = info.get("returnOnEquity") or 0.10
    g_retain = max(0.0, (1 - payout) * roe)   # sustainable growth

    # Long-term growth must leave a minimum 2% spread below ke (prevents explosion)
    g_lt     = min(g_retain, ke - 0.02, TERMINAL_G + 0.015)
    g_lt     = max(g_lt, 0.0)

    # Gordon Growth Model
    spread = ke - g_lt
    if spread > 0.005:
        gordon = round(div_rate * (1 + g_lt) / spread, 2)
        # Sanity cap: no more than 10× current price
        gordon = min(gordon, price * 10)
    else:
        gordon = None

    # 2-stage DDM: 5yr at g_stage1, then terminal at TERMINAL_G
    g_stage1  = min(g_retain, 0.10)
    pv_stage1 = sum(
        div_rate * (1 + g_stage1) ** t / (1 + ke) ** t
        for t in range(1, 6)
    )
    d5    = div_rate * (1 + g_stage1) ** 5
    tv    = d5 * (1 + TERMINAL_G) / (ke - TERMINAL_G) if ke > TERMINAL_G else None
    tv_pv = tv / (1 + ke) ** 5 if tv else 0
    multistage = round(pv_stage1 + tv_pv, 2) if tv else None
    if multistage:
        multistage = min(multistage, price * 10)

    return {"gordon": gordon, "multistage": multistage,
            "g_stage1_pct": round(g_stage1 * 100, 1),
            "g_terminal_pct": round(TERMINAL_G * 100, 1)}


def _dcf(info: dict, cashflow: pd.DataFrame, wacc: float) -> dict:
    """10-year DCF with bear / base / bull FCF growth scenarios.
    Skipped for banks/financials where FCF is not a meaningful metric."""
    sector = info.get("sector", "")
    if any(s in sector for s in ("Financial", "Banking", "Insurance")):
        return {"bear": None, "base": None, "bull": None,
                "note": "DCF not applicable for financial sector"}

    shares = info.get("sharesOutstanding") or 1
    fcf_vals = _row(cashflow, "Free Cash Flow", "FreeCashFlow")
    if not fcf_vals or shares == 0:
        return {"bear": None, "base": None, "bull": None, "note": "No FCF data"}

    fcf = fcf_vals[0]
    if fcf <= 0:
        return {"bear": None, "base": None, "bull": None, "note": "Negative FCF"}

    # Historical FCF CAGR capped at realistic range
    if len(fcf_vals) >= 2:
        n_years = min(len(fcf_vals) - 1, 3)
        oldest  = fcf_vals[min(n_years, len(fcf_vals)-1)]
        if oldest > 0:
            hist_cagr = (fcf_vals[0] / oldest) ** (1 / n_years) - 1
        else:
            hist_cagr = 0.03
    else:
        hist_cagr = 0.03

    # Hard cap: FCF CAGR of 12% max (prevents terminal value explosions)
    hist_cagr = max(-0.10, min(hist_cagr, 0.12))

    # Bear = 50th %, Base = 75th %, Bull = 90th percentile
    g_bear  = max(0.0,  hist_cagr * 0.50)
    g_base  = max(0.02, hist_cagr)
    g_bull  = min(0.12, hist_cagr * 1.50)

    results = {}
    for label, g in [("bear", g_bear), ("base", g_base), ("bull", g_bull)]:
        cf, pv = fcf, 0.0
        for t in range(1, 11):
            cf  *= (1 + g)
            pv  += cf / (1 + wacc) ** t
        tv     = cf * (1 + TERMINAL_G) / (wacc - TERMINAL_G) if wacc > TERMINAL_G else 0
        tv_pv  = tv / (1 + wacc) ** 10
        total_equity = (pv + tv_pv) + (info.get("totalCash") or 0) - (info.get("totalDebt") or 0)
        per_share = round(total_equity / shares, 2)
        results[label] = per_share

    results["g_bear_pct"] = round(g_bear * 100, 1)
    results["g_base_pct"] = round(g_base * 100, 1)
    results["g_bull_pct"] = round(g_bull * 100, 1)
    results["wacc_pct"]   = round(wacc * 100, 2)
    return results


def _epv(info: dict, financials: pd.DataFrame, wacc: float) -> dict:
    """Earnings Power Value: normalized 5yr earnings / cost of capital."""
    shares   = info.get("sharesOutstanding") or 1
    # Try to get net income history (up to 4 years from yfinance)
    ni_vals  = _row(financials, "Net Income", "NetIncome",
                    "Net Income Common Stockholders")
    if not ni_vals:
        eps = info.get("trailingEps") or 0
        ni_vals = [eps * shares] if eps else []

    if not ni_vals or shares == 0:
        return {"value": None, "note": "No earnings data"}

    # Normalize: simple average, exclude outliers (remove min if >3 values)
    if len(ni_vals) >= 3:
        ni_sorted = sorted(ni_vals)
        ni_use    = ni_sorted[1:]   # drop the lowest year
    else:
        ni_use = ni_vals

    normalized_eps = sum(ni_use) / len(ni_use) / shares
    if normalized_eps <= 0:
        return {"value": None, "note": "Negative normalized earnings"}

    epv = round(normalized_eps / wacc, 2)
    return {"value": epv,
            "normalized_eps": round(normalized_eps, 2),
            "years_used": len(ni_use),
            "cost_of_capital_pct": round(wacc * 100, 2)}


def _nav(info: dict, balance: pd.DataFrame) -> dict:
    """Net Asset Value: book value adjusted, vs current price."""
    shares = info.get("sharesOutstanding") or 1
    price  = info.get("currentPrice") or info.get("regularMarketPrice") or 0

    bv_per_share = info.get("bookValue")
    if bv_per_share is None:
        eq_vals = _row(balance, "Stockholders Equity", "Total Equity Gross Minority Interest",
                       "Common Stock Equity")
        bv_per_share = eq_vals[0] / shares if eq_vals and shares > 0 else None

    if bv_per_share is None:
        return {"value": None, "note": "No book value data"}

    # Premium/discount to book
    premium = round((price / bv_per_share - 1) * 100, 1) if bv_per_share > 0 else None
    return {
        "value":         round(bv_per_share, 2),
        "premium_pct":   premium,
        "note":          f"{abs(premium):.0f}% {'premium' if premium and premium > 0 else 'discount'} to book" if premium is not None else "",
    }


def _relative_val(info: dict) -> dict:
    """Implied fair value from P/E, P/B, EV/EBITDA vs sector medians."""
    sector    = info.get("sector", "default")
    medians   = SECTOR_MEDIANS.get(sector) or SECTOR_MEDIANS["default"]
    price     = info.get("currentPrice") or info.get("regularMarketPrice") or 0
    shares    = info.get("sharesOutstanding") or 1

    eps   = info.get("trailingEps")
    bv    = info.get("bookValue")
    ebitda = info.get("ebitda")
    ev    = info.get("enterpriseValue")
    div_yield = (info.get("dividendYield") or 0)   # already as %

    implied = {}

    if eps and eps > 0 and medians.get("pe"):
        implied["pe"] = round(eps * medians["pe"], 2)

    if bv and bv > 0 and medians.get("pb"):
        implied["pb"] = round(bv * medians["pb"], 2)

    if ebitda and ebitda > 0 and ev and ev > 0 and medians.get("ev_ebitda"):
        net_debt   = (info.get("totalDebt") or 0) - (info.get("totalCash") or 0)
        equity_val = ebitda * medians["ev_ebitda"] - net_debt
        implied["ev_ebitda"] = round(equity_val / shares, 2) if shares > 0 else None

    if div_yield > 0 and medians.get("yield"):
        annual_div = info.get("dividendRate") or 0
        if annual_div > 0:
            implied["yield"] = round(annual_div / (medians["yield"] / 100), 2)

    if not implied:
        return {"implied": {}, "bear": None, "base": None, "bull": None}

    vals  = [v for v in implied.values() if v and v > 0]
    base  = round(sum(vals) / len(vals), 2) if vals else None
    bear  = round(min(vals), 2) if vals else None
    bull  = round(max(vals), 2) if vals else None

    return {
        "implied": implied,
        "bear": bear, "base": base, "bull": bull,
        "sector_medians_used": medians,
        "sector": sector,
    }


def run_valuation_models(ticker: str, deep_data: dict) -> dict:
    """Run all 5 models. Returns per-model results + combined fair value range."""
    info       = deep_data["info"]
    cashflow   = deep_data["cashflow"]
    financials = deep_data["financials"]
    balance    = deep_data["balance"]
    price      = info.get("currentPrice") or info.get("regularMarketPrice") or 0

    wacc = _calc_wacc(info, cashflow)
    ke   = _calc_cost_of_equity(info)

    models = {
        "ddm":      _ddm(info, ke),
        "dcf":      _dcf(info, cashflow, wacc),
        "epv":      _epv(info, financials, wacc),
        "nav":      _nav(info, balance),
        "relative": _relative_val(info),
    }

    # Collect all valid model point estimates, then use percentiles for range
    all_points = []

    ddm = models["ddm"]
    if ddm.get("gordon")     and ddm["gordon"]     > 0: all_points.append(ddm["gordon"])
    if ddm.get("multistage") and ddm["multistage"] > 0: all_points.append(ddm["multistage"])

    dcf = models["dcf"]
    if dcf.get("bear") and dcf["bear"] > 0: all_points.append(dcf["bear"])
    if dcf.get("base") and dcf["base"] > 0: all_points.append(dcf["base"])
    if dcf.get("bull") and dcf["bull"] > 0: all_points.append(dcf["bull"])

    if models["epv"].get("value") and models["epv"]["value"] > 0:
        all_points.append(models["epv"]["value"])

    if models["nav"].get("value") and models["nav"]["value"] > 0:
        all_points.append(models["nav"]["value"])

    rel = models["relative"]
    if rel.get("bear") and rel["bear"] > 0: all_points.append(rel["bear"])
    if rel.get("base") and rel["base"] > 0: all_points.append(rel["base"])
    if rel.get("bull") and rel["bull"] > 0: all_points.append(rel["bull"])

    # Sanity filter: remove outliers beyond 4× current price
    if price > 0:
        all_points = [v for v in all_points if v <= price * 4]

    if not all_points:
        fv_low = fv_mid = fv_high = None
        mos = None
    else:
        all_points.sort()
        n       = len(all_points)
        # 25th / 50th / 75th percentile of model outputs
        fv_low  = round(all_points[max(0, int(n * 0.25))], 2)
        fv_mid  = round(all_points[n // 2], 2)
        fv_high = round(all_points[min(n-1, int(n * 0.75))], 2)
        mos     = round((fv_mid - price) / fv_mid * 100, 1) if fv_mid and price else None

    return {
        "models":     models,
        "wacc_pct":   round(wacc * 100, 2),
        "ke_pct":     round(ke   * 100, 2),
        "rf_pct":     round(NORWAY_RF * 100, 2),
        "fv_low":     fv_low,
        "fv_mid":     fv_mid,
        "fv_high":    fv_high,
        "current_price": price,
        "margin_of_safety_pct": mos,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — FRITAKSMETODEN CALCULATOR
# ═══════════════════════════════════════════════════════════════════════════════

def calc_tax_profiles(info: dict, is_osa_qualified: bool = True) -> dict:
    """Return after-tax yield for 3 Norwegian investor types."""
    gross_yield = info.get("dividendYield") or 0    # already in % form
    div_rate    = info.get("dividendRate") or 0
    price       = info.get("currentPrice") or info.get("regularMarketPrice") or 1

    if gross_yield == 0 and div_rate > 0:
        gross_yield = div_rate / price * 100

    def after_tax(gross_pct: float, effective_rate: float) -> float:
        return round(gross_pct * (1 - effective_rate), 2)

    return {
        "gross_yield_pct": round(gross_yield, 2),
        "corporate_fritaks": {
            "label":          "Norwegian Corporate (AS/ASA)",
            "structure":      "Fritaksmetoden",
            "note":           "3% of dividends taxable at 22%",
            "effective_rate": round(FRITAKS_EFFECTIVE * 100, 2),
            "net_yield_pct":  after_tax(gross_yield, FRITAKS_EFFECTIVE),
            "qualifies":      is_osa_qualified,
        },
        "personal_ask": {
            "label":          "Norwegian Personal (Aksjesparekonto)",
            "structure":      "Aksjesparekonto (ASK)",
            "note":           "Tax deferred until withdrawal; ~37.84% when realised",
            "effective_rate": 0.0,
            "net_yield_pct":  round(gross_yield, 2),   # fully re-invested until exit
            "qualifies":      True,
        },
        "foreign_investor": {
            "label":          "Foreign Investor",
            "structure":      "Standard withholding",
            "note":           "15% withholding (treaty may reduce to 10–15%)",
            "effective_rate": round(WITHHOLDING_STD * 100, 2),
            "net_yield_pct":  after_tax(gross_yield, WITHHOLDING_STD),
            "qualifies":      None,
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — ANNUAL REPORT DEEP READER
# ═══════════════════════════════════════════════════════════════════════════════

_DEEP_REPORT_PROMPT = """\
You are Barren Wuffett's senior analyst. Analyse this annual report and return
ONLY a valid JSON object — no markdown, no preamble.

Extract ALL of the following fields as precisely as possible from the text.
Use "Not stated" if genuinely not mentioned. Use null for numeric fields with no data.

{{
  "report_year":               <integer>,
  "dividend_per_share":        <float or null — DPS paid in the year>,
  "proposed_dividend":         <float or null — DPS proposed for next year>,
  "dividend_coverage_ratio":   <float or null — FCF / total dividends paid>,
  "dividend_policy_verbatim":  <string — the exact dividend policy statement, quoted if possible>,
  "dividend_sustainability_commentary": <string — management quotes on sustainability>,
  "dividend_guidance":         <string — any explicit guidance or targets>,
  "capital_allocation_framework": <string — how management allocates capital>,
  "debt_ebitda":               <float or null — net debt / EBITDA>,
  "roic":                      <float or null — return on invested capital %>,
  "revenue_growth_pct":        <float or null>,
  "ebit_margin_pct":           <float or null>,
  "fcf_conversion_pct":        <float or null — FCF as % of net income>,
  "top_dividend_risks":        <list of 3 strings — direct risks to dividend>,
  "going_concern_flag":        <boolean — true if auditor mentions going concern>,
  "dividend_policy_clarity_score": <integer 1-10 — how explicit is the policy?>,
  "barren_annual_score":       <integer 1-100>,
  "barren_annual_notes":       <string — 2-3 Barren-voice sentences on findings>
}}

ANNUAL REPORT TEXT:
{text}
"""

def deep_annual_analysis(ticker: str, company_name: str) -> dict:
    """
    Fetch and deeply analyse the most recent annual report.
    Reuses barren_annual_reports infrastructure for PDF fetching.
    Returns rich structured data beyond the standard annual report module.
    """
    from barren_annual_reports import (
        DIRECT_PDF_URLS, IR_PAGES, EDGAR_CIKS,
        _get_edgar_text, _download_pdf, _extract_pdf_text,
        _truncate_text, _find_pdf_on_page, _pdf_path
    )

    target_years = [datetime.now().year - 1, datetime.now().year - 2]
    cache_path   = os.path.join(REPORTS, f"{ticker.replace('.','_')}_deep.json")

    # Use cache if fresh (< 7 days)
    if os.path.exists(cache_path):
        age = (datetime.now().timestamp() - os.path.getmtime(cache_path)) / 86400
        if age < 7:
            print(f"    📋 Using cached deep report ({ticker})")
            with open(cache_path) as f:
                return json.load(f)

    print(f"    🔍 Deep-reading annual report for {ticker}...")
    text = None
    year = target_years[0]

    if ticker in EDGAR_CIKS:
        text = _get_edgar_text(ticker)
    elif ticker in DIRECT_PDF_URLS or ticker in IR_PAGES:
        pdf_url = DIRECT_PDF_URLS.get(ticker)
        if not pdf_url:
            pdf_url = _find_pdf_on_page(IR_PAGES.get(ticker, ""), target_years)
        if pdf_url:
            pdf_dest = _pdf_path(ticker, year)
            if not os.path.exists(pdf_dest):
                _download_pdf(pdf_url, pdf_dest)
            if os.path.exists(pdf_dest):
                text = _extract_pdf_text(pdf_dest)

    if not text:
        print(f"    ⚠️  No annual report text available for {ticker}")
        return {}

    print(f"    🤖 Deep analysis with Claude ({len(text):,} chars)...")
    try:
        prompt = _DEEP_REPORT_PROMPT.format(text=_truncate_text(text))
        resp   = _client.messages.create(
            model     = "claude-sonnet-4-6",
            max_tokens = 2000,
            messages  = [{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
        result = json.loads(raw)
        result["fetched_at"] = datetime.now().isoformat()
        with open(cache_path, "w") as f:
            json.dump(result, f, indent=2)
        print(f"    ✅ Deep report saved ({ticker})")
        return result
    except Exception as e:
        print(f"    ❌ Deep analysis failed: {e}")
        return {}


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — ENHANCED CONVICTION SCORING (Claude-powered)
# ═══════════════════════════════════════════════════════════════════════════════

_DEEP_SCORE_PROMPT = """\
You are Barren Wuffett — eccentric, warm, obsessive about dividends and intrinsic value.

Analyse this Norwegian stock and return ONLY a valid JSON object.

STOCK DATA:
{stock_json}

VALUATION MODELS:
{val_json}

ANNUAL REPORT INTEL:
{annual_json}

Score each component 1–100. Be rigorous and honest. Penalise heavily for:
- High debt / negative FCF
- Payout ratio > 90%
- Dividend cuts in recent history
- Going concern language
- Overvalued vs all 5 models

Reward strongly for:
- Margin of safety > 20%
- Coverage ratio > 2.0
- ROIC > WACC
- Explicit, committed dividend policy
- Consecutive years of dividend growth

Return EXACTLY this JSON:
{{
  "barren_deep_score": <integer 1-100, overall deep conviction>,
  "intrinsic_value_score": <integer 1-100 — how cheap vs fair value?>,
  "dividend_quality_score": <integer 1-100 — coverage, growth, policy clarity>,
  "business_quality_score": <integer 1-100 — ROIC, moat, sector, management>,
  "risk_score": <integer 1-100, where 100 = very low risk>,
  "conviction_rating": <"STRONG BUY" | "BUY" | "WATCH" | "AVOID">,
  "projected_yield_1y":  <float, expected APY % in 1 year>,
  "projected_yield_3y":  <float, expected APY % over 3 years>,
  "projected_yield_5y":  <float, expected APY % over 5 years>,
  "projected_yield_10y": <float, expected APY % over 10 years>,
  "projected_yield_20y": <float, expected APY % over 20 years>,
  "deep_thesis": <3-4 sentence Barren-voice deep thesis, warm and rigorous>,
  "key_risk": <1 sentence on the main risk>,
  "dividend_policy_summary": <1-2 sentences summarising the dividend policy>,
  "barren_quip": <one short unhinged Barren remark — make it memorable>
}}
"""

def calc_deep_scores(stock_data: dict, valuation: dict, annual: dict) -> dict:
    """Call Claude to score all 4 components and produce enhanced thesis."""
    # Trim large fields before sending to save tokens
    trimmed_annual = {k: v for k, v in annual.items()
                      if k not in ("fetched_at",) and not isinstance(v, str) or len(str(v)) < 600}

    prompt = _DEEP_SCORE_PROMPT.format(
        stock_json  = json.dumps({k: v for k, v in stock_data.items()
                                  if not isinstance(v, dict) and not isinstance(v, list)
                                  and k not in ("description",)}, indent=2),
        val_json    = json.dumps(valuation, indent=2),
        annual_json = json.dumps(trimmed_annual, indent=2),
    )
    resp = _client.messages.create(
        model      = "claude-sonnet-4-6",
        max_tokens = 1200,
        messages   = [{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    return json.loads(raw)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — DEEP PDF CERTIFICATE (2 pages)
# ═══════════════════════════════════════════════════════════════════════════════

def _wrap(c, text: str, font: str, size: float, max_w: float) -> list:
    words, lines, line = str(text).split(), [], ""
    for w in words:
        test = (line + " " + w).strip()
        if c.stringWidth(test, font, size) <= max_w:
            line = test
        else:
            if line: lines.append(line)
            line = w
    if line: lines.append(line)
    return lines

def _header(c, company_name: str, ticker: str, cert_num: int, subtitle: str = "Deep Analysis Certificate"):
    c.setFillColor(AMBER_LIGHT)
    c.roundRect(15, H-110, W-30, 95, 4, stroke=0, fill=1)
    c.setFillColor(AMBER_LIGHT)
    c.rect(15, H-110, W-30, 20, stroke=0, fill=1)

    c.setFillColor(AMBER_DARK)
    c.setFont("Helvetica", 8)
    c.drawCentredString(W/2, H-42, "BARREN WUFFET CAPITAL RESEARCH")
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(W/2, H-68, subtitle)

    c.setFillColor(GRAY_LIGHT)
    c.rect(15, H-132, W-30, 26, stroke=0, fill=1)
    c.setFillColor(GRAY_MID)
    c.setFont("Helvetica", 8)
    c.drawString(30, H-122, f"Certificate No. BW-DEEP-2026-{cert_num:04d}")
    c.drawRightString(W-30, H-122, f"Issued: {date.today().strftime('%d %B %Y')}")

    c.setFillColor(BLACK)
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(W/2, H-166, company_name)
    c.setFillColor(GRAY_MID)
    c.setFont("Helvetica", 9)
    c.drawCentredString(W/2, H-182, ticker)

def _divider(c, y: float):
    c.setStrokeColor(BORDER)
    c.setLineWidth(0.5)
    c.line(30, y, W-30, y)

def _section_title(c, text: str, y: float):
    c.setFillColor(BLACK)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(30, y, text)

def _draw_valuation_table(c, valuation: dict, y_top: float) -> float:
    """Draw 5-model valuation table. Returns y after the table."""
    models  = valuation.get("models", {})
    price   = valuation.get("current_price", 0)
    currency = "NOK"
    col_x   = [30, 160, 265, 370, 475]   # label, bear, base, bull, note
    row_h   = 16
    header_h = 18

    def _fmt(v):
        return f"{v:,.0f}" if v and v > 0 else "—"

    rows = [
        ("Model",            "Bear",                      "Base",                   "Bull",              "Note"),
        ("DDM",
         _fmt(models.get("ddm",{}).get("gordon")),
         _fmt(models.get("ddm",{}).get("multistage")),
         "—",
         f"g={models.get('ddm',{}).get('g_stage1_pct','?')}% → {models.get('ddm',{}).get('g_terminal_pct','?')}%"),
        ("DCF",
         _fmt(models.get("dcf",{}).get("bear")),
         _fmt(models.get("dcf",{}).get("base")),
         _fmt(models.get("dcf",{}).get("bull")),
         f"WACC {valuation.get('wacc_pct','?')}%  g_bear/base/bull {models.get('dcf',{}).get('g_bear_pct','?')}/{models.get('dcf',{}).get('g_base_pct','?')}/{models.get('dcf',{}).get('g_bull_pct','?')}%"),
        ("EPV",
         _fmt(models.get("epv",{}).get("value")),
         "—", "—",
         f"Normalized EPS {_fmt(models.get('epv',{}).get('normalized_eps'))}"),
        ("NAV",
         _fmt(models.get("nav",{}).get("value")),
         "—", "—",
         models.get("nav",{}).get("note","Book value")),
        ("Relative",
         _fmt(models.get("relative",{}).get("bear")),
         _fmt(models.get("relative",{}).get("base")),
         _fmt(models.get("relative",{}).get("bull")),
         f"vs {models.get('relative',{}).get('sector','sector')} medians"),
    ]

    y = y_top
    for i, row in enumerate(rows):
        is_header = (i == 0)
        bg = AMBER_DARK if is_header else (GRAY_LIGHT if i % 2 == 0 else colors.white)
        fg = colors.white if is_header else BLACK
        rh = header_h if is_header else row_h
        c.setFillColor(bg)
        c.rect(30, y - rh, W-60, rh, stroke=0, fill=1)
        c.setFillColor(fg)
        fnt = "Helvetica-Bold" if is_header else "Helvetica"
        c.setFont(fnt, 8 if is_header else 7.5)
        for j, (xpos, cell) in enumerate(zip(col_x, row)):
            align = "center" if j > 0 else "left"
            if align == "center":
                mid = xpos + (col_x[j+1] - xpos) / 2 if j + 1 < len(col_x) else xpos + 40
                c.drawCentredString(mid, y - rh + 5, str(cell))
            else:
                c.drawString(xpos + 4, y - rh + 5, str(cell))
        c.setStrokeColor(BORDER)
        c.setLineWidth(0.3)
        c.line(30, y - rh, W-30, y - rh)
        y -= rh

    # Fair value range highlight bar
    y -= 4
    fv_low  = valuation.get("fv_low")
    fv_mid  = valuation.get("fv_mid")
    fv_high = valuation.get("fv_high")
    mos     = valuation.get("margin_of_safety_pct")

    c.setFillColor(TEAL_LIGHT)
    c.roundRect(30, y - 22, W-60, 22, 4, stroke=0, fill=1)
    c.setStrokeColor(TEAL_MID)
    c.setLineWidth(0.5)
    c.roundRect(30, y - 22, W-60, 22, 4, stroke=1, fill=0)

    c.setFillColor(TEAL_DARK)
    c.setFont("Helvetica-Bold", 9)
    fv_text = (f"Fair Value Range:  Low {_fmt(fv_low)}  ·  Mid {_fmt(fv_mid)}  ·  High {_fmt(fv_high)}"
               f"   |   Current: {_fmt(price)}"
               f"   |   Margin of Safety: {mos:+.1f}%" if mos is not None else f"  Current: {_fmt(price)}")
    c.drawCentredString(W/2, y - 14, fv_text)
    y -= 30

    return y


def _draw_tax_profiles(c, tax: dict, y_top: float) -> float:
    """Draw 3 investor tax profiles side by side. Returns y after."""
    profiles = [
        tax.get("corporate_fritaks", {}),
        tax.get("personal_ask", {}),
        tax.get("foreign_investor", {}),
    ]
    col_bg    = [GREEN_LIGHT, TEAL_LIGHT, BLUE_LIGHT]
    col_title = [GREEN_DARK,  TEAL_DARK,  BLUE_DARK]
    box_w     = (W - 70) / 3
    box_h     = 78
    y         = y_top

    for i, (p, bg, fg) in enumerate(zip(profiles, col_bg, col_title)):
        bx = 30 + i * (box_w + 5)
        c.setFillColor(bg)
        c.roundRect(bx, y - box_h, box_w, box_h, 5, stroke=0, fill=1)
        c.setStrokeColor(BORDER)
        c.setLineWidth(0.4)
        c.roundRect(bx, y - box_h, box_w, box_h, 5, stroke=1, fill=0)

        c.setFillColor(fg)
        c.setFont("Helvetica-Bold", 7.5)
        label_lines = _wrap(c, p.get("label", ""), "Helvetica-Bold", 7.5, box_w - 10)
        ly = y - 12
        for ln in label_lines[:2]:
            c.drawCentredString(bx + box_w/2, ly, ln)
            ly -= 10

        c.setFont("Helvetica", 7)
        c.setFillColor(GRAY_MID)
        c.drawCentredString(bx + box_w/2, ly, p.get("structure", ""))
        ly -= 10

        c.setFillColor(fg)
        c.setFont("Helvetica-Bold", 14)
        net = p.get("net_yield_pct", 0)
        c.drawCentredString(bx + box_w/2, ly - 2, f"{net:.2f}%")
        ly -= 14

        c.setFont("Helvetica", 6.5)
        c.setFillColor(GRAY_MID)
        c.drawCentredString(bx + box_w/2, ly, f"Effective tax: {p.get('effective_rate',0):.2f}%")
        ly -= 9
        note_lines = _wrap(c, p.get("note",""), "Helvetica", 6, box_w - 12)
        for ln in note_lines[:2]:
            c.drawCentredString(bx + box_w/2, ly, ln)
            ly -= 8

    return y - box_h - 8


def _draw_score_breakdown(c, scores: dict, y_top: float) -> float:
    """Draw 4 component scores. Returns y after."""
    items = [
        ("Intrinsic Value",   scores.get("intrinsic_value_score", 0),  "30% weight", AMBER_LIGHT, AMBER_DARK),
        ("Dividend Quality",  scores.get("dividend_quality_score", 0), "30% weight", TEAL_LIGHT,  TEAL_DARK),
        ("Business Quality",  scores.get("business_quality_score", 0), "25% weight", GREEN_LIGHT, GREEN_DARK),
        ("Risk (low=bad)",    scores.get("risk_score", 0),             "15% weight", BLUE_LIGHT,  BLUE_DARK),
    ]
    box_w = (W - 70) / 4
    box_h = 58
    y     = y_top

    for i, (label, score, weight, bg, fg) in enumerate(items):
        bx = 30 + i * (box_w + 4)
        c.setFillColor(bg)
        c.roundRect(bx, y - box_h, box_w, box_h, 5, stroke=0, fill=1)
        c.setStrokeColor(BORDER)
        c.setLineWidth(0.4)
        c.roundRect(bx, y - box_h, box_w, box_h, 5, stroke=1, fill=0)

        c.setFillColor(fg)
        c.setFont("Helvetica-Bold", 7.5)
        c.drawCentredString(bx + box_w/2, y - 13, label)

        c.setFont("Helvetica-Bold", 22)
        c.drawCentredString(bx + box_w/2, y - 36, str(score))

        c.setFillColor(GRAY_MID)
        c.setFont("Helvetica", 7)
        c.drawCentredString(bx + box_w/2, y - 48, weight)

    return y - box_h - 8


def _draw_dividend_chart(c, div_by_year: dict, y_top: float) -> float:
    """Draw simple bar chart of annual dividend per share. Returns y after."""
    if not div_by_year:
        c.setFillColor(GRAY_MID)
        c.setFont("Helvetica", 8)
        c.drawString(30, y_top - 20, "No dividend history available.")
        return y_top - 30

    years = sorted(div_by_year.keys())[-10:]   # last 10 years
    vals  = [div_by_year[y] for y in years]
    max_v = max(vals) if vals else 1
    if max_v == 0: max_v = 1

    chart_w = W - 60
    chart_h = 60
    bar_gap = 4
    n       = len(years)
    bar_w   = (chart_w - bar_gap * (n-1)) / max(n, 1)
    base_y  = y_top - chart_h

    # Axis
    c.setStrokeColor(BORDER)
    c.setLineWidth(0.5)
    c.line(30, base_y, W-30, base_y)   # x axis
    c.line(30, base_y, 30, y_top)     # y axis

    # Bars
    for i, (yr, val) in enumerate(zip(years, vals)):
        bx = 30 + i * (bar_w + bar_gap)
        bh = (val / max_v) * chart_h
        c.setFillColor(TEAL_LIGHT if i < n-1 else TEAL_MID)
        c.setStrokeColor(TEAL_MID)
        c.setLineWidth(0.3)
        c.rect(bx, base_y, bar_w, bh, stroke=1, fill=1)

        # Year label
        c.setFillColor(GRAY_MID)
        c.setFont("Helvetica", 5.5)
        c.drawCentredString(bx + bar_w/2, base_y - 8, str(yr))

        # Value label on top (only if bar is tall enough)
        if bh > 8:
            c.setFont("Helvetica", 5.5)
            c.setFillColor(TEAL_DARK)
            c.drawCentredString(bx + bar_w/2, base_y + bh + 2, f"{val:.1f}")

    # Y axis label
    c.setFillColor(GRAY_MID)
    c.setFont("Helvetica", 6)
    c.drawString(32, y_top + 2, f"{max_v:.1f}")
    c.drawString(32, base_y + 2, "0")

    return base_y - 14


def _draw_projected_yields(c, scores: dict, y_top: float) -> float:
    """Draw the 5 projected yield tiles. Returns y after."""
    yields = [
        ("1 yr",  scores.get("projected_yield_1y",  0)),
        ("3 yr",  scores.get("projected_yield_3y",  0)),
        ("5 yr",  scores.get("projected_yield_5y",  0)),
        ("10 yr", scores.get("projected_yield_10y", 0)),
        ("20 yr", scores.get("projected_yield_20y", 0)),
    ]
    box_w, box_h = 88, 54
    gap   = 8
    total = len(yields) * box_w + (len(yields)-1) * gap
    sx    = (W - total) / 2
    y     = y_top

    for i, (label, val) in enumerate(yields):
        bx = sx + i * (box_w + gap)
        is_p = (i == 2)
        bh   = box_h + (8 if is_p else 0)
        by   = y - bh + (0 if is_p else 8)
        fill = TEAL_LIGHT if is_p else GREEN_LIGHT
        txt  = TEAL_DARK  if is_p else GREEN_DARK
        c.setFillColor(fill)
        c.setStrokeColor(TEAL_MID if is_p else colors.HexColor("#639922"))
        c.setLineWidth(1.0 if is_p else 0.5)
        c.roundRect(bx, by, box_w, bh, 5, stroke=1, fill=1)
        c.setFillColor(txt)
        c.setFont("Helvetica", 8)
        c.drawCentredString(bx+box_w/2, by+bh-13, label)
        c.setFont("Helvetica-Bold", 16 if is_p else 13)
        c.drawCentredString(bx+box_w/2, by+bh/2-4, f"{val:.1f}%")
        if is_p:
            c.setFont("Helvetica", 6)
            c.drawCentredString(bx+box_w/2, by+8, "target")

    return y - box_h - 8 - 8   # below the tallest tile


def draw_deep_certificate(c, result: dict, cert_num: int):
    """Draw 2-page deep analysis certificate."""
    name    = result.get("name", result.get("ticker",""))
    ticker  = result.get("ticker","")
    scores  = result.get("scores", {})
    val     = result.get("valuation", {})
    tax     = result.get("tax_profiles", {})
    annual  = result.get("annual", {})
    div_hist = result.get("dividends", {})

    # ── PAGE 1: Overview, Valuation, Tax Profiles, Scores ──────────────────
    c.setPageSize(A4)
    c.setStrokeColor(BORDER)
    c.setLineWidth(0.5)
    c.roundRect(15, 15, W-30, H-30, 4, stroke=1, fill=0)

    _header(c, name, ticker, cert_num)

    # Conviction badge + deep score
    conviction = scores.get("conviction_rating", "WATCH")
    badge_map  = {
        "STRONG BUY": (TEAL_LIGHT, TEAL_DARK),
        "BUY":        (TEAL_LIGHT, TEAL_DARK),
        "WATCH":      (AMBER_LIGHT, AMBER_DARK),
        "AVOID":      (RED_LIGHT, RED_DARK),
    }
    bg, fg = badge_map.get(conviction, (GRAY_LIGHT, BLACK))
    c.setFillColor(bg)
    c.roundRect(W/2-60, H-212, 120, 20, 10, stroke=0, fill=1)
    c.setFillColor(fg)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(W/2, H-199, conviction)

    # Score circle
    score = scores.get("barren_deep_score", 0)
    cx, cy = W/2, H-250
    c.setFillColor(AMBER_LIGHT)
    c.circle(cx, cy, 28, stroke=0, fill=1)
    c.setStrokeColor(AMBER_MID)
    c.setLineWidth(1)
    c.circle(cx, cy, 28, stroke=1, fill=0)
    c.setFillColor(AMBER_DARK)
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(cx, cy+5, str(score))
    c.setFont("Helvetica", 6)
    c.drawCentredString(cx, cy-10, "DEEP SCORE")

    # WACC / Ke note
    c.setFillColor(GRAY_MID)
    c.setFont("Helvetica", 7.5)
    c.drawCentredString(W/2, H-286,
        f"WACC {val.get('wacc_pct','?')}%  ·  Ke {val.get('ke_pct','?')}%  ·  Rf {val.get('rf_pct','?')}%  ·  ERP 5.0%")

    _divider(c, H-298)

    # Valuation table
    _section_title(c, "5-Model Valuation  (all figures in " + result.get("currency","NOK") + " per share)", H-314)
    y_after_table = _draw_valuation_table(c, val, H-328)

    _divider(c, y_after_table - 4)

    # Tax profiles
    _section_title(c, "Norwegian Tax Regime — Investor Profiles", y_after_table - 18)
    y_after_tax = _draw_tax_profiles(c, tax, y_after_table - 32)

    _divider(c, y_after_tax - 4)

    # Score breakdown
    _section_title(c, "Barren Deep Score Breakdown", y_after_tax - 18)
    y_after_scores = _draw_score_breakdown(c, scores, y_after_tax - 32)

    # Footer p1
    _divider(c, 52)
    c.setFillColor(GRAY_MID)
    c.setFont("Helvetica", 7)
    c.drawString(30, 40, "For informational purposes only. Not financial advice. Page 1 of 2.")
    c.drawRightString(W-30, 40, "Barren Wuffet Capital Research")

    # ── PAGE 2: Dividend Chart, Annual Report Intel, Projected Yields ────────
    c.showPage()
    c.setPageSize(A4)
    c.setStrokeColor(BORDER)
    c.setLineWidth(0.5)
    c.roundRect(15, 15, W-30, H-30, 4, stroke=1, fill=0)

    _header(c, name, ticker, cert_num, subtitle="Deep Analysis — Dividend Intelligence")

    y = H-200

    # Dividend history chart
    _divider(c, y)
    y -= 16
    _section_title(c, "Annual Dividend Per Share — 10 Year History", y)
    y -= 14
    y = _draw_dividend_chart(c, div_hist, y)
    y -= 8

    # Annual report intelligence block
    _divider(c, y)
    y -= 16
    _section_title(c, "Annual Report Intelligence", y)
    y -= 14

    TEXT_W = W - 60
    LINE_H = 12

    # Dividend policy verbatim
    policy = annual.get("dividend_policy_verbatim", "") or annual.get("dividend_policy", "")
    if policy and policy.lower() not in ("not stated", ""):
        c.setFont("Helvetica-Bold", 7.5)
        c.setFillColor(BLACK)
        c.drawString(30, y, "Dividend Policy:")
        y -= LINE_H
        c.setFont("Helvetica-Oblique", 7.5)
        c.setFillColor(GRAY_MID)
        for ln in _wrap(c, f'"{policy}"', "Helvetica-Oblique", 7.5, TEXT_W)[:4]:
            if y < 80: break
            c.drawString(30, y, ln)
            y -= LINE_H
        y -= 4

    # Key quantitative metrics from annual report
    metrics_2col = [
        ("Coverage Ratio",    annual.get("dividend_coverage_ratio")),
        ("Debt/EBITDA",       annual.get("debt_ebitda")),
        ("ROIC",              annual.get("roic")),
        ("FCF Conversion",    annual.get("fcf_conversion_pct")),
        ("EBIT Margin",       annual.get("ebit_margin_pct")),
        ("Policy Clarity",    annual.get("dividend_policy_clarity_score")),
    ]
    col2_x = W/2 + 10
    y_metric_start = y
    c.setFont("Helvetica", 7.5)
    left_items  = metrics_2col[:3]
    right_items = metrics_2col[3:]
    yl, yr = y_metric_start, y_metric_start
    for label, val_m in left_items:
        if val_m is not None and str(val_m) not in ("None", ""):
            c.setFillColor(GRAY_MID)
            c.setFont("Helvetica", 7)
            c.drawString(30, yl, label + ":")
            c.setFillColor(BLACK)
            c.setFont("Helvetica-Bold", 7.5)
            suffix = "%" if "Margin" in label or "ROIC" in label or "FCF" in label else ("x" if "Debt" in label or "Coverage" in label else "/10" if "Clarity" in label else "")
            c.drawString(130, yl, f"{val_m}{suffix}")
            yl -= LINE_H
    for label, val_m in right_items:
        if val_m is not None and str(val_m) not in ("None", ""):
            c.setFillColor(GRAY_MID)
            c.setFont("Helvetica", 7)
            c.drawString(col2_x, yr, label + ":")
            c.setFillColor(BLACK)
            c.setFont("Helvetica-Bold", 7.5)
            suffix = "%" if "Margin" in label or "ROIC" in label or "FCF" in label else ("x" if "Coverage" in label or "Debt" in label else "/10")
            c.drawString(col2_x + 100, yr, f"{val_m}{suffix}")
            yr -= LINE_H
    y = min(yl, yr) - 6

    # Top dividend risks
    risks = annual.get("top_dividend_risks", []) or []
    if risks:
        c.setFillColor(BLACK)
        c.setFont("Helvetica-Bold", 7.5)
        c.drawString(30, y, "Top 3 Dividend Risks:")
        y -= LINE_H
        for risk_txt in risks[:3]:
            if y < 140: break
            c.setFillColor(RED_DARK)
            c.setFont("Helvetica", 6.5)
            for ln in _wrap(c, f"• {risk_txt}", "Helvetica", 6.5, TEXT_W)[:2]:
                c.drawString(32, y, ln)
                y -= 9
        y -= 4

    _divider(c, y)
    y -= 16

    # Projected yields
    _section_title(c, "Projected Annual Yield (APY) — On Today's Purchase Price", y)
    y -= 14
    y = _draw_projected_yields(c, scores, y)
    y -= 8

    _divider(c, y)
    y -= 14

    # Deep thesis
    thesis = scores.get("deep_thesis", "")
    if thesis:
        c.setFillColor(BLACK)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(30, y, "Barren's Deep Thesis:")
        y -= LINE_H
        c.setFont("Helvetica", 7.5)
        for ln in _wrap(c, thesis, "Helvetica", 7.5, TEXT_W)[:5]:
            if y < 110: break
            c.drawString(30, y, ln)
            y -= LINE_H
        y -= 6

    # Key risk
    key_risk = scores.get("key_risk", "")
    if key_risk and y > 110:
        c.setFillColor(BLACK)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(30, y, "Key Risk:")
        y -= LINE_H
        c.setFont("Helvetica", 7.5)
        c.setFillColor(GRAY_MID)
        for ln in _wrap(c, key_risk, "Helvetica", 7.5, TEXT_W)[:2]:
            if y < 100: break
            c.drawString(30, y, ln)
            y -= LINE_H
        y -= 6

    # Barren quip box
    quip = f"\"{scores.get('barren_quip', '')}\""
    if quip and y > 80:
        quip_lines = _wrap(c, quip, "Helvetica-Oblique", 8, TEXT_W - 20)
        q_h = len(quip_lines) * 11 + 16
        if y - q_h > 60:
            c.setStrokeColor(BORDER)
            c.setDash(4, 3)
            c.setLineWidth(0.5)
            c.roundRect(30, y - q_h, W-60, q_h, 5, stroke=1, fill=0)
            c.setDash()
            c.setFont("Helvetica-Oblique", 8)
            c.setFillColor(GRAY_MID)
            qy = y - 10
            for ln in quip_lines:
                c.drawCentredString(W/2, qy, ln)
                qy -= 11

    # Footer p2
    _divider(c, 52)
    c.setFillColor(GRAY_MID)
    c.setFont("Helvetica", 7)
    c.drawString(30, 40, "For informational purposes only. Not financial advice. Page 2 of 2.")
    c.drawRightString(W-30, 40, f"© 2026 Barren Wuffet Capital Research · Powered by Claude AI")
    c.drawCentredString(W/2, 28, "Data: Yahoo Finance · Annual Reports · Norwegian Government Bond Yield")


def generate_deep_certificate(result: dict, output_dir: str = DEEP_DIR) -> str:
    os.makedirs(output_dir, exist_ok=True)
    safe    = result["ticker"].replace(".", "_")
    name    = result.get("name", result["ticker"]).replace(" ", "_").replace("/", "-")
    fname   = os.path.join(output_dir, f"BW_DEEP_{safe}_{name}.pdf")
    cert_no = abs(hash(result["ticker"])) % 9000 + 1000
    cv      = rl_canvas.Canvas(fname, pagesize=A4)
    draw_deep_certificate(cv, result, cert_no)
    cv.save()
    print(f"✅ Deep certificate saved: {fname}")
    return fname


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — ORCHESTRATION
# ═══════════════════════════════════════════════════════════════════════════════

def run_deep_analysis(ticker: str) -> dict:
    """
    Full deep analysis pipeline. Returns result dict and produces:
      1. Enhanced PDF certificate in certificates/deep/
      2. JSON data file in reports/<ticker>_deep_result.json
    """
    print(f"\n{'='*60}")
    print(f"  BARREN DEEP ANALYSIS — {ticker}")
    print(f"{'='*60}\n")

    # 1. Fetch comprehensive yfinance data
    print("📊 Fetching market data...")
    deep_data = fetch_deep_data(ticker)
    info      = deep_data["info"]
    price     = info.get("currentPrice") or info.get("regularMarketPrice") or 0
    if price == 0:
        print(f"❌ Could not fetch price for {ticker}. Check ticker symbol.")
        return {}

    # Basic stock info
    stock_data = {
        "ticker":         ticker,
        "name":           info.get("longName", ticker),
        "sector":         info.get("sector", "Unknown"),
        "industry":       info.get("industry", "Unknown"),
        "country":        info.get("country", "Norway"),
        "currency":       info.get("currency", "NOK"),
        "current_price":  price,
        "dividend_yield": info.get("dividendYield") or 0,
        "dividend_rate":  info.get("dividendRate") or 0,
        "payout_ratio":   round((info.get("payoutRatio") or 0) * 100, 1),
        "pe_ratio":       info.get("trailingPE"),
        "pb_ratio":       info.get("priceToBook"),
        "debt_to_equity": info.get("debtToEquity"),
        "roe":            round((info.get("returnOnEquity") or 0) * 100, 2),
        "market_cap":     info.get("marketCap"),
        "beta":           info.get("beta"),
        "52w_high":       info.get("fiftyTwoWeekHigh"),
        "52w_low":        info.get("fiftyTwoWeekLow"),
    }
    print(f"   {stock_data['name']} — {price:.2f} {stock_data['currency']}")
    print(f"   Yield: {stock_data['dividend_yield']:.2f}%  P/E: {stock_data['pe_ratio']}  Beta: {stock_data['beta']}")

    # 2. Run valuation models
    print("\n📐 Running 5 valuation models...")
    valuation = run_valuation_models(ticker, deep_data)
    if valuation.get("fv_mid"):
        print(f"   Fair value: {valuation['fv_low']} — {valuation['fv_mid']} — {valuation['fv_high']}")
        mos = valuation.get("margin_of_safety_pct")
        print(f"   Margin of safety: {mos:+.1f}%" if mos is not None else "   Margin of safety: n/a")

    # 3. Fritaksmetoden tax profiles
    print("\n🇳🇴 Calculating tax profiles...")
    is_osa = ticker.endswith(".OL")
    tax = calc_tax_profiles(info, is_osa_qualified=is_osa)
    print(f"   Corporate (fritaks):  {tax['corporate_fritaks']['net_yield_pct']:.2f}%")
    print(f"   Personal (ASK):       {tax['personal_ask']['net_yield_pct']:.2f}%")
    print(f"   Foreign (15% w/h):    {tax['foreign_investor']['net_yield_pct']:.2f}%")

    # 4. Deep annual report analysis
    print("\n📄 Reading annual report...")
    annual = deep_annual_analysis(ticker, stock_data["name"])
    if annual:
        print(f"   Policy clarity: {annual.get('dividend_policy_clarity_score','?')}/10")
        print(f"   Coverage ratio: {annual.get('dividend_coverage_ratio','?')}")
    else:
        print("   No annual report data available")

    # 5. Enhanced conviction scoring
    print("\n🧠 Computing enhanced Barren conviction scores...")
    scores = calc_deep_scores(stock_data, valuation, annual)
    print(f"   Deep Score:       {scores.get('barren_deep_score')}/100")
    print(f"   Conviction:       {scores.get('conviction_rating')}")
    print(f"   Intrinsic Value:  {scores.get('intrinsic_value_score')}/100")
    print(f"   Dividend Quality: {scores.get('dividend_quality_score')}/100")
    print(f"   Business Quality: {scores.get('business_quality_score')}/100")
    print(f"   Risk:             {scores.get('risk_score')}/100")

    # 6. Assemble full result
    result = {
        **stock_data,
        "valuation":    valuation,
        "tax_profiles": tax,
        "annual":       annual,
        "scores":       scores,
        "dividends":    deep_data["dividends"],
        # Flatten key scores to top level for compatibility with barren_scorer
        "barren_score":          scores.get("barren_deep_score"),
        "conviction_rating":     scores.get("conviction_rating"),
        "projected_yield_1y":    scores.get("projected_yield_1y"),
        "projected_yield_3y":    scores.get("projected_yield_3y"),
        "projected_yield_5y":    scores.get("projected_yield_5y"),
        "projected_yield_10y":   scores.get("projected_yield_10y"),
        "projected_yield_20y":   scores.get("projected_yield_20y"),
        "thesis":                scores.get("deep_thesis"),
        "key_risk":              scores.get("key_risk"),
        "barren_quip":           scores.get("barren_quip"),
    }

    # 7. Save JSON
    json_path = os.path.join(REPORTS, f"{ticker.replace('.','_')}_deep_result.json")
    with open(json_path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\n💾 JSON saved: {json_path}")

    # 8. Generate PDF certificate
    print("🎨 Generating deep certificate...")
    cert_path = generate_deep_certificate(result)

    # 9. Open certificate automatically
    if sys.platform == "darwin":
        os.system(f'open "{cert_path}"')

    print(f"\n{'='*60}")
    print(f"  ✅  Deep analysis complete — {stock_data['name']}")
    print(f"  📄  {cert_path}")
    print(f"{'='*60}\n")

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python barren_deep_analysis.py <TICKER>")
        print("  e.g. python barren_deep_analysis.py DNB.OL")
        print("  e.g. python barren_deep_analysis.py EQNR.OL")
        sys.exit(1)

    tickers = sys.argv[1:]
    for t in tickers:
        run_deep_analysis(t.upper())
