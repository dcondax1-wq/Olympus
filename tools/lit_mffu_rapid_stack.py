"""LIT on stacked MFFU Rapid / Rapid EOD 50K accounts (owner, 2026-10-19: "We can always stack Rapid accounts EOD for MFFU").
Write-up: research/writeups/lit-mffu-rapid-stack.md. Numbers: research/lit/mffu_rapid_stack.json. Builds on
tools/lit_funded_firms.py (same trades, same eval / funded / 6-month engines, same Monte Carlo paths).

New here:
  1. Eval sizing "plan" for a best-day (consistency) eval: the profit needed is spread over winners so the best day never
     breaks the rule. Pass today when one winner can land inside the pass window [max(target - B, best / c - B),
     c x B / (1 - c)] (B = profit so far, c = the rule's share); otherwise the first winner aims at $A and every later
     winner at the best day so far (equal winners never raise the best day). Grid of A, room cap and $ cap, picked on H1.
  2. The funded Tier-1 news rule on the REAL calendar (not every 08:30): flat with no position from 2 min before to 2 min
     after CPI, the Employment Report (NFP), FOMC statement (14:00) and press conference (14:30), FOMC minutes (14:00).
     A trade open at release - 2 min is flattened at that minute's price (1m bars; 5m bars on 2021-25); an entry inside
     the window is skipped (LIT takes 1 trade a day, so no re-entry). Evals allow news.
  3. Stacking: N = 1..5 Rapid accounts (+ the Builder 50K) on the same paths: bought the same day (identical copies) or a
     week apart. $/month, cash up front, all lose / all pay $0 together.

  python tools/lit_mffu_rapid_stack.py all     # -> research/lit/mffu_rapid_stack.json (1 process)
  python tools/lit_mffu_rapid_stack.py save    # rl.save runs lit_mrs_*
Paper only; nothing live changes.
"""
from __future__ import annotations

import csv
import datetime as dt
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

OUT = os.path.join(ROOT, "research", "lit", "mffu_rapid_stack.json")
FFJ = os.path.join(ROOT, "research", "lit", "funded_firms.json")
PV, COMM = FF.PV, FF.COMM
SEARCHED = "2026-10-19"
_orig_eval_qty = FF.eval_qty


# ================================================================================================ the plans (rules searched 2026-10-19)
def rapid_plans():
    base = {p["id"]: p for p in FF.plans()}
    r = dict(base["mffu_rapid_50k"])
    r.update(price=94.20, list_price=157.0, monthly=True, max_micros=50,
             price_note="list $157 (Aug-2026 guide: 30-day renewal; MFFU moved Builder to one-time on 2026-08-25, Rapid not "
                        "stated); $94.20 assumes the owner's 40% code. Modelled as monthly (worse case).",
             accounts="up to 5 active sim-funded Rapid 25K/50K (Rapid page, earlier search); next to a Builder 50K: not stated")
    e = dict(base["mffu_rapid_eod_50k"])
    e.update(price=94.20, list_price=157.0, monthly=False, max_micros=30,
             price_note="list $157 one-time, 365 days access (launch, Aug 2026); 20% code ETFPROMO ended; $94.20 assumes 40% off",
             accounts="3 sim-funded Rapid EOD (MFFU on X, per Finance Magnates); next to a Builder 50K: not stated")
    return {"rapid": r, "rapid_eod": e, "builder": base["mffu_builder_50k"]}


# ================================================================================================ eval sizing "plan"
def eval_qty_plan(t, st, P, c):
    """c = {"base": "plan", "A": first-winner $, "room_f", "max_usd", "margin"}; other bases -> the old rule."""
    if c.get("base") != "plan" or not P["cons"]:
        return _orig_eval_qty(t, st, P, c)
    cons, m = P["cons"], c.get("margin", 0.95)
    B = st["bal"] + st["cum"]
    b = st["best"]
    tgt_eff = max(P["target"], b / cons)
    if st["bal"] + st["cum"] >= tgt_eff:
        return 1                                    # passed on $, days missing: a 1-micro trade
    w = t["tgt"] * PV - COMM                        # $ a micro if the target is hit
    if w <= 0:
        return 1
    q = None
    if B > 0:
        lo = max(P["target"] - B, b / cons - B, 0.0)
        hi = cons * B / (1.0 - cons) * m
        if lo <= hi:
            qq = max(1, math.ceil(lo / w - 1e-9))
            if qq * w <= hi:
                q = qq                              # one winner passes inside the window
    if q is None:
        aim = c["A"] if b <= 0 else b * m           # first winner: $A; later: equal to the best day (never raise it)
        if b > 0 and B > 0:
            aim = min(aim, cons * B / (1.0 - cons) * m) if B + aim < tgt_eff else aim
        q = max(1, int(aim / w))
    if c.get("up"):                                 # never more than up x the normal LIT size (low-R trades stay small)
        q = min(q, max(1, math.ceil(c["up"] * FF.normal_q(t, P["scale"]))))
    if t.get("wk_m", 1.0) < 1.0:
        q = max(1, int(q * t["wk_m"] + 1e-9))
    loss1 = (t["risk"] + FF.SLIP) * PV + COMM
    caps = []
    if c.get("max_usd"):
        caps.append(int(c["max_usd"] * P["scale"] / loss1))
    if c.get("room_f"):
        caps.append(int(c["room_f"] * max(0.0, st["room"]) / (t["risk"] * PV)))
    for cp in caps:
        if cp < q:
            q = max(1, cp)
    if max(0.0, st["room"]) <= loss1:               # even 1 micro could reach the floor
        return 1
    return int(min(q, P["max_micros"]))


FF.eval_qty = eval_qty_plan                          # run_eval looks the name up at call time


def eval_grid(P):
    As = (1500, 1700, 2000, 2400, 3000) if P["cons"] >= 0.5 else (700, 850, 1000, 1200, 1500)
    G = [dict(FF_RAPID_OLD.get(P["id"], {"base": "need", "until": 999, "room_f": 0.4, "max_usd": 600, "margin": 0.95}))]
    G.append({"base": "scaled", "until": 0, "room_f": 0.6, "max_usd": None})
    for rf, mx, mg in itertools.product((0.4, 0.6, 0.8), (600, 1000, 1500), (0.9, 0.95)):   # lit-funded-firms 'need' + guard
        G.append({"base": "need", "until": 999, "room_f": rf, "max_usd": mx, "margin": mg})
    for A, rf, mx, up in itertools.product(As, (0.4, 0.6, 0.8), (600, 1000, 1500), (None, 1.0, 1.5, 2.5)):
        G.append({"base": "plan", "A": A, "room_f": rf, "max_usd": mx, "up": up, "margin": 0.95})
    return G


FF_RAPID_OLD = {}


def eval_cost(P, c, span):
    """Exact evals of the span: $ per pass (monthly plan: price x months the attempt ran)."""
    D = FF.data()
    a, z = FF.span_idx(span)
    res = [FF.run_eval(P, c, list(range(i, z)), D["by"]) for i in range(a, z)]
    o = FF.eval_summary(res)
    o["dec10"] = round(o["p10"] + o["f10"], 1)
    fees = [P["price"] * (math.ceil(n / 21) if P["monthly"] else 1) for r, n in res]
    p = sum(1 for r, n in res if r == "PASS")
    o["cost_per_pass"] = round(sum(fees) / p) if p else None
    o["open60"] = round(100.0 * sum(1 for r, n in res if r == "OPEN") / len(res), 1)
    return o


def score_eval(o):
    return o["p15"] - o["f15"] + 0.5 * (o["p60"] - o["f60"])


# ================================================================================================ Tier-1 news calendar
_CAL = {}


def tier1():
    """date -> [minutes after midnight ET] of Tier-1 releases (CPI, NFP, FOMC 14:00 + 14:30, FOMC minutes 14:00)."""
    if _CAL:
        return _CAL
    rows = list(csv.DictReader(open(os.path.join(ROOT, "data", "news", "events.csv"), encoding="utf-8")))
    rows += list(csv.DictReader(open(os.path.join(ROOT, "data", "news", "ff_archive.csv"), encoding="utf-8")))
    src = {}
    fomc = set()
    for r in rows:
        ev = r["event"]
        if r["date"] > "2026-10-16":
            continue
        tier = ("CPI" in ev and "PPI" not in ev) or "Non-Farm Payrolls" in ev or ev.startswith("FOMC") or "minutes" in ev.lower()
        if not tier:
            continue
        h, mi = map(int, r["time_et"].split(":"))
        _CAL.setdefault(r["date"], set()).add(h * 60 + mi)
        src.setdefault(r["date"], set()).add(ev)
        if ev.startswith("FOMC rate decision"):
            fomc.add(r["date"])
    for d in sorted(fomc):                          # minutes: 3 weeks after the decision, 14:00 (checked on 2026's 6)
        m = (dt.date.fromisoformat(d) + dt.timedelta(days=21)).isoformat()
        if m <= "2026-10-16":
            _CAL.setdefault(m, set()).add(14 * 60)
            src.setdefault(m, set()).add("FOMC minutes (decision + 21 days)")
    have_nfp = {d[:7] for d, s in src.items() if any("Payrolls" in e for e in s)}
    y, mo = 2021, 1                                 # NFP before Oct 2023 is not in the file: first Friday (reference only)
    while (y, mo) <= (2023, 9):
        if f"{y}-{mo:02d}" not in have_nfp:
            d = dt.date(y, mo, 1)
            while d.weekday() != 4:
                d += dt.timedelta(days=1)
            _CAL.setdefault(d.isoformat(), set()).add(8 * 60 + 30)
            src.setdefault(d.isoformat(), set()).add("NFP (first Friday, approx.)")
        mo += 1
        if mo == 13:
            y, mo = y + 1, 1
    _CAL["_src"] = {k: sorted(v) for k, v in src.items()}
    return _CAL


_BARS = {}


def bars(tf):
    if tf not in _BARS:
        import pandas as pd
        f = "NQ_1m.csv" if tf == 1 else "NQ_5m.csv"
        b = pd.read_csv(os.path.join(ROOT, "data", f))
        _BARS[tf] = (b["time"].to_numpy(np.int64), b["open"].to_numpy(float), b["high"].to_numpy(float),
                     b["low"].to_numpy(float))
    return _BARS[tf]


_NEWS_BY = {}
NEWS_LOG = []


def news_by(pre=2, post=2):
    """FF.data()["by"] with the funded Tier-1 rule applied (calendar days only)."""
    key = (pre, post)
    if key in _NEWS_BY:
        return _NEWS_BY[key]
    from zoneinfo import ZoneInfo
    ny = ZoneInfo("America/New_York")
    D = FF.data()
    cal = tier1()
    out = []
    log = []
    for si, day_trades in enumerate(D["by"]):
        new = []
        for t in day_trades:
            rel = cal.get(t["day"])
            if not rel:
                new.append(t)
                continue
            e = t["entry_t"]
            x = t["exit_t"]
            d0 = dt.datetime.fromisoformat(t["day"]).replace(tzinfo=ny)
            act, tt = "keep", t
            for mins in sorted(rel):
                r = int((d0 + dt.timedelta(minutes=mins)).timestamp())
                w0, w1 = r - pre * 60, r + post * 60
                if w0 <= e < w1:
                    act = "skip"
                    break
                if e < w0 and x > w0:
                    tf = 1 if (t.get("tf") == 1 and t["day"] >= "2025-12-29") else 5
                    T, O, H, L = bars(tf)
                    i0 = int(np.searchsorted(T, e))
                    j = int(np.searchsorted(T, w0 - (w0 % (tf * 60)))) if tf == 5 else int(np.searchsorted(T, w0))
                    if i0 >= len(T) or T[i0] != e or j >= len(T) or j <= i0:
                        act = "skip"                 # cannot price the flatten: count it as no trade
                        break
                    ent = O[i0]
                    px = O[j]
                    dr = t["dir"]
                    pts = dr * (px - ent) - FF.SLIP
                    adv = (np.min(L[i0:j]) - ent) if dr > 0 else (ent - np.max(H[i0:j]))
                    fav = (np.max(H[i0:j]) - ent) if dr > 0 else (ent - np.min(L[i0:j]))
                    tt = {**t, "pts": round(float(pts), 2), "w1": round(float(min(0.0, adv, pts)), 2),
                          "up": round(float(max(0.0, fav)), 2), "exit": "NEWS_FLAT", "exit_t": int(T[j])}
                    act = "flat"
                    break
            log.append({"day": t["day"], "entry_t": e, "act": act, "pts_old": t["pts"], "pts_new": tt["pts"] if act == "flat" else
                        (0.0 if act == "skip" else t["pts"]), "exit_old": t["exit"]})
            if act == "keep":
                new.append(t)
            elif act == "flat":
                new.append(tt)
        out.append(new)
    _NEWS_BY[key] = out
    if key == (2, 2):
        NEWS_LOG[:] = log
    return out


def news_summary():
    news_by()
    o = {}
    for nm, a, z in (("H1", "2026-01-01", "2026-06-30"), ("H2", "2026-07-01", "2026-12-31"), ("2021-25", "2021-01-01", "2025-12-31")):
        L = [x for x in NEWS_LOG if a <= x["day"] <= z]
        allT = [t for t in FF.data()["trades"] if a <= t["day"] <= z]
        tot = sum(t["pts"] for t in allT)
        aff = [x for x in L if x["act"] != "keep"]
        o[nm] = {"trades": len(allT), "on_tier1_days": len(L), "flattened": sum(1 for x in L if x["act"] == "flat"),
                 "skipped": sum(1 for x in L if x["act"] == "skip"),
                 "pts_total": round(tot, 1), "pts_lost": round(sum(x["pts_old"] - x["pts_new"] for x in aff), 1),
                 "pts_share_lost": round(100.0 * sum(x["pts_old"] - x["pts_new"] for x in aff) / tot, 1) if tot else None,
                 "tier1_days": sum(1 for d in tier1() if d != "_src" and a <= d <= z)}
    o["detail_2026"] = [x for x in NEWS_LOG if x["day"] >= "2026" and x["act"] != "keep"]
    return o


# ================================================================================================ funded + life with the news rule
def funded_pick(P, cpf, by):
    D = FF.data()
    rows = []
    for c in FF.funded_grid():
        R = [FF.run_funded(P, c, s, by) for s in FF.mc_seqs("H1", 400, FF.H6, 23)]
        paid = np.mean([r["paid"] for r in R])
        loss = np.mean([r["blown"] is not None for r in R])
        rows.append({"cfg": c, "net_per_month": round(float((paid - loss * (cpf or 0)) / 6.0)), "loss_6m": round(100 * float(loss), 1)})
    best = max(rows, key=lambda r: r["net_per_month"])
    return best["cfg"], rows


def funded_mc(P, cfg, span, by, n=1500, cpf=None):
    R = [FF.run_funded(P, cfg, s, by) for s in FF.mc_seqs(span, n, FF.H6, 23)]
    paid = np.array([r["paid"] for r in R])
    lost = np.array([r["blown"] is not None for r in R])
    fr = [r["first"] + 1 for r in R if r["first"] is not None]
    return {"per_month": round(float(paid.mean()) / 6), "loss_6m": round(100 * float(lost.mean()), 1),
            "loss_3m": round(100 * float(np.mean([r["blown"] is not None and r["blown"] < FF.H3 for r in R])), 1),
            "paid_p10_6m": round(float(np.percentile(paid, 10))), "zero_6m": round(100 * float((paid <= 0).mean()), 1),
            "first_med": float(np.median(fr)) if fr else None,
            "net_per_month": round(float(paid.mean() - lost.mean() * (cpf or 0)) / 6)}


def life_paths(P, ce, cf, span, by, offset=0, n=1500):
    """One account bought `offset` sessions into each 6-month path. Pays/lost keyed to the path's session."""
    D = FF.data()
    out = []
    for s in FF.mc_seqs(span, n, FF.H6, 31):
        sub = s[offset:]
        L = life_by(P, ce, cf, sub, by, horizon=FF.H6 - offset)
        L["pays"] = [(k + offset, v) for k, v in L["pays"]]
        L["lost_at"] = [k + offset for k in L["lost_at"]]
        out.append(L)
    return out


def life_by(P, ce, cf, seq, by, horizon):
    """FF.life with the eval on the normal trades and the funded account on `by` (news rule)."""
    return FF.life(P, ce, cf, seq, by, horizon=horizon)


def stack(accts, span, n=1500):
    """accts = [(label, paths)] on the same paths -> together numbers."""
    net = np.array([[a[1][j]["net"] for a in accts] for j in range(n)])
    tot = net.sum(axis=1)
    m46 = np.array([[sum(v for k, v in a[1][j]["pays"] if k >= 63) for a in accts] for j in range(n)])
    pay6 = np.array([[sum(v for k, v in a[1][j]["pays"]) for a in accts] for j in range(n)])
    lost = np.array([[bool(a[1][j]["lost_at"]) for a in accts] for j in range(n)])
    fees = np.array([[a[1][j]["fees"] for a in accts] for j in range(n)]).sum(axis=1)
    return {"accounts": [a[0] for a in accts], "span": span, "paths": n,
            "net_per_month": round(float(tot.mean()) / 6), "net_med_per_month": round(float(np.median(tot)) / 6),
            "net_p10_6m": round(float(np.percentile(tot, 10))), "net_p90_6m": round(float(np.percentile(tot, 90))),
            "neg_6m": round(100 * float((tot < 0).mean()), 1),
            "months4_6_per_month": round(float(m46.sum(axis=1).mean()) / 3),
            "p_m46_ge_2000": round(100 * float((m46.sum(axis=1) / 3 >= 2000).mean()), 1),
            "all_zero_m46": round(100 * float((m46.sum(axis=1) <= 0).mean()), 1),
            "all_zero_6m": round(100 * float((pay6.sum(axis=1) <= 0).mean()), 1),
            "all_lost": round(100 * float(lost.all(axis=1).mean()), 1),
            "any_lost": round(100 * float(lost.any(axis=1).mean()), 1),
            "fees_6m": round(float(fees.mean()))}


# ================================================================================================ the study
def study(log=print):
    PL = rapid_plans()
    old = json.load(open(FFJ, encoding="utf-8"))
    R_old = {p["id"]: p["results"] for p in old["plans"]}
    for k in ("rapid", "rapid_eod"):
        FF_RAPID_OLD[PL[k]["id"]] = R_old[PL[k]["id"]]["eval_cfg"]
    NB = news_by()
    D = FF.data()
    res = {"news": news_summary()}
    log("news", {k: v for k, v in res["news"].items() if k != "detail_2026"})
    for key in ("rapid", "rapid_eod"):
        P = PL[key]
        t0 = dt.datetime.now()
        rows = []
        for c in eval_grid(P):
            o = eval_cost(P, c, "H1")
            rows.append({"cfg": c, "H1": o, "score": round(score_eval(o), 1)})
        old_row = rows[0]
        best = max(rows, key=lambda r: r["score"])
        fast = max(rows, key=lambda r: (r["H1"]["p10"] - r["H1"]["f10"], r["score"]))
        ce = best["cfg"]
        ev = {s: eval_cost(P, ce, s) for s in ("H1", "H2", "2021-25")}
        ev_old = {s: eval_cost(P, old_row["cfg"], s) for s in ("H1", "H2", "2021-25")}
        ev_fast = {s: eval_cost(P, fast["cfg"], s) for s in ("H1", "H2")}
        ev_mc = {s: FF.eval_mc(P, ce, s) for s in ("H1", "H2")}
        cpf = {s: FF.cost_per_funded(P, ev_mc[s]) for s in ("H1", "H2")}
        log(f"{key} eval pick {ce} H1 {ev['H1']} H2 {ev['H2']} ({(dt.datetime.now() - t0).seconds}s)")
        cf, frows = funded_pick(P, cpf["H1"], NB)
        cf_nonews, _ = funded_pick(P, cpf["H1"], D["by"])
        fu = {s: funded_mc(P, cf, s, NB, cpf=cpf.get(s) or cpf["H1"]) for s in ("H1", "H2", "2021-25")}
        fu_nonews = {s: funded_mc(P, cf_nonews, s, D["by"], cpf=cpf.get(s) or cpf["H1"]) for s in ("H1", "H2")}
        fu_worst = {s: funded_mc({**P, "funded": {**P["funded"], "news_skip": True}}, cf, s, D["by"], cpf=cpf.get(s) or cpf["H1"])
                    for s in ("H1", "H2")}
        log(f"{key} funded {cf['pct']}/{cf['pct_max_usd']}/{cf['max_win']} news H1 {fu['H1']} H2 {fu['H2']} | no news "
            f"H1 {fu_nonews['H1']['per_month']} H2 {fu_nonews['H2']['per_month']} | worst H2 {fu_worst['H2']['per_month']}")
        res[key] = {"plan": {k: P[k] for k in ("id", "firm", "plan", "target", "mll", "trail", "lock", "dll", "cons", "min_days",
                                                 "max_micros", "price", "list_price", "monthly", "funded", "price_note", "accounts")},
                    "eval_cfg": ce, "eval": ev, "eval_old_cfg": old_row["cfg"], "eval_old": ev_old,
                    "eval_fast_cfg": fast["cfg"], "eval_fast": ev_fast, "eval_mc": ev_mc, "cost_per_funded": cpf,
                    "eval_grid": [{"cfg": r["cfg"], "H1": {k: r["H1"][k] for k in ("p10", "f10", "p15", "f15", "p60", "f60",
                                                                                     "pass_med", "cost_per_pass")},
                                   "score": r["score"]} for r in rows],
                    "funded_cfg": cf, "funded": fu, "funded_cfg_no_news": cf_nonews, "funded_no_news": fu_nonews,
                    "funded_worst_case_0830": fu_worst,
                    "funded_grid": sorted(frows, key=lambda r: -r["net_per_month"])[:10]}
    # ---------------- stacking
    B = PL["builder"]
    RB = R_old[B["id"]]
    res["stack"] = []
    for span in ("H1", "H2", "2021-25"):
        bl = FF.life_mc(B, RB["eval_cfg"], RB["funded_cfg"], span)
        for key in ("rapid", "rapid_eod"):
            P, Rk = PL[key], res[key]
            cap = 5 if key == "rapid" else 3
            same = life_paths(P, Rk["eval_cfg"], Rk["funded_cfg"], span, NB, 0)
            stag = [same] + [life_paths(P, Rk["eval_cfg"], Rk["funded_cfg"], span, NB, 5 * j) for j in range(1, 5)]
            for N in range(1, 6):
                for mode in ("same_day", "week_apart"):
                    if mode == "week_apart" and N == 1:
                        continue
                    acc = [(f"{key}#{i + 1}", same if mode == "same_day" else stag[i]) for i in range(N)]
                    for with_b in (False, True):
                        o = stack(([("builder", bl)] if with_b else []) + acc, span)
                        o.update(plan=key, N=N, mode=mode, builder=with_b, over_cap=N > cap,
                                 cash_up_front=round(N * P["price"] + (B["price"] if with_b else 0), 2),
                                 cash_up_front_list=round(N * P["list_price"] + (B["list_price"] if with_b else 0), 2))
                        res["stack"].append(o)
            log(f"stack {span} {key}: " + " | ".join(f"N{o['N']} {o['mode'][:4]} B{int(o['builder'])} ${o['net_per_month']}"
                                                      for o in res["stack"] if o["span"] == span and o["plan"] == key and o["builder"]))
    # the Lucid + FundedNext plan (lit-funded-firms.md) for comparison, same paths
    res["compare_lucid_fn"] = [c for c in old["combos"] if c["plans"] == ["mffu_builder_50k", "lucid_pro_50k", "fn_rapid_daily_50k"]]
    # mixes on the same paths: MFFU-only stacks vs spreading over firms (firm risk)
    base_all = {p["id"]: p for p in FF.plans()}
    MIX = {"B+3EOD+2R": [("rapid_eod", 3), ("rapid", 2)], "B+3EOD+Lucid+FN": [("rapid_eod", 3), ("lucid_pro_50k", 1), ("fn_rapid_daily_50k", 1)],
           "B+1EOD+Lucid+FN": [("rapid_eod", 1), ("lucid_pro_50k", 1), ("fn_rapid_daily_50k", 1)],
           "B+2EOD+Lucid": [("rapid_eod", 2), ("lucid_pro_50k", 1)], "B+1R+1EOD": [("rapid", 1), ("rapid_eod", 1)],
           "B+Lucid+FN": [("lucid_pro_50k", 1), ("fn_rapid_daily_50k", 1)]}
    res["mixes"] = []
    for span in ("H1", "H2", "2021-25"):
        bl = FF.life_mc(B, RB["eval_cfg"], RB["funded_cfg"], span)
        cache = {}
        for name, parts in MIX.items():
            acc, cash, cash_l = [("builder", bl)], B["price"], B["list_price"]
            for k, n in parts:
                if k not in cache:
                    if k in ("rapid", "rapid_eod"):
                        cache[k] = life_paths(PL[k], res[k]["eval_cfg"], res[k]["funded_cfg"], span, NB, 0)
                    else:
                        cache[k] = FF.life_mc(base_all[k], R_old[k]["eval_cfg"], R_old[k]["funded_cfg"], span)
                P_ = PL[k] if k in PL else base_all[k]
                acc += [(f"{k}#{i + 1}", cache[k]) for i in range(n)]
                cash += n * P_["price"]
                cash_l += n * P_["list_price"]
            o = stack(acc, span)
            o.update(mix=name, cash_up_front=round(cash, 2), cash_up_front_list=round(cash_l, 2))
            res["mixes"].append(o)
            log(f"mix {span} {name}: ${o['net_per_month']}/mo m4-6 ${o['months4_6_per_month']} neg {o['neg_6m']} zero46 {o['all_zero_m46']} cash ${o['cash_up_front']}")
    return res


def run_all():
    t0 = dt.datetime.now()
    res = study()
    out = {"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "study": "lit_mffu_rapid_stack", "rules_searched": SEARCHED,
           "writeup": "research/writeups/lit-mffu-rapid-stack.md",
           "trades": "exact live LIT trades (run lit_live; 2026 120 trades), $1.90 a micro, 1 tick slippage",
           "rules": RULES, "method": METHOD, **res,
           "tier1_calendar_2026": {d: sorted(v) for d, v in tier1().items() if d != "_src" and d >= "2026"},
           "tier1_sources_2026": {d: v for d, v in tier1()["_src"].items() if d >= "2026"}}
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1, default=float)
    print("wrote", OUT, os.path.getsize(OUT) // 1024, "KB", (dt.datetime.now() - t0).seconds, "s")


METHOD = {
    "eval": "exact = a fresh eval on every session of the half (that half's sessions, no reset, up to 60 sessions); sizing "
            "picked on H1 by p15 - f15 + 0.5 (p60 - f60); 'fast' = the H1 best p10 - f10. Monthly plan: price x months run.",
    "news": "funded only: flat from 2 min before to 2 min after each Tier-1 release (CPI, NFP, FOMC 14:00 + 14:30, FOMC minutes "
            "= decision + 21 days); a trade open then is closed at the open of the release-2 min 1m bar (5m bar on 2021-25) "
            "with 1 tick slippage; an entry inside the window is skipped. worst_case_0830 = every trade open at 08:30 skipped.",
    "funded": "1,500 paths x 126 sessions (5-session blocks); funded_qty grid picked on H1 (400 paths) by ($ paid - P(lost) x "
              "cost per funded) / 6.",
    "life": "6 months from the purchase: eval -> funded; fail / lost -> new eval next session; net = payouts - fees.",
    "stack": "the accounts on the SAME 1,500 paths (same trades). same_day = bought together (identical copies); week_apart "
             "= account j bought 5j sessions later. The Builder 50K uses its lit-funded-firms.md settings."}

C, U, X = "confirmed (several sources agree; MFFU pages not opened: DNS blocked)", "unconfirmed (one source / third party)", "conflict"
S_RAPID = "https://myfundedfutures.com/plans/rapid"
S_EOD = "https://help.myfundedfutures.com/en/articles/16158363-rapid-eod-50k-a-comprehensive-look"
S_PAY = "https://help.myfundedfutures.com/en/articles/13745661"
S_NEWS = "https://help.myfundedfutures.com/en/articles/8230009-news-trading-policy"
S_FM = "https://www.financemagnates.com/forex/myfundedfutures-trades-intraday-drawdown-for-a-30-consistency-rule/"
S_ETF = "https://www.eltraderfinanciado.com/en/news/myfundedfutures/my-funded-futures-launches-rapid-eod-50k-august-2026"
S_PTV = "https://proptradingvibes.com/blog/myfundedfutures-rapid-eod"
S_PTVN = "https://proptradingvibes.com/blog/myfundedfutures-news-trading-policy"
S_PHN = "https://phidiaspropfirm.com/education/myfundedfutures-news-trading"
S_PRICE = "https://proptradingvibes.com/blog/myfundedfutures-pricing"
S_LIM = "https://proptradingvibes.com/blog/myfundedfutures-position-limits"
S_FAIR = "https://help.myfundedfutures.com/en/articles/8444599-fair-play-and-prohibited-trading-practices"
RULES = {   # searched 2026-10-19 (web search results only; the MFFU pages could not be opened from this machine)
    "rapid_50k": {
        "eval": {"target": [3000, C, [S_RAPID, S_FM]], "max_loss": ["$2,000 EOD trailing in the eval", C, [S_RAPID, S_FM]],
                 "daily_loss": [None, C, [S_FM]], "consistency": ["best day <= 50% of eval profit", X + ": most sources 50%, one says none", [S_FM, S_PTV]],
                 "min_days": [2, C, [S_FM]], "max_contracts": ["5 minis / 50 micros", U, [S_FM]],
                 "price": ["$157 list; Aug-2026 guide: 30-day renewal; MFFU went one-time for Builder on 2026-08-25, Rapid not stated", X, [S_PRICE]]},
        "funded": {"drawdown": ["$2,000 INTRADAY trailing (open P&L), locks at +$100", C, [S_RAPID, "https://daytradingz.com/my-funded-futures-review/"]],
                   "payouts": ["daily; first after the $2,100 buffer; $500 minimum; no per-request cap stated; 90% split; no consistency", C, [S_PAY, "https://propfirmsfinder.com/prop-firm/my-funded-futures/payouts/"]],
                   "live_move": ["after $10,000 net profit in one day or a risk decision; profit above that forfeited", U, ["https://propfirmapp.com/?p=265"]],
                   "news": ["Tier-1 banned on sim-funded: no position or working order from 2 min before to 2 min after; Tier 1 = FOMC statement/meeting, FOMC minutes, Employment Report (NFP), CPI (+EIA / ag reports only for those markets); penalty not stated", C + " (third-party wording)", [S_NEWS, S_PTVN, S_PHN]]},
        "accounts": ["up to 5 active sim-funded on 25K/50K plans (Builder: 1); whether caps are per plan or shared across Rapid / Rapid EOD / Builder: not stated", U, [S_LIM, "https://phidiaspropfirm.com/education/how-many-myfundedfutures-accounts"]]},
    "rapid_eod_50k": {
        "eval": {"target": [3000, C, [S_EOD, S_FM, S_ETF]], "max_loss": ["$2,000 EOD trailing", C, [S_EOD, S_FM]],
                 "daily_loss": [None, C, [S_FM]], "consistency": ["best day <= 30% of eval profit (eval only)", C, [S_EOD, S_FM, S_ETF]],
                 "min_days": [4, C, [S_ETF, S_FM]], "max_contracts": ["3 minis / 30 micros", C, [S_ETF, S_FM]],
                 "price": ["$157 one-time, 365 days access (launch Aug 5 2026; 20% code ETFPROMO then, ended)", C, [S_ETF, S_PRICE]]},
        "funded": {"drawdown": ["$2,000 EOD trailing (stays EOD when funded)", C, [S_EOD, S_FM]],
                   "payouts": ["daily; $2,100 buffer before the first; $500 minimum; then >= $500 net profit since the last payout; no cap; 90%; no consistency", C, [S_EOD, S_FM]],
                   "news": ["as Rapid: Tier-1 banned on sim-funded (2 min before / after)", C + " (third-party)", [S_PTVN, S_PHN]]},
        "accounts": ["3 sim-funded Rapid EOD (MFFU on X, per Finance Magnates)", U, [S_FM]]},
    "both": {"automation": ["bots allowed set to your own parameters; HFT and sim-fill exploits banned (MFFU fair play page); some third-party guides say semi-automated only", X, [S_FAIR, "https://blog.traderspost.io/article/my-funded-futures-review"]],
             "copy_own_accounts": ["not stated; fair-play bans copying / coordinating trades 'for an unfair advantage'; one review lists copy trading from external sources as a termination reason", U, [S_FAIR, "https://fundedtrading.com/propfirm/my-funded-futures/"]],
             "next_to_builder": ["not stated anywhere found", U, []]}}


def save():
    from tools import runlib as rl
    out = json.load(open(OUT, encoding="utf-8"))
    PL = rapid_plans()
    D = FF.data()
    NB = news_by()
    for key in ("rapid", "rapid_eod"):
        P, R = PL[key], out[key]
        T = []
        for span in ("2021-25", "H1", "H2"):
            a, z = FF.span_idx(span)
            seq = list(range(a, z))
            k = 0
            while k < len(seq):
                e, n = FF.run_eval(P, R["eval_cfg"], seq[k:], D["by"], horizon=len(seq) - k)
                k += n
                if e != "PASS":
                    if e == "OPEN":
                        break
                    continue
                keep = []
                f = FF.run_funded(P, R["funded_cfg"], seq, NB, start=k, keep=keep)
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
        T.sort(key=lambda t: t["entry_t"])
        S = rl.score(T, D["sess"])
        e1, e2, f1, f2 = R["eval"]["H1"], R["eval"]["H2"], R["funded"]["H1"], R["funded"]["H2"]
        verdict = (f"MFFU {P['plan']}, eval sizing {R['eval_cfg']}: p10/f10 H1 {e1['p10']}/{e1['f10']} H2 {e2['p10']}/{e2['f10']}, "
                   f"eventual pass {e1['p60']} / {e2['p60']}%, pass_med {e1['pass_med']} / {e2['pass_med']}, $ per pass "
                   f"{e1['cost_per_pass']} / {e2['cost_per_pass']}; funded with the real Tier-1 calendar ${f1['per_month']} / "
                   f"${f2['per_month']} a month, lost {f1['loss_6m']} / {f2['loss_6m']}% in 6 months (H1 / H2).")
        rl.save("lit_mrs_" + key, f"LIT on MFFU {P['plan']} (consistency-aware eval + funded with the Tier-1 calendar)", "risk",
                "Can stacked MFFU Rapid / Rapid EOD accounts run LIT next to the Builder 50K, and what do they pay?",
                params={"plan": {k: P[k] for k in ("target", "mll", "trail", "lock", "dll", "cons", "min_days", "max_micros",
                                                   "price", "funded")}, "news": METHOD["news"]},
                sizing={"eval": R["eval_cfg"], "funded": R["funded_cfg"]}, trades=T, scored=S, status="info", verdict=verdict,
                notes="tools/lit_mffu_rapid_stack.py; stored trades = back-to-back real history, funded trades only (news rule "
                      "applied). The run library's eval columns are not this plan's: see the verdict and "
                      "research/lit/mffu_rapid_stack.json.",
                writeup="lit-mffu-rapid-stack", tags=["lit", "lit_mffu_rapid_stack"])
        print("saved lit_mrs_" + key, flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd == "all":
        run_all()
    elif cmd == "save":
        save()
    elif cmd == "news":
        print(json.dumps(news_summary(), indent=1, default=float))
