"""
barren_annual_reports.py
────────────────────────────────────────────────────────────────────────────
For each supported ticker:
  1. Scrapes the investor-relations page for the most recent annual report PDF.
  2. Downloads and caches the PDF locally (reports/<TICKER>_<YEAR>.pdf).
  3. Extracts text with pdfplumber, prioritising dividend/FCF/risk sections.
  4. Sends extracted text to Claude for structured metric extraction.
  5. Caches the result as reports/<TICKER>_<YEAR>.json — no re-fetch until
     a newer annual report year is detected.

Integration: call get_annual_report_data(ticker) from barren_scorer.py and
merge the returned dict into the Claude scoring prompt.
"""

import os
import re
import json
import time
import requests
import pdfplumber
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()
client   = Anthropic()
BASE     = os.path.dirname(os.path.abspath(__file__))
REPORTS  = os.path.join(BASE, "reports")
os.makedirs(REPORTS, exist_ok=True)

CURRENT_YEAR = datetime.now().year

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# ── Investor Relations pages ─────────────────────────────────────────────────
IR_PAGES = {
    # Nordic
    "EQNR.OL": "https://www.equinor.com/investors/annual-report",
    "AKRBP.OL": "https://akerbp.com/en/investors/reports-and-presentations/annual-reports/",
    "DNB.OL":   "https://www.dnb.no/en/about-us/investor-relations/annual-reports.html",
    "GJF.OL":   "https://www.gjensidige.no/investor/reports-and-presentations",
    "ORK.OL":   "https://www.orkla.com/investor-relations/reports-and-presentations/annual-reports/",
    "TEL.OL":   "https://www.telenor.com/investors/reports-and-presentations/annual-reports/",
    "MOWI.OL":  "https://mowi.com/investors/reports/annual-reports/",
    "STB.OL":   "https://www.storebrand.no/en/investor-relations/reports-and-presentations/",
    "YAR.OL":   "https://www.yara.com/investor-relations/reports-and-publications/annual-reports/",
    "SALM.OL":  "https://www.salmar.no/en/investor-relations/reports-and-presentations/",
    # US Aristocrats
    "JNJ":  "https://investor.jnj.com/annual-reports-and-proxies",
    "KO":   "https://investors.coca-colacompany.com/financial-information/annual-reports",
    "PG":   "https://pginvestor.com/financial-reporting/annual-reports-proxies/default.aspx",
    "MMM":  "https://investors.3m.com/financial-information/annual-reports",
    "CL":   "https://investor.colgatepalmolive.com/financial-information/annual-reports",
    "ABT":  "https://investors.abbott.com/financial-information/annual-reports/default.aspx",
    "EMR":  "https://www.emerson.com/en-us/investors/financial-reports",
    "GPC":  "https://investor.genpt.com/financial-information/annual-reports",
    "PEP":  "https://www.pepsico.com/investors/financial-information/annual-reports",
    "T":    "https://investors.att.com/financial-information/annual-reports",
    "VZ":   "https://www.verizon.com/about/investors/annual-reports",
    "MCD":  "https://corporate.mcdonalds.com/corpmcd/investors/annual-report.html",
    "WMT":  "https://stock.walmart.com/financial-information/annual-reports-and-proxies",
    "XOM":  "https://investor.exxonmobil.com/financial-information/annual-reports",
    "CVX":  "https://www.chevron.com/investors/annual-report",
}

KEYWORDS = [
    "dividend", "cash flow", "free cash", "payout", "guidance", "outlook",
    "capital allocation", "debt", "covenant", "net debt", "leverage",
    "earnings per share", "sustainability", "risk factor", "forward",
]


# ── PDF discovery ─────────────────────────────────────────────────────────────

def _find_pdf_on_page(ir_url: str, target_years: list) -> Optional[str]:
    """Scrape an IR page and return the URL of the best annual report PDF."""
    try:
        r = requests.get(ir_url, headers=HEADERS, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print(f"    ⚠️  Could not fetch IR page: {e}")
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    base = f"{urlparse(ir_url).scheme}://{urlparse(ir_url).netloc}"

    candidates = []
    for a in soup.find_all("a", href=True):
        href  = a["href"].strip()
        text  = a.get_text(" ", strip=True).lower()
        label = (href + " " + text).lower()

        # Must look like an annual report PDF
        is_pdf    = ".pdf" in label
        is_annual = any(w in label for w in ["annual", "årsrapport", "annual-report", "annualreport"])
        if not (is_pdf and is_annual):
            continue

        # Make absolute
        if href.startswith("http"):
            abs_url = href
        else:
            abs_url = urljoin(base, href)

        # Score by year mentions
        year_score = 0
        for i, yr in enumerate(target_years):
            if str(yr) in label:
                year_score = len(target_years) - i  # more points for more recent
                break

        candidates.append((year_score, abs_url))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


# ── PDF download & caching ────────────────────────────────────────────────────

def _safe_ticker(ticker: str) -> str:
    return ticker.replace(".", "_").replace("/", "-")


def _pdf_path(ticker: str, year: int) -> str:
    return os.path.join(REPORTS, f"{_safe_ticker(ticker)}_{year}.pdf")


def _json_path(ticker: str, year: int) -> str:
    return os.path.join(REPORTS, f"{_safe_ticker(ticker)}_{year}.json")


def _download_pdf(url: str, dest: str) -> bool:
    try:
        r = requests.get(url, headers=HEADERS, timeout=60, stream=True)
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                f.write(chunk)
        size_mb = os.path.getsize(dest) / 1_048_576
        print(f"    📥  Downloaded {size_mb:.1f} MB → {os.path.basename(dest)}")
        return True
    except Exception as e:
        print(f"    ❌  Download failed: {e}")
        if os.path.exists(dest):
            os.remove(dest)
        return False


# ── Text extraction ───────────────────────────────────────────────────────────

def _extract_text(pdf_path: str, max_chars: int = 350_000) -> str:
    """
    Extract text from PDF. If the document is very long, keep the first 10 pages
    (cover/highlights) plus the pages that score highest on dividend/FCF keywords.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages = []
            for i, page in enumerate(pdf.pages):
                text  = page.extract_text() or ""
                score = sum(text.lower().count(kw) for kw in KEYWORDS)
                pages.append((i + 1, text, score))

        full = "\n\n".join(f"[PAGE {n}]\n{t}" for n, t, _ in pages)
        if len(full) <= max_chars:
            return full

        # Too long — keep first 10 pages + top-scoring 40 pages
        first   = pages[:10]
        rest    = sorted(pages[10:], key=lambda x: x[2], reverse=True)[:40]
        selected = sorted(first + rest, key=lambda x: x[0])
        return "\n\n".join(f"[PAGE {n}]\n{t}" for n, t, _ in selected)[:max_chars]

    except Exception as e:
        return f"[PDF extraction error: {e}]"


# ── Claude analysis ───────────────────────────────────────────────────────────

_PROMPT = """\
You are Barren Wuffett's research assistant. Read the following annual report
extract and return ONLY a valid JSON object — no markdown, no preamble.

Extract exactly these fields:

{{
  "report_year":                      <integer — fiscal year of this report>,
  "dividend_history":                 <string — recent dividend payments, amounts, trends>,
  "dividend_policy":                  <string — stated dividend policy or payout targets>,
  "dividend_sustainability_commentary": <string — what management says about sustaining/growing the dividend>,
  "free_cash_flow_trend":             <string — FCF figures for the last 2-3 years and direction>,
  "net_debt":                         <string — net debt level and trend>,
  "debt_covenants":                   <string — any debt covenants or financial constraints mentioned>,
  "earnings_guidance":                <string — forward guidance on earnings, revenue, or dividend>,
  "dividend_risks":                   <string — key risks to dividend continuity mentioned in the report>,
  "barren_annual_score":              <integer 1-100 — Barren's rating of this report's dividend safety signals>,
  "barren_annual_notes":              <string — 2-3 sentences of Barren's commentary on these annual report findings>
}}

ANNUAL REPORT TEXT:
{text}
"""


def _analyse_with_claude(ticker: str, company_name: str, text: str) -> dict:
    prompt = _PROMPT.format(text=text[:300_000])
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    return json.loads(raw)


# ── Public entry point ────────────────────────────────────────────────────────

def get_annual_report_data(ticker: str, company_name: str = "") -> dict:
    """
    Returns structured annual report data for a ticker.
    Uses cache if available; fetches and analyses only when a newer report is needed.
    Returns {} if the ticker has no IR page or all fetches fail.
    """
    if ticker not in IR_PAGES:
        return {}

    # Try most recent year first (reports published ~Q1 of following year)
    target_years = [CURRENT_YEAR - 1, CURRENT_YEAR - 2]

    # Check cache — use newest year we have on disk
    for year in target_years:
        jp = _json_path(ticker, year)
        if os.path.exists(jp):
            print(f"    📋  Using cached annual report ({ticker} {year})")
            with open(jp) as f:
                return json.load(f)

    # No cache — fetch
    print(f"    🔍  Searching for annual report PDF for {ticker}...")
    ir_url  = IR_PAGES[ticker]
    pdf_url = _find_pdf_on_page(ir_url, target_years)

    if not pdf_url:
        print(f"    ⚠️  No annual report PDF found for {ticker}")
        return {}

    # Determine year from URL or default to CURRENT_YEAR-1
    year = CURRENT_YEAR - 1
    for yr in target_years:
        if str(yr) in pdf_url:
            year = yr
            break

    pdf_dest = _pdf_path(ticker, year)
    if not os.path.exists(pdf_dest):
        if not _download_pdf(pdf_url, pdf_dest):
            return {}

    print(f"    🔬  Extracting and analysing {ticker} {year} annual report...")
    text   = _extract_text(pdf_dest)
    result = {}

    try:
        result = _analyse_with_claude(ticker, company_name, text)
        result["source_url"] = pdf_url
        result["fetched_at"] = datetime.now().isoformat()

        with open(_json_path(ticker, year), "w") as f:
            json.dump(result, f, indent=2)
        print(f"    ✅  Annual report data saved for {ticker} {year}")

    except Exception as e:
        print(f"    ❌  Claude analysis failed for {ticker}: {e}")

    time.sleep(1)  # polite pause between API calls
    return result


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from barren_scorer import NORDIC

    print("=" * 60)
    print("  BARREN — Annual Report Analyser")
    print("  Starting with Nordic watchlist")
    print("=" * 60)

    for ticker in NORDIC:
        print(f"\n📄 {ticker}")
        data = get_annual_report_data(ticker)
        if data:
            print(f"   Score: {data.get('barren_annual_score', '—')}/100")
            print(f"   Notes: {data.get('barren_annual_notes', '—')[:120]}...")
        else:
            print("   No data retrieved.")
