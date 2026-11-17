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


# ============================================================================================== a settings
def settings():
    tmp = tempfile.mkdtemp()
    try:
        s = N.settings(os.path.join(tmp, "none.json"))
        check("a. no file: the defaults (every type on, quiet 23:00-07:00, summary 16:15, silent after 20 min, reminder 2 h)",
              all(s["alerts"].values()) and s["quiet_hours"] == {"from": "23:00", "to": "07:00"} and s["daily_summary_at"] == "16:15"
              and s["pc_silent_after_min"] == 20 and s["pc_silent_remind_after_min"] == 120, s)
        p = os.path.join(tmp, "s.json")
        with open(p, "w") as fh:
            fh.write("{broken")
        check("a. a broken file: the defaults", N.settings(p) == S)
        j = N.merge({"alerts": {"trade_opened": False, "bogus": False, "pc_silent": "no"}, "quiet_hours": {"from": "25:00", "to": "06:00"},
                     "milestones_pct": [50, "x", 200, 100], "pc_silent_after_min": 1, "daily_summary_at": "16:30"})
        check("a. junk ignored, good values kept, limits clamped", j["alerts"]["trade_opened"] is False and "bogus" not in j["alerts"]
              and j["alerts"]["pc_silent"] is True and j["quiet_hours"] == {"from": "23:00", "to": "06:00"} and j["milestones_pct"] == [50, 100]
              and j["pc_silent_after_min"] == 5 and j["daily_summary_at"] == "16:30", j)
        repo = N.settings(N.SETTINGS_PATH)
        raw = json.load(open(N.SETTINGS_PATH, encoding="utf-8"))
        check("a. the repo's notify_settings.json loads, names every type, all on, the asked defaults",
              set(raw["alerts"]) == set(N.TYPES) and all(repo["alerts"].values()) and repo["milestones_pct"] == [25, 50, 75, 100]
              and repo["pc_silent_after_min"] == 20 and repo["pc_silent_remind_after_min"] == 120 and repo["daily_summary_at"] == "16:15", repo)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    kinds = {k: N.kind_of(k) for k in ("open:lit:1", "close:atlas:2", "guard:goal:lit:x:50", "guard:dd:lit:x:75", "guard:dll:lit:d",
                                        "guard:day:2026-11-16", "cond:bot_down:1", "fill:lit:1:size", "guard:roll:x", "guard:quiet:lit:d")}
    check("a. push keys -> types", list(kinds.values()) == ["trade_opened", "trade_closed", "eval_milestones", "room_low", "room_low",
                                                             "daily_summary", "problems", "problems", "other", "other"], kinds)
    night, day = at(2026, 11, 17, 3, 10), at(2026, 11, 17, 10, 0)
    check("a. quiet hours over midnight: 03:10 and 23:30 quiet, 07:00 and 10:00 not", N.quiet(night, S) and N.quiet(at(2026, 11, 17, 23, 30), S)
          and not N.quiet(at(2026, 11, 17, 7, 0), S) and not N.quiet(day, S))
    msgs = [{"key": "open:lit:1", "priority": "high"}, {"key": "cond:bot_down:1", "priority": "high"}, {"key": "guard:dd:lit:x:75", "priority": "high"},
            {"key": "guard:roll:late", "priority": "high"}, {"key": "guard:quiet:lit:d", "priority": "default"}, {"key": "guard:ready", "priority": "low", "night": True}]
    q = {m["key"]: m["priority"] for m in N.apply(msgs, night, S)}
    check("a. 03:10: the trade and an ordinary push lose their sound; problems, room low and a high 'other' keep it",
          q == {"open:lit:1": "low", "cond:bot_down:1": "high", "guard:dd:lit:x:75": "high", "guard:roll:late": "high",
                "guard:quiet:lit:d": "low", "guard:ready": "low"}, q)
    check("a. 10:00: nothing changed", [m["priority"] for m in N.apply(msgs, day, S)] == [m["priority"] for m in msgs])
    off = N.merge({"alerts": {"trade_opened": False, "problems": False}})
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
        N.settings = lambda path=None: S
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


def main() -> int:
    for f in (settings, milestones, news, silent, cloud, report, workflow):
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
