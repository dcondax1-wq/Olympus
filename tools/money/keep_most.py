"""Keep the most of every payout (2026-11-20, day-taxes). Education, not tax advice.

Owner (2026-11-20): "When we get payouts, I need you to find the best way ... what to do, when to start getting money into
a live account ... maximize how much we keep."

One file, no network, no secrets. Prints / writes research/lab/keep_most.json:
  1. tax(): 2026 / 2027 federal income tax + self-employment tax on a Schedule C profit, with and without a day job, for a
     Maryland (state + county 2.25% / 3.20%) -> the set-aside % per payout at $5k / $15k / $30k / $60k / $100k a year.
  2. ladder: Solo 401(k) room and tax saved, S-corp break-even profit (payroll + extra costs < SE tax saved).
  3. section 1256 (a personal futures account) blended rate vs the same $ as prop income.
  4. live account: risk of ruin at 1 MNQ from the repo's real trades (research/anatomy, costs in), week-block bootstrap,
     per span (2026 Jan-Jun = H1, Jul-Oct = H2, 2021-25), bankrolls $1,000 - $10,000.
  5. waterfall(): the split of a payout the day it lands.
Numbers: IRS Rev. Proc. 2025-32 (2026, incl. the 2025 law) and Rev. Proc. 2026-xx (2027) - sources in
research/writeups/keep-the-most-2026-11-20.md. Run: python -X utf8 tools/money/keep_most.py [--quick]
"""
from __future__ import annotations

import json
import os
import random
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "research", "lab", "keep_most.json")

# ---- federal tables, single filer ---------------------------------------------------------------------------------
# 2026: IRS Rev. Proc. 2025-32 / IR-2025-103 (Oct 9, 2025), SSA 2026 COLA fact sheet; 2027: see YEARS[2027]["src"].
YEARS = {
    2026: {
        "std": 16100.0,
        "brackets": [(12400, .10), (50400, .12), (105700, .22), (201775, .24), (256225, .32), (640600, .35), (None, .37)],
        "ltcg0": 49450.0, "ltcg15": 545500.0,
        "ss_base": 184500.0,
        "k401_deferral": 24500.0, "k401_catchup50": 8000.0, "k415c": 72000.0, "ira": 7500.0,
        "hsa_self": 4400.0, "hsa_family": 8750.0,
        "qbi_threshold": 201750.0,
        "src": "IRS IR-2025-103 + Rev. Proc. 2025-32; IRS Notice 2025-67 (retirement); Rev. Proc. 2025-19 (HSA); SSA 2026 COLA",
    },
}
YEARS[2027] = {
    "std": 16600.0,
    "brackets": [(12800, .10), (52025, .12), (109125, .22), (208325, .24), (264550, .32), (661375, .35), (None, .37)],
    "ltcg0": 51050.0, "ltcg15": 563200.0,
    "ss_base": 192300.0,
    "k401_deferral": 25500.0, "k401_catchup50": 8500.0, "k415c": 75000.0, "ira": 7500.0,
    "hsa_self": 4500.0, "hsa_family": 9000.0,
    "qbi_threshold": 208300.0,
    "src": "IRS IR-2026-133 + Rev. Proc. 2026-35 (Nov 5, 2026); IR-2026-136 + Notice 2026-66 (Nov 12, 2026); Rev. Proc. 2026-24 (HSA); SS base from IRS Pub 15 2027 draft",
}

SE_FACTOR = 0.9235
SS_RATE, MED_RATE, ADD_MED, ADD_MED_AT = 0.124, 0.029, 0.009, 200000.0
NIIT, NIIT_AT = 0.038, 200000.0
# ---- Maryland (owner's state, 2026-11-20; nothing more specific is stored) ----------------------------------------
# State brackets for a single filer after the 2025 Budget Reconciliation and Financing Act (HB 352), the flat standard
# deduction, the personal exemption and its phase-out, the 2% capital-gains surcharge, and the county range.
MD = {
    "brackets": [(1000, .02), (2000, .03), (3000, .04), (100000, .0475), (125000, .05), (150000, .0525), (250000, .055),
                 (500000, .0575), (1000000, .0625), (None, .065)],
    "std": 3350.0,
    "exemption": [(100000, 3200.0), (125000, 1600.0), (150000, 800.0), (None, 0.0)],   # by federal AGI, single
    "cg_surcharge": 0.02, "cg_surcharge_at": 350000.0,
    "local_low": 0.0225, "local_high": 0.032,
    "src": "Maryland Comptroller (marylandtaxes.gov) 2026 rates + HB 352 (2025)",
}


def md_tax(fagi, local, cap_gain=0.0):
    """Maryland state + county tax on a federal AGI (Maryland starts from federal AGI; no lower rate for capital gains,
    60/40 futures included; the 2% surcharge only on net capital gain when FAGI is over $350,000)."""
    ex = next(v for hi, v in MD["exemption"] if hi is None or fagi <= hi)
    base = max(0.0, fagi - MD["std"] - ex)
    t, lo = 0.0, 0.0
    for hi, r in MD["brackets"]:
        top = base if hi is None else min(base, hi)
        if top > lo:
            t += (top - lo) * r
        if hi is None or base <= hi:
            break
        lo = hi
    sur = MD["cg_surcharge"] * cap_gain if fagi > MD["cg_surcharge_at"] else 0.0
    return t + local * base + sur


def state_tax(state, agi, y, cap_gain=0.0):
    """state = a flat rate (float) or ('MD', county_rate)."""
    if isinstance(state, tuple):
        return md_tax(agi, state[1], cap_gain)
    return state * max(0.0, agi - YEARS[y]["std"])


LEVELS = [5000, 15000, 30000, 60000, 100000]
DAY_JOB = 50000.0          # the "with a day job" case: $50,000 W-2 wages
STATE = {"Maryland, county 2.25%": ("MD", 0.0225), "Maryland, county 3.20%": ("MD", 0.032)}
MD_LOW, MD_HIGH = STATE["Maryland, county 2.25%"], STATE["Maryland, county 3.20%"]


def bracket_tax(taxable, y):
    t, lo = 0.0, 0.0
    for hi, r in YEARS[y]["brackets"]:
        top = taxable if hi is None else min(taxable, hi)
        if top > lo:
            t += (top - lo) * r
        if hi is None or taxable <= hi:
            break
        lo = hi
    return t


def marginal(taxable, y):
    for hi, r in YEARS[y]["brackets"]:
        if hi is None or taxable < hi:
            return r
    return .37


def se_tax(profit, wages=0.0, y=2026):
    base = max(0.0, profit) * SE_FACTOR
    if base < 400:
        return 0.0
    ss = SS_RATE * max(0.0, min(base, YEARS[y]["ss_base"] - wages))
    med = MED_RATE * base + ADD_MED * max(0.0, wages + base - max(ADD_MED_AT, wages))
    return ss + med


def tax(profit, wages=0.0, state=0.0, y=2026, qbi=True, pretax_retire=0.0, se_retire=None):
    """Federal + state tax caused by `profit` of Schedule C income on top of `wages`. pretax_retire = traditional Solo
    401(k) / SEP money (lowers income tax, not SE tax). qbi=False is the safe default for the set-aside (QBI for prop
    payouts is likely but unsettled). Returns the total and the parts, all for the WHOLE return minus the wages-only one."""
    def full(p, retire):
        se = se_tax(p, wages, y)
        agi = wages + p - se / 2 - retire
        before_qbi = max(0.0, agi - YEARS[y]["std"])
        q = 0.0
        if qbi and p > 0:
            qbi_income = max(0.0, p - se / 2 - retire)
            q = min(0.2 * qbi_income, 0.2 * before_qbi)
        taxable = max(0.0, before_qbi - q)
        inc = bracket_tax(taxable, y)
        st = state_tax(state, agi, y)
        return {"se": se, "income": inc, "state": st, "qbi": q, "taxable": taxable, "agi": agi}
    a, b = full(profit, pretax_retire), full(0.0, 0.0)
    parts = {k: round(a[k] - b[k], 2) for k in ("se", "income", "state")}
    total = round(sum(parts.values()), 2)
    return {"profit": profit, "wages": wages, "state_rate": state, **parts, "total": total,
            "pct": round(100 * total / profit, 1) if profit else 0.0, "marginal": marginal(a["taxable"], y),
            "qbi": round(a["qbi"], 2), "agi": round(a["agi"], 2)}


def set_aside_table(y=2026):
    rows = []
    for p in LEVELS:
        for job in (0.0, DAY_JOB):
            for sname, s in STATE.items():
                safe = tax(p, job, s, y, qbi=False)
                likely = tax(p, job, s, y, qbi=True)
                rows.append({"profit": p, "day_job": job, "state": sname, "safe_pct": safe["pct"], "safe_total": safe["total"],
                             "with_qbi_pct": likely["pct"], "with_qbi_total": likely["total"], "se": safe["se"],
                             "marginal": safe["marginal"]})
    return rows


def pot_pct(profit, day_job=False, high_county=True, y=2026):
    """The set-aside % in Maryland rounded UP to the next 5 (safe default: no QBI, the highest county rate)."""
    pct = tax(profit, DAY_JOB if day_job else 0.0, MD_HIGH if high_county else MD_LOW, y, qbi=False)["pct"]
    return int(-(-pct // 5) * 5)


# ---- the ladder: Solo 401(k), S-corp ------------------------------------------------------------------------------
def solo401k(profit, y=2026, age50=False):
    se = se_tax(profit, 0.0, y)
    net = max(0.0, profit - se / 2)
    employer = 0.20 * net                     # 25% of W-2 pay for a corporation = 20% of net SE earnings for a sole prop
    employee = min(YEARS[y]["k401_deferral"] + (YEARS[y]["k401_catchup50"] if age50 else 0), net)
    room = min(YEARS[y]["k415c"] + (YEARS[y]["k401_catchup50"] if age50 else 0), employee + employer, net)
    sep = min(employer, YEARS[y]["k415c"])
    return {"profit": profit, "solo401k_max": round(room, 0), "sep_max": round(sep, 0)}


def retire_saving(profit, put_in, wages=0.0, state=0.0, y=2026):
    a = tax(profit, wages, state, y, qbi=True)
    b = tax(profit, wages, state, y, qbi=True, pretax_retire=put_in)
    return round(a["total"] - b["total"], 2)


SCORP_COSTS = {"payroll_service": 600.0, "extra_return_prep": 1000.0, "state_fees_low": 100.0, "state_fees_high": 800.0,
               "unemployment_tax": 420.0}


def scorp(profit, salary_share=0.5, min_salary=30000.0, state_fee=300.0, y=2026, state=None):
    """S-corp vs sole prop: salary = max(min_salary, share x profit) but never more than profit. Payroll tax 15.3% on the
    salary (employer half deductible), the rest is a distribution with no SE tax. QBI shrinks (salary is not QBI)."""
    state = MD_HIGH if state is None else state
    sole = tax(profit, 0.0, state, y, qbi=True)
    sal = min(profit, max(min_salary, salary_share * profit))
    fica = 0.124 * min(sal, YEARS[y]["ss_base"]) + 0.029 * sal
    costs = SCORP_COSTS["payroll_service"] + SCORP_COSTS["extra_return_prep"] + SCORP_COSTS["unemployment_tax"] + state_fee
    k1 = profit - sal - fica / 2 - costs          # employer half of FICA + costs are corporate deductions
    agi = sal + max(0.0, k1)
    before_qbi = max(0.0, agi - YEARS[y]["std"])
    q = min(0.2 * max(0.0, k1), 0.2 * before_qbi)
    inc = bracket_tax(max(0.0, before_qbi - q), y)
    s_total = fica + inc + costs + state_tax(state, agi, y)
    return {"profit": profit, "salary": round(sal), "sole_prop_tax": round(sole["total"]), "scorp_tax_plus_costs": round(s_total),
            "saved": round(sole["total"] - s_total)}


def scorp_break_even(y=2026):
    for p in range(10000, 300001, 1000):
        if scorp(p, y=y)["saved"] > 0:
            return p
    return None


# ---- section 1256 vs prop income ----------------------------------------------------------------------------------
def s1256(gain, wages=0.0, y=2026, state=None):
    """Tax on `gain` of 60/40 futures profit (no SE tax) on top of wages: 60% at the LTCG rate, 40% ordinary; NIIT over
    $200k MAGI. Returns the total and the blended %."""
    std = YEARS[y]["std"]
    st, lt = 0.4 * gain, 0.6 * gain
    base_ord = max(0.0, wages - std)
    ord_with = max(0.0, wages + st - std)          # the standard deduction is used by ordinary income first
    ord_tax = bracket_tax(ord_with, y) - bracket_tax(base_ord, y)
    lt_taxable = max(0.0, wages + gain - std) - ord_with
    stack = ord_with                               # LT gains sit on top of ordinary income
    lt0 = max(0.0, min(lt_taxable, YEARS[y]["ltcg0"] - stack))
    lt20 = max(0.0, (stack + lt_taxable) - max(stack, YEARS[y]["ltcg15"]))
    lt15 = lt_taxable - lt0 - lt20
    lt_tax = 0.15 * lt15 + 0.20 * lt20
    niit = NIIT * max(0.0, min(gain, wages + gain - NIIT_AT))
    st_tax = 0.0
    if state is not None:
        st_tax = state_tax(state, wages + gain, y, cap_gain=gain) - state_tax(state, wages, y)
    total = ord_tax + lt_tax + niit + st_tax
    return {"gain": gain, "total": round(total, 2), "pct": round(100 * total / gain, 1) if gain else 0.0}


def compare_1256(y=2026):
    rows = []
    for p in LEVELS:
        for job in (0.0, DAY_JOB):
            prop = tax(p, job, 0.0, y, qbi=True)
            fut = s1256(p, job, y)
            prop_md = tax(p, job, MD_HIGH, y, qbi=True)
            fut_md = s1256(p, job, y, MD_HIGH)
            rows.append({"amount": p, "day_job": job, "prop_pct": prop["pct"], "prop_tax": prop["total"],
                         "s1256_pct": fut["pct"], "s1256_tax": fut["total"], "kept_more": round(prop["total"] - fut["total"]),
                         "prop_md_tax": prop_md["total"], "s1256_md_tax": fut_md["total"],
                         "kept_more_md": round(prop_md["total"] - fut_md["total"])})
    return rows


# ---- live account: risk of ruin at 1 MNQ --------------------------------------------------------------------------
MNQ_PT = 2.0
EXTRA_COST = 0.0     # the anatomy $ already include commission + slippage, scaled per micro


def load_trades():
    out = defaultdict(list)    # (bot, span) -> [(day, usd at 1 MNQ)]
    for bot in ("lit", "atlas"):
        p = os.path.join(ROOT, "research", "anatomy", f"trades_{bot}.json")
        d = json.load(open(p, encoding="utf-8"))
        c = {k: i for i, k in enumerate(d["cols"])}
        for r in d["rows"]:
            if bot == "lit":
                usd = r[c["usd"]] / max(1, r[c["qty"]])
            else:
                micros = r[c["risk_usd"]] / (r[c["risk_pts"]] * MNQ_PT)
                usd = r[c["usd"]] / micros if micros > 0 else 0.0
            out[(bot, r[c["span"]])].append((r[c["day"]], usd - EXTRA_COST))
    return out


def weeks(trades):
    import datetime as dt
    w = defaultdict(float)
    for day, usd in trades:
        d = dt.date.fromisoformat(day)
        w[d.isocalendar()[:2]] += usd
    return list(w.values())


def span_weeks_count(span):
    return {"H1": 26, "H2": 18, "2021-25": 260}.get(span, 52)


def ruin(week_pnls, n_active_weeks, n_cal_weeks, bank, horizon=52, n=4000, seed=7, floor_share=0.5):
    """Week-block bootstrap: each simulated week is a random calendar week of the span (weeks with no trade count as $0).
    Lost = the balance touches floor_share x bank (you stop and rethink) at any week-end within `horizon` weeks."""
    rng = random.Random(seed)
    pool = list(week_pnls) + [0.0] * max(0, n_cal_weeks - n_active_weeks)
    lost = down = 0
    ends = []
    for _ in range(n):
        b = bank
        hit = False
        for _w in range(horizon):
            b += pool[rng.randrange(len(pool))]
            if b <= floor_share * bank:
                hit = True
                break
        lost += hit
        down += (b < bank)
        ends.append(b - bank)
    ends.sort()
    return {"bank": bank, "lost_half_pct": round(100 * lost / n, 1), "down_after_year_pct": round(100 * down / n, 1),
            "median_year": round(ends[len(ends) // 2]), "bad_10pct_year": round(ends[len(ends) // 10])}


def live_table(quick=False):
    T = load_trades()
    out = {}
    stats = {}
    for span in ("H1", "H2", "2021-25"):
        combo = T[("lit", span)] + T[("atlas", span)]
        for name, tr in (("LIT", T[("lit", span)]), ("ATLAS", T[("atlas", span)]), ("LIT+ATLAS", combo)):
            wk = weeks(tr)
            cal = span_weeks_count(span)
            tot = sum(u for _, u in tr)
            wins = sum(u for _, u in tr if u > 0)
            loss = -sum(u for _, u in tr if u < 0)
            # worst peak-to-trough on the real order
            eq = pk = dd = 0.0
            for _, u in sorted(tr):
                eq += u
                pk = max(pk, eq)
                dd = min(dd, eq - pk)
            stats[f"{name} {span}"] = {"trades": len(tr), "per_week": round(len(tr) / cal, 1), "pf": round(wins / loss, 2) if loss else None,
                                       "usd_month": round(tot / cal * 52 / 12), "max_dd": round(dd)}
            rows = [ruin(wk, len(wk), cal, b, n=1500 if quick else 4000) for b in (1000, 2000, 3000, 5000, 10000)]
            out[f"{name} {span}"] = rows
    return {"stats": stats, "ruin": out}


# ---- the waterfall ------------------------------------------------------------------------------------------------
LIVE_TARGET = 5000.0     # LIT + ATLAS at 1 MNQ each: lose-half in a year 0% (2026-like) / 9% (2021-25-like), live_table()
RESERVE_TARGET = 320.0   # cash for eval buys + re-buys (fleet plan 2026-11-17)


def waterfall(received, pot=30, reserve=10, retire=10, live=20, live_banked=0.0, live_target=LIVE_TARGET,
              reserve_banked=0.0, reserve_target=RESERVE_TARGET):
    """What to do with `received` (what MFFU sent, after its 80/90% cut) the day it lands, in this order:
    1. tax pot `pot`% (set-aside table, rounded up), 2. eval reserve `reserve`% until it holds reserve_target,
    3. retirement `retire`% (Roth IRA / Solo 401(k)), 4. live-account fund `live`% until it holds live_target,
    5. the rest is yours. A bucket that is full gives its share back to you."""
    r = float(received)
    tax_amt = round(r * pot / 100, 2)
    res = round(min(r * reserve / 100, max(0.0, reserve_target - reserve_banked)), 2)
    ret = round(r * retire / 100, 2)
    lv = round(min(r * live / 100, max(0.0, live_target - live_banked)), 2)
    return {"received": r, "tax_pot": tax_amt, "eval_reserve": res, "retirement": ret, "live_fund": lv,
            "yours": round(r - tax_amt - res - ret - lv, 2)}


def main(argv):
    quick = "--quick" in argv
    out = {
        "built": "2026-11-20", "note": "education, not tax advice; single filer; federal + Maryland state + county (2.25% lowest, 3.20% highest)",
        "maryland": {k: v for k, v in MD.items()},
        "years": {str(k): {kk: vv for kk, vv in v.items() if kk != "brackets"} | {"brackets": v["brackets"]} for k, v in YEARS.items()},
        "set_aside_2026": set_aside_table(2026),
        "set_aside_2027": set_aside_table(2027),
        "pot_pct": {f"{p}": {"no_job_low_county": pot_pct(p, False, False), "no_job_high_county": pot_pct(p),
                             "job_low_county": pot_pct(p, True, False), "job_high_county": pot_pct(p, True)} for p in LEVELS},
        "solo401k": [solo401k(p) | {"tax_saved_if_maxed": retire_saving(p, solo401k(p)["solo401k_max"], 0.0, MD_HIGH),
                                    "tax_saved_10pct": retire_saving(p, 0.10 * p, 0.0, MD_HIGH),
                                    "tax_saved_10pct_day_job": retire_saving(p, 0.10 * p, DAY_JOB, MD_HIGH)} for p in LEVELS],
        "scorp": [scorp(p) for p in (30000, 60000, 80000, 100000, 150000)],
        "scorp_break_even": scorp_break_even(),
        "s1256": compare_1256(),
        "live": live_table(quick),
        "waterfall": {"1000": waterfall(800), "5000": waterfall(4000), "1000_buckets_full": waterfall(800, live_banked=LIVE_TARGET, reserve_banked=RESERVE_TARGET)},
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    return out


if __name__ == "__main__":
    o = main(sys.argv[1:])
    print(json.dumps({k: o[k] for k in ("pot_pct", "solo401k", "scorp", "scorp_break_even", "waterfall")}, indent=1))
    print(json.dumps(o["live"]["stats"], indent=1))
    for k, v in o["live"]["ruin"].items():
        print(k, [(r["bank"], r["lost_half_pct"], r["down_after_year_pct"], r["median_year"], r["bad_10pct_year"]) for r in v])
    for r in o["s1256"]:
        print("1256", r)
