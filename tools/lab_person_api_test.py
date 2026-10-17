"""Test the standalone draws_at / manage_step API against the engine's own draw picks (PERSON track)."""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("LE_NO_AUTOSTART", "1")
import numpy as np  # noqa: E402

import engine.liquidity_map as lm  # noqa: E402

from engine.backtest import run  # noqa: E402
from tools import strategy_lab as sl  # noqa: E402
from tools.lab_person_run import BASE, VARIANTS  # noqa: E402

bars5 = sl.bars("NQ", "5m")
r = run("NQ", "5m", {**BASE, **VARIANTS["14_far_pm"], "days_from": "2026-08-20", "days_to": "2026-10-16"}, light=True)
tr = [t for t in r["trades"] if t.get("draw")][:12]
same_src = same_px = 0
t0 = time.time()
for t in tr:
    d = t["dir"]
    ds = lm.draws_at(bars5, t["entry_t"], d, t["signal_price"], t["stop0"])
    fin = next((x for x in ds if x["role"] == "final"), None)
    par = next((x for x in ds if x["role"] == "partial"), None)
    eng = t["draw"]
    same_src += int(fin is not None and fin["source"] == eng["source"])
    same_px += int(fin is not None and abs(fin["price"] - eng["price"]) < 0.3)
    print(f"{t['day']} {'L' if d == 1 else 'S'} entry {t['signal_price']:.2f} | engine T {eng['source']:6s} {eng['price']:.2f} "
          f"{eng['dist_r']:.2f}R | draws_at T {fin['source'] if fin else '-':6s} {fin['price'] if fin else 0:.2f} "
          f"{fin['dist_r'] if fin else 0:.2f}R reach={fin['within_reach'] if fin else '-'} | TP1 "
          f"{(t.get('partial_draw') or {}).get('source', '-')} vs {par['source'] if par else '-'} | n={len(ds)}")
print(f"final source match {same_src}/{len(tr)}, price match {same_px}/{len(tr)}, {(time.time() - t0) / max(1, len(tr)):.2f}s/call")
x = ds[0]
print("keys:", sorted(k for k in x.keys()))

# manage_step on the last trade's path, compared with the engine's own exits (person mode, no trail)
t = tr[-1]
b = bars5
i0 = int(np.searchsorted(b["time"].values, t["entry_t"]))
pos = lm.new_position(t["dir"], t["entry"], t["stop0"], t["qty"], i0, t["target"],
                      (t.get("partial_draw") or {}).get("target"))
ctx = {"o": b["open"].values, "h": b["high"].values, "l": b["low"].values, "c": b["close"].values, "mod": b["mod"].values,
       "atr": t.get("atr") or 20.0, "params": {"stall_bars": 6}}
for i in range(i0, i0 + 120):
    out = lm.manage_step(pos, i, ctx)
    if out["fills"]:
        print("manage_step", b["et"].iloc[i].strftime("%m-%d %H:%M"), out["fills"])
    if out["closed"]:
        break
print("engine exits:", [(e["reason"], e["price"], e["qty"]) for e in t["exits"]])


