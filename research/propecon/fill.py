"""Fill the budget table: each top policy at every budget (n=1000)."""
import json, os, sys
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.ERROR)
import search as S, fleetpol as FP
G = [(b, l, k, "S0", 0, sp) for b, l, k in ((150, "L6 R50+FN+LU alt", "K1 +BLITZ lane in every eval"), (500, "L8 R50,LU", "K1 +BLITZ lane in every eval"),
     (150, "L6 R50+FN+LU alt", "K3 eval +BLITZ 2x on Rapid EOD only")) for sp in ("H1", "H2", "REF")]
def job(a): return a, FP.run(S.P_of(*a[1:5]), a[0], a[5], 1000)
if __name__ == "__main__":
    out = {}
    with Pool(4) as p:
        for a, r in p.imap_unordered(job, G): out[" | ".join(map(str, a))] = r; print(a, r["per_month"], r["p10"], r["fees"], flush=True)
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fill.json"), "w"), indent=0)
