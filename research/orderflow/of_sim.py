"""Synthetic NQ tick simulator with KNOWN planted order-flow effects (research/orderflow/DESIGN3.md, pipeline proof).
Synthetic only: never writes to data/, never trades. Used to prove, before real tick days arrive, that the whole chain works:
ticks -> engine/ofsum summaries -> battery (OF1-OF6) -> v3 features -> of_forward (idea mill `of` grammar) -> of_learn -> journal
-> the Brain's Order Flow room.

The world (per ET calendar day, 00:00-17:00 + 18:00-24:00, ~75k trades):
- price = a random walk in ticks driven by the aggressive flow (Kyle-style linear impact: half the per-second variance comes from
  the signed volume) plus noise; RTH is busier and more volatile than Globex.
- trade signs persist (metaorder splitting: the next trade has the same sign with probability 0.70), NQ-like size mix, real quotes
  (buys at the ask, sells at the bid -> quote-rule sides).
- 3 SWEEP episodes a day (10:00-14:30 ET): price pushes beyond the last hour's high (-> short signal) or low (-> long), the 5m bar
  closes back inside. Two kinds, 50/50:
    absorbed  - at the extreme, aggressive orders keep hitting INTO it (4x the trade rate, 85% with the push) but price does not
                move (a hidden passive order eats them). planted: afterwards price drifts AGAINST the push (the fade wins).
    thin      - the extreme is a quick poke on normal, two-sided flow. planted: afterwards price drifts WITH the push (the fade loses).
  mode="null": the same episodes, but the drift direction is a coin flip (order flow tells nothing).
- depth=True: top-10 snapshots every 5 s in RTH with a planted best-queue imbalance that predicts the NEXT few seconds only.
Signals handed to the battery / learner: LIT-like trades at every episode (te = sweep bar, tn = entry bar, pnl from the bars with
of_study._sim_df: next open, stop 1 tick beyond the sweep bar, 2R, flat 15:55) and ATLAS-like trades (the same episodes, R x $250,
plus as many random no-edge entries).
    python -X utf8 research/orderflow/of_sim.py --days 50 [--null]
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
TICK = 0.25
P_SAME = 0.70
EPISODES = 3


def _mod(path, name):
    sp = importlib.util.spec_from_file_location(name, os.path.join(HERE, path))
    m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
    return m


def _et0(day: str) -> int:
    return int(pd.Timestamp(day + " 00:00", tz="America/New_York").tz_convert("UTC").value // 10**9)


def simulate_day(day: str, p0: int, rng: np.random.Generator, mode: str = "planted", depth: bool = False):
    """-> (ticks DataFrame in engine.tickrec columns, depth DataFrame or None, episodes [dict], last price in ticks)."""
    T = 24 * 3600
    sec = np.arange(T)
    mod = sec // 60
    rth = (mod >= 570) & (mod < 960)
    live = (mod < 1020) | (mod >= 1080)                                   # 17:00-18:00 halt
    rate = np.where(rth, 2.6, 0.35) * live
    sd = np.where(rth, 1.5, 0.45)
    bias = np.zeros(T)                                                    # P(buy) - 0.5 per second (episodes)
    path_override = {}
    eps = []
    # draw episode times first (bar-aligned), so the base walk can be built once
    starts = sorted(rng.choice(np.arange(600, 870, 5), size=EPISODES, replace=False) * 60)
    starts = [s for k, s in enumerate(starts) if k == 0 or s - starts[k - 1] >= 3600][:EPISODES]
    n_sec = rng.poisson(rate)
    for s in starts:
        kind = "absorbed" if rng.random() < 0.5 else "thin"
        t1, t2, t3 = s + 140, s + 210, s + 285
        if kind == "absorbed":
            n_sec[t1:t2] = rng.poisson(10.0, t2 - t1)
        eps.append({"t0": int(s), "t1": t1, "t2": t2, "t3": t3, "kind": kind})
    # signs: persistent Markov chain, then episode bias at the extreme
    N = int(n_sec.sum())
    owner = np.repeat(sec, n_sec)
    flip = rng.random(N) > P_SAME
    sign = np.where(np.cumsum(flip) % 2 == 0, 1, -1) * (1 if rng.random() < 0.5 else -1)
    size = np.where(rng.random(N) < 0.86, rng.integers(1, 4, N), np.minimum(200, (rng.pareto(1.6, N) * 4 + 4).astype(int)))
    # base walk: impact of each second's signed volume + noise
    sv = np.bincount(owner, weights=sign * size, minlength=T)
    sv_sd = np.sqrt(np.maximum(1.0, rate * 9.0))
    dp = sd * (0.70 * sv / sv_sd + 0.70 * rng.standard_normal(T)) * live
    p = p0 + np.cumsum(dp)
    for e in eps:
        s, t1, t2, t3 = e["t0"], e["t1"], e["t2"], e["t3"]
        d_push = 1 if rng.random() < 0.5 else -1                         # +1: sweep a high (fade = short)
        win = p[max(0, s - 3600):s]
        level = (win.max() if d_push == 1 else win.min())
        if abs(level - p[s]) > 80:                                        # too far: sweep from here instead
            level = p[s] + d_push * rng.integers(20, 40)
        over = rng.integers(8, 20)
        back = rng.integers(14, 30)
        ext = level + d_push * over
        seg = np.r_[np.linspace(p[s], ext, t1 - s, endpoint=False),
                    ext + rng.normal(0, 0.6, t2 - t1) * (0.3 if e["kind"] == "absorbed" else 1.0),
                    np.linspace(ext, level - d_push * back, t3 - t2)]
        shift = seg[-1] - p[t3 - 1]
        p[s:t3] = seg
        p[t3:] += shift
        # post-sweep drift over the next 10 minutes
        if mode == "null":
            fade_wins = rng.random() < 0.5
        else:
            fade_wins = (e["kind"] == "absorbed") if rng.random() < 0.85 else (e["kind"] != "absorbed")
        risk = over + back
        drift = (-d_push if fade_wins else d_push) * 3.0 * risk
        L = 10 * 60
        ramp = np.linspace(0, drift, L)
        p[t3:t3 + L] += ramp
        p[t3 + L:] += drift
        # flow: into the extreme with the push during the push; at the extreme 85% with the push if absorbed
        bias[s:t1] = 0.20 * d_push
        bias[t1:t2] = 0.35 * d_push if e["kind"] == "absorbed" else 0.0
        bias[t2:t3] = -0.10 * d_push
        e.update(d_push=int(d_push), level=float(level), ext=float(ext), fade_wins=bool(fade_wins))
    # apply episode bias to the signs (redraw signs where |bias| > 0)
    b_tr = bias[owner]
    m = b_tr != 0
    sign[m] = np.where(rng.random(int(m.sum())) < 0.5 + b_tr[m], 1, -1)
    bid = np.floor(p).astype(np.int64)
    btr = bid[owner]
    price_t = np.where(sign > 0, btr + 1, btr)
    t_ns = (np.int64(_et0(day)) + owner).astype(np.int64) * 10**9 + rng.integers(0, 10**9, N)
    o = np.argsort(t_ns, kind="stable")
    ticks = pd.DataFrame({"t_ns": t_ns[o], "root": "NQ", "price": price_t[o] * TICK, "size": size[o].astype(np.int64),
                          "bid": btr[o] * TICK, "ask": (btr[o] + 1) * TICK, "side": sign[o].astype(np.int8)})
    dp_df = _depth(day, bid, sec, rth, rng) if depth else None
    return ticks, dp_df, eps, int(bid[-1])


def _depth(day, bid, sec, rth, rng):
    """Top-10 snapshots every 5 s in RTH; the best-queue imbalance leans toward the next 10 s move (seconds-only effect)."""
    ts = sec[rth][::5]
    nxt = bid[np.minimum(ts + 10, len(bid) - 1)] - bid[ts]
    n = len(ts)
    base = rng.integers(5, 25, (n, 10)).astype(np.int32)
    lean = np.clip(nxt, -3, 3)
    bs = base.copy(); as_ = rng.integers(5, 25, (n, 10)).astype(np.int32)
    bs[:, 0] = np.maximum(1, bs[:, 0] + (lean > 0) * 25); as_[:, 0] = np.maximum(1, as_[:, 0] + (lean < 0) * 25)
    out = {"t_ms": (np.int64(_et0(day)) + ts) * 1000, "bp": bid[ts] * TICK}
    for k in range(1, 11):
        out[f"bd{k}"] = np.full(n, k - 1, np.int32)
    for k in range(1, 11):
        out[f"bs{k}"] = bs[:, k - 1]
    for k in range(1, 11):
        out[f"ad{k}"] = np.full(n, k, np.int32)
    for k in range(1, 11):
        out[f"as{k}"] = as_[:, k - 1]
    return pd.DataFrame(out)


def world(n_days: int = 50, mode: str = "planted", depth_last: int = 0, seed: int = 7, start: str = "2026-09-14"):
    """n_days of summaries + signals. -> {"R": {day: summary dict as of_battery._from_bytes}, "lit": [...], "atlas": [...],
    "episodes": {day: [...]}}"""
    from engine import ofsum
    B = _mod("of_battery.py", "of_battery_sim")
    rng = np.random.default_rng(seed)
    days = [d.strftime("%Y-%m-%d") for d in pd.bdate_range(start, periods=n_days)]
    R, metas, EP = {}, {}, {}
    p = 80_000
    for k, d in enumerate(days):
        x, dp, eps, p = simulate_day(d, p, rng, mode, depth=k >= n_days - depth_last)
        files = ofsum.summarize(x, d, ofsum.block_threshold(d, metas=metas))
        R[d] = B._from_bytes(files)
        R[d]["depth"] = ofsum.depth_summary(dp) if dp is not None else None
        metas[d] = R[d]["meta"]
        EP[d] = eps
    lit, atlas = signals(R, EP, rng, B)
    return {"R": R, "lit": lit, "atlas": atlas, "episodes": EP, "days": days}


def signals(R, EP, rng, B):
    lit, atlas = [], []
    for d, eps in EP.items():
        D = B.Day(d, R[d])
        rth = D.rth()
        t_rth = {int(t): j for j, t in enumerate(rth.t)}
        for e in eps:
            tb = _et0(d) + e["t0"]
            tb -= tb % 300
            j = t_rth.get(int(tb))
            if j is None or j + 1 >= len(rth):
                continue
            dd = -e["d_push"]
            pnl = B.S._sim_df(rth, j, dd)
            if pnl is None:
                continue
            te, tn = int(rth.at[j, "t"]), int(rth.at[j + 1, "t"])
            lit.append({"day": d, "dir": dd, "pnl": float(pnl), "te": te, "tn": tn, "kind": e["kind"]})
            entry = rth.at[j + 1, "open"]; stop = rth.at[j, "low"] - TICK if dd == 1 else rth.at[j, "high"] + TICK
            risk = abs(entry - stop)
            atlas.append({"day": d, "entry_t": tn, "dir": dd, "pnl": float(pnl) / 500 * 250, "R": float(pnl) / 500, "kind": e["kind"],
                          "risk": float(risk)})
        for _ in range(len(eps)):                                          # no-edge ATLAS entries
            j = int(rng.integers(12, max(13, len(rth) - 12)))
            dd = int(rng.choice([-1, 1]))
            pnl = B.S._sim_df(rth, j, dd)
            if pnl is not None:
                atlas.append({"day": d, "entry_t": int(rth.at[j + 1, "t"]), "dir": dd, "pnl": float(pnl) / 2, "R": float(pnl) / 500, "kind": "random"})
    return lit, atlas


def describe(W) -> dict:
    lit = W["lit"]
    by = {}
    for t in lit:
        k = by.setdefault(t["kind"], [0, 0, 0.0])
        k[0] += 1; k[1] += t["pnl"] > 0; k[2] += t["pnl"]
    return {k: {"n": v[0], "won": v[1], "net": round(v[2])} for k, v in by.items()}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=20); ap.add_argument("--null", action="store_true")
    a = ap.parse_args()
    W = world(a.days, "null" if a.null else "planted", depth_last=5)
    rows = [W["R"][d]["meta"]["rows"] for d in W["days"]]
    print("days", len(rows), "trades/day", int(np.mean(rows)), "LIT signals", len(W["lit"]), describe(W))
