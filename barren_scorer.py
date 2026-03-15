import os
import json
import yfinance as yf
import pandas as pd
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()
client = Anthropic()

# ── Global Dividend Watchlist ────────────────────────────────────────────────

# Nordic (Norway/Sweden/Denmark/Finland)
NORDIC = [
    "EQNR.OL",   # Equinor — Norway, energy
    "AKRBP.OL",  # Aker BP — Norway, oil & gas
    "DNB.OL",    # DNB Bank — Norway, financials
    "GJF.OL",    # Gjensidige Forsikring — Norway, insurance
    "ORK.OL",    # Orkla — Norway, consumer staples
    "TEL.OL",    # Telenor — Norway, telecom
    "MOWI.OL",   # Mowi — Norway, aquaculture
    "STB.OL",    # Storebrand — Norway, financials
    "YAR.OL",    # Yara International — Norway, fertilisers
    "SALM.OL",   # SalMar — Norway, aquaculture
]

# US Dividend Aristocrats (25+ consecutive years of dividend growth)
US_ARISTOCRATS = [
    "JNJ",       # Johnson & Johnson — healthcare
    "KO",        # Coca-Cola — beverages
    "PG",        # Procter & Gamble — consumer staples
    "MMM",       # 3M — industrials
    "CL",        # Colgate-Palmolive — consumer staples
    "ABT",       # Abbott Laboratories — healthcare
    "EMR",       # Emerson Electric — industrials
    "GPC",       # Genuine Parts — distribution
    "PEP",       # PepsiCo — beverages
    "T",         # AT&T — telecom
    "VZ",        # Verizon — telecom
    "MCD",       # McDonald's — restaurants
    "WMT",       # Walmart — retail
    "XOM",       # ExxonMobil — energy
    "CVX",       # Chevron — energy
]

# UK High Yield (FTSE 100)
UK_FTSE = [
    "SHEL.L",    # Shell — energy
    "BP.L",      # BP — energy
    "ULVR.L",    # Unilever — consumer staples
    "GSK.L",     # GSK — pharmaceuticals
    "AZN.L",     # AstraZeneca — pharmaceuticals
    "HSBA.L",    # HSBC — banking
    "LLOY.L",    # Lloyds Banking Group — banking
    "VOD.L",     # Vodafone — telecom
    "NG.L",      # National Grid — utilities
    "SSE.L",     # SSE — utilities
]

# European Dividend Champions
EUROPE = [
    "ALV.DE",    # Allianz — Germany, insurance
    "MUV2.DE",   # Munich Re — Germany, reinsurance
    "SIE.DE",    # Siemens — Germany, industrials
    "BAYN.DE",   # Bayer — Germany, pharma/agri
    "MC.PA",     # LVMH — France, luxury goods
    "TTE.PA",    # TotalEnergies — France, energy
    "SAN.PA",    # Sanofi — France, pharmaceuticals
    "OR.PA",     # L'Oréal — France, consumer
    "ASML.AS",   # ASML — Netherlands, semiconductors
    "RDSA.AS",   # ABN AMRO — Netherlands, banking (ticker: ABN.AS)
    "NOVN.SW",   # Novartis — Switzerland, pharmaceuticals
    "NESN.SW",   # Nestlé — Switzerland, consumer staples
    "ROG.SW",    # Roche — Switzerland, pharmaceuticals
]

# Australia (ASX)
AUSTRALIA = [
    "CBA.AX",    # Commonwealth Bank — banking
    "BHP.AX",    # BHP Group — mining
    "WBC.AX",    # Westpac — banking
    "ANZ.AX",    # ANZ Bank — banking
    "TLS.AX",    # Telstra — telecom
    "WES.AX",    # Wesfarmers — conglomerate
]

# Singapore (SGX)
SINGAPORE = [
    "D05.SI",    # DBS Group — banking
    "O39.SI",    # OCBC Bank — banking
    "U11.SI",    # UOB — banking
    "Z74.SI",    # Singtel — telecom
    "C6L.SI",    # Singapore Airlines — aviation
    "C38U.SI",   # CapitaLand Integrated Commercial Trust — REIT
]

WATCHLIST = NORDIC + US_ARISTOCRATS

# ── Fetch raw data from Yahoo Finance ───────────────────────────────────────
def fetch_stock_data(ticker: str) -> dict:
    stock = yf.Ticker(ticker)
    info = stock.info

    # Pull 5 years of dividend history
    dividends = stock.dividends
    hist = stock.history(period="5y")

    # Calculate dividend growth rate (CAGR over available history)
    if len(dividends) >= 2:
        years = (dividends.index[-1] - dividends.index[0]).days / 365.25
        if years > 0:
            total_div_start = dividends.iloc[0]
            total_div_end   = dividends.iloc[-1]
            if total_div_start > 0:
                div_cagr = (total_div_end / total_div_start) ** (1 / years) - 1
            else:
                div_cagr = 0
        else:
            div_cagr = 0
    else:
        div_cagr = 0

    annual_dividend = info.get("dividendRate") or 0
    current_price   = info.get("currentPrice") or info.get("regularMarketPrice") or 1
    raw_yield = info.get("dividendYield")
    dividend_yield = raw_yield if (raw_yield and raw_yield < 1) else (raw_yield / 100 if raw_yield and raw_yield > 1 else 0)

    return {
        "ticker":            ticker,
        "name":              info.get("longName", ticker),
        "country":           info.get("country", "Norway"),
        "sector":            info.get("sector", "Unknown"),
        "industry":          info.get("industry", "Unknown"),
        "current_price":     current_price,
        "currency":          info.get("currency", "NOK"),
        "dividend_yield":    round(dividend_yield * 100, 2),  # as %
        "annual_dividend":   annual_dividend,
        "div_cagr_5y":       round(div_cagr * 100, 2),        # as %
        "payout_ratio":      round((info.get("payoutRatio") or 0) * 100, 2),
        "pe_ratio":          info.get("trailingPE"),
        "pb_ratio":          info.get("priceToBook"),
        "debt_to_equity":    info.get("debtToEquity"),
        "free_cash_flow":    info.get("freeCashflow"),
        "revenue_growth":    round((info.get("revenueGrowth") or 0) * 100, 2),
        "roe":               round((info.get("returnOnEquity") or 0) * 100, 2),
        "market_cap":        info.get("marketCap"),
        "52w_high":          info.get("fiftyTwoWeekHigh"),
        "52w_low":           info.get("fiftyTwoWeekLow"),
        "analyst_target":    info.get("targetMeanPrice"),
        "description":       info.get("longBusinessSummary", "")[:800],
    }

# ── Ask Barren to score and project yields ──────────────────────────────────
def barren_analyse(data: dict) -> dict:
    # Load persona
    soul_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "persona", "SOUL.md")
    with open(soul_path) as f:
        soul = f.read()

    # Optionally enrich with annual report data (disabled on Railway to save memory)
    annual_section = ""
    if not os.getenv("RAILWAY_ENVIRONMENT"):
        try:
            from barren_annual_reports import get_annual_report_data
            annual = get_annual_report_data(data["ticker"], data.get("name", ""))
            if annual:
                annual_section = f"""

ANNUAL REPORT ANALYSIS (use this to deepen your scoring):
{json.dumps(annual, indent=2)}
"""
        except Exception:
            pass  # annual reports are optional enrichment — never block scoring

    prompt = f"""
You are Barren Wuffett. Your full identity and rules are below:

{soul}

Now analyse this stock with your full personality and rigour.

Analyse this stock and return ONLY a valid JSON object. No preamble, no markdown.

STOCK DATA:
{json.dumps(data, indent=2)}
{annual_section}

Return this exact JSON structure:
{{
  "barren_score": <integer 1-100, overall conviction>,
  "dividend_score": <integer 1-100>,
  "balance_sheet_score": <integer 1-100>,
  "sector_safety_score": <integer 1-100>,
  "value_score": <integer 1-100, how cheap vs intrinsic value>,
  "growth_score": <integer 1-100, long-term dividend growth potential>,
  "projected_yield_1y":  <float, expected APY % in 1 year>,
  "projected_yield_3y":  <float, expected APY % over 3 years>,
  "projected_yield_5y":  <float, expected APY % over 5 years>,
  "projected_yield_10y": <float, expected APY % over 10 years>,
  "projected_yield_20y": <float, expected APY % over 20 years>,
  "conviction_rating": <string: "STRONG BUY" | "BUY" | "WATCH" | "AVOID">,
  "thesis": <2-3 sentence Barren-voice investment thesis, warm and enthusiastic>,
  "key_risk": <1 sentence on the main risk>,
  "barren_quip": <one short, slightly unhinged Barren Wuffet remark about this stock>
}}
"""
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.content[0].text.strip()
    # Strip markdown fences if present
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)

# ── Run a full scan ──────────────────────────────────────────────────────────
def run_scan(tickers: list = WATCHLIST) -> list:
    results = []
    for ticker in tickers:
        print(f"\n🔍 Barren is sniffing around {ticker}...")
        try:
            data    = fetch_stock_data(ticker)
            verdict = barren_analyse(data)
            result  = {**data, **verdict}
            results.append(result)
            print(f"   ✅ {data['name']}: {verdict['conviction_rating']} "
                  f"| Score: {verdict['barren_score']}/100 "
                  f"| 5yr APY: {verdict['projected_yield_5y']}%")
        except Exception as e:
            print(f"   ❌ {ticker} failed: {e}")

    # Sort by barren_score descending
    results.sort(key=lambda x: x.get("barren_score", 0), reverse=True)
    return results

# ── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  BARREN WUFFET — Global Dividend Scanner v0.2")
    print("  'The dividends, my friend, are blowin' in the wind!'")
    print(f"  Scanning {len(WATCHLIST)} stocks across 7 markets")
    print("=" * 60)

    results = run_scan()

    print("\n\n📊 BARREN'S GLOBAL DIVIDEND LEADERBOARD")
    print("-" * 60)
    for r in results:
        print(f"{r['barren_score']:3}/100  {r['name']:<35} "
              f"{r['conviction_rating']:<12} "
              f"Yield: {r['dividend_yield']}% → 5yr: {r['projected_yield_5y']}%")

    # Save raw results for the certificate generator
    with open("scan_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\n💾 Results saved to scan_results.json")