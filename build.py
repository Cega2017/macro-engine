"""Build the terminal from cached data: python3 build.py  (refresh first with ./run_refresh.sh)"""
import os, json, time, traceback, numpy as np, pandas as pd
from engine import config as C
from engine.ctx import Ctx
from engine import tabs_rates as R, tabs_macro as M, tabs_mkt as T, brief as B, render, thesis as TH, explorer as EX

def main():
    t0 = time.time(); X = Ctx(); tabs = []
    order = [M.tab_cycle, M.tab_theme, R.tab_policy, R.tab_global, R.tab_curve, M.tab_inflation, M.tab_growth, T.tab_equity, T.tab_fx,
             T.tab_credit, T.tab_vol, T.tab_pca, TH.tab_thesis, EX.tab_explorer]
    for fn in order:
        try: tabs.append(fn(X)); print(f"{fn.__name__:18s} ok {time.time()-t0:5.1f}s", flush=True)
        except Exception as e:
            traceback.print_exc(); tabs.append(dict(key=fn.__name__, title=fn.__name__.replace("tab_", "").upper(), read=[f"<span class='warn'>BUILD ERROR</span> {e}"], cards=[]))
    tabs.insert(0, B.tab_brief(X, tabs))
    log = json.load(open(os.path.join(C.DATA, "refresh_log.json"))) if os.path.exists(os.path.join(C.DATA, "refresh_log.json")) else {}
    lg = " ".join(f"{k}:{v if v=='ok' else 'FAIL'}" for k, v in log.items() if k != "ts")
    try:
        tvb = X.tvbars.groupby("symbol").date.max(); lg += f" tv:{len(tvb)} symbols to {tvb.max():%m/%d}"
    except Exception: lg += " tv:none"
    try:
        lag = np.busday_count(X.px.index[-1].date(), X.tv.index[-1].date())
        if lag > 0: lg += f" <span class='warn'>ETF data {lag}d behind TradingView ({X.px.index[-1]:%m/%d})</span>"
    except Exception: pass
    out = os.path.join(C.OUT, "terminal.html")
    open(out, "w").write(render.html(tabs, X.asof, lg))
    open(os.path.join(C.OUT, "artifact.html"), "w").write(render.html(tabs, X.asof, lg, fragment=True))
    bundle = {}
    for root, _, files in os.walk(C.ROOT):
        if any(p in root for p in ("/data", "/out", "__pycache__", "/.git")): continue
        for fn in files:
            if fn == ".env" or not fn.endswith((".py", ".sh", ".md", ".txt", ".example", ".service", ".timer", ".plist")): continue
            p = os.path.join(root, fn); bundle[os.path.relpath(p, C.ROOT)] = open(p).read()
    json.dump(bundle, open(os.path.join(C.OUT, "engine_bundle.json"), "w"))
    json.dump({k: (v if isinstance(v, (int, float, str, list)) else str(v)) for k, v in X.facts.items()}, open(os.path.join(C.OUT, "facts.json"), "w"), default=str, indent=1)
    print("wrote", out, f"{os.path.getsize(out)/1e6:.1f}MB", f"{time.time()-t0:.1f}s")

if __name__ == "__main__": main()
