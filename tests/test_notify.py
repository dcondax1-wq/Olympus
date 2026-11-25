"""Phone alerts v2 (engine/notify.py, notify_settings.json, tools/pc_silent_check.py, the $-first texts of tools/pc_report.py /
tools/pc_guard.py). Offline: the ntfy GET / POST are stubs, the heartbeat is a dict, nothing is ever sent.

  a. settings: defaults without a file, junk ignored, the repo file loads; per-type off drops; quiet hours = no sound except
     the ring kinds; push keys map to their types
  b. eval numbers: progress toward the target; milestones 25 / 50 / 75 / 100 once each (only the highest new level)
  c. tomorrow's news (hub, then the calendar file; Friday -> Monday)
  d. PC silent state machine: one push, one reminder after 2 h, nothing more that day, again the next trading day, "reporting
     again" when back; nothing outside market hours or when no source answered; a lost state file never repeats a push
  e. the cloud step end to end (stub ntfy): private topic from LE_NTFY_TOPIC (never printed), fallback to the status topic,
     only the PC's "le-live" posts count, a failed POST is retried, state file written
  f. through pc_report: a type switched off sends nothing, a 03:10 trade arrives without sound
  g. the workflow: the step runs before the install and the monitor, never fails the job, reads the secret, the settings file
     is in the sparse checkout
  h. the 07:30 ET morning brief (tools/morning_brief.py): 4 lines, $ first, no account id; once a day through pc_guard (a
     restart = state.json read back: no repeat); weekends / CME closures / outside 07:30-09:30 nothing; "important only" keeps
     it, the switch drops it; the ntfy POST is a stub (ASCII title); ONE Board event a day, only from the real report

  python -X utf8 -m tests.test_notify
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import sys
import tempfile
from zoneinfo import ZoneInfo

os.environ["LE_PR_NO_NET"] = "1"          # belt and braces: the real network helpers refuse; every test call uses stubs

from engine import notify as N  # noqa: E402
from tools import pc_silent_check as C  # noqa: E402

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(info)[:600]})" if info and not cond else ""))
    return bool(cond)


def at(y, m, d, hh=0, mm=0):
    return int(dt.datetime(y, m, d, hh, mm, tzinfo=ET).timestamp())


S = N.merge({})                            # the defaults, independent of the repo file
ALL = N.merge({"alerts": {k: True for k in N.TYPES}})   # every type on: the quiet-hours / switch checks


# ============================================================================================== a settings
def settings():
    tmp = tempfile.mkdtemp()
    try:
        s = N.settings(os.path.join(tmp, "none.json"))
        imp = {k for k, v in s["alerts"].items() if v}
        check("a. no file: the defaults ('important only': trade results, pass/fail/locked/payout, daily summary, PC silent, problems; "
              "quiet 23:00-07:00, summary 16:15, silent after 20 min, reminder 2 h)",
              imp == {"trade_opened", "trade_closed", "account_status", "room_low", "daily_summary", "morning_brief", "pc_silent", "problems",
                      "setup_progress"} and s["quiet_hours"] == {"from": "23:00", "to": "07:00"}
              and s["daily_summary_at"] == "16:15" and s["morning_brief_at"] == "07:30"
              and s["pc_silent_after_min"] == 20 and s["pc_silent_remind_after_min"] == 120, s)
        p = os.path.join(tmp, "s.json")
        with open(p, "w") as fh:
            fh.write("{broken")
        check("a. a broken file: the defaults", N.settings(p) == S)
        j = N.merge({"alerts": {"trade_opened": False, "bogus": False, "pc_silent": "no"}, "quiet_hours": {"from": "25:00", "to": "06:00"},
                     "milestones_pct": [50, "x", 200, 100], "pc_silent_after_min": 1, "daily_summary_at": "16:30"})
        check("a. junk ignored, good values kept, limits clamped", j["alerts"]["trade_opened"] is False and "bogus" not in j["alerts"]
              and j["alerts"]["pc_silent"] is True and N.merge({"alerts": {"problems": True}})["alerts"]["problems"] is True and j["quiet_hours"] == {"from": "23:00", "to": "06:00"} and j["milestones_pct"] == [50, 100]
              and j["pc_silent_after_min"] == 5 and j["daily_summary_at"] == "16:30", j)
        repo = N.settings(N.SETTINGS_PATH)
        raw = json.load(open(N.SETTINGS_PATH, encoding="utf-8"))
        check("a. the repo's notify_settings.json loads, names every type, 'important only' on (owner 2026-11-18), the asked defaults",
              set(raw["alerts"]) == set(N.TYPES) and {k for k, v in repo["alerts"].items() if v} == set(N.IMPORTANT)
              and repo["alerts"] == N.DEFAULTS["alerts"] and repo["milestones_pct"] == [25, 50, 75, 100]
              and repo["pc_silent_after_min"] == 20 and repo["pc_silent_remind_after_min"] == 120 and repo["daily_summary_at"] == "16:15"
              and repo["morning_brief_at"] == "07:30" and raw["alerts"]["morning_brief"] is True, repo)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    kinds = {k: N.kind_of(k) for k in ("open:lit:1", "close:atlas:2", "guard:goal:lit:x:50", "guard:dd:lit:x:75", "guard:dll:lit:d",
                                        "guard:day:2026-11-16", "cond:bot_down:1", "fill:lit:1:size", "guard:roll:x", "guard:quiet:lit:d",
                                        "guard:goal:lit:2026-11-02:100", "life:passed:atlas:a", "life:locked:atlas:a",
                                        "life:payout_ready:x:f50:abc:2026-11-13", "pc_silent:2026-11-16:1", "guard:brief:2026-11-18")}
    check("a. push keys -> types", list(kinds.values()) == ["trade_opened", "trade_closed", "eval_milestones", "room_low", "room_low",
                                                             "daily_summary", "problems", "problems", "other", "account_status",
                                                             "account_status", "account_status", "account_status", "account_status",
                                                             "pc_silent", "morning_brief"], kinds)
    every = [{"key": k, "priority": "default"} for k in kinds]
    kept = [m["key"] for m in N.apply(every, at(2026, 11, 17, 10, 0), N.merge({}))]
    check("a. 'important only' defaults: entries (owner 2026-11-18 evening), trade results, target reached, PASSED / LOCKED / payout READY, the day "
          "summary, the morning brief, PC silent + problems (bot down, fill size), a quiet eval (MFFU's 7-day rule, account_status since "
          "2026-11-20: as 'other' it was dropped), room low (daily loss / drawdown, ON since night-notify 2026-11-22) are kept; 25-75 %, other are dropped",
          kept == ["open:lit:1", "close:atlas:2", "guard:dd:lit:x:75", "guard:dll:lit:d", "guard:day:2026-11-16", "cond:bot_down:1", "fill:lit:1:size", "guard:quiet:lit:d",
                   "guard:goal:lit:2026-11-02:100", "life:passed:atlas:a",
                   "life:locked:atlas:a", "life:payout_ready:x:f50:abc:2026-11-13", "pc_silent:2026-11-16:1", "guard:brief:2026-11-18"], kept)
    night, day = at(2026, 11, 17, 3, 10), at(2026, 11, 17, 10, 0)
    check("a. quiet hours over midnight: 03:10 and 23:30 quiet, 07:00 and 10:00 not", N.quiet(night, S) and N.quiet(at(2026, 11, 17, 23, 30), S)
          and not N.quiet(at(2026, 11, 17, 7, 0), S) and not N.quiet(day, S))
    msgs = [{"key": "open:lit:1", "priority": "high"}, {"key": "cond:bot_down:1", "priority": "high"}, {"key": "guard:dd:lit:x:75", "priority": "high"},
            {"key": "guard:roll:late", "priority": "high"}, {"key": "guard:quiet:lit:d", "priority": "default"}, {"key": "guard:ready", "priority": "low", "night": True}]
    q = {m["key"]: m["priority"] for m in N.apply(msgs, night, ALL)}
    check("a. 03:10: the trade and an ordinary push lose their sound (they still show); problems, room low, account status (a quiet "
          "eval; tools/pc_guard never sends it in quiet hours) and a high 'other' keep it",
          q == {"open:lit:1": "low", "cond:bot_down:1": "high", "guard:dd:lit:x:75": "high", "guard:roll:late": "high",
                "guard:quiet:lit:d": "default", "guard:ready": "low"}, q)
    ring = N.merge({**ALL, "ring_in_quiet_hours": ["pc_silent", "account_status", "room_low", "problems", *N.TRADE_RING]})
    check("a. trade_opened put in ring_in_quiet_hours: the 03:10 entry rings (the owner's yes / no, STATE.md)",
          {m["key"]: m["priority"] for m in N.apply(msgs, night, ring)}["open:lit:1"] == "high")
    check("a. the defaults do NOT ring trade entries and results at night (lead 2026-11-20: nights stay silent as before)",
          not N.rings("trade_opened", S) and not N.rings("trade_closed", S))
    check("a. 10:00: nothing changed", [m["priority"] for m in N.apply(msgs, day, ALL)] == [m["priority"] for m in msgs])
    off = N.merge({"alerts": {**ALL["alerts"], "trade_opened": False, "problems": False}})
    check("a. a type switched off is dropped", [m["key"] for m in N.apply(msgs, day, off)] == ["guard:dd:lit:x:75", "guard:roll:late", "guard:quiet:lit:d", "guard:ready"])
    check("a. no quiet hours (from == to)", not N.quiet(night, N.merge({"quiet_hours": {"from": "00:00", "to": "00:00"}})))


# ============================================================================================== b eval numbers + milestones
def milestones():
    from tools import pc_guard as G
    check("b. 50K: $1,500 to go = $1,500 of $3,000 (50%)", N.progress({"plan": "MFFU Builder 50K", "to_target": 1500.0}) == (1500.0, 3000.0, 50.0))
    check("b. 25K from profit + $ to go when the plan says no size", N.progress({"profit": 300.0, "to_target": 900.0}) == (300.0, 1200.0, 25.0))
    check("b. no numbers: None", N.progress({"plan": "x"}) is None and N.progress(None) is None)

    def card(tt, **kw):
        c = {"id": "lit", "name": "Zlarior", "plan": "MFFU Builder 50K", "badge": "LIVE", "status": "open", "balance": 50000.0, "floor": 48000.0,
             "room": 2000.0, "mll": 2000.0, "today_pnl": 0.0, "dll": 1000.0, "quiet_days": 0, "eval_start": "2026-11-02", "to_target": tt}
        c.update(kw)
        return c

    def snap(t, c):
        return {"t": t, "hb_age": 60, "mode": "LIVE", "live": {"board": {"lit": c}}}

    t = at(2026, 11, 17, 10, 0)
    goal = lambda m: [x for x in m if ":goal:" in x["key"]]
    st, m = G.guard({}, snap(t, card(3000.0)), roll_state={})
    check("b. 0%: no milestone", not goal(m), m)
    st, m = G.guard(st, snap(t + 900, card(2200.0)), roll_state={})
    g = goal(m)
    check("b. 27%: 'Zlarior 50K: 25% of the target made ($800 of $3,000)', $ to pass in the body", [x["title"] for x in g] == ["Zlarior 50K: 25% of the target made ($800 of $3,000)"]
          and g[0]["body"].startswith("$2,200 to pass."), g)
    st, m = G.guard(st, snap(t + 1800, card(2100.0)), roll_state={})
    check("b. not again at 30%", not goal(m), m)
    st, m = G.guard(st, snap(t + 2700, card(600.0)), roll_state={})
    check("b. 25% -> 80% at once: one push (the 75%), the 50% counted as said", [x["key"] for x in goal(m)] == ["guard:goal:lit:2026-11-02:75"]
          and "guard:goal:lit:2026-11-02:50" in st["sent"], m)
    st, m = G.guard(st, snap(t + 3600, card(2500.0)), roll_state={})
    check("b. a loss back to 17%: nothing (a level is said once)", not goal(m), m)
    st, m = G.guard(st, snap(t + 4500, card(0.0, status="passed")), roll_state={})
    g = goal(m)
    check("b. 100% (passed): 'profit target reached ($3,000)', high", [x["title"] for x in g] == ["Zlarior 50K: profit target reached ($3,000)"]
          and g[0]["priority"] == "high", g)
    _s, m = G.guard({}, snap(t, card(1500.0, eval_start="2026-12-01")), roll_state={})
    check("b. a new eval has its own levels", [x["key"] for x in goal(m)] == ["guard:goal:lit:2026-12-01:50"], m)
    _s, m = G.guard({}, snap(t, card(1500.0, status="failed")), roll_state={})
    check("b. a failed eval: no milestone", not goal(m), m)


# ============================================================================================== c news
def news():
    tmp = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(tmp, "data", "news"))
        with open(os.path.join(tmp, "data", "news", "events.csv"), "w", encoding="utf-8") as fh:
            fh.write("date,time_et,event,impact,source\n2026-11-18,14:00,Fed meeting minutes (Oct 27-28),high,fed\n2026-11-18,08:30,Housing,medium,x\n"
                     "2026-11-23,08:30,CPI m/m,high,bls\n")
        tue = at(2026, 11, 17, 16, 20)
        check("c. Tue -> Wed from the calendar file (high only)", N.news_line(tue, tmp) == "Tomorrow (Wed): Fed meeting minutes (Oct 27-28) 14:00.",
              N.news_line(tue, tmp))
        check("c. Fri -> Mon", N.news_line(at(2026, 11, 20, 16, 20), tmp) == "Tomorrow (Mon): CPI m/m 08:30.", N.news_line(at(2026, 11, 20, 16, 20), tmp))
        check("c. a quiet day says so", N.news_line(at(2026, 11, 18, 16, 20), tmp) == "Tomorrow (Thu): no big US news.")
        with open(os.path.join(tmp, "data", "news", "hub.json"), "w", encoding="utf-8") as fh:
            json.dump({"range": {"from": "2026-11-16", "to": "2026-11-22"}, "events": [
                {"date": "2026-11-18", "time_et": "10:00", "title": "ISM Services PMI", "impact": "high", "country": "USD"},
                {"date": "2026-11-18", "time_et": "09:00", "title": "German thing", "impact": "high", "country": "EUR"}]}, fh)
        check("c. the news hub wins when it covers the day (USD only)", N.news_line(tue, tmp) == "Tomorrow (Wed): ISM Services PMI 10:00.", N.news_line(tue, tmp))
        check("c. Christmas Eve (Thu) -> Mon Dec 28 (Christmas closed, then the weekend)", N.next_session_day(at(2026, 12, 24, 16, 20)).isoformat() == "2026-12-28",
              N.next_session_day(at(2026, 12, 24, 16, 20)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ============================================================================================== d PC silent state machine
def silent():
    last = at(2026, 11, 17, 9, 14)                       # Tuesday
    st, m = N.silent_step({}, last, last + 600, S)
    check("d. 10 min old: nothing", m == [] and st["last_seen"] == last, (st, m))
    st, m = N.silent_step(st, None, last + 25 * 60, S)
    check("d. 25 min old in market hours: ONE push 'Your PC stopped reporting at 09:14 ET. Check it: STOP BOT, START BOT.', high",
          len(m) == 1 and m[0]["title"] == "PC stopped reporting" and m[0]["body"] == "Your PC stopped reporting at 09:14 ET. Check it: STOP BOT, START BOT."
          and m[0]["priority"] == "high", m)
    n_runs = 0
    for k in range(1, 4):                                # the next runs (every 30 min) inside 2 h: nothing
        st, m = N.silent_step(st, None, last + 25 * 60 + k * 1800, S)
        n_runs += len(m)
    check("d. the next runs within 2 h: nothing (never every run)", n_runs == 0, st)
    st, m = N.silent_step(st, None, last + 25 * 60 + 7200, S)
    check("d. 2 h after the push: one reminder 'PC still silent' with how long ago", len(m) == 1 and m[0]["title"] == "PC still silent"
          and "stopped reporting at 09:14 ET (2 h ago)" in m[0]["body"] and "STOP BOT, START BOT" in m[0]["body"], m)
    more = 0
    for k in range(1, 8):
        st, m = N.silent_step(st, None, last + 25 * 60 + 7200 + k * 1800, S)
        more += len(m)
    check("d. after the reminder: nothing more that day", more == 0, st)
    wed = at(2026, 11, 18, 1, 32)
    st, m = N.silent_step(st, None, wed, S)
    check("d. the next trading day (01:32 ET): one push again, naming the day it stopped",
          len(m) == 1 and m[0]["body"] == "Your PC stopped reporting at Tue Nov 17 09:14 ET. Check it: STOP BOT, START BOT.", m)
    st, m = N.silent_step(st, wed + 3000, wed + 3100, S)
    check("d. it reports again: one 'PC reporting again' (no sound), state cleared", len(m) == 1 and m[0]["title"] == "PC reporting again"
          and m[0]["priority"] == "default" and st["out"] is None, (st, m))
    st, m = N.silent_step(st, None, wed + 3700, S)
    check("d. fresh again: nothing", m == [], m)
    sat = at(2026, 11, 21, 10, 0)
    _s, m = N.silent_step({"last_seen": last}, None, sat, S)
    check("d. Saturday: nothing (market closed)", m == [], m)
    _s, m = N.silent_step({"last_seen": last}, None, at(2026, 11, 17, 18, 0), S)
    check("d. 18:00 ET: nothing (outside 01:30-16:00)", m == [], m)
    _s, m = N.silent_step({"last_seen": last}, None, at(2026, 12, 25, 10, 0), S)
    check("d. Christmas (CME closed): nothing", m == [], m)
    _s, m = N.silent_step({"last_seen": last}, None, last + 3600, S, fetched=False)
    check("d. no source answered (network trouble): nothing", m == [], m)
    _s, m = N.silent_step({}, None, last + 3600, S)
    check("d. never seen at all: 'has not reported for 12+ hours'", len(m) == 1 and "has not reported for 12+ hours" in m[0]["body"], m)
    _s, m = N.silent_step({}, last, last + 3600, S, sent_today=[last + 1500])
    check("d. state lost, but today's push is on the topic: no repeat", m == [] and _s["out"]["sent"] == 1, (_s, m))
    _s, m = N.silent_step({}, last, last + 1500 + 7300, S, sent_today=[last + 1500])
    check("d. ... and the reminder still comes 2 h after that push", len(m) == 1 and m[0]["title"] == "PC still silent", m)
    _s, m = N.silent_step({"last_seen": last}, None, last + 3600, N.merge({"alerts": {"pc_silent": False}}))
    check("d. pc_silent off: nothing", m == [], m)
    _s, m = N.silent_step({"last_seen": last}, None, last + 40 * 60, N.merge({"pc_silent_after_min": 45}))
    check("d. pc_silent_after_min 45: 40 min is not silent yet", m == [], m)
    allm = [p for k in ("first", "remind", "back") for p in (N.silent_payloads(k, last, last + 4000), N.silent_payloads(k, None, last + 4000))]
    check("d. every title / body: ASCII (an HTTP header), no $ / account / name", all(all(ord(ch) < 128 for ch in p["title"] + p["body"]) for p in allm)
          and not any("$" in p["body"] for p in allm), allm)


# ============================================================================================== e the cloud step (stub ntfy)
class Net:
    def __init__(self, feed_msgs=(), alert_msgs=(), post_code=200):
        self.feed_msgs, self.alert_msgs, self.post_code = list(feed_msgs), list(alert_msgs), post_code
        self.gets, self.posts = [], []

    def get(self, url, **kw):
        self.gets.append(url)
        if "/olympus-nq-status-test/" in url:
            return 200, "\n".join(json.dumps(m) for m in self.feed_msgs)
        if "/nq-private-topic-1234/" in url:
            return 200, "\n".join(json.dumps(m) for m in self.alert_msgs)
        return 404, ""

    def post(self, url, body, headers, **kw):
        self.posts.append({"url": url, "body": body.decode(), "h": dict(headers)})
        if 200 <= self.post_code < 300:
            topic = url.rsplit("/", 1)[-1]
            msg = {"event": "message", "time": int(self.now), "title": headers.get("Title"), "message": body.decode()}
            (self.alert_msgs if topic == "nq-private-topic-1234" else self.feed_msgs).append(msg)
        return self.post_code, ""


def live_msg(t):
    return {"event": "message", "time": t, "message": json.dumps({"kind": "le-live", "t": t - 100, "reporter": {"t": t}})}


def cloud():
    feed = {"ntfy": "https://ntfy.sh", "topic": "olympus-nq-status-test"}
    env = {"LE_NTFY_TOPIC": "nq-private-topic-1234"}
    tmp = tempfile.mkdtemp()
    try:
        last = at(2026, 11, 17, 9, 14)
        net = Net(feed_msgs=[live_msg(last - 900), live_msg(last), {"event": "message", "time": last + 60, "message": "not json"},
                             {"event": "keepalive", "time": last + 99999}])
        out = []
        net.now = last + 600
        r = C.run(tmp, now=net.now, env=env, get=net.get, post=net.post, hb={"present": False}, feed=feed, s=S, say=out.append)
        check("e. PC posted 10 min ago: nothing sent, last report from the status feed (only 'le-live' posts count)", not net.posts
              and r["state"]["feed_t"] == last and r["state"]["last_seen"] == last, r["state"])
        net.now = last + 30 * 60
        r = C.run(tmp, now=net.now, env=env, get=net.get, post=net.post, hb={"present": True, "t": last - 3600}, feed=feed, s=S, say=out.append)
        ps = net.posts
        check("e. 30 min silent: one push to the PRIVATE topic from LE_NTFY_TOPIC, title / priority / tags headers",
              len(ps) == 1 and ps[0]["url"] == "https://ntfy.sh/nq-private-topic-1234" and ps[0]["h"]["Title"] == "PC stopped reporting"
              and ps[0]["h"]["Priority"] == "high" and ps[0]["body"] == "Your PC stopped reporting at 09:14 ET. Check it: STOP BOT, START BOT.", ps)
        check("e. the private topic is never printed", not any("nq-private-topic-1234" in str(x) for x in out) and any("your private topic" in x for x in out), out)
        saved = json.load(open(os.path.join(tmp, C.STATE_NAME), encoding="utf-8"))
        check("e. state file written (pc_silent.json): sent 1, last seen, where to", saved["out"]["sent"] == 1 and saved["last_seen"] == last
              and saved["to"] == "private", saved)
        os.remove(os.path.join(tmp, C.STATE_NAME))     # the dashboard publish failed: the state is gone
        net.now = last + 60 * 60
        C.run(tmp, now=net.now, env=env, get=net.get, post=net.post, hb={"present": False}, feed=feed, s=S, say=out.append)
        check("e. state file lost: today's push is read back from the topic, no repeat", len(net.posts) == 1, net.posts)
        net.now = last + 30 * 60 + 7200
        C.run(tmp, now=net.now, env=env, get=net.get, post=net.post, hb={"present": False}, feed=feed, s=S, say=out.append)
        check("e. 2 h later: the reminder", len(net.posts) == 2 and net.posts[-1]["h"]["Title"] == "PC still silent", net.posts)
        # fallback: no secret -> the public status topic, and a failed POST is retried on the next run
        tmp2 = tempfile.mkdtemp()
        try:
            n2 = Net(feed_msgs=[live_msg(last)], post_code=429)
            n2.now = last + 30 * 60
            r = C.run(tmp2, now=n2.now, env={}, get=n2.get, post=n2.post, hb={"present": False}, feed=feed, s=S, say=out.append)
            check("e. no LE_NTFY_TOPIC: the plain alert goes to the public status topic", n2.posts and n2.posts[0]["url"] == "https://ntfy.sh/olympus-nq-status-test"
                  and not r["dest_private"], n2.posts)
            check("e. ntfy refused (429): marked not sent", r["state"]["out"]["sent"] == 0, r["state"])
            n2.post_code = 200
            n2.now += 1800
            C.run(tmp2, now=n2.now, env={}, get=n2.get, post=n2.post, hb={"present": False}, feed=feed, s=S, say=out.append)
            check("e. ... retried on the next run and sent", len(n2.posts) == 2 and n2.posts[-1]["h"]["Title"] == "PC stopped reporting", n2.posts)
            n2.now += 1800
            C.run(tmp2, now=n2.now, env={}, get=n2.get, post=n2.post, hb={"present": False}, feed=feed, s=S, say=out.append)
            check("e. the cloud's own alert on the status topic is not a PC report (still silent, no repeat)", len(n2.posts) == 2, n2.posts)
        finally:
            shutil.rmtree(tmp2, ignore_errors=True)
        check("e. dest(): a full https URL, a bad value falls back", C.dest({"LE_NTFY_TOPIC": "https://ntfy.example.org/abc_1"}, feed)
              == {"base": "https://ntfy.example.org", "topic": "abc_1", "private": True}
              and C.dest({"LE_NTFY_TOPIC": "bad topic!"}, feed)["topic"] == "olympus-nq-status-test")
        n3 = Net()
        n3.now = last + 3600
        r = C.run(tmp, now=n3.now, env=env, get=lambda u, **k: (0, "URLError"), post=n3.post, hb={"present": False}, feed=feed, s=S, say=out.append)
        check("e. no source answers (network down): nothing pushed", not n3.posts and not r["msgs"], r)
        real_hb, real_get = C.read_hb, C.http_get
        try:                                   # main() with every source stubbed: no git fetch, no HTTP
            C.read_hb = lambda now: {"present": False}
            C.http_get = lambda url, **k: (0, "network off")
            check("e. main() never fails the job (network off)", C.main(["--out", tmp, "--dry-run"]) == 0)
        finally:
            C.read_hb, C.http_get = real_hb, real_get
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ============================================================================================== f through pc_report
def report():
    from tools import pc_report as R
    from tests.test_launch_kit import lit_card, snap_of
    real = N.settings
    try:
        t = at(2026, 11, 17, 10, 15)
        pos = {"entry_t": t - 180, "side": "SHORT", "qty": 6, "entry": 25100.25, "stop": 25130.0, "target": 24980.0}
        st, _m = R.events({}, snap_of(t - 900, {"lit": lit_card(), "trades": []}))
        b = {"lit": lit_card(position=dict(pos)), "trades": []}
        N.settings = lambda path=None: N.merge({"alerts": {"trade_opened": False}})
        st2, m = R.events(st, snap_of(t, b))
        check("f. trade_opened off: no entry push, the key still recorded (it never comes later)", not [x for x in m if x["key"].startswith("open:")]
              and f"open:lit:{pos['entry_t']}" in st2["seen"], m)
        N.settings = lambda path=None: ALL
        n = at(2026, 11, 17, 3, 10)
        p2 = {**pos, "entry_t": n - 120}
        _s, m = R.events(st, snap_of(n, {"lit": lit_card(position=p2), "trades": []}))
        o = [x for x in m if x["key"].startswith("open:")]
        check("f. a 03:10 ET entry (quiet hours): pushed without sound (priority low), $ first title",
              len(o) == 1 and o[0]["priority"] == "low" and o[0]["title"] == "Zlarior 50K SHORT opened | risk $368 | target +$1,432", o)
    finally:
        N.settings = real


# ============================================================================================== g the workflow
def workflow():
    wf = open(os.path.join(ROOT, ".github", "workflows", "cloud-monitor.yml"), encoding="utf-8").read()
    i_step = wf.find("- name: PC silent check")
    blk = wf[i_step: wf.find("- name:", i_step + 10)]
    check("g. the PC silent step runs before the install and the paper monitor", 0 < i_step < wf.find("- name: Install") < wf.find("- name: Run paper monitor"))
    check("g. it only runs in the guard's window, never fails the job, reads the secret LE_NTFY_TOPIC, restores its state",
          "if: steps.guard.outputs.go == '1'" in blk and "continue-on-error: true" in blk and "${{ secrets.LE_NTFY_TOPIC }}" in blk
          and "pc_silent.json" in blk and "python tools/pc_silent_check.py --out dash || true" in blk, blk)
    check("g. notify_settings.json is in the sparse checkout", re.search(r"^\s+/notify_settings\.json$", wf, re.M) is not None)
    src = open(os.path.join(ROOT, "tools", "pc_silent_check.py"), encoding="utf-8").read() + open(os.path.join(ROOT, "engine", "notify.py"), encoding="utf-8").read()
    check("g. read-only: no order, no arming, no live_model write", not re.search(r"PLACE;|place_order|CLOSEPOSITION|LIVE_PHRASE|/api/live|arm\(", src))


# ============================================================================================== h the morning brief
def brief():
    from tools import morning_brief as MB
    from tools import pc_guard as G
    from tools import pc_report as R
    from tests.test_launch_kit import atlas_card, lit_card, snap_of
    tmp = tempfile.mkdtemp()
    keep_env = {k: os.environ.get(k) for k in ("LE_BOARD_DIR", "LE_INBOX_DIR", "LE_BOARD_SHARED", "LE_PC_REPORT")}
    real = N.settings
    try:
        os.environ.update(LE_BOARD_DIR=os.path.join(tmp, "board"), LE_INBOX_DIR=os.path.join(tmp, "inbox"),
                          LE_BOARD_SHARED=os.path.join(tmp, "shared.jsonl"))
        os.environ.pop("LE_PC_REPORT", None)
        N.settings = lambda path=None: S
        news = os.path.join(tmp, "root")
        os.makedirs(os.path.join(news, "data", "news"))
        with open(os.path.join(news, "data", "news", "events.csv"), "w", encoding="utf-8") as fh:
            fh.write("date,time_et,event,impact\n2026-11-18,08:30,CPI m/m,high\n2026-11-18,10:30,Crude Oil Inventories,medium\n")
        plan = {"accounts": [{"key": "zlarior", "name": "Zlarior", "plan": "MFFU Builder 50K", "stage": "eval", "status": "live", "pc": ["mffu50k_eval", "lit"]},
                             {"key": "atlas", "name": "ATLAS", "plan": "MFFU Builder 25K (funded)", "stage": "funded", "status": "live", "pc": ["atlas"]},
                             {"key": "rapid1", "name": "Rapid EOD 25K (next)", "plan": "MFFU Rapid EOD 25K", "stage": "eval", "status": "waiting"},
                             {"key": "fresh25", "name": "Zlarior 25K #2", "plan": "MFFU Builder 25K", "stage": "eval", "status": "live", "pc": ["b25k_2"]}]}

        def snap(now, lit=None, atlas=None, trades=(), cond=None, eh=None, extra=()):
            board = {"lit": lit or lit_card(balance=49192.78, floor=48168.2, room=1024.58, to_target=3807.22),
                     "atlas": atlas or atlas_card(balance=25000.0, room=1000.0, status="funded", stage="funded", funded={"to_ask": 2100.0, "ready": False}),
                     "trades": list(trades)}
            accts = [{"id": "b25k_2", "name": "Zlarior Builder 25K #2", "kind": "eval", "source": "pc", "plan": "MFFU Builder 25K",
                      "eval": {"balance": 25000.0, "floor": 24000.0, "room": 1000.0, "to_target": 1500.0}, "trades": []}] + list(extra)
            s = snap_of(now, board, eh=eh if eh is not None else {"d": "2026-11-17", "z": ["G", 3.8, 3.9], "a": ["G", 1.9, 2.0, "2026-11-17"], "t": now - 3600})
            s["live"] = {"board": board, "accounts": accts}
            s["cond"] = cond or {}
            return s

        wed = at(2026, 11, 18, 7, 32)
        b = MB.build_full(snap(wed), wed, plan, [], news, fleet="decide the Rapid EOD 50K card first", waiting=4)
        ex = b["lines"]
        check("h. Wed 07:32 (night-brief): READY line, one line per account (armed, $, room, $ to pass / to payout), Today (hours, CPI, "
              "the T1 ban), the next money move, edge + needs you + decide cards", ex[0].startswith("PC ok") and ex[1:4] == [
                  "Zlarior 50K armed · $49,193 · room $1,025 · $3,807 to pass",
                  "Zlarior 25K #2 · $25,000 · room $1,000 · $1,500 to pass",
                  "ATLAS 25K armed · $25,000 · room $1,000 · $2,100 to payout"]
              and ex[4].startswith("Today: Zlarior till 15:30, ATLAS till 12:00 · CPI m/m 08:30")
              and ex[5] == "Next money move: decide the Rapid EOD 50K card first"
              and ex[6] == "Edge GREEN · Needs you: none · Decide cards waiting: 4" and len(ex) <= MB.MAX_LINES, ex)
        check("h. the push: ASCII title 'ZEUS - Wed Nov 18 - PC ok', the body = the lines (<= 8)",
              b["title"] == "ZEUS - Wed Nov 18 - PC ok" and all(ord(c) < 128 for c in b["title"]) and b["body"].split("\n") == ex, b)
        rd = snap(wed)
        rd["rd"] = {"s": "no", "w": "02:00", "b": "PC clock 25 s behind", "f": "double-click FIX_CLOCK.bat once, right-click > Run as administrator"}
        br = MB.build_full(rd, wed, plan, [], news, fleet="", waiting=0)
        check("h. readiness NOT READY: line 1 = the blocker + its fix, the title says NOT READY",
              br["lines"][0] == "NOT READY for 02:00: PC clock 25 s behind. Fix: double-click FIX_CLOCK.bat once, right-click > Run as administrator"
              and br["title"] == "ZEUS - Wed Nov 18 - NOT READY", br)
        rd["rd"] = {"s": "ok", "w": "02:00"}
        check("h. readiness ok: 'READY for 02:00 ...'", MB.build_full(rd, wed, plan, [], news, fleet="", waiting=0)["lines"][0].startswith("READY for 02:00"))
        odd = {"id": "EVBLDR987654321", "name": "EVBLDR987654321", "kind": "eval", "source": "pc", "plan": "MFFU Builder 25K",
               "eval": {"balance": 25100.0, "floor": 24100.0, "room": 1000.0, "to_target": 1400.0}, "trades": []}
        b2 = MB.build_full(snap(wed, extra=[odd]), wed, plan, [], news)
        check("h. an account the plan lacks: shown, its id cut to the last 4 (never the full id)",
              "987654321" not in b2["body"] and "...4321" in b2["body"], b2["body"])
        t3 = at(2026, 11, 18, 3, 5)
        tr = [{"acct": "lit", "src": "live", "day": "2026-11-18", "entry_t": t3, "exit_t": t3 + 1200, "usd": 605.0},
              {"acct": "lit", "src": "paper", "day": "2026-11-18", "entry_t": t3 + 60, "exit_t": t3 + 900, "usd": -200.0},
              {"acct": "lit", "src": "live", "day": "2026-11-17", "entry_t": at(2026, 11, 17, 10, 0), "exit_t": at(2026, 11, 17, 11, 0), "usd": 300.0}]
        pos = {"side": "SHORT", "qty": 2, "entry_t": wed - 300}
        b3 = MB.build_full(snap(wed, trades=tr, atlas=atlas_card(balance=25000.0, status="funded", stage="funded", position=pos,
                                                           funded={"ready": True, "max_request": 1000.0})), wed, plan, [], news)
        t3l = " | ".join(b3["lines"])
        check("h. overnight = since 18:00 ET, paper left out (on the Today line); yesterday's $ on the account line; payout READY -> needs you",
              "overnight Zlarior 50K +$605 (1 trade), ATLAS 25K SHORT open" in t3l and "Zlarior 50K armed · $49,193 · room $1,025 · yesterday +$300" in t3l
              and "payout READY $1,000" in t3l, b3["lines"])
        check("h. night-payday: a payout MFFU pays today = line 2 'REQUEST PAYOUT TODAY: ATLAS 25K $1,000 - MFFU dashboard > Payouts, then "
              "TRADE_HOME -> P' + the title says it; not repeated under Needs you; 8 lines at most; a brief with no payout ready has no such line",
              b3["lines"][1] == "REQUEST PAYOUT TODAY: ATLAS 25K $1,000 - MFFU dashboard > Payouts, then TRADE_HOME -> P"
              and b3["title"].endswith(" - REQUEST PAYOUT TODAY") and "request the ATLAS 25K payout" not in t3l and len(b3["lines"]) <= 8
              and not any("REQUEST PAYOUT" in x for x in MB.build_full(snap(wed), wed, plan, [], news)["lines"]), (b3["title"], b3["lines"]))
        v2 = MB.build(snap(wed, trades=tr, atlas=atlas_card(balance=25000.0, status="funded", stage="funded", position=pos,
                                                     funded={"ready": True, "max_request": 1000.0})), wed, plan, [], news, lvb={})
        check("h. integration: the pushed 5-line brief (night-briefv2) carries night-payday's REQUEST PAYOUT TODAY line first + the title",
              v2["lines"][0].startswith("REQUEST PAYOUT TODAY: ATLAS 25K $1,000") and v2["title"].endswith(" - REQUEST PAYOUT TODAY")
              and not any("REQUEST PAYOUT" in x for x in MB.build(snap(wed), wed, plan, [], news, lvb={})["lines"]), (v2["title"], v2["lines"]))
        b4 = MB.build_full(snap(wed, cond={"bot_down": "x"}, eh={"d": "2026-11-17", "z": ["G", 3.8, 3.9], "a": ["A", 1.2, 2.0, "2026-11-17"], "t": wed}), wed, plan, [], news)
        check("h. a problem: NOT READY in the title, line 1 = 'NOT READY: bot down. Fix: STOP BOT, START BOT'; edge 'Zlarior GREEN, ATLAS AMBER'",
              b4["title"].endswith("NOT READY") and b4["lines"][0] == "NOT READY: bot down. Fix: STOP BOT, START BOT"
              and "Edge Zlarior GREEN, ATLAS AMBER" in b4["lines"][-1], b4["lines"])
        old = snap(wed)
        old.update(hb_age=2400)
        bo = MB.build_full(old, wed, plan, [], news)
        check("h. an old report says so (NOT READY: last report 40 min old)", bo["lines"][0].startswith("NOT READY: last report 40 min old")
              and bo["title"].endswith("NOT READY"), bo["lines"][0])
        mon = at(2026, 11, 23, 7, 31)
        check("h. Monday: ATLAS has no EMA, so its hours start at 09:30", any(x.startswith("Today: Zlarior till 15:30, ATLAS 09:30-12:00")
                                                                              for x in MB.build_full(snap(mon), mon, plan, [], news)["lines"]))
        fri = at(2026, 11, 27, 7, 31)
        bf = next(x for x in MB.build_full(snap(fri), fri, plan, [], news)["lines"] if x.startswith("Today:"))
        check("h. Fri Nov 27 (early close 13:15): entries end 13:00, said plainly", "Zlarior till 13:00, ATLAS till 12:00" in bf and "half day, closes 13:15 ET" in bf, bf)

        # once a day through the guard; a restart (state.json read back) never repeats it
        def run(st, now):
            st, ms = G.guard(st, snap(now))
            return json.loads(json.dumps(st)), [m for m in ms if m["key"].startswith("guard:brief:")]
        st, m = run({}, wed)
        check("h. guard at 07:32: ONE brief (key guard:brief:2026-11-18)", [x["key"] for x in m] == ["guard:brief:2026-11-18"], m)
        st2, m2 = run(st, wed + 15 * 60)
        st3, m3 = run(json.loads(json.dumps(st2)), wed + 30 * 60)
        check("h. 07:47 and after a restart at 08:02: nothing again", not m2 and not m3, (m2, m3))
        nothing = [run({}, t)[1] for t in (at(2026, 11, 18, 7, 10), at(2026, 11, 18, 9, 40), at(2026, 11, 21, 7, 32), at(2026, 12, 25, 7, 32), at(2027, 1, 1, 7, 45))]
        check("h. 07:10, 09:40, Saturday, Christmas, New Year's Day: nothing", not any(nothing), nothing)
        check("h. 'important only' keeps it; morning_brief off drops it", [x["key"] for x in N.apply(m, wed, S)] == ["guard:brief:2026-11-18"]
              and not N.apply(m, wed, N.merge({"alerts": {"morning_brief": False}})), m)
        posts = []

        def http(method, url, body=None, headers=None, timeout=None):
            posts.append({"m": method, "url": url, "body": body.decode("utf-8"), "h": headers})
            return 200, "{}"
        ok, _why = R.ntfy_post("https://ntfy.example", "topic-test", m[0]["body"], title=m[0]["title"], priority=m[0]["priority"], tags=m[0]["tags"], http=http)
        check("h. the ntfy POST (stub): Title 'ZEUS - Wed Nov 18 - PC ok - <yesterday $>', the 5-line body (night-briefv2), nothing sent for real",
              ok and len(posts) == 1 and posts[0]["h"]["Title"].startswith("ZEUS - Wed Nov 18 - PC ok") and len(posts[0]["body"].split("\n")) == 5
              and posts[0]["body"].startswith("Yesterday: "), posts)
        evs = [json.loads(x) for x in open(os.path.join(tmp, "board", "events.jsonl"), encoding="utf-8")]
        check("h. ONE Board event 'brief' for the day (a test board), not again on the later runs", [e["kind"] for e in evs] == ["brief"]
              and evs[0]["data"]["day"] == "2026-11-18" and evs[0]["text"].startswith("Yesterday: ") and " | Bot: " in evs[0]["text"], evs)
        os.environ.pop("LE_BOARD_DIR", None)
        check("h. no Board write outside the real report (no LE_PC_REPORT, no test board): a self-test never posts a fake brief",
              MB.board_post(b) is None)
        from engine import board_events as BE
        check("h. Board kind 'brief' exists (quiet, not LOUD), the page names it", "brief" in BE.KINDS and "brief" not in BE.LOUD
              and "brief: 'Morning brief'" in open(os.path.join(ROOT, "tools", "web_public", "board", "boardmodel.js"), encoding="utf-8").read())
    finally:
        N.settings = real
        for k, v in keep_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(tmp, ignore_errors=True)


def instant():
    """g. instant entry alerts (owner 2026-11-18: 'notifications when we get in a trade in any account')."""
    tmp = tempfile.mkdtemp()
    real_settings = N.settings
    try:
        path = os.path.join(tmp, "instant.json")
        N.settings = lambda path=None: N.merge({})
        p = {"kind": "fill", "key": "fill:1795050000", "t": 1795050000, "account": "MFFUEVBLDR123459998", "side": "LONG", "qty": 6,
             "entry": 24980.25, "stop": 24955, "target": 25360, "body": "Entered 6 MNQ", "title": "LONG · x"}
        sent = []
        poster = lambda base, topic, msg: sent.append((base, topic, msg)) or True
        cfg = {"ntfy": "https://ntfy.sh", "topic": "nq-test-topic-0000"}
        day = at(2026, 11, 18, 10, 0)
        why = N.instant_entry(p, now=day, path=path, cfg=cfg, poster=poster)
        msg = sent[0][2] if sent else {}
        check("g. a real entry goes out at once to the private topic, $ first, ids masked, sound on in the day",
              why == "sent" and len(sent) == 1 and sent[0][1] == cfg["topic"] and msg["title"] == "Zlarior ...9998: LONG 6 MNQ @ 24,980.25"
              and "MFFUEVBLDR" not in msg["title"] + msg["body"] and msg["body"].startswith("stop 24,955.00 (-$303), target 25,360.00 (+$4,557)") and msg["priority"] == "high", (why, msg))
        check("g. the same entry twice: one push", N.instant_entry(p, now=day, path=path, cfg=cfg, poster=poster) == "already sent" and len(sent) == 1)
        check("g. the 15-minute report then skips that entry (90 s match), keeps other trades",
              N.instant_sent(1795050000 + 40, path=path) and not N.instant_sent(1795050000 + 400, path=path))
        old_path = N.INSTANT_PATH
        N.INSTANT_PATH = path
        try:
            kept = [m["key"] for m in N.apply([{"key": "open:lit:1795050030", "entry_t": 1795050030, "priority": "high"},
                                               {"key": "open:atlas:1795059999", "entry_t": 1795059999, "priority": "high"},
                                               {"key": "close:lit:1795050030", "entry_t": 1795050030, "priority": "high"}], day, N.merge({}))]
        finally:
            N.INSTANT_PATH = old_path
        check("g. apply(): the report's copy of an instant entry is dropped, a different entry and the close are kept",
              kept == ["open:atlas:1795059999", "close:lit:1795050030"], kept)
        atl = dict(p, key="fill:1795051000:acctb", t=1795051000, account="ATLAS 25K", body="Entered 2 MNQ (ATLAS)", side="SHORT")
        N.instant_entry(atl, now=day, path=path, cfg=cfg, poster=poster)
        check("g. ATLAS's entry is named ATLAS, short arrow", len(sent) == 2 and sent[1][2]["title"].startswith("ATLAS 25K: SHORT 6 MNQ @ ")
              and sent[1][2]["tags"] == "chart_with_downwards_trend", sent[-1])
        night = at(2026, 11, 18, 3, 10)
        N.instant_entry(dict(p, key="fill:1795060000", t=1795060000), now=night, path=path, cfg=cfg, poster=poster)
        check("g. inside quiet hours it still arrives, without sound", len(sent) == 3 and sent[2][2]["priority"] == "low", sent[-1])
        ring = N.merge({"ring_in_quiet_hours": ["pc_silent", "account_status", "room_low", "problems", *N.TRADE_RING]})
        check("g. trade_opened put in ring_in_quiet_hours: a night entry rings (priority high), a day entry rings either way",
              N.entry_message(p, now=night, s=ring)["priority"] == "high" and N.entry_message(p, now=day)["priority"] == "high")
        for bad, why_word in ((dict(p, key="fill:9", account="Paper"), "not a real"), (dict(p, key="fill:10", account="Sim101"), "not a real"),
                              (dict(p, key="fill:11", strategy="BLITZ"), "not a real"), (dict(p, key="fill:12", kind="outcome"), "not a real")):
            check(f"g. never for paper / sim / BLITZ / an outcome ({bad.get('account')}, {bad.get('strategy')}, {bad.get('kind')})",
                  N.instant_entry(bad, now=day, path=path, cfg=cfg, poster=poster).startswith(why_word) and len(sent) == 3)
        check("g. no private topic on this machine (the cloud): nothing sent",
              N.instant_entry(dict(p, key="fill:13"), now=day, path=path, cfg={}, poster=poster).startswith("no private") and len(sent) == 3)
        check("g. ntfy refuses: not recorded, so the 15-minute report still sends it",
              N.instant_entry(dict(p, key="fill:14", t=1795070000), now=day, path=path, cfg=cfg, poster=lambda *a: False).startswith("ntfy did not")
              and not N.instant_sent(1795070000, path=path))
        def boom(*a):
            raise OSError("down")
        check("g. a network error never raises", N.instant_entry(dict(p, key="fill:15"), now=day, path=path, cfg=cfg, poster=boom).startswith("failed"))
        N.settings = lambda path=None: N.merge({"alerts": {"trade_opened": False}})
        check("g. trade_opened switched off: nothing sent", N.instant_entry(dict(p, key="fill:16"), now=day, path=path, cfg=cfg, poster=poster) == "trade_opened is off"
              and len(sent) == 3)
        import engine.push as P
        src = open(P.__file__, encoding="utf-8").read()
        check("g. engine/push.pc_notify hands every fill to its own daemon thread (never delays routing): the phone app AND "
              "instant_entry (ntfy), whatever the app said (2026-11-20; tests.test_webpush + test_trade_alerts prove it)",
              'threading.Thread(target=_pc_send, args=(dict(payload),), kwargs={"retry_s": NTFY_RETRY_S}, name="push", daemon=True)' in src
              and '(ntfy or notify.instant_entry) if k == "fill"' in src)
        home = os.path.join(tmp, "olympus")
        os.makedirs(home)
        with open(os.path.join(home, "ntfy.json"), "w") as fh:
            json.dump({"topic": "nq-abc-def-ghi-1234", "ntfy": "https://ntfy.sh/"}, fh)
        c = N.alert_cfg({"OLYMPUS_HOME": home})
        check("g. the private topic comes from OLYMPUS_HOME/ntfy.json, like the 15-minute report",
              c == {"ntfy": "https://ntfy.sh", "topic": "nq-abc-def-ghi-1234"} or (c.get("topic") == "nq-abc-def-ghi-1234"), c)
    finally:
        N.settings = real_settings
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    for f in (settings, milestones, news, silent, cloud, report, workflow, brief, instant):
        try:
            f()
        except Exception as e:
            import traceback
            traceback.print_exc()
            check(f"{f.__name__} raised {e.__class__.__name__}: {e}", False)
    n, ok = len(RES), sum(RES)
    print(f"\n{ok}/{n} passed")
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
