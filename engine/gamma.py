"""Dealer gamma exposure (GEX).

Historical regime: SqueezeMetrics' free daily S&P 500 GEX + DIX (squeezemetrics.com/monitor/static/DIX.csv), 2011->today.
  Backtests use the PREVIOUS day's value (GEX is computed after the close) and its trailing 1-year percentile.
Live levels: QQQ option chain (yfinance) -> naive dealer GEX by strike (dealers long calls / short puts, the usual
  SpotGamma-style convention), call wall, put wall and the zero-gamma flip, mapped onto NQ with the live NQ/QQQ ratio.
These are model estimates of dealer positioning, not observed books.
"""
from __future__ import annotations

import math
import os
import time
import urllib.request

import numpy as np
import pandas as pd

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
GEX_URL = "https://squeezemetrics.com/monitor/static/DIX.csv"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
_cache: dict = {}


def refresh_history(max_age_h=12):
    path = os.path.join(DATA, "GEX_1d.csv")
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age_h * 3600:
        return path
    try:
        raw = urllib.request.urlopen(urllib.request.Request(GEX_URL, headers=UA), timeout=30).read()
        # night-cleanup 2026-11-22: only a real DIX.csv replaces the history (an error page or a cut-off download used to
        # overwrite 15 years of GEX with whatever came back)
        old_n = sum(1 for _ in open(path, "rb")) if os.path.exists(path) else 0
        if raw[:22].lower().startswith(b"date,price,dix,gex") and raw.count(b"\n") >= old_n - 5:
            tmp = path + ".tmp"
            with open(tmp, "wb") as fh:
                fh.write(raw)
            os.replace(tmp, path)
    except Exception:
        pass
    return path


def history():
    path = refresh_history()
    if not os.path.exists(path):
        return pd.DataFrame(columns=["date", "price", "dix", "gex"])
    df = pd.read_csv(path)
    df["gex_bn"] = df["gex"] / 1e9
    # trailing 1-year percentile using only data up to that day
    df["gex_pct"] = df["gex"].rolling(252, min_periods=60).apply(lambda w: (w <= w[-1]).mean() * 100, raw=True)
    return df


def prev_day_map():
    """date -> previous session's GEX ($bn), its 1y percentile and DIX (no lookahead)."""
    key = ("prev", os.path.getmtime(os.path.join(DATA, "GEX_1d.csv")) if os.path.exists(os.path.join(DATA, "GEX_1d.csv")) else 0)
    if key in _cache:
        return _cache[key]
    df = history()
    out = {}
    rows = df.to_dict("records")
    for k in range(1, len(rows)):
        pr = rows[k - 1]
        out[str(rows[k]["date"])] = {"gex_bn": pr["gex_bn"], "gex_pct": pr["gex_pct"], "dix": pr["dix"]}
    # also map the day after the last row (today's session uses yesterday's print)
    _cache[key] = out
    return out


def _bs_gamma(S, K, T, iv, r=0.04):
    if T <= 0 or iv <= 0 or S <= 0 or K <= 0:
        return 0.0
    d1 = (math.log(S / K) + (r + 0.5 * iv * iv) * T) / (iv * math.sqrt(T))
    return math.exp(-0.5 * d1 * d1) / math.sqrt(2 * math.pi) / (S * iv * math.sqrt(T))


def live_levels(nq_price=None, max_days=45):
    """Gamma by strike for QQQ (expiries within max_days), walls and flip, converted to NQ points."""
    hit = _cache.get("live")
    if hit and time.time() - hit[0] < 900:
        return hit[1]
    from . import pcbars
    if pcbars.no_yahoo():           # the QQQ option chain came from Yahoo only: off with no_yahoo (owner 2026-10-19)
        raise pcbars.YahooBlocked("live QQQ gamma needs Yahoo; switched off (no_yahoo in live_model.json)")
    import yfinance as yf
    tk = yf.Ticker("QQQ")
    spot = float(tk.history(period="1d", interval="5m")["Close"].iloc[-1])
    today = pd.Timestamp.utcnow().normalize().tz_localize(None)
    rows = []
    for ex in tk.options:
        T_days = (pd.Timestamp(ex) - today).days + 0.5
        if T_days < 1:
            continue   # same-day expiries swamp the profile and vanish at the close
        if T_days > max_days:
            break
        ch = tk.option_chain(ex)
        for side, df in (("call", ch.calls), ("put", ch.puts)):
            df = df[(df["openInterest"] > 0) & (df["impliedVolatility"] > 0.01) & (df["impliedVolatility"] < 3)]
            for r in df.itertuples():
                rows.append((float(r.strike), side, float(r.openInterest), float(r.impliedVolatility), T_days / 365.0))
    if not rows:
        return None

    def total_gex(S):
        g = 0.0
        for K, side, oi, iv, T in rows:
            v = _bs_gamma(S, K, T, iv) * oi * 100 * S * S * 0.01
            g += v if side == "call" else -v
        return g

    by = {}
    for K, side, oi, iv, T in rows:
        v = _bs_gamma(spot, K, T, iv) * oi * 100 * spot * spot * 0.01
        e = by.setdefault(K, [0.0, 0.0])
        if side == "call":
            e[0] += v
        else:
            e[1] -= v
    strikes = sorted(k for k in by if 0.85 * spot <= k <= 1.15 * spot)
    above = [k for k in strikes if k >= spot] or strikes
    below = [k for k in strikes if k <= spot] or strikes
    call_wall = max(above, key=lambda k: by[k][0])     # biggest call gamma overhead: resistance
    put_wall = min(below, key=lambda k: by[k][1])      # biggest put gamma underneath: support
    grid = np.linspace(spot * 0.92, spot * 1.08, 49)
    tot = [total_gex(s) for s in grid]
    flip = None
    for a in range(len(grid) - 1):
        if tot[a] == 0 or (tot[a] < 0) != (tot[a + 1] < 0):
            flip = float(grid[a] + (grid[a + 1] - grid[a]) * abs(tot[a]) / (abs(tot[a]) + abs(tot[a + 1]) or 1))
            break
    net_now = total_gex(spot)
    ratio = (nq_price / spot) if nq_price else None
    conv = (lambda x: round(x * ratio, 2)) if ratio else (lambda x: None)
    profile = [{"strike": k, "nq": conv(k), "call_bn": round(by[k][0] / 1e9, 3), "put_bn": round(by[k][1] / 1e9, 3),
                "net_bn": round((by[k][0] + by[k][1]) / 1e9, 3)} for k in strikes]
    top = sorted(profile, key=lambda x: -abs(x["net_bn"]))[:8]
    out = {"qqq": round(spot, 2), "nq_ratio": round(ratio, 4) if ratio else None, "net_gex_bn": round(net_now / 1e9, 3),
           "regime": "positive gamma (mean-reverting)" if net_now > 0 else "negative gamma (trending)",
           "call_wall": {"qqq": call_wall, "nq": conv(call_wall)}, "put_wall": {"qqq": put_wall, "nq": conv(put_wall)},
           "flip": {"qqq": round(flip, 2) if flip else None, "nq": conv(flip) if flip else None},
           "top_strikes": top, "profile": profile, "expiries_used": sorted({round(T * 365) for *_, T in rows}), "t": int(time.time())}
    _cache["live"] = (time.time(), out)
    return out
