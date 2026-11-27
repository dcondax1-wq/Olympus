"""Order flow v4 (night-of-features 2026-11-27): seven more tick features, rules frozen in research/orderflow/DESIGN_v4.md
(committed before this script). Research only, paper: imports nothing that can trade, changes no bot, size or setting.

Each feature V1-V7 is measured (a) as a filter on Zlarior's LIT replay trades inside the pulled tick days, (b) as a filter on
the pillar's lane A level-fade candidates, (c) as a standalone 30-minute signal; label-shuffle / sign-flip placebo, Holm over
the tests that reach their floor, both halves of the days. -> v4_results.json + v4_verdict.md (+ the LEAD_WIRES ranking).

    python -X utf8 research/orderflow/of_v4.py            # the pulled days (data/pc_days, logs/datapipe/days)
    python -X utf8 research/orderflow/of_v4.py --selftest
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import importlib.util
import io
import json
import os
import sys
import zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
OUT_J = os.path.join(HERE, "v4_results.json")
OUT_MD = os.path.join(HERE, "v4_verdict.md")
TICK, USD_TICK, COMM = 0.25, 0.50, 1.40
N_PERM, P_BAR = 5000, 0.10
FLOOR = {"LIT": 20, "laneA": 40, "alone": 40}
IMB_RATIO, IMB_MIN, STACK = 3.0, 10.0, 3
AS_BAR, BLOCK_SHARE, SLOPE_BAR, VWAP_ATR, HOLD = 1.5, 0.10, 0.10, 1.0, 6
NAMES = {"V1": "Stacked imbalances", "V2": "Delta divergence at the extreme", "V3": "Absorption strength (volume vs range)",
         "V4": "Large-lot prints", "V5": "Delta slope into entry", "V6": "VWAP location", "V7": "First-15-minute delta"}
COST = {"V1": "medium (per-price buckets of one bar)", "V2": "cheap (running CVD + 12-bar extreme)",
        "V3": "medium (bar volume / range, 12-bar median)", "V4": "cheap (signed sum of big prints)",
        "V5": "cheap (3-bar delta sum)", "V6": "cheap (running price x volume sum)", "V7": "cheap (one delta sum at 09:45)"}
FEATS = list(NAMES)
FORWARD_FROM = "2026-11-27"                  # DESIGN_v4 addendum: the forward watch list W1-W4, days from here only
WATCH = {"W1": ("V7", "taken"), "W2": ("V6", "alone"), "W3": ("V5", "laneA"), "W4": ("V3", "laneA")}


def _mod(name):
    sp = importlib.util.spec_from_file_location(f"v4_{name}", os.path.join(HERE, name + ".py"))
    m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
    return m


# ------------------------------------------------------------------------------------------------ per-day arrays
class DayF:
    """The arrays one day's features need, from of_battery.Day."""

    def __init__(self, Dy):
        b = Dy.bars
        self.day = Dy.day
        self.t = b.t.to_numpy(np.int64)
        self.o, self.h, self.l, self.c = (b[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        self.v = b.volume.to_numpy(float)
        self.dl = b.delta.to_numpy(float)
        self.mod = b["mod"].to_numpy(int)
        self.cvd = np.cumsum(self.dl)
        try:
            bt = b["bth"].astype(float).to_numpy() if "bth" in b else np.full(len(b), np.nan)
        except (TypeError, ValueError):
            bt = np.full(len(b), np.nan)
        self.blk = bt if np.isfinite(bt).any() else b["b20"].astype(float).to_numpy()
        self.blk = np.nan_to_num(self.blk)
        self.row_of_t = Dy.row_of_t
        n = len(b)
        self.stk_b, self.stk_s = np.zeros(n), np.zeros(n)
        self.pv, self.vv = np.zeros(n), np.zeros(n)              # footprint price x volume, volume (VWAP)
        for i, g in Dy.fp_by_bar.items():
            if i >= n:
                continue
            k = g.k.to_numpy(int); a = g.a.to_numpy(float); bb = g.b.to_numpy(float); u = g.u.to_numpy(float)
            vol = a + bb + u
            px = self.l[i] + k * TICK
            self.pv[i] = float((px * vol).sum()); self.vv[i] = float(vol.sum())
            self.stk_b[i], self.stk_s[i] = stacks(k, a, bb)
        rg = np.maximum(np.round((self.h - self.l) / TICK), 1.0)
        self.dens = self.v / rg
        tr = self.h - self.l
        self.atr = np.array([tr[max(0, i - 12):i].mean() if i >= 6 else np.nan for i in range(n)])

    def closed_before(self, t_entry):
        """Index of the last 5m bar closed at / before t_entry (None if none)."""
        j = int(np.searchsorted(self.t + 300, t_entry, side="right")) - 1
        return j if j >= 0 else None

    def vwap(self, i):
        if self.mod[i] >= 585:
            a = np.nonzero(self.mod >= 570)[0]
            a0 = int(a[0]) if len(a) else 0
        else:
            a0 = 0
        vv = self.vv[a0:i + 1].sum()
        return self.pv[a0:i + 1].sum() / vv if vv > 0 else np.nan


def stacks(k, a, b):
    """(buy stacks, sell stacks) of one bar's footprint: diagonal 3:1 imbalances (>= 10 contracts), runs of >= 3 ticks."""
    if not len(k):
        return 0, 0
    lo, hi = int(k.min()), int(k.max())
    A = np.zeros(hi - lo + 2); Bv = np.zeros(hi - lo + 2)
    np.add.at(A, k - lo, a); np.add.at(Bv, k - lo, b)
    n = hi - lo + 1
    bi = np.zeros(n, bool); si = np.zeros(n, bool)
    for x in range(n):
        below = Bv[x - 1] if x >= 1 else 0.0
        above = A[x + 1] if x + 1 < n else 0.0
        bi[x] = A[x] >= IMB_MIN and A[x] >= IMB_RATIO * below and x >= 1
        si[x] = Bv[x] >= IMB_MIN and Bv[x] >= IMB_RATIO * above and x + 1 < n
    return _runs(bi), _runs(si)


def _runs(m):
    out, r = 0, 0
    for v in list(m) + [False]:
        if v:
            r += 1
        else:
            out += 1 if r >= STACK else 0
            r = 0
    return out


# ------------------------------------------------------------------------------------------------ the 7 reads at one trade
def reads(F: DayF, i: int, d: int, t_entry: int) -> dict:
    """{V1..V7: True / False / None} for a trade in direction d whose sweep (reference) bar is i, entered at t_entry."""
    out = {k: None for k in FEATS}
    if i is None or F.t[i] + 300 > t_entry:
        ref_ok = False
    else:
        ref_ok = True
    if ref_ok:
        s1 = d * (F.stk_b[i] - F.stk_s[i])
        out["V1"] = bool(s1 > 0)
        if i >= 12:
            w = slice(i - 12, i)
            j = (i - 12 + int(np.argmin(F.l[w]))) if d == 1 else (i - 12 + int(np.argmax(F.h[w])))
            new = F.l[i] < F.l[j] if d == 1 else F.h[i] > F.h[j]
            if new:
                out["V2"] = bool(F.cvd[i] > F.cvd[j]) if d == 1 else bool(F.cvd[i] < F.cvd[j])
            med = float(np.median(F.dens[w]))
            if med > 0:
                out["V3"] = bool(F.dens[i] / med >= AS_BAR)
        s4 = d * (F.blk[i] + (F.blk[i - 1] if i >= 1 else 0.0))
        out["V4"] = None if s4 == 0 else bool(s4 > 0)
        vw = F.vwap(i)
        if np.isfinite(vw):
            out["V6"] = bool(d * (vw - F.c[i]) > 0)
    j = F.closed_before(t_entry)
    if j is not None and j >= 2:
        sv = F.v[j - 2:j + 1].sum()
        if sv > 0:
            out["V5"] = bool(d * F.dl[j - 2:j + 1].sum() / sv > 0)
    idx = [int(x) for x in np.nonzero((F.mod >= 570) & (F.mod < 585))[0]]
    if len(idx) == 3 and F.t[idx[-1]] + 300 <= t_entry:
        sv = F.v[idx].sum()
        if sv > 0:
            out["V7"] = bool(d * F.dl[idx].sum() / sv > 0)
    return out


# ------------------------------------------------------------------------------------------------ standalone signals
def signals(F: DayF) -> dict:
    """{V: [(i_signal, d)]}: the standalone events of DESIGN_v4 (c), one position at a time per feature."""
    n = len(F.t)
    raw = {k: [] for k in FEATS}
    for i in range(n):
        if i + 7 >= n:
            continue
        if F.mod[i] == 580:                                   # the 09:40 bar closes at 09:45: enter at the 09:45 open
            idx = [int(x) for x in np.nonzero((F.mod >= 570) & (F.mod < 585))[0]]
            if len(idx) == 3 and F.dl[idx].sum() != 0:
                raw["V7"].append((i, int(np.sign(F.dl[idx].sum()))))
        if not (585 <= F.mod[i] <= 900):
            continue
        if F.stk_b[i] > 0 and F.stk_s[i] == 0:
            raw["V1"].append((i, 1))
        elif F.stk_s[i] > 0 and F.stk_b[i] == 0:
            raw["V1"].append((i, -1))
        if i >= 12:
            w = slice(i - 12, i)
            jl = i - 12 + int(np.argmin(F.l[w])); jh = i - 12 + int(np.argmax(F.h[w]))
            nl, nh = F.l[i] < F.l[jl], F.h[i] > F.h[jh]
            if nl and not nh and F.cvd[i] > F.cvd[jl]:
                raw["V2"].append((i, 1))
            elif nh and not nl and F.cvd[i] < F.cvd[jh]:
                raw["V2"].append((i, -1))
            med = float(np.median(F.dens[w]))
            l6, h6 = F.l[i] < F.l[i - 6:i].min(), F.h[i] > F.h[i - 6:i].max()
            if med > 0 and F.dens[i] / med >= AS_BAR and l6 != h6:
                raw["V3"].append((i, 1 if l6 else -1))
        if F.v[i] > 0 and abs(F.blk[i]) >= BLOCK_SHARE * F.v[i]:
            raw["V4"].append((i, int(np.sign(F.blk[i]))))
        if i >= 2:
            sv = F.v[i - 2:i + 1].sum()
            sl = F.dl[i - 2:i + 1].sum() / sv if sv > 0 else 0.0
            if abs(sl) >= SLOPE_BAR:
                raw["V5"].append((i, int(np.sign(sl))))
        vw = F.vwap(i)
        if np.isfinite(vw) and np.isfinite(F.atr[i]) and F.atr[i] > 0 and i >= 1:
            dev, dev0 = F.c[i] - vw, F.c[i - 1] - F.vwap(i - 1)
            if abs(dev) >= VWAP_ATR * F.atr[i] and not (abs(dev0) >= VWAP_ATR * F.atr[i] and np.sign(dev0) == np.sign(dev)):
                raw["V6"].append((i, -int(np.sign(dev))))
    out = {}
    for k, ev in raw.items():
        keep, nxt = [], -1
        for i, d in ev:
            if d == 0 or i < nxt:
                continue
            if F.t[i + 1 + HOLD] - F.t[i + 1] != 300 * HOLD:      # a gap in the bars: no clean 30 minutes
                continue
            keep.append((i, d)); nxt = i + HOLD
        out[k] = keep
    return out


def alone_trade(F, i, d):
    g = (F.o[i + 1 + HOLD] - F.o[i + 1]) * d / TICK * USD_TICK      # gross $ at 1 micro, no slippage
    return g


# ------------------------------------------------------------------------------------------------ scoring
def filt_score(y, usd, lab, day, half, seed, floor):
    """y = outcome for the test (R or $), usd = $ shown; lab = True / False / None per row."""
    y = np.asarray(y, float); usd = np.asarray(usd, float)
    comp = np.array([x is not None for x in lab], bool)
    ps = np.array([bool(x) for x in lab], bool)
    kept = ps | ~comp
    o = {"rows": int(len(y)), "with_read": int(comp.sum()), "need": floor, "kept": int(kept.sum()),
         "kept_share": round(float(kept.mean()), 3) if len(y) else None,
         "all_usd": round(float(usd.sum()), 2), "kept_usd": round(float(usd[kept].sum()), 2),
         "kept_mean_usd": round(float(usd[kept].mean()), 2) if kept.any() else None,
         "skip_usd": round(float(usd[~kept].sum()), 2)}
    o["gain"] = round(float(y[kept].mean() - y[~kept].mean()), 3) if kept.any() and (~kept).any() else None
    yc, pc = y[comp], ps[comp]
    if pc.sum() and (~pc).sum():
        obs = yc[pc].mean() - yc[~pc].mean()
        rng = np.random.default_rng(seed)
        k, n = int(pc.sum()), len(yc)
        tot = yc.sum()
        hits = 0
        for _ in range(N_PERM):
            m = rng.choice(n, k, replace=False)
            s = yc[m].sum()
            hits += (s / k - (tot - s) / (n - k)) >= obs - 1e-12
        o["p"] = round((hits + 1) / (N_PERM + 1), 4)
    else:
        o["p"] = None
    hv = []
    for m in (np.array([x <= half for x in day]), np.array([x > half for x in day])):
        a, b = y[kept & m], y[~kept & m]
        hv.append(round(float(a.mean() - b.mean()), 3) if len(a) and len(b) else None)
    o["halves_gain"] = hv
    o["reached_floor"] = bool(comp.sum() >= floor and pc.sum() and (~pc).sum())
    return o


def alone_score(g, day, half, seed, n_days):
    g = np.asarray(g, float)
    cost = 2 * USD_TICK + COMM
    o = {"trades": int(len(g)), "need": FLOOR["alone"], "per_week": round(len(g) / max(n_days / 5, 1e-9), 1)}
    if not len(g):
        o.update(p=None, reached_floor=False, halves_mean_usd=[None, None])
        return o
    net = g - cost
    o.update(mean_usd=round(float(net.mean()), 2), net_usd=round(float(net.sum()), 2),
             usd_month=round(float(net.sum()) / max(n_days / 21, 1e-9), 0), won=round(100 * float((net > 0).mean()), 1),
             pf=round(float(net[net > 0].sum() / -net[net < 0].sum()), 2) if (net < 0).any() else None)
    cum = np.cumsum(net); o["max_dd"] = round(float((np.maximum.accumulate(np.r_[0, cum]) - np.r_[0, cum]).max()), 2)
    rng = np.random.default_rng(seed)
    obs = g.mean()
    flips = rng.choice((-1.0, 1.0), size=(N_PERM, len(g)))
    o["p"] = round(float(((flips @ g) / len(g) >= obs - 1e-12).sum() + 1) / (N_PERM + 1), 4)
    hv = []
    for m in (np.array([x <= half for x in day]), np.array([x > half for x in day])):
        hv.append(round(float(net[m].mean()), 2) if m.any() else None)
    o["halves_mean_usd"] = hv
    o["reached_floor"] = bool(len(g) >= FLOOR["alone"])
    return o


def holm(tests):
    """tests: [(key, p)] reaching floor -> {key: adjusted p}."""
    tests = sorted(tests, key=lambda x: x[1])
    m, out, run = len(tests), {}, 0.0
    for j, (k, p) in enumerate(tests):
        run = max(run, min(1.0, (m - j) * p))
        out[k] = round(run, 4)
    return out


# ------------------------------------------------------------------------------------------------ run
def run(src=None, write=True, say=print):
    B = _mod("of_battery")
    from engine import ofsum, of_paper as P
    from tools.of_realday_verdict import day_dirs
    dirs = day_dirs(src)
    R = {d: ofsum.read(p) for d, p in dirs.items()}
    R = {d: x for d, x in R.items() if x}
    days = sorted(d for d, x in R.items() if int(x["meta"].get("rows", 0)) >= B.MIN_ROWS)
    if not days:
        say("v4: no order-flow day here: python -X utf8 tools/data_pull.py --of --no-battery")
        return {}
    half = days[(len(days) + 1) // 2 - 1]
    D = {d: B.Day(d, R[d]) for d in days}
    F = {d: DayF(D[d]) for d in days}
    out = {"made": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "design": "research/orderflow/DESIGN_v4.md",
           "tick_days": len(days), "first": days[0], "last": days[-1], "half_split_after": half, "tests": {}}
    # (b) lane A candidates
    rows = []
    for k, d in enumerate(days):
        prev = days[k - 1] if k and (dt.date.fromisoformat(d) - dt.date.fromisoformat(days[k - 1])).days <= 4 else None
        with contextlib.redirect_stdout(io.StringIO()):
            S = P.replay_summary(R[d], d, R[prev] if prev else None, prev, lit=[])
        for r in S["rows"]:
            if r.get("R") is None:
                continue
            i = F[d].row_of_t.get(int(r["t_sig"]))
            rows.append({"day": d, "d": r["d"], "R": r["R"], "usd": r["usd_1"], "taken": bool(r.get("taken")),
                         "rd": reads(F[d], i, r["d"], int(r["t_sig"]) + 300)})
    out["laneA_rows"] = len(rows)
    # (a) LIT replay trades in the tick days
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            lit, bars_to = B.lit_trades()
    except Exception as e:  # noqa: BLE001
        lit, bars_to = [], f"unavailable ({e.__class__.__name__})"
    out["lit_bars_to"] = bars_to
    lrows = []
    for t in lit:
        ed = B.et_day(t["te"])
        if ed not in F:
            continue
        i = F[ed].row_of_t.get(int(t["te"]) // 300 * 300)
        lrows.append({"day": ed, "d": t["dir"], "usd": float(t["pnl"]), "rd": reads(F[ed], i, t["dir"], int(t["tn"]))})
    out["lit_rows"] = len(lrows)
    # (c) standalone
    ev = {k: [] for k in FEATS}
    for d in days:
        for k, lst in signals(F[d]).items():
            ev[k] += [(d, alone_trade(F[d], i, s)) for i, s in lst]
    T = out["tests"]
    for v in FEATS:
        sd = zlib.crc32(v.encode())
        T[f"{v}.LIT"] = filt_score([r["usd"] for r in lrows], [r["usd"] for r in lrows], [r["rd"][v] for r in lrows],
                                   [r["day"] for r in lrows], half, sd + 1, FLOOR["LIT"])
        T[f"{v}.laneA"] = filt_score([r["R"] for r in rows], [r["usd"] for r in rows], [r["rd"][v] for r in rows],
                                     [r["day"] for r in rows], half, sd + 2, FLOOR["laneA"])
        tk = [r for r in rows if r["taken"]]
        info = filt_score([r["R"] for r in tk], [r["usd"] for r in tk], [r["rd"][v] for r in tk], [r["day"] for r in tk],
                          half, sd + 3, 10 ** 9)
        T[f"{v}.laneA"]["info_taken_only"] = {k: info[k] for k in ("rows", "with_read", "kept", "kept_usd", "skip_usd", "gain", "halves_gain")}
        T[f"{v}.alone"] = alone_score([g for _d, g in ev[v]], [d for d, _g in ev[v]], half, sd + 4, len(days))
    out["forward"] = forward(rows, ev, days)
    adj = holm([(k, t["p"]) for k, t in T.items() if t.get("reached_floor") and t.get("p") is not None])
    out["holm_m"] = len(adj)
    for k, t in T.items():
        t["p_adj"] = adj.get(k)
        use = k.split(".")[1]
        if not t.get("reached_floor"):
            have = t.get("with_read", t.get("trades", 0))
            t["verdict"] = f"TOO FEW ({have} of {t['need']})"
            continue
        if use == "alone":
            ok = t["p_adj"] < P_BAR and all(h is not None and h > 0 for h in t["halves_mean_usd"]) and t["mean_usd"] > 0
        else:
            ok = (t["p_adj"] < P_BAR and all(h is not None and h > 0 for h in t["halves_gain"]) and (t["kept_share"] or 0) >= 0.30
                  and (t["kept_mean_usd"] or 0) > 0)
        t["verdict"] = "CANDIDATE" if ok else "NO"
    out["ranking"] = rank(T)
    out["verdict_line"] = verdict_line(out)
    say(out["verdict_line"])
    if write:
        with open(OUT_J, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1)
        with open(OUT_MD, "w", encoding="utf-8") as fh:
            fh.write(markdown(out))
    return out


def forward(rows, ev, days):
    """The addendum's watch list W1-W4 on forward days only (>= FORWARD_FROM), Holm over the 4."""
    fd = [d for d in days if d >= FORWARD_FROM]
    o = {"from": FORWARD_FROM, "days": len(fd), "watch": {}}
    if not fd:
        o["line"] = f"forward: 0 tick days from {FORWARD_FROM} yet (watch list W1-W4 waits)"
        return o
    half = fd[(len(fd) + 1) // 2 - 1]
    fr = [r for r in rows if r["day"] >= FORWARD_FROM]
    for w, (v, use) in WATCH.items():
        sd = zlib.crc32(w.encode())
        if use == "alone":
            e = [(d, g) for d, g in ev[v] if d >= FORWARD_FROM]
            t = alone_score([g for _d, g in e], [d for d, _g in e], half, sd, len(fd))
            t["good"] = (t.get("mean_usd") or 0) > 0
        else:
            rr = [r for r in fr if r["taken"]] if use == "taken" else fr
            t = filt_score([r["R"] for r in rr], [r["usd"] for r in rr], [r["rd"][v] for r in rr], [r["day"] for r in rr], half, sd,
                           20 if use == "taken" else FLOOR["laneA"])
            t["good"] = (t.get("gain") or 0) > 0
        o["watch"][w] = {"feature": v, "use": use, **t}
    adj = holm([(w, t["p"]) for w, t in o["watch"].items() if t.get("reached_floor") and t.get("p") is not None])
    for w, t in o["watch"].items():
        t["p_adj"] = adj.get(w)
        t["verdict"] = ("TOO FEW" if not t.get("reached_floor") else
                        "FORWARD PASS" if (t["p_adj"] is not None and t["p_adj"] < P_BAR and t["good"]) else "NO")
    o["line"] = f"forward ({len(fd)} days from {FORWARD_FROM}): " + ", ".join(f"{w} {t['feature']} {t['verdict']}" for w, t in o["watch"].items())
    return o


def rank(T):
    rk = []
    for v in FEATS:
        vs = [T[f"{v}.{u}"] for u in ("LIT", "laneA", "alone")]
        cand = [u for u, t in zip(("LIT", "laneA", "alone"), vs) if t["verdict"] == "CANDIDATE"]
        ps = [t["p"] for t in vs[1:] if t.get("reached_floor") and t.get("p") is not None]
        rk.append({"id": v, "name": NAMES[v], "candidate_in": cand, "best_raw_p": min(ps) if ps else None, "cost": COST[v]})
    rk.sort(key=lambda r: (not r["candidate_in"], r["best_raw_p"] if r["best_raw_p"] is not None else 9, not r["cost"].startswith("cheap")))
    return rk


def verdict_line(o):
    c = [k for k, t in o["tests"].items() if t["verdict"] == "CANDIDATE"]
    return (f"v4 on {o['tick_days']} real tick days ({o['first']}..{o['last']}): {len(c)} of 21 tests CANDIDATE"
            + (f" ({', '.join(c)})" if c else "") + f"; {o['holm_m']} reached their floor (Holm over those).")


def _u(x):
    return "-" if x is None else f"${x:+,.0f}"


def markdown(o):
    T = o["tests"]
    L = ["# Order flow v4: seven more tick features - the verdict", "",
         f"Rules frozen first: `DESIGN_v4.md`. Built by `python -X utf8 research/orderflow/of_v4.py`. Research only, paper.", "",
         f"**Days:** {o['tick_days']} real NQ tick days {o['first']} .. {o['last']} (halves split after {o['half_split_after']}). "
         f"Lane A candidates resolved: {o['laneA_rows']}. LIT replay trades in these days: {o['lit_rows']} (bars to {o['lit_bars_to']}). "
         f"Holm over {o['holm_m']} tests that reached their floor.", "", f"**{o['verdict_line']}**", "",
         "## (b) Filter on lane A (level fade; outcome R, $ at 1 micro, costs in)", "",
         "| feature | with read | kept | kept $ | skipped $ | gain R | halves | p | p adj | verdict |", "|---|---|---|---|---|---|---|---|---|---|"]
    for v in FEATS:
        t = T[f"{v}.laneA"]
        L.append(f"| {v} {NAMES[v]} | {t['with_read']} | {t['kept']} | {_u(t['kept_usd'])} | {_u(t['skip_usd'])} | {t['gain']} | {t['halves_gain']} | {t['p']} | {t['p_adj']} | {t['verdict']} |")
    L += ["", "Inside lane A's TAKEN (absorbed) trades only - information, no p (on top of the absorption gate):", "",
          "| feature | kept | kept $ | skipped $ | gain R | halves |", "|---|---|---|---|---|---|"]
    for v in FEATS:
        t = T[f"{v}.laneA"]["info_taken_only"]
        L.append(f"| {v} {NAMES[v]} | {t['kept']} of {t['rows']} | {_u(t['kept_usd'])} | {_u(t['skip_usd'])} | {t['gain']} | {t['halves_gain']} |")
    L += ["", "Lane A, every candidate as if taken: " + _u(T['V1.laneA']['all_usd']) + " at 1 micro.", "",
          "## (a) Filter on LIT (Zlarior's replay trades, $ at LIT's own size)", "",
          "| feature | with read | kept | all $ | kept $ | gain $ | p | verdict |", "|---|---|---|---|---|---|---|---|"]
    for v in FEATS:
        t = T[f"{v}.LIT"]
        L.append(f"| {v} {NAMES[v]} | {t['with_read']} | {t['kept']} | {_u(t['all_usd'])} | {_u(t['kept_usd'])} | {t['gain']} | {t['p']} | {t['verdict']} |")
    L += ["", "## (c) Standalone 30-minute signal (1 micro, 2 ticks + $1.40 costs)", "",
          "| feature | trades | /week | net $ | $/month | mean $ | won | PF | max DD | halves mean $ | p | p adj | verdict |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for v in FEATS:
        t = T[f"{v}.alone"]
        L.append(f"| {v} {NAMES[v]} | {t['trades']} | {t['per_week']} | {_u(t.get('net_usd'))} | {_u(t.get('usd_month'))} | {t.get('mean_usd')} | "
                 f"{t.get('won')}% | {t.get('pf')} | {'-' if t.get('max_dd') is None else f"${t['max_dd']:,.0f}"} | {t.get('halves_mean_usd')} | {t['p']} | {t['p_adj']} | {t['verdict']} |")
    L += ["", "## Forward watch list (DESIGN_v4 addendum: W1 V7 in taken lane A, W2 V6 standalone, W3 V5 / W4 V3 lane A filters)", "",
          o.get("forward", {}).get("line", "forward: not run")]
    L += ["", "## LEAD_WIRES: which features to log forward on the PC (engine/oflive.py; the lead wires, no engine change here)", ""]
    for n, r in enumerate(o["ranking"], 1):
        L.append(f"{n}. **{r['id']} {r['name']}** - candidate in: {', '.join(r['candidate_in']) or 'none'}; best raw p (lane A / standalone) "
                 f"{r['best_raw_p']}; cost {r['cost']}.")
    L += ["", "Nothing here changes a bot. A CANDIDATE only earns forward logging; the strategy-proof protocol (both 2026 halves "
          "and 2021-25) cannot be met with tick days this short. The lead's wiring list: `LEAD_WIRES_v4.md`.", ""]
    return "\n".join(L)


def selftest():
    k = np.array([0, 1, 2, 3, 4, 5]); a = np.array([0, 40, 40, 40, 1, 1.0]); b = np.array([5, 1, 1, 1, 1, 1.0])
    sb, ss = stacks(k, a, b)
    assert (sb, ss) == (1, 0), (sb, ss)
    assert _runs(np.array([1, 1, 1, 0, 1, 1, 1, 1], bool)) == 2
    assert holm([("x", 0.01), ("y", 0.04)]) == {"x": 0.02, "y": 0.04}
    print("of_v4 selftest ok")
    return True


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=None)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    run(a.src)
