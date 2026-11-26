"""Business planner (research/planner/DESIGN.md, pre-registered). PAPER RESEARCH ONLY.

    python -X utf8 research/planner/planner.py [--n 1000] [--stage 1|2|all]  -> research/planner/results.json

One path = one market for the whole business: every account steps on the same session. Engine objects = research/plans/rank.py
(eval: today's two_week sizing + ATLAS lane; funded: MFFU payout rules), start state = the board on 2026-11-26.
"""
from __future__ import annotations

import argparse
import collections
import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "research", "plans"))
sys.path.insert(0, ROOT)
import rank as R  # noqa: E402

U, RL, AR, SOA = R.U, R.RL, R.AR, R.SOA
OUT = os.path.join(HERE, "results.json")
LEN, MONTH = 252, 21
PRICE = {"mffu_builder_50k": 91.80, "mffu_builder_25k": 63.00, "mffu_rapid_eod_25k": 97.20, "mffu_rapid_eod_50k": 165.00}
CAP = {"mffu_builder_50k": 1, "mffu_builder_25k": 2, "mffu_rapid_eod_25k": 3, "mffu_rapid_eod_50k": 3}
TOTAL_CAP = 5
LIT, LA, AT = ("LIT",), ("LIT", "ATLAS"), ("ATLAS",)
U.SPAN["G26"] = ("2026-01-01", "2026-10-16")

# today's accounts (board 2026-11-26 11:50 ET): name, plan, mix, stage, profit, floor (relative), sessions done
START = [("Zlarior 50K", "mffu_builder_50k", LIT, "eval", -822.48, -1831.80, 28),
         ("Zlarior 25K #2", "mffu_builder_25k", LIT, "eval", 19.24, -976.38, 6),
         ("Rapid EOD 25K", "mffu_rapid_eod_25k", LA, "eval", -4.76, -1000.0, 4),
         ("ATLAS 25K", "mffu_builder_25k", AT, "funded", 401.38, -598.62, 0)]

# buy policies: lane name -> (plan to re-buy, mix) ; extra lanes opened at the start
POLICIES = {
    "K0 today": {"rebuy": {}, "extra": []},
    "K1 run-off (no buys)": {"rebuy": None, "extra": []},
    "K2 + 2nd Rapid 25K": {"rebuy": {}, "extra": [("Rapid EOD 25K #2", "mffu_rapid_eod_25k", LA)]},
    "K3 fill the limits": {"rebuy": {}, "extra": [("Rapid EOD 25K #2", "mffu_rapid_eod_25k", LA),
                                                  ("Rapid EOD 25K #3", "mffu_rapid_eod_25k", LA)]},
    "K4 cheap (25K re-buys)": {"rebuy": {"Zlarior 50K": ("mffu_builder_25k", LIT), "Rapid EOD 25K": ("mffu_builder_25k", LIT)},
                               "extra": []},
    "K5 Rapid 50K re-buy": {"rebuy": {"Rapid EOD 25K": ("mffu_rapid_eod_50k", LA)}, "extra": []},
}
TRIPS = ("W0", "W1", "W2", "W3", "W4", "W5")
MKTS = ("G", "B", "M25", "SW")

_SP, _BY = {}, {}


def spec(plan):
    if plan not in _SP:
        _SP[plan] = R.spec(plan)
    return _SP[plan]


def by(mix, news=False):
    k = (mix, news)
    if k not in _BY:
        _BY[k] = RL.mix_by(mix, news=news)
    return _BY[k]


class Lane:
    def __init__(self, name, plan, mix):
        self.name, self.plan, self.mix = name, plan, mix
        self.st, self.obj, self.wait = "idle", None, 0

    def buy(self, plan=None, mix=None):
        if plan:
            self.plan, self.mix = plan, mix
        self.obj, self.st = spec(self.plan)["ev"](), "eval"
        return PRICE[self.plan]


def paths(S, mkt, n, seed):
    if mkt in ("G", "B"):
        return U.mc_paths(S, "G26" if mkt == "G" else "REF", n, length=LEN, seed=seed)
    a1, z1 = U.span_ix(S, "G26")
    a0, z0 = U.span_ix(S, "REF")
    rng = np.random.default_rng(seed)
    P = []
    for _ in range(n):
        s = []
        while len(s) < LEN:
            good = (len(s) < 63) if mkt == "SW" else (rng.random() < 0.25)
            a, z = (a1, z1) if good else (a0, z0)
            b = int(rng.integers(a, z - U.BLOCK + 1))
            s.extend(range(b, b + U.BLOCK))
        P.append(s[:LEN])
    return P


def run_path(seq, pol, trip, lit_r0):
    P = POLICIES[pol]
    lanes = []
    for name, plan, mix, stage, prof, fl, done in START:
        L = Lane(name, plan, mix)
        sp = spec(plan)
        if stage == "eval":
            e = sp["ev"]()
            e.bal, e.floor, e.peak, e.s, e.dtr = prof, fl, max(prof, fl + sp["E"]["mll"]), done, min(done, 3)
            L.obj, L.st = e, "eval"
        else:
            f = sp["fund"]()
            f.bal, f.floor, f.peak, f.cyc_start = prof, fl, max(prof, 0.0), 0.0
            L.obj, L.st = f, "funded"
        lanes.append(L)
    for name, plan, mix in P["extra"]:
        lanes.append(Lane(name, plan, mix))           # opened below if allowed (start of month 1)
    cash = np.zeros(LEN)
    fees = np.zeros(LEN)
    blocked, consec, peak_biz, biz = False, 0, 0.0, 0.0
    shadow, shadow_last = spec("mffu_builder_50k")["ev"](), True
    litq = collections.deque(lit_r0, maxlen=40)
    n_buy, n_pay, n_fail, n_pass = 0, 0, 0, 0
    BYL = by(LIT)

    def can_buy(plan):
        if P["rebuy"] is None or blocked:
            return False
        if trip == "W4" and not shadow_last:
            return False
        live = [x for x in lanes if x.st != "idle"]
        return len(live) < TOTAL_CAP and sum(1 for x in live if x.plan == plan) < CAP[plan]

    for k, si in enumerate(seq):
        # ---- buys (idle lanes re-open when allowed)
        for L in lanes:
            if L.st == "idle":
                plan, mix = (P["rebuy"] or {}).get(L.name, (L.plan, L.mix if L.mix != AT else AT))
                if can_buy(plan):
                    c = L.buy(plan, mix)
                    fees[k] += c; n_buy += 1
        # ---- the session
        for L in lanes:
            if L.st == "eval":
                r, _ = L.obj.step(by(L.mix)[si])
                if r == "pass":
                    L.st, L.wait, n_pass, consec = "gap", R.GAP, n_pass + 1, 0
                elif r in ("fail", "stuck"):
                    L.st, n_fail, consec = "idle", n_fail + 1, consec + 1
            elif L.st == "gap":
                L.wait -= 1
                if L.wait <= 0:
                    L.obj, L.st = spec(L.plan)["fund"](), "funded"
            elif L.st == "funded":
                ev, x, _ = L.obj.step(by(L.mix, news=L.plan.startswith("mffu_rapid"))[si])
                if ev in ("paid", "grad"):
                    cash[k] += x; n_pay += 1
                if ev in ("lost", "grad"):
                    L.st = "idle"
        # ---- shadow (free paper eval) + tripwires
        r, _ = shadow.step(BYL[si])
        if r:
            shadow_last = r == "pass"
            shadow = spec("mffu_builder_50k")["ev"]()
            if shadow_last and blocked:
                blocked, consec, peak_biz = False, 0, biz
        for t in BYL[si]:
            litq.append(t["pts"] / t["risk"])
        biz += cash[k] - fees[k]
        peak_biz = max(peak_biz, biz)
        if not blocked:
            if (trip == "W1" and consec >= 2) or (trip == "W2" and consec >= 3) or \
                    (trip == "W3" and len(litq) >= 40 and sum(litq) < 0) or (trip == "W5" and biz < peak_biz - 300.0):
                blocked = True
    return cash, fees, n_buy, n_pay, n_fail, n_pass


def stats(rows):
    C = np.array([r[0] for r in rows])
    F = np.array([r[1] for r in rows])
    net = C - F
    m = net.reshape(len(rows), LEN // MONTH, MONTH).sum(2)
    cum = np.cumsum(-net, 1)
    pc = lambda a, q: round(float(np.percentile(a, q)))  # noqa: E731
    n12, n6 = net.sum(1), net[:, :126].sum(1)
    return {"net12_mean": round(float(n12.mean())), "net12_p10": pc(n12, 10), "net12_p50": pc(n12, 50), "net12_p90": pc(n12, 90),
            "net6_mean": round(float(n6.mean())), "net6_p10": pc(n6, 10), "net6_p50": pc(n6, 50), "net6_p90": pc(n6, 90),
            "month_1_6": [pc(m[:, :6], q) for q in (10, 50, 90)], "month_7_12": [pc(m[:, 6:], q) for q in (10, 50, 90)],
            "fees_month_mean": round(float(F.sum(1).mean() / 12), 1), "fees_month_p90": round(float(np.percentile(F.sum(1), 90) / 12), 1),
            "cash_needed_p90": pc(np.maximum(0, cum.max(1)), 90), "p_loss12": round(100 * float((n12 < 0).mean()), 1),
            "buys": round(float(np.mean([r[2] for r in rows])), 2), "pays": round(float(np.mean([r[3] for r in rows])), 2),
            "fails": round(float(np.mean([r[4] for r in rows])), 2), "passes": round(float(np.mean([r[5] for r in rows])), 2)}


G = {}


def job(args):
    pol, trip, mkt = args
    rows = [run_path(seq, pol, trip, G["lit0"]) for seq in G["P"][mkt]]
    return (pol, trip, mkt), stats(rows)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--stage", default="all")
    ap.add_argument("--pick", default="")
    a = ap.parse_args(argv)
    t0 = time.time()
    AR.rapid_patch(AR.T_at(10))
    S = SOA.data()["S"]
    for plan in PRICE:
        spec(plan)
    for mix in (LIT, LA, AT):
        by(mix); by(mix, True)
    lit = [t["pts"] / t["risk"] for ts in by(LIT) for t in ts]
    G["lit0"] = lit[-40:]
    G["P"] = {m: paths(S, m, a.n, 23 + i) for i, m in enumerate(MKTS)}
    out = json.load(open(OUT)) if os.path.exists(OUT) else {"n": a.n, "rows": {}}
    ctx = mp.get_context("fork")
    if a.stage in ("1", "all"):
        jobs = [(p, "W0", m) for p in POLICIES for m in MKTS]
        with ctx.Pool(4) as pool:
            for key, st in pool.imap_unordered(job, jobs):
                out["rows"]["|".join(key)] = st
                print(key, st["net12_mean"], st["net12_p10"], st["net12_p50"], st["net12_p90"], f"[{time.time() - t0:.0f}s]", flush=True)
        K0B = out["rows"]["K0 today|W0|B"]["net12_mean"]
        el = [p for p in POLICIES if out["rows"][f"{p}|W0|B"]["net12_mean"] >= K0B - 300]
        pick = max(el, key=lambda p: out["rows"][f"{p}|W0|M25"]["net12_mean"])
        r = lambda p, m: out["rows"][f"{p}|W0|{m}"]["net12_mean"]  # noqa: E731
        out["buy_pick"] = {"pick": pick, "eligible": el,
                           "card": pick != "K0 today" and r(pick, "G") > r("K0 today", "G") and r(pick, "SW") > r("K0 today", "SW")}
        print("BUY PICK", out["buy_pick"], flush=True)
        json.dump(out, open(OUT, "w"), indent=1)
    if a.stage in ("2", "all"):
        pick = a.pick or out["buy_pick"]["pick"]
        pols = sorted({"K0 today", pick})
        jobs = [(p, t, m) for p in pols for t in TRIPS[1:] for m in MKTS]
        with ctx.Pool(4) as pool:
            for key, st in pool.imap_unordered(job, jobs):
                out["rows"]["|".join(key)] = st
                print(key, st["net12_mean"], st["net12_p10"], st["net12_p50"], st["net12_p90"], f"[{time.time() - t0:.0f}s]", flush=True)
        out["trip"] = {}
        for p in pols:
            for t in TRIPS[1:]:
                w0 = {m: out["rows"][f"{p}|W0|{m}"]["net12_mean"] for m in MKTS}
                w = {m: out["rows"][f"{p}|{t}|{m}"]["net12_mean"] for m in MKTS}
                ok = {"B_cut50": (w0["B"] >= 0) or (w["B"] >= 0.5 * w0["B"]), "SW_better": w["SW"] > w0["SW"],
                      "G_90": w["G"] >= 0.9 * w0["G"], "M25_ok": w["M25"] >= w0["M25"] - 0.1 * abs(w0["M25"])}
                out["trip"][f"{p}|{t}"] = {**ok, "works": all(ok.values()), "SW_gain": w["SW"] - w0["SW"]}
                print("TRIP", p, t, out["trip"][f"{p}|{t}"], flush=True)
        json.dump(out, open(OUT, "w"), indent=1)


if __name__ == "__main__":
    main()
