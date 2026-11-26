"""Guard pushes for the GitHub-free PC report (tools/pc_report.py, every 15 min on the main PC -> your private ntfy topic).
Read-only: it looks at what the bot already reports (its heartbeat, through engine/live_publish.build) and at NinjaTrader's
LE_BarFeed contract file. It never blocks, places, changes or cancels an order, never arms anything, never edits a setting.

  contract roll   engine/roll_watch.countdown: one push a day from 3 days before the roll to the eve (Mon Dec 7 .. Wed Dec 9
                  2026: "double-click tools/bat/ROLL.bat on Wed after 16:00 ET"), "roll ready" when the chart is already switched, the
                  late alarm while the chart sits on another month (no new entries), "roll done" once.
  drawdown        per eval account (Zlarior / LIT 50K, ATLAS 25K, BLITZ 25K; the board cards of engine/live_board): 50% and 75%
                  of the max loss used (1 - room / mll), once per level per eval; re-armed when it falls 10 points back.
  daily loss      today's loss (realized + the open trade's unrealized) at 70% of the account's daily loss limit, once a day.
  quiet bot       no trade for 5+ calendar days (normal: 2-4 a week; MFFU can close an account after 7, a funded one then loses
                  ALL its profits), once a day in the daytime, per account: the 50K, ATLAS and BLITZ from their board cards, the
                  extra accounts (the 25K #2, the Rapid EOD: both its lanes) from the live view's account sections (2026-11-20).
                  The count knows only the bot's own trades. Feed and bot silence were already pushed by pc_report (FEED STALE
                  after 5 min, bot down after 15).
  milestones      eval progress 25 / 50 / 75 / 100% of the profit target (notify_settings.json milestones_pct), once per level.
  day summary     16:15 ET on CME trading days (daily_summary_at, first report run up to 16:59): $ today, $ to pass, room left per
                  account, tomorrow's big US news (engine/notify.news_line).
  morning brief   07:30 ET on CME trading days (notify_settings.json morning_brief_at, up to 09:30; tools/morning_brief.py): ONE
                  4-line ZEUS push (PC ok?, each account $ / to pass / to payout, overnight + today's hours + news, edge + needs you)
                  and one Board event "brief"; key guard:brief:<day>, so a restart never repeats it.
  ready           01:35-01:59 ET on CME trading days (tools/launch_card.ready_push, Monday launch kit 2026-11-14): every bot's
                  mode (LIVE armed / Sim / paper) and drawdown left, the bot, NinjaTrader and the feed; "Ready for 02:00 ET"
                  is a silent (low) push at night, "NOT ready" (what is wrong + its one action) a high one.
Numbers come only from a fresh heartbeat (<= 15 min); the day summary says plainly when the last one is older.

guard(state, snap, roll_state=None) -> (new state, [push]); state = {"sent": {key: t}}. Each key is sent once; pc_report
forgets a key whose push failed, so the next run tries it again. Quiet hours (notify_settings.json, default 23:00-07:00 ET) for
ordinary pushes (they wait);
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


def _settings() -> dict:
    try:
        from engine import notify
        return notify.settings()
    except Exception:
        return {}


def quiet(now: int) -> bool:
    """Quiet hours from notify_settings.json (default 23:00-07:00 ET, the old QUIET_FROM / QUIET_TO)."""
    try:
        from engine import notify
        return notify.quiet(now)
    except Exception:
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
                    "tags": "warning" if late else "calendar", "kind": "problems"})   # a missed roll = the wrong contract: stays on under "important only"
    return out


# ------------------------------------------------------------------------------------------------ eval accounts
DD_LEVELS = (0.5, 0.75)
DD_REARM = 0.10
DLL_NEAR = 0.70
QUIET_DAYS = 5
MFFU_IDLE_DAYS = 7
HB_FRESH_S = 900
SUMMARY_FROM, SUMMARY_TO = 16 * 60 + 15, 17 * 60      # notify_settings.json daily_summary_at (16:15) up to the 17:00 CME break
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


def dd_levels() -> tuple:
    v = _settings().get("room_low_used_pct")
    return tuple(sorted(x / 100.0 for x in v)) if isinstance(v, list) and v else DD_LEVELS


def goal_levels() -> tuple:
    v = _settings().get("milestones_pct")
    return tuple(sorted(int(x) for x in v)) if isinstance(v, list) else (25, 50, 75, 100)


def milestone_pushes(k: str, c: dict, snap: dict, sent: dict, now: int) -> list:
    """Eval progress (owner 2026-11-17): 25 / 50 / 75 / 100% of the profit target made, once per level per eval (only the
    highest new level: 0 -> 60% is one push). Never re-armed: a level said once is not said again after a loss."""
    try:
        from engine import notify
        pr = notify.progress(c)
    except Exception:
        pr = None
    if not pr:
        return []
    made, goal, pct = pr
    tag = str(c.get("eval_start") or "-")
    name = label(k, c)
    for lvl in sorted(goal_levels(), reverse=True):
        key = f"{PREFIX}goal:{k}:{tag}:{lvl}"
        if pct + 1e-9 < lvl:
            continue
        if key in sent:
            return []
        for lower in goal_levels():
            if lower < lvl:
                sent.setdefault(f"{PREFIX}goal:{k}:{tag}:{lower}", now)
        room = _f(c.get("room"))
        tail = (f" Room left {money(room)} of {money(c.get('mll'))}." if room is not None else "") + f" ({kind_word(k, c, snap)})"
        if lvl >= 100:
            return [{"key": key, "title": f"{name}: profit target reached ({money(goal)})",
                     "body": f"{signed(made)} made of the {money(goal)} target. Check MFFU for the pass (its other rules still count).{tail}",
                     "priority": "high", "tags": "tada"}]
        return [{"key": key, "title": f"{name}: {lvl}% of the target made ({money(made)} of {money(goal)})",
                 "body": f"{money(goal - made)} to pass.{tail}", "priority": "default", "tags": "chart_with_upwards_trend"}]
    return []


def account_pushes(snap: dict, sent: dict, now: int) -> list:
    """Room used 50 / 75 % ("room getting low"), eval progress 25 / 50 / 75 / 100 %, daily loss near, quiet bot. Mutates
    `sent` only to re-arm a drawdown level and to mark lower milestone levels as said."""
    if snap.get("hb_age") is None or snap["hb_age"] > HB_FRESH_S:
        return []
    out = []
    day = trading_day(now)
    levels = dd_levels()
    for k, c in cards(snap):
        name = label(k, c)
        status = str(c.get("status") or "open")
        live_eval = status not in ("passed", "failed", "lost", "graduated", "stuck")
        tag = str(c.get("eval_start") or "-")
        used = dd_used(c)
        if status not in ("failed", "lost", "stuck"):
            out += milestone_pushes(k, c, snap, sent, now)
        if used is not None and live_eval:
            keys = {lvl: f"{PREFIX}dd:{k}:{tag}:{int(round(lvl * 100))}" for lvl in levels}
            for lvl in levels:
                if used < lvl - DD_REARM:
                    sent.pop(keys[lvl], None)
            for lvl in sorted(levels, reverse=True):              # only the highest new level: 0 -> 80% is one push
                key = keys[lvl]
                if used >= lvl and key not in sent:
                    for lower in levels:
                        if lower < lvl:
                            sent.setdefault(keys[lower], now)
                    left = _f(c.get("room"))
                    low = lvl >= 0.75 or lvl == max(levels)
                    body = (f"{name} ({kind_word(k, c, snap)}): {used * 100:.0f}% of the drawdown used. Left {money(left)} of "
                            f"{money(c.get('mll'))}" + (f", balance {money(c.get('balance'))}, floor {money(c.get('floor'))}"
                                                        if _f(c.get("balance")) is not None and _f(c.get("floor")) is not None else "")
                            + f". Today {signed(c.get('today_pnl'))}. The bot sizes from the room by itself; this alert changes nothing.")
                    title = (f"{name}: room getting low, {money(left)} left of {money(c.get('mll'))}" if low
                             else f"{name}: {int(round(lvl * 100))}% of the room used, {money(left)} left")
                    out.append({"key": key, "title": title, "body": body, "priority": "high" if low else "default", "tags": "warning"})
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
        q = c.get("quiet_days")             # (the board counts a keep-alive / hand trade noted: engine/keepalive)
        ka_cover = bool(_d(c.get("keepalive")).get("cover"))   # the bot's keep-alive sends this account's ONE warning a day
        if isinstance(q, (int, float)) and q >= QUIET_DAYS and live_eval and not quiet(now) and not c.get("position") \
                and not ka_cover:
            out.append(quiet_push(k, name, int(q), real(k, c, snap), funded_card(c), day, busy_others(snap, k)))
    # the extra accounts (the 25K #2, the Rapid EOD; skeptic 2026-11-20: the board's cards cover only the 50K, ATLAS and BLITZ, so
    # these two had no 7-day alert at all)
    for k, a in extra_cards(snap):
        q = extra_quiet_days(a, now)
        funded = a.get("kind") == "funded"
        # an eval's own clock says passed / failed (engine/accounts.eval_view); a funded account has no eval clock (its eval numbers
        # would read "passed" once its profit tops the eval target), so only an eval is filtered by it
        status = "open" if funded else str(_d(a.get("eval")).get("status") or "open").lower()
        if (q is None or q < QUIET_DAYS or status in STOP_STATUSES or quiet(now) or a.get("position")
                or str(a.get("badge") or "").upper() != "LIVE" or _d(a.get("keepalive")).get("cover")):
            continue
        out.append(quiet_push(k, extra_name(a), int(q), True, funded, day, busy_others(snap, k)))
    return out


STOP_STATUSES = ("passed", "failed", "lost", "graduated", "stuck")


def funded_card(c: dict) -> bool:
    """A board card of a funded account (ATLAS's funded 25K: engine/live_board.atlas_now stage "funded")."""
    return str(c.get("stage") or "").lower() == "funded" or str(c.get("status") or "").lower() == "funded"


def busy_others(snap: dict, k: str) -> list:
    """Names of the OTHER accounts (board cards + extra accounts) that hold an open trade now. day-alerts 2026-11-21 (wf-alert-fix
    HIGH): "place 1 MNQ by hand" is said only when EVERY account is flat: a hand trade against another account's open bot trade is a
    hedge (MFFU rule) and can end both accounts. Never raises."""
    try:
        out = [label(k2, c2) for k2, c2 in cards(snap) if k2 != k and c2.get("position")]
        out += [extra_name(a) for k2, a in extra_cards(snap) if k2 != k and a.get("position")]
        return out
    except Exception:  # noqa: BLE001
        return []


def quiet_push(k: str, name: str, q: int, rl: bool, funded: bool, day: str, busy=()) -> dict:
    """The "no trade for N days" push of one account (key guard:quiet:<id>:<day>, once a day; notify kind account_status: both apps).
    MFFU's rule (mffu_rules.json inactivity): 7 calendar days without a trade and the account can be closed; a sim-funded one then
    loses ALL its profits."""
    busy = list(busy or [])
    late = rl and q >= MFFU_IDLE_DAYS - 1 and not busy
    rule = (f"MFFU can close a funded account after {MFFU_IDLE_DAYS} days without a trade, and it then loses ALL its profits. " if funded
            else f"MFFU can close an eval after {MFFU_IDLE_DAYS} days without a trade. ")
    body = (f"No {name} trade for {q} days (normal: 2-4 a week). "
            + (rule if rl else "")
            # day 6+ on a real account (2026-11-14 drill): the bot has no keep-alive trade; the owner's fix is MFFU's own (the same
            # advice as engine/ops_checks.inactivity_notice and the LIT plan page, engine/lit_brief.mffu_notes)
            + ("Check in the MFFU dashboard that the account is still active, then place 1 MNQ by hand today (in and "
               "out) while EVERY account is flat. " if late else "")
            + (f"Do NOT place a hand trade yet: {', '.join(busy)} has an open trade (a hand trade now is a hedge). "
               "Wait until every account is flat. " if rl and busy and q >= MFFU_IDLE_DAYS - 1 else "")
            # the count knows only the bot's own trades on this account (its ledger): a trade placed by hand may not reset it
            + ("This count knows only the bot's own trades (for one you placed yourself, MFFU's dashboard is the truth). " if rl else "")
            + "Check the bot runs (HEALTH CHECK on the PC) and what it waits for on the Start page.")
    return {"key": f"{PREFIX}quiet:{k}:{day}", "title": f"{name}: no trade for {q} days", "body": body,
            "priority": "high" if rl and q >= MFFU_IDLE_DAYS - 1 else "default", "tags": "hourglass",
            **({"kind": "account_status"} if rl else {})}     # the 7-day rule on a real account: on + rings (day 5 / 6; day-alerts)


def extra_cards(snap: dict) -> list:
    """[(id, section)] of the PC's extra accounts (engine/multi_account: the 25K #2, the Rapid EOD's LIT lane ...): the live view's
    account sections with extra=True (engine/accounts.build_accounts). ids are the bot's own ("b25k_2", "rapid"), never a broker id."""
    out = []
    for a in _d(snap.get("live")).get("accounts") or []:
        if isinstance(a, dict) and a.get("extra") and a.get("id") and not a.get("error"):
            out.append((str(a["id"]), a))
    return out


def extra_quiet_days(a: dict, now: int):
    """Calendar days (ET) without a trade on an extra account (engine/live_board.quiet_days): its trades' days and its P&L days (on
    the Rapid both lanes: engine/multi_account.eval_days adds ATLAS's lane), counted from its eval / funded start when it has none.
    None when nothing is known."""
    try:
        from engine import live_board
        start = (_d(a.get("funded")).get("start") if a.get("kind") == "funded" else None) or _d(a.get("eval")).get("start")
        days = [t.get("day") for t in a.get("trades") or [] if isinstance(t, dict)]
        days += [d[0] for d in a.get("days") or [] if isinstance(d, (list, tuple)) and d]
        return live_board.quiet_days(days, start, now)
    except Exception:
        return None


def extra_name(a: dict) -> str:
    """The owner's name of an extra account ("Zlarior 25K #2", "Rapid EOD 25K"; engine/mffu_view.owner_name, words only), ids masked."""
    try:
        from engine import mffu_view, notify
        return notify.mask_ids(mffu_view.owner_name(a.get("id"), a.get("name"), a.get("plan"), a.get("kind")))[:40]
    except Exception:
        return "Extra account"


def evening_extra(day: str, pa_path=None, digest_path=None, fleet=None) -> str:
    """night-brief 2026-11-23: what the ONE evening message adds after the $ per account: the payouts ready now (engine/payout_autopilot's
    last views), the fleet's next money move (engine/fleet_mgr) and the day's low-priority lines (engine/alert_bus.digest_peek: an update
    applied ...). '' when none. Never raises."""
    out = []
    try:
        import json as _json
        from engine import payout_autopilot as PA
        with open(pa_path or PA.STATE_PATH, encoding="utf-8") as fh:
            last = _json.load(fh).get("last") or {}
        import time as _time                    # red team 2: an autopilot run older than 2 h = not today's payouts: say nothing
        v = (last.get("views") or []) if _time.time() - float(last.get("t") or 0) <= 7200 else []
        rdy = [f"{x.get('name')} {money(x.get('amount'))}" for x in v if isinstance(x, dict) and x.get("ready")]
        stop = [str(x.get("name")) for x in v if isinstance(x, dict) and x.get("guard") == "stop"]
        if rdy:
            out.append("REQUEST PAYOUT TODAY: " + ", ".join(rdy) + " (MFFU dashboard > Payouts, then TRADE_HOME -> P)")
        if stop:
            out.append("Do not take payout #5 on " + ", ".join(stop) + ": close it")
    except Exception:
        pass
    try:
        if fleet is None:
            from engine import fleet_mgr as FM
            s = str((FM.read_tiny() or {}).get("s") or "")
            fleet = s.split("Next: ", 1)[1] if "Next: " in s else ""
        if fleet:
            out.append("Tomorrow: " + fleet)
    except Exception:
        pass
    try:                                        # big-shadow: the buy gate + the shadow eval (display only; OFF unless switched on)
        from tools import morning_brief as _mb
        bg = _mb.buy_gate_line(key="line")      # the private 16:15 push: with the business $ (red team #19: never on the public feed)
        if bg:
            out.append(bg)
            from engine import buy_gate as _bg
            sh = str((_bg.SE._read(_bg.OUT, {}) or {}).get("shadow") or "")
            if sh:
                out.append(sh)
    except Exception:
        pass
    try:
        from engine import alert_bus as AB
        dg = [x for x in AB.digest_peek(day, digest_path) if x][:4]
        if dg:
            out.append("Also: " + "; ".join(dg))
    except Exception:
        pass
    return (" " + " ".join(x.rstrip(".") + "." for x in out)) if out else ""


def day_summary(snap: dict, now: int, sent: dict | None = None) -> list:
    """The day summary after the close (notify_settings.json daily_summary_at, 16:15 ET, up to the 17:00 CME break; CME
    trading days only): per account $ today, $ to pass and the room left, then tomorrow's big US news."""
    e = dt.datetime.fromtimestamp(int(now), ET)
    m = e.hour * 60 + e.minute
    try:
        from engine import notify
        frm = notify.hm_min(_settings().get("daily_summary_at"), SUMMARY_FROM)
    except Exception:
        notify, frm = None, SUMMARY_FROM
    if e.weekday() >= 5 or not (frm <= m < SUMMARY_TO):
        return []
    try:
        from engine import cme_calendar
        if cme_calendar.full_closure(e.date()):
            return []
    except Exception:
        pass
    key = f"{PREFIX}day:{e.date().isoformat()}"
    if key in (sent or {}):
        return []                    # sent already: no rebuild (a later digest line waits for tomorrow's summary, never dropped)
    try:
        news = " " + notify.news_line(now) if notify else ""
    except Exception:
        news = ""
    cs = cards(snap)
    age = snap.get("hb_age")
    if not cs:
        why = "the bot has not reported" if age is None else f"no account numbers in the last report ({int(age) // 60} min ago)"
        return [{"key": key, "title": f"Day {e:%a %b %d}: no numbers", "body": f"No day summary: {why}. Double-click tools/bat/STATUS.bat on the PC.{news}",
                 "priority": "default", "tags": "memo"}]
    lines, tot = [], 0.0
    for k, c in cs:
        t = _f(c.get("today_pnl"))
        tot += t or 0.0
        room = _f(c.get("room"))
        tt = _f(c.get("to_target"))
        lines.append(f"{label(k, c)}: {signed(t)} today"
                     + (f", {money(tt)} to pass" if tt is not None and tt > 0 else ", target reached" if tt is not None else "")
                     + (f", room {money(room)} of {money(c.get('mll'))}" if room is not None else "")
                     + ("" if real(k, c, snap) else " (Sim / paper)"))
    stale = age is None or age > HB_FRESH_S
    head = f"Day {e:%a %b %d}: {signed(tot)}" + (" (last report old)" if stale else "")
    body = ("; ".join(lines) + "." + (f" These are the numbers of the last report, {int(age) // 60} min ago." if stale and age is not None else "")
            + news + evening_extra(e.date().isoformat()))
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
        cands += day_summary(snap, now, st["sent"])
    except Exception:
        pass
    try:                     # the 07:30 ET ZEUS morning brief (tools/morning_brief.py, read-only): once a day, + one Board event
        from tools import morning_brief
        cands += morning_brief.pushes(snap, st["sent"], now)
    except Exception:
        pass
    try:                     # live vs backtest (engine/live_vs_bt.py, read-only): one line a day per drifting bot, after 16:20 ET
        from engine import live_vs_bt
        cands += live_vs_bt.pushes(now, st["sent"])
    except Exception:
        pass
    try:                     # the 01:45 ET "ready for 02:00" push (tools/launch_card.py, read-only): silent when all is well
        from tools import launch_card
        cands += launch_card.ready_push(snap, now)
    except Exception:
        pass
    msgs = []
    for m in cands:
        if m["key"] in st["sent"]:
            continue
        if quiet(now) and m.get("priority") != "high" and not m.get("night"):   # an ordinary push waits for 07:00 ET (not marked sent)
            continue
        st["sent"][m["key"]] = now
        msgs.append(m)
    for k in [k for k, t in st["sent"].items() if now - int(t or 0) > KEEP_S]:
        st["sent"].pop(k, None)
    return st, msgs


def forget(state: dict | None, key: str) -> None:
    """A push that did not go out: drop its key so the next run sends it again."""
    _d(_d(state).get("sent")).pop(key, None)
