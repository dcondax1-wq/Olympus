"""ninjatrader/LE_Bridge.cs (socket order bridge, PAPER prototype) end to end with engine/nt_socket.py, 2026-11-26.

1. C# 5 compile (mono mcs -langversion:5) of the REAL LE_Bridge.cs against tests/nt_stub/NtStubsBridge.cs (stub NinjaTrader
   types + a small order simulator + a driver that starts the add-on on a free localhost port).
2. The Python adapter (engine.nt_socket.NtSocketAdapter, Sim101) trades against it: bracket, breakeven, target fill seen,
   exit flat, kill; the bridge refuses a non-Sim account, an expired command, an unknown command and a foreign order id.
3. NinjaTrader drops a flat position from Account.Positions: the bridge must still report FLAT (the exit check needs it).

The stubs check syntax and protocol logic, not NinjaTrader's real API. Skipped (exit 0) when mono is not installed.
Run: python -X utf8 -m tests.test_le_bridge_cs
"""
from __future__ import annotations

import datetime as dt
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
STUB = os.path.join(ROOT, "tests", "nt_stub", "NtStubsBridge.cs")
CS = os.path.join(ROOT, "ninjatrader", "LE_Bridge.cs")
FAILS = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail and not ok else ""), flush=True)
    if not ok:
        FAILS.append(name)


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def main() -> int:
    if not (shutil.which("mcs") and shutil.which("mono")):
        print("SKIP: mono (mcs) not installed")
        return 0
    from engine import ninjatrader as nt
    from engine.nt_socket import BridgeClient, NtSocketAdapter
    tmp = tempfile.mkdtemp(prefix="le_bridge_cs_")
    proc = None
    try:
        exe = os.path.join(tmp, "bridge.exe")
        r = subprocess.run(["mcs", "-langversion:5", "-out:" + exe, STUB, CS], capture_output=True, text=True, timeout=120)
        check("1. LE_Bridge.cs compiles as C# 5 against the NinjaTrader stubs (+ driver)", r.returncode == 0, (r.stdout + r.stderr)[-800:])
        if r.returncode:
            return 1
        port = _free_port()
        env = {**os.environ, "LE_NTSTUB_DIR": os.path.join(tmp, "nt"), "LE_BRIDGE_PORT": str(port)}
        proc = subprocess.Popen(["mono", exe], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=env)
        first = proc.stdout.readline()
        while first and not first.startswith("READY"):
            first = proc.stdout.readline()
        check("2a. the bridge starts and listens on the configured port", first.strip() == f"READY {port}", first)

        def move(px):
            proc.stdin.write(f"MOVE {px}\n")
            proc.stdin.flush()
            proc.stdout.readline()

        c = BridgeClient(port=port)
        ping = c.request("PING")
        check("2b. PING answers with the build", ping and ping.get("ok") and "le_bridge" in ping.get("build", ""), str(ping))
        wed = dt.datetime(2026, 10, 21, 10, 5, tzinfo=nt.ET).timestamp()

        class Ad(NtSocketAdapter):
            def _gate(self, kind):             # the session clock is not what this test checks: a weekday 10:05 ET for it
                real = self.clock
                self.clock = lambda: wed
                try:
                    return super()._gate(kind)
                finally:
                    self.clock = real

        folder = os.path.join(tmp, "nt_folder")
        os.makedirs(folder)
        cfg = {"adapter": "nt-socket", "sym": "NQ", "armed": True, "nt_folder": folder, "params": {"max_micros": 40, "flat_mod": 955},
               "nt_max_entries_day": 999, "nt_state_path": os.path.join(tmp, "st.json"), "nt_audit_log": os.path.join(tmp, "a.log"),
               "bridge_port": port, "nt_lock": False, "nt_instrument": "MNQ 12-26", "nt_instrument_mini": "NQ 12-26"}
        ad = Ad(cfg)
        ad._alert_fn = lambda t: None
        check("2c. adapter on Sim101 ready", not ad.disabled, str(ad.disabled))
        t0 = time.perf_counter()
        r = ad.send({"sym": "NQ", "side": "buy", "qty": 2, "stop": 24990.13, "target": 25080.0, "entry": 25020.0, "entry_t": int(time.time())})
        ms = (time.perf_counter() - t0) * 1000
        lg = ad.legs[0] if ad.legs else {}
        check("2d. bracket through the real C# bridge: filled, stop + target WORKING, protected",
              r.get("ok") and lg.get("status") == "protected" and ad.read_order(lg["stop_id"])["state"] == "WORKING"
              and ad.read_order(lg["target_id"])["state"] == "WORKING", str(r))
        print(f"     entry -> fill -> bracket confirmed in {ms:.0f} ms (local, simulated fills)")
        r = ad.send({"side": "modify", "stop": 25020.25})
        check("2e. breakeven CHANGE accepted", r.get("ok"), str(r))
        move(25080.0)                                       # the target fills, OCO cancels the stop
        ad.tick()
        p = ad.position_for("MNQ 12-26")
        check("3. target filled: NinjaTrader removed the position, the bridge reports it FLAT; the leg closes",
              p and p["side"] == "FLAT" and ad.read_order(lg["target_id"])["state"] == "FILLED"
              and ad.read_order(lg["stop_id"])["state"] == "CANCELLED" and not [x for x in ad.legs if x["status"] in nt.OPEN_STATUSES],
              f"{p} {ad.legs}")
        move(25020.0)
        r = ad.send({"sym": "NQ", "side": "sell", "qty": 1, "stop": 25050, "target": 24950, "entry": 25020, "entry_t": int(time.time()) + 1})
        r2 = ad.send({"sym": "NQ", "side": "exit", "reason": "TIME STOP"})
        p = ad.position_for("MNQ 12-26")
        check("2f. short entry, then exit: CLOSEPOSITION -> flat, bracket cancelled", r.get("ok") and r2.get("ok") and p["side"] == "FLAT",
              f"{r} {r2} {p}")
        ad.send({"sym": "NQ", "side": "buy", "qty": 1, "stop": 24990, "target": 25080, "entry": 25020, "entry_t": int(time.time()) + 2})
        k = ad.kill()
        check("2g. kill: flat, then no new entry", k.get("ok") and ad.position_for("MNQ 12-26")["side"] == "FLAT"
              and "kill" in ad.send({"sym": "NQ", "side": "buy", "qty": 1, "stop": 24990, "target": 25080, "entry": 25020}).get("error", ""), str(k))
        now_ms = int(time.time() * 1000)
        x = c.request(f"OIF t1 {now_ms} 4000 PLACE;MFFUEVAL123;MNQ 12-26;BUY;1;MARKET;0;0;DAY;;LET1;;")
        check("2h. bridge refuses a non-Sim account (paper only)", x and not x["ok"] and "paper-only" in x["error"], str(x))
        x = c.request(f"OIF t2 {now_ms - 9000} 4000 PLACE;Sim101;MNQ 12-26;BUY;1;MARKET;0;0;DAY;;LET2;;")
        check("2i. bridge refuses an expired command", x and not x["ok"] and "expired" in x["error"], str(x))
        x = c.request(f"OIF t3 {now_ms} 4000 CANCEL;;;;;;;;;;NOTOURS1;;")
        y = c.request("FLY")
        check("2j. bridge refuses a foreign order id and an unknown command", x and not x["ok"] and y and not y["ok"], f"{x} {y}")
        x = c.request(f"OIF t4 {int(time.time() * 1000)} 4000 PLACE;Sim101;MNQ 12-26;BUY;1;MARKET;0;0;DAY;;LET4;;|CHANGE;;;;0;;0;1;;;BAD;;")
        s = c.request("SNAP Sim101")
        check("2k. a request with one bad line runs NO line (checked first)", x and not x["ok"] and "LET4" not in s["orders"], str(x))
        rt = sorted(c.rtts + ad.client.rtts)
        print(f"     round trips: n={len(rt)} p50={rt[len(rt) // 2]:.2f} ms p99={rt[int(len(rt) * .99)]:.2f} ms")
    finally:
        if proc is not None:
            try:
                proc.stdin.write("QUIT\n")
                proc.stdin.flush()
                proc.wait(timeout=10)
            except Exception:
                proc.kill()
        shutil.rmtree(tmp, ignore_errors=True)
    print("ALL PASS" if not FAILS else f"{len(FAILS)} FAILED: {FAILS}")
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
