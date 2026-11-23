"""Stage 2 search (pick on H1 = 2026 Jan-Jun paths ONLY), then score the top 3 per budget + today's plan on H1/H2/REF."""
import itertools, json, os, sys, time
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.ERROR)
import fleetpol as FP
AGG2 = ("LAB", 2.0, 2.0, "LA", 1.0, 1.0, "plan"); AGG1 = ("LAB", 1.0, 1.0, "LA", 1.0, 1.0, "plan")
ALL = ("B50", "B25", "R25", "R50", "FN", "LU")
KITS = {"K0 today's books": {}, "K1 +BLITZ lane in every eval": {t: AGG1 for t in ALL},
        "K2 eval +BLITZ and 2x size everywhere": {t: AGG2 for t in ALL},
        "K3 eval +BLITZ 2x on Rapid EOD only": {"R50": AGG2, "R25": AGG2}}
LISTS = {"L0 B50,B25,R25": ("B50", "B25", "R25"), "L1 R50,R25": ("R50", "R25"), "L2 FN,R50": ("FN", "R50"),
         "L3 R50+FN alt": ("R50", "FN"), "L4 B50,B25": ("B50", "B25"), "L5 R25": ("R25",), "L6 R50+FN+LU alt": ("R50", "FN", "LU"),
         "L7 R50 only": ("R50",), "L8 R50,LU": ("R50", "LU")}
TODAY = {150: ("L2 FN,R50", "K0 today's books", "S0", 0), 300: ("L3 R50+FN alt", "K0 today's books", "S0", 0),
         500: ("L3 R50+FN alt", "K0 today's books", "S0", 0)}


def P_of(l, kit, stop, stag, pol="P4"):
    return {"list": LISTS[l], "books": KITS[kit], "stop": stop, "stagger": stag, "pol": pol, "alt": "alt" in l}


def job(a):
    b, l, kit, stop, stag, span, n = a
    return a, FP.run(P_of(l, kit, stop, stag), b, span, n)


if __name__ == "__main__":
    stage, n = sys.argv[1], int(sys.argv[2])
    t0 = time.time()
    if stage == "search":
        g = [(b, l, k, s, st, "H1", n) for b in (150, 300, 500) for l in LISTS for k in KITS for s in ("S0", "S3") for st in (0, 5)]
        out = {}
        with Pool(4) as pool:
            for i, (a, r) in enumerate(pool.imap_unordered(job, g)):
                out[" | ".join(map(str, a[:5]))] = r
                if i % 40 == 0: print(i, len(g), round(time.time() - t0), a[:5], r["per_month"], flush=True)
        json.dump(out, open(os.path.join(os.path.dirname(__file__), "search_h1.json"), "w"), indent=0)
    else:
        S = json.load(open(os.path.join(os.path.dirname(__file__), "search_h1.json")))
        picks = {}
        for b in (150, 300, 500):
            rows = sorted(((v["net6"], k) for k, v in S.items() if k.startswith(f"{b} |")), reverse=True)
            seen, top = set(), []
            for _, k in rows:
                p = k.split(" | ")
                sig = (p[1], p[2])          # distinct list x kit
                if sig in seen: continue
                seen.add(sig); top.append(p)
                if len(top) == 3: break
            picks[b] = [("today", *TODAY[b])] + [("top%d" % (i + 1), p[1], p[2], p[3], int(p[4])) for i, p in enumerate(top)]
        g = [(b, l, k, s, st, span, n) for b in picks for (_, l, k, s, st) in picks[b] for span in ("H1", "H2", "REF")]
        out = {}
        with Pool(4) as pool:
            for a, r in pool.imap_unordered(job, g):
                out[" | ".join(map(str, a[:6]))] = r
                print(a[:6], r["per_month"], r["p10"], r["fees"], flush=True)
        json.dump({"picks": {str(k): v for k, v in picks.items()}, "rows": out}, open(os.path.join(os.path.dirname(__file__), "final.json"), "w"), indent=0)
