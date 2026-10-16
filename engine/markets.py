"""Cross-market panel: NQ against the instruments that drive or confirm it, with divergence alerts."""
from __future__ import annotations

import time

import numpy as np
import pandas as pd

ASSETS = [
    ("NQ", "NQ=F", "Nasdaq-100 futures"), ("ES", "ES=F", "S&P 500 futures"), ("YM", "YM=F", "Dow futures"),
    ("RTY", "RTY=F", "Russell 2000 futures"), ("DXY", "DX-Y.NYB", "US dollar index"), ("US10Y", "^TNX", "10-year yield"),
    ("VIX", "^VIX", "S&P volatility"), ("GOLD", "GC=F", "Gold futures"), ("OIL", "CL=F", "Crude oil futures"), ("BTC", "BTC-USD", "Bitcoin"),
]
_cache: dict = {}


def snapshot():
    hit = _cache.get("snap")
    if hit and time.time() - hit[0] < 600:
        return hit[1]
    import yfinance as yf
    tickers = [t for _, t, _ in ASSETS]
    df = yf.download(tickers, period="6mo", interval="1d", progress=False, auto_adjust=False, group_by="column")
    close = df["Close"] if isinstance(df.columns, pd.MultiIndex) else df
    close = close.ffill()
    rets = close.pct_change()
    nq = rets["NQ=F"]
    rows = []
    for key, tk, name in ASSETS:
        if tk not in close:
            continue
        c = close[tk].dropna()
        if len(c) < 3:
            continue
        chg = float(c.iloc[-1] / c.iloc[-2] - 1) * 100
        corr20 = float(rets[tk].iloc[-20:].corr(nq.iloc[-20:])) if key != "NQ" else 1.0
        corr60 = float(rets[tk].iloc[-60:].corr(nq.iloc[-60:])) if key != "NQ" else 1.0
        spark = [round(float(x), 4) for x in (c.iloc[-40:] / c.iloc[-40] - 1) * 100]
        rows.append({"key": key, "name": name, "last": round(float(c.iloc[-1]), 4), "chg_pct": round(chg, 2),
                     "chg_5d": round(float(c.iloc[-1] / c.iloc[-6] - 1) * 100, 2) if len(c) > 6 else None,
                     "corr20": None if np.isnan(corr20) else round(corr20, 2), "corr60": None if np.isnan(corr60) else round(corr60, 2),
                     "spark": spark, "date": str(c.index[-1].date())})
    by = {r["key"]: r for r in rows}
    alerts = []
    nqc = by.get("NQ", {}).get("chg_pct", 0)
    if "ES" in by and nqc * by["ES"]["chg_pct"] < 0 and abs(nqc) > 0.2 and abs(by["ES"]["chg_pct"]) > 0.2:
        alerts.append(("warn", f"NQ / ES divergence today ({nqc:+.2f}% vs {by['ES']['chg_pct']:+.2f}%): one index is not confirming (SMT)."))
    if "US10Y" in by and by["US10Y"]["chg_pct"] > 1.5 and nqc > 0.3:
        alerts.append(("warn", f"Yields up {by['US10Y']['chg_pct']:+.2f}% while NQ rallies: rates headwind for tech."))
    if "US10Y" in by and by["US10Y"]["chg_pct"] < -1.5 and nqc < -0.3:
        alerts.append(("info", "Yields falling while NQ sells off: risk-off flows into bonds."))
    if "DXY" in by and by["DXY"]["chg_pct"] > 0.4 and nqc > 0.3:
        alerts.append(("warn", f"Dollar strong ({by['DXY']['chg_pct']:+.2f}%) while NQ rallies: unusual, watch for a failed move."))
    if "VIX" in by and by["VIX"]["chg_pct"] > 5 and nqc > 0:
        alerts.append(("warn", f"VIX up {by['VIX']['chg_pct']:+.1f}% while NQ is green: hedging demand under the surface."))
    if "BTC" in by and abs(by["BTC"]["chg_pct"] - nqc) > 4:
        alerts.append(("info", f"Bitcoin and NQ split by {by['BTC']['chg_pct'] - nqc:+.1f} pts: risk appetite is mixed."))
    if "ES" in by and by["ES"]["corr20"] is not None and by["ES"]["corr20"] < 0.8:
        alerts.append(("warn", f"NQ/ES 20-day correlation only {by['ES']['corr20']:.2f}: indices decoupling."))
    if "RTY" in by and nqc * by["RTY"]["chg_pct"] < 0 and abs(by["RTY"]["chg_pct"]) > 0.5:
        alerts.append(("info", f"Small caps ({by['RTY']['chg_pct']:+.2f}%) moving against NQ: rotation, not broad risk-on/off."))
    out = {"rows": rows, "alerts": [{"level": l, "text": t} for l, t in alerts], "t": int(time.time())}
    _cache["snap"] = (time.time(), out)
    return out
