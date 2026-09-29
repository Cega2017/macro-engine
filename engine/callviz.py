"""CALL CHECKS: one chart per call with its trigger and kill levels drawn on it, plus a pass/fail box.
Same thresholds as thesis.calls(); the chart makes the rule readable without hunting for the referenced levels."""
import numpy as np, pandas as pd, plotly.graph_objects as go
from plotly.subplots import make_subplots
from . import kit as K

KILL, TRIG, REF = "#e05252", "#4caf50", "#8a8a8a"
LB = 190   # ~9 months of daily bars shown; range buttons allow zooming in

def _fig(rows=2, heights=(0.62, 0.38)):
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, row_heights=list(heights)[:rows], vertical_spacing=0.05)
    return fig

def _hl(fig, y, text, color, row=1, dash="dash"):
    fig.add_hline(y=y, line=dict(color=color, width=1.3, dash=dash), row=row, col=1,
                  annotation_text=text, annotation_position="top left", annotation_font=dict(color=color, size=10))

def _step(fig, s, name, color, row=1, dash="dash"):
    s = s.dropna(); fig.add_trace(go.Scatter(x=s.index, y=s.values, name=name, line=dict(color=color, width=1.3, dash=dash, shape="hv")), row=row, col=1)

def _line(fig, s, name, color=K.WHT, row=1, width=1.5):
    s = s.dropna(); fig.add_trace(go.Scatter(x=s.index, y=s.values, name=f"{name}  {s.iloc[-1]:,.2f}", line=dict(color=color, width=width)), row=row, col=1)

def _candles(fig, X, sym, name, row=1):
    b = X.tvbars[X.tvbars.symbol == sym].sort_values("date").iloc[-LB:]
    fig.add_trace(go.Candlestick(x=pd.to_datetime(b.date), open=b.o, high=b.h, low=b.l, close=b.c, name=name,
                                 increasing=dict(line=dict(color="#3a8a2a", width=1), fillcolor="#3a8a2a"),
                                 decreasing=dict(line=dict(color="#a82626", width=1), fillcolor="#a82626")), row=row, col=1)

def _vline(fig, d, text, color=REF):
    fig.add_vline(x=pd.Timestamp(d).value / 1e6, line=dict(color=color, width=1, dash="dot"),
                  annotation_text=text, annotation_position="top", annotation_font=dict(color=color, size=9))

def _finish(fig, h=470):
    K._layout(fig, h); fig.update_layout(xaxis_rangeslider_visible=False, hovermode="x unified")
    for ax in fig.layout:
        if ax.startswith("xaxis"): fig.layout[ax].rangeslider = dict(visible=False)
    K.add_range(fig, "xaxis"); return fig

def _box(call, why, kill, note=""):
    """why/kill: list of (label, value text, bool met)."""
    ok = all(m for _, _, m in why); dead = any(m for _, _, m in kill)
    st, col = ("KILL HIT: drop the call", KILL) if dead else (("CALL LIVE", TRIG) if ok else ("TRIGGER FADING", "#e0b64a"))
    row = lambda l, v, m, good: (f"<tr><td class='a' style='text-align:left'>{l}</td><td class='n w'>{v}</td>"
                                 f"<td style='color:{(TRIG if good else KILL) if m else '#666'}'>{'✔' if m else '·'}</td></tr>")
    h = (f"<div class='ss'><div class='sst' style='color:{col}'>{st}</div><div class='w' style='text-align:center;margin-bottom:6px'><b>{call}</b></div>"
         f"<div class='tt'>WHY (needs all ✔)</div><table>" + "".join(row(l, v, m, True) for l, v, m in why) + "</table>"
         f"<div class='tt' style='margin-top:6px'>KILL (red ✔ = hit)</div><table>" + "".join(row(l, v, m, False) for l, v, m in kill) + "</table>"
         + (f"<div class='asof' style='margin-top:6px'>{note}</div>" if note else "") + "</div>")
    return h

def _pct_rank(s, n=252): return s.rolling(n, min_periods=n // 2).apply(lambda a: (a <= a[-1]).mean() * 100, raw=True)

def call_cards(X, cl):
    F = X.facts; cards = []; have = {a: c for a, c, *_ in cl}
    tells = F.get("event_tells", []); hr = sum("higher" in t[2] for t in tells) / max(len(tells), 1)
    vz = X.S.get("volZ", pd.DataFrame()); lk = X.S.get("linkage", pd.Series(dtype=float))
    def add(title, fig, side, sub):
        c = K.simple(title, fig, side=side, sub=sub); cards.append(c)

    # 1. duration: 2Y candles + payrolls-day close (kill), CPI close (ref); MOVE z with +1 kill line
    a = "US duration (TLT / ZN)"
    if a in have:
        y2 = X.y("US", "02Y"); fig = _fig(); _candles(fig, X, "TVC:US02Y", "US 2Y")
        nfp = [d for d in X.rel.get("NFP", []) if d <= X.asof and d in y2.index]; cpi = [d for d in X.rel.get("CPI", []) if d <= X.asof and d in y2.index]
        kl = y2.loc[nfp[-1]] if nfp else np.nan
        if nfp: _hl(fig, kl, f"KILL: 2Y closes below payrolls-day close {kl:.3f}% ({nfp[-1]:%m/%d})", KILL); _vline(fig, nfp[-1], "NFP")
        if cpi: _hl(fig, y2.loc[cpi[-1]], f"CPI-day close {y2.loc[cpi[-1]]:.3f}% ({cpi[-1]:%m/%d})", REF, dash="dot"); _vline(fig, cpi[-1], "CPI")
        mz = vz.get("Rates (MOVE)", pd.Series(dtype=float)).iloc[-LB:]
        _line(fig, mz, "MOVE z-score (1y)", K.AMB, row=2); _hl(fig, 1, "KILL (with 2Y line): MOVE z below +1", KILL, row=2)
        y10 = X.y("US", "10Y"); d10 = (y10.iloc[-1] - y10.iloc[-22]) * 100; lkv = F.get("linkage", np.nan)
        side = _box(have[a], [("10Y 1M change > +15bp", f"{d10:+.0f}bp", d10 > 15), ("Event tells on higher-rates side > 50%", f"{hr*100:.0f}%", hr > 0.5), ("Linkage > 55%", f"{lkv:.0f}%", lkv > 55), ("Not stretched: 10Y 1M rise < 35bp (else hold, don't add)", f"{d10:+.0f}bp", d10 < 35)],
                    [("2Y below payrolls close", f"{y2.iloc[-1]:.3f} vs {kl:.3f}", bool(y2.iloc[-1] < kl)), ("MOVE z < +1", f"{mz.iloc[-1]:+.2f}", bool(mz.iloc[-1] < 1))],
                    f"Kill needs BOTH. 2Y is {(y2.iloc[-1]-kl)*100:+.0f}bp from the kill line.")
        add("CALL CHECK · US duration", _finish(fig), side, "Top: US 2Y daily candles (TradingView). Red line = the kill level. Bottom: rates-vol z-score.")

    # 2. curve: 2s10s + 21d change in far-ZQ implied rate with +10 (tightening) and −20 (kill)
    a = "US curve 2s10s"
    if a in have:
        from .tabs_rates import policy_12m, curve_regime
        y2, y10 = X.y("US", "02Y"), X.y("US", "10Y"); s = ((y10 - y2) * 100).dropna().iloc[-LB:]; lab = F.get("curve_regime", "")
        p = policy_12m(X); pc = ((p - p.shift(21)) * 100).dropna().iloc[-LB:]
        fig = _fig(); _line(fig, s, "2s10s (bp)")
        _line(fig, pc, "21d change in far fed funds contract (bp)", K.AMB, row=2); _hl(fig, 10, "tightening trigger +10bp", TRIG, row=2); _hl(fig, -20, "KILL: −20bp", KILL, row=2)
        side = _box(have[a], [("2s10s regime = bear flattener", lab, "Bear flattener" in lab), ("Policy tightening (>+10bp 1M)", f"{pc.iloc[-1]:+.0f}bp", pc.iloc[-1] > 10)],
                    [("Regime flips to bull steepener", lab, lab == "Bull steepener"), ("Fed pricing −20bp in 1M", f"{pc.iloc[-1]:+.0f}bp", pc.iloc[-1] < -20)])
        add("CALL CHECK · 2s10s curve", _finish(fig), side, "Top: 2s10s. Bottom: how much hiking the far fed funds contract added in the last month.")

    # 3. SPY: price + 90th-pct-of-1y line; breadth with 40 trigger and 50 kill; VIX z
    a = "S&P 500 (SPY)"
    if a in have:
        cb = X.cboe; ts = (cb.VIX9D / cb.VIX3M).dropna(); hy = X.f("BAMLH0A0HYM2") * 100; h1 = (hy - hy.shift(21)).dropna()
        fig = _fig(); _line(fig, ts.iloc[-LB:], "VIX9D / VIX3M"); _hl(fig, 1.0, "HEDGE SIGNAL: above 1.0 = front-end stress (curve inverted)", KILL)
        _line(fig, h1.iloc[-LB:], "HY OAS 1M change (bp)", K.AMB, row=2); _hl(fig, 50, "HEDGE SIGNAL: +50bp in a month", KILL, row=2)
        spy = X.px.SPY; pct = (spy.iloc[-252:] <= spy.iloc[-1]).mean() * 100; a50v = X.t("INDEX:S5FI").iloc[-1]
        side = _box(have[a], [("No front-end stress (VIX9D/VIX3M < 1)", f"{ts.iloc[-1]:.2f}", ts.iloc[-1] < 1), ("Credit not breaking (HY < +50bp 1M)", f"{h1.iloc[-1]:+.0f}bp", h1.iloc[-1] < 50)],
                    [("VIX curve inverts", f"{ts.iloc[-1]:.2f}", bool(ts.iloc[-1] > 1)), ("HY +50bp in 1M", f"{h1.iloc[-1]:+.0f}bp", bool(h1.iloc[-1] > 50))],
                    f"Context: SPY {pct:.0f}th pct of 1y, breadth {a50v:.0f}%. The 2007–26 test found near-highs + narrow breadth + cheap vol did NOT predict 5% drawdowns, "
                    "so hedging waits for an actual stress signal. These two are proposed triggers, not yet tested.")
        add("CALL CHECK · S&P 500: when to hedge", _finish(fig), side, "Top: VIX short-end vs 3-month (above 1 = stress now). Bottom: HY spread 1M change.")

    # 4. RSP/SPY with rolling 3M high (kill)
    a = "Equal weight vs cap weight (RSP/SPY)"
    if a in have:
        r = (X.px.RSP / X.px.SPY).dropna(); hi = r.rolling(63).max().shift(1); fig = _fig(rows=1, heights=(1,))
        _line(fig, r.iloc[-LB:], "RSP/SPY"); _step(fig, hi.iloc[-LB:], "KILL: prior 3-month high", KILL)
        ch = (r.iloc[-1] / r.iloc[-64] - 1) * 100
        side = _box(have[a], [("RSP/SPY 3M change < −2%", f"{ch:+.1f}%", ch < -2)], [("New 3-month high", f"{(r.iloc[-1]/hi.iloc[-1]-1)*100:+.1f}% vs high", bool(r.iloc[-1] > hi.iloc[-1]))])
        add("CALL CHECK · equal vs cap weight", _finish(fig, 380), side, "Ratio falling = narrowing. The red step is the level that would kill the call.")

    # 5. HY OAS with 1M low (kill) and 40th pct 10y (trigger ceiling)
    a = "High yield vs IG (express: HYGH vs LQDH)"
    if a in have:
        hy = X.f("BAMLH0A0HYM2") * 100; lo = hy.rolling(21).min().shift(1); p40 = hy.iloc[-2500:].quantile(0.4)
        ccc = (X.f("BAMLH0A3HYC") * 100 - hy).dropna(); fig = _fig()
        _line(fig, hy.iloc[-LB:], "HY OAS (bp)"); _step(fig, lo.iloc[-LB:], "KILL: back below prior 1M low", KILL); _hl(fig, p40, f"40th pct of 10y ({p40:.0f}bp): trigger needs spreads below this", REF, dash="dot")
        _line(fig, ccc.iloc[-LB:], "CCC − HY (bp): early stress gauge", K.AMB, row=2)
        d1 = hy.iloc[-1] - hy.iloc[-22]; pc = (hy.iloc[-2500:] <= hy.iloc[-1]).mean() * 100
        side = _box(have[a], [("HY widened > 10bp in 1M", f"{d1:+.0f}bp", d1 > 10), ("From tight levels (< 40th pct 10y)", f"{pc:.0f}th", pc < 40)],
                    [("HY below its 1M low", f"{hy.iloc[-1]:.0f} vs {lo.iloc[-1]:.0f}", bool(hy.iloc[-1] < lo.iloc[-1]))])
        add("CALL CHECK · high yield", _finish(fig), side, "Top: HY spread with the kill step. Bottom: CCC minus HY, the weakest credits.")

    # 6. Oil vs energy equities: XLE/SPY with 1M high (kill); WTI with its level 21d ago
    a = "Oil / energy"
    if a in have:
        r = (X.px.XLE / X.px.SPY).dropna(); hi = r.rolling(21).max().shift(1); cl = X.t("NYMEX:CL1!")
        fig = _fig(); _line(fig, r.iloc[-LB:], "XLE / SPY"); _step(fig, hi.iloc[-LB:], "KILL: prior 1M high (equities confirm oil)", KILL)
        _candles(fig, X, "NYMEX:CL1!", "WTI front month", row=2); _hl(fig, cl.iloc[-22], f"WTI 1M ago {cl.iloc[-22]:.2f}: above = oil up", TRIG, row=2)
        c1 = (cl.iloc[-1] / cl.iloc[-22] - 1) * 100; x1 = (r.iloc[-1] / r.iloc[-22] - 1) * 100
        side = _box(have[a], [("Oil is the top THEME factor", F.get("theme", ""), "Oil" in F.get("theme", "")), ("WTI up over 1M", f"{c1:+.1f}%", c1 > 0), ("XLE lagging SPY over 1M", f"{x1:+.1f}%", x1 < 0)],
                    [("XLE/SPY at a new 1M high", f"{(r.iloc[-1]/hi.iloc[-1]-1)*100:+.1f}% vs high", bool(r.iloc[-1] > hi.iloc[-1]))])
        add("CALL CHECK · oil vs energy stocks", _finish(fig), side, "Top: energy stocks vs the market. Bottom: WTI candles with its level a month ago.")

    # 7. vol relative: MOVE z vs VIX z
    a = "Cross-asset vol"
    if a in have and not vz.empty:
        fig = _fig(rows=1, heights=(1,)); z = vz.iloc[-LB:]
        _line(fig, z["Rates (MOVE)"], "Rates vol z (MOVE)", K.AMB); _line(fig, z["Equity (VIX)"], "Equity vol z (VIX)", K.WHT)
        _hl(fig, 2, "trigger: MOVE z above +2", TRIG); _hl(fig, 0, "trigger: VIX z below 0", REF, dash="dot"); _hl(fig, 1, "KILL: VIX z above +1", KILL)
        m, v = z["Rates (MOVE)"].iloc[-1], z["Equity (VIX)"].iloc[-1]
        side = _box(have[a], [("MOVE z > +2", f"{m:+.2f}", m > 2), ("VIX z < 0", f"{v:+.2f}", v < 0)], [("VIX z > +1 (gap closed)", f"{v:+.2f}", v > 1)])
        add("CALL CHECK · equity vol vs rates vol", _finish(fig, 380), side, "Each vol gauge vs its own 1y history. The gap between the lines is the trade.")

    # 8/9. FX vs 2Y differential
    for p, cc, sgn in (("EURUSD", "DE", 1), ("USDCAD", "CA", -1), ("USDJPY", "JP", -1), ("AUDUSD", "AU", 1), ("GBPUSD", "GB", 1)):
        if p not in have: continue
        diff = ((X.y("US", "02Y") - X.y(cc, "02Y")) * 100).dropna(); spot = X.t(f"FX_IDC:{p}")
        d = pd.concat([spot, diff], axis=1).ffill().dropna(); d.columns = ["s", "d"]
        c63 = np.log(d.s).diff().rolling(63).corr(d.d.diff()).iloc[-1]; dd = d.d.iloc[-1] - d.d.iloc[-22]; kl = d.d.iloc[-1] - 15 * np.sign(dd)
        fig = _fig(); _candles(fig, X, f"FX_IDC:{p}", p)
        _line(fig, d.d.iloc[-LB:], f"US − {cc} 2Y differential (bp)", K.AMB, row=2); _hl(fig, d.d.iloc[-22], "differential 1M ago", REF, row=2, dash="dot")
        _hl(fig, kl, f"KILL: differential back to {kl:.0f}bp (15bp reversal)", KILL, row=2)
        side = _box(have[p], [("Pair trades the 2Y differential (|corr| ≥ 0.4)", f"{c63:+.2f}", abs(c63) >= 0.4), ("Differential moved ≥ 15bp in 1M", f"{dd:+.0f}bp", abs(dd) >= 15)],
                    [("Differential reverses 15bp", f"{d.d.iloc[-1]:.0f} vs {kl:.0f}", False)],
                    "Kill line is set 15bp back from today's differential; it moves with each build.")
        add(f"CALL CHECK · {p}", _finish(fig), side, f"Top: {p} daily candles. Bottom: the rate gap that is driving it.")
    # 10. KRE/KBWB pair watch: pair ratio (up = pair winning) + 20-session 2s10s slope change with ±5bp regime bands
    a = "Short KRE / long KBWB (pair watch)"
    if a in have:
        from .thesis import pair_watch, PAIR_STATS
        pw = pair_watch(X); r = pw["ratio"].iloc[-LB:]; ds = pw["ds20s"].dropna().iloc[-LB:]
        fig = _fig(); _line(fig, r / r.iloc[0] * 100, "KBWB / KRE (rebased; rising = pair winning)")
        _line(fig, ds, "2s10s 20-session change (bp)", K.AMB, row=2); _hl(fig, 5, "+5bp: steepening", TRIG, row=2, dash="dot"); _hl(fig, -5, "−5bp: flattening", REF, row=2, dash="dot")
        g = pw["reg"] in ("Bull steepen", "Flat")
        side = _box(have[a], [("20-session regime = bull steepen or flat", pw["reg"], g)],
                    [("Bear flattener (coin-flip regime: wait)", pw["reg"], pw["reg"] == "Bear flatten"),
                     ("Growth-led bear steepener (IWM beats SPY >1% 20d)", f"{pw['iwm20']:+.1f}%", pw["growth_led"])],
                    f"History after '{pw['reg']}' (2022+): {PAIR_STATS.get(pw['reg'], '—')}. 60-session regime: {pw['reg60']}. "
                    f"KRE–credit corr 63d {pw['c63']:+.2f} ({pw['c63_pct']:.0f}th pct). Watch only; sizing: per-leg $ = NAV × max loss % ÷ 27%.")
        add("CALL CHECK · KRE/KBWB pair (watch)", _finish(fig), side, "Top: big banks vs regionals. Bottom: 2s10s slope change over 20 sessions; regime also uses the 10Y direction.")

    return cards
