"""MECH track smoke test: run mech_ifvg once (no scoring) and print a few trades + quick stats."""
import collections
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.strategy_lab import bars  # noqa: E402
from tools.lab_models import mech_ifvg as M  # noqa: E402

sym = sys.argv[1] if len(sys.argv) > 1 else "NQ"
extra = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
other = "ES" if sym == "NQ" else "NQ"
t0 = time.time()
b = bars(sym, "5m", "2025-04-14", "2026-10-16", warmup_days=7)
e = bars(other, "5m", "2025-04-14", "2026-10-16", warmup_days=7)
dbg = []
tr = M.run(b, {"sym": sym, **extra}, e, _debug=dbg)
tr = [x for x in tr if x["day"] >= "2025-04-14"]
print(f"{len(tr)} trades in {time.time() - t0:.1f}s")
for x in tr[:8]:
    print(x["day"], x["dir"], x["setup"], x["entry"], x["stop"], x["target"], x["exit"], x["exit_kind"], x["qty"], x["pnl"], x["r"])
k = collections.Counter(x["exit_kind"] for x in tr)
print(k)
import numpy as np  # noqa: E402
for lab, a, z in (("y2025", "2025-04-14", "2025-12-31"), ("ytd", "2026-01-02", "2026-10-16")):
    s = [x for x in tr if a <= x["day"] <= z]
    pn = np.array([x["pnl"] for x in s])
    print(lab, len(s), "trades; median stop pts", np.median([x["risk_pts"] for x in s]), "median qty", np.median([x["qty"] for x in s]))
print(collections.Counter(lv for x in tr for lv in x["levels"]).most_common())
