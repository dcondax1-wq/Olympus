"""Side-by-side: the FILE bridge (engine/ninjatrader.py, OIF files) vs the SOCKET bridge (engine/nt_socket.py + LE_Bridge.cs).

PAPER ONLY. Both adapters trade NinjaTrader's own Sim101 account, alternating rounds (file, socket, file, ...), so no extra
setup is needed and the two never hold a position at the same time. Any other account is refused. Each round: 1-micro MNQ
bracket (stop / target 40 pts away) -> stop to breakeven -> exit; every step timed; errors kept.
Results: logs/exec_compare.jsonl (one line per round), summary with --report.

  python -X utf8 tools/exec_compare.py --pc --rounds 20      on the PC, market open (Sim fills need live prices), LE_Bridge
                                                              installed (F5) and NinjaTrader connected
  python -X utf8 tools/exec_compare.py --report               per bridge: rounds, failures, p50 / p95 / max ms per step
  python -X utf8 tools/exec_compare.py --fake --rounds 5      dry run of this tool on simulated NinjaTraders (no PC);
                                                              its timings are the simulator's, NOT a comparison

The fault drills (NinjaTrader closed mid-trade, connection pulled, OneDrive sync on, a bot restart mid-trade) are run by
hand during the comparison week: research/writeups/execution-2026-11-26.md "Reliability comparison plan".
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import ninjatrader as nt                        # noqa: E402
from engine.nt_socket import FakeBridge, NtSocketAdapter     # noqa: E402

OUT = os.path.join(ROOT, "logs", "exec_compare.jsonl")
ACCOUNT = "Sim101"


def _round(ad, price, clock):
    rec = {"bridge": "socket" if isinstance(ad, NtSocketAdapter) else "file", "t": time.time(), "steps": {}, "errors": []}
    d = 40.0

    def step(name, action):
        t0 = time.perf_counter()
        try:
            r = ad.send(action)
        except Exception as e:                                   # the adapters never raise; this is the harness's own net
            r = {"ok": False, "error": f"{e.__class__.__name__}: {e}"}
        rec["steps"][name] = round((time.perf_counter() - t0) * 1000, 1)
        if not r.get("ok"):
            rec["errors"].append(f"{name}: {r.get('error')}")
        return r

    step("entry_to_protected", {"sym": "NQ", "side": "buy", "qty": 1, "stop": price - d, "target": price + d, "entry": price,
                                "entry_t": int(clock())})
    lg = ad.legs[0] if ad.legs else {}
    rec["protected"] = lg.get("status") == "protected"
    if lg:
        step("breakeven", {"side": "modify", "stop": (lg.get("fill_px") or price) - 4})
    step("exit_flat", {"sym": "NQ", "side": "exit", "reason": "exec_compare"})
    t0 = time.perf_counter()
    ad.tick()
    rec["steps"]["tick"] = round((time.perf_counter() - t0) * 1000, 1)
    p = ad.position_for(ad._instruments()["micro"])
    rec["flat"] = bool(p and p["side"] == "FLAT")
    if not rec["flat"]:
        rec["errors"].append(f"not flat after the exit: {p}")
    rec["ok"] = not rec["errors"]
    return rec


def _write(rec, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")


def run_pc(rounds, path=OUT):
    base = {"adapter": "ninjatrader", "sym": "NQ", "account": ACCOUNT, "nt_account": ACCOUNT, "params": {"max_micros": 1}}
    state = os.path.join(ROOT, "data")
    fa = nt.NinjaTraderAdapter({**base, "nt_state_path": os.path.join(state, "exec_compare_file.json")})
    sa = NtSocketAdapter({**base, "adapter": "nt-socket", "nt_state_path": os.path.join(state, "exec_compare_socket.json")})
    for ad in (fa, sa):
        if ad.account != ACCOUNT or not nt.is_sim(ad.account):
            print(f"REFUSED: {ad.account} is not {ACCOUNT}")
            return 2
        if ad.disabled:
            print(f"{ad.name}: disabled ({ad.disabled})")
            return 2
    px = nt._last_price(fa.folder)[0]
    if not px:
        print("no last price in le_feed (is the LE_Feed / LE_BarFeed running?)")
        return 2
    for i in range(rounds):
        for ad in (fa, sa) if i % 2 == 0 else (sa, fa):
            rec = _round(ad, float(px), time.time)
            _write(rec, path)
            print(f"round {i + 1} {rec['bridge']:6s} {'OK ' if rec['ok'] else 'ERR'} {rec['steps']} {'; '.join(rec['errors'])}")
            time.sleep(3)
            px = nt._last_price(fa.folder)[0] or px
    return 0


def run_fake(rounds, path):
    tmp = tempfile.mkdtemp(prefix="le_exec_cmp_")
    now = [dt.datetime(2026, 10, 21, 10, 5, tzinfo=nt.ET).timestamp()]
    clock = lambda: now[0]                                      # noqa: E731
    try:
        folder = os.path.join(tmp, "NinjaTrader 8")
        fnt = nt._FakeNT(folder)
        fb = FakeBridge(os.path.join(tmp, "bridge"), clock=clock)
        base = {"sym": "NQ", "nt_folder": folder, "params": {"max_micros": 1}, "nt_max_entries_day": 999, "nt_lock": False,
                "nt_audit_log": os.path.join(tmp, "a.log")}
        fa = nt.NinjaTraderAdapter({**base, "adapter": "ninjatrader", "nt_state_path": os.path.join(tmp, "f.json")}, clock=clock)
        fa._sleep = lambda s: (fnt.process(), now.__setitem__(0, now[0] + s))
        sa = NtSocketAdapter({**base, "adapter": "nt-socket", "nt_state_path": os.path.join(tmp, "s.json"), "bridge_port": fb.port},
                             clock=clock)
        sa._sleep = lambda s: now.__setitem__(0, now[0] + s)
        for ad in (fa, sa):
            ad._alert_fn = lambda t: None
        for i in range(rounds):
            for ad in (fa, sa):
                rec = _round(ad, 25020.0, clock)
                rec["fake"] = True
                _write(rec, path)
                print(f"round {i + 1} {rec['bridge']:6s} {'OK ' if rec['ok'] else 'ERR'} {rec['steps']} {'; '.join(rec['errors'])}")
                now[0] += 60
        fb.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


def report(path=OUT):
    try:
        recs = [json.loads(ln) for ln in open(path, encoding="utf-8") if ln.strip()]
    except OSError:
        print(f"no results yet ({path})")
        return 1
    for b in ("file", "socket"):
        rs = [r for r in recs if r["bridge"] == b and not r.get("fake")]
        if not rs:
            print(f"{b}: no PC rounds")
            continue
        bad = [r for r in rs if not r["ok"]]
        print(f"{b}: {len(rs)} rounds, {len(bad)} failed ({100 * len(bad) / len(rs):.1f}%)")
        for s in ("entry_to_protected", "breakeven", "exit_flat", "tick"):
            v = sorted(r["steps"][s] for r in rs if s in r["steps"])
            if v:
                print(f"   {s:20s} p50 {v[len(v) // 2]:8.1f} ms   p95 {v[min(len(v) - 1, int(len(v) * .95))]:8.1f} ms   max {v[-1]:8.1f} ms")
        for r in bad[-5:]:
            print("   ERR", dt.datetime.fromtimestamp(r["t"]).strftime("%m-%d %H:%M"), "; ".join(r["errors"])[:200])
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pc", action="store_true")
    ap.add_argument("--fake", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--rounds", type=int, default=10)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    if a.report:
        return report(a.out or OUT)
    if a.fake:
        return run_fake(a.rounds, a.out or os.path.join(tempfile.gettempdir(), "exec_compare_fake.jsonl"))
    if a.pc:
        return run_pc(a.rounds, a.out or OUT)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
