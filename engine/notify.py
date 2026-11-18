"""Phone alerts, short and $-first (owner 2026-11-17: "better notifications on my phone"; not spammy). Stdlib only: the PC
report (tools/pc_report.py + tools/pc_guard.py, every 15 min -> your private ntfy topic) and the cloud's PC-silent check
(tools/pc_silent_check.py, a cloud-monitor step) both use it. Read-only: nothing here places, changes or arms anything.

One settings file: notify_settings.json (repo root; a missing or broken file = DEFAULTS, a missing key = its default).
  alerts               per type on / off: trade_opened, trade_closed, eval_milestones (25/50/75 %), account_status (PASSED,
                       FAILED, LOCKED, LOST, target reached, payout READY), room_low, daily_summary, morning_brief, pc_silent,
                       problems (bot down, FEED STALE, NinjaTrader closed, fill check, trade watch), other (roll, quiet bot, ...).
                       Default (owner 2026-11-18, "important only" + every entry): ON = trade_opened, trade_closed,
                       account_status, daily_summary, morning_brief, pc_silent, problems; the rest OFF. Entries go out the
                       moment the bot routes them (instant_entry, via engine/push.pc_notify; the 15-minute report then skips
                       the same entry), closes with the next report ($, day, room).
  quiet_hours          ET; inside them trade pushes and ordinary ones arrive without sound (ntfy priority "low"), the guard's
                       summaries / milestones wait for the end; ring_in_quiet_hours kinds keep their sound
  milestones_pct       eval progress pushes (% of the profit target made), once per level per eval
  room_low_used_pct    "room getting low" pushes (% of the max loss used), once per level per eval
  daily_summary_at     the day summary time (ET), up to the 17:00 CME break
  morning_brief_at     the morning brief time (ET, default 07:30, up to 09:30; tools/morning_brief.py): 4 lines = PC ok?, each
                       account ($ / to pass / to payout), overnight trades + today's entry hours + big news, edge light + needs you
  pc_silent_after_min  the cloud says "Your PC stopped reporting" when neither its heartbeat nor its status feed is newer
  pc_silent_remind_after_min   one reminder after this; at most 2 pushes per outage per trading day, never every run

Messages (examples):
  Zlarior 50K SHORT opened | risk $368 | target +$1,432
  Zlarior 50K closed +$605 | day +$605 | room $1,750
  Zlarior 50K: 50% of the target made ($1,500 of $3,000)
  ATLAS 25K: room getting low, $250 left of $1,000
  Day Mon Nov 16: +$310                     (each account: $ today, $ to pass, room; tomorrow's big US news)
  ZEUS - Wed Nov 18 - PC ok                 (07:30 ET: accounts, overnight, today's hours + news, edge, needs you)
  PC stopped reporting                      Your PC stopped reporting at 09:14 ET. Check it: STOP BOT, START BOT.
Tests: python -X utf8 -m tests.test_notify
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import re
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
DEFAULTS = {
    "alerts": {k: k in IMPORTANT for k in TYPES},
    "quiet_hours": {"from": "23:00", "to": "07:00"},
    "ring_in_quiet_hours": ["pc_silent", "account_status", "room_low", "problems"],
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
    if k.startswith(("cond:", "back:", "fill:", "watch:", "risk:")):    # risk:throttle: engine/msg_throttle runaway orders
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
        if kind == "trade_opened" and instant_sent(m.get("entry_t")):
            continue                                # the phone already got this entry the moment it was routed
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
INSTANT_PATH = os.path.join(ROOT, "logs", "notify", "instant_sent.json")
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


def instant_sent(entry_t, path=None, now=None) -> bool:
    """True when an instant entry push went out for a trade entered within INSTANT_MATCH_S of entry_t (the report skips it)."""
    t = _f(entry_t)
    if t is None:
        return False
    for v in _d(_instant_state(path).get("entries")).values():
        if _f(v) is not None and abs(_f(v) - t) <= INSTANT_MATCH_S:
            return True
    return False


def _real_entry(p: dict) -> bool:
    if not isinstance(p, dict) or p.get("kind") != "fill":
        return False
    acct = str(p.get("account") or "").lower()
    if any(w in acct for w in ("paper", "sim", "demo", "playback", "replay")):
        return False
    return str(p.get("strategy") or "").upper() != "BLITZ"        # BLITZ is the hidden paper bot


def _px(x) -> str:
    v = _f(x)
    return "" if v is None else (f"{v:,.2f}".rstrip("0").rstrip(".") if v % 1 else f"{v:,.0f}")


def entry_message(p: dict, now=None, s: dict | None = None) -> dict:
    """{title, body, priority, tags} for one routed entry: 'Zlarior 50K: LONG opened | risk $368 | target +$1,432'."""
    p = _d(p)
    side = str(p.get("side") or "").upper() or ("LONG" if "LONG" in str(p.get("title") or "") else "SHORT")
    acct = mask_ids(p.get("account") or "account")
    body0 = str(p.get("body") or "")
    bot = "ATLAS" if ("ATLAS" in body0 or str(p.get("key") or "").endswith(":acctb") or "ATLAS" in acct.upper()) else "Zlarior"
    name = acct if (bot.lower() in acct.lower()) else f"{bot} {acct}"
    m = re.search(r"\b(MNQ|MES|NQ|ES)\b", body0)
    contract = m.group(1) if m else "MNQ"
    q, e, st, tg = _f(p.get("qty")), _f(p.get("entry")), _f(p.get("stop")), _f(p.get("target"))
    usd_pt = PT_USD.get(contract, 2.0)
    risk = abs(e - st) * q * usd_pt if None not in (q, e, st) else None
    gain = abs(tg - e) * q * usd_pt if None not in (q, e, tg) else None
    title = f"{name}: {side} opened" + (f" | risk ${risk:,.0f}" if risk else "") + (f" | target +${gain:,.0f}" if gain else "")
    parts = [f"{int(q) if q is not None else ''} {contract}".strip() + (f" at {_px(e)}" if e is not None else "") + "."]
    if st is not None or tg is not None:
        parts.append(" ".join(x for x in (f"Stop {_px(st)}," if st is not None else "", f"target {_px(tg)}." if tg is not None else "") if x).rstrip(","))
    when = _f(p.get("t"))
    if when:
        parts.append(_et(when).strftime("%I:%M %p ET").lstrip("0") + ".")
    s = s or settings()
    night = quiet(now if now is not None else time.time(), s)
    return {"title": mask_ids(title), "body": mask_ids(" ".join(x for x in parts if x)), "priority": "low" if night else "high",
            "tags": "chart_with_upwards_trend" if side == "LONG" else "chart_with_downwards_trend"}


def _post(base, topic, msg, timeout=8) -> bool:
    import urllib.request
    h = {"Content-Type": "text/plain; charset=utf-8", "Title": msg["title"].encode("ascii", "replace").decode("ascii"),
         "Priority": msg["priority"], "Tags": msg["tags"]}
    req = urllib.request.Request(f"{base}/{topic}", data=msg["body"].encode("utf-8"), headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return 200 <= r.status < 300


def instant_entry(p: dict, now=None, path=None, cfg=None, poster=None) -> str:
    """Send one entry push now (daemon thread from engine/push.pc_notify). Returns why (for tests / logs). Never raises."""
    try:
        if not _real_entry(p):
            return "not a real-account entry"
        s = settings()
        if not on("trade_opened", s):
            return "trade_opened is off"
        cfg = cfg if cfg is not None else alert_cfg()
        if not cfg.get("topic"):
            return "no private alert topic on this PC"
        path = path or INSTANT_PATH
        st = _instant_state(path)
        keys, ents = _d(st.get("keys")), _d(st.get("entries"))
        key = str(p.get("key") or "")
        if key and key in keys:
            return "already sent"
        msg = entry_message(p, now=now, s=s)
        ok = (poster or _post)(cfg["ntfy"], cfg["topic"], msg)
        if not ok:
            return "ntfy did not take it (the 15-minute report sends it instead)"
        t_now = time.time() if now is None else float(now)
        keys[key or f"t:{t_now}"] = t_now
        if _f(p.get("t")) is not None:
            ents[key or f"t:{t_now}"] = _f(p.get("t"))
        cut = t_now - INSTANT_KEEP_S
        st = {"keys": {k: v for k, v in keys.items() if (_f(v) or 0) >= cut},
              "entries": {k: v for k, v in ents.items() if (_f(keys.get(k)) or t_now) >= cut}}
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(st, fh)
        os.replace(tmp, path)
        return "sent"
    except Exception as e:
        return f"failed: {e.__class__.__name__}"
