"""LIT live fills study (owner, 2026-10-18: "study how live fills on a broker / prop firm would work; we need this 200% accurate").

Runs LIT live (live_model.json "lit", run lit_live) under the realistic fill model of engine/lit_fills.py (engine/lit.py option
"fills", default off) and scores it like every LIT run: 2026, H1 (Jan-Jun) / H2 (Jul-Oct 16), 2021-25 as a reference line,
the LIT size rule (run lit_live) AND the eval sizing the bots trade today (lit_sizing.mode "eval": $800 up to a 25-pt stop,
then 800x25/stop, room cap 60%; scored like tools/lit_tightstop.py, the MFFU $1,000 soft daily loss included).

Scenarios are cumulative steps from the plain backtest to the live bot as coded today, then the fixes:
  base        the plain backtest (fills None) == run lit_live
  n0          the realistic code with every knob set to the backtest's assumptions (code check: should be ~base)
  s1_comm     + MFFU commission $1.90 per micro round trip (was $1.40)
  s2_target   + target limit on the tick toward the entry, filled only when price trades 1 tick through it
  s3_stops    + stop / breakeven slippage max(1-2 ticks by hour, 2.5% of the 1m bar range); bars opening through the stop fill there
  s4_spread   + market orders pay half the bid/ask spread of the hour (1 tick RTH and 08:00, 1.5 London, 2 Asia)
  live_today  + the PC bot's real timing: the entry is seen only when the 1m bar after the CISD has closed, then the next poll
                (~31.5 s on average: a 60 s wait not aligned to the minute) + 3 s compute + routing; breakeven and model exits
                reach the broker one poll late; the clock flatten at the first poll after 15:55   == THE REALISTIC MODEL
  live_fixed  live_today with the two code fixes: decide on the CISD bar's close and poll ~2 s after each minute
  stress      live_today with 2x the stop slippage (+1 base tick, 5% of the range), +1 tick spread, target 2 ticks through
  inside1     live_today with the target limit 1 tick inside the level
  fixed_in1   live_fixed with the target limit 1 tick inside the level
  lat_nobe    live_today but the breakeven reaches the broker at once (isolates the breakeven lag)
  measured    (only when logs/fill_audit_report.json exists) the fills tools/fill_audit.py measured: `run measured`

  python tools/lit_fills.py check      # base == run lit_live; n0 close to base
  python tools/lit_fills.py run        # every scenario -> research/lit/fills_results.json (1 process, ~15 min)
  python tools/lit_fills.py save       # store runs lit_fill_* (rl.save, family other, tags lit, lit_fills)
  python tools/lit_fills.py expect     # per-trade expected fills of the realistic model -> research/lit/fills_expected.json
                                       # (tools/fill_audit.py compares the NinjaTrader fills with it)
"""
from __future__ import annotations

import collections
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from tools import lit_final as F  # noqa: E402
from tools import lit_tightstop as TS  # noqa: E402
from tools import runlib as rl  # noqa: E402

OUT = os.path.join(ROOT, "research", "lit", "fills_results.json")
OUT_EXP = os.path.join(ROOT, "research", "lit", "fills_expected.json")
LIVE = {**lit.DEFAULTS, **json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]}
EVAL_RULE, EVAL_ROOM = ("lit", 800, 25.0), 0.6

N0 = {"detect": "bar_close", "poll_s": 0.0, "compute_s": 0.0, "route_s": 0.0, "feed_s": 0.0, "spread_ticks": 2.0,
      "stop_base_ticks": 1.0, "stop_k": 0.0, "tgt_thr": 0, "be_lag": False, "comm_rt": 1.40, "flat_by_clock": False}
S1 = {**N0, "comm_rt": 1.90}
S2 = {**S1, "tgt_thr": 1}
S3 = {**S2, "stop_base_ticks": None, "stop_k": 0.025}
S4 = {**S3, "spread_ticks": None}
LIVE_TODAY = {}                                            # = engine/lit_fills.py FILL_DEFAULTS
LIVE_FIXED = {"detect": "bar_close", "poll_s": 4.0}
STRESS = {"stop_base_ticks": [3.0, 2.5, 2.0, 2.0], "stop_k": 0.05, "spread_ticks": [3.0, 2.5, 2.0, 2.0], "tgt_thr": 2}
SCEN = {
    "base": None, "n0": N0, "s1_comm": S1, "s2_target": S2, "s3_stops": S3, "s4_spread": S4,
    "live_today": LIVE_TODAY, "lat_nobe": {"be_lag": False}, "live_fixed": LIVE_FIXED, "stress": STRESS,
    "inside1": {"tgt_inside": 1}, "fixed_in1": {**LIVE_FIXED, "tgt_inside": 1},
}
TITLES = {
    "n0": "realistic-fill code with the backtest's own assumptions (code check)",
    "s1_comm": "+ MFFU commission $1.90 per micro round trip",
    "s2_target": "+ target limit must trade 1 tick through (tick-rounded toward the entry)",
    "s3_stops": "+ stop slippage by hour and 1m bar range, gap-through stops",
    "s4_spread": "+ half the bid/ask spread of the hour on market orders",
    "live_today": "REALISTIC: + the PC bot's timing as coded today (entry seen after the next 1m bar closes, 60 s poll)",
    "lat_nobe": "REALISTIC as today but breakeven reaches the broker at once (isolates the breakeven lag)",
    "live_fixed": "REALISTIC with the bot fixed (decide on the CISD bar close, poll 2 s after each minute)",
    "stress": "REALISTIC stress: 2x stop slippage, +1 tick spread, target 2 ticks through",
    "inside1": "REALISTIC with the target limit 1 tick inside the level",
    "fixed_in1": "REALISTIC, bot fixed, target limit 1 tick inside the level",
}
# measured: the suggested fills of tools/fill_audit.py (logs/fill_audit_report.json, after a week on Sim101 / the MFFU account)
_AUDIT = os.path.join(ROOT, "logs", "fill_audit_report.json")
if os.path.exists(_AUDIT):
    try:
        _sug = json.load(open(_AUDIT, encoding="utf-8")).get("suggested_fills") or {}
        if _sug:
            SCEN["measured"] = {k: v for k, v in _sug.items() if not k.startswith("_")}
            TITLES["measured"] = "MEASURED: the fills tools/fill_audit.py measured on NinjaTrader"
    except Exception:
        pass
_RUNS = {}


def P_of(name):
    cfg = SCEN[name]
    return {**LIVE, "fills": None if cfg is None else dict(cfg)}


def run(name):
    if name not in _RUNS:
        T = F.run(P_of(name))
        for t in T:
            t.setdefault("mfe", 0.0); t["mfe"] = t["mfe"] or 0.0; t["mae"] = t.get("mae") or 0.0
        _RUNS[name] = T
    return _RUNS[name]


def traded(T):
    return [t for t in T if not t.get("skip")]


# ------------------------------------------------------------------------------------------------ eval sizing (exact, like lit_tightstop)
def unit_of(T):
    """Unit (1-micro) trades in lit_tightstop's format from realistic-fill trades (points per micro and worst point kept)."""
    U = []
    for t in traded(T):
        if "pts" in t:
            pts, w1 = t["pts"], t["w1"]
        else:
            raise ValueError("unit_of needs realistic-fill trades")
        U.append({**t, "legs": [(1.0, pts)], "w1": w1, "exit_k": t.get("exit_model_kind", t["exit"])})
    n_st, m_st = LIVE["wk_stop"] or (10 ** 9, 1.0)
    allT = sorted(T, key=lambda t: t["entry_t"])
    for u in U:
        wk = lit.iso_week(u["day"])
        n = sum(1 for x in allT if x["entry_t"] != u["entry_t"] and x.get("exit_model_kind", x["exit"]) == "STOP"
                and lit.iso_week(x["day"]) == wk and x["exit_t"] <= u["entry_t"])
        u["wk_m"] = float(m_st) if n >= n_st else 1.0
    return U


def eval_score(name):
    cfg = SCEN[name]
    if cfg is None:
        U = TS.unit()
        comm = lit.COMM
    else:
        T = run(name)
        U = unit_of(T)
        comm = lit_fills_params(cfg)["comm_rt"]
    old = TS.COMM
    TS.COMM = comm
    try:
        o = TS.score(U, EVAL_RULE, room_k=EVAL_ROOM, spans=("H1", "H2", "2026", "2021-25"))
        path = TS.evals(U, EVAL_RULE, "2026", EVAL_ROOM)[1] + TS.evals(U, EVAL_RULE, "2021-25", EVAL_ROOM)[1]
    finally:
        TS.COMM = old
    return o, path


def lit_fills_params(cfg):
    from engine import lit_fills
    return lit_fills.params({"fills": cfg})


# ------------------------------------------------------------------------------------------------ diagnostics
def diag(T, spans=("2026", "H1", "H2")):
    out = {}
    for s in spans:
        a, z = F.SPAN[s]
        X = [t for t in T if a <= t["day"] <= z]
        R = [t for t in X if not t.get("skip")]
        if not X or "pts" not in (R[0] if R else {}):
            continue
        tg_m = [t for t in R if t["exit_model_kind"] == "TARGET"]
        d = {"model_trades": len(X), "skipped": len(X) - len(R),
             "skipped_model_pnl": round(sum(t["pnl_model"] for t in X if t.get("skip"))),
             "lat_s_med": float(np.median([t["lat_s"] for t in R])) if R else None,
             "entry_slip_pts_mean": round(float(np.mean([t["slip_entry_pts"] for t in R])), 3) if R else None,
             "entry_slip_pts_p90": round(float(np.percentile([t["slip_entry_pts"] for t in R], 90)), 3) if R else None,
             "entry_slip_pts_worst": round(float(max(t["slip_entry_pts"] for t in R)), 2) if R else None,
             "exits_live": dict(collections.Counter(t["exit"] for t in R)),
             "exits_model": dict(collections.Counter(t["exit_model_kind"] for t in R)),
             "model_targets": len(tg_m), "model_targets_missed_by_limit": sum(1 for t in tg_m if t["exit"] != "TARGET"),
             "pnl_diff_vs_model": round(sum(t["pnl"] - t["pnl_model"] for t in R)),
             "outcome_flips": sum(1 for t in R if (t["pnl"] > 0) != (t["pnl_model"] > 0))}
        st = [t for t in R if t["exit"] in ("STOP", "BE")]
        if st:
            sl = [(t["stop_px"] - t["exit_px"]) * t["dir"] if t["exit"] == "STOP" else (t["entry_model"] - t["exit_px"]) * t["dir"]
                  for t in st]
            d["stop_slip_pts_mean"] = round(float(np.mean(sl)), 3)
            d["stop_slip_pts_p90"] = round(float(np.percentile(sl, 90)), 3)
            d["stop_slip_pts_worst"] = round(float(max(sl)), 2)
        out[s] = d
    return out


KEYS = ("n", "tpw", "wk2", "win", "pf", "net", "per_month", "dd", "p10", "f10", "p20", "f20", "pass_rate", "pass_med")


def summarize(name):
    T = run(name)
    o = F.score(traded(T))
    e, _ = eval_score(name)
    return {"normal": {s: {k: o[s].get(k) for k in KEYS} for s in o},
            "eval": {s: {k: e[s].get(k) for k in KEYS + ("worst_day",)} for s in e},
            "diag": diag(T)}


def fmt(nm, r):
    def f(s, x):
        return (f"{s}: n={x['n']} {x['tpw']}/wk win {x['win']} PF {x['pf']} net {x['net']:+,} (${x['per_month']:,}/mo) DD {x['dd']:,} "
                f"2w {x['p10']}/{x['f10']} 1m {x['p20']}/{x['f20']} pr {x['pass_rate']}")
    lines = [f"== {nm}"]
    for mode in ("normal", "eval"):
        lines.append(f"  [{mode}] " + " | ".join(f(s, r[mode][s]) for s in ("2026", "H1", "H2") if r[mode].get(s, {}).get("n")))
        x = r[mode].get("2021-25", {})
        if x.get("n"):
            lines.append(f"  [{mode}] 2021-25 ref: n={x['n']} PF {x['pf']} net {x['net']:+,} DD {x['dd']:,}")
    if r.get("diag", {}).get("2026"):
        lines.append("  diag 2026: " + json.dumps(r["diag"]["2026"]))
    return "\n".join(lines)


def check():
    T = run("base")
    T26 = [t for t in T if t["day"] >= "2026"]
    net = sum(t["pnl"] for t in T26)
    ok = len(T26) == 120 and round(net) == 41734
    print(f"base == lit_live: {ok} ({len(T26)} trades 2026, net {net:+,.0f})", flush=True)
    N = traded(run("n0"))
    N26 = [t for t in N if t["day"] >= "2026"]
    print(f"n0 (backtest assumptions in the realistic code): {len(N26)} trades 2026, net {sum(t['pnl'] for t in N26):+,.0f}", flush=True)
    a = {(t["day"]): t for t in T26}
    diffs = [(t["day"], t["exit"], a[t["day"]]["exit"], round(t["pnl"] - a[t["day"]]["pnl"], 2)) for t in N26
             if t["day"] in a and abs(t["pnl"] - a[t["day"]]["pnl"]) > 0.05]
    print(f"n0 trades that differ from base: {len(diffs)}", diffs[:12], flush=True)
    return ok


def run_all(names=None):
    res = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    for nm in names or SCEN:
        r = summarize(nm)
        res[nm] = {"title": TITLES.get(nm, "plain backtest (run lit_live)"), "fills": SCEN[nm], **r}
        print(fmt(nm, r), flush=True)
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=1, default=str)
    return res


SAVE = [  # id, scenario, sizing, status, why
    ("lit_fill_n0", "n0", "normal", "info", "Code check: the realistic-fill code with the backtest's own assumptions."),
    ("lit_fill_s1_comm", "s1_comm", "normal", "info", "Step 1: MFFU's $1.90 per micro round trip."),
    ("lit_fill_s2_target", "s2_target", "normal", "info", "Step 2: target limits need a 1-tick trade-through."),
    ("lit_fill_s3_stops", "s3_stops", "normal", "info", "Step 3: stop slippage by hour and bar range."),
    ("lit_fill_s4_spread", "s4_spread", "normal", "info", "Step 4: half the bid/ask spread on market orders."),
    ("lit_fill_live_today", "live_today", "normal", "info", "THE REALISTIC MODEL of the bot as coded today (LIT size rule)."),
    ("lit_fill_live_today_eval", "live_today", "eval", "info", "THE REALISTIC MODEL of the bot as coded today, eval sizing (what the bots trade)."),
    ("lit_fill_live_fixed", "live_fixed", "normal", "adopt-candidate", "Realistic model with the two timing fixes (LIT size rule)."),
    ("lit_fill_live_fixed_eval", "live_fixed", "eval", "adopt-candidate", "Realistic model with the two timing fixes, eval sizing."),
    ("lit_fill_stress", "stress", "normal", "info", "Realistic model, stress costs (LIT size rule)."),
    ("lit_fill_stress_eval", "stress", "eval", "info", "Realistic model, stress costs, eval sizing."),
    ("lit_fill_inside1", "inside1", "normal", "info", "Realistic model, target limit 1 tick inside."),
    ("lit_fill_fixed_in1", "fixed_in1", "normal", "info", "Realistic model, bot fixed, target limit 1 tick inside."),
]


def save():
    res = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    for rid, nm, sizing, status, why in SAVE:
        if sizing == "normal":
            T = traded(run(nm))
            o = res.get(nm, {}).get("normal") or summarize(nm)["normal"]
        else:
            o_e, T = eval_score(nm)
            o = {s: {k: o_e[s].get(k) for k in KEYS} for s in o_e}
        T = [{k: v for k, v in t.items() if k not in ("legs",)} for t in T]
        S = rl.score(T, F.SESS)

        def h(s):
            x = o.get(s) or {}
            if not x.get("n"):
                return "n=0"
            return (f"n={x['n']} {x['tpw']}/wk win {x['win']}% PF {x['pf']} net {x['net']:+,} (${x['per_month']:,}/mo) DD {x['dd']:,} "
                    f"eval 2wk {x['p10']}/{x['f10']} 1mo {x['p20']}/{x['f20']} pass rate {x['pass_rate']}%")
        rl.save(rid, "LIT live fills: " + TITLES[nm] + (" - eval sizing" if sizing == "eval" else ""), "other",
                "Owner order 2026-10-18: how would LIT's orders really fill on the MFFU account (NinjaTrader -> Tradovate -> CME)?",
                params={**P_of(nm), "sizing": sizing, **({"eval_rule": list(EVAL_RULE), "room_k": EVAL_ROOM} if sizing == "eval" else {})},
                trades=T, scored=S, status=status,
                verdict=f"{why} 2026 H1 (pick) {h('H1')}; 2026 H2 (check) {h('H2')}; 2026 {h('2026')}; 2021-25 reference only {h('2021-25')}",
                notes="tools/lit_fills.py; engine/lit_fills.py (engine/lit.py option fills, default off). Assumptions to be replaced by "
                      "measured fills: tools/fill_audit.py.", writeup="lit-live-fills", tags=["lit", "lit_fills"])
        print("saved", rid, h("2026"), flush=True)


def expect(name="live_today"):
    """Per-trade expected prices of the realistic model (and the plain backtest's) for tools/fill_audit.py."""
    T = run(name)
    B = {t["day"]: t for t in run("base")}
    rows = []
    for t in T:
        b = B.get(t["day"])
        rows.append({"day": t["day"], "dir": t["dir"], "entry_t": t["entry_t"], "live_entry_t": t.get("live_entry_t"),
                     "skip": bool(t.get("skip")), "qty": t["qty"], "stop_px": t["stop_px"], "target_px": t["target_px"],
                     "entry_model": t.get("entry_model"), "entry_real": t["entry_px"] if not t.get("skip") else None,
                     "exit_kind": t["exit"], "exit_model_kind": t.get("exit_model_kind"), "exit_real": t.get("exit_px"),
                     "exit_model": t.get("exit_model"), "pnl_real": t["pnl"], "pnl_model": t.get("pnl_model"),
                     "pnl_backtest": b["pnl"] if b else None})
    with open(OUT_EXP, "w", encoding="utf-8") as fh:
        json.dump({"scenario": name, "fills": SCEN[name], "trades": rows}, fh, indent=1, default=str)
    print("wrote", OUT_EXP, len(rows), "trades")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        check()
    elif cmd == "run":
        run_all(sys.argv[2:] or None)
    elif cmd == "save":
        save()
    elif cmd == "expect":
        expect(*(sys.argv[2:3] or []))
