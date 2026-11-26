"""Setup progress pushes (day-closer 2026-11-25, engine/setup_progress.py). Fake bot + fake Brain, a fake clock, every send captured
(never the owner's phone).

    python -X utf8 -m tests.test_setup_progress
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sys
import tempfile
from types import SimpleNamespace
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.environ.setdefault("LE_SELFTEST_CHILD", "1")

ET = ZoneInfo("America/New_York")
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {str(detail)[:700]}"), flush=True)


def ts(y, m, d, hh, mm=0) -> int:
    return int(dt.datetime(y, m, d, hh, mm, tzinfo=ET).timestamp())


DAY = "2026-11-25"


def brain(key, n, label, wait, d=1, setups=()):
    return {"day": DAY, "stage": {"key": key, "n": n, "label": label, "waiting": wait, "dir": d}, "setups": list(setups)}


def row(status, d=1, sid="140:1", text=""):
    return {"id": sid, "dir": d, "side": "LONG" if d == 1 else "SHORT", "status": status, "status_text": text}


def acct(name, armed=True, problem=None, keys=None):
    return SimpleNamespace(spec={"adapter": "ninjatrader", "armed": armed, "name": name, **({"keys": keys} if keys else {})},
                           name=name, label=name if keys else None, problem=problem, adapter=object(),
                           disabled_reason=lambda: problem)


def make_bot(br, second=None, price=25500.0, accts=(), atl=()):
    a = list(atl)
    return SimpleNamespace(running=True, cfg={"adapter": "ninjatrader"}, brain=br, second=second, state={"price": price},
                           accts=SimpleNamespace(accounts=list(accts)), acct_b=a[0] if a else None,
                           acct_r=a[1] if len(a) > 1 else None, acct_r2=None)


def t_lit(tmp):
    print("1. LIT steps 5 / 7 / 8 and cancelled", flush=True)
    from engine import setup_progress as SP
    import engine.launch_check as LC
    LC_orig = LC.rapid_fact
    LC.rapid_fact = lambda b, path=None, slot="rapid": None
    try:
        sent = []
        g = SP.SetupProgress(send=lambda e: sent.append(e) or "queued", state_path=os.path.join(tmp, "sp.json"))
        z2, rp = acct("Zlarior 25K #2"), acct("Rapid EOD 25K", armed=False)
        t = ts(2026, 11, 25, 9, 40)
        b = make_bot(brain("displacement", 4, "Displacement", "waiting for a 5m CISD"), accts=[z2, rp])
        g.step(b, t)
        check("step 4 (displacement) -> nothing yet", not sent, sent)
        b.brain = brain("cisd5", 5, "5m CISD", "5m CISD closed above 25,512: limit next", setups=[row("armed")])
        g.step(b, t + 60)
        check("step 5 -> one line 'Zlarior LONG 5m CISD 5/10' with the Brain's own words", len(sent) == 1
              and "LONG" in sent[0]["title"] and "5/10" in sent[0]["title"] and "25,512" in sent[0]["body"], sent)
        check("...it names the accounts that follow and the one that would not (not armed)",
              "Also on: Zlarior 25K #2" in sent[0]["body"] and "Not on: Rapid EOD 25K - not armed" in sent[0]["body"], sent[0]["body"])
        check("...type setup_progress, soft (no ring) below the entry step", sent[0]["notify_type"] == "setup_progress" and sent[0]["soft"])
        g.step(b, t + 90)
        b.brain = brain("limit", 6, "Limit armed", "LONG limit 25,512 armed until 10:15", setups=[row("armed")])
        g.step(b, t + 120)
        check("the same step again / step 6 -> no new line (de-dup per setup + step; 6 is not a step)", len(sent) == 1, sent)
        b.brain = brain("cisd1m", 7, "1m CISD wait", "Limit tapped at 09:52: waiting for a 1m CISD", setups=[row("tapped")])
        g.step(b, t + 180)
        b.brain = brain("entry", 8, "Entry", "Entering LONG at market now", setups=[row("entering")])
        g.step(b, t + 240)
        check("steps 7 and 8 -> one line each; 8 is loud (not soft)", [e["title"][-4:] for e in sent] == ["5/10", "7/10", "8/10"]
              and not sent[2]["soft"], [e["title"] for e in sent])
        # a second setup that jumps straight to 7, then dies
        sent.clear()
        b.brain = brain("cisd1m", 7, "1m CISD wait", "SHORT limit tapped", d=-1, setups=[row("tapped", d=-1, sid="200:-1")])
        g.step(b, t + 3600)
        check("a jump 4 -> 7 sends ONE line (7/10), not 5 and 7", len(sent) == 1 and "7/10" in sent[0]["title"], sent)
        b.brain = brain("sweep", 2, "Sweep", "waiting", d=None, setups=[row("no_fill", d=-1, sid="200:-1",
                                                                            text="No fill (limit window ended 11:05 ET): price never came back")])
        g.step(b, t + 3700)
        check("it dies -> 'setup cancelled: <the Brain's why>'", len(sent) == 2 and "cancelled" in sent[1]["title"]
              and "price never came back" in sent[1]["body"], sent)
        g.step(b, t + 3800)
        check("cancelled once", len(sent) == 2)
        b.brain = brain("sweep", 2, "Sweep", "waiting", setups=[row("rejected", sid="999:1", text="Rejected: stop too big")])
        g.step(b, t + 3900)
        check("a rejected setup that never got a line -> no 'cancelled'", len(sent) == 2, sent)
        # restart: the de-dup survives (logs/setup_progress.json)
        g2 = SP.SetupProgress(send=lambda e: sent.append(e) or "queued", state_path=os.path.join(tmp, "sp.json"))
        b.brain = brain("entry", 8, "Entry", "Entering", setups=[row("entering")])
        g2.step(b, t + 4000)
        check("after a restart the same setup + step is not sent again", len(sent) == 2, sent)
        # quiet hours: only the entering line
        sent.clear()
        g3 = SP.SetupProgress(send=lambda e: sent.append(e) or "queued", state_path=os.path.join(tmp, "sp3.json"))
        n2 = ts(2026, 11, 25, 3, 10)
        b.brain = brain("cisd5", 5, "5m CISD", "London sweep", setups=[row("armed", sid="30:1")])
        g3.step(b, n2)
        b.brain = brain("entry", 8, "Entry", "Entering LONG", setups=[row("entering", sid="30:1")])
        g3.step(b, n2 + 300)
        check("03:10 ET (quiet): the 5/10 line is held, the 8/10 'entering' line goes", [e["title"][-4:] for e in sent] == ["8/10"], sent)
        # day cap
        sent.clear()
        g4 = SP.SetupProgress(send=lambda e: sent.append(e) or "queued", state_path=os.path.join(tmp, "sp4.json"))
        for i in range(16):
            b.brain = brain("cisd5", 5, "5m CISD", "x", setups=[row("armed", sid=f"{i}:1")])
            g4.step(b, t + i * 10)
        check(f"at most {SP.DAY_MAX} lines a day", len(sent) == SP.DAY_MAX, len(sent))
        b.brain = brain("entry", 8, "Entry", "Entering", setups=[row("entering", sid="50:1")])
        g4.step(b, t + 500)
        check("...the entering line still goes past the cap", len(sent) == SP.DAY_MAX + 1, len(sent))
    finally:
        LC.rapid_fact = LC_orig


def t_atlas(tmp):
    print("2. ATLAS: 30 / 10 pts from an S/R level, armed", flush=True)
    from engine import setup_progress as SP
    import engine.launch_check as LC
    LC_orig = LC.rapid_fact
    LC.rapid_fact = lambda b, path=None, slot="rapid": None
    try:
        sent = []
        g = SP.SetupProgress(send=lambda e: sent.append(e) or "queued", state_path=os.path.join(tmp, "spa.json"))
        sec = {"strategies": {"sr_nyreclaim": {"short": "S/R", "state": {"stage": "waiting", "text": "watching the levels"},
                                               "brain": {"levels": [{"name": "PDH", "label": "prior day high", "px": 25540.0, "stage": "waiting"},
                                                                    {"name": "ONL", "px": 25400.0, "stage": "taken"}]}},
                              "ema_lon_vix": {"short": "EMA", "state": {"stage": "waiting", "text": "-"}, "brain": {}},
                              "macd_sweep": {"short": "MACD", "state": {"stage": "waiting"}, "brain": {"levels": [{"name": "X", "px": 25501}]}}}}
        b25 = acct("ATLAS 25K", keys=["sr_nyreclaim", "ema_lon_vix"])
        t = ts(2026, 11, 25, 9, 40)
        b = make_bot({}, second=sec, price=25500.0, atl=[b25])
        g.step(b, t)
        check("40 pts away -> nothing; a member not on any ATLAS account (MACD) -> nothing", not sent, sent)
        b.state["price"] = 25515.0
        g.step(b, t + 30)
        check("25 pts from PDH -> 'ATLAS S/R: 25 pts from PDH'", len(sent) == 1 and "25 pts" in sent[0]["title"], sent)
        check("...the line names its account", "Also on: ATLAS 25K" in sent[0]["body"], sent[0]["body"])
        b.state["price"] = 25520.0
        g.step(b, t + 60)
        b.state["price"] = 25533.0
        g.step(b, t + 90)
        check("inside 30 again -> no repeat; inside 10 -> one more line", len(sent) == 2 and "7 pts" in sent[1]["title"], sent)
        check("a level already taken is never alerted", all("ONL" not in e["title"] for e in sent))
        sec["strategies"]["ema_lon_vix"]["state"] = {"stage": "armed", "text": "Armed (short): price is at the 5m EMA 50 (25,530)"}
        sec["strategies"]["ema_lon_vix"]["brain"] = {"plan": {"entry": 25530, "stop": 25550, "target": 25470}}
        g.step(b, t + 120)
        check("EMA arms -> 'ATLAS EMA ARMED' with its own words + entry / stop / target", len(sent) == 3 and "ARMED" in sent[2]["title"]
              and "EMA 50" in sent[2]["body"] and "25,550" in sent[2]["body"], sent[-1])
        g.step(b, t + 150)
        check("armed once", len(sent) == 3)
        sent.clear()
        g2 = SP.SetupProgress(send=lambda e: sent.append(e) or "queued", state_path=os.path.join(tmp, "spb.json"))
        b.state["price"] = 25536.0
        g2.step(b, t + 200)
        check("first look already inside 10 pts -> one line (10), not both", sum("PDH" in e["title"] for e in sent) == 1
              and "4 pts" in [e for e in sent if "PDH" in e["title"]][0]["title"], sent)
    finally:
        LC.rapid_fact = LC_orig


def t_off(tmp):
    print("3. switches and safety", flush=True)
    from engine import setup_progress as SP, notify
    sent = []
    g = SP.SetupProgress(send=lambda e: sent.append(e) or "queued", state_path=os.path.join(tmp, "spo.json"))
    t = ts(2026, 11, 25, 9, 40)
    br = brain("cisd1m", 7, "1m CISD wait", "x", setups=[row("tapped")])
    g.step(SimpleNamespace(**{**vars(make_bot(br)), "cfg": {"adapter": "paper"}}), t)
    check("a paper bot -> nothing", not sent)
    g.step(make_bot(br), ts(2026, 11, 28, 9, 40))
    check("Saturday -> nothing", not sent)
    os.environ["LE_SETUP_PROGRESS"] = "0"
    try:
        g.step(make_bot(br), t)
        check("LE_SETUP_PROGRESS=0 -> nothing", not sent)
    finally:
        os.environ.pop("LE_SETUP_PROGRESS", None)
    orig = notify.on
    notify.on = lambda kind, s=None: kind != "setup_progress"
    try:
        g.step(make_bot(br), t)
        check("notify_settings alerts.setup_progress false -> nothing", not sent)
    finally:
        notify.on = orig
    check("default ON: setup_progress is an IMPORTANT type and true in notify_settings.json",
          "setup_progress" in notify.IMPORTANT and json.load(open(os.path.join(ROOT, "notify_settings.json")))["alerts"]["setup_progress"] is True)
    from engine import alert_bus
    check("alert_bus maps kind 'setup' to the setup_progress switch", alert_bus.NOTIFY_TYPE.get("setup") == "setup_progress")

    class Boom:
        running = True
        cfg = {"adapter": "ninjatrader"}

        def __getattr__(self, k):
            raise RuntimeError("broken")
    try:
        g.step(Boom(), t)
        ok = True
    except Exception as e:  # noqa: BLE001
        ok = e
    check("a broken bot never raises", ok is True, ok)
    import inspect
    src = inspect.getsource(SP)
    check("read-only: no order call in the module", not any(w in src for w in (".place_bracket(", ".send_lines(", "._route(", ".flatten(", "adapter.send(")))


def main():
    tmp = tempfile.mkdtemp(prefix="sp_")
    try:
        for f in (t_lit, t_atlas, t_off):
            try:
                f(tmp)
            except Exception as e:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                check(f"{f.__name__} ran", False, e)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(ok for _, ok in RESULTS)
    print(f"\nsetup progress: {n}/{len(RESULTS)} checks passed")
    return 0 if n == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
