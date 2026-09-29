import numpy as np, pandas as pd, plotly.graph_objects as go
from plotly.subplots import make_subplots
from . import kit as K

MC = "FGHJKMNQUVXZ"
FOMC = ["2026-10-28", "2026-12-09"]          # confirmed; later meetings shown by contract month until the 2027 calendar is added

def curve_regime(short, long, n=10):
    """Bull/bear steepener/flattener from the direction of both legs over n sessions; twist when legs move opposite ways."""
    d1, d2 = short.diff(n), long.diff(n); ds = d2 - d1
    lab = np.where(np.sign(d1) != np.sign(d2), np.where(ds > 0, "Steepener twist", "Flattener twist"),
          np.where(d1 < 0, np.where(ds > 0, "Bull steepener", "Bull flattener"), np.where(ds > 0, "Bear steepener", "Bear flattener")))
    return pd.Series(lab, index=short.index).where(d1.notna() & d2.notna())

RCOL = {"Bull steepener": "#3a8a2a", "Bear steepener": "#d64545", "Steepener twist": "#4ecdc4", "Bull flattener": "#4a7bd6",
        "Bear flattener": "#f28c28", "Flattener twist": "#c77dff"}

def regime_bars(spread, lab, h=360):
    """2s10s as a thin line, each day's point coloured by its 10-session regime (one legend entry per regime)."""
    d = pd.concat([spread, lab], axis=1).dropna(); d.columns = ["s", "l"]; d = d.iloc[-520:]
    fig = go.Figure(go.Scatter(x=d.index, y=d.s, mode="lines", line=dict(color="#555", width=1), name="2s10s (bp)", hoverinfo="skip"))
    for k, c in RCOL.items():
        x = d[d.l == k]
        fig.add_trace(go.Scatter(x=x.index, y=x.s, mode="markers", name=f"{k} ({(x.index >= d.index[-252]).sum()}d in last 1y)", marker=dict(color=c, size=5),
                                 hovertemplate="%{x|%Y-%m-%d}  %{y:.0f}bp  " + k + "<extra></extra>"))
    K._layout(fig, h); fig.update_xaxes(domain=[0, 0.86]); K.add_range(fig, win=12)
    fig.update_layout(hovermode="closest"); fig.update_xaxes(range=[str(d.index[0].date()), str(d.index[-1].date())], autorange=False)   # no future padding on reset
    return fig

def _strip(X, root):
    last = X.tv.index[-1] - pd.Timedelta(days=5)     # live contracts only: expired ones (kept for history) stop printing
    cols = sorted([c for c in X.tv.columns if c.split(":")[1].startswith(root) and c[-4:].isdigit() and X.tv[c].last_valid_index() is not None
                   and X.tv[c].last_valid_index() >= last], key=lambda c: (int(c[-4:]), MC.index(c[-5])))
    S = 100 - X.tv[cols].dropna(how="all")
    S.columns = [f"{c[-5]}{c[-2:]}" for c in cols]
    return S, [pd.Period(f"{c[-4:]}-{MC.index(c[-5])+1:02d}", "M") for c in cols]

def policy_12m(X):
    """Implied rate of the furthest ZQ contract in the strip (~11 months out). A fixed contract, so use it for 1–3 month changes, not long history."""
    S, months = _strip(X, "ZQ")
    return S.iloc[:, -1].dropna()


QM = {"H": 3, "M": 6, "U": 9, "Z": 12}
def sofr_moves(X, start="2023-01-01"):
    """Constant-horizon policy pricing from the SR3 strip (live + expired quarterlies). For each day: implied 3M SOFR for the period starting
    12m and 24m ahead (linear interpolation between contract start dates), and the strip extreme within 30 months, all minus EFFR, in 25bp moves."""
    cols = [c for c in X.tv.columns if c.startswith("CME:SR3") and c[-5] in QM]
    st = {c: pd.Timestamp(int(c[-4:]), QM[c[-5]], 18) for c in cols}      # ~3rd Wednesday: start of the contract's reference quarter
    cols = sorted(cols, key=lambda c: st[c]); S = (100 - X.tv[cols]).loc[start:]
    effr = X.f("DFF").reindex(S.index).ffill(); s0 = np.array([st[c].value for c in cols], dtype=float)
    out = {"12m": [], "24m": [], "ext": [], "ext_when": []}
    for t, row in S.iterrows():
        v = row.values.astype(float)
        for h in (12, 24):
            T = (t + pd.DateOffset(months=h)).value; i = np.searchsorted(s0, T) - 1
            ok = 0 <= i < len(cols) - 1 and np.isfinite(v[i]) and np.isfinite(v[i + 1])
            out[f"{h}m"].append(v[i] + (v[i + 1] - v[i]) * (T - s0[i]) / (s0[i + 1] - s0[i]) if ok else np.nan)
        win = (s0 > t.value) & (s0 <= (t + pd.DateOffset(months=30)).value) & np.isfinite(v)
        if win.sum() >= 8:
            d = v[win] - effr.loc[t]; j = np.argmax(np.abs(d)); out["ext"].append(v[win][j]); out["ext_when"].append(np.array(cols)[win][j][-5:])
        else: out["ext"].append(np.nan); out["ext_when"].append(None)
    D = pd.DataFrame({k: out[k] for k in ("12m", "24m", "ext")}, index=S.index)
    M = D.sub(effr, axis=0) / 0.25
    return M, pd.Series(out["ext_when"], index=S.index), effr

def tab_policy(X):
    cards, read = [], []
    effr, sofr, iorb = X.f("DFF"), X.f("SOFR"), X.f("IORB")
    S, months = _strip(X, "ZQ"); S = S.dropna()
    t0 = S.index[-1]; w1 = S.loc[:t0 - pd.Timedelta(days=7)].iloc[-1]; m1 = S.loc[:t0 - pd.Timedelta(days=30)].iloc[-1]; last = S.iloc[-1]
    cur = effr.iloc[-1]; lab = [str(m) for m in months]
    fig = go.Figure()
    for s, n, c, dash in ((m1, "1M ago", K.GRY, "dot"), (w1, "1W ago", K.BLU, "dash"), (last, f"Latest {t0:%m/%d}", K.AMB, "solid")):
        fig.add_trace(go.Scatter(x=lab, y=s.values, name=n, mode="lines+markers", line=dict(color=c, dash=dash, width=2 if dash == "solid" else 1.2)))
    fig.add_hline(y=cur, line=dict(color=K.WHT, dash="dash", width=0.8), annotation_text=f"EFFR {cur:.2f}", annotation_font_color=K.WHT)
    fig.add_trace(go.Bar(x=lab, y=(last - w1).values * 100, name="Δ1W bp", yaxis="y2", marker_color=np.where((last - w1).values >= 0, K.GRN, K.RED), opacity=0.55))
    fig.update_layout(yaxis2=dict(overlaying="y", title="Δ1W bp", zeroline=True, zerolinecolor="#555")); K._layout(fig, 400)
    # meeting table: late-month meetings → next-month contract is fully post-meeting
    col = dict(zip([m.strftime("%Y%m") for m in months], S.columns)); rows = []; pre = cur
    for md in FOMC:
        nxt = (pd.Period(md[:7], "M") + 1).strftime("%Y%m")
        if nxt in col:
            post = last[col[nxt]]; st = (post - pre) * 100; rows.append((md, post, st, (post - cur) * 100)); pre = post
    for m, c in zip(months, S.columns):
        if m > pd.Period(FOMC[-1][:7], "M") + 1:
            post = last[c]; st = (post - pre) * 100; rows.append((f"{m} (contract)", post, st, (post - cur) * 100)); pre = post
    tr = "".join(f"<tr><td class='nm'>{a}</td><td class='n w'>{b:.3f}</td><td class='n {'g' if c>0 else 'r'}'>{c:+.1f}</td><td class='n'>{d:+.1f}</td>"
                 f"<td class='n'>{abs(c)/25*100:.0f}% {'hike' if c>0 else 'cut'}</td></tr>" for a, b, c, d in rows)
    side = (f"<div class='ss'><div class='sst'>FOMC path (ZQ)</div><table><tr><th>Meeting</th><th>Impl</th><th>Step</th><th>Cum</th><th>25bp-eq</th></tr>{tr}</table>"
            f"<div class='asof'>TradingView CBOT ZQ, {t0:%Y-%m-%d}. Meeting steps use the next-month contract as the post-meeting rate.</div></div>")
    cards.append(K.simple("Fed funds futures implied path", fig, side=side, sub="ZQ strip · latest vs 1W vs 1M"))
    tot = (last.iloc[-1] - cur) * 100; chg = (last.iloc[-1] - w1.iloc[-1]) * 100; chgm = (last.iloc[-1] - m1.iloc[-1]) * 100
    p12 = policy_12m(X); ph = (p12 - effr.reindex(p12.index).ffill()) * 100
    cards.append(K.card(f"Hikes/cuts priced out to {months[-1]}", {f"ZQ {months[-1]} implied": p12.iloc[-190:], "EFFR": effr.reindex(p12.index).ffill().iloc[-190:]}, ph.dropna().iloc[-190:], "Implied − EFFR (bp)",
                        sub="Fixed contract, last ~9 months. Positive = hikes priced. Its 1M change is the policy leg of the regime read."))
    # constant-horizon moves priced (the "four cuts to two hikes" view, pushed further out than a calendar year)
    try:
        Mv, when, ef = sofr_moves(X); Mv = Mv.dropna(how="all")
        m24 = Mv["24m"].dropna(); lo, hi = m24.iloc[-252:].min(), m24.iloc[-252:].max(); now = m24.iloc[-1]
        cnt = lambda x: f"{abs(x):.1f} {'hike' if x > 0 else 'cut'}{'s' if abs(x) >= 1.05 else ''}"
        title = f"Fed path: 2-year pricing went from {cnt(lo if abs(lo) > abs(hi) and lo < 0 else m24.iloc[-252])} to {cnt(now)} in a year"
        fig = K.lines({"Next 12 months": Mv["12m"], "Next 24 months": Mv["24m"], "To strip peak/trough (≤30m)": Mv["ext"]}, h=420, hlines=(0,))
        fig.update_yaxes(title_text="number of 25bp moves (+ hikes / − cuts)", side="left"); K.add_range(fig, win=12)
        ch = lambda s, n: s.dropna().iloc[-1] - s.dropna().iloc[-1 - n]
        tr = "".join(f"<tr><td class='a'>{lbl}</td><td class='n w'>{Mv[k].dropna().iloc[-1]:+.1f}</td><td class='n'>{ch(Mv[k],5):+.1f}</td><td class='n'>{ch(Mv[k],21):+.1f}</td><td class='n'>{Mv[k].dropna().iloc[-1]*25:+.0f}bp</td></tr>"
                     for k, lbl in (("12m", "Next 12m"), ("24m", "Next 24m"), ("ext", "Peak/trough")))
        side = (f"<div class='ss'><div class='sst'>Moves priced</div><table><tr><th></th><th>Now</th><th>1W</th><th>1M</th><th>bp</th></tr>{tr}</table>"
                f"<div class='asof'>Extreme sits at the {when.dropna().iloc[-1]} SOFR contract. Spot = EFFR {ef.iloc[-1]:.2f}%. 12m/24m = implied 3M SOFR for the quarter starting "
                f"that far ahead (interpolated), minus EFFR, ÷ 25bp. Constant horizon, so the line doesn't shrink as a calendar year runs out.</div></div>")
        cards.append(dict(K.simple(title, fig, side=side, sub="SOFR futures (SR3) strip incl. expired contracts, TradingView. Rolling 12m and 24m horizons, plus the peak or trough of the strip within 30 months")))
        X.facts.update(moves_12m=Mv["12m"].dropna().iloc[-1], moves_24m=now, moves_ext=Mv["ext"].dropna().iloc[-1])
        read.insert(0, f"Moves priced: <b>{Mv['12m'].dropna().iloc[-1]:+.1f}</b> over 12 months, <b>{now:+.1f}</b> over 24 months ({ch(Mv['24m'],21):+.1f} in 1M); "
                       f"a year ago the 24-month view was {m24.iloc[-252]:+.1f}.")
    except Exception as e:
        read.append(f"<span class='warn'>moves-priced chart failed: {e}</span>")
    # SOFR strip
    Q, qm = _strip(X, "SR3"); Q = Q.dropna()
    q0 = Q.index[-1]; qw = Q.loc[:q0 - pd.Timedelta(days=7)].iloc[-1]; qmm = Q.loc[:q0 - pd.Timedelta(days=30)].iloc[-1]
    fig = go.Figure()
    for s, n, c, dash in ((qmm, "1M ago", K.GRY, "dot"), (qw, "1W ago", K.BLU, "dash"), (Q.iloc[-1], "Latest", "#4ecdc4", "solid")):
        fig.add_trace(go.Scatter(x=list(Q.columns), y=s.values, name=n, mode="lines+markers", line=dict(color=c, dash=dash)))
    K._layout(fig, 340)
    shape = "hike-then-plateau" if Q.iloc[-1].idxmax() not in (Q.columns[0], Q.columns[-1]) else ("still rising at the back" if Q.iloc[-1].iloc[-1] >= Q.iloc[-1].max() - 0.01 else "front-loaded")
    cards.append(K.simple("SOFR futures implied curve (SR3)", fig, sub=f"Shape: {shape}. Terminal {Q.iloc[-1].max():.2f}% ({Q.iloc[-1].idxmax()})"))
    sp = (sofr - effr).dropna() * 100
    cards.append(K.card("Funding: SOFR − EFFR", {"SOFR": sofr.iloc[-750:], "EFFR": effr.iloc[-750:], "IORB": iorb.iloc[-750:]}, sp.iloc[-750:], "SOFR − EFFR (bp)", sub="Repo pressure gauge"))
    X.facts.update(fed_priced_bp=tot, fed_priced_chg1w=chg, fed_priced_chg1m=chgm, policy_12m_chg=(p12.iloc[-1] - p12.iloc[-22]) * 100, next_step=rows[0][2] if rows else np.nan)
    read.append(f"Fed futures price <b>{tot:+.0f}bp</b> by {months[-1]} (EFFR {cur:.2f}% → {last.iloc[-1]:.2f}%). Moved <b>{chg:+.0f}bp</b> in 1W, <b>{chgm:+.0f}bp</b> in 1M → "
                f"{'hawkish repricing still building' if chg > 3 else 'repricing stalled' if abs(chg) <= 3 else 'hawkish pricing unwinding'}.")
    if rows: read.append(f"Next FOMC ({rows[0][0]}): {rows[0][2]:+.0f}bp priced ≈ {abs(rows[0][2])/25*100:.0f}% of a 25bp {'hike' if rows[0][2] > 0 else 'cut'}.")
    read.append(f"SOFR strip {shape}; terminal {Q.iloc[-1].max():.2f}% in {Q.iloc[-1].idxmax()}. Funding {'calm' if abs(sp.iloc[-1]) < 5 else 'stressed'} (SOFR−EFFR {sp.iloc[-1]:+.0f}bp).")
    return dict(key="policy", title="PRICED · POLICY", read=read, cards=cards)

def event_tells(X):
    """'The reaction, not the print': where the 2Y yield and the Ultra Bond future closed on the last CPI and payrolls days vs now."""
    rows = []
    for ev in ("CPI", "NFP"):
        past = [d for d in X.rel.get(ev, []) if d <= X.asof]
        if not past: continue
        d = past[-1]
        for sym, n, up_is in (("TVC:US02Y", "US 2Y yield", "higher rates"), ("CBOT:UB1!", "Ultra bond fut", "lower rates"), ("TVC:US10Y", "US 10Y yield", "higher rates")):
            s = X.t(sym)
            if s.empty or d not in s.index: continue
            lvl = s.loc[d]; now = s.iloc[-1]
            above = now > lvl
            rows.append((ev, f"{d:%m/%d}", n, lvl, now, "above" if above else "below", up_is if above else ("lower rates" if up_is == "higher rates" else "higher rates")))
    return rows

def tab_curve(X):
    cards, read = [], []
    ten = {"1M": X.f("DGS1MO"), "3M": X.f("DGS3MO"), "6M": X.f("DGS6MO"), "1Y": X.f("DGS1"), "2Y": X.y("US", "02Y"), "3Y": X.f("DGS3"),
           "5Y": X.y("US", "05Y"), "7Y": X.f("DGS7"), "10Y": X.y("US", "10Y"), "20Y": X.f("DGS20"), "30Y": X.y("US", "30Y")}
    Y = pd.DataFrame(ten).ffill().dropna()
    fig = go.Figure()
    for lag, n, c, dash in ((252, "1Y ago", K.GRY, "dot"), (21, "1M ago", K.BLU, "dash"), (5, "1W ago", "#c77dff", "dash"), (0, f"Latest {Y.index[-1]:%m/%d}", K.AMB, "solid")):
        fig.add_trace(go.Scatter(x=list(ten), y=Y.iloc[-1 - lag].values, name=n, mode="lines+markers", line=dict(color=c, dash=dash, width=2.2 if lag == 0 else 1.2)))
    ch = (Y.iloc[-1] - Y.iloc[-22]).values * 100
    fig.add_trace(go.Bar(x=list(ten), y=ch, name="Δ1M bp", yaxis="y2", marker_color=np.where(ch >= 0, K.RED, K.GRN), opacity=0.5))
    fig.update_layout(yaxis2=dict(overlaying="y")); K._layout(fig, 380)
    cards.append(K.simple("UST curve snapshot", fig, sub="2/5/10/30Y from TradingView (same-day), rest FRED · bars = 1M change"))
    # simple regime table: nominal, real, breakeven legs
    legs = {"Nominal 2s10s": (Y["2Y"], Y["10Y"]), "Nominal 5s30s": (Y["5Y"], Y["30Y"]), "Real 5s30s (TIPS)": (X.f("DFII5"), X.f("DFII30")),
            "Breakeven 5s10s": (X.f("T5YIE"), X.f("T10YIE"))}
    rows = []
    for n, (a, b) in legs.items():
        d = pd.concat([a, b], axis=1).ffill().dropna(); s = (d.iloc[:, 1] - d.iloc[:, 0]) * 100; lab = curve_regime(d.iloc[:, 0], d.iloc[:, 1])
        days = int((lab[::-1] != lab.iloc[-1]).values.argmax())
        rows.append((n, s.iloc[-1], s.iloc[-1] - s.iloc[-11], lab.iloc[-1], days))
    tr = "".join(f"<tr><td class='nm'>{n}</td><td class='n w'>{v:+.0f}</td><td class='n {'g' if c>0 else 'r'}'>{c:+.0f}</td><td style='color:{RCOL.get(l,'#ccc')}'>{l}</td><td class='n'>{dd}d</td></tr>" for n, v, c, l, dd in rows)
    tbl = f"<div class='tbl'><div class='tt'>Curve regimes (10-session)</div><table><tr><th>Spread</th><th>Level bp</th><th>Δ10d</th><th>Regime</th><th>In regime</th></tr>{tr}</table></div>"
    et = event_tells(X)
    if et:
        tr = "".join(f"<tr><td class='nm'>{e} {d}</td><td>{n}</td><td class='n'>{a:.3f}</td><td class='n w'>{b:.3f}</td><td>{s}</td><td class='{'r' if 'higher' in r else 'g'}'>{r}</td></tr>" for e, d, n, a, b, s, r in et)
        tbl += f"<div class='tbl'><div class='tt'>Event tells: the reaction, not the print (close on last release day vs now)</div><table><tr><th>Event</th><th>Market</th><th>Event close</th><th>Now</th><th>Now is</th><th>Pressure toward</th></tr>{tr}</table></div>"
    s210 = (Y["10Y"] - Y["2Y"]) * 100; lab = curve_regime(Y["2Y"], Y["10Y"])
    cards.append(K.card("2s10s", {"UST 2Y": Y["2Y"], "UST 10Y": Y["10Y"]}, s210, "2s10s (bp)", sub=f"Regime: {lab.iloc[-1]}"))
    cards.append(K.simple("2s10s regime history", regime_bars(s210, lab), sub="Each day coloured by its 10-session regime. Opens on 1Y; 2Y loaded (use All)"))
    s530 = (Y["30Y"] - Y["5Y"]) * 100
    cards.append(K.card("5s30s", {"UST 5Y": Y["5Y"], "UST 30Y": Y["30Y"]}, s530, "5s30s (bp)"))
    for tn, nom, real, be in (("5Y", Y["5Y"], "DFII5", "T5YIE"), ("10Y", Y["10Y"], "DFII10", "T10YIE")):
        d = pd.DataFrame({"n": X.f("DGS" + tn[:-1]), "r": X.f(real), "b": X.f(be)}).dropna().iloc[-400:]; c = d.diff(10) * 100
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(x=c.index, y=c.r, name="Real (TIPS)", marker_color="#4ecdc4", marker_line_width=0))
        fig.add_trace(go.Bar(x=c.index, y=c.b, name="Breakeven", marker_color=K.AMB, marker_line_width=0))
        fig.add_trace(go.Scatter(x=c.index, y=c.n, name="Nominal Δ", line=dict(color=K.WHT, width=1)))
        fig.add_trace(go.Scatter(x=d.index, y=d.n, name=f"{tn} yield", line=dict(color="#c77dff", width=1.1)), secondary_y=True)
        fig.update_layout(barmode="relative", bargap=0); K._layout(fig, 320)
        cards.append(K.simple(f"{tn} move = real + inflation (10-session, bp)", fig))
        read.append(f"{tn}: {c.n.iloc[-1]:+.0f}bp over 10 sessions = real {c.r.iloc[-1]:+.0f} + breakeven {c.b.iloc[-1]:+.0f} → <b>{'real-rate/policy driven' if abs(c.r.iloc[-1]) > abs(c.b.iloc[-1]) else 'inflation-expectations driven'}</b>.")
    X.facts.update(s210=s210.iloc[-1], curve_regime=lab.iloc[-1], y10=Y["10Y"].iloc[-1], y2=Y["2Y"].iloc[-1], y10_1m=(Y["10Y"].iloc[-1] - Y["10Y"].iloc[-22]) * 100,
                   real_curve=rows[2][3], event_tells=[(r[0], r[2], r[6]) for r in et])
    read.insert(0, f"10Y {Y['10Y'].iloc[-1]:.2f}% ({(Y['10Y'].iloc[-1]-Y['10Y'].iloc[-22])*100:+.0f}bp 1M). Regimes: " + "; ".join(f"{r[0]} <b>{r[3]}</b>" for r in rows) + ".")
    if et:
        hr = sum('higher' in r[6] for r in et)
        read.append(f"Event tells: {hr}/{len(et)} markets sit on the higher-rates side of their last CPI/NFP-day close → {'rates pressure intact' if hr > len(et)/2 else 'rates pressure fading'}.")
    return dict(key="curve", title="CURVE", read=read, cards=cards, table=tbl)

CC = ["US", "DE", "GB", "JP", "IT", "FR", "CA", "AU"]
def tab_global(X):
    cards, read = [], []
    T10 = pd.DataFrame({c: X.y(c, "10Y") for c in CC}).ffill().dropna(); T2 = pd.DataFrame({c: X.y(c, "02Y") for c in CC}).ffill().dropna()
    rows = []
    for c in CC:
        a, b = T10[c], T2[c]
        rows.append((c, b.iloc[-1], a.iloc[-1], (a.iloc[-1] - b.iloc[-1]) * 100, (a.iloc[-1] - a.iloc[-6]) * 100, (a.iloc[-1] - a.iloc[-22]) * 100,
                     (b.iloc[-1] - b.iloc[-22]) * 100, (a.iloc[-252:] <= a.iloc[-1]).mean() * 100))
    tr = "".join(f"<tr><td class='nm'>{c}</td><td class='n'>{b:.2f}</td><td class='n w'>{a:.2f}</td><td class='n'>{s:+.0f}</td><td class='n {'r' if w>0 else 'g'}'>{w:+.0f}</td>"
                 f"<td class='n {'r' if m>0 else 'g'}'>{m:+.0f}</td><td class='n {'r' if m2>0 else 'g'}'>{m2:+.0f}</td><td class='n {'hz' if p>=95 else ''}'>{p:.0f}</td></tr>" for c, b, a, s, w, m, m2, p in rows)
    tbl = (f"<div class='tbl'><div class='tt'>Sovereign yields (TradingView, daily)</div><table><tr><th>Ctry</th><th>2Y</th><th>10Y</th><th>2s10s bp</th><th>10Y Δ1W</th><th>10Y Δ1M</th><th>2Y Δ1M</th><th>10Y 1y %ile</th></tr>{tr}</table></div>")
    N = T10.iloc[-252:]; N = (N - N.min()) / (N.max() - N.min()) * 100
    cards.append(K.simple("10Y yields, each scaled to its own 1y range (0 = low, 100 = high)", K.lines({c: N[c] for c in CC}, h=380), sub="Long ends trading in lockstep = global duration shock, not a US story"))
    cards.append(K.simple("10Y yields (levels)", K.lines({c: T10[c] for c in CC}, h=360)))
    cards.append(K.card("BTP − Bund 10Y", {"IT 10Y": T10.IT, "DE 10Y": T10.DE}, (T10.IT - T10.DE) * 100, "IT − DE (bp)", sub="Euro-area risk thermometer"))
    cards.append(K.card("Long ends: UK 30Y and JGB 30Y", {"UK 30Y": X.y("GB", "30Y"), "JP 30Y": X.y("JP", "30Y"), "US 30Y": X.y("US", "30Y")}, (X.y("GB", "30Y") - X.y("US", "30Y")).dropna() * 100,
                        "UK30 − US30 (bp)", sub="The weakest balance sheet wears the move first"))
    peer = T10.drop(columns="US").median(axis=1)
    cards.append(K.card("US 10Y vs peer median", {"US 10Y": T10.US, "Peer median 10Y": peer}, (T10.US - peer) * 100, "US − peers (bp)", sub="Positive and rising = US-specific (fiscal/term premium) repricing"))
    m1 = pd.Series({r[0]: r[5] for r in rows}); up = (m1 > 0).sum()
    X.facts.update(global_10y_up=int(up), us_vs_peer=(T10.US.iloc[-1] - peer.iloc[-1]) * 100, us_vs_peer_1m=((T10.US - peer).iloc[-1] - (T10.US - peer).iloc[-22]) * 100)
    read.append(f"<b>{up}/8</b> 10Y yields higher over 1M; biggest move {m1.idxmax()} ({m1.max():+.0f}bp), smallest {m1.idxmin()} ({m1.min():+.0f}bp) → "
                f"{'global duration selloff' if up >= 6 else 'mixed' if up >= 3 else 'global rally'}.")
    read.append(f"US − peer median {X.facts['us_vs_peer']:+.0f}bp ({X.facts['us_vs_peer_1m']:+.0f}bp 1M): {'US-specific' if abs(X.facts['us_vs_peer_1m']) > 15 else 'moving with the world'}. "
                f"BTP−Bund {(T10.IT-T10.DE).iloc[-1]*100:.0f}bp.")
    return dict(key="global", title="GLOBAL YIELDS", read=read, cards=cards, table=tbl)
