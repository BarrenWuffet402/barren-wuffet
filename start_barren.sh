#!/bin/bash

# Barren Wuffett — Master Startup Script
# Starts all services on boot

BASE="/Users/johanlo/barren-wuffet"
PYTHON="$BASE/venv/bin/python3"
LOG="$BASE/logs"

mkdir -p "$LOG"

echo "$(date) — Barren Wuffett starting up..." >> "$LOG/barren.log"

# Start Ollama server
/opt/homebrew/bin/ollama serve >> "$LOG/ollama.log" 2>&1 &
sleep 5

# Start Flask dashboard
$PYTHON "$BASE/barren_dashboard.py" >> "$LOG/dashboard.log" 2>&1 &
sleep 3

# Start scheduler (runs daily scan + Telegram)
$PYTHON "$BASE/barren_scheduler.py" >> "$LOG/scheduler.log" 2>&1 &

echo "$(date) — All Barren services started." >> "$LOG/barren.log"