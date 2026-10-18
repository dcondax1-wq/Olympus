"""LIT on the 1-minute chart: entry intelligence and human-style trade management (owner, 2026-10-18: "trading off the
1-minute timeframe for entry, smart loss management, think like a person, not how a bot would trade").

Wraps engine/lit.py (not edited) on the live LIT settings (live_model.json "lit" = lit_final + loss pack). Same LIT signals:
the same 5m setups, the same limit at the 5m CISD level (30 min), the same 1m CISD confirmation within 20 bars and the same
stop 1 tick beyond the 5m sweep extreme. With every option off the executor is lit.simulate_x (checked: `check`).

Everything below is decided on CLOSED 1m bars only (no look-ahead) and acts at the next 1m open (+/- 1 tick of slippage),
except the "touch" exits, which are resting stop orders (filled at the level or the bar's open if it gaps through, - 1 tick).
The options apply only on days with full true 1m bars (2026); 5m fall-back days trade as live. 2021-25 has no 1m bars, so
these rules cannot be tested there.

  ENTRY (after the 5m limit is tapped)
    idm1     inner LIT: the 1m low that makes the 1m CISD must take out a 1m swing low (fractal k=2) first; pre = how many 1m
             bars before the tap a swing may come from (0 = formed after the tap). mode req (skip without) | half
    disp1    1m displacement at the CISD candle: body >= body x ATR(14, 1m), close in the top `cloc` of its range, volume >=
             vol x the mean of the 20 1m bars before it. mode req | half
    absorb   absorption on the tap bar ("tap") or the 1m low bar ("low"): volume >= vol x mean(20) and lower wick >= wick of
             the range. mode req | half
    patience skip when, at the CISD close, price has already run more than frac of the way from the 1m low to the target
             (or more than r R above the limit price)
    pull     after the 1m CISD, a limit at the CISD candle's 50% (body or range) for `wait` 1m bars instead of the next open;
             no fill = no trade (cancelled if the target trades or the sweep extreme breaks first)
  LOSS MANAGEMENT ("the trade is wrong", each only while the trade has not yet worked: best point so far < mfe R)
    x_cisd   a 1m CISD against the trade (close beyond the open of the last run of with-trade candles into the high since
             the fill); win = only in the first N minutes
    x_newlow a new 1m low beyond the entry candle's low (ref fill | conf = the CISD candle) within the first N minutes;
             how close (1m close beyond) | touch (stop order 1 tick beyond)
    x_accept k consecutive 1m closes back beyond the swept 5m level (the sweep is failing: price accepted below the old low)
    x_opp    the 1m higher low after the fill (latest confirmed 1m swing low after the fill) is taken: how touch | close
    x_es     ES does not confirm: ES (5m, closed bars) trades beyond its own extreme of the sweep (from 30 min before the
             NQ extreme to the fill) in the other direction; how low | close
    x_vol    a 1m candle against the trade with volume >= vol x mean(20) and body >= body x ATR(1m)
  PROFIT MANAGEMENT
    p_bos    after a 1m break of structure in favour (close above the last 1m swing high since the 1m low) made by a
             displacement candle (body >= body x ATR 1m), move the stop to 1 tick beyond the 1m higher low (lowest low
             between that swing high and the break); be False = no breakeven at 1R (the structure stop replaces it)
    p_lvl    take the profit at a key level when price stalls there: the 18:00 open, the midnight open, the swept session
             box's other side; once price has traded to it (in profit >= min_r R, below the target) a 1m CISD against
             closes the trade at the next open
    p_be     adaptive breakeven: a move to 1R within `fast` minutes is strong -> no breakeven at 1R (alt = breakeven at alt R
             instead, None = never); a slower move -> breakeven at 1R as live
  cut_counts (default True): a losing early exit counts as a stop-out for the weekly stop (2 in a week -> half size)

Scoring: the MFFU eval sizing (live_model.json lit_sizing mode "eval": $800 up to a 25-pt stop, then 800 x 25 / stop,
times the weekly stop, then never more than 60% of the room to the trailing max-loss floor; engine/sizing.py lit_qty), MFFU
50K evals started on every session (tools/lit_tightstop.py scoring), $1,000 soft daily loss limit. Picked on 2026 H1
(Jan 2 - Jun 30), checked on 2026 H2 (Jul 1 - Oct 16).

  python tools/lit_1m_manage.py check          # options off == lit_live (120 trades, +$41,734) and == lit_tight_eval_800_25_room60
  python tools/lit_1m_manage.py grid entry     # entry variants  -> research/lit/m1_results.json
  python tools/lit_1m_manage.py grid loss      # loss-management variants
  python tools/lit_1m_manage.py grid profit    # profit-management variants
  python tools/lit_1m_manage.py combos         # combinations of the shortlisted pieces
  python tools/lit_1m_manage.py diag           # per signal: losers cut early ($ saved) vs winners killed ($ lost)
  python tools/lit_1m_manage.py save           # store the runs lit_1m_* (rl.save, family other, tags lit, lit_1m)
1 CPU process each.
"""
from __future__ import annotations

import collections
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from tools import lit_final as F  # noqa: E402
from tools import lit_tightstop as TS  # noqa: E402
from tools import runlib as rl  # noqa: E402

OUT = os.path.join(ROOT, "research", "lit", "m1_results.json")
OUT_DIAG = os.path.join(ROOT, "research", "lit", "m1_diag.json")
PV, COMM, SLIP, TICK = lit.PV, lit.COMM, lit.SLIP, lit.TICK
LIVE = TS.LIVE
S26 = [d for d in F.SESS if d >= "2026-01-01"]
EVAL = ("lit", 800, 25.0)            # lit_sizing mode "eval"
ROOM = 0.6
LITR = ("lit", 800, 20.0)            # the LIT rule (normal mode), for the check against lit_live
XDEF = {"idm1": None, "disp1": None, "absorb": None, "patience": None, "pull": None,
        "x_cisd": None, "x_newlow": None, "x_accept": None, "x_opp": None, "x_es": None, "x_vol": None,
        "p_bos": None, "p_lvl": None, "p_be": None, "cut_counts": True, "cut_frac": None}


# ================================================================================================ context (1m extras, ES)
class Ctx:
    def __init__(self):
        P = LIVE
        self.M, self.C = F.market(P["ref"], P["extra_boxes"])
        self.B5 = F.bars(self.M, "5m")
        self.B1 = F.bars(self.M, "1m")
        B = self.B1
        from engine.data import load_ltf, load
        raw, _ = load_ltf("NQ", self.M.b)
        j = np.searchsorted(raw.t, B.t)
        assert (raw.t[np.minimum(j, len(raw.t) - 1)] == B.t).all()
        self.v1 = np.asarray(raw.v, float)[j]
        self.atr1 = lit.atr(B.h, B.l, B.c)
        fh, fl = lit.fractals(B.h, B.l)
        self.isfh = np.zeros(B.n, bool); self.isfh[fh] = True
        self.isfl = np.zeros(B.n, bool); self.isfl[fl] = True
        cs = np.r_[0.0, np.cumsum(self.v1)]
        idx = np.arange(B.n)
        lo = np.maximum(idx - 20, 0)
        cnt = np.maximum(idx - lo, 1)
        self.vavg = (cs[idx] - cs[lo]) / cnt            # mean volume of the 20 bars BEFORE each bar
        self.vavg[idx < 20] = np.nan
        es = load("ES", "5m")
        self.es_t, self.es_h, self.es_l, self.es_c = es.t, es.h, es.l, es.c

    def swing_low(self, d):
        """direction-space swing lows (d=1: fractal lows, d=-1: fractal highs)"""
        return self.isfl if d == 1 else self.isfh

    def swing_high(self, d):
        return self.isfh if d == 1 else self.isfl

    def es_dir(self, d):
        return (self.es_h, self.es_l, self.es_c) if d == 1 else (-self.es_l, -self.es_h, -self.es_c)


_CTX = None
_AT = TS.at_size


def at_size(t, mi, mn, cum=0.0):
    """TS.at_size with a partial cut: legs [(f, pts), (1 - f, pts)] -> int(q x f) micros out at the cut (min 0), the rest
    at the final exit; commission on every micro once."""
    legs = t["legs"]
    if len(legs) == 1:
        return _AT(t, mi, mn, cum)
    q = mi + 10 * mn
    q1 = int(q * legs[0][0] + 1e-9)
    pts = (q1 * legs[0][1] + (q - q1) * legs[1][1]) / q
    return _AT({**t, "legs": [(1.0, pts)]}, mi, mn, cum)


TS.at_size = at_size


def ctx():
    global _CTX
    if _CTX is None:
        _CTX = Ctx()
    return _CTX


def X_of(X=None):
    return {**XDEF, **(X or {})}


# ================================================================================================ executor (unit size)
def msim(X, z, entry_px, tgt_lvl, fb, stop0, use1):
    """lit.simulate_x (research mode, 1m CISD entry) at 1 micro plus the X options. Returns a unit trade or None."""
    cx = ctx(); M = cx.M
    P = LIVE
    B = cx.B1 if use1 else cx.B5
    on1 = use1 and B.secs == 60
    d = z["dir"]
    hi_d, lo_d, c_d, o_d = B.dirs(d)
    _, _, c_m, o_m = B.dirs(-d)                # mirrored (against-trade) space for CISD against
    t0 = int(M.t[z["entry_i"]])
    k0 = int(np.searchsorted(B.t, t0))
    s_day = int(M.day_of[z["entry_i"]])
    if k0 >= B.n:
        return None
    flat = P["flat_mod"]
    wait_s = P["wait"] * 300
    cis = P.get("cisd1m")
    if cis and B.secs == 300:
        cis = max(1, cis // 5)
    limit_fill = True
    fill = tapped = kconf = lowk = None
    k = k0
    while k < B.n:
        if B.day[k] != s_day or B.mod[k] >= flat or B.mod[k] >= 1080:
            break
        if tapped is None and B.t[k] >= t0 + wait_s:
            break
        if lo_d[k] <= stop0:
            if tapped is None and lo_d[k] <= entry_px and not cis:
                fill = k; entry = min(entry_px, float(o_d[k]))
            break
        if tapped is None and lo_d[k] <= entry_px:
            if cis:
                tapped = k
            else:
                fill = k; entry = min(entry_px, float(o_d[k])); break
        if tapped is None and hi_d[k] >= tgt_lvl:
            break
        if tapped is not None:
            if k - tapped > cis:
                break
            lowk = tapped + int(np.argmin(lo_d[tapped:k + 1]))
            cz = lit._cisd_level(c_d, o_d, lowk)
            if cz is not None and k > lowk and c_d[k] > cz[0] and k + 1 < B.n and B.day[k + 1] == s_day:
                kconf = k
                fill = k + 1; entry = float(o_d[k + 1]) + SLIP; limit_fill = False
                break
        k += 1
    if fill is None:
        return None
    e_m, why = 1.0, []
    # ---------------------------------------------------------------- entry intelligence (1m days with a 1m CISD only)
    if on1 and kconf is not None:
        kc = kconf
        if X["idm1"]:
            o = X["idm1"]
            a = max(0, tapped - int(o.get("pre", 0)))
            sl = cx.swing_low(d)
            ok = any(sl[j] and lo_d[lowk] < lo_d[j] and j + 2 <= kc for j in range(a, lowk))
            if not ok:
                if o["mode"] == "req":
                    return None
                e_m *= 0.5; why.append("no 1m inducement")
        if X["disp1"]:
            o = X["disp1"]
            rng = hi_d[kc] - lo_d[kc]
            body = (c_d[kc] - o_d[kc]) / max(cx.atr1[kc], 1e-9)
            cloc = (c_d[kc] - lo_d[kc]) / rng if rng > 0 else 0.0
            vr = cx.v1[kc] / cx.vavg[kc] if cx.vavg[kc] and not np.isnan(cx.vavg[kc]) else 0.0
            ok = body >= o.get("body", 0.0) and cloc >= o.get("cloc", 0.0) and vr >= o.get("vol", 0.0)
            if not ok:
                if o["mode"] == "req":
                    return None
                e_m *= 0.5; why.append("weak 1m displacement")
        if X["absorb"]:
            o = X["absorb"]
            kb = tapped if o.get("bar", "low") == "tap" else lowk
            rng = hi_d[kb] - lo_d[kb]
            wick = (min(o_d[kb], c_d[kb]) - lo_d[kb]) / rng if rng > 0 else 0.0
            vr = cx.v1[kb] / cx.vavg[kb] if cx.vavg[kb] and not np.isnan(cx.vavg[kb]) else 0.0
            ok = vr >= o.get("vol", 0.0) and wick >= o.get("wick", 0.0)
            if not ok:
                if o["mode"] == "req":
                    return None
                e_m *= 0.5; why.append("no absorption")
        if X["patience"]:
            o = X["patience"]
            lowp = lo_d[lowk]
            if "frac" in o and (c_d[kc] - lowp) / max(tgt_lvl - lowp, 1e-9) > o["frac"]:
                return None
            if "r" in o and (c_d[kc] - entry_px) / max(entry_px - stop0, 1e-9) > o["r"]:
                return None
        if X["pull"]:
            o = X["pull"]
            L = 0.5 * (o_d[kc] + c_d[kc]) if o.get("px", "body50") == "body50" else 0.5 * (hi_d[kc] + lo_d[kc])
            fill = None
            for b in range(kc + 1, min(B.n, kc + 1 + int(o["wait"]))):
                if B.day[b] != s_day or B.mod[b] >= flat or B.mod[b] >= 1080:
                    break
                if lo_d[b] <= stop0:
                    break
                if lo_d[b] <= L:
                    fill = b; entry = min(L, float(o_d[b])); limit_fill = True
                    break
                if hi_d[b] >= tgt_lvl:
                    break
            if fill is None:
                return None
    risk = entry - stop0
    if risk <= 0 or lit.qty_for(risk) < 1:
        return None
    if fb:
        tg = entry + P["fallback_rr"] * risk
    else:
        dist = tgt_lvl - entry
        if dist < P["min_rr"] * risk:
            return None
        tg = entry + (min(dist, P["max_rr"] * risk) if P["max_rr"] else dist)
    # ---------------------------------------------------------------- management context
    sw_lvl = max(z["sw"].values()) if z.get("sw") else None
    lv = []
    if on1 and X["p_lvl"]:
        xx = M.ctx[z["k"]]
        names = X["p_lvl"].get("lv", ("o18", "o00", "box"))
        if "o18" in names:
            lv.append(("o18", xx["open18"] * d))
        if "box" in names:
            for nm in z["swept"]:
                base = nm[:-2]
                if base in lit.SESSIONS and base in xx and nm.endswith("_l" if d == 1 else "_h"):
                    hi_, lo_, _ = xx[base]
                    lv.append(("box", hi_ if d == 1 else -lo_))
    es_ext = None
    if on1 and X["x_es"]:
        ta = int(M.t[z["ext_i"]]) - 1800
        tb = int(B.t[fill]) // 300 * 300            # 5m bars that closed before the fill's 5m bar
        a = int(np.searchsorted(cx.es_t, ta)); b = int(np.searchsorted(cx.es_t, tb))
        eh, el, ec = cx.es_dir(d)
        if b > a:
            es_ext = float(el[a:b].min())
    be_r = P["be_r"]
    be_lvl = None if be_r is None else entry + be_r * risk
    if on1 and X["p_bos"] and not X["p_bos"].get("be", True):
        be_lvl = None
    cur, be_done, mfe, mae, worst = stop0, False, 0.0, 0.0, 0.0
    hk = fill
    used_sh = set()
    touched = set()
    pend = None
    cutlvl = None
    es_bad = False
    cf = float(X.get("cut_frac") or 1.0) if on1 else 1.0
    part = None                          # (fraction, points) of a partial cut
    k = fill
    exit_px = kind = None
    sl_d = cx.swing_low(d) if on1 else None
    sh_d = cx.swing_high(d) if on1 else None
    while k < B.n:
        if B.day[k] != s_day or B.mod[k] >= 1080:
            k -= 1; exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        if pend is not None:
            if cf < 1.0 and part is None:
                part = (cf, float(o_d[k]) - SLIP - entry, pend); pend = None
            else:
                exit_px, kind = float(o_d[k]) - SLIP, pend
                break
        mae = max(mae, (entry - lo_d[k]) / risk)
        worst = min(worst, lo_d[k] - entry)
        if cutlvl is not None and cutlvl[0] > cur and lo_d[k] <= cutlvl[0]:      # resting stop order above the stop: hit first
            px = min(cutlvl[0], float(o_d[k])) - SLIP
            if cf < 1.0 and part is None:
                part = (cf, px - entry, cutlvl[1]); cutlvl = None
            else:
                exit_px, kind = px, cutlvl[1]; break
        if lo_d[k] <= cur:
            exit_px, kind = cur - SLIP, ("TRAIL" if cur > entry + 1e-9 or (cur > stop0 and not be_done) else "BE" if be_done else "STOP"); break
        if not (k == fill and limit_fill):
            mfe = max(mfe, (hi_d[k] - entry) / risk)
            if hi_d[k] >= tg:
                exit_px, kind = tg, "TARGET"; break
            if be_lvl is not None and not be_done and hi_d[k] >= be_lvl:
                strong = False
                if on1 and X["p_be"] and be_lvl == entry + be_r * risk:
                    strong = (B.t[k] - B.t[fill]) / 60.0 <= X["p_be"]["fast"]
                if strong:
                    alt = X["p_be"].get("alt")
                    be_lvl = None if alt is None else entry + alt * risk
                else:
                    cur, be_done = max(cur, entry), True
        if B.mod[k] >= flat:
            exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        if hi_d[k] >= hi_d[hk]:
            hk = k
        # ---------------------------------------------------------------- signals at the close of bar k (act at k+1)
        if on1:
            mins = (B.t[k] - B.t[fill]) / 60.0
            nxt_ok = k + 1 < B.n and B.day[k + 1] == s_day and B.mod[k + 1] < 1080
            sig = None
            live_cut = part is None
            o = X["x_cisd"] if live_cut else None
            if o and mfe < o["mfe"] and (o.get("win") is None or mins <= o["win"]) and k > hk:
                cz = lit._cisd_level(c_m, o_m, hk)
                if cz is not None and c_d[k] < -cz[0]:
                    sig = "CUT_CISD"
            o = X["x_newlow"] if live_cut else None
            if o and sig is None and mfe < o["mfe"] and mins <= o["win"]:
                ref = lo_d[fill] if o.get("ref", "fill") == "fill" else lo_d[kconf if kconf is not None else fill]
                if o.get("how", "close") == "close":
                    if k > fill and c_d[k] < ref:
                        sig = "CUT_LOW"
                else:
                    cutlvl = (ref - TICK, "CUT_LOW") if mins < o["win"] else None
            o = X["x_accept"] if live_cut else None
            if o and sig is None and sw_lvl is not None and mfe < o.get("mfe", 99):
                n = int(o["k"])
                if k - n + 1 >= fill and (c_d[k - n + 1:k + 1] < sw_lvl).all():
                    sig = "CUT_ACCEPT"
            o = X["x_opp"] if live_cut else None
            if o and sig is None and mfe < o["mfe"]:
                js = [j for j in range(fill, k - 1) if sl_d[j]]
                if js:
                    jl = js[-1]
                    if o.get("how", "touch") == "close":
                        if c_d[k] < lo_d[jl]:
                            sig = "CUT_HL"
                    else:
                        cutlvl = (lo_d[jl] - TICK, "CUT_HL")
            o = X["x_es"] if live_cut else None
            if o and sig is None and es_ext is not None and mfe < o["mfe"]:
                if not es_bad and (int(B.t[k]) + 60) % 300 == 0:
                    ie = int(np.searchsorted(cx.es_t, int(B.t[k]) - 240))
                    if ie < len(cx.es_t) and cx.es_t[ie] == int(B.t[k]) - 240 and cx.es_t[ie] >= int(B.t[fill]) // 300 * 300:
                        eh, el, ec = cx.es_dir(d)
                        v = el[ie] if o.get("how", "low") == "low" else ec[ie]
                        if v < es_ext - TICK:
                            es_bad = True
                            if not o.get("cisd"):
                                sig = "CUT_ES"
                if es_bad and o.get("cisd") and sig is None and k > hk:
                    cz = lit._cisd_level(c_m, o_m, hk)
                    if cz is not None and c_d[k] < -cz[0]:
                        sig = "CUT_ES"
            o = X["x_vol"] if live_cut else None
            if o and sig is None and mfe < o["mfe"] and k > fill:
                vr = cx.v1[k] / cx.vavg[k] if cx.vavg[k] and not np.isnan(cx.vavg[k]) else 0.0
                if c_d[k] < o_d[k] and vr >= o["vol"] and (o_d[k] - c_d[k]) >= o["body"] * cx.atr1[k]:
                    sig = "CUT_VOL"
            o = X["p_lvl"] if live_cut else None
            if o and sig is None and (lv or "o00" in o.get("lv", ())):
                for nm, L in lv:
                    if entry + o.get("min_r", 0.5) * risk <= L < tg and hi_d[k] >= L - o.get("tol", 0.0):
                        touched.add(nm)
                if "o00" in o.get("lv", ("o18", "o00", "box")):
                    i5 = int(np.searchsorted(M.t, B.t[k], side="right") - 1)
                    ov = M.open_00[i5]
                    if not np.isnan(ov) and entry + o.get("min_r", 0.5) * risk <= ov * d < tg and hi_d[k] >= ov * d - o.get("tol", 0.0) \
                            and M.day_of[i5] == s_day:
                        touched.add("o00")
                if touched and k > hk:
                    cz = lit._cisd_level(c_m, o_m, hk)
                    if cz is not None and c_d[k] < -cz[0] and c_d[k] > entry:
                        sig = "LVL"
            o = X["p_bos"]
            if o:
                base = lowk if lowk is not None else fill
                shs = [j for j in range(base, k - 1) if sh_d[j] and j not in used_sh]
                if shs:
                    js = shs[-1]
                    if c_d[k] > hi_d[js] and c_d[k - 1] <= hi_d[js] and (c_d[k] - o_d[k]) >= o["body"] * cx.atr1[k] \
                            and mfe >= o.get("min_r", 0.0):
                        hl = float(lo_d[js:k + 1].min()) - TICK
                        if hl > cur and hl < c_d[k]:
                            cur = hl
                        used_sh.update(j for j in shs)
            if sig is not None:
                if nxt_ok:
                    pend = sig
                elif cf < 1.0:
                    pass                          # no next bar: the rest is closed by the day's end anyway
                else:
                    exit_px, kind = float(c_d[k]) - SLIP, sig
                    break
        k += 1
    if exit_px is None:
        return None
    legs = [(1.0, exit_px - entry)]
    if part is not None:
        legs = [(part[0], part[1]), (1.0 - part[0], exit_px - entry)]
        kind = kind + "+" + part[2]
    xi5 = int(np.searchsorted(M.t, B.t[k], side="right") - 1)
    return {"day": z["day"], "entry_t": int(B.t[fill]), "exit_t": int(B.t[k]) + B.secs, "exit_i": xi5, "dir": d,
            "risk_pts": round(risk, 2), "risk0": round(risk, 2), "exit": kind, "trigger": "LIT-" + ("1m" if B.secs == 60 else "5m"),
            "mfe": round(mfe, 3), "mae": round(min(mae, 1.0 + SLIP / risk), 3), "bars_held": int(k - fill + 1), "regime": "",
            "half": False, "legs": legs, "pts": sum(w * p for w, p in legs), "w1": worst, "w2": 0.0, "part": False, "e_m": e_m, "e_why": why,
            "entry_px": round(entry * d, 2), "stop_px": round(stop0 * d, 2), "target_px": round(tg * d, 2),
            "limit_fill": limit_fill, "swept": z["swept"], "tf": B.secs // 60, "i": z["i"], "ext_i": z["ext_i"]}


def mrun(X=None, sessions=S26):
    """Unit trades of one variant (the lit._run_core research loop + X)."""
    X = X_of(X)
    cx = ctx(); M = cx.M
    P = LIVE
    names = set(P["sweep_names"]) if P.get("sweep_names") else None
    sset = set(sessions) if sessions else None
    out, busy, per_day = [], -1, collections.Counter()
    for z in cx.C:
        if sset is not None and z["day"] not in sset:
            continue
        if z["entry_i"] <= busy or per_day[z["day"]] >= P["max_per_day"]:
            continue
        if not lit.setup_ok(z, P, names):
            continue
        if P.get("monday") and lit.monday_block(M, z):
            continue
        ep = min(float(z["ref_d"]), z["trig_c"])
        stop0 = z["ext_d"] - P["stop_buf"]
        risk = ep - stop0
        if not (P["min_stop"] <= risk <= P["max_stop"]):
            continue
        sh = z["entry_d"] - ep
        TT = {c: [x + sh for x in v] for c, v in lit.targets_x(M, z, P).items()}
        best = None
        for c in P["classes"]:
            for dist in TT.get(c, []):
                if dist >= P["min_rr"] * risk:
                    if best is None or dist < best:
                        best = dist
                    break
        fb = False
        if best is None:
            if not P["fallback_rr"]:
                continue
            tp, fb = P["fallback_rr"] * risk, True
        else:
            tp = min(best, P["max_rr"] * risk) if P["max_rr"] else best
        use1 = P["tf"] == "1m" and int(M.day_of[z["entry_i"]]) in cx.B1.full
        t = msim(X, z, ep, ep + tp, fb, stop0, use1)
        if t is None:
            continue
        busy = t["exit_i"]; per_day[z["day"]] += 1
        out.append(t)
    marks(out, X["cut_counts"])
    return out


def is_stop(t, cut_counts=True):
    if t["exit"].split("+")[0] == "STOP":
        return True
    return cut_counts and t["exit"].startswith("CUT") and t["pts"] < 0


def marks(U, cut_counts=True):
    """The pack's weekly stop (x0.5 after 2 stop-outs finished earlier in the ISO week) times the entry multiplier."""
    n_st, m_st = LIVE["wk_stop"] or (10 ** 9, 1.0)
    for t in U:
        wk = lit.iso_week(t["day"])
        n = sum(1 for x in U if x is not t and is_stop(x, cut_counts) and lit.iso_week(x["day"]) == wk and x["exit_t"] <= t["entry_t"])
        t["wk_m"] = (float(m_st) if n >= n_st else 1.0) * t.get("e_m", 1.0)


_U = {}


def unit(X=None):
    key = json.dumps(X or {}, sort_keys=True, default=str)
    if key not in _U:
        _U[key] = mrun(X)
    return _U[key]


SP = ("H1", "H2", "2026")


def score(U, rule=EVAL, room_k=ROOM):
    o = TS.score(U, rule, room_k=room_k, spans=SP)
    # avg win / avg loss $ at the eval size without the room cap (per trade, exact)
    T = TS.sized(U, rule)
    for s in SP:
        a, zz = F.SPAN[s]
        p = np.array([t["pnl"] for t in T if a <= t["day"] <= zz])
        o[s]["avg_win"] = round(float(p[p > 0].mean())) if (p > 0).any() else None
        o[s]["avg_loss"] = round(float(p[p < 0].mean())) if (p < 0).any() else None
        o[s]["exits"] = dict(collections.Counter(t["exit"] for t in T if a <= t["day"] <= zz))
    return o


def line(nm, o):
    def f(s):
        if not s or not s.get("n"):
            return "n=0"
        return (f"n={s['n']} {s['tpw']}/wk win {s['win']} PF {s['pf']} net {s['net']:+,} ${s['per_month']:,}/mo DD {s['dd']:,} "
                f"aw {s['avg_win']} al {s['avg_loss']} 2w {s['p10']}/{s['f10']} 1m {s['p20']}/{s['f20']} pr {s['pass_rate']} med {s['pass_med']}")
    return f"{nm:42s} H1[{f(o['H1'])}] H2[{f(o['H2'])}]"


# ================================================================================================ check
def check():
    U = unit()
    T = TS.sized(U, LITR)
    L = [t for t in F.run(LIVE) if t["day"] >= "2026-01-01"]
    ka = [(t["day"], t["entry_t"], round(t["pnl"], 2), t["exit"], t["qty"]) for t in sorted(L, key=lambda t: t["entry_t"])]
    kb = [(t["day"], t["entry_t"], round(t["pnl"], 2), t["exit"], t["qty"]) for t in T]
    bad = [(x, y) for x, y in zip(ka, kb) if not (x[:2] == y[:2] and abs(x[2] - y[2]) < 0.03 and x[3:] == y[3:])]
    print(f"lit_live 2026 {len(ka)} trades {sum(t['pnl'] for t in L):+,.0f} | 1m-manage off {len(kb)} trades "
          f"{sum(t['pnl'] for t in T):+,.0f} | mismatches {len(bad) + abs(len(ka) - len(kb))}")
    for x in bad[:3]:
        print("diff", x)
    o = score(U)
    print(line("eval base (800/25 + room 60%)", o))
    return not bad and len(ka) == len(kb)


# ================================================================================================ variants
def variants(group):
    V = collections.OrderedDict()
    if group == "entry":
        for pre in (0, 5, 15):
            for mode in ("req", "half"):
                V[f"idm1 pre{pre} {mode}"] = {"idm1": {"pre": pre, "mode": mode}}
        for b in (0.5, 1.0, 1.5):
            for mode in ("req", "half"):
                V[f"disp1 body>={b} ATR1m {mode}"] = {"disp1": {"body": b, "mode": mode}}
        for cl in (0.5, 0.75):
            for mode in ("req", "half"):
                V[f"disp1 close top {int((1 - cl) * 100)}% {mode}"] = {"disp1": {"cloc": cl, "mode": mode}}
        for v in (1.5, 2.0):
            for mode in ("req", "half"):
                V[f"disp1 vol>={v}x {mode}"] = {"disp1": {"vol": v, "mode": mode}}
        V["disp1 body>=1 + top half + vol>=1.5 half"] = {"disp1": {"body": 1.0, "cloc": 0.5, "vol": 1.5, "mode": "half"}}
        for bar in ("tap", "low"):
            for v, w in ((2.0, 0.0), (1.5, 0.4), (0.0, 0.5), (2.0, 0.4)):
                for mode in ("req", "half"):
                    V[f"absorb {bar} vol>={v} wick>={w} {mode}"] = {"absorb": {"bar": bar, "vol": v, "wick": w, "mode": mode}}
        for fr in (0.1, 0.15, 0.2, 0.3):
            V[f"patience run>{int(fr * 100)}% to target: skip"] = {"patience": {"frac": fr}}
        for r in (0.25, 0.5, 0.75):
            V[f"patience >{r}R above the limit: skip"] = {"patience": {"r": r}}
        for px in ("body50", "range50"):
            for w in (5, 10, 20):
                V[f"pull {px} limit {w} bars"] = {"pull": {"px": px, "wait": w}}
    elif group == "loss":
        for m in (0.25, 0.5, 1.0):
            for w in (None, 30):
                V[f"x_cisd mfe<{m} win{w}"] = {"x_cisd": {"mfe": m, "win": w}}
        for ref in ("fill", "conf"):
            for w in (5, 10, 15, 30):
                for how in ("close", "touch"):
                    V[f"x_newlow {ref} {w}min {how}"] = {"x_newlow": {"ref": ref, "win": w, "how": how, "mfe": 0.5}}
        for n in (1, 2, 3, 5):
            V[f"x_accept {n} closes"] = {"x_accept": {"k": n}}
            V[f"x_accept {n} closes mfe<0.5"] = {"x_accept": {"k": n, "mfe": 0.5}}
        for m in (0.5, 1.0):
            for how in ("touch", "close"):
                V[f"x_opp HL taken mfe<{m} {how}"] = {"x_opp": {"mfe": m, "how": how}}
        for m in (0.5, 1.0):
            for how in ("low", "close"):
                V[f"x_es new extreme mfe<{m} {how}"] = {"x_es": {"mfe": m, "how": how}}
        for v in (2.0, 3.0):
            for b in (0.5, 1.0):
                for m in (0.5,):
                    V[f"x_vol vol>={v} body>={b} mfe<{m}"] = {"x_vol": {"vol": v, "body": b, "mfe": m}}
    elif group == "profit":
        for b in (0.75, 1.0, 1.5):
            for be in (True, False):
                V[f"p_bos body>={b} be1R={be}"] = {"p_bos": {"body": b, "be": be}}
            V[f"p_bos body>={b} after 1R be1R=True"] = {"p_bos": {"body": b, "be": True, "min_r": 1.0}}
        for lvs in (("o18",), ("o00",), ("box",), ("o18", "o00", "box")):
            for mr in (0.5, 1.0, 2.0):
                V[f"p_lvl {'+'.join(lvs)} min {mr}R"] = {"p_lvl": {"lv": lvs, "min_r": mr}}
        for fast in (5, 10, 15, 30):
            for alt in (None, 2.0):
                V[f"p_be 1R within {fast}min -> BE at {alt}"] = {"p_be": {"fast": fast, "alt": alt}}
    elif group == "more":
        for lvs in (("o00",), ("o18", "o00", "box")):
            for mr in (0.5, 1.0, 2.0):
                V[f"p_lvl {'+'.join(lvs)} min {mr}R"] = {"p_lvl": {"lv": lvs, "min_r": mr}}
        for mr in (1.5, 3.0):
            V[f"p_lvl o18 min {mr}R"] = {"p_lvl": {"lv": ("o18",), "min_r": mr}}
        for m in (0.25, 0.5, 0.75, 99):
            for how in ("low", "close"):
                for cz in (False, True):
                    V[f"x_es {how} mfe<{m}{' + 1m CISD' if cz else ''}"] = {"x_es": {"mfe": m, "how": how, "cisd": cz}}
        V["x_es close mfe<0.5 (cut not a stop)"] = {"x_es": {"mfe": 0.5, "how": "close"}, "cut_counts": False}
        V["x_es low mfe<0.5 (cut not a stop)"] = {"x_es": {"mfe": 0.5, "how": "low"}, "cut_counts": False}
        for f in (0.5,):
            V[f"half-cut x_cisd mfe<0.25"] = {"x_cisd": {"mfe": 0.25, "win": None}, "cut_frac": f}
            V[f"half-cut x_cisd mfe<0.5"] = {"x_cisd": {"mfe": 0.5, "win": None}, "cut_frac": f}
            V[f"half-cut x_newlow conf 10min close"] = {"x_newlow": {"ref": "conf", "win": 10, "how": "close", "mfe": 0.5}, "cut_frac": f}
            V[f"half-cut x_newlow conf 15min close"] = {"x_newlow": {"ref": "conf", "win": 15, "how": "close", "mfe": 0.5}, "cut_frac": f}
            V[f"half-cut x_opp mfe<0.5 touch"] = {"x_opp": {"mfe": 0.5, "how": "touch"}, "cut_frac": f}
            V[f"half-cut x_accept 3 closes mfe<0.5"] = {"x_accept": {"k": 3, "mfe": 0.5}, "cut_frac": f}
            V[f"half-cut x_vol vol>=3 body>=0.5"] = {"x_vol": {"vol": 3.0, "body": 0.5, "mfe": 0.5}, "cut_frac": f}
            V[f"half-cut x_es close mfe<0.5"] = {"x_es": {"mfe": 0.5, "how": "close"}, "cut_frac": f}
            V[f"half-cut x_es low mfe<0.75"] = {"x_es": {"mfe": 0.75, "how": "low"}, "cut_frac": f}
        V["x_es close 0.5 + p_lvl o18 2R"] = {"x_es": {"mfe": 0.5, "how": "close"}, "p_lvl": {"lv": ("o18",), "min_r": 2.0}}
        V["x_es low 0.5 + p_lvl o18 1R"] = {"x_es": {"mfe": 0.5, "how": "low"}, "p_lvl": {"lv": ("o18",), "min_r": 1.0}}
        V["x_es close 0.5 + p_lvl o18 1R"] = {"x_es": {"mfe": 0.5, "how": "close"}, "p_lvl": {"lv": ("o18",), "min_r": 1.0}}
    return V


def _load(path=OUT):
    return json.load(open(path)) if os.path.exists(path) else {}


def _store(res, path=OUT):
    tmp = f"{path}.{os.getpid()}.tmp"
    json.dump(res, open(tmp, "w"), indent=1, default=str)
    if os.path.exists(path):          # merge with what another process stored meanwhile
        cur = json.load(open(path))
        cur.update(json.load(open(tmp)))
        json.dump(cur, open(tmp, "w"), indent=1, default=str)
    os.replace(tmp, path)


def grid(group, V=None):
    V = V or variants(group)
    res = {}
    base = score(unit())
    res["base"] = {"X": {}, "o": base}
    print(line("base", base), flush=True)
    for nm, X in V.items():
        o = score(unit(X))
        res[nm] = {"X": X, "o": o, "group": group}
        print(line(nm, o), flush=True)
    _store(res)
    return res


# ================================================================================================ diagnostics
def diag(names=None):
    """Trade by trade vs the live path (same entries): losers cut early ($ saved) and winners killed ($ lost), at the eval
    size of the live trade (exact; no room cap)."""
    res = _load()
    B = {(t["day"], t["entry_t"]): t for t in unit()}
    Tq = {(t["day"], t["entry_t"]): t for t in TS.sized(unit(), EVAL)}
    out = {}
    for nm, rec in res.items():
        if nm == "base" or (names and nm not in names):
            continue
        X = rec["X"]
        if any(X.get(k) for k in ("idm1", "disp1", "absorb", "patience", "pull")):
            continue                     # entry rules change the trade set: not a like-for-like diagnostic
        U = unit(X)
        o = {}
        for s in SP:
            a, zz = F.SPAN[s]
            r = {"losers": 0, "losers_cut": 0, "saved": 0.0, "winners": 0, "winners_killed": 0, "lost": 0.0,
                 "be": 0, "be_cut": 0, "be_d": 0.0, "net_d": 0.0, "fires": 0}
            for t in U:
                if not (a <= t["day"] <= zz):
                    continue
                b = B.get((t["day"], t["entry_t"]))
                if b is None:
                    continue
                q = Tq[(t["day"], t["entry_t"])]["micros"]
                dd_ = (t["pts"] - b["pts"]) * PV * q
                r["net_d"] += dd_
                fired = t["exit"] != b["exit"] or abs(t["pts"] - b["pts"]) > 1e-6
                r["fires"] += fired
                if b["exit"] == "STOP":
                    r["losers"] += 1
                    if fired:
                        r["losers_cut"] += 1; r["saved"] += dd_
                elif b["pts"] > 0.5:
                    r["winners"] += 1
                    if fired and dd_ < 0:
                        r["winners_killed"] += 1; r["lost"] += dd_
                    elif fired:
                        r["lost"] += dd_
                else:
                    r["be"] += 1
                    if fired:
                        r["be_cut"] += 1; r["be_d"] += dd_
            o[s] = {k: (round(v) if isinstance(v, float) else v) for k, v in r.items()}
        out[nm] = o
        h1, h2 = o["H1"], o["H2"]
        print(f"{nm:42s} H1 losers cut {h1['losers_cut']}/{h1['losers']} saved {h1['saved']:+,} winners killed {h1['winners_killed']}/{h1['winners']} "
              f"{h1['lost']:+,} BE {h1['be_d']:+,} net {h1['net_d']:+,} | H2 losers cut {h2['losers_cut']}/{h2['losers']} saved {h2['saved']:+,} "
              f"winners killed {h2['winners_killed']}/{h2['winners']} {h2['lost']:+,} BE {h2['be_d']:+,} net {h2['net_d']:+,}", flush=True)
    json.dump(out, open(OUT_DIAG, "w"), indent=1)
    return out


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        check()
    elif cmd == "grid":
        grid(sys.argv[2])
    elif cmd == "diag":
        diag(sys.argv[2:] or None)
