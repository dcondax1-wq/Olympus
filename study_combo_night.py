"""Confluence-COMBINATION study on real CME futures only (no CFD data), nested week-block walk-forward.

    python -X utf8 study_combo_night.py [--sym NQ] [--check ES] [--from 2026-08-06] [--to 2026-10-16]
                                        [--workers 4] [--train0 4] [--step 2] [--placebo 300] [--out FILE]

What it does
  1. Runs every config of a small grid (9 knobs that already exist in engine.model.DEFAULTS) on --sym and --check,
     flat-ish research sizing (dd_aware off, no daily stop; grade sizing stays on like every earlier study).
  2. Splits the trading days in [--from, --to] into calendar-week blocks. Nested walk-forward: select on weeks
     [0, k) and evaluate untouched on weeks [k, k+step), k = train0, train0+step, ... (last fold takes the leftovers).
     Selection uses only training weeks and requires 2.0-4.5 trades/week there. Four selection rules are tested.
  3. Reports ONLY out-of-sample folds for each rule against the current defaults on the same weeks, the cross-
     instrument check (same chosen config on --check, same weeks), a placebo (engine.robust.placebo) and bootstrap CIs.
  4. Final config per rule = the rule applied to all weeks (what you would deploy) + one-step neighbourhood check +
     MFFU 50K rolling evals with the live risk settings.
Engine code is not modified. Scripts re-run as-is when more CME history is imported (dates are arguments).
"""
from __future__ import annotations

import argparse
import datetime as dt
import itertools
import json
import sys
from multiprocessing import Pool

import numpy as np

from engine import analytics, backtest, robust

RESEARCH = {"dd_aware": False, "daily_max_loss": 1e9, "memory_seed": False}
LIVE = {"dd_aware": True, "daily_max_loss": 600.0, "memory_seed": False}

WINDOWS = {"both": [[570, 690], [810, 930]], "AM": [[570, 690]], "AM+1330-1500": [[570, 690], [810, 900]]}
SPACE = {   # first value of each list = current default
    "min_score": [1, 0, 2],
    "w_htf": [1, 0],
    "w_m15": [-1, 0],
    "w_vwap": [0, 1],
    "grade_skip": ["", "D"],
    "entry_windows": ["both", "AM", "AM+1330-1500"],
    "max_trades_day": [2, 1],
    "stop_after_win": [True, False],
    "min_rr": [1.5, 2.0],
}
KNOBS = list(SPACE)
DEFAULT_KEY = tuple(v[0] for v in SPACE.values())
LO, HI = 2.0, 4.5


def canon(key):
    d = dict(zip(KNOBS, key))
    if d["max_trades_day"] == 1:
        d["stop_after_win"] = True       # irrelevant with one trade a day
    return tuple(d[k] for k in KNOBS)


def to_params(key):
    d = dict(zip(KNOBS, key))
    d["entry_windows"] = WINDOWS[d["entry_windows"]]
    return d


def short(key):
    d = dict(zip(KNOBS, key))
    diff = {k: v for k, v, v0 in zip(KNOBS, key, DEFAULT_KEY) if v != v0}
    return "defaults" if not diff else ", ".join(f"{k}={v!r}" for k, v in diff.items())


def run_one(job):
    sym, key, extra = job
    r = backtest.run(sym, "5m", {**to_params(key), **extra}, light=True)
    tr = [{"day": t["day"], "pnl": float(t["pnl"]), "r": float(t["pnl_r"]), "exit": t["exit_reason"], "grade": t["grade"]}
          for t in r["trades"]]
    days = [{"date": d["date"], "pnl": float(d["pnl"]), "low_intraday": float(d.get("low_intraday", min(0.0, d["pnl"])))}
            for d in r["days"]]
    return sym, key, tr, days


# ------------------------------------------------------------------------------------------- stats
def summ(tr, ndays):
    n = len(tr)
    if not n:
        return {"n": 0, "wk": 0.0, "wr": 0.0, "avg_r": 0.0, "net": 0.0, "pf": 0.0, "dd": 0.0, "t": 0.0, "sum_r": 0.0}
    pnl = np.array([t["pnl"] for t in tr]); rs = np.array([t["r"] for t in tr])
    gp, gl = pnl[pnl > 0].sum(), -pnl[pnl <= 0].sum()
    eq = np.cumsum(pnl); dd = float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min())
    sd = rs.std(ddof=1) if n > 1 else 0.0
    return {"n": n, "wk": n / max(ndays / 5, 1e-9), "wr": float((rs > 0).mean() * 100), "avg_r": float(rs.mean()),
            "net": float(pnl.sum()), "pf": float(gp / gl) if gl else 99.0, "dd": dd,
            "t": float(rs.mean() / sd * np.sqrt(n)) if sd > 0 else 0.0, "sum_r": float(rs.sum())}


def cell(s):
    if not s["n"]:
        return "0 trades"
    return (f"{s['n']} · {s['wk']:.1f}/wk · WR {s['wr']:.0f}% · {s['avg_r']:+.2f}R · ${s['net']:+,.0f} · PF {min(s['pf'], 99):.1f}"
            f" · DD {s['dd']:,.0f}")


def week_of(d):
    x = dt.date.fromisoformat(d)
    return (x - dt.timedelta(days=x.weekday())).isoformat()


# ------------------------------------------------------------------------------------------- selection rules
def block_r(tr, blocks):
    return [sum(t["r"] for t in tr if t["day"] in b) for b in blocks]


def select(pool, rule, tr_days, blocks):
    """pool: {key: trades}; pick the best config on the training days (set) only."""
    nd = len(tr_days)
    best, best_v = None, -1e18
    for key, tr in pool.items():
        t = [x for x in tr if x["day"] in tr_days]
        s = summ(t, nd)
        if not (LO <= s["wk"] <= HI) or s["n"] < 6:
            continue
        if rule == "expectancy":
            v = s["avg_r"]
        elif rule == "t-stat":
            v = s["t"]
        elif rule == "win-rate":
            v = s["wr"] if s["avg_r"] > 0 else -1e9 + s["avg_r"]
        elif rule == "worst-block":
            v = min(block_r(t, blocks)) + 1e-3 * s["sum_r"]
        else:
            raise ValueError(rule)
        if v > best_v + 1e-12 or (abs(v - best_v) <= 1e-12 and key == DEFAULT_KEY):
            best, best_v = key, v
    return best


RULES = ["expectancy", "t-stat", "win-rate", "worst-block"]


def boot_ci(rs, stat=np.mean, n=4000, seed=5):
    rs = np.asarray(rs, float)
    if len(rs) < 2:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    b = np.array([stat(rng.choice(rs, len(rs))) for _ in range(n)])
    return float(np.percentile(b, 5)), float(np.percentile(b, 95))


def eval_block(days):
    pl = analytics.PLANS["builder_50k"]
    one = analytics.simulate_eval([d["pnl"] for d in days], pl, [d["low_intraday"] for d in days])
    roll = analytics.rolling_evals(days, pl)
    mc = analytics.monte_carlo([d["pnl"] for d in days], pl, runs=2000, horizon=60)
    worst_day = min([d["pnl"] for d in days] or [0]); worst_intra = min([d["low_intraday"] for d in days] or [0])
    return one, roll, mc, worst_day, worst_intra


# ------------------------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sym", default="NQ"); ap.add_argument("--check", default="ES")
    ap.add_argument("--from", dest="a", default="2026-08-06"); ap.add_argument("--to", dest="z", default="2026-10-16")
    ap.add_argument("--workers", type=int, default=4); ap.add_argument("--train0", type=int, default=4)
    ap.add_argument("--step", type=int, default=2); ap.add_argument("--placebo", type=int, default=300)
    ap.add_argument("--out", default=None)
    A = ap.parse_args()
    out = open(A.out, "w", encoding="utf-8") if A.out else sys.stdout

    def P(*x):
        print(*x, file=out, flush=True)

    keys = sorted(set(canon(k) for k in itertools.product(*SPACE.values())), key=lambda k: (k != DEFAULT_KEY, str(k)))
    syms = [A.sym] + ([A.check] if A.check else [])
    jobs = [(s, k, RESEARCH) for s in syms for k in keys]
    with Pool(A.workers) as pool:
        res = pool.map(run_one, jobs, chunksize=8)
    inr = lambda d: A.a <= d <= A.z
    TR = {s: {} for s in syms}; DAYS = {}
    for s, k, tr, days in res:
        TR[s][k] = [t for t in tr if inr(t["day"])]
        DAYS[s] = [d["date"] for d in days if inr(d["date"])]
    days = DAYS[A.sym]
    weeks = sorted(set(week_of(d) for d in days))
    wdays = [set(d for d in days if week_of(d) == w) for w in weeks]
    P(f"# combo study  sym={A.sym} check={A.check} range {days[0]}..{days[-1]}  {len(days)} days  {len(weeks)} weeks  "
      f"{len(keys)} configs  band {LO}-{HI}/wk")

    # ---- full-sample landscape (IN-SAMPLE, descriptive only)
    full = {k: summ(TR[A.sym][k], len(days)) for k in keys}
    band = [k for k in keys if LO <= full[k]["wk"] <= HI]
    P(f"\n## Full-sample landscape (in-sample, descriptive)\nconfigs in the {LO}-{HI}/wk band: {len(band)}/{len(keys)}; "
      f"profitable among them: {sum(full[k]['net'] > 0 for k in band)}; defaults: {cell(full[DEFAULT_KEY])}")
    if A.check:
        chk = {k: summ(TR[A.check][k], len(DAYS[A.check])) for k in keys}
        P(f"{A.check} defaults: {cell(chk[DEFAULT_KEY])}; {A.check} configs profitable: {sum(chk[k]['net'] > 0 for k in keys)}/{len(keys)}; "
          f"rank corr(avg R {A.sym}, avg R {A.check}) over band configs: "
          f"{np.corrcoef([full[k]['avg_r'] for k in band], [chk[k]['avg_r'] for k in band])[0, 1]:+.2f}")
    P("\n### Win rate vs expectancy (band configs, in-sample): best avg R per win-rate bucket")
    P("| win-rate bucket | configs | best avg R config | its stats | its ES |")
    P("|---|---|---|---|---|")
    for lo_, hi_ in ((0, 35), (35, 45), (45, 55), (55, 101)):
        ks = [k for k in band if lo_ <= full[k]["wr"] < hi_]
        if not ks:
            P(f"| {lo_}-{min(hi_, 100)}% | 0 | - | - | - |"); continue
        kb = max(ks, key=lambda k: full[k]["avg_r"])
        P(f"| {lo_}-{min(hi_, 100)}% | {len(ks)} | {short(kb)} | {cell(full[kb])} | {cell(chk[kb]) if A.check else '-'} |")
    # pareto front (wr, avg_r)
    front = [k for k in band if not any(full[j]["wr"] >= full[k]["wr"] and full[j]["avg_r"] >= full[k]["avg_r"]
                                        and (full[j]["wr"], full[j]["avg_r"]) != (full[k]["wr"], full[k]["avg_r"]) for j in band)]
    front = sorted(front, key=lambda k: full[k]["wr"])
    P("\n### Pareto front win rate vs avg R (in-sample)")
    P("| config | NQ full | ES full |"); P("|---|---|---|")
    for k in front[:12]:
        P(f"| {short(k)} | {cell(full[k])} | {cell(chk[k]) if A.check else '-'} |")

    # ---- per-knob marginal effect (in-sample, band configs): mean avg R with each value
    P("\n### Per-knob marginal (band configs, mean of avg R across configs holding that value; in-sample)")
    P("| knob | value: NQ mean avgR (n configs) / ES mean avgR |"); P("|---|---|")
    for i, kn in enumerate(KNOBS):
        parts = []
        for v in SPACE[kn]:
            ks = [k for k in band if k[i] == v]
            if ks:
                parts.append(f"{v!r}: {np.mean([full[k]['avg_r'] for k in ks]):+.2f} ({len(ks)})"
                             + (f" / {np.mean([chk[k]['avg_r'] for k in ks]):+.2f}" if A.check else ""))
        P(f"| {kn} | " + " · ".join(parts) + " |")

    # ---- nested walk-forward
    folds = []
    k = A.train0
    while k < len(weeks):
        z = k + A.step if k + 2 * A.step <= len(weeks) else len(weeks)
        folds.append((list(range(0, k)), list(range(k, z))))
        k = z
    P(f"\n## Nested walk-forward ({len(folds)} folds, expanding train window, test blocks of {A.step} weeks)")
    oos_days = sorted(set().union(*[wdays[w] for _, te in folds for w in te]))
    summary = {}
    for rule in RULES + ["defaults", "oracle"]:
        rows, oos_tr, oos_chk, chosen = [], [], [], []
        for trw, tew in folds:
            trd = set().union(*[wdays[w] for w in trw]); ted = set().union(*[wdays[w] for w in tew])
            blocks = [set().union(*[wdays[w] for w in trw[i:i + 2]]) for i in range(0, len(trw), 2)]
            if rule == "defaults":
                key = DEFAULT_KEY
            elif rule == "oracle":   # hindsight best on the TEST block (upper bound, not achievable)
                key = select(TR[A.sym], "expectancy", ted, [ted]) or DEFAULT_KEY
            else:
                key = select(TR[A.sym], rule, trd, blocks) or DEFAULT_KEY
            t_is = [t for t in TR[A.sym][key] if t["day"] in trd]
            t_os = [t for t in TR[A.sym][key] if t["day"] in ted]
            c_os = [t for t in TR[A.check][key] if t["day"] in ted] if A.check else []
            oos_tr += t_os; oos_chk += c_os; chosen.append(key)
            rows.append((weeks[trw[0]], weeks[trw[-1]], weeks[tew[0]], weeks[tew[-1]], key, summ(t_is, len(trd)), summ(t_os, len(ted)),
                         summ(c_os, len(ted))))
        summary[rule] = {"oos": summ(oos_tr, len(oos_days)), "oos_chk": summ(oos_chk, len(oos_days)), "trades": oos_tr,
                         "chosen": chosen, "rows": rows}
        P(f"\n### rule: {rule}")
        P(f"| train weeks | test weeks | chosen config | train (IS) | test (OOS) {A.sym} | test (OOS) {A.check} |")
        P("|---|---|---|---|---|---|")
        for a0, a1, b0, b1, key, si, so, sc in rows:
            P(f"| {a0}..{a1} | {b0}..{b1} | {short(key)} | {cell(si)} | {cell(so)}{' LOW' if so['wk'] < LO else (' HIGH' if so['wk'] > HI else '')} | {cell(sc)} |")
        s = summary[rule]["oos"]
        P(f"OOS pooled {A.sym}: {cell(s)} | {A.check}: {cell(summary[rule]['oos_chk'])} | IS->OOS gap avgR: "
          f"{np.mean([r[5]['avg_r'] for r in rows]):+.2f} -> {s['avg_r']:+.2f}")

    P("\n## OOS comparison (pooled test weeks only)")
    P(f"| rule | OOS {A.sym} | 90% CI avg R (bootstrap) | 90% CI win rate | P(avgR<=0) | OOS {A.check} | weekly R diff vs defaults (90% CI, week bootstrap) |")
    P("|---|---|---|---|---|---|---|")
    test_weeks = [w for _, te in folds for w in te]
    dweek = {w: sum(t["r"] for t in summary["defaults"]["trades"] if t["day"] in wdays[w]) for w in test_weeks}
    for rule in ["defaults"] + RULES + ["oracle"]:
        tr = summary[rule]["trades"]; rs = [t["r"] for t in tr]
        ci = boot_ci(rs); ciw = boot_ci([1.0 if r > 0 else 0.0 for r in rs])
        rng = np.random.default_rng(9); boots = np.array([rng.choice(rs, len(rs)).mean() for _ in range(4000)]) if rs else np.zeros(1)
        rw = {w: sum(t["r"] for t in tr if t["day"] in wdays[w]) for w in test_weeks}
        diffs = np.array([rw[w] - dweek[w] for w in test_weeks])
        bd = np.array([np.random.default_rng(100 + i).choice(diffs, len(diffs)).mean() for i in range(2000)])
        P(f"| {rule} | {cell(summary[rule]['oos'])} | {ci[0]:+.2f}..{ci[1]:+.2f} | {ciw[0] * 100:.0f}..{ciw[1] * 100:.0f}% | "
          f"{float(np.mean(boots <= 0)):.2f} | {cell(summary[rule]['oos_chk'])} | {diffs.mean():+.2f}R/wk ({np.percentile(bd, 5):+.2f}..{np.percentile(bd, 95):+.2f}) |")

    # where do the defaults rank OOS among all configs that were in the band on the OOS days?
    oos_all = {k: summ([t for t in TR[A.sym][k] if t["day"] in set(oos_days)], len(oos_days)) for k in keys}
    ob = [k for k in keys if LO <= oos_all[k]["wk"] <= HI]
    pct = np.mean([oos_all[k]["avg_r"] <= oos_all[DEFAULT_KEY]["avg_r"] for k in ob]) * 100 if ob else float("nan")
    P(f"\nDefaults' OOS avg R is at the {pct:.0f}th percentile of {len(ob)} in-band configs on the same OOS weeks.")

    # ---- final configs (rule on all weeks), neighbourhood, placebo, eval
    alld = set(days)
    blocks_all = [set().union(*wdays[i:i + 2]) for i in range(0, len(weeks), 2)]
    finals = {"defaults": DEFAULT_KEY}
    for rule in RULES:
        finals[rule] = select(TR[A.sym], rule, alld, blocks_all) or DEFAULT_KEY
    P("\n## Final configs (rule applied to ALL weeks - in-sample numbers; judge them by the OOS table above)")
    P(f"| rule | config | {A.sym} full (IS) | {A.check} full |"); P("|---|---|---|---|")
    for rule, key in finals.items():
        P(f"| {rule} | {short(key)} | {cell(full[key])} | {cell(chk[key]) if A.check else '-'} |")

    P("\n## Neighbourhood check (one knob one step; full sample and OOS weeks)")
    for rule, key in finals.items():
        if rule != "defaults" and key == DEFAULT_KEY:
            continue
        P(f"\n### {rule}: {short(key)}")
        P(f"| perturbation | {A.sym} full | {A.sym} OOS weeks | {A.check} full |"); P("|---|---|---|---|")
        for i, kn in enumerate(KNOBS):
            for v in SPACE[kn]:
                if v == key[i]:
                    continue
                nk = canon(key[:i] + (v,) + key[i + 1:])
                if nk == key or nk not in full:
                    continue
                P(f"| {kn}={v!r} | {cell(full[nk])} | {cell(oos_all[nk])} | {cell(chk[nk]) if A.check else '-'} |")

    P("\n## Placebo (engine.robust.placebo: random entries same day/window, same risk/target/BE/time stop) + bootstrap")
    P("| config | real avg R | placebo mean | placebo p95 | p-value | 90% CI real avgR | flipped direction |"); P("|---|---|---|---|---|---|---|")
    seen = set()
    for rule, key in finals.items():
        if key in seen:
            continue
        seen.add(key)
        for s in syms:
            pr = robust.placebo(s, "5m", {**to_params(key), **RESEARCH, "days_from": A.a, "days_to": A.z}, n=A.placebo)
            P(f"| {rule} ({s}) {short(key)} | {pr.get('real')} | {pr.get('placebo_mean')} | {pr.get('placebo_p95')} | "
              f"{pr.get('p_value')} | {pr.get('ci90')} | {pr.get('flipped')} |")

    P("\n## MFFU Builder 50K with LIVE risk settings (grade sizing, $350, dd_aware, $600 daily stop)")
    P("| config | days | net | worst day | worst intraday | eval from day 1 | rolling evals pass/fail/open (avg days) | "
      "OOS-days-only rolling | Monte Carlo 60d pass% / fail% / median days |")
    P("|---|---|---|---|---|---|---|---|---|")
    seen = set()
    for rule, key in finals.items():
        if key in seen:
            continue
        seen.add(key)
        _, _, tr, dl = run_one((A.sym, key, LIVE))
        dl = [d for d in dl if inr(d["date"])]
        one, roll, mc, wd, wi = eval_block(dl)
        _, roll_o, _, _, _ = eval_block([d for d in dl if d["date"] in set(oos_days)])
        P(f"| {rule}: {short(key)} | {len(dl)} | ${sum(d['pnl'] for d in dl):+,.0f} | {wd:,.0f} | {wi:,.0f} | {one['result']} d{one['days']} | "
          f"{roll['pass']}/{roll['fail']}/{roll['open']} ({roll['avg_days_to_pass']}) | {roll_o['pass']}/{roll_o['fail']}/{roll_o['open']} "
          f"({roll_o['avg_days_to_pass']}) | {mc.get('pass_prob')}% / {mc.get('fail_prob')}% / {mc.get('median_days_to_pass')} |")


if __name__ == "__main__":
    main()
