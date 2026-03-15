import schedule
import time
import subprocess
import sys
import os
from datetime import datetime
from dotenv import load_dotenv
from barren_killswitch import is_killed

load_dotenv()

def run_barren():
    if is_killed():
        print("🛑 Kill switch active — skipping scan.")
        return

    print(f"\n{'='*60}")
    print(f"  BARREN WUFFETT — Daily Scan Starting")
    print(f"  {datetime.now().strftime('%A %d %B %Y %H:%M')}")
    print(f"{'='*60}")

    python = sys.executable
    base   = os.path.expanduser("~/barren-wuffet")

    # Step 1 — Scan and score
    print("\n📡 Step 1: Scanning Nordic markets...")
    result = subprocess.run(
        [python, f"{base}/barren_scorer.py"],
        capture_output=True, text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"❌ Scorer failed: {result.stderr}")
        return

    # Step 2 — Generate certificates
    print("\n📄 Step 2: Generating certificates...")
    result = subprocess.run(
        [python, f"{base}/barren_certificate.py"],
        capture_output=True, text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"❌ Certificate generator failed: {result.stderr}")
        return

    # Step 3 — Broadcast to Telegram
    print("\n📢 Step 3: Broadcasting to Telegram...")
    result = subprocess.run(
        [python, f"{base}/barren_telegram.py"],
        capture_output=True, text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"❌ Telegram broadcast failed: {result.stderr}")
        return

    print(f"\n✅ Barren's daily run complete at {datetime.now().strftime('%H:%M')}")

# ── Schedule ──────────────────────────────────────────────────────────────────
schedule.every().day.at("07:30").do(run_barren)

print("🧪 Barren Wuffett Scheduler is running...")
print("   Daily scan scheduled for 07:30")
print("   Press Ctrl+C to stop\n")

# Run immediately once on startup
print("🔄 Running initial scan now...")
run_barren()

# Keep running on schedule
while True:
    schedule.run_pending()
    time.sleep(60)