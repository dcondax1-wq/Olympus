"""Research run library: every backtest the lab runs is stored with its data in research/runs/, scored the same way as the
live results (tools/export_backtest.py), so the dashboard can list, compare and open every run.

  from tools import runlib as rl
  raw = rl.replay({"be_at_r": 1.5})            # exact live-loop replay on top of live_model.json params (cached, see below)
  T = rl.size(raw)                             # live sizing: cold-streak filter (half size), engine micros
  T = rl.size(raw, rule=my_rule)               # my_rule(t, ctx) -> size multiplier (0 = skip the trade), see size()
  S = rl.score(T, raw)                         # 2026 YTD / 2021-25 / All years + each year: stats, MFFU evals, months
  rl.save("risk_ref30", "Full risk up to a 30-pt stop", "risk", "Do wide stops deserve more risk?",
          params={"risk_ref_stop": 30}, trades=T, scored=S, status="rejected", verdict="...", notes="...")
  rl.index()                                   # rebuild research/runs/index.json (save() does it too)

  python tools/runlib.py baseline              # replay + store the live strategy as run "baseline"
  python tools/runlib.py index                 # rebuild the index
  python tools/runlib.py show <id>             # print one run's headline numbers

Judging (CLAUDE.md): a change counts only if it holds in 2026 AND in 2021-25 and keeps 2+ trades a week. Real CME NQ1!
history only (data/NQ_5m.csv). Replays are cached in research/runs/_cache (gitignored), keyed by the params, the data file
and ENGINE_EPOCH. New engine options must default to today's behaviour (then old cache entries stay valid); if you change
what an existing option does, bump ENGINE_EPOCH (or pass fresh=True).

Sizing after the replay is exact for multipliers on the engine's micros: P&L, commission and slippage are all linear in
the number of micros. A rule may only use what was known at entry: the trade's own setup fields (risk_pts, dir, trigger,
regime, htf_trend, pd_pos, features `f`, ...) and trades that had finished before it (ctx). Never mfe / mae / bars_held /
exit / r / pnl of the trade itself.
"""
from __future__ import annotations

import collections
import datetime as dt
import glob
import hashlib
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
RUNS = os.path.join(ROOT, "research", "runs")
CACHE = os.path.join(RUNS, "_cache")
LIVE = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))
LIVE_PARAMS, LIVE_EQF, LIVE_SIZING = LIVE["params"], LIVE.get("equity_filter"), LIVE.get("sizing")
MAX_MICROS = 40                                   # engine max_micros (MFFU 50K: 4 minis / 40 micros)
FAMILIES = ("baseline", "risk", "stops", "targets", "management", "bias", "filters", "timing", "other")
STATUSES = ("baseline", "adopt-candidate", "promising", "rejected", "info")
TRADE_COLS = ["day", "entry_t", "exit_t", "dir", "r", "pnl", "risk_pts", "qty", "risk_usd", "half", "exit", "trigger", "mfe", "mae",
              "bars_held", "regime", "mult"]


# ------------------------------------------------------------------------------------------------ replay (cached)
ENGINE_EPOCH = 1


def _data_key():
    st = os.stat(os.path.join(ROOT, "data", "NQ_5m.csv"))
    return f"{st.st_size}:{ENGINE_EPOCH}"


def _dump(obj, path, **kw):
    """Atomic JSON write (several research processes save runs at the same time)."""
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, **kw)
    os.replace(tmp, path)


def replay(extra=None, base=None, procs=4, label="lab", quiet=False, fresh=False):
    """Exact live-loop replay (tools/five_year.live_jobs: 20-day window per session, as engine/live.py) of base (default
    live_model.json params) + extra. Returns {"params", "sessions", "trades"} with the raw engine trades (full engine
    micros, before the cold-streak filter). Cached on disk."""
    from multiprocessing import Pool
    from tools import export_backtest as ex   # noqa: F401  (installs the rich trade record used in the workers)
    from tools import five_year as fy
    params = {**(LIVE_PARAMS if base is None else base), **(extra or {})}
    key = hashlib.sha1((json.dumps(params, sort_keys=True) + _data_key()).encode()).hexdigest()[:16]
    path = os.path.join(CACHE, key + ".json")
    if os.path.exists(path) and not fresh:
        return json.load(open(path, encoding="utf-8"))
    t0 = time.time()
    with Pool(procs) as pool:
        outs = pool.map(fy.bt, fy.live_jobs(params, label), chunksize=4)
    res = fy.merge(outs, label)
    out = {"params": params, "sessions": sorted({d["date"] for d in res["days"]}), "trades": res["trades"],
           "seconds": round(time.time() - t0)}
    os.makedirs(CACHE, exist_ok=True)
    _dump(out, path, separators=(",", ":"))
    if not quiet:
        print(f"replay {key}: {len(out['trades'])} trades, {len(out['sessions'])} sessions, {out['seconds']}s", flush=True)
    return out


# ------------------------------------------------------------------------------------------------ sizing
def cold_status(raw_sorted, entry_t, eqf):
    """The cold-streak filter exactly as engine/equity_filter.status: sum of the last `lookback` signals (any size) that
    finished before entry_t, in entry order. Returns (mult, sum_r)."""
    if not eqf:
        return 1.0, None
    lb, thr, half = int(eqf.get("lookback", 15)), float(eqf.get("min_sum_r", 0.0)), eqf.get("cold_mode", "skip") == "half"
    cold_size = min(1.0, max(0.0, float(eqf.get("cold_size", 0.5)))) if half else 0.0
    rows = [t for t in raw_sorted if t.get("exit_t") and int(t["exit_t"]) < int(entry_t)]
    last = rows[-lb:]
    s = round(sum(float(t["r"]) for t in last), 2)
    on = len(last) < lb or s > thr
    return (1.0 if on else cold_size), s


def size(raw, eqf="live", rule=None, max_micros=MAX_MICROS, sizing="live"):
    """Sized trades from a replay. eqf: "live" (live_model.json filter), None (off) or a filter dict. sizing: "live"
    (live_model.json "sizing": late-entry size; the fast-eval press is never applied here), None (off) or a dict.
    rule(t, ctx) -> multiplier on the engine's micros after the filter (0 skips the trade). ctx: {"finished": trades
    (sized, this run) that exited before t entered, "equity", "peak", "dd" (sized $), "day_pnl", "cold_mult", "cold_sum_r",
    "streak" (+n wins / -n losses in a row of finished trades)}. Returns trade dicts with qty/pnl/risk_usd after sizing."""
    from engine import sizing as szm
    eqf = LIVE_EQF if eqf == "live" else eqf
    sizing = LIVE_SIZING if sizing == "live" else sizing
    sizing = {**(sizing or {}), "press": None}
    raw_sorted = sorted(raw["trades"], key=lambda t: t["entry_t"])
    out, done = [], []
    for t in raw_sorted:
        q0 = int(t.get("qty") or 0)
        if q0 <= 0:
            continue
        per = float(t["pnl"]) / q0
        cm, cs = cold_status(raw_sorted, t["entry_t"], eqf)
        if cm <= 0:
            continue
        q = szm.route_qty(q0, t, cm, sizing, LIVE_PARAMS)["qty"]
        m = 1.0
        if rule:
            fin = [x for x in done if x["exit_t"] and x["exit_t"] < t["entry_t"]]
            eq = sum(x["pnl"] for x in fin)
            peak, run = 0.0, 0.0
            for x in fin:
                run += x["pnl"]; peak = max(peak, run)
            streak = 0
            for x in reversed(fin):
                s = 1 if x["r"] > 0 else -1
                if streak == 0 or (s > 0) == (streak > 0):
                    streak += s
                else:
                    break
            ctx = {"finished": fin, "equity": eq, "peak": peak, "dd": eq - peak, "cold_mult": cm, "cold_sum_r": cs, "streak": streak,
                   "day_pnl": sum(x["pnl"] for x in fin if x["day"] == t["day"])}
            m = float(rule(t, ctx))
            if m <= 0:
                continue
            q = max(1, min(max_micros, int(q * m))) if m < 1 else min(max_micros, int(q * m))
        rp = float(t.get("risk_pts") or 0)
        x = {**t, "qty": q, "pnl": round(per * q, 2), "risk_usd": round(rp * 2.0 * q, 2), "half": cm < 1, "mult": round(q / q0, 3),
             "low": -min(float(t.get("mae") or 0), max(1.0, -float(t["r"]))) * rp * 2.0 * q}
        out.append(x); done.append(x)
    return out


def days_of(trades, sessions):
    by = collections.defaultdict(list)
    for t in trades:
        by[t["day"]].append(t)
    days = []
    for d in sessions:
        cum = low = 0.0
        for t in by.get(d, []):
            low = min(low, cum + t.get("low", min(0.0, t["pnl"]))); cum += t["pnl"]; low = min(low, cum)
        days.append({"date": d, "pnl": round(cum, 2), "low": round(low, 2), "trades": len(by.get(d, []))})
    return days


# ------------------------------------------------------------------------------------------------ scoring
SPANS = (("2026", "2026-01-01", "2026-12-31"), ("2021-25", "2021-01-01", "2025-12-31"), ("all", "2000-01-01", "2100-01-01"))


def eval_speed(days, horizon=60):
    """Owner's rule (2026-10-17): on the 50K an eval should be decided within 2 weeks and never take over 3 weeks to
    pass. A fresh MFFU Builder 50K eval is started on every session and run up to `horizon` sessions:
      p10/f10, p15/f15, p20/f20  % of starts that passed / failed within 10, 15, 20 sessions
      dec10                      % decided (passed or failed) within 10 sessions
      slow_pass                  % of all passes (within the horizon) that needed more than 15 sessions
      pass_med                   median sessions of a pass
      b2b                        back-to-back evals passed/failed (a new eval the day after each one ends)"""
    from engine.analytics import PLANS, simulate_eval
    plan = PLANS["builder_50k"]
    pn = [d["pnl"] for d in days]; lo = [d["low"] for d in days]
    res = [simulate_eval(pn[i:i + horizon], plan, lo[i:i + horizon]) for i in range(len(days))]
    n = len(res) or 1
    pct = lambda c: round(100 * c / n, 1)
    passes = [r["days"] for r in res if r["result"] == "PASS"]
    out = {}
    for H in (10, 15, 20):
        out[f"p{H}"] = pct(sum(1 for r in res if r["result"] == "PASS" and r["days"] <= H))
        out[f"f{H}"] = pct(sum(1 for r in res if r["result"] == "FAIL" and r["days"] <= H))
    out["dec10"] = round(out["p10"] + out["f10"], 1)
    out["slow_pass"] = round(100 * sum(1 for d in passes if d > 15) / len(passes), 1) if passes else None
    out["pass_med"] = float(np.median(passes)) if passes else None
    k, pa, fa = 0, 0, 0
    while k < len(days):
        x = simulate_eval(pn[k:], plan, lo[k:])
        if x["result"] == "OPEN":
            break
        pa += x["result"] == "PASS"; fa += x["result"] == "FAIL"; k += x["days"]
    out["b2b"] = f"{pa}/{fa}"
    return out


def _compact(T, D):
    """The dashboard columns for one span."""
    from tools.export_backtest import _stats
    s = _stats(T, D) if T else None
    if not s:
        return {"n": 0}
    e = eval_speed(D)
    return {"n": s["trades"], "tpw": s["per_week"], "wk2": s["weeks_2plus_pct"], "win": s["win_pct"], "pf": s["pf"], "net": round(s["net"]),
            "dd": round(s["max_dd"]), "avg_r": round(float(np.mean([t["r"] for t in T])), 3), "stop": s["median_stop_pts"],
            "worst_day": round(s["worst_day"]), "risk": s["median_risk_usd"], "half": s["half_size_trades"],
            "per_month": round(s["net"] / max(len(D) / 21, 1e-9)), **e}


def score(trades, raw_or_sessions):
    """Headline spans (2026, 2021-25, all) + every year + months, all from the sized trades."""
    sess = raw_or_sessions["sessions"] if isinstance(raw_or_sessions, dict) else list(raw_or_sessions)
    days = days_of(trades, sess)
    out = {"spans": {}, "years": {}, "months": {}}
    for name, a, z in SPANS:
        T = [t for t in trades if a <= t["day"] <= z]; D = [d for d in days if a <= d["date"] <= z]
        out["spans"][name] = _compact(T, D) if D else {"n": 0}
    for y in sorted({d["date"][:4] for d in days}):
        T = [t for t in trades if t["day"][:4] == y]
        p = np.array([t["pnl"] for t in T]) if T else np.array([0.0])
        gl = -p[p < 0].sum()
        out["years"][y] = {"n": len(T), "net": round(float(p.sum())), "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None,
                           "win": round(100 * float((p > 0).mean()), 1) if T else None}
    for t in trades:
        m = out["months"].setdefault(t["day"][:7], {"net": 0.0, "n": 0, "wins": 0})
        m["net"] = round(m["net"] + t["pnl"], 2); m["n"] += 1; m["wins"] += t["pnl"] > 0
    out["days"] = days
    return out


def passes(S, base=None, min_tpw=2.0, max_tpw=4.0):
    """The owner's rule: better than the baseline on 2026 AND 2021-25 (net and PF), and 2-4 trades a week in both."""
    a, b = S["spans"]["2026"], S["spans"]["2021-25"]
    if not (min_tpw <= (a.get("tpw") or 0) <= max_tpw and min_tpw <= (b.get("tpw") or 0) <= max_tpw):
        return False
    if base is None:
        return True
    A, B = base["spans"]["2026"], base["spans"]["2021-25"]
    return (a["net"] > A["net"] and (a["pf"] or 0) >= (A["pf"] or 0) and b["net"] > B["net"] and (b["pf"] or 0) >= (B["pf"] or 0))


# ------------------------------------------------------------------------------------------------ store
def _round(v):
    return round(v, 3) if isinstance(v, float) else v


def save(id, title, family, question, params=None, sizing=None, trades=None, scored=None, status="info", verdict="", notes="",
         writeup=None, tags=None):
    """Store one run: research/runs/<id>.json (headline numbers + every trade + every day) and refresh the index."""
    assert family in FAMILIES, family
    assert status in STATUSES, status
    os.makedirs(RUNS, exist_ok=True)
    S = scored or score(trades, sorted({t["day"] for t in trades}))
    rec = {"id": id, "title": title, "family": family, "question": question, "status": status, "verdict": verdict, "notes": notes,
           "writeup": writeup, "tags": tags or [], "params": params or {}, "sizing": sizing or {}, "live_params": LIVE_PARAMS,
           "live_equity_filter": LIVE_EQF, "built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "data": "TradingView CME NQ1! 5m",
           "method": "exact live-loop replay (20-day window per session) + cold-streak filter + sizing; costs included",
           "spans": S["spans"], "years": S["years"], "months": S["months"],
           "trade_cols": TRADE_COLS, "trades": [[_round(t.get(c)) if c != "half" else int(bool(t.get("half"))) for c in TRADE_COLS] for t in trades or []],
           "day_cols": ["date", "pnl", "low", "trades"], "days": [[d["date"], d["pnl"], d["low"], d["trades"]] for d in S["days"]]}
    _dump(rec, os.path.join(RUNS, id + ".json"), separators=(",", ":"))
    index()
    return rec


def load(id):
    return json.load(open(os.path.join(RUNS, id + ".json"), encoding="utf-8"))


def index():
    rows = []
    for p in sorted(glob.glob(os.path.join(RUNS, "*.json"))):
        if os.path.basename(p) == "index.json" or p.endswith(".tmp"):
            continue
        try:
            r = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        rows.append({k: r.get(k) for k in ("id", "title", "family", "question", "status", "verdict", "writeup", "tags", "params",
                                           "sizing", "built", "spans")})
    order = {s: i for i, s in enumerate(STATUSES)}
    rows.sort(key=lambda r: (order.get(r["status"], 9), r["family"], r["id"]))
    _dump({"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "baseline": "baseline", "count": len(rows),
                   "columns": {"n": "trades", "tpw": "trades/week", "wk2": "% weeks with 2+", "win": "win %", "pf": "profit factor",
                               "net": "net $", "per_month": "net $ per month", "dd": "max drawdown $", "avg_r": "avg R", "stop": "median stop pts",
                               "risk": "median $ at risk", "p10": "eval pass % in 2 weeks", "f10": "eval fail % in 2 weeks",
                               "dec10": "% evals decided in 2 weeks", "p15": "eval pass % in 3 weeks", "f15": "eval fail % in 3 weeks",
                               "p20": "eval pass % in 1 month", "f20": "eval fail % in 1 month", "slow_pass": "% of passes slower than 3 weeks",
                               "pass_med": "median sessions to pass", "b2b": "back-to-back evals passed/failed"},
                   "owner_rules": "2-4 trades a week; judged on 2026 and 2021-25; evals decided within 2 weeks, no pass slower than 3 weeks",
                   "runs": rows}, os.path.join(RUNS, "index.json"), indent=1)
    return rows


def line(S, name="2026"):
    s = S["spans"][name]
    if not s.get("n"):
        return f"{name}: no trades"
    return (f"{name}: n={s['n']} tpw={s['tpw']} wk2={s['wk2']}% win={s['win']}% PF={s['pf']} net={s['net']:+,} (${s.get('per_month', 0):,}/mo) "
            f"DD={s['dd']:,} eval2w {s['p10']}/{s['f10']} dec {s.get('dec10')}% eval3w {s.get('p15')}/{s.get('f15')} "
            f"slow {s.get('slow_pass')}% med {s.get('pass_med')} b2b {s['b2b']}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "index"
    if cmd == "baseline":
        raw = replay()
        T = size(raw)
        S = score(T, raw)
        for k in ("2026", "2021-25", "all"):
            print(line(S, k))
        save("baseline", "Live strategy (locked 2026-10-17)", "baseline", "What the live bot does today",
             params={}, trades=T, scored=S, status="baseline",
             verdict="The reference every experiment is judged against.", notes=LIVE.get("label", ""))
    elif cmd == "rescore":
        # recompute every stored run's spans/years from its stored trades and days (new columns, same data)
        for path in sorted(glob.glob(os.path.join(RUNS, "*.json"))):
            if os.path.basename(path) == "index.json":
                continue
            r = json.load(open(path, encoding="utf-8"))
            T = [dict(zip(r["trade_cols"], a)) for a in r["trades"]]
            for t in T:
                t["half"] = bool(t["half"])
                t["low"] = -min(float(t.get("mae") or 0), max(1.0, -float(t["r"]))) * float(t["risk_pts"]) * 2.0 * int(t["qty"])
            S = score(T, [d[0] for d in r["days"]])
            r["spans"], r["years"], r["months"] = S["spans"], S["years"], S["months"]
            r["days"] = [[d["date"], d["pnl"], d["low"], d["trades"]] for d in S["days"]]
            _dump(r, path, separators=(",", ":"))
            print("rescored", r["id"], line(r, "2026")[:80])
        index()
    elif cmd == "show":
        r = load(sys.argv[2])
        print(r["title"], "|", r["status"], "|", r["verdict"])
        for k in ("2026", "2021-25", "all"):
            print(line(r, k))
    else:
        print(len(index()), "runs indexed")
