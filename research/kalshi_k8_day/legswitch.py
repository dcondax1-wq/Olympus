"""The per-leg OFF / ON rule, walk-forward on the public tape: EXACTLY PREREG_legswitch.md (committed before this ran).

    python research/kalshi_k8_day/legswitch.py   -> research/kalshi_k8_day/legswitch.json + plain lines
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import kalshi_k8_feed as F  # noqa: E402
from engine import kalshi_clock as KC, kalshi_legswitch as LS  # noqa: E402

OUT = os.path.join(HERE, "legswitch.json")
FIND = (dt.date(2026, 8, 3), dt.date(2026, 10, 21))
CHECK = (dt.date(2026, 10, 22), dt.date(2026, 11, 20))
RULES = {"main": LS.RULE, "n10": {"n": 10, "pause_at": 4, "resume_at": 6}, "n30": {"n": 30, "pause_at": 15, "resume_at": 18}}


def windows(T, lid, last):
    """Every settled weekday window of the leg (bet or not): [(day, won)] in time order."""
    L = KC.LEG[lid]
    out, d = [], FIRST
    while d <= last:
        if d.weekday() < 5 and not KC.skipped(L, d):
            rec = T.get(KC.ticker(L["series"], KC.leg_open(L, d)))
            if rec and rec.get("res") in ("yes", "no"):
                out.append((d, rec["res"] == L["side"]))
        d += dt.timedelta(days=1)
    return out


FIRST = dt.date(2026, 8, 3)


def run(T, rule, legs):
    bets = {(r["leg"], r["day"]): r for r in F.bets(T, last=CHECK[1], legs=legs)}
    out = {"kept": [], "skipped": []}
    per_leg = {}
    for lid in legs:
        ws = windows(T, lid, CHECK[1])
        paused = False
        n_pause = 0
        for i, (d, _) in enumerate(ws):
            hist = [w for _, w in ws[:i]]              # windows BEFORE this day only
            paused = LS.decide([1 if w else 0 for w in hist], paused, rule)["paused"]
            n_pause += paused
            b = bets.get((lid, d))
            if b:
                (out["skipped"] if paused else out["kept"]).append(b)
        per_leg[lid] = {"windows": len(ws), "paused_days": n_pause}
    return out, per_leg


def summ(rs, lo, hi):
    x = [r for r in rs if lo <= r["day"] <= hi]
    return {"n": len(x), "won": sum(r["won"] for r in x), "net": round(sum(r["pnl"] for r in x), 2)}


def main():
    T = F.tape()
    live = KC.load_config()[0]["live_legs"]
    res = {"prereg": "research/kalshi_k8_day/PREREG_legswitch.md", "rules": {}}
    for name, rule in RULES.items():
        for group, legs in (("live3", live), ("all5", list(KC.LEG))):
            o, per = run(T, rule, legs)
            r = {h: {"skipped": summ(o["skipped"], *p), "kept": summ(o["kept"], *p)} for h, p in (("find", FIND), ("check", CHECK))}
            r["legs"] = per
            res["rules"][f"{name}:{group}"] = r
    m = res["rules"]["main:live3"]
    passed = m["find"]["skipped"]["n"] > 0 and m["check"]["skipped"]["n"] > 0 and m["find"]["skipped"]["net"] < 0 and m["check"]["skipped"]["net"] < 0
    res["verdict"] = "ON" if passed else "OFF for live (display only)"
    res["plain"] = (f"Main rule on the 3 live legs: it would have skipped {m['find']['skipped']['n']} bets in Aug 3-Oct 21 "
                    f"({m['find']['skipped']['won']} won, {m['find']['skipped']['net']:+.2f} $) and {m['check']['skipped']['n']} in Oct 22-Nov 20 "
                    f"({m['check']['skipped']['won']} won, {m['check']['skipped']['net']:+.2f} $). Verdict: {res['verdict']}.")
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1)
    print(res["plain"])
    for k, v in res["rules"].items():
        print(k, {h: v[h] for h in ("find", "check")})
    return 0


if __name__ == "__main__":
    sys.exit(main())
