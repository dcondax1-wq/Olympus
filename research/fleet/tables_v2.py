"""Fleet v2 tables for the write-up (reads results_v2_main.json / results_v2_sens.json / noise_v2.json)."""
import json, os
H = os.path.dirname(os.path.abspath(__file__))
M = json.load(open(f"{H}/results_v2_main.json"))["rows"]
S = json.load(open(f"{H}/results_v2_sens.json"))["rows"] if os.path.exists(f"{H}/results_v2_sens.json") else {}
K = lambda b, n, o, p=126: f"${b}/mo | N={n} | {'LU' if n == 0 else o}-first | LU ${p:g}"
def g(b, n, o, p=126):
    return (M if p == 126 else S).get(K(b, n, o, p))
def mo(v): return "-" if v is None else f"{v:g}"
def d(x): return f"${x:,.0f}" if x >= 0 else f"-${-x:,.0f}"
print("## headline (price $126)")
print("| Budget | Lucid N | order | $/month (6-mo net/6) H1 / H2 | 12-mo $/month H1 / H2 | months to $70k H1 / H2 | P($70k <= 12 mo) H1 / H2 | worst 10% (6 mo) H1 / H2 | 2021-25-like 6-mo net | extra loss vs N=0 | fees 6 mo REF | loss/fees | P(3+ fund. fails in 2 wk, 6 mo) H2 / REF | P(3+ Lucid fail in 2 wk) H2 |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for b in (300, 500, 800):
    base = g(b, 0, "LU")
    for n in (0, 1, 2, 3, 5):
        for o in (("LU",) if n == 0 else ("LU", "BASE")):
            v = g(b, n, o)
            h1, h2, rf = v["H1"], v["H2"], v["REF"]
            ex = rf["net6"] - base["REF"]["net6"]
            print(f"| ${b} | {n} | {'-' if n == 0 else o + '-first'} | {d(h1['net6']/6)} / {d(h2['net6']/6)} | {d(h1['per_month12'])} / {d(h2['per_month12'])} | {mo(h1['corvette_med_months'])} / {mo(h2['corvette_med_months'])} | {h1['corvette_12m']:.0f}% / {h2['corvette_12m']:.0f}% | {d(h1['p10_6'])} / {d(h2['p10_6'])} | {d(rf['net6'])} | {d(ex)} | {d(rf['fees6'])} | {abs(rf['net6'])/rf['fees6']:.2f}x | {h2['p3_fund_6m']:.0f}% / {rf['p3_fund_6m']:.0f}% | {h2['p3_lucid_6m']:.0f}% |")
print("\n## marginal $ per extra Lucid account (6-mo net, step / accounts added), best order = higher H2")
for b in (300, 500, 800):
    for o in ("LU", "BASE"):
        prev, pn = g(b, 0, "LU"), 0
        line = []
        for n in (1, 2, 3, 5):
            v = g(b, n, o)
            line.append(f"N{pn}->{n}: " + " / ".join(f"{d((v[s]['net6']-prev[s]['net6'])/(n-pn))}" for s in ("H1", "H2", "REF")))
            prev, pn = v, n
        print(f"${b} {o}-first (H1 / H2 / REF per added account): " + " | ".join(line))
print("\n## price sensitivity: H1 / H2 / REF 6-mo net")
for b in (300, 500, 800):
    for n in (1, 2, 3, 5):
        for o in ("LU", "BASE"):
            r = [g(b, n, o, p) for p in (76, 126, 176)]
            print(f"${b} N={n} {o}: " + " | ".join(f"${p}: " + "/".join(d(x[s]['net6']) for s in ('H1', 'H2', 'REF')) for p, x in zip((76, 126, 176), r) if x))
