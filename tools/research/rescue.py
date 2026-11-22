"""Zlarior eval rescue (day-litedge round 2, 2026-11-20). PAPER RESEARCH ONLY: reads stored trades, writes
research/lit/rescue.json, changes nothing live.

From TODAY's state, on the real LIT trade lists (tools/money/builder_levers.by_mix, $1.90 a micro + 1 tick a side) and a
+10-tick stress, both Zlarior evals on ONE Monte Carlo (tools/money/lit_two_evals: same 5-session-block paths, so a LIT
streak hits both):
  Z50  Builder 50K from its hole ($49,193: $1,025 room, $3,807 to go)       N25  Builder 25K #2 fresh ($25,000)
Variants (fixed before the run, design in research/lit/rescue_design_2026-11-20.md):
  today   live two_week room_f 0.4 to session 80
  rf03    room_f 0.3        rf02    room_f 0.2
  pause   live sizing, but the EVAL does not trade while the edge light (tools/edge_health: LIT's own last 40 sessions,
          R a week, GREEN above 1.16) is not GREEN; it resumes when GREEN. Funded accounts always trade.
Per variant: one eval each, no re-buy, 60 sessions -> pass / blow %, median sessions to pass; and the 6-month seat
(re-buy a fresh eval at $91.80 / $63 after a blow = option d, then funded with today's funded rules) -> $ a month to the
owner after fees, first payout, no payout in 6 months.

    python -X utf8 tools/research/rescue.py [--n 1000]
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools", "money"))
sys.path.insert(0, ROOT)
import logging  # noqa: E402
logging.disable(logging.ERROR)
import lit_two_evals as T  # noqa: E402

BL, U, SA, A4 = T.BL, T.U, T.SA, T.A4
OUT = os.path.join(ROOT, "research", "lit", "rescue.json")
GREEN_ABOVE, N_LIGHT = 1.16, 40              # research/lab/edge_health.json light.cuts (2021-25 cuts, 40 sessions)
VARS = {"today": {}, "rf03": {"room_f": 0.3}, "rf02": {"room_f": 0.2}, "pause": {"pause": True}}
SPANS = ("H1", "H2", "REF")


def mk_eval(acct, var, start=None):
    e = T.mk_eval(acct, {}, start=start)
    if var.get("room_f"):
        e.sub["two_week"] = dict(e.sub["two_week"], room_f=float(var["room_f"]))
    return e


def stress(BY, ticks=10):
    x = ticks * 0.25
    return [[dict(t, pts=t["pts"] - x, w1=min(t["w1"], t["pts"] - x)) for t in s] for s in BY]


def sess_r(ts):
    return sum(t["pts"] / t["risk"] for t in ts if t.get("strat", "LIT") == "LIT" and t["risk"])


def history(BY, S):
    """LIT's real last 40 sessions of R (size-free, costs in): the stored sessions up to Oct 16 + the twin since Oct 19."""
    tw = json.load(open(os.path.join(ROOT, "research", "lit", "litedge_study.json")))["cold_run"]["twin_since_oct19"]
    by_day = collections.defaultdict(float)
    for r in tw:
        by_day[r["day"]] += float(r["r"])
    d, days = dt.date(2026, 10, 19), []
    while d <= dt.date(2026, 11, 19):
        if d.weekday() < 5:
            days.append(d.isoformat())
        d += dt.timedelta(days=1)
    rec = [by_day.get(x, 0.0) for x in days]
    stored = [sess_r(BY[i]) for i, day in enumerate(S) if day <= "2026-10-16"]
    h = (stored + rec)[-N_LIGHT:]
    return h


def greens(seq, BY, h0):
    """Per session of the path: is the light GREEN at its start (from the sessions before it)?"""
    h = collections.deque(h0, maxlen=N_LIGHT)
    out = []
    for si in seq:
        out.append(sum(h) / (N_LIGHT / 5.0) > GREEN_ABOVE)
        h.append(sess_r(BY[si]))
    return out


def evals(BY, paths, var, h0, h=60):
    rows = []
    for seq in paths:
        ev = {"Z50": mk_eval("Z50", var, start=T.Z50_TODAY), "N25": mk_eval("N25", var)}
        g = greens(seq[:h], BY, h0) if var.get("pause") else None
        res = {k: ("open", h) for k in ev}
        live = set(ev)
        paused = 0
        for k, si in enumerate(seq[:h]):
            if g is not None and not g[k]:
                paused += 1
                continue
            for nm in list(live):
                r, _ = ev[nm].step(BY[si])
                if r:
                    res[nm] = ("pass" if r == "pass" else "fail", k + 1)
                    live.discard(nm)
            if not live:
                break
        res["_paused"] = paused
        rows.append(res)
    n = len(rows)

    def acc(nm):
        o = [r[nm] for r in rows]
        pas = [u for x, u in o if x == "pass"]
        return {"p10": round(100.0 * sum(1 for x, u in o if x == "pass" and u <= 10) / n, 1),
                "p20": round(100.0 * sum(1 for x, u in o if x == "pass" and u <= 20) / n, 1),
                "p60": round(100.0 * len(pas) / n, 1), "f20": round(100.0 * sum(1 for x, u in o if x == "fail" and u <= 20) / n, 1),
                "f60": round(100.0 * sum(1 for x, _ in o if x == "fail") / n, 1),
                "open60": round(100.0 * sum(1 for x, _ in o if x == "open") / n, 1),
                "pass_med": float(np.median(pas)) if pas else None}
    return {"Z50": acc("Z50"), "N25": acc("N25"),
            "both_dead60": round(100.0 * sum(1 for r in rows if r["Z50"][0] == "fail" and r["N25"][0] == "fail") / n, 1),
            "paused_sessions_avg": round(float(np.mean([r["_paused"] for r in rows])), 1)}


def seats(BY, paths, var, cal, h0):
    out = {"Z50": [], "N25": []}
    for seq in paths:
        zs = BL.Seat(lambda _=None: mk_eval("Z50", var), lambda: BL.GF("builder50k", U.UP50, BL.F50_LIT), T.P50,
                     [mk_eval("Z50", var, start=T.Z50_TODAY)])
        ns = BL.Seat(lambda _=None: mk_eval("N25", var), lambda: BL.GF("builder25k", U.UP25, {"LIT": ("fq", None)}), T.P25,
                     [mk_eval("N25", var)])
        g = greens(seq[:T.LEN], BY, h0) if var.get("pause") else None
        for k, si in enumerate(seq[:T.LEN]):
            ts = BY[si]
            te = [] if g is not None and not g[k] else ts
            zs.step(k, te, ts)
            ns.step(k, te, ts)
        out["Z50"].append(zs)
        out["N25"].append(ns)
    res = {nm: BL.seat_stats(v, cal) for nm, v in out.items()}
    tot = np.array([(a.owner - a.cost) + (b.owner - b.cost) for a, b in zip(out["Z50"], out["N25"])])
    res["both_net_m"] = round(float(tot.mean()) / T.MO)
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    a = ap.parse_args(argv)
    import payout_plan as PP
    cal = PP.calendar(T.LEN + 5, T.START)
    S = SA.data()["S"]
    BY0 = BL.by_mix(("LIT",))
    h0 = history(BY0, S)
    light0 = sum(h0) / (N_LIGHT / 5.0)
    print(f"light now: {light0:.2f} R a week over the last {len(h0)} sessions -> {'GREEN' if light0 > GREEN_ABOVE else 'not green'}")
    res = {"date": "2026-11-20", "n": a.n, "z50_today": T.Z50_TODAY, "light_now_r_week": round(light0, 2), "rows": {}}
    for cost, BY in (("model", BY0), ("stress10", stress(BY0))):
        res["rows"][cost] = {}
        for sp in SPANS:
            PE = U.mc_paths(S, sp, a.n, length=60, seed=A4.SEED_EVAL)
            PF = U.mc_paths(S, sp, a.n, length=T.LEN, seed=A4.SEED_LIFE)
            res["rows"][cost][sp] = {}
            for nm, var in VARS.items():
                t1 = time.time()
                ev = evals(BY, PE, var, h0)
                st = seats(BY, PF, var, cal, h0)
                res["rows"][cost][sp][nm] = {"evals": ev, "seats": st}
                z, n_ = ev["Z50"], ev["N25"]
                print(f"{cost:8s} {sp:3s} {nm:6s} 50K pass {z['p60']}% blow {z['f60']}% med {z['pass_med']} | 25K pass {n_['p60']}% "
                      f"blow {n_['f60']}% med {n_['pass_med']} | paused {ev['paused_sessions_avg']} | seat $/mo 50K {st['Z50']['net_m']} "
                      f"25K {st['N25']['net_m']} both {st['both_net_m']} 1st pay {st['Z50']['first_pay_med']}/{st['N25']['first_pay_med']} "
                      f"({time.time() - t1:.0f}s)", flush=True)
            json.dump(res, open(OUT, "w"), indent=1, default=float)
    print("wrote", os.path.relpath(OUT, ROOT))


if __name__ == "__main__":
    main()
