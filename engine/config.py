"""Series registry + settings. Keys come from env (NASDAQ_API_KEY, FRED_API_KEY)."""
import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data"); OUT = os.path.join(ROOT, "out")
NASDAQ_KEY = os.environ.get("NASDAQ_API_KEY", "")
FRED_KEY = os.environ.get("FRED_API_KEY", "")
START = "2005-01-01"

# FRED series: id -> (label, expected cadence in business days before STALE)
FRED = {
 # rates / curve
 "DGS1MO":("UST 1M",3),"DGS3MO":("UST 3M",3),"DGS6MO":("UST 6M",3),"DGS1":("UST 1Y",3),"DGS2":("UST 2Y",3),
 "DGS3":("UST 3Y",3),"DGS5":("UST 5Y",3),"DGS7":("UST 7Y",3),"DGS10":("UST 10Y",3),"DGS20":("UST 20Y",3),"DGS30":("UST 30Y",3),
 "DFF":("EFFR",3),"SOFR":("SOFR",3),"IORB":("IORB",5),
 "DFII5":("5Y TIPS real",3),"DFII10":("10Y TIPS real",3),"DFII30":("30Y TIPS real",3),
 "T5YIE":("5Y breakeven",3),"T10YIE":("10Y breakeven",3),"T5YIFR":("5y5y fwd BE",3),
 "THREEFYTP10":("10Y term premium (KW)",10),
 "EXPINF1YR":("Cleveland 1Y exp infl",45),"EXPINF5YR":("Cleveland 5Y exp infl",45),
 # credit / liquidity / conditions
 "BAMLH0A0HYM2":("HY OAS",3),"BAMLC0A0CM":("IG OAS",3),"BAMLH0A3HYC":("CCC OAS",3),
 "BAMLH0A0HYM2EY":("HY eff yield",3),"BAMLC0A0CMEY":("IG eff yield",3),"BAMLH0A3HYCEY":("CCC eff yield",3),
 "WALCL":("Fed assets",10),"RRPONTSYD":("ON RRP",3),"WTREGEN":("TGA",10),"WRESBAL":("Reserves",10),
 "NFCI":("Chicago NFCI",10),"STLFSI4":("StL stress",10),"M2SL":("M2",45),
 # vol
 "VIXCLS":("VIX",3),"OVXCLS":("OVX",3),"GVZCLS":("GVZ",3),
 # fx (H.10, ~1wk lag)
  # commodities
 "DCOILWTICO":("WTI spot",5),"DCOILBRENTEU":("Brent spot",10),
 # context only (not model inputs)
 "ICSA":("Initial claims",10),"GDPNOW":("GDPNow",20),"MORTGAGE30US":("30Y mortgage",10),"CPILFESL":("Core CPI",45),
}

# Sharadar fund prices (tape)
ETFS = ["SPY","QQQ","IWM","DIA","RSP","EFA","EEM","EWJ","FXI","TLT","IEF","SHY","TIP","LQD","HYG","EMB","GLD","SLV","CPER","DBC",
        "USO","UNG","DBA","UUP","FXE","FXY","FXA","FXB","FXC","FXF","XLK","XLF","XLY","XLV","XLI","XLC","XLE","XLP","XLU","XLB","XLRE",
        "SMH","IYT","KRE","KBWB","XHB","ITB","IWF","IWD","MTUM","SPHB","SPLV","GDX","COPX","URA","IBIT","BITO","HYGH","LQDH","BIL","IEI"]

CBOE = ["VIX","VIX9D","VIX3M","VVIX","SKEW"]

# Large caps for the interactive explorer (PCA / correlation / attribution on single names)
STOCKS = ["AAPL","MSFT","NVDA","AMZN","GOOGL","META","AVGO","TSLA","BRK.B","JPM","V","MA","LLY","UNH","JNJ","ABBV","MRK","XOM","CVX","COP",
          "WMT","COST","HD","PG","KO","PEP","MU","AMD","ORCL","CRM","ADBE","NFLX","INTC","QCOM","CAT","GE","BA","LMT","GS","BAC","NEM","FCX","DE","UNP","NEE"]

# Credit index effective durations (years) for duration-adjusting spreads. Static snapshot from iShares fund pages;
# durations drift slowly, refresh by hand every few months. HY proxied by HYG, IG by LQD. No free CCC duration source.
CREDIT_DUR = {"HY": (3.16, "HYG, iShares, 2026-09-23"), "IG": (7.63, "LQD, iShares, 2026-09-24")}
HY_WAM = 4.13   # HYG weighted avg maturity (yrs), iShares 2026-09-23; used as the CCC maturity assumption
