"""Lane D part 2: RE-ENTRY after a LIT stop-out, and the signals today's 1-trade-a-day rule blocks.

PRE-REGISTERED (this list is the whole grid, 13 versions + one diagnostic census):
  Engine runs with the live LIT params + max_per_day 3 and the engine's own `second` hook (engine/lit.py _run_core, same rules,
  new stop 1 tick beyond the NEW sweep extreme, size from the new stop, one VIX-band target, 1m CISD entry, costs in). The first
  trade of every day is checked to be IDENTICAL to today's live trade (the check below); only the extra trades are new.
  Blocked-signal census (diagnostic, not a version): every extra trade (max_per_day 3, after any exit) as its own ledger,
  split by how the day's first trade ended, and by "setup came while the first trade was still open" (the busy rule is kept in
  every run: one position at a time).
  Versions (extra trade added to today's trades, sized by the LIT size rule x m; m 1.0 and 0.5):
    R1  after a STOP, any side, any level                      (second after STOP)
    R2  after a STOP, SAME side, SAME swept level re-swept, same session bucket (London / NY pre / NY open / PM)
    R3  after a STOP, same side, any level
    R4  after a STOP, OPPOSITE side (the reversal)
    R5  after a STOP, cool-off 30 min, any side
    R6  after any exit but STOP (BE / TARGET / EOD / CUT), any side (the day-cap census as money)
    R7  Monday rule off (the setups the Monday block blocks)
  Gate (lane): beats today's LIT in BOTH 2026 halves (LIT size $ and eval-path $, no more 2-week fails) and 2021-25 not worse.

    python -X utf8 research/edge_hunt/d/reentry.py
"""
from __future__ import annotations

import collections
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import E, HERE, SP, log_variant, row, span_sum, verdict  # noqa: E402
from tools import lit_final as F  # noqa: E402
from engine import lit  # noqa: E402

LIVE = E.LIVE


def sess_bucket(mod):
    return 0 if mod < 300 else 1 if mod < 570 else 2 if mod < 720 else 3        # London / NY pre / NY open / PM (minutes of ET day)


def engine_run(extra):
    P = {**LIVE, **extra}
    return F.run(P)


def mod_of(t):
    import datetime as dt
    from zoneinfo import ZoneInfo
    d = dt.datetime.fromtimestamp(int(t["entry_t"]), ZoneInfo("America/New_York"))
    return d.hour * 60 + d.minute


def extras(T_all, T_base):
    """Trades of the widened run that are not today's trades, with the day's first trade attached."""
    bk = {int(t["entry_t"]) for t in T_base}
    by = collections.defaultdict(list)
    for t in sorted(T_all, key=lambda t: t["entry_t"]):
        by[t["day"]].append(t)
    out = []
    for day, L in by.items():
        for i, t in enumerate(L):
            if i >= 1 and int(t["entry_t"]) not in bk:
                out.append((t, L[0], L[i - 1]))
    return out


def run_units(T_base, T_extra, m):
    """E.trades re-walks every trade (live exit rules == the engine's); extras get multiplier m."""
    U = E.trades(T=T_base)
    xs = E.trades(T=[t for t in T_extra])
    for u in xs:
        u["m"] = m
        u["extra"] = True
    return sorted(U + xs, key=lambda u: u["entry_t"])


def stats_ledger(U):
    """The extras as their own ledger at the LIT size: n, win share, PF, $ per span."""
    L = [l for l in E.lit_size(U) if l.get("extra")]
    o = {}
    for sp in SP:
        a, z = E.SPANS[sp]
        x = [l for l in L if a <= l["day"] <= z]
        p = np.array([l["pnl"] for l in x]) if x else np.array([0.0])
        gl = -p[p < 0].sum()
        o[sp] = {"n": len(x), "net": round(float(p.sum())), "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None,
                 "win": round(100 * float((p > 0).mean()), 1) if x else None,
                 "avgR": round(float(np.mean([l["r"] for l in x])), 3) if x else None}
    return o


def main():
    c = E.ctx()
    T_base = c["T"]
    # --- check: widened engine's first trade per day == today's trade
    T3 = engine_run({"max_per_day": 3, "second": {"after": ["STOP", "BE", "TARGET", "EOD", "CUT_T15"], "side": "any"}})
    first = {}
    for t in sorted(T3, key=lambda t: t["entry_t"]):
        first.setdefault(t["day"], t)
    bk = {int(t["entry_t"]) for t in T_base}
    mism = sum(1 for t in first.values() if int(t["entry_t"]) not in bk) + sum(1 for t in T_base if int(t["entry_t"]) not in {int(x["entry_t"]) for x in T3})
    print("check: today's trades missing/changed in the widened run =", mism, "of", len(T_base), "| widened run trades", len(T3), flush=True)

    base_o, _, base_L = E.evaluate()
    base = E.short(base_o)
    print(row("today's LIT", base), flush=True)
    res = {"_base": base, "_check_mismatch": mism}

    # --- census
    ex_all = extras(T3, T_base)
    census = collections.defaultdict(list)
    for t, f0, prev in ex_all:
        census[prev["exit"]].append(t)
        census["ALL"].append(t)
    cen = {}
    for k, ts in census.items():
        U = run_units(T_base, ts, 1.0)
        cen[k] = stats_ledger(U)
        print("CENSUS after", k, {sp: cen[k][sp] for sp in SP}, flush=True)
    res["_census"] = cen

    def sel(fn):
        return [t for t, f0, prev in ex_all if fn(t, f0, prev)]

    def same_level(t, f0, prev):
        return t["dir"] == prev["dir"] and bool(set(t["swept"]) & set(prev["swept"])) and sess_bucket(mod_of(t)) == sess_bucket(mod_of(prev))

    cfg = collections.OrderedDict()
    cfg["R1_after_stop_any"] = (sel(lambda t, f0, p: p["exit"] == "STOP"), "after a STOP, any side / level")
    cfg["R2_same_level_same_session"] = (sel(lambda t, f0, p: p["exit"] == "STOP" and same_level(t, f0, p)),
                                         "after a STOP, same side, re-sweep of the SAME level, same session bucket")
    cfg["R3_same_side"] = (sel(lambda t, f0, p: p["exit"] == "STOP" and t["dir"] == p["dir"]), "after a STOP, same side, any level")
    cfg["R4_opposite_side"] = (sel(lambda t, f0, p: p["exit"] == "STOP" and t["dir"] != p["dir"]), "after a STOP, opposite side")
    cfg["R5_cool30"] = (sel(lambda t, f0, p: p["exit"] == "STOP" and t["entry_t"] >= p["exit_t"] + 1800), "after a STOP, 30 min cool-off")
    cfg["R6_after_not_stop"] = (sel(lambda t, f0, p: p["exit"] != "STOP"), "after BE / TARGET / EOD / CUT, any side")
    # R7: Monday rule off = engine run without it; extras = trades not in today's list (first-of-day only)
    T7 = engine_run({"monday": False})
    ex7 = [t for t in T7 if int(t["entry_t"]) not in bk]
    print("R7 Monday-rule-off trades not in today's list:", len(ex7), flush=True)
    for nm, (ts, desc) in cfg.items():
        for m in (1.0, 0.5):
            U = run_units(T_base, ts, m)
            o, _, L = E.evaluate(U=U)
            s = E.short(o, base_o)
            s["extra_n"] = {sp: sum(1 for t in ts if E.SPANS[sp][0] <= t["day"] <= E.SPANS[sp][1]) for sp in SP}
            s["extra_ledger"] = stats_ledger(U)
            s["pass"] = verdict(s)
            k = f"{nm}_x{m}"
            res[k] = s
            log_variant("D-reentry", k, desc, {"d_lit": s["d_lit"], "d_eval": s["d_eval"], "pass": s["pass"]})
            print(row(k, s), "| extras", s["extra_n"], "ledger", {sp: (s["extra_ledger"][sp]["net"], s["extra_ledger"][sp]["pf"]) for sp in SP}, "pass", s["pass"], flush=True)
    for m in (1.0, 0.5):
        U = run_units([t for t in T_base if True], ex7, m) if False else None
    # R7 as a swap: today's list replaced by the Monday-off run (the engine's own sequence)
    U = E.trades(T=T7)
    for u in U:
        u["m"] = 1.0
    o, _, L = E.evaluate(U=U)
    s = E.short(o, base_o)
    s["extra_n"] = len(ex7)
    s["pass"] = verdict(s)
    res["R7_monday_off"] = s
    log_variant("D-reentry", "R7_monday_off", "Monday rule off", {"d_lit": s["d_lit"], "d_eval": s["d_eval"], "pass": s["pass"]})
    print(row("R7_monday_off", s), "pass", s["pass"], flush=True)
    json.dump(res, open(os.path.join(HERE, "reentry_results.json"), "w"), indent=1, default=float)


if __name__ == "__main__":
    main()
