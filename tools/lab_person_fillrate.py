"""PERSON track: retest-limit fill rate per period (plain backtest events; the live-loop replay keeps only trades).

  python tools/lab_person_fillrate.py 17_retest6,17b_retest12
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("LE_NO_AUTOSTART", "1")
from engine.backtest import run  # noqa: E402
from tools.lab_person_run import BASE, VARIANTS  # noqa: E402

PER = {"dev": ("2026-01-02", "2026-06-30"), "confirm": ("2026-07-01", "2026-10-16"), "y2025": ("2025-04-14", "2025-12-31")}
for v in sys.argv[1].split(","):
    for per, (a, z) in PER.items():
        r = run("NQ", "5m", {**BASE, **VARIANTS[v], "days_from": a, "days_to": z}, light=False)
        ev = r["events"]
        orders = sum(1 for e in ev if e["type"] == "signal")
        expired = sum(1 for e in ev if e["type"] == "skip" and "not filled within" in e["text"])
        ran = sum(1 for e in ev if e["type"] == "skip" and "reached the target before the retest" in e["text"])
        fills = sum(1 for t in r["trades"] if t.get("entry_kind") == "retest limit")
        tr = [t for t in r["trades"] if t.get("entry_kind") == "retest limit"]
        stop_bar0 = sum(1 for t in tr if t.get("exit_reason") == "STOP" and t.get("bars_held") == 1)
        print(f"{v:14s} {per:8s} orders {orders:3d} filled {fills:3d} ({100 * fills / max(1, orders):.0f}%) expired {expired:3d} "
              f"ran-to-target {ran:3d} | stopped on the fill bar {stop_bar0} | win {sum(t['pnl'] > 0 for t in tr)}/{len(tr)}",
              flush=True)
