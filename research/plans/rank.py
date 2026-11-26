"""Plan ranking (2026-11-22): every allowed eval plan for LIT + ATLAS by real money. PAPER RESEARCH ONLY (nothing bought).
Design (committed before the run): research/plans/DESIGN.md. Write-up: research/writeups/plan-ranking-2026-11-22.md.

    python -X utf8 research/plans/rank.py [--n 1000]     -> research/plans/results.json
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
for p in (ROOT, os.path.join(ROOT, "tools"), os.path.join(ROOT, "tools", "money")):
    sys.path.insert(0, p)
import logging  # noqa: E402
logging.getLogger("engine.sizing").setLevel(logging.ERROR)
import account4_sim as A4  # noqa: E402
import atlas_risk as AR  # noqa: E402
import rapid_levers as RL  # noqa: E402
import stack_one_account as SOA  # noqa: E402
import uprisk as U  # noqa: E402
from engine import sizing as SZ  # noqa: E402

OUT = os.path.join(HERE, "results.json")
PV, COMM, SLIP = A4.PV, A4.COMM, A4.SLIP
LEN, GAP, H_EVAL = 126, A4.GAP, 60
SPANS = ("H1", "H2", "REF")
PLANS = {"mffu_builder_25k": 63.00, "mffu_builder_50k": 91.80, "mffu_rapid_eod_25k": 97.20, "mffu_rapid_eod_50k": 165.00,
         "lucid_pro_50k": 126.00, "lucid_flex_50k": 134.40, "fn_rapid_daily_50k": 149.99}
LABEL = {"mffu_builder_25k": "MFFU Builder 25K", "mffu_builder_50k": "MFFU Builder 50K", "mffu_rapid_eod_25k": "MFFU Rapid EOD 25K",
         "mffu_rapid_eod_50k": "MFFU Rapid EOD 50K", "lucid_pro_50k": "LucidPro 50K (DLL on)", "lucid_flex_50k": "LucidFlex 50K",
         "fn_rapid_daily_50k": "FundedNext Rapid Daily 50K"}


class Funded(A4.Lucid):
    """tools/account4_sim.Lucid's payout logic on the plan's rules, with ATLAS on its own lane (rapid_levers.q_add)."""

    def __init__(self, fcfg, R, z, ask):
        super().__init__(fcfg, R, ask)
        self.z = z

    def step(self, ts, keep=None):
        if self.state != "on":
            return None, None, 0.0
        R, c = self.R, self.cfg
        self.k += 1
        dll, mq, cap = self.dll(), self.maxq(), self.cap()
        A = {"mll": R["mll"], "lock": R["lock"], "dll": dll, "buffer": R["buffer"], "pay_min": R["pay_min"], "pay_max": cap,
             "split": R["split"], "cons": R["cons"] or 0.5, "cycle_days": 0, "first_wait": 0, "max_payouts": R["max_payouts"],
             "max_micros": mq, "scale": 1.0}
        cyc = {"cycle_start_bal": round(self.cyc_start, 2), "cycle_prev": round(sum(self.cyc), 2),
               "best_prev": round(max(self.cyc), 2) if self.cyc else 0.0, "cycle_days_prev": len(self.cyc), "payouts_n": len(self.pays),
               "cycle_target": round(max(0.0, R["buffer"] + min(cap, 2000.0) - self.cyc_start), 2)}
        cum = 0.0
        for t in ts:
            if cum <= -dll:
                break
            room = round(self.bal + cum - self.floor, 2)
            if t["strat"] == "LIT":
                st = {"room": room, "cum": cum, "locked": self.floor >= R["lock"] - 1e-9, "bal": self.bal, **cyc}
                q = min(SZ.funded_qty(t, st, c, acct=A), mq)
            else:
                q = RL.q_add(t, self.z, room, cum, mq, dll)
            if q <= 0:
                continue
            self.n_tr += 1
            pnl = t["pts"] * PV * q - COMM * q
            low = min(0.0, t["w1"] * PV * q - COMM * q, pnl)
            if cum + low <= -dll:
                pnl = -dll - cum - SLIP * PV * q
                low = pnl
            if self.bal + cum + low <= self.floor:
                self.state = "lost"
                return "lost", None, round(self.floor - self.bal, 2)
            cum += pnl
        if abs(cum) > 1e-9:
            self.bal += round(cum, 2)
            self.cyc.append(round(cum, 2))
        self.peak = max(self.peak, self.bal)
        self.floor = min(max(self.floor, self.peak - R["mll"]), R["lock"])
        if self.bal - self.floor < R["stuck"]:                # stuck: 1 micro no longer fits a stop = a dead account (buy again)
            self.state = "lost"
            return "lost", None, round(cum, 2)
        above, cprof = self.bal - R["buffer"] - R.get("keep", 0.0), self.bal - self.cyc_start
        ok = above >= R["pay_min"] and cprof >= R["cycle_min"] and cprof > 0
        if R["cons"]:
            ok = ok and max([x for x in self.cyc if x > 0], default=0.0) <= R["cons"] * cprof + 1e-9
        if R["win_days"]:
            ok = ok and sum(1 for x in self.cyc if x >= R["win_min"]) >= R["win_days"]
        if R.get("cycle_days"):
            ok = ok and len(self.cyc) >= R["cycle_days"]
        amt = min(cap, above)
        if R["share"]:
            amt = min(amt, R["share"] * cprof)
        line = cap if self.ask == "cap" else min(cap, float(self.ask))
        if ok and amt >= max(R["pay_min"], line - 1e-6):
            amt = round(amt, 2)
            self.pays.append(amt)
            self.bal -= amt
            self.cyc, self.cyc_start = [], self.bal
            if len(self.pays) >= R["max_payouts"]:
                self.state = "grad"
                return "grad", amt * self.split, round(cum, 2)
            return "paid", amt * self.split, round(cum, 2)
        return None, None, round(cum, 2)


def spec(plan):
    E, F = A4.rules(plan)
    big = "50k" in plan
    soft = 1000.0 if big else 500.0
    E = {**E, "stuck": 200.0 if big else 100.0}
    has_cons = bool(E.get("cons"))
    if not has_cons:
        E["cons"] = 1.0                                     # no eval consistency rule: the pass check never binds
    ec = A4.ecfg({**E, "dll": min(E["dll"], soft)})
    ec["two_week"]["acct"]["dll"] = min(E["dll"], soft)
    ec["_dll"] = min(E["dll"], soft)
    F = {**F, "dll": min(F["dll"], soft), "stuck": 200.0 if big else 100.0}
    if plan.startswith("mffu_rapid"):
        F["cycle_min"] = max(F["cycle_min"], 500.0 if big else 250.0)   # >= $500 / $250 net since the last payout
        F["keep"] = 1000.0 if big else 500.0                            # the bot's own Rapid rule (engine/rapid.py CUSHION)
    ask = "cap" if F["cap1"] < 1e8 else F["pay_min"]
    z = RL.Z(ATLAS=500 if big else 250)
    fcfg = U.UP50 if big else U.UP25
    news = plan.startswith("mffu_rapid")
    return {"E": E, "F": F, "z": z, "price": PLANS[plan],
            "ev": lambda: RL.Ev(ec, E, z, "guard" if has_cons else "none"),
            "fund": lambda: Funded(fcfg, F, z, ask),
            "BYe": RL.mix_by(RL.LA), "BYf": RL.mix_by(RL.LA, news=news)}


def slot_run(sp, paths):
    rows = []
    for seq in paths:
        cost, owner, evals, lost, pays, first_pay, first_pass = sp["price"], 0.0, 1, 0, 0, None, None
        e, f, wait = sp["ev"](), None, 0
        for k, si in enumerate(seq[:LEN]):
            if e is not None:
                r, _ = e.step(sp["BYe"][si])
                if r == "pass":
                    first_pass = first_pass or k + 1
                    e, wait = None, GAP
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
                first_pay = first_pay or k + 1
            if ev in ("lost", "grad"):
                lost += ev == "lost"
                f = None
                e = sp["ev"](); cost += sp["price"]; evals += 1
        rows.append((owner, cost, evals, lost, pays, first_pay, first_pass))
    a = np.array([[r[0], r[1]] for r in rows])
    net = a[:, 0] - a[:, 1]
    fp = [r[5] for r in rows if r[5]]
    return {"owner_6m": round(float(a[:, 0].mean())), "fees_6m": round(float(a[:, 1].mean()), 1), "net_6m": round(float(net.mean())),
            "net_p10": round(float(np.percentile(net, 10))), "net_p50": round(float(np.percentile(net, 50))),
            "per_dollar": round(float(a[:, 0].mean() / a[:, 1].mean()), 2), "no_pay": round(100.0 * sum(1 for r in rows if not r[4]) / len(rows), 1),
            "evals": round(float(np.mean([r[2] for r in rows])), 2), "lost": round(float(np.mean([r[3] for r in rows])), 2),
            "p_lost": round(100.0 * sum(1 for r in rows if r[3]) / len(rows), 1), "pays": round(float(np.mean([r[4] for r in rows])), 2),
            "first_pay_med": float(np.median(fp)) if fp else None}


def eval_run(sp, paths):
    res = []
    for seq in paths:
        e = sp["ev"]()
        out, used = "open", H_EVAL
        for k, si in enumerate(seq[:H_EVAL]):
            r, _ = e.step(sp["BYe"][si])
            if r:
                out, used = ("pass" if r == "pass" else "fail"), k + 1
                break
        res.append((out, used))
    n = len(res)
    pas = [u for o, u in res if o == "pass"]
    return {"pass": round(100.0 * len(pas) / n, 1), "fail": round(100.0 * sum(1 for o, _ in res if o == "fail") / n, 1),
            "med_days": float(np.median(pas)) if pas else None}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    a = ap.parse_args(argv)
    t0 = time.time()
    A4.apply_costs()                               # LIT's trades at engine/costs.py exit costs (2-tick stops)
    AR.rapid_patch(AR.T_costs())                   # ATLAS at engine/costs.py (12 ticks entry, 2 on stop / market exits), no BLITZ
    S = SOA.data()["S"]
    PF = {sp: U.mc_paths(S, sp, a.n, length=LEN, seed=23) for sp in SPANS}
    PE = {sp: U.mc_paths(S, sp, a.n, length=H_EVAL, seed=7) for sp in SPANS}
    out = {"n": a.n, "rows": {}}
    for plan in PLANS:
        sp = spec(plan)
        r = {"label": LABEL[plan], "price": PLANS[plan]}
        for s in SPANS:
            r[s] = {"eval": eval_run(sp, PE[s]), "slot": slot_run(sp, PF[s])}
        H1, H2, REF = (r[s]["slot"] for s in SPANS)
        r["buy_ok"] = H1["net_6m"] > 0 and H2["net_6m"] > 0 and REF["net_6m"] >= -2 * PLANS[plan]
        out["rows"][plan] = r
        print(f"{LABEL[plan]:28s} " + " | ".join(
            f"{s} pass {r[s]['eval']['pass']}% ~{r[s]['eval']['med_days']}d net ${r[s]['slot']['net_6m']} owner ${r[s]['slot']['owner_6m']} "
            f"fees ${r[s]['slot']['fees_6m']} x{r[s]['slot']['per_dollar']} lost {r[s]['slot']['p_lost']}% nopay {r[s]['slot']['no_pay']}%"
            for s in SPANS) + f" {'BUY-OK' if r['buy_ok'] else ''} [{time.time() - t0:.0f}s]", flush=True)
    rank = sorted(out["rows"], key=lambda p: -out["rows"][p]["H2"]["slot"]["net_6m"])
    out["rank_h2"] = rank
    out["buys"] = [p for p in rank if out["rows"][p]["buy_ok"]][:2]
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=float)
    print("rank:", rank, "buys:", out["buys"])


if __name__ == "__main__":
    main()
