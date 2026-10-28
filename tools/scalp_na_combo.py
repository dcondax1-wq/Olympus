"""BLITZ next to the existing accounts (owner 2026-10-28, research/writeups/scalp-na-mffu.md part 4). Paper research only.

  ATLAS 25K   BLITZ as a 4th member of account B: tools/atlas.py score (members EMA + MD + SR + "NA", the real account-B
              rules: one position, max 2 trades a day, $600 soft daily loss, need size for ATLAS's members, no-hedge vs LIT's
              trades AND armed setups, HEDGE cut). BLITZ's micros: f x room, $ cap, inside the soft daily loss (+ the engine's
              dll_guard). Variants: max trades a day 2 (as built) / 3 / 4, "first come" or ATLAS priority (a BLITZ trade
              is skipped while an ATLAS member holds and flattened at the next member entry).
  LIT 50K     BLITZ on LIT's own Builder 50K, only while LIT is flat: candidates are dropped while LIT holds a trade or has
              a setup armed; a BLITZ trade still open when LIT enters is flattened at that bar's open (LIT priority, 1 tick).
              Eval: tools/second_mix.score_span (pre = LIT priority, reserve = one slot kept for LIT, max 2 trades a day as
              the engine's guards; also 3) on its LIT units; money: tools/uprisk.py's Eval / Funded (bit-for-bit engine
              sizing, the live LIT eval two_week room_f 0.8 and the uprisk funded rule) through tools/div_stack's NA
              dispatch, 6-month account slots on Monte Carlo paths (5-session blocks, seed 23).

    python -X utf8 tools/scalp_na_combo.py atlas          # ATLAS + BLITZ evals (cap 2 / 3, first come / ATLAS first) -> na_combo_atlas.json
    python -X utf8 tools/scalp_na_combo.py atlas_funded   # ATLAS's funded 25K (live preset) +/- BLITZ -> na_combo_atlas_funded.json
    python -X utf8 tools/scalp_na_combo.py atlas6         # the same with the daily cap at 6 -> na_combo_atlas_max6.json
    python -X utf8 tools/scalp_na_combo.py lit            # LIT 50K + BLITZ: second_mix eval windows + slots -> na_combo_lit.json
    python -X utf8 tools/scalp_na_combo.py lit_grid       # size grid, eval / funded-only, placebo, plain NA -> na_combo_lit_grid.json
    python -X utf8 tools/scalp_na_combo.py lit_checks     # paired gain, slippage, late entry, real 2026 path -> na_combo_lit_checks.json
    python -X utf8 tools/scalp_na_combo.py lit_why        # funded 50K only: trading profit vs payouts -> na_combo_lit_why.json
"""
from __future__ import annotations

import collections
import copy
import json
import os
import sys
import time
import warnings

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
warnings.filterwarnings("ignore")
import logging  # noqa: E402
logging.getLogger("engine.sizing").setLevel(logging.ERROR)
from tools import scalp_na_lib as N  # noqa: E402
from tools import scalp_na as X  # noqa: E402

OUT = os.path.join(ROOT, "research", "scalp")
SLIP = 0.25


# ================================================================================================ BLITZ units
def units(T, B):
    """BLITZ trades -> tools/second_mix units (per-micro points with slippage, worst open points, the bar path for a cut)."""
    out = []
    o, l, h, t = B["o"], B["l"], B["h"], B["t"]
    for x in T:
        D = x["dir"]
        j = int(np.searchsorted(t, x["entry_t"]))
        xk = int(np.searchsorted(t, x["exit_t"] - 60 * B["tf"]))
        idx = np.arange(j + 1, xk + 1)
        po = D * (o[idx] - x["entry"])
        lo = (l[j:xk] - x["entry"]) if D > 0 else (x["entry"] - h[j:xk])
        run = np.minimum.accumulate(np.r_[0.0, lo])
        pw = np.maximum(np.round(run[1:len(idx) + 1] if len(idx) else np.zeros(0), 2), -(x["risk_pts"] + SLIP))
        w1 = max(-(x["risk_pts"] + SLIP), min(0.0, -x["mae_pts"], x["pts"]))
        out.append({"day": x["day"], "entry_t": x["entry_t"], "exit_t": x["exit_t"], "dir": D, "exit": x["exit_kind"],
                    "risk": round(x["risk_pts"], 4), "tgt": round(x["risk_pts"], 4), "pts": round(x["pts"], 4), "w1": round(w1, 4),
                    "src": "NA", "pt": t[idx].astype(np.int64), "po": np.round(po, 2), "pw": pw})
    return out


def blitz_units(lit_flat=False, maxday=None, placebo=None, raw=False, late=0, xslip=0.0):
    """2021-25 from 5m, 2026 from 1m. lit_flat: BLITZ candidates dropped while LIT holds / has a setup armed (LIT's account).
    raw: the plain NA scalp (no prior-day range filter)."""
    names = ([] if raw else [X.PICK1[1]]) + (["lit_flat"] if lit_flat else [])
    p = {"maxday": maxday} if maxday else None
    TT = X.blitz_trades(p, names=tuple(names), placebo=placebo, late=late)
    U5 = [u for u in units(TT[5], N.bars(5)) if u["day"] < "2026-01-01"]
    U1 = [u for u in units(TT[1], N.bars(1)) if u["day"] >= "2026-01-01"]
    if xslip:                   # stress: extra slippage on the entry and on the exit (points per side)
        U5 = [{**u, "pts": u["pts"] - 2 * xslip, "w1": u["w1"] - xslip, "po": u["po"] - xslip} for u in U5]
        U1 = [{**u, "pts": u["pts"] - 2 * xslip, "w1": u["w1"] - xslip, "po": u["po"] - xslip} for u in U1]
    return U5 + U1


def cut_on(U, by_other, same_dir_too=True):
    """Flatten a BLITZ unit at the first entry of another trade (by_other: day -> [(entry_t, exit_t, dir)]) inside it; drop
    it when it starts while one is open."""
    from tools import second_mix as M
    out = []
    for u in U:
        os_ = by_other.get(u["day"], ())
        if any(a <= u["entry_t"] < z for a, z, _ in os_):
            continue
        nxt = min((a for a, z, _ in os_ if u["entry_t"] < a < u["exit_t"]), default=None)
        if nxt is not None:
            pts, w1 = M.cut_at(u, nxt)
            u = {**u, "pts": pts, "w1": w1, "exit_t": nxt, "exit": "PRE"}
        out.append(u)
    return out


# ================================================================================================ ATLAS (account B, 25K)
def na_qty(t, st, f, cap, maxq, dll):
    from engine import sizing as SZ
    room = max(0.0, st["room"])
    left = dll + st["cum"]
    b = min(cap, f * room, 0.9 * left)
    loss1 = (t["risk"] + SZ.TW_DLL_SLIP) * SZ.TW_PV + SZ.TW_COMM
    if b <= 0:
        return 0
    q = int(min(maxq, b // ((t["risk"] + 0.25) * 2.0 + 1.9)))
    if q == 0 and loss1 <= min(0.5 * room, 0.9 * left):
        q = 1
    return max(0, min(q, int(max(0.0, left) / loss1 + 1e-9)))


def atlas_score(f=None, cap=None, maxday=2, prio=False, spans=("H1", "H2", "2025", "2021-24")):
    """ATLAS today (f None) or ATLAS + BLITZ (f, cap) under tools/atlas.py's real account-B scorer."""
    from tools import atlas as A
    from tools import second_mix as M
    M.units()
    V = copy.deepcopy(A.BASE)
    if f is not None:
        key = ("NA", prio)
        if key not in _AU:
            U = blitz_units()
            if prio:                               # ATLAS priority: its own members' trades block / flatten BLITZ
                by = collections.defaultdict(list)
                for nm in A.BASE["members"]:
                    for u in A.member_units(nm, A.BASE):
                        by[u["day"]].append((u["entry_t"], u["exit_t"], u["dir"]))
                U = cut_on(U, by)
            _AU[key] = U
        M.units()["NA"] = _AU[key]
        V["members"] = V["members"] + ["NA"]
    orig_q = A.q_variant
    orig_ru = A.member_units

    def q_variant(t, st, V_):
        if t.get("src") == "NA":
            return na_qty(t, st, f, cap, 20, 600.0)
        return orig_q(t, st, V_)

    def member_units(name, V_):
        if name == "NA":
            return M.units()["NA"]
        return orig_ru(name, V_)
    A.q_variant, A.member_units = q_variant, member_units
    try:
        out = {}
        U = A.account_units(V)
        with A.Plan(V) as pl:
            inner = M.play_day

            def play_day(L, day, bal, floor, session, rule, pre=False, max_day=2, lost=None, litcfg=None, dll=None, reserve=True, extra=None):
                return inner(L, day, bal, floor, session, rule, pre, maxday, lost, litcfg, dll, reserve, extra)
            M.play_day = play_day
            from tools import second_account_b as AB
            for s in spans:
                o, T = AB.score(U, "atlas", s, V.get("frule") or pl.safe_rule)
                out[s] = o
    finally:
        A.q_variant, A.member_units = orig_q, orig_ru
        M.units().pop("NA", None)
    return out


_AU = {}
AKEEP = ("p10", "f10", "s10", "dead10", "dec10", "p15", "f15", "p20", "f20", "pass_med", "slow_pass", "p60", "fund_paid_3m",
         "fund_paid_6m", "fund_lost_6m", "ev_eval_3m", "net", "per_month", "pf", "dd", "tpw", "b2b", "by_src", "path_net_less_fees")


def cmd_atlas():
    t0 = time.time()
    rows = []
    base = atlas_score()
    rows.append({"name": "ATLAS today", **{s: {k: base[s].get(k) for k in AKEEP} for s in base}})
    for f, cap in ((0.1, 150.0), (0.2, 150.0), (0.2, 300.0), (0.3, 300.0)):
        for md in (2, 3):
            for prio in (False, True):
                o = atlas_score(f, cap, md, prio)
                rows.append({"name": f"ATLAS + BLITZ f{f} cap{int(cap)} max{md}/day{' ATLAS-priority' if prio else ''}",
                             **{s: {k: o[s].get(k) for k in AKEEP} for s in o}})
                print(f"{rows[-1]['name']} ({time.time() - t0:.0f}s)", flush=True)
    for r in rows:
        print(f"\n{r['name']}")
        for s in ("H1", "H2", "2025", "2021-24"):
            x = r[s]
            print(f"   {s:7s} 2w {x['p10']:5.1f}/{x['dead10']:4.1f} (fail {x['f10']}, stuck {x['s10']}) 3w {x['p15']}/{x['f15']} 1m {x['p20']}/{x['f20']} "
                  f"med {x['pass_med']} slow {x['slow_pass']} p60 {x['p60']} | path ${x['net']:+,} ({x['per_month']:+,}/mo) PF {x['pf']} DD {x['dd']} "
                  f"tpw {x['tpw']} | funded 3m ${x['fund_paid_3m']} 6m ${x['fund_paid_6m']} lost {x['fund_lost_6m']}% | EV/eval 3m ${x['ev_eval_3m']} | {x['by_src']}")
    json.dump(rows, open(os.path.join(OUT, "na_combo_atlas.json"), "w"), default=float)
    return rows


def atlas_funded(f=None, cap=None, maxday=2, prio=False, n=1000, spans=("H1", "H2", "2025", "2021-24")):
    """ATLAS's funded 25K (tools/atlas_funded.mc: the live funded preset via engine/account_b.qty, MFFU payout tracker,
    6-month MC accounts) with or without BLITZ (sized f x room, $ cap, inside the $600 soft daily loss)."""
    from tools import atlas as A
    from tools import atlas_funded as AF
    from tools import second_mix as M
    M.units()
    V = copy.deepcopy(A.BASE)
    if f is not None:
        key = ("NA", prio)
        if key not in _AU:
            atlas_score(f, cap, maxday, prio, spans=("H1",))       # builds the units
        M.units()["NA"] = _AU[key]
        V["members"] = V["members"] + ["NA"]
    orig_ru = A.member_units
    A.member_units = lambda name, V_: M.units()["NA"] if name == "NA" else orig_ru(name, V_)
    try:
        U = A.account_units(V)
    finally:
        A.member_units = orig_ru
        M.units().pop("NA", None)
    by = collections.defaultdict(list)
    for t in sorted(U, key=lambda t: t["entry_t"]):
        by[t["day"]].append(t)

    def qfn(t, st):
        if t.get("src") == "NA":
            return na_qty(t, st, f, cap, 20, 600.0)
        return AF.q_live(t, st)
    inner = M.play_day

    def play_day(L, day, bal, floor, session, rule, pre=False, max_day=2, lost=None, litcfg=None, dll=M.DLL, reserve=True, extra=None):
        return inner(L, day, bal, floor, session, rule, pre, maxday, lost, litcfg, dll, reserve, extra)
    M.play_day = play_day
    try:
        with AF.Sizer(qfn):
            return {s: AF.mc(by, s, n) for s in spans}
    finally:
        M.play_day = inner


def cmd_atlas_funded():
    rows = []
    for nm, f, cap, md, pr in (("ATLAS today", None, None, 2, False), ("+ BLITZ f0.1 cap150 max2", 0.1, 150.0, 2, False),
                               ("+ BLITZ f0.2 cap300 max2 ATLAS-priority", 0.2, 300.0, 2, True),
                               ("+ BLITZ f0.2 cap300 max3 ATLAS-priority", 0.2, 300.0, 3, True),
                               ("+ BLITZ f0.3 cap300 max3 ATLAS-priority", 0.3, 300.0, 3, True)):
        o = atlas_funded(f, cap, md, pr)
        rows.append({"name": nm, **o})
        print(f"{nm:42s} " + " | ".join(f"{s} ${x['per_month']}/mo (p10 ${x['per_month_p10']}) lost {x['lost_6m']}% stuck {x['stuck_6m']}% "
                                         f"first {x['first_med']} pays {x['payouts_6m']}" for s, x in o.items()), flush=True)
    json.dump(rows, open(os.path.join(OUT, "na_combo_atlas_funded.json"), "w"), default=float)


def cmd_atlas6():
    """ATLAS today vs + BLITZ with the account's daily cap raised to 6 (BLITZ needs its trend-day re-entries), ATLAS first."""
    rows = []
    for nm, f, cap, md, pr in (("ATLAS today max2", None, None, 2, False), ("ATLAS today max6", None, None, 6, False),
                               ("+ BLITZ f0.1 cap300 max6 ATLAS-priority", 0.1, 300.0, 6, True),
                               ("+ BLITZ f0.2 cap300 max6 ATLAS-priority", 0.2, 300.0, 6, True),
                               ("+ BLITZ f0.2 cap450 max6 ATLAS-priority", 0.2, 450.0, 6, True)):
        o = atlas_score(f, cap, md, pr)
        fu = atlas_funded(f, cap, md, pr, n=1000)
        rows.append({"name": nm, "eval": {s_: {k: o[s_].get(k) for k in AKEEP} for s_ in o}, "funded": fu})
        print(nm + ": " + " | ".join(f"{s_} 2w {o[s_]['p10']}/{o[s_]['dead10']} p60 {o[s_]['p60']} funded ${fu[s_]['per_month']}/mo stuck {fu[s_]['stuck_6m']}%"
                                    for s_ in o), flush=True)
    json.dump(rows, open(os.path.join(OUT, "na_combo_atlas_max6.json"), "w"), default=float)


# ================================================================================================ LIT (its 50K)
def lit_by_day():
    """LIT's live trades + armed windows: day -> [(start, end, dir)] (anything that blocks / pre-empts BLITZ on LIT's account)."""
    by = collections.defaultdict(list)
    for d, ts in N.lit_trades().items():
        by[d] += [(e, x, dd) for e, x, dd in ts]
    return by


def lit_eval(rule_f=None, cap=None, maxday=2, spans=("H1", "H2", "2025", "2021-24")):
    """tools/second_mix.score_span: LIT units + BLITZ (LIT priority: pre=True, one slot reserved for LIT)."""
    from tools import second_mix as M
    U = list(M.units()["LIT"])
    if rule_f is not None:
        if "lit" not in _AU:
            _AU["lit"] = blitz_units(lit_flat=True)
        U += _AU["lit"]
    inner = M.second_q
    old_play = M.play_day

    def second_q(t, st, rule):
        if rule == "blitz":
            return na_qty(t, st, rule_f, cap, 40, M.DLL)
        return inner(t, st, rule)

    def play_day(L, day, bal, floor, session, rule, pre=False, max_day=2, lost=None, litcfg=None, dll=M.DLL, reserve=True, extra=None):
        return old_play(L, day, bal, floor, session, rule, pre, maxday, lost, litcfg, dll, reserve, extra)
    M.second_q, M.play_day = second_q, play_day
    try:
        return {s: M.score_span(U, "blitz", s, pre=True, reserve=True)[0] for s in spans}
    finally:
        M.second_q, M.play_day = inner, old_play


def atlas_by_day():
    """ATLAS's trades on account B (tools/atlas.account_units(BASE)): day -> [(entry, exit, dir)]."""
    if "atlas_bd" not in _AU:
        from tools import atlas as A
        from tools import second_mix as M
        M.units()
        by = collections.defaultdict(list)
        for u in A.account_units(A.BASE):
            by[u["day"]].append((u["entry_t"], u["exit_t"], u["dir"]))
        _AU["atlas_bd"] = by
    return _AU["atlas_bd"]


def yield_to(U, by_other):
    """Cross-account no-hedge, the other account first: a BLITZ unit is skipped when it starts while the other account holds
    the OPPOSITE side, and flattened at an opposite entry of the other account inside it."""
    from tools import second_mix as M
    out = []
    for u in U:
        os_ = [(a, z) for a, z, d in by_other.get(u["day"], ()) if d != u["dir"]]
        if any(a <= u["entry_t"] < z for a, z in os_):
            continue
        nxt = min((a for a, z in os_ if u["entry_t"] < a < u["exit_t"]), default=None)
        if nxt is not None:
            pts, w1 = M.cut_at(u, nxt)
            u = {**u, "pts": pts, "w1": w1, "exit_t": nxt, "exit": "HEDGE"}
        out.append(u)
    return out


def lit_money(nc=None, n=1000, spans=("H1", "H2", "REF"), maxday=None, nc_eval="same", placebo=None, atlas_yield=True, raw=False,
              late=0, xslip=0.0, per_path=False):
    """6-month account slots (eval -> funded -> payouts, net of every eval) for LIT alone (nc None) or LIT + BLITZ (nc =
    {"f", "cap"}), with tools/uprisk + tools/div_stack (live LIT eval / funded sizing). nc_eval: BLITZ's size in the eval
    ("same" = nc, None = BLITZ only once funded). atlas_yield: BLITZ never opposite to ATLAS on account B."""
    import uprisk as U
    import div_stack as DS
    S, BYL = U.load()
    # entry times of the LIT units (the ledger rows in the order uprisk.trades reads them) so a day's trades run in time order
    import csv
    import datetime as dt
    ets = collections.defaultdict(list)
    for r in csv.DictReader(open(N.LEDGER, encoding="utf-8")):
        if r["trade_id"].startswith(("T-2026", "REF-")):
            ets[r["entry_fill_at"][:10]].append(int(dt.datetime.fromisoformat(r["entry_fill_at"][:25]).timestamp()))
    for i, x in enumerate(BYL):
        for t, e in zip(x, ets.get(S[i], [])):
            t["src"] = "lit"
            t["et"] = e
    BY = BYL
    if nc is not None:
        k = ("litm", maxday, placebo, atlas_yield, raw, late, xslip)
        if k not in _AU:
            T = blitz_units(lit_flat=True, maxday=maxday, placebo=placebo, raw=raw, late=late, xslip=xslip)
            T = cut_on(T, lit_by_day())
            if atlas_yield:
                T = yield_to(T, atlas_by_day())
            byn = collections.defaultdict(list)
            for t in T:
                byn[t["day"]].append({"day": t["day"], "src": "na", "risk": t["risk"], "risk_pts": t["risk"], "tgt": None, "tgt_pts": None,
                                      "pts": t["pts"], "w1": t["w1"], "size_mult": 1.0, "et": t["entry_t"], "xt": t["exit_t"],
                                      "dir": t["dir"], "exit": t["exit"]})
            _AU[k] = byn
        byn = _AU[k]
        BY = [sorted(BYL[i] + byn.get(d, []), key=lambda t: t.get("et", 0)) for i, d in enumerate(S)]
    out = {}
    for sp in spans:
        P = DS.paths(S, sp, n)
        nce = nc if nc_eval == "same" else nc_eval
        mk_e = (lambda: DS.Eval(DS.LIT_E50, "builder50k", nc=nce))
        mk_f = (lambda: DS.Funded("builder50k", DS.LIT_F50, nc=nc))
        R = DS.life(BY, P, mk_e, mk_f, 91.80, U.LEN)
        net = np.array([r["net"] for r in R]) / (U.LEN / 21.0)
        if per_path:
            out[sp + "_paths"] = [float(x) for x in net]
        out[sp] = {"slot_pm": round(float(net.mean())), "slot_p10": round(float(np.percentile(net, 10))),
                   "slot_lose": round(100.0 * float((net < 0).mean()), 1), "funded_6m": round(float(np.mean([r["funded"] for r in R])), 2),
                   "evals_6m": round(float(np.mean([r["evals"] for r in R])), 2), "lost_6m": round(float(np.mean([r["lost"] for r in R])), 2)}
        PE = DS.paths(S, sp, n, length=60)
        out[sp].update(DS.eval_mc(BY, PE, mk_e, 91.80))
    return out


def cmd_lit():
    t0 = time.time()
    rows = []
    for nm, f, cap, md in (("LIT alone", None, None, 2), ("LIT + BLITZ f0.05 cap150 max2", 0.05, 150.0, 2), ("LIT + BLITZ f0.1 cap300 max2", 0.1, 300.0, 2),
                           ("LIT + BLITZ f0.2 cap600 max2", 0.2, 600.0, 2), ("LIT + BLITZ f0.1 cap300 max3", 0.1, 300.0, 3),
                           ("LIT + BLITZ f0.2 cap600 max3", 0.2, 600.0, 3)):
        o = lit_eval(f, cap, md)
        rows.append({"name": nm, "eval": o})
        print(f"{nm} ({time.time() - t0:.0f}s)")
        for s in o:
            x = o[s]
            print(f"   {s:7s} 2w {x['p10']:5.1f}/{x['f10']:4.1f} 1m {x['p20']}/{x['f20']} med {x['pass_med']} | path ${x['net']:+,} ({x['per_month']:+,}/mo) "
                  f"PF {x['pf']} DD {x['dd']} tpw {x['tpw']} lit_lost {x['lit_lost']} {x['by_src']}", flush=True)
    money = []
    for nm, nc, md in (("LIT alone", None, None), ("LIT + BLITZ f0.03 cap100", {"f": 0.03, "cap": 100.0}, None),
                       ("LIT + BLITZ f0.05 cap150", {"f": 0.05, "cap": 150.0}, None), ("LIT + BLITZ f0.1 cap300", {"f": 0.1, "cap": 300.0}, None),
                       ("LIT + BLITZ f0.2 cap600", {"f": 0.2, "cap": 600.0}, None), ("LIT + BLITZ f0.1 cap300, 1 a day", {"f": 0.1, "cap": 300.0}, 1)):
        o = lit_money(nc, maxday=md)
        money.append({"name": nm, "money": o})
        print(f"{nm} ({time.time() - t0:.0f}s): " + " | ".join(
            f"{s} slot ${x['slot_pm']}/mo (p10 ${x['slot_p10']}, lose {x['slot_lose']}%) funded {x['funded_6m']}/6m lost {x['lost_6m']} "
            f"eval 2w {x['p10']}/{x['f10']} ever {x['p_ever']} med {x['pass_med']}" for s, x in o.items()), flush=True)
    json.dump({"eval": rows, "money": money}, open(os.path.join(OUT, "na_combo_lit.json"), "w"), default=float)


def _lgjob(a):
    nm, nc, md, nce, pl, raw = a
    return {"name": nm, "nc": nc, "maxday": md, "eval_too": nce == "same", "placebo": pl, "raw": raw,
            "money": lit_money(nc, n=600, maxday=md, nc_eval=nce, placebo=pl, raw=raw)}


def cmd_lit_grid(procs=4):
    """LIT's 50K + BLITZ while LIT is flat: size grid (picked on H1 slot $), BLITZ in the eval too or only once funded,
    max BLITZ trades a day, the plain NA (no filter) and random-direction placebos of the pick."""
    from multiprocessing import Pool
    import itertools
    t0 = time.time()
    atlas_by_day()
    jobs = [("LIT alone", None, None, "same", None, False)]
    for f, cap, md, nce in itertools.product((0.05, 0.075, 0.1, 0.15, 0.2, 0.3), (150.0, 300.0, 450.0, 600.0, 900.0), (None, 2),
                                            ("same", None)):
        jobs.append((f"BLITZ f{f} cap{int(cap)} {'max2/day' if md else 'max6/day'} {'eval+funded' if nce == 'same' else 'funded only'}",
                     {"f": f, "cap": cap}, md, nce, None, False))
    with Pool(procs) as P:
        R = P.map(_lgjob, jobs, chunksize=2)
    base = R[0]["money"]
    rows = sorted(R[1:], key=lambda r: -r["money"]["H1"]["slot_pm"])
    print(f"{len(R)} LIT+BLITZ variants in {time.time() - t0:.0f}s")
    fmt = lambda r: " | ".join(f"{s} ${x['slot_pm']:>5}/mo ({x['slot_pm'] - base[s]['slot_pm']:+5}) lose {x['slot_lose']:4.1f}% 2w {x['p10']}/{x['f10']}"
                              for s, x in r["money"].items())
    print(f"{'LIT alone':48s} " + " | ".join(f"{s} ${x['slot_pm']:>5}/mo lose {x['slot_lose']:4.1f}% 2w {x['p10']}/{x['f10']}" for s, x in base.items()))
    for r in rows[:15]:
        print(f"{r['name']:48s} " + fmt(r))
    good = sum(1 for r in rows if all(r["money"][s]["slot_pm"] > base[s]["slot_pm"] for s in ("H1", "H2", "REF")))
    good2 = sum(1 for r in rows if all(r["money"][s]["slot_pm"] > base[s]["slot_pm"] for s in ("H1", "H2")))
    print(f"{good2}/{len(rows)} beat LIT alone in both 2026 halves, {good}/{len(rows)} also in 2021-25")
    pick = rows[0]
    # placebo + the plain NA for the pick's size
    extra = [(f"PLACEBO seed {sd} ({pick['name']})", pick["nc"], pick["maxday"], "same" if pick["eval_too"] else None, sd, False) for sd in range(8)]
    extra.append((f"plain NA, no filter ({pick['name']})", pick["nc"], pick["maxday"], "same" if pick["eval_too"] else None, None, True))
    with Pool(procs) as P:
        E = P.map(_lgjob, extra, chunksize=1)
    for r in E:
        print(f"{r['name'][:48]:48s} " + fmt(r))
    pl = {s: float(np.mean([r["money"][s]["slot_pm"] for r in E if r["placebo"] is not None])) for s in ("H1", "H2", "REF")}
    print("placebo mean $/mo:", {s: round(v) for s, v in pl.items()}, "pick:", {s: pick["money"][s]["slot_pm"] for s in pl},
          "LIT alone:", {s: base[s]["slot_pm"] for s in pl})
    json.dump({"base": base, "rows": rows, "pick": pick, "extra": E}, open(os.path.join(OUT, "na_combo_lit_grid.json"), "w"), default=float)


PICK_LIT = {"nc": {"f": 0.2, "cap": 450.0}, "maxday": None, "nc_eval": None}      # H1 pick of cmd_lit_grid


def lit_by(nc):
    """(sessions, day lists) of LIT (+ BLITZ when nc) in time order, as lit_money builds them."""
    import uprisk as U
    lit_money(nc, n=1, spans=("H1",), nc_eval=None)
    S, BYL = U.load()
    import csv
    import datetime as dt
    ets = collections.defaultdict(list)
    for r in csv.DictReader(open(N.LEDGER, encoding="utf-8")):
        if r["trade_id"].startswith(("T-2026", "REF-")):
            ets[r["entry_fill_at"][:10]].append(int(dt.datetime.fromisoformat(r["entry_fill_at"][:25]).timestamp()))
    for i, x in enumerate(BYL):
        for t, e in zip(x, ets.get(S[i], [])):
            t["src"], t["et"] = "lit", e
    if nc is None:
        return S, BYL
    byn = _AU[("litm", None, None, True, False, 0, 0.0)]
    return S, [sorted(BYL[i] + byn.get(d, []), key=lambda t: t.get("et", 0)) for i, d in enumerate(S)]


def cmd_lit_why():
    """Funded 50K only (no eval leg): where the extra money comes from (trading profit vs the payout rules)."""
    import div_stack as DS
    out = {}
    for nm, nc in (("LIT alone", None), ("LIT + BLITZ", PICK_LIT["nc"])):
        S, BY = lit_by(nc)
        out[nm] = {}
        for sp in ("H1", "H2", "REF"):
            P = DS.paths(S, sp, 1000)
            o = DS.funded_mc(BY, P, lambda: DS.Funded("builder50k", DS.LIT_F50, nc=nc), "builder50k")
            out[nm][sp] = o
            print(f"{nm:12s} {sp:4s} paid ${o['per_month']}/mo (p10 6m ${o['paid_p10']}) trading ${o['trade_pnl_m']}/mo first pay {o['first_med']} "
                  f"payouts/6m {o['payouts']} months paying {o['months_paying']}/6 held by 50% rule {o['hold_cons']} sessions lost {o['loss_6m']}% "
                  f"max risk ${o['max_risk']} trades/6m {o['trades_6m']}", flush=True)
    json.dump(out, open(os.path.join(OUT, "na_combo_lit_why.json"), "w"), default=float)


def real_path(nc=None, nc_eval=None, a="2026-01-02", z="2026-10-16"):
    """The real 2026 sessions, one slot from the first session (no resampling): LIT alone vs LIT + BLITZ."""
    import uprisk as U
    import div_stack as DS
    S, BYL = U.load()
    lit_money(nc, n=1, spans=("H1",), nc_eval=nc_eval)          # builds the units + the LIT entry times
    BY = BYL
    if nc is not None:
        byn = _AU[("litm", None, None, True, False, 0, 0.0)]
        BY = [sorted(BYL[i] + byn.get(d, []), key=lambda t: t.get("et", 0)) for i, d in enumerate(S)]
    ix = [i for i, d in enumerate(S) if a <= d <= z]
    nce = nc if nc_eval == "same" else nc_eval
    R = DS.life(BY, [ix], lambda: DS.Eval(DS.LIT_E50, "builder50k", nc=nce), lambda: DS.Funded("builder50k", DS.LIT_F50, nc=nc), 91.80, len(ix))
    r = R[0]
    return {"owner": round(r["owner"]), "cost": round(r["cost"], 2), "net": round(r["net"]), "evals": r["evals"], "funded": r["funded"],
            "payouts": [(S[ix[k - 1]], round(x)) for k, x in r["pays"]]}


def cmd_lit_checks():
    """Stress tests of the LIT + BLITZ pick: paired per-path gain, +1 tick a side, 1 bar late, 2 bars late, no ATLAS
    yield, and the real 2026 path."""
    P = PICK_LIT
    n = 1000
    base = lit_money(None, n=n, per_path=True)
    pick = lit_money(P["nc"], n=n, nc_eval=P["nc_eval"], per_path=True)
    out = {"base": {s: base[s] for s in ("H1", "H2", "REF")}, "pick": {s: pick[s] for s in ("H1", "H2", "REF")}}
    print("LIT alone:", {s: base[s]["slot_pm"] for s in ("H1", "H2", "REF")}, " LIT + BLITZ:", {s: pick[s]["slot_pm"] for s in ("H1", "H2", "REF")})
    for s in ("H1", "H2", "REF"):
        d = np.array(pick[s + "_paths"]) - np.array(base[s + "_paths"])
        out["paired_" + s] = {"mean": round(float(d.mean())), "p10": round(float(np.percentile(d, 10))), "p90": round(float(np.percentile(d, 90))),
                              "better": round(100.0 * float((d > 0).mean()), 1), "worse": round(100.0 * float((d < 0).mean()), 1)}
        print(f"  paired {s}: mean {d.mean():+.0f}/mo, p10 {np.percentile(d, 10):+.0f}, p90 {np.percentile(d, 90):+.0f}, "
              f"better in {100 * (d > 0).mean():.1f}% of 6-month paths, worse in {100 * (d < 0).mean():.1f}%")
    for nm, kw in (("+1 tick a side", {"xslip": 0.25}), ("+2 ticks a side", {"xslip": 0.5}), ("1 bar late", {"late": 1}),
                   ("2 bars late", {"late": 2}), ("no ATLAS yield", {"atlas_yield": False}), ("BLITZ in the eval too", {"nc_eval": "same"})):
        kw2 = {"nc_eval": P["nc_eval"], **kw}
        o = lit_money(P["nc"], n=n, **kw2)
        out[nm] = {s: o[s] for s in ("H1", "H2", "REF")}
        print(f"  {nm:22s} " + " | ".join(f"{s} ${o[s]['slot_pm']}/mo ({o[s]['slot_pm'] - base[s]['slot_pm']:+}) lose {o[s]['slot_lose']}% 2w {o[s]['p10']}/{o[s]['f10']}"
                                          for s in ("H1", "H2", "REF")), flush=True)
    rp0, rp1 = real_path(None), real_path(P["nc"], P["nc_eval"])
    out["real_2026"] = {"lit": rp0, "lit_blitz": rp1}
    print("real 2026 path, LIT alone:", rp0)
    print("real 2026 path, LIT + BLITZ:", rp1)
    # what BLITZ does on LIT's account
    T = _AU[("litm", None, None, True, False, 0, 0.0)]
    T0 = blitz_units()
    for sp, a, z in (("H1", "2026-01-01", "2026-06-30"), ("H2", "2026-07-01", "2026-12-31"), ("REF", "2021-11-01", "2025-12-31")):
        n0 = sum(1 for u in T0 if a <= u["day"] <= z)
        n1 = sum(len([t for t in T.get(d, []) if a <= d <= z]) for d in T)
        print(f"  BLITZ trades {sp}: {n0} alone -> {n1} on LIT's account (LIT flat, no ATLAS opposite)")
        out["n_" + sp] = [n0, n1]
    json.dump(out, open(os.path.join(OUT, "na_combo_lit_checks.json"), "w"), default=float)


if __name__ == "__main__":
    a = sys.argv[1:]
    {"atlas": cmd_atlas, "atlas_funded": cmd_atlas_funded, "lit": cmd_lit, "lit_grid": cmd_lit_grid,
     "lit_checks": cmd_lit_checks, "lit_why": cmd_lit_why, "atlas6": cmd_atlas6}[a[0] if a else "atlas"]()
