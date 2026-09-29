"""Load cached data into one context object."""
import os, json, pandas as pd, numpy as np
from . import config as C, data, tv

class Ctx:
    def __init__(self):
        today = pd.Timestamp.now().normalize()
        f = data.load("fred"); self.fred = f[f.index <= today]
        self.px = data.load("etf_px"); self.tr = data.load("etf_tr")
        self.cboe = data.load("cboe"); self.french = data.load("french")
        self.tv, self.tvbars = tv.closes()
        rp = os.path.join(C.DATA, "releases.json")
        self.rel = {k: [pd.Timestamp(x) for x in v] for k, v in json.load(open(rp)).items()} if os.path.exists(rp) else {}
        self.asof = max(self.px.index[-1], self.tv.index[-1] if len(self.tv) else self.px.index[-1])
        self.facts = {}; self.S = {}   # series shared across tabs (call-check charts)
    def f(self, sid):
        s = self.fred[sid].dropna() if sid in self.fred else pd.Series(dtype=float)
        t = self.tv.get(f"FRED:{sid}")                      # TradingView mirror carries the long ICE history FRED truncated
        if t is not None: s = s.combine_first(t.dropna()) if len(s) else t.dropna()
        return s
    def t(self, sym): return self.tv[sym].dropna() if sym in self.tv else pd.Series(dtype=float)
    def y(self, cc, ten): return self.t(f"TVC:{cc}{ten}")
    def ret(self, t): return self.tr[t].pct_change()
