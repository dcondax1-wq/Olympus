"""LOSS ANATOMY across the bots + 2 untested loss cuts (2026-11-20 night-payday; design research/lab/payday_design_2026-11-20.md,
fixed before this ran). PAPER RESEARCH ONLY: reads research/anatomy/trades_lit.json / trades_atlas.json (tools/win_loss_anatomy.py
build: the live-loop LIT backtest at the LIT size, ATLAS members after the account-B rules at $250 a trade, costs in) and writes
research/lab/payday_losses.json. The Rapid lanes trade these same signals (only their size differs), so their losses are these.

  C1 atlas-after-lit-loss  no new ATLAS entry once a Zlarior trade CLOSED at a loss earlier that day (any side)
  C2 lit-after-atlas-loss  no new Zlarior entry once an ATLAS trade CLOSED at a loss earlier that day

    python -X utf8 tools/payday_losses.py            # ~5 s (plain stats); --seat adds the ATLAS funded 25K Monte Carlo for C1
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "research", "lab", "payday_losses.json")
SPAN = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-10-16"), "2021-25": ("2021-11-01", "2025-12-31")}
SPANS = ("H1", "H2", "2021-25")


def load(bot):
    d = json.load(open(os.path.join(ROOT, "research", "anatomy", f"trades_{bot}.json"), encoding="utf-8"))
    return [dict(zip(d["cols"], r)) for r in d["rows"]]


def weeks(sp):
    a, z = (dt.date.fromisoformat(x) for x in SPAN[sp])
    return ((z - a).days + 1) / 7.0


def stats(rows, sp):
    rows = sorted((r for r in rows if r["span"] == sp), key=lambda r: r["entry_t"])
    usd = [float(r["usd"]) for r in rows]
    w, l = sum(x for x in usd if x > 0), -sum(x for x in usd if x < 0)
    eq = pk = dd = 0.0
    for x in usd:
        eq += x
        pk = max(pk, eq)
        dd = min(dd, eq - pk)
    wk = weeks(sp)
    return {"n": len(rows), "tpw": round(len(rows) / wk, 2), "pf": round(w / l, 2) if l else None, "net": round(sum(usd)),
            "per_month": round(sum(usd) / (wk / (52.0 / 12.0))), "dd": round(dd), "win_pct": round(100.0 * sum(1 for x in usd if x > 0) / max(1, len(usd)), 1),
            "avg_r": round(sum(float(r["r"]) for r in rows) / max(1, len(rows)), 3)}


# ================================================================================================ where the losses sit
def stop_bucket(rows):
    xs = sorted(float(r["risk_pts"]) for r in rows)
    t1, t2 = xs[len(xs) // 3], xs[2 * len(xs) // 3]
    return lambda r: f"stop < {t1:g} pts" if r["risk_pts"] < t1 else f"stop {t1:g}-{t2:g} pts" if r["risk_pts"] < t2 else f"stop >= {t2:g} pts"


DIMS = {
    "session": lambda r: r["session"],
    "weekday": lambda r: r["dow"],
    "news day (Tier-1)": lambda r: "news day" if r["news_day"] else "no news",
    "news inside the trade": lambda r: "release inside" if r["news_in"] else "none inside",
    "VIX": lambda r: r["vix_band"],
}


def clusters(rows, bot):
    dims = dict(DIMS)
    dims["stop size"] = stop_bucket(rows)
    if bot == "atlas":
        dims["member"] = lambda r: r["member"]
    out = {}
    avg = {sp: sum(float(r["r"]) for r in rows if r["span"] == sp) / max(1, sum(1 for r in rows if r["span"] == sp)) for sp in SPANS}
    for dn, f in dims.items():
        b = collections.defaultdict(lambda: {sp: [] for sp in SPANS})
        for r in rows:
            b[f(r)][r["span"]].append(r)
        cells = []
        for key, by in b.items():
            c = {"bucket": key}
            worse = True
            for sp in SPANS:
                rs = by[sp]
                lu = -sum(float(r["usd"]) for r in rs if float(r["usd"]) < 0)
                tot_l = -sum(float(r["usd"]) for r in rows if r["span"] == sp and float(r["usd"]) < 0)
                ar = sum(float(r["r"]) for r in rs) / len(rs) if rs else None
                c[sp] = {"n": len(rs), "loss_share": round(100.0 * lu / tot_l, 1) if tot_l else None,
                         "trade_share": round(100.0 * len(rs) / max(1, sum(1 for r in rows if r["span"] == sp)), 1),
                         "avg_r": round(ar, 3) if ar is not None else None, "net": round(sum(float(r["usd"]) for r in rs))}
                if ar is None or ar >= avg[sp] or (sp != "2021-25" and len(rs) < 5):
                    worse = False
            c["worse_everywhere"] = worse
            cells.append(c)
        cells.sort(key=lambda c: -(c["H2"]["loss_share"] or 0))
        out[dn] = cells
    return out, {sp: round(a, 3) for sp, a in avg.items()}


def same_day(lit, atl):
    """Days both bots traded: how often both lost, and ATLAS's R on Zlarior's losing vs winning days (2026 / 2021-25)."""
    L = collections.defaultdict(list)
    for r in lit:
        L[r["day"]].append(r)
    out = {}
    for sp in SPANS:
        a = [r for r in atl if r["span"] == sp and r["day"] in L]
        on_lose = [float(r["r"]) for r in a if sum(float(x["usd"]) for x in L[r["day"]]) < 0]
        on_win = [float(r["r"]) for r in a if sum(float(x["usd"]) for x in L[r["day"]]) > 0]
        days = {r["day"] for r in a}
        both = sum(1 for d in days if sum(float(x["usd"]) for x in L[d]) < 0
                   and sum(float(r["usd"]) for r in a if r["day"] == d) < 0)
        out[sp] = {"days_both_traded": len(days), "days_both_lost": both,
                   "atlas_r_on_lit_losing_days": round(sum(on_lose) / len(on_lose), 3) if on_lose else None, "n_lose": len(on_lose),
                   "atlas_r_on_lit_winning_days": round(sum(on_win) / len(on_win), 3) if on_win else None, "n_win": len(on_win)}
    return out


# ================================================================================================ the two loss cuts
def cut(trades, others, thr=0.0):
    """Drop a trade when an `others` trade on the same day closed at a loss (usd < -thr) before its entry."""
    by = collections.defaultdict(list)
    for o in others:
        if float(o["usd"]) < -thr:
            by[o["day"]].append(int(o["exit_t"]))
    keep, cutl = [], []
    for t in trades:
        (cutl if any(x <= int(t["entry_t"]) for x in by.get(t["day"], ())) else keep).append(t)
    return keep, cutl


def judge_cut(today, new, cutl, bot):
    """The design's bar: net up AND max DD not worse in every required period (C2 / LIT: H1 pick + H2 check + 2021-25 not
    worse; C1 / ATLAS: H1, H2 and 2021-25), >= 5 cut trades in each 2026 half, 2-4 trades a week kept (LIT)."""
    why, ok = [], True
    for sp in SPANS:
        a, b = today[sp], new[sp]
        nc = sum(1 for t in cutl if t["span"] == sp)
        if sp != "2021-25" and nc < 5:
            ok = False
            why.append(f"{sp}: only {nc} trades cut (too few to judge)")
        if b["net"] <= a["net"] and not (bot == "lit" and sp == "2021-25" and b["net"] >= a["net"]):
            ok = False
            why.append(f"{sp}: net ${a['net']:,} -> ${b['net']:,}")
        if b["dd"] < a["dd"]:
            ok = False
            why.append(f"{sp}: max DD ${a['dd']:,} -> ${b['dd']:,}")
        if bot == "lit" and sp != "2021-25" and not 2.0 <= b["tpw"] <= 4.0:
            ok = False
            why.append(f"{sp}: {b['tpw']} trades a week")
    return ok, why


def seat_c1(n=1000):
    """C1 on the ATLAS funded 25K from today (tools/money/payday_plan.a25_seat with ATLAS's trades cut): first payout, lost."""
    sys.path.insert(0, os.path.join(ROOT, "tools", "money"))
    import payday_plan as PDP
    MP = PDP.MP
    B = MP.by()
    BYa = []
    for i, ts in enumerate(B["A"]):
        lx = [int(t["exit_t"]) for t in B["L"][i] if float(t["pts"]) < 0]
        BYa.append([t for t in ts if not any(x <= int(t["entry_t"]) for x in lx)])
    cut_n = sum(len(a) - len(b) for a, b in zip(B["A"], BYa))
    S = PDP.SA.data()["S"]
    cal = PDP.calendar()
    out = {"cut_trades_all_sessions": cut_n}
    for sp in PDP.SPANS:
        paths = PDP.U.mc_paths(S, sp, n, length=PDP.LEN, seed=PDP.BL.A4.SEED_LIFE)
        R0 = PDP.run(paths, {"A25": PDP.a25_seat})
        R1 = PDP.run(paths, {"A25": lambda: PDP.a25_seat(BYa=BYa)})
        out[sp] = {"today": PDP.acct(R0["A25"], cal, "A25")[0], "c1": PDP.acct(R1["A25"], cal, "A25")[0]}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--seat", action="store_true")
    ap.add_argument("--n", type=int, default=1000)
    a = ap.parse_args(argv)
    lit, atl = load("lit"), load("atlas")
    res = {"v": 1, "date": "2026-11-20", "design": "research/lab/payday_design_2026-11-20.md", "built_by": "tools/payday_losses.py",
           "source": "research/anatomy/trades_lit.json + trades_atlas.json (tools/win_loss_anatomy.py build 2026-11-19)",
           "bots": {}, "cuts": {}}
    for bot, rows in (("lit", lit), ("atlas", atl)):
        cl, avg = clusters(rows, bot)
        res["bots"][bot] = {"today": {sp: stats(rows, sp) for sp in SPANS}, "avg_r": avg, "clusters": cl,
                            "worse_everywhere": [f"{dn}: {c['bucket']}" for dn, cs in cl.items() for c in cs if c["worse_everywhere"]]}
    res["same_day"] = same_day(lit, atl)
    for cid, bot, rows, others in (("C1 atlas-after-lit-loss", "atlas", atl, lit), ("C2 lit-after-atlas-loss", "lit", lit, atl)):
        keep, cutl = cut(rows, others)
        today = res["bots"][bot]["today"]
        new = {sp: stats(keep, sp) for sp in SPANS}
        ok, why = judge_cut(today, new, cutl, bot)
        cut_by = {sp: {"n": sum(1 for t in cutl if t["span"] == sp), "net": round(sum(float(t["usd"]) for t in cutl if t["span"] == sp)),
                       "avg_r": round(sum(float(t["r"]) for t in cutl if t["span"] == sp) / max(1, sum(1 for t in cutl if t["span"] == sp)), 3)}
                  for sp in SPANS}
        # post-hoc sensitivity (labelled, never the verdict): only a REAL loss (<= -0.5R) triggers the cut
        keep2, cutl2 = cut(rows, [o for o in others if float(o["r"]) <= -0.5])
        res["cuts"][cid] = {"bot": bot, "today": today, "with_cut": new, "cut_trades": cut_by, "pass": ok, "why": why,
                            "sensitivity_real_loss_only": {sp: {"net": stats(keep2, sp)["net"], "cut": sum(1 for t in cutl2 if t["span"] == sp)}
                                                           for sp in SPANS}}
        print(cid, "PASS" if ok else "no", why, cut_by)
    if a.seat:
        res["cuts"]["C1 atlas-after-lit-loss"]["a25_seat"] = seat_c1(a.n)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)
    for bot in ("lit", "atlas"):
        print(bot, res["bots"][bot]["today"], "\n  worse in all 3 periods:", res["bots"][bot]["worse_everywhere"])
    print(json.dumps(res["same_day"]))
    print("wrote", os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
