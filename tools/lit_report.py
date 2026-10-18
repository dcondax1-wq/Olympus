"""LIT report tests: the codable rules of the owner's LIT Complete Report (2026-10-18) that LIT live had not tested yet.

Owner order 2026-10-18: "continue pushing all of LIT; add the useful things from this report". Judged on 2026 only: every rule
is picked on 2026 H1 (Jan-Jun) and checked on 2026 H2 (Jul-Oct 16); 2021-25 is a reference line. A rule is adopted only when
it improves BOTH halves and keeps ~2-4 trades a week. Write-up: research/writeups/lit-report-tests.md.

Wraps engine/lit.py (not edited): core() below is a copy of lit._run_core (live=False) with default-off hooks; with no hook
set it reproduces lit_live (live_model.json "lit") trade for trade (`check`).

  python tools/lit_report.py check     # core(P_live) == lit_final.run(P_live)  (120 trades 2026, +$41,734)
  python tools/lit_report.py test      # every variant -> research/lit/report_results.json
  python tools/lit_report.py srr       # the report's chapter 21 model (Session Range Reclaim V2) as a benchmark
  python tools/lit_report.py save      # store the runs lit_rep_* (rl.save, family other, tags lit, lit_report)
1 CPU process.
"""
from __future__ import annotations

import collections
import json
import math
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from tools import lit_final as F  # noqa: E402
from tools import runlib as rl  # noqa: E402

OUT = os.path.join(ROOT, "research", "lit", "report_results.json")
TICK, PV, COMM, SLIP = lit.TICK, lit.PV, lit.COMM, lit.SLIP
P_LIVE = {**lit.DEFAULTS, **json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]}
BOX = ("asia", "lon", "ny", "pre")


# ================================================================================================ core (copy + hooks)
def core(M, cands, P, sessions, B1, B5, X=None):
    """lit._run_core(live=False) plus hooks in X (all default off):
      skip(M, z) -> True      drop the setup (the day stays free for a later one)
      mult(M, z) -> float     size multiplier (one rounding together with how_out and the weekly stop, floor 1 micro)
      second(z, first) -> bool  allow a second trade on a day whose first trade `first` has closed
      qty(t) -> int           re-size a finished trade to this many micros (exact, lit.scale_trade arithmetic)"""
    X = X or {}
    P = {**lit.DEFAULTS, **(P or {})}
    names = set(P["sweep_names"]) if P.get("sweep_names") else None
    sset = set(sessions) if sessions else None
    out, busy, per_day, first = [], -1, collections.Counter(), {}
    buf = P["stop_buf"]
    for z in cands:
        if sset is not None and z["day"] not in sset:
            continue
        if z["entry_i"] <= busy:
            continue
        if per_day[z["day"]] >= P["max_per_day"]:
            if not (X.get("second") and per_day[z["day"]] == 1 and X["second"](z, first[z["day"]])):
                continue
        if not lit.setup_ok(z, P, names):
            continue
        if P.get("monday") and lit.monday_block(M, z):
            continue
        if X.get("skip") and X["skip"](M, z):
            continue
        ep = min(float(z["ref_d"]), z["trig_c"])
        stop = z["ext_d"] - buf
        risk = ep - stop
        if not (P["min_stop"] <= risk <= P["max_stop"]):
            continue
        sh = z["entry_d"] - ep
        TT = {c: [x + sh for x in v] for c, v in lit.targets_x(M, z, P).items()}
        best = None
        for c in P["classes"]:
            for dist in TT.get(c, []):
                if dist >= P["min_rr"] * risk:
                    if best is None or dist < best:
                        best = dist
                    break
        fb = False
        if best is None:
            if not P["fallback_rr"]:
                continue
            tp, fb = P["fallback_rr"] * risk, True
        else:
            tp = min(best, P["max_rr"] * risk) if P["max_rr"] else best
        use1 = P["tf"] == "1m" and B1 is not None and int(M.day_of[z["entry_i"]]) in B1.full
        B = B1 if use1 else B5
        tgt = ("lvl", ep + tp, fb) if P.get("cisd1m") else ("pts", tp)
        t = lit.simulate_x(M, B, z, ep, tgt, stop, P, live=False)
        if t is None:
            continue
        busy = t["exit_i"]; per_day[z["day"]] += 1
        first.setdefault(z["day"], t)
        m = P["how_out"] if (P["how_out"] != 1.0 and not z["how"]) else 1.0
        if P.get("wk_stop"):
            n_st, m_st = P["wk_stop"]
            if lit.week_stops(z["day"], t["entry_t"], out) >= n_st:
                m *= float(m_st)
        if X.get("mult"):
            m *= float(X["mult"](M, z))
        if m != 1.0:
            t = lit.scale_trade(t, m)
        if X.get("qty"):
            q = int(X["qty"](t))
            if q < 1:
                continue
            if q != t["qty"]:
                t = lit.scale_trade(t, q / t["qty"])
        t["_z"] = z
        out.append(t)
    return out


_S = {}


def base():
    if "M" not in _S:
        M, C = F.market(P_LIVE["ref"], P_LIVE["extra_boxes"])
        _S.update(M=M, C=C, B1=F.bars(M, "1m"), B5=F.bars(M, "5m"))
    return _S["M"], _S["C"], _S["B1"], _S["B5"]


def run(X=None, P=None):
    M, C, B1, B5 = base()
    return core(M, C, {**P_LIVE, **(P or {})}, F.SESS, B1, B5, X)


def key(T):
    return [(t["day"], t["entry_t"], round(t["pnl"], 2), t["exit"], t["qty"]) for t in sorted(T, key=lambda t: t["entry_t"])]


def check():
    A = F.run(P_LIVE)
    Bt = run()
    a26 = [t for t in A if t["day"] >= "2026"]
    print("lit_live via lit_final.run:", len(a26), round(sum(t["pnl"] for t in a26)), "| core:",
          sum(t["day"] >= "2026" for t in Bt), round(sum(t["pnl"] for t in Bt if t["day"] >= "2026")),
          "| identical:", key(A) == key(Bt), flush=True)
    return key(A) == key(Bt)


# ================================================================================================ features (all causal)
def dspace(M, d):
    return (M.h, M.l, M.c, M.o) if d == 1 else (-M.l, -M.h, -M.c, -M.o)


def lev_near(z):
    return max(z["sw"].values()) if z.get("sw") else None


def f_reclaim(M, z):
    """Ch.13: the trigger bar closed back beyond the swept level (direction space: close above the swept low)."""
    lv = lev_near(z)
    return lv is not None and z["trig_c"] > lv


def f_closes_beyond(M, z):
    """Ch.18 acceptance: 5m closes beyond the swept level from the first breach (sweep bar) up to the bar before the trigger."""
    lv = lev_near(z)
    if lv is None:
        return 0
    _, _, c_d, _ = dspace(M, z["dir"])
    return int((c_d[z["sweep_i"]:z["i"]] < lv).sum())


def f_close_loc(M, z):
    """Ch.10 / 21: where the trigger bar closed inside its own range (1 = at the high for a long)."""
    hi, lo, c, _ = dspace(M, z["dir"])
    i = z["i"]
    rg = hi[i] - lo[i]
    return float((c[i] - lo[i]) / rg) if rg > 0 else 0.0


def f_rel_disp(M, z):
    """Ch.10 / 21: biggest directional body between the extreme and the trigger / median |body| of the 20 bars before the
    extreme."""
    _, _, c, o = dspace(M, z["dir"])
    ee, i = z["ext_i"], z["i"]
    med = float(np.median(np.abs(c[max(0, ee - 20):ee] - o[max(0, ee - 20):ee]))) if ee >= 20 else 0.0
    body = float((c[ee + 1:i + 1] - o[ee + 1:i + 1]).max()) if i > ee else 0.0
    return body / med if med > 0 else 0.0


def f_fvg(M, z):
    """Ch.9 / 21: a directional FVG formed between the extreme and the trigger (low of bar j >= high of bar j-2 + 1 tick)."""
    hi, lo, _, _ = dspace(M, z["dir"])
    ee, i = z["ext_i"], z["i"]
    return any(lo[j] >= hi[j - 2] + TICK for j in range(max(ee + 2, 2), i + 1))


def idm_q(z, P=P_LIVE):
    dm, age, _ = P["idm_a"]
    return [dd for dd, aa in z["idm_a"] if dd <= dm and aa <= age]


def f_leg_pos(M, z):
    """Ch.11 premium / discount (Smart Risk 50%): where the limit price sits in the leg from the extreme (0) to the leg's swing
    high in the 36 bars before the extreme (1). <= 0.5 = discount for a long."""
    hi, lo, _, _ = dspace(M, z["dir"])
    ee = z["ext_i"]
    top = float(hi[max(0, ee - 36):ee + 1].max())
    ep = min(float(z["ref_d"]), z["trig_c"])
    rg = top - z["ext_d"]
    return (ep - z["ext_d"]) / rg if rg > 0 else 1.0


def f_obstacle_r(M, z, P=P_LIVE):
    """Ch.16 / 26 first obstacle: distance from the limit price to the nearest unbroken opposing level of any class (session
    boxes, PD/PW/PM, gaps, build-ups), in R of the planned stop. None = no level in the path."""
    ep = min(float(z["ref_d"]), z["trig_c"])
    risk = ep - (z["ext_d"] - P["stop_buf"])
    sh = z["entry_d"] - ep
    ds = [x + sh for v in z["targets"].values() for x in v if x + sh > 0]
    return (min(ds) / risk) if ds and risk > 0 else None


def f_double_sided(M, z, boxes_only=True):
    """Ch.6 double-sided sweep: before this sweep's extreme, today's session already traded through the opposite side of a
    known level. boxes_only: the other side of the SAME box (a range swept on both sides); else any opposite level known."""
    d = z["dir"]
    hi, lo, _, _ = dspace(M, d)
    k, ee = z["k"], z["ext_i"]
    x = M.ctx[k]
    s = x["s"]
    if boxes_only:
        for nm in z["swept"]:
            base_ = nm[:-2] if nm.endswith(("_h", "_l")) else None
            if not base_ or base_ not in x or not base_.startswith(BOX):
                continue
            bh, bl, ki = x[base_]
            other = bh if d == 1 else -bl
            if ki + 1 <= ee and hi[ki + 1:ee + 1].max() > other:
                return True
        return False
    for side, px, ki, nm, cls in M.levels(k):
        if (side == "high") != (d == 1) or cls in ("buildup", "gap"):
            continue
        p = px * d
        a = max(ki + 1, s)
        if a <= ee and hi[a:ee + 1].max() > p:
            return True
    return False


def fee_qty(t, budget=800.0, ref_stop=20.0, slip_pts=0.25):
    """Ch.15 / 27 sizing from the loss budget with costs inside it: q = floor(B / (d*V + fees + slip*V)) (B = $800 up to a
    20-pt stop, then 800*20/stop), times the size multiplier already applied to the trade."""
    d = t["risk_pts"]
    B = budget if d <= ref_stop else budget * ref_stop / d
    q = int(B / (d * PV + COMM + slip_pts * PV))
    m = t.get("mult", 1.0) or 1.0
    q = max(1, int(q * m + 1e-9)) if m < 1 else q
    return min(lit.MAX_MICROS, q)


# ================================================================================================ variants
def V():
    S = collections.OrderedDict()
    sk = lambda fn: {"skip": fn}
    half = lambda fn: {"mult": lambda M, z: 0.5 if fn(M, z) else 1.0}
    # ch.13 reclaim
    S["reclaim: trigger closes back beyond the swept level (skip if not)"] = ("ch13 reclaim", sk(lambda M, z: not f_reclaim(M, z)))
    S["reclaim: half size if not"] = ("ch13 reclaim", half(lambda M, z: not f_reclaim(M, z)))
    # ch.13 deadline: extreme -> trigger within n 5m bars
    for n in (3, 6, 9, 12):
        S[f"deadline: confirmation within {n} bars of the extreme"] = ("ch13 deadline", sk(lambda M, z, n=n: z["bars"] > n))
    # ch.18 acceptance
    for n in (1, 2, 3, 4):
        S[f"acceptance: skip after {n}+ closes beyond the swept level"] = ("ch18 acceptance", sk(lambda M, z, n=n: f_closes_beyond(M, z) >= n))
    S["acceptance: half after 2+ closes beyond"] = ("ch18 acceptance", half(lambda M, z: f_closes_beyond(M, z) >= 2))
    # ch.10 / 21 displacement quality
    S["displacement: trigger closes in the top quarter of its bar"] = ("ch21 close location", sk(lambda M, z: f_close_loc(M, z) < 0.75))
    S["displacement: trigger closes in the top half of its bar"] = ("ch21 close location", sk(lambda M, z: f_close_loc(M, z) < 0.5))
    S["displacement: half size unless top quarter"] = ("ch21 close location", half(lambda M, z: f_close_loc(M, z) < 0.75))
    for k in (1.5, 2.0, 3.0):
        S[f"displacement: body >= {k}x median body of 20 bars"] = ("ch21 relative body", sk(lambda M, z, k=k: f_rel_disp(M, z) < k))
    S["displacement: FVG left between the extreme and the trigger (skip without)"] = ("ch21 FVG", sk(lambda M, z: not f_fvg(M, z)))
    # ch.5 / 14 inducements
    S["inducements: 2+ taken (skip with 1)"] = ("ch14 multiple inducements", sk(lambda M, z: len(idm_q(z)) < 2))
    S["inducements: half size with only 1"] = ("ch14 multiple inducements", half(lambda M, z: len(idm_q(z)) < 2))
    for x in (0.1, 0.2, 0.3):
        S[f"inducement: at least {x} ATR above the swept level"] = ("ch5 inducement room", sk(lambda M, z, x=x: not idm_q(z) or max(idm_q(z)) < x))
    # ch.7 ETM final sweep: at least two levels swept by the same run
    S["final sweep: 2+ levels swept (skip with 1)"] = ("ch7 final sweep", sk(lambda M, z: len(z["swept"]) < 2))
    S["final sweep: half size with 1 level swept"] = ("ch7 final sweep", half(lambda M, z: len(z["swept"]) < 2))
    # ch.11 premium / discount of the leg
    S["discount: limit in the lower half of the leg (skip in premium)"] = ("ch11 premium/discount", sk(lambda M, z: f_leg_pos(M, z) > 0.5))
    S["discount: half size in premium"] = ("ch11 premium/discount", half(lambda M, z: f_leg_pos(M, z) > 0.5))
    # ch.6 double-sided sweep
    S["double-sided: skip when the same box's other side was taken first"] = ("ch6 double-sided", sk(lambda M, z: f_double_sided(M, z, True)))
    S["double-sided: skip when any opposite level was taken first today"] = ("ch6 double-sided", sk(lambda M, z: f_double_sided(M, z, False)))
    S["double-sided: half size when any opposite level was taken first"] = ("ch6 double-sided", half(lambda M, z: f_double_sided(M, z, False)))
    # ch.16 / 26 first obstacle
    for r in (0.25, 0.4, 0.5, 0.6, 0.75, 1.0, 1.5):
        S[f"first obstacle: skip when a level sits within {r}R"] = ("ch26 first obstacle", sk(lambda M, z, r=r: (f_obstacle_r(M, z) or 99) < r))
    S["first obstacle: half size when a level sits within 0.5R"] = ("ch26 first obstacle", half(lambda M, z: (f_obstacle_r(M, z) or 99) < 0.5))
    S["first obstacle: half size when a level sits within 1R"] = ("ch26 first obstacle", half(lambda M, z: (f_obstacle_r(M, z) or 99) < 1.0))
    # ch.14 continuation / failed reversal
    S["continuation: 2nd trade same side after a non-stop first trade"] = (
        "ch14 continuation", {"second": lambda z, f: f["exit"] != "STOP" and z["dir"] == f["dir"]})
    S["failed reversal: 2nd trade opposite side after a stop-out"] = (
        "ch14 failed reversal", {"second": lambda z, f: f["exit"] == "STOP" and z["dir"] != f["dir"]})
    S["failed reversal: same, at half size"] = (
        "ch14 failed reversal", {"second": lambda z, f: f["exit"] == "STOP" and z["dir"] != f["dir"], "_second_half": True})
    # ch.15 / 27 sizing with fees + slippage inside the budget
    S["sizing: fees + 1 tick slippage inside the $800 budget"] = ("ch15 sizing", {"qty": fee_qty})
    return S


def _second_half(X):
    if not X.get("_second_half"):
        return X
    seen = {}

    def mult(M, z):
        return 0.5 if seen.get(z["day"]) else 1.0
    X = {k: v for k, v in X.items() if k != "_second_half"}
    sec = X["second"]

    def second(z, f):
        ok = sec(z, f)
        if ok:
            seen[z["day"]] = True
        return ok
    X.update(second=second, mult=mult)
    return X


def h(s):
    return (f"n={s['n']} {s['tpw']}/wk win {s['win']}% PF {s['pf']} net {s['net']:+,} (${s['per_month']:,}/mo) DD {s['dd']:,} "
            f"eval 2wk {s['p10']}/{s['f10']} 1mo {s['p20']}/{s['f20']} pass rate {s['pass_rate']}%")


def test(only=None):
    res = json.load(open(OUT)) if os.path.exists(OUT) else {}
    T0 = run()
    b = F.score(T0)
    res["_base"] = {"name": "lit_live", **b}
    print("BASE", F.fmt(b), flush=True)
    for nm, (fam, X) in V().items():
        if only and only not in nm:
            continue
        T = run(_second_half(dict(X)))
        o = F.score(T)
        d1 = o["H1"]["net"] - b["H1"]["net"]; d2 = o["H2"]["net"] - b["H2"]["net"]
        both = d1 > 0 and d2 > 0 and o["H1"]["tpw"] >= 2.0 and o["H2"]["tpw"] >= 2.0
        res[nm] = {"family": fam, **o, "dH1": d1, "dH2": d2, "both": both}
        print(f"{nm:70s} dH1={d1:+7,} dH2={d2:+7,} both={both} | H1 {o['H1']['tpw']}/wk PF {o['H1']['pf']} | H2 {o['H2']['tpw']}/wk "
              f"PF {o['H2']['pf']} | 2026 DD {o['2026']['dd']:,} 2w {o['2026']['p10']}/{o['2026']['f10']} | 21-25 PF {o['2021-25']['pf']}",
              flush=True)
        json.dump(res, open(OUT, "w"), indent=1, default=str)
    return res


# ================================================================================================ chapter 21 benchmark
WHY = collections.Counter()          # where the ch.21 model drops each day (r1..r12 = the return points of srr_day)
WHY_LABEL = {"r1": "no 1m bars", "r2": "missing range bars (08:00-09:25 not complete)", "r3": "one bar crossed both boundaries",
             "r4": "no boundary event 09:30-10:30", "r5": "no reclaim close within 3 bars", "r6": "no strict 5-bar pivot",
             "r7": "objective (other side) traded before confirmation", "r8": "no confirmation bar (pivot close + 1.5x body + top "
             "quarter + FVG) within 6 bars before 10:30", "r9": "non-positive risk", "r10": "2R target beyond the range",
             "r11": "limit never filled (C+1..C+5, before 10:30)", "r12": "size rounds to zero"}


def srr_day(B, k, M):
    """Session Range Reclaim Version 2 (report ch.21) on true 1m bars for Market day k. Returns a trade dict or None.
    Range 08:00-09:25 (half-open), first boundary event from 09:30, reclaim within 3 bars, strict 5-bar pivot in the 20 bars
    before the sweep, confirmation bar C in R..R+5 (close >= pivot + 1 tick, body >= 1.5x median |body| of 20 bars, close in
    the top quarter, bullish FVG with C-2), all closed before 10:30; buy limit at the FVG midpoint (tick-rounded) for C+1..C+5,
    cancelled at 10:30 or if the stop or target trades first; stop 2 ticks beyond the S..C extreme; target 2R (must stay
    inside the range); flat at 11:00. One candidate a day. Conservative OHLC rules: a bar that touches the limit and the stop
    stops out; no target credit on the fill bar."""
    ix = np.flatnonzero(B.day == k)
    if not len(ix):
        WHY["r1"] += 1
        return None
    a, z = int(ix[0]), int(ix[-1]) + 1
    mod = B.mod[a:z]
    rng = np.flatnonzero((mod >= 480) & (mod < 565))
    if len(rng) != 85:                                   # missing range bars: the day is invalid
        WHY["r2"] += 1
        return None
    H = float(B.h[a + rng].max()); L = float(B.l[a + rng].min())
    freeze = a + int(rng[-1])                            # the 09:24 bar closes at 09:25
    cand = [j for j in range(freeze + 1, z) if B.mod[j] >= 570 and B.mod[j] < 630]
    S = side = None
    for j in cand:
        dn = B.l[j] <= L - TICK and B.c[j - 1] >= L
        up = B.h[j] >= H + TICK and B.c[j - 1] <= H
        if dn and up:
            WHY["r3"] += 1
            return None                                  # one bar crossed both boundaries: reject the day
        if dn or up:
            S, side = j, (1 if dn else -1)
            break
    if S is None:
        WHY["r4"] += 1
        return None
    d = side
    hi, lo, c, o = (B.h, B.l, B.c, B.o) if d == 1 else (-B.l, -B.h, -B.c, -B.o)
    Ld, Hd = (L, H) if d == 1 else (-H, -L)              # direction space: swept boundary Ld (below), objective Hd (above)
    R = next((j for j in range(S, min(S + 4, z)) if c[j] > Ld), None)
    if R is None:
        WHY["r5"] += 1
        return None
    piv = None
    for j in range(S - 3, max(S - 21, a + 1), -1):       # right bars j+1, j+2 closed before S opens
        if j - 2 < a:
            break
        if hi[j] > max(hi[j - 1], hi[j - 2], hi[j + 1], hi[j + 2]):
            piv = float(hi[j]); break
    if piv is None:
        WHY["r6"] += 1
        return None
    C = None
    for j in range(R, min(R + 6, z)):
        if B.mod[j] + 1 > 629:                           # must close strictly before 10:30
            break
        if hi[freeze + 1:j + 1].max() >= Hd:             # the objective traded before confirmation
            WHY["r7"] += 1
            return None
        body = c[j] - o[j]
        med = float(np.median(np.abs(c[j - 20:j] - o[j - 20:j])))
        rg = hi[j] - lo[j]
        if (c[j] >= piv + TICK and body > 0 and body >= 1.5 * med and rg > 0 and (c[j] - lo[j]) / rg >= 0.75
                and lo[j] >= hi[j - 2] + TICK):
            C = j; break
    if C is None:
        WHY["r8"] += 1
        return None
    ext = float(lo[S:C + 1].min())
    stop = ext - 2 * TICK
    mid = (hi[C - 2] + lo[C]) / 2.0
    entry = math.floor(mid / TICK + 1e-9) * TICK          # direction space: a long rounds down, a short (price) rounds up
    risk = entry - stop
    if risk <= 0:
        WHY["r9"] += 1
        return None
    tgt = entry + 2 * risk
    if tgt > Hd - TICK:
        WHY["r10"] += 1
        return None
    fill = None
    for j in range(C + 1, min(C + 6, z)):
        if B.mod[j] >= 630:
            break
        if lo[j] <= entry:
            fill = j; ent = min(entry, float(o[j])); break
        if hi[j] >= tgt:
            break
    if fill is None:
        WHY["r11"] += 1
        return None
    q = lit.qty_for(ent - stop)
    if q < 1:
        WHY["r12"] += 1
        return None
    k_ = fill
    xp = kind = None
    while k_ < z:
        if B.mod[k_] >= 660:
            xp, kind = float(o[k_]) - SLIP, "TIME"; break
        if lo[k_] <= stop:
            xp, kind = stop - SLIP, "STOP"; break
        if k_ != fill and hi[k_] >= tgt:
            xp, kind = tgt, "TARGET"; break
        k_ += 1
    if xp is None:
        k_ = z - 1; xp, kind = float(c[k_]) - SLIP, "EOD"
    rk = ent - stop
    pnl = (xp - ent) * PV * q - COMM * q
    return {"day": M.days[k][0], "entry_t": int(B.t[fill]), "exit_t": int(B.t[k_]) + 60, "dir": d, "r": round(pnl / (rk * PV * q), 3),
            "pnl": round(pnl, 2), "risk_pts": round(rk, 2), "qty": q, "risk_usd": round(rk * PV * q, 2), "exit": kind,
            "trigger": "SRR-v2", "entry_px": round(ent * d, 2), "stop_px": round(stop * d, 2), "target_px": round(tgt * d, 2),
            "low": round(min(0.0, pnl), 2), "half": False, "mult": 1.0, "tf": 1}


def srr():
    M, C, B1, B5 = base()
    T = [t for t in (srr_day(B1, k, M) for k in sorted(B1.full)) if t]
    T = [t for t in T if t["day"] in set(F.SESS)]
    o = F.score(T, spans=("H1", "H2", "2026"))
    funnel = {WHY_LABEL[k]: v for k, v in sorted(WHY.items(), key=lambda x: int(x[0][1:]))}
    print("SRR v2 (ch.21) alone:", F.fmt(o), flush=True)
    print("days:", len(B1.full), "funnel:", funnel, flush=True)
    L = run()
    byday = {t["day"]: t for t in L}
    comb = []
    for t in T:
        lt = byday.get(t["day"])
        if lt is None or t["entry_t"] < lt["entry_t"]:
            comb.append(t)
    keep_days = {t["day"] for t in comb}
    comb += [t for t in L if t["day"] not in keep_days]
    oc = F.score(comb, spans=("H1", "H2", "2026"))
    print("LIT live + SRR (first entry of the day wins):", F.fmt(oc), flush=True)
    res = json.load(open(OUT)) if os.path.exists(OUT) else {}
    res["_srr"] = {"alone": o, "with_lit": oc, "n_days_1m": len(B1.full), "funnel": funnel, "trades": len(T)}
    json.dump(res, open(OUT, "w"), indent=1, default=str)
    return T, comb


# ================================================================================================ ch.28 clocks: European boxes
class MarketDST(lit.Market):
    """lit.Market with the two boxes that are European wall-clock windows kept on Europe/Berlin time (LIT report ch.28):
    lon34 (Reim's London inducement window 09:00-10:00 Berlin = 03:00-04:00 ET) and lon23 (Frankfurt 08:00-09:00 Berlin =
    02:00-03:00 ET). In the weeks when the US and Europe are on different DST (2026: Mar 9-27, Oct 26-30) they sit one hour
    later in ET (04:00-05:00 and 03:00-04:00). Every other box is a New York window and stays as it is."""

    def _context(self):
        super()._context()
        import datetime as _dt
        from zoneinfo import ZoneInfo
        ny, be = ZoneInfo("America/New_York"), ZoneInfo("Europe/Berlin")
        self.dst_shift_days = []
        for x in self.ctx:
            d = _dt.date.fromisoformat(str(x["date"]))
            noon = _dt.datetime(d.year, d.month, d.day, 12, 0)
            off = (be.utcoffset(noon) - ny.utcoffset(noon)).total_seconds() / 3600
            if off == 6:
                continue
            self.dst_shift_days.append(str(x["date"]))
            s, e = x["s"], x["e"]
            md = self.mod[s:e]
            for nm, (a_, z_) in (("lon34", (240, 300)), ("lon23", (180, 240))):
                ii = np.flatnonzero((md >= a_) & (md < z_))
                ii = ii[md[ii] < 1080]
                if len(ii) >= 2:
                    x[nm] = (float(self.h[s + ii].max()), float(self.l[s + ii].min()), int(s + ii[-1]))


def dst():
    import pickle
    M = MarketDST(extra_boxes=P_LIVE["extra_boxes"])
    p = os.path.join(F.CACHE, f"litrep_dst_cands_{rl._data_key().replace(':', '_')}.pkl")
    if os.path.exists(p):
        C = pickle.load(open(p, "rb"))
    else:
        C = lit.candidates(M, ref=P_LIVE["ref"])
        pickle.dump(C, open(p, "wb"))
    B1, B5 = lit.bars_1m(M), lit.bars_5m(M)
    T = core(M, C, P_LIVE, F.SESS, B1, B5)
    o = F.score(T)
    b = F.score(run())
    d26 = [d for d in M.dst_shift_days if d >= "2026"]
    T0 = {(t["day"], t["entry_t"], t["pnl"]) for t in run() if t["day"] in d26}
    T1 = {(t["day"], t["entry_t"], t["pnl"]) for t in T if t["day"] in d26}
    print("DST-shifted days 2026:", d26, flush=True)
    print("trades on them  base:", sorted(T0), "\n  Berlin boxes:", sorted(T1), flush=True)
    print("Berlin-time European boxes:", F.fmt(o), flush=True)
    res = json.load(open(OUT)) if os.path.exists(OUT) else {}
    res["_dst"] = {**o, "dH1": o["H1"]["net"] - b["H1"]["net"], "dH2": o["H2"]["net"] - b["H2"]["net"],
                   "d21_25": o["2021-25"]["net"] - b["2021-25"]["net"], "days_2026": d26, "base_trades": sorted(T0),
                   "dst_trades": sorted(T1)}
    json.dump(res, open(OUT, "w"), indent=1, default=str)
    return T


# ================================================================================================ store runs
def rid_of(nm, n=48):
    rid = "lit_rep_" + "".join(ch if ch.isalnum() else "_" for ch in nm.lower())[:n].strip("_")
    while "__" in rid:
        rid = rid.replace("__", "_")
    return rid


def run_ids():
    """Variant name -> run id (48-char slug; the longer slug when two names share the first 48 characters)."""
    out, used = {}, set()
    for nm in V():
        rid = rid_of(nm)
        if rid in used:
            rid = rid_of(nm, 72)
        used.add(rid)
        out[nm] = rid
    return out


def save(only=None):
    res = json.load(open(OUT))
    b = res["_base"]
    ids = run_ids()
    for nm, (fam, X) in V().items():
        r = res.get(nm)
        if not r or (only and only not in nm):
            continue
        rid = ids[nm]
        T = run(_second_half(dict(X)))
        S = rl.score(T, F.SESS)
        o = F.score(T)
        status = "adopt-candidate" if r["both"] else "rejected"
        clean = [{k: v for k, v in t.items() if not k.startswith("_")} for t in T]
        rl.save(rid, "LIT live + report rule: " + nm, "other",
                "Owner order 2026-10-18: which codable rules of the LIT Complete Report improve LIT live in both halves of 2026?",
                params={**P_LIVE, "report_rule": nm, "chapter": fam}, trades=clean, scored=S, status=status,
                verdict=(f"{'BOTH halves better' if r['both'] else 'rejected'}: dH1 {r['dH1']:+,} dH2 {r['dH2']:+,}. 2026 H1 (pick) {h(o['H1'])}; "
                         f"2026 H2 (check) {h(o['H2'])}; 2026 {h(o['2026'])}; 2021-25 reference only {h(o['2021-25'])}"),
                notes="tools/lit_report.py core() = engine/lit.py _run_core copy with hooks; base lit_live (live_model.json lit) "
                      f"H1 {b['H1']['net']:+,} H2 {b['H2']['net']:+,}.", writeup="lit-report-tests", tags=["lit", "lit_report"])
        print("saved", rid, flush=True)
    if "_srr" in res and not only:
        T, comb = srr()
        for rid, title, TT in (("lit_rep_srr_v2", "Report ch.21 Session Range Reclaim V2 alone (benchmark)", T),
                               ("lit_rep_srr_v2_plus_lit", "LIT live + Session Range Reclaim V2 (first entry of the day wins)", comb)):
            if not T:
                print("SRR v2 made no trade in 2026: nothing to store as a run (the funnel is in report_results.json)", flush=True)
                break
            S = rl.score(TT, F.SESS)
            o = F.score(TT, spans=("H1", "H2", "2026"))
            rl.save(rid, title, "other", "The report's own illustrative model (chapter 21) as a simple comparison model for LIT",
                    params={"model": "srr_v2", "range": "08:00-09:25", "window": "09:30-10:30", "flat": "11:00", "target_r": 2},
                    trades=[dict(t) for t in TT], scored=S, status="rejected",
                    verdict=f"2026 H1 {h(o['H1'])}; H2 {h(o['H2'])}; 2026 {h(o['2026'])} (1m bars: 2026 only)",
                    notes="tools/lit_report.py srr_day on true 1m bars (lit.bars_1m full-coverage days).", writeup="lit-report-tests",
                    tags=["lit", "lit_report"])
            print("saved", rid, flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    arg = sys.argv[2] if len(sys.argv) > 2 else None
    {"check": check, "test": lambda: test(arg), "srr": srr, "save": lambda: save(arg), "dst": dst}[cmd]()
