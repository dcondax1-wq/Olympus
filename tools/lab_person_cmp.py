"""PERSON track: per-trade comparison of two variants' live-loop replay trades (matched on entry time).

  python tools/lab_person_cmp.py base 1_target [ytd]
"""
import collections
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "research", "lab")


def load(v, big):
    with open(os.path.join(OUT, f"P_{v}_trades_{big}.json"), encoding="utf-8") as fh:
        return {int(t["entry_t"]): t for t in json.load(fh)}


a, b = sys.argv[1], sys.argv[2]
big = sys.argv[3] if len(sys.argv) > 3 else "ytd"
A, B = load(a, big), load(b, big)
common = sorted(set(A) & set(B))
only_a, only_b = sorted(set(A) - set(B)), sorted(set(B) - set(A))
print(f"{a}: {len(A)} trades, {b}: {len(B)} trades, common {len(common)}, only {a} {len(only_a)}, only {b} {len(only_b)}")
dr = [B[k]["r"] - A[k]["r"] for k in common]
dp = [B[k]["pnl"] - A[k]["pnl"] for k in common]
print(f"common trades: sum R {sum(A[k]['r'] for k in common):+.1f} -> {sum(B[k]['r'] for k in common):+.1f} "
      f"(diff {sum(dr):+.1f}R, ${sum(dp):+,.0f}); better {sum(x > 0.05 for x in dr)}, worse {sum(x < -0.05 for x in dr)}")
print(f"only-{a} trades: n={len(only_a)} R {sum(A[k]['r'] for k in only_a):+.1f} ${sum(A[k]['pnl'] for k in only_a):+,.0f}")
print(f"only-{b} trades: n={len(only_b)} R {sum(B[k]['r'] for k in only_b):+.1f} ${sum(B[k]['pnl'] for k in only_b):+,.0f}")
ex = collections.defaultdict(lambda: [0, 0.0, 0.0])
for k in common:
    key = (A[k].get("exit"), B[k].get("exit"))
    ex[key][0] += 1
    ex[key][1] += A[k]["r"]
    ex[key][2] += B[k]["r"]
print("exit transitions (common trades):  n  R_a -> R_b")
for (ea, eb), (n, ra, rb) in sorted(ex.items(), key=lambda kv: -kv[1][0]):
    print(f"  {str(ea):22s} -> {str(eb):22s} {n:3d}  {ra:+6.1f} -> {rb:+6.1f}")
mon = collections.defaultdict(lambda: [0.0, 0.0])
for t in A.values():
    mon[t["day"][:7]][0] += t["pnl"]
for t in B.values():
    mon[t["day"][:7]][1] += t["pnl"]
print("month   " + a.rjust(9) + " " + b.rjust(9))
for m in sorted(mon):
    print(f"{m} {mon[m][0]:+9,.0f} {mon[m][1]:+9,.0f}")
