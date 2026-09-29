import numpy as np, pandas as pd
from . import kit as K

MASTER = [("SPY", "px", "SPY", "pct"), ("QQQ", "px", "QQQ", "pct"), ("IWM", "px", "IWM", "pct"), ("RSP", "px", "RSP", "pct"), ("EFA", "px", "EFA", "pct"),
          ("EEM", "px", "EEM", "pct"), ("UST 2Y", "tv", "TVC:US02Y", "bp"), ("UST 10Y", "tv", "TVC:US10Y", "bp"), ("UST 30Y", "tv", "TVC:US30Y", "bp"),
          ("2s10s (bp)", "calc", "s210", "bpl"), ("5Y breakeven", "fred", "T5YIE", "bp"), ("10Y real", "fred", "DFII10", "bp"), ("HY OAS (bp)", "fredbp", "BAMLH0A0HYM2", "bpl"),
          ("VIX", "cboe", "VIX", "lvl"), ("TLT", "px", "TLT", "pct"),
          ("DXY", "tv", "TVC:DXY", "pct"), ("EURUSD", "tv", "FX_IDC:EURUSD", "pct"), ("USDJPY", "tv", "FX_IDC:USDJPY", "pct"), ("WTI", "tv", "NYMEX:CL1!", "pct"),
          ("Gold", "tv", "COMEX:GC1!", "pct"), ("Copper", "tv", "COMEX:HG1!", "pct"), ("MOVE", "tv", "TVC:MOVE", "lvl"), ("DE 10Y", "tv", "TVC:DE10Y", "bp"),
          ("UK 10Y", "tv", "TVC:GB10Y", "bp"), ("JP 10Y", "tv", "TVC:JP10Y", "bp"), ("IBIT (BTC)", "px", "IBIT", "pct")]

def movers_html(X, n=8):
    """Biggest 5-day movers across the ETF + stock universe, scaled by each name's own vol, with the part SPY's beta doesn't explain."""
    from . import data
    tr = X.tr.copy()
    try: tr = tr.join(data.load("stk_tr"), how="left")
    except Exception: pass
    r = tr.pct_change().iloc[-253:]; spy = r["SPY"]
    rows = []
    for c in r.columns:
        x = r[c].dropna()
        if len(x) < 130 or c in ("SPY", "BIL", "SHV", "BOXX"): continue
        b = x.iloc[-126:].cov(spy.reindex(x.index).iloc[-126:]) / spy.iloc[-126:].var()
        e = (x - b * spy.reindex(x.index)).dropna()
        r5 = (1 + x.iloc[-5:]).prod() - 1; s5 = (1 + spy.iloc[-5:]).prod() - 1; res5 = r5 - b * s5
        v = x.iloc[-68:-5].std() * np.sqrt(5); ve = e.iloc[-68:-5].std() * np.sqrt(5)
        if not v or v < 0.004: continue            # skip cash-like names: tiny vol makes z meaningless
        rows.append((c, x.iloc[-1] * 100, r5 * 100, r5 / v if v else np.nan, b, res5 * 100, res5 / ve if ve else np.nan))
    df = pd.DataFrame(rows, columns=["n", "d1", "d5", "z", "beta", "res", "rz"]).dropna().sort_values("z")
    pick = pd.concat([df.tail(n).iloc[::-1], df.head(n)])
    cls = lambda v: "g" if v > 0 else "r"
    tr_ = "".join(f"<tr><td class='nm'>{r.n}</td><td class='n {cls(r.d1)}'>{r.d1:+.1f}%</td><td class='n {cls(r.d5)}'>{r.d5:+.1f}%</td>"
                  f"<td class='n {'hz' if abs(r.z) >= 2 else ''}'>{r.z:+.1f}</td><td class='n'>{r.beta:.2f}</td><td class='n {cls(r.res)}'>{r.res:+.1f}%</td>"
                  f"<td class='n {'hz' if abs(r.rz) >= 2 else ''}'>{r.rz:+.1f}</td><td class='txt'>{'off-SPY driver' if abs(r.rz) >= 2 else ''}</td></tr>" for r in pick.itertuples())
    return (f"<div class='tbl'><div class='tt'>MOVERS · 5 days, top {n} / bottom {n} of {len(df)} ETFs + stocks, ranked by move ÷ own volatility</div><table><tr><th>Name</th><th>1D</th><th>5D</th>"
            f"<th>5D z</th><th>β to SPY</th><th>5D ex-SPY</th><th>ex-SPY z</th><th style='text-align:left'></th></tr>{tr_}</table>"
            f"<div class='asof'>z = 5-day return ÷ the name's normal 5-day volatility (prior 3 months). Ex-SPY = return left after removing SPY × beta (6-month beta); "
            f"'off-SPY driver' = that leftover is 2+ standard deviations: something other than the stock market moved it (rates for bonds, company news for stocks).</div></div>")

def _safe_movers(X):
    try: return movers_html(X)
    except Exception as e: return f"<div class='warn'>movers failed: {e}</div>"

def master_rows(X):
    rows = []
    for name, src, key, kind in MASTER:
        if src == "px": s = X.px[key]
        elif src == "fred": s = X.f(key)
        elif src == "fredbp": s = X.f(key) * 100
        elif src == "cboe": s = X.cboe[key].dropna()
        elif src == "tv": s = X.t(key)
        else: s = (X.y("US", "10Y") - X.y("US", "02Y")).dropna() * 100
        stale = 3 if src != "fred" else 4
        rows.append(K.row_stats(name, s, kind, stale_days=stale if src != "fredbp" else 4))
    return rows

MOVES = {"prce": "breakevens, front end, USD", "lbr": "2Y, USD, cyclicals", "mny": "policy path, FX", "gdp": "growth trades, curve", "bsnss": "cyclicals, copper, curve",
         "cnsm": "consumer stocks, 2Y", "hse": "homebuilders, mortgages", "trd": "FX", "gov": "long end"}
def calendar_html(X):
    import os, json
    from . import config as C
    p = os.path.join(C.DATA, "calendar.json")
    if not os.path.exists(p): return "<div class='alerts'><div class='tt'>RED-FOLDER CALENDAR</div>No calendar pulled yet.</div>"
    ev = pd.DataFrame(json.load(open(p))); ev["t"] = pd.to_datetime(ev.date, utc=True).dt.tz_convert("America/New_York")
    now = pd.Timestamp.now(tz="America/New_York")
    up = ev[(ev.t >= now - pd.Timedelta(hours=12)) & (ev.t <= now + pd.Timedelta(days=14))].sort_values("t")
    def fmt(v, e):
        if v is None or (isinstance(v, float) and np.isnan(v)): return "–"
        sc = e.get("scale"); sc = sc if isinstance(sc, str) else ""
        return f"{v:g}{sc}{'%' if e.get('unit') == '%' else ''}"
    rows = ""
    for _, e in up.iterrows():
        us = e.country == "US"
        rows += (f"<tr><td class='nm'>{e.t:%a %m/%d %H:%M}</td><td class='{'w' if us else ''}' style='text-align:left'>{e.country}</td>"
                 f"<td style='text-align:left'>{'<b>' if us else ''}{e.title}{'</b>' if us else ''} {e.period or ''}</td><td>{fmt(e.forecast, e)}</td><td>{fmt(e.previous, e)}</td>"
                 f"<td>{fmt(e.actual, e) if e.actual is not None else ''}</td><td class='txt'>{MOVES.get(e.category, '')}</td></tr>")
    return (f"<div class='tbl'><div class='tt'>RED-FOLDER CALENDAR · next 14 days, high importance (TradingView, times ET)</div><table><tr><th>When</th><th style='text-align:left'>Ctry</th>"
            f"<th style='text-align:left'>Event</th><th>Consensus</th><th>Prior</th><th>Actual</th><th>What it moves</th></tr>{rows}</table></div>")

def tab_brief(X, tabs):
    F = X.facts; rows = master_rows(X); al = K.alerts(rows)
    sgn = lambda v: "+" if v > 0 else "−"
    # mosaic scorecard: each line (signal, value text, vote +1 risk-on/growth, -1)
    votes = {
        "Growth": [("Tape growth composite", f"{F['g']:+.2f}", np.sign(F["g"])), ("Internals above 100d", f"{F['internals_up']}/10", 1 if F["internals_up"] >= 6 else -1 if F["internals_up"] <= 4 else 0),
                   ("HY OAS 1M", f"{F['hy_1m']:+.0f}bp", -np.sign(F["hy_1m"]) if abs(F["hy_1m"]) > 5 else 0), ("Breadth % > 200d", f"{F['a200']:.0f}%", 1 if F["a200"] > 60 else -1 if F["a200"] < 40 else 0)],
        "Inflation": [("Tape inflation composite", f"{F['i']:+.2f}", np.sign(F["i"])), ("5Y BE 1M", f"{F['be5_1m']:+.0f}bp", np.sign(F["be5_1m"]) if abs(F["be5_1m"]) > 5 else 0),
                      ("5y5y anchor", f"{F['f55']:.2f}%", 1 if F["f55"] > 2.6 else 0)],
        "Policy": [("Fed hikes priced (strip)", f"{F.get('fed_priced_bp', np.nan):+.0f}bp", 1 if F.get("fed_priced_bp", 0) > 25 else -1 if F.get("fed_priced_bp", 0) < -25 else 0),
                   ("Repricing 1W", f"{F.get('fed_priced_chg1w', np.nan):+.0f}bp", np.sign(F.get("fed_priced_chg1w", 0)) if abs(F.get("fed_priced_chg1w", 0)) > 3 else 0),
                   ("10Y 1M", f"{F['y10_1m']:+.0f}bp", np.sign(F["y10_1m"]) if abs(F["y10_1m"]) > 10 else 0)],
        "Risk": [("VIX", f"{F['vix']:.1f}", 1 if F["vix"] < 16 else -1 if F["vix"] > 22 else 0), ("VIX contango", f"{-F['vix_inv']:+.0f}%", -1 if F["vix_inv"] > 0 else 1),
                 ("Stock–bond corr", f"{F['sb_corr']:+.2f}", -1 if F["sb_corr"] > 0.1 else 1 if F["sb_corr"] < -0.1 else 0), ("MOVE", f"{F['move']:.0f}", -1 if F["move"] > 110 else 1 if F["move"] < 80 else 0)],
    }
    lean = {k: int(sum(v[2] for v in vs)) for k, vs in votes.items()}
    lab = {"Growth": ("expanding", "slowing"), "Inflation": ("heating", "cooling"), "Policy": ("hawkish repricing", "dovish repricing"), "Risk": ("risk-on", "risk-off")}
    mos = ""
    for k, vs in votes.items():
        cells = "".join(f"<tr><td class='nm'>{a}</td><td class='n w'>{b}</td><td class='{'g' if c>0 else 'r' if c<0 else ''}'>{'▲' if c>0 else '▼' if c<0 else '·'}</td></tr>" for a, b, c in vs)
        L = lean[k]; txt = lab[k][0] if L > 0 else lab[k][1] if L < 0 else "neutral"
        mos += f"<div class='mos'><div class='tt'>{k}: <span class='{'g' if L>0 else 'r' if L<0 else ''}'>{txt.upper()} ({L:+d})</span></div><table>{cells}</table></div>"
    # cross-asset confirmation of the growth read
    px = X.px; c63 = lambda t: X.tr[t].dropna().iloc[-1] / X.tr[t].dropna().iloc[-64] - 1
    t63 = lambda s: s.iloc[-1] / s.iloc[-64] - 1
    checks = [("Equities (SPY 3M)", c63("SPY")), ("Small caps vs SPX", c63("IWM") - c63("SPY")), ("Copper (HG 3M)", t63(X.t("COMEX:HG1!"))),
              ("Credit, rate-hedged (HYGH vs LQDH)", c63("HYGH") - c63("LQDH")), ("AUDJPY", t63(X.t("FX_IDC:AUDUSD") * X.t("FX_IDC:USDJPY"))), ("EM vs US", c63("EEM") - c63("SPY"))]
    gdir = np.sign(F["g"]) or 1
    agree = sum(1 for _, v in checks if np.sign(v) == gdir)
    conf = "".join(f"<tr><td class='nm'>{a}</td><td class='n {'g' if v>0 else 'r'}'>{v*100:+.1f}%</td><td>{'✔' if np.sign(v)==gdir else '✖'}</td></tr>" for a, v in checks)
    # headline call
    reg = F["regime"]
    head = [f"<b>Cycle:</b> tape says <b>{reg}</b> (growth {F['g']:+.2f}, inflation {F['i']:+.2f}), {F['regime_days']} sessions in · policy <b>{F['policy_state']}</b> · liquidity <b>{F['liq_state']}</b> · vol {F['vol_state']}.",
            f"<b>Dominant theme:</b> equities are trading on <b>{F['theme']}</b> (R² {F['theme_r2']:.2f}); stock–bond corr {F['sb_corr']:+.2f} ({'bonds not hedging' if F['sb_corr']>0.1 else 'bonds hedging'}).",
            f"<b>What's priced:</b> Fed strip {F.get('fed_priced_bp', float('nan')):+.0f}bp of hikes ({F.get('fed_priced_chg1w', float('nan')):+.0f}bp in 1W); 2s10s {F['s210']:+.0f}bp ({F['curve_regime']}); "
            f"5Y BE {F['be5']:.2f}%; HY {F['hy']*100:.0f}bp ({F['hy_pct']:.0f}th pct 10y); VIX {F['vix']:.1f}.",
            f"<b>Cross-asset confirmation of the growth read:</b> {agree}/{len(checks)} markets agree ({'confirmed' if agree >= 5 else 'partial' if agree >= 3 else 'NOT confirmed — divergence is the warning'}).",
            f"<b>Global:</b> {F['global_10y_up']}/8 major 10Y yields higher over 1M; US vs peers {F['us_vs_peer_1m']:+.0f}bp 1M ({'US-specific' if abs(F['us_vs_peer_1m']) > 15 else 'global move'}).",
            f"<b>Tape:</b> linkage {F['linkage']:.0f}% → {'macro-driven, trade momentum' if F['linkage'] > 60 else 'idiosyncratic, fade extremes' if F['linkage'] < 40 else 'no rule'}; "
            f"breadth {F['a50']:.0f}% of stocks > 50d, {F['sect50']}/11 sectors > 50d.",
            "<b>Theses:</b> " + ", ".join(f"{i} {s}" for i, s in F.get("theses", [])) + " (see THESIS).",
            "<b>Calls:</b> " + "; ".join(f"{a}: <b>{c.split(' — ')[0]}</b>" for a, c in F.get("calls", []))]
    flip = []
    flip.append(f"Regime flips if growth composite crosses 0 (now {F['g']:+.2f}) or inflation composite crosses 0 (now {F['i']:+.2f}) — watch the nearest one: "
                f"<b>{'growth' if abs(F['g']) < abs(F['i']) else 'inflation'}</b>.")
    flip.append("Theme flips if the top factor's R² is overtaken for 2+ weeks (see THEME tab).")
    tbl = K.table_html(rows, "Cross-asset dashboard · level · change · context")
    html = (f"<div class='brief'><div class='tt'>THE CALL</div><ul>" + "".join(f"<li>{h}</li>" for h in head) + "</ul>"
            f"<div class='tt'>WHAT WOULD CHANGE IT</div><ul>" + "".join(f"<li>{h}</li>" for h in flip) + "</ul></div>"
            f"<div class='mosaic'>{mos}<div class='mos'><div class='tt'>Cross-asset check ({'growth +' if gdir>0 else 'growth −'})</div><table>{conf}</table></div></div>"
            + calendar_html(X) + _safe_movers(X) +
            f"<div class='alerts'><div class='tt'>WHAT'S STRETCHED · WHAT CHANGED <span class='asof'>(trend flips use 50/200 SMA)</span></div><ul>" + ("".join(f"<li>{a}</li>" for a in al) or "<li>Nothing flagged</li>") + "</ul></div>" + tbl)
    return dict(key="brief", title="BRIEF", read=[], cards=[], html=html)
