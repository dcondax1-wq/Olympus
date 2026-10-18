"""Realistic fill model for the LIT backtest (research only; engine/lit.py option "fills", default None = off).

What the plain backtest (engine/lit.py simulate_x) assumes, and what this module replaces when P["fills"] is set:

  plain backtest                                      realistic model (this file)
  ------------------------------------------------    ----------------------------------------------------------------------
  entry = open of the 1m bar after the 1m CISD        the live bot only SEES the entry once that next 1m bar has CLOSED
          close + 1 tick                              (engine/lit.simulate_x needs bar k+1 in the data and live.clean_bars
                                                      drops the forming bar), then waits for its next poll (60 s loop, not
                                                      aligned to the minute), computes (~2-4 s) and sends a MARKET order.
                                                      Fill = expected price at that moment (Brownian-bridge mean inside the
                                                      1m bar: open + f x (close - open)) + half the bid/ask spread of the hour.
                                                      detect "bar_close" models the recommended fix (decide on the CISD bar's
                                                      close, poll aligned to the minute).
  the model's trade is always taken                   if the model's trade already ended (stop / target / breakeven) before the
                                                      bot routes it, the bot routes nothing (engine/live.py _route_signals):
                                                      a skipped day (qty 0, "skip": True).
  stop = touch -> stop - 1 tick                       STOPMARKET at the broker: triggers on a trade at/through the stop, fills
                                                      at min(stop, bar open) (a bar that opens through the stop fills at the
                                                      open) minus slippage = max(base ticks of the hour, k x 1m bar range),
                                                      never below the bar's low.
  target = touch -> filled at the (unrounded) price   LIMIT at the tick price rounded toward the entry (live.tick_px), filled
                                                      only when the bar trades >= thr ticks THROUGH it (a touch can sit in the
                                                      queue unfilled); inside = place it n ticks inside the level.
  breakeven from the bar after +1R                    the bot sees +1R when that 1m bar closes, then polls: the CHANGE reaches
                                                      the broker ~35 s into the next bar (today's 60 s loop), so the old stop
                                                      guards that whole next bar and the breakeven stop works from the bar
                                                      after; a move that lands in the first half of a bar counts for that bar.
  model exits                                         every model exit (target the broker limit missed, breakeven, EOD) is
                                                      routed as CLOSEPOSITION at the next poll: market at the price then.
  flat 15:55 = close of the 15:55 bar - 1 tick        the NinjaTrader adapter flattens on its first poll at/after 15:55:00.
  $1.40 per micro round trip                          comm_rt (MFFU instrument list: MNQ $1.90 per round turn).

Inside a bar the stop is checked before the target (as the plain backtest); on the bar the live entry happens in, the stop is
checked against the whole bar (its low may have come before the entry: conservative) and no target is credited.
Every number here is an assumption to be replaced by measured ones: tools/fill_audit.py compares the NinjaTrader fills
with these expectations after a week on Sim101 / the MFFU account.
"""
from __future__ import annotations

import numpy as np

TICK = 0.25

# Base slippage in ticks for stop / market exits by ET hour, and the bid/ask spread in ticks by ET hour. Thin hours from the
# 2026 NQ 1m file (median 1m volume: 18:00-02:00 57-128 NQ, 02:00-08:00 85-125, 08:00 202, 09:30-16:00 530-1,316 a minute).
def _hour_table(asia, london, pre, rth):
    t = {}
    for h in range(24):
        t[h] = rth if 9 <= h < 16 else pre if h == 8 else london if 2 <= h < 8 else asia
    return t


FILL_DEFAULTS = {
    "detect": "next_close",     # "next_close" = today's live code (the 1m bar after the CISD must close) | "bar_close" (fix)
    "poll_s": 63.0,             # the PC bot's loop: poll (~3 s) then wait 60 s (engine/live.py _loop), not minute-aligned
    "phase": 0.5,               # expected share of the poll period between the data being ready and the next poll
    "compute_s": 3.0,           # one poll: feed read + lit_live.run (1.3-2.9 s measured on the cloud box; PC may be slower)
    "route_s": 0.3,             # OIF write -> NinjaTrader pickup -> Tradovate -> CME
    "feed_s": 0.5,              # LE_BarFeed writes a closed bar on the first tick of the next one (OnBarClose)
    "spread_ticks": _hour_table(2.0, 1.5, 1.0, 1.0),     # bid/ask spread; market orders pay half of it over the mid
    "stop_base_ticks": _hour_table(2.0, 1.5, 1.0, 1.0),  # stop-market slippage floor by hour
    "stop_k": 0.025,            # ... or k x the 1m bar's range if larger (fast bars slip more)
    "stop_cap_ticks": 80,       # never more than this (a CME protection band is far wider; this is a sanity cap)
    "tgt_thr": 1,               # target limit fills only if the bar trades this many ticks through it (0 = touch fills)
    "tgt_inside": 0,            # place the target limit this many ticks inside the model's level
    "entry_thr": 1,             # a plain resting limit entry (cisd1m None) needs this many ticks of trade-through
    "be_lag": True,             # breakeven reaches the broker one poll after the 1m close that made +1R
    "route_model_exits": True,  # model exits are sent as CLOSEPOSITION at the next poll (NinjaTrader route_all_exits)
    "comm_rt": 1.90,            # $ per micro round trip
    "flat_by_clock": True,      # the adapter flattens at the first poll at/after the flat minute
}


def params(P):
    f = P.get("fills") or {}
    out = {**FILL_DEFAULTS, **{k: v for k, v in f.items() if k not in ("spread_ticks", "stop_base_ticks")}}
    for k in ("spread_ticks", "stop_base_ticks"):
        v = f.get(k)
        if v is None:
            out[k] = FILL_DEFAULTS[k]
        elif isinstance(v, (int, float)):
            out[k] = {h: float(v) for h in range(24)}
        elif isinstance(v, (list, tuple)) and len(v) == 4:
            out[k] = _hour_table(*map(float, v))
        else:
            out[k] = {int(h): float(x) for h, x in dict(v).items()}
    return out


def _hour(t):
    import datetime as dt
    from zoneinfo import ZoneInfo
    return dt.datetime.fromtimestamp(int(t), ZoneInfo("America/New_York")).hour


_HC = {}


def hour_of(t):
    k = int(t) // 3600
    if k not in _HC:
        _HC[k] = _hour(k * 3600)
    return _HC[k]


def tick_toward(px, d=1):
    """Direction-space target price rounded toward the entry (live.tick_px target=True): down in direction space."""
    return np.floor(px / TICK + 1e-9) * TICK if d == 1 else -np.ceil(-px / TICK - 1e-9) * TICK


def simulate(M, B, cand, entry_px, tgt, stop, P):
    """engine/lit.simulate_x (research mode) with the realistic fills above. Returns a trade dict in simulate_x's columns plus
    entry_model / exit_model / exit_model_kind / lat_s / pts / w1 / comm_rt, a skipped trade (qty 0, "skip": True) when the
    model's trade ended before the bot would have routed it, or None (no trade, exactly when simulate_x gives None)."""
    from engine import lit
    Fp = params(P)
    SLIP, PV = lit.SLIP, lit.PV
    d = cand["dir"]
    hi_d, lo_d, c_d, o_d = B.dirs(d)
    t0 = int(M.t[cand["entry_i"]])
    k0 = int(np.searchsorted(B.t, t0))
    s_day = int(M.day_of[cand["entry_i"]])
    if k0 >= B.n:
        return None
    secs = B.secs
    flat = P["flat_mod"]
    wait_s = P["wait"] * 300
    cis = P.get("cisd1m")
    if cis and secs == 300:
        cis = max(1, cis // 5)
    tgt_cancel = entry_px + tgt[1] if tgt[0] == "pts" else tgt[1]
    thr_e = Fp["entry_thr"] * TICK
    # ---------------------------------------------------------------- 1. the model's signal (identical to simulate_x)
    limit_fill = True
    fill = tapped = None
    k = k0
    while k < B.n:
        if B.day[k] != s_day or B.mod[k] >= flat or B.mod[k] >= 1080:
            break
        if tapped is None and B.t[k] >= t0 + wait_s:
            break
        if lo_d[k] <= stop:
            if tapped is None and lo_d[k] <= entry_px - thr_e and not cis:
                fill = k; entry = min(entry_px, float(o_d[k]))
            break
        if tapped is None and lo_d[k] <= entry_px:
            if cis:
                tapped = k
            elif lo_d[k] <= entry_px - thr_e:        # a resting limit needs a trade-through (queue)
                fill = k; entry = min(entry_px, float(o_d[k])); break
        if tapped is None and hi_d[k] >= tgt_cancel:
            break
        if tapped is not None:
            if k - tapped > cis:
                break
            lowk = tapped + int(np.argmin(lo_d[tapped:k + 1]))
            cz = lit._cisd_level(c_d, o_d, lowk)
            if cz is not None and k > lowk and c_d[k] > cz[0] and k + 1 < B.n and B.day[k + 1] == s_day:
                fill = k + 1; entry = float(o_d[k + 1]) + SLIP; limit_fill = False; break
        k += 1
    if fill is None:
        return None
    risk = entry - stop
    if risk <= 0:
        return None
    if tgt[0] == "pts":
        tg = entry + tgt[1]
    else:
        if tgt[2]:
            tg = entry + P["fallback_rr"] * risk
        else:
            dist = tgt[1] - entry
            if dist < P["min_rr"] * risk:
                return None
            tg = entry + (min(dist, P["max_rr"] * risk) if P["max_rr"] else dist)
    q = lit.qty_for(risk)
    if q < 1:
        return None
    # ---------------------------------------------------------------- 2. the model's own management (what the bot runs)
    be_r = P["be_r"]
    cur, be_done = stop, False
    k_be = None
    stop_at = {}                      # bar -> the model's stop after that bar (for the routed stop at entry time)
    k = fill
    k_x = kind_m = xpx_m = None
    while k < B.n:
        if B.day[k] != s_day or B.mod[k] >= 1080:
            k -= 1; k_x, kind_m, xpx_m = k, "EOD", float(c_d[k]) - SLIP; break
        if lo_d[k] <= cur:
            k_x, kind_m, xpx_m = k, ("BE" if be_done else "STOP"), cur - SLIP; break
        if not (k == fill and limit_fill):
            if hi_d[k] >= tg:
                k_x, kind_m, xpx_m = k, "TARGET", tg; break
            if be_r is not None and not be_done and hi_d[k] >= entry + be_r * risk:
                cur, be_done, k_be = entry, True, k
        stop_at[k] = cur
        if B.mod[k] >= flat:
            k_x, kind_m, xpx_m = k, "EOD", float(c_d[k]) - SLIP; break
        k += 1
    if k_x is None:
        return None
    pnl_m = (xpx_m - entry) * PV * q - lit.COMM * q
    # ---------------------------------------------------------------- 3. the live bot and the broker
    lat = Fp["poll_s"] * Fp["phase"] + Fp["compute_s"] + Fp["route_s"] + Fp["feed_s"]
    if limit_fill:
        T_e = int(B.t[fill])           # a resting limit at the broker: no decision latency
    else:
        conf_close = int(B.t[fill - 1]) + secs
        T_e = conf_close + (60 if Fp["detect"] == "next_close" else 0) + lat

    def bar_at(T):
        j = int(np.searchsorted(B.t, T, side="right") - 1)
        return j

    def px_at(j, T):
        """Expected trade price at time T inside bar j (Brownian bridge mean between its open and close)."""
        f = min(1.0, max(0.0, (T - float(B.t[j])) / secs))
        return float(o_d[j]) + f * (float(c_d[j]) - float(o_d[j]))

    def hs(T):
        return 0.5 * Fp["spread_ticks"][hour_of(T)] * TICK

    def stop_slip(b):
        s = max(Fp["stop_base_ticks"][hour_of(B.t[b])] * TICK, Fp["stop_k"] * float(hi_d[b] - lo_d[b]))
        return min(s, Fp["stop_cap_ticks"] * TICK)

    def out(kind, k_end, exit_px, entry_px_real, w1, skip=False, qq=q):
        pnl = (exit_px - entry_px_real) * PV * qq - Fp["comm_rt"] * qq
        low = min(0.0, w1 * PV * qq - Fp["comm_rt"] * qq, pnl)
        xi5 = int(np.searchsorted(M.t, B.t[k_end], side="right") - 1)
        ei5 = int(np.searchsorted(M.t, min(T_e, int(B.t[k_end])), side="right") - 1)
        r_den = risk * PV * qq if qq else 1.0
        return {"day": cand["day"], "entry_t": int(B.t[fill]), "exit_t": int(B.t[k_end]) + secs, "exit_i": xi5, "dir": d,
                "r": round(pnl / r_den, 3) if qq else 0.0, "pnl": round(pnl, 2) if qq else 0.0, "risk_pts": round(risk, 2),
                "qty": qq, "risk_usd": round(risk * PV * qq, 2), "half": False, "exit": kind,
                "trigger": "LIT-" + ("1m" if secs == 60 else "5m"), "mfe": None, "mae": None, "bars_held": int(k_end - fill + 1),
                "regime": "", "mult": 1.0, "low": round(low, 2) if qq else 0.0, "entry_px": round(entry_px_real * d, 2),
                "stop_px": round(stop * d, 2), "target_px": round(tg * d, 2), "swept": cand["swept"], "ind_n": cand["ind_n"],
                "vec": cand["vec"], "i": cand["i"], "ext_i": cand["ext_i"], "ref_i": cand["ref_i"], "sweep_i": cand["sweep_i"],
                "entry_i": ei5, "tf": secs // 60,
                # realistic-fill columns (only when P["fills"] is set)
                "skip": skip, "entry_model": round(entry * d, 2), "exit_model": round(xpx_m * d, 2), "exit_model_kind": kind_m,
                "pnl_model": round(pnl_m, 2), "live_entry_t": int(T_e), "lat_s": round(T_e - int(B.t[fill]), 1),
                "pts": round(exit_px - entry_px_real, 4), "w1": round(w1, 4), "comm_rt": Fp["comm_rt"],
                "slip_entry_pts": round(entry_px_real - entry, 4), "exit_px": round(exit_px * d, 2)}

    j = bar_at(T_e)
    # the model's trade already over when the bot would route it (it only knows bars closed before the poll): not routed
    last_closed = bar_at(T_e - Fp["route_s"] - Fp["compute_s"] - secs)   # bars with t + secs <= the poll's data read
    if not limit_fill and k_x <= last_closed:
        return out("SKIP", k_x, 0.0, 0.0, 0.0, skip=True, qq=0)
    if j < fill or j >= B.n or B.day[j] != s_day or B.mod[j] >= flat or B.mod[j] >= 1080:
        return out("SKIP", k_x, 0.0, 0.0, 0.0, skip=True, qq=0)
    # routed bracket: the model's stop as it stands at the poll (breakeven already in it if it happened), target tick-rounded
    s_r = stop_at.get(last_closed, stop) if not limit_fill else stop
    s_r = round(s_r / TICK) * TICK
    L = float(tick_toward(tg, 1)) - Fp["tgt_inside"] * TICK
    thr_t = Fp["tgt_thr"] * TICK
    if limit_fill:
        e_real = entry
    else:
        e_real = px_at(j, T_e) + hs(T_e)
    w1 = 0.0                                 # worst open P&L in points while in the trade (the stop bar counts to the fill)
    if e_real - s_r <= TICK:                 # the stop would sit at/above the market: rejected -> the adapter flattens at once
        return out("REJ", j, e_real - 2 * hs(T_e), e_real, w1)
    if e_real >= L:                          # target already below the market: the limit fills at once
        return out("TARGET", j, max(L, e_real - 2 * hs(T_e)), e_real, w1)
    lat_poll = Fp["poll_s"] * Fp["phase"] + Fp["compute_s"] + Fp["route_s"] + Fp["feed_s"]
    T_be = None
    if k_be is not None and (int(B.t[k_be]) + secs + lat_poll) > T_e - 1e-9 and stop_at.get(last_closed, stop) != entry:
        T_be = int(B.t[k_be]) + secs + (lat_poll if Fp["be_lag"] else 0.0)
    T_x = int(B.t[k_x]) + secs + lat_poll if Fp["route_model_exits"] else None
    T_eod = None
    if Fp["flat_by_clock"]:
        fl = np.flatnonzero((B.day == s_day) & (B.mod == flat))
        if len(fl):
            T_eod = int(B.t[fl[0]]) + Fp["poll_s"] * Fp["phase"] + Fp["route_s"]
    cur_r = s_r
    be_px = round(entry / TICK) * TICK
    b = j
    while b < B.n:
        if B.day[b] != s_day or B.mod[b] >= 1080:
            b -= 1
            return out("EOD", b, float(c_d[b]) - hs(B.t[b]), e_real, w1)
        tb = int(B.t[b])
        if T_be is not None and tb + 0.5 * secs >= T_be:      # the move landed in the first half of this bar (or before it)
            cur_r = max(cur_r, be_px); T_be = None
        routed = [(T_, nm) for T_, nm in ((T_x, "MODEL_" + str(kind_m)), (T_eod, "EOD")) if T_ is not None and T_ >= T_e]
        # a routed exit / clock flatten that fell in a gap between bars: market at this bar's open
        gap = [(T_, nm) for T_, nm in routed if T_ <= tb and b > j]
        if gap:
            return out(min(gap)[1], b, float(o_d[b]) - hs(tb), e_real, min(w1, float(o_d[b]) - hs(tb) - e_real))
        if lo_d[b] <= cur_r:
            base = cur_r if b == j else min(cur_r, float(o_d[b]))
            xp = max(float(lo_d[b]), base - stop_slip(b))
            w1 = min(w1, xp - e_real)
            return out("BE" if cur_r >= be_px - 1e-9 and cur_r > stop else "STOP", b, xp, e_real, w1)
        w1 = min(w1, float(lo_d[b]) - e_real)
        if b > j and hi_d[b] >= L + thr_t:
            return out("TARGET", b, L, e_real, w1)
        inbar = [(T_, nm) for T_, nm in routed if tb <= T_ < tb + secs]
        if inbar:
            T_, nm = min(inbar)
            return out(nm, b, px_at(b, T_) - hs(T_), e_real, w1)
        if B.mod[b] >= flat and (not Fp["flat_by_clock"] or T_eod is None):
            return out("EOD", b, float(c_d[b]) - hs(tb), e_real, w1)
        b += 1
    return None
