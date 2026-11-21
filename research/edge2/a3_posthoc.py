"""POST-HOC (after A3 failed the gate; shown, never eligible): A3's stop entry with worse stop-order slippage (trigger + 2 / 6 / 10
ticks) and the R of the skipped signals per span, fixed $250 view at 10 ticks of arrival cost."""
import collections, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import edge2 as E
from tools import atlas_edge as AE
from tools import atlas_fills as AF
out = {}
for add in (2, 6, 10):
    U, sk = [], collections.defaultdict(list)
    for u in AF.units():
        v, why = E.stop_fill(u, 12, 5, 10, add=add)
        if v is None:
            p = AF.priced(u, 10, 10)
            sk[u["day"][:4] if u["day"] < "2026" else ("H1" if u["day"] <= "2026-06-30" else "H2")].append(AE.usd250(p) / 250.0)
        else:
            U.append(v)
    fx = AE.fixed(AE.to_T(U))
    out[f"add{add}"] = {"fixed": fx, "skipped_R": {k: (len(v), round(sum(v) / len(v), 3)) for k, v in sorted(sk.items())}}
    print(f"add {add}:", " ".join(f"{sp} ${fx[sp]['per_month']} PF {fx[sp]['pf']} {fx[sp]['tpw']}/wk" for sp in fx), "| skipped n, avg R:", out[f"add{add}"]["skipped_R"])
U0 = [AF.priced(u, 10, 10) for u in AF.units()]
fx0 = AE.fixed(AE.to_T(U0)); print("base 10t:", " ".join(f"{sp} ${fx0[sp]['per_month']} PF {fx0[sp]['pf']}" for sp in fx0))
E.save("A3_posthoc", out)
