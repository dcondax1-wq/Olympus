"""LIT walk-forward RE-TUNING 2022-2026 (2026-11-17, research/writeups/lit-walkforward-2026-11-17.md). RESEARCH ONLY.

Question: LIT was tuned on 2026 Jan-Jun and makes ~$0 in 2021-25. Would a LIT that re-tunes its own knobs every month or
quarter (fit on the trailing 6 / 12 months, trade the next period out of sample) make money in 2021-25 too?

Grid (27 points, picked from a one-at-a-time sensitivity scan over all years: the knobs that move $ most in both regimes):
  disp   0.7 / 0.8 / 0.9      displacement size (ATR) the CISD candle needs (entry filter)
  be_r   1.0 / 1.5 / off      breakeven trigger in R (still entry + be_off 1.25)
  max_rr 5 / 8 / 12           where the VIX-band target is banked (R)
Live = disp 0.8, be_r 1.0, max_rr 8. Everything else is live_model.json "lit" (stop 1 tick beyond the sweep extreme, VIX
band >= 1.5R, 15-minute check, 1 trade a day, Monday rule, weekly stop, costs $1.40 + 1 tick; eval $1.90).

Every grid point is a full engine/lit.py run_x backtest (tools/lit_final.run) on 2021-11-08 .. 2026-10-16. A walk-forward
variant then picks, at each refit month, the point with the best score on the trailing window and takes THAT point's trades
in the next period (out of sample). Trades are re-sized after splicing: LIT size rule ($800 to a 20-pt stop, weekly stop
re-counted on the spliced list), the live eval path (engine/sizing.lit_qty two_week room_f 0.4 kept to session 80 = the
Builder 50K) and the Rapid EOD 50K (same two_week size, 30 micros, best-day cap 30% x $3,000 x 0.95, pass = $3,000 with
the best day <= 30% of the profit and >= 4 traded days, EOD trailing $2,000 floor locked at +$100).

Scores: "dd" = net - |max DD| (LIT size, trailing window); "pf" = PF with at least 1.5 trades a week (else not eligible).
Ties go to the live point. Variants: refit monthly / quarterly x trailing 6 / 12 months (expanding up to 12 from the 6th
month) x score = 8; primary declared before looking: monthly, 12 months, dd. OOS months: 2022-05 .. 2026-10 for all.
Placebo: the same refit dates with a RANDOM grid point each time (1,000 draws): share of draws with more 2022-25 $.

  python -X utf8 tools/lit_wf_retune.py      # ~2 min -> research/lit/wf_retune.json
Paper only. Nothing in live_model*.json or engine/ changes.
"""
from __future__ import annotations

import collections
import datetime as dt
import itertools
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from engine import rapid as RP  # noqa: E402
from engine import sizing as SZ  # noqa: E402
from tools import lit_adv_manage as A  # noqa: E402
from tools import lit_final as F  # noqa: E402
from tools import lit_rev_exit as R  # noqa: E402

OUT = os.path.join(ROOT, "research", "lit", "wf_retune.json")
LIVE = R.LIVE
PV, COMM, SLIP = lit.PV, lit.COMM, lit.SLIP
GRID = {"disp": [0.7, 0.8, 0.9], "be_r": [1.0, 1.5, 99.0], "max_rr": [5.0, 8.0, 12.0]}
LIVE_P = {"disp": LIVE["disp"], "be_r": LIVE["be_r"], "max_rr": LIVE["max_rr"]}
SESS = list(F.SESS)
MONTHS = sorted({d[:7] for d in SESS})
OOS0 = "2022-05"                      # first out-of-sample month (6 months of data before it: 2021-11 .. 2022-04)
OOS = [m for m in MONTHS if m >= OOS0]
ROWS = {"2022 (May-Dec)": ("2022-05-01", "2022-12-31"), "2023": ("2023-01-01", "2023-12-31"),
        "2024": ("2024-01-01", "2024-12-31"), "2025": ("2025-01-01", "2025-12-31"),
        "2022-25": ("2022-05-01", "2025-12-31"), "2026 H1": ("2026-01-01", "2026-06-30"),
        "2026 H2": ("2026-07-01", "2026-12-31")}
RAPID = {"target": 3000.0, "mll": 2000.0, "lock": 100.0, "dll": 1000.0, "max_micros": 30, "cons": 0.3, "min_days": 4}


def key(p):
    return (p["disp"], p["be_r"], p["max_rr"])


def name(p):
    return f"disp {p['disp']} / BE {'off' if p['be_r'] > 50 else p['be_r']} / bank {p['max_rr']:g}R"


# ------------------------------------------------------------------------------------------------ units
def units(T):
    """Engine trades -> size-free units (points per micro net of slippage, worst point, risk, target distance)."""
    out = []
    for t in T:
        q = int(t["qty"])
        risk = float(t["risk_pts"])
        pts = (float(t["pnl"]) + COMM * q) / (PV * q)
        out.append({"day": t["day"], "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "dir": t["dir"], "exit": t["exit"],
                    "risk": risk, "tgt": abs(float(t["target_px"]) - float(t["entry_px"])), "pts": pts,
                    "w1": -float(t["mae"]) * risk, "legs": [(1.0, pts)], "pnl0": float(t["pnl"])})
    return out


def lit_size(U):
    """The LIT size rule on a (spliced) list: qty_for(risk), weekly stop (2 STOP exits earlier in the ISO week -> half)."""
    done, out = [], []
    for u in sorted(U, key=lambda u: u["entry_t"]):
        wk = lit.iso_week(u["day"])
        ws = sum(1 for o in done if o["wk"] == wk and o["exit_t"] <= u["entry_t"] and o["exit"] == "STOP")
        q0 = lit.qty_for(u["risk"])
        q = max(1, int(q0 * LIVE["wk_stop"][1] + 1e-9)) if LIVE.get("wk_stop") and ws >= LIVE["wk_stop"][0] else q0
        pnl = u["pts"] * PV * q - COMM * q
        out.append({**u, "qty": q, "pnl": round(pnl, 2), "wk": wk})
        done.append(out[-1])
    return out


# ------------------------------------------------------------------------------------------------ stats
def span_stats(L, a, z):
    ss = [d for d in SESS if a <= d <= z]
    TT = [t for t in L if a <= t["day"] <= z]
    p = np.array([t["pnl"] for t in TT] or [0.0])
    gl = -p[p < 0].sum()
    eq = np.cumsum(p)
    dd = float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min()) if TT else 0.0
    return {"n": len(TT), "tpw": round(len(TT) / (len(ss) / 5), 2) if ss else 0, "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None,
            "net": round(float(p.sum())), "per_month": round(float(p.sum()) / (len(ss) / 21)) if ss else 0, "dd": round(dd),
            "se": round(float(np.std(p) * np.sqrt(len(TT)))) if len(TT) > 1 else 0}


def score(L, months, how):
    s = set(months)
    p = np.array([t["pnl"] for t in L if t["day"][:7] in s])
    if not len(p):
        return -1e18
    if how == "dd":
        eq = np.cumsum(p)
        dd = float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min())
        return float(p.sum()) + dd
    weeks = sum(1 for d in SESS if d[:7] in s) / 5
    if len(p) < 1.5 * weeks:
        return -1e18
    gl = -p[p < 0].sum()
    return float(p[p > 0].sum() / gl) if gl else 99.0


# ------------------------------------------------------------------------------------------------ eval paths
def by_session(U):
    by = collections.defaultdict(list)
    for t in sorted(U, key=lambda t: t["entry_t"]):
        by[t["day"]].append(t)
    return [by.get(s, []) for s in SESS]


def run_rapid(seq, by, horizon=60):
    """One Rapid EOD 50K eval, LIT lane only: the live two_week size on the Rapid's room, 30 micros, best-day cap."""
    cfg = A.CFG
    P = RAPID
    bal = peak = 0.0
    floor = -P["mll"]
    best, days = 0.0, 0
    for kk, si in enumerate(seq[:horizon]):
        cum, traded = 0.0, False
        for t in by[si]:
            if cum <= -P["dll"]:
                break
            st = {"profit": bal, "cum": cum, "room": bal + cum - floor, "session": kk + 1, "n_today": 0}
            m0 = lit.qty_for(t["risk"])
            q = SZ.lit_qty(m0, {"risk_pts": t["risk"], "tgt_pts": t["tgt"], "size_mult": 1.0}, cfg, room=st["room"], state=st,
                           learning=None)["qty"] if m0 else 0
            q = min(q, P["max_micros"])
            q, _ = RP.best_day_cap(q, t["tgt"], t["risk"], P["target"], cum)
            if q <= 0:
                continue
            pnl = A.leg_pnl(t, q)
            low = min(0.0, t["w1"] * PV * q - A.ECOMM * q, pnl)
            if cum + low <= -P["dll"]:
                pnl = low = -P["dll"] - cum - SLIP * PV * q
            if bal + cum + low <= floor:
                return "FAIL", kk + 1
            cum += pnl
            traded = True
        bal += cum
        days += traded
        if cum > best:
            best = cum
        if bal <= floor:
            return "FAIL", kk + 1
        peak = max(peak, bal)
        floor = min(max(floor, peak - P["mll"]), P["lock"])
        if bal >= max(P["target"], best / P["cons"]) and days >= P["min_days"]:
            return "PASS", kk + 1
    return "OPEN", min(len(seq), horizon)


def evals(U, a, z, kind="builder", last=None):
    """Fresh eval on every session of [a, z] (sessions after z may finish it, up to `last`); 2-week pass / fail, median."""
    by = by_session(U)
    ix = [i for i, d in enumerate(SESS) if a <= d <= z]
    if not ix:
        return {}
    end = len(SESS) if last is None else max(i for i, d in enumerate(SESS) if d <= last) + 1
    res = []
    for i in ix:
        seq = list(range(i, end))
        r = A.run_eval(seq, by, horizon=60) if kind == "builder" else run_rapid(seq, by, horizon=60)
        res.append((r, end - i))
    R10 = [r for r, av in res if av >= 10]
    N = len(R10) or 1
    pas = [r[1] for r, _ in res if r[0] == "PASS"]
    fal = [r[1] for r, _ in res if r[0] == "FAIL"]
    return {"p10": round(100.0 * sum(1 for r in R10 if r[0] == "PASS" and r[1] <= 10) / N, 1),
            "f10": round(100.0 * sum(1 for r in R10 if r[0] == "FAIL" and r[1] <= 10) / N, 1),
            "pass60": round(100.0 * len(pas) / len(res), 1), "fail60": round(100.0 * len(fal) / len(res), 1),
            "pass_med": float(np.median(pas)) if pas else None}


# ------------------------------------------------------------------------------------------------ walk-forward
def refit_months(freq):
    step = 1 if freq == "M" else 3
    return [m for k, m in enumerate(OOS) if k % step == 0]


def walk(runs, pts, freq, win, how):
    """-> (picks {refit month: point index}, month -> point index)."""
    refits = refit_months(freq)
    live_i = next(i for i, p in enumerate(pts) if key(p) == key(LIVE_P))
    picks, month_pick, cur = {}, {}, live_i
    for m in OOS:
        if m in refits:
            k = MONTHS.index(m)
            tr = MONTHS[max(0, k - win):k]
            sc = [score(runs[i], tr, how) for i in range(len(pts))]
            best = max(sc)
            if best > -1e17:
                cur = live_i if sc[live_i] == best else int(np.argmax(sc))
            picks[m] = cur
        month_pick[m] = cur
    return picks, month_pick


def splice(U_all, month_pick):
    return [u for m, i in month_pick.items() for u in U_all[i] if u["day"][:7] == m]


def report_rows(U, label):
    L = lit_size(U)
    o = {}
    for nm, (a, z) in ROWS.items():
        s = span_stats(L, a, z)
        s["builder"] = evals(U, a, z, "builder", last=z)
        s["rapid"] = evals(U, a, z, "rapid", last=z)
        o[nm] = s
    return o


def paired(L, L0):
    """WF minus static, per row: $ difference and its noise (1 s.e. from the per-session differences, sqrt(n) x sd)."""
    def per_day(X):
        c = collections.Counter()
        for t in X:
            c[t["day"]] += t["pnl"]
        return c
    a_, b_ = per_day(L), per_day(L0)
    o = {}
    for nm, (a, z) in ROWS.items():
        d = np.array([a_.get(s, 0.0) - b_.get(s, 0.0) for s in SESS if a <= s <= z])
        o[nm] = {"diff": round(float(d.sum())), "se": round(float(d.std(ddof=1) * np.sqrt(len(d)))) if len(d) > 1 else 0,
                 "days_changed": int((np.abs(d) > 0.5).sum())}
    return o


def stability(picks, pts):
    seq = [picks[m] for m in sorted(picks)]
    flips = sum(1 for a, b in zip(seq, seq[1:]) if a != b)
    per = {k: sum(1 for a, b in zip(seq, seq[1:]) if pts[a][k] != pts[b][k]) for k in GRID}
    cnt = collections.Counter(name(pts[i]) for i in seq)
    live = sum(1 for i in seq if key(pts[i]) == key(LIVE_P))
    return {"refits": len(seq), "flips": flips, "flip_rate": round(flips / max(1, len(seq) - 1), 2), "per_knob": per,
            "live_picked": live, "top": cnt.most_common(5)}


def placebo(runs_m, refits, n=1000, seed=7):
    """Random grid point at each refit date: 2022-25 and 2026 $ (native LIT-size $ per month)."""
    rng = np.random.default_rng(seed)
    K = len(runs_m)
    out = {"2022-25": [], "2026": []}
    for _ in range(n):
        cur, tot = None, collections.Counter()
        for m in OOS:
            if m in refits:
                cur = int(rng.integers(K))
            tot["2026" if m >= "2026" else "2022-25"] += runs_m[cur].get(m, 0.0)
        for s in out:
            out[s].append(tot[s])
    return {s: np.array(v) for s, v in out.items()}


def main():
    t0 = time.time()
    pts = [dict(zip(GRID, v)) for v in itertools.product(*GRID.values())]
    U_all, runs, runs_m = [], [], []
    for p in pts:
        T = F.run({**LIVE, **p})
        U = units(T)
        U_all.append(U)
        L = lit_size(U)
        runs.append(L)
        mm = collections.Counter()
        for t in L:
            mm[t["day"][:7]] += t["pnl"]
        runs_m.append(dict(mm))
    print(f"{len(pts)} grid runs {time.time() - t0:.0f}s", flush=True)
    live_i = next(i for i, p in enumerate(pts) if key(p) == key(LIVE_P))
    # check: re-sizing the static live run reproduces the engine's own $ (weekly stop included)
    d = max(abs(t["pnl"] - t["pnl0"]) for t in runs[live_i])
    print(f"static re-size max |diff| vs engine ${d:.2f}", flush=True)

    res = {"static_live": {"label": "Static LIT (today's knobs)", "point": name(pts[live_i]),
                           "rows": report_rows([u for u in U_all[live_i] if u["day"][:7] >= OOS0], "static")}}
    # best static on 2021-25 (in-sample upper bound): by the dd score on 2021-11..2025-12
    m2125 = [m for m in MONTHS if m <= "2025-12"]
    sc = [score(runs[i], m2125, "dd") for i in range(len(pts))]
    bi = int(np.argmax(sc))
    L0 = lit_size([u for u in U_all[live_i] if u["day"][:7] >= OOS0])
    Ub = [u for u in U_all[bi] if u["day"][:7] >= OOS0]
    res["static_best2125"] = {"label": "Best static picked on 2021-25 (in-sample, upper bound)", "point": name(pts[bi]),
                              "rows": report_rows(Ub, "best"), "vs_static": paired(lit_size(Ub), L0)}
    # each grid point's 2022-25 / 2026 halves (to see the spread)
    res["grid"] = [{"point": name(p), "2022-25": span_stats(runs[i], *ROWS["2022-25"])["net"],
                    "2026 H1": span_stats(runs[i], *ROWS["2026 H1"])["net"], "2026 H2": span_stats(runs[i], *ROWS["2026 H2"])["net"]}
                   for i, p in enumerate(pts)]
    wf = {}
    for freq, win, how in itertools.product(("M", "Q"), (6, 12), ("dd", "pf")):
        k = f"wf_{freq}{win}_{how}"
        picks, month_pick = walk(runs, pts, freq, win, how)
        U = splice(U_all, month_pick)
        rows = report_rows(U, k)
        pl = placebo(runs_m, set(refit_months(freq)))
        wf_m = collections.Counter()
        for m, i in month_pick.items():
            wf_m["2026" if m >= "2026" else "2022-25"] += runs_m[i].get(m, 0.0)
        wf[k] = {"label": f"Walk-forward: refit {'monthly' if freq == 'M' else 'quarterly'}, trailing {win} months, score {how}",
                 "rows": rows, "stability": stability(picks, pts), "vs_static": paired(lit_size(U), L0),
                 "placebo_p": {s: round(float((pl[s] >= wf_m[s]).mean()), 3) for s in pl},
                 "placebo_med": {s: round(float(np.median(pl[s]))) for s in pl},
                 "picks": {m: name(pts[i]) for m, i in picks.items()}}
        r = rows
        print(f"{k:14s} 22-25 {r['2022-25']['net']:+8,} PF {r['2022-25']['pf']} | H1 {r['2026 H1']['net']:+8,} | "
              f"H2 {r['2026 H2']['net']:+8,} | flips {wf[k]['stability']['flips']}/{wf[k]['stability']['refits']} "
              f"placebo p {wf[k]['placebo_p']}", flush=True)
        print("    vs static " + " | ".join(f"{r}: {v['diff']:+,} (se {v['se']:,})" for r, v in wf[k]["vs_static"].items()), flush=True)
    res["walk_forward"] = wf
    for k in ("static_live", "static_best2125"):
        r = res[k]["rows"]
        print(f"{k:14s} 22-25 {r['2022-25']['net']:+8,} PF {r['2022-25']['pf']} | H1 {r['2026 H1']['net']:+8,} | "
              f"H2 {r['2026 H2']['net']:+8,}  ({res[k]['point']})", flush=True)
    out = {"built": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "seconds": round(time.time() - t0),
           "grid": GRID, "live_point": LIVE_P, "oos": [OOS[0], OOS[-1]], "rows": list(ROWS), "primary": "wf_M12_dd", **res}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=float)
    print(f"-> {OUT} ({time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
