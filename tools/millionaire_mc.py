"""M1 "millionaire plan" (owner 2026-11-12: "You're gonna make me a million of trading prop firms and eventually live
accounts, so think like a millionaire."). research/writeups/millionaire-plan-2026-11-13.md. PAPER RESEARCH ONLY: reads the
live LIT trades through tools/uprisk.py, writes research/lab/millionaire_mc.json, nothing live changes.

The whole business as a Monte Carlo, from our own trade list (bootstrap by week = 5-session blocks of the chosen span):
  * every account slot = the uprisk engine (MFFU Builder eval on the live two_week sizing -> 2 sessions of paperwork ->
    MFFU Builder Sim Funded on the live funded preset -> payouts (80% to the owner) -> lost or 5 payouts -> buy the next
    eval). $1.90 a micro. Slot j is bought 5*j sessions after slot 0, on the SAME market path (the copies are one bet).
  * fleets 1 / 3 / 5 / 10 accounts: [MFFU 50K, MFFU 25K, MFFU 25K] (MFFU's per-person Builder cap) then 50Ks at Lucid /
    FundedNext with MFFU 50K rules as the proxy at $130 an eval (list-ish; codes make it cheaper).
  * rebuy policy: "now" = rebuy the next session (the engine); "breaker" = after 3 evals in a row on a slot fail with no
    pass, wait 42 sessions (2 months) before that slot buys again.
  * eval budget ruin = the running cash (budget + payouts - every fee) would have gone below 0.
  * personal live account (option): once the prop cash after a 30% tax set-aside reaches $30,000, $25,000 goes into a
    personal futures account trading the same LIT trades at 1% of equity per trade (micros = floor(1% / risk of a micro),
    stop + 1 tick + $1.90), plus 50% of every later after-tax prop month; personal gains taxed 25% (60/40 blended
    estimate) once a year. Wealth = after-tax prop cash kept + the personal account.

  python -X utf8 tools/millionaire_mc.py [--n 500] [--months 120] [--quick]      -> research/lab/millionaire_mc.json
  python -X utf8 tools/millionaire_mc.py check                                    (flows == uprisk.life on the same paths)
"""
from __future__ import annotations

import json
import math
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import uprisk as U  # noqa: E402

OUT = os.path.join(ROOT, "research", "lab", "millionaire_mc.json")
SPANS = ("H1", "H2", "REF")
MO = 21                                       # sessions a month
OFFSET = 5                                    # sessions between two slots' first eval (a week apart)
SLOTS = {
    "m50": {"plan": "builder50k", "fcfg": U.UP50, "price": 91.80, "label": "MFFU Builder 50K (Zlarior / LIT)"},
    "m25": {"plan": "builder25k", "fcfg": U.UP25, "price": 63.00, "label": "MFFU Builder 25K (LIT copy, room 0.8)"},
    "o50": {"plan": "builder50k", "fcfg": U.UP50, "price": 130.00, "label": "Lucid / FundedNext 50K (MFFU 50K rules as proxy)"},
}
ORDER = ["m50", "m25", "m25", "o50", "o50", "o50", "o50", "o50", "o50", "o50"]
FLEETS = (1, 3, 5, 10)
TAX_PROP = 0.30                               # set-aside on prop payouts (1099 contractor income; estimate, not advice)
TAX_LIVE = 0.25                               # personal futures gains, 60/40 blended estimate
LIVE_TRIGGER, LIVE_SEED, LIVE_ADD, LIVE_RISK = 30000.0, 25000.0, 0.5, 0.01
GOALS = (100_000, 1_000_000)
RESERVE = 300.0                               # eval budget = the fleet's first purchases + this reserve (and 2x the first purchases)
LADDER = {"first_pay": (3, 4), "net_10k": tuple(range(5, 10))}   # ladder: slots 4-5 at the first payout, 6-10 once $10K net is in


def ecfg(plan):
    return U.ecfg_of({}, plan=plan)


def flows(BY, seq, key, start, horizon, breaker=False):
    """Cash per session for one slot on one path (owner payouts +, eval purchases -), the slot bought at session `start`.
    Same state machine as uprisk.life (checked by `check`)."""
    s = SLOTS[key]
    plan, fc, price = s["plan"], s["fcfg"], s["price"]
    ec = ecfg(plan)
    cash = np.zeros(horizon)
    st = {"evals": 0, "funded": 0, "lost": 0, "grads": 0, "paid": 0.0, "fees": 0.0}
    if start >= horizon:
        return cash, st
    cash[start] -= price
    st["evals"], st["fees"] = 1, price
    e, f, wait, pause, fails_row = U.Eval(ec, plan), None, 0, 0, 0
    for k in range(start, horizon):
        si = seq[k]
        if pause > 0:
            pause -= 1
            if pause == 0:
                cash[k] -= price
                st["evals"] += 1
                st["fees"] += price
                e = U.Eval(ec, plan)
            continue
        if f is None and wait == 0:
            r = e.step(BY[si])
            if r == "pass":
                wait = U.GAP
                st["funded"] += 1
                fails_row = 0
            elif r in ("fail", "stuck", "reset"):
                fails_row += 1
                if breaker and fails_row >= 3:
                    pause, fails_row = 42, 0
                    continue
                cash[k] -= price
                st["evals"] += 1
                st["fees"] += price
                e = U.Eval(ec, plan)
        elif f is None:
            wait -= 1
            if wait == 0:
                f = U.Funded(plan, fc, None)
        else:
            ev, x = f.step(BY[si])
            if ev in ("paid", "grad"):
                cash[k] += x
                st["paid"] += x
            if ev in ("lost", "grad"):
                st["lost" if ev == "lost" else "grads"] += 1
                f = None
                cash[k] -= price
                st["evals"] += 1
                st["fees"] += price
                e = U.Eval(ec, plan)
    return cash, st


def personal(BY, seq, prop_month, months):
    """Wealth path (month ends) with the personal live account switched on at the trigger (see the module doc)."""
    kept, acct, on, start_m = 0.0, 0.0, False, None
    year_gain, out = 0.0, []
    for m in range(months):
        net = prop_month[m]
        after = net * (1 - TAX_PROP) if net > 0 else net
        if on:
            kept += after * (1 - LIVE_ADD) if after > 0 else after
            acct += after * LIVE_ADD if after > 0 else 0.0
        else:
            kept += after
            if kept >= LIVE_TRIGGER:
                on, start_m = True, m + 1
                kept -= LIVE_SEED
                acct = LIVE_SEED
        if on:
            for k in range(m * MO, (m + 1) * MO):
                for t in BY[seq[k]]:
                    per = (t["risk"] + U.SLIP) * U.PV + U.COMM
                    q = min(int(LIVE_RISK * acct // per), 3000)
                    if q < 1:
                        continue
                    pnl = q * (t["pts"] * U.PV - U.COMM)
                    acct += pnl
                    year_gain += pnl
            if (m + 1) % 12 == 0 and year_gain > 0:
                acct -= TAX_LIVE * year_gain
                year_gain = 0.0
            elif (m + 1) % 12 == 0:
                year_gain = 0.0
        out.append(kept + acct)
    return np.array(out), start_m


def first_month(path, goal):
    hit = np.nonzero(path >= goal)[0]
    return int(hit[0]) + 1 if len(hit) else None


def summarize(cum, months, live_w=None, live_start=None, first_cost=0.0):
    """cum: [paths x months] cumulative prop cash (pre-tax, net of every fee)."""
    n = cum.shape[0]
    dip = -np.minimum(0, np.minimum.accumulate(cum, axis=1).min(axis=1))
    b1, b2 = first_cost + RESERVE, 2 * first_cost
    monthly = np.diff(np.concatenate([np.zeros((n, 1)), cum], axis=1), axis=1)
    r = {"pm_y1": round(float(monthly[:, :12].mean())), "pm_y2_3": round(float(monthly[:, 12:36].mean())),
         "pm_y1_p10": round(float(np.percentile(cum[:, 11], 10) / 12)), "pm_y1_p90": round(float(np.percentile(cum[:, 11], 90) / 12)),
         "neg_months_y1": round(100.0 * float((monthly[:, :12] <= 0).mean()), 1),
         "path": {str(m): [round(float(np.percentile(cum[:, m - 1], q))) for q in (10, 50, 90)] for m in (1, 3, 6, 12, 24, 36, 60, 120) if m <= months},
         "first_cost": round(first_cost, 2), "budget_1": round(b1, 2), "budget_2": round(b2, 2),
         "ruin_1": round(100.0 * float((dip > b1 + 1e-6).mean()), 1), "ruin_2": round(100.0 * float((dip > b2 + 1e-6).mean()), 1),
         "cash_needed_p50": round(float(np.percentile(dip, 50))), "cash_needed_p95": round(float(np.percentile(dip, 95))),
         "cash_needed_max": round(float(dip.max()))}
    for g in GOALS:
        ms = [first_month(cum[i], g) for i in range(n)]
        hit = [m for m in ms if m is not None]
        r[f"to_{g}"] = {"p_hit": round(100.0 * len(hit) / n, 1), "p_hit_5y": round(100.0 * sum(1 for m in hit if m <= 60) / n, 1),
                        "med": int(np.median(hit)) if len(hit) >= n / 2 else None,
                        "fast_p10": int(np.percentile(hit, 10)) if hit else None,
                        "slow_p90": int(np.percentile([m if m else 10 ** 6 for m in ms], 90)) if hit else None}
    if live_w is not None:
        r["live"] = {"start_med": int(np.median([s for s in live_start if s])) if sum(1 for s in live_start if s) >= n / 2 else None,
                     "p_start": round(100.0 * sum(1 for s in live_start if s) / n, 1),
                     "wealth": {str(m): [round(float(np.percentile(live_w[:, m - 1], q))) for q in (10, 50, 90)] for m in (12, 24, 36, 60, 120) if m <= months}}
        for g in GOALS:
            ms = [first_month(live_w[i], g) for i in range(n)]
            hit = [m for m in ms if m is not None]
            r["live"][f"to_{g}"] = {"p_hit": round(100.0 * len(hit) / n, 1), "p_hit_5y": round(100.0 * sum(1 for m in hit if m <= 60) / n, 1),
                                    "med": int(np.median(hit)) if len(hit) >= n / 2 else None,
                                    "fast_p10": int(np.percentile(hit, 10)) if hit else None}
    return r


def run(n=500, months=120, spans=SPANS, breakers=(False, True), live=True):
    S, BY = U.load()
    horizon = months * MO
    out = {"n": n, "months": months, "offset_sessions": OFFSET, "slots": {k: {kk: v for kk, v in s.items() if kk != "fcfg"} for k, s in SLOTS.items()},
           "order": ORDER, "fleets": list(FLEETS), "tax_prop": TAX_PROP, "tax_live": TAX_LIVE,
           "live_rule": {"trigger": LIVE_TRIGGER, "seed": LIVE_SEED, "add": LIVE_ADD, "risk": LIVE_RISK}, "res": {}, "evals": {}}
    for sp in spans:
        P = U.mc_paths(S, sp, n, length=horizon + 1)
        # the eval scorecard per account type on 60-session paths
        P60 = U.mc_paths(S, sp, 1000, length=60)
        for key in ("m50", "m25"):
            U.PRICE[SLOTS[key]["plan"]] = SLOTS[key]["price"]
            out["evals"].setdefault(key, {})[sp] = U.eval_mc(BY, P60, ecfg(SLOTS[key]["plan"]), plan=SLOTS[key]["plan"], horizon=60)
        for br in breakers:
            tag = f"{sp}{'_breaker' if br else ''}"
            per = np.zeros((len(ORDER), n, horizon))
            stats = [[None] * n for _ in ORDER]
            for j, key in enumerate(ORDER):
                for i, seq in enumerate(P):
                    per[j, i], stats[j][i] = flows(BY, seq, key, OFFSET * j, horizon, breaker=br)
            res = {}
            for N in FLEETS:
                sess = per[:N].sum(axis=0)
                mon = sess.reshape(n, months, MO).sum(axis=2)
                cum = np.cumsum(mon, axis=1)
                lw, ls = None, None
                if live and not br:
                    W = [personal(BY, P[i], mon[i], months) for i in range(n)]
                    lw, ls = np.array([w for w, _ in W]), [s for _, s in W]
                res[str(N)] = summarize(cum, months, lw, ls, first_cost=sum(SLOTS[k]["price"] for k in ORDER[:N]))
                res[str(N)]["evals_y1"] = round(float(np.mean([sum(stats[j][i]["evals"] for j in range(N)) for i in range(n)])) * 12 / months, 1)
                res[str(N)]["fees_total"] = round(float(np.mean([sum(stats[j][i]["fees"] for j in range(N)) for i in range(n)])))
                res[str(N)]["funded_total"] = round(float(np.mean([sum(stats[j][i]["funded"] for j in range(N)) for i in range(n)])), 1)
                res[str(N)]["per_dollar_fee"] = round(float(cum[:, -1].mean()) / max(1.0, res[str(N)]["fees_total"]), 1)
                print(f"{tag:12s} {N:>2} accts  ${res[str(N)]['pm_y1']:>6}/mo y1  ${res[str(N)]['pm_y2_3']:>6}/mo y2-3  "
                      f"ruin {res[str(N)]['ruin_1']:>5}% need p95 ${res[str(N)]['cash_needed_p95']:>5}  100K med {res[str(N)]['to_100000']['med']}  "
                      f"1M med {res[str(N)]['to_1000000']['med']} (5y {res[str(N)]['to_1000000']['p_hit_5y']}%)"
                      + (f"  live 1M med {res[str(N)]['live']['to_1000000']['med']} (5y {res[str(N)]['live']['to_1000000']['p_hit_5y']}%)" if "live" in res[str(N)] else ""),
                      flush=True)
            # per slot type, one account alone over 12 months
            res["slot_alone"] = {}
            for j, key in enumerate(ORDER[:4]):
                if key in res["slot_alone"]:
                    continue
                c = per[j][:, : 12 * MO + OFFSET * j].sum(axis=1)
                fees = np.mean([stats[j][i]["fees"] for i in range(n)]) * 12 / months
                res["slot_alone"][key] = {"y1_net": round(float(c.mean())), "y1_p10": round(float(np.percentile(c, 10))),
                                          "y1_p90": round(float(np.percentile(c, 90))), "fees_y1": round(float(fees)),
                                          "per_fee_dollar": round(float(c.mean()) / max(1.0, float(fees)), 1)}
            if not br:
                res["ladder"] = ladder(BY, P, per, stats, horizon, months, live)
                L = res["ladder"]
                print(f"{tag:12s} ladder    ${L['pm_y1']:>6}/mo y1  ${L['pm_y2_3']:>6}/mo y2-3  ruin {L['ruin_1']}%  need p95 ${L['cash_needed_p95']}  "
                      f"100K med {L['to_100000']['med']}  1M med {L['to_1000000']['med']} (5y {L['to_1000000']['p_hit_5y']}%)"
                      + (f"  live 1M med {L['live']['to_1000000']['med']} (5y {L['live']['to_1000000']['p_hit_5y']}%)" if "live" in L else ""), flush=True)
            out["res"][tag] = res
    U.PRICE.update({"builder50k": 91.80, "builder25k": 63.0})
    return out


def ladder(BY, P, per, stats, horizon, months, live):
    """Result-triggered growth: MFFU's 3 slots from day 1 (as the fixed fleet), slots 4-5 (other-firm 50Ks) the session
    after the first payout, slots 6-10 the session after the running net first reaches $10,000 (each a week apart)."""
    n = len(P)
    mon_all, starts, all_fees, all_funded = [], [], [], []
    for i, seq in enumerate(P):
        tot = per[:3, i].sum(axis=0).copy()
        paid = np.cumsum(np.maximum(tot, 0))
        t1 = int(np.argmax(paid > 0)) + 1 if (paid > 0).any() else None
        fees = sum(stats[j][i]["fees"] for j in range(3))
        fund = sum(stats[j][i]["funded"] for j in range(3))
        st_i = {}
        if t1 is not None:
            for q, j in enumerate(LADDER["first_pay"]):
                c, s = flows(BY, seq, ORDER[j], t1 + OFFSET * q, horizon)
                tot += c
                fees += s["fees"]
                fund += s["funded"]
                st_i[j] = t1 + OFFSET * q
            cum = np.cumsum(tot)
            t2 = int(np.argmax(cum >= 10000)) + 1 if (cum >= 10000).any() else None
            if t2 is not None:
                for q, j in enumerate(LADDER["net_10k"]):
                    c, s = flows(BY, seq, ORDER[j], t2 + OFFSET * q, horizon)
                    tot += c
                    fees += s["fees"]
                    fund += s["funded"]
                    st_i[j] = t2 + OFFSET * q
        mon_all.append(tot.reshape(months, MO).sum(axis=1))
        starts.append(st_i)
        all_fees.append(fees)
        all_funded.append(fund)
    mon = np.array(mon_all)
    cum = np.cumsum(mon, axis=1)
    lw, ls = None, None
    if live:
        W = [personal(BY, P[i], mon[i], months) for i in range(n)]
        lw, ls = np.array([w for w, _ in W]), [s for _, s in W]
    r = summarize(cum, months, lw, ls, first_cost=sum(SLOTS[k]["price"] for k in ORDER[:3]))
    for j, lab in ((3, "acct4_month"), (5, "acct6_month")):
        got = [s[j] / MO for s in starts if j in s]
        r[lab] = {"p": round(100.0 * len(got) / n, 1), "med": round(float(np.median(got)), 1) if len(got) >= n / 2 else None,
                  "p90": round(float(np.percentile(got, 90)), 1) if got else None}
    r["fees_total"] = round(float(np.mean(all_fees)))
    r["funded_total"] = round(float(np.mean(all_funded)), 1)
    return r


def check(n=60):
    """flows() == uprisk.life() on the same paths (one slot, 126 sessions)."""
    S, BY = U.load()
    for sp in ("H2", "REF"):
        P = U.mc_paths(S, sp, n)
        for key in ("m50", "m25"):
            s = SLOTS[key]
            U.PRICE[s["plan"]] = s["price"]
            L = U.life(BY, P, ecfg(s["plan"]), s["fcfg"], plan=s["plan"], raw=True)
            for i, seq in enumerate(P):
                c, st = flows(BY, seq, key, 0, U.LEN)
                assert abs(c.sum() - L[i]["net"]) < 1e-6, (sp, key, i, c.sum(), L[i]["net"])
                assert st["evals"] == L[i]["evals"] and st["funded"] == L[i]["funded"], (sp, key, i)
    U.PRICE.update({"builder50k": 91.80, "builder25k": 63.0})
    print(f"check ok: flows == uprisk.life on {n} paths x 2 spans x 2 plans")


def main():
    a = sys.argv[1:]
    if a and a[0] == "check":
        check()
        return
    n = int(a[a.index("--n") + 1]) if "--n" in a else 500
    months = int(a[a.index("--months") + 1]) if "--months" in a else 120
    if "--quick" in a:
        n, months = 60, 36
    out = run(n, months)
    if "--quick" not in a:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1)
        print("wrote", OUT)


if __name__ == "__main__":
    main()
