"""
Oslo Stock Exchange — Fritaksmetoden qualifying dividend stocks.

Fritaksmetoden (participation exemption) lets a Norwegian AS/ASA receive
dividends and realise gains on shares essentially tax-free (only 3 % of
the dividend is included in taxable income, giving an effective rate of
~0.66 % at the 22 % corporate rate).

Qualifying criteria (simplified):
  • The investee must be a company tax-resident in the EEA, OR
  • A non-EEA company where the Norwegian AS holds ≥ 10 % for ≥ 2 years
    AND the country has an adequate tax treaty with Norway.

All tickers below are Norwegian AS/ASA or Luxembourg/EEA-incorporated
companies listed on Oslo Børs — they qualify under the standard rule.
Companies incorporated in Bermuda, Cayman, Marshall Islands etc. are
excluded even if they trade on Oslo Børs.
"""

import json
import os
import time
import yfinance as yf

# ── Watchlist ────────────────────────────────────────────────────────────────
OSE_FRITAKSMETODEN = [
    # Large-cap blue chips
    ("EQNR.OL",     "Equinor",                    "Energy"),
    ("DNB.OL",      "DNB Bank",                   "Banking"),
    ("NHY.OL",      "Norsk Hydro",                "Materials"),
    ("YAR.OL",      "Yara International",         "Materials"),
    ("TEL.OL",      "Telenor",                    "Telecom"),
    ("ORK.OL",      "Orkla",                      "Consumer Staples"),
    ("GJF.OL",      "Gjensidige Forsikring",      "Insurance"),
    ("MOWI.OL",     "Mowi",                       "Aquaculture"),
    ("SALM.OL",     "SalMar",                     "Aquaculture"),
    ("AKRBP.OL",    "Aker BP",                    "Energy"),
    ("STB.OL",      "Storebrand",                 "Financials"),
    ("KOG.OL",      "Kongsberg Gruppen",          "Defense/Tech"),
    # Mid-cap
    ("AUSS.OL",     "Austevoll Seafood",          "Aquaculture"),
    ("LSG.OL",      "Lerøy Seafood",              "Aquaculture"),
    ("VEI.OL",      "Veidekke",                   "Construction"),
    ("AFG.OL",      "AF Gruppen",                 "Construction"),
    ("SRBANK.OL",   "SpareBank 1 SR-Bank",        "Banking"),
    ("MING.OL",     "SpareBank 1 SMN",            "Banking"),
    ("NONG.OL",     "SpareBank 1 Nord-Norge",     "Banking"),
    ("SUBC.OL",     "Subsea 7",                   "Oil Services"),  # Luxembourg-incorporated (EEA)
    ("TOM.OL",      "Tomra Systems",              "Technology"),
    ("AKER.OL",     "Aker ASA",                   "Holding"),
    ("WWI.OL",      "Wilh. Wilhelmsen Holding",   "Shipping/Holding"),
    ("ODF.OL",      "Odfjell",                    "Shipping"),
    ("PROT.OL",     "Protector Forsikring",       "Insurance"),
    ("ENTRA.OL",    "Entra",                      "Real Estate"),
    ("BAKKA.OL",    "Bakkafrost",                 "Aquaculture"),   # Faroe Islands — EEA
    ("MULTI.OL",    "Multiconsult",               "Engineering"),
    ("KIT.OL",      "Kitron",                     "Electronics"),
    ("SCHA.OL",     "Schibsted A",                "Media"),
]

BASE  = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(BASE, "norway_results.json")
CACHE_TTL = 6 * 3600  # 6 hours


def _cache_valid():
    if not os.path.exists(CACHE):
        return False
    return (time.time() - os.path.getmtime(CACHE)) < CACHE_TTL


def _fetch_one(ticker: str, fallback_name: str, fallback_sector: str) -> dict:
    try:
        info = yf.Ticker(ticker).info
        price  = info.get("currentPrice") or info.get("regularMarketPrice") or 0
        # yfinance returns dividendYield already as a percentage (e.g. 4.37 = 4.37%)
        raw_yield  = info.get("dividendYield") or 0
        pe    = info.get("trailingPE")
        pb    = info.get("priceToBook")
        de    = info.get("debtToEquity")
        roe   = info.get("returnOnEquity")
        payout = info.get("payoutRatio")
        market_cap = info.get("marketCap")
        return {
            "ticker":        ticker,
            "name":          info.get("longName") or fallback_name,
            "sector":        info.get("sector") or fallback_sector,
            "price":         round(price, 2),
            "currency":      info.get("currency", "NOK"),
            "dividend_yield": round(raw_yield, 2) if raw_yield else None,
            "pe_ratio":      round(pe, 1) if pe else None,
            "pb_ratio":      round(pb, 2) if pb else None,
            "debt_to_equity": round(de, 1) if de else None,
            "roe":           round(roe * 100, 1) if roe else None,
            "payout_ratio":  round(payout * 100, 1) if payout else None,
            "market_cap":    market_cap,
        }
    except Exception as e:
        return {
            "ticker": ticker, "name": fallback_name, "sector": fallback_sector,
            "price": None, "currency": "NOK",
            "dividend_yield": None, "pe_ratio": None, "pb_ratio": None,
            "debt_to_equity": None, "roe": None, "payout_ratio": None,
            "market_cap": None, "error": str(e),
        }


def fetch_oslo_data(force: bool = False) -> list:
    """Return list of OSE fritaksmetoden stocks with 5 key value metrics.
    Results are cached for 6 hours to avoid hammering Yahoo Finance."""
    if not force and _cache_valid():
        with open(CACHE) as f:
            return json.load(f)

    print(f"📡 Fetching Oslo Stock Exchange data ({len(OSE_FRITAKSMETODEN)} stocks)...")
    results = []
    for ticker, name, sector in OSE_FRITAKSMETODEN:
        print(f"  → {ticker}")
        row = _fetch_one(ticker, name, sector)
        results.append(row)

    # Sort: dividend payers first, then by yield descending
    results.sort(key=lambda x: (-(x["dividend_yield"] or 0)))

    with open(CACHE, "w") as f:
        json.dump(results, f, indent=2)
    print(f"✅ Oslo data cached ({len(results)} stocks).")
    return results
