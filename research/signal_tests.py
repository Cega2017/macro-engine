"""Quick signal checks for two calls-board rules. Research only; not part of the nightly build.
Rules are evaluated with data up to the close of day t; entry at the NEXT close (t+1); one open position at a time
(no new signal is taken until the prior holding period ends). Long history comes from 5000-bar TradingView pulls
saved in the session tool-results folder (paths below), release dates from FRED (data/releases.json)."""
import os, json, glob, numpy as np, pandas as pd

TR = "/root/.claude/projects/-home-claude/9e2d2219-4001-57f9-aa54-107fc76d81d8/tool-results"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_tv():
    S = {}
    for f in glob.glob(os.path.join(TR, "mcp-Tradingview-mcp-tv-get-ohlcv-17903977*.txt")) + glob.glob(os.path.join(TR, "mcp-Tradingview-mcp-tv-get-ohlcv-17903978*.txt")):
        j = json.load(open(f))
        if len(j.get("bars", [])) < 3000: continue
        idx, c = [], []
        for b in j["bars"]:
            ny = pd.Timestamp(b["t"], unit="s", tz="UTC").tz_convert("America/New_York")
            idx.append(pd.Timestamp((ny + pd.Timedelta(days=1)).date() if ny.hour >= 17 else ny.date())); c.append(b["c"])
        S[j["symbol"]] = pd.Series(c, index=idx).groupby(level=0).last()
    return S

def episodes(sig, horizon):
    """Signal at t → entry t+1; block until entry+horizon. Returns list of entry positions (integer index)."""
    out, i, n = [], 0, len(sig)
    v = sig.values
    while i < n - 1:
        if v[i]:
            e = i + 1
            if e + horizon < n: out.append(e)
            i = e + horizon
        else: i += 1
    return out

def main():
    S = load_tv(); print("series:", {k: (v.index[0].date(), len(v)) for k, v in S.items()})
    rel = {k: [pd.Timestamp(x) for x in v] for k, v in json.load(open(os.path.join(ROOT, "data", "releases.json"))).items()}
    cboe = pd.read_parquet(os.path.join(ROOT, "data", "cboe.parquet"))
    spy = S["AMEX:SPY"]; cal = spy.index
    D = pd.DataFrame({k: S[k].reindex(cal).ffill(limit=3) for k in ["TVC:US10Y", "TVC:US02Y", "CBOT:UB1!", "TVC:DXY", "INDEX:S5FI"]})
    D["SPY"] = spy; D["VIX"] = cboe.VIX.reindex(cal).ffill(limit=3)
    y10, y2, ub = D["TVC:US10Y"], D["TVC:US02Y"], D["CBOT:UB1!"]

    # ---------------- rule 1: duration underweight
    d10 = (y10 - y10.shift(21)) * 100
    tells = pd.Series(np.nan, index=cal)
    evs = {k: sorted(d for d in v if d in cal) for k, v in rel.items()}
    for t in cal:
        n = h = 0
        for k in ("CPI", "NFP"):
            past = [d for d in evs[k] if d <= t]
            if not past: continue
            d = past[-1]
            for s, up_is_higher in ((y2, True), (ub, False), (y10, True)):
                a, b = s.get(d), s.get(t)
                if pd.isna(a) or pd.isna(b): continue
                n += 1; above = b > a; h += int(above if up_is_higher else not above)
        tells[t] = h / n if n else np.nan
    L = pd.concat([spy.pct_change(), y10.diff(), D["TVC:DXY"].pct_change()], axis=1).dropna()
    lk = L.rolling(63).corr().groupby(level=0).apply(lambda m: np.linalg.eigvalsh(m.values)[-1] / 3 * 100 if m.shape == (3, 3) and not m.isna().any().any() else np.nan).reindex(cal)
    valid = d10.notna() & tells.notna() & lk.notna()
    rules = {"FULL RULE (10Y +15bp 1M & tells>50% & linkage>55%)": (d10 > 15) & (tells > 0.5) & (lk > 55),
             "trend only (10Y +15bp 1M)": d10 > 15}
    print(f"\n=== DURATION UNDERWEIGHT · sample {cal[valid.values.argmax()].date()} → {cal[-1].date()} · entry next close, win = 10Y higher at horizon ===")
    for h in (10, 21):
        fwd = (y10.shift(-(h + 1)) - y10.shift(-1)) * 100     # from entry close (t+1) to t+1+h, indexed at signal day t
        base = fwd[valid].dropna()
        print(f"\n-- horizon {h} sessions · baseline (every day): hit {(base > 0).mean()*100:.0f}%  mean {base.mean():+.1f}bp  n={len(base)}")
        for name, sig in rules.items():
            sig = (sig & valid).reindex(cal).fillna(False)
            ent = episodes(sig, h); r = pd.Series([fwd.iloc[e - 1] for e in ent], index=[cal[e] for e in ent]).dropna()
            print(f"   {name}: episodes {len(r)}  hit {(r > 0).mean()*100:.0f}%  mean {r.mean():+.1f}bp  median {r.median():+.1f}bp  worst {r.min():+.0f}bp")
            if "FULL" in name and h == 21:
                full21 = r
    print("\nFull-rule episodes by year (21-session outcome, bp):")
    g = full21.groupby(full21.index.year)
    print(pd.DataFrame({"n": g.size(), "hits": g.apply(lambda x: int((x > 0).sum())), "mean_bp": g.mean().round(1)}).to_string())

    # ---------------- rule 2: SPY protection
    pct = spy.rolling(252).apply(lambda a: (a <= a[-1]).mean() * 100, raw=True)
    vz = (D.VIX - D.VIX.rolling(252, min_periods=150).mean()) / D.VIX.rolling(252, min_periods=150).std()
    a50 = D["INDEX:S5FI"]; H = 45
    valid2 = pct.notna() & a50.notna() & vz.notna()
    mins = pd.Series([spy.iloc[i + 2:i + 2 + H].min() if i + 1 + H < len(spy) else np.nan for i in range(len(spy))], index=cal)
    dd = mins / spy.shift(-1) - 1               # worst close within 45 sessions after entry (t+1), vs entry close
    fr = spy.shift(-(H + 1)) / spy.shift(-1) - 1
    base = dd[valid2].dropna()
    print(f"\n=== SPY PROTECTION · sample {cal[valid2.values.argmax()].date()} → {cal[-1].date()} · entry next close, hit = SPY falls ≥5% (close) within {H} sessions ===")
    print(f"baseline (every day): hit {(base <= -0.05).mean()*100:.0f}%  mean 45d return {fr[valid2].mean()*100:+.1f}%  n={len(base)}")
    rules2 = {"FULL RULE (SPY>90th pct 1y & breadth<40% & VIX z<0.5)": (pct > 90) & (a50 < 40) & (vz < 0.5),
              "SPY>90th pct & VIX z<0.5 (no breadth)": (pct > 90) & (vz < 0.5),
              "SPY>90th pct only": pct > 90}
    for name, sig in rules2.items():
        sig = (sig & valid2).fillna(False)
        ent = episodes(sig, H); idx = [cal[e - 1] for e in ent]
        r = dd.reindex(idx).dropna(); f = fr.reindex(idx).dropna()
        print(f"   {name}: episodes {len(r)}  hit {(r <= -0.05).mean()*100:.0f}%  median worst dd {r.median()*100:+.1f}%  mean 45d ret {f.mean()*100:+.1f}%")
        if "FULL" in name: full2 = pd.DataFrame({"worst_dd_%": (r * 100).round(1), "fwd45_%": (f * 100).round(1)})
    print("\nFull-rule protection episodes (signal date):"); print(full2.to_string())

if __name__ == "__main__": main()
