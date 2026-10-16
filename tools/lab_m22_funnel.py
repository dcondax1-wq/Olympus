"""ICT 2022 model mechanics check: setup funnel counts, frequency, planned R and stop sizes (no P&L printed).

  python tools/lab_m22_funnel.py 2026-01-02 2026-06-30
"""
import collections
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
src = os.path.join(ROOT, "tools", "lab_models", "ict2022.py")
raw = open(src, "rb").read()
if raw.startswith(b"\xef\xbb\xbf"):
    open(src, "wb").write(raw[3:])
    print("BOM removed")
from tools.strategy_lab import bars  # noqa: E402
from tools.lab_models import ict2022 as m  # noqa: E402

a, z = sys.argv[1], sys.argv[2]
for sym in ("NQ", "ES"):
    b = bars(sym, "5m", a, z, warmup_days=7)
    ndays = len({d for d in b["day"] if d >= a})
    for bias in (True, False):
        dbg = []
        tr = m.run(b, {"sym": sym, "bias": bias}, None, _debug=dbg)
        tr = [t for t in tr if t["day"] >= a]
        print(sym, "bias", bias, "trades", len(tr), "tpw", round(len(tr) / (ndays / 5), 2), dbg[0])
        print("   exit", dict(collections.Counter(t["exit_kind"] for t in tr)), "tgt",
              dict(collections.Counter(t["tgt_kind"] for t in tr)), "sess", dict(collections.Counter(t["sess"] for t in tr)))
        rs = sorted(t["plan_r"] for t in tr)
        rk = sorted(t["risk_pts"] for t in tr)
        if rs:
            print("   plan_r q25/50/75", rs[len(rs) // 4], rs[len(rs) // 2], rs[3 * len(rs) // 4],
                  " stop pts q25/50/75", rk[len(rk) // 4], rk[len(rk) // 2], rk[3 * len(rk) // 4])
