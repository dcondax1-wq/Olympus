"""Third strategy (2026-11-19, night-newstrat): a NEW NQ strategy that adds money WITHOUT overlapping Zlarior (LIT: London /
NY sweep reversals, engine/lit.py) or ATLAS (NY EMA / MACD / S-R members, engine/second.py). Paper research only: edits no
engine / model / UI file, arms nothing. Write-up: research/writeups/third-strategy-2026-11-18.md. Numbers:
research/second/third_strategy.json.

Read first (docs/TESTED_AND_REJECTED.md + research/writeups): ORBs, gap fades, VWAP / band / RSI / ATR-stretch / turtle-soup /
round-number fades (scalp-mean-reversion: 87,920 configs), level sweep-reclaims in every window (allday: 7,800; stophunt:
28.7M; strategy tree: 1.13M; Data City: 114k), the lunch squeeze / PM continuation / value-area / 80% rule / London fade
(new-strategy hunt), the famous published edges (Gao, pre-FOMC, turn of month, overnight drift, RSI(2), TSMOM, NR7),
the draw-on-liquidity bias trade (hq-bias), exhaustion fades (hq-reversion), BLITZ (noise area). NOT tested before (grep
of the write-ups + tools/allday.py, whose 18:00 window had no "prior window"):

Three families, hypotheses written BEFORE the first run (every cell is counted; nothing added after a look):

  PCM  Post-close move into the Globex reopen (Asia, a time LIT / ATLAS never trade). 16:00-17:00 ET is when the mega-cap
       earnings / after-hours news hits NQ in a thin market (MFFU must be flat by 16:10, so nobody here trades it). H: a big
       16:00 -> 17:00 move (|M| >= k x its own 20-day mean |M|) either keeps going at the 18:00 reopen (information,
       "follow") or gives part of it back (thin-market overreaction, "fade"). Entry at the 18:00 open ("open") or on the
       first 5m close beyond the 18:00-18:15 range in the trade's direction until 20:00 ("or15"). Stop 1 tick beyond the
       16:00-17:00 window's far extreme (open entry: the move's origin for "follow", the move's extreme for "fade") or the
       18:00-18:15 range's other side (or15). Target 1R / 2R, or for "fade" the 16:00 close (full give-back, >= 1R).
       Out at 09:25 (before the NY open) or 15:55. Mon-Thu evenings only (Friday's move meets a weekend). k 0.5/1/1.5/2.
       Nearest old idea: LIT's 18:00 F-BoS (a false break of the 16:30-17:00 build-up, a LIT entry) - here a standalone
       follow / fade of the whole post-close MOVE.
  CAM  Camarilla + floor-trader pivots (RTH; a classic published day-trading method never coded here; only quarterly
       pivots were tried, as LIT sweep levels). From the prior RTH session's H / L / C (R = H - L): H3 = C + 1.1R/4,
       L3 = C - 1.1R/4, H4 = C + 1.1R/2, L4 = C - 1.1R/2; floor P = (H+L+C)/3, R1 = 2P - L, S1 = 2P - H.
       "fade3": a probe beyond H3 (L3) that closes back inside within 3 bars -> fade (stop 1 tick beyond the probe high /
       low "ext", or beyond H4 / L4 "h4"; target 2R / C / the far L3-H3, >= 1R); open filter: the 09:30 open inside L3-H3
       ("in") or any. "break4": the first 5m close beyond H4 (L4) -> with it (stop 1 tick beyond H3 / L3 or the breakout
       bar; 2R / 3R / 15:55). "fade1": a probe beyond R1 (S1) back inside within 3 bars -> fade to P (>= 1R) or 2R, stop
       beyond the probe. Entries 09:30 -> 11:30 or 15:00, one a day.
  TDS  TD Sequential setup-9 exhaustion (DeMark; never coded here). On 15m or 1h bars of the whole CME day: 9 closes in a
       row above (below) the close 4 bars earlier, after a price flip -> fade at the 9th close ("bar9") or at the first
       counter close within 3 bars ("turn"); "perfect" = bar 8 or 9 high >= bars 6 and 7 highs (mirror). Stop 1 tick
       beyond the setup's extreme (the TDST risk level); target 1R / 2R / the close of setup bar 1 (>= 1R). Signals any
       hour 18:00-15:30 ("all") or RTH 09:30-15:30 only ("rth"); one a trading day; out 15:55; stops over 150 pts
       skipped (1 micro at $500 is already $300+).

Execution (own 24h walk on CME NQ1! 5m, 2021-10 -> 2026-10-16, back-adjusted TradingView export, futures only): signal on
a bar close, entry at the next 5m open + 1 tick, a stop touched in a bar fills at the stop (or the open through it) - 1
tick, a target is a limit that needs a trade-through, stop and target in one bar = stop, time exit at the open of the exit
bar - 1 tick, never past 15:55 (MFFU flat by 16:10) or through the 17:00 halt. Stops under 8 pts widened to 8. $1.90 a
micro. $500 risk a trade: micros = floor(500 / (stop x $2 + $1.90)), 1-40 (size follows the stop). The trading day is the
CME day (18:00 -> 17:00), so a 20:00 trade belongs to the next date.

Judging (same bar as the 2026-11-17 hunt): "holds" = n >= 5, net > 0 and PF >= 1.1 in each of H1 (2026 Jan-Jun), H2
(Jul-Oct 16), 2025, 2021-24. Chance = the same cells with coin-flip directions (stop / target mirrored), 10 seeds. Pick per
family on H1 only: n >= 20, PF >= 1.2, 2-4 trades a week, best H1 $ (also shown: the best H1 cell at any frequency, n >= 12,
PF >= 1.2). Then H2 / 2025 / 2021-24 read untouched + a 200-seed coin-flip placebo on H2 and 2021-25, daily correlation with
LIT (research/lab/backtest_live.json) and ATLAS (research/runs/atlas_base.json), winning days, and eval speed: its own MFFU
Builder 50K ($3,000 target, $2,000 EOD trailing, $400 a trade) and added to LIT's 50K eval days (LIT's daily $ + this at
$250 a trade), a start on every session, pass / fail within 10 and 40 sessions.

    python -X utf8 tools/third_strategy.py grid        # all cells + chance + pick detail -> research/second/third_strategy.json
    python -X utf8 tools/third_strategy.py register    # one ZEUS Lab experiment per family (kind new_strategy)
"""
from __future__ import annotations

import collections
import datetime as dt
import itertools
import json
import math
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "research", "second", "third_strategy.json")
DATE = "2026-11-19"
TICK, PV, COMM = 0.25, 2.0, 1.90
RISK_USD, MAXQ, MIN_STOP, MAX_STOP = 500.0, 40, 8.0, 150.0
SPANS = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-12-31"), "2025": ("2025-01-01", "2025-12-31"),
         "2021-24": ("2021-01-01", "2024-12-31"), "2026": ("2026-01-01", "2026-12-31"), "2021-25": ("2021-01-01", "2025-12-31")}
J4 = ("H1", "H2", "2025", "2021-24")
NAMES = {"pcm": "Post-close move into the 18:00 reopen (follow / fade)", "cam": "Camarilla / floor-trader pivots (RTH)",
         "tds": "TD Sequential 9-count exhaustion fade (15m / 1h, 24h)"}


# ================================================================================================ data (5m, whole CME day)
class Bars:
    def __init__(self):
        d = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
        et = pd.to_datetime(d.time, unit="s", utc=True).dt.tz_convert("America/New_York")
        self.t = d.time.to_numpy(np.int64)
        self.O, self.H, self.L, self.C = (d[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        self.hm = (et.dt.hour * 60 + et.dt.minute).to_numpy()
        self.cal = et.dt.date.astype(str).to_numpy()
        self.wd = et.dt.weekday.to_numpy()
        tday = (et + pd.Timedelta(hours=6)).dt.date.astype(str).to_numpy()       # CME day: 18:00 -> next date
        self.day = tday
        n = len(d)
        # exit indices: first bar of the same CME day at / after 15:55 and 09:25 (else the day's last bar)
        self.x1555 = np.empty(n, np.int64)
        self.x0925 = np.empty(n, np.int64)
        self.rth = {}                                         # day -> (i0, i1) of the 09:30..15:55 bars (full sessions)
        starts = np.r_[0, np.flatnonzero(tday[1:] != tday[:-1]) + 1, n]
        self.dayix = {}
        for a, b in zip(starts[:-1], starts[1:]):
            dd = tday[a]
            self.dayix[dd] = (a, b)
            hh = self.hm[a:b]
            rel = (hh - 1080) % 1440                         # minutes since 18:00
            for xm, arr in ((955, self.x1555), (565, self.x0925)):
                r = (xm - 1080) % 1440
                k = np.flatnonzero(rel >= r)
                arr[a:b] = a + k[0] if len(k) else b - 1
            r0 = np.flatnonzero(hh == 570)
            r1 = np.flatnonzero(hh == 955)
            if len(r0) and len(r1) and r1[0] - r0[0] == 77:
                self.rth[dd] = (a + r0[0], a + r1[0])
        self.days = sorted(self.rth)                          # trading days with a full RTH session (spans / weeks)


_B = {}


def B():
    if "b" not in _B:
        _B["b"] = Bars()
    return _B["b"]


def walk(i, d, stop, tgt, xi):
    """Signal on bar i's close -> enter at bar i+1's open + 1 tick in direction d. xi = index of the exit bar (exit at its
    open - 1 tick). Returns a trade dict or None."""
    b = B()
    e0 = i + 1
    if e0 >= xi:
        return None
    entry = b.O[e0] + d * TICK
    if (entry - stop) * d < MIN_STOP:
        stop = entry - d * MIN_STOP
    risk = (entry - stop) * d
    if risk <= 0 or risk > MAX_STOP:
        return None
    if tgt is not None and (tgt - entry) * d <= 0:
        return None
    mfe = mae = 0.0
    px, kind, j = None, None, None
    for jj in range(e0, xi):
        lo, hi, op = b.L[jj], b.H[jj], b.O[jj]
        if d == 1 and lo <= stop:
            px, kind, j = min(op, stop) - TICK, "STOP", jj
            break
        if d == -1 and hi >= stop:
            px, kind, j = max(op, stop) + TICK, "STOP", jj
            break
        mfe = max(mfe, (hi - entry) if d == 1 else (entry - lo))
        mae = min(mae, (lo - entry) if d == 1 else (entry - hi))
        if tgt is not None and ((d == 1 and hi > tgt) or (d == -1 and lo < tgt)):
            px, kind, j = tgt, "TARGET", jj
            break
    if px is None:
        j = xi
        px, kind = b.O[xi] - d * TICK, "TIME"
    return {"day": b.day[e0], "i": int(i), "dir": d, "entry": entry, "stop": stop, "risk": risk, "pts": (px - entry) * d,
            "exit": kind, "mfe": mfe / risk, "mae": -mae / risk, "bars": int(j - e0)}


def execute(sigs, flip=None):
    """sigs: (i, d, stop, tgt_or_None, R_or_None, xi). flip: rng -> coin-flip direction (stop / target mirrored)."""
    b = B()
    W = []
    for i, d, stop, tgt, R, xi in sigs:
        if i + 1 >= len(b.O):
            continue
        ref = b.O[i + 1]
        if flip is not None and flip.random() < 0.5:
            dist = (ref - stop) * d
            td = None if tgt is None else (tgt - ref) * d
            d = -d
            stop = ref - d * dist
            tgt = None if td is None else ref + d * td
        if tgt is None and R:
            entry = ref + d * TICK
            risk = max(MIN_STOP, (entry - stop) * d)
            tgt = entry + d * R * risk
        w = walk(i, d, stop, tgt, xi)
        if w is not None:
            W.append(w)
    return W


def book(W, usd=RISK_USD):
    T = []
    for w in W:
        q = min(MAXQ, int(usd // (w["risk"] * PV + COMM)))
        if q < 1:
            continue
        pnl = q * (w["pts"] * PV - COMM)
        T.append({"day": w["day"], "pnl": round(pnl, 2), "r": round(pnl / (w["risk"] * PV * q), 3), "risk_pts": round(w["risk"], 2),
                  "q": q, "dir": w["dir"], "exit": w["exit"], "low": round(min(0.0, -w["mae"] * w["risk"] * PV * q - COMM * q, pnl), 2)})
    return T


def span_days(span):
    a, z = SPANS[span]
    return [x for x in B().days if a <= x <= z]


def stats(T, span):
    days = span_days(span)
    if not days:
        return {"n": 0}
    ds = set(days)
    X = [t for t in T if t["day"] in ds]
    weeks = {dt.date.fromisoformat(x).isocalendar()[:2] for x in days}
    if not X:
        return {"n": 0, "net": 0, "pf": None, "tpw": 0.0}
    p = np.array([t["pnl"] for t in X])
    gl = -p[p < 0].sum()
    eq = np.cumsum(p)
    return {"n": len(X), "tpw": round(len(X) / len(weeks), 2), "win": round(100.0 * float((p > 0).mean()), 1),
            "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None, "net": round(float(p.sum())),
            "per_month": round(float(p.sum()) / (len(days) / 21.0)),
            "dd": round(float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min())),
            "avg_r": round(float(np.mean([t["r"] for t in X])), 3), "stop": round(float(np.median([t["risk_pts"] for t in X])), 1),
            "t": round(float(p.mean() / (p.std(ddof=1) / math.sqrt(len(p)))), 2) if len(p) > 2 and p.std() > 0 else None}


def score(T):
    return {s: stats(T, s) for s in SPANS}


def holds(S):
    return all(S[s].get("n", 0) >= 5 and S[s]["net"] > 0 and (S[s]["pf"] or 0) >= 1.1 for s in J4)


# ================================================================================================ PCM post-close move
def pcm_events():
    """(day_after, i_1800, M, rth_close, win_hi, win_lo) for Mon-Thu evenings with a 16:00-17:00 window and an 18:00 reopen
    the same evening. mean20 = the mean |M| of the 20 events before."""
    b = B()
    ev = []
    for dd, (a, z) in b.dayix.items():
        hh = b.hm[a:z]
        i55 = np.flatnonzero(hh == 955)
        i1655 = np.flatnonzero(hh == 1015)
        if not len(i55) or not len(i1655) or b.wd[a + i55[0]] > 3:
            continue
        i0, i1 = a + i55[0], a + i1655[0]
        nx = z                                                # the next CME day's first bar
        if nx >= len(b.O) or b.hm[nx] != 1080 or b.cal[nx] != b.cal[i1]:
            continue
        rc = b.C[i0]
        M = b.C[i1] - rc
        ev.append((b.day[nx], nx, M, rc, float(b.H[i0 + 1:i1 + 1].max()), float(b.L[i0 + 1:i1 + 1].min())))
    ev.sort(key=lambda x: x[1])
    out = []
    hist = collections.deque(maxlen=20)
    for e in ev:
        m20 = float(np.mean(hist)) if len(hist) >= 15 else np.nan
        hist.append(abs(e[2]))
        out.append(e + (m20,))
    return out


def pcm(cfg):
    b = B()
    out = []
    for day, nx, M, rc, whi, wlo, m20 in _cache("pcm_ev", pcm_events):
        if not np.isfinite(m20) or abs(M) < cfg["k"] * m20 or M == 0:
            continue
        s = 1 if M > 0 else -1
        d = s if cfg["dir"] == "follow" else -s
        xi = b.x0925[nx] if cfg["tx"] == "0925" else b.x1555[nx]
        if cfg["trig"] == "open":
            i = nx - 1                                        # "signal" at the 16:55 bar close -> entry at the 18:00 open
            far = (wlo if d == 1 else whi) if cfg["dir"] == "follow" else (wlo if d == 1 else whi)
            stop = far - d * TICK
        else:
            if nx + 3 >= len(b.O) or b.day[nx + 2] != day:
                continue
            hi, lo = b.H[nx:nx + 3].max(), b.L[nx:nx + 3].min()
            i = None
            for j in range(nx + 3, min(xi, nx + 24)):         # 18:15 .. 20:00 closes
                if (d == 1 and b.C[j] > hi) or (d == -1 and b.C[j] < lo):
                    i = j
                    break
            if i is None:
                continue
            stop = (lo if d == 1 else hi) - d * TICK
        tgt, R = None, None
        if cfg["tgt"] == "close":
            entry = b.O[i + 1] + d * TICK
            risk = max(MIN_STOP, (entry - stop) * d)
            if (rc - entry) * d < 1.0 * risk:
                continue
            tgt = rc
        else:
            R = float(cfg["tgt"][1:])
        out.append((i, d, stop, tgt, R, xi))
    return out


# ================================================================================================ CAM pivots (RTH)
def cam_levels():
    b = B()
    L = {}
    prev = None
    for dd in b.days:
        i0, i1 = b.rth[dd]
        if prev is not None and (dt.date.fromisoformat(dd) - dt.date.fromisoformat(prev[0])).days <= 4:
            H, Lo, C = prev[1:]
            R = H - Lo
            P = (H + Lo + C) / 3.0
            L[dd] = {"H3": C + 1.1 * R / 4, "L3": C - 1.1 * R / 4, "H4": C + 1.1 * R / 2, "L4": C - 1.1 * R / 2, "C": C,
                     "P": P, "R1": 2 * P - Lo, "S1": 2 * P - H}
        prev = (dd, float(b.H[i0:i1 + 1].max()), float(b.L[i0:i1 + 1].min()), float(b.C[i1]))
    return L


def cam(cfg):
    b = B()
    LV = _cache("cam_lv", cam_levels)
    last_hm = cfg["until"][0] * 60 + cfg["until"][1]
    out = []
    for dd, lv in LV.items():
        i0, i1 = b.rth[dd]
        xi = i1                                               # out at the 15:55 bar's open
        o = b.O[i0]
        z = i0 + (last_hm - 570) // 5 - 1                     # last signal bar closes at `until`
        if cfg["kind"] == "break4":
            hi4, lo4 = lv["H4"], lv["L4"]
            for j in range(i0, z + 1):
                pc = b.C[j - 1] if j > i0 else o
                d = 1 if (b.C[j] > hi4 and pc <= hi4) else -1 if (b.C[j] < lo4 and pc >= lo4) else 0
                if not d:
                    continue
                stop = ((lv["H3"] if d == 1 else lv["L3"]) if cfg["stop"] == "h3" else (b.L[j] if d == 1 else b.H[j])) - d * TICK
                R = None if cfg["tgt"] == "eod" else float(cfg["tgt"][1:])
                out.append((j, d, stop, None, R, xi))
                break
            continue
        up, dn = ("H3", "L3") if cfg["kind"] == "fade3" else ("R1", "S1")
        hiL, loL = lv[up], lv[dn]
        if cfg.get("open") == "in" and not (loL < o < hiL):
            continue
        st = {-1: None, 1: None}                              # fade side -> [first touch j, extreme] | "done"
        hit = None
        for j in range(i0, z + 1):
            for s, lvl in ((-1, hiL), (1, loL)):
                if st[s] == "done" or (s == -1 and o >= lvl) or (s == 1 and o <= lvl):
                    continue                                  # opened beyond = not a probe; accepted = done today
                if st[s] is None:
                    if not (b.H[j] > lvl if s == -1 else b.L[j] < lvl):
                        continue
                    st[s] = [j, b.H[j] if s == -1 else b.L[j]]
                else:
                    st[s][1] = max(st[s][1], b.H[j]) if s == -1 else min(st[s][1], b.L[j])
                if not (b.C[j] < lvl if s == -1 else b.C[j] > lvl):
                    if j - st[s][0] >= 2:
                        st[s] = "done"                        # 3 closes beyond: accepted
                    continue
                ext = st[s][1]
                stop = ext - s * TICK
                if cfg["kind"] == "fade3" and cfg["stop"] == "h4":
                    h4 = (lv["H4"] if s == -1 else lv["L4"]) - s * TICK
                    stop = h4 if (h4 - ext) * (-s) >= 0 else stop  # H4 beyond the probe: stop there, else at the probe
                entry = b.O[j + 1] + s * TICK
                risk = max(MIN_STOP, (entry - stop) * s)
                tg = cfg["tgt"]
                tgt = {"c": lv["C"], "far": loL if s == -1 else hiL, "p": lv["P"]}.get(tg)
                if tgt is not None and (tgt - entry) * s < 1.0 * risk:
                    st[s] = "done"
                    continue
                hit = (j, s, stop, tgt, 2.0 if tg == "r2" else None, xi)
                break
            if hit:
                out.append(hit)
                break
    return out


# ================================================================================================ TDS TD Sequential
def td_bars(tf):
    """tf-minute bars of the whole CME day built from 5m (aligned to 18:00): arrays + the 5m index of each bar's last bar."""
    b = B()
    rel = (b.hm - 1080) % 1440
    key = np.array([f"{x}|{r // tf}" for x, r in zip(b.day, rel)])
    starts = np.r_[0, np.flatnonzero(key[1:] != key[:-1]) + 1]
    ends = np.r_[starts[1:], len(key)] - 1
    H = np.maximum.reduceat(b.H, starts)
    L = np.minimum.reduceat(b.L, starts)
    C = b.C[ends]
    return {"H": H, "L": L, "C": C, "last": ends}


def tds(cfg):
    b = B()
    X = _cache(f"td{cfg['tf']}", lambda: td_bars(cfg["tf"]))
    H, L, C, last = X["H"], X["L"], X["C"], X["last"]
    n = len(C)
    out = []
    used = set()
    cand = []
    for side in (1, -1):                                      # side +1 = sell setup (closes above c-4) -> short
        up = np.zeros(n, bool)
        up[4:] = (C[4:] > C[:-4]) if side == 1 else (C[4:] < C[:-4])
        run = 0
        for k in range(4, n):
            run = run + 1 if up[k] else 0
            if run != 9:
                continue
            a = k - 8
            if a - 1 < 4 or up[a - 1]:
                continue                                      # needs the price flip before bar 1
            if cfg["perfect"]:
                if side == 1 and not max(H[k], H[k - 1]) >= max(H[k - 2], H[k - 3]):
                    continue
                if side == -1 and not min(L[k], L[k - 1]) <= min(L[k - 2], L[k - 3]):
                    continue
            sig = k
            if cfg["conf"] == "turn":
                sig = None
                for m in range(k + 1, min(n, k + 4)):
                    if (side == 1 and C[m] < C[m - 1]) or (side == -1 and C[m] > C[m - 1]):
                        sig = m
                        break
                if sig is None:
                    continue
            ext = H[a:sig + 1].max() if side == 1 else L[a:sig + 1].min()
            cand.append((int(last[sig]), -side, float(ext), float(C[a])))
    cand.sort()
    for i, d, ext, c1 in cand:
        if i + 1 >= len(b.O):
            continue
        hm = b.hm[i + 1]
        rel = (hm - 1080) % 1440
        if cfg["hours"] == "rth" and not (570 <= hm <= 930):
            continue
        if rel > (930 - 1080) % 1440:                         # no new entries 15:30 -> 18:00
            continue
        dd = b.day[i + 1]
        if dd in used or b.day[i] != dd:
            continue
        xi = b.x1555[i + 1]
        stop = ext - d * TICK
        tg = cfg["tgt"]
        tgt, R = None, None
        if tg == "start":
            entry = b.O[i + 1] + d * TICK
            risk = max(MIN_STOP, (entry - stop) * d)
            if (c1 - entry) * d < 1.0 * risk:
                continue
            tgt = c1
        else:
            R = float(tg[1:])
        out.append((i, d, stop, tgt, R, xi))
        used.add(dd)
    return out


# ================================================================================================ grid
FAM = {"pcm": pcm, "cam": cam, "tds": tds}
_C = {}


def _cache(key, fn):
    if key not in _C:
        _C[key] = fn()
    return _C[key]


def grid():
    G = []
    for k, dr, trig, tgt, tx in itertools.product([0.5, 1.0, 1.5, 2.0], ["follow", "fade"], ["open", "or15"],
                                                  ["r1", "r2", "close"], ["0925", "1555"]):
        if tgt == "close" and dr == "follow":
            continue
        G.append((f"pcm_k{int(k * 10)}_{dr}_{trig}_{tgt}_x{tx}", "pcm", {"k": k, "dir": dr, "trig": trig, "tgt": tgt, "tx": tx}))
    for stop, tgt, until, op in itertools.product(["ext", "h4"], ["r2", "c", "far"], [(11, 30), (15, 0)], ["in", "any"]):
        G.append((f"cam_fade3_{stop}_{tgt}_u{until[0]}_{op}", "cam", {"kind": "fade3", "stop": stop, "tgt": tgt, "until": until, "open": op}))
    for stop, tgt, until in itertools.product(["h3", "bar"], ["r2", "r3", "eod"], [(11, 30), (15, 0)]):
        G.append((f"cam_break4_{stop}_{tgt}_u{until[0]}", "cam", {"kind": "break4", "stop": stop, "tgt": tgt, "until": until}))
    for tgt, until, op in itertools.product(["p", "r2"], [(11, 30), (15, 0)], ["in", "any"]):
        G.append((f"cam_fade1_{tgt}_u{until[0]}_{op}", "cam", {"kind": "fade1", "stop": "ext", "tgt": tgt, "until": until, "open": op}))
    for tf, perf, conf, tgt, hours in itertools.product([15, 60], [False, True], ["bar9", "turn"], ["r1", "r2", "start"], ["all", "rth"]):
        G.append((f"tds_{tf}_{'p' if perf else 'a'}_{conf}_{tgt}_{hours}", "tds",
                  {"tf": tf, "perfect": perf, "conf": conf, "tgt": tgt, "hours": hours}))
    return G


# ================================================================================================ other accounts' days
def _runs_path(name):
    for base in (os.path.join(ROOT, "research", "runs"), os.path.join(os.path.dirname(ROOT), "nq-liquidity-engine", "research", "runs")):
        p = os.path.join(base, name)
        if os.path.exists(p):
            return p
    return None


def lit_daily():
    d = json.load(open(os.path.join(ROOT, "research", "lab", "backtest_live.json"), encoding="utf-8"))
    return {x["date"]: float(x["pnl"]) for x in d["days"]}


def atlas_daily():
    p = _runs_path("atlas_base.json")
    if not p:
        return {}
    d = json.load(open(p, encoding="utf-8"))
    return {x[0]: float(x[1]) for x in d["days"]}


def days_view(T, span, lit, atl):
    days = span_days(span)
    by = collections.defaultdict(float)
    for t in T:
        by[t["day"]] += t["pnl"]
    mo = len(days) / 21.0
    y = np.array([by.get(x, 0.0) for x in days])
    out = {"win_days_mo": round(sum(1 for v in y if v > 0) / mo, 2), "loss_days_mo": round(sum(1 for v in y if v < 0) / mo, 2)}
    for nm, ref in (("lit", lit), ("atlas", atl)):
        x = np.array([ref.get(z, 0.0) for z in days])
        out[f"corr_{nm}"] = round(float(np.corrcoef(x, y)[0, 1]), 3) if x.std() > 0 and y.std() > 0 else None
    both = np.array([lit.get(z, 0.0) + atl.get(z, 0.0) for z in days])
    out["new_green_off_both_mo"] = round(sum(1 for a, v in zip(both, y) if v > 0 and a <= 0) / mo, 2)
    return out


def eval_mc(daily, low, span, target=3000.0, trail=2000.0, horizons=(10, 40)):
    """A fresh MFFU Builder 50K started on every session: +$3,000 target, $2,000 EOD trailing (locks at +$100). A start
    too late to judge at a horizon (no result and fewer sessions left) is left out of that horizon."""
    days = span_days(span)
    H = max(horizons)
    res = {h: [] for h in horizons}
    meds = []
    for i in range(len(days)):
        bal, hi, out = 0.0, 0.0, None
        for nn, x in enumerate(days[i:i + H], 1):
            floor = min(hi - trail, 100.0)
            if bal + low.get(x, 0.0) <= floor:
                out = ("F", nn)
                break
            bal += daily.get(x, 0.0)
            if bal >= target:
                out = ("P", nn)
                break
            hi = max(hi, bal)
        for h in horizons:
            if out is not None and out[1] <= h:
                res[h].append(out[0])
            elif i + h <= len(days):
                res[h].append("O")
        if out and out[0] == "P":
            meds.append(out[1])
    o = {}
    for h in horizons:
        r = res[h]
        if r:
            o[f"pass{h}"] = round(100.0 * r.count("P") / len(r), 1)
            o[f"fail{h}"] = round(100.0 * r.count("F") / len(r), 1)
    o["med_pass"] = int(np.median(meds)) if meds else None
    return o


def eval_views(T, lit_days, lit_low):
    """Own 50K at $400 a trade; LIT's 50K days + this at $250 a trade vs LIT alone (LIT at its run size)."""
    out = {}
    own, own_low = collections.defaultdict(float), collections.defaultdict(float)
    add, add_low = collections.defaultdict(float), collections.defaultdict(float)
    for t in T:
        own[t["day"]] += t["pnl"] * 0.8
        own_low[t["day"]] = min(own_low[t["day"]], t["low"] * 0.8)
        add[t["day"]] += t["pnl"] * 0.5
        add_low[t["day"]] = min(add_low[t["day"]], t["low"] * 0.5)
    comb = {d: lit_days.get(d, 0.0) + add.get(d, 0.0) for d in set(lit_days) | set(add)}
    comb_low = {d: lit_low.get(d, 0.0) + add_low.get(d, 0.0) for d in set(lit_low) | set(add_low)}
    for sp in ("H1", "H2", "2021-25"):
        out[sp] = {"own_400": eval_mc(own, own_low, sp), "lit_alone": eval_mc(lit_days, lit_low, sp),
                   "lit_plus_250": eval_mc(comb, comb_low, sp)}
    return out


# ================================================================================================ main
def main_grid(log=print):
    t0 = time.time()
    G = grid()
    lit = lit_daily()
    d0 = json.load(open(os.path.join(ROOT, "research", "lab", "backtest_live.json"), encoding="utf-8"))
    lit_low = {x["date"]: float(x.get("low") or 0.0) for x in d0["days"]}
    atl = atlas_daily()
    res, sigs_of = {}, {}
    for cid, fam, cfg in G:
        sg = FAM[fam](cfg)
        T = book(execute(sg))
        S = score(T)
        res[cid] = {"fam": fam, "cfg": cfg, "S": S, "holds": holds(S)}
        sigs_of[cid] = sg
        log(f"{cid:36s} " + " | ".join(f"{s} n{S[s].get('n')} {S[s].get('tpw')}/wk PF {S[s].get('pf')} ${S[s].get('net')}" for s in J4))
    chance = collections.defaultdict(list)
    for seed in range(10):
        rng = np.random.default_rng(500 + seed)
        cnt = collections.Counter()
        for cid, r in res.items():
            cnt[r["fam"]] += int(holds(score(book(execute(sigs_of[cid], flip=rng)))))
        for f in FAM:
            chance[f].append(cnt[f])
    fams = {}
    for f in FAM:
        ids = [c for c in res if res[c]["fam"] == f]
        S1 = lambda c, s="H1": res[c]["S"][s]  # noqa: E731
        ok = [c for c in ids if S1(c).get("n", 0) >= 20 and (S1(c).get("pf") or 0) >= 1.2 and 2.0 <= S1(c).get("tpw", 0) <= 4.0]
        oka = [c for c in ids if S1(c).get("n", 0) >= 12 and (S1(c).get("pf") or 0) >= 1.2]
        fams[f] = {"name": NAMES[f], "cells": len(ids), "hold_all4": sum(res[c]["holds"] for c in ids),
                   "chance_mean": round(float(np.mean(chance[f])), 2), "chance_max": int(max(chance[f])),
                   "h1_h2_positive": sum(1 for c in ids if S1(c).get("net", 0) > 0 and S1(c, "H2").get("net", 0) > 0),
                   "h1_2to4": sum(1 for c in ids if 2.0 <= S1(c).get("tpw", 0) <= 4.0),
                   "h1_pick": max(ok, key=lambda c: S1(c)["net"]) if ok else None,
                   "h1_pick_any_freq": max(oka, key=lambda c: S1(c)["net"]) if oka else None,
                   "holders": [c for c in ids if res[c]["holds"]]}
        log(f"{f}: {fams[f]}")
    detail = {}
    for f in FAM:
        for c in [fams[f]["h1_pick"], fams[f]["h1_pick_any_freq"]] + fams[f]["holders"]:
            if not c or c in detail:
                continue
            T = book(execute(sigs_of[c]))
            pl = {"H2": [], "2021-25": []}
            for seed in range(200):
                Tf = book(execute(sigs_of[c], flip=np.random.default_rng(2000 + seed)))
                for s in pl:
                    pl[s].append(stats(Tf, s).get("net", 0))
            placebo = {s: round(float(np.mean([x >= res[c]["S"][s].get("net", 0) for x in pl[s]])), 3) for s in pl}
            yrs = {}
            for t in T:
                yrs[t["day"][:4]] = yrs.get(t["day"][:4], 0.0) + t["pnl"]
            detail[c] = {"S": res[c]["S"], "placebo_p": placebo, "years": {y: round(v) for y, v in sorted(yrs.items())},
                         "days": {s: days_view(T, s, lit, atl) for s in ("H1", "H2", "2021-25")},
                         "eval": eval_views(T, lit, lit_low)}
            log(f"detail {c}: placebo {placebo} years {detail[c]['years']}")
    out = {"built": DATE, "took_s": round(time.time() - t0), "n_cells": len(G), "families": fams, "detail": detail, "cells": res}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1, default=str)
    log(f"wrote {os.path.relpath(OUT, ROOT)} ({time.time() - t0:.0f}s)")
    return out


# ================================================================================================ ZEUS Lab (kind new_strategy)
HYP = {"pcm": "A big 16:00 -> 17:00 move (mega-cap earnings hour, MFFU flat) keeps going (follow) or gives part back (fade) "
              "after the 18:00 reopen.",
       "cam": "Camarilla H3/L3 probes that close back inside fade, H4/L4 closes break out; floor R1/S1 probes fade to P.",
       "tds": "A completed TD Sequential 9-count (15m / 1h, whole CME day) marks exhaustion: fade it to 1R / 2R / bar 1."}
WHAT = {"pcm": "A third strategy (own paper account): after a big post-close move, trade the 18:00 reopen with it or against it, "
               "stop beyond the move, out by 09:25 or 15:55.",
        "cam": "A third strategy (own paper account): trade the classic Camarilla / floor pivots in NY hours, one a day.",
        "tds": "A third strategy (own paper account): fade a completed TD Sequential 9-count, any hour 18:00-15:30, one a day."}


def lab_result(e: dict, path: str = OUT) -> dict:
    """ZEUS Lab runner for kind new_strategy: this tool's stored verdict (rerun `grid` for new bars). No H1 pick at 2-4 a
    week = rejected; a pick must hold in H2, 2025 and 2021-24 with a coin-flip placebo p <= 0.1 in H2 and 2021-25."""
    o = json.load(open(path, encoding="utf-8"))
    fam = o["families"].get(e.get("family")) or {}
    pick = fam.get("h1_pick")
    head = {}
    if pick:
        S = o["cells"][pick]["S"]
        head = {sp: {k: S[sp].get(k) for k in ("n", "tpw", "pf", "net", "dd", "per_month")} for sp in J4}
    base = {sp: {"per_month": 0, "n": 0} for sp in J4}
    if not pick:
        why = (f"no Jan-Jun pick: none of its {fam.get('cells')} versions made PF >= 1.2 on 20+ trades at 2-4 a week in Jan-Jun"
               f" ($500 a trade); {fam.get('hold_all4')} hold all 4 spans vs {fam.get('chance_mean')} with coin-flip sides")
        return {"proof_ok": False, "why": why, "flip": {"H1": 1.0, "H2": 1.0}, "head": head, "base": base, "deltas": [],
                "usd_month_by": None}
    c = o["cells"][pick]
    pl = (o.get("detail", {}).get(pick) or {}).get("placebo_p") or {}
    ok = c["holds"] and float(pl.get("H2", 1)) <= 0.1 and float(pl.get("2021-25", 1)) <= 0.1
    why = (f"pick {pick}: " + ", ".join(f"{sp} PF {c['S'][sp].get('pf')} ${c['S'][sp].get('net')}" for sp in J4)
           + f"; coin-flip p H2 {pl.get('H2')} / 2021-25 {pl.get('2021-25')}") + ("" if ok else " -> fails the hold / placebo bar")
    return {"proof_ok": ok, "why": why, "flip": {"H1": 1.0, "H2": float(pl.get("H2", 1))}, "head": head, "base": base,
            "deltas": [], "usd_month_by": {sp: (head.get(sp) or {}).get("per_month") for sp in ("H1", "H2")}}


def cmd_register(log=print):
    from tools import zeus_lab as Z
    o = json.load(open(OUT, encoding="utf-8"))
    for f, v in o["families"].items():
        e = {"id": f"third_{f}", "bot": "third", "kind": "new_strategy", "family": f, "cells": v["cells"], "registered": DATE,
             "origin": "claude", "source": "research/writeups/third-strategy-2026-11-18.md (tools/third_strategy.py)",
             "title": f"Third strategy: {v['name']}", "what_changes": WHAT[f], "hypothesis": HYP[f], "judged_by": "new_strategy",
             "pick": v.get("h1_pick")}
        err = Z.register(e)
        log(f"{e['id']}: {'saved' if not err else err}")
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "grid"
    if cmd == "grid":
        main_grid()
    elif cmd == "register":
        cmd_register()
