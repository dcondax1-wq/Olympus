"""MFFU's 2% price-limit rule (help center 9698984 "2% Price Limit Rule", dated 2026-08-24; research/lit/mffu_rules.json
price_limit_rule): "we do not allow market participation when a product is trading within 2% of a price limit. This
prohibited conduct is enforced in the following accounts: Sim Funded Account, Live Funded Account." For NQ / MNQ: "overnight
price limits have increased to 5%, which is 2% below the CME limit of 7%. Consequently, trading is suspended"; the levels are
the reference (CME's end-of-day settlement) x (1 +/- 0.07 -/+ 0.02), e.g. 18,556 -> stop above 19,483 / below 17,628.

The bot (day-pricelimit 2026-11-20, research/handoff/2026-11-20/pricelimit/REPORT.md):
  reference  the prior session's settlement, proxied by the close of the last bar ending at or before 16:00 ET (13:00 on a
             CME half day: the last bar of that session) before the current session (which opens 18:00 ET);
  trigger    |price / reference - 1| >= 4.75% (MFFU's 5% minus a 0.25% margin for the settlement proxy and a fast tape);
  sticky     once hit, the rest of that trading day (to 18:00 ET) stays blocked: "trading is suspended";
  scope      FUNDED accounts only (sim funded + live, the article's words): no new entry, an open position is flattened.
             Evaluations are not named by MFFU and are not touched. Regular hours use the same +/-5% band: CME's day-session
             equity limits are downside only (7 / 13 / 20%), so the upside stop in regular hours is stricter than MFFU asks.
  unknown    no fresh reading (no bars this poll, no reference bar) = not blocked (the stale-feed guard already stops entries).

LiveBot.poll_once calls update() once per poll with its 5m / 1m bars, BEFORE any account routes; the funded accounts ask
blocked(now). Pure functions are separate (reference / status) so research and tests use them on any bars. Never raises.
"""
from __future__ import annotations

import datetime as _dt

CME_LIMIT = 0.07            # NQ / MNQ overnight up / down limit (MFFU's article; CME's page was unreachable 2026-11-20)
MFFU_BUFFER = 0.02          # MFFU: no trading within 2% of the limit -> 5%
MARGIN = 0.0025             # the bot stops 0.25% earlier (settlement proxy, a fast tape)
TRIGGER = CME_LIMIT - MFFU_BUFFER - MARGIN     # 0.0475
FRESH_S = 180               # a reading older than this is unknown (not blocked)
REASON = "PRICE LIMIT"

_LAST: dict = {}            # the latest reading (update())
_STICKY: dict = {}          # trading day -> the first reading that hit the trigger


def _et(ts):
    from zoneinfo import ZoneInfo
    return _dt.datetime.fromtimestamp(int(ts), tz=ZoneInfo("America/New_York"))


def _ts(d: _dt.date, h: int, m: int = 0) -> int:
    from zoneinfo import ZoneInfo
    return int(_dt.datetime(d.year, d.month, d.day, h, m, tzinfo=ZoneInfo("America/New_York")).timestamp())


def trading_day(now) -> str:
    return (_et(now) + _dt.timedelta(hours=6)).strftime("%Y-%m-%d")      # 18:00 ET opens the next trading day


def session_open(now) -> int:
    """18:00 ET that opened the trading day `now` is in."""
    e = _et(now)
    d = e.date() if e.hour >= 18 else e.date() - _dt.timedelta(days=1)
    return _ts(d, 18)


def reference(times, closes, now, bar_s: int = 300) -> tuple:
    """(reference price, its bar's end time) = the last bar ending at or before 16:00 ET before this session opened, no more
    than 4 days back (a weekend / holiday) and inside that day's regular session (a half day's 13:00 close counts); (None,
    None) when there is none."""
    so = session_open(now)
    e = _et(so - 1)                                          # the session that ended before this one opened
    settle = _ts(e.date(), 16)
    if settle > so:
        settle -= 86400
    lo = settle - 4 * 86400
    best = None
    for t, c in zip(times, closes):
        end = int(t) + int(bar_s)
        if lo <= end <= settle and 9 <= _et(int(t)).hour < 16:      # a regular-hours bar (start 09:00-15:59 ET)
            if best is None or end > best[1]:
                best = (float(c), end)
    return best if best else (None, None)


def status(times, closes, now, bar_s: int = 300, price=None) -> dict:
    """{"ref", "price", "pct" (signed), "up", "dn" (MFFU's 5% levels), "hit"} on these bars at `now` (price = the last close
    at or before now when not given). Never raises; {} when unknown."""
    try:
        ref, ref_t = reference(times, closes, now, bar_s)
        if not ref:
            return {}
        if price is None:
            px = [(int(t), float(c)) for t, c in zip(times, closes) if int(t) + int(bar_s) <= int(now) + int(bar_s)]
            if not px:
                return {}
            price = max(px)[1]
        pct = float(price) / ref - 1.0
        return {"ref": round(ref, 2), "ref_t": ref_t, "price": round(float(price), 2), "pct": round(pct, 5),
                "up": round(ref * (1 + CME_LIMIT - MFFU_BUFFER), 2), "dn": round(ref * (1 - CME_LIMIT + MFFU_BUFFER), 2),
                "hit": abs(pct) >= TRIGGER - 1e-12}
    except Exception:
        return {}


def update(df5, df1, now) -> dict:
    """LiveBot: one reading per poll (5m bars for the reference, the newest 1m close for the price). Never raises."""
    try:
        price = None
        if df1 is not None and len(df1):
            price = float(df1["close"].iloc[-1])
        st = status(df5["time"].tolist(), df5["close"].tolist(), int(now), 300, price)
        _LAST.clear()
        if st:
            _LAST.update(st, t=int(now))
            if st["hit"]:
                _STICKY.setdefault(trading_day(now), {**st, "t": int(now)})
        return dict(_LAST)
    except Exception:
        return {}


def blocked(now) -> str | None:
    """Why a FUNDED account may not trade now (None = it may): the trigger was hit this trading day (sticky), or the fresh
    reading is inside MFFU's 2% band."""
    day = trading_day(now)
    s = _STICKY.get(day)
    if s:
        return (f"{REASON}: NQ {s['pct'] * 100:+.2f}% from the {s['ref']:,.2f} settlement at {_et(s['t']):%H:%M} ET "
                f"(MFFU: no trading within 2% of the CME 7% limit, funded accounts; suspended for the rest of the session)")
    if _LAST and int(now) - int(_LAST.get("t") or 0) <= FRESH_S and _LAST.get("hit"):
        return f"{REASON}: NQ {_LAST['pct'] * 100:+.2f}% from the {_LAST['ref']:,.2f} settlement"
    return None


def reset():
    """Tests."""
    _LAST.clear()
    _STICKY.clear()
