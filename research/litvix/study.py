"""LIT by VIX x 20-day trend x direction, the 7-loser streak odds, and the 2 pre-registered rules (research/litvix/DESIGN.md).
PAPER RESEARCH ONLY.   python -X utf8 research/litvix/study.py  -> research/litvix/results.json
"""
from __future__ import annotations

import bisect
import collections
import csv
import datetime as dt
import json
import os
import random
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from tools import stops_targets_time as STT  # noqa: E402
from tools import lit_edge as E  # noqa: E402
from tools import livegap as LG  # noqa: E402

OUT = os.path.join(HERE, "results.json")
SPANS = ("2021-25", "H1", "H2")
PV, COMM = 2.0, 1.40


def span_of(d):
    return "H1" if "2026-01-01" <= d <= "2026-06-30" else "H2" if d >= "2026-07-01" else "2021-25"


def vix_prior():
    rows = list(csv.DictReader(open(os.path.join(ROOT, "data", "VIX_1d.csv"), encoding="utf-8")))
    ds = [r["date"] for r in rows]
    cl = [float(r["close"]) for r in rows]
    def f(day):
        k = bisect.bisect_left(ds, day) - 1
        return cl[k] if k >= 0 else None
    return f


def trend_prior():
    rows = list(csv.DictReader(open(os.path.join(ROOT, "data", "NQ_1d.csv"), encoding="utf-8")))
    ds = [dt.datetime.fromtimestamp(int(r["time"]), dt.timezone.utc).strftime("%Y-%m-%d") for r in rows]
    cl = [float(r["close"]) for r in rows]
    def f(day):
        k = bisect.bisect_left(ds, day) - 1
        if k < 20:
            return None
        ret = cl[k] / cl[k - 20] - 1
        return "down" if ret < -0.03 else "up" if ret > 0.03 else "flat"
    return f


def band(v):
    return None if v is None else "VIX <15" if v < 15 else "VIX 15-20" if v < 20 else "VIX 20-25" if v < 25 else "VIX 25+"


def units_all():
    """lit_live units (to 2026-10-16) + the livegap twin after (PC bars), all in stops_targets_time unit shape."""
    U = STT.units()
    last = max(u["day"] for u in U)
    tw, _ = LG.lit_twin(since="2026-10-12")
    for t in tw:
        if t["day"] > last:
            U.append({"day": t["day"], "entry_t": t["entry_t"], "exit_t": t["entry_t"] + 3600, "dir": t["dir"], "exit": t["exit"],
                      "risk": t["risk"], "risk0": t["risk"], "tgt": t["tgt"], "pts": t["pts"], "w1": t["w1"], "legs": [(1.0, t["pts"])],
                      "mfe": None, "tf": 1, "m": 1.0, "src": "ext", "struct_hit": False, "live_exit": t["exit"], "live_pts": t["pts"],
                      "live_qty": t["lit_qty"], "late_twin": True})
    return sorted(U, key=lambda u: u["entry_t"])


def stats(L):
    if not L:
        return {"n": 0}
    p = np.array([l["pnl"] for l in L])
    gl = -p[p < 0].sum()
    days = sorted({l["day"] for l in L})
    months = max(1.0, (dt.date.fromisoformat(days[-1]) - dt.date.fromisoformat(days[0])).days / 30.4)
    return {"n": len(L), "win": round(100 * float((p > 0).mean()), 1), "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None,
            "net": round(float(p.sum())), "avg": round(float(p.mean())), "per_month_in_bucket": round(float(p.sum()) / months),
            "longest_no_win": longest(L)}


def longest(L):
    best = cur = 0
    for l in sorted(L, key=lambda l: l["entry_t"]):
        cur = cur + 1 if l["pnl"] <= 0 else 0
        best = max(best, cur)
    return best


def streaks(L, k=7, draws=10000, seed=7):
    seq = [l["pnl"] > 0 for l in sorted(L, key=lambda l: l["entry_t"])]
    runs, cur = [], 0
    for w in seq + [True]:
        if not w:
            cur += 1
        else:
            if cur:
                runs.append(cur)
            cur = 0
    out = {"runs_7plus": sum(r >= k for r in runs), "longest": max(runs) if runs else 0,
           "runs_by_len": dict(sorted(collections.Counter(runs).items()))}
    for sp in SPANS:
        S = [l for l in L if span_of(l["day"]) == sp]
        w = float(np.mean([l["pnl"] > 0 for l in S]))
        out[f"win_rate_{sp}"] = round(100 * w, 1)
        out[f"p_7_straight_no_win_{sp}"] = round(100 * (1 - w) ** k, 2)
    rnd = random.Random(seed)
    S26 = [l["pnl"] > 0 for l in L if l["day"] >= "2026-01-01" and not l.get("late_twin")]
    n_year = int(round(len(S26) / (len([1 for l in L if "2026-01-01" <= l["day"] <= "2026-10-16"]) or 1) * 0 + 125))
    hit = 0
    for _ in range(draws):
        s = [rnd.choice(S26) for _ in range(n_year)]
        c = b = 0
        for x in s:
            c = 0 if x else c + 1
            b = max(b, c)
        hit += b >= k
    out["p_a_7_run_in_a_year_of_trades_at_2026_rates"] = round(100 * hit / draws, 1)
    out["year_of_trades"] = n_year
    return out


def run(say=print):
    U = units_all()
    vf, tf = vix_prior(), trend_prior()
    L = STT.size_matched(U)
    for l in L:
        l["vix"] = vf(l["day"])
        l["band"] = band(l["vix"])
        l["trend"] = tf(l["day"])
        l["with"] = None if l["trend"] in (None, "flat") else ("with" if (l["dir"] > 0) == (l["trend"] == "up") else "against")
        l["span"] = span_of(l["day"])
    res = {"made": "2026-11-24", "design": "research/litvix/DESIGN.md", "n": len(L), "last_day": L[-1]["day"]}
    T = {}
    for sp in SPANS + ("all",):
        S = [l for l in L if sp == "all" or l["span"] == sp]
        T[sp] = {
            "all": stats(S),
            "band": {b: stats([l for l in S if l["band"] == b]) for b in ("VIX <15", "VIX 15-20", "VIX 20-25", "VIX 25+")},
            "band_x_trend": {f"{b} | {t}": stats([l for l in S if l["band"] == b and l["trend"] == t])
                             for b in ("VIX 20-25", "VIX 25+") for t in ("down", "flat", "up")},
            "trend_x_dir": {f"{t} | {'long' if d > 0 else 'short'}": stats([l for l in S if l["trend"] == t and l["dir"] == d])
                            for t in ("down", "flat", "up") for d in (1, -1)},
            "vix25_down_x_dir": {("long" if d > 0 else "short"): stats([l for l in S if l["band"] == "VIX 25+" and l["trend"] == "down"
                                                                        and l["dir"] == d]) for d in (1, -1)}}
    res["tables"] = T
    res["live_window"] = stats([l for l in L if "2026-10-19" <= l["day"] <= "2026-11-20"])
    res["live_window_tags"] = [{k: l.get(k) for k in ("day", "dir", "band", "vix", "trend", "pnl", "exit")}
                               for l in L if "2026-10-19" <= l["day"] <= "2026-11-20"]
    res["streaks"] = streaks([l for l in L if not l.get("late_twin")])
    # rules
    base_E = E.eval_path(U)
    def eval_of(U2):
        Ev = E.eval_path(U2)
        return {sp: {k: Ev[sp].get(k) for k in ("n", "net", "p10", "f10", "pass_med")} for sp in ("H1", "H2")}
    base = {"spans": {sp: STT.stats(L, sp) for sp in STT.SPANS}, "eval50": eval_of(U)}
    res["base"] = base
    tags = {l["entry_t"]: l for l in L}
    for name, fn in (("V1 longs off when VIX > 25 and 20-day trend down", lambda l: l["dir"] > 0),
                     ("V2 all LIT off when VIX > 25 and 20-day trend down", lambda l: True)):
        hit = {e for e, l in tags.items() if l["vix"] is not None and l["vix"] > 25 and l["trend"] == "down" and fn(l)}
        U2 = [u for u in U if u["entry_t"] not in hit]
        L2 = STT.size_matched(U2)
        o = {"skipped": {sp: sum(1 for e in hit if tags[e]["span"] == sp) for sp in SPANS},
             "skipped_usd": {sp: round(sum(tags[e]["pnl"] for e in hit if tags[e]["span"] == sp)) for sp in SPANS},
             "spans": {sp: STT.stats(L2, sp) for sp in STT.SPANS}, "eval50": eval_of(U2)}
        why = []
        for sp in STT.SPANS:
            a, b = o["spans"][sp], base["spans"][sp]
            if a["net"] <= b["net"]:
                why.append(f"{sp} net ${a['net']:,} vs ${b['net']:,}")
            if (a["pf"] or 0) < (b["pf"] or 0):
                why.append(f"{sp} PF {a['pf']} vs {b['pf']}")
            if a["tpw"] < 2:
                why.append(f"{sp} {a['tpw']} trades/week")
        for sp in ("H1", "H2"):
            if (o["eval50"][sp]["net"] or 0) < (base["eval50"][sp]["net"] or 0):
                why.append(f"{sp} 50K eval ${o['eval50'][sp]['net']:,.0f} vs ${base['eval50'][sp]['net']:,.0f}")
            if (o["eval50"][sp]["f10"] or 0) > (base["eval50"][sp]["f10"] or 0):
                why.append(f"{sp} 2-week fails {o['eval50'][sp]['f10']} vs {base['eval50'][sp]['f10']}")
        k = len(hit)
        g = -sum(tags[e]["pnl"] for e in hit)
        rnd = random.Random(7)
        pool = [l["pnl"] for l in L if l["day"] <= "2026-10-16"]
        o["placebo_p"] = round(sum(-sum(rnd.sample(pool, k)) >= g for _ in range(2000)) / 2000, 4) if k else None
        if o["placebo_p"] is None or o["placebo_p"] >= 0.025:
            why.append(f"placebo p {o['placebo_p']} (bar 0.025)")
        o["verdict"] = "needs-owner-yes" if not why else "FAIL (variance, not a rule)"
        o["why"] = why
        res[name] = o
        say(f"{name}: {o['verdict']} | skipped {o['skipped']} ${o['skipped_usd']} | " + "; ".join(why))
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)
    return res


if __name__ == "__main__":
    R = run()
    for sp in SPANS + ("all",):
        t = R["tables"][sp]
        print(f"== {sp}: all {t['all']}")
        for k in ("band", "band_x_trend", "trend_x_dir", "vix25_down_x_dir"):
            for b, s in t[k].items():
                if s.get("n"):
                    print(f"   {k:16s} {b:22s} n{s['n']:4d} win {s['win']:5.1f} PF {s['pf']} net ${s['net']:,} ${s['per_month_in_bucket']:,}/mo-in-bucket streak {s['longest_no_win']}")
    print("live window:", R["live_window"])
    for x in R["live_window_tags"]:
        print("  ", x)
    print("streaks:", R["streaks"])
