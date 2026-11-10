#!/usr/bin/env python3
"""CHRYSOS ("the gold"): the prop-firm eval and payout fleet planner. Money machine #1. PAPER / PLANNING ONLY: it reads published stats and writes one JSON file.
It never trades, never buys anything and never promises income: every dollar is an ESTIMATE from the stored LIT backtests, with a conservative, a base and an optimistic case.

    python tools/money/chrysos.py --out <dir>             # reads research/lit/*.json when present, else the bundled numbers; writes <dir>/chrysos.json
    python tools/money/chrysos.py --out <dir> --fixture   # the bundled sample only (offline, deterministic): status "sample"
    python tools/money/chrysos.py --selftest              # the maths, checked without any file

The page (tools/web_public/chrysos/) reads ../money/chrysos.json and falls back to its own fixture.json (this tool's --fixture output).

What it computes, per account type (Builder 50K, Builder 25K, ATLAS 25K), at the owner's real one-time prices (CLAUDE.md: $91.80, $63, $43, $0 activation):
  * odds: pass / fail / still-open shares of the stored eval runs (research/lit/builder_25k.json: H1, H2, Monte Carlo), turned into three cases;
  * attempts: 1 / p_adj accounts bought per funded account (a failed account is bought again; a reset price is not published, so a new account is assumed);
  * time: sessions to pass (median) and to the first payout, in calendar days (5 sessions = 7 days);
  * money: payout per month once funded (uprisk lifecycle runs, H2 ~ $684 a month to the owner on a 50K, headline ~$915), survival per month, MFFU payout caps;
  * break-even month, 6- and 12-month net, a dated payout calendar and a fleet total (all copies trade the same signals, so they do NOT fail independently).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CASES = ("conservative", "base", "optimistic")
HORIZON = 12                 # months planned
SESSIONS_TO_DAYS = 7 / 5     # 5 trading sessions = 7 calendar days
GAP_DAYS = 14                # one payout request every two weeks at most (MFFU cycle)
FIXED_ASOF = "2026-11-10T00:00:00Z"

# the owner's real one-time prices (CLAUDE.md 2026-10-26). list = MFFU list price, only for the "you save" line.
PLANS = {
    "b50": {"name": "Builder 50K", "price": 91.8, "list": 153.0, "size": 50000, "rules": "builder_50k", "stats": "50k", "scale": 1.0},
    "b25": {"name": "Builder 25K", "price": 63.0, "list": 105.0, "size": 25000, "rules": "builder_25k", "stats": "25k", "scale": 0.5},
    "atlas": {"name": "ATLAS 25K", "price": 43.0, "list": 105.0, "size": 25000, "rules": "builder_25k", "stats": "25k", "scale": 0.5},
}
ORDER = ("b50", "b25", "atlas")

# bundled stats (copied from research/lit on 2026-11-10; the live read replaces them when the files exist). eval: pass / fail / open % and median sessions to pass.
BUNDLED = {
    "limits": {
        "builder_50k": {"target": 3000.0, "mll": 2000.0, "dll": 1000.0, "max_micros": 40, "pay_min": 500.0, "pay_max": 2000.0, "split": 0.8, "max_payouts": 5},
        "builder_25k": {"target": 1500.0, "mll": 1000.0, "dll": 600.0, "max_micros": 20, "pay_min": 250.0, "pay_max": 1000.0, "split": 0.8, "max_payouts": 5},
    },
    "eval": {
        "50k": {"H1": {"pass": 89.9, "fail": 8.7, "open": 1.4, "pass_med": 7.5, "p10": 50.7, "f10": 2.9},
                "H2": {"pass": 89.9, "fail": 8.7, "open": 1.4, "pass_med": 7.5, "p10": 50.7, "f10": 2.9},
                "MC H2": {"pass": 77.1, "fail": 9.0, "open": 13.9, "pass_med": 8.0, "p10": 48.0, "f10": 3.5}},
        "25k": {"H1": {"pass": 73.9, "fail": 2.5, "open": 23.6, "pass_med": 5.5, "p10": 54.6, "f10": 0.8},
                "H2": {"pass": 63.8, "fail": 4.3, "open": 31.9, "pass_med": 5.0, "p10": 50.7, "f10": 0.0},
                "MC H2": {"pass": 70.0, "fail": 6.0, "open": 24.0, "pass_med": 6.0, "p10": 50.0, "f10": 1.0}},
    },
    # funded phase on a 50K: owner payout per month (uprisk lifecycle H1 / H2, REF = 2021-25 reference line) and sessions to the first payout
    "funded": {"H1_month": 761.0, "H2_month": 684.0, "REF_month": 16.0, "headline_month": 915.0, "first_pay_sessions": 26.0, "first_pay_sessions_slow": 52.0,
               "weak_ratio": 0.105, "weak_month": "2026-08", "worst_month_usd": 459.0, "mean_month_usd": 4372.0},
}

# the three cases: how hard each number is pushed against (or for) the owner. Everything is an assumption, written down here.
CASE_RULES = {
    "conservative": {"open_w": 0.5, "fail_x": 2.0, "fail_add": 5.0, "pay_share": 0.40, "survive": 0.92, "time_x": 1.6, "first_pay": "slow", "pass_pick": "worst", "cohort": True, "fail_cycles": 1, "weak_every": 3},
    "base":         {"open_w": 0.25, "fail_x": 1.0, "fail_add": 0.0, "pay_share": 1.00, "survive": 0.97, "time_x": 1.0, "first_pay": "med", "pass_pick": "H2"},
    "optimistic":   {"open_w": 0.0, "fail_x": 0.8, "fail_add": 0.0, "pay_share": 915.0 / 684.0, "survive": 0.99, "time_x": 0.8, "first_pay": "fast", "pass_pick": "best"},
}

# what the owner holds on 2026-11-10 (CLAUDE.md + home.json ids). Prices already paid are sunk: they are shown, not counted again.
DEFAULT_FLEET = [
    {"id": "mffu50k_eval", "plan": "b50", "status": "eval", "label": "Builder 50K (the LIT account)", "paid": 91.8},
    {"id": "acctb", "plan": "atlas", "status": "eval", "label": "ATLAS 25K", "paid": 43.0},
]
DEFAULT_BUDGET = 200.0
MAX_ACCOUNTS = 6    # the fleet is capped: more copies = the same trades, more fees, more to lose at once

NOTES = [
    "Estimate, not a promise. Every dollar below comes from backtests of the LIT rules on past data. Real results will differ and you can lose every fee.",
    "All accounts take the SAME signals, so they win and lose together. Five accounts are not five independent chances.",
    "A failed eval is assumed to be bought again at the same price (MFFU publishes no reset price for one-time plans). Check the real price before you rely on it.",
    "Payouts need the owner present, MFFU's consistency and minimum-day rules and a request every two weeks at most. Rules checked 2026-10-18: re-check before the first payout.",
    "The Cautious case is a stress path, not an average: every copy shares ONE outcome, so the whole cohort fails its first eval together, every account is bought again (a loss month), and only the second try passes. "
    "It then pays 40% of the tested amount, loses 8% of funded accounts a month, and every third month is as weak as the worst real 2026 month (August: $459 against a $4,372 average, about 10%). The 2021-25 reference line pays about nothing.",
]


# ------------------------------------------------------------------------------------------------ helpers
def _num(x, default=None):
    try:
        v = float(x)
        return v if v == v and abs(v) != float("inf") else default
    except (TypeError, ValueError):
        return default


def r2(x):
    return round(float(x) + 0.0, 2)


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def load_stats(root=ROOT, fixture=False):
    """The bundled numbers, with the stored research files laid over them when they exist. Returns (stats, source)."""
    st = json.loads(json.dumps(BUNDLED))
    if fixture:
        return st, "bundled sample"
    used = []
    lit = os.path.join(root, "research", "lit")
    b = _read(os.path.join(lit, "builder_25k.json"))
    if isinstance(b, dict):
        for key, src in (("25k", "C25 (config C scaled)"), ("50k", "_50k_live")):
            blk = b.get(src)
            if not isinstance(blk, dict):
                continue
            for h in ("H1", "H2", "MC H2"):
                e = blk.get(h)
                if isinstance(e, dict) and all(_num(e.get(k)) is not None for k in ("pass", "fail", "pass_med")):
                    st["eval"][key][h] = {k: _num(e.get(k), 0.0) for k in ("pass", "fail", "open", "pass_med", "p10", "f10")}
                    used.append(f"{src}/{h}")
    u = _read(os.path.join(lit, "uprisk_life.json"))
    try:
        life = u["life"]["today__rec"]
        for k, kk in (("H1", "H1_month"), ("H2", "H2_month"), ("REF", "REF_month")):
            v = _num(life[k]["owner_m"])
            if v is not None:
                st["funded"][kk] = v
        v = _num(life["H2"]["first_pay_med"])
        if v:
            st["funded"]["first_pay_sessions_slow"] = v
        used.append("uprisk_life/today__rec")
    except (TypeError, KeyError):
        pass
    ll = _read(os.path.join(root, "research", "runs", "lit_live.json"))
    try:
        mm = {k: _num(v["net"]) for k, v in ll["months"].items() if k.startswith("2026") and _num(v.get("net")) is not None}
        if len(mm) >= 6:
            mean = sum(mm.values()) / len(mm)
            worst_k = min(mm, key=mm.get)
            st["funded"].update({"weak_ratio": round(mm[worst_k] / mean, 4), "weak_month": worst_k, "worst_month_usd": mm[worst_k], "mean_month_usd": round(mean, 1)})
            used.append("lit_live/months 2026")
    except (TypeError, KeyError, AttributeError, ZeroDivisionError):
        pass
    m = _read(os.path.join(lit, "mffu_rules.json"))
    try:
        for p in ("builder_50k", "builder_25k"):
            for k in st["limits"][p]:
                v = _num(m["limits"][p].get(k))
                if v is not None:
                    st["limits"][p][k] = v
        used.append("mffu_rules")
    except (TypeError, KeyError):
        pass
    return st, ("research/lit: " + ", ".join(used)) if used else "bundled sample"


# ------------------------------------------------------------------------------------------------ the maths
def eval_odds(st, plan, case):
    """(p_adj, fail_pct, pass_med_sessions): the chance one bought account becomes funded, after the case's push."""
    cr = CASE_RULES[case]
    runs = list(st["eval"][PLANS[plan]["stats"]].values())
    if cr["pass_pick"] == "worst":
        run = min(runs, key=lambda r: r["pass"])
    elif cr["pass_pick"] == "best":
        run = max(runs, key=lambda r: r["pass"])
    else:
        run = st["eval"][PLANS[plan]["stats"]]["H2"]
    fail = clamp(run["fail"] * cr["fail_x"] + cr["fail_add"], 0.0, 100.0)
    passed = run["pass"] - (cr["fail_add"] if case == "conservative" else 0.0)
    passed = clamp(passed, 1.0, 100.0)
    open_ = max(0.0, run.get("open", 0.0))
    p_adj = passed / (passed + fail + open_ * cr["open_w"])
    return clamp(p_adj, 0.05, 0.99), fail, run["pass_med"] * cr["time_x"]


def funded_month(st, plan, case):
    """Expected payout to the owner per month while the account is funded, in dollars (a 50K figure scaled to the account)."""
    f = st["funded"]
    base = f["H2_month"] * CASE_RULES[case]["pay_share"] if case != "optimistic" else f["headline_month"]
    return base * PLANS[plan]["scale"]


def cohort_days(st):
    """Calendar days of ONE eval cycle that every copy shares in the Cautious case: the slowest plan's median sessions to pass, pushed by the case."""
    cr = CASE_RULES["conservative"]
    return max(eval_odds(st, k, "conservative")[2] for k in ORDER) * SESSIONS_TO_DAYS


def account_case(st, plan, case, owned=False, months=HORIZON):
    """One account type, one case: odds, time, cost, month-by-month cumulative net and the break-even. Money in dollars, ESTIMATES."""
    P = PLANS[plan]
    lim = st["limits"][P["rules"]]
    cr = CASE_RULES[case]
    p_adj, fail_pct, pass_med = eval_odds(st, plan, case)
    attempts = 1.0 / p_adj
    price = P["price"]
    to_funded_days = pass_med * SESSIONS_TO_DAYS + (attempts - 1.0) * pass_med * SESSIONS_TO_DAYS
    cohort = bool(cr.get("cohort"))
    cyc = cohort_days(st)
    if cohort:
        # CORRELATED stress path: the copies trade the same signals, so they share ONE outcome per cycle. The whole cohort fails its first eval together
        # (the fees are lost at the same moment), every copy is bought again, and only the next cycle passes. Not an average of independent chances.
        attempts = 1.0 + cr["fail_cycles"]
        to_funded_days = cyc * attempts
    fp = {"slow": st["funded"]["first_pay_sessions_slow"], "med": st["funded"]["first_pay_sessions"], "fast": st["funded"]["first_pay_sessions"] * 0.6}[cr["first_pay"]]
    first_pay_days = to_funded_days + fp * SESSIONS_TO_DAYS
    rate = funded_month(st, plan, case)
    cap_total = lim["max_payouts"] * lim["pay_max"]
    cap_month = lim["pay_max"] * 30.0 / GAP_DAYS
    rate = min(rate, cap_month)
    first_buy = 0.0 if owned else price
    extra_buys = (attempts - 1.0) * price
    weak = st["funded"].get("weak_ratio", 0.105)
    series, cum_in, inc_s, fee_s = [], 0.0, [], []
    for m in range(0, months + 1):
        t = m * 30.0
        inc = 0.0
        if m > 0:
            lo, hi = (m - 1) * 30.0, t
            live = max(0.0, hi - max(lo, first_pay_days))
            if live > 0:
                mid = (max(lo, first_pay_days) + hi) / 2.0
                surv = cr["survive"] ** max(0.0, (mid - first_pay_days) / 30.0)
                pw = p_adj if not cohort else 1.0
                wk = weak if cohort and cr["weak_every"] and m % cr["weak_every"] == 0 else 1.0     # every 3rd month is as weak as the worst real 2026 month
                inc = min(rate * wk * live / 30.0 * surv * pw, max(0.0, cap_total * pw - cum_in))
        cum_in += inc
        if cohort:
            spent = first_buy + (extra_buys if t >= cyc else 0.0)          # the repurchase lands in the month the cohort fails: a real loss month
        else:
            spent = first_buy + (extra_buys if t >= to_funded_days else extra_buys * (t / max(to_funded_days, 1.0)))
        series.append(r2(cum_in - spent))
        inc_s.append(r2(cum_in))
        fee_s.append(r2(spent + (price if owned else 0.0)))
    be_month = None
    for i in range(1, len(series)):
        if series[i - 1] < 0 <= series[i]:
            frac = (0 - series[i - 1]) / (series[i] - series[i - 1]) if series[i] != series[i - 1] else 0.0
            be_month = r2((i - 1 + frac))
            break
    if be_month is None and series and series[0] >= 0 and not first_buy:
        be_month = 0.0
    cost_exp = first_buy + extra_buys
    return {
        "case": case, "p_funded": r2(p_adj * 100), "fail_pct": r2(fail_pct), "attempts": r2(attempts),
        "days_to_funded": int(round(to_funded_days)), "days_to_first_payout": int(round(first_pay_days)),
        "payout_month": r2(rate * (p_adj if not cohort else (2 + weak) / 3.0)), "cohort_fail": cohort, "payout_month_if_funded": r2(rate), "cost_expected": r2(cost_exp), "cum": series, "income": inc_s, "fees_all": fee_s,
        "net6": series[min(6, months)], "net12": series[min(12, months)], "breakeven_month": be_month, "survive_month": cr["survive"], "payout_cap_total": cap_total,
    }


def build_account(st, plan, owned=False, acc_id=None, label=None, status="candidate", paid=None):
    P = PLANS[plan]
    cases = {c: account_case(st, plan, c, owned=owned) for c in CASES}
    b = cases["base"]
    spend = b["cost_expected"] if not owned else b["cost_expected"]
    roi = b["net12"] / max(spend, P["price"] * 0.5, 1.0)
    return {
        "id": acc_id or plan, "plan": plan, "name": label or P["name"], "status": status, "owned": owned, "price": P["price"], "list": P["list"], "paid": paid if paid is not None else (P["price"] if owned else 0.0),
        "size": P["size"], "cases": cases, "roi12": r2(roi), "sunk": bool(owned),
    }


def score_of(acc):
    """0-100: how good the next dollar is here. Pushed down by the conservative case, never above 90 (it is an estimate)."""
    b, c = acc["cases"]["base"], acc["cases"]["conservative"]
    s = 50 + 28 * (acc["roi12"] / (abs(acc["roi12"]) + 3.0))
    s += 12 if c["net12"] > 0 else -10
    s -= 6 if (b["breakeven_month"] is None or b["breakeven_month"] > 6) else 0
    return int(clamp(round(s), 0, 90))


def risk_of(acc):
    b, c = acc["cases"]["base"], acc["cases"]["conservative"]
    if c["net12"] < 0 and (b["breakeven_month"] is None or b["breakeven_month"] > 6):
        return "high"
    if c["net12"] < 0 or (b["breakeven_month"] or 0) > 4:
        return "med"
    return "low"


def asof_date(asof):
    return dt.datetime.strptime(asof[:10], "%Y-%m-%d").date()


def calendar(accounts, asof, case="base", months=HORIZON):
    """Dated payout requests (the base case): the amount IF the account is funded and the chance it is. Sorted by date."""
    d0 = asof_date(asof)
    out = []
    for a in accounts:
        c = a["cases"][case]
        lim_pay = PLANS[a["plan"]]
        gap_amt = min(c["payout_month_if_funded"] * GAP_DAYS / 30.0, 1e9)
        paid_so_far = 0.0
        for i in range(5):
            day = c["days_to_first_payout"] + i * GAP_DAYS
            if day > months * 30:
                break
            amt = min(gap_amt, c["payout_cap_total"] - paid_so_far)
            if amt <= 0:
                break
            prob = c["p_funded"] / 100.0 * c["survive_month"] ** (i * GAP_DAYS / 30.0)
            out.append({"date": (d0 + dt.timedelta(days=day)).isoformat(), "account": a["name"], "id": a["id"], "usd_if_funded": r2(amt), "chance_pct": r2(prob * 100), "usd_expected": r2(amt * prob), "n": i + 1})
            paid_so_far += amt
        _ = lim_pay
    out.sort(key=lambda e: (e["date"], e["id"]))
    return out


def fleet_totals(accounts):
    t = {}
    for c in CASES:
        cum = [sum(a["cases"][c]["cum"][m] for a in accounts) for m in range(HORIZON + 1)]
        be = None
        for i in range(1, len(cum)):
            if cum[i - 1] < 0 <= cum[i]:
                be = r2(i - 1 + (0 - cum[i - 1]) / (cum[i] - cum[i - 1]))
                break
        t[c] = {"cum": [r2(x) for x in cum], "loss_months": [i for i in range(1, len(cum)) if cum[i] < cum[i - 1] - 0.005], "net6": r2(cum[6]), "net12": r2(cum[12]), "breakeven_month": be,
                "cost_expected": r2(sum(a["cases"][c]["cost_expected"] for a in accounts)), "payout_month": r2(sum(a["cases"][c]["payout_month"] for a in accounts))}
    return t


def plan(st, source, fleet=None, budget=DEFAULT_BUDGET, asof=FIXED_ASOF, status="ok"):
    fleet = fleet if fleet is not None else DEFAULT_FLEET
    owned = [build_account(st, f["plan"], owned=True, acc_id=f["id"], label=f.get("label"), status=f.get("status", "eval"), paid=f.get("paid")) for f in fleet if f.get("plan") in PLANS]
    cands = [build_account(st, k) for k in ORDER]
    for a in cands:
        a["score"], a["risk"] = score_of(a), risk_of(a)
    for a in owned:
        a["score"], a["risk"] = score_of(a), risk_of(a)
    ranked = sorted(cands, key=lambda a: (-a["roi12"], a["price"]))
    buys, left = [], float(budget)
    for a in ranked:
        if len(owned) + len(buys) >= MAX_ACCOUNTS:
            break
        # worth buying only if the base case pays back inside the plan AND the conservative case does not lose more than the fee
        worth = a["cases"]["base"]["net12"] > 0 and a["cases"]["conservative"]["net12"] > -a["cases"]["conservative"]["cost_expected"]
        if worth and a["cases"]["base"]["cost_expected"] <= left:
            buys.append(dict(a, id=a["id"] + f"_next{len(buys) + 1}"))
            left -= a["cases"]["base"]["cost_expected"]
    all_acc = owned + buys
    items = []
    for i, a in enumerate(ranked):
        b, c, o = a["cases"]["base"], a["cases"]["conservative"], a["cases"]["optimistic"]
        pick = any(x["plan"] == a["plan"] for x in buys)
        items.append({
            "title": f"{'Next buy' if pick and i == 0 else 'Buy' if pick else 'Lower priority'}: {a['name']} (${a['price']:.2f})",
            "detail": f"Estimate: {b['p_funded']:.0f}% become funded (base), about ${b['cost_expected']:.0f} in fees per funded account, break-even {fmt_be(b['breakeven_month'])}, 12-month net about ${b['net12']:,.0f} "
                      f"(worst case ${c['net12']:,.0f}, best case ${o['net12']:,.0f}).",
            "usd": b["net12"], "score": a["score"], "risk": a["risk"],
        })
    for a in owned:
        b, c = a["cases"]["base"], a["cases"]["conservative"]
        items.append({"title": f"Keep going: {a['name']} (fee ${a['paid']:.2f} already paid)", "detail": f"Estimate: first payout in about {b['days_to_first_payout']} days (base), then about ${b['payout_month']:,.0f} a month expected; worst case ${c['net12']:,.0f} over 12 months.",
                      "usd": b["net12"], "score": a["score"], "risk": a["risk"]})
    fl = fleet_totals(all_acc)
    cal = calendar(all_acc, asof)
    b12 = fl["base"]["net12"]
    headline = (f"Estimate: the fleet of {len(all_acc)} account{'s' if len(all_acc) != 1 else ''} nets about ${b12:,.0f} over 12 months (worst case ${fl['conservative']['net12']:,.0f}, best case ${fl['optimistic']['net12']:,.0f}); "
                f"break-even {fmt_be(fl['base']['breakeven_month'])}. Not a promise.")
    return {
        "v": 1, "id": "chrysos", "asof": asof, "mode": "paper", "status": status,
        "headline": {"text": headline, "usd_month": r2(b12 / 12.0)},
        "items": items,
        "notes": NOTES + [f"Stats source: {source}. Prices: Builder 50K $91.80, Builder 25K $63, ATLAS 25K $43, one time, $0 activation."],
        "chrysos": {
            "budget": budget, "spent_if_all_bought": r2(sum(a["cases"]["base"]["cost_expected"] for a in buys)), "max_accounts": MAX_ACCOUNTS,
            "prices": {k: {"name": v["name"], "price": v["price"], "list": v["list"], "size": v["size"]} for k, v in PLANS.items()},
            "case_rules": CASE_RULES, "owned": owned, "candidates": cands, "buy_next": [dict(b_, id=b_["id"]) for b_ in buys], "fleet": fl, "calendar": cal,
            "stats": {"eval": st["eval"], "funded": st["funded"]}, "source": source, "horizon_months": HORIZON,
        },
    }


def fmt_be(m):
    if m is None:
        return "not within 12 months"
    if m <= 0:
        return "already"
    return f"in about {m:.1f} months"


def write(out_dir, root=ROOT, fixture=False, fleet=None, budget=DEFAULT_BUDGET, now=None):
    st, source = load_stats(root, fixture)
    asof = FIXED_ASOF if fixture else (now or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    status = "sample" if source == "bundled sample" else "ok"
    doc = plan(st, source, fleet=fleet, budget=budget, asof=asof, status=status)
    if status == "sample":
        doc["demo"] = True
        doc["note"] = "EXAMPLE numbers, not real: a sample plan from bundled test statistics, shown until the site's own chrysos.json exists."
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "chrysos.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, sort_keys=False)
    return path, doc


# ------------------------------------------------------------------------------------------------ selftest
def selftest():
    ok = []

    def chk(name, cond, info=""):
        ok.append(bool(cond))
        print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f" -> {info}"))
    st, src = load_stats(fixture=True)
    chk("bundled stats", src == "bundled sample" and set(st["eval"]) == {"50k", "25k"})
    for k, price in (("b50", 91.8), ("b25", 63.0), ("atlas", 43.0)):
        chk(f"owner price {k}", PLANS[k]["price"] == price)
    p_c, _, _ = eval_odds(st, "b50", "conservative")
    p_b, _, _ = eval_odds(st, "b50", "base")
    p_o, _, _ = eval_odds(st, "b50", "optimistic")
    chk("odds order conservative < base < optimistic", p_c < p_b < p_o, (p_c, p_b, p_o))
    chk("odds are probabilities", all(0 < x < 1 for x in (p_c, p_b, p_o)))
    for k in ORDER:
        a = {c: account_case(st, k, c) for c in CASES}
        chk(f"{k}: net12 conservative <= base <= optimistic", a["conservative"]["net12"] <= a["base"]["net12"] <= a["optimistic"]["net12"], [a[c]["net12"] for c in CASES])
        chk(f"{k}: month 0 equals minus the fee", a["base"]["cum"][0] == -PLANS[k]["price"], a["base"]["cum"][0])
        chk(f"{k}: first payout after funded", a["base"]["days_to_first_payout"] > a["base"]["days_to_funded"] > 0)
        cap = a["base"]["payout_cap_total"]
        tot = a["base"]["cum"][-1] + a["base"]["cost_expected"]
        chk(f"{k}: payouts never above the MFFU cap x odds", tot <= cap * (a["base"]["p_funded"] / 100) + 0.05, (tot, cap))
    ow = account_case(st, "b50", "base", owned=True)
    nw = account_case(st, "b50", "base")
    chk("owned account: the paid fee is sunk (month 0 = 0)", ow["cum"][0] == 0.0 and nw["cum"][0] == -91.8)
    chk("break-even month is None or between 0 and 12", all(account_case(st, k, c)["breakeven_month"] is None or 0 <= account_case(st, k, c)["breakeven_month"] <= 12 for k in ORDER for c in CASES))
    doc = plan(st, src)
    chk("contract keys", all(k in doc for k in ("v", "id", "asof", "mode", "status", "headline", "items", "notes")) and doc["mode"] == "paper" and doc["id"] == "chrysos")
    chk("items shape", all(set(i) == {"title", "detail", "usd", "score", "risk"} and 0 <= i["score"] <= 100 and i["risk"] in ("low", "med", "high") for i in doc["items"]))
    chk("honest: the word estimate in the headline and in every item", "Estimate" in doc["headline"]["text"] and all("Estimate" in i["detail"] for i in doc["items"]))
    chk("no promise words", not any(w in json.dumps(doc).lower() for w in ("guarantee", "risk-free", "sure thing", "you will earn")))
    cal = doc["chrysos"]["calendar"]
    chk("calendar sorted, dated, within 12 months", cal == sorted(cal, key=lambda e: (e["date"], e["id"])) and all(e["date"] <= "2027-11-30" for e in cal) and len(cal) > 0)
    chk("calendar chance <= 100 and expected <= if-funded", all(0 < e["chance_pct"] <= 100 and e["usd_expected"] <= e["usd_if_funded"] for e in cal))
    fc = doc["chrysos"]["fleet"]["conservative"]
    chk("Cautious: net-negative at month 1 and 2 (fees, a failed first cycle, no payout yet)", fc["cum"][1] < 0 and fc["cum"][2] < 0, fc["cum"][:4])
    chk("Cautious: shows a real LOSS month (the whole cohort is bought again at once)", len(fc["loss_months"]) >= 1, fc["loss_months"])
    cc = doc["chrysos"]["candidates"]
    chk("Cautious: every copy shares the same failure moment (one cohort, not independent multiples): same days_to_funded for 25K and 50K", len({a["cases"]["conservative"]["days_to_funded"] for a in cc}) == 1)
    chk("Cautious: every account is bought exactly twice (1 fail + 1 pass), resets repurchased", all(abs(a["cases"]["conservative"]["attempts"] - 2.0) < 1e-9 for a in cc))
    chk("weak month ratio is the worst real 2026 month over the mean (bundled 459 / 4372)", abs(st["funded"]["weak_ratio"] - 459.0 / 4372.0) < 0.01, st["funded"]["weak_ratio"])
    n_acc = len(doc["chrysos"]["owned"]) + len(doc["chrysos"]["buy_next"])
    chk("fleet capped", n_acc <= MAX_ACCOUNTS, n_acc)
    zero = plan(st, src, budget=0.0)
    chk("budget 0 buys nothing", zero["chrysos"]["buy_next"] == [])
    big = plan(st, src, fleet=[], budget=10000.0)
    chk("empty fleet works and the cap holds", len(big["chrysos"]["buy_next"]) <= MAX_ACCOUNTS)
    j = json.dumps(doc)
    chk("serialisable, no NaN", "NaN" not in j and "Infinity" not in j)
    chk("deterministic", json.dumps(plan(st, src)) == j)
    bad = plan(st, src, fleet=[{"id": "x", "plan": "nope"}])
    chk("unknown plan in the fleet is ignored", bad["chrysos"]["owned"] == [])
    bad_n = sum(1 for x in ok if not x)
    print(f"\n{len(ok) - bad_n}/{len(ok)} passed")
    return bad_n == 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="CHRYSOS: prop-firm fleet planner (paper, planning only)")
    ap.add_argument("--out", help="folder for chrysos.json")
    ap.add_argument("--fixture", action="store_true", help="use the bundled sample numbers only (offline, deterministic)")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--budget", type=float, default=DEFAULT_BUDGET, help="dollars of new fees to plan (default 200)")
    ap.add_argument("--fleet", help="JSON file: [{id, plan b50|b25|atlas, status, label, paid}] of the accounts you hold")
    a = ap.parse_args(argv)
    if a.selftest:
        return 0 if selftest() else 1
    if not a.out:
        ap.error("--out is required")
    fleet = _read(a.fleet) if a.fleet else None
    path, doc = write(a.out, fixture=a.fixture, fleet=fleet if isinstance(fleet, list) else None, budget=a.budget)
    print(f"wrote {path} ({doc['status']}): {doc['headline']['text']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
