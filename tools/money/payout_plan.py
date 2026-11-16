#!/usr/bin/env python3
"""PAYOUT PLAN (team E, 2026-11-16): when each eval can pass, the first payout's date and $, and when to buy account #3, #4 ...
from the payouts only (never rent money), with the $ a month at 2, 3, 4 and 6 accounts. PAPER RESEARCH ONLY: it reads stored
trades and the firms' rules, writes research/lab/payout_plan.json, never trades, buys or calls anything.

    python -X utf8 tools/money/payout_plan.py              (~2-4 min: 300 paths per half, 12 months)
    python -X utf8 tools/money/payout_plan.py --n 100      (quick)
    python -X utf8 tools/money/payout_plan.py --selftest   (bundled checks, ~20 s)

What it plays (tools/account4_sim.py + tools/uprisk.py: the live sizing code, the firms' rules from the guard's own data):
  Zlarior   LIT on its MFFU Builder 50K eval FROM ITS REAL STATE (the owner's last report: $1,145 of the $2,000 drawdown left,
            $3,687 still to make, session 20; the bot has not traded since), the live eval sizing (two_week, 40% of the room,
            kept to session 80), then MFFU sim funded (buffer $2,100, $500-$2,000, best day <= 50%, 2 days a cycle, 80%,
            5 payouts) on the live funded preset. A failed / ended account is bought again ($91.80).
  #3 ...    each new account is a LucidPro 50K copy of Zlarior (MFFU funds only ONE Builder 50K a person: a second MFFU 50K
            cannot be funded next to Zlarior's, help center 2026-11-16): ONE new account per payout that reached the bank,
            bought that session when the PAYOUT BANK holds two of its price ($134.40 with a 30% code: one to buy, one kept
            for a re-buy). Lucid allows 5 funded a household; 6 accounts = Zlarior + ATLAS + 4 Lucid copies.
  ATLAS     a different bot (account B) the replay cannot play: its $ a month is the stored research estimate
            (research/lab/rd_money.json slot atlas25: H1 $568 / H2 $382 / 2021-25 -$2), added from month 3 (after its pass).
  Money     a payout reaches the bank 3 sessions after it is taken (an assumption: MFFU / Lucid process payouts in about
            1-3 business days). Fees are paid from the bank; when the bank is short, from the owner's pocket (counted).
            The owner can never lose more than the fees: the losses inside an account are the firm's money. STOP rule:
            at most 2 re-buys ($183.60) from the pocket; past that the account is not bought again (stop and rethink).
Paths: whole weeks (5 sessions) drawn from Jan-Jun 2026 (H1, where LIT was picked), Jul-Oct 2026 (H2, the check: quote H2)
and 2021-25 (REF, where LIT has no edge). Every account trades the SAME path: one signal (daily correlation ~0.94), so one
bad week hits them all at once. Backtests overstate; nothing here is a promise.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
OUT = os.path.join(ROOT, "research", "lab", "payout_plan.json")
START_DAY = "2026-11-17"            # the first session after tonight's arming (2026-11-16 evening)
HORIZON = 252                       # 12 months of sessions
MONTH = 21                          # sessions a month
LAND = 3                            # sessions from taking a payout to the money in the bank (assumption)
SPANS = ("H1", "H2", "REF")
# the real eval state (STATE.md / research/writeups/eval-guard-2026-11-13.md: the owner's last report 2026-11-07)
ZLARIOR = {"room": 1145.0, "to_go": 3687.0, "session": 20, "price": 91.80, "plan": "MFFU Builder 50K", "asof": "2026-11-07"}
ATLAS = {"room": 822.0, "to_go": 1678.0, "price": 43.00, "plan": "MFFU Builder 25K", "asof": "2026-11-07",
         "usd_month": {"H1": 568.0, "H2": 382.0, "REF": -2.0}, "from_month": 3,
         "pass_2wk": {"H1": 57.3, "H2": 34.5}, "src": "research/writeups/eval-guard-2026-11-13.md, research/lab/rd_money.json"}
NEW_PRICE = 134.40                  # LucidPro 50K, list $192 - 30% code (docs/ACCOUNT_4.md; confirm at checkout)
NEW_PLAN = "LucidPro 50K copy of Zlarior"
TARGETS = (2, 3, 4, 6)              # accounts in all (Zlarior + ATLAS + the copies)
POCKET_CAP = 2 * 91.80              # the stop rule: at most 2 Zlarior re-buys from the owner's pocket, then stop and rethink
SEED = 41


def calendar(n: int, start: str = START_DAY) -> list:
    """n CME sessions from start (weekdays, full closures skipped: engine/cme_calendar)."""
    try:
        from engine.cme_calendar import full_closure
    except Exception:                              # noqa: BLE001
        full_closure = lambda d: False             # noqa: E731
    out, d = [], dt.date.fromisoformat(start)
    while len(out) < n:
        if d.weekday() < 5 and not full_closure(d.isoformat()):
            out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out


def zlarior_slot(A4, spec):
    """Zlarior's slot started from the real eval state (the eval already paid for: no fee counted)."""
    s = A4.Slot(spec)
    s.cost = 0.0
    e = s.e
    prof = 3000.0 - ZLARIOR["to_go"]               # -687: the balance vs the start
    e.bal = prof
    e.floor = prof - ZLARIOR["room"]                # -1,832 (the EOD floor; it trails from the best close)
    e.peak = e.floor + e.E["mll"]
    e.s = ZLARIOR["session"]
    e.dtr = ZLARIOR["session"]
    return s


def play(BY, paths, n_target: int, A, B, A4):
    """One growth policy on every path. -> per path: monthly owner cash, fees from the pocket, buy sessions, Zlarior's
    pass / fail / first payout."""
    out = []
    max_lit = max(1, n_target - 1)                  # ATLAS is the other account
    for seq in paths:
        slots = [zlarior_slot(A4, A)]
        prev = [(0.0, 0.0)]
        bank, pocket = 0.0, 0.0
        land, credits = {}, 0
        month = np.zeros(HORIZON // MONTH + 1)
        buys = []
        z_pass = z_fail = z_pay = z_pay_amt = stopped = None
        for k, si in enumerate(seq[:HORIZON]):
            for j, s in enumerate(slots):
                s.step(k, BY[si])
                o0, c0 = prev[j]
                d_own, d_cost = s.owner - o0, s.cost - c0
                prev[j] = (s.owner, s.cost)
                if d_own > 1e-9:
                    land[k + LAND] = land.get(k + LAND, 0.0) + d_own
                    if j == 0 and z_pay is None:
                        z_pay, z_pay_amt = k, d_own
                if d_cost > 1e-9:                    # a re-buy: the bank first, else the pocket (capped: the stop rule)
                    take = min(bank, d_cost)
                    if pocket + d_cost - take > POCKET_CAP + 1e-6:
                        s.cost -= d_cost             # STOP: no re-buy from the owner's pocket past the cap
                        s.e, s.f, s.done = None, None, True
                        prev[j] = (s.owner, s.cost)
                        stopped = stopped or k
                        continue
                    bank -= take
                    pocket += d_cost - take
                    month[k // MONTH] -= d_cost
            if z_pass is None and z_fail is None:
                for kk, ev in slots[0].events:
                    if ev == "pass":
                        z_pass = kk
                    elif ev == "fail":
                        z_fail = kk
            got = land.pop(k, 0.0)
            if got:
                bank += got
                month[k // MONTH] += got
                credits += 1                         # one new account per payout that reached the bank
            if credits and len(slots) < max_lit and bank >= 2 * NEW_PRICE - 1e-9:
                credits -= 1
                ns = A4.Slot(B)                     # bought now from the bank: its eval starts next session
                bank -= ns.cost
                month[k // MONTH] -= ns.cost
                slots.append(ns)
                prev.append((ns.owner, ns.cost))
                buys.append(k)
        out.append({"month": month[: HORIZON // MONTH], "pocket": pocket, "buys": buys, "z_pass": z_pass, "z_fail": z_fail,
                    "z_pay": z_pay, "z_pay_amt": z_pay_amt, "bank": bank, "stopped": stopped})
    return out


def _pct(xs, q):
    return float(np.percentile(xs, q)) if len(xs) else None


def summarize(R, cal, span, n_target):
    n = len(R)
    ML = np.array([r["month"] for r in R])          # paths x 12: Zlarior + the copies (the replayed accounts)
    at = ATLAS["usd_month"][span]
    M = ML + np.array([[at if m + 1 >= ATLAS["from_month"] else 0.0 for m in range(ML.shape[1])]]) if n_target >= 2 else ML
    day = lambda k: cal[int(round(k))] if k is not None and int(round(k)) < len(cal) else None   # noqa: E731
    # the bad months from the replayed accounts only, ATLAS counted at its worst (a re-buy, no payout): its flat average
    # estimate must not hide a month where the one LIT signal paid nothing on every account at once
    o = {"accounts": n_target, "usd_month_y1": round(float(M.mean())), "usd_month_m7_12": round(float(M[:, 6:].mean())),
         "month_p10": round(_pct(ML.ravel(), 10)), "month_worst": round(float(ML.min()) - ATLAS["price"]),
         "months_negative_pct": round(100.0 * float((ML < -1e-6).mean()), 1),
         "months_no_income_pct": round(100.0 * float((ML < 1.0).mean()), 1),
         "months_no_income_m7_12_pct": round(100.0 * float((ML[:, 6:] < 1.0).mean()), 1),
         "stopped_pct": round(100.0 * sum(1 for r in R if r["stopped"] is not None) / n, 1),
         "y1_total": round(float(M.sum(axis=1).mean())), "y1_p10": round(_pct(M.sum(axis=1), 10)),
         "pocket_mean": round(float(np.mean([r["pocket"] for r in R])), 2),
         "pocket_p90": round(_pct([r["pocket"] for r in R], 90), 2), "pocket_max": round(max(r["pocket"] for r in R), 2)}
    buys = {}
    for i in range(n_target - 2):
        ks = [r["buys"][i] for r in R if len(r["buys"]) > i]
        buys[f"#{i + 3}"] = {"pct_12m": round(100.0 * len(ks) / n, 1), "p25": day(_pct(ks, 25)), "median": day(_pct(ks, 50)),
                             "p75": day(_pct(ks, 75))}
    o["buy"] = buys
    return o


def zlarior_summary(R, cal):
    n = len(R)
    ps = [r["z_pass"] for r in R if r["z_pass"] is not None]
    fs = [r["z_fail"] for r in R if r["z_fail"] is not None and (r["z_pass"] is None or r["z_fail"] < r["z_pass"])]
    pays = [r["z_pay"] for r in R if r["z_pay"] is not None]
    amts = [r["z_pay_amt"] for r in R if r["z_pay_amt"] is not None]
    day = lambda k: cal[int(round(k))] if k is not None and int(round(k)) < len(cal) else None   # noqa: E731
    return {"pass_10": round(100.0 * sum(1 for k in ps if k < 10) / n, 1), "fail_10": round(100.0 * sum(1 for k in fs if k < 10) / n, 1),
            "pass_ever": round(100.0 * len(ps) / n, 1), "first_eval_failed": round(100.0 * len(fs) / n, 1),
            "pass_earliest": day(_pct(ps, 10)), "pass_median": day(_pct(ps, 50)),
            "first_payout_pct_12m": round(100.0 * len(pays) / n, 1), "first_payout_earliest": day(_pct(pays, 10)),
            "first_payout_median": day(_pct(pays, 50)), "first_payout_in_bank_median": day(_pct(pays, 50) + LAND if pays else None),
            "first_payout_usd_median": round(_pct(amts, 50)) if amts else None, "first_payout_usd_p10": round(_pct(amts, 10)) if amts else None}


def study(n=300, log=print):
    import account4_sim as A4
    import uprisk as U
    S, BY = A4.load()
    A, B = A4.specs()
    cal = calendar(HORIZON + LAND + 2)
    res = {"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "tool": "tools/money/payout_plan.py", "n": n, "start": START_DAY,
           "zlarior_state": ZLARIOR, "atlas": ATLAS, "new_account": {"plan": NEW_PLAN, "price": NEW_PRICE},
           "rules": {"land_sessions": LAND, "buy_when_bank": 2 * NEW_PRICE, "one_buy_per_payout": True, "pocket_cap": POCKET_CAP, "max_lucid_funded": 5, "mffu_builder50k_funded": 1},
           "spans": {}}
    for sp in SPANS:
        P = U.mc_paths(S, sp, n, length=HORIZON, seed=SEED)
        row = {"plans": {}}
        for nt in TARGETS:
            R = play(BY, P, nt, A, B, A4)
            row["plans"][str(nt)] = summarize(R, cal, sp, nt)
            if nt == TARGETS[-1]:
                row["zlarior"] = zlarior_summary(R, cal)
            log(f"{sp} {nt} accounts: {row['plans'][str(nt)]['usd_month_y1']}/mo y1, {row['plans'][str(nt)]['usd_month_m7_12']}/mo m7-12, "
                f"worst month {row['plans'][str(nt)]['month_worst']}")
        res["spans"][sp] = row
    return res


def selftest() -> int:
    import account4_sim as A4
    import uprisk as U
    cal = calendar(30)
    assert cal[0] == "2026-11-17" and "2026-12-25" not in cal and all(dt.date.fromisoformat(d).weekday() < 5 for d in cal), cal
    S, BY = A4.load()
    A, B = A4.specs()
    z = zlarior_slot(A4, A)
    assert z.cost == 0.0 and abs(z.e.bal + 687.0) < 1e-9 and abs((z.e.bal - z.e.floor) - 1145.0) < 1e-9, (z.e.bal, z.e.floor)
    P = U.mc_paths(S, "H2", 20, length=HORIZON, seed=SEED)
    R2 = play(BY, P, 2, A, B, A4)
    R6 = play(BY, P, 6, A, B, A4)
    assert all(not r["buys"] for r in R2), "2 accounts: nothing bought"
    assert all(len(r["buys"]) <= 4 for r in R6), "6 accounts: at most 4 copies"
    assert all(r["buys"] == sorted(r["buys"]) for r in R6)
    for r in R6:                                   # a buy only once a payout reached the bank (never from the pocket)
        if r["buys"]:
            assert r["z_pay"] is not None and r["buys"][0] >= r["z_pay"] + LAND, (r["buys"], r["z_pay"])
    s = summarize(R6, calendar(HORIZON + 10), "H2", 6)
    assert s["month_worst"] <= s["month_p10"] <= s["usd_month_y1"] + 1e6 and set(s["buy"]) == {"#3", "#4", "#5", "#6"}
    print("payout_plan selftest ok")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    res = study(a.n)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1)
        fh.write("\n")
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
