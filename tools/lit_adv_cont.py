"""LIT Advanced Decisions Report, chapters 2-4 + experiment 4 of chapter 13 (owner's report of 2026-10-18; research material).

  ch2  fade vs continuation: the internal reference LIT sweeps is not the larger THESIS BOUNDARY (a farther low for a long,
       high for a short, whose break defeats the setup). Nine predeclared boundary selectors, each known before the sweep bar:
         last15 / last1h / last4h   the most recent confirmed fractal swing (k=2) of that timeframe still unbroken at the
                                    sweep bar (the protected low of the current leg)
         far1h / far4h              the nearest unbroken 1h / 4h swing BEYOND the swept level (the "farther" low)
         bos15 / bos1h / bos4h      the protected low of the last break of structure (close through a confirmed swing) of
                                    that timeframe: "against" when that break went the other way
         rng24                      the 24-hour range low before the sweep (internal sweep vs a new 24-hour extreme)
       status at the trigger bar: intact (the sweep extreme stayed inside it) / broken / against / absent.
       Tests on the live path: skip or half the broken (generic fade of a thesis-changing break) or the intact setups; for
       intact (boundary-preserving) setups a target at the next liquidity pool; and NEW continuation trades: sweeps of an
       internal 15m swing (not a LIT level) while the 1h structure boundary stays intact, same inducement / displacement /
       CISD / 1m entry / stop, to the VIX band or to the next pool.
  ch3  zone eligibility and session carryover (experiment 4): every pre-permission thesis (sweep + inducement + displacement
       + 5m CISD complete before 02:00 ET, from 18:00) keeps its first-known times (level known, eligibility = trigger close,
       order permission = 02:00) and, under CARRYOVER, places today's limit at 02:00 if it is still active (extreme intact,
       target not traded; optionally not yet mitigated); RESET = today's rule (dropped, wait for a new London sequence).
       Also: a London/NY thesis whose 30-minute limit expired untapped is re-armed at the next session open (03:00 / 08:00 /
       09:30) when still active and unmitigated.
  ch4  a weak zone reaction is not a completed trap (touch -> reaction -> failure of the swept level, each timestamped
       before the sweep); a timed forceful sweep without a pre-sweep pause can be continuation; a farther untaken objective
       just beyond the extreme ("on the way"); ES must reference the same event (ES's copy of the same named level swept in
       the same bars / ES led / NQ only, and ES's own 5m CISD by the same trigger bar; unmatched kept as unknown).

Scoring: the 2026 LIT candidate set of tools/lit_select.py (every setup the live filters accept, each simulated alone with the
live executor; the 1-a-day replay == run lit_live, see `check`); rules change skip / size / target on the real one-trade-a-day
path; size under the live two_week mode (engine/sizing.py two_week_qty via tools/lit_2wk.run_eval: a fresh MFFU 50K eval on
every session for p10/f10, $ from back-to-back evals reset at 10 sessions, tools/lit_ob.tw_score); the plain LIT rule $ for
reference; and per ORIGINAL candidate (unit R, skipped = 0). Pick on 2026 H1, check on H2; 2021-25 = reference (5m only).

  python tools/lit_adv_cont.py check       # base path == lit_live; annotation lookahead test
  python tools/lit_adv_cont.py grid        # every variant -> research/lit/adv_cont_results.json
  python tools/lit_adv_cont.py ledger      # the eligibility / carryover ledger -> research/lit/adv_cont_ledger.json
  python tools/lit_adv_cont.py save        # rl.save the runs lit_adv_* (family other, tags lit, lit_adv)
Paper only. 1 CPU process. Changes no engine file.
"""
from __future__ import annotations

import collections
import copy
import inspect
import json
import os
import pickle
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import data as edata  # noqa: E402
from engine import lit  # noqa: E402
from tools import lit_final as F  # noqa: E402
from tools import lit_select as S  # noqa: E402
from tools import lit_ob as OBT  # noqa: E402
from tools import runlib as rl  # noqa: E402

TL = S.TL
PU = S.PU
SESS = S.SESS
SPAN = S.SPAN
CACHE = os.path.join(ROOT, "research", "runs", "_cache")
OUTD = os.path.join(ROOT, "research", "lit")
OUT = os.path.join(OUTD, "adv_cont_results.json")
OUT_LEDGER = os.path.join(OUTD, "adv_cont_ledger.json")
VER = "v1"
PRICE = 91.80
TFS = ("15m", "1h", "4h")
LOOK = {"15m": 2 * 276, "1h": 5 * 276, "4h": 20 * 276}       # swing memory in 5m bars
SEL = ("last15", "last1h", "last4h", "far1h", "far4h", "bos15", "bos1h", "bos4h", "rng24")
MAJOR = {"pd", "pw", "pm", "gap"}
OPENS = (120, 180, 480, 510, 570)                             # 02:00, 03:00, 08:00, 08:30, 09:30 ET
_S = {}


# ================================================================================================ base data
def base():
    if "M" not in _S:
        M, C, B1, B5 = S.base()
        R = S.build()["rows"]
        Z = {(z["day"], z["i"], z["dir"]): z for z in C}
        _S.update(M=M, C=C, B1=B1, B5=B5, R=R, Z=Z)
    return _S["M"], _S["C"], _S["B1"], _S["B5"], _S["R"], _S["Z"]


def dirs(A, d):
    """direction-space (hi, lo, close, open) of an object with h, l, c, o arrays."""
    return (A.h, A.l, A.c, A.o) if d == 1 else (-A.l, -A.h, -A.c, -A.o)


# ================================================================================================ HTF swings and structure
def tf_key(t, mod, day_of, tf):
    if tf == "15m":
        return t // 900
    if tf == "1h":
        return t // 3600
    return np.asarray(day_of).astype(np.int64) * 10 + ((np.asarray(mod) - 1080) % 1440) // 240


def tf_struct(t, h, l, c, mod, day_of, tf):
    """Fractal swings (k=2) and breaks of structure of one timeframe built from 5m arrays; every object carries the 5m index
    whose close makes it known. Returns {d: {"sw": [(price_d, known5)], "bos": [(known5, dir, protected_price_d)]}} with
    prices in direction space of d (d=1: lows / protected lows; d=-1: negated highs)."""
    key = np.asarray(tf_key(t, mod, day_of, tf))
    n = len(key)
    st = np.r_[0, np.flatnonzero(np.diff(key) != 0) + 1]
    en = np.r_[st[1:], n]
    H = np.maximum.reduceat(h, st).astype(float); L = np.minimum.reduceat(l, st).astype(float)
    Cc = c[en - 1].astype(float); last = en - 1
    N = len(H)
    fh, fl = lit.fractals(H, L, 2)
    out = {1: {"sw": [], "bos": []}, -1: {"sw": [], "bos": []}}
    for j in fl:
        if j + 2 < N:
            out[1]["sw"].append((float(L[j]), int(last[j + 2])))
    for j in fh:
        if j + 2 < N:
            out[-1]["sw"].append((-float(H[j]), int(last[j + 2])))
    # breaks of structure: a TF close beyond the latest confirmed, unbroken swing (confirmed before that bar)
    conf_h = collections.defaultdict(list); conf_l = collections.defaultdict(list)
    for j in fh:
        if j + 2 < N:
            conf_h[j + 2].append(j)
    for j in fl:
        if j + 2 < N:
            conf_l[j + 2].append(j)
    sh = sl = None
    for b in range(N):
        if sh is not None and Cc[b] > H[sh]:
            out[1]["bos"].append((int(last[b]), 1, float(L[sh:b + 1].min())))
            out[-1]["bos"].append((int(last[b]), 1, None))
            sh = None
        if sl is not None and Cc[b] < L[sl]:
            out[-1]["bos"].append((int(last[b]), -1, -float(H[sl:b + 1].max())))
            out[1]["bos"].append((int(last[b]), -1, None))
            sl = None
        for j in conf_h.get(b, []):           # confirmed at the close of b: usable from b + 1
            sh = j
        for j in conf_l.get(b, []):
            sl = j
    for d in (1, -1):
        out[d]["sw"].sort(key=lambda x: x[1])
        out[d]["sw_k"] = np.array([x[1] for x in out[d]["sw"]], dtype=np.int64)
        out[d]["bos_k"] = np.array([x[0] for x in out[d]["bos"]], dtype=np.int64)
    return out


def structs(M):
    if "ST" not in _S:
        _S["ST"] = {tf: tf_struct(M.t, M.h, M.l, M.c, M.mod, M.day_of, tf) for tf in TFS}
    return _S["ST"]


def boundary(ST, lo_d, z, lev_near):
    """Status of every selector for setup z (direction space); everything used is known before the sweep bar sb."""
    sb, ee, ext, d = z["sweep_i"], z["ext_i"], z["ext_d"], z["dir"]
    out = {}
    for tf in TFS:
        X = ST[tf][d]
        hi_k = int(np.searchsorted(X["sw_k"], sb))         # swings known strictly before sb
        last = far = None
        for q in range(hi_k - 1, -1, -1):
            p, kn = X["sw"][q]
            if kn < sb - LOOK[tf]:
                break
            if kn + 1 < sb and lo_d[kn + 1:sb].min() < p:
                continue                                    # already broken before the sweep: no longer a boundary
            if last is None:
                last = p
            if p < lev_near and (far is None or p > far):
                far = p
        nm = {"15m": "15", "1h": "1h", "4h": "4h"}[tf]
        out["last" + nm] = "absent" if last is None else ("broken" if ext < last else "intact")
        if tf != "15m":
            out["far" + nm] = "absent" if far is None else ("broken" if ext < far else "intact")
        jb = int(np.searchsorted(X["bos_k"], sb)) - 1
        if jb < 0 or X["bos"][jb][0] < sb - LOOK[tf]:
            out["bos" + nm] = "absent"
        else:
            kn, bd, pp = X["bos"][jb]
            if bd != d:
                out["bos" + nm] = "against"
            elif kn + 1 < sb and lo_d[kn + 1:sb].min() < pp:
                out["bos" + nm] = "broken"                   # the protected low already failed before the sweep
            else:
                out["bos" + nm] = "broken" if ext < pp else "intact"
    a = max(0, sb - 288)
    out["rng24"] = ("broken" if ext < float(lo_d[a:sb].min()) else "intact") if sb - a >= 12 else "absent"
    return out


# ================================================================================================ ch4 features
def near_level(M, z):
    """(price_d, known index, name, class) of the nearest swept level (the internal reference LIT trades)."""
    d = z["dir"]
    lev_near = max(z["sw"].values())
    best = None
    for side, px, ki, nm, cls in M.levels(z["k"]):
        if (side == "low") != (d == 1):
            continue
        if abs(px * d - lev_near) < 1e-6 and ki < z["ext_i"]:
            if best is None or ki > best[1]:
                best = (lev_near, ki, nm, cls)
    return best


def trap(A, z, lv, s):
    """Touch -> reaction -> failure of the swept level before the sweep (direction space, all bars < the level's first
    breach). Returns dict with react_atr (max reaction after the first touch, ATR), touch / react / fail indices."""
    hi_d, lo_d, _, _ = dirs(A, z["dir"])
    lev, ki = lv[0], lv[1]
    a0 = max(ki + 1, s - 600)
    seg = lo_d[a0:z["ext_i"] + 1] < lev
    fb = a0 + int(np.argmax(seg)) if seg.any() else z["ext_i"]
    at = A.atr
    jt = None
    for j in range(a0, fb):
        if lo_d[j] <= lev + 0.1 * at[j]:
            jt = j
            break
    if jt is None:
        return {"touch": None, "react_atr": 0.0, "react_i": None, "fail": fb}
    mh = float(hi_d[jt:fb].max()) if fb > jt else float(hi_d[jt])
    ra = (mh - lev) / max(float(at[jt]), 1e-9)
    jr = None
    for j in range(jt, fb):
        if hi_d[j] - lev >= 1.0 * at[jt]:
            jr = j
            break
    return {"touch": jt, "react_atr": round(ra, 3), "react_i": jr, "fail": fb}


def force_pause(A, z):
    hi_d, lo_d, _, _ = dirs(A, z["dir"])
    sb, ee = z["sweep_i"], z["ext_i"]
    at = A.atr
    rng = (A.h[sb:ee + 1] - A.l[sb:ee + 1]) / np.maximum(at[sb:ee + 1], 1e-9)
    a = max(0, sb - 6)
    pause = (float(hi_d[a:sb].max()) - float(lo_d[a:sb].min())) / max(float(at[sb - 1]), 1e-9) if sb - a >= 3 else np.nan
    m = int(A.mod[sb])
    timed = any(o <= m < o + 15 for o in OPENS)
    return {"force": round(float(rng.max()), 3), "pause": round(float(pause), 3), "timed": int(timed)}


def onway(M, z, lo_d, s):
    """ATR distance from the sweep extreme to the nearest untaken level BEYOND it (the trade's adverse side) known before
    the extreme: (major levels only, any LIT level)."""
    d, ee, i, ext = z["dir"], z["ext_i"], z["i"], z["ext_d"]
    best_m = best_a = None
    for side, px, ki, nm, cls in M.levels(z["k"]):
        if (side == "low") != (d == 1) or ki >= ee:
            continue
        p = px * d
        if p >= ext:
            continue
        a0 = max(ki, s - 600) + 1
        if a0 <= i and lo_d[a0:i + 1].min() < p:
            continue
        dist = (ext - p) / max(z["atr_ext"], 1e-9)
        best_a = dist if best_a is None else min(best_a, dist)
        if cls in MAJOR:
            best_m = dist if best_m is None else min(best_m, dist)
    return {"onway_major": None if best_m is None else round(best_m, 3), "onway_any": None if best_a is None else round(best_a, 3)}


# ================================================================================================ ES, the same event
class ESMarket(lit.Market):
    def __init__(self):
        orig = lit.load
        lit.load = lambda sym, tf: edata.load("ES", tf)
        try:
            super().__init__()
        finally:
            lit.load = orig


def es_market():
    if "E" not in _S:
        E = ESMarket()
        _S["E"] = E
        _S["E_idx"] = {int(t): j for j, t in enumerate(E.t)}
        _S["E_day"] = {d: k for k, (d, s, e) in enumerate(E.days)}
    return _S["E"], _S["E_idx"], _S["E_day"]


def es_event(M, z, E, e_idx, e_day, t_cut=None):
    """ES on the same timestamps as NQ's setup. cls: both (ES took its copy of a swept named level between NQ's sweep bar and
    the trigger) / es_led (ES took it before NQ's sweep bar) / nq_only (ES did not take it by the trigger: SMT divergence) /
    unmatched (no copy or missing ES bars). shift: ES closed above its own 5m CISD level (from its own extreme in the same
    24 bars) by NQ's trigger bar: 1 / 0 / None."""
    d, i, ee, sb = z["dir"], z["i"], z["ext_i"], z["sweep_i"]
    ek = e_day.get(z["day"])
    ii, iee, isb, ia = (e_idx.get(int(M.t[j])) for j in (i, ee, sb, max(0, i - 24)))
    out = {"es_cls": "unmatched", "es_shift": None}
    if ek is None or None in (ii, iee, isb, ia):
        return out
    if t_cut is not None:
        assert int(E.t[ii]) <= t_cut
    ehi, elo, ec, eo = dirs(E, d)
    ex = E.ctx[ek]; es_ = ex["s"]
    res = []
    for nm in z["swept"]:
        base = nm[:-2] if nm.endswith(("_h", "_l")) else None
        lv = None
        if base in lit.SESSIONS and base in ex:
            hi_, lo_, ki = ex[base]
            lv = (lo_ if d == 1 else -hi_, ki)
        elif nm in ("pdl", "pwl", "pml", "pdh", "pwh", "pmh") and nm[:2] + "h" in ex:
            lv = (ex[nm[:2] + ("l" if d == 1 else "h")] * d, es_ - 1)
        if lv is None or lv[1] >= ii:
            continue
        pv, ki = lv
        a0 = max(ki + 1, es_ - 600)
        seg = elo[a0:ii + 1] < pv
        jb = a0 + int(np.argmax(seg)) if seg.any() else None
        res.append("nq_only" if jb is None else "es_led" if jb < isb else "both")
    if res:
        out["es_cls"] = "both" if "both" in res else "es_led" if "es_led" in res else "nq_only"
    eeE = ia + int(np.argmin(elo[ia:ii + 1]))
    if eeE < ii:
        cz = lit._cisd_level(ec, eo, eeE)
        if cz is not None:
            out["es_shift"] = int(bool((ec[eeE + 1:ii + 1] > cz[0]).any()))
    return out


# ================================================================================================ annotate every candidate
def annotate(force=False):
    p = os.path.join(CACHE, f"litadv_ann_{VER}_{rl._data_key().replace(':', '_')}.pkl")
    if os.path.exists(p) and not force:
        return pickle.load(open(p, "rb"))
    M, C, B1, B5, R, Z = base()
    ST = structs(M)
    E, e_idx, e_day = es_market()
    A = {}
    for r in R:
        z = Z[r["key"]]
        A[r["key"]] = ann_one(M, z, ST, E, e_idx, e_day)
    pickle.dump(A, open(p, "wb"))
    return A


def ann_one(M, z, ST, E, e_idx, e_day, t_cut=None):
    d = z["dir"]
    hi_d, lo_d, _, _ = dirs(M, d)
    s = M.ctx[z["k"]]["s"]
    lev_near = max(z["sw"].values())
    a = {"bd": boundary(ST, lo_d, z, lev_near)}
    lv = near_level(M, z)
    a["lv"] = None if lv is None else {"name": lv[2], "cls": lv[3], "known_i": lv[1]}
    a["trap"] = trap(M, z, lv, s) if lv is not None else None
    a.update(force_pause(M, z))
    a.update(onway(M, z, lo_d, s))
    a.update(es_event(M, z, E, e_idx, e_day, t_cut) if E is not None else {"es_cls": "unmatched", "es_shift": None})
    return a


class _Cut:
    """M with every 5m array cut after bar n (for the lookahead test)."""

    def __init__(self, M, n):
        self.__dict__.update(M.__dict__)
        for k in ("t", "o", "h", "l", "c", "v", "mod", "dow", "atr", "day_of"):
            setattr(self, k, getattr(M, k)[:n])
        self.n = n
        self._M = M

    def levels(self, k):
        return self._M.levels(k)


def lookahead(n=25, seed=3):
    """Annotations recomputed on 5m (and ES) data cut at the trigger bar close == the full-data annotations."""
    M, C, B1, B5, R, Z = base()
    A = annotate()
    E, e_idx, e_day = es_market()
    rng = np.random.default_rng(seed)
    keys = [r["key"] for r in R if r["day"] >= "2025-06-01"]
    bad = 0
    for q in rng.choice(len(keys), size=min(n, len(keys)), replace=False):
        key = keys[int(q)]
        z = Z[key]
        cut = z["i"] + 1
        Mc = _Cut(M, cut)
        STc = {tf: tf_struct(Mc.t, Mc.h, Mc.l, Mc.c, Mc.mod, Mc.day_of, tf) for tf in TFS}
        jc = int(np.searchsorted(E.t, M.t[z["i"]], side="right"))
        Ec = _Cut(E, jc)
        a = ann_one(Mc, z, STc, Ec, e_idx, e_day, t_cut=int(M.t[z["i"]]))
        b = A[key]
        same = json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)
        if not same:
            bad += 1
            print("DIFF", key, a, b)
    print(f"lookahead: {n} setups recomputed on data cut at the trigger bar, {n - bad} identical")
    return bad == 0


# ================================================================================================ extra candidates
def _patched_candidates():
    """lit.candidates with the evening (18:00-24:00) trigger bars allowed (ch3: Asia theses); otherwise identical."""
    if "cand_ev" not in _S:
        src = inspect.getsource(lit.candidates)
        a = "if not (t_from <= mod[i] < t_to) or mod[i] >= 1080:"
        b = "if ei >= e or mod[ei] >= 955 or mod[ei] >= 1080:"
        assert a in src and b in src
        src = src.replace(a, "if (t_to <= mod[i] < 1080) or mod[i] < t_from:")
        src = src.replace(b, "if ei >= e or (955 <= mod[ei] < 1080):")
        src = src.replace("def candidates(", "def candidates_ev(")
        ns = dict(vars(lit))
        ns["_week_context"] = _no_week
        exec(compile(src, "lit_candidates_ev", "exec"), ns)
        _S["cand_ev"] = ns["candidates_ev"]
    return _S["cand_ev"]


def pre_window_theses():
    """Every thesis completed before the 02:00 order permission (trigger bar 18:00-01:55, entry bar before 02:00), with the
    live filters except the entry window. Cached."""
    p = os.path.join(CACHE, f"litadv_prewin_{VER}_{rl._data_key().replace(':', '_')}.pkl")
    if os.path.exists(p):
        return pickle.load(open(p, "rb"))
    M = _days2026(base()[0])
    wk0 = lit._week_context
    lit._week_context = _no_week
    try:
        C2 = lit.candidates(M, ref=PU["ref"], evening=True)     # engine option (all-hours study): triggers from 18:30 ET
    finally:
        lit._week_context = wk0
    out = [z for z in C2 if (z["mod"] >= 1080 or z["mod"] < 120)]
    pickle.dump(out, open(p, "wb"))
    return out


def _no_week(M, C):
    for z in C:
        z["mw_break"] = None


def _days2026(M):
    """M with every day before 2026 emptied (the candidate generators skip it): the new setup types are built for 2026 only
    (the judged year); their 2021-25 reference line is therefore the base line."""
    M2 = copy.copy(M)
    M2.days = [(d, s_, e_) if d >= "2025-12-28" else (d, s_, s_) for d, s_, e_ in M.days]
    return M2


def plan(M, z, P=PU, window_free=False):
    Pw = {**P, "window": [[0, 1440]]} if window_free else P
    return S.plan_of(M, z, Pw)


def _sim(M, z, ep, tp, stop0, entry_i=None):
    B1, B5 = base()[2], base()[3]
    zz = z if entry_i is None else dict(z, entry_i=int(entry_i), entry_t=int(M.t[entry_i]), mod=int(M.mod[entry_i]))
    use1 = int(M.day_of[zz["entry_i"]]) in B1.full
    u = TL.tsim(M, B1 if use1 else B5, zz, ep, ep + tp, False, stop0, PU)
    if u is not None:
        u["r1"] = u["legs"][0][1] / u["risk_pts"]
    return u, zz


def _row(z, u, src, extra=None):
    r = {"day": z["day"], "key": (z["day"], z["i"], z["dir"], src), "entry_i": z["entry_i"], "u": u, "src": src,
         "z": {k: z[k] for k in ("i", "dir", "swept", "ext_i", "entry_i", "k")}}
    r.update(extra or {})
    return r


def carry_rows(start=1080, need_unmit=False, until=None):
    """ch3 CARRYOVER: pre-permission theses (entry bar from `start` ET, 1080 = 18:00, or from 00:00 when start < 120) whose
    limit is placed at the first 02:00 bar when still active: extreme intact, target untouched (need_unmit: CISD level not
    yet revisited either). Returns (rows, ledger)."""
    M = base()[0]
    rows, led = [], []
    for z in pre_window_theses():
        m = z["mod"]
        if start >= 1080:
            if not (m >= start or m < 120):
                continue
        elif not (start <= m < 120):
            continue
        pl = plan(M, z, window_free=True)
        if pl is None:
            continue
        x = M.ctx[z["k"]]
        s, e = x["s"], x["e"]
        k02 = next((j for j in range(z["entry_i"], e) if 120 <= M.mod[j] < 1080), None)
        rec = {"day": z["day"], "dir": z["dir"], "thesis_id": f"{z['day']}:{z['dir']}:{z['ext_i']}",
               "zone": z["swept"], "zone_created_at": None, "eligibility_event": "5m CISD close",
               "eligibility_available_at": int(M.t[z["i"]]) + 300, "initiating_session": "asia" if m >= 1080 else "late asia 00-02",
               "permission_at": int(M.t[k02]) if k02 is not None else None, "objective": "VIX band",
               "limit": round(pl["ep"] * z["dir"], 2), "stop": round(pl["stop0"] * z["dir"], 2)}
        lv = near_level(M, z)
        if lv is not None:
            rec["zone_created_at"] = int(M.t[lv[1]]) + 300 if lv[1] >= 0 else None
        if k02 is None:
            rec["expiry_reason"] = "no 02:00 bar"; led.append(rec); continue
        hi_d, lo_d, _, _ = dirs(M, z["dir"])
        seg_l = lo_d[z["i"] + 1:k02]; seg_h = hi_d[z["i"] + 1:k02]
        if len(seg_l) and seg_l.min() <= pl["stop0"]:
            rec["expiry_reason"] = "extreme broken before 02:00"; led.append(rec); continue
        if len(seg_h) and seg_h.max() >= pl["ep"] + pl["tp"]:
            rec["expiry_reason"] = "objective traded before 02:00"; led.append(rec); continue
        mit = bool(len(seg_l) and seg_l.min() <= pl["ep"])
        rec["mitigated_before_permission"] = mit
        if need_unmit and mit:
            rec["expiry_reason"] = "mitigated before 02:00 (no order)"; led.append(rec); continue
        if until is not None and M.mod[k02] >= until:
            rec["expiry_reason"] = "permission later than the age limit"; led.append(rec); continue
        u, zz = _sim(M, z, pl["ep"], pl["tp"], pl["stop0"], entry_i=k02)
        rec["expiry_reason"] = None if u is not None else "no fill in the 30-minute window / no 1m CISD"
        rec["result_r"] = None if u is None else round(u["r1"], 3)
        rec["exit"] = None if u is None else u["exit"]
        led.append(rec)
        rows.append(_row(zz, u, "carry", {"orig_mod": m, "mit": mit}))
    return rows, led


def rearm_rows(opens=(180, 480, 570)):
    """ch3: a live-filter setup whose 30-minute limit expired UNTAPPED (extreme intact, target untouched) is re-armed at the
    next session open in `opens` (ET minutes) when the thesis is still active and the CISD level still unmitigated."""
    M, C, B1, B5, R, Z = base()
    rows = []
    for r in R:
        if r["u"] is not None:
            continue
        z = Z[r["key"]]
        pl = plan(M, z)
        if pl is None:
            continue
        hi_d, lo_d, _, _ = dirs(M, z["dir"])
        a = z["entry_i"]; w = a + PU["wait"]
        x = M.ctx[z["k"]]; e = x["e"]
        if w >= e:
            continue
        if lo_d[a:w].min() <= pl["ep"] or hi_d[a:w].max() >= pl["ep"] + pl["tp"]:
            continue                                         # tapped (the order was used) or target hit: not an expiry
        nxt = next((j for j in range(w, e) if any(M.mod[j] == o for o in opens) and M.mod[j] < 930), None)
        if nxt is None:
            continue
        if nxt > w and (lo_d[w:nxt].min() <= pl["ep"] or hi_d[w:nxt].max() >= pl["ep"] + pl["tp"]):
            continue                                         # mitigated without an order / objective consumed / broken
        u, zz = _sim(M, z, pl["ep"], pl["tp"], pl["stop0"], entry_i=nxt)
        rows.append(_row(zz, u, "rearm", {"orig_mod": z["mod"]}))
    return rows


def internal_rows(tgt="vix", sel="bos1h"):
    """ch2 continuation trades: setups whose swept reference is only an INTERNAL 15m swing (not any LIT level), with the
    selected larger boundary intact (default: the protected low of the last 1h break of structure, which must point the
    trade's way); live inducement / displacement / CISD / 1m entry / stop; target the VIX band ("vix") or the nearest
    untaken LIT pool >= 1.5R ("pool", VIX band when none)."""
    M, C, B1, B5, R, Z = base()
    Ci = internal_candidates()
    ST = structs(M)
    have = {(z["day"], z["dir"], z["ext_i"]) for z in C}
    rows = []
    for z in Ci:
        if (z["day"], z["dir"], z["ext_i"]) in have or z["day"] not in set(SESS):
            continue
        if any(not nm.startswith("i15") for nm in z["swept"]):
            continue
        pl = plan(M, z)
        if pl is None:
            continue
        hi_d, lo_d, _, _ = dirs(M, z["dir"])
        bd = boundary(ST, lo_d, z, max(z["sw"].values()))
        if bd[sel] != "intact":
            continue
        tp = pl["tp"]
        if tgt == "pool":
            sh = z["entry_d"] - pl["ep"]
            ds = sorted(x + sh for c, v in z["targets"].items() if c != "internal" for x in v)
            ds = [x for x in ds if x >= PU["min_rr"] * pl["risk"]]
            if ds:
                tp = min(ds[0], PU["max_rr"] * pl["risk"])
        u, _ = _sim(M, z, pl["ep"], tp, pl["stop0"])
        rows.append(_row(z, u, "internal"))
    return rows


def internal_candidates():
    p = os.path.join(CACHE, f"litadv_int15_{VER}_{rl._data_key().replace(':', '_')}.pkl")
    if os.path.exists(p):
        return pickle.load(open(p, "rb"))
    M = base()[0]
    X = structs(M)["15m"]
    sw = {1: X[1]["sw"], -1: X[-1]["sw"]}
    kk = {d: X[d]["sw_k"] for d in (1, -1)}
    orig = M.levels

    def levels(k):
        L = list(orig(k))
        s, e = M.days[k][1], M.days[k][2]
        for d, side in ((1, "low"), (-1, "high")):
            a, b = int(np.searchsorted(kk[d], s - 288)), int(np.searchsorted(kk[d], e))
            for p_, kn in sw[d][a:b]:
                L.append((side, float(p_ * d), int(kn), "i15_" + side[0], "internal"))
        return L
    M2 = _days2026(M)
    M2.levels = levels
    wk0 = lit._week_context
    lit._week_context = _no_week
    try:
        C2 = lit.candidates(M2, ref=PU["ref"])
    finally:
        lit._week_context = wk0
    pickle.dump(C2, open(p, "wb"))
    return C2


# ================================================================================================ owner's session notes + SMT
def session_ctx():
    """Owner's LIT-group session notes, causal at each setup's trigger close (setups = sweep + inducement + displacement +
    5m CISD that pass the live setup filters, filled or not):
      asia_dir   direction of the latest Asia thesis of the trading day (trigger 18:00-01:55, the pre-02:00 theses)
      lon_dir    direction of the latest London / Frankfurt setup (entry 02:00-07:55) whose trigger closed before this one
      idm_pre_ny any Asia or London setup before 08:00 this day
      smt15      ATR distance from the sweep extreme to the nearest UNBROKEN 15m swing beyond it (liquidity right beside
                 the zone: the owner's Smart Money Trap), known before the extreme; None = none within 2 days"""
    p = os.path.join(CACHE, f"litadv_sess_{VER}_{rl._data_key().replace(':', '_')}.pkl")
    if os.path.exists(p):
        return pickle.load(open(p, "rb"))
    M, C, B1, B5, R, Z = base()
    Pw = {**PU, "window": [[0, 1440]]}
    asia = collections.defaultdict(list)
    for z in pre_window_theses():
        if lit.setup_ok(z, Pw, None):
            asia[z["day"]].append((int(M.t[z["i"]]), z["dir"]))
    lon = collections.defaultdict(list)
    for z in C:
        if 120 <= z["mod"] < 480 and lit.setup_ok(z, PU, None):
            lon[z["day"]].append((int(M.t[z["i"]]), z["dir"]))
    X = structs(M)["15m"]
    out = {}
    for r in R:
        z = Z[r["key"]]
        ti = int(M.t[z["i"]])
        a = [x for x in asia.get(z["day"], []) if x[0] < ti]
        l_ = [x for x in lon.get(z["day"], []) if x[0] < ti]
        d = z["dir"]
        hi_d, lo_d, _, _ = dirs(M, d)
        sw, kk = X[d]["sw"], X[d]["sw_k"]
        hi_k = int(np.searchsorted(kk, z["ext_i"]))
        best = None
        for q in range(hi_k - 1, -1, -1):
            p_, kn = sw[q]
            if kn < z["ext_i"] - LOOK["15m"]:
                break
            if p_ >= z["ext_d"]:
                continue
            if lo_d[kn + 1:z["i"] + 1].min() < p_:
                continue
            dd = (z["ext_d"] - p_) / max(z["atr_ext"], 1e-9)
            best = dd if best is None else min(best, dd)
        out[r["key"]] = {"asia_dir": max(a)[1] if a else 0, "lon_dir": max(l_)[1] if l_ else 0,
                         "idm_pre_ny": int(bool(a or [x for x in lon.get(z["day"], []) if x[0] < ti])),
                         "smt15": None if best is None else round(best, 3), "mod": z["mod"], "dir": d}
    pickle.dump(out, open(p, "wb"))
    return out


# ================================================================================================ the path and its scores
def merged(extra):
    R = base()[4]
    rows = list(R) + list(extra)
    rows.sort(key=lambda r: (r["entry_i"], -r["z"]["dir"], 0 if r.get("src") is None else 1))
    return rows


def ann_all():
    if "AA" not in _S:
        A = annotate()
        SC = session_ctx()
        Z = base()[5]
        M = base()[0]

        def own2(k):
            z = Z[k]
            q = [aa for dd, aa in z["idm_a"] if dd <= 1.0 and aa <= 36]
            em = int(M.mod[z["ext_i"]])
            return {"idm_age": min(q) if q else None, "cls": sorted(z["swept_cls"]),
                    "ext_open30": int(any(o <= em < o + 30 for o in OPENS))}
        _S["AA"] = {k: {**v, **SC.get(k, {}), **own2(k)} for k, v in A.items()}
    return _S["AA"]


def run(skip=None, size=None, extra=(), retarget=None):
    """The real one-trade-a-day path. skip(row, ann) / size(row, ann) on the original candidates (extra rows always pass);
    retarget(row, ann) -> a new u (target change) or None (keep)."""
    A = ann_all()
    rows = merged(extra)
    if retarget is not None:
        rr = []
        for r in rows:
            nu = retarget(r, A.get(r["key"])) if r.get("src") is None else None
            rr.append(dict(r, u=nu[1]) if nu is not None else r)
        rows = rr
    sk = (lambda r: r.get("src") is None and skip(r, A[r["key"]])) if skip else None
    sz = (lambda r: size(r, A[r["key"]]) if r.get("src") is None else 1.0) if size else None
    U = S.replay(rows, skip=sk, size=sz)
    for t in U:
        t["ob_m"] = t["g_m"]; t["wk_raw"] = t["wk_m"]
    return U, rows


def cand_r(rows, skip=None, size=None, span="H1"):
    """Per ORIGINAL candidate (live-filter setups of the span, each simulated alone, unit size, unfilled = 0): total unit R
    and the count; skipped = 0, sized = R x mult; extra rows add their own R."""
    A = ann_all()
    a, z = SPAN[span]
    tot, n = 0.0, 0
    for r in rows:
        if not (a <= r["day"] <= z):
            continue
        if r.get("src") is None:
            n += 1
        if r["u"] is None:
            continue
        if r.get("src") is None:
            if skip and skip(r, A[r["key"]]):
                continue
            m = size(r, A[r["key"]]) if size else 1.0
        else:
            m = 1.0
        tot += r["u"]["r1"] * m
    return round(tot, 2), n


def score(U, rows, skip=None, size=None):
    o2, _ = OBT.tw_score(U)
    lit_rule = TL.sized(U, ("lit", 800, 20.0))
    out = {}
    for sp in ("H1", "H2", "2026", "2021-25"):
        x = dict(o2[sp])
        st = TL.stats(lit_rule, sp)
        x["lit_net"] = st.get("net"); x["lit_pf"] = st.get("pf"); x["lit_dd"] = st.get("dd"); x["lit_pm"] = st.get("per_month")
        x["cand_r"], x["n_cand"] = cand_r(rows, skip, size, sp)
        x["cost_2wk"] = round(PRICE / (x["p10"] / 100)) if x.get("p10") else None
        out[sp] = x
    return out


def line(o, sp):
    x = o[sp]
    if not x.get("n"):
        return f"{sp}: n=0"
    return (f"{sp}: n={x['n']} {x['tpw']}/wk win {x['win']}% PF {x['pf']} {x['net']:+,} (${x['per_month']:,}/mo) DD {x['dd']:,} "
            f"2w {x['p10']}/{x['f10']} | LIT rule {x['lit_net']:+,} PF {x['lit_pf']} | candR {x['cand_r']:+} of {x['n_cand']}")


# ================================================================================================ the variants
def _half(cond):
    return lambda r, a: 0.5 if cond(r, a) else 1.0


def variants():
    V = collections.OrderedDict()
    # ---- ch2: the thesis boundary
    for sel in SEL:
        for st in ("broken", "intact") + (("against",) if sel.startswith("bos") else ()):
            c = (lambda sel, st: (lambda r, a: a["bd"][sel] == st))(sel, st)
            V[f"ch2 {sel}: skip {st}"] = dict(fam=f"ch2 {sel}", skip=c)
            V[f"ch2 {sel}: half {st}"] = dict(fam=f"ch2 {sel}", size=_half(c))
    V["ch2 boundary-preserving: target the next pool when bos1h intact"] = dict(fam="ch2 target", retarget=retarget_pool("bos1h"))
    V["ch2 boundary-preserving: target the next pool when last1h intact"] = dict(fam="ch2 target", retarget=retarget_pool("last1h"))
    V["ch2 boundary-preserving: target the next pool when rng24 intact"] = dict(fam="ch2 target", retarget=retarget_pool("rng24"))
    for sel in ("bos1h", "bos4h", "last1h"):
        for tg in ("vix", "pool"):
            V[f"ch2 continuation trades: internal 15m sweep, {sel} intact, target {tg}"] = dict(
                fam="ch2 continuation", extra=("internal", tg, sel))
    # ---- ch3: carryover vs reset
    for start, lab in ((1080, "18:00"), (1200, "20:00"), (0, "00:00")):
        for um in (False, True):
            V[f"ch3 carry pre-02:00 theses from {lab}{' (unmitigated only)' if um else ''}"] = dict(
                fam="ch3 carry", extra=("carry", start, um))
    for ops, lab in (((180, 480, 570), "03:00/08:00/09:30"), ((480, 570), "08:00/09:30"), ((570,), "09:30")):
        V[f"ch3 re-arm an expired untapped limit at the next open {lab}"] = dict(fam="ch3 rearm", extra=("rearm", ops))
    # ---- ch4: weak reaction vs completed trap
    for th in (0.5, 1.0, 1.5):
        pas = (lambda th: (lambda r, a: a["trap"] is not None and a["trap"]["react_atr"] < th))(th)
        V[f"ch4 trap: skip unless touch + reaction >= {th} ATR before the sweep"] = dict(fam="ch4 trap", skip=pas)
        V[f"ch4 trap: half unless touch + reaction >= {th} ATR"] = dict(fam="ch4 trap", size=_half(pas))
        V[f"ch4 trap: skip completed traps (reaction >= {th} ATR)"] = dict(fam="ch4 trap",
                                                                         skip=(lambda th: lambda r, a: a["trap"] is not None and a["trap"]["react_atr"] >= th)(th))
    pt = lambda r, a: a["trap"] is not None and a["trap"]["touch"] is None
    V["ch4 pass-through (no touch before the sweep): skip"] = dict(fam="ch4 trap", skip=pt)
    V["ch4 pass-through: half"] = dict(fam="ch4 trap", size=_half(pt))
    # ---- ch4: timed forceful sweep
    for fz in (1.5, 2.0, 2.5):
        for pz in (1.5, 2.5):
            c = (lambda fz, pz: lambda r, a: a["force"] >= fz and not (a["pause"] <= pz))(fz, pz)
            V[f"ch4 forceful (bar >= {fz} ATR) without a pause (6-bar range <= {pz} ATR): skip"] = dict(fam="ch4 force", skip=c)
            V[f"ch4 forceful (bar >= {fz} ATR) without a pause (<= {pz} ATR): half"] = dict(fam="ch4 force", size=_half(c))
        c = (lambda fz: lambda r, a: a["force"] >= fz and a["timed"] == 1)(fz)
        V[f"ch4 timed (first 15 min of an open) + forceful (>= {fz} ATR): skip"] = dict(fam="ch4 force", skip=c)
        V[f"ch4 timed + forceful (>= {fz} ATR): half"] = dict(fam="ch4 force", size=_half(c))
    for dz in (0.5, 1.0, 2.0):
        for key, lab in (("onway_major", "major"), ("onway_any", "any LIT")):
            c = (lambda key, dz: lambda r, a: a[key] is not None and a[key] <= dz)(key, dz)
            V[f"ch4 on the way: untaken {lab} level <= {dz} ATR beyond the extreme: skip"] = dict(fam="ch4 onway", skip=c)
            V[f"ch4 on the way: {lab} <= {dz} ATR: half"] = dict(fam="ch4 onway", size=_half(c))
    # ---- owner's session notes (LIT group)
    LONPRE = lambda a: 120 <= a["mod"] < 570
    for m, lab in ((0.5, "half"), (0.75, "0.75x"), (0.0, "skip")):
        f = (lambda m: (lambda c: dict(skip=c) if m == 0 else dict(size=lambda r, a: m if c(r, a) else 1.0)))(m)
        V[f"own Asia IDM -> London/pre-NY continue: {lab} London/pre-NY setups against Asia"] = dict(
            fam="own asia", **f(lambda r, a: LONPRE(a) and a["asia_dir"] != 0 and a["dir"] != a["asia_dir"]))
        V[f"own London IDM -> NY continues: {lab} NY (08:00+) setups against London"] = dict(
            fam="own london", **f(lambda r, a: a["mod"] >= 480 and a["lon_dir"] != 0 and a["dir"] != a["lon_dir"]))
        V[f"own London IDM -> NY continues: {lab} NY (09:30+) setups against London"] = dict(
            fam="own london", **f(lambda r, a: a["mod"] >= 570 and a["lon_dir"] != 0 and a["dir"] != a["lon_dir"]))
        V[f"own no IDM before NY: {lab} NY setups on days WITH an earlier IDM"] = dict(
            fam="own noidm", **f(lambda r, a: a["mod"] >= 480 and a["idm_pre_ny"] == 1))
        V[f"own no IDM before NY: {lab} NY setups on days WITHOUT an earlier IDM"] = dict(
            fam="own noidm", **f(lambda r, a: a["mod"] >= 480 and a["idm_pre_ny"] == 0))
        V[f"own sessions combined: {lab} setups against Asia (London/pre-NY) or against London (NY)"] = dict(
            fam="own combined", **f(lambda r, a: (LONPRE(a) and a["asia_dir"] != 0 and a["dir"] != a["asia_dir"]) or
                                    (a["mod"] >= 570 and a["lon_dir"] != 0 and a["dir"] != a["lon_dir"])))
        for dz in (0.25, 0.5, 1.0):
            V[f"own SMT trap: {lab} when an unbroken 15m swing sits <= {dz} ATR beyond the extreme"] = dict(
                fam="own smt", **f((lambda dz: lambda r, a: a["smt15"] is not None and a["smt15"] <= dz)(dz)))
            V[f"own SMT trap: {lab} when an untaken LIT level sits <= {dz} ATR beyond the extreme"] = dict(
                fam="own smt", **f((lambda dz: lambda r, a: a["onway_any"] is not None and a["onway_any"] <= dz)(dz)))
    # ---- owner's tips (2nd batch): inducement speed, hierarchy, session-open final inducement, continuation / reversal IDM
    RANK = lambda a: 3 if set(a["cls"]) & MAJOR else 2 if set(a["cls"]) & {"asia", "london", "ny", "pre"} else 1
    CONT = lambda a: a["bd"]["bos1h"] == "intact" and not (set(a["cls"]) & MAJOR)
    REV = lambda a: "buildup" in a["cls"] and a["bd"]["bos1h"] == "against"
    for m, lab in ((0.5, "half"), (0.75, "0.75x"), (0.0, "skip")):
        f = (lambda m: (lambda c: dict(skip=c) if m == 0 else dict(size=lambda r, a: m if c(r, a) else 1.0)))(m)
        for ag in (6, 12, 24):
            V[f"own2 IDM speed: {lab} when the inducement swing is older than {ag} bars at the sweep (slow = build-up)"] = dict(
                fam="own2 speed", **f((lambda ag: lambda r, a: a["idm_age"] is not None and a["idm_age"] > ag)(ag)))
        V[f"own2 hierarchy: {lab} when only a minor level (build-up) was swept"] = dict(fam="own2 rank", **f(lambda r, a: RANK(a) == 1))
        V[f"own2 hierarchy: {lab} unless a major level (PD/PW/PM/gap) was swept"] = dict(fam="own2 rank", **f(lambda r, a: RANK(a) < 3))
        V[f"own2 session open: {lab} unless the sweep extreme came within 30 min of an open"] = dict(
            fam="own2 open", **f(lambda r, a: a["ext_open30"] == 0))
        V[f"own2 continuation/reversal IDM: {lab} setups that are neither"] = dict(
            fam="own2 contrev", **f(lambda r, a: not (CONT(a) or REV(a))))
        V[f"own2 continuation IDM only: {lab} the rest"] = dict(fam="own2 contrev", **f(lambda r, a: not CONT(a)))
    # ---- post hoc (after the class tables): a compressed range just before the sweep (the 'pause') under-performed
    for pz in (1.0, 1.5, 2.0):
        c = (lambda pz: lambda r, a: a["pause"] <= pz)(pz)
        V[f"post pause before the sweep (6-bar range <= {pz} ATR): skip"] = dict(fam="post pause", skip=c)
        V[f"post pause before the sweep (6-bar range <= {pz} ATR): half"] = dict(fam="post pause", size=_half(c))
    # ---- ch4: ES, the same event
    for cl in ("nq_only", "es_led", "both"):
        c = (lambda cl: lambda r, a: a["es_cls"] == cl)(cl)
        V[f"ch4 ES same level: skip {cl}"] = dict(fam="ch4 es", skip=c)
        V[f"ch4 ES same level: half {cl}"] = dict(fam="ch4 es", size=_half(c))
    c = lambda r, a: a["es_shift"] == 0
    V["ch4 ES has not shifted (own 5m CISD) by NQ's trigger: skip"] = dict(fam="ch4 es", skip=c)
    V["ch4 ES has not shifted by NQ's trigger: half"] = dict(fam="ch4 es", size=_half(c))
    c = lambda r, a: a["es_shift"] == 1
    V["ch4 ES shifted first / same bar: skip"] = dict(fam="ch4 es", skip=c)
    return V


def retarget_pool(sel):
    """boundary-preserving setups (sel intact): target the nearest untaken LIT pool >= 1.5R instead of the VIX band (banked
    at 8R; the VIX band when no pool). Returns None (keep) or ("new", u or None)."""
    def fn(r, a):
        if a is None or a["bd"][sel] != "intact":
            return None
        M, C, B1, B5, R, Z = base()
        z = Z[r["key"]]
        pl = plan(M, z)
        sh = z["entry_d"] - pl["ep"]
        ds = sorted(x + sh for v in z["targets"].values() for x in v)
        ds = [x for x in ds if x >= PU["min_rr"] * pl["risk"]]
        if not ds:
            return None
        tp = min(ds[0], PU["max_rr"] * pl["risk"])
        if abs(tp - pl["tp"]) < 1e-9:
            return None
        return ("new", _sim(M, z, pl["ep"], tp, pl["stop0"])[0])
    return fn


_X = {}


def extra_of(spec):
    if spec is None:
        return []
    if spec not in _X:
        if spec[0] == "carry":
            _X[spec] = carry_rows(spec[1], spec[2])[0]
        elif spec[0] == "rearm":
            _X[spec] = rearm_rows(spec[1])
        elif spec[0] == "internal":
            _X[spec] = internal_rows(spec[1], spec[2])
    return _X[spec]


def run_spec(spec):
    ex = extra_of(spec.get("extra"))
    U, rows = run(spec.get("skip"), spec.get("size"), ex, spec.get("retarget"))
    return score(U, rows, spec.get("skip"), spec.get("size")), U, rows


# ================================================================================================ commands
def _compact(o):
    keys = ("n", "tpw", "wk2", "win", "pf", "net", "per_month", "dd", "p10", "f10", "p20", "f20", "pass_med", "cost_2wk", "b2b",
            "lit_net", "lit_pf", "lit_dd", "lit_pm", "cand_r", "n_cand")
    return {s: {k: o[s].get(k) for k in keys} for s in o}


def verdict(o, b):
    h1, h2 = o["H1"], o["H2"]
    B1_, B2_ = b["H1"], b["H2"]
    up = lambda x, y: (x["p10"] > y["p10"] and x["net"] > y["net"])
    eq = lambda x, y: (x["p10"] == y["p10"] and x["net"] == y["net"] and x["n"] == y["n"])
    if eq(h1, B1_) and eq(h2, B2_):
        return "no change"
    tpw_ok = min(h1["tpw"], h2["tpw"]) >= 2.0
    if up(h1, B1_) and up(h2, B2_):
        return "both halves up" + ("" if tpw_ok else " but < 2 trades/wk")
    if up(h1, B1_):
        return "H1 only"
    if up(h2, B2_):
        return "H2 only"
    return "worse"


def grid(only=None):
    base_o, U0, rows0 = run_spec({})
    print("BASE")
    for sp in ("H1", "H2", "2026", "2021-25"):
        print("  " + line(base_o, sp))
    out = collections.OrderedDict(base={"o": _compact(base_o)})
    V = variants()
    pri = lambda nm: (0 if nm.startswith("own") else 1 if nm.startswith("ch4") else 2 if nm.startswith("ch2") and "extra" not in V[nm]
                      else 3 if nm.startswith("ch3") else 4)
    dest = OUT if not only else OUT.replace(".json", "_" + OBT._slug(only) + ".json")
    for nm in sorted(V, key=pri):
        spec = V[nm]
        if only and not any(nm.startswith(x) for x in only.split(",")):
            continue
        o, U, rows = run_spec(spec)
        v = verdict(o, base_o)
        out[nm] = {"fam": spec["fam"], "o": _compact(o), "verdict": v}
        print(f"\n{nm}  [{v}]")
        for sp in ("H1", "H2", "2021-25"):
            print("  " + line(o, sp), flush=True)
        json.dump(out, open(dest, "w"), indent=1, default=float)
    json.dump(out, open(dest, "w"), indent=1, default=float)
    return out


def check():
    M, C, B1, B5, R, Z = base()
    U, rows = run()
    n26 = [t for t in TL.sized(U, ("lit", 800, 20.0)) if t["day"] >= "2026"]
    net = sum(t["pnl"] for t in n26)
    print(f"base path: 2026 {len(n26)} trades, LIT rule net {net:+,.0f} (run lit_live: 120, +41,734)")
    ok = len(n26) == 120 and abs(net - 41734) < 2
    return lookahead() and ok


def ledger():
    """ch3 ledger: every pre-permission thesis with its first-known times and what carryover did with it, plus the
    paired carry-vs-reset outcome per initiating thesis on the real path."""
    rows, led = carry_rows(1080, False)
    base_o, U0, _ = run_spec({})
    o, U1, _ = run_spec({"extra": ("carry", 1080, False)})
    day0 = collections.defaultdict(float); day1 = collections.defaultdict(float)
    for t in OBT.tw_score(U0, spans=("2026",))[1]:
        day0[t["day"]] += t["pnl"]
    for t in OBT.tw_score(U1, spans=("2026",))[1]:
        day1[t["day"]] += t["pnl"]
    U0d = {t["day"]: t for t in U0}
    U1d = {t["day"]: t for t in U1}
    for rec in led:
        d = rec["day"]
        b, c = U0d.get(d), U1d.get(d)
        rec["reset_day_trade_r"] = None if b is None else round(b["legs"][0][1] / b["risk_pts"], 3)
        rec["carry_day_trade_r"] = None if c is None else round(c["legs"][0][1] / c["risk_pts"], 3)
        rec["carry_took_it"] = bool(c is not None and b is not None and c["entry_t"] != b["entry_t"]) or (c is not None and b is None)
    s26 = [r for r in led if r["day"] >= "2026"]
    reasons = collections.Counter(r.get("expiry_reason") or "traded (filled)" for r in s26)
    summ = {"theses_2026": len(s26), "reasons": dict(reasons),
            "zone_known_before_eligibility": all(r["zone_created_at"] is None or r["zone_created_at"] <= r["eligibility_available_at"]
                                                 for r in led),
            "eligibility_before_permission": all(r["permission_at"] is None or r["eligibility_available_at"] <= r["permission_at"]
                                                 for r in led)}
    for sp in ("H1", "H2"):
        a, z = SPAN[sp]
        L = [r for r in led if a <= r["day"] <= z]
        took = [r for r in L if r["carry_took_it"]]
        summ[sp] = {"theses": len(L), "carried_and_filled": sum(1 for r in L if r.get("result_r") is not None),
                    "days_changed": len(took),
                    "carry_r_on_changed_days": round(sum(r["carry_day_trade_r"] or 0 for r in took), 2),
                    "reset_r_on_changed_days": round(sum(r["reset_day_trade_r"] or 0 for r in took), 2)}
    json.dump({"summary": summ, "ledger": led}, open(OUT_LEDGER, "w"), indent=1, default=float)
    print(json.dumps(summ, indent=1))
    return summ


def describe():
    """Class counts and unit-R by class for the 2026 candidates (H1 / H2), for the write-up."""
    M, C, B1, B5, R, Z = base()
    A = annotate()
    out = {}

    def cls_of(a):
        c = {f"bd_{s}": a["bd"][s] for s in SEL}
        tr = a["trap"]
        c["trap"] = "n/a" if tr is None else ("pass-through" if tr["touch"] is None else "trap>=1ATR" if tr["react_atr"] >= 1.0
                                               else "weak<1ATR")
        c["force"] = "forceful>=2ATR" if a["force"] >= 2.0 else "normal"
        c["pause"] = "pause<=1.5ATR" if a["pause"] <= 1.5 else "no pause"
        c["timed"] = "timed" if a["timed"] else "untimed"
        c["onway_major<=1ATR"] = "yes" if (a["onway_major"] is not None and a["onway_major"] <= 1.0) else "no"
        c["es_cls"] = a["es_cls"]
        c["es_shift"] = {None: "unknown", 1: "ES shifted", 0: "ES not shifted"}[a["es_shift"]]
        return c
    for sp in ("H1", "H2", "2021-25"):
        a0, z0 = SPAN[sp]
        tab = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0, 0.0]))
        for r in R:
            if not (a0 <= r["day"] <= z0):
                continue
            for f, v in cls_of(A[r["key"]]).items():
                c = tab[f][v]
                c[0] += 1
                if r["u"] is not None:
                    c[1] += 1; c[2] += r["u"]["r1"]
        out[sp] = {f: {v: {"cands": c[0], "filled": c[1], "sum_r": round(c[2], 2), "r_per_cand": round(c[2] / c[0], 3)}
                       for v, c in sorted(d.items())} for f, d in tab.items()}
    # selector agreement on 2026 candidates
    k26 = [r["key"] for r in R if r["day"] >= "2026"]
    agree = {}
    for i, s1 in enumerate(SEL):
        for s2 in SEL[i + 1:]:
            same = sum(1 for k in k26 if A[k]["bd"][s1] == A[k]["bd"][s2])
            agree[f"{s1}~{s2}"] = round(100 * same / len(k26), 1)
    out["agreement_2026"] = agree
    json.dump(out, open(os.path.join(OUTD, "adv_cont_classes.json"), "w"), indent=1)
    return out


SAVES = collections.OrderedDict()      # filled after the grid: name -> (id, status)


def save(names, statuses=None):
    res = json.load(open(OUT))
    V = variants()
    base_o = res["base"]["o"]
    for nm in names:
        spec = V[nm] if nm != "base" else {}
        o, U, rows = run_spec(spec)
        Tr = OBT.tw_score(U, spans=("2026",))[1] + OBT.tw_score(U, spans=("2021-25",))[1]
        Tr = [{k: v for k, v in t.items()} for t in Tr]
        Sc = rl.score(Tr, SESS)
        rid = "lit_adv_" + ("base" if nm == "base" else OBT._slug(nm.replace("ch2 ", "").replace("ch3 ", "").replace("ch4 ", "")))
        st = (statuses or {}).get(nm, "rejected" if nm != "base" else "info")
        h = lambda s: (f"n={o[s]['n']} {o[s]['tpw']}/wk win {o[s]['win']}% PF {o[s]['pf']} net {o[s]['net']:+,} (${o[s]['per_month']:,}/mo) "
                       f"DD {o[s]['dd']:,}; eval 2wk {o[s]['p10']}/{o[s]['f10']}; LIT-rule size {o[s]['lit_net']:+,}; unit R per original "
                       f"candidate {o[s]['cand_r']:+} over {o[s]['n_cand']}")
        ver = (f"{res.get(nm, {}).get('verdict', 'base')}. TWO_WEEK MODE (live sizing, fresh eval each session, $ from back-to-back "
               f"evals reset at 10 sessions): H1 (pick) {h('H1')}; H2 (check) {h('H2')}; 2021-25 reference {h('2021-25')}. "
               f"Base H1 2wk {base_o['H1']['p10']}/{base_o['H1']['f10']} net {base_o['H1']['net']:+,}; H2 2wk "
               f"{base_o['H2']['p10']}/{base_o['H2']['f10']} net {base_o['H2']['net']:+,}.")
        rl.save(rid, "LIT advanced report ch2-4: " + nm, "other",
                "Owner's LIT Advanced Decisions Report (2026-10-18), chapters 2-4 + experiment 4 of ch13: internal sweep vs "
                "thesis boundary (fade vs continuation), zone eligibility and session carryover vs reset, weak reaction vs "
                "completed trap, timed forceful sweeps, ES on the same event.",
                params={**S.LIVE, "rule": nm}, sizing={"two_week": OBT.TWC}, trades=Tr, scored=Sc, status=st, verdict=ver,
                notes="tools/lit_adv_cont.py (wraps tools/lit_select.py, tools/lit_ob.py scoring, engine/lit.py; none edited). "
                      "Annotations causal at the trigger bar (lookahead test). Trades = two_week back-to-back eval path.",
                writeup="lit-adv-continuation", tags=["lit", "lit_adv"])
        print("saved", rid)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "grid"
    if cmd == "check":
        print("OK" if check() else "FAIL")
    elif cmd == "annotate":
        annotate(force=True)
    elif cmd == "grid":
        grid(sys.argv[2] if len(sys.argv) > 2 else None)
    elif cmd == "ledger":
        ledger()
    elif cmd == "describe":
        print(json.dumps(describe(), indent=1)[:6000])
    else:
        raise SystemExit(f"unknown command {cmd}")
