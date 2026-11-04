"""The more-accounts plan (job 27, 2026-11-04): what 1 / 2 / 3 / 4 / 6 MFFU accounts of mixed 50K / 25K would make a month after fees,
with the accounts' days kept together (the same sampled sessions drive every account) so a bad week hits all of them.
RESEARCH ONLY. Input: research/second/sn_daily.npz (python -X utf8 tools/second_night.py corr) = the 2026 daily series of
LIT (run lit_live $), ATLAS (account-B units, R) and BLITZ (account-C 1m trades, R).

Account lifecycle (MFFU Builder, research/lit/mffu_rules.json, confirmed): eval -> 2 sessions of paperwork -> funded -> payouts at 80%,
a breach buys a new eval. 50K: target 3,000, EOD trailing max loss 2,000 locked at start + 100, soft daily loss 1,000, buffer 2,100,
payout 500-2,000, best day <= 50% of the cycle, 2 trading days a cycle, 5 payouts. 25K: 1,500 / 1,000 / 600 / buffer 1,100 / payout
250-1,000. Funded caps per person: 1 Builder 50K and 2 Builder 25K at once (a passed account over the cap waits).
Sizes (nominal, from the stored runs): LIT $ as lit_live, LIT copy on a 25K = 0.6 x, ATLAS $500 risk a trade, BLITZ $450 in the eval and
$150 funded (a day capped at +$400). Prices: LIT 50K $91.80, ATLAS 25K $43, BLITZ / LIT 25K $63 (the owner's real prices).

    python -X utf8 tools/second_plan.py            # -> research/second/sn_plan.json
Simplifications are listed in the write-up (daily resolution, no stuck-room rule, eval size = funded size for LIT / ATLAS).
"""
from __future__ import annotations

import collections
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_P = os.path.join(ROOT, "research", "second", "sn_plan.json")
PLANS = {"50": {"target": 3000.0, "mll": 2000.0, "dll": 1000.0, "buf": 2100.0, "pmin": 500.0, "pmax": 2000.0, "cap": 1},
         "25": {"target": 1500.0, "mll": 1000.0, "dll": 600.0, "buf": 1100.0, "pmin": 250.0, "pmax": 1000.0, "cap": 2}}
LOCK, SPLIT, PAPER_DAYS, MAX_PAY = 100.0, 0.8, 2, 5


class Acct:
    def __init__(self, name, plan, price, eval_s, fund_s):
        self.name, self.P, self.price, self.es, self.fs, self.plan = name, PLANS[plan], price, eval_s, fund_s, plan
        self.fees = price
        self.evals, self.fails, self.pay, self.paid_n, self.first = 1, 0, 0.0, 0, None
        self.state, self.wait = "eval", 0
        self.breach_days = []
        self.reset_eval()

    def reset_eval(self):
        self.bal = self.peak = 0.0
        self.floor = -self.P["mll"]

    def _start_funded(self):
        self.bal = self.peak = 0.0
        self.floor = -self.P["mll"]
        self.days, self.cyc_days, self.cyc_best, self.cyc_profit = 0, 0, 0.0, 0.0
        self.paid_n = 0

    def _breach(self, k):
        self.fails += 1
        self.evals += 1
        self.fees += self.price
        self.breach_days.append(k)
        self.state = "eval"
        self.reset_eval()

    def step(self, k, cap_free):
        P = self.P
        if self.state == "wait_cap":
            if cap_free(self.plan):
                self.state = "funded"
                self._start_funded()
            return
        if self.state == "paper":
            self.wait -= 1
            if self.wait <= 0:
                if cap_free(self.plan):
                    self.state = "funded"
                    self._start_funded()
                else:
                    self.state = "wait_cap"
            return
        if self.state == "done":
            return
        x = float((self.es if self.state == "eval" else self.fs)[k])
        x = max(x, -P["dll"])
        self.bal += x
        if self.state == "eval":
            if self.bal <= self.floor:
                self._breach(k)
                return
            self.peak = max(self.peak, self.bal)
            self.floor = min(max(self.floor, self.peak - P["mll"]), LOCK)
            if self.bal >= P["target"]:
                self.state, self.wait = "paper", PAPER_DAYS
            return
        self.days += 1
        if abs(x) > 1e-9:
            self.cyc_days += 1
        self.cyc_best = max(self.cyc_best, x)
        self.cyc_profit += x
        if self.bal <= self.floor:
            self._breach(k)
            return
        if self.paid_n == 0:
            self.peak = max(self.peak, self.bal)
            self.floor = min(max(self.floor, self.peak - P["mll"]), LOCK)
        avail = self.bal - P["buf"]
        if (self.cyc_days >= 2 and avail >= P["pmin"] and self.cyc_profit > 0 and self.cyc_best <= 0.5 * self.cyc_profit + 1e-9):
            amt = min(P["pmax"], avail)
            self.bal -= amt
            self.pay += SPLIT * amt
            self.paid_n += 1
            self.floor = LOCK
            self.cyc_days, self.cyc_best, self.cyc_profit = 0, 0.0, 0.0
            if self.first is None:
                self.first = k
            if self.paid_n >= MAX_PAY:
                self.state = "done"


def sim_plan(spec, starts, n_paths=400, length=126, seed=11):
    rng = np.random.default_rng(seed)
    res = []
    for p in range(n_paths):
        idx = []
        while len(idx) < length:
            b = int(rng.choice(starts))
            idx += list(range(b, b + 5))
        idx = np.array(idx[:length])
        A = [Acct(nm, pl, pr, es[idx], fs[idx]) for nm, pl, pr, es, fs in spec]
        for k in range(length):
            def cap_free(plan, A=A):
                return sum(1 for a in A if a.plan == plan and a.state == "funded") < PLANS[plan]["cap"]
            for a in A:
                a.step(k, cap_free)
        res.append({"A": [(a.name, a.pay, a.fees, a.fails, a.paid_n, a.first, list(a.breach_days), a.evals) for a in A]})
    return res


def summarize(res, length=126):
    net = np.array([sum(x[1] - x[2] for x in r["A"]) for r in res])
    pay = np.array([sum(x[1] for x in r["A"]) for r in res])
    fees = np.array([sum(x[2] for x in r["A"]) for r in res])
    ev = np.array([sum(x[7] for x in r["A"]) for r in res])
    fl = np.array([sum(x[3] for x in r["A"]) for r in res])
    firsts = [min([x[5] for x in r["A"] if x[5] is not None], default=None) for r in res]
    got = [f for f in firsts if f is not None]
    joint = 0
    for r in res:
        w = collections.Counter()
        for x in r["A"]:
            for d in set(int(b) // 5 for b in x[6]):
                w[d] += 1
        joint += sum(1 for v in w.values() if v >= 2)
    months = length / 21.0
    return {"per_month": round(float(net.mean() / months)), "net_6m": round(float(net.mean())), "p10_net_6m": round(float(np.percentile(net, 10))),
            "p90_net_6m": round(float(np.percentile(net, 90))), "neg_6m_pct": round(100.0 * float((net < 0).mean()), 1),
            "owner_payouts_6m": round(float(pay.mean())), "fees_6m": round(float(fees.mean())), "evals_bought_6m": round(float(ev.mean()), 2),
            "fails_6m": round(float(fl.mean()), 2), "fails_per_month": round(float(fl.mean() / months), 2),
            "evals_per_month": round(float(ev.mean() / months), 2), "any_payout_pct": round(100.0 * len(got) / len(res), 1),
            "first_payout_session_med": float(np.median(got)) if got else None, "first_payout_session_p90": float(np.percentile(got, 90)) if got else None,
            "joint_breach_windows_per_path": round(joint / len(res), 3)}


def main():
    z = np.load(os.path.join(ROOT, "research", "second", "sn_daily.npz"))
    days = [str(d) for d in z["days"]]
    n = len(days)
    split = sum(1 for d in days if d <= "2026-06-30")
    L, AR, BR = z["L"], z["A_R"], z["B_R"]
    # funded winner caps as the live funded presets (50K: a winner <= $2,000; 25K: <= $1,000; BLITZ: no new trade after +$400)
    ser = {"L50": (np.minimum(L, 3000.0), np.minimum(L, 2000.0)), "L25": (np.minimum(0.6 * L, 1500.0), np.minimum(0.6 * L, 1000.0)),
           "A25": (500.0 * AR, np.minimum(500.0 * AR, 1000.0)), "B25": (450.0 * BR, np.minimum(150.0 * BR, 400.0))}
    PRICE = {"L50": 91.80, "L25": 63.0, "A25": 43.0, "B25": 63.0}
    PL = {"L50": "50", "L25": "25", "A25": "25", "B25": "25"}
    SETS = collections.OrderedDict([
        ("1 account: LIT 50K", ["L50"]), ("1 account: ATLAS 25K", ["A25"]), ("1 account: BLITZ 25K", ["B25"]),
        ("2 accounts: LIT 50K + ATLAS 25K", ["L50", "A25"]),
        ("2 accounts: LIT 50K + BLITZ 25K", ["L50", "B25"]),
        ("3 accounts: LIT 50K + ATLAS 25K + BLITZ 25K", ["L50", "A25", "B25"]),
        ("4 accounts: + a LIT copy on a 25K", ["L50", "A25", "B25", "L25"]),
        ("6 accounts: + a 2nd ATLAS 25K + a 2nd BLITZ 25K", ["L50", "A25", "B25", "L25", "A25", "B25"]),
    ])
    spans = {"H1": list(range(0, split - 5)), "H2": list(range(split, n - 5)), "2026": list(range(0, n - 5))}
    out = {"sessions": n, "split": split, "prices": PRICE, "plans": {}}
    for nm, mem in SETS.items():
        out["plans"][nm] = {}
        spec = [(f"{m}#{i}", PL[m], PRICE[m], ser[m][0], ser[m][1]) for i, m in enumerate(mem)]
        for sp, st in spans.items():
            t1 = time.time()
            R = sim_plan(spec, st, n_paths=int(os.environ.get("PLAN_PATHS", "400")))
            o = summarize(R)
            o["by_account"] = {}
            for i, m in enumerate(mem):
                key = f"{m}#{i}"
                a = np.array([[x[1], x[2], x[3], x[4]] for r in R for x in r["A"] if x[0] == key], float)
                o["by_account"][key] = {"owner_payouts_6m": round(float(a[:, 0].mean())), "fees_6m": round(float(a[:, 1].mean())),
                                        "net_per_month": round(float((a[:, 0] - a[:, 1]).mean() / 6.0)), "fails_6m": round(float(a[:, 2].mean()), 2),
                                        "payouts_n": round(float(a[:, 3].mean()), 2)}
            out["plans"][nm][sp] = o
            print(f"{nm:50s} {sp:5s} {json.dumps({k: v for k, v in o.items() if k != 'by_account'})} ({time.time() - t1:.0f}s)", flush=True)
            json.dump(out, open(OUT_P, "w"), indent=1)
    json.dump(out, open(OUT_P, "w"), indent=1)


if __name__ == "__main__":
    main()
