"""Loss-cut study for the MFFU Builder 50K eval pass rate (run prefix "losscut_", 2026-10-17).

Question: can the locked strategy pass a larger share of its MFFU 50K evals by cutting losing trades / losing stretches,
without breaking the owner's rules (2-4 trades a week, stops beyond the sweep, better in 2026 AND 2021-25)?

Headline metric: pass rate of decided evals = passed / (passed + failed). Because a smaller size always raises that number
(at the cost of slower evals), every idea is also compared with the "uniform size" frontier: the same strategy at
x0.5 ... x1.25 size on every trade. An idea is real only when it beats that frontier (more passes at the same speed).

  python tools/research_losscut.py critic     # step 1: critic of the intraday package (year by year, odd/even, neighbours, placebo)
  python tools/research_losscut.py ideas      # step 2: new loss-cut ideas (trade rules + eval-state rules), stores losscut_* runs
  python tools/research_losscut.py frontier   # uniform-size frontier + the pass-rate math
Uses only the cached exact live-loop replay (tools/runlib.replay); no engine change.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import math
import os
import random
import sys
from zoneinfo import ZoneInfo

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import runlib as rl  # noqa: E402
from engine.analytics import PLANS  # noqa: E402

ET = ZoneInfo("America/New_York")
PLAN = PLANS["builder_50k"]
OUT = os.path.join(ROOT, "research", "lab", "losscut.json")
SPANS = (("2026", "2026-01-01", "2026-12-31"), ("2021-25", "2021-01-01", "2025-12-31"), ("all", "2000-01-01", "2100-01-01"))


# ------------------------------------------------------------------------------------------------ data
_RAW = None


def raw():
    global _RAW
    if _RAW is None:
        _RAW = rl.replay(procs=3, quiet=True)
    return _RAW


def base_trades():
    return rl.size(raw())


_ADR = None


def adr_map(n=14):
    """ADR(n) of the prior n Globex sessions (18:00-17:00 ET, labelled by the ET date of the close), known before the day."""
    global _ADR
    if _ADR is not None:
        return _ADR
    hi, lo = {}, {}
    with open(os.path.join(ROOT, "data", "NQ_5m.csv"), encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            ts, o, h, l, c = line.split(",")[:5]
            d = dt.datetime.fromtimestamp(int(ts), ET)
            day = (d + dt.timedelta(hours=6)).date().isoformat()   # 18:00 ET belongs to the next session
            h, l = float(h), float(l)
            hi[day] = max(hi.get(day, h), h); lo[day] = min(lo.get(day, l), l)
    days = sorted(hi)
    rng = [hi[d] - lo[d] for d in days]
    _ADR = {d: (float(np.mean(rng[i - n:i])) if i >= n else None) for i, d in enumerate(days)}
    return _ADR


# ------------------------------------------------------------------------------------------------ eval simulator with eval-state sizing
def _q(q, m, cap=rl.MAX_MICROS):
    if m <= 0:
        return 0
    if m == 1:
        return q
    return max(1, min(cap, int(q * m))) if m < 1 else min(cap, int(q * m))


class Eval:
    """One MFFU Builder 50K eval (same rules as engine.analytics.simulate_eval: EOD-trailing $2,000 max loss checked
    against the day's worst open point, locking at start + $100; pass at +$3,000)."""

    def __init__(self):
        self.bal = PLAN["start"]; self.peak = self.bal; self.mll = self.bal - PLAN["mll"]
        self.lock = PLAN["start"] + PLAN["lock_above"]
        self.trades = []; self.days = 0; self.week = None; self.week_pnl = 0.0; self.week_n = 0

    def state(self, day, wk=None):
        wk = wk if wk is not None else dt.date.fromisoformat(day).isocalendar()[:2]
        if wk != self.week:
            self.week, self.week_pnl, self.week_n = wk, 0.0, 0
        streak = 0
        for x in reversed(self.trades):
            s = 1 if x > 0 else -1
            if streak == 0 or (s > 0) == (streak > 0):
                streak += s
            else:
                break
        return {"profit": self.bal - PLAN["start"], "cushion": self.bal - self.mll, "need": PLAN["start"] + PLAN["target"] - self.bal,
                "locked": self.mll >= self.lock, "n": len(self.trades), "days": self.days, "week_pnl": self.week_pnl,
                "week_n": self.week_n, "streak": streak, "dd": self.bal - self.peak, "last": self.trades[-1] if self.trades else None}

    def day(self, day, trades, rule, wk=None):
        """Trade one session; returns "PASS" / "FAIL" / None and the trades taken."""
        cum = low = 0.0
        out = []
        if wk is not None or rule:
            self.state(day, wk)                      # rolls the week even on a day without a trade
        for t in trades:
            m = rule(t, self.state(day, wk)) if rule else 1.0
            q = _q(int(t["qty"]), m)
            if q <= 0:
                continue
            per = t["pnl"] / t["qty"]; lper = t["low"] / t["qty"]
            pnl = per * q
            low = min(low, cum + lper * q); cum += pnl; low = min(low, cum)
            self.trades.append(pnl); self.week_pnl += pnl; self.week_n += 1
            out.append({**t, "qty": q, "pnl": round(pnl, 2), "low": lper * q, "mult": round(q / max(1, int(t["qty"])) * t.get("mult", 1), 3)})
        self.days += 1
        res = None
        if self.bal + low <= self.mll or self.bal + cum <= self.mll:
            res = "FAIL"
        self.bal += cum
        if res is None:
            self.peak = max(self.peak, self.bal)
            self.mll = min(max(self.mll, self.peak - PLAN["mll"]), self.lock)
            if self.bal - PLAN["start"] >= PLAN["target"]:
                res = "PASS"
        return res, out


def by_day(trades):
    by = collections.defaultdict(list)
    for t in sorted(trades, key=lambda x: x["entry_t"]):
        by[t["day"]].append(t)
    return by


def run_eval(sess, k0, by, rule, horizon=None):
    ev = Eval(); taken = []
    end = len(sess) if horizon is None else min(len(sess), k0 + horizon)
    for i in range(k0, end):
        r, out = ev.day(sess[i], by.get(sess[i], []), rule)
        taken += out
        if r:
            return r, i - k0 + 1, taken
    return "OPEN", end - k0, taken


def eval_metrics(trades, sess, rule=None, offsets=range(0, 100, 5)):
    """Rolling starts on every session (60-session horizon and unlimited) + back-to-back chains averaged over 20 first days."""
    by = by_day(trades)
    n = len(sess)
    r60 = [run_eval(sess, k, by, rule, 60)[:2] for k in range(n)]
    rinf = [run_eval(sess, k, by, rule, None)[:2] for k in range(n)]
    pct = lambda c: round(100 * c / max(n, 1), 1)
    p60 = sum(r == "PASS" for r, _ in r60); f60 = sum(r == "FAIL" for r, _ in r60)
    p20 = sum(r == "PASS" and d <= 20 for r, d in r60); f20 = sum(r == "FAIL" and d <= 20 for r, d in r60)
    p10 = sum(r == "PASS" and d <= 10 for r, d in r60); f10 = sum(r == "FAIL" and d <= 10 for r, d in r60)
    P = sum(r == "PASS" for r, _ in rinf); F = sum(r == "FAIL" for r, _ in rinf)
    pd_ = [d for r, d in rinf if r == "PASS"]; fd = [d for r, d in rinf if r == "FAIL"]
    # back-to-back
    chains = []
    for off in offsets:
        if off >= n:
            continue
        k, pa, fa, used = off, 0, 0, 0
        while k < n:
            r, d, _ = run_eval(sess, k, by, rule, None)
            if r == "OPEN":
                break
            pa += r == "PASS"; fa += r == "FAIL"; k += d; used += d
        chains.append((pa, fa, used))
    k, pa0, fa0 = 0, 0, 0
    while k < n:
        r, d, _ = run_eval(sess, k, by, rule, None)
        if r == "OPEN":
            break
        pa0 += r == "PASS"; fa0 += r == "FAIL"; k += d
    cp = sum(c[0] for c in chains); cf = sum(c[1] for c in chains); yrs = sum(c[2] for c in chains) / 252 or 1e-9
    return {"p10": pct(p10), "f10": pct(f10), "p20": pct(p20), "f20": pct(f20), "p60": pct(p60), "f60": pct(f60),
            "open60": pct(n - p60 - f60), "rate60": round(100 * p60 / (p60 + f60), 1) if p60 + f60 else None,
            "rate": round(100 * P / (P + F), 1) if P + F else None, "open_end": pct(n - P - F),
            "pass_med": float(np.median(pd_)) if pd_ else None, "fail_med": float(np.median(fd)) if fd else None,
            "b2b": f"{pa0}/{fa0}", "b2b_rate": round(100 * cp / (cp + cf), 1) if cp + cf else None,
            "evals_per_pass": round((cp + cf) / cp, 2) if cp else None, "passes_yr": round(cp / yrs, 2), "fails_yr": round(cf / yrs, 2)}


def evals_by_year(trades, sess, rule=None):
    """Real history: evals started on every session of a year, run to the end of the data: passed / failed / open."""
    by = by_day(trades)
    out = collections.defaultdict(lambda: [0, 0, 0])
    for k, d in enumerate(sess):
        r, _, _ = run_eval(sess, k, by, rule, None)
        out[d[:4]][0 if r == "PASS" else 1 if r == "FAIL" else 2] += 1
    return {y: {"pass": v[0], "fail": v[1], "open": v[2], "rate": round(100 * v[0] / max(1, v[0] + v[1]), 1)} for y, v in sorted(out.items())}


def chain_trades(trades, sess, rule):
    """The account an eval-state rule produces: back-to-back evals from the first session (each new eval starts fresh);
    an open eval at the end keeps its trades."""
    by = by_day(trades)
    k, out = 0, []
    while k < len(sess):
        r, d, taken = run_eval(sess, k, by, rule, None)
        out += taken; k += d
    return out


def evaluate(trades, rule=None, eval_state=False):
    """Fixed rule (trade fields only) or eval-state rule; returns runlib-style score S plus eval metrics per span."""
    R = raw()
    sess = R["sessions"]
    if eval_state:
        T = chain_trades(trades, sess, rule)
    else:
        T = trades if rule is None else apply_fixed(trades, rule)
    S = rl.score(T, R)
    ev = {}
    for name, a, z in SPANS:
        ss = [d for d in sess if a <= d <= z]
        tt = [t for t in trades if a <= t["day"] <= z] if eval_state else [t for t in T if a <= t["day"] <= z]
        ev[name] = eval_metrics(tt, ss, rule if eval_state else None)
        ev[name].update(mc_metrics(tt, ss, rule if eval_state else None))
        S["spans"][name].update({k: v for k, v in ev[name].items() if k in ("p60", "f60", "rate60", "rate", "b2b_rate", "evals_per_pass")})
    return T, S, ev


def apply_fixed(trades, rule):
    out = []
    for t in trades:
        m = rule(t, None)
        q = _q(int(t["qty"]), m)
        if q <= 0:
            continue
        per = t["pnl"] / t["qty"]; lper = t["low"] / t["qty"]
        out.append({**t, "qty": q, "pnl": round(per * q, 2), "low": lper * q, "risk_usd": round(float(t["risk_pts"]) * 2 * q, 2),
                    "mult": round(t.get("mult", 1) * q / max(1, int(t["qty"])), 3)})
    return out


# ------------------------------------------------------------------------------------------------ week-block bootstrap
def _weeks(trades, sess):
    by = by_day(trades)
    wk = collections.OrderedDict()
    for d in sess:
        wk.setdefault(dt.date.fromisoformat(d).isocalendar()[:2], []).append((d, by.get(d, [])))
    return list(wk.values())


def _mc_job(args):
    weeks, rule_id, n, seed, cap = args
    rule = _RULES.get(rule_id) if rule_id else None
    rng = random.Random(seed)
    P = F = O = 0; plen, flen, alllen = [], [], []
    p20 = f20 = 0
    for _ in range(n):
        ev = Eval(); k = 0; res = None; w = 0
        while res is None and k < cap:
            week = weeks[rng.randrange(len(weeks))]; w += 1
            for d, ts in week:
                r, _ = ev.day(d, ts, rule, wk=w)
                k += 1
                if r:
                    res = r; break
        if res == "PASS":
            P += 1; plen.append(k); p20 += k <= 20
        elif res == "FAIL":
            F += 1; flen.append(k); f20 += k <= 20
        else:
            O += 1
        alllen.append(k)
    return P, F, O, plen, flen, p20, f20, alllen


_RULES = {}


def mc_metrics(trades, sess, rule=None, n=6000, cap=504, procs=3, seed=3):
    """Week-block bootstrap of the period: evals built from randomly drawn real weeks (with replacement) until passed,
    failed or `cap` sessions (2 years). Smooth pass rate / speed numbers for comparing ideas and the uniform-size frontier."""
    from multiprocessing import Pool
    weeks = _weeks(trades, sess)
    rid = None
    if rule is not None:
        rid = f"r{id(rule)}"; _RULES[rid] = rule
    jobs = [(weeks, rid, n // procs, seed + i, cap) for i in range(procs)]
    if procs > 1:
        with Pool(procs) as pool:
            outs = pool.map(_mc_job, jobs)
    else:
        outs = [_mc_job(j) for j in jobs]
    P = sum(o[0] for o in outs); F = sum(o[1] for o in outs); O = sum(o[2] for o in outs)
    plen = [x for o in outs for x in o[3]]; alllen = [x for o in outs for x in o[7]]
    N = P + F + O
    return {"mc_rate": round(100 * P / max(P + F, 1), 1), "mc_open": round(100 * O / N, 1),
            "mc_p20": round(100 * sum(o[5] for o in outs) / N, 1), "mc_f20": round(100 * sum(o[6] for o in outs) / N, 1),
            "mc_pass_med": float(np.median(plen)) if plen else None,
            "mc_passes_yr": round(252 * P / max(sum(alllen), 1), 2)}


# ------------------------------------------------------------------------------------------------ printing
def row(name, S, ev):
    o = {}
    for sp in ("2026", "2021-25", "all"):
        s, e = S["spans"][sp], ev[sp]
        o[sp] = {"n": s.get("n"), "tpw": s.get("tpw"), "win": s.get("win"), "pf": s.get("pf"), "net": s.get("net"), "per_month": s.get("per_month"),
                 "dd": s.get("dd"), **e}
    return o


def fmt(name, o):
    lines = []
    for sp in ("2026", "2021-25", "all"):
        x = o[sp]
        lines.append(f"  {sp:7s} n={x['n']} tpw={x['tpw']} win={x['win']} PF={x['pf']} net={x['net']:+,} ${x['per_month']}/mo DD={x['dd']:,} | "
                     f"rate60={x['rate60']} rate={x['rate']} b2b={x['b2b']} b2bR={x['b2b_rate']} e/p={x['evals_per_pass']} pass/yr={x['passes_yr']} "
                     f"| 1m {x['p20']}/{x['f20']} 60s {x['p60']}/{x['f60']} open60 {x['open60']} med {x['pass_med']}"
                     f" || MC rate {x.get('mc_rate')} 1m {x.get('mc_p20')}/{x.get('mc_f20')} med {x.get('mc_pass_med')} pass/yr {x.get('mc_passes_yr')} open {x.get('mc_open')}")
    return name + "\n" + "\n".join(lines)


# ------------------------------------------------------------------------------------------------ step 1: critic
def in_bucket(t, a, z):
    return a <= float(t["risk_pts"]) < z


def is_eq_target(t):
    lab = t.get("target_label") or ""
    if lab.startswith("5.0R cap"):
        return False
    for k in ("PW", "PD", "ON", "LO", "AS"):
        if k in lab and lab.index(k) < (lab.index("EQ") if "EQ" in lab else 99):
            return False
    return "EQ" in lab


def target_kind(t):
    from tools.research_intra import target_kind as tk
    return tk(t)


def year_delta(T0, T1):
    a = collections.defaultdict(float); b = collections.defaultdict(float)
    for t in T0:
        a[t["day"][:4]] += t["pnl"]
    for t in T1:
        b[t["day"][:4]] += t["pnl"]
    return {y: round(b[y] - a[y]) for y in sorted(a)}


def parity_delta(T0, T1):
    a = collections.defaultdict(float)
    for t in T0:
        a[("odd" if int(t["day"][5:7]) % 2 else "even", "2026" if t["day"] >= "2026" else "2021-25")] -= t["pnl"]
    for t in T1:
        a[("odd" if int(t["day"][5:7]) % 2 else "even", "2026" if t["day"] >= "2026" else "2021-25")] += t["pnl"]
    return {f"{k[1]} {k[0]}": round(v) for k, v in sorted(a.items())}


def placebo(T0, sel, mult, n_iter=2000, seed=11):
    """Random groups of the same size per period sized by `mult`: how often does a random group beat the real one in BOTH periods?"""
    rng = random.Random(seed)
    idx = {"2026": [i for i, t in enumerate(T0) if t["day"] >= "2026"], "old": [i for i, t in enumerate(T0) if t["day"] < "2026"]}
    real = {}
    for k, ids in idx.items():
        real[k] = sum((_q(int(T0[i]["qty"]), mult) / T0[i]["qty"] - 1) * T0[i]["pnl"] for i in ids if sel(T0[i]))
    cnt = {k: sum(1 for i in ids if sel(T0[i])) for k, ids in idx.items()}
    beat_both = beat = {"2026": 0, "old": 0}
    beat = {"2026": 0, "old": 0}; both = 0
    for _ in range(n_iter):
        ok = True
        for k, ids in idx.items():
            pick = rng.sample(ids, cnt[k])
            g = sum((_q(int(T0[i]["qty"]), mult) / T0[i]["qty"] - 1) * T0[i]["pnl"] for i in pick)
            if g >= real[k]:
                beat[k] += 1
            else:
                ok = False
        both += ok
    return {"gain_2026": round(real["2026"]), "gain_2021_25": round(real["old"]), "n_2026": cnt["2026"], "n_2021_25": cnt["old"],
            "p_2026": round(beat["2026"] / n_iter, 3), "p_2021_25": round(beat["old"] / n_iter, 3), "p_both": round(both / n_iter, 3)}


def cmd_critic():
    T0 = base_trades()
    _, S0, ev0 = evaluate(T0)
    res = {"baseline": row("baseline", S0, ev0)}
    print(fmt("baseline", res["baseline"]))
    pieces = {
        "stop3040_half": (lambda t: in_bucket(t, 30, 40), 0.5),
        "stop2535_half": (lambda t: in_bucket(t, 25, 35), 0.5),
        "stop3545_half": (lambda t: in_bucket(t, 35, 45), 0.5),
        "stop2842_half": (lambda t: in_bucket(t, 28, 42), 0.5),
        "stop3238_half": (lambda t: in_bucket(t, 32, 38), 0.5),
        "stop3045_half": (lambda t: in_bucket(t, 30, 45), 0.5),
        "stop4050_half": (lambda t: in_bucket(t, 40, 50), 0.5),
        "stop2030_half": (lambda t: in_bucket(t, 20, 30), 0.5),
        "stop3040_q75": (lambda t: in_bucket(t, 30, 40), 0.75),
        "tgt_eq_half": (lambda t: target_kind(t) == "equal highs/lows", 0.5),
        "cisd_125": (lambda t: t["trigger"] == "CISD", 1.25),
        "all_125": (lambda t: True, 1.25),
        "ifvg_08": (lambda t: t["trigger"] != "CISD", 0.8),
    }
    crit = {}
    for name, (sel, m) in pieces.items():
        rule = (lambda s, mm: (lambda t, c: mm if s(t) else 1.0))(sel, m)
        T1 = apply_fixed(T0, rule)
        _, S1, ev1 = evaluate(T1)
        o = row(name, S1, ev1)
        crit[name] = {"row": o, "years": year_delta(T0, T1), "parity": parity_delta(T0, T1), "placebo": placebo(T0, sel, m)}
        fr = (json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}).get("frontier")
        if fr:
            crit[name]["vs_frontier"] = {sp: frontier_beats(o, fr, sp) for sp in ("2026", "2021-25", "all")}
            print("   vs uniform-size frontier (MC pass-rate points)", crit[name]["vs_frontier"])
            tpw_ok, rate_up, money_up, beat = verdict_of(o, res["baseline"], fr)
            st = _store(f"losscut_critic_{name}", f"Critic: {name.replace('_', ' ')}", "Critic of the intraday package: does this slice hold "
                        "year by year, on odd/even months and with neighbouring thresholds?", T1, S1, o, res["baseline"], "fixed",
                        tpw_ok, rate_up, money_up, beat, crit[name]["years"])
            crit[name]["status"] = st; print("   ->", st)
        print(fmt(name, o)); print("   years", crit[name]["years"]); print("   parity", crit[name]["parity"]); print("   placebo", crit[name]["placebo"])
    # the package as stacked by the intraday study
    pk = lambda t, c: (0.5 if in_bucket(t, 30, 40) else 1.0) * (0.5 if target_kind(t) == "equal highs/lows" else 1.0) * (1.25 if t["trigger"] == "CISD" else 1.0)
    pd_ = lambda t, c: (0.5 if in_bucket(t, 30, 40) else 1.0) * (0.5 if target_kind(t) == "equal highs/lows" else 1.0)
    for name, rule in (("package_all", pk), ("package_defensive", pd_)):
        T1 = apply_fixed(T0, rule)
        _, S1, ev1 = evaluate(T1)
        o = row(name, S1, ev1)
        crit[name] = {"row": o, "years": year_delta(T0, T1), "parity": parity_delta(T0, T1)}
        fr = (json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}).get("frontier")
        if fr:
            crit[name]["vs_frontier"] = {sp: frontier_beats(o, fr, sp) for sp in ("2026", "2021-25", "all")}
            print("   vs uniform-size frontier", crit[name]["vs_frontier"])
            tpw_ok, rate_up, money_up, beat = verdict_of(o, res["baseline"], fr)
            st = _store(f"losscut_critic_{name}", f"Critic: intraday {name.replace('_', ' ')}", "The intraday study's stacked package, re-scored "
                        "on the eval pass rate.", T1, S1, o, res["baseline"], "fixed", tpw_ok, rate_up, money_up, beat, crit[name]["years"])
            crit[name]["status"] = st; print("   ->", st)
        print(fmt(name, o)); print("   years", crit[name]["years"]); print("   parity", crit[name]["parity"])
    res["critic"] = crit
    _merge_out(res)


def _merge_out(d):
    cur = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    cur.update(d)
    rl._dump(cur, OUT, indent=1)


# ------------------------------------------------------------------------------------------------ frontier + math
def cmd_frontier():
    T0 = base_trades()
    fr = {}
    for m in (0.25, 0.4, 0.5, 0.6, 0.75, 0.9, 1.0, 1.1, 1.25, 1.5):
        T1 = apply_fixed(T0, lambda t, c, m=m: m)
        _, S1, ev1 = evaluate(T1)
        fr[str(m)] = row(f"x{m}", S1, ev1)
        print(fmt(f"uniform x{m}", fr[str(m)]))
    # the math: per-trade $ distribution in each period
    math_ = {}
    for sp, a, z in SPANS:
        p = np.array([t["pnl"] for t in T0 if a <= t["day"] <= z])
        w, l = p[p > 0], p[p <= 0]
        mu, sd = float(p.mean()), float(p.std())
        k = 2 * mu / sd ** 2
        # Brownian gambler's ruin, fixed $2,000 floor (no trailing): P(+3000 before -2000)
        pr = (1 - math.exp(-k * 2000)) / (1 - math.exp(-k * 5000)) if k else 0.4
        math_[sp] = {"n": len(p), "mean": round(mu, 1), "sd": round(sd, 1), "win_pct": round(100 * len(w) / len(p), 1),
                     "avg_win": round(float(w.mean())), "avg_loss": round(float(l.mean())), "median_loss": round(float(np.median(l))),
                     "wins_to_pass": round(3000 / float(w.mean()), 1), "losses_to_fail": round(2000 / -float(l.mean()), 1),
                     "ruin_pass_fixed_floor": round(100 * pr, 1)}
        print(sp, math_[sp])
    # bootstrap of trades with the real trailing rule, for a few sizes, to show the ceiling
    rng = np.random.default_rng(5)
    boot = {}
    for sp, a, z in SPANS:
        Tp = [t for t in T0 if a <= t["day"] <= z]
        pn = np.array([t["pnl"] for t in Tp]); lo = np.array([t["low"] for t in Tp])
        for m in (0.25, 0.5, 1.0, 1.5):
            P = F = 0; lens = []
            for _ in range(4000):
                ev = Eval(); i = 0
                while i < 2000:
                    j = rng.integers(len(pn))
                    pnl, low = pn[j] * m, lo[j] * m
                    res = None
                    if ev.bal + low <= ev.mll or ev.bal + pnl <= ev.mll:
                        res = "FAIL"
                    ev.bal += pnl
                    if res is None:
                        ev.peak = max(ev.peak, ev.bal); ev.mll = min(max(ev.mll, ev.peak - 2000), ev.lock)
                        if ev.bal - 50000 >= 3000:
                            res = "PASS"
                    i += 1
                    if res:
                        P += res == "PASS"; F += res == "FAIL"; lens.append(i); break
            boot[f"{sp} x{m}"] = {"rate": round(100 * P / max(P + F, 1), 1), "median_trades_to_decide": float(np.median(lens)) if lens else None}
            print("bootstrap", sp, m, boot[f"{sp} x{m}"])
    _merge_out({"frontier": fr, "math": math_, "bootstrap": boot})


# ------------------------------------------------------------------------------------------------ step 2: ideas
def cold_flip_first(T0):
    """Set of entry_t of the first trade after the cold-streak filter turned back to full size (cold_mult 1 after < 1)."""
    out, prev = set(), None
    for t in sorted(T0, key=lambda x: x["entry_t"]):
        c = t["half"]
        if prev is True and c is False:
            out.add(t["entry_t"])
        prev = c
    return out


def kz_minutes(t):
    d = dt.datetime.fromtimestamp(int(t["entry_t"]), ET)
    m = d.hour * 60 + d.minute
    return m - (570 if m < 720 else 810)


def ideas():
    """(id, title, question, kind, rule). kind: 'fixed' (trade fields + earlier finished trades) or 'eval' (eval state)."""
    adr = adr_map()
    T0 = base_trades()
    flip = cold_flip_first(T0)

    def stop_adr(t):
        a = adr.get(t["day"])
        return float(t["risk_pts"]) / a if a else 0.0

    L = []
    # --- eval-state: losing week brake (1 trade a day, so a day cap does nothing; the week is the next unit)
    for x in (300, 500, 800):
        L.append((f"losscut_wk{x}_half", f"Half size for the rest of the eval week after -${x}",
                  f"Inside an eval, once the week's P&L is -${x} or worse, trade the rest of that week at half size.", "eval",
                  (lambda t, s, x=x: 0.5 if s["week_pnl"] <= -x else 1.0)))
    L.append(("losscut_wk500_skip", "Stop for the rest of the eval week after -$500",
              "Inside an eval, once the week's P&L is -$500 or worse, skip the rest of that week.", "eval",
              lambda t, s: 0.0 if s["week_pnl"] <= -500 else 1.0))
    L.append(("losscut_wk2loss_half", "Half size after the first two eval trades of a week both lost",
              "Skipping the second leg of a losing week: after two losing trades in the same week, half size until Monday.", "eval",
              lambda t, s: 0.5 if s["week_n"] >= 2 and s["week_pnl"] < 0 and s["streak"] <= -2 else 1.0))
    # neighbours of the 2-losses week brake (critic)
    L.append(("losscut_wk2loss_q75", "x0.75 after the first two eval trades of a week both lost",
              "Neighbour of the week brake: smaller cut.", "eval",
              lambda t, s: 0.75 if s["week_n"] >= 2 and s["week_pnl"] < 0 and s["streak"] <= -2 else 1.0))
    L.append(("losscut_wk2loss_q25", "Quarter size after two losing eval trades in a week",
              "Neighbour of the week brake: bigger cut.", "eval",
              lambda t, s: 0.25 if s["week_n"] >= 2 and s["week_pnl"] < 0 and s["streak"] <= -2 else 1.0))
    L.append(("losscut_wk2loss_skip", "Skip the rest of the week after two losing eval trades",
              "Neighbour of the week brake: no trade.", "eval",
              lambda t, s: 0.0 if s["week_n"] >= 2 and s["week_pnl"] < 0 and s["streak"] <= -2 else 1.0))
    L.append(("losscut_wk1loss_half", "Half size after the first eval trade of the week lost",
              "Neighbour of the week brake: one loss.", "eval",
              lambda t, s: 0.5 if s["week_n"] >= 1 and s["week_pnl"] < 0 else 1.0))
    L.append(("losscut_wk3loss_half", "Half size after three losing eval trades in a week",
              "Neighbour of the week brake: three losses.", "eval",
              lambda t, s: 0.5 if s["week_n"] >= 3 and s["week_pnl"] < 0 and s["streak"] <= -3 else 1.0))
    L.append(("losscut_wkneg2_half", "Half size once an eval week is down after 2+ trades",
              "Week brake without the streak condition: 2+ trades this week and the week is negative.", "eval",
              lambda t, s: 0.5 if s["week_n"] >= 2 and s["week_pnl"] < 0 else 1.0))
    L.append(("losscut_loss2_half", "Half size after two losing eval trades in a row (any week)",
              "Is it the week or just the streak? (seq_ study: the next trade after a loss is not worse.)", "eval",
              lambda t, s: 0.5 if s["streak"] <= -2 else 1.0))
    for x in (200, 400):
        L.append((f"losscut_wk{x}_half", f"Half size for the rest of the eval week after -${x}",
                  f"Neighbour of the $ week brake: -${x}.", "eval",
                  (lambda t, s, x=x: 0.5 if s["week_pnl"] <= -x else 1.0)))
    # inducement mirror (eval angle on the thin 'no inducement' lesson)
    L.append(("losscut_noind_x15", "x1.5 when no inducement was taken first",
              "Mirror of the inducement idea: press the 'no inducement' trades instead of cutting the rest.", "fixed",
              lambda t, c: 1.5 if not (t.get("smc") or {}).get("x_inducement") else 1.0))
    # --- eval-state: cushion ladder (size with the cushion to the trailing max loss, both ways)
    L.append(("losscut_cush_ladder", "Size with the cushion: x0.5 under $1,000, x1.25 over $2,500",
              "Cut size as the cushion to the trailing max loss shrinks, press as it grows (it only grows above $2,000 once the floor locks).",
              "eval", lambda t, s: 0.5 if s["cushion"] < 1000 else (1.25 if s["cushion"] > 2500 else 1.0)))
    L.append(("losscut_cush_prop", "Size in proportion to the cushion (cushion / $2,000, 0.4-1.5)",
              "Continuous version: multiplier = cushion / $2,000, between 0.4 and 1.5.", "eval",
              lambda t, s: min(1.5, max(0.4, s["cushion"] / 2000.0))))
    L.append(("losscut_cush750_half", "Half size while the cushion is under $750",
              "Defend only the last $750 above the trailing max loss.", "eval",
              lambda t, s: 0.5 if s["cushion"] < 750 else 1.0))
    L.append(("losscut_lock_press", "x1.5 once the eval floor has locked and profit is under the target",
              "After the floor locks at $50,100 the trailing loss no longer moves: press there.", "eval",
              lambda t, s: 1.5 if s["locked"] else 1.0))
    L.append(("losscut_dd1000_half", "Half size while the eval is $1,000+ below its best balance",
              "Eval drawdown brake: half size until a new eval high.", "eval",
              lambda t, s: 0.5 if s["dd"] <= -1000 else 1.0))
    L.append(("losscut_finish_cap", "Never risk more than what is still needed to pass",
              "Close to the target, the full risk only buys more downside: cap $ risk at the money still needed.", "eval",
              lambda t, s: min(1.0, max(0.0, s["need"]) / max(1.0, float(t["risk_usd"]))) if s["need"] < float(t["risk_usd"]) else 1.0))
    # --- trade rules from the losing trades
    for k in (0.20, 0.25, 0.30):
        L.append((f"losscut_stopadr{int(k*100)}_half", f"Half size when the stop is over {int(k*100)}% of the 14-day ADR",
                  f"Stops beyond {int(k*100)}% of the average daily range: half size.", "fixed",
                  (lambda t, c, k=k: 0.5 if stop_adr(t) > k else 1.0)))
    L.append(("losscut_flip_first_half", "Half size on the first trade after the cold streak ends",
              "Is the first full-size trade after the filter flips back a trap?", "fixed",
              lambda t, c: 0.5 if t["entry_t"] in flip else 1.0))
    L.append(("losscut_flip_first_125", "x1.25 on the first trade after the cold streak ends",
              "Or is it the best moment (eval-game.md: best time to start an eval)?", "fixed",
              lambda t, c: 1.25 if t["entry_t"] in flip else 1.0))
    L.append(("losscut_kz_late_half", "Half size on entries 60+ minutes into a killzone",
              "Time of entry within the killzone: are the late entries the losers?", "fixed",
              lambda t, c: 0.5 if kz_minutes(t) >= 60 else 1.0))
    L.append(("losscut_noresweep_half", "Half size when there was no re-sweep",
              "Lesson table: no re-sweep is worse in both periods (92 / 16 trades).", "fixed",
              lambda t, c: 0.5 if not (t.get("smc") or {}).get("x_resweep") else 1.0))
    L.append(("losscut_ind_half", "Half size when inducement was taken first",
              "Open work item 4: smaller size when the inducement was taken first.", "fixed",
              lambda t, c: 0.5 if (t.get("smc") or {}).get("x_inducement") else 1.0))
    L.append(("losscut_against1h_ifvg_half", "Half size on IFVG trades against the 1H trend",
              "The most common loss lesson is 'traded against the 1H trend'; IFVG is the weaker trigger.", "fixed",
              lambda t, c: 0.5 if t["trigger"] != "CISD" and (t.get("htf_trend") or 0) * t["dir"] < 0 else 1.0))
    L.append(("losscut_minor_ifvg_half", "Half size on IFVG trades that swept only a 15m swing",
              "Both 'worse in both periods' lessons together (minor pool and IFVG).", "fixed",
              lambda t, c: 0.5 if t["trigger"] != "CISD" and _minor(t) else 1.0))
    wk2 = lambda s: s["week_n"] >= 2 and s["week_pnl"] < 0 and s["streak"] <= -2
    L.append(("losscut_combo_wk2_stop3040", "Week brake (2 losses) + half size on 30-40 pt stops",
              "The new eval rule stacked on the best intraday slice.", "eval",
              lambda t, s: (0.5 if wk2(s) else 1.0) * (0.5 if in_bucket(t, 30, 40) else 1.0)))
    L.append(("losscut_combo_wk2_defensive", "Week brake (2 losses) + 30-40 pt stops half + equal-highs/lows target half",
              "The new eval rule stacked on the intraday defensive package.", "eval",
              lambda t, s: (0.5 if wk2(s) else 1.0) * (0.5 if in_bucket(t, 30, 40) else 1.0) * (0.5 if target_kind(t) == "equal highs/lows" else 1.0)))
    return L


def _minor(t):
    from tools.research_intra import pool_kind
    return pool_kind(t) == "minor (15m swing)"


def verdict_of(o, b, frontier):
    a26, a21 = o["2026"], o["2021-25"]
    b26, b21 = b["2026"], b["2021-25"]
    tpw_ok = 2.0 <= (a26["tpw"] or 0) <= 4.0 and 2.0 <= (a21["tpw"] or 0) <= 4.0
    rate_up = a26["mc_rate"] >= b26["mc_rate"] - 0.5 and a21["mc_rate"] > b21["mc_rate"] + 1.0
    money_up = a26["net"] >= 0.95 * b26["net"] and a21["net"] >= 0.95 * b21["net"]
    beat = {sp: frontier_beats(o, frontier, sp) for sp in ("2026", "2021-25", "all")}
    return tpw_ok, rate_up, money_up, beat


def frontier_beats(o, frontier, span="2021-25"):
    """Week-block Monte Carlo: the uniform-size frontier (pass rate vs passes a year). Returns this run's pass rate minus
    the uniform-size pass rate at the same passes a year (points); > 0 = better than just trading smaller / bigger."""
    pts = sorted(((v[span]["mc_passes_yr"], v[span]["mc_rate"]) for v in frontier.values()), key=lambda p: p[0])
    x = o[span]["mc_passes_yr"]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= x <= x1 and x1 > x0:
            y = y0 + (y1 - y0) * (x - x0) / (x1 - x0)
            return round(o[span]["mc_rate"] - y, 1)
    return None


def cmd_ideas(only=None):
    T0 = base_trades()
    cur = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    base = cur.get("baseline")
    frontier = cur.get("frontier") or {}
    res = cur.get("ideas", {})
    for id_, title, q, kind, rule in ideas():
        if only and id_ not in only:
            continue
        T1, S1, ev1 = evaluate(T0, rule=rule, eval_state=(kind == "eval"))
        o = row(id_, S1, ev1)
        tpw_ok, rate_up, money_up, beat = verdict_of(o, base, frontier)
        res[id_] = {"title": title, "kind": kind, "row": o, "tpw_ok": tpw_ok, "rate_up": rate_up, "money_up": money_up,
                    "vs_frontier": beat}
        if kind == "fixed":
            res[id_]["years"] = year_delta(T0, T1); res[id_]["parity"] = parity_delta(T0, T1)
            res[id_]["eval_years"] = evals_by_year(T1, raw()["sessions"])
        else:
            res[id_]["eval_years"] = evals_by_year(T0, raw()["sessions"], rule)
        print("   eval years", {y: v["rate"] for y, v in res[id_]["eval_years"].items()})
        print(fmt(f"{id_} [{kind}] tpw_ok={tpw_ok} rate_up={rate_up} money_up={money_up} vs_frontier={beat}", o))
        if kind == "fixed":
            print("   years", res[id_]["years"], "parity", res[id_]["parity"])
        res[id_]["status"] = _store(id_, title, q, T1, S1, o, base, kind, tpw_ok, rate_up, money_up, beat, res[id_].get("years"))
        print("   ->", res[id_]["status"])
    _merge_out({"ideas": res})


def _store(id_, title, q, T1, S1, o, base, kind, tpw_ok, rate_up, money_up, beat, years=None):
    a, b, c = o["2026"], o["2021-25"], o["all"]
    A, B, C = base["2026"], base["2021-25"], base["all"]
    f = lambda v: "n/a" if v is None else f"{v:+}"
    txt = (f"Eval pass rate (week-bootstrap, decided evals): 2026 {a['mc_rate']}% (base {A['mc_rate']}%), 2021-25 {b['mc_rate']}% "
           f"(base {B['mc_rate']}%), 5y {c['mc_rate']}% (base {C['mc_rate']}%); vs trading uniformly smaller/bigger at the same speed: "
           f"2021-25 {f(beat.get('2021-25'))} pts, 5y {f(beat.get('all'))} pts. Real history b2b 5y {c['b2b']} (base {C['b2b']}). "
           f"2026 {a['net']:+,} (${a['per_month']:,}/mo, PF {a['pf']}, DD {a['dd']:,}, {a['tpw']}/wk, 1-month {a['p20']}/{a['f20']}) vs {A['net']:+,}; "
           f"2021-25 {b['net']:+,} (${b['per_month']:,}/mo, PF {b['pf']}, DD {b['dd']:,}, {b['tpw']}/wk, 1-month {b['p20']}/{b['f20']}) vs {B['net']:+,}.")
    yrs_ok = years is None or sum(1 for v in years.values() if v > 0) >= 4
    fb = beat.get("2021-25"); fa = beat.get("all")
    if tpw_ok and rate_up and money_up and yrs_ok and (fb or 0) >= 1.5 and (fa or 0) >= 1.0:
        status = "adopt-candidate"
    elif tpw_ok and rate_up and (fb or 0) > 0:
        status = "promising"
    else:
        status = "rejected"
    rl.save(id_, title, "risk", q, params={}, sizing={"kind": kind, "study": "losscut"}, trades=T1, scored=S1, status=status,
            verdict=f"{status}. " + txt,
            notes="Loss-cut study for the eval pass rate (tools/research_losscut.py). kind=eval: sized from each eval's own state; "
                  "the stored trades are the back-to-back eval chain from the first session.",
            writeup="loss-cut-eval-pass", tags=["losscut", kind])
    return status


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "critic"
    if cmd == "critic":
        cmd_critic()
    elif cmd == "frontier":
        cmd_frontier()
    elif cmd == "ideas":
        cmd_ideas(set(sys.argv[2:]) or None)
