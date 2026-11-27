"""Lane A size test (pre-registered: research/orderflow/DESIGN_lanea_size.md). PAPER RESEARCH ONLY: changes no bot.

    python -X utf8 research/orderflow/lanea_proof/size.py [--paths 1000] [--cache PKL]  -> lanea_proof/size_results.json
"""
from __future__ import annotations

import argparse
import collections
import contextlib
import io
import json
import logging
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import proof as PR  # noqa: E402

OUT = os.path.join(HERE, "size_results.json")
SIZES = ("Q1", "Q2", "Q3", "C50", "C100", "C150", "REF")
GATES = ("none", "UP", "FLOOR", "UP+FLOOR")
EDGES = {"a measured": 0.0, "b half": 0.5, "c zero": 1.0}
PLANS = {"mffu_builder_50k": "Builder 50K", "mffu_builder_25k": "Builder 25K", "mffu_rapid_eod_25k": "Rapid EOD 25K"}
CUR = {"acct": None, "size": "REF", "gate": "none", "big": True}


def install():
    logging.getLogger("engine.sizing").setLevel(logging.ERROR)
    import rank as RK
    import rapid_levers as RL
    import stack_one_account as SOA
    RL.PRI.setdefault("LANEA", 6)
    with contextlib.redirect_stdout(io.StringIO()):
        RK.A4.apply_costs()
    orig_q = SOA.stack_q

    def stack_q(t, z, room, cum, maxq, dll=SOA.SOFT_DLL):
        if t["strat"] != "LANEA":
            return orig_q(t, z, room, cum, maxq, dll)
        if CUR["size"] == "REF":
            q = orig_q(t, z, room, cum, maxq, dll)
        else:
            a = CUR["acct"]
            X = Y = 1000.0 if CUR["big"] else 500.0
            if a is not None and "UP" in CUR["gate"] and a.bal < X:
                return 0
            if a is not None and "FLOOR" in CUR["gate"] and a.bal - a.floor < Y:
                return 0
            loss1 = (t["risk"] + SOA.SLIP) * SOA.PV + SOA.COMM
            s = CUR["size"]
            q = int(s[1:]) if s[0] == "Q" else int(float(s[1:]) // loss1)
            q = min(q, int(maxq), int(max(0.0, dll + min(0.0, cum)) // loss1))
            return max(0, q)
        if q <= 0:
            return 0
        a = CUR["acct"]
        X = Y = 1000.0 if CUR["big"] else 500.0
        if a is not None and "UP" in CUR["gate"] and a.bal < X:
            return 0
        if a is not None and "FLOOR" in CUR["gate"] and a.bal - a.floor < Y:
            return 0
        return q

    SOA.stack_q = stack_q
    for cls in (RL.Ev, RK.Funded):
        f = cls.step

        def wrap(self, ts, keep=None, _f=f):
            CUR["acct"] = self
            return _f(self, ts, keep)
        cls.step = wrap
    return RK, RL, SOA


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--paths", type=int, default=1000)
    ap.add_argument("--cache", default=None)
    a = ap.parse_args(argv)
    R, B = PR.load_days()
    days, rows, D = PR.signals(R, B)
    taken = [r for r in rows if r.get("lane") == "A" and r["taken"]]
    T1 = [(r, PR.sim(r, D[r["day"]], "F1")) for r in taken]
    T1 = [(r, s) for r, s in T1 if s]
    m = float(np.mean([s["R"] for _, s in T1]))
    lit, atl, _ = PR.lit_atlas(a.cache)
    other = [t for t in lit + atl if PR.FIRST <= t["day"] <= PR.LAST]
    RK, RL, SOA = install()
    rng = np.random.default_rng(5)
    nd = len(days)

    def paths(length):
        out = []
        for _ in range(a.paths):
            seq = []
            while len(seq) < length:
                s0 = int(rng.integers(0, nd))
                seq += [(s0 + j) % nd for j in range(5)]
            out.append(seq[:length])
        return out

    PE, PF = paths(RK.H_EVAL), paths(RK.LEN)
    share = {}
    for c in (50, 100, 150):
        share[f"C{c}"] = round(float(np.mean([c // ((s["risk"] + 0.25) * 2 + 1.9) >= 1 for _, s in T1])), 2)
    out = {"design": "research/orderflow/DESIGN_lanea_size.md", "paths": a.paths, "measured_mean_R": round(m, 3),
           "lane_a_trades": len(T1), "stop_usd_per_micro_median": round(float(np.median([(s["risk"] + 0.25) * 2 + 1.9 for _, s in T1])), 1),
           "cap_share_with_1_micro": share, "rows": {}}
    for ename, k in EDGES.items():
        by_day = collections.defaultdict(list)
        for r, s in T1:
            pts = s["pts"] - k * m * s["risk"]
            by_day[r["day"]].append({"day": r["day"], "entry_t": s["fill_t"], "exit_t": s["exit_t"], "dir": r["d"], "strat": "LANEA",
                                     "risk": s["risk"], "pts": pts, "w1": min(s["w1"], pts), "tgt": PR.RR * s["risk"], "tf": 5})
        for t in other:
            by_day[t["day"]].append(t)
        for plan, label in PLANS.items():
            big = "50k" in plan
            CUR["big"] = big
            variants = [("base", None, None)] + [(f"{s} / {g}", s, g) for s in SIZES for g in GATES]
            for vname, s, g in variants:
                mix = ("LIT", "ATLAS") if s is None else ("LIT", "ATLAS", "LANEA")
                CUR["size"], CUR["gate"] = (s or "REF"), (g or "none")
                sp = RK.spec(plan)
                z = RL.Z(ATLAS=500 if big else 250, LANEA=500 if big else 250)
                E = sp["E"]
                soft = 1000.0 if big else 500.0
                ec = RK.A4.ecfg({**E, "dll": min(E["dll"], soft)})
                ec["two_week"]["acct"]["dll"] = min(E["dll"], soft)
                ec["_dll"] = min(E["dll"], soft)
                hc = E.get("cons", 1.0) < 1.0
                sp["ev"] = lambda ec=ec, E=E, z=z, hc=hc: RL.Ev(ec, E, z, "guard" if hc else "none")
                fcfg = RK.U.UP50 if big else RK.U.UP25
                ask = "cap" if sp["F"]["cap1"] < 1e8 else sp["F"]["pay_min"]
                sp["fund"] = lambda fcfg=fcfg, F=sp["F"], z=z, ask=ask: RK.Funded(fcfg, F, z, ask)
                BY = []
                for d in days:
                    ts = sorted([t for t in by_day.get(d, []) if t["strat"] in mix], key=lambda t: (t["entry_t"], RL.PRI[t["strat"]]))
                    BY.append(SOA.news_rule(ts) if plan.startswith("mffu_rapid") and ts else ts)
                sp["BYe"] = sp["BYf"] = BY
                ev = PR.eval_dd(sp, PE)
                sl = RK.slot_run(sp, PF)
                out["rows"].setdefault(label, {}).setdefault(vname, {})[ename] = {
                    "pass": ev["pass"], "fail": ev["fail"], "days": ev["med_days"], "net6": sl["net_6m"],
                    "per_month": round(sl["net_6m"] / (RK.LEN / 21.0), 1), "blown": sl["p_lost"], "p10": sl["net_p10"], "fee": sp["price"]}
            print(ename, label, "done", flush=True)
    # the pick rule
    safe, scored = [], {}
    for v in [f"{s} / {g}" for s in SIZES for g in GATES]:
        ok, add_a, pos_a, b_ok = True, 0.0, 0, True
        for label in PLANS.values():
            base, x = out["rows"][label]["base"], out["rows"][label][v]
            c, b0 = x["c zero"], base["c zero"]
            ok &= c["pass"] >= b0["pass"] - 1 and c["fail"] <= b0["fail"] + 2 and c["blown"] <= b0["blown"] + 3 and c["net6"] >= b0["net6"] - x["c zero"]["fee"]
            d_a = x["a measured"]["net6"] - base["a measured"]["net6"]
            add_a += d_a
            pos_a += d_a > 0
            b_ok &= x["b half"]["net6"] >= base["b half"]["net6"]
        scored[v] = {"safe_zero_edge": bool(ok), "sum_add_a": round(add_a), "plans_up_a": pos_a, "half_no_loss": bool(b_ok)}
        if ok and pos_a >= 2 and b_ok:
            safe.append((add_a, v))
    out["scored"] = scored
    out["pick"] = max(safe)[1] if safe else None
    out["pick_line"] = (f"pick {out['pick']}" if safe else "no size is free: lane A stays paper")
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=float)
    print(out["pick_line"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
