"""Do the time windows add money? (research/notime/DESIGN.md). PAPER RESEARCH ONLY.
    python -X utf8 research/notime/notime.py  -> research/notime/results.json
"""
from __future__ import annotations

import collections
import copy
import datetime as dt
import json
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
OUT = os.path.join(HERE, "results.json")
SPANS = {"2021-25": ("2021-11-01", "2025-12-31"), "Jan-Jun 2026": ("2026-01-01", "2026-06-30"), "Jul-Oct 2026": ("2026-07-01", "2026-10-16")}
ACCTS = {"Builder 50K": {"target": 3000, "mll": 2000, "lock": 100, "dll": 1000, "x": 1.0},
         "Builder 25K": {"target": 1500, "mll": 1000, "lock": 100, "dll": 600, "x": 0.5},
         "Rapid EOD 25K": {"target": 1500, "mll": 1000, "lock": 100, "dll": 500, "x": 0.5, "best": 0.30, "min_days": 4}}


def evals(p, lo, A, horizon=40):
    p, lo = np.asarray(p) * A["x"], np.asarray(lo) * A["x"]
    n = len(p)
    res = []
    for i in range(n):
        bal = peak = best = 0.0
        floor = -A["mll"]; days = 0; out = "OPEN"
        for k in range(i, min(n, i + horizon)):
            dp, dl = p[k], lo[k]
            if dl <= -A["dll"]:
                dp, dl = -A["dll"], -A["dll"]
            if bal + dl <= floor:
                out = "FAIL"; break
            bal += dp; days += dp != 0; best = max(best, dp); peak = max(peak, bal)
            floor = min(max(floor, peak - A["mll"]), A["lock"])
            if bal >= A["target"] and days >= A.get("min_days", 1) and (not A.get("best") or best <= A["best"] * bal):
                out = "PASS"; break
        if n - i >= horizon or out != "OPEN":
            res.append(out)
    return {"pass": round(100 * res.count("PASS") / len(res), 1) if res else None,
            "fail": round(100 * res.count("FAIL") / len(res), 1) if res else None}


def score(daily, ntr, sessions):
    """daily: {day: (pnl, low)}; ntr: {day: trades}."""
    out = {}
    for nm, (a, z) in SPANS.items():
        ds = [d for d in sessions if a <= d <= z]
        p = np.array([daily.get(d, (0, 0))[0] for d in ds]); lo = np.array([min(daily.get(d, (0, 0))[1], 0) for d in ds])
        n = sum(ntr.get(d, 0) for d in ds)
        eq = np.cumsum(p); dd = float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min()) if len(p) else 0
        g, l = p[p > 0].sum(), -p[p < 0].sum()
        out[nm] = {"tpw": round(n / (len(ds) / 5), 2), "trades": n, "pf": round(float(g / l), 2) if l else None, "net": round(float(p.sum())),
                   "per_month": round(float(p.sum()) / (len(ds) / 21)), "max_dd": round(dd),
                   "evals": {k: evals(p, lo, A) for k, A in ACCTS.items()}}
    return out


def lit_part(sessions):
    out = {}
    for nm, run in (("today (02:00-15:30)", "lit_hours_base"), ("no window (18:00-15:30, whole day)", "lit_hours_full"),
                    ("late (02:00-15:50)", "lit_hours_late")):
        d = json.load(open(os.path.join(ROOT, "research", "runs", f"{run}.json"), encoding="utf-8"))["days"]
        out[nm] = score({r[0]: (r[1], r[2]) for r in d}, {r[0]: r[3] for r in d}, sessions)
    return out


def atlas_part(say):
    from engine import second
    from tools import second_ema as SE, second_md as SM, second_sr as SR
    SE.WINS["any"] = (0, 955)
    SM.KZ["any"] = ((1080, 1440), (0, 955))
    SR.WINDOWS["any"] = (0, 955)
    base = second.load_cfg()
    keys = ("ema_lon_vix", "macd_sweep", "sr_nyreclaim")
    def cfg_of(var):
        c = copy.deepcopy(base)
        c["strategies"] = {k: c["strategies"][k] for k in keys}
        for k in keys:
            s = c["strategies"][k]
            if var == "today":
                continue
            if k == "ema_lon_vix":
                s["entry"]["win"] = "all" if var == "day" else "any"
                if var == "any":
                    s["entry"]["reg"] = "none"
            elif k == "macd_sweep":
                s["flt"]["kz"] = "all" if var == "day" else "any"
            else:
                s["key"]["win"] = "all" if var == "day" else "any"
        return c
    d5 = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv")).drop_duplicates("time").sort_values("time").reset_index(drop=True)
    d1 = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv")).drop_duplicates("time").sort_values("time").reset_index(drop=True)
    ET = dt.timezone(dt.timedelta(hours=-5))
    months = []
    m = dt.date(2021, 11, 1)
    while m <= dt.date(2026, 10, 1):
        months.append(m)
        m = (m.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    trades = {v: collections.defaultdict(dict) for v in ("today", "day", "any")}
    t0 = time.time()
    for var in ("today", "day", "any"):
        cfg = cfg_of(var)
        for mo in months:
            nxt = (mo.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
            end = int(dt.datetime(nxt.year, nxt.month, 1, 17, 0, tzinfo=ET).timestamp()) - 86400 * 1
            end = min(end, int(d5.time.max()) + 300)
            x5 = d5[(d5.time < end) & (d5.time >= end - 86400 * 110)].reset_index(drop=True)
            x1 = d1[(d1.time < end) & (d1.time >= end - 86400 * 70)].reset_index(drop=True) if mo >= dt.date(2026, 1, 1) else None
            if len(x5) < 1000:
                continue
            try:
                r = second.run(x5, one_min=x1 if x1 is not None and len(x1) else None, now=end, cfg=cfg, lit=[])
            except Exception as ex:  # noqa: BLE001
                say(f"  {var} {mo} error {ex}")
                continue
            for k in keys:
                for t in r["strategies"][k]["trades"]:
                    if t.get("exit_kind") and t["day"][:7] == mo.isoformat()[:7]:
                        trades[var][k][t["entry_t"]] = t
        say(f"  ATLAS {var}: " + ", ".join(f"{k} {len(trades[var][k])}" for k in keys) + f" [{time.time() - t0:.0f}s]")
    return trades


def daily_of(T):
    dly, n = collections.defaultdict(lambda: [0.0, 0.0]), collections.Counter()
    for t in sorted(T, key=lambda t: t["entry_t"]):
        d = t["day"]
        u = float(t.get("usd") or 0)
        worst = -abs(float(t.get("risk_usd") or 0)) if t.get("exit_kind") == "STOP" else min(0.0, u)
        dly[d][1] = min(dly[d][1], dly[d][0] + worst)
        dly[d][0] += u
        n[d] += 1
    return {d: tuple(v) for d, v in dly.items()}, n


def one_position(T):
    out, busy = [], 0
    for t in sorted(T, key=lambda t: t["entry_t"]):
        if t["entry_t"] >= busy:
            out.append(t); busy = t["exit_t"]
    return out


def verdict(rows, a, b):
    """'a' = today, 'b' = no window."""
    w = sum(rows[a][s]["net"] > rows[b][s]["net"] for s in SPANS)
    ta, tb = sum(rows[a][s]["net"] for s in SPANS), sum(rows[b][s]["net"] for s in SPANS)
    if w >= 2 and ta > tb:
        return f"the window ADDS money (today wins {w} of 3 spans, total ${ta:,} vs ${tb:,})"
    if w <= 1 and tb > ta:
        return f"the window COSTS money (no-window wins {3 - w} of 3 spans, total ${tb:,} vs ${ta:,})"
    return f"no clear answer (today wins {w} of 3, total ${ta:,} vs ${tb:,})"


def main():
    t0 = time.time()
    say = lambda s: print(f"[{time.time() - t0:5.0f}s] {s}", flush=True)  # noqa: E731
    d = json.load(open(os.path.join(ROOT, "research", "runs", "lit_hours_base.json"), encoding="utf-8"))["days"]
    sessions = [r[0] for r in d]
    res = {"made": "2026-11-24", "design": "research/notime/DESIGN.md"}
    res["LIT"] = lit_part(sessions)
    res["LIT_verdict"] = verdict(res["LIT"], "today (02:00-15:30)", "no window (18:00-15:30, whole day)")
    say("LIT: " + res["LIT_verdict"])
    T = atlas_part(say)
    names = {"ema_lon_vix": "ATLAS EMA", "macd_sweep": "ATLAS MACD", "sr_nyreclaim": "ATLAS S/R"}
    WORD = {"today": "today", "day": "day (02:00-15:30)", "any": "any time (00:00-15:55)"}
    for k, nm in names.items():
        rows = {}
        for var in ("today", "day", "any"):
            dl, n = daily_of(list(T[var][k].values()))
            rows[WORD[var]] = score(dl, n, sessions)
        res[nm] = rows
        res[nm + "_verdict"] = verdict(rows, "today", "any time (00:00-15:55)")
        res[nm + "_verdict_day"] = verdict(rows, "today", "day (02:00-15:30)")
        say(f"{nm}: {res[nm + '_verdict']} | vs day: {res[nm + '_verdict_day']}")
    rows = {}
    for var in ("today", "day", "any"):
        allT = one_position([t for k in names for t in T[var][k].values()])
        dl, n = daily_of(allT)
        rows[WORD[var]] = score(dl, n, sessions)
    res["ATLAS (3 members, one position)"] = rows
    res["ATLAS_verdict"] = verdict(rows, "today", "any time (00:00-15:55)")
    say("ATLAS book: " + res["ATLAS_verdict"])
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)
    for key in ["LIT", "ATLAS EMA", "ATLAS MACD", "ATLAS S/R", "ATLAS (3 members, one position)"]:
        for v, r in res[key].items():
            say(f"{key:30s} {v:36s} " + " | ".join(
                f"{s}: {r[s]['tpw']}/wk PF {r[s]['pf']} ${r[s]['net']:,} (${r[s]['per_month']:,}/mo) DD ${r[s]['max_dd']:,} "
                f"50K {r[s]['evals']['Builder 50K']['pass']}/{r[s]['evals']['Builder 50K']['fail']}" for s in SPANS))
    say(f"-> {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()
