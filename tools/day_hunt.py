"""Day hunt 2026-11-23 (research/writeups/day-hunt-2026-11-23.md). RESEARCH ONLY, paper, never touches live_model*.json.

Pre-registered: research/lit/day_hunt_design_2026-11-23.md (one fixed version, written before any result).

  ESD  = ES-confirmed displacement: a LIT NQ setup that passes every live filter except displacement, with its biggest body in
         [0.6, 0.8) NQ-ATR, is kept only if ES1! 5m printed a body >= 0.8 ES-ATR(14) in the setup direction on a closed 5m bar
         from NQ's sweep-extreme bar to NQ's trigger bar. Everything else = live LIT.
  atlas_payout = odds that the ATLAS funded 25K reaches MFFU's minimum payout from today's profit at its current size
         (day-block bootstrap of ATLAS's recent backtest days + the consistency rule).

    python -X utf8 tools/day_hunt.py esd       # -> research/lit/day_hunt.json
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from tools import lit_more_money as MM  # noqa: E402
from tools import lit_edge as E  # noqa: E402
from tools import lit_final as F  # noqa: E402

OUT = os.path.join(ROOT, "research", "lit", "day_hunt.json")
LO, HI, ES_BODY = 0.6, 0.8, 0.8


def es_atr():
    X = MM.es_bars()
    if "atr" not in X:
        h, l, c = X["h"], X["l"], X["c"]
        pc = np.r_[c[0], c[:-1]]
        tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
        a = np.convolve(tr, np.ones(14) / 14, mode="full")[:len(tr)]
        a[:13] = np.nan
        X["atr"] = a
    return X["atr"]


def es_confirms(z, M):
    """True / False / None (no ES data) for the ESD rule."""
    X = MM.es_bars()
    atr = es_atr()
    te, ti = int(M.t[z["ext_i"]]), int(M.t[z["i"]])
    if te < X["t"][0] + 14 * 300 or ti > X["t"][-1]:
        return None
    a, b = MM.es_window(te, ti + 1)              # ES bars opening from the extreme bar to the trigger bar (both closed)
    if b <= a:
        return None
    body = (X["c"][a:b] - X["o"][a:b]) * z["dir"]
    return bool(np.nanmax(body / atr[a:b]) >= ES_BODY)


def esd_trades():
    M, C = MM.cands()
    sk, cnt = [], {"band": 0, "es_yes": 0, "es_no": 0, "es_none": 0}
    for z in C:
        if LO <= z["disp"] < HI:
            cnt["band"] += 1
            ok = es_confirms(z, M)
            cnt["es_yes" if ok else "es_none" if ok is None else "es_no"] += 1
            if not ok:
                sk.append([z["day"], int(z["i"]), int(z["dir"])])
    T = F.run({**MM.LIVE, "disp": LO, "skip_keys": sk})
    return T, cnt


def esd():
    E.ctx()
    base, U0, L0 = E.evaluate({}, fund=True)
    bs = E.short(base)
    print(E.line("base", bs), flush=True)
    T, cnt = esd_trades()
    U = MM.walk({}, T=T)
    s = MM.score("esd", U, base, L0, {"cands": cnt})
    b26 = {(u["day"], u["entry_t"]) for u in U0}
    s["new_trades"] = [{"day": u["day"], "dir": u["dir"], "exit": u["exit"], "R": round(u["pts"] / u["risk"], 2)}
                       for u in U if (u["day"], u["entry_t"]) not in b26]
    json.dump({"base": bs, "esd": s, "design": "research/lit/day_hunt_design_2026-11-23.md"}, open(OUT, "w"), indent=1,
              default=float)
    print(json.dumps(s["new_trades"], indent=0)[:3000])
    return s




# ================================================================================================ ATLAS payout odds
def atlas_payout(n=10000, seed=23, profit0=401.0, days0=(-113.0, 514.0)):
    """Odds that the ATLAS funded 25K is payout-ELIGIBLE (MFFU: balance >= start + $1,100 buffer + $250 minimum = +$1,350,
    2+ traded days in the cycle, best day <= 50% of the cycle's profit) by Fri 11-27 (5 sessions) and Thu 12-04 (9: Thanksgiving
    11-26 counted, 12-04 is Friday -> 10) at its CURRENT live size (tools/atlas_more PGF = the live funded preset UP25 +
    the $100 stuck stop), from today's +$401, room $1,000. Day-block bootstrap of ATLAS's recent sessions."""
    import datetime as _dt
    sys.path.insert(0, os.path.join(ROOT, "tools", "money"))
    from tools import atlas_more as AM
    from tools import atlas_revive as RV
    S = AM.sessions()
    T, _ = AM.idea_T(AM.IDEAS["today"])
    BY = dict(zip(S, RV.by_session(T, S)))
    # fresh 5 weeks (engine/second.run replayed on the new bars, Oct 19 - Nov 19)
    U = AM.fresh_units()
    TF = AM.to_T(RV.one_pos(sorted([u for m in AM.MEMBERS for u in U.get(m, [])], key=lambda u: u["entry_t"])))
    fs = json.load(open(AM.OUT_FRESH, encoding="utf-8"))["sessions"]
    for d in fs:
        BY[d] = [{**t, "strat": "ATLAS"} for t in TF if t["day"] == d]
    for d in BY:
        BY[d] = [{**t, "strat": "ATLAS"} for t in BY[d]]
    PGF = AM._pgf()
    pools = {"recent Jul 1 - Nov 19": [d for d in sorted(BY) if "2026-07-01" <= d <= "2026-11-19"],
             "fresh Oct 19 - Nov 19 only": [d for d in sorted(BY) if "2026-10-19" <= d <= "2026-11-19"],
             "all 2026": [d for d in sorted(BY) if "2026-01-01" <= d <= "2026-11-19"]}
    horizons = {"Fri 11-27": 5, "Fri 12-04": 10}
    out = {"profit0": profit0, "days0": list(days0), "n": n, "pools": {}}
    rng = np.random.default_rng(seed)
    for nm, pool in pools.items():
        ntr = sum(len(BY[d]) for d in pool)
        res = {"sessions": len(pool), "trades": ntr, "tpw": round(ntr / (len(pool) / 5), 2)}
        H = max(horizons.values())
        hit_at, lost, pnl_end, reach_at, usd_tr = [], 0, [], [], []
        for _ in range(n):
            f = PGF({})
            f.bal = f.peak = profit0
            f.trade_pnl = profit0
            f.floor = profit0 - 1000.0
            f.cyc = list(days0)
            f.first_trade = "2026-11-18"
            f.elig_from = "2026-11-20"
            f.k = 0
            seq = rng.choice(len(pool), size=H)
            hit = None
            reach = None
            for k, ix in enumerate(seq):
                ev, _x = f.step(BY[pool[ix]])
                if ev == "lost" or f.dead:
                    lost += 1
                    break
                tr = f._fast_track("2026-12-31")
                if reach is None and f.bal >= 1350.0:
                    reach = k + 1
                if hit is None and tr["status"] in ("eligible", "ready"):
                    hit = k + 1
                    break
            hit_at.append(hit)
            reach_at.append(reach)
            usd_tr.extend(abs(v) for v in f.days.values())
            pnl_end.append(f.bal)
        for hz, h in horizons.items():
            res[hz] = round(100.0 * sum(1 for x in hit_at if x and x <= h) / n, 1)
            res[hz + " $ only (no best-day rule)"] = round(100.0 * sum(1 for x in reach_at if x and x <= h) / n, 1)
        res["median_abs_day_usd"] = round(float(np.median(usd_tr)), 0) if usd_tr else 0
        res["lost_or_stuck_10"] = round(100.0 * lost / n, 1)
        out["pools"][nm] = res
        print(nm, res, flush=True)
    # what the cap means: the biggest one-day win the live size allows
    out["note"] = ("best-day rule: at +$1,350 the best day must be <= $675; a one-trade +$949 day would need the cycle at "
                   "+$1,898 instead. P['buffer'], P['pay_min'] from tools/uprisk.fplan('builder25k').")
    from tools import uprisk as UU
    P, A_ = UU.fplan("builder25k")
    out["plan"] = {k: P.get(k) for k in ("buffer", "pay_min", "pay_max", "cons", "cycle_days")} | {"mll": A_["mll"], "dll": A_["dll"]}
    print(out["plan"])
    p = os.path.join(ROOT, "research", "second", "atlas_payout_2026-11-23.json")
    json.dump(out, open(p, "w"), indent=1)
    return out


if __name__ == "__main__":
    {"esd": esd, "payout": atlas_payout}[sys.argv[1] if len(sys.argv) > 1 else "esd"]()
