#!/usr/bin/env bash
# Launch (or resume) the M3 campaign. Run inside tmux on the droplet:
#   tmux new -d -s m3 'bash ~/chronogauntlet/deploy/launch_m3.sh [concurrency] [budget]'
# Resumes from ALL prior raw_*.jsonl (successful cells skipped, failed cells retried).
set -u
cd "$(dirname "$0")/.."
CONC="${1:-20}"
BUDGET="${2:-150}"
TZ=UTC ./.venv/bin/python -m generation.run_campaign \
  --samples 5 --greedy --languages python,js \
  --concurrency "$CONC" --budget-usd "$BUDGET" \
  --resume 'results/campaign/raw_*.jsonl' \
  > "results/campaign/run.out" 2>&1
