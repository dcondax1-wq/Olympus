"""Order blocks (LIT / ICT) from OHLC bars, no look-ahead. Pure numpy functions, no engine state: the research wrapper
(tools/lit_ob.py) and a dashboard can draw exactly the same blocks from the same bars.

What an order block is here (bullish; a bearish block is the exact mirror, with highs and lows swapped):
  1. The block = the LAST run of down-close candles (1 to run_max = 3, a doji inside the run is allowed) right before the first
     up-close candle of a move up. Doji / neutral candle = body <= doji x range (or no range); up to skip_neutral of them may
     sit between the run and the move.
  2. The move must be a displacement that, within disp_max candles of its first up candle,
       a. leaves a fair value gap: low[b] > high[b-2] with candle b-2 no earlier than the block's last candle, and
       b. breaks structure: a close above the last confirmed swing high (2-bar fractal) made before the block
          (qualify "bos"; the swing must sit above the block and still be intact), or, when the block's own low took
          sell-side liquidity, a close above the block's body top (CISD) is enough (qualify "bos_or_liq", the default).
          qualify "liq" needs both the sweep and the CISD close. The biggest body of the move must be >= min_disp_atr
          (0.8) x ATR(14) and the FVG >= min_fvg_atr (0.1) x ATR(14).
     and it must not trade below the block's low or close back below the block before it qualifies.
  3. The block is KNOWN at the close of the candle that completes both (conf). Nothing before that bar can use it.
  4. Zone: body = [lowest body bottom, highest body top] of the run (TTrades), wick = [lowest low, highest high].
     Mean threshold (mt) = the middle of the body zone; wick_mt = the middle of the wick zone.
  5. swept = the block's low took a 2-bar fractal low (made in the liq_lb candles before the run, untaken until the run).
  6. kind = "extreme" when the block's low is the lowest low since the swing high its move broke (the origin of the leg
     that broke structure; without a broken swing: the last leg_lb candles), else "decisional" (a block formed higher
     inside that leg, closer to price).
  7. Life cycle (lifecycle()): fresh until the first touch (low <= the proximal edge = zone top: mitigation); failed when a
     candle CLOSES below the distal edge (zone bottom) at or after the touch -> a bearish BREAKER block on the same zone,
     known at that close, fresh until price trades back up to its proximal edge (the zone bottom).
Timeframes: resample() builds 15m / 1h / 4h candles from 5m (1h = clock hours, 15m = clock quarters, 4h = 18:00 ET aligned
like engine/lit.py open_4h); an HTF candle is known only after its last 5m bar closed (`last`).

    obs = detect(o, h, l, c, tf="1h")                 # both directions, indices in the bars given
    lifecycle(obs, h, l, c)                           # adds mit / brk / brk_mit indices on the same bars
    zones = chart_zones(t, o, h, l, c, mod, day, "1h")  # JSON-ready rows for a chart (times in seconds)
"""
from __future__ import annotations

import numpy as np

DEFAULTS = {
    "doji": 0.1,          # body <= doji x range = neutral candle (also any candle with no range)
    "run_max": 3,         # at most this many candles in the block's run (longer slow runs make useless wide zones)
    "skip_neutral": 1,    # neutral candles allowed between the run and the first candle of the move
    "disp_max": 4,        # the move has this many candles (from its first up candle) to leave the FVG and break structure
    "qualify": "bos_or_liq",   # "bos" | "bos_or_liq" | "liq" | "cisd" (close above the body top only; loosest)
    "need_fvg": True,
    "swing_lb": 48,       # the swing high that must break was made at most this many candles before the run
    "liq_lb": 48,         # the swept fractal low was made at most this many candles before the run
    "leg_lb": 24,         # extreme vs decisional: lowest low of this many candles up to conf
    "min_disp_atr": 0.8,  # biggest body of the move >= this x ATR(14) of that timeframe (LIT's displacement: 0.8)
    "min_fvg_atr": 0.1,   # the FVG must be at least this x ATR(14) tall (no 1-tick gaps in a slow grind)
    "no_break": True,     # no session break (a bar-to-bar time gap > the timeframe + 30 min: the 17:00 halt, weekends)
                          # between the block and the bar that qualifies it: an opening gap is not a displacement
}
TF_SECS = {"5m": 300, "15m": 900, "1h": 3600, "4h": 14400}


# ------------------------------------------------------------------------------------------------ bars
def resample(t, o, h, l, c, tf, mod=None, day=None, closed_last=False):
    """HTF candles from 5m arrays. Returns dict t (open time of the first 5m bar), o, h, l, c, first, last (5m indices).
    tf "5m" returns the bars unchanged. 4h needs mod (ET minute) and day (trading-day index). The final candle is dropped
    unless closed_last (it may still be forming)."""
    t = np.asarray(t); o = np.asarray(o, float); h = np.asarray(h, float); l = np.asarray(l, float); c = np.asarray(c, float)
    n = len(t)
    if tf == "5m":
        ix = np.arange(n)
        return {"t": t, "o": o, "h": h, "l": l, "c": c, "first": ix, "last": ix}
    if tf == "15m":
        g = t // 900
    elif tf == "1h":
        g = t // 3600
    elif tf == "4h":
        if mod is None or day is None:
            raise ValueError("4h needs mod and day")
        g = np.asarray(day).astype(np.int64) * 10 + ((np.asarray(mod) - 1080) % 1440) // 240
    else:
        raise ValueError(tf)
    st = np.r_[0, np.flatnonzero(np.diff(g)) + 1]
    en = np.r_[st[1:], n] - 1
    if not closed_last and len(st):
        st, en = st[:-1], en[:-1]
    if not len(st):
        e = np.array([], dtype=np.int64)
        return {"t": e, "o": e.astype(float), "h": e.astype(float), "l": e.astype(float), "c": e.astype(float), "first": e, "last": e}
    return {"t": t[st], "o": o[st], "h": np.maximum.reduceat(h, st)[:len(st)], "l": np.minimum.reduceat(l, st)[:len(st)],
            "c": c[en], "first": st, "last": en}


def atr(h, l, c, n=14):
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    out = np.empty_like(tr)
    if not len(tr):
        return out
    out[0] = tr[0]
    a = 1.0 / n
    for i in range(1, len(tr)):
        out[i] = out[i - 1] + a * (tr[i] - out[i - 1])
    return out


def _fractal_lows(l, k=2):
    n = len(l)
    out = np.zeros(n, bool)
    for j in range(k, n - k):
        if l[j] < l[j - k:j].min() and l[j] <= l[j + 1:j + k + 1].min():
            out[j] = True
    return np.flatnonzero(out)


# ------------------------------------------------------------------------------------------------ detection
def _detect_dir(o, h, l, c, P, at, rej=None, brk=None):
    """Bullish blocks in direction space (o, h, l, c already mirrored for bearish). rej: a list that collects the
    rejected candidates (last down run before an up candle that never qualified) with the reason."""
    n = len(o)
    rng = h - l
    body = np.abs(c - o)
    neutral = (rng <= 0) | (body <= P["doji"] * rng)
    up = (c > o) & ~neutral
    dn = (c < o) & ~neutral
    fh = _fractal_lows(-h)            # swing highs = fractal lows of -h
    fl = _fractal_lows(l)
    out = []
    seen = set()
    for u in range(1, n):
        if not up[u]:
            continue
        j, sk = u - 1, 0
        while j >= 0 and neutral[j] and sk < P["skip_neutral"]:
            j -= 1; sk += 1
        if j < 0 or not dn[j]:
            continue
        e_run = j
        s_run = j
        while s_run - 1 >= 0 and e_run - (s_run - 1) + 1 <= P["run_max"]:
            p = s_run - 1
            if dn[p]:
                s_run = p
            elif neutral[p] and p - 1 >= 0 and dn[p - 1] and e_run - (p - 1) + 1 <= P["run_max"]:
                s_run = p - 1
            else:
                break
        if (s_run, e_run) in seen:
            continue
        seg = slice(s_run, e_run + 1)
        body_top = float(np.maximum(o[seg], c[seg]).max()); body_bot = float(np.minimum(o[seg], c[seg]).min())
        wick_top = float(h[seg].max()); wick_bot = float(l[seg].min())
        # swing high to break: the most recent 2-bar fractal high before the run, made within swing_lb candles, ABOVE the
        # block's body and still intact (no close above it between the swing and the move)
        q = int(np.searchsorted(fh, s_run)) - 1
        bos_lvl = None
        while q >= 0 and fh[q] >= s_run - P["swing_lb"]:
            f = int(fh[q])
            if h[f] > body_top and (f + 1 >= u or c[f + 1:u].max() <= h[f]):
                bos_lvl = float(h[f]); break
            q -= 1
        # sell-side taken by the block: a fractal low before the run, untaken until the run, under-cut by the run's low
        swept = False
        a = int(np.searchsorted(fl, s_run - P["liq_lb"])); b_ = int(np.searchsorted(fl, s_run))
        for f in fl[a:b_]:
            f = int(f)
            if f + 2 > e_run or wick_bot >= l[f]:
                continue
            if f + 1 >= s_run or l[f + 1:s_run].min() >= l[f]:
                swept = True; break
        fvg = None; bos_k = None; cisd_k = None; conf = None; died = None
        for b in range(u, min(n, u + P["disp_max"])):
            if l[b] < wick_bot or c[b] < body_bot:
                died = "price went back below the block first"   # a lower low / a close back below: not the origin
                break
            if fvg is None and b - 2 >= e_run and l[b] - h[b - 2] >= P["min_fvg_atr"] * at[b]:
                fvg = (float(h[b - 2]), float(l[b]), b)
            if cisd_k is None and c[b] > body_top:
                cisd_k = b
            if bos_k is None and bos_lvl is not None and c[b] > bos_lvl:
                bos_k = b
            qual = P["qualify"]
            ok_s = (bos_k is not None if qual == "bos" else
                    (bos_k is not None or (swept and cisd_k is not None)) if qual == "bos_or_liq" else
                    (swept and cisd_k is not None) if qual == "liq" else cisd_k is not None)
            if ok_s and (fvg is not None or not P["need_fvg"]):
                conf = b; break
        if conf is not None and brk is not None and brk[s_run + 1:conf + 1].any():
            if rej is not None:
                rej.append({"s": s_run, "e": e_run, "u": u, "why": "session break inside the move (an opening gap)", "fvg": fvg is not None,
                            "bos_lvl": bos_lvl, "swept": swept, "cisd": cisd_k is not None, "conf": conf})
            continue
        if conf is None:
            if rej is not None:
                rej.append({"s": s_run, "e": e_run, "u": u, "why": (died or ("no FVG" if fvg is None and P["need_fvg"] else
                            "no structure break")),
                            "fvg": fvg is not None, "bos_lvl": bos_lvl, "swept": swept, "cisd": cisd_k is not None})
            continue
        mb = float(body[u:conf + 1].max() / max(at[conf], 1e-9))
        if mb < P["min_disp_atr"]:
            if rej is not None:
                rej.append({"s": s_run, "e": e_run, "u": u, "why": f"weak move (biggest body {mb:.2f} ATR)", "fvg": True,
                            "bos_lvl": bos_lvl, "swept": swept, "cisd": True, "conf": conf})
            continue
        seen.add((s_run, e_run))
        # the leg that broke structure starts at the swing high it broke (else leg_lb candles back): the block holding the
        # lowest low since then is that leg's origin (extreme); a block above that low formed later in it (decisional)
        ref = int(fh[q]) if (bos_lvl is not None and q >= 0) else max(0, s_run - P["leg_lb"])
        lo_leg = float(l[ref:conf + 1].min())
        out.append({"s": s_run, "e": e_run, "u": u, "conf": conf, "body_top": body_top, "body_bot": body_bot,
                    "wick_top": wick_top, "wick_bot": wick_bot, "fvg": fvg[:2] if fvg else None,
                    "bos": bos_lvl if bos_k is not None else None, "bos_i": bos_k, "swept": bool(swept),
                    "kind": "extreme" if wick_bot <= lo_leg else "decisional", "disp_atr": round(mb, 3),
                    "n_run": e_run - s_run + 1})
    return out


def detect(o, h, l, c, cfg=None, tf="5m", rejects=None, t=None):
    """Every order block of both directions in the bars given (sorted by conf). Prices are real prices: for a bullish
    block (dir +1) top/bot = the zone, proximal edge = top; for a bearish block (dir -1) proximal edge = bot.
    rejects: a list that receives the candidates that did not qualify ({"dir", "s", "e", "u", "why", ...}).
    t: bar open times in seconds (needed for the session-break rule no_break; without t the rule is off)."""
    P = {**DEFAULTS, **(cfg or {})}
    o = np.asarray(o, float); h = np.asarray(h, float); l = np.asarray(l, float); c = np.asarray(c, float)
    at = atr(h, l, c)
    brk = None
    if t is not None and P["no_break"] and len(t) > 1:
        tt = np.asarray(t, dtype=np.int64)
        brk = np.r_[False, np.diff(tt) > TF_SECS.get(tf, 300) + 1800]     # brk[i]: a session break right before bar i
    out = []
    for d in (1, -1):
        rj = [] if rejects is not None else None
        if d == 1:
            R = _detect_dir(o, h, l, c, P, at, rj, brk)
        else:
            R = _detect_dir(-o, -l, -h, -c, P, at, rj, brk)
        if rejects is not None:
            rejects.extend({**r, "dir": d, "tf": tf} for r in rj)
        for r in R:
            x = {"dir": d, "tf": tf, "s": r["s"], "e": r["e"], "u": r["u"], "conf": r["conf"], "swept": r["swept"],
                 "kind": r["kind"], "disp_atr": r["disp_atr"], "n_run": r["n_run"], "bos_i": r["bos_i"]}
            if d == 1:
                x.update(body_top=r["body_top"], body_bot=r["body_bot"], wick_top=r["wick_top"], wick_bot=r["wick_bot"],
                         fvg=r["fvg"], bos=r["bos"])
            else:
                x.update(body_top=-r["body_bot"], body_bot=-r["body_top"], wick_top=-r["wick_bot"], wick_bot=-r["wick_top"],
                         fvg=(-r["fvg"][1], -r["fvg"][0]) if r["fvg"] else None, bos=-r["bos"] if r["bos"] is not None else None)
            x["mt"] = 0.5 * (x["body_top"] + x["body_bot"])
            x["wick_mt"] = 0.5 * (x["wick_top"] + x["wick_bot"])
            out.append(x)
    out.sort(key=lambda x: (x["conf"], -x["dir"]))
    return out


def zone(ob, kind="body"):
    """(bot, top) of the zone: "body" or "wick"."""
    return (ob["body_bot"], ob["body_top"]) if kind == "body" else (ob["wick_bot"], ob["wick_top"])


def proximal(ob, kind="body"):
    b, t = zone(ob, kind)
    return t if ob["dir"] == 1 else b


def distal(ob, kind="body"):
    b, t = zone(ob, kind)
    return b if ob["dir"] == 1 else t


# ------------------------------------------------------------------------------------------------ life cycle
def _first(mask, start):
    if start >= len(mask):
        return None
    m = mask[start:]
    j = int(np.argmax(m)) if len(m) else 0
    return start + j if len(m) and m[j] else None


def touch_and_break(d, bot, top, h, l, c, start, end=None):
    """On the bars h/l/c from index start: (mit = first touch of the proximal edge, brk = first close through the distal
    edge at/after mit, brk_mit = first touch of the breaker's proximal edge after brk). None when it never happens before
    end. Bullish d=+1: touch = low <= top, break = close < bot, breaker touch = high >= bot. Mirror for d=-1."""
    end = len(h) if end is None else min(end, len(h))
    if start >= end:
        return None, None, None
    hs, ls, cs = h[start:end], l[start:end], c[start:end]
    if d == 1:
        m = _first(ls <= top, 0)
        if m is None:
            return None, None, None
        b = _first(cs <= bot - 1e-9, m)
        bm = _first(hs >= bot, b + 1) if b is not None else None
    else:
        m = _first(hs >= bot, 0)
        if m is None:
            return None, None, None
        b = _first(cs >= top + 1e-9, m)
        bm = _first(ls <= top, b + 1) if b is not None else None
    f = lambda v: None if v is None else int(start + v)
    return f(m), f(b), f(bm)


def lifecycle(obs, h, l, c, kind="body", max_bars=None):
    """Adds mit / brk / brk_mit (indices on the same bars as detect) to every block, for zone `kind`."""
    h = np.asarray(h, float); l = np.asarray(l, float); c = np.asarray(c, float)
    for ob in obs:
        b, t = zone(ob, kind)
        st = ob["conf"] + 1
        m, br, bm = touch_and_break(ob["dir"], b, t, h, l, c, st, None if max_bars is None else st + max_bars)
        ob["mit"], ob["brk"], ob["brk_mit"] = m, br, bm
    return obs


def state_at(ob, i):
    """The block's state as seen at the close of bar i: None (not known yet), "fresh", "mitigated", "breaker" (failed,
    the breaker not touched yet), "breaker_used"."""
    if i < ob["conf"]:
        return None
    if ob.get("mit") is None or i < ob["mit"]:
        return "fresh"
    if ob.get("brk") is None or i < ob["brk"]:
        return "mitigated"
    if ob.get("brk_mit") is None or i < ob["brk_mit"]:
        return "breaker"
    return "breaker_used"


# ------------------------------------------------------------------------------------------------ chart helper
def chart_zones(t, o, h, l, c, mod=None, day=None, tf="5m", cfg=None, kind="body", since=None):
    """JSON-ready blocks of one timeframe for a chart from 5m arrays: start / known / mitigated / broken times (seconds,
    5m bar open times; a block is drawn from its first candle to the touch, a breaker from the break to its touch)."""
    B = resample(t, o, h, l, c, tf, mod, day)
    obs = lifecycle(detect(B["o"], B["h"], B["l"], B["c"], cfg, tf, t=B["t"]), B["h"], B["l"], B["c"], kind)
    sec = TF_SECS[tf]
    tt = B["t"]
    T = lambda i: None if i is None else int(tt[i])
    rows = []
    for ob in obs:
        if since is not None and tt[ob["conf"]] < since:
            continue
        bt, tp = zone(ob, kind)
        rows.append({"dir": ob["dir"], "tf": tf, "kind": ob["kind"], "swept": ob["swept"], "bot": round(bt, 2), "top": round(tp, 2),
                     "mt": round(0.5 * (bt + tp), 2), "t_start": T(ob["s"]), "t_known": int(tt[ob["conf"]]) + sec,
                     "t_mit": T(ob["mit"]), "t_brk": None if ob["brk"] is None else int(tt[ob["brk"]]) + sec,
                     "t_brk_mit": T(ob["brk_mit"]), "bos": ob["bos"], "fvg": ob["fvg"]})
    return rows


def selftest():
    # a clean bullish block: down candles, then a 3-candle displacement with an FVG that breaks the swing high at 105
    o = np.array([100, 103, 104, 105, 104, 103, 102, 101.5, 104, 108, 111, 112.])
    c = np.array([103, 104, 105, 104, 103, 102, 101, 104.0, 108, 111, 112, 113.])
    h = np.array([103.5, 104.5, 106, 105.5, 104.5, 103.5, 102.5, 104.5, 108.5, 111.5, 112.5, 113.5])
    l = np.array([99.5, 102.5, 103.5, 103.5, 102.5, 101.5, 100.5, 101, 103.8, 107.5, 110.5, 111.5])
    obs = detect(o, h, l, c, {"disp_max": 4})
    bull = [x for x in obs if x["dir"] == 1]
    assert bull, obs
    ob = bull[0]
    assert ob["s"] == 4 and ob["e"] == 6 and ob["body_top"] == 104 and ob["body_bot"] == 101, ob   # run_max 3
    assert ob["conf"] >= 8 and ob["fvg"] is not None and ob["bos"] == 106.0, ob
    # mirror: the same bars upside down give the same block as a bearish one
    obs2 = detect(-o, -l, -h, -c)
    bear = [x for x in obs2 if x["dir"] == -1]
    assert bear and bear[0]["body_bot"] == -104 and bear[0]["body_top"] == -101, bear
    # life cycle: touch at the top, close through the bottom -> breaker
    h2 = np.r_[h, 112, 106, 103]; l2 = np.r_[l, 104.5, 100.0, 99.0]; c2 = np.r_[c, 105, 100.5, 102]
    lifecycle(bull, h2, l2, c2)
    assert bull[0]["mit"] == 13 and bull[0]["brk"] == 13 and bull[0]["brk_mit"] == 14, bull[0]
    assert state_at(bull[0], 9) == "fresh" and state_at(bull[0], 13) == "breaker" and state_at(bull[0], 5) is None
    print("lit_ob selftest OK")
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if selftest() else 1)
