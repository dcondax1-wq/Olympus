"""All strategies on our 4 accounts: fastest FIRST payout from today's real balances (2026-11-27). PAPER RESEARCH ONLY.
Design (committed before any scored run): DESIGN.md (this folder). Engine = research/plans/rank.py + research/onebook/book.py.

    python -X utf8 research/portfolio/allstrats-2026-11-28/allstrats.py [--n 1000] [--only Z50]  -> results.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "research", "onebook"))
import book as BK  # noqa: E402  (real fills for ATLAS, BLITZ kept; patches the sizers we re-patch below)

R, RL, SOA, SZ, U, np = BK.R, BK.RL, BK.SOA, BK.SZ, BK.U, BK.R.np
OUT = os.path.join(HERE, "results.json")
U.SPAN["Y25"] = ("2025-01-01", "2025-12-31")
MKTS = ("H1", "H2", "REF", "Y25")
LEN, H_EVAL = 126, 60

# ------------------------------------------------------------------ calendar (CME sessions from Mon 2026-11-30)
CLOSED = {dt.date(2026, 12, 25), dt.date(2027, 1, 1), dt.date(2027, 1, 18)}


def calendar(n=LEN):
    d, out = dt.date(2026, 11, 30), []
    while len(out) < n:
        if d.weekday() < 5 and d not in CLOSED:
            out.append(d)
        d += dt.timedelta(days=1)
    return out


CAL = calendar()
DEC31 = sum(1 for d in CAL if d <= dt.date(2026, 12, 31))
JAN31 = sum(1 for d in CAL if d <= dt.date(2027, 1, 31))

# ------------------------------------------------------------------ per-strategy lane multipliers (eval / funded phase)
CFG = {}
PH = BK.PH
_q_add0 = BK._q_add


def q_add(t, z, room, cum, maxq, dll):
    m = CFG.get(("e" if PH["p"] == "e" else "f", t["strat"]), 1.0)
    if m <= 0:
        return 0
    s = z.get(t["strat"])
    if m != 1.0 and isinstance(s, dict):
        z = {**z, t["strat"]: {"usd": s["usd"] * m, "f": s["f"] * m}}
    return _q_add0(t, z, room, cum, maxq, dll)


RL.q_add = q_add


# ------------------------------------------------------------------ the shared risk manager: one position (first in keeps it)
def one_pos(ts):
    out, busy = [], -1
    for t in sorted(ts, key=lambda t: (t["entry_t"], RL.PRI[t["strat"]])):
        if t["entry_t"] < busy:
            continue
        out.append(t)
        busy = max(busy, t["exit_t"])
    return out


_MIX = {}


def mix(bots, news):
    k = (tuple(sorted(bots)), news)
    if k not in _MIX:
        _MIX[k] = [one_pos(ts) for ts in RL.mix_by(bots, news=news)]
    return _MIX[k]


# ------------------------------------------------------------------ accounts and mixes (DESIGN.md)
ACCTS = {
    "Z50": {"plan": "mffu_builder_50k", "label": "Zlarior Builder 50K eval", "stage": "eval",
            "st": {"bal": -518.0, "floor": -1831.0, "peak": 169.0, "s": 29, "dtr": 20, "best": 0.0}},
    "N25": {"plan": "mffu_builder_25k", "label": "Zlarior 25K #2 eval", "stage": "eval",
            "st": {"bal": 19.0, "floor": -977.0, "peak": 23.0, "s": 7, "dtr": 1, "best": 19.0}},
    "R25": {"plan": "mffu_rapid_eod_25k", "label": "Rapid EOD 25K eval", "stage": "eval",
            "st": {"bal": 299.0, "floor": -701.0, "peak": 299.0, "s": 2, "dtr": 1, "best": 304.0}},
    "A25": {"plan": "mffu_builder_25k", "label": "ATLAS Builder 25K funded", "stage": "funded",
            "st": {"bal": 401.0, "floor": -599.0, "peak": 401.0, "cyc": [401.0], "cyc_start": 0.0}},
}
L, A, B = "LIT", "ATLAS", "BLITZ"
# id -> (eval bots, funded bots, lane mults {(phase, strat): m}, BLITZ lane $ on a 25K)
MIXES = {
    "M01 LIT": ((L,), (L,), {}, None),
    "M02 ATLAS": ((A,), (A,), {}, None),
    "M03 LIT+ATLAS": ((L, A), (L, A), {}, None),
    "M04 LIT+ATLAS x0.5 eval": ((L, A), (L, A), {("e", A): 0.5}, None),
    "M05 LIT+ATLAS+BLITZ150": ((L, A, B), (L, A, B), {}, 150),
    "M06 LIT+ATLAS+BLITZ300": ((L, A, B), (L, A, B), {}, 300),
    "M07 LIT+BLITZ150": ((L, B), (L, B), {}, 150),
    "M08 ATLAS+BLITZ150": ((A, B), (A, B), {}, 150),
    "M09 LIT+ATLAS x0.5+BLITZ150": ((L, A, B), (L, A, B), {("e", A): 0.5}, 150),
    "M10 LIT eval, all 3 funded": ((L,), (L, A, B), {}, 150),
}
TODAY = {"Z50": "M04 LIT+ATLAS x0.5 eval", "N25": "M01 LIT", "R25": "M03 LIT+ATLAS", "A25": "M02 ATLAS"}


def spec(acct, mx):
    me, mf, mult, blitz = MIXES[mx]
    ac = ACCTS[acct]
    plan = ac["plan"]
    sp = R.spec(plan)
    big = "50k" in plan
    news = plan.startswith("mffu_rapid")
    z = dict(sp["z"])
    if blitz:
        z["BLITZ"] = {"usd": float(blitz) * (2 if big else 1), "f": 0.3}
    E = sp["E"]
    has_cons = E.get("cons", 1.0) < 1.0
    ec = sp["ev"]().cfg
    F, fcfg, ask = sp["F"], (U.UP50 if big else U.UP25), ("cap" if sp["F"]["cap1"] < 1e8 else sp["F"]["pay_min"])
    sp.update(z=z, mult=mult, news=news, big=big,
              ev=lambda: RL.Ev(ec, E, z, "guard" if has_cons else "none"),
              fund=lambda: R.Funded(fcfg, F, z, ask),
              BYe=mix(me, False), BYf=mix(mf, news), BYx=mix(mf, False))
    usd = {s: 0.0 for s in RL.PRI}
    usd["LIT"] = 500.0 if big else 250.0
    usd["ATLAS"] = z["ATLAS"]["usd"]
    usd["BLITZ"] = z.get("BLITZ", {"usd": 150.0})["usd"]
    sp["usd"] = usd
    return sp


def start_eval(sp, st):
    e = sp["ev"]()
    e.bal, e.floor, e.peak, e.s, e.dtr, e.best = st["bal"], st["floor"], st["peak"], st["s"], st["dtr"], st["best"]
    return e


def start_funded(sp, st):
    f = sp["fund"]()
    f.bal, f.floor, f.peak, f.cyc, f.cyc_start = st["bal"], st["floor"], st["peak"], list(st["cyc"]), st["cyc_start"]
    return f


def path_run(sp, acct, seq):
    """One 6-month path from today's state. -> dict of the slot's facts."""
    ac = ACCTS[acct]
    cost, owner, lost, pays, first_pay, cur_out, cur_k = 0.0, 0.0, 0, 0, None, "open", None
    eq, peak_eq, dd = 0.0, 0.0, 0.0
    if ac["stage"] == "eval":
        e, f, wait = start_eval(sp, ac["st"]), None, 0
    else:
        e, f, wait = None, start_funded(sp, ac["st"]), 0
    first_acct = True
    for k, si in enumerate(seq[:LEN]):
        if e is not None:
            r, _ = e.step(sp["BYe"][si])
            if r == "pass":
                if first_acct and cur_out == "open":
                    cur_out, cur_k = "pass", k + 1
                e, wait = None, R.GAP
            elif r in ("fail", "stuck"):
                if first_acct and cur_out == "open":
                    cur_out, cur_k = "fail", k + 1
                first_acct = False
                e = sp["ev"](); cost += sp["price"]; eq -= sp["price"]
            continue
        if f is None:
            wait -= 1
            if wait <= 0:
                f = sp["fund"]()
            continue
        ev, x, _ = f.step(sp["BYf"][si])
        if ev in ("paid", "grad"):
            owner += x; pays += 1; eq += x
            first_pay = first_pay or k + 1
        if ev in ("lost", "grad"):
            if ev == "lost":
                lost += 1
                if first_acct and ac["stage"] == "funded" and cur_out == "open" and not pays:
                    cur_out, cur_k = "fail", k + 1
            first_acct = False
            f = None
            e = sp["ev"](); cost += sp["price"]; eq -= sp["price"]
        peak_eq = max(peak_eq, eq)
        dd = min(dd, eq - peak_eq)
    return {"owner": owner, "cost": cost, "lost": lost, "pays": pays, "fp": first_pay, "cur": cur_out, "cur_k": cur_k}


def summarize(rows, stage):
    n = len(rows)
    fp = np.array([r["fp"] if r["fp"] else LEN + 1 for r in rows], dtype=float)
    net = np.array([r["owner"] - r["cost"] for r in rows])
    med = float(np.median(fp))
    fail = 100.0 * sum(1 for r in rows if r["cur"] == "fail" and (stage == "funded" or r["cur_k"] <= H_EVAL)) / n
    pk = [r["cur_k"] for r in rows if r["cur"] == "pass"]
    return {"first_pay_med_sessions": None if med > LEN else med,
            "first_pay_med_date": None if med > LEN else CAL[int(math.ceil(med)) - 1].isoformat(),
            "paid_by_dec31": round(100.0 * float((fp <= DEC31).mean()), 1),
            "paid_by_jan31": round(100.0 * float((fp <= JAN31).mean()), 1),
            "paid_6m": round(100.0 * float((fp <= LEN).mean()), 1),
            "fail": round(fail, 1), "pass_med_sessions": float(np.median(pk)) if pk else None,
            "per_month": round(float(net.mean()) / 6.0), "net_p10_6m": round(float(np.percentile(net, 10))),
            "owner_6m": round(float(np.mean([r["owner"] for r in rows]))),
            "fees_6m": round(float(np.mean([r["cost"] for r in rows])), 1),
            "p_lost_funded": round(100.0 * sum(1 for r in rows if r["lost"]) / n, 1)}


def run(acct, mx, P, S):
    sp = spec(acct, mx)
    CFG.clear()
    CFG.update(sp["mult"])
    out = {}
    for m in MKTS:
        rows = [path_run(sp, acct, seq) for seq in P[m]]
        out[m] = summarize(rows, ACCTS[acct]["stage"])
        out[m]["fixed"] = SOA.plain_stats(sp["BYx"], S, m, sp["usd"])
    CFG.clear()
    return out


def pick(acct, rows):
    T = rows[TODAY[acct]]
    elig = [k for k, r in rows.items() if r["H1"]["fail"] <= T["H1"]["fail"] + 3.0]
    best = sorted(elig, key=lambda k: (-rows[k]["H1"]["paid_by_jan31"], rows[k]["H1"]["first_pay_med_sessions"] or 999,
                                        -rows[k]["H1"]["per_month"]))[0]
    r = rows[best]
    chk = {"h1_h2_paid_jan31_higher": all(r[m]["paid_by_jan31"] > T[m]["paid_by_jan31"] for m in ("H1", "H2")),
           "h1_h2_usd_not_lower": all(r[m]["per_month"] >= T[m]["per_month"] for m in ("H1", "H2")),
           "h2_fail_ok": r["H2"]["fail"] <= T["H2"]["fail"] + 3.0,
           "ref_ok": r["REF"]["per_month"] >= T["REF"]["per_month"] - 50 and r["REF"]["fail"] <= T["REF"]["fail"] + 5.0,
           "margin_ge_2pts": all(r[m]["paid_by_jan31"] - T[m]["paid_by_jan31"] >= 2.0 for m in ("H1", "H2"))}
    chk["card"] = best != TODAY[acct] and all(chk.values())
    return {"today": TODAY[acct], "pick": best, "eligible": elig, **chk}


def line(acct, mx, r):
    return f"{acct} {mx:30s} " + " | ".join(
        f"{m} 1st {r[m]['first_pay_med_sessions']} D{r[m]['paid_by_dec31']}/J{r[m]['paid_by_jan31']}% fail {r[m]['fail']} "
        f"${r[m]['per_month']}/mo" for m in MKTS)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--only", default="")
    a = ap.parse_args(argv)
    t0 = time.time()
    S = SOA.data()["S"]
    P = {m: U.mc_paths(S, m, a.n, length=LEN, seed=23) for m in MKTS}
    res = {"n": a.n, "dec31_session": DEC31, "jan31_session": JAN31, "accounts": {}}
    for acct in ACCTS:
        if a.only and a.only != acct:
            continue
        rows = {}
        mixes = [k for k in MIXES if not (ACCTS[acct]["stage"] == "funded" and k.startswith("M10"))]
        for mx in mixes:
            rows[mx] = run(acct, mx, P, S)
            print(line(acct, mx, rows[mx]), f"[{time.time() - t0:.0f}s]", flush=True)
        res["accounts"][acct] = {"label": ACCTS[acct]["label"], "start": ACCTS[acct]["st"], "rows": rows,
                                 "pick": pick(acct, rows)}
        print("PICK", acct, res["accounts"][acct]["pick"], flush=True)
    res["poseidon"] = ("NOT in the Monte Carlo: lane A has 51 real tick days (2026-09..11), no 2026 H1 / 2021-25 ticks; "
                       "40 trades +0.49R (p 0.0065, halves differ) = forward paper only (gate 0: 30 forward trades).")
    res["rows_counted"] = sum(len(v["rows"]) for v in res["accounts"].values())
    with open(OUT if not a.only else OUT.replace(".json", f"_{a.only}.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)


if __name__ == "__main__":
    main()
