"""HQ LIT: a higher-probability LIT without losing its payoff (owner 2026-10-23: "I need a strategy that trades 2+ times a week,
high-quality setups, with high probability and high profit").

Three parts, all on the live LIT (live_model.json "lit" = run lit_live), judged the LIT way: pick on 2026 H1 (Jan-Jun), check
untouched on 2026 H2 (Jul-Oct 16), 2021-25 a reference line (5m bars only there: the 15-minute check never acts).

  1. exits   trade-level exit redesign on the engine's own trades (same setups, same fills, same stops): a partial at 1R /
             1.5R / 2R + a runner to the VIX band, breakeven timing (0.75R / 1R / 1.5R / a confirmed 1m higher low / at the
             partial / none), a trail behind confirmed 5m (or 1m) swings after 2R, time exits, the 15-minute check thresholds.
             The re-walker reproduces engine/lit.py simulate_x exit for exit (check: 631/631 trades to the cent) and does the
             partial accounting per micro (int(q x f) micros out at the partial, the rest on the runner).
  2. grade   an A+/B/C grade from facts known at the fill (sweep depth, displacement, inducements, level type, session, VIX
             regime, distance to the target in R, stop width, PVSRA vector) -> size up A+ / size down C, never skip; a
             pre-registered textbook grade (no fitting) and a data grade fitted on H1 only; random-grade placebos.
  3. switch  the existing OFF switches re-scored on today's data and live rules: scale_in, cisd1m 22, room_f 0.55, the Asia slot
             (lit-more-entries lead 1), wk_loss_usd 1200, how_out 0.5 - each alone and all 64 combinations.

Two views, costs in ($1.90 a micro round trip everywhere + 1 tick on market entries and stop / BE / time exits):
  LIT size rule  $800 up to a 20-pt stop, then 800x20/stop, max 40 micros, weekly stop (= how run lit_live is scored, but at
                 $1.90 instead of $1.40 a micro: live H1 / H2 are ~$300 / ~$150 lower than the published lit_live)
  eval path      the live two_week sizing (engine/sizing.lit_qty: two_week for 10 sessions, then safe_eval, no reset) on the
                 trades as units; tools/lit_adv_manage + tools/lit_big_ideas scoring, extended here with the eval weekly loss
                 stop (state wk_pnl) and the how_out multiplier in the safe_eval phase (exactly what lit_qty does with them)

    python -X utf8 tools/hq_lit.py check      # re-walker == engine (631 trades), units == lit_adopt_combo, eval == published
    python -X utf8 tools/hq_lit.py exits      # part 1 -> research/hq/exits.json
    python -X utf8 tools/hq_lit.py grade      # part 2 -> research/hq/grade.json
    python -X utf8 tools/hq_lit.py switch     # part 3 -> research/hq/switch.json
    python -X utf8 tools/hq_lit.py save       # rl.save runs hq_lit_*
Paper only. Edits no engine file and no live_model*.json.
"""
from __future__ import annotations

import collections
import copy
import itertools
import json
import os
import random
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from engine import sizing as SZ  # noqa: E402
from tools import lit_final as F  # noqa: E402
from tools import lit_adopt_combo as AC  # noqa: E402
from tools import lit_big_ideas as BI  # noqa: E402  (patches lit_adv_manage.run_eval)
from tools import lit_adv_manage as A  # noqa: E402

OUTD = os.path.join(ROOT, "research", "hq")
LIVE = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]
CFG0 = copy.deepcopy(A.CFG)
PV, SLIP, TICK = lit.PV, lit.SLIP, lit.TICK
COMM = 1.90                                  # MFFU MNQ round trip (owner: $1.90 a micro + 1 tick)
SPAN = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-12-31"), "2026": ("2026-01-01", "2026-12-31"),
        "2021-25": ("2021-01-01", "2025-12-31")}
SESS = F.SESS
SCALE = {"pb": 0.25, "f": 1.0, "rat_k": 1.0, "min_rk": 2.0, "n": 1}          # CLAUDE.md scale-in config
ASIA = {"window": [[1080, 1440], [0, 930]], "all_hours": True, "max_per_day": 2,      # lit-more-entries lead 1 switch JSON
        "per_session": [[[1080, 120], [120, 1080]], 1], "kz": [[1080, 1440, {"max_rr": 3.0}], [0, 120, {"max_rr": 3.0}]]}


def sess_of(span):
    a, z = SPAN[span]
    return [d for d in SESS if a <= d <= z]


# ================================================================================================ market + swings
class Ctx:
    def __init__(self):
        self.M, self.C = F.market(LIVE["ref"], LIVE["extra_boxes"])
        self.B1, self.B5 = F.bars(self.M, "1m"), F.bars(self.M, "5m")
        self.cand = {(z["day"], int(z["i"]), int(z["dir"])): z for z in self.C}
        self.sw = {}
        for B in (self.B1, self.B5):
            fh, fl = lit.fractals(B.h, B.l)
            # last swing confirmed by the close of bar j (fractal at s, confirmed at s + 2): value per direction space
            for d, idx, val in ((1, fl, B.l), (-1, fh, -B.h)):
                last = np.full(B.n, np.nan)
                lix = np.full(B.n, -1, dtype=np.int64)
                conf = np.asarray(idx, dtype=np.int64) + 2
                ok = conf < B.n
                last[conf[ok]] = val[np.asarray(idx)[ok]]
                lix[conf[ok]] = np.asarray(idx)[ok]
                # forward fill within the array (a day change is handled by the caller: swing index >= the fill)
                m = ~np.isnan(last)
                pos = np.where(m, np.arange(B.n), -1)
                pos = np.maximum.accumulate(pos)
                vv = np.where(pos >= 0, last[np.maximum(pos, 0)], np.nan)
                ii = np.where(pos >= 0, lix[np.maximum(pos, 0)], -1)
                self.sw[(B.secs, d)] = (vv, ii)
        self.t5_close = self.B5.t + 300


_CX = None


def cx():
    global _CX
    if _CX is None:
        _CX = Ctx()
    return _CX


# ================================================================================================ engine runs
_RUNS = {}


def run(x=None, asia=False):
    """Engine trades of the live LIT + x (engine/lit.py run_x via tools/lit_final; asia -> the evening candidates)."""
    key = json.dumps([x or {}, asia], sort_keys=True, default=str)
    if key not in _RUNS:
        if asia:
            from tools import lit_all_hours as AH
            _RUNS[key] = AH.run({**LIVE, **ASIA, **(x or {})})
        else:
            _RUNS[key] = F.run({**LIVE, **(x or {})})
    return _RUNS[key]


def recost(T):
    """Engine trades ($1.40 a micro) -> $1.90 a micro (exact: commission is linear in micros)."""
    out = []
    for t in T:
        q = int(t.get("qty_total") or t["qty"])
        x = dict(t)
        x["pnl"] = round(t["pnl"] - (COMM - lit.COMM) * q, 2)
        x["low"] = round(min(t["low"] - (COMM - lit.COMM) * q, x["pnl"]), 2)
        x["r"] = round(x["pnl"] / t["risk_usd"], 3) if t["risk_usd"] else 0.0
        out.append(x)
    return out


# ================================================================================================ the re-walker
POL0 = {"be_r": 1.0, "be_off": None, "be_mode": "r", "tc": "live", "part": None, "trail": None, "tx": None, "flat": None}


def pol_of(p=None):
    o = {**POL0, **(p or {})}
    if o["be_off"] is None:
        o["be_off"] = float(LIVE.get("be_off") or 0.0)
    if o["tc"] == "live":
        o["tc"] = LIVE.get("t_check")
    if o["flat"] is None:
        o["flat"] = LIVE["flat_mod"]
    return o


def walk(t, pol, comm=COMM):
    """Re-walk one engine trade from its fill with exit policy pol (same entry, same stop, same target). Returns the trade
    at the LIT-rule qty of the engine trade (re-sized later by size_lit) with its unit legs. Bars: the trade's own (1m on true
    1m days, else 5m). Intrabar order as the engine: stop first, then the partial, the target, the breakeven move; a decision
    at a bar's close acts from the next bar."""
    c = cx()
    d = int(t["dir"])
    B = c.B1 if t.get("tf") == 1 else c.B5
    hi_d, lo_d, c_d, o_d = B.dirs(d)
    fill = int(np.searchsorted(B.t, int(t["entry_t"])))
    assert int(B.t[fill]) == int(t["entry_t"]), t["day"]
    entry, stop, tg = float(t["entry_px"]) * d, float(t["stop_px"]) * d, float(t["target_px"]) * d
    risk = entry - stop
    s_day = B.day[fill]
    tc = pol["tc"] if B.secs == 60 else None
    pt = pol["part"]
    plvl = entry + float(pt["r"]) * risk if pt else None
    tr = pol["trail"]
    trb = f_tr = None
    if tr:
        trb = c.B1 if (tr.get("tf", 5) == 1 and B.secs == 60) else c.B5
        f_tr = int(np.searchsorted(trb.t, int(B.t[fill]), side="right") - 1)     # the trail bar holding the fill
    tx = pol["tx"]
    cur, be, mfe, worst = stop, False, 0.0, 0.0
    part_px, cut, trailing = None, None, False
    k = fill
    ex = kind = None
    while k < B.n:
        if B.day[k] != s_day or B.mod[k] >= 1080:
            k -= 1; ex, kind = float(c_d[k]) - SLIP, "EOD"; break
        if cut is not None:
            ex, kind = float(o_d[k]) - SLIP, cut; break
        worst = min(worst, lo_d[k] - entry)
        if lo_d[k] <= cur:
            ex, kind = cur - SLIP, ("TRAIL" if trailing else ("BE" if be else "STOP")); break
        mfe = max(mfe, (hi_d[k] - entry) / risk)
        if pt and part_px is None and plvl < tg and hi_d[k] >= plvl:
            part_px = plvl
            if pol["be_mode"] == "part" and not be:
                cur, be = max(cur, entry + pol["be_off"]), True
        if hi_d[k] >= tg:
            ex, kind = tg, "TARGET"; break
        if pol["be_mode"] == "r" and pol["be_r"] is not None and not be and hi_d[k] >= entry + pol["be_r"] * risk:
            cur, be = entry + pol["be_off"], True
        if pol["be_mode"] == "sw1" and not be and B.secs == 60:
            vv, ii = c.sw[(60, d)]
            if ii[k] > fill and vv[k] > entry + pol["be_off"]:
                cur, be = entry + pol["be_off"], True
        if tr and mfe >= float(tr["after"]):
            if trb.secs == 60:
                j = k
            else:
                j = int(np.searchsorted(c.t5_close, int(B.t[k]) + B.secs, side="right") - 1)
            vv, ii = c.sw[(trb.secs, d)]
            if j >= 0 and ii[j] >= f_tr:
                lv = float(vv[j]) - float(tr.get("buf", TICK))
                if lv > cur and lv > entry:
                    cur, trailing = lv, True
                    be = True
        if B.mod[k] >= pol["flat"]:
            ex, kind = float(c_d[k]) - SLIP, "EOD"; break
        if tx:
            el = round((B.t[k] - B.t[fill]) / 60.0) + B.secs // 60
            if el == int(tx["min"]) and (c_d[k] - entry) / risk < float(tx["lo"]) and (not tx.get("pre_be") or not be) \
                    and k + 1 < B.n and B.day[k + 1] == s_day:
                cut = "TIME"
        if tc and not be and round((B.t[k] - B.t[fill]) / 60.0) + 1 == int(tc.get("at", 15)) \
                and mfe < float(tc.get("mfe", 0.5)) and c_d[k] < entry - float(tc.get("x", 0.3)) * risk:
            if k + 1 < B.n and B.day[k + 1] == s_day:
                cut = "CUT_T15"
        k += 1
    if ex is None:
        return None
    f = float(pt["f"]) if (pt and part_px is not None) else 0.0
    legs = [(f, part_px - entry), (1.0 - f, ex - entry)] if f > 0 else [(1.0, ex - entry)]
    out = {k_: t[k_] for k_ in ("day", "entry_t", "dir", "risk_pts", "entry_px", "stop_px", "target_px", "swept", "ind_n", "vec",
                                "i", "tf", "trigger")}
    out.update(exit=kind, exit_t=int(B.t[k]) + B.secs, legs=legs, pts=sum(w * p for w, p in legs), w1=min(0.0, worst),
               tgt=tg - entry, mfe=round(mfe, 3), part=part_px is not None, bars_held=int(k - fill + 1), comm=comm)
    return out


def leg_pnl(u, q, comm=COMM):
    L = u["legs"]
    if len(L) == 1:
        g = L[0][1] * PV * q
    else:
        q1 = int(q * L[0][0] + 1e-9)
        g = (q1 * L[0][1] + (q - q1) * L[1][1]) * PV
    return g - comm * q


def size_lit(W, how=1.0, wk=None, m_of=None, comm=COMM):
    """LIT size rule on walked trades: $800 up to 20 pts (lit.qty_for), x how_out outside the HOW window, x the weekly stop
    (after wk[0] STOP exits in the ISO week, x wk[1]), x a grade multiplier m_of(u) (rounded once, floor 1, max 40)."""
    wk = LIVE.get("wk_stop") if wk is None else wk
    out = []
    c = cx()
    for u in sorted(W, key=lambda u: u["entry_t"]):
        q0 = lit.qty_for(u["risk_pts"])
        m = 1.0
        z = c.cand.get((u["day"], int(u["i"]), int(u["dir"])))
        if how != 1.0 and z is not None and not z["how"]:
            m *= how
        if wk:
            if lit.week_stops(u["day"], u["entry_t"], out) >= wk[0]:
                m *= float(wk[1])
        if m_of is not None:
            m *= float(m_of(u))
        q = q0 if abs(m - 1.0) < 1e-9 else (max(1, int(q0 * m + 1e-9)) if m < 1 else min(lit.MAX_MICROS, int(q0 * m + 1e-9)))
        pnl = leg_pnl(u, q, comm)
        x = dict(u)
        x.update(qty=q, pnl=round(pnl, 2), risk_usd=round(u["risk_pts"] * PV * q, 2), r=round(pnl / (u["risk_pts"] * PV * q), 3),
                 low=round(min(0.0, u["w1"] * PV * q - comm * q, pnl), 2), mult=round(q / q0, 3) if q0 else 1.0,
                 half=q < q0, exit_i=0, mae=None, regime="")
        out.append(x)
    return out


def walk_all(T, pol=None):
    P = pol_of(pol)
    W = [walk(t, P) for t in T]
    return [w for w in W if w is not None]


# ================================================================================================ eval path
def units_of(W, m_of=None, how=1.0, blend=None):
    """Walked trades (2026) -> eval units (risk, tgt, pts, w1, legs, exit; m = grade multiplier; hm = how_out multiplier for
    the safe_eval phase; blend -> sizing target = the partial-weighted winner)."""
    c = cx()
    U = []
    for u in W:
        if u["day"] < "2026-01-01":
            continue
        x = {"day": u["day"], "entry_t": int(u["entry_t"]), "exit_t": int(u["exit_t"]), "dir": int(u["dir"]), "exit": u["exit"],
             "risk": float(u["risk_pts"]), "tgt": round(float(u["tgt"]), 4), "pts": round(float(u["pts"]), 4),
             "w1": round(float(u["w1"]), 4), "legs": [(w, round(p, 4)) for w, p in u["legs"]], "on1": u.get("tf") == 1}
        if blend:                            # research sizing: the target the two_week rule sizes on = the blended winner
            f_, r_ = float(blend["f"]), float(blend["r"])
            if r_ * x["risk"] < x["tgt"]:
                x["tgt_size"] = round(f_ * r_ * x["risk"] + (1 - f_) * x["tgt"], 4)
        if m_of is not None:
            x["m"] = float(m_of(u))
        if how != 1.0:
            z = c.cand.get((u["day"], int(u["i"]), int(u["dir"])))
            if z is not None and not z["how"]:
                x["hm"] = how
        U.append(x)
    return U


def engine_units(T, how=1.0):
    """Engine trades -> eval units (tools/lit_adopt_combo.units, + the x_m multiplier of the Asia slot, + how_out)."""
    T26 = [t for t in T if t["day"] >= "2026-01-01"]
    U = AC.units(T26)
    c = cx()
    for u, t in zip(U, T26):
        if t.get("x_m") is not None:
            u["m"] = float(t["x_m"])
        if how != 1.0:
            z = c.cand.get((t["day"], int(t["i"]), int(t["dir"]))) or evening_cand().get((t["day"], int(t["i"]), int(t["dir"])))
            if z is not None and not z["how"]:
                u["hm"] = how
    return U


_EVC = {}


def evening_cand():
    if not _EVC:
        from tools import lit_all_hours as AH
        _EVC.update({(z["day"], int(z["i"]), int(z["dir"])): z for z in AH.market()[1]})
    return _EVC


def run_eval_hq(seq, by, horizon=20, keep=None, cfg=None):
    """tools/lit_big_ideas.run_eval_x + the eval weekly loss stop (state wk_pnl: this eval's closed P&L of the ISO week, the
    live eval_state(today=) number) + the how_out multiplier on the base micros (lit_qty's safe_eval phase starts from the
    engine qty, which carries how_out; two_week ignores it, as live) + a sizing-target override t["tgt_size"]."""
    cfg = cfg or A.CFG
    tgt, mll, dll, lockv = A.A50["target"], A.A50["mll"], A.A50["dll"], A.A50["lock"]
    bal = peak = 0.0
    floor = -mll
    wk_pnl = collections.defaultdict(float)
    for kk, si in enumerate(seq[:horizon]):
        cum = 0.0
        day = A.S26[si]
        wk = lit.iso_week(day)
        for t in by[si]:
            if cum <= -dll:
                break
            st = {"profit": bal, "cum": cum, "room": bal + cum - floor, "session": kk + 1, "n_today": 0, "wk_pnl": wk_pnl[wk] + cum}
            m0 = lit.qty_for(t["risk"])
            if t.get("hm") and m0:
                m0 = max(1, int(m0 * float(t["hm"]) + 1e-9))
            q = SZ.lit_qty(m0, {"risk_pts": t["risk"], "tgt_pts": t.get("tgt_size", t["tgt"]), "size_mult": 1.0}, cfg,
                           room=st["room"], state=st, learning=None)["qty"] if m0 else 0
            if q <= 0:
                continue
            qfull = q
            m = float(t.get("m", 1.0))
            if m < 1.0 - 1e-9:
                q = max(1, int(q * m + 1e-9))
            elif m > 1.0 + 1e-9:
                q = max(q, min(int(q * m + 1e-9), BI._cap(t, st)))
            pnl, low, tot = BI.trade_pnl(t, q, qfull, st)
            if cum + low <= -dll:
                pnl = -dll - cum - SLIP * PV * tot
                low = pnl
            rec = {**{k: t[k] for k in ("day", "entry_t", "exit_t", "dir", "exit", "risk", "tgt")}, "qty": tot, "pnl": round(pnl, 2),
                   "low": round(low, 2), "risk_usd": round(t["risk"] * PV * q, 2)}
            if bal + cum + low <= floor:
                if keep is not None:
                    keep.append(rec)
                return "FAIL", kk + 1
            cum += pnl
            if keep is not None:
                keep.append(rec)
        bal += cum
        wk_pnl[wk] += cum
        if bal <= floor:
            return "FAIL", kk + 1
        peak = max(peak, bal)
        floor = min(max(floor, peak - mll), lockv)
        if bal >= tgt:
            return "PASS", kk + 1
    return "OPEN", min(len(seq), horizon)


A.run_eval = run_eval_hq


def eval_view(U, cfg=None):
    A.CFG = {**copy.deepcopy(CFG0), **(cfg or {})}
    if cfg and "two_week" in cfg:
        A.CFG["two_week"] = {**CFG0["two_week"], **cfg["two_week"]}
    try:
        o = BI.short(BI.score(U))
    finally:
        A.CFG = copy.deepcopy(CFG0)
    return o


def eval_path(U, cfg=None):
    """The back-to-back eval-path trades (H1 + H2) for rl.save."""
    A.CFG = {**copy.deepcopy(CFG0), **(cfg or {})}
    if cfg and "two_week" in cfg:
        A.CFG["two_week"] = {**CFG0["two_week"], **cfg["two_week"]}
    try:
        Tp = []
        for sp in ("H1", "H2"):
            Tp += A.b2b(U, sp)[0]
        c = copy.deepcopy(A.CFG)
    finally:
        A.CFG = copy.deepcopy(CFG0)
    for t in Tp:
        t["risk_pts"] = t["risk"]; t["r"] = round(t["pnl"] / t["risk_usd"], 3) if t["risk_usd"] else 0.0
        t.update(half=False, trigger="LIT-1m", mfe=None, mae=None, bars_held=None, regime="", mult=None, tgt_pts=t["tgt"])
    return Tp, c


# ================================================================================================ LIT-rule metrics
def mstats(T, span):
    ss = sess_of(span)
    a, z = SPAN[span]
    TT = [t for t in T if a <= t["day"] <= z]
    allwk = sorted({lit.iso_week(d) for d in ss})
    if not TT:
        return {"n": 0}
    p = np.array([t["pnl"] for t in TT]); r = np.array([float(t["r"]) for t in TT])
    gl = -p[p < 0].sum()
    eq = np.cumsum(p); dd = float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min())
    wkc = collections.Counter(lit.iso_week(t["day"]) for t in TT)
    mo = collections.defaultdict(float)
    for t in TT:
        mo[t["day"][:7]] += t["pnl"]
    ps = np.sort(p)[::-1]
    w05 = r >= 0.5
    return {"n": len(TT), "tpw": round(len(TT) / (len(ss) / 5), 2), "wk2": round(100 * sum(wkc[w] >= 2 for w in allwk) / len(allwk)),
            "win1": round(100 * float((r >= 1.0).mean()), 1), "win05": round(100 * float(w05.mean()), 1),
            "win0": round(100 * float((p > 0).mean()), 1), "loss": round(100 * float((r <= -0.5).mean()), 1),
            "be": round(100 * float(np.mean([t["exit"] == "BE" for t in TT])), 1),
            "avg_win_r": round(float(r[w05].mean()), 2) if w05.any() else None,
            "exp_r": round(float(r.mean()), 3), "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None,
            "net": round(float(p.sum())), "per_month": round(float(p.sum()) / (len(ss) / 21)), "dd": round(dd),
            "drop5": round(float(ps[5:].sum())), "months_up": f"{sum(1 for v in mo.values() if v > 0)}/{len(mo)}",
            "exits": dict(collections.Counter(t["exit"] for t in TT))}


def lit_view(T):
    return {s: mstats(T, s) for s in ("H1", "H2", "2026", "2021-25")}


def months(T):
    m = collections.defaultdict(float)
    for t in T:
        if t["day"] >= "2026-01-01":
            m[t["day"][:7]] += t["pnl"]
    return {k: round(v) for k, v in sorted(m.items())}


def day_pnl(T, days):
    m = collections.defaultdict(float)
    for t in T:
        m[t["day"]] += t["pnl"]
    return np.array([m.get(d, 0.0) for d in days])


def boot(Tv, Tb, span, n=4000, seed=11):
    days = sess_of(span)
    dv = day_pnl(Tv, days) - day_pnl(Tb, days)
    if not np.any(np.abs(dv) > 1e-6):
        return {"diff": 0, "lo": 0, "hi": 0, "p_le0": None}
    rng = np.random.default_rng(seed)
    ix = rng.integers(0, len(days), size=(n, len(days)))
    s = dv[ix].sum(1)
    return {"diff": round(float(dv.sum())), "lo": round(float(np.percentile(s, 5))), "hi": round(float(np.percentile(s, 95))),
            "p_le0": round(float((s <= 0).mean()), 3)}


def full(T, U, cfg=None, base=None):
    o = {"lit": lit_view(T), "eval": eval_view(U, cfg), "months": months(T)}
    if base is not None:
        o["boot_h1"] = boot(T, base, "H1")
        o["boot_h2"] = boot(T, base, "H2")
    return o


def line(nm, o):
    L, E = o["lit"], o["eval"]

    def f(s):
        x = L[s]
        return (f"{x['tpw']}/wk w1 {x['win1']} w.5 {x['win05']} BE {x['be']} PF {x['pf']} {x['net']:+,}" if x.get("n") else "n=0")

    def g(s):
        x = E[s]
        return f"{x['net']:+,} 2w {x['p10']}/{x['f10']} 1m {x['p20']}/{x['f20']} med {x['pass_med']}"
    return f"{nm[:26]:26s} H1[{f('H1')}] H2[{f('H2')}] 21-25[{L['2021-25'].get('net', 0):+,}] | ev H1[{g('H1')}] H2[{g('H2')}]"


def jdump(obj, name):
    os.makedirs(OUTD, exist_ok=True)
    p = os.path.join(OUTD, name)
    json.dump(obj, open(p, "w"), indent=1, default=float)
    return p


# ================================================================================================ check
def base_walk():
    T0 = run()
    return T0, walk_all(T0)


def check():
    T0 = run()
    Wc = [walk(t, pol_of(), comm=lit.COMM) for t in T0]
    bad = [(t["day"], t["exit"], w and w["exit"], t["pnl"], w and round(leg_pnl(w, t["qty"], lit.COMM), 2))
           for t, w in zip(T0, Wc) if w is None or w["exit"] != t["exit"] or abs(leg_pnl(w, t["qty"], lit.COMM) - t["pnl"]) > 0.05
           or int(w["exit_t"]) != int(t["exit_t"])]
    print(f"re-walker == engine (exit, exit time, P&L to 5 cents at the engine qty): {len(T0) - len(bad)}/{len(T0)}", flush=True)
    for b in bad[:8]:
        print("  diff", b)
    W = walk_all(T0)
    S = size_lit(W, comm=lit.COMM)
    qd = sum(1 for a, b in zip(sorted(T0, key=lambda t: t["entry_t"]), S) if a["qty"] != b["qty"])
    print(f"LIT size rule re-sized (weekly stop rebuilt) == engine qty: {len(S) - qd}/{len(S)}", flush=True)
    U1 = units_of(W)
    U2 = engine_units(T0)
    ud = sum(1 for a, b in zip(U1, U2) if (a["exit"], round(a["pts"], 2), round(a["w1"], 2), round(a["tgt"], 2))
             != (b["exit"], round(b["pts"], 2), round(b["w1"], 2), round(b["tgt"], 2)))
    print(f"walked units == lit_adopt_combo.units: {len(U1) - ud}/{len(U2)}", flush=True)
    e = eval_view(U1)
    print("eval path live:", {s: (e[s]["net"], e[s]["p10"], e[s]["f10"], e[s]["p20"], e[s]["f20"], e[s]["pass_med"]) for s in ("H1", "H2")},
          "(published lit_adopt_t15_be_off_eval: +34,253 57.1/5.9 | +9,059 52.2/0.0)", flush=True)
    o = lit_view(size_lit(W))
    print("LIT rule live at $1.90:", {s: (o[s]["n"], o[s]["net"], o[s]["pf"], o[s]["win05"]) for s in ("H1", "H2", "2021-25")}, flush=True)
    return not bad and not qd and not ud


# ================================================================================================ part 1: exits
def exit_variants():
    V = collections.OrderedDict()
    V["live"] = ("live exits (BE at 1R + 1.25 pts, 15-minute check, VIX band banked at 8R, flat 15:55)", {})
    for b in (0.5, 0.75, 1.25, 1.5, 2.0):
        V[f"be{b:g}"] = (f"BE at {b:g}R", {"be_r": b})
    V["be_none"] = ("no breakeven", {"be_r": None})
    V["be_sw1"] = ("BE after a confirmed 1m higher low above the BE price (structure), no R trigger", {"be_mode": "sw1"})
    for r in (1.0, 1.5, 2.0):
        for f in (0.25, 0.33, 0.5, 0.75):
            V[f"p{r:g}_{int(f * 100)}"] = (f"partial {int(f * 100)}% at {r:g}R, runner to the band, BE at 1R",
                                           {"part": {"r": r, "f": f}})
            if r > 1.0:
                V[f"p{r:g}_{int(f * 100)}_bep"] = (f"partial {int(f * 100)}% at {r:g}R, BE only when the partial fills",
                                                   {"part": {"r": r, "f": f}, "be_mode": "part"})
    for a in (1.5, 2.0, 3.0, 4.0):
        for tf in (5, 1):
            V[f"tr{a:g}_{tf}m"] = (f"trail behind confirmed {tf}m swings after {a:g}R", {"trail": {"after": a, "tf": tf, "buf": TICK}})
    V["p1_50_tr2_5m"] = ("partial 50% at 1R + trail the runner behind 5m swings after 2R",
                         {"part": {"r": 1.0, "f": 0.5}, "trail": {"after": 2.0, "tf": 5, "buf": TICK}})
    V["p1_33_tr2_5m"] = ("partial 33% at 1R + trail behind 5m swings after 2R",
                         {"part": {"r": 1.0, "f": 0.33}, "trail": {"after": 2.0, "tf": 5, "buf": TICK}})
    for mn in (30, 60, 90, 120, 180):
        for lo in (0.0, 0.5):
            V[f"tx{mn}_{lo:g}"] = (f"time exit: out at {mn} min when below {lo:g}R", {"tx": {"min": mn, "lo": lo}})
    V["tc_off"] = ("no 15-minute check", {"tc": None})
    for at in (10, 15, 20, 30):
        for x in (0.2, 0.3, 0.4):
            for mf in (0.3, 0.5, 0.7):
                if (at, x, mf) == (15, 0.3, 0.5):
                    continue
                V[f"tc{at}_{x:g}_{mf:g}"] = (f"15-minute check at {at} min, below -{x:g}R, MFE < {mf:g}R",
                                             {"tc": {"at": at, "x": x, "mfe": mf}})
    return V


def score_exit(T0, pol, base_T=None):
    W = walk_all(T0, pol)
    T = size_lit(W)
    o = full(T, units_of(W), base=base_T)
    if pol.get("part"):
        o["eval_blend"] = eval_view(units_of(W, blend=pol["part"]))
    o["n_part"] = sum(1 for w in W if w.get("part") and w["day"] >= "2026")
    return o, T, W


def exits():
    T0 = run()
    V = exit_variants()
    res = {"variants": {}}
    base = None
    for nm, (lab, pol) in V.items():
        o, T, _ = score_exit(T0, pol, base)
        if nm == "live":
            base = T
            o, T, _ = score_exit(T0, pol, base)
        o.update(label=lab, pol=pol)
        res["variants"][nm] = o
        print(line(nm, o) + (f" | blend H1 {o['eval_blend']['H1']['net']:+,} {o['eval_blend']['H1']['p10']}/{o['eval_blend']['H1']['f10']}"
                             f" H2 {o['eval_blend']['H2']['net']:+,} {o['eval_blend']['H2']['p10']}/{o['eval_blend']['H2']['f10']}"
                             if "eval_blend" in o else ""), flush=True)
    jdump(res, "exits.json")
    return res


# ================================================================================================ part 2: A+ grade
FEATS = ["depth", "disp", "idm_n", "idm_fresh", "htf", "london", "vix", "tgt_r", "stop", "vec"]
FEAT_LAB = {"depth": "sweep depth (ATR)", "disp": "displacement body (ATR)", "idm_n": "inducements taken first (<= 1 ATR, 36 bars)",
            "idm_fresh": "age of the nearest inducement (bars, lower = fresher)", "htf": "a PD / PW / PM level swept",
            "london": "entry before 08:00 ET (London)", "vix": "VIX close the day before", "tgt_r": "distance to the target (R)",
            "stop": "stop width (pts)", "vec": "PVSRA vector candle at the sweep"}


def feats(u):
    """Facts known at the fill (the 5m setup, the fill price, the planned stop and target): no look-ahead."""
    c = cx()
    z = c.cand[(u["day"], int(u["i"]), int(u["dir"]))]
    ia = [(float(dd), int(aa)) for dd, aa in (z.get("idm_a") or []) if dd <= 1.0 and aa <= 36]
    x = c.M.ctx[z["k"]]
    return {"depth": float(z["depth_atr"]), "disp": float(z["disp"]), "idm_n": len(ia),
            "idm_fresh": float(min(aa for _, aa in ia)) if ia else 99.0,
            "htf": float(any(k in ("pd", "pw", "pm") for k in z["swept_cls"])), "london": float(z["mod"] < 480),
            "vix": float(x.get("vix") or np.nan), "tgt_r": float(u["tgt"]) / float(u["risk_pts"]), "stop": float(u["risk_pts"]),
            "vec": float(bool(z["vec"]))}


def textbook_points(f):
    """Pre-registered LIT 'A+' checklist (playbook wording, thresholds fixed before looking at outcomes): an HTF level swept,
    strong displacement (>= 1.2 ATR), 2+ inducements, a deep sweep (>= 0.75 ATR), a PVSRA vector at the sweep, a fresh
    inducement (<= 6 bars = 30 min), a target >= 3R."""
    return int(f["htf"] > 0) + int(f["disp"] >= 1.2) + int(f["idm_n"] >= 2) + int(f["depth"] >= 0.75) + int(f["vec"] > 0) \
        + int(f["idm_fresh"] <= 6) + int(f["tgt_r"] >= 3.0)


def fit_grade(W, FF):
    """Data grade fitted on H1 only: per feature, the H1 median splits the trades; the side with the higher mean unit R in H1
    scores 1. Grade score = sum. A = H1 top third of the score, C = H1 bottom third (cut-offs from H1)."""
    H1 = [i for i, u in enumerate(W) if SPAN["H1"][0] <= u["day"] <= SPAN["H1"][1]]
    R = np.array([W[i]["pts"] / W[i]["risk_pts"] for i in H1])
    rule = {}
    for f in FEATS:
        v = np.array([FF[i][f] for i in H1])
        med = float(np.nanmedian(v))
        hi = v > med if len(set(v)) > 2 else v >= max(med, 0.5) if set(v) <= {0.0, 1.0} else v > med
        if hi.all() or (~hi).all():
            continue
        good_hi = R[hi].mean() >= R[~hi].mean()
        rule[f] = {"thr": med if not set(v) <= {0.0, 1.0} else 0.5, "hi_good": bool(good_hi),
                   "spread": round(float(abs(R[hi].mean() - R[~hi].mean())), 3)}
    sc = lambda ff: sum(int((ff[f] > r["thr"]) == r["hi_good"]) for f, r in rule.items())  # noqa
    s1 = np.array([sc(FF[i]) for i in H1])
    lo, hi = float(np.percentile(s1, 33.3)), float(np.percentile(s1, 66.7))
    return rule, sc, lo, hi


def grade_sets(W):
    FF = [feats(u) for u in W]
    G = {}
    tp = [textbook_points(f) for f in FF]
    h1p = [p for p, u in zip(tp, W) if SPAN["H1"][0] <= u["day"] <= SPAN["H1"][1]]
    print("textbook points H1:", sorted(collections.Counter(h1p).items()), flush=True)
    # the checklist is fixed in advance; A = 5+ of 7 points (top ~quarter of H1), C = 3 or fewer, B = 4 (outcomes not used)
    G["textbook"] = (["A" if p >= 5 else "C" if p <= 3 else "B" for p in tp],
                     "pre-registered textbook checklist of 7 points (A = 5+ points, B = 4, C = 3 or fewer)")
    rule, sc, lo, hi = fit_grade(W, FF)
    G["data"] = (["A" if sc(f) > hi else "C" if sc(f) <= lo else "B" for f in FF], f"data grade fitted on H1 ({len(rule)} "
                 f"median splits; A = score > {hi:g}, C = score <= {lo:g})")
    best = max(rule, key=lambda f: rule[f]["spread"])
    r = rule[best]
    G["single"] = (["A" if (f[best] > r["thr"]) == r["hi_good"] else "C" for f in FF],
                   f"single best H1 feature: {FEAT_LAB[best]} {'>' if r['hi_good'] else '<='} {r['thr']:g} = A, else C")
    return G, FF, rule


SCHEMES = collections.OrderedDict([("a15_c05", {"A": 1.5, "B": 1.0, "C": 0.5}), ("a125_c075", {"A": 1.25, "B": 1.0, "C": 0.75}),
                                   ("c05", {"A": 1.0, "B": 1.0, "C": 0.5}), ("a15", {"A": 1.5, "B": 1.0, "C": 1.0})])


def grade_score(W, labels, sch, base_T=None, fast=False):
    lab = {(u["day"], u["entry_t"]): g for u, g in zip(W, labels)}
    mo = lambda u: sch[lab[(u["day"], u["entry_t"])]]  # noqa
    T = size_lit(W, m_of=mo)
    if fast:
        return {s: round(sum(t["pnl"] for t in T if SPAN[s][0] <= t["day"] <= SPAN[s][1])) for s in ("H1", "H2", "2021-25")}, T
    U = units_of(W, m_of=mo)
    return full(T, U, base=base_T), T


def grade(n_placebo=300):
    T0 = run()
    W = walk_all(T0)
    W = sorted(W, key=lambda u: u["entry_t"])
    G, FF, rule = grade_sets(W)
    base_T = size_lit(W)
    res = {"rule": rule, "grades": {}, "feature_r": {}}
    # what each feature says, H1 (fit) and H2 (check), unit R by median split
    for f in FEATS:
        row = {}
        for sp in ("H1", "H2", "2021-25"):
            ix = [i for i, u in enumerate(W) if SPAN[sp][0] <= u["day"] <= SPAN[sp][1]]
            v = np.array([FF[i][f] for i in ix]); R = np.array([W[i]["pts"] / W[i]["risk_pts"] for i in ix])
            thr = rule.get(f, {}).get("thr", float(np.nanmedian(v)))
            hi = v > thr
            row[sp] = {"hi_r": round(float(R[hi].mean()), 3) if hi.any() else None, "lo_r": round(float(R[~hi].mean()), 3) if (~hi).any() else None,
                       "n_hi": int(hi.sum()), "n_lo": int((~hi).sum())}
        res["feature_r"][f] = row
        print(f"{f:10s} thr {rule.get(f, {}).get('thr')} " + " ".join(f"{sp}: hi {row[sp]['hi_r']} ({row[sp]['n_hi']}) lo {row[sp]['lo_r']} ({row[sp]['n_lo']})"
                                                                  for sp in row), flush=True)
    rng = random.Random(3)
    for gn, (labels, desc) in G.items():
        cnt = {sp: dict(collections.Counter(g for u, g in zip(W, labels) if SPAN[sp][0] <= u["day"] <= SPAN[sp][1]))
               for sp in ("H1", "H2", "2021-25")}
        res["grades"][gn] = {"desc": desc, "counts": cnt, "schemes": {}}
        # mean unit R by grade
        res["grades"][gn]["r_by_grade"] = {sp: {g: round(float(np.mean([u["pts"] / u["risk_pts"] for u, gg in zip(W, labels)
                                                                          if gg == g and SPAN[sp][0] <= u["day"] <= SPAN[sp][1]])), 3)
                                               for g in "ABC" if cnt[sp].get(g)} for sp in cnt}
        print(gn, desc, cnt, res["grades"][gn]["r_by_grade"], flush=True)
        for sn, sch in SCHEMES.items():
            o, T = grade_score(W, labels, sch, base_T)
            res["grades"][gn]["schemes"][sn] = o
            print(line(f"{gn}:{sn}", o), flush=True)
        # placebo: the same A/B/C counts per half, labels shuffled within each half (scheme a15_c05)
        pls = {"a15_c05": [], "a15": []}
        for _ in range(n_placebo):
            lab2 = list(labels)
            for sp in ("H1", "H2", "2021-25"):
                ix = [i for i, u in enumerate(W) if SPAN[sp][0] <= u["day"] <= SPAN[sp][1]]
                vals = [lab2[i] for i in ix]
                rng.shuffle(vals)
                for i, v in zip(ix, vals):
                    lab2[i] = v
            for sn in pls:
                pls[sn].append(grade_score(W, lab2, SCHEMES[sn], fast=True)[0])
        res["grades"][gn]["placebo"] = {}
        for sn, pl in pls.items():
            real = grade_score(W, labels, SCHEMES[sn], fast=True)[0]
            res["grades"][gn]["placebo"][sn] = {
                sp: {"real": real[sp], "pctile": round(100.0 * float(np.mean([p[sp] < real[sp] for p in pl])), 1),
                     "p50": round(float(np.median([p[sp] for p in pl]))), "p95": round(float(np.percentile([p[sp] for p in pl], 95)))}
                for sp in real}
        print("  placebo (a15_c05, LIT $):", res["grades"][gn]["placebo"], flush=True)
    jdump(res, "grade.json")
    return res


# ================================================================================================ part 3: the OFF switches
SWITCH = collections.OrderedDict([
    ("scale", ("scale-in after BE (scale_in)", {"scale_in": SCALE}, None)),
    ("c22", ("1m CISD window 22 bars (cisd1m 22)", {"cisd1m": 22}, None)),
    ("r55", ("two_week room cap 55% (room_f 0.55)", {}, {"two_week": {"room_f": 0.55}})),
    ("asia", ("Asia slot (lit-more-entries lead 1)", "asia", None)),
    ("wk12", ("eval weekly loss stop -$1,200 (wk_loss_usd 1200)", {}, {"wk_loss_usd": 1200})),
    ("how", ("half size outside the high/low-of-week window (how_out 0.5)", {"how_out": 0.5}, None)),
])


def combo(keys):
    x, cfg, asia = {}, {}, False
    for k in keys:
        _, px, pc = SWITCH[k]
        if px == "asia":
            asia = True
        else:
            x.update(px)
        for a, b in (pc or {}).items():
            cfg[a] = {**cfg.get(a, {}), **b} if isinstance(b, dict) else b
    return x, cfg, asia


def score_combo(keys, base_T=None):
    x, cfg, asia = combo(keys)
    T = recost(run(x, asia=asia))
    U = engine_units(run(x, asia=asia), how=float(x.get("how_out", 1.0)))
    o = full(T, U, cfg=cfg, base=base_T)
    o.update(keys=list(keys), params=x, cfg=cfg, asia=asia)
    return o, T


def switch():
    res = {"combos": {}}
    base, base_T = score_combo(())
    res["combos"]["live"] = base
    print(line("live", base), flush=True)
    keys = list(SWITCH)
    for n in range(1, len(keys) + 1):
        for ks in itertools.combinations(keys, n):
            o, _ = score_combo(ks, base_T)
            nm = "+".join(ks)
            res["combos"][nm] = o
            print(line(nm, o), flush=True)
    jdump(res, "switch.json")
    return res


# ================================================================================================ follow-up, tables, save
FOLLOW = collections.OrderedDict([
    # neighbours of the switch pick (scale + room 55% + weekly loss stop $1,200) and of the no-scale pick
    ("pick_wk1000", (("scale", "r55"), {"wk_loss_usd": 1000})),
    ("pick_wk1500", (("scale", "r55"), {"wk_loss_usd": 1500})),
    ("pick_r50", (("scale", "wk12"), {"two_week": {"room_f": 0.5}})),
    ("pick_r65", (("scale", "wk12"), {"two_week": {"room_f": 0.65}})),
    ("noscale_wk1000", (("r55",), {"wk_loss_usd": 1000})),
    ("noscale_wk1500", (("r55",), {"wk_loss_usd": 1500})),
    ("noscale_r50", (("wk12",), {"two_week": {"room_f": 0.5}})),
    ("noscale_r65", (("wk12",), {"two_week": {"room_f": 0.65}})),
])


def follow():
    res = {}
    _, base_T = score_combo(())
    for nm, (keys, c2) in FOLLOW.items():
        x, cfg, asia = combo(keys)
        for a, b in c2.items():
            cfg[a] = {**cfg.get(a, {}), **b} if isinstance(b, dict) else b
        T = recost(run(x, asia=asia))
        U = engine_units(run(x, asia=asia), how=float(x.get("how_out", 1.0)))
        o = full(T, U, cfg=cfg, base=base_T)
        o.update(keys=list(keys), params=x, cfg=cfg)
        res[nm] = o
        print(line(nm, o), flush=True)
    # the two small exit leads on top of the no-scale pick (the re-walker has no scale-in adds)
    for nm, pol in (("noscale+tx120_0", {"tx": {"min": 120, "lo": 0.0}}), ("noscale+tc_mfe07", {"tc": {"at": 15, "x": 0.3, "mfe": 0.7}})):
        W = walk_all(run(), pol)
        o = full(size_lit(W), units_of(W), cfg=combo(("r55", "wk12"))[1], base=base_T)
        res[nm] = o
        print(line(nm, o), flush=True)
    jdump(res, "follow.json")
    return res


def _k(v):
    return f"{v / 1000:+.1f}k" if v is not None else "-"


def row_q(lab, o):
    """quality row per half: trades/wk, % weeks 2+, win >= 1R / >= 0.5R / > $0, BE %, loss <= -0.5R %, avg winner R, expectancy R"""
    L = o["lit"]
    c = []
    for s in ("H1", "H2"):
        x = L[s]
        c.append(f"{x['tpw']} · {x['wk2']}% · {x['win1']} / {x['win05']} / {x['win0']} · {x['be']} · {x['loss']} · "
                 f"{x['avg_win_r']} · {x['exp_r']:+.2f}")
    return f"| {lab} | " + " | ".join(c) + " |"


def row_m(lab, o):
    L, E = o["lit"], o["eval"]
    return (f"| {lab} | {L['H1']['pf']} / {L['H2']['pf']} | {_k(L['H1']['net'])} / {_k(L['H2']['net'])} | ${L['H2']['per_month']:,} | "
            f"{_k(L['2021-25'].get('net'))} | {_k(L['2026']['dd'])} | {_k(L['H1']['drop5'])} / {_k(L['H2']['drop5'])} | "
            f"{_k(E['H1']['net'])} / {_k(E['H2']['net'])} | {E['H1']['p10']}/{E['H1']['f10']} · {E['H2']['p10']}/{E['H2']['f10']} | "
            f"{E['H1']['p20']}/{E['H1']['f20']} · {E['H2']['p20']}/{E['H2']['f20']} | {E['H1']['pass_med']} / {E['H2']['pass_med']} |")


HQ = ("| variant | H1: trades/wk · weeks 2+ · win >= 1R / >= 0.5R / > $0 · BE % · loss <= -0.5R % · avg winner R · "
      "expectancy R | H2: same |\n|---|---|---|")
HM = ("| variant | PF H1 / H2 | LIT $ H1 / H2 | H2 $/month | 2021-25 $ | max DD 2026 | $ without the best 5 H1 / H2 | "
      "eval $ H1 / H2 | eval 2-wk pass/fail H1 · H2 | eval 1-mo pass/fail H1 · H2 | median sessions to pass H1 / H2 |\n"
      "|---|---|---|---|---|---|---|---|---|---|---|")


def tables(path_md):
    E = json.load(open(os.path.join(OUTD, "exits.json")))["variants"]
    G = json.load(open(os.path.join(OUTD, "grade.json")))
    S = json.load(open(os.path.join(OUTD, "switch.json")))["combos"]
    pf = os.path.join(OUTD, "follow.json")
    Fw = json.load(open(pf)) if os.path.exists(pf) else {}
    L = ["\n### Appendix A - every exit variant: quality (LIT size rule)\n\n" + HQ]
    for nm, o in E.items():
        L.append(row_q(f"{o['label']} (`{nm}`)", o))
    L.append("\n### Appendix B - every exit variant: money and eval path (partial rows twice: live sizing, then the blended "
             "sizing target)\n\n" + HM)
    for nm, o in E.items():
        L.append(row_m(f"`{nm}`", o))
        if "eval_blend" in o:
            L.append(row_m(f"`{nm}` + blended sizing target", {**o, "eval": o["eval_blend"]}))
    L.append("\n### Appendix C - grades x size schemes\n\n" + HM)
    for gn, g in G["grades"].items():
        for sn, o in g["schemes"].items():
            L.append(row_m(f"{gn} {sn}", o))
    L.append("\n### Appendix D - all 64 switch combinations: money and eval path\n\n" + HM)
    for nm, o in S.items():
        L.append(row_m(f"`{nm}`", o))
    L.append("\n### Appendix D2 - all 64 switch combinations: quality\n\n" + HQ)
    for nm, o in S.items():
        L.append(row_q(f"`{nm}`", o))
    if Fw:
        L.append("\n### Appendix E - neighbours of the picks\n\n" + HM)
        for nm, o in Fw.items():
            L.append(row_m(f"`{nm}`", o))
    open(path_md, "w").write("\n".join(L) + "\n")
    print("wrote", path_md)


def mtest():
    """How many variants beat live in both halves (LIT $ / eval $ / eval odds), vs a coin-flip expectation."""
    E = json.load(open(os.path.join(OUTD, "exits.json")))["variants"]
    G = json.load(open(os.path.join(OUTD, "grade.json")))["grades"]
    S = json.load(open(os.path.join(OUTD, "switch.json")))["combos"]
    b = S["live"]
    V = {**{"exit:" + k: v for k, v in E.items() if k != "live"},
         **{f"grade:{g}:{s}": o for g, d in G.items() for s, o in d["schemes"].items()},
         **{"switch:" + k: v for k, v in S.items() if k != "live"}}
    rows = []
    for nm, o in V.items():
        l, e = o["lit"], o["eval"]
        if all(l[s]["net"] == b["lit"][s]["net"] and e[s]["net"] == b["eval"][s]["net"] for s in ("H1", "H2")):
            continue
        rows.append({"nm": nm, "lit": [l[s]["net"] - b["lit"][s]["net"] for s in ("H1", "H2")],
                     "ev": [e[s]["net"] - b["eval"][s]["net"] for s in ("H1", "H2")],
                     "odds": [round(e[s]["p10"] - b["eval"][s]["p10"] - (e[s]["f10"] - b["eval"][s]["f10"]), 1) for s in ("H1", "H2")],
                     "win05": [round(l[s]["win05"] - b["lit"][s]["win05"], 1) for s in ("H1", "H2")],
                     "p": o.get("boot_h2", {}).get("p_le0")})
    n = len(rows)
    out = {"n": n,
           "both_halves_lit": [r["nm"] for r in rows if min(r["lit"]) > 0],
           "both_halves_all": [r["nm"] for r in rows if min(r["lit"]) > 0 and min(r["ev"]) > 0 and min(r["odds"]) >= 0],
           "win05_up_money_kept": [r["nm"] for r in rows if min(r["win05"]) > 0 and min(r["lit"]) >= 0],
           "coin_flip_both": round(n / 4), "coin_flip_all": round(n / 16), "rows": rows}
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=1))
    jdump(out, "mtest.json")
    return out


Q = ("Owner 2026-10-23: 'I need a strategy that trades 2+ times a week, high-quality setups, with high probability and high "
     "profit.' Can LIT become a higher-probability strategy without losing its payoff (exits, A+ grade sizing, the OFF switches)?")


def _h(s):
    return (f"n={s['n']} {s['tpw']}/wk win>=1R {s['win1']}% >=0.5R {s['win05']}% BE {s['be']}% PF {s['pf']} net {s['net']:+,} "
            f"(${s['per_month']:,}/mo) DD {s['dd']:,}")


def _he(s):
    return (f"PF {s['pf']} net {s['net']:+,} (${s['per_month']:,}/mo) DD {s['dd']:,}; 2-week pass/fail {s['p10']}/{s['f10']} "
            f"(Monte Carlo {s['mc_p10']}/{s['mc_f10']}), 1 month {s['p20']}/{s['f20']}, median {s['pass_med']} sessions")


def save_one(rid, title, T, U, cfg=None, params=None, status="info", head="", note="", family="other"):
    from tools import runlib as rl
    o = full(T, U, cfg=cfg)
    l, e = o["lit"], o["eval"]
    keep = ("day", "entry_t", "exit_t", "dir", "r", "pnl", "risk_pts", "qty", "risk_usd", "half", "exit", "trigger", "mfe", "mae",
            "bars_held", "regime", "mult", "low", "entry_px", "stop_px", "target_px")
    Ts = [{k: t.get(k) for k in keep} for t in T]
    P = {**lit.DEFAULTS, **LIVE, **(params or {})}
    rl.save(rid, title, family, Q, params=P, trades=Ts, scored=rl.score(Ts, F.SESS), status=status,
            verdict=f"{head} LIT size rule ($1.90 a micro): 2026 H1 (pick) {_h(l['H1'])}; H2 (check) {_h(l['H2'])}; 2021-25 "
                    f"reference {_h(l['2021-25'])}. Eval path (two_week{(', ' + json.dumps(cfg)) if cfg else ''}): H1 {_he(e['H1'])}; "
                    f"H2 {_he(e['H2'])}.",
            notes="tools/hq_lit.py: " + (note or "engine/lit.py run_x on live_model.json lit + these params."),
            writeup="hq-lit", tags=["lit", "hq_lit"])
    Tp, c = eval_path(U, cfg)
    rl.save(rid + "_eval", title + " (eval path, two_week sizing)", family, Q, params=P, sizing={"mode": "two_week", **c}, trades=Tp,
            scored=rl.score(Tp, A.S26), status=status,
            verdict=f"{head} Eval path: H1 (pick) {_he(e['H1'])}. H2 (check) {_he(e['H2'])}. 2021-25: no 1m bars.",
            notes="tools/hq_lit.py: the trades as units, sized by the live two_week rules (stored trades = the back-to-back eval "
                  "path per half).", writeup="hq-lit", tags=["lit", "hq_lit"])
    print("saved", rid, flush=True)


EXIT_SAVE = (("p1_50", "LIT + partial 50% at 1R, runner to the VIX band (BE at 1R)", {"part": {"r": 1.0, "f": 0.5}}, "rejected"),
             ("p2_33", "LIT + partial 33% at 2R, runner to the VIX band", {"part": {"r": 2.0, "f": 0.33}}, "rejected"),
             ("be_none", "LIT without breakeven", {"be_r": None}, "rejected"),
             ("be_sw1", "LIT with BE after a confirmed 1m higher low (structure)", {"be_mode": "sw1"}, "rejected"),
             ("tr2_5m", "LIT + trail behind confirmed 5m swings after 2R", {"trail": {"after": 2.0, "tf": 5, "buf": TICK}}, "rejected"),
             ("tx120_0", "LIT + time exit at 120 minutes when below 0R", {"tx": {"min": 120, "lo": 0.0}}, "info"),
             ("tc_mfe07", "LIT 15-minute check with MFE < 0.7R (was 0.5R)", {"tc": {"at": 15, "x": 0.3, "mfe": 0.7}}, "info"))
GRADE_SAVE = (("textbook", "a15_c05", "rejected"), ("data", "a15_c05", "rejected"), ("single", "a15", "promising"))
SWITCH_SAVE = ((("scale",), "adopt-candidate"), (("c22",), "adopt-candidate"), (("r55",), "adopt-candidate"), (("asia",), "promising"),
               (("wk12",), "adopt-candidate"), (("how",), "rejected"), (("scale", "r55", "wk12"), "adopt-candidate"),
               (("c22", "r55", "wk12"), "adopt-candidate"))


def save():
    from tools import runlib as rl
    idx = rl.index
    rl.index = lambda: None              # one index rebuild at the end
    try:
        T0 = run()
        W0 = walk_all(T0)
        save_one("hq_lit_live", "LIT live at $1.90 a micro (HQ study reference)", size_lit(W0), units_of(W0),
                 head="Reference: live LIT, re-walked (== engine 631/631).")
        for nm, title, pol, st in EXIT_SAVE:
            W = walk_all(T0, pol)
            save_one("hq_lit_" + nm, title, size_lit(W), units_of(W), status=st, head="HQ exits: " + title + ".",
                     params={"hq_exit": pol}, family="management",
                     note="the engine's own trades re-walked from the fill with this exit policy (partial: int(q x f) micros out "
                          "at the partial price, the rest on the runner).")
        W = sorted(W0, key=lambda u: u["entry_t"])
        Gs, _, _ = grade_sets(W)
        for gn, sn, st in GRADE_SAVE:
            lab = {(u["day"], u["entry_t"]): g for u, g in zip(W, Gs[gn][0])}
            sch = SCHEMES[sn]
            mo = lambda u, lab=lab, sch=sch: sch[lab[(u["day"], u["entry_t"])]]  # noqa
            save_one(f"hq_lit_grade_{gn}_{sn}", f"LIT + grade sizing: {Gs[gn][1]}, scheme {sn}", size_lit(W, m_of=mo),
                     units_of(W, m_of=mo), status=st, head=f"HQ grade ({Gs[gn][1]}; scheme {sn} = {sch}).",
                     params={"hq_grade": gn, "scheme": sch}, family="risk")
        for keys, st in SWITCH_SAVE:
            x, cfg, asia = combo(keys)
            T = recost(run(x, asia=asia))
            U = engine_units(run(x, asia=asia), how=float(x.get("how_out", 1.0)))
            lab = " + ".join(SWITCH[k][0] for k in keys)
            save_one("hq_lit_sw_" + "_".join(keys), "LIT + " + lab, T, U, cfg=cfg or None,
                     params={**x, **({"asia_slot": ASIA} if asia else {})}, status=st, head="HQ switch re-score: " + lab + ".")
    finally:
        rl.index = idx
    rl.index()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        check()
    elif cmd == "exits":
        exits()
    elif cmd == "grade":
        grade()
    elif cmd == "switch":
        switch()
    elif cmd == "follow":
        follow()
    elif cmd == "tables":
        tables(sys.argv[2])
    elif cmd == "mtest":
        mtest()
    elif cmd == "save":
        save()
