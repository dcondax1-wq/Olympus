"""The whole MFFU fleet on ONE Monte Carlo (owner 2026-11-17, night-fleet). PAPER RESEARCH ONLY: reads stored trades, writes
research/lab/fleet_plan.json + tools/web_public/business/plan.json, changes nothing live.
Write-up: research/writeups/fleet-plan-2026-11-17.md. Page: tools/web_public/business/plan.html.

Every account runs on the SAME 5-session-block paths (tools/uprisk.mc_paths, seed 23, 126 sessions from 2026-11-17), so a bad
week hits all of them at once (they trade the same signals). The accounts (the owner's after 2026-11-17):

  Z50   Zlarior, Builder 50K eval from its real hole ($49,192.78: $3,807 to go, $1,025 room, ~session 26), LIT live two_week;
        funded = LIT + ATLAS $500 (builder_levers F50_LA, ask $1,500). Fails -> a fresh 50K at $91.80 (the slot logic).
  A25   ATLAS funded Builder 25K, $25,000 from this week (2 sessions of paperwork), ATLAS alone at the 25K funded preset
        (funded25 "ATLAS alone (today)"). Lost / 5 payouts -> a fresh 25K eval ($63) on ATLAS's eval sizing.
  N25   NEW Builder 25K eval ($63): LIT on the 25K two_week; funded = LIT + ATLAS $250 on one account (funded25.by_shared,
        the engine/lit25 one-account rule). Fails -> re-buy.
  R1    NEW Rapid EOD 50K eval ($165 with CLUB): LIT + ATLAS $500, the 30% best-day guard; funded keeps $1,000 above the
        $2,100 buffer (rapid_levers "LIT + ATLAS", cushion 1000). Fails / lost -> re-buy at $165.
  R2    the 5th funded slot (MFFU max 5 funded: 1 Builder 50K, 2 Builder 25K, up to 3 Rapid EOD 50K): a 2nd Rapid EOD 50K,
        bought on the session after the payouts in hand (after the 30% tax pot) first reach its $165. Owner said "1 rapid":
        shown separately, the fleet totals are given with and without it.

Re-buy rule = the research's slot logic (account4_sim / builder_levers.Seat / rapid_levers.Slot): a failed or stuck eval is
re-bought at once, a lost funded account starts a fresh eval; no early give-up (rapid-levers-2026-11-16: give-up is noise).
Cash = payouts x split (80% Builder, 90% Rapid) - every fee; "after tax" moves 30% of each payout to the tax pot first.
A payout counts on the day it is paid by the sim; the bank shows it ~2-4 business days later.

    python -X utf8 tools/money/fleet_plan.py            # n=1000 a market -> research/lab/fleet_plan.json + business/plan.json
    python -X utf8 tools/money/fleet_plan.py --n 100    # quicker
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import builder_levers as BL  # noqa: E402
import rapid_levers as RL  # noqa: E402
import funded25 as F25  # noqa: E402

SA, U, np = BL.SA, BL.U, BL.np
ROOT = BL.ROOT
OUT = os.path.join(ROOT, "research", "lab", "fleet_plan.json")
PAGE = os.path.join(ROOT, "tools", "web_public", "business", "plan.json")
START = "2026-11-17"
P50, P25, PR = 91.80, 63.00, 165.00            # owner's real prices with CLUB
RL.PRICE = PR                                  # rapid_levers.Slot charges its module PRICE on every buy
TAX = 0.30
LEN, GAP = BL.LEN, BL.GAP
ZLARIOR = {"room": 1025.0, "to_go": 3807.0, "session": 26}   # 2026-11-17: $49,192.78, floor $48,168.20
NAMES = {"Z50": "Zlarior 50K", "A25": "ATLAS funded 25K", "N25": "New 25K", "R1": "Rapid EOD 50K", "R2": "Rapid EOD 50K #2"}
MKT = {"H1": "2026 Jan-Jun-like", "H2": "2026 Jul-Oct-like", "REF": "2021-25-like"}


# ================================================================================================ the accounts
class BSeat:
    """builder_levers.Seat on its own eval / funded trade lists, stepped by path session index."""

    def __init__(self, seat, BYe, BYf):
        self.s, self.BYe, self.BYf = seat, BYe, BYf
        self.c0 = 0.0                                  # the buy at creation is charged on the first session

    def step(self, k, si):
        o0 = self.s.owner
        self.s.step(k, self.BYe[si], self.BYf[si])
        c, self.c0 = self.s.cost - self.c0, self.s.cost
        return self.s.owner - o0, c

    def funded(self):
        return self.s.f is not None

    @property
    def first_pay(self):
        return self.s.first_pay


class RSeat:
    """rapid_levers.Slot (eval -> 2 sessions -> funded -> lost -> buy again)."""

    def __init__(self, spec):
        self.s = RL.Slot(spec)
        self.c0 = 0.0                                  # the buy at creation is charged on the first session

    def step(self, k, si):
        o0 = self.s.owner
        self.s.step(k, si)
        c, self.c0 = self.s.cost - self.c0, self.s.cost
        return self.s.owner - o0, c

    def funded(self):
        return self.s.f is not None

    @property
    def first_pay(self):
        return self.s.first_pay


def makers():
    E25, E50 = BL.E25, BL.E50
    BYl, BYla, BYa = BL.by_mix(("LIT",)), BL.by_mix(("LIT", "ATLAS")), BL.by_mix(("ATLAS",))
    BYs, _ = F25.by_shared()
    rspec = RL.spec_of("LIT + ATLAS", pol=("cushion", 1000))

    def z50():
        s = BL.Seat(lambda _=None: BL.GEv(E50, BL.Zlit50()), lambda: BL.GF("builder50k", U.UP50, BL.F50_LA), P50,
                    [BL.GEv(E50, BL.Zlit50(), start=ZLARIOR)])
        return BSeat(s, BYl, BYla)

    def a25():
        s = BL.Seat(lambda _=None: BL.GEv(E25, BL.Zatlas25(), stuck=200.0),
                    lambda: BL.GF("builder25k", U.UP25, {"ATLAS": ("fq", None)}), P25, [])
        s.evals, s.wait, s.first_pass = [], GAP, 0          # passed already: MFFU paperwork, then funded at $25,000
        return BSeat(s, BYa, BYa)

    def n25():
        ze = lambda: {"LIT": ("lit", BL.ecfg25())}                                   # noqa: E731
        zf = {"LIT": ("fq", None), "ATLAS": ("stack", 250.0, 0.3)}
        s = BL.Seat(lambda _=None: BL.GEv(E25, ze()), lambda: BL.GF("builder25k", U.UP25, zf), P25, [BL.GEv(E25, ze())],
                    cost0=P25)
        return BSeat(s, BYl, BYs)

    return {"Z50": z50, "A25": a25, "N25": n25, "R1": lambda: RSeat(rspec), "R2": lambda: RSeat(rspec)}


# ================================================================================================ one market
def run_market(paths, M):
    """-> arrays [path, session] of cash in (owner, gross of tax) and fees per account, funded flags, first payouts, R2 buy."""
    n = len(paths)
    keys = list(NAMES)
    own = {k: np.zeros((n, LEN)) for k in keys}
    fee = {k: np.zeros((n, LEN)) for k in keys}
    fund = {k: np.zeros((n, LEN), dtype=bool) for k in keys}
    first = {k: np.full(n, -1) for k in keys}
    r2_buy = np.full(n, -1)
    for p, seq in enumerate(paths):
        A = {k: M[k]() for k in ("Z50", "A25", "N25", "R1")}
        paid_net = 0.0
        for k, si in enumerate(seq[:LEN]):
            for nm, a in A.items():
                o, c = a.step(k, si)
                own[nm][p, k], fee[nm][p, k] = o, c
                fund[nm][p, k] = a.funded()
                if nm != "R2":
                    paid_net += o * (1 - TAX)
            if "R2" not in A and paid_net >= PR:       # payouts in hand (after the tax pot) cover the 5th account: buy it
                A["R2"] = M["R2"]()                    # first session next session (bought after today's close)
                r2_buy[p] = k + 1
        for nm, a in A.items():
            first[nm][p] = (a.first_pay - 1) if a.first_pay else -1
    return {"own": own, "fee": fee, "fund": fund, "first": first, "r2_buy": r2_buy}


def pct(a, q):
    return round(float(np.percentile(a, q)))


def summarize(R, cal, months):
    keys = list(NAMES)
    n = R["own"]["Z50"].shape[0]
    mi = np.array([months.index(d[:7]) for d in cal[:LEN]])
    out = {}
    for tag, ks in (("five", keys), ("four", [k for k in keys if k != "R2"])):
        own = sum(R["own"][k] for k in ks)
        fee = sum(R["fee"][k] for k in ks)
        cash = own - fee                                  # after fees and splits
        net = own * (1 - TAX) - fee                       # after the 30% tax pot too
        rows = []
        for m, mk in enumerate(months):
            sel = mi == m
            cm, nm_ = cash[:, sel].sum(1), net[:, sel].sum(1)
            cum = net[:, mi <= m].sum(1)
            cumc = cash[:, mi <= m].sum(1)
            rows.append({"month": mk, "sessions": int(sel.sum()), "cash_mean": round(float(cm.mean())),
                         "net_mean": round(float(nm_.mean())), "tax_mean": round(float((own[:, sel].sum(1) * TAX).mean())),
                         "fees_mean": round(float(fee[:, sel].sum(1).mean())),
                         "cum_net_p10": pct(cum, 10), "cum_net_p50": pct(cum, 50), "cum_net_p90": pct(cum, 90),
                         "cum_cash_p10": pct(cumc, 10), "cum_cash_p50": pct(cumc, 50), "cum_cash_p90": pct(cumc, 90),
                         "cum_net_mean": round(float(cum.mean()))})
        # out of pocket: the most the fleet is ever down (fees paid minus payouts in hand after tax), incl. today's buys
        dn = np.maximum.accumulate(-np.cumsum(net, axis=1), axis=1)[:, -1]
        jan = cal.index(next(d for d in cal if d > "2027-01-31"))
        any_pay = (own[:, :jan] > 0).any(1)
        fa = np.array([int(np.argmax(r)) if r.any() else -1 for r in own > 0])
        dec = cal.index(next(d for d in cal if d > "2026-12-31"))
        out[tag] = {"months": rows, "first_any_med": cal[int(np.median(fa[fa >= 0]))] if (fa >= 0).any() else None,
                    "p_pay_by_dec31": round(100.0 * float(((fa >= 0) & (fa < dec)).mean()), 1), "total_net_mean": round(float(net.sum(1).mean())), "total_cash_mean": round(float(cash.sum(1).mean())),
                    "total_net_p10": pct(net.sum(1), 10), "total_net_p50": pct(net.sum(1), 50), "total_net_p90": pct(net.sum(1), 90),
                    "p_no_pay_by_jan31": round(100.0 * (1 - any_pay.mean()), 1),
                    "p_no_pay_6m": round(100.0 * (1 - (own > 0).any(1).mean()), 1),
                    "p_net_negative_6m": round(100.0 * (net.sum(1) < 0).mean(), 1),
                    "pocket_p50": pct(dn, 50), "pocket_p90": pct(dn, 90), "pocket_p95": pct(dn, 95), "pocket_max": round(float(dn.max())),
                    "fees_mean": round(float(fee.sum(1).mean()))}
    jan = cal.index(next(d for d in cal if d > "2027-01-31"))
    acc = {}
    for k in keys:
        f = R["first"][k]
        got = f[f >= 0]
        fu = R["fund"][k]
        ff = np.array([int(np.argmax(r)) if r.any() else -1 for r in fu])
        fg = ff[ff >= 0]
        acc[k] = {"name": NAMES[k], "first_pay_med": cal[int(np.median(got))] if len(got) else None,
                  "first_pay_p25": cal[int(np.percentile(got, 25))] if len(got) else None,
                  "first_pay_p75": cal[int(np.percentile(got, 75))] if len(got) else None,
                  "p_pay_by_jan31": round(100.0 * float(((f >= 0) & (f < jan)).mean()), 1),
                  "p_no_pay_6m": round(100.0 * float((f < 0).mean()), 1),
                  "funded_med": cal[int(np.median(fg))] if len(fg) else None, "p_funded_6m": round(100.0 * len(fg) / n, 1),
                  "cash_net_6m": round(float((R["own"][k] * (1 - TAX) - R["fee"][k]).sum(1).mean())),
                  "fees_6m": round(float(R["fee"][k].sum(1).mean())),
                  "buys_6m": round(float(R["fee"][k].sum(1).mean()) / {"Z50": P50, "R1": PR, "R2": PR}.get(k, P25), 2), "paid_6m": round(float(R["own"][k].sum(1).mean()))}
    rb = R["r2_buy"]
    acc["R2"]["buy_med"] = cal[int(np.median(rb[rb >= 0]))] if (rb >= 0).any() else None
    acc["R2"]["p_bought"] = round(100.0 * float((rb >= 0).mean()), 1)
    allf = np.all([R["fund"][k] for k in keys], axis=0)            # all five funded on the same session
    a5 = np.array([int(np.argmax(r)) if r.any() else -1 for r in allf])
    fill = {"p_all5_6m": round(100.0 * float((a5 >= 0).mean()), 1),
            "all5_med": cal[int(np.median(a5[a5 >= 0]))] if (a5 >= 0).any() else None,
            "p_all5_by": {mk: round(100.0 * float(((a5 >= 0) & (mi[np.maximum(a5, 0)] <= m)).mean()), 1) for m, mk in enumerate(months)}}
    return {"fleet": out, "accounts": acc, "fill5": fill}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--no-save", action="store_true")
    a = ap.parse_args(argv)
    import logging
    logging.getLogger("engine.sizing").setLevel(logging.ERROR)
    import payout_plan as PP
    t0 = time.time()
    cal = PP.calendar(LEN + 5, START)
    months = sorted({d[:7] for d in cal[:LEN]})
    S = SA.data()["S"]
    M = makers()
    res = {"date": START, "n": a.n, "sessions": LEN, "end": cal[LEN - 1], "prices": {"builder50k": P50, "builder25k": P25, "rapid_eod50k": PR},
           "tax": TAX, "zlarior": ZLARIOR, "markets": MKT, "months": months, "spans": U.SPAN, "rows": {}}
    for sp in ("H2", "H1", "REF"):
        t1 = time.time()
        paths = U.mc_paths(S, sp, a.n, length=LEN, seed=BL.A4.SEED_LIFE)
        r = summarize(run_market(paths, M), cal, months)
        res["rows"][sp] = r
        f5, f4 = r["fleet"]["five"], r["fleet"]["four"]
        print(f"{sp:3s} 6m after tax: 5 accts mean ${f5['total_net_mean']:,} (p10 {f5['total_net_p10']:,} / p50 {f5['total_net_p50']:,} / "
              f"p90 {f5['total_net_p90']:,}) | 4 accts ${f4['total_net_mean']:,} | no pay by Jan31 {f5['p_no_pay_by_jan31']}% | "
              f"1st any {f5['first_any_med']} by Dec31 {f5['p_pay_by_dec31']}% | pocket p90 ${f5['pocket_p90']} p95 ${f5['pocket_p95']} | all 5 funded {r['fill5']['p_all5_6m']}% med {r['fill5']['all5_med']} "
              f"({time.time() - t1:.0f}s)")
        for m in f5["months"]:
            print(f"     {m['month']} cash ${m['cash_mean']:,} after tax ${m['net_mean']:,} | cum after tax p10/50/90 "
                  f"{m['cum_net_p10']:,} / {m['cum_net_p50']:,} / {m['cum_net_p90']:,}")
        for k, x in r["accounts"].items():
            print(f"     {x['name']:18s} 1st pay {x['first_pay_med']} (p25 {x['first_pay_p25']} p75 {x['first_pay_p75']}) by Jan31 "
                  f"{x['p_pay_by_jan31']}% none {x['p_no_pay_6m']}% funded {x['funded_med']} ({x['p_funded_6m']}%) "
                  f"net ${x['cash_net_6m']:,} fees ${x['fees_6m']}" + (f" bought {x['buy_med']} ({x['p_bought']}%)" if k == "R2" else ""))
    if not a.no_save:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=1, default=float)
        with open(PAGE, "w", encoding="utf-8") as fh:
            json.dump(res, fh, separators=(",", ":"), default=float)
        print("wrote", os.path.relpath(OUT, ROOT), "and", os.path.relpath(PAGE, ROOT))
    print(f"{time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
