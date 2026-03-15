import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")

def send_message(text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id":    CHAT_ID,
        "text":       text,
        "parse_mode": "HTML",
    }
    r = requests.post(url, json=payload)
    return r.json()

def format_certificate_message(r: dict) -> str:
    conviction_emoji = {
        "STRONG BUY": "🟢",
        "BUY":        "🟡",
        "WATCH":      "🟠",
        "AVOID":      "🔴",
    }.get(r.get("conviction_rating", "WATCH"), "⚪")

    return f"""🧪 <b>BARREN WUFFETT RESEARCH ALERT</b>

<b>{r.get('name', r['ticker'])}</b> ({r['ticker']})
{conviction_emoji} {r.get('conviction_rating', '—')} · Score: {r.get('barren_score', 0)}/100
📍 {r.get('sector', '—')} · {r.get('country', '—')}

💰 <b>Current yield:</b> {r.get('dividend_yield', 0):.2f}%
📈 <b>5yr div CAGR:</b> {r.get('div_cagr_5y', 0):.1f}%
📊 <b>Payout ratio:</b> {r.get('payout_ratio', 0):.0f}%

⏱ <b>Projected APY</b>
  1yr  → {r.get('projected_yield_1y',  0):.1f}%
  3yr  → {r.get('projected_yield_3y',  0):.1f}%
  5yr  → {r.get('projected_yield_5y',  0):.1f}% ⭐
  10yr → {r.get('projected_yield_10y', 0):.1f}%
  20yr → {r.get('projected_yield_20y', 0):.1f}%

🧠 <b>Thesis</b>
<i>{r.get('thesis', '')}</i>

⚠️ <b>Risk</b>
{r.get('key_risk', '')}

🔬 <i>"{r.get('barren_quip', '')}"</i>

━━━━━━━━━━━━━━━━━━━━
<i>Barren Wuffett Capital Research · Not financial advice</i>"""

def broadcast_top_picks(json_file="scan_results.json", min_score=60):
    with open(json_file) as f:
        results = json.load(f)

    # Filter to BUY and above only
    picks = [r for r in results if r.get("barren_score", 0) >= min_score]

    if not picks:
        send_message("🧪 Barren here — scanned the Nordic markets today and nothing met my exacting dividend standards. The search continues, my friends!")
        return

    # Send intro message
    send_message(f"""🧪 <b>BARREN WUFFETT — NORDIC SCAN COMPLETE</b>

My magnificent dividend-sniffing algorithms have completed their Nordic patrol!

Found <b>{len(picks)} worthy picks</b> out of {len(results)} stocks scanned.
Sending full certificates now... 🔬""")

    # Send one message per pick
    import time
    for r in picks:
        msg = format_certificate_message(r)
        result = send_message(msg)
        if result.get("ok"):
            print(f"✅ Sent: {r.get('name', r['ticker'])}")
        else:
            print(f"❌ Failed: {result}")
        time.sleep(1)  # be polite to Telegram API

    # Send closing quip
    send_message("""🧪 That's today's dividend intelligence dispatch!

Remember friends — we don't chase yield, we <b>compound</b> it. 
The tortoise always beats the hare, especially when the tortoise pays dividends! 🐢💰

<i>— Barren Wuffett</i>""")

if __name__ == "__main__":
    print("Sending Barren's picks to Telegram...")
    broadcast_top_picks()