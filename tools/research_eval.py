"""The eval game on the LOCKED strategy (study "eval", runs eval_*, research/writeups/eval-game.md).

  python tools/research_eval.py all      # every table printed (markdown), research/lab/eval_game.json, runs eval_* saved
  python tools/research_eval.py quick    # tables only, nothing saved

What it does (no engine replay: it reads run "baseline" = the exact live-loop replay with the live sizing, costs included,
1,278 sessions Nov 2021 - Oct 2026, one line per session: day P&L, worst open P&L, trades):
  1. plans      MFFU Builder 50K vs the add-on ($1.5k MLL) vs the other 50K plans in engine/analytics.PLANS: a fresh eval on
                every session (pass / fail within 2 weeks, 1 month, 3 months), back-to-back chains from 20 start days
                (passes and fails a year, evals bought per pass, sessions and fees per funded account).
  2. consistency  the "best day <= X% of profit" pass rule (MFFU Builder does not apply it to the eval; Lucid 50%, Topstep 55%,
                Tradeify Select 40% do): how many passes it delays, by how many sessions, how many it turns into fails.
  3. timing     when to start an eval: cold-streak state at the start (known from the shadow ledger), after a winning / losing /
                flat day, after a winning / losing week, first session of the week / month. Pass / fail odds by start condition.
  4. two        two evals at once on independent accounts with the same trades, the second one started 0-20 sessions later:
                sessions until the FIRST funded account and the fees paid, vs one account at a time.
  5. after_fail after a failed eval: sessions and evals until the next pass.
  6. payouts    the funded stage (buffer, payout min / max, 50% consistency, 80% split as in PLANS): months to the first payout,
                to the first $2,000 payout and to $2,000 in the trader's pocket, accounts blown before the first payout.
Every start uses only what was known then (finished sessions, the cold-streak state at 09:30). Evals started on every session
overlap, so the effective sample is far smaller than the number of starts; 2026 has 198 sessions and almost no fails.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import runlib as rl                       # noqa: E402
from engine.analytics import PLANS, simulate_eval    # noqa: E402

ET = ZoneInfo("America/New_York")
SPANS = {"2026": ("2026-01-01", "2026-12-31"), "2021-25": ("2021-01-01", "2025-12-31"), "all": ("2000-01-01", "2100-01-01")}
HORIZON = 60
SESS_PER_MONTH = 21.0
LAB = os.path.join(ROOT, "research", "lab")
WRITEUP = "research/writeups/eval-game.md"
# What each eval costs (engine/analytics PLANS "price" strings made numeric; re-check before buying).
#   monthly: a subscription paid every month the chain runs; one_time: paid per eval; activation: paid once per pass.
PRICES = {
    "builder_50k": {"monthly": 153.0, "coupon": 100.0, "activation": 0.0},
    "builder_50k_addon": {"monthly": 125.0, "coupon": 125.0, "activation": 0.0},
    "topstep_50k": {"monthly": 49.0, "coupon": 49.0, "activation": 149.0},
    "tradeify_select_50k": {"one_time": 165.0, "activation": 0.0},
    "tradeify_growth_50k": {"one_time": 145.0, "activation": 0.0},
    "lucid_flex_50k": {"one_time": 146.0, "coupon": 100.0, "activation": 0.0},
    "apex_50k": {"one_time": 197.0, "activation": 129.0},
}
BUILDER = PLANS["builder_50k"]


# ------------------------------------------------------------------------------------------------ data
def session_ts(day):
    y, m, d = (int(x) for x in day.split("-"))
    return int(dt.datetime(y, m, d, 9, 30, tzinfo=ET).timestamp())


def load():
    r = rl.load("baseline")
    days = [dict(zip(r["day_cols"], d)) for d in r["days"]]
    trades = [dict(zip(r["trade_cols"], a)) for a in r["trades"]]
    for t in trades:
        t["half"] = bool(t["half"])
        t["low"] = -min(float(t.get("mae") or 0), max(1.0, -float(t["r"]))) * float(t["risk_pts"]) * 2.0 * int(t["qty"])
    sess = [d["date"] for d in days]
    raw = rl.replay(quiet=True)
    raw_sorted = sorted(raw["trades"], key=lambda t: t["entry_t"])
    cold = np.array([rl.cold_status(raw_sorted, session_ts(d), rl.LIVE_EQF)[0] < 1 for d in sess])
    return {"run": r, "days": days, "trades": trades, "sess": sess, "pnl": np.array([d["pnl"] for d in days]),
            "low": np.array([d["low"] for d in days]), "ntr": np.array([d["trades"] for d in days]), "cold": cold}


def span_idx(D, name):
    a, z = SPANS[name]
    return [i for i, s in enumerate(D["sess"]) if a <= s <= z]


def ev(P, L, plan, k, horizon=None):
    end = len(P) if horizon is None else min(len(P), k + horizon)
    return simulate_eval(list(P[k:end]), plan, list(L[k:end]))


def pct(c, n):
    return round(100.0 * c / n, 1) if n else None


def med(xs):
    return float(np.median(xs)) if len(xs) else None


def mean(xs, nd=1):
    return round(float(np.mean(xs)), nd) if len(xs) else None


def months(sessions):
    return round(sessions / SESS_PER_MONTH, 1) if sessions is not None else None


# ------------------------------------------------------------------------------------------------ 1. plans
def rolling(P, L, plan, horizon=HORIZON):
    res = [ev(P, L, plan, k, horizon) for k in range(len(P))]
    n = len(res)
    out = {"n": n}
    for H in (10, 15, 20, 30, 60):
        out[f"p{H}"] = pct(sum(1 for r in res if r["result"] == "PASS" and r["days"] <= H), n)
        out[f"f{H}"] = pct(sum(1 for r in res if r["result"] == "FAIL" and r["days"] <= H), n)
    out["open60"] = round(100 - out["p60"] - out["f60"], 1)
    passes = [r["days"] for r in res if r["result"] == "PASS"]
    fails = [r["days"] for r in res if r["result"] == "FAIL"]
    out["pass_med"] = med(passes); out["fail_med"] = med(fails)
    out["slow_pass"] = pct(sum(1 for d in passes if d > 15), len(passes))
    return out, res


def chain(P, L, plan, k0):
    """Back-to-back evals from session k0 (a new one the session after each pass or fail) until the data runs out.
    Returns [(result, days, start)], and the index where the last (open) eval started."""
    k, out = k0, []
    while k < len(P):
        r = ev(P, L, plan, k)
        if r["result"] == "OPEN":
            break
        out.append((r["result"], r["days"], k)); k += r["days"]
    return out, k


def b2b(P, L, plan, offsets=range(0, 100, 5)):
    """Chains from 20 different first days: passes / fails a year, evals bought per pass, sessions per funded account."""
    Pc = Fc = 0; yrs = 0.0; per_funded, evals_per_funded = [], []
    for k0 in offsets:
        if k0 >= len(P):
            continue
        ch, _ = chain(P, L, plan, k0)
        Pc += sum(1 for r, _, _ in ch if r == "PASS"); Fc += sum(1 for r, _, _ in ch if r == "FAIL")
        yrs += (len(P) - k0) / 252.0
        prev, bought = k0, 0
        for r, d, k in ch:
            bought += 1
            if r == "PASS":
                per_funded.append(k + d - prev); evals_per_funded.append(bought); prev, bought = k + d, 0
    return {"pass_yr": round(Pc / yrs, 2) if yrs else None, "fail_yr": round(Fc / yrs, 2) if yrs else None,
            "evals_per_pass": round((Pc + Fc) / Pc, 2) if Pc else None, "passes": Pc, "fails": Fc,
            "sess_per_funded_med": med(per_funded), "sess_per_funded_mean": mean(per_funded),
            "evals_per_funded_mean": mean(evals_per_funded, 2)}


def fees(plan_key, bb):
    """$ of eval fees per funded account: subscription plans pay every month of the chain, one-time plans pay per eval."""
    pr = PRICES[plan_key]
    if bb["sess_per_funded_mean"] is None:
        return None, None
    m = bb["sess_per_funded_mean"] / SESS_PER_MONTH
    if "monthly" in pr:
        list_ = m * pr["monthly"] + pr["activation"]
        coupon = m * pr.get("coupon", pr["monthly"]) + pr["activation"]
    else:
        list_ = bb["evals_per_funded_mean"] * pr["one_time"] + pr["activation"]
        coupon = bb["evals_per_funded_mean"] * pr.get("coupon", pr["one_time"]) + pr["activation"]
    return round(list_), round(coupon)


def study_plans(D):
    out = {}
    for span in ("2026", "2021-25", "all"):
        ix = span_idx(D, span); P, L = D["pnl"][ix], D["low"][ix]
        out[span] = {}
        for key, plan in PLANS.items():
            ro, _ = rolling(P, L, plan)
            bb = b2b(P, L, plan)
            fl, fc = fees(key, bb)
            out[span][key] = {"name": plan["name"], "rolling": ro, "b2b": bb, "fees_list": fl, "fees_coupon": fc,
                              "automation": plan.get("automation"), "price": plan.get("price")}
    return out


# ------------------------------------------------------------------------------------------------ 2. consistency
def study_consistency(D, levels=(0.5, 0.4, 0.55), horizon=120):
    out = {}
    for span in ("2026", "2021-25", "all"):
        ix = span_idx(D, span); P, L = D["pnl"][ix], D["low"][ix]
        base = [ev(P, L, BUILDER, k, horizon) for k in range(len(P))]
        bp = [k for k, r in enumerate(base) if r["result"] == "PASS"]
        row = {"n_starts": len(P), "n_pass_base": len(bp), "pass_med_base": med([base[k]["days"] for k in bp])}
        # share of the pass-time profit made on the best single day
        shares = []
        for k in bp:
            d = base[k]["days"]; seg = P[k:k + d]
            shares.append(float(seg.max() / seg.sum()))
        row["best_day_share_med"] = round(100 * med(shares), 1) if shares else None
        row["best_day_share_p90"] = round(100 * float(np.percentile(shares, 90)), 1) if shares else None
        for c in levels:
            plan = {**BUILDER, "eval_consistency": c}
            res = [ev(P, L, plan, k, horizon) for k in range(len(P))]
            same = delayed = to_fail = to_open = 0; delays = []
            for k in bp:
                r = res[k]
                if r["result"] == "PASS":
                    if r["days"] == base[k]["days"]:
                        same += 1
                    else:
                        delayed += 1; delays.append(r["days"] - base[k]["days"])
                elif r["result"] == "FAIL":
                    to_fail += 1
                else:
                    to_open += 1
            n = len(bp) or 1
            row[f"c{int(c * 100)}"] = {"same": pct(same, n), "delayed": pct(delayed, n), "to_fail": pct(to_fail, n),
                                       "to_open": pct(to_open, n), "delay_med": med(delays), "delay_mean": mean(delays),
                                       "delay_p90": float(np.percentile(delays, 90)) if delays else None,
                                       "pass_med": med([r["days"] for r in res if r["result"] == "PASS"]),
                                       "p20": pct(sum(1 for r in res if r["result"] == "PASS" and r["days"] <= 20), len(P)),
                                       "p20_base": pct(sum(1 for r in base if r["result"] == "PASS" and r["days"] <= 20), len(P)),
                                       "p60": pct(sum(1 for r in res if r["result"] == "PASS" and r["days"] <= 60), len(P)),
                                       "p60_base": pct(sum(1 for r in base if r["result"] == "PASS" and r["days"] <= 60), len(P))}
        out[span] = row
    return out


# ------------------------------------------------------------------------------------------------ 3. start timing
def conditions(D):
    sess, pnl, ntr, cold = D["sess"], D["pnl"], D["ntr"], D["cold"]
    N = len(sess)
    wd = [dt.date.fromisoformat(s).weekday() for s in sess]

    def prev_any(g, a, b):   # cold at any session in [g-b, g-a)
        lo, hi = max(0, g - b), max(0, g - a)
        return bool(cold[lo:hi].any()) if hi > lo else False

    C = collections.OrderedDict()
    C["every session"] = lambda g: True
    C["full size at the start (not in a cold streak)"] = lambda g: not cold[g]
    C["in a cold streak at the start"] = lambda g: bool(cold[g])
    C["cold streak ended within the last 5 sessions"] = lambda g: not cold[g] and prev_any(g, 0, 5)
    C["cold streak ended 6-20 sessions ago"] = lambda g: not cold[g] and not prev_any(g, 0, 5) and prev_any(g, 5, 20)
    C["full size for 20+ sessions"] = lambda g: g >= 20 and not cold[g] and not prev_any(g, 0, 20)
    C["after a winning day"] = lambda g: g > 0 and pnl[g - 1] > 0
    C["after a losing day"] = lambda g: g > 0 and pnl[g - 1] < 0
    C["after a day without a trade"] = lambda g: g > 0 and ntr[g - 1] == 0
    C["after a winning week (last 5 sessions > 0)"] = lambda g: g >= 5 and pnl[g - 5:g].sum() > 0
    C["after a losing week (last 5 sessions < 0)"] = lambda g: g >= 5 and pnl[g - 5:g].sum() < 0
    C["first session of the week"] = lambda g: g == 0 or wd[g] < wd[g - 1] or (dt.date.fromisoformat(sess[g]) - dt.date.fromisoformat(sess[g - 1])).days >= 3
    C["a Monday"] = lambda g: wd[g] == 0
    C["mid-week (Tue-Fri, not the first session)"] = lambda g: not C["first session of the week"](g)
    C["first session of the month"] = lambda g: g == 0 or sess[g][:7] != sess[g - 1][:7]
    C["not the first session of the month"] = lambda g: not C["first session of the month"](g)
    return C


def study_timing(D):
    C = conditions(D)
    out = {}
    for span in ("2026", "2021-25", "all"):
        ix = span_idx(D, span); P, L = D["pnl"][ix], D["low"][ix]
        res = [ev(P, L, BUILDER, k, HORIZON) for k in range(len(P))]
        rows = collections.OrderedDict()
        for name, fn in C.items():
            sel = [j for j, g in enumerate(ix) if fn(g)]
            R = [res[j] for j in sel]; n = len(R)
            if not n:
                rows[name] = {"n": 0}; continue
            passes = [r["days"] for r in R if r["result"] == "PASS"]
            fails = [r for r in R if r["result"] == "FAIL"]
            dec = len(passes) + len(fails)
            rows[name] = {"n": n, "p10": pct(sum(1 for d in passes if d <= 10), n), "f10": pct(sum(1 for r in fails if r["days"] <= 10), n),
                          "p20": pct(sum(1 for d in passes if d <= 20), n), "f20": pct(sum(1 for r in fails if r["days"] <= 20), n),
                          "p60": pct(len(passes), n), "f60": pct(len(fails), n), "open60": pct(n - dec, n),
                          "pass_share_decided": pct(len(passes), dec), "pass_med": med(passes)}
        out[span] = rows
    return out


# ------------------------------------------------------------------------------------------------ 4. two accounts, 5. after a fail
def first_pass(P, L, plan, k):
    """Chain from k until the first pass: (sessions from k to the pass, evals bought incl. the pass) or (None, bought) if the
    data ends first."""
    j, bought = k, 0
    while j < len(P):
        r = ev(P, L, plan, j)
        if r["result"] == "OPEN":
            return None, bought + 1
        bought += 1; j += r["days"]
        if r["result"] == "PASS":
            return j - k, bought
    return None, bought


def study_two(D, lags=(0, 5, 10, 20)):
    out = {}
    for span in ("2026", "2021-25", "all"):
        ix = span_idx(D, span); P, L = D["pnl"][ix], D["low"][ix]
        fp = [first_pass(P, L, BUILDER, k) for k in range(len(P))]
        res = {}
        single = [fp[k][0] for k in range(len(P))]
        n = len(P)
        for lag in lags:
            T, F, both, months_paid = [], 0, 0, []
            cens = 0
            for k in range(n):
                a = single[k]
                b = single[k + lag] if k + lag < n else None
                b_abs = (b + lag) if b is not None else None
                cands = [x for x in (a, b_abs) if x is not None]
                if not cands:
                    cens += 1; continue
                t = min(cands); T.append(t)
                # months of subscription paid by both accounts until the first funded moment (B starts `lag` sessions later)
                months_paid.append((t + max(0, t - lag)) / SESS_PER_MONTH if lag > 0 else 2 * t / SESS_PER_MONTH)
                if a is not None and b_abs is not None and abs(a - b_abs) <= 60:
                    both += 1
            T = np.array(T)
            res[f"lag{lag}"] = {"n": n, "censored_pct": pct(cens, n), "first_funded_med": med(T), "first_funded_mean": mean(T),
                                "first_funded_p90": float(np.percentile(T, 90)) if len(T) else None,
                                "funded_3m_pct": pct(int((T <= 63).sum()), n), "funded_6m_pct": pct(int((T <= 126).sum()), n),
                                "months_fees_mean": mean(months_paid, 2), "fees_list": round(float(np.mean(months_paid)) * PRICES["builder_50k"]["monthly"]) if len(months_paid) else None,
                                "both_funded_within_60_pct": pct(both, n)}
        S = np.array([x for x in single if x is not None])
        mp = [x / SESS_PER_MONTH for x in S]
        res["single"] = {"n": n, "censored_pct": pct(sum(1 for x in single if x is None), n), "first_funded_med": med(S),
                         "first_funded_mean": mean(S), "first_funded_p90": float(np.percentile(S, 90)) if len(S) else None,
                         "funded_3m_pct": pct(int((S <= 63).sum()), n), "funded_6m_pct": pct(int((S <= 126).sum()), n),
                         "months_fees_mean": mean(mp, 2), "fees_list": round(float(np.mean(mp)) * PRICES["builder_50k"]["monthly"]) if mp else None,
                         "evals_mean": mean([fp[k][1] for k in range(n) if fp[k][0] is not None], 2)}
        out[span] = res
    return out


def study_after_fail(D):
    out = {}
    for span in ("2026", "2021-25", "all"):
        ix = span_idx(D, span); P, L = D["pnl"][ix], D["low"][ix]
        n_fail = 0; gaps, evals, next_pass, cens = [], [], 0, 0
        fail_days = []
        for k in range(len(P)):
            r = ev(P, L, BUILDER, k)
            if r["result"] != "FAIL":
                continue
            n_fail += 1; fail_days.append(r["days"])
            kf = k + r["days"]
            g, b = first_pass(P, L, BUILDER, kf)
            if g is None:
                cens += 1; continue
            gaps.append(g); evals.append(b); next_pass += b == 1
        G = np.array(gaps)
        out[span] = {"n_starts": len(P), "n_fail": n_fail, "fail_pct": pct(n_fail, len(P)), "fail_days_med": med(fail_days),
                     "censored_pct": pct(cens, n_fail), "gap_med": med(G), "gap_mean": mean(G), "gap_p90": float(np.percentile(G, 90)) if len(G) else None,
                     "gap_months_med": months(med(G)), "gap_months_mean": months(mean(G)) if len(G) else None,
                     "evals_mean": mean(evals, 2), "next_eval_passes_pct": pct(next_pass, len(gaps)),
                     "within_3m_pct": pct(int((G <= 63).sum()), len(gaps)) if len(G) else None}
    return out


# ------------------------------------------------------------------------------------------------ 6. payouts
def funded_path(P, L, plan, k, horizon=None, cons=True, intraday=True):
    """The funded stage from session k: balance starts at 0, MLL -mll trailing EOD and locking at +lock_above, payouts as in
    engine/analytics.funded_payouts (buffer, payout_min / max, consistency, split, payout_min_days)."""
    end = len(P) if horizon is None else min(len(P), k + horizon)
    bal = peak = 0.0; mll = -plan["mll"]
    lock = plan["lock_above"] if plan.get("lock_above") is not None else float("inf")
    cycle, last, paid, events = [], 0.0, 0.0, []
    for j in range(k, end):
        if intraday and bal + L[j] <= mll:
            return {"blown": j - k + 1, "events": events, "paid": paid, "sessions": j - k + 1}
        bal += P[j]
        if bal <= mll:
            return {"blown": j - k + 1, "events": events, "paid": paid, "sessions": j - k + 1}
        peak = max(peak, bal); mll = min(max(mll, peak - plan["mll"]), lock)
        if P[j] != 0:
            cycle.append(P[j])
        pc = bal - last; qual = sum(1 for x in cycle if x > 0); best = max(cycle) if cycle else 0.0
        ok_cons = (not cons) or best <= plan["consistency"] * pc
        if bal >= plan["buffer"] + plan["payout_min"] and pc >= plan["payout_min"] and qual >= plan["payout_min_days"] and pc > 0 and ok_cons:
            amt = min(plan["payout_max"], bal - plan["buffer"])
            if amt >= plan["payout_min"]:
                paid += amt * plan["split"]; bal -= amt; last = bal; cycle = []
                events.append({"session": j - k + 1, "amount": round(amt), "to_trader": round(amt * plan["split"])})
    return {"blown": None, "events": events, "paid": paid, "sessions": end - k}


def _payout_stats(P, L, plan, horizon, cons):
    n = len(P)
    first, first_amt, first2k, cum2k, blown_before, blown_sess, cens_first = [], [], [], [], 0, [], 0
    paid_6m, paid_12m, n_payouts_12m = [], [], []
    for k in range(n):
        f = funded_path(P, L, plan, k, horizon, cons=cons)
        ev_ = f["events"]
        if ev_:
            first.append(ev_[0]["session"]); first_amt.append(ev_[0]["amount"])
        elif f["blown"]:
            blown_before += 1; blown_sess.append(f["blown"])
        else:
            cens_first += 1
        big = [e["session"] for e in ev_ if e["amount"] >= plan["payout_max"]]
        if big:
            first2k.append(big[0])
        s = 0.0
        for e in ev_:
            s += e["to_trader"]
            if s >= 2000:
                cum2k.append(e["session"]); break
        if k + 126 <= n:
            paid_6m.append(sum(e["to_trader"] for e in ev_ if e["session"] <= 126))
        if k + 252 <= n:
            paid_12m.append(sum(e["to_trader"] for e in ev_ if e["session"] <= 252))
            n_payouts_12m.append(sum(1 for e in ev_ if e["session"] <= 252))
    F = np.array(first); C2 = np.array(cum2k); B2 = np.array(first2k)
    return {"first_payout_pct": pct(len(F), n), "first_payout_med": med(F), "first_payout_months_med": months(med(F)),
            "first_payout_mean": mean(F), "first_payout_p90": float(np.percentile(F, 90)) if len(F) else None,
            "first_within_3m_pct": pct(int((F <= 63).sum()), n), "first_within_6m_pct": pct(int((F <= 126).sum()), n),
            "first_amount_med": med(first_amt), "first_amount_mean": mean(first_amt, 0),
            "first_is_2k_pct": pct(sum(1 for a in first_amt if a >= plan["payout_max"]), len(first_amt)),
            "blown_before_first_pct": pct(blown_before, n), "blown_sess_med": med(blown_sess), "open_no_payout_pct": pct(cens_first, n),
            "first2k_pct": pct(len(B2), n), "first2k_med": med(B2), "first2k_months_med": months(med(B2)),
            "first2k_within_6m_pct": pct(int((B2 <= 126).sum()), n), "first2k_within_12m_pct": pct(int((B2 <= 252).sum()), n),
            "cum2k_pct": pct(len(C2), n), "cum2k_med": med(C2), "cum2k_months_med": months(med(C2)),
            "cum2k_within_6m_pct": pct(int((C2 <= 126).sum()), n), "cum2k_within_12m_pct": pct(int((C2 <= 252).sum()), n),
            "n_starts_6m": len(paid_6m), "paid_6m_med": med(paid_6m), "paid_6m_mean": mean(paid_6m, 0),
            "zero_paid_6m_pct": pct(sum(1 for x in paid_6m if x == 0), len(paid_6m)),
            "n_starts_12m": len(paid_12m), "paid_12m_med": med(paid_12m), "paid_12m_mean": mean(paid_12m, 0),
            "payouts_12m_mean": mean(n_payouts_12m, 2), "zero_paid_12m_pct": pct(sum(1 for x in paid_12m if x == 0), len(paid_12m))}


def study_payouts(D, plan=BUILDER, horizon=252):
    """The funded stage from every session, with the 50% best-day rule of PLANS (cons) and without it (nocons)."""
    out = {}
    for span in ("2026", "2021-25", "all"):
        ix = span_idx(D, span); P, L = D["pnl"][ix], D["low"][ix]
        n = len(P)
        per_month = float(P.sum()) / (n / SESS_PER_MONTH)
        row = {"n_starts": n, "net_per_month": round(per_month),
               "arith_months_to_2k_payout": round((plan["buffer"] + plan["payout_max"]) / per_month, 1) if per_month > 0 else None,
               "cons": _payout_stats(P, L, plan, horizon, True), "nocons": _payout_stats(P, L, plan, horizon, False)}
        delayed, delays, blocked = 0, [], 0
        for k in range(n):
            f = funded_path(P, L, plan, k, horizon, cons=True); g = funded_path(P, L, plan, k, horizon, cons=False)
            if g["events"] and f["events"] and f["events"][0]["session"] > g["events"][0]["session"]:
                delayed += 1; delays.append(f["events"][0]["session"] - g["events"][0]["session"])
            elif g["events"] and not f["events"] and not f["blown"]:
                blocked += 1
        row.update({"cons_delayed_pct": pct(delayed, n), "cons_blocked_pct": pct(blocked, n), "cons_delay_med": med(delays), "cons_delay_mean": mean(delays)})
        out[span] = row
    return out


def study_sample(D):
    """How thin the sample really is: distinct sessions on which the rolling Builder evals end, cold-streak episodes, big days."""
    out = {}
    for span in ("2026", "2021-25", "all"):
        ix = span_idx(D, span); P, L = D["pnl"][ix], D["low"][ix]; cold = D["cold"][ix]
        res = [ev(P, L, BUILDER, k, 120) for k in range(len(P))]
        pass_end = {k + r["days"] for k, r in enumerate(res) if r["result"] == "PASS"}
        fail_end = {k + r["days"] for k, r in enumerate(res) if r["result"] == "FAIL"}
        bp = [k for k, r in enumerate(res) if r["result"] == "PASS"]
        one_day = sum(1 for k in bp if P[k:k + res[k]["days"]].max() >= BUILDER["target"])
        ends = sum(1 for g in range(1, len(cold)) if cold[g - 1] and not cold[g])
        out[span] = {"sessions": len(P), "pass_starts": len(bp), "distinct_pass_sessions": len(pass_end), "fail_starts": sum(1 for r in res if r["result"] == "FAIL"),
                     "distinct_fail_sessions": len(fail_end), "one_day_pass_pct": pct(one_day, len(bp)), "days_1500": int((P >= 1500).sum()),
                     "days_3000": int((P >= 3000).sum()), "cold_streak_ends": ends, "cold_share_pct": round(100 * float(cold.mean()), 1),
                     "biggest_day": round(float(P.max()))}
    return out


# ------------------------------------------------------------------------------------------------ tables
def md(rows, header):
    s = "| " + " | ".join(header) + " |\n|" + "|".join("---:" if i else "---" for i in range(len(header))) + "|\n"
    for r in rows:
        s += "| " + " | ".join("" if v is None else str(v) for v in r) + " |\n"
    return s


def fmt_pf(a, b):
    return f"{a}% / {b}%"


def g(x, nd=0):
    if x is None:
        return "-"
    return f"{x:.{nd}f}" if isinstance(x, float) else str(x)


def tables(R):
    T = {}
    # 1 plans
    for span in ("2026", "2021-25", "all"):
        rows = []
        for key, v in R["plans"][span].items():
            ro, bb = v["rolling"], v["b2b"]
            rows.append([v["name"], fmt_pf(ro["p10"], ro["f10"]), fmt_pf(ro["p20"], ro["f20"]), fmt_pf(ro["p60"], ro["f60"]), g(ro["pass_med"]),
                         f"{g(bb['pass_yr'], 2)} / {g(bb['fail_yr'], 2)}", g(bb["evals_per_pass"], 2), g(months(bb["sess_per_funded_med"]), 1),
                         f"${v['fees_list']:,}" + (f" (${v['fees_coupon']:,})" if v["fees_coupon"] not in (None, v["fees_list"]) else "") if v["fees_list"] is not None else "-"])
        T[f"plans_{span}"] = md(rows, ["plan", "2 weeks pass / fail", "1 month", "3 months", "median sessions to pass", "passes / fails a year",
                                       "evals bought per pass", "median months to funded", "fees per funded account"])
    rows = [[v["name"], v["price"], v["automation"]] for v in R["plans"]["all"].values()]
    T["plans_info"] = md(rows, ["plan", "price", "automation"])
    # 2 consistency
    rows = []
    for span in ("2026", "2021-25", "all"):
        r = R["consistency"][span]
        for c in (50, 40, 55):
            x = r[f"c{c}"]
            rows.append([span, f"{c}%", r["n_pass_base"], f"{x['same']}%", f"{x['delayed']}%", g(x["delay_med"]), g(x["delay_mean"], 1), g(x["delay_p90"]),
                         f"{x['to_fail']}%", f"{x['to_open']}%", f"{x['p20_base']}% -> {x['p20']}%", f"{x['p60_base']}% -> {x['p60']}%",
                         f"{g(r['pass_med_base'])} -> {g(x['pass_med'])}"])
    T["consistency"] = md(rows, ["period", "best day at most", "passes without the rule", "pass the same day", "delayed", "delay: median sessions", "mean",
                                 "1 in 10 worse than", "turn into a fail", "still open after 120 sessions", "passed within 1 month", "within 3 months",
                                 "median sessions to pass"])
    rows = [[span, f"{R['consistency'][span]['best_day_share_med']}%", f"{R['consistency'][span]['best_day_share_p90']}%"] for span in ("2026", "2021-25", "all")]
    T["best_day_share"] = md(rows, ["period", "best day's share of the pass profit: median", "1 in 10 above"])
    # 3 timing
    for span in ("2026", "2021-25", "all"):
        rows = []
        for name, r in R["timing"][span].items():
            if not r["n"]:
                rows.append([name, 0] + ["-"] * 6); continue
            rows.append([name, r["n"], fmt_pf(r["p10"], r["f10"]), fmt_pf(r["p20"], r["f20"]), fmt_pf(r["p60"], r["f60"]), f"{r['open60']}%",
                         g(r["pass_share_decided"]) + "%" if r["pass_share_decided"] is not None else "-", g(r["pass_med"])])
        T[f"timing_{span}"] = md(rows, ["eval started ...", "starts", "2 weeks pass / fail", "1 month", "3 months", "still open after 3 months",
                                        "passes among decided", "median sessions to pass"])
    # 4 two accounts
    rows = []
    for span in ("2026", "2021-25", "all"):
        r = R["two"][span]
        for key, label in (("single", "one account at a time"), ("lag0", "two accounts, same start day"), ("lag5", "second account 5 sessions later"),
                           ("lag10", "second account 10 sessions later"), ("lag20", "second account 20 sessions later")):
            x = r[key]
            rows.append([span, label, g(x["first_funded_med"]), g(months(x["first_funded_med"]), 1), g(x["first_funded_mean"]), g(x["first_funded_p90"]),
                         f"{x['funded_3m_pct']}%", f"{x['funded_6m_pct']}%", f"{x['censored_pct']}%", g(x["months_fees_mean"], 1), f"${x['fees_list']:,}" if x["fees_list"] else "-",
                         f"{x['both_funded_within_60_pct']}%" if "both_funded_within_60_pct" in x else "-"])
    T["two"] = md(rows, ["period", "set-up", "sessions to the first funded account: median", "months", "mean", "1 in 10 worse than", "funded within 3 months",
                         "within 6 months", "no pass before the data ends", "months of fees paid (mean)", "fees at $153 a month", "both accounts funded within 3 months of each other"])
    # 5 after fail
    rows = []
    for span in ("2026", "2021-25", "all"):
        r = R["after_fail"][span]
        rows.append([span, r["n_starts"], r["n_fail"], f"{r['fail_pct']}%", g(r["fail_days_med"]), g(r["gap_med"]), g(r["gap_months_med"], 1), g(r["gap_mean"]),
                     g(r["gap_months_mean"], 1), g(r["gap_p90"]), f"{r['within_3m_pct']}%" if r["within_3m_pct"] is not None else "-",
                     g(r["evals_mean"], 2), f"{r['next_eval_passes_pct']}%" if r["next_eval_passes_pct"] is not None else "-", f"{r['censored_pct']}%" if r["censored_pct"] is not None else "-"])
    T["after_fail"] = md(rows, ["period", "starts", "of which failed", "fail share", "median sessions to the fail", "sessions from the fail to the next pass: median",
                                "months", "mean", "months", "1 in 10 worse than", "next pass within 3 months", "evals bought after the fail (mean)",
                                "the very next eval passes", "no pass before the data ends"])
    # 6 payouts
    rows = []
    for span in ("2026", "2021-25", "all"):
        r0 = R["payouts"][span]
        for var, label in (("cons", "with the 50% best-day rule"), ("nocons", "without it")):
            r = r0[var]
            rows.append([span, label, f"${r0['net_per_month']:,}", g(r0["arith_months_to_2k_payout"], 1), f"{r['first_payout_pct']}%", g(r["first_payout_months_med"], 1),
                         f"{r['first_within_3m_pct']}% / {r['first_within_6m_pct']}%", f"${g(r['first_amount_med'])}", f"{r['first_is_2k_pct']}%",
                         f"{r['first2k_pct']}%", g(r["first2k_months_med"], 1), f"{r['cum2k_pct']}%", g(r["cum2k_months_med"], 1),
                         f"{r['cum2k_within_6m_pct']}% / {r['cum2k_within_12m_pct']}%", f"{r['blown_before_first_pct']}%", g(months(r["blown_sess_med"]), 1),
                         f"{r['open_no_payout_pct']}%"])
    T["payouts"] = md(rows, ["period", "payout rule", "net per month (eval account)", "months to a $2,000 payout at that pace (arithmetic)",
                             "accounts that reach a first payout within 12 months", "months to it (median)", "within 3 / 6 months", "first payout (median $)",
                             "first payout is the $2,000 maximum", "reach a $2,000 payout", "months (median)", "$2,000 in the trader's pocket", "months (median)",
                             "within 6 / 12 months", "blown before any payout", "months to the blow-up (median)", "still waiting at the data end"])
    rows = []
    for span in ("2026", "2021-25", "all"):
        r0 = R["payouts"][span]
        for var, label in (("cons", "with the 50% best-day rule"), ("nocons", "without it")):
            r = r0[var]
            d6 = r["n_starts_6m"] > 0; d12 = r["n_starts_12m"] > 0
            rows.append([span, label, r["n_starts_6m"], f"${g(r['paid_6m_med'])}" if d6 else "-", f"${g(r['paid_6m_mean'])}" if d6 else "-",
                         f"{r['zero_paid_6m_pct']}%" if d6 else "-", r["n_starts_12m"], f"${g(r['paid_12m_med'])}" if d12 else "-", f"${g(r['paid_12m_mean'])}" if d12 else "-",
                         g(r["payouts_12m_mean"], 2) if d12 else "-", f"{r['zero_paid_12m_pct']}%" if d12 else "-"])
    T["payouts_cash"] = md(rows, ["period", "payout rule", "starts with 6 months of data", "cash to the trader in 6 months: median", "mean", "nothing paid in 6 months",
                                  "starts with 12 months of data", "in 12 months: median", "mean", "payouts in 12 months (mean)", "nothing paid in 12 months"])
    rows = [[span, f"{R['payouts'][span]['cons_delayed_pct']}%", f"{R['payouts'][span]['cons_blocked_pct']}%", g(R['payouts'][span]["cons_delay_med"]),
             g(months(R['payouts'][span]["cons_delay_med"]), 1), g(R['payouts'][span]["cons_delay_mean"], 1)] for span in ("2026", "2021-25", "all")]
    T["payouts_cons"] = md(rows, ["period", "first payout delayed by the 50% rule", "blocked for the whole 12 months by it", "delay: median sessions", "months", "mean sessions"])
    # sample
    rows = []
    for span in ("2026", "2021-25", "all"):
        r = R["sample"][span]
        rows.append([span, r["sessions"], r["pass_starts"], r["distinct_pass_sessions"], r["fail_starts"], r["distinct_fail_sessions"], f"{r['one_day_pass_pct']}%",
                     r["days_1500"], r["days_3000"], f"${r['biggest_day']:,}", r["cold_streak_ends"], f"{r['cold_share_pct']}%"])
    T["sample"] = md(rows, ["period", "sessions", "starts that pass (120-session horizon)", "distinct sessions those passes land on", "starts that fail",
                            "distinct fail sessions", "passes that contain a single day >= $3,000", "days >= $1,500", "days >= $3,000", "biggest day",
                            "cold streaks that ended", "sessions spent in a cold streak"])
    return T


# ------------------------------------------------------------------------------------------------ runs
def save_runs(D, R):
    T, sess = D["trades"], D["sess"]
    S = rl.score(T, sess)
    tags = ["eval", "eval-game"]
    note = "Info run: the trades are the baseline's (locked strategy, live sizing). The eval-game numbers are in the verdict, in research/lab/eval_game.json and in the write-up."
    p = R["plans"]; a, b = p["2026"]["builder_50k"], p["2021-25"]["builder_50k"]; ad = p["2021-25"]["builder_50k_addon"]
    rl.save("eval_plans", "Eval game: MFFU Builder 50K vs the add-on vs other 50K plans", "other",
            "Which 50K eval is cheapest to pass with the locked strategy?", params={}, sizing={"rule": "live sizing (locked 2026-10-17)"},
            trades=T, scored=S, status="info", writeup=WRITEUP, tags=tags,
            verdict=(f"Builder 50K: evals bought per pass {a['b2b']['evals_per_pass']} (2026) / {b['b2b']['evals_per_pass']} (2021-25), fees per funded account "
                     f"${a['fees_list']:,} / ${b['fees_list']:,} at list. The $1.5k-MLL add-on fails more (2021-25 1-month fail {ad['rolling']['f20']}% vs "
                     f"{b['rolling']['f20']}%) and needs {ad['b2b']['evals_per_pass']} evals per pass. Full table per plan in the write-up."), notes=note)
    c = R["consistency"]
    rl.save("eval_consistency", "Eval game: the best-day consistency rule on the eval", "other",
            "How often would a best-day <= 50% rule delay a pass, and by how much?", params={}, sizing={"rule": "live sizing"},
            trades=T, scored=S, status="info", writeup=WRITEUP, tags=tags,
            verdict=(f"50% rule (not MFFU Builder's, but Lucid's): 2021-25 {c['2021-25']['c50']['delayed']}% of passes delayed (median {g(c['2021-25']['c50']['delay_med'])} sessions), "
                     f"{c['2021-25']['c50']['to_fail']}% turned into fails; 2026 {c['2026']['c50']['delayed']}% delayed, {c['2026']['c50']['to_fail']}% to fails. "
                     f"Tradeify's 40% rule hurts far more."), notes=note)
    t = R["timing"]
    rl.save("eval_timing", "Eval game: when to start the eval", "timing",
            "Do the cold-streak state, the previous day/week or the calendar change the eval odds at the start?", params={}, sizing={"rule": "live sizing"},
            trades=T, scored=S, status="info", writeup=WRITEUP, tags=tags,
            verdict=(f"Start when the filter is at full size: 2021-25 1-month pass {t['2021-25']['full size at the start (not in a cold streak)']['p20']}% vs "
                     f"{t['2021-25']['in a cold streak at the start']['p20']}% in a cold streak; 2026 {t['2026']['full size at the start (not in a cold streak)']['p20']}% vs "
                     f"{t['2026']['in a cold streak at the start']['p20']}%. Day of week, month start and yesterday's result matter much less. Overlapping starts: read as odds, not proof."),
            notes=note)
    w = R["two"]
    rl.save("eval_two_accounts", "Eval game: two evals at once (same trades)", "other",
            "Does a second account, started a few sessions later, get the first funded account sooner?", params={}, sizing={"rule": "live sizing"},
            trades=T, scored=S, status="info", writeup=WRITEUP, tags=tags,
            verdict=(f"Same trades = same result: two accounts started the same day pass or fail together. Started 10 sessions apart, median sessions to the first funded "
                     f"account {g(w['2021-25']['single']['first_funded_med'])} -> {g(w['2021-25']['lag10']['first_funded_med'])} (2021-25), "
                     f"{g(w['2026']['single']['first_funded_med'])} -> {g(w['2026']['lag10']['first_funded_med'])} (2026), for about twice the fees."), notes=note)
    f = R["after_fail"]
    rl.save("eval_after_fail", "Eval game: after a failed eval, how long until the next pass", "other",
            "After a fail, how many sessions and evals until a pass?", params={}, sizing={"rule": "live sizing"},
            trades=T, scored=S, status="info", writeup=WRITEUP, tags=tags,
            verdict=(f"2021-25: {f['2021-25']['n_fail']} failed starts; median {g(f['2021-25']['gap_med'])} sessions ({g(f['2021-25']['gap_months_med'], 1)} months) from the fail "
                     f"to the next pass, {g(f['2021-25']['evals_mean'], 2)} more evals on average, the very next eval passes {f['2021-25']['next_eval_passes_pct']}% of the time; "
                     f"{f['2021-25']['censored_pct']}% never saw a pass before the data ended. 2026: {f['2026']['n_fail']} fails."), notes=note)
    po = {k: {**v["cons"], "nocons": v["nocons"]} for k, v in R["payouts"].items()}
    rl.save("eval_payouts", "Eval game: the payout path after funding", "other",
            "How long until the first payout, the first $2,000 payout and $2,000 in the trader's pocket?", params={}, sizing={"rule": "live sizing"},
            trades=T, scored=S, status="info", writeup=WRITEUP, tags=tags,
            verdict=(f"Funded Builder 50K (buffer $2,100, payouts $500-2,000, 50% consistency, 80% split): first payout median {g(po['2026']['first_payout_months_med'], 1)} months (2026) / "
                     f"{g(po['2021-25']['first_payout_months_med'], 1)} months (2021-25); $2,000 in the trader's pocket median {g(po['2026']['cum2k_months_med'], 1)} / "
                     f"{g(po['2021-25']['cum2k_months_med'], 1)} months; blown before any payout {po['2026']['blown_before_first_pct']}% / {po['2021-25']['blown_before_first_pct']}%. "
                     f"Without the 50% best-day rule the first payout comes in {g(po['2026']['nocons']['first_payout_months_med'], 1)} / {g(po['2021-25']['nocons']['first_payout_months_med'], 1)} months: "
                     f"the rule is the binding constraint, because the profit comes in a few $3-4k days."),
            notes=note)
    print("saved runs eval_plans, eval_consistency, eval_timing, eval_two_accounts, eval_after_fail, eval_payouts")


def main(cmd="all"):
    t0 = dt.datetime.now()
    D = load()
    R = {"plans": study_plans(D), "consistency": study_consistency(D), "timing": study_timing(D), "two": study_two(D),
         "after_fail": study_after_fail(D), "payouts": study_payouts(D), "sample": study_sample(D)}
    T = tables(R)
    for k, v in T.items():
        print(f"\n### {k}\n{v}")
    print(f"\n{(dt.datetime.now() - t0).seconds}s")
    if cmd == "all":
        os.makedirs(LAB, exist_ok=True)
        rl._dump({"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "source": "run baseline (locked strategy, live sizing)",
                  "plans": {k: {kk: v for kk, v in p.items()} for k, p in PLANS.items()}, "prices": PRICES, "results": R, "tables": T},
                 os.path.join(LAB, "eval_game.json"), indent=1)
        save_runs(D, R)
    return R, T


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "all")
