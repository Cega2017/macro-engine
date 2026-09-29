import numpy as np, pandas as pd, plotly.graph_objects as go
from plotly.subplots import make_subplots
from sklearn.decomposition import PCA
from . import kit as K

def world_board(X):
    """World equity indices by region (TradingView, local currency, price return)."""
    from .tv import EQ_IDX
    html, rows_all = "", []
    for reg, d in EQ_IDX.items():
        rows = [K.row_stats(n, X.t(s), "pct", stale_days=3) for n, s in d.items()]
        rows = [r for r in rows if r]; rows_all += rows
        html += K.table_html(rows, f"{reg} · local currency, price return")
    up = sum(r["m1"] > 0 for r in rows_all); n = len(rows_all)
    best = max(rows_all, key=lambda r: r["m1"]); worst = min(rows_all, key=lambda r: r["m1"])
    hi = [r["name"] for r in rows_all if r["pct"] >= 95]
    read = (f"World equities: <b>{up}/{n}</b> major indices up over 1M; best {best['name']} ({best['m1']:+.1f}%), worst {worst['name']} ({worst['m1']:+.1f}%). "
            + (f"At 1y highs (95th pct+): {', '.join(hi)}." if hi else "None at 1y highs."))
    X.facts.update(world_up=up, world_n=n)
    return f"<div class='tt' style='margin-top:6px'>WORLD EQUITY BOARD</div>{html}", read

def tab_equity(X):
    cards, read = [], []
    px = X.px
    # breadth from constituents (point-in-time membership not applied here: current+changed members since 2023 → mild survivorship, flagged)
    a20, a50, a200 = X.t("INDEX:S5TW"), X.t("INDEX:S5FI"), X.t("INDEX:S5TH")
    secs_ = ["XLK", "XLC", "XLY", "XLF", "XLI", "XLE", "XLB", "XLV", "XLP", "XLU", "XLRE"]
    sb = (px[secs_] > px[secs_].rolling(50).mean()).sum(axis=1)
    start = px.index[-756]
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.4, 0.38, 0.22], vertical_spacing=0.03)
    spy = px.SPY[px.index >= start]
    fig.add_trace(go.Scatter(x=spy.index, y=spy.values, name=f"SPY {spy.iloc[-1]:,.2f}", line=dict(color=K.WHT, width=1.3)), row=1, col=1)
    for s, n, c in ((a20, "% > 20d", K.BLU), (a50, "% > 50d", K.AMB), (a200, "% > 200d", "#c77dff")):
        s = s[s.index >= start]; fig.add_trace(go.Scatter(x=s.index, y=s.values, name=f"{n} {s.iloc[-1]:.0f}", line=dict(color=c, width=1.2)), row=2, col=1)
    for y in (20, 50, 80): fig.add_hline(y=y, line=dict(color="#555", dash="dot", width=0.7), row=2, col=1)
    sbb = sb[sb.index >= start]
    fig.add_trace(go.Bar(x=sbb.index, y=sbb.values, name=f"Sectors > 50d {int(sbb.iloc[-1])}/11", showlegend=False, marker_color=np.where(sbb.values >= 6, K.GRN, K.RED), marker_line_width=0), row=3, col=1)
    K._layout(fig, 640); fig.update_xaxes(domain=[0, 0.86]); fig.update_layout(bargap=0); K.add_range(fig, "xaxis")
    cards.append(K.simple("SPY vs breadth (shared time axis)", fig, sub="Top: SPY. Middle: % of S&P 500 stocks above 20/50/200d (TradingView). Bottom: sectors above their 50d (of 11; green = 6 or more). Divergence = index up while the middle pane falls."))
    rel = np.log(px.RSP / px.SPY) * 100
    cards.append(K.card("Equal weight vs cap weight", {"SPY (rebased)": px.SPY / px.SPY.iloc[0] * 100, "RSP (rebased)": px.RSP / px.RSP.iloc[0] * 100}, (rel - rel.iloc[-2500]).iloc[-2500:], "log(RSP/SPY) since start (%)",
                        sub="Falling = narrowing leadership. Long-run test (1926–) showed no reliable timing signal from this"))
    fr = X.french.dropna(); sig = (np.log1p(fr.vw_hi30) - np.log1p(fr.ew_hi30)).rolling(12).sum() * 100
    cards.append(K.card("Cap-wt minus equal-wt, largest 30% US stocks (1926–)", {"Cum. cap/equal ratio": np.exp((np.log1p(fr.vw_hi30) - np.log1p(fr.ew_hi30)).cumsum())},
                        sig, "Trailing 12m spread (%)", main_log=True, sub="Ken French / CRSP monthly"))
    # sector heat: last 10 sessions excess vs SPY
    secs = ["XLK", "XLC", "XLY", "XLF", "XLI", "XLE", "XLB", "XLV", "XLP", "XLU", "XLRE"]
    ex = (px[secs].pct_change().sub(px.SPY.pct_change(), axis=0) * 100).iloc[-10:].T
    ex.columns = [f"{c:%m/%d}" for c in ex.columns]
    ex["10d"] = ((px[secs].iloc[-1] / px[secs].iloc[-11]) / (px.SPY.iloc[-1] / px.SPY.iloc[-11]) - 1) * 100
    cards.append(K.simple("Sector excess return vs SPY, last 10 sessions (%)", K.heat(ex.round(2), h=380), sub="Daily; last column = cumulative 10d"))
    rs = (px[secs].iloc[-126:] / px[secs].iloc[-126]).div(px.SPY.iloc[-126:] / px.SPY.iloc[-126], axis=0) * 100
    cards.append(K.simple("Sector relative strength vs SPY (6M, rebased 100)", K.lines({s: rs[s] for s in secs}, h=380)))
    X.facts.update(a50=a50.iloc[-1], a200=a200.iloc[-1], sect50=int(sb.iloc[-1]), rsp_spy_3m=(rel.iloc[-1] - rel.iloc[-64]))
    spy_pct = (px.SPY.iloc[-252:] <= px.SPY.iloc[-1]).mean() * 100
    read.append(f"Stock breadth <b>{a50.iloc[-1]:.0f}%</b> above 50d / <b>{a200.iloc[-1]:.0f}%</b> above 200d; sector breadth <b>{int(sb.iloc[-1])}/11</b> above 50d. "
                f"SPY at {spy_pct:.0f}th pct of 1y range → {'<b>fragile: index at highs on a narrow base</b>' if spy_pct > 90 and a50.iloc[-1] < 40 else 'no divergence'}.")
    read.append(f"RSP vs SPY {rel.iloc[-1]-rel.iloc[-64]:+.1f}% over 3M.")
    best, worst = ex["10d"].idxmax(), ex["10d"].idxmin()
    read.append(f"10-session leadership: {best} ({ex['10d'].max():+.1f}% vs SPY); laggard {worst} ({ex['10d'].min():+.1f}%).")
    read.append("Narrow breadth alone has not timed the index (1926– test: sign flips by sample). Use it as a condition, not a trigger.")
    try:
        wb, wr = world_board(X); read.insert(0, wr)
    except Exception as e: wb = f"<div class='warn'>world board failed: {e}</div>"
    return dict(key="equity", title="EQUITY & BREADTH", read=read, cards=cards, html=wb)

PAIRS = [("EURUSD", "DE", 1), ("USDJPY", "JP", -1), ("GBPUSD", "GB", 1), ("AUDUSD", "AU", 1), ("USDCAD", "CA", -1)]
def tab_fx(X):
    cards, read = [], []
    dxy = X.t("TVC:DXY")
    cards.append(K.card("Dollar index (DXY)", {"DXY": dxy}, dxy.pct_change(21) * 100, "21d % change", sub="TradingView"))
    rows = []
    for p, cc, sgn in PAIRS:
        spot = X.t(f"FX_IDC:{p}"); diff = (X.y("US", "02Y") - X.y(cc, "02Y")) * 100
        d = pd.concat([spot, diff], axis=1).ffill().dropna(); d.columns = ["s", "d"]
        c63 = np.log(d.s).diff().rolling(63).corr(d.d.diff())
        fig = K.lines({p: d.s.iloc[-750:]}, secondary={f"US−{cc} 2Y (bp)": d.d.iloc[-750:]})
        cards.append(K.simple(f"{p} vs US−{cc} 2Y rate differential", fig, sub=f"63d corr of daily changes: {c63.iloc[-1]:+.2f} (expected sign {'−' if sgn > 0 else '+'})"))
        rows.append((p, d.s.iloc[-1], (d.s.iloc[-1] / d.s.iloc[-22] - 1) * 100, d.d.iloc[-1], d.d.iloc[-1] - d.d.iloc[-22], c63.iloc[-1]))
    tr = "".join(f"<tr><td class='nm'>{p}</td><td class='n w'>{s:.4f}</td><td class='n {'g' if c>0 else 'r'}'>{c:+.2f}%</td><td class='n'>{dd:+.0f}</td><td class='n'>{dc:+.0f}</td>"
                 f"<td class='n {'hz' if abs(k)>=0.4 else ''}'>{k:+.2f}</td><td>{'rates-driven' if abs(k)>=0.4 else 'not trading rates'}</td></tr>" for p, s, c, dd, dc, k in rows)
    tbl = f"<div class='tbl'><div class='tt'>FX vs 2Y differentials</div><table><tr><th>Pair</th><th>Spot</th><th>1M</th><th>US−foreign 2Y bp</th><th>Δ1M bp</th><th>63d corr</th><th>Read</th></tr>{tr}</table></div>"
    fx = {p: X.t(f"FX_IDC:{p}") for p in ("EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "USDCAD", "USDCHF", "USDMXN", "USDCNH")}
    R = pd.DataFrame({k: (np.log(s).diff().rolling(30).std() - np.log(s).diff().rolling(100).std()) * np.sqrt(252) * 100 for k, s in fx.items()}).iloc[-750:]
    cards.append(K.simple("FX vol impulse: RV30 − RV100", K.lines({k: R[k] for k in R}, h=340, hlines=(0,)), sub="Positive = short-term vol expanding vs trend"))
    X.facts.update(dxy_1m=(dxy.iloc[-1] / dxy.iloc[-22] - 1) * 100)
    read.append(f"DXY {dxy.iloc[-1]:.2f} ({X.facts['dxy_1m']:+.1f}% 1M, {K.stats(dxy.iloc[-756:])['pct']:.0f}th pct 3y).")
    rd = [r[0] for r in rows if abs(r[5]) >= 0.4]
    read.append(f"Trading on rate differentials: {', '.join(rd) if rd else 'none'}; " + ", ".join(f"{r[0]} diff {r[4]:+.0f}bp 1M" for r in rows) + ".")
    return dict(key="fx", title="FX", read=read, cards=cards, table=tbl)

def _dpar(y, T):
    """Modified duration of a par bond with annual coupon = yield y (decimal), maturity T years."""
    return (1 / y) * (1 - (1 + y) ** (-T))

def credit_durations(X):
    """Daily duration estimates. HY: par-bond formula at HY effective yield and HYG's avg maturity, scaled to match HYG's published duration today.
    IG: maturity solved so the formula matches LQD's published duration today. CCC: HY's maturity and scale at the CCC yield (+3y/5y band)."""
    from . import config as C
    yh, yi, yc = X.f("BAMLH0A0HYM2EY") / 100, X.f("BAMLC0A0CMEY") / 100, X.f("BAMLH0A3HYCEY") / 100
    T = C.HY_WAM; sc = C.CREDIT_DUR["HY"][0] / _dpar(yh.iloc[-1], T)
    Ts = np.linspace(2, 30, 2801); Ti = Ts[np.argmin(np.abs(_dpar(yi.iloc[-1], Ts) - C.CREDIT_DUR["IG"][0]))]
    return pd.DataFrame({"HY": sc * _dpar(yh, T), "IG": _dpar(yi, Ti), "CCC": sc * _dpar(yc, T), "CCC_lo": sc * _dpar(yc, 3.0), "CCC_hi": sc * _dpar(yc, 5.0)}).dropna()

def tab_credit(X):
    cards, read = [], []
    hy, ig, ccc = X.f("BAMLH0A0HYM2"), X.f("BAMLC0A0CM"), X.f("BAMLH0A3HYC")
    cards.append(K.card("High-yield OAS", {"HY OAS": hy.iloc[-2500:]}, hy.diff(5).iloc[-2500:] * 100, "5d change (bp)", derived_kind="bars", sub="ICE BofA via FRED"))
    cards.append(K.card("HY / IG spread ratio", {"HY OAS": hy.iloc[-2500:], "IG OAS": ig.iloc[-2500:]}, (hy / ig).iloc[-2500:], "HY/IG", sub="Rising = decompression (quality flight)"))
    from . import config as C
    D = credit_durations(X); hyo, igo, ccco = hy * 100, ig * 100, ccc * 100
    be = pd.DataFrame({"HY": hyo / D.HY, "IG": igo / D.IG, "CCC": ccco / D.CCC}).dropna()
    cards.append(K.card("Duration-adjusted spreads: breakeven widening (OAS ÷ duration, bp per year of duration)", {k: be[k].iloc[-2500:] for k in ["CCC", "HY", "IG"]},
                        (be.HY / be.IG).iloc[-2500:], "HY ÷ IG (duration-adjusted)",
                        sub=f"How far each index's spread can widen in a year before its extra carry is gone. Durations estimated daily from each index's effective yield (see note on the CCC card)"))
    adj = (be.CCC - be.HY).dropna()
    cards.append(K.card("CCC − HY, duration-adjusted (bp per year of duration)", {"CCC est. duration (yrs)": D.CCC.iloc[-2500:], "HY duration (yrs)": D.HY.iloc[-2500:],
                        "CCC dur if maturity 3y": D.CCC_lo.iloc[-2500:], "CCC dur if maturity 5y": D.CCC_hi.iloc[-2500:]}, adj.iloc[-2500:], "CCC − HY per year of duration (bp)",
                        sub=f"Rough: CCC duration = par-bond duration at the CCC effective yield and HYG's {C.HY_WAM}y avg maturity, scaled so the same formula matches HYG's published "
                            f"{C.CREDIT_DUR['HY'][0]}y. Band shows 3y/5y maturity. Distressed bonds trade on price, so true CCC duration is likely shorter still"))
    ecr = (X.tr.HYGH / X.tr.LQDH).dropna()
    cards.append(K.card("Rate-hedged credit: HYGH vs LQDH (Treasury component stripped)", {"HYGH (rebased)": (X.tr.HYGH / X.tr.HYGH.dropna().iloc[-1500] * 100).iloc[-1500:],
                        "LQDH (rebased)": (X.tr.LQDH / X.tr.LQDH.dropna().iloc[-1500] * 100).iloc[-1500:]}, (ecr / ecr.rolling(63).mean() - 1).iloc[-1500:] * 100, "HYGH/LQDH vs 63d avg (%)",
                        sub="iShares interest-rate-hedged HY and IG ETFs: each holds the bonds and shorts Treasury futures, so returns are close to credit-only. Falling ratio = HY lagging IG on credit alone"))
    cards.append(K.card("CCC − HY, raw OAS gap", {"CCC OAS": ccc.iloc[-2500:]}, (ccc - hy).iloc[-2500:] * 100, "CCC − HY (bp)", sub="Unadjusted yield gap. Compare with the duration-adjusted card above"))
    wal, rrp, tga = X.f("WALCL") / 1e6, X.f("RRPONTSYD") / 1e3, X.f("WTREGEN") / 1e6
    nl = pd.concat([wal, rrp, tga], axis=1).ffill().dropna(); nl = (nl.iloc[:, 0] - nl.iloc[:, 1] - nl.iloc[:, 2])
    d = pd.concat([nl, X.px.SPY], axis=1).ffill().dropna().iloc[-1500:]; d.columns = ["NL", "SPY"]
    cards.append(K.simple("Fed net liquidity (WALCL − RRP − TGA, $tn) vs SPY", K.lines({"Net liquidity $tn": d.NL}, secondary={"SPY": d.SPY}), sub="Weekly Fed data ffilled"))
    cards.append(K.card("Bank reserves", {"Reserves $tn": X.f("WRESBAL").iloc[-500:] / 1e6}, X.f("WRESBAL").pct_change(4).iloc[-500:] * 100, "4wk % change", sub="Weekly"))
    fc = pd.DataFrame({"NFCI": X.f("NFCI"), "StL stress": X.f("STLFSI4")}).iloc[-800:]
    cards.append(K.simple("Financial conditions", K.lines({k: fc[k].dropna() for k in fc}, hlines=(0,)), sub="> 0 = tighter than average"))
    X.facts.update(hy=hy.iloc[-1], hy_pct=K.stats(hy.iloc[-2500:])["pct"], hy_1m=(hy.iloc[-1] - hy.iloc[-22]) * 100, nl_3m=nl.iloc[-1] - nl.iloc[-13] if len(nl) > 13 else np.nan)
    read.append(f"HY OAS <b>{hy.iloc[-1]*100:.0f}bp</b> ({(hy.iloc[-1]-hy.iloc[-22])*100:+.0f}bp 1M), {K.stats(hy.iloc[-2500:])['pct']:.0f}th pct of 10y → credit is {'priced for perfection' if K.stats(hy.iloc[-2500:])['pct'] < 15 else 'calm' if K.stats(hy.iloc[-2500:])['pct'] < 50 else 'stressed'}.")
    ap = K.stats(adj.iloc[-2500:])["pct"]; X.facts.update(ccc_adj=adj.iloc[-1], ccc_adj_pct=ap, ccc_dur=D.CCC.iloc[-1])
    read.append(f"Per year of duration: CCC {be.CCC.iloc[-1]:.0f}bp, HY {be.HY.iloc[-1]:.0f}bp, IG {be.IG.iloc[-1]:.0f}bp. "
                f"Duration-adjusted CCC − HY <b>{adj.iloc[-1]:.0f}bp</b> ({adj.iloc[-1]-adj.iloc[-22]:+.0f}bp 1M, {ap:.0f}th pct 10y; CCC duration est. {D.CCC.iloc[-1]:.1f}y, range {D.CCC_lo.iloc[-1]:.1f}–{D.CCC_hi.iloc[-1]:.1f}y).")
    read.append(f"HY/IG ratio {(hy/ig).iloc[-1]:.2f}; CCC−HY {(ccc-hy).iloc[-1]*100:.0f}bp ({(ccc-hy).diff(21).iloc[-1]*100:+.0f}bp 1M).")
    read.append(f"Net liquidity ${nl.iloc[-1]:.2f}tn ({nl.iloc[-1]-nl.iloc[-60]:+.2f}tn over ~3M). NFCI {X.f('NFCI').iloc[-1]:+.2f}.")
    return dict(key="credit", title="CREDIT & LIQUIDITY", read=read, cards=cards)

def tab_vol(X):
    cards, read = [], []
    c = X.cboe; vix = c.VIX.dropna() if "VIX" in c else X.f("VIXCLS")
    ts = pd.concat([c.VIX9D, vix, c.VIX3M], axis=1).dropna(); ts.columns = ["VIX9D", "VIX", "VIX3M"]
    inv = (ts.VIX9D / ts.VIX3M - 1) * 100
    cards.append(K.card("VIX term structure", {k: ts[k].iloc[-756:] for k in ts}, -inv.iloc[-756:], "Contango: 1 − VIX9D/VIX3M (%)", derived_kind="bars", sub="Green = normal contango (calm); red = inverted, near-term stress"))
    rv = X.ret("SPY").rolling(21).std() * np.sqrt(252) * 100
    vrp = (vix - rv.reindex(vix.index)).dropna()
    cards.append(K.card("SPX vol risk premium", {"VIX": vix.iloc[-1500:], "SPY RV21": rv.iloc[-1500:]}, vrp.iloc[-1500:], "VIX − RV21", sub="Rich premium favors short vol; negative = realized outrunning implied"))
    # cross-asset vol z-scores (1y rolling): implied where we have it, realized where we don't (labelled)
    fxr = pd.DataFrame({p: np.log(X.t(f"FX_IDC:{p}")).diff() for p in ("EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "USDCAD", "USDCHF")})
    fxrv = (fxr.rolling(21).std() * np.sqrt(252) * 100).mean(axis=1)
    hyv = X.f("BAMLH0A0HYM2").diff().rolling(21).std() * np.sqrt(252) * 100
    VV = {"Rates (MOVE)": X.t("TVC:MOVE"), "Equity (VIX)": vix, "FX (G6 realized 21d)": fxrv, "Gold (GVZ)": X.f("GVZCLS"), "Oil (OVX)": X.f("OVXCLS"), "Credit (HY OAS realized 21d)": hyv}
    Z = pd.DataFrame({k: (s - s.rolling(252, min_periods=150).mean()) / s.rolling(252, min_periods=150).std() for k, s in VV.items()}).ffill()
    X.S["volZ"] = Z.iloc[-520:]; Z = Z.iloc[-220:]
    zl = Z.iloc[-1].sort_values(ascending=False)
    side = "<div class='ss'><div class='sst'>Vol z-score (1y)</div><table>" + "".join(
        f"<tr><td class='a'>{k}</td><td class='n {'hz' if v >= 2 else 'mz' if v >= 1 else ''}'>{v:+.2f}</td></tr>" for k, v in zl.items()) + \
        "</table><div class='asof'>Which asset class is repricing uncertainty. Implied vol except FX and credit (realized — no free implied feed).</div></div>"
    cards.insert(0, K.simple("Cross-asset vol z-scores", K.lines({k: Z[k] for k in Z}, h=380, hlines=(0, 2)), side=side, sub="Each vol measure vs its own trailing 1y mean/stdev"))
    X.facts["vol_z"] = zl.round(2).to_dict()
    read.insert(0, f"Vol repricing led by <b>{zl.index[0]}</b> ({zl.iloc[0]:+.1f}σ); lowest {zl.index[-1]} ({zl.iloc[-1]:+.1f}σ). "
                   + ("<b>One asset class is stressed while others are calm → the shock is local to it; watch for spillover.</b>" if zl.iloc[0] > 2 and zl.iloc[1] < 1 else
                      "Broad vol repricing across assets." if (zl > 1).sum() >= 3 else "No broad vol stress."))
    mv = X.t("TVC:MOVE"); mvx = (mv / vix.reindex(mv.index).ffill()).dropna()
    cards.append(K.card("MOVE (rates vol) and MOVE/VIX", {"MOVE": mv.iloc[-1000:]}, mvx.iloc[-1000:], "MOVE / VIX", sub="High ratio = bond market is the stressed market"))
    cor = X.t("CBOE:COR3M")
    cards.append(K.card("Implied correlation (COR3M)", {"COR3M": cor.iloc[-1000:]}, cor.diff(21).iloc[-1000:], "21d change", sub="Rising = index hedging / macro-driven tape; falling = dispersion"))
    # linkage: PC1 share of SPX / 10Y / DXY daily moves (63d)
    L = pd.concat([X.ret("SPY"), X.y("US", "10Y").diff(), X.t("TVC:DXY").pct_change()], axis=1).dropna()
    lk = L.rolling(63).corr().groupby(level=0).apply(lambda m: np.linalg.eigvalsh(m.values)[-1] / 3 * 100 if m.shape == (3, 3) and not m.isna().any().any() else np.nan).dropna()
    cards.append(K.card("Linkage: share of SPX/10Y/DXY variance in one factor (63d)", {"Linkage %": lk.iloc[-1000:]}, (lk - 50).iloc[-1000:], "Linkage − 50",
                        sub=">60% = macro-driven tape: trade momentum, don't fade. <40% = idiosyncratic"))
    cards.append(K.simple("VVIX & SKEW", K.lines({"VVIX": c.VVIX.dropna().iloc[-1000:]}, secondary={"SKEW": c.SKEW.dropna().iloc[-1000:]}), sub="Vol-of-vol and tail pricing"))
    A = ["SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "IEF", "HYG", "GLD", "SLV", "CPER", "USO", "DBC", "DBA", "UUP", "FXE", "FXY", "XLE", "XLU", "IBIT"]
    r = X.tr[A].pct_change()
    now = r.iloc[-63:].corr(); yr = r.iloc[-504:].corr()
    cards.append(K.simple("Cross-asset correlation, 63d", K.heat(now.round(2), h=560), sub="Daily total returns"))
    cards.append(K.simple("Correlation change: 63d minus 2y", K.heat((now - yr).round(2), h=560), sub="Regime shifts in co-movement"))
    avgc = r.rolling(63).corr().groupby(level=0).apply(lambda m: (m.values[np.triu_indices(len(A), 1)]).mean() if m.shape[0] == len(A) else np.nan)
    X.S["linkage"] = lk
    X.facts.update(vix=vix.iloc[-1], vrp=vrp.iloc[-1], vix_inv=inv.iloc[-1], move=mv.iloc[-1], linkage=lk.iloc[-1], cor3m=cor.iloc[-1])
    read.append(f"Linkage <b>{lk.iloc[-1]:.0f}%</b> → {'macro-driven: trade momentum, do not fade' if lk.iloc[-1] > 60 else 'idiosyncratic: fade extremes' if lk.iloc[-1] < 40 else 'middle: no rule'}. "
                f"MOVE {mv.iloc[-1]:.0f} (MOVE/VIX {mvx.iloc[-1]:.1f}, {K.stats(mvx.iloc[-756:])['pct']:.0f}th pct 3y). COR3M {cor.iloc[-1]:.1f}.")
    read.append(f"VIX {vix.iloc[-1]:.1f} ({K.stats(vix.iloc[-756:])['pct']:.0f}th pct 3y); term structure {'INVERTED' if inv.iloc[-1] > 0 else 'in contango'} (contango {-inv.iloc[-1]:+.0f}%). VRP {vrp.iloc[-1]:+.1f} vol pts.")
    read.append(f"VVIX {c.VVIX.dropna().iloc[-1]:.0f}, SKEW {c.SKEW.dropna().iloc[-1]:.0f}.")
    return dict(key="vol", title="VOL & CORR", read=read, cards=cards)

UNIV = ["SPY", "QQQ", "IWM", "EFA", "EEM", "EWJ", "TLT", "IEF", "SHY", "TIP", "LQD", "HYG", "EMB", "GLD", "SLV", "CPER", "USO", "UNG", "DBA", "UUP", "FXE", "FXY", "FXA", "XLE", "XLU", "XLF", "SMH"]

def tab_pca(X):
    cards, read = [], []
    r = X.tr[UNIV].pct_change().dropna()
    z = (r - r.rolling(252).mean()) / r.rolling(252).std()
    W = 126; dates = r.index[-750:]; share, s3 = [], []
    for t in dates[::5]:
        blk = r.loc[:t].iloc[-W:]; blk = (blk - blk.mean()) / blk.std()
        p = PCA(5).fit(blk.values); share.append((t, *p.explained_variance_ratio_[:3]))
    sh = pd.DataFrame(share, columns=["date", "PC1", "PC2", "PC3"]).set_index("date") * 100
    cards.append(K.simple("Share of cross-asset variance by factor (126d rolling PCA)", K.lines({k: sh[k] for k in sh}, h=340),
                          sub=f"{len(UNIV)} ETFs, standardized daily returns. Rising PC1 = one macro factor dominating (correlation regime)"))
    blk = r.iloc[-W:]; blk = (blk - blk.mean()) / blk.std(); p = PCA(5).fit(blk.values)
    L = pd.DataFrame(p.components_[:3].T, index=UNIV, columns=["PC1", "PC2", "PC3"])
    for k in L:   # sign convention: SPY loads positive on PC1; TLT positive on PC2 if possible
        ref = "SPY" if k == "PC1" else ("TLT" if k == "PC2" else "UUP")
        if L.loc[ref, k] < 0: L[k] *= -1
    lab = {}
    for k in L:
        top = L[k].abs().sort_values(ascending=False).index[:4]; lab[k] = "/".join(f"{t}{'+' if L.loc[t,k]>0 else '−'}" for t in top)
    fig = make_subplots(rows=1, cols=3, subplot_titles=[f"{k}: {lab[k]}" for k in L], horizontal_spacing=0.06)
    for j, k in enumerate(L):
        s = L[k].sort_values()
        fig.add_trace(go.Bar(y=s.index, x=s.values, orientation="h", marker_color=np.where(s.values >= 0, K.GRN, K.RED), showlegend=False), row=1, col=j + 1)
    fig.update_annotations(font=dict(size=10, color=K.AMB)); K._layout(fig, 560, legend=False); fig.update_yaxes(side="left", tickfont=dict(size=9))
    cards.append(K.simple("Current factor loadings (last 126d)", fig, sub=f"Variance explained: PC1 {p.explained_variance_ratio_[0]*100:.0f}%, PC2 {p.explained_variance_ratio_[1]*100:.0f}%, PC3 {p.explained_variance_ratio_[2]*100:.0f}%"))
    # factor returns (project standardized returns on current loadings) + residual movers
    zs = z.dropna().iloc[-250:]
    fr = pd.DataFrame(zs.values @ L.values, index=zs.index, columns=L.columns).cumsum()
    cards.append(K.simple("Cumulative factor scores (current loadings, 1y)", K.lines({f"{k} ({lab[k]})": fr[k] for k in fr}, h=340), sub="Which factor has been trending"))
    recent = z.dropna().iloc[-5:]; fit = (recent.values @ L.values) @ L.values.T
    resid = pd.DataFrame(recent.values - fit, index=recent.index, columns=UNIV).sum()
    rt = resid.sort_values()
    tbl = "".join(f"<tr><td class='nm'>{t}</td><td class='n {'g' if v>0 else 'r'}'>{v:+.2f}</td></tr>" for t, v in pd.concat([rt.head(4), rt.tail(4)]).items())
    side = f"<div class='ss'><div class='sst'>Off-factor movers (5d residual z)</div><table>{tbl}</table><div class='asof'>What moved that the 3 macro factors don't explain</div></div>"
    cards[-1]["side"] = side
    X.facts.update(pc1=p.explained_variance_ratio_[0] * 100, pc1_lab=lab["PC1"], pc2_lab=lab["PC2"])
    read.append(f"PC1 explains <b>{p.explained_variance_ratio_[0]*100:.0f}%</b> of cross-asset variance ({sh.PC1.iloc[-1]-sh.PC1.iloc[-13]:+.0f}pts vs ~3M ago): "
                f"{'one factor is running the tape — diversification is thin' if p.explained_variance_ratio_[0] > 0.35 else 'moderate concentration'}. PC1 = {lab['PC1']}.")
    read.append(f"PC2 = {lab['PC2']}; PC3 = {lab['PC3']}. Biggest off-factor moves (5d): {rt.index[-1]} {rt.iloc[-1]:+.1f}, {rt.index[0]} {rt.iloc[0]:+.1f}.")
    return dict(key="pca", title="PCA / TAPE", read=read, cards=cards)

