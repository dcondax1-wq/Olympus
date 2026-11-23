"""Where the lift comes from: Lucid alone vs the BLITZ eval lane alone (n=1000, H1/H2/REF)."""
import json, os, sys
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.ERROR)
import search as S, fleetpol as FP
G = [(b, l, k, "S0", 0, sp) for b in (150, 300, 500) for l, k in (("L3 R50+FN alt", "K1 +BLITZ lane in every eval"),
     ("L6 R50+FN+LU alt", "K0 today's books"), ("L7 R50 only", "K0 today's books"), ("L2 FN,R50", "K1 +BLITZ lane in every eval"))
     for sp in ("H1", "H2", "REF")]
G += [(b, "L3 R50+FN alt", "K0 today's books", "S0", 0, sp, "P5") for b in (300,) for sp in ("H1", "H2", "REF")]
def job(a):
    pol = a[6] if len(a) > 6 else "P4"
    return a, FP.run(S.P_of(a[1], a[2], a[3], a[4], pol), a[0], a[5], 1000)
if __name__ == "__main__":
    out = {}
    with Pool(4) as p:
        for a, r in p.imap_unordered(job, G):
            out[" | ".join(map(str, a))] = r; print(a, r["per_month"], flush=True)
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "decomp.json"), "w"), indent=0)
