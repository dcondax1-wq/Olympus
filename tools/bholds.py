"""B-holds vs LIT priority (owner 2026-10-27): when ATLAS (account B, Builder 25K) is in a trade and LIT (Zlarior, Builder
50K) signals the OTHER way, who gives way?

  lit_priority (live today)  B is closed at market at LIT's entry (HEDGE, 1 tick slippage), LIT takes its trade.
  b_holds                    LIT's opposite entry is SKIPPED while B is open; B runs to its own exit. LIT's same-direction
                             entries are unaffected; LIT open still blocks an opposite B entry (both rules); LIT's armed
                             opposite setups still block a B entry (both rules, tools/atlas_lit_armed.py).

A skipped LIT signal is lost for the day (LIT takes 1 trade a day; the live model does not look for a second one).
Which B trades "hold" is decided on the candidate trades (B's own one position + max 2 a day applied in entry order);
B's eval sizing / soft daily loss can still drop such a B trade later, the LIT skip stays (small approximation, both ways
the same code). Executors = the repo's own: LIT on the Builder 50K = tools/second_mix.run_eval (live lit_sizing two_week,
room_f 0.8, then safe_eval; $1,000 soft daily loss; $1.90 a micro); ATLAS on the Builder 25K = tools/atlas.score
(tools/second_account_b.score: need size = engine/account_b.qty, stuck < $100, max 2 a day, $600 soft loss).
Fresh eval every session (20 sessions) for the odds; $ = the back-to-back eval path of each account.

    python -X utf8 tools/bholds.py           # table -> research/second/bholds.json
    python -X utf8 tools/bholds.py save      # + rl.save runs bholds_*
Paper research only: edits no engine file, no live_model*.json, no second_model.json.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import second_mix as M  # noqa: E402
from tools import second_account_b as SAB  # noqa: E402
from tools import atlas as A  # noqa: E402
from tools import atlas_lit_armed as ARM  # noqa: E402

ET = ZoneInfo("America/New_York")
OUT = os.path.join(ROOT, "research", "second", "bholds.json")
M.SPANS.update({"2026": ("2026-01-01", "2026-12-31"), "2021-25": ("2021-01-01", "2025-12-31")})
SPANS = ("H1", "H2", "2026", "2025", "2021-24", "2021-25")
RULES = ("lit_priority", "b_holds")


def hm(ts):
    return dt.datetime.fromtimestamp(int(ts), ET).strftime("%H:%M")


def raw_b():
    V = A.BASE
    U = []
    for nm in V["members"]:
        U += A.member_units(nm, V)
    pr = {nm: i for i, nm in enumerate(V["members"])}
    return sorted(U, key=lambda t: (t["entry_t"], pr.get(t["src"], 9)))


def build(rule):
    """(LIT units, B units, conflict list) under a rule."""
    LIT = M.units()["LIT"]
    by = collections.defaultdict(list)
    for x in LIT:
        by[x["day"]].append(x)
    AW = ARM.by_day()
    skipped, conf, out = set(), [], []
    busy, nday, cur = 0, 0, None
    for t in raw_b():
        if t["day"] != cur:
            cur, busy, nday = t["day"], 0, 0
        L = [x for x in by.get(t["day"], ()) if x["dir"] != t["dir"] and x["entry_t"] not in skipped]
        if any(x["entry_t"] <= t["entry_t"] < x["exit_t"] for x in L):
            continue                                        # LIT open the other way: no B entry (both rules)
        if any(d != t["dir"] and a <= t["entry_t"] < z for d, a, z in AW.get(t["day"], ())):
            continue                                        # LIT armed the other way: no B entry (both rules)
        taken = t["entry_t"] >= busy and nday < 2
        nxt = min((x for x in L if t["entry_t"] < x["entry_t"] < t["exit_t"]), key=lambda x: x["entry_t"], default=None)
        if nxt is not None and taken:
            pts, w1 = M.cut_at(t, nxt["entry_t"])
            conf.append({"day": t["day"], "src": t["src"], "b_dir": t["dir"], "b_in": hm(t["entry_t"]), "lit_in": hm(nxt["entry_t"]),
                         "b_exit_full": t["exit"], "b_r_full": round(t["pts"] / t["risk"], 2), "b_r_cut": round(pts / t["risk"], 2),
                         "lit_exit": nxt["exit"], "lit_r": round(nxt["pts"] / nxt["risk"], 2), "lit_entry_t": nxt["entry_t"]})
        if nxt is not None:
            if rule == "lit_priority":
                pts, w1 = M.cut_at(t, nxt["entry_t"])
                t = {**t, "pts": pts, "w1": w1, "exit_t": nxt["entry_t"], "exit": "HEDGE"}
            elif taken:
                for x in L:
                    if t["entry_t"] < x["entry_t"] < t["exit_t"]:
                        skipped.add(x["entry_t"])
                t = {**t, "held": True}
        if taken:
            busy, nday = t["exit_t"], nday + 1
        out.append(t)
    return [x for x in LIT if x["entry_t"] not in skipped], out, conf, skipped


# ================================================================================================ LIT eval on the 50K
def lit_score(U, span):
    by = M.by_day(U)
    S = M.span_days(span)
    res = [(M.run_eval(S[i:i + 20], by, "usd500"), len(S) - i) for i in range(len(S))]
    o = {"starts": len(S)}
    for lab, h in (("10", 10), ("15", 15), ("20", 20)):
        R = [r for r, av in res if av >= h]
        N = len(R) or 1
        o["p" + lab] = round(100.0 * sum(1 for r in R if r[0] == "PASS" and r[1] <= h) / N, 1)
        o["f" + lab] = round(100.0 * sum(1 for r in R if r[0] == "FAIL" and r[1] <= h) / N, 1)
    o["dec10"] = round(o["p10"] + o["f10"], 1)
    pas = [r[1] for r, _ in res if r[0] == "PASS" and r[1] <= 20]
    o["pass_med"] = float(np.median(pas)) if pas else None
    o["slow_pass"] = round(100.0 * sum(1 for x in pas if x > 15) / len(pas), 1) if pas else None
    k, T = 0, []
    while k < len(S):
        r, used = M.run_eval(S[k:], by, "usd500", len(S) - k, keep=T)
        if r == "OPEN":
            break
        k += used
    o.update(money(T, len(S)))
    return o, T


def money(T, nsess):
    T = sorted(T, key=lambda t: t["exit_t"])
    p = np.array([t["pnl"] for t in T]) if T else np.zeros(1)
    gl = -p[p < 0].sum()
    eq = np.cumsum(p)
    return {"n": len(T), "tpw": round(len(T) / (nsess / 5), 2), "net": round(float(p.sum())),
            "per_month": round(float(p.sum()) / (nsess / 21)), "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None,
            "dd": round(float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min())),
            "wk2": wk2(T, nsess)}


def wk2(T, nsess):
    """% of weeks with 2+ trades (weeks with at least one session)."""
    c = collections.Counter(dt.date.fromisoformat(t["day"]).isocalendar()[:2] for t in T)
    return c


_LL = {}


def lit_live():
    """entry_t -> the run lit_live trade (LIT's own size rule, $800 a trade up to 20 pts), re-priced at the live $1.90 a micro."""
    if "t" not in _LL:
        from tools import runlib as rl
        r = rl.load("lit_live")
        T = [dict(zip(r["trade_cols"], x)) for x in r["trades"]]
        _LL["t"] = {int(t["entry_t"]): {**t, "pnl": round(t["pnl"] - 0.5 * t["qty"], 2)} for t in T}
    return _LL["t"]


def lit_money(LU, span):
    S = M.span_days(span)
    a, z = S[0], S[-1]
    LL = lit_live()
    T = [{**LL[x["entry_t"]], "exit_t": x["exit_t"]} for x in LU if a <= x["day"] <= z]
    return money(T, len(S)), T


def score_rule(rule):
    LU, BU, conf, skipped = build(rule)
    o = {}
    paths = {}
    for s in SPANS:
        lo, lT = lit_score(LU, s)
        with A.Plan(A.BASE) as pl:
            bo, bT = SAB.score(BU, "atlas", s, pl.safe_rule)
        S = M.span_days(s)
        a, z = S[0], S[-1]
        lm, lmT = lit_money(LU, s)
        cm = money(lmT + bT, len(S))
        weeks = sorted({dt.date.fromisoformat(d).isocalendar()[:2] for d in S})
        for x, T in ((lo, lT), (lm, lmT), (cm, lmT + bT)):
            c = collections.Counter(dt.date.fromisoformat(t["day"]).isocalendar()[:2] for t in T)
            x["wk2"] = round(100.0 * sum(1 for w in weeks if c.get(w, 0) >= 2) / len(weeks), 1)
        cb = collections.Counter(dt.date.fromisoformat(t["day"]).isocalendar()[:2] for t in bT)
        bo["wk2"] = round(100.0 * sum(1 for w in weeks if cb.get(w, 0) >= 2) / len(weeks), 1)
        cf = [c for c in conf if a <= c["day"] <= z]
        LL = lit_live()
        for c in cf:
            c["lit_usd"] = LL[c["lit_entry_t"]]["pnl"]
        o[s] = {"lit": lo, "lit_money": lm, "b": bo, "comb": cm,
                "conflicts": len(cf), "lit_skipped": sum(1 for x in skipped if a <= dt.datetime.fromtimestamp(x, ET).date().isoformat() <= z),
                "b_hedge_path": sum(1 for t in bT if t["exit"] == "HEDGE"),
                "b_held_path": sum(1 for t in bT if any(c["day"] == t["day"] and c["b_in"] == hm(t["entry_t"]) for c in cf)) if rule == "b_holds" else 0,
                "conf": cf}
        paths[s] = (lmT, bT)          # LIT stored at its own size rule (run lit_live, $1.90)
    return o, paths


def line(nm, x):
    return (f"{nm:5s} n {x['n']:4d} tpw {x['tpw']:4.2f} wk2 {x.get('wk2')} net {x['net']:+8,} ({x['per_month']:+6,}/mo) PF {x['pf']} "
            f"DD {x['dd']:,}" + (f" | 2w {x['p10']}/{x['f10']} dec10 {x['dec10']} 15 {x['p15']}/{x['f15']} slow {x['slow_pass']} "
                                 f"med {x['pass_med']}" if "p10" in x else ""))


def main(save=False):
    M.units()
    R = {}
    for rule in RULES:
        R[rule] = score_rule(rule)
        print("=" * 30, rule, flush=True)
        for s in SPANS:
            x = R[rule][0][s]
            print(f"-- {s}: conflicts {x['conflicts']}, LIT skipped {x['lit_skipped']}, B HEDGE on path {x['b_hedge_path']}, "
                  f"B held on path {x['b_held_path']}")
            for nm in ("lit", "lit_money", "b", "comb"):
                print("   " + line(nm, x[nm]), flush=True)
    conf = R["b_holds"][0]["2026"]["conf"]
    print("2026 conflicts (R per trade, size-free):")
    for c in conf:
        print("  ", {k: v for k, v in c.items() if k != "lit_entry_t"})
    for s in SPANS:
        cf = R["b_holds"][0][s]["conf"]
        if cf:
            print(f"{s}: {len(cf)} conflicts; B full {sum(c['b_r_full'] for c in cf):+.1f}R vs cut {sum(c['b_r_cut'] for c in cf):+.1f}R; "
                  f"LIT skipped {sum(c['lit_r'] for c in cf):+.1f}R = ${sum(c['lit_usd'] for c in cf):+,.0f} at LIT's size; "
                  f"LIT wins/losses skipped {sum(1 for c in cf if c['lit_r'] > 0.1)}/{sum(1 for c in cf if c['lit_r'] < -0.1)}; "
                  f"B held better {sum(1 for c in cf if c['b_r_full'] > c['b_r_cut'])}/{len(cf)}")
    dump = {r: {s: {k: v for k, v in R[r][0][s].items()} for s in SPANS} for r in RULES}
    json.dump(dump, open(OUT, "w", encoding="utf-8"), indent=1, default=str)
    print("wrote", OUT)
    if save:
        store(R)
    return R


def store(R):
    from tools import runlib as rl
    sess = [d for d in M.units()["sessions"] if d >= "2021-01-01"]
    Q = ("Owner 2026-10-27: when ATLAS (account B, 25K) holds a trade and LIT (50K) signals the other way, should B hold and "
         "LIT skip (b_holds) instead of B closed at market (lit_priority, live)?")
    for rule in RULES:
        o, P = R[rule]
        for acct, k in (("lit", 0), ("b", 1)):
            T = []
            for s in ("2026", "2021-25"):
                for t in P[s][k]:
                    T.append({"day": t["day"], "entry_t": t["entry_t"], "exit_t": t["exit_t"], "dir": t["dir"],
                              "r": round(t["pnl"] / t["risk_usd"], 3) if t["risk_usd"] else 0.0, "pnl": t["pnl"],
                              "risk_pts": t.get("risk", t.get("risk_pts")), "qty": t["qty"], "risk_usd": t["risk_usd"], "half": False,
                              "exit": t["exit"], "trigger": t.get("src", t.get("trigger")), "mfe": None, "mae": None, "bars_held": None,
                              "regime": "", "mult": None, "low": t.get("low", min(0.0, t["pnl"]))})
            mk = "lit_money" if acct == "lit" else "b"
            f = lambda s: (f"{o[s][mk]['tpw']}/wk, {o[s][mk]['net']:+,} (${o[s][mk]['per_month']:,}/mo, PF {o[s][mk]['pf']}, "
                           f"DD {o[s][mk]['dd']:,}); 2-week pass/fail {o[s][acct]['p10']}/{o[s][acct]['f10']}, med {o[s][acct]['pass_med']}; "
                           f"conflicts {o[s]['conflicts']}, LIT skipped {o[s]['lit_skipped']}")
            rid = f"bholds_{rule}_{acct}"
            title = f"{'LIT 50K' if acct == 'lit' else 'ATLAS 25K'} under rule {rule} (B-holds vs LIT priority)"
            rl.save(rid, title, "other", Q, params={"rule": rule, "account": acct}, sizing={"lit": "two_week 50K", "b": "need 25K"},
                    trades=T, scored=rl.score(T, sess), status="rejected" if rule == "b_holds" else "info",
                    verdict=f"H1 {f('H1')}. H2 {f('H2')}. 2021-25 {f('2021-25')}.",
                    notes="tools/bholds.py; trades: LIT = run lit_live trades at LIT's own size rule ($1.90 a micro) minus the skipped "
                          "ones; ATLAS = its back-to-back Builder 25K eval path; 2026 and 2021-25. The run library's own eval "
                          "columns re-score these trades on the 50K plan and are not the published odds (verdict has them).",
                    writeup="b-holds-vs-lit-priority", tags=["second", "account_b", "atlas", "hedge"])
            print("saved", rid, flush=True)


if __name__ == "__main__":
    ARM_CACHE = os.environ.get("BHOLDS_ARMED")
    if ARM_CACHE:
        ARM.CACHE = ARM_CACHE
    main(save=len(sys.argv) > 1 and sys.argv[1] == "save")
