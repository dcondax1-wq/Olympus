"""Trade watch, ATLAS twin (night W1, 2026-11-16): account B's live entries vs engine/second.run on the same bars, a push ONLY on
a real mismatch (a missed entry at an open B probed with no reason of its own, a fill > 4 ticks worse, a stop missing / off).
Temp folders, a fake twin for the rules + one real twin replay on the repo's bars; nothing is routed, sent or armed.

  python -X utf8 -m tests.test_trade_watch_atlas        # ~5 s
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools import trade_watch as TW  # noqa: E402

RES = []


def check(name, ok, detail=""):
    RES.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {detail}"))


def write_state(root, ledger, probes, held=None):
    os.makedirs(os.path.join(root, "data"), exist_ok=True)
    st = {"v": 1, "account": "SIM-B", "ledger": ledger, "seen": [["probe", t] for t in probes], "held": held or {}}
    with open(os.path.join(root, "data", "live_state_acctb.json"), "w", encoding="utf-8") as fh:
        json.dump(st, fh)


def entry(t, side, stop, fill=None, ok=True, src="macd_sweep", qty=3):
    res = {"ok": ok}
    if fill is not None:
        res["legs"] = [{"fill_px": fill, "filled": qty}]
    return {"t": t + 5, "sym": "NQ", "side": side, "qty": qty, "stop": stop, "target": 99999.0, "entry": 100.0, "entry_t": t,
            "src": src, "strategy": src.upper()[:4], "result": res}


def rules(tmp):
    now = 1791900000                     # 2026-10-13 ~12:40 ET
    t0 = now - 6 * 3600
    T = lambda i: t0 + 300 * i
    tw = [
        {"key": "macd_sweep", "short": "MACD", "entry_t": T(0), "dir": 1, "entry": 100.0, "stop": 90.0, "usd": 120.0},   # same: nothing
        {"key": "macd_sweep", "short": "MACD", "entry_t": T(1), "dir": 1, "entry": 100.0, "stop": 90.0, "usd": 50.0},    # slip 8 ticks
        {"key": "ema_lon_vix", "short": "EMA", "entry_t": T(2), "dir": -1, "entry": 100.0, "stop": 110.0, "usd": -80.0},  # no stop
        {"key": "macd_sweep", "short": "MACD", "entry_t": T(3), "dir": 1, "entry": 100.0, "stop": 90.0, "usd": 60.0},    # stop 12 ticks off
        {"key": "macd_sweep", "short": "MACD", "entry_t": T(4), "dir": 1, "entry": 100.0, "stop": 90.0, "usd": 412.0},   # missed (probed)
        {"key": "macd_sweep", "short": "MACD", "entry_t": T(5), "dir": 1, "entry": 100.0, "stop": 90.0, "usd": 70.0},    # held: no hedging
        {"key": "macd_sweep", "short": "MACD", "entry_t": T(6), "dir": 1, "entry": 100.0, "stop": 90.0, "usd": 70.0},    # not probed (PC off / B open)
        {"key": "macd_sweep", "short": "MACD", "entry_t": T(7), "dir": 1, "entry": 100.0, "stop": 90.0, "usd": 70.0},    # refused (fill_check's)
        {"key": "macd_sweep", "short": "MACD", "entry_t": T(8), "dir": 1, "entry": 100.0, "stop": 90.0, "usd": 70.0},    # qty only + 2 tick slip
        {"key": "macd_sweep", "short": "MACD", "entry_t": T(9), "dir": 1, "entry": 100.0, "stop": 90.0, "usd": 70.0},    # 2nd member, same open
        {"key": "sr_nyreclaim", "short": "S/R", "entry_t": T(9), "dir": 1, "entry": 100.0, "stop": 95.0, "usd": 70.0},
    ]
    ledger = [entry(T(0), "buy", 90.0, fill=100.25), entry(T(1), "buy", 90.0, fill=102.0),
              entry(T(2), "sell", None, fill=100.0, src="ema_lon_vix"), entry(T(3), "buy", 93.0, fill=100.0),
              entry(T(7), "buy", 90.0, ok=False), entry(T(8), "buy", 90.0, fill=100.5, qty=1),
              entry(T(9), "buy", 95.0, fill=100.0, src="sr_nyreclaim")]
    root = os.path.join(tmp, "r1")
    write_state(root, ledger, [T(i) for i in range(10) if i != 6], held={str(T(5)): {"key": "macd_sweep", "why": "no hedging: LIT short"}})
    days_seen = []

    def twin(days, keys):
        days_seen.append((list(days), list(keys)))
        from engine.account_b import trading_day
        return {d: [t for t in tw if trading_day(t["entry_t"]) == d] for d in days}
    fl = TW.atlas_flags(root, now, twin=twin)
    keys = sorted(f["key"] for f in fl)
    want = sorted([f"watch:atlas:{T(1)}:slip", f"watch:atlas:{T(2)}:stop", f"watch:atlas:{T(3)}:stop", f"watch:atlas:{T(4)}:missed"])
    check("a. pushes only: slip > 4 ticks, no stop, stop off the twin, missed at a probed open with no reason", keys == want, keys)
    check("a. the members come from the ledger when no account_b block is there", days_seen and
          set(days_seen[0][1]) >= {"macd_sweep", "ema_lon_vix", "sr_nyreclaim"}, days_seen)
    b = {f["code"]: f["body"] for f in fl}
    check("a. the slip says ticks and $", "8 ticks worse" in b.get("slip", "") and "$12" in b.get("slip", ""), b.get("slip"))
    check("a. the missed one says the twin's $", "+$412" in b.get("missed", ""), b.get("missed"))
    check("a. titles say ATLAS", all(f["title"].startswith("ATLAS vs backtest") for f in fl))
    # old (> 2 days): nothing
    check("b. older than 2 days: nothing", TW.atlas_flags(root, now + 3 * 86400, twin=twin) == [])
    # no state file / a broken twin: no flags, no crash
    check("c. no account B state: nothing", TW.atlas_flags(os.path.join(tmp, "none"), now, twin=twin) == [])

    def boom(days, keys):
        raise RuntimeError("twin failed")
    check("c. a failing twin: nothing, never raises", TW.atlas_flags(root, now, twin=boom) == [])
    # account B off (data/account_b.json says null) and nothing in the ledger: nothing replayed
    r2 = os.path.join(tmp, "r2")
    write_state(r2, [], [T(4)])
    with open(os.path.join(r2, "data", "account_b.json"), "w") as fh:
        json.dump({"account_b": None}, fh)
    check("c. account B off: nothing replayed", TW.atlas_flags(r2, now, twin=twin) == [] and len(days_seen) == 1, days_seen)
    # flags() carries the ATLAS ones next to Zlarior's (no report.json here)
    real_af = TW.atlas_flags
    TW.atlas_flags = lambda r, n: real_af(r, n, twin=twin)
    try:
        fk = sorted(f["key"] for f in TW.flags(root, now))
    finally:
        TW.atlas_flags = real_af
    check("d. flags() includes the ATLAS mismatches", fk == want, fk)


def real_twin(tmp):
    """engine/second.run on the repo's bars: 2026-10-07 09:35 ET, MACD + S/R LONG at 31,214 (stop 31,142.75)."""
    tb = 1791381300
    now = tb + 3600
    root = os.path.join(tmp, "r3")
    write_state(root, [entry(tb, "buy", 31142.75, fill=31214.25, src="macd_sweep")], [tb])
    fl = TW.atlas_flags(root, now)
    check("e. real twin: the same entry and stop as the research -> nothing", fl == [], fl)
    cache = os.path.join(root, "logs", "exec_audit", "atlas_twin.json")
    ok = os.path.exists(cache) and any(t["entry_t"] == tb for d in json.load(open(cache)).values() for t in d["trades"])
    check("e. real twin: the day's twin trades are cached", ok)
    write_state(root, [], [tb])
    with open(os.path.join(root, "data", "account_b.json"), "w") as fh:          # the members from the account_b block
        json.dump({"account_b": {"account": "SIM-B", "strategies": ["ema_lon_vix", "macd_sweep", "sr_nyreclaim"]}}, fh)
    fl = TW.atlas_flags(root, now)
    check("e. real twin: probed, flat, not routed, no reason -> one missed push", [f["code"] for f in fl] == ["missed"], fl)
    write_state(root, [entry(tb, "buy", 31150.0, fill=31216.0, src="macd_sweep")], [tb])
    fl = sorted(f["code"] for f in TW.atlas_flags(root, now))
    check("e. real twin: fill 8 ticks worse and stop 29 ticks closer -> slip + stop", fl == ["slip", "stop"], fl)


def main():
    tmp = tempfile.mkdtemp(prefix="tw_atlas_")
    try:
        rules(tmp)
        real_twin(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
