"""THESIS tab: falsifiable theses (Capital Flows style) checked against the data every build.
Edit THESES below. Each condition is (label, fn(X) -> (met: bool, shown_value: str)). Any KILL met → FALSIFIED."""
import numpy as np, pandas as pd
from . import kit as K
from .tabs_rates import curve_regime

def _chg(s, n): s = s.dropna(); return s.iloc[-1] - s.iloc[-1 - n]
def _ratio(X, a, b): return (X.px[a] / X.px[b]).dropna()

def c_real_up(X):       v = _chg(X.f("DFII10"), 21) * 100; return v > 0, f"{v:+.0f}bp 21d"
def c_mega_selling(X):  r = _ratio(X, "SPY", "RSP"); return r.iloc[-1] <= r.iloc[-21:].min() * 1.001, f"SPY/RSP {r.iloc[-1]/r.iloc[-21:].max()*100-100:+.1f}% vs 21d high"
def c_vix_front(X):     c = X.cboe; v = c.VIX9D.dropna().iloc[-1] / c.VIX3M.dropna().iloc[-1]; return v > 0.95, f"{v:.2f}"
def c_linkage(X):       v = X.facts.get("linkage", np.nan); return v > 60, f"{v:.0f}%"
def k_broadening(X):
    a50 = X.t("INDEX:S5FI").iloc[-1]; spy = X.px.SPY; hi = spy.iloc[-1] >= spy.iloc[-252:].max() * 0.999
    return bool(hi and a50 > 50), f"SPY {'at' if hi else 'below'} 1y high, {a50:.0f}% > 50d"
def k_rates_relief(X):
    v = _chg(X.f("DFII10"), 21) * 100; p = X.facts.get("fed_priced_bp", np.nan); return (v < -25) and (p < 50), f"real {v:+.0f}bp, priced {p:+.0f}bp"

def c_oil_up(X):        v = _chg(X.t("NYMEX:CL1!"), 21); return v > 0, f"WTI {v:+.1f} 21d"
def c_be_high(X):       v = X.f("T5YIE").iloc[-1]; return v > 2.40, f"{v:.2f}%"
def c_sb_pos(X):        v = X.facts.get("sb_corr", np.nan); return v > 0.3, f"{v:+.2f}"
def c_xle_lead(X):      r = _ratio(X, "XLE", "SPY"); v = (r.iloc[-1] / r.iloc[-22] - 1) * 100; return v > 0, f"{v:+.1f}% 21d"
def k_oil_fail(X):
    cl = X.t("NYMEX:CL1!"); dd = (cl.iloc[-1] / cl.iloc[-21:].max() - 1) * 100; be = X.f("T5YIE").iloc[-1]
    return dd < -10 and be < 2.25, f"WTI {dd:+.0f}% off 21d high, 5Y BE {be:.2f}"
def k_equity_reject(X):
    r = _ratio(X, "XLE", "SPY"); cl = X.t("NYMEX:CL1!"); return (r.iloc[-1] <= r.iloc[-21:].min() * 1.001) and _chg(cl, 21) > 0, "XLE/SPY at 21d low while WTI up" if (r.iloc[-1] <= r.iloc[-21:].min() * 1.001) else "no"

def c_hy_wide(X):       v = X.f("BAMLH0A0HYM2").iloc[-1] * 100; return v > 350, f"{v:.0f}bp"
def c_recession(X):     v = X.facts.get("regime", ""); return v == "Slowdown", v
def c_bull_steep(X):    v = X.facts.get("curve_regime", ""); return v == "Bull steepener", v
def c_dovish(X):        v = X.facts.get("fed_priced_chg1m", np.nan); return v < -20, f"{v:+.0f}bp 1M"
def k_growth_ok(X):     g = X.facts.get("g", np.nan); hy = X.f("BAMLH0A0HYM2").iloc[-1] * 100; return g > 0 and hy < 300, f"growth {g:+.2f}, HY {hy:.0f}bp"
def k_longend(X):
    d = pd.concat([X.y("US", "05Y"), X.y("US", "30Y")], axis=1).ffill().dropna(); lab = curve_regime(d.iloc[:, 0], d.iloc[:, 1]).iloc[-1]; p = X.facts.get("fed_priced_chg1m", np.nan)
    return lab == "Bear steepener" and abs(p) < 10, f"5s30s {lab}, policy {p:+.0f}bp 1M"

THESES = [
 dict(id="T1", title="The rate shock reaches the multiple", horizon="Cyclical · 6–10 weeks", status_note="DRAFT",
      hypothesis="Real-rate-led 10Y selloff with hikes priced meets an index held up by a narrow top at low VIX; the multiple compresses and index insurance reprices.",
      chain=["Hikes priced ↑", "10Y real yield ↑", "Mega-caps join the selling", "Front-end vol bid"],
      expression="SPY 2–3M put spreads only once VIX9D/VIX3M > 1 (front-end stress confirms); the near-highs/cheap-vol setup alone did not pay in the 2007–26 test.",
      confirm=[("10Y real yield rising (21d)", c_real_up), ("SPY/RSP at 21d low (mega-caps selling)", c_mega_selling), ("VIX9D/VIX3M > 0.95", c_vix_front), ("Linkage > 60%", c_linkage)],
      kill=[("Broadening: SPY at 1y high with >50% of stocks above 50d", k_broadening), ("Rates relief: real 10Y −25bp in 21d and < +50bp priced", k_rates_relief)]),
 dict(id="T2", title="Oil is the inflation impulse; stocks and bonds won't hedge each other", horizon="Cyclical · 1–3 months", status_note="DRAFT",
      hypothesis="Crude drives breakevens and the front end; equities fall with oil and bonds stop hedging.",
      chain=["WTI ↑", "5Y breakeven ↑", "Front end reprices hikes", "Stock–bond correlation stays positive"],
      expression="Long XLE vs SPY; underweight duration vs cash.",
      confirm=[("WTI up over 21d", c_oil_up), ("5Y breakeven > 2.40%", c_be_high), ("Stock–bond corr (63d) > 0.3", c_sb_pos), ("XLE outperforming SPY (21d)", c_xle_lead)],
      kill=[("Transmission failed: WTI −10% off high and 5Y BE < 2.25%", k_oil_fail), ("Equities reject the oil move: XLE/SPY at 21d low while WTI up", k_equity_reject)]),
 dict(id="T3", title="Hikes into falling growth: bear flattener rolls into bull steepener", horizon="Structural · 3–6 months", status_note="DRAFT",
      hypothesis="The Fed prices hikes while growth momentum falls; credit cracks first, growth breaks, the front end rallies.",
      chain=["Hikes priced on falling growth", "Credit reprices (HY > 350bp)", "Tape regime → Slowdown", "2s10s → bull steepener"],
      expression="2s10s steepener (ZT vs ZN) at 25%; add only at extremes.",
      confirm=[("HY OAS > 350bp", c_hy_wide), ("Tape regime = Slowdown", c_recession), ("2s10s regime = bull steepener", c_bull_steep), ("Fed pricing −20bp in 1M", c_dovish)],
      kill=[("Economy absorbs hikes: growth > 0 and HY < 300bp", k_growth_ok), ("Long-end story instead: 5s30s bear steepening with policy flat", k_longend)]),
]


# ---- KRE/KBWB pair watch (Driver X-Ray study, 2026-09-26). Tested rule: 20-session 2s10s regime (slope change beyond ±5bp,
# bull/bear by 10Y direction) -> next-20d pair return, 2022+: bull steepen +1.6% (76% up), flat +0.3%/+1.1% (60d lookback),
# bull flatten ~0, bear steepen mixed (+0.6% on 20d lookback, -0.4% on 60d), bear flatten -0.2% to -0.4% (coin flip). Thin samples (4-18 indep. periods).
PAIR_STATS = {"Bull steepen": "+1.6% next 20d, 76% up", "Flat": "+0.3% to +1.1%, 57–68% up", "Bull flatten": "~0%, 53–65% up",
              "Bear steepen": "mixed: +0.6% / −0.4% by lookback", "Bear flatten": "−0.2% to −0.4%, ~52% up (coin flip)"}
def _us_yields(X):
    y2, y10 = X.y("US", "02Y"), X.y("US", "10Y")
    if len(y2) < 80 or len(y10) < 80: y2, y10 = X.f("DGS2"), X.f("DGS10")
    d = pd.concat([y2, y10], axis=1).ffill().dropna(); d.columns = ["y2", "y10"]; return d
def pair_regime(d, n=20, thr=5):
    ds = ((d.y10 - d.y2) - (d.y10 - d.y2).shift(n)) * 100; d10 = (d.y10 - d.y10.shift(n)) * 100
    lab = np.where(ds > thr, np.where(d10 > 0, "Bear steepen", "Bull steepen"), np.where(ds < -thr, np.where(d10 > 0, "Bear flatten", "Bull flatten"), "Flat"))
    return pd.Series(lab, index=d.index).where(ds.notna()), ds, d10
def pair_watch(X):
    d = _us_yields(X); l20, ds20, d1020 = pair_regime(d, 20, 5); l60, _, _ = pair_regime(d, 60, 10)
    tr = X.tr; ratio = (tr.KBWB / tr.KRE).dropna()                     # rising = short-KRE/long-KBWB pair winning
    iwm = ((tr.IWM / tr.SPY).dropna()); iwm20 = (iwm.iloc[-1] / iwm.iloc[-21] - 1) * 100
    r = tr[["KRE", "HYG", "IEI"]].pct_change().dropna(); cr = r.HYG - 0.6 * r.IEI; c63 = r.KRE.rolling(63).corr(cr)
    reg = l20.dropna().iloc[-1]; growth_led = reg == "Bear steepen" and iwm20 > 1
    if reg in ("Bull steepen", "Flat"): call = "WATCH · ENTRY WINDOW OPEN (green)"
    elif reg == "Bull flatten": call = "WATCH · NEUTRAL"
    elif reg == "Bear steepen": call = "WATCH · STAND ASIDE: growth-led steepener" if growth_led else "WATCH · AMBER: term-premium steepener, small size OK"
    else: call = "WATCH · WAIT (coin-flip regime)"
    return dict(reg=reg, reg60=l60.dropna().iloc[-1], ds20=ds20.iloc[-1], d1020=d1020.iloc[-1], iwm20=iwm20, growth_led=growth_led,
                c63=c63.iloc[-1], c63_pct=(c63.dropna() <= c63.iloc[-1]).mean() * 100, ratio=ratio, ds20s=ds20, iwm=iwm, call=call,
                pair1m=(ratio.iloc[-1] / ratio.iloc[-22] - 1) * 100)

def evaluate(X):
    out = []
    for th in THESES:
        res = []
        for kind, conds in (("CONFIRM", th["confirm"]), ("KILL", th["kill"])):
            for lab, fn in conds:
                try: met, val = fn(X)
                except Exception as e: met, val = None, f"n/a ({e})"
                res.append((kind, lab, None if met is None else bool(met), val))
        kills = [r for r in res if r[0] == "KILL" and r[2]]; conf = [r for r in res if r[0] == "CONFIRM"]
        share = sum(bool(r[2]) for r in conf) / len(conf)
        status = "FALSIFIED" if kills else "CONFIRMING" if share >= 0.67 else "ACTIVE" if share >= 0.34 else "UNCONFIRMED"
        out.append((th, res, status, share))
    return out

def calls(X):
    """Rule-based macro calls from today's facts. Each: (asset, call, why, invalidation, horizon). Coarse and directional by design."""
    F = X.facts; out = []
    tells = F.get("event_tells", []); hr = sum("higher" in t[2] for t in tells) / max(len(tells), 1)
    lk = F.get("linkage", 50); y1m = F.get("y10_1m", 0); vz = F.get("vol_z", {})
    # duration
    if y1m > 15 and hr > 0.5 and lk > 55:
        stretched = y1m > 35
        out.append(("US duration (TLT / ZN)", "UNDERWEIGHT — hold, but don't add (move stretched)" if stretched else "UNDERWEIGHT — don't buy the dip yet",
                    f"10Y +{y1m:.0f}bp 1M, {hr*100:.0f}% of event tells on the higher-rates side, linkage {lk:.0f}% (momentum regime)"
                    + (". Test note: after 35bp+ monthly rises, underweights lost on average (yields came back)" if stretched else "")
                    + ". Backtest 2007–26: 55% hit at 21d, 72% at 42d (n=25, small sample)",
                    "US 2Y closes back below its last payrolls-day close and MOVE z-score falls under +1", "1–2 months"))
    elif y1m < -15 and hr < 0.5:
        out.append(("US duration (TLT / ZN)", "OVERWEIGHT", f"10Y {y1m:+.0f}bp 1M and event tells on the lower-rates side", "10Y retakes its 1M high", "2–6 weeks"))
    else:
        out.append(("US duration (TLT / ZN)", "NEUTRAL", "no clean trend/tell alignment", "—", "—"))
    # curve
    cr = F.get("curve_regime", "")
    if "Bear flattener" in cr and F.get("policy_state") == "TIGHTENING":
        out.append(("US curve 2s10s", "FLATTENER bias; steepeners premature", f"2s10s regime {cr} with policy {F.get('policy_state')} (+{F.get('policy_chg', 0):.0f}bp 1M)",
                    "2s10s regime flips to bull steepener or Fed pricing falls 20bp in a month", "1–3 months"))
    elif "steepener" in cr.lower():
        out.append(("US curve 2s10s", "STEEPENER", f"regime {cr}", "regime flips to a flattener", "1–3 months"))
    # KRE/KBWB pair watch (not a position; entry gate from the curve regime)
    try:
        pw = pair_watch(X)
        out.append(("Short KRE / long KBWB (pair watch)", pw["call"],
                    f"2s10s 20-session regime {pw['reg']} ({pw['ds20']:+.0f}bp slope, 10Y {pw['d1020']:+.0f}bp); 60-session {pw['reg60']}. Post-2022 history after this regime: {PAIR_STATS.get(pw['reg'], '—')}. "
                    f"IWM vs SPY {pw['iwm20']:+.1f}% 20d; KRE–credit corr (63d) {pw['c63']:+.2f} ({pw['c63_pct']:.0f}th pct). Pair {pw['pair1m']:+.1f}% 1M. "
                    "Pair = blow-up insurance (regional-only stress), mostly short small-cap otherwise; thin sample, a tilt not a rule",
                    "Green: bull steepen or flat. Wait: bear flatten. Bear steepen: stand aside if IWM beats SPY by >1% over 20d (growth-led)", "weeks–months"))
    except Exception as e:
        out.append(("Short KRE / long KBWB (pair watch)", "n/a", f"pair watch failed: {e}", "—", "—"))
    # equity index
    spy_pct = (X.px.SPY.iloc[-252:] <= X.px.SPY.iloc[-1]).mean() * 100; a50 = F.get("a50", 50)
    if spy_pct > 90 and a50 < 40 and vz.get("Equity (VIX)", 0) < 0.5:
        out.append(("S&P 500 (SPY)", "HOLD CORE, NO SYSTEMATIC HEDGE", f"SPY {spy_pct:.0f}th pct of 1y with only {a50:.0f}% of stocks above 50d; equity vol z {vz.get('Equity (VIX)', 0):+.1f}. "
                    f"Backtest 2007–26: near highs with cheap vol saw FEWER 5% drawdowns in 45d (17–21%) than an average day (29%); breadth added nothing. "
                    f"Narrow breadth is not a hedge signal on its own. Tail protection is optional, not rule-backed",
                    "a real stress signal instead: VIX term structure inverts (VIX9D > VIX3M) or HY widens 50bp+ in a month", "1–2 months"))
    elif F.get("regime") == "Goldilocks" and a50 > 60:
        out.append(("S&P 500 (SPY)", "LONG / ADD", "Goldilocks tape with broad participation", "growth composite turns negative", "1–3 months"))
    # breadth relative
    if F.get("rsp_spy_3m", 0) < -2:
        out.append(("Equal weight vs cap weight (RSP/SPY)", "NO CATCH-UP BET — stay cap-weighted", f"RSP/SPY {F.get('rsp_spy_3m', 0):+.1f}% 3M and still falling; 1926– history shows no reliable mean reversion",
                    "RSP/SPY makes a 3-month high", "1–3 months"))
    # credit
    if F.get("hy_1m", 0) > 10 and F.get("hy_pct", 50) < 40:
        out.append(("High yield vs IG (express: HYGH vs LQDH)", "UNDERWEIGHT HY vs IG", f"HY {F.get('hy', 0)*100:.0f}bp ({F.get('hy_pct', 0):.0f}th pct 10y) and widening {F.get('hy_1m', 0):+.0f}bp 1M: tight spreads, deteriorating trend",
                    "HY OAS back below its 1M low", "1–3 months"))
    # oil / energy
    xle = (X.px.XLE / X.px.SPY); xl = (xle.iloc[-1] / xle.iloc[-22] - 1) * 100; cl = X.t("NYMEX:CL1!"); cl1 = (cl.iloc[-1] / cl.iloc[-22] - 1) * 100
    if "Oil" in F.get("theme", "") and cl1 > 0 and xl < 0:
        out.append(("Oil / energy", "OWN THE INFLATION HEDGE IN FUTURES OR BREAKEVENS, NOT ENERGY STOCKS", f"oil drives SPY (R² {F.get('theme_r2', 0):.2f}) and WTI {cl1:+.0f}% 1M, but XLE {xl:+.1f}% vs SPY: equities reject the oil move",
                    "XLE/SPY makes a 1M high (equities confirm) — then energy equities are fine", "2–6 weeks"))
    # vol relative
    if vz.get("Rates (MOVE)", 0) > 2 and vz.get("Equity (VIX)", 0) < 0:
        out.append(("Cross-asset vol", "EQUITY VOL IS CHEAP vs RATES VOL", f"MOVE z {vz.get('Rates (MOVE)', 0):+.1f} vs VIX z {vz.get('Equity (VIX)', 0):+.1f}: the rates shock hasn't reached equity options",
                    "VIX z-score catches up above +1 (the gap closes)", "2–4 weeks"))
    # FX from differentials
    for p, cc, sgn in (("EURUSD", "DE", 1), ("USDCAD", "CA", -1), ("USDJPY", "JP", -1), ("AUDUSD", "AU", 1), ("GBPUSD", "GB", 1)):
        spot = X.t(f"FX_IDC:{p}"); diff = (X.y("US", "02Y") - X.y(cc, "02Y")) * 100
        d = pd.concat([spot, diff], axis=1).ffill().dropna(); d.columns = ["s", "d"]
        c63 = np.log(d.s).diff().rolling(63).corr(d.d.diff()).iloc[-1]; dd = d.d.iloc[-1] - d.d.iloc[-22]
        if abs(c63) >= 0.4 and abs(dd) >= 15:
            usd_up = dd > 0; pair_up = (not usd_up) if sgn > 0 else usd_up
            out.append((p, f"{'HIGHER' if pair_up else 'LOWER'} bias", f"pair is trading the 2Y differential (corr {c63:+.2f}); US−{cc} 2Y {dd:+.0f}bp 1M",
                        f"US−{cc} 2Y differential reverses 15bp", "2–6 weeks"))
    return out

SC = {"FALSIFIED": "#e05252", "CONFIRMING": "#4caf50", "ACTIVE": "#e0b64a", "UNCONFIRMED": "#888"}
def tab_thesis(X):
    ev = evaluate(X); read = []
    cl = calls(X)
    rows = "".join(f"<tr><td class='nm'>{a}</td><td style='text-align:left' class='w'><b>{c}</b></td><td class='txt'>{w}</td><td class='txt'>{i}</td><td class='txt'>{h}</td></tr>" for a, c, w, i, h in cl)
    html = (f"<div class='tbl'><div class='tt'>CALLS BOARD · rule-based from today's tape (not personal advice; size to your own risk)</div><table><tr><th>Market</th>"
            f"<th style='text-align:left'>Call</th><th style='text-align:left'>Why (today's evidence)</th><th style='text-align:left'>What kills it</th><th style='text-align:left'>Horizon</th></tr>{rows}</table></div>")
    X.facts["calls"] = [(a, c) for a, c, *_ in cl]
    from .callviz import call_cards
    try: cards = call_cards(X, cl)
    except Exception as e: import traceback; traceback.print_exc(); cards = []
    html += "<div class='tt' style='margin-top:10px'>CALL CHECKS · each call drawn with its trigger (green) and kill (red) levels</div>"
    html2 = "<div class='tt' style='margin-top:10px'>THESES · slower, falsifiable stories</div>"
    for th, res, st, sh in ev:
        rows = "".join(f"<tr><td>{k}</td><td class='nm'>{l}</td><td class='n w'>{v}</td><td class='{'g' if (m and k=='CONFIRM') else 'r' if (m and k=='KILL') else ''}'>"
                       f"{'✔ met' if m else '— not met' if m is False else 'n/a'}</td></tr>" for k, l, m, v in res)
        html2 += (f"<div class='mos' style='margin-bottom:10px'><div class='tt'>{th['id']} · {th['title']} <span style='color:{SC[st]}'>[{st}]</span> "
                 f"<span class='asof'>{th['horizon']} · {th['status_note']}</span></div>"
                 f"<div><b>Hypothesis:</b> {th['hypothesis']}</div><div><b>Causal chain:</b> {' → '.join(th['chain'])}</div>"
                 f"<div><b>Expression:</b> {th['expression']}</div><table style='margin-top:6px'>{rows}</table></div>")
        read.append(f"{th['id']} {th['title']}: <b style='color:{SC[st]}'>{st}</b> ({sh*100:.0f}% of confirms met)")
    X.facts["theses"] = [(th["id"], st) for th, _, st, _ in ev]
    read.append("Theses are drafts written from the current tape: edit engine/thesis.py. Status is re-checked every build; kill conditions are pre-committed.")
    return dict(key="thesis", title="THESIS", read=read, cards=cards, html=html, html2=html2)
