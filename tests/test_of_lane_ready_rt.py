"""red team #34 (night-of-lane-ready 2026-11-27): the order-flow lane runner and /oflane.
  1. a real / MFFU account is never started or routed (cfg edited by hand, Telegram, the runner)
  2. ONE runner: a second one (heartbeat aged by a slow tick) exits at once and leaves the first one's heartbeat / stop flag;
     no new start from 16:00 ET (the PC update window opens; the lane is flat by 15:55)
  3. /oflane from anyone but the owner's private chat (a group, a stranger, a forward) changes nothing
  4. Sim101 is never picked while ATLAS's week is on, a lane trades it or another process holds its lock
    python -X utf8 -m tests.test_of_lane_ready_rt
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
ET = ZoneInfo("America/New_York")
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"), flush=True)


def et(y, m, d, hh, mm):
    return dt.datetime(y, m, d, hh, mm, tzinfo=ET).timestamp()


def wj(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(o, fh)


def main():
    from engine import of_lane as L, ops_checks as O, tg_cmd as T
    mon = et(2026, 11, 30, 10, 0)                       # a Monday
    # 1 ------------------------------------------------------------------ never a real account
    for acct in ("MFFUEVAL12345", "APEX-1", "Sim101x", "sim101 ; Live1", ""):
        with tempfile.TemporaryDirectory() as td:
            wj(os.path.join(td, "data", "of_lane.json"), {"on": True, "account": acct})
            calls = []
            r = O.of_lane_kick(mon, real=True, root=td, popen=lambda *a, **k: calls.append(a))
            check(f"1. kick refuses account {acct!r}", not calls and r in ("refused: not a simulation account",), r)
            ok, msg = L.set_switch(True, acct or None, root=td) if acct else (False, "")
            if acct:
                check(f"1. set_switch refuses {acct!r} (writes nothing)", not ok and msg.startswith("NOT switched on")
                      and L.load_cfg(td)["account"] == acct, msg)
            tk = L.tick(now=mon, root=td, nd=os.path.join(td, "nt"))
            check(f"1. tick refuses {acct!r} (no adapter)", "ad" not in tk and (tk.get("refused") or tk.get("off")), tk)
    p, say = T.parse_text("/oflane on MFFUEVAL12345")
    check("1. /oflane takes no account name", p is None and "never used" in (say or ""), (p, say))

    # 2 ------------------------------------------------------------------ one runner, none from 16:00
    with tempfile.TemporaryDirectory() as td:
        wj(os.path.join(td, "data", "of_lane.json"), {"on": True, "account": "Sim102", "auto_account": False})
        lk = L.run_lock(td)
        check("2. the first runner takes the run lock", lk is not None)
        wj(os.path.join(td, "data", "of_lane_run.json"), {"pid": 1, "t": int(mon)})
        open(os.path.join(td, "data", "of_lane_stop"), "w").write("x")
        ticks = []
        w = L.loop(td, clock=lambda: mon, sleep=lambda s: None, tick_fn=lambda **k: ticks.append(1) or {"S": {}, "routed": []},
                   max_runs=3)
        check("2. a second runner exits at once without a tick", w == "already running" and not ticks, (w, ticks))
        check("2. ... and leaves the first one's heartbeat + stop flag",
              os.path.exists(os.path.join(td, "data", "of_lane_run.json")) and os.path.exists(os.path.join(td, "data", "of_lane_stop")))
        # another PROCESS sees the lock too (the real case: two detached runners)
        code = ("import sys; sys.path.insert(0, %r); from engine import of_lane as L; print('free' if L.run_lock(%r) else 'held')"
                % (ROOT, td))
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60).stdout.strip()
        check("2. another process sees the run lock held", out == "held", out)
        lk.close()
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60).stdout.strip()
        check("2. released when the first runner ends", out == "free", out)
    for hh, mm, want in ((15, 59, "started (test)"), (16, 0, "too late to start (from 16:00 ET)"), (16, 10, "too late to start (from 16:00 ET)")):
        with tempfile.TemporaryDirectory() as td:
            wj(os.path.join(td, "data", "of_lane.json"), {"on": True, "account": "Sim102"})
            r = O.of_lane_kick(et(2026, 11, 30, hh, mm), real=False, root=td)
            check(f"2. kick at {hh:02d}:{mm:02d} ET -> {want}", r == want, r)

    # 3 ------------------------------------------------------------------ /oflane only from the owner
    owner = "424242"
    base = {"message_id": 5, "text": "/oflane on", "chat": {"id": int(owner), "type": "private"}, "from": {"id": int(owner)}}
    bad = {"group": {**base, "chat": {"id": int(owner), "type": "group"}},
           "stranger": {**base, "chat": {"id": 999, "type": "private"}, "from": {"id": 999}},
           "forward": {**base, "forward_origin": {"type": "user"}},
           "bot": {**base, "from": {"id": int(owner), "is_bot": True}}}
    for k, m in bad.items():
        check(f"3. {k} is not the owner", not T.is_owner(m, owner))
    check("3. the owner's private chat is", T.is_owner(base, owner))
    with tempfile.TemporaryDirectory() as td:
        sent = []

        class H:
            def __call__(self, method, url, data=None, timeout=None, **kw):
                if "getUpdates" in url:
                    return 200, json.dumps({"ok": True, "result": [{"update_id": i + 1, "message": m} for i, m in enumerate(bad.values())]})
                sent.append(url)
                return 200, json.dumps({"ok": True, "result": {}})
        try:
            tc = T.TgCommands(rc=None, cfg_fn=lambda: {"telegram": {"token": "1:a", "chat_id": owner}}, http=H(),
                              path=os.path.join(td, "tg.json"), env={"LE_TG_CMDS": "1"})
            tc.oflane_root = td
            tc.tick(mon)
            check("3. strangers' /oflane on: switch still OFF, no reply", L.load_cfg(td)["on"] is False and not sent, sent)
        except TypeError as e:
            check("3. TgCommands harness", False, e)

    # 4 ------------------------------------------------------------------ Sim101 only when nobody uses it
    with tempfile.TemporaryDirectory() as td:
        nd = os.path.join(td, "NinjaTrader 8")
        os.makedirs(os.path.join(nd, "le_locks"))
        os.makedirs(os.path.join(nd, "le_feed"))
        with open(os.path.join(nd, "le_feed", "accounts.csv"), "w") as fh:
            fh.write(f"name,t,cash\nSim101,{int(time.time())},100000\n")
        lp = os.path.join(nd, "le_locks", "Sim101.lock")
        code = ("import fcntl,sys,time; fh=open(%r,'a+'); fcntl.flock(fh.fileno(), fcntl.LOCK_EX); print('ok', flush=True); "
                "sys.stdin.read()" % lp) if os.name != "nt" else \
               ("import msvcrt,sys; fh=open(%r,'a+'); fh.seek(0); msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1); print('ok', flush=True); "
                "sys.stdin.read()" % lp)
        pr = subprocess.Popen([sys.executable, "-c", code], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        try:
            pr.stdout.readline()
            a, note = L.pick_account(nd)
            check("4. Sim101 locked by another process (START's Sim test / a bot) -> Sim102 + why", a == "Sim102" and "lock" in (note or ""),
                  (a, note))
        finally:
            pr.stdin.close()
            pr.wait(30)
        from engine import atlas_exec as AX
        old = (AX.is_on, AX.lanes)
        try:
            AX.is_on, AX.lanes = (lambda *a, **k: True), (lambda *a, **k: [])
            a, note = L.pick_account(nd)
            check("4. ATLAS's Sim101 week on -> never Sim101", a == "Sim102", (a, note))
            AX.is_on, AX.lanes = (lambda *a, **k: False), (lambda *a, **k: [("Rapid", "Sim101")])
            a, note = L.pick_account(nd)
            check("4. a lane configured on Sim101 -> never Sim101", a == "Sim102", (a, note))
            AX.is_on, AX.lanes = (lambda *a, **k: False), (lambda *a, **k: [])
            a, note = L.pick_account(nd)
            check("4. nobody on Sim101 + no Sim102 -> Sim101 (said so)", a == "Sim101" and "Sim101" in (note or ""), (a, note))
            AX.is_on = lambda *a, **k: (_ for _ in ()).throw(OSError("x"))
            a, note = L.pick_account(nd)
            check("4. ATLAS unreadable -> fails closed (Sim102)", a == "Sim102", (a, note))
        finally:
            AX.is_on, AX.lanes = old
    n = sum(RES)
    print(f"\n{n}/{len(RES)} passed")
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
