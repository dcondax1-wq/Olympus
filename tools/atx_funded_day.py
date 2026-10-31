"""ATLAS funded day-count rule (2026-10-31, research/writeups/atlas-funded-one-a-day-2026-10-31.md).

Question: does the FUNDED ATLAS 25K pay the owner more if it takes at most ONE trade a day (the day's first ATLAS signal)
instead of two? The eval is unchanged (today's ATLAS), so only the slot $ (eval -> funded -> MFFU payouts -> a new $63 eval,
tools/atx_edge.slot) can move. Trade-count rules were tested on the EVAL path before (atlas-confluences.md "Trades a day":
max 1 / max 3 / 2nd only after a win or a loss, 0 kept); never on the funded account's payouts.

Pick on 2026 H1 only (max 1 vs max 3 vs today's max 2), frozen, checked on 2026 H2 and 2021-25. Controls: keep ONE RANDOM
signal of the day instead of the first (4 seeds), so "1 a day" has to beat "any 1 a day".

    python -X utf8 tools/atx_funded_day.py run [n]     # slot $ for every variant -> research/second/atx_funded_day.json
    python -X utf8 tools/atx_funded_day.py save        # runs atxd_* in the run library (real-session slot trades)
Paper research only: nothing in engine/, second_model.json or live_model*.json is touched.
"""
from __future__ import annotations

import json
import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import atx_edge as X  # noqa: E402

OUT = os.path.join(X.OUT, "atx_funded_day.json")


def funded_play(max_day=2, pick=None):
    """A funded-stage play_day: at most max_day trades a day; pick="random:<seed>" keeps one random signal of the day."""
    V2, A, M, EAB = X.libs()

    def play(L, day, bal, floor, session, rule, pre=False, _md=2, lost=None, litcfg=None, dll=None, reserve=False, extra=None):
        L = list(L)
        if pick and L:
            seed = int(pick.split(":")[1])
            rng = random.Random(f"{seed}:{day}")
            L = [L[rng.randrange(len(L))]]
        return M.play_day(L, day, bal, floor, session, rule, pre, max_day, lost, litcfg, dll=dll, reserve=reserve, extra=extra)
    return play


VARIANTS = [("today", dict()), ("max1", dict(max_day=1)), ("max3", dict(max_day=3)), ("max4", dict(max_day=4))] + \
           [(f"rand1_s{s}", dict(max_day=1, pick=f"random:{s}")) for s in (1, 2, 3, 4)]


SEEDS = (23, 5, 11, 41)          # 23 = atx_edge's seed (the pick); the others = path-resampling robustness


def one(name, kw, n, seed=23):
    X.PLAY_FUNDED[0] = funded_play(**kw) if kw else None
    try:
        sl = X.slot(X.today(), n=n, seed=seed)
        sl["2021-25"] = X.slot_ref(sl)
        rs, T = X.real_slot(X.today())
    finally:
        X.PLAY_FUNDED[0] = None
    ft = [t for t in T if t["stage"] == "funded"]
    return {"slot": sl, "real": rs, "funded_trades": stats(ft), "_T": T}


def stats(T):
    """PF, R per $ risked, $ net, max drawdown, trades by span of the funded trades on the real-session path."""
    out = {}
    for s, (a, b) in {"H1": ("2026-01-01", "2026-07-01"), "H2": ("2026-07-01", "2027-01-01"), "2021-25": ("2021-01-01", "2026-01-01")}.items():
        x = [t for t in T if a <= t["day"] < b]
        w = sum(t["pnl"] for t in x if t["pnl"] > 0)
        l = -sum(t["pnl"] for t in x if t["pnl"] < 0)
        ru = sum(t.get("risk_usd") or 0 for t in x)
        eq = pk = dd = 0.0
        for t in sorted(x, key=lambda t: t["entry_t"]):
            eq += t["pnl"]
            pk = max(pk, eq)
            dd = min(dd, eq - pk)
        days = sorted({t["day"] for t in x})
        out[s] = {"n": len(x), "net": round(sum(t["pnl"] for t in x)), "pf": round(w / l, 2) if l else None,
                  "r_per_risk": round(sum(t["pnl"] for t in x) / ru, 3) if ru else None, "dd": round(dd),
                  "days": len(days), "two_trade_days": sum(1 for d in days if sum(1 for t in x if t["day"] == d) >= 2)}
    return out


def cmd_run(n=300):
    res = {}
    for name, kw in VARIANTS:
        t0 = time.time()
        o = one(name, kw, n)
        o.pop("_T")
        if not name.startswith("rand"):
            o["seeds"] = {}
            for sd in SEEDS[1:]:
                q = one(name, kw, n, seed=sd)
                o["seeds"][sd] = {s: q["slot"][s]["pm"] for s in ("H1", "H2", "2021-25")}
        res[name] = o
        print(f"{name:10s} " + " | ".join(f"{s} slot ${o['slot'][s]['pm']:+,}/mo lose {o['slot'][s]['lose']}%" for s in ("H1", "H2", "2021-25"))
              + (f"  seeds {o['seeds']}" if o.get("seeds") else "") + f"  ({time.time() - t0:.0f}s)", flush=True)
        json.dump({"n": n, "res": res}, open(OUT, "w", encoding="utf-8"), indent=1)
    return res


def cmd_save():
    from tools import runlib as rl
    V2, A, M, EAB = X.libs()
    sess = sorted(set(M.units()["sessions"]))
    R = json.load(open(OUT, encoding="utf-8"))["res"]
    for name, title, st in (("max1", "ATLAS funded 25K: 1 trade a day (eval unchanged)", "rejected"),
                            ("max3", "ATLAS funded 25K: up to 3 trades a day (the H1 pick; eval unchanged)", "rejected"),
                            ("today", "ATLAS slot today (2 a day funded), reference for atxd_*", "info")):
        kw = dict(VARIANTS)[name]
        o = one(name, kw, 20)
        T = X._runlib_trades(o["_T"])
        r = R[name]
        vt = "; ".join(f"{s}: slot ${r['slot'][s]['pm']:,}/mo (today ${R['today']['slot'][s]['pm']:,}), lose {r['slot'][s]['lose']}%, "
                       f"funded PF {r['funded_trades'][s]['pf']}, R/$ {r['funded_trades'][s]['r_per_risk']}" for s in ("H1", "H2", "2021-25"))
        rl.save(f"atxd_{name}", title, "risk", "ATLAS 2026-10-31: does the funded 25K pay more with at most one trade a day?",
                params={"funded_max_day": kw.get("max_day", 2), "eval": "today"},
                sizing={"eval": "engine/account_b.qty need", "funded": "engine/sizing.funded_qty 25K preset (atx_edge.funded_q)"},
                trades=T, scored=rl.score(T, sess), status=st, verdict=vt,
                notes="tools/atx_funded_day.py (slot = block-bootstrap paths x 126 sessions, $63 evals, 80% payouts; trades = real-session path)",
                writeup="atlas-funded-one-a-day-2026-10-31", tags=["atlas", "account_b", "25k", "funded", "slot", "trades_a_day"])
        print("saved", name, flush=True)


if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else "run"
    if c == "run":
        cmd_run(int(sys.argv[2]) if len(sys.argv) > 2 else 300)
    elif c == "save":
        cmd_save()
