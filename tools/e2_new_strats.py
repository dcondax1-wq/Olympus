"""Team E2 (2026-11-13): NEW NQ strategies, uncorrelated with LIT / ATLAS / BLITZ, for more eval accounts.
Write-up: research/writeups/nq-new-strategies-2026-11-13.md. Numbers: research/second/e2_new_strats.json. Paper research only:
edits no engine / model / UI file, arms nothing.

Seven families, each with its hypothesis written BEFORE the run and the angle that is new against the rejected list
(docs/CLAUDE_REFERENCE.md "Tested and rejected"; quant-anomalies.md, hq-reversion.md, atlas-chatgpt-breakouts.md,
retail-standalone.md, allday.md, diversifier-search.md, 2026-11-03-strategy-tree.md, lit-big-ideas.md):

  orb2  ORB with a failed-breakout filter. H: when one side of the opening range is broken and the break FAILS (a close back
        inside), the stops behind that side are spent and the opposite-side break is the real move. Enter on the first 5m
        close beyond the OTHER side, stop 1 tick beyond the failed break's extreme (the protected high/low). Not redone:
        plain ORBs with R targets (dead), the failed-ORB FADE back inside (hq-reversion lead, lost 2025).
  pdx   Prior-day high/low sweep reversal in RTH with CLIMAX VOLUME. H: a first sweep of PDH/PDL that reclaims within 1 bar
        on 1.5-2.5x the time-of-day volume is a stop run that gets absorbed; fade it to VWAP / the prior-day middle / 2R,
        stop 1 tick beyond the sweep extreme. New angle: the relative-volume gate (rv 0 = the plain fade, the control).
  rs    NQ / ES relative strength at the open (2025-04+ only: no ES data before). H (two, both run): "lead" - NQ beating ES
        by z noise-sigmas at 10:00 / 10:30 keeps leading; "catch" - NQ lagging an ES move catches up. Stop beyond the
        opening range. The LIT SMT size study (lit-adv-audit-smt.md) was a size rule on LIT trades, not a strategy.
  gapf  Overnight inventory (gap) fade with volume confirmation. H: a gap of >= g x the 14-day range whose opening range
        closes in its far half (the drive failed) fades toward the prior close; volume "low" = the opening range traded
        below its 20-day volume (no institutional push), "high" = above (the reversal is real). Stop 1 tick beyond the
        opening-range extreme. Not redone: the unconditional gap fill (quant-anomalies q_gap_fill, dead).
  vwr   VWAP reversion on LOW-VIX days. H: on quiet days (VIX at yesterday's close below its 1-year median / 33rd pct) a
        close back inside the VWAP +/- k sd band after a close outside it reverts to VWAP; stop 1 tick beyond the stretch
        extreme. vf "none" = the plain fade (hq-reversion: loses), the control for the regime angle.
  eod   End-of-day. (a) "lbrk": a 5m close at a new day high / low after 14:00-15:00 runs into the close, stop beyond the
        last 30-60 min swing (structure, not the textbook first-half-hour sign of Gao / Baltussen, dead). (b) "lrev":
        the note from quant-anomalies.md ("since 2025 the last half hour tends to reverse the day's move"): fade a day
        move of >= thr sigma at 15:00 / 15:25, stop 1 tick beyond the day's extreme. 2021-24 is out of sample for (b).
  news  CPI / NFP / FOMC playbook. FOMC: the 14:00-14:30 statement range, then 14:35-15:30 trade the break ("go") or the
        failed break ("fade"). CPI / NFP (08:30): the 09:30-10:00 range break taken only WITH ("follow") or AGAINST
        ("against") the 08:30-09:30 release move. Not testable as LIT news setups (lit-big-ideas.md: 94-395 pt stops).

Execution (as tools/div_search.py): TradingView CME NQ1! 5m RTH (2021-11 -> 2026-10-16, full 78-bar days), entry at the
next 5m open + 1 tick, a stop touched in a bar fills at the stop (or the open through it) - 1 tick, a target needs a
trade-through, stop + target in one bar = stop, the time exit at the exit bar's open - 1 tick; $1.90 a micro. $500 risk a
trade: micros = floor(500 / (stop x $2 + $1.90)), 1-40 (size follows the stop). Every stop is 1 tick beyond the structure
that defines the setup (sweep extreme / failed-break extreme / opening range / swing); a stop under 8 points is widened
to 8 (a 1-tick-wide structure is noise). ES for rs only (CME ES1! 5m 2025-04-14 -> 2026-10-16).

Judging: every variant on H1 (2026 Jan-Jun), H2 (Jul-Oct 16), 2025, 2021-24; "holds" = net > 0 and PF >= 1.1 in all four.
Chance level = the same variants with coin-flip directions (stop mirrored at the same distance, same exits), 20 seeds.
Pick per family on H1 (n >= 12, PF >= 1.2, best H1 $, as div_search) and a 2021-24 re-pick; every span reported.
Correlation: daily P&L vs runs lit_live, atlas_base, sn_blitz_today (BLITZ). Eval / slot: tools/div_stack.py engines.

    python -X utf8 tools/e2_new_strats.py grid      # all families -> research/second/e2_new_strats.json
    python -X utf8 tools/e2_new_strats.py blitz     # BLITZ fix angles (gap-aware band, implied-vol band)
    python -X utf8 tools/e2_new_strats.py slot      # eval / funded / slot $ of the best new one + the 3rd-account question
    python -X utf8 tools/e2_new_strats.py save      # rl.save runs e2_*
"""
from __future__ import annotations

import collections
import datetime as dt
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

OUT = os.path.join(ROOT, "research", "second", "e2_new_strats.json")
PV, COMM, TICK, NB = DS.PV, DS.COMM, DS.TICK, DS.NB
MIN_STOP = 8.0
J4 = ("H1", "H2", "2025", "2021-24")
col = DS.col_of

# BLS CPI release dates 2021-2023-09 (the repo calendar has CPI from 2023-10; checked against the 08:30 bar range below)
CPI_EXTRA = ["2021-11-10", "2021-12-10",
             "2022-01-12", "2022-02-10", "2022-03-10", "2022-04-12", "2022-05-11", "2022-06-10", "2022-07-13", "2022-08-10",
             "2022-09-13", "2022-10-13", "2022-11-10", "2022-12-13",
             "2023-01-12", "2023-02-14", "2023-03-14", "2023-04-12", "2023-05-10", "2023-06-13", "2023-07-12", "2023-08-10",
             "2023-09-13"]


# ================================================================================================ extra day facts
class Ext:
    """Per RTH day of DS.D(): prior RTH high / low / close (early closes included), overnight high / low / volume and the
    08:25 close, 14-day mean RTH range, time-of-day relative volume, VWAP sd, VIX at the prior close + its 1-year median
    / 33rd pct, the news calendar."""

    def __init__(self):
        B = DS.D()
        d = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
        et = pd.to_datetime(d.time, unit="s", utc=True).dt.tz_convert("America/New_York")
        hm = (et.dt.hour * 60 + et.dt.minute).to_numpy()
        cal = et.dt.date.to_numpy()
        sess = np.array([c + dt.timedelta(days=1) if m >= 1080 else c for c, m in zip(cal, hm)])
        sess = np.array([x.isoformat() for x in sess])
        cal = np.array([x.isoformat() for x in cal])
        H, L, C, V = (d[k].to_numpy(float) for k in ("high", "low", "close", "volume"))
        rth = (hm >= 570) & (hm < 960)
        on = (hm >= 1080) | (hm < 570)
        rh, rl, rc = {}, {}, {}
        for day, ix in pd.Series(np.arange(len(d))[rth]).groupby(cal[rth]).groups.items():
            ix = np.array(sorted(pd.Series(np.arange(len(d))[rth]).loc[ix]))
            rh[day], rl[day], rc[day] = H[ix].max(), L[ix].min(), C[ix[-1]]
        onh, onl, onv, c825 = {}, {}, {}, {}
        idx_on = np.arange(len(d))[on]
        for day, ix in pd.Series(idx_on).groupby(sess[on]).groups.items():
            ii = np.array(sorted(pd.Series(idx_on).loc[ix]))
            onh[day], onl[day], onv[day] = H[ii].max(), L[ii].min(), V[ii].sum()
            pre = ii[hm[ii] == 505]
            if len(pre):
                c825[day] = C[pre[-1]]
        rdays = sorted(rh)
        prev = {}
        for a, b in zip(rdays[:-1], rdays[1:]):
            prev[b] = a
        n = len(B.days)
        self.PH = np.array([rh[prev[x]] if x in prev else np.nan for x in B.days])
        self.PL = np.array([rl[prev[x]] if x in prev else np.nan for x in B.days])
        self.ONH = np.array([onh.get(x, np.nan) for x in B.days])
        self.ONL = np.array([onl.get(x, np.nan) for x in B.days])
        self.C825 = np.array([c825.get(x, np.nan) for x in B.days])
        rng = B.H.max(axis=1) - B.L.min(axis=1)
        self.rng14 = np.array([rng[max(0, k - 14):k].mean() if k >= 10 else np.nan for k in range(n)])
        self.prng = np.array([(self.PH[k] - self.PL[k]) / self.rng14[k] if k >= 10 else np.nan for k in range(n)])
        vm = np.full_like(B.V, np.nan)
        for k in range(20, n):
            vm[k] = B.V[k - 20:k].mean(axis=0)
        self.rvol = B.V / np.maximum(vm, 1.0)
        self.vavg = vm
        tp = (B.H + B.L + B.C) / 3.0
        cv = np.maximum(np.cumsum(B.V, axis=1), 1.0)
        self.VSD = np.sqrt(np.maximum(np.cumsum(B.V * tp * tp, axis=1) / cv - B.VW ** 2, 0.0))
        vix = pd.read_csv(os.path.join(ROOT, "data", "VIX_1d.csv"))
        vix = vix[vix.close > 0]
        vd, vv = vix.date.astype(str).tolist(), vix.close.astype(float).to_numpy()
        import bisect
        self.vix = np.full(n, np.nan); self.vix_med = np.full(n, np.nan); self.vix_p33 = np.full(n, np.nan)
        for k, x in enumerate(B.days):
            i = bisect.bisect_left(vd, x)
            if i > 0:
                self.vix[k] = vv[i - 1]
                h = vv[max(0, i - 253):i - 1]
                if len(h) >= 120:
                    self.vix_med[k] = float(np.median(h)); self.vix_p33[k] = float(np.percentile(h, 33))
        from tools import scalp_na_lib as SL
        N = SL.news_days()
        self.news = {x: set(N.get(x, ())) for x in B.days}
        for x in CPI_EXTRA:
            if x in self.news:
                self.news[x].add("CPI")


_E = {}


def E():
    if "e" not in _E:
        _E["e"] = Ext()
    return _E["e"]


class ESDays:
    """CME ES1! 5m full RTH days aligned to NQ's days (nan where ES has no full day), noise sigma 14 sessions."""

    def __init__(self):
        B = DS.D()
        d = pd.read_csv(os.path.join(ROOT, "data", "ES_5m.csv"))
        et = pd.to_datetime(d.time, unit="s", utc=True).dt.tz_convert("America/New_York")
        hm = (et.dt.hour * 60 + et.dt.minute).to_numpy()
        date = et.dt.date.astype(str).to_numpy()
        rth = (hm >= 570) & (hm < 960)
        d = d[rth].reset_index(drop=True); hm, date = hm[rth], date[rth]
        rows = {}
        for day, idx in pd.Series(np.arange(len(d))).groupby(date).groups.items():
            ix = np.array(sorted(idx))
            if len(ix) == NB and hm[ix[0]] == 570:
                rows[day] = ix
        n = len(B.days)
        self.C = np.full((n, NB), np.nan); self.O0 = np.full(n, np.nan)
        cl, op = d.close.to_numpy(float), d.open.to_numpy(float)
        for k, x in enumerate(B.days):
            if x in rows:
                self.C[k] = cl[rows[x]]; self.O0[k] = op[rows[x][0]]
        mv = np.abs(self.C - self.O0[:, None])
        self.sig = np.full_like(mv, np.nan)
        ok = np.where(np.isfinite(self.O0))[0]
        for q in range(14, len(ok)):
            self.sig[ok[q]] = mv[ok[q - 14:q]].mean(axis=0)


_ES = {}


def ES():
    if "e" not in _ES:
        _ES["e"] = ESDays()
    return _ES["e"]


# ================================================================================================ one trade
def walk(k, j, d, stop, tgt=None, end=None, rr=None):
    """DS.walk with a time exit (`end` = column whose OPEN is the exit, default 15:55) and an R target (rr x the risk)."""
    B = DS.D()
    e0 = j + 1
    last = NB - 1 if end is None else min(NB - 1, end)
    if e0 >= last:
        return None
    O, H, L = B.O[k], B.H[k], B.L[k]
    entry = O[e0] + d * TICK
    s = float(stop)
    if (entry - s) * d < MIN_STOP:
        s = entry - d * MIN_STOP
    risk = (entry - s) * d
    if rr is not None:
        tgt = entry + d * rr * risk
    if tgt is not None and (tgt - entry) * d <= 0:
        return None
    mfe = mae = 0.0
    ex_px = ex_kind = ex_j = None
    for jj in range(e0, last):
        if d == 1 and L[jj] <= s:
            ex_px, ex_kind, ex_j = min(O[jj], s) - TICK, "STOP", jj
            mae = min(mae, L[jj] - entry); break
        if d == -1 and H[jj] >= s:
            ex_px, ex_kind, ex_j = max(O[jj], s) + TICK, "STOP", jj
            mae = min(mae, entry - H[jj]); break
        mfe = max(mfe, (H[jj] - entry) if d == 1 else (entry - L[jj]))
        mae = min(mae, (L[jj] - entry) if d == 1 else (entry - H[jj]))
        if tgt is not None and ((d == 1 and H[jj] > tgt) or (d == -1 and L[jj] < tgt)):
            ex_px, ex_kind, ex_j = tgt, "TARGET", jj
            break
    if ex_px is None:
        ex_j = last
        ex_px = O[last] - d * TICK
        ex_kind = "TIME"
    return {"k": k, "j": j, "dir": d, "entry": entry, "stop0": s, "risk": risk, "exit_px": ex_px, "exit": ex_kind,
            "exit_j": ex_j, "pts": (ex_px - entry) * d, "mfe": mfe, "mae": mae, "tgt": tgt, "end": end, "rr": rr}


def mirror(w, rng):
    """Coin-flip twin: same entry bar, random side, the same stop distance, the same kind of target / time exit."""
    d = int(rng.choice([-1, 1]))
    B = DS.D()
    entry = B.O[w["k"], w["j"] + 1] + d * TICK
    stop = entry - d * w["risk"]
    tgt = None
    if w["tgt"] is not None and w["rr"] is None:
        tgt = entry + d * abs(w["tgt"] - w["entry"])
    return walk(w["k"], w["j"], d, stop, tgt=tgt, end=w["end"], rr=w["rr"])


def _ex(ex):
    """exit code -> (rr, end column)."""
    if ex == "eod":
        return None, None
    if ex.startswith("r"):
        return float(ex[1:]), None
    raise ValueError(ex)


# ================================================================================================ families
def run_orb2(c, days=None):
    B = DS.D()
    jor = col((9, 30 + c["orm"])) if c["orm"] < 30 else col((9 + (30 + c["orm"]) // 60, (30 + c["orm"]) % 60))
    last = col(c["last"])
    rr, end = _ex(c["ex"])
    out = []
    for k in (days if days is not None else range(len(B.days))):
        H, L, C = B.H[k], B.L[k], B.C[k]
        orh, orl = H[:jor + 1].max(), L[:jor + 1].min()
        up_ext = dn_ext = None
        fail_up = fail_dn = False
        for j in range(jor + 1, last + 1):
            if H[j] > orh:
                up_ext = H[j] if up_ext is None else max(up_ext, H[j])
            if L[j] < orl:
                dn_ext = L[j] if dn_ext is None else min(dn_ext, L[j])
            if up_ext is not None and C[j] < orh:
                fail_up = True
            if dn_ext is not None and C[j] > orl:
                fail_dn = True
            d = 0
            if fail_up and C[j] < orl and C[j - 1] >= orl:
                d, stop = -1, up_ext + TICK
            elif fail_dn and C[j] > orh and C[j - 1] <= orh:
                d, stop = 1, dn_ext - TICK
            if d:
                w = walk(k, j, d, stop, end=end, rr=rr)
                if w:
                    out.append(w)
                break
    return out


def run_pdx(c, days=None):
    B, X = DS.D(), E()
    last = col(c["last"])
    out = []
    for k in (days if days is not None else range(len(B.days))):
        ph, pl = X.PH[k], X.PL[k]
        if not np.isfinite(ph) or not np.isfinite(X.rvol[k, 0]):
            continue
        H, L, C, O = B.H[k], B.L[k], B.C[k], B.O[k]
        if not (pl < O[0] < ph):
            continue
        done = False
        for j in range(1, last + 1):
            for d, lvl in ((-1, ph), (1, pl)):
                prior_x = H[:j].max() if d == -1 else L[:j].min()
                swept = (H[j] > lvl and prior_x <= lvl) if d == -1 else (L[j] < lvl and prior_x >= lvl)
                if not swept:
                    continue
                # reclaim in the sweep bar or the next one
                jr = j if ((C[j] < lvl) if d == -1 else (C[j] > lvl)) else (j + 1 if j + 1 <= last and ((C[j + 1] < lvl) if d == -1 else (C[j + 1] > lvl)) else None)
                if jr is None:
                    continue
                rv = max(X.rvol[k, j], X.rvol[k, jr])
                if rv < c["rv"]:
                    continue
                ext = H[j:jr + 1].max() if d == -1 else L[j:jr + 1].min()
                stop = ext + TICK if d == -1 else ext - TICK
                tg, rr = None, None
                if c["tg"] == "r2":
                    rr = 2.0
                elif c["tg"] == "vwap":
                    tg = B.VW[k, jr]
                else:
                    tg = (ph + pl) / 2.0
                w = walk(k, jr, d, stop, tgt=tg, rr=rr)
                if w:
                    w["rv"] = float(rv)
                    out.append(w)
                done = True
                break
            if done:
                break
    return out


def run_rs(c, days=None):
    B, S = DS.D(), ES()
    j = col(c["at"])
    rr, end = _ex(c["ex"])
    out = []
    for k in (days if days is not None else range(len(B.days))):
        sN, sE = B.sig[14][k, j], S.sig[k, j]
        if not (np.isfinite(sN) and np.isfinite(sE) and sN > 0 and sE > 0 and np.isfinite(S.C[k, j])):
            continue
        zN = (B.C[k, j] - B.O[k, 0]) / sN
        zE = (S.C[k, j] - S.O0[k]) / sE
        sp = zN - zE
        d = 0
        if c["mode"] == "lead":
            d = 1 if (sp > c["z"] and zN > 0) else -1 if (sp < -c["z"] and zN < 0) else 0
        else:
            d = 1 if (sp < -c["z"] and zE > 0) else -1 if (sp > c["z"] and zE < 0) else 0
        if not d:
            continue
        stop = (B.L[k, :j + 1].min() - TICK) if d == 1 else (B.H[k, :j + 1].max() + TICK)
        w = walk(k, j, d, stop, end=end, rr=rr)
        if w:
            w["zN"], w["zE"] = float(zN), float(zE)
            out.append(w)
    return out


def run_gapf(c, days=None):
    B, X = DS.D(), E()
    jor = col((9, 45)) if c["orm"] == 15 else col((10, 0))
    out = []
    for k in (days if days is not None else range(len(B.days))):
        pc, r14 = B.PC[k], X.rng14[k]
        if not (np.isfinite(pc) and np.isfinite(r14) and np.isfinite(X.vavg[k, 0])):
            continue
        gap = B.O[k, 0] - pc
        if abs(gap) < c["g"] * r14:
            continue
        d = -1 if gap > 0 else 1
        orh, orl = B.H[k, :jor + 1].max(), B.L[k, :jor + 1].min()
        mid = (orh + orl) / 2.0
        cl = B.C[k, jor]
        if (d == -1 and cl >= mid) or (d == 1 and cl <= mid):
            continue
        rv = B.V[k, :jor + 1].sum() / max(1.0, X.vavg[k, :jor + 1].sum())
        if c["vol"] == "low" and rv >= 0.9:
            continue
        if c["vol"] == "high" and rv <= 1.1:
            continue
        stop = orh + TICK if d == -1 else orl - TICK
        if c["tg"] == "fill":
            w = walk(k, jor, d, stop, tgt=pc)
        else:
            w = walk(k, jor, d, stop, rr=2.0)
        if w:
            w["rv"], w["gap"] = float(rv), float(gap / r14)
            out.append(w)
    return out


def run_vwr(c, days=None):
    B, X = DS.D(), E()
    j0, j1 = col((10, 30)), col((14, 30))
    out = []
    for k in (days if days is not None else range(len(B.days))):
        if c["vf"] != "none":
            ref = X.vix_med[k] if c["vf"] == "med" else X.vix_p33[k]
            if not (np.isfinite(ref) and np.isfinite(X.vix[k]) and X.vix[k] < ref):
                continue
        H, L, C, VW, SD = B.H[k], B.L[k], B.C[k], B.VW[k], X.VSD[k]
        free = j0
        n = 0
        ext_hi = ext_lo = None
        for j in range(j0 - 6, j1 + 1):
            up, dn = VW[j] + c["kb"] * SD[j], VW[j] - c["kb"] * SD[j]
            if C[j] > up:
                ext_hi = H[j] if ext_hi is None else max(ext_hi, H[j])
            if C[j] < dn:
                ext_lo = L[j] if ext_lo is None else min(ext_lo, L[j])
            if j < free or j < j0 or n >= c.get("maxn", 1):
                continue
            d = 0
            if ext_hi is not None and C[j] <= up and C[j - 1] > VW[j - 1] + c["kb"] * SD[j - 1]:
                d, stop = -1, max(ext_hi, H[j]) + TICK
            elif ext_lo is not None and C[j] >= dn and C[j - 1] < VW[j - 1] - c["kb"] * SD[j - 1]:
                d, stop = 1, min(ext_lo, L[j]) - TICK
            if not d:
                continue
            w = walk(k, j, d, stop, tgt=VW[j] if c["tg"] == "vwap" else None, rr=1.0 if c["tg"] == "r1" else None)
            if d == -1:
                ext_hi = None
            else:
                ext_lo = None
            if w:
                out.append(w)
                n += 1
                free = w["exit_j"] + 1
    return out


def run_eod(c, days=None):
    B = DS.D()
    out = []
    for k in (days if days is not None else range(len(B.days))):
        H, L, C, O = B.H[k], B.L[k], B.C[k], B.O[k]
        if c["kind"] == "lbrk":
            j0, j1 = col(c["start"]), col((15, 40))
            for j in range(j0, j1 + 1):
                hi, lo = H[:j].max(), L[:j].min()
                d = 1 if C[j] > hi else -1 if C[j] < lo else 0
                if c["agree"] and d and np.sign(C[j] - O[0]) != d:
                    d = 0
                if not d:
                    continue
                sw = c["swing"]
                stop = L[j - sw + 1:j + 1].min() - TICK if d == 1 else H[j - sw + 1:j + 1].max() + TICK
                w = walk(k, j, d, stop)
                if w:
                    out.append(w)
                break
        else:
            j = col(c["at"])
            sg = B.sig[14][k, j]
            if not np.isfinite(sg) or sg <= 0:
                continue
            mv = (C[j] - O[0]) / sg
            if abs(mv) < c["thr"]:
                continue
            d = -1 if mv > 0 else 1
            stop = H[:j + 1].max() + TICK if d == -1 else L[:j + 1].min() - TICK
            w = walk(k, j, d, stop)
            if w:
                out.append(w)
    return out


def run_news(c, days=None):
    B, X = DS.D(), E()
    rr, end = _ex(c["ex"])
    out = []
    for k in (days if days is not None else range(len(B.days))):
        ev = X.news.get(B.days[k], set())
        H, L, C, O = B.H[k], B.L[k], B.C[k], B.O[k]
        if c["ev"] == "fomc":
            if "FOMC" not in ev:
                continue
            a, z = col((14, 5)), col((14, 30))
            rh, rl = H[a:z + 1].max(), L[a:z + 1].min()
            ext_u = ext_d = None
            for j in range(z + 1, col((15, 30)) + 1):
                if c["mode"] == "go":
                    d = 1 if C[j] > rh else -1 if C[j] < rl else 0
                    if d:
                        stop = rl - TICK if d == 1 else rh + TICK
                        w = walk(k, j, d, stop, end=end, rr=rr)
                        if w:
                            out.append(w)
                        break
                else:
                    if H[j] > rh:
                        ext_u = H[j] if ext_u is None else max(ext_u, H[j])
                    if L[j] < rl:
                        ext_d = L[j] if ext_d is None else min(ext_d, L[j])
                    d = 0
                    if ext_u is not None and C[j] < rh:
                        d, stop = -1, ext_u + TICK
                    elif ext_d is not None and C[j] > rl:
                        d, stop = 1, ext_d - TICK
                    if d:
                        w = walk(k, j, d, stop, end=end, rr=rr)
                        if w:
                            out.append(w)
                        break
        else:
            if not (ev & {"CPI", "Non-Farm"}) or not np.isfinite(X.C825[k]):
                continue
            rel = np.sign(O[0] - X.C825[k])
            if not rel:
                continue
            jor = col((10, 0))
            orh, orl = H[:jor + 1].max(), L[:jor + 1].min()
            for j in range(jor + 1, col((12, 0)) + 1):
                d = 1 if C[j] > orh else -1 if C[j] < orl else 0
                if not d:
                    continue
                if (c["mode"] == "follow") != (d == rel):
                    break
                stop = orl - TICK if d == 1 else orh + TICK
                w = walk(k, j, d, stop, end=end, rr=rr)
                if w:
                    out.append(w)
                break
    return out


FAM = {"orb2": run_orb2, "pdx": run_pdx, "rs": run_rs, "gapf": run_gapf, "vwr": run_vwr, "eod": run_eod, "news": run_news}


def grid():
    G = []
    for orm in (15, 30, 60):
        for ex in ("r2", "r3", "eod"):
            for last in ((12, 0), (14, 0)):
                G.append((f"orb2_or{orm}_{ex}_to{last[0]}", {"fam": "orb2", "orm": orm, "ex": ex, "last": last}))
    for rv in (0.0, 1.5, 2.5):
        for tg in ("r2", "vwap", "pdmid"):
            for last in ((11, 30), (15, 0)):
                G.append((f"pdx_rv{rv:g}_{tg}_to{last[0]}", {"fam": "pdx", "rv": rv, "tg": tg, "last": last}))
    for mode in ("lead", "catch"):
        for z in (0.5, 1.0):
            for at in ((10, 0), (10, 30)):
                for ex in ("r2", "eod"):
                    G.append((f"rs_{mode}_z{z:g}_{at[0]}{at[1]:02d}_{ex}", {"fam": "rs", "mode": mode, "z": z, "at": at, "ex": ex}))
    for g in (0.1, 0.25):
        for vol in ("none", "low", "high"):
            for orm in (15, 30):
                for tg in ("fill", "r2"):
                    G.append((f"gapf_g{g:g}_{vol}_or{orm}_{tg}", {"fam": "gapf", "g": g, "vol": vol, "orm": orm, "tg": tg}))
    for vf in ("none", "med", "p33"):
        for kb in (1.5, 2.0, 2.5):
            for tg in ("vwap", "r1"):
                G.append((f"vwr_{vf}_k{kb:g}_{tg}", {"fam": "vwr", "vf": vf, "kb": kb, "tg": tg}))
    for start in ((14, 0), (14, 30), (15, 0)):
        for agree in (False, True):
            for sw in (6, 12):
                G.append((f"eod_lbrk_{start[0]}{start[1]:02d}_{'agree' if agree else 'any'}_sw{sw}",
                          {"fam": "eod", "kind": "lbrk", "start": start, "agree": agree, "swing": sw}))
    for thr in (0.5, 1.0, 1.5):
        for at in ((15, 0), (15, 25)):
            G.append((f"eod_lrev_t{thr:g}_{at[0]}{at[1]:02d}", {"fam": "eod", "kind": "lrev", "thr": thr, "at": at}))
    for mode in ("go", "fade"):
        for ex in ("r2", "eod"):
            G.append((f"news_fomc_{mode}_{ex}", {"fam": "news", "ev": "fomc", "mode": mode, "ex": ex}))
    for mode in ("follow", "against"):
        for ex in ("r2", "eod"):
            G.append((f"news_cpi_{mode}_{ex}", {"fam": "news", "ev": "cpi", "mode": mode, "ex": ex}))
    return G


def run(cfg, days=None):
    return FAM[cfg["fam"]](cfg, days)


# ================================================================================================ money / scoring
def booked(W):
    return DS.booked(W)


def score(T):
    return DS.score(T)


def holds(S, pf=1.1):
    return all(S[s].get("n", 0) >= 5 and S[s]["net"] > 0 and (S[s]["pf"] or 0) >= pf for s in J4)


_DAILY = {}


def daily_of_run(rid):
    if rid not in _DAILY:
        r = json.load(open(os.path.join(ROOT, "research", "runs", rid + ".json"), encoding="utf-8"))
        _DAILY[rid] = {d[0]: float(d[1]) for d in r["days"]}
    return _DAILY[rid]


def corr_with(T, rid, span):
    ref = daily_of_run(rid)
    a, z = DS.SPANS[span]
    by = collections.defaultdict(float)
    for t in T:
        by[t["day"]] += t["pnl"]
    days = [d for d in DS.D().days if a <= d <= z]
    x = np.array([ref.get(d, 0.0) for d in days]); y = np.array([by.get(d, 0.0) for d in days])
    if x.std() == 0 or y.std() == 0:
        return None
    return round(float(np.corrcoef(x, y)[0, 1]), 3)


def corr_all(T):
    return {nm: {sp: corr_with(T, rid, sp) for sp in ("2026", "2021-25")}
            for nm, rid in (("lit", "lit_live"), ("atlas", "atlas_base"), ("blitz", "sn_blitz_today"))}


def pick(res, fam, span="H1", min_n=12):
    c = [(cid, r) for cid, r in res.items() if r["fam"] == fam and r["S"][span].get("n", 0) >= min_n and (r["S"][span]["pf"] or 0) >= 1.2]
    if not c:
        return None
    return max(c, key=lambda x: x[1]["S"][span]["net"])[0]


def grid_main():
    G = grid()
    res = {}
    for cid, cfg in G:
        W = run(cfg)
        T = booked(W)
        S = score(T)
        res[cid] = {"fam": cfg["fam"], "cfg": cfg, "S": S, "holds": holds(S)}
        print(f"{cid:34s} " + " | ".join(f"{s} n{S[s].get('n',0):>3} pf {S[s].get('pf')} ${S[s].get('net',0):>7}" for s in J4)
              + f" | tpw {S['2026'].get('tpw')}/{S['2021-25'].get('tpw')}" + ("  HOLDS" if res[cid]["holds"] else ""), flush=True)
    # chance level: coin-flip twins of every variant, 20 seeds
    chance = []
    for seed in range(20):
        rng = np.random.default_rng(1000 + seed)
        n = 0
        for cid, cfg in G:
            W = [m for m in (mirror(w, rng) for w in run_cached(cid, cfg)) if m]
            n += holds(score(booked(W)))
        chance.append(n)
    picks = {}
    for fam in FAM:
        p1 = pick(res, fam, "H1")
        p2 = pick(res, fam, "2021-24", min_n=30)
        picks[fam] = {"h1": p1, "pre2025": p2}
    out = {"built": dt.date.today().isoformat(), "n_variants": len(G),
           "holds": [cid for cid, r in res.items() if r["holds"]], "chance_holds": chance,
           "chance_mean": round(float(np.mean(chance)), 2), "picks": picks, "res": res}
    for fam, p in picks.items():
        for which, cid in p.items():
            if cid:
                out["res"][cid]["corr"] = corr_all(booked(run_cached(cid, dict(G)[cid])))
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1, default=float)
    print("holds:", out["holds"], "| chance mean", out["chance_mean"], chance)
    print("picks:", picks)
    print("->", OUT)


_RC = {}


def run_cached(cid, cfg):
    if cid not in _RC:
        _RC[cid] = run(cfg)
    return _RC[cid]


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "grid"
    if cmd == "grid":
        grid_main()
    elif cmd == "cpicheck":
        B, X = DS.D(), E()
        d = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
        et = pd.to_datetime(d.time, unit="s", utc=True).dt.tz_convert("America/New_York")
        m = (et.dt.hour == 8) & (et.dt.minute == 30)
        r = (d.high - d.low)[m]
        days = et[m].dt.date.astype(str).to_numpy()
        rr = dict(zip(days, r.to_numpy()))
        med = float(np.median(r))
        for x in CPI_EXTRA:
            print(x, rr.get(x), round(rr.get(x, 0) / med, 2))
        print("median 08:30 bar range", med)
