"""Post-hoc (labelled): the REF-best unit policy (LIT only, both phases, $min ask) as a whole fleet. n=1000."""
import json, os, sys
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.ERROR)
import search as S, fleetpol as FP
LO = ("L", 1.0, 1.0, "L", 1.0, 1.0, "min")
S.KITS["K4 LIT only both phases"] = {t: LO for t in ("B50", "B25", "R25", "R50", "FN", "LU")}
S.LISTS["L9 B50,FN"] = ("B50", "FN")
G = [(b, l, "K4 LIT only both phases", "S0", 0, sp) for b in (150, 300, 500) for l in ("L9 B50,FN", "L3 R50+FN alt") for sp in ("H1", "H2", "REF")]
def job(a):
    return a, FP.run(S.P_of(*a[1:5]), a[0], a[5], 1000)
if __name__ == "__main__":
    out = {}
    with Pool(4) as p:
        for a, r in p.imap_unordered(job, G):
            out[" | ".join(map(str, a))] = r; print(a, r["per_month"], r["p10"], flush=True)
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "litonly.json"), "w"), indent=0)
