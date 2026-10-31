"""ATLAS funded day-count rule (2026-10-31, research/writeups/atlas-funded-one-a-day-2026-10-31.md).

Question: does the FUNDED ATLAS 25K pay the owner more if it takes at most ONE trade a day (the day's first ATLAS signal)
instead of two? The eval is unchanged (today's ATLAS), so only the slot $ (eval -> funded -> MFFU payouts -> a new $63 eval,
tools/atx_edge.slot) can move. Trade-count rules were tested on the EVAL path before (atlas-confluences.md "Trades a day":
max 1 / max 3 / 2nd only after a win or a loss, 0 kept); never on the funded account's payouts.

Pick on 2026 H1 only (max 1 vs max 3 vs today's max 2), frozen, checked on 2026 H2 and 2021-25. Controls: keep ONE RANDOM
signal of the day instead of the first (4 seeds), so "1 a day" has to beat "any 1 a day".

    python -X utf8 tools/atx_funded_day.py run [n]     # slot $ for every variant -> research/second/atx_funded_day.json
    python -X utf8 tools/atx_funded_day.py save        # runs atxd_* in the run library (real-session slot trades)
    python -X utf8 tools/atx_funded_day.py vix         # idea 2: funded-only VIX band per member
    python -X utf8 tools/atx_funded_day.py partial     # idea 3: funded half off at 0.75 / 1 / 1.5R + BE runner (+ control)
    python -X utf8 tools/atx_funded_day.py save_partial  # runs atxd_partial_*
    python -X utf8 tools/atx_funded_day.py reentry     # idea 4: funded re-entry after a stop-out (+ control, run atxd_reentry_1r)
Paper research only: nothing in engine/, second_model.json or live_model*.json is touched.
"""
from __future__ import annotations

import json
import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import atx_edge as X  # noqa: E402

OUT = os.path.join(X.OUT, "atx_funded_day.json")


def funded_play(max_day=2, pick=None):
    """A funded-stage play_day: at most max_day trades a day; pick="random:<seed>" keeps one random signal of the day."""
    V2, A, M, EAB = X.libs()

    def play(L, day, bal, floor, session, rule, pre=False, _md=2, lost=None, litcfg=None, dll=None, reserve=False, extra=None):
        L = list(L)
        if pick and L:
            seed = int(pick.split(":")[1])
            rng = random.Random(f"{seed}:{day}")
            L = [L[rng.randrange(len(L))]]
        return M.play_day(L, day, bal, floor, session, rule, pre, max_day, lost, litcfg, dll=dll, reserve=reserve, extra=extra)
    return play


VARIANTS = [("today", dict()), ("max1", dict(max_day=1)), ("max3", dict(max_day=3)), ("max4", dict(max_day=4))] + \
           [(f"rand1_s{s}", dict(max_day=1, pick=f"random:{s}")) for s in (1, 2, 3, 4)]


SEEDS = (23, 5, 11, 41)          # 23 = atx_edge's seed (the pick); the others = path-resampling robustness


def one(name, kw, n, seed=23):
    X.PLAY_FUNDED[0] = funded_play(**kw) if kw else None
    try:
        sl = X.slot(X.today(), n=n, seed=seed)
        sl["2021-25"] = X.slot_ref(sl)
        rs, T = X.real_slot(X.today())
    finally:
        X.PLAY_FUNDED[0] = None
    ft = [t for t in T if t["stage"] == "funded"]
    return {"slot": sl, "real": rs, "funded_trades": stats(ft), "_T": T}


def stats(T):
    """PF, R per $ risked, $ net, max drawdown, trades by span of the funded trades on the real-session path."""
    out = {}
    for s, (a, b) in {"H1": ("2026-01-01", "2026-07-01"), "H2": ("2026-07-01", "2027-01-01"), "2021-25": ("2021-01-01", "2026-01-01")}.items():
        x = [t for t in T if a <= t["day"] < b]
        w = sum(t["pnl"] for t in x if t["pnl"] > 0)
        l = -sum(t["pnl"] for t in x if t["pnl"] < 0)
        ru = sum(t.get("risk_usd") or 0 for t in x)
        eq = pk = dd = 0.0
        for t in sorted(x, key=lambda t: t["entry_t"]):
            eq += t["pnl"]
            pk = max(pk, eq)
            dd = min(dd, eq - pk)
        days = sorted({t["day"] for t in x})
        out[s] = {"n": len(x), "net": round(sum(t["pnl"] for t in x)), "pf": round(w / l, 2) if l else None,
                  "r_per_risk": round(sum(t["pnl"] for t in x) / ru, 3) if ru else None, "dd": round(dd),
                  "days": len(days), "two_trade_days": sum(1 for d in days if sum(1 for t in x if t["day"] == d) >= 2)}
    return out


def cmd_run(n=300):
    res = {}
    for name, kw in VARIANTS:
        t0 = time.time()
        o = one(name, kw, n)
        o.pop("_T")
        if not name.startswith("rand"):
            o["seeds"] = {}
            for sd in SEEDS[1:]:
                q = one(name, kw, n, seed=sd)
                o["seeds"][sd] = {s: q["slot"][s]["pm"] for s in ("H1", "H2", "2021-25")}
        res[name] = o
        print(f"{name:10s} " + " | ".join(f"{s} slot ${o['slot'][s]['pm']:+,}/mo lose {o['slot'][s]['lose']}%" for s in ("H1", "H2", "2021-25"))
              + (f"  seeds {o['seeds']}" if o.get("seeds") else "") + f"  ({time.time() - t0:.0f}s)", flush=True)
        json.dump({"n": n, "res": res}, open(OUT, "w", encoding="utf-8"), indent=1)
    return res


def cmd_save():
    from tools import runlib as rl
    V2, A, M, EAB = X.libs()
    sess = sorted(set(M.units()["sessions"]))
    R = json.load(open(OUT, encoding="utf-8"))["res"]
    for name, title, st in (("max1", "ATLAS funded 25K: 1 trade a day (eval unchanged)", "rejected"),
                            ("max3", "ATLAS funded 25K: up to 3 trades a day (the H1 pick; eval unchanged)", "rejected"),
                            ("today", "ATLAS slot today (2 a day funded), reference for atxd_*", "info")):
        kw = dict(VARIANTS)[name]
        o = one(name, kw, 20)
        T = X._runlib_trades(o["_T"])
        r = R[name]
        vt = "; ".join(f"{s}: slot ${r['slot'][s]['pm']:,}/mo (today ${R['today']['slot'][s]['pm']:,}), lose {r['slot'][s]['lose']}%, "
                       f"funded PF {r['funded_trades'][s]['pf']}, R/$ {r['funded_trades'][s]['r_per_risk']}" for s in ("H1", "H2", "2021-25"))
        rl.save(f"atxd_{name}", title, "risk", "ATLAS 2026-10-31: does the funded 25K pay more with at most one trade a day?",
                params={"funded_max_day": kw.get("max_day", 2), "eval": "today"},
                sizing={"eval": "engine/account_b.qty need", "funded": "engine/sizing.funded_qty 25K preset (atx_edge.funded_q)"},
                trades=T, scored=rl.score(T, sess), status=st, verdict=vt,
                notes="tools/atx_funded_day.py (slot = block-bootstrap paths x 126 sessions, $63 evals, 80% payouts; trades = real-session path)",
                writeup="atlas-funded-one-a-day-2026-10-31", tags=["atlas", "account_b", "25k", "funded", "slot", "trades_a_day"])
        print("saved", name, flush=True)


# ============================================================ idea 2: funded-only VIX band per member (eval unchanged)
def vix_prev(day, _c={}):
    """The prior session's CBOE VIX close (known before the open)."""
    import bisect
    if "k" not in _c:
        from tools import scalp_na_lib as N
        N.prev_close("VIX", "2021-01-04")
        _c["k"], _c["v"] = N._M["VIX"]
    k = bisect.bisect_left(_c["k"], day) - 1
    v = float(_c["v"][k]) if k >= 0 else float("nan")
    return v if v == v and v > 0 else None


def vix_cuts():
    """Tercile cut points of the VIX over 2026 H1 sessions (frozen)."""
    import numpy as np
    V2, A, M, EAB = X.libs()
    v = [vix_prev(d) for d in sorted(set(M.units()["sessions"])) if X.H1[0] <= d <= X.H1[1]]
    v = [x for x in v if x]
    return [float(np.percentile(v, 33.33)), float(np.percentile(v, 66.67))]


def band(day, cuts):
    v = vix_prev(day)
    return None if v is None else (0 if v < cuts[0] else 1 if v < cuts[1] else 2)


def vix_buckets(cuts, min_n=5):
    """H1 R per VIX band of each member's ACCOUNT units (today's no-hedge rules): {member: {band: (mean R, n, sum R)}}."""
    import collections
    import numpy as np
    from tools import ab_edge as E
    V2, A, M, EAB = X.libs()
    B = collections.defaultdict(lambda: collections.defaultdict(list))
    for u in A.account_units(X.today()):
        if u["src"] in X.MEM and X.H1[0] <= u["day"] <= X.H1[1]:
            B[u["src"]][band(u["day"], cuts)].append(E._R(u))
    return {m: {b: (float(np.mean(x)), len(x), float(np.sum(x))) for b, x in d.items() if len(x) >= min_n and b is not None} for m, d in B.items()}


def vf_drop(picks, cuts):
    """Funded variant: today's members, each member skips its picked VIX band (picks = {member: band})."""
    import copy
    V2, A, M, EAB = X.libs()
    V = copy.deepcopy(X.today())
    V["drop"] = {m: sorted(int(u["entry_t"]) for u in M.units()[m] if band(u["day"], cuts) == b) for m, b in picks.items()}
    return V


def cmd_vix(n=300, k_ctl=8):
    import numpy as np
    cuts = vix_cuts()
    st = vix_buckets(cuts)
    pick = {m: min((v[2], b) for b, v in d.items() if v[0] < 0)[1] for m, d in st.items() if any(v[0] < 0 for v in d.values())}
    print("cuts", [round(c, 2) for c in cuts], "H1 buckets", {m: {b: (round(v[0], 2), v[1]) for b, v in d.items()} for m, d in st.items()}, "pick", pick, flush=True)
    res = {"cuts": cuts, "buckets": {m: {str(b): v for b, v in d.items()} for m, d in st.items()}, "pick": pick, "rows": {}}

    def run(name, picks, seeds=(23,)):
        o = {}
        for sd in seeds:
            sl = X.slot(X.today(), vf_drop(picks, cuts), n=n, seed=sd)
            sl["2021-25"] = X.slot_ref(sl)
            o[sd] = {s: sl[s]["pm"] for s in ("H1", "H2", "2021-25")}
            o[f"lose_{sd}"] = {s: sl[s]["lose"] for s in ("H1", "H2", "2021-25")}
        res["rows"][name] = o
        print(f"{name:28s} {o[23]}  " + " ".join(f"s{sd} {o[sd]}" for sd in seeds[1:]), flush=True)
        json.dump(res, open(os.path.join(X.OUT, "atx_funded_vix.json"), "w", encoding="utf-8"), indent=1)
        return o

    run("today", {}, SEEDS)
    run("pick: worst H1 VIX band", pick, SEEDS)
    rng = np.random.default_rng(7)
    for i in range(k_ctl):                               # control: a random band of each picked member
        run(f"control {i}", {m: int(rng.integers(0, 3)) for m in pick})
    return res


# ============================================================ idea 3: funded partial at xR + runner (stop to BE), eval unchanged
_PART = {}


def partial_map(lvl):
    """{(src, entry_t): new pts per micro} for half off at lvl x R and the stop to breakeven on the rest (bars from the
    member's own bar set, highs and lows in trade direction; a bar that touches both the stop and lvl R = stop first;
    a bar after the partial that touches entry = runner out at BE less 1 tick; else the runner keeps the trade's exit)."""
    import numpy as np
    if lvl in _PART:
        return _PART[lvl]
    from tools import lit_final as F
    V2, A, M, EAB = X.libs()
    if "B" not in _PART:
        Mk, _ = F.market("cisd", [])
        _PART["B"] = (F.bars(Mk, "5m"), F.bars(Mk, "1m"))
    B5, B1 = _PART["B"]
    out = {}
    for nm in X.MEM:
        for u in M.units()[nm]:
            B = B1 if int(u["entry_t"]) >= int(B1.t[0]) + 86400 else B5
            k0 = int(np.searchsorted(B.t, int(u["entry_t"]), side="right"))
            kx = int(np.searchsorted(B.t, int(u["exit_t"]) - B.secs))
            dr, r = int(u["dir"]), float(u["risk"])
            e = float(u["pts"])
            # entry price is not in the unit: rebuild it from the first bar's open and po[0]
            if not len(u["po"]) or kx < k0:
                continue
            ent = float(B.o[k0]) - float(u["po"][0]) * dr
            hi = (B.h[k0:kx + 1] - ent) * dr if dr == 1 else (ent - B.l[k0:kx + 1])
            lo = (B.l[k0:kx + 1] - ent) * dr if dr == 1 else (ent - B.h[k0:kx + 1])
            hit = np.where(hi >= lvl * r)[0]
            if not len(hit):
                continue
            j = int(hit[0])
            if (lo[:j + 1] <= -r).any() or j == len(hi) - 1 and e < lvl * r:
                continue                                  # stop first (or the exit bar itself without the level): unchanged
            run = e
            if (lo[j + 1:len(lo) - 1] <= 0).any():
                run = -M.SLIP                             # runner stopped at breakeven before the trade's own exit
            out[(nm, int(u["entry_t"]))] = 0.5 * lvl * r + 0.5 * run
    _PART[lvl] = out
    return out


def funded_partial(lvl, frac=1.0, seed=None):
    """A funded play_day with the partial applied (to a seeded random share `frac` of the eligible trades = the control)."""
    V2, A, M, EAB = X.libs()
    mp = partial_map(lvl)

    def play(L, day, bal, floor, session, rule, pre=False, _md=2, lost=None, litcfg=None, dll=None, reserve=False, extra=None):
        L2 = []
        for t in L:
            k = (t["src"], int(t["entry_t"]))
            if k in mp and (frac >= 1.0 or random.Random(f"{seed}:{k}").random() < frac):
                t = {**t, "pts": round(mp[k], 4)}
            L2.append(t)
        return M.play_day(L2, day, bal, floor, session, rule, pre, 2, lost, litcfg, dll=dll, reserve=reserve, extra=extra)
    return play


def cmd_partial(n=300):
    res = {}
    rows = [("today", None), ("p0.75", (0.75,)), ("p1", (1.0,)), ("p1.5", (1.5,))] + \
           [(f"ctl_p1_half_s{s}", (1.0, 0.5, s)) for s in (1, 2, 3, 4)]
    for name, a in rows:
        X.PLAY_FUNDED[0] = funded_partial(*a) if a else None
        try:
            o = {}
            for sd in (SEEDS if not name.startswith("ctl") else (23,)):
                sl = X.slot(X.today(), n=n, seed=sd)
                sl["2021-25"] = X.slot_ref(sl)
                o[sd] = {s: sl[s]["pm"] for s in ("H1", "H2", "2021-25")}
            rs, T = X.real_slot(X.today())
        finally:
            X.PLAY_FUNDED[0] = None
        o["funded_trades"] = stats([t for t in T if t["stage"] == "funded"])
        o["n_changed"] = len(partial_map(a[0])) if a else 0
        res[name] = o
        print(f"{name:16s} {o[23]}  " + " ".join(f"s{sd} {o[sd]}" for sd in SEEDS[1:] if sd in o), flush=True)
        json.dump(res, open(os.path.join(X.OUT, "atx_funded_partial.json"), "w", encoding="utf-8"), indent=1, default=str)
    return res


def cmd_save_partial():
    from tools import runlib as rl
    V2, A, M, EAB = X.libs()
    sess = sorted(set(M.units()["sessions"]))
    R = json.load(open(os.path.join(X.OUT, "atx_funded_partial.json"), encoding="utf-8"))
    for name, lvl, title in (("p1", 1.0, "ATLAS funded 25K: half off at 1R, stop to BE, runner to today's target (eval unchanged)"),
                             ("p1.5", 1.5, "ATLAS funded 25K: half off at 1.5R, stop to BE (neighbour; eval unchanged)")):
        X.PLAY_FUNDED[0] = funded_partial(lvl)
        try:
            rs, T = X.real_slot(X.today())
        finally:
            X.PLAY_FUNDED[0] = None
        T = X._runlib_trades(T)
        r, b = R[name], R["today"]
        vt = "; ".join(f"{s}: slot ${r['23'][s]:,}/mo (today ${b['23'][s]:,}), funded PF {r['funded_trades'][s]['pf']}, "
                       f"R/$ {r['funded_trades'][s]['r_per_risk']}" for s in ("H1", "H2", "2021-25"))
        rl.save("atxd_partial_" + name.replace(".", "p"), title, "management", "ATLAS 2026-10-31: does a partial + breakeven runner "
                "on the FUNDED 25K pay the owner more?", params={"funded_partial_R": lvl, "eval": "today",
                                                                 "runner": "stop to breakeven, else the trade's own exit"},
                sizing={"eval": "engine/account_b.qty need", "funded": "engine/sizing.funded_qty 25K preset (atx_edge.funded_q)"},
                trades=T, scored=rl.score(T, sess), status="rejected", verdict=vt,
                notes="tools/atx_funded_day.py partial (bar highs / lows from the members' own bar set; a bar touching both = stop first)",
                writeup="atlas-funded-one-a-day-2026-10-31", tags=["atlas", "account_b", "25k", "funded", "slot", "partial"])
        print("saved", name, flush=True)


# ============================================================ idea 4: funded re-entry after a stop-out (eval unchanged)
def reentry_units(rmult=1.0, flip_seed=None):
    """The member records hold one trade per member per day, so the re-entry = the same setup once more: after a STOP exit
    before 15:00 ET, enter at the next bar's open in the same direction (flip_seed: a coin-flip direction = the control),
    stop rmult x the first trade's risk away, target = the first trade's target price, flat 15:55 ET; a bar touching both
    = stop first; 1 tick slippage on entry and on a stop."""
    import numpy as np
    key = ("re", rmult, flip_seed)
    if key in _PART:
        return _PART[key]
    from tools import lit_final as F
    V2, A, M, EAB = X.libs()
    if "B" not in _PART:
        Mk, _ = F.market("cisd", [])
        _PART["B"] = (F.bars(Mk, "5m"), F.bars(Mk, "1m"))
    B5, B1 = _PART["B"]
    out = []
    for nm in X.MEM:
        for u in M.units()[nm]:
            if str(u["exit"]).lower() != "stop" or not len(u["po"]):
                continue
            B = B1 if int(u["entry_t"]) >= int(B1.t[0]) + 86400 else B5
            k0 = int(np.searchsorted(B.t, int(u["entry_t"]), side="right"))
            kx = int(np.searchsorted(B.t, int(u["exit_t"]) - B.secs))
            kr = kx + 1
            if kr >= len(B.t) or B.t[kr] - B.t[kx] > 3600 or A.et_mod(int(B.t[kr])) >= 15 * 60:
                continue
            dr0 = int(u["dir"])
            ent0 = float(B.o[k0]) - float(u["po"][0]) * dr0
            dr = dr0 if flip_seed is None else (dr0 if random.Random(f"{flip_seed}:{nm}:{u['entry_t']}").random() < 0.5 else -dr0)
            r = float(u["risk"]) * rmult
            ent = float(B.o[kr]) + M.SLIP * dr
            tgt = (float(u["tgt"]) - (ent - ent0) * dr0) if dr == dr0 else float(u["tgt"])
            if tgt < 0.5 * r:
                continue
            w, pts, xt, ex = 0.0, None, None, None
            k = kr
            while k < len(B.t) and B.t[k] - B.t[kr] < 12 * 3600:
                hi = (B.h[k] - ent) if dr == 1 else (ent - B.l[k])
                lo = (B.l[k] - ent) if dr == 1 else (ent - B.h[k])
                if A.et_mod(int(B.t[k])) >= 15 * 60 + 55:
                    pts, xt, ex = (float(B.o[k]) - ent) * dr, int(B.t[k]), "FLAT"
                    break
                if lo <= -r:
                    pts, xt, ex, w = -r - M.SLIP, int(B.t[k]) + B.secs, "STOP", -r
                    break
                w = min(w, lo)
                if hi >= tgt:
                    pts, xt, ex = tgt, int(B.t[k]) + B.secs, "TARGET"
                    break
                k += 1
            if pts is None:
                continue
            out.append({"day": u["day"], "entry_t": int(B.t[kr]), "exit_t": xt, "dir": dr, "exit": ex, "risk": round(r, 4),
                        "tgt": round(tgt, 4), "pts": round(pts, 4), "w1": round(max(-(r + 0.25), min(0.0, w, pts)), 4), "src": nm,
                        "pt": np.zeros(0, np.int64), "po": np.zeros(0), "pw": np.zeros(0), "reentry": True})
    by = {}
    for t in out:
        by.setdefault(t["day"], []).append(t)
    _PART[key] = by
    return by


def funded_reentry(rmult=1.0, flip_seed=None):
    V2, A, M, EAB = X.libs()
    by = reentry_units(rmult, flip_seed)

    def play(L, day, bal, floor, session, rule, pre=False, _md=2, lost=None, litcfg=None, dll=None, reserve=False, extra=None):
        L2 = sorted(list(L) + by.get(day, []), key=lambda t: t["entry_t"])
        return M.play_day(L2, day, bal, floor, session, rule, pre, 2, lost, litcfg, dll=dll, reserve=reserve, extra=extra)
    return play


def cmd_reentry(n=300):
    from tools import runlib as rl
    V2, A, M, EAB = X.libs()
    res = {}
    rows = [("today", None), ("re1", (1.0, None)), ("re1.5", (1.5, None))] + [(f"ctl_flip_s{s}", (1.0, s)) for s in (1, 2, 3, 4)]
    T1 = None
    for name, a in rows:
        X.PLAY_FUNDED[0] = funded_reentry(*a) if a else None
        try:
            o = {}
            for sd in (SEEDS if not name.startswith("ctl") else (23,)):
                sl = X.slot(X.today(), n=n, seed=sd)
                sl["2021-25"] = X.slot_ref(sl)
                o[sd] = {s: sl[s]["pm"] for s in ("H1", "H2", "2021-25")}
            rs, T = X.real_slot(X.today())
        finally:
            X.PLAY_FUNDED[0] = None
        o["funded_trades"] = stats([t for t in T if t["stage"] == "funded"])
        if a:
            U = [t for v in reentry_units(*a).values() for t in v]
            o["reentries"] = {s: {"n": len(x), "sum_R": round(sum(t["pts"] / t["risk"] for t in x), 1)}
                              for s, x in (("H1", [t for t in U if X.H1[0] <= t["day"] <= X.H1[1]]),
                                           ("H2", [t for t in U if t["day"] > X.H1[1]]), ("2021-25", [t for t in U if t["day"] < "2026"]))}
        if name == "re1":
            T1 = T
        res[name] = o
        print(f"{name:14s} {o[23]}  " + " ".join(f"s{sd} {o[sd]}" for sd in SEEDS[1:] if sd in o) + f"  {o.get('reentries', '')}", flush=True)
        json.dump(res, open(os.path.join(X.OUT, "atx_funded_reentry.json"), "w", encoding="utf-8"), indent=1, default=str)
    sess = sorted(set(M.units()["sessions"]))
    T = X._runlib_trades(T1)
    r, b = res["re1"], res["today"]
    vt = "; ".join(f"{s}: slot ${r[23][s]:,}/mo (today ${b[23][s]:,})" for s in ("H1", "H2", "2021-25"))
    rl.save("atxd_reentry_1r", "ATLAS funded 25K: the same setup once more after a stop-out (eval unchanged)", "management",
            "ATLAS 2026-10-31: does a re-entry after a stop-out on the FUNDED 25K pay the owner more?",
            params={"rmult": 1.0, "eval": "today", "rule": "after a STOP before 15:00 ET: next bar open, same direction, same risk, "
                    "the first trade's target price, flat 15:55"},
            sizing={"eval": "engine/account_b.qty need", "funded": "engine/sizing.funded_qty 25K preset (atx_edge.funded_q)"},
            trades=T, scored=rl.score(T, sess), status="rejected" if not all(r[23][s] > b[23][s] for s in ("H1", "H2", "2021-25")) else "promising",
            verdict=vt, notes="tools/atx_funded_day.py reentry", writeup="atlas-funded-one-a-day-2026-10-31",
            tags=["atlas", "account_b", "25k", "funded", "slot", "reentry"])
    return res


if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else "run"
    if c == "reentry":
        cmd_reentry()
        sys.exit(0)
    {"run": lambda: cmd_run(int(sys.argv[2]) if len(sys.argv) > 2 else 300), "save": cmd_save, "vix": cmd_vix,
     "partial": cmd_partial, "save_partial": cmd_save_partial}[c]()
