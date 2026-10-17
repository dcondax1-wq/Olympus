"""
LIQUIDITY-SWEEP -> IFVG MECHANICAL MODEL  (Blake-style mech model + AMT + ICT liquidity confluence)

Pipeline per bar (no lookahead: only closed bars / confirmed swings are used):
  1. LIQUIDITY MAP   - PDH/PDL (+older untaken), prior week H/L, Asia/London/Overnight H/L,
                       1H swing highs/lows, 15m ITH/ITL, equal highs/lows (EQH/EQL).
  2. AUCTION (AMT)   - prior RTH volume profile -> POC / VAH / VAL, open location vs value.
  3. STRUCTURE       - 1H + 15m swing structure, BOS/CHoCH, protected high / protected low.
  4. SWEEP           - price trades through a pool  -> setup ARMED in the opposite direction.
  5. MANIPULATION    - the leg from the last swing to the sweep extreme.
  6. IFVG TRIGGER    - a body close through a fair value gap formed inside that leg
                       (CISD close-through fallback when the leg has no FVG).
  7. DRAW ON LIQ.    - target = nearest untaken opposing pool that pays >= min R.
  8. CONFLUENCE      - HTF trend, protected low/high intact, LRL vs HRL path, AMT location,
                       SMT divergence vs partner index, pool quality.
  9. EXECUTION       - next-bar-open fill w/ slippage, stop beyond sweep, partial @1R -> BE, runner to DOL,
                       flat before close, prop-firm-aware daily loss / trade caps / drawdown-aware sizing.
"""
from __future__ import annotations

import datetime as _dt
import math
from copy import deepcopy

import numpy as np

from .data import Bars, TF_SECONDS, resample
from .instruments import INSTRUMENTS
from .learn import Ridge, vec
from .mtf import MTF, from_bars

DEFAULTS = {
    "entry_windows": [[570, 690], [810, 930]],   # ET minutes: 09:30-11:30, 13:30-15:30
    "arm_start": 480,           # sweeps from 08:00 ET may arm a setup
    "arm_expiry_min": 60,       # minutes after the last extreme before an armed setup expires
    "leg_lookback_min": 120,    # minutes searched back from the extreme for the manipulation-leg origin
    "flat_mod": 955,            # 15:55 ET flatten (MFFU: no positions through session close)
    "max_trades_day": 2,
    "stop_after_win": True,
    "daily_max_loss": 600.0,    # internal stop well inside MFFU $1,000 soft DLL
    "risk_usd": 350.0,
    "dd_aware": True,           # cap risk at a fraction of the cushion above the trailing MLL
    "cushion_frac": 0.25,
    "risk_mode": "fixed",       # fixed (risk_usd, capped by cushion_frac when dd_aware) | cushion (cushion_frac x distance to MLL)
    "lock_boost": 1.0,          # multiply risk once the trailing MLL has locked (eval sprint lever; 1 = off)
    "grade_sizing": True,       # size every trade by its A+..D checklist grade (replaces conviction sizing when on)
    # discovery-scan grade weights (study_discovery.py): first-45m x2 + Q3 entry improved all 3 periods at equal trade count
    "g_h1sweep": 0, "g_early": 2, "g_stacked": 0, "g_q3": 1,
    "g_pd": 2,                  # grade weight of the 1H discount/premium check (discovery: negative in every period)
    "g_london": 0,              # grade penalty when the raided pool is the London high/low (discovery: stable negative)
    "skip_london": False,       # hard-skip London H/L raids instead of down-sizing
    "ifvg_fail_exit": False,    # exit at the close if a bar closes back through the far side of the inverted FVG (idea failed)
    # ---- in-trade exit signals: every open trade watches for warning signs; each first firing is logged with the
    #      counterfactual "what if we had left here" so the bot learns which signs are worth acting on
    "exit_rules": "giveback",   # comma list of signals to always act on (opp_disp, trig_break, giveback, stall, zone_reentry,
                                #   zone_fail, opp_fvg, m15_flip, two_against, vol_against)
                                #   giveback won on all 4 periods: NQ PF 8.7 -> 9.9, max DD -514 -> -372, bad periods -$400..-$900 smaller
    "exit_learn": True,         # walk-forward: act on any other signal once its past counterfactual gain is proven
    "exit_learn_min": 20,       # ... after at least this many completed trades where it fired
    "exit_learn_threshold": 0.20,   # ... and the average gain from leaving is at least this many R (conservative: never hurt in tests)
    "exit_stall_bars": 6,       # 'stall' = no new high-water mark for this many bars while still under +1R
    "exit_giveback_r": 0.5,     # 'giveback' = trade reached this many R, then a bar closes back below entry
    "lock_at_r": 0, "lock_r": 0,   # once MFE >= lock_at_r, stop can never be worse than entry + lock_r x risk
    "be_at_r_trending": 0, "max_rr_trending": 0,   # regime-conditional exits: earlier BE / nearer target cap on trending days
    # ---- trend-day playbook: with-trend FVG retest continuation (second setup for the regime where reversals fail)
    "trend_model": False,
    "trend_require_regime": True,   # only on trending days (10-day efficiency > regime_er10_max)
    "trend_require_dir5": False,    # also require the 5-day direction to agree
    "trend_fvg_lookback_min": 90,   # how far back a with-trend FVG may have formed
    "trend_fvg_mult": 1.0,          # min gap size as a multiple of the instrument's min_fvg
    "trend_full_size": True,        # continuation trades are not halved by the trending-regime rule
    "grade_skip": "",           # grades to pass on entirely, e.g. "D"
    "conviction_step": 0.33,    # risk x (1 + step x conviction); conviction from sign-stable confluences (0 = off)
    "conviction_min": 0.5,
    "conviction_max": 1.5,
    "conviction_major": False,
    "risk_min": 200.0,
    "risk_max": 700.0,
    "start_balance": 50000.0,
    "mll": 2000.0,
    "mll_lock": 50100.0,
    "account_reset_cushion": 250.0,   # backtest only (never live): EOD cushion above the MLL below which the simulated
                                      #   account is treated as blown and a fresh start_balance eval begins (0 = never)
    "contract": "auto",         # auto | micro | mini
    "max_micros": 40,           # MFFU 50K: 4 minis / 40 micros
    "slippage_ticks": 1,
    "touch_ticks": 1,           # limit targets need a trade-through of N ticks
    "stop_mode": "swing",       # swing (beyond sweep extreme) | ifvg (beyond the inverted gap)
    "min_rr": 1.5,
    "max_rr": 5.0,
    "fallback_rr": 2.0,
    "use_fallback": True,
    "partial_r": 1.0,
    "partial_pct": 0.0,
    "be_after_partial": True,
    "partial_at": "r",          # r (at partial_r) | pool (at the first opposing pool between entry and target)
    "target_mode": "major",     # major (nearest major pool >= min R: session/day/week H-L, 1H swings, EQH/EQL) | major_next | dol (nearest pool >= min R) | dol_next (the pool after it) | fixed (fallback_rr) | draw (liquidity map, see below)
    "stop_buffer_mult": 1.0,    # multiplies the instrument stop buffer beyond the sweep
    "fixed_stop_pts": 0.0,      # > 0: stop exactly this many points from entry, whatever the structure (0 = off)
    "risk_ref_stop": 0.0,       # > 0: full risk_usd up to this stop (pts); wider stops risk risk_usd x ref / stop (0 = off)
    "be_at_r": 1.0,             # move stop to breakeven once price runs this many R (0 = off)
    "trail_mode": "none",       # none | r (trail trail_r behind the best price) | swing (trail behind 5m swings)
    "trail_start_r": 2.0,
    "trail_r": 1.0,
    "time_stop_min": 30,        # exit if the trade hasn't reached +0.5R after N minutes (0 = off)
    "use_cisd": True,
    "arm_minor": True,          # let plain 15m ITH/ITL sweeps arm setups (more trades, lower quality)
    "ifvg_pick": "first",       # first | outer
    "min_score": 1,
    "pools": {"PD": True, "PW": True, "ASIA": True, "LON": True, "ON": True, "H1": True, "M15": True},
    "amt_targets": False,
    "w_htf": 1, "w_protected": 0, "w_lrl": 1, "w_amt": 0, "w_smt": 0, "w_quality": 0,
    "long": True, "short": True,
    "days_from": None, "days_to": None,  # optional trading-day date filters (yyyy-mm-dd)
    "spec": {},                 # per-run instrument overrides (min_fvg, min_stop, max_stop, ...)
    "live": False,              # live mode: keep the last open position instead of closing it at data end
    # ---- news & volatility guard
    "news_filter": True,        # block new entries around high-impact US releases (CPI, NFP, FOMC, ...)
    "news_before_min": 15,
    "news_after_min": 30,
    "fomc_pm_off": True,        # with news_filter: no entries after 13:00 ET on FOMC days
    "news_flatten_min": 5,      # flatten an open trade this many minutes before a high-impact release (0 = off)
    "news_day_skip": "",        # comma list of event keywords whose whole day is skipped, e.g. "CPI,Payrolls"
    "vix_max": 0.0,             # skip days whose prior VIX close is above this (0 = off)
    "vix_min": 0.0,             # skip days whose prior VIX close is below this (0 = off)
    "regime_er10_max": 0.45,    # trending-market detector: 10-day efficiency above this = trending regime (0 = off)
    "regime_mode": "half",      # what to do in a trending regime: skip | half (trade at half size)
    "day_range_max": 1.6,       # no new entries once today's range >= this x the 20-day average range (0 = off)
    # ---- multi-timeframe layer
    "ifvg_tf": "base",          # base (5m IFVG) | highest (wait for the 15m IFVG when the leg has a 15m FVG)
                                #   | lower (5m context, confirm on the first 1m body close; needs true 1m bars, see data.load_ltf)
    "w_mtf": 0,                 # +w when >=2 of 1D/4H/1H/15m FVG order flow agree (net), -w when >=2 disagree
    "w_m15": -1,                # 15m structure already agrees -> late entry (study: hurt in both halves)
    "w_pd": 1,                  # sweep in discount (longs) / premium (shorts) of the 1H dealing range
    "w_midnight": 0,            # sweep below (longs) / above (shorts) the midnight true-day open
    "w_dol": 0,                 # trade points toward the nearest MAJOR untaken liquidity (HTF draw)
    "w_disp": 0, "w_fast": 0, "w_multi": 0, "w_major": 0, "w_vol": 0, "w_shallow": 0, "w_first": 0, "w_vwap": 0,
    "w_keylevel": 0,            # sweep tapped a 1D/4H/1H FVG or inverted FVG (Blake "valid key level")
    "mtf_gate": -9,             # hard filter: minimum net MTF alignment (-9 = off)
    "counter_rr_cap": 0,        # when fading HTF order flow (net <= -2) cap the target at this R (0 = off)
    # ---- shadow trades + walk-forward learner
    "learn": False,             # gate entries with a ridge model trained only on already-resolved shadow trades
    "learn_min": 30,            # resolved shadows required before the learner takes over
    "learn_lambda": 8.0,        # ridge penalty (bigger = more conservative)
    "learn_threshold": 0.0,     # take the trade when predicted R >= threshold
    # ---- persistent trade memory (engine/memory.py, data/memory.db)
    "memory_seed": True,        # seed the exit-signal learner from remembered paper + live trades at the start of every run
    "memory_write_backtest": False,   # also store this backtest's trades in memory as source 'backtest' (never used for seeding)
    # ---- discretionary-trader layer (engine/liquidity_map.py, rules from research/lab/DOL_PLAYBOOK.md). Every default
    #      below keeps today's behaviour; each piece switches on with its own mode: target_mode "draw",
    #      stop_model "struct_atr", manage_mode "person", plus exit rule "cisd_disp", noon_exit and the draw_* skip rules.
    #      target_mode "draw" (DOL-4): T = nearest Tier-A draw (PW/PD/RTH/ON/Asia/London H-L, 4H/D swings, EQH/EQL)
    #        >= draw_min_rr x R and within reach, else nearest Tier-B (1H swings, live 1H/4H/1D FVGs), else draw_fallback
    "draw_pick": "tier",        # tier (playbook DOL-4) | significance (most significant clean ERL: W > D > session > 1H swing)
                                #   | farthest_reach (farthest Tier A/B ERL >= draw_min_rr still within reach, else the
                                #   nearest within-reach draw >= draw_alt_min_rr; DRAW_LEARNER.md variant a)
    "draw_alt_min_rr": 1.5,     # farthest_reach fallback / PM cap: nearest within-reach draw at least this many R away
    "draw_pm": "same",          # same | nearest (PM entries: T = nearest within-reach draw >= draw_alt_min_rr)
    #      trader heuristics (research/lab/TRADER_HEURISTICS.md, NQ1! 2021-26 checks); draw mode only, all off by default
    "draw_pdx": False,          # B1: yesterday closed beyond the day-before's high (low) -> T = yesterday's high (low) when
                                #   >= draw_alt_min_rr and within reach (taken 80% / 67% vs 55% / 46%); void once the
                                #   opposite extreme trades first
    "draw_one_side": False,     # B3: 09:30 open inside the prior RTH range and one prior-day extreme already taken today ->
                                #   never target the other one (or beyond it): it follows only ~10% of the time
    "no_fade_drive": False,     # T1: pass on trades against an opening drive (by 10:00: the 09:30 open never revisited from
                                #   the 3rd bar, adverse <= 0.05 x ADR20, close - open >= 0.20 x ADR20)
    "balance_first": False,     # T4 proxy: RTH open inside the prior value area (AMT balance) -> T = nearest draw within
                                #   reach >= draw_alt_min_rr (quick exit)
    "draw_min_rr": 2.0,         # draw: minimum distance to T in R
    "draw_reach": "playbook",   # playbook: dist <= max(0.5 x ADR10, ADR10 - today's range) | none
    "draw_fallback": "2r",      # no Tier A/B draw: 2r (DOL-9: E + 2R) | skip | major (today's nearest-major rule)
    "draw_exit_ticks": 2,       # exit this many ticks before the pool (into it, not beyond)
    "draw_max_obst": 2,         # significance pick only: path obstacles allowed
    "draw_eq_w": 1.0,           # significance pick only: bonus for an equal highs / lows pool
    "draw_rank": "rule",        # rule | learned (engine/draw_learner.predict(features) -> P(hit before stop); max EV =
                                #   p*R - (1-p) among Tier A/B draws; falls back to the rule if the module is missing)
    "draw_min_ev": -99.0,       # learned: pass when the best draw's EV (in R) is below this (-99 = never)
    "draw_hrlr": "off",         # DOL-6 skip rule: off | tp1 (>= 3 obstacles: everything exits at TP1, skip if TP1 < draw_min_rr)
    "draw_block_r": 0.0,        # DOL-6 skip rule: pass if a live opposing 1H/4H FVG starts within this many R (0 = off)
    "irl_tfs": "5m,15m,1h,4h,1d",   # timeframes whose live FVGs are internal (IRL) draws
    "irl_mitigation": "ce_touch",   # an FVG stops being a draw on: ce_touch (a wick to its 50% CE; playbook D6) | ce_close |
                                    #   touch (any trade into it) | full
    "fvg_min": "playbook",      # gap minimum: playbook (5m max(1 tick, 0.1 ATR14), 15m+ 1 tick) | engine (min_fvg x tf mult)
    "irl_level": "edge",        # an FVG draw's price: edge (near edge = first touch) | ce
    "irl_min_r": 1.0,           # TP1 = nearest internal draw at least this many R away, short of T (DOL-5)
    "irl_partial_src": "playbook",  # TP1 candidates: playbook (gaps + Tier B/C pools, HTF gap > EQ > swing > 5m gap within
                                    #   0.25R) | all (any draw, nearest) | fvg (gaps only)
    #      stop_model "struct_atr" (STOP-1..3): sweep extreme - max(2 ticks, stop_atr_buf x ATR14); never widened to a
    #        minimum or tightened; too wide (> max stop) = pass, inside the noise (< min_stop_atr x ATR) = pass
    "stop_model": "fixed",      # fixed (today: stop_mode + instrument min/max stop clamp) | struct_atr | protected_swing
    "stop_atr_buf": 0.1,        # struct_atr: buffer = max(2 ticks, this x Wilder ATR14 of 5m)
    "min_stop_atr": 0.5,        # struct_atr: pass when the stop is tighter than this x ATR14 (0 = off)
    "max_stop_atr": 0.0,        # struct_atr: pass when the stop is wider than this x ATR14 (0 = off)
    "stop_cap": "size",         # struct_atr: size (playbook STOP-3: too wide only when risk_usd buys < 1 micro) | spec
                                #   (also pass above the instrument max_stop, 60 NQ points)
    "stop_origin": False,       # struct_atr: use the displacement-origin higher low when tighter and valid (playbook: no)
    #      manage_mode "person" (MGMT-1..4): TP1 for ceil(n x irl_partial_pct) (>= 1 runner kept) -> stop to entry + 2 ticks
    #        at the first of TP1 or +person_be_r R -> trail to each new 5m protected low - buffer on every BOS -> rest at T
    "manage_mode": "standard",  # standard (today: be_at_r, partial_pct, trail_mode) | person
    "irl_partial_pct": 0.5,     # person: fraction closed at TP1
    "person_be_r": 1.0,         # person: breakeven at +this R if TP1 has not filled yet (0 = only at TP1)
    "person_be_ticks": 2,       # person: breakeven stop = entry + this many ticks
    "person_trail": True,       # person: structure trail after breakeven (MGMT-3)
    "trail_buf_atr": 0.1,       # person: trail buffer = max(2 ticks, this x ATR14)
    "noon_exit": False,         # MGMT-7: at 12:00 ET exit an AM trade whose stop is still below entry
    #      entry_mode "retest" (gallery finding: most full-stop losers died inside the entry bar): after the trigger, rest a
    #        LIMIT at the trigger zone and fill only if a later bar trades 1 tick through it within retest_bars; the stop
    #        stays at invalidation. Cancelled when it expires, at flat time, or if price reaches the target first.
    "entry_mode": "market",     # market (today: next bar's open) | retest
    "retest_bars": 6,           # retest: bars the limit stays working after the signal bar
    "retest_level": "edge",     # retest: IFVG near edge | ce (its 50%); a CISD trigger always uses its CISD level
    #      stop_model "protected_swing": like struct_atr, but the invalidation is the swing the displacement launched
    #        from (lowest low from the candle before the in-favour run that triggered, through the trigger bar) instead of
    #        the sweep wick; no draw >= min_rr -> pass
}

MAJOR_KINDS = {"PDH", "PDL", "PWH", "PWL", "ONH", "ONL", "LOH", "LOL", "ASH", "ASL", "H1H", "H1L"}


def _is_major(q):
    """Major liquidity: session / day / week extremes, 1H swings and any equal highs/lows."""
    return bool(q.get("eq")) or any(k in MAJOR_KINDS for k in q.get("kinds", [q["kind"]]))


_DRAW_LEARNER = {"tried": False, "fn": None}


def _draw_predictor():
    """draw_rank 'learned': engine/draw_learner.predict(features) -> P(draw hit before the stop), or None when the
    module (owned by another session) is missing or has no predict(); the rule ranking is used then."""
    if not _DRAW_LEARNER["tried"]:
        _DRAW_LEARNER["tried"] = True
        try:
            from . import draw_learner as _dl
            fn = getattr(_dl, "predict", None)
            _DRAW_LEARNER["fn"] = fn if callable(fn) else None
        except Exception:
            _DRAW_LEARNER["fn"] = None
    return _DRAW_LEARNER["fn"]


POOL_STRENGTH = {"PDH": 2, "PDL": 2, "PWH": 3, "PWL": 3, "ONH": 2, "ONL": 2, "ASH": 1, "ASL": 1,
                 "LOH": 2, "LOL": 2, "H1H": 2, "H1L": 2, "ITH": 1, "ITL": 1, "PDH2": 2, "PDL2": 2}


def merge_params(p: dict | None) -> dict:
    out = deepcopy(DEFAULTS)
    for k, v in (p or {}).items():
        if k == "pools" and isinstance(v, dict):
            out["pools"].update(v)
        elif k in out:
            out[k] = v
    return out


# ----------------------------------------------------------------------------------------- structure
class Structure:
    """Fractal swing structure with BOS / CHoCH and protected high/low tracking."""

    def __init__(self, n: int = 2):
        self.n = n
        self.t, self.h, self.l, self.c = [], [], [], []
        self.sh = None   # (idx, price) last unbroken swing high
        self.sl = None
        self.trend = 0
        self.protected_low = None
        self.protected_high = None
        self.lsh = None   # latest confirmed swing high / low (dealing range)
        self.lsl = None
        self.events = []

    def add(self, t, h, l, c):
        self.t.append(t); self.h.append(h); self.l.append(l); self.c.append(c)
        new = []
        n = self.n
        k = len(self.h) - 1 - n
        if k >= n:
            hk, lk = self.h[k], self.l[k]
            if hk > max(self.h[k - n:k]) and hk >= max(self.h[k + 1:k + n + 1]):
                self.sh = (k, hk)
                self.lsh = hk
                new.append(("H", hk, self.t[k]))
            if lk < min(self.l[k - n:k]) and lk <= min(self.l[k + 1:k + n + 1]):
                self.sl = (k, lk)
                self.lsl = lk
                new.append(("L", lk, self.t[k]))
        i = len(self.c) - 1
        if self.sh is not None and c > self.sh[1]:
            seg = self.l[self.sh[0]:i + 1]
            self.protected_low = min(seg) if seg else l
            if self.trend != 1:
                self.events.append((t, "CHoCH up" if self.trend == -1 else "BOS up"))
            self.trend = 1
            self.sh = None
        elif self.sl is not None and c < self.sl[1]:
            seg = self.h[self.sl[0]:i + 1]
            self.protected_high = max(seg) if seg else h
            if self.trend != -1:
                self.events.append((t, "CHoCH down" if self.trend == 1 else "BOS down"))
            self.trend = -1
            self.sl = None
        if self.trend == 1 and self.protected_low is not None and c < self.protected_low:
            self.trend = -1
            self.protected_high = max(self.h[max(0, i - 12):i + 1])
            self.events.append((t, "Protected low broken"))
        elif self.trend == -1 and self.protected_high is not None and c > self.protected_high:
            self.trend = 1
            self.protected_low = min(self.l[max(0, i - 12):i + 1])
            self.events.append((t, "Protected high broken"))
        return new


# ----------------------------------------------------------------------------------------- AMT
def volume_profile(h, l, v, bin_size):
    if len(h) == 0:
        return None
    lo = math.floor(min(l) / bin_size) * bin_size
    hi = math.ceil(max(h) / bin_size) * bin_size
    nb = max(1, int(round((hi - lo) / bin_size)))
    hist = np.zeros(nb)
    for hh, ll, vv in zip(h, l, v):
        vv = vv if vv > 0 else 1.0
        a = int((ll - lo) // bin_size)
        b = int((hh - lo) // bin_size)
        a, b = max(0, min(a, nb - 1)), max(0, min(b, nb - 1))
        hist[a:b + 1] += vv / (b - a + 1)
    poc_i = int(np.argmax(hist))
    total = hist.sum()
    lo_i = hi_i = poc_i
    acc = hist[poc_i]
    while acc < 0.7 * total and (lo_i > 0 or hi_i < nb - 1):
        up = hist[hi_i + 1] if hi_i < nb - 1 else -1
        dn = hist[lo_i - 1] if lo_i > 0 else -1
        if up >= dn:
            hi_i += 1; acc += up
        else:
            lo_i -= 1; acc += dn
    return {
        "poc": lo + (poc_i + 0.5) * bin_size,
        "vah": lo + (hi_i + 1) * bin_size,
        "val": lo + lo_i * bin_size,
        "lo": lo, "bin": bin_size, "hist": [round(float(x), 1) for x in hist],
    }


# ----------------------------------------------------------------------------------------- engine
class Engine:
    def __init__(self, base: Bars, htf: Bars | None = None, partner: Bars | None = None, params: dict | None = None,
                 ltf: Bars | None = None):
        self.b = base
        self.sym = base.sym
        self.p = merge_params(params)
        self.spec = {**INSTRUMENTS[base.sym], **(self.p.get("spec") or {})}
        self.secs = TF_SECONDS[base.tf]
        self.htf = htf if htf is not None else resample(base, "1h")
        self.m15 = resample(base, "15m") if self.secs < 900 else base
        self.mtf = MTF(self.htf, from_bars(self.m15, 900), self.spec["min_fvg"]) if self.htf.tf == "1h" and self.m15.tf == "15m" else None
        # news calendar + volatility (always loaded so every candidate records them as features)
        from . import news as _news
        evs = _news.historical_events(("high",))
        self._ev_t = np.array([e["t"] for e in evs], dtype=np.int64)
        self._ev_name = [e["event"] for e in evs]
        self._ev_day = {}
        for e in evs:
            self._ev_day.setdefault(e["date"], []).append(e["event"])
        self._vix = _news.vix_prev_close("VIX")
        from . import gamma as _gamma
        try:
            self._gex = _gamma.prev_day_map()
        except Exception:
            self._gex = {}
        self.partner = partner
        self.partner_idx = None
        if partner is not None:
            self.partner_idx = {int(t): j for j, t in enumerate(partner.t)}
        # hybrid entry (ifvg_tf "lower"): 5m context, trigger confirmed on the 1m close. Off unless asked for.
        self.ltf, self._ltf_a, self._ltf_dir, self.ltf_info = None, None, None, None
        if self.p["ifvg_tf"] == "lower":
            self._ltf_setup(ltf)

    def _ltf_setup(self, ltf):
        """Map every base bar to its 1m bars. A 5m bar is usable only when all of its 1m bars exist (consecutive 60 s
        spacing) and they rebuild the 5m bar within spec['ltf_tol'] points (default 1.0); other bars fall back to the
        normal 5m trigger, and ltf_info says how much of the run actually used 1m confirmation."""
        b = self.b
        info = {"requested": "lower", "source": None if ltf is None else f"{ltf.sym} {ltf.tf} ({len(ltf)} bars)",
                "windows_1m": 0, "inconsistent": 0, "entry_bars": 0, "entry_bars_1m": 0}
        nper = self.secs // 60
        if ltf is None or len(ltf) == 0 or nper < 2:
            info["mode"] = "5m fallback: no 1m bars supplied - every trigger used the normal 5m close"
            self.ltf_info = info
            return
        # private copy of the price arrays: the 1m scan rebuilds the live 5m bar in place and must never touch shared,
        # cached Bars (data.load caches them; the dashboard may run several backtests in one process)
        self.b = b = Bars(b.sym, b.tf, b.t, b.o.copy(), b.h.copy(), b.l.copy(), b.c.copy(), b.v.copy(),
                          b.mod, b.tday, b.dow, b.date_str)
        tol = float(self.spec.get("ltf_tol", 1.0))
        a = np.full(len(b), -1, dtype=np.int64)
        k = np.searchsorted(ltf.t, b.t)
        last = k + nper - 1
        ok = last < len(ltf)
        idx = np.nonzero(ok)[0]
        ok_idx = idx[(ltf.t[k[idx]] == b.t[idx]) & (ltf.t[last[idx]] == b.t[idx] + self.secs - 60)]
        for i in ok_idx:
            j = int(k[i])
            sl = slice(j, j + nper)
            if (abs(ltf.o[j] - b.o[i]) <= tol and abs(ltf.h[sl].max() - b.h[i]) <= tol and
                    abs(ltf.l[sl].min() - b.l[i]) <= tol and abs(ltf.c[j + nper - 1] - b.c[i]) <= tol):
                a[i] = j
            else:
                info["inconsistent"] += 1
        win = np.array([any(x <= int(m) < z for x, z in self.p["entry_windows"]) for m in b.mod])
        info["windows_1m"] = int((a >= 0).sum())
        info["entry_bars"] = int(win.sum())
        info["entry_bars_1m"] = int((win & (a >= 0)).sum())
        if info["windows_1m"] == 0:
            info["mode"] = "5m fallback: the 1m bars cover none of this run's 5m bars - every trigger used the normal 5m close"
            self.ltf_info = info
            return
        info["mode"] = (f"1m confirmation on {info['entry_bars_1m']} of {info['entry_bars']} entry-window 5m bars; "
                        f"the rest fell back to the normal 5m trigger")
        self.ltf, self._ltf_a, self.ltf_info = ltf, a, info
        self._ltf_dir = {1: (ltf.o, ltf.h, ltf.l, ltf.c), -1: (-ltf.o, -ltf.l, -ltf.h, -ltf.c)}

    # ------------------------------------------------------------------ helpers
    def _pool(self, kind, side, price, t_created, label=None):
        # the same extreme detected by several lenses (e.g. a 1H swing that is also a 15m swing or the Asia high)
        # is ONE level - merge it instead of double counting it as "equal highs"
        for q in self.active:
            if q["side"] == side and abs(q["price"] - price) < self.spec["tick"] / 2:
                if kind not in q["kinds"]:
                    q["kinds"].append(kind)
                    q["strength"] = max(q["strength"], POOL_STRENGTH.get(kind, 1))
                    if POOL_STRENGTH.get(kind, 1) > POOL_STRENGTH.get(q["kind"], 1):
                        q["kind"] = kind
                    pre = ("EQH·" if side == "H" else "EQL·") if q["eq"] else ""
                    order = sorted(q["kinds"], key=lambda k: -POOL_STRENGTH.get(k, 1))
                    q["label"] = pre + "/".join(order)
                return q
        pid = len(self.all_pools)
        pool = {"id": pid, "kind": kind, "side": side, "price": float(price), "label": label or kind,
                "t0": int(t_created), "t1": None, "strength": POOL_STRENGTH.get(kind, 1), "eq": False, "kinds": [kind]}
        self.all_pools.append(pool)
        self.active.append(pool)
        return pool

    def _mark_equal(self, pool):
        tol = self.spec["eq_tol"]
        for q in self.active:
            if q is pool or q["side"] != pool["side"] or q["kind"] not in ("H1H", "H1L", "ITH", "ITL", "PDH", "PDL", "ONH", "ONL", "LOH", "LOL", "ASH", "ASL"):
                continue
            if self.spec["tick"] / 2 <= abs(q["price"] - pool["price"]) <= tol:
                for z in (q, pool):
                    if not z["eq"]:
                        z["eq"] = True
                        z["strength"] += 1
                        z["label"] = ("EQH·" if z["side"] == "H" else "EQL·") + z["label"]

    def _ev(self, t, kind, text, **data):
        self.events.append({"t": int(t), "type": kind, "text": text, **data})

    # ------------------------------------------------------------------ main loop
    def run(self):
        b, p, spec = self.b, self.p, self.spec
        tick = spec["tick"]
        n = len(b)
        self.all_pools, self.active = [], []
        self.events, self.trades, self.signals, self.days = [], [], [], {}
        self.ifvgs = []
        self.profiles = {}
        self.struct_events = []

        h1 = Structure(2)
        m15 = Structure(2)
        hi_ptr = 0
        m15_ptr = 0
        htf, mb = self.htf, self.m15
        htf_secs = TF_SECONDS[htf.tf]
        m15_secs = TF_SECONDS[mb.tf]

        # warm the 1h structure with history before the first base bar
        while hi_ptr < len(htf) and htf.t[hi_ptr] + htf_secs <= b.t[0]:
            h1.add(htf.t[hi_ptr], htf.h[hi_ptr], htf.l[hi_ptr], htf.c[hi_ptr])
            hi_ptr += 1
        # discretionary layer (off by default): Wilder ATR14 of the base bars + the liquidity map (live FVGs on
        # 5m / 15m / 1H / 4H / 1D, prior RTH H/L, 4H / daily swings) for target_mode "draw" / manage_mode "person"
        use_map = p["target_mode"] == "draw" or p["manage_mode"] == "person"
        self._atr_w = None
        if use_map or p["stop_model"] in ("struct_atr", "protected_swing"):
            from .liquidity_map import wilder_atr
            self._atr_w = wilder_atr(b.h, b.l, b.c)
        self._lmap = self._build_lmap(htf, mb) if use_map else None
        self._cisd_on = "cisd_disp" in {x.strip() for x in str(p["exit_rules"]).split(",")}

        # per-day accumulators
        cur_day = None
        day_start_idx = 0
        prev_days = []          # list of dicts {tday, high, low, date}
        self._prev_days_ref = prev_days
        self._trend_used = set()
        self._xstats = {}
        self._xseed_n = {}
        if p.get("memory_seed"):
            # continual learning: start the exit learner from what paper + live trading already taught it (never backtest
            # rows). Only remembered trades on this symbol that CLOSED BEFORE this run's first bar are used: trades inside
            # the window are re-derived from the bars walk-forward anyway, so this never double counts and a backtest over
            # the same dates never sees outcomes from its own future.
            try:
                from .memory import MEMORY
                if MEMORY.exists() and MEMORY.count(("paper", "live")) >= 1:
                    gains = MEMORY.exit_gains(("paper", "live"), sym=self.sym, before=int(b.t[0]))
                    self._xstats = {k: list(v) for k, v in gains.items()}
                    self._xseed_n = {k: len(v) for k, v in gains.items()}
            except Exception:
                self._xstats, self._xseed_n = {}, {}
        self._regime_day = {}
        week_hl = {}            # iso-week -> [hi, lo]
        sess = {}
        prof = None
        open_loc = None
        rth_open = None

        balance = p["start_balance"]
        peak_eod = balance
        mll_level = balance - p["mll"]
        self.account_resets = []

        pos = None
        pending = None          # order to fill at next bar open
        setups = {1: None, -1: None}
        self.shadows = []       # every candidate signal with a virtual outcome (learning set)
        open_shadows = []
        learner = Ridge(p["learn_lambda"])
        self.learner_log = []
        midnight_open = None
        self._m15_ptr = 0
        self._vw = [0.0, 0.0, None]
        self._tz = {"day": None, "AM": None, "PM": None, "week": None, "micro": {}}   # true opens (Quarterly Theory / AMD)
        day_pnl = 0.0
        day_trades = 0
        day_won = False

        dir_arr = {
            1: (b.o, b.h, b.l, b.c),
            -1: (-b.o, -b.l, -b.h, -b.c),
        }

        def in_window(mod):
            return any(a <= mod < z for a, z in p["entry_windows"])

        # ---- hybrid entry (ifvg_tf "lower") helpers; inert unless _ltf_setup found usable 1m bars
        ltf_on = self._ltf_a is not None
        ltf_carry = None            # 1m trigger on the last minute of a 5m bar: becomes `pending` after this bar's fill step
        L1 = self.ltf

        def bar_put(k, o_, h_, l_, c_, v_):
            """Overwrite base bar k (and its direction-space mirror) - used to expose only the 1m bars closed so far."""
            b.o[k], b.h[k], b.l[k], b.c[k], b.v[k] = o_, h_, l_, c_, v_
            nO, nH, nL, nC = dir_arr[-1]
            nO[k], nH[k], nL[k], nC[k] = -o_, -l_, -h_, -c_

        def ltf_decide(d, s, trig, order, i, j, mod):
            """Same decision path as the 5m block below, for a trigger confirmed on 1m bar j. Returns the sized order or None."""
            t1 = int(L1.t[j])
            if order.get("skip"):
                self._ev(t1, "skip", order["skip"], dir=d)
                if order.get("consume"):
                    setups[d] = None
                return None
            sh = {"dir": d, "sig_i": i, "t": t1, "day": b.date_str[i], "stop": order["stop"], "target": order["target"],
                  "entry": None, "f": order["features"], "score": order["score"], "taken": False,
                  "trigger": order["trigger"], "tags": order["conf_tags"], "grade": order["grade"],
                  "grade_points": order["grade_points"]}
            open_shadows.append(sh)
            if day_trades >= p["max_trades_day"] or day_pnl <= -p["daily_max_loss"] or (p["stop_after_win"] and day_won):
                self._ev(t1, "skip", f"{order['trigger']} (1m) valid but daily limits reached - logged as shadow trade", dir=d)
                setups[d] = None
                return None
            nb = self._news_block(t1, b.date_str[i], mod)
            if not nb and p["day_range_max"] and len(prev_days) >= 5:
                adr = float(np.mean([x["high"] - x["low"] for x in prev_days[-20:]]))
                dr = float(b.h[day_start_idx:i + 1].max() - b.l[day_start_idx:i + 1].min())
                if adr > 0 and dr / adr >= p["day_range_max"]:
                    nb = f"day range already {dr / adr:.1f}x its 20-day average (trend / news day)"
            er10 = (self._regime_day or {}).get("er10")
            trending = bool(p["regime_er10_max"] and er10 is not None and er10 > p["regime_er10_max"])
            order["regime"] = "trending" if trending else "rotational"
            if not nb and trending and p["regime_mode"] == "skip" and order.get("model") != "trend":
                nb = f"trending regime (10-day efficiency {er10:.2f} > {p['regime_er10_max']}) - reversal model stands aside"
            if nb:
                self._ev(t1, "news", f"{order['trigger']} (1m) valid but {nb} - pass (shadow logged)", dir=d)
                return None
            take = order["score"] >= p["min_score"] and order["features"]["mtf_net"] >= p["mtf_gate"]
            why = f"confluence {order['score']} < {p['min_score']}" if order["score"] < p["min_score"] else \
                f"MTF alignment {order['features']['mtf_net']} < gate {p['mtf_gate']}"
            if p["learn"] and len(self.shadows) >= p["learn_min"]:
                done = self.shadows
                learner.fit(np.array([vec(z["f"]) for z in done]), np.array([z["r"] for z in done]))
                pred = learner.predict(vec(order["features"]))
                take = pred >= p["learn_threshold"]
                why = f"learner E[R] {pred:+.2f} < {p['learn_threshold']}"
                order["pred_r"] = round(pred, 3)
                order["conf_tags"] = order["conf_tags"] + [f"learner E[R] {pred:+.2f}"]
                self.learner_log.append({"t": t1, "pred": round(pred, 3), "take": bool(take), "n": len(done),
                                         "w": learner.weights(), "mu": round(learner.mu, 3)})
            if not take:
                self._ev(t1, "skip", f"{order['trigger']} (1m) found but {why} [{', '.join(order['conf_tags'])}] - pass (shadow logged)", dir=d)
                return None
            sized = self._size(order, balance, mll_level)
            if sized.get("skip"):
                self._ev(t1, "skip", sized["skip"], dir=d)
                setups[d] = None
                return None
            sh["taken"] = True
            px1 = float(L1.c[j])
            self.signals.append({"t": t1, "dir": d, "price": px1, "score": order["score"],
                                 "trigger": order["trigger"], "pools": [q["label"] for q in s["pools"]], "tf": "1m"})
            self._ev(t1, "signal", f"{order['trigger']} CONFIRMED ON 1m ({'bullish' if d == 1 else 'bearish'} 1m body close "
                     f"through {trig['top'] * d:.2f}) | GRADE {order['grade']} ({order['grade_points']} pts) | score {order['score']} "
                     f"[{', '.join(order['conf_tags'])}] -> sending {'BUY' if d == 1 else 'SELL'} {order['qty_label']}", dir=d, price=px1)
            self.ifvgs.append({"t0": trig["t0"], "t1": t1, "top": trig["zone"][1], "bottom": trig["zone"][0],
                               "dir": d, "type": order["trigger"]})
            setups[d] = None
            setups[-d] = None
            return order

        for i in range(n):
            t, o, h, l, c, mod = int(b.t[i]), b.o[i], b.h[i], b.l[i], b.c[i], int(b.mod[i])
            tday = int(b.tday[i])
            t_end = t + self.secs

            # ======================================================= new trading day
            if tday != cur_day:
                if cur_day is not None:
                    # close any position at previous close (safety; normally flat already)
                    if pos is not None:
                        self._close(pos, i - 1, b.c[i - 1], "EOD")
                        balance += pos["pnl"]
                        day_pnl += pos["pnl"]
                        self.days[b.date_str[i - 1]]["trades"] += 1
                        pos = None
                    # end-of-day trailing drawdown update
                    self.days[b.date_str[i - 1]]["pnl"] = round(day_pnl, 2)
                    self.days[b.date_str[i - 1]]["balance"] = round(balance, 2)
                    peak_eod = max(peak_eod, balance)
                    mll_level = min(max(mll_level, peak_eod - p["mll"]), p["mll_lock"])
                    self.days[b.date_str[i - 1]]["mll"] = mll_level
                    if p["account_reset_cushion"] and not p["live"] and balance - mll_level < p["account_reset_cushion"]:
                        # multi-year research runs: an account at (or within a few $ of) its trailing max-loss level can no
                        # longer size even 1 micro (cushion x cushion_frac) and used to sit out the rest of history (2021-26
                        # run: 0 trades from 2024-03 on). Model what a trader does: the eval is dead, start a fresh one.
                        self.account_resets.append({"date": b.date_str[i - 1], "balance": round(balance, 2), "mll": mll_level})
                        self._ev(int(b.t[i - 1]), "risk", f"account reset: balance {balance:,.0f} vs MLL {mll_level:,.0f} "
                                 f"(cushion < {p['account_reset_cushion']:.0f}) - fresh {p['start_balance']:,.0f} eval")
                        balance = p["start_balance"]
                        peak_eod = balance
                        mll_level = balance - p["mll"]
                    a = day_start_idx
                    dh, dl = float(b.h[a:i].max()), float(b.l[a:i].min())
                    rth = [(k) for k in range(a, i) if 570 <= b.mod[k] < 960]
                    prev_days.append({"tday": cur_day, "high": dh, "low": dl, "date": b.date_str[i - 1],
                                      "open": float(b.o[a]), "close": float(b.c[i - 1]),
                                      "rth_open": float(b.o[rth[0]]) if rth else None, "rth_close": float(b.c[rth[-1]]) if rth else None,
                                      "rth_high": float(b.h[rth].max()) if rth else None, "rth_low": float(b.l[rth].min()) if rth else None})
                    if rth:
                        prof = volume_profile(b.h[rth], b.l[rth], b.v[rth], spec["profile_bin"])
                        if prof:
                            prof["date"] = b.date_str[i - 1]
                            self.profiles[b.date_str[i]] = prof
                cur_day = tday
                day_start_idx = i
                self._day_start = i
                self._adr20 = float(np.mean([x["high"] - x["low"] for x in prev_days[-20:]])) if prev_days else None
                self._regime_day = self._day_regime(prev_days)
                rd = self._regime_day
                self._day_meta = ({
                    "er5": None if rd.get("er5") is None else round(rd["er5"], 3),
                    "er10": None if rd.get("er10") is None else round(rd["er10"], 3),
                    "pd_trend": None if rd.get("pd_trend") is None else round(rd["pd_trend"], 3),
                    "vol_expansion": None if rd.get("vol_expansion") is None else round(rd["vol_expansion"], 3),
                    "regime": None if rd.get("er10") is None else ("trending" if rd["er10"] > (p["regime_er10_max"] or 0.45) else "rotational"),
                })
                day_pnl, day_trades, day_won = 0.0, 0, False
                setups = {1: None, -1: None}
                midnight_open = None
                sess = {"ASIA": [-1e18, 1e18, False], "LON": [-1e18, 1e18, False], "ON": [-1e18, 1e18, False]}
                self._sess = sess
                open_loc, rth_open = None, None
                self.days[b.date_str[i]] = {"date": b.date_str[i], "dow": int(b.dow[i]), "pnl": 0.0, "trades": 0, **self._day_meta}
                # retire stale pools: session pools older than 2 days, swing pools older than 5 days
                keep = []
                for q in self.active:
                    age = t - q["t0"]
                    lim = 5 * 86400 if q["kind"] in ("H1H", "H1L", "PWH", "PWL") else 2.2 * 86400
                    if q["kind"] in ("ITH", "ITL"):
                        lim = 1.2 * 86400
                    if age <= lim:
                        keep.append(q)
                    else:
                        q["t2"] = t   # retired (stale) - no longer tracked as liquidity
                self.active = keep
                if prev_days and p["pools"]["PD"]:
                    pdh, pdl = prev_days[-1]["high"], prev_days[-1]["low"]
                    for kind, side, px in (("PDH", "H", pdh), ("PDL", "L", pdl)):
                        q = self._pool(kind, side, px, t)
                        if (side == "H" and h > px) or (side == "L" and l < px):
                            q["t1"] = t
                            self.active.remove(q)
                # prior week high / low (on first day of a new week)
                if p["pools"]["PW"] and len(prev_days) >= 2:
                    wk = lambda ds: _dt.date.fromisoformat(ds).isocalendar()[:2]
                    this_w = wk(b.date_str[i])
                    if wk(prev_days[-1]["date"]) != this_w:
                        pw = [d for d in prev_days if wk(d["date"]) == wk(prev_days[-1]["date"])]
                        self._pool("PWH", "H", max(d["high"] for d in pw), t)
                        self._pool("PWL", "L", min(d["low"] for d in pw), t)

            # ======================================================= hybrid entry: 1m confirmation inside this 5m bar
            # Runs before this bar's structure / pool / VWAP updates, so the context is the previous 5m close. Each 1m bar
            # of the window is walked in order with bar i rebuilt from the 1m bars closed so far (no lookahead); a trigger
            # on 1m bar j fills at the open of 1m bar j+1, and stop / target are checked on the window's remaining 1m bars.
            if ltf_on and pos is None and pending is None and self._ltf_a[i] >= 0 and (setups[1] or setups[-1]) \
                    and in_window(mod) and mod < p["flat_mod"] - 10:
                j0 = int(self._ltf_a[i])
                nper = self.secs // 60
                full = (o, h, l, c, b.v[i])
                taken, tj, td = None, None, None
                try:
                    for j in range(j0, j0 + nper):
                        bar_put(i, o, float(L1.h[j0:j + 1].max()), float(L1.l[j0:j + 1].min()), float(L1.c[j]),
                                float(L1.v[j0:j + 1].sum()))
                        for d in (1, -1):
                            s = setups[d]
                            if s is None:
                                continue
                            O, H, L, C = dir_arr[d]
                            if L[i] < s["ext"] * d:
                                s["ext"] = b.l[i] if d == 1 else b.h[i]
                                s["ext_i"] = i
                            if (i - s["ext_i"]) * self.secs > p["arm_expiry_min"] * 60:
                                continue                    # the 5m rule expires it at this bar's close
                            s["ltf_scan_i"] = i
                            trig = self._find_trigger(d, s, i, O, H, L, C, ltf_j=j)
                            if trig is None:
                                continue
                            order = self._plan(d, s, trig, i, h1, m15, prof, open_loc, midnight_open)
                            taken = ltf_decide(d, s, trig, order, i, j, mod)
                            if taken is not None:
                                tj, td = j, d
                                break
                        if taken is not None:
                            break
                finally:
                    bar_put(i, *full)
                if taken is not None and tj == j0 + nper - 1:
                    ltf_carry = taken                       # next 1m open == next 5m open: the normal fill step takes it
                elif taken is not None:
                    d, jf = td, tj + 1
                    slip = p["slippage_ticks"] * tick
                    fill = float(L1.o[jf]) + d * slip
                    risk_pts = (fill - taken["stop"]) * d
                    if risk_pts <= 0 or (taken["target"] - fill) * d <= 0:
                        self._ev(int(L1.t[jf]), "skip", "Gap through stop/target at the 1m fill - order cancelled")
                    else:
                        pos = dict(taken)
                        pos.update({"entry": fill, "entry_t": int(L1.t[jf]), "entry_i": i, "risk_pts": risk_pts,
                                    "stop0": taken["stop"], "rr": round((taken["target"] - fill) * d / risk_pts, 2),
                                    "remaining": taken["qty"], "partial_done": False, "pnl": 0.0, "pnl_pts": 0.0,
                                    "pnl_partial_booked": 0.0, "mae": 0.0, "mfe": 0.0, "exits": [], "xsig": {}, "mfe_i": i,
                                    "m15_entry": m15.trend, "entry_tf": "1m",
                                    "atr": float(np.mean(np.maximum(b.h[max(1, i - 14):i], b.c[max(0, i - 15):i - 1]) -
                                                         np.minimum(b.l[max(1, i - 14):i], b.c[max(0, i - 15):i - 1]))) if i > 2 else risk_pts})
                        pos["partial_px"] = fill + d * p["partial_r"] * risk_pts
                        pp = taken.get("partial_pool")
                        if p["partial_at"] == "pool" and pp and 0.5 <= (pp[0] - fill) * d / risk_pts and (pp[0] - taken["target"]) * d < 0:
                            pos["partial_px"] = pp[0]
                        if p["manage_mode"] == "person":
                            pdw = taken.get("partial_draw")
                            pos["partial_px"] = pdw["target"] if pdw and (pdw["target"] - fill) * d > 0 else None
                        day_trades += 1
                        self._ev(int(L1.t[jf]), "entry", f"{'LONG' if d == 1 else 'SHORT'} {pos['qty_label']} @ {fill:.2f} (1m fill) | "
                                 f"SL {pos['stop']:.2f} | TP {pos['target']:.2f} ({pos['target_label']}) | {pos['rr']}R", dir=d, price=fill)
                        # stop / target on the rest of this window, 1m by 1m (stop checked first, as on 5m)
                        ex = None
                        for q1 in range(jf, j0 + nper):
                            qo, qh, ql = L1.o[q1], L1.h[q1], L1.l[q1]
                            low_d, high_d = (ql, qh) if d == 1 else (-qh, -ql)
                            pos["mae"] = max(pos["mae"], (pos["entry"] * d - low_d) / risk_pts)
                            mfe_now = (high_d - pos["entry"] * d) / risk_pts
                            if mfe_now > pos["mfe"]:
                                pos["mfe"] = mfe_now
                            if low_d <= pos["stop"] * d:
                                ex = ((min(qo * d, pos["stop"] * d) - slip) * d, "STOP", q1)
                                break
                            if high_d >= pos["target"] * d + p["touch_ticks"] * tick:
                                ex = (pos["target"], "TARGET", q1)
                                break
                        if ex is None:
                            # the 5m management step below handles the rest of this bar on its post-fill part only
                            pos["ltf_post"] = (float(L1.o[jf]), float(L1.h[jf:j0 + nper].max()), float(L1.l[jf:j0 + nper].min()))
                        else:
                            self._exit(pos, pos["remaining"], float(ex[0]), int(L1.t[ex[2]]), ex[1])
                            self._finalize(pos, i)
                            balance += pos["pnl"]
                            day_pnl += pos["pnl"]
                            self.days[b.date_str[i]]["trades"] += 1
                            if pos["pnl"] > 0:
                                day_won = True
                            self._ev(int(L1.t[ex[2]]), "exit", f"EXIT {pos['exit_reason']} (1m) | {pos['pnl_r']:+.2f}R | ${pos['pnl']:+,.0f}",
                                     pnl=pos["pnl"])
                            if day_pnl <= -p["daily_max_loss"]:
                                self._ev(t, "risk", f"Daily loss stop hit (${day_pnl:,.0f}) - bot done for the day")
                            pos = None

            # ======================================================= HTF structure updates (closed bars only)
            while hi_ptr < len(htf) and htf.t[hi_ptr] + htf_secs <= t_end:
                for side, px, ts in h1.add(htf.t[hi_ptr], htf.h[hi_ptr], htf.l[hi_ptr], htf.c[hi_ptr]):
                    if p["pools"]["H1"] and ts >= b.t[0] - 3 * 86400:
                        q = self._pool("H1H" if side == "H" else "H1L", side, px, htf.t[hi_ptr] + htf_secs)
                        # was it already run before confirmation?
                        self._mark_equal(q)
                hi_ptr += 1
            while m15_ptr < len(mb) and mb.t[m15_ptr] + m15_secs <= t_end:
                for side, px, ts in m15.add(mb.t[m15_ptr], mb.h[m15_ptr], mb.l[m15_ptr], mb.c[m15_ptr]):
                    if p["pools"]["M15"]:
                        q = self._pool("ITH" if side == "H" else "ITL", side, px, mb.t[m15_ptr] + m15_secs)
                        self._mark_equal(q)
                m15_ptr += 1
            self._m15_ptr = m15_ptr
            if self.mtf is not None:
                self.mtf.advance(t_end, int(b.t[0]) - 3 * 86400)
            if self._lmap is not None:
                self._lmap.advance(t_end, i)
            if midnight_open is None and 0 <= mod < 1080:
                midnight_open = o   # ICT "true day open"
            # ---- Quarterly Theory true opens (open of each cycle's 2nd quarter) + AMD daily open
            if i == day_start_idx:
                self._tz["day"] = o                                   # 18:00 ET daily candle open (Power of 3)
                self._tz["AM"], self._tz["PM"], self._tz["micro"] = None, None, {}
                if int(b.dow[i]) == 1:
                    self._tz["week"] = o                              # Tuesday's open = weekly true open
            if mod == 450:
                self._tz["AM"] = o                                    # 07:30 NY AM session true open
            if mod == 810:
                self._tz["PM"] = o                                    # 13:30 NY PM session true open
            for qs in (360, 450, 540, 630, 720, 810, 900):          # 90-min quarters; micro Q2 starts at +22.5 min
                if mod == qs + 20:
                    self._tz["micro"][qs] = o
            # RTH session VWAP (AMT fair value proxy)
            if mod == 570 or (570 <= mod < 960 and self._vw[2] != tday):
                self._vw = [0.0, 0.0, tday]
            if 570 <= mod < 960:
                vv = b.v[i] if b.v[i] > 0 else 1.0
                self._vw[0] += (h + l + c) / 3 * vv
                self._vw[1] += vv

            # ======================================================= session pools
            in_asia = mod >= 1200 or mod < 0
            in_lon = 120 <= mod < 300
            in_on = mod >= 1080 or mod < 570
            if in_asia:
                sess["ASIA"][0] = max(sess["ASIA"][0], h); sess["ASIA"][1] = min(sess["ASIA"][1], l)
            elif sess["ASIA"][0] > -1e17 and not sess["ASIA"][2] and mod < 1080:
                sess["ASIA"][2] = True
                if p["pools"]["ASIA"]:
                    self._mark_equal(self._pool("ASH", "H", sess["ASIA"][0], t))
                    self._mark_equal(self._pool("ASL", "L", sess["ASIA"][1], t))
            if in_lon:
                sess["LON"][0] = max(sess["LON"][0], h); sess["LON"][1] = min(sess["LON"][1], l)
            elif sess["LON"][0] > -1e17 and not sess["LON"][2] and 300 <= mod < 1080:
                sess["LON"][2] = True
                if p["pools"]["LON"]:
                    self._mark_equal(self._pool("LOH", "H", sess["LON"][0], t))
                    self._mark_equal(self._pool("LOL", "L", sess["LON"][1], t))
            if in_on:
                sess["ON"][0] = max(sess["ON"][0], h); sess["ON"][1] = min(sess["ON"][1], l)
            elif sess["ON"][0] > -1e17 and not sess["ON"][2] and 570 <= mod < 1080:
                sess["ON"][2] = True
                if p["pools"]["ON"]:
                    self._pool("ONH", "H", sess["ON"][0], t)
                    self._pool("ONL", "L", sess["ON"][1], t)
            if rth_open is None and 570 <= mod < 960:
                rth_open = o
                if prof:
                    open_loc = "above" if o > prof["vah"] else ("below" if o < prof["val"] else "inside")
                    self._ev(t, "amt", f"RTH open {o:.2f} {open_loc.upper()} prior value "
                             f"(VAL {prof['val']:.2f} / POC {prof['poc']:.2f} / VAH {prof['vah']:.2f})"
                             + (" -> balance: expect rotation, fade the edges" if open_loc == "inside"
                                else " -> imbalance: watch for acceptance or an 80%-rule return into value"))

            # ======================================================= fill pending order at this bar's open
            if pending is not None and pos is None:
                d = pending["dir"]
                slip = p["slippage_ticks"] * tick
                lim, post, fill = pending.get("limit"), None, None
                if lim is None:
                    fill = o + d * slip
                elif i > pending["limit_exp"] or mod >= p["flat_mod"] - 10 or int(b.tday[i]) != pending["limit_tday"]:
                    self._ev(t, "skip", f"retest limit {lim:.2f} not filled within {pending['retest_bars']} bars - "
                             f"order cancelled", dir=d)
                    pending = None
                elif (l if d == 1 else -h) <= lim * d - p["touch_ticks"] * tick:
                    # limit filled (a gap through it fills at the open). On this bar only the part after the fill is
                    # managed: the stop can be hit, a target cannot (the bar's high may have come before the fill).
                    fill = min(o * d, lim * d) * d
                    post = (fill, max(fill, c), l) if d == 1 else (fill, h, min(fill, c))
                elif (h if d == 1 else -l) >= pending["target"] * d:
                    self._ev(t, "skip", "price reached the target before the retest - order cancelled", dir=d)
                    pending = None
            if pending is not None and pos is None and fill is not None:
                risk_pts = (fill - pending["stop"]) * d
                if risk_pts <= 0 or (pending["target"] - fill) * d <= 0:
                    self._ev(t, "skip", "Gap through stop/target at open - order cancelled")
                else:
                    pos = dict(pending)
                    pos.update({"entry": fill, "entry_t": t, "entry_i": i, "risk_pts": risk_pts, "stop0": pending["stop"],
                                "rr": round((pending["target"] - fill) * d / risk_pts, 2), "remaining": pending["qty"],
                                "partial_done": False, "pnl": 0.0, "pnl_pts": 0.0, "pnl_partial_booked": 0.0,
                                "mae": 0.0, "mfe": 0.0, "exits": [], "xsig": {}, "mfe_i": i, "m15_entry": m15.trend,
                                "atr": float(np.mean(np.maximum(b.h[max(1, i - 14):i], b.c[max(0, i - 15):i - 1]) -
                                                     np.minimum(b.l[max(1, i - 14):i], b.c[max(0, i - 15):i - 1]))) if i > 2 else risk_pts})
                    pos["partial_px"] = fill + d * p["partial_r"] * risk_pts
                    pp = pending.get("partial_pool")
                    if p["partial_at"] == "pool" and pp and 0.5 <= (pp[0] - fill) * d / risk_pts and (pp[0] - pending["target"]) * d < 0:
                        pos["partial_px"] = pp[0]
                    if p["manage_mode"] == "person":
                        pdw = pending.get("partial_draw")
                        pos["partial_px"] = pdw["target"] if pdw and (pdw["target"] - fill) * d > 0 else None
                    if post is not None:
                        pos["ltf_post"], pos["entry_kind"] = post, "retest limit"
                    day_trades += 1
                    self._ev(t, "entry", f"{'LONG' if d == 1 else 'SHORT'} {pos['qty_label']} @ {fill:.2f}"
                             f"{' (retest limit)' if post is not None else ''} | "
                             f"SL {pos['stop']:.2f} | TP {pos['target']:.2f} ({pos['target_label']}) | {pos['rr']}R",
                             dir=d, price=fill)
                pending = None
            if ltf_carry is not None:
                pending, ltf_carry = ltf_carry, None        # 1m trigger on the bar's last minute: fills at the next bar open
            ltf_bar = pos is not None and pos.get("ltf_post") is not None
            if ltf_bar:
                o, h, l = pos.pop("ltf_post")              # entered on 1m inside this bar: manage only the post-fill part

            # ======================================================= manage open position
            if pos is not None:
                d = pos["dir"]
                slip = p["slippage_ticks"] * tick
                pos["mae"] = max(pos["mae"], ((pos["entry"] - l) if d == 1 else (h - pos["entry"])) / pos["risk_pts"])
                mfe_now = ((h - pos["entry"]) if d == 1 else (pos["entry"] - l)) / pos["risk_pts"]
                if mfe_now > pos["mfe"]:
                    pos["mfe"], pos["mfe_i"] = mfe_now, i
                fired = self._exit_signals(pos, i, o, h, l, c, m15)
                act = self._exit_active(fired)
                low_d = l if d == 1 else -h
                high_d = h if d == 1 else -l
                stop_d = pos["stop"] * d
                exited = False
                if low_d <= stop_d:
                    px = (min(o * d, stop_d) - slip) * d
                    self._exit(pos, pos["remaining"], px, t, "STOP" if not (pos["partial_done"] or pos.get("managed")) else "BE/TRAIL")
                    exited = True
                else:
                    if p["manage_mode"] == "person":
                        # person (MGMT-1/2): bank ceil(n x irl_partial_pct) at TP1 (always keep a runner), then the stop
                        # goes to entry + person_be_ticks. One contract = no partial, so TP1 alone does not move the stop.
                        if (not pos["partial_done"]) and pos.get("partial_px") is not None and \
                                high_d >= pos["partial_px"] * d + p["touch_ticks"] * tick:
                            q = min(pos["qty"] - 1, int(math.ceil(pos["qty"] * p["irl_partial_pct"] - 1e-9)))
                            pos["partial_done"] = True
                            if 1 <= q < pos["remaining"]:
                                self._exit(pos, q, pos["partial_px"], t, f"TP1 {(pos.get('partial_draw') or {}).get('source', 'IRL')}")
                                pos["stop"] = max(pos["stop"] * d, pos["entry"] * d + p["person_be_ticks"] * tick) * d
                                pos["managed"] = True
                    elif (not pos["partial_done"]) and p["partial_pct"] > 0 and high_d >= pos["partial_px"] * d + p["touch_ticks"] * tick:
                        q = int(math.floor(pos["qty"] * p["partial_pct"]))
                        if q >= 1 and q < pos["remaining"]:
                            self._exit(pos, q, pos["partial_px"], t, f"TP1 {p['partial_r']}R")
                            pos["partial_done"] = True
                            if p["be_after_partial"]:
                                pos["stop"] = pos["entry"] + d * tick
                        else:
                            pos["partial_done"] = True
                    if high_d >= pos["target"] * d + p["touch_ticks"] * tick:
                        self._exit(pos, pos["remaining"], pos["target"], t, "TARGET")
                        exited = True
                    elif mod >= p["flat_mod"] or (i == n - 1 and not p["live"]) or (i + 1 < n and b.tday[i + 1] != tday):
                        self._exit(pos, pos["remaining"], c - d * slip, t, "TIME")
                        exited = True
                    elif p["news_flatten_min"] and len(self._ev_t) and \
                            np.any((self._ev_t > t_end) & (self._ev_t <= t_end + p["news_flatten_min"] * 60)):
                        self._exit(pos, pos["remaining"], c - d * slip, t, "NEWS FLAT")
                        exited = True
                    elif p["time_stop_min"] and (i - pos["entry_i"] + 1) * self.secs >= p["time_stop_min"] * 60 and pos["mfe"] < 0.5:
                        self._exit(pos, pos["remaining"], c - d * slip, t, "TIME STOP")
                        exited = True
                    elif p["noon_exit"] and mod + self.secs // 60 == 720 and int(b.mod[pos["entry_i"]]) < 720 and \
                            pos["stop"] * d < pos["entry"] * d:
                        self._exit(pos, pos["remaining"], c - d * slip, t, "NOON UNPROTECTED")
                        exited = True
                    elif p["ifvg_fail_exit"] and pos.get("zone") and i > pos["entry_i"] and \
                            (c - pos["zone"][0 if d == 1 else 1]) * d < 0:
                        self._exit(pos, pos["remaining"], c - d * slip, t, "IFVG FAIL")
                        exited = True
                    elif act:
                        pos["exit_signal"] = act
                        self._exit(pos, pos["remaining"], c - d * slip, t, f"SIGNAL {act}")
                        exited = True
                    else:
                        # ---- stop management for the NEXT bar (decided on this bar's close: no intrabar lookahead)
                        e_d, risk = pos["entry"] * d, pos["risk_pts"]
                        new_stop_d = pos["stop"] * d
                        be_r = p["be_at_r_trending"] if (pos.get("regime") == "trending" and p["be_at_r_trending"]) else p["be_at_r"]
                        be_tk = tick
                        if p["manage_mode"] == "person":
                            be_r, be_tk = p["person_be_r"], p["person_be_ticks"] * tick   # MGMT-2: TP1 or +1R, never earlier
                        if be_r and pos["mfe"] >= be_r:
                            new_stop_d = max(new_stop_d, e_d + be_tk)
                        if p["lock_at_r"] and pos["mfe"] >= p["lock_at_r"]:
                            new_stop_d = max(new_stop_d, e_d + p["lock_r"] * risk)
                        if p["trail_mode"] != "none" and pos["mfe"] >= p["trail_start_r"]:
                            if p["trail_mode"] == "r":
                                best_d = e_d + pos["mfe"] * risk
                                new_stop_d = max(new_stop_d, best_d - p["trail_r"] * risk)
                            else:
                                Ld = b.l if d == 1 else -b.h
                                k = i - 2       # latest confirmed fractal swing (2 bars each side)
                                while k > pos["entry_i"] + 1:
                                    if Ld[k] < Ld[k - 1] and Ld[k] < Ld[k - 2] and Ld[k] <= Ld[k + 1] and Ld[k] <= Ld[k + 2]:
                                        new_stop_d = max(new_stop_d, Ld[k] - spec["stop_buffer"])
                                        break
                                    k -= 1
                        if p["manage_mode"] == "person" and p["person_trail"]:
                            # MGMT-3: once at breakeven, every 5m BOS in favour lifts the stop to the new protected low - buffer
                            prot = self._protected_swing(pos, i, d)
                            if prot is not None and new_stop_d >= e_d:
                                atr_i = float(self._atr_w[i]) if self._atr_w is not None else (pos.get("atr") or risk)
                                new_stop_d = max(new_stop_d, prot - max(2 * tick, p["trail_buf_atr"] * atr_i))
                        if new_stop_d > pos["stop"] * d:
                            pos["stop"] = new_stop_d * d
                            pos["managed"] = True
                if exited:
                    self._finalize(pos, i)
                    balance += pos["pnl"]
                    day_pnl += pos["pnl"]
                    self.days[b.date_str[i]]["trades"] += 1
                    if pos["pnl"] > 0:
                        day_won = True
                    self._ev(t, "exit", f"EXIT {pos['exit_reason']} | {pos['pnl_r']:+.2f}R | ${pos['pnl']:+,.0f}",
                             pnl=pos["pnl"])
                    if day_pnl <= -p["daily_max_loss"]:
                        self._ev(t, "risk", f"Daily loss stop hit (${day_pnl:,.0f}) - bot done for the day")
                    pos = None
            if ltf_bar:
                o, h, l = b.o[i], b.h[i], b.l[i]

            # ======================================================= shadow trades (virtual outcomes for learning)
            if open_shadows:
                still_sh = []
                for sh in open_shadows:
                    if self._shadow_step(sh, i, o, h, l, c, mod, tday, n):
                        if sh.get("r") is not None:
                            self.shadows.append(sh)
                    else:
                        still_sh.append(sh)
                open_shadows = still_sh

            # ======================================================= liquidity sweeps
            swept = []
            still = []
            for q in self.active:
                if q["side"] == "H" and h >= q["price"] + tick:
                    q["t1"] = t
                    swept.append(q)
                elif q["side"] == "L" and l <= q["price"] - tick:
                    q["t1"] = t
                    swept.append(q)
                else:
                    still.append(q)
            self.active = still
            can_arm = mod >= p["arm_start"] and mod < p["flat_mod"]
            for q in swept:
                d = 1 if q["side"] == "L" else -1   # sell-side sweep arms longs, buy-side sweep arms shorts
                if q["kind"] in ("ITH", "ITL") and not q["eq"] and not p["arm_minor"]:
                    continue  # minor internal swings don't arm on their own
                if not can_arm:
                    continue
                if (d == 1 and not p["long"]) or (d == -1 and not p["short"]):
                    continue
                ext = l if d == 1 else h
                s = setups[d]
                if s is None:
                    setups[d] = {"dir": d, "ext": ext, "ext_i": i, "arm_i": i, "pools": [q], "triggered": False}
                    self._ev(t, "sweep", f"{'SSL' if d == 1 else 'BSL'} SWEPT: {q['label']} {q['price']:.2f} "
                             f"-> {'long' if d == 1 else 'short'} setup armed, hunting IFVG", dir=d, price=q["price"])
                else:
                    s["pools"].append(q)
                    self._ev(t, "sweep", f"Also swept {q['label']} {q['price']:.2f}", dir=d, price=q["price"])

            # ======================================================= armed setups -> IFVG trigger
            for d in (1, -1):
                s = setups[d]
                O, H, L, C = dir_arr[d]
                trig = None
                if s is None:
                    # no sweep armed this way: the trend-day playbook may still offer a with-trend continuation
                    if pos is not None or pending is not None or not in_window(mod) or mod >= p["flat_mod"] - 10:
                        continue
                    hit = self._find_continuation(d, i, O, H, L, C, h1, tday)
                    if hit is None:
                        continue
                    s, trig = hit
                else:
                    if L[i] < s["ext"] * d:
                        s["ext"] = l if d == 1 else h
                        s["ext_i"] = i
                    if (i - s["ext_i"]) * self.secs > p["arm_expiry_min"] * 60:
                        self._ev(t, "expire", f"{'Long' if d == 1 else 'Short'} setup expired - no IFVG in time")
                        setups[d] = None
                        continue
                    if pos is not None or pending is not None:
                        continue
                    if not in_window(mod) or mod >= p["flat_mod"] - 10:
                        continue
                    if s.get("ltf_scan_i") == i:
                        continue        # hybrid: this bar was already checked 1m by 1m; the 5m close adds nothing new
                    trig = self._find_trigger(d, s, i, O, H, L, C)
                    if trig is None:
                        continue
                order = self._plan(d, s, trig, i, h1, m15, prof, open_loc, midnight_open)
                if order.get("skip"):
                    self._ev(t, "skip", order["skip"], dir=d)
                    if order.get("consume"):
                        setups[d] = None
                    continue
                # every valid candidate becomes a shadow trade, whatever we decide next
                sh = {"dir": d, "sig_i": i, "t": t, "day": b.date_str[i], "stop": order["stop"], "target": order["target"],
                      "entry": None, "f": order["features"], "score": order["score"], "taken": False,
                      "trigger": order["trigger"], "tags": order["conf_tags"], "grade": order["grade"],
                      "grade_points": order["grade_points"]}
                open_shadows.append(sh)
                if day_trades >= p["max_trades_day"] or day_pnl <= -p["daily_max_loss"] or (p["stop_after_win"] and day_won):
                    self._ev(t, "skip", f"{order['trigger']} valid but daily limits reached - logged as shadow trade", dir=d)
                    setups[d] = None
                    continue
                nb = self._news_block(t, b.date_str[i], mod)
                if not nb and p["day_range_max"] and len(prev_days) >= 5:
                    adr = float(np.mean([x["high"] - x["low"] for x in prev_days[-20:]]))
                    dr = float(b.h[day_start_idx:i + 1].max() - b.l[day_start_idx:i + 1].min())
                    if adr > 0 and dr / adr >= p["day_range_max"]:
                        nb = f"day range already {dr / adr:.1f}x its 20-day average (trend / news day)"
                er10 = (self._regime_day or {}).get("er10")
                trending = bool(p["regime_er10_max"] and er10 is not None and er10 > p["regime_er10_max"])
                order["regime"] = "trending" if trending else "rotational"
                if not nb and trending and p["regime_mode"] == "skip" and order.get("model") != "trend":
                    nb = f"trending regime (10-day efficiency {er10:.2f} > {p['regime_er10_max']}) - reversal model stands aside"
                if nb:
                    self._ev(t, "news", f"{order['trigger']} valid but {nb} - pass (shadow logged)", dir=d)
                    continue
                # ---- decision: confluence rule, or the walk-forward learner once it has enough resolved shadows
                take = order["score"] >= p["min_score"] and order["features"]["mtf_net"] >= p["mtf_gate"]
                why = f"confluence {order['score']} < {p['min_score']}" if order["score"] < p["min_score"] else \
                    f"MTF alignment {order['features']['mtf_net']} < gate {p['mtf_gate']}"
                if p["learn"]:
                    done = self.shadows
                    if len(done) >= p["learn_min"]:
                        X = np.array([vec(z["f"]) for z in done])
                        y = np.array([z["r"] for z in done])
                        learner.fit(X, y)
                        pred = learner.predict(vec(order["features"]))
                        take = pred >= p["learn_threshold"]
                        why = f"learner E[R] {pred:+.2f} < {p['learn_threshold']}"
                        order["pred_r"] = round(pred, 3)
                        order["conf_tags"] = order["conf_tags"] + [f"learner E[R] {pred:+.2f}"]
                        self.learner_log.append({"t": t, "pred": round(pred, 3), "take": bool(take), "n": len(done),
                                                 "w": learner.weights(), "mu": round(learner.mu, 3)})
                if not take:
                    self._ev(t, "skip", f"{order['trigger']} found but {why} [{', '.join(order['conf_tags'])}] - pass (shadow logged)", dir=d)
                    continue
                sized = self._size(order, balance, mll_level)
                if sized.get("skip"):
                    self._ev(t, "skip", sized["skip"], dir=d)
                    setups[d] = None
                    continue
                sh["taken"] = True
                pending = order
                self.signals.append({"t": t, "dir": d, "price": float(c), "score": order["score"],
                                     "trigger": order["trigger"], "pools": [q["label"] for q in s["pools"]]})
                self._ev(t, "signal", f"{order['trigger']} CONFIRMED ({'bullish' if d == 1 else 'bearish'} body close "
                         f"through {trig['top'] * d:.2f}) | GRADE {order['grade']} ({order['grade_points']} pts: "
                         f"{', '.join(c['label'] for c in order['checklist'] if c['state'] * c['weight'] > 0)[:160]}) | score {order['score']} [{', '.join(order['conf_tags'])}] "
                         f"-> sending {'BUY' if d == 1 else 'SELL'} {order['qty_label']}", dir=d, price=float(c))
                self.ifvgs.append({"t0": trig["t0"], "t1": t, "top": trig["zone"][1], "bottom": trig["zone"][0],
                                   "dir": d, "type": order["trigger"]})
                setups[d] = None
                setups[-d] = None

        # final day close-out
        if cur_day is not None and b.date_str[n - 1] in self.days:
            self.days[b.date_str[n - 1]]["pnl"] = round(day_pnl, 2)
            self.days[b.date_str[n - 1]]["balance"] = round(balance, 2)
            peak_eod = max(peak_eod, balance)
            mll_level = min(max(mll_level, peak_eod - p["mll"]), p["mll_lock"])
            self.days[b.date_str[n - 1]]["mll"] = mll_level
        for (tt, txt) in h1.events:
            self.struct_events.append({"t": int(tt), "tf": "1h", "text": txt})
        for (tt, txt) in m15.events:
            self.struct_events.append({"t": int(tt), "tf": "15m", "text": txt})

        # ---- live snapshot of the model at the last bar
        last_mod = int(b.mod[n - 1])
        if pos is not None:
            mstate = "IN TRADE"
        elif pending is not None:
            mstate = "ORDER PENDING"
        elif day_trades >= p["max_trades_day"] or day_pnl <= -p["daily_max_loss"] or (p["stop_after_win"] and day_won):
            mstate = "DONE FOR DAY"
        elif not in_window(last_mod):
            mstate = "OUTSIDE KILLZONE"
        elif setups[1] or setups[-1]:
            mstate = "ARMED - HUNTING IFVG"
        else:
            mstate = "WAITING FOR SWEEP"
        clean = lambda s: None if s is None else {"dir": s["dir"], "ext": float(s["ext"]), "arm_t": int(b.t[s["arm_i"]]),
                                                  "pools": [q["label"] for q in s["pools"]]}
        self.state = {
            "t": int(b.t[n - 1]), "price": float(b.c[n - 1]), "model_state": mstate,
            "position": None if pos is None else {k: v for k, v in pos.items() if k != "exits"} | {"exits": pos["exits"]},
            "pending": pending, "setups": {"long": clean(setups[1]), "short": clean(setups[-1])},
            "h1_trend": h1.trend, "m15_trend": m15.trend,
            "h1_protected_low": h1.protected_low, "h1_protected_high": h1.protected_high,
            "m15_protected_low": m15.protected_low, "m15_protected_high": m15.protected_high,
            "active_pools": sorted([dict(q) for q in self.active], key=lambda q: -q["price"]),
            "profile": prof, "open_loc": open_loc, "day_pnl": round(day_pnl, 2), "day_trades": day_trades,
            "balance": round(balance, 2), "mll": mll_level,
            "session": {k: [v[0] if v[0] > -1e17 else None, v[1] if v[1] < 1e17 else None, v[2]] for k, v in sess.items()},
            "mtf": self._mtf_snapshot(h1, m15, float(b.c[n - 1]), midnight_open),
        }
        return self

    def _mtf_snapshot(self, h1, m15, price, midnight_open):
        rows = []
        if self.mtf is not None:
            for tf in ("1D", "4H", "1H", "15m"):
                trk = self.mtf.trk[tf]
                near = sorted(trk.active, key=lambda g: min(abs(price - g["top"]), abs(price - g["bot"])))[:3]
                rows.append({"tf": tf, "bias": trk.bias, "last": trk.last_event,
                             "zones": [{"dir": g["dir"], "top": float(g["top"]), "bot": float(g["bot"]), "state": g["state"]} for g in near]})
        dr = None
        if h1.lsh is not None and h1.lsl is not None and h1.lsh > h1.lsl:
            dr = {"high": h1.lsh, "low": h1.lsl, "eq": (h1.lsh + h1.lsl) / 2, "pos": round((price - h1.lsl) / (h1.lsh - h1.lsl), 3)}
        net = sum(r["bias"] for r in rows)
        return {"tfs": rows, "net": net, "structure": {"1H": h1.trend, "15m": m15.trend}, "dealing_range": dr,
                "midnight_open": midnight_open}

    # ------------------------------------------------------------------ market regime (known before the open)
    @staticmethod
    def _day_regime(prev_days):
        """Regime measures from completed sessions only. er = efficiency ratio: |net move| / sum of |daily moves|."""
        out = {}
        if len(prev_days) < 6:
            return out
        closes = [d["close"] for d in prev_days]

        def er(n):
            if len(closes) < n + 1:
                return None
            seg = closes[-(n + 1):]
            path = sum(abs(seg[k + 1] - seg[k]) for k in range(n))
            return abs(seg[-1] - seg[0]) / path if path else None
        out["er5"], out["er10"] = er(5), er(10)
        rng = [d["high"] - d["low"] for d in prev_days]
        adr20 = float(np.mean(rng[-21:-1])) if len(rng) > 2 else None
        adr60 = float(np.mean(rng[-61:-1])) if len(rng) > 21 else None
        pd_ = prev_days[-1]
        out["pd_range_ratio"] = (rng[-1] / adr20) if adr20 else None
        if pd_.get("rth_open") is not None and pd_["rth_high"] > pd_["rth_low"]:
            out["pd_trend"] = abs(pd_["rth_close"] - pd_["rth_open"]) / (pd_["rth_high"] - pd_["rth_low"])
        out["vol_expansion"] = (float(np.mean(rng[-5:])) / adr60) if adr60 else None
        out["dir5"] = (1 if closes[-1] > closes[-6] else -1) if len(closes) >= 6 else 0
        return out

    def _regime_now(self, i, d):
        """Regime features at signal time: day-level measures + today's directional efficiency so far."""
        b = self.b
        rg = dict(getattr(self, "_regime_day", {}) or {})
        ds = getattr(self, "_day_start", 0)
        rth0 = next((k for k in range(ds, i + 1) if int(b.mod[k]) >= 570 and int(b.mod[k]) < 1080), None)
        a = rth0 if rth0 is not None and rth0 < i else ds
        cl = b.c[a:i + 1]
        path = float(np.abs(np.diff(cl)).sum()) if len(cl) > 1 else 0.0
        rg["day_er"] = abs(float(cl[-1] - cl[0])) / path if path else None
        rg["day_dir"] = (1 if cl[-1] > cl[0] else -1) if len(cl) > 1 else 0
        adr = getattr(self, "_adr20", None)
        if rth0 is not None and adr and len(self._prev_days_ref) and self._prev_days_ref[-1].get("rth_close"):
            rg["gap_adr"] = abs(float(b.o[rth0]) - self._prev_days_ref[-1]["rth_close"]) / adr
        # labels
        er5 = rg.get("er5")
        rg["trending_5d"] = int(er5 is not None and er5 >= 0.5)
        rg["rotational_5d"] = int(er5 is not None and er5 <= 0.25)
        rg["counter_5d"] = int(rg.get("dir5", 0) == -d)        # fading the 5-day direction
        rg["trend_today"] = int(rg.get("day_er") is not None and rg["day_er"] >= 0.35)
        rg["fade_today"] = int(rg.get("day_dir", 0) == -d)    # trade against today's net direction
        rg["pd_trend_day"] = int(rg.get("pd_trend") is not None and rg["pd_trend"] >= 0.6)
        rg["vol_expanding"] = int(rg.get("vol_expansion") is not None and rg["vol_expansion"] >= 1.25)
        rg["big_gap"] = int(rg.get("gap_adr") is not None and rg["gap_adr"] >= 0.35)
        return {("rg_" + k): (round(v, 3) if isinstance(v, float) else v) for k, v in rg.items()}

    # ------------------------------------------------------------------ news / volatility state at a moment
    def _news_state(self, t, day):
        p = self.p
        k = int(np.searchsorted(self._ev_t, t - p["news_after_min"] * 60))
        in_win, which = False, None
        while k < len(self._ev_t) and self._ev_t[k] <= t + p["news_before_min"] * 60:
            in_win, which = True, self._ev_name[k]
            k += 1
        day_ev = self._ev_day.get(day, [])
        return {"in_window": in_win, "event": which, "day_events": day_ev,
                "fomc_day": any("FOMC" in e for e in day_ev), "vix": self._vix.get(day)}

    def _news_block(self, t, day, mod):
        """Reason string when the news / volatility guard blocks a new entry, else None."""
        p = self.p
        st = self._news_state(t, day)
        if p["news_filter"]:
            if st["in_window"]:
                return f"NEWS BLACKOUT ({st['event']})"
            if p["fomc_pm_off"] and st["fomc_day"] and mod >= 780:
                return "FOMC day - no afternoon trades"
        if p["news_day_skip"]:
            keys = [k.strip().lower() for k in p["news_day_skip"].split(",") if k.strip()]
            hit = next((e for e in st["day_events"] if any(k in e.lower() for k in keys)), None)
            if hit:
                return f"News day skipped ({hit})"
        v = st["vix"]
        if v is not None and p["vix_max"] and v > p["vix_max"]:
            return f"VIX {v:.1f} above {p['vix_max']}"
        if v is not None and p["vix_min"] and v < p["vix_min"]:
            return f"VIX {v:.1f} below {p['vix_min']}"
        return None

    # ------------------------------------------------------------------ trend-day playbook
    def _find_continuation(self, d, i, O, H, L, C, h1, tday):
        """With-trend FVG retest: a gap in the trend direction forms, price pulls back into it without closing through
        it, then a bar closes back out of the gap. Entry next open, stop under the pullback low, target = next draw."""
        p, spec, b = self.p, self.spec, self.b
        if not p["trend_model"] or h1.trend != d:
            return None
        rd = getattr(self, "_regime_day", None) or {}
        er10 = rd.get("er10")
        if p["trend_require_regime"] and not (p["regime_er10_max"] and er10 is not None and er10 > p["regime_er10_max"]):
            return None
        if p["trend_require_dir5"] and rd.get("dir5") != d:
            return None
        if not (C[i] > O[i]):
            return None
        lb = int(p["trend_fvg_lookback_min"] * 60 // self.secs)
        a = max(2, i - lb)
        min_fvg = spec["min_fvg"] * p["trend_fvg_mult"]
        used = self._trend_used
        for k in range(i - 1, a, -1):          # most recent with-trend gap first; gap at bar k: L[k] > H[k-2]
            bot, top = H[k - 2], L[k]
            if top - bot < min_fvg or (tday, k) in used:
                continue
            closes, lows = C[k + 1:i + 1], L[k + 1:i + 1]
            if len(closes) == 0 or closes.min() < bot:        # gap closed through: not respected
                continue
            if lows.min() > top:                             # never retested
                continue
            if C[i] <= top:                                  # confirmation = close back out of the gap
                continue
            used.add((tday, k))
            ext_d = float(lows.min())
            ext_i = k + 1 + int(np.argmin(lows))
            pool = {"id": -1, "kind": "PB", "side": "L" if d == 1 else "H", "price": ext_d * d, "label": "pullback",
                    "t0": int(b.t[ext_i]), "t1": int(b.t[i]), "strength": 1, "eq": False, "kinds": ["PB"]}
            s = {"dir": d, "ext": ext_d * d, "ext_i": ext_i, "arm_i": k, "pools": [pool], "triggered": False}
            trig = {"type": "CONT", "tf": b.tf, "k": k, "t0": int(b.t[k - 2]), "top": top, "bot": bot,
                    "zone": sorted([bot * d, top * d]), "inv_low": float(bot)}
            self._ev(int(b.t[i]), "sweep", f"TREND DAY: with-trend FVG {bot * d:.2f}-{top * d:.2f} retested and held "
                     f"-> {'long' if d == 1 else 'short'} continuation", dir=d, price=top * d)
            return s, trig
        return None

    # ------------------------------------------------------------------ trigger detection
    def _find_trigger(self, d, s, i, O, H, L, C, ltf_j=None):
        if ltf_j is not None:
            return self._find_trigger_1m(d, s, i, O, H, L, C, ltf_j)
        p, spec = self.p, self.spec
        ext_i = s["ext_i"]
        a = max(0, ext_i - int(p["leg_lookback_min"] * 60 // self.secs))
        seg = H[a:ext_i + 1]
        leg_start = a + int(np.argmax(seg))
        min_fvg = spec["min_fvg"]
        b = self.b
        # ---- highest-timeframe IFVG: if the manipulation leg holds a 15m FVG, only its 15m inversion counts
        if p["ifvg_tf"] == "highest" and self.m15 is not b:
            mb = self.m15
            last = self._m15_ptr - 1                       # latest CLOSED 15m bar
            t_leg = int(b.t[leg_start]) // 900 * 900
            k0 = int(np.searchsorted(mb.t, t_leg))
            if last - k0 >= 2:
                if d == 1:
                    MO, MH, ML, MC = mb.o, mb.h, mb.l, mb.c
                else:
                    MO, MH, ML, MC = -mb.o, -mb.l, -mb.h, -mb.c
                gaps = [(k, MH[k], ML[k - 2]) for k in range(k0 + 2, last) if ML[k - 2] - MH[k] >= min_fvg * 1.5]
                if gaps:
                    closed_now = int(mb.t[last]) + 900 == int(b.t[i]) + self.secs
                    if not closed_now:
                        return None
                    for k, bot, top in sorted(gaps, key=lambda z: z[2]):
                        if MC[last] > top and MO[last] < MC[last] and (last - k <= 1 or MC[k + 1:last].max() <= top):
                            return {"type": "IFVG15", "tf": "15m", "k": i, "t0": int(mb.t[k - 2]), "top": top, "bot": bot,
                                    "zone": sorted([bot * d, top * d]), "inv_low": float(min(ML[k - 2:k + 1]))}
                    return None
        cands = []
        # "against" FVGs inside the manipulation leg: in direction-space they are bearish gaps H[k] < L[k-2]
        for k in range(leg_start + 2, i):
            top, bot = L[k - 2], H[k]
            if top - bot >= min_fvg:
                cands.append((k, bot, top))
        if cands:
            if p["ifvg_pick"] == "outer":
                cands = [max(cands, key=lambda z: z[2])]
            for k, bot, top in sorted(cands, key=lambda z: z[2]):
                # first body close through the top of the gap happens on this bar
                if C[i] > top and O[i] < C[i]:
                    prev_closes = C[k + 1:i]
                    if len(prev_closes) == 0 or prev_closes.max() <= top:
                        zone = sorted([bot * d, top * d])
                        return {"type": "IFVG", "tf": b.tf, "k": k, "t0": int(b.t[k - 2]), "top": top, "bot": bot, "zone": zone,
                                "inv_low": float(min(L[k - 2:k + 1]))}
            return None
        if p["use_cisd"]:
            j = ext_i
            while j > leg_start and C[j] < O[j]:
                j -= 1
            # j is the last up-close candle before the down sequence; level = open of first down candle
            first_dn = j + 1 if j < ext_i else ext_i
            level = O[first_dn]
            if C[i] > level and O[i] < C[i]:
                prev = C[ext_i + 1:i]
                if len(prev) == 0 or prev.max() <= level:
                    zone = sorted([L[ext_i] * d, level * d])
                    k = max(first_dn, 2)
                    return {"type": "CISD", "tf": b.tf, "k": k, "t0": int(b.t[k]), "top": level, "bot": L[ext_i], "zone": zone,
                            "inv_low": float(L[ext_i])}
        return None

    def _find_trigger_1m(self, d, s, i, O, H, L, C, j):
        """Hybrid trigger (ifvg_tf "lower"). The manipulation leg and its FVGs come from the 5m bars; the confirmation is the
        FIRST 1m body close through the gap (1m bar j). Legs without a 5m FVG use a 1m CISD: a 1m body close through the
        open of the 1m down-run that printed the extreme (the 5m CISD level when the extreme bar has no 1m data).
        run() has already rebuilt base bar i from the 1m bars closed up to j, so nothing later than 1m bar j is visible."""
        p, spec, b, m = self.p, self.spec, self.b, self.ltf
        mo, mh, ml, mc = self._ltf_dir[d]
        ext_i = s["ext_i"]
        a = max(0, ext_i - int(p["leg_lookback_min"] * 60 // self.secs))
        leg_start = a + int(np.argmax(H[a:ext_i + 1]))
        lo, lc = mo[j], mc[j]
        if not lo < lc:
            return None
        used = s.setdefault("ltf_used", set())       # a level confirms once: later 1m closes through it are not "first"
        cands = [(k, H[k], L[k - 2]) for k in range(leg_start + 2, i) if L[k - 2] - H[k] >= spec["min_fvg"]]
        if cands:
            if p["ifvg_pick"] == "outer":
                cands = [max(cands, key=lambda z: z[2])]
            for k, bot, top in sorted(cands, key=lambda z: z[2]):
                if lc <= top or ("F", k) in used:
                    continue
                prev = C[k + 1:i]
                if len(prev) and prev.max() > top:
                    continue
                ja = int(np.searchsorted(m.t, b.t[k + 1]))
                if j > ja and mc[ja:j].max() > top:
                    continue
                used.add(("F", k))
                return {"type": "IFVG", "tf": "1m", "k": k, "t0": int(b.t[k - 2]), "top": top, "bot": bot,
                        "zone": sorted([bot * d, top * d]), "inv_low": float(min(L[k - 2:k + 1])), "ltf_j": int(j)}
            return None
        if not p["use_cisd"]:
            return None
        e0 = int(self._ltf_a[ext_i])
        if e0 >= 0:
            nper = self.secs // 60
            e_hi = j if ext_i == i else e0 + nper - 1
            e1 = e0 + int(np.argmin(ml[e0:e_hi + 1]))
            lim = max(int(np.searchsorted(m.t, b.t[leg_start])), 0)
            g = e1
            while g > lim and m.t[g - 1] == m.t[g] - 60:      # start of the contiguous 1m run that holds the extreme
                g -= 1
            q = e1
            while q > g and mc[q] < mo[q]:
                q -= 1
            first_dn = q + 1 if q < e1 else e1
            level, bot, key = mo[first_dn], ml[e1], ("C1", int(m.t[first_dn]))
            if j > e1 + 1 and mc[e1 + 1:j].max() > level:
                return None
        else:
            q = ext_i
            while q > leg_start and C[q] < O[q]:
                q -= 1
            first_dn = q + 1 if q < ext_i else ext_i
            level, bot, key = O[first_dn], L[ext_i], ("C5", int(b.t[first_dn]))
            j0 = int(self._ltf_a[i])
            if j > j0 and mc[j0:j].max() > level:
                return None
        prev = C[ext_i + 1:i]
        if lc <= level or key in used or (len(prev) and prev.max() > level):
            return None
        used.add(key)
        return {"type": "CISD", "tf": "1m", "k": ext_i, "t0": key[1], "top": level, "bot": bot,
                "zone": sorted([bot * d, level * d]), "inv_low": float(bot), "ltf_j": int(j)}

    # ------------------------------------------------------------------ discretionary layer helpers (off by default)
    def _build_lmap(self, htf, mb):
        """Liquidity map fed bar by bar: live FVGs on the base tf / 15m / 1H / 4H / 1D, prior RTH H/L and 4H / daily
        3-bar swings (Tier-A pools the engine does not track). HTF series start a few weeks before the first base bar."""
        from .liquidity_map import LiquidityBook
        b, p = self.b, self.p
        book = LiquidityBook(self.spec["tick"], self.spec["min_fvg"], p["irl_mitigation"], p["fvg_min"])
        t0 = int(b.t[0])
        book.add_gap_series("5m" if b.tf == "5m" else b.tf, b.t, b.t + self.secs, b.h, b.l, b.c, atr=self._atr_w, tday=b.tday)
        if mb is not b and mb.tf == "15m":
            book.add_gap_series("15m", mb.t, mb.t + 900, mb.h, mb.l, mb.c)
        if htf is not None and htf.tf == "1h":
            book.add_gap_series("1h", htf.t, htf.t + 3600, htf.h, htf.l, htf.c, start_t=t0 - 12 * 86400)
            if self.mtf is not None:
                s4, s1d = self.mtf.series["4H"], self.mtf.series["1D"]
            else:
                from .mtf import build_1d, build_4h
                s4, s1d = build_4h(htf), build_1d(htf)
            ref = (htf.t, htf.t + 3600, htf.h, htf.l)
            for tf, s_ in (("4h", s4), ("1d", s1d)):
                book.add_gap_series(tf, s_.t, s_.tc, s_.h, s_.l, s_.c, start_t=t0 - 30 * 86400)
                book.add_swing_series(tf, s_.t, s_.tc, s_.h, s_.l, start_t=t0 - 30 * 86400, ref=ref)
        book.set_base(b)
        return book

    def _atr_at(self, i, trig=None):
        """Wilder ATR14 of the base bars at the decision bar (the previous bar on a 1m confirmation inside bar i)."""
        k = i - 1 if (trig is not None and trig.get("ltf_j") is not None and i > 0) else i
        if self._atr_w is not None:
            return float(self._atr_w[k])
        from .liquidity_map import atr14
        return atr14(self.b, k)

    def _draws(self, d, entry, risk, i, h1, trig=None):
        """Every draw on the trade's side (engine pools + map pools + fresh 5m k=2 / 15m k=1 swings + live FVGs)."""
        from .liquidity_map import draws, live_swings
        b, p = self.b, self.p
        tick = self.spec["tick"]
        sw = {"H": [], "L": []}
        ds0 = int(getattr(self, "_day_start", 0))
        per_day = max(1, 82800 // self.secs)            # base bars in one 23h CME day
        hs, ls = live_swings(b.h, b.l, 2, i, (i - ds0) + per_day, tick)   # 5m k=2: confirmed today or yesterday
        sw["H"] += [(px, j, "5m", int(b.t[j])) for px, j in hs]
        sw["L"] += [(px, j, "5m", int(b.t[j])) for px, j in ls]
        mb = self.m15
        last = self._m15_ptr - 1                       # latest CLOSED 15m bar
        if mb is not b and last >= 4:
            hs, ls = live_swings(mb.h, mb.l, 1, last, 5 * 92, tick)     # 15m k=1: the last 5 CME days
            k5 = int(np.searchsorted(b.t, int(mb.t[last]) + 900))
            hi_since = float(b.h[k5:i + 1].max()) if k5 <= i else -1e18
            lo_since = float(b.l[k5:i + 1].min()) if k5 <= i else 1e18
            sw["H"] += [(px, j, "15m", int(mb.t[j])) for px, j in hs if hi_since < px + tick]
            sw["L"] += [(px, j, "15m", int(mb.t[j])) for px, j in ls if lo_since > px - tick]
        return draws(d, entry, risk, self._atr_at(i, trig), int(b.t[i]) + self.secs, self.active, self._lmap, swings=sw,
                     h1_trend=h1.trend, mod=int(b.mod[i]), tick=tick, irl_tfs=p["irl_tfs"], irl_level=p["irl_level"],
                     eq_w=p["draw_eq_w"], day_start_t=int(b.t[ds0]))

    def _pick_draw(self, ds, d, entry, risk, i, open_loc=None):
        """Final target T from the map: reach = max(0.5 x ADR10, ADR10 - today's range) (DOL-4), then the optional trader
        heuristics (B3 one-side cap, B1 strong prior-day extreme), the PM / balance-day nearest caps, then the pick rule."""
        from .liquidity_map import nearest_in_reach, pick_primary
        p, b, tick = self.p, self.b, self.spec["tick"]
        max_dist = None
        ds0 = getattr(self, "_day_start", 0)
        pdays = self._prev_days_ref or []
        if p["draw_reach"] == "playbook":
            last10 = pdays[-10:]
            if last10:
                adr10 = float(np.mean([x["high"] - x["low"] for x in last10]))
                today = float(b.h[ds0:i + 1].max() - b.l[ds0:i + 1].min())
                max_dist = max(0.5 * adr10, adr10 - today)
        if p["draw_one_side"] and pdays and pdays[-1].get("rth_high") is not None:
            # B3: inside 09:30 open and the opposite prior-RTH extreme already taken in RTH -> never target this side's
            # extreme or anything beyond it
            y = pdays[-1]
            rth0 = next((k for k in range(ds0, i + 1) if 570 <= int(b.mod[k]) < 960), None)
            if rth0 is not None and y["rth_low"] <= float(b.o[rth0]) <= y["rth_high"]:
                if d == 1 and float(b.l[rth0:i + 1].min()) <= y["rth_low"] - tick:
                    cap = (y["rth_high"] - entry) - tick
                elif d == -1 and float(b.h[rth0:i + 1].max()) >= y["rth_high"] + tick:
                    cap = (entry - y["rth_low"]) - tick
                else:
                    cap = None
                if cap is not None:
                    max_dist = cap if max_dist is None else min(max_dist, cap)
        if p["draw_pdx"] and len(pdays) >= 2:
            # B1: yesterday closed beyond the day-before's high (low) -> yesterday's high (low) is the draw, unless the
            # opposite extreme has traded first today
            y, pp = pdays[-1], pdays[-2]
            lvl = None
            if d == 1 and y["close"] > pp["high"] and float(b.l[ds0:i + 1].min()) > y["low"] - tick:
                lvl = y["high"]
            elif d == -1 and y["close"] < pp["low"] and float(b.h[ds0:i + 1].max()) < y["high"] + tick:
                lvl = y["low"]
            if lvl is not None:
                dist = (lvl - entry) * d
                x = next((z for z in ds if abs(z["price"] - lvl) < tick / 2 + 1e-9), None)
                if x is not None and dist >= p["draw_alt_min_rr"] * risk and (max_dist is None or dist <= max_dist):
                    return {"primary": x, "why": "B1: yesterday closed beyond its prior extreme", "ev": None,
                            "max_dist": max_dist}
        if p["balance_first"] and open_loc == "inside" and not (p["draw_pm"] == "nearest" and int(b.mod[i]) >= 720):
            x = nearest_in_reach(ds, p["draw_alt_min_rr"], max_dist)
            return {"primary": x, "why": "balance day: nearest draw within reach" if x is not None else
                    f"balance day: no draw >= {p['draw_alt_min_rr']}R within reach", "ev": None, "max_dist": max_dist}
        if p["draw_pm"] == "nearest" and int(b.mod[i]) >= 720:
            # PM entries reach their draws far less often (DRAW_LEARNER.md): cap T at the nearest draw within reach
            x = nearest_in_reach(ds, p["draw_alt_min_rr"], max_dist)
            return {"primary": x, "why": "PM: nearest draw within reach" if x is not None else
                    f"PM: no draw >= {p['draw_alt_min_rr']}R within reach", "ev": None, "max_dist": max_dist}
        pred = _draw_predictor() if p["draw_rank"] == "learned" else None
        prim, why, ev = pick_primary(ds, p["draw_min_rr"], max_dist, p["draw_pick"], p["draw_max_obst"], p["draw_rank"],
                                     pred, p["draw_min_ev"], p["draw_alt_min_rr"])
        return {"primary": prim, "why": why, "ev": ev, "max_dist": max_dist}

    def _open_drive(self, i):
        """TRADER_HEURISTICS T1 opening drive, known from 10:00: +1 up / -1 down / 0. Up = the 09:55 close is >= 0.20 x
        ADR20 above the 09:30 open, the low never went more than 0.05 x ADR20 below the open, and no bar from the 3rd one
        (09:40) touched the open. Down is the mirror."""
        b = self.b
        ds0 = getattr(self, "_day_start", 0)
        adr = getattr(self, "_adr20", None)
        if not adr or int(b.mod[i]) < 600:
            return 0
        k0 = next((k for k in range(ds0, i + 1) if int(b.mod[k]) == 570), None)
        if k0 is None or k0 + 5 > i or int(b.mod[k0 + 5]) != 595:
            return 0
        o, c = float(b.o[k0]), float(b.c[k0 + 5])
        lo, hi = float(b.l[k0:k0 + 6].min()), float(b.h[k0:k0 + 6].max())
        if c - o >= 0.20 * adr and o - lo <= 0.05 * adr and float(b.l[k0 + 2:k0 + 6].min()) > o:
            return 1
        if o - c >= 0.20 * adr and hi - o <= 0.05 * adr and float(b.h[k0 + 2:k0 + 6].max()) < o:
            return -1
        return 0

    def _struct_stop(self, d, s, i, entry, mode="struct_atr"):
        """stop_model 'struct_atr' (playbook STOP-1..3): the sweep extreme (optionally the displacement-origin higher low
        when tighter and valid) - max(2 ticks, stop_atr_buf x ATR14). stop_model 'protected_swing': the swing the
        displacement launched from = the lowest low from the candle before the in-favour run that ends at the trigger,
        through the trigger bar (never beyond the sweep extreme). Never widened to a minimum and never tightened to make
        the numbers work: a stop inside the noise (< min_stop_atr x ATR) or wider than the cap is a pass."""
        b, p, spec = self.b, self.p, self.spec
        tick = spec["tick"]
        atr = self._atr_at(i)
        e_d, ext_d, ext_i = entry * d, s["ext"] * d, int(s["ext_i"])
        buf = max(2 * tick, p["stop_atr_buf"] * atr)
        floor_ = p["min_stop_atr"] * atr
        inval_d, src = ext_d, "sweep extreme"
        if mode == "protected_swing":
            up = lambda j: (b.c[j] - b.o[j]) * d > 0
            ld = (lambda j: float(b.l[j])) if d == 1 else (lambda j: -float(b.h[j]))
            f = i
            while f - 1 > ext_i and up(f - 1):
                f -= 1                                   # first candle of the in-favour run that ends at the trigger
            a0 = max(ext_i, f - 1)
            inval_d = max(ext_d, min(ld(j) for j in range(a0, i + 1)))
            src = "protected swing" if inval_d > ext_d else "protected swing = sweep extreme"
        elif p["stop_origin"] and i - ext_i >= 3:
            ld = (lambda j: float(b.l[j])) if d == 1 else (lambda j: -float(b.h[j]))
            seg = [ld(j) for j in range(ext_i + 1, i + 1)]
            kk = ext_i + 1 + int(np.argmin(seg))
            # a real higher low the displacement launched from: lower than the bar before and the bar after it
            if ext_i + 2 <= kk <= i - 1 and ld(kk) < ld(kk - 1) and ld(kk) <= ld(kk + 1):
                lo = ld(kk)
                if lo - ext_d >= 0.25 * atr and e_d - (lo - buf) >= max(floor_, 2 * tick):
                    inval_d, src = lo, "displacement origin"
        stop_d = inval_d - buf
        risk = e_d - stop_d
        if risk <= 0 or (floor_ and risk < floor_):
            return {"skip": f"Stop {risk:.1f}pts < {p['min_stop_atr']} x ATR {atr:.1f} (inside the noise) - pass", "consume": False}
        cap = spec["max_stop"] if p["stop_cap"] == "spec" else 1e18     # "size": only the n < 1 contract veto in _size
        if p["max_stop_atr"]:
            cap = min(cap, p["max_stop_atr"] * atr)
        if risk > cap:
            return {"skip": f"Stop {risk:.1f}pts > max {cap:.1f} - pass (risk too wide)", "consume": True}
        return {"stop": float(stop_d * d), "risk": float(risk), "atr14": float(atr), "src": src, "inval": float(inval_d * d)}

    def _protected_swing(self, pos, i, d):
        """5m structure for the person trail (playbook D10): a BOS is a close beyond the most recent confirmed (k=2), not yet
        broken swing high; at each BOS the protected low = the lowest low from the broken swing's bar through the BOS bar.
        Returns the highest protected low so far in direction space (None before the first BOS)."""
        b = self.b
        hd = (lambda j: float(b.h[j])) if d == 1 else (lambda j: -float(b.l[j]))
        ld = (lambda j: float(b.l[j])) if d == 1 else (lambda j: -float(b.h[j]))
        st = pos.get("pswing")
        if st is None:
            st = pos["pswing"] = {"sh": None, "sh_k": None, "prot": None}
            e_i = pos["entry_i"]
            for k in range(e_i - 3, max(1, e_i - 60), -1):      # latest swing high confirmed before the entry bar
                hk = hd(k)
                if hk > hd(k - 1) and hk > hd(k - 2) and hk >= hd(k + 1) and hk >= hd(k + 2):
                    if max(float(b.c[j]) * d for j in range(k + 1, e_i)) <= hk:
                        st["sh"], st["sh_k"] = hk, k
                    break
        k = i - 2
        if k >= 2 and k >= pos["entry_i"] - 2:
            hk = hd(k)
            if hk > hd(k - 1) and hk > hd(k - 2) and hk >= hd(k + 1) and hk >= hd(k + 2):
                st["sh"], st["sh_k"] = hk, k
        if st["sh"] is not None and float(b.c[i]) * d > st["sh"]:
            lo = min(ld(j) for j in range(st["sh_k"], i + 1))
            st["prot"] = lo if st["prot"] is None else max(st["prot"], lo)
            st["sh"], st["sh_k"] = None, None
        return st["prot"]

    # ------------------------------------------------------------------ order planning + confluence
    def _plan(self, d, s, trig, i, h1, m15, prof, open_loc, midnight_open):
        b, p, spec = self.b, self.p, self.spec
        tick = spec["tick"]
        c = b.c[i]
        entry = c
        ext = s["ext"]
        if p["no_fade_drive"]:
            drv = self._open_drive(i)
            if drv == -d:
                return {"skip": f"opening drive {'up' if drv == 1 else 'down'} today - never fade it (T1) - pass", "consume": True}
        stop_info = None
        if p["stop_model"] in ("struct_atr", "protected_swing"):
            # structural invalidation + ATR buffer; never widened to a minimum (too tight = inside the noise = pass)
            stop_info = self._struct_stop(d, s, i, entry, p["stop_model"])
            if stop_info.get("skip"):
                return stop_info
            stop, risk = stop_info["stop"], stop_info["risk"]
        else:
            buf = spec["stop_buffer"] * p["stop_buffer_mult"]
            if p["stop_mode"] == "ifvg":
                stop = (trig["inv_low"] - buf) * d   # inv_low is in direction-space
            else:
                stop = ext - d * buf
            # direction-space helpers
            risk = (entry - stop) * d
            if p["fixed_stop_pts"]:
                stop, risk = entry - d * p["fixed_stop_pts"], p["fixed_stop_pts"]
            elif risk < spec["min_stop"]:
                stop = entry - d * spec["min_stop"]
                risk = spec["min_stop"]
            if risk > spec["max_stop"]:
                alt = (trig["inv_low"] - buf) * d
                alt_risk = (entry - alt) * d
                if p["stop_mode"] == "swing" and spec["min_stop"] <= alt_risk <= spec["max_stop"]:
                    stop, risk = alt, alt_risk
                else:
                    return {"skip": f"Stop {risk:.1f}pts > max {spec['max_stop']} - pass (risk too wide)", "consume": True}

        # ---- draw on liquidity
        opp = "H" if d == 1 else "L"
        cands = []
        for q in self.active:
            if q["side"] == opp and (q["price"] - entry) * d > 0:
                cands.append((q["price"], q["label"], q))
        if p["amt_targets"] and prof:
            for key in ("poc", "vah", "val"):
                px = prof[key]
                if (px - entry) * d > 0:
                    cands.append((px, "p" + key.upper(), None))
        cands.sort(key=lambda z: (z[0] - entry) * d)
        target, tlabel, tpool = None, None, None
        tmode = p["target_mode"]
        ds, draw_sel, tp1 = None, None, None
        if self._lmap is not None:
            ds = self._draws(d, entry, risk, i, h1, trig)
        if tmode == "draw":
            # DOL-4: nearest Tier-A draw >= draw_min_rr within reach, else nearest Tier B (or the significance / learned
            # pick); exit draw_exit_ticks before the pool. No R cap. Nothing qualifies -> draw_fallback.
            draw_sel = self._pick_draw(ds, d, entry, risk, i, open_loc)
            pr = draw_sel["primary"]
            if pr is not None:
                pr["target"] = float(pr["price"] - d * p["draw_exit_ticks"] * tick)
                target, tlabel, tpool = pr["target"], f"{pr['label']} (tier {pr['tier']} {pr['source']} draw)", pr["pool"]
            elif p["draw_fallback"] == "skip":
                return {"skip": draw_sel["why"] + " - pass", "consume": True}
            elif p["draw_fallback"] == "2r":
                target, tlabel = entry + d * p["fallback_rr"] * risk, f"{p['fallback_rr']}R ({draw_sel['why']})"
            else:
                tmode = "major"
        qual = [z for z in cands if (z[0] - entry) * d / risk >= p["min_rr"]]
        if tmode == "dol_next" and len(qual) >= 2:
            qual = qual[1:]
        if tmode in ("major", "major_next"):
            qual = [z for z in qual if z[2] is not None and _is_major(z[2])]
            if tmode == "major_next" and len(qual) >= 2:
                qual = qual[1:]
        if tmode == "fixed":
            qual = []
        er10_now = (getattr(self, "_regime_day", None) or {}).get("er10")
        trending_now = bool(p["regime_er10_max"] and er10_now is not None and er10_now > p["regime_er10_max"])
        max_rr = p["max_rr_trending"] if (trending_now and p["max_rr_trending"]) else p["max_rr"]
        if qual and target is None:
            px, lab, q = qual[0]
            r = (px - entry) * d / risk
            if r > max_rr:
                target, tlabel = entry + d * max_rr * risk, f"{max_rr}R cap (toward {lab})" + (" · trending" if max_rr != p["max_rr"] else "")
            else:
                target, tlabel, tpool = px - d * tick, lab, q
        if target is None and p["target_mode"] == "fixed":
            target, tlabel = entry + d * p["fallback_rr"] * risk, f"{p['fallback_rr']}R fixed"
        # first opposing pool on the way (>= 0.75R) - used for pool-based partials
        partial_pool = None
        for px, lab, q in cands:
            if 0.75 <= (px - entry) * d / risk and (target is None or (px - target) * d < 0):
                partial_pool = (float(px - d * tick), lab)
                break
        if target is None:
            if not p["use_fallback"] or p["stop_model"] in ("struct_atr", "protected_swing"):
                return {"skip": "No draw on liquidity with enough room (< min R) - pass", "consume": True}
            target, tlabel = entry + d * p["fallback_rr"] * risk, f"{p['fallback_rr']}R (no DOL)"
        # TP1 (DOL-5): nearest internal draw (live FVG / Tier B-C pool) in [irl_min_r x R, T); a gap exits at its near
        # edge, a pool 2 ticks before it. manage_mode "person" takes the partial there.
        partial_draw = None
        if ds is not None:
            from .liquidity_map import pick_partial
            tp1 = pick_partial(ds, (target - entry) * d, p["irl_min_r"], risk, p["irl_partial_src"])
            if tp1 is not None:
                tp1["target"] = float(tp1["price"] if tp1["is_gap"] else tp1["price"] - d * 2 * tick)
                if (tp1["target"] - entry) * d <= 0:
                    tp1 = None
            if p["manage_mode"] == "person":
                partial_draw = tp1
        # DOL-6 skip rules (draw mode only; both off by default)
        if p["target_mode"] == "draw" and ds is not None:
            if p["draw_block_r"] > 0:
                blk = [g for g in self._lmap.gaps(-d, {"1h", "4h"})
                       if (g["ce"] - entry) * d > 0 and ((g["bot"] if d == 1 else g["top"]) - entry) * d <= p["draw_block_r"] * risk]
                if blk:
                    g = blk[0]
                    return {"skip": f"live {g['tf']} FVG {g['bot']:.2f}-{g['top']:.2f} blocks the path within "
                                    f"{p['draw_block_r']}R - pass", "consume": True}
            pr = draw_sel["primary"] if draw_sel else None
            if p["draw_hrlr"] == "tp1" and pr is not None and pr["obstacles"] >= 3:
                if tp1 is not None and (tp1["target"] - entry) * d >= p["draw_min_rr"] * risk:
                    target, tlabel, tpool = tp1["target"], f"{tp1['label']} (HRLR: all out at TP1)", tp1["pool"]
                    partial_draw = None
                else:
                    return {"skip": f"high-resistance path ({pr['obstacles']} obstacles to {pr['source']}) and TP1 "
                                    f"< {p['draw_min_rr']}R - pass", "consume": True}

        # ---- confluence
        tags, score = [], 0
        if h1.trend == d:
            score += p["w_htf"]; tags.append("HTF trend")
        elif h1.trend == -d:
            score -= p["w_htf"]; tags.append("counter-HTF")
        prot = h1.protected_low if d == 1 else h1.protected_high
        if prot is not None and (ext - prot) * d > 0 and h1.trend == d:
            score += p["w_protected"]; tags.append("protected " + ("low" if d == 1 else "high") + " intact")
        # LRL / HRL: unswept opposing swings between entry and target
        obstacles = 0
        for q in self.active:
            if q["side"] == opp and q["kind"] in ("ITH", "ITL", "H1H", "H1L") and q is not tpool:
                dist = (q["price"] - entry) * d
                if 0 < dist < (target - entry) * d:
                    obstacles += 1
        if obstacles <= 1:
            score += p["w_lrl"]; tags.append(f"LRL ({obstacles} obstacles)")
        elif obstacles >= 3:
            score -= p["w_lrl"]; tags.append(f"HRL ({obstacles} obstacles)")
        if prof:
            discount = (prof["poc"] - ext) * d >= 0
            accept = open_loc == ("above" if d == 1 else "below") and (c - (prof["vah"] if d == 1 else prof["val"])) * d > 0
            if discount or accept:
                score += p["w_amt"]
                tags.append("AMT " + (("discount" if d == 1 else "premium") + " vs POC" if discount else "acceptance outside value"))
        smt = self._smt(d, s, i)
        if smt:
            score += p["w_smt"]; tags.append("SMT divergence")
        quality = max(q["strength"] for q in s["pools"]) >= 2
        if quality:
            score += p["w_quality"]; tags.append("quality pool")

        # ---- multi-timeframe confluence
        bias = self.mtf.bias() if self.mtf is not None else {"1D": 0, "4H": 0, "1H": 0, "15m": 0}
        mtf_net = sum(v * d for v in bias.values())
        if mtf_net >= 2:
            score += p["w_mtf"]; tags.append(f"MTF aligned {mtf_net:+d}")
        elif mtf_net <= -2:
            score -= p["w_mtf"]; tags.append(f"MTF against {mtf_net:+d}")
        if m15.trend == d:
            score += p["w_m15"]; tags.append("15m already aligned (late)" if p["w_m15"] < 0 else "15m structure")
        pd_v, pd_pos = 0, None
        if h1.lsh is not None and h1.lsl is not None and h1.lsh > h1.lsl:
            pd_pos = (ext - h1.lsl) / (h1.lsh - h1.lsl)
            fav = pd_pos <= 0.5 if d == 1 else pd_pos >= 0.5
            pd_v = 1 if fav else -1
            if fav:
                score += p["w_pd"]; tags.append(("discount" if d == 1 else "premium") + f" {pd_pos * 100:.0f}% of 1H range")
        mid_v = 0
        if midnight_open is not None:
            mid_v = 1 if (midnight_open - ext) * d > 0 else -1
            if mid_v > 0:
                score += p["w_midnight"]; tags.append(("below" if d == 1 else "above") + " midnight open")
        key = self.mtf.keylevel(d, ext, spec["stop_buffer"] * 2) if self.mtf is not None else None
        if key:
            score += p["w_keylevel"]; tags.append(f"HTF key level {key}")
        if trig.get("tf") == "15m":
            tags.append("15m IFVG")
        # ---- draw on liquidity (higher-timeframe): where is the nearest MAJOR untaken liquidity?
        up = [q["price"] - entry for q in self.active if q["side"] == "H" and q["price"] > entry and _is_major(q)]
        dn = [entry - q["price"] for q in self.active if q["side"] == "L" and q["price"] < entry and _is_major(q)]
        near_up, near_dn = (min(up) if up else None), (min(dn) if dn else None)
        dol_dir = 0
        if near_up is not None and near_dn is not None:
            dol_dir = 1 if near_up < near_dn else -1
        elif near_up is not None or near_dn is not None:
            dol_dir = 1 if near_up is not None else -1
        dol_align = int(dol_dir == d)
        room = (near_up if d == 1 else near_dn)
        dol_room_r = round(room / risk, 2) if room else 0.0
        tgt_major = int(tpool is not None and _is_major(tpool))
        if dol_align:
            score += p["w_dol"]; tags.append("toward nearest major liquidity")

        # ---- Quarterly Theory / AMD / gamma
        def q90(m):
            for st in (360, 720):          # NY AM 06:00-12:00, NY PM 12:00-18:00 sessions
                if st <= m < st + 360:
                    return ("AM" if st == 360 else "PM"), int((m - st) // 90) + 1, st + int((m - st) // 90) * 90
            return None, 0, None
        e_sess, e_q, e_qs = q90(int(b.mod[i]))
        s_sess, s_q, _ = q90(int(b.mod[s["arm_i"]]))
        e_micro = int((int(b.mod[i]) - e_qs) // 22.5) + 1 if e_qs is not None else 0
        tz = self._tz
        side = lambda ref: 0 if ref is None else (1 if (ref - ext) * d > 0 else -1)   # +1 = sweep on the "manipulation" side
        gx = self._gex.get(b.date_str[i], {})
        qt = {
            "q90_entry": e_q, "q90_sweep": s_q, "micro_entry": e_micro,
            "qt_q2_sweep": int(s_q == 2), "qt_q2q3": int(s_q == 2 and e_q == 3 and s_sess == e_sess),
            "qt_entry_q3": int(e_q == 3), "qt_micro_23": int(e_micro in (2, 3)),
            "amd_day_open": side(tz["day"]), "qt_session_open": side(tz.get(e_sess)) if e_sess else 0,
            "qt_90_open": side(tz["micro"].get(e_qs)) if e_qs is not None else 0, "qt_week_open": side(tz["week"]),
            "gex_bn": round(float(gx["gex_bn"]), 2) if gx.get("gex_bn") == gx.get("gex_bn") and gx else None,
            "gex_pct": round(float(gx["gex_pct"]), 1) if gx and gx.get("gex_pct") == gx.get("gex_pct") else None,
            "dix": round(float(gx["dix"]), 4) if gx else None,
        }
        qt["gex_low"] = int(qt["gex_pct"] is not None and qt["gex_pct"] < 25)
        qt["gex_high"] = int(qt["gex_pct"] is not None and qt["gex_pct"] >= 75)
        qt["gex_neg"] = int(qt["gex_bn"] is not None and qt["gex_bn"] < 0)
        if qt["qt_q2q3"]:
            tags.append("QT: Q2 manipulation -> Q3 entry")
        if qt["amd_day_open"] > 0:
            tags.append("PO3: raid beyond daily open")
        if qt["gex_bn"] is not None:
            tags.append(f"GEX {qt['gex_bn']:+.1f}bn ({qt['gex_pct']:.0f}th pct)" if qt["gex_pct"] is not None else f"GEX {qt['gex_bn']:+.1f}bn")

        nst = self._news_state(int(b.t[i]), b.date_str[i])
        if nst["in_window"]:
            tags.append(f"news window: {nst['event']}")
        elif nst["day_events"]:
            tags.append("news day: " + ", ".join(sorted(set(nst["day_events"])))[:60])

        # ---- raid / displacement / participation confluences
        k0 = max(0, i - 14)
        tr_ = np.maximum(b.h[k0:i + 1], np.r_[b.c[max(0, k0 - 1)], b.c[k0:i]]) - np.minimum(b.l[k0:i + 1], np.r_[b.c[max(0, k0 - 1)], b.c[k0:i]])
        atr = float(tr_.mean()) if len(tr_) else risk
        pool_px = s["pools"][0]["price"]
        depth = (pool_px - ext) * d                      # how far price ran past the first swept pool
        depth_atr = depth / atr if atr else 0.0
        body = abs(b.c[i] - b.o[i])
        disp = body / atr if atr else 0.0
        reclaim_bars = i - s["ext_i"]
        sweep_i = s["arm_i"]
        vavg = float(b.v[max(0, sweep_i - 20):sweep_i].mean()) if sweep_i > 0 else 0.0
        vmax = float(b.v[sweep_i:s["ext_i"] + 1].max()) if s["ext_i"] >= sweep_i else float(b.v[sweep_i])
        vol_climax = int(vavg > 0 and vmax >= 1.5 * vavg)
        vwap = self._vw[0] / self._vw[1] if self._vw[1] > 0 and self._vw[2] == int(b.tday[i]) else None
        vwap_disc = 0 if vwap is None else (1 if (vwap - entry) * d > 0 else -1)   # long below VWAP / short above
        extra = {
            "shallow_raid": int(depth_atr <= 0.5), "deep_raid": int(depth_atr >= 1.5),
            "disp_strong": int(disp >= 1.0), "fast_reclaim": int(reclaim_bars <= 3),
            "first_hour": int(570 <= int(b.mod[i]) < 630), "multi_sweep": int(len(s["pools"]) >= 2),
            "major_swept": int(any(_is_major(q) for q in s["pools"])), "vol_climax": vol_climax, "vwap_disc": vwap_disc,
        }
        for key, w_key, label in (("disp_strong", "w_disp", "strong displacement"), ("fast_reclaim", "w_fast", "fast reclaim"),
                                  ("multi_sweep", "w_multi", "stacked liquidity raid"), ("major_swept", "w_major", "major pool raided"),
                                  ("vol_climax", "w_vol", "volume climax on raid"), ("shallow_raid", "w_shallow", "shallow raid"),
                                  ("first_hour", "w_first", "first hour")):
            if extra[key] > 0:
                if p[w_key]:
                    score += p[w_key]
                tags.append(label)
        if extra["vwap_disc"] > 0:
            score += p["w_vwap"]; tags.append(("below" if d == 1 else "above") + " session VWAP")

        # ---- discovery batch: many cheap candidate confluences, recorded on every candidate for the discovery scan
        labels = " ".join(q["label"] for q in s["pools"])
        mod_i = int(b.mod[i])
        sess_start = 570 if mod_i < 720 else 810
        rng_i = float(b.h[i] - b.l[i]) or 1e-9
        close_pos = (float(b.c[i] - b.l[i]) / rng_i) if d == 1 else (float(b.h[i] - b.c[i]) / rng_i)
        vavg_i = float(b.v[max(0, i - 20):i].mean()) if i > 0 else 0.0
        today_trades = [t for t in self.trades if t.get("entry_i", -1) >= getattr(self, "_day_start", 0)]
        pd_ = self._prev_days_ref[-1] if self._prev_days_ref else None
        sess = getattr(self, "_sess", {}) or {}
        on = sess.get("ON")
        adr = getattr(self, "_adr20", None)
        zone = trig.get("zone") or [0, 0]
        disc = {
            "x_swept_pd": int("PDH" in labels or "PDL" in labels), "x_swept_on": int("ONH" in labels or "ONL" in labels),
            "x_swept_asia": int("ASH" in labels or "ASL" in labels), "x_swept_london": int("LOH" in labels or "LOL" in labels),
            "x_swept_h1": int("H1H" in labels or "H1L" in labels), "x_swept_eq": int("EQ" in labels), "x_swept_pw": int("PWH" in labels or "PWL" in labels),
            "x_minor_only": int(all(q["kind"] in ("ITH", "ITL") and not q["eq"] for q in s["pools"])),
            "x_strong_close": int(close_pos >= 0.75), "x_weak_close": int(close_pos <= 0.4),
            "x_trigger_vol_hi": int(vavg_i > 0 and float(b.v[i]) >= 1.5 * vavg_i),
            "x_early_session": int(mod_i - sess_start < 45), "x_late_session": int(mod_i - sess_start >= 90),
            "x_monday": int(b.dow[i] == 0), "x_friday": int(b.dow[i] == 4), "x_midweek": int(b.dow[i] in (1, 2, 3)),
            "x_after_loss": int(any(t["pnl"] <= 0 for t in today_trades)), "x_second_trade": int(len(today_trades) >= 1),
            "x_tight_stop": int(risk / atr <= 1.0) if atr else 0, "x_wide_stop": int(risk / atr >= 2.5) if atr else 0,
            "x_big_ifvg": int(abs(zone[1] - zone[0]) / atr >= 0.6) if atr else 0,
            "x_far_target": int(adr is not None and abs(target - entry) / adr >= 0.5),
            "x_near_target": int(adr is not None and abs(target - entry) / adr <= 0.2),
            "x_vwap_far": int(vwap is not None and atr and abs(entry - vwap) / atr >= 3),
            "x_poc_side": 0 if not prof else (1 if (prof["poc"] - entry) * d > 0 else -1),
            "x_pd_mid_side": 0 if not pd_ else (1 if ((pd_["high"] + pd_["low"]) / 2 - entry) * d > 0 else -1),
            "x_pd_weak_close": 0 if not pd_ or pd_["high"] <= pd_["low"] else int(
                ((pd_["close"] - pd_["low"]) / (pd_["high"] - pd_["low"]) <= 0.3) if d == 1 else ((pd_["high"] - pd_["close"]) / (pd_["high"] - pd_["low"]) <= 0.3)),
            "x_inside_day": int(len(self._prev_days_ref) >= 2 and self._prev_days_ref[-1]["high"] <= self._prev_days_ref[-2]["high"]
                                and self._prev_days_ref[-1]["low"] >= self._prev_days_ref[-2]["low"]),
            "x_on_wide": int(bool(on) and adr is not None and on[0] > -1e17 and (on[0] - on[1]) / adr >= 0.6),
            "x_on_narrow": int(bool(on) and adr is not None and on[0] > -1e17 and (on[0] - on[1]) / adr <= 0.3),
            "x_with_day": int((float(b.c[i]) - float(b.o[getattr(self, '_day_start', i)])) * d > 0),
            "x_cisd_trigger": int(trig["type"] == "CISD"), "x_long": int(d == 1), "trend_model": int(trig["type"] == "CONT"),
        }
        if p["skip_london"] and disc["x_swept_london"]:
            return {"skip": "raid was the London high/low - pass (stable negative edge)", "consume": True}
        b_mod = int(b.mod[i])
        rr_plan = (target - entry) * d / risk
        if p["counter_rr_cap"] and mtf_net <= -2 and rr_plan > p["counter_rr_cap"]:
            # fading higher-timeframe order flow: bank the first draw instead of running for the HTF pool
            target = entry + d * p["counter_rr_cap"] * risk
            tlabel = f"{p['counter_rr_cap']}R (counter-HTF cap)"
            rr_plan = p["counter_rr_cap"]
            tags.append("counter-HTF: quick target")
        features = {
            "htf_trend": h1.trend * d, "protected": int(any(t.startswith("protected") for t in tags)),
            "lrl": int(obstacles <= 1), "hrl": int(obstacles >= 3), "amt": int(any(t.startswith("AMT") for t in tags)),
            "smt": int(bool(smt)), "quality": int(quality), "m15_trend": m15.trend * d,
            "b_1D": bias["1D"] * d, "b_4H": bias["4H"] * d, "b_1H": bias["1H"] * d, "b_15m": bias["15m"] * d,
            "mtf_net": mtf_net, "pd": pd_v, "midnight": mid_v, "keylevel": int(bool(key)),
            "trig_15m": int(trig.get("tf") == "15m"), "cisd": int(trig["type"] == "CISD"), "pm": int(b_mod >= 780),
            "rr_plan": round(rr_plan, 2), "obstacles": obstacles,
            "pd_pos": None if pd_pos is None else round(pd_pos, 3),
            "dol_align": dol_align, "tgt_major": tgt_major, "dol_room_r": dol_room_r, "dol_room3": int(dol_room_r >= 3),
            **extra, "depth_atr": round(depth_atr, 2), "disp_atr": round(disp, 2), "reclaim_bars": int(reclaim_bars),
            "news_win": int(nst["in_window"]), "news_day": int(bool(nst["day_events"])), "fomc_day": int(nst["fomc_day"]),
            "vix_prev": nst["vix"] or 0.0, "vix_hi": int(bool(nst["vix"]) and nst["vix"] >= 20),
            **qt, **self._regime_now(i, d), **disc,
        }
        grade, gmult, checklist, gpts = self._grade(features, i, d)
        if trig["type"] == "CONT":
            tags = ["trend-day continuation"] + tags
        sig_ext = float(b.l[i]) if d == 1 else float(b.h[i])     # trigger candle's extreme: closing back through it = warning
        order = {"grade": grade, "grade_mult": gmult, "checklist": checklist, "grade_points": gpts, "model": "trend" if trig["type"] == "CONT" else "sweep",
                 "dir": d, "stop": float(stop), "target": float(target), "target_label": tlabel, "score": score,
                 "conf_tags": tags, "trigger": trig["type"], "trigger_tf": trig.get("tf"), "signal_t": int(b.t[i]),
                 "signal_price": float(c), "pools": [q["label"] for q in s["pools"]], "sweep_ext": float(ext),
                 "zone": trig["zone"], "htf_trend": h1.trend, "m15_trend": m15.trend, "open_loc": open_loc,
                 "features": features, "mtf_bias": bias, "pd_pos": None if pd_pos is None else round(pd_pos, 3),
                 "midnight_open": midnight_open, "key_level": key, "risk_pts_plan": float(risk), "partial_pool": partial_pool,
                 "sig_ext": sig_ext}
        if p["entry_mode"] == "retest":
            # rest a limit at the trigger zone (IFVG near edge or CE; the CISD level); size on the limit-to-stop risk
            top_d, bot_d = float(trig["top"]), float(trig["bot"])
            lvl_d = (top_d + bot_d) / 2 if (p["retest_level"] == "ce" and trig["type"] != "CISD") else top_d
            lim = min(lvl_d, float(c) * d) * d               # never a worse price than the signal close
            risk_l = (lim - stop) * d
            if risk_l <= 2 * tick or (target - lim) * d <= 0:
                return {"skip": f"retest limit {lim:.2f} not beyond the stop {float(stop):.2f} - pass", "consume": True}
            order.update({"limit": float(lim), "risk_pts_plan": float(risk_l), "retest_bars": int(p["retest_bars"]),
                          "limit_exp": int(i + p["retest_bars"]), "limit_tday": int(b.tday[i])})
            tags.append(f"retest limit {lim:.2f} ({p['retest_bars']} bars)")
        if stop_info is not None or ds is not None:
            # discretionary layer: what the stop / target / partial were built from (trade records + events)
            from .liquidity_map import compact
            order["stop_src"] = stop_info["src"] if stop_info else p["stop_mode"]
            order["atr14"] = round(stop_info["atr14"], 2) if stop_info else None
            order["draw"] = compact(draw_sel["primary"]) if draw_sel else None
            order["partial_draw"] = compact(partial_draw)
            if draw_sel and draw_sel.get("ev") is not None:
                order["draw_ev"] = round(float(draw_sel["ev"]), 3)
            if partial_draw is not None:
                tags.append(f"partial @ {partial_draw['label']} ({partial_draw['dist_r']:.1f}R)")
            if draw_sel and draw_sel["primary"] is not None:
                pr = draw_sel["primary"]
                tags.append(f"draw {pr['source']}{' EQ' if pr['eq'] else ''} {pr['dist_r']:.1f}R, {pr['obstacles']} obstacles")
        return order

    # ------------------------------------------------------------------ discretionary-style trade grade
    GRADES = [("A+", 7, 1.5), ("A", 5, 1.25), ("B", 3, 1.0), ("C", 1, 0.75), ("D", -99, 0.5)]

    def _grade(self, f, i, d):
        """Checklist of everything the research learned, weighted by how well it held up. Returns grade, size x, items."""
        b = self.b
        ratio = None
        if getattr(self, "_adr20", None):
            ds = getattr(self, "_day_start", 0)
            ratio = float(b.h[ds:i + 1].max() - b.l[ds:i + 1].min()) / self._adr20
        items = [
            # (label, state +1 for / -1 against / 0 neutral, weight, evidence class)
            ("1H structure with the trade", f["htf_trend"], 2 if f["htf_trend"] > 0 else 1, "proven"),
            ("Sweep in discount / premium of 1H range", f["pd"], self.p["g_pd"], "proven"),
            ("Raid not on the London high / low", -1 if f.get("x_swept_london") else 1, self.p["g_london"] if f.get("x_swept_london") else 0, "discovered"),
            ("Entry on the value side of session VWAP", f.get("vwap_disc", 0), 2, "proven"),
            ("No volume climax on the raid", -1 if f.get("vol_climax") else 1, 2 if f.get("vol_climax") else 0, "proven"),
            ("Clear path to target (LRL)", 1 if f["lrl"] else (-1 if f["hrl"] else 0), 2 if f["hrl"] else 1, "proven"),
            ("Not the opening hour", -1 if f.get("first_hour") else 1, 1 if f.get("first_hour") else 0, "partial"),
            ("15m structure not already turned", -1 if f["m15_trend"] > 0 else 1, 1 if f["m15_trend"] > 0 else 0, "partial"),
            ("Quarterly Theory: Q2 manipulation", 1 if f.get("qt_q2_sweep") else 0, 1, "partial"),
            ("Raid beyond the 90-min true open", f.get("qt_90_open", 0), 1, "partial"),
            ("Day not already stretched (<1.2x ADR)", 0 if ratio is None else (1 if ratio < 1.2 else -1), 0 if ratio is None or ratio < 1.2 else 1, "partial"),
            ("No high-impact news today", -1 if f.get("news_day") else 1, 0, "context"),
            ("Dealer gamma positive (prior day)", 0 if f.get("gex_bn") is None else (1 if f["gex_bn"] > 0 else -1), 0, "context"),
            ("VIX below 20", 0 if not f.get("vix_prev") else (1 if f["vix_prev"] < 20 else -1), 0, "context"),
            ("AMD: raid beyond the daily open", f.get("amd_day_open", 0), 0, "context"),
            # discovery-scan additions (sizing only - they never block a trade, so frequency is unchanged)
            ("Raid not on a 1H swing (session/day pool instead)", -1 if f.get("x_swept_h1") else 1, self.p["g_h1sweep"] if f.get("x_swept_h1") else 0, "discovered"),
            ("Past the first 45 minutes of the session", -1 if f.get("x_early_session") else 1, self.p["g_early"] if f.get("x_early_session") else 0, "discovered"),
            ("Single clean raid (not stacked)", -1 if f.get("multi_sweep") else 1, self.p["g_stacked"] if f.get("multi_sweep") else 0, "discovered"),
            ("Q2 sweep, not a Q3 entry", -1 if f.get("qt_entry_q3") else 0, self.p["g_q3"], "discovered"),
        ]
        pts = sum(s * w for _, s, w, _ in items)
        grade, mult = next((g, m) for g, th, m in self.GRADES if pts >= th)
        checklist = [{"label": lab, "state": int(s), "weight": w, "evidence": ev} for lab, s, w, ev in items]
        return grade, mult, checklist, int(pts)

    def _size(self, order, balance, mll_level):
        """Prop-aware sizing in micros (MFFU 50K: max 40 micros / 4 minis). Mutates and returns the order."""
        p, spec = self.p, self.spec
        risk = order["risk_pts_plan"]
        risk_usd = p["risk_usd"]
        cushion = balance - mll_level
        if p["risk_mode"] == "cushion":
            # risk a fixed fraction of the distance to the trailing max-loss level: shrinks after losses,
            # grows once the MLL locks and profits build (faster final leg to the target)
            risk_usd = min(p["risk_max"], max(p["risk_min"], cushion * p["cushion_frac"]))
            risk_usd = min(risk_usd, max(0.0, cushion * 0.35))   # never more than 35% of the remaining cushion
        elif p["dd_aware"]:
            risk_usd = min(risk_usd, max(0.0, cushion * p["cushion_frac"]))
        if p["grade_sizing"]:
            if p["grade_skip"] and order["grade"] in [g.strip() for g in p["grade_skip"].split(",")]:
                return {"skip": f"Grade {order['grade']} ({order['grade_points']} pts) - pass", "consume": False}
            risk_usd *= order["grade_mult"]
            order["conf_tags"] = order["conf_tags"] + [f"grade {order['grade']} · size ×{order['grade_mult']}"]
        elif p["conviction_step"] > 0:
            # conviction sizing from sign-stable confluences: +VWAP-side, -volume climax, -first hour, -major-pool raid
            f = order["features"]
            conv = (1 if f.get("vwap_disc", 0) > 0 else 0) - f.get("vol_climax", 0) - f.get("first_hour", 0) \
                - (f.get("major_swept", 0) if p["conviction_major"] else 0)
            mult = min(p["conviction_max"], max(p["conviction_min"], 1 + p["conviction_step"] * conv))
            risk_usd *= mult
            order["conviction"] = conv
            order["conf_tags"] = order["conf_tags"] + [f"size ×{mult:.2f} (conviction {conv:+d})"]
        if p["risk_ref_stop"] and risk > p["risk_ref_stop"]:
            # de-risk wide stops: full risk up to the reference stop, then risk shrinks in proportion (owner rule)
            risk_usd *= p["risk_ref_stop"] / risk
            order["conf_tags"] = order["conf_tags"] + [f"wide stop {risk:.0f} pts: risk ${risk_usd:.0f}"]
        if order.get("regime") == "trending" and p["regime_mode"] == "half" and not (order.get("model") == "trend" and p["trend_full_size"]):
            risk_usd *= 0.5
            order["conf_tags"] = order["conf_tags"] + ["trending regime: half size"]
        if p["lock_boost"] > 1 and mll_level >= p["mll_lock"]:
            # MLL has locked (balance >= start + $2.1k): the account can absorb more, press toward the target
            risk_usd = min(risk_usd * p["lock_boost"], max(0.0, cushion * 0.35))
        micros = int(risk_usd // (risk * spec["micro_pv"]))
        mode = p["contract"]
        if mode == "mini":
            minis = min(4, int(risk_usd // (risk * spec["mini_pv"])))
            micros = minis * 10
        micros = min(micros, p["max_micros"])
        if micros < 1:
            return {"skip": f"Risk ${risk_usd:.0f} too small for a {risk:.1f}pt stop - pass", "consume": True}
        minis, rem = (micros // 10, micros % 10) if mode != "micro" else (0, micros)
        sym = self.sym
        qty_label = " + ".join(x for x in [f"{minis} {sym}" if minis else "", f"{rem} M{sym}" if rem else ""] if x)
        order.update({"qty": micros, "minis": minis, "micros": rem, "qty_label": qty_label,
                      "risk_usd_plan": round(micros * risk * spec["micro_pv"], 2)})
        return order

    def _shadow_step(self, sh, i, o, h, l, c, mod, tday, n):
        """Advance one virtual (shadow) trade by a bar. Returns True once it is resolved."""
        p, tick, b = self.p, self.spec["tick"], self.b
        d = sh["dir"]
        slip = p["slippage_ticks"] * tick
        if sh["entry"] is None:
            if i <= sh["sig_i"]:
                return False
            fill = o + d * slip
            risk = (fill - sh["stop"]) * d
            if risk <= 0 or (sh["target"] - fill) * d <= 0:
                sh["r"] = None
                return True
            sh["entry"], sh["risk"] = fill, risk
        low_d, high_d = (l, h) if d == 1 else (-h, -l)
        px = None
        if low_d <= sh["stop"] * d:
            px = (min(o * d, sh["stop"] * d) - slip) * d
        elif high_d >= sh["target"] * d + p["touch_ticks"] * tick:
            px = sh["target"]
        elif mod >= p["flat_mod"] or (i + 1 < n and b.tday[i + 1] != tday) or (i == n - 1 and not p["live"]):
            px = c - d * slip
        if px is None:
            return False
        sh["r"] = round((px - sh["entry"]) * d / sh["risk"], 3)
        sh["exit_t"] = int(b.t[i])
        return True

    def _smt(self, d, s, i):
        if self.partner is None:
            return False
        b, pb, idx = self.b, self.partner, self.partner_idx
        W = 36
        a0 = max(0, s["arm_i"] - W)
        ja = idx.get(int(b.t[a0])); js = idx.get(int(b.t[s["arm_i"]])); je = idx.get(int(b.t[i]))
        if ja is None or js is None or je is None or js <= ja or je < js:
            return False
        if d == 1:
            return pb.l[js:je + 1].min() > pb.l[ja:js].min()
        return pb.h[js:je + 1].max() < pb.h[ja:js].max()

    # ------------------------------------------------------------------ in-trade exit signals (learned)
    EXIT_SIGNALS = {
        "opp_disp": "Displacement candle against the trade (body >= 1 ATR)",
        "trig_break": "Close back through the trigger candle's extreme",
        "giveback": "Was +0.5R, now closing below entry",
        "stall": "No new high-water mark for 30 min while under +1R",
        "zone_reentry": "Close back inside the inverted FVG",
        "zone_fail": "Close through the far side of the inverted FVG",
        "opp_fvg": "Opposing FVG forms against the trade",
        "m15_flip": "15m structure flips against the trade",
        "two_against": "Two consecutive momentum closes against",
        "vol_against": "Volume climax (2x) on a candle against",
        "cisd_disp": "Opposing CISD with displacement (body >= 1 ATR and 60% of range, or a gap)",
    }

    def _cisd_against(self, pos, i, o, h, l, c):
        """DOL playbook MGMT-5 / D11: bar i closes beyond the OPEN of the first candle of the latest in-favour delivery
        series (a maximal run of in-favour candles that started after entry), its body is >= 50% of its range, and it is
        a displacement candle (body >= 1 ATR and >= 60% of range) or it leaves an opposing 5m FVG."""
        b, d = self.b, pos["dir"]
        e_i = pos["entry_i"]
        rng = float(h - l)
        body = float(o - c) * d                     # > 0: the candle closes against the trade
        if i - e_i < 1 or rng <= 0 or body <= 0 or body < 0.5 * rng:
            return False
        up = lambda j: (b.c[j] - b.o[j]) * d > 0
        j = i - 1
        while j >= e_i and not up(j):
            j -= 1
        if j < e_i:
            return False
        f = j
        while f - 1 >= e_i and up(f - 1):
            f -= 1
        if f == e_i and e_i >= 1 and up(e_i - 1):
            return False                            # the series started before the entry
        if not (c * d < b.o[f] * d):
            return False
        atr = float(self._atr_w[i]) if getattr(self, "_atr_w", None) is not None else (pos.get("atr") or pos["risk_pts"])
        disp = body >= 1.0 * atr and body >= 0.6 * rng
        gap = i >= 2 and ((b.h[i] < b.l[i - 2]) if d == 1 else (b.l[i] > b.h[i - 2]))
        return bool(disp or gap)

    def _exit_signals(self, pos, i, o, h, l, c, m15):
        """Evaluate every warning sign on this bar; log the first firing with the R we'd bank by leaving here."""
        b, p, d = self.b, self.p, pos["dir"]
        e, risk, atr = pos["entry"], pos["risk_pts"], pos["atr"] or pos["risk_pts"]
        k = i - pos["entry_i"]
        c_d, o_d, e_d = c * d, o * d, e * d
        zone = pos.get("zone") or [0, 0]
        sig = pos.get("sig_ext")
        now = {
            "opp_disp": (o - c) * d >= 1.0 * atr,
            "trig_break": sig is not None and (c - sig) * d < 0,
            "giveback": pos["mfe"] >= p["exit_giveback_r"] and c_d < e_d,
            "stall": pos["mfe"] < 1.0 and (i - pos["mfe_i"]) >= p["exit_stall_bars"],
            "zone_reentry": zone[0] <= c <= zone[1],
            "zone_fail": (c - zone[0 if d == 1 else 1]) * d < 0,
            "opp_fvg": k >= 2 and ((b.h[i] < b.l[i - 2]) if d == 1 else (b.l[i] > b.h[i - 2])),
            "m15_flip": m15.trend == -d and pos.get("m15_entry") != -d,
            "two_against": k >= 2 and (c - b.l[i - 1]) * d < 0 and (b.c[i - 1] - b.l[i - 2]) * d < 0 if d == 1 else
                           k >= 2 and (c - b.h[i - 1]) * d < 0 and (b.c[i - 1] - b.h[i - 2]) * d < 0,
            "vol_against": (c - o) * d < 0 and i > 20 and b.v[i] >= 2.0 * float(b.v[i - 20:i].mean()),
        }
        if getattr(self, "_cisd_on", False):
            now["cisd_disp"] = self._cisd_against(pos, i, o, h, l, c)
        slip_r = p["slippage_ticks"] * self.spec["tick"] / risk
        fired = []
        for name, on in now.items():
            if on and name not in pos["xsig"]:
                pos["xsig"][name] = {"k": int(k), "r": round((c_d - e_d) / risk - slip_r, 3), "mfe": round(pos["mfe"], 2)}
                fired.append(name)
        return fired

    def _exit_active(self, fired):
        """Which freshly fired signal (if any) should we act on: a fixed rule, or one the walk-forward stats have proven."""
        if not fired:
            return None
        p = self.p
        rules = {s.strip() for s in p["exit_rules"].split(",") if s.strip()}
        for name in fired:
            if name in rules:
                return name
            if p["exit_learn"]:
                g = self._xstats.get(name, [])
                if len(g) >= p["exit_learn_min"] and float(np.mean(g)) >= p["exit_learn_threshold"]:
                    return name
        return None

    def exit_signal_summary(self):
        out = []
        for name, label in self.EXIT_SIGNALS.items():
            g = self._xstats.get(name, [])
            acted = sum(1 for t in self.trades if t.get("exit_signal") == name)
            if not g and not acted:
                continue
            arr = np.array(g) if g else np.array([0.0])
            out.append({"key": name, "label": label, "n": len(g), "acted": acted, "seeded": self._xseed_n.get(name, 0),
                        "avg_gain": round(float(arr.mean()), 3) if g else None,
                        "helped": round(float((arr > 0.1).mean()), 3) if g else None, "hurt": round(float((arr < -0.1).mean()), 3) if g else None,
                        "total_gain": round(float(arr.sum()), 2) if g else None,
                        "learned": bool(g) and len(g) >= self.p["exit_learn_min"] and float(arr.mean()) >= self.p["exit_learn_threshold"]})
        rules = {s.strip() for s in self.p["exit_rules"].split(",") if s.strip()}
        out.sort(key=lambda x: (0 if x["key"] in rules else 1, -(x["avg_gain"] if x["avg_gain"] is not None else -9)))
        return out

    # ------------------------------------------------------------------ fills / bookkeeping
    def _exit(self, pos, qty, px, t, reason):
        d = pos["dir"]
        pts = (px - pos["entry"]) * d
        pos["exits"].append({"t": int(t), "qty": int(qty), "price": float(px), "reason": reason, "pts": round(pts, 2)})
        pos["remaining"] -= qty
        pos["exit_reason"] = reason

    def _close(self, pos, i, px, reason):
        if pos["remaining"] > 0:
            self._exit(pos, pos["remaining"], px, self.b.t[i], reason)
        self._finalize(pos, i)

    def _finalize(self, pos, i):
        spec = self.spec
        gross = sum(e["pts"] * e["qty"] for e in pos["exits"]) * spec["micro_pv"]
        comm = pos["minis"] * spec["mini_comm_rt"] + pos["micros"] * spec["micro_comm_rt"]
        if pos["minis"] == 0 and pos["micros"] == 0:
            comm = pos["qty"] * spec["micro_comm_rt"]
        pos["gross"] = round(gross, 2)
        pos["comm"] = round(comm, 2)
        pos["pnl"] = round(gross - comm, 2)
        risk_usd = pos["risk_pts"] * pos["qty"] * spec["micro_pv"]
        pos["pnl_r"] = round(pos["pnl"] / risk_usd, 3) if risk_usd else 0.0
        pos["exit_t"] = pos["exits"][-1]["t"]
        pos["exit_price"] = pos["exits"][-1]["price"]
        pos["bars_held"] = i - pos["entry_i"] + 1
        # counterfactual value of every exit signal that fired: R banked by leaving there minus R actually made
        final_r = sum(e["pts"] * e["qty"] for e in pos["exits"]) / (pos["risk_pts"] * pos["qty"]) if pos["qty"] else 0.0
        rules = {s.strip() for s in self.p["exit_rules"].split(",") if s.strip()}
        for name, x in pos.get("xsig", {}).items():
            if pos.get("exit_signal") == name or name in rules:
                continue          # we act on it (or a hard exit beat it on the same bar): no counterfactual
            x["gain"] = round(x["r"] - final_r, 3)
            self._xstats.setdefault(name, []).append(x["gain"])
        self.trades.append({k: v for k, v in pos.items() if k not in ("remaining",)})

    # ------------------------------------------------------------------ output
    def result(self):
        return {
            "sym": self.sym, "tf": self.b.tf, "params": self.p,
            "trades": self.trades, "events": self.events, "signals": self.signals,
            "pools": self.all_pools, "ifvgs": self.ifvgs, "profiles": self.profiles,
            "days": list(self.days.values()), "structure": self.struct_events, "state": self.state,
            "shadows": self.shadows, "learner_log": self.learner_log, "exit_signals": self.exit_signal_summary(),
            "account_resets": getattr(self, "account_resets", []),
            "htf_fvgs": [g for g in (self.mtf.records() if self.mtf else []) if (g["t1"] or 4e9) >= int(self.b.t[0])],
            "mtf_events": self.mtf.events if self.mtf else [],
            **({"ltf": self.ltf_summary()} if self.ltf_info else {}),
        }

    def ltf_summary(self):
        """ifvg_tf 'lower' only: how much of the run really used 1m confirmation (the rest fell back to the 5m trigger)."""
        info = dict(self.ltf_info)
        n1 = sum(1 for t in self.trades if t.get("trigger_tf") == "1m")
        info["trades_1m_trigger"] = n1
        info["trades_5m_fallback"] = len(self.trades) - n1
        return info



