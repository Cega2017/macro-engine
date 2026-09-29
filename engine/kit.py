"""Bloomberg-style chart kit. Every card = Plotly figure (black, amber/white, green/red fills) + HTML summary box."""
import json, re, numpy as np, pandas as pd, plotly.graph_objects as go
from plotly.subplots import make_subplots

BG, GRID, AMB, WHT, YEL, GRN, RED, BLU, GRY = "#000000", "#2a2a2a", "#f28c28", "#ffffff", "#e0b64a", "#3a8a2a", "#a82626", "#5fa8ff", "#8a8a8a"
PAL = [WHT, AMB, BLU, "#9be15d", "#4ecdc4", "#c77dff", "#ff6b6b", "#ffd166"]
FONT = dict(family="Menlo, Consolas, 'DejaVu Sans Mono', monospace", size=11, color="#d0d0d0")
_uid = [0]

def _thin(s, keep=504):
    """Daily for the last ~2y, weekly before that (keeps files small; stats use full data)."""
    s = s.dropna()
    if len(s) <= keep * 1.5 or not isinstance(s.index, pd.DatetimeIndex): return s
    old = s.iloc[:-keep].resample("W-FRI").last().dropna()
    return pd.concat([old, s.iloc[-keep:]])

def _layout(fig, h=420, legend=True):
    fig.update_layout(paper_bgcolor=BG, plot_bgcolor=BG, font=FONT, height=h, margin=dict(l=10, r=60, t=28, b=24),
                      hovermode="x unified", showlegend=legend,
                      legend=dict(orientation="h", y=1.0, yanchor="bottom", x=0, bgcolor="rgba(0,0,0,0)", font=dict(size=10)),
                      hoverlabel=dict(bgcolor="#111", font=FONT))
    fig.update_xaxes(gridcolor=GRID, griddash="dot", zeroline=False, linecolor="#444", showspikes=True, spikecolor="#666", spikethickness=1)
    fig.update_yaxes(gridcolor=GRID, griddash="dot", zeroline=False, linecolor="#444")
    fig.for_each_yaxis(lambda ax: ax.update(side="left", showgrid=False) if ax.overlaying else ax.update(side=ax.side or "right"))
    return fig

_FL = re.compile(r"(-?\d+\.\d{5,})")
RANGE = dict(buttons=[dict(count=1, label="1M", step="month", stepmode="backward"), dict(count=3, label="3M", step="month", stepmode="backward"),
                      dict(count=6, label="6M", step="month", stepmode="backward"), dict(count=1, label="YTD", step="year", stepmode="todate"),
                      dict(count=1, label="1Y", step="year", stepmode="backward"), dict(count=3, label="3Y", step="year", stepmode="backward"), dict(step="all", label="All")],
             bgcolor="#1a1a1a", activecolor="#f28c28", font=dict(color="#f28c28", size=10), x=0, y=1.0, yanchor="bottom")
def add_range(fig, axis="xaxis", win="all"):
    """Lookback buttons are drawn by the page (anchored to the last data point, applied to every date axis), not by Plotly's rangeselector."""
    fig.update_layout(meta=dict(range=True, win=win))
    return fig

def fig_json(fig):
    j = fig.to_json()
    j = re.sub(r"T00:00:00(\.0+)?", "", j)
    def r(m):
        v = float(m.group(1)); t = f"{v:.6g}" if abs(v) >= 1000 else f"{v:.4f}".rstrip("0").rstrip(".")
        return t if t not in ("-0", "") else "0"
    return _FL.sub(r, j)

# ---------------- stats
def stats(s):
    s = s.dropna()
    if len(s) < 5: return {}
    m, sd, last = s.mean(), s.std(), s.iloc[-1]
    return dict(last=last, mean=m, median=s.median(), sd=sd, z=(last - m) / sd if sd else np.nan,
                pct=(s <= last).mean() * 100, hi=s.max(), hi_d=s.idxmax(), lo=s.min(), lo_d=s.idxmin(), asof=s.index[-1])

def summary_html(s, title="Spread Summary", fmt="{:.2f}"):
    st = stats(s)
    if not st: return ""
    rows = [("Last", st["last"], 1), ("Mean", st["mean"], 1), ("Off Avg", st["last"] - st["mean"], 1), ("Median", st["median"], 0),
            ("StDev", st["sd"], 0), ("StDev from Mean", st["z"], 0), ("Percentile", st["pct"], 0),
            (f"High {st['hi_d']:%Y-%m-%d}", st["hi"], 0), (f"Low {st['lo_d']:%Y-%m-%d}", st["lo"], 0)]
    tr = "".join(f"<tr><td class='{'w' if w else 'a'}'>{k}</td><td class='n'>{fmt.format(v)}</td></tr>" for k, v, w in rows)
    return f"<div class='ss'><div class='sst'>{title}</div><table>{tr}</table><div class='asof'>as of {st['asof']:%Y-%m-%d}</div></div>"

# ---------------- the core card: main pane + derived pane (+ histogram) + summary
def card(title, main, derived=None, derived_title="Spread", note="", units="", h=520, main_log=False, fill_main=False,
         derived_kind="area", hist=True, sub=""):
    """main: dict name->Series (plotted top). derived: Series (plotted bottom w/ green/red fill + hist + summary)."""
    _uid[0] += 1; cid = f"c{_uid[0]}"
    rows = 2 if derived is not None else 1
    fig = make_subplots(rows=rows, cols=2 if (derived is not None and hist) else 1,
                        column_widths=[0.86, 0.14] if (derived is not None and hist) else None,
                        row_heights=[0.55, 0.45] if rows == 2 else None, shared_xaxes=False,
                        horizontal_spacing=0.05, vertical_spacing=0.08,
                        specs=[[{}, {}], [{}, {}]] if (derived is not None and hist) else None)
    for i, (n, s) in enumerate(main.items()):
        s = _thin(s)
        if s.empty: continue
        fig.add_trace(go.Scatter(x=s.index, y=s.values, name=f"{n}  {s.iloc[-1]:,.2f}", line=dict(color=PAL[i % len(PAL)], width=1.3),
                                 fill="tozeroy" if (fill_main and i == 0) else None, fillcolor="rgba(95,168,255,0.12)"), row=1, col=1)
    s0 = list(main.values())[0].dropna()
    if len(s0) > 260 and derived is not None:
        e21 = _thin(s0.ewm(span=21, adjust=False).mean())
        fig.add_trace(go.Scatter(x=e21.index, y=e21.values, name=f"21d EMA ({list(main)[0]})", line=dict(color="#4ecdc4", width=1, dash="dot")), row=1, col=1)
        for w, col in ((50, "#9be15d"), (200, "#ff6b6b")):
            m = _thin(s0.rolling(w).mean())
            fig.add_trace(go.Scatter(x=m.index, y=m.values, name=f"{w}d avg ({list(main)[0]})", line=dict(color=col, width=1, dash="dot"), visible="legendonly"), row=1, col=1)
    if main_log: fig.update_yaxes(type="log", row=1, col=1)
    if derived is not None:
        dfull = derived.dropna(); d = _thin(dfull) if derived_kind != "bars" else dfull.iloc[-756:]
        if derived_kind == "bars":
            fig.add_trace(go.Bar(x=d.index, y=d.values, marker_color=np.where(d.values >= 0, GRN, RED), name=derived_title,
                                 marker_line_width=0, showlegend=False), row=2, col=1)
        else:
            pos, neg = d.clip(lower=0), d.clip(upper=0)
            fig.add_trace(go.Scatter(x=d.index, y=pos, fill="tozeroy", line=dict(width=0), fillcolor="rgba(58,138,42,0.85)", showlegend=False, hoverinfo="skip", legendgroup="drv"), row=2, col=1)
            fig.add_trace(go.Scatter(x=d.index, y=neg, fill="tozeroy", line=dict(width=0), fillcolor="rgba(168,38,38,0.85)", showlegend=False, hoverinfo="skip", legendgroup="drv"), row=2, col=1)
            fig.add_trace(go.Scatter(x=d.index, y=d.values, line=dict(color=YEL, width=1), name=f"{derived_title}  {d.iloc[-1]:,.2f}", legendgroup="drv"), row=2, col=1)
        fig.add_hline(y=d.iloc[-1], line=dict(color=YEL, width=0.8), row=2, col=1)
        ax_ = "3" if hist else "2"
        fig.add_annotation(x=1, xref=f"x{ax_} domain", y=d.iloc[-1], yref=f"y{ax_}", text=f"{d.iloc[-1]:,.2f}",
                           showarrow=False, bgcolor=YEL, font=dict(color="black", size=10), xanchor="left")
        if hist:
            d = dfull if derived_kind != "bars" else d
            cnt, edges = np.histogram(d.values, bins=30); ctr = (edges[:-1] + edges[1:]) / 2
            fig.add_trace(go.Bar(y=ctr, x=cnt, orientation="h", marker_color=np.where(ctr >= 0, GRN, RED), showlegend=False,
                                 hoverinfo="skip", marker_line_width=0), row=2, col=2)
            mu, sd = d.mean(), d.std(); yy = np.linspace(d.min(), d.max(), 100)
            fig.add_trace(go.Scatter(y=yy, x=len(d) * (edges[1] - edges[0]) * np.exp(-(yy - mu) ** 2 / (2 * sd ** 2)) / (sd * np.sqrt(2 * np.pi)),
                                     line=dict(color=YEL, width=1), showlegend=False, hoverinfo="skip"), row=2, col=2)
            fig.add_hline(y=d.iloc[-1], line=dict(color=YEL, width=0.8), row=2, col=2)
            fig.update_yaxes(showticklabels=False, row=2, col=2)
            fig.update_xaxes(showticklabels=False, row=2, col=2)
            fig.update_yaxes(matches=None, showgrid=False, row=2, col=2); fig.update_yaxes(range=[d.min(), d.max()], row=2, col=2)   # full-history distribution; yellow line marks today
            fig.add_annotation(text="full-history<br>distribution", xref="x4 domain", yref="y4 domain", x=0.5, y=1.02, showarrow=False, font=dict(size=9, color=GRY), yanchor="bottom")
            fig.update_xaxes(visible=False, row=1, col=2); fig.update_yaxes(visible=False, row=1, col=2)
        fig.update_xaxes(matches="x", row=2, col=1)
        fig.add_annotation(text=derived_title, xref="paper", yref="paper", x=0, y=0.44, showarrow=False, font=dict(color=YEL, size=11), xanchor="left")
    _layout(fig, h)
    if isinstance(list(main.values())[0].index, pd.DatetimeIndex): add_range(fig, "xaxis")
    side = summary_html(derived, "Spread Summary") if derived is not None else summary_html(list(main.values())[0], "Summary")
    return dict(id=cid, title=title, sub=sub, note=note, fig=fig_json(fig), side=side)

def simple(title, fig, note="", side="", sub="", h=None):
    _uid[0] += 1
    if h: fig.update_layout(height=h)
    return dict(id=f"c{_uid[0]}", title=title, sub=sub, note=note, fig=fig_json(fig), side=side)

def lines(series: dict, h=380, log=False, secondary=None, hlines=(), bars=None):
    fig = make_subplots(specs=[[{"secondary_y": bool(secondary)}]])
    for i, (n, s) in enumerate(series.items()):
        s = _thin(s)
        if s.empty: continue
        fig.add_trace(go.Scatter(x=s.index, y=s.values, name=f"{n}  {s.iloc[-1]:,.2f}", line=dict(color=PAL[i % len(PAL)], width=1.3)), secondary_y=False)
    if secondary:
        for j, (n, s) in enumerate(secondary.items()):
            s = s.dropna()
            fig.add_trace(go.Scatter(x=s.index, y=s.values, name=f"{n} (L)  {s.iloc[-1]:,.2f}", line=dict(color=PAL[(j + 3) % len(PAL)], width=1.1, dash="dot")), secondary_y=True)
        fig.update_yaxes(side="left", secondary_y=True, showgrid=False)
    for y in hlines: fig.add_hline(y=y, line=dict(color="#777", width=0.7, dash="dash"))
    if log: fig.update_yaxes(type="log", secondary_y=False)
    _layout(fig, h)
    first = next(iter(series.values()))
    if isinstance(first.index, pd.DatetimeIndex): add_range(fig)
    return fig

def signed_bars(s, name="", h=300, overlay=None):
    s = s.dropna(); fig = make_subplots(specs=[[{"secondary_y": overlay is not None}]])
    fig.add_trace(go.Bar(x=s.index, y=s.values, marker_color=np.where(s.values >= 0, GRN, RED), marker_line_width=0, name=f"{name}  {s.iloc[-1]:,.2f}"))
    if overlay is not None:
        o = overlay.dropna(); fig.add_trace(go.Scatter(x=o.index, y=o.values, line=dict(color=WHT, width=1.1), name=f"{o.name}  {o.iloc[-1]:,.2f}"), secondary_y=True)
        fig.update_yaxes(side="left", secondary_y=True, showgrid=False)
    _layout(fig, h); add_range(fig)
    return fig

def scatter_ols(x, y, xname, yname, h=380, label_last=True):
    d = pd.concat([x, y], axis=1).dropna(); d.columns = ["x", "y"]
    b, a = np.polyfit(d.x, d.y, 1); r2 = d.x.corr(d.y) ** 2
    fig = go.Figure(go.Scatter(x=d.x, y=d.y, mode="markers", marker=dict(color=BLU, size=5, opacity=0.5), name="history",
                               text=[f"{i:%Y-%m-%d}" for i in d.index], hovertemplate="%{text}<br>x %{x:.2f}<br>y %{y:.2f}"))
    xx = np.linspace(d.x.min(), d.x.max(), 50)
    fig.add_trace(go.Scatter(x=xx, y=a + b * xx, line=dict(color=AMB, width=1.5), name=f"OLS  b={b:.2f}  R²={r2:.2f}"))
    fig.add_trace(go.Scatter(x=[d.x.iloc[-1]], y=[d.y.iloc[-1]], mode="markers", marker=dict(color=YEL, size=13, symbol="diamond", line=dict(color="black", width=1)), name=f"latest {d.index[-1]:%m/%d}"))
    fig.update_layout(xaxis_title=xname, yaxis_title=yname, hovermode="closest")
    return _layout(fig, h)

def heat(df, h=420, zmid=0, fmt=".2f", colorscale=None):
    cs = colorscale or [[0, RED], [0.5, "#111"], [1, GRN]]
    fig = go.Figure(go.Heatmap(z=df.values, x=[str(c) for c in df.columns], y=[str(i) for i in df.index], colorscale=cs, zmid=zmid,
                               text=np.vectorize(lambda v: "" if pd.isna(v) else format(v, fmt))(df.values), texttemplate="%{text}",
                               textfont=dict(size=10), showscale=False, hoverongaps=False))
    fig.update_layout(hovermode="closest"); _layout(fig, h, legend=False)
    fig.update_yaxes(autorange="reversed", side="left"); fig.update_layout(margin=dict(l=150, r=10, t=10, b=30))
    return fig

# ---------------- dashboard table (the MMH-style header) + alerts
def _trend(s):
    """Trend regime: price vs 50d and 200d SMA with 50d slope. Returns label, days in state."""
    s = s.dropna()
    if len(s) < 220: return "n/a", 0
    m50, m200 = s.rolling(50).mean(), s.rolling(200).mean()
    up = (s > m50) & (m50 > m200) & (m50.diff(10) > 0); dn = (s < m50) & (m50 < m200) & (m50.diff(10) < 0)
    lab = pd.Series(np.where(up, "UP", np.where(dn, "DOWN", "MIXED")), index=s.index)
    cur = lab.iloc[-1]; days = int((lab[::-1] != cur).values.argmax()) if (lab != cur).any() else len(lab)
    return cur, days

def _trend21(s):
    """Short-term trend: price vs 21d EMA with the EMA's 5-day slope."""
    s = s.dropna()
    if len(s) < 60: return "n/a", 0
    e = s.ewm(span=21, adjust=False).mean(); sl = e.diff(5)
    lab = pd.Series(np.where((s > e) & (sl > 0), "UP", np.where((s < e) & (sl < 0), "DOWN", "MIXED")), index=s.index)
    cur = lab.iloc[-1]; days = int((lab[::-1] != cur).values.argmax()) if (lab != cur).any() else len(lab)
    return cur, days

def spark(s, n=63, w=90, h=18):
    """Inline SVG sparkline of the last n points (green if up over the window, red if down)."""
    s = s.dropna().iloc[-n:]
    if len(s) < 5: return ""
    lo, hi = s.min(), s.max(); rng = (hi - lo) or 1
    pts = " ".join(f"{i*(w-2)/(len(s)-1)+1:.1f},{h-1-(v-lo)/rng*(h-2):.1f}" for i, v in enumerate(s.values))
    c = "#4caf50" if s.iloc[-1] >= s.iloc[0] else "#e05252"
    return f"<svg width='{w}' height='{h}' viewBox='0 0 {w} {h}'><polyline points='{pts}' fill='none' stroke='{c}' stroke-width='1.2'/></svg>"

def row_stats(name, s, kind="pct", stale_days=5, window_z=756):
    """kind 'pct' for prices, 'bp' for yields/spreads (changes in bp), 'lvl' for indices like VIX (pt changes)."""
    s = s.dropna()
    if s.empty: return None
    last = s.iloc[-1]; asof = s.index[-1]
    def ch(n):
        if len(s) <= n: return np.nan
        prev = s.iloc[-1 - n]
        return (last / prev - 1) * 100 if kind == "pct" else (last - prev) * (100 if kind == "bp" else 1)
    ytd_base = s[s.index < pd.Timestamp(asof.year, 1, 1)]
    ytd = np.nan if ytd_base.empty else ((last / ytd_base.iloc[-1] - 1) * 100 if kind == "pct" else (last - ytd_base.iloc[-1]) * (100 if kind == "bp" else 1))
    d5 = (s.pct_change(5) if kind == "pct" else s.diff(5)).dropna().iloc[-window_z:]
    z5 = (d5.iloc[-1] - d5.mean()) / d5.std() if len(d5) > 50 else np.nan
    y1 = s.iloc[-252:]; pct = (y1 <= last).mean() * 100
    tr, days = _trend(s); t21, d21 = _trend21(s)
    bdays = np.busday_count(asof.date(), pd.Timestamp.now().date())
    return dict(name=name, last=last, d1=ch(1), d5=ch(5), m1=ch(21), ytd=ytd, z5=z5, pct=pct, trend=tr, days=days, t21=t21, d21=d21, spark=spark(s),
                stale=bdays > stale_days, asof=asof, kind=kind)

def table_html(rows, title=""):
    unit = {"pct": "%", "bp": "bp", "lvl": "", "bpl": "bp"}
    def c(v, k, zc=False):
        if v is None or pd.isna(v): return "<td class='n'>–</td>"
        cls = "g" if v > 0 else ("r" if v < 0 else "")
        if zc: cls = "hz" if abs(v) >= 2 else ("mz" if abs(v) >= 1.5 else "")
        return f"<td class='n {cls}'>{(format(v, '+.0f') if (k in ('bp', 'bpl') and not zc) else format(v, '+.2f'))}{'' if zc else unit[k]}</td>"
    body = ""
    for r in [r for r in rows if r]:
        k = r["kind"]; pc = r["pct"]; pcl = "hz" if pc >= 95 or pc <= 5 else ""
        tcl = {"UP": "g", "DOWN": "r"}.get(r["trend"], ""); tc2 = {"UP": "g", "DOWN": "r"}.get(r.get("t21"), "")
        st = f" <span class='stale'>STALE {r['asof']:%m/%d}</span>" if r["stale"] else ""
        body += (f"<tr><td class='nm'>{r['name']}{st}</td><td class='n w'>{r['last']:,.2f}</td><td class='sp'>{r.get('spark','')}</td>{c(r['d1'],k)}{c(r['d5'],k)}{c(r['m1'],k)}{c(r['ytd'],k)}"
                 f"{c(r['z5'],k,True)}<td class='n {pcl}'>{pc:.0f}</td><td><span class='t21 {tc2}'>{r.get('t21')} d{r.get('d21')}</span><span class='t50 {tcl}'>{r['trend']} d{r['days']}</span></td></tr>")
    return (f"<div class='tbl'><div class='tt'>{title}</div><table><tr><th>Series</th><th>Last</th><th style='text-align:center'>3M</th><th>1D</th><th>5D</th><th>1M</th><th>YTD</th>"
            f"<th>5D z</th><th>1Y %ile</th><th><span class='t21'>Trend 21 EMA</span><span class='t50'>Trend 50/200</span></th></tr>{body}</table></div>")

def alerts(rows):
    out = []
    for r in [r for r in rows if r]:
        if not pd.isna(r["z5"]) and abs(r["z5"]) >= 2: out.append(f"<b>{r['name']}</b> 5-day move {r['z5']:+.1f}σ vs 3y")
        if r["pct"] >= 97: out.append(f"<b>{r['name']}</b> at {r['pct']:.0f}th pct of 1y range")
        if r["pct"] <= 3: out.append(f"<b>{r['name']}</b> at {r['pct']:.0f}th pct of 1y range (1y low zone)")
        if r["days"] <= 3 and r["trend"] != "n/a": out.append(f"<b>{r['name']}</b> trend flipped to {r['trend']} ({r['days']}d ago)")
        if r["stale"]: out.append(f"<b>{r['name']}</b> STALE (last {r['asof']:%Y-%m-%d})")
    return out
