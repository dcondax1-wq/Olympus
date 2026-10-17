"""Confluence lab (CONFLUENCE track): causal confluence features for any trade + honest with/without tests.

API
  features(bars5, entry_t, d, es5=None, entry_px=None) -> dict
      bars5    strategy_lab.bars(...) frame (NQ or ES 5m; give it enough warm-up: >= 25 sessions before the first trade)
      entry_t  unix seconds of the entry; d = +1 long / -1 short
      es5      ES 5m frame for the intermarket items (None -> those items are None)
      entry_px the trade's own fill price (optional; known at entry, so causal)
  Booleans are the confluences (True = present). Keys ending in _x are numeric helpers. None = not defined yet at
  that time (e.g. the initial balance before 10:30). FEATURES lists the tested booleans with a one-line definition.

Causality
  Only 5m bars whose close (open time + 300 s) is <= entry_t. 15m / 1H bars only after their last 5m bar closed.
  Day / week context from completed sessions; "so far" values from today's closed bars only. Session windows (Asia,
  London, CBDR, IB, OR, ...) only after their last bar closed. Reference price = entry_px if given, else the open of the
  5m bar that starts exactly at entry_t (known at that instant), else the last closed bar's close.

CLI (writes research/lab/CONFLUENCE_RESULTS.md + confluence_results.json; reads the cached beds)
  python -X utf8 tools/lab_confluences.py all        # priority + beds + no-lookahead check (about 1 minute)
  python -X utf8 tools/lab_confluences.py priority   # leading candidate (engine, max 1 trade/day): filters + pairs
  python -X utf8 tools/lab_confluences.py beds       # every test bed: with/without, labels, placebo, pooled test
  python -X utf8 tools/lab_confluences.py models [--refresh]   # (re)run the lab models on NQ 2026 + 2025, cache
  python -X utf8 tools/lab_confluences.py lookahead 120        # recompute on bars cut at the entry; must match
  python -X utf8 tools/lab_confluences.py write      # re-render the markdown from the json
Test-bed caches: research/lab/conf_testbed_orig1day.json (engine, max 1/day: 2026 + 2025-04-14..12-31),
  conf_testbed_engine.json (engine, max 2/day: 2026 + 2025), conf_testbed_models.json (lab models, by module mtime).
  The engine caches were built once with strategy_lab.engine_trades(params, start, end, procs=2..3).
"""
from __future__ import annotations

import collections
import datetime as dt
import importlib
import itertools
import json
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.strategy_lab import ET  # noqa: E402

LAB = os.path.join(ROOT, "research", "lab")
_CTX: dict = {}
_NEWS = None

# ------------------------------------------------------------------------------------------------ catalog of features
# name -> (group, one-line mechanical definition). Long wording; shorts are mirrored.
FEATURES = {
    # ICT core: premium / discount, OTE
    "pd_disc_pdr": ("ICT P/D", "entry below the 50% of the prior day's full-session range (long) / above (short)"),
    "near_eq_pdr": ("ICT P/D", "entry within 10% of the prior-day range around its 50% (equilibrium)"),
    "pd_disc_day": ("ICT P/D", "entry below the 50% of today's range so far (session from 18:00)"),
    "pd_disc_h1": ("ICT P/D", "entry below the 50% of the 1H dealing range (last confirmed 1H swing high / low)"),
    "pd_disc_week": ("ICT P/D", "entry below the 50% of the prior week's range"),
    "ote_5m": ("ICT P/D", "entry at a 62-79% retracement of the last 5m up-leg (low of 3 h -> high since), leg >= 1.5 ATR"),
    # PD arrays
    "in_fvg_5m": ("PD array", "entry inside an unfilled bullish 5m FVG formed in the last 2 h (+-0.1 ATR)"),
    "fvg_1h_leg": ("PD array", "a bullish 5m FVG >= 0.25 ATR formed in the last hour (displacement left a gap)"),
    "ifvg_5m": ("PD array", "a bearish 5m FVG (last 3 h) was inverted by a close above its top in the last hour"),
    "in_ob_5m": ("PD array", "entry inside a bullish order block: last down candle before a >=1 ATR up body, unbroken, last 3 h"),
    "in_breaker_5m": ("PD array", "entry inside a bullish breaker: up candle at a swing high, lower low taken, then close above that high"),
    "in_mitig_5m": ("PD array", "entry inside a bullish mitigation block: as breaker but the dip made a higher low"),
    "rejection_wick": ("PD array", "the lowest bar of the last 30 min has a lower wick >= 50% of its range"),
    "in_rejection_blk": ("PD array", "entry inside the wick zone (low .. body bottom) of a long-wick swing low of the last 2 h"),
    "in_bpr_5m": ("PD array", "entry inside a balanced price range (bearish FVG overlapped by a later bullish FVG, last 2 h)"),
    "vol_imb_5m": ("PD array", "a bullish volume imbalance (body gap between two up candles) in the last 30 min"),
    "liq_void_draw": ("PD array", "an unfilled bearish liquidity void (>= 2 ATR candle, last 6 h) above the entry (draw)"),
    # structure
    "mss_disp": ("Structure", "close above the last 5m swing high in the last hour with displacement (>=0.8 ATR body or FVG)"),
    "choch_5m": ("Structure", "5m change of character: close above a swing high that was a lower high, in the last hour"),
    "trend_5m_with": ("Structure", "the last 5m break of structure was upward"),
    "trend_15m_with": ("Structure", "15m BOS trend up (last close through a confirmed 15m swing was upward)"),
    "trend_1h_with": ("Structure", "1H BOS trend up (last close through a confirmed 1H swing was upward)"),
    "daily_bias_with": ("Structure", "ICT daily bias up: prior day closed above the day before's high, or swept its low and closed back in"),
    "erl_swept": ("Structure", "external sell-side liquidity (PDL / PWL / Asia low / London low, untaken earlier) swept in the last 3 h"),
    "erl_to_irl": ("Structure", "erl_swept and the entry is inside a bullish 5m FVG (ERL -> IRL entry)"),
    "inducement": ("Structure", "a confirmed 5m swing low inside the down-leg was taken before the final low (staircase/IDM)"),
    "cisd": ("Structure", "CISD: a close above the open of the down-candle run that printed the last-hour low"),
    # time
    "in_macro": ("ICT time", "entry inside an ICT macro (02:33-03:00, 04:03-04:30, 08:50-09:10, 09:50-10:10, 10:50-11:10, 11:50-12:10, 13:10-13:40, 15:15-15:45)"),
    "in_sb_hour": ("ICT time", "entry inside a Silver Bullet hour (03-04, 10-11, 14-15 ET)"),
    "kz_ny_am": ("ICT time", "entry inside the NY AM killzone 08:30-11:00"),
    "kz_ny_pm": ("ICT time", "entry inside the NY PM killzone 13:30-16:00"),
    "kz_london": ("ICT time", "entry inside the London killzone 02:00-05:00"),
    "first_hour_rth": ("ICT time", "entry in the first RTH hour 09:30-10:30"),
    "qt_ny_q3": ("ICT time", "Quarterly Theory: entry in Q3 (09:00-10:30) of the NY AM session 06:00-12:00"),
    "qt_micro_23": ("ICT time", "Quarterly Theory: entry in the 2nd or 3rd 22.5-min quarter of its 90-min cycle"),
    "below_mo": ("ICT time", "entry below the 00:00 ET midnight open (after midnight)"),
    "below_globex_open": ("ICT time", "entry below the 18:00 ET daily (Globex) open"),
    "below_0830": ("ICT time", "entry below the 08:30 ET open (after 08:30)"),
    "below_rth_open": ("ICT time", "entry below the 09:30 RTH open (after 09:30)"),
    "below_tso": ("ICT time", "entry below the Quarterly-Theory true session open (open of Q2 of the 6-h session)"),
    "below_week_open": ("ICT time", "entry below the weekly open (Sunday 18:00)"),
    "nwog_draw": ("ICT time", "the NWOG consequent encroachment (Fri close / Sun open midpoint) is above the entry"),
    "in_nwog": ("ICT time", "entry inside the NWOG range (+-0.1 ATR)"),
    "ndog_draw": ("ICT time", "the NDOG midpoint (17:00 close / 18:00 open) is above the entry"),
    "judas_mo": ("ICT time", "Judas: after midnight price ran >= 0.1 ADR below the midnight open, entry back above it"),
    "judas_rth": ("ICT time", "Judas: after 09:30 price ran >= 0.1 ADR below the RTH open, entry (>= 09:45) back above it"),
    # ranges and profiles
    "po3_daily": ("Ranges", "daily PO3: today's low so far >= 0.15 ADR below the 18:00 open and entry <= open + 0.15 ADR"),
    "wk_profile_early": ("Ranges", "Mon-Wed and entry in the bottom 30% of the week's range so far (low of week forming early)"),
    "cbdr_ext": ("Ranges", "today's low (since 20:00) is 1-4 CBDR standard deviations below the CBDR (14:00-20:00) low"),
    "asia_ext": ("Ranges", "today's low since 00:00 is 2-4 Asia-range SDs below the Asia (20:00-00:00) low"),
    "asia_small": ("Ranges", "the Asia range is <= 40% of the 20-day ADR (accumulation)"),
    # AMT / volume
    "vwap_rth_with": ("AMT", "entry above the RTH (09:30) VWAP"),
    "vwap_eth_with": ("AMT", "entry above the session (18:00) VWAP"),
    "vwap_2sd_fade": ("AMT", "entry below session VWAP - 2 SD (stretched; mean reversion long)"),
    "vwap_1sd_inside": ("AMT", "entry within +-1 SD of session VWAP"),
    "in_prior_value": ("AMT", "entry inside the prior RTH value area (VAL..VAH, 70%)"),
    "poc_side_with": ("AMT", "entry above the prior RTH POC"),
    "open_in_value": ("AMT", "09:30 open inside the prior value area (balance)"),
    "open_out_value_with": ("AMT", "09:30 open above the prior VAH (imbalance up)"),
    "ib_break_with": ("AMT", "after 10:30, a close above the initial-balance high happened before the entry"),
    "ib_narrow": ("AMT", "initial balance (09:30-10:30) < 30% of the 20-day ADR"),
    "orb_with": ("AMT", "after 10:00, entry above the 30-min opening-range high"),
    "in_or": ("AMT", "after 10:00, entry inside the 30-min opening range"),
    "at_lvn": ("AMT", "entry at a low-volume node of the prior 5 sessions' profile (< 0.5x median bin)"),
    "at_hvn": ("AMT", "entry at a high-volume node of the prior 5 sessions' profile (> 1.5x median bin)"),
    # classic
    "round_big": ("Classic", "the last-30-min low is within 0.15 ATR of a 100-pt NQ level (50-pt ES), unadjusted price"),
    "round_q": ("Classic", "the last-30-min low is within 0.15 ATR of a 00/25/50/75 level, unadjusted price"),
    "pdl_swept": ("Classic", "prior-day low swept (traded through, untaken earlier today) in the last hour"),
    "pwl_swept": ("Classic", "prior-week low swept in the last hour"),
    "in_pw_range": ("Classic", "entry inside the prior week's range"),
    "dow_mon": ("Classic", "Monday"), "dow_tue": ("Classic", "Tuesday"), "dow_wed": ("Classic", "Wednesday"),
    "dow_thu": ("Classic", "Thursday"), "dow_fri": ("Classic", "Friday"),
    "news_day": ("Classic", "a high-impact US release today (CPI, NFP, FOMC; data/news/events.csv)"),
    "fomc_day": ("Classic", "FOMC decision day"),
    "cpi_nfp_day": ("Classic", "CPI or NFP day"),
    "adr_room": ("Classic", "at least 50% of the 20-day ADR left above the entry (low so far + ADR - entry >= 0.5 ADR)"),
    "adr_exhausted": ("Classic", "today's range so far >= 100% of the 20-day ADR"),
    "atr_expanding": ("Classic", "mean 5m true range of the last 30 min >= 1.3x its 10-day same-time average"),
    "nr4_prev": ("Classic", "prior day was an NR4 (narrowest range of the last 4 sessions)"),
    "trend_day_with": ("Classic", "trend day up so far: >= 0.4 ADR above the 18:00 open and in the top 25% of today's range"),
    "trend_day_against": ("Classic", "trend day down so far (the mirror), i.e. trading against a trend day"),
    "gap_big": ("Classic", "RTH gap (09:30 open vs prior 16:00 close) >= 0.25 ADR"),
    "gap_with": ("Classic", "RTH gap up >= 0.1 ADR (gap in the trade's direction)"),
    "gap_against": ("Classic", "RTH gap down >= 0.1 ADR (fading / against the gap)"),
    # intermarket
    "nq_rs_with": ("Intermarket", "NQ stronger than ES since the 09:30 open (18:00 before RTH): long the stronger index"),
    "es_vwap_with": ("Intermarket", "ES above its own session VWAP"),
    "es_trend_with": ("Intermarket", "ES up since its 18:00 open"),
    "smt_es": ("Intermarket", "SMT: exactly one of NQ / ES swept its 4-h low in the last 30 min (divergence)"),
    "es_confirms": ("Intermarket", "both NQ and ES swept their 4-h lows in the last 30 min (no divergence)"),
}
BOOL = list(FEATURES)


# ------------------------------------------------------------------------------------------------ helpers
def _trading_day(ts):
    return (dt.datetime.fromtimestamp(int(ts), ET) + dt.timedelta(hours=6)).strftime("%Y-%m-%d")


def _news():
    global _NEWS
    if _NEWS is None:
        _NEWS = collections.defaultdict(list)
        p = os.path.join(ROOT, "data", "news", "events.csv")
        if os.path.exists(p):
            df = pd.read_csv(p)
            for r in df.itertuples():
                hh, mm = str(r.time_et).split(":")[:2]
                _NEWS[str(r.date)].append((int(hh) * 60 + int(mm), str(r.event), str(r.impact)))
    return _NEWS


def _rolls(nq_like):
    p = os.path.join(ROOT, "data", "NQ_rolls.json" if nq_like else "ES_rolls.json")
    try:
        with open(p, encoding="utf-8") as fh:
            rr = json.load(fh)["rolls"]
    except Exception:
        return np.zeros(0), np.zeros(1)
    by = {}
    for r in rr:                                    # one gap per target contract (ES file lists ESZ26 twice; keep last)
        if r.get("switch_t") and r.get("gap") is not None:
            by[r.get("to")] = (int(r["switch_t"]), float(r["gap"]))
    v = sorted(by.values())
    sw = np.array([a for a, _ in v], np.int64)
    gaps = np.array([g for _, g in v], float)
    suffix = np.r_[np.cumsum(gaps[::-1])[::-1], 0.0]  # suffix[i] = sum of gaps of rolls i.. (switch after the bar)
    return sw, suffix


def _segments(key):
    brk = np.flatnonzero(key[1:] != key[:-1]) + 1
    return np.r_[0, brk], np.r_[brk, len(key)]


class _HTF:
    """Resampled clock bars (15m / 1H) with 3-candle swings and a BOS trend, all known at each bar's close."""

    def __init__(self, t, o, h, l, c, span):
        key = t // span
        s, e = _segments(key)
        self.close_t = (key[s] + 1) * span
        self.o, self.c = o[s], c[e - 1]
        self.h, self.l = np.maximum.reduceat(h, s), np.minimum.reduceat(l, s)
        n = len(s)
        self.trend = np.zeros(n, np.int8)
        self.sh_at = np.full(n, np.nan)
        self.sl_at = np.full(n, np.nan)
        H, L, C = self.h, self.l, self.c
        sh = sl = None
        shb = slb = True
        tr = 0
        for m in range(n):
            if m >= 2:                                   # swing at m-1 confirmed by bar m's close
                if H[m - 1] > H[m - 2] and H[m - 1] > H[m]:
                    sh, shb = H[m - 1], False
                if L[m - 1] < L[m - 2] and L[m - 1] < L[m]:
                    sl, slb = L[m - 1], False
            if sh is not None and not shb and C[m] > sh:
                tr, shb = 1, True
            if sl is not None and not slb and C[m] < sl:
                tr, slb = -1, True
            self.trend[m] = tr
            self.sh_at[m] = np.nan if sh is None else sh
            self.sl_at[m] = np.nan if sl is None else sl

    def last(self, entry_t):
        return int(np.searchsorted(self.close_t, entry_t, side="right")) - 1


class Ctx:
    """Everything precomputed once per bars frame."""

    def __init__(self, b):
        self.t = b["time"].to_numpy(np.int64)
        self.o, self.h = b["open"].to_numpy(float), b["high"].to_numpy(float)
        self.l, self.c = b["low"].to_numpy(float), b["close"].to_numpy(float)
        self.v = np.maximum(b["volume"].to_numpy(float), 0.0)
        self.mod = b["mod"].to_numpy(np.int64)
        day = b["day"].to_numpy()
        n = len(self.t)
        self.ds, self.de = _segments(day)
        self.days = [str(day[i]) for i in self.ds]
        self.day_ix = {d: k for k, d in enumerate(self.days)}
        self.di = np.repeat(np.arange(len(self.ds)), self.de - self.ds)
        self.nq_like = float(np.median(self.c)) > 9000
        self.step_big, self.step_q = (100.0, 25.0) if self.nq_like else (50.0, 25.0)
        self.roll_t, self.roll_suffix = _rolls(self.nq_like)
        o, h, l, c, v, mod = self.o, self.h, self.l, self.c, self.v, self.mod
        pc = np.r_[c[0], c[:-1]]
        self.tr = np.maximum(h, pc) - np.minimum(l, pc)
        self.atr = pd.Series(self.tr).rolling(14, min_periods=1).mean().to_numpy()
        # session VWAP (18:00) and RTH VWAP (09:30-16:00) with SD
        tp = (h + l + c) / 3.0
        self.vw_e, self.sd_e = self._vwap(tp, v, self.di)
        rth = (mod >= 570) & (mod < 960)
        g = np.where(rth, self.di, -1)
        vr, sr = self._vwap(tp, np.where(rth, v, 0.0), g)
        self.vw_r = np.where(rth, vr, np.nan)
        # FVGs
        self.fvg_up = np.zeros(n, bool)
        self.fvg_dn = np.zeros(n, bool)
        self.fvg_up[2:] = l[2:] > h[:-2]
        self.fvg_dn[2:] = h[2:] < l[:-2]
        # 5m fractal swings (2 bars each side; confirmed at idx + 2)
        sh = np.zeros(n, bool)
        sl = np.zeros(n, bool)
        sh[2:-2] = (h[2:-2] > h[1:-3]) & (h[2:-2] > h[:-4]) & (h[2:-2] >= h[3:-1]) & (h[2:-2] >= h[4:])
        sl[2:-2] = (l[2:-2] < l[1:-3]) & (l[2:-2] < l[:-4]) & (l[2:-2] <= l[3:-1]) & (l[2:-2] <= l[4:])
        self.sh_idx, self.sl_idx = np.flatnonzero(sh), np.flatnonzero(sl)
        self._structure()
        self.h1 = _HTF(self.t, o, h, l, c, 3600)
        self.m15 = _HTF(self.t, o, h, l, c, 900)
        self._days()
        # true range by (day, 5-min slot from 18:00) for the time-of-day volatility baseline
        slot = ((mod - 1080) % 1440) // 5
        self.trm = np.full((len(self.ds), 288), np.nan)
        self.trm[self.di, slot] = self.tr
        self.slot = slot
        self._prof = {}

    @staticmethod
    def _vwap(tp, v, g):
        df = pd.DataFrame({"g": g, "v": v, "pv": v * tp, "pv2": v * tp * tp})
        cs = df.groupby("g")[["v", "pv", "pv2"]].cumsum().to_numpy()
        with np.errstate(invalid="ignore", divide="ignore"):
            vw = np.where(cs[:, 0] > 0, cs[:, 1] / cs[:, 0], tp)
            var = np.where(cs[:, 0] > 0, cs[:, 2] / cs[:, 0] - vw * vw, 0.0)
        return vw, np.sqrt(np.maximum(var, 0.0))

    def _structure(self):
        n, c = len(self.t), self.c
        self.brk_up, self.brk_dn = np.zeros(n, bool), np.zeros(n, bool)
        self.choch_up, self.choch_dn = np.zeros(n, bool), np.zeros(n, bool)
        self.trend5 = np.zeros(n, np.int8)
        hi, lo = self.h, self.l
        ih = il = 0
        sh = sl = psh = psl = None
        shb = slb = True
        tr = 0
        SH, SL = self.sh_idx, self.sl_idx
        for k in range(n):
            while ih < len(SH) and SH[ih] + 2 <= k:
                psh, sh, shb = sh, hi[SH[ih]], False
                ih += 1
            while il < len(SL) and SL[il] + 2 <= k:
                psl, sl, slb = sl, lo[SL[il]], False
                il += 1
            if sh is not None and not shb and c[k] > sh:
                self.brk_up[k], shb, tr = True, True, 1
                if psh is not None and sh < psh:
                    self.choch_up[k] = True
            if sl is not None and not slb and c[k] < sl:
                self.brk_dn[k], slb, tr = True, True, -1
                if psl is not None and sl > psl:
                    self.choch_dn[k] = True
            self.trend5[k] = tr

    def _days(self):
        o, h, l, c, mod, t = self.o, self.h, self.l, self.c, self.mod, self.t
        D = []
        for k, (a, z) in enumerate(zip(self.ds, self.de)):
            m = mod[a:z]
            x = {"open18": o[a], "hi": h[a:z].max(), "lo": l[a:z].min(), "close": c[z - 1], "first_t": int(t[a])}
            tday = dt.date.fromisoformat(self.days[k])

            def nominal(minute, tday=tday):
                # ET wall clock of this trading day; minutes >= 18:00 belong to the previous calendar evening
                d0 = tday - dt.timedelta(days=1) if minute >= 1080 else tday
                return int(dt.datetime(d0.year, d0.month, d0.day, minute // 60, minute % 60, tzinfo=ET).timestamp())

            def win(mask, end_min, a=a):
                # window stats; it counts as finished only once the clock passes its nominal end (live-safe)
                idx = np.flatnonzero(mask)
                if not len(idx):
                    return None
                ii = idx + a
                return {"hi": float(h[ii].max()), "lo": float(l[ii].min()), "end_t": nominal(end_min),
                        "start_t": int(t[ii[0]]), "open": float(o[ii[0]]), "close": float(c[ii[-1]]), "i0": int(ii[0]),
                        "i1": int(ii[-1])}
            x["asia"] = win(m >= 1200, 0)                             # 20:00-24:00, done at 00:00
            x["lon"] = win((m >= 120) & (m < 300), 300)
            x["rth"] = win((m >= 570) & (m < 960), 960)
            x["ib"] = win((m >= 570) & (m < 630), 630)
            x["or"] = win((m >= 570) & (m < 600), 600)
            x["eve"] = win((m >= 1080) & (m < 1200), 1200)           # 18:00-20:00 part of the CBDR
            x["late"] = win((m >= 840) & (m < 1020), 1020)           # 14:00-17:00 (the CBDR start, used by the next day)
            pm = np.flatnonzero(m < 1080)
            x["mo"] = (float(o[a + pm[0]]), int(t[a + pm[0]])) if len(pm) else None
            p8 = np.flatnonzero((m >= 510) & (m < 1080))
            x["o0830"] = (float(o[a + p8[0]]), int(t[a + p8[0]])) if len(p8) else None
            x["date"] = dt.date.fromisoformat(self.days[k])
            x["wd"] = x["date"].weekday()
            x["wk"] = tuple(x["date"].isocalendar()[:2])
            D.append(x)
        for k, x in enumerate(D):
            rng = [D[i]["hi"] - D[i]["lo"] for i in range(max(0, k - 20), k)]
            x["adr20"] = float(np.mean(rng)) if len(rng) >= 5 else None
            if k >= 1:
                p = D[k - 1]
                x["pdh"], x["pdl"], x["pdc"] = p["hi"], p["lo"], p["close"]
                x["prth_close"] = p["rth"]["close"] if p["rth"] else None
                x["ndog"] = (min(p["close"], x["open18"]), max(p["close"], x["open18"]))
                if p["late"] and x["eve"]:
                    x["cbdr"] = {"hi": max(p["late"]["hi"], x["eve"]["hi"]), "lo": min(p["late"]["lo"], x["eve"]["lo"]),
                                 "end_t": x["eve"]["end_t"]}
                else:
                    x["cbdr"] = None
            if k >= 2:
                p, q = D[k - 1], D[k - 2]
                if p["close"] > q["hi"]:
                    b = 1
                elif p["close"] < q["lo"]:
                    b = -1
                elif p["hi"] > q["hi"] and p["lo"] >= q["lo"]:
                    b = -1                                   # swept the high only and closed back inside
                elif p["lo"] < q["lo"] and p["hi"] <= q["hi"]:
                    b = 1
                else:
                    b = 0
                x["bias"] = b
            if k >= 4:
                r = [D[i]["hi"] - D[i]["lo"] for i in range(k - 4, k)]
                x["nr4"] = bool(r[-1] < min(r[:-1]))
        # weeks
        wk_days = collections.OrderedDict()
        for k, x in enumerate(D):
            wk_days.setdefault(x["wk"], []).append(k)
        keys = list(wk_days)
        for wi, w in enumerate(keys):
            ks = wk_days[w]
            prev = wk_days[keys[wi - 1]] if wi >= 1 else None
            for k in ks:
                x = D[k]
                x["wk_start"] = ks[0]
                x["wk_open"] = D[ks[0]]["open18"]
                if prev and len(prev) >= 3:
                    x["pwh"] = max(D[i]["hi"] for i in prev)
                    x["pwl"] = min(D[i]["lo"] for i in prev)
                    fc, so = D[prev[-1]]["close"], D[ks[0]]["open18"]
                    x["nwog"] = (min(fc, so), max(fc, so))
        self.D = D

    def profile(self, k):
        """Prior-RTH value area (VAL, POC, VAH) of day k's RTH, from 5m volume spread evenly over each bar's range."""
        if k in self._prof:
            return self._prof[k]
        x = self.D[k]
        out = None
        if x["rth"]:
            a, z = x["rth"]["i0"], x["rth"]["i1"] + 1
            lo, hi = self.l[a:z], self.h[a:z]
            bs = 1.0 if self.nq_like else 0.25
            b0 = np.floor(lo / bs).astype(np.int64)
            b1 = np.floor(hi / bs).astype(np.int64)
            base = int(b0.min())
            vol = np.zeros(int(b1.max()) - base + 1)
            for i in range(len(b0)):
                nb = b1[i] - b0[i] + 1
                vol[b0[i] - base:b1[i] - base + 1] += self.v[a + i] / nb
            poc = int(np.argmax(vol))
            tot, acc, lo_i, hi_i = vol.sum(), vol[poc], poc, poc
            while acc < 0.7 * tot and (lo_i > 0 or hi_i < len(vol) - 1):
                up = vol[hi_i + 1] if hi_i < len(vol) - 1 else -1
                dn = vol[lo_i - 1] if lo_i > 0 else -1
                if up >= dn:
                    hi_i += 1
                    acc += up
                else:
                    lo_i -= 1
                    acc += dn
            out = ((base + lo_i) * bs, (base + poc + 0.5) * bs, (base + hi_i + 1) * bs)
        self._prof[k] = out
        return out

    def vol_nodes(self, k, days=5):
        key = ("vn", k)
        if key in self._prof:
            return self._prof[key]
        if k < days:
            self._prof[key] = None
            return None
        a, z = self.ds[k - days], self.de[k - 1]
        lo, hi, v = self.l[a:z], self.h[a:z], self.v[a:z]
        bs = 2.0 if self.nq_like else 0.5
        b0 = np.floor(lo / bs).astype(np.int64)
        b1 = np.floor(hi / bs).astype(np.int64)
        base = int(b0.min())
        vol = np.zeros(int(b1.max()) - base + 1)
        nb = b1 - b0 + 1
        for i in range(len(b0)):
            vol[b0[i] - base:b1[i] - base + 1] += v[i] / nb[i]
        med = float(np.median(vol[vol > 0])) if (vol > 0).any() else 0.0
        out = (base, bs, vol, med)
        self._prof[key] = out
        return out

    def unadj(self, px, ts):
        if not len(self.roll_t):
            return px
        i = int(np.searchsorted(self.roll_t, ts, side="right"))
        return px - self.roll_suffix[i]

    # ------------------------------------------------------------------------------------------ per-trade features
    def feat(self, entry_t, d, es=None, entry_px=None):
        t, o, h, l, c = self.t, self.o, self.h, self.l, self.c
        entry_t, d = int(entry_t), (1 if d > 0 else -1)
        j = int(np.searchsorted(t, entry_t - 300, side="right")) - 1
        day = _trading_day(entry_t)
        k = self.day_ix.get(day)
        if j < 100 or k is None or k < 6:
            return {}
        D = self.D[k]
        jn = j + 1
        if entry_px is not None:
            p0 = float(entry_px)
        elif jn < len(t) and t[jn] == entry_t:
            p0 = float(o[jn])
        else:
            p0 = float(c[j])
        e = dt.datetime.fromtimestamp(entry_t, ET)
        me = e.hour * 60 + e.minute
        a = float(self.atr[j]) or 1.0
        tol = 0.1 * a
        adr = D.get("adr20") or (D["hi"] - D["lo"])
        s0 = int(self.ds[k])
        tod = j >= s0
        F = {"p0_x": p0, "atr_x": a, "adr_x": adr, "mod_x": me}

        def below(ref):                         # entry on the discount side of ref for this direction
            return None if ref is None else bool((p0 - ref) * d < 0)

        # mirrored window arrays (long logic everywhere): last W bars ending at j
        W = 80
        w0 = max(0, j - W + 1)
        if d == 1:
            O, H, L, C = o[w0:j + 1], h[w0:j + 1], l[w0:j + 1], c[w0:j + 1]
        else:
            O, H, L, C = -o[w0:j + 1], -l[w0:j + 1], -h[w0:j + 1], -c[w0:j + 1]
        P = d * p0
        A = self.atr[w0:j + 1]
        n = len(C)
        jl = n - 1
        fup = np.zeros(n, bool)
        fdn = np.zeros(n, bool)
        fup[2:] = L[2:] > H[:-2]
        fdn[2:] = H[2:] < L[:-2]

        # ---- premium / discount
        if D.get("pdh") is not None:
            rng = D["pdh"] - D["pdl"]
            F["pd_disc_pdr"] = below((D["pdh"] + D["pdl"]) / 2)
            pos = (p0 - D["pdl"]) / rng if rng > 0 else 0.5
            F["near_eq_pdr"] = bool(abs(pos - 0.5) <= 0.1)
            F["pos_pdr_x"] = round(pos, 3)
        if tod:
            hs, ls = float(h[s0:j + 1].max()), float(l[s0:j + 1].min())
            F["pd_disc_day"] = below((hs + ls) / 2) if hs > ls else None
        else:
            hs = ls = None
        q = self.h1.last(entry_t)
        if q >= 0 and not np.isnan(self.h1.sh_at[q]) and not np.isnan(self.h1.sl_at[q]) and self.h1.sh_at[q] > self.h1.sl_at[q]:
            F["pd_disc_h1"] = below((self.h1.sh_at[q] + self.h1.sl_at[q]) / 2)
        F["trend_1h_with"] = bool(q >= 0 and self.h1.trend[q] == d)
        q15 = self.m15.last(entry_t)
        F["trend_15m_with"] = bool(q15 >= 0 and self.m15.trend[q15] == d)
        if D.get("pwh") is not None:
            F["pd_disc_week"] = below((D["pwh"] + D["pwl"]) / 2)
            F["in_pw_range"] = bool(D["pwl"] <= p0 <= D["pwh"])
        # OTE on the last 3h up-leg
        wl = L[max(0, n - 36):]
        il = int(np.argmin(wl)) + max(0, n - 36)
        lo_leg = L[il]
        hi_leg = H[il:].max()
        leg = hi_leg - lo_leg
        if leg >= 1.5 * a:
            ret = (hi_leg - P) / leg
            F["ote_5m"] = bool(0.62 <= ret <= 0.79)
            F["ote_ret_x"] = round(float(ret), 3)
        else:
            F["ote_5m"] = False

        # ---- PD arrays
        def fvg_zones(mask, lookback, up=True):
            out = []
            for i in range(max(2, n - lookback), n):
                if not mask[i]:
                    continue
                if up:
                    bot, top = H[i - 2], L[i]
                    if (C[i + 1:] < bot).any():
                        continue
                else:
                    bot, top = H[i], L[i - 2]
                    if (C[i + 1:] > top).any():
                        continue
                out.append((i, bot, top))
            return out
        ups = fvg_zones(fup, 24, True)
        F["in_fvg_5m"] = any(b - tol <= P <= tp + tol for _, b, tp in ups)
        F["fvg_1h_leg"] = any(fup[i] and (L[i] - H[i - 2]) >= 0.25 * a for i in range(max(2, n - 12), n))
        inv = False
        for i in range(max(2, n - 36), n):
            if fdn[i]:
                top = L[i - 2]
                after = np.flatnonzero(C[i + 1:] > top)
                if len(after) and (i + 1 + after[0]) >= n - 12:
                    inv = True
                    break
        F["ifvg_5m"] = inv
        # order block: last down candle before a >= 1 ATR up body, still unbroken
        ob = False
        for m in range(max(1, n - 36), n):
            if C[m] - O[m] >= 1.0 * A[m - 1]:
                for z in range(m - 1, max(-1, m - 6), -1):
                    if C[z] < O[z]:
                        if not (C[z + 1:] < L[z]).any() and L[z] - tol <= P <= H[z] + tol:
                            ob = True
                        break
            if ob:
                break
        F["in_ob_5m"] = ob
        # breaker / mitigation: up candle at a swing high -> dip (lower low = breaker, higher low = mitigation)
        # -> close above that swing high -> entry back inside the candle zone
        sw_hi = [i for i in range(max(12, n - 48), n - 4) if H[i] > H[i - 1] and H[i] > H[i - 2] and H[i] >= H[i + 1] and H[i] >= H[i + 2]]
        brk = mit = False
        for sidx in reversed(sw_hi):
            after = np.flatnonzero(C[sidx + 3:] > H[sidx])
            if not len(after):
                continue
            mb = sidx + 3 + int(after[0])
            if mb >= jl:
                continue
            dip = L[sidx:mb].min()
            pre = L[sidx - 12:sidx].min()
            zc = [z for z in range(sidx, max(sidx - 4, -1), -1) if C[z] > O[z]]
            if not zc:
                continue
            z = zc[0]
            if (C[mb + 1:] < L[z]).any():
                continue
            if L[z] - tol <= P <= H[z] + tol:
                if dip < pre:
                    brk = True
                else:
                    mit = True
            break
        F["in_breaker_5m"], F["in_mitig_5m"] = brk, mit
        # rejection
        e6 = n - 6 + int(np.argmin(L[n - 6:]))
        rg = H[e6] - L[e6]
        F["rejection_wick"] = bool(rg > 0 and (min(O[e6], C[e6]) - L[e6]) >= 0.5 * rg)
        e24 = n - 24 + int(np.argmin(L[n - 24:]))
        rg24, wk24 = H[e24] - L[e24], min(O[e24], C[e24]) - L[e24]
        F["in_rejection_blk"] = bool(rg24 > 0 and wk24 >= 0.5 * rg24 and wk24 >= 0.5 * a and not (C[e24 + 1:] < L[e24]).any()
                                     and L[e24] - tol <= P <= min(O[e24], C[e24]) + tol)
        # BPR: a bearish FVG overlapped by a later bullish FVG, entry inside the overlap
        dns = [(i, H[i], L[i - 2]) for i in range(max(2, n - 24), n) if fdn[i]]
        bpr = False
        for iu, bu, tu in ups:
            for idn, bd, td in dns:
                if idn < iu:
                    lo_o, hi_o = max(bu, bd), min(tu, td)
                    if hi_o > lo_o and lo_o - tol <= P <= hi_o + tol:
                        bpr = True
        F["in_bpr_5m"] = bpr
        F["vol_imb_5m"] = any(O[i] >= C[i - 1] + 0.5 and L[i] <= H[i - 1] and C[i] > O[i] and C[i - 1] > O[i - 1]
                              for i in range(n - 6, n))
        void = False
        for m in range(max(1, n - 72), n - 1):
            if C[m] < O[m] and (H[m] - L[m]) >= 2.0 * A[m - 1] and H[m] > P and H[m + 1:].max() < H[m]:
                void = True
                break
        F["liq_void_draw"] = void

        # ---- structure
        bu_arr = self.brk_up if d == 1 else self.brk_dn
        ch_arr = self.choch_up if d == 1 else self.choch_dn
        mss = False
        for kk in range(max(0, j - 11), j + 1):
            if bu_arr[kk]:
                li = kk - w0
                disp = (C[li] - O[li]) >= 0.8 * A[li - 1] or fup[li] or (li + 1 <= jl and fup[li + 1])
                if disp:
                    mss = True
                    break
        F["mss_disp"] = mss
        F["choch_5m"] = bool(ch_arr[max(0, j - 11):j + 1].any())
        F["trend_5m_with"] = bool(self.trend5[j] == d)
        F["daily_bias_with"] = None if D.get("bias") is None else bool(D["bias"] == d)
        # external liquidity (sell-side for a long), untaken earlier today, swept in the last 36 bars
        lv = []
        if D.get("pdh") is not None:
            lv.append((d * (D["pdl"] if d == 1 else D["pdh"]), s0))
        if D.get("pwh") is not None:
            lv.append((d * (D["pwl"] if d == 1 else D["pwh"]), int(self.ds[D["wk_start"]])))
        for wn in ("asia", "lon"):
            wv = D.get(wn)
            if wv and wv["end_t"] <= entry_t:
                lv.append((d * (wv["lo"] if d == 1 else wv["hi"]), wv["i1"] + 1))
        g0 = max(w0, j - 35)

        def swept(level, since_i, look):
            a0 = max(j - look + 1, since_i)
            if a0 > j:
                return False
            if since_i < a0:                    # untaken between formation and the look window
                pre = (l[since_i:a0].min() if d == 1 else -h[since_i:a0].max()) if a0 > since_i else np.inf
                if pre < level:
                    return False
            lowest = l[a0:j + 1].min() if d == 1 else -h[a0:j + 1].max()
            return bool(lowest < level)
        F["erl_swept"] = any(swept(lvl, si, 36) for lvl, si in lv)
        F["erl_to_irl"] = bool(F["erl_swept"] and F["in_fvg_5m"])
        if D.get("pdh") is not None:
            F["pdl_swept"] = swept(d * (D["pdl"] if d == 1 else D["pdh"]), s0, 12)
        if D.get("pwh") is not None:
            F["pwl_swept"] = swept(d * (D["pwl"] if d == 1 else D["pwh"]), int(self.ds[D["wk_start"]]), 12)
        # inducement: confirmed swing low inside the down-leg, taken before the final (last-hour) low
        ex = n - 12 + int(np.argmin(L[n - 12:]))
        st = max(0, ex - 24) + int(np.argmax(H[max(0, ex - 24):ex + 1]))
        idm = False
        for i in range(max(st + 2, 2), ex - 2):
            if L[i] < L[i - 1] and L[i] < L[i - 2] and L[i] <= L[i + 1] and L[i] <= L[i + 2] and L[i] > L[ex]:
                idm = True
                break
        F["inducement"] = idm
        # CISD
        f = ex if C[ex] < O[ex] else ex - 1
        cis = False
        if f >= 1 and C[f] < O[f]:
            while f - 1 >= max(0, ex - 12) and C[f - 1] < O[f - 1]:
                f -= 1
            cis = bool((C[ex + 1:] > O[f]).any())
        F["cisd"] = cis

        # ---- time
        mac = ((153, 180), (243, 270), (530, 550), (590, 610), (650, 670), (710, 730), (790, 820), (915, 945))
        F["in_macro"] = any(x0 <= me < x1 for x0, x1 in mac)
        F["in_sb_hour"] = any(x0 <= me < x1 for x0, x1 in ((180, 240), (600, 660), (840, 900)))
        F["kz_ny_am"] = 510 <= me < 660
        F["kz_ny_pm"] = 810 <= me < 960
        F["kz_london"] = 120 <= me < 300
        F["first_hour_rth"] = 570 <= me < 630
        F["qt_ny_q3"] = 540 <= me < 630
        ms = (me - 1080) % 1440
        F["qt_micro_23"] = 22.5 <= (ms % 90) < 67.5
        F["below_mo"] = below(D["mo"][0]) if D.get("mo") and D["mo"][1] <= entry_t else None
        F["below_globex_open"] = below(D["open18"])
        F["below_0830"] = below(D["o0830"][0]) if D.get("o0830") and D["o0830"][1] <= entry_t else None
        rth_open = D["rth"]["open"] if D.get("rth") and D["rth"]["start_t"] <= entry_t else None
        F["below_rth_open"] = below(rth_open)
        blk = ms // 360
        q2t = (1080 + blk * 360 + 90) % 1440           # ET minute of the session's Q2 open
        tso = None
        if ms % 360 >= 90:
            ii = np.flatnonzero((self.mod[s0:j + 1] == q2t))
            tso = float(o[s0 + ii[0]]) if len(ii) else None
        F["below_tso"] = below(tso)
        F["below_week_open"] = below(D.get("wk_open"))
        if D.get("nwog") and D["nwog"][1] - D["nwog"][0] >= 0.25:
            lo_g, hi_g = D["nwog"]
            F["nwog_draw"] = bool(((lo_g + hi_g) / 2 - p0) * d > tol)
            F["in_nwog"] = bool(lo_g - tol <= p0 <= hi_g + tol)
        else:
            F["nwog_draw"] = F["in_nwog"] = False
        if D.get("ndog") and D["ndog"][1] - D["ndog"][0] >= 0.25:
            F["ndog_draw"] = bool(((D["ndog"][0] + D["ndog"][1]) / 2 - p0) * d > tol)
        else:
            F["ndog_draw"] = False
        if D.get("mo") and D["mo"][1] <= entry_t:
            i_mo = int(np.searchsorted(t, D["mo"][1]))
            if i_mo <= j:
                ext = l[i_mo:j + 1].min() if d == 1 else h[i_mo:j + 1].max()
                F["judas_mo"] = bool((D["mo"][0] - ext) * d >= 0.1 * adr and (p0 - D["mo"][0]) * d > 0)
        if rth_open is not None and me >= 585 and me < 720:
            i_r = D["rth"]["i0"]
            if i_r <= j:
                ext = l[i_r:j + 1].min() if d == 1 else h[i_r:j + 1].max()
                F["judas_rth"] = bool((rth_open - ext) * d >= 0.1 * adr and (p0 - rth_open) * d > 0)
        else:
            F["judas_rth"] = False

        # ---- ranges / profiles
        if tod:
            ext_d = ls if d == 1 else hs
            F["po3_daily"] = bool((D["open18"] - ext_d) * d >= 0.15 * adr and (p0 - D["open18"]) * d <= 0.15 * adr)
            F["adr_room"] = bool(((ls + adr - p0) if d == 1 else (p0 - (hs - adr))) >= 0.5 * adr)
            F["adr_exhausted"] = bool(hs - ls >= adr)
            F["adr_used_x"] = round((hs - ls) / adr, 3)
            up_move = (c[j] - D["open18"]) * d
            pos_d = (c[j] - ls) / (hs - ls) if hs > ls else 0.5
            F["trend_day_with"] = bool(up_move >= 0.4 * adr and (pos_d >= 0.75 if d == 1 else pos_d <= 0.25))
            F["trend_day_against"] = bool(-up_move >= 0.4 * adr and (pos_d <= 0.25 if d == 1 else pos_d >= 0.75))
        ws = int(self.ds[D["wk_start"]])
        if ws <= j:
            wh, wlo = float(h[ws:j + 1].max()), float(l[ws:j + 1].min())
            if wh - wlo >= 0.5 * adr:
                pw = (p0 - wlo) / (wh - wlo)
                F["wk_profile_early"] = bool(D["wd"] <= 2 and (pw <= 0.3 if d == 1 else pw >= 0.7))
            else:
                F["wk_profile_early"] = False
        cb = D.get("cbdr")
        if cb and cb["end_t"] <= entry_t and cb["hi"] > cb["lo"]:
            i20 = int(np.searchsorted(t, cb["end_t"]))
            if i20 <= j:
                ext = l[i20:j + 1].min() if d == 1 else h[i20:j + 1].max()
                nsd = ((cb["lo"] - ext) if d == 1 else (ext - cb["hi"])) / (cb["hi"] - cb["lo"])
                F["cbdr_ext"] = bool(1.0 <= nsd <= 4.0)
                F["cbdr_sd_x"] = round(float(nsd), 2)
        asia = D.get("asia")
        if asia and asia["end_t"] <= entry_t and asia["hi"] > asia["lo"]:
            F["asia_small"] = bool((asia["hi"] - asia["lo"]) <= 0.4 * adr)
            i00 = int(np.searchsorted(t, asia["end_t"]))
            if i00 <= j:
                ext = l[i00:j + 1].min() if d == 1 else h[i00:j + 1].max()
                nsd = ((asia["lo"] - ext) if d == 1 else (ext - asia["hi"])) / (asia["hi"] - asia["lo"])
                F["asia_ext"] = bool(2.0 <= nsd <= 4.0)
                F["asia_sd_x"] = round(float(nsd), 2)

        # ---- AMT
        if not np.isnan(self.vw_r[j]) and self.di[j] == k:
            F["vwap_rth_with"] = bool((p0 - self.vw_r[j]) * d > 0)
        if tod:
            vw, sd = self.vw_e[j], self.sd_e[j]
            F["vwap_eth_with"] = bool((p0 - vw) * d > 0)
            F["vwap_2sd_fade"] = bool(sd > 0 and (p0 - (vw - d * 2 * sd)) * d < 0)
            F["vwap_1sd_inside"] = bool(abs(p0 - vw) <= sd)
        pr = self.profile(k - 1)
        if pr:
            val, poc, vah = pr
            F["in_prior_value"] = bool(val <= p0 <= vah)
            F["poc_side_with"] = bool((p0 - poc) * d > 0)
            if rth_open is not None:
                F["open_in_value"] = bool(val <= rth_open <= vah)
                F["open_out_value_with"] = bool((rth_open > vah) if d == 1 else (rth_open < val))
        ib = D.get("ib")
        if ib and ib["end_t"] <= entry_t:
            F["ib_narrow"] = bool((ib["hi"] - ib["lo"]) < 0.3 * adr)
            i10 = int(np.searchsorted(t, ib["end_t"]))
            lvl = ib["hi"] if d == 1 else ib["lo"]
            F["ib_break_with"] = bool(i10 <= j and ((c[i10:j + 1] - lvl) * d > 0).any())
        else:
            F["ib_break_with"] = False
        orr = D.get("or")
        if orr and orr["end_t"] <= entry_t:
            F["orb_with"] = bool((p0 - (orr["hi"] if d == 1 else orr["lo"])) * d > 0)
            F["in_or"] = bool(orr["lo"] <= p0 <= orr["hi"])
        else:
            F["orb_with"] = F["in_or"] = False
        vn = self.vol_nodes(k)
        if vn:
            base, bs, vol, med = vn
            bi = int(np.floor(p0 / bs)) - base
            if 0 <= bi < len(vol) and med > 0:
                F["at_lvn"] = bool(vol[bi] < 0.5 * med)
                F["at_hvn"] = bool(vol[bi] > 1.5 * med)
            else:
                F["at_lvn"], F["at_hvn"] = True, False      # outside the 5-day profile = no volume there

        # ---- classic
        ext6 = (l[j - 5:j + 1].min() if d == 1 else h[j - 5:j + 1].max())
        ux = self.unadj(float(ext6), int(t[j]))
        tr_ = max(0.15 * a, 0.5)
        F["round_big"] = bool(abs(ux - round(ux / self.step_big) * self.step_big) <= tr_)
        F["round_q"] = bool(abs(ux - round(ux / self.step_q) * self.step_q) <= tr_)
        for i_, nm in enumerate(("dow_mon", "dow_tue", "dow_wed", "dow_thu", "dow_fri")):
            F[nm] = D["wd"] == i_
        ev = [x for x in _news().get(day, []) if x[2] == "high"]
        F["news_day"] = bool(ev)
        F["fomc_day"] = any("FOMC" in x[1] for x in ev)
        F["cpi_nfp_day"] = any(("CPI" in x[1]) or ("Non-Farm" in x[1]) for x in ev)
        sl6 = self.slot[j - 5:j + 1]
        if k >= 11 and self.di[j - 5] == k:
            base_tr = np.nanmean(self.trm[k - 10:k][:, sl6])
            F["atr_expanding"] = bool(base_tr > 0 and self.tr[j - 5:j + 1].mean() >= 1.3 * base_tr)
        else:
            F["atr_expanding"] = False
        F["nr4_prev"] = D.get("nr4")
        prc = D.get("prth_close")
        if rth_open is not None and prc is not None:
            gap = rth_open - prc
            F["gap_big"] = bool(abs(gap) >= 0.25 * adr)
            F["gap_with"] = bool(gap * d >= 0.1 * adr)
            F["gap_against"] = bool(-gap * d >= 0.1 * adr)
            F["gap_x"] = round(gap / adr, 3)

        # ---- intermarket
        if es is not None:
            je = int(np.searchsorted(es.t, entry_t - 300, side="right")) - 1
            ke = es.day_ix.get(day)
            if je > 100 and ke is not None and es.di[je] == ke and abs(int(es.t[je]) - int(t[j])) <= 600:
                De = es.D[ke]
                ref_n, ref_e = D["open18"], De["open18"]
                if rth_open is not None and De.get("rth") and De["rth"]["start_t"] <= entry_t:
                    ref_n, ref_e = rth_open, De["rth"]["open"]
                rn = (c[j] - ref_n) / ref_n
                re_ = (es.c[je] - ref_e) / ref_e
                F["nq_rs_with"] = bool((rn - re_) * d > 0)
                F["es_vwap_with"] = bool((es.c[je] - es.vw_e[je]) * d > 0)
                F["es_trend_with"] = bool((es.c[je] - De["open18"]) * d > 0)
                # 4h reference vs last 30 min, same clock windows on both
                t_ref0, t_sw0 = int(t[max(0, j - 47)]), int(t[j - 5])
                i_r0 = int(np.searchsorted(es.t, t_ref0))
                i_s0 = int(np.searchsorted(es.t, t_sw0))
                if i_s0 - i_r0 >= 20 and je - i_s0 >= 3:
                    if d == 1:
                        sw_n = l[j - 5:j + 1].min() < l[max(0, j - 47):j - 5].min()
                        sw_e = es.l[i_s0:je + 1].min() < es.l[i_r0:i_s0].min()
                    else:
                        sw_n = h[j - 5:j + 1].max() > h[max(0, j - 47):j - 5].max()
                        sw_e = es.h[i_s0:je + 1].max() > es.h[i_r0:i_s0].max()
                    F["smt_es"] = bool(sw_n != sw_e)
                    F["es_confirms"] = bool(sw_n and sw_e)
        return F


def _ctx_for(b):
    key = (len(b), int(b["time"].iloc[0]), int(b["time"].iloc[-1]), float(b["close"].iloc[-1]))
    cx = _CTX.get(key)
    if cx is None:
        cx = _CTX[key] = Ctx(b)
    return cx


def features(bars5, entry_t, d, es5=None, entry_px=None):
    """Named confluence values for a trade entered at entry_t in direction d (see module docstring)."""
    cx = _ctx_for(bars5)
    ex = _ctx_for(es5) if es5 is not None and len(es5) else None
    return cx.feat(entry_t, d, ex, entry_px)


# ================================================================================================ test harness
SEG26 = {"ytd": ("2026-01-02", "2026-10-16"), "H1": ("2026-01-02", "2026-06-30"), "H2": ("2026-07-01", "2026-10-16"),
         "JanMar": ("2026-01-02", "2026-03-31"), "AprJul": ("2026-04-01", "2026-07-31"), "AugOct": ("2026-08-01", "2026-10-16")}
SEG25 = {"y2025": ("2025-04-14", "2025-12-31"), "H1": ("2025-04-14", "2025-08-31"), "H2": ("2025-09-01", "2025-12-31")}
ORIG1D_PARAMS = {"grade_sizing": False, "conviction_step": 0, "max_trades_day": 1}
BED_ORIG1D = os.path.join(LAB, "conf_testbed_orig1day.json")
BED_ENGINE = os.path.join(LAB, "conf_testbed_engine.json")
BED_MODELS = os.path.join(LAB, "conf_testbed_models.json")
OUT_MD = os.path.join(LAB, "CONFLUENCE_RESULTS.md")
OUT_JSON = os.path.join(LAB, "confluence_results.json")
_FRAMES = {}


def _truthy(v):
    return v is not None and bool(v)


def frames():
    if not _FRAMES:
        from tools.strategy_lab import bars as lab_bars
        _FRAMES["nq"] = lab_bars("NQ", "5m", "2024-12-01", "2026-10-16")
        _FRAMES["es"] = lab_bars("ES", "5m", "2025-04-01", "2026-10-16")
    return _FRAMES["nq"], _FRAMES["es"]


def annotate(trades):
    b, es = frames()
    for t in trades:
        if "_f" not in t:
            t["_f"] = features(b, t["entry_t"], t["dir"], es, t.get("entry"))
    return trades


def rules_for(trades, names=None):
    """keep-masks: 'X' = keep only trades with confluence X, 'not X' = veto X."""
    names = names or BOOL
    out = {}
    for f in names:
        m = np.array([_truthy(t["_f"].get(f)) for t in trades], bool)
        out[f] = m
        out["not " + f] = ~m
    return out


def seg_stats(trades, mask, a, z):
    pn = np.array([t["pnl"] for t, k in zip(trades, mask) if k and a <= t["day"] <= z], float)
    rr = np.array([t["r"] for t, k in zip(trades, mask) if k and a <= t["day"] <= z], float)
    n = len(pn)
    gp, gl = float(pn[pn > 0].sum()), float(-pn[pn < 0].sum())
    return {"n": n, "net": round(float(pn.sum()), 0), "pf": (round(gp / gl, 2) if gl > 0 else (99.0 if gp > 0 else None)),
            "avg_r": round(float(rr.mean()), 3) if n else None, "win": round(float((pn > 0).mean() * 100), 1) if n else None}


def rebuild_days(trades, mask, days):
    full = collections.Counter(t["day"] for t in trades)
    kp = collections.defaultdict(list)
    for t, k in zip(trades, mask):
        if k:
            kp[t["day"]].append(t)
    out = []
    for d in days:
        ks = kp.get(d["date"], [])
        if not ks:
            out.append({"date": d["date"], "pnl": 0.0, "low": 0.0, "trades": 0})
        elif len(ks) == full[d["date"]]:
            out.append({"date": d["date"], "pnl": float(d["pnl"]), "low": float(d["low"]), "trades": len(ks)})
        else:
            p = float(sum(t["pnl"] for t in ks))
            out.append({"date": d["date"], "pnl": p, "low": min(0.0, p), "trades": len(ks)})
    return out


def full_stats(trades, mask, days, a, z):
    from tools.strategy_lab import stats as lab_stats
    kept = [t for t, k in zip(trades, mask) if k]
    s = lab_stats(kept, a, z, given_days=rebuild_days(trades, mask, days))
    return {k: s[k] for k in ("trades", "tpw", "win_rate", "avg_r", "ci95_r", "pf", "net", "max_dd", "worst_day",
                              "losing_months", "rolling_pass", "zero_edge_pass", "b2b_pass", "b2b_fail", "weeks_in_2_5")} | \
        {"months": {m: v["net"] for m, v in s["months"].items()}}


def gate_emulate(cand, rule_fn, a, z):
    """Filter used as an entry gate on the max-2/day candidate list: the first kept trade of each day is taken."""
    seen, kept = set(), []
    for t in sorted(cand, key=lambda t: t["entry_t"]):
        if not (a <= t["day"] <= z) or t["day"] in seen:
            continue
        if rule_fn(t):
            kept.append(t)
            seen.add(t["day"])
    pn = np.array([t["pnl"] for t in kept], float)
    gp, gl = float(pn[pn > 0].sum()), float(-pn[pn < 0].sum())
    return {"n": len(kept), "net": round(float(pn.sum()), 0), "pf": round(gp / gl, 2) if gl > 0 else None}


def _rule_fn(rule):
    parts = [p.strip() for p in rule.split(" & ")]

    def fn(t):
        for p in parts:
            neg = p.startswith("not ")
            v = _truthy(t["_f"].get(p[4:] if neg else p))
            if v == neg:
                return False
        return True
    return fn


def _weeks(a, z, days):
    return max(1e-9, sum(1 for d in days if a <= d["date"] <= z) / 5.0)


def priority(n_placebo=200, top=15):
    """Leading candidate (engine, max 1 trade/day): which confluences, alone or in pairs, skip the Apr-Jul losers,
    keep the Aug-Oct winners and still leave >= 2 trades/week? Holdout check on 2025-04-14..2025-12-31."""
    t0 = time.time()
    bed = json.load(open(BED_ORIG1D, encoding="utf-8"))
    T26, D26 = annotate(bed["ytd"]["trades"]), bed["ytd"]["days"]
    T25, D25 = annotate(bed["y2025"]["trades"]), bed["y2025"]["days"]
    cand = json.load(open(BED_ENGINE, encoding="utf-8"))
    C26 = annotate(cand["ytd"]["trades"])
    C25 = annotate([t for t in cand["y2025"]["trades"] if t["day"] >= SEG25["y2025"][0]])
    weeks26, weeks25 = _weeks(*SEG26["ytd"], D26), _weeks(*SEG25["y2025"], D25)
    min_n = int(np.ceil(2.0 * weeks26))
    print(f"orig1day: 2026 {len(T26)} trades ({len(T26) / weeks26:.2f}/wk), 2025 {len(T25)}; keep >= {min_n} for 2/wk", flush=True)
    R26, R25 = rules_for(T26), rules_for(T25)
    base_mask26, base_mask25 = np.ones(len(T26), bool), np.ones(len(T25), bool)
    base = {"seg": {s: seg_stats(T26, base_mask26, *SEG26[s]) for s in SEG26},
            "seg25": {s: seg_stats(T25, base_mask25, *SEG25[s]) for s in SEG25},
            "ytd": full_stats(T26, base_mask26, D26, *SEG26["ytd"]),
            "y2025": full_stats(T25, base_mask25, D25, *SEG25["y2025"])}
    pnl26 = np.array([t["pnl"] for t in T26])
    seg_ix = {s: np.array([SEG26[s][0] <= t["day"] <= SEG26[s][1] for t in T26]) for s in SEG26}
    pnl25 = np.array([t["pnl"] for t in T25])
    b_aug, b_aprjul, b_ytd = base["seg"]["AugOct"]["net"], base["seg"]["AprJul"]["net"], base["seg"]["ytd"]["net"]
    keep_aug = 0.9 * b_aug

    def score_masks(M):                    # M: (r, n) bool -> objective pieces, vectorised
        cnt = M.sum(1)
        aug = M[:, seg_ix["AugOct"]] @ pnl26[seg_ix["AugOct"]]
        apr = M[:, seg_ix["AprJul"]] @ pnl26[seg_ix["AprJul"]]
        tot = M @ pnl26
        ok = (cnt >= min_n) & (aug >= keep_aug) & (cnt < len(T26))
        return cnt, aug, apr, tot, ok

    names = list(R26)
    K26 = np.array([R26[r] for r in names])
    K25 = np.array([R25[r] for r in names])
    # ---- single rules
    rows = []
    cnt, aug, apr, tot, ok = score_masks(K26)
    for i, r in enumerate(names):
        rows.append({"rule": r, "n": int(cnt[i]), "tpw": round(cnt[i] / weeks26, 2), "d_aprjul": round(float(apr[i] - b_aprjul), 0),
                     "aug_keep": round(float(aug[i] / b_aug), 2) if b_aug else None, "d_ytd": round(float(tot[i] - b_ytd), 0),
                     "ok": bool(ok[i]), "d_2025": round(float(K25[i] @ pnl25 - pnl25.sum()), 0),
                     "n25": int(K25[i].sum())})
    # ---- pairs (AND of two keep-rules, never a rule with its own negation)
    pair_rows = []
    nr = len(names)
    for i in range(nr):
        M = K26[i] & K26[i + 1:]
        c2, a2, p2, t2, ok2 = score_masks(M)
        M25 = K25[i] & K25[i + 1:]
        d25 = M25 @ pnl25 - pnl25.sum()
        for jj in np.flatnonzero(ok2):
            j = i + 1 + jj
            if names[j] == "not " + names[i] or names[i] == "not " + names[j]:
                continue
            if (M[jj] == K26[i]).all() or (M[jj] == K26[j]).all():
                continue                       # one side is a no-op on this bed: that is a single rule, not a pair
            pair_rows.append({"rule": names[i] + " & " + names[j], "n": int(c2[jj]), "tpw": round(c2[jj] / weeks26, 2),
                              "d_aprjul": round(float(p2[jj] - b_aprjul), 0), "aug_keep": round(float(a2[jj] / b_aug), 2),
                              "d_ytd": round(float(t2[jj] - b_ytd), 0), "ok": True, "d_2025": round(float(d25[jj]), 0),
                              "n25": int(M25[jj].sum())})
    singles_ok = sorted([r for r in rows if r["ok"]], key=lambda r: -r["d_ytd"])
    pairs_ok = sorted(pair_rows, key=lambda r: -r["d_ytd"])
    print(f"singles ok {len(singles_ok)} / {len(rows)}; pairs ok {len(pairs_ok)}  ({time.time() - t0:.0f}s)", flush=True)

    # ---- placebo: permute every feature column across trades, rerun the same search, record the best d_ytd
    rng = np.random.default_rng(20261016)
    feat_cols = np.array([[_truthy(t["_f"].get(f)) for t in T26] for f in BOOL])
    best_single, best_pair = [], []
    for rep in range(n_placebo):
        P = np.array([rng.permutation(col) for col in feat_cols])
        KP = np.concatenate([P, ~P])
        c1, a1, p1, t1, ok1 = score_masks(KP)
        best_single.append(float((t1[ok1] - b_ytd).max()) if ok1.any() else 0.0)
        bp = -1e18
        for i in range(len(KP)):
            c2, a2, p2, t2, ok2 = score_masks(KP[i] & KP[i + 1:])
            if ok2.any():
                bp = max(bp, float((t2[ok2] - b_ytd).max()))
        best_pair.append(bp if bp > -1e17 else 0.0)
    placebo = {"reps": n_placebo, "best_single_d_ytd": {"p50": round(float(np.percentile(best_single, 50)), 0),
                                                        "p90": round(float(np.percentile(best_single, 90)), 0),
                                                        "p95": round(float(np.percentile(best_single, 95)), 0)},
               "best_pair_d_ytd": {"p50": round(float(np.percentile(best_pair, 50)), 0),
                                   "p90": round(float(np.percentile(best_pair, 90)), 0),
                                   "p95": round(float(np.percentile(best_pair, 95)), 0)}}
    real_bs = singles_ok[0]["d_ytd"] if singles_ok else 0.0
    real_bp = pairs_ok[0]["d_ytd"] if pairs_ok else 0.0
    placebo["p_single"] = round(float(np.mean(np.array(best_single) >= real_bs)), 3)
    placebo["p_pair"] = round(float(np.mean(np.array(best_pair) >= real_bp)), 3)
    print("placebo", placebo, f"({time.time() - t0:.0f}s)", flush=True)

    # ---- detail for the top candidates (full scorecards, months, 2025 holdout, gate emulation)
    def detail(rule):
        fn = _rule_fn(rule)
        m26 = np.array([fn(t) for t in T26], bool)
        m25 = np.array([fn(t) for t in T25], bool)
        return {"rule": rule, "seg": {s: seg_stats(T26, m26, *SEG26[s]) for s in SEG26},
                "seg25": {s: seg_stats(T25, m25, *SEG25[s]) for s in SEG25},
                "ytd": full_stats(T26, m26, D26, *SEG26["ytd"]), "y2025": full_stats(T25, m25, D25, *SEG25["y2025"]),
                "gate26": gate_emulate(C26, fn, *SEG26["ytd"]), "gate25": gate_emulate(C25, fn, *SEG25["y2025"]),
                "dropped": [{"day": t["day"], "dir": t["dir"], "pnl": t["pnl"], "r": t["r"]} for t, k in zip(T26, m26) if not k]}
    det_single = [detail(r["rule"]) for r in singles_ok[:top]]
    det_pair = [detail(r["rule"]) for r in pairs_ok[:top]]
    base["gate26"] = gate_emulate(C26, lambda t: True, *SEG26["ytd"])
    base["gate25"] = gate_emulate(C25, lambda t: True, *SEG25["y2025"])
    # robust picks: pass in 2026 AND do not hurt 2025 (holdout)
    robust_s = [r for r in singles_ok if r["d_2025"] >= 0][:top]
    robust_p = [r for r in pairs_ok if r["d_2025"] >= 0][:top]
    det_rs = [detail(r["rule"]) for r in robust_s[:8]]
    det_rp = [detail(r["rule"]) for r in robust_p[:8]]
    # oracle bound: the best any filter could do while keeping >= 2/wk = drop the (n - min_n) worst trades
    worst = sorted(T26, key=lambda t: t["pnl"])[:max(0, len(T26) - min_n)]
    worst_aj = sorted([t for t in T26 if SEG26["AprJul"][0] <= t["day"] <= SEG26["AprJul"][1]], key=lambda t: t["pnl"])
    oracle = {"drop_n": len(worst), "d_ytd": round(-sum(t["pnl"] for t in worst), 0),
              "aprjul_best_possible": round(b_aprjul - sum(t["pnl"] for t in worst_aj[:len(worst)]), 0),
              "aprjul_trades": len(worst_aj), "aprjul_losers": sum(1 for t in worst_aj if t["pnl"] <= 0)}
    # full scorecards (losing months, 50K pass) for every single rule that keeps >= 1.5/wk
    full_single = {}
    for r in rows:
        if r["n"] >= 1.5 * weeks26 and r["n"] < len(T26):
            m26, m25 = R26[r["rule"]], R25[r["rule"]]
            full_single[r["rule"]] = {"ytd": full_stats(T26, m26, D26, *SEG26["ytd"]),
                                      "y2025": full_stats(T25, m25, D25, *SEG25["y2025"]),
                                      "seg": {s: seg_stats(T26, m26, *SEG26[s]) for s in SEG26},
                                      "seg25": {s: seg_stats(T25, m25, *SEG25[s]) for s in SEG25}}
    print(f"full single scorecards {len(full_single)} ({time.time() - t0:.0f}s)", flush=True)
    res = {"generated": time.strftime("%Y-%m-%d %H:%M"), "params": ORIG1D_PARAMS, "min_kept_2026": min_n,
           "oracle": oracle, "full_single": full_single,
           "weeks26": weeks26, "weeks25": weeks25, "base": base, "n_rules": len(names), "n_pairs_ok": len(pairs_ok),
           "singles": rows, "pairs_top": pairs_ok[:200], "placebo": placebo, "detail_single": det_single,
           "detail_pair": det_pair, "detail_robust_single": det_rs, "detail_robust_pair": det_rp,
           "freq26": {f: round(float(np.mean([_truthy(t["_f"].get(f)) for t in T26])), 3) for f in BOOL},
           "freq25": {f: round(float(np.mean([_truthy(t["_f"].get(f)) for t in T25])), 3) for f in BOOL}}
    print(f"priority done ({time.time() - t0:.0f}s)", flush=True)
    return res


# ================================================================================================ report writers
VERDICT_PRIORITY = """
### Verdict (plain English)

1. **No confluence skips the Apr-Jul losers at 2 trades a week.** The candidate trades 2.26/wk, so the 2.0/wk floor
   lets a filter drop at most 10 of 93 trades, while Apr-Jul holds 35 trades with 32 losers. Even a perfect hindsight
   filter could only lift Apr-Jul from -2,889 to about -550. The real filters move it by 0 to +880.
2. **The best feasible combination is `not fomc_day & not atr_expanding`.** It skips FOMC days, and it skips entries
   where the last 30 minutes ran at 1.3x or more their 10-day same-time true range. The effects:
   - 2026: 83 trades (2.01/wk), +1,420.
   - Jan-Jun: +592 becomes +2,521. Apr-Jul: -2,889 becomes -2,010. Aug-Oct keeps 95%.
   - 50K pass: 63.5% (zero-edge 22.3%) against 48.1% (zero-edge 27.0%).
   - 2025 holdout: +1,361 becomes +1,876 (PF 1.14 to 1.22).
   - Losing months stay at 5. April and May are untouched. The gain comes from 4 January losers (-1,057) and
     3 June losers (-869). It also drops one +519 August winner.
3. **That gain is the size luck gives.** Columns of shuffled random features, searched the same way, find a pair at
   least this good 28% of the time, and a single filter at least as good as the best real one 48% of the time. Effects
   this small cannot be told apart from noise: about +$1k from skipping 10 trades.
4. **Mechanical reasons, for what they are worth:**
   - Skipping FOMC days is a standard risk rule rather than an edge. It removes 2 trades in 2026 and 5 in 2025, both
     years improve, and the cost is tiny.
   - Skipping volatility expansion has a plausible story: sweeps into expanding range tend to continue rather than
     reverse. It holds in 2025 (+358).
   - `not fvg_1h_leg` (veto a fresh displacement FVG) has no sound story, since it is the opposite of the ICT claim.
     Treat it as noise.
5. **If the floor were relaxed to about 1.6-1.9/wk,** three filters each do the following: `asia_small` (Asia range <=
   40% ADR), `adr_room` (at least half an ADR left in the trade's direction) and `not open_in_value` (skip days that
   open inside prior value).
   - They trim Apr-Jul by +1.0k to +1.3k.
   - They also trim the 2025 Sep-Dec losing stretch (+284 to +880) and raise the 2025 total.
   - But they give up 14-22% of Aug-Oct.

   They break the owner's frequency rule, and they were found by searching these same 10 months.
6. **Recommendation:** no confluence gate for Monday. If one rule is wanted, add "no new entries on FOMC days" as a
   risk rule and log `atr_expanding` for paper evidence. The Apr-Jul drawdown looks like regime, not a missing
   confluence. None of the 92 confluences separates those months' losers from the Aug-Oct winners.
"""      # written by hand after reading the numbers below (kept in code so a re-run keeps it)


TOPLINE = """
## 0. Bottom line (first full pass, 16 Oct 2026)

**Scope.** 92 causal confluence booleans (46 popular concepts; see `CONFLUENCE_CATALOG.md`) were tested on 14 trade
beds, all real NQ futures:
- the leading candidate (engine `max_trades_day: 1`): 2026 YTD (93 trades) and a 2025-04-14..12-31 holdout (118);
- the engine at max 2/day: 2026 (106) and 2025 (183);
- the five lab models with their default params on NQ, in 2026 and in 2025-04-14..12-31:
  - silver_bullet: 94 and 92 trades;
  - ict2022: 54 and 43;
  - mech_ifvg: 80 and 77;
  - continuation: 20 and 11;
  - session_po3: 16 and 41.

**1. Nothing survives a multiple-testing check.**
- *Per bed:* the number of HELPS\\*/HURTS\\* labels is about what random features produce (17 HELPS\\* against about 30
  expected by chance; 39 HURTS\\* against about 28).
- *Pooled over 8 roughly independent bed families:* the strongest confluence reaches |z| = 2.66. Under shuffled
  outcomes the largest |z| among 92 confluences is 2.70 at the median, and the 95% family-wise line is |z| >= 3.77.
- *On the leading candidate:* the best filter or pair at >= 2/wk is matched by random-feature searches 28-48% of the
  time.

**2. Top 5 that helped**, ranked by pooled z: the with-minus-without avg R, averaged over the 8 families. None is
significant after correction.

| # | confluence | pooled diff | z | families with that sign | detail |
|---|---|---:|---:|---|---|
| 1 | `trend_1h_with` (1H break-of-structure trend in the trade's direction) | +0.30R | 2.66 (nominal p ~ 0.01) | 5 of 8 | HELPS\\* on silver_bullet 2026 (+0.69R) and mech_ifvg 2025 (+1.09R). On the leading candidate: +0.17R but flips sign (dev -0.56, confirm +1.03), and it keeps only 0.97/wk. |
| 2 | `trend_5m_with` (last 5m BOS in the trade's direction) | +0.21R | 1.51 | 4 of 6 | HELPS\\* on both 2025 engine beds (+0.54R, +0.42R). -0.14R on the 2026 candidate. |
| 3 | `nq_rs_with` (NQ stronger than ES since the open: long the stronger index) | +0.17R | 1.40 | 6 of 8 | +0.40R on the 2026 candidate (dev -0.09, confirm +1.53). |
| 4 | `gap_big` (RTH gap >= 0.25 ADR) | +0.12R | 1.12 | 4 of 8 | HELPS\\* on silver_bullet 2025 (+0.84R). |
| 5 | `trend_day_with` (>= 0.4 ADR above the 18:00 open and in the top quarter of the day) | +0.20R | 1.06 | 3 of 5 | +0.41R on the 2026 candidate, on 12 trades. |

The common thread is that with-trend entries do a little better. Every one of these also cuts frequency well below
2/wk on every bed.

Per-bed strict HELPS (passing the 2/wk rule) occurred only on 2025 engine beds:
- `adr_room` on the max-1/day 2025 bed: +0.38R, CI [+0.03, +0.73], keeps 2.69/wk.
- `asia_small` (+0.57R) and `ifvg_5m` (+0.56R) on the max-2/day 2025 bed.

Each one is negative on at least one other bed: `adr_room` -0.51R on silver_bullet 2026, `asia_small` -1.06R on
ict2022 2026, `ifvg_5m` -0.86R on silver_bullet 2026.

**3. Clear HURTS: none after correction.**

The most consistent negatives are all nominally p < 0.05 pooled and negative in 6 of 8 families:
- `liq_void_draw`: -0.30R, z -2.39. An unfilled bearish void sits above a long entry, so the long comes right after a
  crash candle.
- `below_rth_open`: -0.25R, z -2.27. This tests ICT's "buy below the open" without the daily-bias condition, and it
  comes out backwards.
- `below_tso`: -0.26R, z -2.25. Below the Quarterly-Theory true session open.

Per-bed strict HURTS, where vetoing still leaves 2/wk:
- `news_day` / `cpi_nfp_day` on both 2025 engine beds: -0.57R and -0.75R / -0.66R. Thin in 2026.
- `in_ob_5m` (entry inside a 5m order block) on both 2025 engine beds: -0.41R and -0.49R.
- `fvg_1h_leg` and `dow_wed` on the 2026 max-2/day engine bed.

**4. The leading candidate (section 1).** No confluence skips the Apr-Jul losers at 2 trades/week. The arithmetic
forbids it: at most 10 of 93 trades can go. The best feasible pair is `not fomc_day & not atr_expanding`:
- 2026: +1,420, 50K pass 63.5% (zero-edge 22.3%) against 48.1% (27.0%);
- 2025 holdout: +515;
- but it is within luck (p = 28%).

Recommendation: keep the engine as is. Optionally add "no entries on FOMC days" as a risk rule, not as an edge.
"""


def _m(x, nd=0):
    if x is None:
        return "-"
    return f"{x:+,.{nd}f}" if isinstance(x, (int, float, np.floating)) else str(x)


def _pf(x):
    return "-" if x is None else f"{x:.2f}"


def _row_single(name, seg, ytd, y25, seg25=None, gate=None, weeks26=None):
    g = f"{_m(gate['net'])} ({gate['n']})" if gate else "-"
    return (f"| {name} | {ytd['tpw']:.2f} | {_m(seg['H1']['net'])} ({_pf(seg['H1']['pf'])}) | "
            f"{_m(seg['H2']['net'])} ({_pf(seg['H2']['pf'])}) | {_m(seg['AprJul']['net'])} | {_m(seg['AugOct']['net'])} | "
            f"{ytd['losing_months']} | {ytd['rolling_pass']} ({ytd['zero_edge_pass']}) | "
            f"{_m(y25['net'])} ({_pf(y25['pf'])}), {y25['tpw']:.2f}/wk | {g} |")


HDR_SINGLE = ("| keep only trades where | kept /wk | Jan-Jun net (PF) | Jul-Oct net (PF) | Apr-Jul net | Aug-Oct net | "
              "losing months | 50K pass % (zero-edge) | 2025 holdout net (PF), /wk | gate-emulated 2026 net (n) |\n"
              "|---|---:|---|---|---:|---:|---:|---|---|---|")


def priority_md(res):
    b = res["base"]
    L = ["## 1. Leading candidate first: Liquidity Engine, `max_trades_day: 1` (priority from the lead)", "",
         f"Test bed: `engine_trades({json.dumps(res['params'])}, 2026-01-02, 2026-10-16)` live-loop replay, cached in "
         "`research/lab/conf_testbed_orig1day.json` (93 trades), plus the same params on 2025-04-14..2025-12-31 as a "
         "holdout (118 trades). Filters are applied to the finished trade list: a skipped trade is simply gone "
         "(the 'gate-emulated' column instead replays the filter as an entry gate on the max-2/day list, so a vetoed "
         "first setup can be replaced by that day's second one). Day P&L and intraday lows are rebuilt from the "
         "engine's own day list, and pass rates come from `strategy_lab.stats` (rolling MFFU 50K; zero-edge baseline in "
         "brackets). No confirm-log entries were written (`score()` was not called).", ""]
    if VERDICT_PRIORITY:
        L += [VERDICT_PRIORITY.strip(), ""]
    o = res["oracle"]
    L += ["### The arithmetic first", "",
          f"- Base 2026: {b['ytd']['trades']} trades, {b['ytd']['tpw']}/wk, PF {b['ytd']['pf']}, net {_m(b['ytd']['net'])}, "
          f"{b['ytd']['losing_months']} losing months, 50K pass {b['ytd']['rolling_pass']}% (zero-edge {b['ytd']['zero_edge_pass']}%).",
          f"- Apr-Jul: {b['seg']['AprJul']['n']} trades, net {_m(b['seg']['AprJul']['net'])}, PF {_pf(b['seg']['AprJul']['pf'])}, "
          f"win {b['seg']['AprJul']['win']}%. Aug-Oct: {b['seg']['AugOct']['n']} trades, net {_m(b['seg']['AugOct']['net'])}, "
          f"PF {_pf(b['seg']['AugOct']['pf'])}.",
          f"- **2.0 trades/week over 2026 means keeping at least {res['min_kept_2026']} of {b['ytd']['trades']} trades: a filter "
          f"may drop at most {o['drop_n']}.** Apr-Jul alone has {o['aprjul_trades']} trades ({o['aprjul_losers']} losers). "
          f"Even a perfect hindsight filter that drops the {o['drop_n']} worst Apr-Jul trades leaves Apr-Jul at "
          f"{_m(o['aprjul_best_possible'])}; dropping the {o['drop_n']} worst trades of the whole year adds at most "
          f"{_m(o['d_ytd'])}. So no confluence can 'skip the Apr-Jul losers' at 2/wk; the most any filter can do is trim "
          "the worst of them.",
          f"- 2025 holdout base: {b['y2025']['trades']} trades, {b['y2025']['tpw']}/wk, PF {b['y2025']['pf']}, net "
          f"{_m(b['y2025']['net'])}, 50K pass {b['y2025']['rolling_pass']}% (zero-edge {b['y2025']['zero_edge_pass']}%).", ""]
    # feasible singles
    feas = [r for r in res["singles"] if r["ok"]]
    feas.sort(key=lambda r: -r["d_ytd"])
    L += ["### Single confluences that keep >= 2.0/wk and >= 90% of the Aug-Oct net", "",
          f"{len(feas)} of {res['n_rules']} single filters (each confluence as 'require it' and as 'veto it') pass the "
          "frequency floor and keep the Aug-Oct winners. Sorted by the 2026 net change.", "", HDR_SINGLE,
          _row_single("**all trades (base)**", b["seg"], b["ytd"], b["y2025"], gate=b["gate26"])]
    fs = res["full_single"]
    gates = {d["rule"]: d["gate26"] for d in res["detail_single"] + res["detail_robust_single"]}
    for r in feas:
        x = fs.get(r["rule"])
        if x:
            L.append(_row_single(f"`{r['rule']}`", x["seg"], x["ytd"], x["y2025"], gate=gates.get(r["rule"])))
    # near misses
    near = []
    for rule, x in fs.items():
        rr = next(r for r in res["singles"] if r["rule"] == rule)
        if not rr["ok"] and x["ytd"]["tpw"] >= 1.5 and x["seg"]["H1"]["net"] > b["seg"]["H1"]["net"] and \
                x["seg"]["AugOct"]["net"] >= 0.9 * b["seg"]["AugOct"]["net"]:
            near.append((x["ytd"]["net"] - b["ytd"]["net"], rule, x))
    near.sort(key=lambda z: -z[0])
    L += ["", "### Near misses: better Jan-Jun, Aug-Oct kept, but under 2.0/wk (1.5-2.0/wk)", "",
          "Shown because a looser floor or a second setup type could restore frequency; they fail the brief as is.", "",
          HDR_SINGLE]
    for _, rule, x in near[:12]:
        L.append(_row_single(f"`{rule}`", x["seg"], x["ytd"], x["y2025"]))
    # what it would take: best Apr-Jul improvers at any frequency (>= 1.5/wk), with the 2025 analogue
    bj = b["seg"]["AprJul"]["net"]
    cand = []
    for rule, x in fs.items():
        if x["seg"]["AugOct"]["net"] >= 0.75 * b["seg"]["AugOct"]["net"]:
            cand.append((x["seg"]["AprJul"]["net"] - bj, rule, x))
    cand.sort(key=lambda z: -z[0])
    L += ["", "### What it would take: the best Apr-Jul improvers at any frequency >= 1.5/wk (Aug-Oct kept >= 75%)", "",
          "2025 Sep-Dec was the holdout's own losing stretch (base net "
          f"{_m(b['seg25']['H2']['net'])}), so the last two columns ask whether the same filter also trimmed that one.", "",
          "| keep only trades where | kept /wk | Apr-Jul change | Aug-Oct kept | Jan-Mar net (base " + _m(b["seg"]["JanMar"]["net"]) +
          ") | 2025 Sep-Dec change | 2025 total change |", "|---|---:|---:|---:|---:|---:|---:|"]
    for dj, rule, x in cand[:12]:
        L.append(f"| `{rule}` | {x['ytd']['tpw']:.2f} | {_m(dj)} | {x['seg']['AugOct']['net'] / b['seg']['AugOct']['net']:.0%} | "
                 f"{_m(x['seg']['JanMar']['net'])} | {_m(x['seg25']['H2']['net'] - b['seg25']['H2']['net'])} | "
                 f"{_m(x['y2025']['net'] - b['y2025']['net'])} |")
    # pairs
    L += ["", "### Pairs (two filters ANDed), feasible at >= 2.0/wk and >= 90% of Aug-Oct", "",
          f"{res['n_pairs_ok']} feasible pairs. Top by 2026 net change, then the best ones that also do not lower the 2025 net.", "",
          HDR_SINGLE]
    for d in res["detail_pair"][:10]:
        L.append(_row_single(f"`{d['rule']}`", d["seg"], d["ytd"], d["y2025"], gate=d["gate26"]))
    L += ["", "Pairs that also do not lower the 2025 holdout net:", "", HDR_SINGLE]
    for d in res["detail_robust_pair"][:8]:
        L.append(_row_single(f"`{d['rule']}`", d["seg"], d["ytd"], d["y2025"], gate=d["gate26"]))
    p = res["placebo"]
    L += ["", "### Is the best filter better than luck? (placebo search)", "",
          f"Every confluence column was randomly permuted across the 93 trades ({p['reps']} times; same frequencies, no "
          "information) and the same search was rerun under the same constraints.", "",
          "| search | best real 2026 net change | best random: median | 90th pct | 95th pct | share of random searches that beat the real best |",
          "|---|---:|---:|---:|---:|---:|",
          f"| single filter | {_m(feas[0]['d_ytd'] if feas else 0)} | {_m(p['best_single_d_ytd']['p50'])} | "
          f"{_m(p['best_single_d_ytd']['p90'])} | {_m(p['best_single_d_ytd']['p95'])} | {p['p_single']:.0%} |",
          f"| pair of filters | {_m(res['pairs_top'][0]['d_ytd'] if res['pairs_top'] else 0)} | {_m(p['best_pair_d_ytd']['p50'])} | "
          f"{_m(p['best_pair_d_ytd']['p90'])} | {_m(p['best_pair_d_ytd']['p95'])} | {p['p_pair']:.0%} |", ""]
    la = res.get("lookahead")
    if la:
        L += [f"**No-lookahead check** (`python -X utf8 tools/lab_confluences.py lookahead 120`). Every confluence was "
              f"recomputed on bars cut off at the entry, with the same start, for {la['checked']} random trades from the "
              f"engine and model beds. There were {la['mismatches']} mismatches. {la['unexplained']} of them have no "
              "explanation; the rest are entries at exactly 09:30, where the full-data run can read the 09:30 bar's open, "
              "which prints at entry_t. Session windows (IB, OR, Asia, London, CBDR) count as finished only once the clock "
              "passes their end, so `features()` is safe to call live on a frame that ends at the last closed bar.", ""]
    return "\n".join(L)


def write_results(pri=None, beds=None):
    old = {}
    if os.path.exists(OUT_JSON):
        try:
            old = json.load(open(OUT_JSON, encoding="utf-8"))
        except Exception:
            old = {}
    if pri is not None:
        old["priority"] = pri
    if beds is not None:
        old["beds"] = beds
    old["generated"] = time.strftime("%Y-%m-%d %H:%M")
    old["features"] = {k: {"group": g, "definition": dfn} for k, (g, dfn) in FEATURES.items()}
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(old, fh, indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x))
    L = ["# Confluence results (CONFLUENCE track, real CME NQ1! / ES1! 5m only)", "",
         f"Generated {old['generated']} by `python -X utf8 tools/lab_confluences.py all`. Features: `tools/lab_confluences.py` "
         "(`features(bars5, entry_t, d, es5)`, causal). Catalog and sources: `research/lab/CONFLUENCE_CATALOG.md`. "
         "Machine-readable: `research/lab/confluence_results.json`.", ""]
    if old.get("priority") and old.get("beds"):
        L.append(TOPLINE.strip() + "\n")
    if old.get("priority"):
        L.append(priority_md(old["priority"]))
    if old.get("beds"):
        L.append(beds_md(old["beds"]))
    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print("wrote", OUT_MD, OUT_JSON, flush=True)


def _d(x):
    return "-" if x is None else f"{x:+.2f}"


def beds_md(beds):
    names = [b for b in beds if not b.startswith("_")]
    L = ["## 2. Every test bed: with vs without each confluence", "",
         "Each confluence splits a bed's trades into 'with' (feature True) and 'without' (False or not yet defined). "
         "Halves: dev 2026-01-02..06-30 / confirm 07-01..10-16 for the 2026 beds; 2025-04-14..08-31 / 09-01..12-31 for the "
         "max-1/day 2025 holdout and the 2025 model beds; 2025 H1 / H2 for the max-2/day 2025 bed. 'diff' = avg R with "
         "minus avg R without; CI = two-sample bootstrap 95% (2,000 draws). Model beds = `run(bars('NQ','5m',start,end,"
         "warmup_days=30), {'sym': 'NQ'}, es5)` with each module's default params (cached in "
         "`research/lab/conf_testbed_models.json`, keyed by module mtime).", "",
         "Labels (fixed before looking at results):", "",
         "- **HELPS**: diff > 0 in both halves, the kept ('with') set trades >= 2.0/week over the bed, and the full-period "
         "95% CI excludes 0 *or* both halves are clearly positive (diff >= +0.15R and bootstrap P(diff > 0) >= 0.9 in each).",
         "- **HURTS**: the mirror (diff < 0 in both halves, same significance test), and vetoing it still leaves >= 2.0/week.",
         "- **NOISE**: everything else. **THIN**: fewer than 8 trades on either side (or 3 in a half).",
         "- **HELPS\\* / HURTS\\***: the same sign and significance test *without* the 2/week condition (most beds trade "
         "only 1.2-2.6/week, so almost no filter can keep 2/week; the starred label shows the edge alone).", "",
         "### Beds and how many labels luck alone would give", "",
         "Placebo: 300 random features per bed (each trade True with probability 0.1-0.9, no information) put through "
         "the same labels. 'Expected by chance' = placebo rate x the number of confluences tested on that bed.", "",
         "| bed | trades | /wk | avg R (dev / confirm) | tested | HELPS / HURTS | HELPS\\* / HURTS\\* | expected by chance (HELPS\\* / HURTS\\*) |",
         "|---|---:|---:|---|---:|---|---|---|"]
    for b in names:
        x = beds[b]
        c, s = x["counts"]["edge"], x["counts"]["strict"]
        L.append(f"| {x['label']} | {x['n']} | {x['tpw']} | {_d(x['base']['h1']['avg_r'])} / {_d(x['base']['h2']['avg_r'])} | "
                 f"{x['expected_false']['tested']} | {s.get('HELPS', 0)} / {s.get('HURTS', 0)} | {c.get('HELPS', 0)} / {c.get('HURTS', 0)} | "
                 f"{x['expected_false']['helps']} / {x['expected_false']['hurts']} |")
    pl = beds.get("_pooled")
    if pl:
        real = pl["real"]
        pos = sorted([(v["z"], f, v) for f, v in real.items() if v["z"] > 0], reverse=True)[:12]
        neg = sorted([(v["z"], f, v) for f, v in real.items() if v["z"] < 0])[:12]
        L += ["", f"### Pooled over the {len(pl['families'])} roughly independent bed families (multiple-testing aware)", "",
              f"Families: {', '.join(pl['families'])} (the max-2/day engine beds are left out because they contain the "
              "max-1/day trades). Pooled diff = equal-weight mean of the per-family with-minus-without avg R; z = pooled "
              "diff / its standard error. Family-wise threshold: shuffle the trade outcomes inside every family "
              f"{pl['reps']} times, keep the largest |z| over all {len(BOOL)} confluences each time; its 95th percentile is "
              f"**|z| >= {pl['maxz_p95']}** (median {pl['maxz_p50']}). Only a confluence above that line is better than the "
              "best of 92 random tries.", "",
              "| confluence | group | pooled diff (R) | z | families with that sign | nominal p < 0.05 | survives family-wise |",
              "|---|---|---:|---:|---|---|---|"]
        for z, f, v in pos + neg:
            L.append(f"| `{f}` | {FEATURES[f][0]} | {v['mean_diff']:+.3f} | {v['z']:+.2f} | {v['same_sign']} of {v['k']} | "
                     f"{'yes' if v['nominal_sig'] else 'no'} | {'**yes**' if v['familywise_sig'] else 'no'} |")
    cr = beds["_cross"]
    short = {"orig1day_2026": "E1d26", "orig1day_2025": "E1d25", "engine_2026": "E26", "engine_2025": "E25",
             "silver_bullet_2026": "SB26", "ict2022_2026": "M22-26", "mech_ifvg_2026": "MECH26", "continuation_2026": "CONT26",
             "session_po3_2026": "PO3-26", "silver_bullet_2025": "SB25", "ict2022_2025": "M22-25", "mech_ifvg_2025": "MECH25",
             "continuation_2025": "CONT25", "session_po3_2025": "PO3-25"}
    L += ["", "### Cross-bed summary (all confluences)", "",
          "Per bed: the full-period diff in R; a trailing `*` marks HELPS\\*/HURTS\\* on that bed, `!` marks a strict "
          "HELPS/HURTS, `.` = THIN. Sorted by (beds positive - beds negative), then mean diff. Beds overlap (the max-1/day "
          "trades are mostly the first trades of the max-2/day beds, and the four ICT models trade similar sweeps), so "
          "they are not independent votes.", "",
          "| confluence | group | " + " | ".join(short.get(b, b) for b in names) + " | + / - beds | mean diff |",
          "|---|---|" + "---:|" * len(names) + "---|---:|"]

    def cell(v):
        if v["edge"] == "THIN" or v["diff"] is None:
            return "."
        mark = "!" if v["label"] in ("HELPS", "HURTS") else ("*" if v["edge"] in ("HELPS", "HURTS") else "")
        return f"{v['diff']:+.2f}{mark}"
    order = sorted(BOOL, key=lambda f: (-(cr[f]["pos"] - cr[f]["neg"]), -(cr[f]["mean_diff"] or 0)))
    for f in order:
        r = cr[f]
        L.append(f"| `{f}` | {FEATURES[f][0]} | " + " | ".join(cell(r["per"][b]) for b in names) +
                 f" | {r['pos']} / {r['neg']} | {_d(r['mean_diff'])} |")
    L += ["", "### Per-bed detail: the 8 best and 8 worst confluences by full-period diff (non-THIN)", ""]
    for b in names:
        x = beds[b]
        fs = [(f, v) for f, v in x["features"].items() if v["edge_label"] != "THIN" and v["full"]["diff"] is not None]
        fs.sort(key=lambda z: -z[1]["full"]["diff"])
        pick = fs[:8] + [z for z in fs[-8:] if z not in fs[:8]]
        L += [f"#### {x['label']} ({x['n']} trades, {x['tpw']}/wk)", "",
              "| confluence | label | freq | n with (dev/conf) | win % w / wo | avg R w / wo | PF w / wo | diff dev | diff conf | diff full [95% CI] | kept /wk |",
              "|---|---|---:|---|---|---|---|---:|---:|---|---:|"]
        for f, v in pick:
            fu, ci = v["full"], v["full"]["ci"]
            lab = v["label"] if v["label"] != "NOISE" else (v["edge_label"] + "*" if v["edge_label"] != "NOISE" else "NOISE")
            L.append(f"| `{f}` | {lab} | {v['freq']:.0%} | {v['h1']['with']['n']}/{v['h2']['with']['n']} | "
                     f"{fu['with']['win']} / {fu['without']['win']} | {_d(fu['with']['avg_r'])} / {_d(fu['without']['avg_r'])} | "
                     f"{_pf(fu['with']['pf'])} / {_pf(fu['without']['pf'])} | {_d(v['h1']['diff'])} | {_d(v['h2']['diff'])} | "
                     f"{_d(fu['diff'])} [{_d(ci['lo']) if ci else '-'}, {_d(ci['hi']) if ci else '-'}] | {fu['tpw_with']} |")
        L.append("")
    return "\n".join(L)




# ================================================================================================ multi-bed with/without
MODELS = ["silver_bullet", "ict2022", "mech_ifvg", "continuation"]
EXTRA_MODELS = ["session_po3"]
H26 = (("2026-01-02", "2026-06-30"), ("2026-07-01", "2026-10-16"), ("2026-01-02", "2026-10-16"))
H25 = (("2025-04-14", "2025-08-31"), ("2025-09-01", "2025-12-31"), ("2025-04-14", "2025-12-31"))
H25F = (("2025-01-02", "2025-06-30"), ("2025-07-01", "2025-12-31"), ("2025-01-02", "2025-12-31"))


def _sessions_between(a, z):
    b, _ = frames()
    d = b["day"]
    return int(((d >= a) & (d <= z)).groupby(d).any().sum()) if len(b) else 0


def model_beds(refresh=False):
    """Run each lab model on NQ 2026 YTD (params {'sym': 'NQ'}, ES as es5) once; cache keyed by the module's mtime."""
    from tools.strategy_lab import bars as lab_bars
    cache = {}
    if os.path.exists(BED_MODELS):
        try:
            cache = json.load(open(BED_MODELS, encoding="utf-8"))
        except Exception:
            cache = {}
    frames_by = {}
    for name in MODELS + EXTRA_MODELS:
        path = os.path.join(ROOT, "tools", "lab_models", f"{name}.py")
        if not os.path.exists(path):
            continue
        mt = int(os.path.getmtime(path))
        for yr, a, z in (("2026", "2026-01-02", "2026-10-16"), ("2025", "2025-04-14", "2025-12-31")):
            key = name if yr == "2026" else f"{name}@2025"
            if not refresh and cache.get(key, {}).get("mtime") == mt and "trades" in cache[key]:
                continue
            if yr not in frames_by:
                frames_by[yr] = (lab_bars("NQ", "5m", a, z, warmup_days=30), lab_bars("ES", "5m", a, z, warmup_days=30))
            b5, es5 = frames_by[yr]
            t0 = time.time()
            try:
                mod = importlib.import_module(f"tools.lab_models.{name}")
                mod = importlib.reload(mod)
                tr = mod.run(b5, {"sym": "NQ"}, es5)
                tr = [{k: v for k, v in t.items() if k in ("day", "entry_t", "exit_t", "dir", "entry", "stop", "exit", "exit_kind",
                                                              "setup", "qty", "risk_pts", "pnl", "r")}
                      for t in tr if a <= t["day"] <= z and t.get("exit_kind") != "open"]
                cache[key] = {"mtime": mt, "trades": tr, "secs": round(time.time() - t0, 1), "params": {"sym": "NQ"},
                              "period": [a, z]}
                print(f"model {key}: {len(tr)} trades in {time.time() - t0:.0f}s", flush=True)
            except Exception as e:                       # a module still being written by its owner
                cache[key] = {"mtime": mt, "error": repr(e)[:300]}
                print(f"model {key}: ERROR {e!r}", flush=True)
            with open(BED_MODELS, "w", encoding="utf-8") as fh:
                json.dump(cache, fh, default=float)
    return cache


def load_beds():
    beds = collections.OrderedDict()
    o1 = json.load(open(BED_ORIG1D, encoding="utf-8"))
    beds["orig1day_2026"] = {"label": "Engine max 1/day, 2026 (primary)", "trades": o1["ytd"]["trades"], "halves": H26}
    beds["orig1day_2025"] = {"label": "Engine max 1/day, 2025-04-14..12-31 (holdout)", "trades": o1["y2025"]["trades"], "halves": H25}
    if os.path.exists(BED_ENGINE):
        e = json.load(open(BED_ENGINE, encoding="utf-8"))
        beds["engine_2026"] = {"label": "Engine (grade off, conviction 0, max 2/day), 2026", "trades": e["ytd"]["trades"], "halves": H26}
        beds["engine_2025"] = {"label": "Engine (grade off, conviction 0, max 2/day), 2025", "trades": e["y2025"]["trades"], "halves": H25F}
    mb = model_beds()
    for yr in ("2026", "2025"):
        for name in MODELS + EXTRA_MODELS:
            v = mb.get(name if yr == "2026" else f"{name}@2025", {})
            if v.get("trades"):
                beds[f"{name}_{yr}"] = {"label": f"lab model {name} (NQ, defaults), " +
                                        ("2026" if yr == "2026" else "2025-04-14..12-31") +
                                        (" [extra]" if name in EXTRA_MODELS else ""),
                                        "trades": v["trades"], "halves": H26 if yr == "2026" else H25}
    return beds


def _boot_diff(a, b, n=2000, seed=11):
    if len(a) < 3 or len(b) < 3:
        return None
    rng = np.random.default_rng(seed)
    ma = a[rng.integers(0, len(a), (n, len(a)))].mean(1)
    mb = b[rng.integers(0, len(b), (n, len(b)))].mean(1)
    dd = ma - mb
    return {"lo": float(np.percentile(dd, 2.5)), "hi": float(np.percentile(dd, 97.5)), "p_pos": float((dd > 0).mean())}


def _grp(rr, pn):
    n = len(rr)
    if not n:
        return {"n": 0, "win": None, "avg_r": None, "pf": None}
    gp, gl = float(pn[pn > 0].sum()), float(-pn[pn < 0].sum())
    return {"n": n, "win": round(float((pn > 0).mean() * 100), 1), "avg_r": round(float(rr.mean()), 3),
            "pf": round(gp / gl, 2) if gl > 0 else (99.0 if gp > 0 else None), "net": round(float(pn.sum()), 0)}


def test_feature(trades, mask, halves, weeks, min_n=8, min_half=3, boot_n=2000):
    out = {"freq": round(float(mask.mean()), 3)}
    days = np.array([t["day"] for t in trades])
    rr = np.array([t["r"] for t in trades], float)
    pn = np.array([t["pnl"] for t in trades], float)
    for key, (a, z) in zip(("h1", "h2", "full"), halves):
        sel = (days >= a) & (days <= z)
        w, wo = sel & mask, sel & ~mask
        out[key] = {"with": _grp(rr[w], pn[w]), "without": _grp(rr[wo], pn[wo]),
                    "tpw_with": round(w.sum() / weeks[key], 2), "tpw_without": round(wo.sum() / weeks[key], 2)}
        gw, gwo = out[key]["with"], out[key]["without"]
        out[key]["diff"] = round(gw["avg_r"] - gwo["avg_r"], 3) if gw["n"] and gwo["n"] else None
        out[key]["ci"] = _boot_diff(rr[w], rr[wo], n=boot_n, seed=11 + len(key)) if gw["n"] >= min_half and gwo["n"] >= min_half else None
    out["label"], out["edge_label"] = label(out, min_n, min_half)
    return out


def label(x, min_n=8, min_half=3):
    f, h1, h2 = x["full"], x["h1"], x["h2"]
    if (f["with"]["n"] < min_n or f["without"]["n"] < min_n or h1["with"]["n"] < min_half or h2["with"]["n"] < min_half
            or h1["without"]["n"] < min_half or h2["without"]["n"] < min_half or h1["diff"] is None or h2["diff"] is None):
        return "THIN", "THIN"

    def clear(h, sgn):
        return h["ci"] is not None and h["diff"] * sgn >= 0.15 and (h["ci"]["p_pos"] if sgn > 0 else 1 - h["ci"]["p_pos"]) >= 0.9
    out = []
    for sgn, name, tpw in ((1, "HELPS", f["tpw_with"]), (-1, "HURTS", f["tpw_without"])):
        same = h1["diff"] * sgn > 0 and h2["diff"] * sgn > 0
        sig = (f["ci"] is not None and ((f["ci"]["lo"] > 0) if sgn > 0 else (f["ci"]["hi"] < 0))) or (clear(h1, sgn) and clear(h2, sgn))
        if same and sig:
            out.append((name, tpw >= 2.0))
    if not out:
        return "NOISE", "NOISE"
    name, freq_ok = out[0]
    return (name if freq_ok else "NOISE"), name


def placebo_fpr(trades, halves, weeks, reps=300, seed=5):
    rng = np.random.default_rng(seed)
    probs = [0.1, 0.25, 0.5, 0.75, 0.9]
    cnt = collections.Counter()
    tested = 0
    for i in range(reps):
        m = rng.random(len(trades)) < probs[i % len(probs)]
        x = test_feature(trades, m, halves, weeks, boot_n=500)
        if x["edge_label"] == "THIN":
            continue
        tested += 1
        cnt[x["edge_label"]] += 1
        cnt["strict_" + x["label"]] += 1
    return {"tested": tested, "helps_rate": round(cnt["HELPS"] / max(tested, 1), 3), "hurts_rate": round(cnt["HURTS"] / max(tested, 1), 3),
            "strict_helps_rate": round(cnt["strict_HELPS"] / max(tested, 1), 3),
            "strict_hurts_rate": round(cnt["strict_HURTS"] / max(tested, 1), 3)}


def run_beds(placebo_reps=300):
    t0 = time.time()
    beds = load_beds()
    out = collections.OrderedDict()
    for name, bd in beds.items():
        tr = annotate(bd["trades"])
        tr = [t for t in tr if t["_f"]]
        halves = bd["halves"]
        weeks = {k: max(1e-9, _sessions_between(a, z) / 5.0) for k, (a, z) in zip(("h1", "h2", "full"), halves)}
        res = {"label": bd["label"], "n": len(tr), "tpw": round(len(tr) / weeks["full"], 2), "halves": halves,
               "base": {k: _grp(np.array([t["r"] for t in tr if a <= t["day"] <= z], float),
                                np.array([t["pnl"] for t in tr if a <= t["day"] <= z], float))
                        for k, (a, z) in zip(("h1", "h2", "full"), halves)},
               "features": {}}
        for f in BOOL:
            m = np.array([_truthy(t["_f"].get(f)) for t in tr], bool)
            res["features"][f] = test_feature(tr, m, halves, weeks)
        res["placebo"] = placebo_fpr(tr, halves, weeks, reps=placebo_reps)
        lab = collections.Counter(v["edge_label"] for v in res["features"].values())
        res["counts"] = {"edge": dict(lab), "strict": dict(collections.Counter(v["label"] for v in res["features"].values()))}
        ntest = sum(1 for v in res["features"].values() if v["edge_label"] != "THIN")
        res["expected_false"] = {"helps": round(res["placebo"]["helps_rate"] * ntest, 1),
                                 "hurts": round(res["placebo"]["hurts_rate"] * ntest, 1), "tested": ntest}
        out[name] = res
        print(f"bed {name}: n={len(tr)} tpw={res['tpw']} edge labels {dict(lab)} expected false {res['expected_false']} "
              f"({time.time() - t0:.0f}s)", flush=True)
    out["_cross"] = cross_bed(out)
    out["_pooled"] = pooled_test({b: annotate(beds[b]["trades"]) for b in FAMILIES if b in beds})
    return out


FAMILIES = ["orig1day_2026", "orig1day_2025", "silver_bullet_2026", "ict2022_2026", "mech_ifvg_2026",
            "silver_bullet_2025", "ict2022_2025", "mech_ifvg_2025"]


def _diff_se(r, m):
    a, b = r[m], r[~m]
    if len(a) < 8 or len(b) < 8:
        return None, None
    return float(a.mean() - b.mean()), float(np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b)))


def pooled_test(fam, reps=400, seed=3):
    """Equal-weight average of the with-minus-without diff over the (roughly independent) bed families, its z, and a
    permutation null for the largest |z| among all confluences (family-wise multiple-testing threshold)."""
    R = {b: np.array([t["r"] for t in tr if t["_f"]], float) for b, tr in fam.items()}
    M = {b: {f: np.array([_truthy(t["_f"].get(f)) for t in tr if t["_f"]], bool) for f in BOOL} for b, tr in fam.items()}

    def zstats(RR, masks):
        res = {}
        for f in BOOL:
            ds, ses = [], []
            for b in fam:
                dd, se = _diff_se(RR[b], masks[b][f])
                if dd is not None and se and se > 0:
                    ds.append(dd)
                    ses.append(se)
            if len(ds) >= 3:
                m = float(np.mean(ds))
                se = float(np.sqrt(np.sum(np.square(ses))) / len(ses))
                res[f] = {"mean_diff": round(m, 3), "se": round(se, 3), "z": round(m / se, 2), "k": len(ds),
                          "same_sign": int(max(sum(1 for x in ds if x > 0), sum(1 for x in ds if x < 0)))}
        return res
    real = zstats(R, M)
    rng = np.random.default_rng(seed)
    maxz = []
    for _ in range(reps):                  # Westfall-Young: shuffle the outcomes, keep the confluence columns intact
        zs = zstats({b: rng.permutation(R[b]) for b in fam}, M)
        maxz.append(max((abs(v["z"]) for v in zs.values()), default=0.0))
    thr = float(np.percentile(maxz, 95))
    for f, v in real.items():
        v["familywise_sig"] = abs(v["z"]) >= thr
        v["nominal_sig"] = abs(v["z"]) >= 1.96
    return {"families": list(fam), "real": real, "maxz_p95": round(thr, 2), "maxz_p50": round(float(np.percentile(maxz, 50)), 2),
            "reps": reps}


def cross_bed(beds):
    names = [b for b in beds if not b.startswith("_")]
    rows = {}
    for f in BOOL:
        per = {}
        for b in names:
            x = beds[b]["features"][f]
            per[b] = {"diff": x["full"]["diff"], "label": x["label"], "edge": x["edge_label"], "freq": x["freq"],
                      "tpw_with": x["full"]["tpw_with"], "tpw_without": x["full"]["tpw_without"]}
        ds = [v["diff"] for v in per.values() if v["diff"] is not None and v["edge"] != "THIN"]
        rows[f] = {"per": per, "n_beds": len(ds), "pos": sum(1 for v in ds if v > 0), "neg": sum(1 for v in ds if v < 0),
                   "mean_diff": round(float(np.mean(ds)), 3) if ds else None,
                   "helps": [b for b, v in per.items() if v["edge"] == "HELPS"],
                   "hurts": [b for b, v in per.items() if v["edge"] == "HURTS"],
                   "strict_helps": [b for b, v in per.items() if v["label"] == "HELPS"],
                   "strict_hurts": [b for b, v in per.items() if v["label"] == "HURTS"]}
    return rows


def lookahead_check(n=60, seed=1):
    """Recompute features on bars truncated at the entry (same start) and compare: any difference = lookahead."""
    from tools.strategy_lab import bars as lab_bars
    o1 = json.load(open(BED_ORIG1D, encoding="utf-8"))
    mb = json.load(open(BED_MODELS, encoding="utf-8")) if os.path.exists(BED_MODELS) else {}
    pool = o1["ytd"]["trades"] + o1["y2025"]["trades"] + sum((v.get("trades", []) for v in mb.values()), [])
    rng = np.random.default_rng(seed)
    pick = [pool[i] for i in rng.choice(len(pool), size=min(n, len(pool)), replace=False)]
    nq_all = lab_bars("NQ", "5m", "2024-12-01", "2026-10-16")
    es_all = lab_bars("ES", "5m", "2025-04-01", "2026-10-16")
    bad, checked = [], 0
    for t in pick:
        a = (dt.date.fromisoformat(t["day"]) - dt.timedelta(days=45)).isoformat()
        full = nq_all[nq_all["day"] >= a].reset_index(drop=True)
        efull = es_all[es_all["day"] >= a].reset_index(drop=True)
        f_full = Ctx(full).feat(t["entry_t"], t["dir"], Ctx(efull) if len(efull) else None, t.get("entry"))
        if not f_full:
            continue
        px = f_full["p0_x"]
        cut = full[full["time"] + 300 <= t["entry_t"]].reset_index(drop=True)
        ecut = efull[efull["time"] + 300 <= t["entry_t"]].reset_index(drop=True)
        f_cut = Ctx(cut).feat(t["entry_t"], t["dir"], Ctx(ecut) if len(ecut) else None, px)
        checked += 1
        e = dt.datetime.fromtimestamp(int(t["entry_t"]), ET)
        at_open = (e.hour * 60 + e.minute) in (0, 510, 570, 1080) or (e.hour * 60 + e.minute) % 90 == 0
        for k in BOOL:
            if _truthy(f_full.get(k)) != _truthy(f_cut.get(k)):
                bad.append((t["day"], t["entry_t"], e.strftime("%H:%M"), k, f_full.get(k), f_cut.get(k),
                            "open-at-entry" if at_open else "LOOKAHEAD?"))
    real = [b for b in bad if b[-1] != "open-at-entry"]
    print(f"lookahead check: {checked} trades, {len(bad)} mismatches, {len(real)} not explained by an opening price "
          f"that prints exactly at entry_t", flush=True)
    for b in bad[:30]:
        print("  ", b)
    return {"checked": checked, "mismatches": len(bad), "unexplained": len(real), "examples": bad[:30]}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd == "priority":
        write_results(pri=priority(n_placebo=int(sys.argv[2]) if len(sys.argv) > 2 else 200))
    elif cmd == "models":
        model_beds(refresh="--refresh" in sys.argv)
    elif cmd == "beds":
        write_results(beds=run_beds())
    elif cmd == "write":
        write_results()
    elif cmd == "lookahead":
        lookahead_check(int(sys.argv[2]) if len(sys.argv) > 2 else 60)
    elif cmd == "all":
        pri, bd = priority(), run_beds()
        pri["lookahead"] = lookahead_check(120)
        write_results(pri=pri, beds=bd)
