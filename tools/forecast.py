"""EVAL PASS FORECASTER (research/batch5/DESIGN.md part B). PAPER RESEARCH ONLY: reads balances, changes nothing.

    python -X utf8 tools/forecast.py            # -> research/forecast/forecast.json (+ a table); nightly-safe (~1-2 min, numba used)
    python -X utf8 tools/forecast.py --offline  # use the last saved balances (research/forecast/forecast.json "state") instead of the board

forecast.json shape (read by the dashboard / Telegram EOD):
  {"made", "data_to", "n_paths", "markets": {"2026-like": "...", "2021-25-like": "..."},
   "accounts": {"<key>": {"name", "plan", "stage": "eval"|"funded", "strategies": [...], "state": {balance, floor, room, profit,
                 sessions_done},
                 "<market>": {"pass_pct", "fail_pct", "open_pct", "pass_med_sessions", "first_payout_med_sessions",
                              "first_payout_60_pct", "lost_pct" (funded)}}},
   "words": {"<key>": "one plain line"}}
Engine: research/plans/rank.py (the live two_week eval sizing + ATLAS's lane + the MFFU funded payout rules), started from
TODAY's state (tools/board.gather), 1,000 paths of 5-session blocks per market.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "research", "plans"))
OUT = os.path.join(ROOT, "research", "forecast", "forecast.json")
MARKETS = {"2026-like": ("Y26", ("2026-01-01", "2026-10-16")), "2021-25-like": ("REF", None)}
ACCTS = {   # board key -> plan, start balance, strategy mix, eval start (sessions done are counted from it)
    "zlarior": {"plan": "mffu_builder_50k", "start": 50000.0, "mix": ("LIT",), "eval_start": "2026-10-19"},
    "fresh25": {"plan": "mffu_builder_25k", "start": 25000.0, "mix": ("LIT",), "eval_start": "2026-11-18"},
    "rapid1": {"plan": "mffu_rapid_eod_25k", "start": 25000.0, "mix": ("LIT", "ATLAS"), "eval_start": "2026-11-20"},
    "atlas": {"plan": "mffu_builder_25k", "start": 25000.0, "mix": ("ATLAS",), "funded": True},
}
HORIZON = 126


def board_state(offline=False):
    if not offline:
        try:
            from tools import board as B
            rows = B.gather().get("accounts") or []
            return {r["key"]: {"balance": r.get("balance"), "floor": r.get("floor"), "room": r.get("room"), "stage": r.get("stage"),
                               "name": r.get("name"), "plan_label": r.get("plan"), "src": r.get("src")} for r in rows}, "board (PC live)"
        except Exception as ex:  # noqa: BLE001
            print(f"board not reachable ({ex.__class__.__name__}); using the last saved state")
    old = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    return {k: v.get("state") for k, v in (old.get("accounts") or {}).items()}, "last saved forecast.json"


def sessions_since(day, S=None):
    """Weekdays from the eval start to today (the engine's session list ends at its last bar, so it cannot count them)."""
    return int(np.busday_count(day, dt.date.today().isoformat()))


def run(n=1000, offline=False, say=print):
    import rank as R
    U, RL, AR, SOA = R.U, R.RL, R.AR, R.SOA
    U.SPAN["Y26"] = ("2026-01-01", "2026-10-16")
    R.A4.apply_costs()                               # LIT's trades at engine/costs.py exit costs, as rank.py
    AR.rapid_patch(AR.T_costs())                     # ATLAS at engine/costs.py (12 entry / 10 exit ticks), as rank.py
    S = SOA.data()["S"]
    state, src = board_state(offline)
    out = {"made": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "data_to": str(S[-1]), "n_paths": n,
           "state_source": src, "markets": {"2026-like": "Jan-Oct 2026 sessions", "2021-25-like": "Nov 2021 - Dec 2025 sessions"},
           "engine": "research/plans/rank.py (two_week eval sizing, ATLAS lane at 10 ticks a side, MFFU funded payout rules)",
           "accounts": {}, "words": {}}
    PATHS = {m: U.mc_paths(S, key, n, length=HORIZON + 40, seed=7) for m, (key, _) in MARKETS.items()}
    for key, A in ACCTS.items():
        st = (state or {}).get(key)
        if not st or st.get("balance") is None:
            say(f"{key}: no live balance, skipped")
            continue
        sp = R.spec(A["plan"])
        BYe, BYf = RL.mix_by(A["mix"]), RL.mix_by(A["mix"], news=A["plan"].startswith("mffu_rapid"))
        profit = float(st["balance"]) - A["start"]
        floor_rel = float(st["floor"]) - A["start"] if st.get("floor") is not None else -sp["E"]["mll"]
        done = sessions_since(A["eval_start"], [str(d) for d in S]) if A.get("eval_start") else 0
        row = {"name": st.get("name"), "plan": A["plan"], "stage": "funded" if A.get("funded") else "eval", "strategies": list(A["mix"]),
               "state": {"balance": st["balance"], "floor": st.get("floor"), "room": st.get("room"), "profit": round(profit, 2),
                         "sessions_done": done}}
        for m, P in PATHS.items():
            res = []
            for seq in P:
                if A.get("funded"):
                    f = sp["fund"]()
                    f.bal, f.floor, f.peak, f.cyc_start = profit, floor_rel, max(profit, 0.0), 0.0
                    first, lost = None, False
                    for k, si in enumerate(seq[:HORIZON]):
                        ev, x, _ = f.step(BYf[si])
                        if ev in ("paid", "grad") and first is None:
                            first = k + 1; break
                        if ev == "lost":
                            lost = True; break
                    res.append(("funded", first, lost))
                    continue
                e = sp["ev"]()
                e.bal, e.floor, e.peak, e.s, e.dtr = profit, floor_rel, max(profit, floor_rel + sp["E"]["mll"]), done, min(done, 3)
                out_, used, first = "open", None, None
                for k, si in enumerate(seq[:HORIZON]):
                    r_, _ = e.step(BYe[si])
                    if r_ == "pass":
                        out_, used = "pass", k + 1; break
                    if r_ in ("fail", "stuck"):
                        out_, used = "fail", k + 1; break
                if out_ == "pass":
                    f, wait = None, R.GAP
                    for k2, si in enumerate(seq[used:used + HORIZON]):
                        if f is None:
                            wait -= 1
                            if wait <= 0:
                                f = sp["fund"]()
                            continue
                        ev, x, _ = f.step(BYf[si])
                        if ev in ("paid", "grad"):
                            first = used + k2 + 1; break
                        if ev == "lost":
                            break
                res.append((out_, used, first))
            if A.get("funded"):
                fp = [r[1] for r in res if r[1]]
                row[m] = {"first_payout_pct": round(100 * len(fp) / len(res), 1), "first_payout_med_sessions": float(np.median(fp)) if fp else None,
                          "first_payout_60_pct": round(100 * sum(1 for x in fp if x <= 60) / len(res), 1),
                          "lost_pct": round(100 * sum(1 for r in res if r[2]) / len(res), 1)}
            else:
                ps = [r[1] for r in res if r[0] == "pass"]
                fp = [r[2] for r in res if r[2]]
                row[m] = {"pass_pct": round(100 * len(ps) / len(res), 1), "fail_pct": round(100 * sum(1 for r in res if r[0] == "fail") / len(res), 1),
                          "open_pct": round(100 * sum(1 for r in res if r[0] == "open") / len(res), 1),
                          "pass_med_sessions": float(np.median(ps)) if ps else None,
                          "first_payout_med_sessions": float(np.median(fp)) if fp else None,
                          "first_payout_60_pct": round(100 * sum(1 for x in fp if x <= 60) / len(res), 1)}
        out["accounts"][key] = row
        a, b = row["2026-like"], row["2021-25-like"]
        if A.get("funded"):
            out["words"][key] = (f"{row['name']}: first payout {a['first_payout_pct']}% within 6 months in a 2026-like market "
                                 f"(median {a['first_payout_med_sessions']} sessions), {b['first_payout_pct']}% in a 2021-25-like one")
        else:
            out["words"][key] = (f"{row['name']}: pass {a['pass_pct']}% / fail {a['fail_pct']}% in a 2026-like market (median "
                                 f"{a['pass_med_sessions']} sessions), {b['pass_pct']}% / {b['fail_pct']}% in a 2021-25-like one")
        say(out["words"][key])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1, default=float)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args(argv)
    run(a.n, a.offline)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
