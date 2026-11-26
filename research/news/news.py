"""News-day playbook (research/news/DESIGN.md). PAPER RESEARCH ONLY.
    python -X utf8 research/news/news.py   -> research/news/results.json
"""
from __future__ import annotations

import collections
import csv
import datetime as dt
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
for p in ("research/moretrades", "research/blitzv2"):
    sys.path.insert(0, os.path.join(ROOT, p))
os.chdir(ROOT)
from tools import scalp_na_lib as N  # noqa: E402
import moretrades as MT  # noqa: E402
import blitzv2 as BZ  # noqa: E402

TICK, PV, COMM, USD = 0.25, 2.0, 1.90, 250.0
COSTS = {"base": (6, 2), "stress": (12, 4)}
SPANS = {"2021-25": ("2021-11-01", "2025-12-31"), "2026 H1": ("2026-01-01", "2026-06-30"), "2026 Jul-Nov20": ("2026-07-01", "2026-11-20")}


# ------------------------------------------------------------------------------------------------ calendar
def calendar():
    ev = collections.defaultdict(set)
    for r in csv.DictReader(open("data/news/events.csv", encoding="utf-8")):
        e, d = r["event"], r["date"]
        if e.startswith("CPI"):
            ev[d].add("CPI")
        elif e.startswith("Non-Farm Payrolls"):
            ev[d].add("NFP")
        elif e.startswith("PPI"):
            ev[d].add("PPI")
        elif e.startswith("FOMC rate decision"):
            ev[d].add("FOMC")
        elif r["impact"] == "high":
            ev[d].add("other")
    have_nfp = {d[:7] for d, s in ev.items() if "NFP" in s}
    m = dt.date(2021, 11, 1)
    while m <= dt.date(2023, 12, 1):
        if m.isoformat()[:7] not in have_nfp:
            d = m + dt.timedelta(days=(4 - m.weekday()) % 7)
            ev[d.isoformat()].add("NFP_rule")
        m = (m.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    return ev


# ------------------------------------------------------------------------------------------------ bars
class Day:
    def __init__(self, B):
        self.B = B
        self.idx = collections.defaultdict(list)
        for i, d in enumerate(B["dates"][B["day"]]):
            self.idx[d].append(i)
        self.dates = sorted(self.idx)
        self.pos = {d: k for k, d in enumerate(self.dates)}

    def bar_at(self, d, mod):
        for i in self.idx.get(d, []):
            if self.B["mod"][i] == mod:
                return i
        return None

    def window(self, d, a, z):
        return [i for i in self.idx.get(d, []) if a <= self.B["mod"][i] < z]

    def prev(self, d):
        k = self.pos.get(d)
        return self.dates[k - 1] if k else None

    def overnight(self, d):
        p = self.prev(d)
        I = ([i for i in self.idx.get(p, []) if self.B["mod"][i] >= 1080] if p else []) + self.window(d, 0, 510)
        if not I:
            return None
        return float(self.B["h"][I].max()), float(self.B["l"][I].min())

    def prior_rth(self, d):
        p = self.prev(d)
        I = self.window(p, 570, 960) if p else []
        return (float(self.B["h"][I].max()), float(self.B["l"][I].min())) if I else None


def walk(B, j, D, stop, tg, flat_mod, cost):
    """one trade from bar j's open; -> dict or None. cost = (entry ticks, exit ticks on stop / market)."""
    o, h, l, c, mod = B["o"], B["h"], B["l"], B["c"], B["mod"]
    ke, kx = cost
    fill = float(o[j]) + D * ke * TICK
    risk = D * (fill - stop)
    if risk < 4 * TICK:
        return None
    day = B["day"][j]
    mae = 0.0
    i = j
    while i < len(o) and B["day"][i] == day:
        if mod[i] >= flat_mod:
            xp, kind = float(o[i]) - D * kx * TICK, "time"; break
        if i > j and ((D > 0 and o[i] <= stop) or (D < 0 and o[i] >= stop)):
            xp, kind = float(o[i]) - D * kx * TICK, "stop"; break
        if (D > 0 and l[i] <= stop) or (D < 0 and h[i] >= stop):
            xp, kind = stop - D * kx * TICK, "stop"; break
        mae = max(mae, (fill - l[i]) if D > 0 else (h[i] - fill))
        if tg is not None and ((D > 0 and h[i] >= tg) or (D < 0 and l[i] <= tg)):
            xp, kind = tg, "target"; break
        i += 1
    else:
        i -= 1
        xp, kind = float(c[i]) - D * kx * TICK, "eod"
    pts = D * (xp - fill)
    rpm = (risk + TICK) * PV + COMM
    q = max(1, int(USD / rpm))
    return {"entry_t": int(B["t"][j]), "exit_t": int(B["t"][i]) + 300, "dir": D, "risk_pts": risk, "pts": pts, "exit": kind,
            "pnl": q * (pts * PV - COMM), "low": min(0.0, q * (-max(mae, D * (fill - xp)) * PV - COMM)), "r": (pts * PV - COMM) / rpm}


def first_close_beyond(B, I, hi, lo):
    for i in I:
        if B["c"][i] > hi:
            return i, 1
        if B["c"][i] < lo:
            return i, -1
    return None, 0


def play(name, DY, d, cost):
    B = DY.B
    if name in ("N1", "N2", "N3", "N4"):
        r0 = DY.bar_at(d, 510)
        if r0 is None:
            return None
        if name == "N1":
            hi, lo = B["h"][r0], B["l"][r0]
            i, D = first_close_beyond(B, DY.window(d, 515, 565), hi, lo)
            if not D or i + 1 >= len(B["o"]):
                return None
            return walk(B, i + 1, D, (lo - TICK) if D > 0 else (hi + TICK), None, 630, cost) if False else \
                _rr(B, i + 1, D, (lo - TICK) if D > 0 else (hi + TICK), 2.0, 630, cost)
        if name == "N2":
            W = DY.window(d, 510, 525)
            if len(W) < 3:
                return None
            hi, lo = B["h"][W].max(), B["l"][W].min()
            i, D = first_close_beyond(B, DY.window(d, 525, 585), hi, lo)
            if not D:
                return None
            return _rr(B, i + 1, D, (lo - TICK) if D > 0 else (hi + TICK), 2.0, 690, cost)
        if name == "N3":
            on = DY.overnight(d)
            W = DY.window(d, 510, 525)
            if not on or len(W) < 3:
                return None
            hi, lo = B["h"][W].max(), B["l"][W].min()
            took_h, took_l = hi > on[0], lo < on[1]
            if took_h == took_l:
                return None
            mid = (on[0] + on[1]) / 2
            for i in DY.window(d, 525, 570):
                if took_h and B["c"][i] < on[0]:
                    return _cap(B, i + 1, -1, hi + TICK, mid, 3.0, 690, cost)
                if took_l and B["c"][i] > on[1]:
                    return _cap(B, i + 1, 1, lo - TICK, mid, 3.0, 690, cost)
            return None
        if name == "N4":
            body = B["c"][r0] - B["o"][r0]
            if abs(body) < 0.5 * B["atr5"][r0] or r0 + 1 >= len(B["o"]):
                return None
            D = 1 if body > 0 else -1
            return walk(B, r0 + 1, D, (B["l"][r0] - TICK) if D > 0 else (B["h"][r0] + TICK), None, 570, cost)
    W = DY.window(d, 840, 870)
    if len(W) < 5:
        return None
    hi, lo = B["h"][W].max(), B["l"][W].min()
    if name == "N5":
        i, D = first_close_beyond(B, DY.window(d, 870, 915), hi, lo)
        if not D:
            return None
        return _rr(B, i + 1, D, (lo - TICK) if D > 0 else (hi + TICK), 2.0, 955, cost)
    if name == "N6":
        P = DY.window(d, 570, 840)
        if len(P) < 10:
            return None
        ph, pl = B["h"][P].max(), B["l"][P].min()
        took_h, took_l = hi > ph, lo < pl
        if took_h == took_l:
            return None
        mid = (ph + pl) / 2
        for i in DY.window(d, 870, 915):
            if took_h and B["c"][i] < ph:
                return _cap(B, i + 1, -1, hi + TICK, mid, 3.0, 955, cost)
            if took_l and B["c"][i] > pl:
                return _cap(B, i + 1, 1, lo - TICK, mid, 3.0, 955, cost)
    return None


def _rr(B, j, D, stop, rr, flat, cost):
    if j >= len(B["o"]):
        return None
    fill = float(B["o"][j]) + D * cost[0] * TICK
    return walk(B, j, D, stop, fill + D * rr * D * (fill - stop) * D if False else fill + D * rr * abs(fill - stop), flat, cost)


def _cap(B, j, D, stop, tgt, cap, flat, cost):
    if j >= len(B["o"]):
        return None
    fill = float(B["o"][j]) + D * cost[0] * TICK
    risk = D * (fill - stop)
    if risk <= 0 or D * (tgt - fill) <= 0:
        return None
    return walk(B, j, D, stop, fill + D * min(D * (tgt - fill), cap * risk), flat, cost)


# ------------------------------------------------------------------------------------------------ measurement
def measure(DY, days, at):
    B = DY.B
    out = collections.defaultdict(list)
    for d in days:
        r0 = DY.bar_at(d, at)
        if r0 is None:
            continue
        W = DY.window(d, at, at + 60)
        if len(W) < 10:
            continue
        rng = B["h"][W].max() - B["l"][W].min()
        D = 1 if B["c"][r0] >= B["o"][r0] else -1
        a5 = B["atr5"][r0 - 1] if r0 else B["atr5"][r0]
        o0 = B["o"][r0]
        out["range_1h_pts"].append(rng)
        for mn in (15, 30, 60):
            k = DY.bar_at(d, at + mn - 5)
            if k is None:
                continue
            mv = D * (B["c"][k] - B["c"][r0])
            out[f"cont_{mn}"].append(mv > 0)
            out[f"rev_{mn}"].append(D * (B["c"][k] - o0) < 0)
            out[f"move_atr_{mn}"].append(mv / a5 if a5 else 0)
        pre = DY.overnight(d) if at == 510 else (lambda P: (B["h"][P].max(), B["l"][P].min()) if P else None)(DY.window(d, 570, at))
        W30 = DY.window(d, at, at + 30)
        if pre and W30:
            bh, bl = B["h"][W30].max() > pre[0], B["l"][W30].min() < pre[1]
            out["break_pre_30"].append(bh or bl)
            k = DY.bar_at(d, at + 55)
            if k is not None and (bh or bl):
                out["break_back_inside_60"].append(pre[1] <= B["c"][k] <= pre[0])
    return {k: (round(float(np.mean(v)) * (1 if k.startswith(("range", "move")) else 100), 2), len(v)) for k, v in out.items()}


def score(T, S):
    """$ stats + walk-forward on a trade list with day keys."""
    o = {}
    for nm, (a, z) in SPANS.items():
        TT = [t for t in T if a <= t["day"] <= z]
        p = np.array([t["pnl"] for t in TT]) if TT else np.zeros(0)
        g, l = p[p > 0].sum(), -p[p < 0].sum()
        ns = len([d for d in S if a <= d <= z])
        o[nm] = {"n": len(TT), "pf": round(float(g / l), 2) if l else None, "net": round(float(p.sum())),
                 "per_month": round(float(p.sum()) / (ns / 21)) if ns else 0, "win": round(100 * float((p > 0).mean()), 1) if len(p) else None,
                 "avg_r": round(float(np.mean([t["r"] for t in TT])), 3) if TT else None}
    wins = tot = 0
    m = dt.date(2021, 11, 1)
    while m <= dt.date(2026, 6, 1):
        z = ((m + dt.timedelta(days=183)).replace(day=1) - dt.timedelta(days=1)).isoformat()
        TT = [t["pnl"] for t in T if m.isoformat() <= t["day"] <= z]
        if TT:
            tot += 1; wins += sum(TT) > 0
        m = (m + dt.timedelta(days=95)).replace(day=1)
    o["walk_forward"] = f"{wins}/{tot}"
    return o


def main():
    t0 = time.time()
    say = lambda s: print(f"[{time.time() - t0:5.0f}s] {s}", flush=True)  # noqa: E731
    EV = calendar()
    B = N.bars(5)
    DY = Day(B)
    S = [d for d in DY.dates if "2021-11-01" <= d <= "2026-11-20" and dt.date.fromisoformat(d).weekday() < 5]
    ev830 = {d: s for d, s in EV.items() if s & {"CPI", "NFP", "PPI", "NFP_rule"} and d in DY.idx}
    fomc = {d for d, s in EV.items() if "FOMC" in s and d in DY.idx}
    anyev = {d for d in EV}
    non = [d for d in S if d not in anyev]
    res = {"made": "2026-11-26", "design": "research/news/DESIGN.md", "coverage": {}, "measure": {}, "plays": {}}
    for ty in ("CPI", "NFP", "PPI", "NFP_rule"):
        res["coverage"][ty] = collections.Counter(d[:4] for d, s in ev830.items() if ty in s)
    res["coverage"]["FOMC"] = collections.Counter(d[:4] for d in fomc)
    say(f"coverage {json.dumps(res['coverage'])}")
    for ty in ("CPI", "NFP", "PPI"):
        days = [d for d, s in ev830.items() if ty in s or (ty == "NFP" and "NFP_rule" in s)]
        res["measure"][ty] = measure(DY, days, 510)
    res["measure"]["all 08:30 Tier-1"] = measure(DY, list(ev830), 510)
    res["measure"]["08:30 on non-event days (placebo)"] = measure(DY, non, 510)
    res["measure"]["FOMC 14:00"] = measure(DY, sorted(fomc), 840)
    res["measure"]["14:00 on non-event days (placebo)"] = measure(DY, non, 840)
    for k, v in res["measure"].items():
        say(f"{k:40s} {v}")
    # playbooks
    PT = {}
    for nm in ("N1", "N2", "N3", "N4", "N5", "N6"):
        days = sorted(fomc) if nm in ("N5", "N6") else sorted(ev830)
        o = {}
        for ck, cost in COSTS.items():
            T = [dict(t, day=d) for d in days for t in [play(nm, DY, d, cost)] if t]
            o[ck] = score(T, S)
            if ck == "base":
                PT[nm] = T
        Tp = [dict(t, day=d) for d in non for t in [play(nm, DY, d, COSTS["base"])] if t]
        o["placebo_non_event"] = score(Tp, S)
        res["plays"][nm] = o
        say(f"{nm}: " + " | ".join(f"{sp}: n{o['base'][sp]['n']} PF {o['base'][sp]['pf']} ${o['base'][sp]['net']:,} (stress PF {o['stress'][sp]['pf']}, placebo PF {o['placebo_non_event'][sp]['pf']} avgR {o['placebo_non_event'][sp]['avg_r']})" for sp in SPANS)
            + f" | WF {o['base']['walk_forward']}")
    # LIT / ATLAS on news days
    say("LIT + ATLAS ...")
    LT, SL = BZ.lit_trades()
    AT = BZ.atlas_trades()
    newsdays = set(ev830) | fomc
    for nm, T in (("N7 LIT", LT), ("N8 ATLAS", AT)):
        on = [t for t in T if t["day"] in newsdays]
        off = [t for t in T if t["day"] not in newsdays]
        res["plays"][nm] = {"as_is": {sp: v for sp, v in MT_span(T, SL).items()}, "skip_news": MT_span(off, SL),
                            "news_day_trades": {sp: {"n": sum(1 for t in on if a <= t["day"] <= z), "net": round(sum(t["pnl"] for t in on if a <= t["day"] <= z))}
                                                for sp, (a, z) in SPANS.items()}}
        say(f"{nm}: news-day trades {res['plays'][nm]['news_day_trades']}")
    # add-on to the LIT + ATLAS 50K path
    comb = {}
    variants = {"LIT + ATLAS": LT + AT, "LIT + ATLAS, both skip news days": [t for t in LT + AT if t["day"] not in newsdays]}
    for nm in ("N1", "N2", "N3", "N4", "N5", "N6"):
        variants[f"LIT + ATLAS + {nm}"] = LT + AT + [dict(t, src=nm) for t in PT[nm]]
    for k, T in variants.items():
        comb[k] = MT_span(BZ.one_position(T), SL)
        say(f"{k:34s} " + " | ".join(f"{sp}: ${x['per_month']:,}/mo 50K {x['50K']['pass']}/{x['50K']['fail']} med {x['50K']['med']}" for sp, x in comb[k].items()))
    res["combined_50k"] = comb
    json.dump(res, open(os.path.join(HERE, "results.json"), "w"), indent=1, default=float)


def MT_span(T, S):
    out = {}
    for sp, (a, z) in SPANS.items():
        x = MT.span_stats(T, S, a, z)
        out[sp] = {"tpw": x["tpw"], "pf": x["pf"], "per_month": x["per_month"], "max_dd": x["max_dd"], "50K": x["evals"]["50K"]}
    return out


if __name__ == "__main__":
    main()
