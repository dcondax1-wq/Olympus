"""ATLAS funded-25K risk at real fills (2026-11-20, night-atlasrisk): the open Decide items about ATLAS's money (room 40%,
keep trading under $100, ask at $1,000, the Rapid ATLAS lane) and "pause ATLAS?" re-judged at 3 / 6 / 10 ticks a side
from today's real account. Design (committed before any run): research/second/atlas_risk_design.md.
Write-up: research/writeups/atlas-risk-real-fills-2026-11-20.md.

RESEARCH ONLY. Nothing here touches second_model.json, data/account_b.json, live_model*.json or any engine file.

  python -X utf8 tools/atlas_risk.py run            # 1,000 paths a market (run it through /home/user/heavy.sh)
  python -X utf8 tools/atlas_risk.py run --n 200    # quick, noisier
  python -X utf8 tools/atlas_risk.py posthoc        # room 40% + ask $1,000 / + the 1-micro probe (added after the run)
  python -X utf8 tools/atlas_risk.py cards          # the Decide-card value fields (10 ticks) -> atlas_risk.json "cards"
  python -X utf8 tools/atlas_risk.py show           # print the stored table + the bar

Engines: the funded 25K = tools/atlas_more PGF2 (MFFU Builder 25K funded rules, the live funded preset, the stuck line,
MFFU's inactivity close) from today's account (tools/atlas_health.at_today); the Rapid 25K = tools/money/money_plan.RSeat
on tools/money/rapid25.acct("25k", keep $500). ATLAS's trades re-priced with tools/atlas_fills.priced (N ticks a side).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools", "money"))
import logging  # noqa: E402
logging.getLogger("engine.sizing").setLevel(logging.ERROR)

DATE = "2026-11-20"
DESIGN = "research/second/atlas_risk_design.md"
OUT = os.path.join(ROOT, "research", "second", "atlas_risk.json")
COSTS = (1, 3, 6, 10)
JUDGE = (6, 10)
SPANS = ("H1", "H2", "REF")
TOKEN_USD = 3.0           # a 1-micro scratch trade a week to keep MFFU's 7-day rule ($1.90 + about 2 ticks), PAUSE only
SPLIT = 0.8

# the funded 25K options (each one change against today's approved base = min_room 0, 60% of the room, ask $750)
FUNDED = {
    "base": {"stuck": 0.0},
    "O1_room40": {"stuck": 0.0, "pct": 0.4},
    "O2_old_stop100": {"stuck": 100.0},
    "O3_ask1000": {"stuck": 0.0, "ask": 1000.0},
    "O5a_pause4wk": {"stuck": 0.0, "pause": 20},
    "O5b_probe1micro": {"stuck": 0.0, "probe": 25},
}
POST_HOC = {   # added AFTER the run (O1, O3 and O5b passed): shown, never eligible
    "PH1_room40_ask1000": {"stuck": 0.0, "pct": 0.4, "ask": 1000.0},
    "PH2_room40_probe1micro": {"stuck": 0.0, "pct": 0.4, "probe": 25},
}
RAPID = {"base": 250, "O4a_atlas_off": 0, "O4b_atlas150": 150}
CARD = {"O1_room40": "atlas-funded-room-40", "O2_old_stop100": "atlas-funded-keep-trading", "O3_ask1000": "payout-ping-1000",
        "O4a_atlas_off": "atlas-on-rapid", "O4b_atlas150": "atlas-on-rapid", "O5a_pause4wk": "pause", "O5b_probe1micro": "pause",
        "O5c_stop": "pause"}
_C = {}


def _AF():
    from tools import atlas_fills as AF
    return AF


def _AM():
    return _AF()._AM()


def T_at(n):
    AF = _AF()
    return AF.to_T([AF.priced(u, n, n) for u in AF.units()])


def calendar():
    if "cal" not in _C:
        import payday_plan as PD
        _C["cal"] = PD.calendar()
    return _C["cal"]


def first_stats(firsts):
    """median first payout over ALL paths (None = never in 6 months) -> (session k | None, date | None, % no payout)."""
    cal = calendar()
    arr = np.array([f if f else 10 ** 6 for f in firsts], dtype=float)
    m = float(np.percentile(arr, 50, method="lower"))
    nop = round(100.0 * float(np.mean(arr >= 10 ** 6)), 1)
    if m >= 10 ** 6 or nop >= 50.0:              # design: "none in 6 months" when half or more of the paths never pay
        return None, None, nop
    return int(m), cal[int(m) - 1], nop


# ================================================================================================ the funded 25K
def pgf3():
    if "PGF3" in _C:
        return _C["PGF3"]
    P2 = _AM()._pgf()

    class PGF3(P2):
        """atlas_more PGF2 + ask (the request line), pause (no ATLAS trade for the first N sessions), probe (1 micro for the
        first N sessions)."""

        def __init__(self, I):
            super().__init__(I)
            if I.get("ask") is not None:
                self.P["ask_above"] = float(I["ask"])
            self.sess = 0

        def qty(self, t, st):
            q = super().qty(t, st)
            I = self.I
            if I.get("pause") and self.sess < int(I["pause"]):
                return 0
            if I.get("probe") and self.sess < int(I["probe"]) and q > 1:
                return 1
            return q

        def step(self, ts, keep=None):
            r = super().step(ts, keep)
            self.sess += 1
            return r

    _C["PGF3"] = PGF3
    return PGF3


def funded_ctx(n):
    if ("fctx", n) not in _C:
        import builder_levers as BL
        from tools import uprisk as U
        S = _AM().sessions()
        _C[("fctx", n)] = (S, {sp: U.mc_paths(S, sp, n, length=BL.LEN, seed=BL.A4.SEED_LIFE) for sp in SPANS})
    return _C[("fctx", n)]


def funded_row(I, T, n):
    from tools import atlas_revive as RV
    AM = _AM()
    S, PF = funded_ctx(n)
    BY = RV.by_session(T, S)
    PG = pgf3()
    out = {}
    for sp in SPANS:
        r = AM.run_paths(BY, PF[sp], lambda: AM.at_today(PG(I)))
        k, d, nop = first_stats(r["_first"])
        usd = float(np.mean(r["_pm"]))
        if I.get("pause"):
            usd -= (int(I["pause"]) / 5.0) * TOKEN_USD * SPLIT / 6.0
        out[sp] = {"usd_m": round(usd), "first_k": k, "first_date": d, "no_pay_6m": nop, "lost_6m": r["dead_6m"],
                   "floor_6m": r["lost_6m"], "idle_6m": r["idle_6m"], "stuck_6m": r["stuck_6m"], "payouts": r["payouts"],
                   "_pm": r["_pm"], "_end": r["_end"]}
    return out


# ================================================================================================ the Rapid 25K
def rapid_patch(T):
    import rapid_levers as RL
    import stack_one_account as SOA
    AT = [{"day": t["day"], "risk": float(t["risk"]), "tgt": t.get("tgt"), "pts": float(t["pts"]), "w1": float(t["w1"]),
           "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "dir": int(t["dir"]), "strat": "ATLAS", "src": t["src"]} for t in T]
    SOA._atlas = lambda: AT
    SOA._blitz = lambda: []
    SOA._D.clear()
    RL._MB.clear()


def rapid_spec(lane):
    import rapid25 as R25
    import rapid_levers as RL
    sp = R25.acct("25k", ("cushion", 500.0), atlas=(lane or 250))
    if not lane:
        sp = dict(sp)
        sp["BYe"], sp["BYf"], sp["mix_f"] = RL.mix_by(("LIT",)), RL.mix_by(("LIT",), news=True), ("LIT",)
    return sp


def rapid_paths(n):
    if ("rp", n) not in _C:
        import account4_sim as A4
        import rapid_levers as RL
        import stack_one_account as SOA
        from tools import uprisk as U
        S = SOA.data()["S"]
        _C[("rp", n)] = {sp: U.mc_paths(S, sp, n, length=RL.LEN, seed=A4.SEED_LIFE) for sp in SPANS}
    return _C[("rp", n)]


def rapid_row(spec, n):
    import money_plan as MP
    import rapid_levers as RL
    PF = rapid_paths(n)
    out = {}
    for sp in SPANS:
        net, firsts, lost = [], [], []
        for seq in PF[sp]:
            s = MP.RSeat(spec, join=0)
            own = cost = 0.0
            first = None
            for k, si in enumerate(seq[:RL.LEN]):
                o, c = s.step(k, si)
                own += o
                cost += c
                if o > 0 and first is None:
                    first = k + 1
            net.append(own - cost)
            firsts.append(first)
            lost.append(s.lost > 0)
        k, d, nop = first_stats(firsts)
        out[sp] = {"usd_m": round(float(np.mean(net)) / MP.MO), "first_k": k, "first_date": d, "no_pay_6m": nop,
                   "lost_6m": round(100.0 * float(np.mean(lost)), 1)}
    return out


# ================================================================================================ the bar
def bar(ch, base):
    """design: better only if at BOTH 6 and 10 ticks: loss lower in H1 and H2 by >= 0.5 and REF not up > 0.5, AND $ >= 90%
    of the base's in H1 and H2 and REF >= base - $10."""
    why = []
    for n in JUDGE:
        a, b = ch[f"{n}t"], base[f"{n}t"]
        for sp in ("H1", "H2"):
            if not a[sp]["lost_6m"] <= b[sp]["lost_6m"] - 0.5:
                why.append(f"{n}t {sp} loss {b[sp]['lost_6m']} -> {a[sp]['lost_6m']}% (needs -0.5)")
            if a[sp]["usd_m"] < 0.9 * b[sp]["usd_m"]:
                why.append(f"{n}t {sp} ${b[sp]['usd_m']} -> ${a[sp]['usd_m']}/mo (< 90%)")
        if a["REF"]["lost_6m"] > b["REF"]["lost_6m"] + 0.5:
            why.append(f"{n}t REF loss {b['REF']['lost_6m']} -> {a['REF']['lost_6m']}%")
        if a["REF"]["usd_m"] < b["REF"]["usd_m"] - 10:
            why.append(f"{n}t REF ${b['REF']['usd_m']} -> ${a['REF']['usd_m']}/mo")
    return (not why), why


def bar_at(ch, base, n):
    """the pause question: the same bar at one cost (10 ticks)."""
    a, b = {f"{n}t": ch[f"{n}t"]}, {f"{n}t": base[f"{n}t"]}
    global JUDGE
    keep, JUDGE = JUDGE, (n,)
    try:
        return bar(a, b)
    finally:
        JUDGE = keep


def paired_loss(ch, base, n, sp):
    """paths lost by the challenger but not the base, and the other way (same paths)."""
    dead = ("lost", "stuck", "idle")
    a, b = ch[f"{n}t"][sp]["_end"], base[f"{n}t"][sp]["_end"]
    return {"only_ch": sum(1 for x, y in zip(a, b) if x in dead and y not in dead),
            "only_base": sum(1 for x, y in zip(a, b) if y in dead and x not in dead), "n": len(a)}


def answer(passers):
    """the design's rule ("pause" only if a pause-family variant passes at 10 ticks) in plain words: O5b is not a pause, it
    keeps trading at 1 micro, so a lone O5b pass reads "keep trading, smaller"."""
    if any(k in passers for k in ("O5a_pause4wk", "O5c_stop")):
        return "pause / stop (" + ", ".join(passers) + ")"
    if passers == ["O5b_probe1micro"]:
        return "keep trading, smaller: 1 micro for 25 sessions, then normal (O5b passed; a real pause and a stop did not)"
    return "keep trading"


def stop_row():
    return {sp: {"usd_m": 0, "first_k": None, "first_date": None, "no_pay_6m": 100.0, "lost_6m": 0.0} for sp in SPANS}


# ================================================================================================ run
def strip(r):
    return {sp: {k: v for k, v in x.items() if not k.startswith("_")} for sp, x in r.items()}


def cmd_run(n=1000, log=print):
    t0 = time.time()
    res = {"date": DATE, "design": DESIGN, "n_paths": n, "costs": list(COSTS), "funded": {k: {} for k in FUNDED},
           "rapid": {k: {} for k in RAPID}}
    full = {k: {} for k in FUNDED}
    for c in COSTS:
        T = T_at(c)
        for nm, I in FUNDED.items():
            r = funded_row(I, T, n)
            full[nm][f"{c}t"] = r
            res["funded"][nm][f"{c}t"] = strip(r)
            log(f"funded {nm:16s} {c:2d}t " + " | ".join(f"{sp} ${r[sp]['usd_m']}/mo 1st {r[sp]['first_date']} lost {r[sp]['lost_6m']}%"
                                                         f" (floor {r[sp]['floor_6m']} idle {r[sp]['idle_6m']} stuck {r[sp]['stuck_6m']})"
                                                         for sp in SPANS) + f"  [{time.time() - t0:.0f}s]")
        rapid_patch(T)
        for nm, lane in RAPID.items():
            if nm == "O4a_atlas_off" and c != COSTS[0]:
                res["rapid"][nm][f"{c}t"] = res["rapid"][nm][f"{COSTS[0]}t"]      # LIT alone: no ATLAS trade to re-price
                continue
            r = rapid_row(rapid_spec(lane), n)
            res["rapid"][nm][f"{c}t"] = r
            log(f"rapid  {nm:16s} {c:2d}t " + " | ".join(f"{sp} ${r[sp]['usd_m']}/mo 1st {r[sp]['first_date']} no pay {r[sp]['no_pay_6m']}% "
                                                         f"lost {r[sp]['lost_6m']}%" for sp in SPANS) + f"  [{time.time() - t0:.0f}s]")
    res["funded"]["O5c_stop"] = {f"{c}t": stop_row() for c in COSTS}
    # the bar
    J = {}
    for nm in FUNDED:
        if nm == "base":
            continue
        ok, why = bar(res["funded"][nm], res["funded"]["base"])
        J[nm] = {"card": CARD[nm], "better": ok, "why_not": why,
                 "paired_lost": {f"{c}t": {sp: paired_loss(full[nm], full["base"], c, sp) for sp in SPANS} for c in JUDGE}}
    ok, why = bar(res["funded"]["O5c_stop"], res["funded"]["base"])
    J["O5c_stop"] = {"card": "pause", "better": ok, "why_not": why}
    for nm in ("O4a_atlas_off", "O4b_atlas150"):
        ok, why = bar(res["rapid"][nm], res["rapid"]["base"])
        J[nm] = {"card": CARD[nm], "better": ok, "why_not": why}
    P = {}
    for nm in ("O5a_pause4wk", "O5b_probe1micro", "O5c_stop"):
        ok, why = bar_at(res["funded"][nm], res["funded"]["base"], 10)
        P[nm] = {"better_at_10t": ok, "why_not": why}
    b10 = res["funded"]["base"]["10t"]
    P["keep_pays_at_10t"] = all(b10[sp]["usd_m"] > 50 for sp in ("H1", "H2"))
    P["passers_at_10t"] = [k for k in ("O5a_pause4wk", "O5b_probe1micro", "O5c_stop") if P[k]["better_at_10t"]]
    P["answer"] = answer(P["passers_at_10t"])
    res["bar"], res["pause"] = J, P
    res["cards"] = card_values(res)
    res["took_s"] = round(time.time() - t0)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)
    show(res, log)
    log(f"wrote {os.path.relpath(OUT, ROOT)}  [{res['took_s']}s]")
    return res


def cmd_posthoc(n=1000, log=print):
    """post-hoc combos against O1 (room 40%) at the same cost: does ask $1,000 or the 1-micro probe add anything once room 40%
    is in? Shown, never eligible (design: research/second/atlas_risk_design.md)."""
    res = json.load(open(OUT, encoding="utf-8"))
    ph = {"note": "post-hoc (added after O1 / O3 / O5b passed): shown, never eligible", "rows": {}, "vs_room40": {}}
    for c in COSTS:
        T = T_at(c)
        for nm, I in POST_HOC.items():
            r = strip(funded_row(I, T, n))
            ph["rows"].setdefault(nm, {})[f"{c}t"] = r
            log(f"posthoc {nm:22s} {c:2d}t " + " | ".join(f"{sp} ${r[sp]['usd_m']}/mo 1st {r[sp]['first_date']} lost {r[sp]['lost_6m']}%" for sp in SPANS))
    for nm in POST_HOC:
        ok, why = bar(ph["rows"][nm], res["funded"]["O1_room40"])
        ph["vs_room40"][nm] = {"better": ok, "why_not": why}
        log(f"posthoc {nm} vs room 40%: {'better' if ok else 'not better: ' + '; '.join(why)[:300]}")
    res["posthoc"] = ph
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)
    return ph


def card_values(res):
    """the Decide-card value fields this study sets (10 ticks a side; usd_month = the Jul-Oct-like $ change, like money_plan's):
    room 40% vs today, keep trading (min_room 0) vs the old $100 stop, ATLAS on the Rapid vs LIT alone."""
    F, R, c = res["funded"], res["rapid"], "10t"

    def d(a, b):
        return {"jan_jun": a["H1"]["usd_m"] - b["H1"]["usd_m"], "jul_oct": a["H2"]["usd_m"] - b["H2"]["usd_m"],
                "y2021_25": a["REF"]["usd_m"] - b["REF"]["usd_m"]}
    out = {"atlas-funded-room-40": {"by": d(F["O1_room40"][c], F["base"][c]), "recommend": "yes" if res["bar"]["O1_room40"]["better"] else "no"},
           "atlas-funded-keep-trading": {"by": d(F["base"][c], F["O2_old_stop100"][c]), "recommend": "yes"},
           "atlas-on-rapid": {"by": d(R["base"][c], R["O4a_atlas_off"][c]),
                              "recommend": "no" if res["bar"]["O4a_atlas_off"]["better"] else "yes"}}
    for v in out.values():
        v["usd_month_by"] = v.pop("by")
        v["usd_month"] = v["usd_month_by"]["jul_oct"]
    return out


def cmd_cards(log=print):
    res = json.load(open(OUT, encoding="utf-8"))
    res["cards"] = card_values(res)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)
    for k, v in res["cards"].items():
        log(f"card {k}: {json.dumps(v)}")
    return res["cards"]


def show(res=None, log=print):
    res = res or json.load(open(OUT, encoding="utf-8"))
    for grp in ("funded", "rapid"):
        for nm, rows in res[grp].items():
            for c, r in rows.items():
                log(f"{grp:6s} {nm:16s} {c:>3s} " + " | ".join(f"{sp} ${r[sp]['usd_m']} {r[sp]['first_date'] or 'none'} lost {r[sp]['lost_6m']}%" for sp in SPANS))
    for nm, j in res["bar"].items():
        log(f"BAR {nm:16s} ({j['card']}): {'BETTER' if j['better'] else 'not better: ' + '; '.join(j['why_not'])[:400]}")
    log(f"PAUSE at 10t: {json.dumps(res['pause'])[:800]}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "posthoc", "cards", "show"])
    ap.add_argument("--n", type=int, default=1000)
    a = ap.parse_args(argv)
    if a.cmd == "run":
        cmd_run(a.n)
    elif a.cmd == "posthoc":
        cmd_posthoc(a.n)
    elif a.cmd == "cards":
        cmd_cards()
    else:
        show()
    return 0


if __name__ == "__main__":
    sys.exit(main())
