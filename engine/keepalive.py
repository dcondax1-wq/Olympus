"""Keep-alive trade for MFFU's 7-day inactivity rule (owner 2026-11-20: "if a account hasn't traded in 7 days it needs a very
small trade to reset counter?"). OFF by default: one switch per account, and only the owner turns one on.
The owner's two ways to turn it on (2026-11-22 night-zerotouch, owner: "make this automatic. I shouldn't need to do anything"):
  * START BOT / the Start page / MONDAY_SETUP.bat: when HE types I ACCEPT LIVE RISK at a START (the phrase that already
    authorizes live orders on these accounts), that same typed phrase also switches the keep-alive ON for exactly the real
    MFFU accounts that START arms (start_consent below; engine/go.step_arm prints one line "Keep-alive ON for: ..."). Sim /
    paper accounts and accounts the START did not arm stay as they are. The phrase is never written: data/keepalive.json
    gets only a consent flag {"consent": {"t", "day", "accounts", "via": "start_phrase"}}, like data/auto_resume.json.
    A START without the phrase ("Start trading" with a valid auto-resume, a resume after a reboot) never changes a switch.
  * KEEPALIVE_ON.bat (he types KEEP ALIVE ON), as before.
  The opt-out sticks: tools/bat/KEEPALIVE_OFF.bat (--off all) or --off <key> also records "owner_off", and a later START phrase does
  NOT turn those back on (the summary says "stays OFF: you turned it off"); only KEEPALIVE_ON.bat / --on clears it.

The rule. MFFU Terms section 7 "Dormant Accounts" (myfundedfutures.com/terms, updated 2026-10-09) and the help center (articles
16596524, 14290805, 17036130, 18337038; all read 2026-11-20): every Evaluation and Sim Funded account needs at least one
EXECUTED trade in every 7 consecutive calendar days, weekends and holidays included. Without one, MFFU may close the account
and count the closure as a breach, and a Sim Funded account also loses ALL its profits. No warning is promised. A filled trade
counts. A login, or an order that never fills, does not. Live accounts have no such rule. MFFU sets no minimum size and no
minimum hold time, and nothing bans a small trade made only to stay active. The one soft rule is Terms 12.4 (consistency in
position sizing, trade frequency and risk exposure): 12.4.1 names "substantially larger position sizes", 12.4.2 "open
substantially smaller or larger numbers of positions than typical", 12.4.3 "inconsistent or erratic trading activity". So
MFFU support is asked in writing before the owner switches one on (research/lit/mffu_rules.json inactivity.terms_12_4).
The keep-alive is an ordinary 1-micro trade: front-month MNQ, the liquid last half hour of RTH, held about 2 minutes, never
inside a Tier-1 news window, never opposite another account, no tight bracket, flat long before the close.

Which days count (account_days()). Only CONFIRMED fills, by their ET calendar date: an entry the broker took (the ledger row's
result ok True: the NinjaTrader adapter says ok only after the fill and its bracket), an adapter leg with filled > 0, an
"Execution=" line for that account in NinjaTrader's own Log (<NinjaTrader 8>/log, the format engine/eval_fix reads: the
bot's fills AND the owner's hand trades, nothing to type), a keep-alive that filled, and the owner's --traded notes. Every
confirmed day is also kept in the state file (acc.<key>.fills, the last FILLS_KEEP), so a restart on a later day (the ledger
of LiveBot / an extra account is restored only on its own day; the adapter keeps no history) forgets none; the saved
ledger's fills are read once at the restart too (LiveBot._restore, multi_account Account.restore: obj._ka_seed). Never a
booked $ day (LiveBot.eval_days), an exit row or a close: those also exist for entries NinjaTrader never took ($0 'not
placed' rows, voided days, a kill with no position). In doubt this counts FEWER days: an extra keep-alive costs about
$2.40, a missed one can cost the account. An account with no fill yet counts from the day before its start (the start
day is day 1); its start = the EARLIEST start of its lanes, moved earlier by an MFFU start override (data/keepalive.json
"start", START_DEFAULTS: the 25K #2 went on the PC Tue 11-17 evening, the Rapid EOD 25K was bought Thu 11-19 evening); a
start in the future is ignored.

When (plan()). D = the account's last traded day (or its start). The cautious deadline is D + 6, because day 7 is read as too
late, as in engine/cme_calendar.idle_plan. The keep-alive acts on the LAST full CME session on or before that deadline
(lead_sessions 1). That is at least one calendar day before MFFU's literal limit (D + 7) and leaves every earlier session for
a real trade. A half day is used only when no full session is left. Once the deadline has passed it acts on the next session
anyway, because a late trade beats none.

Where in the day (window()). A full day: 15:33-15:48 ET. That is after LIT's last entry (15:30) and ATLAS's (12:00), before
the bot's flat time (15:55), before MFFU's 16:10, and before the 15:50 closing imbalance. A CME half day: from 12 to 2 minutes
before the entry cut (the adapters refuse entries from 15 minutes before the halt), e.g. 12:33-12:43 ET for a 13:00 halt;
that window lies inside LIT's entry hours (its cut is 12:45 then), so a LIT entry can come during the hold (before_entry
below closes the keep-alive first). Never 16:10-18:00, never after a half day's halt, never in the Sunday or overnight session.

What (tick()). ONE MNQ market order on that account's own NinjaTrader adapter (the one its strategy already uses, under the
owner's own arming), with a hard OCO stop and target 10 points (40 ticks, $20) away. It is closed at market after hold_s
(120 s, inside the window: an entry is only sent while the whole hold fits before 15:50 ET / a half day's entry cut).
Expected cost: $1.90 commission + 1 tick of spread = about $2.40. Worst case: the stop, 2 ticks of slippage and commission =
$22.90. At most MAX_TRIES attempts a day, and only one keep-alive open on the PC at a time.
Every gate must pass, or nothing is sent (the reason is logged once a day):
  the owner's switch for that account is ON; the bot is not killed; the adapter is enabled and not read-only; the owner's
  stops (guards._owner_blocks: the pause of engine/entry_pause from the phone / dashboard, the presence check-in, ai_watch's
  anomaly pause and combined-loss stop), LIT's own soft daily loss and the combo day stop (guards entry_problems), the remote
  flatten's "no new entries today" (LiveBot._no_entries_day);
  the startup reconcile (guards.startup_problems, AccountB.startup_block), the PC clock guard, each lane's own lock /
  entry block / MFFU lock (lifecycle.block, multi_account Account.entry_block); the account is
  not passed / failed / locked / lost / stuck / locked out today (engine/lifecycle + the strategy's own status); no trade on
  it yet this trading day; inside the window; no Tier-1 release (CPI, jobs, FOMC, minutes) within NEWS_PAD_S around the
  whole hold, on every account (the Rapid funded news ban is +-3 min, so this is stricter); fresh bars and no feed block;
  the account flat: no strategy position or entry in flight on ANY lane of that NinjaTrader account, no open bracket, and
  NinjaTrader shows FLAT; no other account opposite (the keep-alive takes the side an open account already holds, else long;
  two sides or an unknown side = skip); and engine/firms.check passes (contracts, the max-loss floor at the stop, the daily
  loss left, the eval best-day rule, the firm's flat time, hedging across ALL accounts).
Strategies are never disturbed. On a full day LIT (last entry 15:30) and ATLAS (12:00) do not enter in that window; on a
half day LIT can (see above). The keep-alive never writes to a strategy's ledger, so no stats, sizing or audits change. It
only closes its own bracket (by its entry time), never a CLOSEPOSITION on a guess. The kill switch and the adapter's
flat-time safety close it like any trade. Every strategy entry asks before_entry() right before its order goes out
(LiveBot._route, AccountB.route, multi_account Account.route and the hedging guard AccountRouter.opposite_open): a
keep-alive on the SAME NinjaTrader account (any side) or the other way on any account is closed at market first. The real
entry then goes out; only when NinjaTrader has not confirmed that close yet is it refused ("hedging guard: the keep-alive
trade ... is closing"), like any hedge refusal. guards.reconcile_tick / startup_problems count an open keep-alive leg as
expected (never a "Position mismatch" close).

Restart safety. The state file next to the bot's state (data/keepalive_state.json) is written BEFORE the order goes out. After
a restart, the adapter restores its bracket from its own state file and the next tick closes it. A keep-alive that filled
never repeats that day, and an attempt that never filled is retried at most MAX_TRIES times.

Alerts (the private ntfy topic, engine/notify.instant_problem; ids masked). Sent from a background thread, never inside the
live loop's lock; a key is recorded only once ntfy took it, else retried every ALERT_RETRY_S (5 min):
  heads-up the morning of the act day (from 09:30 ET): "Keep-alive today on Zlarior 50K ... about -$2.40, at most -$23"
  the entry ("Keep-alive on Zlarior 50K: BUY 1 MNQ @ ...") and the result ("... closed LONG about -$2.40"), straight to ntfy,
  plus the normal trade alert labelled "Keep-alive on <account>" (engine/push.pc_notify)
  a refusal that leaves no attempt today: "place 1 MNQ by hand before 16:05 ET" (with why: e.g. "your pause blocks it"),
  retried every 5 min until then when ntfy does not take it
  switch OFF (the owner's hand trade): the session before the act day "the next session is the last safe day", then on the
  act day "TODAY is the last safe day: place 1 MNQ by hand", each once.
The 25K #2 and the Rapid get these too (they had no phone warning before). ONE inactivity warning per account and day, from
one place: while the bot runs (the heartbeat's "keepalive" block, cover), engine/ops_checks.inactivity_notice, tools/pc_guard,
tools/morning_brief and account_b's own idle push leave the warning to the keep-alive and count its days (last_day()). The
cover counts only while it is fresh (its "t" at most COVER_FRESH_S old for the reader: hb_covers(block, lane, now), the
board card's cover, ops_checks' fresh heartbeat): with the bot down they warn as before.

Config: data/keepalive.json (gitignored; the start cfg's "keepalive" block in test harnesses; a harness never reads the file)
  {"accounts": {"lit": false, "atlas": false, "x:b25k_2": false, "rapid": false}, "start": {"x:b25k_2": "2026-11-17"}}
  python -X utf8 -m engine.keepalive --status                    switches, last results, the plan
  python -X utf8 -m engine.keepalive --plan 2026-11-16           when a keep-alive would act after a last trade that day
  python -X utf8 -m engine.keepalive --on lit --yes              the OWNER's yes (live orders): Claude never runs it
  python -X utf8 -m engine.keepalive --off lit
  python -X utf8 -m engine.keepalive --on all --yes              every known account at once (KEEPALIVE_ON.bat: the owner
                                                                 types KEEP ALIVE ON); --off all = tools/bat/KEEPALIVE_OFF.bat
  python -X utf8 -m engine.keepalive --skip lit                  no keep-alive on lit today
  python -X utf8 -m engine.keepalive --traded lit [yyyy-mm-dd]   you traded it by hand (default today, the ET date; never a
                                                                 future day or more than 7 days back): prints the new deadline
                                                                 (only needed when NinjaTrader's Log is not where the bot reads)
  python -X utf8 -m engine.keepalive --start x:b25k_2 2026-11-17 the day MFFU's account started (only moves the start earlier;
                                                                 never a future day)
  Every KEY must be a known account: lit, atlas, rapid or x:<id> of data/accounts.json (a typo is refused, not "noted").
Tests: python -X utf8 -m tests.test_keepalive
"""
from __future__ import annotations

import datetime as _dt
import glob
import json
import os
import re
import sys
import threading
import time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "data", "keepalive.json")     # gitignored: the owner's switches
STATE_FILE = "keepalive_state.json"                            # gitignored, next to the bot's state file (data/)
VERSION = 1

LIMIT_DAYS = 7                  # MFFU: one executed trade in every 7 consecutive calendar days (Terms section 7)
LEAD_SESSIONS = 1               # act on the last full CME session on or before the cautious deadline (D + 6)
FULL_WINDOW = (15 * 60 + 33, 15 * 60 + 48)     # 15:33-15:48 ET: after LIT's 15:30 last entry, before the 15:55 flat
HALF_WINDOW = (12, 2)           # a half day: from 12 to 2 minutes before the entry cut (halt - 15 min)
HEADSUP_FROM = 9 * 60 + 30      # the act day's heads-up from 09:30 ET
HOLD_S = 120                    # closed at market after this (an ordinary trade's hold, not an in-and-out; MFFU Terms 12.4)
HOLD_RANGE = (20, 180)
POLL_S = 30                     # the bot polls every 30 s: the close lands up to one poll after hold_s
QTY = 1                         # one micro (MNQ)
STOP_PTS = TARGET_PTS = 10.0    # 40 ticks: a hard OCO stop and target ($20 a micro), never a tight bracket
TICK, PV = 0.25, 2.0            # MNQ: $0.50 a tick, $2 a point
COMM = 1.90                     # $ a micro round trip (engine/sizing.LIVE_COMM)
SLIP_TICKS = 2                  # a stop-out's slippage (engine/firms.SLIP_PTS 0.5 pt)
EXPECTED_COST = round(COMM + TICK * PV, 2)                                   # $2.40: commission + 1 tick of spread
WORST_COST = round(STOP_PTS * PV + SLIP_TICKS * TICK * PV + COMM, 2)         # $22.90: the stop + slippage + commission
NEWS_PAD_S = 10 * 60            # no keep-alive within 10 min of a Tier-1 release (any account)
FRESH_BAR_S = 180               # the last 1m bar must be this fresh
MAX_TRIES = 2                   # attempts a day when an entry did not fill (a refusal, NinjaTrader slow)
RETRY_S = 120
CLOSE_RETRY_S = 30
MIN_ROOM = 100.0                # never on an account with less room than this (the presets' "stuck" line)
PRIORITY = ("lit", "atlas", "rapid")           # one NinjaTrader account = one target: the first lane's key wins
MFFU_PLANS = ("mffu_builder_25k", "mffu_builder_50k", "mffu_rapid_eod_25k", "mffu_rapid_eod_50k")

ALERT_RETRY_S = 300             # an alert ntfy did not take is tried again after this (never more often)
ALERT_FINAL = ("sent", "already sent", "hook", "queued", "problems is off", "not the real bot")   # done: never re-sent
RETRY_MAX_S = 6 * 3600          # a one-shot alert (entry / result) is retried for at most this long
COVER_FRESH_S = 1200            # the keep-alive "covers" an account's inactivity warnings while its tick ran this recently
COVER_EVERY_S = 300
TRADED_BACK_DAYS = 7            # --traded: never a future day, never more than this many days back (a phone typo)
START_PULL_DAYS = 7             # an MFFU start override only moves an account's start EARLIER, by at most this many days
START_DEFAULTS = {"x:b25k_2": "2026-11-17",    # STATE.md 2026-11-17: the 25K #2 went on the PC ~20:30 ET (its bot start: 11-18)
                  "rapid": "2026-11-19"}       # STATE.md 2026-11-19 20:15 ET: the Rapid EOD 25K bought (MFFU may count from then)
ACTIVE = ("sending", "open", "closing")
FILLS_KEEP = 10                 # confirmed fill days kept per account in the state file (they survive a restart)
EXEC_SCAN_S = 120               # NinjaTrader's Log is read for new "Execution=" lines at most this often (bot clock)
EXEC_BACK_DAYS = LIMIT_DAYS + 2  # ... over this many calendar days of log files
EXEC_MAX_BYTES = 64 << 20       # at most this much log read per scan (the rest on the next scans)
HAND_BY = 16 * 60 + 5           # "place 1 MNQ by hand before 16:05 ET" (MFFU's flat 16:10; a half day: 5 min before the halt)

ALERT_HOOK = None               # tests: fn(kind, payload) instead of the phone ("problem" | "trade")
SYNC_ALERTS = False             # tests: deliver in the caller's thread (the hook does too)
_MX = threading.RLock()
_TRIED: dict = {}               # (state path, alert key) -> the bot clock of the last try (the retry throttle)
_LAST_THREAD = None
_EXEC: dict = {}                # NinjaTrader folder -> {"t": last scan, "files": {path: bytes read}, "hits": {Name: {days}}}


# ------------------------------------------------------------------------------------------------ small helpers
def _et(t) -> _dt.datetime:
    return _dt.datetime.fromtimestamp(float(t), ET)


def _mod(t) -> int:
    e = _et(t)
    return e.hour * 60 + e.minute


def _date(x) -> _dt.date:
    return x if isinstance(x, _dt.date) else _dt.date.fromisoformat(str(x)[:10])


def trading_day(t) -> str:
    return (_et(t) + _dt.timedelta(hours=6)).strftime("%Y-%m-%d")


def _cal(t) -> str:
    """The ET calendar date of a moment (MFFU counts calendar days; an evening fill is never moved to the next date)."""
    return _et(t).strftime("%Y-%m-%d")


def _num(x, d=None):
    try:
        v = float(x)
        return d if v != v else v
    except (TypeError, ValueError):
        return d


def _hm(m) -> str:
    return f"{int(m) // 60:02d}:{int(m) % 60:02d}"


def money(x) -> str:
    v = _num(x, 0.0)
    return ("-" if v < 0 else "") + f"${abs(v):,.2f}"


# ------------------------------------------------------------------------------------------------ the calendar (pure)
def window(day):
    """(first, last) ET minute of the keep-alive window on trading date `day` (last exclusive), or None (no session, a full
    CME closure, a weekend)."""
    from . import cme_calendar as CC
    d = _date(day)
    if d.weekday() >= 5 or CC.full_closure(d):
        return None
    ec = CC.early_close(d)
    if ec is None:
        return FULL_WINDOW
    cut = CC.entry_cut(d, 955)
    a, z = cut - HALF_WINDOW[0], cut - HALF_WINDOW[1]
    return (a, z) if 0 < a < z else None


def in_window(now) -> bool:
    """now is inside today's window (the calendar date = the trading date: the window is always in the afternoon)."""
    e = _et(now)
    w = window(e.date())
    if not w or trading_day(now) != e.date().isoformat():
        return False
    from . import cme_calendar as CC
    m = e.hour * 60 + e.minute
    return w[0] <= m < w[1] and not CC.halted(now)


def exit_by(day) -> int | None:
    """ET minute the keep-alive must be flat by on trading date `day`: the window's end + 2 min (15:50 on a full day, before
    the closing imbalance; a half day: its entry cut). None = no window."""
    w = window(day)
    return w[1] + HALF_WINDOW[1] if w else None


def fits(now, hold_s: int = HOLD_S) -> bool:
    """An entry now, closed hold_s later (+ one poll), is flat before exit_by() of today."""
    e = _et(now)
    xb = exit_by(e.date())
    if xb is None:
        return False
    lim = _dt.datetime(e.year, e.month, e.day, xb // 60, xb % 60, tzinfo=ET).timestamp()
    return int(now) + int(hold_s) + POLL_S <= lim


def plan(last_day, now, limit: int = LIMIT_DAYS, lead: int = LEAD_SESSIONS) -> dict:
    """When the keep-alive acts after a last traded day (or the account's start) `last_day`.
    {"last", "today", "idle_days", "deadline" (cautious, D + limit - 1), "hard" (MFFU's literal last day, D + limit),
     "sessions": [days that can still take one, today included while its window is open], "act_day", "due" (act now-ish:
     today is the act day and nothing traded today), "eve" (the act day is the next session), "late" (past the deadline)}."""
    last = _date(last_day)
    t = int(now)
    today = _date(trading_day(t))
    m = _mod(t)
    deadline = last + _dt.timedelta(days=max(1, int(limit)) - 1)
    hard = last + _dt.timedelta(days=max(1, int(limit)))
    idle = (today - last).days

    def open_on(d):
        w = window(d)
        return bool(w) and (d != today or (_et(t).date() == today and m < w[1]))

    sess, d = [], today
    while d <= deadline:
        if open_on(d):
            sess.append(d)
        d += _dt.timedelta(days=1)
    full = [x for x in sess if window(x) == FULL_WINDOW]
    late = not sess
    if full:
        act = full[max(0, len(full) - max(1, int(lead)))]
    elif sess:
        act = sess[0]                                   # only half days left: the first one
    else:                                               # past the deadline: the next session (a late trade beats none)
        act, d = None, today
        for _ in range(14):
            if open_on(d):
                act = d
                break
            d += _dt.timedelta(days=1)
    nxt = None
    d = today + _dt.timedelta(days=1)
    for _ in range(14):
        if window(d):
            nxt = d
            break
        d += _dt.timedelta(days=1)
    return {"last": last.isoformat(), "today": today.isoformat(), "idle_days": idle, "deadline": deadline.isoformat(),
            "hard": hard.isoformat(), "sessions": [x.isoformat() for x in sess], "act_day": act.isoformat() if act else None,
            "due": bool(idle >= 1 and act == today), "eve": bool(idle >= 0 and act is not None and nxt == act and act != today),
            "late": late}


# ------------------------------------------------------------------------------------------------ config / state files
def is_real(bot) -> bool:
    try:
        from .live import STATE_PATH
        return getattr(bot, "state_path", None) == STATE_PATH
    except Exception:
        return False


def _wanted(bot) -> bool:
    """The real bot (its switches + the owner's warnings), or a harness whose cfg has a "keepalive" block. Any other test
    harness: nothing at all (no file, no log line)."""
    return bot is not None and (is_real(bot) or "keepalive" in (getattr(bot, "cfg", None) or {}))


def load_config(bot=None, path: str | None = None) -> dict:
    """{"accounts": {key: bool}, "hold_s", "lead_sessions"}: the start cfg's "keepalive" block (test harnesses), else the
    owner's data/keepalive.json for the real bot; a harness never reads the owner's file. Anything unreadable = all OFF."""
    raw = None
    cfg = getattr(bot, "cfg", None) or {}
    if bot is not None and "keepalive" in cfg:
        raw = cfg.get("keepalive")
    elif path is not None or bot is None or is_real(bot):
        try:
            with open(path or CONFIG_PATH, encoding="utf-8") as fh:
                raw = json.load(fh)
        except Exception:
            raw = None
    raw = raw if isinstance(raw, dict) else {}
    acc = raw.get("accounts") if isinstance(raw.get("accounts"), dict) else {}
    hold = _num(raw.get("hold_s"), HOLD_S)
    lead = _num(raw.get("lead_sessions"), LEAD_SESSIONS)
    start = {}
    for k, v in (raw.get("start") or {}).items() if isinstance(raw.get("start"), dict) else []:
        try:
            start[str(k)] = _date(v).isoformat()
        except Exception:
            continue
    return {"accounts": {str(k): v is True for k, v in acc.items()},
            "hold_s": int(min(HOLD_RANGE[1], max(HOLD_RANGE[0], hold))), "lead_sessions": int(min(3, max(1, lead))),
            "skip": {str(k): str(v) for k, v in (raw.get("skip") or {}).items()} if isinstance(raw.get("skip"), dict) else {},
            "start": start,
            "owner_off": {str(k): str(v) for k, v in (raw.get("owner_off") or {}).items()} if isinstance(raw.get("owner_off"), dict) else {},
            "consent": raw.get("consent") if isinstance(raw.get("consent"), dict) else None}


def save_config(c: dict, path: str | None = None) -> str:
    p = path or CONFIG_PATH
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"accounts": c.get("accounts") or {}, **({"skip": c["skip"]} if c.get("skip") else {}),
                   **({"start": c["start"]} if c.get("start") else {}),
                   **({"owner_off": c["owner_off"]} if c.get("owner_off") else {}),
                   **({"consent": c["consent"]} if c.get("consent") else {})}, fh, indent=1)
    from . import fsutil as _fsutil
    _fsutil.replace(tmp, p)
    return p


def state_path_for(bot=None) -> str:
    sp = getattr(bot, "state_path", None) or os.path.join(ROOT, "data", "live_state.json")
    return os.path.join(os.path.dirname(os.path.abspath(sp)), STATE_FILE)


def load_state(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            st = json.load(fh)
        if isinstance(st, dict) and isinstance(st.get("acc"), dict):
            st.setdefault("sent", [])
            st.setdefault("notes", {})
            st.setdefault("log", [])
            st.setdefault("retry", [])
            return st
    except Exception:
        pass
    return {"v": VERSION, "acc": {}, "sent": [], "notes": {}, "log": [], "retry": []}


def save_state(st: dict, path: str):
    with _MX:
        st["v"] = VERSION
        st["sent"] = list(st.get("sent") or [])[-200:]
        st["log"] = list(st.get("log") or [])[-60:]
        st["retry"] = list(st.get("retry") or [])[-10:]
        st["notes"] = {k: v for k, v in (st.get("notes") or {}).items() if str(v)[:10] >= _cut_day()}
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(st, fh, indent=1)
        from . import fsutil as _fsutil
        _fsutil.replace(tmp, path)


def _cut_day() -> str:
    return (_dt.date.today() - _dt.timedelta(days=10)).isoformat()


def _mtime(p):
    try:
        return os.stat(p).st_mtime_ns
    except OSError:
        return None


def _book(bot) -> dict:
    """The bot's keep-alive book (cached on the bot; re-read when the file changed outside the bot, e.g. --traded)."""
    b = getattr(bot, "_ka_book", None)
    p = state_path_for(bot)
    if not isinstance(b, dict) or b.get("_path") != p or b.get("_mt") != _mtime(p):
        b = {"_path": p, "st": load_state(p), "_mt": _mtime(p)}
        try:
            bot._ka_book = b
        except Exception:
            pass
    return b


def _save_book(bot, b):
    """Write the bot's book. When the file changed since the bot read it (the owner's --traded from a command window while a
    tick ran), its hand-trade notes are merged in first, so the bot's save never drops them."""
    with _MX:
        if _mtime(b["_path"]) != b.get("_mt"):
            try:
                disk = load_state(b["_path"])
                for k, a in (disk.get("acc") or {}).items():
                    m = (a or {}).get("marked") if isinstance(a, dict) else None
                    if m:
                        cur = b["st"].setdefault("acc", {}).setdefault(k, {})
                        cur["marked"] = max(str(cur.get("marked") or ""), str(m))
            except Exception:
                pass
        save_state(b["st"], b["_path"])
        b["_mt"] = _mtime(b["_path"])


_LAST: dict = {}


def _file_state(bot=None, path: str | None = None) -> dict:
    """The keep-alive state file, cached by mtime (read without the live loop's lock: the file is replaced atomically)."""
    p = path or state_path_for(bot)
    mt = _mtime(p)
    if mt is None:
        return {}
    c = _LAST.get(p)
    if c is None or c[0] != mt:
        c = (mt, load_state(p))
        _LAST[p] = c
    return c[1]


def last_day(bot, key: str, path: str | None = None) -> str | None:
    """The newest day account `key` had a CONFIRMED fill the keep-alive knows of: a keep-alive that filled, a hand trade
    seen in NinjaTrader's Log or noted (--traded), a strategy fill it kept (acc.<key>.fills), else None. The idle counters
    (engine/account_b.idle_days, ops_checks, the board's quiet days via the heartbeat) add it so their warnings stop after a
    keep-alive / a hand trade. bot None = the PC's own data/ folder. Never raises."""
    try:
        a = (_file_state(bot, path).get("acc") or {}).get(key) or {}
        ds = [str(d)[:10] for d in [a.get("last"), a.get("marked")] + list(a.get("fills") or []) if d]
        return max(ds) if ds else None
    except Exception:
        return None


def covered(key: str, now=None, bot=None, path: str | None = None) -> bool:
    """True while the bot's keep-alive sends account `key`'s inactivity warnings itself (its tick ran in the last
    COVER_FRESH_S and `key` is an MFFU account it watches): the other warners (ops_checks, pc_guard, the morning brief,
    account_b's idle push) then stay quiet, so the phone gets ONE warning per account and day. Never raises."""
    try:
        cv = _file_state(bot, path).get("cover") or {}
        now = float(time.time() if now is None else now)
        return key in (cv.get("keys") or []) and abs(now - float(cv.get("t") or 0)) <= COVER_FRESH_S
    except Exception:
        return False


def hb_block(bot) -> dict | None:
    """The heartbeat's "keepalive" block (engine/heartbeat; tiny, no names / ids beyond the engine keys): {"t", "on": {key:
    bool}, "last": {key: keep-alive fill / hand-trade day}, "cover": [keys whose warnings the keep-alive sends],
    "lane": {"lit" | "atlas" | "rapid": the key of the account that lane trades}}. None when there is nothing to say (the
    payload stays as before on a paper bot). Never raises."""
    try:
        if not _wanted(bot):
            return None
        st = _file_state(bot)
        acc = st.get("acc") or {}
        last = {k: v for k, v in ((k, last_day(bot, k)) for k in acc) if v}
        cv = st.get("cover") or {}
        clk = getattr(bot, "clock", None)
        now = float(clk() if callable(clk) else time.time())
        fresh = abs(now - float(cv.get("t") or 0)) <= COVER_FRESH_S
        lane = {}
        for g in targets(bot):
            for ln in g["lanes"]:
                if ln["key"] in ("lit", "atlas", "rapid"):
                    lane.setdefault(ln["key"], g["key"])
        C = load_config(bot)
        on = {k: True for k, v in C["accounts"].items() if v}
        if not (last or lane or on):
            return None
        return {"t": int(cv.get("t") or 0), "on": on, "last": last, "cover": list(cv.get("keys") or []) if fresh else [],
                "lane": lane}
    except Exception:
        return None


def hb_last(block, lane: str) -> str | None:
    """The keep-alive / hand-trade day the heartbeat block holds for the account a lane ("lit", "atlas") trades."""
    try:
        b = block if isinstance(block, dict) else {}
        return (b.get("last") or {}).get((b.get("lane") or {}).get(lane, lane))
    except Exception:
        return None


def cover_fresh(t, now=None) -> bool:
    """A cover stamped at `t` still holds at `now` (at most COVER_FRESH_S old). A dead bot's last heartbeat keeps its block
    for days: its cover must not keep the other warners quiet then."""
    try:
        t = float(t or 0)
        now = time.time() if now is None else float(now)
        return t > 0 and abs(now - t) <= COVER_FRESH_S
    except Exception:
        return False


def hb_covers(block, lane: str, now=None) -> bool:
    """The heartbeat block says the bot's keep-alive sends the warnings of the account `lane` trades, and that block is
    fresh at `now` (default: the wall clock). A stale block (the bot down) never covers. Never raises."""
    try:
        b = block if isinstance(block, dict) else {}
        return (b.get("lane") or {}).get(lane, lane) in (b.get("cover") or []) and cover_fresh(b.get("t"), now)
    except Exception:
        return False


# ------------------------------------------------------------------------------------------------ the accounts (targets)
_SIM_ACCT = re.compile(r"^(sim\d*|playback\d*|backtest)$", re.I)


def _ok_entry(r) -> bool:
    """A REAL broker entry: ok True from a live adapter on a real account. Red-team 2026-11-21: a paper lane's or a Sim101 test's
    'ok' rows in the same ledger counted as MFFU fills, so the keep-alive skipped its day and every 7-day warning went quiet."""
    if not (isinstance(r, dict) and r.get("side") in ("buy", "sell")):
        return False
    res = r.get("result") if isinstance(r.get("result"), dict) else {}
    if res.get("ok") is not True or str(res.get("adapter") or "").lower() in ("paper", "webhook", "lab"):
        return False
    return not _SIM_ACCT.match(str(res.get("account") or "").strip())


def _fill_days(rows, account=None) -> set:
    """ET calendar dates of the entries the broker took (ledger rows with result ok True, a live adapter, a real account; with
    account given, rows that name another NinjaTrader account are left out)."""
    out = set()
    acct = str(account or "").strip().lower()
    for r in rows or []:
        try:
            ra = str(((r.get("result") or {}).get("account")) or "").strip().lower()
            if _ok_entry(r) and r.get("t") and not (acct and ra and ra != acct):
                out.add(_cal(int(r["t"])))
        except Exception:
            continue
    return out


def seed_days(rows) -> set:
    """The confirmed fill days of a SAVED ledger, read at a restart before the bot drops an earlier day's ledger
    (engine/live.LiveBot._restore, engine/multi_account.Account.restore keep them as obj._ka_seed). Never raises."""
    try:
        return _fill_days(rows if isinstance(rows, list) else [])
    except Exception:
        return set()


def _lane_days(kind, obj, bot, account=None) -> set:
    """ET calendar days with a CONFIRMED fill on one lane: the entries the broker took (the ledger's buy / sell rows with
    result ok True; the NinjaTrader adapter answers ok only once the entry filled and its bracket is in), plus those of the
    ledger saved before a restart (obj._ka_seed). Never a booked $ day (LiveBot.eval_days), an exit row or a close: those
    also exist for entries NinjaTrader never took ($0 'not placed' exits, days voided as refused, a kill with no position)
    and would move the deadline past MFFU's."""
    try:
        o = bot if kind == "lit" else obj
        seed = getattr(o, "_ka_seed", None)
        return _fill_days(getattr(o, "ledger", None), account) | {str(d)[:10] for d in (seed or ()) if d}
    except Exception:
        return set()


def _exec_line(line: str):
    """(NinjaTrader account Name, ET calendar day) of one NinjaTrader Log line with an "Execution=" (a fill), else None.
    The line starts with the PC's local time ("2026-10-28 04:01:27:342|1|8|Execution='...' Instrument='MNQ 12-26'
    Account='...' Price=... Time='10/28/2026 4:01:27 AM' ..."). The day = the earliest of the log line's local date, its ET
    date and the execution's own Time= (when NinjaTrader writes one and it reads as a date up to 3 days before the line: an
    execution logged again at a reconnect after midnight keeps its own day). Never a later day than the fill's."""
    i = line.find("Account='")
    if i < 0 or "Execution=" not in line:
        return None
    j = line.find("'", i + 9)
    if j <= i + 9:
        return None
    try:
        loc = _dt.datetime.strptime(line[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    day = loc.date().isoformat()
    try:
        day = min(day, _cal(time.mktime(loc.timetuple())))
    except Exception:
        pass
    k = line.find("Time='")
    if k >= 0:
        raw = line[k + 6:line.find("'", k + 6)].strip()
        for fmt in ("%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%d.%m.%Y %H:%M:%S"):
            try:
                x = _dt.datetime.strptime(raw, fmt).date()
            except ValueError:
                continue
            if 0 <= (loc.date() - x).days <= 3:
                day = min(day, x.isoformat())
                break
    return line[i + 9:j], day


def nt_exec_days(folder, account, now=None) -> set:
    """ET calendar days with a fill on NinjaTrader account `account` in NinjaTrader's own Log (<folder>/log/
    log.YYYYMMDD.*.txt): the bot's fills AND the owner's hand trades, on disk across restarts. The last EXEC_BACK_DAYS of
    files, read incrementally (only new bytes), at most every EXEC_SCAN_S of the bot clock and EXEC_MAX_BYTES a scan.
    Read-only; never raises (no folder / no log = nothing)."""
    try:
        if not folder or not account:
            return set()
        now = float(time.time() if now is None else now)
        c = _EXEC.setdefault(os.path.abspath(str(folder)), {"t": None, "files": {}, "hits": {}})
        if c["t"] is None or now - c["t"] >= EXEC_SCAN_S or now < c["t"]:
            c["t"] = now
            _exec_scan(os.path.join(str(folder), "log"), c, now)
        return set(c["hits"].get(str(account)) or ())
    except Exception:
        return set()


def _exec_scan(logd, c, now):
    cut = (_et(now).date() - _dt.timedelta(days=EXEC_BACK_DAYS)).strftime("%Y%m%d")
    names = []
    for p in glob.glob(os.path.join(logd, "log.*.txt")):
        parts = os.path.basename(p).split(".")
        if len(parts) >= 3 and parts[1].isdigit() and len(parts[1]) == 8 and parts[1] >= cut:
            names.append(p)
    budget = EXEC_MAX_BYTES
    for p in sorted(names):
        try:
            size = os.path.getsize(p)
        except OSError:
            continue
        off = int(c["files"].get(p) or 0)
        if size < off:
            off = 0                                      # a new file under the same name: read it again
        if size == off or budget <= 0:
            c["files"][p] = off
            continue
        try:                                             # (NinjaTrader keeps today's file open: shared read)
            with open(p, "rb") as fh:
                fh.seek(off)
                raw = fh.read(min(size - off, budget))
        except OSError:
            continue
        k = raw.rfind(b"\n")
        if k < 0:
            c["files"][p] = off                          # no whole line yet
            continue
        raw = raw[:k + 1]
        c["files"][p] = off + len(raw)
        budget -= len(raw)
        if b"Execution=" not in raw:
            continue
        for ln in raw.decode("utf-8", "replace").splitlines():
            if "Execution=" in ln:
                x = _exec_line(ln)
                if x:
                    c["hits"].setdefault(x[0], set()).add(x[1])
    old = (_et(now).date() - _dt.timedelta(days=EXEC_BACK_DAYS + 2)).isoformat()
    c["hits"] = {a: {d for d in ds if d >= old} for a, ds in c["hits"].items()}
    c["files"] = {p: v for p, v in c["files"].items() if p in names}


def _adapter_days(ad) -> set:
    """ET calendar days of the adapter's legs NinjaTrader reported a fill for (open and the last closed ones)."""
    out = set()
    for lg in list(getattr(ad, "history", None) or []) + list(getattr(ad, "legs", None) or []):
        try:
            if isinstance(lg, dict) and int(lg.get("filled") or 0) > 0 and (lg.get("sent_at") or lg.get("entry_t")):
                out.add(_cal(int(lg.get("sent_at") or lg["entry_t"])))
        except Exception:
            continue
    return out


def _lane_start(kind, obj, bot) -> str | None:
    try:
        if kind == "lit":
            return bot.eval_start() or None
        if hasattr(obj, "start_day"):
            return obj.start_day() or None
        f = (getattr(obj, "spec", None) or {}).get("funded") or {}
        funded = callable(getattr(obj, "funded", None)) and obj.funded()
        return str((f.get("start") if funded else (obj.spec or {}).get("eval_start")) or "") or None
    except Exception:
        return None


def _lane_open(kind, obj, bot):
    """(busy, dir or None, why) for one lane: a strategy position, an entry in flight."""
    try:
        if kind == "lit":
            st = getattr(bot, "state", None) or {}
            pos, en = st.get("position"), st.get("enter_now")
            if pos:
                return True, (1 if pos.get("dir", 1) == 1 else -1), "LIT holds a position"
            if en:
                return True, (1 if en.get("dir", 1) == 1 else -1), "LIT is entering"
            ot = getattr(bot, "_open_routed", None)
            if ot is not None:
                e = next((r for r in reversed(getattr(bot, "ledger", None) or []) if r.get("side") in ("buy", "sell")
                          and r.get("entry_t") == ot), None)
                return True, ((1 if e["side"] == "buy" else -1) if e else None), "a routed position is open"
            return False, None, None
        ot = getattr(obj, "open_t", None)
        if ot is None:
            return False, None, None
        pv = (getattr(obj, "prov", None) or {}).get(int(ot)) if isinstance(getattr(obj, "prov", None), dict) else None
        if pv and pv.get("dir") in (1, -1):
            return True, int(pv["dir"]), "a position is open"
        e = next((r for r in reversed(getattr(obj, "ledger", None) or []) if r.get("side") in ("buy", "sell")
                  and r.get("entry_t") == ot), None)
        return True, ((1 if e["side"] == "buy" else -1) if e else None), "a position is open"
    except Exception as e:  # noqa: BLE001
        return True, None, f"state unreadable ({e.__class__.__name__})"


def _adapter_open(ad):
    """(busy, dir or None, why) at the broker: an open bracket of ours, or NinjaTrader's position file not FLAT."""
    try:
        from .ninjatrader import OPEN_STATUSES
        for lg in list(getattr(ad, "legs", None) or []):
            if isinstance(lg, dict) and lg.get("status") in OPEN_STATUSES:
                return True, int(lg.get("dir") or 0) or None, f"a bracket is {lg.get('status')}"
        if callable(getattr(ad, "positions", None)):
            for p in (ad.positions() or {}).get("positions") or []:
                if p.get("side") in ("LONG", "SHORT"):
                    return True, (1 if p["side"] == "LONG" else -1), f"NinjaTrader shows {p['side']} {p.get('qty')}"
        return False, None, None
    except Exception as e:  # noqa: BLE001
        return True, None, f"broker state unreadable ({e.__class__.__name__})"


def lanes(bot) -> list:
    """Every routed lane on the bot: {"key", "kind", "obj", "adapter", "nt", "trade"} (trade = an MFFU target candidate)."""
    out = []
    cfg = getattr(bot, "cfg", None) or {}
    ad = getattr(bot, "adapter", None)
    if ad is not None and str((getattr(bot, "state", None) or {}).get("model") or cfg.get("model") or "lit") == "lit":
        out.append({"key": "lit", "kind": "lit", "obj": bot, "adapter": ad, "trade": True,
                    "nt": str(cfg.get("nt_account") or getattr(ad, "account", "") or "") or None})
    for attr, key in (("acct_b", "atlas"), ("acct_r", "rapid")):
        o = getattr(bot, attr, None)
        if o is not None and not getattr(o, "problem", None):
            out.append({"key": key, "kind": "acct", "obj": o, "adapter": getattr(o, "adapter", None), "trade": True,
                        "nt": str(getattr(o, "name", "") or "") or None})
    for a in list(getattr(getattr(bot, "accts", None), "accounts", None) or []):
        if getattr(a, "problem", None):
            continue
        sp = getattr(a, "spec", None) or {}
        key = "rapid" if sp.get("lane") == "rapid" else f"x:{getattr(a, 'id', None) or sp.get('id')}"
        out.append({"key": key, "kind": "extra", "obj": a, "adapter": getattr(a, "adapter", None), "trade": True,
                    "nt": str(sp.get("nt_account") or "") or None if sp.get("adapter") == "ninjatrader" else None})
    c = getattr(bot, "acct_c", None)                    # BLITZ (paper / hidden): never a target, its side still counts
    if c is not None:
        out.append({"key": "blitz", "kind": "acct", "obj": c, "adapter": getattr(c, "adapter", None), "trade": False,
                    "nt": str(getattr(c, "name", "") or "") or None})
    fl = getattr(bot, "fleet", None)
    for i, f in enumerate(list(getattr(fl, "followers", None) or [])):
        out.append({"key": f"fleet:{i}", "kind": "fleet", "obj": f, "adapter": getattr(f, "adapter", None), "trade": False,
                    "nt": str(((getattr(f, "spec", None) or {}).get("nt_account")) or "") or None})
    return out


def targets(bot) -> list:
    """One target per NinjaTrader account: {"key", "label", "adapter", "lanes", "nt"}. Lanes on the same account (the Rapid's
    LIT + ATLAS lanes, ATLAS + LIT's lit25 lane) are one target; the key goes by PRIORITY, else the first lane's."""
    groups = []
    for ln in lanes(bot):
        if not ln["trade"] or ln["adapter"] is None or getattr(ln["adapter"], "name", None) != "ninjatrader":
            continue                                   # paper: no MFFU account behind it
        g = next((g for g in groups if (ln["nt"] and g["nt"] == ln["nt"]) or g["key"] == ln["key"]), None)
        if g is None:
            groups.append({"key": ln["key"], "nt": ln["nt"], "lanes": [ln]})
        else:
            g["lanes"].append(ln)
            if ln["key"] in PRIORITY and (g["key"] not in PRIORITY or PRIORITY.index(ln["key"]) < PRIORITY.index(g["key"])):
                g["key"] = ln["key"]
    from . import lifecycle as LC
    for g in groups:
        main = next((ln for ln in g["lanes"] if ln["key"] == g["key"] and ln["kind"] != "acct"), None) \
            or next((ln for ln in g["lanes"] if ln["key"] == g["key"]), g["lanes"][0])
        g["adapter"] = main["adapter"]
        g["main"] = main
        try:
            g["label"] = LC.label_of(g["key"], None if g["key"] == "lit" else main["obj"])
        except Exception:
            g["label"] = g["key"]
    return groups


def _plan_id(g) -> str | None:
    """engine/firms plan id of the target (None = not an MFFU account: the keep-alive is for MFFU's rule only)."""
    key, obj = g["key"], g["main"]["obj"]
    sp = getattr(obj, "spec", None) or {}
    if key == "lit":
        cfg = getattr(obj, "cfg", None) or {}
        return "mffu_builder_25k" if "25" in str(cfg.get("plan") or cfg.get("preset") or "") else "mffu_builder_50k"
    if key == "rapid":
        pre = str(sp.get("preset") or sp.get("plan") or "")
        for ln in g["lanes"]:
            pre = pre or str(((getattr(ln["obj"], "spec", None) or {}).get("preset")) or "")
        return "mffu_rapid_eod_25k" if "25k" in pre.lower() else "mffu_rapid_eod_50k"
    if key == "atlas":
        return "mffu_builder_50k" if "50k" in str(sp.get("plan") or "").lower() else "mffu_builder_25k"
    pre = str(sp.get("preset") or "")
    return pre if pre in MFFU_PLANS else None


def _funded(g) -> bool:
    for ln in g["lanes"]:
        o = ln["obj"]
        try:
            if ln["kind"] == "extra" and getattr(o, "mode", None) == "funded":
                return True
            if ln["kind"] == "acct" and callable(getattr(o, "funded", None)) and o.funded():
                return True
        except Exception:
            continue
    if g["key"] == "lit":
        try:
            from . import lifecycle as LC
            b = LC.book_for(g["main"]["obj"], create=False)
            return bool(b) and b.stage("lit") in ("funded", "payout_ready")
        except Exception:
            return False
    return False


def _start_override(C, key, start, now=None):
    """The account's MFFU start when it is earlier than the bot's (an evening purchase, a lane switched on later): the owner's
    data/keepalive.json "start" (--start), else START_DEFAULTS. Only ever moves the start EARLIER, by at most
    START_PULL_DAYS (a stale override can not pull a new account's clock back weeks); never a start after today (ET, `now`;
    a future one would drop every earlier fill and push the warnings into the future)."""
    v = ((C or {}).get("start") or {}).get(key) or START_DEFAULTS.get(key)
    try:
        v = _date(v).isoformat() if v else None
    except Exception:
        return start
    if not v or (now is not None and v > _cal(now)):
        return start
    if not start:
        return v
    if v < start and (_date(start) - _date(v)).days <= START_PULL_DAYS:
        return v
    return start


def _bot_now(bot, now=None) -> float:
    if now is not None:
        return float(now)
    try:
        clk = getattr(bot, "clock", None)
        return float(clk() if callable(clk) else time.time())
    except Exception:
        return time.time()


def _exact_days(bot, g, now=None) -> set:
    """Every CONFIRMED fill day the bot can see now on a target: the lanes' ledgers (+ the restart seed), the adapters'
    filled legs, NinjaTrader's Log for the account's Name (hand trades too). These are kept (acc.<key>.fills)."""
    days, seen = set(), set()
    for ln in g["lanes"]:
        days |= _lane_days(ln["kind"], ln["obj"], bot, ln["nt"] or getattr(ln["adapter"], "account", None))
        days |= _adapter_days(ln["adapter"])
        ad = ln["adapter"]
        k = (getattr(ad, "folder", None), ln["nt"] or getattr(ad, "account", None))
        if k[0] and k[1] and k not in seen:
            seen.add(k)
            days |= nt_exec_days(k[0], k[1], _bot_now(bot, now))
    return days


def account_days(bot, g, C=None, now=None) -> tuple:
    """(confirmed fill days set, start day) of a target: _exact_days + the days the state file kept (acc.<key>.fills: they
    outlive a restart) + its keep-alive fills and hand-trade notes, from its start. start = the EARLIEST lane start (a lane
    switched on later, e.g. the Rapid's LIT lane or lit25, never hides an earlier trade on the account), moved earlier by an
    MFFU start override. g["_exact"] = the confirmed days seen now (_plan_all keeps them)."""
    now = _bot_now(bot, now)
    days = _exact_days(bot, g, now)
    try:
        g["_exact"] = set(days)
    except Exception:
        pass
    starts = []
    for ln in g["lanes"]:
        s = _lane_start(ln["kind"], ln["obj"], bot)
        if s:
            starts.append(str(s)[:10])
    start = min(starts) if starts else None
    start = _start_override(C if C is not None else load_config(bot), g["key"], start, now)
    a = (_book(bot)["st"].get("acc") or {}).get(g["key"]) or {}
    days |= {str(d)[:10] for d in [a.get("last"), a.get("marked")] + list(a.get("fills") or []) if d}
    return ({d for d in days if not start or d >= start}, start)


def _remember(st, key, days) -> bool:
    """Keep a target's confirmed fill days in the state file (the newest FILLS_KEEP): a restart on a later day forgets the
    in-memory ledgers, never these. True = changed."""
    ds = {str(d)[:10] for d in (days or ()) if d}
    if not ds:
        return False
    a = st.setdefault("acc", {}).setdefault(key, {})
    old = [str(d)[:10] for d in (a.get("fills") or [])]
    new = sorted(set(old) | ds)[-FILLS_KEEP:]
    if new == old:
        return False
    a["fills"] = new
    return True


def last_of(days, start) -> tuple:
    """(last traded day, never): the newest confirmed fill day; an account with none counts from the day BEFORE its start
    (the start day is day 1 of MFFU's 7, so the bot acts / warns one day earlier than counting from the start)."""
    if days:
        return max(days), False
    if start:
        return (_date(start) - _dt.timedelta(days=1)).isoformat(), True
    return None, True


def last_known(bot, g, C=None) -> tuple:
    """(last traded day, start, never) of a target (account_days + last_of)."""
    days, start = account_days(bot, g, C)
    last, never = last_of(days, start)
    return last, start, never


def key_for(bot, obj) -> str | None:
    """The keep-alive key of the account a lane object trades (its target's key: one key per NinjaTrader account), else the
    lane's own key ("atlas" for LiveBot.acct_b, "rapid" for acct_r, x:<id> for an extra account), else None. Never raises."""
    try:
        for g in targets(bot):
            if any(ln["obj"] is obj for ln in g["lanes"]):
                return g["key"]
        for ln in lanes(bot):
            if ln["obj"] is obj:
                return ln["key"]
    except Exception:
        pass
    return None


def _stood_down(bot, g, now) -> str | None:
    """Why the account takes no trade at all now (passed / failed / locked / lost / stuck / locked out today), else None."""
    try:
        from . import lifecycle as LC
        if LC.is_stood_down(bot, g["key"]):
            b = LC.book_for(bot, create=False)
            return f"MFFU stage {b.stage(g['key']) if b else 'stood down'}"
    except Exception:
        pass
    today = trading_day(now)
    for ln in g["lanes"]:
        o = ln["obj"]
        try:
            if ln["kind"] == "lit":
                s = ((getattr(bot, "state", None) or {}).get("eval_life") or {}).get("status")
                if s in ("passed", "failed"):
                    return f"eval {s}"
            elif ln["kind"] == "acct":
                from . import account_b as AB
                s = (o.eval_view(now) or {}).get("status")
                if s in AB.STOP_STATUSES:
                    return f"account {s}"
            elif ln["kind"] == "extra":
                lk = getattr(o, "lock", None)
                if lk and lk.get("day") == today:
                    return f"locked out today: {lk.get('reason')}"
        except Exception as e:  # noqa: BLE001
            return f"status unreadable ({e.__class__.__name__})"
    return None


def _facts(bot, g, now) -> dict | None:
    """{"start", "balance", "floor", "day_pnl"} the firm's way, from engine/lifecycle's facts (None = unknown: no trade)."""
    from . import lifecycle as LC
    key, obj = g["key"], g["main"]["obj"]
    today = trading_day(now)
    try:
        if key == "lit":
            f = LC.lit_facts(bot, now)
            day = float((bot.eval_days() or {}).get(today) or 0.0)
        elif key == "atlas":
            f = LC.atlas_facts(obj, now)
            day = LC._today_pnl(obj, today)
        elif key == "rapid":
            ra = getattr(bot, "acct_r", None)
            lane = next((ln["obj"] for ln in g["lanes"] if ln["kind"] == "extra"), None)
            f = LC.rapid_facts(ra, lane, now)
            day = LC._today_pnl(ra if ra is not None else lane, today)
        else:
            f = LC.extra_facts(obj, now)
            day = LC._today_pnl(obj, today)
    except Exception:
        return None
    if not f or f.get("balance") is None or f.get("floor") is None:
        return None
    return {"start": float(f.get("start") or 0.0), "balance": float(f["balance"]), "floor": float(f["floor"]), "day_pnl": float(day)}


def _price(bot, px=None, bar_t=None):
    """(price, bar time): the poll's last 1m close, else the last bar the bot kept."""
    if px is not None:
        return float(px), int(bar_t or 0)
    try:
        b = (getattr(bot, "bars_tail", None) or [])[-1]
        return float(b["close"]), int(b["time"])
    except Exception:
        return None, 0


def _releases(now) -> list:
    try:
        from .multi_account import tier1_releases
        return list(tier1_releases(trading_day(now)))
    except Exception:
        return []


def news_block(now, hold_s: int = HOLD_S, releases=None) -> str | None:
    """A Tier-1 release within NEWS_PAD_S of the whole hold (entry .. exit + a minute)."""
    for r in (_releases(now) if releases is None else releases):
        if r - NEWS_PAD_S <= now + hold_s + 60 and now < r + NEWS_PAD_S:
            return f"Tier-1 release at {_et(r):%H:%M} ET"
    return None


def _others_side(bot, g):
    """(dirs of every OTHER lane / account holding or entering, why when one is unknown) for the no-hedge rule."""
    dirs, unknown = set(), None
    mine = {id(ln["obj"]) for ln in g["lanes"]}
    mine_ad = {id(ln["adapter"]) for ln in g["lanes"]}
    for ln in lanes(bot):
        if id(ln["obj"]) in mine:
            continue
        if g["nt"] and ln["nt"] == g["nt"]:
            continue
        busy, d, why = _lane_open(ln["kind"], ln["obj"], bot)
        if busy:
            if d in (1, -1):
                dirs.add(d)
            else:
                unknown = f"{ln['key']}: {why}"
        if ln["adapter"] is not None and id(ln["adapter"]) not in mine_ad:
            busy, d, why = _adapter_open(ln["adapter"])
            if busy:
                if d in (1, -1):
                    dirs.add(d)
                else:
                    unknown = f"{ln['key']}: {why}"
    return dirs, unknown


def _who_nt(who, bot) -> str | None:
    """The NinjaTrader account Name a lane object trades (the bot itself: its cfg nt_account)."""
    try:
        if who is bot:
            return str((getattr(bot, "cfg", None) or {}).get("nt_account") or getattr(getattr(bot, "adapter", None), "account", "")
                       or "") or None
        sp = getattr(who, "spec", None) or {}
        return str(sp.get("nt_account") or getattr(who, "name", "") or "") or None
    except Exception:
        return None


def _holds(g, who, bot) -> bool:
    """`who` (the lane about to enter) trades the target's NinjaTrader account."""
    if who is None:
        return False
    if who is bot and any(ln["kind"] == "lit" for ln in g["lanes"]):
        return True
    if any(ln["obj"] is who for ln in g["lanes"]):
        return True
    nt = _who_nt(who, bot)
    return bool(nt and g.get("nt") and nt == g["nt"])


def before_entry(bot, d: int, who=None) -> str | None:
    """Every strategy entry asks this right before its order goes out (LiveBot._route, AccountB.route, multi_account
    Account.route; the hedging guard AccountRouter.opposite_open too). An open keep-alive is closed at market first when it
    sits on the SAME NinjaTrader account as the entry (any side: one position per account, the adapter would refuse the
    entry and the real trade would be lost) or holds the OTHER side on any account (no hedging). `who` = the entering lane's
    object (the bot itself for its own account); None or unknown = only the no-hedge rule. None = go ahead (nothing open, or
    it closed and NinjaTrader shows it flat), else why the entry must wait (the close is not confirmed yet)."""
    if not _wanted(bot):
        return None
    try:                                                 # the fast path (nothing open) never waits for the keep-alive's lock
        b0 = getattr(bot, "_ka_book", None)              # (the bot's own book, else the file: written before every order)
        st0 = b0["st"] if isinstance(b0, dict) and b0.get("_path") == state_path_for(bot) else _file_state(bot)
        if not any(a.get("phase") in ACTIVE for a in (st0.get("acc") or {}).values()):
            return None
    except Exception:
        return None
    try:
        with _MX:
            b = _book(bot)
            T = None
            for key, a in (b["st"].get("acc") or {}).items():
                if a.get("phase") not in ACTIVE:
                    continue
                T = targets(bot) if T is None else T
                g = next((x for x in T if x["key"] == key), None)
                same = g is not None and _holds(g, who, bot)
                if not (same or int(a.get("dir") or 0) == -int(d)):
                    continue
                ad = g["adapter"] if g else None
                if ad is None or _leg_of(ad, int(a["entry_t"])) is None:
                    continue                             # its bracket is gone: flat (the next tick books it)
                res = _send(ad, {"sym": (getattr(bot, "cfg", None) or {}).get("sym", "NQ"), "side": "exit", "qty": QTY,
                                 "reason": "KEEP-ALIVE", "entry_t": int(a["entry_t"])})
                a.update(phase="closing", close_at=int(getattr(bot, "clock", time.time)()), closes=int(a.get("closes") or 0) + 1,
                         yielded=True)
                _save_book(bot, b)
                why = "a strategy entry on the same account" if same else "a strategy entry the other way"
                _log(bot, "order", f"{key}: keep-alive closed for {why} ({'ok' if res.get('ok') else res.get('error')})")
                if not res.get("ok") or _leg_of(ad, int(a["entry_t"])) is not None:
                    return f"hedging guard: the keep-alive trade on {a.get('label') or key} is closing (not confirmed yet)"
    except Exception as e:  # noqa: BLE001
        return f"hedging guard: keep-alive state unreadable ({e.__class__.__name__})"
    return None


def opposite(bot, d: int) -> str | None:
    """The no-hedge rule alone (an entry of direction d on an unknown account): before_entry(bot, d)."""
    return before_entry(bot, d, None)


# ------------------------------------------------------------------------------------------------ alerts
def _alert(bot, kind: str, p: dict) -> str:
    """kind "problem": engine/notify.instant_problem (the private ntfy topic, straight); kind "trade": an entry / exit
    notice (engine/push.pc_notify). Only the real bot sends; a test sets ALERT_HOOK. Never raises."""
    try:
        if ALERT_HOOK is not None:
            ALERT_HOOK(kind, dict(p))
            return "hook"
        if not is_real(bot):
            return "not the real bot"
        if kind == "problem":
            from . import notify
            return notify.instant_problem(dict(p))
        from . import push
        push.pc_notify(dict(p))
        return "queued"
    except Exception as e:  # noqa: BLE001
        return f"failed: {e.__class__.__name__}"


def _due(st: dict, bot, key: str, now) -> bool:
    """An alert key not delivered yet and not tried in the last ALERT_RETRY_S."""
    if not key:
        return True
    if key in st["sent"]:
        return False
    t = _TRIED.get((state_path_for(bot), key))
    return t is None or float(now) - float(t) >= ALERT_RETRY_S


def _queue(Q, st, bot, kind, p, now, row=None, once=False, until=None) -> bool:
    """Queue one alert for delivery after the tick (outside the lock). False = sent already / tried too recently.
    once: a one-shot alert (the entry / result / a refusal) that is kept in st["retry"] when ntfy refuses it (until: the bot
    clock after which a retry no longer makes sense, default RETRY_MAX_S after the first try)."""
    k = str(p.get("key") or "")
    if not _due(st, bot, k, now):
        return False
    _TRIED[(state_path_for(bot), k)] = float(now)
    Q.append({"kind": kind, "p": dict(p), "k": k, "row": row, "once": once, "t": float(now), "until": until})
    if row is not None:
        row["alert"] = "queued"
    return True


def _dispatch(bot, Q):
    """Deliver the queued alerts: a background thread on the real bot (a slow ntfy never holds the live loop or the
    keep-alive's lock), in this thread for tests (ALERT_HOOK / SYNC_ALERTS)."""
    global _LAST_THREAD
    if not Q:
        return
    if ALERT_HOOK is not None or SYNC_ALERTS:
        _deliver(bot, Q)
        return
    t = threading.Thread(target=_deliver, args=(bot, list(Q)), name="keepalive-alerts", daemon=True)
    _LAST_THREAD = t
    t.start()


def _deliver(bot, Q):
    """Send each alert; record its key only when it went out (ALERT_FINAL), else it is tried again (warnings: on a later
    poll, ALERT_RETRY_S apart; one-shot alerts: from st["retry"], for at most RETRY_MAX_S). Never raises."""
    done, failed = [], []
    for it in Q:
        r = _alert(bot, it["kind"], it["p"])
        if it.get("row") is not None:
            it["row"]["alert"] = r
        (done if r in ALERT_FINAL else failed).append((it, r))
        if r not in ALERT_FINAL:
            _log(bot, "error", f"alert '{str(it['p'].get('title'))[:60]}' not delivered ({r}): tried again in "
                               f"{ALERT_RETRY_S // 60} min")
    try:
        with _MX:
            b = _book(bot)
            st = b["st"]
            for it, _ in done:
                if it["k"] and it["k"] not in st["sent"]:
                    st["sent"].append(it["k"])
            keep = [x for x in st.get("retry") or [] if x.get("k") not in {it["k"] for it, _ in done}]
            for it, r in failed:
                if it.get("once") and it["k"] and not any(x.get("k") == it["k"] for x in keep):
                    keep.append({"k": it["k"], "kind": it["kind"], "p": it["p"], "t0": it["t"], "why": str(r)[:80],
                                 **({"until": float(it["until"])} if it.get("until") else {})})
            st["retry"] = keep
            _save_book(bot, b)
    except Exception as e:  # noqa: BLE001
        _log(bot, "error", f"keep-alive alert book not saved ({e.__class__.__name__})")


def _retry_due(bot, st, now, Q):
    """Re-queue the one-shot alerts ntfy refused earlier (ALERT_RETRY_S apart, for at most RETRY_MAX_S)."""
    keep = []
    for x in st.get("retry") or []:
        if not isinstance(x, dict) or x.get("k") in st["sent"] or float(now) - float(x.get("t0") or 0) > RETRY_MAX_S \
                or (x.get("until") and float(now) > float(x["until"])):
            continue
        keep.append(x)
        _queue(Q, st, bot, x.get("kind") or "problem", x.get("p") or {}, now, once=True, until=x.get("until"))
    st["retry"] = keep


def _log(bot, kind, text):
    try:
        bot._log(kind, f"[keep-alive] {text}")
    except Exception:
        pass


def _note(bot, st, key, text, now):
    """Log a skip reason once per account, day and reason."""
    k = f"{key}:{trading_day(now)}:{text[:60]}"
    if k in st["notes"]:
        return
    st["notes"][k] = trading_day(now)
    _log(bot, "system", f"{key}: no keep-alive now: {text}")


# ------------------------------------------------------------------------------------------------ the tick
def tick(bot, now=None, px=None, bar_t=None, may_open: bool = True) -> list:
    """Once per poll (LiveBot._keepalive_tick): close an open keep-alive after hold_s, finish / report it, then (may_open:
    after the poll's routing, with fresh bars) send the heads-up / warnings and open a keep-alive where one is due. The
    alerts go out after the lock is released (a background thread on the real bot). Returns what happened (tests). Never
    raises."""
    out, Q = [], []
    if not _wanted(bot):
        return out
    try:
        with _MX:
            now = int(now if now is not None else bot.clock())
            book = _book(bot)
            st = book["st"]
            active = any(a.get("phase") in ACTIVE for a in (st.get("acc") or {}).values())
            if not may_open and not active:
                return out                                 # the adapter-tick call: nothing open = nothing to do
            C = load_config(bot)
            T = targets(bot)
            dirty = _manage(bot, st, C, T, now, px, out, Q, late=not may_open) if active else False
            if may_open:
                dirty = _plan_all(bot, st, C, T, now, px, bar_t, out, Q, book=book) or dirty
                n = len(Q)
                _retry_due(bot, st, now, Q)
                dirty = dirty or len(Q) > n
            if dirty or out:
                _save_book(bot, book)
    except Exception as e:  # noqa: BLE001
        _log(bot, "error", f"keep-alive tick failed: {e.__class__.__name__}: {e}")
    try:
        _dispatch(bot, Q)
    except Exception as e:  # noqa: BLE001
        _log(bot, "error", f"keep-alive alerts failed: {e.__class__.__name__}: {e}")
    return out


def _leg_of(ad, entry_t, open_only=True):
    try:
        from .ninjatrader import OPEN_STATUSES
        for lg in list(getattr(ad, "legs", None) or []):
            if isinstance(lg, dict) and int(lg.get("entry_t") or 0) == int(entry_t) and (not open_only or lg.get("status") in OPEN_STATUSES):
                return lg
        if not open_only:
            for lg in reversed(list(getattr(ad, "history", None) or [])):
                if isinstance(lg, dict) and int(lg.get("entry_t") or 0) == int(entry_t):
                    return lg
    except Exception:
        return None
    return None


def _push_ids(ad):
    pa = getattr(ad, "push_as", None) if isinstance(getattr(ad, "push_as", None), dict) else {}
    try:
        acct = ad._push_account() if callable(getattr(ad, "_push_account", None)) else getattr(ad, "account", "account")
    except Exception:
        acct = getattr(ad, "account", "account")
    return str(acct or "account"), pa.get("suffix") or "", pa.get("nm")


def _manage(bot, st, C, T, now, px, out, Q, late: bool = False) -> bool:
    """Close / finish the open keep-alives. late (the adapter-tick call, before the poll's data): only a close the
    post-routing call missed (hold + 25 s) or a kill; the normal close runs after the routing with the fresh price."""
    dirty = False
    by_key = {g["key"]: g for g in T}
    hold = C["hold_s"] + 25 if late else max(5, C["hold_s"] - 5)
    for key, a in list((st.get("acc") or {}).items()):
        if a.get("phase") not in ACTIVE:
            continue
        g = by_key.get(key)
        ad = g["adapter"] if g else None
        if ad is None:
            if not a.get("lost_warned"):
                a["lost_warned"] = True
                dirty = True
                _log(bot, "risk", f"{key}: the keep-alive's account is gone from the bot; check NinjaTrader by hand")
            continue
        et_ = int(a["entry_t"])
        lg = _leg_of(ad, et_)
        if lg is not None:
            if lg.get("fill_px") and not a.get("fill"):
                a["fill"], dirty = float(lg["fill_px"]), True
            age = now - int(a.get("sent_at") or et_)
            killed = bool(getattr(bot, "kill", False))
            last_close = int(a.get("close_at") or 0)
            if (age >= hold or killed) and now - last_close >= CLOSE_RETRY_S and int(a.get("closes") or 0) < 4:
                p_now, _ = _price(bot, px)
                a.update(close_at=now, closes=int(a.get("closes") or 0) + 1, phase="closing", px_close=p_now)
                dirty = True
                res = _send(ad, {"sym": (getattr(bot, "cfg", None) or {}).get("sym", "NQ"), "side": "exit", "qty": QTY,
                                 "reason": "KEEP-ALIVE", "entry_t": et_})
                _log(bot, "order", f"{key}: keep-alive close sent ({'ok' if res.get('ok') else res.get('error')})")
                out.append({"key": key, "do": "close", "ok": bool(res.get("ok"))})
                if res.get("ok"):
                    lg = _leg_of(ad, et_)
            if lg is not None:
                continue
        # no open leg of ours left: closed (our exit, the bracket, the flat-time safety, by hand) or never placed
        done = _leg_of(ad, et_, open_only=False)
        filled = bool(done and int(done.get("filled") or 0) > 0) or bool(a.get("fill"))
        if a.get("phase") == "sending" and done is None and now - int(a.get("sent_at") or et_) < 15:
            continue                                     # the entry may still be on its way (a crash mid-send is retried)
        dirty = True
        if filled:
            fill = float((done or {}).get("fill_px") or a.get("fill") or 0.0)
            why = str((done or {}).get("closed") or "closed").lower()
            exit_reason, ex = "KEEP-ALIVE", a.get("px_close") or _price(bot, px)[0]
            if why.startswith("stop") and done:
                exit_reason, ex = "STOP", done.get("stop")
            elif why.startswith("target") and done:
                exit_reason, ex = "TARGET", done.get("target")
            d = int(a.get("dir") or 1)
            # a CLOSEPOSITION exit has no fill price at NinjaTrader: the last price minus 1 tick (crossing the spread) estimates it
            spread = TICK * PV if exit_reason == "KEEP-ALIVE" else 0.0
            usd = round(((float(ex) - fill) * d * PV - spread if ex and fill else -TICK * PV) * QTY - COMM * QTY, 2)
            a.update(phase="done", last=a.get("day"), usd=usd, exit=exit_reason, closed_at=now, fill=fill or None)
            side = "LONG" if d == 1 else "SHORT"
            nxt = plan(a.get("day") or trading_day(now), now)["hard"]
            label = a.get("label") or key
            _log(bot, "risk", f"{key}: keep-alive trade done: {side} 1 MNQ, about {money(usd)} ({exit_reason.lower()}); MFFU's "
                              f"7-day clock restarts from {a.get('day')} (next trade due by {nxt})")
            acct, sfx, nm = _push_ids(ad)
            from . import push
            p = push.outcome_payload(acct, side, exit_reason, usd, et_, now, src="pc", exit_px=ex, qty=QTY,
                                     who=f"Keep-alive on {label}")
            p["key"] = f"{p['key']}{sfx}"
            p["title"] = f"Keep-alive on {label}: {side} closed"
            p["body"] = (f"{money(usd)} (expected about -{money(EXPECTED_COST)}, at most -{money(WORST_COST)}). "
                         f"MFFU's 7-day clock restarts today.")
            if nm:
                p["nm"] = nm
            row = {"key": key, "do": "done", "usd": usd}
            out.append(row)
            _queue(Q, st, bot, "trade", p, now, row=row)
            # the same result straight to ntfy (engine/notify.instant_problem): it never waits on the web-push route
            _queue(Q, st, bot, "problem", {"key": f"ka:result:{key}:{et_}", "code": "keepalive", "soft": True, "dup_of": p["key"],
                                           "tags": "white_check_mark", "bot": "atlas" if key == "atlas" else "lit",
                                           "title": f"Keep-alive on {label}: closed {side} about {money(usd)}",
                                           "body": f"1 MNQ, {exit_reason.lower()} (expected about -{money(EXPECTED_COST)}, at most "
                                                   f"-{money(WORST_COST)}). MFFU's 7-day clock restarts from {a.get('day')}: "
                                                   f"the next trade is due by {nxt}."}, now, once=True)
        else:
            a.update(phase="failed", closed_at=now)
            why = a.get("error") or "the entry never filled"
            _log(bot, "risk", f"{key}: keep-alive not filled ({why})")
            out.append({"key": key, "do": "not_filled", "why": why})
            _final_refusal(bot, st, C, a, key, now, why, out, Q)
    return dirty


def hand_by(day) -> int:
    """ET minute a hand trade should be done by on trading date `day`: 16:05 (MFFU's flat 16:10), a half day 5 minutes
    before the halt."""
    try:
        from . import cme_calendar as CC
        return int(CC.flat_cut(_date(day), HAND_BY))
    except Exception:
        return HAND_BY


def _hand_note(key) -> str:
    """How the bot learns of a hand trade: NinjaTrader's own Log (no PC step); --traded only as a fallback at the PC."""
    return (f"The bot sees the fill in NinjaTrader's log by itself within a few minutes (at the PC you can also send: "
            f"python -X utf8 -m engine.keepalive --traded {key}).")


def _final_refusal(bot, st, C, a, key, now, why, out, Q, force: bool = False):
    """The last attempt of the day failed (or the window ran out with the keep-alive blocked: force): tell the owner to place
    it by hand (once a day; when ntfy does not take it, retried every ALERT_RETRY_S until the hand-trade time)."""
    if not force and int(a.get("tries") or 0) < MAX_TRIES and in_window(now + RETRY_S) and fits(now + RETRY_S, C["hold_s"]):
        return                                           # a retry is still possible today
    day = trading_day(now)
    k = f"ka:refused:{key}:{day}"
    hb = hand_by(day)
    e = _et(now)
    until = _dt.datetime(e.year, e.month, e.day, hb // 60, hb % 60, tzinfo=ET).timestamp()
    p = {"key": k, "code": "keepalive", "title": f"Keep-alive on {a.get('label') or key} did not go through",
         "body": f"{str(why)[:160]}. Place 1 MNQ by hand on this account before {_hm(hb)} ET (in and out, about "
                 f"-{money(EXPECTED_COST)}). {_hand_note(key)}"}
    row = {"key": key, "do": "refused_alert"}
    if _queue(Q, st, bot, "problem", p, now, row=row, once=True, until=until):
        out.append(row)


def _send(ad, action) -> dict:
    try:
        res = ad.send(action)
        return res if isinstance(res, dict) else {"ok": False, "error": "no result"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{e.__class__.__name__}: {e}"}


def _set_cover(st, keys, now) -> bool:
    cv = st.get("cover") or {}
    keys = sorted(set(keys))
    if not keys and not cv.get("keys"):
        return False                                     # nothing watched (a paper bot): no state file written for it
    if cv.get("keys") == keys and now - int(cv.get("t") or 0) < COVER_EVERY_S:
        return False
    st["cover"] = {"t": int(now), "keys": keys}
    return True


def _plan_all(bot, st, C, T, now, px, bar_t, out, Q, book=None) -> bool:
    dirty = False
    acc = st.setdefault("acc", {})
    busy_any = any(a.get("phase") in ACTIVE for a in acc.values())
    today = trading_day(now)
    cover = []
    for g in T:
        key = g["key"]
        on = C["accounts"].get(key) is True
        pid = _plan_id(g)
        if pid is None:
            continue
        sim = bool(getattr(g["adapter"], "sim", False)) and is_real(bot)
        days, start = account_days(bot, g, C, now)
        dirty = _remember(st, key, g.get("_exact")) or dirty      # the fill days outlive a restart
        a = acc.get(key) or {}
        last, never = last_of(days, start)
        if not last:
            if on:
                _note(bot, st, key, "no start day and no trade known", now)
            continue
        if not sim:
            cover.append(key)                              # this account's inactivity warnings come from here
        if a.get("day") == today and a.get("phase") == "done":
            continue                                       # this account's keep-alive filled today
        if today in days:
            continue
        P = plan(last, now, lead=C["lead_sessions"])
        P.update(never=never, start=start)
        if not (P["due"] or P["eve"]):
            continue
        sd = _stood_down(bot, g, now)
        if sd:
            if on:
                _note(bot, st, key, sd, now)
            continue
        dirty = _warn(bot, st, g, P, on, now, out, Q, C) or dirty
        if not (on and may_trade_today(C, key, today) and P["due"]):
            continue
        if busy_any:
            _note(bot, st, key, "another keep-alive is open", now)
            continue
        if a.get("day") == today and int(a.get("tries") or 0) >= MAX_TRIES:
            continue
        if a.get("day") == today and now - int(a.get("sent_at") or 0) < RETRY_S:
            continue
        why = _gate(bot, g, pid, now, px, bar_t, C)
        if isinstance(why, str):
            waiting = why.startswith(("outside the keep-alive window", "no session today", "too late in the window"))
            if not waiting:
                _note(bot, st, key, why, now)            # (waiting for the window is not news)
            if not waiting and in_window(now) and not fits(now + POLL_S, C["hold_s"]):
                # the last poll a keep-alive could still fit: blocked all window -> the owner places it by hand
                a_ = {**a, "label": g["label"], "tries": MAX_TRIES}
                dirty = True
                _final_refusal(bot, st, C, a_, key, now, f"it was blocked all window: {why}", out, Q, force=True)
            continue
        side, ref = why["side"], why["ref"]
        d = 1 if side == "buy" else -1
        stop = round((ref - d * STOP_PTS) / TICK) * TICK
        target = round((ref + d * TARGET_PTS) / TICK) * TICK
        tries = (int(a.get("tries") or 0) if a.get("day") == today else 0) + 1
        a = {**{k: v for k, v in a.items() if k in ("last", "marked", "fills")}, "day": today, "phase": "sending", "tries": tries,
             "entry_t": int(now), "sent_at": int(now), "side": side, "dir": d, "ref": ref, "stop": stop, "target": target,
             "label": g["label"], "plan": P, "idle_days": P["idle_days"]}
        acc[key] = a
        _save_book(bot, book if book is not None else _book(bot))   # write-ahead: a crash after the order file still knows it
        ad = g["adapter"]
        label = g["label"]
        action = {"sym": (getattr(bot, "cfg", None) or {}).get("sym", "NQ"), "side": side, "qty": QTY, "entry": ref,
                  "stop": stop, "target": target, "entry_t": int(now), "who": f"Keep-alive on {label}"[:40],
                  "reason": "KEEP-ALIVE", "keepalive": True}
        _log(bot, "order", f"{key}: keep-alive {side.upper()} 1 MNQ @ ~{ref:,.2f}, stop {stop:,.2f}, target {target:,.2f}: "
                           f"no trade for {P['idle_days']} days (MFFU's deadline {P['hard']}), out in {C['hold_s']} s")
        res = _send(ad, action)
        try:
            from . import lifecycle as LC
            LC.after_route(bot, key, label, ad, action, res, acct=g["nt"] or key)
        except Exception:
            pass
        lg = _leg_of(ad, int(now))
        if lg is not None:
            lg["keepalive"] = True                      # marks the keep-alive's leg (restart, reconcile, history readers)
            try:
                ad._save()
            except Exception:
                pass
        row = {"key": key, "do": "open", "ok": bool(res.get("ok")), "side": side, "error": res.get("error")}
        if res.get("ok") or lg is not None:
            a["phase"] = "open"
            if lg is not None and lg.get("fill_px"):
                a["fill"] = float(lg["fill_px"])
            px_in = a.get("fill") or ref
            _queue(Q, st, bot, "problem", {
                "key": f"ka:entry:{key}:{int(now)}", "code": "keepalive", "soft": True, "tags": "repeat",
                "bot": "atlas" if key == "atlas" else "lit",
                "title": f"Keep-alive on {label}: {side.upper()} 1 MNQ @ {px_in:,.2f}",
                "body": (f"MFFU's 7-day rule: no trade for {P['idle_days']} days (MFFU's limit {P['hard']}). Stop {stop:,.2f}, "
                         f"target {target:,.2f} (10 points, $20). The bot closes it in about {C['hold_s'] // 60} min: about "
                         f"-{money(EXPECTED_COST)}, at most -{money(WORST_COST)}.")}, now, row=row, once=True)
        else:
            a.update(phase="failed", error=str(res.get("error") or "refused")[:200], closed_at=int(now))
            _log(bot, "risk", f"{key}: keep-alive refused: {a['error']}")
            _final_refusal(bot, st, C, a, key, now, a["error"], out, Q)
        out.append(row)
        busy_any = True
        dirty = True
    return _set_cover(st, cover, now) or dirty


def may_trade_today(C, key, today) -> bool:
    return C.get("skip", {}).get(key) != today


def _system_block(bot, g, now) -> str | None:
    """The owner's stops and the entry guards LIT / ATLAS / the extra accounts obey (None = none blocks):
    the phone / dashboard pause (engine/entry_pause) and the rest of guards._owner_blocks (presence check-in, ai_watch's
    anomaly pause and combined-loss stop: OFF by default), the remote flatten's "no new entries today"
    (LiveBot._no_entries_day), the PC clock guard (guards.clock_problem), the startup reconcile (guards.startup_problems for
    the bot's own account, AccountB.startup_block), LIT's soft daily loss + the combo day stop on LIT's own account, each
    lane's MFFU lock (lifecycle.block), lock-out and entry block (multi_account Account.entry_block). A check that fails
    blocks (the keep-alive is optional; the owner is told to trade by hand)."""
    today = trading_day(now)
    try:
        from . import entry_pause
        p = entry_pause.problem(bot, now)
        if p:
            return f"your pause blocks the keep-alive ({p})"
    except Exception as e:  # noqa: BLE001
        return f"the pause check failed ({e.__class__.__name__})"
    nd = getattr(bot, "_no_entries_day", None)
    if nd is not None and nd == today:
        return "you flattened remotely today: no new entries today (the keep-alive too)"
    try:
        from . import guards as G
        from . import lifecycle as LC
        c = G.config(bot)
        ob = G._owner_blocks(bot, c, now)                # the pause again + presence check-in + ai_watch's stops (OFF by default)
        if ob:
            return "your stop blocks the keep-alive (" + "; ".join(str(x) for x in ob)[:160] + ")"
        cp = G.clock_problem(bot, c)
        if cp:
            return cp
    except Exception as e:  # noqa: BLE001
        return f"the owner-stop / clock check failed ({e.__class__.__name__})"
    for ln in g["lanes"]:
        o = ln["obj"]
        try:
            if ln["kind"] == "lit":
                sp = G.startup_problems(bot, c, now)
                if sp:
                    return "STARTUP DISARMED until reconciled: " + "; ".join(sp)
                lb = LC.block(bot, "lit", now)
                if lb:
                    return lb
                dp = getattr(bot, "day_pnl_routed", None)
                pnl = float(dp()) if callable(dp) else None
                if pnl is not None and c.get("daily_loss") and pnl <= -float(c.get("daily_loss_usd") or 1000.0):
                    return (f"LIT's soft daily loss: today's routed P&L ${pnl:,.0f} reached -$"
                            f"{float(c.get('daily_loss_usd') or 1000.0):,.0f}")
                if pnl is not None and c.get("combo_day_stop") is not None and pnl <= -float(c["combo_day_stop"]):
                    return f"combo eval day stop: today's closed ${pnl:,.0f} <= -${float(c['combo_day_stop']):,.0f}"
            elif ln["kind"] == "acct":
                why = o.startup_block(now) if callable(getattr(o, "startup_block", None)) else None
                why = why or (o.life_block(now) if callable(getattr(o, "life_block", None)) else None)
                lk = getattr(o, "lock", None)
                if not why and isinstance(lk, dict) and lk.get("day") == today:
                    why = f"locked out today: {lk.get('reason')}"
                if not why and callable(getattr(o, "disabled_reason", None)):
                    dis = o.disabled_reason()
                    why = f"disabled: {dis}" if dis else None
                if why:
                    return f"{ln['key']}: {why}"
            elif ln["kind"] == "extra":
                why = o.entry_block(now) if callable(getattr(o, "entry_block", None)) else None
                if why and not str(why).startswith("already traded today"):   # (its fills decide that, not its count)
                    return f"{ln['key']}: {why}"
        except Exception as e:  # noqa: BLE001
            return f"{ln['key']}: entry check failed ({e.__class__.__name__})"
    return None


def _gate(bot, g, pid, now, px, bar_t, C):
    """Every check before the order; a str = why not, else {"side", "ref"}."""
    if getattr(bot, "kill", False):
        return "kill switch"
    ad = g["adapter"]
    if getattr(ad, "disabled", None):
        return f"adapter disabled: {ad.disabled}"
    if getattr(ad, "readonly", False) or getattr(ad, "killed", False):
        return "adapter read-only / killed"
    if getattr(ad, "nt_reset", None) or getattr(ad, "state_problem", None):
        return "NinjaTrader reset / state problem open"
    if not in_window(now):
        w = window(trading_day(now))
        return f"outside the keep-alive window ({_hm(w[0])}-{_hm(w[1])} ET)" if w else "no session today"
    sb = _system_block(bot, g, now)
    if sb:
        return sb
    try:
        from . import lifecycle as LC
        if LC.outside_hours(now):
            return "MFFU flat hours"
    except Exception:
        pass
    nb = news_block(now, C["hold_s"])
    if nb:
        return nb
    h = getattr(bot, "health", None) or {}
    if h.get("entries_blocked") or h.get("stale"):
        return "feed stale: entries blocked"
    ref, bt = _price(bot, px, bar_t)
    if not ref or ref <= 0 or (bt and now - bt > FRESH_BAR_S):
        return "no fresh price"
    for ln in g["lanes"]:
        busy, _, why = _lane_open(ln["kind"], ln["obj"], bot)
        if busy:
            return f"{ln['key']}: {why}"
        busy, _, why = _adapter_open(ln["adapter"])
        if busy:
            return f"{ln['key']}: {why}"
    dirs, unknown = _others_side(bot, g)
    if unknown:
        return f"another account's side is unknown ({unknown})"
    if len(dirs) > 1:
        return "accounts hold both sides"
    side = "sell" if dirs == {-1} else "buy"
    fx = _facts(bot, g, now)
    if fx is None:
        return "balance / floor unknown"
    if fx["balance"] - fx["floor"] < MIN_ROOM:
        return f"room ${fx['balance'] - fx['floor']:,.0f} under ${MIN_ROOM:,.0f}"
    from . import firms
    P = firms.profile(pid, "funded" if _funded(g) else "eval")
    if P is None:
        return f"no firm rules for {pid}"
    mll = float(_num(P.get("dd_amount"), 0.0) or 0.0)
    stt = {"start": fx["start"] or float(_num(P.get("start"), 0.0) or 0.0), "balance": fx["balance"],
           "eod_high": fx["floor"] + mll, "intra_high": fx["floor"] + mll, "day_pnl": fx["day_pnl"], "open_micros": 0}
    d = 1 if side == "buy" else -1
    order = {"sym": "MNQ", "side": side, "qty": QTY, "entry": ref, "stop": ref - d * STOP_PTS, "target": ref + d * TARGET_PTS}
    pos = [{"account": "other", "sym": "NQ", "dir": x} for x in dirs]
    chk = firms.check(P, stt, order, positions=pos, now=now)
    if not chk.get("ok") or int(chk.get("max_qty") or 0) < QTY:
        return "rule check: " + "; ".join(chk.get("block") or ["1 micro does not fit"])[:200]
    if not fits(now, C["hold_s"]):
        return f"too late in the window for a {C['hold_s']} s hold (flat by {_hm(exit_by(trading_day(now)) or 950)} ET)"
    return {"side": side, "ref": float(ref)}


def _idle_words(P) -> str:
    if P.get("never"):
        return f"No trade yet on this account since it started ({P.get('start')})"
    return f"No trade for {P['idle_days']} days"


def _warn(bot, st, g, P, on, now, out, Q, C) -> bool:
    """The phone notices before a keep-alive (ON) or a hand trade (OFF). Each once per account and day (retried until
    ntfy took it)."""
    key, label = g["key"], g["label"]
    if getattr(g["adapter"], "sim", False) and is_real(bot):
        return False                                     # a Sim account on the real bot: no MFFU rule, no phone warning
    m = _mod(now)
    if m < HEADSUP_FROM or m >= 16 * 60 + 10 or not window(P["today"]) or _et(now).date().isoformat() != P["today"]:
        return False
    w = window(P["act_day"]) if P.get("act_day") else None
    win = f"{_hm(w[0])} ET" if w else "the afternoon"
    left = (_date(P["hard"]) - _date(P["today"])).days
    hold_min = max(1, C["hold_s"] // 60)
    if P["due"]:
        k = f"ka:{'headsup' if on else 'today'}:{key}:{P['today']}"
        if on:
            p = {"key": k, "code": "keepalive", "soft": True, "title": f"Keep-alive today on {label}",
                 "body": f"{_idle_words(P)} (MFFU can close an account after {LIMIT_DAYS} days; its limit {P['hard']}). If "
                         f"nothing trades by then, the bot buys 1 MNQ at {win} (or sells, the side an open account holds) and "
                         f"closes it about {hold_min} min later: about -{money(EXPECTED_COST)}, at most -{money(WORST_COST)}. "
                         f"Skip today: python -X utf8 -m engine.keepalive --skip {key}"}
        else:
            late = ("" if left > 0 else " MFFU's 7 days end TODAY." if left == 0
                    else f" MFFU's 7 days ran out on {P['hard']}: trade it today and check the MFFU dashboard.")
            p = {"key": k, "code": "keepalive", "title": f"{label}: TODAY is the last safe day to trade",
                 "body": f"{_idle_words(P)}. MFFU can close the account after {LIMIT_DAYS} days without a "
                         f"trade{' and a funded one loses ALL its profits' if _funded(g) else ''}.{late} Place 1 MNQ by hand "
                         f"before {_hm((w or FULL_WINDOW)[1] + HALF_WINDOW[1])} ET (in and out, about -{money(EXPECTED_COST)}). "
                         f"{_hand_note(key)}"}
        row = {"key": key, "do": "headsup" if on else "warn_today"}
        if not _queue(Q, st, bot, "problem", p, now, row=row):
            return False
        out.append(row)
        return True
    if P["eve"] and not on:
        k = f"ka:eve:{key}:{P['today']}"
        if f"ka:today:{key}:{P['today']}" in st["sent"]:
            return False                                 # told "TODAY" already: one warning a day (tomorrow's says TODAY again)
        nd = _date(P["act_day"])
        p = {"key": k, "code": "keepalive", "soft": True, "title": f"{label}: the next session is the last safe day to trade",
             "body": f"{_idle_words(P)}; MFFU's limit is {P['hard']} ({left} days). If the bot does not trade it first, place "
                     f"1 MNQ by hand on {nd:%a} {nd:%m-%d} (in and out), or turn the keep-alive on: KEEPALIVE_ON.bat on the "
                     f"PC."}
        row = {"key": key, "do": "warn_eve"}
        if not _queue(Q, st, bot, "problem", p, now, row=row):
            return False
        out.append(row)
        return True
    return False


# ------------------------------------------------------------------------------------------------ the START phrase's consent
CONSENT_NOTE = "it only trades an account that would otherwise hit 7 days without a trade"


def start_consent(phrase, armed, now=None, path: str | None = None) -> dict:
    """The owner typed I ACCEPT LIVE RISK at a START (engine/go.step_arm, after every account is armed): the keep-alive goes
    ON for exactly `armed` = [(key, label, NinjaTrader name)] of the real accounts that START armed. A Sim / paper name, a
    key the owner switched OFF himself (owner_off, "*" = tools/bat/KEEPALIVE_OFF.bat) and any account not in `armed` are left as they
    are. Without the exact phrase nothing changes. The phrase is never written: only {"consent": {"t", "day", "accounts",
    "via"}}. Returns {"on": [labels], "kept_off": [labels], "line": the summary line ("" = nothing to say)}. Never raises."""
    out = {"on": [], "kept_off": [], "line": "", "keys": []}
    try:
        from .tradovate import LIVE_PHRASE
        if phrase != LIVE_PHRASE:
            return out
        try:
            from .ninjatrader import is_sim
        except Exception:
            def is_sim(n):
                return True
        now = time.time() if now is None else float(now)
        C = load_config(None, path=path or CONFIG_PATH)
        off = dict(C.get("owner_off") or {})
        try:                                   # red team 2026-11-23: a file from BEFORE owner_off existed (no "owner_off" and no
            with open(path or CONFIG_PATH, encoding="utf-8") as fh:      # "consent" field): an explicit false there is his OFF
                raw = json.load(fh)
            if isinstance(raw, dict) and "owner_off" not in raw and "consent" not in raw:
                legacy = {str(k): "before" for k, v in (raw.get("accounts") or {}).items() if v is False}
                off.update(legacy)
                C["owner_off"] = {**(C.get("owner_off") or {}), **legacy}     # kept in the file: every later START keeps it off
        except Exception:
            pass
        on_keys = []
        for key, label, name in armed or []:
            key, label, name = str(key or ""), str(label or key), str(name or "").strip()
            if not key or not name or is_sim(name) or key in on_keys:
                continue
            if C["accounts"].get(key) is not True and (key in off or "*" in off):
                out["kept_off"].append(label)
                continue
            C["accounts"][key] = True
            on_keys.append(key)
            out["on"].append(label)
        if on_keys:
            C["consent"] = {"t": int(now), "day": _cal(now), "accounts": on_keys, "via": "start_phrase"}
            save_config(C, path or CONFIG_PATH)
        out["keys"] = on_keys
        parts = []
        if out["on"]:
            parts.append(f"Keep-alive ON for: {', '.join(out['on'])} ({CONSENT_NOTE}). Off: tools/bat/KEEPALIVE_OFF.bat or TRADE_HOME.")
        if out["kept_off"]:
            parts.append(f"Keep-alive stays OFF for: {', '.join(out['kept_off'])} (you turned it off; KEEPALIVE_ON.bat turns it on).")
        out["line"] = " ".join(parts)
    except Exception as e:  # noqa: BLE001
        out["line"] = f"Keep-alive NOT changed ({e.__class__.__name__}): KEEPALIVE_ON.bat turns it on."
    return out


# ------------------------------------------------------------------------------------------------ status / CLI
def status(bot=None, now=None) -> dict:
    """The switches, each account's last keep-alive and (with a bot) its plan. Never raises."""
    now = int(now or time.time())
    C = load_config(bot)
    st = load_state(state_path_for(bot))
    rows = []
    if bot is not None:
        try:
            for g in targets(bot):
                last, start, never = last_known(bot, g, C)
                rows.append({"key": g["key"], "label": g["label"], "on": C["accounts"].get(g["key"]) is True,
                             "mffu": _plan_id(g) is not None, "last_trade": None if never else last, "start": start,
                             "plan": plan(last, now, lead=C["lead_sessions"]) if last else None})
        except Exception as e:  # noqa: BLE001
            rows.append({"error": f"{e.__class__.__name__}: {e}"})
    return {"accounts": C["accounts"], "skip": C["skip"], "start": C["start"], "hold_s": C["hold_s"], "rows": rows,
            "last": {k: {x: a.get(x) for x in ("day", "phase", "usd", "exit", "tries", "error", "last", "marked", "fills")}
                     for k, a in (st.get("acc") or {}).items()},
            "cost": {"expected": EXPECTED_COST, "worst": WORST_COST}}


def check_traded_day(day, now=None) -> str:
    """The hand-trade day for --traded: default the ET calendar date now (typed in the evening it is still today, never the
    next trading day); refused (ValueError) when in the future or more than TRADED_BACK_DAYS back (a phone typo would
    otherwise silence the keep-alive and every inactivity warning for weeks)."""
    now = time.time() if now is None else float(now)
    today = _et(now).date()
    d = _date(day) if day else today
    if d > today:
        raise ValueError(f"{d} is in the future (today is {today} ET)")
    if (today - d).days > TRADED_BACK_DAYS:
        raise ValueError(f"{d} is more than {TRADED_BACK_DAYS} days back")
    return d.isoformat()


def known_keys(path: str | None = None) -> set:
    """The account keys the keep-alive knows: lit, atlas, rapid, x:<id> of every extra account in data/accounts.json, the
    START_DEFAULTS keys and the keys the bot itself wrote to its state file. Never raises."""
    ks = {"lit", "atlas", "rapid"} | set(START_DEFAULTS)
    try:
        from .multi_account import load_file
        for sp in load_file():
            if sp.get("id"):
                ks.add("rapid" if sp.get("lane") == "rapid" else f"x:{sp['id']}")
    except Exception:
        pass
    try:
        ks |= {str(k) for k in (load_state(path or state_path_for(None)).get("acc") or {})}
    except Exception:
        pass
    return ks


def check_key(key, path: str | None = None) -> str:
    """`key` when it is a known account key, else ValueError (a typo like x:b25k2 must not print 'noted' and change
    nothing)."""
    k = str(key or "").strip()
    ks = known_keys(path)
    if k not in ks:
        raise ValueError(f"unknown account {k!r} (known: {', '.join(sorted(ks))})")
    return k


def check_start_day(day, now=None) -> str:
    """--start: a real date, never after today (ET)."""
    d = _date(day)
    today = _et(time.time() if now is None else float(now)).date()
    if d > today:
        raise ValueError(f"{d} is in the future (today is {today} ET)")
    return d.isoformat()


def mark_traded(key: str, day: str | None = None, path: str | None = None, now=None) -> dict:
    """The owner traded an account by hand: its idle clock restarts from `day` (default today, the ET date). Raises
    ValueError for a day in the future / too far back. The file is re-read right before the write and the write retried
    when the bot saved it in between (the bot's own save merges these notes too: _save_book)."""
    d = check_traded_day(day, now)
    p = path or state_path_for(None)
    for _ in range(5):
        mt = _mtime(p)
        st = load_state(p)
        a = st["acc"].setdefault(key, {})
        a["marked"] = max(d, str(a.get("marked") or ""))
        if _mtime(p) != mt:
            time.sleep(0.05)
            continue                                     # the bot wrote it meanwhile: read its newer file again
        save_state(st, p)
        return a
    save_state(st, p)
    return a


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="engine.keepalive", description="MFFU 7-day keep-alive trade (OFF by default)")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--plan", metavar="LAST_TRADE_DAY")
    ap.add_argument("--on", metavar="KEY")
    ap.add_argument("--off", metavar="KEY")
    ap.add_argument("--skip", metavar="KEY")
    ap.add_argument("--traded", nargs="+", metavar=("KEY", "DAY"))
    ap.add_argument("--start", nargs=2, metavar=("KEY", "DAY"))
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args(argv)
    if a.plan:
        p = plan(a.plan, time.time())
        w = window(p["act_day"]) if p["act_day"] else None
        print(f"last trade {p['last']}: MFFU's literal limit {p['hard']}, cautious deadline {p['deadline']}; the keep-alive acts on "
              f"{p['act_day'] or '-'}" + (f" {_hm(w[0])}-{_hm(w[1])} ET" if w else "") + f" (today {p['today']}: due {p['due']}).")
        print(f"cost: about {money(EXPECTED_COST)} (commission ${COMM:.2f} + 1 tick), at most {money(WORST_COST)} (stop {STOP_PTS:g} pts)")
        return 0
    if a.on and a.off:
        print("NOT changed: use --on or --off, not both.")
        return 2
    if "all" in (a.on, a.off):        # KEEPALIVE_ON.bat / tools/bat/KEEPALIVE_OFF.bat: every known account in one go (owner 2026-11-20)
        C = load_config(None)
        # --off all also clears keys only the config still names (an account removed since), so OFF means every account
        keys = sorted(set(known_keys()) | (set(C.get("accounts") or {}) if a.off else set()))
        if a.on and not a.yes:
            print(f"This lets the bot place a REAL 1-MNQ order on each MFFU account ({', '.join(keys)}) when it has not "
                  f"traded for days (about -{money(EXPECTED_COST)} each time, at most -{money(WORST_COST)}). The owner's "
                  f"decision only. Add --yes to switch it on.")
            return 2
        for k in keys:
            C["accounts"][k] = bool(a.on)
        if a.on:
            C["owner_off"] = {}                          # his ON clears every earlier OFF
        else:                                            # sticks: a later START phrase leaves these OFF (start_consent)
            C["owner_off"] = {**{k: _cal(time.time()) for k in keys}, "*": _cal(time.time())}
        print(f"keep-alive {'ON' if a.on else 'OFF'} for {', '.join(keys)} ({save_config(C)}); the bot reads it on its "
              f"next poll" + ("" if a.on else ". A START with the phrase keeps it OFF; KEEPALIVE_ON.bat turns it back on."))
        return 0
    try:
        for k in (a.on, a.off, a.skip, (a.start or [None])[0], (a.traded or [None])[0]):
            if k is not None:
                check_key(k)
    except ValueError as e:
        print(f"NOT changed: {e}.")
        return 2
    if a.on or a.off:
        C = load_config(None)
        key = a.on or a.off
        if a.on and not a.yes:
            print(f"This lets the bot place a REAL 1-MNQ order on {key} when it has not traded for days (about -{money(EXPECTED_COST)}, "
                  f"at most -{money(WORST_COST)}). The owner's decision only. Add --yes to switch it on.")
            return 2
        C["accounts"][key] = bool(a.on)
        if a.on:
            C["owner_off"].pop(key, None)
        else:
            C["owner_off"][key] = _cal(time.time())     # sticks: a later START phrase leaves it OFF
        print(f"keep-alive {key}: {'ON' if a.on else 'OFF'} ({save_config(C)}); the bot reads it on its next poll")
        return 0
    if a.skip:
        C = load_config(None)
        C["skip"][a.skip] = trading_day(time.time())
        save_config(C)
        print(f"no keep-alive on {a.skip} today ({C['skip'][a.skip]})")
        return 0
    if a.start:
        try:
            d = check_start_day(a.start[1])
        except ValueError as e:
            print(f"NOT changed: {e} (yyyy-mm-dd, never a future day)")
            return 2
        except Exception:
            print(f"not a date: {a.start[1]!r} (yyyy-mm-dd)")
            return 2
        C = load_config(None)
        C["start"][a.start[0]] = d
        save_config(C)
        print(f"{a.start[0]}: MFFU start {d} (used when it is up to {START_PULL_DAYS} days before the bot's own start)")
        return 0
    if a.traded:
        try:
            r = mark_traded(a.traded[0], a.traded[1] if len(a.traded) > 1 else None)
        except ValueError as e:
            print(f"NOT noted: {e}. Send the ET date of the hand trade (yyyy-mm-dd), or nothing for today.")
            return 2
        p = plan(r["marked"], time.time())
        print(f"{a.traded[0]}: hand trade noted on {r['marked']}. MFFU's 7 days now end {p['hard']}; the bot's last safe day "
              f"is {p['act_day'] or p['deadline']}.")
        return 0
    s = status(None)
    print(json.dumps(s, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
