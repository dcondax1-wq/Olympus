"""night-of-monfix 2026-11-27: lane A before vs after the Monday 'previous day' fix, on the real pulled tick days.

before = the old rule (proof.py): previous day = the previous usable file (>= MIN_ROWS rows) within 4 calendar days, old
         levels() (a Sunday-evening file stands in as the prior day; a thin Sunday is skipped and its 18:00-24:00 lost).
after  = engine/of_paper._prev_summary's new rule: previous day = the last file WITH RTH bars; Globex-only files in between
         (any size) join the overnight range.
Books: 'first' = the engine's replay_summary book (the first absorbed signal of each day: one step() call, exits resolved
after the signal loop), 'onepos' = every absorbed signal, one position at a time (a signal is taken when the earlier taken
trade's exit bar is at or before the signal bar). v1 entry (next open + 1 tick) and E5 entry (DESIGN_paper_v2) both scored.
Trading days: weekdays with RTH bars, the 11-26 half day skipped. Paper research only: no rule change.
Run: python -X utf8 research/orderflow/monfix/run.py
"""
from __future__ import annotations

import contextlib
import datetime as dt
import io
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
from engine import ofsum, of_paper as P  # noqa: E402

SKIP = {"2026-11-26"}                     # Thanksgiving half day


def levels_old(D, days, i):
    """of_battery.levels as on pc 27e55f77 (before the fix)."""
    d = days[i]
    out = []
    b = D[d].bars
    on = b[b["mod"] < 570]
    if i > 0 and (dt.date.fromisoformat(d) - dt.date.fromisoformat(days[i - 1])).days <= 4:
        pb = D[days[i - 1]].bars
        pr = pb[(pb["mod"] >= 570) & (pb["mod"] < 960)]
        if len(pr):
            out += [("pdh", float(pr.high.max()), 1), ("pdl", float(pr.low.min()), -1)]
        on = pd.concat([pb[pb["mod"] >= 1080], on])
    if len(on):
        out += [("onh", float(on.high.max()), 1), ("onl", float(on.low.min()), -1)]
    return out


def load(src):
    R = {}
    for d in sorted(os.listdir(src)):
        p = os.path.join(src, d)
        if os.path.isdir(p) and os.path.exists(os.path.join(p, "of", "NQ_meta.json")):
            x = ofsum.read(p)
            if x:
                R[d] = x
    return R


def prev_old(R, B, d):
    usable = sorted(k for k in R if int(R[k]["meta"].get("rows", 0)) >= B.MIN_ROWS and k < d)
    if usable and (dt.date.fromisoformat(d) - dt.date.fromisoformat(usable[-1])).days <= 4:
        return usable[-1], R[usable[-1]]
    return None, None


def prev_new(R, B, d):
    d0, extra = dt.date.fromisoformat(d), []
    for back in range(1, 5):
        p = (d0 - dt.timedelta(days=back)).isoformat()
        if p not in R:
            continue
        if B.has_rth(B.Day(p, R[p])):
            return p, dict(R[p], extra=list(reversed(extra)))
        extra.append((p, R[p]))
    if extra:
        return extra[0][0], dict(extra[0][1], extra=list(reversed(extra[1:])))
    return None, None


def rows_for(R, days, which):
    B, _, _ = P._mods()
    keep = B.levels
    if which == "before":
        B.levels = levels_old
    try:
        out, lv = [], {}
        for d in days:
            pd_, Rp = (prev_old if which == "before" else prev_new)(R, B, d)
            if which == "before" and Rp is not None:
                Rp = {k: v for k, v in Rp.items() if k != "extra"}
            with contextlib.redirect_stdout(io.StringIO()):
                S = P.replay_summary(R[d], d, Rp, pd_, lit=[])
            out += S["rows"]
            lv[d] = {"prev": pd_, "levels": {x["name"]: x["px"] for x in S.get("levels") or []}}
        return out, lv
    finally:
        B.levels = keep


def book(rows, kind, entry):
    Rk, Uk, Xk = ("R", "usd_1", "exit_t") if entry == "v1" else ("R_e5", "usd_1_e5", "exit_t_e5")
    cand = sorted((r for r in rows if r.get("absorbed")), key=lambda r: (r["day"], r["t_sig"]))
    if kind == "first":
        cand = [r for r in cand if r.get("taken")]
    else:
        sel, open_until = [], {}
        for r in cand:
            o = open_until.get(r["day"])
            if o is not None and (o is True or o > r["t_sig"]):
                continue
            if r.get(Rk) is None and entry == "v1" and r.get("fill") is None:
                continue
            sel.append(r)
            x = r.get(Xk)
            open_until[r["day"]] = True if x is None else int(x)
        cand = sel
    return [r for r in cand if r.get(Rk) is not None], Rk, Uk


def stats(tr, Rk, Uk, days):
    n = len(tr)
    wk = len(days) / 5.0
    usd = [float(r[Uk]) for r in tr]
    Rs = [float(r[Rk]) for r in tr]
    eq, peak, dd = 0.0, 0.0, 0.0
    for u in usd:
        eq += u; peak = max(peak, eq); dd = max(dd, peak - eq)
    gw, gl = sum(u for u in usd if u > 0), -sum(u for u in usd if u < 0)
    half = days[len(days) // 2]
    h1 = [r for r in tr if r["day"] < half]; h2 = [r for r in tr if r["day"] >= half]
    m = lambda xs: round(sum(float(r[Rk]) for r in xs) / len(xs), 3) if xs else None
    return {"trades": n, "per_week": round(n / wk, 2), "win_pct": round(100 * sum(1 for x in Rs if x > 0) / n, 1) if n else None,
            "mean_R": round(sum(Rs) / n, 3) if n else None, "pf": round(gw / gl, 2) if gl else None,
            "usd_1_micro": round(sum(usd), 0), "max_dd_usd": round(dd, 0),
            "halves": {"older": {"n": len(h1), "mean_R": m(h1), "usd": round(sum(float(r[Uk]) for r in h1), 0)},
                       "newer": {"n": len(h2), "mean_R": m(h2), "usd": round(sum(float(r[Uk]) for r in h2), 0)}}}


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data", "pc_days")
    R = load(src)
    B, _, _ = P._mods()
    days = [d for d in sorted(R) if dt.date.fromisoformat(d).weekday() < 5 and d not in SKIP and B.has_rth(B.Day(d, R[d]))]
    res = {"made_from": f"{len(R)} files, {days[0]}..{days[-1]}", "trading_days": len(days), "weeks": round(len(days) / 5, 1),
           "skipped": sorted(set(R) - set(days)), "books": {}, "monday_levels": {}}
    for which in ("before", "after"):
        rows, lv = rows_for(R, days, which)
        for d in days:
            if dt.date.fromisoformat(d).weekday() == 0:
                res["monday_levels"].setdefault(d, {})[which] = lv[d]
        for kind in ("first", "onepos"):
            for entry in ("v1", "e5"):
                tr, Rk, Uk = book(rows, kind, entry)
                res["books"][f"{which}|{kind}|{entry}"] = stats(tr, Rk, Uk, days)
                if which == "after" and kind == "onepos":
                    ft = {(r["day"], r["t_sig"]) for r in book(rows, "first", entry)[0]}
                    later = [r for r in tr if (r["day"], r["t_sig"]) not in ft]
                    res["books"][f"after|onepos_later_only|{entry}"] = stats(later, Rk, Uk, days)
    json.dump(res, open(os.path.join(HERE, "results.json"), "w"), indent=1)
    for k, v in res["books"].items():
        print(f"{k:34s} n={v['trades']:3d} /wk={v['per_week']:5.2f} win={v['win_pct']} R={v['mean_R']} PF={v['pf']} "
              f"$={v['usd_1_micro']:+,.0f} DD=${v['max_dd_usd']:,.0f} halves {v['halves']['older']['mean_R']}/{v['halves']['newer']['mean_R']}")
    for d, v in res["monday_levels"].items():
        print(d, "before prev", v["before"]["prev"], sorted(v["before"]["levels"]), "| after prev", v["after"]["prev"], sorted(v["after"]["levels"]))


if __name__ == "__main__":
    main()
