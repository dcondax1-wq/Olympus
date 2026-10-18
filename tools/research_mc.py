"""Monte Carlo of the MFFU Builder 50K eval on the LOCKED strategy (study "mc", runs mc_*, research/writeups/monte-carlo-evals.md).

  python tools/research_mc.py all      # everything: tables printed, research/archive/engine-2026-10-17/montecarlo.json, runs mc_* saved
  python tools/research_mc.py check    # sanity checks (bootstrap engine vs runlib's exact rolling evals, press re-sizing)
  python tools/research_mc.py quick    # fewer paths, no saving (smoke test)

What it does
  * Takes the exact live-loop replay of the locked strategy (tools/runlib.replay, cached) with the live sizing
    (runlib.size: cold-streak quarter size, late-entry half size, costs included) and turns it into one line per session:
    day P&L and worst open P&L ($), 1,278 sessions Nov 2021 - Oct 2026, 768 trades (1 trade a day at most).
  * Resamples that history many times and runs a fresh MFFU Builder 50K eval on every resampled path ($3,000 target,
    $2,000 end-of-day trailing max loss checked against the intraday low, locks at $50,100; engine/analytics.simulate_eval):
      iid      sessions drawn one at a time with replacement (no dependence at all)
      block5   blocks of 5 consecutive sessions (a week), keeps the week-to-week clustering of wins and losses
      state5   blocks of 5 sessions chained by the cold-streak state: the next block must start in the same state
               (cold / full size) the previous one ended in. This keeps the 13-18 week cold streaks alive in the
               resampled paths and lets an eval start "just after a cold streak ended" or "deep in one".
    The sized trades are resampled as they are (the cold-streak quarter size is already in the day P&L), so the
    dependence between a trade's size and the streak before it is kept.
  * Pools: all years, 2026 only, 2021-25 only.
  * The fast-eval press (run risk_fast_press1000: $800 on any stop while the eval is less than $1,000 down, else live
    sizing) is sized INSIDE the simulation from each simulated eval's own balance (two pre-sized versions of every
    trade, press / live; tools/research_risk's exact micro re-sizing), so the press is applied to the right state.
  * Reports: pass / fail odds within 2, 3, 4, 6 weeks and 60 sessions, sessions to pass, evals bought per pass and
    months of fees until a funded account (back-to-back evals on long resampled paths), worst drawdown inside an eval.
  * No look-ahead: every path is built from finished sessions; sizes were set at entry with what was known then.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import sys
import time
from zoneinfo import ZoneInfo

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import runlib as rl           # noqa: E402
from tools import research_risk as rr    # noqa: E402

PLAN = {"start": 50000.0, "target": 3000.0, "mll": 2000.0, "lock": 50100.0, "dll": 1000.0}
PRICE_LIST, PRICE_COUPON = 153.0, 100.0       # MFFU Builder 50K monthly fee (engine/analytics PLANS: $153 list, $92-107 couponed)
HORIZON = 60
H_WEEKS = {"2w": 10, "3w": 15, "4w": 20, "6w": 30}
BLOCK = 5
N_PATHS, N_CHAINS, CHAIN_MAX = 4000, 2000, 1260    # 1260 sessions = 5 years of chaining
POOLS = {"all": ("2000-01-01", "2100-01-01"), "2026": ("2026-01-01", "2026-12-31"), "2021-25": ("2021-01-01", "2025-12-31")}
ET = ZoneInfo("America/New_York")
LAB = os.path.join(ROOT, "research", "lab")
WRITEUPS = os.path.join(ROOT, "research", "writeups")


# ------------------------------------------------------------------------------------------------ data: one line per session
def session_ts(day):
    y, m, d = (int(x) for x in day.split("-"))
    return int(dt.datetime(y, m, d, 9, 30, tzinfo=ET).timestamp())


def build():
    """Per-session arrays for the locked strategy (live sizing) and for the fast-eval press (press / live versions)."""
    raw = rl.replay(quiet=True)
    T = rl.size(raw)
    S = rl.score(T, raw)
    sess = raw["sessions"]
    days = rl.days_of(T, sess)
    N = len(sess)
    pnl = np.array([d["pnl"] for d in days]); low = np.array([d["low"] for d in days])
    ntr = np.array([d["trades"] for d in days])
    # cold-streak state at the start of every session (the filter as the live loop computes it)
    raw_sorted = sorted(raw["trades"], key=lambda t: t["entry_t"])
    cold = np.array([rl.cold_status(raw_sorted, session_ts(d), rl.LIVE_EQF)[0] < 1 for d in sess])
    # press: every trade pre-sized two ways (eval less than $1,000 down -> press; else live), exact micro re-sizing
    Tp = rr.prep(raw)
    pol = {**rr.RECOMMENDED, **rr._press(60, -1000.0)}
    by = collections.defaultdict(list)
    for t in Tp:
        by[t["day"]].append(t)
    p_pnl = np.zeros(N); p_low = np.zeros(N); l_pnl = np.zeros(N); l_low = np.zeros(N)
    for k, d in enumerate(sess):
        for t in by.get(d, ()):
            for arr_p, arr_l, profit in ((p_pnl, p_low, 0.0), (l_pnl, l_low, -5000.0)):
                q, qe, _ = rr.qty_for(Tp, t, pol, {"profit": profit})
                if q <= 0:
                    continue
                pn, lo = rr.pnl_of(t, q, qe), t["_lpm"] * q
                pn, lo = rr.dll_cut(pn, min(lo, pn, 0.0))
                arr_p[k] += pn; arr_l[k] = min(arr_l[k], lo, arr_p[k])
    data = {"sessions": sess, "N": N, "pnl": pnl, "low": low, "ntr": ntr, "cold": cold,
            "press_pnl": p_pnl, "press_low": p_low, "live_pnl": l_pnl, "live_low": l_low,
            "raw": raw, "T": T, "S": S, "Tp": Tp, "pol": pol}
    data["streak"] = streak_lengths(cold)
    return data


def streak_lengths(cold):
    """For every session: how many sessions the current state (cold or not) has lasted, counting this one."""
    out = np.zeros(len(cold), dtype=int)
    run = 0
    for k in range(len(cold)):
        run = run + 1 if k and cold[k] == cold[k - 1] else 1
        out[k] = run
    return out


def pool_range(data, name):
    a, z = POOLS[name]
    idx = [k for k, d in enumerate(data["sessions"]) if a <= d <= z]
    return idx[0], idx[-1] + 1


# ------------------------------------------------------------------------------------------------ eval on one path
def run_eval(data, seq, mode="live", horizon=HORIZON, path=None):
    """One MFFU Builder 50K eval over the session indices `seq` (at most `horizon` of them).
    mode "live": day P&L as the locked strategy sized it. mode "press": the fast-eval press, sized from this eval's own
    balance (press version of the day while the eval is less than $1,000 down, live version below).
    Returns (result, days, max drawdown inside the eval, min cushion above the trailing floor)."""
    bal = peak = PLAN["start"]; mll = PLAN["start"] - PLAN["mll"]
    hi = PLAN["start"]; maxdd = 0.0; cush = PLAN["mll"]
    P, L = data["pnl"], data["low"]
    for n, k in enumerate(seq[:horizon], 1):
        if mode == "press":
            if bal - PLAN["start"] >= -1000.0:
                dp, lo = data["press_pnl"][k], data["press_low"][k]
            else:
                dp, lo = data["live_pnl"][k], data["live_low"][k]
        else:
            dp, lo = P[k], L[k]
        trough = bal + min(lo, dp, 0.0)
        maxdd = max(maxdd, hi - trough)
        cush = min(cush, trough - mll)
        if trough <= mll:
            bal += dp
            if path is not None:
                path.append(bal)
            return "FAIL", n, maxdd, cush
        bal += dp
        if path is not None:
            path.append(bal)
        hi = max(hi, bal); peak = max(peak, bal)
        mll = min(max(mll, peak - PLAN["mll"]), PLAN["lock"])
        if bal - PLAN["start"] >= PLAN["target"]:
            return "PASS", n, maxdd, cush
    return "OPEN", min(len(seq), horizon), maxdd, cush


# ------------------------------------------------------------------------------------------------ resampling schemes
class Sampler:
    """Draws session-index sequences from a pool with one of the schemes (iid / block5 / state5)."""

    def __init__(self, data, pool="all", scheme="block5", seed=7, block=BLOCK):
        self.d, self.scheme, self.block = data, scheme, block
        self.a, self.z = pool_range(data, pool)
        self.rng = np.random.default_rng(seed)
        self.starts = np.arange(self.a, self.z - block + 1)
        cold = data["cold"]
        self.end_state = {j: bool(cold[min(j + block, self.z - 1)]) for j in self.starts}
        self.by_state = {s: np.array([j for j in self.starts if bool(cold[j]) == s]) for s in (False, True)}

    def seq(self, length, start_set=None):
        """`length` session indices. start_set: candidate first-block starts (state5 / block5), else any start."""
        rng = self.rng
        if self.scheme == "iid":
            return rng.integers(self.a, self.z, size=length)
        out = []
        starts = self.starts if start_set is None else np.asarray(start_set)
        j = int(rng.choice(starts))
        while len(out) < length:
            out.extend(range(j, min(j + self.block, self.z)))
            if self.scheme == "state5":
                cand = self.by_state[self.end_state.get(j, bool(self.d["cold"][min(j + self.block, self.z - 1)]))]
                j = int(rng.choice(cand))
            else:
                j = int(rng.choice(self.starts))
        return np.array(out[:length])


def state_sets(data, pool, block_starts=True):
    """Session indices inside the pool by the cold-streak state at the eval's first session. block_starts: only indices
    that can start a full 5-session block (for the samplers); else every session of the pool (for the real history).
      warm / cold     full size / cold-streak quarter size at the start
      just_warmed     the first 3 sessions after a cold streak ended
      deep_cold       10 or more sessions into a cold streak"""
    a, z = pool_range(data, pool)
    cold, run = data["cold"], data["streak"]
    ok = range(a, z - BLOCK + 1) if block_starts else range(a, z)
    return {"any": list(ok),
            "warm": [j for j in ok if not cold[j]],
            "cold": [j for j in ok if cold[j]],
            "just_warmed": [j for j in ok if not cold[j] and run[j] <= 3 and j - run[j] >= 0],
            "deep_cold": [j for j in ok if cold[j] and run[j] >= 10]}


# ------------------------------------------------------------------------------------------------ Monte Carlo
def simulate(data, pool="all", scheme="block5", mode="live", n=N_PATHS, seed=7, start_set=None, keep_paths=0):
    """n fresh evals on resampled paths. Returns the summary dict (+ `paths` when keep_paths > 0)."""
    smp = Sampler(data, pool, scheme, seed)
    res, days, dds, cushs, paths = [], [], [], [], []
    for i in range(n):
        seq = smp.seq(HORIZON, start_set)
        p = [] if i < keep_paths else None
        r, dn, dd, cu = run_eval(data, seq, mode, HORIZON, p)
        res.append(r); days.append(dn); dds.append(dd); cushs.append(cu)
        if p is not None:
            paths.append({"days": [round(x) for x in p], "result": r, "days_n": dn})
    res, days, dds = np.array(res), np.array(days), np.array(dds)
    pct = lambda m: round(100.0 * float(np.mean(m)), 1)
    out = {"pool": pool, "scheme": scheme, "mode": mode, "n": n, "start": "any" if start_set is None else "set"}
    for lab, H in H_WEEKS.items():
        out[f"pass_{lab}"] = pct((res == "PASS") & (days <= H)); out[f"fail_{lab}"] = pct((res == "FAIL") & (days <= H))
        out[f"dec_{lab}"] = round(out[f"pass_{lab}"] + out[f"fail_{lab}"], 1)
    out["pass_60"] = pct(res == "PASS"); out["fail_60"] = pct(res == "FAIL"); out["open_60"] = pct(res == "OPEN")
    pd_ = days[res == "PASS"]
    out["pass_days"] = {"median": float(np.median(pd_)) if len(pd_) else None, "mean": round(float(pd_.mean()), 1) if len(pd_) else None,
                        "p25": float(np.percentile(pd_, 25)) if len(pd_) else None, "p75": float(np.percentile(pd_, 75)) if len(pd_) else None,
                        "p90": float(np.percentile(pd_, 90)) if len(pd_) else None,
                        "slow_pct": pct(pd_ > 15) if len(pd_) else None}        # passes slower than 3 weeks
    fd = days[res == "FAIL"]
    out["fail_days"] = {"median": float(np.median(fd)) if len(fd) else None, "p90": float(np.percentile(fd, 90)) if len(fd) else None}
    out["hist"] = {"pass_days": np.bincount(days[res == "PASS"], minlength=HORIZON + 1)[1:HORIZON + 1].tolist(),
                   "fail_days": np.bincount(days[res == "FAIL"], minlength=HORIZON + 1)[1:HORIZON + 1].tolist()}
    out["dd"] = {"median": round(float(np.median(dds))), "p90": round(float(np.percentile(dds, 90))),
                 "p99": round(float(np.percentile(dds, 99))), "worst": round(float(dds.max())),
                 "pass_median": round(float(np.median(dds[res == "PASS"]))) if len(pd_) else None,
                 "pass_worst": round(float(dds[res == "PASS"].max())) if len(pd_) else None,
                 "pass_near_death_pct": pct(np.array(cushs)[res == "PASS"] < 500) if len(pd_) else None}  # passed within $500 of failing
    if keep_paths:
        out["paths"] = paths
    return out


def chains(data, pool="all", scheme="block5", mode="live", n=N_CHAINS, seed=11, start_set=None):
    """Back-to-back evals (a new one the session after each pass or fail) on long resampled paths, until the first pass:
    evals bought, sessions / months until funded, and the long-run (passes + fails) / passes."""
    smp = Sampler(data, pool, scheme, seed)
    evals, sessions, funded = [], [], 0
    P_all = F_all = 0
    for _ in range(n):
        seq = smp.seq(CHAIN_MAX, start_set)
        k, ne, got = 0, 0, False
        while k < CHAIN_MAX:
            r, dn, _, _ = run_eval(data, seq[k:], mode, CHAIN_MAX - k)
            ne += 1; k += dn
            if r == "PASS":
                P_all += 1; got = True; break
            if r == "FAIL":
                F_all += 1; continue
            break                                      # OPEN at the end of the path
        if got:
            funded += 1; evals.append(ne); sessions.append(k)
        else:
            evals.append(ne); sessions.append(CHAIN_MAX)
    ev, se = np.array(evals), np.array(sessions)
    months = np.ceil(se / 21.0)
    pct = lambda m: round(100.0 * float(np.mean(m)), 1)
    return {"pool": pool, "scheme": scheme, "mode": mode, "n": n,
            "funded_pct": pct(se < CHAIN_MAX),
            "evals_per_pass_mean": round(float(ev.mean()), 2), "evals_per_pass_median": float(np.median(ev)),
            "evals_p90": float(np.percentile(ev, 90)),
            "longrun_evals_per_pass": round((P_all + F_all) / P_all, 2) if P_all else None,
            "weeks_to_funded_median": round(float(np.median(se)) / 5.0, 1), "weeks_to_funded_mean": round(float(se.mean()) / 5.0, 1),
            "weeks_to_funded_p90": round(float(np.percentile(se, 90)) / 5.0, 1),
            "funded_3m": pct(se <= 63), "funded_6m": pct(se <= 126), "funded_12m": pct(se <= 252),
            "months_fees_mean": round(float(months.mean()), 2), "months_fees_median": float(np.median(months)),
            "cost_list_mean": round(float(months.mean()) * PRICE_LIST), "cost_coupon_mean": round(float(months.mean()) * PRICE_COUPON),
            "cost_list_p90": round(float(np.percentile(months, 90)) * PRICE_LIST)}


def exact_rolling(data, pool="all", mode="live", start_set=None):
    """The real history, no resampling: a fresh eval started on every session of the pool (or of start_set) and followed
    for up to 60 sessions. Same definition as runlib.eval_speed, so it must match the dashboard's p10/f10/p20/f20."""
    a, z = pool_range(data, pool)
    starts = list(range(a, z)) if start_set is None else list(start_set)
    res, days = [], []
    for k in starts:
        r, dn, _, _ = run_eval(data, np.arange(k, z), mode, HORIZON)
        res.append(r); days.append(dn)
    res, days = np.array(res), np.array(days)
    n = max(1, len(res))
    pct = lambda m: round(100.0 * float(np.sum(m)) / n, 1)
    out = {"pool": pool, "mode": mode, "n_starts": len(starts)}
    for lab, H in H_WEEKS.items():
        out[f"pass_{lab}"] = pct((res == "PASS") & (days <= H)); out[f"fail_{lab}"] = pct((res == "FAIL") & (days <= H))
    out["pass_60"] = pct(res == "PASS"); out["fail_60"] = pct(res == "FAIL"); out["open_60"] = pct(res == "OPEN")
    pd_ = days[res == "PASS"]
    out["pass_med"] = float(np.median(pd_)) if len(pd_) else None
    return out


# ------------------------------------------------------------------------------------------------ reporting helpers
def money(x):
    return f"-${abs(x):,.0f}" if x < 0 else f"+${x:,.0f}" if x > 0 else "$0"


def prob_row(r):
    return (f"{r['pass_2w']}% / {r['fail_2w']}%", f"{r['pass_3w']}% / {r['fail_3w']}%", f"{r['pass_4w']}% / {r['fail_4w']}%",
            f"{r['pass_6w']}% / {r['fail_6w']}%", f"{r['pass_60']}% / {r['fail_60']}% / {r['open_60']}%",
            f"{r['pass_days']['median']:g}" if r['pass_days']['median'] is not None else "-")


def md_table(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---:" if i else "---" for i in range(len(head))) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out)


# ------------------------------------------------------------------------------------------------ checks
def check(data):
    """The bootstrap engine must reproduce runlib's exact rolling evals on the real sequence, and the press re-sizing must
    reproduce runlib.size's quantities in live mode."""
    S = data["S"]["spans"]
    ok = True
    for pool, key in (("all", "all"), ("2026", "2026"), ("2021-25", "2021-25")):
        e = exact_rolling(data, pool, "live")
        ref = S[key]
        same = abs(e["pass_2w"] - ref["p10"]) < 0.05 and abs(e["fail_2w"] - ref["f10"]) < 0.05 and \
            abs(e["pass_4w"] - ref["p20"]) < 0.05 and abs(e["fail_4w"] - ref["f20"]) < 0.05
        ok &= same
        print(f"check rolling {pool:8s}: mc 2w {e['pass_2w']}/{e['fail_2w']} 1m {e['pass_4w']}/{e['fail_4w']} | runlib "
              f"{ref['p10']}/{ref['f10']} {ref['p20']}/{ref['f20']} {'OK' if same else 'MISMATCH'}")
    # live-mode re-sizing through research_risk == runlib.size (the live-version arrays of the press mode)
    diff = float(np.abs(data["live_pnl"] - data["pnl"]).max())
    print(f"check press machinery, live version vs runlib.size day P&L: max diff ${diff:.2f} {'OK' if diff < 0.01 else 'MISMATCH'}")
    ok &= diff < 0.01
    # press chain on the real sequence vs the stored run risk_fast_press1000 (same replay -> identical day P&L)
    try:
        r = rl.load("risk_fast_press1000")
        stored = {d[0]: d[1] for d in r["days"]}
        sess = data["sessions"]
        k, mine = 0, {}
        while k < len(sess):
            bal = PLAN["start"]; peak = bal; mll = bal - PLAN["mll"]; done = False
            for j in range(k, len(sess)):
                dp, lo = (data["press_pnl"][j], data["press_low"][j]) if bal - PLAN["start"] >= -1000 else (data["live_pnl"][j], data["live_low"][j])
                mine[sess[j]] = dp
                if bal + min(lo, dp, 0) <= mll:
                    bal += dp; k = j + 1; done = True; break
                bal += dp; peak = max(peak, bal); mll = min(max(mll, peak - PLAN["mll"]), PLAN["lock"])
                if bal - PLAN["start"] >= PLAN["target"]:
                    k = j + 1; done = True; break
            if not done:
                break
        cmp = [(d, mine[d], stored.get(d)) for d in mine if stored.get(d) is not None]
        md = max(abs(a - b) for _, a, b in cmp) if cmp else None
        print(f"check press chain vs stored run risk_fast_press1000 (built {r['built']}, be_trend "
              f"{r.get('live_params', {}).get('be_at_r_trending')}): {len(cmp)} sessions, max day diff ${md:.2f}"
              + (" OK" if md is not None and md < 0.01 else " (differs: the stored run was built on the earlier lock; this study re-sizes the locked replay)"))
    except Exception as ex:  # pragma: no cover
        print("check press chain: skipped", ex)
    return ok


# ------------------------------------------------------------------------------------------------ main study
def study(n_paths=N_PATHS, n_chains=N_CHAINS, save=True):
    t0 = time.time()
    data = build()
    N = data["N"]
    cold = data["cold"]
    print(f"data: {N} sessions, {int(data['ntr'].sum())} trades, cold-state sessions {int(cold.sum())} ({100 * cold.mean():.0f}%), "
          f"{time.time() - t0:.1f}s")
    check(data)
    R = {"sim": {}, "chain": {}, "exact": {}, "cond": {}, "cond_exact": {}}
    # 1. unconditional: pools x schemes x modes
    for mode in ("live", "press"):
        for pool in POOLS:
            R["exact"][(mode, pool)] = exact_rolling(data, pool, mode)
            for scheme in ("iid", "block5", "state5"):
                key = (mode, pool, scheme)
                keep = 300 if key == ("live", "all", "block5") else 0
                R["sim"][key] = simulate(data, pool, scheme, mode, n_paths, seed=7, keep_paths=keep)
                if scheme != "iid" or pool == "all":
                    R["chain"][key] = chains(data, pool, scheme, mode, n_chains, seed=11)
                print(f"  {mode:5s} {pool:8s} {scheme:6s} 2w {R['sim'][key]['pass_2w']}/{R['sim'][key]['fail_2w']} "
                      f"60 {R['sim'][key]['pass_60']}/{R['sim'][key]['fail_60']}/{R['sim'][key]['open_60']} "
                      f"med {R['sim'][key]['pass_days']['median']} "
                      + (f"| chain evals/pass {R['chain'][key]['evals_per_pass_mean']} wks {R['chain'][key]['weeks_to_funded_median']}" if key in R["chain"] else "")
                      + f"  ({time.time() - t0:.0f}s)", flush=True)
    # 2. conditional on the cold-streak state at the start (state-matched blocks + the real history)
    for mode in ("live", "press"):
        for pool in ("all", "2021-25", "2026"):
            sets = state_sets(data, pool)
            exact_sets = state_sets(data, pool, block_starts=False)
            for name, st in sets.items():
                if name == "any" or len(st) < 8:
                    continue
                R["cond"][(mode, pool, name)] = {**simulate(data, pool, "state5", mode, n_paths, seed=19, start_set=st), "n_starts": len(st)}
                R["cond"][(mode, pool, name)]["chain"] = chains(data, pool, "state5", mode, n_chains // 2, seed=23, start_set=st)
                R["cond_exact"][(mode, pool, name)] = exact_rolling(data, pool, mode, start_set=exact_sets[name])
                c = R["cond"][(mode, pool, name)]; e = R["cond_exact"][(mode, pool, name)]
                print(f"  cond {mode:5s} {pool:8s} {name:12s} starts {len(st):4d}: 2w {c['pass_2w']}/{c['fail_2w']} 1m {c['pass_4w']}/{c['fail_4w']} "
                      f"60 {c['pass_60']}/{c['fail_60']}/{c['open_60']} | exact 2w {e['pass_2w']}/{e['fail_2w']} 1m {e['pass_4w']}/{e['fail_4w']} "
                      f"60 {e['pass_60']}/{e['fail_60']}", flush=True)
    print(f"simulations done in {time.time() - t0:.0f}s")
    # cold-streak facts for the write-up
    runs = []
    k = 0
    while k < N:
        j = k
        while j + 1 < N and cold[j + 1] == cold[k]:
            j += 1
        runs.append((bool(cold[k]), j - k + 1, data["sessions"][k], data["sessions"][j])); k = j + 1
    cold_runs = [r for r in runs if r[0]]
    R["cold_runs"] = cold_runs
    R["data"] = data
    if save:
        write_json(R)
        save_runs(R)
    print(report(R))
    return R


def write_json(R):
    main = R["sim"][("live", "all", "block5")]
    press = R["sim"][("press", "all", "block5")]
    paths = main["paths"]
    # mixed outcomes for the 3D view: proportional, with at least 40 of each outcome when available
    by = collections.defaultdict(list)
    for p in paths:
        by[p["result"]].append(p)
    pick = []
    for res in ("PASS", "FAIL", "OPEN"):
        pick.extend(by[res][:max(40, int(round(300 * len(by[res]) / max(1, len(paths)))))])
    pick = pick[:300]
    if len(pick) < 300:
        extra = [p for p in paths if p not in pick]
        pick.extend(extra[:300 - len(pick)])
    prob = lambda r: {"pass_2w": r["pass_2w"], "fail_2w": r["fail_2w"], "pass_3w": r["pass_3w"], "fail_3w": r["fail_3w"],
                      "pass_4w": r["pass_4w"], "fail_4w": r["fail_4w"], "pass_6w": r["pass_6w"], "fail_6w": r["fail_6w"],
                      "pass_60": r["pass_60"], "fail_60": r["fail_60"], "open_60": r["open_60"],
                      "pass_days_median": r["pass_days"]["median"], "pass_days_p90": r["pass_days"]["p90"],
                      "dd_median": r["dd"]["median"], "dd_p90": r["dd"]["p90"], "dd_worst": r["dd"]["worst"]}
    strip = lambda r: {k: v for k, v in r.items() if k not in ("paths",)}
    out = {"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "study": "mc", "writeup": "research/writeups/monte-carlo-evals.md",
           "strategy": "locked 2026-10-17 (live_model.json): quarter size when cold, half size on late entries, breakeven 3R on trending days",
           "plan": "MFFU Builder 50K: +$3,000 target, $2,000 EOD trailing max loss (intraday low checked), locks at $50,100",
           "method": f"{main['n']} resampled 60-session paths per case; block5 = blocks of 5 consecutive sessions, iid = single sessions, "
                     "state5 = 5-session blocks chained by the cold-streak state; all-years pool = 1,278 sessions Nov 2021 - Oct 2026",
           "paths": pick, "paths_pool": "all years, block5, locked strategy",
           "hist": main["hist"], "prob": prob(main), "press": prob(press),
           "press_rule": "run risk_fast_press1000: $800 on any stop while the eval is less than $1,000 down, else live sizing; "
                         "sized inside the simulation from each eval's own balance",
           "chain": {"locked": R["chain"][("live", "all", "block5")], "press": R["chain"][("press", "all", "block5")]},
           "cases": [strip(r) for r in R["sim"].values()],
           "chains": list(R["chain"].values()),
           "exact": list(R["exact"].values()),
           "conditional": [{**strip(r), "start_state": k[2]} for k, r in R["cond"].items()],
           "conditional_exact": [{**r, "start_state": k[2]} for k, r in R["cond_exact"].items()],
           "cold_streaks": [{"sessions": n, "from": a, "to": z} for _, n, a, z in R["cold_runs"]]}
    # the Liquidity Engine is archived since LIT went live (2026-10-18): its Monte Carlo goes to the archive, and
    # research/lab/montecarlo.json is LIT's (tools/lit_dash_data.py)
    arc = os.path.join(ROOT, "research", "archive", "engine-2026-10-17")
    os.makedirs(arc, exist_ok=True)
    rl._dump(out, os.path.join(arc, "montecarlo.json"), separators=(",", ":"))
    print("wrote research/archive/engine-2026-10-17/montecarlo.json", f"({os.path.getsize(os.path.join(arc, 'montecarlo.json')) // 1024} KB)")


def _mc_note(R, mode):
    s = R["sim"][(mode, "all", "block5")]; c = R["chain"][(mode, "all", "block5")]
    a = R["sim"][(mode, "2026", "block5")]; b = R["sim"][(mode, "2021-25", "block5")]
    return (f"Monte Carlo ({s['n']} resampled 60-session paths, 5-session blocks). All years: pass/fail within 2 weeks {s['pass_2w']}% / "
            f"{s['fail_2w']}%, within 1 month {s['pass_4w']}% / {s['fail_4w']}%, within 60 sessions {s['pass_60']}% / {s['fail_60']}% "
            f"({s['open_60']}% still open); median {s['pass_days']['median']:g} sessions to pass. 2026 pool: 2 weeks {a['pass_2w']}% / "
            f"{a['fail_2w']}%, 60 sessions {a['pass_60']}% / {a['fail_60']}%. 2021-25 pool: 2 weeks {b['pass_2w']}% / {b['fail_2w']}%, "
            f"60 sessions {b['pass_60']}% / {b['fail_60']}%. Back-to-back until funded (all years): {c['evals_per_pass_mean']} evals per "
            f"pass on average (median {c['evals_per_pass_median']:g}), median {c['weeks_to_funded_median']} weeks to a funded account, "
            f"{c['funded_3m']}% funded within 3 months, {c['months_fees_mean']} months of fees on average (${c['cost_list_mean']:,} at $153). "
            f"Worst drawdown inside an eval: median ${s['dd']['median']:,}, 1 in 10 worse than ${s['dd']['p90']:,}, worst ${s['dd']['worst']:,}.")


def save_runs(R):
    data = R["data"]; T, raw, S = data["T"], data["raw"], data["S"]
    q = "How likely is the MFFU 50K eval to pass or fail, how fast, and how many evals until funded?"
    rl.save("mc_locked", "Monte Carlo: locked strategy, MFFU 50K eval odds", "risk", q, params={}, sizing={"rule": "live sizing (locked 2026-10-17)"},
            trades=T, scored=S, status="info", writeup="research/writeups/monte-carlo-evals.md", tags=["monte-carlo", "eval"],
            verdict=_mc_note(R, "live"),
            notes="Same trades as the baseline; the Monte Carlo resamples their sessions (iid, 5-session blocks, and cold-state-matched "
                  "blocks) and runs a fresh MFFU Builder 50K eval on every path. Full tables: research/lab/montecarlo.json.")
    for pool, pid in (("2026", "mc_pool_2026"), ("2021-25", "mc_pool_2021_25")):
        a, z = POOLS[pool]
        TT = [t for t in T if a <= t["day"] <= z]
        sess = [d for d in raw["sessions"] if a <= d <= z]
        s = R["sim"][("live", pool, "block5")]; c = R["chain"][("live", pool, "block5")]
        rl.save(pid, f"Monte Carlo: {pool} trade pool only", "risk", q, params={}, sizing={"rule": "live sizing; trade pool restricted to " + pool},
                trades=TT, scored=rl.score(TT, sess), status="info", writeup="research/writeups/monte-carlo-evals.md", tags=["monte-carlo", "eval"],
                verdict=(f"Resampling only {pool} sessions ({s['n']} paths, 5-session blocks): pass/fail within 2 weeks {s['pass_2w']}% / {s['fail_2w']}%, "
                         f"1 month {s['pass_4w']}% / {s['fail_4w']}%, 60 sessions {s['pass_60']}% / {s['fail_60']}% ({s['open_60']}% open); median "
                         f"{s['pass_days']['median']:g} sessions to pass; {c['evals_per_pass_mean']} evals per pass, median {c['weeks_to_funded_median']} "
                         f"weeks to funded, {c['funded_3m']}% funded within 3 months."),
                notes="Info run: the trades are the baseline's trades of this period; the Monte Carlo numbers are in the verdict and in research/lab/montecarlo.json.")
    # press: back-to-back chain trades on the locked replay, sized from each eval's own balance (as run risk_fast_press1000)
    Tp, pol = data["Tp"], data["pol"]
    tr = rr.chain_trades(Tp, pol, raw["sessions"])
    Sp = rr.score(tr, raw, Tp, pol, eval_aware=True)
    rl.save("mc_press", "Monte Carlo: fast-eval press ($800 on any stop until $1,000 down)", "risk", q, params={},
            sizing={"rule": "while the eval balance is above $49,000: $800 at risk whatever the stop; below it live sizing; cold x0.25, late x0.5"},
            trades=tr, scored=Sp, status="info", writeup="research/writeups/monte-carlo-evals.md", tags=["monte-carlo", "eval", "fast-eval"],
            verdict=_mc_note(R, "press"),
            notes="Trades = back-to-back evals on the locked replay with the press (as run risk_fast_press1000, re-sized on the locked replay). "
                  "In the Monte Carlo the press is applied inside each simulated eval from its own balance.")
    print("saved runs mc_locked, mc_pool_2026, mc_pool_2021_25, mc_press")


def report(R):
    out = []
    head = ["case", "2 weeks pass / fail", "3 weeks", "4 weeks", "6 weeks", "60 sessions pass / fail / open", "median sessions to pass"]
    for mode in ("live", "press"):
        rows = []
        for pool in POOLS:
            e = R["exact"][(mode, pool)]
            rows.append((f"{pool} real history (rolling starts, n={e['n_starts']})", f"{e['pass_2w']}% / {e['fail_2w']}%", f"{e['pass_3w']}% / {e['fail_3w']}%",
                         f"{e['pass_4w']}% / {e['fail_4w']}%", f"{e['pass_6w']}% / {e['fail_6w']}%", f"{e['pass_60']}% / {e['fail_60']}% / {e['open_60']}%",
                         f"{e['pass_med']:g}" if e['pass_med'] else "-"))
            for scheme in ("iid", "block5", "state5"):
                rows.append((f"{pool} {scheme}", *prob_row(R["sim"][(mode, pool, scheme)])))
        out.append(f"\n### {mode}\n" + md_table(head, rows))
    return "\n".join(out)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd == "check":
        check(build())
    elif cmd == "quick":
        study(n_paths=500, n_chains=200, save=False)
    else:
        study()
