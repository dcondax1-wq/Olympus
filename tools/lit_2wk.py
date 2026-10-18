"""LIT two-week eval (owner order 2026-10-18: "an MFFU eval must be PASSED IN 2 WEEKS (10 sessions) OR LESS. Eventually does
not count. Revamp the eval mode for that.").

Objective: P(pass within 10 sessions) of a fresh MFFU Builder 50K eval ($3,000 target, $2,000 EOD trailing max loss locking at
+$100, $1,000 soft daily loss, max 40 micros) and the cost per 2-week pass = $91.80 / P(pass within 10). An eval not passed by
session 10 counts as a failed purchase. The 25K Builder ($63; $1,500 target, $1,000 max loss, $600 soft daily loss, 2 minis =
20 micros) is scored with every $ of the sizing rule halved.

Trades: the exact live LIT signals at 1 micro (tools/lit_tightstop.trun, stop_mode ext = 1 tick beyond the sweep extreme; the
live LIT settings incl. the Monday rule; trade for trade == run lit_live). Each trade keeps what is known at entry (stop
distance after the fill, target distance, weekly-stop multiplier) and what happens after (points, worst open points), so any
sizing rule can be applied exactly, path by path. Variants of the signal set (lever 3, still LIT):
  live     1 trade a day (the live rule)
  two      a second LIT trade on the same day only when the first was stopped out (a new sweep + inducement + CISD after the
           first exit; the weekly stop recounted on the new set)
  w0       entry window 00:00-15:30 instead of 02:00-15:30 (more of Asia / early London)
  two_w0   both

Sizing (tools/lit_2wk_sizing.py two_week_qty, the function the coordinator can move into engine/sizing.py):
  base     "need" = one winner passes: micros so the trade's target $ covers what is still needed to +$3,000;
           "lit"  = $usd up to a ref-pt stop, then usd x ref / stop (the LIT family: 800/25 = today's eval mode)
  then x the weekly stop (optional), a clock press after session `press_at` (x press_mult), a protect cap once up
  (a full loss may not take the profit below protect_keep x the profit), the room cap (f x room to the floor), the soft daily
  loss cap (a full stop-out incl. 1 tick + commission may not take the day below -$1,000), 40 micros, min 1 micro.

Samples: a fresh eval on every session (real history; H1 starts / H2 starts on that half's sessions only, 2026 on all of
2026) and a 4,000-path Monte Carlo of 20 sessions in blocks of 5 consecutive sessions from the half. Pick on H1, check on H2;
2021-25 (5m entries, no 1m data) is a reference line.

  python tools/lit_2wk.py build      # unit trades of the 4 signal sets -> research/runs/_cache/lit_2wk_unit_*.json (1 process)
  python tools/lit_2wk.py ceiling    # the theoretical ceiling of P(pass in 10)
  python tools/lit_2wk.py grid       # every config -> research/lit/two_week.json (2 processes)
  python tools/lit_2wk.py timing     # start-timing rules on the shortlisted configs
  python tools/lit_2wk.py save       # rl.save the runs lit_2wk_*
Paper only.
"""
from __future__ import annotations

import collections
import datetime as dt
import itertools
import json
import math
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import lit_2wk_sizing as S  # noqa: E402

CACHE = os.path.join(ROOT, "research", "runs", "_cache")
OUT = os.path.join(ROOT, "research", "lit", "two_week.json")
OUT_T = os.path.join(ROOT, "research", "lit", "two_week_timing.json")
OUT_C = os.path.join(ROOT, "research", "lit", "two_week_ceiling.json")
PV, COMM, SLIP = 2.0, 1.40, 0.25
SPAN = {"2026": ("2026-01-01", "2026-12-31"), "H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-12-31"),
        "2021-25": ("2021-01-01", "2025-12-31")}
N_MC, MC_LEN = 4000, 20
PRICE = {"50k": 91.80, "25k": 63.0}
ACCT = {"50k": {"target": 3000.0, "mll": 2000.0, "lock": 100.0, "dll": 1000.0, "max_micros": 40, "scale": 1.0},
        "25k": {"target": 1500.0, "mll": 1000.0, "lock": 100.0, "dll": 600.0, "max_micros": 20, "scale": 0.5}}
VARIANTS = {"live": {}, "two": {"max_per_day": 2}, "w0": {"window": [[0, 930]]}, "two_w0": {"max_per_day": 2, "window": [[0, 930]]}}


# ================================================================================================ unit trades
def _unit_path(v):
    return os.path.join(CACHE, f"lit_2wk_unit_{v}.json")


def build(variants=None):
    from engine import lit
    from tools import lit_tightstop as T
    for v in variants or VARIANTS:
        U = T.trun(VARIANTS[v])
        U.sort(key=lambda t: t["entry_t"])
        if VARIANTS[v].get("max_per_day", 1) > 1:
            first = {}
            keep = []
            for t in U:
                if t["day"] not in first:
                    first[t["day"]] = t
                    keep.append(t)
                elif first[t["day"]]["exit"] == "STOP":
                    keep.append(t)                # second shot only after a stop-out (causal: the first trade has exited)
            U = keep
        T.wk_marks(U)
        out = []
        for t in U:
            tg = abs(float(t["target_px"]) - float(t["entry_px"]))
            out.append({"day": t["day"], "entry_t": t["entry_t"], "exit_t": t["exit_t"], "dir": t["dir"], "risk": t["risk_pts"],
                        "tgt": round(tg, 2), "pts": round(float(t["legs"][0][1]), 4), "w1": round(float(t["w1"]), 4),
                        "exit": t["exit"], "wk_m": t.get("wk_m", 1.0), "tf": t["tf"]})
        json.dump({"sess": list(T.SESS), "variant": VARIANTS[v], "trades": out}, open(_unit_path(v), "w"), default=float)
        n26 = [t for t in out if t["day"] >= "2026"]
        print(f"{v}: {len(out)} trades, 2026 {len(n26)}, net 1 micro {sum(t['pts'] * PV - COMM for t in n26):+,.0f}", flush=True)


_D = {}


def data(v="live"):
    if v not in _D:
        d = json.load(open(_unit_path(v), encoding="utf-8"))
        sess = d["sess"]
        by = collections.defaultdict(list)
        for t in d["trades"]:
            by[t["day"]].append(t)
        _D[v] = {"sess": sess, "by": [by.get(s, []) for s in sess], "trades": d["trades"],
                 "dow": np.array([dt.date.fromisoformat(s).weekday() for s in sess])}
    return _D[v]


def span_idx(span, v="live"):
    a, z = SPAN[span]
    s = data(v)["sess"]
    ix = [i for i, d in enumerate(s) if a <= d <= z]
    return ix[0], ix[-1] + 1


# ================================================================================================ the eval (exact MFFU Builder)
def run_eval(cfg, seq, by, acct="50k", horizon=MC_LEN, keep=None):
    """One eval over session indices seq. Returns (result PASS/FAIL/OPEN, sessions used, worst day $, max $ at risk)."""
    A = ACCT[acct]
    tgt, mll, dll, lockv = A["target"], A["mll"], A["dll"], A["lock"]
    bal = peak = 0.0
    floor = -mll
    worst_day, max_risk = 0.0, 0.0
    for k, si in enumerate(seq[:horizon]):
        cum = 0.0
        for j, t in enumerate(by[si]):
            if cum <= -dll:
                break                                           # soft daily loss reached: the day is over
            st = {"profit": bal, "cum": cum, "room": bal + cum - floor, "session": k + 1, "n_today": j}
            q = S.two_week_qty(t, st, cfg, acct=A)
            if q <= 0:
                continue
            comm = COMM * q
            pnl = t["pts"] * PV * q - comm
            low = min(0.0, t["w1"] * PV * q - comm, pnl)
            max_risk = max(max_risk, (t["risk"] + SLIP) * PV * q + comm)
            if cum + low <= -dll:                               # MFFU flattens at the soft daily loss
                pnl = -dll - cum - SLIP * PV * q
                low = pnl
            if bal + cum + low <= floor:
                if keep is not None:
                    keep.append((si, q, pnl))
                return "FAIL", k + 1, min(worst_day, cum + low), max_risk
            cum += pnl
            if keep is not None:
                keep.append((si, q, pnl))
        bal += cum
        worst_day = min(worst_day, cum)
        if bal <= floor:
            return "FAIL", k + 1, worst_day, max_risk
        peak = max(peak, bal)
        floor = min(max(floor, peak - mll), lockv)
        if bal >= tgt:
            return "PASS", k + 1, worst_day, max_risk
    return "OPEN", min(len(seq), horizon), worst_day, max_risk


def summarize(res, acct="50k"):
    N = len(res) or 1
    pc = lambda c: round(100.0 * c / N, 1)
    o = {"n": len(res)}
    for lab, h in (("10", 10), ("20", 20)):
        o[f"p{lab}"] = pc(sum(1 for r in res if r[0] == "PASS" and r[1] <= h))
        o[f"f{lab}"] = pc(sum(1 for r in res if r[0] == "FAIL" and r[1] <= h))
        o[f"o{lab}"] = round(100 - o[f"p{lab}"] - o[f"f{lab}"], 1)
    pas = [r[1] for r in res if r[0] == "PASS" and r[1] <= 20]
    o["pass_med"] = float(np.median(pas)) if pas else None
    o["cost"] = round(PRICE[acct] / (o["p10"] / 100.0), 0) if o["p10"] > 0 else None
    o["worst_day"] = round(min(r[2] for r in res)) if res else 0
    o["max_risk"] = round(max(r[3] for r in res)) if res else 0
    return o


def exact(cfg, span, v="live", acct="50k", starts=None, horizon=MC_LEN):
    D = data(v)
    a, z = span_idx(span, v)
    st = range(a, z) if starts is None else [i for i in starts if a <= i < z]
    res = [run_eval(cfg, list(range(i, min(z, i + horizon))), D["by"], acct, horizon) for i in st]
    # starts too close to the span end to see 10 sessions are left out of the 10-session rates' denominator? no: an eval
    # started there just ends OPEN when the data runs out (same as tools/lit_prop_firms.py)
    return summarize(res, acct)


_SEQ = {}


def mc_seqs(span, v="live", n=N_MC, length=MC_LEN, seed=7):
    key = (span, v, n, length, seed)
    if key not in _SEQ:
        a, z = span_idx(span, v)
        rng = np.random.default_rng(seed)
        st = np.arange(a, z - 5 + 1)
        out = []
        for _ in range(n):
            seq = []
            while len(seq) < length:
                j = int(rng.choice(st))
                seq.extend(range(j, j + 5))
            out.append(seq[:length])
        _SEQ[key] = out
    return _SEQ[key]


def mc(cfg, span, v="live", acct="50k"):
    D = data(v)
    return summarize([run_eval(cfg, s, D["by"], acct) for s in mc_seqs(span, v)], acct)


def score(cfg, v="live", spans=("H1", "H2", "2026", "2021-25"), mcs=("H1", "H2", "2026"), acct="50k"):
    o = {}
    for s in spans:
        o[s] = exact(cfg, s, v, acct)
    for s in mcs:
        o["mc_" + s] = mc(cfg, s, v, acct)
    return o


# ================================================================================================ the ceiling
def ceiling():
    """Upper bounds of P(pass within 10 sessions) for LIT's signals, whatever the sizing.
    (a) target-hit: share of 10-session windows with at least one TARGET exit (one winner can pass only if it reaches target)
    (b) any-winner: at least one trade that made money
    (c) hindsight oracle: every winner at the most micros the rules allow (40, and a full stop-out inside the $1,000 soft
        daily loss), every other trade at 1 micro; pass if the eval reaches +$3,000 within 10 sessions without failing
    (d) the analytic line: 1 - (1 - p_target)^n with n = LIT's trades in 10 sessions (Poisson)."""
    rep = {}
    for v in ("live", "two"):
        D = data(v)
        for span in ("H1", "H2", "2026", "2021-25"):
            a, z = span_idx(span, v)
            by = D["by"]
            hit = win = orc = 0
            ntr = []
            for i in range(a, z):
                w = [t for k in range(i, min(z, i + 10)) for t in by[k]]
                ntr.append(len(w))
                hit += any(t["exit"] == "TARGET" for t in w)
                win += any(t["pts"] > 0 for t in w)
                # oracle
                bal, peak, floor, ok = 0.0, 0.0, -2000.0, None
                for k in range(i, min(z, i + 10)):
                    cum = 0.0
                    for t in by[k]:
                        if t["pts"] > 0:
                            q = max(1, min(40, int((1000.0 + max(0.0, cum)) / ((t["risk"] + SLIP) * PV + COMM))))
                        else:
                            q = 1
                        cum += t["pts"] * PV * q - COMM * q
                    bal += cum
                    if bal <= floor:
                        ok = False; break
                    peak = max(peak, bal); floor = min(max(floor, peak - 2000.0), 100.0)
                    if bal >= 3000.0:
                        ok = True; break
                orc += ok is True
            N = z - a
            T_ = [t for k in range(a, z) for t in by[k]]
            p_t = sum(t["exit"] == "TARGET" for t in T_) / max(1, len(T_))
            lam = len(T_) / N * 10
            analytic = 1 - math.exp(-lam * p_t)         # Poisson(lam) trades, each a target with p_t
            rep[f"{v}|{span}"] = {"starts": N, "trades_per_10": round(lam, 2), "p_target": round(100 * p_t, 1),
                                  "p_win": round(100 * sum(t["pts"] > 0 for t in T_) / max(1, len(T_)), 1),
                                  "target_in_10": round(100 * hit / N, 1), "winner_in_10": round(100 * win / N, 1),
                                  "oracle_in_10": round(100 * orc / N, 1), "analytic": round(100 * analytic, 1),
                                  "med_tgt_r": round(float(np.median([t["tgt"] / t["risk"] for t in T_])), 2),
                                  "med_tgt_usd_at_1000_risk": round(float(np.median([1000.0 * t["tgt"] / (t["risk"] + SLIP) for t in T_])))}
            print(v, span, rep[f"{v}|{span}"], flush=True)
    json.dump(rep, open(OUT_C, "w"), indent=1)
    return rep


# ================================================================================================ the grid
def configs():
    C = collections.OrderedDict()
    C["live LIT size ($800/20, no cap)"] = {"base": "lit", "usd": 800, "ref": 20, "room_f": None, "dll_cap": False}
    C["eval mode today ($800/25 + room 60%)"] = {"base": "lit", "usd": 800, "ref": 25, "room_f": 0.6, "dll_cap": False}
    for usd, ref in itertools.product((800, 1000, 1200), (25, 40, 60)):
        for f in (0.4, 0.5, 0.6, 0.8, 1.0):
            C[f"fixed ${usd}/{ref} room {f}"] = {"base": "lit", "usd": usd, "ref": ref, "room_f": f}
    for f in (0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0):
        for wk in (True, False):
            for mx in (None, 800, 1000):
                C[f"need room {f} wk {int(wk)} max {mx}"] = {"base": "need", "room_f": f, "wk": wk, "max_usd": mx}
    return C


def press_configs(base):
    """Day-by-day pressure and protect on top of a base config."""
    C = collections.OrderedDict()
    for at, m in ((5, 1.5), (6, 1.5), (6, 2.0), (7, 2.0), (8, 2.0), (8, 3.0)):
        C[f"press x{m} from session {at}"] = {**base, "press_at": at, "press_mult": m}
    for keep in (0.0, 0.3, 0.5, 0.7):
        for over in (1000, 1500, 2000):
            C[f"protect: keep {keep} of profit once +{over}"] = {**base, "protect_over": over, "protect_keep": keep}
    return C


def _job(args):
    nm, cfg, v = args
    return nm, v, score(cfg, v, spans=("H1", "H2", "2026"), mcs=("H1", "H2"))


def grid(procs=2):
    from multiprocessing import Pool
    res = json.load(open(OUT)) if os.path.exists(OUT) else {}
    jobs = [(nm, cfg, v) for v in ("live", "two", "w0", "two_w0") for nm, cfg in configs().items()
            if f"{v}|{nm}" not in res and (v == "live" or nm.startswith(("need", "eval mode", "fixed $1000/40", "fixed $800/40", "fixed $1200/40")))]
    with Pool(procs) as p:
        for k, (nm, v, o) in enumerate(p.imap_unordered(_job, jobs)):
            res[f"{v}|{nm}"] = {"cfg": dict(configs()[nm]), "v": v, **o}
            if k % 10 == 0:
                json.dump(res, open(OUT, "w"), indent=1)
                print(k, len(jobs), short(f"{v}|{nm}", res[f"{v}|{nm}"]), flush=True)
    json.dump(res, open(OUT, "w"), indent=1)
    return res


def short(nm, o):
    f = lambda s: f"{o[s]['p10']}/{o[s]['f10']}/{o[s]['o10']}" if s in o else "-"
    return f"{nm:55s} H1 {f('H1')} H2 {f('H2')} mcH1 {f('mc_H1')} mcH2 {f('mc_H2')}"


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "ceiling"
    if cmd == "build":
        build(sys.argv[2:] or None)
    elif cmd == "ceiling":
        ceiling()
    elif cmd == "grid":
        grid()
