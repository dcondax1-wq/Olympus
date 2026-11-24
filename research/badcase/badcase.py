"""The BAD-case business plan (research/badcase/DESIGN.md). PAPER RESEARCH ONLY.
    python -X utf8 research/badcase/badcase.py [--n 500]  -> research/badcase/results.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "research", "plans"))
sys.path.insert(0, os.path.join(ROOT, "research", "pillars"))
sys.path.insert(0, ROOT)
import rank as R  # noqa: E402

U, RL, AR, SOA = R.U, R.RL, R.AR, R.SOA
OUT = os.path.join(HERE, "results.json")
OUT4 = os.path.join(HERE, "blitz_rapid_4mkts.json")
U.SPAN["Y25"] = ("2025-01-01", "2025-12-31")
MKTS = ("Y25", "REF", "H1", "H2")
WORD = {"Y25": "2025-like", "REF": "2021-25 mix", "H1": "2026 Jan-Jun-like", "H2": "2026 Jul-Oct-like"}
PLANS = ("mffu_builder_50k", "mffu_builder_25k", "mffu_rapid_eod_25k")


def slot_full(sp, paths):
    """rank.slot_run + passes, the 90th-percentile monthly eval spend, owner $ per pass."""
    rows = []
    for seq in paths:
        cost, owner, evals, lost, pays, passes = sp["price"], 0.0, 1, 0, 0, 0
        e, f, wait = sp["ev"](), None, 0
        for k, si in enumerate(seq[:R.LEN]):
            if e is not None:
                r, _ = e.step(sp["BYe"][si])
                if r == "pass":
                    passes += 1
                    e, wait = None, R.GAP
                elif r in ("fail", "stuck"):
                    e = sp["ev"](); cost += sp["price"]; evals += 1
                continue
            if f is None:
                wait -= 1
                if wait <= 0:
                    f = sp["fund"]()
                continue
            ev, x, _ = f.step(sp["BYf"][si])
            if ev in ("paid", "grad"):
                owner += x; pays += 1
            if ev in ("lost", "grad"):
                lost += ev == "lost"
                f = None
                e = sp["ev"](); cost += sp["price"]; evals += 1
        rows.append((owner, cost, evals, lost, pays, passes))
    A = np.array(rows, float)
    net = A[:, 0] - A[:, 1]
    tot_pass = A[:, 5].sum()
    return {"owner_6m": round(float(A[:, 0].mean())), "fees_6m": round(float(A[:, 1].mean()), 1), "net_6m": round(float(net.mean())),
            "net_p10": round(float(np.percentile(net, 10))), "evals_bought": round(float(A[:, 2].mean()), 2),
            "net_per_eval": round(float(net.mean() / A[:, 2].mean()), 1), "payouts_per_month": round(float(A[:, 4].mean() / 6), 2),
            "spend_per_month_p90": round(float(np.percentile(A[:, 1], 90) / 6), 1), "spend_per_month_mean": round(float(A[:, 1].mean() / 6), 1),
            "funded_lost": round(float(A[:, 3].mean()), 2), "no_pay_pct": round(100.0 * float((A[:, 4] == 0).mean()), 1),
            "owner_per_pass": round(float(A[:, 0].sum() / tot_pass)) if tot_pass else 0}


def part1(n, say):
    AR.rapid_patch(AR.T_at(10))
    S = SOA.data()["S"]
    PF = {m: U.mc_paths(S, m, n, length=R.LEN, seed=23) for m in MKTS}
    PE = {m: U.mc_paths(S, m, n, length=R.H_EVAL, seed=7) for m in MKTS}
    out = {}
    for plan in PLANS:
        sp = R.spec(plan)
        row = {"price": R.PLANS[plan]}
        for m in MKTS:
            ev = R.eval_run(sp, PE[m])
            sl = slot_full(sp, PF[m])
            be = round(100.0 * sp["price"] / sl["owner_per_pass"], 1) if sl["owner_per_pass"] else None
            row[m] = {"eval": ev, "slot": sl, "break_even_pass_pct": be}
            say(f"{plan:20s} {m:4s} pass {ev['pass']}/{ev['fail']} net6m ${sl['net_6m']} per eval ${sl['net_per_eval']} "
                f"pays/mo {sl['payouts_per_month']} spend/mo p90 ${sl['spend_per_month_p90']} owner/pass ${sl['owner_per_pass']} BE {be}%")
        row["worth_buying_in_2025"] = row["Y25"]["slot"]["net_6m"] > 0 and row["REF"]["slot"]["net_6m"] >= -2 * row["price"]
        out[plan] = row
    return out, S, PF


def part2(S, PF, say):
    """ATLAS funded 25K alone from a fresh funded start: today / smaller lane / ask the minimum."""
    base = R.spec("mffu_builder_25k")
    BYf = RL.mix_by(("ATLAS",))
    F = base["F"]
    out = {}
    for name, usd, ask in (("today ($250 a trade, ask the cap)", 250, "cap"), ("smaller ($150 a trade)", 150, "cap"),
                           ("ask the minimum every time", 250, F["pay_min"])):
        z = RL.Z(ATLAS=usd)
        row = {}
        for m in MKTS:
            res = []
            for seq in PF[m]:
                f = R.Funded(U.UP25, F, z, ask)
                owner, pays, lost, first = 0.0, 0, 0, None
                for k, si in enumerate(seq[:R.LEN]):
                    ev, x, _ = f.step(BYf[si])
                    if ev in ("paid", "grad"):
                        owner += x; pays += 1; first = first or k + 1
                    if ev in ("lost", "grad"):
                        lost += ev == "lost"
                        break
                res.append((owner, pays, lost, first))
            A = np.array([r[:3] for r in res], float)
            fp = [r[3] for r in res if r[3]]
            row[m] = {"owner_6m": round(float(A[:, 0].mean())), "payouts": round(float(A[:, 1].mean()), 2),
                      "lost_pct": round(100.0 * float(A[:, 2].mean()), 1), "no_pay_pct": round(100.0 * float((A[:, 1] == 0).mean()), 1),
                      "first_pay_med": float(np.median(fp)) if fp else None}
        out[name] = row
        say(f"ATLAS funded {name}: " + " | ".join(f"{m} ${row[m]['owner_6m']} pays {row[m]['payouts']} lost {row[m]['lost_pct']}% "
                                                  f"first {row[m]['first_pay_med']}" for m in MKTS))
    return out


def part3(owner_per_pass, price, S, say):
    """The early-warning rule on the real eval engine: a fresh Builder 50K eval started on each real session, in date order."""
    from tools import stops_targets_time as STT
    sp = R.spec("mffu_builder_50k")
    L = STT.size_matched(STT.units())
    r = [(l["day"], l["pnl"] / (l["risk0"] * 2.0 * max(1, l["qty"]))) for l in sorted(L, key=lambda l: l["entry_t"])]
    h1 = [x for d, x in r if "2026-01-01" <= d <= "2026-06-30"]
    win = [np.mean(h1[i - 20:i]) for i in range(20, len(h1) + 1)]
    lo_band, mid = float(np.percentile(win, 10)), float(np.median(win))
    days = [str(d) for d in S]
    sig, on, k, hist = {}, False, 0, []
    for day in days:
        while k < len(r) and r[k][0] < day:
            hist.append(r[k][1]); k += 1
        if len(hist) >= 20:
            m = float(np.mean(hist[-20:]))
            on = True if m < lo_band else (False if m > mid else on)
        sig[day] = on
    def outcome(i):
        e = sp["ev"]()
        for j in range(i, min(len(days), i + 40)):
            x, _ = e.step(sp["BYe"][j])
            if x == "pass":
                return "PASS"
            if x in ("fail", "stuck"):
                return "FAIL"
        return "OPEN"
    out = {"band_lo_avg_r": round(lo_band, 3), "band_mid_avg_r": round(mid, 3),
           "rule": "LIT rolling 20-trade avg R < the Jan-Jun 2026 10th pct -> ON until > the Jan-Jun median"}
    for nm, a_, z in (("2021-25", "2021-11-01", "2025-12-31"), ("2025", "2025-01-01", "2025-12-31"),
                      ("Jan-Jun 2026", "2026-01-01", "2026-06-30"), ("Jul-Oct 2026", "2026-07-01", "2026-10-16")):
        ix = [i for i, dd in enumerate(days) if a_ <= dd <= z and i + 40 <= len(days)]
        res = {s_: [outcome(i) for i in ix if sig[days[i]] == s_] for s_ in (True, False)}
        row = {}
        for s_, lab in ((True, "signal ON (stop buying)"), (False, "signal OFF")):
            R_ = res[s_]
            pas = 100.0 * sum(x == "PASS" for x in R_) / len(R_) if R_ else None
            row[lab] = {"sessions": len(R_), "pass_pct": round(pas, 1) if pas is not None else None,
                        "fail_pct": round(100.0 * sum(x == "FAIL" for x in R_) / len(R_), 1) if R_ else None,
                        "usd_per_eval": round(pas / 100 * owner_per_pass - price) if pas is not None else None}
        row["on_share_pct"] = round(100.0 * len(res[True]) / max(1, len(res[True]) + len(res[False])), 1)
        out[nm] = row
        say(f"warning {nm}: {row}")
    a, b = out["2021-25"]["signal ON (stop buying)"]["pass_pct"], out["2021-25"]["signal OFF"]["pass_pct"]
    out["useful"] = bool(a is not None and b is not None and b - a > 10 and out["Jul-Oct 2026"]["on_share_pct"] <= 20)
    return out


def part4(n, say):
    import blitz_rapid as P
    B = P.B
    S = P.SOA.data()["S"]
    PE = {m: P.U.mc_paths(S, m, n, length=P.R.H_EVAL, seed=7) for m in MKTS}
    PF = {m: P.U.mc_paths(S, m, n, length=P.R.LEN, seed=23) for m in MKTS}
    out = {}
    for name in ("V0 today LIT+ATLAS", "V5 BLITZ $150"):
        sp = P.build(name)
        row = {}
        for m in MKTS:
            ev = P.R.eval_run(sp, PE[m])
            sl = P.R.slot_run(sp, PF[m])
            row[m] = {"eval": ev, "net_6m": sl["net_6m"], "owner_6m": sl["owner_6m"], "fees_6m": sl["fees_6m"], "p_lost": sl["p_lost"]}
        out[name] = row
        say(f"Rapid {name}: " + " | ".join(f"{m} pass {row[m]['eval']['pass']}/{row[m]['eval']['fail']} net ${row[m]['net_6m']}" for m in MKTS))
    out["blitz_plus_ev_all"] = all(out["V5 BLITZ $150"][m]["net_6m"] > out["V0 today LIT+ATLAS"][m]["net_6m"] for m in MKTS)
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=500); ap.add_argument("--part4", action="store_true")
    a = ap.parse_args()
    if a.part4:                       # own process: the Rapid/BLITZ engine must load before rank's cost patch drops BLITZ
        r4 = part4(a.n, print)
        json.dump(r4, open(OUT4, "w", encoding="utf-8"), indent=1, default=float)
        return
    t0 = time.time()
    say = lambda s: print(f"[{time.time() - t0:5.0f}s] {s}", flush=True)  # noqa: E731
    res = {"made": "2026-11-24", "design": "research/badcase/DESIGN.md", "n": a.n, "markets": WORD}
    res["plans"], S, PF = part1(a.n, say)
    res["atlas_funded"] = part2(S, PF, say)
    b50 = res["plans"]["mffu_builder_50k"]["REF"]["slot"]["owner_per_pass"]
    res["warning"] = part3(b50, R.PLANS["mffu_builder_50k"], S, say)
    import subprocess
    subprocess.run([sys.executable, "-X", "utf8", os.path.abspath(__file__), "--part4", "--n", str(a.n)], check=True)
    res["blitz_rapid"] = json.load(open(OUT4, encoding="utf-8"))
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)
    say(f"-> {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()
