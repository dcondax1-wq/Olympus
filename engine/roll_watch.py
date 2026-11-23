"""The quarterly contract roll on the NinjaTrader route, as the owner sees it (read-only: never routes, arms or sizes).

Next roll: Thursday 2026-12-10 00:00 ET, the front month goes from 12-26 to 03-27 (MNQ and NQ alike; 8 days before the
Dec 18 expiry, engine/ninjatrader.nt_instrument). The ORDER contract switches by itself by the ET date. The LE_BarFeed
chart (MNQ, or the NQ chart with signal_root "NQ") the owner switches by hand: le_feed\\<ROOT>_instrument.txt says which
contract it is on. While they differ the adapter sends no new entry (ninjatrader.contract_problem, the roll guard;
tests/test_nt_roll_guard.py) and pcbars.merge_basis back-adjusts the older bars once the chart is on the new contract
(tests/test_roll.py, tests/test_dec_roll.py). The owner's steps: docs/ROLL_DEC_2026.md.

  state(now, chart, root)   {"orders", "chart", "root", "level", "say", "fix", "problem", "roll": {...}}; level:
                            ok | soon (roll within 7 days) | early (chart already on the next contract, orders follow
                            at 00:00 ET) | bad (chart on another month: no new entry) | unknown (no contract file) |
                            continuous ("MNQ ##-##": the roll check is off)
  fact(folder, cfg, now)    state() for the PC's own LE_BarFeed files (launch checklist facts, heartbeat "launch")
  problem(folder, cfg, now) the one line for the Start page's "Live bars from NinjaTrader" (go.feed_problem), or None
  launch_item(st)           the launch checklist line ("roll": red only when level is bad)
  reminders(now)            7 days before / the day before (date only; the same keys as engine/ops_checks.roll_notice)
  late_notice(st, now)      on and after the roll day while the chart is still on the old contract (once a trading day)
  cloud_notices(pc, now)    what the cloud monitor pushes (tools/cloud_monitor.py): the reminders and the late alarm, only
                            when the PC's own 5-minute helper (engine/ops_checks --tick) is not running (no double push)
  countdown(st, now)        the phone pushes of the GitHub-free PC report (tools/pc_guard.py -> ntfy): one a day from 3 days
                            before the roll to the eve (Mon Dec 7 .. Wed Dec 9), "chart already switched", the late alarm
                            (late_notice) and "roll done" once. Read-only, like everything here.
"""
from __future__ import annotations

import datetime as dt
import time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
SOON_DAYS = 7
OPS_FRESH_S = 3600                      # the PC's ops tick ran within the hour: the PC pushes the roll notices itself
HB_FRESH_S = 20 * 60


def _et(t) -> dt.datetime:
    return dt.datetime.fromtimestamp(int(t), ET)


def next_roll(today: dt.date):
    """(roll day, old contract, new contract) of the next quarterly roll, MNQ names (ops_checks.next_roll's rule)."""
    from .ninjatrader import nt_instrument
    cur = nt_instrument("MNQ", today)
    for i in range(1, 120):
        d = today + dt.timedelta(days=i)
        n = nt_instrument("MNQ", d)
        if n != cur:
            return d, cur, n
    return None


def last_roll(today: dt.date):
    """(roll day, old, new) of the roll that put today's order contract in place (within 100 days), else None."""
    from .ninjatrader import nt_instrument
    cur = nt_instrument("MNQ", today)
    for i in range(0, 100):
        d = today - dt.timedelta(days=i)
        prev = nt_instrument("MNQ", d - dt.timedelta(days=1))
        if prev != cur:
            return d, prev, cur
    return None


def _month(name) -> str:
    return str(name or "").split(" ")[-1]


def state(now=None, chart: str | None = None, root: str | None = None) -> dict:
    """The chart contract against the order contract on the ET date of `now`."""
    from .ninjatrader import contract_expiry, contract_problem, nt_instrument
    now = int(now if now is not None else time.time())
    today = _et(now).date()
    orders = nt_instrument("MNQ", today)
    nr = next_roll(today)
    roll = None
    if nr:
        day, old, new = nr
        roll = {"day": day.isoformat(), "old": old, "new": new, "in_days": (day - today).days,
                "eve": (day - dt.timedelta(days=1)).isoformat()}
    croot = (root or (str(chart).split(" ")[0] if chart else None) or "MNQ")
    out = {"orders": orders, "chart": chart, "root": root, "roll": roll, "problem": None, "fix": ""}
    want = f"{croot} {_month(orders)}"

    def switch(to):
        return f"NinjaTrader: right-click the {croot} chart > Instrument > {to}, Days to load 30, OK, save workspace"
    if not chart:
        out.update(level="unknown", say=f"chart contract unknown (no {croot}_instrument.txt: recompile LE_BarFeed); "
                                        f"orders go to {orders}")
        return out
    ce, oe = contract_expiry(chart), contract_expiry(orders)
    if ce is None:
        out.update(level="continuous", say=f"chart on a continuous contract ({chart}): roll check off", fix=switch(want))
        return out
    if ce == oe:
        if roll and 1 <= roll["in_days"] <= SOON_DAYS:
            r = dt.date.fromisoformat(roll["day"])
            e = dt.date.fromisoformat(roll["eve"])
            to = f"{croot} {_month(roll['new'])}"
            out.update(level="soon", say=f"roll {r:%a %b %d}: orders go to {roll['new']} by themselves; switch the chart "
                                         f"{e:%a %b %d} after 16:00 ET", fix=switch(to))
        else:
            out.update(level="ok", say=f"chart {chart}, orders {orders}"
                                       + (f"; next roll {dt.date.fromisoformat(roll['day']):%a %b %d}" if roll else ""))
        return out
    e_now = _et(now)
    if roll and ce == contract_expiry(roll["new"]) and roll["in_days"] == 1 and e_now.hour * 60 + e_now.minute >= 955:
        # switched the evening before, after the 15:55 flat: the adapter refuses entries until 00:00 ET, and LIT has none
        # before 02:00. Switched during the day before: red (no entry for the rest of that session).
        out.update(level="early", say=f"chart already on {chart}; orders follow at 00:00 ET ({roll['old']} until then)")
        return out
    lr = last_roll(today)
    since = f" since {lr[0]:%a %b %d}" if lr and ce < oe else ""
    out.update(level="bad", problem=contract_problem(chart, [orders]),
               say=f"chart still on {chart}, orders on {orders}{since}: no new entry" if ce < oe else
               f"chart on {chart}, orders on {orders}: no new entry", fix=switch(want))
    return out


def fact(folder=None, cfg: dict | None = None, now=None) -> dict:
    """state() for the PC's LE_BarFeed files: the chart the bot decides on (signal_root) and its contract. Never raises."""
    try:
        from .ninjatrader import NinjaTraderBars, default_folder, signal_root
        cfg = cfg or {}
        feed = NinjaTraderBars(folder or cfg.get("nt_folder") or default_folder(), roots=cfg.get("nt_feed_roots"))
        root = feed.root_for("NQ")
        st = state(now, feed.chart_instrument("NQ"), root)
        st["signal_root"] = signal_root(cfg)
        return st
    except Exception as e:
        return {"level": "unknown", "say": f"roll check failed: {e.__class__.__name__}", "problem": None}


def problem(folder=None, cfg: dict | None = None, now=None) -> str | None:
    """None unless the chart the bot decides on sits on another contract month than the orders (no new entry then)."""
    st = fact(folder, cfg, now)
    if st.get("level") != "bad":
        return None
    return f"{PREFIX}{st['say']}. Fix: {st['fix']}"


PREFIX = "Contract roll: "


def is_problem_text(why) -> bool:
    """Is this feed_problem() text the roll line (it carries its own fix, not the chart-reload one)?"""
    return str(why or "").startswith(PREFIX)


CHECK_CMD = "python tools/roll_check.py"


def launch_item(st: dict | None) -> dict:
    """The launch checklist line "Chart contract (roll)": good (chart = the order month, or already on the next one the
    evening before), bad (another month: no new entry; the detail says the NinjaTrader click, the fix is the check
    command), info (roll within 7 days: the reminder; contract unknown / continuous; an older heartbeat without it)."""
    st = st or {}
    lvl = st.get("level") or "unknown"
    state_ = "good" if lvl in ("ok", "early") else "bad" if lvl == "bad" else "info"
    detail = st.get("say") or "not checked yet (update the PC bot)"
    if lvl in ("bad", "soon", "continuous") and st.get("fix"):
        detail = f"{detail}. Fix: {st['fix']}"
    return {"key": "roll", "label": "Chart contract (roll)", "state": state_, "detail": detail,
            "fix": CHECK_CMD if lvl == "bad" else ""}


def compact(st: dict | None) -> dict:
    """The fields the heartbeat carries (launch facts "roll"), without the long texts' duplicates."""
    st = st or {}
    r = st.get("roll") or {}
    return {k: v for k, v in {"level": st.get("level"), "chart": st.get("chart"), "root": st.get("root"),
                              "orders": st.get("orders"), "signal_root": st.get("signal_root"), "say": st.get("say"),
                              "fix": st.get("fix") or None,
                              "roll": {"day": r.get("day"), "new": r.get("new"), "in_days": r.get("in_days")} if r else None
                              }.items() if v is not None}


# ---------------------------------------------------------------------------------------------------- pushes
def reminders(now=None) -> list:
    """The dated reminders: {"key", "title", "body"} 2-7 days before the roll (key ...:week) and the day before
    (...:tomorrow). Same keys and wording as engine/ops_checks.roll_notice (the PC's 5-minute helper)."""
    now = int(now if now is not None else time.time())
    today = _et(now).date()
    nr = next_roll(today)
    if not nr:
        return []
    day, old, new = nr
    n = (day - today).days
    if n > SOON_DAYS or n < 1:
        return []
    eve = day - dt.timedelta(days=1)
    when = "tomorrow" if n == 1 else f"in {n} days"
    body = (f"Orders switch to {new} by themselves on {day:%a %b %d}. You switch the chart: on {eve:%a %b %d} after 16:00 ET open "
            f"the NinjaTrader chart with LE_BarFeed, type {new} as its instrument (NQ chart: NQ {_month(new)}), Data Series > "
            "Days to load 30, OK. Check LE_BarFeed is still on it, then run HEALTH CHECK (bar feed green).")
    return [{"key": f"ops:roll:{new}:{'tomorrow' if n == 1 else 'week'}", "title": f"Contract roll {when}: {old} -> {new}",
             "body": body}]


def late_notice(st: dict | None, now=None) -> dict | None:
    """The chart still on the old contract after the roll (level bad): one push per trading day."""
    st = st or {}
    if st.get("level") != "bad":
        return None
    now = int(now if now is not None else time.time())
    e = _et(now)
    day = (e.date() + dt.timedelta(days=1)) if e.hour >= 18 else e.date()
    from .ninjatrader import contract_expiry
    ce, oe = contract_expiry(st.get("chart")), contract_expiry(st.get("orders"))
    old = bool(ce and oe and ce < oe)
    return {"key": f"roll:late:{st.get('orders')}:{day.isoformat()}",
            "title": f"Chart still on {st.get('chart')}: no new entries" if old else
            f"Chart on {st.get('chart')}, orders on {st.get('orders')}: no new entries",
            "body": f"{st['say'][0].upper()}{st['say'][1:]}. Fix it: {st.get('fix')}."}


def cloud_notices(pc: dict | None, now=None) -> list:
    """What the cloud monitor pushes about the roll: the dated reminders (even with the PC off) and the late alarm from
    the PC's heartbeat ("launch" facts "roll"), unless the PC's own ops helper ran within the hour (it pushes the same)."""
    now = int(now if now is not None else time.time())
    pc = pc or {}
    ops = pc.get("ops") if isinstance(pc.get("ops"), dict) else {}
    tick = ops.get("tick_t")
    if pc.get("present") and tick and now - int(tick) <= OPS_FRESH_S:
        return []
    out = list(reminders(now))
    st = (((pc.get("launch") or {}).get("facts") or {}).get("roll")) if isinstance(pc.get("launch"), dict) else None
    age = pc.get("age_s")
    if st and pc.get("present") and (age is None or age <= HB_FRESH_S):
        n = late_notice(st, now)
        if n:
            out.append(n)
    return out


# ---------------------------------------------------------------------------------- the countdown (PC report, ntfy)
WARN_FROM_DAYS = 3                      # Thu Dec 10 roll -> one push a day on Mon Dec 7, Tue Dec 8, Wed Dec 9
DONE_DAYS = 4                           # "roll done" is said once, within 4 days after the roll day
ROLL_BAT = "tools/bat/ROLL.bat"


def countdown(st: dict | None, now=None) -> list:
    """[{"key", "title", "body", "priority"}] for the PC report's phone pushes (tools/pc_guard.py sends each key once).
    st = state() / fact() of this PC's chart. Never raises."""
    try:
        return _countdown(st or {}, int(now if now is not None else time.time()))
    except Exception:
        return []


def _countdown(st: dict, now: int) -> list:
    from .ninjatrader import contract_expiry
    today = _et(now).date()
    out = []
    lvl = st.get("level")
    nr = next_roll(today)
    if nr:
        day, old, new = nr
        n = (day - today).days
        eve = day - dt.timedelta(days=1)
        if lvl == "early":
            out.append({"key": f"roll:ready:{new}", "title": f"Roll ready: chart on {st.get('chart')}",
                        "body": f"The chart is already on {st.get('chart')}. Orders follow at 00:00 ET {day:%a %b %d} by themselves. "
                                "Nothing else to do.", "priority": "default"})
        elif 1 <= n <= WARN_FROM_DAYS:
            title = (f"Contract roll tonight: {old} -> {new}" if n == 1 else
                     f"Contract roll in {n} days: {old} -> {new}")
            when = "Tonight" if n == 1 else f"On {eve:%a %b %d}"
            unknown = (" (The PC cannot see the chart's contract right now: open NinjaTrader with the LE_BarFeed chart.)"
                       if lvl in ("unknown", "continuous", None) else "")
            body = (f"On {day:%a %b %d} at 00:00 ET the orders switch to {new} by themselves (every bot is flat then). "
                    f"{when} after 16:00 ET: double-click {ROLL_BAT} on the PC. It waits until every bot is flat, tells you the "
                    f"one NinjaTrader click (chart > Instrument > {new}) and checks it.{unknown}")
            out.append({"key": f"roll:soon:{new}:{today.isoformat()}", "title": title, "body": body,
                        "priority": "high" if n == 1 else "default"})
    ln = late_notice(st, now)
    if ln:
        out.append({"key": ln["key"], "title": ln["title"],
                    "body": f"{ln['body']} Or double-click {ROLL_BAT} on the PC: it shows the click and checks it.",
                    "priority": "high"})
    lr = last_roll(today)
    if lr and lvl == "ok" and 0 <= (today - lr[0]).days <= DONE_DAYS:
        ce, oe = contract_expiry(st.get("chart")), contract_expiry(lr[2])
        if ce and ce == oe:
            out.append({"key": f"roll:done:{lr[2]}", "title": f"Roll done: chart and orders on the {_month(lr[2])} contract",
                        "body": f"Chart {st.get('chart')}, orders {st.get('orders')}. The bot trades the new contract as usual.",
                        "priority": "default"})
    return out
