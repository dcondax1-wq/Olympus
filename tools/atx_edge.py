"""ATLAS edge, day session (2026-10-30 b, research/writeups/atlas-edge-2026-10-30b.md): make ATLAS (account B, MFFU Builder
25K) better without breaking its eval.

Builds on tools/ab_edge.py (last night: the stop hunts x0.5 + the noise-area day-hold member x0.5 = run
ab_atlas_na_hunts_lead, more money in all four spans but it FAILED the H1 2-week test 62.2 / 5.9 vs 65.5 / 0.8) and on
tools/atlas_v2.py (the account-B executor: need size via engine/account_b.qty, one position, max 2 a day, never opposite
LIT incl. its armed setups, $600 soft daily loss, stuck under $100) and tools/atlas_funded.py (the funded 25K: live funded
size, MFFU payouts via engine/funded_life.track, 5 payouts = graduated).

New here (pre-declared families, few values each):
  sched   the extra members (hunts SHA / SHT, NA day-hold NAD) by EVAL STATE: only from eval session N, a smaller weight
          before N, only while the room is >= $X, or only once funded (a "schedule" multiplier on the member weight,
          known at the entry: the session number and the room are the eval tracker's own numbers)
  slot    a whole-account slot simulator (eval -> funded -> payouts -> a new $63 eval after a pass is graduated / a
          fail / stuck): $ to the owner a month net of every eval bought, 300 block-bootstrap paths x 126 sessions per
          span (5-session blocks, seed 23, 2 sessions from pass to the first funded day, as blitz25k_size.life)
  funded  funded-stage money: buffer-first size (smaller until the trailing floor locks at start + $100, bigger after),
          the payout ask line, extra members on the funded account only
  win     per-member windows picked on 2026 H1 only (each member's weakest entry-hour / weekday bucket) with a
          shuffled-window control (the same number of trades dropped from random buckets of the same member)
  maxd    member-specific day limits (the NA day-hold / the hunts only as the day's first ATLAS trade, or never after a
          loss)

    python -X utf8 tools/atx_edge.py base      # today / hunts / lead reproduce + their slot $
    python -X utf8 tools/atx_edge.py sched     # family sched (eval-state schedule of the extra members)
    python -X utf8 tools/atx_edge.py funded    # family funded (slot simulator)
    python -X utf8 tools/atx_edge.py win       # family win + shuffled control
    python -X utf8 tools/atx_edge.py save      # runs atx_* in the run library
Paper research only: nothing in engine/, second_model.json or live_model*.json is touched.
"""
from __future__ import annotations

import collections
import copy
import datetime as dt
import itertools
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import logging  # noqa: E402
logging.getLogger("engine.sizing").setLevel(logging.ERROR)
from tools import ab_edge as E  # noqa: E402

OUT = os.path.join(ROOT, "research", "second")
MEM = ["EMA", "MD", "SR"]
XTRA = ["NAD", "SHA", "SHT"]
MONTHS = {"H1": 6.1, "H2": 3.71, "2025": 12.29, "2021-24": 38.76}        # sessions / 21 of each ATLAS span (ab_edge.MONTHS_A)
SPANS4 = ("H1", "H2", "2025", "2021-24")
PRICE = 63.0
_L = {}


# ================================================================================================ libs + the schedule patch
def libs():
    if "x" in _L:
        return _L["x"]
    V2, A, M, EAB = E.atlas_libs()
    U = M.units()
    if "NAD" not in U:
        U["NAD"] = E.nad_units()
    orig = A.q_variant
    cache = {}

    def qv(t, st, V, _orig=orig):
        sc = V.get("sched")
        if sc and t["src"] in sc["members"]:
            m = sched_mult(sc, st)
            if m <= 0:
                return 0
            k = (id(V), t["src"], m)
            hit = cache.get(k)
            if hit is None or hit[0] is not V:          # the cache holds V itself, so its id is never reused
                hit = (V, {**V, "w": {**(V.get("w") or {}), t["src"]: m}})
                cache[k] = hit
            V = hit[1]
        return _orig(t, st, V)
    A.q_variant = qv
    _L["x"] = (V2, A, M, EAB)
    return _L["x"]


def sched_mult(sc, st):
    """The extra member's weight at this entry from the eval tracker's own state: session number (1.. in the eval, 99 =
    funded) and the room to the floor ($, the day's closed P&L in)."""
    ses = int(st.get("session", 1))
    if ses >= 99:
        return float(sc.get("funded", sc.get("late", 0.5)))
    m = float(sc["early"]) if ses < int(sc.get("from", 1)) else float(sc.get("late", 0.5))
    if sc.get("room_min") is not None and float(st["room"]) < float(sc["room_min"]):
        m = float(sc.get("low", 0.0))
    if sc.get("room_max") is not None and float(st["room"]) >= float(sc["room_max"]):
        m = float(sc.get("high", m))
    if sc.get("no_after_loss") and float(st.get("cum", 0.0)) < 0:
        m = 0.0
    if sc.get("only_flat_day") and abs(float(st.get("cum", 0.0))) > 1e-9:
        m = 0.0
    return m


def V_(**kw):
    V2, A, M, EAB = libs()
    return V2.V_(**kw)


def today():
    return V_()


def hunts():
    return V_(members=MEM + ["SHA", "SHT"], w={"SHA": 0.5, "SHT": 0.5})


def lead(wn=0.5, wh=0.5, **kw):
    return V_(members=MEM + XTRA, w={"NAD": wn, "SHA": wh, "SHT": wh}, **kw)


# ================================================================================================ the slot simulator
_CAL = []


def cal(k):
    while len(_CAL) <= k:
        d = dt.date(2027, 1, 4) if not _CAL else dt.date.fromisoformat(_CAL[-1]) + dt.timedelta(days=1)
        while d.weekday() >= 5:
            d += dt.timedelta(days=1)
        _CAL.append(d.isoformat())
    return _CAL[k]


def mc_paths(S, n, length, seed=23, block=5):
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        s = []
        while len(s) < length:
            b = int(rng.integers(0, len(S) - block + 1))
            s.extend(S[b:b + block])
        out.append(s[:length])
    return out


class Eval:
    """One Builder 25K eval (tools/atlas_v2.run_eval, min room $100), stepped one session at a time."""

    def __init__(self, M):
        self.M, self.bal, self.peak, self.floor, self.k = M, 0.0, 0.0, -M.MLL, 0

    def step(self, L, day):
        M = self.M
        self.k += 1
        cum, recs, failed = M.play_day(L, day, self.bal, self.floor, self.k, "atlas", False, 2, None, reserve=False)
        if failed:
            return "fail", recs
        self.bal += cum
        if self.bal <= self.floor:
            return "fail", recs
        self.peak = max(self.peak, self.bal)
        self.floor = min(max(self.floor, self.peak - M.MLL), M.LOCK)
        if self.bal >= M.TGT:
            return "pass", recs
        if self.bal - self.floor < 100.0:
            return "stuck", recs
        return None, recs


class Funded:
    """One funded Builder 25K (tools/atlas_funded.account), stepped one session at a time; returns $ paid to the owner."""

    def __init__(self, M, P):
        self.M, self.P = M, P
        self.bal = self.peak = 0.0
        self.floor = -float(P["mll"])
        self.lock = float(P["lock"])
        self.days, self.pays, self.k, self.done, self.why = {}, {}, 0, False, None

    def step(self, L, day):
        from engine import funded_life as FL
        M, P = self.M, self.P
        cd = cal(self.k)
        self.k += 1
        from engine import sizing as SZ
        cyc = SZ.funded_cycle(self.days, 0.0, self.pays, plan=P)    # engine/multi_account.sizing_state's cycle facts (cons_aware)
        play = PLAY_FUNDED[0] or M.play_day
        cum, recs, failed = play(L, day, self.bal, self.floor, 99, "funded", False, 2, None, dll=float(P["dll"]), reserve=False,
                                 extra={"locked": self.floor >= self.lock - 1e-9, "payouts_n": len(self.pays),
                                        "cycle_target": cyc["cycle_target"], "cycle_prev": cyc["cycle_prev"]})
        if failed:
            self.done, self.why = True, "lost"
            return 0.0, recs
        self.bal += cum
        if recs:
            self.days[cd] = round(cum, 2)
        self.peak = max(self.peak, self.bal)
        self.floor = min(max(self.floor, self.peak - float(P["mll"])), self.lock)
        if self.bal - self.floor < float(P.get("fmin", 100.0)):     # stuck: the bot stops (live $100); "fmin" = give up earlier
            self.done, self.why = True, "stuck"
            return 0.0, recs
        tr = FL.track(self.days, self.pays, P, today=cd)
        if tr["status"] == "ready":
            amt = float(tr["max_request"])
            self.pays[cd] = amt
            self.bal -= amt
            self.floor = max(self.floor, self.lock)
            if len(self.pays) >= int(P["max_payouts"]):
                self.done, self.why = True, "grad"
            return amt * float(P["split"]), recs
        return 0.0, recs


FZ_LIVE = {}           # the live funded preset (60% of the room, $50-$750, ref 20 pts, a winner <= $1,000, skip breach)


def funded_q(fz, Vf):
    """Funded size: engine/sizing.funded_qty on the 25K preset (= engine/account_b.qty funded, tools/atlas_funded.q_live) with
    the variant's overrides: pre_pct / post_pct (room share before / after the floor locks at start + $100), post_max ($ cap
    after the lock), then the member weight (never above the funded size) and the soft daily loss guard."""
    from engine import sizing as SZ
    from tools import atlas_funded as AF
    V2, A, M, EAB = libs()
    base = dict(AF.CFG["funded"])
    if "max_win" in fz:
        base["max_win"] = fz["max_win"]
    if "cons_aware" in fz:                               # engine/sizing.funded_qty: cap the day's win so the 50% best-day rule holds
        base["cons_aware"] = fz["cons_aware"]
    pre ={**base, **({"pct": fz["pre_pct"]} if "pre_pct" in fz else {}), **({"pct_max_usd": fz["pre_max"]} if "pre_max" in fz else {})}
    post = {**base, **({"pct": fz["post_pct"]} if "post_pct" in fz else {}), **({"pct_max_usd": fz["post_max"]} if "post_max" in fz else {}),
            **({"max_win": fz["post_win"]} if "post_win" in fz else {})}
    W = Vf.get("w") or {}
    sc = Vf.get("sched")

    day_tp, day_sl = fz.get("day_tp"), fz.get("day_sl")

    def q(t, st):
        r = float(t["risk"])
        cum = float(st.get("cum", 0.0))
        if (day_tp is not None and cum >= float(day_tp)) or (day_sl is not None and cum <= -float(day_sl)):
            return 0                                     # funded day take-profit / day stop: no new entry today
        if t["src"] == "BLZ":
            return blz_q(t, st, float(W.get("BLZ", 1.0)), fz)
        c = post if st.get("locked") else pre
        n = SZ.funded_qty({"risk_pts": r, "tgt_pts": float(t["tgt"]), "size_mult": 1.0}, dict(st), c, acct=AF.ACCT)
        n = min(int(AF.ACCT["max_micros"]), int(n))
        if n <= 0:
            return 0
        w = float(W.get(t["src"], 1.0))
        if sc and t["src"] in sc["members"]:
            w = float(sc.get("funded", sc.get("late", w)))
        w = min(1.0, w)
        if w <= 0:
            return 0
        if w < 1.0:
            n = max(1, int(n * w + 1e-9))
        return int(EAB.dll_guard({"qty": n, "reasons": []}, r, AF.SPEC["rules"], st)["qty"])
    return q


def slot(Ve, Vf=None, fz=None, ask=None, spans=SPANS4, n=300, length=126, gap=2, seed=23):
    """The whole 25K slot over 6 months: eval (variant Ve's members + need size) -> funded (variant Vf's members, funded size
    fz) -> MFFU payouts (80% to the owner; ask line `ask` above the $1,100 buffer, live $750) -> a new $63 eval after a
    fail / stuck / a funded account lost, stuck or graduated (5 payouts). -> per span {pm: owner $ a month net of evals,
    p10: 10th percentile, lose: % of paths that lose, funded / evals / payouts per 6 months, first payout median}."""
    V2, A, M, EAB = libs()
    from engine import funded_life as FL
    from tools import atlas_funded as AF
    Vf = Vf or Ve
    fz = fz or FZ_LIVE
    P = dict(FL.plan_of("builder25k"))
    if ask is not None:
        P["ask_above"] = float(ask)
    if "fmin" in fz:
        P["fmin"] = float(fz["fmin"])
    be = M.by_day(A.account_units(Ve))
    bf = be if Vf is Ve else M.by_day(A.account_units(Vf))
    qf = funded_q(fz, Vf)
    out = {}
    with A.Plan(Ve):
        with AF.Sizer(qf):
            for s in spans:
                S = AF.span_sessions(s)
                nets, nf, ne, npay, first, made_e, made_f = [], [], [], [], [], [], []
                for seq in mc_paths(S, n, length, seed=seed):
                    cash, f_n, e_n, p_n, wait, acc, fp, me, mf = -PRICE, 0, 1, 0, 0, Eval(M), None, 0.0, 0.0
                    for k, d in enumerate(seq):
                        if wait:
                            wait -= 1
                            continue
                        if isinstance(acc, Eval):
                            r, recs = acc.step(be.get(d, ()), d)
                            me += sum(x["pnl"] for x in recs)
                            if r == "pass":
                                acc, wait, f_n = Funded(M, P), gap, f_n + 1
                            elif r in ("fail", "stuck"):
                                cash -= PRICE
                                e_n += 1
                                acc = Eval(M)
                        else:
                            paid, recs = acc.step(bf.get(d, ()), d)
                            mf += sum(x["pnl"] for x in recs)
                            if paid:
                                p_n += 1
                                fp = fp or k + 1
                            cash += paid
                            if acc.done:
                                cash -= PRICE
                                e_n += 1
                                acc = Eval(M)
                    nets.append(cash / (length / 21.0))
                    nf.append(f_n)
                    ne.append(e_n)
                    npay.append(p_n)
                    made_e.append(me)
                    made_f.append(mf)
                    if fp:
                        first.append(fp)
                a = np.array(nets)
                out[s] = {"pm": round(float(a.mean())), "p10": round(float(np.percentile(a, 10))), "lose": round(100.0 * float((a < 0).mean()), 1),
                          "funded_6m": round(float(np.mean(nf)), 2), "evals_6m": round(float(np.mean(ne)), 2),
                          "payouts_6m": round(float(np.mean(npay)), 2), "first_pay_med": float(np.median(first)) if first else None,
                          "eval_trading_pm": round(float(np.mean(made_e)) / 6.0), "funded_trading_pm": round(float(np.mean(made_f)) / 6.0)}
    return out


def real_slot(Ve, Vf=None, fz=None, ask=None, spans=SPANS4, gap=2):
    """The slot on each span's REAL sessions from its first session (one path, no resampling): eval -> funded -> ... ->
    the sized trades of every stage (stage tag) + the owner's payouts less the evals bought. For the run library."""
    V2, A, M, EAB = libs()
    from engine import funded_life as FL
    from tools import atlas_funded as AF
    Vf = Vf or Ve
    fz = fz or FZ_LIVE
    P = dict(FL.plan_of("builder25k"))
    if ask is not None:
        P["ask_above"] = float(ask)
    be = M.by_day(A.account_units(Ve))
    bf = be if Vf is Ve else M.by_day(A.account_units(Vf))
    out, T = {}, []
    with A.Plan(Ve):
        with AF.Sizer(funded_q(fz, Vf)):
            for s in spans:
                S = AF.span_sessions(s)
                cash, wait, acc, n_e, n_f, n_p = -PRICE, 0, Eval(M), 1, 0, 0
                for d in S:
                    if wait:
                        wait -= 1
                        continue
                    if isinstance(acc, Eval):
                        r, recs = acc.step(be.get(d, ()), d)
                        T += [{**x, "stage": "eval"} for x in recs]
                        if r == "pass":
                            acc, wait, n_f = Funded(M, P), gap, n_f + 1
                        elif r in ("fail", "stuck"):
                            cash -= PRICE
                            n_e += 1
                            acc = Eval(M)
                    else:
                        paid, recs = acc.step(bf.get(d, ()), d)
                        T += [{**x, "stage": "funded"} for x in recs]
                        cash += paid
                        n_p += 1 if paid else 0
                        if acc.done:
                            cash -= PRICE
                            n_e += 1
                            acc = Eval(M)
                out[s] = {"owner_net": round(cash), "per_month": round(cash / MONTHS[s]), "evals": n_e, "funded": n_f, "payouts": n_p}
    return out, T


# ================================================================================================ scoring + the gate
KEEP = ("p10", "f10", "s10", "dead10", "dec10", "p15", "f15", "p20", "f20", "dead20", "pass_med", "slow_pass", "mp_net_less_fees", "mp_per_eval",
        "mp_passes", "mp_pass_per_month", "net", "per_month", "pf", "dd", "tpw", "sig_tpw", "sig_wk2", "wk2", "n", "fund_paid_3m", "by_src",
        "starts", "max_risk")


def ev(V):
    V2, A, M, EAB = libs()
    o = V2.score(V)
    o = {s: {k: o[s].get(k) for k in KEEP} for s in o}
    o["2021-25"] = ref_join(o["2025"], o["2021-24"])
    for s in o:
        o[s]["pm"] = round(o[s]["mp_net_less_fees"] / (MONTHS[s] if s in MONTHS else MONTHS["2025"] + MONTHS["2021-24"]))
    return o


def ref_join(a, b):
    """2025 + 2021-24 as one 2021-25 reference: rates weighted by eval starts, money summed."""
    na, nb = a["starts"], b["starts"]
    w = lambda k: round((a[k] * na + b[k] * nb) / (na + nb), 1) if a.get(k) is not None and b.get(k) is not None else None
    o = {k: w(k) for k in ("p10", "f10", "s10", "dead10", "dec10", "p15", "f15", "p20", "f20", "dead20", "slow_pass", "sig_tpw", "sig_wk2",
                           "wk2", "tpw")}
    o["pass_med"] = b.get("pass_med")
    o["mp_net_less_fees"] = a["mp_net_less_fees"] + b["mp_net_less_fees"]
    o["net"] = a["net"] + b["net"]
    o["n"] = a["n"] + b["n"]
    o["per_month"] = round(o["net"] / (MONTHS["2025"] + MONTHS["2021-24"]))
    o["pf"] = None
    o["dd"] = min(a["dd"], b["dd"])
    o["starts"] = na + nb
    o["mp_per_eval"] = None
    o["mp_pass_per_month"] = round((a["mp_pass_per_month"] * na + b["mp_pass_per_month"] * nb) / (na + nb), 2)
    o["fund_paid_3m"] = None
    o["by_src"] = None
    return o


def slot_ref(sl):
    """2021-25 slot $ a month = the 2025 and 2021-24 rows weighted by their months."""
    a, b = sl["2025"], sl["2021-24"]
    wa, wb = MONTHS["2025"], MONTHS["2021-24"]
    return {"pm": round((a["pm"] * wa + b["pm"] * wb) / (wa + wb)), "lose": round((a["lose"] * wa + b["lose"] * wb) / (wa + wb), 1),
            "funded_6m": round((a["funded_6m"] * wa + b["funded_6m"] * wb) / (wa + wb), 2),
            "evals_6m": round((a["evals_6m"] * wa + b["evals_6m"] * wb) / (wa + wb), 2),
            "payouts_6m": round((a["payouts_6m"] * wa + b["payouts_6m"] * wb) / (wa + wb), 2),
            "p10": None, "first_pay_med": None,
            "eval_trading_pm": round((a["eval_trading_pm"] * wa + b["eval_trading_pm"] * wb) / (wa + wb)),
            "funded_trading_pm": round((a["funded_trading_pm"] * wa + b["funded_trading_pm"] * wb) / (wa + wb))}


def full(V, Vf=None, fz=None, ask=None, n=300, eval_V=None):
    """ev (the eval numbers of eval_V or V) + the slot (eval with V, funded with Vf)."""
    o = ev(eval_V or V)
    sl = slot(V, Vf, fz, ask, n=n)
    sl["2021-25"] = slot_ref(sl)
    for s in o:
        o[s]["slot"] = sl[s]
    return o


GATE_SPANS = ("H1", "H2", "2021-25")


def gate(o, b, money="pm", eval_same=False):
    """The owner's gate (strict): in H1 (pick), H2 (check) and 2021-25 (reference) ALL of
       - the eval is not worse: 2-week pass >= today's and dead (fail + stuck) <= today's (2021-25: pass - dead >= today's);
       - more money: eval-path $ a month (less fees) >= today's and the slot's owner $ a month >= today's, one of them up;
       - 2+ candidate trades a week.
    eval_same: a funded-only change (the eval is today's by construction): only the slot $ must be up."""
    res = {}
    for s in GATE_SPANS:
        x, y = o[s], b[s]
        if s == "2021-25":
            ev_ok = (x["p10"] - x["dead10"]) >= (y["p10"] - y["dead10"]) - 1e-9
        else:
            ev_ok = x["p10"] >= y["p10"] - 1e-9 and x["dead10"] <= y["dead10"] + 1e-9
        m_ok = x["pm"] >= y["pm"] and x["slot"]["pm"] >= y["slot"]["pm"] and (x["pm"] > y["pm"] or x["slot"]["pm"] > y["slot"]["pm"])
        if eval_same:
            m_ok = x["slot"]["pm"] > y["slot"]["pm"]
        fr = (x.get("sig_tpw") or 0) >= 2.0
        res[s] = {"eval": bool(ev_ok), "money": bool(m_ok), "freq": bool(fr), "ok": bool(ev_ok and m_ok and fr)}
    res["pass"] = all(res[s]["ok"] for s in GATE_SPANS)
    return res


def line(name, o, g=None):
    f = lambda s: (f"{s} {o[s]['p10']:.1f}/{o[s]['dead10']:.1f} ${o[s]['pm']:+,}/mo slot ${o[s]['slot']['pm']:+,}" if "slot" in o[s] else
                   f"{s} {o[s]['p10']:.1f}/{o[s]['dead10']:.1f} ${o[s]['pm']:+,}/mo")
    tag = "" if g is None else ("PASS " if g["pass"] else "     ") + "".join(("+" if g[s]["ok"] else "-") for s in GATE_SPANS) + " "
    return f"{tag}{name:44s} " + " | ".join(f(s) for s in ("H1", "H2", "2021-25"))


def dump(obj, name):
    E.dump(obj, os.path.join(OUT, name))


def _job(args):
    name, kind, kw = args
    libs()
    if kind == "full":
        o = full(**kw)
    elif kind == "slot":                                   # round 2: one seed of the slot simulator on the given spans
        add_years()
        if kw.pop("placebo", False):
            V2, A, M, EAB = libs()
            M.units().update(V2.placebo_members(n=12))
        o = slot(**kw)
    else:
        o = ev(kw["V"])
    return name, o


YEARS2 = {"2022": ("2022-01-01", "2022-12-31"), "2023": ("2023-01-01", "2023-12-31"), "2024": ("2024-01-01", "2024-12-31")}


def add_years():
    """2022 / 2023 / 2024 as extra spans of the slot simulator (2025 is already one)."""
    V2, A, M, EAB = libs()
    for k, v in YEARS2.items():
        if k not in M.SPANS:
            M.SPANS[k] = v
            MONTHS[k] = len([d for d in M.units()["sessions"] if v[0] <= d <= v[1]]) / 21.0


def pool_map(jobs, procs=2):
    import multiprocessing as mp
    if procs <= 1:
        return [_job(j) for j in jobs]
    with mp.get_context("fork").Pool(procs) as p:
        return p.map(_job, jobs, chunksize=1)


# ================================================================================================ commands
def cmd_base(n=300):
    t0 = time.time()
    libs()
    rows = {}
    for nm, V in (("today", today()), ("hunts x0.5", hunts()), ("lead: NA x0.5 + hunts x0.5", lead())):
        rows[nm] = full(V, n=n)
        print(line(nm, rows[nm]), f"({time.time() - t0:.0f}s)", flush=True)
        for s in ("H1", "H2", "2025", "2021-24"):
            sl = rows[nm][s]["slot"]
            print(f"     {s:7s} 2w {rows[nm][s]['p10']}/{rows[nm][s]['dead10']} eval-path ${rows[nm][s]['mp_net_less_fees']:,} slot ${sl['pm']}/mo p10 {sl['p10']} "
                  f"lose {sl['lose']}% funded {sl['funded_6m']} evals {sl['evals_6m']} payouts {sl['payouts_6m']} first {sl['first_pay_med']}", flush=True)
    dump({"built": time.strftime("%Y-%m-%d %H:%M"), "rows": rows}, "atx_base.json")
    return rows


def sched_family():
    """(name, V) of the pre-declared eval-state schedules of the extra members (NA + hunts at x0.5 when on)."""
    out = []
    X = list(XTRA)
    for N in (2, 3, 4, 5, 6, 8, 11):                                  # S1 the extra members only from eval session N
        out.append((f"S1 extras from session {N}", lead(sched={"members": X, "from": N, "early": 0.0, "late": 0.5})))
    for N, we in itertools.product((3, 5, 8), (0.25,)):               # S2 a lower weight early
        out.append((f"S2 extras x{we} before session {N}", lead(sched={"members": X, "from": N, "early": we, "late": 0.5})))
    for N in (3, 5, 8, 11):                                            # S3 hunts always, NA only from session N
        out.append((f"S3 NA from session {N}, hunts always", lead(sched={"members": ["NAD"], "from": N, "early": 0.0, "late": 0.5})))
    for X_ in (800.0, 1000.0, 1200.0, 1500.0):                        # S4 the extras only while the room is >= $X (start = $1,000)
        out.append((f"S4 extras only while room >= ${X_:,.0f}", lead(sched={"members": X, "from": 1, "early": 0.5, "late": 0.5, "room_min": X_})))
    for X_ in (800.0, 1000.0, 1200.0, 1500.0):                        # S5 NA only while room >= $X
        out.append((f"S5 NA only while room >= ${X_:,.0f}", lead(sched={"members": ["NAD"], "from": 1, "early": 0.5, "late": 0.5, "room_min": X_})))
    for X_ in (1200.0, 1500.0, 2000.0):                               # S6 extras x0.5 only while the room is BELOW $X (a "catch-up" use)
        out.append((f"S6 extras off once room >= ${X_:,.0f}", lead(sched={"members": X, "from": 1, "early": 0.5, "late": 0.5, "room_max": X_, "high": 0.0})))
    return out


def cmd_sched(n=300, procs=2):
    t0 = time.time()
    libs()
    base = full(today(), n=n)
    print(line("today", base), flush=True)
    F = sched_family()
    jobs = [(nm, "full", {"V": V, "n": n}) for nm, V in F]
    jobs += [("funded-only: eval today, funded + NA + hunts x0.5", "full", {"V": today(), "Vf": lead(), "n": n}),
             ("funded-only: eval today, funded + hunts x0.5", "full", {"V": today(), "Vf": hunts(), "n": n}),
             ("funded-only: eval hunts x0.5, funded + NA + hunts", "full", {"V": hunts(), "Vf": lead(), "n": n}),
             ("hunts x0.5 eval + funded (atlas-v2 lead)", "full", {"V": hunts(), "n": n}),
             ("lead as is (ab_atlas_na_hunts_lead)", "full", {"V": lead(), "n": n})]
    rows = []
    for nm, o in pool_map(jobs, procs):
        g = gate(o, base)
        rows.append({"name": nm, "o": o, "gate": g})
        print(line(nm, o, g), flush=True)
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "base": base, "rows": rows, "n_pass": sum(r["gate"]["pass"] for r in rows)}
    dump(out, "atx_sched.json")
    print(f"{out['n_pass']} of {len(rows)} pass ({time.time() - t0:.0f}s)", flush=True)
    return out


def maxd_family():
    """Member-specific day limits for the extras (known at the entry: the day's closed P&L so far)."""
    X = list(XTRA)
    return [("D1 extras never after a losing trade today", lead(sched={"members": X, "from": 1, "early": 0.5, "late": 0.5, "no_after_loss": True})),
            ("D2 extras only as the day's first trade (nothing closed yet)", lead(sched={"members": X, "from": 1, "early": 0.5, "late": 0.5, "only_flat_day": True})),
            ("D3 NA never after a losing trade today", lead(sched={"members": ["NAD"], "from": 1, "early": 0.5, "late": 0.5, "no_after_loss": True})),
            ("D4 NA only as the day's first trade", lead(sched={"members": ["NAD"], "from": 1, "early": 0.5, "late": 0.5, "only_flat_day": True}))]


def stage_family():
    """Round 2 (after family sched: the NA member costs FUNDED money in every schedule; the hunts on the funded account pay):
    (Ve = the eval's members, Vf = the funded account's members)."""
    H = lambda w: V_(members=MEM + ["SHA", "SHT"], w={"SHA": w, "SHT": w})
    A1 = lambda w: V_(members=MEM + ["SHA"], w={"SHA": w})
    out = []
    for nm, sc in (("NA from session 5", {"members": ["NAD"], "from": 5, "early": 0.0, "late": 0.5}),
                   ("NA from session 8", {"members": ["NAD"], "from": 8, "early": 0.0, "late": 0.5}),
                   ("NA from session 11", {"members": ["NAD"], "from": 11, "early": 0.0, "late": 0.5}),
                   ("NA only while room >= $1,000", {"members": ["NAD"], "from": 1, "early": 0.5, "late": 0.5, "room_min": 1000.0}),
                   ("NA only while room >= $1,200", {"members": ["NAD"], "from": 1, "early": 0.5, "late": 0.5, "room_min": 1200.0}),
                   ("NA only while room >= $1,500", {"members": ["NAD"], "from": 1, "early": 0.5, "late": 0.5, "room_min": 1500.0})):
        out.append((f"E1 eval hunts x0.5 + {nm}; funded hunts x0.5 (no NA)", {"V": lead(sched=sc), "Vf": H(0.5)}))
    for w in (0.4, 0.5, 0.6, 0.75, 1.0):
        out.append((f"E3 eval today; funded + hunts x{w:g}", {"V": today(), "Vf": H(w)}))
    for w in (0.4, 0.6, 0.75):
        out.append((f"E5 hunts x{w:g} eval + funded", {"V": H(w)}))
    out.append(("E4 hunts x0.5 eval; funded hunts x1.0", {"V": H(0.5), "Vf": H(1.0)}))
    for w in (0.5, 0.75, 1.0):
        out.append((f"E2 sh_asia only x{w:g} eval + funded (market entry)", {"V": A1(w)}))
        out.append((f"E2 eval today; funded + sh_asia x{w:g}", {"V": today(), "Vf": A1(w)}))
    out.append(("E2 eval today; funded + sh_trend x0.5", {"V": today(), "Vf": V_(members=MEM + ["SHT"], w={"SHT": 0.5})}))
    return out


def cmd_family(fam, n=300, procs=2):
    t0 = time.time()
    libs()
    base = full(today(), n=n)
    if fam == "stage":
        F = stage_family()
        jobs = [(nm, "full", {**kw, "n": n}) for nm, kw in F]
        rows = []
        for nm, o in pool_map(jobs, procs):
            same = "eval today" in nm
            g = gate(o, base, eval_same=same)
            rows.append({"name": nm, "o": o, "gate": g, "eval_same": same})
            print(line(nm, o, g), flush=True)
        out = {"built": time.strftime("%Y-%m-%d %H:%M"), "base": base, "rows": rows, "n_pass": sum(r["gate"]["pass"] for r in rows)}
        dump(out, "atx_stage.json")
        print(f"{out['n_pass']} of {len(rows)} pass ({time.time() - t0:.0f}s)", flush=True)
        return out
    F = {"maxd": maxd_family}[fam]()
    rows = []
    for nm, o in pool_map([(nm, "full", {"V": V, "n": n}) for nm, V in F], procs):
        g = gate(o, base)
        rows.append({"name": nm, "o": o, "gate": g})
        print(line(nm, o, g), flush=True)
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "base": base, "rows": rows, "n_pass": sum(r["gate"]["pass"] for r in rows)}
    dump(out, f"atx_{fam}.json")
    print(f"{out['n_pass']} of {len(rows)} pass ({time.time() - t0:.0f}s)", flush=True)
    return out


def funded_family():
    out = []
    for pre, post in ((0.3, 0.6), (0.4, 0.6), (0.5, 0.6), (0.4, 0.8), (0.5, 0.8), (0.6, 0.8), (0.3, 0.8)):
        out.append((f"F1 buffer-first {pre:g} -> {post:g} of the room after the lock", {"fz": {"pre_pct": pre, "post_pct": post}}))
    for pre, post, mx in ((0.4, 0.8, 1000.0), (0.5, 0.8, 1000.0), (0.6, 0.8, 1000.0), (0.6, 0.6, 1000.0)):
        out.append((f"F2 buffer-first {pre:g} -> {post:g}, cap $1,000 after the lock", {"fz": {"pre_pct": pre, "post_pct": post, "post_max": mx}}))
    for ask in (250.0, 500.0, 1000.0, 1500.0):
        out.append((f"F3 ask once ${ask:,.0f} above the buffer (live $750)", {"ask": ask}))
    for mw in (750.0, 1500.0):
        out.append((f"F4 funded winner cap ${mw:,.0f} (live $1,000; the 50% best-day rule)", {"fz": {"max_win": mw}}))
    return out


def cmd_funded(n=300, procs=2):
    """The funded-stage money rules on today's funded account AND on the funded-only hunts candidate (eval today, funded +
    hunts x0.5). Gate: the slot's owner $ a month up in H1, H2 and 2021-25 against today (the eval is unchanged)."""
    t0 = time.time()
    libs()
    base = full(today(), n=n)
    cand_vf = V_(members=MEM + ["SHA", "SHT"], w={"SHA": 0.5, "SHT": 0.5})
    cand = full(today(), Vf=cand_vf, n=n)
    print(line("today", base), flush=True)
    print(line("funded + hunts x0.5", cand), flush=True)
    jobs = []
    for nm, kw in funded_family():
        jobs.append((nm, "full", {"V": today(), "n": n, **kw}))
        jobs.append((nm + " | funded + hunts x0.5", "full", {"V": today(), "Vf": cand_vf, "n": n, **kw}))
    rows = []
    for nm, o in pool_map(jobs, procs):
        g = gate(o, base, eval_same=True)
        on_cand = nm.endswith("hunts x0.5")
        gc = gate(o, cand, eval_same=True) if on_cand else None
        rows.append({"name": nm, "o": o, "gate": g, "gate_vs_cand": gc})
        print(line(nm, o, g), "vs cand " + ("PASS" if gc and gc["pass"] else "-") if on_cand else "",
              " | ".join(f"{s} pay {o[s]['slot']['payouts_6m']} lose {o[s]['slot']['lose']}%" for s in ("H1", "H2", "2021-25")), flush=True)
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "base": base, "cand": cand, "rows": rows, "n_pass": sum(r["gate"]["pass"] for r in rows),
           "n_pass_vs_cand": sum(bool(r["gate_vs_cand"] and r["gate_vs_cand"]["pass"]) for r in rows)}
    dump(out, "atx_funded.json")
    print(f"{out['n_pass']} of {len(rows)} pass ({time.time() - t0:.0f}s)", flush=True)
    return out


# ================================================================================================ per-member windows (picked on H1)
H1 = ("2026-01-01", "2026-06-30")


def bkey(u, fact):
    V2, A, M, EAB = libs()
    if fact == "hour":
        return A.et_mod(u["entry_t"]) // 60
    if fact == "dow":
        return dt.date.fromisoformat(u["day"]).weekday()
    if fact == "sess":                                  # Asia 18:00-02:00, London 02:00-09:30, NY 09:30-17:00
        m = A.et_mod(u["entry_t"])
        return "asia" if (m >= 18 * 60 or m < 120) else "london" if m < 570 else "ny"
    raise KeyError(fact)


def member_buckets(V, name, fact, min_n=5):
    """H1 stats of one member's ACCOUNT units (after the no-hedge rules) per bucket: {bucket: (mean R, n, sum R)}."""
    V2, A, M, EAB = libs()
    B = collections.defaultdict(list)
    for u in A.account_units(V):
        if u["src"] == name and H1[0] <= u["day"] <= H1[1]:
            B[bkey(u, fact)].append(E._R(u))
    return {b: (float(np.mean(x)), len(x), float(np.sum(x))) for b, x in B.items() if len(x) >= min_n}


def drop_set(name, fact, bucket):
    V2, A, M, EAB = libs()
    return sorted(int(u["entry_t"]) for u in M.units()[name] if bkey(u, fact) == bucket)


def worst(V, name, fact, min_n=5):
    st = member_buckets(V, name, fact, min_n)
    c = [(v[2], b) for b, v in st.items() if v[0] < 0]
    return min(c)[1] if c else None


def with_drops(V, picks):
    """picks = {member: [(fact, bucket), ...]} -> V with V["drop"] (tools/atlas_v2.member_units drops those entries)."""
    V = copy.deepcopy(V)
    d = collections.defaultdict(set)
    for nm, L in picks.items():
        for fact, b in L:
            d[nm].update(drop_set(nm, fact, b))
    V["drop"] = {k: sorted(v) for k, v in d.items()}
    return V


def win_family():
    out = []
    for bnm, B, members in (("today", today(), MEM), ("lead", lead(), MEM + XTRA)):
        for fact in ("hour", "dow", "sess"):          # sess only splits sh_trend (every other member trades one session)
            picks = {}
            for nm in members:
                w = worst(B, nm, fact)
                if w is not None:
                    picks[nm] = [(fact, w)]
            if picks:
                out.append((f"W {bnm}: each member's worst H1 {fact} dropped", bnm, fact, members, picks))
        if bnm == "lead":
            for fact in ("hour", "dow"):
                w = worst(B, "NAD", fact)
                if w is not None:
                    out.append((f"W lead: NA's worst H1 {fact} dropped", bnm, fact, ["NAD"], {"NAD": [(fact, w)]}))
            both = {"NAD": [(f, worst(B, "NAD", f)) for f in ("hour", "dow") if worst(B, "NAD", f) is not None]}
            out.append(("W lead: NA's worst H1 hour AND weekday dropped", bnm, "hour", ["NAD"], both))
    return out


def shuffled(B, fact, members, picks, k, seed):
    """The control: each picked member drops a RANDOM bucket of the same fact (any bucket with 5+ H1 trades), not its worst."""
    rng = np.random.default_rng(seed)
    out = {}
    for nm, L in picks.items():
        out[nm] = []
        for f, _ in L:
            bs = sorted(member_buckets(B, nm, f), key=str)
            out[nm].append((f, bs[int(rng.integers(0, len(bs)))]))
    return out


def cmd_win(n=300, procs=2, n_ctl=12):
    t0 = time.time()
    libs()
    base = full(today(), n=n)
    print(line("today", base), flush=True)
    F = win_family()
    Bv = {"today": today(), "lead": lead()}
    jobs = [(nm, "full", {"V": with_drops(Bv[b], p), "n": n}) for nm, b, fact, mem, p in F]
    rows = []
    for (nm, b, fact, mem, p), (_, o) in zip(F, pool_map(jobs, procs)):
        g = gate(o, base)
        rows.append({"name": nm, "base": b, "fact": fact, "picks": {k: [list(x) for x in v] for k, v in p.items()}, "o": o, "gate": g})
        print(line(nm, o, g), {k: v[0][1] for k, v in p.items()}, flush=True)
    # shuffled-window control for every row: random buckets, eval numbers only (the slot is too slow for many draws)
    for r, (nm, b, fact, mem, p) in zip(rows, F):
        jobs = [(f"{nm} ctl{i}", "ev", {"V": with_drops(Bv[b], shuffled(Bv[b], fact, mem, p, 0, 100 + i))}) for i in range(n_ctl)]
        res = pool_map(jobs, procs)
        real = {s: r["o"][s]["pm"] for s in GATE_SPANS}
        ctl = {s: [o[s]["pm"] for _, o in res] for s in GATE_SPANS}
        r["control"] = {"n": n_ctl, **{f"{s}_pm_mean": round(float(np.mean(ctl[s]))) for s in GATE_SPANS},
                        **{f"{s}_share_ge_real": round(float(np.mean([c >= real[s] for c in ctl[s]])), 2) for s in GATE_SPANS},
                        "p10_h1_mean": round(float(np.mean([o["H1"]["p10"] for _, o in res])), 1)}
        print("   control", nm, r["control"], flush=True)
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "base": base, "rows": rows, "n_pass": sum(r["gate"]["pass"] for r in rows)}
    dump(out, "atx_win.json")
    print(f"{out['n_pass']} of {len(rows)} pass ({time.time() - t0:.0f}s)", flush=True)
    return out


# ================================================================================================ round 4: the lead's NA member + funded rules
def cmd_round4(n=300, procs=2):
    """(a) the fixed lead's neighbours: NA only from eval session N (8 / 11 / 14) or only while the room is >= $X, NA x0.25-0.75,
    hunts x0.4-0.6, the funded account with the hunts only (no NA); judged against today AND against the hunts alone (does
    the NA member add owner money?); (b) the 50% best-day rule in the funded size (engine/sizing.funded_qty cons_aware) on
    today's funded account and on the funded-only hunts candidate."""
    t0 = time.time()
    libs()
    base = full(today(), n=n)
    jobs = []
    for N, wn, wh in itertools.product((8, 11, 14), (0.25, 0.5, 0.75), (0.4, 0.5, 0.6)):
        sc = {"members": ["NAD"], "from": N, "early": 0.0, "late": wn}
        jobs.append((f"G1 NA x{wn:g} from session {N}, hunts x{wh:g}; funded hunts x{wh:g}", "full",
                     {"V": lead(wn, wh, sched=sc), "Vf": H_(wh), "n": n}))
    for X_, wn in itertools.product((1200.0, 1500.0), (0.25, 0.5, 0.75)):
        sc = {"members": ["NAD"], "from": 1, "early": wn, "late": wn, "room_min": X_}
        jobs.append((f"G2 NA x{wn:g} only while room >= ${X_:,.0f}, hunts x0.5; funded hunts x0.5", "full",
                     {"V": lead(wn, 0.5, sched=sc), "Vf": H_(0.5), "n": n}))
    for ca in (True, "after_payout"):
        jobs.append((f"F5 funded cons_aware {ca}", "full", {"V": today(), "fz": {"cons_aware": ca}, "n": n}))
        jobs.append((f"F5 funded cons_aware {ca} | funded + hunts x0.5", "full", {"V": today(), "Vf": H_(0.5), "fz": {"cons_aware": ca}, "n": n}))
    jobs.append(("ref hunts x0.5 eval + funded", "full", {"V": H_(0.5), "n": n}))
    jobs.append(("ref eval today; funded + hunts x0.5", "full", {"V": today(), "Vf": H_(0.5), "n": n}))
    res = pool_map(jobs, procs)
    R = dict(res)
    href = R["ref hunts x0.5 eval + funded"]
    fref = R["ref eval today; funded + hunts x0.5"]
    rows = []
    for nm, o in res:
        same = nm.startswith("F5") or nm.startswith("ref eval today")
        g = gate(o, base, eval_same=same)
        gh = gate(o, href) if nm.startswith("G") else (gate(o, fref, eval_same=True) if nm.endswith("hunts x0.5") and nm.startswith("F5") else None)
        rows.append({"name": nm, "o": o, "gate": g, "gate_vs_ref": gh})
        print(line(nm, o, g), ("| vs hunts-only ref " + ("PASS" if gh["pass"] else "-")) if gh else "", flush=True)
    G = [r for r in rows if r["name"].startswith("G")]
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "base": base, "rows": rows, "n_g": len(G), "n_g_pass": sum(r["gate"]["pass"] for r in G),
           "n_g_pass_vs_hunts": sum(r["gate_vs_ref"]["pass"] for r in G),
           "n_g_slot_ge_hunts_all3": sum(all(r["o"][s]["slot"]["pm"] >= href[s]["slot"]["pm"] for s in GATE_SPANS) for r in G)}
    dump(out, "atx_round4.json")
    print(f"G: {out['n_g_pass']} of {len(G)} pass vs today, {out['n_g_pass_vs_hunts']} vs the hunts alone, "
          f"{out['n_g_slot_ge_hunts_all3']} have a slot >= the hunts alone in all three spans ({time.time() - t0:.0f}s)", flush=True)
    return out


def cmd_e4grid(n=300, procs=2):
    """Neighbours of 'hunts x0.5 in the eval, x1.0 once funded': eval hunts x0.4-0.75 by funded hunts x0.75 / x1.0."""
    t0 = time.time()
    libs()
    base = full(today(), n=n)
    jobs = [(f"eval hunts x{we:g}; funded hunts x{wf:g}", "full", {"V": H_(we), "Vf": H_(wf), "n": n})
            for we, wf in itertools.product((0.4, 0.5, 0.6, 0.75), (0.75, 1.0))]
    rows = []
    for nm, o in pool_map(jobs, procs):
        g = gate(o, base)
        rows.append({"name": nm, "o": o, "gate": g})
        print(line(nm, o, g), flush=True)
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "base": base, "rows": rows, "n_pass": sum(r["gate"]["pass"] for r in rows)}
    dump(out, "atx_e4grid.json")
    print(f"{out['n_pass']} of {len(rows)} pass ({time.time() - t0:.0f}s)", flush=True)
    return out


def cmd_fmin(n=300, procs=2):
    """When to give up a funded 25K: the bot stops it under $100 of room (live); give up under $200 / $300 / $400 instead
    (buy the next $63 eval sooner) - on today's funded account and on the funded-only hunts candidate."""
    t0 = time.time()
    libs()
    base = full(today(), n=n)
    cand = full(today(), Vf=H_(0.5), n=n)
    jobs = []
    for fm in (200.0, 300.0, 400.0):
        jobs.append((f"F6 give up a funded account under ${fm:,.0f} of room", "full", {"V": today(), "fz": {"fmin": fm}, "n": n}))
        jobs.append((f"F6 give up under ${fm:,.0f} | funded + hunts x0.5", "full", {"V": today(), "Vf": H_(0.5), "fz": {"fmin": fm}, "n": n}))
    for tp in (300.0, 400.0, 500.0, 750.0):                 # F7 funded day take-profit (the 50% best-day rule; BLITZ's funded uses $400)
        jobs.append((f"F7 funded: no new entry once the day is +${tp:,.0f}", "full", {"V": today(), "fz": {"day_tp": tp}, "n": n}))
        jobs.append((f"F7 day +${tp:,.0f} | funded + hunts x0.5", "full", {"V": today(), "Vf": H_(0.5), "fz": {"day_tp": tp}, "n": n}))
    for sl in (200.0, 300.0, 400.0):                         # F8 funded day stop below the $600 soft daily loss
        jobs.append((f"F8 funded: no new entry once the day is -${sl:,.0f}", "full", {"V": today(), "fz": {"day_sl": sl}, "n": n}))
        jobs.append((f"F8 day -${sl:,.0f} | funded + hunts x0.5", "full", {"V": today(), "Vf": H_(0.5), "fz": {"day_sl": sl}, "n": n}))
    rows = []
    for nm, o in pool_map(jobs, procs):
        g = gate(o, base, eval_same=True)
        gc = gate(o, cand, eval_same=True) if nm.endswith("hunts x0.5") else None
        rows.append({"name": nm, "o": o, "gate": g, "gate_vs_cand": gc})
        print(line(nm, o, g), ("| vs cand " + ("PASS" if gc["pass"] else "-")) if gc else "",
              " | ".join(f"{s} evals {o[s]['slot']['evals_6m']} lose {o[s]['slot']['lose']}%" for s in GATE_SPANS), flush=True)
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "base": base, "cand": cand, "rows": rows}
    dump(out, "atx_fmin.json")
    print(f"done ({time.time() - t0:.0f}s)", flush=True)
    return out


def cmd_why(n=300):
    """Why the NA member costs funded money: the funded account with and without it (eval = hunts x0.5 for both), payouts,
    stuck / lost, and how often the 50% best-day rule holds a payout back (tools/atlas_funded.mc on its 1,000 paths)."""
    from tools import atlas_funded as AF
    V2, A, M, EAB = libs()
    out = {}
    for nm, Vf in (("hunts x0.5", H_(0.5)), ("hunts x0.5 + NA x0.5", lead()), ("today", today())):
        by = M.by_day(A.account_units(Vf))
        with A.Plan(Vf):
            with AF.Sizer(funded_q(FZ_LIVE, Vf)):
                out[nm] = {s: AF.mc(by, s, n=n) for s in ("H1", "H2", "2025", "2021-24")}
        print(nm, {s: {k: out[nm][s][k] for k in ("per_month", "payouts_per_month", "stuck_6m", "lost_6m", "cons_block_days", "made_per_month",
                                                  "trades_per_week", "first_med")} for s in out[nm]}, flush=True)
    dump(out, "atx_why.json")
    return out


# ================================================================================================ random-time hunt members (control)
def cmd_placebo(n=300, procs=2, k=12):
    """The hunts replaced by their random-time twins (tools/atlas_v2.placebo_members: the same side and mechanics, a random 5m
    signal bar of the same session bucket in a random session of the span) and by the flipped twin, for the two hunt
    candidates: (a) funded-only hunts x0.5 (the eval stays today's), (b) hunts x0.5 in the eval and on the funded account."""
    t0 = time.time()
    V2, A, M, EAB = libs()
    M.units().update(V2.placebo_members(n=k))
    base = full(today(), n=n)
    H = lambda w, sub=None: V_(members=MEM + ["SHA", "SHT"], w={"SHA": w, "SHT": w}, **({"sub": sub} if sub else {}))
    subs = [(f"rtime{i}", {h: f"P{h}_r{i}" for h in ("SHA", "SHT")}) for i in range(k)] + [("flip", {h: f"P{h}_f" for h in ("SHA", "SHT")})]
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "base": base, "cands": {}}
    for cname, mk in (("funded-only hunts x0.5", lambda sub: {"V": today(), "Vf": H(0.5, sub)}),
                      ("hunts x0.5 eval + funded", lambda sub: {"V": H(0.5, sub)})):
        real = full(**mk(None), n=n)
        jobs = [(lab, "full", {**mk(sub), "n": n}) for lab, sub in subs]
        res = dict(pool_map(jobs, procs))
        same = cname.startswith("funded-only")
        R = {}
        rl_ = [lab for lab, _ in subs if lab != "flip"]
        for s in GATE_SPANS:
            r = [res[lab][s]["slot"]["pm"] for lab in rl_]
            e = [res[lab][s]["pm"] for lab in rl_]
            R[s] = {"real_slot": real[s]["slot"]["pm"], "rand_slot_mean": round(float(np.mean(r))),
                    "rand_slot_ge_real": round(float(np.mean([x >= real[s]["slot"]["pm"] for x in r])), 2),
                    "flip_slot": res["flip"][s]["slot"]["pm"], "real_eval_pm": real[s]["pm"], "rand_eval_pm_mean": round(float(np.mean(e))),
                    "rand_eval_ge_real": round(float(np.mean([x >= real[s]["pm"] for x in e])), 2), "flip_eval_pm": res["flip"][s]["pm"],
                    "real_p10": real[s]["p10"], "rand_p10_mean": round(float(np.mean([res[lab][s]["p10"] for lab in rl_])), 1)}
        npass = sum(gate(res[lab], base, eval_same=same)["pass"] for lab in rl_)
        out["cands"][cname] = {"spans": R, "rand_pass": npass, "n": k, "flip_pass": gate(res["flip"], base, eval_same=same)["pass"],
                               "rows": {lab: {s: {"p10": o[s]["p10"], "dead10": o[s]["dead10"], "pm": o[s]["pm"], "slot": o[s]["slot"]["pm"]}
                                              for s in GATE_SPANS} for lab, o in res.items()}}
        print(cname, f"random members passing the gate {npass}/{k}, flip passes {out['cands'][cname]['flip_pass']}", flush=True)
        for s in GATE_SPANS:
            print("   ", s, R[s], flush=True)
    dump(out, "atx_placebo.json")
    print(f"done {time.time() - t0:.0f}s", flush=True)
    return out


# ================================================================================================ the finalists: checks + run library
def H_(w):
    return V_(members=MEM + ["SHA", "SHT"], w={"SHA": w, "SHT": w})


def finalists():
    """(run id, title, kwargs of full / real_slot). Fixed after families sched / stage / placebo / funded / win."""
    na11 = lead(sched={"members": ["NAD"], "from": 11, "early": 0.0, "late": 0.5})
    return [("atx_today", "ATLAS today (baseline for the slot)", {"V": today()}),
            ("atx_funded_hunts_w05", "Eval = today's ATLAS; once funded, + the two stop hunts x0.5", {"V": today(), "Vf": H_(0.5)}),
            ("atx_funded_hunts_w075", "Eval = today's ATLAS; once funded, + the two stop hunts x0.75", {"V": today(), "Vf": H_(0.75)}),
            ("atx_hunts_w05_funded_w1", "Hunts x0.5 in the eval, x1.0 once funded", {"V": H_(0.5), "Vf": H_(1.0)}),
            ("atx_hunts_w075", "Hunts x0.75 in the eval and once funded", {"V": H_(0.75)}),
            ("atx_lead_na_s11_funded_hunts", "The NA + hunts lead fixed: NA only from eval session 11, no NA once funded", {"V": na11, "Vf": H_(0.5)}),
            ("atx_lead_as_is", "The NA + hunts lead as is (ab_atlas_na_hunts_lead) on the slot", {"V": lead()})]


YEARS = {"2022": ("2022-01-01", "2022-12-31"), "2023": ("2023-01-01", "2023-12-31"), "2024": ("2024-01-01", "2024-12-31")}


def cmd_checks(n=500, procs=2):
    """The finalists on a second set of slot paths (seed 7, 500 paths) and per year of the reference (2022 / 2023 / 2024 /
    2025: eval 2-week pass / dead + slot $ a month)."""
    t0 = time.time()
    V2, A, M, EAB = libs()
    for k, v in YEARS.items():
        M.SPANS[k] = v
        MONTHS[k] = len([d for d in M.units()["sessions"] if v[0] <= d <= v[1]]) / 21.0
    global mc_paths
    _mc = mc_paths

    def mc7(S, n_, length, seed=23, block=5):
        return _mc(S, n_, length, seed=7, block=block)
    out = {}
    for rid, _, kw in finalists():
        mc_paths = mc7
        sl = slot(kw["V"], kw.get("Vf"), n=n, spans=("H1", "H2", "2025", "2021-24"))
        mc_paths = _mc
        sy = slot(kw["V"], kw.get("Vf"), n=200, spans=tuple(YEARS) + ("2025",))
        ey = V2.score(kw["V"], spans=tuple(YEARS) + ("2025",))
        out[rid] = {"seed7": sl, "years": {y: {"p10": ey[y]["p10"], "dead10": ey[y]["dead10"], "eval_pm": round(ey[y]["mp_net_less_fees"] / MONTHS[y]),
                                                "slot_pm": sy[y]["pm"]} for y in tuple(YEARS) + ("2025",)}}
        print(rid, "seed7 slot", {s: sl[s]["pm"] for s in sl}, "| years", {y: (v["p10"], v["dead10"], v["slot_pm"]) for y, v in out[rid]["years"].items()},
              f"({time.time() - t0:.0f}s)", flush=True)
    dump(out, "atx_checks.json")
    return out


def _runlib_trades(T):
    out = []
    for t in T:
        ru = t.get("risk_usd") or 0.0
        out.append({"day": t["day"], "entry_t": t["entry_t"], "exit_t": t["exit_t"], "dir": t["dir"], "r": t["pnl"] / ru if ru else 0.0,
                    "pnl": t["pnl"], "risk_pts": t["risk"], "qty": t["qty"], "risk_usd": ru, "half": 0, "exit": t["exit"],
                    "trigger": f"atlas-{t['stage']}:{t['src']}", "mfe": None, "mae": None, "bars_held": None, "regime": None, "mult": 1.0,
                    "low": t.get("low")})
    out.sort(key=lambda t: t["entry_t"])
    return out


def cmd_save():
    """runs atx_* (trades = the slot on each span's real sessions: eval + funded trades, sized; numbers in the verdict)."""
    from tools import runlib as rl
    V2, A, M, EAB = libs()
    sess = sorted(set(M.units()["sessions"]))
    res = json.load(open(os.path.join(OUT, "atx_final.json"), encoding="utf-8"))
    for rid, title, kw in finalists():
        o = res[rid]
        rs, T = real_slot(kw["V"], kw.get("Vf"))
        f = lambda s: (f"{s}: 2-week pass/dead {o[s]['p10']}/{o[s]['dead10']}, eval-path ${o[s]['pm']:,}/mo less fees, slot ${o[s]['slot']['pm']:,}/mo "
                       f"to the owner net of evals, {o[s]['sig_tpw']} trades/wk")
        st = res["_status"].get(rid, "info")
        vt = res["_verdict"].get(rid, "") + " " + "; ".join(f(s) for s in GATE_SPANS) + \
            ". Real-session slot (one path from each span's first session): " + "; ".join(f"{s} ${rs[s]['per_month']:,}/mo ({rs[s]['payouts']} payouts, {rs[s]['evals']} evals)" for s in rs)
        rl.save(rid, title, "risk", "ATLAS 2026-10-30 b: can a stage-aware member set (extra members by eval session / room / funded stage) "
                "keep the hunts' and the NA lead's money without breaking the 25K eval?", params={k: v for k, v in kw.items()},
                sizing={"eval": "engine/account_b.qty need (tools/atlas.q_variant) x the member weight / schedule",
                        "funded": "engine/sizing.funded_qty on the 25K preset (60% room, $50-$750, ref 20, winner <= $1,000) x the member weight (<= 1)"},
                trades=_runlib_trades(T), scored=rl.score(_runlib_trades(T), sess), status=st, verdict=vt.strip(),
                notes="tools/atx_edge.py (slot = 300 block-bootstrap paths x 126 sessions, $63 evals, 80% payouts)",
                writeup="atlas-edge-2026-10-30b", tags=["atlas", "account_b", "25k", "stop_hunt", "funded", "slot"])
        print("saved", rid, flush=True)


def cmd_final(n=300, procs=2):
    """The finalists' full numbers (the same paths as the families) -> research/second/atx_final.json (+ status / verdict)."""
    libs()
    F = finalists()
    res = dict(pool_map([(rid, "full", {**kw, "n": n}) for rid, _, kw in F], procs))
    base = res["atx_today"]
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), **res, "_gate": {}, "_status": {}, "_verdict": {}}
    out["_real"] = {}
    for rid, title, kw in F:
        same = kw["V"] is not None and rid.startswith("atx_funded")
        g = gate(res[rid], base, eval_same=same)
        out["_gate"][rid] = g
        rs, T = real_slot(kw["V"], kw.get("Vf"))
        out["_real"][rid] = {s: {**rs[s], **path_stats(T, s)} for s in rs}
        print(line(rid, res[rid], g), flush=True)
        print("     real-session slot:", {s: (out["_real"][rid][s]["per_month"], out["_real"][rid][s]["tpw"], out["_real"][rid][s]["pf"],
                                           out["_real"][rid][s]["dd"]) for s in rs}, flush=True)
    dump(out, "atx_final.json")
    return out


def path_stats(T, s):
    """Trades a week, % weeks with 2+, PF, net, $ a month, max DD of the slot path's trades (eval + funded) in span s."""
    from tools import atlas_funded as AF
    S = AF.span_sessions(s)
    X = [t for t in T if S[0] <= t["day"] <= S[-1]]
    wk = lambda d: dt.date.fromisoformat(d).isocalendar()[:2]
    W = collections.Counter(wk(t["day"]) for t in X)
    allw = sorted({wk(d) for d in S})
    p = np.array([t["pnl"] for t in X]) if X else np.zeros(1)
    gl = -p[p < 0].sum()
    eq = np.cumsum(p)
    return {"n": len(X), "tpw": round(len(X) / (len(S) / 5), 2), "wk2": round(100.0 * sum(1 for w in allw if W.get(w, 0) >= 2) / len(allw), 1),
            "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None, "net": round(float(p.sum())), "trade_pm": round(float(p.sum()) / MONTHS[s]),
            "dd": round(float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min())),
            "n_funded": sum(1 for t in X if t.get("stage") == "funded")}


# ================================================================================================ round 2 (coordinator, 13:20)
R2_SPANS = ("H1", "H2", "2025", "2021-24", "2022", "2023", "2024")
R2_SEEDS = tuple(range(101, 121))                      # 20 seeds of the slot simulator (200 paths each)


def A1f(w, sub=None):
    """Config A, clean: the funded account trades ATLAS's members + sh_asia (market entry at the next 5m open) at weight w."""
    return V_(members=MEM + ["SHA"], w={"SHA": w}, **({"sub": {"SHA": sub}} if sub else {}))


def seeds_table(res, names, spans, seeds):
    """{name: {span: {"mean", "sd", "seeds": [...]}}} from pool results keyed f"{name}|{seed}"."""
    out = {}
    for nm in names:
        out[nm] = {}
        for s in spans:
            x = [res[f"{nm}|{sd}"][s]["pm"] for sd in seeds if f"{nm}|{sd}" in res]
            out[nm][s] = {"mean": round(float(np.mean(x)), 1), "sd": round(float(np.std(x)), 1), "seeds": x}
        a, b = out[nm]["2025"], out[nm]["2021-24"]
        wa, wb = MONTHS["2025"], MONTHS["2021-24"]
        ref = [(x * wa + y * wb) / (wa + wb) for x, y in zip(a["seeds"], b["seeds"])]
        out[nm]["2021-25"] = {"mean": round(float(np.mean(ref)), 1), "sd": round(float(np.std(ref)), 1), "seeds": [round(v, 1) for v in ref]}
    return out


def paired(T, nm, base="today", spans=("H1", "H2", "2021-25", "2022", "2023", "2024", "2025")):
    """mean difference vs base and the share of seeds where nm beats base (the same paths)."""
    o = {}
    for s in spans:
        d = [x - y for x, y in zip(T[nm][s]["seeds"], T[base][s]["seeds"])]
        o[s] = {"diff": round(float(np.mean(d)), 1), "win_share": round(float(np.mean([v > 0 for v in d])), 2)}
    return o


def cmd_r2a(n=200, procs=2, k_ctl=12, ctl_seeds=4):
    """Round 2 item 1: eval unchanged, the funded stage + sh_asia ONLY (weights 0.4 / 0.5 / 0.75 / 1.0): 20 seeds x 200 slot
    paths per span (H1 / H2 / 2025 / 2021-24 + each year 2022-24), the random-time control (12 copies of sh_asia + the flipped
    twin, at x0.5, on the first 4 seeds) and the real 2026 calendar path."""
    t0 = time.time()
    V2, A, M, EAB = libs()
    add_years()
    M.units().update(V2.placebo_members(n=k_ctl))
    var = {"today": (today(), None)}
    for w in (0.4, 0.5, 0.75, 1.0):
        var[f"funded + sh_asia x{w:g}"] = (today(), A1f(w))
    jobs = [(f"{nm}|{sd}", "slot", {"Ve": Ve, "Vf": Vf, "spans": R2_SPANS, "n": n, "seed": sd}) for nm, (Ve, Vf) in var.items() for sd in R2_SEEDS]
    ctl = {f"rtime{i}": A1f(0.5, f"PSHA_r{i}") for i in range(k_ctl)}
    ctl["flip"] = A1f(0.5, "PSHA_f")
    jobs += [(f"{nm}|{sd}", "slot", {"Ve": today(), "Vf": Vf, "spans": SPANS4, "n": n, "seed": sd, "placebo": True})
             for nm, Vf in ctl.items() for sd in R2_SEEDS[:ctl_seeds]]
    res = dict(pool_map(jobs, procs))
    T = seeds_table(res, list(var), R2_SPANS, R2_SEEDS)
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "n_paths": n, "seeds": list(R2_SEEDS), "table": T, "paired": {}, "gate": {}, "real": {}}
    for nm in var:
        if nm == "today":
            continue
        pr = paired(T, nm)
        out["paired"][nm] = pr
        out["gate"][nm] = all(pr[s]["diff"] > 0 for s in ("H1", "H2", "2021-25"))
        print(f"{nm:24s} " + " | ".join(f"{s} ${T[nm][s]['mean']:,.0f} ({pr[s]['diff']:+.0f}, {int(100 * pr[s]['win_share'])}% seeds)"
                                         for s in ("H1", "H2", "2021-25", "2022", "2023", "2024", "2025")), "PASS" if out["gate"][nm] else "", flush=True)
    print("today                    " + " | ".join(f"{s} ${T['today'][s]['mean']:,.0f} (sd {T['today'][s]['sd']:.0f})" for s in ("H1", "H2", "2021-25", "2022", "2023", "2024", "2025")), flush=True)
    # control: same 4 seeds
    C = seeds_table(res, list(ctl) + ["funded + sh_asia x0.5", "today"], SPANS4, R2_SEEDS[:ctl_seeds])
    rt = [f"rtime{i}" for i in range(k_ctl)]
    out["control"] = {s: {"real": C["funded + sh_asia x0.5"][s]["mean"], "today": C["today"][s]["mean"],
                          "rand_mean": round(float(np.mean([C[r][s]["mean"] for r in rt])), 1),
                          "rand_ge_real": round(float(np.mean([C[r][s]["mean"] >= C["funded + sh_asia x0.5"][s]["mean"] for r in rt])), 2),
                          "rand_gt_today": round(float(np.mean([C[r][s]["mean"] > C["today"][s]["mean"] for r in rt])), 2),
                          "flip": C["flip"][s]["mean"]} for s in ("H1", "H2", "2021-25")}
    out["control"]["n"] = k_ctl
    print("random-time sh_asia control (x0.5, 4 seeds):", out["control"], flush=True)
    for nm, (Ve, Vf) in var.items():
        rs, Tr = real_slot(Ve, Vf)
        out["real"][nm] = {s: {**rs[s], **path_stats(Tr, s)} for s in rs}
        print("   real 2026 calendar path", nm, {s: (out["real"][nm][s]["per_month"], out["real"][nm][s]["payouts"], out["real"][nm][s]["tpw"]) for s in rs}, flush=True)
    dump(out, "atx2_asia.json")
    print(f"done ({time.time() - t0:.0f}s)", flush=True)
    return out


SUB_POOL = ("EMA", "MD", "SR", "SHA")


def subsets():
    out = []
    for r in range(1, 5):
        for c in itertools.combinations(SUB_POOL, r):
            out.append(list(c))
    return out


def sub_V(c):
    return V_(members=list(c), w={"SHA": 0.5} if "SHA" in c else {})


def sub_name(c):
    return "+".join(c)


def cmd_r2b_pick(n=200, procs=2, seeds=R2_SEEDS[:10]):
    """Round 2 item 2, step 1 (H1 ONLY): which of EMA / MACD / S/R (and sh_asia x0.5) trade the FUNDED stage, eval unchanged.
    Every subset scored on 2026 H1 only (10 seeds x 200 slot paths); the best H1 mean is frozen in atx2_subset_pick.json
    BEFORE any H2 / 2021-25 number of a subset is computed (step 2 = cmd_r2b_check)."""
    t0 = time.time()
    libs()
    S = subsets()
    jobs = [(f"{sub_name(c)}|{sd}", "slot", {"Ve": today(), "Vf": sub_V(c), "spans": ("H1",), "n": n, "seed": sd}) for c in S for sd in seeds]
    res = dict(pool_map(jobs, procs))
    h1 = {sub_name(c): round(float(np.mean([res[f"{sub_name(c)}|{sd}"]["H1"]["pm"] for sd in seeds])), 1) for c in S}
    pick = max(h1, key=h1.get)
    out = {"built": time.strftime("%Y-%m-%d %H:%M:%S"), "rule": "highest 2026 H1 slot $ a month (mean of 10 seeds x 200 paths), eval unchanged",
           "h1": dict(sorted(h1.items(), key=lambda kv: -kv[1])), "pick": pick, "today": h1["EMA+MD+SR"]}
    dump(out, "atx2_subset_pick.json")
    for k, v in out["h1"].items():
        print(f"   {k:16s} H1 ${v:,.0f}", flush=True)
    print(f"FROZEN pick (H1 only): {pick} ${h1[pick]:,.0f} vs today ${h1['EMA+MD+SR']:,.0f} ({time.time() - t0:.0f}s)", flush=True)
    return out


def cmd_r2b_check(n=200, procs=2, seeds=R2_SEEDS[:10]):
    """Round 2 item 2, step 2: the frozen pick and every other subset (its neighbours) on H2 / 2025 / 2021-24 / each year, the
    pick's rank among the 15 subsets, and the real 2026 calendar path."""
    t0 = time.time()
    V2, A, M, EAB = libs()
    add_years()
    P = json.load(open(os.path.join(OUT, "atx2_subset_pick.json"), encoding="utf-8"))
    pick = P["pick"]
    S = subsets()
    sp = ("H2", "2025", "2021-24", "2022", "2023", "2024")
    jobs = [(f"{sub_name(c)}|{sd}", "slot", {"Ve": today(), "Vf": sub_V(c), "spans": sp, "n": n, "seed": sd}) for c in S for sd in seeds]
    res = dict(pool_map(jobs, procs))
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "pick": pick, "h1": P["h1"], "rows": {}}
    for c in S:
        nm = sub_name(c)
        r = {s: round(float(np.mean([res[f"{nm}|{sd}"][s]["pm"] for sd in seeds])), 1) for s in sp}
        wa, wb = MONTHS["2025"], MONTHS["2021-24"]
        r["2021-25"] = round((r["2025"] * wa + r["2021-24"] * wb) / (wa + wb), 1)
        r["H1"] = P["h1"][nm]
        out["rows"][nm] = r
    b = out["rows"]["EMA+MD+SR"]
    for nm, r in sorted(out["rows"].items(), key=lambda kv: -kv[1]["H1"]):
        g = all(r[s] > b[s] for s in ("H1", "H2", "2021-25"))
        r["gate"] = bool(g) if nm != "EMA+MD+SR" else None
        print(f"{'PICK ' if nm == pick else '     '}{nm:16s} " + " | ".join(f"{s} ${r[s]:,.0f}" for s in ("H1", "H2", "2021-25", "2022", "2023", "2024", "2025")),
              ("PASS" if g else "") if nm != "EMA+MD+SR" else "(today)", flush=True)
    for s in ("H2", "2021-25"):
        order = sorted(out["rows"], key=lambda k: -out["rows"][k][s])
        out[f"pick_rank_{s}"] = order.index(pick) + 1
    out["pick_gate"] = out["rows"][pick]["gate"]
    out["n_subsets_pass"] = sum(1 for r in out["rows"].values() if r.get("gate"))
    rs, Tr = real_slot(today(), sub_V(pick.split("+")))
    out["real_pick"] = {s: {**rs[s], **path_stats(Tr, s)} for s in rs}
    print("pick rank among 15 subsets: H2", out["pick_rank_H2"], "2021-25", out["pick_rank_2021-25"], "| real path",
          {s: out["real_pick"][s]["per_month"] for s in rs}, f"({time.time() - t0:.0f}s)", flush=True)
    dump(out, "atx2_subset_check.json")
    return out


# ================================================================================================ round 2 item 3: BLITZ as a funded-only member
PLAY_FUNDED = [None]
BLZ_CACHE = os.path.join(ROOT, "research", "runs", "_cache", "atx2_blitz_units.pkl")


def blz_q(t, st, w, fz):
    """BLITZ's own funded size (blitz-25k.md funded pick, scalp_na_lib.qty frac): min($150, 10% of the room) x w, <= 0.9 x the
    soft daily loss left, 1 micro while a stop-out fits half the room; fz "blz_1micro" = always 1 micro."""
    from tools import atlas_funded as AF
    V2, A, M, EAB = libs()
    room = float(st["room"])
    dll_left = 600.0 + float(st.get("cum", 0.0))
    rpm = (float(t["risk"]) + 0.25) * 2.0 + 1.90
    if fz.get("blz_1micro"):
        q = 1 if rpm <= min(0.5 * room, 0.9 * dll_left) else 0
    else:
        b = min(min(150.0, 0.10 * room) * w, 0.9 * dll_left)
        if b <= 0:
            return 0
        q = int(min(20, b // rpm))
        if q == 0 and rpm <= min(0.5 * room, 0.9 * dll_left):
            q = 1
    if q <= 0:
        return 0
    return int(EAB.dll_guard({"qty": q, "reasons": []}, float(t["risk"]), AF.SPEC["rules"], st)["qty"])


def play_day_blz(L, day, bal, floor, session, rule, pre=False, max_day=2, lost=None, litcfg=None, dll=600.0, reserve=False, extra=None):
    """tools/second_mix.play_day (one position, the soft daily loss, the floor at each trade's worst point) with BLITZ ("BLZ")
    counted on its own: ATLAS's members keep max 2 a day, BLITZ max 6 a day and no new BLITZ entry once the day is +$400 (its
    funded day take-profit); BLITZ only while no other ATLAS trade is open (one position)."""
    V2, A, M, EAB = libs()
    cum, busy, n, nb, recs = 0.0, 0, 0, 0, []
    for t in L:
        if cum <= -dll:
            break
        isb = t["src"] == "BLZ"
        if t["entry_t"] < busy:
            continue
        if isb and (nb >= 6 or cum >= 400.0):
            continue
        if not isb and n >= max_day:
            continue
        st = {"profit": bal, "cum": cum, "room": bal + cum - floor, "session": session, "n_today": 0, **(extra or {})}
        q = M.second_q(t, st, rule)
        if q <= 0:
            continue
        pts, w1, ex, xt = t["pts"], t["w1"], t["exit"], t["exit_t"]
        pnl = pts * M.PV * q - M.ECOMM * q
        low = min(0.0, w1 * M.PV * q - M.ECOMM * q, pnl)
        if cum + low <= -dll:
            pnl = -dll - cum - M.SLIP * M.PV * q
            low = pnl
        recs.append({"day": day, "entry_t": t["entry_t"], "exit_t": xt, "dir": t["dir"], "exit": ex, "risk": t["risk"], "tgt": t["tgt"],
                     "src": t["src"], "qty": q, "pnl": round(pnl, 2), "low": round(low, 2), "risk_usd": round(t["risk"] * M.PV * q, 2)})
        busy = xt
        if isb:
            nb += 1
        else:
            n += 1
        if bal + cum + low <= floor:
            return cum, recs, True
        cum += pnl
    return cum, recs, False


def blz_units(placebo=None):
    """BLITZ's research trades (tools/blitz25k_lib.trades({}, "lit+atlas"): 1m in 2026, 5m in 2021-25) -> account-B units "BLZ"
    (no bar path: an opposite LIT entry during a BLITZ trade drops it, conservative, as the NA member)."""
    import pickle
    key = f"p{placebo}" if placebo is not None else "real"
    C = pickle.load(open(BLZ_CACHE, "rb")) if os.path.exists(BLZ_CACHE) else {}
    if key not in C:
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        from tools import blitz25k_grid as G
        from tools import blitz25k_lib as K
        G.prep()
        TT = K.trades({}, "lit+atlas", placebo)
        out = []
        for tf, cut in ((1, lambda d: d >= "2026-01-01"), (5, lambda d: d < "2026-01-01")):
            for t in TT[tf]:
                if not cut(t["day"]):
                    continue
                r = float(t["risk_pts"])
                if r <= 0:
                    continue
                out.append({"day": t["day"], "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "dir": int(t["dir"]), "exit": str(t["exit_kind"]),
                            "risk": r, "tgt": 2.0 * r, "pts": float(t["pts"]), "w1": float(max(-(r + 0.25), min(0.0, -float(t["mae_pts"]), float(t["pts"])))),
                            "src": "BLZ", "pt": np.zeros(0, np.int64), "po": np.zeros(0), "pw": np.zeros(0)})
        C[key] = out
        pickle.dump(C, open(BLZ_CACHE, "wb"))
    return C[key]


def blz_install(placebos=()):
    V2, A, M, EAB = libs()
    U = M.units()
    if "BLZ" not in U:
        U["BLZ"] = blz_units()
    for sd in placebos:
        if f"BLZ_p{sd}" not in U:
            U[f"BLZ_p{sd}"] = [{**u, "src": "BLZ"} for u in blz_units(sd)]
    return U


def cmd_r2c(n=200, procs=2, seeds=R2_SEEDS[:10], ctl=(1, 2, 3, 4, 5, 6), ctl_seeds=4):
    """Round 2 item 3: BLITZ as a FUNDED-ONLY member of ATLAS's 25K (eval unchanged): its own funded size x0.5 / x1.0 or 1 micro,
    one ATLAS position at a time, its own 6 a day and +$400 day take-profit; control = BLITZ's random-direction twins
    (tools/blitz25k_lib placebo: the same signal bars, a coin-flip side; random-time copies need a re-simulation)."""
    t0 = time.time()
    V2, A, M, EAB = libs()
    add_years()
    U = blz_install(ctl)
    print("BLITZ units", len(U["BLZ"]), "2026", sum(1 for u in U["BLZ"] if u["day"] >= "2026-01-01"), flush=True)
    PLAY_FUNDED[0] = play_day_blz
    B = lambda w, sub=None: V_(members=MEM + ["BLZ"], w={"BLZ": w}, **({"sub": {"BLZ": sub}} if sub else {}))
    var = {"today": (today(), None, None), "funded + BLITZ x0.5": (today(), B(0.5), None), "funded + BLITZ x1.0": (today(), B(1.0), None),
           "funded + BLITZ 1 micro": (today(), B(1.0), {"blz_1micro": True})}
    jobs = [(f"{nm}|{sd}", "slot", {"Ve": Ve, "Vf": Vf, "fz": fz, "spans": R2_SPANS, "n": n, "seed": sd}) for nm, (Ve, Vf, fz) in var.items() for sd in seeds]
    C_ = {f"dir{c}": B(0.5, f"BLZ_p{c}") for c in ctl}
    jobs += [(f"{nm}|{sd}", "slot", {"Ve": today(), "Vf": Vf, "spans": SPANS4, "n": n, "seed": sd}) for nm, Vf in C_.items() for sd in seeds[:ctl_seeds]]
    res = dict(pool_map(jobs, procs))
    T = seeds_table(res, list(var), R2_SPANS, seeds)
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "table": T, "paired": {}, "gate": {}, "real": {}}
    for nm in var:
        if nm == "today":
            continue
        pr = paired(T, nm)
        out["paired"][nm] = pr
        out["gate"][nm] = all(pr[s]["diff"] > 0 for s in ("H1", "H2", "2021-25"))
        print(f"{nm:24s} " + " | ".join(f"{s} ${T[nm][s]['mean']:,.0f} ({pr[s]['diff']:+.0f}, {int(100 * pr[s]['win_share'])}%)"
                                         for s in ("H1", "H2", "2021-25", "2022", "2023", "2024", "2025")), "PASS" if out["gate"][nm] else "", flush=True)
    print("today                    " + " | ".join(f"{s} ${T['today'][s]['mean']:,.0f}" for s in ("H1", "H2", "2021-25", "2022", "2023", "2024", "2025")), flush=True)
    CT = seeds_table(res, list(C_) + ["funded + BLITZ x0.5", "today"], SPANS4, seeds[:ctl_seeds])
    out["control"] = {s: {"real": CT["funded + BLITZ x0.5"][s]["mean"], "today": CT["today"][s]["mean"],
                          "rand_dir_mean": round(float(np.mean([CT[c][s]["mean"] for c in C_])), 1),
                          "rand_ge_real": round(float(np.mean([CT[c][s]["mean"] >= CT["funded + BLITZ x0.5"][s]["mean"] for c in C_])), 2)}
                      for s in ("H1", "H2", "2021-25")}
    print("random-direction BLITZ control (x0.5, 4 seeds):", out["control"], flush=True)
    for nm, (Ve, Vf, fz) in var.items():
        rs, Tr = real_slot(Ve, Vf, fz)
        out["real"][nm] = {s: {**rs[s], **path_stats(Tr, s)} for s in rs}
        print("   real calendar path", nm, {s: (out["real"][nm][s]["per_month"], out["real"][nm][s]["payouts"]) for s in rs}, flush=True)
    PLAY_FUNDED[0] = None
    dump(out, "atx2_blitz.json")
    print(f"done ({time.time() - t0:.0f}s)", flush=True)
    return out


def cmd_save2():
    """runs atx2_* (round 2): trades = the slot on each span's real sessions (eval + funded trades); the 20-seed slot numbers
    and the controls are in the verdict (from atx2_asia.json / atx2_subset_check.json / atx2_blitz.json)."""
    from tools import runlib as rl
    V2, A, M, EAB = libs()
    sess = sorted(set(M.units()["sessions"]))
    J = lambda f: json.load(open(os.path.join(OUT, f), encoding="utf-8")) if os.path.exists(os.path.join(OUT, f)) else None
    a, sb, bz = J("atx2_asia.json"), J("atx2_subset_check.json"), J("atx2_blitz.json")
    rows = []
    if a:
        T = a["table"]
        for w, st in ((0.5, "promising"), (0.75, "promising"), (1.0, "rejected")):
            nm = f"funded + sh_asia x{w:g}"
            pr = a["paired"][nm]
            vt = (f"Eval = today's ATLAS; once funded + sh_asia x{w:g} (market entry). Slot $/mo (20 seeds x 200 paths): "
                  + "; ".join(f"{s} ${T[nm][s]['mean']:,.0f} vs ${T['today'][s]['mean']:,.0f} ({pr[s]['diff']:+.0f}, {int(100 * pr[s]['win_share'])}% of seeds up)"
                              for s in ("H1", "H2", "2021-25", "2022", "2023", "2024", "2025"))
                  + f". Random-time sh_asia x0.5 (12 copies): H1 ${a['control']['H1']['rand_mean']:,.0f}, H2 ${a['control']['H2']['rand_mean']:,.0f}. "
                  + ("Passes the slot gate; the clean H2 gain is small and the real calendar path is flat in H2." if w < 1 else "H2 below today: rejected."))
            rows.append((f"atx2_funded_asia_w{str(w).replace('.', '')}", f"Eval = today; once funded + sh_asia x{w:g} (round 2, config A clean)",
                         today(), A1f(w), None, st, vt, False))
    if bz:
        T = bz["table"]
        for nm, rid, Vf, fz in (("funded + BLITZ x0.5", "atx2_funded_blitz_w05", V_(members=MEM + ["BLZ"], w={"BLZ": 0.5}), None),
                                ("funded + BLITZ 1 micro", "atx2_funded_blitz_1micro", V_(members=MEM + ["BLZ"], w={"BLZ": 1.0}), {"blz_1micro": True})):
            pr = bz["paired"][nm]
            ok = bz["gate"][nm]
            vt = (f"Eval = today's ATLAS; once funded + BLITZ ({nm[9:]}). Slot $/mo (10 seeds x 200 paths): "
                  + "; ".join(f"{s} ${T[nm][s]['mean']:,.0f} vs ${T['today'][s]['mean']:,.0f} ({pr[s]['diff']:+.0f})" for s in ("H1", "H2", "2021-25"))
                  + (". Passes the slot gate." if ok else ". Fails the slot gate."))
            rows.append((rid, f"Eval = today; once funded + BLITZ {nm[15:]} (round 2)", today(), Vf, fz, "rejected", vt + " Rejected: its random-direction twins reach its H2 slot in 2 of 6 draws, 2021-25 is +$2-3 (70% of seeds), 2024 is below today on every seed, and the real H2 calendar path pays $182 vs $414 a month.", True))
    for rid, title, Ve, Vf, fz, st, vt, isb in rows:
        if isb:
            blz_install()
            PLAY_FUNDED[0] = play_day_blz
        rs, Tt = real_slot(Ve, Vf, fz)
        PLAY_FUNDED[0] = None
        vt2 = vt + " Real-session slot: " + "; ".join(f"{s} ${rs[s]['per_month']:,}/mo ({rs[s]['payouts']} payouts)" for s in rs)
        TR = _runlib_trades(Tt)
        rl.save(rid, title, "risk", "ATLAS 2026-10-30 b round 2: which members should trade ATLAS's FUNDED 25K (eval unchanged)?",
                params={"eval": Ve, "funded": Vf, "fz": fz or {}}, sizing={"eval": "engine/account_b.qty need", "funded": "funded preset x weight; BLITZ: its own 10% / $150"},
                trades=TR, scored=rl.score(TR, sess), status=st, verdict=vt2, notes="tools/atx_edge.py r2a / r2b_* / r2c",
                writeup="atlas-edge-2026-10-30b", tags=["atlas", "account_b", "25k", "funded", "slot", "round2"])
        print("saved", rid, flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "base"
    {"base": cmd_base, "sched": cmd_sched, "funded": cmd_funded, "win": cmd_win, "maxd": lambda: cmd_family("maxd"),
     "stage": lambda: cmd_family("stage"), "placebo": cmd_placebo, "final": cmd_final, "checks": cmd_checks, "save": cmd_save, "round4": cmd_round4, "why": cmd_why, "e4grid": cmd_e4grid, "fmin": cmd_fmin,
     "r2a": cmd_r2a, "r2b_pick": cmd_r2b_pick, "r2b_check": cmd_r2b_check, "r2c": cmd_r2c, "save2": cmd_save2}[cmd]()
