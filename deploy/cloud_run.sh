#!/bin/bash
# Cloud build, step 1 (before the TradingView pulls): install deps + refresh non-TV sources.
# Keys come ONLY from environment variables (NASDAQ_API_KEY, FRED_API_KEY). In the cloud no .env file is
# written or needed; run_refresh.sh still reads a local .env if one exists (for runs on your own machine).
set -e; cd "$(dirname "$0")/.."
missing=""
if [ ! -f .env ]; then
  [ -z "$NASDAQ_API_KEY" ] && missing="$missing NASDAQ_API_KEY"
  [ -z "$FRED_API_KEY" ] && missing="$missing FRED_API_KEY"
fi
if [ -n "$missing" ]; then echo "ERROR: missing env vars:$missing"; exit 2; fi
pip install --break-system-packages -q -r requirements.txt 2>/dev/null || true
mkdir -p data out
[ -f out/facts_prev.json ] && echo "prior facts: out/facts_prev.json found" || echo "WARN: no out/facts_prev.json — change detection will be skipped"
./run_refresh.sh
python3 -m engine.tv plan > out/tv_plan.json
echo "TV plan: $(python3 -c "import json;print(len(json.load(open('out/tv_plan.json'))))") symbols → out/tv_plan.json"
python3 -m engine.tv calendar > out/tv_calendar.json; echo "TV calendar params → out/tv_calendar.json"
