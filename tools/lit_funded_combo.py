"""The funded-account studies re-run on the NEW live LIT (2026-10-20: t_check + scale_in + be_off ON, research/lit/adopt_combo.json
"all3"): per-firm eval odds and time, funded $/month, P(lose the funded account in 6 months), the stacks (current plan, + 1 MFFU
Rapid EOD, + a Builder 25K started a week later), net of fees over 6 months, and how many evals to buy (and when) on a $300 /
$600 / $1,000 budget. Write-up: research/writeups/lit-funded-combo.md. Numbers: research/lit/funded_combo.json.

Builds on tools/lit_funded_firms.py (plans, eval / funded / 6-month engines, the same Monte Carlo paths) and
tools/lit_mffu_rapid_stack.py (Rapid prices, the "plan" eval sizing for best-day evals, the real Tier-1 news calendar).
New here:
  trades   the engine's own trades with the three options on (engine/lit.py run_x on live_model.json "lit", 630 trades, 2026:
           120, 52 with a scale-in add), as units: per-micro points of the first entry, worst open points, best open points
           (mfe, for intraday floors), the weekly-stop multiplier, and the adds (stop distance at the fill, distance from the
           entry, points, worst open points). A reference set without scale-in (t_check + be_off) shows what the adds are worth.
  adds     every account sizes the adds with engine/sizing.scale_in_qty (the live rule: f = 1 x the first entry's micros, open
           add risk <= the first entry's $ risk, <= 60% of the room to the floor, <= the soft daily loss left today), capped by
           the plan's max contracts. With a best-day rule (eval: Rapid 50% / Rapid EOD 30%; payout: MFFU Builder 50%, Lucid 40%,
           FundedNext Rapid Pro 40%) the adds are trimmed so the day's win at the target stays inside the cap ("add_cap"); the
           uncapped version is scored too.
  habit    the payout habit of lit-money-batch2.md (ask only once $1,500+ is above the buffer) as a funded option, picked on H1.
  budget   a cash-limited buyer: $B in the pocket, accounts bought in a fixed order whenever the cash (budget - fees paid +
           payouts received) covers the price; a failed eval / lost or finished funded account frees its slot for a re-buy.

  python -X utf8 tools/lit_funded_combo.py units   # build the unit caches (engine run, ~1 min)
  python -X utf8 tools/lit_funded_combo.py check   # base trades + this executor == tools/lit_funded_firms.py numbers
  python -X utf8 tools/lit_funded_combo.py all     # -> research/lit/funded_combo.json
  python -X utf8 tools/lit_funded_combo.py save    # rl.save runs lit_fc_*
Paper only. Edits no engine file; nothing live changes.
"""
from __future__ import annotations

import datetime as dt
import heapq
import itertools
import json
import math
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import lit_funded_firms as FF  # noqa: E402
import lit_mffu_rapid_stack as MRS  # noqa: E402  (patches FF.eval_qty with the "plan" best-day eval sizing)
from engine import sizing as SZ  # noqa: E402

CACHE = os.path.join(ROOT, "research", "runs", "_cache")
OUT = os.path.join(ROOT, "research", "lit", "funded_combo.json")
PV, COMM, SLIP, BIG = FF.PV, FF.COMM, FF.SLIP, FF.BIG
H6, H3 = FF.H6, FF.H3
ADD_RF = 0.6                                   # the live add budget: 60% of the room (engine/sizing.scale_in_qty default)
VARIANTS = {"all3": {"t_check": {"at": 15, "x": 0.3, "mfe": 0.5}, "scale_in": {"pb": 0.25, "f": 1.0, "rat_k": 1.0, "min_rk": 2.0, "n": 1},
                     "be_off": 1.25},
            "t15_be_off": {"t_check": {"at": 15, "x": 0.3, "mfe": 0.5}, "be_off": 1.25, "scale_in": None},
            "base": {"t_check": None, "scale_in": None, "be_off": None}}


# ================================================================================================ trades -> units
def unit_path(var):
    return os.path.join(CACHE, f"lit_fc_units_{var}.json")


def build_units(var):
    from engine import lit
    from tools import lit_final as LF
    live = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]
    P = {**live, **VARIANTS[var]}
    P = {k: v for k, v in P.items() if v is not None}
    for k in ("t_check", "scale_in", "be_off"):
        if VARIANTS[var].get(k) is None:
            P[k] = lit.DEFAULTS.get(k)
    T = LF.run(P)
    M, _ = LF.market(P["ref"], P.get("extra_boxes") or [])
    B1, B5 = LF.bars(M, "1m"), LF.bars(M, "5m")
    out = []
    for t in T:
        d = int(t["dir"])
        B = B1 if t.get("tf") == 1 else B5
        e = float(t["entry_px"]) * d
        if t.get("adds"):
            pts, w1 = float(t["pts"]), float(t["w1"])
        else:
            pts = (t["pnl"] + lit.COMM * t["qty"]) / (lit.PV * t["qty"])
            k0 = int(np.searchsorted(B.t, int(t["entry_t"])))
            kx = int(np.searchsorted(B.t, int(t["exit_t"]) - B.secs))
            if t["exit"] == "CUT_T15":
                kx -= 1
            lo = B.l if d == 1 else -B.h
            w1 = min(0.0, float(lo[k0:kx + 1].min()) - e) if kx >= k0 else 0.0
        u = {"day": t["day"], "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "dir": d, "exit": t["exit"],
             "risk": float(t["risk_pts"]), "tgt": round(d * (float(t["target_px"]) - float(t["entry_px"])), 4),
             "pts": round(pts, 4), "w1": round(float(w1), 4), "wk_m": float(t.get("size_mult") or 1.0), "tf": t.get("tf"),
             "up": round(max(0.0, float(t.get("mfe") or 0.0)) * float(t["risk_pts"]), 4), "entry_px": float(t["entry_px"])}
        if t.get("adds"):
            u.update(w_pre=float(t["w_pre"]), add_f=1.0,
                     adds=[{"rk": float(a["rk"]), "prev_rk": [float(x) for x in a["prev_rk"]], "w_ph": float(a["w_ph"]),
                            "dist": float(a["dist"]), "pts": float(a["pts"]), "t": int(a["t"]), "px": float(a["px"])}
                           for a in t["adds"]])
        out.append(u)
    sess = json.load(open(os.path.join(CACHE, "lit_2wk_unit_live.json"), encoding="utf-8"))["sess"]
    json.dump({"variant": var, "params": {k: P.get(k) for k in ("t_check", "scale_in", "be_off")}, "sess": sess, "trades": out},
              open(unit_path(var), "w", encoding="utf-8"), default=float)
    print(var, len(out), "trades,", sum(1 for u in out if u["day"] >= "2026"), "in 2026,",
          sum(1 for u in out if u.get("adds")), "with adds", flush=True)


VAR = {"name": None}


def use(var):
    """Point tools/lit_funded_firms.py (and the news calendar of lit_mffu_rapid_stack.py) at this variant's units."""
    import collections
    d = json.load(open(unit_path(var), encoding="utf-8"))
    by = collections.defaultdict(list)
    for t in d["trades"]:
        by[t["day"]].append(t)
    FF._D.clear()
    FF._D.update(sess=d["sess"], by=[by.get(s, []) for s in d["sess"]], trades=d["trades"])
    FF._NEWS.clear()
    FF._LIFE.clear()
    MRS._NEWS_BY.clear()
    _EV.clear()
    _FU.clear()
    _BE.clear()
    _BF.clear()
    VAR["name"] = var


# ================================================================================================ one trade with its adds
def trade_pnl(t, q, room, cum, dll, max_micros, win_cap=None, adds_on=True, diag=None):
    """$ P&L, worst open $, best open $ and total micros of one trade at q first-entry micros (+ its adds)."""
    adds = t.get("adds") if adds_on else None
    if not adds:
        pnl = t["pts"] * PV * q - COMM * q
        return pnl, min(0.0, t["w1"] * PV * q - COMM * q, pnl), t["up"] * PV * q, q
    qa = SZ.scale_in_qty(q, q, t["risk"], adds, f=t.get("add_f", 1.0), state={"room": room, "cum": cum}, room_f=ADD_RF,
                         dll=dll if dll else BIG, max_micros=max_micros)
    want = int(t.get("add_f", 1.0) * q)
    if diag is not None:
        diag["adds"] += 1
        diag["want"] += want * len(adds)
        diag["got"] += sum(qa)
        diag["mm_hit"] += int(q + want > max_micros)
    n0 = sum(qa)
    if win_cap is not None:                      # never let the adds break a best-day rule at the target
        base_w = q * (t["tgt"] * PV - COMM)
        for i in range(len(qa) - 1, -1, -1):
            per = (t["tgt"] - adds[i]["dist"]) * PV - COMM
            while qa[i] > 0 and base_w + sum(qq * ((t["tgt"] - a["dist"]) * PV - COMM) for qq, a in zip(qa, adds)) > win_cap + 1e-9 \
                    and per > 0:
                qa[i] -= 1
        if diag is not None:
            diag["cap_cut"] += n0 - sum(qa)
    tot = q + sum(qa)
    g = q * t["pts"] * PV
    lows = [q * t.get("w_pre", t["w1"]) * PV]
    up = q * t["up"]
    for i, a in enumerate(adds):
        g += qa[i] * a["pts"] * PV
        lows.append((q * a["w_ph"] + sum(qq * (a["w_ph"] - b["dist"]) for qq, b in zip(qa[:i + 1], adds))) * PV)
        up += qa[i] * max(0.0, t["up"] - a["dist"])
    pnl = g - COMM * tot
    if diag is not None and sum(qa):
        diag["add_usd"] += sum(qa[i] * a["pts"] * PV - COMM * qa[i] for i, a in enumerate(adds))
    return pnl, min(0.0, min(lows) - COMM * tot, pnl), up * PV, tot


def eval_win_cap(P, st, c):
    """The day's biggest win that keeps the eval best-day rule (same window as tools/lit_funded_firms.eval_qty)."""
    cons = P["cons"]
    if not cons:
        return None
    m = c.get("margin", 0.95)
    bal, best = st["bal"], st["best"]
    tgt_eff = max(P["target"], best / cons)
    pass_day = tgt_eff - bal
    ok_day = cons * max(0.0, bal) / (1 - cons)
    day_cap = ok_day * m if pass_day <= ok_day * m else max(cons * P["target"] * m, best)
    return max(0.0, day_cap - st["cum"])


# ================================================================================================ eval / funded with adds
def run_eval(P, c, seq, by, horizon=FF.H_EVAL):
    mll, dll, intra = P["mll"], P["dll"], P["trail"] == "intra"
    lockv = P["lock"] if P["lock"] is not None else BIG
    bal = peak = 0.0
    floor = -mll
    best, active = 0.0, 0
    adds_on = c.get("adds", True)
    for k, si in enumerate(seq[:horizon]):
        cum, traded = 0.0, False
        for t in by[si]:
            if dll and cum <= -dll:
                break
            st = {"bal": bal, "cum": cum, "best": best, "k": k, "room": bal + cum - floor}
            q = FF.eval_qty(t, st, P, c)
            if q <= 0:
                continue
            traded = True
            wc = eval_win_cap(P, st, c) if c.get("add_cap", True) else None
            pnl, low, up, tot = trade_pnl(t, q, st["room"], cum, dll, P["max_micros"], wc, adds_on)
            if dll and cum + low <= -dll:
                pnl = low = -dll - cum - SLIP * PV * tot
                up = 0.0
            if bal + cum + low <= floor:
                return "FAIL", k + 1
            if intra and up > 0:
                peak = max(peak, bal + cum + up)
                floor = min(max(floor, peak - mll), lockv)
                if bal + cum + pnl <= floor:
                    return "FAIL", k + 1
            cum += pnl
        bal += cum
        if bal <= floor:
            return "FAIL", k + 1
        peak = max(peak, bal)
        floor = min(max(floor, peak - mll), lockv)
        if traded:
            active += 1
            best = max(best, cum)
        if bal >= P["target"] and active >= P["min_days"] and (not P["cons"] or best <= P["cons"] * bal + 1e-9):
            return "PASS", k + 1
    return "OPEN", min(len(seq), horizon)


DIAG = {}


def run_funded(P, cfg, seq, by, start=0, keep=None, diag=None):
    Fd = P["funded"]
    A = FF.facct(P)
    mll, dll, lockv, intra = P["mll"], Fd["dll"], A["lock"], Fd["trail"] == "intra"
    buf = Fd["buffer"] if Fd["buffer"] is not None else mll + 100
    cfgx = {k: v for k, v in cfg.items() if k not in ("add_cap", "adds", "pay_min")}
    cfgx["dll_cap"] = bool(dll)
    skip = FF.NEWS_IDS() if Fd.get("news_skip") else None
    adds_on = cfg.get("adds", True)
    wcap = cfg["max_win"] * P["scale"] if (cfg.get("add_cap", True) and cfg.get("max_win")) else None
    pay_min = max(Fd["pay_min"], cfg.get("pay_min") or 0.0)
    bal = peak = 0.0
    floor = -mll
    paid = gross = 0.0
    n_pay, first, last_bal, last_k, cyc = 0, None, 0.0, start - 999, []
    pay_at = []
    for k in range(start, len(seq)):
        si = seq[k]
        cum = 0.0
        traded = False
        for t in by[si]:
            if dll and cum <= -dll:
                break
            if skip and t["entry_t"] in skip:
                continue
            st = {"room": bal + cum - floor, "cum": cum, "locked": floor >= lockv - 1e-9}
            q = SZ.funded_qty(t, st, cfgx, acct=A)
            if q <= 0:
                continue
            traded = True
            pnl, low, up, tot = trade_pnl(t, q, st["room"], cum, dll, P["max_micros"], wcap, adds_on, diag)
            if dll and cum + low <= -dll:
                pnl = low = -dll - cum - SLIP * PV * tot
                up = 0.0
            if bal + cum + low <= floor:
                if keep is not None:
                    keep.append((t, tot, floor - bal - cum))
                return {"paid": paid, "pay_at": pay_at, "n": n_pay, "first": first, "blown": k, "grad": None}
            if intra and up > 0:
                peak = max(peak, bal + cum + up)
                floor = min(max(floor, peak - mll), lockv)
                if bal + cum + pnl <= floor:
                    if keep is not None:
                        keep.append((t, tot, floor - bal - cum))
                    return {"paid": paid, "pay_at": pay_at, "n": n_pay, "first": first, "blown": k, "grad": None}
            cum += pnl
            if keep is not None:
                keep.append((t, tot, pnl))
        bal += cum
        peak = max(peak, bal)
        floor = min(max(floor, peak - mll), lockv)
        if traded:
            cyc.append(cum)
        if k - start + 1 < Fd["first_wait"] or k - last_k < Fd["every"]:
            continue
        if Fd["days"] and len(cyc) < Fd["days"]:
            continue
        prof = bal - last_bal
        if prof <= 0 or prof < Fd["cyc_min"]:
            continue
        if Fd["win_days"] and sum(1 for x in cyc if x >= max(Fd["win_min"], 0.01)) < Fd["win_days"]:
            continue
        if Fd["cons"] is not None and cyc and max(cyc) > Fd["cons"] * prof:
            continue
        amt = bal - buf
        if Fd["pay_pct"] is not None:
            amt = min(amt, Fd["pay_pct"] * bal)
        amt = min(amt, FF.pay_cap(Fd, n_pay))
        if amt < max(pay_min, 1.0):
            continue
        sp = Fd["split"]
        if Fd["split_first"]:
            lim, sp2 = Fd["split_first"]
            a1 = max(0.0, min(amt, lim - gross))
            share = a1 * sp + (amt - a1) * sp2
        else:
            share = amt * sp
        paid += share
        gross += amt
        n_pay += 1
        pay_at.append((k, share))
        first = first if first is not None else k
        bal -= amt
        last_bal, last_k, cyc = bal, k, []
        if Fd["max_payouts"] and n_pay >= Fd["max_payouts"]:
            return {"paid": paid, "pay_at": pay_at, "n": n_pay, "first": first, "blown": None, "grad": k}
    return {"paid": paid, "pay_at": pay_at, "n": n_pay, "first": first, "blown": None, "grad": None}


FF.run_eval = run_eval                 # FF.eval_exact / eval_mc / life / save look these names up at call time
FF.run_funded = run_funded


# ================================================================================================ news calendar with adds
def news_by():
    """lit_mffu_rapid_stack.news_by (funded Tier-1 rule, real calendar) with the adds fixed on flattened trades: an add filled
    before the flatten is closed at the same price, a later one never happens."""
    NB = MRS.news_by()
    out = []
    for day in NB:
        new = []
        for t in day:
            if t.get("exit") == "NEWS_FLAT" and t.get("adds"):
                px = t["entry_px"] + t["dir"] * (t["pts"] + SLIP)          # the flatten price (entry +/- the base points)
                ad = [{**a, "pts": round(t["dir"] * (px - a["px"]) - SLIP, 4)} for a in t["adds"] if a["t"] < t["exit_t"]]
                t = {**t, "adds": ad} if ad else {k: v for k, v in t.items() if k not in ("adds", "w_pre")}
            new.append(t)
        out.append(new)
    return out


# ================================================================================================ plans
def plans():
    base = {p["id"]: p for p in FF.plans()}
    R = MRS.rapid_plans()
    keep = ["mffu_builder_50k", "lucid_pro_50k", "fn_rapid_daily_50k", "fn_rapid_pro_50k", "mffu_builder_25k"]
    P = [dict(base[k]) for k in keep]
    P += [dict(R["rapid_eod"], news_cal=True), dict(R["rapid"], news_cal=True)]
    for p in P:
        p.pop("fixed_eval", None) if p["id"] != "mffu_builder_50k" else None
    return P


ELIGIBLE = {"mffu_builder_50k": "yes (the owner's eval)", "lucid_pro_50k": "yes", "fn_rapid_daily_50k": "yes",
            "fn_rapid_pro_50k": "yes", "mffu_builder_25k": "only if MFFU allows it next to the 50K (sources conflict)",
            "mffu_rapid_eod_50k": "only if MFFU allows it next to the Builder 50K (not stated); funded Tier-1 news ban",
            "mffu_rapid_50k": "as Rapid EOD; intraday trailing floor when funded"}


# ================================================================================================ per-plan study
_EV, _FU = {}, {}


def fby(P):
    return news_by() if P.get("news_cal") else FF.data()["by"]


def funded_mc(P, cfg, span, n=1500, cpf=None, diag=False):
    by = fby(P)
    dg = {"adds": 0, "want": 0, "got": 0, "mm_hit": 0, "cap_cut": 0, "add_usd": 0.0} if diag else None
    R = [run_funded(P, cfg, s, by, diag=dg) for s in FF.mc_seqs(span, n, H6, 23)]
    paid = np.array([r["paid"] for r in R])
    lost = np.array([r["blown"] is not None for r in R])
    o = {"paths": n, "per_month": round(float(paid.mean()) / 6), "paid_6m": round(float(paid.mean())),
         "paid_p10_6m": round(float(np.percentile(paid, 10))), "loss_6m": round(100 * float(lost.mean()), 1),
         "loss_3m": round(100 * float(np.mean([r["blown"] is not None and r["blown"] < H3 for r in R])), 1),
         "zero_6m": round(100 * float((paid <= 0).mean()), 1), "grad_6m": round(100 * float(np.mean([r["grad"] is not None for r in R])), 1)}
    fr = [r["first"] + 1 for r in R if r["first"] is not None]
    o["first_med"] = float(np.median(fr)) if fr else None
    o["payouts_mean"] = round(float(np.mean([r["n"] for r in R])), 2)
    if cpf:
        o["net_per_month"] = round(float(paid.mean() - lost.mean() * cpf) / 6)
    if dg is not None and dg["adds"]:
        o["adds_diag"] = {"add_trades": dg["adds"], "add_micros_wanted": dg["want"], "add_micros_got": dg["got"],
                          "share_got": round(100.0 * dg["got"] / max(1, dg["want"]), 1),
                          "max_contracts_hit_pct": round(100.0 * dg["mm_hit"] / dg["adds"], 1),
                          "best_day_cut_micros": dg["cap_cut"], "add_usd_per_path": round(dg["add_usd"] / n)}
    return o


def life_mc(P, ce, cf, span, n=1500, offset=0):
    key = (P["id"], json.dumps(ce, sort_keys=True), json.dumps(cf, sort_keys=True), span, n, offset, VAR["name"])
    if key not in FF._LIFE:
        by = fby(P)
        out = []
        for s in FF.mc_seqs(span, n, H6, 31):
            L = FF.life(P, ce, cf, s[offset:], by, horizon=H6 - offset)
            L["pays"] = [(k + offset, v) for k, v in L["pays"]]
            L["lost_at"] = [k + offset for k in L["lost_at"]]
            out.append(L)
        FF._LIFE[key] = out
    return FF._LIFE[key]


def eval_full(P, c, span):
    o = FF.eval_exact(P, c, span)
    o["dec10"] = round(o["p10"] + o["f10"], 1)
    return o


def pick_eval(P):
    if P["id"] == "mffu_builder_50k":
        return P["fixed_eval"], []
    G = MRS.eval_grid(P) if P["cons"] else FF.eval_grid()
    G = G + [{**c, "add_cap": False} for c in G if P["cons"]][:0]      # add_cap scored below on the pick only
    rows = []
    for c in G:
        o = eval_full(P, c, "H1")
        sc = MRS.score_eval(o) if P["cons"] else FF.eval_score(o)
        rows.append({"cfg": c, "H1": {k: o[k] for k in ("p10", "f10", "p15", "f15", "p60", "f60", "pass_med")}, "score": round(sc, 1)})
    best = max(rows, key=lambda r: r["score"])
    return best["cfg"], sorted(rows, key=lambda r: -r["score"])[:8]


def pick_funded(P, cpf):
    if P["id"] == "mffu_builder_50k":
        base = dict(FF.plans()[0]["fixed_funded"])
        rows = []
    else:
        rows = []
        for c in FF.funded_grid():
            o = funded_mc(P, c, "H1", n=400, cpf=cpf)
            rows.append({"cfg": c, "H1": {k: o[k] for k in ("per_month", "net_per_month", "loss_6m", "first_med")}})
        base = max(rows, key=lambda r: r["H1"]["net_per_month"])["cfg"]
    # toggles on the pick, picked on H1 too: adds capped by the payout best-day rule or not, the $1,500 payout habit
    tog = []
    for add_cap, habit in itertools.product((True, False), (None, 1500.0)):
        if not base.get("max_win") and not add_cap:
            continue
        if habit and (P["funded"]["pay_min"] or 0) >= habit:
            continue
        c = {**base, "add_cap": add_cap, "pay_min": habit}
        o = funded_mc(P, c, "H1", n=1000, cpf=cpf)
        tog.append({"cfg": c, "H1": {k: o[k] for k in ("per_month", "net_per_month", "loss_6m", "first_med")}})
    best = max(tog, key=lambda r: r["H1"]["net_per_month"])
    return best["cfg"], rows[:0] + sorted(rows, key=lambda r: -r["H1"]["net_per_month"])[:6], tog


def study_plan(P, log=print):
    t0 = dt.datetime.now()
    ce, eg = pick_eval(P)
    ev = {s: eval_full(P, ce, s) for s in ("H1", "H2", "2026", "2021-25")}
    ev_mc = {s: FF.eval_mc(P, ce, s) for s in ("H1", "H2")}
    ev_noadd = {s: eval_full(P, {**ce, "adds": False}, s) for s in ("H1", "H2")}
    ev_nocap = {s: eval_full(P, {**ce, "add_cap": False}, s) for s in ("H1", "H2")} if P["cons"] else None
    cpf = {s: FF.cost_per_funded(P, ev_mc[s]) for s in ("H1", "H2")}
    cf, fg, tog = pick_funded(P, cpf["H1"])
    fu = {s: funded_mc(P, cf, s, cpf=cpf.get(s) or cpf["H1"], diag=True) for s in ("H1", "H2", "2021-25")}
    fu_noadd = {s: funded_mc(P, {**cf, "adds": False}, s, cpf=cpf.get(s) or cpf["H1"]) for s in ("H1", "H2")}
    fu_tog = {json.dumps({k: r["cfg"].get(k) for k in ("add_cap", "pay_min")}): {s: funded_mc(P, r["cfg"], s, cpf=cpf.get(s) or cpf["H1"])
                                                                                  for s in ("H1", "H2")} for r in tog}
    li = {s: FF.life_summary(life_mc(P, ce, cf, s)) for s in ("H1", "H2", "2021-25")}
    log(f"[{VAR['name']}] {P['id']}: eval H1 p10/f10 {ev['H1']['p10']}/{ev['H1']['f10']} p60 {ev['H1']['p60']} | H2 "
        f"{ev['H2']['p10']}/{ev['H2']['f10']} p60 {ev['H2']['p60']} | funded {cf.get('pct')}/{cf.get('pct_max_usd')}/{cf.get('max_win')} "
        f"cap {cf.get('add_cap')} habit {cf.get('pay_min')} H1 ${fu['H1']['per_month']} lost {fu['H1']['loss_6m']} H2 "
        f"${fu['H2']['per_month']} lost {fu['H2']['loss_6m']} | life H1 ${li['H1']['net_per_month']} H2 ${li['H2']['net_per_month']} "
        f"({(dt.datetime.now() - t0).seconds}s)", flush=True)
    return {"id": P["id"], "eval_cfg": ce, "eval": ev, "eval_mc": ev_mc, "eval_no_adds": ev_noadd, "eval_adds_uncapped": ev_nocap,
            "eval_grid_top": eg, "cost_per_funded": cpf, "funded_cfg": cf, "funded_grid_top": fg, "funded_toggles": tog,
            "funded": fu, "funded_no_adds": fu_noadd, "funded_toggle_scores": fu_tog, "life": li}


# ================================================================================================ stacks (same paths)
def stack(accts, span, n=1500):
    o = MRS.stack(accts, span, n)
    pay = np.array([[sum(v for k, v in a[1][j]["pays"]) for a in accts] for j in range(n)])
    o["corr_paid"] = [[round(float(x), 2) for x in r] for r in np.atleast_2d(np.corrcoef(pay.T))] if len(accts) > 1 else [[1.0]]
    m46 = np.array([sum(sum(v for k, v in a[1][j]["pays"] if k >= 63) for a in accts) for j in range(n)])
    o["any_zero_m46"] = round(100 * float(np.mean([[sum(v for k, v in a[1][j]["pays"] if k >= 63) <= 0 for a in accts]
                                                    for j in range(n)], axis=0).max()), 1)
    _ = m46
    return o


STACKS = {
    "B50": [("mffu_builder_50k", 0)],
    "B50+Lucid": [("mffu_builder_50k", 0), ("lucid_pro_50k", 0)],
    "current: B50+Lucid+FN": [("mffu_builder_50k", 0), ("lucid_pro_50k", 0), ("fn_rapid_daily_50k", 0)],
    "current + 1 Rapid EOD": [("mffu_builder_50k", 0), ("lucid_pro_50k", 0), ("fn_rapid_daily_50k", 0), ("mffu_rapid_eod_50k", 0)],
    "current + 25K a week later": [("mffu_builder_50k", 0), ("lucid_pro_50k", 0), ("fn_rapid_daily_50k", 0), ("mffu_builder_25k", 5)],
    "current + 25K same day": [("mffu_builder_50k", 0), ("lucid_pro_50k", 0), ("fn_rapid_daily_50k", 0), ("mffu_builder_25k", 0)],
    "current + Rapid EOD + 25K a week later": [("mffu_builder_50k", 0), ("lucid_pro_50k", 0), ("fn_rapid_daily_50k", 0),
                                               ("mffu_rapid_eod_50k", 0), ("mffu_builder_25k", 5)],
    "current + 2nd Lucid a week later": [("mffu_builder_50k", 0), ("lucid_pro_50k", 0), ("fn_rapid_daily_50k", 0), ("lucid_pro_50k", 5)],
    "current, Lucid + FN a week later": [("mffu_builder_50k", 0), ("lucid_pro_50k", 5), ("fn_rapid_daily_50k", 5)],
}


def run_stacks(PL, R, spans=("H1", "H2", "2021-25")):
    by_id = {p["id"]: p for p in PL}
    out = []
    for span in spans:
        for name, parts in STACKS.items():
            acc, cash = [], 0.0
            for i, (pid, off) in enumerate(parts):
                P = by_id[pid]
                acc.append((f"{pid}@{off}#{i}", life_mc(P, R[pid]["eval_cfg"], R[pid]["funded_cfg"], span, offset=off)))
                cash += P["price"]
            o = stack(acc, span)
            o.update(stack=name, cash_up_front=round(cash, 2))
            out.append(o)
            print(f"[{VAR['name']}] stack {span} {name}: ${o['net_per_month']}/mo m4-6 ${o['months4_6_per_month']} neg {o['neg_6m']} "
                  f"zero46 {o['all_zero_m46']} all_lost {o['all_lost']} cash ${o['cash_up_front']}", flush=True)
    return out


# ================================================================================================ the budget buyer
class Slot:
    __slots__ = ("P", "ce", "cf", "off")

    def __init__(self, P, ce, cf, off):
        self.P, self.ce, self.cf, self.off = P, ce, cf, off


_BE, _BF = {}, {}


def _ev(P, ce, j, seq, k, span):
    key = (P["id"], span, j, k)
    if key not in _BE:
        _BE[key] = run_eval(P, ce, seq[k:H6], FF.data()["by"], horizon=H6 - k)
    return _BE[key]


def _fu(P, cf, j, seq, k, by, span):
    key = (P["id"], span, j, k)
    if key not in _BF:
        _BF[key] = run_funded(P, cf, seq[:H6], by, start=k)
    return _BF[key]


def budget_path(slots, j, seq, budget, bys, span):
    """One 6-month path, cash-limited. Each slot: idle from its offset; buy when cash >= price; eval -> funded; a fail, a
    lost funded account or a finished one (5 payouts) -> idle again the next session. -> (net, fees, paid, max_out, n_bought)."""
    cash, fees, paid, n_buy = float(budget), 0.0, 0.0, 0
    income = []                                     # (session, $) payouts, applied as time passes
    ev = [(s.off, i, "idle") for i, s in enumerate(slots)]
    heapq.heapify(ev)
    min_cash = cash
    waiting = []
    k_now = 0

    def collect(upto):
        nonlocal cash, paid
        keep = []
        for k, v in income:
            if k < upto:
                cash += v
                paid += v
            else:
                keep.append((k, v))
        income[:] = keep

    while ev or waiting:
        if ev:
            k, i, kind = heapq.heappop(ev)
        else:
            break
        if k >= H6:
            continue
        k_now = k
        collect(k)
        s = slots[i]
        P = s.P
        if kind == "idle":
            if cash + 1e-9 < P["price"]:
                nxt = min([kk for kk, _ in income if kk >= k] or [k + 5])       # wait for the next payout (or a week)
                heapq.heappush(ev, (max(k + 1, nxt), i, "idle"))
                continue
            cash -= P["price"]
            fees += P["price"]
            n_buy += 1
            min_cash = min(min_cash, cash)
            r, n = _ev(P, s.ce, j, seq, k, span)
            if r == "PASS":
                kf = k + n
                fees += P["act"]
                cash -= P["act"]
                f = _fu(P, s.cf, j, seq, kf, bys[P["id"]], span)
                for kk, v in f["pay_at"]:
                    if kk < H6:
                        income.append((kk + 1, v))      # the money arrives after the session it was asked
                end = f["blown"] if f["blown"] is not None else f["grad"]
                if end is not None:
                    heapq.heappush(ev, (end + 1, i, "idle"))
            elif r == "FAIL":
                heapq.heappush(ev, (k + n, i, "idle"))
    collect(H6 + 1)
    _ = k_now
    return paid - fees, fees, paid, budget - min_cash, n_buy


def budget_eval(slots, span, budget, n=1000):
    seqs = FF.mc_seqs(span, 1500, H6, 31)[:n]
    bys = {s.P["id"]: fby(s.P) for s in slots}
    R = [budget_path(slots, j, seq, budget, bys, span) for j, seq in enumerate(seqs)]
    net = np.array([r[0] for r in R])
    return {"net_per_month": round(float(net.mean()) / 6), "net_med_per_month": round(float(np.median(net)) / 6),
            "neg_6m": round(100 * float((net < 0).mean()), 1), "p10_6m": round(float(np.percentile(net, 10))),
            "fees_6m": round(float(np.mean([r[1] for r in R]))), "paid_6m": round(float(np.mean([r[2] for r in R]))),
            "max_out_of_pocket": round(float(np.mean([r[3] for r in R]))), "evals_bought": round(float(np.mean([r[4] for r in R])), 2)}


def run_budgets(PL, R, budgets=(300, 600, 1000)):
    """Every mix of up to 6 accounts (B50 <= 1, 25K <= 1, Lucid <= 3, FN Rapid Daily <= 2, Rapid EOD <= 3), bought same day or
    a week apart (in the order B50, Lucid, FN, Rapid EOD, 25K), cash-limited. Picked on H1, checked on H2."""
    by_id = {p["id"]: p for p in PL}
    caps = [("mffu_builder_50k", 1), ("lucid_pro_50k", 3), ("fn_rapid_daily_50k", 2), ("mffu_rapid_eod_50k", 3), ("mffu_builder_25k", 1)]
    mixes = []
    for cnt in itertools.product(*[range(c + 1) for _, c in caps]):
        if not 0 < sum(cnt) <= 6:
            continue
        ids = [pid for (pid, _), c in zip(caps, cnt) for _ in range(c)]
        mixes.append(ids)
    rows = []
    for budget in budgets:
        for ids in mixes:
            up = sum(by_id[i]["price"] for i in ids[:1])
            if up > budget:
                continue
            for mode in ("same_day", "week_apart"):
                if mode == "week_apart" and len(ids) == 1:
                    continue
                slots = [Slot(by_id[i], R[i]["eval_cfg"], R[i]["funded_cfg"], 0 if mode == "same_day" else 5 * k)
                         for k, i in enumerate(ids)]
                o = {"budget": budget, "accounts": ids, "mode": mode,
                     "confirmed_only": all(i in ("mffu_builder_50k", "lucid_pro_50k", "fn_rapid_daily_50k") for i in ids),
                     "cash_for_all_day1": round(sum(by_id[i]["price"] for i in ids), 2)}
                o["H1"] = budget_eval(slots, "H1", budget)
                rows.append(o)
        print(f"[{VAR['name']}] budget ${budget}: {sum(1 for r in rows if r['budget'] == budget)} mixes scored on H1", flush=True)
    best = {}
    for budget in budgets:
        for conf in (True, False):
            C = [r for r in rows if r["budget"] == budget and (r["confirmed_only"] or not conf)]
            C.sort(key=lambda r: -r["H1"]["net_per_month"])
            top = C[:5]
            for r in top:
                if "H2" not in r:
                    slots = [Slot(by_id[i], R[i]["eval_cfg"], R[i]["funded_cfg"], 0 if r["mode"] == "same_day" else 5 * k)
                             for k, i in enumerate(r["accounts"])]
                    r["H2"] = budget_eval(slots, "H2", budget)
                    r["2021-25"] = budget_eval(slots, "2021-25", budget)
            best[f"{budget}_{'confirmed' if conf else 'all'}"] = top
            b = top[0]
            print(f"[{VAR['name']}] budget ${budget} {'confirmed' if conf else 'all'}: {b['accounts']} {b['mode']} H1 "
                  f"${b['H1']['net_per_month']} H2 ${b['H2']['net_per_month']} out-of-pocket {b['H2']['max_out_of_pocket']}", flush=True)
    return {"best": best, "n_mixes": len(rows),
            "all_H1": [{k: r[k] for k in ("budget", "accounts", "mode", "confirmed_only")} | {"H1": r["H1"]["net_per_month"]}
                       for r in rows]}


# ================================================================================================ check / all / save
def check():
    """The base trades (no options) through this executor must give lit_funded_firms.py's numbers (same engine, same paths)."""
    use("base")
    old = json.load(open(FF.OUT, encoding="utf-8"))
    R0 = {p["id"]: p["results"] for p in old["plans"]}
    ok = True
    for P in FF.plans():
        if P["id"] not in ("mffu_builder_50k", "lucid_pro_50k", "fn_rapid_daily_50k"):
            continue
        r0 = R0[P["id"]]
        e = FF.eval_exact(P, r0["eval_cfg"], "H1")
        f = funded_mc(P, r0["funded_cfg"], "H2", cpf=r0["cost_per_funded"]["H2"])
        print(P["id"], "eval H1 p10/f10/p60", e["p10"], e["f10"], e["p60"], "vs", r0["eval"]["H1"]["p10"], r0["eval"]["H1"]["f10"],
              r0["eval"]["H1"]["p60"], "| funded H2 $/mo", f["per_month"], "vs", r0["funded"]["H2"]["per_month"], "lost", f["loss_6m"],
              "vs", r0["funded"]["H2"]["loss_6m"], flush=True)
        ok &= abs(e["p60"] - r0["eval"]["H1"]["p60"]) < 6 and abs(f["per_month"] - r0["funded"]["H2"]["per_month"]) < 80
    print("check", "OK (base units == the lit_live cache: exact)"
          if ok else "DIFF", flush=True)
    return ok


def _work(arg):
    var, pid = arg
    use(var)
    P = next(p for p in plans() if p["id"] == pid)
    return pid, study_plan(P)


def run_all(var="all3", budgets=True, procs=4):
    import multiprocessing as mp
    use(var)
    PL = plans()
    with mp.get_context("fork").Pool(procs) as pool:
        R = dict(pool.map(_work, [(var, P["id"]) for P in PL], chunksize=1))
    use(var)
    st = run_stacks(PL, R)
    bu = run_budgets(PL, R) if budgets else None
    news = MRS.news_summary()
    return {"variant": var, "plans": [{**{k: P[k] for k in ("id", "firm", "plan", "target", "mll", "trail", "lock", "dll", "cons",
                                                             "min_days", "max_micros", "price", "list_price", "monthly", "act",
                                                             "funded", "price_note", "accounts", "news")},
                                        "eligible": ELIGIBLE[P["id"]], "results": R[P["id"]]} for P in PL],
            "stacks": st, "budgets": bu, "news": {k: v for k, v in news.items() if k != "detail_2026"},
            "news_2026": news.get("detail_2026")}


def main_all():
    t0 = dt.datetime.now()
    out = {"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "study": "lit_funded_combo",
           "writeup": "research/writeups/lit-funded-combo.md",
           "trades": "engine/lit.py run_x on live_model.json lit (t_check + scale_in + be_off ON), 630 trades, 2026: 120 (52 with an add); "
                     "$1.90 a micro, 1 tick slippage; adds sized by engine/sizing.scale_in_qty (60% room, soft daily loss, max contracts)",
           "method": "as research/lit/funded_firms.json (exact evals on every session of the half, 2,000 MC evals, 1,500 funded / "
                     "6-month paths of 126 sessions in 5-session blocks, H1 pick / H2 check) + adds + best-day add cap + payout "
                     "habit toggle + cash-limited budget buyer (1,000 paths)"}
    out["all3"] = run_all("all3")
    out["t15_be_off"] = run_all("t15_be_off", budgets=False)
    json.dump(out, open(OUT, "w", encoding="utf-8"), separators=(",", ":"), default=float)
    print("wrote", OUT, os.path.getsize(OUT) // 1024, "KB", (dt.datetime.now() - t0).seconds, "s", flush=True)


def save():
    """rl.save one run per plan (lit_fc_<plan>: back-to-back real-history funded trades, 2021-11..2026-10) + the recommended stack."""
    from tools import runlib as rl
    out = json.load(open(OUT, encoding="utf-8"))
    use("all3")
    D = FF.data()
    PLd = {p["id"]: p for p in plans()}
    allT = {}
    for row in out["all3"]["plans"]:
        P = PLd[row["id"]]
        R = row["results"]
        T = []
        by = fby(P)
        for span in ("2021-25", "H1", "H2"):
            a, z = FF.span_idx(span)
            seq = list(range(a, z))
            k = 0
            while k < len(seq):
                e, n = run_eval(P, R["eval_cfg"], seq[k:], D["by"], horizon=len(seq) - k)
                k += n
                if e != "PASS":
                    if e == "OPEN":
                        break
                    continue
                keep = []
                f = run_funded(P, R["funded_cfg"], seq, by, start=k, keep=keep)
                for t, q, pnl in keep:
                    ru = t["risk"] * PV * q
                    T.append({"day": t["day"], "entry_t": t["entry_t"], "exit_t": t["exit_t"], "dir": t["dir"],
                              "r": round(pnl / ru, 3) if ru else 0.0, "pnl": round(pnl, 2), "low": round(min(0.0, pnl), 2),
                              "risk_pts": t["risk"], "qty": q, "risk_usd": round(ru, 2), "half": t.get("wk_m", 1.0) < 1,
                              "exit": t["exit"], "trigger": "LIT-" + ("1m" if t.get("tf") == 1 else "5m"), "mfe": None,
                              "mae": None, "bars_held": None, "regime": "", "mult": None, "tgt_pts": t["tgt"]})
                if f["blown"] is not None:
                    k = f["blown"] + 1
                elif f["grad"] is not None:
                    k = f["grad"] + 1
                else:
                    break
        if not T:
            continue
        T.sort(key=lambda t: t["entry_t"])
        allT[P["id"]] = T
        e1, e2, f1, f2, l1, l2 = (R["eval"]["H1"], R["eval"]["H2"], R["funded"]["H1"], R["funded"]["H2"], R["life"]["H1"], R["life"]["H2"])
        verdict = (f"{P['firm']} {P['plan']} on the new live LIT (t_check + scale_in + be_off): eval p10/f10 H1 {e1['p10']}/{e1['f10']} "
                   f"H2 {e2['p10']}/{e2['f10']}, eventual pass {e1['p60']} / {e2['p60']}%, pass_med {e1['pass_med']} / {e2['pass_med']}; "
                   f"funded MC ${f1['per_month']} / ${f2['per_month']} a month, lost in 6 months {f1['loss_6m']} / {f2['loss_6m']}%; "
                   f"6 months from purchase net of fees ${l1['net_per_month']} / ${l2['net_per_month']} a month (H1 / H2). "
                   f"Can the bot run there: {ELIGIBLE[P['id']]}.")
        rl.save("lit_fc_" + P["id"], f"LIT combo on {P['firm']} {P['plan']} (eval + funded)", "risk",
                "The funded-account plan re-run on the new live LIT (t_check + scale_in + be_off): what does each account pay?",
                params={"plan": {k: P[k] for k in ("target", "mll", "trail", "lock", "dll", "cons", "min_days", "max_micros", "price",
                                                   "funded")}, "lit": VARIANTS["all3"]},
                sizing={"eval": R["eval_cfg"], "funded": R["funded_cfg"], "adds": "engine.sizing.scale_in_qty, 60% room"},
                trades=T, scored=rl.score(T, D["sess"]), status="adopt-candidate" if ELIGIBLE[P["id"]].startswith("yes") else "info",
                verdict=verdict, notes="tools/lit_funded_combo.py; stored trades = back-to-back real history, funded trades only. "
                                       "The run library's eval columns are not this plan's numbers: those are in the verdict and "
                                       "research/lit/funded_combo.json.", writeup="lit-funded-combo", tags=["lit", "lit_funded_combo"])
        print("saved lit_fc_" + P["id"], flush=True)
    st = {(s["stack"], s["span"]): s for s in out["all3"]["stacks"]}
    for name, rid in (("current: B50+Lucid+FN", "lit_fc_stack_current"), ("current + 1 Rapid EOD", "lit_fc_stack_rapid_eod"),
                      ("current + 25K a week later", "lit_fc_stack_25k_week")):
        ids = [pid for pid, _ in STACKS[name]]
        T = sorted([t for pid in ids for t in allT.get(pid, [])], key=lambda t: t["entry_t"])
        h1, h2, ref = st[(name, "H1")], st[(name, "H2")], st[(name, "2021-25")]
        rl.save(rid, f"LIT combo stack: {name}", "risk", "Which accounts together, net of fees over 6 months, on the new live LIT?",
                params={"accounts": STACKS[name], "lit": VARIANTS["all3"]}, trades=T, scored=rl.score(T, D["sess"]),
                status="adopt-candidate" if "Rapid" not in name and "25K" not in name else "info",
                verdict=(f"{name}: 6 months from buying, net of fees ${h1['net_per_month']} / ${h2['net_per_month']} a month (H1 / H2), "
                         f"months 4-6 ${h1['months4_6_per_month']} / ${h2['months4_6_per_month']}, 6 months lose money {h1['neg_6m']} / "
                         f"{h2['neg_6m']}%, all pay $0 in months 4-6 {h1['all_zero_m46']} / {h2['all_zero_m46']}%, cash up front "
                         f"${h1['cash_up_front']}; 2021-25 reference ${ref['net_per_month']} a month."),
                notes="tools/lit_funded_combo.py; stored trades = each account's back-to-back real-history funded trades, merged.",
                writeup="lit-funded-combo", tags=["lit", "lit_funded_combo"])
        print("saved", rid, flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd == "units":
        for v in (sys.argv[2:] or list(VARIANTS)):
            build_units(v)
    elif cmd == "check":
        check()
    elif cmd == "all":
        main_all()
    elif cmd == "save":
        save()
    elif cmd == "one":
        use(sys.argv[3] if len(sys.argv) > 3 else "all3")
        P = next(p for p in plans() if p["id"] == sys.argv[2])
        r = study_plan(P)
        print(json.dumps({k: r[k] for k in ("eval_cfg", "funded_cfg", "funded", "life")}, default=float)[:3000])
