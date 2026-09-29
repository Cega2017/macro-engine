"""Run-over-run change detection. Compares out/facts.json (this run) with out/facts_prev.json
(the facts.json published with the previous artifact version). Writes out/facts_diff.json and prints a summary."""
import json, os, sys
from . import config as C

LEVELS = {  # key: (label, threshold for "notable" move, unit)
    "fed_priced_bp": ("Fed priced", 10, "bp"), "y10": ("10Y", 0.10, "%"), "y2": ("2Y", 0.10, "%"),
    "s210": ("2s10s", 10, "bp"), "hy": ("HY OAS", 0.25, "%"), "vix": ("VIX", 2.5, ""), "move": ("MOVE", 10, ""),
}
STATES = ["regime", "policy_state", "liq_state", "vol_state", "theme", "curve_regime"]


def _pairs(v):
    return {str(a): str(b) for a, b in v} if isinstance(v, list) else {}


def diff(prev, cur):
    out = {"prev_available": bool(prev), "states": [], "theses": [], "calls": [], "levels": []}
    if not prev:
        return out
    for k in STATES:
        if k in cur and prev.get(k) != cur.get(k):
            out["states"].append([k, prev.get(k), cur.get(k)])
    for fld in ("theses", "calls"):
        p, c = _pairs(prev.get(fld)), _pairs(cur.get(fld))
        for key in sorted(set(p) | set(c)):
            if p.get(key) != c.get(key):
                out[fld].append([key, p.get(key, "(new)"), c.get(key, "(dropped)")])
    for k, (lab, th, u) in LEVELS.items():
        try:
            a, b = float(prev[k]), float(cur[k])
        except (KeyError, TypeError, ValueError):
            continue
        if abs(b - a) >= th:
            out["levels"].append([lab, round(a, 3), round(b, 3), u])
    return out


def main():
    cur_p, prev_p = os.path.join(C.OUT, "facts.json"), os.path.join(C.OUT, "facts_prev.json")
    cur = json.load(open(cur_p))
    try:
        prev = json.load(open(prev_p))
    except Exception:
        prev = {}
    d = diff(prev, cur)
    json.dump(d, open(os.path.join(C.OUT, "facts_diff.json"), "w"), indent=1)
    if not d["prev_available"]:
        print("facts diff: NO PRIOR facts.json — change detection skipped this run"); return
    n = sum(len(d[k]) for k in ("states", "theses", "calls", "levels"))
    print(f"facts diff vs prior run: {n} changes")
    for k in ("states", "theses", "calls"):
        for name, a, b in d[k]:
            print(f"  {k[:-1] if k != 'theses' else 'thesis'} {name}: {a} -> {b}")
    for lab, a, b, u in d["levels"]:
        print(f"  level {lab}: {a}{u} -> {b}{u}")


if __name__ == "__main__":
    sys.exit(main())
