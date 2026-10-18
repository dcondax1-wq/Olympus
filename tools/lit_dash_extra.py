"""Extra data for the LIT dashboard panels (Day clock, Setup tracker, Levels board, Eval cockpit, Week planner).

Both dashboards render these panels with tools/web_public/litkit.js; this module adds what data.json / the PC API do not
carry yet. Pure reads, no network, safe to call on every cloud-monitor run:

    from tools import lit_dash_extra
    data["lit_extra"] = lit_dash_extra.extra(state, live_model)      # tools/build_web_dashboard.py

Returns (every key optional for the page; a missing file just leaves its part out):
    plan     MFFU Builder 50K rules: start, target, mll (trailing EOD), dll (soft daily), lock_at (the floor stops trailing)
    sizing   LIT size rule + switches: risk_usd, ref_stop, max_micros, mode, fast_ref_stop, safe_cap, wk_stop, tick, point_value
    rules    LIT timing / trade rules: window (ET minutes), flat_mod, max_per_day, min/max stop, min/max RR, be_r, depth, disp
    boxes    the session boxes LIT draws levels from (ET minutes; engine/lit.py SESSIONS) with plain names
    stats    the live LIT run (research/runs/lit_live.json) per span (2026, H1, H2): trades, win %, avg win / loss $, median
             stop, median risk $, avg winner R; plus `days`: every 2026 session as [date, pnl, intraday low, trades]
             (the Eval cockpit resamples them from the current balance: forward pass / fail odds)
    levels   the live loop's full untaken LIT level list when the state carries it (state.active_pools / state.levels)
    lit      the live loop's day context when the state carries it (open18, vix, vix_move, signals_today) + session boxes
"""
from __future__ import annotations

import json
import os
import statistics as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN = os.path.join(ROOT, "research", "runs", "lit_live.json")
H1_END = "2026-06-30"

BOXES = [  # key in engine/lit.py SESSIONS, label as lit_live.py names it in state.session, ET minutes, class
    ("asia20", "Asia 20-00", 1200, 1440, "asia"),
    ("lon23", "Frankfurt 02-03", 120, 180, "london"),
    ("lon34", "London 03-04", 180, 240, "london"),
    ("pre", "Premarket", 240, 570, "pre"),
    ("ny89", "NY 08-09", 480, 540, "ny"),
    ("rth", "Cash session", 570, 960, "rth"),
]


def _load(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def _plan():
    try:
        from engine.analytics import PLANS
        p = PLANS["builder_50k"]
        return {"name": p["name"], "start": p["start"], "target": p["target"], "mll": p["mll"], "dll": p.get("dll"),
                "lock_at": p["start"] + (p.get("lock_above") or 0), "consistency": p.get("consistency")}
    except Exception:                      # the dashboard must never break the build
        return {"name": "MFFU Builder 50K", "start": 50000, "target": 3000, "mll": 2000, "dll": 1000, "lock_at": 50100}


def _span_stats(rows, cols):
    i = {c: k for k, c in enumerate(cols)}
    if not rows:
        return None
    pnl = [r[i["pnl"]] for r in rows]
    wins = [r for r in rows if r[i["pnl"]] > 0]
    losses = [r for r in rows if r[i["pnl"]] < 0]
    return {"n": len(rows), "win": round(100 * len(wins) / len(rows), 1),
            "net": round(sum(pnl)), "avg_win": round(st.mean([r[i["pnl"]] for r in wins])) if wins else None,
            "avg_loss": round(st.mean([r[i["pnl"]] for r in losses])) if losses else None,
            "avg_win_r": round(st.mean([r[i["r"]] for r in wins]), 2) if wins else None,
            "stops": sum(1 for r in rows if r[i["exit"]] == "STOP"),
            "med_stop": round(st.median([r[i["risk_pts"]] for r in rows]), 2),
            "med_risk": round(st.median([r[i["risk_usd"]] for r in rows])),
            "med_qty": int(st.median([r[i["qty"]] for r in rows]))}


def _stats(path=RUN):
    run = _load(path)
    if not run:
        return None
    cols, T = run.get("trade_cols") or [], run.get("trades") or []
    T26 = [t for t in T if str(t[0]).startswith("2026")]
    out = {"run": run.get("id"), "built": run.get("built"),
           "spans": {"2026": _span_stats(T26, cols),
                     "H1": _span_stats([t for t in T26 if t[0] <= H1_END], cols),
                     "H2": _span_stats([t for t in T26 if t[0] > H1_END], cols)}}
    dcols = run.get("day_cols") or ["date", "pnl", "low", "trades"]
    j = {c: k for k, c in enumerate(dcols)}
    out["days"] = [[d[j["date"]], round(float(d[j["pnl"]]), 2), round(float(d[j.get("low", j["pnl"])]), 2), int(d[j.get("trades", 0)] or 0)]
                   for d in run.get("days") or [] if str(d[j["date"]]).startswith("2026")]
    out["h1_end"] = H1_END
    return out


def extra(state: dict | None, lm: dict | None, run_path: str = RUN) -> dict:
    state, lm = state or {}, lm or {}
    P = lm.get("lit") or {}
    pr = lm.get("params") or {}
    ls = lm.get("lit_sizing") or {}
    out = {"version": 1, "plan": _plan()}
    out["sizing"] = {"risk_usd": pr.get("risk_usd", 800), "ref_stop": pr.get("risk_ref_stop", 20.0), "max_micros": pr.get("max_micros", 40),
                     "mode": ls.get("mode", "normal"), "fast_ref_stop": ls.get("fast_ref_stop", 40.0), "safe_cap": ls.get("safe_cap", 0.6),
                     "wk_stop": P.get("wk_stop"), "tick": 0.25, "point_value": 2.0, "modes": ls.get("modes")}
    out["rules"] = {"window": P.get("window", [[120, 930]]), "flat_mod": P.get("flat_mod", 955), "max_per_day": P.get("max_per_day", 1),
                    "min_stop": P.get("min_stop", 8.0), "max_stop": P.get("max_stop", 80.0), "min_rr": P.get("min_rr", 1.5),
                    "max_rr": P.get("max_rr", 8.0), "be_r": P.get("be_r", 1.0), "depth": P.get("depth", 0.5), "disp": P.get("disp", 0.8),
                    "idm": P.get("idm_a"), "limit_min": 30, "cisd1m_bars": P.get("cisd1m", 20), "monday": bool(P.get("monday")),
                    "vix_k": P.get("vix_k", 1.0)}
    out["boxes"] = [{"key": k, "label": lab, "a": a, "b": b, "kind": kind} for k, lab, a, b, kind in BOXES]
    s = _stats(run_path)
    if s:
        out["stats"] = s
    lv = state.get("levels") or state.get("active_pools")
    if lv:
        out["levels"] = lv
    if state.get("lit") or state.get("session"):
        out["lit"] = {**(state.get("lit") or {}), "session": state.get("session") or {}}
    return out


if __name__ == "__main__":
    import argparse
    import sys
    sys.path.insert(0, ROOT)
    ap = argparse.ArgumentParser(description="print the LIT dashboard extras for a cloud state file")
    ap.add_argument("--state", default="dash/state.json")
    a = ap.parse_args()
    x = extra(_load(a.state, {}), _load(os.path.join(ROOT, "live_model.json"), {}))
    days = (x.get("stats") or {}).pop("days", [])
    print(json.dumps(x, indent=1, default=str)[:4000])
    print(f"... {len(days)} 2026 sessions")
