"""night-of-lane-ready 2026-11-27: the order-flow lane made ready to switch on from the phone (fake Telegram, fake NinjaTrader folder,
temp repo roots; nothing real can trade).
  a. account: Sim102 when NinjaTrader lists it; Sim101 (said so) when Sim102 is missing and nothing else uses Sim101; Sim102 + the
     how-to when Sim101 is busy (ATLAS's Sim101 week, a lane on Sim101, a process holding its lock); a real account never
  b. Telegram /oflane on|off|status: owner's private chat only, answered without the control path, Sim only, plain words
  c. engine/ops_checks.of_lane_kick: 09:20-16:15 ET weekdays, only on + Sim, detached BELOW_NORMAL, never twice, kill, the 16:15 stop
  d. the runner loop: heartbeat, exits only while flat (stop flag / OFF / kill / 16:10)
  e. the decision card draft
    python -X utf8 -m tests.test_of_lane_ready
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import tempfile
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
ET = ZoneInfo("America/New_York")
RES: list = []
OWNER = "424242"
TOKEN = "123:abc"


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"), flush=True)


def world(td, accounts=("Sim101",), cfg=None):
    nd = os.path.join(td, "NinjaTrader 8")
    for sub in ("le_feed", "outgoing", "incoming", "le_locks"):
        os.makedirs(os.path.join(nd, sub), exist_ok=True)
    os.makedirs(os.path.join(td, "data"), exist_ok=True)
    if accounts is not None:
        with open(os.path.join(nd, "le_feed", "accounts.csv"), "w") as fh:
            fh.write("name,t,cash\n" + "".join(f"{a},{int(time.time())},100000\n" for a in accounts))
    from engine import of_lane as L
    json.dump({**L.DEFAULT_CFG, "nt_folder": nd, **(cfg or {})}, open(os.path.join(td, "data", L.CFG_NAME), "w"))
    return nd


class FakeTG:
    def __init__(self):
        self.queue, self.sent, self.n = [], [], 500

    def msg(self, text, chat=OWNER, frm=None, ctype="private", fwd=False):
        self.n += 1
        m = {"message_id": self.n, "date": int(time.time()), "text": text, "chat": {"id": int(chat), "type": ctype},
             "from": {"id": int(frm or chat), "is_bot": False}}
        if fwd:
            m["forward_date"] = int(time.time())
        self.queue.append({"update_id": self.n, "message": m})

    def __call__(self, method, url, body=None, headers=None):
        q = json.loads(body.decode()) if body else {}
        if url.endswith("/getUpdates"):
            off = int(q.get("offset") or 0)
            return 200, json.dumps({"ok": True, "result": [u for u in self.queue if u["update_id"] >= off]})
        if url.endswith("/sendMessage"):
            self.sent.append(q.get("text") or "")
            return 200, json.dumps({"ok": True})
        return 404, "{}"


class NoControl:
    """The control path (engine/remote_ctl): /oflane must never reach it."""
    busy = False
    done_path = os.devnull
    calls: list = []

    def run_external(self, cmds, now, reply=None, tg=None):
        self.calls.append(cmds)
        return []


def main():
    from engine import of_lane as L, ops_checks as OC, tg_cmd as T, atlas_exec as AX
    real_on, real_lanes = AX.is_on, AX.lanes
    AX.is_on, AX.lanes = (lambda *a, **k: False), (lambda: [])
    try:
        # ---- a. account choice
        with tempfile.TemporaryDirectory() as td:
            nd = world(td, ("Sim101", "Sim102"))
            a1 = L.pick_account(nd)
            nd = world(td, ("Sim101",))
            a2 = L.pick_account(nd)
            AX.is_on = lambda *a, **k: True
            a3 = L.pick_account(nd)
            AX.is_on = lambda *a, **k: False
            AX.lanes = lambda: [("ATLAS account B", "Sim101")]
            a4 = L.pick_account(nd)
            AX.lanes = lambda: []
            import fcntl
            lp = os.path.join(nd, "le_locks", "Sim101.lock")
            fh = open(lp, "a+")
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            a5 = L.pick_account(nd)
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN); fh.close()
            a6 = L.pick_account(nd)
            os.remove(os.path.join(nd, "le_feed", "accounts.csv"))
            a7 = L.pick_account(nd)
        check("a. NinjaTrader lists Sim102 -> Sim102, nothing to say", a1 == ("Sim102", None), a1)
        check("a. Sim102 missing + Sim101 free -> Sim101, said plainly (+ how to add Sim102 later)",
              a2[0] == "Sim101" and "Sim102 is not in NinjaTrader" in a2[1] and "Add Sim account" in a2[1], a2)
        check("a. ATLAS's Sim101 week on -> never Sim101 (Sim102 + the how-to + why)", a3[0] == "Sim102" and "Sim101 week" in a3[1]
              and "Add Sim account" in a3[1], a3)
        check("a. an ATLAS lane configured on Sim101 -> never Sim101", a4[0] == "Sim102" and "trades Sim101" in a4[1], a4)
        check("a. another process holds the Sim101 account lock -> never Sim101", a5[0] == "Sim102" and "lock" in a5[1], a5)
        check("a. the lock released again -> Sim101 (the probe never keeps the lock)", a6[0] == "Sim101", a6)
        check("a. no fresh account list (cannot tell) -> Sim102 + 'could not check' (never guesses Sim101)",
              a7[0] == "Sim102" and "could not check" in a7[1].lower(), a7)
        # ---- b. Telegram
        with tempfile.TemporaryDirectory() as td:
            nd = world(td, ("Sim101",))
            os.makedirs(os.path.join(td, "research", "evalplan"))
            json.dump({"line": "Order flow ladder step 0 (paper forward): watching. 0 / 20 forward trades."},
                      open(os.path.join(td, "research", "evalplan", "ladder.json"), "w"))
            day = dt.datetime.now(ET).strftime("%Y-%m-%d")
            json.dump({"day": day, "line": "OF paper Nov 27: 1 trade, +2.0R (1 micro +$48)"}, open(os.path.join(td, "data", "of_paper.json"), "w"))
            fake = FakeTG()
            ctl = NoControl()
            poll = T.TgCommands(ctl, cfg_fn=lambda: {"telegram": {"token": TOKEN, "chat_id": OWNER}}, http=fake,
                                path=os.path.join(td, "tg.json"), env={}, started_at=time.time())
            poll.oflane_root = td

            def say(text, **k):
                fake.sent.clear()
                fake.msg(text, **k)
                poll.tick()
                return list(fake.sent)
            cfgp = os.path.join(td, "data", L.CFG_NAME)
            r_strange = say("/oflane on", chat="999")
            c0 = json.load(open(cfgp))
            r_fwd = say("/oflane on", fwd=True)
            c1 = json.load(open(cfgp))
            check("b. a stranger's / a forwarded /oflane on: no reply, nothing switched", not r_strange and not r_fwd
                  and c0["on"] is False and c1["on"] is False, (r_strange, r_fwd))
            r_real = say("/oflane on MFFUEVAL123")
            check("b. /oflane on <an account>: refused, nothing switched (it never takes an account)", r_real and "never used" in r_real[0]
                  and json.load(open(cfgp))["on"] is False, r_real)
            r_on = say("/oflane on")
            c2 = json.load(open(cfgp))
            check("b. /oflane on: switch ON for the Sim account (Sim101 here: Sim102 missing, Sim101 free), said in plain words",
                  c2["on"] is True and c2["account"] == "Sim101" and r_on and "ON for Sim101" in r_on[0]
                  and "simulation money" in r_on[0] and "Sim102 is not in NinjaTrader" in r_on[0], (c2, r_on))
            check("b. /oflane on: today's paper stats + the ladder step + when it starts",
                  "OF paper Nov 27" in r_on[0] and "ladder step 0" in r_on[0] and "09:20 ET" in r_on[0], r_on)
            r_st = say("/oflane status")
            check("b. /oflane status: account, today's trades, the ladder step", r_st and "Order-flow lane: ON | account Sim101" in r_st[0]
                  and "OF lane" not in "" and "ladder step 0" in r_st[0] and "Paper bot today" in r_st[0], r_st)
            r_off = say("/oflane off")
            check("b. /oflane off: OFF in plain words", json.load(open(cfgp))["on"] is False and r_off and "OFF" in r_off[0], r_off)
            json.dump({**json.load(open(cfgp)), "account": "MFFUEVAL123", "auto_account": False}, open(cfgp, "w"))
            r_bad = say("/oflane on")
            check("b. a hand-edited switch naming a real account: /oflane on is refused, stays OFF",
                  r_bad and "NOT switched on" in r_bad[0] and json.load(open(cfgp))["on"] is False, r_bad)
            check("b. /oflane never went through the control path (remote_ctl)", ctl.calls == [], ctl.calls)
            check("b. /help lists /oflane as the practice account", "/oflane" in T.HELP and "Sim" in T.HELP)
        # ---- c. the runner kick
        with tempfile.TemporaryDirectory() as td:
            nd = world(td, ("Sim101",))
            calls = []
            pop = lambda *a, **k: calls.append((a, k))   # noqa: E731
            wed = lambda h, m: int(dt.datetime(2026, 12, 2, h, m, tzinfo=ET).timestamp())   # noqa: E731
            k = {"root": td, "popen": pop}
            r0 = OC.of_lane_kick(wed(9, 10), **k)
            r1 = OC.of_lane_kick(wed(9, 21), **k)
            L.set_switch(True, root=td)
            r2 = OC.of_lane_kick(wed(9, 21), **k)
            r3 = OC.of_lane_kick(wed(9, 22), **k)
            json.dump({"pid": 1, "t": wed(9, 30)}, open(os.path.join(td, "data", L.RUN_NAME), "w"))
            r4 = OC.of_lane_kick(wed(9, 31), **k)
            json.dump({"pid": 1, "t": wed(16, 14)}, open(os.path.join(td, "data", L.RUN_NAME), "w"))
            r5 = OC.of_lane_kick(wed(16, 15), **k)
            stop = os.path.exists(os.path.join(td, "data", L.STOP_NAME))
            r6 = OC.of_lane_kick(int(dt.datetime(2026, 12, 5, 10, 0, tzinfo=ET).timestamp()), **k)
            os.remove(os.path.join(td, "data", L.RUN_NAME))
            r7 = OC.of_lane_kick(wed(11, 0) + 86400, **k)              # the next day: yesterday's stop flag cleared at the start
            stop2 = os.path.exists(os.path.join(td, "data", L.STOP_NAME))
            json.dump({"kill": True}, open(os.path.join(td, "data", "live_state.json"), "w"))
            os.remove(os.path.join(td, "data", "of_lane_start.json"))
            r8 = OC.of_lane_kick(wed(11, 0) + 2 * 86400, **k)
            os.remove(os.path.join(td, "data", "live_state.json"))
            c = json.load(open(os.path.join(td, "data", L.CFG_NAME)))
            json.dump({**c, "account": "MFFUEVAL123"}, open(os.path.join(td, "data", L.CFG_NAME), "w"))
            r9 = OC.of_lane_kick(wed(11, 0) + 2 * 86400, **k)
        check("c. not before 09:20 ET; OFF -> not started", r0 is None and r1 == "off", (r0, r1))
        argv = calls[0][0][0] if calls else []
        check("c. ON + Sim at 09:21 -> `-m engine.of_lane loop` started detached (no window, below the bot)",
              r2 == "started" and argv[-3:] == ["-m", "engine.of_lane", "loop"] and calls[0][1]["stdout"] is not None
              and ("creationflags" in calls[0][1] or "preexec_fn" in calls[0][1]), (r2, calls[:1]))
        check("c. never twice: a start < 3 min ago = 'starting', a fresh heartbeat = 'running'", r3 == "starting" and r4 == "running"
              and len(calls) == 2 - 1 + (1 if r7 == "started" else 0), (r3, r4, len(calls)))
        check("c. 16:15 ET with the runner alive -> the stop flag (it exits once flat)", r5 == "stop sent" and stop, r5)
        check("c. weekend -> nothing; the next day the old stop flag is cleared and it starts", r6 is None and r7 == "started" and not stop2,
              (r6, r7, stop2))
        check("c. kill switch on -> not started; a real account in the switch -> refused", r8 == "kill" and r9.startswith("refused"), (r8, r9))
        src = open(os.path.join(ROOT, "engine", "ops_checks.py"), encoding="utf-8").read()
        check("c. the scheduled ops tick calls of_lane_kick (scheduled runs only, like of_paper_kick)",
              "        of_paper_kick(now)\n        of_lane_kick(now)" in src)
        check("c. the Windows start is BELOW_NORMAL + DETACHED + NO_WINDOW", "0x00004000" in src.split("def of_lane_kick")[1].split("def of_paper_line")[0])
        # ---- d. the loop
        with tempfile.TemporaryDirectory() as td:
            world(td, ("Sim101",))
            L.set_switch(True, root=td)
            t = [float(dt.datetime(2026, 12, 2, 10, 0, tzinfo=ET).timestamp())]
            beats = []

            def tk(now, root, ad):
                beats.append(os.path.exists(os.path.join(root, "data", L.RUN_NAME)))
                return {"S": {}, "routed": []}
            open(os.path.join(td, "data", L.STOP_NAME), "w").close()
            S = L.load_state(td)
            S["trades"].append({"id": "x", "row_id": "x", "status": "open", "d": 1, "day": "2026-12-02"})
            L.save_state(S, td)
            w1 = L.loop(td, clock=lambda: t[0], sleep=lambda s: t.__setitem__(0, t[0] + s), tick_fn=tk, max_runs=5)
            S["trades"][0]["status"] = "closed"
            L.save_state(S, td)
            open(os.path.join(td, "data", L.STOP_NAME), "w").close()
            w2 = L.loop(td, clock=lambda: t[0], sleep=lambda s: t.__setitem__(0, t[0] + s), tick_fn=tk, max_runs=50)
            gone = not os.path.exists(os.path.join(td, "data", L.RUN_NAME)) and not os.path.exists(os.path.join(td, "data", L.STOP_NAME))
            L.set_switch(False, root=td)
            w3 = L.loop(td, clock=lambda: t[0], sleep=lambda s: t.__setitem__(0, t[0] + s), tick_fn=tk, max_runs=50)
            L.set_switch(True, root=td)
            open(os.path.join(td, "data", L.KILL_NAME), "w").close()
            w4 = L.loop(td, clock=lambda: t[0], sleep=lambda s: t.__setitem__(0, t[0] + s), tick_fn=tk, max_runs=50)
            os.remove(os.path.join(td, "data", L.KILL_NAME))
            t[0] = float(dt.datetime(2026, 12, 2, 16, 11, tzinfo=ET).timestamp())
            w5 = L.loop(td, clock=lambda: t[0], sleep=lambda s: t.__setitem__(0, t[0] + s), tick_fn=tk, max_runs=50)
        check("d. the runner never exits while the lane holds a trade (stop flag ignored until flat)", w1 is None and len(beats) >= 5, w1)
        check("d. flat + the 16:15 stop flag -> exits; heartbeat + flag removed", w2 == "stop flag (16:15)" and gone, (w2, gone))
        check("d. flat + OFF / kill / after 16:10 -> exits", (w3, w4, w5) == ("switched OFF", "kill switch", "after 16:10 ET"), (w3, w4, w5))
        check("d. the heartbeat is written every run", all(beats), beats[:5])
        # the morning re-pick: Sim101 yesterday, Sim102 created overnight -> the runner's start moves the lane to Sim102 (flat)
        with tempfile.TemporaryDirectory() as td:
            nd = world(td, ("Sim101",))
            L.set_switch(True, root=td)
            before = L.load_cfg(td)["account"]
            world(td, ("Sim101", "Sim102"), cfg={"on": True, "account": "Sim101", "account_note": "x"})
            L.loop(td, clock=time.time, sleep=lambda s: None, tick_fn=lambda **k: {"S": {}, "routed": []}, max_runs=1)
            after = L.load_cfg(td)
        check("d. the runner's morning re-pick: Sim101 -> Sim102 once NinjaTrader lists it (while flat)",
              before == "Sim101" and after["account"] == "Sim102" and not after.get("account_note"), (before, after))
        # ---- e. the card
        cp = os.path.join(ROOT, "research", "handoff", "2026-11-27", "oflane", "card.json")
        cd = json.load(open(cp, encoding="utf-8"))
        check("e. card draft: practice account, /oflane on, honest numbers, no real money",
              cd["question"].startswith("Order flow on the practice account (Sim, no real money)") and "/oflane on" in cd["question"]
              and cd["options"] == ["yes", "no", "later"] and "forward" in cd["why"].lower() and cd["impact_usd"] == 0
              and "real money" in cd["risk"].lower(), cd)
    finally:
        AX.is_on, AX.lanes = real_on, real_lanes
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
