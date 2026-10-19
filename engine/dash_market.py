"""Market-side dashboard data: price, clock, regime gauges, liquidity map, session ranges, NQ vs ES, news timeline,
model / bias snapshots and the session prep card (contract: research/DASHBOARD_API.md).

Bars = the tail of the stored CME history (data/<SYM>_5m.csv, read from the end of the file, never the whole 17 MB)
overlaid with the live bot's freshest bars (BOT.bars_tail, Yahoo NQ=F). Fresh ES bars come from a background
subprocess job (engine/dash_data.py es_fresh) so yfinance never runs inside the server beside the bot.
"""
from __future__ import annotations

import datetime as dt
import io
import os
import threading
import time
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from . import dash_data as D

ET = ZoneInfo("America/New_York")
DATA = D.DATA
SESSIONS = [("ASIA", "Asia", 1200, 1440), ("LON", "London", 120, 300), ("ON", "Overnight", 1080, 570),
            ("NY_AM", "NY AM", 570, 690), ("LUNCH", "NY lunch", 690, 810), ("NY_PM", "NY PM", 810, 960)]
_lock = threading.Lock()
_cache: dict = {}


def _r(v, nd=2):
    if v is None:
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    if v != v or v in (float("inf"), float("-inf")):
        return None
    return round(v, nd)


def ttl(key, secs, fn):
    now = time.time()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < secs:
            return hit[1]
    val = fn()
    with _lock:
        _cache[key] = (now, val)
    return val


def _params():
    from .model import DEFAULTS
    return DEFAULTS


def _bot():
    from .live import BOT
    return BOT


def et_now(now=None):
    return dt.datetime.fromtimestamp(now or time.time(), ET)


def hhmm(m):
    m = int(m) % 1440
    return f"{m // 60:02d}:{m % 60:02d}"


def market_open(ts):
    from .live import market_open as mo
    return mo(ts)


# ------------------------------------------------------------------ bars
def _tail_csv(path, nbytes):
    """Last ~nbytes of a CSV as a DataFrame (header kept). Cached by file mtime."""
    st = os.stat(path)
    key = ("tail", path, st.st_mtime, nbytes)
    with _lock:
        hit = _cache.get(key)
    if hit:
        return hit[1]
    with open(path, "rb") as fh:
        header = fh.readline()
        if st.st_size > nbytes:
            fh.seek(st.st_size - nbytes)
            fh.readline()
        body = fh.read()
    df = pd.read_csv(io.BytesIO(header + body))
    df.columns = [c.strip().lower() for c in df.columns]
    df = df[["time", "open", "high", "low", "close", "volume"]]
    df = df[~((df["high"] == df["low"]) & (df["volume"] <= 0))]
    with _lock:
        for k in [k for k in _cache if isinstance(k, tuple) and k[:2] == ("tail", path)]:
            _cache.pop(k, None)
        _cache[key] = (time.time(), df)
    return df


def _tag(df):
    ts = pd.to_datetime(df["time"].values, unit="s", utc=True).tz_convert(ET)
    df = df.copy()
    df["mod"] = (ts.hour * 60 + ts.minute).values
    df["date"] = (ts + pd.Timedelta(hours=6)).strftime("%Y-%m-%d").values
    return df.reset_index(drop=True)


def _es_fresh_rows():
    obj = D.read_cache("es_fresh")
    age = time.time() - (obj or {}).get("computed_at", 0)
    if (obj is None or age > 300) and (obj is None or market_open(time.time())):
        D.JOBS_MGR.submit({"kind": "es_fresh"}, force=True)
    return (obj or {}).get("result", {}).get("rows") or [], (obj or {}).get("computed_at")


def bars(sym="NQ", tf="5m", nbytes=1_300_000):
    """Recent bars as a tagged DataFrame: stored tail + fresh overlay (bot tail for NQ, ES job rows for ES)."""
    path = os.path.join(DATA, f"{sym}_{tf}.csv")
    if not os.path.exists(path):
        return None
    base = _tail_csv(path, nbytes)
    extra, stamp = None, None
    if tf == "5m":
        if sym == "NQ":
            bot = _bot()
            tail = list(bot.bars_tail or [])
            if tail and (bot.cfg or {}).get("sym", "NQ") == "NQ":
                extra = pd.DataFrame(tail)[["time", "open", "high", "low", "close", "volume"]]
                stamp = (int(extra["time"].iloc[-1]), len(extra))
        elif sym == "ES":
            rows, at = _es_fresh_rows()
            if rows:
                extra = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "volume"])
                extra = extra[(extra["time"] % 300 == 0) & (extra["time"] + 300 <= time.time())]
                stamp = (at, len(extra))
    key = ("bars", sym, tf, os.path.getmtime(path), nbytes, stamp)
    with _lock:
        hit = _cache.get(key)
    if hit:
        return hit[1]
    df = base if extra is None or not len(extra) else pd.concat([base, extra]).drop_duplicates("time", keep="last")
    df = _tag(df.sort_values("time"))
    with _lock:
        for k in [k for k in _cache if isinstance(k, tuple) and k[:3] == ("bars", sym, tf)]:
            _cache.pop(k, None)
        _cache[key] = (time.time(), df)
    return df


def daily(df):
    """Per trading day OHLC (+ RTH open/close) from tagged intraday bars."""
    g = df.groupby("date", sort=True)
    out = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(), "close": g["close"].last(),
                        "bars": g["time"].size(), "t0": g["time"].first(), "t1": g["time"].last()})
    rth = df[(df["mod"] >= 570) & (df["mod"] < 960)].groupby("date")
    out["rth_open"] = rth["open"].first()
    out["rth_close"] = rth["close"].last()
    return out


def current_day():
    """Trading-day label of the session now in progress or next to start (weekends roll to Monday)."""
    return D.today_session()


def _split(df, dd):
    """(today's bars | None, completed daily frame) relative to the current session."""
    cur = current_day()
    today = df[df["date"] == cur] if cur in set(dd.index) else None
    done = dd[dd.index < cur]
    return cur, today, done


def _er(closes, n):
    if len(closes) < n + 1:
        return None
    seg = closes[-(n + 1):]
    path = float(np.abs(np.diff(seg)).sum())
    return abs(seg[-1] - seg[0]) / path if path else None


# ------------------------------------------------------------------ ticker
def ticker(n=78):
    df = bars("NQ")
    if df is None or not len(df):
        return {"status": "no_data", "message": "no NQ bars on disk"}
    dd = daily(df)
    cur, today, done = _split(df, dd)
    last = df.iloc[-1]
    prev_close = float(done["close"].iloc[-1]) if len(done) else None
    if today is None or not len(today):          # between sessions: show the last completed session
        today = df[df["date"] == df["date"].iloc[-1]]
        prev = dd[dd.index < df["date"].iloc[-1]]
        prev_close = float(prev["close"].iloc[-1]) if len(prev) else None
    px = float(last["close"])
    spark = df.tail(n)
    bot = _bot()
    return {"status": "ok", "sym": "NQ", "last": px, "t": int(last["time"]), "session": str(today["date"].iloc[0]),
            "prev_close": prev_close, "chg": _r(px - prev_close) if prev_close else None,
            "chg_pct": _r((px / prev_close - 1) * 100, 2) if prev_close else None,
            "day_high": float(today["high"].max()), "day_low": float(today["low"].min()), "day_open": float(today["open"].iloc[0]),
            "spark": [float(x) for x in spark["close"]], "spark_t0": int(spark["time"].iloc[0]), "spark_step_s": 300,
            "data_age_s": int(time.time() - (int(last["time"]) + 300)), "market_open": market_open(time.time()),
            "bot_fresh": bool(bot.bars_tail), "source": "stored CME NQ1! history + live bot bars ("
            + ("NinjaTrader" if getattr(bot, "no_yahoo", False) else "Yahoo NQ=F") + ")"}


# ------------------------------------------------------------------ clock / killzones
def _at(day: dt.date, minute: int) -> int:
    return int(dt.datetime(day.year, day.month, day.day, minute // 60, minute % 60, tzinfo=ET).timestamp())


def clock(now=None):
    now = int(now or time.time())
    p = _params()
    e = et_now(now)
    mod = e.hour * 60 + e.minute
    zones = [("London", 120, 300, False)] + [(nm, a, z, True) for nm, (a, z) in zip(("NY AM", "NY PM"), p["entry_windows"])]
    is_wd = e.weekday() < 5
    kz = []
    for name, a, z, trades in zones:
        st = "closed" if not is_wd else ("done" if mod >= z else "active" if mod >= a else "upcoming")
        kz.append({"name": name, "start_et": hhmm(a), "end_et": hhmm(z), "trades": trades, "state": st,
                   "start_t": _at(e.date(), a), "end_t": _at(e.date(), z)})
    nxt = None
    for k in range(0, 9):
        d = e.date() + dt.timedelta(days=k)
        if d.weekday() >= 5:
            continue
        for name, a, z, trades in zones:
            if not trades:
                continue
            s, f = _at(d, a), _at(d, z)
            if f > now and market_open(s + 60):
                nxt = {"name": name, "date": d.isoformat(), "start_t": s, "end_t": f, "in_s": max(0, s - now), "active": s <= now < f}
                break
        if nxt:
            break
    opn = market_open(now)
    next_open = next_close = None
    for k in range(0, 9):
        d = e.date() + dt.timedelta(days=k)
        c18, c17 = _at(d, 1080), _at(d, 1020)
        if next_open is None and not opn and c18 > now and market_open(c18 + 60):
            next_open = c18
        if next_close is None and opn and c17 > now and market_open(c17 - 60):
            next_close = c17
    return {"status": "ok", "now": now, "now_et": e.strftime("%a %H:%M"), "date_et": e.date().isoformat(), "market_open": opn,
            "next_open_t": next_open, "next_close_t": next_close, "killzones": kz, "flat_et": hhmm(p["flat_mod"]),
            "flat_t": _at(e.date(), p["flat_mod"]) if is_wd else None, "next_entry_window": nxt,
            "arm_from_et": hhmm(p.get("arm_start", 480))}


# ------------------------------------------------------------------ regime / volatility
def _vix(name):
    """Daily CBOE index closes (data/VIX_1d.csv, VXN_1d.csv). The last row can be today's partial session."""
    path = os.path.join(DATA, f"{name}_1d.csv")
    if not os.path.exists(path):
        return None
    with open(path, "rb") as fh:
        cols = [c.strip().lower() for c in fh.readline().decode().split(",")]
        size = os.path.getsize(path)
        fh.seek(max(0, size - 4000))
        if size > 4000:
            fh.readline()
        body = fh.read().decode("utf-8", "replace")
    if "date" not in cols or "close" not in cols:
        return None
    raw = pd.read_csv(io.StringIO(body), header=None, names=cols).dropna()
    raw = raw[raw["date"].astype(str).str.match(r"\d{4}-\d{2}-\d{2}")]
    if not len(raw):
        return None
    last, prev = raw.iloc[-1], raw.iloc[-2] if len(raw) > 1 else None
    return {"last": _r(last["close"]), "date": str(last["date"]), "prev_close": _r(prev["close"]) if prev is not None else None,
            "prev_date": str(prev["date"]) if prev is not None else None, "high": _r(last["high"]), "low": _r(last["low"])}


def regime():
    df = bars("NQ")
    if df is None:
        return {"status": "no_data", "message": "no NQ bars"}
    dd = daily(df)
    cur, today, done = _split(df, dd)
    p = _params()
    rng = (done["high"] - done["low"]).values
    closes = done["close"].values
    pc = np.r_[np.nan, closes[:-1]]
    tr = np.nanmax(np.vstack([done["high"].values - done["low"].values, np.abs(done["high"].values - pc),
                              np.abs(done["low"].values - pc)]), axis=0)
    adr20 = float(np.mean(rng[-20:])) if len(rng) >= 5 else None
    adr60 = float(np.mean(rng[-60:])) if len(rng) >= 21 else None
    today_rng = float(today["high"].max() - today["low"].min()) if today is not None and len(today) else None
    er10, er5 = _er(closes, 10), _er(closes, 5)
    thr = p.get("regime_er10_max") or 0.45
    lim = p.get("day_range_max") or 0
    tr5 = (df["high"] - df["low"]).values
    atr5 = float(np.mean(tr5[-14:])) if len(tr5) >= 14 else None
    recent = df[df["date"].isin(list(done.index[-20:]))]
    rth5 = recent[(recent["mod"] >= 570) & (recent["mod"] < 960)]
    base5 = float((rth5["high"] - rth5["low"]).mean()) if len(rth5) else None
    series = []
    for k in range(max(11, len(done) - 60), len(done) + 1):
        e10 = _er(closes[:k], 10)
        series.append({"date": done.index[k - 1], "er10": _r(e10, 3), "range": _r(rng[k - 1]),
                       "regime": None if e10 is None else ("trending" if e10 > thr else "rotational")})
    return {"status": "ok", "session": cur, "sessions_used": int(len(done)),
            "daily": {"atr14": _r(np.mean(tr[-14:])) if len(tr) >= 14 else None, "adr20": _r(adr20), "adr60": _r(adr60),
                      "today_range": _r(today_rng), "today_pct_adr": _r(today_rng / adr20 * 100, 1) if today_rng and adr20 else None,
                      "er5": _r(er5, 3), "er10": _r(er10, 3), "regime": None if er10 is None else ("trending" if er10 > thr else "rotational"),
                      "regime_threshold": thr, "regime_mode": p.get("regime_mode"),
                      "vol_expansion": _r(np.mean(rng[-5:]) / adr60, 3) if adr60 else None,
                      "dir5": (1 if closes[-1] > closes[-6] else -1) if len(closes) >= 6 else None,
                      "day_range_guard": {"limit_x_adr": lim, "used_x_adr": _r(today_rng / adr20, 2) if today_rng and adr20 else None,
                                          "blocks_entries": bool(lim and today_rng and adr20 and today_rng / adr20 >= lim)}},
            "intraday": {"atr14_5m": _r(atr5), "rth_avg_5m_range_20d": _r(base5),
                         "atr14_5m_pct_of_20d": _r(atr5 / base5 * 100, 1) if atr5 and base5 else None},
            "vix": {"VIX": _vix("VIX"), "VXN": _vix("VXN")}, "series": series,
            "note": "regime = 10-session efficiency ratio of completed sessions (engine rule: > threshold = trending, half size)"}


# ------------------------------------------------------------------ key levels + liquidity map
def _levels(df, dd, cur, today):
    """Key ICT levels for the current (or next) session with swept flags."""
    days = list(dd.index)
    prev_days = [d for d in days if d < cur]
    out = []
    if not prev_days:
        return out
    pd_ = dd.loc[prev_days[-1]]
    tb = today if today is not None else df.iloc[0:0]

    def swept(level, side, sub):
        if sub is None or not len(sub):
            return False
        return bool(sub["high"].max() > level) if side == "H" else bool(sub["low"].min() < level)

    def add(label, price, side, sub, kind="key", formed=None):
        if price is None or price != price:
            return
        out.append({"label": label, "price": float(price), "side": side, "kind": kind, "swept": swept(float(price), side, sub),
                    "formed": formed})
    add("PDH", pd_["high"], "H", tb, formed=prev_days[-1])
    add("PDL", pd_["low"], "L", tb, formed=prev_days[-1])
    add("PDC", pd_["close"], "C", None, formed=prev_days[-1])
    cw = dt.date.fromisoformat(cur).isocalendar()[:2]
    pw = [d for d in prev_days if dt.date.fromisoformat(d).isocalendar()[:2] != cw]
    if pw:
        wk = dt.date.fromisoformat(pw[-1]).isocalendar()[:2]
        sel = [d for d in pw if dt.date.fromisoformat(d).isocalendar()[:2] == wk]
        this_week = df[df["date"].isin([d for d in days if dt.date.fromisoformat(d).isocalendar()[:2] == cw])]
        add("PWH", dd.loc[sel, "high"].max(), "H", this_week, formed=sel[-1])
        add("PWL", dd.loc[sel, "low"].min(), "L", this_week, formed=sel[-1])
    if len(tb):
        on = tb[(tb["mod"] >= 1080) | (tb["mod"] < 570)]
        asia = tb[tb["mod"] >= 1200]
        lon = tb[(tb["mod"] >= 120) & (tb["mod"] < 300)]
        after = lambda m0: tb[(tb["mod"] >= m0) & (tb["mod"] < 1080)]
        if len(on):
            add("ONH", on["high"].max(), "H", after(570), kind="session")
            add("ONL", on["low"].min(), "L", after(570), kind="session")
        if len(asia):
            add("ASH", asia["high"].max(), "H", after(0), kind="session")
            add("ASL", asia["low"].min(), "L", after(0), kind="session")
        if len(lon):
            add("LOH", lon["high"].max(), "H", after(300), kind="session")
            add("LOL", lon["low"].min(), "L", after(300), kind="session")
        mid = tb[tb["mod"] == 0]
        if len(mid):
            add("MIDNIGHT_OPEN", mid["open"].iloc[0], "C", None, kind="open")
        rth = tb[tb["mod"] >= 570]
        rth = rth[rth["mod"] < 1080]
        if len(rth):
            add("RTH_OPEN", rth["open"].iloc[0], "C", None, kind="open")
    return out


def liquidity(max_n=30):
    df = bars("NQ")
    if df is None:
        return {"status": "no_data", "message": "no NQ bars"}
    dd = daily(df)
    cur, today, done = _split(df, dd)
    px = float(df["close"].iloc[-1])
    rng = (done["high"] - done["low"]).values
    adr = float(np.mean(rng[-20:])) if len(rng) >= 5 else None
    levels = _levels(df, dd, cur, today)
    for lv in levels:
        lv["dist"] = _r(lv["price"] - px)
        lv["dist_adr"] = _r((lv["price"] - px) / adr, 2) if adr else None
    bot = _bot()
    st = bot.state or {}
    pools = []
    for q in (st.get("active_pools") or [])[:200]:
        pools.append({"label": q.get("label"), "price": _r(q.get("price")), "side": q.get("side"), "kinds": q.get("kinds"),
                      "strength": q.get("strength"), "eq": q.get("eq"), "formed_t": q.get("t0"),
                      "dist": _r(q.get("price") - px), "dist_adr": _r((q.get("price") - px) / adr, 2) if adr else None})
    pools.sort(key=lambda q: abs(q["dist"] or 0))
    pools = sorted(pools[:max_n], key=lambda q: -(q["price"] or 0))
    cand = [x for x in levels if x["kind"] != "open" and x["side"] != "C" and not x["swept"]] + pools
    above = min((x for x in cand if (x["dist"] or 0) > 0), key=lambda x: x["dist"], default=None)
    below = max((x for x in cand if (x["dist"] or 0) < 0), key=lambda x: x["dist"], default=None)
    short = lambda x: None if x is None else {"label": x["label"], "price": x["price"], "dist": x["dist"]}
    return {"status": "ok", "price": px, "t": int(df["time"].iloc[-1]), "session": cur, "adr20": _r(adr),
            "levels": sorted(levels, key=lambda x: -x["price"]), "pools": pools,
            "nearest": {"above": short(above), "below": short(below)},
            "source": "live engine pools + levels computed from bars" if st else "levels computed from bars (bot not polling: no engine pools)"}


# ------------------------------------------------------------------ session ranges
def _sess_slice(day_df, a, z):
    m = day_df["mod"]
    sel = (m >= a) | (m < z) if a > z else ((m >= a) & (m < z))
    return day_df[sel]


def sessions():
    df = bars("NQ")
    if df is None:
        return {"status": "no_data", "message": "no NQ bars"}
    dd = daily(df)
    cur, today, done = _split(df, dd)
    show = cur if today is not None and len(today) else df["date"].iloc[-1]
    tb = df[df["date"] == show]
    hist = list(done.index[-20:])
    now = time.time()
    d = dt.date.fromisoformat(show)
    rows = []
    for key, name, a, z in SESSIONS:
        s = _sess_slice(tb, a, z)
        avgs = []
        for h in hist:
            hs = _sess_slice(df[df["date"] == h], a, z)
            if len(hs):
                avgs.append(float(hs["high"].max() - hs["low"].min()))
        eve = d - dt.timedelta(days=1)            # evening minutes (>= 18:00) of trading day d fall on the prior calendar day
        start = _at(eve, a) if a >= 1080 else _at(d, a)
        if a > z or z == 1440:                    # wraps past midnight (Overnight 18:00-09:30, Asia 20:00-24:00)
            end = _at(d, z % 1440)
        else:
            end = _at(eve, z) if a >= 1080 else _at(d, z)
        state = "done" if now >= end else "active" if now >= start else "upcoming"
        hi = float(s["high"].max()) if len(s) else None
        lo = float(s["low"].min()) if len(s) else None
        rngv = hi - lo if hi is not None else None
        avg = float(np.mean(avgs)) if avgs else None
        rows.append({"key": key, "name": name, "start_et": hhmm(a), "end_et": hhmm(z), "start_t": start, "end_t": end, "state": state,
                     "high": hi, "low": lo, "range": _r(rngv), "avg20": _r(avg), "pct_of_avg": _r(rngv / avg * 100, 1) if rngv and avg else None,
                     "bars": int(len(s))})
    return {"status": "ok", "date": show, "is_current": show == cur, "sessions": rows,
            "day": {"open": float(tb["open"].iloc[0]), "high": float(tb["high"].max()), "low": float(tb["low"].min()),
                    "range": _r(tb["high"].max() - tb["low"].min()), "last": float(tb["close"].iloc[-1])} if len(tb) else None}


# ------------------------------------------------------------------ NQ vs ES
def intermarket(days=60):
    nq5, es5 = bars("NQ"), bars("ES")
    if nq5 is None or es5 is None:
        return {"status": "no_data", "message": "ES or NQ 5m history missing"}
    nqh = _tag(_tail_csv(os.path.join(DATA, "NQ_1h.csv"), 400_000))
    esh = _tag(_tail_csv(os.path.join(DATA, "ES_1h.csv"), 400_000))
    cn = pd.concat([daily(nqh)["close"], daily(nq5)["close"]]).groupby(level=0).last()
    ce = pd.concat([daily(esh)["close"], daily(es5)["close"]]).groupby(level=0).last()
    j = pd.DataFrame({"nq": cn, "es": ce}).dropna().sort_index()
    ret = j.pct_change().dropna()
    corr = lambda n: _r(ret.tail(n)["nq"].corr(ret.tail(n)["es"]), 3) if len(ret) >= min(n, 10) else None
    beta = None
    if len(ret) >= 20:
        t = ret.tail(60)
        beta = _r(t["nq"].cov(t["es"]) / t["es"].var(), 3) if t["es"].var() > 0 else None
    seg = j.tail(days)
    rs = [{"date": d, "nq": _r(r.nq / seg["nq"].iloc[0] * 100, 2), "es": _r(r.es / seg["es"].iloc[0] * 100, 2),
           "ratio": _r((r.nq / seg["nq"].iloc[0]) / (r.es / seg["es"].iloc[0]), 4)} for d, r in seg.iterrows()]
    cur = current_day()
    today = {}
    smt = []
    ddn, dde = daily(nq5), daily(es5)
    show = cur if cur in ddn.index else ddn.index[-1]
    tn, te = nq5[nq5["date"] == show], es5[es5["date"] == show]
    pn = ddn[ddn.index < show]
    pe = dde[dde.index < show]
    lag = None
    if len(tn) and len(te):                       # compare over the common time range only (ES history can lag NQ)
        common = min(int(tn["time"].iloc[-1]), int(te["time"].iloc[-1]))
        lag = int(tn["time"].iloc[-1]) - int(te["time"].iloc[-1])
        tn, te = tn[tn["time"] <= common], te[te["time"] <= common]
    if len(tn) and len(te) and len(pn) and len(pe):
        cn_, ce_ = float(tn["close"].iloc[-1]), float(te["close"].iloc[-1])
        nqc, esc = (cn_ / pn["close"].iloc[-1] - 1) * 100, (ce_ / pe["close"].iloc[-1] - 1) * 100
        today = {"session": show, "nq_chg_pct": _r(nqc, 2), "es_chg_pct": _r(esc, 2), "spread_pct": _r(nqc - esc, 2),
                 "leader": "NQ" if nqc > esc else "ES", "compared_to_t": int(tn["time"].iloc[-1]), "es_lag_s": lag,
                 "note": "both measured to the last bar they share" if lag else None}
        m = pd.merge(tn[["time", "close"]], te[["time", "close"]], on="time", suffixes=("_n", "_e"))
        if len(m) > 12:
            today["intraday_5m_corr"] = _r(m["close_n"].pct_change().corr(m["close_e"].pct_change()), 3)
        lv_n = {x["label"]: x for x in _levels(nq5, ddn, show, tn)}
        lv_e = {x["label"]: x for x in _levels(es5, dde, show, te)}
        for lab in ("PDH", "PDL", "PWH", "PWL", "ONH", "ONL", "ASH", "ASL", "LOH", "LOL"):
            if lab in lv_n and lab in lv_e:
                a, b = lv_n[lab]["swept"], lv_e[lab]["swept"]
                note = None
                if a != b:
                    side = lv_n[lab]["side"]
                    who, held = ("NQ", "ES") if a else ("ES", "NQ")
                    note = f"{who} took {lab}, {held} held: {'bearish' if side == 'H' else 'bullish'} SMT"
                smt.append({"level": lab, "nq_swept": a, "es_swept": b, "divergence": a != b, "note": note})
    es_rows, es_at = _es_fresh_rows()
    return {"status": "ok", "today": today, "corr": {"d20": corr(20), "d60": corr(60)}, "beta_60d": beta, "rs_series": rs,
            "smt": {"today": smt}, "as_of": {"nq": int(nq5["time"].iloc[-1]), "es": int(es5["time"].iloc[-1]), "es_fresh_fetch": es_at},
            "es_source": "stored CME ES history + Yahoo ES=F (fetched in a background job)" if es_rows else "stored CME ES history",
            "days": int(len(j))}


# ------------------------------------------------------------------ news / blackouts
def news(days=7, impact="medium", now=None):
    from . import calendar_week as cw
    now = int(now or time.time())
    p = _params()
    start = et_now(now).date()
    end = start + dt.timedelta(days=max(1, min(int(days), 31)))

    def load():
        try:
            return cw.dashboard_rows(start, end, impact, use_feed=True)
        except Exception:
            return cw.dashboard_rows(start, end, impact, use_feed=False)
    rows = ttl(("news", start.isoformat(), end.isoformat(), impact), 600, load)
    before, after = int(p.get("news_before_min", 15)), int(p.get("news_after_min", 30))
    evs = []
    for r in rows:
        x = dict(r)
        if r["impact"] == "high":
            x["blackout_start_t"] = r["t"] - before * 60
            x["blackout_end_t"] = r["t"] + after * 60
            x["flatten_t"] = r["t"] - int(p.get("news_flatten_min") or 0) * 60 if p.get("news_flatten_min") else None
        evs.append(x)
    hi = [e for e in evs if e["impact"] == "high"]
    nxt = next((e for e in hi if e["blackout_end_t"] > now), None)
    in_bo = [e for e in hi if e["blackout_start_t"] <= now < e["blackout_end_t"]]
    plans = []
    d = start
    while d <= end:
        if d.weekday() < 5:
            risk, action = cw._day_plan(evs, d.isoformat())
            plans.append({"date": d.isoformat(), "weekday": d.strftime("%a"), "risk": risk, "action": action,
                          "n_high": sum(1 for e in hi if e["date"] == d.isoformat()),
                          "n_events": sum(1 for e in evs if e["date"] == d.isoformat()), "notes": cw.DAY_NOTES.get(d.isoformat()),
                          "fomc_pm_off": any(e.get("fomc_pm_off") for e in hi if e["date"] == d.isoformat())})
        d += dt.timedelta(days=1)

    def g():
        try:
            from . import news as nw
            r = nw.guard(now=now, params={k: p[k] for k in ("news_before_min", "news_after_min", "fomc_pm_off", "vix_max") if k in p},
                         vol={}, events=nw.upcoming_events(now))
            return {"allowed": r["allowed"], "reasons": r["reasons"]}
        except Exception as e:
            return {"allowed": None, "reasons": [], "error": str(e)[:200]}
    return {"status": "ok" if evs else "no_data", "now": now, "from": start.isoformat(), "to": end.isoformat(), "impact": impact,
            "events": evs, "days": plans, "in_blackout": bool(in_bo), "current_blackout": in_bo[0] if in_bo else None,
            "next_blackout": None if not nxt else {"event": nxt["event"], "t": nxt["t"], "start_t": nxt["blackout_start_t"],
                                                   "end_t": nxt["blackout_end_t"], "in_s": max(0, nxt["blackout_start_t"] - now),
                                                   "date": nxt["date"], "time_et": nxt["time_et"], "killzones_hit": nxt.get("killzones_hit")},
            "next_event": next(({"event": e["event"], "t": e["t"], "impact": e["impact"], "in_s": e["t"] - now} for e in evs if e["t"] > now), None),
            "guard": ttl(("guard", now // 60), 60, g), "rules": {"before_min": before, "after_min": after,
                                                                 "flatten_min": p.get("news_flatten_min"), "fomc_pm_off": p.get("fomc_pm_off")},
            **({} if evs else {"message": "no events in the calendar for this range"})}


# ------------------------------------------------------------------ model + bias (live engine snapshot)
FLOW = ["OUTSIDE KILLZONE", "WAITING FOR SWEEP", "ARMED - HUNTING IFVG", "ORDER PENDING", "IN TRADE", "DONE FOR DAY"]


def model():
    bot = _bot()
    st = bot.state
    if not st:
        return {"status": "no_data", "running": bool(bot.running),
                "message": "the live engine has not completed a poll yet (bot stopped or just started)"}
    p = _params()
    now = time.time()
    px = float(st.get("price") or 0)
    setups = {}
    for side, s in (st.get("setups") or {}).items():
        setups[side] = None if not s else {**s, "age_min": int((now - s["arm_t"]) / 60) if s.get("arm_t") else None,
                                            "dist_from_ext": _r(px - s["ext"]) if s.get("ext") is not None else None}
    pos = st.get("position")
    position = None
    if pos:
        entry, stop0 = float(pos.get("entry") or 0), float(pos.get("stop0", pos.get("stop")) or 0)
        risk = abs(entry - stop0) or None
        d = int(pos.get("dir") or 1)
        position = {k: pos.get(k) for k in ("dir", "entry", "stop", "stop0", "target", "qty", "qty_label", "entry_t", "grade", "trigger",
                                            "target_label", "pools", "exit_signal")}
        position.update(live_r=_r((px - entry) * d / risk, 3) if risk else None, to_stop_pts=_r((px - float(pos.get("stop") or stop0)) * d),
                        to_target_pts=_r((float(pos.get("target") or 0) - px) * d) if pos.get("target") else None,
                        mins_in_trade=int((now - pos["entry_t"]) / 60) if pos.get("entry_t") else None)
    ms = st.get("model_state")
    return {"status": "ok", "running": bool(bot.running), "t": st.get("t"), "price": px, "model_state": ms, "flow": FLOW,
            "flow_index": FLOW.index(ms) if ms in FLOW else None, "setups": setups, "pending": st.get("pending"), "position": position,
            "day": {"pnl": st.get("day_pnl"), "trades": st.get("day_trades"), "max_trades": p.get("max_trades_day"),
                    "daily_stop": p.get("daily_max_loss"), "stop_after_win": p.get("stop_after_win")},
            "engine_account": {"balance": st.get("balance"), "mll": st.get("mll"),
                               "note": "the live engine's own simulated account over its rolling window; not the MFFU balance"},
            "trend": {"h1": st.get("h1_trend"), "m15": st.get("m15_trend")}, "last_poll": bot.last_poll}


def bias():
    bot = _bot()
    st = bot.state
    if not st:
        return {"status": "no_data", "message": "the live engine has not completed a poll yet"}
    m = st.get("mtf") or {}
    dr = m.get("dealing_range")
    if dr:
        dr = {**dr, "zone": "premium" if (dr.get("pos") or 0) > 0.5 else "discount",
              "outside": bool((dr.get("pos") or 0) < 0 or (dr.get("pos") or 0) > 1)}
    return {"status": "ok", "t": st.get("t"), "price": st.get("price"), "net": m.get("net"), "tfs": m.get("tfs") or [],
            "structure": {**(m.get("structure") or {}), "h1_protected_low": st.get("h1_protected_low"),
                          "h1_protected_high": st.get("h1_protected_high"), "m15_protected_low": st.get("m15_protected_low"),
                          "m15_protected_high": st.get("m15_protected_high")},
            "dealing_range": dr, "midnight_open": m.get("midnight_open"), "open_loc": st.get("open_loc"),
            "profile": st.get("profile")}


# ------------------------------------------------------------------ session prep
def prep(now=None):
    now = int(now or time.time())
    p = _params()
    e = et_now(now)
    d = e.date()
    if d.weekday() >= 5 or e.hour * 60 + e.minute >= p["flat_mod"]:
        d += dt.timedelta(days=1)
        while d.weekday() >= 5:
            d += dt.timedelta(days=1)
    day = d.isoformat()
    nw = news(days=max(1, (d - e.date()).days + 1), impact="low", now=now)
    plan = next((x for x in nw["days"] if x["date"] == day), None)
    df = bars("NQ")
    lv, reg = [], {}
    if df is not None:
        dd = daily(df)
        done = dd[dd.index < day]
        today = df[df["date"] == day]
        lv = [{"label": x["label"], "price": x["price"], "swept": x["swept"]} for x in _levels(df, dd, day, today if len(today) else None)]
        closes = done["close"].values
        rng = (done["high"] - done["low"]).values
        er10 = _er(closes, 10)
        thr = p.get("regime_er10_max") or 0.45
        reg = {"er10": _r(er10, 3), "regime": None if er10 is None else ("trending" if er10 > thr else "rotational"),
               "provisional": bool(len(done)) and done.index[-1] == current_day() and market_open(time.time()),
               "adr20": _r(np.mean(rng[-20:])) if len(rng) >= 5 else None,
               "sizing": "half size (trending regime)" if er10 is not None and er10 > thr and p.get("regime_mode") == "half" else "normal"}
    evs = [x for x in nw["events"] if x["date"] == day]
    bot = _bot()
    chk = [f"Paper bot {'RUNNING' if bot.running else 'STOPPED'} (adapter={(bot.cfg or {}).get('adapter', '-')})",
           "TradingView alerts active on the MNQ chart (live orders come from the Pine strategy)",
           f"Blackouts pasted into the Pine input for the week of {(d - dt.timedelta(days=d.weekday())).isoformat()}"]
    if any(x["impact"] == "high" for x in evs):
        chk.append("High-impact release today: confirm the Pine blackout covers " +
                   ", ".join(f"{x['time_et']} {x['event']}" for x in evs if x["impact"] == "high"))
    if plan and plan.get("fomc_pm_off"):
        chk.append("FOMC day: no PM session")
    return {"status": "ok", "date": day, "weekday": d.strftime("%a"), "risk": plan["risk"] if plan else None,
            "action": plan["action"] if plan else None, "notes": plan["notes"] if plan else None, "events": evs, **reg,
            "levels": lv, "killzones": [f"{hhmm(a)}-{hhmm(z)}" for a, z in p["entry_windows"]], "flat_et": hhmm(p["flat_mod"]),
            "max_trades": p.get("max_trades_day"), "daily_stop": p.get("daily_max_loss"), "checklist": chk}
