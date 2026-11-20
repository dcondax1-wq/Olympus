"""PREMARKET BRIEF (day-brief 2026-11-20): the "thinking before the trade" page data -> tools/web_public/nq/brief.json.

Owner: "thinking process before, and through trades. News, bias, entries, more than just the strategy and rules."
Contract: docs/BRIEF.md (v 1). Pure and deterministic: same files + same --now = the same bytes (only `built_at` churns).
Futures data only (data/NQ_5m.csv = TradingView CME NQ1! + NinjaTrader pushed bars, data/VIX_1d.csv, data/VXN_1d.csv,
data/news/events.csv); never Yahoo. READ ONLY: it never places, changes or arms anything; the bots' rules are read from
their own constants (engine/live_board windows, engine/guards news defaults, engine/multi_account Rapid news ban).

  python -X utf8 tools/premarket_brief.py                    # build brief.json for now
  python -X utf8 tools/premarket_brief.py --now 2026-11-10T08:05 --out x.json   # any ET moment (samples, tests)
  python -X utf8 tools/premarket_brief.py --measure          # re-measure the pre-registered bias -> research/lab/brief_bias.json

The bias (research/lab/brief_bias_prereg_2026-11-20.md, pre-registered before measuring): B1 overnight drift at 08:00 ET
(primary), B2 fade yesterday's candle (secondary). The build reads the stored measurement (research/lab/brief_bias.json);
--measure rewrites it from the bars.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
ET = ZoneInfo("America/New_York")
UTC = dt.timezone.utc
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "tools", "web_public", "nq", "brief.json")
MEASURE = os.path.join(ROOT, "research", "lab", "brief_bias.json")
PREREG = "research/lab/brief_bias_prereg_2026-11-20.md"
TRADES = os.path.join(ROOT, "tools", "web_public", "trading", "trades.json")
ACCOUNTS = os.path.join(ROOT, "tools", "web_public", "business", "accounts.json")

# pre-registered constants (do not tune: the prereg file is the source)
B1_K, B2_K, ATR_N, MIN_BODY = 0.20, 0.10, 14, 1.0
BANDS = ((15.0, "calm"), (20.0, "normal"), (30.0, "elevated"), (1e9, "high"))
PERIODS = (("2021-25", "2000-01-01", "2025-12-31"), ("2026H1", "2026-01-01", "2026-06-30"), ("2026H2", "2026-07-01", "2099-12-31"))

# the bots' entry windows (minutes ET) - one source: engine/live_board (the copies below only if it fails to import)
LIT_WINDOW = (120, 930)
ATLAS_WINDOWS = {"ema_lon_vix": [(180, 570)], "macd_sweep": [(120, 300), (570, 660)], "sr_nyreclaim": [(570, 720)]}
ATLAS_NO_MONDAY = {"ema_lon_vix"}
try:
    from engine.live_board import ATLAS_NO_MONDAY, ATLAS_WINDOWS, LIT_WINDOW  # noqa: F811
except Exception:  # noqa: BLE001
    pass


# ------------------------------------------------------------------------------------------------ small helpers
def _hm(m: int) -> str:
    return f"{int(m) // 60:02d}:{int(m) % 60:02d}"


def _r(x, n=2):
    return None if x is None else round(float(x), n)


def band(v):
    if v is None:
        return None
    return next(name for top, name in BANDS if float(v) < top)


def cme_day(t_et: dt.datetime) -> dt.date:
    """The CME trading day of an ET moment: 18:00 ET and later belongs to the next day (weekends roll to Monday)."""
    d = t_et.date() + dt.timedelta(days=1) if t_et.hour >= 18 else t_et.date()
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    return d


def _early(day: str):
    try:
        from engine import cme_calendar
        ec = cme_calendar.early_close(day)
        return int(ec) if isinstance(ec, (int, float)) else None
    except Exception:  # noqa: BLE001
        return None


def _closed(day: str) -> bool:
    try:
        from engine import cme_calendar
        return bool(cme_calendar.full_closure(day))
    except Exception:  # noqa: BLE001
        return False


def binom_p(k: int, n: int) -> float | None:
    """One-sided P(X >= k) for X ~ Bin(n, 0.5)."""
    if n <= 0:
        return None
    lg = [0.0] * (n + 1)
    for i in range(1, n + 1):
        lg[i] = lg[i - 1] + math.log(i)
    s = sum(math.exp(lg[n] - lg[i] - lg[n - i] - n * math.log(2)) for i in range(k, n + 1))
    return round(min(1.0, s), 4)


# ------------------------------------------------------------------------------------------------ data
def load_bars(path=None):
    """5m bars -> list of (t, et datetime, o, h, l, c)."""
    path = path or os.path.join(DATA, "NQ_5m.csv")
    out = []
    with open(path, newline="") as f:
        r = csv.reader(f)
        next(r)
        for row in r:
            t = int(float(row[0]))
            out.append((t, dt.datetime.fromtimestamp(t, ET), float(row[1]), float(row[2]), float(row[3]), float(row[4])))
    return out


def load_vol(name):
    p = os.path.join(DATA, f"{name}_1d.csv")
    out = {}
    if os.path.exists(p):
        with open(p, newline="") as f:
            for row in csv.DictReader(f):
                try:
                    out[row["date"]] = float(row["close"])
                except (KeyError, ValueError):
                    pass
    return out


def load_events():
    p = os.path.join(DATA, "news", "events.csv")
    out = []
    if os.path.exists(p):
        with open(p, newline="") as f:
            for row in csv.DictReader(f):
                imp = (row.get("impact") or "").strip().lower()
                if imp not in ("high", "medium"):
                    continue
                out.append({"date": row["date"], "time": row.get("time_et") or "", "event": row.get("event") or "",
                            "tier": 1 if imp == "high" else 2, "source": (row.get("source") or "").split(" (")[0]})
    out.sort(key=lambda e: (e["date"], e["time"], e["event"]))
    return out


def days_table(bars):
    """Per CME day: open/high/low/close, 18:00 open, 07:55 close, RTH 09:30 open / 15:55 close, RTH high/low."""
    days = {}
    for t, e, o, h, l, c in bars:
        d = cme_day(e).isoformat()
        x = days.get(d)
        if x is None:
            x = days[d] = {"day": d, "open": o, "high": h, "low": l, "close": c, "first_t": t, "last_t": t,
                           "o1800": None, "c0755": None, "rth_open": None, "rth_close": None, "rth_hi": None, "rth_lo": None,
                           "on_hi": None, "on_lo": None}
        x["high"], x["low"], x["close"], x["last_t"] = max(x["high"], h), min(x["low"], l), c, t
        hm = e.hour * 60 + e.minute
        if hm == 18 * 60:
            x["o1800"] = o
        if hm == 7 * 60 + 55:
            x["c0755"] = c
        if hm == 9 * 60 + 30:
            x["rth_open"] = o
        if hm == 15 * 60 + 55:
            x["rth_close"] = c
        if 570 <= hm < 960:
            x["rth_hi"] = h if x["rth_hi"] is None else max(x["rth_hi"], h)
            x["rth_lo"] = l if x["rth_lo"] is None else min(x["rth_lo"], l)
        elif hm >= 18 * 60 or hm < 570:
            x["on_hi"] = h if x["on_hi"] is None else max(x["on_hi"], h)
            x["on_lo"] = l if x["on_lo"] is None else min(x["on_lo"], l)
    out = [days[k] for k in sorted(days)]
    for i, x in enumerate(out):
        prev = out[max(0, i - ATR_N):i]
        x["atr"] = sum(p["high"] - p["low"] for p in prev) / len(prev) if len(prev) == ATR_N else None
        x["prev"] = out[i - 1] if i else None
    return out


# ------------------------------------------------------------------------------------------------ the bias rules
def b1_call(move, atr):
    if move is None or not atr:
        return "none"
    return "up" if move >= B1_K * atr else "down" if move <= -B1_K * atr else "none"


def b2_call(prev, atr):
    if not prev or not atr:
        return "none"
    body = prev["close"] - prev["open"]
    if abs(body) < B2_K * atr:
        return "none"
    return "down" if body > 0 else "up"


def _rows(days, vix, tier1_days):
    rows = []
    for x in days:
        if x["prev"] is None or x["atr"] is None or _early(x["day"]) is not None:
            continue
        if None in (x["o1800"], x["c0755"], x["rth_open"], x["rth_close"]):
            continue
        body = x["rth_close"] - x["rth_open"]
        if abs(body) < MIN_BODY:
            continue
        pv = x["prev"]["day"]
        rows.append({"day": x["day"], "up": body > 0, "b1": b1_call(x["c0755"] - x["o1800"], x["atr"]),
                     "b2": b2_call(x["prev"], x["atr"]), "vix_band": band(vix.get(pv)), "tier1": x["day"] in tier1_days})
    return rows


def _score(rows, key):
    called = [r for r in rows if r[key] != "none"]
    n = len(called)
    hits = sum(1 for r in called if (r[key] == "up") == r["up"])
    up_share = (sum(1 for r in rows if r["up"]) / len(rows)) if rows else None
    # drift baseline of the called days: an UP call is compared with the share of up days, a DOWN call with down days
    base = None
    if n and up_share is not None:
        nu = sum(1 for r in called if r[key] == "up")
        base = (nu * up_share + (n - nu) * (1 - up_share)) / n
    return {"n": n, "hits": hits, "hit_pct": _r(100 * hits / n, 1) if n else None,
            "base_pct": _r(100 * base, 1) if base is not None else None, "p": binom_p(hits, n),
            "days": len(rows), "up_days_pct": _r(100 * up_share, 1) if up_share is not None else None}


def measure(bars=None, write=True):
    bars = bars or load_bars()
    days = days_table(bars)
    vix = load_vol("VIX")
    tier1 = {e["date"] for e in load_events() if e["tier"] == 1 and e["time"] >= "08:30"}
    rows = _rows(days, vix, tier1)
    res = {"prereg": PREREG, "data": "data/NQ_5m.csv", "from": rows[0]["day"] if rows else None,
           "to": rows[-1]["day"] if rows else None, "rules": {}}
    for key in ("b1", "b2"):
        per = {}
        for name, a, z in PERIODS:
            pr = [r for r in rows if a <= r["day"] <= z]
            per[name] = _score(pr, key)
            sub = {}
            for b in ("calm", "normal", "elevated", "high"):
                s = _score([r for r in pr if r["vix_band"] == b], key)
                if s["n"]:
                    sub["vix_" + b] = {k: s[k] for k in ("n", "hits", "hit_pct")}
            for lab, flag in (("tier1_day", True), ("no_tier1", False)):
                s = _score([r for r in pr if r["tier1"] == flag], key)
                if s["n"]:
                    sub[lab] = {k: s[k] for k in ("n", "hits", "hit_pct")}
            per[name]["sub"] = sub
        works = all(p["n"] >= 40 and p["hit_pct"] is not None and p["hit_pct"] > 50 and p["p"] is not None
                    and p["p"] < 0.025 and p["hit_pct"] > (p["base_pct"] or 50) for p in per.values())
        res["rules"][key.upper()] = {"periods": per, "works": works}
    if write:
        os.makedirs(os.path.dirname(MEASURE), exist_ok=True)
        with open(MEASURE, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=1, sort_keys=True)
            f.write("\n")
    return res


def stored_measure():
    try:
        with open(MEASURE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return None


# ------------------------------------------------------------------------------------------------ the brief
B1_TEXT = ("At 08:00 ET: if NQ moved up at least 0.2 x ATR since the 18:00 open, call UP; down at least 0.2 x ATR, call DOWN; "
           "else no call. Judged on the 09:30-16:00 candle.")
B2_TEXT = "Fade yesterday's candle: yesterday closed up -> call DOWN, closed down -> call UP (tiny candles: no call)."

LIT_WAIT = ("A sweep of a level (yesterday's high/low, a session high/low, last week's high/low, an opening gap) by at least "
            "half an ATR, after a small swing was taken first; then a strong candle back and a 5m close through the shift "
            "level (CISD); entry on the 1m confirmation. Stop 1 tick past the sweep, target = 18:00 open +/- one VIX day "
            "move (at least 1.5R, banked at 8R), break-even at 1R, flat 15:55, 1 trade a day.")
LIT_SIZE = "Size follows the stop: eval two-week rule (one winner passes), capped at 40% of the eval room, soft $1,000 day."
ATLAS = {
    "ema_lon_vix": ("atlas_ema", "ATLAS EMA", "London trend pullback: 15m and 1h EMA 21 above the 50 (or below for shorts), a "
                    "pullback to the 5m EMA 50 that sweeps a swing, then a 5m close back with the trend (CISD). Stop past the "
                    "sweep wick, VIX-band target, BE + costs at 1R. Never on Mondays."),
    "macd_sweep": ("atlas_macd", "ATLAS MACD", "A LIT level swept by half an ATR, then a 5m close back with MACD divergence; "
                   "market entry, stop past the sweep, VIX-band target, 15-minute check."),
    "sr_nyreclaim": ("atlas_sr", "ATLAS S/R", "NY open: one of the day's levels (yesterday's RTH high/low, overnight high/low, "
                     "Asia/London box, last week, opening range) swept after an inducement, then a strong 5m close back "
                     "through it; market entry, stop past the sweep, 2R target, 1 a day."),
}
ATLAS_SIZE = "ATLAS funded 25K preset: a fixed $ risk per trade, micros = $ / stop; one position, max 2 entries a day."


def _news_rules():
    """What each bot does around news, read from the code's own defaults (engine/guards DEFAULTS, multi_account presets)."""
    news_on, news_min = False, 2
    try:
        from engine import guards
        news_on, news_min = bool(guards.DEFAULTS.get("news")), int(guards.DEFAULTS.get("news_min") or 2)
        try:
            with open(os.path.join(ROOT, "live_model.json"), encoding="utf-8") as f:
                g = json.load(f).get("guards") or {}
            news_on, news_min = bool(g.get("news", news_on)), int(g.get("news_min", news_min) or 2)
        except Exception:  # noqa: BLE001
            pass
    except Exception:  # noqa: BLE001
        pass
    rapid_ban = "funded"
    try:
        from engine import multi_account
        rapid_ban = multi_account.PRESETS["mffu_rapid_eod_25k"]["rules"].get("news_ban")
    except Exception:  # noqa: BLE001
        pass
    base = (f"Tier-1 news guard ON: no entry from {news_min} min before to {news_min} min after" if news_on else
            "No news block (MFFU Builder allows news; a news blackout did not help in research, hq-habits.md): "
            "it trades through releases with its normal stop")
    rapid = ("Eval: same as Zlarior and ATLAS (no news block). Funded: no entry and flat from 2 min before to 2 min after "
             "every Tier-1 release (MFFU Rapid rule)" if rapid_ban == "funded" else
             "Tier-1 news: no entry and flat -2/+2 min" if rapid_ban else "No news block")
    return {"lit": base, "atlas": base, "rapid": rapid}


def _accounts():
    try:
        with open(ACCOUNTS, encoding="utf-8") as f:
            acc = json.load(f).get("accounts") or []
    except Exception:  # noqa: BLE001
        acc = []
    lit, atlas, rapid = [], [], []
    for a in acc:
        name, plan, stage = a.get("name") or "", a.get("plan") or "", a.get("stage") or ""
        short = plan.replace("MFFU ", "")
        label = (f"{name} ({stage})" if short == name else f"{name} ({short}, {stage})") if plan else name
        k = a.get("key")
        if k == "atlas":
            atlas.append(label)
        elif k and k.startswith("rapid"):
            rapid.append(label)
        elif "zlarior" in (k or "") or "Zlarior" in name or "LIT" in (a.get("bots") or ""):
            lit.append(label)
    return lit or ["Zlarior (Builder 50K, eval)"], atlas or ["ATLAS (Builder 25K funded)"], rapid or ["Rapid EOD 25K (planned)"]


def _windows(day: dt.date, ranges, no_monday=False):
    ds = day.isoformat()
    if day.weekday() >= 5 or _closed(ds) or (no_monday and day.weekday() == 0):
        return []
    ec = _early(ds)
    out = []
    for a, z in ranges:
        zz = min(z, ec - 15) if ec is not None else z
        if zz > a:
            out.append({"from": _hm(a), "to": _hm(zz)})
    return out


def _state(wins, day: dt.date, now_et: dt.datetime):
    if not wins:
        return "off_today"
    # minute of the trading day: the evening before (18:00+) and weekends count as before the first window
    hm = now_et.hour * 60 + now_et.minute if now_et.date() == day else (-1 if now_et.date() < day else 9999)
    mins = [(int(w["from"][:2]) * 60 + int(w["from"][3:]), int(w["to"][:2]) * 60 + int(w["to"][3:])) for w in wins]
    if any(a <= hm < z for a, z in mins):
        return "open"
    if hm >= max(z for _, z in mins):
        return "done"
    return "before"


def _pick(levels, names):
    return [{"name": lv["name"], "price": lv["price"]} for lv in levels if lv["name"] in names]


def _trades_today(day: str):
    try:
        with open(TRADES, encoding="utf-8") as f:
            rows = json.load(f).get("trades") or []
    except Exception:  # noqa: BLE001
        return None
    out = []
    for t in rows:
        if t.get("day") != day or t.get("src") not in ("live", "paper"):
            continue
        out.append({"bot": t.get("bot"), "account": t.get("acct"), "side": t.get("side"), "time": t.get("hm"),
                    "r": _r(t.get("r")), "usd": _r(t.get("usd"), 0), "src": t.get("src")})
    # the paper twin of a trade the PC really took is the same trade: a bot with live rows keeps only those
    live_bots = {t["bot"] for t in out if t["src"] == "live"}
    return [t for t in out if t["src"] == "live" or t["bot"] not in live_bots]


def _recap(x: dict, prev: dict | None) -> dict:
    """What happened on day row x vs its brief: the levels taken, did the 08:00 call (B1) and B2 hold, the bots' trades."""
    on_hi, on_lo = x.get("on_hi"), x.get("on_lo")
    took = [n for n, cond in (("PDH", prev and x["high"] > prev["high"]), ("PDL", prev and x["low"] < prev["low"]),
                              ("ONH", on_hi is not None and (x.get("rth_hi") or -1e9) > on_hi),
                              ("ONL", on_lo is not None and (x.get("rth_lo") or 1e9) < on_lo)) if cond]
    body = (x["rth_close"] - x["rth_open"]) if (x.get("rth_close") is not None and x.get("rth_open") is not None) else None
    move = (x["c0755"] - x["o1800"]) if (x.get("c0755") is not None and x.get("o1800") is not None) else None
    c1 = b1_call(move, x.get("atr"))
    c2 = b2_call(prev, x.get("atr"))

    def held(c):
        return None if (c == "none" or body is None or abs(body) < MIN_BODY) else ((c == "up") == (body > 0))

    tr = _trades_today(x["day"])
    if not tr:
        traded = "no trade data for this day yet (trades.json is refreshed from the PC's data)"
    else:
        parts = []
        for b in ("LIT", "ATLAS"):
            mine = [t for t in tr if (t["bot"] or "").upper() == b]
            lab = "Zlarior" if b == "LIT" else "ATLAS"
            if not mine:
                parts.append(f"{lab}: no trade")
            else:
                usd = sum((t["usd"] or 0) for t in mine)
                what = ", ".join(f"{t['side'] or ''} {t['time'] or ''}".strip() for t in mine)
                money = f"{'+' if usd >= 0 else '-'}${abs(usd):,.0f}"
                parts.append(f"{lab}: {len(mine)} trade{'s' if len(mine) > 1 else ''} ({what}, {money}, {mine[0]['src']})")
        traded = ". ".join(parts) + "."
    return {"rth_open": _r(x.get("rth_open")), "rth_close": _r(x.get("rth_close")), "body_pts": _r(body, 1),
            "high": _r(x["high"]), "low": _r(x["low"]), "took": took, "bias_call": c1, "bias_held": held(c1),
            "alt_call": c2, "alt_held": held(c2), "trades": tr or [], "traded": traded}


def build(now: int | None = None, bars=None, measured=None) -> dict:
    now = int(now if now is not None else dt.datetime.now(UTC).timestamp())
    now_et = dt.datetime.fromtimestamp(now, ET)
    day = cme_day(now_et)
    ds = day.isoformat()
    bars = [b for b in (bars or load_bars()) if b[0] <= now - 300]   # only bars that have closed by `now`
    days = days_table(bars)
    vix, vxn = load_vol("VIX"), load_vol("VXN")
    events = load_events()
    measured = measured if measured is not None else stored_measure()
    stale, notes = [], []

    today = next((x for x in days if x["day"] == ds), None)
    prior = next((x for x in reversed(days) if x["day"] < ds), None)
    last_bar = bars[-1] if bars else None
    last = last_bar[5] if last_bar else None
    bars_age = int((now - last_bar[0] - 300) / 60) if last_bar else None
    if bars_age is not None and bars_age > 90 and not (now_et.weekday() >= 5 or _closed(ds)):
        stale.append(f"NQ bars end {last_bar[1]:%Y-%m-%d %H:%M} ET: today's session is not in the cloud data yet "
                     "(the PC pushes its bars after 17:05 ET)")
    atr = (today or {}).get("atr") if today else None
    if atr is None and days:
        tail = [x for x in days if x["day"] < ds][-ATR_N:]
        atr = sum(x["high"] - x["low"] for x in tail) / len(tail) if len(tail) == ATR_N else None

    def vol(src, name):
        ks = [k for k in src if k < ds]
        if not ks:
            return None
        k = max(ks)
        v = src[k]
        age = (day - dt.date.fromisoformat(k)).days
        if age > 4:
            stale.append(f"{name} is from {k} ({age} days old): band and target size use that close")
        ref = last or 0
        return {"value": _r(v), "date": k, "band": band(v), "day_move_pts": _r(ref * v / 100 / math.sqrt(252), 1)}

    mvix, mvxn = vol(vix, "VIX"), vol(vxn, "VXN")

    # weekly levels: the previous Mon-Fri CME week
    monday = day - dt.timedelta(days=day.weekday())
    pw = [x for x in days if (monday - dt.timedelta(days=7)).isoformat() <= x["day"] < monday.isoformat()]
    pwh = max(x["high"] for x in pw) if pw else None
    pwl = min(x["low"] for x in pw) if pw else None

    on_hi = on_lo = on_to = None
    rth_open = (today or {}).get("rth_open")
    if today:
        on_hi, on_lo = today.get("on_hi"), today.get("on_lo")
        on_to = "09:30" if rth_open is not None else (f"{last_bar[1]:%H:%M}" if last_bar else None)
    prior_rth_close = (prior or {}).get("rth_close")
    gap_ref = rth_open if rth_open is not None else (last if today else None)
    gap = (gap_ref - prior_rth_close) if (gap_ref is not None and prior_rth_close is not None) else None

    levels = []
    for name, p in (("PDH", (prior or {}).get("high")), ("PDL", (prior or {}).get("low")), ("PDC", prior_rth_close),
                    ("ONH", on_hi), ("ONL", on_lo), ("PWH", pwh), ("PWL", pwl), ("RTH open", rth_open),
                    ("18:00 open", (today or {}).get("o1800"))):
        if p is not None:
            levels.append({"name": name, "price": _r(p), "dist_pts": _r(p - last, 1) if last is not None else None})
    # LIT's target band (18:00 open +/- one VIX day move) - the levels Zlarior aims for today
    if today and today.get("o1800") is not None and mvix:
        mv = today["o1800"] * mvix["value"] / 100 / math.sqrt(252)
        for name, p in (("LIT target up", today["o1800"] + mv), ("LIT target down", today["o1800"] - mv)):
            levels.append({"name": name, "price": _r(p), "dist_pts": _r(p - last, 1) if last is not None else None})
    levels.sort(key=lambda x: -x["price"])

    where, where_text = None, None
    if prior and last is not None:
        if last > prior["high"]:
            where = "above_pdh"
            where_text = f"Price {last:,.2f} is {last - prior['high']:.0f} pts ABOVE yesterday's high {prior['high']:,.2f}"
        elif last < prior["low"]:
            where = "below_pdl"
            where_text = f"Price {last:,.2f} is {prior['low'] - last:.0f} pts BELOW yesterday's low {prior['low']:,.2f}"
        else:
            where = "inside"
            where_text = (f"Price {last:,.2f} is inside yesterday's range: {prior['high'] - last:.0f} pts under its high, "
                          f"{last - prior['low']:.0f} pts over its low")
        if not today:
            where_text += " (last close, before today's session)"

    market = {"last": _r(last), "prior_day": ({"day": prior["day"], "high": _r(prior["high"]), "low": _r(prior["low"]),
                                                "close": _r(prior["close"])} if prior else None),
              "prior_rth_close": _r(prior_rth_close),
              "overnight": ({"high": _r(on_hi), "low": _r(on_lo), "from": "18:00", "to": on_to} if on_hi is not None else None),
              "rth_open": _r(rth_open), "gap_pts": _r(gap, 1), "gap_atr": _r(gap / atr, 2) if (gap is not None and atr) else None,
              "atr_pts": _r(atr, 1), "vix": mvix, "vxn": mvxn, "where": where, "where_text": where_text, "levels": levels}

    # ---------------- news
    wk_from, wk_to = monday.isoformat(), (monday + dt.timedelta(days=4)).isoformat()
    n_today = [{"time": e["time"], "event": e["event"], "tier": e["tier"], "source": e["source"]} for e in events if e["date"] == ds]
    n_week = [{"date": e["date"], "weekday": dt.date.fromisoformat(e["date"]).strftime("%a"), "time": e["time"],
               "event": e["event"], "tier": e["tier"]} for e in events if wk_from <= e["date"] <= wk_to]
    now_key = (now_et.date().isoformat(), f"{now_et:%H:%M}")
    nxt = next((e for e in events if e["tier"] == 1 and (e["date"], e["time"]) > now_key), None)
    nr = _news_rules()
    news = {"today": n_today, "week": n_week, "tier1_today": any(e["tier"] == 1 for e in n_today),
            "next_tier1": ({"date": nxt["date"], "time": nxt["time"], "event": nxt["event"],
                            "in_days": (dt.date.fromisoformat(nxt["date"]) - now_et.date()).days} if nxt else None),
            "rules": [{"bot": "Zlarior (LIT)", "rule": nr["lit"]}, {"bot": "ATLAS", "rule": nr["atlas"]},
                      {"bot": "Rapid EOD", "rule": nr["rapid"]}]}
    t1_late = [e for e in n_today if e["tier"] == 1 and e["time"] >= "08:30"]

    # ---------------- bias
    at8 = now_et.date() == day and (now_et.hour * 60 + now_et.minute) >= 8 * 60 and now_et.hour < 18
    move = (today["c0755"] - today["o1800"]) if (today and today.get("c0755") is not None and today.get("o1800") is not None) else None
    why_none = None
    if day != now_et.date() or not at8:
        if not (today and move is not None):
            why_none = "before 08:00 ET: the call is made at 08:00 from the overnight move"
    if move is None and why_none is None:
        why_none = "the overnight bars to 08:00 are not in the data"
    call = b1_call(move, atr) if move is not None else "none"
    if call == "none" and why_none is None:
        why_none = f"the overnight move ({move:+.0f} pts) is smaller than 0.2 x ATR ({B1_K * atr:.0f} pts)"
    call2 = b2_call(prior, atr)
    m = (measured or {}).get("rules") or {}

    def per(key):
        p = (m.get(key) or {}).get("periods") or {}
        return {k: {kk: v.get(kk) for kk in ("n", "hits", "hit_pct", "base_pct", "p")} for k, v in p.items()}

    works = bool((m.get("B1") or {}).get("works"))

    def vtext(key, name):
        p = per(key)
        if not p:
            return f"{name}: not measured yet (run --measure)"
        bits = [f"{p[k]['hit_pct']}% of {p[k]['n']} ({k})" for k in ("2021-25", "2026H1", "2026H2") if k in p and p[k]["n"]]
        ok = (m.get(key) or {}).get("works")
        return f"{name} hit " + ", ".join(bits) + (": passes the pre-registered bar" if ok else ": no better than a coin")

    flags = []
    if t1_late:
        flags.append(f"Tier-1 news after the call: {', '.join(e['time'] + ' ' + e['event'] for e in t1_late)}")
    if mvix and mvix["band"] == "high":
        flags.append(f"VIX {mvix['value']} (high band): days swing both ways")
    if _early(ds) is not None:
        flags.append(f"early close {_hm(_early(ds))} ET")
    if stale:
        flags.append("data stale (see data.stale)")
    bias = {"call": call, "rule_id": "B1", "rule": B1_TEXT, "prereg": PREREG,
            "inputs": {"overnight_move_pts": _r(move, 1), "atr_pts": _r(atr, 1), "threshold_pts": _r(B1_K * atr, 1) if atr else None,
                       "at": "08:00"},
            "why_none": why_none if call == "none" else None, "measured": per("B1"),
            "alt": {"rule_id": "B2", "rule": B2_TEXT, "call": call2, "measured": per("B2"),
                    "works": bool((m.get("B2") or {}).get("works"))},
            "works": works, "context_only": not works,
            "verdict": vtext("B1", "B1") + ". " + vtext("B2", "B2") + ".", "not_reliable": flags}

    # ---------------- bots
    lit_acc, atlas_acc, rapid_acc = _accounts()
    lvl_lit = _pick(levels, {"PDH", "PDL", "ONH", "ONL", "PWH", "PWL", "LIT target up", "LIT target down"})
    w_lit = _windows(day, [LIT_WINDOW])
    lit_wait = LIT_WAIT + (" Monday rule: once Monday has taken Friday's high only shorts, Friday's low only longs."
                           if day.weekday() == 0 else "")
    bots = [{"id": "lit", "name": "Zlarior (LIT)", "accounts": lit_acc, "windows": w_lit, "state": _state(w_lit, day, now_et),
             "max_trades": 1, "waiting_for": lit_wait, "watch": lvl_lit, "news_rule": nr["lit"], "size_rule": LIT_SIZE}]
    for k, (bid, name, wait) in ATLAS.items():
        w = _windows(day, ATLAS_WINDOWS.get(k, []), k in ATLAS_NO_MONDAY)
        names = {"PDH", "PDL", "ONH", "ONL", "PWH", "PWL"} if k != "ema_lon_vix" else {"ONH", "ONL"}
        if k == "sr_nyreclaim":
            names |= {"PDC", "RTH open"}
        bots.append({"id": bid, "name": name, "accounts": atlas_acc, "windows": w, "state": _state(w, day, now_et),
                     "max_trades": 1 if k == "sr_nyreclaim" else 2, "waiting_for": wait, "watch": _pick(levels, names),
                     "news_rule": nr["atlas"], "size_rule": ATLAS_SIZE})
    w_r = _windows(day, [LIT_WINDOW])
    planned = all("planned" in a.lower() or "plan" in a.lower() for a in rapid_acc)
    bots.append({"id": "rapid", "name": rapid_acc[0].split(" (")[0] if rapid_acc else "Rapid EOD 25K", "accounts": rapid_acc,
                 "windows": w_r, "state": _state(w_r, day, now_et), "max_trades": 2,
                 "waiting_for": ("Zlarior's LIT setup and the ATLAS setups on ONE account, never two positions at once "
                                 "(LIT first). A winning day is kept under 30% of the $1,500 target.") +
                                (" Not trading yet: the account is not set up on the PC." if planned else ""),
                 "watch": lvl_lit, "news_rule": nr["rapid"],
                 "size_rule": "Eval: LIT's two-week size on $1,500 / $1,000 floor / 20 micros, soft $500 day; ATLAS <= $250 a trade."})

    # ---------------- phase + recap
    hm = now_et.hour * 60 + now_et.minute
    if day.weekday() >= 5 or _closed(ds):
        phase = "closed"
    elif now_et.date() == day and 570 <= hm < 960:
        phase = "rth"
    elif now_et.date() == day and 960 <= hm < 18 * 60:
        phase = "post"
    else:
        phase = "pre"
    recap = _recap(today, prior) if (phase == "post" and today) else None
    prev_recap = None
    if prior and prior.get("rth_close") is not None:
        pp = next((x for x in reversed(days) if x["day"] < prior["day"]), None)
        prev_recap = {"day": prior["day"], **_recap(prior, pp)}

    # ---------------- headline + notes
    hl = []
    if gap is not None and atr:
        hl.append(f"{'Gap up' if gap > 0 else 'Gap down'} {abs(gap):.0f} pts" if abs(gap) >= 0.1 * atr else "No real gap")
    if where == "above_pdh":
        hl.append("above yesterday's high")
    elif where == "below_pdl":
        hl.append("below yesterday's low")
    elif where == "inside":
        hl.append("inside yesterday's range")
    t1 = [e for e in n_today if e["tier"] == 1]
    hl.append(("; ".join(f"{e['event']} {e['time']}" for e in t1) + " (Tier 1)") if t1 else "no Tier-1 news today")
    hl.append(f"Bias: {call}" + (" (context, coin)" if not works else ""))
    headline = ". ".join(s[0].upper() + s[1:] for s in hl if s) + "."
    if _early(ds) is not None:
        notes.append(f"CME early close {_hm(_early(ds))} ET: every window ends 15 min before")
    notes.append("Read only: the brief never changes what a bot does; the bots follow their coded rules.")
    if not works:
        notes.append("The day bias did not beat a coin on the pre-registered test: use it as context, never as a reason to trade.")

    return {"v": 1, "built_at": dt.datetime.fromtimestamp(now, UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), "day": ds,
            "weekday": day.strftime("%a"), "phase": phase, "early_close": _hm(_early(ds)) if _early(ds) is not None else None,
            "headline": headline,
            "data": {"bars": "NQ 5m (TradingView CME NQ1! + NinjaTrader)",
                     "bars_to": f"{last_bar[1]:%Y-%m-%d %H:%M}" if last_bar else None,
                     "vix_date": (mvix or {}).get("date"), "vxn_date": (mvxn or {}).get("date"), "stale": stale},
            "market": market, "news": news, "bias": bias, "bots": bots, "recap": recap, "prev_recap": prev_recap,
            "notes": notes[:5]}


def dumps(b: dict) -> str:
    return json.dumps(b, separators=(",", ":"), sort_keys=False, ensure_ascii=False) + "\n"


def write(b: dict, path=OUT) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    s = dumps(b)
    try:                                   # no rewrite when only built_at would change (no churn)
        with open(path, encoding="utf-8") as f:
            old = json.loads(f.read())
        if {**old, "built_at": None} == {**json.loads(s), "built_at": None}:
            return path
    except Exception:  # noqa: BLE001
        pass
    with open(path, "w", encoding="utf-8") as f:
        f.write(s)
    return path


def _parse_now(s: str | None):
    if not s:
        return None
    d = dt.datetime.fromisoformat(s)
    if d.tzinfo is None:
        d = d.replace(tzinfo=ET)
    return int(d.timestamp())


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--now", help="ET moment, e.g. 2026-11-10T08:05 (default: now)")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--measure", action="store_true", help="re-measure the pre-registered bias rules")
    a = ap.parse_args(argv)
    if a.measure:
        res = measure()
        for k, v in res["rules"].items():
            print(k, "works" if v["works"] else "NO EDGE", {p: (x["hit_pct"], x["n"], x["base_pct"], x["p"]) for p, x in v["periods"].items()})
        return 0
    b = build(_parse_now(a.now))
    p = write(b, a.out)
    print(f"brief {b['day']} {b['phase']}: {b['headline']} -> {os.path.relpath(p, ROOT)} ({len(dumps(b))} B)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
