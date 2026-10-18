"""Execution economics study (run prefix exec_, 2026-10-17): micros vs minis, slippage sensitivity, route break-even and the
cost of an order delay. Post-hoc on the locked strategy's exact replay (tools/runlib); two engine replays (retest entry,
2-tick slippage). Writes research/runs/exec_*.json and prints the tables used in research/writeups/execution-economics.md.

  python tools/research_exec.py            # post-hoc parts + whatever replays are cached
"""
from __future__ import annotations

import collections
import copy
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import runlib as rl  # noqa: E402

TICK, PV = 0.25, 2.0                       # NQ tick, $ per point per micro
MINI_RT, MICRO_RT = 4.50, 1.50             # engine round-turn commission assumptions (engine/instruments.py)
OUT = os.path.join(os.environ.get("EXEC_SCRATCH", "/tmp"), "exec_tables.json")
YEARS = ("2021", "2022", "2023", "2024", "2025", "2026")


def comm_booked(q):
    """Engine booking: every 10 micros become one NQ mini."""
    return (q // 10) * MINI_RT + (q % 10) * MICRO_RT


def comm_micro(q, rt=MICRO_RT):
    return q * rt


def comm_mini_only(q):
    """Minis only: micros below 10 cannot be traded (None = no trade)."""
    return None if q < 10 else (q // 10) * MINI_RT


def span(t):
    return "2026" if t["day"] >= "2026" else "2021-25"


def months(trades, key="2021-25"):
    a, z = ("2026-01-01", "2026-12-31") if key == "2026" else ("2021-01-01", "2025-12-31")
    n_sessions = None
    return [t for t in trades if a <= t["day"] <= z]


def retrade(T, fn):
    """Copy of the sized trades with pnl adjusted by fn(t) -> new pnl; r follows."""
    out = []
    for t in T:
        x = dict(t)
        x["pnl"] = round(fn(t), 2)
        x["r"] = round(x["pnl"] / t["risk_usd"], 3) if t["risk_usd"] else t["r"]
        out.append(x)
    return out


def headline(S):
    o = {}
    for k in ("2026", "2021-25", "all"):
        s = S["spans"][k]
        o[k] = {x: s.get(x) for x in ("n", "tpw", "wk2", "pf", "net", "per_month", "dd", "p10", "f10", "p15", "f15", "b2b")}
    return o


def main():
    raw = rl.replay()
    T = rl.size(raw)
    S = rl.score(T, raw)
    base = headline(S)
    tables = {"baseline": base}
    print("baseline", json.dumps(base))

    # ---------------------------------------------------------------- 0. reconstruct gross / commission per trade (check)
    bad = 0
    for t in raw["trades"]:
        gross = (t["exit_price"] - t["entry"]) * t["dir"] * t["qty"] * PV
        if abs(gross - comm_booked(t["qty"]) - t["pnl"]) > 0.02:
            bad += 1
    print("pnl reconstruction mismatches (raw):", bad, "of", len(raw["trades"]))
    tables["recon_mismatch"] = bad

    # ---------------------------------------------------------------- 1. micros vs minis
    # a) commission under the booking rules, live sizing (sized qty), per year and per period
    rows = collections.defaultdict(lambda: collections.defaultdict(float))
    lost_mini_only = collections.Counter()
    for t in T:
        q = t["qty"]; y = t["day"][:4]
        rows["booked"][y] += comm_booked(q)
        rows["micro_only"][y] += comm_micro(q)
        rows["micro_only_1.00"][y] += comm_micro(q, 1.00)
        rows["micro_only_2.00"][y] += comm_micro(q, 2.00)
        c = comm_mini_only(q)
        if c is None:
            lost_mini_only[y] += 1
        else:
            rows["mini_only"][y] += c
        rows["linear_rl"][y] += t["mult"] * comm_booked(int(round(q / t["mult"]))) if t["mult"] else comm_booked(q)
    comm_tbl = {k: {y: round(v.get(y, 0.0)) for y in YEARS} for k, v in rows.items()}
    for k in comm_tbl:
        comm_tbl[k]["2021-25"] = sum(comm_tbl[k][y] for y in YEARS[:-1]); comm_tbl[k]["all"] = comm_tbl[k]["2021-25"] + comm_tbl[k]["2026"]
    tables["commission"] = comm_tbl
    tables["mini_only_lost_trades"] = {y: lost_mini_only.get(y, 0) for y in YEARS}
    print("commission by booking rule:", json.dumps(comm_tbl, indent=0))
    print("mini-only trades lost:", dict(lost_mini_only), "of", len(T))

    # qty distribution of the sized trades
    qs = collections.Counter(t["qty"] for t in T)
    tables["qty_hist"] = {"1": qs[1], "2-4": sum(qs[q] for q in range(2, 5)), "5-9": sum(qs[q] for q in range(5, 10)),
                          "10-19": sum(qs[q] for q in range(10, 20)), "20-39": sum(qs[q] for q in range(20, 40)), "40": qs[40]}
    print("sized qty histogram:", tables["qty_hist"])

    # b) rounding: planned risk vs the risk the integer micros carry
    from engine.sizing import is_late
    plan = []
    for t in T:
        rp = t["risk_pts"]
        raw_q = int(round(t["qty"] / t["mult"])) if t["mult"] else t["qty"]
        planned_raw = 800.0 * min(1.0, 20.0 / rp) * (0.5 if t.get("regime") == "trending" else 1.0)   # engine, before rounding
        planned_sized = planned_raw * (0.25 if t["half"] else 1.0) * (0.5 if is_late(t) else 1.0)      # live multipliers
        actual = t["qty"] * rp * PV
        plan.append((t, planned_raw, raw_q * rp * PV, planned_sized, actual))
    util_raw = np.array([a / p for _, p, a, _, _ in plan]); util_sized = np.array([a / p for _, _, _, p, a in plan])
    # $ left on the table by rounding down (fractional contracts, gross only): pnl scales with qty
    left = collections.defaultdict(float)
    for t, p_raw, a_raw, p_s, a_s in plan:
        if a_s > 0:
            gross = t["pnl"] + comm_booked(t["qty"])
            left[t["day"][:4]] += gross * (p_s / a_s - 1.0)
    tables["rounding"] = {"util_raw_mean": round(float(util_raw.mean()), 3), "util_raw_p10": round(float(np.percentile(util_raw, 10)), 3),
                          "util_sized_mean": round(float(util_sized.mean()), 3), "util_sized_min": round(float(util_sized.min()), 3),
                          "fractional_gross_gain": {y: round(left.get(y, 0.0)) for y in YEARS}}
    print("rounding:", tables["rounding"])

    # ---------------------------------------------------------------- 2. slippage 0 / 1 / 2 ticks (post-hoc, exact in $ per tick)
    def slip_sides(t):
        return 1 + (0 if t["exit"] == "TARGET" else 1)
    slip_cost_1 = {t["entry_t"]: slip_sides(t) * TICK * PV * t["qty"] for t in T}
    T0 = retrade(T, lambda t: t["pnl"] + slip_cost_1[t["entry_t"]])
    T2 = retrade(T, lambda t: t["pnl"] - slip_cost_1[t["entry_t"]])
    S0, S2 = rl.score(T0, raw), rl.score(T2, raw)
    tables["slip"] = {"0": headline(S0), "1": base, "2": headline(S2),
                      "per_tick_$": {y: round(sum(v for k, v in slip_cost_1.items() if any(t["entry_t"] == k and t["day"][:4] == y for t in T))) for y in YEARS}}
    by_y = collections.defaultdict(float)
    for t in T:
        by_y[t["day"][:4]] += slip_cost_1[t["entry_t"]]
    tables["slip"]["per_tick_$"] = {y: round(by_y.get(y, 0.0)) for y in YEARS}
    tables["slip"]["sides"] = collections.Counter(slip_sides(t) for t in T)
    print("slippage:", json.dumps({k: tables["slip"][k] for k in ("per_tick_$", "sides")}))
    print(" 0 ticks:", json.dumps(headline(S0))); print(" 2 ticks:", json.dumps(headline(S2)))
    rl.save("exec_slip0", "No slippage (0 ticks) on the locked strategy", "other",
            "How much of the result is the 1-tick slippage assumption?", params={"slippage_ticks": 0}, sizing="post-hoc exact: +1 tick per slipped side",
            trades=T0, scored=S0, status="info", verdict="Each tick of slippage is worth about $0.50 per micro per side; see the write-up.",
            notes="Post-hoc: adds back 1 tick x $2 x micros on the entry and on every non-TARGET exit. Entries/exits themselves unchanged.")
    rl.save("exec_slip2_posthoc", "2 ticks of slippage (post-hoc)", "other",
            "What if fills are 2 ticks worse than the mid on every market order?", params={"slippage_ticks": 2}, sizing="post-hoc exact in $",
            trades=T2, scored=S2, status="info", verdict="Pessimistic fills cost the same again as today's slippage assumption.",
            notes="Post-hoc: subtracts one more tick per slipped side. The replay exec_slip2_replay checks it inside the engine.")

    # ---------------------------------------------------------------- 1c. micro-only and mini-only booking as runs
    Tm = retrade(T, lambda t: t["pnl"] + comm_booked(t["qty"]) - comm_micro(t["qty"]))
    Sm = rl.score(Tm, raw)
    tables["micro_only"] = headline(Sm)
    rl.save("exec_micro_only", "Book every contract as a micro (no NQ minis)", "other",
            "What does the mini booking of 10+ micros save?", params={"contract": "micro"}, sizing="live; commission $1.50 per micro round turn",
            trades=Tm, scored=Sm, status="info", verdict="Minis save money only on the few 10+ micro trades; see the write-up.",
            notes="Post-hoc: commission = micros x $1.50 instead of minis x $4.50 + remainder x $1.50.")
    Tmini = [t for t in T if t["qty"] >= 10]
    Tmini = retrade(Tmini, lambda t: (t["pnl"] + comm_booked(t["qty"])) * ((t["qty"] // 10) * 10) / t["qty"] - (t["qty"] // 10) * MINI_RT)
    for t in Tmini:
        t["qty"] = (t["qty"] // 10) * 10
    Smini = rl.score(Tmini, raw)
    tables["mini_only"] = headline(Smini)
    rl.save("exec_mini_only", "Minis only (skip anything under 10 micros)", "other",
            "Could the account trade NQ minis only?", params={"contract": "mini"}, sizing="live, then rounded down to whole minis; < 1 mini = no trade",
            trades=Tmini, scored=Smini, status="rejected", verdict="Loses most trades and the 2-a-week rule.",
            notes="Post-hoc: keeps the trades with 10+ micros, rounds the quantity down to whole minis.")
    print("micro-only:", json.dumps(tables["micro_only"])); print("mini-only:", json.dumps(tables["mini_only"]))

    # ---------------------------------------------------------------- 4. route break-even: $ per month by period and months covered
    def monthly(trades, a, z):
        m = collections.defaultdict(float)
        for t in trades:
            if a <= t["day"] <= z:
                m[t["day"][:7]] += t["pnl"]
        return m
    months_all = sorted({d[:7] for d in raw["sessions"]})
    be = {}
    for key, a, z in (("2026", "2026-01-01", "2026-12-31"), ("2021-25", "2021-01-01", "2025-12-31")):
        mm = monthly(T, a, z)
        ms = [m for m in months_all if a[:7] <= m <= z[:7]]
        vals = np.array([mm.get(m, 0.0) for m in ms])
        be[key] = {"months": len(ms), "mean": round(float(vals.mean())), "median": round(float(np.median(vals))),
                   "pct_months_over_50": round(100 * float((vals > 50).mean()), 1), "pct_months_over_75": round(100 * float((vals > 75).mean()), 1),
                   "pct_months_negative": round(100 * float((vals < 0).mean()), 1),
                   "cost_share": {name: round(100 * 12 * c / max(1e-9, float(vals.sum()) * 12 / len(ms)), 1)
                                  for name, c in (("bridge_50", 50), ("vps_20", 20), ("bridge_vps_70", 70), ("ninjatrader_0", 0))},
                   "net_after": {name: round(float(vals.mean()) - c) for name, c in (("bridge_50", 50), ("vps_20", 20), ("bridge_vps_70", 70))}}
    tables["breakeven"] = be
    print("break-even:", json.dumps(be))

    # ---------------------------------------------------------------- 5. order delay (2026, 1-minute bars)
    m1 = {}
    path = os.path.join(ROOT, "data", "NQ_1m.csv")
    with open(path, encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            p = line.split(",")
            m1[int(p[0])] = (float(p[1]), float(p[2]), float(p[3]), float(p[4]))
    keys = sorted(m1)
    T26 = [t for t in T if t["day"] >= "2026"]
    rows = []
    miss = 0
    for t in T26:
        e = int(t["entry_t"]); d = t["dir"]
        if e not in m1:
            miss += 1
            continue
        o0, h0, l0, c0 = m1[e]
        nxt = m1.get(e + 60)
        o5 = m1.get(e + 300)
        if nxt is None:
            miss += 1
            continue
        fill0 = o0 + d * TICK                          # engine fill (open + 1 tick)
        fill60 = nxt[0] + d * TICK
        fill300 = (o5[0] + d * TICK) if o5 else None
        adverse_1m = (h0 - o0) if d == 1 else (o0 - l0)   # worst price within the first minute (chasing)
        rows.append({"day": t["day"], "dir": d, "qty": t["qty"], "risk_pts": t["risk_pts"], "r": t["r"], "exit": t["exit"],
                     "engine_entry": t["entry"], "m1_open": o0, "align": abs(fill0 - t["entry"]) < 1e-6,
                     "d60_pts": round((fill60 - fill0) * d, 2), "d300_pts": round((fill300 - fill0) * d, 2) if fill300 else None,
                     "worst1m_pts": round(adverse_1m, 2), "rng1m": round(h0 - l0, 2)})
    n = len(rows)
    d60 = np.array([r["d60_pts"] for r in rows]); q = np.array([r["qty"] for r in rows]); rp = np.array([r["risk_pts"] for r in rows])
    d300 = np.array([r["d300_pts"] if r["d300_pts"] is not None else 0.0 for r in rows])
    worst = np.array([r["worst1m_pts"] for r in rows]); rng = np.array([r["rng1m"] for r in rows])
    cost60 = d60 * q * PV                               # $ worse (>0 = the delayed fill is worse)
    cost300 = d300 * q * PV
    # 1 second: linear share of the first-minute drift (1/60) and a random-walk share of its range (sqrt(1/60))
    one_s_lin = (np.abs(d60) / 60) * q * PV
    one_s_rw = (rng * np.sqrt(1 / 60) / 2) * q * PV     # half the range as the typical excursion, scaled by sqrt(time)
    net26 = S["spans"]["2026"]["net"]
    delay = {"trades": n, "missing_1m": miss, "aligned": int(sum(r["align"] for r in rows)),
             "d60_pts_mean": round(float(d60.mean()), 2), "d60_pts_median": round(float(np.median(d60)), 2),
             "d60_pts_abs_mean": round(float(np.abs(d60).mean()), 2), "d60_worse_pct": round(100 * float((d60 > 0).mean()), 1),
             "d60_better_pct": round(100 * float((d60 < 0).mean()), 1),
             "d60_cost_$_signed": round(float(cost60.sum())), "d60_cost_$_adverse_only": round(float(cost60[cost60 > 0].sum())),
             "d60_cost_$_abs": round(float(np.abs(cost60).sum())),
             "d60_as_pct_of_risk_mean": round(100 * float((np.abs(d60) / rp).mean()), 1),
             "d60_over_10pct_risk": int(((np.abs(d60) / rp) > 0.10).sum()), "d60_over_25pct_risk": int(((np.abs(d60) / rp) > 0.25).sum()),
             "d300_cost_$_signed": round(float(cost300.sum())), "d300_cost_$_abs": round(float(np.abs(cost300).sum())),
             "d300_pts_abs_mean": round(float(np.abs(d300).mean()), 2),
             "worst1m_pts_mean": round(float(worst.mean()), 2), "worst1m_cost_$": round(float((worst * q * PV).sum())),
             "rng1m_mean": round(float(rng.mean()), 2),
             "one_s_linear_$": round(float(one_s_lin.sum())), "one_s_randomwalk_$": round(float(one_s_rw.sum())),
             "net_2026": net26, "pct_net_60s_abs": round(100 * float(np.abs(cost60).sum()) / net26, 1),
             "pct_net_60s_adverse": round(100 * float(cost60[cost60 > 0].sum()) / net26, 1),
             "pct_net_1s_rw": round(100 * float(one_s_rw.sum()) / net26, 2)}
    # by direction of the eventual result: do winners run away from a late order?
    win = np.array([r["r"] > 0 for r in rows])
    delay["d60_pts_mean_winners"] = round(float(d60[win].mean()), 2) if win.any() else None
    delay["d60_pts_mean_losers"] = round(float(d60[~win].mean()), 2) if (~win).any() else None
    delay["d60_cost_$_winners"] = round(float(cost60[win].sum())); delay["d60_cost_$_losers"] = round(float(cost60[~win].sum()))
    tables["delay"] = delay
    tables["delay_rows"] = rows
    print("delay:", json.dumps(delay))

    # ---------------------------------------------------------------- replays (if cached)
    for extra, rid, title, q_, status in (({"entry_mode": "retest"}, "exec_retest", "Limit entry at the trigger zone (retest, 6 bars)",
                                           "Does waiting for a pullback to the IFVG edge beat the next-bar market entry?", None),
                                          ({"slippage_ticks": 2}, "exec_slip2_replay", "2 ticks of slippage (engine replay)",
                                           "Engine check of the post-hoc 2-tick slippage numbers", "info")):
        import hashlib
        params = {**rl.LIVE_PARAMS, **extra}
        key = hashlib.sha1((json.dumps(params, sort_keys=True) + rl._data_key()).encode()).hexdigest()[:16]
        if not os.path.exists(os.path.join(rl.CACHE, key + ".json")):
            print("replay not cached yet:", extra)
            continue
        rawx = rl.replay(extra, procs=2)
        Tx = rl.size(rawx); Sx = rl.score(Tx, rawx)
        hx = headline(Sx)
        tables[rid] = hx
        tables[rid + "_raw_n"] = len(rawx["trades"])
        if rid == "exec_retest":
            A = {t["day"]: t for t in raw["trades"]}; B = {t["day"]: t for t in rawx["trades"]}
            missed = [A[d] for d in A if d not in B]
            diff = [d for d in B if d in A and A[d]["dir"] == B[d]["dir"]]
            imp = np.array([(A[d]["entry"] - B[d]["entry"]) * A[d]["dir"] for d in diff])
            tables["retest_cmp"] = {
                "filled": len(rawx["trades"]), "missed": len(missed), "missed_2026": sum(1 for t in missed if t["day"] >= "2026"),
                "missed_sum_r": round(sum(t["r"] for t in missed), 1), "missed_sum_r_2026": round(sum(t["r"] for t in missed if t["day"] >= "2026"), 1),
                "missed_exits": dict(collections.Counter(t["exit"] for t in missed)),
                "missed_win_pct": round(100 * np.mean([t["r"] > 0 for t in missed]), 1),
                "better_pts_mean": round(float(imp.mean()), 2), "better_pts_median": round(float(np.median(imp)), 2),
                "stop_base_mean": round(float(np.mean([A[d]["risk_pts"] for d in diff])), 1),
                "stop_retest_mean": round(float(np.mean([B[d]["risk_pts"] for d in diff])), 1),
                "fill_delay_min_mean": round(float(np.mean([(B[d]["entry_t"] - A[d]["entry_t"]) / 60 for d in diff])), 1),
                "exits_2026_base": dict(collections.Counter(t["exit"] for t in raw["trades"] if t["day"] >= "2026")),
                "exits_2026_retest": dict(collections.Counter(t["exit"] for t in rawx["trades"] if t["day"] >= "2026")),
                "win_filled_base": round(100 * np.mean([A[d]["r"] > 0 for d in diff]), 1), "win_filled_retest": round(100 * np.mean([B[d]["r"] > 0 for d in diff]), 1)}
            print("retest cmp", json.dumps(tables["retest_cmp"]))
            ok = rl.passes(Sx, S)
            tpw_ok = hx["2026"]["tpw"] >= 2 and hx["2021-25"]["tpw"] >= 2
            status = "adopt-candidate" if ok else ("rejected" if (not tpw_ok or hx["2026"]["net"] < 0.75 * base["2026"]["net"]) else "promising")
            verdict = (f"2026 net ${hx['2026']['net']:,} (locked ${base['2026']['net']:,}), 2021-25 ${hx['2021-25']['net']:,} (locked ${base['2021-25']['net']:,}); "
                       f"{len(missed)} setups never pull back and are missed, they hold {tables['retest_cmp']['missed_sum_r']}R; 2026 falls under 2 trades a week. {status}.")
        else:
            verdict = f"Engine replay with 2-tick slippage: 2026 net {hx['2026']['net']}, 2021-25 {hx['2021-25']['net']} (post-hoc {tables['slip']['2']['2026']['net']} / {tables['slip']['2']['2021-25']['net']})."
        rl.save(rid, title, "other" if rid != "exec_retest" else "timing", q_, params=extra, sizing="live", trades=Tx, scored=Sx,
                status=status, verdict=verdict, notes="Engine replay (rl.replay, procs=2) on the locked params.")
        print(rid, json.dumps(hx))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(tables, fh, indent=1, default=lambda o: dict(o) if isinstance(o, collections.Counter) else str(o))
    print("tables ->", OUT)


if __name__ == "__main__":
    main()
