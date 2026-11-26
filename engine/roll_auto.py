"""Hands-free quarterly roll (day-ops2 2026-11-26; lead: "make it automatic and verified").

Before today the December roll needed one NinjaTrader click: the LE_BarFeed chart switched to MNQ 03-27 (tools/bat/ROLL.bat),
because NinjaTrader cannot change a chart's instrument from outside. The LE_Feed add-on (no-chart mode) follows the bot's
le_feed\\feed_instruments.txt by itself, but it was never verified on the owner's PC. This module makes the switch to it SAFE
and automatic, then lets the roll happen by itself:

  1. PREP (from PREP_DAYS before the roll; self-heal's hourly run, never 01:50-16:00 ET on a weekday, only flat):
     le_feed\\le_feed_mode.txt = "shadow" FIRST, then LE_Feed.cs is put into NinjaTrader's AddOns (engine/ns_sync.install).
     In shadow mode the add-on writes its bars to le_feed\\shadow\\ only: the chart stays the bot's ONLY bar source.
  2. VERIFY: every run compares the closed 1-minute bars of le_feed\\shadow\\<ROOT>_1m.csv with the chart's le_feed\\<ROOT>_1m.csv
     (open/high/low/close, the overlap of each ET day). A day counts as equal with >= MIN_BARS overlapping bars and at most
     MAX_DIFF_F of them different. MATCH_DAYS equal days in a row = verified. One different day resets the count.
  3. SWITCH: verified + outside trading hours + flat -> le_feed_mode.txt = "live": the add-on writes le_feed\\ and the chart's
     LE_BarFeed defers to it (LE_FeedHub). ONE Telegram line. From then on the roll needs no click: at 00:00 ET on the roll day
     the bot writes the new contract into feed_instruments.txt (engine/ninjatrader.sync_feed_instruments) and the add-on follows
     within 3 minutes; orders (nt_instrument), the keep-alive (it trades through the account's own adapter) and the order-flow
     recorder (engine/tickrec.front_names, now the same day) move by the date.
  4. FALLBACK: live mode with the add-on's status older than STALE_S while NinjaTrader runs -> "shadow" again (the chart, still
     open, writes again by itself) + one alert. Before the roll, with nothing verified by the eve: the old path (tools/bat/ROLL.bat, the
     existing reminders) stays exactly as it was.
  5. DONE: on the roll day after 00:05 ET, once le_feed\\<ROOT>_instrument.txt names the new contract: ONE Telegram line
     "Roll done: orders, bars and the order-flow recorder on MNQ 03-27".

Left to the owner, honestly: if NinjaTrader does not compile the copied file by itself, ONE "press F5 once" line (engine/ns_sync);
if LE_Feed never verifies before the roll, the chart click as before. Nothing here places, changes or cancels an order.
State: logs/self_heal/roll_auto.json (gitignored). Off: LE_ROLL_AUTO=0. Tests: tests.test_ops2.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_REL = os.path.join("logs", "self_heal", "roll_auto.json")
MODE_FILE = "le_feed_mode.txt"
PREP_DAYS = 14
MATCH_DAYS = 2
MIN_BARS = 300
MAX_DIFF_F = 0.005
STALE_S = 10 * 60
ROOTS = ("MNQ", "NQ")


def _et(t) -> dt.datetime:
    return dt.datetime.fromtimestamp(float(t), ET)


def _in_trading(now) -> bool:
    e = _et(now)
    m = e.hour * 60 + e.minute
    return e.weekday() < 5 and 110 <= m < 960


def roll_day(today: dt.date) -> dt.date:
    """The next day (today included) the bot's order contract changes (engine/ninjatrader.nt_instrument)."""
    from .ninjatrader import nt_instrument
    cur = nt_instrument("MNQ", today)
    d = today
    for _ in range(120):
        nxt = d + dt.timedelta(days=1)
        if nt_instrument("MNQ", nxt) != cur:
            return nxt
        d = nxt
    return d


def last_roll_day(today: dt.date) -> dt.date | None:
    from .ninjatrader import nt_instrument
    d = today
    for _ in range(120):
        prv = d - dt.timedelta(days=1)
        if nt_instrument("MNQ", prv) != nt_instrument("MNQ", d):
            return d
        d = prv
    return None


def _read(p):
    try:
        with open(p, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def read_mode(nt: str) -> str | None:
    t = _read(os.path.join(nt, "le_feed", MODE_FILE))
    return None if t is None else ("shadow" if t.strip().lower() == "shadow" else "live")


def write_mode(nt: str, mode: str) -> None:
    d = os.path.join(nt, "le_feed")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, MODE_FILE)
    with open(p + ".tmp", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(mode + "\n")
    from .fsutil import replace as _replace
    _replace(p + ".tmp", p)


def bars(path: str) -> dict:
    """{open time (unix s): (o, h, l, c)} of a LE_BarFeed / LE_Feed csv (time,open,high,low,close,volume)."""
    out = {}
    t = _read(path) or ""
    for ln in t.splitlines():
        p = ln.split(",")
        if len(p) < 5 or not p[0][:1].isdigit():
            continue
        try:
            out[int(float(p[0]))] = tuple(round(float(x), 2) for x in p[1:5])
        except ValueError:
            continue
    return out


def compare(chart: dict, shadow: dict, before: int | None = None) -> dict:
    """{ET day: (overlapping bars, different bars)} of the closed bars both files hold (the newest bar of each is skipped:
    it may be the one still being written). before: only bars that opened before this time."""
    # red team 2026-11-26: a chart bar the shadow MISSED counts as different (a feed with gaps must never verify), within the
    # shadow's own span only (it starts later than the chart: before its first bar nothing is held against it)
    if not chart or not shadow:
        return {}
    lo, hi = min(shadow), max(shadow)
    common = sorted(t for t in chart if lo <= t < hi and t < max(chart))
    days: dict = {}
    for t in common:
        if before is not None and t >= before:
            continue
        d = _et(t).date().isoformat()
        n, bad = days.get(d, (0, 0))
        days[d] = (n + 1, bad + (shadow.get(t) != chart[t]))
    return days


def verdict(days: dict, today: str) -> tuple:
    """(equal days in a row up to the newest finished day, first different day or None). Today's day is still running: skipped."""
    run, bad_day = 0, None
    for d in sorted(days):
        if d >= today:
            continue
        n, bad = days[d]
        if n < MIN_BARS:
            continue                                    # a short day (weekend, holiday): neither counts nor resets
        if bad <= n * MAX_DIFF_F:
            run += 1
        else:
            run, bad_day = 0, d
    return run, bad_day


def _state(root):
    try:
        with open(os.path.join(root, STATE_REL), encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save(root, st):
    try:
        p = os.path.join(root, STATE_REL)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p + ".tmp", "w", encoding="utf-8") as fh:
            json.dump(st, fh)
        from .fsutil import replace as _replace
        _replace(p + ".tmp", p)
    except OSError:
        pass


def _status_age(nt: str, rel: str, now) -> float | None:
    try:
        return now - os.path.getmtime(os.path.join(nt, rel))
    except OSError:
        return None


def live_fresh(nt: str, now) -> bool:
    """The add-on feeds the bot right now (its le_feed status line is fresh): the owner's own no-chart mode."""
    a = _status_age(nt, os.path.join("le_feed", "le_feed_status.txt"), now)
    return a is not None and a <= STALE_S


def nt_running(nt: str, now) -> bool:
    """NinjaTrader is up: one of our NinjaScript status files (tick recorder, chart feed) is fresh."""
    for rel in (os.path.join("le_ticks", "le_tickrec_status.txt"), os.path.join("le_feed", "MNQ_1m.csv"),
                os.path.join("le_feed", "NQ_1m.csv"), os.path.join("le_feed", "accounts.csv")):
        a = _status_age(nt, rel, now)
        if a is not None and a <= STALE_S:
            return True
    return False


def default_notify(title: str, body: str, key: str) -> None:
    """Telegram first (engine/alert_bus, when ALERTS_SETUP is done), else the PC's ntfy notice. Never raises."""
    try:
        from . import alert_bus
        if alert_bus.active():
            alert_bus.send({"kind": "remote", "key": key, "title": title, "body": body})
            return
    except Exception:  # noqa: BLE001
        pass
    try:
        from .autoupdate import notify
        notify(title, body, key=key)
    except Exception:  # noqa: BLE001
        pass


def tick(root: str, nt: str | None, now=None, flat=None, notify=None, env=None, apply: bool = True) -> list:
    """One hourly pass. [{"status": fixed | would | need | info | ok, "text"}]. Never raises."""
    env = os.environ if env is None else env
    now = time.time() if now is None else float(now)
    if str(env.get("LE_ROLL_AUTO", "1")) == "0" or not nt or not os.path.isdir(nt):
        return []
    notify = notify or default_notify
    try:
        return _tick(root, nt, now, flat, notify, apply)
    except Exception as e:  # noqa: BLE001
        return [{"status": "info", "text": f"roll autopilot skipped ({e.__class__.__name__}: {e})"}]


def _tick(root, nt, now, flat, notify, apply) -> list:
    from . import ns_sync
    from .ninjatrader import nt_instrument
    out = []
    st = _state(root)
    today = _et(now).date()
    rd = roll_day(today)
    days_left = (rd - today).days
    mode = read_mode(nt)
    installed = os.path.exists(ns_sync.dest(nt, "LE_Feed.cs"))
    quiet = _in_trading(now)
    busy = None if quiet else (flat() if callable(flat) else None)

    # 5. done: the roll day, the add-on (live) names the new contract
    lr = last_roll_day(today)
    if lr and lr == today and _et(now).hour * 60 + _et(now).minute >= 5 and st.get("done") != lr.isoformat():
        want = nt_instrument("MNQ", today)
        have = (_read(os.path.join(nt, "le_feed", "MNQ_instrument.txt")) or "").strip()
        rec = [x for x in (_read(os.path.join(nt, "le_ticks", "instruments.txt")) or "").split() if x]
        if have == want:
            if apply:
                st["done"] = lr.isoformat()
                notify(f"Roll done: {want}", f"Orders, bars (LE_Feed{'' if mode == 'live' else ' / chart'}) and the order-flow recorder "
                       f"are on {want.split(' ')[-1]}; the keep-alive trades it too. Nothing to do."
                       + ("" if not rec or any(want.split(' ')[-1] in r for r in rec) else " (order-flow list not switched yet)"),
                       f"roll:done:{lr.isoformat()}")
            out.append({"status": "fixed", "text": f"roll done: bars on {want}"})

    # 4. fallback: live mode, the add-on silent while NinjaTrader runs
    if mode == "live" and installed and st.get("switched"):
        age = _status_age(nt, os.path.join("le_feed", "le_feed_status.txt"), now)
        if (age is None or age > STALE_S) and nt_running(nt, now):
            if apply:
                write_mode(nt, "shadow")
                st.pop("switched", None)
                st["fallback"] = int(now)
                st["run"] = 0
                notify("Bars: back on your chart", "The LE_Feed add-on stopped writing, so your NinjaTrader chart feeds the bot again "
                       "(nothing to do; the roll then needs tools/bat/ROLL.bat as before).", f"roll:fallback:{int(now) // 3600}")
            out.append({"status": "fixed", "text": "LE_Feed silent in live mode: back to the chart (shadow)"})
            _save(root, st) if apply else None
            return out

    # 1. prep: shadow FIRST (also for an old LE_Feed that is installed but not feeding: an update must never take over the bars
    #    unverified), then the add-on. An add-on that already feeds the bot (the owner's own no-chart mode) is left alone.
    if mode is None and not live_fresh(nt, now) and (installed or days_left <= PREP_DAYS):
        if apply:
            write_mode(nt, "shadow")
            mode = "shadow"
        out.append({"status": "fixed" if apply else "would", "text": "LE_Feed set to shadow mode (the chart stays the bar source)"})
    if days_left <= PREP_DAYS and not installed and mode == "shadow":
        if quiet or busy:
            out.append({"status": "info", "text": f"roll prep waits ({'trading hours' if quiet else busy})"})
        elif apply:
            r = ns_sync.install(root, nt, "LE_Feed.cs", now, flat=lambda: None)
            st["installed"] = int(now)
            out.append({"status": "fixed" if r.get("ok") else "info",
                        "text": "roll prep: LE_Feed put into NinjaTrader in shadow mode (the chart stays the bar source)"
                        if r.get("ok") else f"roll prep: LE_Feed not installed ({r.get('why')})"})
        else:
            out.append({"status": "would", "text": "would put LE_Feed into NinjaTrader in shadow mode"})

    # 2. verify (shadow)
    if read_mode(nt) == "shadow":
        best = None
        for r in ROOTS:
            c = bars(os.path.join(nt, "le_feed", f"{r}_1m.csv"))
            s = bars(os.path.join(nt, "le_feed", "shadow", f"{r}_1m.csv"))
            if c and s:
                run, bad = verdict(compare(c, s), today.isoformat())
                if best is None or run < best[1]:
                    best = (r, run, bad)               # every root both write must be equal: the weakest counts
        if best:
            st.update(run=best[1], bad_day=best[2], checked=int(now))
            out.append({"status": "info", "text": f"LE_Feed shadow vs chart: {best[1]} equal day(s) in a row ({best[0]})"
                        + (f", different on {best[2]}" if best[2] else "")})
        # 3. switch
        if best and best[1] >= MATCH_DAYS and days_left <= PREP_DAYS:
            if quiet or busy:
                out.append({"status": "info", "text": f"switch to LE_Feed waits ({'trading hours' if quiet else busy})"})
            elif apply:
                write_mode(nt, "live")
                st["switched"] = int(now)
                notify("Bars now from LE_Feed", f"The no-chart add-on matched your chart bar for bar on {best[1]} days, so it feeds the "
                       f"bot now: the {rd.strftime('%b %d')} roll needs no click (your chart can stay open).", f"roll:live:{rd.isoformat()}")
                out.append({"status": "fixed", "text": f"switched the bars to LE_Feed (verified {best[1]} days)"})
            else:
                out.append({"status": "would", "text": "would switch the bars to LE_Feed"})
    if apply:
        _save(root, st)
    return out


def status(root: str = ROOT) -> dict:
    return _state(root)
