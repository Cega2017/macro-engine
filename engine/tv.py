"""TradingView layer. TV data arrives through the TradingView MCP connector inside a Claude session, so:
  1) `python3 -m engine.tv plan`   → prints the symbol list the session must pull (get_ohlcv, interval 1D, count as listed)
  2) the session calls mcp-tv-get-ohlcv for each (large results spill to tool-results/*.txt; small ones stay in the transcript)
  3) `python3 -m engine.tv ingest` → harvests every TV ohlcv result from this machine's Claude transcripts + spill files
                                     into data/tv_bars.parquet (symbol, date, o, h, l, c), merged with anything already cached."""
import os, re, sys, glob, json, datetime as dt, pandas as pd
from . import config as C

YIELDS = [f"TVC:{c}{t}" for c in ("US", "DE", "GB", "JP", "IT", "FR", "CA", "AU") for t in ("02Y", "10Y")] + \
         ["TVC:US05Y", "TVC:US30Y", "TVC:DE30Y", "TVC:GB30Y", "TVC:JP30Y", "TVC:CN10Y"]
FX = ["FX_IDC:EURUSD", "FX_IDC:USDJPY", "FX_IDC:GBPUSD", "FX_IDC:AUDUSD", "FX_IDC:USDCAD", "FX_IDC:USDCHF", "FX_IDC:USDMXN", "FX_IDC:USDCNH", "TVC:DXY"]
CMDTY = ["NYMEX:CL1!", "ICEEUR:BRN1!", "COMEX:GC1!", "COMEX:SI1!", "COMEX:HG1!", "NYMEX:NG1!", "CBOT:ZC1!", "CBOT:ZW1!"]
RISK = ["TVC:MOVE", "CBOE:COR3M", "INDEX:S5FI", "INDEX:S5TH", "INDEX:S5TW", "CBOT:UB1!", "CBOT:ZT1!", "CBOT:ZN1!"]
CREDIT = [f"FRED:{x}" for x in ("BAMLH0A0HYM2", "BAMLC0A0CM", "BAMLH0A3HYC", "BAMLH0A0HYM2EY", "BAMLC0A0CMEY", "BAMLH0A3HYCEY")]   # ICE credit: FRED's own API now serves only 3y
MC = "FGHJKMNQUVXZ"

def strip_symbols(today=None):
    d = today or dt.date.today(); out = []
    y, m = d.year, d.month
    for k in range(19):                      # ZQ: current month + 18 (out to early 2028)
        mm = (m - 1 + k) % 12; yy = y + (m - 1 + k) // 12
        out.append(f"CBOT:ZQ{MC[mm]}{yy}")
    q = [3, 6, 9, 12]; yy, mm = y, next((x for x in q if x > m), None)
    if mm is None: yy, mm = y + 1, 3
    for k in range(9):                       # SR3 quarterlies
        out.append(f"CME:SR3{MC[mm-1]}{yy}"); mm += 3
        if mm > 12: mm -= 12; yy += 1
    return out

def calendar_request(today=None):
    d = today or dt.date.today()
    return {"countries": "US,EU,GB,JP,CA,AU,DE,CN", "date_from": str(d - dt.timedelta(days=3)), "date_to": str(d + dt.timedelta(days=21)), "min_importance": 1}

EQ_IDX = {"Americas": {"S&P 500": "SP:SPX", "Nasdaq 100": "NASDAQ:NDX", "Russell 2000": "TVC:RUT", "S&P/TSX": "TSX:TSX", "Bovespa": "BMFBOVESPA:IBOV", "Mexico IPC": "BMV:ME"},
          "Europe": {"STOXX 600": "TVC:SXXP", "Euro Stoxx 50": "TVC:SX5E", "DAX": "XETR:DAX", "FTSE 100": "TVC:UKX", "CAC 40": "EURONEXT:PX1", "FTSE MIB": "INDEX:FTSEMIB", "IBEX 35": "BME:IBC", "SMI": "SIX:SMI"},
          "Asia-Pacific": {"Nikkei 225": "TVC:NI225", "TOPIX": "TSE:TOPIX", "Hang Seng": "TVC:HSI", "CSI 300": "SSE:000300", "Shanghai Comp": "SSE:000001", "KOSPI": "KRX:KOSPI",
                           "Taiwan TAIEX": "TWSE:TAIEX", "ASX 200": "ASX:XJO", "Nifty 50": "NSE:NIFTY"}}
SR3_HIST = [f"CME:SR3{m}{y}" for y in (2023, 2024, 2025, 2026) for m in "HMUZ" if (y, "HMUZ".index(m)) < (2026, 3)]   # expired quarterlies: history for constant-horizon pricing

def plan():
    return [{"symbol": s, "count": 1500} for s in SR3_HIST] + [{"symbol": s, "count": 1500} for r in EQ_IDX.values() for s in r.values()] + [{"symbol": s, "count": 1500} for s in YIELDS + FX + CMDTY + RISK] + [{"symbol": s, "count": 1000} for s in strip_symbols()] + [{"symbol": s, "count": 5000} for s in CREDIT]

def _bars_from_obj(o):
    if isinstance(o, dict) and "bars" in o and "symbol" in o:
        return o["symbol"], o["bars"]
    return None

CAL = []
def _harvest_cal(o):
    if isinstance(o, dict) and isinstance(o.get("result"), list) and o["result"] and isinstance(o["result"][0], dict) and "indicator" in o["result"][0]:
        CAL.extend(o["result"])

def _harvest_text(txt, out):
    txt = txt.strip()
    if txt.startswith("{") and '"indicator"' in txt:
        try: _harvest_cal(json.loads(txt))
        except Exception: pass
    if txt.startswith("{") and '"bars"' in txt:
        try:
            r = _bars_from_obj(json.loads(txt))
            if r: out.append(r)
        except Exception: pass
    m = re.search(r"saved to (\S+get-ohlcv\S+\.txt)", txt)
    if m and os.path.exists(m.group(1)):
        try:
            r = _bars_from_obj(json.load(open(m.group(1))))
            if r: out.append(r)
        except Exception: pass

def ingest(root=os.path.expanduser("~/.claude/projects")):
    found = []
    for f in glob.glob(os.path.join(root, "**", "*get-ohlcv*.txt"), recursive=True):
        try:
            r = _bars_from_obj(json.load(open(f)))
            if r: found.append(r)
        except Exception: pass
    for f in glob.glob(os.path.join(root, "**", "*get-economic-calendar*.txt"), recursive=True):
        try: _harvest_cal(json.load(open(f)))
        except Exception: pass
    for f in glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True):
        with open(f, errors="ignore") as fh:
            for line in fh:
                if "Tradingview" not in line and '"bars"' not in line and '"indicator"' not in line: continue
                try: j = json.loads(line)
                except Exception: continue
                msg = j.get("message", {}); cont = msg.get("content") if isinstance(msg, dict) else None
                if not isinstance(cont, list): continue
                for c in cont:
                    if c.get("type") != "tool_result": continue
                    cc = c.get("content")
                    items = cc if isinstance(cc, list) else [{"type": "text", "text": cc}]
                    for it in items:
                        if isinstance(it, dict) and isinstance(it.get("text"), str): _harvest_text(it["text"], found)
    rows = []
    for sym, bars in found:
        for b in bars:
            if b.get("c") is None: continue
            ny = pd.Timestamp(b["t"], unit="s", tz="UTC").tz_convert("America/New_York")
            d = (ny + pd.Timedelta(days=1)).date() if ny.hour >= 17 else ny.date()   # FX/futures sessions opening the prior evening → next trading date
            rows.append((sym, pd.Timestamp(d).normalize(), b.get("o"), b.get("h"), b.get("l"), b["c"], b["t"]))
    new = pd.DataFrame(rows, columns=["symbol", "date", "o", "h", "l", "c", "t"])
    path = os.path.join(C.DATA, "tv_bars.parquet")
    if os.path.exists(path): new = pd.concat([pd.read_parquet(path), new])
    new = new.sort_values("t").drop_duplicates(["symbol", "date"], keep="last").sort_values(["symbol", "date"])
    new.to_parquet(path)
    if CAL:
        cp = os.path.join(C.DATA, "calendar.json")
        old = {e["id"]: e for e in (json.load(open(cp)) if os.path.exists(cp) else [])}
        for e in CAL: old[e["id"]] = {k: e.get(k) for k in ("id", "date", "country", "title", "period", "actual", "forecast", "previous", "unit", "scale", "category", "importance")}
        json.dump(list(old.values()), open(cp, "w")); print(f"calendar: {len(CAL)} events harvested")
    last = new.groupby("symbol").date.max()
    print(f"tv ingest: {len(found)} results, {new.symbol.nunique()} symbols, latest {last.max():%Y-%m-%d}; stale(<{last.max():%m-%d}): {sorted(s for s in last[last < last.max() - pd.Timedelta(days=4)].index if s not in SR3_HIST)}")
    return new

def closes():
    p = os.path.join(C.DATA, "tv_bars.parquet")
    if not os.path.exists(p): return pd.DataFrame(), pd.DataFrame()
    d = pd.read_parquet(p); d["date"] = pd.to_datetime(d["date"])
    return d.pivot_table(index="date", columns="symbol", values="c").sort_index(), d

if __name__ == "__main__":
    if sys.argv[1:] == ["plan"]: print(json.dumps(plan()))
    elif sys.argv[1:] == ["calendar"]: print(json.dumps(calendar_request()))
    else: ingest()
