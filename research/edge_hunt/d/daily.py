"""Daily P&L at real fills for lane E: today's LIT (plain 1x, the base) and the lane's best non-winning candidate
(tree 13 facts, walk-forward, up-only 1.5x: passes the money gate, fails the chance controls; NOT recommended).
Columns: date, variant, trades, pnl_usd (LIT size rule on the 50K, costs + 1 tick slip in), pnl_usd_per_micro (sum of
pts x $2 - $1.40 per micro, size-independent), risk_usd (sum of stop $ at that size)."""
import csv, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import E, HERE
import meta_label as ML
from engine import lit

rows = ML.build()
U0 = [r["u"] for r in rows]
mm = ML.walk_forward(rows, ML.F12, "tree", "D_up15")
out = {}
for name, U in (("today_LIT_1x", [{**u, "m": 1.0} for u in U0]), ("meta_tree13_up15_NOT_A_WINNER", [{**u, "m": mm[u["entry_t"]]} for u in U0])):
    L = E.lit_size(U)
    for l in L:
        k = (l["day"], name)
        d = out.setdefault(k, [0, 0.0, 0.0, 0.0])
        d[0] += 1; d[1] += l["pnl"]; d[2] += l["pts"] * lit.PV - lit.COMM; d[3] += l["risk_usd"]
with open(os.path.join(HERE, "daily.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["date", "variant", "trades", "pnl_usd", "pnl_usd_per_micro", "risk_usd"])
    for (day, nm), (n, p, pm, r) in sorted(out.items()):
        w.writerow([day, nm, n, round(p, 2), round(pm, 2), round(r, 2)])
print(len(out), "rows")
