"""ChatGPT's 20 LIT filter ideas (L01-L20) and the V3 / V4 target variants (owner's ChatGPT dossier, 2026-10-24).

Spec: research/writeups/specs/chatgpt-2026-10-24-ideas.md (the owner's paste; thresholds are ChatGPT's, fixed before any
result: P = primary, A1 / A2 = the two alternatives; no cross-grid). Every L rule is a skip / cancel filter on the live LIT's
own setups (live_model.json "lit" = run lit_live) through engine/lit.py run_x: the setup is removed before the executor
(engine option skip_keys), the day stays free for a later setup, stop and target unchanged. engine/lit.py is not edited.

Shared definitions (direction space: shorts are mirrored, a long's "low" is a short's high):
  L   = the nearest swept level (the highest swept level for a long; the level whose breach is the sweep)
  s5  = the first 5m bar from the sweep bar to the extreme that trades below L
  s   = the first completed 1m bar inside s5 that trades below L (needs clean 1m bars that day = 2026; else UNKNOWN)
  I   = the selected inducement = the most recent inducement the live rule counts (<= 1 ATR above L, <= 36 bars old)
  b   = LIT's own displacement bar (5m): the bar with the biggest body / ATR between the extreme and the CISD trigger
  A   = Wilder ATR(14) of the completed 5m bars, frozen at the bar before s5
  q   = 1 tick = 0.25 pt. A feature that cannot be measured (no 1m bars, zero range, no pivot) = UNKNOWN = no trade change.
L16-L20 act while the entry waits. LIT's CISD limit is VIRTUAL (research/lit/order_trace.md): nothing works at the broker until
the 1m CISD decides the market entry, so "cancel the pending entry" = skip the setup when the rule fires on a 1m bar that
closed before the 1m CISD decision bar. These read the setup's own wait window (5m CISD close -> decision bar), found by
iterating: run, flag the trades whose window fires the rule, skip them, rerun, until no new trade is flagged (exact: a
setup's window depends on that setup only).

V3 / V4: the target band (18:00 open +/- vix_k x one-day move) from VXN or VIX9D instead of VIX, prior-day close only (the
last CBOE close before the trading day), multipliers vix_k 1.0 / 0.9 / 1.1. CBOE's own History files
(cdn.cboe.com/api/global/us_indices/daily_prices/, downloaded 2026-10-24 to research/lit/gpt_cboe/, equal to data/VXN_1d.csv
and data/CBOE_vol_1d.csv on every overlapping day). Controls (not candidates): VIX x 0.9 / 1.1.

Judged the LIT way: pick on 2026 H1, check on 2026 H2, 2021-25 a reference line (5m only there: the 1m features are UNKNOWN).
Candidate = H1 $ better AND H2 $ not worse AND tail retention >= 90% (kept / all 2026 baseline trades with MFE >= 4R) AND
2026 trades/week >= 2. Every candidate gets a placebo (200 random skips of the same count per span).

  python -X utf8 tools/lit_gpt_filters.py run        # every variant -> research/lit/gpt_filters.json (~3 min)
  python -X utf8 tools/lit_gpt_filters.py placebo    # placebo for the candidates (and the best H1 non-candidates)
  python -X utf8 tools/lit_gpt_filters.py lookahead  # noise-overwrite check of every feature
  python -X utf8 tools/lit_gpt_filters.py save       # rl.save runs lit_gpt_*
Paper only. Edits no engine file and no live_model*.json.
"""
from __future__ import annotations

import collections
import copy
import json
import math
import os
import random
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from tools import lit_supplement as SUP  # noqa: E402  (base market, eval path, lit_view)
from tools import lit_ablation as AB  # noqa: E402

OUT = os.path.join(ROOT, "research", "lit", "gpt_filters.json")
CBOE = os.path.join(ROOT, "research", "lit", "gpt_cboe")
P_LIVE = SUP.P_LIVE
F = SUP.F
TICK = lit.TICK
Q = ("Owner 2026-10-24: ChatGPT's research dossier proposes 20 LIT filters (L01-L20, each with a primary and two "
     "alternative thresholds) and a VXN / VIX9D target band (V3 / V4). Do any of them make the live LIT more money without "
     "cutting its big winners? Picked on 2026 H1, checked on 2026 H2.")
TAILS = (3.0, 4.0, 5.0)


def key(z):
    return (z["day"], int(z["i"]), int(z["dir"]))


# ================================================================================================ geometry helpers
def d5(M, d):
    return (M.h, M.l, M.c, M.o) if d == 1 else (-M.l, -M.h, -M.c, -M.o)


def d1(B, d):
    return (B.h, B.l, B.c, B.o) if d == 1 else (-B.l, -B.h, -B.c, -B.o)


def lev_L(z):
    return max(z["sw"].values())


def s5_of(M, z):
    _, lo, _, _ = d5(M, z["dir"])
    L = lev_L(z)
    for j in range(z["sweep_i"], z["ext_i"] + 1):
        if lo[j] < L:
            return j
    return z["sweep_i"]


def feat_atr(M, z):
    j = s5_of(M, z) - 1
    a = float(M.atr[j]) if j >= 0 else 0.0
    return a if a > 0 else None


def s1_of(M, B, z):
    """B index of s (first 1m bar inside s5 below L) or None (no clean 1m bars that day / no 1m breach)."""
    if B is None or z["k"] not in B.full:
        return None
    s5 = s5_of(M, z)
    t5 = int(M.t[s5])
    j0, j1 = int(np.searchsorted(B.t, t5)), int(np.searchsorted(B.t, t5 + 300))
    _, lo, _, _ = d1(B, z["dir"])
    L = lev_L(z)
    for j in range(j0, j1):
        if lo[j] < L:
            return j
    return None


def disp_bar(M, z, first_qual=None):
    """LIT's displacement bar b (biggest body / ATR between the extreme and the trigger); first_qual = the first bar whose
    body / ATR >= first_qual instead."""
    hi, lo, c, o = d5(M, z["dir"])
    ee, i = z["ext_i"], z["i"]
    body = (c[ee + 1:i + 1] - o[ee + 1:i + 1]) / np.maximum(M.atr[ee + 1:i + 1], 1e-9)
    if not len(body):
        return None
    if first_qual is not None:
        ok = np.flatnonzero(body >= first_qual)
        return ee + 1 + int(ok[0]) if len(ok) else None
    return ee + 1 + int(np.argmax(body))


def sel_idm(z):
    dm, age, _ = P_LIVE["idm_a"]
    q = [(aa, dd) for dd, aa in z["idm_a"] if dd <= dm and aa <= age]
    if not q:
        return None
    aa, dd = min(q)
    return z["sweep_i"] - aa


def level_ki(M, z, L):
    d = z["dir"]
    ks = [ki for side, px, ki, nm, cls in M.levels(z["k"]) if (side == "low") == (d == 1) and abs(px * d - L) < 1e-6]
    return min(ks) if ks else None


# ================================================================================================ features (raw metrics)
def m_eff(M, B, z, _):
    b = disp_bar(M, z)
    if b is None:
        return None
    hi, lo, c, o = d5(M, z["dir"])
    r = hi[b] - lo[b]
    return None if r <= 0 else abs(c[b] - o[b]) / r


def m_cloc(M, B, z, _):
    b = disp_bar(M, z)
    if b is None:
        return None
    hi, lo, c, o = d5(M, z["dir"])
    r = hi[b] - lo[b]
    return None if r <= 0 else (c[b] - lo[b]) / r


def m_reclaim(M, B, z, _):
    """1m bars from s to the first 1m close back above L (same bar = 0); inf when no close above L before the CISD close."""
    js = s1_of(M, B, z)
    if js is None:
        return None
    _, _, c, _ = d1(B, z["dir"])
    L = lev_L(z)
    je = int(np.searchsorted(B.t, int(M.t[z["i"]]) + 300))
    for j in range(js, je):
        if c[j] > L:
            return j - js
    return math.inf


def m_disp_prompt(M, B, z, _):
    """1m bars from s's close to the close of the first qualifying displacement bar (5m body >= the live 0.8 ATR)."""
    js = s1_of(M, B, z)
    if js is None:
        return None
    b = disp_bar(M, z, first_qual=P_LIVE["disp"])
    if b is None:
        return None
    return (int(M.t[b]) + 300 - (int(B.t[js]) + 60)) / 60.0


def m_cisd_prompt(M, B, z, _):
    js = s1_of(M, B, z)
    if js is None:
        return None
    return (int(M.t[z["i"]]) + 300 - (int(B.t[js]) + 60)) / 60.0


def m_idm_prom(M, B, z, _):
    m = sel_idm(z)
    A = feat_atr(M, z)
    if m is None or A is None or m < 2:
        return None
    hi, lo, _, _ = d5(M, z["dir"])
    return (min(hi[m - 2:m].max(), hi[m + 1:m + 3].max()) - lo[m]) / A


def m_sep(M, B, z, _):
    m = sel_idm(z)
    A = feat_atr(M, z)
    if m is None or A is None:
        return None
    _, lo, _, _ = d5(M, z["dir"])
    return (lo[m] - lev_L(z)) / A


def m_idm_recency(M, B, z, _):
    """Minutes from the moment I is known (its 2-bar fractal confirms: close of bar m + 2) to the close of s."""
    m = sel_idm(z)
    js = s1_of(M, B, z)
    if m is None or js is None:
        return None
    return (int(B.t[js]) + 60 - (int(M.t[m + 2]) + 300)) / 60.0


def m_touches(M, B, z, N):
    """Prior contact episodes with L since it became a level (5m bars with a low within 0.1 A above L; runs closer than N
    non-contact bars merge; the episode that runs into the sweep is the approach itself and is not counted)."""
    A = feat_atr(M, z)
    L = lev_L(z)
    ki = level_ki(M, z, L)
    if A is None or ki is None:
        return None
    _, lo, _, _ = d5(M, z["dir"])
    s5 = s5_of(M, z)
    a = max(ki + 1, M.ctx[z["k"]]["s"] - 600)
    if a >= s5:
        return 0
    cont = np.flatnonzero(lo[a:s5] <= L + 0.1 * A) + a
    if not len(cont):
        return 0
    eps, last = [], None
    for j in cont:
        if last is None or j - last - 1 >= N:
            eps.append([j, j])
        else:
            eps[-1][1] = j
        last = j
    if eps and s5 - eps[-1][1] - 1 < N:
        eps = eps[:-1]
    return len(eps)


def m_raid(M, B, z, _):
    """Extra distinct known same-side levels (untaken before s) that the 1m sweep bar s also trades through."""
    js = s1_of(M, B, z)
    if js is None:
        return None
    d = z["dir"]
    hi1, lo1, _, _ = d1(B, d)
    _, lo5, _, _ = d5(M, d)
    L = lev_L(z)
    s5 = s5_of(M, z)
    j0 = int(np.searchsorted(B.t, int(M.t[s5])))
    s0 = M.ctx[z["k"]]["s"]
    px_ = []
    for side, px, ki, nm, cls in M.levels(z["k"]):
        if (side == "low") != (d == 1) or ki >= s5:
            continue
        p = px * d
        if abs(p - L) <= TICK + 1e-9 or not (lo1[js] < p <= hi1[js]):
            continue
        a = max(ki + 1, s0 - 600)
        if a < s5 and lo5[a:s5].min() < p:
            continue
        if js > j0 and lo1[j0:js].min() < p:
            continue
        if all(abs(p - x) > TICK + 1e-9 for x in px_):
            px_.append(p)
    return len(px_)


def _pre1(M, B, z, N):
    js = s1_of(M, B, z)
    if js is None or js - N < 0:
        return None
    a = js - N
    if int(B.t[js - 1]) - int(B.t[a]) != 60 * (N - 1) or B.day[a] != B.day[js]:
        return None
    return a, js


def m_appr_eff(M, B, z, N):
    w = _pre1(M, B, z, N)
    if w is None:
        return None
    _, _, c, _ = d1(B, z["dir"])
    cc = c[w[0]:w[1]]
    den = np.abs(np.diff(cc)).sum()
    return None if den <= 0 else abs(cc[-1] - cc[0]) / den


def m_appr_overlap(M, B, z, N):
    w = _pre1(M, B, z, N)
    if w is None:
        return None
    hi, lo, _, _ = d1(B, z["dir"])
    h, l = hi[w[0]:w[1]], lo[w[0]:w[1]]
    ov = []
    for j in range(1, len(h)):
        r = min(h[j] - l[j], h[j - 1] - l[j - 1])
        if r <= 0:
            return None
        ov.append(max(0.0, min(h[j], h[j - 1]) - max(l[j], l[j - 1])) / r)
    return float(np.mean(ov)) if ov else None


def m_disp_beyond(M, B, z, N):
    """Ticks by which b's close clears the highest high of the N 1m bars before s."""
    w = _pre1(M, B, z, N)
    b = disp_bar(M, z)
    if w is None or b is None:
        return None
    hi1, _, _, _ = d1(B, z["dir"])
    _, _, c5, _ = d5(M, z["dir"])
    return (c5[b] - hi1[w[0]:w[1]].max()) / TICK


def m_pivot_clear(M, B, z, _):
    """Ticks by which the 5m CISD close clears the latest opposite 5m pivot (2-left / 2-right swing high) known before s5."""
    d = z["dir"]
    sw = M.fh if d == 1 else M.fl
    hi, _, _, _ = d5(M, d)
    s5 = s5_of(M, z)
    jj = int(np.searchsorted(sw, s5 - 2)) - 1      # pivot p confirmed at the close of p + 2 <= s5 - 1
    if jj < 0 or sw[jj] < M.ctx[z["k"]]["s"] - 600:
        return None
    return (z["trig_c"] - hi[int(sw[jj])]) / TICK


def m_run_age(M, B, z, _):
    return z["i"] - z["ref_i"] + 1


def m_stop_pen(M, B, z, _):
    pen = lev_L(z) - z["ext_d"]
    if pen <= 0:
        return None
    ep = min(float(z["ref_d"]), z["trig_c"])
    return (ep - (z["ext_d"] - P_LIVE["stop_buf"])) / pen


PRE = {"L01": m_eff, "L02": m_cloc, "L03": m_reclaim, "L04": m_disp_prompt, "L05": m_cisd_prompt, "L06": m_idm_prom,
       "L07": m_sep, "L08": m_idm_recency, "L09": m_touches, "L10": m_raid, "L11": m_appr_eff, "L12": m_appr_overlap,
       "L13": m_disp_beyond, "L14": m_pivot_clear, "L15": m_run_age, "L19": m_stop_pen}


# ------------------------------------------------------------------------------------------------ wait-window (L16-L20)
def window(M, B, z, t):
    """(k0, kd): 1m indices of the first bar after the 5m CISD close and of the 1m CISD decision bar (fill bar - 1)."""
    if B is None or t.get("tf") != 1 or z["k"] not in B.full:
        return None
    k0 = int(np.searchsorted(B.t, int(M.t[z["entry_i"]])))
    kf = int(np.searchsorted(B.t, int(t["entry_t"])))
    if kf >= B.n or int(B.t[kf]) != int(t["entry_t"]) or kf - 1 < k0:
        return None
    return k0, kf - 1


def w_arm(M, B, z, t, N):
    """L16: keep = N consecutive 1m closes above the 5m CISD level before the limit is touched (arming after the CISD)."""
    w = window(M, B, z, t)
    if w is None:
        return None
    k0, kd = w
    _, lo, c, _ = d1(B, z["dir"])
    ep = min(float(z["ref_d"]), z["trig_c"])
    run = 0
    for k in range(k0, kd + 1):
        if lo[k] <= ep:
            return False                 # touched before armed
        run = run + 1 if c[k] > z["ref_d"] else 0
        if run >= N:
            return True
    return False


def w_adverse(M, B, z, t, _):
    """L17: the biggest adverse 1m body / A among the bars that closed while the entry waited."""
    w = window(M, B, z, t)
    A = feat_atr(M, z)
    if w is None or A is None:
        return None
    k0, kd = w
    if kd <= k0:
        return 0.0
    _, _, c, o = d1(B, z["dir"])
    return float(max(0.0, (o[k0:kd] - c[k0:kd]).max()) / A)


def w_age(M, B, z, t, _):
    """L18: minutes from the 5m CISD close to the 1m CISD decision (the decision bar's close)."""
    w = window(M, B, z, t)
    if w is None:
        return None
    return (int(B.t[w[1]]) + 60 - int(M.t[z["entry_i"]])) / 60.0


def w_opp_cisd(M, B, z, t, N):
    """L20: keep = no run of N consecutive 1m closes below an opposite (bearish for a long) 1m CISD level while waiting."""
    w = window(M, B, z, t)
    if w is None:
        return None
    k0, kd = w
    hi, _, c, o = d1(B, z["dir"])
    oc, oo = -c, -o                      # opposite direction space
    run, lvl_prev = 0, None
    for k in range(k0, kd):
        hk = k0 + int(np.argmax(hi[k0:k + 1]))
        cz = lit._cisd_level(oc, oo, hk) if hk >= 3 else None
        if cz is None or k <= hk:
            run = 0
            continue
        lvl = -cz[0]
        if lvl != lvl_prev:
            run, lvl_prev = 0, lvl
        run = run + 1 if c[k] < lvl else 0
        if run >= N:
            return False
    return True


WAIT = {"L16": w_arm, "L17": w_adverse, "L18": w_age, "L20": w_opp_cisd}

# rule -> (ChatGPT rank, plain name, metric param per variant, threshold per variant, keep if)
RULES = collections.OrderedDict([
    ("L01", (8, "displacement body efficiency |C-O|/(H-L) of LIT's displacement bar", [None] * 3, [0.7, 0.6, 0.8], ">=")),
    ("L02", (9, "displacement close location (C-L)/(H-L)", [None] * 3, [0.85, 0.75, 0.95], ">=")),
    ("L03", (4, "prompt reclaim: 1m close back through the level within k 1m bars of the sweep bar", [None] * 3, [2, 1, 3], "<=")),
    ("L04", (5, "prompt displacement: qualifying displacement closes within k 1m bars of the sweep bar", [None] * 3, [3, 1, 5], "<=")),
    ("L05", (7, "prompt 5m CISD: CISD close within k minutes of the 1m sweep bar's close", [None] * 3, [10, 5, 15], "<=")),
    ("L06", (2, "inducement prominence / ATR", [None] * 3, [0.25, 0.125, 0.5], ">=")),
    ("L07", (1, "inducement-to-level separation (I - L) / ATR", [None] * 3, [0.25, 0.125, 0.5], ">=")),
    ("L08", (12, "inducement recency: sweep within k minutes of the inducement being known", [None] * 3, [30, 15, 60], "<=")),
    ("L09", (13, "prior touches of the level (episodes, reset after N quiet bars) <= k", [1, 2, 3], [1, 0, 2], "<=")),
    ("L10", (16, "isolated raid: extra known levels crossed by the 1m sweep bar <= k", [None] * 3, [1, 0, 2], "<=")),
    ("L11", (14, "approach efficiency over N 1m closes before the sweep >= k", [5, 3, 8], [0.65, 0.5, 0.8], ">=")),
    ("L12", (15, "approach overlap of consecutive 1m ranges over N bars <= k", [5, 3, 8], [0.5, 0.35, 0.65], "<=")),
    ("L13", (3, "displacement closes beyond the last N 1m bars' opposite extreme by >= k ticks", [3, 2, 5], [1, 0, 2], ">=")),
    ("L14", (6, "5m CISD close clears the latest opposite 5m pivot by >= k ticks", [None] * 3, [1, 0, 2], ">=")),
    ("L15", (10, "CISD run age: 5m bars from run start to the CISD close <= k", [None] * 3, [6, 3, 12], "<=")),
    ("L16", (17, "after the 5m CISD wait N 1m closes on the favourable side before arming", [2, 1, 3], [None] * 3, "bool")),
    ("L17", (18, "cancel when a 1m adverse body / ATR > k while waiting", [None] * 3, [0.6, 0.4, 0.8], "<=")),
    ("L18", (19, "cancel the waiting entry k minutes after the 5m CISD", [None] * 3, [15, 10, 20], "<=")),
    ("L19", (11, "stop / sweep penetration beyond the level <= k", [None] * 3, [3, 2, 4], "<=")),
    ("L20", (20, "cancel after N 1m closes beyond an opposite 1m CISD level", [2, 1, 3], [None] * 3, "bool")),
])
VARS = ("P", "A1", "A2")


def keep_of(val, thr, how):
    if val is None:
        return True                      # UNKNOWN = no trade change
    if how == "bool":
        return bool(val)
    return val >= thr - 1e-12 if how == ">=" else val <= thr + 1e-12


def variants():
    out = collections.OrderedDict()
    for L, (rank, name, pars, thrs, how) in RULES.items():
        for vi, vn in enumerate(VARS):
            p, th = pars[vi], thrs[vi]
            lab = (f"N {p}" if p is not None else "") + (", " if p is not None and th is not None else "") + \
                  (f"k {th}" if th is not None else "")
            out[f"{L}_{vn}"] = {"rule": L, "var": vn, "rank": rank, "name": name, "param": p, "thr": th, "how": how,
                                "label": f"{L} {vn} ({lab}): {name}"}
    return out


# ================================================================================================ running
_S = {}


def base():
    if "B" not in _S:
        M, C, B1, B5 = SUP.base()
        Tb = lit.run_x(M, C, P_LIVE, F.SESS, B1=B1, B5=B5)
        _S.update(B=(M, C, B1, B5), Tb=Tb, byk={key(z): z for z in C})
    return _S["B"]


def run_var(v, M=None, C=None, B1=None, B5=None):
    """Trades, info for one L variant."""
    M, C, B1, B5 = base() if M is None else (M, C, B1, B5)
    L = v["rule"]
    info = {}
    if L in PRE:
        fn = PRE[L]
        vals = {key(z): fn(M, B1, z, v["param"]) for z in C}
        skip = [list(k) for k, x in vals.items() if not keep_of(x, v["thr"], v["how"])]
        info["unknown_2026"] = sum(1 for k, x in vals.items() if x is None and k[0] >= "2026")
        info["flagged_cands"] = len(skip)
        T = lit.run_x(M, C, {**P_LIVE, "skip_keys": skip}, F.SESS, B1=B1, B5=B5)
        return T, info
    fn = WAIT[L]
    byk = {key(z): z for z in C}
    skip, seen, it = set(), {}, 0
    while True:
        it += 1
        T = lit.run_x(M, C, {**P_LIVE, "skip_keys": [list(k) for k in skip]}, F.SESS, B1=B1, B5=B5)
        new = 0
        for t in T:
            k = (t["day"], int(t["i"]), int(t["dir"]))
            if k in seen:
                continue
            x = fn(M, B1, byk[k], t, v["param"])
            seen[k] = x
            if not keep_of(x, v["thr"], v["how"]):
                skip.add(k)
                new += 1
        if not new:
            break
    info.update(iterations=it, cancelled=len(skip), unknown_2026=sum(1 for k, x in seen.items() if x is None and k[0] >= "2026"))
    return T, info


def tail(T, Tb):
    kv = {(t["day"], int(t["entry_t"])) for t in T}
    o = {}
    for r in TAILS:
        bt = [t for t in Tb if t["day"] >= "2026" and float(t["mfe"]) >= r]
        o[f"{r:g}R"] = {"all": len(bt), "kept": sum(1 for t in bt if (t["day"], int(t["entry_t"])) in kv),
                        "pct": round(100.0 * sum(1 for t in bt if (t["day"], int(t["entry_t"])) in kv) / max(len(bt), 1), 1)}
    return o


def score(T, Tb):
    o = SUP.score_all(T, {}, Tb)
    for part in ("lit", "eval"):         # a span with no trades: zeros (not None) so the deltas work
        for sp in ("H1", "H2", "2026", "2021-25"):
            s = o[part].setdefault(sp, {})
            for k_ in ("n", "tpw", "win", "pf", "net", "per_month", "dd", "p10", "f10"):
                if s.get(k_) is None:
                    s[k_] = 0
    o["tail"] = tail(T, Tb if Tb is not None else T)
    return o


def verdict(o, b):
    v = SUP.verdict(o, b)
    v["tail4"] = o["tail"]["4R"]["pct"]
    v["candidate"] = bool(v["candidate"] and v["tail4"] >= 90.0)
    return v


# ------------------------------------------------------------------------------------------------ V3 / V4 target band
def cboe(name):
    df = pd.read_csv(os.path.join(CBOE, f"{name}_History.csv"))
    d = pd.to_datetime(df["DATE"]).dt.strftime("%Y-%m-%d")
    return list(d), df["CLOSE"].values.astype(float)


def ctx_with(M, src):
    """M.ctx with vix_move from another CBOE index (prior-day close: the last close before the trading day)."""
    import bisect
    if src == "VIX":
        return M.ctx
    dd, cc = cboe(src)
    out = []
    for x in M.ctx:
        y = dict(x)
        j = bisect.bisect_left(dd, x["date"]) - 1
        if j >= 0 and cc[j] > 0:
            y["vix_move"] = float(cc[j]) / 100.0 / math.sqrt(252.0) * float(x["open18"])
        else:
            y.pop("vix_move", None)
        out.append(y)
    return out


VT = collections.OrderedDict([
    ("V3_k10", ("VXN", 1.0, True)), ("V3_k09", ("VXN", 0.9, True)), ("V3_k11", ("VXN", 1.1, True)),
    ("V4_k10", ("VIX9D", 1.0, True)), ("V4_k09", ("VIX9D", 0.9, True)), ("V4_k11", ("VIX9D", 1.1, True)),
    ("CTRL_vix_k09", ("VIX", 0.9, False)), ("CTRL_vix_k11", ("VIX", 1.1, False)),
])


def run_vt(name):
    M, C, B1, B5 = base()
    src, k, _ = VT[name]
    keep = M.ctx
    try:
        M.ctx = ctx_with(M, src)
        T = lit.run_x(M, C, {**P_LIVE, "vix_k": k}, F.SESS, B1=B1, B5=B5)
    finally:
        M.ctx = keep
    return T, {"src": src, "vix_k": k}


# ================================================================================================ main
def main():
    M, C, B1, B5 = base()
    Tb = _S["Tb"]
    b = score(Tb, None)
    print(f"base lit_live 2026: {sum(1 for t in Tb if t['day'] >= '2026')} trades "
          f"{round(sum(t['pnl'] for t in Tb if t['day'] >= '2026')):+,}; tails {b['tail']}", flush=True)
    res = {"_base": b, "_n_tests": 0, "variants": {}, "targets": {}}
    for nm, v in variants().items():
        T, info = run_var(v)
        o = score(T, Tb)
        o.update(spec=v, info=info, v=verdict(o, b))
        res["variants"][nm] = o
        res["_n_tests"] += 1
        print(line(nm, o), info, o["changed_2026"], flush=True)
    for nm, (src, k, counted) in VT.items():
        T, info = run_vt(nm)
        o = score(T, Tb)
        o.update(info=info, v=verdict(o, b), counted=counted)
        res["targets"][nm] = o
        res["_n_tests"] += int(counted)
        print(line(nm, o), info, o["changed_2026"], flush=True)
    json.dump(res, open(OUT, "w"), indent=1, default=str)
    return res


def line(nm, o):
    L, E, v = o["lit"], o["eval"], o["v"]
    f = lambda s: f"{L[s]['tpw']}/wk PF {L[s]['pf']} {L[s]['net']:+,}"  # noqa
    return (f"{nm:13s} dH1 {v['dH1']:+7,} dH2 {v['dH2']:+7,} tail4 {v['tail4']:5.1f} cand={v['candidate']} | 2026[{f('2026')}] "
            f"H1[{f('H1')}] H2[{f('H2')}] 21-25[{f('2021-25')}] | eval 2w H1 {E['H1']['p10']}/{E['H1']['f10']} "
            f"H2 {E['H2']['p10']}/{E['H2']['f10']}")


# ================================================================================================ placebo
def placebo(n=200, seed=7):
    """Candidates + the five best H1 non-candidates: the same number of random skips of the base's trades per span (H1,
    H2, 2021-25), n draws; where the variant's H1 / H2 $ change sits in that distribution."""
    res = json.load(open(OUT))
    M, C, B1, B5 = base()
    Tb = _S["Tb"]
    bl = res["_base"]["lit"]
    rng = random.Random(seed)
    allv = {**res["variants"], **{k: v for k, v in res["targets"].items()}}
    pick = [k for k, o in allv.items() if o["v"]["candidate"]]
    pick += [k for k, _ in sorted(((k, o) for k, o in allv.items() if not o["v"]["candidate"] and o["v"]["dH1"] > 0),
                                  key=lambda kv: -kv[1]["v"]["dH1"])[:5]]
    V_ = variants()
    pools = {"H1": [t for t in Tb if "2026-01-01" <= t["day"] <= "2026-06-30"], "H2": [t for t in Tb if t["day"] >= "2026-07-01"],
             "old": [t for t in Tb if t["day"] < "2026"]}
    for nm in pick:
        o = allv[nm]
        Tv = run_var(V_[nm])[0] if nm in V_ else run_vt(nm)[0]
        kv = {(t["day"], int(t["entry_t"])) for t in Tv}
        dropped = [t for t in Tb if (t["day"], int(t["entry_t"])) not in kv]
        n1 = sum(1 for t in dropped if "2026-01-01" <= t["day"] <= "2026-06-30")
        n2 = sum(1 for t in dropped if t["day"] >= "2026-07-01")
        n0 = sum(1 for t in dropped if t["day"] < "2026")
        d1_, d2_ = [], []
        for _ in range(n):
            pk = rng.sample(pools["H1"], n1) + rng.sample(pools["H2"], n2) + rng.sample(pools["old"], min(n0, len(pools["old"])))
            ks = [[t["day"], int(t["i"]), int(t["dir"])] for t in pk]
            T = lit.run_x(M, C, {**P_LIVE, "skip_keys": ks}, F.SESS, B1=B1, B5=B5)
            s = AB.fast(T)
            d1_.append(s["H1"] - bl["H1"]["net"]); d2_.append(s["H2"] - bl["H2"]["net"])
        d1_, d2_ = np.array(d1_), np.array(d2_)
        o["placebo"] = {"n": n, "dropped": {"H1": n1, "H2": n2, "2021-25": n0},
                        "H1_mean": round(float(d1_.mean())), "H2_mean": round(float(d2_.mean())),
                        "H1_p_ge": round(float((d1_ >= o["v"]["dH1"]).mean()), 3),
                        "H2_p_ge": round(float((d2_ >= o["v"]["dH2"]).mean()), 3),
                        "both_p_ge": round(float(((d1_ >= o["v"]["dH1"]) & (d2_ >= o["v"]["dH2"])).mean()), 3)}
        print(nm, o["placebo"], flush=True)
    json.dump(res, open(OUT, "w"), indent=1, default=str)


# ================================================================================================ look-ahead check
def lookahead(n=400, seed=1):
    """Pre-trigger features: every 5m bar after the trigger bar i and every 1m bar from the trigger bar's close on are
    overwritten with noise; each feature must come out the same. Wait-window features (L16-L20): every 1m bar from the 1m
    CISD decision bar on (and every 5m bar after i) is overwritten; the same check on the base's 2026 trades."""
    M, C, B1, B5 = base()
    Tb = _S["Tb"]
    byk = _S["byk"]
    rng = np.random.default_rng(seed)
    c26 = [z for z in C if z["day"] >= "2026"]
    S_ = [c26[int(q)] for q in rng.choice(len(c26), size=min(n // 2, len(c26)), replace=False)] + \
         [C[int(q)] for q in rng.choice(len(C), size=n // 2, replace=False)]
    arr5, arr1 = ("o", "h", "l", "c"), ("o", "h", "l", "c")
    k5 = {a: getattr(M, a).copy() for a in arr5}
    k1 = {a: getattr(B1, a).copy() for a in arr1}
    V_ = variants()
    pars = {L: sorted({v["param"] for v in V_.values() if v["rule"] == L}, key=str) for L in RULES}
    bad, checked = collections.Counter(), collections.Counter()

    def noise(i5, j1):
        for a in arr5:
            x = k5[a].copy(); x[i5 + 1:] += rng.normal(0, 50, size=len(x) - i5 - 1); setattr(M, a, x)
        for a in arr1:
            x = k1[a].copy(); x[j1:] += rng.normal(0, 50, size=len(x) - j1); setattr(B1, a, x)

    def restore():
        for a in arr5:
            setattr(M, a, k5[a])
        for a in arr1:
            setattr(B1, a, k1[a])
    try:
        for z in S_:
            ref = {(L, p): fn(M, B1, z, p) for L, fn in PRE.items() for p in pars[L]}
            noise(z["i"], int(np.searchsorted(B1.t, int(M.t[z["i"]]) + 300)))
            for (L, p), r in ref.items():
                checked[L] += 1
                x = PRE[L](M, B1, z, p)
                if not (x == r or (x is not None and r is not None and abs(x - r) < 1e-9)):
                    bad[L] += 1
            restore()
        for t in [t for t in Tb if t["day"] >= "2026" and t.get("tf") == 1]:
            z = byk[(t["day"], int(t["i"]), int(t["dir"]))]
            ref = {(L, p): fn(M, B1, z, t, p) for L, fn in WAIT.items() for p in pars[L]}
            kf = int(np.searchsorted(B1.t, int(t["entry_t"])))
            noise(z["i"], kf - 1)
            for (L, p), r in ref.items():
                checked[L] += 1
                x = WAIT[L](M, B1, z, t, p)
                if not (x == r or (x is not None and r is not None and abs(x - r) < 1e-9)):
                    bad[L] += 1
            restore()
    finally:
        restore()
    print(f"look-ahead check: {dict(checked)}; changed by future bars: {dict(bad) or 'none'}", flush=True)
    res = json.load(open(OUT)) if os.path.exists(OUT) else {}
    res["_lookahead"] = {"checked": dict(checked), "changed": dict(bad)}
    json.dump(res, open(OUT, "w"), indent=1, default=str)
    return not bad


# ================================================================================================ store runs
def _h(s):
    return f"n={s['n']} {s['tpw']}/wk win {s['win']}% PF {s['pf']} net {s['net']:+,} (${s['per_month']:,}/mo) DD {s['dd']:,}"


def _he(s):
    return f"PF {s['pf']} net {s['net']:+,} (${s['per_month']:,}/mo); 2-week pass/fail {s['p10']}/{s['f10']}"


def save():
    from tools import runlib as rl
    res = json.load(open(OUT))
    idx = rl.index
    rl.index = lambda: None
    V_ = variants()
    try:
        items = [(nm, res["variants"][nm], V_[nm]) for nm in V_ if nm in res["variants"]] + \
                [(nm, res["targets"][nm], None) for nm in VT if nm in res["targets"]]
        for nm, o, v in items:
            T, info = run_var(v) if v else run_vt(nm)
            Ts = [{k: x for k, x in t.items() if not k.startswith("_") and k not in ("size_why", "size_mult")} for t in T]
            l, e, vv = o["lit"], o["eval"], o["v"]
            st = "adopt-candidate" if vv["candidate"] else "rejected"
            pl = o.get("placebo")
            rid = "lit_gpt_" + nm.lower()
            title = ("LIT live + ChatGPT filter " + v["label"]) if v else \
                    (f"LIT live, target band from {VT[nm][0]} x {VT[nm][1]} (ChatGPT {'V3' if VT[nm][0] == 'VXN' else 'V4' if VT[nm][0] == 'VIX9D' else 'control'})")
            rl.save(rid, title, "other", Q,
                    params={**P_LIVE, "gpt_rule": nm, "spec": v, "info": info} if v else {**P_LIVE, "vix_k": VT[nm][1],
                                                                                          "band_src": VT[nm][0], "info": info},
                    trades=Ts, scored=rl.score(Ts, F.SESS), status=st,
                    verdict=(f"{'CANDIDATE' if vv['candidate'] else 'rejected'}: dH1 {vv['dH1']:+,} dH2 {vv['dH2']:+,} "
                             f"(2021-25 {vv['d2021_25']:+,}); tail retention MFE>=4R {vv['tail4']}% "
                             f"(3R {o['tail']['3R']['pct']}%, 5R {o['tail']['5R']['pct']}%). LIT size rule: 2026 H1 (pick) "
                             f"{_h(l['H1'])}; H2 (check) {_h(l['H2'])}; 2026 {_h(l['2026'])}; 2021-25 reference "
                             f"{_h(l['2021-25'])}. Eval path (two_week): H1 {_he(e['H1'])}; H2 {_he(e['H2'])}."
                             + (f" Placebo: {json.dumps(pl)}" if pl else "")),
                    notes="tools/lit_gpt_filters.py: engine/lit.py run_x on live_model.json lit (skip_keys; L16-L20 iterated "
                          "cancel of the virtual limit before the 1m CISD; V3/V4 = vix_move from CBOE VXN / VIX9D prior close); "
                          "eval path = lit_big_ideas executor (two_week).",
                    writeup="lit-chatgpt-filters", tags=["lit", "lit_gpt"])
            print("saved", rid, flush=True)
    finally:
        rl.index = idx
    rl.index()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    {"run": main, "placebo": placebo, "lookahead": lookahead, "save": save}[cmd]()
