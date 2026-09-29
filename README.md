# Macro Terminal engine

Bloomberg-style multi-tab macro terminal. Python engine → one self-contained HTML page. Runs entirely in the cloud as a Claude scheduled task
(TradingView data only reaches us through the TradingView connector inside a Claude session).

## Daily run (what the scheduled task does)
1. Restore code from the artifact's `engine_bundle.json`; save the artifact's published `facts.json` as `out/facts_prev.json` (prior run, for change detection).
2. `deploy/cloud_run.sh` → FRED, Sharadar ETFs, Cboe, Ken French, FRED release calendar; writes `out/tv_plan.json`.
   Keys come from env vars NASDAQ_API_KEY / FRED_API_KEY (cloud environment settings). No `.env` is written in the cloud.
3. Pull every symbol in `out/tv_plan.json` with the TradingView get_ohlcv tool (interval 1D, count as listed). Large results spill to tool-result files; that is how they are harvested.
4. `deploy/cloud_finish.sh` → `engine.tv ingest`, `build.py` → `out/artifact.html` + `out/engine_bundle.json` + `out/facts.json`,
   then `engine.factdiff` → `out/facts_diff.json` (state/thesis/call/level changes vs prior run).
5. Republish the artifact (same URL) with `engine_bundle.json` and `facts.json` as supporting files.

## Sources
TradingView: global 2Y/10Y/30Y yields, FX spot + DXY, commodity futures, MOVE, COR3M, S&P breadth (S5TW/S5FI/S5TH), ZQ + SR3 strips, UB/ZT/ZN.
FRED: TIPS real yields, breakevens, EFFR/SOFR/IORB, OAS, Fed balance sheet/RRP/TGA, NFCI, VIX/OVX/GVZ, release dates (CPI, payrolls).
Sharadar: ETF total-return prices (sectors, factors, cross-asset). Cboe: VIX9D/VIX3M/VVIX/SKEW. Ken French: 1926– cap vs equal weight.

## Tabs
F0 BRIEF · F1 CYCLE · F2 THEME · F3 PRICED/POLICY · F4 GLOBAL YIELDS · F5 CURVE · F6 INFLATION · F7 GROWTH · F8 EQUITY & BREADTH · F9 FX ·
F10 CREDIT & LIQUIDITY · F11 VOL & CORR · F12 PCA/TAPE · F13 THESIS

Retired: CFTC positioning, CDS, IBKR module, constituent-level breadth, FRED H.10 FX, OECD monthly yields, release-data GIP classifier.
Edit theses in engine/thesis.py.
