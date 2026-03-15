# 🧪 Barren Wuffett Capital Research

[![Live Dashboard](https://img.shields.io/badge/Live%20Dashboard-web--production--0de447.up.railway.app-amber?style=for-the-badge&logo=railway)](https://web-production-0de447.up.railway.app)
[![Telegram](https://img.shields.io/badge/Telegram-@BARRENWUFFETTT-2CA5E0?style=for-the-badge&logo=telegram)](https://t.me/BARRENWUFFETTT)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python)](https://python.org)
[![Claude AI](https://img.shields.io/badge/Powered%20by-Claude%20AI-8B5CF6?style=for-the-badge)](https://anthropic.com)
[![Railway](https://img.shields.io/badge/Deployed%20on-Railway-0B0D0E?style=for-the-badge&logo=railway)](https://railway.app)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

> *"The dividends, my friend, are blowin' in the wind!"*

**Barren Wuffett** is an autonomous AI dividend-intelligence agent that scans 60+ global dividend stocks daily, scores each one using a multi-factor model powered by Claude AI, generates PDF research certificates, and broadcasts top picks to a Telegram channel — all running 24/7 on Railway.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Setup & Installation](#setup--installation)
- [Configuration](#configuration)
- [Running Locally](#running-locally)
- [Railway Deployment](#railway-deployment)
- [How the Barren Score Works](#how-the-barren-score-works)
- [Watchlist Coverage](#watchlist-coverage)
- [The Persona](#the-persona)
- [Kill Switch](#kill-switch)
- [Annual Report Reader](#annual-report-reader)
- [Contributing & Roadmap](#contributing--roadmap)

---

## Overview

Barren Wuffett is a full-stack autonomous research agent built on top of Claude AI. Every morning at **07:30 Oslo time**, it:

1. Fetches live price and fundamental data for 60+ dividend stocks across 7 global markets via Yahoo Finance.
2. Sends each stock through Claude (claude-sonnet-4-6), which embodies the "Barren Wuffett" persona, and scores it across five dimensions.
3. Projects the stock's annual yield (APY) at 1, 3, 5, 10, and 20-year horizons.
4. Generates a styled **PDF Dividend Intelligence Certificate** for every stock.
5. Broadcasts top picks (score ≥ 60) with full research notes to the public Telegram channel **@BARRENWUFFETTT**.
6. Serves the full leaderboard, certificates, and stats on a public web dashboard.

For supported tickers, Barren also reads actual **annual reports** — pulling 10-K filings from SEC EDGAR (US stocks) and PDF reports from Nordic IR pages — to deepen the scoring with real management commentary and financial detail.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    BARREN WUFFETT SYSTEM                        │
│                                                                 │
│  ┌────────────┐   07:30 Oslo   ┌─────────────────────────────┐ │
│  │ APScheduler│ ──────────────▶│      barren_scorer.py       │ │
│  │ (in-process│                │  Yahoo Finance → fetch data │ │
│  │  cron job) │                │  Claude AI → score & thesis │ │
│  └────────────┘                │  Annual reports (optional)  │ │
│                                └──────────┬──────────────────┘ │
│                                           │ scan_results.json   │
│                          ┌────────────────▼──────────────────┐  │
│                          │      barren_certificate.py        │  │
│                          │   ReportLab → PDF per stock       │  │
│                          └────────────────┬──────────────────┘  │
│                                           │ certificates/*.pdf  │
│                          ┌────────────────▼──────────────────┐  │
│                          │       barren_telegram.py          │  │
│                          │   Broadcasts top picks (≥60)     │  │
│                          └───────────────────────────────────┘  │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                  barren_dashboard.py (Flask)              │  │
│  │   /        → Leaderboard card grid + stats               │  │
│  │   /certificate/<ticker> → Serve PDF certificates         │  │
│  └────────────────────────────┬──────────────────────────────┘  │
│                               │                                 │
│  ┌────────────────────────────▼──────────────────────────────┐  │
│  │              gunicorn (Railway / local)                   │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐    │
│  │ barren_annual_reports.py                               │    │
│  │  US:     SEC EDGAR 10-K API → HTML → Claude extract   │    │
│  │  Nordic: Direct PDF URLs / IR page scraping → Claude  │    │
│  │  Cache:  reports/<ticker>_<year>.json                  │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌──────────────┐   ┌────────────────┐   ┌──────────────────┐  │
│  │barren_       │   │barren_         │   │   persona/       │  │
│  │killswitch.py │   │inference.py    │   │   SOUL.md        │  │
│  │KILLSWITCH    │   │Claude primary  │   │   GOALS.md       │  │
│  │file sentinel │   │Ollama fallback │   │   MEMORY.md      │  │
│  └──────────────┘   └────────────────┘   └──────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Features

- **Daily Autonomous Scans** — APScheduler cron runs at 07:30 Oslo time every day; a background thread on startup ensures the first scan bootstraps immediately if no data exists.
- **60+ Global Stocks** — Nordic (Oslo Børs), US Dividend Aristocrats, UK FTSE 100, European Champions, ASX, and SGX all covered.
- **AI Scoring Engine** — Claude generates six sub-scores, conviction rating, investment thesis, key risk, projected APY at five time horizons, and a "Barren quip" for every stock.
- **PDF Certificates** — Beautiful A4 Dividend Intelligence Certificates generated with ReportLab, numbered with `BW-2026-XXXX` serial numbers and served directly from the dashboard.
- **Telegram Broadcasts** — Formatted HTML messages with full research notes sent to [@BARRENWUFFETTT](https://t.me/BARRENWUFFETTT) after every scan.
- **Web Dashboard** — Responsive Flask UI with conviction-filter buttons, score circles, projected yield grids, and per-stock certificate download links.
- **Annual Report Reader** — Fetches and Claude-analyses real annual reports: 10-K filings via SEC EDGAR for US stocks, PDF downloads for Nordic stocks.
- **Kill Switch** — A single file (`KILLSWITCH`) or message phrase `STOP ALL IMMEDIATELY` halts all activity instantly.
- **Three-Tier Inference** — Primary: Claude API. Fallback: local Ollama (currently disabled pending M5 Metal fix). Graceful failure handling throughout.
- **Railway-native** — Nixpacks build, gunicorn web server, health check path, failure restart policy — zero-config cloud deployment.

---

## Tech Stack

| Layer | Technology |
|---|---|
| AI Inference | [Anthropic Claude](https://anthropic.com) (claude-sonnet-4-6) |
| Web Framework | [Flask](https://flask.palletsprojects.com) 3.1 |
| WSGI Server | [Gunicorn](https://gunicorn.org) 23 |
| Scheduling | [APScheduler](https://apscheduler.readthedocs.io) 3.11 |
| Market Data | [yfinance](https://github.com/ranaroussi/yfinance) 1.2 |
| PDF Generation | [ReportLab](https://www.reportlab.com) 4.4 |
| PDF Parsing | [pdfplumber](https://github.com/jsvine/pdfplumber) 0.11 |
| HTML Parsing | [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) 4.14 |
| Data Analysis | [pandas](https://pandas.pydata.org) 2.3 |
| HTTP Client | [requests](https://requests.readthedocs.io) 2.32 |
| Config | [python-dotenv](https://github.com/theskumar/python-dotenv) 1.2 |
| Deployment | [Railway](https://railway.app) (Nixpacks) |
| Local Fallback LLM | [Ollama](https://ollama.ai) + qwen2.5:14b |

---

## Project Structure

```
barren-wuffet/
│
├── barren_scorer.py          # Core scanner: fetches data, calls Claude, runs watchlist
├── barren_dashboard.py       # Flask web app: leaderboard UI + certificate serving
├── barren_certificate.py     # ReportLab PDF certificate generator
├── barren_telegram.py        # Telegram broadcast: formats and sends research alerts
├── barren_scheduler.py       # Local scheduler: subprocess-based daily pipeline
├── barren_inference.py       # Three-tier inference: Claude API → Ollama → hard fail
├── barren_killswitch.py      # Kill switch: file sentinel + message phrase detection
├── barren_annual_reports.py  # Annual report reader: SEC EDGAR (US) + PDF (Nordic)
│
├── persona/
│   ├── SOUL.md               # Barren's identity, voice, philosophy, guardrails
│   ├── GOALS.md              # Mission, active goals, watchlist coverage, roadmap
│   └── MEMORY.md             # Scan history, key findings, lessons learned
│
├── reports/                  # Cached annual report JSON + downloaded PDFs
│   └── <TICKER>_<YEAR>.json
│
├── certificates/             # Generated PDF certificates
│   └── BW_<TICKER>_<NAME>.pdf
│
├── logs/                     # Local run logs (gitignored)
│   ├── barren.log
│   ├── dashboard.log
│   ├── scheduler.log
│   └── ollama.log
│
├── scan_results.json         # Latest scan output (auto-generated, gitignored)
├── start_barren.sh           # Local master startup script (Ollama + Flask + scheduler)
├── Procfile                  # Railway/Heroku process definition
├── railway.json              # Railway deployment configuration
├── requirements.txt          # Python dependencies
└── .env                      # Local secrets (never committed)
```

---

## Setup & Installation

### Prerequisites

- Python 3.11+
- An [Anthropic API key](https://console.anthropic.com)
- A Telegram bot token and channel chat ID (for broadcasts)

### 1. Clone the repo

```bash
git clone https://github.com/BarrenWuffet402/barren-wuffet.git
cd barren-wuffet
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate   # macOS/Linux
# venv\Scripts\activate    # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create your `.env` file

```bash
cp .env.example .env   # or create from scratch — see Configuration below
```

---

## Configuration

Create a `.env` file in the project root with the following variables:

```env
# ── Required ──────────────────────────────────────────────────────────────────

# Anthropic Claude API key
ANTHROPIC_API_KEY=sk-ant-...

# Telegram bot token (from @BotFather)
TELEGRAM_BOT_TOKEN=123456789:AAxxxxxx...

# Telegram channel or chat ID to broadcast to
# For a public channel use the numeric ID (e.g. -1001234567890)
# or the channel username (e.g. @BARRENWUFFETTT)
TELEGRAM_CHAT_ID=@BARRENWUFFETTT

# ── Optional ──────────────────────────────────────────────────────────────────

# Port for the Flask dashboard (defaults to 5000 locally)
PORT=5000

# Set on Railway automatically — disables annual report fetching to save memory
# RAILWAY_ENVIRONMENT=production
```

> **Note:** `ANTHROPIC_API_KEY` is the only variable required to run a scan. Telegram variables are only needed for broadcasts. The `RAILWAY_ENVIRONMENT` variable is injected automatically by Railway and skips annual report downloading to conserve worker memory.

---

## Running Locally

### Option A — Full stack (recommended)

The `start_barren.sh` script launches Ollama (local LLM fallback), the Flask dashboard, and the scheduler in one shot:

```bash
chmod +x start_barren.sh
./start_barren.sh
```

Then open [http://localhost:5000](http://localhost:5000) in your browser.

### Option B — Dashboard only

```bash
source venv/bin/activate
python barren_dashboard.py
```

The dashboard will auto-bootstrap on first launch: it runs a full scan, generates certificates, and sends a Telegram broadcast before serving the UI.

### Option C — Manual scan

```bash
source venv/bin/activate
python barren_scorer.py
```

Results are written to `scan_results.json`.

### Option D — Certificates only

```bash
python barren_certificate.py
```

Reads `scan_results.json` and writes PDFs to `certificates/`.

### Option E — Telegram broadcast only

```bash
python barren_telegram.py
```

Reads `scan_results.json` and sends all picks with score ≥ 60 to Telegram.

### Option F — Annual reports

```bash
# Analyse all watchlist tickers
python barren_annual_reports.py

# Analyse specific tickers
python barren_annual_reports.py EQNR.OL DNB.OL KO JNJ
```

### Kill switch (CLI)

```bash
python barren_killswitch.py status   # check current state
python barren_killswitch.py kill     # halt all activity
python barren_killswitch.py revive   # resume activity
```

---

## Railway Deployment

The project is fully configured for zero-config deployment on [Railway](https://railway.app).

### One-click deploy from this repo

1. Fork or push this repo to GitHub.
2. Create a new Railway project and connect the repo.
3. Add the required environment variables in Railway's **Variables** tab:
   - `ANTHROPIC_API_KEY`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
4. Railway will auto-detect `railway.json` and `Procfile` and deploy.

### What happens on Railway

```
Railway builds with Nixpacks
    ↓
gunicorn barren_dashboard:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120
    ↓
Flask app starts → background thread runs _bootstrap()
    ↓
If scan_results.json is missing or empty:
    → run_scan() over full WATCHLIST
    → generate_all_certificates()
    → broadcast_top_picks() to Telegram
    ↓
APScheduler cron fires daily at 07:30 Europe/Oslo
    → force re-scan → re-generate certificates → re-broadcast
```

A `.bootstrap.lock` file prevents duplicate bootstraps when Railway runs two replicas simultaneously.

Annual report fetching is automatically **disabled** on Railway (`RAILWAY_ENVIRONMENT` is set by the platform) to stay within memory constraints. All other scoring runs normally.

### Deployment files

| File | Purpose |
|---|---|
| `Procfile` | Defines the `web` process for gunicorn |
| `railway.json` | Build (Nixpacks), start command, health check, restart policy |
| `requirements.txt` | All Python dependencies pinned to exact versions |

---

## How the Barren Score Works

Every stock in the watchlist receives a **Barren Score** from 1–100. This is a holistic conviction score produced by Claude, drawing on five sub-dimensions plus optional annual report enrichment.

### Sub-scores

| Sub-score | What it measures |
|---|---|
| **Dividend Score** (1–100) | Current yield size, consistency, CAGR, and payout ratio sustainability |
| **Balance Sheet Score** (1–100) | Debt-to-equity, free cash flow, interest coverage — can the company *keep paying*? |
| **Sector Safety Score** (1–100) | Sector defensiveness: utilities/staples/healthcare score high; cyclicals score lower |
| **Value Score** (1–100) | Price vs intrinsic value — P/E, P/B, analyst target vs current price |
| **Growth Score** (1–100) | Long-term dividend growth potential: revenue growth, ROE, reinvestment capacity |

### Overall Barren Score

Claude synthesises the five sub-scores, the raw financial data, and (when available) annual report findings into a single **Barren Score**. It is not a simple average — the model weights balance sheet and payout sustainability more heavily than raw yield, in line with Barren's philosophy.

### Conviction ratings

| Rating | Meaning |
|---|---|
| **STRONG BUY** | High conviction; sustainable yield, strong balance sheet, attractive valuation |
| **BUY** | Good fundamentals; minor concerns but overall positive |
| **WATCH** | Interesting but not quite there — worth monitoring |
| **AVOID** | Unsustainable payout, weak balance sheet, or structurally challenged sector |

### Projected APY

For each stock, Claude projects the **Annual Percentage Yield** (income return on today's purchase price, compounded) at five horizons:

```
1yr  → baseline expectation
3yr  → near-term trend
5yr  → primary target (highlighted in dashboard and certificates)
10yr → medium-term compounding
20yr → long-term compounding (Barren's true horizon)
```

These projections incorporate the current yield, 5-year dividend CAGR, payout sustainability, and growth outlook.

### Annual report enrichment

When annual report data is available (see [Annual Report Reader](#annual-report-reader)), Claude receives an additional JSON block covering:

- Dividend history and policy
- Free cash flow trend
- Net debt and covenants
- Forward earnings guidance
- Dividend risk commentary

This enrichment can shift the Barren Score by ±10–15 points for stocks where management guidance diverges significantly from trailing metrics.

---

## Watchlist Coverage

The active `WATCHLIST` (in `barren_scorer.py`) is the union of the Nordic and US Aristocrat groups. The full watchlist across all six regions covers **60 stocks** and is tracked in `persona/GOALS.md`.

### Active scan (25 stocks)

| Region | Tickers |
|---|---|
| **Nordic** (Oslo Børs) | EQNR.OL, AKRBP.OL, DNB.OL, GJF.OL, ORK.OL, TEL.OL, MOWI.OL, STB.OL, YAR.OL, SALM.OL |
| **US Aristocrats** | JNJ, KO, PG, MMM, CL, ABT, EMR, GPC, PEP, T, VZ, MCD, WMT, XOM, CVX |

### Defined but not yet in active scan (35 stocks)

| Region | Tickers |
|---|---|
| **UK FTSE 100** | SHEL.L, BP.L, ULVR.L, GSK.L, AZN.L, HSBA.L, LLOY.L, VOD.L, NG.L, SSE.L |
| **European Champions** | ALV.DE, MUV2.DE, SIE.DE, BAYN.DE, MC.PA, TTE.PA, SAN.PA, OR.PA, ASML.AS, ABN.AS, NOVN.SW, NESN.SW, ROG.SW |
| **Australia (ASX)** | CBA.AX, BHP.AX, WBC.AX, ANZ.AX, TLS.AX, WES.AX |
| **Singapore (SGX)** | D05.SI, O39.SI, U11.SI, Z74.SI, C6L.SI, C38U.SI |

To activate all 60 stocks, update the `WATCHLIST` line in `barren_scorer.py`:

```python
WATCHLIST = NORDIC + US_ARISTOCRATS + UK_FTSE + EUROPE + AUSTRALIA + SINGAPORE
```

---

## The Persona

Barren Wuffett is not just a script — it is a character with a defined identity, voice, and philosophy, stored in the `persona/` directory and injected into every Claude prompt.

### Identity (`persona/SOUL.md`)

**Barren Wuffett** is a slightly-genius, warmhearted, fanatic dividend investor with the enthusiasm of a mad scientist who has just discovered compound interest. He is deeply kind, endlessly curious, and genuinely thrilled by dividend data.

**Voice characteristics:**
- Warm, direct, occasionally unhinged with excitement
- Uses vivid analogies and metaphors
- Calls followers *"my dividend friends"* or *"fellow compounders"*
- When excited: verbose, exclamation marks, ALL CAPS for emphasis
- When analysing risk: precise, measured, honest
- Signs off as *"— Barren Wuffett"* or *"🧪 Barren"*

**Investment philosophy:**
- Dividend yield is the foundation, not the ceiling
- Balance sheet strength matters more than yield size
- Payout ratio is the heartbeat — it must be sustainable
- Sector safety and geography determine long-term survival
- Time horizon: 5–20 years minimum

### Goals (`persona/GOALS.md`)

Current mission: *"Build the world's most entertaining and rigorous dividend intelligence research service."*

Key targets: sustainable yield > 4%, Barren Score > 65.

### Memory (`persona/MEMORY.md`)

Barren maintains a running memory of scan history, key findings, and lessons learned. Notable early observations:
- **DNB Bank ASA** — Norway's most reliable dividend compounder (78/100)
- **Gjensidige** — Insurance fortress, 23% ROE, solid Nordic moat
- **Aker BP** — High yield (7.9%) but 1196% payout ratio — AVOID
- **SalMar** — 268% payout ratio — dividend built on debt

---

## Kill Switch

Barren includes a hard safety mechanism that immediately halts all activity when triggered.

### How it works

The kill switch is a simple **file sentinel**. When the file `~/barren-wuffet/KILLSWITCH` exists, Barren will not run any scans, generate certificates, or send Telegram messages. It respects the kill switch at the start of every scheduled run.

### Activation methods

**1. CLI**
```bash
python barren_killswitch.py kill    # halt
python barren_killswitch.py revive  # resume
python barren_killswitch.py status  # check
```

**2. Direct file creation**
```bash
touch ~/barren-wuffet/KILLSWITCH    # halt
rm ~/barren-wuffet/KILLSWITCH       # resume
```

**3. Magic phrase**

Sending the exact phrase `STOP ALL IMMEDIATELY` anywhere that `check_message_for_killswitch()` is called will activate the kill switch programmatically. No arguments. No exceptions. No delays.

### Kill switch in code

The `barren_scheduler.py` checks the kill switch at the top of every `run_barren()` invocation:

```python
from barren_killswitch import is_killed

def run_barren():
    if is_killed():
        print("Kill switch active — skipping scan.")
        return
```

---

## Annual Report Reader

`barren_annual_reports.py` is an optional enrichment layer that fetches, parses, and Claude-analyses actual annual reports before scoring.

### Two discovery strategies

**US stocks — SEC EDGAR**

Uses the free, public [EDGAR REST API](https://efts.sec.gov/LATEST/search-index?q=%2210-K%22). No scraping, no authentication, no rate-limit issues. Supports all 15 US Aristocrats with hardcoded CIK numbers.

Process:
1. Fetch submission metadata from `data.sec.gov/submissions/CIK<cik>.json`
2. Locate the most recent 10-K filing
3. Download the main HTML document
4. Strip XBRL metadata, extract clean text
5. Send to Claude for structured JSON extraction

**Nordic stocks — IR page + PDF**

Two-stage fallback:
1. **Direct PDF URLs** (hardcoded, updated annually) — fastest and most reliable
2. **IR page scraping** (BeautifulSoup, keyword matching on `annual`/`årsrapport`) — fallback

Process:
1. Download PDF to `reports/<ticker>_<year>.pdf`
2. Extract text with `pdfplumber`, scoring pages by keyword density
3. Select first 10 pages + top 40 keyword-dense pages (cap: 350,000 chars)
4. Send to Claude for structured JSON extraction

### Extracted fields

```json
{
  "report_year": 2024,
  "dividend_history": "...",
  "dividend_policy": "...",
  "dividend_sustainability_commentary": "...",
  "free_cash_flow_trend": "...",
  "net_debt": "...",
  "debt_covenants": "...",
  "earnings_guidance": "...",
  "dividend_risks": "...",
  "barren_annual_score": 82,
  "barren_annual_notes": "..."
}
```

### Caching

Results are cached to `reports/<ticker>_<year>.json`. Subsequent runs read from cache — no duplicate API calls, no re-downloading PDFs. Cache is valid for the duration of that fiscal year.

### On Railway

Annual report fetching is **disabled** on Railway (`RAILWAY_ENVIRONMENT` is set) to avoid memory pressure from large PDF downloads. It runs fully on local deployments.

---

## Contributing & Roadmap

### How to contribute

1. Fork the repo on GitHub: [github.com/BarrenWuffet402/barren-wuffet](https://github.com/BarrenWuffet402/barren-wuffet)
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes and add tests if relevant
4. Open a pull request with a clear description

### Roadmap

#### Phase 3 — REITs worldwide (next)
- [ ] Add REIT watchlist: US (VNQ components), Singapore (CapitaLand, Mapletree), Australian (Goodman, Scentre)
- [ ] REIT-specific scoring adjustments (FFO-based payout ratio, NAV discount)
- [ ] REIT section in dashboard

#### Phase 4 — Emerging markets
- [ ] Brazil: Itaú, Petrobras, Vale dividends
- [ ] South Africa: Naspers, Standard Bank
- [ ] India: HDFC, Infosys dividends

#### Phase 5 — Platform
- [ ] Enable all 60 stocks in active `WATCHLIST`
- [ ] Historical score tracking — chart Barren Score over time
- [ ] Email digest subscription
- [ ] Portfolio tracker: enter your holdings, see your projected personal income
- [ ] Webhook for Telegram kill-switch commands
- [ ] Re-enable Ollama fallback once Apple M5 Metal support ships

#### Infrastructure
- [ ] Persistent storage on Railway (avoid cold-start re-scans)
- [ ] Redis cache for scan results
- [ ] Scheduled certificate archiving to S3/R2

---

## Disclaimer

Barren Wuffett is an autonomous AI research agent. All output — scores, theses, projections, and certificates — is **for informational purposes only and does not constitute financial advice**. Past dividend behaviour does not guarantee future payments. Always do your own research before making investment decisions.

---

<div align="center">

**© 2026 Barren Wuffett Capital Research · Powered by Claude AI · Data: Yahoo Finance**

*"We don't chase yield, we compound it. The tortoise always beats the hare, especially when the tortoise pays dividends!"*

[Dashboard](https://web-production-0de447.up.railway.app) · [Telegram](https://t.me/BARRENWUFFETTT) · [GitHub](https://github.com/BarrenWuffet402/barren-wuffet)

</div>
