"""Multi-strategy books, step 3: the optimizer of research/books/DESIGN.md. PAPER ONLY.
    python -X utf8 tools/books/optimize.py lanes          # stage 1: every lane alone, 3 periods (report) + the H1 gate
    python -X utf8 tools/books/optimize.py screen         # stage 2: every 2-5 lane book on H1 (plain stream)
    python -X utf8 tools/books/optimize.py accounts       # stage 3: kept books on the 4 accounts, H1 only -> picks
    python -X utf8 tools/books/optimize.py final [n]      # stage 4: picks + today's setups, H1 / H2 / REF, real + model fills
"""
import collections, itertools, json, math, os, sys, time
from multiprocessing import Pool
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [HERE, ROOT, os.path.join(ROOT, "tools"), os.path.join(ROOT, "tools", "money")]
import sim
import combo_account as CA
OUT = os.path.join(ROOT, "research", "books")
ACCTS = ("b50", "b25", "r25", "r50")
ACCT_NAME = {"b50": "Builder 50K", "b25": "Builder 25K", "r25": "Rapid EOD 25K", "r50": "Rapid EOD 50K"}
SIZING = {"b50": "own", "b25": "own", "r25": "lanes", "r50": "lanes"}
TODAY = {"b50": "Z", "b25": "A", "r25": "Z+A", "r50": "Z+A"}
USD = 250.0
MEMBERS = {"E", "M", "S"}
K_TOP, K_FIVE = 40, 25


def jload(n):
    return json.load(open(os.path.join(OUT, n), encoding="utf-8"))


def jdump(o, n):
    json.dump(o, open(os.path.join(OUT, n), "w", encoding="utf-8"), indent=1, default=float)


def daily(combo, span, rule="first", usd=USD):
    """the period's real days in order: $ a day of the combo at a fixed $ a trade (CA.plain_stats's book-keeping)."""
    D = CA.combo_days(combo)
    a, z = CA.span_ix(span)
    out, pnl = [], []
    for si in range(a, z):
        d, opn = 0.0, []
        for t in D[si]:
            opn = [o for o in opn if o[0] > t["et"]]
            if opn and (rule != "adds" or any(o[1] != t["d"] for o in opn)):
                continue
            q = max(1, min(20, int(usd // ((t["risk"] + CA.SLIP) * CA.PV + CA.COMM))))
            p = t["pts"] * CA.PV * q - CA.COMM * q
            d += p
            pnl.append(p)
            opn.append((t["xt"], t["d"]))
        out.append(d)
    return np.array(out), np.array(pnl)


def stats(combo, span, rule="first", usd=USD):
    s = CA.plain_stats(combo, span, rule=rule, usd=usd)
    return {k: s[k] for k in ("trades", "tpw", "win", "pf", "net", "per_month", "max_dd", "win_days_pw")}


# ---------------------------------------------------------------- stage 1
def lanes():
    d = sim.use("real")
    out = {}
    for s in sim.LANES:
        out[s] = {"name": d["names"][s], **{sp: stats(s, sp) for sp in ("H1", "H2", "REF")}}
        print(s, out[s]["H1"]["per_month"], out[s]["H2"]["per_month"], out[s]["REF"]["per_month"], out[s]["H1"]["tpw"], flush=True)
    gate = [s for s in sim.LANES if out[s]["H1"]["net"] > 0]
    jdump({"lanes": out, "gate": gate, "grid_picks": d["grid_picks"], "grid_cells_tried": d["grid_cells_tried"]}, "lanes_stats.json")
    print("gate", gate)


# ---------------------------------------------------------------- stage 2
def books(gate):
    out = []
    for k in range(2, 6):
        for c in itertools.combinations(gate, k):
            if "A" in c and MEMBERS & set(c):
                continue
            out.append("+".join(c))
    return out


def _screen_one(combo):
    a, p = daily(combo, "H1")
    CA._D.get("C", {}).clear()                       # no cache across 100k books (memory)
    gl = -p[p < 0].sum()
    ns = len(a)
    return combo, float(a.sum()) / (ns / 21.0), len(p) / (ns / 5.0), (float(p[p > 0].sum() / gl) if gl else 99.0)


def _init():
    sim.use("real")


def screen():
    L = jload("lanes_stats.json")
    B = books(L["gate"])
    print(len(B), "books", flush=True)
    t0 = time.time()
    with Pool(4, initializer=_init) as pool:
        R = pool.map(_screen_one, B, chunksize=200)
    print(round(time.time() - t0), "s", flush=True)
    R.sort(key=lambda r: -r[1])
    top = [r[0] for r in R[:K_TOP]]
    five = [r[0] for r in R if r[2] >= 5.0][:K_FIVE]
    FIX = set("ZAEMSBPHTOW")
    fx = [r for r in R if set(r[0].split("+")) <= FIX]
    ftop = [r[0] for r in fx[:15]]
    ffive = [r[0] for r in fx if r[2] >= 5.0][:10]
    jdump({"n_books": len(B), "top": top, "five": five, "fixed_top": ftop, "fixed_five": ffive, "all": [[c, round(m), round(t, 2), round(f, 2)] for c, m, t, f in R]},
          "screen.json")
    for r in R[:10]:
        print(r)


# ---------------------------------------------------------------- stage 3
def _acct_job(args):
    acct, combo, rule, n, spans, fills = args
    sim.use(fills)
    r = CA.R(acct, combo, sizing=SIZING[acct] if "+" in combo else "own", rule=rule)
    r["live"] = "live"
    o = CA.score_row(r, n=n, spans=spans)
    return (acct, combo, rule, fills, {sp: {"slot": v["slot"], "funded": v["funded"], "net": v["_net"].round(1).tolist()}
                                       for sp, v in o.items()})


def accounts():
    S = jload("screen.json")
    cand = list(dict.fromkeys(S["top"] + S["five"] + S["fixed_top"] + S["fixed_five"]))
    FIX = set("ZAEMSBPHTOW")
    singles = sorted({x for c in cand for x in c.split("+")}, key=lambda s: CA.PRIO.get(s, 99))
    sim.use("real")
    jobs = []
    for acct in ACCTS:
        for c in list(dict.fromkeys(cand + singles + [TODAY[acct], "Z+A"])):
            for rule in (("first", "adds") if "+" in c else ("first",)):
                jobs.append((acct, c, rule, 300, ("H1",), "real"))
    print(len(jobs), "account rows", flush=True)
    t0 = time.time()
    with Pool(4) as pool:
        R = pool.map(_acct_job, jobs, chunksize=4)
    print(round(time.time() - t0), "s", flush=True)
    rows = []
    for acct, c, rule, _, o in R:
        s = o["H1"]["slot"]
        tpw = stats(c, "H1", rule=rule)["tpw"]
        rows.append({"acct": acct, "book": c, "rule": rule, "net_m": s["net_m"], "p_neg": s["p_neg"], "pass60": s["eval"]["p60"],
                     "pass_med": s["eval"]["pass_med"], "first_pay": s["first_pay_med"], "tpw": tpw})
    picks = {}
    for acct in ACCTS:
        A = [r for r in rows if r["acct"] == acct and "+" in r["book"]]
        best = max(A, key=lambda r: r["net_m"])
        five = max([r for r in A if r["tpw"] >= 5.0], key=lambda r: r["net_m"], default=None)
        Af = [r for r in A if set(r["book"].split("+")) <= FIX]
        fbest = max(Af, key=lambda r: r["net_m"])
        ffive = max([r for r in Af if r["tpw"] >= 5.0], key=lambda r: r["net_m"], default=None)
        picks[acct] = {"money": best, "five": five, "fixed_money": fbest, "fixed_five": ffive}
        print("   fixed", fbest, "\n   fixed five", ffive)
        print(acct, "money", best, "\n     five", five, flush=True)
    jdump({"n_rows": len(jobs), "rows": rows, "picks": picks}, "accounts_h1.json")


# ---------------------------------------------------------------- stage 4
def pvals():
    """Bonferroni + reality check on H1 real days: book daily $ - today's setup daily $ (same $ a trade)."""
    S, A, L = jload("screen.json"), jload("accounts_h1.json"), jload("lanes_stats.json")
    sim.use("real")
    N = sum(L["grid_cells_tried"].values()) + S["n_books"] + A["n_rows"]
    allb = [c for c, *_ in S["all"]]
    out = {"N": N, "alpha": 0.05 / N, "picks": {}}
    rng = np.random.default_rng(11)
    for acct in ACCTS:
        base, _ = daily(TODAY[acct], "H1")
        n = len(base)
        M = np.empty((len(allb), n))
        for i, c in enumerate(allb):
            M[i] = daily(c, "H1")[0] - base
            CA._D.get("C", {}).clear()
        mu, sd = M.mean(1), M.std(1, ddof=1)
        tt = mu / (sd / math.sqrt(n) + 1e-9)
        # 5-day block bootstrap of the centred matrix -> max-t null
        nb = int(math.ceil(n / 5))
        mx = []
        C = M - mu[:, None]
        for _ in range(500):
            st = rng.integers(0, n - 5, nb)
            ix = (st[:, None] + np.arange(5)[None, :]).ravel()[:n]
            X = C[:, ix]
            mx.append(float((X.mean(1) / (X.std(1, ddof=1) / math.sqrt(n) + 1e-9)).max()))
        mx = np.array(mx)
        for kind in ("money", "five", "fixed_money", "fixed_five"):
            p = A["picks"][acct][kind]
            if not p:
                continue
            d = daily(p["book"], "H1", rule=p["rule"])[0] - base
            t = d.mean() / (d.std(ddof=1) / math.sqrt(n) + 1e-9)
            from math import erf
            pv = 0.5 * (1 - erf(t / math.sqrt(2)))
            out["picks"][f"{acct}|{kind}"] = {"book": p["book"], "rule": p["rule"], "t": round(float(t), 2), "p": float(pv),
                                              "bonferroni_pass": bool(pv < 0.05 / N),
                                              "reality_check_p": round(float((mx >= t).mean()), 3),
                                              "gain_per_day": round(float(d.mean()), 1)}
        print(acct, out["picks"], flush=True)
    jdump(out, "pvals.json")


def final(n=2000):
    A = jload("accounts_h1.json")
    jobs, seen = [], set()
    for acct in ACCTS:
        want = [(TODAY[acct], "first"), ("Z", "first"), ("Z+A", "first")]
        for kind in ("money", "five", "fixed_money", "fixed_five"):
            p = A["picks"][acct][kind]
            if p:
                want.append((p["book"], p["rule"]))
        for c, rule in want:
            for fills in ("real", "model"):
                k = (acct, c, rule, fills)
                if k not in seen:
                    seen.add(k)
                    jobs.append((acct, c, rule, n, ("H1", "H2", "REF"), fills))
    print(len(jobs), "final rows", flush=True)
    with Pool(4) as pool:
        R = pool.map(_acct_job, jobs, chunksize=1)
    out = []
    for acct, c, rule, fills, o in R:
        sim.use(fills)
        row = {"acct": acct, "book": c, "rule": rule, "fills": fills}
        for sp, v in o.items():
            s, f = v["slot"], v["funded"]
            row[sp] = {"plain": stats(c, sp, rule=rule), "net_m": s["net_m"], "p10_m": s["p10_m"], "p_neg": s["p_neg"],
                       "pass60": s["eval"]["p60"], "fail60": s["eval"]["f60"], "pass_med": s["eval"]["pass_med"],
                       "pass10": s["eval"]["p10"], "first_pay_med": s["first_pay_med"], "funded_m": f["per_month"],
                       "funded_first_med": f["first_med"], "funded_lost": f["lost_or_stuck"], "max_risk": s["max_risk"]}
        out.append(row)
        print(acct, c, rule, fills, {sp: row[sp]["net_m"] for sp in o}, flush=True)
    jdump({"n_paths": n, "rows": out}, "final.json")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "lanes":
        lanes()
    elif cmd == "screen":
        screen()
    elif cmd == "accounts":
        accounts()
    elif cmd == "pvals":
        pvals()
    elif cmd == "final":
        final(int(sys.argv[2]) if len(sys.argv) > 2 else 2000)
