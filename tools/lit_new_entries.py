"""LIT new entry types and confluences (owner 2026-10-19: "add confluences and different types of entries: smart money traps,
IDM, build-ups, different types of inducements, 15-min order blocks aligned with other stuff, MSNR; find other entries that work
and put them in the bot; there are easily 3+ LIT trades a week").

Write-up: research/writeups/lit-new-entries.md. Detectors: engine/lit_entries.py (pure, closed bars only). engine/lit.py is not
edited; every new setup runs through the exact live LIT detector (engine.lit.candidates on other liquidity) and executor
(engine.lit.run_x with live_model.json "lit": 30-min limit at the 5m CISD level, 1m CISD entry, stop 1 tick beyond the sweep
extreme, VIX-band target, BE 1R, Monday rule, weekly stop).

Families (each scored alone, as an extra source with 1 trade a day (first fill of either source wins: what a live bot can do),
and as a 2nd trade a day; pick on H1 Jan-Jun 2026, check on H2 Jul-Oct 2026, 2021-25 = 5m reference only):
  msnr     MSNR levels (engine/lit_entries.msnr_levels: A / V levels from the close line, QM, SnR flips; 15m / 1h / 4h) as the
           swept liquidity of a LIT setup: standalone MSNR entries
  msnrlit  MSNR levels added to the LIT levels (a sweep of either counts)
  idmob    SMC inducement into an order block: a sweep of a 5m swing (IDM) sitting just in front of a fresh 15m / 1h block,
           the extreme runs into the block, 5m CISD -> LIT entry
  stack    stacked confluence as an independent 2nd entry type from the LIT setups the live filters reject (shallower sweep,
           smaller displacement, no inducement) when >= n confluences line up (15m / 1h OB at the extreme, SMT with ES, a
           fresh MSNR level at the extreme, 2+ inducements, build-up swept, PDH/PWH/PMH/gap swept, 4h storyline aligned);
           and live-filter setups with >= n confluences as a 2nd trade after the day's trade ended
  grade    confluence as SIZE on today's trades (A+ up / weak down); money at the LIT rule, eval under two_week (cuts only:
           "one winner passes" already sizes to the target)

Scoring = tools/lit_more.py (LIT rule $ + weekly stop at $1.90/micro, MFFU 50K exact eval under the live lit_sizing: two_week
for 10 sessions then safe_eval, fresh start on every session -> p10/f10 + 1,000-path MC).

  python -X utf8 tools/lit_new_entries.py check      # base == lit_live, lookahead test of the levels and tags
  python -X utf8 tools/lit_new_entries.py all        # every family -> research/lit/new_entries.json, then saves runs lit_ent_*
Paper only.
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
from engine import lit_entries as E  # noqa: E402
from engine import sizing as SZ  # noqa: E402
from tools import lit_more as LMo  # noqa: E402
from tools import runlib as rl  # noqa: E402

OUT = os.path.join(ROOT, "research", "lit", "new_entries.json")
CACHE = os.path.join(ROOT, "research", "runs", "_cache")
LIVE = LMo.LIVE
SESS = LMo.SESS
PV, COMM, SLIP = LMo.PV, LMo.COMM, LMo.SLIP
_S = {}
_RES = {}
_U = {}


# ================================================================================================ pools
def base():
    return LMo.nq()


def levels(tf, kinds=("A", "V", "QM", "F"), k=2, mm=0.5):
    key = ("lv", tf, tuple(kinds), k, mm)
    if key not in _S:
        M = base()[0]
        L = E.add_touch(M, E.msnr_levels(M, tf, k, mm, kinds))
        _S[key] = L
    return _S[key]


def pool(tag, L, keep_lit=False, cls="msnr", max_age=8640):
    """(LevelMarket, candidates) for levels L (cached on disk by tag)."""
    if tag in _S:
        return _S[tag]
    M = base()[0]
    LMk = E.LevelMarket(M, L, keep_lit=keep_lit, cls=cls, max_age=max_age)
    p = os.path.join(CACHE, f"litent_{tag}_v1_{rl._data_key().replace(':', '_')}.pkl")
    if os.path.exists(p):
        C = pickle.load(open(p, "rb"))
    else:
        C = lit.candidates(LMk, ref="cisd")
        os.makedirs(CACHE, exist_ok=True)
        pickle.dump(C, open(p, "wb"))
    _S[tag] = (LMk, C)
    return _S[tag]


def run_m(Mx, C, P, src):
    _, _, B1, B5 = base()
    P = {**LIVE, **(P or {})}
    T = lit.run_x(Mx, C, P, SESS, B1=B1, B5=B5)
    return T, LMo.unit(T, "NQ", src)


# ================================================================================================ scoring (lit_more + grade mult)
def money_trades(U):
    T = []
    for u in LMo.wk_mults(U):
        q = lit.qty_for(u["risk"])
        if q < 1:
            continue
        m = u["wk_m"] * u.get("g_m", 1.0)
        if m == 0:
            continue
        if m != 1:
            q = max(1, int(q * m + 1e-9)) if m < 1 else min(lit.MAX_MICROS, int(q * m + 1e-9))
        pnl = u["pts"] * PV * q - COMM * q
        T.append(dict(u, qty=q, pnl=round(pnl, 2), low=round(min(0.0, u["w1"] * PV * q - COMM * q, pnl), 2)))
    return T


def run_eval(seq, by, cfg=LMo.EVAL_CFG, horizon=10):
    """tools/lit_more.run_eval + a grade cut g_m < 1 applied after the live eval sizing (0 = skip; > 1 ignored)."""
    bal = peak = 0.0
    floor = -LMo.MLL
    for k, si in enumerate(seq[:horizon]):
        cum = 0.0
        opn = []
        for j, t in enumerate(by[si]):
            still = []
            for o in opn:
                if o[0] <= t["entry_t"]:
                    cum += o[1]
                else:
                    still.append(o)
            opn = still
            if cum <= -LMo.DLL:
                break
            orisk = sum(o[3] for o in opn)
            st = {"profit": bal, "cum": cum - orisk, "room": bal + cum - orisk - floor, "session": k + 1, "n_today": j}
            base_q = lit.qty_for(t["risk"])
            m0 = max(1, int(base_q * (t.get("wk_m") or 1.0) + 1e-9)) if base_q else 0
            q = SZ.lit_qty(m0, {"risk_pts": t["risk"], "tgt_pts": t["tgt"], "size_mult": t.get("wk_m", 1.0)}, cfg,
                           room=st["room"], state=st, learning=None)["qty"] if m0 else 0
            g = t.get("g_m", 1.0)
            if q > 0 and g < 1:
                q = 0 if g == 0 else max(1, int(q * g + 1e-9))
            if q <= 0:
                continue
            pnl = t["pts"] * PV * q - COMM * q
            low = min(0.0, t["w1"] * PV * q - COMM * q, pnl)
            olow = sum(o[2] for o in opn)
            if cum + olow + low <= -LMo.DLL:
                pnl = -LMo.DLL - cum - olow - SLIP * PV * q
                low = pnl
            if bal + cum + olow + low <= floor:
                return "FAIL", k + 1
            opn.append((t["exit_t"], pnl, low, (t["risk"] + SLIP) * PV * q + COMM * q))
        cum += sum(o[1] for o in opn)
        bal += cum
        if bal <= floor:
            return "FAIL", k + 1
        peak = max(peak, bal)
        floor = min(max(floor, peak - LMo.MLL), LMo.LOCK)
        if bal >= LMo.TGT:
            return "PASS", k + 1
    return "OPEN", min(len(seq), horizon)


def evals(U, span, n_mc=1000):
    U = LMo.wk_mults(U)
    by = collections.defaultdict(list)
    for t in U:
        by[t["day"]].append(t)
    ss = LMo.sess_in(span)
    B = [sorted(by.get(s, []), key=lambda t: t["entry_t"]) for s in ss]
    z = len(ss)
    ex = [run_eval(list(range(k, z)), B) for k in range(0, z - 10 + 1)]
    rng = np.random.default_rng(11)
    mc = []
    for _ in range(n_mc):
        s = []
        while len(s) < 10:
            b = int(rng.integers(0, z - 5 + 1))
            s.extend(range(b, b + 5))
        mc.append(run_eval(s[:10], B))
    f = lambda R, r: round(100.0 * sum(1 for x in R if x[0] == r) / max(1, len(R)), 1)
    pas = [d for r, d in ex if r == "PASS"]
    return {"p10": f(ex, "PASS"), "f10": f(ex, "FAIL"), "pass_med": float(np.median(pas)) if pas else None,
            "mc_p10": f(mc, "PASS"), "mc_f10": f(mc, "FAIL"), "n_starts": len(ex)}


def score(U):
    T = money_trades(U)
    o = {s: LMo.stats(T, s) for s in ("H1", "H2", "2026", "ref")}
    for s in ("H1", "H2"):
        o[s].update(evals(U, s))
    return o


def line(key, o):
    f = lambda s: (f"{o[s]['n']:3d} {o[s]['tpw']:4.2f}/wk PF {o[s]['pf']} {o[s]['net']:+7,} DD {o[s]['dd']:+,} "
                   f"2wk {o[s]['p10']}/{o[s]['f10']} mc {o[s]['mc_p10']}/{o[s]['mc_f10']}")
    return f"{key[:58]:58s} H1[{f('H1')}] H2[{f('H2')}] ref PF {o['ref']['pf']} {o['ref']['net']:+,}"


def put(key, U, meta=None, quiet=False):
    o = score(U)
    o["meta"] = meta or {}
    _RES[key] = o
    _U[key] = U
    if not quiet:
        print(line(key, o), flush=True)
    return o


def dump():
    old = json.load(open(OUT)) if os.path.exists(OUT) else {}
    old.update(_RES)
    json.dump(old, open(OUT, "w"), indent=1, default=float)


def verdict_ok(key, bkey="base (live LIT)"):
    """Adopt test: both halves gain $ AND the 2-week pass, H2 2-week fail not up by more than 1.5 points."""
    o, b = _RES[key], _RES[bkey]
    return all(o[s]["net"] > b[s]["net"] and o[s]["p10"] >= b[s]["p10"] for s in ("H1", "H2")) and \
        o["H2"]["f10"] <= b["H2"]["f10"] + 1.5 and o["H1"]["f10"] <= b["H1"]["f10"] + 1.5


def extra_set(Ub, Ux, lab, meta):
    """Score an extra source alone, + base at 1 a day (first fill wins) and as a 2nd trade a day."""
    put(lab + " | alone", Ux, {**meta, "combo": "alone"})
    put(lab + " | + live, 1 a day", LMo.merge([Ub, Ux], max_day=1), {**meta, "combo": "add1"})
    put(lab + " | + live, 2 a day", LMo.merge([Ub, Ux], max_day=2), {**meta, "combo": "add2"})


def novel(Ux, Ub):
    """Trades of the extra source on days the live LIT does not trade (diagnostic)."""
    bd = {u["day"] for u in Ub}
    return [u for u in Ux if u["day"] not in bd]


# ================================================================================================ families
def fam_base():
    T = LMo.run_on("nq", {})
    Ub = LMo.unit(T)
    put("base (live LIT)", Ub, {"family": "base"})
    _S["Tb"] = T
    return Ub


P_RELAX = {
    "live filters": {},
    "depth 0.25": {"depth": 0.25},
    "depth 0": {"depth": 0.0},
    "no idm": {"idm_a": None},
    "depth 0.25 no idm": {"depth": 0.25, "idm_a": None},
}


def fam_msnr(Ub, grid=True):
    out = []
    sets = [("1h", ("A", "V")), ("1h", ("QM",)), ("1h", ("F",)), ("4h", ("A", "V")), ("4h", ("QM",)), ("4h", ("F",)),
            ("15m", ("A", "V")), ("15m", ("QM",)), ("1h", ("A", "V", "QM", "F")), ("4h", ("A", "V", "QM", "F"))]
    for tf, kinds in sets:
        L = levels(tf, kinds)
        tag = f"msnr_{tf}_{''.join(kinds)}"
        Mx, C = pool(tag, L)
        for pl, P in (P_RELAX.items() if grid else [("live filters", {})]):
            T, Ux = run_m(Mx, C, P, tag)
            lab = f"MSNR {tf} {'+'.join(kinds)} standalone, {pl}"
            meta = {"family": "msnr", "tf": tf, "kinds": kinds, "P": P}
            o = put(lab + " | alone", Ux, {**meta, "combo": "alone"})
            out.append((lab, Ux))
            nv = novel(Ux, Ub)
            o["meta"]["novel_2026"] = sum(1 for u in nv if u["day"] >= "2026")
            if o["H1"]["n"] >= 4:
                put(lab + " | + live, 1 a day", LMo.merge([Ub, Ux], max_day=1), {**meta, "combo": "add1"})
                put(lab + " | + live, 2 a day", LMo.merge([Ub, Ux], max_day=2), {**meta, "combo": "add2"})
    return out


def fam_msnrlit(Ub):
    """MSNR levels added to the LIT levels: a sweep of either is LIT liquidity (live filters otherwise)."""
    for tf, kinds in (("1h", ("A", "V")), ("1h", ("QM",)), ("4h", ("A", "V", "QM")), ("1h", ("A", "V", "QM", "F"))):
        L = levels(tf, kinds)
        tag = f"msnrlit_{tf}_{''.join(kinds)}"
        Mx, C = pool(tag, L, keep_lit=True)
        T, Ux = run_m(Mx, C, {}, tag)
        put(f"LIT + MSNR {tf} {'+'.join(kinds)} levels as liquidity (replaces live)", Ux, {"family": "msnrlit", "tf": tf, "kinds": kinds})


# ---------------------------------------------------------------- IDM into an order block
def ob_blocks(tf):
    from tools import lit_ob as TOB
    M = base()[0]
    return TOB.blocks(M, tf, None, "body")


def fam_idmob(Ub):
    M = base()[0]
    for tfs in (("15m",), ("1h",), ("15m", "1h")):
        obs = [ob for tf in tfs for ob in ob_blocks(tf)]
        for near in (1.0, 2.0):
            L = E.idm_ob_levels(M, obs, near=near)
            for q, lv in enumerate(L):
                lv["name"] = f"idm{lv['tf']}#{q}"
                lv["cls"] = "idm"
            E.add_touch(M, L)
            tag = f"idmob_{'-'.join(tfs)}_{near}"
            Mx, C = pool(tag, L, cls="idm", max_age=576)
            byname = {lv["name"]: lv for lv in L}
            for tol in (0.0, 0.5):
                Ck = []
                for z in C:
                    hit = False
                    for nm in z["swept"]:
                        lv = byname.get(nm)
                        if not lv:
                            continue
                        ob = lv["ob"]
                        ext = z["ext_d"] * z["dir"]
                        if z["dir"] == 1 and ext <= ob["top"] + tol * z["atr_ext"] and ext >= ob["bot"] - 0.5 * z["atr_ext"]:
                            hit = True
                        if z["dir"] == -1 and ext >= ob["bot"] - tol * z["atr_ext"] and ext <= ob["top"] + 0.5 * z["atr_ext"]:
                            hit = True
                    if hit:
                        Ck.append(z)
                for pl, P in (("live filters, no idm gate", {"idm_a": None}), ("depth 0.25, no idm gate", {"idm_a": None, "depth": 0.25}),
                              ("depth 0, no idm gate", {"idm_a": None, "depth": 0.0})):
                    T, Ux = run_m(Mx, Ck, P, tag)
                    lab = f"IDM->OB {'+'.join(tfs)} near {near} ATR, into block tol {tol}, {pl}"
                    meta = {"family": "idmob", "tfs": tfs, "near": near, "tol": tol, "P": P}
                    o = put(lab + " | alone", Ux, {**meta, "combo": "alone"})
                    if o["H1"]["n"] >= 4:
                        put(lab + " | + live, 1 a day", LMo.merge([Ub, Ux], max_day=1), {**meta, "combo": "add1"})
                        put(lab + " | + live, 2 a day", LMo.merge([Ub, Ux], max_day=2), {**meta, "combo": "add2"})


# ---------------------------------------------------------------- confluence tags on LIT candidates
TAGS = ["ob15", "ob1h", "smt", "msnr", "idm2", "bu", "major", "story"]


def tags():
    """Confluence tags of every LIT candidate (closed bars <= the trigger bar only)."""
    if "tags" in _S:
        return _S["tags"]
    p = os.path.join(CACHE, f"litent_tags_v1_{rl._data_key().replace(':', '_')}.pkl")
    if os.path.exists(p):
        _S["tags"] = pickle.load(open(p, "rb"))
        return _S["tags"]
    from tools import lit_ob as TOB
    from tools import lit_adv_audit as AA
    M, C, _, _ = base()
    Es = AA.es_bars(M)
    st4 = E.storyline(M, "4h")
    LV = [lv for tf in ("1h", "4h") for lv in levels(tf, ("A", "V", "QM"))]
    by_side = {}
    for sd in ("low", "high"):
        X = sorted([lv for lv in LV if lv["side"] == sd], key=lambda x: x["touch"])
        by_side[sd] = (X, np.array([x["touch"] for x in X]))
    out = {}
    for z in C:
        d, i, ee, sb = z["dir"], z["i"], z["ext_i"], z["sweep_i"]
        key = (z["day"], z["i"], d)
        g = {}
        g["ob15"] = bool(TOB.poi_hits(M, z, {"tfs": ["15m"], "tol": 0.5}))
        g["ob1h"] = bool(TOB.poi_hits(M, z, {"tfs": ["1h"], "tol": 0.5}))
        try:
            g["smt"] = AA.smt_flags(M, Es, z)["state"] == "smt"
        except Exception:
            g["smt"] = False
        X, ta = by_side["low" if d == 1 else "high"]
        a = int(np.searchsorted(ta, sb - 12)); b = int(np.searchsorted(ta, ee, side="right"))
        g["msnr"] = any(lv["ki"] < lv["touch"] and 0.0 <= lv["px"] * d - z["ext_d"] <= 1.0 * z["atr_ext"] for lv in X[a:b])
        g["idm2"] = sum(1 for dd, aa in z["idm_a"] if dd <= 1.0 and aa <= 36) >= 2
        g["bu"] = "buildup" in z["swept_cls"]
        g["major"] = bool(set(z["swept_cls"]) & {"pd", "pw", "pm", "gap"})
        g["story"] = int(st4[i]) == d
        out[key] = g
    pickle.dump(out, open(p, "wb"))
    _S["tags"] = out
    return out


def grade(g, use=TAGS):
    return sum(1 for t in use if g.get(t))


def fam_stack(Ub):
    M, C, _, _ = base()
    G = tags()
    live_ok = lambda z: lit.setup_ok(z, LIVE, None)
    Tb = _S["Tb"]
    bexit = {t["day"]: t["exit_t"] for t in Tb}
    for use_lab, use in (("all 8", TAGS), ("no story/major", ["ob15", "ob1h", "smt", "msnr", "idm2", "bu"])):
        for n in (2, 3, 4):
            for pl, P in (("depth 0.25 disp 0.5 no idm", {"depth": 0.25, "disp": 0.5, "idm_a": None}),
                          ("depth 0.25 no idm", {"depth": 0.25, "idm_a": None}),
                          ("no idm", {"idm_a": None})):
                Cs = [z for z in C if not live_ok(z) and grade(G[(z["day"], z["i"], z["dir"])], use) >= n]
                T, Ux = run_m(M, Cs, P, "stack")
                lab = f"stacked >= {n} of {use_lab}, rejected-by-live setups, {pl}"
                meta = {"family": "stack", "n": n, "use": use, "P": P}
                o = put(lab + " | alone", Ux, {**meta, "combo": "alone"})
                if o["H1"]["n"] >= 4:
                    put(lab + " | + live, 1 a day", LMo.merge([Ub, Ux], max_day=1), {**meta, "combo": "add1"})
                    put(lab + " | + live, 2 a day", LMo.merge([Ub, Ux], max_day=2), {**meta, "combo": "add2"})
        # live-filter setups with >= n confluences as a 2nd trade once the day's trade has ended
        for n in (2, 3, 4):
            Cs = [z for z in C if live_ok(z) and grade(G[(z["day"], z["i"], z["dir"])], use) >= n
                  and z["day"] in bexit and int(M.t[z["entry_i"]]) >= bexit[z["day"]]]
            T, Ux = run_m(M, Cs, {}, "stack2")
            lab = f"2nd trade: live-filter setup with >= {n} of {use_lab} after the day's trade"
            meta = {"family": "stack2", "n": n, "use": use}
            put(lab + " | alone", Ux, {**meta, "combo": "alone"}, quiet=True)
            put(lab + " | + live, 2 a day", LMo.merge([Ub, Ux], max_day=2), {**meta, "combo": "add2"})


def tag_trades(Ub, T):
    """unit records of the live trades with their candidate tags."""
    G = tags()
    TT = [t for t in T if t["qty"]]
    assert len(TT) == len(Ub)
    out = []
    for u, t in zip(Ub, TT):
        out.append(dict(u, g=G.get((t["day"], t["i"], t["dir"]), {})))
    return out


def tag_table(Ug):
    """Per tag: n, win, avg R per micro (pts / risk) in H1 / H2 with vs without (unit records at 1 micro)."""
    rows = {}
    for tg in TAGS + ["grade>=3", "grade<=1"]:
        r = {}
        for sp in ("H1", "H2", "ref"):
            a, z = LMo.SPAN[sp]
            X = [u for u in Ug if a <= u["day"] <= z]
            if tg.startswith("grade"):
                f = (lambda u: grade(u["g"]) >= 3) if tg == "grade>=3" else (lambda u: grade(u["g"]) <= 1)
            else:
                f = lambda u, tg=tg: bool(u["g"].get(tg))
            w = [u["pts"] / u["risk"] for u in X if f(u)]
            wo = [u["pts"] / u["risk"] for u in X if not f(u)]
            r[sp] = {"n": len(w), "avgR": round(float(np.mean(w)), 3) if w else None,
                     "n_wo": len(wo), "avgR_wo": round(float(np.mean(wo)), 3) if wo else None}
        rows[tg] = r
    return rows


def fam_grade(Ub):
    T = _S["Tb"]
    Ug = tag_trades(Ub, T)
    tt = tag_table(Ug)
    _RES["_tag_table"] = tt
    for tg, r in tt.items():
        print(f"  {tg:9s} " + "  ".join(f"{sp}: {r[sp]['n']:3d} {r[sp]['avgR']} vs {r[sp]['n_wo']:3d} {r[sp]['avgR_wo']}" for sp in ("H1", "H2", "ref")))
    rules = []
    for use_lab, use in (("all 8", TAGS), ("ob/smt/msnr/idm2/bu", ["ob15", "ob1h", "smt", "msnr", "idm2", "bu"])):
        for hi_n, hi_m in ((3, 1.5), (3, 1.25), (4, 1.5)):
            rules.append((f"{use_lab}: grade >= {hi_n} x{hi_m}", use, lambda g, use=use, n=hi_n, m=hi_m: m if grade(g, use) >= n else 1.0))
        for lo_n, lo_m in ((0, 0.5), (1, 0.5), (1, 0.75), (0, 0.0)):
            rules.append((f"{use_lab}: grade <= {lo_n} x{lo_m}", use, lambda g, use=use, n=lo_n, m=lo_m: m if grade(g, use) <= n else 1.0))
        rules.append((f"{use_lab}: >= 3 x1.5, <= 0 x0.5", use, lambda g, use=use: 1.5 if grade(g, use) >= 3 else 0.5 if grade(g, use) == 0 else 1.0))
    for tg in TAGS:
        rules.append((f"tag {tg}: x1.5 with", None, lambda g, tg=tg: 1.5 if g.get(tg) else 1.0))
        rules.append((f"tag {tg}: x0.5 without", None, lambda g, tg=tg: 1.0 if g.get(tg) else 0.5))
    for lab, use, fn in rules:
        U = [dict(u, g_m=fn(u["g"])) for u in Ug]
        put("grade size: " + lab, U, {"family": "grade"})


# ================================================================================================ lookahead + check
class _Cut:
    """A Market-like view of the first n 5m bars (for the lookahead test)."""

    def __init__(self, M, n):
        self.t, self.o, self.h, self.l, self.c = M.t[:n], M.o[:n], M.h[:n], M.l[:n], M.c[:n]
        self.mod, self.day_of, self.n = M.mod[:n], M.day_of[:n], n


def lookahead(cuts=12, seed=5):
    M = base()[0]
    rng = np.random.default_rng(seed)
    idx = rng.integers(int(M.n * 0.9), M.n - 100, cuts)
    bad = 0
    for tf in ("15m", "1h", "4h"):
        full = E.msnr_levels(M, tf)
        for n in idx:
            n = int(n)
            Mc = _Cut(M, n)
            cut = E.msnr_levels(Mc, tf)
            a = {(x["side"], round(x["px"], 2), x["ki"], x["kind"]) for x in full if x["ki"] < n - 1}
            b = {(x["side"], round(x["px"], 2), x["ki"], x["kind"]) for x in cut if x["ki"] < n - 1}
            # a level known before the cut must be found on the cut data, and vice versa
            if a != b:
                bad += 1
                print(tf, n, "diff", len(a - b), len(b - a), list(a ^ b)[:3])
        st_full = E.storyline(M, tf)
        for n in idx[:4]:
            n = int(n)
            st_cut = E.storyline(_Cut(M, n), tf)
            # storyline at bars < n is known from closed candles only
            m = int(np.flatnonzero(np.diff(M.day_of[:n]))[-1]) if n else 0
            if not np.array_equal(st_full[:m], st_cut[:m]):
                bad += 1
                print(tf, "storyline diff at cut", n)
    print("lookahead test:", "OK" if bad == 0 else f"{bad} mismatches", f"({cuts} cuts x 3 tfs)")
    return bad


def check():
    T = LMo.run_on("nq", {})
    r = rl.load("lit_live")
    Tr = [dict(zip(r["trade_cols"], a)) for a in r["trades"]]
    a = {(t["day"], int(t["entry_t"])): round(t["pnl"], 2) for t in Tr if t["day"] >= "2026"}
    b = {(t["day"], int(t["entry_t"])): round(t["pnl"], 2) for t in T if t["day"] >= "2026"}
    same = sum(1 for k in a if k in b and abs(a[k] - b[k]) < 0.02)
    print(f"lit_live 2026 {len(a)} {sum(a.values()):+,.0f} | here {len(b)} {sum(b.values()):+,.0f} | identical {same}")
    U = LMo.unit(T)
    o, o2 = score(U), LMo.score(U)
    print("eval same as lit_more:", all(o[s][k] == o2[s][k] for s in ("H1", "H2") for k in ("p10", "f10", "net")),
          {s: (o[s]["p10"], o[s]["f10"], o[s]["net"]) for s in ("H1", "H2")})
    # LevelMarket with the LIT levels only == the base candidates
    M, C, _, _ = base()
    Mx = E.LevelMarket(M, [], keep_lit=True)
    C2 = lit.candidates(Mx, ref="cisd")
    print("LevelMarket(keep_lit, no extra) candidates identical:", len(C2) == len(C) and all(
        (x["day"], x["i"], x["dir"], x["swept"]) == (y["day"], y["i"], y["dir"], y["swept"]) for x, y in zip(C, C2)))
    lookahead()


# ================================================================================================ save
def save(picks):
    """picks: [(run id, result key, status, family)]."""
    for rid, key, status, fam in picks:
        U = _U[key]
        MT = money_trades(U)
        T = []
        for t in MT:
            ru = t["risk"] * PV * t["qty"]
            T.append({"day": t["day"], "entry_t": t["entry_t"], "exit_t": t["exit_t"], "dir": t["dir"], "r": round(t["pnl"] / ru, 3) if ru else 0.0,
                      "pnl": t["pnl"], "low": t["low"], "risk_pts": round(t["risk"], 2), "qty": t["qty"], "risk_usd": round(ru, 2),
                      "half": t["wk_m"] < 1, "exit": t["exit"], "trigger": f"LIT-{t['src']}", "mfe": None, "mae": None,
                      "bars_held": None, "regime": "", "mult": round(t["wk_m"] * t.get("g_m", 1.0), 3)})
        o = _RES[key]
        h = lambda s: (f"{s}: {o[s]['n']} trades, {o[s]['tpw']}/wk, {o[s]['wk2']}% weeks 2+, win {o[s]['win']}%, PF {o[s]['pf']}, "
                       f"net ${o[s]['net']:+,} (${o[s]['per_month']:,}/mo), DD ${o[s]['dd']:,}; live eval sizing 2-wk pass/fail "
                       f"{o[s]['p10']}/{o[s]['f10']} (MC {o[s]['mc_p10']}/{o[s]['mc_f10']})")
        verdict = "; ".join(h(s) for s in ("H1", "H2")) + f"; 2021-25 reference (5m) PF {o['ref']['pf']} ${o['ref']['net']:+,}."
        meta = {k: (list(v) if isinstance(v, tuple) else v) for k, v in o.get("meta", {}).items()}
        rl.save(rid, "LIT new entries: " + key, fam, "Owner 2026-10-19: add confluences and new LIT entry types (MSNR, IDM into "
                "order blocks, stacked confluence, smart money trap, build-ups); 3+ LIT trades a week.", params={"variant": key, **meta},
                sizing={"money": "LIT rule $800/20 + weekly stop, $1.90/micro", "eval": "lit_sizing two_week (10 sessions) then safe_eval"},
                trades=T, scored=rl.score(T, SESS), status=status, verdict=verdict,
                notes="tools/lit_new_entries.py, engine/lit_entries.py. Results: research/lit/new_entries.json",
                writeup="lit-new-entries", tags=["lit", "lit_ent"])
        print("saved", rid, flush=True)


def all_():
    Ub = fam_base()
    fam_msnr(Ub); dump()
    fam_msnrlit(Ub); dump()
    fam_idmob(Ub); dump()
    fam_stack(Ub); dump()
    fam_grade(Ub); dump()
    return Ub


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        check()
    elif cmd == "all":
        all_()
    elif cmd in ("msnr", "msnrlit", "idmob", "stack", "grade"):
        Ub = fam_base()
        globals()["fam_" + cmd](Ub)
        dump()
