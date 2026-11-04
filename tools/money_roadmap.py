"""The owner's MONEY ROADMAP (job 31, 2026-11-04): 12 months, month by month, for the three accounts he runs or is about to arm:
LIT on a Builder 50K, ATLAS on a Builder 25K, BLITZ on a Builder 25K. RESEARCH / DISPLAY ONLY: nothing live is read or changed.

What it does: a lifecycle Monte Carlo (5-session blocks of the real 2026 sessions, 21 sessions = 1 model month, 252 sessions = 12 months),
one set of sampled sessions drives all accounts at once, so a bad week hits every account. It re-uses tools/second_plan.Acct (the funded
study's account: eval -> 2 sessions paperwork -> funded -> payouts at the 80% split, payout caps, a breach buys a new eval) and records every
fee and every payout with its session, so each month shows cash in, cash out, net, and the whole thing reconciles to the cent.

    python -X utf8 tools/money_roadmap.py            # full run (3,000 paths a half) -> research/props/roadmap.json
    python -X utf8 tools/money_roadmap.py report     # roadmap.json -> research/writeups/2026-11-04_money_roadmap.md (plain words) and the small
                                                     # published tools/web_public/plutus/roadmap.json (+ roadmapfallback.js) for Plutus and Ledger
    python -X utf8 tools/money_roadmap.py check      # reconciliation self-check of a small fresh run AND of the stored roadmap.json
Inputs: research/second/sn_daily.npz (python -X utf8 tools/second_night.py corr): 2026 daily LIT $, ATLAS R, BLITZ R.
Every number is shown for Jan-Jun 2026 (H1, the pick half) and Jul-Oct 2026 (H2, the check half). H2 is the CONSERVATIVE one.
"""
from __future__ import annotations

import datetime as dt
import itertools
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.second_plan import Acct, PLANS, SPLIT, MAX_PAY  # noqa: E402

OUT_P = os.path.join(ROOT, "research", "props", "roadmap.json")
NPZ = os.path.join(ROOT, "research", "second", "sn_daily.npz")
MONTH = 21
MONTHS = 12
LEN = MONTH * MONTHS
PRICE = {"L50": 91.80, "L50f": 91.80, "L25": 63.0, "A25": 43.0, "B25": 63.0}
PLAN_OF = {"L50": "50", "L50f": "50", "L25": "25", "A25": "25", "B25": "25"}
LABEL = {"L50": "LIT on the 50K", "L50f": "LIT on the 50K (eval sized as the engine study)", "A25": "ATLAS on a 25K", "B25": "BLITZ on a 25K", "L25": "LIT copy on a 25K",
         "A25b": "ATLAS copy on a 25K"}
SERKEY = {"L50": "L50", "L50f": "L50f", "A25": "A25", "A25b": "A25", "B25": "B25", "L25": "L25"}
# engine-faithful 2-week (10 sessions) pass / fail, % (the published eval studies; the daily model below is coarser)
PUBLISHED_2W = {"L50": {"H1": (52.9, 17.8), "H2": (58.6, 20.9)}, "A25": {"H1": (65.5, 0.0), "H2": (43.5, 0.0)},
                "B25": {"H1": (49.6, 26.9), "H2": (36.2, 21.7)}}
HOLIDAYS = {dt.date(2026, 11, 26), dt.date(2026, 12, 25), dt.date(2027, 1, 1), dt.date(2027, 1, 18), dt.date(2027, 2, 15),
            dt.date(2027, 3, 26), dt.date(2027, 5, 31), dt.date(2027, 6, 18), dt.date(2027, 7, 5), dt.date(2027, 9, 6),
            dt.date(2027, 11, 25)}
FIRST_SESSION = dt.date(2026, 11, 5)


def calendar(n=LEN):
    d, out = FIRST_SESSION, []
    while len(out) < n:
        if d.weekday() < 5 and d not in HOLIDAYS:
            out.append(d)
        d += dt.timedelta(days=1)
    return out


CAL = calendar()


def dstr(k):
    return CAL[min(int(k), LEN - 1)].isoformat()


def series():
    z = np.load(NPZ)
    days = [str(d) for d in z["days"]]
    split = sum(1 for d in days if d <= "2026-06-30")
    L, AR, BR = z["L"], z["A_R"], z["B_R"]
    ser = {"L50": (np.minimum(L, 3000.0), np.minimum(L, 2000.0)), "L25": (np.minimum(0.6 * L, 1500.0), np.minimum(0.6 * L, 1000.0)),
           "A25": (500.0 * AR, np.minimum(500.0 * AR, 1000.0)), "B25": (450.0 * BR, np.minimum(150.0 * BR, 400.0))}
    # the engine-faithful LIT eval (uprisk: room_f 0.8, no weekly stop) risks more than the funded size and so is faster than the daily
    # model's plain series; 1.75 x is the scale that best matches the published 2-week pass / fail in H1 (50 / 14 vs 52.9 / 17.8)
    ser["L50f"] = (np.minimum(1.75 * L, 5250.0), ser["L50"][1])
    return ser, len(days), split


class RAcct(Acct):
    """second_plan.Acct plus: a start session, a bill for every purchase, an event log, the first eval's pass / fail session and
    (optionally) a new eval once the account has moved to live after its 5th payout."""

    def __init__(self, name, key, start=0, sunk=False, recycle=False):
        self.key = key
        super().__init__(name, PLAN_OF[SERKEY[key] if SERKEY[key] in PLAN_OF else key], PRICE[SERKEY[key]], SER[SERKEY[key]][0], SER[SERKEY[key]][1])
        self.fees = 0.0
        self.start, self.sunk_flag, self.recycle = start, sunk, recycle
        self.sunk = 0.0
        self.ev = []  # (session, "fee"|"sunk"|"pay", amount)
        self.pass_k = self.fail_k = self.fund_k = None
        self.grads = 0
        self.state = "pending"

    def _bill(self, k, initial=False):
        self.fees += self.price
        if initial and self.sunk_flag:
            self.sunk += self.price
            self.ev.append((k, "sunk", self.price))
        else:
            self.ev.append((k, "fee", self.price))

    def step(self, k, cap_free):
        if k < self.start:
            return
        if k == self.start and self.state == "pending":
            self.state = "eval"
            self._bill(k, initial=True)
        p0, f0, s0, n0 = self.pay, self.fees, self.state, self.fails
        super().step(k, cap_free)
        if self.pay > p0 + 1e-9:
            self.ev.append((k, "pay", self.pay - p0))
        if self.fees > f0 + 1e-9:  # a breach bought a new eval
            self.ev.append((k, "fee", self.fees - f0))
            if self.fail_k is None and self.pass_k is None:  # the first eval failed
                self.fail_k = k
        if s0 == "eval" and self.state == "paper" and self.pass_k is None and self.fail_k is None:
            self.pass_k = k
        if s0 != "funded" and self.state == "funded" and self.fund_k is None:
            self.fund_k = k
        if self.state == "done" and self.recycle and k < LEN - 1:
            self.grads += 1
            self._bill(k)
            self.evals += 1
            self.state = "eval"
            self.reset_eval()
        elif self.state == "done" and s0 != "done":
            self.grads += 1


def paths(starts, n, seed):
    rng = np.random.default_rng(seed)
    out = np.zeros((n, LEN), int)
    for p in range(n):
        idx = []
        while len(idx) < LEN:
            b = int(rng.choice(starts))
            idx += list(range(b, b + 5))
        out[p] = idx[:LEN]
    return out


def simulate(spec, idxs):
    """spec = [(name, key, start, sunk, recycle)]. Returns dict of arrays per path / account / month."""
    global SER
    P, A = len(idxs), len(spec)
    pay = np.zeros((P, A, MONTHS))
    fee = np.zeros((P, A, MONTHS))
    sunk = np.zeros((P, A))
    first_pay = np.full((P, A), -1.0)
    pass_k = np.full((P, A), -1.0)
    fail_k = np.full((P, A), -1.0)
    fund_k = np.full((P, A), -1.0)
    counters = np.zeros((P, A, 4))  # a.pay, a.fees, fails, grads (the account's own books, for the reconciliation)
    for p in range(P):
        base = {k: (v[0], v[1]) for k, v in SER0.items()}
        ix = idxs[p]
        SER = {k: (v[0][ix], v[1][ix]) for k, v in base.items()}
        accts = [RAcct(nm, key, st, sk, rc) for nm, key, st, sk, rc in spec]
        for k in range(LEN):
            def cap_free(plan, accts=accts):
                return sum(1 for a in accts if a.plan == plan and a.state == "funded") < PLANS[plan]["cap"]
            for a in accts:
                a.step(k, cap_free)
        for i, a in enumerate(accts):
            for k, kind, amt in a.ev:
                m = min(k // MONTH, MONTHS - 1)
                if kind == "pay":
                    pay[p, i, m] += amt
                    if first_pay[p, i] < 0:
                        first_pay[p, i] = k
                elif kind == "fee":
                    fee[p, i, m] += amt
                else:
                    sunk[p, i] += amt
            pass_k[p, i] = -1 if a.pass_k is None else a.pass_k - a.start
            fail_k[p, i] = -1 if a.fail_k is None else a.fail_k - a.start
            fund_k[p, i] = -1 if a.fund_k is None else a.fund_k
            counters[p, i] = (a.pay, a.fees, a.fails, a.grads)
    return {"pay": pay, "fee": fee, "sunk": sunk, "first_pay": first_pay, "pass_k": pass_k, "fail_k": fail_k, "fund_k": fund_k,
            "counters": counters, "names": [s[0] for s in spec], "spec": spec}


def _pct(a, q):
    return float(np.percentile(a, q))


def table(R, who=None):
    """Month-by-month cash for the chosen accounts (all if None): mean in / out / net, and p10 / p90 of net and of the running total."""
    ix = list(range(len(R["names"]))) if who is None else who
    pay = R["pay"][:, ix, :].sum(1)
    fee = R["fee"][:, ix, :].sum(1)
    net = pay - fee
    cum = np.cumsum(net, axis=1)
    sunk = float(R["sunk"][:, ix].sum(1).mean())
    rows = []
    for m in range(MONTHS):
        rows.append({"m": m + 1, "from": dstr(m * MONTH), "to": dstr(m * MONTH + MONTH - 1), "cash_in": round(float(pay[:, m].mean()), 2),
                     "cash_out": round(float(fee[:, m].mean()), 2), "net": round(float(net[:, m].mean()), 2),
                     "net_p10": round(_pct(net[:, m], 10), 2), "net_p90": round(_pct(net[:, m], 90), 2),
                     "cum": round(float(cum[:, m].mean()), 2), "cum_p10": round(_pct(cum[:, m], 10), 2),
                     "cum_p50": round(_pct(cum[:, m], 50), 2), "cum_p90": round(_pct(cum[:, m], 90), 2),
                     "cum_min": round(float(cum[:, m].min()), 2), "cum_max": round(float(cum[:, m].max()), 2)})
    tot = {"cash_in": round(float(pay.sum(1).mean()), 2), "cash_out": round(float(fee.sum(1).mean()), 2), "net": round(float(net.sum(1).mean()), 2),
           "sunk_already_paid": round(sunk, 2), "net_after_sunk": round(float(net.sum(1).mean()) - sunk, 2),
           "best_p90": round(_pct(cum[:, -1], 90), 2), "worst_p10": round(_pct(cum[:, -1], 10), 2), "median": round(_pct(cum[:, -1], 50), 2),
           "worst_path": round(float(cum[:, -1].min()), 2), "best_path": round(float(cum[:, -1].max()), 2),
           "pct_paths_negative": round(100.0 * float((cum[:, -1] < 0).mean()), 1)}
    return {"months": rows, "total": tot}


def pass_stats(R, i):
    pk, fk = R["pass_k"][:, i], R["fail_k"][:, i]
    ok = pk >= 0

    def within(a, n):
        return round(100.0 * float(((a >= 0) & (a < n)).mean()), 1)
    # "within 10 sessions" = by the 10th session counted from the first (index 0..9); a month = 21
    return {"pass_2w": within(pk, 10), "fail_2w": within(fk, 10), "pass_m1": within(pk, 21), "fail_m1": within(fk, 21),
            "pass_m2": within(pk, 42), "median_pass_session": (float(np.median(pk[ok]) + 1) if ok.any() else None)}


def payout_stats(R, i):
    fp = R["first_pay"][:, i]
    ok = fp >= 0
    a = fp[ok]
    out = {"any_payout_12m_pct": round(100.0 * float(ok.mean()), 1)}
    for mm in (2, 3, 6):
        out[f"payout_by_m{mm}_pct"] = round(100.0 * float(((fp >= 0) & (fp < mm * MONTH)).mean()), 1)
    if len(a):
        out.update({"first_payout_session_p10": float(_pct(a, 10)), "first_payout_session_med": float(_pct(a, 50)),
                    "first_payout_session_p90": float(_pct(a, 90)), "first_payout_date_p10": dstr(_pct(a, 10)),
                    "first_payout_date_med": dstr(_pct(a, 50)), "first_payout_date_p90": dstr(_pct(a, 90))})
    out["owner_paid_12m_mean"] = round(float(R["counters"][:, i, 0].mean()), 2)
    out["graduated_pct"] = round(100.0 * float((R["counters"][:, i, 3] > 0).mean()), 1)
    out["breaches_12m_mean"] = round(float(R["counters"][:, i, 2].mean()), 2)
    return out


def payback(R, i):
    """Month in which the account's running total (everything it paid out minus everything it cost, its first eval price included
    even if already paid) is back above zero: for the average path and for the middle (median) path."""
    pay, fee = R["pay"][:, i, :], R["fee"][:, i, :] + R["sunk"][:, i][:, None] * np.eye(1, MONTHS, 0)
    cum = np.cumsum(pay - fee, axis=1)
    mean, med = cum.mean(0), np.median(cum, 0)

    def first(a):
        pos = np.where(a >= 0)[0]
        return int(pos[0] + 1) if len(pos) else None
    return {"payback_month_mean": first(mean), "payback_month_median": first(med),
            "paid_back_by_m3_pct": round(100.0 * float((cum[:, 2] >= 0).mean()), 1),
            "paid_back_by_m6_pct": round(100.0 * float((cum[:, 5] >= 0).mean()), 1),
            "paid_back_by_m12_pct": round(100.0 * float((cum[:, 11] >= 0).mean()), 1)}


def account_block(R, i, full=True):
    t = table(R, [i])
    o = {"name": R["names"][i], "label": LABEL.get(R["spec"][i][1], R["spec"][i][1]), "price": PRICE[SERKEY[R["spec"][i][1]]],
         "total": t["total"], "eval": pass_stats(R, i), "payouts": payout_stats(R, i), "payback": payback(R, i)}
    if full:
        o["monthly"] = [{"m": r["m"], "in": r["cash_in"], "out": r["cash_out"], "net": r["net"]} for r in t["months"]]
    return o


def scenario(R, full=True):
    t = table(R)
    out = dict(t) if full else {"total": t["total"]}
    out["accounts"] = [account_block(R, i, full) for i in range(len(R["names"]))]
    fp = R["first_pay"]
    anyfp = np.array([x[x >= 0].min() if (x >= 0).any() else -1 for x in fp])
    ok = anyfp >= 0
    if ok.any():
        a = anyfp[ok]
        out["first_payout_any"] = {"pct_paths": round(100.0 * float(ok.mean()), 1), "session_p10": float(_pct(a, 10)),
                                   "session_med": float(_pct(a, 50)), "session_p90": float(_pct(a, 90)), "date_p10": dstr(_pct(a, 10)),
                                   "date_med": dstr(_pct(a, 50)), "date_p90": dstr(_pct(a, 90)),
                                   "by_m1_pct": round(100.0 * float(((anyfp >= 0) & (anyfp < 21)).mean()), 1),
                                   "by_m2_pct": round(100.0 * float(((anyfp >= 0) & (anyfp < 42)).mean()), 1)}
    out["fails_12m"] = round(float(R["counters"][:, :, 2].sum(1).mean()), 2)
    out["evals_bought_12m"] = round(float((R["counters"][:, :, 1].sum(1) / 1.0).mean()), 2)
    return out


def specs():
    now = lambda key, rc=False, nm=None: (nm or key, key, 0, True, rc)  # already bought / running: the first price is sunk
    S = {
        "trio": [now("L50"), now("A25"), now("B25")],
        "trio_recycle": [now("L50", True), now("A25", True), now("B25", True)],
        "trio_fastlit": [now("L50f", False, "L50f"), now("A25"), now("B25")],
        "slot_atlas_copy": [now("L50"), now("A25"), now("A25b", False, "A25b")],
        "slot_lit25": [now("L50"), now("A25"), now("L25")],
        "duo_lit_atlas": [now("L50"), now("A25")],
    }
    for k in ("L50", "A25", "B25", "L25"):
        S["solo_" + k] = [(k, k, 0, True, False)]
    S["solo_A25b"] = [("A25b", "A25b", 0, True, False)]
    # the order of purchase, one a month, bills inside the window (nothing sunk), against buying all three on day 1
    S["buy_all_now"] = [(k, k, 0, False, False) for k in ("L50", "A25", "B25")]
    for perm in itertools.permutations(("L50", "A25", "B25")):
        S["order_" + "_".join(perm)] = [(k, k, MONTH * j, False, False) for j, k in enumerate(perm)]
    return S


def run_all(n_paths, seed=31, only=None):
    global SER0
    ser, n, split = series()
    SER0 = ser
    sets = {"H1": list(range(0, split - 5)), "H2": list(range(split, n - 5)), "2026": list(range(0, n - 5))}
    S = specs()
    res = {}
    for half in ("H1", "H2"):
        idxs = paths(sets[half], n_paths, seed)
        res[half] = {}
        for nm, sp in S.items():
            if only and nm not in only:
                continue
            t0 = time.time()
            R = simulate(sp, idxs)
            res[half][nm] = R
            print(f"{half} {nm:34s} net12 {table(R)['total']['net']:9.0f} ({time.time() - t0:.0f}s)", flush=True)
    return res, split, n


SER0 = {}
SER = {}


def reconcile(res, tol=0.01):
    """The totals must reconcile: for every path and account, payouts - fees (event by event) == the account's own books, and
    the month table's cash_in - cash_out == net, months add to the total, accounts add to the scenario, sunk fees = first prices."""
    bad = []
    for half, sc in res.items():
        for nm, R in sc.items():
            pay, fee, sunk, c = R["pay"], R["fee"], R["sunk"], R["counters"]
            if np.abs(pay.sum(2) - c[:, :, 0]).max() > tol:
                bad.append((half, nm, "payout events != account payouts"))
            if np.abs(fee.sum(2) + sunk - c[:, :, 1]).max() > tol:
                bad.append((half, nm, "fee events + sunk != account fees"))
            t = table(R)
            for r in t["months"]:
                if abs(r["cash_in"] - r["cash_out"] - r["net"]) > 0.02:
                    bad.append((half, nm, f"month {r['m']} in-out != net"))
            if abs(sum(r["net"] for r in t["months"]) - t["total"]["net"]) > 0.1:
                bad.append((half, nm, "months != total net"))
            if abs(t["months"][-1]["cum"] - t["total"]["net"]) > 0.1:
                bad.append((half, nm, "last running total != total net"))
            sc_ = scenario(R)
            if abs(sum(a["total"]["net"] for a in sc_["accounts"]) - t["total"]["net"]) > 0.1 * max(1, len(sc_["accounts"])):
                bad.append((half, nm, "accounts != scenario net"))
            if abs(t["total"]["cash_in"] - t["total"]["cash_out"] - t["total"]["net"]) > 0.02:
                bad.append((half, nm, "total in - out != net"))
            if nm == "trio" and abs(t["total"]["sunk_already_paid"] - (91.80 + 43.0 + 63.0)) > 0.01:
                bad.append((half, nm, "sunk fees != 91.80 + 43 + 63"))
            # a payout never exceeds the plan's cap: 5 x 80% x payout max, per account and per purchase
            for i, (_, key, *_r) in enumerate(R["spec"]):
                cap = MAX_PAY * SPLIT * PLANS[PLAN_OF[SERKEY[key]]]["pmax"]
                lives = 1 + c[:, i, 3] + c[:, i, 2]  # the account's purchases that could each pay up to the cap
                if (c[:, i, 0] > cap * lives + 1e-6).any():
                    bad.append((half, nm, f"{R['names'][i]} paid over its payout cap"))
    return bad


def check_json(path=OUT_P):
    d = json.load(open(path))
    bad = []
    for half in ("H1", "H2"):
        for nm, sc in d["scenarios"][half].items():
            ms = sc.get("months", [])
            for r in ms:
                if abs(r["cash_in"] - r["cash_out"] - r["net"]) > 0.02:
                    bad.append((half, nm, r["m"], "in - out != net"))
            if ms and abs(sum(r["net"] for r in ms) - sc["total"]["net"]) > 0.1:
                bad.append((half, nm, "months != total"))
            if ms and abs(ms[-1]["cum"] - sc["total"]["net"]) > 0.1:
                bad.append((half, nm, "running total != total"))
            if abs(sc["total"]["cash_in"] - sc["total"]["cash_out"] - sc["total"]["net"]) > 0.02:
                bad.append((half, nm, "total in - out != net"))
            if sc["accounts"]:
                if abs(sum(a["total"]["cash_in"] for a in sc["accounts"]) - sc["total"]["cash_in"]) > 0.1 * len(sc["accounts"]):
                    bad.append((half, nm, "accounts cash in != scenario"))
                if abs(sum(a["total"]["cash_out"] for a in sc["accounts"]) - sc["total"]["cash_out"]) > 0.1 * len(sc["accounts"]):
                    bad.append((half, nm, "accounts cash out != scenario"))
    base = d["scenarios"]["H2"]["trio"]["total"]
    if abs(base["net"] - base["cash_in"] + base["cash_out"]) > 0.02:
        bad.append(("verdict", "fees + payouts != net"))
    return bad


FULL = {"trio", "trio_recycle", "trio_fastlit", "slot_atlas_copy", "slot_lit25"}
SHORT = {"L50": "LIT 50K", "A25": "ATLAS 25K", "B25": "BLITZ 25K"}


def derive(d):
    """Plain-words answers computed from the stored scenarios: the verdict, the slot comparison, the buying order, the pass table."""
    S = d["scenarios"]

    def tot(h, nm):
        return S[h][nm]["total"]

    def acct(h, nm, name):
        return next(a for a in S[h][nm]["accounts"] if a["name"] == name)
    k = lambda x: ("-" if x < 0 else "") + f"${abs(x):,.0f}"
    t1, t2 = tot("H1", "trio"), tot("H2", "trio")
    fp1, fp2 = S["H1"]["trio"]["first_payout_any"], S["H2"]["trio"]["first_payout_any"]
    a1, a2 = acct("H1", "trio", "A25")["payouts"], acct("H2", "trio", "A25")["payouts"]
    l1, l2 = acct("H1", "trio", "L50")["payouts"], acct("H2", "trio", "L50")["payouts"]
    rec1, rec2 = tot("H1", "trio_recycle"), tot("H2", "trio_recycle")
    sk = t2["sunk_already_paid"]
    rb1 = {n: acct("H1", "trio_recycle", n)["total"]["net"] - acct("H1", "trio", n)["total"]["net"] for n in ("L50", "A25", "B25")}
    rb2 = {n: acct("H2", "trio_recycle", n)["total"]["net"] - acct("H2", "trio", n)["total"]["net"] for n in ("L50", "A25", "B25")}
    verdict = {
        "do_first": ("ATLAS on the 25K first: it is the first cash (typical first payout " + a2["first_payout_date_med"] + " conservative) and pays its price back in month "
                     + str(acct("H2", "solo_A25", "A25")["payback"]["payback_month_median"]) + ". Run all three accounts at once (LIT 50K, ATLAS 25K, BLITZ 25K): "
                     "buying all three on day 1 beats every staggered order, and the fees are only $198."),
        "then": ("LIT on the 50K second: the biggest total (" + k(acct("H2", "trio", "L50")["total"]["net"]) + " in 12 months) but its first payout is later. BLITZ is the weakest of the three "
                 "(" + k(acct("H2", "trio", "B25")["total"]["net"]) + "): a second ATLAS or a LIT copy would earn more in that slot. When an account has been paid its 5th payout "
                 "(it then moves to a live account), buy the next ATLAS 25K eval ($43) first: a re-buy adds "
                 + k(rb2["A25"]) + " (conservative) in the year, against " + k(rb2["L50"]) + " for LIT and " + k(rb2["B25"]) + " for BLITZ."),
        "first_payout": (f"First payout from any account: typical {fp2['date_med']} (conservative, Jul-Oct) to {fp1['date_med']} (Jan-Jun); "
                         f"1 in 10 paths already by {fp1['date_p10']} / {fp2['date_p10']}, 9 in 10 by {fp1['date_p90']} / {fp2['date_p90']}. It comes from ATLAS "
                         f"(typical {a2['first_payout_date_med']} conservative, {a1['first_payout_date_med']} Jan-Jun); LIT on the 50K comes later "
                         f"(typical {l2['first_payout_date_med']} / {l1['first_payout_date_med']})."),
        "month12": (f"Cash to the owner by month 12 ({d['month_labels'][-1]['to']}), after every fee including the {k(sk)} already paid for the three evals: "
                    f"conservative (Jul-Oct) middle path {k(t2['median'] - sk)}, worst case (1 path in 10) {k(t2['worst_p10'] - sk)}, best case (1 in 10) {k(t2['best_p90'] - sk)}; "
                    f"Jan-Jun version middle {k(t1['median'] - sk)}, worst {k(t1['worst_p10'] - sk)}, best {k(t1['best_p90'] - sk)}. "
                    f"The worst of all {d['paths_per_half']:,} sampled paths still ends at {k(t2['worst_path'] - sk)} (H2); no path ends below $0."
                    if t2["pct_paths_negative"] == 0 else "see the table"),
        "with_recycle": (f"If the owner buys a new eval each time an account has been paid 5 times: {k(rec2['median'] - sk)} middle path conservative "
                         f"({k(rec2['worst_p10'] - sk)} worst / {k(rec2['best_p90'] - sk)} best), {k(rec1['median'] - sk)} Jan-Jun."),
        "rebuy_adds": {"H1": {n: round(v) for n, v in rb1.items()}, "H2": {n: round(v) for n, v in rb2.items()}},
        "caps": ("The money is front-loaded: each account stops paying after 5 payouts (5 x $1,000 x 80% = $4,000 on a 25K, 5 x $2,000 x 80% = $8,000 "
                 "on the 50K, then it moves to a live account that this table does not count), so months 8-12 fall off unless a new eval is bought."),
    }
    slot = {}
    for h in ("H1", "H2"):
        rows = []
        for nm, lab in (("trio", "BLITZ on the 2nd 25K (the plan)"), ("slot_atlas_copy", "a 2nd ATLAS on the 2nd 25K"),
                        ("slot_lit25", "a LIT copy on the 2nd 25K")):
            t = tot(h, nm)
            third = S[h][nm]["accounts"][2]
            rows.append({"slot": lab, "scenario": nm, "net12": t["net"], "median": t["median"], "worst_p10": t["worst_p10"],
                         "best_p90": t["best_p90"], "slot_net12": third["total"]["net"], "slot_first_payout": third["payouts"].get("first_payout_date_med"),
                         "slot_payback_median": third["payback"]["payback_month_median"], "paid_back_by_m3_pct": third["payback"]["paid_back_by_m3_pct"]})
        slot[h] = rows
    solo = {}
    for h in ("H1", "H2"):
        solo[h] = []
        for nm, lab in (("solo_A25", "ATLAS 25K"), ("solo_L50", "LIT 50K"), ("solo_L25", "LIT copy 25K"), ("solo_B25", "BLITZ 25K")):
            a = S[h][nm]["accounts"][0]
            solo[h].append({"account": lab, "price": a["price"], "net12": a["total"]["net"], "first_payout_med": a["payouts"].get("first_payout_date_med"),
                            "payback_month_median": a["payback"]["payback_month_median"], "payback_month_mean": a["payback"]["payback_month_mean"],
                            "paid_back_by_m3_pct": a["payback"]["paid_back_by_m3_pct"], "paid_back_by_m6_pct": a["payback"]["paid_back_by_m6_pct"]})
    order = {}
    for h in ("H1", "H2"):
        rows = []
        for nm, v in S[h].items():
            if nm.startswith("order_") or nm == "buy_all_now":
                t = v["total"]
                fp = v.get("first_payout_any", {})
                lab = "all three on day 1" if nm == "buy_all_now" else ", then ".join(SHORT[x] for x in nm[6:].split("_")) + " (one a month)"
                rows.append({"order": lab, "net12": t["net"], "worst_p10": t["worst_p10"], "best_p90": t["best_p90"], "first_payout_med": fp.get("date_med")})
        rows.sort(key=lambda r: -r["net12"])
        order[h] = rows
    passes = {}
    for h in ("H1", "H2"):
        passes[h] = []
        for name, lab in (("L50", "LIT 50K"), ("A25", "ATLAS 25K"), ("B25", "BLITZ 25K")):
            e = acct(h, "trio", name)["eval"]
            pub = PUBLISHED_2W[name][h]
            passes[h].append({"account": lab, "model_pass_2w": e["pass_2w"], "model_fail_2w": e["fail_2w"], "model_pass_m1": e["pass_m1"],
                              "model_fail_m1": e["fail_m1"], "published_pass_2w": pub[0], "published_fail_2w": pub[1]})
        e = acct(h, "trio_fastlit", "L50f")["eval"]
        passes[h].append({"account": "LIT 50K, eval sized as the engine study", "model_pass_2w": e["pass_2w"], "model_fail_2w": e["fail_2w"],
                          "model_pass_m1": e["pass_m1"], "model_fail_m1": e["fail_m1"], "published_pass_2w": PUBLISHED_2W["L50"][h][0],
                          "published_fail_2w": PUBLISHED_2W["L50"][h][1]})
    return {"verdict": verdict, "slot": slot, "single_account": solo, "order": order, "eval_pass": passes}


def build(n_paths=3000):
    res, split, n = run_all(n_paths)
    bad = reconcile(res)
    if bad:
        raise SystemExit("RECONCILIATION FAILED: " + json.dumps(bad[:10]))
    out = {"title": "Money roadmap, next 12 months", "updated": "2026-11-04", "paths_per_half": n_paths,
           "how": ("Lifecycle Monte Carlo (tools/money_roadmap.py): 5-session blocks of the real 2026 sessions, 21 sessions = 1 model month, "
                   "one sample drives all accounts together. Cash in = payouts to the owner at the MFFU 80% split; cash out = eval fees at the "
                   "owner's real prices ($91.80 / $63 / $43, $0 activation) and the new eval every breach buys (reset fee unknown: priced as a "
                   "new eval). The three evals running now are already paid ('sunk'), so they are not in the cash out. "
                   "H1 = Jan-Jun 2026 (pick half), H2 = Jul-Oct 2026 (check half). H2 is the conservative one."),
           "conservative": "H2", "sessions": n, "split_session": split, "first_session": dstr(0), "prices": PRICE,
           "published_pass_2w": {k: {h: {"pass": v[0], "fail": v[1]} for h, v in vv.items()} for k, vv in PUBLISHED_2W.items()},
           "month_labels": [{"m": m + 1, "from": dstr(m * MONTH), "to": dstr(m * MONTH + MONTH - 1)} for m in range(MONTHS)],
           "scenarios": {h: {nm: scenario(R, nm in FULL) for nm, R in sc.items()} for h, sc in res.items()}}
    out.update(derive(out))
    os.makedirs(os.path.dirname(OUT_P), exist_ok=True)
    json.dump(out, open(OUT_P, "w"), separators=(",", ":"))
    bad = check_json()
    if bad:
        raise SystemExit("JSON CHECK FAILED: " + json.dumps(bad[:10]))
    print("written", OUT_P, os.path.getsize(OUT_P), "bytes; reconciliation OK")
    report()


MD_P = os.path.join(ROOT, "research", "writeups", "2026-11-04_money_roadmap.md")


def report(path=OUT_P, md_path=MD_P):
    """Write the plain-words write-up from the stored roadmap.json, so the text and the file can never disagree."""
    d = json.load(open(path))
    d.update(derive(d))  # refresh the plain-words answers from the stored scenarios
    json.dump(d, open(path, "w"), separators=(",", ":"))
    S, V = d["scenarios"], d["verdict"]
    m = lambda x: ("-" if x < 0 else "") + f"${abs(x):,.0f}"
    L = []
    w = L.append
    w("# Money roadmap: the next 12 months (2026-11-04)")
    w("")
    w("Research and display only. Nothing live was touched. Numbers: `tools/money_roadmap.py` -> `research/props/roadmap.json` "
      f"({d['paths_per_half']:,} sampled 12-month paths per half). Two versions of every number: **Jan-Jun 2026 (H1)** and **Jul-Oct 2026 (H2)**. "
      "**H2 is the conservative one: quote H2.**")
    w("")
    w("## Verdict")
    w("")
    w(f"- **Do first:** {V['do_first']}")
    w(f"- **Then:** {V['then']}")
    w(f"- **Expected first payout:** {V['first_payout']}")
    w(f"- **Best case / worst case by month 12:** {V['month12']}")
    w(f"- **With re-buying:** {V['with_recycle']}")
    w(f"- **Why it fades:** {V['caps']}")
    w("")
    w("## Month by month, all three accounts (cash to the owner after the 80% split, fees at his real prices)")
    w("")
    w("| Month | Dates | Payouts in (H2) | Fees out (H2) | Net (H2) | Running total H2 (average; worst 1-in-10 to best 1-in-10) | Running total H1 (average) |")
    w("|---|---|---|---|---|---|---|")
    h2, h1 = S["H2"]["trio"]["months"], S["H1"]["trio"]["months"]
    for a, b in zip(h2, h1):
        w(f"| {a['m']} | {a['from'][5:]} to {a['to'][5:]} | {m(a['cash_in'])} | {m(a['cash_out'])} | {m(a['net'])} | "
          f"{m(a['cum'])} ({m(a['cum_p10'])} to {m(a['cum_p90'])}) | {m(b['cum'])} |")
    t2, t1 = S["H2"]["trio"]["total"], S["H1"]["trio"]["total"]
    w(f"| **12 months** | | **{m(t2['cash_in'])}** | **{m(t2['cash_out'])}** | **{m(t2['net'])}** | middle path {m(t2['median'])}, worst {m(t2['worst_p10'])}, best {m(t2['best_p90'])} | "
      f"{m(t1['net'])} (middle {m(t1['median'])}, worst {m(t1['worst_p10'])}, best {m(t1['best_p90'])}) |")
    sk = t2["sunk_already_paid"]
    w(f"| **after the {m(sk)} already paid** | | | | **{m(t2['net'] - sk)}** | middle {m(t2['median'] - sk)}, worst {m(t2['worst_p10'] - sk)}, best {m(t2['best_p90'] - sk)} | "
      f"{m(t1['net'] - sk)} (middle {m(t1['median'] - sk)}) |")
    w("")
    w(f"Check: payouts {m(t2['cash_in'])} - fees {m(t2['cash_out'])} = net {m(t2['net'])} (H2); the three evals now running "
      f"({m(t2['sunk_already_paid'])}: 91.80 + 43 + 63) are already paid and are not counted as cash out. "
      "A negative worst case in months 1-2 is a reset (a new eval) before any payout.")
    w("")
    w("## By account (12 months, average path)")
    w("")
    w("| Account | Payouts in H2 / H1 | Fees H2 / H1 | Net H2 / H1 | First payout, typical H2 / H1 | Chance of a payout by month 3 H2 / H1 |")
    w("|---|---|---|---|---|---|")
    for a2, a1 in zip(S["H2"]["trio"]["accounts"], S["H1"]["trio"]["accounts"]):
        w(f"| {a2['label']} | {m(a2['total']['cash_in'])} / {m(a1['total']['cash_in'])} | {m(a2['total']['cash_out'])} / {m(a1['total']['cash_out'])} | "
          f"{m(a2['total']['net'])} / {m(a1['total']['net'])} | {a2['payouts'].get('first_payout_date_med')} / {a1['payouts'].get('first_payout_date_med')} | "
          f"{a2['payouts']['payout_by_m3_pct']}% / {a1['payouts']['payout_by_m3_pct']}% |")
    w("")
    w("## Chance each account passes its eval: in 2 weeks and by the end of month 1")
    w("")
    w("| Account | 2 weeks, published engine study (pass / fail) H2 | H1 | Model: 2 weeks H2 | Model: month 1 H2 | Model: month 1 H1 |")
    w("|---|---|---|---|---|---|")
    for a, b in zip(d["eval_pass"]["H2"], d["eval_pass"]["H1"]):
        w(f"| {a['account']} | {a['published_pass_2w']}% / {a['published_fail_2w']}% | {b['published_pass_2w']}% / {b['published_fail_2w']}% | "
          f"{a['model_pass_2w']}% / {a['model_fail_2w']}% | {a['model_pass_m1']}% / {a['model_fail_m1']}% | {b['model_pass_m1']}% / {b['model_fail_m1']}% |")
    w("")
    w("The published 2-week figures come from the engine-faithful eval studies (the ones on Plutus). The month-1 figures come from the roadmap's "
      "daily model, which is rougher: it passes LIT more slowly than the engine study and fails ATLAS more often (25% vs 0%, a $43 re-buy each). "
      "So the roadmap is **slow on LIT cash, harsh on ATLAS fails**. The row 'eval sized as the engine study' shows LIT when its eval is risked as the study does.")
    w("")
    w("## Which account to buy (each one alone), and the payback month")
    w("")
    w("| Account (price) | Net in 12 months H2 / H1 | First payout, typical H2 / H1 | Paid back by month 3, H2 / H1 | Payback month (typical path) H2 / H1 |")
    w("|---|---|---|---|---|")
    for a, b in zip(d["single_account"]["H2"], d["single_account"]["H1"]):
        w(f"| {a['account']} (${a['price']:.2f}) | {m(a['net12'])} / {m(b['net12'])} | {a['first_payout_med']} / {b['first_payout_med']} | "
          f"{a['paid_back_by_m3_pct']}% / {b['paid_back_by_m3_pct']}% | month {a['payback_month_median']} / month {b['payback_month_median']} |")
    w("")
    w("Payback = the month the account's running total (everything paid out minus its price and any re-buys) is above zero on the typical path.")
    w("")
    w("## The second 25K: BLITZ, a second ATLAS, or a LIT copy? (LIT 50K + ATLAS 25K + this)")
    w("")
    w("| Second 25K | 12-month net, all three H2 / H1 | Worst 1-in-10 H2 | That account alone, net H2 / H1 | Its payback month H2 |")
    w("|---|---|---|---|---|")
    for a, b in zip(d["slot"]["H2"], d["slot"]["H1"]):
        w(f"| {a['slot']} | {m(a['net12'])} / {m(b['net12'])} | {m(a['worst_p10'])} | {m(a['slot_net12'])} / {m(b['slot_net12'])} | month {a['slot_payback_median']} |")
    w("")
    w("A second ATLAS or a LIT copy beats BLITZ in both halves on money, because BLITZ is the slowest and smallest payer. "
      "BLITZ is still the only one that is not the same bet twice (its days are about 0 / -0.06 correlated with ATLAS / LIT; a copy of ATLAS is the same days). "
      "Not checked: whether MFFU lets one trader run the same strategy on two of his own accounts; check the rules before buying a copy.")
    w("")
    w("## Does the order of buying matter? (one a month, nothing already paid)")
    w("")
    w("| Order | 12-month net H2 | Worst 1-in-10 H2 | 12-month net H1 |")
    w("|---|---|---|---|")
    h1o = {r["order"]: r for r in d["order"]["H1"]}
    for r in d["order"]["H2"]:
        w(f"| {r['order']} | {m(r['net12'])} | {m(r['worst_p10'])} | {m(h1o[r['order']]['net12'])} |")
    w("")
    bo2 = d["order"]["H2"]
    allnow = next(r for r in bo2 if r["order"].startswith("all three"))
    others = [r for r in bo2 if r is not allnow]
    bo1 = d["order"]["H1"]
    allnow1 = next(r for r in bo1 if r["order"].startswith("all three"))
    others1 = [r for r in bo1 if r is not allnow1]
    w(f"All three on day 1 is the best in both halves: waiting costs {m(allnow['net12'] - others[0]['net12'])} to {m(allnow['net12'] - others[-1]['net12'])} "
      f"over the year (H2), {m(allnow1['net12'] - others1[0]['net12'])} to {m(allnow1['net12'] - others1[-1]['net12'])} (H1). Fees are so small ($198 for the three) "
      f"that cash on hand never decides the order. If one had to wait, the best staggered order in both halves is **{others[0]['order'].split(' (')[0]}**: "
      "the slow payers get the head start, and ATLAS, which finishes its 5 payouts fastest, loses least by waiting.")
    w("")
    w("## When an account finishes its 5 payouts: what a re-buy is worth (12 months)")
    w("")
    w("| Re-buy a new eval for | Adds in 12 months H2 (conservative) / H1 | Price |")
    w("|---|---|---|")
    for n_, lab in (("A25", "ATLAS 25K"), ("L50", "LIT 50K"), ("B25", "BLITZ 25K")):
        w(f"| {lab} | {m(V['rebuy_adds']['H2'][n_])} / {m(V['rebuy_adds']['H1'][n_])} | ${d['prices'][n_]:.2f} |")
    w("")
    w("A re-buy only pays if the new account can finish inside the year: ATLAS (first payout in about 5 to 6 weeks) fits twice; LIT on the 50K and BLITZ rarely finish a second round "
      "inside the year, so a re-buy there pays mostly in year 2. The sum, with every re-buy: see 'With re-buying' in the verdict.")
    w("")
    w("## What to trust, and what not")
    w("")
    w("- **Daily model.** One P&L per session, the same funded rules as `tools/second_plan.py` (80% split, payout floor and cap, 2 trading days a cycle, best day <= 50% of the cycle, "
      "5 payouts then live). Its first six months match what is already published (`sn_plan.json`: $1,532 H1 / $1,136 H2 a month; this run: "
      f"{m(S['H1']['trio']['months'][5]['cum'] / 6)} / {m(S['H2']['trio']['months'][5]['cum'] / 6)} a month), but spread over 12 months it fades as accounts reach 5 payouts.")
    w("- **Live accounts are not counted.** After the 5th payout an account moves to a live account (Blue Row Capital); its later payouts are not in these numbers. Re-buying is shown as a separate line.")
    w("- **Reset fee unknown** (no price published for one-time plans): a breach is priced as a new eval at his real price.")
    w("- **Only 2026 data**: six months to pick on (Jan-Jun) and four to check on (Jul-Oct), in 5-session blocks. H2 is the lower of the two versions, not a guaranteed floor. "
      "Paper only; no payout is ever requested by this code.")
    w("- BLITZ here uses the stored funded size ($150 a trade, a day capped at +$400). The later-break size fix proposed in the BLITZ study is not applied (untested here), so BLITZ may be understated.")
    w("- The model passes the LIT eval more slowly than the engine study (see the pass table), so LIT's first payout is later here than in `lit_funded_firms` (about 40 sessions from purchase there).")
    w("")
    w("## Next steps (owner)")
    w("")
    w("1. Run LIT, ATLAS and BLITZ together now; nothing to buy until an account has been paid 5 times.")
    w("2. When an account is paid its 5th payout, buy the next ATLAS 25K eval ($43) first.")
    w("")
    w("Where it shows: Plutus, Plan tab, 'Money plan' card (`tools/web_public/plutus/roadmap.json`, made by `report`); Ledger, Break-even tracker, 'Expected vs actual cash so far this year'.")
    w("")
    w("3. Re-run `python -X utf8 tools/money_roadmap.py` after the 2026 data grows; check with `python -X utf8 -m tests.test_money_roadmap`.")
    open(md_path, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("wrote", md_path)
    write_compact(d)


PUB_P = os.path.join(ROOT, "tools", "web_public", "plutus", "roadmap.json")
PUB_JS = os.path.join(ROOT, "tools", "web_public", "plutus", "roadmapfallback.js")
SHORT_ID = {"L50": "lit50", "A25": "atlas25", "B25": "blitz25"}
SHORT_NAME = {"L50": "LIT on the 50K", "A25": "ATLAS on a 25K", "B25": "BLITZ on a 25K"}
CAVEATS = [
    "These are study numbers from 2026 paper results. They are not promises.",
    "The Jul-Oct version is the conservative one. Look at it first; Jan-Jun is the better half.",
    "Check the MFFU rules before copying a strategy to a second account. This plan did not check whether the firm allows it.",
    "After the 5th payout an account moves to a live account. Its later payouts are not counted here, so the money fades after month 6.",
    "MFFU publishes no reset price for these plans, so a failed eval is priced as a new eval at your real price ($91.80, $63 or $43).",
    "The $198 for the three evals now running is already paid. Months show cash from today.",
    "LIT pays later here than in the engine study, because this plan's eval model passes LIT more slowly. ATLAS fails more evals here than in the engine study.",
    "The worst case is 1 path in 10, not the floor. Drawdown left on each account decides whether an eval survives; a breach costs a new eval.",
]


def compact(d):
    """The small published file for the Plutus 'Money plan' card and the Ledger's expected-vs-actual line (< 25 KB): the verdict sentence,
    12 monthly rows for Jul-Oct (conservative) and Jan-Jun, first-payout ranges, payback months, the order of buying, a sentence for each month
    and the caveats in plain words. Everything is read from the stored roadmap.json, so it can never disagree with it."""
    S, V = d["scenarios"], d["verdict"]
    sk = S["H2"]["trio"]["total"]["sunk_already_paid"]
    ver = {}
    for h, lab in (("H2", "Jul-Oct (conservative)"), ("H1", "Jan-Jun")):
        sc = S[h]["trio"]
        t = sc["total"]
        ver[h] = {"label": lab, "mid": round(t["median"] - sk), "lo": round(t["worst_p10"] - sk), "hi": round(t["best_p90"] - sk), "avg": round(t["net"] - sk),
                  "in": round(t["cash_in"]), "out": round(t["cash_out"]), "worst_path": round(t["worst_path"] - sk),
                  "months": [{"m": r["m"], "from": r["from"], "to": r["to"], "in": round(r["cash_in"]), "out": round(r["cash_out"]), "net": round(r["net"]),
                              "cum": round(r["cum"]), "lo": round(r["cum_p10"]), "hi": round(r["cum_p90"])} for r in sc["months"]]}
    accts = []
    for name in ("A25", "L50", "B25"):
        row = {"id": SHORT_ID[name], "label": SHORT_NAME[name], "price": PRICE[name]}
        for h in ("H2", "H1"):
            a = next(x for x in S[h]["trio"]["accounts"] if x["name"] == name)
            p = a["payouts"]
            row[h] = {"net12": round(a["total"]["net"]), "first": [p.get("first_payout_date_p10"), p.get("first_payout_date_med"), p.get("first_payout_date_p90")],
                      "by_m3": p.get("payout_by_m3_pct"), "payback": a["payback"]["payback_month_median"], "paid_back_m3": a["payback"]["paid_back_by_m3_pct"]}
        accts.append(row)
    order = {"best": "Buy all three on day 1.", "rebuy": V["rebuy_adds"], "wait_cost": {}, "if_waiting": {}, "second_25k": {}}
    for h in ("H2", "H1"):
        rows = d["order"][h]
        allnow = next(r for r in rows if r["order"].startswith("all three"))
        others = [r for r in rows if r is not allnow]
        order["wait_cost"][h] = [round(allnow["net12"] - others[0]["net12"]), round(allnow["net12"] - others[-1]["net12"])]
        order["if_waiting"][h] = others[0]["order"].split(" (")[0]
        order["second_25k"][h] = [{"slot": r["slot"], "net12": round(r["net12"]), "alone": round(r["slot_net12"])} for r in d["slot"][h]]
    a_h2 = accts[0]["H2"]
    fp = S["H2"]["trio"]["first_payout_any"]
    fp1 = S["H1"]["trio"]["first_payout_any"]
    k = lambda x: ("-" if x < 0 else "") + f"${abs(x):,.0f}"
    headline = (f"Run ATLAS first, then LIT, all three accounts now. First payout about {fp['date_med']} (conservative) or {fp1['date_med']} (Jan-Jun). "
                f"By month 12: {k(ver['H2']['mid'])} in the conservative version (worst {k(ver['H2']['lo'])}, best {k(ver['H2']['hi'])}), {k(ver['H1']['mid'])} in Jan-Jun.")
    todo = []
    first_txt = f"{a_h2['first'][0]} to {a_h2['first'][2]}"
    for m in range(1, MONTHS + 1):
        if m == 1:
            todo.append(f"Run LIT, ATLAS and BLITZ together. Nothing to buy. The first ATLAS payout is expected {first_txt}.")
        elif m == 2:
            todo.append(f"Keep all three trading. Request the first ATLAS payout once it reaches its payout floor ({first_txt} is the range). A failed eval costs a new one.")
        elif m <= 6:
            todo.append("Request payouts as each account reaches its floor. When an account has had its 5th payout, buy the next ATLAS 25K eval ($43) first.")
        else:
            todo.append("Payouts fade as accounts finish their 5. Re-buy ATLAS 25K first, then LIT 50K, then BLITZ 25K, as each one finishes.")
    return {"v": 1, "title": "Money plan", "updated": d["updated"], "source": "research/props/roadmap.json (tools/money_roadmap.py)", "conservative": "H2",
            "first_session": d["first_session"], "paid_already": round(sk, 2), "headline": headline, "verdict": {x: V[x] for x in ("do_first", "then", "first_payout", "month12", "with_recycle", "caps")},
            "versions": ver, "accounts": accts, "order": order, "todo": todo, "caveats": CAVEATS,
            "eval_2w": {x["account"]: [x["published_pass_2w"], x["published_fail_2w"]] for x in d["eval_pass"]["H2"][:3]}}


def write_compact(d):
    c = compact(d)
    os.makedirs(os.path.dirname(PUB_P), exist_ok=True)
    txt = json.dumps(c, separators=(",", ":"), ensure_ascii=True)
    open(PUB_P, "w", encoding="utf-8").write(txt + "\n")
    open(PUB_JS, "w", encoding="utf-8").write(
        "// GENERATED by python -X utf8 tools/money_roadmap.py (do not edit): the offline copy of roadmap.json, shown with an OFFLINE COPY tag when the file cannot be read.\n"
        "export const FALLBACK = " + txt + ";\n")
    size = os.path.getsize(PUB_P)
    if size >= 25_000:
        raise SystemExit(f"compact roadmap.json too big: {size} bytes")
    print("wrote", PUB_P, size, "bytes and", PUB_JS)
    return c


def check(n_paths=150):
    res, _s, _n = run_all(n_paths, seed=5, only={"trio", "trio_recycle", "slot_lit25", "solo_A25", "buy_all_now", "order_B25_A25_L50"})
    bad = reconcile(res)
    if os.path.exists(OUT_P):
        bad += check_json()
    print("RECONCILES" if not bad else "MISMATCH " + json.dumps(bad[:10]))
    return bad


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        sys.exit(1 if check() else 0)
    if len(sys.argv) > 1 and sys.argv[1] == "report":
        report()
        sys.exit(0)
    build(int(os.environ.get("ROADMAP_PATHS", "3000")))
