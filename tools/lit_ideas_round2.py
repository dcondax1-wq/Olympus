"""LIT ideas round 2 (job 28, 2026-11-04): scale-in robustness (bootstrap by session, the best trades removed in smaller steps) and six
new LIT ideas on the exact live trades (tools/lit_ideas_night + tools/lit_edge machinery). RESEARCH ONLY: engine/ and live_model*.json untouched.

New ideas (all size tilts that keep every trade, or a per-setup-type cut time; cut points fixed on 2026 Jan-Jun):
  asia      the Asia-slot result of the same trading day (18:00-02:00, finished before LIT's entry) sizes LIT: after a loss / a win
  lvl_age   age of the swept level in hours (old resting liquidity vs a fresh one)
  lvl_touch number of times the level was touched before the sweep
  reclaim   time sweep -> CISD close in 5m bars (sweep-then-reclaim speed)
  reuse     the swept level was already swept by LIT's trade of the last 3 sessions (one entry per level, as size)
  cutcurve  the 15-minute cut moved per setup type (London vs later, session boxes vs daily/weekly levels): 10 / 25 minutes

    python -X utf8 tools/lit_ideas_round2.py scale    # scale-in bootstrap -> research/lit/ideas_round2_scale.json
    python -X utf8 tools/lit_ideas_round2.py grid     # the six ideas -> research/lit/ideas_round2_grid.json
    python -X utf8 tools/lit_ideas_round2.py report
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import lit_ideas_night as N  # noqa: E402
from tools import lit_edge as E  # noqa: E402
from tools import lit_final as F  # noqa: E402
from engine import lit  # noqa: E402

OUT = os.path.join(ROOT, "research", "lit", "ideas_round2_grid.json")
OUT_S = os.path.join(ROOT, "research", "lit", "ideas_round2_scale.json")
LIVE = E.LIVE
ET = dt.timezone(dt.timedelta(hours=-5))
try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except Exception:  # noqa: BLE001
    pass


# ================================================================================================ scale-in robustness
def cmd_scale(n_boot=5000, seed=3):
    """Scale-in (OFF) at LIT size, 2026: per-trade $ the adds make; bootstrap by session and by week; the best 1 / 2 / 3 trades removed;
    extra cost of worse add fills (+4 ticks per add micro, the live $1.90 vs the research $1.40)."""
    T0 = F.run({**LIVE})
    T1 = F.run({**LIVE, "scale_in": E.SCALE})
    b = {t["entry_t"]: t for t in T0}
    rows = []
    for t in T1:
        if t.get("adds") and t["day"] >= "2026-01-01":
            o = b[t["entry_t"]]
            q_add = sum(int(a.get("qty", 0)) for a in t["adds"])
            rows.append({"day": t["day"], "d": float(t["pnl"] - o["pnl"]), "q": q_add})
    T26 = [t for t in T0 if t["day"] >= "2026-01-01"]
    sessions = {"H1": sorted({t["day"] for t in T26 if t["day"] <= "2026-06-30"}), "H2": sorted({t["day"] for t in T26 if t["day"] > "2026-06-30"})}
    out = {}
    rng = np.random.default_rng(seed)
    for sp in ("H1", "H2"):
        S = sessions[sp]
        # every 2026 session of the half (trade days of the base run + days with adds; no-trade days add 0)
        days = sorted({r["day"] for r in rows if (r["day"] <= "2026-06-30") == (sp == "H1")} | set(S))
        gain = {d: 0.0 for d in days}
        qd = {d: 0 for d in days}
        for r in rows:
            if r["day"] in gain:
                gain[r["day"]] += r["d"]
                qd[r["day"]] += r["q"]
        g = np.array([gain[d] for d in days])
        q = np.array([qd[d] for d in days], float)
        order = np.sort(g)[::-1]
        res = {"sessions": len(days), "trades_with_adds": int(sum(1 for r in rows if (r["day"] <= "2026-06-30") == (sp == "H1"))),
               "gain": round(float(g.sum())), "best3": [round(float(x)) for x in order[:3]], "worst3": [round(float(x)) for x in order[-3:]],
               "without_best1": round(float(order[1:].sum())), "without_best2": round(float(order[2:].sum())), "without_best3": round(float(order[3:].sum())),
               "add_micros": int(q.sum())}
        # bootstrap sessions with replacement
        n = len(days)
        bs = np.array([g[rng.integers(0, n, n)].sum() for _ in range(n_boot)])
        wk = collections.defaultdict(list)
        for i, d in enumerate(days):
            wk[lit.iso_week(d)].append(i)
        W = list(wk.values())
        bw = np.array([sum(g[W[j]].sum() for j in rng.integers(0, len(W), len(W))) for _ in range(n_boot)])
        res["boot_session"] = {"p5": round(float(np.percentile(bs, 5))), "p50": round(float(np.percentile(bs, 50))), "p95": round(float(np.percentile(bs, 95))),
                               "share_positive": round(float((bs > 0).mean()), 3)}
        res["boot_week"] = {"p5": round(float(np.percentile(bw, 5))), "p50": round(float(np.percentile(bw, 50))), "p95": round(float(np.percentile(bw, 95))),
                            "share_positive": round(float((bw > 0).mean()), 3)}
        # bootstrap after removing the single best trade-day
        g1 = np.sort(g)[:-1]
        b1 = np.array([g1[rng.integers(0, len(g1), n)].sum() for _ in range(n_boot)])
        res["boot_session_without_best1"] = {"p5": round(float(np.percentile(b1, 5))), "p50": round(float(np.percentile(b1, 50))),
                                             "share_positive": round(float((b1 > 0).mean()), 3)}
        res["extra_cost"] = {str(tk): round(float(q.sum()) * (tk * 0.25 * 2.0 + 0.5)) for tk in (0, 4, 8)}
        res["net_after_4_ticks_and_live_comm"] = round(res["gain"] - res["extra_cost"]["4"])
        res["net_without_best1_after_4_ticks"] = round(res["without_best1"] - res["extra_cost"]["4"])
        out[sp] = res
    json.dump(out, open(OUT_S, "w"), indent=1)
    print(json.dumps(out, indent=1))


# ================================================================================================ the six ideas
def et_min(ts):
    x = dt.datetime.fromtimestamp(int(ts), ET)
    return x.hour * 60 + x.minute


def asia_trades():
    """Asia-slot trades (entry 18:00-02:00 ET, trading-day keyed) of the all-hours engine run: {day: [(entry_t, exit_t, dir, R)]}."""
    P = {**LIVE, "all_hours": True, "window": [[1080, 1440], [0, 930]], "max_per_day": 2, "per_session": [[[1080, 120], [120, 480], [480, 1080]], 1]}
    T = F.run(P)
    out = collections.defaultdict(list)
    for t in T:
        m = et_min(t["entry_t"])
        if m >= 1080 or m < 120:
            risk = abs(t["entry_px"] - t["stop_px"])
            pts = (t["pnl"] / max(1, t["qty"])) / lit.PV if t.get("qty") else 0.0
            out[t["day"]].append((int(t["entry_t"]), int(t["exit_t"]), int(t["dir"]), (pts / risk) if risk else 0.0))
    return out, len(T)


def feature_fns():
    c = E.ctx()
    q = E.h1_cut
    V = collections.OrderedDict()

    def tri(key, hi_good, up=1.25, dn=0.75, which="both"):
        lo, hi = q(key, 1 / 3), q(key, 2 / 3)

        def f(t, r):
            v = N.lvl(r, key)
            if v != v:
                return 1.0
            g = (v >= hi) if hi_good else (v <= lo)
            b = (v <= lo) if hi_good else (v >= hi)
            return up if (g and which in ("both", "up")) else dn if (b and which in ("both", "down")) else 1.0
        return f
    V["lvl_age_old_up125"] = (tri("lvl_age_h", True, which="up"), "swept level is old (top third by hours) x1.25", "old resting liquidity")
    V["lvl_age_old_up125_fresh_dn075"] = (tri("lvl_age_h", True), "old level x1.25, fresh level x0.75", "old resting liquidity")
    V["lvl_age_fresh_up125"] = (tri("lvl_age_h", False, which="up"), "fresh level (bottom third) x1.25", "fresh levels react")
    V["lvl_touch_many_up125"] = (tri("lvl_touches", True, which="up"), "level touched many times before (top third) x1.25", "more stops rest there")
    V["lvl_touch_many_up125_few_dn075"] = (tri("lvl_touches", True), "many touches x1.25, few x0.75", "same")
    V["lvl_touch_few_up125"] = (tri("lvl_touches", False, which="up"), "few touches (bottom third) x1.25", "clean level")
    V["reclaim_fast_up125"] = (tri("sweep_bars", False, which="up"), "sweep -> CISD fast (bottom third of 5m bars) x1.25", "fast reclaim")
    V["reclaim_fast_up125_slow_dn075"] = (tri("sweep_bars", False), "fast reclaim x1.25, slow x0.75", "same")
    V["reclaim_slow_dn075"] = (tri("sweep_bars", False, which="down"), "slow reclaim (top third) x0.75", "slow = weak")
    # level reuse: the swept level names already swept by the previous LIT trade within 3 sessions
    I = c["intel"]
    T = sorted(c["T"], key=lambda t: t["entry_t"])
    prev = {}
    hist = []
    for t in T:
        row = I.get(int(t["entry_t"]), {})
        names = set(str(row.get("swept") or "").split())
        d0 = dt.date.fromisoformat(t["day"])
        reuse = False
        for h_day, h_names in hist[-4:]:
            if 0 < (d0 - h_day).days <= 5 and (names & h_names):
                reuse = True
        prev[int(t["entry_t"])] = reuse
        hist.append((d0, names))
    V["reuse_dn075"] = (lambda t, r: 0.75 if prev.get(int(t["entry_t"])) else 1.0, "the same level was swept by LIT's last trade within 3 sessions: x0.75", "one entry per level")
    V["reuse_up125"] = (lambda t, r: 1.25 if prev.get(int(t["entry_t"])) else 1.0, "same level swept again: x1.25", "sweeps repeat")
    # Asia-slot interaction
    A, n_all = asia_trades()

    def asia_res(t):
        done = [x for x in A.get(t["day"], []) if x[1] <= int(t["entry_t"])]
        return sum(x[3] for x in done) if done else None

    def asia_same(t):
        done = [x for x in A.get(t["day"], []) if x[1] <= int(t["entry_t"])]
        if not done:
            return None
        return any(x[2] == t["dir"] for x in done)
    V["asia_lost_dn075"] = (lambda t, r: 0.75 if (asia_res(t) is not None and asia_res(t) < 0) else 1.0, "Asia slot lost before LIT's entry: x0.75", "bad overnight tape")
    V["asia_lost_up125"] = (lambda t, r: 1.25 if (asia_res(t) is not None and asia_res(t) < 0) else 1.0, "Asia slot lost: x1.25", "stops run, then reversal")
    V["asia_won_up125"] = (lambda t, r: 1.25 if (asia_res(t) is not None and asia_res(t) > 0) else 1.0, "Asia slot won: x1.25", "trend overnight")
    V["asia_won_dn075"] = (lambda t, r: 0.75 if (asia_res(t) is not None and asia_res(t) > 0) else 1.0, "Asia slot won: x0.75", "give-back")
    V["asia_same_dir_up125"] = (lambda t, r: 1.25 if asia_same(t) else 1.0, "Asia trade in the same direction as LIT: x1.25", "agreement")
    V["asia_opp_dir_dn075"] = (lambda t, r: 0.75 if asia_same(t) is False else 1.0, "Asia trade opposite to LIT: x0.75", "conflict")
    n_days = sum(1 for t in c["T"] if t["day"] >= "2026" and A.get(t["day"]))
    return V, {"asia_runs": n_all, "asia_days_with_a_trade_2026": len({d for d in A if d >= "2026"}), "lit_days_with_asia_before": n_days}


def trades_cut(rule):
    """Re-manage every live trade with the live executor but the 15-minute check moved by setup type: rule(t, row) -> minutes or None."""
    c = E.ctx()
    out = []
    for t in c["T"]:
        row = c["intel"].get(int(t["entry_t"]), {})
        at = rule(t, row)
        X = {"tc1": {"at": at}} if at else {}
        out += N.trades2(X, T=[t])
    return out


def cut_rules():
    R = collections.OrderedDict()
    R["london_at10_rest15"] = (lambda t, r: 10 if r.get("session") == "London 02-05" else None, "cut at 10 min in the London 02-05 trades")
    R["london_at25_rest15"] = (lambda t, r: 25 if r.get("session") == "London 02-05" else None, "cut at 25 min in the London 02-05 trades")
    R["ny_at10"] = (lambda t, r: 10 if str(r.get("session", "")).startswith("NY") else None, "cut at 10 min in the NY trades")
    R["ny_at25"] = (lambda t, r: 25 if str(r.get("session", "")).startswith("NY") else None, "cut at 25 min in the NY trades")
    R["box_at10"] = (lambda t, r: 10 if "box" in str(r.get("lvl_type", "")).lower() else None, "cut at 10 min when a session box was swept")
    R["box_at25"] = (lambda t, r: 25 if "box" in str(r.get("lvl_type", "")).lower() else None, "cut at 25 min when a session box was swept")
    R["buildup_at10"] = (lambda t, r: 10 if r.get("lvl_type") == "build-up" else None, "cut at 10 min when a build-up level was swept")
    R["buildup_at25"] = (lambda t, r: 25 if r.get("lvl_type") == "build-up" else None, "cut at 25 min when a build-up level was swept")
    R["wide_stop_at25"] = (lambda t, r: 25 if N.lvl(r, "stop_pts") >= E.h1_cut("stop_pts", 2 / 3) else None, "cut at 25 min for wide stops (top third)")
    R["wide_stop_at10"] = (lambda t, r: 10 if N.lvl(r, "stop_pts") >= E.h1_cut("stop_pts", 2 / 3) else None, "cut at 10 min for wide stops")
    return R


def cmd_grid():
    t0 = time.time()
    res = json.load(open(OUT)) if os.path.exists(OUT) else {}
    c = E.ctx()
    base, U0, L0 = E.evaluate({}, fund=True)
    bs = E.short(base)
    res["base"] = bs
    print(E.line("base", bs), flush=True)
    V, info = feature_fns()
    res["_asia_info"] = info
    print(info, flush=True)
    for nm, (fn, desc, hyp) in V.items():
        N.run_variant(res, "tilt", nm, bs, L0, mfn=fn, plc=True, info={"desc": desc, "hyp": hyp})
        json.dump(res, open(OUT, "w"), indent=1, default=float)
    for nm, (rule, desc) in cut_rules().items():
        key = f"cutcurve:{nm}"
        if key in res:
            continue
        U = trades_cut(rule)
        N.run_variant(res, "cutcurve", nm, bs, L0, U=U, info={"desc": desc})
        json.dump(res, open(OUT, "w"), indent=1, default=float)
    print(f"done in {time.time() - t0:.0f}s", flush=True)


def report():
    res = json.load(open(OUT))
    for k, s in res.items():
        if k in ("base", "_asia_info") or "d_lit" not in s:
            continue
        pl = s.get("placebo") or {}
        print(f"{k:42s} dLIT {s['d_lit']['H1']:+7,} {s['d_lit']['H2']:+7,} ref {s['d_lit']['2021-25']:+7,} | dEV {s['d_eval']['H1']:+7,} {s['d_eval']['H2']:+7,} | p10 {tuple(s['d_p10'].values())} f10 {tuple(s['d_f10'].values())} "
              f"| fund {tuple(s['d_fund'].values())} | chg {tuple(s['chg'].values())} | pl {pl}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "grid"
    if cmd == "scale":
        cmd_scale()
    elif cmd == "grid":
        cmd_grid()
    elif cmd == "report":
        report()
