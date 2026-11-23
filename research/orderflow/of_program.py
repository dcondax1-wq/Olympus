"""Order-flow program, part B: what 1m / 5m bars with volume CAN test (day-ofprogram 2026-11-23).

PRE-REGISTERED. Every rule and number below was written and committed BEFORE the first run; nothing is tuned afterwards.
Already rejected and NOT repeated (docs/TESTED_AND_REJECTED.md, vwap-volume-profile.md): Dalton 80% rule (twice), failed
auction at the prior value-area edge, prior-day POC first touch, VXN initial-balance breakout, IB sweep-and-reclaim scalp
(1m, VWAP target), 24 VWAP / VP size tilts on LIT, 5m CLV delta proxy S1/S2/S4 (orderflow-2026-11-23.md).

Data: data/NQ_5m.csv via tools/lit_losses.base() (2021-10 .. 2026-11, back-adjusted, volume per bar) and data/NQ_1m.csv
(2025-12-28 .. 2026-11). Spans: 2021-25 (5m only), 2026 H1 (2025-12-28 .. 2026-06-30), 2026 H2 (2026-07-01 ..).
Costs (stand-alones): $500 risk, micros = floor(500 / (risk pts * $2)), cap 40, min 1; $1.40 a micro round trip + 0.25 pt
slippage on entry and on stop / market exits (targets fill at the price). Flat 15:55 ET. First signal per day.
LIT trades: tools/lit_losses.run() = the live LIT replay, costs in (same list as of_study.py).

Profiles: prior trading day, RTH 09:30-16:00 5m bars, each bar's volume spread evenly over its ticks, 2-pt bins, smoothed with
a centred 3-bin mean. POC = biggest bin, value area 70 %.

B1 LVN rejection (stand-alone). LVN = smoothed local minimum <= 35 % of the POC bin with a bin >= 60 % of the POC on BOTH
   sides (a low-volume gap between two high-volume nodes), from the prior day's profile. 10:00-15:00 ET: a 5m bar touches an
   LVN (low <= L <= high) coming from above (previous close > L) and closes above L in the top half of its range -> long next
   open, stop 1 tick under the bar low, target 2R. Mirror from below. First per day.
B2 IB failed range extension (stand-alone). IB = 09:30-10:30. 10:30-14:30: the first bar that trades above IBH (below IBL);
   if it or one of the next 2 bars closes back inside the IB -> fade at the next open, stop 1 tick beyond the extension
   extreme, target IB midpoint, skip if reward < 1R. One per day.
B3 Poor high / low (TPO unfinished auction) as a LIT skip. Prior-day RTH high is POOR when >= 2 of the 13 30-min TPO periods
   have a high within 2 ticks of it (mirror for the low). A LIT short whose sweep extreme reached the prior-day RTH high
   (long: the low) is "swept a poor extreme". Claim: unfinished auctions get finished, so that sweep fails -> skip those.
   Also: next-session revisit rate of poor vs not-poor extremes (does the AMT claim exist on NQ at all).
B4 BVC delta (Easley, Lopez de Prado & O'Hara 2012 bulk volume classification) instead of the old CLV proxy:
   delta = V * (2 * Phi(dP / sd) - 1), sd = rolling std of dP over the prior 100 bars. 5m BVC for all spans, 1m BVC for 2026.
   S1' divergence: delta over the 15 min ending at the close of the sweep-extreme 5m bar has the trade's sign -> take only those.
   S4' confirmation: delta from the extreme bar's open to the entry has the trade's sign -> skip the rest ("refuted").
B5 Sweep participation (exhaustion needs volume). relvol = volume of the sweep-extreme 5m bar / mean of the 20 bars before.
   Skip LIT trades with relvol < 1.0.
B6 1m absorption print at the sweep (2026 only). In the sweep-extreme 5m bar, the 1m bar that made the extreme has volume
   >= 2x the mean of the prior 60 1m bars AND closes in its far half (long: top half) -> "absorbed". Take only absorbed trades.
Gates. Stand-alone: PF >= 1.15 and net > 0 in all 3 spans, >= 1 trade a week, coin-flip-direction placebo p < 0.10 (500 draws,
   same signal bars, both directions simulated). LIT add-on (skip rules): more net $ than all-LIT in every span tested
   (2021-25, H1, H2; B6 only H1, H2), else rejected. For stand-alones also report daily-P&L correlation with LIT.

  python research/orderflow/of_program.py   -> research/orderflow/program_results.json
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "research", "orderflow", "program_results.json")
TICK, PV, COMM, SLIP, RISK = 0.25, 2.0, 1.40, 0.25, 500.0
SPANS = [("2021-25", "2021-01-01", "2025-12-27"), ("2026 H1", "2025-12-28", "2026-06-30"), ("2026 H2", "2026-07-01", "2026-12-31")]
RNG = np.random.default_rng(20261123)


def span_of(day):
    for nm, a, b in SPANS:
        if a <= day <= b:
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


# ------------------------------------------------------------------------------------------------ data
def load():
    from tools import lit_losses as L
    M, C, B1, B5 = L.base()
    T = L.run()
    m1 = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv")).drop_duplicates("time").sort_values("time").reset_index(drop=True)
    return M, T, m1


def span_weeks(M):
    out = {}
    for nm, a, b in SPANS:
        ds = sorted({d for d in M.dates if a <= d <= b})
        out[nm] = max(1.0, (pd.Timestamp(ds[-1]) - pd.Timestamp(ds[0])).days / 7) if ds else None
    return out


def rth_index(M):
    """trading day -> array of 5m bar indices 09:30-15:55."""
    out = {}
    for d, a, b in M.days:
        idx = np.arange(a, b)
        idx = idx[(M.mod[idx] >= 570) & (M.mod[idx] < 960)]
        if len(idx) >= 60:
            out[str(d)] = idx
    return out


def profile(M, idx, bin_pts=2.0):
    lo = math.floor(M.l[idx].min() / bin_pts) * bin_pts
    hi = math.ceil(M.h[idx].max() / bin_pts) * bin_pts
    nb = int(round((hi - lo) / bin_pts)) + 1
    vol = np.zeros(nb)
    for k in idx:
        ticks = np.arange(M.l[k], M.h[k] + TICK / 2, TICK)
        if not len(ticks):
            continue
        b = np.floor((ticks - lo) / bin_pts).astype(int)
        np.add.at(vol, np.clip(b, 0, nb - 1), M.v[k] / len(ticks))
    sm = np.convolve(vol, np.ones(3) / 3, mode="same")
    prices = lo + bin_pts * np.arange(nb) + bin_pts / 2
    poc = int(np.argmax(sm))
    return prices, sm, poc


def lvns(prices, sm, poc):
    pv = sm[poc]
    out = []
    for i in range(1, len(sm) - 1):
        if sm[i] <= sm[i - 1] and sm[i] <= sm[i + 1] and sm[i] <= 0.35 * pv:
            if sm[:i].max() >= 0.6 * pv and sm[i + 1:].max() >= 0.6 * pv:
                out.append(float(prices[i]))
    return out


# ------------------------------------------------------------------------------------------------ stand-alone simulator
def sim(M, idx_day, k, d, stop, tgt=None, rr=2.0):
    """Entry at open of bar k+1 (must be in idx_day), 5m bars, stop/target, flat at the last RTH bar <= 15:55."""
    pos = np.searchsorted(idx_day, k)
    if pos + 1 >= len(idx_day):
        return None
    e_i = idx_day[pos + 1]
    entry = M.o[e_i] + SLIP * d
    risk = (entry - stop) * d
    if risk <= 0:
        return None
    if tgt is None:
        tgt = entry + rr * risk * d
    elif (tgt - entry) * d < 1.0 * risk:
        return None
    q = int(min(40, RISK // (risk * PV)))
    if q < 1:
        return None
    px, last = None, e_i
    for j in idx_day[pos + 1:]:
        if M.mod[j] > 955:
            break
        if (d == 1 and M.l[j] <= stop) or (d == -1 and M.h[j] >= stop):
            px = stop - SLIP * d; break
        if (d == 1 and M.h[j] >= tgt) or (d == -1 and M.l[j] <= tgt):
            px = tgt; break
        last = j
    if px is None:
        px = M.c[last] - SLIP * d
    return (px - entry) * d * PV * q - COMM * q


def standalone_report(M, sigs, wk, lit_daily):
    """sigs: list of (day, k, d, pnl_actual, pnl_flipped)."""
    res = {}
    for nm, _, _ in SPANS:
        res[nm] = stats([s[3] for s in sigs if span_of(s[0]) == nm], wk[nm])
    act = np.array([s[3] for s in sigs])
    flip = np.array([s[4] if s[4] is not None else 0.0 for s in sigs])
    draws = []
    for _ in range(500):
        m = RNG.random(len(sigs)) < 0.5
        draws.append(np.where(m, act, flip).sum())
    res["placebo_p"] = round(float((np.array(draws) >= act.sum()).mean()), 3)
    dd = pd.Series({s[0]: s[3] for s in sigs})
    corr = {}
    for nm, a, b in SPANS:
        ld = lit_daily[(lit_daily.index >= a) & (lit_daily.index <= b)]
        days = sorted(set(ld.index) | set(x for x in dd.index if a <= x <= b))
        if len(days) > 10:
            x = dd.reindex(days).fillna(0); y = ld.reindex(days).fillna(0)
            corr[nm] = round(float(np.corrcoef(x, y)[0, 1]), 3)
    res["corr_LIT_daily"] = corr
    ok = all((res[nm].get("pf") or 0) >= 1.15 and res[nm].get("net$", 0) > 0 and (res[nm].get("per_wk") or 0) >= 1.0
             for nm, _, _ in SPANS) and res["placebo_p"] < 0.10
    res["verdict"] = "PASS" if ok else "REJECTED"
    return res


def b1_lvn(M, R):
    sigs = []
    days = sorted(R)
    for p, d in zip(days[:-1], days[1:]):
        prices, sm, poc = profile(M, R[p])
        L = lvns(prices, sm, poc)
        if not L:
            continue
        idx = R[d]
        for k in idx[1:]:
            if not (600 <= M.mod[k] < 900):
                continue
            rng = M.h[k] - M.l[k]
            if rng <= 0:
                continue
            pc = M.c[k - 1]
            hit = None
            for lv in L:
                if M.l[k] <= lv <= M.h[k]:
                    if pc > lv and M.c[k] > lv and M.c[k] >= M.l[k] + rng / 2:
                        hit = 1
                    elif pc < lv and M.c[k] < lv and M.c[k] <= M.l[k] + rng / 2:
                        hit = -1
                    if hit:
                        break
            if hit:
                a = sim(M, idx, k, hit, M.l[k] - TICK if hit == 1 else M.h[k] + TICK)
                f = sim(M, idx, k, -hit, M.h[k] + TICK if hit == 1 else M.l[k] - TICK)
                if a is not None:
                    sigs.append((d, k, hit, a, f))
                break
    return sigs


def b2_ib_fail(M, R):
    sigs = []
    for d, idx in R.items():
        ib = idx[(M.mod[idx] >= 570) & (M.mod[idx] < 630)]
        if len(ib) < 12:
            continue
        ibh, ibl = M.h[ib].max(), M.l[ib].min()
        mid = (ibh + ibl) / 2
        rest = idx[(M.mod[idx] >= 630) & (M.mod[idx] < 870)]
        for n, k in enumerate(rest):
            side = 1 if M.h[k] > ibh else (-1 if M.l[k] < ibl else 0)   # +1 = broke up
            if not side:
                continue
            win = rest[n:n + 3]
            ext = M.h[k] if side == 1 else M.l[k]
            got = None
            for j in win:
                ext = max(ext, M.h[j]) if side == 1 else min(ext, M.l[j])
                if (side == 1 and M.c[j] < ibh) or (side == -1 and M.c[j] > ibl):
                    got = j; break
            if got is not None:
                dd = -side
                stop = ext + TICK if dd == -1 else ext - TICK
                a = sim(M, idx, got, dd, stop, tgt=mid)
                # flipped = go WITH the extension, stop 1 tick past the opposite side of the reclaim bar, 2R
                fstop = (M.l[got] - TICK) if side == 1 else (M.h[got] + TICK)
                f = sim(M, idx, got, side, fstop)
                if a is not None:
                    sigs.append((d, got, dd, a, f))
            break                                                       # first break of the day decides
    return sigs


# ------------------------------------------------------------------------------------------------ LIT add-ons
def lit_rows(M, T):
    return [{"day": t["day"], "pnl": t["pnl"], "dir": t["dir"], "e": t["ext_i"], "ei": t["entry_i"],
             "t_ext": int(M.t[t["ext_i"]]), "t_ent": int(M.t[t["entry_i"]])} for t in T]


def addon_report(rows, keep, wk, spans=None):
    res = {}
    ok = True
    for nm, _, _ in SPANS:
        if spans and nm not in spans:
            continue
        R = [x for x in rows if span_of(x["day"]) == nm]
        K = [x for x, k in zip(rows, keep) if k and span_of(x["day"]) == nm]
        S = [x for x, k in zip(rows, keep) if not k and span_of(x["day"]) == nm]
        base, kept, skip = stats([x["pnl"] for x in R], wk[nm]), stats([x["pnl"] for x in K], wk[nm]), stats([x["pnl"] for x in S], wk[nm])
        res[nm] = {"all LIT": base, "kept": kept, "skipped": skip, "gain$": kept.get("net$", 0) - base.get("net$", 0)}
        ok = ok and res[nm]["gain$"] > 0
    res["verdict"] = "PASS" if ok else "REJECTED"
    return res


def bvc(close, vol, win=100):
    dp = np.diff(close, prepend=close[0])
    sd = pd.Series(dp).shift(1).rolling(win, min_periods=30).std().values
    z = np.where(sd > 0, dp / np.where(sd > 0, sd, 1), 0.0)
    phi = 0.5 * (1 + np.vectorize(math.erf)(z / math.sqrt(2)))
    return vol * (2 * phi - 1)


def poor_flags(M, R):
    """day -> (rth_high, high_poor, rth_low, low_poor)."""
    out = {}
    for d, idx in R.items():
        hi, lo = M.h[idx].max(), M.l[idx].min()
        per = (M.mod[idx] - 570) // 30
        ph = sum(1 for p in np.unique(per) if M.h[idx[per == p]].max() >= hi - 2 * TICK)
        pl = sum(1 for p in np.unique(per) if M.l[idx[per == p]].min() <= lo + 2 * TICK)
        out[d] = (hi, ph >= 2, lo, pl >= 2)
    return out


def main():
    M, T, m1 = load()
    wk = span_weeks(M)
    R = rth_index(M)
    rows = lit_rows(M, T)
    lit_daily = pd.Series([x["pnl"] for x in rows], index=[x["day"] for x in rows]).groupby(level=0).sum()
    out = {"made": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "pre_registered": "see docstring; committed before the first run",
           "lit_trades": len(rows), "weeks": wk}

    s1 = b1_lvn(M, R)
    out["B1 LVN rejection"] = standalone_report(M, s1, wk, lit_daily)
    s2 = b2_ib_fail(M, R)
    out["B2 IB failed extension"] = standalone_report(M, s2, wk, lit_daily)

    # B3 poor extremes
    PF = poor_flags(M, R)
    days = sorted(R)
    prev = {d: p for p, d in zip(days[:-1], days[1:])}
    keep, tagged = [], 0
    for x in rows:
        p = prev.get(x["day"])
        swept_poor = False
        if p:
            hi, hp, lo, lp = PF[p]
            if x["dir"] == -1 and M.h[x["e"]] >= hi and hp:
                swept_poor = True
            if x["dir"] == 1 and M.l[x["e"]] <= lo and lp:
                swept_poor = True
        tagged += swept_poor
        keep.append(not swept_poor)
    b3 = addon_report(rows, keep, wk)
    b3["trades_tagged"] = tagged
    rev = {"poor": [0, 0], "not_poor": [0, 0]}
    for p, d in zip(days[:-1], days[1:]):
        hi, hp, lo, lp = PF[p]
        nx = R[d]
        for lvl, poor, up in ((hi, hp, True), (lo, lp, False)):
            o = M.o[nx[0]]
            if (up and o >= lvl) or (not up and o <= lvl):
                continue                                   # opened beyond it: not a revisit test
            hit = (M.h[nx].max() >= lvl) if up else (M.l[nx].min() <= lvl)
            key = "poor" if poor else "not_poor"
            rev[key][0] += int(hit); rev[key][1] += 1
    b3["next_RTH_revisit_rate"] = {k: {"revisited%": round(100 * a / b, 1) if b else None, "n": b} for k, (a, b) in rev.items()}
    out["B3 poor high/low LIT skip"] = b3

    # B4 BVC delta, 5m (all spans) and 1m (2026)
    d5 = bvc(M.c, M.v)
    k1 = [np.sum(d5[x["e"] - 2:x["e"] + 1]) * x["dir"] > 0 for x in rows]
    k4 = [np.sum(d5[x["e"]:max(x["e"] + 1, x["ei"])]) * x["dir"] > 0 for x in rows]
    out["B4 S1' BVC-5m divergence (take div only)"] = addon_report(rows, k1, wk)
    out["B4 S4' BVC-5m confirmation (skip refuted)"] = addon_report(rows, k4, wk)
    t1 = m1.time.values
    d1 = bvc(m1.close.values.astype(float), m1.volume.values.astype(float))
    cs = np.concatenate([[0], np.cumsum(d1)])

    def win(a, b):
        i, j = np.searchsorted(t1, a), np.searchsorted(t1, b)
        return cs[j] - cs[i], j - i
    r26 = [x for x in rows if x["day"] >= "2025-12-28"]
    k1m, k4m, have = [], [], []
    for x in r26:
        a1, n1 = win(x["t_ext"] - 600, x["t_ext"] + 300)
        a4, n4 = win(x["t_ext"], x["t_ent"])
        have.append(n1 >= 10)
        k1m.append(a1 * x["dir"] > 0); k4m.append(a4 * x["dir"] > 0)
    out["B4 S1' BVC-1m divergence (take div only)"] = addon_report(r26, k1m, wk, spans=("2026 H1", "2026 H2"))
    out["B4 S4' BVC-1m confirmation (skip refuted)"] = addon_report(r26, k4m, wk, spans=("2026 H1", "2026 H2"))
    out["B4 1m coverage"] = "%d of %d 2026 LIT trades have >= 10 1m bars in the S1 window" % (sum(have), len(r26))

    # B5 sweep participation
    k5 = []
    for x in rows:
        e = x["e"]
        base = M.v[max(0, e - 20):e].mean() if e > 0 else 0
        k5.append(base > 0 and M.v[e] / base >= 1.0)
    out["B5 sweep relvol >= 1 (skip thin sweeps)"] = addon_report(rows, k5, wk)

    # B6 1m absorption print at the sweep extreme (2026)
    vm = pd.Series(m1.volume.values.astype(float)).shift(1).rolling(60, min_periods=30).mean().values
    k6 = []
    for x in r26:
        i, j = np.searchsorted(t1, x["t_ext"]), np.searchsorted(t1, x["t_ext"] + 300)
        if j - i < 3:
            k6.append(False); continue
        seg = m1.iloc[i:j]
        q = int(seg.low.values.argmin()) if x["dir"] == 1 else int(seg.high.values.argmax())
        r_ = seg.iloc[q]
        rng = r_.high - r_.low
        far = (r_.close >= r_.low + rng / 2) if x["dir"] == 1 else (r_.close <= r_.low + rng / 2)
        k6.append(bool(rng > 0 and vm[i + q] > 0 and r_.volume >= 2 * vm[i + q] and far))
    out["B6 1m absorption print at sweep (take absorbed only)"] = addon_report(r26, k6, wk, spans=("2026 H1", "2026 H2"))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1, default=str)
    for k, v in out.items():
        if isinstance(v, dict) and "verdict" in v:
            print("\n==", k, "->", v["verdict"])
            for sp, row in v.items():
                print("  ", sp, row)
    return out


if __name__ == "__main__":
    main()
