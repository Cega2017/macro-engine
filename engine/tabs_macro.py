import numpy as np, pandas as pd, plotly.graph_objects as go
from plotly.subplots import make_subplots
from . import kit as K

QN = {(1, 1): "Overheat", (1, -1): "Goldilocks", (-1, 1): "Stagflation", (-1, -1): "Slowdown"}
QC = {"Overheat": "#f28c28", "Goldilocks": "#3a8a2a", "Stagflation": "#d64545", "Slowdown": "#4a7bd6"}

def _z(s, win=756, minp=252):
    """z-score using only data up to t (rolling window) — no look-ahead."""
    return (s - s.rolling(win, min_periods=minp).mean()) / s.rolling(win, min_periods=minp).std()

def composites(X, h=63):
    px = X.px; f = X.fred.reindex(px.index).ffill()
    lr = lambda a, b: np.log(px[a] / px[b]).diff(h)
    G = pd.DataFrame({"Copper/Gold": lr("CPER", "GLD"), "Discretionary/Staples": lr("XLY", "XLP"), "Industrials/Utilities": lr("XLI", "XLU"),
                      "Small/Large": lr("IWM", "SPY"), "High beta/Low vol": lr("SPHB", "SPLV"), "HY credit (−ΔOAS)": -f["BAMLH0A0HYM2"].diff(h)})
    I = pd.DataFrame({"5Y breakeven": f["T5YIE"].diff(h), "10Y breakeven": f["T10YIE"].diff(h), "Agriculture (DBA)": np.log(px.DBA).diff(h),
                      "TIPS/Nominals": lr("TIP", "IEF"), "Oil (USO)": np.log(px.USO).diff(h)})
    Gz, Iz = G.apply(_z), I.apply(_z)
    return G, I, Gz, Iz, Gz.mean(axis=1, skipna=True), Iz.mean(axis=1, skipna=True)

def tab_cycle(X):
    cards, read = [], []
    G, I, Gz, Iz, g, i = composites(X)
    d = pd.DataFrame({"g": g, "i": i}).dropna()
    q = pd.Series([QN[(1 if a >= 0 else -1, 1 if b >= 0 else -1)] for a, b in zip(d.g, d.i)], index=d.index)
    vix = X.cboe.VIX.reindex(d.index).ffill(); vhi = vix > vix.rolling(252, min_periods=120).median()
    cur = q.iloc[-1]; days = int((q[::-1] != cur).values.argmax())
    from .tabs_rates import policy_12m
    p12 = policy_12m(X); pchg = (p12.iloc[-1] - p12.iloc[-22]) * 100
    pol = "TIGHTENING" if pchg > 10 else "EASING" if pchg < -10 else "STEADY"
    wal, rrp, tga = X.f("WALCL") / 1e6, X.f("RRPONTSYD") / 1e3, X.f("WTREGEN") / 1e6
    nl = pd.concat([wal, rrp, tga], axis=1).ffill().dropna(); nl = nl.iloc[:, 0] - nl.iloc[:, 1] - nl.iloc[:, 2]
    liq = "DRAINING" if nl.iloc[-1] - nl.loc[:nl.index[-1] - pd.Timedelta(days=90)].iloc[-1] < -0.05 else "ADDING" if nl.iloc[-1] - nl.loc[:nl.index[-1] - pd.Timedelta(days=90)].iloc[-1] > 0.05 else "FLAT"
    X.facts.update(regime=cur, g=d.g.iloc[-1], i=d.i.iloc[-1], vol_state="high" if vhi.iloc[-1] else "low", regime_days=days, policy_state=pol, policy_chg=pchg, liq_state=liq)
    # quadrant trajectory (weekly, last 26w)
    w = d.resample("W-FRI").last().iloc[-26:]
    fig = go.Figure()
    for (gx, iy), n in QN.items():
        fig.add_shape(type="rect", x0=0, x1=3 * gx, y0=0, y1=3 * iy, fillcolor=QC[n], opacity=0.10, line_width=0)
        fig.add_annotation(x=2.2 * gx, y=2.6 * iy, text=n, showarrow=False, font=dict(color=QC[n], size=12))
    fig.add_trace(go.Scatter(x=w.g, y=w.i, mode="lines+markers", line=dict(color=K.GRY, width=1), marker=dict(size=5, color=K.GRY), name="26w trail",
                             text=[f"week of {x:%Y-%m-%d}" for x in w.index], hovertemplate="%{text}<br>G %{x:.2f} I %{y:.2f}"))
    fig.add_trace(go.Scatter(x=[d.g.iloc[-1]], y=[d.i.iloc[-1]], mode="markers+text", marker=dict(size=16, color=QC[cur], symbol="diamond", line=dict(color="white", width=1)),
                             text=[f" now {d.g.iloc[-1]:+.2f}/{d.i.iloc[-1]:+.2f}"], textposition="middle right", name="now"))
    fig.add_hline(y=0, line_color="#666"); fig.add_vline(x=0, line_color="#666")
    fig.update_layout(xaxis=dict(range=[-2.6, 2.6], title="Growth momentum (z)"), yaxis=dict(range=[-2.6, 2.6], title="Inflation momentum (z)"), hovermode="closest")
    K._layout(fig, 460)
    # transition matrix (weekly, 4w ahead)
    qw = q.resample("W-FRI").last().dropna(); nxt = qw.shift(-4)
    tm = pd.crosstab(qw[:-4], nxt[:-4], normalize="index").reindex(index=list(QC), columns=list(QC)).fillna(0) * 100
    cnt = qw[:-4].value_counts()
    tr = "".join(f"<tr><td class='nm' style='color:{QC[a]}'>{a}</td>" + "".join(f"<td class='n {'hz' if a==b else ''}'>{tm.loc[a,b]:.0f}</td>" for b in QC) + f"<td class='n'>{cnt.get(a,0)}</td></tr>" for a in QC)
    side = (f"<div class='ss'><div class='sst'>4-week transition % (rows = now)</div><table><tr><th></th>" + "".join(f"<th>{b[:5]}</th>" for b in QC) + "<th>N wks</th></tr>" + tr +
            f"</table><div class='asof'>Weekly states since {qw.index[0]:%Y}. Small sample; overlapping.</div></div>")
    cards.append(K.simple("Growth × inflation momentum (tape)", fig, side=side, sub=f"Dots = weekly (Friday) readings, last 26 weeks. Now: <b style='color:{QC[cur]}'>{cur}</b> for {days} sessions · policy {pol} · liquidity {liq} · vol {'HIGH' if vhi.iloc[-1] else 'LOW'}"))
    # ribbon + component scores
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.25, 0.75], vertical_spacing=0.04)
    qq = q.iloc[-1500:]
    for n, c in QC.items():
        x = qq[qq == n]; fig.add_trace(go.Bar(x=x.index, y=[1] * len(x), marker_color=c, marker_line_width=0, name=n, showlegend=True), row=1, col=1)
    fig.add_trace(go.Scatter(x=g.index[-1500:], y=g.iloc[-1500:], name="Growth", line=dict(color=K.GRN, width=1.3)), row=2, col=1)
    fig.add_trace(go.Scatter(x=i.index[-1500:], y=i.iloc[-1500:], name="Inflation", line=dict(color=K.AMB, width=1.3)), row=2, col=1)
    fig.add_hline(y=0, line_color="#666", row=2, col=1); fig.update_layout(bargap=0); fig.update_yaxes(visible=False, row=1, col=1)
    cards.append(K.simple("Regime ribbon + composite scores", K._layout(fig, 380), sub="Each score = average z of 63-day changes (3y rolling z, known at t)"))
    # component table
    comp = pd.concat([Gz.iloc[-1].rename("z now"), (Gz.iloc[-1] - Gz.iloc[-22]).rename("Δ1M")], axis=1).assign(side="Growth")
    comp = pd.concat([comp, pd.concat([Iz.iloc[-1].rename("z now"), (Iz.iloc[-1] - Iz.iloc[-22]).rename("Δ1M")], axis=1).assign(side="Inflation")])
    cards.append(K.simple("Composite inputs (z)", K.heat(comp[["z now", "Δ1M"]].round(2), h=40 + 26 * len(comp), fmt=".2f"),
                          sub="Growth: copper/gold, XLY/XLP, XLI/XLU, IWM/SPY, SPHB/SPLV, HY OAS. Inflation: 5Y/10Y BE, DBA (ags), TIP/IEF, USO. DBA replaces DBC, which is ~half energy and double-counted oil."))
    # conditional forward returns by regime (21d)
    assets = ["SPY", "QQQ", "IWM", "TLT", "GLD", "DBC", "DBA", "UUP", "HYG", "EEM", "XLE"]
    fr = np.log(X.tr[assets]).diff(21).shift(-21).reindex(q.index)
    tab = fr.groupby(q).mean().reindex(list(QC)) * 100; hit = (fr > 0).groupby(q).mean().reindex(list(QC)) * 100
    cards.append(K.simple("Next-21d mean return by regime (%)", K.heat(tab.round(1), h=220, fmt=".1f"),
                          sub=f"Daily obs since {q.index[0]:%Y}, overlapping 21d windows → ~{len(q)//21} independent obs total. Context, not a signal."))
    cur_best = tab.loc[cur].sort_values()
    read.append("<b>What this is:</b> the tape regime says which macro backdrop markets are <i>trading as if</i> we are in, read from asset prices alone "
                "(cyclical vs defensive stocks, copper vs gold, credit, breakevens, oil). It is not a measure of the economy: GDP or payrolls can say otherwise, "
                "and the tape often moves before the data does. Treat it as positioning and pricing, not a forecast.")
    read.append(f"Tape regime: <b style='color:{QC[cur]}'>{cur}</b> (growth {d.g.iloc[-1]:+.2f}, inflation {d.i.iloc[-1]:+.2f}) for {days} sessions. "
                f"Policy <b>{pol}</b> (12M-ahead fed funds {pchg:+.0f}bp in 1M) · liquidity <b>{liq}</b> (Fed net liquidity, 3M) · vol <b>{'HIGH' if vhi.iloc[-1] else 'LOW'}</b>.")
    read.append(f"Growth momentum {'rising' if d.g.iloc[-1] > d.g.iloc[-22] else 'falling'} over 1M ({d.g.iloc[-22]:+.2f} → {d.g.iloc[-1]:+.2f}); inflation {'rising' if d.i.iloc[-1] > d.i.iloc[-22] else 'falling'} ({d.i.iloc[-22]:+.2f} → {d.i.iloc[-1]:+.2f}).")
    read.append(f"4-week persistence of {cur}: {tm.loc[cur, cur]:.0f}%. Most likely exit: {tm.loc[cur].drop(cur).idxmax()} ({tm.loc[cur].drop(cur).max():.0f}%).")
    read.append(f"In past {cur} spells the best 21d performers were {', '.join(cur_best.index[-3:][::-1])}; worst {', '.join(cur_best.index[:2])} (small sample).")
    return dict(key="cycle", title="CYCLE", read=read, cards=cards)

def tab_theme(X):
    """Dominant theme: which macro factor explains equity/bond daily moves right now."""
    cards, read = [], []
    f = X.fred.reindex(X.px.index).ffill()
    dxy = X.t("TVC:DXY").reindex(X.px.index).ffill(); cl = X.t("NYMEX:CL1!").reindex(X.px.index).ffill()
    F = pd.DataFrame({"Real rates (Δ10Y TIPS)": f.DFII10.diff(), "Infl. expectations (Δ5Y BE)": f.T5YIE.diff(), "Dollar (DXY)": dxy.pct_change(),
                      "Oil (WTI)": cl.pct_change(), "Credit (ΔHY OAS)": f.BAMLH0A0HYM2.diff()}).dropna()
    A = {"SPY": X.ret("SPY"), "QQQ": X.ret("QQQ"), "IWM": X.ret("IWM"), "TLT": X.ret("TLT"), "GLD": X.ret("GLD"), "EEM": X.ret("EEM"), "HYG": X.ret("HYG")}
    W = 63
    corr_now = pd.DataFrame({a: F.iloc[-W:].corrwith(r.reindex(F.index).iloc[-W:]) for a, r in A.items()}).T
    corr_1y = pd.DataFrame({a: F.iloc[-252:].corrwith(r.reindex(F.index).iloc[-252:]) for a, r in A.items()}).T
    cards.append(K.simple("63d correlation: assets vs macro factors", K.heat(corr_now.round(2), h=300),
                          sub="Daily changes. Biggest |corr| in a row = what that asset is trading on right now."))
    cards.append(K.simple("Change vs 1y correlation", K.heat((corr_now - corr_1y).round(2), h=300), sub="Which linkages are strengthening (green) or breaking (red)"))
    spy = A["SPY"].reindex(F.index)
    r2 = pd.DataFrame({k: spy.rolling(W).corr(F[k]) ** 2 for k in F}).iloc[-750:]
    cards.append(K.simple("What is SPY trading on? rolling 63d R² by factor", K.lines({k: r2[k] for k in r2}, h=360), sub="Univariate R² of SPY daily returns on each factor"))
    tlt = A["TLT"].reindex(F.index); sb = spy.rolling(W).corr(tlt).dropna()
    rb = lambda s: s.iloc[-756:] / s.iloc[-756] * 100
    cards.append(K.card("Stock–bond correlation (SPY vs TLT, 63d)", {"SPY 63d return %": (X.tr.SPY.pct_change(63) * 100).iloc[-756:], "TLT 63d return %": (X.tr.TLT.pct_change(63) * 100).iloc[-756:]}, -sb.iloc[-756:], "minus 63d corr (flipped so green = bonds hedging)",
                        derived_kind="bars", sub="Pane plots −corr: above 0 (green) = bonds hedge equities; below 0 (red) = stocks and bonds fall together, rates are the risk", hist=True))
    dom = r2.iloc[-1].sort_values(ascending=False)
    X.facts.update(theme=dom.index[0], theme_r2=dom.iloc[0], sb_corr=sb.iloc[-1])
    read.append(f"Dominant theme for equities: <b>{dom.index[0]}</b> (R² {dom.iloc[0]:.2f}), then {dom.index[1]} ({dom.iloc[1]:.2f}). Sign: SPY vs {dom.index[0]} corr {corr_now.loc['SPY', dom.index[0]]:+.2f}.")
    read.append(f"Stock–bond corr {sb.iloc[-1]:+.2f} → bonds {'HEDGE' if sb.iloc[-1] < -0.1 else 'do NOT hedge' if sb.iloc[-1] > 0.1 else 'are a weak hedge for'} equities. "
                f"When positive, inflation/rates is the macro driver and 60/40 diversification fails.")
    brk = (corr_now - corr_1y).abs().stack().sort_values(ascending=False).head(3)
    read.append("Biggest correlation shifts vs 1y: " + "; ".join(f"{a}↔{b} {corr_1y.loc[a,b]:+.2f}→{corr_now.loc[a,b]:+.2f}" for (a, b), _ in brk.items()) + ".")
    return dict(key="theme", title="THEME", read=read, cards=cards)

def tab_inflation(X):
    cards, read = [], []
    be5, be10, f55 = X.f("T5YIE"), X.f("T10YIE"), X.f("T5YIFR"); r10 = X.f("DFII10")
    cards.append(K.card("Breakevens", {"5Y BE": be5.iloc[-2500:], "10Y BE": be10.iloc[-2500:], "5y5y fwd": f55.iloc[-2500:]}, (be5 - be10).iloc[-2500:] * 100, "5Y − 10Y BE (bp)",
                        sub="Front-loaded inflation (5Y > 10Y) = near-term shock; 5y5y = long-run anchor"))
    oil = X.t("NYMEX:CL1!")
    d = pd.concat([be5, oil], axis=1).dropna().iloc[-750:]
    cards.append(K.simple("5Y breakeven vs WTI", K.lines({"5Y BE": d.iloc[:, 0]}, secondary={"WTI": d.iloc[:, 1]}), sub="Energy pass-through to inflation pricing"))
    gld = X.t("COMEX:GC1!")
    d = pd.concat([gld, r10], axis=1).dropna().iloc[-1500:]; d.columns = ["GLD", "r"]
    fig = K.lines({"Gold (GC1!)": d.GLD}, secondary={"10Y real yield (inverted)": -d.r})
    cards.append(K.simple("Gold vs 10Y real yield (inverted)", fig, sub="Gap = gold trading on something other than real rates (fiscal / geopolitical / CB buying)"))
    ratio = X.px.TIP / X.px.IEF
    cards.append(K.card("TIP / IEF", {"TIP/IEF": ratio.iloc[-1500:], "100d SMA": ratio.rolling(100).mean().iloc[-1500:]}, (ratio / ratio.rolling(100).mean() - 1).iloc[-1500:] * 100, "% vs 100d SMA",
                        sub="Rising = inflation protection outperforming nominals"))
    cards.append(K.card("Commodities: broad (DBC) vs agriculture (DBA)", {"DBC (broad, ~half energy)": X.px.DBC.iloc[-1500:] / X.px.DBC.iloc[-1500] * 100, "DBA (agriculture)": X.px.DBA.iloc[-1500:] / X.px.DBA.iloc[-1500] * 100},
                        X.px.DBA.pct_change(63).iloc[-1500:] * 100, "DBA 63d % change", sub="DBC moves mostly with oil; DBA is the non-energy (food) inflation pulse and is what the inflation composite uses"))
    rv = X.ret("USO").rolling(21).std() * np.sqrt(252) * 100; ovx = X.f("OVXCLS")
    vrp = (ovx - rv.reindex(ovx.index)).dropna()
    cards.append(K.card("Crude implied vs realized", {"OVX": ovx.iloc[-1000:], "USO RV21": rv.iloc[-1000:]}, vrp.iloc[-1000:], "OVX − RV", sub="Positive = fear premium; negative = realized outrunning implied (squeeze)"))
    cl = pd.DataFrame({"1Y": X.f("EXPINF1YR"), "5Y": X.f("EXPINF5YR")}).iloc[-120:]
    cards.append(K.simple("Cleveland Fed expected inflation (monthly model)", K.lines({k: cl[k] for k in cl}, h=300), sub="Model-based, monthly — context"))
    X.facts.update(be5=be5.iloc[-1], be5_1m=(be5.iloc[-1] - be5.iloc[-22]) * 100, f55=f55.iloc[-1], r10=r10.iloc[-1])
    read.append(f"5Y breakeven <b>{be5.iloc[-1]:.2f}%</b> ({(be5.iloc[-1]-be5.iloc[-22])*100:+.0f}bp 1M, {K.stats(be5.iloc[-756:])['pct']:.0f}th pct 3y); 5y5y {f55.iloc[-1]:.2f}% "
                f"→ long-run anchor {'intact' if f55.iloc[-1] < 2.6 else 'drifting higher'}.")
    read.append(f"10Y real yield {r10.iloc[-1]:.2f}% ({(r10.iloc[-1]-r10.iloc[-22])*100:+.0f}bp 1M). Gold {'decoupled from' if gld.pct_change(63).iloc[-1] > 0 and r10.diff(63).iloc[-1] > 0 else 'consistent with'} real rates over 3M.")
    ag = pd.DataFrame({"Corn": X.t("CBOT:ZC1!"), "Wheat": X.t("CBOT:ZW1!"), "Copper": X.t("COMEX:HG1!"), "WTI": X.t("NYMEX:CL1!"), "Brent": X.t("ICEEUR:BRN1!")}).ffill().iloc[-504:]
    cards.append(K.simple("Commodity futures (rebased, 2y)", K.lines({k: ag[k] / ag[k].dropna().iloc[0] * 100 for k in ag}, h=320), sub="TradingView front months"))
    read.append(f"Crude vol premium OVX−RV {vrp.iloc[-1]:+.1f} ({K.stats(vrp.iloc[-756:])['pct']:.0f}th pct 3y).")
    return dict(key="inflation", title="INFLATION", read=read, cards=cards)

PAIRS = [("CPER", "GLD", "Copper / Gold", "Growth vs fear. Rising = reflation/growth; falling = defensive, growth scare."),
         ("XLY", "XLP", "Discretionary / Staples", "Rising = consumer risk appetite, soft landing; falling = defensive consumer stress."),
         ("XLI", "XLU", "Industrials / Utilities", "Cyclical capex vs bond proxies. Rising = growth; falling = slowdown or falling-rate bid."),
         ("IWM", "SPY", "Small / Large", "Domestic, rate-sensitive, credit-dependent vs mega-cap. Rising = broadening, easier financing."),
         ("SPHB", "SPLV", "High beta / Low vol", "Pure risk appetite gauge."),
         ("KRE", "SPY", "Regional banks / SPX", "Credit creation and curve health. Falling = funding/credit stress."),
         ("IYT", "SPY", "Transports / SPX", "Goods-economy activity (Dow theory)."),
         ("SMH", "SPY", "Semis / SPX", "Global tech/AI capex cycle leadership."),
         ("XHB", "SPY", "Homebuilders / SPX", "Rate-sensitive housing demand; the first place the 10Y bites."),
         ("EEM", "SPY", "EM / US", "Global growth + weaker USD; falling = dollar squeeze / US exceptionalism."),
         ("GLD", "TLT", "Gold / Long bonds", "Hard asset vs duration. Rising = inflation/fiscal/geopolitical hedge; falling = disinflation bid."),
         ("HYGH", "LQDH", "HY / IG, rate-hedged", "Credit risk appetite with the Treasury leg stripped out (rate-hedged ETFs). Falling = junk lagging quality before equities notice.")]

def tab_growth(X):
    cards, read, rows = [], [], []
    fig = make_subplots(rows=3, cols=4, subplot_titles=[p[2] for p in PAIRS], vertical_spacing=0.09, horizontal_spacing=0.04)
    for k, (a, b, n, _) in enumerate(PAIRS):
        r = (X.px[a] / X.px[b]).dropna(); sma = r.rolling(100).mean(); rr = r.iloc[-126:]; base = rr.iloc[0]
        rw, cl = k // 4 + 1, k % 4 + 1
        up = r.iloc[-1] > sma.iloc[-1]
        fig.add_trace(go.Scatter(x=rr.index, y=rr / base * 100, line=dict(color=K.GRN if up else K.RED, width=1.3), showlegend=False, name=n), row=rw, col=cl)
        fig.add_trace(go.Scatter(x=rr.index, y=sma.iloc[-126:] / base * 100, line=dict(color=K.GRY, width=1, dash="dot"), showlegend=False, name="100d SMA"), row=rw, col=cl)
        z = K.stats(np.log(r).diff(63).iloc[-756:])["z"]
        rows.append((n, up, (r.iloc[-1] / r.iloc[-64] - 1) * 100, z, _))
    fig.update_annotations(font=dict(size=10, color=K.AMB)); K._layout(fig, 640, legend=False)
    tr = "".join(f"<tr><td class='nm'>{n}</td><td class='{'g' if up else 'r'}'>{'ABOVE' if up else 'BELOW'}</td><td class='n {'g' if c>0 else 'r'}'>{c:+.1f}%</td><td class='n'>{z:+.1f}</td><td class='txt'>{t}</td></tr>" for n, up, c, z, t in rows)
    cards.append(K.simple("Macro internals (6M, rebased; dotted = 100d SMA)", fig, sub="Green = ratio above its 100d SMA"))
    tbl = f"<div class='tbl'><div class='tt'>Internals read</div><table><tr><th>Ratio</th><th>vs 100d</th><th>3M</th><th>3M z</th><th>What it tells you</th></tr>{tr}</table></div>"
    ups = sum(r[1] for r in rows[:10])
    X.facts.update(internals_up=ups, internals_n=10)
    read.append(f"<b>{ups} of 10</b> growth-sensitive ratios are above their 100d SMA → tape growth read: <b>{'broadening/expanding' if ups >= 7 else 'mixed' if ups >= 4 else 'defensive/slowing'}</b>.")
    strong = sorted(rows, key=lambda r: -r[3])[:2]; weak = sorted(rows, key=lambda r: r[3])[:2]
    read.append("Strongest 3M: " + ", ".join(f"{r[0]} ({r[3]:+.1f}σ)" for r in strong) + ". Weakest: " + ", ".join(f"{r[0]} ({r[3]:+.1f}σ)" for r in weak) + ".")
    # ---- momentum: multi-horizon z-scores, acceleration, and the composite growth impulse
    H = {"1W": 5, "1M": 21, "3M": 63, "6M": 126}; M = {}; P = {}
    for a, b, n, _ in PAIRS:
        lr = np.log(X.px[a] / X.px[b]).dropna(); M[n] = {}; P[n] = {}
        for k, h in H.items():
            ch = lr.diff(h); M[n][k] = K.stats(ch.iloc[-756:])["z"]; P[n][k] = ch.iloc[-1] * 100
    MZ = pd.DataFrame(M).T[list(H)]; MP = pd.DataFrame(P).T[list(H)]
    MZ["Accel (1M z − 3M z)"] = MZ["1M"] - MZ["3M"]
    fig = K.heat(MZ.round(1), h=440, fmt="+.1f"); cards.append(K.simple("Growth momentum by horizon (z-score of each ratio's change vs its own 3y history)", fig,
        sub="Green = growth-side ratio rising faster than normal for that horizon. Accel > 0 = the last month is stronger than the 3-month trend (momentum improving)."))
    _, _, _, _, gc, _ = composites(X); gi = gc.dropna(); acc = gi.diff(21)
    cards.append(K.card("Growth impulse: tape growth composite and its 1M change", {"Growth composite (z)": gi.iloc[-756:]}, acc.iloc[-756:], "21d change (acceleration)", derived_kind="bars",
        sub="Level = growth momentum (63d changes, z-scored). Bars = is that momentum building (green) or fading (red)? Same composite as the F1 CYCLE x-axis."))
    pos1, pos3 = int((MP["1M"] > 0).sum()), int((MP["3M"] > 0).sum()); accn = int((MZ["Accel (1M z − 3M z)"] > 0).sum())
    X.facts.update(g_accel=acc.iloc[-1], mom_pos1m=pos1, mom_accel=accn)
    read.append(f"Momentum: <b>{pos1}/{len(MP)}</b> growth ratios up over 1M, {pos3}/{len(MP)} over 3M; <b>{accn}/{len(MP)}</b> accelerating (1M stronger than 3M). "
                f"Growth composite {gi.iloc[-1]:+.2f} and {'<b>building</b>' if acc.iloc[-1] > 0 else '<b>fading</b>'} ({acc.iloc[-1]:+.2f} over 1M).")
    ic = X.f("ICSA"); gdpn = X.f("GDPNOW")
    cards.append(K.card("Initial jobless claims (context)", {"Claims": ic.iloc[-160:]}, (ic.rolling(4).mean() / ic.rolling(52).mean() - 1).iloc[-160:] * 100, "4wk avg vs 52wk avg (%)",
                        sub="Release data — context only, not an engine input"))
    return dict(key="growth", title="GROWTH", read=read, cards=cards, table=tbl)
