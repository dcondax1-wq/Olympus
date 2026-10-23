"""LIT Advanced Knowledge Supplement tests (owner 2026-10-23): the testable ideas of the supplement on the live LIT.

Every idea is a pre-declared rule (2-3 variants each, fixed before looking at results) applied to the live LIT
(live_model.json "lit" = run lit_live) through engine/lit.py run_x, the code the live loop runs. engine/lit.py is not edited:
  skip     the setup is removed before the executor (engine option skip_keys), so the day stays free for a later setup
  half     the trade is taken at half size (lit.scale_trade on the LIT size rule; unit multiplier m = 0.5 on the eval path)
  cands    the candidate list itself changes (re-armed deeper sweep, equality policy, relocated CISD threshold)
Judged the LIT way: pick on 2026 H1 (Jan-Jun), check on 2026 H2 (Jul-Oct 16), 2021-25 a reference line (5m only there).
Candidate = H1 $ better AND H2 $ not worse AND 2026 trades/week >= 2. Every winner gets a placebo (the same number of random
skips / half sizes, 200 draws) and a paired day bootstrap.

Look-ahead: every feature reads bars <= the setup's trigger bar i only (known when the limit is placed). `lookahead` checks it:
the bars after i are overwritten with noise and every feature must come out the same.

  python -X utf8 tools/lit_supplement.py run         # every variant -> research/lit/supplement.json (~10 min)
  python -X utf8 tools/lit_supplement.py placebo     # placebo for the winners of `run`
  python -X utf8 tools/lit_supplement.py lookahead   # no-look-ahead check of the features
  python -X utf8 tools/lit_supplement.py save        # rl.save runs lit_sup_*
Paper only. Edits no engine file and no live_model*.json.
"""
from __future__ import annotations

import bisect
import collections
import copy
import json
import os
import pickle
import random
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from tools import lit_final as F  # noqa: E402
from tools import lit_ablation as AB  # noqa: E402  (lit_view, boot; imports lit_big_ideas = the m-aware eval executor)
from tools import lit_adopt_combo as AC  # noqa: E402
from tools import lit_big_ideas as BI  # noqa: E402
from tools import lit_adv_manage as A  # noqa: E402

OUT = os.path.join(ROOT, "research", "lit", "supplement.json")
LIVE = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]
P_LIVE = {**lit.DEFAULTS, **LIVE}
TICK = lit.TICK
CFG0 = copy.deepcopy(A.CFG)
Q = ("Owner 2026-10-23: which testable ideas of the 'LIT Advanced Knowledge Supplement' (structure states, trap identity, "
     "IDM vocabulary, path history) make the live LIT more money? Picked on 2026 H1, checked on 2026 H2.")
TIER = {"pm": 4, "pw": 3, "pd": 2, "asia": 1, "london": 1, "ny": 1, "pre": 1, "x_ny": 1, "gap": 1, "buildup": 0}

_S = {}


def base():
    if "M" not in _S:
        M, C = F.market(LIVE["ref"], LIVE.get("extra_boxes") or [])
        _S.update(M=M, C=C, B1=F.bars(M, "1m"), B5=F.bars(M, "5m"))
    return _S["M"], _S["C"], _S["B1"], _S["B5"]


def key(z):
    return (z["day"], int(z["i"]), int(z["dir"]))


# ================================================================================================ features (bars <= i)
def dspace(M, d):
    return (M.h, M.l, M.c, M.o) if d == 1 else (-M.l, -M.h, -M.c, -M.o)


def ep_of(z):
    return min(float(z["ref_d"]), z["trig_c"])


def f_target_visited(M, z):
    """S07 path history: the trade's own objective (18:00 open +/- 1 VIX one-day move, direction space) already traded today
    (18:00 -> trigger bar close) before this setup."""
    x = M.ctx[z["k"]]
    vm = x.get("vix_move")
    if not vm:
        return False
    hi, _, _, _ = dspace(M, z["dir"])
    p = x["open18"] * z["dir"] + P_LIVE["vix_k"] * vm
    return bool(hi[x["s"]:z["i"] + 1].max() >= p)


def f_opp_objective(M, z):
    """S02 completed cycle: the OTHER side's objective (18:00 open -/+ 1 VIX move) already traded today before the trigger
    close = the day completed a cycle against this setup; this setup is countertrend to it."""
    x = M.ctx[z["k"]]
    vm = x.get("vix_move")
    if not vm:
        return False
    _, lo, _, _ = dspace(M, z["dir"])
    p = x["open18"] * z["dir"] - P_LIVE["vix_k"] * vm
    return bool(lo[x["s"]:z["i"] + 1].min() <= p)


def f_opp_objective_old(M, z):
    """S02 strict: the opposite objective hit before the trigger AND the swept level existed before that hit (the setup
    defends an old origin that the completed cycle turned into a target)."""
    x = M.ctx[z["k"]]
    vm = x.get("vix_move")
    if not vm:
        return False
    _, lo, _, _ = dspace(M, z["dir"])
    p = x["open18"] * z["dir"] - P_LIVE["vix_k"] * vm
    seg = lo[x["s"]:z["i"] + 1] <= p
    if not seg.any():
        return False
    hit = x["s"] + int(np.argmax(seg))
    ki = [ki for side, px, ki, nm, cls in M.levels(z["k"]) if nm in z["swept"] and (side == "low") == (z["dir"] == 1)]
    return bool(ki) and min(ki) < hit


def idms(M, z):
    """The inducements the live rule counts (idm_a: <= 1 ATR above the swept level, <= 36 bars before the sweep), with their
    geometry: m (swing bar), px (direction space), take bar tk, inside (formed after the leg's swing high = inside the leg),
    front (below the limit price = between the entry zone and the swept liquidity), wick (take bar closed back at / above it),
    reclaim (a close back at / above it within the take bar + 2 bars, up to the trigger)."""
    dm, age, _ = P_LIVE["idm_a"]
    hi, lo, c, _ = dspace(M, z["dir"])
    s = M.ctx[z["k"]]["s"]
    ee, sb, i = z["ext_i"], z["sweep_i"], z["i"]
    leg_top = int(ee - np.argmax(hi[max(ee - 36, s - 600):ee + 1][::-1])) if ee > s else ee
    ep = ep_of(z)
    out = []
    for dd, aa in z["idm_a"]:
        if dd > dm or aa > age:
            continue
        m = sb - aa
        px = float(lo[m])
        sg = lo[m + 1:ee + 1] < px
        tk = m + 1 + int(np.argmax(sg))
        rc = c[tk:min(tk + 3, i + 1)]
        out.append({"m": m, "px": px, "tk": tk, "inside": m >= leg_top, "front": px < ep, "wick": bool(c[tk] >= px),
                    "reclaim": bool((rc >= px).any())})
    return out


def f_bigger_pool(M, z, k_atr):
    """S01 / S11 required raid: an untaken same-side level of a HIGHER tier (pm > pw > pd > session box / gap > build-up) than
    every swept level sits within k_atr ATR beyond the sweep extreme (the raid stopped short of the bigger pool)."""
    d = z["dir"]
    _, lo, _, _ = dspace(M, d)
    x = M.ctx[z["k"]]
    s, i = x["s"], z["i"]
    t_sw = max(TIER.get(c, 0) for c in z["swept_cls"])
    for side, px, ki, nm, cls in M.levels(z["k"]):
        if (side == "low") != (d == 1) or ki > i or TIER.get(cls, 0) <= t_sw:
            continue
        p = px * d
        if p >= z["ext_d"] or z["ext_d"] - p > k_atr * z["atr_ext"]:
            continue
        a = max(ki + 1, s - 600)
        if a > i or lo[a:i + 1].min() > p:
            return True
    return False


def wick_thr(M, z):
    """S26: highest wick (direction space) of the bars between the extreme and the trigger that poked above the CISD level
    without closing above it; None when no bar did."""
    hi, _, _, _ = dspace(M, z["dir"])
    seg = hi[z["ext_i"] + 1:z["i"]]
    seg = seg[seg > z["ref_d"]]
    return float(seg.max()) if len(seg) else None


FEATS = {
    "target_visited": f_target_visited, "opp_objective": f_opp_objective, "opp_objective_old": f_opp_objective_old,
    "idm_inside": lambda M, z: any(q["inside"] for q in idms(M, z)),
    "idm_inside_front": lambda M, z: any(q["inside"] and q["front"] for q in idms(M, z)),
    "idm_wick": lambda M, z: any(q["wick"] for q in idms(M, z)),
    "idm_reclaim": lambda M, z: any(q["reclaim"] for q in idms(M, z)),
    "idm_body": lambda M, z: any(not q["wick"] for q in idms(M, z)),
    "pool05": lambda M, z: f_bigger_pool(M, z, 0.5), "pool10": lambda M, z: f_bigger_pool(M, z, 1.0),
    "wick_thr": wick_thr,
}


# ================================================================================================ candidate-list variants
def rearm(M, C, inherit_new=True, win=36):
    """S05 second shift after a failed first: a deeper sweep (new extreme beyond a first setup's extreme, within `win` bars of
    the first trigger, same day and side) inherits the first setup's trap (its inducements and swept levels), so it can
    trade although on its own it has no inducement / its first breach is out of the 24-bar sweep window. inherit_new also
    adds the deeper setups that only a 48-bar sweep window finds. Still 1 trade a day (a filled first setup ends the day)."""
    names = None
    C2 = C
    if inherit_new:
        p = os.path.join(F.CACHE, f"litsup_c48_{rl_key()}.pkl")
        if os.path.exists(p):
            C2 = pickle.load(open(p, "rb"))
        else:
            C2 = lit.candidates(M, ref=LIVE["ref"], sweep_win=48)
            pickle.dump(C2, open(p, "wb"))
    have = {key(z) for z in C}
    firsts = collections.defaultdict(list)
    for z in C:
        if lit.setup_ok(z, P_LIVE, names) and not lit.monday_block(M, z):
            firsts[(z["day"], z["dir"])].append(z)
    out, n_rearm = [], 0
    by_k = {key(z): z for z in C}
    for z in C2:
        k = key(z)
        if k not in have and not inherit_new:
            continue
        z0 = by_k.get(k, z)
        f1 = [a for a in firsts.get((z["day"], z["dir"]), []) if a["i"] < z["ext_i"] <= a["i"] + win and z["ext_d"] < a["ext_d"]]
        if not f1:
            if k in have:
                out.append(z0)
            continue
        a = f1[-1]
        zz = dict(z0)
        sw = dict(a["sw"])
        for nm, px in z0["sw"].items():
            sw[nm] = max(px, sw.get(nm, -1e18))
        zz.update(idm_a=list(a["idm_a"]) + list(z0["idm_a"]), sw=sw, swept=sorted(set(a["swept"]) | set(z0["swept"])),
                  swept_cls=sorted(set(a["swept_cls"]) | set(z0["swept_cls"])),
                  depth_atr=round((max(sw.values()) - zz["ext_d"]) / max(zz["atr_ext"], 1e-9), 3), rearm=key(a))
        if not lit.setup_ok(z0, P_LIVE, names) or k not in have:
            n_rearm += 1
        out.append(zz)
    out.sort(key=lambda z: (z["entry_t"], -z["dir"]))
    return out, n_rearm


def relocate(M, C, delay=6):
    """S26 body-break threshold relocation: when a bar between the extreme and the trigger poked above the CISD level with a
    wick only, the threshold moves to that wick. The trigger must close above it; if it does not, the setup triggers on the
    first later close above the wick (within `delay` bars, the extreme intact, before 15:55), else it is gone."""
    o, h, l, c, mod, at = M.o, M.h, M.l, M.c, M.mod, M.atr
    out, moved, dropped = [], 0, 0
    for z in C:
        thr = wick_thr(M, z)
        if thr is None or z["trig_c"] > thr:
            out.append(z)
            continue
        if delay <= 0:
            dropped += 1
            continue
        hi, lo, cd, od = dspace(M, z["dir"])
        x = M.ctx[z["k"]]
        e = x["e"]
        j = None
        for q in range(z["i"] + 1, min(z["i"] + 1 + delay, e - 1)):
            if lo[q] <= z["ext_d"]:
                break
            if cd[q] > thr:
                j = q
                break
        if j is None or j + 1 >= e or lit._late(mod[j + 1], 955, False):
            dropped += 1
            continue
        ee = z["ext_i"]
        body = (cd[ee:j + 1] - od[ee:j + 1]) / np.maximum(at[ee:j + 1], 1e-9)
        zz = dict(z)
        zz.update(i=int(j), entry_i=int(j + 1), entry_t=int(M.t[j + 1]), entry_d=float(od[j + 1]) + lit.SLIP, trig_c=float(cd[j]),
                  mod=int(mod[j + 1]), disp=round(float(body[1:].max()) if len(body) > 1 else 0.0, 3), bars=int(j - ee),
                  atr=round(float(at[j]), 2), moved_from=int(z["i"]))
        moved += 1
        out.append(zz)
    out.sort(key=lambda z: (z["entry_t"], -z["dir"]))
    return out, {"moved": moved, "dropped": dropped}


class MarketEq(lit.Market):
    """Equality policy (S13 / S22): every liquidity level is moved `tol` points toward price (direction space), so a low
    within tol of a low-side level counts as touched / swept (tol > 0 = equal counts; tol < 0 = a sweep must go more than
    |tol| beyond). Targets (other side) the same way."""
    tol = 0.0

    def levels(self, k):
        L = super().levels(k)
        return [(sd, px + self.tol if sd == "low" else px - self.tol, ki, nm, cls) for sd, px, ki, nm, cls in L]


def rl_key():
    from tools import runlib as rl
    return rl._data_key().replace(":", "_")


def eq_market(tol):
    k = ("eq", tol)
    if k not in _S:
        cls = type(f"MarketEq_{str(tol).replace('-', 'm').replace('.', '_')}", (MarketEq,), {"tol": tol})
        M = cls(extra_boxes=list(LIVE.get("extra_boxes") or []))
        p = os.path.join(F.CACHE, f"litsup_eq{tol}_{rl_key()}.pkl")
        if os.path.exists(p):
            C = pickle.load(open(p, "rb"))
        else:
            C = lit.candidates(M, ref=LIVE["ref"])
            pickle.dump(C, open(p, "wb"))
        _S[k] = (M, C, lit.bars_1m(M), lit.bars_5m(M))
    return _S[k]


# ================================================================================================ variants
def V():
    """name -> (idea, kind, spec). kind skip / half: spec = predicate(M, z) -> True = skip / half. kind cands: spec = fn()
    -> (M, C, B1, B5, info)."""
    S = collections.OrderedDict()
    S["1a target already visited today: skip"] = ("S07 path history", "skip", f_target_visited)
    S["1b target already visited today: half size"] = ("S07 path history", "half", f_target_visited)
    S["2a inducement must be inside the leg (after the leg's swing high): skip"] = (
        "S24/S25 trap geometry", "skip", lambda M, z: not FEATS["idm_inside"](M, z))
    S["2b inducement inside the leg AND in front of the entry: skip"] = (
        "S24/S25 trap geometry", "skip", lambda M, z: not FEATS["idm_inside_front"](M, z))
    S["2c inducement inside the leg AND in front of the entry: half size"] = (
        "S24/S25 trap geometry", "half", lambda M, z: not FEATS["idm_inside_front"](M, z))
    S["3a inducement taken by a wick (take bar closes back): skip"] = (
        "S15/S16 IDM taken vs reclaimed", "skip", lambda M, z: not FEATS["idm_wick"](M, z))
    S["3b inducement reclaimed within 2 bars of the take: skip"] = (
        "S15/S16 IDM taken vs reclaimed", "skip", lambda M, z: not FEATS["idm_reclaim"](M, z))
    S["3c inducement taken by a body close: skip"] = (
        "S15/S16 IDM taken vs reclaimed", "skip", lambda M, z: not FEATS["idm_body"](M, z))
    S["4a higher-tier pool untaken within 0.5 ATR beyond the extreme: skip"] = (
        "S01/S11 required raid", "skip", FEATS["pool05"])
    S["4b higher-tier pool untaken within 1.0 ATR beyond the extreme: skip"] = (
        "S01/S11 required raid", "skip", FEATS["pool10"])
    S["4c higher-tier pool untaken within 1.0 ATR beyond the extreme: half size"] = (
        "S01/S11 required raid", "half", FEATS["pool10"])

    def c_rearm(new):
        def f():
            M, C, B1, B5 = base()
            C2, n = rearm(M, C, inherit_new=new)
            return M, C2, B1, B5, {"rearmed": n}
        return f
    S["5a second shift: deeper sweep inherits the first trap (24-bar window)"] = ("S05 second shift", "cands", c_rearm(False))
    S["5b second shift: deeper sweep inherits the first trap (+48-bar window setups)"] = ("S05 second shift", "cands", c_rearm(True))
    S["6a opposite objective hit today (completed cycle): skip countertrend"] = ("S02 completed cycle", "skip", f_opp_objective)
    S["6b opposite objective hit today: half size countertrend"] = ("S02 completed cycle", "half", f_opp_objective)
    S["6c opposite objective hit and the swept level is older: skip"] = ("S02 completed cycle", "skip", f_opp_objective_old)

    def c_eq(tol):
        def f():
            M, C, B1, B5 = eq_market(tol)
            return M, C, B1, B5, {"tol": tol}
        return f
    S["7a equal within 1 tick counts as swept"] = ("S13/S22 equality policy", "cands", c_eq(0.25))
    S["7b equal within 2 ticks counts as swept"] = ("S13/S22 equality policy", "cands", c_eq(0.5))
    S["7c a sweep must go more than 2 ticks beyond"] = ("S13/S22 equality policy", "cands", c_eq(-0.5))

    def c_rel(delay):
        def f():
            M, C, B1, B5 = base()
            C2, info = relocate(M, C, delay)
            return M, C2, B1, B5, info
        return f
    S["8a CISD threshold moves to a wick probe: skip if the trigger is not above it"] = ("S26 threshold relocation", "cands", c_rel(0))
    S["8b CISD threshold moves to a wick probe: trigger on the first close above it (6 bars)"] = (
        "S26 threshold relocation", "cands", c_rel(6))
    return S


# ================================================================================================ running + scoring
def run_kind(kind, spec, rng_keys=None):
    """Trades + the per-trade eval multiplier map {(day, entry_t): m}."""
    M, C, B1, B5 = base()
    info = {}
    mm = {}
    if kind == "skip":
        ks = [list(key(z)) for z in C if spec(M, z)] if rng_keys is None else [list(k) for k in rng_keys]
        T = lit.run_x(M, C, {**P_LIVE, "skip_keys": ks}, F.SESS, B1=B1, B5=B5)
        info["flagged_cands"] = len(ks)
    elif kind == "half":
        T0 = lit.run_x(M, C, P_LIVE, F.SESS, B1=B1, B5=B5)
        byk = {key(z): z for z in C}
        T = []
        for t in T0:
            hit = (t["day"], int(t["i"]), int(t["dir"])) in rng_keys if rng_keys is not None else spec(M, byk[(t["day"], int(t["i"]), int(t["dir"]))])
            if hit:
                t = lit.scale_trade(t, 0.5)
                mm[(t["day"], int(t["entry_t"]))] = 0.5
            T.append(t)
        info["halved"] = len(mm)
        info["halved_2026"] = sum(1 for k in mm if k[0] >= "2026")
    else:
        M2, C2, B1b, B5b, info = spec()
        T = lit.run_x(M2, C2, P_LIVE, F.SESS, B1=B1b, B5=B5b)
    return T, mm, info


def eval_view(T, mm):
    U = AC.units(T)
    for u in U:
        m = mm.get((u["day"], u["entry_t"]))
        if m is not None:
            u["m"] = m
    A.CFG = copy.deepcopy(CFG0)
    try:
        return BI.short(BI.score(U))
    finally:
        A.CFG = copy.deepcopy(CFG0)


def score_all(T, mm, Tb=None):
    o = {"lit": AB.lit_view(T), "eval": eval_view(T, mm)}
    if Tb is not None:
        o["boot_h1"] = AB.boot(T, Tb, AB.H1D)
        o["boot_h2"] = AB.boot(T, Tb, AB.H2D)
        kb = {(t["day"], t["entry_t"]) for t in Tb if t["day"] >= "2026"}
        kv = {(t["day"], t["entry_t"]) for t in T if t["day"] >= "2026"}
        o["changed_2026"] = {"dropped": len(kb - kv), "new": len(kv - kb), "resized": sum(1 for k in mm if k[0] >= "2026")}
    return o


def verdict(o, b):
    L, Lb = o["lit"], b["lit"]
    dH1 = L["H1"]["net"] - Lb["H1"]["net"]
    dH2 = L["H2"]["net"] - Lb["H2"]["net"]
    cand = dH1 > 0 and dH2 >= 0 and L["2026"]["tpw"] >= 2.0
    return {"dH1": dH1, "dH2": dH2, "d2021_25": L["2021-25"]["net"] - Lb["2021-25"]["net"],
            "dE_H1": o["eval"]["H1"]["net"] - b["eval"]["H1"]["net"], "dE_H2": o["eval"]["H2"]["net"] - b["eval"]["H2"]["net"],
            "candidate": cand}


def line(nm, o):
    L, E = o["lit"], o["eval"]
    f = lambda s: f"{L[s]['tpw']}/wk PF {L[s]['pf']} {L[s]['net']:+,}"  # noqa
    g = lambda s: f"{E[s]['net']:+,} 2w {E[s]['p10']}/{E[s]['f10']}"  # noqa
    v = o.get("v", {})
    return (f"{nm[:62]:62s} dH1 {v.get('dH1', 0):+7,} dH2 {v.get('dH2', 0):+7,} cand={v.get('candidate')} | H1[{f('H1')}] "
            f"H2[{f('H2')}] 21-25[{f('2021-25')}] | eval H1[{g('H1')}] H2[{g('H2')}]")


def main():
    M, C, B1, B5 = base()
    Tb = lit.run_x(M, C, P_LIVE, F.SESS, B1=B1, B5=B5)
    b = score_all(Tb, {})
    n26 = sum(1 for t in Tb if t["day"] >= "2026")
    print(f"base lit_live: 2026 {n26} trades {round(sum(t['pnl'] for t in Tb if t['day'] >= '2026')):+,}", flush=True)
    res = {"_base": b, "_n_tests": 0, "variants": {}}
    for nm, (idea, kind, spec) in V().items():
        T, mm, info = run_kind(kind, spec)
        o = score_all(T, mm, Tb)
        o.update(idea=idea, kind=kind, info=info, v=verdict(o, b))
        res["variants"][nm] = o
        res["_n_tests"] += 1
        print(line(nm, o), info, o["changed_2026"], flush=True)
        json.dump(res, open(OUT, "w"), indent=1, default=str)
    return res


# ================================================================================================ placebo
def placebo(n=200, seed=3):
    """For every candidate of `run`: the same number of random skips (of the base's 2026 + 2021-25 trades' setups) or random
    half sizes, n draws; where the variant's H1 / H2 $ gains sit in the placebo distribution."""
    res = json.load(open(OUT))
    M, C, B1, B5 = base()
    Tb = lit.run_x(M, C, P_LIVE, F.SESS, B1=B1, B5=B5)
    b = res["_base"]["lit"]
    V_ = V()
    rng = random.Random(seed)
    for nm, o in res["variants"].items():
        if not o["v"]["candidate"]:
            continue
        idea, kind, spec = V_[nm]
        if kind == "cands":
            # candidate-list change: the placebo drops the same number of the base's trades per span at random (the
            # variant dropped these trades and replaced some by other setups; the placebo lets the engine refill the day)
            Tv, _, _ = run_kind(kind, spec)
            kv = {(t["day"], t["entry_t"]) for t in Tv}
            flagged = [t for t in Tb if (t["day"], t["entry_t"]) not in kv]
            kind = "skip"
        else:
            byk = {key(z): z for z in C}
            flagged = [t for t in Tb if spec(M, byk[(t["day"], int(t["i"]), int(t["dir"]))])]
        n1 = sum(1 for t in flagged if "2026-01-01" <= t["day"] <= "2026-06-30")
        n2 = sum(1 for t in flagged if t["day"] >= "2026-07-01")
        n0 = sum(1 for t in flagged if t["day"] < "2026")
        pools = {"H1": [t for t in Tb if "2026-01-01" <= t["day"] <= "2026-06-30"], "H2": [t for t in Tb if t["day"] >= "2026-07-01"],
                 "old": [t for t in Tb if t["day"] < "2026"]}
        d1, d2 = [], []
        for _ in range(n):
            pick = rng.sample(pools["H1"], n1) + rng.sample(pools["H2"], n2) + rng.sample(pools["old"], min(n0, len(pools["old"])))
            ks = {(t["day"], int(t["i"]), int(t["dir"])) for t in pick}
            T, _, _ = run_kind(kind, None, rng_keys=ks)
            s = AB.fast(T)
            d1.append(s["H1"] - b["H1"]["net"]); d2.append(s["H2"] - b["H2"]["net"])
        d1, d2 = np.array(d1), np.array(d2)
        o["placebo"] = {"n": n, "trades_flagged": {"H1": n1, "H2": n2, "2021-25": n0},
                        "H1_mean": round(float(d1.mean())), "H2_mean": round(float(d2.mean())),
                        "H1_p_ge": round(float((d1 >= o["v"]["dH1"]).mean()), 3), "H2_p_ge": round(float((d2 >= o["v"]["dH2"]).mean()), 3),
                        "both_p_ge": round(float(((d1 >= o["v"]["dH1"]) & (d2 >= o["v"]["dH2"])).mean()), 3)}
        print(nm, o["placebo"], flush=True)
        json.dump(res, open(OUT, "w"), indent=1, default=str)


# ================================================================================================ look-ahead check
def lookahead(n=400, seed=1):
    """Overwrite every bar after the trigger bar i with noise (a copy of the market) and recompute each feature: identical =
    the feature reads only bars known when the limit is placed. Also the re-arm / relocation fields: re-arm reads only the
    first setup (trigger < the deeper extreme) and the deeper setup's own detector; relocation is checked bar by bar."""
    M, C, B1, B5 = base()
    rng = np.random.default_rng(seed)
    S = rng.choice(len(C), size=min(n, len(C)), replace=False)
    bad = collections.Counter()
    arrs = ("o", "h", "l", "c")
    keep = {a: getattr(M, a).copy() for a in arrs}
    try:
        for q in S:
            z = C[int(q)]
            ref = {nm: fn(M, z) for nm, fn in FEATS.items()}
            i = z["i"]
            for a in arrs:
                v = keep[a].copy()
                v[i + 1:] = v[i + 1:] + rng.normal(0, 50, size=len(v) - i - 1)
                setattr(M, a, v)
            for nm, fn in FEATS.items():
                if fn(M, z) != ref[nm]:
                    bad[nm] += 1
            for a in arrs:
                setattr(M, a, keep[a])
    finally:
        for a in arrs:
            setattr(M, a, keep[a])
    print(f"look-ahead check on {len(S)} setups: features changed by future bars: {dict(bad) or 'none'}", flush=True)
    res = json.load(open(OUT)) if os.path.exists(OUT) else {}
    res["_lookahead"] = {"setups": len(S), "changed": dict(bad)}
    json.dump(res, open(OUT, "w"), indent=1, default=str)
    return not bad


# ================================================================================================ store runs
def rid_of(nm):
    rid = "lit_sup_" + "".join(ch if ch.isalnum() else "_" for ch in nm.lower())[:44].strip("_")
    while "__" in rid:
        rid = rid.replace("__", "_")
    return rid


def _h(s):
    return f"n={s['n']} {s['tpw']}/wk win {s['win']}% PF {s['pf']} net {s['net']:+,} (${s['per_month']:,}/mo) DD {s['dd']:,}"


def _he(s):
    return f"PF {s['pf']} net {s['net']:+,} (${s['per_month']:,}/mo) DD {s['dd']:,}; 2-week pass/fail {s['p10']}/{s['f10']}"


def save():
    from tools import runlib as rl
    res = json.load(open(OUT))
    idx = rl.index
    rl.index = lambda: None
    try:
        for nm, (idea, kind, spec) in V().items():
            o = res["variants"].get(nm)
            if not o:
                continue
            T, mm, info = run_kind(kind, spec)
            Ts = [{k: v for k, v in t.items() if not k.startswith("_") and k not in ("size_why", "size_mult")} for t in T]
            l, e, v = o["lit"], o["eval"], o["v"]
            st = "adopt-candidate" if v["candidate"] else "rejected"
            pl = o.get("placebo")
            rl.save(rid_of(nm), "LIT live + supplement rule: " + nm, "other", Q,
                    params={**P_LIVE, "supplement_rule": nm, "idea": idea, "kind": kind, "info": info}, trades=Ts,
                    scored=rl.score(Ts, F.SESS), status=st,
                    verdict=(f"{'CANDIDATE' if v['candidate'] else 'rejected'}: dH1 {v['dH1']:+,} dH2 {v['dH2']:+,} (2021-25 "
                             f"{v['d2021_25']:+,}). LIT size rule: 2026 H1 (pick) {_h(l['H1'])}; H2 (check) {_h(l['H2'])}; "
                             f"2026 {_h(l['2026'])}; 2021-25 reference {_h(l['2021-25'])}. Eval path (two_week): H1 {_he(e['H1'])}; "
                             f"H2 {_he(e['H2'])}." + (f" Placebo: {json.dumps(pl)}" if pl else "")),
                    notes="tools/lit_supplement.py: engine/lit.py run_x on live_model.json lit (skip_keys / scale_trade / "
                          "changed candidate list); eval path = lit_big_ideas executor with unit m.",
                    writeup="lit-supplement", tags=["lit", "lit_supplement"])
            print("saved", rid_of(nm), flush=True)
    finally:
        rl.index = idx
    rl.index()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    {"run": main, "placebo": placebo, "lookahead": lookahead, "save": save}[cmd]()
