"""New-strategy hunt (2026-11-17): a THIRD NQ strategy that wins on days LIT and ATLAS don't (more winning days for the
MFFU Rapid 30% best-day rule and the Builder funded 50% consistency rule). Paper research only: edits no engine / model / UI
file, arms nothing. Write-up: research/writeups/new-strategy-hunt-2026-11-17.md. Numbers: research/second/new_hunt.json.

Read first (docs/CLAUDE_REFERENCE.md "Tested and rejected" + the write-ups behind it). Discarded as already covered:
  - first pullback after a 2-sigma opening drive = hq-continuation.md (first pullback in a London / NY leg of k ATR, 186k
    versions) + BLITZ opening drive (blitz-25k.md) + the 2-sigma excursion tilt (atlas-blitz-edge).
  - plain ORB / gap fade / VWAP fades / NR7 / late new-day-high break / last-half-hour reversal (E2, public-strategies).
  - VP as a LIT size filter (vwap-volume-profile.md) - but NOT the value-area edges as their own setup (family FAV / D80).

Four families, hypotheses written BEFORE the run (each cell is counted; nothing added after the first look):

  LSQ  Lunch squeeze -> PM break (owner ideas 1 + 2 in one grid). H: the NY lunch (11:00-14:00) range is a volatility
       contraction; when it is narrow (vs the AM range or vs its own 20-day mean) the first 5m close beyond it in the PM
       (range end -> 15:00) starts the afternoon move, best WITH the AM trend (14:00-15:30 continuation). Stop 1 tick beyond
       the opposite side of the range ("opp") or its middle ("mid"); target 1.5R / 2R / 3R or the 15:55 close. New vs E2
       "late break" (a new DAY high after 14:00): the level is the lunch box, gated by contraction.
  FAV  Failed auction at the prior session's value-area edge. Volume profile of the prior RTH session from its 5m bars
       (each bar's volume spread evenly over its 1-pt price bins), POC, VAH / VAL = 70% contiguous around the POC. H: a
       probe beyond VAH (VAL) that closes back inside within N bars is excess (no acceptance) -> fade it to the POC / the
       far edge / 2R. Stop 1 tick beyond the probe extreme (min 8 pts). New vs second-sr / LIT: the level is the value
       edge (inside the prior range), not PDH / PDL / session highs.
  D80  Dalton's 80% rule. H: an open outside the prior value area that gets back inside and holds for 1 / 2 half-hour
       closes rotates through value to the far edge. Stop 1 tick beyond the day's extreme on the outside side.
  LXF  London extension fade into the NY open. H: when the 02:00 -> 09:30 move is >= k x its 20-day mean size, the NY
       open's failure to extend (a 5m close beyond the 09:30-09:45 / 10:00 range or back across the 09:30 open, against
       the extension) mean-reverts part of the London move. Stop 1 tick beyond the RTH extreme so far. Target 50% / 100%
       of the extension or 2R. Near-overlap: E2 gap fade (measured from the prior 16:00 close); here from London's 02:00.

Execution = tools/div_search.py walk(): CME NQ1! 5m RTH (back-adjusted, 2021-11 -> 2026-10-16), signal on a 5m close, entry
at the next open + 1 tick, stop fills at the stop (or the open through it) - 1 tick, a target needs a trade-through, stop and
target in one bar = stop, flat 15:55 (open of the last bar - 1 tick). $1.90 a micro. $500 risk: micros = floor(500 /
(stop x $2 + $1.90)), 1-40 (size follows the stop). One trade a day per cell.

Judging: "holds" = net > 0 and PF >= 1.1 in each of H1 (2026 Jan-Jun), H2 (Jul-Oct 16), 2025, 2021-24. Chance level = the
same cells with coin-flip directions (stop and target mirrored at the same distance), 10 seeds. Pick per family on H1 only
(n >= 20, PF >= 1.2, 2-4 trades a week, best H1 $), then H2 / 2021-25 read untouched. Correlation: daily P&L vs LIT
(research/lab/backtest_live.json days). Eval: its own Builder 50K (+$3,000, $2,000 EOD trailing, locks at $50,100), $400
risk, a start on every session, pass / fail within 40 sessions + median sessions to pass.

    python -X utf8 tools/new_hunt.py grid        # all cells + chance level -> research/second/new_hunt.json
"""
from __future__ import annotations

import collections
import datetime as dt
import itertools
import json
import math
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import div_search as DS  # noqa: E402

OUT = os.path.join(ROOT, "research", "second", "new_hunt.json")
TICK, NB, PV, COMM = DS.TICK, DS.NB, DS.PV, DS.COMM
MIN_STOP = 8.0
J4 = ("H1", "H2", "2025", "2021-24")
col = DS.col_of                     # column of the bar that CLOSES at (h, m)


def c0(h, m):
    """Column of the bar that OPENS at (h, m)."""
    return (h * 60 + m - 570) // 5


# ================================================================================================ extra facts
class X:
    def __init__(self):
        B = DS.D()
        self.B = B
        n = len(B.days)
        # prior full RTH session's volume profile (POC / VAH / VAL), skipped when the gap is > 4 calendar days
        self.POC = np.full(n, np.nan); self.VAH = np.full(n, np.nan); self.VAL = np.full(n, np.nan)
        for k in range(1, n):
            a, b = dt.date.fromisoformat(B.days[k - 1]), dt.date.fromisoformat(B.days[k])
            if (b - a).days > 4:
                continue
            self.POC[k], self.VAH[k], self.VAL[k] = profile(B.H[k - 1], B.L[k - 1], B.V[k - 1])
        rng = B.H.max(axis=1) - B.L.min(axis=1)
        self.rng14 = np.array([rng[max(0, k - 14):k].mean() if k >= 10 else np.nan for k in range(n)])
        # London 02:00 open (same calendar date) from the full 5m file
        d = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"), usecols=["time", "open"])
        et = pd.to_datetime(d.time, unit="s", utc=True).dt.tz_convert("America/New_York")
        hm = (et.dt.hour * 60 + et.dt.minute).to_numpy()
        date = et.dt.date.astype(str).to_numpy()
        m = hm == 120
        o2 = dict(zip(date[m], d.open.to_numpy(float)[m]))
        self.O2 = np.array([o2.get(x, np.nan) for x in B.days])
        ext = B.O[:, 0] - self.O2
        self.ext = ext
        ae = np.abs(ext)
        self.ext20 = np.array([np.nanmean(ae[max(0, k - 20):k]) if k >= 15 else np.nan for k in range(n)])


def profile(H, L, V, va=0.70):
    lo = int(math.floor(L.min())); hi = int(math.ceil(H.max()))
    vol = np.zeros(hi - lo + 1)
    for h, l, v in zip(H, L, V):
        a, b = int(math.floor(l)) - lo, int(math.ceil(h)) - lo
        vol[a:b + 1] += v / (b - a + 1)
    p = int(np.argmax(vol))
    tot, acc, i, j = vol.sum(), vol[p], p, p
    while acc < va * tot and (i > 0 or j < len(vol) - 1):
        up = vol[j + 1:j + 3].sum() if j < len(vol) - 1 else -1
        dn = vol[max(0, i - 2):i].sum() if i > 0 else -1
        if up >= dn:
            step = min(2, len(vol) - 1 - j); acc += vol[j + 1:j + 1 + step].sum(); j += step
        else:
            step = min(2, i); acc += vol[i - step:i].sum(); i -= step
    return lo + p + 0.5, lo + j + 1.0, lo + i + 0.0


_X = {}


def XX():
    if "x" not in _X:
        _X["x"] = X()
    return _X["x"]


# ================================================================================================ signals -> trades
def execute(sigs, flip=None):
    """sigs: list of (k, j, d, stop, tgt_or_None, R_or_None). R = target in R multiples (if tgt None). flip: rng for the
    coin-flip control (direction reversed with p 0.5, stop / target mirrored at the same distance from the next open)."""
    B = DS.D()
    W = []
    for k, j, d, stop, tgt, R in sigs:
        if j + 1 >= NB - 1:
            continue
        ref = B.O[k, j + 1]
        if flip is not None and flip.random() < 0.5:
            dist = (ref - stop) * d
            tdist = None if tgt is None else (tgt - ref) * d
            d = -d
            stop = ref - d * dist
            tgt = None if tdist is None else ref + d * tdist
        entry = ref + d * TICK
        if (entry - stop) * d < MIN_STOP:
            stop = entry - d * MIN_STOP
        if tgt is None and R:
            tgt = entry + d * R * (entry - stop) * d
        w = DS.walk(B, k, j, d, stop, "fixed", tgt=tgt)
        if w is not None:
            W.append(w)
    return W


def lsq(cfg):
    B, E = DS.D(), XX()
    (h0, m0), (h1, m1) = cfg["win"]
    a, z = c0(h0, m0), col((h1, m1))
    last = col((15, 0))
    hist = collections.deque(maxlen=20)
    out = []
    for k in range(len(B.days)):
        hi, lo = B.H[k, a:z + 1].max(), B.L[k, a:z + 1].min()
        rr = hi - lo
        am = B.H[k, :a].max() - B.L[k, :a].min()
        mean20 = np.mean(hist) if len(hist) >= 15 else np.nan
        hist.append(rr)
        if cfg["comp"] == "am50" and not rr <= 0.5 * am:
            continue
        if cfg["comp"] == "hist80" and not (np.isfinite(mean20) and rr <= 0.8 * mean20):
            continue
        move = B.C[k, a - 1] - B.O[k, 0]
        sg = B.sig[14][k, a - 1]
        for j in range(z + 1, last + 1):
            c = B.C[k, j]
            d = 1 if c > hi else -1 if c < lo else 0
            if not d:
                continue
            if cfg["trend"] != "any":
                if not np.isfinite(sg) or abs(move) < 0.5 * sg:
                    break
                w = 1 if move > 0 else -1
                if (cfg["trend"] == "with") != (d == w):
                    break
            ref = (lo if d == 1 else hi) if cfg["stop"] == "opp" else (hi + lo) / 2.0
            stop = ref - d * TICK
            R = None if cfg["exit"] == "eod" else float(cfg["exit"][1:])
            out.append((k, j, d, stop, None, R))
            break
    return out


def fav(cfg):
    B, E = DS.D(), XX()
    a, z = 0, col(cfg["until"])
    out = []
    for k in range(len(B.days)):
        vah, val, poc = E.VAH[k], E.VAL[k], E.POC[k]
        if not np.isfinite(vah) or not np.isfinite(E.rng14[k]):
            continue
        o = B.O[k, 0]
        if cfg["open"] == "in" and not (val <= o <= vah):
            continue
        depth = cfg["depth"] * E.rng14[k]
        st = {1: None, -1: None}           # side -> (start col, extreme)
        for j in range(a, z + 1):
            done = False
            for s, lvl in ((-1, vah), (1, val)):        # s = trade direction (fade): short above VAH, long below VAL
                beyond = (B.H[k, j] > lvl + depth) if s == -1 else (B.L[k, j] < lvl - depth)
                if st[s] is None and beyond and ((o <= lvl) if s == -1 else (o >= lvl)):
                    st[s] = [j, B.H[k, j] if s == -1 else B.L[k, j]]
                elif st[s] is not None:
                    st[s][1] = max(st[s][1], B.H[k, j]) if s == -1 else min(st[s][1], B.L[k, j])
                if st[s] is None:
                    continue
                back = B.C[k, j] < lvl if s == -1 else B.C[k, j] > lvl
                if back:
                    if j - st[s][0] <= cfg["nbars"]:
                        stop = st[s][1] - s * TICK
                        entry = B.O[k, j + 1] + s * TICK if j + 1 < NB else np.nan
                        tgt = {"poc": poc, "far": val if s == -1 else vah, "r2": None}[cfg["tgt"]]
                        risk = max(MIN_STOP, (entry - stop) * s)
                        if tgt is not None and (tgt - entry) * s < 1.0 * risk:
                            st[s] = None
                            continue
                        out.append((k, j, s, stop, tgt, 2.0 if tgt is None else None))
                        done = True
                        break
                    st[s] = None                # too slow: accepted, reset
            if done:
                break
    return out


def d80(cfg):
    B, E = DS.D(), XX()
    z = col(cfg["until"])
    chk = [j for j in DS.CHECKS if j <= z]
    out = []
    for k in range(len(B.days)):
        vah, val, poc = E.VAH[k], E.VAL[k], E.POC[k]
        if not np.isfinite(vah):
            continue
        o = B.O[k, 0]
        s = -1 if o > vah else 1 if o < val else 0
        if not s:
            continue
        run = 0
        for j in chk:
            inside = val < B.C[k, j] < vah
            run = run + 1 if inside else 0
            if run >= cfg["closes"]:
                ext = B.H[k, :j + 1].max() if s == -1 else B.L[k, :j + 1].min()
                stop = ext - s * TICK
                entry = B.O[k, j + 1] + s * TICK
                tgt = {"poc": poc, "far": val if s == -1 else vah, "r2": None}[cfg["tgt"]]
                risk = max(MIN_STOP, (entry - stop) * s)
                if tgt is not None and (tgt - entry) * s < 0.5 * risk:
                    break
                out.append((k, j, s, stop, tgt, 2.0 if tgt is None else None))
                break
    return out


def lxf(cfg):
    B, E = DS.D(), XX()
    last = col(cfg["last"])
    out = []
    for k in range(len(B.days)):
        e, m = E.ext[k], E.ext20[k]
        if not (np.isfinite(e) and np.isfinite(m)) or abs(e) < cfg["k"] * m:
            continue
        s = -1 if e > 0 else 1                         # fade the London extension
        orj = col((9, 45)) if cfg["trig"] == "or15" else col((10, 0))
        orh, orl = B.H[k, :orj + 1].max(), B.L[k, :orj + 1].min()
        o = B.O[k, 0]
        for j in range(orj + 1, last + 1):
            c = B.C[k, j]
            if cfg["trig"] in ("or15", "or30"):
                hit = c < orl if s == -1 else c > orh
            else:
                hit = c < o if s == -1 else c > o
            if not hit:
                continue
            ext = B.H[k, :j + 1].max() if s == -1 else B.L[k, :j + 1].min()
            stop = ext - s * TICK
            entry = B.O[k, j + 1] + s * TICK
            risk = max(MIN_STOP, (entry - stop) * s)
            tgt = {"half": E.O2[k] + 0.5 * e, "full": E.O2[k], "r2": None}[cfg["tgt"]]
            if tgt is not None and (tgt - entry) * s < 1.0 * risk:
                break
            out.append((k, j, s, stop, tgt, 2.0 if tgt is None else None))
            break
    return out


FAM = {"lsq": lsq, "fav": fav, "d80": d80, "lxf": lxf}


def grid():
    G = []
    for win, comp, trend, stop, ex in itertools.product(
            [((11, 0), (13, 0)), ((11, 30), (13, 30)), ((12, 0), (14, 0))], ["any", "am50", "hist80"],
            ["any", "with", "against"], ["opp", "mid"], ["r1.5", "r2", "r3", "eod"]):
        cid = f"lsq_{win[0][0]}{win[0][1]:02d}_{comp}_{trend}_{stop}_{ex}"
        G.append((cid, "lsq", {"win": win, "comp": comp, "trend": trend, "stop": stop, "exit": ex}))
    for depth, nb, until, op, tgt in itertools.product([0.0, 0.1], [1, 3, 6], [(11, 30), (15, 0)], ["any", "in"],
                                                      ["poc", "far", "r2"]):
        cid = f"fav_d{int(depth * 100)}_n{nb}_u{until[0]}_{op}_{tgt}"
        G.append((cid, "fav", {"depth": depth, "nbars": nb, "until": until, "open": op, "tgt": tgt}))
    for closes, until, tgt in itertools.product([1, 2], [(12, 0), (15, 0)], ["poc", "far", "r2"]):
        G.append((f"d80_c{closes}_u{until[0]}_{tgt}", "d80", {"closes": closes, "until": until, "tgt": tgt}))
    for kk, trig, tgt, last in itertools.product([1.0, 1.5, 2.0], ["or15", "or30", "open"], ["half", "full", "r2"],
                                                 [(11, 30), (13, 0)]):
        G.append((f"lxf_k{int(kk * 10)}_{trig}_{tgt}_l{last[0]}", "lxf", {"k": kk, "trig": trig, "tgt": tgt, "last": last}))
    return G


# ================================================================================================ scoring
def lit_daily():
    d = json.load(open(os.path.join(ROOT, "research", "lab", "backtest_live.json"), encoding="utf-8"))
    return {x["date"]: float(x["pnl"]) for x in d["days"]}


def holds(S):
    return all(S[s].get("n", 0) >= 5 and S[s]["net"] > 0 and (S[s]["pf"] or 0) >= 1.1 for s in J4)


def eval_mc(T, span, risk=400.0, horizon=40):
    """Own Builder 50K: +$3,000, $2,000 EOD trailing (locks at $50,100), $risk a trade (re-sized from the $500 book)."""
    B = DS.D()
    a, z = DS.SPANS[span]
    days = [x for x in B.days if a <= x <= z]
    by, low = collections.defaultdict(float), collections.defaultdict(float)
    f = risk / 500.0
    for t in T:
        by[t["day"]] += t["pnl"] * f
        low[t["day"]] = min(low[t["day"]], t["low"] * f)
    res = []
    for i in range(len(days)):
        bal, hi, out = 0.0, 0.0, None
        for n, x in enumerate(days[i:i + horizon], 1):
            floor = min(hi - 2000.0, 100.0)
            if bal + low.get(x, 0.0) <= floor:
                out = ("F", n); break
            bal += by.get(x, 0.0)
            if bal >= 3000.0:
                out = ("P", n); break
            hi = max(hi, bal)
        if out is None and i + horizon > len(days):
            continue                      # not enough sessions left to judge
        res.append(out or ("O", horizon))
    if not res:
        return {}
    p = [n for r, n in res if r == "P"]
    return {"starts": len(res), "pass": round(100.0 * len(p) / len(res), 1),
            "fail": round(100.0 * sum(1 for r, _ in res if r == "F") / len(res), 1),
            "med_sessions": int(np.median(p)) if p else None}


def overlap(T, lit, span):
    """Winning days: LIT alone vs LIT + new (same day summed), per month; new-strategy wins on LIT's no-win days."""
    a, z = DS.SPANS[span]
    B = DS.D()
    days = [x for x in B.days if a <= x <= z]
    by = collections.defaultdict(float)
    for t in T:
        by[t["day"]] += t["pnl"]
    lw = sum(1 for x in days if lit.get(x, 0.0) > 0)
    cw = sum(1 for x in days if lit.get(x, 0.0) + by.get(x, 0.0) > 0)
    nw = [x for x in days if by.get(x, 0.0) > 0]
    off = sum(1 for x in nw if lit.get(x, 0.0) <= 0)
    mo = len(days) / 21.0
    x = np.array([lit.get(d, 0.0) for d in days]); y = np.array([by.get(d, 0.0) for d in days])
    c = float(np.corrcoef(x, y)[0, 1]) if x.std() > 0 and y.std() > 0 else None
    return {"corr": round(c, 3) if c is not None else None, "lit_win_days_mo": round(lw / mo, 1),
            "combo_win_days_mo": round(cw / mo, 1), "new_win_days_off_lit_pct": round(100.0 * off / len(nw), 1) if nw else None}


def main_grid():
    G = grid()
    lit = lit_daily()
    res = {}
    for cid, fam, cfg in G:
        sigs = FAM[fam](cfg)
        T = DS.booked(execute(sigs))
        S = DS.score(T)
        res[cid] = {"fam": fam, "cfg": {k: v for k, v in cfg.items()}, "S": {s: S[s] for s in ("H1", "H2", "2025", "2021-24", "2021-25")},
                    "holds": holds(S), "sigs": sigs}
    # chance level: coin-flip directions, 10 seeds
    chance = collections.defaultdict(list)
    for seed in range(10):
        rng = np.random.default_rng(100 + seed)
        cnt = collections.Counter()
        for cid, r in res.items():
            T = DS.booked(execute(r["sigs"], flip=rng))
            if holds(DS.score(T)):
                cnt[r["fam"]] += 1
        for f in FAM:
            chance[f].append(cnt[f])
    fams = {}
    for f in FAM:
        ids = [c for c in res if res[c]["fam"] == f]
        fams[f] = {"cells": len(ids), "hold_all4": sum(res[c]["holds"] for c in ids),
                   "chance_mean": round(float(np.mean(chance[f])), 2), "chance_max": int(max(chance[f])),
                   "h1_and_h2": sum(1 for c in ids if all(res[c]["S"][s].get("n", 0) >= 5 and res[c]["S"][s]["net"] > 0 for s in ("H1", "H2")))}
        # H1 pick
        ok = [c for c in ids if res[c]["S"]["H1"].get("n", 0) >= 20 and (res[c]["S"]["H1"]["pf"] or 0) >= 1.2
              and 2.0 <= res[c]["S"]["H1"]["tpw"] <= 4.0]
        pick = max(ok, key=lambda c: res[c]["S"]["H1"]["net"]) if ok else None
        fams[f]["h1_pick"] = pick
        okany = [c for c in ids if res[c]["S"]["H1"].get("n", 0) >= 12 and (res[c]["S"]["H1"]["pf"] or 0) >= 1.2]
        fams[f]["h1_pick_any_freq"] = max(okany, key=lambda c: res[c]["S"]["H1"]["net"]) if okany else None
    detail = {}
    for f in FAM:
        for key in ("h1_pick", "h1_pick_any_freq"):
            c = fams[f][key]
            if not c or c in detail:
                continue
            T = DS.booked(execute(res[c]["sigs"]))
            pl = []
            for seed in range(200):
                rng = np.random.default_rng(1000 + seed)
                pl.append(DS.stats(DS.booked(execute(res[c]["sigs"], flip=rng)), "H2").get("net", 0))
            h2 = res[c]["S"]["H2"].get("net", 0)
            detail[c] = {"S": res[c]["S"], "ov": {s: overlap(T, lit, s) for s in ("H1", "H2", "2021-25")},
                         "eval": {s: eval_mc(T, s) for s in ("H1", "H2", "2021-25")},
                         "placebo_h2_p": round(float(np.mean([x >= h2 for x in pl])), 3)}
    for r in res.values():
        r.pop("sigs")
    out = {"built": dt.date.today().isoformat(), "families": fams, "detail": detail, "cells": res}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1, default=str)
    print(json.dumps(fams, indent=1))
    for c, v in detail.items():
        print(c)
        for s in ("H1", "H2", "2025", "2021-24", "2021-25"):
            x = v["S"][s]
            print(f"  {s:8s} n={x.get('n')} tpw={x.get('tpw')} pf={x.get('pf')} net={x.get('net')} /mo={x.get('per_month')} dd={x.get('dd')} stop={x.get('stop')}")
        print("  overlap", v["ov"]); print("  eval", v["eval"]); print("  placebo H2 p", v["placebo_h2_p"])
    hold = [c for c in res if res[c]["holds"]]
    print("cells holding all 4 spans:", len(hold))
    for c in hold:
        print(" ", c, {s: (res[c]["S"][s]["n"], res[c]["S"][s]["tpw"], res[c]["S"][s]["pf"], res[c]["S"][s]["net"]) for s in J4})


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "grid"
    if cmd == "grid":
        main_grid()
