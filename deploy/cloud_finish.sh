#!/bin/bash
# Cloud build, step 2 (after the TradingView pulls): harvest TV results from this session, build, diff vs prior run.
set -e; cd "$(dirname "$0")/.."
python3 -m engine.tv ingest
python3 build.py
python3 -m engine.factdiff
