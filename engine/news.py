"""News, calendar and volatility layer.

Live (dashboard + live bot):
  * Forex Factory weekly calendar (nfs.faireconomy.media ff_calendar_thisweek.json) - every currency, impact, forecast, previous
  * Headlines: ForexLive, CNBC markets, MarketWatch, Investing.com, Federal Reserve press releases (RSS), keyword-flagged
  * Volatility: VIX and VXN (Nasdaq-100 volatility) levels + 1-year percentile, NQ realized range vs its 20-day average
  * Mega-cap earnings dates (the stocks that move NQ)
Historical (backtests): data/news/events.csv (build_news.py) + data/VIX_1d.csv / VXN_1d.csv daily closes.

Trade guard = the single answer to "may the bot open a trade right now, and if not, why?"
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

import pandas as pd

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
NEWS = os.path.join(DATA, "news")
os.makedirs(NEWS, exist_ok=True)
ET_TZ = ZoneInfo("America/New_York")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
FEEDS = {
    "ForexLive": "https://www.forexlive.com/feed",
    "CNBC Markets": "https://www.cnbc.com/id/20910258/device/rss/rss.html",
    "MarketWatch": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "Investing.com": "https://www.investing.com/rss/news_25.rss",
    "Federal Reserve": "https://www.federalreserve.gov/feeds/press_all.xml",
}
MEGACAPS = ["NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "META", "AVGO", "TSLA", "NFLX", "AMD"]
HOT = [r"\bfed\b", "powell", "fomc", "rate (cut|hike|decision)", r"\bcpi\b", "inflation", "payrolls", r"\bjobs\b", "tariff",
       "sanction", r"\bwar\b", "attack", "missile", "shutdown", "default", "downgrade", "nvidia", "earnings", "treasury",
       "yields?", "recession", "bank", "emergency", "nasdaq", "s&p", "selloff", "plunge", "surge", "crash", "trump", "china"]
HOT_RE = re.compile("|".join(HOT), re.I)

_cache: dict = {}
_lock = threading.Lock()
_BG = {"on": False, "inflight": set(), "warm": {}}


def background_refresh(on: bool = True):
    """The PC bot (engine/live.py, the real bot only): an expired entry (the calendar every 30 min, VIX / VXN every 15 min:
    downloads with 15-30 s timeouts) is served at once from the last copy and downloaded again in a background thread, so a
    slow or hanging network never sits inside a poll before LIT's routing. The first read still waits (nothing to serve).
    Off (the default: cloud monitor, tools, tests): the caller downloads, as before."""
    _BG["on"] = bool(on)
    # the calendar download rewrites ff_archive.csv when it changed: parse it again in that thread (the entry guard's
    # news_hit and upcoming_events read these two)
    _BG["warm"] = {"ff": [(historical_events, ("high",)), (historical_events, ("high", "medium"))]}


def _refresh(key, fn):
    try:
        val = fn()
        with _lock:
            _cache[key] = (time.time(), val)
        for args in _BG["warm"].get(key, ()):             # re-read the files the download rewrote, here, not in the poll
            try:
                args[0](*args[1:])
            except Exception:
                pass
    except Exception:
        pass                                              # the last copy stays; the next read tries again
    finally:
        with _lock:
            _BG["inflight"].discard(key)


def _cached(key, ttl, fn):
    with _lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < ttl:
            return hit[1]
        if hit and _BG["on"]:
            if key not in _BG["inflight"]:
                _BG["inflight"].add(key)
                threading.Thread(target=_refresh, args=(key, fn), name=f"news-refresh-{key}", daemon=True).start()
            return hit[1]
    val = fn()
    with _lock:
        _cache[key] = (time.time(), val)
    return val


def _get(url, timeout=15):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


# ------------------------------------------------------------------ live calendar (Forex Factory)
def ff_calendar():
    """This week's calendar for every currency. Cached 30 min (the feed asks not to be hammered)."""
    path = os.path.join(NEWS, "ff_thisweek.json")

    def load():
        try:
            raw = _get(FF_URL)
            open(path, "wb").write(raw)
        except Exception:
            raw = open(path, "rb").read() if os.path.exists(path) else b"[]"
        out = []
        for e in json.loads(raw.decode("utf-8", "ignore") or "[]"):
            try:
                t = dt.datetime.fromisoformat(e["date"])
            except Exception:
                continue
            out.append({"t": int(t.timestamp()), "time_et": t.astimezone(ET_TZ).strftime("%a %b %d %H:%M"),
                        "currency": e.get("country", ""), "impact": (e.get("impact") or "").lower(), "event": e.get("title", ""),
                        "forecast": e.get("forecast", ""), "previous": e.get("previous", ""), "actual": e.get("actual", ""),
                        "source": "Forex Factory"})
        out = sorted(out, key=lambda x: x["t"])
        _archive(out)
        return out
    return _cached("ff", 1800, load)


def _archive(evs):
    """Keep every USD high/medium event the live feed ever showed, so history builds itself going forward."""
    path = os.path.join(NEWS, "ff_archive.csv")
    rows = [{"date": dt.datetime.fromtimestamp(e["t"], ET_TZ).strftime("%Y-%m-%d"),
             "time_et": dt.datetime.fromtimestamp(e["t"], ET_TZ).strftime("%H:%M"), "event": e["event"],
             "impact": e["impact"], "source": "forexfactory"} for e in evs if e["currency"] == "USD" and e["impact"] in ("high", "medium")]
    if not rows:
        return
    df = pd.DataFrame(rows)
    old = None
    if os.path.exists(path):
        with open(path, encoding="utf-8", errors="replace", newline="") as fh:
            old = fh.read()
        df = pd.concat([pd.read_csv(path), df])
    text = df.drop_duplicates(["date", "time_et", "event"]).sort_values(["date", "time_et"]).to_csv(index=False)
    if text != old:                       # unchanged: not rewritten (its time stays, historical_events keeps its parse)
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)


# ------------------------------------------------------------------ historical calendar (backtests)
_hist_cache: dict = {}


def historical_events(impacts=("high",)):
    """Official calendar (events.csv) + everything the live feed has archived. One row per (date, time) slot."""
    paths = [os.path.join(NEWS, f) for f in ("events.csv", "ff_archive.csv") if os.path.exists(os.path.join(NEWS, f))]
    if not paths:
        return []
    key = (tuple(impacts), tuple((pth, os.path.getmtime(pth)) for pth in paths))
    if key in _hist_cache:
        return _hist_cache[key]
    df = pd.concat([pd.read_csv(pth) for pth in paths])
    df = df[df["impact"].isin(impacts)].drop_duplicates(["date", "time_et", "event"])
    out = []
    for r in df.itertuples():
        hh, mm = map(int, str(r.time_et).split(":")[:2])
        y, mo, d = map(int, r.date.split("-"))
        t = dt.datetime(y, mo, d, hh, mm, tzinfo=ET_TZ)
        out.append({"t": int(t.timestamp()), "date": r.date, "time_et": r.time_et, "event": r.event, "impact": r.impact,
                    "currency": "USD", "source": r.source})
    out.sort(key=lambda e: e["t"])
    _hist_cache[key] = out
    return out


def vix_prev_close(name="VIX"):
    """date -> PREVIOUS session's close (what a trader knows before the open; no lookahead)."""
    path = os.path.join(DATA, f"{name}_1d.csv")
    if not os.path.exists(path):
        return {}
    df = pd.read_csv(path)
    closes = df["close"].astype(float).tolist()
    dates = df["date"].astype(str).tolist()
    return {dates[k]: closes[k - 1] for k in range(1, len(dates))}


def upcoming_events(now=None, days=7):
    """USD high/medium events ahead: live FF feed merged with the historical calendar (covers FF outages)."""
    now = now or int(time.time())
    ev = [e for e in ff_calendar() if e["currency"] == "USD" and e["impact"] in ("high", "medium")]
    seen = {(e["t"] // 600, e["event"][:10].lower()) for e in ev}
    for e in historical_events(("high", "medium")):
        if now - 3600 <= e["t"] <= now + days * 86400 and (e["t"] // 600, e["event"][:10].lower()) not in seen:
            ev.append({**e, "time_et": dt.datetime.fromtimestamp(e["t"], ET_TZ).strftime("%a %b %d %H:%M")})
    return sorted([e for e in ev if e["t"] >= now - 3600], key=lambda x: x["t"])


# ------------------------------------------------------------------ headlines
def headlines(limit=60):
    def load():
        items = []
        for src, url in FEEDS.items():
            try:
                root = ET.fromstring(_get(url, 8))
            except Exception:
                continue
            for it in root.iter("item"):
                title = (it.findtext("title") or "").strip()
                link = (it.findtext("link") or "").strip()
                pub = it.findtext("pubDate") or it.findtext("{http://purl.org/dc/elements/1.1/}date") or ""
                try:
                    ts = int(pd.Timestamp(pub).timestamp()) if pub else 0
                except Exception:
                    ts = 0
                if title:
                    items.append({"t": ts, "source": src, "title": title, "link": link, "hot": bool(HOT_RE.search(title))})
        items.sort(key=lambda x: -x["t"])
        return items[:limit]
    return _cached("headlines", 300, load)


# ------------------------------------------------------------------ volatility
CBOE_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/{name}_History.csv"


def _cboe_parse(raw: bytes) -> pd.DataFrame:
    """CBOE's index history file (DATE,OPEN,HIGH,LOW,CLOSE with MM/DD/YYYY dates) -> date-indexed open/high/low/close."""
    import io
    df = pd.read_csv(io.BytesIO(raw))
    df.columns = [str(c).strip().lower() for c in df.columns]
    df["date"] = pd.to_datetime(df["date"], format="mixed").dt.strftime("%Y-%m-%d")
    df = df.set_index("date")[["open", "high", "low", "close"]].apply(pd.to_numeric, errors="coerce").dropna()
    return df[df["close"] > 0]


def _cboe_daily(name, path=None, fetch=None):
    """VIX / VXN daily closes from CBOE's own history file (no Yahoo, owner 2026-10-19; engine/pcbars.py). Same closes as
    Yahoo's ^VIX (Yahoo republishes CBOE's). New dates are added to data/<name>_1d.csv; stored rows are kept. A failed
    download keeps the stored file."""
    path = path or os.path.join(DATA, f"{name}_1d.csv")
    try:
        raw = (fetch or (lambda u: urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30).read()))(
            CBOE_URL.format(name=name))
        df = _cboe_parse(raw)
        if not len(df):
            raise ValueError("empty CBOE file")
        df.index.name = "date"
        if os.path.exists(path):
            old = pd.read_csv(path, index_col="date")
            # CBOE's rows win for the last 10 stored dates (a partial "today" row written during a session gets its final
            # close) and add every newer date; older stored rows are never rewritten
            cut = sorted(old.index.astype(str))[-10] if len(old) >= 10 else ""
            new = df[df.index >= cut]
            df = pd.concat([old[~old.index.isin(new.index)], new]).sort_index()
        tmp = path + ".tmp"
        df.to_csv(tmp)
        from .fsutil import replace as _fs_replace   # retried: Windows / OneDrive lock the target a moment
        _fs_replace(tmp, path)
    except Exception:
        df = pd.read_csv(path, index_col="date") if os.path.exists(path) else pd.DataFrame()
    return df


def _yf_daily(sym, name):
    path = os.path.join(DATA, f"{name}_1d.csv")
    try:
        from . import pcbars
        if pcbars.no_yahoo():
            return _cboe_daily(name, path)
    except ImportError:
        pass
    try:
        import yfinance as yf
        df = yf.download(sym, period="2y" if os.path.exists(path) else "5y", interval="1d", progress=False, auto_adjust=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.rename(columns=str.lower)[["open", "high", "low", "close"]].dropna()
        df.index = pd.to_datetime(df.index).strftime("%Y-%m-%d")
        df.index.name = "date"
        if os.path.exists(path):
            old = pd.read_csv(path, index_col="date")
            df = pd.concat([old[~old.index.isin(df.index)], df]).sort_index()
        df.to_csv(path)
    except Exception:
        df = pd.read_csv(path, index_col="date") if os.path.exists(path) else pd.DataFrame()
    return df


def volatility():
    def load():
        out = {}
        for sym, name in (("^VIX", "VIX"), ("^VXN", "VXN")):
            df = _yf_daily(sym, name)
            if df.empty:
                continue
            c = df["close"].astype(float)
            last = float(c.iloc[-1])
            yr = c.iloc[-252:]
            out[name] = {"last": round(last, 2), "date": df.index[-1], "pct_1y": round(float((yr <= last).mean() * 100), 1),
                         "avg_1y": round(float(yr.mean()), 2), "chg_1d": round(float(c.iloc[-1] - c.iloc[-2]), 2) if len(c) > 1 else 0.0,
                         "history": [{"date": d, "close": round(float(v), 2)} for d, v in c.iloc[-120:].items()]}
        v = out.get("VXN", out.get("VIX"))
        regime = "unknown"
        if v:
            regime = "extreme" if v["pct_1y"] >= 95 or (out.get("VIX", {}).get("last", 0) >= 30) else \
                "elevated" if v["pct_1y"] >= 75 else "calm" if v["pct_1y"] <= 20 else "normal"
        out["regime"] = regime
        return out
    return _cached("vol", 900, load)


def nq_range_state(bars):
    """Today's NQ high-low range vs the average full-day range of the last 20 trading days."""
    if bars is None or len(bars) == 0:
        return None
    df = pd.DataFrame({"d": bars.date_str, "h": bars.h, "l": bars.l})
    rng = df.groupby("d").agg(h=("h", "max"), l=("l", "min"))
    rng["r"] = rng["h"] - rng["l"]
    if len(rng) < 3:
        return None
    today = float(rng["r"].iloc[-1])
    adr = float(rng["r"].iloc[-21:-1].mean())
    return {"today_range": round(today, 2), "adr20": round(adr, 2), "ratio": round(today / adr, 2) if adr else None, "date": rng.index[-1]}


def earnings():
    def load():
        out = []
        from . import pcbars
        if pcbars.no_yahoo():                 # megacap earnings dates came from Yahoo: off with no_yahoo
            return out
        try:
            import yfinance as yf
            for s in MEGACAPS:
                try:
                    cal = yf.Ticker(s).calendar
                    d = (cal or {}).get("Earnings Date") if isinstance(cal, dict) else None
                    if d:
                        out.append({"symbol": s, "date": str(d[0])})
                except Exception:
                    continue
        except Exception:
            pass
        return sorted(out, key=lambda x: x["date"])
    return _cached("earnings", 6 * 3600, load)


# ------------------------------------------------------------------ the trade guard
def guard(now=None, params=None, vol=None, events=None):
    """Can the bot open a new trade at `now`? Returns allowed + every reason it is blocked + what's next."""
    p = {"news_before_min": 15, "news_after_min": 30, "fomc_pm_off": True, "vix_max": 0.0, **(params or {})}
    now = now or int(time.time())
    events = events if events is not None else upcoming_events(now)
    reasons = []
    for e in events:
        if e.get("impact") != "high":
            continue
        if e["t"] - p["news_before_min"] * 60 <= now <= e["t"] + p["news_after_min"] * 60:
            reasons.append(f"News blackout: {e['event']} at {dt.datetime.fromtimestamp(e['t'], ET_TZ):%H:%M} ET")
    et_now = dt.datetime.fromtimestamp(now, ET_TZ)
    if p["fomc_pm_off"] and et_now.hour >= 13:
        for e in events:
            if "FOMC" in e["event"] and dt.datetime.fromtimestamp(e["t"], ET_TZ).date() == et_now.date():
                reasons.append("FOMC day: no afternoon trades")
                break
    vol = vol if vol is not None else volatility()
    vix = vol.get("VIX", {}).get("last") if vol else None
    if p["vix_max"] and vix and vix > p["vix_max"]:
        reasons.append(f"VIX {vix} above limit {p['vix_max']}")
    nxt = next((e for e in events if e["t"] > now and e.get("impact") == "high"), None)
    return {"allowed": not reasons, "reasons": reasons, "regime": vol.get("regime") if vol else None,
            "next_high": nxt, "now": now}
