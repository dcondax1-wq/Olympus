"""Order-flow program round 2: the LVN family pushed further + volume-at-price features (day-ofprogram 2026-11-23).

PRE-REGISTERED. Written and committed BEFORE the first run. Every variant below is run and counted in the multiple-testing
correction (Holm over the coin-flip placebo p of ALL stand-alone variants in this file + B1 from of_program.py). No setting is
changed after the first look; failures go to docs/TESTED_AND_REJECTED.md.

Bars: data/NQ_5m.csv (2021-10 ..), data/ES_5m.csv (2025-04 ..), data/NQ_1m.csv (2025-12-28 ..; same prices as the 5m file,
checked). Trading day = 18:00 ET roll. LVN trades run on 5m bars (for 1m-profile variants: 5m bars resampled from the 1m
file, so profile and trades share one source). The (3) features on the 1m feed run wholly on 1m bars (TPO, POC, trades). Costs: $500 risk, micros = floor(500 / (risk pts * point value)) cap 40, NQ
micro $2/pt, ES micro $5/pt, $1.40 a micro round trip, 0.25 pt slippage on entry and stop / market exits.
Spans: "2021-25" (NQ: 2021-10..2025-12-27; ES: 2025-04..2025-12-27), "2026 H1" (2025-12-28..2026-06-30), "2026 H2" (2026-07-01..).
1m-profile variants have only H1 / H2.

PROFILES. RTH 09:30-16:00 bars; each bar's volume spread evenly over the 2-pt bins it touches; centred 3-bin mean.
  D1 = prior trading day, W5 = the 5 prior trading days summed, C20 = the 20 prior trading days summed.
  LVN = smoothed local minimum <= 35 % of the POC bin with a bin >= 60 % of the POC on both sides (B1's definition).
  HVN = smoothed local maximum >= 60 % of the POC bin (the POC included).

(1) LVN REJECTION (B1's rule unchanged, only the market / window / profile change). A 5m bar touches an LVN coming from above
    (previous close > L), closes above L in the top half of its range -> long next open, stop 1 tick under the bar, 2R.
    Mirror from below. First signal per window per day.
    Windows: LDN signals 03:00-07:55, flat 09:25 | AM signals 09:45-11:55, flat 15:55 | PM signals 12:00-14:55, flat 15:55.
    Grid: {NQ 5m-profile, ES 5m-profile, NQ 1m-profile} x {D1, W5, C20} x {LDN, AM, PM} = 27 variants.
    + U = "union lane": NQ 5m D1, all three windows together (up to 3 a day) = 28. (B1 itself = NQ 5m D1 10:00-15:00.)
(2) LIT CONFLUENCE. For each LIT trade (tools/lit_losses.run()), prior-day NQ 5m D1 profile: into_LVN = an LVN within 5 pts
    of the sweep extreme; into_HVN = an HVN within 5 pts. Report avg R / $ with vs without per span. Pre-set rules:
    L1 skip into_HVN trades; L2 x1.25 size on into_LVN trades (P&L x 1.25, micro rounding ignored); L3 x0.5 on into_HVN.
    Pass = more net $ than all-LIT in all 3 spans.
(3) VOLUME-AT-PRICE features, each one rule, run on a 1m feed (H1/H2) and a 5m feed (3 spans) = 6 variants:
    V1 developing-POC migration: RTH profile from 09:30; POC at 10:00 < POC at 10:30 < POC at 11:00 and the 10:55 bar closes
       above the 11:00 POC -> long at the 11:00 open, stop 1 tick under the 09:30-11:00 low, 2R, flat 15:55 (mirror short).
    V2 single prints: 30-min TPO periods from 09:30; at 12:00, 1-pt prices touched by exactly one of the 09:30-12:00 periods,
       runs >= 10 pts = single-print zones. 12:00-14:55: the first bar that trades into a zone below price and closes above
       the zone top -> long, stop 1 tick under the bar, 2R (mirror for a zone above). One per day.
    V3 poor high / low magnet: prior-day RTH high is poor (>= 2 of its 30-min periods within 2 ticks of it, = B3). At the
       10:00 bar open, price below a poor high (and no poor low below) -> long, stop 1 tick under the 09:30-10:00 low,
       target = the poor high, skip if reward < 1R. Mirror for a poor low. One per day.
GATES. Stand-alone: PF >= 1.15 and net > 0 in every span it has, >= 1 trade a week (the union lane is how LVN could get
    there), Holm-adjusted placebo p < 0.10 (5,000 coin-flip-direction draws on the same signal bars). Add-on value reported
    for every stand-alone: daily-P&L correlation with LIT, LIT + X, and a "Rapid book" LIT + ATLAS + X: LIT replay $, ATLAS =
    its 3 members' stored trades (research/second/{ema,md,sr}_best.json) at r x $250, X at r x $250. That book is a plain
    sum of daily $ (no MFFU rule simulation).

  python research/orderflow/of_lvn.py   -> research/orderflow/lvn_results.json
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
ET = ZoneInfo("America/New_York")
OUT = os.path.join(ROOT, "research", "orderflow", "lvn_results.json")
TICK, COMM, SLIP, RISK, BIN = 0.25, 1.40, 0.25, 500.0, 2.0
PVS = {"NQ": 2.0, "ES": 5.0}
SPANS = [("2021-25", "2021-01-01", "2025-12-27"), ("2026 H1", "2025-12-28", "2026-06-30"), ("2026 H2", "2026-07-01", "2026-12-31")]
WINDOWS = {"LDN": (180, 480, 565), "AM": (585, 720, 955), "PM": (720, 900, 955)}   # signal start, signal end (excl), flat
DRAWS = 5000
RNG = np.random.default_rng(20261123)


def span_of(d):
    for nm, a, b in SPANS:
        if a <= d <= b:
            return nm
    return None


def stats(p, wk=None):
    p = np.asarray(p, float)
    if not len(p):
        return {"n": 0}
    gl = -p[p < 0].sum()
    eq = np.cumsum(p)
    dd = float((np.maximum.accumulate(np.concatenate([[0], eq]))[1:] - eq).max())
    o = {"n": int(len(p)), "win%": round(100 * float((p > 0).mean()), 1), "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None,
         "net$": round(float(p.sum())), "maxDD$": round(dd)}
    if wk:
        o["per_wk"] = round(len(p) / wk, 2)
        o["$/mo"] = round(float(p.sum()) / (wk / 4.345))
    return o


# ------------------------------------------------------------------------------------------------ bars
class Bars:
    def __init__(self, df, sym):
        df = df.drop_duplicates("time").sort_values("time").reset_index(drop=True)
        t = pd.to_datetime(df.time, unit="s", utc=True).dt.tz_convert(ET)
        self.sym, self.pv = sym, PVS[sym]
        self.t = df.time.values
        self.o, self.h, self.l, self.c, self.v = (df[k].values.astype(float) for k in ("open", "high", "low", "close", "volume"))
        self.mod = (t.dt.hour * 60 + t.dt.minute).values
        td = (t + pd.Timedelta(hours=6)).dt.strftime("%Y-%m-%d").values          # 18:00 ET roll
        self.td = td
        self.days, self.idx = [], {}
        start = 0
        for i in range(1, len(td) + 1):
            if i == len(td) or td[i] != td[start]:
                self.days.append(td[start]); self.idx[td[start]] = np.arange(start, i); start = i

    def rth(self, d):
        ix = self.idx[d]
        return ix[(self.mod[ix] >= 570) & (self.mod[ix] < 960)]


def resample5(df1):
    b = df1.assign(k=df1.time // 300 * 300).groupby("k")
    return pd.DataFrame({"time": b.time.first().index.values, "open": b.open.first().values, "high": b.high.max().values,
                         "low": b.low.min().values, "close": b.close.last().values, "volume": b.volume.sum().values})


def day_profile(B, d):
    """(first global bin, raw volume per 2-pt bin) of trading day d's RTH bars; volume spread evenly over touched bins."""
    ix = B.rth(d)
    if len(ix) < 30:
        return None
    b0 = np.floor(B.l[ix] / BIN).astype(int)
    b1 = np.floor(B.h[ix] / BIN).astype(int)
    lo = int(b0.min()); n = int(b1.max()) - lo + 2
    diff = np.zeros(n)
    w = B.v[ix] / (b1 - b0 + 1)
    np.add.at(diff, b0 - lo, w); np.add.at(diff, b1 - lo + 1, -w)
    return lo, np.cumsum(diff)[:-1]


def combine(profs):
    profs = [p for p in profs if p is not None]
    if not profs:
        return None
    lo = min(p[0] for p in profs); hi = max(p[0] + len(p[1]) for p in profs)
    v = np.zeros(hi - lo)
    for a, x in profs:
        v[a - lo:a - lo + len(x)] += x
    return lo, v


def nodes(prof):
    lo, v = prof
    sm = np.convolve(v, np.ones(3) / 3, mode="same")
    pv = sm.max()
    price = (lo + np.arange(len(sm))) * BIN + BIN / 2
    lv, hv = [], []
    for i in range(1, len(sm) - 1):
        if sm[i] <= sm[i - 1] and sm[i] <= sm[i + 1] and sm[i] <= 0.35 * pv and sm[:i].max() >= 0.6 * pv and sm[i + 1:].max() >= 0.6 * pv:
            lv.append(float(price[i]))
        if sm[i] >= sm[i - 1] and sm[i] >= sm[i + 1] and sm[i] >= 0.6 * pv:
            hv.append(float(price[i]))
    return lv, hv


def profiles(B, kind, P1=None):
    """trading day -> (LVNs, HVNs) of the profile available BEFORE that day. P1 = 1m Bars to build the profile from."""
    src = P1 or B
    dp = {d: day_profile(src, d) for d in src.days}
    order = [d for d in src.days if dp[d] is not None]
    n = {"D1": 1, "W5": 5, "C20": 20}[kind]
    out = {}
    for i in range(n, len(order)):
        prof = combine([dp[x] for x in order[i - n:i]])
        if prof is not None:
            out[order[i]] = nodes(prof)
    return out


# ------------------------------------------------------------------------------------------------ simulator
def sim(B, d, k, dd, stop, flat, tgt=None):
    ix = B.idx[d]
    pos = int(np.searchsorted(ix, k))
    if pos + 1 >= len(ix) or B.mod[ix[pos + 1]] > flat:
        return None
    e = ix[pos + 1]
    entry = B.o[e] + SLIP * dd
    risk = (entry - stop) * dd
    if risk <= 0:
        return None
    if tgt is None:
        tgt = entry + 2 * risk * dd
    elif (tgt - entry) * dd < risk:
        return None
    q = int(min(40, RISK // (risk * B.pv)))
    if q < 1:
        return None
    px, last = None, e
    for j in ix[pos + 1:]:
        if B.mod[j] > flat or B.mod[j] < B.mod[e]:
            break
        last = j
        if (dd == 1 and B.l[j] <= stop) or (dd == -1 and B.h[j] >= stop):
            px = stop - SLIP * dd; break
        if (dd == 1 and B.h[j] >= tgt) or (dd == -1 and B.l[j] <= tgt):
            px = tgt; break
    if px is None:
        px = B.c[last] - SLIP * dd
    return {"pnl": (px - entry) * dd * B.pv * q - COMM * q, "r": (px - entry) * dd / risk}


def lvn_signals(B, prof, win):
    s0, s1, flat = WINDOWS[win]
    sigs = []
    for d in B.days:
        if d not in prof or not prof[d][0]:
            continue
        L = prof[d][0]
        ix = B.idx[d]
        for n in range(1, len(ix)):
            k = ix[n]
            if not (s0 <= B.mod[k] < s1):
                continue
            rg = B.h[k] - B.l[k]
            pc = B.c[ix[n - 1]]
            hit = 0
            for lv in L:
                if rg > 0 and B.l[k] <= lv <= B.h[k]:
                    if pc > lv and B.c[k] > lv and B.c[k] >= B.l[k] + rg / 2:
                        hit = 1
                    elif pc < lv and B.c[k] < lv and B.c[k] <= B.l[k] + rg / 2:
                        hit = -1
                    if hit:
                        break
            if hit:
                a = sim(B, d, k, hit, B.l[k] - TICK if hit == 1 else B.h[k] + TICK, flat)
                f = sim(B, d, k, -hit, B.h[k] + TICK if hit == 1 else B.l[k] - TICK, flat)
                if a:
                    sigs.append({"day": d, "pnl": a["pnl"], "r": a["r"], "flip": f["pnl"] if f else 0.0, "flip_r": f["r"] if f else 0.0})
                break
    return sigs


# ------------------------------------------------------------------------------------------------ volume-at-price features
def tpo_periods(B, ix):
    return (B.mod[ix] - 570) // 30


def v1_dpoc(B):
    sigs = []
    for d in B.days:
        ix = B.rth(d)
        if len(ix) < 60:
            continue
        pocs = []
        for cut in (600, 630, 660):
            sub = ix[B.mod[ix] < cut]
            if not len(sub):
                break
            b0 = np.floor(B.l[sub] / BIN).astype(int); b1 = np.floor(B.h[sub] / BIN).astype(int)
            lo = b0.min(); diff = np.zeros(b1.max() - lo + 2); w = B.v[sub] / (b1 - b0 + 1)
            np.add.at(diff, b0 - lo, w); np.add.at(diff, b1 - lo + 1, -w)
            pocs.append((lo + int(np.argmax(np.cumsum(diff)[:-1]))) * BIN + BIN / 2)
        if len(pocs) < 3:
            continue
        pre = ix[B.mod[ix] < 660]
        sig_k = pre[-1]
        dd = 1 if (pocs[0] < pocs[1] < pocs[2] and B.c[sig_k] > pocs[2]) else (-1 if (pocs[0] > pocs[1] > pocs[2] and B.c[sig_k] < pocs[2]) else 0)
        if not dd:
            continue
        stop = B.l[pre].min() - TICK if dd == 1 else B.h[pre].max() + TICK
        fstop = B.h[pre].max() + TICK if dd == 1 else B.l[pre].min() - TICK
        a = sim(B, d, sig_k, dd, stop, 955); f = sim(B, d, sig_k, -dd, fstop, 955)
        if a:
            sigs.append({"day": d, "pnl": a["pnl"], "r": a["r"], "flip": f["pnl"] if f else 0.0, "flip_r": f["r"] if f else 0.0})
    return sigs


def v2_single(B):
    sigs = []
    for d in B.days:
        ix = B.rth(d)
        am = ix[B.mod[ix] < 720]
        if len(am) < 20:
            continue
        lo, hi = math.floor(B.l[am].min()), math.ceil(B.h[am].max())
        grid = np.arange(lo, hi + 1, 1.0)
        cnt = np.zeros(len(grid), int)
        per = tpo_periods(B, am)
        for p in np.unique(per):
            sub = am[per == p]
            cnt += (grid >= B.l[sub].min()) & (grid <= B.h[sub].max())
        zones, s = [], None
        for i, c in enumerate(cnt):
            if c == 1 and s is None:
                s = i
            if (c != 1 or i == len(cnt) - 1) and s is not None:
                e = i if c == 1 else i - 1
                if grid[e] - grid[s] >= 10:
                    zones.append((grid[s], grid[e]))
                s = None
        if not zones:
            continue
        pm = ix[(B.mod[ix] >= 720) & (B.mod[ix] < 900)]
        for k in pm:
            prev = B.c[k - 1]
            hit = 0
            for zl, zh in zones:
                if B.l[k] <= zh and B.h[k] >= zl:
                    if prev > zh and B.c[k] > zh:
                        hit = 1
                    elif prev < zl and B.c[k] < zl:
                        hit = -1
                    if hit:
                        break
            if hit:
                a = sim(B, d, k, hit, B.l[k] - TICK if hit == 1 else B.h[k] + TICK, 955)
                f = sim(B, d, k, -hit, B.h[k] + TICK if hit == 1 else B.l[k] - TICK, 955)
                if a:
                    sigs.append({"day": d, "pnl": a["pnl"], "r": a["r"], "flip": f["pnl"] if f else 0.0, "flip_r": f["r"] if f else 0.0})
                break
    return sigs


def poor(B, ix):
    hi, lo = B.h[ix].max(), B.l[ix].min()
    per = tpo_periods(B, ix)
    ph = sum(1 for p in np.unique(per) if B.h[ix[per == p]].max() >= hi - 2 * TICK)
    pl = sum(1 for p in np.unique(per) if B.l[ix[per == p]].min() <= lo + 2 * TICK)
    return hi, ph >= 2, lo, pl >= 2


def v3_poor(B):
    sigs = []
    days = [d for d in B.days if len(B.rth(d)) >= 60]
    for p, d in zip(days[:-1], days[1:]):
        hi, hp, lo, lp = poor(B, B.rth(p))
        ix = B.rth(d)
        op = ix[B.mod[ix] < 600]
        at = ix[B.mod[ix] >= 600]
        if not len(op) or not len(at):
            continue
        px = B.o[at[0]]
        up = hp and px < hi
        dn = lp and px > lo
        if up == dn:
            continue
        dd = 1 if up else -1
        k = op[-1]
        stop = B.l[op].min() - TICK if dd == 1 else B.h[op].max() + TICK
        a = sim(B, d, k, dd, stop, 955, tgt=hi if dd == 1 else lo)
        fstop = B.h[op].max() + TICK if dd == 1 else B.l[op].min() - TICK
        f = sim(B, d, k, -dd, fstop, 955)
        if a:
            sigs.append({"day": d, "pnl": a["pnl"], "r": a["r"], "flip": f["pnl"] if f else 0.0, "flip_r": f["r"] if f else 0.0})
    return sigs


# ------------------------------------------------------------------------------------------------ reporting
def weeks_for(B):
    out = {}
    for nm, a, b in SPANS:
        ds = [d for d in B.days if a <= d <= b]
        out[nm] = max(1.0, (pd.Timestamp(ds[-1]) - pd.Timestamp(ds[0])).days / 7) if len(ds) > 5 else None
    return out


def placebo(sigs):
    if not sigs:
        return 1.0
    a = np.array([s["pnl"] for s in sigs]); f = np.array([s["flip"] for s in sigs])
    m = RNG.random((DRAWS, len(sigs))) < 0.5
    tot = np.where(m, a, f).sum(1)
    return float((np.sum(tot >= a.sum()) + 1) / (DRAWS + 1))


def report(sigs, wk, lit_daily, atlas_daily):
    res = {}
    for nm, _, _ in SPANS:
        if wk.get(nm):
            res[nm] = stats([s["pnl"] for s in sigs if span_of(s["day"]) == nm], wk[nm])
    res["placebo_p"] = round(placebo(sigs), 4)
    xd = pd.Series([s["r"] * 250 for s in sigs], index=[s["day"] for s in sigs], dtype=float).groupby(level=0).sum()
    xfull = pd.Series([s["pnl"] for s in sigs], index=[s["day"] for s in sigs], dtype=float).groupby(level=0).sum()
    add = {}
    for nm, a, b in SPANS:
        if not wk.get(nm) or nm not in res or not res[nm].get("n"):
            continue
        days = sorted(set(lit_daily.index) | set(atlas_daily.index) | set(xd.index))
        days = [d for d in days if a <= d <= b]
        L_ = lit_daily.reindex(days).fillna(0); A_ = atlas_daily.reindex(days).fillna(0)
        X_ = xd.reindex(days).fillna(0); Xf = xfull.reindex(days).fillna(0)

        def dd_(s):
            e = np.cumsum(s.values); return round(float((np.maximum.accumulate(np.concatenate([[0], e]))[1:] - e).max()))
        add[nm] = {"corr_LIT": round(float(np.corrcoef(L_, Xf)[0, 1]), 3) if Xf.std() > 0 and L_.std() > 0 else None,
                   "LIT$": round(L_.sum()), "LIT+X$": round((L_ + Xf).sum()), "LIT+X maxDD$": dd_(L_ + Xf), "LIT maxDD$": dd_(L_),
                   "book LIT+ATLAS$": round((L_ + A_).sum()), "book LIT+ATLAS+X(250)$": round((L_ + A_ + X_).sum()),
                   "book maxDD before/after": [dd_(L_ + A_), dd_(L_ + A_ + X_)],
                   "book $/mo before/after": [round((L_ + A_).sum() / (wk[nm] / 4.345)), round((L_ + A_ + X_).sum() / (wk[nm] / 4.345))]}
    res["add_on"] = add
    return res


def gate(res):
    sp = [res[nm] for nm, _, _ in SPANS if nm in res and isinstance(res[nm], dict) and "n" in res[nm]]
    return bool(sp) and all((x.get("pf") or 0) >= 1.15 and x.get("net$", 0) > 0 and (x.get("per_wk") or 0) >= 1.0 for x in sp)


def holm(ps):
    keys = sorted(ps, key=lambda k: ps[k])
    m, out, run = len(keys), {}, 0.0
    for i, k in enumerate(keys):
        run = max(run, min(1.0, (m - i) * ps[k]))
        out[k] = round(run, 4)
    return out


def main():
    from tools import lit_losses as L
    M, C, B1x, B5x = L.base()
    T = L.run()
    nq = Bars(pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv")), "NQ")
    es = Bars(pd.read_csv(os.path.join(ROOT, "data", "ES_5m.csv")), "ES")
    m1 = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv")).drop_duplicates("time").sort_values("time")
    nq1 = Bars(m1, "NQ")                       # 1m bars (profiles + TPOs)
    nq1_5 = Bars(resample5(m1), "NQ")          # 5m bars from the 1m file (trades)
    lit_daily = pd.Series([t["pnl"] for t in T], index=[t["day"] for t in T]).groupby(level=0).sum()
    at = []
    for f in ("ema", "md", "sr"):
        for t in json.load(open(os.path.join(ROOT, "research", "second", f + "_best.json")))["trades"]:
            at.append((t["day"], float(t["r"]) * 250 - 2.8))
    atlas_daily = pd.Series([x[1] for x in at], index=[x[0] for x in at]).groupby(level=0).sum()
    out = {"made": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "pre_registered": "docstring, committed before the first run"}
    W = {"NQ5": weeks_for(nq), "ES5": weeks_for(es), "NQ1": weeks_for(nq1_5)}
    W["NQ1"]["2021-25"] = None
    res, ps = {}, {}
    feeds = {"NQ 5m-profile": (nq, None, W["NQ5"]), "ES 5m-profile": (es, None, W["ES5"]), "NQ 1m-profile": (nq1_5, nq1, W["NQ1"])}
    union = []
    for fname, (B, P1, wk) in feeds.items():
        for kind in ("D1", "W5", "C20"):
            prof = profiles(B, kind, P1)
            for win in WINDOWS:
                s = lvn_signals(B, prof, win)
                key = "LVN %s %s %s" % (fname, kind, win)
                res[key] = report(s, wk, lit_daily if B.sym == "NQ" else lit_daily, atlas_daily)
                ps[key] = res[key]["placebo_p"]
                if fname == "NQ 5m-profile" and kind == "D1":
                    union += s
                print(key, {k: (v.get("net$"), v.get("pf"), v.get("per_wk")) for k, v in res[key].items() if isinstance(v, dict) and "n" in v}, ps[key])
    res["LVN union NQ 5m D1 LDN+AM+PM"] = report(union, W["NQ5"], lit_daily, atlas_daily)
    ps["LVN union NQ 5m D1 LDN+AM+PM"] = res["LVN union NQ 5m D1 LDN+AM+PM"]["placebo_p"]
    for nm, fn in (("V1 dPOC migration", v1_dpoc), ("V2 single prints", v2_single), ("V3 poor high/low magnet", v3_poor)):
        for feed, B, wk in (("1m", nq1, W["NQ1"]), ("5m", nq, W["NQ5"])):
            s = fn(B)
            key = "%s (%s)" % (nm, feed)
            res[key] = report(s, wk, lit_daily, atlas_daily)
            ps[key] = res[key]["placebo_p"]
            print(key, {k: (v.get("net$"), v.get("pf"), v.get("per_wk")) for k, v in res[key].items() if isinstance(v, dict) and "n" in v}, ps[key])
    ps["B1 (of_program, 500 draws)"] = 0.004
    adj = holm(ps)
    for k in res:
        res[k]["holm_p"] = adj.get(k)
        res[k]["verdict"] = "PASS" if (gate(res[k]) and adj.get(k, 1) < 0.10) else "REJECTED"
    out["standalone"] = res
    out["tests_in_correction"] = len(ps)
    # (2) LIT confluence
    prof = profiles(nq, "D1")
    rows = []
    for t in T:
        e = t["ext_i"]
        ext = M.l[e] if t["dir"] == 1 else M.h[e]
        lv, hv = prof.get(t["day"], ([], []))
        rows.append({"day": t["day"], "pnl": t["pnl"], "r": t["r"], "lvn": any(abs(ext - x) <= 5 for x in lv), "hvn": any(abs(ext - x) <= 5 for x in hv)})
    conf = {}
    for nm, _, _ in SPANS:
        R = [x for x in rows if span_of(x["day"]) == nm]
        g = lambda f: {"n": sum(1 for x in R if f(x)), "avgR": round(float(np.mean([x["r"] for x in R if f(x)])), 3) if any(f(x) for x in R) else None,  # noqa: E731
                       "net$": round(sum(x["pnl"] for x in R if f(x)))}
        base = sum(x["pnl"] for x in R)
        conf[nm] = {"into LVN": g(lambda x: x["lvn"]), "not LVN": g(lambda x: not x["lvn"]), "into HVN": g(lambda x: x["hvn"]),
                    "not HVN": g(lambda x: not x["hvn"]), "all LIT$": round(base),
                    "L1 skip HVN gain$": round(-sum(x["pnl"] for x in R if x["hvn"])),
                    "L2 x1.25 LVN gain$": round(0.25 * sum(x["pnl"] for x in R if x["lvn"])),
                    "L3 x0.5 HVN gain$": round(-0.5 * sum(x["pnl"] for x in R if x["hvn"]))}
    for rule in ("L1 skip HVN gain$", "L2 x1.25 LVN gain$", "L3 x0.5 HVN gain$"):
        conf[rule.replace(" gain$", "") + " verdict"] = "PASS" if all(conf[nm][rule] > 0 for nm, _, _ in SPANS) else "REJECTED"
    out["LIT confluence"] = conf
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(json.dumps(conf, indent=1))
    print("PASS:", [k for k, v in res.items() if v["verdict"] == "PASS"])


if __name__ == "__main__":
    main()
