"""Funded-phase money from the payout rules, without changing a trade (owner order 2026-10-26, item 2). Write-up:
research/writeups/payout-policy.md. Numbers: research/lab/payout_policy.json. Paper research only: no live file changes.

Already settled (not redone, re-confirmed here on the LIVE funded sizing): the owner's $1,500-above-the-buffer ask line
(uprisk.md "asks": best of $500 / $1,000 / $1,500 / $2,000 over 6 months), the $2,000 winner cap (live), cons_aware
(funded-path.md / uprisk.md: -$56 to -$92 a month), "harvest" (1 micro once the next request is banked: rejected).

New here, on the owner's copied stack (MFFU Builder 50K + 2 x 25K + 4 x 50K-type at LucidPro / FundedNext, MFFU 50K rules
as the proxy as in uprisk.md; all LIT, live eval + funded sizing, bought a week apart, 12 months, the same market path):
  1. lifetime ask line  the ask line over 12 months (an MFFU account pays at most 5 requests, so a small request wastes
                        one of the five): $1,500 (today) vs $2,000 (only full requests) vs $1,000
  2. stack reserve      at most m payouts a calendar month across the stack; a ready account over the limit waits (its
                        cycle goes on) and asks in a month nobody else could: does it cut the months with no payout?
  3. pre-buy            buy the replacement eval when an account takes its 4th payout (MFFU ends a sim account after 5,
                        LucidPro / FundedNext after 5 too) instead of after the 5th, so the next funded account is ready
                        when this one leaves. MFFU holds 1 sim-funded Builder 50K per person: a pre-bought eval that passes
                        early waits (no trades) until the old account is gone - check with MFFU before using it there.
  4. cons_aware         re-checked on the live funded sizing (true / "after_payout").

Engines: tools/uprisk.py Eval / Funded (bit for bit engine/sizing + engine/funded_life), stepped together session by session
by tools/payout_policy.Stack; the funded payout decision goes through a gate (policy) instead of "always ask when ready".

    python -X utf8 tools/payout_policy.py [--n 1000]        -> research/lab/payout_policy.json
    python -X utf8 tools/payout_policy.py combo [--n 1000]  # + eval two_week after 10, pre-buy and the NA add-on together
"""
from __future__ import annotations

import collections
import copy
import datetime as dt
import json
import math
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import uprisk as U  # noqa: E402
from engine import funded_life as FL  # noqa: E402

OUT = os.path.join(ROOT, "research", "lab", "payout_policy.json")
SPANS = ("H1", "H2", "REF")
PRICE = {"builder50k": 91.80, "builder25k": 63.00}
PV, COMM, SLIP = 2.0, 1.90, 0.25


class GFunded(U.Funded):
    """uprisk.Funded whose payout goes through gate(account, amount) -> bool (False = wait; the cycle goes on)."""

    gate = None

    def step(self, ts, keep=None):
        if self.state != "on":
            return None, None
        A, P = self.A, self.P
        day = U.cal(self.k)
        self.k += 1
        st0, cyc = self._fast_state()
        cum = 0.0
        for t in ts:
            if cum <= -A["dll"]:
                break
            room = round(st0["balance"] + cum - st0["floor"], 2)
            st = {"room": room, "cum": cum, "locked": st0["floor"] >= A["lock"] - 1e-9, "bal": st0["balance"], **cyc}
            q = self.qty(t, st)
            if q <= 0:
                continue
            self.n_tr += 1
            pnl = t["pts"] * PV * q - COMM * q
            low = min(0.0, t["w1"] * PV * q - COMM * q, pnl)
            self.max_risk = max(self.max_risk, (t["risk"] + SLIP) * PV * q + COMM * q)
            if cum + low <= -A["dll"]:
                pnl = -A["dll"] - cum - SLIP * PV * q
                low = pnl
            if st0["balance"] + cum + low <= st0["floor"]:
                lossd = st0["floor"] - st0["balance"]
                self.days[day] = round(lossd, 2)
                self.trade_pnl += lossd
                self.state = "lost"
                return "lost", None
            cum += pnl
        if abs(cum) > 1e-9:
            self.days[day] = round(cum, 2)
            self.trade_pnl += cum
            self.bal += round(cum, 2)
            self.cyc.append(round(cum, 2))
            if self.first_trade is None:
                self.first_trade = day
                self.elig_from = FL._next_weekday(FL._add_days(day, int(math.ceil(P["first_wait_h"] / 24.0))))
        self.peak = max(self.peak, self.bal)
        self.floor = min(max(self.floor, self.peak - A["mll"]), A["lock"])
        tr = self._fast_track(day)
        if tr["status"] == "ready" and (self.gate is None or self.gate(self, tr["max_request"])):
            amt = tr["max_request"]
            self.pays[day] = amt
            self.paid += amt
            self.bal -= amt
            self.cyc_start_bal = self.bal
            self.cyc = []
            if len(self.pays) >= P["max_payouts"]:
                self.state = "grad"
                return "grad", amt * P["split"]
            return "paid", amt * P["split"]
        return None, None


class Slot:
    """One account slot: eval -> 2 sessions -> funded -> lost / 5 payouts -> the next eval (or a pre-bought one)."""

    def __init__(self, plan, ecfg, fcfg, price, ask=None, prebuy_at=None):
        self.plan, self.ecfg, self.fcfg, self.price, self.ask, self.prebuy_at = plan, ecfg, fcfg, price, ask, prebuy_at
        self.cost, self.owner, self.evals = price, 0.0, 1
        self.e, self.f, self.wait = U.Eval(ecfg, plan), None, 0
        self.pre = None                   # a pre-bought eval running next to the funded account
        self.pre_passed = False
        self.pays = []
        self.lost = self.grads = 0

    def _new_eval(self):
        self.cost += self.price
        self.evals += 1
        return U.Eval(self.ecfg, self.plan)

    def step(self, ts, g, gate):
        if self.f is None and self.wait == 0:
            r = self.e.step(ts)
            if r == "pass":
                self.wait = U.GAP
            elif r in ("fail", "stuck", "reset"):
                self.e = self._new_eval()
            return
        if self.f is None:
            self.wait -= 1
            if self.wait == 0:
                self.f = GFunded(self.plan, self.fcfg, self.ask)
                self.f.gate = gate
            return
        # a pre-bought eval trades the same signals next to the funded account until it passes (then it waits)
        if self.pre is not None and not self.pre_passed:
            r = self.pre.step(ts)
            if r == "pass":
                self.pre_passed = True
            elif r in ("fail", "stuck", "reset"):
                self.pre = self._new_eval()
        ev, x = self.f.step(ts)
        if ev in ("paid", "grad"):
            self.owner += x
            self.pays.append((g + 1, x))
            if self.prebuy_at and ev == "paid" and len(self.f.pays) == self.prebuy_at and self.pre is None:
                self.pre = self._new_eval()
        if ev in ("lost", "grad"):
            self.lost += ev == "lost"
            self.grads += ev == "grad"
            self.f = None
            if self.pre is not None:
                if self.pre_passed:
                    self.wait = U.GAP          # the waiting eval becomes the next funded account
                else:
                    self.e = self.pre          # keep trading the pre-bought eval
                self.pre, self.pre_passed = None, False
            else:
                self.e = self._new_eval()


def run_stack(BY, P, slots, offset=5, horizon=252, policy=None):
    """slots: [(plan, ecfg, fcfg, price, ask, prebuy_at)]; policy: None | {"max_per_month": m}. -> per-path rows."""
    M = horizon // 21
    rows = []
    for seq in P:
        S = [Slot(*s) for s in slots]
        month_paid = collections.Counter()
        g_now = [0]

        def gate(acct, amt):
            if not policy:
                return True
            m = g_now[0] // 21
            if month_paid[m] >= policy["max_per_month"]:
                return False
            month_paid[m] += 1
            return True
        L = horizon + offset * (len(S) - 1)
        for g in range(L):
            g_now[0] = g
            for j, sl in enumerate(S):
                if g < offset * j or g >= offset * j + horizon:
                    continue
                sl.step(BY[seq[g]], g, gate)
        pm = np.zeros(M)
        for sl in S:
            for k, x in sl.pays:
                m = (k - 1) // 21
                if m < M:
                    pm[m] += x
        rows.append({"net": sum(s.owner - s.cost for s in S), "owner": sum(s.owner for s in S), "cost": sum(s.cost for s in S),
                     "pm": pm, "evals": sum(s.evals for s in S), "lost": sum(s.lost for s in S), "grads": sum(s.grads for s in S),
                     "pays": sum(len(s.pays) for s in S)})
    return rows


def summarise(rows, horizon=252):
    n = len(rows)
    mo = horizon / 21.0
    net = np.array([r["net"] for r in rows])
    pm = np.array([r["pm"] for r in rows])
    z = pm[:, 3:] <= 0
    dry3 = np.mean([any(zz[a:a + 3].all() for a in range(len(zz) - 2)) for zz in z])
    dry2 = np.mean([any(zz[a:a + 2].all() for a in range(len(zz) - 1)) for zz in z])
    return {"net_m": round(float(net.mean()) / mo), "net_p10_m": round(float(np.percentile(net, 10)) / mo),
            "p_neg": round(100.0 * float((net < 0).mean()), 1), "owner_m": round(float(np.mean([r["owner"] for r in rows])) / mo),
            "cost_m": round(float(np.mean([r["cost"] for r in rows])) / mo), "zero_months_after_m3": round(100.0 * float(z.mean()), 1),
            "dry2_after_m3": round(100.0 * float(dry2), 1), "dry3_after_m3": round(100.0 * float(dry3), 1),
            "month_p10_after_m3": round(float(np.percentile(pm[:, 3:], 10))), "month_med_after_m3": round(float(np.median(pm[:, 3:]))),
            "evals": round(float(np.mean([r["evals"] for r in rows])), 2), "grads": round(float(np.mean([r["grads"] for r in rows])), 2),
            "pays": round(float(np.mean([r["pays"] for r in rows])), 2), "lost": round(float(np.mean([r["lost"] for r in rows])), 2)}


def stack_slots(ask=None, prebuy=None, fund50=U.UP50, fund25=U.UP25):
    e50, e25 = U.ecfg_of({}), U.ecfg_of({}, plan="builder25k")
    k25 = None if ask is None else ask * 0.5
    s50 = ("builder50k", e50, fund50, PRICE["builder50k"], ask, prebuy)
    s25 = ("builder25k", e25, fund25, PRICE["builder25k"], k25, prebuy)
    return [s50, s25, s25, s50, s50, s50, s50]


def main():
    n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else U.N_MC
    S, BY = U.load()
    out = {"built": dt.date.today().isoformat(), "n": n, "rows": {}, "single": {}}
    P = {sp: {b: [seq for seq in __import__("div_stack").paths(S, sp, n, length=252 + 30, block=b)] for b in (5, 21)} for sp in SPANS}
    variants = [
        ("today", dict()),
        ("ask2000", dict(ask=2000.0)),
        ("ask1000", dict(ask=1000.0)),
        ("reserve2", dict(policy={"max_per_month": 2})),
        ("reserve3", dict(policy={"max_per_month": 3})),
        ("reserve4", dict(policy={"max_per_month": 4})),
        ("prebuy4", dict(prebuy=4)),
        ("prebuy3", dict(prebuy=3)),
        ("prebuy4_ask2000", dict(prebuy=4, ask=2000.0)),
        ("cons_aware", dict(fund50={**U.UP50, "cons_aware": True}, fund25={**U.UP25, "cons_aware": True})),
        ("cons_after_payout", dict(fund50={**U.UP50, "cons_aware": "after_payout"}, fund25={**U.UP25, "cons_aware": "after_payout"})),
    ]
    for vid, v in variants:
        pol = v.pop("policy", None)
        slots = stack_slots(**v)
        for b in (5, 21):
            row = {sp: summarise(run_stack(BY, P[sp][b], slots, policy=pol)) for sp in SPANS}
            out["rows"][f"{vid}__b{b}"] = row
            print(f"b{b:<2} {vid:18s} " + " | ".join(
                f"{sp} ${row[sp]['net_m']:>5}/mo p10 ${row[sp]['net_p10_m']:>5} zero-mo {row[sp]['zero_months_after_m3']:>5}% "
                f"dry2 {row[sp]['dry2_after_m3']:>5}% dry3 {row[sp]['dry3_after_m3']:>5}% evals {row[sp]['evals']} grads {row[sp]['grads']}"
                for sp in SPANS), flush=True)
    # one MFFU 50K slot alone (12 months) for the ask line / pre-buy, so the per-account effect is visible
    for vid, v in (("today", {}), ("ask2000", {"ask": 2000.0}), ("ask1000", {"ask": 1000.0}), ("prebuy4", {"prebuy": 4})):
        sl = [("builder50k", U.ecfg_of({}), U.UP50, PRICE["builder50k"], v.get("ask"), v.get("prebuy"))]
        row = {sp: summarise(run_stack(BY, P[sp][5], sl)) for sp in SPANS}
        out["single"][vid] = row
        print(f"single 50K {vid:10s} " + " | ".join(f"{sp} ${row[sp]['net_m']:>5}/mo pays {row[sp]['pays']} grads {row[sp]['grads']} "
                                                    f"evals {row[sp]['evals']}" for sp in SPANS), flush=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1, default=float)
    print("->", OUT)


def combo_main(n):
    """The three gains of 2026-10-26 together on the same stack: the eval kept on two_week after session 10
    (eval-cost.md), the pre-bought replacement eval at the 4th payout (this study) and the NA add-on on every funded account
    (diversifier-search.md: 3% of the room, <= $150 on a 50K / $75 on a 25K, never while LIT holds). -> key "combo"."""
    import div_stack as DSK
    S, BYL, BYN, BYM = DSK.load()

    class MixG(GFunded):
        def qty(self, t, st):
            if t.get("src") == "na":
                cap = 150.0 if int(self.A["max_micros"]) >= 40 else 75.0
                return DSK.na_q(t, st["room"], {"f": 0.03, "cap": cap}, self.A["max_micros"], float(self.A["dll"]) + st["cum"])
            return super().qty(t, st)
    gf0, ev0 = globals()["GFunded"], U.Eval
    out = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    P = {sp: {b: DSK.paths(S, sp, n, length=252 + 30, block=b) for b in (5, 21)} for sp in SPANS}
    tw = {"two_week_until": 999}
    e50, e25 = U.ecfg_of(dict(tw)), U.ecfg_of(dict(tw), plan="builder25k")
    cfgs = {
        "tw99": (BYL, False, [("builder50k", e50, U.UP50, PRICE["builder50k"], None, None),
                              ("builder25k", e25, U.UP25, PRICE["builder25k"], None, None)]),
        "mix_prebuy4": (BYM, True, None),
        "all3_tw99_prebuy4_mix": (BYM, True, [("builder50k", e50, U.UP50, PRICE["builder50k"], None, 4),
                                              ("builder25k", e25, U.UP25, PRICE["builder25k"], None, 4)]),
    }
    res = {}
    try:
        U.Eval = DSK.Eval                              # LIT-only eval sizing on mixed days (NA never trades an eval)
        for cid, (BY, mix, sl) in cfgs.items():
            globals()["GFunded"] = MixG if mix else gf0
            if sl is None:
                slots = stack_slots(prebuy=4)
            else:
                s50, s25 = sl
                slots = [s50, s25, s25, s50, s50, s50, s50]
            for b in (5, 21):
                row = {sp: summarise(run_stack(BY, P[sp][b], slots)) for sp in SPANS}
                res[f"{cid}__b{b}"] = row
                print(f"combo b{b:<2} {cid:24s} " + " | ".join(
                    f"{sp} ${row[sp]['net_m']:>5}/mo p10 ${row[sp]['net_p10_m']:>5} zero-mo {row[sp]['zero_months_after_m3']:>5}% "
                    f"dry3 {row[sp]['dry3_after_m3']:>5}% evals {row[sp]['evals']}" for sp in SPANS), flush=True)
    finally:
        U.Eval = ev0
        globals()["GFunded"] = gf0
    out["combo"] = res
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1, default=float)
    print("->", OUT)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "combo":
        combo_main(int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else U.N_MC)
    else:
        main()
