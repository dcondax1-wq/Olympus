"""LIT untested ENTRY ideas (owner, 2026-10-18: "Remember our strategy is LIT based nothing that goes outside, try every single
one of these and go find more we haven't tested").

Wraps engine/lit.py (not edited) on the live LIT settings (live_model.json "lit" = lit_final + loss pack) with the live eval
sizing ($800 up to a 25-pt stop, then 800x25/stop, weekly stop, never more than 60% of the room to the MFFU max-loss floor:
engine/sizing.py lit_qty mode "eval" = run lit_tight_eval_800_25_room60). The LIT setups, the stop (1 tick beyond the sweep
extreme), the VIX-band target (>= 1.5R from the real fill, banked at 8R), breakeven at 1R and the 15:55 flat are the live ones.
Only HOW and WHEN the trade is entered changes:

  1. buy-stop entry (ent="bstop", bs_k=K): after the 1m CISD candle closes, a stop order 1 tick beyond that candle's high (low
     for shorts) instead of buying the next 1m open; cancelled after K bars, or when the sweep extreme breaks first. Filled at
     the trigger (or the bar's open on a gap) + 1 tick of slippage. The fill bar gets no target / breakeven credit.
  2. missed-limit chase (chase={...}): the 30-min limit at the 5m CISD level was never tapped and price ran toward the target.
     Chase on the first 1m pullback that prints a 1m CISD in the trade's direction (a close above the open of the last run of
     down-closes into the pullback low), at the next 1m open, while that open is still less than `frac` of the way from the
     limit to the target. from "expiry" = only once the 30-min limit expired untapped (for `win` more minutes); "any" = also
     while the limit is still working. size = size multiplier for chase trades. The stop stays 1 tick beyond the sweep
     extreme (size follows the stop).
  3. ES SMT (smt={...}): ES (data/ES_5m.csv, closed 5m bars; ES 1m only starts 2026-09-16) did not take its own copy of the
     swept level (session box / PDH-PDL / PWH-PWL / PMH-PML) while NQ swept it.
       mode "size": x times the size when SMT is present (one rounding with the weekly stop, max 40 micros, then the room cap)
       mode "nosmt": x times the size when SMT is NOT present
       mode "filter": only SMT setups
     plus x1m kind "smt": SMT as the 1m trigger instead of the 5m CISD (an extra setup, first come first served with the live
     ones, 1 trade a day): NQ's 1m low takes a LIT level by >= depth ATR, the inducement swing was taken first, ES has not
     taken its copy, then the first 1m CISD -> next 1m open; stop 1 tick beyond the 1m sweep extreme.
  4. LIT opening model (x1m kind "open"): a 1m sweep between 09:30 and 10:00 of the NY trap box (08:00-09:30) or the overnight
     high/low (18:00-09:30), with the inducement taken first (optional) and a 1m CISD, entry at the next 1m open until sig_end,
     as an extra NY setup (only on days the live LIT has not traded yet: 1 trade a day, first come first served).
  Days without full 1m bars (all of 2021-25) run the 1m rules on 5m bars (as the live loop does).

  python tools/lit_t_entries.py check   # defaults == run lit_live (120 trades 2026) and == the baseline eval run numbers
  python tools/lit_t_entries.py grid    # every variant -> research/lit/t_entries_results.json
  python tools/lit_t_entries.py save    # store every variant as run lit_u_entries_* (family other, tags lit, lit_untested, lit_entries)
Pick on 2026 H1 (Jan 2 - Jun 30), check on 2026 H2 (Jul 1 - Oct 16); 2021-25 is a reference line (5m only, no 1m data).
1 CPU process. Paper research only.
"""
from __future__ import annotations

import bisect
import collections
import json
import os
import re
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import data as edata  # noqa: E402
from engine import lit  # noqa: E402
from tools import lit_final as F  # noqa: E402
from tools import lit_tightstop as TS  # noqa: E402
from tools import runlib as rl  # noqa: E402

OUT = os.path.join(ROOT, "research", "lit", "t_entries_results.json")
SESS, SPAN = F.SESS, F.SPAN
PV, COMM, SLIP, TICK = lit.PV, lit.COMM, lit.SLIP, lit.TICK
LIVE = TS.LIVE
RULE = ("lit", 800, 25.0)          # live eval sizing: $800 up to a 25-pt stop, then 800x25/stop
ROOM_K = 0.6                       # + never more than 60% of the room to the trailing max-loss floor

EDEF = {
    "ent": "next", "bs_k": 5,      # idea 1
    "chase": None,                 # idea 2: {"frac", "from", "win", "size"}
    "smt": None,                   # idea 3: {"mode": "size"|"nosmt"|"filter", "x"}
    "x1m": None,                   # ideas 3 (kind smt) and 4 (kind open): extra 1m-detector setups
}


def P_of(P=None):
    return {**LIVE, **EDEF, **(P or {})}


# ================================================================================================ size multipliers > 1 (cap 40)
_qty0 = TS.qty_of


def _qty(t, rule, room=None, room_k=None):
    """TS.qty_of, but a size multiplier above 1 (SMT 1.25x) never goes past 40 micros (MFFU 50K max; then the room cap)."""
    mi, mn = _qty0(t, rule, room, room_k)
    if mi > TS.MAXQ:
        mi = TS.MAXQ
        if room_k is not None and room is not None:
            mi = min(mi, max(1, int(room_k * room / (t["risk_pts"] * PV))))
    return mi, mn


TS.qty_of = _qty                   # this process only (TS._play / TS.sized look it up by name)


# ================================================================================================ ES (SMT)
class ESMarket(lit.Market):
    """lit.Market built on CME ES1! 5m (its own session boxes, PDH/PDL, PWH/PWL, PMH/PML)."""

    def __init__(self):
        orig = lit.load
        lit.load = lambda sym, tf: edata.load("ES", tf)
        try:
            super().__init__()
        finally:
            lit.load = orig


_ES = {}


def es():
    if "E" not in _ES:
        E = ESMarket()
        _ES["E"] = E
        _ES["day"] = {d: k for k, (d, s, e) in enumerate(E.days)}
        _ES["idx"] = {int(t): i for i, t in enumerate(E.t)}
    return _ES["E"], _ES["day"], _ES["idx"]


def _es_level(E, ek, nm, d):
    """(direction-space price, ES known index) of ES's copy of NQ level `nm`, or None (build-ups and gaps have no copy)."""
    ex = E.ctx[ek]
    if nm.split("_")[0] in ("trap", "on"):           # opening-model levels: ES's own trap box / overnight range
        L = [(p, ki) for p, ki, n2 in _levels_x(E, ek, d, "open", X={"lv": None}) if n2 == nm]
        return L[0] if L else None
    base = nm[:-2] if nm.endswith(("_h", "_l")) else None
    if base in lit.SESSIONS and base in ex:
        hi_, lo_, ki = ex[base]
        return (lo_ if d == 1 else -hi_), ki
    if nm in ("pdl", "pwl", "pml", "pdh", "pwh", "pmh") and nm[:2] + "h" in ex:
        return ex[nm[:2] + ("l" if d == 1 else "h")] * d, ex["s"] - 1
    return None


def smt_z(M, z):
    """True = ES did NOT take its copy of at least one swept level (from its known bar to NQ's trigger bar), and ES had not
    taken it before NQ's sweep; False = ES took every matched copy; None = no ES data / no matched level.
    (tools/lit_filters.py smt_lvl, on the live candidates.)"""
    E, eday, eidx = es()
    d = z["dir"]
    ek = eday.get(z["day"])
    ie, ii_, isb = eidx.get(int(M.t[z["ext_i"]])), eidx.get(int(M.t[z["i"]])), eidx.get(int(M.t[z["sweep_i"]]))
    if ek is None or ie is None or ii_ is None or isb is None:
        return None
    elo = E.l if d == 1 else -E.h
    es_ = E.ctx[ek]["s"]
    win_lo = float(elo[min(isb, ie):ii_ + 1].min())
    took = []
    for nm in z["swept"]:
        lv = _es_level(E, ek, nm, d)
        if lv is None:
            continue
        pv, ki = lv
        prior = elo[max(ki + 1, es_ - 600):min(isb, ie)]
        if len(prior) and prior.min() < pv:
            took.append(True); continue
        took.append(win_lo < pv)
    return (not all(took)) if took else None


# ================================================================================================ trade management (live rules)
def manage(M, B, d, s_day, fill, entry, stop, tg, no_credit, P):
    """Walk an open long (direction space) on B from bar `fill`: stop, VIX target, breakeven at 1R, flat 15:55 (the live
    rules of lit.simulate_x). no_credit = the fill bar gets no target / breakeven credit (limit / stop-order fills)."""
    hi_d, lo_d, c_d, o_d = B.dirs(d)
    risk = entry - stop
    be_d = None if P["be_r"] is None else P["be_r"] * risk
    flat = P["flat_mod"]
    cur, be_done, mfe, mae, worst = stop, False, 0.0, 0.0, 0.0
    k = fill
    exit_px = kind = None
    while k < B.n:
        if B.day[k] != s_day or B.mod[k] >= 1080:
            k -= 1; exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        mae = max(mae, (entry - lo_d[k]) / risk)
        worst = min(worst, lo_d[k] - entry)
        if lo_d[k] <= cur:
            exit_px, kind = cur - SLIP, ("BE" if be_done else "STOP"); break
        if not (k == fill and no_credit):
            mfe = max(mfe, (hi_d[k] - entry) / risk)
            if hi_d[k] >= tg:
                exit_px, kind = tg, "TARGET"; break
            if be_d is not None and not be_done and hi_d[k] >= entry + be_d:
                cur, be_done = entry, True
        if B.mod[k] >= flat:
            exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        k += 1
    if exit_px is None:
        return None
    xi5 = int(np.searchsorted(M.t, B.t[k], side="right") - 1)
    return {"entry_t": int(B.t[fill]), "exit_t": int(B.t[k]) + B.secs, "exit_i": xi5, "dir": d, "risk_pts": round(risk, 2),
            "exit": kind, "trigger": "LIT-" + ("1m" if B.secs == 60 else "5m"), "mfe": round(mfe, 3),
            "mae": round(min(mae, 1.0 + SLIP / risk), 3), "bars_held": int(k - fill + 1), "regime": "", "half": False,
            "legs": [(1.0, exit_px - entry)], "w1": worst, "w2": 0.0, "part": False, "entry_px": round(entry * d, 2),
            "stop_px": round(stop * d, 2), "target_px": round(tg * d, 2), "tf": B.secs // 60, "be_done": be_done}


def _target(entry, risk, tgt_lvl, fb, P):
    if fb:
        return entry + P["fallback_rr"] * risk
    dist = tgt_lvl - entry
    if dist < P["min_rr"] * risk:
        return None
    return entry + (min(dist, P["max_rr"] * risk) if P["max_rr"] else dist)


# ================================================================================================ executor of the live setups
def esim(M, B, z, entry_px, tgt_lvl, fb, stop0, P):
    """lit.simulate_x (research mode, 1m CISD entry) at 1 micro, with the entry options of EDEF (ideas 1 and 2)."""
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
    ch = P["chase"]
    ch_end = t0 + wait_s + (ch["win"] * 60 if ch else 0)
    no_credit = True
    fill = tapped = kconf = None
    how = "limit"
    hk = None                                    # chase: bar of the running high since the limit was placed
    k = k0
    while k < B.n:
        if B.day[k] != s_day or B.mod[k] >= flat or B.mod[k] >= 1080:
            break
        expired = tapped is None and B.t[k] >= t0 + wait_s
        if expired and not (ch and B.t[k] < ch_end):
            break
        if lo_d[k] <= stop0:
            break
        if tapped is None and not expired and lo_d[k] <= entry_px:
            tapped = k
        if tapped is None and hi_d[k] >= tgt_lvl:
            break
        if tapped is None and ch:
            # idea 2: the first 1m pullback with a 1m CISD in the trade's direction, while < frac of the way to the target
            if hk is None or hi_d[k] >= hi_d[hk]:
                hk = k                                   # running high since the limit was placed
            elif expired or ch["from"] == "any":
                lowk = hk + int(np.argmin(lo_d[hk:k + 1]))
                if k > lowk > hk:
                    cz = lit._cisd_level(c_d, o_d, lowk)
                    if (cz is not None and cz[1] >= hk and c_d[k] > cz[0] and c_d[lowk + 1:k].max(initial=-1e18) <= cz[0]
                            and k + 1 < B.n and B.day[k + 1] == s_day and B.mod[k + 1] < flat):
                        px = float(o_d[k + 1]) + SLIP
                        if px < entry_px + ch["frac"] * (tgt_lvl - entry_px):
                            fill, entry, no_credit, how = k + 1, px, False, "chase"
                            break
        if tapped is not None:
            if k - tapped > cis:
                break
            lowk = tapped + int(np.argmin(lo_d[tapped:k + 1]))
            cz = lit._cisd_level(c_d, o_d, lowk)
            if cz is not None and k > lowk and c_d[k] > cz[0] and k + 1 < B.n and B.day[k + 1] == s_day:
                kconf = k
                break
        k += 1
    if kconf is not None:
        if P["ent"] == "next":
            fill, entry, no_credit, how = kconf + 1, float(o_d[kconf + 1]) + SLIP, False, "next"
        elif P["ent"] == "bstop":
            # idea 1: a buy-stop 1 tick above the 1m CISD candle's high, working for bs_k bars
            trig = float(hi_d[kconf]) + TICK
            for b in range(kconf + 1, min(B.n, kconf + 1 + P["bs_k"])):
                if B.day[b] != s_day or B.mod[b] >= flat or B.mod[b] >= 1080:
                    break
                if o_d[b] >= trig:
                    fill, entry, no_credit, how = b, float(o_d[b]) + SLIP, True, "bstop"; break
                if hi_d[b] >= trig:
                    fill, entry, no_credit, how = b, trig + SLIP, True, "bstop"; break
                if lo_d[b] <= stop0:
                    break
        else:
            raise ValueError(P["ent"])
    if fill is None:
        return None
    risk = entry - stop0
    if risk <= 0 or lit.qty_for(risk) < 1:
        return None
    tg = _target(entry, risk, tgt_lvl, fb, P)
    if tg is None:
        return None
    t = manage(M, B, d, s_day, fill, entry, stop0, tg, no_credit, P)
    if t is None:
        return None
    t.update(day=z["day"], how=how, swept=z["swept"], i=z["i"], ext_i=z["ext_i"], src="lit",
             x_m=(ch["size"] if (how == "chase" and ch) else 1.0))
    return t


# ================================================================================================ the 1m detector (ideas 3, 4)
_DR = {}


def day_ranges(B):
    if id(B) not in _DR:
        dd = np.asarray(B.day)
        st = np.r_[0, np.flatnonzero(np.diff(dd)) + 1]
        en = np.r_[st[1:], len(dd)]
        _DR[id(B)] = {int(dd[a]): (int(a), int(b)) for a, b in zip(st, en) if dd[a] >= 0}
    return _DR[id(B)]


def _levels_x(M, k, d, kind, X=None):
    """[(direction-space price, known 5m index, name)] of the low-side liquidity (for longs) used by the detector.
    kind "open": X["lv"] = None (trap box + overnight) | "trap" | "on"."""
    x = M.ctx[k]; s, e = x["s"], x["e"]
    mod = M.mod
    if kind == "open":
        lv = (X or {}).get("lv")
        ii = np.arange(s, e)
        k930 = ii[(mod[ii] >= 570) & (mod[ii] < 1080)]
        if not len(k930):
            return []
        ki = int(k930[0]) - 1
        out = []
        trap = ii[(mod[ii] >= 480) & (mod[ii] < 570)]
        on = ii[(ii <= ki)]
        for nm, jj in (("trap", trap), ("on", on)):
            if len(jj) < 2 or (lv and nm != lv):
                continue
            p = float(M.l[jj].min()) if d == 1 else -float(M.h[jj].max())
            out.append((p, ki, nm + ("_l" if d == 1 else "_h")))
        return out
    side = "low" if d == 1 else "high"
    out = []
    for sd, px, ki, nm, cls in M.levels(k):
        if sd != side or cls in ("buildup", "gap"):
            continue
        out.append((float(px) * d, int(ki), nm))
    return out


def _idm_ok(M, d, s, sb, p, X):
    """LIT inducement (live idm_a [1.0, 36, 1]) seen at the 5m breach bar sb (only closed 5m bars before it): a confirmed 5m
    swing low above the swept level, <= 1 ATR above it, <= 36 bars before the breach, untouched until the final push."""
    if not X.get("idm", True):
        return True
    hi_d5 = M.h if d == 1 else -M.l
    lo_d5 = M.l if d == 1 else -M.h
    sw = M.fl if d == 1 else M.fh
    at = float(M.atr[sb - 1])
    a = max(s - 600, sb - 36)
    if sb - 1 <= a:
        return False
    leg_top = a + int(np.argmax(hi_d5[a:sb]))
    lo_i = bisect.bisect_left(sw, sb - 36)
    for m in sw[lo_i:bisect.bisect_left(sw, sb - 2)]:
        m = int(m)
        lm = float(lo_d5[m])
        if lm <= p or (lm - p) / max(at, 1e-9) > 1.0:
            continue
        seg = lo_d5[m + 1:sb] < lm
        tk = m + 1 + int(np.argmax(seg)) if seg.any() else sb
        if tk >= max(leg_top, m + 3):
            return True
    return False


def detect(M, B1, B5, X, P, days):
    """Extra setups (signals) of the 1m detector. Returns [{day, t, dir, B, fill, entry, stop, tg, ...}] (unit size)."""
    kind = X["kind"]
    E = eday = eidx = None
    if kind == "smt" or X.get("smt_req"):
        E, eday, eidx = es()
    out = []
    dmap = {d_: k for k, (d_, s, e) in enumerate(M.days)}
    r1, r5 = day_ranges(B1) if B1 is not None else {}, day_ranges(B5)
    w_a, w_b = X.get("sweep_win", (120, 930))
    sig_end = X.get("sig_end", 930)
    for day in days:
        k = dmap.get(day)
        if k is None:
            continue
        x = M.ctx[k]
        if "pdh" not in x or not x.get("vix_move"):
            continue
        s, e = x["s"], x["e"]
        use1 = B1 is not None and k in B1.full
        B = B1 if use1 else B5
        a_, b_ = (r1 if use1 else r5).get(k, (0, 0))
        if b_ - a_ < 10:
            continue
        for d in (1, -1):
            hi_d, lo_d, c_d, o_d = B.dirs(d)
            lo_d5 = M.l if d == 1 else -M.h
            L = _levels_x(M, k, d, kind, X)
            br = []                                  # (exec bar of the first breach, price, name)
            for p, ki, nm in L:
                fb = lit._first_breach(lo_d5, max(ki, s - 600), e, p)
                if fb >= e or fb < s:
                    continue
                if not (w_a <= M.mod[fb] < w_b):
                    continue
                t5 = int(M.t[fb])
                j0 = a_ + int(np.searchsorted(B.t[a_:b_], t5))
                j = j0
                while j < b_ and B.t[j] < t5 + 300 and not (lo_d[j] < p):
                    j += 1
                if j >= b_ or B.t[j] >= t5 + 300:
                    continue
                br.append((j, p, nm, fb, ki))
            if not br:
                continue
            br.sort()
            by_j = collections.defaultdict(list)
            for b in br:
                by_j[b[0]].append(b)
            ev = None
            for j in range(br[0][0], b_):
                if B.mod[j] >= P["flat_mod"] or B.mod[j] >= 1080:
                    break
                if ev is not None and B.t[j] - ev["tb"] > X.get("ev_max", 60) * 60:
                    ev = None                            # no setup within ev_max minutes of the sweep
                for jb, p, nm, fb, ki in by_j.get(j, ()):
                    if ev is None:
                        ev = {"lev": p, "names": [(nm, ki)], "jb": j, "tb": int(B.t[j]), "sb": fb, "ext": float(lo_d[j]),
                              "ext_j": j, "idm": _idm_ok(M, d, s, fb, p, X)}
                    else:
                        ev["names"].append((nm, ki)); ev["lev"] = max(ev["lev"], p)
                        ev["idm"] = ev["idm"] or _idm_ok(M, d, s, fb, p, X)
                if ev is None:
                    continue
                if lo_d[j] < ev["ext"]:
                    ev["ext"], ev["ext_j"] = float(lo_d[j]), j
                ej = ev["ext_j"]
                if j <= ej:
                    continue
                cz = lit._cisd_level(c_d, o_d, ej)
                if cz is None or not (c_d[j] > cz[0]) or c_d[ej + 1:j].max(initial=-1e18) > cz[0]:
                    continue
                # a first 1m close above the CISD level of the run into the extreme: is it a setup?
                ok = ev["idm"]
                at5 = float(M.atr[max(ev["sb"] - 1, 0)])
                if (ev["lev"] - ev["ext"]) / max(at5, 1e-9) < X.get("depth", 0.5):
                    ok = False
                mod_n = int(B.mod[j + 1]) if j + 1 < b_ else 10 ** 6
                if not (P["window"][0][0] <= mod_n < min(P["window"][0][1], sig_end)):
                    ok = False
                smt = None
                if ok and E is not None:
                    smt = _smt_now(M, E, eday, eidx, day, d, ev, int(B.t[j]) + B.secs, int(B.t[ev["jb"]]))
                    if (kind == "smt" or X.get("smt_req")) and smt is not True:
                        ok = False
                if ok and X.get("disp"):
                    body = (c_d[ej:j + 1] - o_d[ej:j + 1]) / max(at5, 1e-9)
                    ok = float(body.max()) >= X["disp"]
                if not ok:
                    continue
                if j + 1 >= b_:
                    break
                entry = float(o_d[j + 1]) + SLIP
                stop = ev["ext"] - P["stop_buf"]
                risk = entry - stop
                ev = None
                if not (P["min_stop"] <= risk <= P["max_stop"]) or lit.qty_for(risk) < 1:
                    continue
                vt = x["open18"] * d + P["vix_k"] * x["vix_move"]
                tg = _target(entry, risk, vt, False, P)
                if tg is None:
                    continue
                out.append({"day": day, "t": int(B.t[j + 1]), "dir": d, "B": B, "fill": j + 1, "entry": entry, "stop": stop,
                            "tg": tg, "s_day": k, "smt": smt})
    out.sort(key=lambda s_: (s_["t"], -s_["dir"]))
    return out


def _smt_now(M, E, eday, eidx, day, d, ev, t_now, t_breach):
    """ES SMT seen at t_now (closed ES 5m bars only): ES had not taken its copy of at least one of the swept levels."""
    ek = eday.get(day)
    if ek is None:
        return None
    elo = E.l if d == 1 else -E.h
    es_ = E.ctx[ek]["s"]
    i_now = int(np.searchsorted(E.t, t_now - 300, side="right")) - 1
    i_b = int(np.searchsorted(E.t, t_breach - 300, side="right")) - 1
    took = []
    for nm, _ki in ev["names"]:
        lv = _es_level(E, ek, nm, d)
        if lv is None:
            continue
        pv, ki = lv
        if i_now <= ki:
            continue
        prior = elo[max(ki + 1, es_ - 600):max(ki + 1, i_b + 1)]
        if len(prior) and prior.min() < pv:
            took.append(True); continue
        took.append(float(elo[max(ki + 1, es_ - 600):i_now + 1].min()) < pv)
    return (not all(took)) if took else None


# ================================================================================================ the run (live loop order)
def erun(P=None, sessions=SESS):
    """Unit-size trades of one variant (lit._run_core research mode + EDEF), live setups and detector setups first come
    first served, one trade a day, never two at once."""
    P = P_of(P)
    names = set(P["sweep_names"]) if P.get("sweep_names") else None
    sset = set(sessions) if sessions else None
    M, C = F.market(P["ref"], P["extra_boxes"])
    B5 = F.bars(M, "5m")
    B1 = F.bars(M, "1m") if P["tf"] == "1m" else None
    X = P["x1m"]
    ev = [(int(M.t[z["entry_i"]]), 0, n, z) for n, z in enumerate(C) if sset is None or z["day"] in sset]
    if X:
        S = detect(M, B1, B5, X, P, sorted(sset) if sset else [d for d, _, _ in M.days])
        # a 1m signal is known at its fill bar's open; the live 5m setup at its entry bar's open (= when the limit is placed)
        ev += [(s_["t"], 1, n, s_) for n, s_ in enumerate(S)]
    ev.sort(key=lambda r: (r[0], r[1], r[2]))
    sm = P["smt"]
    out, busy, per_day = [], -1, collections.Counter()
    for _t, src, _n, z in ev:
        if src == 1:
            ei5 = int(np.searchsorted(M.t, z["t"], side="right") - 1)
            if ei5 <= busy or per_day[z["day"]] >= P["max_per_day"]:
                continue
            if P.get("monday") and lit.monday_block(M, {"k": z["s_day"], "i": ei5 - 1, "dir": z["dir"]}):
                continue
            t = manage(M, z["B"], z["dir"], z["s_day"], z["fill"], z["entry"], z["stop"], z["tg"], False, P)
            if t is None:
                continue
            t.update(day=z["day"], how="x1m_" + X["kind"], src="x1m", smt=z["smt"], x_m=float(X.get("size", 1.0)))
            busy = t["exit_i"]; per_day[z["day"]] += 1
            out.append(t)
            continue
        if z["entry_i"] <= busy or per_day[z["day"]] >= P["max_per_day"]:
            continue
        if not lit.setup_ok(z, P, names):
            continue
        if P.get("monday") and lit.monday_block(M, z):
            continue
        smt = smt_z(M, z) if sm else None
        if sm and sm["mode"] == "filter" and smt is not True:
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
        use1 = P["tf"] == "1m" and B1 is not None and int(M.day_of[z["entry_i"]]) in B1.full
        B = B1 if use1 else B5
        t = esim(M, B, z, ep, ep + tp, fb, stop0, P)
        if t is None:
            continue
        t["smt"] = smt
        if sm and sm["mode"] == "size" and smt is True:
            t["x_m"] *= sm["x"]
        if sm and sm["mode"] == "nosmt" and smt is not True:
            t["x_m"] *= sm["x"]
        busy = t["exit_i"]; per_day[z["day"]] += 1
        out.append(t)
    return out


_U = {}


def unit(P=None):
    key = json.dumps(P or {}, sort_keys=True, default=str)
    if key not in _U:
        U = erun(P)
        TS.wk_marks(U)
        for t in U:
            if t.get("x_m", 1.0) != 1.0:
                t["wk_m"] = t["wk_m"] * t["x_m"]
        _U[key] = U
    return _U[key]


# ================================================================================================ scoring (= the baseline run's)
SP = ("H1", "H2", "2026", "2021-25")


def score(U, spans=SP):
    out = {}
    for s in spans:
        e, path = TS.evals(U, RULE, s, ROOM_K)
        st = TS.stats(path, s)
        a, z = SPAN[s]
        TT = [t for t in path if a <= t["day"] <= z]
        w = [t["pnl"] for t in TT if t["pnl"] > 0]; ls = [t["pnl"] for t in TT if t["pnl"] <= 0]
        st["avg_win"] = round(float(np.mean(w))) if w else 0
        st["avg_loss"] = round(float(np.mean(ls))) if ls else 0
        st["how"] = dict(collections.Counter(t.get("how", "next") for t in TT))
        out[s] = {**st, **e}
    return out


def row(nm, o, spans=("H1", "H2", "2021-25")):
    def f(s):
        if not s or not s.get("n"):
            return "n=0"
        return (f"n={s['n']} {s['tpw']}/wk win {s['win']} PF {s['pf']} net {s['net']:+,} ${s['per_month']:,}/mo DD {s['dd']:,} "
                f"w {s['avg_win']} l {s['avg_loss']} 2w {s['p10']}/{s['f10']} 1m {s['p20']}/{s['f20']} pr {s['pass_rate']} med {s['pass_med']}")
    return f"{nm:30s} " + " | ".join(f"{k}[{f(o.get(k))}]" for k in spans if k in o)


# ================================================================================================ check
def check():
    U = unit()
    T = TS.sized(U, ("lit", 800, 20.0))
    L = F.run(LIVE)
    ka = [(t["day"], t["entry_t"], round(t["pnl"], 2), t["exit"], t["qty"]) for t in sorted(L, key=lambda t: t["entry_t"])]
    kb = [(t["day"], t["entry_t"], round(t["pnl"], 2), t["exit"], t["qty"]) for t in T]
    bad = [(x, y) for x, y in zip(ka, kb) if not (x[:2] == y[:2] and abs(x[2] - y[2]) < 0.03 and x[3:] == y[3:])]
    n26 = [t for t in T if t["day"] >= "2026"]
    print(f"engine lit_live {len(ka)} trades | wrapper {len(kb)} | mismatches {len(bad) + abs(len(ka) - len(kb))} | "
          f"2026 {len(n26)} trades net {sum(t['pnl'] for t in n26):+,.0f}")
    o = score(U, spans=("H1", "H2"))
    print(row("baseline (eval sizing)", o, spans=("H1", "H2")))
    ok = (not bad and len(ka) == len(kb) and len(n26) == 120 and o["H1"]["net"] == 33305 and o["H2"]["net"] == 10465)
    print("CHECK", "OK" if ok else "FAILED")
    return ok


# ================================================================================================ the grid
def variants():
    V = collections.OrderedDict()
    V["base"] = {}
    # 1. buy-stop entry beyond the 1m CISD candle
    for kk in (3, 5, 10):
        V[f"bstop {kk}"] = {"ent": "bstop", "bs_k": kk}
    # 2. missed-limit chase
    for fr in (0.25, 0.4, 0.6):
        V[f"chase exp {fr} 60m"] = {"chase": {"frac": fr, "from": "expiry", "win": 60, "size": 1.0}}
        V[f"chase any {fr} 60m"] = {"chase": {"frac": fr, "from": "any", "win": 60, "size": 1.0}}
    V["chase exp 0.4 120m"] = {"chase": {"frac": 0.4, "from": "expiry", "win": 120, "size": 1.0}}
    V["chase exp 0.4 60m half"] = {"chase": {"frac": 0.4, "from": "expiry", "win": 60, "size": 0.5}}
    # 3. ES SMT
    for xx in (1.25, 1.5):
        V[f"smt size {xx}"] = {"smt": {"mode": "size", "x": xx}}
    V["smt nosmt 0.75"] = {"smt": {"mode": "nosmt", "x": 0.75}}
    V["smt filter"] = {"smt": {"mode": "filter"}}
    for em in (30, 60):
        V[f"smt trig {em}m"] = {"x1m": {"kind": "smt", "ev_max": em, "depth": 0.5, "idm": True, "size": 1.0}}
    V["smt trig 60m 1.25"] = {"x1m": {"kind": "smt", "ev_max": 60, "depth": 0.5, "idm": True, "size": 1.25}}
    V["smt trig 60m disp0.8"] = {"x1m": {"kind": "smt", "ev_max": 60, "depth": 0.5, "idm": True, "size": 1.0, "disp": 0.8}}
    # 4. LIT opening model (09:30-10:00 sweep of the NY trap box / overnight high-low)
    for dp in (0.25, 0.5):
        for se in (600, 630):
            V[f"open d{dp} to{se // 60}{se % 60:02d}"] = {"x1m": {"kind": "open", "sweep_win": (570, 600), "sig_end": se,
                                                                  "depth": dp, "idm": True, "ev_max": 60}}
    V["open d0.25 to1030 noidm"] = {"x1m": {"kind": "open", "sweep_win": (570, 600), "sig_end": 630, "depth": 0.25,
                                            "idm": False, "ev_max": 60}}
    V["open d0.5 to1030 smt"] = {"x1m": {"kind": "open", "sweep_win": (570, 600), "sig_end": 630, "depth": 0.5,
                                         "idm": True, "ev_max": 60, "smt_req": True}}
    # robustness of the best opening model (neighbours of d0.25 to 10:00)
    OB = {"kind": "open", "sweep_win": (570, 600), "sig_end": 600, "depth": 0.25, "idm": True, "ev_max": 60}
    V["open d0.25 to1015"] = {"x1m": {**OB, "sig_end": 615}}
    V["open d0.25 to1000 ev30"] = {"x1m": {**OB, "ev_max": 30}}
    V["open d0.25 to1000 trap only"] = {"x1m": {**OB, "lv": "trap"}}
    V["open d0.25 to1000 overnight only"] = {"x1m": {**OB, "lv": "on"}}
    V["open d0.25 to1000 half"] = {"x1m": {**OB, "size": 0.5}}
    V["open d0.25 to1000 smt"] = {"x1m": {**OB, "smt_req": True}}
    V["open d0 to1000"] = {"x1m": {**OB, "depth": 0.0}}
    return V


def _load():
    return json.load(open(OUT)) if os.path.exists(OUT) else {}


def grid(only=None):
    res = _load()
    for nm, P in variants().items():
        if only and not any(o in nm for o in only):
            continue
        U = unit(P)
        o = score(U)
        res[nm] = {"params": P, "score": o,
                   "how26": dict(collections.Counter(t.get("how", "next") for t in U if t["day"] >= "2026")),
                   "smt26": dict(collections.Counter(str(t.get("smt")) for t in U if t["day"] >= "2026"))}
        print(row(nm, o), flush=True)
        json.dump(res, open(OUT, "w"), indent=1, default=str)
    return res


# ================================================================================================ store runs
def _slug(nm):
    return "lit_u_entries_" + re.sub(r"[^a-z0-9]+", "_", nm.lower().replace(".", "p")).strip("_")


IDEA = [("bstop", "1. buy-stop entry beyond the 1m CISD candle"), ("chase", "2. missed-limit chase"),
        ("smt", "3. ES SMT"), ("open", "4. LIT opening model")]


def save_all():
    """Store every grid variant (ADOPT only when H1 and H2 both beat the baseline and 2-4 trades/week)."""
    res = _load()
    V = variants()
    b = res["base"]["score"]
    for nm, rec in res.items():
        o = rec["score"]
        if nm == "base":
            rid, title, st, why = (_slug("base"), "LIT live + eval sizing (reference of the untested-entries study, == lit_tight_eval_800_25_room60)",
                                   "info", "Reference: the live LIT entry with the live eval sizing.")
        else:
            d1, d2 = o["H1"]["net"] - b["H1"]["net"], o["H2"]["net"] - b["H2"]["net"]
            tpw = min(o["H1"]["tpw"], o["H2"]["tpw"]); tpx = max(o["H1"]["tpw"], o["H2"]["tpw"])
            if d1 > 0 and d2 > 0 and tpw >= 2 and tpx <= 4:
                st, v = "adopt-candidate", "ADOPT"
            elif abs(d1) < 500 and abs(d2) < 500:
                st, v = "info", "NEUTRAL"
            else:
                st, v = "rejected", "REJECT"
            idea = next(t for k, t in IDEA if nm.startswith(k))
            rid, title, why = _slug(nm), f"LIT untested entries - {idea}: {nm}", f"{v}: H1 {d1:+,} $ / H2 {d2:+,} $ vs the baseline (LIT live + eval sizing)."
        U = unit(V[nm])
        T = TS.evals(U, RULE, "2026", ROOM_K)[1] + TS.evals(U, RULE, "2021-25", ROOM_K)[1]
        T = [{k: v for k, v in t.items() if k not in ("legs", "B")} for t in T]
        S = rl.score(T, SESS)
        h = lambda s: (f"n={s['n']} {s['tpw']}/wk win {s['win']}% PF {s['pf']} net {s['net']:+,} (${s['per_month']:,}/mo) DD {s['dd']:,} "
                       f"avg win ${s['avg_win']:,} avg loss ${s['avg_loss']:,}; eval 2wk {s['p10']}/{s['f10']} 1mo {s['p20']}/{s['f20']} "
                       f"pass rate {s['pass_rate']}% median {s['pass_med']}") if s.get("n") else "no trades"
        rl.save(rid, title, "other", "Owner 2026-10-18: try every untested LIT entry idea (entries group) on the live LIT signals.",
                params={**LIVE, **EDEF, **V[nm], "size": list(RULE), "room_k": ROOM_K}, trades=T, scored=S, status=st,
                verdict=f"{why} 2026 H1 (pick) {h(o['H1'])}; 2026 H2 (check) {h(o['H2'])}; 2021-25 reference only {h(o['2021-25'])}",
                notes="tools/lit_t_entries.py (wraps engine/lit.py; defaults == run lit_live trade for trade and == run "
                      "lit_tight_eval_800_25_room60). Same LIT stop, target and management; only the entry changes. "
                      "Eval sizing: $800 up to a 25-pt stop, then 800x25/stop, weekly stop, 60% room cap.",
                writeup="lit-untested-entries", tags=["lit", "lit_untested", "lit_entries"])
        print("saved", rid, flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        sys.exit(0 if check() else 1)
    elif cmd == "grid":
        grid(sys.argv[2:] or None)
    elif cmd == "save":
        save_all()
