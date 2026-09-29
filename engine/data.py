"""Fetch + cache. Every series is stored as parquet with a 'fetched' stamp; staleness judged per series cadence."""
import os, io, time, json, zipfile, requests, pandas as pd, numpy as np
from . import config as C
S = requests.Session()

def _get(url, params=None, tries=4):
    for i in range(tries):
        try:
            r = S.get(url, params=params, timeout=60)
            if r.status_code == 200: return r
        except requests.RequestException: pass
        time.sleep(2 * (i + 1))
    raise RuntimeError(f"fetch failed {url}")

def _path(name): return os.path.join(C.DATA, name + ".parquet")
def load(name): return pd.read_parquet(_path(name)) if os.path.exists(_path(name)) else None
def save(name, df): df.to_parquet(_path(name))

# ---------- FRED
def fred(ids=None):
    ids = ids or list(C.FRED); out = {}
    for sid in ids:
        r = _get("https://api.stlouisfed.org/fred/series/observations",
                 dict(series_id=sid, api_key=C.FRED_KEY, file_type="json", observation_start=C.START))
        o = pd.DataFrame(r.json()["observations"])
        s = pd.to_numeric(o.value, errors="coerce"); s.index = pd.to_datetime(o.date)
        out[sid] = s.dropna()
    df = pd.DataFrame(out); save("fred", df); return df

# ---------- Sharadar
def _sharadar(table, params):
    rows, cols, cur = [], None, None
    while True:
        p = dict(params, api_key=C.NASDAQ_KEY, **{"qopts.per_page": 10000})
        if cur: p["qopts.cursor_id"] = cur
        j = _get(f"https://data.nasdaq.com/api/v3/datatables/SHARADAR/{table}.json", p).json()
        d = j["datatable"]; cols = [c["name"] for c in d["columns"]]; rows += d["data"]
        cur = j["meta"]["next_cursor_id"]
        if not cur: break
    return pd.DataFrame(rows, columns=cols)

def etfs(tickers=None):
    tickers = tickers or C.ETFS; parts = []
    for i in range(0, len(tickers), 20):
        parts.append(_sharadar("SFP", {"ticker": ",".join(tickers[i:i+20]), "date.gte": C.START,
                                       "qopts.columns": "ticker,date,close,closeadj"}))
    d = pd.concat(parts); d["date"] = pd.to_datetime(d.date)
    px = d.pivot_table(index="date", columns="ticker", values="close").sort_index()
    tr = d.pivot_table(index="date", columns="ticker", values="closeadj").sort_index()
    save("etf_px", px); save("etf_tr", tr); return px, tr

# ---------- release calendar (event anchors: CPI, payrolls) from FRED
RELEASES = {"CPI": 10, "NFP": 50}
def releases():
    out = {}
    for k, rid in RELEASES.items():
        r = _get("https://api.stlouisfed.org/fred/release/dates", dict(release_id=rid, api_key=C.FRED_KEY, file_type="json",
                 realtime_start="2003-01-01", include_release_dates_with_no_data="true", limit=10000))
        out[k] = [x["date"] for x in r.json()["release_dates"]]
    json.dump(out, open(os.path.join(C.DATA, "releases.json"), "w")); return out

# ---------- single stocks for the explorer (Sharadar SEP, total-return closeadj)
def stocks(tickers=None):
    tickers = tickers or C.STOCKS; parts = []
    for i in range(0, len(tickers), 25):
        parts.append(_sharadar("SEP", {"ticker": ",".join(tickers[i:i+25]), "date.gte": "2021-01-01", "qopts.columns": "ticker,date,closeadj"}))
    x = pd.concat(parts); x["date"] = pd.to_datetime(x.date)
    tr = x.pivot_table(index="date", columns="ticker", values="closeadj").sort_index(); save("stk_tr", tr); return tr

# ---------- Cboe
def cboe():
    out = {}
    for n in C.CBOE:
        t = _get(f"https://cdn.cboe.com/api/global/us_indices/daily_prices/{n}_History.csv").text
        d = pd.read_csv(io.StringIO(t)); d.columns = [c.upper() for c in d.columns]
        d.index = pd.to_datetime(d["DATE"]); col = "CLOSE" if "CLOSE" in d else d.columns[-1]
        out[n] = pd.to_numeric(d[col], errors="coerce")
    df = pd.DataFrame(out); df = df[df.index >= C.START]; save("cboe", df); return df

# ---------- Ken French (long-run breadth)
def french():
    r = _get("https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/Portfolios_Formed_on_ME_CSV.zip")
    z = zipfile.ZipFile(io.BytesIO(r.content)); txt = z.read(z.namelist()[0]).decode("latin1").splitlines()
    def sect(title):
        i = [k for k, l in enumerate(txt) if title in l][0] + 1; hdr = txt[i]; rows = []; i += 1
        while i < len(txt) and txt[i].strip() and txt[i].split(",")[0].strip().isdigit(): rows.append(txt[i]); i += 1
        d = pd.read_csv(io.StringIO(hdr + "\n" + "\n".join(rows))); d.index = pd.PeriodIndex(d.iloc[:, 0].astype(str), freq="M").to_timestamp("M")
        return d.iloc[:, 1:].replace([-99.99, -999], np.nan) / 100
    vw = sect("Average Value Weight Returns -- Monthly"); ew = sect("Average Equal Weighted Returns -- Monthly")
    df = pd.DataFrame({"vw_hi30": vw["Hi 30"], "ew_hi30": ew["Hi 30"]}); save("french", df); return df

def refresh_all():
    t0 = time.time(); log = {}
    for name, fn in (("fred", fred), ("etfs", etfs), ("cboe", cboe), ("french", french), ("releases", releases), ("stocks", stocks)):
        try: fn(); log[name] = "ok"
        except Exception as e: log[name] = f"FAIL {e}"
        print(name, log[name], round(time.time() - t0), "s", flush=True)
    json.dump(dict(log, ts=pd.Timestamp.now().isoformat()), open(os.path.join(C.DATA, "refresh_log.json"), "w"))
    return log
