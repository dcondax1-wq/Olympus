"""Phone alerts, short and $-first (owner 2026-11-17: "better notifications on my phone"; not spammy). Stdlib only: the PC
report (tools/pc_report.py + tools/pc_guard.py, every 15 min -> your private ntfy topic) and the cloud's PC-silent check
(tools/pc_silent_check.py, a cloud-monitor step) both use it. Read-only: nothing here places, changes or arms anything.

One settings file: notify_settings.json (repo root; a missing or broken file = DEFAULTS, a missing key = its default).
  alerts               per type on / off: trade_opened, trade_closed, eval_milestones (25/50/75 %), account_status (PASSED,
                       FAILED, LOCKED, LOST, target reached, payout READY), room_low, daily_summary, morning_brief, pc_silent,
                       problems (bot down, FEED STALE, NinjaTrader closed, fill check, trade watch), other (roll, quiet bot, ...).
                       Default (owner 2026-11-18, "important only" + every entry): ON = trade_opened, trade_closed,
                       account_status, daily_summary, morning_brief, pc_silent, problems; the rest OFF. Entries go out the
                       moment NinjaTrader fills them (instant_entry, via engine/push.pc_notify; the 15-minute report then skips
                       the same entry), closes the moment they close (instant_exit, 2026-11-20: $, today, balance, $ to pass).
  quiet_hours          ET; inside them trade pushes and ordinary ones arrive without sound (ntfy priority "low"), the guard's
                       summaries / milestones wait for the end; ring_in_quiet_hours kinds keep their sound
  milestones_pct       eval progress pushes (% of the profit target made), once per level per eval
  room_low_used_pct    "room getting low" pushes (% of the max loss used), once per level per eval
  daily_summary_at     the day summary time (ET), up to the 17:00 CME break
  morning_brief_at     the morning brief time (ET, default 07:30, up to 09:30; tools/morning_brief.py): 4 lines = PC ok?, each
                       account ($ / to pass / to payout), overnight trades + today's entry hours + big news, edge light + needs you
  pc_silent_after_min  the cloud says "Your PC stopped reporting" when neither its heartbeat nor its status feed is newer
  pc_silent_remind_after_min   one reminder after this; at most 2 pushes per outage per trading day, never every run

Messages (examples; docs/TRADE_ALERTS.md):
  Zlarior 50K: LONG 4 MNQ @ 21,034.25       stop 21,012.00 (-$178), target 21,090.50 (+$450) · 10:31 AM ET.   (instant, at the fill)
  Zlarior 50K: closed LONG +$312 (target)   today +$312, balance $49,505, $3,495 to pass · +1.4R · 4 MNQ · 10:58 AM ET.
  Zlarior 50K SHORT opened | risk $368 | target +$1,432   (the 15-minute report's own words, tools/pc_report, when no instant push went)
  Zlarior 50K: 50% of the target made ($1,500 of $3,000)
  ATLAS 25K: room getting low, $250 left of $1,000
  Day Mon Nov 16: +$310                     (each account: $ today, $ to pass, room; tomorrow's big US news)
  ZEUS - Wed Nov 18 - PC ok                 (07:30 ET: accounts, overnight, today's hours + news, edge, needs you)
  PC stopped reporting                      Your PC stopped reporting at 09:14 ET. Check it: STOP BOT, START BOT.
Tests: python -X utf8 -m tests.test_notify, tests.test_trade_alerts (every account route: one entry + one exit, name, $)
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import re
import threading
import time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_PATH = os.path.join(ROOT, "notify_settings.json")
TYPES = ("trade_opened", "trade_closed", "eval_milestones", "account_status", "room_low", "daily_summary", "morning_brief", "pc_silent",
         "problems", "other")
# owner 2026-11-18: "important only" = trade results, PASSED / FAILED / LOCKED, payout ready, PC silent, the daily summary
# (+ the 07:30 ET morning brief, tools/morning_brief.py, 2026-11-18).
# Everything else is OFF by default (one line in notify_settings.json turns a type back on).
# owner 2026-11-18 evening: "I want notifications when we get in a trade in any account" -> trade_opened ON, sent the moment the
# bot routes the entry (instant_entry below, from engine/push.pc_notify), not at the next 15-minute report.
IMPORTANT = ("trade_opened", "trade_closed", "account_status", "daily_summary", "morning_brief", "pc_silent", "problems")   # problems = emergencies (bot down, NinjaTrader closed)
# A trade's entry and result in quiet hours (23:00-07:00 ET) come WITHOUT sound but still show (as before 2026-11-20). Putting
# TRADE_RING in ring_in_quiet_hours (notify_settings.json) makes them ring at night: the owner's yes / no, asked on STATE.md
# 'Waiting on the owner' (lead 2026-11-20; ATLAS enters around 03:00-04:00 ET, LIT from 02:00 ET on several accounts).
TRADE_RING = ("trade_opened", "trade_closed")
# The kinds that go to BOTH phone routes, the Olympus app AND the private ntfy topic (2026-11-20, notify_settings.json trade_routes;
# a push service's "accepted" only means Apple / Google took it, not that the iPhone showed it): a trade's entry and result, PASSED /
# FAILED / LOCKED / payout ready / a quiet eval (account_status), room low (OFF by default), the 15-minute report's problems (bot
# down, NinjaTrader closed, FEED STALE; the ones engine/fast_alarm already sent in the entry hours are dropped by problem_dup and
# stay on ntfy only; "Back to normal" stays Olympus first, NOT_DUAL_KEYS), pc_silent (the report makes no such key: PC silent comes
# from the cloud's tools/pc_silent_check.py, on ntfy). Every other kind: Olympus first, ntfy only when no phone took it.
DUAL_KINDS = ("trade_opened", "trade_closed", "account_status", "room_low", "problems", "pc_silent")
# trade_routes: "both" (default) = Olympus AND ntfy; "olympus" = Olympus first, ntfy only when no phone took it; "ntfy" = ntfy first,
# Olympus only when ntfy did not take it. A single-route choice keeps the other as the fallback, so an alert never reaches nobody.
ROUTES = ("both", "olympus", "ntfy")
DEFAULTS = {
    "alerts": {k: k in IMPORTANT for k in TYPES},
    "quiet_hours": {"from": "23:00", "to": "07:00"},
    "ring_in_quiet_hours": ["pc_silent", "account_status", "room_low", "problems"],
    "trade_routes": "both",
    "milestones_pct": [25, 50, 75, 100],
    "room_low_used_pct": [50, 75],
    "daily_summary_at": "16:15",
    "morning_brief_at": "07:30",
    "pc_silent_after_min": 20,
    "pc_silent_remind_after_min": 120,
}
GOAL_BY_SIZE = {"25K": 1500.0, "50K": 3000.0, "100K": 6000.0, "150K": 9000.0}   # MFFU profit targets (research/lit/mffu_rules.json)
_CACHE = {"key": None, "val": None}


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


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
    return "-" if v is None else ("+" if v >= 0 else "-") + "${:,.0f}".format(abs(round(v)))


def hm_min(s, default: int) -> int:
    """'16:15' -> 975 minutes after midnight; junk -> default."""
    m = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*", str(s or ""))
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        return default
    return int(m.group(1)) * 60 + int(m.group(2))


def _et(t) -> dt.datetime:
    return dt.datetime.fromtimestamp(int(t), ET)


def _mod(t) -> int:
    e = _et(t)
    return e.hour * 60 + e.minute


# ------------------------------------------------------------------------------------------------ settings
def settings(path: str | None = None) -> dict:
    """The settings file merged over DEFAULTS. Never raises (cached by the file's mtime)."""
    p = path or SETTINGS_PATH
    try:
        key = (p, os.path.getmtime(p))
    except OSError:
        key = (p, None)
    if _CACHE["key"] == key and _CACHE["val"] is not None:
        return _CACHE["val"]
    raw = {}
    if key[1] is not None:
        try:
            with open(p, encoding="utf-8") as fh:
                raw = json.load(fh)
        except Exception:
            raw = {}
    out = merge(raw)
    _CACHE.update(key=key, val=out)
    return out


def merge(raw) -> dict:
    raw = _d(raw)
    out = json.loads(json.dumps(DEFAULTS))
    for k, v in _d(raw.get("alerts")).items():
        if k in out["alerts"] and isinstance(v, bool):
            out["alerts"][k] = v
    q = _d(raw.get("quiet_hours"))
    for k in ("from", "to"):
        if isinstance(q.get(k), str) and hm_min(q[k], -1) >= 0:
            out["quiet_hours"][k] = q[k]
    if q.get("off") is True:
        out["quiet_hours"]["off"] = True
    if isinstance(raw.get("ring_in_quiet_hours"), list):
        out["ring_in_quiet_hours"] = [str(x) for x in raw["ring_in_quiet_hours"] if str(x) in TYPES]
    if str(raw.get("trade_routes") or "").strip().lower() in ROUTES:
        out["trade_routes"] = str(raw["trade_routes"]).strip().lower()
    for k in ("milestones_pct", "room_low_used_pct"):
        if isinstance(raw.get(k), list):
            vals = sorted({int(x) for x in raw[k] if isinstance(x, (int, float)) and 0 < x <= 100})
            out[k] = vals
    for k in ("daily_summary_at", "morning_brief_at"):
        if isinstance(raw.get(k), str) and hm_min(raw[k], -1) >= 0:
            out[k] = raw[k]
    for k, lo, hi in (("pc_silent_after_min", 5, 240), ("pc_silent_remind_after_min", 30, 720)):
        v = raw.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out[k] = int(min(hi, max(lo, v)))
    return out


def on(kind: str, s: dict | None = None) -> bool:
    return bool(_d((s or settings()).get("alerts")).get(kind, True))


def quiet(now, s: dict | None = None) -> bool:
    """Inside the quiet hours (ET). A window over midnight (23:00-07:00) works; from == to = never quiet."""
    q = _d((s or settings()).get("quiet_hours"))
    if q.get("off"):
        return False
    a, b = hm_min(q.get("from"), 23 * 60), hm_min(q.get("to"), 7 * 60)
    m = _mod(now)
    if a == b:
        return False
    return a <= m < b if a < b else (m >= a or m < b)


def rings(kind: str, s: dict | None = None) -> bool:
    return kind in ((s or settings()).get("ring_in_quiet_hours") or ())


def trade_routes(s: dict | None = None) -> str:
    """notify_settings.json trade_routes: "both" (default) | "olympus" | "ntfy" (ROUTES). Never raises."""
    try:
        v = str((s or settings()).get("trade_routes") or "both").lower()
        return v if v in ROUTES else "both"
    except Exception:
        return "both"


# "Back to normal" (back:<code>) and "PC back" (pc_back:) are problems / pc_silent by kind but stay Olympus first, as before: the
# problem itself already goes to both apps, and a second copy of the all-clear would add one more sound at night (skeptic
# 2026-11-20: a FEED STALE flap at 00:15 ET would be 4 sounds; it is 3, it was 2 before both routes).
NOT_DUAL_KEYS = ("back:", "pc_back:")


def dual(kind: str, key=None) -> bool:
    """An alert that goes to both phone routes when trade_routes is "both": its kind is in DUAL_KINDS and its key is not an all-clear
    (NOT_DUAL_KEYS)."""
    return kind in DUAL_KINDS and not str(key or "").startswith(NOT_DUAL_KEYS)


def kind_of(key: str) -> str:
    """The settings type of a PC report push, from its key."""
    k = str(key or "")
    if k.startswith("open:"):
        return "trade_opened"
    if k.startswith("close:"):
        return "trade_closed"
    if k.startswith("life:"):                       # engine/lifecycle.py: PASSED / FAILED / LOCKED / LOST / payout READY
        return "account_status"
    if k.startswith("guard:goal:"):                 # tools/pc_guard.py: 25 / 50 / 75 % = progress; 100 % = the target reached
        return "account_status" if k.rstrip().endswith(":100") else "eval_milestones"
    if k.startswith(("guard:dd:", "guard:dll:")):
        return "room_low"
    if k.startswith("guard:day:"):
        return "daily_summary"
    if k.startswith("guard:brief:"):                # tools/morning_brief.py: the 07:30 ET ZEUS brief
        return "morning_brief"
    if k.startswith("breaker:"):                    # engine/circuit_breaker: live vs twin SIZE DOWN / PAUSE advice for an account
        return "account_status"
    if k.startswith("guard:quiet:"):                # tools/pc_guard: a live eval 5+ days without a trade (MFFU closes an eval after 7;
        return "account_status"                     # high from day 6, never in quiet hours). Was "other" (OFF): it reached no phone
    if k.startswith(("cond:", "back:", "fill:", "watch:", "risk:")):    # risk:throttle: engine/msg_throttle runaway orders
        return "problems"
    if k.startswith(("pc_silent:", "pc_back:")):
        return "pc_silent"
    return "other"


# the 15-minute report's account words ("open:<acct>:<t>", tools/pc_report._trade_events) -> the account part of the instant alerts'
# keys ("fill:<t>" = LIT's primary 50K and the 50K combo on it, ":acctb" = ATLAS's account B, ":acctc" = BLITZ's account C,
# ":<id>" = an extra account / the Rapid's LIT lane, ":acctr" = the Rapid's ATLAS lane)
REPORT_ACCT = {"lit": "", "atlas": "acctb", "blitz": "acctc"}
# The report's "lit" row stands for EVERY LIT account: engine/live_board.trade_log files all the PC's LIT trades (the 50K, the 25K #2,
# the Rapid's LIT lane) under "lit", one row per bar, labelled as the 50K. So for that row any LIT-family instant alert counts (every
# key whose account part is not one of these); ATLAS (acctb) and BLITZ (acctc) keep the exact match (skeptic 2026-11-20: with an
# exact "" match, the 25K #2's own entry / result came back 15 minutes later as a false "Zlarior 50K opened / closed" on both apps).
NOT_LIT = ("acctb", "acctc", "acctr")


def acct_match(key, acct) -> bool:
    """Whether an instant alert's key counts for a report push's account (report_acct): None = any account (the old rule), "" (the
    report's "lit" row) = any LIT-family key (not NOT_LIT), else the exact account part ("acctb" = ATLAS only)."""
    if acct is None:
        return True
    ka = key_acct(key)
    if str(acct) == "":
        return ka not in NOT_LIT
    return ka == str(acct)


def key_acct(key) -> str:
    """The account part of an instant trade alert's key: "fill:1795164300:acctb" -> "acctb", "out:1795164300:b25k_2" -> "b25k_2",
    "fill:1795164300" -> "" (LIT's primary account)."""
    parts = str(key or "").split(":", 2)
    return parts[2] if len(parts) == 3 and parts[0] in ("fill", "out") else ""


def report_acct(m: dict):
    """The instant key's account part a 15-minute report trade push stands for (REPORT_ACCT; an extra account's id stays itself).
    None when the push names no account (then any account matches, the old rule)."""
    m = _d(m)
    a = m.get("acct")
    if a is None:
        k = str(m.get("key") or "")
        parts = k.split(":")
        if k.startswith(("open:", "close:")) and len(parts) >= 3:
            a = parts[1]
    if a is None or str(a) == "":
        return None
    a = str(a)
    return REPORT_ACCT.get(a, a)


def entry_t_of(m: dict):
    """A report push's trade entry time: its "entry_t", else the last number of its key ("open:lit:1795050000")."""
    m = _d(m)
    if _f(m.get("entry_t")) is not None:
        return _f(m.get("entry_t"))
    k = str(m.get("key") or "")
    if k.startswith(("open:", "close:")):
        return _f(k.rsplit(":", 1)[-1])
    return None


def apply(msgs, now, s: dict | None = None) -> list:
    """The settings on a list of pushes ({key, title, body, priority, ...}): a type that is off is dropped (its key stays
    recorded as seen by the caller, so it never comes later); in quiet hours a trade or an ordinary push loses its sound."""
    s = s or settings()
    out = []
    for m in msgs or []:
        if not isinstance(m, dict):
            continue
        kind = m.get("kind") or kind_of(m.get("key"))
        if not on(kind, s):
            continue
        # per account (2026-11-20): ATLAS's instant alert never stands for LIT's report copy on the same bar, nor LIT's for ATLAS's;
        # the report's one "lit" row stands for every LIT account (acct_match)
        if kind == "trade_opened" and instant_sent(entry_t_of(m), acct=report_acct(m)):
            continue                                # ntfy already got this entry the moment it was routed
        if kind == "trade_closed" and instant_sent(entry_t_of(m), what="exits", acct=report_acct(m)):
            continue                                # ntfy already got this exit the moment the bot saw it
        if kind == "problems" and problem_dup(m, now):
            continue                                # the PC's fast alarm already sent it (engine/fast_alarm.py, instant_problem)
        if quiet(now, s) and not rings(kind, s) and not m.get("night"):
            if kind in ("trade_opened", "trade_closed") or m.get("priority") in (None, "", "default"):
                m = {**m, "priority": "low"}
        out.append(m)
    return out


# ------------------------------------------------------------------------------------------------ eval numbers
def goal_usd(card: dict | None):
    """The eval's profit target in $: MFFU's by the plan size (50K $3,000, 25K $1,500), else profit + $ to go."""
    c = _d(card)
    m = re.search(r"(\d+K)", str(c.get("plan") or ""))
    if m and m.group(1) in GOAL_BY_SIZE:
        return GOAL_BY_SIZE[m.group(1)]
    p, tt = _f(c.get("profit")), _f(c.get("to_target"))
    if p is not None and tt is not None and p + max(0.0, tt) > 0:
        return p + max(0.0, tt)
    return None


def progress(card: dict | None):
    """(made $, goal $, pct 0-100) toward the profit target, or None when the card does not say."""
    c = _d(card)
    goal, tt = goal_usd(c), _f(c.get("to_target"))
    if not goal:
        return None
    if tt is None:
        p = _f(c.get("profit"))
        if p is None:
            return None
        made = p
    else:
        made = goal - max(0.0, tt)
    made = max(0.0, min(goal, made))
    return made, goal, made / goal * 100.0


# ------------------------------------------------------------------------------------------------ tomorrow's news
NEWS_WORDS = ("cpi", "fomc", "fed ", "fed chair", "powell", "payroll", "non-farm", "nfp", "pce", "gdp", "ppi", "retail", "ism",
              "minutes", "jobless", "unemployment", "jolts")


def next_session_day(now) -> dt.date:
    """The next CME trading day after today's close (Fri -> Mon, a full closure skipped)."""
    d = _et(now).date()
    for _ in range(10):
        d += dt.timedelta(days=1)
        if d.weekday() >= 5:
            continue
        try:
            from .cme_calendar import full_closure
            if full_closure(d):
                continue
        except Exception:
            pass
        return d
    return d


def news_on(day: dt.date, root: str = ROOT) -> list:
    """[(time 'HH:MM', title)] of the high-impact US releases on `day`: the news hub (data/news/hub.json) when it covers the day,
    else the stored calendar (data/news/events.csv). Never raises."""
    ds = day.isoformat()
    out = []
    try:
        with open(os.path.join(root, "data", "news", "hub.json"), encoding="utf-8") as fh:
            hub = json.load(fh)
        rng = _d(hub.get("range"))
        evs = [e for e in hub.get("events") or [] if isinstance(e, dict)]
        if (rng.get("from") or "9") <= ds <= (rng.get("to") or "0") or any(e.get("date") == ds for e in evs):
            for e in evs:
                if e.get("date") == ds and e.get("impact") == "high" and e.get("country") in (None, "USD"):
                    out.append((str(e.get("time_et") or ""), str(e.get("title") or "")))
            return _dedupe(out)
    except Exception:
        pass
    try:
        with open(os.path.join(root, "data", "news", "events.csv"), encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if r.get("date") == ds and r.get("impact") == "high":
                    out.append((str(r.get("time_et") or ""), str(r.get("event") or "")))
    except Exception:
        pass
    return _dedupe(out)


def _dedupe(rows) -> list:
    seen, out = set(), []
    for t, title in sorted(rows):
        k = (t, title.lower())
        if title and k not in seen:
            seen.add(k)
            out.append((t, title))
    return out


def news_line(now, root: str = ROOT) -> str:
    """'Tomorrow (Wed): Fed meeting minutes 14:00.' / 'Tomorrow (Mon): no big US news.' (the big ones first, 3 at most)."""
    day = next_session_day(now)
    rows = news_on(day, root)
    name = day.strftime("%a")
    if not rows:
        return f"Tomorrow ({name}): no big US news."
    big = [r for r in rows if any(w in r[1].lower() + " " for w in NEWS_WORDS)] or rows
    txt = ", ".join(f"{title} {t}".strip() for t, title in big[:3]) + (f" (+{len(big) - 3} more)" if len(big) > 3 else "")
    return f"Tomorrow ({name}): {txt}."


# ------------------------------------------------------------------------------------------------ PC silent (cloud)
def silent_window(now) -> bool:
    """Market hours for the PC-silent check: weekdays 01:30-16:00 ET, not a CME full closure (engine/push.pc_offline_window)."""
    try:
        from .push import pc_offline_window
        return pc_offline_window(now)
    except Exception:
        e = _et(now)
        return e.weekday() < 5 and 90 <= e.hour * 60 + e.minute <= 960


def since_text(t, now) -> str:
    """'09:14 ET' today, 'Fri Nov 6 09:14 ET' another day."""
    e, n = _et(t), _et(now)
    return f"{e:%H:%M} ET" if e.date() == n.date() else f"{e:%a %b} {e.day} {e:%H:%M} ET"


def _span(sec) -> str:
    sec = max(0, int(sec))
    if sec < 5400:
        return f"{sec // 60} min"
    if sec < 2 * 86400:
        return f"{sec / 3600:.0f} h"
    return f"{sec / 86400:.0f} days"


def silent_payloads(kind: str, last_t, now) -> dict:
    """The pushes of the PC-silent check: kind first / remind / back."""
    act = "Check it: STOP BOT, START BOT."
    if kind == "back":
        return {"title": "PC reporting again", "body": "Your PC is reporting again" + (f" (last report {since_text(last_t, now)})." if last_t else "."),
                "priority": "default", "tags": "white_check_mark"}
    when = (f"at {since_text(last_t, now)}" if last_t else "")
    if kind == "remind":
        body = (f"Reminder: your PC stopped reporting {when} ({_span(now - last_t)} ago). {act}" if last_t
                else f"Reminder: your PC has not reported for 12+ hours. {act}")
        return {"title": "PC still silent", "body": body, "priority": "high", "tags": "warning"}
    body = f"Your PC stopped reporting {when}. {act}" if last_t else f"Your PC has not reported for 12+ hours. {act}"
    return {"title": "PC stopped reporting", "body": body, "priority": "high", "tags": "rotating_light"}


def silent_step(prev: dict | None, seen_t, now, s: dict | None = None, fetched: bool = True, sent_today=()) -> tuple:
    """One cloud run of the PC-silent check. prev = the stored state ({"last_seen", "out": {"day", "sent", "first_t"}}),
    seen_t = the newest sign of life seen now (heartbeat branch "t", status-feed post time; None = none visible),
    fetched = at least one source answered (False = network trouble: nothing is pushed), sent_today = times of this
    trading day's PC-silent pushes read back from the alert topic (a lost state file never means a repeat).
    -> (new state, [push]). Per outage and trading day: one push, one reminder after pc_silent_remind_after_min, then
    nothing; one "reporting again" when it comes back after a push."""
    s = s or settings()
    now = int(now)
    st = {"last_seen": _d(prev).get("last_seen"), "out": dict(_d(_d(prev).get("out"))) or None}
    if seen_t:
        st["last_seen"] = max(int(seen_t), int(st["last_seen"] or 0))
    if not fetched:
        return st, []
    last = int(st["last_seen"]) if st["last_seen"] else None
    stale = last is None or now - last > int(s["pc_silent_after_min"]) * 60
    out = st["out"]
    if not stale:
        msgs = []
        if out and out.get("sent") and on("pc_silent", s):
            msgs.append({"key": f"pc_back:{out.get('day')}:{last}", **silent_payloads("back", last, now)})
        st["out"] = None
        return st, msgs
    if not silent_window(now) or not on("pc_silent", s):
        return st, []
    day = _et(now).date().isoformat()
    if not out or out.get("day") != day:
        out = {"day": day, "sent": 0, "first_t": None}
    back = sorted(int(t) for t in sent_today or () if t)
    if len(back) > int(out.get("sent") or 0):
        out.update(sent=min(2, len(back)), first_t=back[0])
    msgs = []
    if not out.get("sent"):
        msgs.append({"key": f"pc_silent:{day}:1", **silent_payloads("first", last, now)})
        out.update(sent=1, first_t=now)
    elif out.get("sent") == 1 and now - int(out.get("first_t") or now) >= int(s["pc_silent_remind_after_min"]) * 60:
        msgs.append({"key": f"pc_silent:{day}:2", **silent_payloads("remind", last, now)})
        out["sent"] = 2
    st["out"] = out
    return st, msgs


# ------------------------------------------------------------------------------------------------ instant entry alerts
# Owner 2026-11-18: "I want notifications when we get in a trade in any account." Every routed entry of every bot (LIT /
# Zlarior on each eval, ATLAS on the funded 25K, the extra accounts) already calls engine/push.pc_notify with a "fill"
# payload; pc_notify hands real-account entries to instant_entry in a daemon thread: one ntfy push to the owner's PRIVATE
# alert topic (the same OLYMPUS_HOME/ntfy.json the 15-minute report uses), at once. Never raises, never blocks routing.
# 2026-11-20 (owner: "notifications for trade entries I never got one from today. And results"): ATLAS's 03:45 ET entry and its
# 07:10 ET +$514 close reached no phone. Most likely (unconfirmed: the PC's push logs were not read) they went only to the one
# Olympus phone the PC's public posts listed all night: its push service answering "accepted" made ntfy AND the 15-minute report
# skip their copies. Since then a trade's entry and exit go to BOTH routes (engine/push._pc_send, notify_settings.json trade_routes);
# logs/notify/trade_alerts.jsonl keeps what each route answered.
INSTANT_PATH = os.path.join(ROOT, "logs", "notify", "instant_sent.json")
TRADE_LOG_NAME = "trade_alerts.jsonl"           # next to INSTANT_PATH (engine/push._trade_log)
INSTANT_KEEP_S = 3 * 86400
INSTANT_MATCH_S = 90                # the report's entry time vs the routed one (fill time vs order time)
PT_USD = {"MNQ": 2.0, "MES": 5.0, "NQ": 20.0, "ES": 50.0}
_ID_RX = re.compile(r"\b[A-Z]{4,}[A-Z0-9]*\d{5,}\b")


def mask_ids(s) -> str:
    """Account ids never leave the PC whole: MFFUEVBLDR123456 -> ...3456."""
    return _ID_RX.sub(lambda m: "..." + m.group(0)[-4:], str(s or ""))


def alert_cfg(env=None) -> dict:
    """The private alert topic {"ntfy", "topic"} from OLYMPUS_HOME/ntfy.json (tools/pc_report.load_cfg's file); {} when none."""
    try:
        try:
            from . import nogithub
            d = nogithub.olympus_dir(env)
        except Exception:
            e = os.environ if env is None else env
            d = e.get("OLYMPUS_HOME") or os.path.join(e.get("USERPROFILE") or os.path.expanduser("~"), ".olympus")
        with open(os.path.join(d, "ntfy.json"), encoding="utf-8") as fh:
            c = json.load(fh) or {}
        topic = str(c.get("topic") or "").strip()
        if not topic or c.get("on", True) is False:
            return {}
        return {"ntfy": str(c.get("ntfy") or "https://ntfy.sh").rstrip("/"), "topic": topic}
    except Exception:
        return {}


def _instant_state(path=None) -> dict:
    try:
        with open(path or INSTANT_PATH, encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def instant_sent(entry_t, path=None, now=None, what: str = "entries", acct=None) -> bool:
    """True when an instant push went out for a trade entered within INSTANT_MATCH_S of entry_t (the report skips its own copy).
    what: "entries" / "exits" = the private ntfy topic took it; "app_entries" / "app_exits" = only the phone app took it (since
    2026-11-20 the report still sends its ntfy copy then, engine/push._pc_send). acct: report_acct of a report push (acct_match:
    "" = the report's "lit" row = any LIT account's alert, "acctb" = ATLAS's only, ...). None = any account."""
    t = _f(entry_t)
    if t is None:
        return False
    for k, v in _d(_instant_state(path).get(what)).items():
        if not acct_match(k, acct):
            continue
        if _f(v) is not None and abs(_f(v) - t) <= INSTANT_MATCH_S:
            return True
    return False


def _save_instant(st: dict, path, t_now: float) -> None:
    keys = _d(st.get("keys"))
    cut = t_now - INSTANT_KEEP_S
    out = {"keys": {k: v for k, v in keys.items() if (_f(v) or 0) >= cut}}
    for what in ("entries", "exits", "app_entries", "app_exits", "problems"):
        out[what] = {k: v for k, v in _d(st.get(what)).items() if (_f(keys.get(k)) or t_now) >= cut}
    for k in ("ntfy_days", "closes"):                # the day's ntfy count (the budget) and the recent closes (exit_context)
        if st.get(k):
            out[k] = st[k]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    import threading as _th
    tmp = f"{path}.{os.getpid()}.{_th.get_ident()}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(out, fh)
    os.replace(tmp, path)


def _trade_entry_t(p: dict):
    """The entry time of a trade notice: "fill:<t>" / "out:<t>" keys carry it (an outcome's own "t" is the exit)."""
    m = re.match(r"^(?:fill|out):(\d+)", str(_d(p).get("key") or ""))
    return _f(m.group(1)) if m else (_f(_d(p).get("t")) if _d(p).get("kind") == "fill" else None)


# redteam 2026-11-20: the push threads, the fill audit and the watchdog's fast alarm all read-modify-write instant_sent.json in
# this process: one lock around each read-modify-write (never around a network post), so one thread never drops another's record
_INSTANT_LOCK = threading.RLock()


def _count_ntfy(st: dict, t_now: float) -> None:
    """One more post to ntfy this UTC day (ntfy_days: the budget tools/pc_report keeps room for; 3 days kept)."""
    nd = {k: v for k, v in _d(st.get("ntfy_days")).items() if k >= _utc_day(t_now - 3 * 86400)}
    nd[_utc_day(t_now)] = int(nd.get(_utc_day(t_now)) or 0) + 1
    st["ntfy_days"] = nd


def count_ntfy(now=None, path=None) -> None:
    """One more ntfy post this UTC day from outside the trade path (engine/alert_check's test alert). Never raises."""
    try:
        with _INSTANT_LOCK:
            path = path or INSTANT_PATH
            st = _instant_state(path)
            t_now = time.time() if now is None else float(now)
            _count_ntfy(st, t_now)
            _save_instant(st, path, t_now)
    except Exception:
        pass


def instant_record(p: dict, what: str = "entry", now=None, path=None, app_only: bool = False) -> bool:
    """The phone app got this entry / exit at once (engine/push.pc_notify): recorded so the 15-minute report does not send it to the
    phone app again. app_only=True (engine/push._pc_send since 2026-11-20: ntfy did not take it, refused or no topic in the bot's
    process): "app_entries" / "app_exits", the report still sends its ntfy copy when its own config has a topic (2026-11-20: a
    push service's "accepted" is not proof the phone showed it). app_only=False: "entries" / "exits", the report skips it entirely.
    Never raises."""
    try:
        with _INSTANT_LOCK:
            return _instant_record(p, what, now, path, app_only)
    except Exception:
        return False


def _instant_record(p: dict, what: str, now, path, app_only: bool = False) -> bool:
    try:
        path = path or INSTANT_PATH
        st = _instant_state(path)
        t_now = time.time() if now is None else float(now)
        et_ = _trade_entry_t(p)
        key = str(_d(p).get("key") or f"t:{t_now}")
        st.setdefault("keys", {})[key] = t_now
        if et_ is not None:
            bucket = "entries" if what == "entry" else "exits"
            st.setdefault(f"app_{bucket}" if app_only else bucket, {})[key] = et_
        if what != "entry":
            _note_close(st, p, t_now)
        _save_instant(st, path, t_now)
        return True
    except Exception:
        return False


def real_trade(p: dict) -> bool:
    """An entry / exit notice of a real account: never Paper, Sim, a demo / replay account, or BLITZ (the hidden paper bot)."""
    if not isinstance(p, dict) or p.get("kind") not in ("fill", "outcome"):
        return False
    acct = str(p.get("account") or "").lower()
    if any(w in acct for w in ("paper", "sim", "demo", "playback", "replay", "blitz")):
        return False
    return str(p.get("strategy") or "").upper() != "BLITZ" and not str(p.get("key") or "").endswith(":acctc")


def _real_entry(p: dict) -> bool:
    return isinstance(p, dict) and p.get("kind") == "fill" and real_trade(p)


def _px(x) -> str:
    v = _f(x)
    return "" if v is None else (f"{v:,.2f}".rstrip("0").rstrip(".") if v % 1 else f"{v:,.0f}")


def display_name(p: dict, lane: bool = True) -> str:
    """The owner's name of the account a trade notice is about ("Zlarior 50K", "ATLAS 25K funded", "Rapid EOD 25K"; ids masked).
    Order: the combo's bot label ("ATLAS on Zlarior 50K", engine/combo50k), the PC's names.json (engine/mffu_view.push_name: the
    owner's own names by the last 4 digits), the route's own name ("nm"), else bot + the masked account."""
    p = _d(p)
    if p.get("who"):
        return mask_ids(str(p["who"])[:40])
    acct = mask_ids(p.get("account") or "account")
    body0 = str(p.get("body") or "")
    key = str(p.get("key") or "")
    bot = "ATLAS" if ("ATLAS" in body0 or key.endswith((":acctb", ":acctr")) or "ATLAS" in acct.upper()) else "Zlarior"
    name = acct if (bot.lower() in acct.lower()) else f"{bot} {acct}"
    if p.get("nm"):
        name = str(p["nm"])[:40]
    try:                                    # the owner's own names ("Zlarior 50K", "ATLAS 25K funded"), from the PC's names.json
        from . import mffu_view
        name = mffu_view.push_name(p.get("account")) or name
    except Exception:
        pass
    if lane and key.endswith(":acctr") and "atlas" not in name.lower():
        name = f"{name} (ATLAS)"            # ATLAS's lane on the Rapid EOD (engine/rapid.RapidAtlas): the same account as LIT's lane
    return mask_ids(name)


# the exit's reason in a few words (owner 2026-11-20: "closed LONG +$312 (target)")
EXIT_WORDS = {"TARGET": "target", "STOP": "stop", "BE": "breakeven", "TIME": "time exit", "EOD": "day's end", "TIME SAFETY": "before the close",
              "KILL": "kill switch", "KILL SWITCH": "kill switch", "FLATTEN": "flattened", "LIT PRIORITY": "for a LIT entry",
              "HEDGE": "no-hedge rule", "NO TRADE": "not placed", "CUT": "cut early", "T15": "15-min rule", "TIME STOP": "time stop",
              "BANK": "banked", "BANK (BEST-DAY ROOM)": "banked (best-day room)", "NEWS": "news"}
LIVE_SNAP = os.path.join(ROOT, "data", "pc_report", "live.json")   # tools/pc_report: the PC's last full live view (every 15 min)


def _px2(x) -> str:
    v = _f(x)
    return "" if v is None else f"{v:,.2f}"


def _contract(p: dict) -> str:
    c = str(_d(p).get("contract") or "").upper()
    if c in PT_USD:
        return c
    m = re.search(r"\b(MNQ|MES|NQ|ES)\b", str(_d(p).get("body") or ""))
    return m.group(1) if m else "MNQ"


def _norm(s) -> str:
    return re.sub(r"[^a-z0-9#]+", " ", str(s or "").lower()).strip()


def _snap_cards(L: dict) -> list:
    """[(owner name, last4, card)] of the live view's real accounts: engine/accounts sections + the board's ATLAS card."""
    out = []
    try:
        from . import mffu_view as MV
    except Exception:
        return out
    for a in L.get("accounts") or []:
        if not isinstance(a, dict) or a.get("error") or a.get("source") in ("cloud", "pc_blitz") or a.get("id") == "acct_c":
            continue
        ev = _d(a.get("eval"))
        card = {"balance": _f(ev.get("balance")), "today": _f(ev.get("today")) if ev else _f(_d(a.get("pnl")).get("today")),
                "to_pass": _f(ev.get("to_target")) if a.get("kind") != "funded" else None, "kind": a.get("kind")}
        if card["today"] is None:
            card["today"] = _f(_d(_d(a.get("pnl")).get("today")).get("usd")) if isinstance(_d(a.get("pnl")).get("today"), dict) else None
        nm = MV.owner_name(a.get("id"), a.get("name"), a.get("plan"), a.get("kind"))
        out.append((nm, MV.last4(a.get("broker_account")), card))
    c = _d(_d(L.get("board")).get("atlas"))
    if c and not c.get("error") and _f(c.get("balance")) is not None:
        funded = str(c.get("status") or "").lower() == "funded" or str(c.get("stage") or "").lower() == "funded"
        f = _d(c.get("funded"))
        out.append((MV.owner_name("atlas", "ATLAS", c.get("plan") or "Builder 25K", "funded" if funded else "eval"), MV.last4(c.get("broker")),
                    {"balance": _f(c.get("balance")), "today": next((_f(c.get(k)) for k in ("today_pnl", "today", "day_pnl") if _f(c.get(k)) is not None), None),
                     "to_pass": None if funded else _f(c.get("to_target")), "kind": "funded" if funded else "eval",
                     "payout": _f(f.get("max_request")) if f else None}))
    return out


def exit_context(p: dict, path: str | None = None, closes=None) -> dict:
    """{"day", "balance", "to_pass" / "payout"} of the account after this exit, for 'today +$312, balance $49,505, $3,495 to pass'.
    The route's own numbers win (payload "day_usd", "balance", "to_pass", "to_payout"); else the PC's last live view
    (data/pc_report/live.json, every 15 min) + the closes the phone got since that view (this one included: the instant state's
    "closes"). {} when nothing is known (the alert then says only the trade). Never raises."""
    p = _d(p)
    out = {}
    try:
        for a, b in (("day_usd", "day"), ("balance", "balance"), ("to_pass", "to_pass"), ("to_payout", "to_payout")):
            if _f(p.get(a)) is not None:
                out[b] = _f(p[a])
        if "balance" in out and ("day" in out or "to_pass" in out):
            return out
        try:
            with open(path or LIVE_SNAP, encoding="utf-8") as fh:
                L = json.load(fh)
        except Exception:
            return out
        L = _d(L)
        name = _norm(display_name(dict(p, who=None), lane=False))
        l4 = None
        try:
            from . import mffu_view as MV
            l4 = MV.last4(p.get("account"))
        except Exception:
            pass
        hit = None
        for nm, cl4, card in _snap_cards(L):
            if (l4 and cl4 and l4 == cl4) or (_norm(nm) and _norm(nm) == name):
                hit = card
                break
        if hit is None:
            return out
        snap_t = _f(L.get("t")) or 0.0
        exit_t = _f(p.get("t")) or time.time()
        try:
            from .live import trading_day
        except Exception:
            trading_day = lambda t: _et(t).date().isoformat()
        same_day = trading_day(snap_t) == trading_day(exit_t) if snap_t else False
        usd = _f(p.get("usd")) or 0.0
        later = [c for c in (closes if closes is not None else _d(_instant_state()).get("closes") or [])
                 if isinstance(c, dict) and _norm(c.get("nm")) == name and (_f(c.get("t")) or 0) > snap_t and c.get("key") != p.get("key")
                 and trading_day(_f(c.get("t"))) == trading_day(exit_t)]
        add = (usd if exit_t > snap_t else 0.0) + sum(_f(c.get("usd")) or 0.0 for c in later)
        if hit.get("balance") is not None and "balance" not in out:
            out["balance"] = hit["balance"] + add
        if "day" not in out:
            out["day"] = ((hit.get("today") or 0.0) if same_day else 0.0) + add
        if hit.get("to_pass") is not None and "to_pass" not in out:
            out["to_pass"] = max(0.0, hit["to_pass"] - add)
        if hit.get("payout") and "to_payout" not in out:
            out["payout_ready"] = hit["payout"]
    except Exception:
        pass
    return out


def exit_message(p: dict, now=None, s: dict | None = None, ctx: dict | None = None) -> dict:
    """{title, body, priority, tags} for one exit (owner 2026-11-20): 'Zlarior 50K: closed LONG +$312 (target)' /
    'today +$312, balance $49,505, $3,495 to pass · +1.6R · 10:58 AM ET.' (the phone app's notice replaces the entry's)."""
    p = _d(p)
    side = str(p.get("side") or "").upper()
    usd = _f(p.get("usd"))
    reason = str(p.get("exit") or "").upper()
    why = EXIT_WORDS.get(reason, reason.lower())
    title = (f"{display_name(p)}: closed {(side + ' ') if side in ('LONG', 'SHORT') else ''}{signed(usd) if usd is not None else ''}"
             + (f" ({why})" if why else "")).replace("  ", " ")
    c = exit_context(p) if ctx is None else ctx
    acct = []
    if _f(c.get("day")) is not None:
        acct.append(f"today {signed(c['day'])}")
    if _f(c.get("balance")) is not None:
        acct.append(f"balance {money(c['balance'])}")
    if _f(c.get("to_pass")) is not None:
        acct.append("target reached" if c["to_pass"] <= 0.5 else f"{money(c['to_pass'])} to pass")
    elif _f(c.get("to_payout")) is not None:
        acct.append("payout ready" if c["to_payout"] <= 0.5 else f"{money(c['to_payout'])} to payout")
    elif _f(c.get("payout_ready")):
        acct.append(f"payout ready {money(c['payout_ready'])}")
    r = _f(p.get("R") if p.get("R") is not None else p.get("r"))
    q = _f(p.get("qty"))
    tail = [f"{r:+.1f}R" if r is not None else "", f"{int(q)} {_contract(p)}" if q else "",
            _et(p["t"]).strftime("%I:%M %p ET").lstrip("0") if _f(p.get("t")) else ""]
    body = ", ".join(acct)
    body = " · ".join(x for x in [body, *tail] if x) + "."
    s = s or settings()
    night = quiet(now if now is not None else time.time(), s) and not rings("trade_closed", s)
    return {"title": mask_ids(title), "body": mask_ids(body), "priority": "low" if night else "default",
            "tags": "white_check_mark" if (usd or 0) > 0 else ("heavy_minus_sign" if usd is not None and abs(usd) < 0.5 else "x")}


def entry_message(p: dict, now=None, s: dict | None = None) -> dict:
    """{title, body, priority, tags} for one routed / filled entry (owner 2026-11-20):
    'Zlarior 50K: LONG 4 MNQ @ 21,034.25' / 'stop 21,012.00 (-$178), target 21,090.50 (+$450) · 10:31 AM ET.'"""
    p = _d(p)
    side = str(p.get("side") or "").upper() or ("LONG" if "LONG" in str(p.get("title") or "") else "SHORT")
    name = display_name(p)
    contract = _contract(p)
    q, e, st, tg = _f(p.get("qty")), _f(p.get("entry")), _f(p.get("stop")), _f(p.get("target"))
    usd_pt = PT_USD.get(contract, 2.0)
    risk = abs(e - st) * q * usd_pt if None not in (q, e, st) else None
    gain = abs(tg - e) * q * usd_pt if None not in (q, e, tg) else None
    title = f"{name}: {side}" + (f" {int(q)}" if q is not None else "") + f" {contract}" + (f" @ {_px2(e)}" if e is not None else "")
    parts = []
    if st is not None:
        parts.append(f"stop {_px2(st)}" + (f" (-${risk:,.0f})" if risk is not None else ""))
    if tg is not None:
        parts.append(f"target {_px2(tg)}" + (f" (+${gain:,.0f})" if gain is not None else ""))
    body = ", ".join(parts)
    when = _f(p.get("t"))
    if when:
        body = " · ".join(x for x in (body, _et(when).strftime("%I:%M %p ET").lstrip("0")) if x)
    s = s or settings()
    night = quiet(now if now is not None else time.time(), s) and not rings("trade_opened", s)
    return {"title": mask_ids(title), "body": mask_ids((body or "Entered") + "."), "priority": "low" if night else "high",
            "tags": "chart_with_upwards_trend" if side == "LONG" else "chart_with_downwards_trend", "risk": risk, "gain": gain}


def _post(base, topic, msg, timeout=8) -> bool:
    import urllib.request
    h = {"Content-Type": "text/plain; charset=utf-8", "Title": msg["title"].encode("ascii", "replace").decode("ascii"),
         "Priority": msg["priority"], "Tags": msg["tags"]}
    req = urllib.request.Request(f"{base}/{topic}", data=msg["body"].encode("utf-8"), headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return 200 <= r.status < 300


# ------------------------------------------------------------------------------------------------ instant problems
# (night-nqlive 2026-11-20) The bot's own fast alarm (engine/fast_alarm.py: armed but not polling / feed stale in the entry hours,
# within 2 minutes) and a MISSED TRADE (engine/fill_audit: the bot's model took an entry the bot did not route, with its reason)
# go to the private ntfy alert topic at once, type "problems" (IMPORTANT, rings in quiet hours). The 15-minute report then skips
# its own copy of the same problem (apply -> problem_dup): one alert, one phone.
PROBLEM_DUP_S = 20 * 60              # a report "cond:<code>" / "back:<code>" within this of the fast alarm's own = the same problem


def problem_message(p: dict, now=None, s: dict | None = None) -> dict:
    """A problem push's words. p["soft"] (engine/fill_audit.rule_hold: an entry the bot's own rule held back on purpose) = no
    sound in quiet hours and normal priority by day; every other problem is high and rings in quiet hours ("problems" in
    ring_in_quiet_hours, the default)."""
    s = s or settings()
    soft = bool(p.get("soft"))
    night = quiet(now if now is not None else time.time(), s) and (soft or not rings("problems", s))
    return {"title": mask_ids(str(p.get("title") or "Problem"))[:120], "body": mask_ids(str(p.get("body") or ""))[:600],
            "priority": "low" if night else ("default" if soft else "high"), "tags": str(p.get("tags") or "rotating_light")}


def instant_problem(p: dict, now=None, path=None, cfg=None, poster=None) -> str:
    """Send one problem push now. p: {"key" (unique, sent once), "title", "body", "code" ("missed" | "slip" | "bot_down" |
    "feed_stale"), "cond" (the report's condition code it stands for, optional), "back" (True for a "back to normal"),
    "entry_t" (a trade's entry time, optional), "bot" ("lit" default | "atlas")}. Returns why (tests / logs). Never raises."""
    try:
        s = settings()
        if not on("problems", s):
            return "problems is off"
        cfg = cfg if cfg is not None else alert_cfg()
        if not cfg.get("topic"):
            return "no private alert topic on this PC"
        path = path or INSTANT_PATH
        st = _instant_state(path)
        keys, probs = _d(st.get("keys")), _d(st.get("problems"))
        key = str(p.get("key") or "")
        if not key:
            return "no key"
        if key in keys:
            return "already sent"
        ok = (poster or _post)(cfg["ntfy"], cfg["topic"], problem_message(p, now=now, s=s))
        if not ok:
            return "ntfy did not take it (the 15-minute report sends it instead)"
        t_now = time.time() if now is None else float(now)
        with _INSTANT_LOCK:
            st = _instant_state(path)                   # re-read: another thread may have written meanwhile
            keys, probs = _d(st.get("keys")), _d(st.get("problems"))
            keys[key] = t_now
            probs[key] = {"t": t_now, "code": p.get("code"), "cond": p.get("cond"), "back": bool(p.get("back")),
                          "entry_t": _f(p.get("entry_t")), "bot": str(p.get("bot") or "lit")}
            st.update(keys=keys, problems=probs)
            _count_ntfy(st, t_now)                      # redteam 2026-11-20: a problem push uses ntfy's daily room too
            _save_instant(st, path, t_now)
        return "sent"
    except Exception as e:
        return f"failed: {e.__class__.__name__}"


def problem_dup(m: dict, now=None, path=None) -> bool:
    """A 15-minute report push that repeats a problem the fast alarm already sent: "watch:<bot>:<entry_t>:missed|slip" (same
    entry, same code), "cond:<code>:..." / "back:<code>:..." (same condition within PROBLEM_DUP_S)."""
    try:
        k = str(_d(m).get("key") or "")
        P = _d(_instant_state(path).get("problems")).values()
        t_now = time.time() if now is None else float(now)
        parts = k.split(":")
        if k.startswith("watch:") and len(parts) >= 4:
            et_, code = _f(parts[2]), parts[3]
            return et_ is not None and any(isinstance(v, dict) and v.get("code") == code and str(v.get("bot") or "lit") == parts[1]
                                           and _f(v.get("entry_t")) is not None
                                           and abs(_f(v.get("entry_t")) - et_) <= INSTANT_MATCH_S for v in P)
        if k.startswith(("cond:", "back:")) and len(parts) >= 2:
            back = k.startswith("back:")
            return any(isinstance(v, dict) and v.get("cond") == parts[1] and bool(v.get("back")) == back
                       and abs(t_now - (_f(v.get("t")) or 0)) <= PROBLEM_DUP_S for v in P)
    except Exception:
        return False
    return False



def _utc_day(t) -> str:
    return dt.datetime.fromtimestamp(int(t), dt.timezone.utc).strftime("%Y-%m-%d")


def ntfy_today(now=None, path=None) -> int:
    """How many instant trade alerts this PC posted to ntfy this UTC day (ntfy.sh's free cap is per IP and UTC day: the 15-minute
    report's chart and extra status posts count these and stop early, so the status posts never crowd a trade alert out)."""
    try:
        return int(_d(_instant_state(path).get("ntfy_days")).get(_utc_day(time.time() if now is None else now)) or 0)
    except Exception:
        return 0


def _instant_send(p: dict, what: str, now=None, path=None, cfg=None, poster=None) -> str:
    """One trade alert (an entry or an exit) to the private ntfy topic, at once. One per key, ever (fill:<t>[:acct] / out:<t>[:acct]).
    Never raises."""
    try:
        if not real_trade(p) or p.get("kind") != ("fill" if what == "entry" else "outcome"):
            return "not a real-account entry" if what == "entry" else "not a real-account exit"
        s = settings()
        kind = "trade_opened" if what == "entry" else "trade_closed"
        if not on(kind, s):
            return f"{kind} is off"
        cfg = cfg if cfg is not None else alert_cfg()
        if not cfg.get("topic"):
            return "no private alert topic on this PC"
        path = path or INSTANT_PATH
        st = _instant_state(path)
        keys = _d(st.get("keys"))
        key = str(p.get("key") or "")
        if key and key in keys:
            return "already sent"
        msg = entry_message(p, now=now, s=s) if what == "entry" else exit_message(p, now=now, s=s)
        ok = (poster or _post)(cfg["ntfy"], cfg["topic"], msg)
        if not ok:
            return "ntfy did not take it (the 15-minute report sends it instead)"
        t_now = time.time() if now is None else float(now)
        with _INSTANT_LOCK:
            st = _instant_state(path)              # re-read: another thread may have written meanwhile
            keys = _d(st.get("keys"))
            keys[key or f"t:{t_now}"] = t_now
            et_ = _trade_entry_t(p)
            if et_ is not None:
                st.setdefault("entries" if what == "entry" else "exits", {})[key or f"t:{t_now}"] = et_
            st.update(keys=keys)
            _count_ntfy(st, t_now)
            if what == "exit":
                _note_close(st, p, t_now)
            _save_instant(st, path, t_now)
        return "sent"
    except Exception as e:
        return f"failed: {e.__class__.__name__}"


def _note_close(st: dict, p: dict, t_now: float) -> None:
    """Remember one close the phone got (name, exit time, $): the next exit's 'today' / balance add it until the next live view."""
    try:
        cl = [c for c in st.get("closes") or [] if isinstance(c, dict) and (_f(c.get("t")) or 0) >= t_now - 2 * 86400]
        if not any(c.get("key") == p.get("key") for c in cl):
            cl.append({"key": str(p.get("key") or ""), "nm": display_name(dict(p, who=None), lane=False), "t": _f(p.get("t")) or t_now,
                       "usd": _f(p.get("usd")) or 0.0})
        st["closes"] = cl[-40:]
    except Exception:
        pass


def instant_entry(p: dict, now=None, path=None, cfg=None, poster=None) -> str:
    """Send one entry push now (daemon thread from engine/push.pc_notify). Returns why (for tests / logs). Never raises."""
    return _instant_send(p, "entry", now=now, path=path, cfg=cfg, poster=poster)


def instant_exit(p: dict, now=None, path=None, cfg=None, poster=None) -> str:
    """Send one exit push now (owner 2026-11-20: "exactly when a trade is taken and closed, results of it"): 'Zlarior 50K: closed
    LONG +$312 (target)' / 'today +$312, balance $49,505, $3,495 to pass'. The 15-minute report then skips its own close of
    that trade (apply: instant_sent(..., what="exits")). Never raises."""
    return _instant_send(p, "exit", now=now, path=path, cfg=cfg, poster=poster)
