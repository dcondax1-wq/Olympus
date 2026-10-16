"""Five-year NQ research harness (real CME NQ1! history in data/NQ_5m.csv; never CFD).

  python tools/five_year.py runs      # full-history runs (old vs fixed account handling) + independent 8-week windows
  python tools/five_year.py skips     # per-year skip-reason census (why candidates did not become trades)

Results go to research/five_year/*.json; research/FIVE_YEAR_REPORT.md is written from them by `report`.
"""
from __future__ import annotations

import collections
import json
import math
import os
import sys
import time
from multiprocessing import Pool

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "research", "five_year")
WIN_SESS, WARM_SESS = 40, 25          # 8-week test windows, 5-week warm-up (pools, ADR, 10-day regime, 1h structure)


def _slim(t):
    return {"day": t["day"], "pnl": float(t["pnl"]), "r": float(t.get("pnl_r") or 0.0), "dir": t["dir"],
            "trigger": t.get("trigger"), "exit": t.get("exit_reason"), "qty": t.get("qty"), "entry_t": t["entry_t"],
            "risk_pts": float(t.get("risk_pts") or 0), "grade": t.get("grade"), "mae": float(t.get("mae") or 0),
            "regime": t.get("regime"),
            "f": {k: v for k, v in (t.get("features") or {}).items()
                  if k in REGIME_KEYS and (v is None or isinstance(v, (int, float)))}}


REGIME_KEYS = {"rg_er10", "rg_er5", "rg_vol_expansion", "rg_dir5", "rg_counter_5d", "vix_prev", "rg_pd_range_ratio",
               "rg_day_er", "rg_gap_adr", "htf_trend", "x_long", "rr_plan", "atr", "adr", "depth_atr", "x_wide_stop",
               "first_hour", "pm", "cisd", "news_day", "rg_trending_5d", "rg_rotational_5d", "x_with_day", "rg_fade_today"}


def bt(job):
    """job = (label, params, keep_from, keep_to). Runs one light backtest; keeps trades/days whose session is in range."""
    label, params, k0, k1 = job
    from engine.backtest import run
    r = run("NQ", "5m", params, light=True)
    keep = lambda d: (k0 is None or d >= k0) and (k1 is None or d <= k1)
    return {"label": label, "params": params,
            "trades": [_slim(t) for t in r["trades"] if keep(t["day"])],
            "days": [{"date": d["date"], "pnl": float(d["pnl"]), "trades": d.get("trades", 0),
                      "low": float(d.get("low_intraday", min(0.0, d["pnl"])))} for d in r["days"] if keep(d["date"])],
            "resets": r.get("account_resets", [])}


def sessions():
    from engine.data import load
    b = load("NQ", "5m")
    return sorted(set(b.date_str))


def window_jobs(params, label, win=WIN_SESS, warm=WARM_SESS):
    ss = sessions()
    jobs = []
    for a in range(warm, len(ss), win):
        z = min(a + win, len(ss)) - 1
        jobs.append((f"{label}:{ss[a]}", {**params, "days_from": ss[a - warm], "days_to": ss[z]}, ss[a], ss[z]))
    return jobs


def pool_map(jobs, procs=8):
    with Pool(min(procs, len(jobs))) as p:
        return p.map(bt, jobs)


def merge(outs, label):
    tr, dd, rs = [], [], []
    for o in outs:
        tr += o["trades"]; dd += o["days"]; rs += o["resets"]
    tr.sort(key=lambda t: t["entry_t"]); dd.sort(key=lambda d: d["date"])
    return {"label": label, "trades": tr, "days": dd, "resets": rs}


# ------------------------------------------------------------------------------------------------ stats
def boot_ci(x, n=4000, seed=7, q=(2.5, 97.5)):
    x = np.asarray(x, float)
    if len(x) < 5:
        return [None, None]
    rng = np.random.default_rng(seed)
    m = x[rng.integers(0, len(x), (n, len(x)))].mean(1)
    return [round(float(np.percentile(m, q[0])), 3), round(float(np.percentile(m, q[1])), 3)]


def seq_evals(days, plan):
    """Back-to-back MFFU evals over the period: start one, run until PASS/FAIL, start the next the following day."""
    from engine.analytics import simulate_eval
    pn = [d["pnl"] for d in days]
    lo = [d["low"] for d in days]
    k, res = 0, collections.Counter()
    lens = []
    while k < len(pn):
        r = simulate_eval(pn[k:], plan, lo[k:])
        res[r["result"]] += 1
        lens.append(r["days"])
        if r["result"] == "OPEN":
            break
        k += r["days"]
    return {"pass": res["PASS"], "fail": res["FAIL"], "open": res["OPEN"], "avg_days": round(float(np.mean(lens)), 1) if lens else None}


def roll_evals(days, plan):
    from engine.analytics import rolling_evals
    r = rolling_evals([{"date": d["date"], "pnl": d["pnl"], "low_intraday": d["low"]} for d in days], plan)
    return {"pass_rate": r["pass_rate"], "completed": r["completed"], "avg_days_to_pass": r["avg_days_to_pass"]}


def period_stats(trades, days, plan=None, evals=True):
    n = len(trades)
    pnl = np.array([t["pnl"] for t in trades]) if n else np.zeros(0)
    rr = np.array([t["r"] for t in trades]) if n else np.zeros(0)
    gp, gl = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    eq = np.cumsum(pnl) if n else np.zeros(1)
    dd = float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min()) if n else 0.0
    sess = len(days)
    out = {"sessions": sess, "trades": n, "tpw": round(n / max(sess / 5, 1e-9), 2),
           "wr": round(float((pnl > 0).mean() * 100), 1) if n else 0.0,
           "avg_r": round(float(rr.mean()), 3) if n else 0.0, "ci95_r": boot_ci(rr),
           "pf": round(float(gp / gl), 2) if gl > 0 else None, "net": round(float(pnl.sum()), 0), "max_dd": round(dd, 0),
           "zero_weeks": None}
    # weeks with zero trades (frequency consistency)
    wk = collections.Counter()
    import datetime as dt
    for d in days:
        y, w, _ = dt.date.fromisoformat(d["date"]).isocalendar()
        wk[(y, w)] += 0
    for t in trades:
        y, w, _ = dt.date.fromisoformat(t["day"]).isocalendar()
        wk[(y, w)] += 1
    if wk:
        out["zero_weeks"] = round(sum(1 for v in wk.values() if v == 0) / len(wk) * 100, 0)
    if evals and plan is not None and days:
        out["evals"] = seq_evals(days, plan)
        out["rolling"] = roll_evals(days, plan)
    return out


def by_period(res, key, plan):
    """key: 'year' | 'quarter'."""
    f = (lambda d: d[:4]) if key == "year" else (lambda d: f"{d[:4]}Q{(int(d[5:7]) - 1) // 3 + 1}")
    groups = collections.OrderedDict()
    for d in res["days"]:
        groups.setdefault(f(d["date"]), {"days": [], "trades": []})["days"].append(d)
    for t in res["trades"]:
        groups[f(t["day"])]["trades"].append(t)
    return {k: period_stats(v["trades"], v["days"], plan, evals=(key == "year")) for k, v in groups.items()}


def save(name, obj):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, default=lambda o: float(o) if isinstance(o, np.floating) else int(o))


def load_json(name):
    with open(os.path.join(OUT, name), encoding="utf-8") as fh:
        return json.load(fh)


# ------------------------------------------------------------------------------------------------ commands
def cmd_runs(procs=8):
    from engine.analytics import PLANS
    plan = PLANS["builder_50k"]
    t0 = time.time()
    full = [("full_old", {"account_reset_cushion": 0}, None, None), ("full_fixed", {}, None, None),
            ("full_flat", {"dd_aware": False}, None, None)]
    wj = window_jobs({}, "win")
    outs = pool_map(full + wj, procs)
    res = {o["label"]: o for o in outs[:len(full)]}
    res["windowed"] = merge(outs[len(full):], "windowed")
    summary = {}
    for k, v in res.items():
        summary[k] = {"total": period_stats(v["trades"], v["days"], plan), "year": by_period(v, "year", plan),
                      "quarter": by_period(v, "quarter", plan), "resets": v["resets"]}
        save(f"run_{k}.json", v)
    save("summary_runs.json", summary)
    print(f"done in {time.time() - t0:.0f}s")
    for k, v in summary.items():
        print(f"\n== {k}: {v['total']}  resets={len(v['resets'])}")
        for q, s in v["quarter"].items():
            print(f"  {q}: n={s['trades']:3d} tpw={s['tpw']:.2f} wr={s['wr']:5.1f} avgR={s['avg_r']:+.3f} pf={s['pf']} net={s['net']:+.0f}")


def _skip_census(job):
    label, params = job
    from engine.backtest import run
    r = run("NQ", "5m", params, light=False)
    import re
    c = collections.defaultdict(collections.Counter)
    for e in r["events"]:
        if e["type"] not in ("skip", "news", "risk"):
            continue
        import datetime as dt
        y = dt.datetime.utcfromtimestamp(e["t"]).strftime("%Y")
        txt = re.sub(r"[-+]?\d[\d,.]*", "#", e["text"])
        txt = re.sub(r"\[.*?\]", "[..]", txt)[:90]
        c[y][txt] += 1
    shadows = collections.Counter(s["day"][:4] for s in r["shadows"])
    taken = collections.Counter(s["day"][:4] for s in r["shadows"] if s.get("taken"))
    return {"label": label, "skips": {y: dict(v.most_common(25)) for y, v in c.items()},
            "shadows": dict(shadows), "taken": dict(taken)}


def cmd_skips(procs=4):
    jobs = [("fixed", {}), ("old", {"account_reset_cushion": 0})]
    with Pool(len(jobs)) as p:
        outs = p.map(_skip_census, jobs)
    save("skips.json", {o["label"]: o for o in outs})
    for o in outs:
        print("\n==", o["label"], "shadows", o["shadows"], "taken", o["taken"])
        for y, v in sorted(o["skips"].items()):
            print(" ", y)
            for k, n in list(v.items())[:12]:
                print(f"    {n:5d}  {k}")


def live_jobs(params, label, window_days=20):
    """Exact replay of the live loop: for every session D the engine sees only the last `window_days` calendar days of
    base bars (engine/live.py LIVE_DEFAULTS window_days=20, fresh 50K simulated balance each poll) and only day-D trades
    count."""
    import datetime as dt
    ss = sessions()
    jobs = []
    for k, d in enumerate(ss):
        if k < 15:
            continue
        a = (dt.date.fromisoformat(d) - dt.timedelta(days=window_days)).isoformat()
        jobs.append((f"{label}:{d}", {**params, "days_from": a, "days_to": d}, d, d))
    return jobs


def cmd_live(procs=10, params=None, label="live"):
    from engine.analytics import PLANS
    plan = PLANS["builder_50k"]
    t0 = time.time()
    jobs = live_jobs(params or {}, label)
    with Pool(procs) as p:
        outs = p.map(bt, jobs, chunksize=8)
    res = merge(outs, label)
    save(f"run_{label}.json", res)
    s = {"total": period_stats(res["trades"], res["days"], plan), "year": by_period(res, "year", plan),
         "quarter": by_period(res, "quarter", plan)}
    save(f"summary_{label}.json", s)
    print(f"{label}: {len(jobs)} replays in {time.time() - t0:.0f}s", s["total"])
    for q, v in s["quarter"].items():
        print(f"  {q}: n={v['trades']:3d} tpw={v['tpw']:.2f} wr={v['wr']:5.1f} avgR={v['avg_r']:+.3f} pf={v['pf']} net={v['net']:+.0f}")
    return s


GRID = {
    "baseline": {},
    "max_stop80": {"spec": {"max_stop": 80.0}}, "max_stop100": {"spec": {"max_stop": 100.0}},
    "max_stop45": {"spec": {"max_stop": 45.0}}, "min_stop15": {"spec": {"min_stop": 15.0}},
    "no_grade_sizing": {"grade_sizing": False, "conviction_step": 0},
    "no_giveback": {"exit_rules": ""}, "giveback_1r": {"exit_giveback_r": 1.0},
    "time_stop0": {"time_stop_min": 0}, "time_stop60": {"time_stop_min": 60}, "time_stop15": {"time_stop_min": 15},
    "be_off": {"be_at_r": 0}, "be_1.5": {"be_at_r": 1.5}, "be_0.75": {"be_at_r": 0.75},
    "min_rr2": {"min_rr": 2.0}, "min_rr1": {"min_rr": 1.0}, "max_rr3": {"max_rr": 3.0}, "max_rr8": {"max_rr": 8.0},
    "target_dol": {"target_mode": "dol"}, "target_fixed2": {"target_mode": "fixed", "fallback_rr": 2.0},
    "target_fixed3": {"target_mode": "fixed", "fallback_rr": 3.0},
    "regime_skip": {"regime_mode": "skip"}, "regime_off": {"regime_er10_max": 0},
    "range_off": {"day_range_max": 0}, "range_1.2": {"day_range_max": 1.2},
    "arm_minor_off": {"arm_minor": False}, "max1_day": {"max_trades_day": 1}, "no_stop_after_win": {"stop_after_win": False},
    "am_only": {"entry_windows": [[570, 690]]}, "am_wide": {"entry_windows": [[570, 720], [810, 930]]},
    "no_cisd": {"use_cisd": False}, "ifvg_outer": {"ifvg_pick": "outer"}, "stop_ifvg": {"stop_mode": "ifvg"},
    "min_score0": {"min_score": 0}, "min_score2": {"min_score": 2},
    "w_htf0": {"w_htf": 0}, "w_lrl0": {"w_lrl": 0}, "w_m15_0": {"w_m15": 0}, "w_pd0": {"w_pd": 0},
    "trail_r": {"trail_mode": "r"}, "trail_swing": {"trail_mode": "swing"},
    "buffer1.5": {"stop_buffer_mult": 1.5}, "arm_exp30": {"arm_expiry_min": 30}, "arm_exp90": {"arm_expiry_min": 90},
    "ifvg_15m": {"ifvg_tf": "highest"}, "news_off": {"news_filter": False}, "g_early0": {"g_early": 0}, "g_pd0": {"g_pd": 0},
    "partial50": {"partial_pct": 0.5}, "trend_model": {"trend_model": True},
}
_T, _NG, _RS, _M1, _AM = ({"trend_model": True}, {"grade_sizing": False, "conviction_step": 0}, {"regime_mode": "skip"},
                          {"max_trades_day": 1}, {"arm_minor": False})
COMBOS = {
    "baseline": {}, "trend": _T,
    "trend+max1": {**_T, **_M1}, "trend+rskip": {**_T, **_RS}, "trend+nograde": {**_T, **_NG},
    "trend+rskip+nograde": {**_T, **_RS, **_NG}, "rskip+nograde": {**_RS, **_NG}, "nograde+max1": {**_NG, **_M1},
    "trend+dir5": {**_T, "trend_require_dir5": True}, "trend+max1+nograde": {**_T, **_M1, **_NG},
    "trend+armminor_off": {**_T, **_AM}, "trend+armminor_off+rskip": {**_T, **_AM, **_RS},
    "trend+armminor_off+nograde": {**_T, **_AM, **_NG}, "trend+rskip+max1": {**_T, **_RS, **_M1},
    "trend_noregime": {**_T, "trend_require_regime": False}, "trend_noregime+max1": {**_T, "trend_require_regime": False, **_M1},
    "trend+fvg1.5": {**_T, "trend_fvg_mult": 1.5}, "trend+half": {**_T, "trend_full_size": False},
}
TRAIN = ("2021-10-01", "2024-12-31")
TEST = ("2025-01-01", "2026-10-31")
TEST_CLEAN = ("2025-01-01", "2026-07-31")     # excludes Aug-Oct 2026, the window the defaults were tuned on


def _span(res, a, z):
    tr = [t for t in res["trades"] if a <= t["day"] <= z]
    ds = [d for d in res["days"] if a <= d["date"] <= z]
    s = period_stats(tr, ds, None, evals=False)
    s["total_r"] = round(sum(t["r"] for t in tr), 1)
    return s


def grid_summary(res):
    yrs = by_period(res, "year", None)
    return {"train": _span(res, *TRAIN), "test": _span(res, *TEST), "test_clean": _span(res, *TEST_CLEAN),
            "years": {y: {k: v[k] for k in ("trades", "tpw", "avg_r", "pf", "net")} for y, v in yrs.items()}}


def cmd_grid(procs=6, mode="full"):
    G = COMBOS if mode == "combo" else GRID
    keys = list(G)
    if mode == "flat":
        jobs = [(k, {**G[k], "dd_aware": False}, None, None) for k in keys]
    else:
        jobs = [(k, G[k], None, None) for k in keys]
    t0 = time.time()
    outs = pool_map(jobs, procs)
    out = {o["label"]: {"params": o["params"], **grid_summary(o)} for o in outs}
    save(f"grid_{mode}.json", out)
    b = out["baseline"]
    print(f"grid {mode}: {len(jobs)} runs in {time.time() - t0:.0f}s")
    hdr = f"{'variant':18s} {'trainR':>7s} {'train$':>7s} {'testR':>7s} {'test$':>7s} {'cleanR':>7s} {'clean$':>7s}  tpw/yr"
    print(hdr)
    for k, v in sorted(out.items(), key=lambda kv: -kv[1]["train"]["total_r"]):
        print(f"{k:18s} {v['train']['total_r']:+7.1f} {v['train']['net']:+7.0f} {v['test']['total_r']:+7.1f} {v['test']['net']:+7.0f} "
              f"{v['test_clean']['total_r']:+7.1f} {v['test_clean']['net']:+7.0f}  " + " ".join(f"{y[2:]}:{s['tpw']:.1f}" for y, s in v["years"].items()))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "runs"
    if cmd == "grid":
        cmd_grid(mode=sys.argv[2] if len(sys.argv) > 2 else "full")
        sys.exit(0)
    if cmd == "live":
        extra = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
        cmd_live(params=extra, label=sys.argv[3] if len(sys.argv) > 3 else "live")
    else:
        {"runs": cmd_runs, "skips": cmd_skips}[cmd]()
