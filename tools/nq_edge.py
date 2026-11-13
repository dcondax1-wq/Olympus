"""NQ edge sprint (2026-11-13, owner: "build everything so that it's profitable, find every edge, make me money, mainly NQ").
research/writeups/nq-edge-2026-11-13.md. Paper research only: engine/, live_model*.json and second_model.json untouched (the
room guard is a research wrapper around engine.sizing.lit_qty inside this process only).

Ideas (hypotheses in the write-up, written before any test):
  L1 room guard (Zlarior eval): room to the trailing floor < r0 -> one trade risks at most x of the room (a full stop-out incl.
     1 tick + $1.90 a micro); 1 micro is still allowed when it fits the live cap (mode floor1) or the trade is skipped (skip)
  L2 two_week after session 10 (two_week_until 999) re-measured
  L3 option-expiry calendar size (OPEX Friday / OPEX week / quarterly week / roll week / month-end) x0.5, LIT size + placebo
  L4 ATLAS agreement as LIT size (an ATLAS member entered the same day before LIT's fill: same side x1.25, other side x0.75)
  A1 room guard on ATLAS's 25K, A2 calendar size on ATLAS (tools/atlas_v2 verdict: 2026 H1 AND H2 better, 2025 / 2021-24 ok)
  S1 from today's thin eval states (Zlarior room ~$1,145, ATLAS room ~$822): pass / fail odds per sizing

Scoring: tools/lit_edge.evaluate (exact live LIT trades; LIT size rule H1 / H2 / 2021-25, the real-order eval windows +
Monte Carlo on the live two_week sizing, the funded 50K $ a month), tools/uprisk (eval Monte Carlo H1 / H2 / 2021-25 and the
whole account slot: eval -> funded -> payouts net of every $91.80 eval, 1,000 six-month paths), tools/atlas_v2.score (ATLAS
account-B rules on the 25K, back-to-back eval paths net of $63 fees from every 5th session).

    python -X utf8 tools/nq_edge.py lit       # L1-L4 + S1 (Zlarior) -> research/lit/nq_edge_lit.json
    python -X utf8 tools/nq_edge.py atlas     # A1, A2 + S1 (ATLAS)  -> research/second/nq_edge_atlas.json
    python -X utf8 tools/nq_edge.py save      # runs nq_edge_* in the run library
"""
from __future__ import annotations

import collections
import copy
import datetime as dt
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import logging  # noqa: E402
logging.getLogger("engine.sizing").setLevel(logging.ERROR)
from engine import sizing as SZ  # noqa: E402
from tools import lit_edge as E  # noqa: E402
from tools import uprisk as UP  # noqa: E402
from tools import runlib as rl  # noqa: E402

OUT_L = os.path.join(ROOT, "research", "lit", "nq_edge_lit.json")
OUT_A = os.path.join(ROOT, "research", "second", "nq_edge_atlas.json")
N_MC = int(os.environ.get("NQE_N", "1000"))

# ================================================================================================ the room guard (research)
PROTECT: dict = {}
_ORIG = SZ.lit_qty


def loss1(risk):
    """A full stop-out of 1 micro: stop + 1 tick at $2 a point + $1.90 (the live cap invariant)."""
    return (float(risk) + SZ.TW_SLIP) * SZ.TW_PV + SZ.TW_COMM


def lit_qty_guard(m0, trade, cfg=None, room=None, state=None, **kw):
    out = _ORIG(m0, trade, cfg, room=room, state=state, **kw)
    P = PROTECT
    if not P or out.get("qty", 0) <= 0 or (cfg or {}).get("mode") not in ("two_week", "eval", "safe_eval"):
        return out
    rm = room if room is not None else (state or {}).get("room")
    if rm is None or float(rm) >= P["r0"]:
        return out
    if P.get("from") and int((state or {}).get("session") or 0) < int(P["from"]):
        return out
    l1 = loss1(trade.get("risk_pts") or trade.get("risk"))
    cap = int(P["x"] * max(0.0, float(rm)) / l1 + 1e-9)
    if cap < 1:
        cap = 1 if P.get("mode", "floor1") == "floor1" else 0
    if cap < out["qty"]:
        out = {**out, "qty": cap, "reasons": list(out.get("reasons") or []) + [f"room guard {P}"]}
    return out


SZ.lit_qty = lit_qty_guard


class guard:
    def __init__(self, P):
        self.P = P or {}

    def __enter__(self):
        PROTECT.clear()
        PROTECT.update(self.P)

    def __exit__(self, *a):
        PROTECT.clear()


# ================================================================================================ calendar facts
def third_friday(y, m):
    d = dt.date(y, m, 15)
    return d + dt.timedelta(days=(4 - d.weekday()) % 7)


def cal_facts(sessions):
    """day -> set of calendar tags, known before the day opens: opex (3rd Friday; the session before when it is not a
    session), opex_wk (its ISO week), quad_wk (OPEX week of Mar / Jun / Sep / Dec), roll_wk (the week before the quarterly
    expiry week: the roll Thursday is 8 days before the expiry), mend (the last session of the month)."""
    S = sorted(sessions)
    Sset = set(S)
    out = collections.defaultdict(set)
    years = sorted({int(d[:4]) for d in S})
    for y in years:
        for m in range(1, 13):
            f = third_friday(y, m)
            fd = f.isoformat()
            while fd not in Sset and fd > S[0]:
                f = f - dt.timedelta(days=1)
                fd = f.isoformat()
                if (third_friday(y, m) - f).days > 4:
                    break
            if fd in Sset:
                out[fd].add("opex")
            wk = third_friday(y, m).isocalendar()[:2]
            prev = (third_friday(y, m) - dt.timedelta(days=7)).isocalendar()[:2]
            for d in S:
                if not d.startswith(f"{y}-"):
                    continue
                w = dt.date.fromisoformat(d).isocalendar()[:2]
                if w == wk:
                    out[d].add("opex_wk")
                    if m in (3, 6, 9, 12):
                        out[d].add("quad_wk")
                if m in (3, 6, 9, 12) and w == prev:
                    out[d].add("roll_wk")
    for a, b in zip(S, S[1:] + ["9999-99-99"]):
        if a[:7] != b[:7]:
            out[a].add("mend")
    return out


CAL_TAGS = ("opex", "opex_wk", "quad_wk", "roll_wk", "mend")


# ================================================================================================ Zlarior scoring
_P = {}


def paths(sp, length):
    k = (sp, length, N_MC)
    if k not in _P:
        _P[k] = UP.mc_paths(E.ctx()["S_up"], sp, N_MC, length=length)
    return _P[k]


Z_STATES = {   # today's thin Zlarior eval (TONIGHT_EVAL.md: $1,145 of $2,000 left), before / after eval session 10
    "z_room1145_s5": {"bal": -855.0, "peak": 0.0, "s": 5},
    "z_room1145_s15": {"bal": -855.0, "peak": 0.0, "s": 15},
}


def state_mc(BY, cfg, st, sp, horizon=40, plan="builder50k"):
    """Odds from an eval already in progress: balance / peak / sessions used -> pass / fail (+ stuck) within 10 more
    sessions and within `horizon`, median sessions to pass (Monte Carlo of 5-session blocks of the span)."""
    R = []
    for seq in paths(sp, horizon):
        e = UP.Eval(cfg, plan)
        e.bal, e.peak = st["bal"], st["peak"]
        e.floor = min(max(-e.E["mll"], e.peak - e.E["mll"]), e.E["lock"])
        e.s = st["s"] - 1
        out, used = "open", horizon
        for k, si in enumerate(seq[:horizon]):
            r = e.step(BY[si])
            if r:
                out, used = r, k + 1
                break
        R.append((out, used))
    n = len(R)
    pas = [u for o, u in R if o == "pass"]
    return {"p10": round(100.0 * sum(1 for u in pas if u <= 10) / n, 1),
            "f10": round(100.0 * sum(1 for o, u in R if o in ("fail", "stuck") and u <= 10) / n, 1),
            "p_ever": round(100.0 * len(pas) / n, 1),
            "f_ever": round(100.0 * sum(1 for o, u in R if o in ("fail", "stuck")) / n, 1),
            "pass_med": float(np.median(pas)) if pas else None}


def z_score(U=None, mfn=None, ecfg_var=None, P=None, fund=True, state=True, slot=True):
    """Everything for one Zlarior variant: trades U (or the live ones re-sized by mfn), eval cfg changes (uprisk.ecfg_of keys),
    room guard P."""
    with guard(P):
        cfg = copy.deepcopy(E.A.CFG)
        if ecfg_var:
            for k in ("two_week_until", "after_mode", "safe_cap"):
                if k in ecfg_var:
                    cfg[k] = ecfg_var[k]
            if "room_f" in ecfg_var:
                cfg["two_week"] = {**cfg["two_week"], "room_f": ecfg_var["room_f"]}
        o, U, L = E.evaluate(mfn=mfn, fund=fund, eval_cfg=cfg if ecfg_var else None, U=U)
        BY = E.funded_by(U)
        ec = UP.ecfg_of(ecfg_var or {})
        o["mc"] = {sp: UP.eval_mc(BY, paths(sp, 60), ec) for sp in ("H1", "H2", "REF")}
        if slot:
            o["slot"] = {sp: UP.life(BY, paths(sp, UP.LEN), ec, E.FUND_LIVE) for sp in ("H1", "H2", "REF")}
        if state:
            o["state"] = {nm: {sp: state_mc(BY, ec, st, sp) for sp in ("H1", "H2", "REF")} for nm, st in Z_STATES.items()}
    return o, U, L


def z_line(nm, o, b=None):
    ev, mc = o["eval"], o["mc"]
    t = (f"{nm:28s} LIT $/mo {o['lit']['H1']['per_month']:>5}/{o['lit']['H2']['per_month']:>5}/{o['lit']['2021-25']['per_month']:>4} | "
         f"evalpath $/mo {ev['H1']['per_month']:>5}/{ev['H2']['per_month']:>5} win2w {ev['H1']['p10']}/{ev['H1']['f10']} "
         f"{ev['H2']['p10']}/{ev['H2']['f10']} | MC2w {mc['H1']['p10']}/{mc['H1']['f10']} {mc['H2']['p10']}/{mc['H2']['f10']} "
         f"{mc['REF']['p10']}/{mc['REF']['f10']} med {mc['H1']['pass_med']}/{mc['H2']['pass_med']}")
    if "slot" in o:
        t += f" | slot $/mo {o['slot']['H1']['net_m']}/{o['slot']['H2']['net_m']}/{o['slot']['REF']['net_m']}"
    if "fund" in o:
        t += f" | fund {o['fund']['H1']['per_month']}/{o['fund']['H2']['per_month']}/{o['fund']['REF']['per_month']}"
    if "state" in o:
        for k, s in o["state"].items():
            t += f" | {k[-3:]} p10/f10 {s['H1']['p10']}/{s['H1']['f10']} {s['H2']['p10']}/{s['H2']['f10']} {s['REF']['p10']}/{s['REF']['f10']}"
    return t


def z_compact(o):
    c = E.short(o)
    for k in ("mc", "slot", "state", "placebo", "n_tilted", "info"):
        if k in o:
            c[k] = o[k]
    return c


def z_gate_size(o, b):
    """Sizing-only (eval) candidates: the account slot $ a month up in H1 AND H2 (2021-25 not down by more than $10), the
    2-week fail rate not up (MC and real-order windows, H1 and H2), the 2-week pass not down by more than 1 point."""
    ok = all(o["slot"][h]["net_m"] > b["slot"][h]["net_m"] for h in ("H1", "H2"))
    ok &= o["slot"]["REF"]["net_m"] >= b["slot"]["REF"]["net_m"] - 10
    ok &= all(o["mc"][h]["f10"] <= b["mc"][h]["f10"] and o["eval"][h]["f10"] <= b["eval"][h]["f10"] for h in ("H1", "H2"))
    ok &= all(o["mc"][h]["p10"] >= b["mc"][h]["p10"] - 1.0 for h in ("H1", "H2"))
    return bool(ok)


def atlas_lit_agree(up, dn, mode="both"):
    """mfn for LIT: an ATLAS member's research candidate (EMA / MACD / S/R units) entered the same day strictly before LIT's
    fill: same side -> up, only the other side -> dn."""
    from tools import ab_edge as AE
    V2, A, M, EAB = AE.atlas_libs()
    V = V2.V_()
    by = collections.defaultdict(list)
    for nm in ("EMA", "MD", "SR"):
        for u in A.member_units(nm, V):
            by[u["day"]].append((int(u["entry_t"]), int(u["dir"])))

    def f(t, r):
        prev = [d for e, d in by.get(t["day"], ()) if e < int(t["entry_t"])]
        if not prev:
            return 1.0
        if any(d == t["dir"] for d in prev):
            return up if mode in ("both", "up") else 1.0
        return dn if mode in ("both", "dn") else 1.0
    return f


def cmd_lit():
    t0 = time.time()
    res = {"built": time.strftime("%Y-%m-%d %H:%M"), "n_mc": N_MC, "rows": {}}
    base, U0, L0 = z_score()
    res["rows"]["base"] = z_compact(base)
    print(z_line("today", base), flush=True)

    def put(nm, o, kind):
        c = z_compact(o)
        c["kind"] = kind
        if kind == "size":
            c["gate"] = z_gate_size(o, base)
        else:
            s = E.short(o, base)
            c["gate"] = E.gate(s)
            c["d_lit"], c["d_eval"], c["d_f10"] = s["d_lit"], s["d_eval"], s["d_f10"]
            c["d_fund"] = s.get("d_fund")
        res["rows"][nm] = c
        print(z_line(nm, o) + ("  GATE" if c["gate"] else ""), flush=True)
        json.dump(res, open(OUT_L, "w"), indent=1, default=float)

    # ---- L1 room guard
    for r0 in (1000.0, 1200.0, 1500.0):
        for x in (0.4, 0.5, 0.6):
            o, _, _ = z_score(U=U0, P={"r0": r0, "x": x, "mode": "floor1"}, fund=False)
            put(f"guard_r{int(r0)}_x{x}", o, "size")
    o, _, _ = z_score(U=U0, P={"r0": 1200.0, "x": 0.5, "mode": "skip"}, fund=False)
    put("guard_r1200_x0.5_skip", o, "size")
    # ---- L2 two_week after session 10
    o, _, _ = z_score(U=U0, ecfg_var={"two_week_until": 999}, fund=False)
    put("tw_until_999", o, "size")
    o, _, _ = z_score(U=U0, ecfg_var={"two_week_until": 999}, P={"r0": 1200.0, "x": 0.5, "mode": "floor1"}, fund=False)
    put("tw_until_999+guard_r1200_x0.5", o, "size")
    # ---- L3 calendar size
    F = E.F
    C = cal_facts(F.SESS)
    for tag in CAL_TAGS:
        mfn = (lambda tg: (lambda t, r: 0.5 if tg in C.get(t["day"], ()) else 1.0))(tag)
        o, U, L = z_score(mfn=mfn, slot=False)
        o["n_tilted"] = {sp: sum(1 for u in U if u["m"] != 1.0 and E.SPANS[sp][0] <= u["day"] <= E.SPANS[sp][1]) for sp in E.SPANS}
        o["placebo"] = E.placebo(U, L0, n=200)
        put(f"cal_{tag}_x0.5", o, "tilt")
    # ---- L4 ATLAS agreement
    for nm, (up, dn, mode) in {"agree_125_075": (1.25, 0.75, "both"), "agree_only_15": (1.5, 1.0, "up"),
                               "disagree_only_05": (1.0, 0.5, "dn")}.items():
        o, U, L = z_score(mfn=atlas_lit_agree(up, dn, mode), slot=False)
        o["n_tilted"] = {sp: sum(1 for u in U if u["m"] != 1.0 and E.SPANS[sp][0] <= u["day"] <= E.SPANS[sp][1]) for sp in E.SPANS}
        o["placebo"] = E.placebo(U, L0, n=200)
        put(f"atlas_{nm}", o, "tilt")
    print(f"done in {time.time() - t0:.0f}s -> {OUT_L}", flush=True)


# ================================================================================================ ATLAS
A_STATES = {"a_room822_s8": {"bal": -178.0, "peak": 0.0, "s": 8}}


def a_libs():
    from tools import ab_edge as AE
    return AE, *AE.atlas_libs()


def a_state(V, st, sp, horizon=40, n=None, seed=29):
    """ATLAS 25K eval odds from a state (tools/atlas_v2.run_eval from bal / peak / session): 5-session blocks of the span."""
    AE, V2, A, M, EAB = a_libs()
    n = n or N_MC
    U = A.account_units(V)
    S = M.units()["sessions"]
    a, z = M.SPANS[sp]
    S = [d for d in S if a <= d <= z]
    rng = np.random.default_rng(seed)
    starts = np.arange(0, len(S) - 5 + 1)
    R = []
    V2.EV["min_room"] = float(V.get("min_room", 100.0))
    try:
        with A.Plan(V) as pl:
            by = M.by_day(U)
            for _ in range(n):
                seq = []
                while len(seq) < horizon:
                    j = int(rng.choice(starts))
                    seq += S[j:j + 5]
                bal, peak = st["bal"], st["peak"]
                floor = min(max(-M.MLL, peak - M.MLL), M.LOCK)
                out, used = "open", horizon
                for kk, day in enumerate(seq[:horizon]):
                    cum, recs, failed = M.play_day(by.get(day, ()), day, bal, floor, st["s"] + kk, "atlas", False, 2, None,
                                                   reserve=False)
                    if failed or bal + cum <= floor:
                        out, used = "fail", kk + 1
                        break
                    bal += cum
                    peak = max(peak, bal)
                    floor = min(max(floor, peak - M.MLL), M.LOCK)
                    if bal >= M.TGT:
                        out, used = "pass", kk + 1
                        break
                    if bal - floor < V2.EV["min_room"]:
                        out, used = "stuck", kk + 1
                        break
                R.append((out, used))
    finally:
        V2.EV["min_room"] = 100.0
    pas = [u for o, u in R if o == "pass"]
    return {"p10": round(100.0 * sum(1 for u in pas if u <= 10) / n, 1),
            "f10": round(100.0 * sum(1 for o, u in R if o in ("fail", "stuck") and u <= 10) / n, 1),
            "p_ever": round(100.0 * len(pas) / n, 1), "f_ever": round(100.0 * sum(1 for o, u in R if o != "pass" and o != "open") / n, 1),
            "pass_med": float(np.median(pas)) if pas else None}


A_KEYS = ("p10", "f10", "dead10", "dec10", "p15", "f15", "pass_med", "slow_pass", "mp_net_less_fees", "mp_per_eval",
          "mp_passes", "net", "per_month", "pf", "dd", "tpw", "sig_tpw", "sig_wk2", "wk2", "n", "fund_paid_3m")


def a_run(V, P=None, state=True):
    AE, V2, A, M, EAB = a_libs()
    with guard(P):
        o = V2.score(V)
        c = {s: {k: o[s].get(k) for k in A_KEYS} for s in o}
        if state:
            c["state"] = {nm: {sp: a_state(V, st, sp) for sp in ("H1", "H2", "2025", "2021-24")} for nm, st in A_STATES.items()}
    return o, c


def a_line(nm, c, v=None):
    f = lambda s: (f"{s} 2w {c[s]['p10']}/{c[s]['dead10']} med {c[s]['pass_med']} slot${c[s]['mp_net_less_fees']:+,} "
                   f"path {c[s]['net']:+,} PF {c[s]['pf']}")
    t = f"{nm:24s} " + " | ".join(f(s) for s in ("H1", "H2", "2025", "2021-24"))
    if "state" in c:
        for k, s in c["state"].items():
            t += " | state " + " ".join(f"{sp} {s[sp]['p10']}/{s[sp]['f10']}" for sp in s)
    if v is not None:
        t += f" | verdict {v}"
    return t


def cmd_atlas():
    t0 = time.time()
    AE, V2, A, M, EAB = a_libs()
    V0 = V2.V_()
    res = {"built": time.strftime("%Y-%m-%d %H:%M"), "rows": {}}
    ob, cb = a_run(V0)
    res["rows"]["base"] = cb
    print(a_line("today", cb), flush=True)

    def put(nm, o, c, fam=""):
        v = V2.verdict(o, ob, fam)
        c["verdict"] = v
        res["rows"][nm] = c
        print(a_line(nm, c, v), flush=True)
        json.dump(res, open(OUT_A, "w"), indent=1, default=float)

    # ---- A1 room guard on the 25K (half the 50K's dollars; the 25K's live room share is already 0.5, so x < 0.5)
    for r0 in (500.0, 600.0, 750.0):
        for x in (0.25, 0.33, 0.4):
            o, c = a_run(V0, {"r0": r0, "x": x, "mode": "floor1"})
            put(f"guard_r{int(r0)}_x{x}", o, c)
    # ---- A2 calendar size x0.5 (multipliers through ab_edge's member-unit hook)
    C = cal_facts(M.units()["sessions"])
    allu = A.account_units(V0)
    for tag in CAL_TAGS:
        um = {(u["src"], u["entry_t"]): 0.5 for u in allu if tag in C.get(u["day"], ())}
        key = f"nqe_cal_{tag}"
        AE._UM[key] = um
        V = {**V0, "um": key}
        o, c = a_run(V, state=False)
        c["n_tilted"] = len(um)
        c["placebo"] = AE.a_placebo(V0, um, n=40)
        put(f"cal_{tag}_x0.5", o, c)
    print(f"done in {time.time() - t0:.0f}s -> {OUT_A}", flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "lit"
    if cmd == "lit":
        cmd_lit()
    elif cmd == "atlas":
        cmd_atlas()
    elif cmd == "save":
        from tools import nq_edge_save
        nq_edge_save.main()
    else:
        raise SystemExit(__doc__)
