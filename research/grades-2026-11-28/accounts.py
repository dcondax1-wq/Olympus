"""DESIGN.md test 3: grade maps on the Builder 50K combo (LIT + ATLAS, live row a50_eval). PAPER ONLY. -> results_accounts.json"""
import json, math, os, pickle, sys, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, os.path.join(ROOT, "tools"), os.path.join(ROOT, "tools", "money")):
    sys.path.insert(0, p)
import logging; logging.getLogger("engine.sizing").setLevel(logging.ERROR)
import combo_account as C
MULT = pickle.load(open(os.path.join(os.environ.get("SCR", "/tmp"), "grades_mult.pkl"), "rb"))
CUR = {"m": None}
_size = C.Book.size


def size(self, t, room, cum, st):
    q = _size(self, t, room, cum, st)
    if CUR["m"] is None or q <= 0:
        return q
    m = CUR["m"].get((t["s"], t["et"]), 1.0)
    return 0 if m <= 0 else min(self.maxq, max(1, int(math.floor(q * m + 1e-9))))


C.Book.size = size


def job(a):
    key, mk, n = a
    C._patch_account_b()
    CUR["m"] = None if key == "live" else MULT[key]
    r = C.frow("a50_eval")
    De = C.combo_days(r["eval"]); cell = C.cell_of(r)
    res = []
    for seq in C.day_paths(mk, n, length=C.H_EVAL, seed=C.SEED_SLOT):
        e = C.Eval(cell, r["eval"]); o, u = "open", C.H_EVAL
        for k, si in enumerate(seq):
            x, _ = e.step(De[si])
            if x:
                o, u = ("pass" if x == "pass" else "fail"), k + 1; break
        res.append((o, u))
    ps = [u for o, u in res if o == "pass"]
    sl = C.run_slot(r, C.day_paths(mk, n, seed=C.SEED_FUND))
    net = np.array([q[0] for q in sl]); fp = [q[7] for q in sl if q[7]]
    return key, mk, {"pass": round(100 * len(ps) / n, 1), "fail": round(100 * sum(1 for o, _ in res if o == "fail") / n, 1),
                     "med_pass": float(np.median(ps)) if ps else None, "per_month": round(float(net.mean()) / C.MONTHS),
                     "first_pay_med": float(np.median(fp)) if fp else None}


def main():
    C.trades(); C.atlas_paths(); C._patch_account_b()
    keys = ["live"] + sorted(MULT)
    jobs = [(k, m, 1000) for k in keys for m in ("H1", "H2", "REF")]
    import multiprocessing as mp
    out = {}
    with mp.get_context("fork").Pool(4) as pool:
        for k, m, o in pool.imap_unordered(job, jobs):
            out.setdefault(k, {})[m] = o
            print(k, m, o, flush=True)
    L = out["live"]
    for k in keys[1:]:
        out[k]["pass_rule"] = bool(out[k]["H1"]["per_month"] > L["H1"]["per_month"] and out[k]["H2"]["per_month"] > L["H2"]["per_month"]
                                   and out[k]["H1"]["fail"] <= L["H1"]["fail"] + 3 and out[k]["H2"]["fail"] <= L["H2"]["fail"] + 3)
    json.dump(out, open(os.path.join(HERE, "results_accounts.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
