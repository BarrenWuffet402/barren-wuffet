import os
import json
from flask import Flask, render_template_string, send_file, abort
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

BASE    = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(BASE, "scan_results.json")
CERTS   = os.path.join(BASE, "certificates")

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
</style>
</head>
<body>

<header>
  <h1>🧪 Barren Wuffett Capital Research</h1>
  <p>Autonomous dividend intelligence · Global markets</p>
  <p class="tagline">"The dividends, my friend, are blowin' in the wind!"</p>
</header>

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

@app.route("/")
def index():
    results  = load_results()
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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("🧪 Barren Wuffett Dashboard starting...")
    print(f"   Open http://localhost:{port} in your browser")
    app.run(debug=False, host="0.0.0.0", port=port)