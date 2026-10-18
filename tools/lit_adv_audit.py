"""LIT backtest audit for the owner's "LIT Advanced Decisions Report" (2026-10-18) chapter 7 ("clocks and chart windows
change the evidence"), plus experiment 5 (synchronized NQ / ES divergence, SMT) of its chapter 13.

Research only. Changes no engine file: it wraps engine/lit.py (run_x, simulate_x, bars_1m) and tools/runlib.py scoring.

Part 1, the audit (python tools/lit_adv_audit.py audit -> research/lit/adv_audit.json). For every 2026 LIT live trade
(run lit_live, 120 trades, re-made here with engine.lit.run_x on live_model.json "lit"):
  same-bar exits      a stop / breakeven exit on a bar that also reached the target (order inside the bar unknown; the
                      backtest takes the stop: conservative); exits on the fill bar
  gap-through         a stop / breakeven exit on a bar that OPENED beyond the stop (a real stop-market fills at the open,
                      the backtest at the stop - 1 tick: optimistic); a target bar that opened beyond the target
  missing 1m minutes  1m windows dropped by bars_1m (they do not rebuild the 5m bar) inside a trade or its setup walk: the
                      1m walk jumps over them. Re-run with each dropped window replaced by its 5m bar ("gap5m", the
                      default-off fix, built here, not in the engine)
  session end         fills after 15:30, the 15:55 flat (the backtest exits at the 15:55 1m bar's CLOSE = 15:56; the bot
                      at 15:55:00), early-close holidays, 5m-fallback days (flat at the 16:00 close)
  clocks              5m setup time vs 1m fill time; trading-day label vs fill date; US-only DST weeks with a London box
  unresolved          setups still open at the end of the data; trades the walk drops (exit None)
  scoring             runlib.eval_speed counts every start, also the ones whose 10 / 20 sessions run past the end of the
                      span (they can only be OPEN): p10 / f10 / p20 / f20 are diluted. Re-scored on full windows only
                      (runlib.eval_speed(full_only=True), default off) and with H1 starts allowed to run into July.
Part 2, SMT (python tools/lit_adv_audit.py smt -> research/lit/adv_smt.json; save -> runs lit_adv_smt_*):
  see smt_flags() for the matching rule.
Judged on 2026 only: pick on H1 (Jan 2 - Jun 30), check on H2 (Jul 1 - Oct 16). Paper only. 1 CPU process.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from engine.data import DATA_DIR  # noqa: E402
from tools import lit_final as F  # noqa: E402
from tools import runlib as rl  # noqa: E402

OUTD = os.path.join(ROOT, "research", "lit")
P_LIVE = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]
PV, SLIP = lit.PV, lit.SLIP
ET = "America/New_York"
H1 = ("2026-01-01", "2026-06-30")
H2 = ("2026-07-01", "2026-12-31")
Y26 = ("2026-01-01", "2026-12-31")
SESS = F.SESS


def et(t):
    return pd.Timestamp(int(t), unit="s", tz="UTC").tz_convert(ET)


_S = {}


def live():
    """(M, C, B1, B5, trades) of the live LIT settings (all years; 2026 == run lit_live)."""
    if not _S:
        M, C = F.market(P_LIVE["ref"], P_LIVE.get("extra_boxes") or ())
        B1, B5 = F.bars(M, "1m"), F.bars(M, "5m")
        T = lit.run_x(M, C, P_LIVE, SESS, B1=B1, B5=B5)
        _S.update(M=M, C=C, B1=B1, B5=B5, T=T)
    return _S["M"], _S["C"], _S["B1"], _S["B5"], _S["T"]


# ================================================================================================ part 1: the audit
def gap5m_bars(M, B1):
    """B1 with every dropped 5m window of a full-coverage 1m day replaced by its 5m bar (one coarse bar, so the walk sees a
    stop or target touched inside the window). The default-off fix of the "missing 1m minutes" finding."""
    have = set((B1.t // 300 * 300).tolist())
    add = []
    for k in sorted(B1.full):
        d, s, e = M.days[k]
        for j in range(s, e):
            if int(M.t[j]) not in have and M.mod[j] < 1080:
                add.append(j)
    add = np.array(add, dtype=int)
    t = np.r_[B1.t, M.t[add]]
    o = np.r_[B1.o, M.o[add]]; h = np.r_[B1.h, M.h[add]]; l = np.r_[B1.l, M.l[add]]; c = np.r_[B1.c, M.c[add]]
    mod = np.r_[B1.mod, M.mod[add]]; day = np.r_[B1.day, M.day_of[add]]
    ix = np.argsort(t, kind="stable")
    B = lit.XBars(t[ix], o[ix], h[ix], l[ix], c[ix], mod[ix], day[ix], 60, B1.full)
    return B, len(add)


def _trade_bars(M, B1, B5, t):
    B = B1 if t["tf"] == 1 else B5
    kf = int(np.searchsorted(B.t, t["entry_t"]))
    kx = int(np.searchsorted(B.t, t["exit_t"] - B.secs))
    return B, kf, kx


def audit_trade(M, B1, B5, t):
    d = t["dir"]
    B, kf, kx = _trade_bars(M, B1, B5, t)
    hi, lo, c, o = B.dirs(d)
    q = t["qty"]
    entry, stop, tg = t["entry_px"] * d, t["stop_px"] * d, t["target_px"] * d
    risk = entry - stop
    cur = entry if t["exit"] == "BE" else stop
    x = {"day": t["day"], "dir": d, "exit": t["exit"], "tf": t["tf"], "pnl": t["pnl"], "qty": q}
    # same-bar exits
    x["exit_on_fill_bar"] = kx == kf
    x["amb_tgt"] = t["exit"] in ("STOP", "BE") and bool(hi[kx] >= tg)
    x["amb_tgt_usd"] = round((tg - (cur - SLIP)) * PV * q, 2) if x["amb_tgt"] else 0.0
    x["stop_bar_hit_1r"] = t["exit"] == "STOP" and bool(hi[kx] >= entry + risk)
    # gap-through
    x["gap_stop"] = t["exit"] in ("STOP", "BE") and kx != kf and bool(o[kx] < cur)
    x["gap_stop_usd"] = round((o[kx] - cur) * PV * q, 2) if x["gap_stop"] else 0.0
    x["gap_tgt"] = t["exit"] == "TARGET" and bool(o[kx] > tg)
    x["gap_tgt_usd"] = round((o[kx] - tg) * PV * q, 2) if x["gap_tgt"] else 0.0
    # worst point on the exit bar (intraday low used by the eval may come after the exit)
    seg = lo[kf:kx + 1]
    x["worst_on_exit_bar"] = t["exit"] in ("TARGET", "BE", "EOD") and kx > kf and bool(lo[kx] <= seg.min())
    # missing 1m minutes inside the trade (1m only) and in the setup walk
    setup_t = int(M.t[t["i"]]) + 300
    if t["tf"] == 1:
        k0 = int(np.searchsorted(B.t, setup_t))
        tt = B.t[k0:kx + 1]
        dif = np.diff(tt)
        miss = int(((dif - 60) // 60)[(dif > 60)].sum())
        x["missing_min_setup"] = int(((np.diff(B.t[k0:kf + 1]) - 60) // 60)[np.diff(B.t[k0:kf + 1]) > 60].sum()) if kf > k0 else 0
        x["missing_min_trade"] = miss - x["missing_min_setup"]
    else:
        x["missing_min_setup"] = x["missing_min_trade"] = None
    # clocks
    x["setup_et"] = et(setup_t).strftime("%H:%M")
    x["fill_et"] = et(t["entry_t"]).strftime("%H:%M")
    x["delay_min"] = round((t["entry_t"] - setup_t) / 60.0, 1)
    x["fill_after_1530"] = int(B.mod[kf]) >= 930
    x["fill_date_differs"] = et(t["entry_t"]).strftime("%Y-%m-%d") != t["day"]
    # session end
    x["exit_mod"] = int(B.mod[kx])
    x["eod"] = t["exit"] == "EOD"
    x["eod_close_vs_open_usd"] = round((o[kx] - c[kx]) * PV * q, 2) if (t["exit"] == "EOD" and t["tf"] == 1 and B.mod[kx] >= 955) else 0.0
    x["exit_in_flat_bar"] = t["exit"] in ("STOP", "BE", "TARGET") and int(B.mod[kx]) >= P_LIVE["flat_mod"]
    x["exit_in_flat_bar_usd"] = 0.0
    if x["exit_in_flat_bar"]:
        px = t.get("exit_px")
        ex = (cur - SLIP) if t["exit"] in ("STOP", "BE") else tg
        x["exit_in_flat_bar_usd"] = round(((o[kx] - SLIP) - ex) * PV * q, 2)
    from engine.lit_live import early_close
    x["early_close_day"] = early_close(t["day"]) is not None
    x["eod_by_day_end"] = t["exit"] == "EOD" and int(B.mod[kx]) < P_LIVE["flat_mod"]
    x["swept"] = t["swept"]
    return x


def eval_honest(days, horizon_list=(10, 20)):
    """p / f within H sessions counting only the starts that can see all H sessions."""
    from engine.analytics import PLANS, simulate_eval
    plan = PLANS["builder_50k"]
    pn = [d["pnl"] for d in days]; lo = [d["low"] for d in days]
    out = {}
    for H in horizon_list:
        res = [simulate_eval(pn[i:i + H], plan, lo[i:i + H]) for i in range(len(days) - H + 1)]
        n = len(res) or 1
        out[f"p{H}"] = round(100 * sum(r["result"] == "PASS" for r in res) / n, 1)
        out[f"f{H}"] = round(100 * sum(r["result"] == "FAIL" for r in res) / n, 1)
        out[f"n{H}"] = len(res)
    return out


def scoring_check(T):
    """runlib's eval odds (every start) vs full windows only, and H1 starts allowed to run into July."""
    days_all = rl.days_of(T, [s for s in SESS if s >= "2026"])
    o = {}
    for nm, (a, z) in (("2026", Y26), ("H1", H1), ("H2", H2)):
        D = [d for d in days_all if a <= d["date"] <= z]
        e = rl.eval_speed(D)
        o[nm] = {"runlib": {k: e[k] for k in ("p10", "f10", "p20", "f20")}, "full_windows": eval_honest(D), "starts": len(D)}
    # H1 starts that may continue into H2 (the data exists): the honest H1 number
    idx = [i for i, d in enumerate(days_all) if H1[0] <= d["date"] <= H1[1]]
    from engine.analytics import PLANS, simulate_eval
    plan = PLANS["builder_50k"]
    pn = [d["pnl"] for d in days_all]; lo = [d["low"] for d in days_all]
    for H in (10, 20):
        res = [simulate_eval(pn[i:i + H], plan, lo[i:i + H]) for i in idx]
        o["H1"][f"into_july_p{H}"] = round(100 * sum(r["result"] == "PASS" for r in res) / len(res), 1)
        o["H1"][f"into_july_f{H}"] = round(100 * sum(r["result"] == "FAIL" for r in res) / len(res), 1)
    worst = min(d["low"] for d in days_all)
    o["worst_day_low"] = round(worst)
    o["days_below_dll"] = sum(1 for d in days_all if d["low"] <= -1000)
    return o


def dst_check(T):
    """US-only DST weeks of 2026 (US switched 2026-03-08, Europe 2026-03-29): London boxes sit 1 hour off London time."""
    rows = [t for t in T if "2026-03-09" <= t["day"] <= "2026-03-27"]
    lon = [t for t in rows if any(s.startswith("lon") for s in t["swept"])]
    return {"trades": len(rows), "london_box_sweeps": len(lon), "london_pnl": round(sum(t["pnl"] for t in lon)),
            "days": [t["day"] for t in lon]}


def tz_check(M):
    """The ET minute of day vs pandas tz conversion on a sample of bars around both 2026 DST changes."""
    bad = 0
    for lo_, hi_ in (("2026-03-06", "2026-03-11"), ("2025-10-31", "2025-11-04")):
        ix = [i for i, d in enumerate(M.dates) if lo_ <= d <= hi_]
        for i in ix:
            ts = et(M.t[i])
            bad += (ts.hour * 60 + ts.minute) != int(M.mod[i])
    return bad


def compare(T0, T1):
    """Trade-by-trade differences of two 2026 trade lists (keyed by day)."""
    a = {t["day"]: t for t in T0 if t["day"] >= "2026"}
    b = {t["day"]: t for t in T1 if t["day"] >= "2026"}
    ch = []
    for d in sorted(set(a) | set(b)):
        x, y = a.get(d), b.get(d)
        if x and y and x["entry_t"] == y["entry_t"] and x["exit"] == y["exit"] and abs(x["pnl"] - y["pnl"]) < 0.01:
            continue
        ch.append({"day": d, "before": (x["exit"], x["pnl"]) if x else None, "after": (y["exit"], y["pnl"]) if y else None})
    dn = sum(y["pnl"] for y in b.values()) - sum(x["pnl"] for x in a.values())
    return {"changed": ch, "n_changed": len(ch), "d_net": round(dn), "n_before": len(a), "n_after": len(b),
            "net_before": round(sum(x["pnl"] for x in a.values())), "net_after": round(sum(y["pnl"] for y in b.values()))}


def halves(T):
    o = {}
    for nm, (a, z) in (("H1", H1), ("H2", H2), ("2026", Y26)):
        TT = [t for t in T if a <= t["day"] <= z]
        o[nm] = round(sum(t["pnl"] for t in TT))
    return o


def audit():
    M, C, B1, B5, T = live()
    T26 = [t for t in T if t["day"] >= "2026"]
    rows = [audit_trade(M, B1, B5, t) for t in T26]
    R = {"n": len(rows), "net": round(sum(t["pnl"] for t in T26)), "tz_mismatch_bars": tz_check(M)}

    def grp(key, usd=None):
        g = [r for r in rows if r[key]]
        out = {"n": len(g), "pnl": round(sum(r["pnl"] for r in g)), "days": [r["day"] for r in g]}
        if usd:
            out["usd"] = round(sum(r[usd] for r in g))
        return out
    R["exit_on_fill_bar"] = grp("exit_on_fill_bar")
    R["stop_or_be_bar_also_hit_target"] = grp("amb_tgt", "amb_tgt_usd")
    R["stop_bar_also_hit_1r"] = grp("stop_bar_hit_1r")
    R["stop_gap_through"] = grp("gap_stop", "gap_stop_usd")
    R["target_gap_through"] = grp("gap_tgt", "gap_tgt_usd")
    R["worst_point_on_exit_bar"] = grp("worst_on_exit_bar")
    R["fill_after_1530"] = grp("fill_after_1530")
    R["fill_date_differs"] = grp("fill_date_differs")
    R["eod"] = grp("eod", "eod_close_vs_open_usd")
    R["exit_in_flat_bar"] = grp("exit_in_flat_bar", "exit_in_flat_bar_usd")
    R["early_close_day"] = grp("early_close_day")
    R["eod_by_day_end"] = grp("eod_by_day_end")
    R["tf5"] = {"n": sum(r["tf"] == 5 for r in rows), "days": [r["day"] for r in rows if r["tf"] == 5],
                "pnl": round(sum(r["pnl"] for r in rows if r["tf"] == 5))}
    ms = [r for r in rows if r["tf"] == 1 and (r["missing_min_trade"] or r["missing_min_setup"])]
    R["missing_1m"] = {"n": len(ms), "trade_minutes": sum(r["missing_min_trade"] for r in ms),
                       "setup_minutes": sum(r["missing_min_setup"] for r in ms), "days": [r["day"] for r in ms]}
    dl = np.array([r["delay_min"] for r in rows])
    R["delay_min"] = {"median": float(np.median(dl)), "p90": float(np.percentile(dl, 90)), "max": float(dl.max()),
                      "over_30": int((dl > 30).sum())}
    R["dst"] = dst_check(T26)
    # the gap5m fix: same rules, the dropped 1m windows replaced by their 5m bar
    Bg, nadd = gap5m_bars(M, B1)
    Tg = lit.run_x(M, C, P_LIVE, SESS, B1=Bg, B5=B5)
    R["gap5m"] = {"windows_added": nadd, **compare(T, Tg), "halves_before": halves(T26), "halves_after": halves(Tg)}
    # unresolved: the last session and any setup the walk cannot finish
    last = SESS[-1]
    R["last_session"] = {"day": last, "trade": [(t["exit"], t["pnl"]) for t in T26 if t["day"] == last]}
    R["scoring"] = scoring_check(T26)
    R["rows"] = rows
    json.dump(R, open(os.path.join(OUTD, "adv_audit.json"), "w"), indent=1, default=float)
    show = {k: v for k, v in R.items() if k != "rows"}
    for k, v in show.items():
        if isinstance(v, dict) and "changed" in v:
            v = {**v, "changed": v["changed"][:12]}
        print(k, json.dumps(v, default=float)[:900])
    return R


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "audit"
    if cmd == "audit":
        audit()
    else:
        raise SystemExit(f"unknown command {cmd}")
