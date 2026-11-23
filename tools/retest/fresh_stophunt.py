"""Fresh-data check (2026-11-23): the frozen stop-hunt FINAL specs (tools/stophunt.FINAL, fixed 2026-10-23) re-run on the
bars as they are now (data to 2026-11-19). 2026-10-19..11-19 was never seen by any pick. PAPER ONLY.
    python -X utf8 tools/retest/fresh_stophunt.py
"""
import json, os, sys, math
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [ROOT, os.path.join(ROOT, "tools")]
import numpy as np
import stophunt as SH
g = SH.base()
out = {}
for nm in ("sh_asia_resweep", "sh_trend_idm5"):
    st, rows = SH.one(g, SH.FINAL[nm])
    out[nm] = rows
    for a, z, lab in (("2026-07-01", "2026-10-16", "Jul-Oct16"), ("2026-10-17", "2026-12-31", "FRESH Oct17-Nov19"), ("2022-05-01", "2025-12-31", "2022-05..25")):
        p = np.array([r["pnl_usd"] for r in rows if a <= r["day"] <= z])
        t = p.mean() / (p.std(ddof=1) / math.sqrt(len(p))) if len(p) > 2 else 0.0
        print(nm, lab, len(p), "trades", round(float(p.sum())), "$", "win", round(100 * float((p > 0).mean()), 1) if len(p) else None, "t", round(float(t), 2))
json.dump(out, open(os.path.join(ROOT, "research", "retest", "fresh_stophunt.json"), "w"), default=str)
