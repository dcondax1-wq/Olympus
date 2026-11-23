"""READY check red team (2026-11-23): engine/readiness can never crash, delay or block the bot server, never writes a trading
file, does not spam, and does not say NOT READY on a healthy PC (Sim days, the clock's whole-second probe, the 7-day clock's
weekend). Fakes only: no network, nothing trades, the real data/ files are never written.

    python -X utf8 -m tests.test_ready_rt
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import tempfile
import threading
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import readiness as R  # noqa: E402

ET = ZoneInfo("America/New_York")
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"   -> {str(info)[:300]}"))


def ts(y, mo, d, h, mi=0) -> int:
    return int(dt.datetime(y, mo, d, h, mi, tzinfo=ET).timestamp())


MON_0115 = ts(2026, 11, 23, 1, 15)
OKC = [{"key": k, "level": "ok", "text": "x"} for k in ("server", "bot", "heartbeat", "nt_conn", "feed_1m", "feed_5m", "internet")]


def hb(lit="LIVE", lit_arm=True, at="live", at_arm=True):
    return {"t": 1, "health": {"account": {"label": lit, "armed": lit_arm, "enabled": True}, "accounts": []},
            "second": {"route": {"account_b": {"label": at, "armed": at_arm}}}}


def facts(**kw):
    f = {"hb": hb(), "drift_s": 0.2, "disk_free_gb": 100, "checks": OKC, "k7": []}
    f.update(kw)
    return f


def lvl(f, now=MON_0115):
    return R.ready_verdict(now, facts=f)


def main() -> int:
    tmp = tempfile.mkdtemp()
    LP, SP = os.path.join(tmp, "last.json"), os.path.join(tmp, "st.json")

    # 1. the server start hook: never blocks, never raises, never runs on a dev / test server
    real_tick = R.tick
    for k in ("LE_PC_WATCH", "LE_NO_AUTOSTART", "LE_SELFTEST_CHILD", "LE_READY"):
        os.environ.pop(k, None)
    hung = threading.Event()
    R.tick = lambda **kw: (hung.set(), time.sleep(60))
    t0 = time.time()
    R.start_after_boot(delay_s=0)
    took = time.time() - t0
    hung.wait(2)
    th = [t for t in threading.enumerate() if t.name == "ready-start"]
    check("1a. a readiness check that hangs 60 s: start_after_boot returns at once, in a daemon thread", took < 0.5 and hung.is_set()
          and th and all(t.daemon for t in th), (took, th))
    threading.excepthook = lambda a: None          # the thread's own death is the point here: keep the output quiet
    R.tick = lambda **kw: (_ for _ in ()).throw(RuntimeError("boom"))
    try:
        R.start_after_boot(delay_s=0)
        time.sleep(0.2)
        ok = True
    except Exception as e:
        ok = e
    check("1b. a readiness check that raises: the start hook does not raise (the thread dies alone)", ok is True, ok)
    for env in ("LE_NO_AUTOSTART", "LE_SELFTEST_CHILD", "LE_PC_WATCH", "LE_READY"):
        ran = []
        R.tick = lambda **kw: ran.append(1)
        os.environ[env] = "0" if env in ("LE_PC_WATCH", "LE_READY") else "1"
        R.start_after_boot(delay_s=0)
        time.sleep(0.2)
        os.environ.pop(env)
        check(f"1c. {env} set (dev / test server, sealed self-test child, switched off): no start check at all", not ran, ran)
    R.tick = real_tick
    garbage = [None, "x", 7, [], {"hb": "x", "checks": "y", "k7": "z", "drift_s": "nan?", "disk_free_gb": "?"},
               {"checks": [None, 1, {"key": "bot", "level": "bad"}], "hb": {"health": "?"}}, {"k7": [{"left": "x"}]}]
    out = []
    for g in garbage:
        try:
            v = R.ready_verdict(MON_0115, facts=g if isinstance(g, dict) else {"hb": g})
            out.append(v.get("level") in (R.READY, R.WARN, R.NOT_READY))
        except Exception as e:  # noqa: BLE001
            out.append(e)
    check("1d. garbage facts never raise: always one of READY / WARN / NOT READY", all(x is True for x in out), out)
    r = R.tick(MON_0115, facts={"hb": [], "checks": None}, sender=lambda a: None, last_path=LP, state_path=SP)
    check("1e. tick on garbage returns a verdict, never raises", isinstance(r, dict) and "verdict" in r, r)
    R2 = R.ready_verdict
    R.ready_verdict = lambda *a, **k: (_ for _ in ()).throw(ValueError("x"))
    r = R.tick(MON_0115, sender=lambda a: None, last_path=LP, state_path=SP)
    R.ready_verdict = R2
    check("1f. the verdict itself raising: tick returns {'error'}, never raises", r == {"error": "ValueError"}, r)

    # 2. read-only: the only files it opens for writing are its two own data files
    src = open(os.path.join(ROOT, "engine", "readiness.py"), encoding="utf-8").read()
    src = "\n".join(ln for ln in src.split("# READY VERDICT", 1)[1].splitlines() if not ln.lstrip().startswith("#"))   # the new code
    writes = re.findall(r"open\([^)]*['\"]w['\"]", src)
    check("2a. readiness.py writes only through _write (ready_last / ready_state), never a trading file",
          len(writes) == 1 and "subprocess" not in src and "LAST_PATH" in src and "STATE_PATH" in src
          and not re.search(r"live_model|second_model|accounts/|autostart\.json|armed\s*=|\.arm\(|start_bot", src), writes)
    ready_cli = open(os.path.join(ROOT, "tools", "ready_check.py"), encoding="utf-8").read()
    check("2b. tools/ready_check.py writes nothing, runs nothing", not re.search(r"open\([^)]*['\"][wa]['\"]|subprocess|os\.system", ready_cli), "")
    gi = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
    check("2c. data/ready_last.json + data/ready_state.json are gitignored (bot-made, never committed)",
          "data/ready_last.json" in gi and "data/ready_state.json" in gi, "")

    # 3. alert spam
    bad = facts(drift_s=25)
    sent = []
    for i in range(24):                                   # 2 hours of 5-minute ticks, NOT READY the whole time
        R.tick(MON_0115 + i * 300, facts=bad, sender=sent.append, last_path=LP, state_path=os.path.join(tmp, "s3a.json"))
    check("3a. 2 hours NOT READY on the same blocker: at most 2 alerts (once an hour)", 1 <= len(sent) <= 2, len(sent))
    sent = []
    for i in range(24):                                   # a flapping NinjaTrader connection: bad, ok, bad, ok every 5 min
        f = facts(checks=OKC + ([{"key": "nt_conn", "level": "bad", "text": "x"}] if i % 2 == 0 else []))
        R.tick(MON_0115 + i * 300, facts=f, sender=sent.append, last_path=LP, state_path=os.path.join(tmp, "s3b.json"))
    check("3b. a blocker that comes and goes every 5 min: still at most 2 alerts in 2 hours", 1 <= len(sent) <= 2, len(sent))
    sent = []
    keys = ["nt_conn", "feed_1m", "server", "internet", "bot", "heartbeat"]
    for i in range(12):                                   # a different blocker every 5 min (internet / PC flapping)
        f = facts(checks=[c for c in OKC if c["key"] != keys[i % 6]] + [{"key": keys[i % 6], "level": "bad", "text": "x"}])
        R.tick(MON_0115 + i * 300, facts=f, sender=sent.append, last_path=LP, state_path=os.path.join(tmp, "s3c.json"))
    check("3c. a new blocker every 5 min for an hour: never two alerts within 10 min (<= 6 an hour)",
          len(sent) <= 6, len(sent))
    sp = os.path.join(tmp, "s3d.json")
    sent = []
    R.tick(MON_0115, facts=bad, sender=sent.append, last_path=LP, state_path=sp)
    R.tick(MON_0115 + 100, facts=bad, sender=sent.append, last_path=LP, state_path=sp, reason="start")   # the server restarted
    R.tick(MON_0115 + 200, facts=bad, sender=sent.append, last_path=LP, state_path=sp, reason="start")
    check("3d. de-dup survives a server restart (state on disk): two restarts = no second alert", len(sent) == 1, len(sent))
    sent = []
    sim = facts(hb=hb(lit="Sim101", lit_arm=False, at="sim", at_arm=True), drift_s=25)
    for i in range(6):
        R.tick(MON_0115 + i * 300, facts=sim, sender=sent.append, last_path=LP, state_path=os.path.join(tmp, "s3e.json"))
    check("3e. a Sim / paper-only day: no alert at all, even with a real blocker", not sent, sent)
    sent = []
    sat = ts(2026, 11, 28, 11, 0)
    for i in range(12):
        R.tick(sat + i * 300, facts=facts(checks=OKC + [{"key": "internet", "level": "bad", "text": "x"}]), sender=sent.append,
               last_path=LP, state_path=os.path.join(tmp, "s3f.json"))
    check("3f. PC offline on a Saturday: no alerts (not the active period)", not sent, sent)

    # 4. no false NOT READY
    v = lvl(facts(hb=hb(lit="Sim101", lit_arm=False, at="sim", at_arm=True)))
    check("4a. both bots on Sim (paper day): no 'not armed' NOT READY, the day is paper-only",
          v["level"] == R.READY and v.get("paper_only"), v)
    v = lvl(facts(hb=hb(at="sim", at_arm=True)))
    check("4b. Zlarior LIVE + ATLAS armed on Sim: ATLAS is 'on Sim' (WARN), never 'not armed'",
          v["level"] == R.WARN and "on Sim" in v["blockers"][0]["what"] and "not armed" not in json.dumps(v), v)
    v = lvl(facts(hb=hb(at_arm=False)))
    check("4c. ATLAS LIVE but not armed (the 2026-11-22 night): still NOT READY", v["level"] == R.NOT_READY
          and v["blockers"][0]["what"] == "ATLAS 25K is not armed", v)
    check("4d. the clock: the guard's proof math (5.4 s with a 1.6 s doubt proves only 4.8 s: the guard lets it trade = READY)",
          abs(R.proven_drift({"drift_s": 5.4, "unc_s": 1.6}) - 4.8) < 1e-9 and R.proven_drift({"drift_s": 24.0, "unc_s": 1.2}) > 5
          and R.proven_drift({"drift_s": -0.4, "unc_s": 1.0}) == 0.0 and R.proven_drift({}) is None,
          [R.proven_drift({"drift_s": 5.4, "unc_s": 1.6})])
    fri = ts(2026, 11, 20, 1, 15)
    v = lvl(facts(k7=[{"nm": "ATLAS 25K", "left": 2, "ses": 1, "on": False}]), fri)
    check("4e. 7-day clock: Friday, MFFU's last day Sunday (2 days but 1 session left) = NOT READY, not a silent WARN",
          v["level"] == R.NOT_READY and "1 session" in v["blockers"][0]["what"], v)
    v = lvl(facts(k7=[{"nm": "ATLAS 25K", "left": 4, "ses": 3, "on": False}]))
    check("4f. 7-day clock with 4 days / 3 sessions left: nothing (no nagging)", v["level"] == R.READY, v)
    v = lvl(facts(k7=[{"nm": "ATLAS 25K", "left": 2, "ses": 1, "on": True}]), fri)
    check("4g. ... and keep-alive ON covers it", v["level"] == R.READY, v)

    # 5. privacy: the public block
    nasty = facts(hb={"health": {"account": {"label": "LIVE", "armed": False, "enabled": True},
                                 "accounts": [{"id": "x1", "name": "MFFU 50K " + "Z" * 80, "label": "LIVE", "armed": False}]}})
    b = R.rd(R.ready_verdict(MON_0115, facts=nasty))
    size = len(json.dumps(b, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    check("5a. rd block <= 200 bytes, no time, no ids", size <= 200 and "t" not in b and "x1" not in json.dumps(b), (size, b))
    check("5b. rd(None / garbage) = None", R.rd(None) is None and R.rd({"level": "?"}) is None and R.rd("x") is None, "")
    ok = sum(RES)
    print(f"\n{ok}/{len(RES)} passed")
    return 0 if ok == len(RES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
