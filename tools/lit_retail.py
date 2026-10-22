"""Retail tools as NEW LIT entries (owner 2026-10-21: "EMAs / supply and demand / support and resistance ... Even MACD.
Implementing into LIT. We still should definitely find 3 entries a week whatever we do.").

Detectors: engine/lit_retail.py (pure, closed bars only). Every new setup runs through the exact live LIT executor
(engine/lit.run_x with live_model.json "lit": t_check, be_off, Monday rule, weekly stop, 1m CISD entry, VIX-band target).

Families: levels (S/R clusters, round numbers, S/D zone edges as extra LIT sweep levels), sd (zone retest), brt (break and
retest), ema (EMA pullback in trend), macd (MACD divergence replacing a failed LIT filter).
Ways to combine with LIT (each scored):
  alone   the new setup on its own, 1 trade a day
  first   LIT + new, 1 trade a day, the first fill wins (what a live bot can do; it can take a day's slot before LIT's setup)
  slot    the new setup only on days LIT has no trade (the owner's "second slot"; needs to know LIT will not trade later that
          day, so it is an upper bound, not a live rule)
  second  LIT + new, up to 2 a day, at most 1 of each source, one at a time (engine option src_cap 1)
Scoring = tools/lit_more.py (LIT rule $ with weekly stop at $1.90/micro; MFFU 50K eval under the live lit_sizing two_week for
10 sessions then safe_eval, a fresh eval on every session -> 2-week (10 sessions) and 1-month (21 sessions) pass / fail).
Pick on H1 (Jan 2-Jun 30 2026), check on H2 (Jul 1-Oct 16); 2021-25 reference (5m execution).

  python -X utf8 tools/lit_retail.py check     # base == lit_live; no look-ahead (data cut at the entry) on every family
  python -X utf8 tools/lit_retail.py all       # every variant -> research/lit/retail_entries.json + rl.save lit_retail_e_*
Paper only.
"""
from __future__ import annotations

import collections
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from engine import lit_retail as R  # noqa: E402
from tools import lit_more as LMo  # noqa: E402
from tools import runlib as rl  # noqa: E402

OUT = os.path.join(ROOT, "research", "lit", "retail_entries.json")
LIVE = LMo.LIVE
SESS = LMo.SESS
_S = {}
RES = {}


def base():
    if "b" not in _S:
        M, C, B1, B5 = LMo.nq()
        T = lit.run_x(M, C, LIVE, SESS, B1=B1, B5=B5)
        _S["b"] = (M, C, B1, B5, T)
    return _S["b"]


def run(Cs, P=None):
    M, C, B1, B5, _ = base()
    return lit.run_x(M, Cs, {**LIVE, **(P or {})}, SESS, B1=B1, B5=B5)


def key(t):
    return (t["day"], int(t["entry_t"]))


# ------------------------------------------------------------------------------------------------ scoring
def evals(U, span):
    U = LMo.wk_mults(U)
    by = collections.defaultdict(list)
    for t in U:
        by[t["day"]].append(t)
    ss = LMo.sess_in(span)
    B = [sorted(by.get(s, []), key=lambda t: t["entry_t"]) for s in ss]
    z = len(ss)
    o = {}
    for h, tag in ((10, "10"), (21, "21")):
        ex = [LMo.run_eval(list(range(k, z)), B, horizon=h) for k in range(0, z - h + 1)]
        o["p" + tag] = round(100.0 * sum(r == "PASS" for r, _ in ex) / max(1, len(ex)), 1)
        o["f" + tag] = round(100.0 * sum(r == "FAIL" for r, _ in ex) / max(1, len(ex)), 1)
    return o


def score(U, added_keys=frozenset()):
    T = LMo.money_trades(U)
    o = {}
    for s in ("H1", "H2", "2026", "ref"):
        st = LMo.stats(T, s)
        a, zz = LMo.SPAN[s]
        TT = [t for t in T if a <= t["day"] <= zz]
        wks = collections.Counter(lit.iso_week(t["day"]) for t in TT)
        allw = {lit.iso_week(d) for d in LMo.sess_in(s)}
        st["wk3"] = round(100.0 * sum(1 for w in allw if wks[w] >= 3) / max(1, len(allw)), 1)
        st["added"] = sum(1 for t in TT if (t["day"], t["entry_t"]) in added_keys)
        o[s] = st
        if s in ("H1", "H2"):
            st.update(evals(U, s))
    return o


def line(k, o):
    f = lambda s: (f"{o[s]['n']:3d}(+{o[s]['added']:2d}) {o[s]['tpw']:4.2f}/wk w3 {o[s]['wk3']:4.1f} PF {o[s]['pf']} "
                   f"{o[s]['net']:+7,} DD {o[s]['dd']:+,} 2wk {o[s]['p10']}/{o[s]['f10']} 1mo {o[s]['p21']}/{o[s]['f21']}")
    return f"{k[:52]:52s} H1[{f('H1')}] H2[{f('H2')}] ref {o['ref']['n']} PF {o['ref']['pf']} {o['ref']['net']:+,}"


def put(k, T, meta, base_keys):
    U = LMo.unit(T)
    added = frozenset(key(t) for t in T if key(t) not in base_keys)
    o = score(U, added)
    o["meta"] = meta
    RES[k] = o
    _S.setdefault("T", {})[k] = (T, added)
    print(line(k, o), flush=True)
    return o


def variant(name, cfg, extraP=None):
    """Score one retail family cfg in the four combinations. extraP: run_x keys for every run (e.g. target classes)."""
    M, C, B1, B5, Tb = base()
    P = {**LIVE, **(extraP or {})}
    t0 = time.time()
    Cn = R.apply(M, C, {**P, "retail": cfg})
    Cn = [z for z in Cn if z.get("src", "lit") != "lit"]
    bk = {key(t) for t in Tb}
    meta = {"cfg": cfg, "P": extraP or {}, "n_cands": len(Cn)}
    Ta = run(Cn, extraP)
    put(f"{name} | alone", Ta, {**meta, "mode": "alone"}, set())
    Tf = run(R.merge(C, Cn), extraP)
    put(f"{name} | first", Tf, {**meta, "mode": "first"}, bk)
    lit_days = {t["day"] for t in Tb}
    Ts = sorted(list(Tb) + [t for t in Ta if t["day"] not in lit_days], key=lambda t: t["entry_t"])
    put(f"{name} | slot", Ts, {**meta, "mode": "slot"}, bk)
    T2 = run(R.merge(C, Cn), {**(extraP or {}), "max_per_day": 2, "src_cap": 1})
    put(f"{name} | second", T2, {**meta, "mode": "second"}, bk)
    print(f"   ({len(Cn)} candidates, {time.time() - t0:.0f}s)", flush=True)


# ------------------------------------------------------------------------------------------------ the grid
GRID = [
    # 1. extra LIT sweep levels (the unchanged LIT chain on them)
    ("L sr15", {"kind": "levels", "sr_tf": ["15m"]}),
    ("L sr1h", {"kind": "levels", "sr_tf": ["1h"]}),
    ("L sr15+1h", {"kind": "levels", "sr_tf": ["15m", "1h"]}),
    ("L sr15 3 touches", {"kind": "levels", "sr_tf": ["15m"], "sr_n": 3}),
    ("L sr15 tol 0.15", {"kind": "levels", "sr_tf": ["15m"], "sr_tol": 0.15}),
    ("L round 100", {"kind": "levels", "rn": [100]}),
    ("L round 50", {"kind": "levels", "rn": [50]}),
    ("L sd15 edges", {"kind": "levels", "sd_tf": ["15m"]}),
    ("L sd1h edges", {"kind": "levels", "sd_tf": ["1h"]}),
    ("L sd15 distal", {"kind": "levels", "sd_tf": ["15m"], "sd_edges": "d"}),
    ("L all (sr15+1h, rn100, sd15+1h)", {"kind": "levels", "sr_tf": ["15m", "1h"], "rn": [100], "sd_tf": ["15m", "1h"]}),
    # 2. supply / demand zone retest
    ("SD 15m stop zone", {"kind": "sd", "sd_tf": ["15m"], "stop": "zone"}),
    ("SD 15m stop ext", {"kind": "sd", "sd_tf": ["15m"], "stop": "ext"}),
    ("SD 1h stop zone", {"kind": "sd", "sd_tf": ["1h"], "stop": "zone"}),
    ("SD 1h stop ext", {"kind": "sd", "sd_tf": ["1h"], "stop": "ext"}),
    ("SD 15m+1h stop zone", {"kind": "sd", "sd_tf": ["15m", "1h"], "stop": "zone"}),
    ("SD 15m body 2.0", {"kind": "sd", "sd_tf": ["15m"], "sd_body": 2.0}),
    ("SD 15m+1h disp 0.8", {"kind": "sd", "sd_tf": ["15m", "1h"], "disp": 0.8}),
    # 3. S/R break and retest
    ("BRT sr15+1h", {"kind": "brt", "sr_tf": ["15m", "1h"]}),
    ("BRT sr1h", {"kind": "brt", "sr_tf": ["1h"]}),
    ("BRT sr15+1h+PDH/L", {"kind": "brt", "sr_tf": ["15m", "1h"], "brt_pd": True}),
    ("BRT sr15+1h tol 0.5", {"kind": "brt", "sr_tf": ["15m", "1h"], "brt_tol": 0.5}),
    ("BRT sr15+1h disp 0.8", {"kind": "brt", "sr_tf": ["15m", "1h"], "disp": 0.8}),
    ("BRT PDH/L only", {"kind": "brt", "sr_tf": [], "brt_pd": True}),
    # 4. EMA pullback in trend
    ("EMA pb 5m21", {"kind": "ema", "ema_pb": "5m21"}),
    ("EMA pb 5m50", {"kind": "ema", "ema_pb": "5m50"}),
    ("EMA pb 15m21", {"kind": "ema", "ema_pb": "15m21"}),
    ("EMA pb 5m21 strong", {"kind": "ema", "ema_pb": "5m21", "ema_h4": True}),
    ("EMA pb 5m50 strong", {"kind": "ema", "ema_pb": "5m50", "ema_h4": True}),
    ("EMA pb 5m21 disp 0.8", {"kind": "ema", "ema_pb": "5m21", "disp": 0.8}),
    # 5. MACD divergence as the substitute confirmation
    ("MACD 5m for any filter", {"kind": "macd", "macd_tf": "5m", "macd_sub": ["any"]}),
    ("MACD 5m for inducement", {"kind": "macd", "macd_tf": "5m", "macd_sub": ["idm"]}),
    ("MACD 5m for depth", {"kind": "macd", "macd_tf": "5m", "macd_sub": ["depth"]}),
    ("MACD 5m for displacement", {"kind": "macd", "macd_tf": "5m", "macd_sub": ["disp"]}),
    ("MACD 15m for any filter", {"kind": "macd", "macd_tf": "15m", "macd_sub": ["any"]}),
    ("MACD 15m for inducement", {"kind": "macd", "macd_tf": "15m", "macd_sub": ["idm"]}),
    ("MACD 5m any, depth>=0.25 disp>=0.5", {"kind": "macd", "macd_tf": "5m", "macd_sub": ["any"], "depth_min": 0.25, "disp_min": 0.5}),
]
# neighbours of the two closest calls (picked after the first grid: counted as extra tests) + their combination
SD_X = {"kind": "sd", "sd_tf": ["15m"], "stop": "ext"}
MC15 = {"kind": "macd", "macd_tf": "15m", "macd_sub": ["idm"]}
GRID2 = [
    ("N SD 15m stop ext body 1.75", {**SD_X, "sd_body": 1.75}),
    ("N SD 15m stop ext body 2.0", {**SD_X, "sd_body": 2.0}),
    ("N SD 15m stop ext through 0.25", {**SD_X, "sd_through": 0.25}),
    ("N SD 15m stop ext age 1 day", {**SD_X, "sd_age": 288}),
    ("N MACD 15m inducement look 72", {**MC15, "macd_look": 72}),
    ("N MACD 15m inducement look 36", {**MC15, "macd_look": 36}),
    ("N MACD 15m inducement or depth", {**MC15, "macd_sub": ["idm", "depth"]}),
    ("N MACD 5m+15m inducement", [MC15, {"kind": "macd", "macd_tf": "5m", "macd_sub": ["idm"]}]),
    ("N combo SD 15m ext + MACD 15m inducement", [SD_X, MC15]),
    ("N combo SD 15m body 2.0 + MACD 15m inducement", [{"kind": "sd", "sd_tf": ["15m"], "sd_body": 2.0}, MC15]),
]


def dump():
    old = json.load(open(OUT)) if os.path.exists(OUT) else {}
    old.update(RES)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(old, open(OUT, "w"), indent=1, default=float)


def all_(names=None):
    M, C, B1, B5, Tb = base()
    put("base (live LIT)", Tb, {"mode": "base"}, {key(t) for t in Tb})
    for nm, cfg in GRID:
        if names and not any(nm.startswith(x) for x in names):
            continue
        variant(nm, cfg)
        dump()


# ------------------------------------------------------------------------------------------------ look-ahead check
def lookahead(cfg, n=25, seed=3):
    """Rebuild the family on data cut at the entry bar (the bars up to the trigger bar's close + the entry bar) and check every
    sampled 2026 candidate comes back identical (same trigger, extreme, CISD level, stop extreme)."""
    M, C, B1, B5, Tb = base()
    Cn = [z for z in R.build(M, C, cfg, LIVE) if z["day"] >= "2026"]
    rng = np.random.default_rng(seed)
    pick = [Cn[q] for q in sorted(rng.choice(len(Cn), size=min(n, len(Cn)), replace=False))] if Cn else []
    bad = 0
    for z in pick:
        a = max(0, z["entry_i"] - 288 * 40)
        b5 = M.b.slice(a, z["entry_i"] + 1)
        Mx = lit.Market(bars=b5)
        Mx.n_closed = Mx.n - 1            # the entry bar is forming: never a trigger / level / swing / candle
        Cx = lit.candidates(Mx, ref="cisd")
        got = [y for y in R.build(Mx, Cx, cfg, LIVE) if y["day"] == z["day"] and y["entry_t"] == z["entry_t"] and y["dir"] == z["dir"]]
        ok = any(abs(y["ext_d"] - z["ext_d"]) < 1e-6 and abs(y["ref_d"] - z["ref_d"]) < 1e-6 for y in got)
        bad += not ok
        if not ok:
            print("   LOOK-AHEAD?", z["day"], z["entry_t"], z["dir"], z["ext_d"], z["ref_d"], [(y["ext_d"], y["ref_d"]) for y in got])
    print(f"lookahead {cfg}: {len(pick)} sampled, {bad} differ", flush=True)
    return bad


def check():
    M, C, B1, B5, Tb = base()
    r = rl.load("lit_live")
    a = {(t[0], t[1]) for t in [[dict(zip(r["trade_cols"], x))["day"], int(dict(zip(r["trade_cols"], x))["entry_t"])] for x in r["trades"]]
         if t[0] >= "2026"}
    b = {key(t) for t in Tb if t["day"] >= "2026"}
    print("base 2026", len(b), "lit_live", len(a), "identical", len(a & b))
    T0 = lit.run_x(M, R.apply(M, C, {**LIVE, "retail": None}), {**LIVE, "retail": None, "src_cap": None}, SESS, B1=B1, B5=B5)
    print("retail None -> identical trades:", [key(t) for t in T0] == [key(t) for t in Tb])
    for nm, cfg in GRID:
        if nm in ("L sr15", "L round 100", "L sd15 edges", "SD 15m stop zone", "BRT sr15+1h", "EMA pb 5m21", "MACD 5m for any filter",
                  "MACD 15m for any filter"):
            lookahead(cfg)


# ------------------------------------------------------------------------------------------------ save
def save(keys, status_of):
    M, C, B1, B5, Tb = base()
    for k in keys:
        T, added = _S["T"][k]
        U = LMo.unit(T)
        MT = LMo.money_trades(U)
        rows = []
        for t in MT:
            ru = t["risk"] * LMo.PV * t["qty"]
            rows.append({"day": t["day"], "entry_t": t["entry_t"], "exit_t": t["exit_t"], "dir": t["dir"], "r": round(t["pnl"] / ru, 3) if ru else 0.0,
                         "pnl": t["pnl"], "low": t["low"], "risk_pts": round(t["risk"], 2), "qty": t["qty"], "risk_usd": round(ru, 2),
                         "half": t["wk_m"] < 1, "exit": t["exit"], "trigger": "LIT-retail" if (t["day"], t["entry_t"]) in added else "LIT",
                         "mfe": None, "mae": None, "bars_held": None, "regime": "", "mult": t["wk_m"]})
        o = RES[k]
        h = lambda s: (f"{s}: {o[s]['n']} trades (+{o[s]['added']} new), {o[s]['tpw']}/wk, 3+/wk {o[s]['wk3']}% of weeks, win {o[s]['win']}%, "
                       f"PF {o[s]['pf']}, net ${o[s]['net']:+,} (${o[s]['per_month']:,}/mo), DD ${o[s]['dd']:,}; eval two_week 2-wk "
                       f"pass/fail {o[s]['p10']}/{o[s]['f10']}, 1-mo {o[s]['p21']}/{o[s]['f21']}")
        verdict = "; ".join(h(s) for s in ("H1", "H2")) + f"; 2021-25 reference (5m) PF {o['ref']['pf']} ${o['ref']['net']:+,}."
        rid = "lit_retail_e_" + "".join(ch if ch.isalnum() else "_" for ch in k.lower()).strip("_")
        while "__" in rid:
            rid = rid.replace("__", "_")
        rl.save(rid, "LIT retail entries: " + k, "other",
                "Owner 2026-10-21: retail tools (EMAs, supply/demand, S/R, MACD) as new LIT entries; 3+ trades a week.",
                params={"variant": k, **o.get("meta", {})},
                sizing={"money": "LIT rule $800/20 + weekly stop, $1.90/micro", "eval": "lit_sizing two_week (10 sessions) then safe_eval"},
                trades=rows, scored=rl.score(rows, SESS), status=status_of(k), verdict=verdict,
                notes="tools/lit_retail.py, engine/lit_retail.py. Results: research/lit/retail_entries.json",
                writeup="lit-retail-entries", tags=["lit", "lit_retail"])
        print("saved", rid, flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        check()
    elif cmd == "all":
        all_(sys.argv[2:] or None)
        dump()
    elif cmd == "save":
        # one stored run per variant (the "second" combination: the one that adds the most trades) + every combination of the
        # closest calls and of the H1 pick; every row of every combination is in research/lit/retail_entries.json
        M, C, B1, B5, Tb = base()
        bk = {key(t) for t in Tb}
        put("base (live LIT)", Tb, {"mode": "base"}, bk)
        keys = ["base (live LIT)"]
        FULL = ("MACD 15m for inducement", "N SD 15m stop ext body 1.75", "N combo SD 15m ext + MACD 15m inducement", "EMA pb 15m21")
        for nm, cfg in GRID + GRID2:
            if nm in FULL:
                variant(nm, cfg)
                keys += [f"{nm} | {m}" for m in ("alone", "first", "slot", "second")]
                continue
            Cn = [z for z in R.apply(M, C, {**LIVE, "retail": cfg}) if z.get("src", "lit") != "lit"]
            T2 = run(R.merge(C, Cn), {"max_per_day": 2, "src_cap": 1})
            put(f"{nm} | second", T2, {"cfg": cfg, "P": {}, "n_cands": len(Cn), "mode": "second"}, bk)
            keys.append(f"{nm} | second")
        best = {"MACD 15m for inducement | second", "N SD 15m stop ext body 1.75 | second",
                "N combo SD 15m ext + MACD 15m inducement | second"}
        save(keys, lambda k: "info" if k.startswith("base") else "promising" if k in best else "rejected")
        rl.index()
    elif cmd == "grid2":
        base()
        put("base (live LIT)", base()[4], {"mode": "base"}, {key(t) for t in base()[4]})
        for nm, cfg in GRID2:
            variant(nm, cfg)
            dump()
