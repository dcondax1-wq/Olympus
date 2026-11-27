"""big-zeroerr2 (2026-11-26): the real-error sweep's fixes.

    python -X utf8 -m tests.test_zeroerr2          (~25 s: one real hung process, one real faulthandler dump)

a. engine/hang_guard.Guard (fake clock): no answer for HANG_S -> flat = the server is killed (the supervisor restarts it) + ONE
   line, all within 5 minutes of the first silence; a trade may be open = NOT killed, one line, killed once flat; a server that
   answers again is left alone; a server still starting is not "hung"; the guard ends when the server exits.
b. The 2026-11-25 hang replayed: heartbeat stops 17:22 ET -> restarted by 17:27 ET (was: 7 h, until a hand restart at 00:35).
c. Real processes: a "server" that accepts connections but never answers is found by the real ping and killed by the real
   kill; a frozen event loop's faulthandler dump names the frozen function (where_stuck).
d. server.py wiring: the guard + the stack dump start in the server's startup (supervised PC only), before the watchdog.
e. The sweep's other clusters are covered where they live: the update hold-back (generated_files / auto-park / Telegram /update,
   tests.test_handsfree), the false "ATLAS 25K is on Sim" (preflight.arms kind first, tests.test_ready*), clock + OneDrive
   (tests.test_ops2); here only that their fixed code is in this checkout.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import hang_guard as HG  # noqa: E402

ET = ZoneInfo("America/New_York")
RES = []


def check(name, ok, info=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}{(': ' + str(info)[:400]) if info and not ok else ''}")
    RES.append(bool(ok))


def et(y, m, d, hh, mm=0, ss=0) -> float:
    return dt.datetime(y, m, d, hh, mm, ss, tzinfo=ET).timestamp()


class World:
    def __init__(self, tmp, t0, flat=None):
        self.t = [t0]
        self.up = True
        self.alive = True
        self.kills = []
        self.sent = []
        self.flat = flat
        self.g = HG.Guard(4242, 8766, root=tmp, clock=lambda: self.t[0], ping_fn=lambda: self.up, alive_fn=lambda: self.alive,
                          kill_fn=lambda: self.kills.append(self.t[0]) or True, flat_fn=lambda: self.flat,
                          notify=lambda ti, b, k: self.sent.append((ti, b, k)), state_path=os.path.join(tmp, "hg.json"),
                          stacks=os.path.join(tmp, "stacks.txt"))

    def run(self, seconds):
        out = []
        end = self.t[0] + seconds
        while self.t[0] < end and not self.g.done:
            out.append(self.g.step())
            self.t[0] += HG.CHECK_S
        return out


def test_guard(tmp):
    import engine.board_events as BE
    keep = BE.emit
    boards = []
    BE.emit = lambda *a, **k: boards.append(a)
    try:
        # b. the 2026-11-25 hang: the server started long before, stops answering at 17:22 ET
        w = World(tmp, et(2026, 11, 25, 16, 0))
        w.run(3600)
        w.up = False
        t_hang = w.t[0] = et(2026, 11, 25, 17, 22)
        w.run(600)
        rs = w.kills[0] if w.kills else None
        check("a1/b. no answer from 17:22 ET -> restarted (flat) within 5 min, ONE line, one board event",
              rs is not None and rs - t_hang <= 300 and len(w.sent) == 1 and "restarted" in w.sent[0][0] and len(boards) == 1
              and w.g.done, (rs and rs - t_hang, w.sent))
        st = json.load(open(os.path.join(tmp, "hg.json")))
        check("a2. the restart is recorded (data/hang_guard.json: since, minutes, killed)", st["last"]["killed"] is True
              and st["last"]["since"] == int(t_hang) and 2 <= st["last"]["min"] <= 5, st)
        # a trade may be open: never killed, one line, then killed once flat
        w2 = World(tmp, et(2026, 11, 26, 9, 0), flat="LIT trade open")
        w2.run(300)
        w2.up = False
        w2.run(900)
        told = len(w2.sent)
        check("a3. a trade may be open: NOT killed, one line saying so (never repeated)", not w2.kills and told == 1
              and "NOT restarted" in w2.sent[0][0] and "broker" in w2.sent[0][1], w2.sent)
        w2.flat = None
        w2.run(60)
        check("a4. ... and restarted as soon as the files say flat", len(w2.kills) == 1 and "restarted" in w2.sent[-1][0])
        # comes back by itself
        w3 = World(tmp, et(2026, 11, 26, 9, 0), flat="trade open")
        w3.run(300)
        w3.up = False
        w3.run(400)
        w3.up = True
        w3.run(40)
        check("a5. a hung server that answers again by itself: left alone, one 'answers again' line after the 'NOT restarted' one",
              not w3.kills and [s[0] for s in w3.sent] == ["PC server hung: NOT restarted", "PC server answers again"], w3.sent)
        w4 = World(tmp, et(2026, 11, 26, 9, 0))
        w4.up = False
        r = w4.run(HG.START_GRACE_S - HG.CHECK_S)
        check("a6. a server still starting (first 2 min) is never called hung", not w4.kills and set(r) == {"waiting"}, r)
        w5 = World(tmp, et(2026, 11, 26, 9, 0))
        w5.up = True
        w5.run(60)
        w5.alive = False
        check("a7. the server exited (the supervisor restarts it): the guard ends quietly", w5.g.step() == "gone" and w5.g.done
              and not w5.sent)
        w6 = World(tmp, et(2026, 11, 26, 9, 0))
        w6.run(300)
        w6.up = False
        r = w6.run(HG.HANG_S - HG.CHECK_S)
        check("a8. a short busy moment (under 2.5 min) is not acted on", not w6.kills and "restarted" not in r)
        check("a9. HANG_S + one check + the supervisor's 5 s restart stay inside the 5-minute promise",
              HG.HANG_S + HG.CHECK_S + HG.PING_TIMEOUT_S + 5 <= 300)
    finally:
        BE.emit = keep


HUNG = r'''
import socket, time
s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind(("127.0.0.1", int(__import__("sys").argv[1])))
s.listen(50)
conns = []
while True:
    c, _ = s.accept(); conns.append(c)          # accepts, never answers: what a frozen server looks like from outside
'''

FROZEN = r'''
import faulthandler, sys, time
fh = open(sys.argv[1], "w")
faulthandler.dump_traceback_later(1, repeat=False, file=fh)
def frozen_here():
    time.sleep(3)                                # the "event loop" never comes back to re-arm it
frozen_here()
'''


def test_real(tmp):
    if os.name == "nt":
        check("c. (posix only here)", True)
        return
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    p = subprocess.Popen([sys.executable, "-c", HUNG, str(port)])
    try:
        time.sleep(1.0)
        t0 = time.time()
        up = HG.ping(port, timeout=2)
        check("c1. the real ping says 'no answer' for a server that accepts but never answers (within its timeout)",
              up is False and time.time() - t0 < 5)
        check("c2. alive() sees the process", HG.alive(p.pid))
        ok = HG.kill_tree(p.pid)
        p.wait(timeout=10)
        check("c3. kill_tree ends it (the supervisor would start a fresh server)", ok and p.returncode is not None)
    finally:
        if p.poll() is None:
            p.kill()
    path = os.path.join(tmp, "dump.txt")
    subprocess.run([sys.executable, "-c", FROZEN, path], timeout=30)
    where = HG.where_stuck(time.time(), path)
    check("c4. a frozen loop's faulthandler dump names the frozen function (the next hang tells us its cause)",
          "frozen_here" in where, where)


def test_wiring():
    src = open(os.path.join(ROOT, "server.py"), encoding="utf-8").read()
    start = src[src.index("def _autostart_startup"):src.index('app.router.add_event_handler("startup", _autostart_startup)')]
    check("d1. server.py starts the hang guard + the stack dump in its startup, before the watchdog",
          "_hang_guard_start()" in start and start.index("_hang_guard_start()") < start.index("WATCHDOG.start()"))
    hs = src[src.index("def _hang_guard_start"):src.index("def _autostart_startup")]
    check("d2. only on the supervised PC server (LE_SUPERVISED=1) and off with LE_HANG_GUARD=0",
          'LE_SUPERVISED") != "1"' in hs and "_hg.enabled()" in hs and HG.enabled({"LE_HANG_GUARD": "0"}) is False)
    check("d3. spawn() refuses outside the supervised server (tests, the cloud)", HG.spawn(1, 1, env={"LE_SUPERVISED": "0"}) is False)
    ign = subprocess.run(["git", "check-ignore", "--no-index", "data/hang_guard.json", "data/hang_guard_123.lock",
                          "logs/hang_stacks.txt"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    check("d4. its files are git-ignored (the update never blocks on them)", len(ign) == 3, ign)


def test_clusters():
    from engine.generated_files import is_generated
    from engine import self_heal as SH
    pre = open(os.path.join(ROOT, "engine", "preflight.py"), encoding="utf-8").read()
    check("e1. update hold-back cluster: results.json is a generated file, a hand edit parks, market data parks",
          is_generated("research/orderflow/results.json") and SH.parkable("engine/x.py") and SH.parkable("data/NQ_5m.csv"))
    check("e2. false 'ATLAS 25K is on Sim' cluster: preflight reads the kind first (the label is 'ATLAS <account>')",
          'ab.get("kind") or ab.get("label")' in pre)
    check("e3. the self-heal 'could not fix' board line is once a day per fault (the PC's old code posted it every 15 min)",
          SH.ALERT_EVERY_S >= 24 * 3600)


def test_rt22_followups(tmp):
    """red team #22 follow-ups: one flat check for every account (the update and the guard), and the guard's bare async ping."""
    from engine import autoupdate as AU
    root = os.path.join(tmp, "flat")
    os.makedirs(os.path.join(root, "data"))
    check("f1. no state files: flat", AU.files_flat_reason(root) is None)
    open(os.path.join(root, "data", "ninjatrader_state_acctb.json"), "w").write(json.dumps({"legs": [
        {"status": "protected", "instrument": "MNQ 12-26"}]}))
    why = AU.files_flat_reason(root)
    check("f2. an open ATLAS leg (data/ninjatrader_state_acctb.json) = NOT flat for the update, the remote restart, auto-park and "
          "the guard alike", why and "acctb" in why and HG.all_flat_reason(root) == why, why)
    open(os.path.join(root, "data", "ninjatrader_state_acctb.json"), "w").write(json.dumps({"legs": [{"status": "closed"}]}))
    open(os.path.join(root, "data", "ninjatrader_state_rapid.json"), "w").write("{not json")
    why = AU.files_flat_reason(root)
    check("f3. a state file it cannot read = NOT flat (fails closed)", why and "unreadable" in why, why)
    os.remove(os.path.join(root, "data", "ninjatrader_state_rapid.json"))
    open(os.path.join(root, "data", "ninjatrader_state_simcheck.json"), "w").write(json.dumps({"legs": [{"status": "protected"}]}))
    check("f4. closed legs + the self-test's simcheck file: flat", AU.files_flat_reason(root) is None)
    stale = os.path.join(root, "data", "ninjatrader_state_fleet_old.json")
    open(stale, "w").write(json.dumps({"legs": [{"status": "protected", "instrument": "MNQ 12-26"}]}))
    old_t = time.time() - 30 * 86400
    os.utime(stale, (old_t, old_t))
    check("f8. a 30-day-old state file with an open leg (an account the bot no longer runs) no longer blocks every update",
          AU.files_flat_reason(root) is None and HG.all_flat_reason(root) is None, AU.files_flat_reason(root))
    os.utime(stale, None)
    why = AU.files_flat_reason(root)
    check("f9. the same open leg in a FRESH file still blocks (and names the file)", why and "fleet_old" in why, why)
    os.utime(stale, (old_t, old_t))
    bad = os.path.join(root, "data", "ninjatrader_state_bad.json")
    open(bad, "w").write("{broken")
    why = AU.files_flat_reason(root)
    check("f10. a fresh unreadable state file still fails closed, naming the file", why and "ninjatrader_state_bad.json" in why
          and "unreadable" in why, why)
    os.remove(bad)
    src = open(os.path.join(ROOT, "server.py"), encoding="utf-8").read()
    al = src[src.index('@app.get("/api/health/alive")'):src.index('@app.get("/api/health/ping")')]
    check("f5. GET /api/health/alive is async and reads nothing (no HEARTBEAT / health block / lock)",
          "async def health_alive" in al and "HEARTBEAT" not in al and "WATCHDOG" not in al and 'return {"ok": True}' in al)
    hg = open(os.path.join(ROOT, "engine", "hang_guard.py"), encoding="utf-8").read()
    check("f6. the guard pings /api/health/alive (not the heavier /api/health/ping)", "/api/health/alive\"" in hg
          and "/api/health/ping\", headers" not in hg)
    try:
        from fastapi.testclient import TestClient
        import importlib
        os.environ.setdefault("LE_NO_AUTOSTART", "1")
        srv = importlib.import_module("server")
        r = TestClient(srv.app, client=("127.0.0.1", 50000)).get("/api/health/alive")
        check("f7. the real app answers /api/health/alive with {'ok': true}", r.status_code == 200 and r.json().get("ok") is True,
              (r.status_code, r.text[:100]))
    except Exception as e:  # noqa: BLE001
        check("f7. the real app answers /api/health/alive", False, f"{e.__class__.__name__}: {e}")


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="le_zeroerr2_")
    try:
        test_guard(tmp)
        test_real(tmp)
        test_wiring()
        test_clusters()
        test_rt22_followups(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
