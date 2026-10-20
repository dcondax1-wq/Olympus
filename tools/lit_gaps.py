"""LIT gap audit (2026-10-20): LIT / ICT / SMC ideas that no earlier LIT study tested, run through the ENGINE (engine/lit.py
run_x, the code the live loop runs) with new default-off options, on live LIT and on top of the adopt-candidate combo
(t_check + scale_in + be_off, tools/lit_adopt_combo.py). Judged the LIT way: 2026 only, H1 (Jan-Jun) picks, H2 (Jul-Oct)
checks; 2021-25 is a reference line (5m bars only there).

Two views, both costs in (the same as tools/lit_adopt_combo.py / tools/lit_idm_eval.py):
  LIT size rule  the engine's own trades ($800 up to a 20-pt stop, weekly stop), scored by tools/lit_final.score
  eval path      the live two_week sizing (engine/sizing.lit_qty: two_week 10 sessions then safe_eval, no reset, $1.90 a micro,
                 scale-in adds by engine/sizing.scale_in_qty), the engine's trades as units (tools/lit_adopt_combo.units),
                 scored by tools/lit_adv_manage.py + tools/lit_big_ideas.py (fresh evals on every session, Monte Carlo,
                 back-to-back path)

Families (engine option -> idea):
  kz        killzone parameters (London 02:00-08:00 vs New York 08:00-15:30 own depth / displacement / target)
  satr      ATR-regime stop limits (skip a planned stop above k x or below k x the 5m ATR)
  dmax      maximum sweep depth (a sweep that runs too far is a breakout, not a sweep)
  sd        Asia-range standard-deviation targets (the Asia box extreme +/- k x its range; replace / nearer / farther vs the band)
  lvl       new liquidity: Monday's high/low on Wed-Fri, 10/20-day highs/lows (turtle soup), also as targets
  tx        time exits: London trades by the NY open / 10:00 / 11:00 if not at breakeven; the 12:00 profit take re-scored
  rebe      re-entry after a breakeven scratch, same side (or any side)
  nth       entry on the 2nd 1m CISD after the tap
  open      the LIT opening model (09:30-10:00 sweep of the overnight / NY trap range, tools/lit_t_entries.detect) as
            market-entry candidates inside the engine (first time on the real eval path and with the combo)
  trap      the failed-zone flip (smart money trap: a LIT zone reacts, then its extreme breaks; trade the failure at the
            zone's CISD level, tools/lit_t_discovery.trap_setups) as limit candidates inside the engine

    python -X utf8 tools/lit_gaps.py check          # options off == lit_live (and the combo == research/lit/adopt_combo.json)
    python -X utf8 tools/lit_gaps.py grid [fam..]    # score -> research/lit/gaps_results.json
    python -X utf8 tools/lit_gaps.py save           # rl.save runs lit_gap_* (best per family, both bases)
Paper only. Changes nothing in live_model.json.
"""
from __future__ import annotations

import collections
import json
import os
import pickle
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from tools import lit_adopt_combo as AC  # noqa: E402
from tools import lit_big_ideas as BI  # noqa: E402  (patches lit_adv_manage.run_eval with the add-aware eval)
from tools import lit_adv_manage as A  # noqa: E402
from tools import lit_final as F  # noqa: E402
from tools import runlib as rl  # noqa: E402

OUT = os.path.join(ROOT, "research", "lit", "gaps_results.json")
LIVE = AC.LIVE
COMBO = {"t_check": AC.T15, "scale_in": AC.SCALE, "be_off": AC.BE_OFF}
BASES = {"live": {}, "combo": COMBO}


# ------------------------------------------------------------------------------------------------ data
_MK = {}


def market(levels=()):
    """Market + candidates (ref cisd, live boxes) with optional extra liquidity levels; candidates cached on disk."""
    levels = tuple(sorted(levels))
    if not levels:
        return F.market(LIVE["ref"], LIVE["extra_boxes"])
    if levels in _MK:
        return _MK[levels]
    M = lit.Market(extra_boxes=list(LIVE["extra_boxes"]), extra_levels=list(levels))
    p = os.path.join(F.CACHE, f"litgaps_{F.CAND_V}_{'-'.join(levels)}_{rl._data_key().replace(':', '_')}.pkl")
    if os.path.exists(p):
        C = pickle.load(open(p, "rb"))
    else:
        C = lit.candidates(M, ref=LIVE["ref"])
        os.makedirs(F.CACHE, exist_ok=True)
        pickle.dump(C, open(p, "wb"))
    _MK[levels] = (M, C)
    return M, C


def _stub(M, k, d, day, ei5, i, entry_d, ext_d, ref_d, swept):
    """A candidate dict carrying every field run_x / simulate_x read (pre-filtered: pre_ok)."""
    return {"day": day, "k": k, "dir": d, "i": int(i), "ext_i": int(i), "ref_i": int(i), "entry_i": int(ei5), "sweep_i": int(i),
            "entry_t": int(M.t[ei5]), "entry_d": float(entry_d), "ext_d": float(ext_d), "ref_d": float(ref_d),
            "trig_c": float(ref_d), "mod": int(M.mod[ei5]), "swept": swept, "swept_cls": [], "depth_atr": 0.0, "ind_n": 0,
            "disp": 0.0, "vec": False, "vec_any": False, "how": True, "targets": {}, "idm_a": [], "atr": float(M.atr[i]),
            "atr_ext": float(M.atr[i]), "sw": {}, "pre_ok": True}


def open_cands(M, X, P):
    """The LIT opening model (tools/lit_t_entries.detect, the 2026-10-18 adopt-candidate: overnight range, depth 0.25 ATR, by
    10:00) as market-entry candidates: the engine fills them at the detector's 1m bar open and manages them like any trade."""
    from tools import lit_t_entries as TE
    B1, B5 = F.bars(M, "1m"), F.bars(M, "5m")
    S = TE.detect(M, B1, B5, X, {**P, "flat_mod": P["flat_mod"]}, list(F.SESS))
    out = []
    for s_ in S:
        if s_["B"].secs != 60:
            continue
        ei5 = int(np.searchsorted(M.t, s_["t"], side="right") - 1)
        z = _stub(M, s_["s_day"], s_["dir"], s_["day"], ei5, ei5 - 1, s_["entry"], s_["stop"] + P["stop_buf"], s_["entry"],
                  ["open_" + (X.get("lv") or "both")])
        z["mkt"] = {"t": int(s_["t"]), "entry_d": float(s_["entry"]), "stop_d": float(s_["stop"]), "tf": 1}
        z["_t"] = int(s_["t"])
        out.append(z)
    return out


def trap_cands(M, C, P, X):
    """The failed-zone flip (tools/lit_t_discovery.trap_setups): a limit at the retest of the zone's CISD level ("ref") or of
    its broken extreme ("ext"), placed after the 5m bar that broke the zone's extreme, 30 min, then the live 1m CISD; stop 1
    tick beyond the reaction extreme; target the VIX band on the new side."""
    from tools import lit_t_discovery as TD
    B1, B5 = F.bars(M, "1m"), F.bars(M, "5m")
    S = TD.trap_setups(M, C, {**P, "trap": X}, set(F.SESS), B1, B5)
    out = []
    for s_ in S:
        f = int(s_["f"])
        if f + 1 >= M.n or int(M.t[f + 1]) != int(s_["t"]):
            continue
        z = _stub(M, s_["k"], s_["dir"], s_["day"], f + 1, f, s_["L"], s_["stop"] + P["stop_buf"], s_["L"], ["trap"])
        z["_t"] = int(s_["t"])
        out.append(z)
    return out


def run_v(x, base="live"):
    """Engine trades of one variant: live_model.json lit + the base's options + x. x may carry "_levels" (extra liquidity
    levels), "_open" (opening-model detector settings) or "_trap" (failed-zone settings)."""
    x = dict(x)
    levels = x.pop("_levels", ())
    xo, xt = x.pop("_open", None), x.pop("_trap", None)
    P = {**lit.DEFAULTS, **LIVE, **BASES[base], **x}
    M, C = market(levels)
    if xo or xt:
        ex = (open_cands(M, xo, P) if xo else []) + (trap_cands(M, C, P, xt) if xt else [])
        ev = [(int(M.t[z["entry_i"]]), 0, n, z) for n, z in enumerate(C)] + [(z["_t"], 1, n, z) for n, z in enumerate(ex)]
        ev.sort(key=lambda r: (r[0], r[1], r[2]))
        C = [r[3] for r in ev]
    return lit.run_x(M, C, P, F.SESS, B1=F.bars(M, "1m"), B5=F.bars(M, "5m"))


# ------------------------------------------------------------------------------------------------ scoring
def changed(T, T0):
    """Trades that differ from the base (added, removed or a different exit / P&L), per half."""
    key = lambda t: (t["day"], int(t["entry_t"]), t["exit"], round(t["pnl"], 1))  # noqa: E731
    a, b = {key(t) for t in T if t["day"] >= "2026"}, {key(t) for t in T0 if t["day"] >= "2026"}
    o = {}
    for s, (lo, hi) in (("H1", ("2026-01-01", "2026-06-30")), ("H2", ("2026-07-01", "2026-12-31"))):
        o[s] = sum(1 for k in a ^ b if lo <= k[0] <= hi)
    return o


def ev_dollars(U, span, horizon=10):
    """Average $ a fresh eval makes in its first `horizon` sessions (or until it passes / fails), over every start of the
    half that can see the full horizon: the eval-path money without the back-to-back path's restart noise."""
    by = A.by_day(U)
    a, z = A.span_ix(span)
    v = []
    for i in range(a, z - horizon + 1):
        K = []
        A.run_eval(list(range(i, i + horizon)), by, horizon, keep=K)
        v.append(sum(t["pnl"] for t in K))
    return round(float(np.mean(v)), 1) if v else 0.0


def score_T(T):
    A._MC.clear()
    U = AC.units(T)
    e = BI.short(BI.score(U))
    for s in ("H1", "H2"):
        e[s]["ev10"] = ev_dollars(U, s)
    o = F.score(T, spans=("H1", "H2", "2021-25"), fast=True)
    lr = {s: {k: o[s].get(k) for k in ("n", "tpw", "pf", "net", "dd")} for s in o}
    return {"lit": lr, "eval": e, "exits": dict(collections.Counter(t["exit"] for t in T if t["day"] >= "2026"))}


def delta(o, b):
    """Changes vs the base: eval-path net / 2-week pass / fail (real starts and Monte Carlo), LIT-rule net, 2021-25 net."""
    d = {}
    for s in ("H1", "H2"):
        e, eb = o["eval"][s], b["eval"][s]
        d[s] = {"eval_net": e["net"] - eb["net"], "ev10": round(e["ev10"] - eb["ev10"], 1), "p10": round(e["p10"] - eb["p10"], 1), "f10": round(e["f10"] - eb["f10"], 1),
                "mc_p10": round(e["mc_p10"] - eb["mc_p10"], 1), "mc_f10": round(e["mc_f10"] - eb["mc_f10"], 1),
                "lit_net": o["lit"][s]["net"] - b["lit"][s]["net"], "tpw": e["tpw"]}
    d["2021-25"] = o["lit"]["2021-25"]["net"] - b["lit"]["2021-25"]["net"]
    return d


def gate(d, ch):
    """Adopt-candidate test: more net $ in H1 AND H2 on the eval path and at the LIT size, no more 2-week fails (real starts
    and Monte Carlo, 0.5 pt tolerance on the MC), 2-4 trades a week, and at least 4 changed trades in each half."""
    why = []
    for s in ("H1", "H2"):
        x = d[s]
        if x["eval_net"] <= 0:
            why.append(f"{s} eval-path $ {x['eval_net']:+,}")
        if x["ev10"] <= 0:
            why.append(f"{s} $ per 2-week eval {x['ev10']:+}")
        if x["lit_net"] <= 0:
            why.append(f"{s} LIT-size $ {x['lit_net']:+,}")
        if x["f10"] > 0:
            why.append(f"{s} 2-wk fails +{x['f10']}")
        if x["mc_f10"] > 0.5:
            why.append(f"{s} MC 2-wk fails +{x['mc_f10']}")
        if not (2.0 <= x["tpw"] <= 4.0):
            why.append(f"{s} {x['tpw']}/wk")
        if ch[s] < 4:
            why.append(f"{s} only {ch[s]} trades changed")
    return why


# ------------------------------------------------------------------------------------------------ variants
NY, LON = [480, 960], [0, 480]
OPEN_OB = {"kind": "open", "sweep_win": (570, 600), "sig_end": 600, "depth": 0.25, "idm": True, "ev_max": 60}
TRAP = {"react": 1.0, "win": 24, "lvl": "ref", "wait": 30}


def variants():
    V = collections.OrderedDict()
    # 1. killzone parameters
    for k_, v_ in (("disp", 0.6), ("disp", 1.0), ("disp", 1.2), ("depth", 0.3), ("depth", 0.75), ("depth", 1.0),
                   ("vix_k", 0.75), ("vix_k", 1.25), ("min_rr", 2.5), ("max_rr", 5.0)):
        V[f"kz NY {k_} {v_}"] = ("kz", {"kz": [[NY[0], NY[1], {k_: v_}]]})
    for k_, v_ in (("disp", 1.0), ("depth", 0.75), ("vix_k", 1.25), ("vix_k", 0.9)):
        V[f"kz London {k_} {v_}"] = ("kz", {"kz": [[LON[0], LON[1], {k_: v_}]]})
    for k_, v_ in (("disp", 1.0), ("depth", 0.75), ("vix_k", 0.75)):
        V[f"kz 05:00+ {k_} {v_}"] = ("kz", {"kz": [[300, 960, {k_: v_}]]})
    for dp in (0.6, 0.65, 0.7, 0.8, 0.9, 1.0):
        V[f"kz London depth {dp}"] = ("kz", {"kz": [[LON[0], LON[1], {"depth": dp}]]})
    for dp in (0.6, 0.7, 0.75, 0.8):
        V[f"depth all-day {dp}"] = ("kz", {"depth": dp})
    # 2. ATR-regime stop limits (planned stop / 5m ATR at the trigger)
    for hi in (3.0, 4.0, 5.0, 6.0, 8.0):
        V[f"satr max {hi}"] = ("satr", {"stop_atr": [None, hi]})
    for lo in (1.0, 1.5, 2.0):
        V[f"satr min {lo}"] = ("satr", {"stop_atr": [lo, None]})
    # 3. maximum sweep depth
    for dm in (1.5, 2.0, 2.5, 3.0, 4.0):
        V[f"dmax {dm}"] = ("dmax", {"depth_max": dm})
    # 4. Asia-range standard-deviation targets
    for k_ in (1.0, 1.5, 2.0, 2.5, 3.0, 4.0):
        V[f"sd asia20 replace {k_}"] = ("sd", {"sd_tgt": {"box": "asia20", "k": k_, "mode": "replace"}})
    for k_ in (2.0, 3.0, 4.0):
        V[f"sd asia20 near {k_}"] = ("sd", {"sd_tgt": {"box": "asia20", "k": k_, "mode": "near"}})
    for k_ in (1.0, 1.5, 2.0):
        V[f"sd asia20 far {k_}"] = ("sd", {"sd_tgt": {"box": "asia20", "k": k_, "mode": "far"}})
    for k_ in (1.5, 2.0, 2.5):
        V[f"sd asia18 replace {k_}"] = ("sd", {"sd_tgt": {"box": "asia18", "k": k_, "mode": "replace"}})
    # 5. new liquidity levels (sweepable) and as targets
    for lv in (("mon",), ("d10",), ("d20",), ("mon", "d20")):
        V[f"lvl {'+'.join(lv)}"] = ("lvl", {"_levels": lv})
    V["lvl mon + mon target"] = ("lvl", {"_levels": ("mon",), "classes": ["vix", "mon"]})
    V["lvl d20 + d20 target"] = ("lvl", {"_levels": ("d20",), "classes": ["vix", "d20"]})
    # 6. time exits
    for at in (570, 600, 660):
        V[f"tx London not-BE out {at // 60:02d}:{at % 60:02d}"] = ("tx", {"tx": [{"at": at, "pre": 480, "be": False}]})
        V[f"tx London <0R out {at // 60:02d}:{at % 60:02d}"] = ("tx", {"tx": [{"at": at, "pre": 480, "hi": 0.0}]})
    V["tx London all out 09:30"] = ("tx", {"tx": [{"at": 570, "pre": 480}]})
    V["tx London all out 11:00"] = ("tx", {"tx": [{"at": 660, "pre": 480}]})
    for at in (690, 720, 750):
        for r_ in (0.5, 1.0):
            V[f"tx profit {at // 60:02d}:{at % 60:02d} >= {r_}R"] = ("tx", {"tx": [{"at": at, "lo": r_}]})
    for at, r_ in ((705, 0.5), (720, 0.25), (720, 0.75), (735, 0.5)):
        V[f"tx profit {at // 60:02d}:{at % 60:02d} >= {r_}R"] = ("tx", {"tx": [{"at": at, "lo": r_}]})
    # 7. re-entry after a breakeven scratch
    V["rebe same"] = ("rebe", {"re_be": {"side": "same", "kinds": ["BE"]}})
    V["rebe any"] = ("rebe", {"re_be": {"side": "any", "kinds": ["BE"]}})
    V["rebe same +cut"] = ("rebe", {"re_be": {"side": "same", "kinds": ["BE", "CUT_T15"]}})
    V["rebe same +stop"] = ("rebe", {"re_be": {"side": "same", "kinds": ["BE", "STOP"]}})
    # 8. 2nd 1m CISD
    V["nth 2"] = ("nth", {"cisd_nth": 2})
    V["nth 2 window 30"] = ("nth", {"cisd_nth": 2, "cisd1m": 15})
    # 9. opening model
    V["open overnight d0.25 to10:00"] = ("open", {"_open": {**OPEN_OB, "lv": "on"}})
    V["open overnight d0.5 to10:00"] = ("open", {"_open": {**OPEN_OB, "lv": "on", "depth": 0.5}})
    V["open overnight d0 to10:00"] = ("open", {"_open": {**OPEN_OB, "lv": "on", "depth": 0.0}})
    V["open overnight d0.25 to10:15"] = ("open", {"_open": {**OPEN_OB, "lv": "on", "sig_end": 615}})
    V["open trap box d0.25 to10:00"] = ("open", {"_open": {**OPEN_OB, "lv": "trap"}})
    V["open both d0.25 to10:00"] = ("open", {"_open": {**OPEN_OB}})
    # 10. failed-zone flip
    V["trap ref react1.0"] = ("trap", {"_trap": TRAP})
    V["trap ref react0.5"] = ("trap", {"_trap": {**TRAP, "react": 0.5}})
    V["trap ref react1.5"] = ("trap", {"_trap": {**TRAP, "react": 1.5}})
    V["trap ref react1.0 win12"] = ("trap", {"_trap": {**TRAP, "win": 12}})
    V["trap ext react1.0"] = ("trap", {"_trap": {**TRAP, "lvl": "ext"}})
    return V


def _clean(x):
    return dict(x)


# ------------------------------------------------------------------------------------------------ runs
def _load():
    return json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}


def check():
    T = run_v({}, "live")
    r = rl.load("lit_live")
    Tr = [dict(zip(r["trade_cols"], a)) for a in r["trades"]]
    ka = [(t["day"], int(t["entry_t"]), round(t["pnl"], 2)) for t in Tr]
    kb = [(t["day"], int(t["entry_t"]), round(t["pnl"], 2)) for t in T]
    print(f"options off: {len(kb)} trades vs lit_live {len(ka)}; identical {ka == kb}", flush=True)
    b = score_T(T)
    ref = json.load(open(AC.OUT, encoding="utf-8"))
    ok = all(b["eval"][s][k] == ref["base"]["eval"][s][k] for s in ("H1", "H2") for k in ("net", "p10", "f10", "mc_p10", "mc_f10"))
    print("live eval == research/lit/adopt_combo.json base:", ok, flush=True)
    c = score_T(run_v({}, "combo"))
    okc = all(c["eval"][s][k] == ref["all3"]["eval"][s][k] for s in ("H1", "H2") for k in ("net", "p10", "f10", "mc_p10", "mc_f10"))
    print("combo eval == research/lit/adopt_combo.json all3:", okc, flush=True)
    return ka == kb and ok and okc


def line(nm, base, o, d, ch):
    e = o["eval"]
    return (f"{base:5s} {nm:36s} H1 eval {d['H1']['eval_net']:+7,} lit {d['H1']['lit_net']:+7,} 2w {e['H1']['p10']}/{e['H1']['f10']} "
            f"mc {e['H1']['mc_p10']}/{e['H1']['mc_f10']} ch {ch['H1']:2d} | H2 eval {d['H2']['eval_net']:+7,} lit "
            f"{d['H2']['lit_net']:+7,} 2w {e['H2']['p10']}/{e['H2']['f10']} mc {e['H2']['mc_p10']}/{e['H2']['mc_f10']} ch {ch['H2']:2d}"
            f" | 21-25 {d['2021-25']:+7,} | {e['H1']['tpw']}/{e['H2']['tpw']} wk")


def grid(fams=None):
    res = _load()
    T0 = {b: run_v({}, b) for b in BASES}
    B0 = {b: score_T(T0[b]) for b in BASES}
    res["_base"] = B0
    for nm, (fam, x) in variants().items():
        if fams and fam not in fams:
            continue
        for b in BASES:
            T = run_v(_clean(x), b)
            o = score_T(T)
            d = delta(o, B0[b])
            ch = changed(T, T0[b])
            why = gate(d, ch)
            res[f"{b}|{nm}"] = {"fam": fam, "base": b, "params": {k: v for k, v in x.items()}, "score": o, "delta": d,
                                "changed": ch, "fails": why}
            print(line(nm, b, o, d, ch) + ("  PASS" if not why else ""), flush=True)
        json.dump(res, open(OUT, "w", encoding="utf-8"), indent=1, default=lambda v: list(v) if isinstance(v, tuple) else float(v))
    return res


FAM = {"kz": ("killzone parameters (London vs New York)", "filters"), "satr": ("ATR-regime stop limits", "stops"),
       "dmax": ("maximum sweep depth", "filters"), "sd": ("Asia-range standard-deviation targets", "targets"),
       "lvl": ("Monday range / 10-20-day highs-lows as liquidity (turtle soup)", "filters"),
       "tx": ("time exits (London by NY open, midday profit take)", "management"),
       "rebe": ("re-entry after a breakeven scratch", "timing"), "nth": ("entry on the 2nd 1m CISD", "timing"),
       "open": ("LIT opening model 09:30-10:00 (overnight / NY trap range)", "sessions"),
       "trap": ("failed-zone flip (smart money trap)", "other")}
STATUS = {"tx": "promising"}      # the midday profit take: every gate but the back-to-back eval-path $ (see the write-up)


def _h(o, d, s):
    e, l_ = o["eval"][s], o["lit"][s]
    return (f"eval path n={e['n']} {e['tpw']}/wk PF {e['pf']} net {e['net']:+,} (${e['per_month']:,}/mo, {d[s]['eval_net']:+,}) DD "
            f"{e['dd']:,}, $ per 2-week eval {e['ev10']:+,.0f} ({d[s]['ev10']:+,.0f}), 2-week pass/fail {e['p10']}/{e['f10']} (MC "
            f"{e['mc_p10']}/{e['mc_f10']}); LIT size net {l_['net']:+,} ({d[s]['lit_net']:+,}) PF {l_['pf']} DD {l_['dd']:,}")


def save():
    R = _load()
    Q = ("Owner 2026-10-20: gap audit - which LIT / ICT / SMC ideas were never tested on LIT? Test the top ~10 on live LIT and on "
         "the adopt-candidate combo (t_check + scale_in + be_off), money first, real eval path.")
    by = collections.defaultdict(list)
    for k, v in R.items():
        if not k.startswith("_") and v["base"] == "live":
            by[v["fam"]].append(k.split("|", 1)[1])
    for fam, names in by.items():
        pick = max(names, key=lambda n: R["live|" + n]["delta"]["H1"]["lit_net"] + 1e-3 * R["live|" + n]["delta"]["H1"]["ev10"])
        for b in BASES:
            v = R[f"{b}|{pick}"]
            x = dict(v["params"])
            T = [{k: val for k, val in t.items() if not k.startswith("_") and k not in ("size_why",)} for t in run_v(x, b)]
            st = STATUS.get(fam, "adopt-candidate" if not v["fails"] else "rejected")
            o, d = v["score"], v["delta"]
            P = {**lit.DEFAULTS, **LIVE, **BASES[b], **{k: val for k, val in x.items() if not k.startswith("_")}, "gap_extra": {
                k: val for k, val in x.items() if k.startswith("_")}}
            rid = f"lit_gap_{fam}_{b}"
            rl.save(rid, f"LIT gap audit: {FAM[fam][0]} - {pick} (on {'live LIT' if b == 'live' else 'the combo'})", FAM[fam][1], Q,
                    params=json.loads(json.dumps(P, default=lambda q: list(q) if isinstance(q, tuple) else str(q))),
                    trades=T, scored=rl.score(T, F.SESS), status=st,
                    verdict=f"H1 pick of the family by LIT-size net. 2026 H1 (pick): {_h(o, d, 'H1')}. 2026 H2 (check): {_h(o, d, 'H2')}. "
                            f"2021-25 reference LIT size {d['2021-25']:+,}. Changed trades H1/H2 {v['changed']['H1']}/{v['changed']['H2']}. "
                            f"Gate: {'all passed' if not v['fails'] else '; '.join(v['fails'])}.",
                    notes="tools/lit_gaps.py: engine/lit.py run_x + the default-off gap options; eval path = tools/lit_adopt_combo."
                          "units + tools/lit_big_ideas / lit_adv_manage scoring (two_week 10 sessions then safe_eval, $1.90).",
                    writeup="lit-gap-audit", tags=["lit", "lit_gap"])
            print("saved", rid, pick, st, flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        print("CHECK", "OK" if check() else "FAILED")
    elif cmd == "grid":
        grid(sys.argv[2:] or None)
    elif cmd == "save":
        save()
