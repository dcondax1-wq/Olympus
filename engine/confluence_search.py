"""Confluence learning loop (futures only).

Every recorded feature on every candidate (shadow) trade is a candidate confluence. Each run:

  (a) re-runs the engine on real CME futures - NQ (the traded instrument) and ES (cross-instrument robustness check
      only) - and rebuilds week-block folds of NQ from whatever history is in data/ (nothing hard-coded: add CME
      history and the folds grow automatically);
  (b) scans each feature: lift (avg R present minus absent) per NQ fold on all candidates AND on taken trades, plus
      ES, with a bootstrap confidence interval. The SIGN is decided on the earlier ("decide") folds only and must be
      confirmed on the later ("confirm") folds - walk-forward, no lookahead;
  (c) every sign-stable feature is tested as a grade sizing weight (+-1 / +-2) - through real g_* engine params where
      they exist, otherwise by post-processing the trade list (each trade's pnl rescaled by the grade multiplier the
      new weight would give; marked "needs engine hook") - and as an entry filter (hard gate) when trade frequency
      allows;
  (d) every ACTIVE confluence (live in the engine's grade or score gate) is tested for removal / re-weighting;
  (e) the adoption rule decides: ACTIVE / PROBATION / CANDIDATE / RETIRED, with the evidence and a plain-English
      reason. Retired confluences are re-scanned every run and come back automatically if the evidence turns.

Adoption rule (all must hold):  NQ out-of-sample (confirm folds) P&L improves, NQ decide folds improve, NQ total stays
positive, NQ 2.0-4.5 trades/week overall and in every fold (a fold already below 2.0 at baseline may not lose
trades), and ES total P&L is not hurt. Partly passing -> PROBATION. Failing -> RETIRED.

This module never edits engine DEFAULTS: passing changes are written as recommended params for the lead.

CLI:  python -m engine.confluence_search --run      full cycle, writes data/confluence_registry.json + research/CONFLUENCE_LOG.md
      python -m engine.confluence_search --report   print the registry summary
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
import zlib
from multiprocessing import Pool

import numpy as np

from .data import DATA_DIR

ROOT = os.path.dirname(DATA_DIR)
REG_PATH = os.path.join(DATA_DIR, "confluence_registry.json")
LOG_PATH = os.path.join(ROOT, "research", "CONFLUENCE_LOG.md")

PRIMARY, CHECK = "NQ", "ES"            # real CME futures only (no CFD data anywhere)
FLAT = {"dd_aware": False, "daily_max_loss": 1e9}      # flat sizing, same as the study_* scripts
WIDE = {"max_trades_day": 9, "stop_after_win": False, "min_score": -99, "daily_max_loss": 1e9, "dd_aware": False}
FOLD_SESSIONS = 10                      # 2-week folds
MIN_FOLDS, MAX_FOLDS = 3, 8             # more history -> more (or longer) folds
CONFIRM_FRAC = 0.4                      # last 40% of folds confirm what the first 60% decided
TPW_MIN, TPW_MAX = 2.0, 4.5             # owner: 2-4 trades/week, small tolerance, never below 2.0
MIN_SIDE = 3                            # samples needed on each side (present / absent) to measure a fold's lift
KEEP_MIN_USD = 150.0                    # a live confluence "earns its place" only if removing it costs at least this on NQ
BOOT, SEED = 2000, 7
POOL_N = 4
SKIP = {"gex_bn", "gex_pct", "dix", "pd_pos", "vix_prev", "q90_entry", "q90_sweep", "micro_entry"}

# live grade checklist items: (registry id / feature, checklist label prefix, engine param or "hook" for hard-coded weights)
GRADE_ITEMS = [
    ("htf_trend", "1H structure with the trade", "hook"),
    ("pd", "Sweep in discount / premium", "g_pd"),
    ("x_swept_london", "Raid not on the London", "g_london"),
    ("vwap_disc", "Entry on the value side", "hook"),
    ("vol_climax", "No volume climax", "hook"),
    ("lrl", "Clear path to target", "hook"),
    ("first_hour", "Not the opening hour", "hook"),
    ("m15_trend", "15m structure not already", "hook"),
    ("qt_q2_sweep", "Quarterly Theory: Q2", "hook"),
    ("qt_90_open", "Raid beyond the 90-min", "hook"),
    ("day_stretched", "Day not already stretched", "hook"),
    ("x_swept_h1", "Raid not on a 1H swing", "g_h1sweep"),
    ("x_early_session", "Past the first 45", "g_early"),
    ("multi_sweep", "Single clean raid", "g_stacked"),
    ("qt_entry_q3", "Q2 sweep, not a Q3", "g_q3"),
]
G_PENALTY = {"x_swept_h1": "g_h1sweep", "x_early_session": "g_early", "multi_sweep": "g_stacked",
             "x_swept_london": "g_london", "qt_entry_q3": "g_q3"}     # grade effect when present = -g
G_SIGNED = {"pd": "g_pd"}                                             # grade effect = state x g
# score-gate weights (entry filter: score >= min_score)
W_KEYS = {"htf_trend": "w_htf", "protected": "w_protected", "lrl": "w_lrl", "amt": "w_amt", "smt": "w_smt",
          "quality": "w_quality", "mtf_net": "w_mtf", "m15_trend": "w_m15", "pd": "w_pd", "midnight": "w_midnight",
          "keylevel": "w_keylevel", "dol_align": "w_dol", "disp_strong": "w_disp", "fast_reclaim": "w_fast",
          "multi_sweep": "w_multi", "major_swept": "w_major", "vol_climax": "w_vol", "shallow_raid": "w_shallow",
          "first_hour": "w_first", "vwap_disc": "w_vwap"}
EXTRA_NAMES = {"day_stretched": "Day already stretched (>=1.2x ADR)", "qt_q2_sweep": "QT: sweep in Q2"}


def _names():
    try:
        from .discovery import NAMES
        return {**NAMES, **EXTRA_NAMES}
    except Exception:
        return dict(EXTRA_NAMES)


def _progress(i, n, msg):
    print(f"PROGRESS {i}/{n} {msg}", flush=True)


def _num(v):
    if v is None or isinstance(v, bool):
        return None if v is None else int(v)
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


# ------------------------------------------------------------------------------------------------ backtests (cached)
_STAMPS = {}     # frozen per process (one learning cycle): files appended mid-cycle must not change cache keys


def _data_stamp(sym):
    if sym in _STAMPS:
        return _STAMPS[sym]
    p = os.path.join(DATA_DIR, f"{sym}_5m.csv")
    try:
        st = os.stat(p)
        s = f"{int(st.st_mtime)}:{st.st_size}"
    except OSError:
        s = "missing"
    _STAMPS[sym] = s
    return s


def _defaults_stamp():
    from .model import DEFAULTS
    return hashlib.sha1(json.dumps(DEFAULTS, sort_keys=True, default=str).encode()).hexdigest()[:10]


def _hash(sym, params, wide):
    raw = json.dumps([sym, params, wide, _data_stamp(sym), _defaults_stamp()], sort_keys=True, default=str)
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def _slim_trade(t):
    return {"day": t["day"], "pnl": float(t["pnl"]), "r": float(t.get("pnl_r") or 0.0),
            "pts": float(sum(c["state"] * c["weight"] for c in t.get("checklist") or [])),
            "mult": float(t.get("grade_mult") or 1.0),
            "f": {k: _num(v) for k, v in (t.get("features") or {}).items()},
            "ck": [[c["label"], int(c["state"]), float(c["weight"])] for c in t.get("checklist") or []]}


def _bt(job):
    """Worker: one engine run. job = (sym, params, wide). Returns slim trades, sessions and (wide) candidates."""
    sym, params, wide = job
    from . import backtest
    if wide:
        r = backtest.run(sym, "5m", {**params, **WIDE})
        cands = [{"day": s["day"], "r": float(s["r"]), "taken": bool(s.get("taken")),
                  "f": {k: _num(v) for k, v in (s.get("f") or {}).items()}}
                 for s in r["shadows"] if s.get("r") is not None]
        return {"sym": sym, "days": [d["date"] for d in r["days"]], "cands": cands}
    r = backtest.run(sym, "5m", {**params, **FLAT}, light=True)
    return {"sym": sym, "days": [d["date"] for d in r["days"]], "trades": [_slim_trade(t) for t in r["trades"]]}


class Runner:
    """Runs engine backtests in a Pool (<= 4), cached per (symbol, params, data file, engine defaults) hash."""

    def __init__(self, procs=POOL_N):
        self.procs = procs
        self.cache = {}
        self.n_runs = 0

    def run_many(self, jobs):
        todo, seen = [], set()
        # hash once: a data file being appended to mid-cycle (live bars, the ES harvest) must not orphan cached results
        hs = [_hash(sym, params, wide) for sym, params, wide in jobs]
        for h, (sym, params, wide) in zip(hs, jobs):
            if h not in self.cache and h not in seen:
                seen.add(h)
                todo.append((h, (sym, params, wide)))
        if todo:
            if self.procs > 1 and len(todo) > 1:
                with Pool(min(self.procs, len(todo))) as pool:
                    outs = pool.map(_bt, [j for _, j in todo])
            else:
                outs = [_bt(j) for _, j in todo]
            for (h, _), o in zip(todo, outs):
                self.cache[h] = o
            self.n_runs += len(todo)
        return [self.cache[h] for h in hs]

    def get(self, sym, params, wide=False):
        return self.run_many([(sym, params, wide)])[0]


# ------------------------------------------------------------------------------------------------ folds
FOLD_MODE = "year"          # "year": one fold per calendar year once >= 2 years of history exist; "even": equal blocks
CONFIRM_FROM = "2025-01-01"  # year mode: folds starting on/after this date are out-of-sample (train 2021-24, test 2025-26)
MIN_YEAR_SESSIONS = 60       # a partial first/last year shorter than this joins its neighbour


def _year_folds(days):
    groups = {}
    for d in days:
        groups.setdefault(d[:4], []).append(d)
    ys = [groups[y] for y in sorted(groups)]
    if len(ys) > 1 and len(ys[0]) < MIN_YEAR_SESSIONS:
        ys[1] = ys[0] + ys[1]; ys = ys[1:]
    if len(ys) > 1 and len(ys[-1]) < MIN_YEAR_SESSIONS:
        ys[-2] = ys[-2] + ys[-1]; ys = ys[:-1]
    out = []
    for j, c in enumerate(ys):
        out.append({"name": f"F{j + 1}", "from": c[0], "to": c[-1], "sessions": len(c),
                    "role": "confirm" if c[0] >= CONFIRM_FROM else "decide",
                    "label": f"F{j + 1} {c[0][:7]}..{c[-1][:7]}"})
    if not any(f["role"] == "confirm" for f in out) or all(f["role"] == "confirm" for f in out):
        return None
    return out


def build_folds(days):
    """Contiguous week-block folds over the available NQ sessions (dates come from the data, never hard-coded)."""
    days = sorted(set(days))
    n = len(days)
    if FOLD_MODE == "year" and n >= 2 * 250:
        yf = _year_folds(days)
        if yf:
            return yf
    k = max(MIN_FOLDS, min(MAX_FOLDS, n // FOLD_SESSIONS)) if n >= MIN_FOLDS * 3 else 1
    chunks = [list(c) for c in np.array_split(np.array(days), k) if len(c)]
    n_conf = max(1, int(round(len(chunks) * CONFIRM_FRAC))) if len(chunks) > 1 else 0
    out = []
    for j, c in enumerate(chunks):
        out.append({"name": f"F{j + 1}", "from": str(c[0]), "to": str(c[-1]), "sessions": len(c),
                    "role": "confirm" if j >= len(chunks) - n_conf else "decide",
                    "label": f"F{j + 1} {str(c[0])[5:]}..{str(c[-1])[5:]}"})
    return out


def _fold_of(day, folds):
    for j, f in enumerate(folds):
        if f["from"] <= day <= f["to"]:
            return j
    return None


# ------------------------------------------------------------------------------------------------ feature scan
def _kind(vals):
    u = set(np.unique(vals).tolist()) if len(vals) else set()
    if u <= {0, 1}:
        return "binary"
    if u <= {-1, 0, 1}:
        return "signed"
    return "continuous"


def _ind(v, kind, med):
    """Present / absent indicator for a feature value: binary 1/0, signed -1/0/+1, continuous 1 above the median."""
    x = float(v or 0)
    if kind == "binary":
        return 1 if x > 0 else 0
    if kind == "signed":
        return 1 if x > 0 else (-1 if x < 0 else 0)
    return 1 if (med is not None and x > med) else 0


def _on_off(rows, key, kind, med):
    on, off = [], []
    for s in rows:
        v = s["f"].get(key)
        x = float(v or 0)
        if kind == "continuous":
            (on if x > med else off).append(s["r"])
        elif kind == "signed":
            if x > 0:
                on.append(s["r"])
            elif x < 0:
                off.append(s["r"])
        else:
            (on if x > 0 else off).append(s["r"])
    return on, off


def _lift(rows, key, kind, med):
    on, off = _on_off(rows, key, kind, med)
    if len(on) >= MIN_SIDE and len(off) >= MIN_SIDE:
        return {"lift": round(float(np.mean(on) - np.mean(off)), 3), "n_on": len(on), "n_off": len(off),
                "r_on": round(float(np.mean(on)), 3)}
    return {"lift": None, "n_on": len(on), "n_off": len(off), "r_on": round(float(np.mean(on)), 3) if on else None}


def _boot_lift(rows, key, kind, med, seed):
    on, off = _on_off(rows, key, kind, med)
    if len(on) < MIN_SIDE or len(off) < MIN_SIDE:
        return None
    rng = np.random.default_rng(seed)
    a, b = np.array(on), np.array(off)
    ia = rng.integers(0, len(a), (BOOT, len(a)))
    ib = rng.integers(0, len(b), (BOOT, len(b)))
    d = a[ia].mean(1) - b[ib].mean(1)
    return [round(float(np.percentile(d, 5)), 3), round(float(np.percentile(d, 95)), 3)]


def scan(nq_c, es_c, nq_t, es_t, folds):
    """Lift of every numeric feature per NQ fold (+ES), on candidates and on taken trades. Sign decided on decide folds."""
    names = _names()
    dec = [j for j, f in enumerate(folds) if f["role"] == "decide"]
    con = [j for j, f in enumerate(folds) if f["role"] == "confirm"]
    by_fold = lambda rows: [[s for s in rows if _fold_of(s["day"], folds) == j] for j in range(len(folds))]
    nq_cf, nq_tf = by_fold(nq_c), by_fold(nq_t)
    keys = sorted({k for s in nq_c + es_c for k, v in s["f"].items() if v is not None and k not in SKIP})
    out = {}
    for k in keys:
        vals = np.array([float(s["f"].get(k) or 0) for s in nq_c + es_c])
        kind = _kind(vals)
        dec_rows = [s for j in dec for s in nq_cf[j]]
        med = float(np.median([float(s["f"].get(k) or 0) for s in dec_rows])) if kind == "continuous" and dec_rows else None
        if kind == "binary" and vals.sum() < 6:
            continue
        per = [{"slice": folds[j]["label"], "role": folds[j]["role"], **_lift(nq_cf[j], k, kind, med)} for j in range(len(folds))]
        per_t = [{"slice": folds[j]["label"], "role": folds[j]["role"], **_lift(nq_tf[j], k, kind, med)} for j in range(len(folds))]
        es = {"slice": "ES", "role": "check", **_lift(es_c, k, kind, med)}
        es_tk = {"slice": "ES", "role": "check", **_lift(es_t, k, kind, med)}
        d_l = _lift(dec_rows, k, kind, med)
        c_l = _lift([s for j in con for s in nq_cf[j]], k, kind, med)
        pooled = _lift(nq_c, k, kind, med)
        pooled_t = _lift(nq_t, k, kind, med)
        sign = 0 if d_l["lift"] is None or d_l["lift"] == 0 else (1 if d_l["lift"] > 0 else -1)
        valid = [p["lift"] for p in per if p["lift"] is not None]
        agree = sum(1 for x in valid if sign and x * sign > 0.02)
        wf = bool(sign and c_l["lift"] is not None and c_l["lift"] * sign > 0)
        es_ok = None if es["lift"] is None or not sign else bool(es["lift"] * sign > 0)
        if len(valid) < 3 or not sign:
            verdict = "THIN"
        elif agree >= max(3, len(valid) // 2 + 1) and wf and abs(d_l["lift"]) >= 0.10:
            verdict = "STABLE"
        elif agree * 2 >= len(valid) and (wf or es_ok):
            verdict = "LEANING"
        else:
            verdict = "NOISE"
        out[k] = {"key": k, "name": names.get(k, k), "kind": kind, "median": med, "sign": sign, "verdict": verdict,
                  "agree": agree, "valid": len(valid), "wf_confirm": wf, "es_agree": es_ok,
                  "candidates": {"per": per + [es], "decide": d_l["lift"], "confirm": c_l["lift"], "pooled": pooled["lift"],
                                 "n_on": pooled["n_on"], "n_off": pooled["n_off"],
                                 "ci90": _boot_lift(nq_c, k, kind, med, SEED + zlib.crc32(k.encode()) % 10000)},
                  "taken": {"per": per_t + [es_tk], "pooled": pooled_t["lift"], "n_on": pooled_t["n_on"], "n_off": pooled_t["n_off"]},
                  "freq": round(pooled["n_on"] / max(1, len(nq_c)), 3)}
    return out


# ------------------------------------------------------------------------------------------------ post-processing hooks
def _grades():
    from .model import Engine
    return list(Engine.GRADES)


def apply_hooks(trades, hooks, grades):
    """Apply post-processed confluences to a trade list: grade weight add/remove rescales pnl by the new grade
    multiplier; drop_if removes trades (hard gate). Used for confluences the engine cannot express yet."""
    if not hooks:
        return trades
    out = []
    for t in trades:
        pts, drop = t["pts"], False
        for h in hooks:
            if h["op"] == "grade_add":
                pts += h["w"] * _ind(t["f"].get(h["feature"]), h["kind"], h.get("median"))
            elif h["op"] == "grade_remove":
                for lab, st, w in t["ck"]:
                    if lab.startswith(h["label"]):
                        pts -= st * w
            elif h["op"] == "drop_if":
                pres = _ind(t["f"].get(h["feature"]), h["kind"], h.get("median")) > 0
                if pres == h["present"]:
                    drop = True
        if drop:
            continue
        m = next(m for g, th, m in grades if pts >= th)
        out.append({**t, "pnl": t["pnl"] * (m / t["mult"] if t["mult"] else 1.0), "pts": pts, "mult": m})
    return out


# ------------------------------------------------------------------------------------------------ evaluation
def evaluate(nq, es, folds, es_sessions):
    per = []
    for j, f in enumerate(folds):
        tr = [t for t in nq if f["from"] <= t["day"] <= f["to"]]
        per.append({"pnl": round(sum(t["pnl"] for t in tr), 2), "n": len(tr), "tpw": round(len(tr) / max(f["sessions"] / 5, 1e-9), 2)})
    n_sess = sum(f["sessions"] for f in folds)
    by_day = {}
    for t in nq:
        by_day[t["day"]] = by_day.get(t["day"], 0.0) + t["pnl"]
    gp = sum(t["pnl"] for t in nq if t["pnl"] > 0)
    gl = -sum(t["pnl"] for t in nq if t["pnl"] < 0)
    eq = np.cumsum([t["pnl"] for t in nq]) if nq else np.array([0.0])
    dd = float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min()) if nq else 0.0
    return {"nq_total": round(sum(t["pnl"] for t in nq), 2), "nq_n": len(nq), "nq_tpw": round(len(nq) / max(n_sess / 5, 1e-9), 2),
            "nq_pf": round(gp / gl, 2) if gl else None, "nq_dd": round(dd, 2),
            "decide": round(sum(p["pnl"] for p, f in zip(per, folds) if f["role"] == "decide"), 2),
            "confirm": round(sum(p["pnl"] for p, f in zip(per, folds) if f["role"] == "confirm"), 2),
            "folds": per, "es_total": round(sum(t["pnl"] for t in es), 2), "es_n": len(es),
            "es_tpw": round(len(es) / max(es_sessions / 5, 1e-9), 2), "_by_day": by_day}


def _boot_delta(a, b, days, seed):
    d = np.array([b["_by_day"].get(x, 0.0) - a["_by_day"].get(x, 0.0) for x in days])
    if not len(d) or not d.any():
        return [0.0, 0.0]
    rng = np.random.default_rng(seed)
    s = d[rng.integers(0, len(d), (BOOT, len(d)))].sum(1)
    return [round(float(np.percentile(s, 5)), 0), round(float(np.percentile(s, 95)), 0)]


def judge(test, base, folds, days, seed=SEED):
    """Apply the adoption rule. Returns a compact JSON-able verdict."""
    d_nq = test["nq_total"] - base["nq_total"]
    d_dec = test["decide"] - base["decide"]
    d_con = test["confirm"] - base["confirm"]
    d_es = test["es_total"] - base["es_total"]
    better = sum(1 for a, b in zip(base["folds"], test["folds"]) if b["pnl"] > a["pnl"] + 0.5)
    worse = sum(1 for a, b in zip(base["folds"], test["folds"]) if b["pnl"] < a["pnl"] - 0.5)
    fails = []
    if not (TPW_MIN <= test["nq_tpw"] <= TPW_MAX):
        fails.append(f"NQ {test['nq_tpw']:.1f} trades/week (needs {TPW_MIN}-{TPW_MAX})")
    for f, a, b in zip(folds, base["folds"], test["folds"]):
        lo = min(TPW_MIN, a["tpw"])
        if b["tpw"] > TPW_MAX + 1e-9 or b["tpw"] < lo - 1e-9:
            fails.append(f"{f['name']} {b['tpw']:.1f} trades/week")
    freq_ok = not fails
    if d_con <= 0:
        fails.append(f"out-of-sample folds {d_con:+.0f}")
    if d_dec <= 0:
        fails.append(f"decide folds {d_dec:+.0f}")
    if test["nq_total"] <= 0:
        fails.append("NQ total not positive")
    if d_es < 0:
        fails.append(f"hurts ES {d_es:+.0f}")
    if worse > better:
        fails.append(f"worse in {worse} of {len(folds)} folds")
    if not fails:
        verdict = "pass"
    elif freq_ok and d_nq > 0 and (d_con > 0 or d_dec > 0):
        verdict = "partial"
    else:
        verdict = "fail"
    return {"verdict": verdict, "fails": fails, "d_nq": round(d_nq, 0), "d_decide": round(d_dec, 0), "d_confirm": round(d_con, 0),
            "d_es": round(d_es, 0), "nq_total": round(test["nq_total"], 0), "es_total": round(test["es_total"], 0),
            "nq_tpw": test["nq_tpw"], "fold_tpw": [p["tpw"] for p in test["folds"]], "fold_pnl": [round(p["pnl"], 0) for p in test["folds"]],
            "es_tpw": test["es_tpw"], "nq_n": test["nq_n"], "pf": test["nq_pf"], "dd": round(test["nq_dd"], 0),
            "better": better, "worse": worse, "ci90_d_nq": _boot_delta(base, test, days, seed)}


# ------------------------------------------------------------------------------------------------ test plan
def _live_state(defaults, base_trades):
    """Which grade items / score gates are live in the engine right now, and their current weights."""
    live = {}
    for fid, label, param in GRADE_ITEMS:
        if param != "hook":
            w = defaults.get(param, 0)
        else:
            ws = sorted({abs(w) for t in base_trades for lab, st, w in t["ck"] if lab.startswith(label) and w})
            w = ws[-1] if ws else 0
        if w:
            live[fid] = {"kind": "grade", "param": param, "label": label, "weight": w}
    gates = {}
    for feat, wk in W_KEYS.items():
        if defaults.get(wk):
            gates["gate:" + wk] = {"kind": "gate", "param": wk, "feature": feat, "weight": defaults[wk]}
    return live, gates


def _sizing_variant(feat, sw, info):
    """A grade-weight variant: engine param if one exists, otherwise a post-processing hook."""
    if feat in G_PENALTY:
        return {"params": {G_PENALTY[feat]: -sw}, "hooks": [], "hook": False}
    if feat in G_SIGNED:
        return {"params": {G_SIGNED[feat]: sw}, "hooks": [], "hook": False}
    return {"params": {}, "hooks": [{"op": "grade_add", "feature": feat, "kind": info["kind"], "median": info["median"], "w": sw}], "hook": True}


def plan_tests(sc, live, gates, defaults):
    tests = []
    grade_ids = {fid for fid, _, _ in GRADE_ITEMS}
    # (b) sign-stable features not live in the grade: add as a sizing weight, and try as a filter
    for k, info in sc.items():
        if info["verdict"] != "STABLE" or k in live:
            continue
        s = info["sign"]
        for w in (1, 2):
            v = _sizing_variant(k, s * w, info)
            tests.append({"item": k, "kind": "add_grade", "label": f"grade weight {s * w:+d}", "weight": s * w, **v})
        # filters (hard / soft gates)
        if k == "x_swept_london" and s < 0:
            tests.append({"item": k, "kind": "filter", "label": "hard gate: skip London H/L raids", "params": {"skip_london": True}, "hooks": [], "hook": False})
        else:
            tests.append({"item": k, "kind": "filter", "label": "hard gate: " + ("only take it when present" if s > 0 else "skip when present"),
                          "params": {}, "hook": True,
                          "hooks": [{"op": "drop_if", "feature": k, "kind": info["kind"], "median": info["median"], "present": s < 0}]})
        wk = W_KEYS.get(k)
        if wk and not defaults.get(wk):
            tests.append({"item": k, "kind": "filter", "label": f"score gate {wk}={s:+d}", "params": {wk: s}, "hooks": [], "hook": False})
    # (c) live grade items: remove, step down, step up
    for fid, d in live.items():
        w = d["weight"]
        if d["param"] != "hook":
            p = d["param"]
            tests.append({"item": fid, "kind": "remove", "label": f"remove ({p}=0)", "params": {p: 0}, "hooks": [], "hook": False, "weight": 0})
            if abs(w) >= 2:
                tests.append({"item": fid, "kind": "reweight", "label": f"{p}={w - (1 if w > 0 else -1)}", "params": {p: w - (1 if w > 0 else -1)},
                              "hooks": [], "hook": False, "weight": w - (1 if w > 0 else -1)})
            tests.append({"item": fid, "kind": "reweight", "label": f"{p}={w + (1 if w > 0 else -1)}", "params": {p: w + (1 if w > 0 else -1)},
                          "hooks": [], "hook": False, "weight": w + (1 if w > 0 else -1)})
        else:
            tests.append({"item": fid, "kind": "remove", "label": "remove from grade", "params": {}, "hook": True, "weight": 0,
                          "hooks": [{"op": "grade_remove", "label": d["label"]}]})
    # live score gates: remove
    for gid, d in gates.items():
        tests.append({"item": gid, "kind": "remove", "label": f"remove gate ({d['param']}=0)", "params": {d["param"]: 0}, "hooks": [], "hook": False, "weight": 0})
    for t in tests:
        t["id"] = f"{t['item']}|{t['label']}"
    _ = grade_ids
    return tests


# ------------------------------------------------------------------------------------------------ decisions
def _plain_lift(info):
    if not info:
        return ""
    c = info["candidates"]
    side = "better" if info["sign"] > 0 else "worse"
    return (f"candidates with it do {side} by {abs(c['decide'] or 0):.2f}R in the earlier folds "
            f"({info['agree']}/{info['valid']} folds agree, out-of-sample {'confirms' if info['wf_confirm'] else 'does not confirm'}"
            f"{', ES agrees' if info['es_agree'] else (', ES disagrees' if info['es_agree'] is False else '')})")


def _fmt_eval(j):
    return (f"NQ {j['d_nq']:+.0f} (OOS {j['d_confirm']:+.0f}, decide {j['d_decide']:+.0f}), ES {j['d_es']:+.0f}, "
            f"{j['nq_tpw']:.1f} trades/wk")


def decide(sc, live, gates, tests, results, defaults):
    """Turn scan + test verdicts into registry statuses with plain-English reasons."""
    names = _names()
    items = {}
    by_item = {}
    for t in tests:
        by_item.setdefault(t["item"], []).append(t)
    # every scanned feature + every live item + every live gate
    ids = sorted(set(sc) | set(live) | set(gates))
    for iid in ids:
        feat = gates[iid]["feature"] if iid in gates else iid
        info = sc.get(feat)
        tl = by_item.get(iid, [])
        for t in tl:
            t["result"] = results[t["id"]]
        it = {"id": iid, "feature": feat, "name": (names.get(feat, feat) + (" (score gate)" if iid in gates else "")),
              "scan": None if not info else {k: info[k] for k in ("verdict", "sign", "agree", "valid", "wf_confirm", "es_agree", "kind", "median", "freq")},
              "evidence": None if not info else {"candidates": info["candidates"], "taken": info["taken"]},
              "live": iid in live or iid in gates, "tests": [{k: t[k] for k in ("label", "kind", "params", "hooks", "hook", "result")} for t in tl],
              "recommended": None, "needs_engine_hook": False}
        if iid in gates:
            it["mechanism"] = f"score gate {gates[iid]['param']}"
            it["weight"] = gates[iid]["weight"]
        elif iid in live:
            it["mechanism"] = f"grade {live[iid]['param']}" if live[iid]["param"] != "hook" else "grade (hard-coded weight)"
            it["weight"] = live[iid]["weight"]
        else:
            it["mechanism"] = (f"grade {G_PENALTY.get(feat) or G_SIGNED.get(feat)}" if (feat in G_PENALTY or feat in G_SIGNED) else "grade (needs engine hook)")
            it["weight"] = 0
        if it["live"]:
            rem = [t for t in tl if t["kind"] == "remove"]
            rew = [t for t in tl if t["kind"] == "reweight"]
            rj = rem[0]["result"] if rem else None
            best_rw = max((t for t in rew if t["result"]["verdict"] == "pass"), key=lambda t: t["result"]["d_nq"], default=None)
            ev = _plain_lift(info)
            if rj and rj["verdict"] == "pass" and (best_rw is None or rj["d_nq"] >= best_rw["result"]["d_nq"]):
                it.update(status="RETIRED", decision="retire",
                          reason=f"Taking it out of the {'gate' if iid in gates else 'grade'} improved every test: {_fmt_eval(rj)}. {ev}".strip(),
                          recommended={"params": rem[0]["params"], "hooks": rem[0]["hooks"]}, needs_engine_hook=rem[0]["hook"])
            elif best_rw is not None:
                it.update(status="ACTIVE", decision="reweight",
                          reason=f"Keeps its place; {best_rw['label']} passed the rule: {_fmt_eval(best_rw['result'])}.",
                          recommended={"params": best_rw["params"], "hooks": []})
            elif rj and rj["d_nq"] <= -KEEP_MIN_USD and rj["d_confirm"] <= 0:
                it.update(status="ACTIVE", decision="keep",
                          reason=f"Earns its place: removing it costs NQ {rj['d_nq']:+.0f} (OOS {rj['d_confirm']:+.0f}, ES {rj['d_es']:+.0f}). {ev}".strip())
            elif rj and rj["d_nq"] < 0:
                it.update(status="PROBATION", decision="watch",
                          reason=f"Barely matters: removing it changes NQ only {rj['d_nq']:+.0f} (OOS {rj['d_confirm']:+.0f}, ES {rj['d_es']:+.0f}). "
                                 f"Kept for now, re-tested every run. {ev}".strip())
            elif rj:
                it.update(status="PROBATION", decision="watch",
                          reason=f"Removing it would help NQ but not on every rule ({_fmt_eval(rj)}; failed: {', '.join(rj['fails'][:2]) or 'no clear gain'}). {ev}".strip())
            else:
                it.update(status="ACTIVE", decision="keep", reason="Live in the engine; no removal test available.")
        else:
            v = info["verdict"] if info else "THIN"
            if v == "THIN":
                it.update(status="CANDIDATE", decision="collect", reason="Too few candidates on one side to measure it per fold yet - waiting for more futures history.")
            elif v == "NOISE":
                it.update(status="RETIRED", decision="retire",
                          reason=f"Its edge flips sign between folds ({info['agree']}/{info['valid']} agree"
                                 f"{', not confirmed out-of-sample' if not info['wf_confirm'] else ''}) - noise for this strategy. Re-scanned every run.")
            elif v == "LEANING":
                it.update(status="CANDIDATE", decision="watch", reason=f"Leaning but not consistent enough to test yet: {_plain_lift(info)}.")
            else:
                passing = [t for t in tl if t["result"]["verdict"] == "pass"]
                partial = [t for t in tl if t["result"]["verdict"] == "partial"]
                if passing:
                    # prefer sizing (no frequency risk), then the larger NQ gain, then the smaller weight
                    best = max(passing, key=lambda t: (t["kind"] == "add_grade", t["result"]["d_nq"], -abs(t.get("weight") or 0)))
                    it.update(status="ACTIVE", decision="adopt", weight=best.get("weight") or 0,
                              reason=f"Sign-stable and {best['label']} passed every rule: {_fmt_eval(best['result'])}. "
                                     f"{'Needs an engine hook before it can go live.' if best['hook'] else 'Recommended params ready for the lead.'}",
                              recommended={"params": best["params"], "hooks": best["hooks"], "label": best["label"]}, needs_engine_hook=best["hook"])
                elif partial:
                    best = max(partial, key=lambda t: t["result"]["d_nq"])
                    it.update(status="PROBATION", decision="watch",
                              reason=f"Sign-stable; {best['label']} helped NQ overall ({_fmt_eval(best['result'])}) but failed: {', '.join(best['result']['fails'][:3])}.")
                else:
                    b = max(tl, key=lambda t: t["result"]["d_nq"]) if tl else None
                    it.update(status="RETIRED", decision="retire",
                              reason=("Sign-stable on candidates, but no weight or filter improved the futures backtest"
                                      + (f" (best: {b['label']}, {_fmt_eval(b['result'])}; {', '.join(b['result']['fails'][:2])})." if b else ".")))
        items[iid] = it
    return items


# ------------------------------------------------------------------------------------------------ registry I/O
def load_registry():
    if os.path.exists(REG_PATH):
        try:
            with open(REG_PATH, encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            pass
    return {"version": 1, "items": {}, "runs": []}


def _save(reg):
    tmp = REG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(reg, fh, indent=1, default=lambda o: float(o) if isinstance(o, np.floating) else int(o) if isinstance(o, np.integer) else str(o))
    from .fsutil import replace as _fs_replace   # retried: Windows / OneDrive lock the target a moment
    _fs_replace(tmp, REG_PATH)


def _merge_history(old, new, today, run_id):
    """Keep dates added / retired, first seen and a short decision history across runs."""
    for iid, it in new.items():
        prev = (old or {}).get(iid) or {}
        it["first_seen"] = prev.get("first_seen", today)
        it["added"] = prev.get("added") if prev.get("status") == "ACTIVE" else None
        it["retired"] = prev.get("retired") if prev.get("status") == "RETIRED" else None
        if it["status"] == "ACTIVE" and not it["added"]:
            it["added"] = today
        if it["status"] == "RETIRED" and not it["retired"]:
            it["retired"] = today
        it["prev_status"] = prev.get("status")
        hist = list(prev.get("history") or [])
        hist.append({"run": run_id, "date": today, "status": it["status"], "decision": it["decision"]})
        it["history"] = hist[-20:]
    # items that vanished from the scan keep their last record, marked stale
    for iid, it in (old or {}).items():
        if iid not in new:
            new[iid] = {**it, "stale": True}
    return new


# ------------------------------------------------------------------------------------------------ the cycle
def run_cycle(procs=POOL_N, write=True):
    t0 = time.time()
    from .model import DEFAULTS
    defaults = json.loads(json.dumps(DEFAULTS, default=str))
    grades = _grades()
    R = Runner(procs)
    steps = 6
    _progress(1, steps, "baseline backtests + candidate trades (NQ, ES futures)")
    base_nq, base_es, wide_nq, wide_es = R.run_many([(PRIMARY, {}, False), (CHECK, {}, False), (PRIMARY, {}, True), (CHECK, {}, True)])
    folds = build_folds(base_nq["days"])
    days = sorted(base_nq["days"])
    es_sessions = len(base_es["days"])
    base = evaluate(base_nq["trades"], base_es["trades"], folds, es_sessions)

    _progress(2, steps, f"scanning features over {len(folds)} folds ({len(wide_nq['cands'])} NQ / {len(wide_es['cands'])} ES candidates)")
    sc = scan(wide_nq["cands"], wide_es["cands"], base_nq["trades"], base_es["trades"], folds)

    live, gates = _live_state(defaults, base_nq["trades"])
    tests = plan_tests(sc, live, gates, defaults)
    _progress(3, steps, f"{len(tests)} tests planned; running engine variants")
    psets = sorted({json.dumps(t["params"], sort_keys=True) for t in tests})
    jobs = [(sym, json.loads(p), False) for p in psets for sym in (PRIMARY, CHECK)]
    R.run_many(jobs)

    _progress(4, steps, "judging every test against the adoption rule")
    results = {}
    for k, t in enumerate(tests):
        nq = apply_hooks(R.get(PRIMARY, t["params"])["trades"], t["hooks"], grades)
        es = apply_hooks(R.get(CHECK, t["params"])["trades"], t["hooks"], grades)
        results[t["id"]] = judge(evaluate(nq, es, folds, es_sessions), base, folds, days, SEED + k)
    items = decide(sc, live, gates, tests, results, defaults)

    _progress(5, steps, "verifying the combined recommendation")
    rec_engine, rec_hooks, rec_ids = {}, [], []
    ranked = sorted([it for it in items.values() if it.get("recommended")],
                    key=lambda it: -max([t["result"]["d_nq"] for t in it["tests"]] or [0]))
    combined = None
    for it in ranked:
        trial_p = {**rec_engine, **it["recommended"]["params"]}
        trial_h = rec_hooks + list(it["recommended"].get("hooks") or [])
        nq = apply_hooks(R.get(PRIMARY, trial_p)["trades"], trial_h, grades)
        es = apply_hooks(R.get(CHECK, trial_p)["trades"], trial_h, grades)
        j = judge(evaluate(nq, es, folds, es_sessions), base, folds, days)
        if j["verdict"] == "pass" and (combined is None or j["d_nq"] > combined["d_nq"]):
            rec_engine, rec_hooks, combined = trial_p, trial_h, j
            rec_ids.append(it["id"])
    engine_only = None
    if rec_engine:
        nq = R.get(PRIMARY, rec_engine)["trades"]
        es = R.get(CHECK, rec_engine)["trades"]
        engine_only = judge(evaluate(nq, es, folds, es_sessions), base, folds, days)

    _progress(6, steps, "writing the registry")
    old = load_registry()
    today = time.strftime("%Y-%m-%d")
    run_id = time.strftime("%Y%m%d-%H%M%S")
    items = _merge_history(old.get("items"), items, today, run_id)
    cur = [it for it in items.values() if not it.get("stale")]
    added = [it["id"] for it in cur if it["status"] == "ACTIVE" and it["decision"] in ("adopt", "reweight")]
    retired_live = [it["id"] for it in cur if it["status"] == "RETIRED" and it["live"]]
    newly_retired = [it["id"] for it in cur if it["status"] == "RETIRED" and it.get("prev_status") != "RETIRED"]
    counts = {s: sum(1 for it in cur if it["status"] == s) for s in ("ACTIVE", "PROBATION", "CANDIDATE", "RETIRED")}
    bview = {k: v for k, v in base.items() if not k.startswith("_")}
    last = {"run": run_id, "started": time.strftime("%Y-%m-%d %H:%M", time.localtime(t0)), "secs": round(time.time() - t0, 1),
            "n_backtests": R.n_runs, "n_tests": len(tests), "counts": counts,
            "added": added, "retired_live": retired_live, "newly_retired": newly_retired,
            "probation": [it["id"] for it in cur if it["status"] == "PROBATION"],
            "recommended_params": rec_engine, "recommended_hooks": rec_hooks, "recommended_items": rec_ids,
            "combined": combined, "engine_only": engine_only,
            "tpw_before": {"NQ": base["nq_tpw"], "folds": [p["tpw"] for p in base["folds"]], "ES": base["es_tpw"]},
            "tpw_after": None if not combined else {"NQ": combined["nq_tpw"], "folds": combined["fold_tpw"], "ES": combined["es_tpw"]}}
    last["summary"] = _summary_text(last, items, base)
    reg = {"version": 1, "generated": time.strftime("%Y-%m-%d %H:%M"), "futures_only": True,
           "data": {PRIMARY: {"from": days[0], "to": days[-1], "sessions": len(days), "candidates": len(wide_nq["cands"]), "trades": base["nq_n"]},
                    CHECK: {"from": min(base_es["days"]), "to": max(base_es["days"]), "sessions": es_sessions,
                            "candidates": len(wide_es["cands"]), "trades": base["es_n"]}},
           "folds": folds,
           "rule": {"tpw": [TPW_MIN, TPW_MAX],
                    "text": f"Adopt only when NQ out-of-sample folds AND decide folds improve, NQ total stays positive, NQ {TPW_MIN}-{TPW_MAX} "
                            f"trades/week overall and in every fold (a fold already under {TPW_MIN} may not lose trades), no more folds worse than "
                            f"better, and ES futures P&L is not hurt. Partly passing -> PROBATION; failing -> RETIRED."},
           "baseline": bview, "defaults_used": {k: defaults[k] for k in sorted(defaults) if k.startswith(("g_", "w_")) or k in ("min_score", "grade_skip", "skip_london")},
           "items": items, "last_run": last,
           "runs": ((old.get("runs") or []) + [{k: last[k] for k in ("run", "started", "secs", "counts", "added", "retired_live", "newly_retired", "recommended_params")}])[-30:]}
    if write:
        _save(reg)
        _append_log(reg)
    print(last["summary"], flush=True)
    print("DONE", flush=True)
    return reg


def _summary_text(last, items, base):
    nm = lambda i: items[i]["name"] if i in items else i
    parts = [f"{last['counts']['ACTIVE']} active, {last['counts']['PROBATION']} probation, {last['counts']['CANDIDATE']} candidate, "
             f"{last['counts']['RETIRED']} retired ({last['n_tests']} tests, {last['n_backtests']} backtests, {last['secs']}s)."]
    if last["recommended_items"]:
        c = last["combined"]
        parts.append(f"Recommended: {', '.join(nm(i) for i in last['recommended_items'])} -> NQ {base['nq_total']:+.0f} to {c['nq_total']:+.0f} "
                     f"(OOS {c['d_confirm']:+.0f}), ES {c['d_es']:+.0f}, {c['nq_tpw']:.1f} trades/week.")
    else:
        parts.append("No change passed the adoption rule; the current grade stays as it is.")
    if last["retired_live"]:
        parts.append(f"Live confluences recommended for retirement: {', '.join(nm(i) for i in last['retired_live'])}.")
    return " ".join(parts)


def _append_log(reg):
    last, b = reg["last_run"], reg["baseline"]
    items = reg["items"]
    L = [f"\n## Confluence learning cycle {last['started']} (run {last['run']})\n",
         f"Data: NQ futures {reg['data']['NQ']['from']}..{reg['data']['NQ']['to']} ({reg['data']['NQ']['sessions']} sessions, "
         f"{reg['data']['NQ']['candidates']} candidates, {b['nq_n']} trades) · ES futures check ({reg['data']['ES']['sessions']} sessions, {b['es_n']} trades). No CFD data.\n",
         "Folds: " + ", ".join(f"{f['label']} ({f['role']}, {f['sessions']}s)" for f in reg["folds"]) + "\n",
         f"Baseline: NQ ${b['nq_total']:+.0f} ({b['nq_tpw']:.1f}/wk; folds " + ", ".join(f"${p['pnl']:+.0f} {p['tpw']:.1f}/wk" for p in b["folds"])
         + f"), ES ${b['es_total']:+.0f}.\n", f"\n{last['summary']}\n"]
    if last["recommended_params"] or last["recommended_hooks"]:
        L.append(f"\nRecommended params (lead applies): `{json.dumps(last['recommended_params'])}`" +
                 (f"; needs engine hook: `{json.dumps(last['recommended_hooks'])}`" if last["recommended_hooks"] else "") + "\n")
    for st in ("ACTIVE", "PROBATION", "RETIRED"):
        rows = [it for it in items.values() if it["status"] == st and not it.get("stale") and (st != "RETIRED" or it["live"] or (it.get("scan") or {}).get("verdict") == "STABLE")]
        if rows:
            L.append(f"\n**{st}**\n")
            for it in sorted(rows, key=lambda x: x["id"]):
                L.append(f"- {it['name']} [{it['mechanism']}]: {it['reason']}\n")
    n_noise = sum(1 for it in items.values() if it["status"] == "RETIRED" and not it["live"] and (it.get("scan") or {}).get("verdict") == "NOISE")
    L.append(f"\n({n_noise} more features retired as sign-flipping noise; {last['counts']['CANDIDATE']} candidates waiting for more data.)\n")
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    new = not os.path.exists(LOG_PATH)
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        if new:
            fh.write("# Confluence learning log\n\nOne entry per learning cycle (engine/confluence_search.py). Futures only: NQ week-block folds "
                     "(walk-forward decide -> confirm) plus ES as a robustness check.\n")
        fh.write("".join(L))


def report(reg=None):
    reg = reg or load_registry()
    if not reg.get("items"):
        print("No registry yet. Run: python -m engine.confluence_search --run")
        return
    last = reg.get("last_run") or {}
    print(f"Confluence registry · generated {reg.get('generated')} · NQ {reg['data']['NQ']['from']}..{reg['data']['NQ']['to']} "
          f"({reg['data']['NQ']['sessions']} sessions) · ES check")
    print("Folds:", ", ".join(f"{f['label']}[{f['role'][0]}]" for f in reg["folds"]))
    b = reg["baseline"]
    print(f"Baseline NQ ${b['nq_total']:+.0f} {b['nq_tpw']:.1f}/wk | folds " + " ".join(f"{p['pnl']:+.0f}({p['tpw']:.1f})" for p in b["folds"])
          + f" | ES ${b['es_total']:+.0f}")
    print(last.get("summary", ""))
    for st in ("ACTIVE", "PROBATION", "CANDIDATE", "RETIRED"):
        rows = sorted([it for it in reg["items"].values() if it["status"] == st and not it.get("stale")], key=lambda x: x["id"])
        print(f"\n== {st} ({len(rows)})")
        for it in rows:
            if st in ("CANDIDATE", "RETIRED") and not it["live"] and (it.get("scan") or {}).get("verdict") in ("NOISE", "THIN", "LEANING"):
                continue
            print(f"  {it['name'][:44]:44s} [{it['mechanism']}] {it['reason'][:220]}")
        hidden = [it for it in rows if st in ("CANDIDATE", "RETIRED") and not it["live"] and (it.get("scan") or {}).get("verdict") in ("NOISE", "THIN", "LEANING")]
        if hidden:
            print(f"  (+{len(hidden)} {'noise / thin / leaning' if st == 'RETIRED' else 'thin / leaning'} features: "
                  + ", ".join(it["id"] for it in hidden[:40]) + ("..." if len(hidden) > 40 else "") + ")")
    if last.get("recommended_params") or last.get("recommended_hooks"):
        print("\nRecommended params:", json.dumps(last["recommended_params"]), "| hooks:", json.dumps(last.get("recommended_hooks")))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Confluence learning loop (futures only)")
    ap.add_argument("--run", action="store_true", help="run a full learning cycle and write the registry + log")
    ap.add_argument("--report", action="store_true", help="print the registry summary")
    ap.add_argument("--procs", type=int, default=POOL_N)
    a = ap.parse_args()
    if a.run:
        report(run_cycle(procs=max(1, min(POOL_N, a.procs))))
    elif a.report:
        report()
    else:
        ap.print_help()
        sys.exit(1)
