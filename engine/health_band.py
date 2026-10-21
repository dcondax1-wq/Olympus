"""'Within expected range' (competitor-features #6, 2026-10-21): is live LIT broken, or is this just a normal bad week?

From the 2026 sessions of run lit_live (the live config's replay) a bootstrap draws 4,000 paths of N sessions (N = 1..60;
a session with no trade counts as 0, so the band also says how many trades N sessions bring) and stores, for every N, the
percentiles 1..99 of the cumulative R, the number of trades and the $ (LIT size rule, and the eval path: run
lit_adopt_t15_be_off_eval, the two_week sizing the paper and PC bots trade). Two bands: all of 2026 and H2 only (Jul-Oct,
the check half: "quote the H2 rate"). The headline uses the H2 band; the 2026 band is shown next to it.
The live and paper results so far are placed in that band: "inside the expected range (p38)", amber below p10, red below
p5 ("investigate"). It reports only. It never sizes, pauses or changes anything.

  python -X utf8 -m engine.health_band build     # -> research/lab/health_band.json (~2 s; rerun when run lit_live changes)
  python -X utf8 -m engine.health_band show      # the band at 5 / 10 / 20 / 40 sessions
Pure functions (tests/test_perf.py): bootstrap(days, ...), band_at(B, n), pct_of(qs, v), compare(B, trades, ...).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "research", "lab", "health_band.json")
RUN = "lit_live"
EVAL_RUN = "lit_adopt_t15_be_off_eval"
LIT_START = "2026-10-19"          # LIT is the live strategy from the session of Mon 2026-10-19 (locked 2026-10-18)
N_MAX = 60
REPS = 4000
SEED = 20261021
VERSION = 1
QS = list(range(1, 100))          # stored percentiles


def _run(rid):
    try:
        with open(os.path.join(ROOT, "research", "runs", rid + ".json"), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def sessions_of(run, ev=None, a="2026-01-01", z="2026-12-31"):
    """One row per session: [R, trades, $ LIT rule, $ eval path] (the run's days, trades summed per day)."""
    c = run["trade_cols"]
    T = [dict(zip(c, r)) for r in run["trades"]]
    byd = {}
    for t in T:
        if a <= t["day"] <= z:
            x = byd.setdefault(t["day"], [0.0, 0, 0.0, 0.0])
            x[0] += float(t["r"] or 0)
            x[1] += 1
            x[2] += float(t["pnl"] or 0)
    evd = {}
    if ev:
        ce = ev["trade_cols"]
        for r in ev["trades"]:
            t = dict(zip(ce, r))
            evd[(t["day"], int(t["entry_t"]))] = float(t["pnl"] or 0)
        for t in T:
            if a <= t["day"] <= z:
                byd[t["day"]][3] += evd.get((t["day"], int(t["entry_t"])), 0.0)
    days = [d[0] for d in run["days"] if a <= d[0] <= z]
    return np.array([byd.get(d, [0.0, 0, 0.0, 0.0]) for d in days], float), days


def bootstrap(S, n_max=N_MAX, reps=REPS, seed=SEED):
    """S: sessions x [R, n, $, $eval] -> {metric: array (n_max, 99)} of percentiles 1..99 of the cumulative sums."""
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(S), size=(reps, n_max))
    out = {}
    for j, k in enumerate(("r", "n", "usd", "usd_eval")):
        cum = np.cumsum(S[idx, j], axis=1)                       # reps x n_max
        out[k] = np.percentile(cum, QS, axis=0).T                 # n_max x 99
    return out


def trade_bootstrap(R, n_max=N_MAX, reps=REPS, seed=SEED + 1):
    """Per-trade R -> percentiles of the cumulative R after N trades, and the chance of a losing streak of k in 20 trades."""
    rng = np.random.default_rng(seed)
    X = np.asarray(R, float)[rng.integers(0, len(R), size=(reps, n_max))]
    cum = np.percentile(np.cumsum(X, axis=1), QS, axis=0).T
    loss = X[:, :20] < 0
    streak = np.zeros(reps, int)
    run_ = np.zeros(reps, int)
    for j in range(20):
        run_ = np.where(loss[:, j], run_ + 1, 0)
        streak = np.maximum(streak, run_)
    p_streak = {int(k): round(100.0 * float((streak >= k).mean()), 1) for k in range(1, 9)}
    return cum, p_streak


def build():
    run, ev = _run(RUN), _run(EVAL_RUN)
    if not run:
        raise SystemExit(f"run {RUN} missing")
    out = {"v": VERSION, "built": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "run": RUN, "eval_run": EVAL_RUN,
           "run_built": run.get("built"), "n_max": N_MAX, "reps": REPS, "qs": [QS[0], QS[-1]], "bands": {}, "lit_start": LIT_START}
    c = run["trade_cols"]
    for name, (a, z) in {"H2": ("2026-07-01", "2026-12-31"), "2026": ("2026-01-01", "2026-12-31")}.items():
        S, days = sessions_of(run, ev, a, z)
        B = bootstrap(S)
        R = [float(r[c.index("r")] or 0) for r in run["trades"] if a <= r[0] <= z]
        tb, ps = trade_bootstrap(R)
        out["bands"][name] = {"from": days[0], "to": days[-1], "sessions": len(days), "trades": int(S[:, 1].sum()),
                              "r_per_session": round(float(S[:, 0].mean()), 3), "usd_eval_per_session": round(float(S[:, 3].mean()), 1),
                              "trades_per_week": round(5 * float(S[:, 1].mean()), 2),
                              **{k: np.round(v, 2).tolist() for k, v in B.items()},
                              "r_trades": np.round(tb, 2).tolist(), "p_streak20": ps}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, separators=(",", ":"))
    return out


def load(path=OUT):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def pct_of(qs, v):
    """Percentile (0..100) of value v within the stored percentiles 1..99 (linear between them, clipped to 0.5 / 99.5)."""
    q = np.asarray(qs, float)
    if v is None or not len(q):
        return None
    if v < q[0]:
        return 0.5
    if v > q[-1]:
        return 99.5
    i = int(np.searchsorted(q, v, side="right"))
    if i >= len(q):
        return 99.0
    lo, hi = q[i - 1], q[i]
    f = 0.0 if hi == lo else (v - lo) / (hi - lo)
    # ties (a flat stretch of the distribution, e.g. many 0R paths): the middle of the tie
    j = int(np.searchsorted(q, v, side="left"))
    if hi == lo or (j < i - 1):
        return round(float((j + i) / 2.0 + 0.5), 1)
    return round(float(i + f), 1)


def band_at(Bn, n, metric="r"):
    """{"p5", "p10", "p25", "p50", "p75", "p90", "p95"} of a metric after n sessions."""
    n = max(1, min(int(n), len(Bn[metric])))
    q = Bn[metric][n - 1]
    return {f"p{p}": q[p - 1] for p in (5, 10, 25, 50, 75, 90, 95)}


def cone(Bn, n_max, metric="usd_eval"):
    """Lines for the equity chart: per session 0..n_max, p5 / p25 / p50 / p75 / p95 of the cumulative metric."""
    n_max = max(1, min(int(n_max), len(Bn[metric])))
    rows = [[0, 0, 0, 0, 0, 0]]
    for k in range(1, n_max + 1):
        q = Bn[metric][k - 1]
        rows.append([k, q[4], q[24], q[49], q[74], q[94]])
    return {"cols": ["session", "p5", "p25", "p50", "p75", "p95"], "rows": rows, "metric": metric}


def sessions_between(a, b):
    """Weekday sessions from day a to day b, both included (CME holidays are rare enough to ignore here)."""
    try:
        d0, d1 = dt.date.fromisoformat(a), dt.date.fromisoformat(b)
    except (TypeError, ValueError):
        return 0
    n, d = 0, d0
    while d <= d1:
        n += d.weekday() < 5
        d += dt.timedelta(days=1)
    return n


def level(p):
    return None if p is None else "bad" if p < 5 else "warn" if p < 10 else "good"


def compare(B, trades, start, today, band="H2", label="Live", session_over=True):
    """trades: [{"day", "r", "usd"}] since start (finished trades). today: the trading day now. -> the card's facts."""
    if not B or band not in (B.get("bands") or {}):
        return None
    Bn = B["bands"][band]
    T = sorted([t for t in trades if t.get("day") and t["day"] >= start and t.get("r") is not None], key=lambda t: (t["day"], t.get("t") or 0))
    n_s = sessions_between(start, today) - (0 if session_over else 1)
    n_s = max(n_s, len({t["day"] for t in T}))          # a session with a finished trade counts even before 16:05
    if n_s <= 0:
        return {"label": label, "band": band, "start": start, "sessions": 0, "trades": 0, "level": None,
                "text": f"{label}: no session finished since {start} yet."}
    n_s_c = min(n_s, B["n_max"])
    R = round(sum(float(t["r"]) for t in T), 2)
    usd = round(sum(float(t.get("usd") or 0) for t in T), 2)
    pr = pct_of(Bn["r"][n_s_c - 1], R)
    pu = pct_of(Bn["usd_eval"][n_s_c - 1], usd) if any(t.get("usd") is not None for t in T) else None
    pn = pct_of(Bn["n"][n_s_c - 1], len(T))
    br = band_at(Bn, n_s_c, "r")
    bu = band_at(Bn, n_s_c, "usd_eval")
    bn = band_at(Bn, n_s_c, "n")
    # the current losing streak and how common it is in 20 trades
    st = 0
    for t in reversed(T):
        if float(t["r"]) < 0:
            st += 1
        else:
            break
    lv = level(pr)
    head = (f"{label} is inside the expected range (p{pr:.0f})" if lv == "good" else
            f"{label} is at the low end of the range (p{pr:.0f}): watch" if lv == "warn" else
            f"{label} is below p5 (p{pr:.0f}): investigate")
    if not T:
        head = f"{label}: no trade in {n_s} session{'s' if n_s != 1 else ''} (p{pn:.0f} for trade count)"
        lv = level(pn)
    return {"label": label, "band": band, "start": start, "sessions": n_s, "trades": len(T), "r": R, "usd": usd,
            "pct_r": pr, "pct_usd": pu, "pct_n": pn, "level": lv, "band_r": br, "band_usd": bu, "band_n": bn,
            "streak": st, "p_streak": (Bn.get("p_streak20") or {}).get(str(st)) if st else None,
            "text": head, "detail": (f"{len(T)} trades in {n_s} sessions, {R:+.1f}R / {usd:+,.0f} $. Expected after {n_s} sessions "
                                     f"(90% band, {band}): {br['p5']:+.1f}R to {br['p95']:+.1f}R, median {br['p50']:+.1f}R; "
                                     f"{bn['p5']:.0f}-{bn['p95']:.0f} trades.")}


def from_state(st, journal=None, start=None):
    """Paper (cloud ledger) and live (the PC's routed trades) trade lists from the cloud state / the PC journal."""
    st = st or {}
    paper, live = [], []
    for k, v in (st.get("ledger") or {}).items():
        if not isinstance(v, dict) or v.get("taken") is False or not v.get("exit") or v.get("exit") == "OPEN":
            continue
        paper.append({"day": v.get("day"), "t": int(k) if str(k).isdigit() else 0, "r": v.get("R"), "usd": v.get("usd")})
    acct = ((st.get("pc") or {}).get("acct") or {}) if isinstance(st.get("pc"), dict) else {}
    seen = set()
    for t in acct.get("trades") or []:
        if t.get("entry_t") and t.get("exit"):
            seen.add(int(t["entry_t"]))
            live.append({"day": t.get("day"), "t": int(t["entry_t"]), "r": t.get("r"), "usd": t.get("pnl")})
    for r in journal or []:
        if r.get("source") == "pc" and r.get("entry_t") and r.get("exit") and int(r["entry_t"]) not in seen:
            live.append({"day": r.get("day"), "t": int(r["entry_t"]), "r": r.get("r"), "usd": r.get("pnl")})
    return paper, live


def card(B, st=None, journal=None, now=None, start=None):
    """Both comparisons (paper, live) on the H2 band and the 2026 band + the cone for the equity chart."""
    if not B:
        return None
    import time as _t
    from zoneinfo import ZoneInfo
    now = int(now or _t.time())
    et = dt.datetime.fromtimestamp(now, ZoneInfo("America/New_York"))
    today = (et + dt.timedelta(hours=6)).date().isoformat()
    over = et.hour * 60 + et.minute >= 16 * 60 + 5 or et.weekday() >= 5
    start = start or ((st or {}).get("lit_sizing_start") or B.get("lit_start") or LIT_START)
    paper, live = from_state(st, journal)
    out = {"v": VERSION, "start": start, "today": today, "built": B.get("built"),
           "bands": {k: {kk: v[kk] for kk in ("from", "to", "sessions", "trades", "r_per_session", "usd_eval_per_session",
                                               "trades_per_week")} for k, v in B["bands"].items()}}
    for lab, T in (("paper", paper), ("live", live)):
        out[lab] = compare(B, T, start, today, "H2", "Paper" if lab == "paper" else "Live", over) if (T or (lab == "paper" and st is not None)) else None
        if out[lab] is not None:
            out[lab]["vs_2026"] = (compare(B, T, start, today, "2026", lab, over) or {}).get("pct_r")
            cum, eq = 0.0, []
            for t in sorted([t for t in T if t.get("day") and t["day"] >= start], key=lambda t: (t["day"], t.get("t") or 0)):
                cum += float(t.get("usd") or 0)
                eq.append([sessions_between(start, t["day"]), t["day"], round(cum, 2)])
            out[lab]["equity"] = eq
    main_ = out.get("live") if out.get("live") and out["live"].get("trades") else out.get("paper")
    out["headline"] = (main_ or {}).get("text")
    out["level"] = (main_ or {}).get("level")
    ns = max([(out.get(k) or {}).get("sessions") or 0 for k in ("paper", "live")] + [10])
    out["cone"] = cone(B["bands"]["H2"], min(B["n_max"], ns + 5), "usd_eval")
    out["cone_r"] = cone(B["bands"]["H2"], min(B["n_max"], ns + 5), "r")
    return out


def main(argv):
    if argv and argv[0] == "build":
        b = build()
        for k, v in b["bands"].items():
            print(k, {kk: v[kk] for kk in ("from", "to", "sessions", "trades", "r_per_session", "usd_eval_per_session", "trades_per_week")})
        print("->", OUT)
        return 0
    B = load()
    if not B:
        print("no band: python -m engine.health_band build")
        return 1
    for k, Bn in B["bands"].items():
        for n in (5, 10, 20, 40):
            r, u, c = band_at(Bn, n, "r"), band_at(Bn, n, "usd_eval"), band_at(Bn, n, "n")
            print(f"{k} {n:2d} sessions: R {r['p5']:+.1f}..{r['p95']:+.1f} (p50 {r['p50']:+.1f}) $eval {u['p5']:+,.0f}..{u['p95']:+,.0f} trades {c['p5']:.0f}-{c['p95']:.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
