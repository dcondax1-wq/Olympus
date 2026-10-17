"""Stress tests of the LOCKED strategy (study "stress", runs stress_*, research/writeups/stress-tests.md).

  python tools/research_stress.py all        # every part, tables printed, runs stress_* saved
  python tools/research_stress.py costs      # one part: costs | feed | worst | micro | cap | late

Everything works on the exact live-loop replay of the locked strategy (tools/runlib.replay, cached: 768 raw engine trades)
with the live sizing (runlib.size: quarter size in cold streaks, half size on late entries). No engine replay is run:
engine/model.py has no "enter one bar late" option (entry_mode is market = next bar's open, or retest = a limit at the
trigger zone), so the one-bar-late test is a re-pricing of the same trades on the real 5m bars with the exits kept.

(a) Costs. Engine books: pnl = (exit - entry) x dir x micros x $2 - commission, commission = minis x $4.50 + odd micros x
    $1.50 (10 micros = 1 mini), slippage 1 tick on the entry fill and on every exit except a TARGET (a resting limit).
    Verified on all 768 trades. Stress: slippage 2 / 3 ticks = 1 / 2 extra ticks x $0.50 per micro per leg (entry leg
    always, exit leg unless TARGET); commission doubled = the booked commission once more. The R of every raw trade is
    recomputed with the stressed costs, so the cold-streak filter (which sums R) sees the stressed record too.
(b) Price feed: TradingView trades MNQ1! prints, the engine NQ1! prints. research/pine_parity/parity_locked_2026-10-16.json
    (8 weeks, same script on both feeds) gives the per-trade $ differences; data/tv_mnq_5m_2026-10-16.csv vs
    data/NQ_5m.csv (roll shift removed) gives how often a bar's prints differ and by how much.
(c) Worst plausible start: an MFFU Builder 50K eval started on the worst day, at the start of the worst losing streak and at
    the start of the worst 10-session stretch of every year (engine/analytics.simulate_eval, intraday lows included).
(d) Size rounding: the 1-micro trades, and what rounding down (and the floor of 1 micro) costs or saves versus fractional size.
(e) max_micros 20 and 10 instead of 40: the engine's micros capped after the live sizing (runlib.size max_micros).
(f) One bar late (approximate): fill at the open of the bar AFTER the engine's fill bar (+1 tick slippage), stop and target
    unchanged, micros re-sized from the new stop distance with the same cold/late multiplier, exit price and time kept.
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
from tools import runlib as rl                 # noqa: E402
from engine import sizing as szm               # noqa: E402
from engine.analytics import PLANS, simulate_eval   # noqa: E402

TICK, PV, MINI_RT, MICRO_RT = 0.25, 2.0, 4.50, 1.50
ET = ZoneInfo("America/New_York")
PLAN = PLANS["builder_50k"]
SCRATCH = os.environ.get("STRESS_SCRATCH", os.path.join(ROOT, "research", "lab"))
OUT = {}


# ------------------------------------------------------------------------------------------------ helpers
def comm(q):
    return (q // 10) * MINI_RT + (q % 10) * MICRO_RT


def gross(t, q):
    return (t["exit_price"] - t["entry"]) * t["dir"] * q * PV


def money(x):
    return f"{x:+,.0f}" if x < 0 else f"+{x:,.0f}"


def row(S, name):
    s = S["spans"][name]
    return s


def table(rows, head):
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---:" if i else "---" for i in range(len(head))) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out)


def span_table(named, keys=("2026", "2021-25", "all")):
    """named: [(label, S)]. One block per span with the owner's columns."""
    blocks = []
    for k in keys:
        rows = []
        for lab, S in named:
            s = S["spans"][k]
            rows.append([lab, s["n"], s["tpw"], f"{s['win']}%", s["pf"], money(s["net"]), money(s["per_month"]), money(s["dd"]),
                         f"{s['p10']}% / {s['f10']}%", f"{s['p20']}% / {s['f20']}%", s["b2b"]])
        blocks.append(f"**{k}**\n\n" + table(rows, ["variant", "trades", "/week", "win", "PF", "net $", "$/month", "max DD",
                                                     "eval 2w pass/fail", "eval 1m pass/fail", "b2b"]))
    return "\n\n".join(blocks)


def check_formula(raw):
    bad = 0
    for t in raw["trades"]:
        q = t["qty"]
        if abs(round(gross(t, q) - comm(q), 2) - t["pnl"]) > 0.011:
            bad += 1
        if abs(round(t["pnl"] / (t["risk_pts"] * PV * q), 3) - t["r"]) > 0.0011:
            bad += 1
    return bad


# ------------------------------------------------------------------------------------------------ (a) costs
def restress_raw(raw, slip_ticks=1, comm_mult=1.0):
    trades = []
    for t in raw["trades"]:
        q = t["qty"]
        legs = 1 if t["exit"] == "TARGET" else 2
        extra = (slip_ticks - 1) * TICK * PV * q * legs
        pnl = gross(t, q) - comm_mult * comm(q) - extra
        trades.append({**t, "pnl": round(pnl, 2), "r": round(pnl / (t["risk_pts"] * PV * q), 3)})
    return {**raw, "trades": trades}


def part_costs(raw, T0, S0, save=True):
    print("\n## (a) Costs")
    # what the baseline already pays
    base_comm = sum(comm(t["qty"]) for t in T0)
    base_slip = sum(TICK * PV * t["qty"] * (1 if t["exit"] == "TARGET" else 2) for t in T0)
    gross_all = sum(gross(t, t["qty"]) for t in T0)
    by = {}
    for k, a, z in rl.SPANS:
        Tk = [t for t in T0 if a <= t["day"] <= z]
        by[k] = {"comm": sum(comm(t["qty"]) for t in Tk), "slip": sum(TICK * PV * t["qty"] * (1 if t["exit"] == "TARGET" else 2) for t in Tk),
                 "gross": sum(gross(t, t["qty"]) for t in Tk), "n": len(Tk), "target_exits": sum(1 for t in Tk if t["exit"] == "TARGET"),
                 "micros": sum(t["qty"] for t in Tk)}
    print("baseline costs: commission", round(base_comm), "slippage", round(base_slip), "gross", round(gross_all))
    cases = [("slip2", "Slippage 2 ticks", 2, 1.0), ("slip3", "Slippage 3 ticks", 3, 1.0), ("comm2", "Commission doubled", 1, 2.0),
             ("slip2_comm2", "Slippage 2 ticks + commission doubled", 2, 2.0), ("slip3_comm2", "Slippage 3 ticks + commission doubled", 3, 2.0)]
    named = [("Baseline (1 tick, $1.50/micro)", S0)]
    res = {"baseline_costs": by}
    cold0 = {t["entry_t"]: t["half"] for t in T0}
    for cid, lab, sl, cm in cases:
        raw_s = restress_raw(raw, sl, cm)
        T = rl.size(raw_s)
        S = rl.score(T, raw_s)
        flips = sum(1 for t in T if cold0.get(t["entry_t"]) != t["half"])
        extra = sum(t0["pnl"] for t0 in T0) - sum(t["pnl"] for t in T)
        named.append((lab, S))
        res[cid] = {"label": lab, "slip_ticks": sl, "comm_mult": cm, "cold_flips": flips, "extra_cost_all": round(extra),
                    "spans": {k: {kk: S["spans"][k][kk] for kk in ("n", "net", "pf", "per_month", "dd", "p10", "f10", "p20", "f20", "b2b", "win")}
                              for k in ("2026", "2021-25", "all")}}
        print(f"{lab}: cold flips {flips}, extra cost ${extra:,.0f}")
        for k in ("2026", "2021-25", "all"):
            print("  ", rl.line(S, k))
        if save:
            rl.save(f"stress_{cid}", f"Stress: {lab.lower()}", "other", "What do higher execution costs do to the locked strategy?",
                    params={"slippage_ticks": sl, "commission_mult": cm}, trades=T, scored=S, status="info",
                    verdict=(f"Costs re-priced on the exact replay (slippage {sl} ticks, commission x{cm:g}): "
                             f"2026 {money(S['spans']['2026']['net'])} (PF {S['spans']['2026']['pf']}), 2021-25 {money(S['spans']['2021-25']['net'])} "
                             f"(PF {S['spans']['2021-25']['pf']}); cold-streak state flipped on {flips} trades."),
                    notes="pnl = (exit - entry) x dir x micros x $2 - commission x mult - extra slippage (ticks - 1) x $0.50 x micros x legs "
                          "(entry leg + exit leg unless TARGET). R recomputed, so the cold-streak filter sees the stressed record.",
                    writeup="stress-tests.md", tags=["stress", "costs"])
    print(span_table(named))
    # break-even slippage (linear in ticks on the raw record, filter state frozen at baseline): 2021-25 and all
    for k, a, z in rl.SPANS:
        Tk = [t for t in T0 if a <= t["day"] <= z]
        per_tick = sum(TICK * PV * t["qty"] * (1 if t["exit"] == "TARGET" else 2) for t in Tk)
        net = sum(t["pnl"] for t in Tk)
        res.setdefault("per_extra_tick", {})[k] = {"cost_per_extra_tick": round(per_tick), "net": round(net),
                                                    "ticks_to_zero": round(net / per_tick, 1) if per_tick else None}
        print(f"{k}: each extra tick of slippage costs ${per_tick:,.0f}; net {net:,.0f} -> zero at {net / per_tick:.1f} extra ticks")
    OUT["costs"] = res
    return res


# ------------------------------------------------------------------------------------------------ (b) price feed
def part_feed(T0):
    print("\n## (b) Price feed: MNQ1! (TradingView) vs NQ1! (engine)")
    import pandas as pd
    par = json.load(open(os.path.join(ROOT, "research", "pine_parity", "parity_locked_2026-10-16.json"), encoding="utf-8"))
    rows = par["rows"]
    matched = [r for r in rows if r["status"] in ("MATCH", "R DIFF")]
    tv_only = [r for r in rows if r["status"] == "TV ONLY"]
    py_only = [r for r in rows if r["status"] == "PY ONLY"]
    diffs = [(r["tv_usd"] - r["py_usd"]) for r in matched]
    size_diff = [r for r in matched if not r["size_ok"]]
    exit_diff = [r for r in matched if r["tv"] != r["py"]]
    net_tv, net_py = par["parity"]["net_tv"], par["parity"]["net_py_mnq"]
    drift = net_tv - net_py
    unmatched_usd = sum(r["tv_usd"] for r in tv_only) - sum(r["py_usd"] for r in py_only)
    size_usd = sum((r["tv_usd"] - r["py_usd"]) for r in size_diff)
    price_usd = sum((r["tv_usd"] - r["py_usd"]) for r in matched if r["size_ok"])
    weeks = 8.0
    n_rows = len(rows)
    # trades a year from the baseline (all years)
    sess = len({t["day"] for t in T0})
    tpy = len(T0) / (1278 / 252)
    mean_abs = float(np.mean([abs(d) for d in diffs] + [abs(r["tv_usd"]) for r in tv_only] + [abs(r["py_usd"]) for r in py_only]))
    scale_lin = 52 / weeks
    scale_sqrt = scale_lin ** 0.5
    feed = {"window": par["parity"]["window"], "rows": n_rows, "matched": len(matched), "tv_only": len(tv_only), "py_only": len(py_only),
            "size_diff": len(size_diff), "exit_diff": len(exit_diff), "net_tv": net_tv, "net_py_mnq": net_py, "drift_8w": round(drift, 2),
            "drift_from_unmatched": round(unmatched_usd, 2), "drift_from_sizes": round(size_usd, 2), "drift_from_prices": round(price_usd, 2),
            "mean_abs_diff_per_row": round(mean_abs, 2), "gross_churn_per_year": round(mean_abs * tpy),
            "drift_year_random_walk": round(abs(drift) * scale_sqrt), "drift_year_one_way": round(abs(drift) * scale_lin),
            "trades_per_year": round(tpy, 1)}
    print(json.dumps(feed, indent=1))
    # bars: MNQ export vs NQ file, roll shift removed
    nq = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
    mn = pd.read_csv(os.path.join(ROOT, "data", "tv_mnq_5m_2026-10-16.csv"))
    rolls = json.load(open(os.path.join(ROOT, "data", "NQ_rolls.json"), encoding="utf-8"))["rolls"]
    m = nq.merge(mn, on="time", suffixes=("_nq", "_mn"))
    adj = np.zeros(len(m))
    for r in rolls:
        adj += np.where(m["time"].values < r["switch_t"], r["gap"], 0.0)
    mod = np.array([dt.datetime.fromtimestamp(int(t), ET).hour * 60 + dt.datetime.fromtimestamp(int(t), ET).minute for t in m["time"]])
    rth = (mod >= 570) & (mod < 960)
    bars = {}
    for col in ("open", "high", "low", "close"):
        d = ((m[col + "_mn"].values - (m[col + "_nq"].values - adj)) / TICK)
        for lab, mask in (("all", np.ones(len(m), bool)), ("rth", rth)):
            x = d[mask]
            bars[f"{col}_{lab}"] = {"bars": int(mask.sum()), "mean_ticks": round(float(x.mean()), 2), "mean_abs_ticks": round(float(np.abs(x).mean()), 2),
                                    "pct_ge1": round(100 * float((np.abs(x) >= 1).mean()), 1), "pct_ge2": round(100 * float((np.abs(x) >= 2).mean()), 1),
                                    "pct_ge4": round(100 * float((np.abs(x) >= 4).mean()), 1), "max_abs": int(np.abs(x).max())}
    # same-direction check: a 3-pt gap edge is 12 ticks; stop distances change when the sweep extreme (a low/high) differs
    print(json.dumps({k: v for k, v in bars.items() if k.endswith("rth")}, indent=1))
    feed["bars"] = bars
    OUT["feed"] = feed
    return feed


# ------------------------------------------------------------------------------------------------ (c) worst start
def run_eval(days, k0, horizon=None):
    pn = [d["pnl"] for d in days[k0:]]
    lo = [d["low"] for d in days[k0:]]
    if horizon:
        pn, lo = pn[:horizon], lo[:horizon]
    r = simulate_eval(pn, PLAN, lo)
    # closest approach to the trailing max loss (cushion), $: from the path (balance after each day, mll)
    bal = PLAN["start"]
    cush = []
    for k, p in enumerate(r["path"]):
        intra = bal + lo[k]
        cush.append(min(intra, p["balance"]) - p["mll"])
        bal = p["balance"]
    return {"result": r["result"], "sessions": r["days"], "balance": r["balance"], "min_cushion": round(min(cush), 2) if cush else None,
            "trough": round(min(p["balance"] for p in r["path"]) - PLAN["start"], 2) if r["path"] else None}


def part_worst(T0, S0):
    print("\n## (c) Worst plausible start")
    days = S0["days"]
    idx = {d["date"]: i for i, d in enumerate(days)}
    years = sorted({d["date"][:4] for d in days})
    out = {"years": {}, "all_starts": None}
    # all starts for reference: distribution of outcomes
    allres = [run_eval(days, k) for k in range(len(days))]
    cnt = collections.Counter(r["result"] for r in allres)
    out["all_starts"] = {k: round(100 * v / len(allres), 1) for k, v in cnt.items()}
    print("every start, run to the end of the data:", out["all_starts"])
    for y in years:
        D = [(i, d) for i, d in enumerate(days) if d["date"][:4] == y]
        Ty = [t for t in T0 if t["day"][:4] == y]
        if not D:
            continue
        # worst day
        iw, dw = min(D, key=lambda x: x[1]["pnl"])
        # worst 10-session stretch
        best = None
        for j in range(len(D)):
            win = D[j:j + 10]
            if len(win) < 10:
                break
            s = sum(d["pnl"] for _, d in win)
            if best is None or s < best[0]:
                best = (s, win[0][0], win[0][1]["date"], win[-1][1]["date"])
        # worst losing streak (consecutive losing trades) by count, then by $; and the biggest $ losing run
        streaks, cur = [], []
        for t in Ty:
            if t["pnl"] < 0:
                cur.append(t)
            else:
                if cur:
                    streaks.append(cur)
                cur = []
        if cur:
            streaks.append(cur)
        longest = max(streaks, key=lambda s: (len(s), -sum(t["pnl"] for t in s))) if streaks else []
        costliest = min(streaks, key=lambda s: sum(t["pnl"] for t in s)) if streaks else []
        # ten worst individual days summed
        ten = sorted((d["pnl"] for _, d in D))[:10]
        rec = {"worst_day": {"date": dw["date"], "pnl": dw["pnl"], "eval": run_eval(days, iw)},
               "worst_10_sessions": {"from": best[2], "to": best[3], "pnl": round(best[0], 2), "eval": run_eval(days, best[1])} if best else None,
               "longest_losing_streak": {"trades": len(longest), "pnl": round(sum(t["pnl"] for t in longest), 2),
                                         "from": longest[0]["day"] if longest else None, "to": longest[-1]["day"] if longest else None,
                                         "eval": run_eval(days, idx[longest[0]["day"]]) if longest else None},
               "costliest_losing_streak": {"trades": len(costliest), "pnl": round(sum(t["pnl"] for t in costliest), 2),
                                           "from": costliest[0]["day"] if costliest else None, "to": costliest[-1]["day"] if costliest else None,
                                           "eval": run_eval(days, idx[costliest[0]["day"]]) if costliest else None},
               "ten_worst_days_sum": round(sum(ten), 2), "sessions": len(D), "trades": len(Ty)}
        out["years"][y] = rec
        print(y, json.dumps(rec, default=str))
    # the worst of everything over all 5 years
    allD = list(enumerate(days))
    worst10 = None
    for j in range(len(allD) - 9):
        s = sum(d["pnl"] for _, d in allD[j:j + 10])
        if worst10 is None or s < worst10[0]:
            worst10 = (s, j, allD[j][1]["date"], allD[j + 9][1]["date"])
    out["worst_10_sessions_all"] = {"from": worst10[2], "to": worst10[3], "pnl": round(worst10[0], 2), "eval": run_eval(days, worst10[1])}
    # how many starts in each year end in a fail, and how deep the worst eval got
    out["fail_by_start_year"] = {}
    for y in years:
        ks = [i for i, d in enumerate(days) if d["date"][:4] == y]
        rs = [allres[k] for k in ks]
        c = collections.Counter(r["result"] for r in rs)
        out["fail_by_start_year"][y] = {"starts": len(rs), "pass_pct": round(100 * c["PASS"] / len(rs), 1), "fail_pct": round(100 * c["FAIL"] / len(rs), 1),
                                        "open_pct": round(100 * c["OPEN"] / len(rs), 1),
                                        "min_cushion": round(min(r["min_cushion"] for r in rs), 2),
                                        "fail_fast_10": round(100 * sum(1 for r in rs if r["result"] == "FAIL" and r["sessions"] <= 10) / len(rs), 1),
                                        "median_fail_sessions": float(np.median([r["sessions"] for r in rs if r["result"] == "FAIL"])) if c["FAIL"] else None}
    print(json.dumps(out["fail_by_start_year"], indent=1))
    OUT["worst"] = out
    return out


# ------------------------------------------------------------------------------------------------ (d) size rounding
def frac_micros(t, cold_mult, late):
    """Unrounded micros the sizing rules imply: $800 x min(1, 20/stop) [x 0.5 trending] / (stop x $2) x cold x late."""
    usd = rl.LIVE_PARAMS["risk_usd"] * min(1.0, rl.LIVE_PARAMS["risk_ref_stop"] / t["risk_pts"])
    if "trending regime: half size" in (t.get("conf_tags") or []):
        usd *= 0.5
    q = usd / (t["risk_pts"] * PV)
    q *= cold_mult
    if late:
        q *= float(rl.LIVE_SIZING["late_mult"])
    return min(q, rl.MAX_MICROS)


def part_micro(raw, T0, S0, save=True):
    print("\n## (d) Size rounding and 1-micro trades")
    raw_sorted = sorted(raw["trades"], key=lambda t: t["entry_t"])
    out = {}
    one = [t for t in T0 if t["qty"] == 1]
    res = {"n_all": len(T0), "n_one": len(one), "one_net": round(sum(t["pnl"] for t in one), 2), "one_wins": sum(1 for t in one if t["pnl"] > 0),
           "one_r_sum": round(sum(t["r"] for t in one), 2), "one_cold": sum(1 for t in one if t["half"]),
           "one_late": sum(1 for t in one if szm.is_late(t)), "one_wide": sum(1 for t in one if t["risk_pts"] > 30)}
    # fractional vs rounded, trade by trade
    rows = []
    for t in T0:
        cm, _ = rl.cold_status(raw_sorted, t["entry_t"], rl.LIVE_EQF)
        qf = frac_micros(t, cm, szm.is_late(t))
        per = t["pnl"] / t["qty"]
        rows.append({"day": t["day"], "qty": t["qty"], "qf": qf, "pnl": t["pnl"], "pnl_frac": per * qf, "per": per, "cold": t["half"]})
    def agg(rs):
        if not rs:
            return {}
        d = sum(r["pnl"] - r["pnl_frac"] for r in rs)
        return {"n": len(rs), "actual": round(sum(r["pnl"] for r in rs)), "fractional": round(sum(r["pnl_frac"] for r in rs)),
                "rounding_effect": round(d), "avg_micros_actual": round(float(np.mean([r["qty"] for r in rs])), 2),
                "avg_micros_frac": round(float(np.mean([r["qf"] for r in rs])), 2)}
    for k, a, z in rl.SPANS:
        rs = [r for r in rows if a <= r["day"] <= z]
        ones = [r for r in rs if r["qty"] == 1]
        up = [r for r in ones if r["qf"] < 1]
        res.setdefault("spans", {})[k] = {"all": agg(rs), "one_micro": agg(ones), "one_micro_rounded_up": agg(up),
                                          "one_micro_rounded_down": agg([r for r in ones if r["qf"] >= 1]),
                                          "one_win_pct": round(100 * sum(1 for r in ones if r["pnl"] > 0) / len(ones), 1) if ones else None,
                                          "one_pf": (round(sum(r["pnl"] for r in ones if r["pnl"] > 0) / -sum(r["pnl"] for r in ones if r["pnl"] < 0), 2)
                                                     if any(r["pnl"] < 0 for r in ones) else None)}
    print(json.dumps(res, indent=1))
    # variant: skip the 1-micro trades (what the money looks like without them; the filter still sees them as signals)
    sizing = rl.LIVE_SIZING

    def skip_one(t, ctx):
        q = szm.route_qty(int(t["qty"]), t, ctx["cold_mult"], sizing, rl.LIVE_PARAMS)["qty"]
        return 0.0 if q <= 1 else 1.0
    T = rl.size(raw, rule=skip_one)
    S = rl.score(T, raw)
    for k in ("2026", "2021-25", "all"):
        print("  skip 1-micro:", rl.line(S, k))
    res["skip_one"] = {k: {kk: S["spans"][k][kk] for kk in ("n", "tpw", "net", "pf", "per_month", "dd", "p20", "f20", "b2b")} for k in ("2026", "2021-25", "all")}
    if save:
        rl.save("stress_skip_1micro", "Stress: skip the 1-micro trades", "risk", "Are the 1-micro trades worth placing?",
                sizing={"skip_qty_le": 1}, trades=T, scored=S, status="info",
                verdict=(f"Without the {res['n_one']} one-micro trades: 2026 {money(S['spans']['2026']['net'])} (PF {S['spans']['2026']['pf']}), "
                         f"2021-25 {money(S['spans']['2021-25']['net'])} (PF {S['spans']['2021-25']['pf']}), {S['spans']['2021-25']['tpw']} trades a week. "
                         "Information only: the 1-micro trades are mostly cold-streak quarter-size trades and they are the paper record that ends a cold streak."),
                notes="Rule: a trade whose live-sized quantity is 1 micro is not placed. The cold-streak filter still counts it (it sums every signal's R).",
                writeup="stress-tests.md", tags=["stress", "rounding"])
    OUT["micro"] = res
    return res


# ------------------------------------------------------------------------------------------------ (e) max micros
def part_cap(raw, T0, S0, save=True):
    print("\n## (e) max_micros 20 / 10")
    named = [("max 40 (live)", S0)]
    res = {}
    for cap in (20, 10):
        T = rl.size(raw, rule=lambda t, ctx: 1.0, max_micros=cap)
        S = rl.score(T, raw)
        capped = [(a, b) for a, b in zip(sorted(T0, key=lambda t: t["entry_t"]), sorted(T, key=lambda t: t["entry_t"])) if a["qty"] != b["qty"]]
        lost = sum(a["pnl"] - b["pnl"] for a, b in capped)
        by = {}
        for k, a, z in rl.SPANS:
            c = [(x, y) for x, y in capped if a <= x["day"] <= z]
            by[k] = {"capped": len(c), "lost": round(sum(x["pnl"] - y["pnl"] for x, y in c)),
                     "capped_wins": sum(1 for x, y in c if x["pnl"] > 0), "n": S["spans"][k]["n"]}
        named.append((f"max {cap}", S))
        res[cap] = {"capped_trades": len(capped), "lost_vs_live": round(lost), "by": by,
                    "spans": {k: {kk: S["spans"][k][kk] for kk in ("n", "net", "pf", "per_month", "dd", "p10", "f10", "p20", "f20", "b2b", "risk")} for k in ("2026", "2021-25", "all")}}
        print(f"max {cap}: capped {len(capped)} trades, ${lost:,.0f} less than live", json.dumps(by))
        for k in ("2026", "2021-25", "all"):
            print("  ", rl.line(S, k))
        if save:
            rl.save(f"stress_max{cap}", f"Stress: at most {cap} micros a trade", "risk", f"What if the plan allowed only {cap} micros ({cap // 10} minis)?",
                    sizing={"max_micros": cap}, trades=T, scored=S, status="info",
                    verdict=(f"Cap {cap} micros: {len(capped)} trades capped, ${lost:,.0f} less over 5 years; 2026 {money(S['spans']['2026']['net'])} "
                             f"(PF {S['spans']['2026']['pf']}), 2021-25 {money(S['spans']['2021-25']['net'])} (PF {S['spans']['2021-25']['pf']})."),
                    notes="Live sizing, then the engine's micros capped. Same trades, same filter state; only the size of the tight-stop trades changes.",
                    writeup="stress-tests.md", tags=["stress", "contracts"])
    print(span_table(named))
    OUT["cap"] = res
    return res


# ------------------------------------------------------------------------------------------------ (f) one bar late (approx)
def part_late(raw, T0, S0, save=True):
    print("\n## (f) Entry one bar late (approximate: same exits)")
    import pandas as pd
    bars = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
    op = dict(zip(bars["time"].astype(int), bars["open"].astype(float)))
    tday = {int(t): dt.datetime.fromtimestamp(int(t), ET).strftime("%Y-%m-%d") for t in bars["time"]}
    sized = {t["entry_t"]: t for t in T0}
    kept, skipped, gap_stop, past_target, no_bar, same_bar_exit = [], [], 0, 0, 0, 0
    fill_check = 0
    for t in raw["trades"]:
        d = t["dir"]
        if abs(op.get(t["entry_t"], np.nan) + d * TICK - t["entry"]) > 1e-6:
            fill_check += 1
        t1 = t["entry_t"] + 300
        if t1 not in op or tday.get(t1) != t["day"]:
            no_bar += 1
            skipped.append(t)
            continue
        s = sized.get(t["entry_t"])
        if s is None:
            continue
        e1 = op[t1] + d * TICK
        rp1 = (e1 - t["stop"]) * d
        if rp1 <= 0:
            gap_stop += 1
            skipped.append(t)
            continue
        if (t["target"] - e1) * d <= 0:
            past_target += 1
            skipped.append(t)
            continue
        if t["exit_t"] <= t1:
            same_bar_exit += 1
        usd = rl.LIVE_PARAMS["risk_usd"] * min(1.0, rl.LIVE_PARAMS["risk_ref_stop"] / rp1)
        if "trending regime: half size" in (t.get("conf_tags") or []):
            usd *= 0.5
        q0 = int(min(rl.MAX_MICROS, usd // (rp1 * PV)))
        if q0 < 1:
            skipped.append(t)
            continue
        mult = s["qty"] / t["qty"]
        q = q0 if mult >= 1 else max(1, int(np.floor(q0 * mult)))
        q = min(q, rl.MAX_MICROS)
        pnl = (t["exit_price"] - e1) * d * q * PV - comm(q)
        r = pnl / (rp1 * PV * q)
        x = {**s, "entry": e1, "entry_t": t1, "risk_pts": round(rp1, 2), "qty": q, "pnl": round(pnl, 2), "r": round(r, 3),
             "risk_usd": round(rp1 * PV * q, 2), "mult": round(q / max(q0, 1), 3), "low": -min(float(t.get("mae") or 0), max(1.0, -r)) * rp1 * PV * q,
             "entry_shift_ticks": round((e1 - t["entry"]) * d / TICK, 1)}
        kept.append(x)
    S = rl.score(kept, raw)
    shift = np.array([x["entry_shift_ticks"] for x in kept])
    res = {"fill_check_mismatch": fill_check, "kept": len(kept), "skipped": len(skipped), "no_next_bar": no_bar, "gap_through_stop": gap_stop,
           "past_target": past_target, "exit_before_or_at_new_fill": same_bar_exit,
           "entry_shift_ticks": {"mean": round(float(shift.mean()), 2), "median": float(np.median(shift)), "worse_pct": round(100 * float((shift > 0).mean()), 1),
                                 "better_pct": round(100 * float((shift < 0).mean()), 1), "p10": float(np.percentile(shift, 10)), "p90": float(np.percentile(shift, 90))},
           "skipped_pnl_live": round(sum(sized[t["entry_t"]]["pnl"] for t in skipped if t["entry_t"] in sized), 2),
           "spans": {k: {kk: S["spans"][k][kk] for kk in ("n", "tpw", "net", "pf", "per_month", "dd", "p20", "f20", "b2b", "win")} for k in ("2026", "2021-25", "all")}}
    print(json.dumps(res, indent=1))
    for k in ("2026", "2021-25", "all"):
        print("  ", rl.line(S, k))
    if save:
        rl.save("stress_late1bar_approx", "Stress: entry one bar late (approximate)", "timing",
                "What if every fill came one 5-minute bar after the engine's fill?",
                params={"entry_delay_bars": 1, "method": "re-priced on the real bars, exits kept"}, trades=kept, scored=S, status="info",
                verdict=(f"Approximate (same exits): {len(kept)} of {len(raw['trades'])} trades keep a valid entry; 2026 {money(S['spans']['2026']['net'])} "
                         f"(PF {S['spans']['2026']['pf']}), 2021-25 {money(S['spans']['2021-25']['net'])} (PF {S['spans']['2021-25']['pf']}). "
                         "No engine option exists for a delayed entry, so the exits are not re-simulated."),
                notes=("Fill = open of the bar after the engine's fill bar + 1 tick; stop/target unchanged; micros from the new stop distance with the "
                       "same cold/late multiplier; exit price and time kept. Trades whose late fill would be through the stop or past the target are dropped."),
                writeup="stress-tests.md", tags=["stress", "execution"])
    OUT["late"] = res
    return res


# ------------------------------------------------------------------------------------------------ main
def main(parts):
    raw = rl.replay()
    bad = check_formula(raw)
    print(f"P&L formula check: {bad} mismatches on {len(raw['trades'])} raw trades")
    T0 = rl.size(raw)
    S0 = rl.score(T0, raw)
    for k in ("2026", "2021-25", "all"):
        print("baseline", rl.line(S0, k))
    OUT["baseline"] = {k: S0["spans"][k] for k in ("2026", "2021-25", "all")}
    OUT["formula_mismatches"] = bad
    save = "--nosave" not in sys.argv
    if "costs" in parts:
        part_costs(raw, T0, S0, save)
    if "feed" in parts:
        part_feed(T0)
    if "worst" in parts:
        part_worst(T0, S0)
    if "micro" in parts:
        part_micro(raw, T0, S0, save)
    if "cap" in parts:
        part_cap(raw, T0, S0, save)
    if "late" in parts:
        part_late(raw, T0, S0, save)
    os.makedirs(SCRATCH, exist_ok=True)
    path = os.path.join(SCRATCH, "stress_results.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(OUT, fh, indent=1, default=str)
    print("saved", path)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    parts = ["costs", "feed", "worst", "micro", "cap", "late"] if (not args or args[0] == "all") else args
    main(parts)
