"""Phone alerts, short and $-first (owner 2026-11-17: "better notifications on my phone"; not spammy). Stdlib only: the PC
report (tools/pc_report.py + tools/pc_guard.py, every 15 min -> your private ntfy topic) and the cloud's PC-silent check
(tools/pc_silent_check.py, a cloud-monitor step) both use it. Read-only: nothing here places, changes or arms anything.

One settings file: notify_settings.json (repo root; a missing or broken file = DEFAULTS, a missing key = its default).
  alerts               per type on / off: trade_opened, trade_closed, eval_milestones (25/50/75 %), account_status (PASSED,
                       FAILED, LOCKED, LOST, target reached, payout READY), room_low, daily_summary, pc_silent,
                       problems (bot down, FEED STALE, NinjaTrader closed, fill check, trade watch), other (roll, quiet bot, ...).
                       Default (owner 2026-11-18, "important only"): ON = trade_closed, account_status, daily_summary, pc_silent;
                       the rest OFF
  quiet_hours          ET; inside them trade pushes and ordinary ones arrive without sound (ntfy priority "low"), the guard's
                       summaries / milestones wait for the end; ring_in_quiet_hours kinds keep their sound
  milestones_pct       eval progress pushes (% of the profit target made), once per level per eval
  room_low_used_pct    "room getting low" pushes (% of the max loss used), once per level per eval
  daily_summary_at     the day summary time (ET), up to the 17:00 CME break
  pc_silent_after_min  the cloud says "Your PC stopped reporting" when neither its heartbeat nor its status feed is newer
  pc_silent_remind_after_min   one reminder after this; at most 2 pushes per outage per trading day, never every run

Messages (examples):
  Zlarior 50K SHORT opened | risk $368 | target +$1,432
  Zlarior 50K closed +$605 | day +$605 | room $1,750
  Zlarior 50K: 50% of the target made ($1,500 of $3,000)
  ATLAS 25K: room getting low, $250 left of $1,000
  Day Mon Nov 16: +$310                     (each account: $ today, $ to pass, room; tomorrow's big US news)
  PC stopped reporting                      Your PC stopped reporting at 09:14 ET. Check it: STOP BOT, START BOT.
Tests: python -X utf8 -m tests.test_notify
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import re
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_PATH = os.path.join(ROOT, "notify_settings.json")
TYPES = ("trade_opened", "trade_closed", "eval_milestones", "account_status", "room_low", "daily_summary", "pc_silent", "problems",
         "other")
# owner 2026-11-18: "important only" = trade results, PASSED / FAILED / LOCKED, payout ready, PC silent, the daily summary.
# Everything else is OFF by default (one line in notify_settings.json turns a type back on).
IMPORTANT = ("trade_closed", "account_status", "daily_summary", "pc_silent", "problems")   # problems = emergencies (bot down, NinjaTrader closed)
DEFAULTS = {
    "alerts": {k: k in IMPORTANT for k in TYPES},
    "quiet_hours": {"from": "23:00", "to": "07:00"},
    "ring_in_quiet_hours": ["pc_silent", "account_status", "room_low", "problems"],
    "milestones_pct": [25, 50, 75, 100],
    "room_low_used_pct": [50, 75],
    "daily_summary_at": "16:15",
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
    for k in ("milestones_pct", "room_low_used_pct"):
        if isinstance(raw.get(k), list):
            vals = sorted({int(x) for x in raw[k] if isinstance(x, (int, float)) and 0 < x <= 100})
            out[k] = vals
    if isinstance(raw.get("daily_summary_at"), str) and hm_min(raw["daily_summary_at"], -1) >= 0:
        out["daily_summary_at"] = raw["daily_summary_at"]
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
    if k.startswith(("cond:", "back:", "fill:", "watch:")):
        return "problems"
    if k.startswith(("pc_silent:", "pc_back:")):
        return "pc_silent"
    return "other"


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
