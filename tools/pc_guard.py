"""Guard pushes for the GitHub-free PC report (tools/pc_report.py, every 15 min on the main PC -> your private ntfy topic).
Read-only: it looks at what the bot already reports (its heartbeat, through engine/live_publish.build) and at NinjaTrader's
LE_BarFeed contract file. It never blocks, places, changes or cancels an order, never arms anything, never edits a setting.

  contract roll   engine/roll_watch.countdown: one push a day from 3 days before the roll to the eve (Mon Dec 7 .. Wed Dec 9
                  2026: "double-click ROLL.bat on Wed after 16:00 ET"), "roll ready" when the chart is already switched, the
                  late alarm while the chart sits on another month (no new entries), "roll done" once.
  drawdown        per eval account (Zlarior / LIT 50K, ATLAS 25K, BLITZ 25K; the board cards of engine/live_board): 50% and 75%
                  of the max loss used (1 - room / mll), once per level per eval; re-armed when it falls 10 points back.
  daily loss      today's loss (realized + the open trade's unrealized) at 70% of the account's daily loss limit, once a day.
  quiet bot       no trade for 5+ calendar days (normal: 2-4 a week; MFFU can close an eval after 7), once a day in the
                  daytime. Feed and bot silence were already pushed by pc_report (FEED STALE after 5 min, bot down after 15).
  day summary     16:05 ET on CME trading days (first report run 16:05-16:59): $ today, trades, drawdown left per account.
Numbers come only from a fresh heartbeat (<= 15 min); the day summary says plainly when the last one is older.

guard(state, snap, roll_state=None) -> (new state, [push]); state = {"sent": {key: t}}. Each key is sent once; pc_report
forgets a key whose push failed, so the next run tries it again. Quiet hours 23:00-07:00 ET for ordinary pushes (they wait);
high-priority ones (75% drawdown, daily loss near) go out at any hour, the roll's late alarm from 01:40 ET (before LIT's
02:00 window). Tests: tests/test_pc_guard.py (accounts, summary), tests/test_roll_now.py (roll).
"""
from __future__ import annotations

import datetime as dt
import time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
PREFIX = "guard:"
KEEP_S = 40 * 86400                     # sent keys are kept 40 days (day keys never come back after that)
QUIET_FROM, QUIET_TO = 23 * 60, 7 * 60  # no ordinary guard push between 23:00 and 07:00 ET
LATE_FROM = 100                         # the roll's late alarm: from 01:40 ET


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _mod(now: int) -> int:
    e = dt.datetime.fromtimestamp(int(now), ET)
    return e.hour * 60 + e.minute


def quiet(now: int) -> bool:
    m = _mod(now)
    return m >= QUIET_FROM or m < QUIET_TO


# ------------------------------------------------------------------------------------------------ contract roll
def roll_pushes(now: int, roll_state=None) -> list:
    from engine import roll_watch
    st = roll_state if roll_state is not None else roll_watch.fact(None, {}, now)
    out = []
    for m in roll_watch.countdown(st, now):
        late = m["key"].startswith("roll:late:")
        if late and _mod(now) < LATE_FROM:
            continue
        if not late and quiet(now):
            continue
        out.append({"key": PREFIX + m["key"], "title": m["title"], "body": m["body"], "priority": m.get("priority") or "default",
                    "tags": "warning" if late else "calendar"})
    return out


# ------------------------------------------------------------------------------------------------ eval accounts
DD_LEVELS = (0.5, 0.75)
DD_REARM = 0.10
DLL_NEAR = 0.70
QUIET_DAYS = 5
MFFU_IDLE_DAYS = 7
HB_FRESH_S = 900
SUMMARY_FROM, SUMMARY_TO = 16 * 60 + 5, 17 * 60       # 16:05 up to the 17:00 CME break (4 report runs); later = skipped
BOTS = ("lit", "atlas", "blitz")


def _f(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def money(x) -> str:
    v = _f(x)
    return "-" if v is None else ("-" if v < 0 else "") + "${:,.0f}".format(abs(v))


def signed(x) -> str:
    v = _f(x)
    return "-" if v is None else ("+" if v >= 0 else "-") + "${:,.0f}".format(abs(v))


def trading_day(now: int) -> str:
    """CME trading day: 18:00 ET starts the next day's session."""
    return (dt.datetime.fromtimestamp(int(now), ET) + dt.timedelta(hours=6)).date().isoformat()


def cards(snap: dict) -> list:
    """[(id, card)] of the accounts that are set up and still running an eval or a funded account."""
    bd = _d(_d(snap.get("live")).get("board"))
    out = []
    for k in BOTS:
        c = _d(bd.get(k))
        if not c or c.get("error") or c.get("off") or str(c.get("status") or "") in ("not set up", "off"):
            continue
        if k != "lit" and c.get("configured") is False:
            continue
        out.append((k, c))
    return out


def label(k: str, c: dict) -> str:
    import re
    size = re.search(r"(\d+K)", str(c.get("plan") or ""))
    name = {"lit": "Zlarior"}.get(k, str(c.get("name") or k.upper()))
    return f"{name} {size.group(1)}" if size else name


def real(k: str, c: dict, snap: dict) -> bool:
    if k == "lit":
        return snap.get("mode") == "LIVE"
    return bool(c.get("real")) or "LIVE" in str(c.get("badge") or "").upper()


def kind_word(k, c, snap) -> str:
    return "real account" if real(k, c, snap) else "Sim / paper"


def dd_used(c: dict):
    room, mll = _f(c.get("room")), _f(c.get("mll"))
    if room is None or not mll:
        return None
    return max(0.0, min(1.0, 1.0 - room / mll))


def account_pushes(snap: dict, sent: dict, now: int) -> list:
    """Drawdown 50 / 75 %, daily loss near, quiet bot. Mutates `sent` only to re-arm a drawdown level."""
    if snap.get("hb_age") is None or snap["hb_age"] > HB_FRESH_S:
        return []
    out = []
    day = trading_day(now)
    for k, c in cards(snap):
        name = label(k, c)
        status = str(c.get("status") or "open")
        live_eval = status not in ("passed", "failed", "lost", "graduated", "stuck")
        tag = str(c.get("eval_start") or "-")
        used = dd_used(c)
        if used is not None and live_eval:
            keys = {lvl: f"{PREFIX}dd:{k}:{tag}:{int(lvl * 100)}" for lvl in DD_LEVELS}
            for lvl in DD_LEVELS:
                if used < lvl - DD_REARM:
                    sent.pop(keys[lvl], None)
            for lvl in sorted(DD_LEVELS, reverse=True):          # only the highest new level: 0 -> 80% is one push
                key = keys[lvl]
                if used >= lvl and key not in sent:
                    for lower in DD_LEVELS:
                        if lower < lvl:
                            sent.setdefault(keys[lower], now)
                    left = _f(c.get("room"))
                    body = (f"{name} ({kind_word(k, c, snap)}): {used * 100:.0f}% of the drawdown used. Left {money(left)} of "
                            f"{money(c.get('mll'))}" + (f", balance {money(c.get('balance'))}, floor {money(c.get('floor'))}"
                                                        if _f(c.get("balance")) is not None and _f(c.get("floor")) is not None else "")
                            + f". Today {signed(c.get('today_pnl'))}. The bot sizes from the room by itself; this alert changes nothing.")
                    out.append({"key": key, "title": f"{name}: {int(lvl * 100)}% of the drawdown used", "body": body,
                                "priority": "high" if lvl >= 0.75 else "default", "tags": "warning"})
                    break
        dll = _f(c.get("dll"))
        if dll and live_eval:
            today = _f(c.get("today_pnl")) or 0.0
            pos = _d(c.get("position"))
            unreal = _f(pos.get("unrealized_usd")) or 0.0
            loss = max(0.0, -(today + min(0.0, unreal)), _f(c.get("dll_used")) or 0.0)
            if loss >= DLL_NEAR * dll:
                key = f"{PREFIX}dll:{k}:{day}"
                body = (f"{name} ({kind_word(k, c, snap)}): down {money(loss)} today of the {money(dll)} daily loss limit "
                        f"({loss / dll * 100:.0f}%)" + (f", {money(-unreal)} of it in the open trade" if unreal < 0 else "")
                        + ". The bot keeps its own stops; this alert changes nothing.")
                out.append({"key": key, "title": f"{name}: daily loss limit near ({loss / dll * 100:.0f}%)", "body": body,
                            "priority": "high", "tags": "warning"})
        q = c.get("quiet_days")
        if isinstance(q, (int, float)) and q >= QUIET_DAYS and live_eval and not quiet(now) and not c.get("position"):
            rl = real(k, c, snap)
            late = rl and q >= MFFU_IDLE_DAYS - 1
            body = (f"No {name} trade for {int(q)} days (normal: 2-4 a week). "
                    + (f"MFFU can close an eval after {MFFU_IDLE_DAYS} days without a trade. " if rl else "")
                    # day 6+ on a real eval (2026-11-14 drill): the bot has no keep-alive trade; the owner's fix is MFFU's own
                    # (the same advice as engine/ops_checks.inactivity_notice and the LIT plan page, engine/lit_brief.mffu_notes)
                    + ("Check in the MFFU dashboard that the account is still active, then place 1 MNQ by hand today (in and "
                       "out) while the bot is flat. " if late else "")
                    + "Check the bot runs (HEALTH CHECK on the PC) and what it waits for on the Start page.")
            out.append({"key": f"{PREFIX}quiet:{k}:{day}", "title": f"{name}: no trade for {int(q)} days", "body": body,
                        "priority": "high" if rl and q >= MFFU_IDLE_DAYS - 1 else "default", "tags": "hourglass"})
    return out


def day_summary(snap: dict, now: int) -> list:
    """The 16:05 ET push: $ today, trades and drawdown left per account (CME trading days only)."""
    e = dt.datetime.fromtimestamp(int(now), ET)
    m = e.hour * 60 + e.minute
    if e.weekday() >= 5 or not (SUMMARY_FROM <= m < SUMMARY_TO):
        return []
    try:
        from engine import cme_calendar
        if cme_calendar.full_closure(e.date()):
            return []
    except Exception:
        pass
    key = f"{PREFIX}day:{e.date().isoformat()}"
    cs = cards(snap)
    age = snap.get("hb_age")
    if not cs:
        why = "the bot has not reported" if age is None else f"no account numbers in the last report ({int(age) // 60} min ago)"
        return [{"key": key, "title": f"Day {e:%a %b %d}: no numbers", "body": f"No day summary: {why}. Double-click STATUS.bat on the PC.",
                 "priority": "default", "tags": "memo"}]
    lines, tot = [], 0.0
    for k, c in cs:
        t = _f(c.get("today_pnl"))
        tot += t or 0.0
        n = c.get("trades_today")
        room = _f(c.get("room"))
        lines.append(f"{label(k, c)}: {signed(t)}" + (f", {int(n)} trade{'s' if int(n) != 1 else ''}" if isinstance(n, (int, float)) else "")
                     + (f", drawdown left {money(room)} of {money(c.get('mll'))}" if room is not None else "")
                     + (f", {money(c.get('to_target'))} to target" if _f(c.get("to_target")) is not None and _f(c.get("to_target")) > 0 else "")
                     + ("" if real(k, c, snap) else " (Sim / paper)"))
    stale = age is None or age > HB_FRESH_S
    head = f"Day {e:%a %b %d}: {signed(tot)}" + (" (last report old)" if stale else "")
    body = "; ".join(lines) + "." + (f" These are the numbers of the last report, {int(age) // 60} min ago." if stale and age is not None else "")
    return [{"key": key, "title": head, "body": body, "priority": "default", "tags": "memo"}]


# ------------------------------------------------------------------------------------------------ one run
def guard(state: dict | None, snap: dict, roll_state=None) -> tuple:
    """(new guard state, [push messages]) for one PC report run. Never raises (a failure sends nothing)."""
    st = {"sent": dict(_d(_d(state).get("sent")))}
    now = int(snap.get("t") or time.time())
    cands = []
    try:
        cands += roll_pushes(now, roll_state if roll_state is not None else snap.get("roll"))
    except Exception:
        pass
    try:
        cands += account_pushes(snap, st["sent"], now)
    except Exception:
        pass
    try:
        cands += day_summary(snap, now)
    except Exception:
        pass
    msgs = []
    for m in cands:
        if m["key"] in st["sent"]:
            continue
        if quiet(now) and m.get("priority") != "high":      # an ordinary push waits for 07:00 ET (it is not marked sent)
            continue
        st["sent"][m["key"]] = now
        msgs.append(m)
    for k in [k for k, t in st["sent"].items() if now - int(t or 0) > KEEP_S]:
        st["sent"].pop(k, None)
    return st, msgs


def forget(state: dict | None, key: str) -> None:
    """A push that did not go out: drop its key so the next run sends it again."""
    _d(_d(state).get("sent")).pop(key, None)
