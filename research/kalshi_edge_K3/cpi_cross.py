#!/usr/bin/env python3
"""K3 angle 1, cross-market: CPI month-on-month (KXCPI, seasonally adjusted) against CPI year-on-year (KXCPIYOY, not adjusted)
for the same month. Once last year's index and the seasonal factors are known, the y/y print is (almost) a function of the m/m
print, so the two ladders must agree. If a y/y strike is bid above the ask of an m/m strike that it implies (or the reverse),
buying the pair pays $1 in every state: a true arbitrage, up to the seasonal-factor error.

Mapping: yoy = I_nsa(t-1) * (1 + mm) * r / I_nsa(t-12) - 1, with r = sf(t)/sf(t-1) taken from last year's factors
(sf = NSA/SA, FRED CPIAUCNS/CPIAUCSL). The error eps of that mapping is measured on 2015-2026 with the unrounded m/m from the
Cleveland Fed file; the arbitrage is only counted when it holds for any eps within [-E, E], E = max |eps| seen + 0.02.

    python research/kalshi_edge_K3/cpi_cross.py
Writes data/cpi_cross.json.
"""
import gzip, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kk

MON = "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split()


def fpc(p):
    return kk.fee_c(p, 100) / 100


def load(ser):
    rows = [json.loads(l) for l in gzip.open(os.path.join(kk.DATA, f"econ_{ser}.jsonl.gz"), "rt")]
    by = {}
    for r in rows:
        if r["st"] != "greater" or r["fs"] is None:
            continue
        tag = r["e"].split("-")[1]
        by.setdefault(tag, []).append(r)
    return by


def ym(tag):
    return 2000 + int(tag[:2]), MON.index(tag[2:5]) + 1


def key(y, m):
    return f"{y:04d}-{m:02d}-01"


def shift(y, m, k):
    i = y * 12 + (m - 1) + k
    return i // 12, i % 12 + 1


def main():
    idx = json.load(open(os.path.join(kk.DATA, "cpi_index.json")))
    sa = dict(map(tuple, idx["CPIAUCSL"])); ns = dict(map(tuple, idx["CPIAUCNS"]))
    nc = json.load(open(os.path.join(kk.DATA, "nowcast_cpi.json")))

    def g(y, m, mm):
        """yoy in % implied by an m/m (in %) for month (y, m)"""
        p1, p12, p13 = shift(y, m, -1), shift(y, m, -12), shift(y, m, -13)
        try:
            r = (ns[key(*p12)] / sa[key(*p12)]) / (ns[key(*p13)] / sa[key(*p13)])
            return 100 * (ns[key(*p1)] * (1 + mm / 100) * r / ns[key(*p12)] - 1)
        except KeyError:
            return None
    # mapping error on history (exact yoy from NSA index, unrounded m/m from the Cleveland file)
    eps = []
    for mo, d in nc.items():
        y, m = int(mo[:4]), int(mo[5:])
        if y < 2016 or d["actual"][0] is None or key(y, m) not in ns or key(*shift(y, m, -12)) not in ns:
            continue
        yy = 100 * (ns[key(y, m)] / ns[key(*shift(y, m, -12))] - 1)
        p = g(y, m, d["actual"][0])
        if p is not None:
            eps.append((mo, round(yy - p, 4)))
    E = max(abs(e) for _, e in eps) + 0.02
    mm, yo = load("KXCPI"), load("KXCPIYOY")
    hits, checks, months = [], 0, 0
    for tag in sorted(set(mm) & set(yo)):
        y, m = ym(tag)
        if g(y, m, 0.0) is None:
            continue
        months += 1
        A, Y = mm[tag], yo[tag]
        for a in A:
            for b in Y:
                X, Yk = a["fs"], b["fs"]
                # case 1: yoy > Yk implies mm > X  when the smallest mm giving yoy >= Yk+0.05-E is >= X+0.05
                # g is increasing in mm: find mm* with g(mm*) = Yk + 0.05 - E by bisection
                def inv(target):
                    lo, hi = -3.0, 3.0
                    for _ in range(60):
                        mid = (lo + hi) / 2
                        if g(y, m, mid) < target:
                            lo = mid
                        else:
                            hi = mid
                    return hi
                c1 = inv(Yk + 0.05 - E) >= X + 0.05          # P(yoy>Yk) <= P(mm>X)
                c2 = g(y, m, X + 0.05) - E >= Yk + 0.05       # P(mm>X)  <= P(yoy>Yk)
                if not (c1 or c2):
                    continue
                for off in set(a["q"]) & set(b["q"]):
                    qa, qb = a["q"][off], b["q"][off]
                    checks += 1
                    if c1:   # buy YES mm>X at its ask, buy NO yoy>Yk at 100 - its bid
                        pa, pb = qa[1], 100 - qb[0]
                    else:    # buy YES yoy>Yk at its ask, buy NO mm>X
                        pa, pb = qb[1], 100 - qa[0]
                    if not (0 < pa < 100 and 0 < pb < 100):
                        continue
                    gross = 100 - pa - pb
                    net = gross - fpc(pa) - fpc(pb)
                    if gross > 0:
                        # realised payoff of the pair (should be >= 100 if the logic is right)
                        ya, yb = a["res"] == "yes", b["res"] == "yes"
                        pay = (100 if ya else 0) + (0 if yb else 100) if c1 else (100 if yb else 0) + (0 if ya else 100)
                        hits.append({"tag": tag, "mm": X, "yoy": Yk, "case": 1 if c1 else 2, "off_h": off, "gross_c": gross, "net_c": round(net, 2),
                                     "payoff_c": pay, "vol": [qa[2], qb[2]]})
    out = {"E_mapping_error_pts": round(E, 3), "eps_n": len(eps), "eps_worst": sorted(eps, key=lambda x: -abs(x[1]))[:5],
           "months": months, "pair_checks": checks, "hits_gross_pos": len(hits), "hits_net_pos": sum(1 for h in hits if h["net_c"] > 0),
           "payoff_failures": sum(1 for h in hits if h["payoff_c"] < 100), "hits": sorted(hits, key=lambda h: -h["net_c"])[:40]}
    json.dump(out, open(os.path.join(kk.DATA, "cpi_cross.json"), "w"), indent=1)
    print({k: v for k, v in out.items() if k != "hits"})
    for h in out["hits"][:15]:
        print(h)


if __name__ == "__main__":
    main()
