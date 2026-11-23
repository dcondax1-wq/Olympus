"""The December 2026 roll made safe and (almost) automatic: tools/bat/ROLL.bat + tools/roll_now.py, the dated phone pushes
(engine/roll_watch.countdown -> tools/pc_guard.py -> tools/pc_report.py -> ntfy). Temp folders, a fake NinjaTrader folder,
a fixed clock, fake HTTP: never the real network, never NinjaTrader, never an order.

  A. countdown   no push before Mon Dec 7; one a day Mon 7 / Tue 8 / Wed 9 ("tonight" on the eve); "ready" when the chart is
                 switched on the eve; the late alarm on Thu 10 with the chart left on 12-26; "done" once; the March roll alike
  B. pc_guard    each key once, quiet hours (the late alarm from 01:40 ET), through pc_report.run_once: pushed to the private
                 topic, never on the reporter's first run, a failed push retried, unchanged trading code
  C. roll_now    too early before Wed 15:56 ET; an open MNQ position or a trade in the heartbeat -> not now, nothing changed;
                 the eve with the chart on 12-26 -> the click text and a wait that ends when the chart shows 03-27; an old
                 pinned contract removed from data/autostart.json with a backup (nothing else in it changed); the add-on
                 mode needs no click (after the roll its contract list is fixed when the bot did not write it); --check
                 changes nothing; nothing to do on an ordinary day
  D. static      tools/bat/ROLL.bat (CRLF, ASCII, runs tools\\roll_now.py, pauses); roll_now.py / pc_guard.py write no order file, no
                 live_model*.json, no live phrase; the order contract rule is unchanged (12-26 through Dec 9, 03-27 from Dec 10)

  python -X utf8 -m tests.test_roll_now
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.environ["LE_PR_NO_NET"] = "1"

from engine import roll_watch  # noqa: E402
from engine.ninjatrader import ET, feed_instruments, nt_instrument  # noqa: E402


def _want(t) -> str:
    """feed_instruments.txt as the bot writes it on the day of `t` (the MNQ contract, + the ES research contract once
    engine/ninjatrader.feed_instruments carries it: data health 2026-11-20)."""
    return "".join(f"{n}\n" for n in feed_instruments({"nt_account": "Sim101"}, dt.datetime.fromtimestamp(t, ET).date()))
from tools import pc_guard as G  # noqa: E402
from tools import roll_now as RN  # noqa: E402

RES: list = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(info)[:700]})" if info and not cond else ""))
    return bool(cond)


def at(y, m, d, hh=0, mm=0):
    return int(dt.datetime(y, m, d, hh, mm, tzinfo=ET).timestamp())


def st_at(t, chart, root="MNQ"):
    return roll_watch.state(t, chart, root)


# ============================================================================================== A countdown
def countdown():
    keys = lambda t, ch: [m["key"] for m in roll_watch.countdown(st_at(t, ch), t)]
    check("A: nothing on Sun Dec 6 (the 7-day reminder of ops_checks stays as it was)", keys(at(2026, 12, 6, 10), "MNQ 12-26") == [])
    k7, k8, k9 = keys(at(2026, 12, 7, 10), "MNQ 12-26"), keys(at(2026, 12, 8, 10), "MNQ 12-26"), keys(at(2026, 12, 9, 10), "MNQ 12-26")
    check("A: one push a day Mon Dec 7, Tue Dec 8, Wed Dec 9, each with its own key",
          k7 == ["roll:soon:MNQ 03-27:2026-12-07"] and k8 == ["roll:soon:MNQ 03-27:2026-12-08"] and k9 == ["roll:soon:MNQ 03-27:2026-12-09"],
          (k7, k8, k9))
    m9 = roll_watch.countdown(st_at(at(2026, 12, 9, 10), "MNQ 12-26"), at(2026, 12, 9, 10))[0]
    m7 = roll_watch.countdown(st_at(at(2026, 12, 7, 10), "MNQ 12-26"), at(2026, 12, 7, 10))[0]
    check("A: the eve says tonight (high priority), Monday says in 3 days; both name tools/bat/ROLL.bat, 16:00 ET and MNQ 03-27",
          "tonight" in m9["title"] and m9["priority"] == "high" and "in 3 days" in m7["title"]
          and all("tools/bat/ROLL.bat" in m["body"] and "16:00 ET" in m["body"] and "MNQ 03-27" in m["body"] for m in (m7, m9)), (m7, m9))
    check("A: under 600 characters (one phone screen)", all(len(m["body"]) < 600 for m in (m7, m9)), [len(m7["body"]), len(m9["body"])])
    ku = keys(at(2026, 12, 8, 10), None)
    mu = roll_watch.countdown(st_at(at(2026, 12, 8, 10), None), at(2026, 12, 8, 10))[0]
    check("A: chart contract unknown -> still the reminder, with the hint to open the chart", ku and "cannot see the chart" in mu["body"], mu)
    ke = keys(at(2026, 12, 9, 17), "MNQ 03-27")
    check("A: the eve after 16:00 with the chart already on 03-27 -> 'ready', no reminder", ke == ["roll:ready:MNQ 03-27"], ke)
    kl = keys(at(2026, 12, 10, 9), "MNQ 12-26")
    ml = roll_watch.countdown(st_at(at(2026, 12, 10, 9), "MNQ 12-26"), at(2026, 12, 10, 9))[0]
    check("A: Thu Dec 10 with the chart on 12-26 -> the late alarm (no new entries), tools/bat/ROLL.bat named",
          kl == ["roll:late:MNQ 03-27:2026-12-10"] and "no new entries" in ml["title"] and "tools/bat/ROLL.bat" in ml["body"], ml)
    kd = keys(at(2026, 12, 10, 9), "MNQ 03-27")
    check("A: Thu Dec 10 with the chart on 03-27 -> 'done' once (one key for the roll)", kd == ["roll:done:MNQ 03-27"], kd)
    check("A: a week later nothing", keys(at(2026, 12, 17, 9), "MNQ 03-27") == [])
    km = keys(at(2027, 3, 8, 9), "MNQ 03-27")
    check("A: the March 2027 roll the same way (Mon Mar 8 -> 06-27)", km == ["roll:soon:MNQ 06-27:2027-03-08"], km)
    kq = keys(at(2026, 12, 8, 10), "NQ 12-26")
    mq = roll_watch.countdown(roll_watch.state(at(2026, 12, 8, 10), "NQ 12-26", "NQ"), at(2026, 12, 8, 10))
    check("A: an NQ chart (signal_root NQ) gets the same reminder", kq == ["roll:soon:MNQ 03-27:2026-12-08"] and mq, mq)
    check("A: countdown never raises on junk", roll_watch.countdown({"level": "bad", "chart": 5}, "x") == [])


# ============================================================================================== B pc_guard + pc_report
def guard():
    t = at(2026, 12, 7, 10)
    s0 = st_at(t, "MNQ 12-26")
    st, m = G.guard({}, {"t": t}, roll_state=s0)
    st2, m2 = G.guard(st, {"t": t + 900}, roll_state=s0)
    check("B: guard sends the day's roll push once (key guard:roll:soon:...), not again 15 minutes later",
          [x["key"] for x in m] == ["guard:roll:soon:MNQ 03-27:2026-12-07"] and m2 == [], (m, m2))
    _st3, m3 = G.guard(st2, {"t": at(2026, 12, 8, 10)}, roll_state=st_at(at(2026, 12, 8, 10), "MNQ 12-26"))
    check("B: the next day its own push", [x["key"] for x in m3] == ["guard:roll:soon:MNQ 03-27:2026-12-08"], m3)
    _s, mq = G.guard({}, {"t": at(2026, 12, 7, 23, 30)}, roll_state=st_at(at(2026, 12, 7, 23, 30), "MNQ 12-26"))
    _s, mq2 = G.guard({}, {"t": at(2026, 12, 8, 6, 45)}, roll_state=st_at(at(2026, 12, 8, 6, 45), "MNQ 12-26"))
    check("B: quiet hours 23:00-07:00 ET: no reminder at night", mq == [] and mq2 == [], (mq, mq2))
    tl = at(2026, 12, 10, 0, 30)
    _s, ml0 = G.guard({}, {"t": tl}, roll_state=st_at(tl, "MNQ 12-26"))
    tl2 = at(2026, 12, 10, 1, 45)
    _s, ml1 = G.guard({}, {"t": tl2}, roll_state=st_at(tl2, "MNQ 12-26"))
    check("B: the late alarm waits for 01:40 ET (before LIT's 02:00 window), then goes out high priority",
          ml0 == [] and [x["key"] for x in ml1] == ["guard:roll:late:MNQ 03-27:2026-12-10"] and ml1[0]["priority"] == "high", (ml0, ml1))
    old = {"sent": {"guard:old": t - 50 * 86400, "guard:new": t - 86400}}
    s4, _ = G.guard(old, {"t": t}, roll_state={})
    check("B: sent keys older than 40 days are dropped", "guard:old" not in s4["sent"] and "guard:new" in s4["sent"], s4)
    G.forget(s4, "guard:new")
    check("B: forget() drops a key (a failed push is sent again)", "guard:new" not in s4["sent"])
    # ---- through the real reporter (fake http, fake heartbeat folder)
    from tests.test_bots_back import Box, FakeHTTP
    from tests.test_live_publish import hb_payload
    real_fact = roll_watch.fact
    b = Box()
    try:
        cfg = b.topic()
        now = at(2026, 12, 8, 10)
        roll_watch.fact = lambda *a, **k: st_at(now, "MNQ 12-26")
        hb = hb_payload(now - 60, position=False)
        hb["acct"]["trades"][-1]["day"] = "2026-12-07"
        b.hb(hb)
        h = FakeHTTP()
        b.run(h, now)
        first = [c["h"].get("Title", "") for c in h.posts(cfg["topic"])]
        check("B: reporter's first run only records (no roll push yet)", not [x for x in first if "roll" in x.lower()], first)
        h = FakeHTTP()
        b.run(h, now + 900)
        ps = [c for c in h.posts(cfg["topic"]) if "roll" in c["h"].get("Title", "").lower()]
        check("B: the next run pushes the roll reminder to the private topic, ASCII title, tools/bat/ROLL.bat in the body",
              len(ps) == 1 and "Contract roll in 2 days" in ps[0]["h"]["Title"] and "tools/bat/ROLL.bat" in ps[0]["body"]
              and all(ord(ch) < 128 for ch in ps[0]["h"]["Title"]), [c["h"] for c in h.posts()])
        h = FakeHTTP()
        b.run(h, now + 1800)
        check("B: not again the same day", not [c for c in h.posts(cfg["topic"]) if "roll" in c["h"].get("Title", "").lower()])
        now2 = at(2026, 12, 9, 10)
        roll_watch.fact = lambda *a, **k: st_at(now2, "MNQ 12-26")
        hb["t"] = now2 - 60
        b.hb(hb)
        h = FakeHTTP(ntfy_status=500)
        b.run(h, now2)
        h = FakeHTTP()
        b.run(h, now2 + 900)
        ps = [c for c in h.posts(cfg["topic"]) if "tonight" in c["h"].get("Title", "")]
        check("B: a failed push (ntfy 500) is sent on the next run", len(ps) == 1, [c["h"] for c in h.posts()])
        state = json.load(open(os.path.join(b.work, "state.json"), encoding="utf-8"))
        check("B: the guard's state lives in the reporter's own state.json (data/pc_report, gitignored)",
              any(k.startswith("guard:roll:") for k in state.get("guard", {}).get("sent", {})), state.get("guard"))
    finally:
        roll_watch.fact = real_fact
        b.cleanup()


# ============================================================================================== C roll_now
class NTBox:
    def __init__(self):
        self.dir = tempfile.mkdtemp(prefix="roll_", dir=os.environ.get("LE_TEST_TMP") or None)
        self.nt = os.path.join(self.dir, "NinjaTrader 8")
        self.root = os.path.join(self.dir, "bot")
        for p in ("le_feed", "outgoing", "incoming"):
            os.makedirs(os.path.join(self.nt, p))
        os.makedirs(os.path.join(self.root, "data"))
        os.makedirs(os.path.join(self.root, "logs", "pc_hb"))
        with open(os.path.join(self.nt, "le_feed", "MNQ_5m.csv"), "w") as fh:
            fh.write("time,open,high,low,close,volume\n")

    def chart(self, name):
        with open(os.path.join(self.nt, "le_feed", "MNQ_instrument.txt"), "w") as fh:
            fh.write(name + "\n")

    def pos(self, inst, acct, line):
        with open(os.path.join(self.nt, "outgoing", f"{inst}_{acct}_Position.txt"), "w") as fh:
            fh.write(line)

    def autostart(self, cfg):
        with open(os.path.join(self.root, "data", "autostart.json"), "w") as fh:
            json.dump({"cfg": cfg, "saved_at": 1, "mode": "sim"}, fh)

    def facts(self, now):
        return RN.gather(now, folder=self.nt, root=self.root, cfg={"nt_feed_roots": {"NQ": ["MNQ", "NQ"]}})

    def cleanup(self):
        shutil.rmtree(self.dir, ignore_errors=True)


def roll_now():
    b = NTBox()
    try:
        b.chart("MNQ 12-26")
        out = []
        say = out.append
        f = b.facts(at(2026, 11, 13, 10))
        rc = RN.run(f, say=say)
        check("C: an ordinary day: nothing to roll, the next roll date and tools/bat/ROLL.bat's day are said, exit 0",
              rc == 0 and any("Nothing to roll" in x and "Thu Dec 10" in x and "Wed Dec 09" in x for x in out), out)
        out.clear()
        f = b.facts(at(2026, 12, 9, 14, 0))
        rc = RN.run(f, say=say)
        check("C: Wed Dec 9 14:00 ET (bots may still trade): too early, nothing changed, exit 2",
              rc == 2 and any("too early" in x.lower() and "16:00" in x for x in out), out)
        eve = at(2026, 12, 9, 16, 30)
        b.pos("MNQ 12-26 Globex", "Sim101", "LONG;2;25000")
        out.clear()
        rc = RN.run(b.facts(eve), say=say)
        check("C: an open MNQ position in NinjaTrader -> not now, nothing changed, exit 2",
              rc == 2 and any("Not now" in x and "LONG 2 MNQ 12-26 Globex on Sim101" in x for x in out), out)
        b.pos("MNQ 12-26 Globex", "Sim101", "FLAT;0;0")
        b.pos("ES 12-26 Globex", "Sim101", "LONG;1;6000")          # not ours: ignored
        with open(os.path.join(b.root, "logs", "pc_hb", "heartbeat.json"), "w") as fh:
            json.dump({"t": eve - 60, "position": True}, fh)
        out.clear()
        rc = RN.run(b.facts(eve), say=say)
        check("C: the heartbeat shows a trade -> not now", rc == 2 and any("heartbeat" in x for x in out), out)
        with open(os.path.join(b.root, "logs", "pc_hb", "heartbeat.json"), "w") as fh:
            json.dump({"t": eve - 60, "position": False, "account_c": {"open": None}}, fh)
        b.autostart({"nt_account": "Sim101", "nt_instrument": "MNQ 12-26", "adapter": "ninjatrader", "sym": "NQ"})
        out.clear()
        calls = {"n": 0}

        def regather():
            calls["n"] += 1
            if calls["n"] == 3:
                b.chart("MNQ 03-27")              # the owner clicks during the wait
            return b.facts(eve + 30 * calls["n"])
        rc = RN.run(b.facts(eve), say=say, wait_s=600, regather=regather, sleep=lambda s: None, roll_check=lambda: "OK (fake)")
        rec = json.load(open(os.path.join(b.root, "data", "autostart.json"), encoding="utf-8"))
        baks = [n for n in os.listdir(os.path.join(b.root, "data")) if n.startswith("autostart.json.before-roll-")]
        check("C: the eve, flat, chart on 12-26: the 3 click lines (Instrument > MNQ 03-27, Days to load 30, Save Workspace)",
              any("Instrument > MNQ 03-27" in x for x in out) and any("Days to load 30" in x for x in out)
              and any("Save Workspace" in x for x in out), out)
        check("C: ... waits until the chart shows 03-27, then 'Roll ready' (orders at 00:00 ET Thu Dec 10), exit 0",
              rc == 0 and calls["n"] == 3 and any("chart on MNQ 03-27" in x for x in out)
              and any("Roll ready" in x and "Thu Dec 10" in x for x in out) and any("History check: OK" in x for x in out), out)
        check("C: the old pinned MNQ 12-26 is removed from data/autostart.json, a backup kept, nothing else changed; restart hint said",
              "nt_instrument" not in rec["cfg"] and rec["cfg"]["nt_account"] == "Sim101" and rec["saved_at"] == 1 and len(baks) == 1
              and "MNQ 12-26" in open(os.path.join(b.root, "data", baks[0]), encoding="utf-8").read()
              and any("STOP_BOT.bat, then tools/bat/BOTS_BACK.bat" in x for x in out), (rec, baks, out))
        b.chart("MNQ 12-26")
        out.clear()
        rc = RN.run(b.facts(eve), say=say, wait_s=60, regather=lambda: b.facts(eve), sleep=lambda s: None)
        check("C: the click never comes -> [FIX] do the click, then tools/bat/ROLL.bat again, exit 1",
              rc == 1 and any("[FIX]" in x and "tools/bat/ROLL.bat again" in x for x in out), out)
        out.clear()
        rc = RN.run(b.facts(eve), say=say, wait_s=0, regather=None)
        check("C: --wait 0 -> the click text and exit 1, no wait", rc == 1 and any("Instrument > MNQ 03-27" in x for x in out), out)
        # ---- the roll day, chart left on 12-26 (entries refused): flat -> the click is asked for 03-27
        thu = at(2026, 12, 10, 9)
        out.clear()
        rc = RN.run(b.facts(thu), say=say, wait_s=0)
        check("C: Thu Dec 10 09:00, chart still on 12-26: allowed while flat (entries are blocked anyway), asks for 03-27",
              rc == 1 and any("Instrument > MNQ 03-27" in x for x in out), out)
        b.chart("MNQ 03-27")
        out.clear()
        rc = RN.run(b.facts(thu), say=say)
        check("C: Thu Dec 10 with the chart on 03-27: nothing to roll, exit 0", rc == 0 and any("Nothing to roll" in x for x in out), out)
        # ---- --check changes nothing
        b.chart("MNQ 12-26")
        b.autostart({"nt_account": "Sim101", "nt_instrument": "MNQ 12-26"})
        before = open(os.path.join(b.root, "data", "autostart.json"), encoding="utf-8").read()
        out.clear()
        rc = RN.run(b.facts(thu), check_only=True, say=say)
        check("C: --check: says what is to do, changes nothing, exit 1",
              rc == 1 and open(os.path.join(b.root, "data", "autostart.json"), encoding="utf-8").read() == before
              and any("To do: unpin; chart" in x for x in out), out)
        # ---- add-on mode (no chart): nothing to click; after the roll a stale contract list is fixed
        with open(os.path.join(b.nt, "le_feed", "le_feed_status.txt"), "w") as fh:
            fh.write(f"{eve - 30},source=addon,instruments=MNQ 12-26,last_1m={eve - 90},resubs=0,connected=1\n")
        with open(os.path.join(b.nt, "le_feed", "feed_instruments.txt"), "w") as fh:
            fh.write(_want(eve))
        b.autostart({"nt_account": "Sim101"})
        out.clear()
        rc = RN.run(b.facts(eve), say=say, wait_s=0)
        check("C: add-on mode on the eve: no click, 'Roll ready', the contract list left to the bot",
              rc == 0 and not any("Instrument >" in x for x in out) and any("Roll ready" in x for x in out)
              and open(os.path.join(b.nt, "le_feed", "feed_instruments.txt")).read() == _want(eve), out)
        with open(os.path.join(b.nt, "le_feed", "le_feed_status.txt"), "w") as fh:
            fh.write(f"{thu - 30},source=addon,instruments=MNQ 12-26,last_1m={thu - 90},resubs=0,connected=1\n")
        out.clear()
        rc = RN.run(b.facts(thu), say=say, wait_s=0)
        check("C: add-on mode after the roll with the bot not running: feed_instruments.txt -> MNQ 03-27 (the bot's own rule)",
              rc == 0 and open(os.path.join(b.nt, "le_feed", "feed_instruments.txt")).read() == _want(thu)
              and any("told the LE_Feed add-on: MNQ 03-27" in x for x in out), out)
        # ---- chart mode, the chart's contract unreadable (older LE_BarFeed / continuous): the click text, no endless wait
        os.remove(os.path.join(b.nt, "le_feed", "le_feed_status.txt"))
        os.remove(os.path.join(b.nt, "le_feed", "MNQ_instrument.txt"))
        out.clear()
        n = {"c": 0}
        rc = RN.run(b.facts(eve), say=say, wait_s=600, regather=lambda: n.__setitem__("c", n["c"] + 1) or b.facts(eve), sleep=lambda s: None)
        check("C: chart contract unreadable on the eve: the click text and [FIX] (dated contract), exit 1, no wait",
              rc == 1 and n["c"] == 0 and any("Instrument > MNQ 03-27" in x for x in out) and any("[FIX]" in x and "dated contract" in x for x in out), out)
        incoming = os.listdir(os.path.join(b.nt, "incoming"))
        check("C: no order file was ever written (incoming\\ empty)", incoming == [], incoming)
    finally:
        b.cleanup()


# ============================================================================================== D static
def static():
    raw = open(os.path.join(ROOT, "tools/bat/ROLL.bat"), "rb").read()
    check("D: tools/bat/ROLL.bat CRLF, ASCII, runs tools\\roll_now.py, pauses, names the zip update when the script is missing",
          b"\n" not in raw.replace(b"\r\n", b"") and all(c < 128 for c in raw) and b'tools\\roll_now.py" %*' in raw
          and b"pause" in raw and b"UPDATE_FROM_ZIP.bat" in raw)
    for rel in ("tools/roll_now.py", "tools/pc_guard.py"):
        src = open(os.path.join(ROOT, rel), encoding="utf-8").read()
        body = src.split('"""', 2)[-1]
        check(f"D: {rel}: no order line, no incoming\\ write, no live_model, no live phrase, no arming",
              not re.search(r"place_line|PLACE;|CLOSEPOSITION|incoming|live_model|I ACCEPT|LIVE_PHRASE|enable-auto-resume|/api/live", body))
    check("D: the order contract rule is unchanged (12-26 through Wed Dec 9, 03-27 from Thu Dec 10, 06-27 from Thu Mar 11 2027)",
          nt_instrument("MNQ", dt.date(2026, 12, 9)) == "MNQ 12-26" and nt_instrument("MNQ", dt.date(2026, 12, 10)) == "MNQ 03-27"
          and nt_instrument("MNQ", dt.date(2027, 3, 10)) == "MNQ 03-27" and nt_instrument("MNQ", dt.date(2027, 3, 11)) == "MNQ 06-27")


def main() -> int:
    countdown()
    guard()
    roll_now()
    static()
    n, ok = len(RES), sum(RES)
    print(f"\n{ok}/{n} passed")
    return 0 if ok == n else 1


def test_roll_now():                       # pytest entry
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
