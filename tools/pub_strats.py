"""Famous published strategies, as their authors specify them, on CME NQ1! (and ES1! where the rule needs it).
Owner 2026-11-17: "find other people's strategies that are successful and replicate them." Write-up:
research/writeups/public-strategies-2026-11-17.md. Numbers: research/quant/pub_strats.json. Paper research only.

Already done before (tools/quant_anoms.py, quant-anomalies.md, 2026-10-23): Gao intraday momentum, overnight drift, turn of
the month, pre-FOMC drift as point tests with placebos. Here they are re-scored the same way as the new ones (win %, PF,
max DD, MFFU eval pass speed, LIT correlation) and, new, in an MFFU-legal (flat by 16:10 ET) form. New families: Connors
RSI(2), time-series momentum (Moskowitz-Ooi-Pedersen 12-month and a 20/60-day trend), Crabel NR7 / NR4 breakouts.

Data: data/NQ_5m.csv (TradingView CME NQ1!, additive back-adjusted, point moves exact; 2021-11 -> 2026-10-16), ES_5m.csv
(TV ES1!, 2025-04 ->). Prices are 5m bar OPENS (16:00 = the 16:00 bar's open = the cash close). Costs: $1.90 a micro round
trip + 1 tick slippage each way (MNQ: 1.45 pts a micro a trade; MES: 0.88 pts). No tuning: every rule is fixed here.
Size: intraday (MFFU-legal) trades risk $500 against a volatility stop max(10, 1.5 x ATR20 x sqrt(hold h / 23)) pts
(1-40 micros) - no stop is placed unless the rule has one (NR7: the far side). Multi-day / overnight holds: 1 micro
(MFFU forbids holding past 16:10 ET, so those cannot run on an MFFU account at all; $ shown for a personal account).

    python -X utf8 tools/pub_strats.py      # -> research/quant/pub_strats.json + printed table
"""
from __future__ import annotations

import json
import math
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.quant_anoms import Bars, FOMC  # noqa: E402

OUT = os.path.join(ROOT, "research", "quant", "pub_strats.json")
SPANS = {"2021-25": ("2021-11-08", "2025-12-31"), "2026H1": ("2026-01-01", "2026-06-30"),
         "2026H2": ("2026-07-01", "2026-10-31")}
PT = {"NQ": 2.0, "ES": 5.0}           # micro $ a point
COST_PTS = {"NQ": 0.5 + 1.90 / 2.0, "ES": 0.5 + 1.90 / 5.0}
RISK = 500.0
MAXQ = 40


class Strat:
    def __init__(self, B, sym):
        self.B, self.sym = B, sym
        self.S = B.full
        self.k = {s: i for i, s in enumerate(self.S)}

    def px(self, s, hm):
        return self.B.px(s, hm)

    def vol_q(self, s, hold_h):
        a = self.B.atr.get(s)
        if a is None:
            return None
        stop = max(10.0, 1.5 * a * math.sqrt(hold_h / 23.0))
        return int(max(1, min(MAXQ, RISK // (stop * PT[self.sym]))))

    def trade(self, s0, hm0, s1, hm1, d, q, px0=None, px1=None):
        """Legs marked at each 16:00 so a multi-day hold has a daily P&L (for drawdown). Cost on the exit leg."""
        e = self.px(s0, hm0) if px0 is None else px0
        x = self.px(s1, hm1) if px1 is None else px1
        if e is None or x is None:
            return None
        legs = []
        if s0 == s1:
            legs.append((s1, d * (x - e)))
        else:
            k0, k1 = self.k[s0], self.k[s1]
            prev = e
            for kk in range(k0, k1):
                m = self.px(self.S[kk], 960)
                legs.append((self.S[kk], d * (m - prev)))
                prev = m
            legs.append((s1, d * (x - prev)))
        c = COST_PTS[self.sym]
        legs[-1] = (legs[-1][0], legs[-1][1] - c)
        usd = [(s, p * q * PT[self.sym]) for s, p in legs]
        return {"s0": s0, "s1": s1, "d": d, "q": q, "pts": d * (x - e) - c, "usd": sum(u for _, u in usd), "legs": usd}


# ------------------------------------------------------------------------------------------------ the strategies
def gao(st, mode="pub"):
    """Gao-Han-Li-Zhou 2018: r1 = prev 16:00 close -> 10:00; trade the last half hour 15:30 -> 16:00 in its sign.
    'r12': sign(r1 + r12) with r12 = 15:00 -> 15:30 (the paper's second predictor).
    'fade': pre-registered here from quant-anomalies' 2025-26 lead: fade prev close -> 15:30 in the last half hour."""
    T = []
    for k in range(1, len(st.S)):
        s, p = st.S[k], st.S[k - 1]
        c0, a10, a1500, a1530 = st.px(p, 960), st.px(s, 600), st.px(s, 900), st.px(s, 930)
        if None in (c0, a10, a1500, a1530):
            continue
        if mode == "pub":
            sig = a10 - c0
        elif mode == "r12":
            sig = (a10 - c0) / c0 + (a1530 - a1500) / a1500
        else:
            sig = -(a1530 - c0)
        if sig == 0:
            continue
        q = st.vol_q(s, 0.5)
        t = q and st.trade(s, 930, s, 960, 1 if sig > 0 else -1, q)
        if t:
            T.append(t)
    return T


def fomc(st, mode="pub"):
    """Lucca-Moench 2015: long 14:00 the day before -> 13:55 (just before the 14:00 statement). Overnight hold.
    'rth': 09:30 -> 13:55 on the FOMC day. 'two': day-before 09:30 -> 16:00 + FOMC day 09:30 -> 13:55 (both legal)."""
    T = []
    for f in FOMC:
        if f not in st.k or st.k[f] == 0:
            continue
        p = st.S[st.k[f] - 1]
        if mode == "pub":
            t = st.trade(p, 840, f, 835, 1, 1)
            T += [t] if t else []
        else:
            if mode == "two":
                q = st.vol_q(p, 6.5)
                t = q and st.trade(p, 570, p, 960, 1, q)
                T += [t] if t else []
            q = st.vol_q(f, 4.4)
            t = q and st.trade(f, 570, f, 835, 1, q)
            T += [t] if t else []
    return T


def month_days(st):
    by = {}
    for s in st.S:
        by.setdefault(s[:7], []).append(s)
    return [by[m] for m in sorted(by)]


def tom(st, mode="pub"):
    """Lakonishok-Smidt 1988 / McConnell-Xu 2008: long the last trading day of the month through day +3.
    'pub': 16:00 of day -2 -> 16:00 of day +3 (overnight). 'rth': day-trade 09:30 -> 16:00 on days -1, +1, +2, +3."""
    M = month_days(st)
    T = []
    for a, b in zip(M[:-1], M[1:]):
        if len(a) < 3 or len(b) < 3 or a[-1] != st.S[st.k[b[0]] - 1]:
            continue
        if mode == "pub":
            t = st.trade(a[-2], 960, b[2], 960, 1, 1)
            T += [t] if t else []
        else:
            for s in (a[-1], b[0], b[1], b[2]):
                q = st.vol_q(s, 6.5)
                t = q and st.trade(s, 570, s, 960, 1, q)
                T += [t] if t else []
    return T


def overnight(st, mode="pub"):
    """Cliff-Cooper-Gulen 2008 / Lou-Polk-Skouras 2019: long 16:00 -> next 09:30, flat in the day.
    'ls': also short the day session 09:30 -> 16:00. 'dayshort': only the short day leg (MFFU-legal)."""
    T = []
    for k in range(len(st.S) - 1):
        s, n = st.S[k], st.S[k + 1]
        if mode in ("pub", "ls"):
            t = st.trade(s, 960, n, 570, 1, 1)
            T += [t] if t else []
        if mode in ("ls", "dayshort"):
            q = 1 if mode == "ls" else st.vol_q(n, 6.5)
            t = q and st.trade(n, 570, n, 960, -1, q)
            T += [t] if t else []
    return T


def closes(st):
    return np.array([st.px(s, 955) for s in st.S], float)


def rsi_wilder(c, n=2):
    d = np.diff(c, prepend=c[0])
    up, dn = np.clip(d, 0, None), np.clip(-d, 0, None)
    au, ad = np.zeros(len(c)), np.zeros(len(c))
    au[n], ad[n] = up[1:n + 1].mean(), dn[1:n + 1].mean()
    for i in range(n + 1, len(c)):
        au[i] = (au[i - 1] * (n - 1) + up[i]) / n
        ad[i] = (ad[i - 1] * (n - 1) + dn[i]) / n
    r = np.where(ad == 0, 100.0, 100 - 100 / (1 + au / np.where(ad == 0, 1, ad)))
    r[:n] = 50
    return r


def sma(c, n):
    out = np.full(len(c), np.nan)
    cs = np.cumsum(c)
    out[n - 1:] = (cs[n - 1:] - np.concatenate([[0], cs[:-n]])) / n
    return out


def connors(st, mode="pub"):
    """Connors & Alvarez (Short Term Trading Strategies That Work, 2008): long at the close when RSI(2) < 10 and the close
    > 200-day SMA; exit at the close when close > 5-day SMA. 'Close' = the 15:55 price. 'pub' holds overnight (1 micro).
    'rth': same days in the trade, but only the 09:30 -> 15:55 part of each (MFFU-legal). 'ls': plus the mirror short
    (RSI(2) > 90 below the 200-day SMA, exit close < 5-day SMA), overnight."""
    c = closes(st)
    r, m200, m5 = rsi_wilder(c), sma(c, 200), sma(c, 5)
    T = []
    sides = (1, -1) if mode == "ls" else (1,)
    for d in sides:
        i = 200
        while i < len(c) - 1:
            ok = (r[i] < 10 and c[i] > m200[i]) if d == 1 else (r[i] > 90 and c[i] < m200[i])
            if not ok:
                i += 1
                continue
            j = i + 1
            while j < len(c) - 1 and not ((c[j] > m5[j]) if d == 1 else (c[j] < m5[j])):
                j += 1
            if mode == "rth":
                for kk in range(i + 1, j + 1):
                    s = st.S[kk]
                    q = st.vol_q(s, 6.4)
                    t = q and st.trade(s, 570, s, 955, d, q)
                    T += [t] if t else []
            else:
                t = st.trade(st.S[i], 955, st.S[j], 955, d, 1)
                T += [t] if t else []
            i = j + 1
    return T


def tsmom(st, mode="pub"):
    """Moskowitz-Ooi-Pedersen 2012: at each month end go long (short) for the next month if the past 12-month return is
    up (down). 1 micro, overnight. 'fast': daily, long if SMA20 > SMA60 else short, held close to close (overnight).
    'fast_rth': the 'fast' signal from the prior close, traded 09:30 -> 15:55 each day (MFFU-legal)."""
    c = closes(st)
    T = []
    if mode == "pub":
        M = month_days(st)
        ends = [m[-1] for m in M]
        for a, b in zip(ends[:-1], ends[1:]):
            i = st.k[a]
            if i < 252:
                continue
            d = 1 if c[i] > c[i - 252] else -1
            t = st.trade(a, 955, b, 955, d, 1)
            T += [t] if t else []
        return T
    f, s_ = sma(c, 20), sma(c, 60)
    if mode == "fast":
        i = 60
        while i < len(c) - 1:
            d = 1 if f[i] > s_[i] else -1
            j = i + 1
            while j < len(c) - 1 and (1 if f[j] > s_[j] else -1) == d:
                j += 1
            t = st.trade(st.S[i], 955, st.S[j], 955, d, 1)
            T += [t] if t else []
            i = j
        return T
    for i in range(60, len(c) - 1):
        d = 1 if f[i] > s_[i] else -1
        s = st.S[i + 1]
        q = st.vol_q(s, 6.4)
        t = q and st.trade(s, 570, s, 955, d, q)
        T += [t] if t else []
    return T


def nr(st, mode="nr7"):
    """Crabel 1990 (Day Trading with Short Term Price Patterns and Opening Range Breakout): after an NR7 day (the
    narrowest 09:30-16:00 range of the last 7), next day buy stop 1 tick above its high / sell stop 1 tick below its low
    (first touched, 09:30-15:55), stop = 1 tick beyond the other side, exit 16:00. 'nr4': the 4-day version. 'nr7id':
    NR7 that is also an inside day (Crabel / Raschke)."""
    B = st.B
    H, L = {}, {}
    for s in st.S:
        a, b = B.i(s, 570), B.i(s, 955)
        H[s], L[s] = float(B.h[a:b + 1].max()), float(B.l[a:b + 1].min())
    n = 4 if mode == "nr4" else 7
    T = []
    tick = 0.25
    for k in range(n, len(st.S) - 1):
        s = st.S[k]
        rng = [H[x] - L[x] for x in st.S[k - n + 1:k + 1]]
        if rng[-1] > min(rng):
            continue
        if mode == "nr7id" and not (H[s] < H[st.S[k - 1]] and L[s] > L[st.S[k - 1]]):
            continue
        nx = st.S[k + 1]
        up, dn = H[s] + tick, L[s] - tick
        a, b = B.i(nx, 570), B.i(nx, 960)
        stop_pts = up - dn
        q = int(max(1, min(MAXQ, RISK // (stop_pts * PT[st.sym]))))
        side = None
        for i in range(a, b):
            hu, hd = B.h[i] >= up, B.l[i] <= dn
            if hu and hd:
                break                                   # both in the first bar: ambiguous, skip the day
            if hu or hd:
                side, i0 = (1, i) if hu else (-1, i)
                break
        if side is None:
            continue
        e = max(up, B.o[i0]) if side == 1 else min(dn, B.o[i0])
        sp = dn if side == 1 else up
        x, kx = None, None
        for i in range(i0, b):
            if (side == 1 and B.l[i] <= sp and i > i0) or (side == -1 and B.h[i] >= sp and i > i0):
                x = min(sp, B.o[i]) if side == 1 else max(sp, B.o[i])
                break
        if x is None:
            x = B.o[b]
        t = st.trade(nx, 570, nx, 960, side, q, px0=e, px1=x)
        T += [t] if t else []
    return T


# ------------------------------------------------------------------------------------------------ scoring
def in_span(s, span):
    a, b = SPANS[span]
    return a <= s <= b


def daily(T):
    D = {}
    for t in T:
        for s, u in t["legs"]:
            D[s] = D.get(s, 0.0) + u
    return D


def stats(T, st, span):
    TT = [t for t in T if in_span(t["s1"], span)]
    sess = [s for s in st.S if in_span(s, span)]
    if not sess:
        return None
    D = daily(T)
    eq, pk, dd = 0.0, 0.0, 0.0
    for s in sess:
        eq += D.get(s, 0.0)
        pk = max(pk, eq)
        dd = min(dd, eq - pk)
    w = [t["usd"] for t in TT if t["usd"] > 0]
    lo = [t["usd"] for t in TT if t["usd"] <= 0]
    net = sum(t["usd"] for t in TT)
    n = len(TT)
    pts = [t["pts"] for t in TT]
    tstat = (np.mean(pts) / (np.std(pts, ddof=1) / math.sqrt(n))) if n > 2 and np.std(pts) > 0 else 0.0
    return {"trades": n, "per_week": round(n / (len(sess) / 5), 2), "win_pct": round(100 * len(w) / n, 1) if n else None,
            "pf": round(sum(w) / -sum(lo), 2) if lo and sum(lo) < 0 else None, "net": round(net),
            "per_month": round(net / (len(sess) / 21)), "max_dd": round(dd), "pts_t": round(float(tstat), 2),
            "sessions": len(sess)}


def evals(D, st, span, rapid=False, horizon=None):
    """Start an MFFU 50K eval on every session of the span: $3,000 target, $2,000 EOD trailing floor (locks at
    +$100 once the EOD high reaches +$2,100). rapid: also the best day <= 30% of the profit at the pass."""
    S = st.S
    starts = [i for i, s in enumerate(S) if in_span(s, span)]
    res = []
    for i0 in starts:
        bal, hi, best, out = 0.0, 0.0, 0.0, None
        for j in range(i0, len(S) if horizon is None else min(len(S), i0 + horizon)):
            p = D.get(S[j], 0.0)
            bal += p
            best = max(best, p)
            floor = min(hi - 2000.0, 100.0)
            if bal <= floor:
                out = ("F", j - i0 + 1)
                break
            hi = max(hi, bal)
            if bal >= 3000.0 and (not rapid or best <= 0.30 * bal):
                out = ("P", j - i0 + 1)
                break
        res.append(out)
    n = len(res)
    P = [x[1] for x in res if x and x[0] == "P"]
    F = [x for x in res if x and x[0] == "F"]
    return {"starts": n, "pass_pct": round(100 * len(P) / n, 1), "fail_pct": round(100 * len(F) / n, 1),
            "median_sessions": int(np.median(P)) if P else None}


def lit_days():
    d = json.load(open(os.path.join(ROOT, "research", "lab", "backtest_live.json"), encoding="utf-8"))
    return {x["date"]: float(x["pnl"]) for x in d["days"]}


def corr(D, LD, st, span=None):
    ss = [s for s in st.S if s in LD and (span is None or in_span(s, span))]
    a = np.array([D.get(s, 0.0) for s in ss])
    b = np.array([LD[s] for s in ss])
    c = float(np.corrcoef(a, b)[0, 1]) if a.std() > 0 and b.std() > 0 else 0.0
    off = [D.get(s, 0.0) for s in ss if LD[s] <= 0]
    return round(c, 2), round(float(np.mean(off)) * 21) if off else None


CELLS = [
    ("gao_pub", "NQ", gao, "pub", True), ("gao_r12", "NQ", gao, "r12", True), ("gao_fade", "NQ", gao, "fade", True),
    ("fomc_pub", "NQ", fomc, "pub", False), ("fomc_rth", "NQ", fomc, "rth", True), ("fomc_two", "NQ", fomc, "two", True),
    ("tom_pub", "NQ", tom, "pub", False), ("tom_rth", "NQ", tom, "rth", True), ("tom_pub_es", "ES", tom, "pub", False),
    ("on_pub", "NQ", overnight, "pub", False), ("on_ls", "NQ", overnight, "ls", False),
    ("on_dayshort", "NQ", overnight, "dayshort", True),
    ("rsi2_pub", "NQ", connors, "pub", False), ("rsi2_rth", "NQ", connors, "rth", True), ("rsi2_ls", "NQ", connors, "ls", False),
    ("tsmom12_pub", "NQ", tsmom, "pub", False), ("tsmom_fast", "NQ", tsmom, "fast", False),
    ("tsmom_fast_rth", "NQ", tsmom, "fast_rth", True), ("tsmom_fast_es", "ES", tsmom, "fast", False),
    ("nr7_pub", "NQ", nr, "nr7", True), ("nr4", "NQ", nr, "nr4", True), ("nr7_id", "NQ", nr, "nr7id", True),
]


def main():
    bars = {"NQ": Strat(Bars("NQ"), "NQ"), "ES": Strat(Bars("ES"), "ES")}
    LD = lit_days()
    out = {}
    for cid, sym, fn, mode, legal in CELLS:
        st = bars[sym]
        T = fn(st, mode)
        D = daily(T)
        row = {"sym": sym, "mffu_legal": legal, "spans": {}}
        for sp in SPANS:
            s = stats(T, st, sp)
            if s is None:
                continue
            if legal:
                s["eval_builder_1mo"] = evals(D, st, sp, horizon=21)
                s["eval_builder"] = evals(D, st, sp)
                s["eval_rapid"] = evals(D, st, sp, rapid=True)
            if sym == "NQ":
                s["lit_corr"], s["usd_mo_on_lit_bad_days"] = corr(D, LD, st, sp)
            row["spans"][sp] = s
        if sym == "NQ":
            row["lit_corr_all"] = corr(D, LD, st)[0]
        out[cid] = row
        print(cid, sym, "legal" if legal else "overnight")
        for sp, s in row["spans"].items():
            e = (f" | B1mo {s['eval_builder_1mo']['pass_pct']}/{s['eval_builder_1mo']['fail_pct']}"
                 f" Bever {s['eval_builder']['pass_pct']}/{s['eval_builder']['fail_pct']} med {s['eval_builder']['median_sessions']}"
                 f" R {s['eval_rapid']['pass_pct']}/{s['eval_rapid']['fail_pct']} med {s['eval_rapid']['median_sessions']}"
                 ) if legal else ""
            print(f"   {sp:7s} n {s['trades']:4d} /wk {s['per_week']:5.2f} win {s['win_pct']} PF {s['pf']} net {s['net']:7d}"
                  f" /mo {s['per_month']:6d} dd {s['max_dd']:7d} t {s['pts_t']:5.2f} corr {s.get('lit_corr')}{e}")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"cells": len(CELLS), "spans": SPANS, "risk_usd": RISK, "results": out}, open(OUT, "w"), indent=1)
    print("cells", len(CELLS), "->", OUT)


if __name__ == "__main__" and len(sys.argv) == 1:
    main()


def extra():
    """Checks for the one cell positive in all three spans with a sane count (tom_rth): a placebo (4 random sessions a
    month, same long 09:30 -> 16:00 trade, same size; 1,000 draws) and the eval at 2x / 3x size. Also the plain
    every-day long RTH (the drift TOM rides on)."""
    st = Strat(Bars("NQ"), "NQ")
    T = tom(st, "rth")
    allday = []
    for s in st.S:
        q = st.vol_q(s, 6.5)
        t = q and st.trade(s, 570, s, 960, 1, q)
        if t:
            allday.append(t)
    byd = {t["s1"]: t["usd"] for t in allday}
    rng = np.random.default_rng(7)
    M = month_days(st)
    res = {"every_day_long_rth": {sp: stats(allday, st, sp) for sp in SPANS}, "placebo_p": {}, "eval_scaled": {}}
    for sp in SPANS:
        act = sum(t["usd"] for t in T if in_span(t["s1"], sp))
        mm = [m for m in M if in_span(m[0], sp) or in_span(m[-1], sp)]
        sims = []
        for _ in range(1000):
            tot = 0.0
            for m in mm:
                pool = [s for s in m if in_span(s, sp) and s in byd]
                if pool:
                    pick = rng.choice(len(pool), size=min(len(pool), 2), replace=False)
                    tot += sum(byd[pool[i]] for i in pick)
            sims.append(tot * len([t for t in T if in_span(t["s1"], sp)]) / max(1, 2 * len(mm)))
        res["placebo_p"][sp] = round(float(np.mean(np.array(sims) >= act)), 3)
        D = daily(T)
        for x in (2, 3):
            Dx = {k: v * x for k, v in D.items()}
            res["eval_scaled"][f"{sp}_x{x}"] = {"builder": evals(Dx, st, sp), "rapid": evals(Dx, st, sp, rapid=True)}
    print(json.dumps(res, indent=1, default=str)[:4000])
    d = json.load(open(OUT))
    d["tom_rth_checks"] = res
    json.dump(d, open(OUT, "w"), indent=1)


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "extra":
    extra()
