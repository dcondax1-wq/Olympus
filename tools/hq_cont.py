"""HQ continuation (owner 2026-10-23: "a strategy that trades 2+ times a week, high-quality setups, with high probability and
high profit"). Family: TREND / CONTINUATION with structure - the opposite of LIT's reversal.

The setup (long; shorts are the mirror, computed on the negated prices):
  1. Session: London (from 02:00 ET; the leg must confirm by 05:00, entries until 07:30, 'session' hold flat 09:25) or NY
     (from 09:30; confirm by 11:30, entries until 12:00, 'session' hold flat 13:30). 'both' = the two together, one
     position at a time.
  2. Opening structure ('struct'): the session's first 15 / 30 minutes ('or15' / 'or30'), or the range before the session
     ('box' = Asia 20:00-00:00 for London, the overnight 18:00-09:30 for NY).
  3. Directional leg: the first 5m close beyond the structure, with the leg (running high - the session's lowest low, the
     leg origin) >= k x the 5m ATR(14) and (disp > 0) a candle in the leg with a body >= disp x ATR. Only the first leg of
     the session counts (one clear direction or no trade). Filters at that bar: 'vwap' = close above the 18:00 session
     VWAP, 'trend' = the last completed 1h bar's EMA 21 above its EMA 50.
  4. The FIRST pullback into the leg's zone within pbw bars: 'fib50' = 50% of origin..leg high, 'fvg' = the leg's most
     recent bullish 5m FVG (top), 'ob' = the last down-close candle before the leg's first displacement candle (its high).
     A low below the leg origin first = no trade.
  5. Trigger ('trig') within 6 bars of the touch: 'cisd' = a 5m close above the open of the down-candle run into the
     pullback low; 'close' = a 5m close above the prior candle's high; 'hunt' = the second leg after a stop hunt: after the
     first CISD, price trades below that pullback's low (the first entry's stop) but not below the leg origin within 24
     bars, then a new 5m CISD back up.
  6. Entry at the next 5m open + 1 tick. Stop ('stopm'): 'pb' = 1 tick beyond the pullback's protected low, 'origin' = 1
     tick beyond the leg origin. Stops 6-80 pts (else no trade).
  7. Targets: 'R1.5' / 'R2' / 'R3' fixed R; 'S' = the next liquidity pool in the trend direction (leg high, the day's high so
     far, PDH, PWH, PMH, the Asia / London box high, untaken equal highs = LIT build-ups) at least 1R away, banked at 8R;
     'S3' = the same capped at 3R; 'PS' = half at 1R, the rest at the pool (>= 1.5R, else 2R) with the stop at entry + 1.25
     after the partial; 'P2' = half at 1R, rest at 2R. Breakeven (entry + 1.25 pts) at +1R optional ('be'). Flat at the
     session hold ('s') or 15:55 ('eod').
Execution, no look-ahead, costs in: everything a signal uses is known at its 5m close; management on true 1m bars on 2026
days with full 1m coverage, else 5m (stop first when stop and target share a bar; target = limit filled on a trade-through;
stop / time exits - 1 tick). Size = the LIT size rule ($800 up to a 20-pt stop, then 800 x 20 / stop, max 40 micros),
$1.90 a micro. Data: TradingView CME NQ1! (data/NQ_5m.csv, data/NQ_1m.csv). No Yahoo, no CFD.

    python -X utf8 tools/hq_cont.py grid     # every variant, stats per span -> research/hq/grid.json.gz (~10 min, 4 procs)
    python -X utf8 tools/hq_cont.py pick     # H1 picks + pre-2025 re-pick, plateau, placebos, chance, months -> picks.json
    python -X utf8 tools/hq_cont.py evals    # 50K next to LIT + 25K alone for the picks -> evals.json
    python -X utf8 tools/hq_cont.py save     # rl.save hq_cont_* + research/hq/<pick>.json (common trade format)
Research only: edits no engine file, no live_model*.json, no second_model.json, no UI.
"""
from __future__ import annotations

import collections
import datetime as dt
import gzip
import hashlib
import itertools
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from tools import allday as A  # noqa: E402

OUT = os.path.join(ROOT, "research", "hq")
TICK, PV, COMM, BE_OFF = 0.25, 2.0, 1.90, 1.25
SPANS = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-12-31"), "2025": ("2025-01-01", "2025-12-31"),
         "2021-24": ("2021-01-01", "2024-12-31"), "2026": ("2026-01-01", "2026-12-31")}
GRID_SPANS = ("H1", "H2", "2025", "2021-24")
# session: start, confirm-by, entries-until, 'session' flat (ET minutes)
SESS = {"lon": (120, 300, 450, 565), "ny": (570, 690, 720, 810)}
EOD = 955

ORDER = {  # parameter values in order (neighbours = one step in one position)
    "sess": ["lon", "ny", "both"],
    "struct": ["or15", "or30", "box"],
    "k": ["2", "3", "4"],
    "disp": ["0", "0.8"],
    "vwap": ["0", "1"],
    "trend": ["0", "1"],
    "zone": ["fib50", "fvg", "ob"],
    "pbw": ["12", "24"],
    "trig": ["close", "cisd", "hunt"],
    "stopm": ["pb", "origin"],
    "tgt": ["R1.5", "R2", "R3", "S3", "S", "P2", "PS"],
    "be": ["None", "1.0"],
    "hold": ["s", "eod"],
}
DIMS = list(ORDER)
UNORDERED = {"sess", "zone", "trig", "stopm", "tgt", "struct"}     # any value counts as one step
EXITS = [(t, be, h) for t in ("R1.5", "R2", "R3", "S3", "S") for be in (None, 1.0) for h in ("s", "eod")] + \
        [(t, None, h) for t in ("P2", "PS") for h in ("s", "eod")]


def _dump(obj, path, **kw):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    if path.endswith(".gz"):
        with gzip.open(tmp, "wt", encoding="utf-8") as fh:
            json.dump(obj, fh, **kw)
    else:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, **kw)
    os.replace(tmp, path)


def _load(path):
    if path.endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return json.load(fh)
    return json.load(open(path, encoding="utf-8"))


# ================================================================================================ data
_X = {}


def data():
    """allday's market (5m bars, days, ATR, VWAP from 18:00, 1m bars) + the 1h EMA trend per 5m bar (last completed hour),
    the bar index of each session start per day, LIT build-ups split by side."""
    D = A.data()
    if _X:
        return D, _X
    M = D["M"]
    # 1h bars: UTC hour buckets = ET hour buckets; an hour is complete at the close of its last 5m bar
    hb = M.t // 3600
    starts = np.r_[0, np.flatnonzero(np.diff(hb)) + 1]
    ends = np.r_[starts[1:], M.n]
    hc = M.c[ends - 1]

    def ema(x, n):
        a = 2.0 / (n + 1)
        out = np.empty_like(x)
        out[0] = x[0]
        for j in range(1, len(x)):
            out[j] = out[j - 1] + a * (x[j] - out[j - 1])
        return out
    e21, e50 = ema(hc, 21), ema(hc, 50)
    hsign = np.sign(e21 - e50)
    # for 5m bar i: the latest hour whose last bar index <= i
    last_of_hour = ends - 1
    j = np.searchsorted(last_of_hour, np.arange(M.n), side="right") - 1
    tr = np.where(j >= 0, hsign[np.maximum(j, 0)], 0.0)
    # session start bar per day
    st = {}
    for nm, (a, *_r) in SESS.items():
        arr = np.full(len(M.days), -1, dtype=np.int64)
        for k, (d, s, e) in enumerate(M.days):
            rr = (M.mod[s:e] - 1080) % 1440
            ii = np.flatnonzero(rr >= A.rel(a))
            if len(ii):
                arr[k] = s + int(ii[0])
        st[nm] = arr
    bu = {"high": ([], []), "low": ([], [])}
    for side, px, ki in M.bu:
        bu[side][0].append(px); bu[side][1].append(ki)
    bu = {s: (np.array(v[0]), np.array(v[1], dtype=np.int64)) for s, v in bu.items()}
    _X.update(trend=tr, st=st, bu=bu)
    return D, _X


def _dirs(M, d):
    if d == 1:
        return M.o, M.h, M.l, M.c
    return -M.o, -M.l, -M.h, -M.c


def mod_at(D, k, m_rel):
    """bar index of the first bar of day k at or after trading-day minute m_rel (since 18:00)."""
    M = D["M"]
    d, s, e = M.days[k]
    rr = (M.mod[s:e] - 1080) % 1440
    ii = np.flatnonzero(rr >= m_rel)
    return s + int(ii[0]) if len(ii) else e


# ================================================================================================ signals
def legs(sess, struct, kk, disp, k):
    """The session's first directional leg on day k: dict(dir, a0 = session start, m = confirm bar, origin (trade space),
    origin_i, vwap_ok, trend_ok, s/e of the window) or None."""
    D, X = data()
    M = D["M"]
    a, conf_by, ent_by, _fl = SESS[sess]
    d, s, e = M.days[k]
    i0 = int(X["st"][sess][k])
    if i0 < 0 or i0 >= e - 2:
        return None
    zc = mod_at(D, k, A.rel(conf_by))
    if struct.startswith("or"):
        m0 = int(struct[2:]) // 5
        if zc - i0 < m0 + 2:
            return None
        hi, lo = float(M.h[i0:i0 + m0].max()), float(M.l[i0:i0 + m0].min())
        f = i0 + m0
    else:
        if sess == "lon":
            x = M.ctx[k].get("asia20")
            if not x or x[2] >= i0:
                return None
            hi, lo = x[0], x[1]
        else:
            if i0 - s < 12:
                return None
            hi, lo = float(M.h[s:i0].max()), float(M.l[s:i0].min())
        f = i0
    V, TR = D["vwap"], X["trend"]
    for m in range(f, zc):
        for dr, lvl in ((1, hi), (-1, lo)):
            o_, h_, l_, c_ = _dirs(M, dr)
            L = lvl * dr
            if c_[m] > L:
                oi = i0 + int(np.argmin(l_[i0:m + 1]))
                origin = float(l_[oi])
                # leg: from the origin forward; confirm when running high - origin >= kk ATR (from this bar on, while
                # still before the confirm-by time and without a close back inside the structure)
                for q in range(m, zc):
                    if c_[q] <= L:
                        return None
                    if l_[q] < origin:
                        return None
                    H = float(h_[oi:q + 1].max())
                    if H - origin < kk * float(M.atr[q]):
                        continue
                    if disp > 0:
                        body = (c_[oi:q + 1] - o_[oi:q + 1])
                        if not (body >= disp * M.atr[oi:q + 1]).any():
                            continue
                    vw = float(V[q]) * dr
                    return {"sess": sess, "dir": dr, "i0": i0, "m": q, "origin": origin, "oi": oi, "lvl": L, "k": k,
                            "vwap_ok": bool(c_[q] > vw), "trend_ok": bool(TR[q] * dr > 0)}
                return None
    return None


def zone_top(M, lg, zone, j, dr):
    """The zone's top (trade space) as known before bar j (bars < j), or None."""
    o_, h_, l_, c_ = _dirs(M, dr)
    oi = lg["oi"]
    if j - 1 < oi:
        return None
    H = float(h_[oi:j].max())
    if zone == "fib50":
        return lg["origin"] + 0.5 * (H - lg["origin"])
    if zone == "fvg":
        # most recent bullish FVG: l[x+1] > h[x-1], x+1 <= j-1, inside the leg (x-1 >= oi)
        for x in range(j - 2, oi, -1):
            if l_[x + 1] > h_[x - 1]:
                return float(l_[x + 1])
        return None
    if zone == "ob":
        at = M.atr
        fd = None
        for x in range(oi, j):
            if c_[x] - o_[x] >= 0.8 * at[x]:
                fd = x
                break
        if fd is None:
            return None
        for x in range(fd - 1, max(oi - 4, 0), -1):
            if c_[x] < o_[x]:
                return float(h_[x])
        return float(h_[oi])
    raise ValueError(zone)


def cisd_at(M, dr, lo_i, m, floor_i):
    """5m CISD at bar m: a close above the open of the first candle of the down-candle run into the low at lo_i (the run =
    the consecutive down-close candles ending at the low bar, or at the bar before it when the low bar closed up)."""
    o_, h_, l_, c_ = _dirs(M, dr)
    q = lo_i
    if c_[q] >= o_[q]:
        q -= 1
    if q < floor_i or c_[q] >= o_[q]:
        ref = h_[lo_i]
    else:
        while q - 1 >= floor_i and c_[q - 1] < o_[q - 1]:
            q -= 1
        ref = o_[q]
    return c_[m] > ref


def signals(lg, zone, trig, pbw_max=24):
    """First pullback into the zone after the leg's confirm bar and its trigger. Returns a list of dicts (one per stop mode)
    with touch offset (for the pbw cutoff), signal bar, stop (price), the pools (trade space) - or []."""
    D, X = data()
    M = D["M"]
    dr, k = lg["dir"], lg["k"]
    sess = lg["sess"]
    a, conf_by, ent_by, _fl = SESS[sess]
    d, s, e = M.days[k]
    ze = mod_at(D, k, A.rel(ent_by))
    o_, h_, l_, c_ = _dirs(M, dr)
    origin, oi, m0 = lg["origin"], lg["oi"], lg["m"]
    touch = None
    for j in range(m0 + 1, min(ze, m0 + 1 + pbw_max)):
        if l_[j] < origin:
            return []
        zt = zone_top(M, lg, zone, j, dr)
        if zt is None:
            continue
        if l_[j] <= zt:
            touch = j
            break
    if touch is None:
        return []
    off = touch - m0
    sig, lo_i = None, touch
    for m in range(touch, min(ze, touch + 7)):
        if l_[m] < origin:
            return []
        if l_[m] <= l_[lo_i]:
            lo_i = m
        if trig == "close":
            ok = c_[m] > h_[m - 1]
        else:
            ok = cisd_at(M, dr, lo_i, m, oi)
        if ok:
            sig = m
            break
    if sig is None:
        return []
    pb_low = float(l_[lo_i:sig + 1].min()) if lo_i <= sig else float(l_[sig])
    pb_low = min(pb_low, float(l_[touch:sig + 1].min()))
    if trig == "hunt":
        # second leg: the first entry's stop (pb_low) is taken, the leg origin holds, then a new CISD
        sw, sig2, lo2 = None, None, None
        for m in range(sig + 1, min(ze, sig + 25)):
            if l_[m] < origin:
                return []
            if sw is None:
                if l_[m] >= pb_low:
                    continue
                sw, lo2 = m, m
            if l_[m] <= l_[lo2]:
                lo2 = m
            if cisd_at(M, dr, lo2, m, sw):
                sig2 = m
                break
        if sig2 is None:
            return []
        sig = sig2
        pb_low = float(l_[sw:sig + 1].min())
    out = []
    for stopm in ("pb", "origin"):
        sp = (pb_low if stopm == "pb" else min(origin, pb_low)) - TICK
        out.append({"stopm": stopm, "off": off, "i": sig, "dir": dr, "k": k, "day": str(d), "stop_d": sp, "sess": sess,
                    "pools": pools(lg, sig)})
    return out


def pools(lg, m):
    """Liquidity pools in the trend direction known at bar m's close (trade space, sorted): the leg high, the day's high so
    far, PDH / PWH / PMH, the Asia box high (closed), the London 02:00-05:00 box high (closed, for NY), untaken build-up
    (equal) highs - each only if no high since its known time reached it."""
    D, X = data()
    M = D["M"]
    dr, k = lg["dir"], lg["k"]
    o_, h_, l_, c_ = _dirs(M, dr)
    d, s, e = M.days[k]
    x = M.ctx[k]
    dh = float(h_[s:m + 1].max())
    P = {float(h_[lg["oi"]:m + 1].max()), dh}
    up = "h" if dr == 1 else "l"
    for nm in ("pd", "pw", "pm"):
        v = x.get(nm + up)
        if v is not None and v * dr > dh:
            P.add(float(v) * dr)
    for nm in ("asia20", "lon25"):
        b = x.get(nm)
        if b and b[2] < m:
            v = (b[0] if dr == 1 else b[1]) * dr
            if v > float(h_[b[2] + 1:m + 1].max()):
                P.add(float(v))
    px, ki = X["bu"]["high" if dr == 1 else "low"]
    if len(px):
        lo_ = np.searchsorted(ki, m - 576)
        hi_ = np.searchsorted(ki, m, side="right")
        for j in range(lo_, hi_):
            v = float(px[j]) * dr
            if v > float(h_[ki[j]:m + 1].max()):
                P.add(v)
    return sorted(P)


# ================================================================================================ execution
_PATH = {}


def path(k, i_entry, flat_mod):
    key = (k, i_entry, flat_mod)
    if key in _PATH:
        return _PATH[key]
    D, _ = data()
    M, B1 = D["M"], D["B1"]
    d, s, e = M.days[k]
    t0 = int(M.t[i_entry])
    tf = int(M.t[s]) + (A.rel(flat_mod) - A.rel(M.mod[s])) * 60
    r = None
    if k in D["full"]:
        a = int(np.searchsorted(B1.t, t0))
        z = int(np.searchsorted(B1.t, tf))
        if z > a and int(B1.t[a]) == t0:
            r = (B1.t[a:z], B1.o[a:z], B1.h[a:z], B1.l[a:z], B1.c[a:z], 60)
    if r is None:
        z = min(e, int(np.searchsorted(M.t, tf)))
        r = (M.t[i_entry:z], M.o[i_entry:z], M.h[i_entry:z], M.l[i_entry:z], M.c[i_entry:z], 300)
    if len(_PATH) > 20000:
        _PATH.clear()
    _PATH[key] = r
    return r


def _first(mask, start=0):
    j = np.flatnonzero(mask[start:])
    return int(j[0]) + start if len(j) else len(mask)


def simulate(c, exits=EXITS):
    """One candidate through the exit configs -> {exit: trade (common format + extras) or None}."""
    D, _ = data()
    M = D["M"]
    d, i = c["dir"], c["i"]
    out = {}
    if i + 1 >= M.n or M.day_of[i + 1] != c["k"]:
        return out
    for ex in exits:
        tgt, be, hold = ex
        flat = SESS[c["sess"]][3] if hold == "s" else EOD
        T, O, H, L, C, secs = path(c["k"], i + 1, flat)
        if len(T) == 0:
            continue
        if d == 1:
            o, h, l, cl = O, H, L, C
        else:
            o, h, l, cl = -O, -L, -H, -C
        e = float(o[0]) + TICK
        sp = c["stop_d"]
        risk = e - sp
        if not (6.0 <= risk <= 80.0):
            continue
        P = [p for p in c["pools"] if p > e]
        part = tgt in ("P2", "PS")
        if tgt in ("S", "S3"):
            cand = [p for p in P if p - e >= 1.0 * risk]
            if not cand:
                continue
            tg = min(cand[0], e + (8.0 if tgt == "S" else 3.0) * risk)
        elif tgt == "PS":
            cand = [p for p in P if p - e >= 1.5 * risk]
            tg = min(cand[0], e + 8.0 * risk) if cand else e + 2.0 * risk
        elif tgt == "P2":
            tg = e + 2.0 * risk
        else:
            tg = e + float(tgt[1:]) * risk
        q = lit.qty_for(risk)
        if q <= 0:
            continue
        n = len(l)
        s0 = _first(l <= sp)
        if part and q >= 2:
            q1 = q // 2
            t1 = e + 1.0 * risk
            j1 = _first(h >= t1 + TICK)
            if s0 <= j1 and s0 < n:                         # stopped before the partial
                j, px, kind = s0, min(float(o[s0]), sp) - TICK, "STOP"
                legs_ = [(q, px)]
            elif j1 < n:
                bes = e + BE_OFF
                s2 = _first(l <= bes, j1 + 1)
                t2 = _first(h >= tg + TICK, j1)
                if t2 == j1 and tg > t1:                    # the same bar cannot fill both on the way (conservative)
                    t2 = _first(h >= tg + TICK, j1 + 1)
                if s2 <= t2 and s2 < n:
                    j, px2, kind = s2, min(float(o[s2]), bes) - TICK, "PART_BE"
                elif t2 < n:
                    j, px2, kind = t2, max(float(o[t2]), tg) if t2 > j1 else tg, "PART_TARGET"
                else:
                    j, px2, kind = n - 1, float(cl[n - 1]) - TICK, "PART_TIME"
                legs_ = [(q1, max(float(o[j1]), t1)), (q - q1, px2)]
            else:
                j, px, kind = n - 1, float(cl[n - 1]) - TICK, "TIME"
                legs_ = [(q, px)]
        else:
            tt = _first(h >= tg + TICK)
            b = _first(h >= e + be * risk) if be else n
            bes = e + BE_OFF
            s_pre = s0 if s0 <= b else n
            s_post = _first(l <= bes, b + 1) if (b < n and s_pre == n) else n
            si = s_pre if s_pre < n else s_post
            if si <= tt and si < n:
                j = si
                lv = sp if si == s_pre else bes
                px, kind = min(float(o[j]), lv) - TICK, ("STOP" if si == s_pre else "BE")
            elif tt < n:
                j, px, kind = tt, max(float(o[tt]), tg), "TARGET"
            else:
                j, px, kind = n - 1, float(cl[n - 1]) - TICK, "TIME"
            legs_ = [(q, px)]
        ptsq = sum(qq * (pp - e) for qq, pp in legs_)
        pts = ptsq / q
        pnl = ptsq * PV - COMM * q
        xb = e + pts
        w1 = float(min(0.0, l[:j + 1].min() - e))
        if kind in ("STOP", "BE", "PART_BE", "TARGET", "PART_TARGET"):
            w1 = max(w1, -(risk + TICK))
        out[ex] = {"day": c["day"], "entry_t": int(T[0]), "exit_t": int(T[j]) + secs, "dir": d, "entry": round(e * d, 2),
                   "stop": round(sp * d, 2), "target": round(tg * d, 2), "exit": round(xb * d, 4), "exit_kind": kind,
                   "r": round(pnl / (risk * PV * q), 3), "qty": q, "pnl_usd": round(pnl, 2), "setup": c.get("setup", "hq"),
                   "risk": round(risk, 2), "pts": round(pts, 4), "w1": round(w1, 4), "tgt_pts": round(tg - e, 2),
                   "sess": c["sess"], "w": c["sess"]}
    return out


# ================================================================================================ grid
def gen_key(v):
    return "|".join(str(v[d]) for d in DIMS)


def parse(key):
    return dict(zip(DIMS, key.split("|")))


def merge(a, b):
    """Two sessions' trades in one account: entry order, one position at a time."""
    allt = sorted(a + b, key=lambda t: t["entry_t"])
    out, busy = [], -1
    for t in allt:
        if t["entry_t"] < busy:
            continue
        out.append(t)
        busy = t["exit_t"]
    return out


_WEEK = {}


def week_of(day):
    if day not in _WEEK:
        y, w, _ = dt.date.fromisoformat(day).isocalendar()
        _WEEK[day] = y * 100 + w
    return _WEEK[day]


def stats(T, span, sessions=None):
    """Money and quality at the LIT size (costs in) for one span."""
    D, _ = data()
    a, z = SPANS[span]
    ss = [x for x in (sessions or D["sess"]) if a <= x <= z]
    TT = [t for t in T if a <= t["day"] <= z]
    nw = max(1.0, len(ss) / 5.0)
    weeks = collections.Counter(week_of(x) for x in ss)
    if not TT:
        return {"n": 0, "tpw": 0.0, "wk2": 0.0, "net": 0, "pf": None, "win1": None, "win": None, "be": None, "avgw": None,
                "exp_r": None, "exp_usd": None, "per_month": 0, "dd": 0, "t": 0.0}
    p = np.array([t["pnl_usd"] for t in TT])
    r = np.array([t["r"] for t in TT])
    tw = collections.Counter(week_of(t["day"]) for t in TT)
    gl = -p[p < 0].sum()
    eq = np.cumsum(p)
    dd = float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min())
    sd = float(r.std(ddof=1)) if len(r) > 1 else 0.0
    be = np.array([t["exit_kind"] in ("BE", "PART_BE") for t in TT])
    return {"n": len(TT), "tpw": round(len(TT) / nw, 2), "wk2": round(100.0 * sum(1 for w in weeks if tw.get(w, 0) >= 2) / max(1, len(weeks)), 1),
            "win1": round(100.0 * float((r >= 1.0).mean()), 1), "win": round(100.0 * float((p > 0).mean()), 1),
            "be": round(100.0 * float(be.mean()), 1), "avgw": round(float(r[r > 0].mean()), 2) if (r > 0).any() else None,
            "exp_r": round(float(r.mean()), 3), "exp_usd": round(float(p.mean())), "pf": round(float(p[p > 0].sum() / gl), 2) if gl > 0 else 99.0,
            "net": round(float(p.sum())), "per_month": round(float(p.sum()) / max(1.0, len(ss) / 21.0)), "dd": round(dd),
            "t": round(float(r.mean()) / sd * np.sqrt(len(r)), 2) if sd > 0 else 0.0}


def leg_jobs():
    return list(itertools.product(ORDER["struct"], ORDER["k"], ORDER["disp"]))


def job_trades(struct, kk, disp, keep=None):
    """Every variant of one leg config (struct, k, disp) -> {variant key: [trades]}. keep = a set of keys to return (else
    all)."""
    D, X = data()
    M = D["M"]
    sims = {}
    per = collections.defaultdict(list)        # (sess, vwap, trend, zone, pbw, trig, stopm, ex) -> trades
    for k, (d, s, e) in enumerate(M.days):
        if str(d) not in D["sset"]:
            continue
        for sess in ("lon", "ny"):
            lg = legs(sess, struct, float(kk), float(disp), k)
            if not lg:
                continue
            for zone in ORDER["zone"]:
                for trig in ORDER["trig"]:
                    for c in signals(lg, zone, trig):
                        key = (k, c["i"], c["dir"], round(c["stop_d"], 2), sess)
                        if key not in sims:
                            sims[key] = simulate(c)
                        res = sims[key]
                        for pbw in ORDER["pbw"]:
                            if c["off"] > int(pbw):
                                continue
                            for vw in ("0", "1"):
                                if vw == "1" and not lg["vwap_ok"]:
                                    continue
                                for tr in ("0", "1"):
                                    if tr == "1" and not lg["trend_ok"]:
                                        continue
                                    for ex, t in res.items():
                                        per[(sess, vw, tr, zone, pbw, trig, c["stopm"], ex)].append(t)
    out = {}
    for vw, tr, zone, pbw, trig, stopm, ex in itertools.product(("0", "1"), ("0", "1"), ORDER["zone"], ORDER["pbw"], ORDER["trig"],
                                                                 ORDER["stopm"], EXITS):
        L = per.get(("lon", vw, tr, zone, pbw, trig, stopm, ex), [])
        N = per.get(("ny", vw, tr, zone, pbw, trig, stopm, ex), [])
        for sess, TT in (("lon", L), ("ny", N), ("both", None)):
            v = {"sess": sess, "struct": struct, "k": kk, "disp": disp, "vwap": vw, "trend": tr, "zone": zone, "pbw": pbw,
                 "trig": trig, "stopm": stopm, "tgt": ex[0], "be": str(ex[1]), "hold": ex[2]}
            key = gen_key(v)
            if keep is not None and key not in keep:
                continue
            out[key] = TT if TT is not None else merge(L, N)
    return out


def _grid_job(job):
    struct, kk, disp = job
    t0 = time.time()
    R = job_trades(struct, kk, disp)
    S = {key: {sp: stats(T, sp) for sp in GRID_SPANS} for key, T in R.items()}
    return S, f"{job} {len(R)} variants {time.time() - t0:.0f}s"


GRID = os.path.join(ROOT, "research", "runs", "_cache", "hq_cont_grid.json.gz")   # ~186k variants, too big to commit


def cmd_grid(procs=4):
    from multiprocessing import Pool
    data()
    J = leg_jobs()
    out = {}
    t0 = time.time()
    with Pool(procs) as pool:
        for S, msg in pool.imap_unordered(_grid_job, J):
            out.update(S)
            print(msg, f"total {time.time() - t0:.0f}s", flush=True)
    # compact: list of per-span tuples
    cols = ["n", "tpw", "wk2", "win1", "win", "be", "avgw", "exp_r", "exp_usd", "pf", "net", "per_month", "dd", "t"]
    comp = {k: {sp: [v[sp][c] for c in cols] for sp in GRID_SPANS} for k, v in out.items()}
    _dump({"cols": cols, "spans": list(GRID_SPANS), "dims": DIMS, "v": comp}, GRID, separators=(",", ":"))
    print(len(out), "variants", flush=True)


_G = {}


def grid():
    if not _G:
        G = _load(GRID)
        cols = G["cols"]
        _G.update({k: {sp: dict(zip(cols, x)) for sp, x in v.items()} for k, v in G["v"].items()})
    return _G


def _many_job(a):
    (struct, kk, disp), keys = a
    return job_trades(struct, kk, disp, keep=set(keys))


TCACHE = os.path.join(ROOT, "research", "runs", "_cache", "hq_cont_trades.pkl")
_TC = {}


def trades_many(keys, procs=4):
    """{key: trades} for many variants: one job_trades run per leg config, in parallel; cached on disk."""
    import pickle
    from multiprocessing import Pool
    if not _TC and os.path.exists(TCACHE):
        _TC.update(pickle.load(open(TCACHE, "rb")))
    need = [k for k in keys if k not in _TC]
    if need:
        by = collections.defaultdict(list)
        for k in need:
            p = parse(k)
            by[(p["struct"], p["k"], p["disp"])].append(k)
        with Pool(min(procs, len(by))) as pool:
            for R in pool.imap_unordered(_many_job, list(by.items())):
                _TC.update(R)
        pickle.dump(dict(_TC), open(TCACHE, "wb"))
    return {k: _TC[k] for k in keys}


def trades_of(key):
    return trades_many([key])[key]


# ================================================================================================ picking
def neighbours(key, keys):
    p = parse(key)
    out = []
    for dm in DIMS:
        seq = ORDER[dm]
        j = seq.index(p[dm])
        cand = [x for x in seq if x != p[dm]] if dm in UNORDERED else [seq[x] for x in (j - 1, j + 1) if 0 <= x < len(seq)]
        for u in cand:
            q = dict(p)
            q[dm] = u
            if dm in ("tgt",) and u in ("P2", "PS") and q["be"] != "None":
                continue
            if dm == "be" and q["tgt"] in ("P2", "PS"):
                continue
            kq = gen_key(q)
            if kq in keys:
                out.append(kq)
    return out


def eligible(s, min_tpw=2.0, min_n=30):
    """Owner's frequency (2+ a week) and quality floor: n >= 30, PF >= 1.2, average winner >= 1.5R."""
    return (s["n"] >= min_n and s["tpw"] >= min_tpw and s["net"] > 0 and (s["pf"] or 0) >= 1.2 and (s["avgw"] or 0) >= 1.5)


def score_of(s):
    """Pick score: the t-stat of net R (expectancy x sqrt(n) / sd), so a high win rate, a big winner and enough trades all
    count; ties are rare."""
    return s["t"] or 0.0


def pick(on="H1", top=3, min_tpw=2.0, exclude_same_leg=True, mode="t"):
    """Plateau pick on one span: eligible variants (2+ a week, n >= 30, PF >= 1.2, avg winner >= 1.5R) ranked by
    0.5 x own score + 0.5 x median score of the one-step neighbours. Returns the top distinct picks (different setup:
    sess/struct/k/zone/trig/stopm) and the eligible count."""
    G = grid()
    keys = set(G)
    sc = {}
    for k, v in G.items():
        s = v[on]
        if not eligible(s, min_tpw):
            continue
        own = score_of(s) if mode == "t" else (s["win1"] or 0) * 0.05 + score_of(s)
        nb = neighbours(k, keys)
        med = float(np.median([score_of(G[o][on]) for o in nb])) if nb else 0.0
        sc[k] = (0.5 * own + 0.5 * med, own, med, len(nb))
    ranked = sorted(sc, key=lambda k: -sc[k][0])
    picks, seen = [], set()
    for k in ranked:
        p = parse(k)
        sig = (p["sess"], p["struct"], p["zone"], p["trig"]) if exclude_same_leg else k
        if sig in seen:
            continue
        seen.add(sig)
        picks.append({"key": k, "plateau": round(sc[k][0], 2), "own": sc[k][1], "nb_med": round(sc[k][2], 2), "nb_n": sc[k][3]})
        if len(picks) >= top:
            break
    return picks, len(sc), ranked


def months(T, a="2021-01-01", z="2026-12-31"):
    m = collections.defaultdict(lambda: [0, 0.0, 0])
    for t in T:
        if a <= t["day"] <= z:
            x = m[t["day"][:7]]
            x[0] += 1; x[1] += t["pnl_usd"]; x[2] += t["r"] >= 1.0
    return {k: {"n": v[0], "net": round(v[1]), "win1": v[2]} for k, v in sorted(m.items())}


def drop_best(T, span, n=5):
    a, z = SPANS[span]
    p = sorted((t["pnl_usd"] for t in T if a <= t["day"] <= z), reverse=True)
    return round(sum(p[n:]))


def entry_window(sess):
    """Bars where a pick's signals can sit (for the random-time placebo): confirm-by start .. entries-until."""
    a, cb, eb, _ = SESS[sess]
    return a, eb


def placebo(key, T, span, n_draw=200, seed=11, kind="time"):
    """kind 'time': random entries on the pick's own days and sessions, same direction, a random 5m bar of the session's
    entry window, the pick's own stop distance and target structure (R of the drawn trade), same exit rule.
    kind 'dir': the pick's own entry bars and stops, random direction (stop mirrored), same R target.
    Returns the share of draws at least as good as the pick (net $; win >= 1R % and PF together)."""
    D, _ = data()
    M = D["M"]
    p = parse(key)
    a_, z_ = SPANS[span]
    TT = [t for t in T if a_ <= t["day"] <= z_]
    if len(TT) < 5:
        return None
    rng = np.random.default_rng(seed + int(hashlib.md5((key + kind + span).encode()).hexdigest()[:6], 16) % 1000)
    hold = p["hold"]
    be = None if p["be"] == "None" else float(p["be"])
    tg = p["tgt"]
    nets, w1s, pfs = [], [], []
    m0s = {}
    for _ in range(n_draw):
        P = []
        for t in TT:
            k = D["dmap"][t["day"]]
            risk = float(t["risk"])
            rr = float(t["tgt_pts"]) / risk
            ex_tg = tg if tg not in ("S", "S3", "PS") else ("R%.3f" % rr if tg != "PS" else "PS")
            for _try in range(20):
                if kind == "time":
                    # from the leg's confirm bar (the direction is known only then) to the session's last entry bar
                    a, eb = entry_window(t["sess"])
                    if (k, t["sess"]) not in m0s:
                        lg = legs(t["sess"], p["struct"], float(p["k"]), float(p["disp"]), k)
                        m0s[(k, t["sess"])] = lg["m"] if lg else mod_at(D, k, A.rel(a))
                    i_lo = m0s[(k, t["sess"])]; i_hi = mod_at(D, k, A.rel(eb))
                    if i_hi - i_lo < 2:
                        break
                    m = int(rng.integers(i_lo, i_hi - 1))
                    dr = int(t["dir"])
                else:
                    m = int(np.searchsorted(M.t, int(t["entry_t"]) // 300 * 300)) - 1
                    dr = 1 if rng.random() < 0.5 else -1
                e0 = float(M.o[m + 1]) * dr + TICK
                c = {"k": k, "day": t["day"], "i": m, "dir": dr, "stop_d": e0 - risk, "sess": t["sess"],
                     "pools": [e0 + rr * risk + 1e-9] if tg == "PS" else [], "setup": "placebo"}
                ex = (ex_tg if not ex_tg.startswith("R") else ex_tg, be, hold)
                x = _sim_any(c, ex)
                if x is not None:
                    P.append(x)
                    break
        if not P:
            continue
        pp = np.array([x["pnl_usd"] for x in P]); r = np.array([x["r"] for x in P])
        gl = -pp[pp < 0].sum()
        nets.append(float(pp.sum())); w1s.append(100.0 * float((r >= 1.0).mean())); pfs.append(float(pp[pp > 0].sum() / gl) if gl > 0 else 99.0)
    s = stats(T, span)
    nets, w1s, pfs = np.array(nets), np.array(w1s), np.array(pfs)
    return {"span": span, "kind": kind, "n": len(TT), "draws": len(nets), "p_net": round(float((nets >= s["net"]).mean()), 3),
            "p_win_pf": round(float(((w1s >= s["win1"]) & (pfs >= s["pf"])).mean()), 3),
            "rand_net_p50": round(float(np.median(nets))), "rand_net_p90": round(float(np.percentile(nets, 90))),
            "rand_win1_p50": round(float(np.median(w1s)), 1), "pick_net": s["net"], "pick_win1": s["win1"]}


def _sim_any(c, ex):
    """simulate with an arbitrary fixed-R target string 'R<x>'."""
    tgt = ex[0]
    if tgt.startswith("R") and tgt not in ("R1.5", "R2", "R3"):
        r = simulate(c, [ex])
        return r.get(ex)
    return simulate(c, [ex]).get(ex)


def chance(n_legs=4, per_leg=30, seed=5):
    """Chance level: random-time strategies built on random grid variants' own trades (same days, sessions, directions,
    stops and target R; one random draw each): how often such a strategy is positive in H2, 2025 and 2021-24 together,
    and in all four spans."""
    G = grid()
    rng = np.random.default_rng(seed)
    legs_ = leg_jobs()
    chosen = [legs_[int(j)] for j in rng.choice(len(legs_), n_legs, replace=False)]
    keys = []
    for lg in chosen:
        ks = [k for k, v in G.items() if tuple(parse(k)[d] for d in ("struct", "k", "disp")) == lg and v["H1"]["n"] >= 30]
        keys += [ks[int(j)] for j in rng.choice(len(ks), min(per_leg, len(ks)), replace=False)]
    TT = trades_many(keys)
    hits3 = hits4 = n = 0
    for k in keys:
        R = [placebo(k, TT[k], sp, n_draw=1, seed=int(rng.integers(1 << 30)), kind="time") for sp in GRID_SPANS]
        if any(x is None for x in R):
            continue
        n += 1
        hits3 += all(x["rand_net_p50"] > 0 for x in R[1:])
        hits4 += all(x["rand_net_p50"] > 0 for x in R)
    return {"strategies": n, "positive_H2_2025_2021-24": hits3, "rate3": round(hits3 / max(1, n), 4),
            "positive_all_4": hits4, "rate4": round(hits4 / max(1, n), 4)}


def family_counts():
    """Multiple-testing view: how many variants were scored, how many distinct trade sets, how many eligible on H1, and of
    those how many hold in H2 / 2025 / 2021-24 (net > 0) - vs the rate across all variants; the H1-vs-H2 correlation of
    the t-stat."""
    G = grid()
    allk = list(G)
    el = [k for k in allk if eligible(G[k]["H1"])]
    sig = {}
    for k in allk:
        s = G[k]
        sig.setdefault(tuple((s[sp]["n"], s[sp]["net"]) for sp in GRID_SPANS), k)

    def rate(ks, f):
        return round(100.0 * sum(1 for k in ks if f(G[k])) / max(1, len(ks)), 1)
    pos3 = lambda v: v["H2"]["net"] > 0 and v["2025"]["net"] > 0 and v["2021-24"]["net"] > 0  # noqa: E731
    h1 = np.array([G[k]["H1"]["t"] for k in allk if G[k]["H1"]["n"] >= 20 and G[k]["H2"]["n"] >= 10])
    h2 = np.array([G[k]["H2"]["t"] for k in allk if G[k]["H1"]["n"] >= 20 and G[k]["H2"]["n"] >= 10])
    l1 = np.array([G[k]["2021-24"]["t"] for k in allk if G[k]["2021-24"]["n"] >= 50 and G[k]["2025"]["n"] >= 20])
    l2 = np.array([G[k]["2025"]["t"] for k in allk if G[k]["2021-24"]["n"] >= 50 and G[k]["2025"]["n"] >= 20])
    top = sorted(el, key=lambda k: -G[k]["H1"]["t"])[:50]
    return {"variants": len(allk), "distinct_trade_sets": len(sig), "eligible_h1": len(el),
            "all_pos_h2": rate(allk, lambda v: v["H2"]["net"] > 0), "elig_pos_h2": rate(el, lambda v: v["H2"]["net"] > 0),
            "top50_pos_h2": rate(top, lambda v: v["H2"]["net"] > 0),
            "all_pos3": rate(allk, pos3), "elig_pos3": rate(el, pos3), "top50_pos3": rate(top, pos3),
            "all_pos_2021_24": rate(allk, lambda v: v["2021-24"]["net"] > 0),
            "all_pos_2025": rate(allk, lambda v: v["2025"]["net"] > 0),
            "corr_t_h1_h2": round(float(np.corrcoef(h1, h2)[0, 1]), 3) if len(h1) > 10 else None,
            "corr_t_2124_2025": round(float(np.corrcoef(l1, l2)[0, 1]), 3) if len(l1) > 10 else None,
            "mean_t": {sp: round(float(np.mean([G[k][sp]["t"] for k in allk if G[k][sp]["n"] >= 10])), 3) for sp in GRID_SPANS},
            "mean_exp_r": {sp: round(float(np.mean([G[k][sp]["exp_r"] for k in allk if G[k][sp]["n"] >= 10])), 3) for sp in GRID_SPANS}}


def describe(key, T=None, placebos=True):
    G = grid()
    T = T if T is not None else trades_of(key)
    sp = {s: stats(T, s) for s in ("H1", "H2", "2026", "2025", "2021-24")}
    nb = neighbours(key, set(G))
    rec = {"key": key, "params": parse(key), "spans": sp,
           "drop_best5": {s: drop_best(T, s) for s in ("H1", "H2", "2025", "2021-24")},
           "months": months(T), "neighbours": {"n": len(nb),
                                                "h1_pos": sum(1 for o in nb if G[o]["H1"]["net"] > 0),
                                                "h2_pos": sum(1 for o in nb if G[o]["H2"]["net"] > 0),
                                                "2025_pos": sum(1 for o in nb if G[o]["2025"]["net"] > 0),
                                                "2124_pos": sum(1 for o in nb if G[o]["2021-24"]["net"] > 0),
                                                "h2_med_net": round(float(np.median([G[o]["H2"]["net"] for o in nb]))) if nb else None,
                                                "2124_med_net": round(float(np.median([G[o]["2021-24"]["net"] for o in nb]))) if nb else None}}
    if placebos:
        rec["placebo"] = {f"{kind}|{s}": placebo(key, T, s, kind=kind) for kind in ("time", "dir") for s in ("H1", "H2", "2025", "2021-24")}
    return rec


PICKS = os.path.join(OUT, "picks.json")


def cmd_pick():
    G = grid()
    t0 = time.time()
    res = {"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "variants": len(G)}
    ph1, n1, r1 = pick("H1")
    pl, nl, rl_ = pick("2021-24")
    relaxed = False
    if not pl:                       # nothing at 2+ a week holds the floor over 2021-24: relax the frequency to 1.5 a week
        pl, nl, rl_ = pick("2021-24", min_tpw=1.5)
        relaxed = True
    trades_many([p["key"] for p in ph1 + pl])
    res["h1"] = {"eligible": n1, "picks": []}
    res["pre2025"] = {"eligible": nl, "picks": [], "relaxed_tpw_1.5": relaxed,
                      "eligible_at_2pw": sum(1 for v in G.values() if eligible(v["2021-24"]))}
    for p in ph1:
        print("H1 pick", p, flush=True)
        res["h1"]["picks"].append({**p, **describe(p["key"])})
    for p in pl:
        print("pre-2025 pick", p, flush=True)
        res["pre2025"]["picks"].append({**p, **describe(p["key"])})
    # top-10 H1 ranks (no placebo) to show the spread
    res["h1_top10"] = [{"key": k, "spans": G[k]} for k in r1[:10]]
    res["pre2025_top10"] = [{"key": k, "spans": G[k]} for k in rl_[:10]]
    res["family"] = family_counts()
    print("family", res["family"], flush=True)
    res["chance"] = chance()
    print("chance", res["chance"], f"{time.time() - t0:.0f}s", flush=True)
    _dump(res, PICKS, indent=1, default=float)


PEEKED = [  # chosen AFTER looking at every period (research/hq/family.json): not a fair out-of-sample pick, shown as leads
    ("both|or30|3|0|0|1|fvg|12|close|pb|R3|1.0|eod", "peeked: the variant at 2+ a week positive in all four periods with the best worst-period PF"),
    ("ny|or30|4|0.8|0|1|fvg|24|close|pb|R1.5|1.0|eod", "peeked: the variant positive in all four periods with the best worst-period t-stat (NY only, ~1 a week)"),
]


def cmd_peek():
    P = _load(PICKS)
    trades_many([k for k, _ in PEEKED])
    P["peeked"] = {"picks": [{"key": k, "how": how, **describe(k)} for k, how in PEEKED]}
    for p in P["peeked"]["picks"]:
        print("peeked", p["key"], {s: (v["n"], v["tpw"], v["win1"], v["pf"], v["net"]) for s, v in p["spans"].items()}, flush=True)
    _dump(P, PICKS, indent=1, default=float)


# ================================================================================================ evals
EVALS = os.path.join(OUT, "evals.json")


def eval_block(T, src):
    from tools import second_mix as SM
    UL = list(SM.units()["LIT"])
    UU = A.my_units(T, src)
    o = {}
    for sp in ("H1", "H2", "2025", "2021-24"):
        o[sp] = {"50k_need0.5": A.score_50k(UL + UU, "need0.5", sp, 2)[0],
                 "50k_usd300_safe_dll": A.score_50k(UL + UU, "usd300_safe_dll", sp, 2)[0],
                 "25k_alone": A.score_acct(SM.no_hedge(UU), "builder25k", sp, 2)[0]}
    return o


def cmd_evals():
    from tools import second_mix as SM
    P = _load(PICKS)
    UL = list(SM.units()["LIT"])
    res = {"lit_alone_50k": {sp: A.score_50k(UL, "usd300", sp, 2)[0] for sp in ("H1", "H2", "2025", "2021-24")}, "picks": {}}
    for grp in ("h1", "pre2025", "peeked"):
        for j, p in enumerate(P.get(grp, {}).get("picks", [])):
            T = trades_of(p["key"])
            res["picks"][f"{grp}_{j + 1}"] = {"key": p["key"], **eval_block(T, f"HQ{grp}{j + 1}")}
            print(grp, j + 1, {sp: (v["50k_need0.5"]["p10"], v["50k_need0.5"]["f10"], v["25k_alone"]["p10"], v["25k_alone"].get("dead10"))
                               for sp, v in res["picks"][f"{grp}_{j + 1}"].items() if sp != "key"}, flush=True)
    _dump(res, EVALS, indent=1, default=float)


# ================================================================================================ save
COMMON = ("day", "entry_t", "exit_t", "dir", "entry", "stop", "target", "exit", "exit_kind", "r", "qty", "pnl_usd", "setup")


def rules_of(key):
    p = parse(key)
    sl = {"lon": "London (leg confirmed 02:00-05:00 ET, entries until 07:30)", "ny": "NY (leg confirmed 09:30-11:30 ET, entries until 12:00)",
          "both": "London (02:00-05:00 leg, entries until 07:30) and NY (09:30-11:30 leg, entries until 12:00), one position at a time"}[p["sess"]]
    st = {"or15": "the session's first 15 minutes' range", "or30": "the session's first 30 minutes' range",
          "box": "the range before the session (Asia 20:00-00:00 for London, the overnight 18:00-09:30 for NY)"}[p["struct"]]
    zn = {"fib50": "the 50% retracement of the leg", "fvg": "the leg's most recent 5m fair value gap",
          "ob": "the leg's order block (last opposite candle before the first big candle)"}[p["zone"]]
    tr = {"close": "a 5m close beyond the prior candle's high (long) / low (short)",
          "cisd": "a 5m CISD back in the trend (close beyond the open of the candle run into the pullback extreme)",
          "hunt": "the second leg: the first pullback's extreme (the first entry's stop) is swept, the leg origin holds, then a new 5m CISD"}[p["trig"]]
    tg = {"R1.5": "1.5R", "R2": "2R", "R3": "3R", "S3": "the next liquidity pool in the trend direction (>= 1R), capped at 3R",
          "S": "the next liquidity pool in the trend direction (>= 1R), banked at 8R",
          "P2": "half at 1R, the rest at 2R (stop to entry + 1.25 after the half)",
          "PS": "half at 1R, the rest at the next pool >= 1.5R (else 2R), stop to entry + 1.25 after the half"}[p["tgt"]]
    out = [f"Session: {sl}.", f"Opening structure: {st}.",
           f"Directional leg: the session's first 5m close beyond it, leg >= {p['k']} x the 5m ATR(14) from the session's low (high)"
           + (f", with a candle body >= {p['disp']} ATR in the leg" if p["disp"] != "0" else "") + "; only the first leg of the session counts.",
           "Filters: " + ", ".join(x for x in (("close on the trend side of the 18:00 session VWAP" if p["vwap"] == "1" else ""),
                                               ("1h EMA 21 vs 50 in the trend direction" if p["trend"] == "1" else "")) if x) if (p["vwap"] == "1" or p["trend"] == "1") else "Filters: none.",
           f"Entry zone: the first pullback into {zn} within {int(p['pbw']) * 5} minutes of the leg; below the leg origin first = no trade.",
           f"Trigger (within 30 minutes of the touch): {tr}; entry at the next 5m open + 1 tick.",
           "Stop: 1 tick beyond " + ("the pullback's protected low (high)" if p["stopm"] == "pb" else "the leg origin") + " (6-80 pts, else no trade).",
           f"Target: {tg}." + ("" if p["be"] == "None" else " Breakeven (entry + 1.25 pts) once +1R was reached."),
           "Time exit: " + ("London 09:25 / NY 13:30" if p["hold"] == "s" else "15:55 ET") + ". One trade a session.",
           "Size: $800 risk up to a 20-pt stop, then 800 x 20 / stop (max 40 micros); $1.90 a micro, 1 tick slippage on market fills."]
    return out


def run_trades(T):
    out = []
    for t in T:
        q = int(t["qty"])
        w1 = t.get("w1")
        low = min(0.0, (w1 * PV * q - COMM * q) if w1 is not None else 0.0, t["pnl_usd"])
        out.append({"day": t["day"], "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "dir": int(t["dir"]), "r": float(t["r"]),
                    "pnl": float(t["pnl_usd"]), "risk_pts": float(t["risk"]), "qty": q, "risk_usd": round(float(t["risk"]) * PV * q, 2),
                    "half": False, "exit": t["exit_kind"], "trigger": t["setup"], "mfe": None, "mae": None, "bars_held": None,
                    "regime": t.get("sess", ""), "mult": None, "low": round(low, 2)})
    return out


def _h(s):
    return (f"{s['n']} trades ({s['tpw']}/wk, {s['wk2']}% weeks 2+), win >= 1R {s['win1']}%, BE {s['be']}%, avg winner {s['avgw']}R, "
            f"exp {s['exp_r']}R / ${s['exp_usd']}, PF {s['pf']}, net {s['net']:+,} (${s['per_month']:,}/mo), DD {s['dd']:,}")


def cmd_save():
    from tools import runlib as rl
    D, _ = data()
    P = _load(PICKS)
    E = _load(EVALS)
    Q = ("Owner 2026-10-23: a strategy that trades 2+ times a week, high-quality setups, high probability and high profit - trend "
         "continuation with structure (first pullback after a directional session leg).")
    index = {}
    for grp, how in (("h1", "picked on 2026 H1 (plateau), H2 / 2025 / 2021-24 untouched"),
                     ("pre2025", "picked on 2021-11..2024-12 (plateau, 1.5+ a week: nothing at 2+ a week qualified), 2025 / 2026 untouched"),
                     ("peeked", "chosen after looking at every period (not out of sample)")):
        for j, p in enumerate(P.get(grp, {}).get("picks", [])):
            fid = f"{grp}_{j + 1}"
            key = p["key"]
            T = trades_of(key)
            for t in T:
                t["setup"] = f"HQ continuation {fid}"
            ev = E["picks"].get(fid, {})
            rec = {"id": fid, "key": key, "how_picked": how, "params": parse(key), "rules": rules_of(key), "spans": p["spans"],
                   "drop_best5": p["drop_best5"], "neighbours": p["neighbours"], "placebo": p.get("placebo"), "months": p["months"],
                   "evals": ev, "costs": "$1.90 a micro round trip + 1 tick on market entries, stop and time exits",
                   "data": "TradingView CME NQ1! 5m (data/NQ_5m.csv), 1m for the 2026 trade path (data/NQ_1m.csv)",
                   "trade_format": list(COMMON), "trades": [{c: t.get(c) for c in COMMON} for t in T]}
            _dump(rec, os.path.join(OUT, f"hq_cont_{fid}.json"), separators=(",", ":"))
            s = p["spans"]
            e50 = {sp: ev.get(sp, {}).get("50k_need0.5", {}) for sp in ("H1", "H2")}
            e25 = {sp: ev.get(sp, {}).get("25k_alone", {}) for sp in ("H1", "H2")}
            index[fid] = {"key": key, "how": how, "spans": {sp: {x: s[sp].get(x) for x in ("n", "tpw", "win1", "pf", "net")} for sp in s}}
            rl.save("hq_cont_" + fid, f"HQ continuation ({how.split(' (')[0]}) #{j + 1}", "other", Q,
                    params={"key": key, "rules": rules_of(key)}, trades=run_trades(T), scored=rl.score(run_trades(T), D["sess"]),
                    status="rejected",
                    verdict=(f"LIT size, costs in. H1 {_h(s['H1'])}. H2 {_h(s['H2'])}. 2025 {_h(s['2025'])}. 2021-24 {_h(s['2021-24'])}. "
                             f"50K next to LIT (need0.5) 2-week pass/fail H1 {e50['H1'].get('p10')}/{e50['H1'].get('f10')}, "
                             f"H2 {e50['H2'].get('p10')}/{e50['H2'].get('f10')}; 25K alone H1 {e25['H1'].get('p10')}/{e25['H1'].get('f10')}, "
                             f"H2 {e25['H2'].get('p10')}/{e25['H2'].get('f10')}."),
                    notes=f"tools/hq_cont.py, variant {key}", writeup="hq-continuation", tags=["hq", "continuation", grp])
    _dump({"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "files": index}, os.path.join(OUT, "index.json"), indent=1)
    print(len(index), "picks saved", flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "grid"
    {"grid": cmd_grid, "pick": cmd_pick, "peek": cmd_peek, "evals": cmd_evals, "save": cmd_save}[cmd]()
