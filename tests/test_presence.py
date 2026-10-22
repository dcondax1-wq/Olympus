"""'I'm here' presence check-in, the entry pause and the weekly hands-off score (engine/presence.py, entry_pause.py,
handsoff.py, presence_api.py; the guard hooks in engine/guards.py). Temp files only; no network, no broker.

  python -X utf8 -m tests.test_presence          (~3 s)
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import entry_pause, guards, handsoff, presence  # noqa: E402

ET = ZoneInfo("America/New_York")
RES = []


def check(name, ok, info=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}{(': ' + str(info)) if info and not ok else ''}")
    RES.append(bool(ok))


def ts(y, mo, d, h, mi=0):
    return int(dt.datetime(y, mo, d, h, mi, tzinfo=ET).timestamp())


class FakeBot:
    def __init__(self, tmp, now, running=True):
        self.state_path = os.path.join(tmp, "live_state.json")
        self.clock = lambda: now[0]
        self.running = running
        self.cfg = {"sym": "NQ", "adapter": "paper"}
        self.state = {}
        self.ledger = []
        self.health = {}
        self.pushed, self.logs, self.errors = [], [], []

    def _push_send(self, p):
        self.pushed.append(p)

    def _log(self, kind, text):
        self.logs.append((kind, text))

    def _note_error(self, t):
        self.errors.append(t)

    def day_pnl_routed(self):
        return 0.0


OFF = {k: False for k in ("calendar", "order_sanity", "dup_entry", "daily_loss", "clock", "news")}


def main():
    tmp = tempfile.mkdtemp(prefix="le_presence_")
    try:
        presence_tests(tmp)
        pause_tests(tmp)
        guard_tests(tmp)
        handsoff_tests(tmp)
        api_tests(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n, ok = len(RES), sum(RES)
    print(f"\n{ok}/{n} presence / pause / hands-off checks passed")
    return 0 if ok == n else 1


# ---------------------------------------------------------------------------------------------- presence
def presence_tests(tmp):
    p = os.path.join(tmp, "p1", "presence.jsonl")
    t0 = ts(2026, 10, 21, 1, 52)
    check("no file: not present, 'Not checked in yet'", presence.status(t0, p)["line"] == "Not checked in yet"
          and not presence.status(t0, p)["present"])
    presence.check_in("pc", None, t0, p)
    s = presence.status(t0 + 60, p)
    check("check-in at 01:52: 'Present since 01:52 ET (until 05:52 ET)' (4 h default)",
          s["present"] and s["line"] == "Present since 01:52 ET (until 05:52 ET)", s)
    presence.check_in("phone", 2, t0 + 3 * 3600, p)               # 04:52 + 2 h = 06:52: extends the window
    w = presence.windows(presence.events(p), t0 + 4 * 3600)
    check("a second check-in while present extends the window (one window, until 06:52)",
          len(w) == 1 and w[0]["to"] == t0 + 5 * 3600 and w[0]["taps"] == 2, w)
    presence.check_out("pc", t0 + 4 * 3600, p)                      # 05:52 "I'm leaving"
    s = presence.status(t0 + 4 * 3600 + 60, p)
    w = presence.windows(presence.events(p), t0 + 4 * 3600 + 60)
    check("I'm leaving closes it: not present, window ended 'checked out' at 05:52",
          not s["present"] and w[-1]["ended"] == "checked out" and w[-1]["to"] == t0 + 4 * 3600 and "last check-in" in s["line"], (s, w))
    presence.check_in("pc", 1, t0 + 6 * 3600, p)                    # 07:52 for 1 h
    w = presence.windows(presence.events(p), t0 + 9 * 3600)
    check("a 1-h check-in that ran out: 'expired', not present", w[-1]["ended"] == "expired"
          and not presence.present_at(t0 + 9 * 3600, w) and presence.present_at(t0 + 6 * 3600 + 60, w), w)
    check("hours are clamped (0.25-16 h), junk -> 4 h", presence._hours(100) == 16.0 and presence._hours(0) == 0.25
          and presence._hours("x") == 4.0)
    # the log page: trades with / without presence
    led = os.path.join(tmp, "p1", "ledger.jsonl")
    e1, e2 = t0 + 2 * 3600, t0 + 10 * 3600                          # 03:52 present, 11:52 not
    rows = [{"t": e1 + 3, "side": "buy", "qty": 4, "entry_t": e1, "result": {"ok": True}},
            {"t": e1 + 1800, "side": "exit", "qty": 4, "entry_t": e1, "reason": "TARGET"},
            {"t": e2 + 3, "side": "sell", "qty": 2, "entry_t": e2, "result": {"ok": True}},
            {"t": e2 + 600, "side": "exit", "qty": 2, "entry_t": e2, "reason": "STOP"},
            {"t": e2 + 700, "side": "buy", "qty": 1, "entry_t": e2 + 650, "result": {"ok": True}},
            {"t": e2 + 710, "side": "exit", "qty": 1, "entry_t": e2 + 650, "reason": "NO TRADE"}]
    with open(led, "w", encoding="utf-8") as fh:
        fh.write("\n".join(json.dumps(r) for r in rows))
    v = presence.log_view(now=t0 + 12 * 3600, days=3, path=p, ledger_path=led)
    tr = {t["entry_t"]: t for t in v["trades"]}
    check("presence log: 2 bot trades (the NO TRADE one dropped), 03:52 present (30 of 30 min), 11:52 not",
          len(v["trades"]) == 2 and tr[e1]["present"] and tr[e1]["overlap_min"] == 30 and not tr[e2]["present"]
          and v["summary"]["line"] == "present for 1 of 2 trades", v["summary"])
    check("presence log: windows newest first, with labels", v["windows"][0]["from"] == t0 + 6 * 3600 and "ET" in v["windows"][0]["label"])


# ---------------------------------------------------------------------------------------------- pause
def pause_tests(tmp):
    now = ts(2026, 10, 21, 10, 0)                                    # Wednesday
    u, lab = entry_pause.parse_until("tomorrow", now)
    check("tomorrow = 00:00 ET tonight", u == ts(2026, 10, 22, 0, 0) and lab.startswith("tomorrow"), (u, lab))
    check("HH:MM ahead today = today", entry_pause.parse_until("14:30", now)[0] == ts(2026, 10, 21, 14, 30))
    check("HH:MM already past = tomorrow", entry_pause.parse_until("09:00", now)[0] == ts(2026, 10, 22, 9, 0))
    check("a date = 00:00 ET that day", entry_pause.parse_until("2026-10-26", now)[0] == ts(2026, 10, 26, 0, 0))
    bad = [entry_pause.parse_until(x, now)[0] for x in ("", "24:00", "soon", "2026-10-20", "2026-12-31", "2026-02-30", None)]
    check("bad / past / > 14 days / impossible: refused", bad == [None] * 7, bad)
    dst = entry_pause.parse_until("01:30", ts(2026, 10, 31, 12, 0))[0]          # the night of the DST change (Nov 1)
    check("HH:MM across the DST change is 01:30 local", dt.datetime.fromtimestamp(dst, ET).strftime("%m-%d %H:%M") == "11-01 01:30")
    now_ = [now]
    bot = FakeBot(os.path.join(tmp, "pz"), now_)
    os.makedirs(os.path.dirname(bot.state_path), exist_ok=True)
    pp = entry_pause.path_for(bot)
    check("pause file beside live_state.json is data/entry_pause.json; a harness state file gets <name>_pause.json",
          os.path.basename(pp) == "entry_pause.json"
          and os.path.basename(entry_pause.path_for(type("B", (), {"state_path": "/x/live_state_k.json"})())) == "live_state_k_pause.json")
    r = entry_pause.set_pause("tomorrow", now, pp, src="pc")
    check("set_pause ok + active", r["ok"] and entry_pause.active(now, pp)["until"] == u)
    check("problem while paused", "paused by you until tomorrow" in (entry_pause.problem(bot, now + 60) or ""))
    check("an expired pause: no problem, file removed", entry_pause.problem(bot, u + 1) is None and not os.path.exists(pp))
    entry_pause.set_pause("14:30", now, pp)
    check("clear: True when a pause was running, then nothing", entry_pause.clear(pp, now) is True and entry_pause.clear(pp, now) is False)


# ---------------------------------------------------------------------------------------------- guards
def guard_tests(tmp):
    check("guards defaults: presence_required OFF, presence_hours 4",
          guards.DEFAULTS["presence_required"] is False and guards.DEFAULTS["presence_hours"] == 4.0)
    now = [ts(2026, 10, 21, 3, 0)]
    bot = FakeBot(os.path.join(tmp, "g"), now)
    os.makedirs(os.path.dirname(bot.state_path), exist_ok=True)
    ent = {"entry_t": now[0], "dir": 1, "qty": 2, "entry": 25000.0, "stop": 24980.0, "target": 25060.0}
    act = {"side": "buy", "qty": 2, "stop": 24980.0, "target": 25060.0, "entry": 25000.0}
    c = {**guards.DEFAULTS, **OFF}
    check("default config, no check-in, no pause: nothing blocks", guards.entry_problems(bot, ent, act, 2, now[0], c=c) == [])
    con = {**c, "presence_required": True}
    p = guards.entry_problems(bot, ent, act, 2, now[0], c=con)
    check("presence_required ON + no check-in: blocked 'no check-in in the last 4 h'", len(p) == 1 and "no check-in in the last 4 h" in p[0], p)
    presence.check_in("pc", None, now[0] - 3600, presence.path_for(bot))
    check("ON + a check-in 1 h ago: not blocked", guards.entry_problems(bot, ent, act, 2, now[0], c=con) == [])
    check("ON + that check-in 5 h later (expired): blocked again",
          len(guards.entry_problems(bot, ent, act, 2, now[0] + 4 * 3600, c=con)) == 1)
    entry_pause.set_pause("tomorrow", now[0], entry_pause.path_for(bot))
    p = guards.entry_problems(bot, ent, act, 2, now[0], c=c)
    check("a pause blocks even with every guard off", len(p) == 1 and "paused by you" in p[0], p)
    entry_pause.clear(entry_pause.path_for(bot))
    # the 'Check in to keep trading' push: ON only, weekdays 01:40-15:30, once per day + last check-in
    b2 = FakeBot(os.path.join(tmp, "g2"), now)
    os.makedirs(os.path.dirname(b2.state_path), exist_ok=True)
    t = ts(2026, 10, 21, 1, 45)
    check("push: guard OFF -> no push", presence.tick(b2, c, t) is False and not b2.pushed)
    check("push: ON, 01:45 Wed, nobody checked in -> 'Check in to keep trading'",
          presence.tick(b2, con, t) is True and b2.pushed and b2.pushed[-1]["title"] == "Check in to keep trading")
    check("push: not repeated the same day", presence.tick(b2, con, t + 600) is False and len(b2.pushed) == 1)
    check("push: not on a Saturday, not at 01:00, not after 15:30",
          not presence.tick(b2, con, ts(2026, 10, 24, 9, 0)) and not presence.tick(b2, con, ts(2026, 10, 22, 1, 0))
          and not presence.tick(b2, con, ts(2026, 10, 22, 15, 45)))
    presence.check_in("phone", 1, t + 700, presence.path_for(b2))
    check("push: checked in -> none", presence.tick(b2, con, t + 800) is False)
    check("push: the 1-h window ran out -> pushed again (new key)", presence.tick(b2, con, t + 700 + 3700) is True and len(b2.pushed) == 2)
    b3 = FakeBot(os.path.join(tmp, "g3"), now, running=False)
    check("push: bot stopped -> none", presence.tick(b3, con, t) is False)


# ---------------------------------------------------------------------------------------------- hands-off
def git(cwd, *a):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, timeout=30)


def handsoff_tests(tmp):
    d = os.path.join(tmp, "ho")
    os.makedirs(d)
    hp = os.path.join(d, "handsoff.jsonl")
    wed = ts(2026, 10, 21, 10, 0)
    sat = ts(2026, 10, 24, 12, 0)
    check("points: stop 10 in trading hours, 2 outside; kill 15 / 5; restart 10 / 0; manual trade 25",
          handsoff.points("stop", wed) == 10 and handsoff.points("stop", sat) == 2 and handsoff.points("kill", sat) == 5
          and handsoff.points("restart", sat) == 0 and handsoff.points("restart", wed) == 10 and handsoff.points("manual_trade", sat) == 25)
    v = handsoff.view(now=wed, weeks=2, path=hp, report_path=os.path.join(d, "none.json"))
    check("no events: 100, 'hands off'", v["weeks"][0]["score"] == 100 and v["weeks"][0]["verdict"].startswith("hands off"))
    e_close = ts(2026, 10, 20, 9, 0)                                   # Tue: manual close of a matched trade
    handsoff.record("manual_close", "reconcile", "account flat, bot ledger LONG 4 micros", now=e_close, path=hp)
    handsoff.record("pause", "phone", "until tomorrow", now=ts(2026, 10, 21, 2, 0), path=hp)
    handsoff.record("stop", "dashboard", "Stop", now=ts(2026, 10, 19, 20, 0), path=hp)      # Mon evening: 2 pts
    handsoff.record("manual_trade", "reconcile", "account LONG 1", now=ts(2026, 10, 14, 11, 0), path=hp)   # last week
    rep = os.path.join(d, "report.json")
    with open(rep, "w", encoding="utf-8") as fh:
        json.dump({"rows": [
            {"status": "matched", "day": "2026-10-20", "entry_t": ts(2026, 10, 20, 4, 0), "exec_usd": -312.5},
            {"status": "missed", "day": "2026-10-21", "entry_t": ts(2026, 10, 21, 3, 5), "missed_usd": 640.0},
            {"status": "extra", "day": "2026-10-14", "entry_t": ts(2026, 10, 14, 10, 0), "live_pnl": -80.0}]}, fh)
    v = handsoff.view(now=wed, weeks=2, path=hp, report_path=rep)
    w0, w1 = v["weeks"]
    by = {i["kind"]: i for i in w0["events"]}
    check("this week: 100 - 20 (manual close) - 5 (pause) - 2 (stop in the evening) = 73",
          w0["score"] == 73 and w0["n"] == 3 and w0["current"], w0)
    check("cost of the manual close from the audit: '-$312' vs the backtest at the same size",
          by["manual_close"]["usd"] == -312.5 and "-$312" in by["manual_close"]["note"], by["manual_close"])
    check("cost of the pause: the backtest trade at 03:05 not taken (+$640 -> -640)",
          by["pause"]["usd"] == -640.0 and "03:05" in by["pause"]["note"], by["pause"])
    check("the evening stop: no backtest trade missed that day", by["stop"]["usd"] == 0.0 and "no backtest trade" in by["stop"]["note"])
    check("last week: the manual trade, 75, extra trade -$80 'not the strategy's P&L'",
          w1["score"] == 75 and w1["events"][0]["usd"] == -80.0 and "not the strategy" in w1["events"][0]["note"], w1)
    cp = handsoff.compact(now=wed, path=hp, report_path=rep)
    check("compact block (heartbeat): score, verdict, <= 5 events", cp["score"] == 73 and len(cp["events"]) == 3
          and len(json.dumps(cp)) < 2000, cp)
    # no_checkin: only once the check-in is in use
    pp = os.path.join(d, "presence.jsonl")
    led = os.path.join(d, "ledger.jsonl")
    e = ts(2026, 10, 21, 4, 0)
    with open(led, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"t": e, "side": "buy", "qty": 3, "entry_t": e, "result": {"ok": True}}) + "\n")
    v = handsoff.view(now=wed, weeks=1, path=hp, report_path=rep, presence_path=pp, ledger_path=led)
    check("no check-in ever used: a trade without presence costs nothing", v["weeks"][0]["score"] == 73)
    presence.check_in("pc", 1, ts(2026, 10, 20, 2, 0), pp)
    v = handsoff.view(now=wed, weeks=1, path=hp, report_path=rep, presence_path=pp, ledger_path=led)
    check("check-in in use: the 04:00 trade with nobody checked in -> no_checkin -5 (68)",
          v["weeks"][0]["score"] == 68 and any(i["kind"] == "no_checkin" for i in v["weeks"][0]["events"]), v["weeks"][0])
    # settings hash: baseline, hand edit, update from GitHub
    repo = os.path.join(d, "repo")
    os.makedirs(repo)
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "t@t")
    git(repo, "config", "user.name", "t")
    lm = os.path.join(repo, "live_model.json")
    with open(lm, "w") as fh:
        fh.write('{"a": 1}')
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "c1")
    sp = os.path.join(d, "s", "handsoff.jsonl")
    os.makedirs(os.path.dirname(sp))
    check("settings: first sight is the baseline (no event)", handsoff.settings_check(sp, repo, now=wed) == [])
    check("settings: unchanged -> nothing", handsoff.settings_check(sp, repo, now=wed) == [])
    with open(lm, "w") as fh:
        fh.write('{"a": 2}')
    ev = handsoff.settings_check(sp, repo, now=wed)
    check("settings: edited by hand (differs from the committed file) -> 'settings' (15 points)",
          [e["kind"] for e in ev] == ["settings"] and handsoff.points("settings", wed) == 15, ev)
    git(repo, "commit", "-qam", "c2")
    with open(lm, "w") as fh:
        fh.write('{"a": 3}')
    git(repo, "commit", "-qam", "c3")
    ev = handsoff.settings_check(sp, repo, now=wed)
    check("settings: a change that equals the committed file (an update) -> 'settings_update' (0 points)",
          [e["kind"] for e in ev] == ["settings_update"] and handsoff.points("settings_update", wed) == 0, ev)
    # server start
    rp = os.path.join(d, "r", "handsoff.jsonl")
    os.makedirs(os.path.dirname(rp))
    done = os.path.join(d, "r", "remote_done.json")
    check("server start after an auto-update (marker): no event", handsoff.note_server_start({"sha": "abc"}, rp, done, now=wed) is None)
    with open(done, "w") as fh:
        json.dump({"last": {"cmd": "restart", "t": wed - 60, "status": "done"}}, fh)
    check("server start right after a remote restart: no event", handsoff.note_server_start(None, rp, done, now=wed) is None)
    r = handsoff.note_server_start(None, rp, done, now=wed + 3600)
    check("a start nobody asked for, Wed 11:00 ET: 'restart' (10 points)", r and r["kind"] == "restart"
          and handsoff.points("restart", r["t"]) == 10, r)
    # reconcile hook: guards.reconcile_tick records a manual trade
    check("handsoff path beside live_state.json is data/handsoff.jsonl",
          os.path.basename(handsoff.path_for(type("B", (), {"state_path": "/x/live_state.json"})())) == "handsoff.jsonl")
    check("tick on a simulated clock: nothing (test harnesses)", handsoff.tick(FakeBot(d, [wed])) == [])


# ---------------------------------------------------------------------------------------------- the PC API
def api_tests(tmp):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from engine import presence_api
    d = os.path.join(tmp, "api")
    os.makedirs(d)
    now = [ts(2026, 10, 21, 2, 10)]
    bot = FakeBot(d, now)
    presence_api.bind(bot)
    app = FastAPI()
    app.include_router(presence_api.router)
    cl = TestClient(app)
    r = cl.post("/api/next/presence/checkin", json={}).json()
    check("POST checkin: ok, 'Present since 02:10 ET'", r["ok"] and r["status"]["line"].startswith("Present since 02:10 ET"), r)
    g = cl.get("/api/next/presence").json()
    check("GET presence: status present, guard OFF, no pause", g["status"]["present"] and g["status"]["guard"] is False and g["pause"] is None, g)
    b = cl.post("/api/next/pause", json={"until": "nope"})
    check("POST pause with a bad until: 400", b.status_code == 400 and not b.json()["ok"])
    p = cl.post("/api/next/pause", json={"until": "tomorrow"}).json()
    check("POST pause tomorrow: ok, active, a hands-off 'pause' event, a log line",
          p["ok"] and cl.get("/api/next/pause").json()["pause"]["until"] == ts(2026, 10, 22, 0, 0)
          and [e["kind"] for e in handsoff.events(handsoff.path_for(bot))] == ["pause"] and any("PAUSE" in t for _, t in bot.logs), p)
    h = cl.get("/api/next/handsoff").json()
    check("GET handsoff: this week 95 with the pause listed", h["weeks"][0]["score"] == 95 and h["weeks"][0]["events"][0]["kind"] == "pause", h["weeks"][0])
    c = cl.post("/api/next/pause/clear", json={}).json()
    check("POST pause/clear: was paused, now none", c["was_paused"] and cl.get("/api/next/pause").json()["pause"] is None)
    o = cl.post("/api/next/presence/checkout", json={}).json()
    check("POST checkout: not present", not o["status"]["present"])
    check("the API never touched the bot (still running, no pushes)", bot.running and not bot.pushed)


if __name__ == "__main__":
    sys.exit(main())
