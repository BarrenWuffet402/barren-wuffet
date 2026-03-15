"""
barren_annual_reports.py
────────────────────────────────────────────────────────────────────────────
Two discovery strategies:
  • US stocks  → SEC EDGAR (free public API, no scraping, no blocks)
  • Nordic stocks → IR page scraping + PDF download + pdfplumber

Both paths feed text to Claude for structured metric extraction, with full
JSON caching so we only re-fetch when a new annual report year is available.
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
client  = Anthropic()
BASE    = os.path.dirname(os.path.abspath(__file__))
REPORTS = os.path.join(BASE, "reports")
os.makedirs(REPORTS, exist_ok=True)

CURRENT_YEAR = datetime.now().year

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
# EDGAR requires a descriptive User-Agent per their policy
EDGAR_HEADERS = {
    "User-Agent": "BarrenWuffettResearch research@barrenwuffett.com",
    "Accept":     "application/json",
}

# ── US tickers → SEC EDGAR CIK numbers ───────────────────────────────────────
EDGAR_CIKS = {
    "JNJ":  "0000200406",
    "KO":   "0000021344",
    "PG":   "0000080424",
    "MMM":  "0000066740",
    "CL":   "0000021665",
    "ABT":  "0000001800",
    "EMR":  "0000032604",
    "GPC":  "0000040987",
    "PEP":  "0000077476",
    "T":    "0000732717",
    "VZ":   "0000732712",
    "MCD":  "0000063908",
    "WMT":  "0000104169",
    "XOM":  "0000034088",
    "CVX":  "0000093410",
}

# ── Nordic IR pages for PDF scraping ─────────────────────────────────────────
IR_PAGES = {
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
}

# Terms that indicate annual report content (English + Norwegian)
ANNUAL_TERMS = [
    "annual", "annual-report", "annualreport",
    "årsrapport", "årsberetning", "årsmelding",
]

KEYWORDS = [
    "dividend", "cash flow", "free cash", "payout", "guidance", "outlook",
    "capital allocation", "debt", "covenant", "net debt", "leverage",
    "earnings per share", "sustainability", "risk factor",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_ticker(ticker: str) -> str:
    return ticker.replace(".", "_").replace("/", "-")

def _json_path(ticker: str, year: int) -> str:
    return os.path.join(REPORTS, f"{_safe_ticker(ticker)}_{year}.json")

def _pdf_path(ticker: str, year: int) -> str:
    return os.path.join(REPORTS, f"{_safe_ticker(ticker)}_{year}.pdf")


# ── Strategy A: SEC EDGAR for US stocks ──────────────────────────────────────

def _get_edgar_text(ticker: str) -> Optional[str]:
    """Fetch the most recent 10-K text from SEC EDGAR."""
    cik = EDGAR_CIKS.get(ticker)
    if not cik:
        return None

    cik_int = str(int(cik))  # strip leading zeros for URL paths

    try:
        # 1. Get submission metadata
        sub_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        r = requests.get(sub_url, headers=EDGAR_HEADERS, timeout=15)
        r.raise_for_status()
        filings = r.json()["filings"]["recent"]

        # 2. Find the most recent 10-K
        accno = None
        for form, date, acc in zip(filings["form"], filings["filingDate"], filings["accessionNumber"]):
            if form == "10-K":
                accno = acc
                print(f"    📑  Found 10-K filing: {date}")
                break

        if not accno:
            print(f"    ⚠️  No 10-K found on EDGAR for {ticker}")
            return None

        # 3. Get filing index to find the main document
        accno_clean = accno.replace("-", "")
        index_url   = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accno_clean}/{accno}-index.htm"
        idx_r = requests.get(index_url, headers=EDGAR_HEADERS, timeout=15)
        idx_r.raise_for_status()
        soup  = BeautifulSoup(idx_r.text, "html.parser")

        # 4. Find the main 10-K document (htm/html, not exhibit)
        doc_url = None
        for row in soup.select("table tr"):
            cells = row.find_all("td")
            if len(cells) >= 4:
                doc_type = cells[3].get_text(strip=True)
                if doc_type == "10-K":
                    a = cells[2].find("a")
                    if a and a.get("href"):
                        doc_url = "https://www.sec.gov" + a["href"]
                        break

        if not doc_url:
            # Fallback: first htm link in the index
            for a in soup.find_all("a", href=True):
                if a["href"].endswith(".htm") and accno_clean in a["href"]:
                    doc_url = "https://www.sec.gov" + a["href"]
                    break

        if not doc_url:
            print(f"    ⚠️  Could not locate 10-K document for {ticker}")
            return None

        # 5. Download and extract text
        print(f"    📥  Fetching 10-K from EDGAR...")
        doc_r = requests.get(doc_url, headers=EDGAR_HEADERS, timeout=60)
        doc_r.raise_for_status()
        text = BeautifulSoup(doc_r.text, "html.parser").get_text(separator="\n")
        print(f"    ✅  Got {len(text):,} chars of 10-K text")
        return text

    except Exception as e:
        print(f"    ❌  EDGAR fetch failed for {ticker}: {e}")
        return None


# ── Strategy B: IR page scraping + PDF for Nordic ────────────────────────────

def _find_pdf_on_page(ir_url: str, target_years: list) -> Optional[str]:
    """Scrape an IR page for annual report PDF links."""
    try:
        r = requests.get(ir_url, headers=BROWSER_HEADERS, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print(f"    ⚠️  Could not fetch IR page ({e})")
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    base = f"{urlparse(ir_url).scheme}://{urlparse(ir_url).netloc}"

    candidates = []
    for a in soup.find_all("a", href=True):
        href  = a["href"].strip()
        text  = a.get_text(" ", strip=True).lower()
        label = (href + " " + text).lower()

        is_pdf    = ".pdf" in label
        is_annual = any(term in label for term in ANNUAL_TERMS)
        if not (is_pdf and is_annual):
            continue

        abs_url = href if href.startswith("http") else urljoin(base, href)

        year_score = 0
        for i, yr in enumerate(target_years):
            if str(yr) in label:
                year_score = len(target_years) - i
                break

        candidates.append((year_score, abs_url))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def _download_pdf(url: str, dest: str) -> bool:
    try:
        r = requests.get(url, headers=BROWSER_HEADERS, timeout=60, stream=True)
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                f.write(chunk)
        print(f"    📥  Downloaded {os.path.getsize(dest)/1_048_576:.1f} MB")
        return True
    except Exception as e:
        print(f"    ❌  PDF download failed: {e}")
        if os.path.exists(dest):
            os.remove(dest)
        return False


def _extract_pdf_text(pdf_path: str, max_chars: int = 350_000) -> str:
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

        # Too long: keep first 10 pages + top 40 by keyword density
        first    = pages[:10]
        rest     = sorted(pages[10:], key=lambda x: x[2], reverse=True)[:40]
        selected = sorted(first + rest, key=lambda x: x[0])
        return "\n\n".join(f"[PAGE {n}]\n{t}" for n, t, _ in selected)[:max_chars]
    except Exception as e:
        return f"[PDF extraction error: {e}]"


def _truncate_text(text: str, max_chars: int = 350_000) -> str:
    """Smart truncation: keep start + highest-density middle sections."""
    if len(text) <= max_chars:
        return text
    # Keep first 50k chars (cover/highlights) + last 300k chars
    return text[:50_000] + "\n\n[... truncated ...]\n\n" + text[-(max_chars - 50_000):]


# ── Claude analysis ───────────────────────────────────────────────────────────

_PROMPT = """\
You are Barren Wuffett's research assistant. Read the following annual report
and return ONLY a valid JSON object — no markdown, no preamble.

Extract exactly these fields:
{{
  "report_year":                        <integer — fiscal year>,
  "dividend_history":                   <string — recent dividend amounts and trend>,
  "dividend_policy":                    <string — stated payout policy or targets>,
  "dividend_sustainability_commentary": <string — management commentary on sustaining/growing dividend>,
  "free_cash_flow_trend":               <string — FCF figures for last 2-3 years>,
  "net_debt":                           <string — net debt level and trend>,
  "debt_covenants":                     <string — any debt covenants or financial constraints>,
  "earnings_guidance":                  <string — forward guidance on earnings or dividend>,
  "dividend_risks":                     <string — key risks to dividend continuity>,
  "barren_annual_score":                <integer 1-100 — dividend safety rating>,
  "barren_annual_notes":                <string — 2-3 sentences Barren commentary on findings>
}}

ANNUAL REPORT TEXT:
{text}
"""

def _analyse_with_claude(text: str) -> dict:
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": _PROMPT.format(text=text)}],
    )
    raw = response.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    return json.loads(raw)


# ── Public entry point ────────────────────────────────────────────────────────

def get_annual_report_data(ticker: str, company_name: str = "") -> dict:
    """
    Returns structured annual report data. Uses cache if available.
    US tickers use SEC EDGAR; Nordic tickers scrape IR pages for PDFs.
    Returns {} if nothing can be retrieved.
    """
    target_years = [CURRENT_YEAR - 1, CURRENT_YEAR - 2]

    # Check cache
    for year in target_years:
        jp = _json_path(ticker, year)
        if os.path.exists(jp):
            print(f"    📋  Using cached report ({ticker} {year})")
            with open(jp) as f:
                return json.load(f)

    print(f"    🔍  Fetching annual report for {ticker}...")
    text = None
    year = target_years[0]

    # US: SEC EDGAR
    if ticker in EDGAR_CIKS:
        text = _get_edgar_text(ticker)

    # Nordic: IR page scraping
    elif ticker in IR_PAGES:
        pdf_url = _find_pdf_on_page(IR_PAGES[ticker], target_years)
        if not pdf_url:
            print(f"    ⚠️  No PDF found for {ticker}")
            return {}

        for yr in target_years:
            if str(yr) in pdf_url:
                year = yr
                break

        pdf_dest = _pdf_path(ticker, year)
        if not os.path.exists(pdf_dest):
            if not _download_pdf(pdf_url, pdf_dest):
                return {}

        text = _extract_pdf_text(pdf_dest)

    if not text:
        return {}

    print(f"    🤖  Analysing with Claude...")
    try:
        result = _analyse_with_claude(_truncate_text(text))
        result["source"]     = "EDGAR" if ticker in EDGAR_CIKS else "IR page"
        result["fetched_at"] = datetime.now().isoformat()

        with open(_json_path(ticker, year), "w") as f:
            json.dump(result, f, indent=2)
        print(f"    ✅  Saved report data ({ticker} {year})")

    except Exception as e:
        print(f"    ❌  Claude analysis failed: {e}")
        return {}

    time.sleep(1)
    return result


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from barren_scorer import NORDIC, US_ARISTOCRATS

    tickers_map = {t: "Nordic" for t in NORDIC}
    tickers_map.update({t: "US" for t in US_ARISTOCRATS})

    # Allow passing specific tickers on the command line
    targets = sys.argv[1:] if len(sys.argv) > 1 else list(tickers_map.keys())

    print("=" * 60)
    print("  BARREN — Annual Report Analyser")
    print(f"  Processing {len(targets)} tickers")
    print("=" * 60)

    for ticker in targets:
        print(f"\n📄 {ticker} ({tickers_map.get(ticker, '?')})")
        data = get_annual_report_data(ticker)
        if data:
            print(f"   Score : {data.get('barren_annual_score', '—')}/100")
            print(f"   Policy: {str(data.get('dividend_policy', '—'))[:100]}")
            print(f"   Notes : {str(data.get('barren_annual_notes', '—'))[:150]}")
        else:
            print("   No data retrieved.")
