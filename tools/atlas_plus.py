"""ATLAS new members (2026-11-18, night-atlasplus): does a NEW rule-based member add winning DAYS to ATLAS on the owner's
FUNDED Builder 25K (payouts need many small winning days: 50% consistency) without piling losses onto the days ATLAS / LIT
lose? Research only: never touches second_model.json, data/account_b.json, live_model*.json or any engine file.
Write-up: research/writeups/atlas-members-2026-11-18.md. Numbers: research/second/atlas_plus.json.

Read first (docs/TESTED_AND_REJECTED.md): VWAP reversion on low-VIX days and gap fade + failed opening drive (E2), the
first pullback in a London / NY leg (hq-continuation) and BLITZ's opening drive, the failed auction at the prior value
edge + Dalton's 80% rule (new-strategy hunt), VWAP side / distance as a size filter (ab_edge, strategy tree), NR7 / NR4
(public strategies). Not tested before: the VWAP PULLBACK WITH the trend as an entry, an opening-drive continuation
triggered on 1m, a 15m Keltner squeeze release, and any of them as an ATLAS member on the funded account.

Hypotheses, written BEFORE the first run (every cell below is counted in the many-tests bar; nothing added after a look):
  VWP  VWAP pullback with trend. H: on a trending RTH morning the first dip to the session VWAP that closes back on the
       trend side is where late buyers / sellers re-enter. Trend = VWAP rising over the last 30 min (long) and "s1" also
       the move from the 09:30 open >= 0.5 x the 14-day noise sigma at that minute. Touch bar: low <= VWAP, close above it,
       close > open (mirror for shorts), at least 3 of the 6 bars before closed above VWAP. Stop 1 tick beyond the lowest
       low of the last 3 bars. Window 10:00-12:00 or 10:00-14:30. One a day.
  ODC  Opening-drive continuation on 1m confirmation. H: a strong 09:30 drive (>= k x the 14-day sigma by 09:45 or 10:00,
       closing in its outer 30%) that pulls back 25-62% resumes; the 1m close above the last 3 1m highs (below the 3 lows
       for shorts) is the trigger. Stop 1 tick beyond the pullback extreme. Until 11:00, one a day. 1m bars exist only for
       2026 (data/NQ_1m.csv); 2021-25 uses the same rule on 5m bars (close beyond the last 2 5m highs) - shown, labelled.
  PVA  Prior-day value-area re-entry = Dalton's 80% rule, ALREADY REJECTED (new-strategy hunt). Re-measured once, as an
       ATLAS member only (its H1 pick there, d80_c1_u12_r2), never re-searched.
  KSQ  15m Keltner squeeze. H: Bollinger(20, 2) inside Keltner(20, EMA +- 1.5 ATR) for >= N 15m RTH bars = compression;
       within 3 bars of the squeeze ending, the first 15m close beyond the squeeze box starts the expansion. Stop 1 tick
       beyond the breakout 15m bar ("bar") or the box middle ("mid"). Signals 10:00-14:30.
  POC  (own idea, declared after the first four ran, before its own run; counted) Prior-day POC first touch. H: the
       prior RTH session's point of control (the hunt's 5m-built profile) acts as support / resistance the first time RTH
       trades back to it from one side: the first 5m bar (from 09:35) whose range reaches the POC from above (below) and
       closes back on its side by >= 0.1 x its range is faded in the old direction (long from above). Stop 1 tick beyond
       the touch bar. Until 12:00 or 15:00, one a day.
  Targets (all): one target - 2R, or ATLAS's VIX band (open18 +- VIX/100/sqrt(252) x open18, at least 1.5R, at most 8R,
  = the MACD / EMA members). Stops below 8 pts widened to 8; stops above 80 pts skipped (S/R's max_stop). Flat 15:55.

Execution: tools/div_search.walk (5m RTH, entry at the next open + 1 tick, stop first in a bar touching both, a target
needs a trade-through, stop / EOD exits 1 tick worse); ODC 2026 on a 1m walk with the same rules. $1.90 a micro.

Judging (in this order, H1 = 2026 Jan-Jun picks, H2 = Jul-Oct 16 checks):
  1. alone at $250 a trade (micros = floor(250 / (stop x $2 + $1.90))): per family the H1 pick = best H1 net among cells with
     H1 n >= 12 and PF >= 1.2; no pick = family rejected.
  2. chance level: the same cells with coin-flip sides (stop / target mirrored), 10 seeds: "holds" = net > 0 and PF >= 1.1
     in H1, H2, 2025 and 2021-24.
  3. days: winning days the member adds on days ATLAS + LIT were not green, and its losing days on days ATLAS or LIT lost
     vs what independence predicts.
  4. as an ATLAS member (pick only): the live account-B rules (tools/atlas.account_units: never opposite LIT incl. its armed
     setups, HEDGE close; one position, max 2 a day), the funded 25K Monte Carlo of tools/atlas_revive (MFFU builder25k
     funded rules, 600 paths x 126 sessions) at ATLAS's funded sizing $250 / 30% of the room, plus the preset "fq" sizing
     shown. Gate = tools/atlas_revive.passes (funded $ a month up in BOTH halves, no-payout / first payout not worse,
     2021-25 not lower, combined ATLAS 2-4 trades a week with today's 4.06 as the top) + more green days a month in both
     halves + losing days shared with LIT not up by more than 0.2 a month. Two shapes: "+X" and "+X, S/R out" (keeps the
     trade count).
  5. ZEUS Lab guard: sign-flip p of the per-day $ change (combo - today, fixed $250) <= family alpha 0.2 / every cell
     counted, in both halves.
A pass goes to the Lab's 4-week forward shadow; the owner says yes later.

    python -X utf8 tools/atlas_plus.py grid      # stages 1-3 -> research/second/atlas_plus.json
    python -X utf8 tools/atlas_plus.py combo     # stages 4-5 on the picks (~1 min a shape)
    python -X utf8 tools/atlas_plus.py register  # one ZEUS Lab experiment per family (zeus_lab.register)
    python -X utf8 tools/atlas_plus.py all
"""
from __future__ import annotations

import bisect
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
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tools", "money"))
import div_search as DS  # noqa: E402

OUT = os.path.join(ROOT, "research", "second", "atlas_plus.json")
TICK, NB, PV, COMM = DS.TICK, DS.NB, DS.PV, DS.COMM
MIN_STOP, MAX_STOP, USD = 8.0, 80.0, 250.0
J4 = ("H1", "H2", "2025", "2021-24")
SPN = ("H1", "H2", "2025", "2021-24", "2021-25")
DATE = "2026-11-18"
col = DS.col_of                                 # column of the 5m bar that CLOSES at (h, m)


def c0(h, m):
    return (h * 60 + m - 570) // 5


# ================================================================================================ facts known before a trade
_F = {}


def facts():
    """open18 (18:00 ET open of the trading day) and the prior VIX close per RTH day of div_search.D()."""
    if "f" in _F:
        return _F["f"]
    B = DS.D()
    d = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"), usecols=["time", "open"])
    et = pd.to_datetime(d.time, unit="s", utc=True).dt.tz_convert("America/New_York")
    m = ((et.dt.hour == 18) & (et.dt.minute == 0)).to_numpy()
    o18 = {}
    for t, o in zip(et[m], d.open.to_numpy(float)[m]):
        x = t.date() + dt.timedelta(days=1)
        o18[x.isoformat()] = float(o)
    v = pd.read_csv(os.path.join(ROOT, "data", "VIX_1d.csv"))
    vd, vc = [str(x)[:10] for x in v["date"]], v["close"].astype(float).tolist()
    O18 = np.array([o18.get(x, np.nan) for x in B.days])
    VIX = np.array([vc[bisect.bisect_left(vd, x) - 1] if bisect.bisect_left(vd, x) > 0 else np.nan for x in B.days])
    VM = VIX / 100.0 / math.sqrt(252.0) * O18
    _F["f"] = (O18, VIX, VM)
    return _F["f"]


# ================================================================================================ 1m days (2026)
class Days1:
    """2026 RTH sessions on 1m bars (390 a day), only days with every minute."""

    def __init__(self):
        d = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv"))
        et = pd.to_datetime(d.time, unit="s", utc=True).dt.tz_convert("America/New_York")
        hm = (et.dt.hour * 60 + et.dt.minute).to_numpy()
        date = et.dt.date.astype(str).to_numpy()
        rth = (hm >= 570) & (hm < 960)
        d, hm, date = d[rth].reset_index(drop=True), hm[rth], date[rth]
        self.pos = {}
        rows = []
        for day, idx in pd.Series(np.arange(len(d))).groupby(date).groups.items():
            ix = np.array(sorted(idx))
            if len(ix) == 390 and hm[ix[0]] == 570:
                self.pos[day] = len(rows)
                rows.append(ix)
        ix = np.array(rows)
        self.t = d.time.to_numpy(np.int64)[ix]
        self.O, self.H, self.L, self.C = (d[k].to_numpy(float)[ix] for k in ("open", "high", "low", "close"))


_D1 = {}


def D1():
    if "d" not in _D1:
        _D1["d"] = Days1()
    return _D1["d"]


def walk_arr(t, O, H, L, C, e0, d, stop, tgt, last):
    """div_search.walk on any bar arrays of one day: enter at the open of bar e0 (+1 tick), exits stop / target / the open of
    bar `last` (15:55). Returns the fill, exit and path (bar indices) or None."""
    if e0 >= last:
        return None
    entry = O[e0] + d * TICK
    s = float(stop)
    if (entry - s) * d <= 0:
        return None
    risk = (entry - s) * d
    mae = 0.0
    ex_px = ex_kind = ex_j = None
    for jj in range(e0, last):
        if d == 1 and L[jj] <= s:
            ex_px, ex_kind, ex_j = min(O[jj], s) - TICK, "STOP", jj
            mae = min(mae, L[jj] - entry)
            break
        if d == -1 and H[jj] >= s:
            ex_px, ex_kind, ex_j = max(O[jj], s) + TICK, "STOP", jj
            mae = min(mae, entry - H[jj])
            break
        mae = min(mae, (L[jj] - entry) if d == 1 else (entry - H[jj]))
        if tgt is not None and ((d == 1 and H[jj] > tgt) or (d == -1 and L[jj] < tgt)):
            ex_px, ex_kind, ex_j = tgt, "TARGET", jj
            break
    if ex_px is None:
        ex_j, ex_px, ex_kind = last, O[last] - d * TICK, "EOD"
    return {"entry": entry, "risk": risk, "exit_px": ex_px, "exit": ex_kind, "e0": e0, "ex_j": ex_j, "pts": (ex_px - entry) * d,
            "mae": mae}


# ================================================================================================ signals -> units
def unit_of(day, d, w, t, O, H, L, tgt, src, secs):
    """A walk -> an account-B unit (second_mix.second_units / atlas_v2._sh_units fields, path on the walked bars)."""
    k0, kx = w["e0"], w["ex_j"]
    e, risk, pts = w["entry"], w["risk"], w["pts"]
    lo = L if d == 1 else -H
    op = O[k0:kx + 1] * d - e * d
    lw = np.minimum.accumulate(np.r_[0.0, lo[k0:kx] - e * d])
    w1 = max(-(risk + 0.25), min(0.0, w["mae"], pts))
    return {"day": day, "entry_t": int(t[k0]), "exit_t": int(t[kx]) + (secs if w["exit"] != "EOD" else 0), "dir": int(d),
            "exit": w["exit"], "risk": round(float(risk), 4), "tgt": round(float(abs(tgt - e)), 4) if tgt is not None else None,
            "pts": round(float(pts), 4), "w1": round(float(w1), 4), "src": src, "pt": t[k0:kx + 1].astype(np.int64),
            "po": np.round(op, 2), "pw": np.maximum(np.round(lw, 2), -(risk + 0.25))}


def target(k, d, entry, risk, kind):
    """2R or ATLAS's VIX band (>= 1.5R else no trade, <= 8R)."""
    if kind == "vix":
        O18, _, VM = facts()
        if not (np.isfinite(O18[k]) and np.isfinite(VM[k])):
            return None, False
        dist = (O18[k] + d * VM[k] - entry) * d
        if dist < 1.5 * risk:
            return None, False
        return entry + d * min(dist, 8.0 * risk), True
    return entry + d * float(kind) * risk, True


def mirror(d, ref, stop, flip):
    if flip is not None and flip.random() < 0.5:
        dist = (ref - stop) * d
        d = -d
        stop = ref - d * dist
    return d, stop


def execute(sigs, src, tgt_kind, flip=None, max_stop=MAX_STOP):
    """sigs: (k, j, d, stop) on the 5m RTH matrix (entry at the open of column j+1) or (k, j, d, stop, "1m") with j a 1m index.
    flip: coin-flip control (side reversed with p 0.5, stop mirrored at the same distance)."""
    B = DS.D()
    U = []
    for s in sigs:
        k, j, d, stop = s[:4]
        one = len(s) > 4 and s[4] == "1m"
        if one:
            X = D1()
            i = X.pos[B.days[k]]
            t, O, H, L, C, last, secs = X.t[i], X.O[i], X.H[i], X.L[i], X.C[i], 385, 60
        else:
            t, O, H, L, C, last, secs = B.t[k], B.O[k], B.H[k], B.L[k], B.C[k], NB - 1, 300
        if j + 1 >= last:
            continue
        ref = O[j + 1]
        d, stop = mirror(d, ref, stop, flip)
        entry = ref + d * TICK
        if (entry - stop) * d < MIN_STOP:
            stop = entry - d * MIN_STOP
        risk = (entry - stop) * d
        if max_stop and risk > max_stop:
            continue
        tg, ok = target(k, d, entry, risk, tgt_kind)
        if not ok:
            continue
        w = walk_arr(t, O, H, L, C, j + 1, d, stop, tg, last)
        if w is None:
            continue
        U.append(unit_of(B.days[k], d, w, t, O, H, L, tg, src, secs))
    return U


# ================================================================================================ the families
def vwp(cfg):
    B = DS.D()
    a, z = c0(10, 0), col(cfg["until"])
    out = []
    for k in range(len(B.days)):
        VW, O, H, L, C = B.VW[k], B.O[k], B.H[k], B.L[k], B.C[k]
        sg = B.sig[14][k]
        for j in range(max(a, 6), z + 1):
            sl = VW[j] - VW[j - 6]
            d = 1 if sl > 0 else -1 if sl < 0 else 0
            if not d:
                continue
            if cfg["trend"] == "s1" and not (np.isfinite(sg[j]) and (C[j] - O[0]) * d >= 0.5 * sg[j]):
                continue
            side = (C[j - 6:j] - VW[j - 6:j]) * d > 0
            if side.sum() < 3:
                continue
            touch = (L[j] <= VW[j] and C[j] > VW[j] and C[j] > O[j]) if d == 1 else (H[j] >= VW[j] and C[j] < VW[j] and C[j] < O[j])
            if not touch:
                continue
            ext = L[j - 2:j + 1].min() if d == 1 else H[j - 2:j + 1].max()
            out.append((k, j, d, ext - d * TICK))
            break
    return out


def _odc_day(O, H, L, C, de, last, dr, look):
    """One opening drive on one day's bars (bar 0 = 09:30): drive to bar de (inclusive) in direction dr; pullback 25-62% of
    the drive range, then a close beyond the last `look` bars' extreme. Returns (j, stop) or None."""
    hi, lo = H[:de + 1].max(), L[:de + 1].min()
    rng = hi - lo
    if rng <= 0:
        return None
    ext = hi if dr == 1 else lo
    pb = None                                         # pullback extreme so far (low for longs)
    for j in range(de + 1, last + 1):
        if dr == 1:
            if H[j] > ext and pb is None:
                ext = H[j]
                rng = ext - lo
                continue
            pb = L[j] if pb is None else min(pb, L[j])
            r = (ext - pb) / rng
        else:
            if L[j] < ext and pb is None:
                ext = L[j]
                rng = hi - ext
                continue
            pb = H[j] if pb is None else max(pb, H[j])
            r = (pb - ext) / rng
        if r > 0.618:
            return None
        if r < 0.25 or j - look < de + 1:
            continue
        prev = H[j - look:j].max() if dr == 1 else L[j - look:j].min()
        if (C[j] - prev) * dr > 0 and (L[j] > pb if dr == 1 else H[j] < pb):
            return j, pb - dr * TICK
    return None


def odc(cfg):
    B = DS.D()
    out = []
    de5 = col(cfg["drive"])                           # 5m column of the drive's last bar
    last5 = col((11, 0))
    for k in range(len(B.days)):
        sg = B.sig[14][k, de5]
        mv = B.C[k, de5] - B.O[k, 0]
        if not np.isfinite(sg) or abs(mv) < cfg["k"] * sg:
            continue
        dr = 1 if mv > 0 else -1
        hi, lo = B.H[k, :de5 + 1].max(), B.L[k, :de5 + 1].min()
        if (B.C[k, de5] - lo) / max(hi - lo, 1e-9) < 0.7 if dr == 1 else (hi - B.C[k, de5]) / max(hi - lo, 1e-9) < 0.7:
            continue
        day = B.days[k]
        if day >= "2026-01-01" and day in D1().pos:
            X = D1()
            i = X.pos[day]
            m = (cfg["drive"][0] * 60 + cfg["drive"][1] - 570) - 1      # 1m index of the drive's last bar
            r = _odc_day(X.O[i], X.H[i], X.L[i], X.C[i], m, 89, dr, 3)  # 1m bar 89 = 10:59
            if r:
                out.append((k, r[0], dr, r[1], "1m"))
        else:
            r = _odc_day(B.O[k], B.H[k], B.L[k], B.C[k], de5, last5, dr, 2)
            if r:
                out.append((k, r[0], dr, r[1]))
    return out


def pva(cfg):
    """Dalton 80% rule, the new-strategy hunt's own signal code (tools/new_hunt.d80), re-measured as a member."""
    import new_hunt as NH
    return [(k, j, s, stop) for k, j, s, stop, *_ in NH.d80(cfg)]


def poc(cfg):
    import new_hunt as NH
    B, E = DS.D(), NH.XX()
    z = col(cfg["until"])
    out = []
    for k in range(len(B.days)):
        p = E.POC[k]
        if not np.isfinite(p):
            continue
        O, H, L, C = B.O[k], B.H[k], B.L[k], B.C[k]
        side = 1 if O[0] > p else -1 if O[0] < p else 0
        if not side:
            continue
        for j in range(1, z + 1):
            if L[j - 1] <= p <= H[j - 1] and j > 1:
                break                                 # touched earlier without a signal: no longer the first test
            if not (L[j] <= p <= H[j]):
                continue
            rg = H[j] - L[j]
            if rg > 0 and (C[j] - p) * side >= 0.1 * rg:
                out.append((k, j, side, (L[j] if side == 1 else H[j]) - side * TICK))
            break
    return out


_K = {}


def k15():
    """15m RTH bars (3 x 5m) across days + Bollinger(20, 2) / Keltner(20, 1.5 ATR) squeeze flags."""
    if "k" in _K:
        return _K["k"]
    B = DS.D()
    n = len(B.days)
    o = B.O[:, 0::3].reshape(-1)
    h = np.maximum.reduceat(B.H, np.arange(0, NB, 3), axis=1).reshape(-1)
    l = np.minimum.reduceat(B.L, np.arange(0, NB, 3), axis=1).reshape(-1)
    c = B.C[:, 2::3].reshape(-1)
    s = pd.Series(c)
    ema = s.ewm(span=20, adjust=False).mean().to_numpy()
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
    atr = pd.Series(tr).rolling(20).mean().to_numpy()
    sma, sd = s.rolling(20).mean().to_numpy(), s.rolling(20).std(ddof=0).to_numpy()
    on = (sma + 2 * sd < ema + 1.5 * atr) & (sma - 2 * sd > ema - 1.5 * atr)
    _K["k"] = (n, o, h, l, c, on)
    return _K["k"]


def ksq(cfg):
    n, o, h, l, c, on = k15()
    per = 26
    out = []
    N = cfg["n"]
    for k in range(n):
        for q in range(1, 20):                        # 15m bar q closes at 09:45 + 15q (q 1 = 10:00 ... q 19 = 14:30)
            i = k * per + q
            if i < N + 4:
                continue
            # squeeze ended within the last 3 bars (incl. this one) after >= N bars on
            end = None
            for b in range(i, i - 3, -1):
                if not on[b] and on[b - N:b].all():
                    end = b
                    break
            if end is None:
                continue
            box_h, box_l = h[end - N:end].max(), l[end - N:end].min()
            d = 1 if c[i] > box_h else -1 if c[i] < box_l else 0
            if not d or (c[i - 1] - (box_h if d == 1 else box_l)) * d > 0:
                continue                              # not the first close beyond the box
            stop = (l[i] if d == 1 else h[i]) - d * TICK if cfg["stop"] == "bar" else (box_h + box_l) / 2.0
            out.append((k, 3 * q + 2, d, stop))
            break
    return out


MS = {"pva": None}             # the re-measure keeps the hunt's own rules (no stop cap)
FAM = {"vwp": vwp, "odc": odc, "pva": pva, "ksq": ksq, "poc": poc}
NAMES = {"vwp": "VWAP pullback with trend", "odc": "Opening-drive continuation (1m trigger)",
         "pva": "Prior-day value-area re-entry (80% rule, re-measure)", "ksq": "15m Keltner squeeze release",
         "poc": "Prior-day POC first touch (own idea)"}


def grid():
    G = []
    for until, trend, tg in itertools.product([(12, 0), (14, 30)], ["slope", "s1"], ["2", "vix"]):
        G.append((f"vwp_u{until[0]}_{trend}_t{tg}", "vwp", {"until": until, "trend": trend}, tg))
    for kk, drive, tg in itertools.product([0.75, 1.25], [(9, 45), (10, 0)], ["2", "vix"]):
        G.append((f"odc_k{int(kk * 100)}_d{drive[0]}{drive[1]:02d}_t{tg}", "odc", {"k": kk, "drive": drive}, tg))
    G.append(("pva_d80_c1_u12_t2", "pva", {"closes": 1, "until": (12, 0), "tgt": "r2"}, "2"))
    for nn, stop, tg in itertools.product([4, 6], ["bar", "mid"], ["2", "vix"]):
        G.append((f"ksq_n{nn}_{stop}_t{tg}", "ksq", {"n": nn, "stop": stop}, tg))
    for until, tg in itertools.product([(12, 0), (15, 0)], ["2", "vix"]):
        G.append((f"poc_u{until[0]}_t{tg}", "poc", {"until": until}, tg))
    return G


# ================================================================================================ scoring alone ($250)
def book(U, usd=USD):
    T = []
    for u in U:
        q = min(40, int(usd // (u["risk"] * PV + COMM)))
        if q < 1:
            continue
        T.append({"day": u["day"], "pnl": round(q * (u["pts"] * PV - COMM), 2), "r": (u["pts"] * PV - COMM) / (u["risk"] * PV),
                  "risk_pts": u["risk"]})
    return T


def span_days(span):
    a, z = DS.SPANS[span]
    if span == "H2":
        z = "2026-10-16"
    return [x for x in DS.D().days if a <= x <= z]


def stats(T, span):
    days = span_days(span)
    ds = set(days)
    X = [t for t in T if t["day"] in ds]
    if not X:
        return {"n": 0, "net": 0, "pf": None, "tpw": 0.0}
    p = np.array([t["pnl"] for t in X])
    gl = -p[p < 0].sum()
    eq = np.cumsum(p)
    return {"n": len(X), "tpw": round(len(X) / (len(days) / 5.0), 2), "win": round(100.0 * float((p > 0).mean()), 1),
            "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None, "net": round(float(p.sum())),
            "per_month": round(float(p.sum()) / (len(days) / 21.0)), "dd": round(float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min())),
            "stop": round(float(np.median([t["risk_pts"] for t in X])), 1)}


def holds(S):
    return all(S[s]["n"] >= 5 and S[s]["net"] > 0 and (S[s]["pf"] or 0) >= 1.1 for s in J4)


_B = {}


def base_days():
    """day -> ATLAS today (live units, one position, max 2 a day) at $250 a trade, and LIT's live-run day $."""
    if "b" not in _B:
        from tools import atlas as A
        from tools import atlas_revive as R
        T = book(R.one_pos(A.account_units(A.BASE)))
        at = collections.defaultdict(float)
        for t in T:
            at[t["day"]] += t["pnl"]
        _B["b"] = (dict(at), DS.lit_daily(), T)
    return _B["b"]


def days_view(T, span):
    """The member's days next to ATLAS + LIT: green days it adds where ATLAS + LIT were not green, and its losing days on
    days ATLAS or LIT lost (vs independence)."""
    at, lit, _ = base_days()
    days = span_days(span)
    by = collections.defaultdict(float)
    for t in T:
        by[t["day"]] += t["pnl"]
    mo = len(days) / 21.0
    win = [d for d in days if by.get(d, 0) > 0]
    loss = [d for d in days if by.get(d, 0) < 0]
    bad = {d for d in days if at.get(d, 0) < 0 or lit.get(d, 0) < 0}
    new_green = sum(1 for d in win if at.get(d, 0) + lit.get(d, 0) <= 0)
    pile = sum(1 for d in loss if d in bad)
    x = np.array([at.get(d, 0) + lit.get(d, 0) for d in days])
    y = np.array([by.get(d, 0) for d in days])
    c = float(np.corrcoef(x, y)[0, 1]) if x.std() > 0 and y.std() > 0 else None
    return {"win_days_mo": round(len(win) / mo, 2), "loss_days_mo": round(len(loss) / mo, 2),
            "new_green_mo": round(new_green / mo, 2), "loss_on_bad_mo": round(pile / mo, 2),
            "loss_on_bad_expected_mo": round(len(loss) * len(bad) / max(1, len(days)) / mo, 2),
            "corr_atlas_lit": round(c, 3) if c is not None else None}


def cmd_grid(log=print):
    t0 = time.time()
    G = grid()
    res, units = {}, {}
    for cid, fam, cfg, tg in G:
        sigs = FAM[fam](cfg)
        U = execute(sigs, cid, tg, max_stop=MS.get(fam, MAX_STOP))
        T = book(U)
        S = {s: stats(T, s) for s in SPN}
        res[cid] = {"fam": fam, "cfg": cfg, "tgt": tg, "S": S, "holds": holds(S), "days": {s: days_view(T, s) for s in ("H1", "H2", "2021-25")}}
        units[cid] = (sigs, tg)
        log(f"{cid:24s} " + " | ".join(f"{s} n{S[s]['n']} {S[s]['tpw']}/wk PF {S[s]['pf']} ${S[s]['net']}" for s in J4))
    chance = collections.defaultdict(list)
    for seed in range(10):
        rng = np.random.default_rng(300 + seed)
        cnt = collections.Counter()
        for cid, (sigs, tg) in units.items():
            T = book(execute(sigs, cid, tg, flip=rng, max_stop=MS.get(res[cid]["fam"], MAX_STOP)))
            cnt[res[cid]["fam"]] += int(holds({s: stats(T, s) for s in J4}))
        for f in FAM:
            chance[f].append(cnt[f])
    fams = {}
    for f in FAM:
        ids = [c for c in res if res[c]["fam"] == f]
        ok = [c for c in ids if res[c]["S"]["H1"]["n"] >= 12 and (res[c]["S"]["H1"]["pf"] or 0) >= 1.2 and res[c]["S"]["H1"]["net"] > 0]
        pick = max(ok, key=lambda c: res[c]["S"]["H1"]["net"]) if ok else None
        fams[f] = {"name": NAMES[f], "cells": len(ids), "hold_all4": sum(res[c]["holds"] for c in ids),
                   "chance_mean": round(float(np.mean(chance[f])), 2), "chance_max": int(max(chance[f])),
                   "h1_and_h2_positive": sum(1 for c in ids if res[c]["S"]["H1"]["net"] > 0 and res[c]["S"]["H2"]["net"] > 0),
                   "h1_pick": pick}
        log(f"{f}: {fams[f]}")
    out = {"date": DATE, "built_s": round(time.time() - t0), "families": fams, "cells": res, "n_cells": len(G)}
    old = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    if old.get("combo"):
        out["combo"] = old["combo"]
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1, default=str)
    log(f"wrote {os.path.relpath(OUT, ROOT)} ({time.time() - t0:.0f}s)")
    return out


# ================================================================================================ as an ATLAS member (funded 25K)
def install(cids):
    """Put the candidates' units into second_mix's unit cache (tools/atlas.member_units reads them like any member)."""
    from tools import second_mix as M
    U = M.units()
    G = {cid: (fam, cfg, tg) for cid, fam, cfg, tg in grid()}
    for cid in cids:
        if cid not in U:
            fam, cfg, tg = G[cid]
            U[cid] = execute(FAM[fam](cfg), cid, tg, max_stop=MS.get(fam, MAX_STOP))
    return U


def combo_days(T, S, span):
    """Fixed $250: ATLAS (with the member) day $ -> green days / losing days shared with LIT, per month."""
    lit = DS.lit_daily()
    days = span_days(span) if span != "REF" else [d for d in DS.D().days if "2021-11-01" <= d <= "2025-12-31"]
    ds = set(days)
    by = collections.defaultdict(float)
    for t in T:
        if t["day"] in ds:
            q = int(USD * t.get("w", 1.0) // ((t["risk"] + 0.25) * PV + COMM))
            by[t["day"]] += q * (t["pts"] * PV - COMM)
    mo = len(days) / 21.0
    return {"green_mo": round(sum(1 for d in days if by.get(d, 0) > 0) / mo, 2),
            "red_mo": round(sum(1 for d in days if by.get(d, 0) < 0) / mo, 2),
            "red_with_lit_mo": round(sum(1 for d in days if by.get(d, 0) < 0 and lit.get(d, 0) < 0) / mo, 2),
            "by": dict(by)}


def cmd_combo(n=600, log=print):
    import logging
    logging.getLogger("engine.sizing").setLevel(logging.ERROR)
    import builder_levers as BL
    import stack_one_account as SA
    from tools import atlas as A
    from tools import atlas_revive as R
    from tools import uprisk as U
    from tools import zeus_lab as Z
    o = json.load(open(OUT, encoding="utf-8"))
    picks = [v["h1_pick"] for v in o["families"].values() if v.get("h1_pick")]
    install(picks)
    WGF = R._wgf()
    S = SA.data()["S"]
    PF = {sp: U.mc_paths(S, sp, n, length=BL.LEN, seed=BL.A4.SEED_LIFE) for sp in BL.SPANS}
    SIZING = {"stack250": {"ATLAS": ("stack", 250.0, 0.3)}, "fq": {"ATLAS": ("fq", None)}}
    shapes = {"ATLAS today": {}}
    for c in picks:
        shapes[f"+ {c}"] = {"members": ["EMA", "MD", "SR", c]}
        shapes[f"+ {c}, S/R out"] = {"members": ["EMA", "MD", c]}
    exps, _, _, _ = Z.load_registry()
    lab_cells = Z.cells([e for e in exps if e.get("kind") != "atlas_member"]) + o["n_cells"]
    thr = Z.p_needed(max(lab_cells, o["n_cells"]), 0.2)
    rows = {}
    for nm, I in shapes.items():
        T = R.variant_units(I)
        BY = R.by_session(T, S)
        row = {"idea": I}
        for zk, z in SIZING.items():
            row[zk] = {sp: {"funded": BL.funded_run(BY, PF[sp], lambda z=z: WGF("builder25k", U.UP25, z)), "fixed": R.fixed_stats(T, S, sp)}
                       for sp in BL.SPANS}
        row["days"] = {sp: combo_days(T, S, sp) for sp in ("H1", "H2", "REF")}
        rows[nm] = row
        f = row["stack250"]
        log(f"{nm:34s} " + " | ".join(f"{sp} ${f[sp]['funded']['per_month']}/mo 1st {f[sp]['funded']['first_med']} nopay "
                                      f"{f[sp]['funded']['no_pay_6m']}% {f[sp]['fixed']['tpw']}/wk PF {f[sp]['fixed']['pf']} "
                                      f"green {row['days'][sp]['green_mo']} redLIT {row['days'][sp]['red_with_lit_mo']}"
                                      for sp in BL.SPANS))
    base = rows["ATLAS today"]
    for nm, row in rows.items():
        if nm == "ATLAS today":
            continue
        g_money = R.passes(row["stack250"], base["stack250"])
        g_fq = R.passes(row["fq"], base["fq"])
        g_days = all(row["days"][sp]["green_mo"] > base["days"][sp]["green_mo"] and
                     row["days"][sp]["red_with_lit_mo"] <= base["days"][sp]["red_with_lit_mo"] + 0.2 for sp in ("H1", "H2"))
        b0, b1 = base["days"], row["days"]
        flip = {}
        D = []
        for sp in ("H1", "H2"):
            dd = [b1[sp]["by"].get(d, 0.0) - b0[sp]["by"].get(d, 0.0) for d in set(b0[sp]["by"]) | set(b1[sp]["by"])]
            dd = [x for x in dd if abs(x) > 1e-9]
            flip[sp] = Z.signflip_p(dd, 4000)
        for sp in ("H1", "H2", "REF"):
            for d in sorted(set(b0[sp]["by"]) | set(b1[sp]["by"])):
                x = b1[sp]["by"].get(d, 0.0) - b0[sp]["by"].get(d, 0.0)
                if abs(x) > 1e-9:
                    D.append({"day": d, "t": f"{nm}:{d}", "usd": round(x, 2)})
        g_luck = all(flip[sp] <= thr for sp in ("H1", "H2"))
        why = []
        f, fb = row["stack250"], base["stack250"]
        for sp, w in (("H1", "Jan-Jun"), ("H2", "Jul-Oct")):
            dm = f[sp]["funded"]["per_month"] - fb[sp]["funded"]["per_month"]
            if dm <= 0:
                why.append(f"{w} funded {Z.money(dm)} a month")
            if f[sp]["fixed"]["tpw"] > max(4.0, fb[sp]["fixed"]["tpw"] + 0.1):
                why.append(f"{w} {f[sp]['fixed']['tpw']} trades a week (rule 2-4)")
        if f["REF"]["funded"]["per_month"] < fb["REF"]["funded"]["per_month"]:
            why.append(f"2021-25 {Z.money(f['REF']['funded']['per_month'] - fb['REF']['funded']['per_month'])} a month")
        if not g_days:
            why.append("green days not up in both halves (or more red days with LIT)")
        if not g_luck:
            why.append(f"could be luck: p {flip['H1']} / {flip['H2']} (needs <= {thr})")
        if not why and not g_money:
            why.append("no-payout or first payout worse")
        row.update(gate_money=g_money, gate_money_fq=g_fq, gate_days=g_days, flip=flip, thr=thr, deltas=D,
                   passes=bool(g_money and g_days and g_luck), why="; ".join(why) or "passes: better in Jan-Jun and Jul-Oct, costs in, beats random, survives the many-tests guard")
        log(f"  {nm}: {'PASS' if row['passes'] else 'no'} - {row['why']}")
    for row in rows.values():
        for sp in row["days"]:
            row["days"][sp].pop("by", None)
    o["combo"] = {"n_paths": n, "thr": thr, "sizing": {k: str(v) for k, v in SIZING.items()}, "rows": rows}
    json.dump(o, open(OUT, "w", encoding="utf-8"), indent=1, default=str)
    log(f"wrote {os.path.relpath(OUT, ROOT)}")
    return o


# ================================================================================================ ZEUS Lab runner (kind atlas_member)
def _head(row, cell=None):
    """Lab page format: H1 / H2 funded $ a month (ATLAS $250 / 30% room) + fixed-$250 detail; 2025 / 2021-24 carry REF."""
    f = row["stack250"]
    h = {}
    for sp in ("H1", "H2"):
        x = f[sp]["fixed"]
        h[sp] = {"per_month": f[sp]["funded"]["per_month"], "n": x["n"], "tpw": x["tpw"], "pf": x["pf"], "net": x["net"], "dd": x["max_dd"],
                 "first_med": f[sp]["funded"]["first_med"], "no_pay_6m": f[sp]["funded"]["no_pay_6m"]}
    for sp in ("2025", "2021-24"):
        h[sp] = {"per_month": f["REF"]["funded"]["per_month"], "n": f["REF"]["fixed"]["n"], "tpw": f["REF"]["fixed"]["tpw"],
                 "pf": f["REF"]["fixed"]["pf"], "net": f["REF"]["fixed"]["net"], "dd": f["REF"]["fixed"]["max_dd"]}
    return h


def lab_result(e: dict, path: str = OUT) -> dict:
    """ZEUS Lab runner for kind atlas_member: the stored verdict of this tool (research/second/atlas_plus.json; rerun the tool
    for new bars). A family with no H1 pick is rejected at stage 1; a pick is judged by its combo row (e['shape'])."""
    o = json.load(open(path, encoding="utf-8"))
    fam = o["families"].get(e.get("family")) or {}
    rows = (o.get("combo") or {}).get("rows") or {}
    base = rows.get("ATLAS today")
    head = _head(base) if base else {}
    pick = fam.get("h1_pick")
    if not pick:
        why = (f"no Jan-Jun pick: none of its {fam.get('cells')} versions made money with PF >= 1.2 on 12+ trades in Jan-Jun"
               f" (alone, $250 a trade); {fam.get('hold_all4')} hold all 4 spans vs {fam.get('chance_mean')} with coin-flip sides")
        return {"proof_ok": False, "why": why, "flip": {"H1": 1.0, "H2": 1.0}, "head": head, "base": head, "deltas": [],
                "usd_month_by": None}
    nm = e.get("shape") or f"+ {pick}"
    r = rows.get(nm)
    if r is None:
        return {"proof_ok": False, "why": f"combo {nm!r} not scored yet: python -X utf8 tools/atlas_plus.py combo", "flip": {},
                "head": head, "base": head, "deltas": [], "usd_month_by": None}
    h = _head(r)
    by = {sp: round(h[sp]["per_month"] - head[sp]["per_month"]) for sp in ("H1", "H2")}
    return {"proof_ok": bool(r["gate_money"] and r["gate_days"]), "why": r["why"], "flip": r["flip"], "head": h, "base": head,
            "deltas": r["deltas"], "usd_month_by": by}


HYP = {
    "vwp": "On a trending RTH morning the first dip to the session VWAP that closes back on the trend side is where late "
           "traders re-enter (VWAP rising over 30 min; s1 also needs the move from the open >= 0.5 x the 14-day sigma).",
    "odc": "A strong 09:30 drive that pulls back 25-62% resumes; a 1m close beyond the last 3 1m extremes is the trigger "
           "(2026 on 1m; 2021-25 the same rule on 5m bars).",
    "pva": "Dalton's 80% rule (already rejected alone in the new-strategy hunt) re-measured once as an ATLAS member.",
    "ksq": "Bollinger(20, 2) inside Keltner(20, 1.5 ATR) for >= N 15m bars = compression; the first 15m close beyond the "
           "squeeze box within 3 bars of the release starts the move.",
    "poc": "The prior RTH session's point of control holds the first time price trades back to it (own idea).",
}
WHAT = {
    "vwp": "ATLAS gets a 4th member: buy the first dip to VWAP in an up-trend (sell the first rally in a down-trend), "
           "10:00-14:30, stop 1 tick beyond the last 3 bars, one target.",
    "odc": "ATLAS gets a 4th member: after a strong opening drive, enter the pullback's 1m turn in the drive's direction, "
           "until 11:00, stop 1 tick beyond the pullback, one target.",
    "pva": "ATLAS gets a 4th member: Dalton's 80% rule (open outside yesterday's value area, back inside -> trade to the far edge).",
    "ksq": "ATLAS gets a 4th member: trade the first 15m close out of a Keltner squeeze box, stop beyond the breakout bar or "
           "box middle, one target.",
    "poc": "ATLAS gets a 4th member: fade the first touch of yesterday's point of control, stop 1 tick beyond the touch bar.",
}


def cmd_register(log=print):
    """One ZEUS Lab experiment per family (kind atlas_member, cells = versions searched) through tools/zeus_lab.register."""
    from tools import zeus_lab as Z
    o = json.load(open(OUT, encoding="utf-8"))
    for f, v in o["families"].items():
        e = {"id": f"atlas_member_{f}", "bot": "atlas", "kind": "atlas_member", "family": f, "cells": v["cells"],
             "registered": DATE, "origin": "claude", "source": "research/writeups/atlas-members-2026-11-18.md (tools/atlas_plus.py)",
             "title": f"ATLAS: new member - {v['name']}", "what_changes": WHAT[f], "hypothesis": HYP[f],
             "judged_by": "atlas_member", "pick": v.get("h1_pick")}
        if v.get("h1_pick"):
            e["shape"] = f"+ {v['h1_pick']}"
        err = Z.register(e)
        log(f"{e['id']}: {'saved' if not err else err}")
    return 0


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("grid", "combo", "register", "all"))
    ap.add_argument("--n", type=int, default=600)
    a = ap.parse_args(argv)
    if a.cmd in ("grid", "all"):
        cmd_grid()
    if a.cmd in ("combo", "all"):
        cmd_combo(a.n)
    if a.cmd in ("register", "all"):
        cmd_register()
    return 0


if __name__ == "__main__":
    sys.exit(main())
