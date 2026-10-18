"""LIT Advanced Decisions Report (owner, 2026-10-18), chapters 6, 8, 9, 10 and experiments 2-3 of chapter 13: breakeven versus
mitigation, partial exits at the first opposition, target choice from the entry location / remaining journey / deadline, and an
objective that is encountered before the entry fills.

Wraps engine/lit.py (not edited) on the live LIT settings (live_model.json "lit"). Same LIT signals: the same 5m setups, the same
30-min limit at the 5m CISD level, the same 1m CISD within 20 bars, the same stop 1 tick beyond the sweep extreme, the VIX-band
target (>= 1.5R, banked at 8R), BE at 1R, flat 15:55, 1 trade a day. With every option off the executor gives the live trades
(`check`: == research/runs/_cache/lit_2wk_unit_live.json, which is == run lit_live).

No look-ahead: structure (1m / 5m fractal swings, k=2) is used only once its confirming bar has closed; a decision made at a bar's
close acts from the next bar. Intrabar: the stop is checked before the target / partial / breakeven in the same bar (as live).
Options apply on days with true 1m bars (2026: 119 of 120 trades); 5m fall-back days trade as live.

Options (X):
  pre_sess   the VIX band (known from 18:00) was already traded between 18:00 and the setup: "keep" (live) | "skip" |
             "reval:<new>" (new objective, see below)
  pre_tap    the objective trades after the limit is placed and before it is tapped: "cancel" (live) | "keep" | "reval:<new>"
  pre_conf   the objective trades after the tap and before the 1m CISD fill: "keep" (live) | "cancel" | "reval:<new>"
             <new> = vix15 / vix2 (18:00 open +/- 1.5 / 2 VIX day moves) | pool (the nearest LIT pool beyond, untouched so far)
  be         {"r": trigger R or None, "off": pts beyond entry for the BE stop (costs = 1.0), "need": None | "sw1" (a confirmed
             1m higher low above the BE stop after the fill) | "sw5" (same on 5m) | "left" (a 1m close beyond the pre-pullback
             high = price has left the mitigation area), "pend": None | "ob50" (no BE while the zone's 50% between the limit
             and the stop is untouched) | "fvg1" (no BE while a 1m FVG left after the fill, bottom <= entry + 0.25R, is
             untouched)}; default {"r": 1.0, "off": 0.0}
  part       {"obst": "pool" | "struct" | "leg" | "all", "f": fraction, "min_r": R, "be": "keep" | "after" | "none"}: close f at
             the first obstacle >= min_r R from the fill and below the target (a resting limit, filled on a touch);
             be "after" = no BE at 1R, BE on the rest once the partial is filled
             obstacle sets: pool = LIT pools untouched at the fill (session boxes, PD/PW/PM, gaps, build-ups); leg = the
             pre-pullback high (the setup's own swing before the return to the limit); struct = pool + leg; all = + the 18:00
             and midnight opens
  tsel       target choice at the fill: {"mode": "loc"} (sweep extreme is not the session's extreme so far -> the first
             obstacle >= 1.5R, else the band) | {"mode": "journey", "u": u} (the session range so far >= u VIX day moves ->
             first obstacle) | {"mode": "deadline", "c": c} (target capped at c x the VIX move scaled to the minutes left to
             15:55, sqrt time, never under 1.5R) | {"mode": "near", "obst": set} (always the nearer); obst = obstacle set

Sizing / scoring: the live sizing, lit_sizing mode "two_week" (engine/sizing.py two_week_qty, config C: one winner passes, 60% of
the room, $1,000 soft daily loss cap, 40 micros, no weekly stop). Main metric: P(pass within 10 sessions) of a fresh MFFU
Builder 50K eval started on every session of H1 (Jan 2 - Jun 30) / H2 (Jul 1 - Oct 16), plus a 4,000-path Monte Carlo
(tools/lit_2wk.py). $, PF, win %, drawdown: the back-to-back eval path (a new eval after a pass, a fail or 10 sessions).
Costs: $1.40 per micro, 1 tick on market entries and on stop / BE / time exits.

  python -X utf8 tools/lit_adv_manage.py check     # options off == the live unit trades
  python -X utf8 tools/lit_adv_manage.py grid      # every variant -> research/lit/adv_results.json
  python -X utf8 tools/lit_adv_manage.py diag      # BE recoveries vs losses, partial continuation, first passage, pre-fill
  python -X utf8 tools/lit_adv_manage.py save      # rl.save the runs lit_adv_*
Paper only.
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
from engine import sizing as SZ  # noqa: E402
from tools import lit_final as F  # noqa: E402
from tools import lit_2wk as W  # noqa: E402

OUT = os.environ.get("ADV_OUT") or os.path.join(ROOT, "research", "lit", "adv_results2.json")
OUT_DIAG = os.path.join(ROOT, "research", "lit", "adv_diag.json")
PV, COMM, SLIP, TICK = lit.PV, lit.COMM, lit.SLIP, lit.TICK
LIVE = {**lit.DEFAULTS, **json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]}
_LM = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit_sizing"]
CFG = {**{k: _LM[k] for k in ("two_week", "safe_cap", "eval_ref_stop", "fast_ref_stop")}, "mode": "two_week",
       "two_week_until": _LM.get("two_week_until", 10), "after_mode": _LM.get("after_mode", "safe_eval")}
ECOMM = SZ.TW_COMM                   # MFFU MNQ round trip $1.90 (the eval scoring)
A50 = W.ACCT["50k"]
SPANS = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-12-31"), "2026": ("2026-01-01", "2026-12-31")}
S26 = [d for d in F.SESS if d >= "2026-01-01"]
BE_COST = 1.25                        # commission $1.90 / micro = 0.95 pt + 1 tick exit slippage 0.25 pt, rounded up to 5 ticks
XDEF = {"pre_sess": "keep", "pre_tap": "cancel", "pre_conf": "keep", "be": {"r": 1.0, "off": 0.0}, "part": None, "tsel": None,
        "t_check": None}
DIAG = []                             # pre-fill events of the last run (cancelled ones included)


# ================================================================================================ context
class Ctx:
    def __init__(self):
        self.M, self.C = F.market(LIVE["ref"], LIVE["extra_boxes"])
        self.B5 = F.bars(self.M, "5m")
        self.B1 = F.bars(self.M, "1m")
        self.sw = {}
        for B in (self.B1, self.B5):
            fh, fl = lit.fractals(B.h, B.l)
            a = np.zeros(B.n, bool); a[fh] = True
            b = np.zeros(B.n, bool); b[fl] = True
            self.sw[B.secs] = (a, b)

    def swing_low(self, d, secs):
        a, b = self.sw[secs]
        return b if d == 1 else a


_CTX = None


def ctx():
    global _CTX
    if _CTX is None:
        _CTX = Ctx()
    return _CTX


def X_of(X=None):
    o = {**XDEF, **(X or {})}
    o["be"] = {"r": 1.0, "off": 0.0, "need": None, "pend": None, **(o["be"] or {})} if o["be"] is not None else None
    return o


# ================================================================================================ objectives
def pools(z, d):
    """LIT pools beyond the trigger, untouched at the trigger bar (direction-space prices), all classes."""
    out = []
    for cls, L in z["targets"].items():
        for dist in L:
            out.append((z["entry_d"] + dist, cls))
    return sorted(out)


def obstacles(cx, z, d, mode, B, k0, upto, entry, H):
    """Opposing references between the fill and the target, untouched by bar upto-1 (direction space), sorted."""
    hi_d = B.dirs(d)[0]
    seen = float(hi_d[k0:upto].max()) if upto > k0 else -np.inf
    L = []
    if mode in ("pool", "struct", "all"):
        L += [(p, c) for p, c in pools(z, d)]
    if mode in ("leg", "struct", "all") and H is not None:
        L.append((H, "leg"))
    if mode == "all":
        M = cx.M
        x = M.ctx[z["k"]]
        L.append((x["open18"] * d, "o18"))
        i5 = int(np.searchsorted(M.t, B.t[upto - 1], side="right") - 1)
        ov = M.open_00[i5]
        if not np.isnan(ov):
            L.append((float(ov) * d, "o00"))
    return sorted((p, c) for p, c in L if p > entry + 1e-9 and p > seen)


def new_objective(cx, z, d, how, old, seen):
    """A replacement objective beyond `old` and beyond everything traded so far (`seen`), direction space; None = none."""
    x = cx.M.ctx[z["k"]]
    vm = x.get("vix_move")
    if how in ("vix15", "vix2") and vm:
        p = x["open18"] * d + (1.5 if how == "vix15" else 2.0) * LIVE["vix_k"] * vm
        return p if p > max(old, seen) else None
    if how == "pool":
        c = [p for p, _ in pools(z, d) if p > max(old, seen)]
        return min(c) if c else None
    return None


def band(cx, z):
    x = cx.M.ctx[z["k"]]
    vm = x.get("vix_move")
    return (x["open18"] * z["dir"] + LIVE["vix_k"] * vm, vm) if vm else (None, None)


# ================================================================================================ executor (unit size)
def asim(X, z, entry_px, tgt_lvl, fb, stop0, use1, pre_flag=None):
    cx = ctx(); M = cx.M
    P = LIVE
    B = cx.B1 if use1 else cx.B5
    on = use1 and B.secs == 60
    d = z["dir"]
    hi_d, lo_d, c_d, o_d = B.dirs(d)
    t0 = int(M.t[z["entry_i"]])
    k0 = int(np.searchsorted(B.t, t0))
    s_day = int(M.day_of[z["entry_i"]])
    if k0 >= B.n:
        return None
    flat = P["flat_mod"]
    wait_s = P["wait"] * 300
    cis = P.get("cisd1m")
    if cis and B.secs == 300:
        cis = max(1, cis // 5)
    ev = {"day": z["day"], "dir": d, "sess": pre_flag, "tap": None, "conf": None}
    tg_c = tgt_lvl
    limit_fill = True
    fill = tapped = None
    k = k0
    while k < B.n:
        if B.day[k] != s_day or B.mod[k] >= flat or B.mod[k] >= 1080:
            break
        if tapped is None and B.t[k] >= t0 + wait_s:
            break
        if lo_d[k] <= stop0:
            if tapped is None and lo_d[k] <= entry_px and not cis:
                fill = k; entry = min(entry_px, float(o_d[k]))
            break
        if tapped is None and lo_d[k] <= entry_px:
            if cis:
                tapped = k
            else:
                fill = k; entry = min(entry_px, float(o_d[k])); break
        if hi_d[k] >= tg_c and (tapped is None or (on and k > tapped)):
            ph = "tap" if tapped is None else "conf"
            act = X["pre_" + ph] if on else ("cancel" if ph == "tap" else "keep")
            ev[ph] = act
            if act == "cancel":
                ev["result"] = "cancelled"; DIAG.append(ev)
                return None
            if act.startswith("reval"):
                seen = float(hi_d[k0:k + 1].max())
                nw = new_objective(cx, z, d, act.split(":")[1], tg_c, seen)
                if nw is None:
                    ev["result"] = "no new objective"; DIAG.append(ev)
                    return None
                tg_c = nw
        if tapped is not None:
            if k - tapped > cis:
                break
            lowk = tapped + int(np.argmin(lo_d[tapped:k + 1]))
            cz = lit._cisd_level(c_d, o_d, lowk)
            if cz is not None and k > lowk and c_d[k] > cz[0] and k + 1 < B.n and B.day[k + 1] == s_day:
                fill = k + 1; entry = float(o_d[k + 1]) + SLIP; limit_fill = False
                break
        k += 1
    if fill is None:
        if ev["tap"] or ev["conf"] or ev["sess"]:
            ev["result"] = "no fill"; DIAG.append(ev)
        return None
    risk = entry - stop0
    if risk <= 0 or lit.qty_for(risk) < 1:
        return None
    # pre-pullback high: the 5m leg from the extreme to the trigger, then the 1m bars until the tap
    H5 = float(np.max(cx.B5.dirs(d)[0][z["ext_i"]:z["i"] + 1]))
    kt = tapped if tapped is not None else fill
    H = max(H5, float(hi_d[k0:kt].max())) if kt > k0 else H5
    if fb:
        tg = entry + P["fallback_rr"] * risk
    else:
        dist = tg_c - entry
        if dist < P["min_rr"] * risk:
            if ev["tap"] or ev["conf"] or ev["sess"]:
                ev["result"] = "under 1.5R"; DIAG.append(ev)
            return None
        tg = entry + (min(dist, P["max_rr"] * risk) if P["max_rr"] else dist)
    tg_live = tg
    # ---------------------------------------------------------------- target choice at the fill (ch10)
    tsel_why = None
    if on and X["tsel"]:
        o = X["tsel"]
        ob = obstacles(cx, z, d, o.get("obst", "struct"), B, k0, fill, entry, H)
        near = [p for p, _ in ob if p - entry >= P["min_rr"] * risk and p < tg]
        md = o["mode"]
        use_near = False
        if md == "near":
            use_near = True
        elif md == "loc":
            x = cx.M.ctx[z["k"]]
            lo5 = cx.B5.dirs(d)[1]
            use_near = float(lo5[z["ext_i"]]) > float(lo5[x["s"]:z["i"] + 1].min()) + 1e-9
        elif md == "journey":
            x = cx.M.ctx[z["k"]]
            vm = x.get("vix_move")
            rng = float(cx.M.h[x["s"]:z["i"] + 1].max() - cx.M.l[x["s"]:z["i"] + 1].min())
            use_near = bool(vm) and rng >= o["u"] * vm
        elif md == "deadline":
            x = cx.M.ctx[z["k"]]
            vm = x.get("vix_move")
            rem = max(1.0, flat - float(B.mod[fill]))
            if vm:
                cap = entry + max(P["min_rr"] * risk, o["c"] * vm * math.sqrt(rem / 1380.0))
                if cap < tg:
                    tg, tsel_why = cap, "deadline"
        if use_near and near:
            tg, tsel_why = near[0], md
    # ---------------------------------------------------------------- management (ch8 / ch9)
    be = X["be"] if on else {"r": P["be_r"], "off": 0.0, "need": None, "pend": None}
    if be is None:
        be = {"r": None, "off": 0.0, "need": None, "pend": None}
    be_r, be_off, need, pend = be["r"], float(be.get("off") or 0.0), be.get("need"), be.get("pend")
    if not on:
        be_r, be_off, need, pend = P["be_r"], 0.0, None, None
    pt = X["part"] if on else None
    p_lvl = None
    if pt:
        ob = obstacles(cx, z, d, pt["obst"], B, k0, fill, entry, H)
        c = [p for p, _ in ob if p - entry >= pt["min_r"] * risk and p < tg - 1e-9]
        p_lvl = c[0] if c else None
        if pt.get("be") == "none" or (pt.get("be") == "after" and p_lvl is not None):
            be_r, need, pend = None, None, None
    be_lvl = None if be_r is None else entry + be_r * risk
    any_be = be_r is not None or need is not None
    stopbe = entry + be_off
    mid = 0.5 * (entry_px + stop0)
    minlo = float(lo_d[tapped:fill].min()) if (tapped is not None and fill > tapped) else float(lo_d[fill])
    gaps = []                                      # untouched 1m FVGs after the fill (bottom, top)
    sl_b = cx.swing_low(d, B.secs)
    if need == "sw5":
        lo5d = cx.B5.dirs(d)[1]
        sl5 = cx.swing_low(d, 300)
        j5 = int(np.searchsorted(M.t, B.t[fill], side="left"))
    need_ok = need is None
    cur, be_done, mfe, mae, worst = stop0, False, 0.0, 0.0, 0.0
    part = None
    be_t = None
    tc = X["t_check"] if on else None
    cut = None
    k = fill
    exit_px = kind = None
    while k < B.n:
        if B.day[k] != s_day or B.mod[k] >= 1080:
            k -= 1; exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        if cut is not None:
            exit_px, kind = float(o_d[k]) - SLIP, cut; break
        mae = max(mae, (entry - lo_d[k]) / risk)
        worst = min(worst, lo_d[k] - entry)
        if lo_d[k] <= cur:
            exit_px, kind = cur - SLIP, ("BE" if be_done else "STOP"); break
        if not (k == fill and limit_fill):
            mfe = max(mfe, (hi_d[k] - entry) / risk)
            if p_lvl is not None and part is None and hi_d[k] >= p_lvl:
                part = (float(pt["f"]), p_lvl - entry)
                if pt.get("be") == "after" and not be_done:
                    cur, be_done, be_t = max(cur, stopbe), True, int(B.t[k])
            if hi_d[k] >= tg:
                exit_px, kind = tg, "TARGET"; break
        if B.mod[k] >= flat:
            exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        if tc and not be_done and (B.t[k] - B.t[fill]) / 60.0 + 1.0 == float(tc.get("at", 15)) \
                and mfe < float(tc.get("mfe", 0.5)) and c_d[k] < entry - float(tc.get("x", 0.3)) * risk \
                and k + 1 < B.n and B.day[k + 1] == s_day:
            cut = "CUT_T15"                  # research/lit/loss_learn_t15_patch.md: exit at the next 1m open
            k += 1
            continue
        # ---- end of bar k: breakeven decision (acts from bar k+1)
        if any_be and not be_done and not (k == fill and limit_fill):
            pend_now = False
            if pend == "ob50":
                pend_now = minlo > mid
            elif pend == "fvg1":
                pend_now = any(True for b_, t_ in gaps)
            if need == "sw1" and not need_ok:
                j = k - 2                                      # a swing at j is confirmed at the close of j + 2
                need_ok = j >= fill and bool(sl_b[j]) and lo_d[j] > stopbe
            elif need == "sw5" and not need_ok:
                ie = int(np.searchsorted(M.t, B.t[k] + B.secs - 300, side="right"))   # 5m bars closed by bar k's close
                while j5 < ie - 2 and not need_ok:
                    need_ok = bool(sl5[j5]) and lo5d[j5] > stopbe
                    j5 += 1
            elif need == "left" and not need_ok:
                need_ok = c_d[k] > H
            if need is None:
                go = be_lvl is not None and hi_d[k] >= be_lvl and not pend_now
            else:
                go = need_ok and (be_r is None or mfe >= be_r) and c_d[k] > stopbe and not pend_now
            if go:
                cur, be_done, be_t = max(cur, stopbe), True, int(B.t[k])
        # ---- state updates with bar k (known from its close)
        minlo = min(minlo, float(lo_d[k]))
        if pend == "fvg1":
            gaps = [(b_, t_) for b_, t_ in gaps if lo_d[k] > t_]
            if k >= fill + 1 and lo_d[k] > hi_d[k - 2] and hi_d[k - 2] <= entry + 0.25 * risk:
                gaps.append((float(hi_d[k - 2]), float(lo_d[k])))
        k += 1
    if exit_px is None:
        return None
    legs = [(1.0, exit_px - entry)]
    if part is not None:
        legs = [(part[0], part[1]), (1.0 - part[0], exit_px - entry)]
        kind = kind + "+P"
    xi5 = int(np.searchsorted(M.t, B.t[k], side="right") - 1)
    ob_struct = obstacles(cx, z, d, "struct", B, k0, fill, entry, H) if on else []
    return {"day": z["day"], "entry_t": int(B.t[fill]), "exit_t": int(B.t[k]) + B.secs, "exit_i": xi5, "dir": d,
            "risk": round(risk, 2), "tgt": round(tg - entry, 2), "tgt_live": round(tg_live - entry, 2), "exit": kind,
            "legs": legs, "pts": round(sum(w * p for w, p in legs), 4), "w1": round(worst, 4), "mfe": round(mfe, 3),
            "mae": round(min(mae, 1.0 + SLIP / risk), 3), "tf": B.secs // 60, "wk_m": 1.0, "be_t": be_t,
            "entry_px": round(entry * d, 2), "stop_px": round(stop0 * d, 2), "target_px": round(tg * d, 2),
            "tsel": tsel_why, "p_lvl": None if p_lvl is None else round((p_lvl - entry) / risk, 3),
            "obst1": [(round((p - entry) / risk, 3), c) for p, c in ob_struct[:4]], "pre": {k_: ev[k_] for k_ in ("sess", "tap", "conf")},
            "H_r": round((H - entry) / risk, 3), "on1": on, "z_i": z["i"], "fill_k": int(fill), "fill_secs": B.secs}


def arun(X=None, sessions=S26):
    X = X_of(X)
    cx = ctx(); M = cx.M
    P = LIVE
    names = set(P["sweep_names"]) if P.get("sweep_names") else None
    sset = set(sessions) if sessions else None
    out, busy, per_day = [], -1, collections.Counter()
    del DIAG[:]
    for z in cx.C:
        if sset is not None and z["day"] not in sset:
            continue
        if z["entry_i"] <= busy or per_day[z["day"]] >= P["max_per_day"]:
            continue
        if not lit.setup_ok(z, P, names):
            continue
        if P.get("monday") and lit.monday_block(M, z):
            continue
        ep = min(float(z["ref_d"]), z["trig_c"])
        stop0 = z["ext_d"] - P["stop_buf"]
        risk = ep - stop0
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
        use1 = P["tf"] == "1m" and int(M.day_of[z["entry_i"]]) in cx.B1.full
        tgt_lvl = ep + tp
        flag = None
        # ---- ch6: the band was already traded between 18:00 (first known) and the setup bar
        bp, vm = band(cx, z)
        if bp is not None and use1:
            x = M.ctx[z["k"]]
            hi5 = cx.B5.dirs(z["dir"])[0]
            seen = float(hi5[x["s"]:z["i"] + 1].max())
            if seen >= bp:
                flag = X["pre_sess"]
                if flag == "skip":
                    DIAG.append({"day": z["day"], "dir": z["dir"], "sess": "skip", "tap": None, "conf": None, "result": "skipped"})
                    continue
                if flag.startswith("reval"):
                    nw = new_objective(cx, z, z["dir"], flag.split(":")[1], bp, seen)
                    if nw is None or nw - ep < P["min_rr"] * risk:
                        DIAG.append({"day": z["day"], "dir": z["dir"], "sess": flag, "tap": None, "conf": None, "result": "no new objective"})
                        continue
                    tgt_lvl = ep + (min(nw - ep, P["max_rr"] * risk) if P["max_rr"] else nw - ep)
        t = asim(X, z, ep, tgt_lvl, fb, stop0, use1, flag)
        if t is None:
            continue
        busy = t["exit_i"]; per_day[z["day"]] += 1
        out.append(t)
    return out


_U = {}


def unit(X=None):
    key = json.dumps(X or {}, sort_keys=True, default=str)
    if key not in _U:
        _U[key] = (arun(X), list(DIAG))
    return _U[key][0]


# ================================================================================================ scoring (live two_week sizing)
def by_day(U):
    by = collections.defaultdict(list)
    for t in sorted(U, key=lambda t: t["entry_t"]):
        by[t["day"]].append(t)
    return [by.get(s, []) for s in S26]


def leg_pnl(t, q):
    legs = t["legs"]
    if len(legs) == 1:
        g = legs[0][1] * PV * q
    else:
        q1 = int(q * legs[0][0] + 1e-9)
        g = (q1 * legs[0][1] + (q - q1) * legs[1][1]) * PV
    return g - ECOMM * q


def run_eval(seq, by, horizon=20, keep=None, cfg=None):
    """One MFFU 50K eval, sized by engine/sizing.lit_qty exactly as the live loop (two_week for 10 sessions, then safe_eval),
    with partial legs (integer micros: int(q x f) out at the partial), commission $1.90."""
    cfg = cfg or CFG
    tgt, mll, dll, lockv = A50["target"], A50["mll"], A50["dll"], A50["lock"]
    bal = peak = 0.0
    floor = -mll
    for kk, si in enumerate(seq[:horizon]):
        cum = 0.0
        for t in by[si]:
            if cum <= -dll:
                break
            st = {"profit": bal, "cum": cum, "room": bal + cum - floor, "session": kk + 1, "n_today": 0}
            m0 = lit.qty_for(t["risk"])
            q = SZ.lit_qty(m0, {"risk_pts": t["risk"], "tgt_pts": t["tgt"], "size_mult": 1.0}, cfg, room=st["room"], state=st,
                           learning=None)["qty"] if m0 else 0
            if q <= 0:
                continue
            pnl = leg_pnl(t, q)
            low = min(0.0, t["w1"] * PV * q - ECOMM * q, pnl)
            if cum + low <= -dll:
                pnl = -dll - cum - SLIP * PV * q
                low = pnl
            rec = {**{k: t[k] for k in ("day", "entry_t", "exit_t", "dir", "exit", "risk", "tgt")}, "qty": q, "pnl": round(pnl, 2),
                   "low": round(low, 2), "risk_usd": round(t["risk"] * PV * q, 2)}
            if bal + cum + low <= floor:
                if keep is not None:
                    keep.append(rec)
                return "FAIL", kk + 1
            cum += pnl
            if keep is not None:
                keep.append(rec)
        bal += cum
        if bal <= floor:
            return "FAIL", kk + 1
        peak = max(peak, bal)
        floor = min(max(floor, peak - mll), lockv)
        if bal >= tgt:
            return "PASS", kk + 1
    return "OPEN", min(len(seq), horizon)


def span_ix(span):
    a, z = SPANS[span]
    ix = [i for i, d in enumerate(S26) if a <= d <= z]
    return ix[0], ix[-1] + 1


def evals(U, span):
    by = by_day(U)
    a, z = span_ix(span)
    res = [(run_eval(list(range(i, min(z, i + 20))), by), z - i) for i in range(a, z)]
    o = {}
    for lab, h in (("10", 10), ("20", 20)):
        R = [r for r, av in res if av >= h]
        N = len(R) or 1
        o["n" + lab] = len(R)
        o["p" + lab] = round(100.0 * sum(1 for r in R if r[0] == "PASS" and r[1] <= h) / N, 1)
        o["f" + lab] = round(100.0 * sum(1 for r in R if r[0] == "FAIL" and r[1] <= h) / N, 1)
    pas = [r[1] for r, _ in res if r[0] == "PASS" and r[1] <= 20]
    o["pass_med"] = float(np.median(pas)) if pas else None
    o["cost"] = round(W.PRICE["50k"] / (o["p10"] / 100.0)) if o["p10"] > 0 else None
    return o


_MC = {}


def mc(U, span, n=2000):
    by = by_day(U)
    a, z = span_ix(span)
    if (span, n) not in _MC:
        rng = np.random.default_rng(7)
        st = np.arange(a, z - 5 + 1)
        S = []
        for _ in range(n):
            seq = []
            while len(seq) < 20:
                j = int(rng.choice(st)); seq.extend(range(j, j + 5))
            S.append(seq[:20])
        _MC[(span, n)] = S
    res = [run_eval(s, by) for s in _MC[(span, n)]]
    N = len(res)
    return {"p10": round(100.0 * sum(1 for r in res if r[0] == "PASS" and r[1] <= 10) / N, 1),
            "f10": round(100.0 * sum(1 for r in res if r[0] == "FAIL" and r[1] <= 10) / N, 1)}


def b2b(U, span):
    """The owner's policy (no reset): a new eval only after a pass or a fail. Returns the path trades and pass/fail counts."""
    by = by_day(U)
    a, z = span_ix(span)
    k, T, n = a, [], collections.Counter()
    while k < z:
        r, used = run_eval(list(range(k, z)), by, z - k, keep=T)
        if r == "OPEN":
            n[r] += 1
            break
        n[r] += 1
        k += used
    return T, n


def stats(T, span):
    a, z = SPANS[span]
    ss = [d for d in S26 if a <= d <= z]
    TT = [t for t in T if a <= t["day"] <= z]
    if not TT:
        return {"n": 0}
    p = np.array([t["pnl"] for t in TT]); gl = -p[p < 0].sum()
    eq = np.cumsum(p); dd = float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min())
    wk = collections.Counter(lit.iso_week(t["day"]) for t in TT)
    allwk = {lit.iso_week(d) for d in ss}
    return {"n": len(TT), "tpw": round(len(TT) / (len(ss) / 5), 2), "wk2": round(100 * sum(wk[w] >= 2 for w in allwk) / len(allwk)),
            "win": round(100 * float((p > 0).mean()), 1), "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None,
            "net": round(float(p.sum())), "per_month": round(float(p.sum()) / (len(ss) / 21)), "dd": round(dd),
            "avg_win": round(float(p[p > 0].mean())) if (p > 0).any() else None,
            "avg_loss": round(float(p[p < 0].mean())) if (p < 0).any() else None,
            "exits": dict(collections.Counter(t["exit"] for t in TT))}


def unit_stats(U, span):
    """Per trade in R at unit size (exit mix, total R) - a size-free view."""
    a, z = SPANS[span]
    TT = [t for t in U if a <= t["day"] <= z]
    R = [t["pts"] / t["risk"] for t in TT]
    return {"n": len(TT), "tot_r": round(float(np.sum(R)), 2), "avg_r": round(float(np.mean(R)), 3) if R else None,
            "exits": dict(collections.Counter(t["exit"] for t in TT))}


def score(U):
    o = {}
    for s in ("H1", "H2"):
        T, n = b2b(U, s)
        o[s] = {**stats(T, s), **evals(U, s), "mc": mc(U, s), "b2b": f"{n['PASS']}/{n['FAIL']}/{n['OPEN']}", "unit": unit_stats(U, s)}
    return o


def line(nm, o):
    def f(s):
        if not s.get("n"):
            return "n=0"
        return (f"n={s['n']} {s['tpw']}/wk win {s['win']} PF {s['pf']} net {s['net']:+,} ${s['per_month']:,}/mo DD {s['dd']:,} "
                f"2w {s['p10']}/{s['f10']} mc {s['mc']['p10']}/{s['mc']['f10']} 1mo {s['p20']}/{s['f20']} R {s['unit']['tot_r']}")
    return f"{nm[:48]:48s} H1[{f(o['H1'])}] H2[{f(o['H2'])}]"


# ================================================================================================ check
def check():
    U = unit()
    ref = [t for t in json.load(open(W._unit_path("live")))["trades"] if t["day"] >= "2026"]
    ka = [(t["day"], t["entry_t"], t["exit"], round(t["pts"], 2), t["risk"], round(t["tgt"], 2)) for t in ref]
    kb = [(t["day"], t["entry_t"], t["exit"], round(t["pts"], 2), t["risk"], round(t["tgt"], 2)) for t in U]
    bad = [(x, y) for x, y in zip(ka, kb) if x != y]
    print(f"live unit trades 2026: {len(ka)} | adv executor off: {len(kb)} | mismatches {len(bad) + abs(len(ka) - len(kb))}")
    for x in bad[:5]:
        print("diff", x)
    o = score(U)
    print(line("live (two_week config C)", o))
    return not bad and len(ka) == len(kb)


# ================================================================================================ variants
T15 = {"at": 15, "x": 0.3, "mfe": 0.5}


def variants():
    """Round 2 (2026-10-18 evening): the live sizing two_week 10 sessions then safe_eval, $1.90, no reset; every idea
    alone and on top of the 15-minute check (t_check, research/lit/loss_learn_t15_patch.md)."""
    V = collections.OrderedDict()
    ideas = collections.OrderedDict()
    ideas["live"] = {}
    for off in (0.5, 1.0, 1.25, 1.5, 2.0, 3.0):
        ideas[f"BE at 1R to entry + {off} pts"] = {"be": {"r": 1.0, "off": off}}
    ideas["BE at 1R, not while ob50 pending"] = {"be": {"r": 1.0, "pend": "ob50"}}
    ideas["BE at 1R, not while ob50 pending, + 1.25 pts"] = {"be": {"r": 1.0, "pend": "ob50", "off": 1.25}}
    ideas["BE at 1R + sw5"] = {"be": {"r": 1.0, "need": "sw5"}}
    ideas["BE at 1.5R"] = {"be": {"r": 1.5}}
    ideas["no BE"] = {"be": {"r": None}}
    ideas["part 0.33 at first leg >= 1.0R, BE keep"] = {"part": {"obst": "leg", "f": 0.33, "min_r": 1.0, "be": "keep"}}
    ideas["part 0.5 at first struct >= 1.0R, BE after"] = {"part": {"obst": "struct", "f": 0.5, "min_r": 1.0, "be": "after"}}
    ideas["tsel deadline c=1.5"] = {"tsel": {"mode": "deadline", "c": 1.5}}
    ideas["tsel deadline c=2.0"] = {"tsel": {"mode": "deadline", "c": 2.0}}
    ideas["tsel journey >= 1.0 VIX moves"] = {"tsel": {"mode": "journey", "u": 1.0, "obst": "struct"}}
    ideas["tsel loc (struct)"] = {"tsel": {"mode": "loc", "obst": "struct"}}
    ideas["pre_sess reval:pool"] = {"pre_sess": "reval:pool"}
    for nm, X in ideas.items():
        V[nm] = X
        V[nm + " | t15"] = {**X, "t_check": T15}
    return V


def variants1():
    """Round 1 (2026-10-18 afternoon, two_week config C, $1.40, reset after 10 sessions): research/lit/adv_results.json."""
    V = collections.OrderedDict()
    V["live"] = {}
    # ---- ch6 / exp 3: the objective is encountered before the fill
    for a in ("skip", "reval:vix15", "reval:vix2", "reval:pool"):
        V[f"pre_sess {a}"] = {"pre_sess": a}
    for a in ("keep", "reval:vix15", "reval:vix2", "reval:pool"):
        V[f"pre_tap {a}"] = {"pre_tap": a}
    for a in ("cancel", "reval:vix15", "reval:vix2", "reval:pool"):
        V[f"pre_conf {a}"] = {"pre_conf": a}
    V["pre all cancel/skip"] = {"pre_sess": "skip", "pre_tap": "cancel", "pre_conf": "cancel"}
    V["pre all reval vix15"] = {"pre_sess": "reval:vix15", "pre_tap": "reval:vix15", "pre_conf": "reval:vix15"}
    # ---- ch8 / exp 2: breakeven versus mitigation
    V["no BE"] = {"be": {"r": None}}
    for r in (0.75, 1.25, 1.5, 2.0, 3.0):
        V[f"BE at {r}R"] = {"be": {"r": r}}
    V["BE at 1R to entry + costs"] = {"be": {"r": 1.0, "off": BE_COST}}
    V["BE at 1.5R to entry + costs"] = {"be": {"r": 1.5, "off": BE_COST}}
    for nd in ("sw1", "sw5", "left"):
        V[f"BE on {nd} only"] = {"be": {"r": None, "need": nd}}
        V[f"BE at 1R + {nd}"] = {"be": {"r": 1.0, "need": nd}}
    for pd in ("ob50", "fvg1"):
        V[f"BE at 1R, not while {pd} pending"] = {"be": {"r": 1.0, "pend": pd}}
        V[f"BE at 1R, not while {pd} pending, + costs"] = {"be": {"r": 1.0, "pend": pd, "off": BE_COST}}
    # ---- ch9: partial at the first opposition
    for ob in ("leg", "pool", "struct", "all"):
        for f in (0.5, 0.33):
            for mr in (1.0,):
                for bm in ("keep", "after"):
                    V[f"part {f} at first {ob} >= {mr}R, BE {bm}"] = {"part": {"obst": ob, "f": f, "min_r": mr, "be": bm}}
    V["part 0.5 at first struct >= 0.5R, BE after"] = {"part": {"obst": "struct", "f": 0.5, "min_r": 0.5, "be": "after"}}
    V["part 0.5 at first struct >= 2R, BE keep"] = {"part": {"obst": "struct", "f": 0.5, "min_r": 2.0, "be": "keep"}}
    V["part 0.25 at first struct >= 1R, BE keep"] = {"part": {"obst": "struct", "f": 0.25, "min_r": 1.0, "be": "keep"}}
    # ---- ch10: target from the entry location, the remaining journey, the deadline
    for ob in ("struct", "all"):
        V[f"tsel loc ({ob})"] = {"tsel": {"mode": "loc", "obst": ob}}
        V[f"tsel near ({ob})"] = {"tsel": {"mode": "near", "obst": ob}}
    for u in (0.75, 1.0, 1.25, 1.5):
        V[f"tsel journey >= {u} VIX moves"] = {"tsel": {"mode": "journey", "u": u, "obst": "struct"}}
    for c in (1.0, 1.5, 2.0, 2.5):
        V[f"tsel deadline c={c}"] = {"tsel": {"mode": "deadline", "c": c}}
    return V


def _load():
    return json.load(open(OUT)) if os.path.exists(OUT) else {}


def grid(only=None):
    res = _load()
    for nm, X in variants().items():
        if only and not any(s in nm for s in only):
            continue
        U = unit(X)
        o = score(U)
        o["X"] = X
        o["pre_events"] = collections.Counter(f"{e['sess'] or '-'}|{e['tap'] or '-'}|{e['conf'] or '-'}|{e.get('result', 'filled')}"
                                              for e in _U[json.dumps(X or {}, sort_keys=True, default=str)][1])
        o["n_pre"] = {ph: sum(1 for t in U if t["pre"][ph]) for ph in ("sess", "tap", "conf")}
        res[nm] = o
        print(line(nm, o), flush=True)
        json.dump(res, open(OUT, "w"), indent=1, default=float)
    return res


# ================================================================================================ diagnostics
def wilson(k, n, zc=1.96):
    if not n:
        return (None, None)
    ph = k / n
    den = 1 + zc * zc / n
    c = (ph + zc * zc / (2 * n)) / den
    h = zc * math.sqrt(ph * (1 - ph) / n + zc * zc / (4 * n * n)) / den
    return (round(100 * (c - h), 1), round(100 * (c + h), 1))


def live_qty(U):
    """The micros the live sizing gave each trade on the back-to-back path (H1 and H2), keyed by entry_t."""
    q = {}
    for s in ("H1", "H2"):
        T, _ = b2b(U, s)
        for t in T:
            q[t["entry_t"]] = t["qty"]
    return q


def walk(t, horizon_flat=True):
    """The market path after a live fill, ignoring every exit, to 15:55: first minute of each event (None = not by 15:55)."""
    cx = ctx(); B = cx.B1 if t["fill_secs"] == 60 else cx.B5
    d = t["dir"]
    hi_d, lo_d, c_d, o_d = B.dirs(d)
    k0 = t["fill_k"]
    e = t["entry_px"] * d; st = t["stop_px"] * d; tg = e + t["tgt"]; r = t["risk"]
    ob = t["obst1"][0][0] if t["obst1"] else None
    ev = {"stop": None, "target": None, "r1": None, "obst": None, "back_after_1r": None, "tgt_after_stop": None}
    k = k0
    day = B.day[k0]
    while k < B.n and B.day[k] == day and B.mod[k] < LIVE["flat_mod"] and B.mod[k] < 1080:
        m = (B.t[k] - B.t[k0]) / 60.0
        if ev["stop"] is None and lo_d[k] <= st:
            ev["stop"] = m
        if hi_d[k] >= tg:
            if ev["target"] is None:
                ev["target"] = m
            if ev["stop"] is not None and ev["tgt_after_stop"] is None:
                ev["tgt_after_stop"] = m
        if ev["r1"] is None and hi_d[k] >= e + r:
            ev["r1"] = m
        elif ev["r1"] is not None and ev["back_after_1r"] is None and lo_d[k] <= e and m > ev["r1"]:
            ev["back_after_1r"] = m
        if ob is not None and ev["obst"] is None and hi_d[k] >= e + ob * r:
            ev["obst"] = m
        k += 1
    return ev


def diag():
    out = {}
    L = unit()
    N = unit({"be": {"r": None}})
    qmap = live_qty(L)
    nb = {t["entry_t"]: t for t in N}
    # ---- ch8: what breakeven changes (paired, same trades)
    rows = []
    for t in L:
        y = nb.get(t["entry_t"])
        if y is None:
            continue
        q = qmap.get(t["entry_t"], 1)
        rows.append({"day": t["day"], "half": "H1" if t["day"] <= "2026-06-30" else "H2", "exit": t["exit"], "exit_nobe": y["exit"],
                     "z_r": round(t["pts"] / t["risk"], 3), "y_r": round(y["pts"] / y["risk"], 3), "b_r": round(t["tgt"] / t["risk"], 2),
                     "q": q, "z_usd": round(t["pts"] * PV * q - ECOMM * q, 2), "y_usd": round(y["pts"] * PV * q - ECOMM * q, 2)})
    be = {}
    for h in ("H1", "H2", "2026"):
        R = [r for r in rows if (h == "2026" or r["half"] == h)]
        ch = [r for r in R if r["exit"] == "BE"]
        rec = [r for r in ch if r["exit_nobe"] == "TARGET"]
        avo = [r for r in ch if r["exit_nobe"] == "STOP"]
        mid = [r for r in ch if r["exit_nobe"] not in ("TARGET", "STOP")]
        zbar = float(np.mean([r["z_r"] for r in ch])) if ch else 0.0
        bbar = float(np.mean([r["b_r"] for r in ch])) if ch else 0.0
        be[h] = {"trades": len(R), "reach_1r": sum(1 for r in R if r["exit"] == "BE" or r["exit"] == "TARGET" or r["z_r"] > 0.9),
                 "changed": len(ch), "recoveries": len(rec), "losses_avoided": len(avo), "other": len(mid),
                 "q_pct": round(100 * len(rec) / len(ch), 1) if ch else None, "q_ci95": wilson(len(rec), len(ch)),
                 "recovery_usd_removed": round(sum(r["y_usd"] - r["z_usd"] for r in rec)),
                 "loss_usd_avoided": round(sum(r["z_usd"] - r["y_usd"] for r in avo)),
                 "other_usd": round(sum(r["z_usd"] - r["y_usd"] for r in mid)),
                 "net_usd_be_vs_none": round(sum(r["z_usd"] - r["y_usd"] for r in ch)),
                 "net_r_be_vs_none": round(sum(r["z_r"] - r["y_r"] for r in ch), 2),
                 "z_mean_r": round(zbar, 3), "b_mean_r": round(bbar, 2),
                 "q_threshold_pct": round(100 * (zbar + 1) / (bbar + 1), 1) if ch else None,
                 "changed_list": [{k: r[k] for k in ("day", "exit_nobe", "z_r", "y_r", "q", "z_usd", "y_usd")} for r in ch]}
    out["be_vs_none"] = be
    # ---- ch9 / ch10: first passage after the fill (live trades, every exit ignored, to 15:55)
    fp = {}
    for h in ("H1", "H2", "2026"):
        TT = [t for t in L if t["on1"] and (h == "2026" or (t["day"] <= "2026-06-30") == (h == "H1"))]
        E = [(t, walk(t)) for t in TT]
        n = len(E)
        cum = {}
        for cut in (30, 60, 120, 240, 10 ** 9):
            tf = sum(1 for _, e in E if e["target"] is not None and e["target"] <= cut and (e["stop"] is None or e["target"] < e["stop"]))
            sf = sum(1 for _, e in E if e["stop"] is not None and e["stop"] <= cut and (e["target"] is None or e["stop"] <= e["target"]))
            cum["eod" if cut > 10 ** 8 else f"{cut}m"] = {"target_first": round(100 * tf / n, 1), "stop_first": round(100 * sf / n, 1),
                                                          "open": round(100 * (n - tf - sf) / n, 1)}
        tas = sum(1 for _, e in E if e["tgt_after_stop"] is not None)
        # obstacle (first struct obstacle) reached before the stop: then target-before-stop?
        ob = [(t, e) for t, e in E if t["obst1"] and e["obst"] is not None and (e["stop"] is None or e["obst"] < e["stop"])]
        p_ok = sum(1 for t, e in ob if e["target"] is not None and (e["stop"] is None or e["target"] < e["stop"]))
        a_ = [t["obst1"][0][0] for t, _ in ob]; b_ = [t["tgt"] / t["risk"] for t, _ in ob]
        # 1R reached, back to entry, then target (the BE paths)
        r1 = [(t, e) for t, e in E if e["r1"] is not None and (e["stop"] is None or e["r1"] < e["stop"])]
        back = [(t, e) for t, e in r1 if e["back_after_1r"] is not None and (e["target"] is None or e["back_after_1r"] < e["target"])]
        back_tgt = sum(1 for t, e in back if e["target"] is not None and (e["stop"] is None or e["target"] < e["stop"]))
        fp[h] = {"n": n, "cumulative": cum, "target_seen_after_stop": tas,
                 "obst_first": {"n": len(ob), "then_target_before_stop": p_ok, "p_pct": round(100 * p_ok / len(ob), 1) if ob else None,
                                "p_ci95": wilson(p_ok, len(ob)), "a_mean_r": round(float(np.mean(a_)), 2) if a_ else None,
                                "b_mean_r": round(float(np.mean(b_)), 2) if b_ else None,
                                "partial_pays_if_p_below_pct": round(100 * float(np.mean([(a + 1) / (b + 1) for a, b in zip(a_, b_)])), 1) if a_ else None},
                 "r1_first": len(r1), "back_to_entry_after_1r": len(back), "back_then_target": back_tgt,
                 "back_then_target_ci95": wilson(back_tgt, len(back)),
                 "obst_r_median": round(float(np.median([t["obst1"][0][0] for t in TT if t["obst1"]])), 2),
                 "obst_kinds": dict(collections.Counter(t["obst1"][0][1] for t in TT if t["obst1"])),
                 "no_obst": sum(1 for t in TT if not t["obst1"])}
    out["first_passage"] = fp
    # ---- ch6: the objective before the fill (live run)
    pre = collections.Counter()
    for t in L:
        for ph in ("sess", "tap", "conf"):
            if t["pre"][ph]:
                pre[f"filled, {ph} {t['pre'][ph]}, exit {t['exit']}"] += 1
    for e in _U[json.dumps({}, sort_keys=True)][1]:
        pre[f"{e['sess'] or '-'}|{e['tap'] or '-'}|{e['conf'] or '-'}|{e.get('result')}"] += 1
    out["pre_fill_live"] = dict(pre)
    out["pre_sess_trades"] = [{"day": t["day"], "exit": t["exit"], "r": round(t["pts"] / t["risk"], 2)} for t in L if t["pre"]["sess"]]
    out["pre_conf_trades"] = [{"day": t["day"], "exit": t["exit"], "r": round(t["pts"] / t["risk"], 2)} for t in L if t["pre"]["conf"]]
    json.dump(out, open(OUT_DIAG, "w"), indent=1, default=float)
    print(json.dumps({k: (v if k != "be_vs_none" else {h: {kk: vv for kk, vv in x.items() if kk != "changed_list"} for h, x in v.items()})
                      for k, v in out.items()}, indent=1, default=float))
    return out


# ================================================================================================ save
Q = ("LIT Advanced Decisions Report ch6/8/9/10 (owner 2026-10-18): does breakeven remove more recoveries than losses, do partials "
     "at the first opposition pay, should the target follow the entry location / journey / deadline, and what to do when the "
     "objective trades before the fill? Live two_week sizing, picked on 2026 H1, checked on H2.")
SAVES = [   # run id, variant name (round 2: live sizing two_week 10 sessions then safe_eval, $1.90, no reset)
    ("lit_adv_base", "live"), ("lit_adv_base_t15", "live | t15"),
    ("lit_adv_be_costs", "BE at 1R to entry + 1.25 pts"), ("lit_adv_be_costs_t15", "BE at 1R to entry + 1.25 pts | t15"),
    ("lit_adv_be_off_1", "BE at 1R to entry + 1.0 pts"), ("lit_adv_be_off_2", "BE at 1R to entry + 2.0 pts"),
    ("lit_adv_be_pend_ob50", "BE at 1R, not while ob50 pending"), ("lit_adv_be_pend_ob50_t15", "BE at 1R, not while ob50 pending | t15"),
    ("lit_adv_be_sw5", "BE at 1R + sw5"), ("lit_adv_be_sw5_t15", "BE at 1R + sw5 | t15"),
    ("lit_adv_be_1p5r", "BE at 1.5R"), ("lit_adv_no_be", "no BE"), ("lit_adv_no_be_t15", "no BE | t15"),
    ("lit_adv_part_leg_third", "part 0.33 at first leg >= 1.0R, BE keep"),
    ("lit_adv_part_struct_half_be_after", "part 0.5 at first struct >= 1.0R, BE after"),
    ("lit_adv_tsel_deadline_1p5", "tsel deadline c=1.5"), ("lit_adv_tsel_deadline_1p5_t15", "tsel deadline c=1.5 | t15"),
    ("lit_adv_tsel_deadline_2", "tsel deadline c=2.0"), ("lit_adv_tsel_deadline_2_t15", "tsel deadline c=2.0 | t15"),
    ("lit_adv_tsel_journey_1", "tsel journey >= 1.0 VIX moves"), ("lit_adv_tsel_loc", "tsel loc (struct)"),
    ("lit_adv_pre_sess_reval_pool", "pre_sess reval:pool"),
]


def verdict_of(o, base):
    up = lambda s, k: (o[s][k] or 0) > (base[s][k] or 0) + 1e-9
    dn = lambda s, k: (o[s][k] or 0) < (base[s][k] or 0) - 1e-9
    if all(o[s]["p10"] == base[s]["p10"] and o[s]["net"] == base[s]["net"] for s in ("H1", "H2")):
        return "info", "no change on the live trades"
    both_p = up("H1", "p10") and up("H2", "p10")
    both_n = up("H1", "net") and up("H2", "net")
    if both_p and both_n:
        return "promising", "better 2-week pass rate and more money in both halves"
    if both_n and not dn("H1", "p10") and not dn("H2", "p10") and not up("H1", "f10") and not up("H2", "f10"):
        return "promising", "more money in both halves, 2-week pass and fail rates not worse"
    if (up("H1", "p10") or up("H1", "net")) and not (up("H2", "p10") or up("H2", "net")):
        return "rejected", "H1 only"
    if (up("H2", "p10") or up("H2", "net")) and not (up("H1", "p10") or up("H1", "net")):
        return "rejected", "H2 only"
    if dn("H1", "p10") and dn("H2", "p10"):
        return "rejected", "fewer 2-week passes in both halves"
    return "rejected", "mixed: not better in both halves"


def save(only=None):
    from tools import runlib as rl
    res = _load()
    V = variants()
    for rid, nm in SAVES:
        if only and rid not in only:
            continue
        X = V[nm]
        U = unit(X)
        o = res.get(nm) or score(U)
        T = []
        for sp in ("H1", "H2"):
            T += b2b(U, sp)[0]
        for t in T:
            t["risk_pts"] = t["risk"]; t["r"] = round(t["pnl"] / t["risk_usd"], 3) if t["risk_usd"] else 0.0
        S = rl.score(T, S26)
        ref = "live | t15" if nm.endswith("| t15") else "live"
        st, why = verdict_of(o, res[ref]) if nm != ref else ("info", "reference: LIT live" + (" + the 15-minute check" if "t15" in nm else "")
                                                             + " with the live sizing")
        if rid in ("lit_adv_be_costs", "lit_adv_be_costs_t15") and st == "promising":
            st = "adopt-candidate"
        why += f" (vs {ref})"
        h = lambda s: (f"n={o[s]['n']} {o[s]['tpw']}/wk win {o[s]['win']}% PF {o[s]['pf']} net {o[s]['net']:+,} (${o[s]['per_month']:,}/mo) "
                       f"DD {o[s]['dd']:,}; 2-week pass/fail {o[s]['p10']}/{o[s]['f10']} (Monte Carlo {o[s]['mc']['p10']}/{o[s]['mc']['f10']}), "
                       f"1 month {o[s]['p20']}/{o[s]['f20']}, unit R {o[s]['unit']['tot_r']}")
        rl.save(rid, nm, "other", Q, params={**LIVE, **X_of(X)}, sizing={"mode": "two_week", **CFG}, trades=T, scored=S, status=st,
                verdict=f"{why}. 2026 H1 (pick) {h('H1')}; 2026 H2 (check) {h('H2')}. 2021-25: no 1m bars, not tested.",
                notes="tools/lit_adv_manage.py (wraps engine/lit.py; options off == the live unit trades == run lit_live). Sizing: the live "
                      "lit_sizing mode two_week (config C). Stored trades = the back-to-back eval path per half (a new eval after a pass, "
                      "a fail or 10 sessions); the eval columns in the verdict are fresh evals started on every session.",
                writeup="lit-adv-management", tags=["lit", "lit_adv"])
        print("saved", rid, st, why, flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        check()
    elif cmd == "grid":
        grid(sys.argv[2:] or None)
    elif cmd == "diag":
        diag()
    elif cmd == "save":
        save(sys.argv[2:] or None)
