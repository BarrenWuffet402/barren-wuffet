import os
import json
import threading
from flask import Flask, render_template_string, send_file, abort, jsonify
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

load_dotenv()

app = Flask(__name__)

BASE      = os.path.dirname(os.path.abspath(__file__))
RESULTS   = os.path.join(BASE, "scan_results.json")
CERTS     = os.path.join(BASE, "certificates")
DEEP_DIR  = os.path.join(BASE, "certificates", "deep")


def _bootstrap():
    """Run on startup: generate scan_results.json and certificates if missing."""
    needs_scan  = not os.path.exists(RESULTS) or os.path.getsize(RESULTS) < 10
    needs_certs = not os.path.isdir(CERTS) or len([f for f in os.listdir(CERTS) if f.endswith(".pdf")]) == 0

    if not needs_scan and not needs_certs:
        return

    # Lock file prevents duplicate bootstrap if Railway runs two instances simultaneously
    lock = os.path.join(BASE, ".bootstrap.lock")
    if os.path.exists(lock):
        print("⏳ Bootstrap already running in another process — skipping.")
        return
    open(lock, "w").close()

    print("🚀 Bootstrap: generating missing data...")

    try:
        if needs_scan:
            print("📡 Running stock scan (this takes a few minutes)...")
            try:
                import sys
                sys.path.insert(0, BASE)
                from barren_scorer import run_scan, WATCHLIST
                results = run_scan(WATCHLIST)
                with open(RESULTS, "w") as f:
                    json.dump(results, f, indent=2)
                print(f"✅ Scan complete — {len(results)} stocks saved.")
            except Exception as e:
                print(f"❌ Scan failed: {e}")
                return

        if needs_certs:
            print("🎨 Generating certificates...")
            try:
                from barren_certificate import generate_all_certificates
                generate_all_certificates(json_file=RESULTS, output_dir=CERTS)
                print("✅ Certificates generated.")
            except Exception as e:
                print(f"❌ Certificate generation failed: {e}")

        print("📣 Broadcasting to Telegram...")
        try:
            from barren_telegram import broadcast_top_picks
            broadcast_top_picks(json_file=RESULTS)
            print("✅ Telegram broadcast sent.")
        except Exception as e:
            print(f"❌ Telegram broadcast failed: {e}")
    finally:
        if os.path.exists(lock):
            os.remove(lock)


def _daily_scan():
    """Full scan + certificates + Telegram — runs on schedule."""
    print("⏰ Daily scan triggered by scheduler...")
    # Force re-scan by temporarily removing results
    if os.path.exists(RESULTS):
        os.remove(RESULTS)
    _bootstrap()


# ── Daily scheduler — 07:30 Oslo time ────────────────────────────────────────
_scheduler = BackgroundScheduler(timezone="Europe/Oslo")
_scheduler.add_job(_daily_scan, CronTrigger(hour=7, minute=30))
_scheduler.start()


# Kick off bootstrap in background so gunicorn starts immediately
threading.Thread(target=_bootstrap, daemon=True).start()

def load_results():
    if not os.path.exists(RESULTS):
        return []
    with open(RESULTS) as f:
        return json.load(f)

CONVICTION_EMOJI = {
    "STRONG BUY": "🟢",
    "BUY":        "🟡",
    "WATCH":      "🟠",
    "AVOID":      "🔴",
}

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Barren Wuffett Capital Research</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f8f6f0; color: #2c2c2a; line-height: 1.6; }

  header { background: #faeeda; border-bottom: 2px solid #ba7517;
           padding: 24px 40px; }
  header h1 { font-size: 28px; font-weight: 600; color: #412402; }
  header p  { color: #633806; font-size: 14px; margin-top: 4px; }
  header .tagline { font-style: italic; color: #854f0b; margin-top: 8px; font-size: 15px; }

  .stats { display: flex; gap: 24px; padding: 20px 40px;
           background: #fff; border-bottom: 1px solid #d3d1c7; flex-wrap: wrap; }
  .stat  { text-align: center; }
  .stat .num  { font-size: 28px; font-weight: 600; color: #412402; }
  .stat .label { font-size: 12px; color: #888780; text-transform: uppercase; letter-spacing: 1px; }

  .filters { padding: 16px 40px; display: flex; gap: 12px; flex-wrap: wrap;
             background: #f8f6f0; border-bottom: 1px solid #d3d1c7; }
  .filter-btn { padding: 6px 16px; border-radius: 20px; border: 1px solid #d3d1c7;
                background: white; cursor: pointer; font-size: 13px; color: #5f5e5a;
                transition: all 0.2s; }
  .filter-btn:hover, .filter-btn.active { background: #faeeda; border-color: #ba7517;
                                           color: #412402; }

  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
          gap: 20px; padding: 24px 40px; }

  .card { background: white; border-radius: 12px; border: 1px solid #d3d1c7;
          overflow: hidden; transition: transform 0.2s, box-shadow 0.2s; }
  .card:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.08); }

  .card-header { padding: 16px 20px; background: #faeeda; border-bottom: 1px solid #e8d5a0; }
  .card-header .name { font-size: 17px; font-weight: 600; color: #412402; }
  .card-header .meta { font-size: 12px; color: #854f0b; margin-top: 2px; }

  .card-body { padding: 16px 20px; }

  .conviction { display: inline-block; padding: 3px 12px; border-radius: 12px;
                font-size: 12px; font-weight: 600; margin-bottom: 12px; }
  .conv-STRONG-BUY { background: #e1f5ee; color: #04342c; }
  .conv-BUY        { background: #e1f5ee; color: #04342c; }
  .conv-WATCH      { background: #faeeda; color: #412402; }
  .conv-AVOID      { background: #fcebeb; color: #501313; }

  .score-row { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
  .score-circle { width: 52px; height: 52px; border-radius: 50%;
                  background: #faeeda; border: 2px solid #ba7517;
                  display: flex; flex-direction: column; align-items: center;
                  justify-content: center; flex-shrink: 0; }
  .score-circle .num   { font-size: 18px; font-weight: 700; color: #412402; line-height: 1; }
  .score-circle .label { font-size: 8px; color: #854f0b; text-transform: uppercase; }
  .sub-scores { font-size: 11px; color: #888780; line-height: 1.8; }

  .yields { display: grid; grid-template-columns: repeat(5, 1fr);
            gap: 4px; margin: 12px 0; }
  .yield-box { background: #eaf3de; border-radius: 6px; padding: 6px 4px;
               text-align: center; }
  .yield-box.primary { background: #e1f5ee; border: 1px solid #1d9e75; }
  .yield-box .yr  { font-size: 10px; color: #3b6d11; }
  .yield-box .pct { font-size: 14px; font-weight: 700; color: #173404; }
  .yield-box.primary .yr  { color: #085041; }
  .yield-box.primary .pct { font-size: 16px; color: #04342c; }

  .thesis { font-size: 12px; color: #5f5e5a; font-style: italic;
            border-left: 3px solid #fac775; padding-left: 10px;
            margin: 10px 0; line-height: 1.5;
            display: -webkit-box; -webkit-line-clamp: 3;
            -webkit-box-orient: vertical; overflow: hidden; }

  .quip { font-size: 11px; color: #888780; font-style: italic; margin-top: 8px; }

  .card-footer { padding: 12px 20px; border-top: 1px solid #f1efe8;
                 display: flex; justify-content: space-between; align-items: center; }
  .metrics { font-size: 11px; color: #888780; }
  .metrics span { margin-right: 10px; }
  .dl-btn { padding: 6px 14px; background: #412402; color: white;
            border-radius: 6px; font-size: 12px; text-decoration: none;
            transition: background 0.2s; }
  .dl-btn:hover { background: #633806; }

  footer { text-align: center; padding: 32px; color: #888780; font-size: 12px;
           border-top: 1px solid #d3d1c7; margin-top: 20px; }

  nav { background: #412402; display: flex; gap: 0; }
  nav a { color: #faeeda; padding: 10px 22px; font-size: 13px; font-weight: 500;
          text-decoration: none; letter-spacing: 0.5px; transition: background 0.2s; }
  nav a:hover { background: #633806; }
  nav a.active { background: #633806; border-bottom: 2px solid #fac775; }
</style>
</head>
<body>

<header>
  <h1>🧪 Barren Wuffett Capital Research</h1>
  <p>Autonomous dividend intelligence · Global markets</p>
  <p class="tagline">"The dividends, my friend, are blowin' in the wind!"</p>
</header>
<nav>
  <a href="/" class="active">Global</a>
  <a href="/norway">🇳🇴 Norway</a>
</nav>

<div class="stats">
  <div class="stat">
    <div class="num">{{ total }}</div>
    <div class="label">Stocks scanned</div>
  </div>
  <div class="stat">
    <div class="num">{{ buys }}</div>
    <div class="label">Buy / Strong buy</div>
  </div>
  <div class="stat">
    <div class="num">{{ avg_yield }}%</div>
    <div class="label">Avg current yield</div>
  </div>
  <div class="stat">
    <div class="num">{{ avg_5yr }}%</div>
    <div class="label">Avg 5yr projected APY</div>
  </div>
  <div class="stat">
    <div class="num">{{ last_scan }}</div>
    <div class="label">Last scan</div>
  </div>
</div>

<div class="filters">
  <button class="filter-btn active" onclick="filterCards('ALL')">All</button>
  <button class="filter-btn" onclick="filterCards('STRONG BUY')">🟢 Strong buy</button>
  <button class="filter-btn" onclick="filterCards('BUY')">🟡 Buy</button>
  <button class="filter-btn" onclick="filterCards('WATCH')">🟠 Watch</button>
  <button class="filter-btn" onclick="filterCards('AVOID')">🔴 Avoid</button>
</div>

<div class="grid" id="grid">
{% for r in results %}
<div class="card" data-conviction="{{ r.conviction_rating }}">
  <div class="card-header">
    <div class="name">{{ r.name or r.ticker }}</div>
    <div class="meta">{{ r.ticker }} · {{ r.sector }} · {{ r.country }}</div>
  </div>
  <div class="card-body">
    <div class="conviction conv-{{ r.conviction_rating.replace(' ', '-') }}">
      {{ conv_emoji.get(r.conviction_rating, '⚪') }} {{ r.conviction_rating }}
    </div>
    <div class="score-row">
      <div class="score-circle">
        <div class="num">{{ r.barren_score }}</div>
        <div class="label">score</div>
      </div>
      <div class="sub-scores">
        Dividend: {{ r.dividend_score }}<br>
        Balance sheet: {{ r.balance_sheet_score }}<br>
        Sector safety: {{ r.sector_safety_score }}<br>
        Value: {{ r.value_score }} · Growth: {{ r.growth_score }}
      </div>
    </div>
    <div class="yields">
      <div class="yield-box"><div class="yr">1yr</div><div class="pct">{{ "%.1f"|format(r.projected_yield_1y) }}%</div></div>
      <div class="yield-box"><div class="yr">3yr</div><div class="pct">{{ "%.1f"|format(r.projected_yield_3y) }}%</div></div>
      <div class="yield-box primary"><div class="yr">5yr ⭐</div><div class="pct">{{ "%.1f"|format(r.projected_yield_5y) }}%</div></div>
      <div class="yield-box"><div class="yr">10yr</div><div class="pct">{{ "%.1f"|format(r.projected_yield_10y) }}%</div></div>
      <div class="yield-box"><div class="yr">20yr</div><div class="pct">{{ "%.1f"|format(r.projected_yield_20y) }}%</div></div>
    </div>
    <div class="thesis">{{ r.thesis }}</div>
    <div class="quip">"{{ r.barren_quip }}"</div>
  </div>
  <div class="card-footer">
    <div class="metrics">
      <span>Yield: {{ r.dividend_yield }}%</span>
      <span>P/E: {{ "%.1f"|format(r.pe_ratio) if r.pe_ratio else "—" }}x</span>
      <span>Payout: {{ "%.0f"|format(r.payout_ratio) }}%</span>
    </div>
    <a href="/certificate/{{ r.ticker }}" class="dl-btn">📄 Certificate</a>
  </div>
</div>
{% endfor %}
</div>

<footer>
  © 2026 Barren Wuffett Capital Research · Powered by Claude AI · Not financial advice
</footer>

<script>
function filterCards(conviction) {
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');
  document.querySelectorAll('.card').forEach(card => {
    card.style.display = (conviction === 'ALL' ||
      card.dataset.conviction === conviction) ? 'block' : 'none';
  });
}
</script>
</body>
</html>
"""

NORWAY_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Norway — Barren Wuffett Capital Research</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f8f6f0; color: #2c2c2a; line-height: 1.6; }

  header { background: #faeeda; border-bottom: 2px solid #ba7517; padding: 24px 40px; }
  header h1 { font-size: 28px; font-weight: 600; color: #412402; }
  header p  { color: #633806; font-size: 14px; margin-top: 4px; }

  nav { background: #412402; display: flex; gap: 0; }
  nav a { color: #faeeda; padding: 10px 22px; font-size: 13px; font-weight: 500;
          text-decoration: none; letter-spacing: 0.5px; transition: background 0.2s; }
  nav a:hover { background: #633806; }
  nav a.active { background: #633806; border-bottom: 2px solid #fac775; }

  .page-body { padding: 28px 40px; }

  .intro { background: white; border: 1px solid #d3d1c7; border-radius: 10px;
           padding: 18px 22px; margin-bottom: 24px; max-width: 860px; }
  .intro h2 { font-size: 16px; color: #412402; margin-bottom: 6px; }
  .intro p  { font-size: 13px; color: #5f5e5a; line-height: 1.6; }
  .intro .highlight { background: #eaf3de; display: inline-block; padding: 2px 8px;
                      border-radius: 4px; font-weight: 600; color: #173404; font-size: 12px; }

  .controls { display: flex; align-items: center; gap: 14px; margin-bottom: 18px; flex-wrap: wrap; }
  .filter-input { padding: 7px 14px; border: 1px solid #d3d1c7; border-radius: 6px;
                  font-size: 13px; width: 220px; background: white; }
  .filter-input:focus { outline: none; border-color: #ba7517; }
  .sector-select { padding: 7px 14px; border: 1px solid #d3d1c7; border-radius: 6px;
                   font-size: 13px; background: white; cursor: pointer; }
  .refresh-btn { margin-left: auto; padding: 7px 16px; background: #412402; color: white;
                 border: none; border-radius: 6px; font-size: 13px; cursor: pointer;
                 text-decoration: none; transition: background 0.2s; }
  .refresh-btn:hover { background: #633806; }
  .last-updated { font-size: 12px; color: #888780; }

  table { width: 100%; border-collapse: collapse; background: white;
          border-radius: 10px; overflow: hidden; border: 1px solid #d3d1c7;
          font-size: 13px; }
  thead th { background: #412402; color: #faeeda; padding: 12px 14px;
             text-align: left; font-weight: 600; font-size: 12px;
             letter-spacing: 0.5px; white-space: nowrap; cursor: pointer;
             user-select: none; }
  thead th:hover { background: #633806; }
  thead th .sort-arrow { margin-left: 4px; opacity: 0.5; }
  thead th.sorted .sort-arrow { opacity: 1; }

  tbody tr { border-bottom: 1px solid #f1efe8; transition: background 0.15s; }
  tbody tr:last-child { border-bottom: none; }
  tbody tr:hover { background: #fdf9f2; }
  tbody td { padding: 11px 14px; vertical-align: middle; }

  .ticker-col { font-weight: 700; color: #412402; font-size: 13px; }
  .name-col   { color: #2c2c2a; }
  .sector-badge { display: inline-block; padding: 2px 8px; border-radius: 10px;
                  font-size: 11px; background: #faeeda; color: #633806; white-space: nowrap; }
  .metric { font-weight: 600; color: #2c2c2a; }
  .metric.yield-high { color: #04342c; }
  .metric.yield-mid  { color: #412402; }
  .metric.yield-low  { color: #888780; }
  .metric.good { color: #04342c; }
  .metric.warn { color: #854f0b; }
  .metric.bad  { color: #501313; }
  .na { color: #c5c3bb; font-size: 12px; }

  .fritaks-badge { display: inline-block; font-size: 10px; background: #e1f5ee;
                   color: #04342c; padding: 2px 6px; border-radius: 4px;
                   font-weight: 600; }

  .summary-row { display: flex; gap: 24px; margin-bottom: 20px; flex-wrap: wrap; }
  .summary-stat { background: white; border: 1px solid #d3d1c7; border-radius: 8px;
                  padding: 14px 20px; text-align: center; min-width: 130px; }
  .summary-stat .num   { font-size: 26px; font-weight: 700; color: #412402; }
  .summary-stat .label { font-size: 11px; color: #888780; text-transform: uppercase;
                         letter-spacing: 0.8px; margin-top: 2px; }

  .no-data { text-align: center; padding: 60px; color: #888780; }

  /* Deep analysis cards */
  .deep-section { margin-bottom: 28px; }
  .deep-section h2 { font-size: 15px; font-weight: 600; color: #412402;
                     margin-bottom: 14px; display: flex; align-items: center; gap: 8px; }
  .deep-cards { display: flex; gap: 16px; flex-wrap: wrap; }
  .deep-card { background: white; border: 1px solid #d3d1c7; border-radius: 10px;
               overflow: hidden; width: 240px; transition: transform 0.2s, box-shadow 0.2s; }
  .deep-card:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(0,0,0,0.08); }
  .deep-card-header { background: #412402; padding: 12px 14px; }
  .deep-card-header .ticker { font-size: 13px; font-weight: 700; color: #faeeda; }
  .deep-card-header .name   { font-size: 11px; color: #c9a96e; margin-top: 2px;
                               white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .deep-card-body { padding: 12px 14px; }
  .deep-metrics { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-bottom: 10px; }
  .deep-metric { font-size: 11px; }
  .deep-metric .label { color: #888780; }
  .deep-metric .value { font-weight: 600; color: #2c2c2a; }
  .deep-metric .value.green { color: #04342c; }
  .deep-metric .value.amber { color: #412402; }
  .deep-metric .value.red   { color: #501313; }
  .deep-conviction { display: inline-block; padding: 2px 10px; border-radius: 10px;
                     font-size: 11px; font-weight: 600; margin-bottom: 10px; }
  .dc-STRONG-BUY, .dc-BUY  { background: #e1f5ee; color: #04342c; }
  .dc-WATCH                 { background: #faeeda; color: #412402; }
  .dc-AVOID                 { background: #fcebeb; color: #501313; }
  .deep-btn { display: block; text-align: center; padding: 7px; background: #412402;
              color: white; border-radius: 6px; font-size: 12px; text-decoration: none;
              transition: background 0.2s; }
  .deep-btn:hover { background: #633806; }

  footer { text-align: center; padding: 32px; color: #888780; font-size: 12px;
           border-top: 1px solid #d3d1c7; margin-top: 20px; }
</style>
</head>
<body>

<header>
  <h1>🧪 Barren Wuffett Capital Research</h1>
  <p>Autonomous dividend intelligence · Oslo Stock Exchange</p>
</header>
<nav>
  <a href="/">Global</a>
  <a href="/norway" class="active">🇳🇴 Norway</a>
</nav>

<div class="page-body">

  {% if deep_analyses %}
  <div class="deep-section">
    <h2>🔬 Deep Analysis Reports
      <span style="font-size:12px;font-weight:400;color:#888780;">
        — full 5-model valuation · fritaksmetoden tax profiles · annual report intelligence
      </span>
    </h2>
    <div class="deep-cards">
    {% for d in deep_analyses %}
      <div class="deep-card">
        <div class="deep-card-header">
          <div class="ticker">{{ d.ticker.replace('.OL','') }}</div>
          <div class="name">{{ d.name }}</div>
        </div>
        <div class="deep-card-body">
          <div class="deep-conviction dc-{{ d.conviction.replace(' ','-') }}">
            {{ d.conviction }}
          </div>
          <div class="deep-metrics">
            <div class="deep-metric">
              <div class="label">Deep Score</div>
              <div class="value amber">{{ d.deep_score }}/100</div>
            </div>
            <div class="deep-metric">
              <div class="label">Current Yield</div>
              <div class="value green">{{ d.yield_pct }}%</div>
            </div>
            <div class="deep-metric">
              <div class="label">Fair Value Mid</div>
              <div class="value">{{ d.fv_mid }} NOK</div>
            </div>
            <div class="deep-metric">
              <div class="label">Margin of Safety</div>
              <div class="value {% if d.mos and d.mos > 10 %}green{% elif d.mos and d.mos < 0 %}red{% else %}amber{% endif %}">
                {{ d.mos_str }}
              </div>
            </div>
            <div class="deep-metric">
              <div class="label">5yr APY</div>
              <div class="value green">{{ d.yield_5y }}%</div>
            </div>
            <div class="deep-metric">
              <div class="label">Policy Clarity</div>
              <div class="value">{{ d.policy_clarity }}/10</div>
            </div>
          </div>
          <a href="/norway/deep/{{ d.ticker }}" class="deep-btn" target="_blank">
            📄 Open Deep Certificate
          </a>
        </div>
      </div>
    {% endfor %}
    </div>
  </div>
  {% endif %}

  <div class="intro">
    <h2>🇳🇴 Oslo Børs — Fritaksmetoden Qualifying Stocks</h2>
    <p>
      All stocks below are incorporated in Norway or the EEA, listed on Oslo Stock Exchange,
      and qualify under <strong>fritaksmetoden</strong> for Norwegian AS companies.
      Dividends and capital gains are <span class="highlight">~97 % tax-free</span>
      (only 3 % included in taxable income → effective rate ~0.66 % at 22 % corporate tax).
      Foreign-incorporated companies (Bermuda, Cayman, etc.) are excluded even if traded on Oslo Børs.
    </p>
  </div>

  <div class="summary-row">
    <div class="summary-stat">
      <div class="num">{{ total }}</div>
      <div class="label">Stocks</div>
    </div>
    <div class="summary-stat">
      <div class="num">{{ paying }}</div>
      <div class="label">Paying dividends</div>
    </div>
    <div class="summary-stat">
      <div class="num">{{ avg_yield }}%</div>
      <div class="label">Avg yield</div>
    </div>
    <div class="summary-stat">
      <div class="num">{{ avg_pe }}x</div>
      <div class="label">Avg P/E</div>
    </div>
  </div>

  <div class="controls">
    <input class="filter-input" type="text" id="searchInput"
           placeholder="Search company or ticker..." onkeyup="applyFilters()">
    <select class="sector-select" id="sectorFilter" onchange="applyFilters()">
      <option value="">All sectors</option>
      {% for s in sectors %}
      <option value="{{ s }}">{{ s }}</option>
      {% endfor %}
    </select>
    <span class="last-updated">Updated: {{ last_updated }}</span>
    <a href="/norway/refresh" class="refresh-btn">↻ Refresh data</a>
  </div>

  <table id="norwayTable">
    <thead>
      <tr>
        <th onclick="sortTable(0)">Ticker <span class="sort-arrow">↕</span></th>
        <th onclick="sortTable(1)">Company <span class="sort-arrow">↕</span></th>
        <th onclick="sortTable(2)">Sector <span class="sort-arrow">↕</span></th>
        <th onclick="sortTable(3)" title="Current dividend yield">Yield % <span class="sort-arrow">↕</span></th>
        <th onclick="sortTable(4)" title="Trailing 12-month Price/Earnings">P/E <span class="sort-arrow">↕</span></th>
        <th onclick="sortTable(5)" title="Price to Book Value">P/B <span class="sort-arrow">↕</span></th>
        <th onclick="sortTable(6)" title="Total Debt / Equity (%)">D/E % <span class="sort-arrow">↕</span></th>
        <th onclick="sortTable(7)" title="Return on Equity">ROE % <span class="sort-arrow">↕</span></th>
        <th title="Fritaksmetoden">Fritaks</th>
      </tr>
    </thead>
    <tbody id="tableBody">
    {% for r in stocks %}
    <tr data-sector="{{ r.sector }}" data-name="{{ r.name|lower }} {{ r.ticker|lower }}">
      <td class="ticker-col">{{ r.ticker.replace('.OL','') }}</td>
      <td class="name-col">{{ r.name }}</td>
      <td><span class="sector-badge">{{ r.sector }}</span></td>

      <td class="metric {% if r.dividend_yield and r.dividend_yield >= 5 %}yield-high{% elif r.dividend_yield and r.dividend_yield >= 2 %}yield-mid{% else %}yield-low{% endif %}"
          data-val="{{ r.dividend_yield or 0 }}">
        {% if r.dividend_yield %}{{ "%.1f"|format(r.dividend_yield) }}%{% else %}<span class="na">—</span>{% endif %}
      </td>

      <td class="metric {% if r.pe_ratio and r.pe_ratio < 15 %}good{% elif r.pe_ratio and r.pe_ratio > 25 %}warn{% endif %}"
          data-val="{{ r.pe_ratio or 999 }}">
        {% if r.pe_ratio %}{{ "%.1f"|format(r.pe_ratio) }}x{% else %}<span class="na">—</span>{% endif %}
      </td>

      <td class="metric {% if r.pb_ratio and r.pb_ratio < 1.5 %}good{% elif r.pb_ratio and r.pb_ratio > 4 %}warn{% endif %}"
          data-val="{{ r.pb_ratio or 999 }}">
        {% if r.pb_ratio %}{{ "%.2f"|format(r.pb_ratio) }}{% else %}<span class="na">—</span>{% endif %}
      </td>

      <td class="metric {% if r.debt_to_equity is not none and r.debt_to_equity < 50 %}good{% elif r.debt_to_equity is not none and r.debt_to_equity > 150 %}warn{% endif %}"
          data-val="{{ r.debt_to_equity if r.debt_to_equity is not none else 999 }}">
        {% if r.debt_to_equity is not none %}{{ "%.0f"|format(r.debt_to_equity) }}{% else %}<span class="na">—</span>{% endif %}
      </td>

      <td class="metric {% if r.roe and r.roe >= 15 %}good{% elif r.roe and r.roe < 5 %}warn{% endif %}"
          data-val="{{ r.roe or 0 }}">
        {% if r.roe %}{{ "%.1f"|format(r.roe) }}%{% else %}<span class="na">—</span>{% endif %}
      </td>

      <td><span class="fritaks-badge">✓ EEA</span></td>
    </tr>
    {% endfor %}
    </tbody>
  </table>

  <p style="font-size:11px;color:#888780;margin-top:12px;">
    <strong>Metrics explained:</strong>
    Yield = current dividend yield · P/E = price/earnings (lower = cheaper) ·
    P/B = price/book (below 1.5 = value territory) ·
    D/E = debt-to-equity % (lower = stronger balance sheet) ·
    ROE = return on equity (above 15 % = excellent).
    Green = favourable · Amber = elevated · Data from Yahoo Finance, refreshed every 6 h.
  </p>

</div>

<footer>
  © 2026 Barren Wuffett Capital Research · Powered by Claude AI · Not financial advice
</footer>

<script>
let sortDir = {};

function sortTable(col) {
  const tbody = document.getElementById('tableBody');
  const rows  = Array.from(tbody.querySelectorAll('tr:not([style*="none"])'));
  const asc   = !sortDir[col];
  sortDir     = {};
  sortDir[col] = asc;

  rows.sort((a, b) => {
    let aVal = a.cells[col].getAttribute('data-val') ?? a.cells[col].textContent.trim();
    let bVal = b.cells[col].getAttribute('data-val') ?? b.cells[col].textContent.trim();
    const aNum = parseFloat(aVal), bNum = parseFloat(bVal);
    if (!isNaN(aNum) && !isNaN(bNum)) return asc ? aNum - bNum : bNum - aNum;
    return asc ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
  });

  rows.forEach(r => tbody.appendChild(r));

  document.querySelectorAll('thead th').forEach((th, i) => {
    th.classList.toggle('sorted', i === col);
    const arrow = th.querySelector('.sort-arrow');
    if (arrow) arrow.textContent = i === col ? (asc ? '↑' : '↓') : '↕';
  });
}

function applyFilters() {
  const search = document.getElementById('searchInput').value.toLowerCase();
  const sector = document.getElementById('sectorFilter').value;
  document.querySelectorAll('#tableBody tr').forEach(row => {
    const matchSearch = !search || row.dataset.name.includes(search);
    const matchSector = !sector || row.dataset.sector === sector;
    row.style.display = matchSearch && matchSector ? '' : 'none';
  });
}
</script>
</body>
</html>
"""

@app.route("/")
def index():
    results  = load_results()
    if not results:
        return ("<html><body style='font-family:sans-serif;text-align:center;padding:80px;"
                "background:#faeeda'><h2>🧪 Barren Wuffett is warming up...</h2>"
                "<p style='color:#633806;margin-top:16px'>Running the first scan. "
                "Check back in a few minutes.</p>"
                "<script>setTimeout(()=>location.reload(),30000)</script></body></html>"), 202
    buys     = sum(1 for r in results if r.get("conviction_rating") in ("BUY", "STRONG BUY"))
    avg_yield = round(sum(r.get("dividend_yield", 0) for r in results) / max(len(results), 1), 2)
    avg_5yr   = round(sum(r.get("projected_yield_5y", 0) for r in results) / max(len(results), 1), 2)

    import os
    mtime = os.path.getmtime(RESULTS) if os.path.exists(RESULTS) else 0
    from datetime import datetime
    last_scan = datetime.fromtimestamp(mtime).strftime("%d %b %Y %H:%M") if mtime else "Never"

    return render_template_string(HTML,
        results   = results,
        total     = len(results),
        buys      = buys,
        avg_yield = avg_yield,
        avg_5yr   = avg_5yr,
        last_scan = last_scan,
        conv_emoji = CONVICTION_EMOJI,
    )

@app.route("/certificate/<ticker>")
def certificate(ticker):
    safe = ticker.replace(".", "_").replace("/", "-")
    for fname in os.listdir(CERTS):
        if safe in fname and fname.endswith(".pdf"):
            return send_file(os.path.join(CERTS, fname),
                           as_attachment=False,
                           mimetype="application/pdf")
    abort(404)

def load_deep_analyses():
    """Scan certificates/deep/ for available deep analysis results."""
    if not os.path.isdir(DEEP_DIR):
        return []
    analyses = []
    for fname in sorted(os.listdir(DEEP_DIR)):
        if not fname.endswith(".pdf"):
            continue
        # Derive ticker from filename: BW_DEEP_DNB_OL_... → DNB.OL
        parts = fname.replace("BW_DEEP_", "").split("_")
        if len(parts) >= 2:
            raw = parts[0] + "_" + parts[1]   # e.g. DNB_OL
            ticker = raw.replace("_", ".", 1)  # DNB.OL
        else:
            continue

        # Try to load the JSON result for metrics
        json_path = os.path.join(BASE, "reports", f"{ticker.replace('.','_')}_deep_result.json")
        meta = {"ticker": ticker, "name": ticker, "conviction": "—",
                "deep_score": "—", "yield_pct": "—", "fv_mid": "—",
                "mos": None, "mos_str": "—", "yield_5y": "—", "policy_clarity": "—"}
        if os.path.exists(json_path):
            try:
                with open(json_path) as f:
                    d = json.load(f)
                scores  = d.get("scores", {})
                val     = d.get("valuation", {})
                annual  = d.get("annual", {})
                mos     = val.get("margin_of_safety_pct")
                meta.update({
                    "name":           d.get("name", ticker),
                    "conviction":     scores.get("conviction_rating", "—"),
                    "deep_score":     scores.get("barren_deep_score", "—"),
                    "yield_pct":      round(d.get("dividend_yield", 0), 2),
                    "fv_mid":         val.get("fv_mid", "—"),
                    "mos":            mos,
                    "mos_str":        f"{mos:+.1f}%" if mos is not None else "—",
                    "yield_5y":       scores.get("projected_yield_5y", "—"),
                    "policy_clarity": annual.get("dividend_policy_clarity_score", "—"),
                })
            except Exception:
                pass
        analyses.append(meta)
    return analyses


@app.route("/norway")
def norway():
    from norway_data import fetch_oslo_data, CACHE
    stocks = fetch_oslo_data()

    paying   = sum(1 for s in stocks if s.get("dividend_yield"))
    yields   = [s["dividend_yield"] for s in stocks if s.get("dividend_yield")]
    pes      = [s["pe_ratio"]       for s in stocks if s.get("pe_ratio")]
    avg_yield = round(sum(yields) / len(yields), 1) if yields else 0
    avg_pe    = round(sum(pes) / len(pes), 1)       if pes    else 0

    sectors = sorted(set(s["sector"] for s in stocks if s.get("sector")))

    import os as _os
    from datetime import datetime
    mtime = _os.path.getmtime(CACHE) if _os.path.exists(CACHE) else 0
    last_updated = datetime.fromtimestamp(mtime).strftime("%d %b %Y %H:%M") if mtime else "Never"

    return render_template_string(NORWAY_HTML,
        stocks         = stocks,
        total          = len(stocks),
        paying         = paying,
        avg_yield      = avg_yield,
        avg_pe         = avg_pe,
        sectors        = sectors,
        last_updated   = last_updated,
        deep_analyses  = load_deep_analyses(),
    )


@app.route("/norway/deep/<ticker>")
def norway_deep_cert(ticker):
    """Serve a deep analysis PDF certificate."""
    safe = ticker.replace(".", "_").replace("/", "-")
    if os.path.isdir(DEEP_DIR):
        for fname in os.listdir(DEEP_DIR):
            if fname.startswith(f"BW_DEEP_{safe}") and fname.endswith(".pdf"):
                return send_file(os.path.join(DEEP_DIR, fname),
                                 as_attachment=False, mimetype="application/pdf")
    abort(404)


@app.route("/norway/refresh")
def norway_refresh():
    """Force-refresh Oslo data and redirect back."""
    from flask import redirect
    from norway_data import fetch_oslo_data
    fetch_oslo_data(force=True)
    return redirect("/norway")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("🧪 Barren Wuffett Dashboard starting...")
    print(f"   Open http://localhost:{port} in your browser")
    app.run(debug=False, host="0.0.0.0", port=port)