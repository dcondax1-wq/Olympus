"""Phone remote control through GitHub (engine/remote_ctl.py, docs/REMOTE_CONTROL.md), against a local bare git repo (no
network): the "phone" commits control/command.json to branch control, the "PC" fetches and runs it.

    python -X utf8 -m tests.test_remote_ctl          (~5 s)

Covers: the control branch template (tools/init_control_branch.py: created once, never overwritten, ignored by the PC),
each command (kill, stop after flat / now, flatten, update, restart, status, start), stale / future / duplicate / unknown /
bad-id commands ignored, update and restart refused when not flat (and in trading hours / unsupervised), kill and flatten
mid-trade on the self-test's fake NinjaTrader with a real LiveBot, no start possible on a real account (whatever else the
command carries), an id recorded before a restart runs (never twice), the heartbeat's "remote" line.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import remote_ctl as rc  # noqa: E402
from tools import init_control_branch as icb  # noqa: E402

ET = rc.ET
RES = []


def check(name, ok, info=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}{(': ' + str(info)) if info and not ok else ''}")
    RES.append(bool(ok))


def git(cwd, *args, inp=None):
    return subprocess.run(["git", *args], cwd=cwd, input=inp, capture_output=True, text=True, timeout=60)


class World:
    def __init__(self):
        self.tmp = tempfile.mkdtemp(prefix="le_rc_")
        self.bare = os.path.join(self.tmp, "bare.git")
        self.pc = os.path.join(self.tmp, "pc")
        self.phone = os.path.join(self.tmp, "phone")
        subprocess.run(["git", "init", "-q", "--bare", self.bare], check=True)
        for d in (self.pc, self.phone):
            subprocess.run(["git", "init", "-q", d], check=True)
            git(d, "remote", "add", "origin", self.bare)
            git(d, "config", "user.name", "t")
            git(d, "config", "user.email", "t@t")
        self.done = os.path.join(self.tmp, "remote_done.json")
        self.notes = []

    def send(self, obj):
        """The owner's edit + commit in the GitHub app: control/command.json on branch control."""
        git(self.phone, "fetch", "-q", "origin", "control")
        if not git(self.phone, "rev-parse", "FETCH_HEAD").returncode:
            git(self.phone, "checkout", "-q", "-B", "control", "FETCH_HEAD")
        else:
            git(self.phone, "checkout", "-q", "--orphan", "control")
        os.makedirs(os.path.join(self.phone, "control"), exist_ok=True)
        with open(os.path.join(self.phone, "control", "command.json"), "w", encoding="utf-8") as f:
            f.write(obj if isinstance(obj, str) else json.dumps(obj))
        git(self.phone, "add", "-A")
        git(self.phone, "commit", "-q", "-m", "cmd")
        r = git(self.phone, "push", "-q", "origin", "control")
        assert not r.returncode, r.stderr

    def ctl(self, bot, hooks=None, env=None, clock=None):
        return rc.RemoteControl(bot, hooks=hooks or {}, cwd=self.pc, done_path=self.done, notify=self.note,
                                log=lambda t: None, env=env if env is not None else {"LE_REMOTE": "1", "LE_SUPERVISED": "1"},
                                clock=clock or time.time)

    def note(self, title, body, key):
        self.notes.append((title, body, key))


class FakeAdapter:
    name = "fake"

    def __init__(self):
        self.legs = []


class FakeBot:
    def __init__(self, running=True, position=None):
        self.running = running
        self.cfg = {"sym": "NQ", "adapter": "ninjatrader", "nt_account": "Sim101"}
        self.state = {"position": position}
        self.adapter = FakeAdapter()
        self._open_routed = None
        self.kill = False
        self.health = {}

    def _save_state(self):
        pass


def recorder():
    calls = []

    def mk(name, ret=None):
        def fn(*a):
            calls.append((name, a))
            return ret if ret is not None else {"ok": True}
        return fn
    hooks = {n: mk(n) for n in ("kill", "stop", "flatten", "beat")}
    hooks["start"] = mk("start")
    hooks["exit"] = mk("exit")
    return hooks, calls


def cmd(c, ts=None, **kw):
    ts = time.time() if ts is None else ts
    return {"id": f"{c}-{int(ts)}-{len(kw)}{os.urandom(2).hex()}", "ts": int(ts), "cmd": c, **kw}


def names(calls):
    return [c[0] for c in calls]


def main():
    w = World()
    try:
        # ---- the control branch template
        r1 = icb.init(w.pc, "origin")
        r2 = icb.init(w.pc, "origin")
        ls = git(w.pc, "ls-tree", "-r", "--name-only", r1.get("commit") or "HEAD").stdout.split()
        check("init_control_branch: creates control (command.json + README.md), second run leaves it alone",
              r1["status"] == "created" and r2["status"] == "exists" and ls == ["control/README.md", "control/command.json"], (r1, r2, ls))
        dry = icb.init(w.pc, "origin", dry_run=True)
        check("init_control_branch --dry-run on an existing branch: 'exists', nothing pushed", dry["status"] == "exists", dry)
        hooks, calls = recorder()
        bot = FakeBot()
        c = w.ctl(bot, hooks)
        out = c.tick()
        check("the blank template is ignored silently (no command, no notice, no heartbeat push)",
              out == [] and not calls and not w.notes, (out, calls, w.notes))

        # ---- status
        w.send(cmd("status"))
        out = c.tick()
        check("status: done, a phone notice with the bot's status, a fresh heartbeat",
              out and out[0][2] == "done" and "RUNNING" in w.notes[-1][1] and names(calls) == ["beat"], (out, calls, w.notes[-1:]))
        hb = rc.hb_field(w.done, env={"LE_REMOTE": "1"})
        check("heartbeat 'remote' block: 'remote: last cmd status done at HH:MM ET', on",
              hb["on"] and hb["last"].startswith("remote: last cmd status done at ") and hb["last"].endswith(" ET"), hb)

        # ---- duplicate: the same file read again
        calls.clear()
        n0 = len(w.notes)
        out = c.tick()
        check("duplicate id (the same file on the next fetch): not run again, no notice", out == [] and not calls and len(w.notes) == n0)

        # ---- stale / future / unknown / bad id / config change
        calls.clear()
        w.send({"commands": [cmd("kill", ts=time.time() - 16 * 60), cmd("kill", ts=time.time() + 600),
                             {"id": "x-1", "ts": int(time.time()), "cmd": "set_param", "risk_usd": 5000},
                             {"id": "bad id with spaces", "ts": int(time.time()), "cmd": "kill"},
                             {"id": "noTs-1", "cmd": "kill"}]})
        out = c.tick()
        st = [o[2] for o in out]
        check("16-min-old kill, a future ts, a config command, a bad id, no ts: all ignored, nothing called",
              st == ["ignored"] * 5 and not [x for x in calls if x[0] != "beat"] and "too old" in out[0][3] and "future" in out[1][3]
              and "never accepted" in out[2][3], out)
        n0 = len(w.notes)
        out = c.tick()
        check("ignored ids are not reported again on the next fetch (a bad id cannot be stored: skipped, never a notice)",
              [o[3][:6] for o in out] == ["bad id"] and len(w.notes) == n0, (out, w.notes[n0:]))

        # ---- ISO ts and ms ts
        check("parse_ts: seconds, ms, ISO Z, ISO offset, junk",
              rc.parse_ts(1760983320) == 1760983320 and rc.parse_ts(1760983320000) == 1760983320
              and rc.parse_ts("2026-10-20T18:02:00Z") == dt.datetime(2026, 10, 20, 18, 2, tzinfo=dt.timezone.utc).timestamp()
              and rc.parse_ts("2026-10-20T14:02:00-04:00") == rc.parse_ts("2026-10-20T18:02:00Z") and rc.parse_ts("soon") is None)

        # ---- stop after flat
        calls.clear()
        bot.state["position"] = {"entry_t": 1, "dir": 1, "qty": 2}
        w.send(cmd("stop", now=False))
        out = c.tick()
        check("stop while in a trade: pending, bot not stopped yet, notice 'will stop once flat'",
              out[0][2] == "pending" and "stop" not in names(calls) and "once flat" in w.notes[-1][1]
              and rc.hb_field(w.done)["pending_stop"], (out, calls))
        c.tick()
        check("still in the trade on the next pass: still waiting", "stop" not in names(calls))
        bot.state["position"] = None
        c.tick()
        check("flat: the pending stop runs once (stop hook), notice 'bot stopped (now flat)'",
              names(calls).count("stop") == 1 and "now flat" in w.notes[-1][1] and not rc.hb_field(w.done)["pending_stop"], calls)
        c.tick()
        check("not stopped twice", names(calls).count("stop") == 1)

        # ---- stop now
        calls.clear()
        bot.running = True
        bot.state["position"] = {"entry_t": 2, "dir": -1, "qty": 3}
        w.send(cmd("stop", now=True))
        out = c.tick()
        check("stop now in a trade: flatten then stop", out[0][2] == "done" and names(calls)[:2] == ["flatten", "stop"], calls)

        # ---- flatten (fake hooks)
        calls.clear()
        w.send(cmd("flatten"))
        out = c.tick()
        check("flatten: the flatten hook, the bot is not stopped", out[0][2] == "done" and names(calls)[0] == "flatten"
              and "stop" not in names(calls), calls)

        # ---- update / restart refused when not flat
        calls.clear()
        sat = dt.datetime(2026, 10, 24, 12, 0, tzinfo=ET).timestamp()       # Saturday noon: no trading hours
        wed = dt.datetime(2026, 10, 21, 10, 0, tzinfo=ET).timestamp()       # Wednesday 10:00 ET: trading hours
        upd = {"n": 0}

        def fake_update():
            upd["n"] += 1
            return {"status": "updated", "restart": True, "old": "a" * 40, "new": "b" * 40, "reason": "ok"}
        hooks["update"] = fake_update
        bot.running = True
        bot.state["position"] = {"entry_t": 3, "dir": 1, "qty": 1}
        cs = w.ctl(bot, hooks, clock=lambda: sat)
        w.send({"commands": [cmd("update", ts=sat), cmd("restart", ts=sat)]})
        out = cs.tick()
        check("update and restart in a trade: both refused 'not flat', no update run, no exit",
              [o[2] for o in out] == ["refused", "refused"] and all("not flat" in o[3] for o in out) and upd["n"] == 0
              and "exit" not in names(calls), out)
        bot.state["position"] = None
        bot.state["setups"] = {"x": {"stage": "limit"}}
        w.send(cmd("restart", ts=sat))
        out = cs.tick()
        check("restart with a LIT entry pending (limit / 1m CISD): refused", out[0][2] == "refused" and "pending" in out[0][3], out)
        bot.state.pop("setups")
        cu = w.ctl(bot, hooks, env={"LE_REMOTE": "1"}, clock=lambda: sat)
        w.send(cmd("restart", ts=sat))
        out = cu.tick()
        check("restart when the server is not supervised by run_bot.ps1: refused", out[0][2] == "refused" and "run_bot" in out[0][3], out)
        cw = w.ctl(bot, hooks, clock=lambda: wed)
        w.send({"commands": [cmd("update", ts=wed), cmd("restart", ts=wed)]})
        out = cw.tick()
        check("flat but Wednesday 10:00 ET: update refused (trading hours) and restart refused while the bot runs",
              [o[2] for o in out] == ["refused", "refused"] and "trading hours" in out[0][3] and "trading hours" in out[1][3]
              and upd["n"] == 0, out)

        # ---- restart when flat: id recorded first, exit 75, never twice
        calls.clear()
        rid = cmd("restart", ts=sat)
        w.send(rid)
        out = cs.tick()
        d = rc.load_done(w.done)
        check("restart when flat (Saturday): exit(75), the id stored as done before the exit",
              ("exit", (75,)) in calls and d["done"][rid["id"]]["status"] == "done", (calls, d.get("last")))
        calls.clear()
        cs.tick()
        check("after the restart the same command is not run again", "exit" not in names(calls))

        # ---- update when flat (Saturday): the update runs, then the restart
        calls.clear()
        w.send(cmd("update", ts=sat))
        out = cs.tick()
        check("update when flat outside trading hours: update runs once, then exit(75)",
              upd["n"] == 1 and ("exit", (75,)) in calls and out[0][2] == "done", (out, calls))
        hooks["update"] = lambda: {"status": "up_to_date", "reason": "at bbbbbbb"}
        cs = w.ctl(bot, hooks, clock=lambda: sat)
        calls.clear()
        w.send(cmd("update", ts=sat))
        out = cs.tick()
        check("update already up to date: done, no restart", out[0][2] == "done" and "exit" not in names(calls), out)
        hooks["update"] = lambda: {"status": "rolled_back", "reason": "self-test failed; rolled back", "alert": True}
        cs = w.ctl(bot, hooks, clock=lambda: sat)
        w.send(cmd("update", ts=sat))
        out = cs.tick()
        check("update rolled back: failed, no restart", out[0][2] == "failed" and "exit" not in names(calls), out)
        hooks.pop("update")

        # ---- start: Sim only
        calls.clear()
        bot.running = False
        w.send({"commands": [cmd("start", account="MFFUEVAL12345"),
                             cmd("start", account="Sim101", adapter="tradovate", confirm="I AM LIVE", nt_account="MFFUEVAL12345",
                                 armed=True, present=True, risk_usd=9999)]})
        out = c.tick()
        sb = [x for x in calls if x[0] == "start"]
        body = sb[0][1][0] if sb else {}
        check("start on a real account: refused, the start hook never called", out[0][2] == "refused" and "REAL account" in out[0][3]
              and len(sb) == 1, out)
        check("start on Sim101 carrying adapter / confirm / account / risk fields: only a Sim101 NinjaTrader body is built "
              "(no confirm, no present, no extra fields)",
              out[1][2] == "done" and body.get("nt_account") == "Sim101" and body.get("adapter") == "ninjatrader"
              and "confirm" not in body and "present" not in body and "risk_usd" not in body and "accounts" not in body, body)
        from engine.ninjatrader import is_sim
        for acct in ("Sim101x", "MFFU Sim101", "", "LIVE123", "../Sim101"):
            calls.clear()
            w.send(cmd("start", account=acct or None))
            out = c.tick()
            started = [x for x in calls if x[0] == "start"]
            body = started[0][1][0] if started else {}
            ok = (not started) if not (acct == "" or is_sim(acct)) else (body.get("nt_account") in ("Sim101", acct))
            check(f"start account {acct!r}: real names never reach the start hook", ok and all(is_sim(b[1][0].get("nt_account", "Sim101"))
                                                                                         for b in started), (out, started))
        calls.clear()
        bot.running = True
        w.send(cmd("start"))
        out = c.tick()
        check("start while running: refused", out[0][2] == "refused" and "start" not in names(calls), out)

        # ---- kill (fake hooks)
        calls.clear()
        w.send(cmd("kill"))
        out = c.tick()
        check("kill: the kill hook, done notice", out[0][2] == "done" and names(calls)[0] == "kill" and "KILL" in w.notes[-1][1], out)

        # ---- pause / resume_entries / present (engine/entry_pause.py, engine/presence.py)
        pause_tests(w, bot, hooks, calls)

        # ---- off without LE_REMOTE
        co = w.ctl(bot, hooks, env={})
        check("off unless LE_REMOTE=1 (no thread)", co.start() is False and not rc.enabled({}) and rc.enabled({"LE_REMOTE": "1"}))

        # ---- real LiveBot + the fake NinjaTrader: kill and flatten mid-trade
        live_tests(w)

        # ---- the heartbeat carries the block
        from engine import heartbeat
        old = rc.DONE_PATH
        try:
            rc.DONE_PATH = w.done
            pl = heartbeat.Heartbeat(FakeBot()).payload()
        finally:
            rc.DONE_PATH = old
        check("heartbeat payload has 'remote' with the last command line",
              isinstance(pl.get("remote"), dict) and "remote: last cmd" in str(pl["remote"].get("last")), pl.get("remote"))
    finally:
        shutil.rmtree(w.tmp, ignore_errors=True)
    n, ok = len(RES), sum(RES)
    print(f"\n{ok}/{n} remote-control checks passed")
    return 0 if ok == n else 1


def pause_tests(w, bot, hooks, calls):
    from engine import entry_pause, handsoff, presence
    wed = dt.datetime(2026, 10, 21, 10, 0, tzinfo=ET).timestamp()       # Wednesday 10:00 ET
    c = w.ctl(bot, hooks, clock=lambda: wed)
    calls.clear()
    n_ho = len(handsoff.events(c.handsoff_path))
    w.send(cmd("pause", ts=wed, until="tomorrow"))
    out = c.tick()
    p = entry_pause.load(c.pause_path)
    mid = dt.datetime(2026, 10, 22, 0, 0, tzinfo=ET).timestamp()
    check("pause until tomorrow: done, data file until 00:00 ET tonight, notice says so, no order hook called",
          out and out[0][2] == "done" and p and p["until"] == mid and "no new entries until tomorrow" in w.notes[-1][1]
          and not [x for x in calls if x[0] != "beat"], (out, p, calls))
    pauses = lambda: [e for e in handsoff.events(c.handsoff_path) if e["kind"] == "pause" and e["src"] == "phone"]
    check("pause is a hands-off event (phone)", len(handsoff.events(c.handsoff_path)) == n_ho + 1 and len(pauses()) == 1)
    hb = rc.hb_field(w.done, env={"LE_REMOTE": "1"})
    check("heartbeat 'remote' block carries the pause, presence and the hands-off score",
          (hb.get("pause") or {}).get("until") == mid and "presence" in hb and isinstance(hb.get("handsoff"), dict)
          and hb["handsoff"]["score"] <= 100, hb)
    w.send(cmd("pause", ts=wed, until="14:30"))
    out = c.tick()
    p = entry_pause.load(c.pause_path)
    check("pause until 14:30: today 14:30 ET (the later command replaces the first)",
          out[0][2] == "done" and p["until"] == dt.datetime(2026, 10, 21, 14, 30, tzinfo=ET).timestamp(), (out, p))
    w.send({"commands": [cmd("pause", ts=wed, until="25:00"), cmd("pause", ts=wed), cmd("pause", ts=wed, until="2027-06-01")]})
    out = c.tick()
    check("pause with a bad time / no until / more than 14 days ahead: refused, the running pause is kept",
          [o[2] for o in out] == ["refused"] * 3 and entry_pause.load(c.pause_path)["until"] == p["until"], out)
    w.send(cmd("resume_entries", ts=wed))
    out = c.tick()
    check("resume_entries: done 'pause lifted', file gone", out[0][2] == "done" and "pause lifted" in out[0][3]
          and entry_pause.load(c.pause_path) is None, out)
    w.send(cmd("resume_entries", ts=wed))
    out = c.tick()
    check("resume_entries with no pause: done 'no pause was running'", "no pause was running" in out[0][3], out)
    w.send(cmd("present", ts=wed, hours=2))
    out = c.tick()
    ev = presence.events(c.presence_path)
    check("present: a phone check-in line in presence.jsonl (2 h), notice 'present until 12:00 ET', no order hook",
          out[0][2] == "done" and ev and ev[-1]["src"] == "phone" and ev[-1]["hours"] == 2.0 and "12:00 ET" in out[0][3]
          and not [x for x in calls if x[0] not in ("beat",)], (out, ev))
    check("present / resume_entries / status are not hands-off events",
          len(handsoff.events(c.handsoff_path)) == n_ho + 2 and len(pauses()) == 2, handsoff.events(c.handsoff_path))


def live_tests(w):
    from engine import live
    from engine import ninjatrader as N
    folder = os.path.join(w.tmp, "NinjaTrader 8")
    fake = N._FakeNT(folder)
    now = [dt.datetime(2026, 10, 22, 10, 5, 3, tzinfo=ET).timestamp()]

    def make_bot(tag):
        bot = live.LiveBot()
        bot.clock = lambda: now[0]
        bot.state_path = os.path.join(w.tmp, f"live_state_{tag}.json")
        bot._remember = lambda *a, **kw: None
        r = bot.start({"sym": "NQ", "tf": "5m", "adapter": "ninjatrader", "armed": True, "data": "ninjatrader", "nt_folder": folder,
                       "nt_state_path": os.path.join(w.tmp, f"nt_{tag}.json"), "nt_audit_log": os.path.join(w.tmp, "oif.log")},
                      spawn=False)
        assert r["ok"], r
        ad = bot.adapter
        ad.clock = lambda: now[0]
        ad._sleep = lambda s: (fake.process(), now.__setitem__(0, now[0] + s))
        ad._alert_fn = lambda *a: None
        t_in = int(now[0]) - 3
        pos = {"entry_t": t_in, "dir": 1, "qty": 2, "entry": 25020.0, "stop": 24990.0, "target": 25080.0}
        rr = bot._route({"sym": "NQ", "side": "buy", "qty": 2, "stop": 24990.0, "target": 25080.0, "entry": 25020.0, "entry_t": t_in})
        bot._open_routed, bot._open_qty = t_in, 2
        bot.state = {"position": dict(pos)}
        assert rr.get("ok"), rr
        return bot

    P = ("Sim101", "MNQ 12-26")
    # kill mid-trade: the server's kill hook = BOT.kill_switch (+ auto-resume off, autostart cleared)
    bot = make_bot("k")
    in_trade = fake.pos.get(P, [0])[0] == 2
    c = w.ctl(bot, {"kill": bot.kill_switch, "stop": bot.stop, "flatten": bot.flatten_now, "beat": lambda: {"ok": True}},
              clock=lambda: now[0])
    w.send(cmd("kill", ts=now[0]))
    out = c.tick()
    check("LiveBot + fake NinjaTrader: remote kill mid-trade -> FLATTENEVERYTHING, account flat, kill flag, bot stopped",
          in_trade and out and out[0][2] == "done" and fake.pos.get(P, [0])[0] == 0 and bot.kill and not bot.running
          and any("FLATTENEVERYTHING" in ln for _, ls in fake.files for ln in ls), (out, fake.pos))
    # flatten mid-trade: position closed, bot keeps running, no kill flag, no new entry today
    now[0] += 3600
    fake.move(25020.0)
    bot = make_bot("f")
    in_trade = fake.pos.get(P, [0])[0] == 2
    c = w.ctl(bot, {"kill": bot.kill_switch, "stop": bot.stop, "flatten": bot.flatten_now, "beat": lambda: {"ok": True}},
              clock=lambda: now[0])
    w.send(cmd("flatten", ts=now[0]))
    out = c.tick()
    check("LiveBot + fake NinjaTrader: remote flatten mid-trade -> account flat, bot still running, no kill flag",
          in_trade and out and out[0][2] == "done" and fake.pos.get(P, [0])[0] == 0 and bot.running and not bot.kill
          and bot._open_routed is None and bot._no_entries_day == live.trading_day(now[0]), (out, fake.pos.get(P)))
    k = len(fake.files)
    bot._route_signals({"trades": [], "events": []}, "NQ", int(now[0]), 300)
    check("after the flatten, the model's still-open position is not re-routed, no modify / add sent", len(fake.files) == k)
    t2 = int(now[0]) + 300
    now[0] = t2 + 310
    bot.state = {"position": {"entry_t": t2, "dir": 1, "qty": 2, "entry": 25020.0, "stop": 24990.0, "target": 25080.0}}
    bot._route_signals({"trades": [], "events": []}, "NQ", int(now[0]), 300)
    check("a new model entry later the same day is NOT routed (remote flatten = done for today)",
          len(fake.files) == k and fake.pos.get(P, [0])[0] == 0 and t2 in bot._blocked_entries, fake.pos.get(P))

    # pause mid-trade: the open trade keeps its bracket, a new entry is blocked by the guard; resume lifts only the pause
    from engine import guards, entry_pause
    now[0] += 3600
    fake.move(25020.0)
    bot = make_bot("p")
    k = len(fake.files)
    c = w.ctl(bot, {"kill": bot.kill_switch, "stop": bot.stop, "flatten": bot.flatten_now, "beat": lambda: {"ok": True}},
              clock=lambda: now[0])
    w.send(cmd("pause", ts=now[0], until="tomorrow"))
    out = c.tick()
    ent = {"entry_t": int(now[0]) + 600, "dir": 1, "qty": 1, "entry": 25020.0, "stop": 24990.0, "target": 25080.0}
    why = guards.entry_block(bot, ent, bot._entry_action(ent, 1, "NQ"), 1, int(now[0]) + 610) or ""
    check("LiveBot: remote pause mid-trade -> done, nothing sent to NinjaTrader, position still 2, bot running",
          out and out[0][2] == "done" and len(fake.files) == k and fake.pos.get(P, [0])[0] == 2 and bot.running
          and c.pause_path == entry_pause.path_for(bot) and "open trade keeps its stop and target" in out[0][3], (out, fake.pos.get(P)))
    check("LiveBot: a new entry while paused -> GUARD 'paused by you until tomorrow'", "paused by you until tomorrow" in why, why)
    w.send(cmd("resume_entries", ts=now[0]))
    out = c.tick()
    why = guards.entry_block(bot, ent, bot._entry_action(ent, 1, "NQ"), 1, int(now[0]) + 610) or ""
    check("LiveBot: resume_entries -> the pause no longer blocks (other guards unchanged)", out[0][2] == "done" and "paused" not in why, why)


if __name__ == "__main__":
    sys.exit(main())
