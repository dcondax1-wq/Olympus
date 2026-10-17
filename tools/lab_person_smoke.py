"""PERSON track smoke test: one plain backtest per discretionary-layer variant on a short window (no live-loop replay).

  python tools/lab_person_smoke.py [days_from days_to [variant,variant]]
"""
import collections
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("LE_NO_AUTOSTART", "1")
from engine.backtest import run  # noqa: E402
from tools.lab_person_run import BASE, VARIANTS  # noqa: E402

a, z = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else ("2026-08-06", "2026-10-16")
only = sys.argv[3].split(",") if len(sys.argv) > 3 else list(VARIANTS)
for k in only:
    p = {**BASE, **VARIANTS[k], "days_from": a, "days_to": z}
    t0 = time.time()
    r = run("NQ", "5m", p, light=True)
    tr = r["trades"]
    ex = collections.Counter(t.get("exit_reason", "?").split(" ")[0] for t in tr)
    tiers = collections.Counter((t.get("draw") or {}).get("tier", "-") for t in tr)
    srcs = collections.Counter((t.get("draw") or {}).get("source", "-") for t in tr)
    tp1 = sum(1 for t in tr if t.get("partial_draw"))
    rp = sorted(round(t["risk_pts"], 1) for t in tr)
    rr = sorted(t.get("rr") for t in tr if t.get("rr") is not None)
    print(f"{k:12s} n={len(tr):3d} net={r['stats']['net']:+9.1f} {time.time() - t0:5.1f}s exits={dict(ex)} tiers={dict(tiers)} "
          f"src={dict(srcs)} tp1={tp1} risk_med={rp[len(rp) // 2] if rp else None} rr_med={rr[len(rr) // 2] if rr else None}",
          flush=True)
