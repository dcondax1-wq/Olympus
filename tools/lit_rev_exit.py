"""LIT reversal exits (owner 2026-10-28, after the first real live LIT trade): profit-protect on a violent reversal, trailing
after MFE >= k R, a "near-1R" breakeven, and a tighter "first highs" stop.

The trade of 2026-10-28: SHORT 5 MNQ @ 29,945.00 03:43 ET, stop 29,987.50 (42.5 pts), target 29,665.75. Low 29,904.50 at
03:56 (0.95R, BE at 1R never triggered), then four big green 1m candles 03:56-03:59 and the stop filled 04:01 @ 29,987.75
(-$437). Owner: "we probably should have trailed; the stop shouldn't be that big, maybe at the first highs; after those long
green candles the bot should have known we were reversing".

Same live LIT trades (tools/lit_final.run with live_model.json "lit": 631 trades, 120 in 2026, == run lit_live). Only what
happens after the fill changes (1 trade a day, flat 15:55, so the trade list never changes). The executor below is the
post-fill part of engine/lit.simulate_x (stop before target in a bar, BE at 1R -> entry + 1.25, the 15-minute check, flat
15:55); with every new option off it gives every live trade's exit and points exactly (`check`).

New options (X), all decided at a bar's CLOSE and acting from the next bar (no look-ahead):
  rev    {"k": R, "trig": "bar"|"run2"|"run3"|"retr", "m": ATR multiple, "g": retrace share, "act": "exit"|"be"|"be0",
          "scope": "any"|"pre"}: once the best point so far is >= k R, a 1m candle closing against by >= m x ATR(14) of the bar
          before ("bar"), 2 / 3 candles in a row all closing against with open-to-close >= m x ATR ("run2"/"run3"), or the
          close giving back >= g of the best open profit ("retr") -> exit at the next open - 1 tick ("exit"), or the stop to
          entry + 1.25 ("be") / entry ("be0"); scope "pre" = only while the 1R breakeven has not happened yet.
  trail  {"k": R, "tf": 1|5, "lock": bool}: once the best point is >= k R, the stop ratchets to 1 tick beyond the last
          confirmed swing (fractal k=2, confirmed at j+2's close) made after the fill (lock: only once that swing is beyond
          entry + 1.25).
  be_r   breakeven trigger in R (live 1.0; tested 0.75 / 0.9), still at entry + 1.25.
  tight  {"tf": 1|5, "tgt": "same"|"cap8", "min": pts}: the stop at 1 tick beyond the nearest swing high (short) / low (long)
          between the entry and the sweep extreme, confirmed and untaken before the fill (fallback: the live stop). Size,
          breakeven R, t_check R follow the new stop; tgt "same" keeps the live target price, "cap8" re-banks at 8 new R.
Any stop that a new rule moved fills at min(stop, bar open) - 1 tick (a gap through it fills at the open).

Money: (1) the LIT size rule (as run lit_live: $800 up to 20 pts, x the weekly stop, $1.40 + 1 tick) for 2026 H1/H2 and
2021-25 (5m bars there: ATR / swings / candles on 5m; t_check off on 5m as live); (2) the live eval path: lit_sizing two_week
(room_f 0.8, no weekly loss stop, safe_eval after session 10, $1.90) on back-to-back MFFU 50K evals, and the eval odds of a
fresh eval started on every session (tools/lit_adv_manage.run_eval, horizon 60 inside the half) + its 2,000-path MC.

  python -X utf8 tools/lit_rev_exit.py check    # options off == live trades (exit + points), today's trade replayed
  python -X utf8 tools/lit_rev_exit.py grid     # every variant -> research/lit/rev_exit_results.json
  python -X utf8 tools/lit_rev_exit.py save     # rl.save runs lit_rev_*
Paper only; engine/ and live_model*.json untouched.
"""
from __future__ import annotations

import collections
import gzip
import io
import json
import os
import subprocess
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from tools import lit_final as F  # noqa: E402
from tools import lit_adv_manage as A  # noqa: E402
from tools import runlib as rl  # noqa: E402

OUT = os.path.join(ROOT, "research", "lit", "rev_exit_results.json")
PV, COMM, SLIP, TICK = lit.PV, lit.COMM, lit.SLIP, lit.TICK
LIVE = {**lit.DEFAULTS, **json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]}
BE_OFF = float(LIVE.get("be_off") or 0.0)
SPANS = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-12-31"), "2021-25": ("2021-01-01", "2025-12-31")}


# ================================================================================================ bars
class Bx:
    """Executor bars + direction-space ATR / swing arrays (cached per direction)."""

    def __init__(self, B):
        self.B = B
        self.atr = lit.atr(B.h, B.l, B.c, 14)
        self._sw = {}

    def swings(self, d):
        """bool array: j is a swing low in direction space (a long's higher low / a short's lower high)."""
        if d not in self._sw:
            hi_d, lo_d = self.B.dirs(d)[:2]
            _, fl = lit.fractals(hi_d, lo_d)
            a = np.zeros(self.B.n, bool); a[fl] = True
            fh, _ = lit.fractals(hi_d, lo_d)
            b = np.zeros(self.B.n, bool); b[fh] = True
            self._sw[d] = (a, b)        # (swing lows, swing highs) in direction space
        return self._sw[d]


_CX = {}


def cx():
    if not _CX:
        M, C = F.market(LIVE["ref"], LIVE["extra_boxes"])
        _CX["M"] = M
        _CX[60] = Bx(F.bars(M, "1m"))
        _CX[300] = Bx(F.bars(M, "5m"))
        _CX["T"] = F.run(LIVE)
    return _CX


# ================================================================================================ executor (post-fill)
def manage(X, BX, fill, d, entry, stop, tg, s_day, risk, BX5=None, t5=None):
    """Walk one filled trade from bar `fill` (direction-space prices). Returns (exit kind, exit pts, worst pts, mfe R, exit k)."""
    X = X or {}
    B = BX.B
    hi_d, lo_d, c_d, o_d = B.dirs(d)
    flat = LIVE["flat_mod"]
    on1 = B.secs == 60
    tc = LIVE.get("t_check") if on1 else None
    be_r = X.get("be_r", LIVE["be_r"])
    rev, tr = X.get("rev"), X.get("trail")
    cur, be_done, mfe, worst = stop, False, 0.0, 0.0
    moved = False                  # the stop was moved by a new rule (gap fills at the open)
    tag = None                     # exit label of a moved stop
    cut = None
    if tr:
        TB = BX if (int(tr.get("tf", 1)) * 60 == B.secs or BX5 is None or B.secs == 300) else BX5
        swl = TB.swings(d)[0]
        tlo = TB.B.dirs(d)[1]
        j_sc = int(np.searchsorted(TB.B.t, B.t[fill], side="left"))     # swings at / after the fill bar only
    atr = BX.atr
    k = fill
    exit_px = kind = None
    while k < B.n:
        if B.day[k] != s_day or B.mod[k] >= 1080:
            k -= 1; exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        if cut is not None:
            exit_px, kind = float(o_d[k]) - SLIP, cut; break
        worst = min(worst, lo_d[k] - entry)
        if lo_d[k] <= cur:
            px = min(cur, float(o_d[k])) if moved else cur
            exit_px, kind = px - SLIP, (tag if moved else ("BE" if be_done else "STOP")); break
        mfe = max(mfe, (hi_d[k] - entry) / risk)
        if hi_d[k] >= tg:
            exit_px, kind = tg, "TARGET"; break
        if be_r is not None and not be_done and hi_d[k] >= entry + be_r * risk:
            if entry + BE_OFF > cur:
                cur = entry + BE_OFF
                if moved:
                    tag = "BE"
            be_done = True
        if B.mod[k] >= flat:
            exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        if tc and not be_done and round((B.t[k] - B.t[fill]) / 60.0) + 1 == int(tc.get("at", 15)) \
                and mfe < float(tc.get("mfe", 0.5)) and c_d[k] < entry - float(tc.get("x", 0.3)) * risk:
            if k + 1 < B.n and B.day[k + 1] == s_day:
                cut = "CUT_T15"
                k += 1
                continue
        # ---- new rules at the close of bar k
        if rev and mfe >= rev["k"] and (rev.get("scope", "any") == "any" or not be_done) and k + 1 < B.n and B.day[k + 1] == s_day:
            fire = False
            a0 = float(atr[k - 1]) if k > 0 else float(atr[k])
            tg_ = rev["trig"]
            if tg_ == "bar":
                fire = (o_d[k] - c_d[k]) >= rev["m"] * a0
            elif tg_ in ("run2", "run3"):
                n = 2 if tg_ == "run2" else 3
                if k - n + 1 >= fill and all(c_d[j] < o_d[j] for j in range(k - n + 1, k + 1)):
                    fire = (o_d[k - n + 1] - c_d[k]) >= rev["m"] * (float(atr[k - n]) if k - n >= 0 else a0)
            elif tg_ == "retr":
                best = entry + mfe * risk
                fire = (best - c_d[k]) >= rev["g"] * (best - entry)
            if fire:
                act = rev.get("act", "exit")
                if act == "exit":
                    cut = "REV"
                    k += 1
                    continue
                lvl = entry + (BE_OFF if act == "be" else 0.0)
                if lvl > cur:
                    if c_d[k] <= lvl:            # already beyond the new stop: out at the next open
                        cut = "REV_BE"
                        k += 1
                        continue
                    cur, moved, tag = lvl, True, "REV_BE"
        if tr and mfe >= tr["k"]:
            TBn = TB.B
            # swings of TB confirmed by the close of bar k (TB bar j confirmed at j + 2's close)
            ie = int(np.searchsorted(TBn.t, B.t[k] + B.secs - TBn.secs, side="right"))    # TB bars closed by bar k's close
            j_best = None
            for j in range(j_sc, max(j_sc, ie - 2)):
                if swl[j]:
                    j_best = j
            if j_best is not None:
                lvl = float(tlo[j_best]) - TICK
                if (not tr.get("lock") or lvl >= entry + BE_OFF) and lvl > cur and lvl < c_d[k]:
                    cur, moved, tag = lvl, True, "TRAIL"
        k += 1
    if exit_px is None:
        return None
    return kind, exit_px - entry, worst, mfe, k


# ================================================================================================ the tighter stop
def tight_stop(t, BX, X):
    """1 tick beyond the nearest confirmed, untaken swing between the entry and the sweep extreme (direction space), or None.
    tf 5 on a 1m trade: swings of the 5m bars (confirmed by a 5m close before the fill)."""
    o = X["tight"]
    c = cx()
    M = c["M"]
    TB = c[300] if (int(o.get("tf", 1)) == 5 or BX.B.secs == 300) else BX
    return _tight(TB, t["dir"], t["entry_px"] * t["dir"], t["stop_px"] * t["dir"], t["entry_t"], int(M.t[t["ext_i"]]),
                  float(o.get("min", LIVE["min_stop"])))


def _tight(TB, d, entry, stop0, t_fill, t_ext, mn):
    B = TB.B
    lo_d = B.dirs(d)[1]
    nf = int(np.searchsorted(B.t, t_fill - B.secs, side="right"))     # bars closed before the fill
    a = int(np.searchsorted(B.t, t_ext))
    lows = TB.swings(d)[0]
    best = None
    for j in range(a + 1, nf - 2):            # confirmed at j + 2 <= nf - 1
        if not lows[j]:
            continue
        lv = float(lo_d[j])
        if not (stop0 < lv - TICK and lv < entry):
            continue
        if float(lo_d[j + 1:nf].min()) <= lv:  # taken before the fill
            continue
        if entry - (lv - TICK) < mn:
            continue
        if best is None or lv > best:
            best = lv
    return None if best is None else best - TICK


# ================================================================================================ all trades
def trades(X=None, live_trades=None):
    """Re-manage every live trade under X. Returns unit trades (points) with what the sizing needs."""
    X = X or {}
    c = cx()
    T = live_trades or c["T"]
    out = []
    for t in T:
        BX = c[60] if t["tf"] == 1 else c[300]
        B = BX.B
        d = t["dir"]
        fill = int(np.searchsorted(B.t, t["entry_t"]))
        assert int(B.t[fill]) == t["entry_t"], t["day"]
        entry, stop, tg = t["entry_px"] * d, t["stop_px"] * d, t["target_px"] * d
        tg_live = tg
        if X.get("tight"):
            ns = tight_stop(t, BX, X)
            if ns is not None:
                stop = ns
                if X["tight"].get("tgt") == "cap8":
                    tg = min(tg, entry + LIVE["max_rr"] * (entry - stop))
        risk = entry - stop
        r = manage(X, BX, fill, d, entry, stop, tg, int(B.day[fill]), risk, BX5=c[300])
        kind, pts, worst, mfe, kx = r
        out.append({"day": t["day"], "entry_t": t["entry_t"], "exit_t": int(B.t[kx]) + B.secs, "dir": d, "exit": kind,
                    "risk": round(risk, 2), "tgt": round(tg - entry, 2), "pts": round(pts, 4), "w1": round(worst, 4),
                    "legs": [(1.0, pts)], "mfe": round(mfe, 3), "tf": t["tf"], "live_exit": t["exit"],
                    "live_pts": round((t["pnl"] + COMM * t["qty"]) / (PV * t["qty"]), 4), "live_risk": t["risk_pts"],
                    "tight": round(risk, 2) != round(t["risk_pts"], 2)})
    return out


def lit_size(U):
    """The LIT size rule as run lit_live: lit.qty_for(stop) x the weekly stop (2 STOP exits in the ISO week -> half)."""
    out = []
    for u in sorted(U, key=lambda u: u["entry_t"]):
        q0 = lit.qty_for(u["risk"])
        wk = lit.iso_week(u["day"])
        ws = sum(1 for o in out if lit.iso_week(o["day"]) == wk and o["exit_t"] <= u["entry_t"]
                 and (o["exit"] == "STOP" or (o["exit"] == "TRAIL" and o["pts"] < 0)))
        m = LIVE["wk_stop"][1] if LIVE.get("wk_stop") and ws >= LIVE["wk_stop"][0] else 1.0
        q = max(1, int(q0 * m + 1e-9)) if m < 1 else q0
        pnl = u["pts"] * PV * q - COMM * q
        low = min(0.0, u["w1"] * PV * q - COMM * q, pnl)
        out.append({**u, "qty": q, "pnl": round(pnl, 2), "low": round(low, 2), "r": round(pnl / (u["risk"] * PV * q), 3),
                    "risk_pts": u["risk"], "risk_usd": round(u["risk"] * PV * q, 2), "half": m < 1, "mult": m,
                    "trigger": "LIT-%dm" % u["tf"], "mae": None, "bars_held": None, "regime": ""})
    return out


# ================================================================================================ scoring
def lit_stats(T, span):
    a, z = SPANS[span]
    ss = [d for d in F.SESS if a <= d <= z]
    TT = [t for t in T if a <= t["day"] <= z]
    p = np.array([t["pnl"] for t in TT]); gl = -p[p < 0].sum()
    eq = np.cumsum(p); dd = float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min())
    wk = collections.Counter(lit.iso_week(t["day"]) for t in TT)
    allwk = {lit.iso_week(d) for d in ss}
    days = rl.days_of(TT, ss)
    e = rl.eval_speed(days)
    return {"n": len(TT), "tpw": round(len(TT) / (len(ss) / 5), 2), "wk2": round(100 * sum(wk[w] >= 2 for w in allwk) / len(allwk)),
            "win": round(100 * float((p > 0).mean()), 1), "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None,
            "net": round(float(p.sum())), "per_month": round(float(p.sum()) / (len(ss) / 21)), "dd": round(dd),
            "tot_r": round(float(sum(t["pts"] / t["risk"] for t in TT)), 2),
            **{k: e[k] for k in ("p10", "f10", "dec10", "p15", "f15", "slow_pass", "pass_med")}}


def eval_odds(U, span, horizon=60):
    """Fresh eval on every session of the half (live two_week sizing), up to `horizon` sessions inside the half."""
    by = A.by_day(U)
    a, z = A.span_ix(span)
    res = [(A.run_eval(list(range(i, z)), by, horizon=horizon), z - i) for i in range(a, z)]
    o = {}
    for h in (10, 15):
        R = [r for r, av in res if av >= h]
        N = len(R) or 1
        o[f"p{h}"] = round(100.0 * sum(1 for r in R if r[0] == "PASS" and r[1] <= h) / N, 1)
        o[f"f{h}"] = round(100.0 * sum(1 for r in R if r[0] == "FAIL" and r[1] <= h) / N, 1)
    o["dec10"] = round(o["p10"] + o["f10"], 1)
    pas = [r[1] for r, _ in res if r[0] == "PASS"]
    o["slow_pass"] = round(100.0 * sum(1 for x in pas if x > 15) / len(pas), 1) if pas else None
    o["pass_med"] = float(np.median(pas)) if pas else None
    return o


def b2b10(U, span):
    """Back-to-back evals at the live eval size, a new eval after a pass, a fail or 10 sessions (the 2-week clock)."""
    by = A.by_day(U)
    a, z = A.span_ix(span)
    k, T, n = a, [], collections.Counter()
    while k < z:
        r, used = A.run_eval(list(range(k, z)), by, 10, keep=T)
        n[r] += 1
        k += used if r != "OPEN" else 10
    return T, n


def eval_path(U, span):
    T, n = b2b10(U, span)
    s = A.stats(T, span)
    s.pop("exits", None)
    return {**s, **eval_odds(U, span), "mc": A.mc(U, span), "b2b": f"{n['PASS']}/{n['FAIL']}/{n['OPEN']}"}


def changed(U, L):
    """Trades whose outcome changed vs live, at the LIT size: losers saved / winners killed (count, $)."""
    out = {}
    for span in ("H1", "H2", "2021-25"):
        a, z = SPANS[span]
        sv = kl = 0; sv_usd = kl_usd = 0.0; oth = 0.0; nch = 0
        for u, l in zip(U, L):
            if not (a <= u["day"] <= z):
                continue
            du = u["pnl"] - l["pnl"]
            if abs(du) < 0.5:
                continue
            nch += 1
            if l["pnl"] < 0 and du > 0:
                sv += 1; sv_usd += du
            elif l["pnl"] > 0 and du < 0:
                kl += 1; kl_usd += du
            else:
                oth += du
        out[span] = {"changed": nch, "losers_saved": sv, "saved_usd": round(sv_usd), "winners_cut": kl, "cut_usd": round(kl_usd),
                     "other_usd": round(oth)}
    return out


def evaluate(X, base_L=None):
    U = trades(X)
    L = lit_size(U)
    U26 = [u for u in U if u["day"] >= "2026"]
    o = {"X": X, "lit": {s: lit_stats(L, s) for s in ("H1", "H2", "2021-25")},
         "eval": {s: eval_path(U26, s) for s in ("H1", "H2")}}
    if base_L is not None:
        o["chg"] = changed(L, base_L)
    o["n_tight"] = sum(1 for u in U if u["tight"] and u["day"] >= "2026")
    return o, U, L


def line(nm, o):
    def f(s):
        return f"PF {s['pf']} net {s['net']:+,} DD {s['dd']:,} 2w {s['p10']}/{s['f10']}"
    e = o["eval"]
    return (f"{nm[:40]:40s} LIT H1[{f(o['lit']['H1'])}] H2[{f(o['lit']['H2'])}] 21-25[{f(o['lit']['2021-25'])}] | "
            f"EVAL H1[{f(e['H1'])} mc {e['H1']['mc']['p10']}/{e['H1']['mc']['f10']}] H2[{f(e['H2'])} mc {e['H2']['mc']['p10']}/{e['H2']['mc']['f10']}]")


# ================================================================================================ the 2026-10-28 trade
TODAY = {"day": "2026-10-28", "dir": -1, "entry": 29945.00, "stop": 29987.50, "target": 29665.75, "qty": 5,
         "entry_et": "2026-10-28 03:43", "ext_et": "2026-10-28 03:13"}


def today_bars():
    raw = subprocess.run(["git", "-C", ROOT, "show", "origin/heartbeat:bars_1m.csv.gz"], capture_output=True, check=True).stdout
    import pandas as pd
    df = pd.read_csv(io.BytesIO(gzip.decompress(raw)))
    et = pd.to_datetime(df.time, unit="s", utc=True).dt.tz_convert("America/New_York")
    # trading day = the session from 18:00 the evening before
    sday = (et + pd.Timedelta(hours=6)).dt.strftime("%Y-%m-%d")
    mod = (et.dt.hour * 60 + et.dt.minute).values
    days = sorted(set(sday))
    dix = {d: i for i, d in enumerate(days)}
    B = lit.XBars(df.time.values.astype(np.int64), df.open.values.astype(float), df.high.values.astype(float),
                  df.low.values.astype(float), df.close.values.astype(float), mod, np.array([dix[x] for x in sday]), 60)
    return B, et, dix


def five(B):
    """5m bars built from 1m bars (bar open times on the 5-minute grid)."""
    g = B.t // 300 * 300
    st = np.r_[0, np.flatnonzero(np.diff(g)) + 1]
    en = np.r_[st[1:], B.n]
    return lit.XBars(g[st], B.o[st], np.maximum.reduceat(B.h, st), np.minimum.reduceat(B.l, st), B.c[en - 1], B.mod[st] // 5 * 5,
                     B.day[st], 300)


def today(X):
    import pandas as pd
    B, et, dix = today_bars()
    BX = Bx(B)
    d = TODAY["dir"]
    ts = lambda s: int(pd.Timestamp(s, tz="America/New_York").timestamp())
    fill = int(np.searchsorted(B.t, ts(TODAY["entry_et"])))
    entry, stop, tg = TODAY["entry"] * d, TODAY["stop"] * d, TODAY["target"] * d
    if X.get("tight"):
        TB = BX if int(X["tight"].get("tf", 1)) == 1 else Bx(five(B))
        ns = _tight(TB, d, entry, stop, int(B.t[fill]), ts(TODAY["ext_et"]), 8.0)
        if ns is not None:
            stop = ns
            if X["tight"].get("tgt") == "cap8":
                tg = min(tg, entry + LIVE["max_rr"] * (entry - stop))
    risk = entry - stop
    r = manage(X, BX, fill, d, entry, stop, tg, int(B.day[fill]), risk, BX5=Bx(five(B)))
    kind, pts, worst, mfe, kx = r
    q_live = TODAY["qty"]
    # the live order risked 5 micros on 42.5 pts (two_week sizing); a tighter stop at the same $ risk buys more micros
    q = max(1, min(40, int(q_live * (42.5 + 0.25) / (risk + 0.25))))
    usd = pts * PV * q - 1.90 * q
    return {"exit": kind, "exit_px": round((entry + pts) * d, 2), "exit_et": str(et.iloc[kx])[:16], "pts": round(pts, 2),
            "stop_px": round(stop * d, 2), "risk_pts": round(risk, 2), "qty": q, "usd": round(usd), "mfe_r": round(mfe, 2)}


# ================================================================================================ variants
def variants():
    V = collections.OrderedDict()
    V["live"] = {}
    # idea 1: profit-protect on a violent reversal
    for k in (0.5, 0.75, 0.9):
        for act in ("exit", "be", "be0"):
            for m in (1.5, 2.0, 3.0):
                V[f"rev_bar_k{k}_m{m}_{act}"] = {"rev": {"k": k, "trig": "bar", "m": m, "act": act}}
            for m in (2.0, 3.0):
                V[f"rev_run2_k{k}_m{m}_{act}"] = {"rev": {"k": k, "trig": "run2", "m": m, "act": act}}
            for m in (2.5, 3.5):
                V[f"rev_run3_k{k}_m{m}_{act}"] = {"rev": {"k": k, "trig": "run3", "m": m, "act": act}}
            for g in (0.5, 0.75):
                V[f"rev_retr_k{k}_g{g}_{act}"] = {"rev": {"k": k, "trig": "retr", "g": g, "act": act}}
    # idea 2: trailing after MFE >= k R, near-1R breakeven
    for k in (0.5, 0.75, 0.9, 1.0):
        for tf in (1, 5):
            for lock in (False, True):
                V[f"trail{tf}m_k{k}{'_lock' if lock else ''}"] = {"trail": {"k": k, "tf": tf, "lock": lock}}
    for b in (0.75, 0.9):
        V[f"be_{b}R"] = {"be_r": b}
    # idea 3: stop at the first highs
    for tf in (1, 5):
        for tg in ("same", "cap8"):
            V[f"tight{tf}m_{tg}"] = {"tight": {"tf": tf, "tgt": tg}}
    return V


def check():
    c = cx()
    U = trades({})
    bad = [(u["day"], u["exit"], u["live_exit"], u["pts"], u["live_pts"]) for u in U
           if u["exit"] != u["live_exit"] or abs(u["pts"] - u["live_pts"]) > 0.01]
    L = lit_size(U)
    badq = [(l["day"], l["qty"], t["qty"]) for l, t in zip(L, sorted(c["T"], key=lambda t: t["entry_t"])) if l["qty"] != t["qty"]]
    n26 = sum(1 for u in U if u["day"] >= "2026")
    print(f"live trades {len(U)} (2026 {n26}) | exit/points mismatches {len(bad)} | size mismatches {len(badq)}")
    for b in bad[:8]:
        print("  diff", b)
    for b in badq[:8]:
        print("  qty", b)
    print("2026 net", round(sum(l["pnl"] for l in L if l["day"] >= "2026")), "2021-25 net", round(sum(l["pnl"] for l in L if l["day"] < "2026")))
    print("today live replay:", today({}))
    return not bad and not badq


def grid(names=None):
    res = json.load(open(OUT)) if os.path.exists(OUT) else {}
    V = variants()
    base_o, _, base_L = evaluate({})
    res["live"] = base_o
    print(line("live", base_o), flush=True)
    for nm, X in V.items():
        if nm == "live" or (names and nm not in names) or (nm in res and not names):
            continue
        o, U, L = evaluate(X, base_L)
        o["today"] = today(X)
        res[nm] = o
        print(line(nm, o), "| today", o["today"]["exit"], o["today"]["usd"], flush=True)
        json.dump(res, open(OUT, "w"), indent=1, default=str)
    res["live"]["today"] = today({})
    json.dump(res, open(OUT, "w"), indent=1, default=str)
    return res


SAVE = [   # run id, variant, family, status
    ("lit_rev_base", "live", "management", "info"),
    ("lit_rev_bar_k09_m2_exit", "rev_bar_k0.9_m2.0_exit", "management", "rejected"),
    ("lit_rev_bar_k05_m3_exit", "rev_bar_k0.5_m3.0_exit", "management", "rejected"),
    ("lit_rev_run2_k075_m2_be", "rev_run2_k0.75_m2.0_be", "management", "rejected"),
    ("lit_rev_run2_k09_m2_be", "rev_run2_k0.9_m2.0_be", "management", "rejected"),
    ("lit_rev_retr_k09_g05_exit", "rev_retr_k0.9_g0.5_exit", "management", "rejected"),
    ("lit_rev_retr_k075_g075_be", "rev_retr_k0.75_g0.75_be", "management", "rejected"),
    ("lit_rev_trail1m_k09", "trail1m_k0.9", "management", "rejected"),
    ("lit_rev_trail5m_k09", "trail5m_k0.9", "management", "rejected"),
    ("lit_rev_be09", "be_0.9R", "management", "rejected"),
    ("lit_rev_be075", "be_0.75R", "management", "rejected"),
    ("lit_rev_tight1m_same", "tight1m_same", "stops", "rejected"),
    ("lit_rev_tight5m_cap8", "tight5m_cap8", "stops", "rejected"),
]


def save():
    res = json.load(open(OUT))
    V = variants()
    for rid, nm, fam, st in SAVE:
        o = res[nm]
        U = trades(V[nm]); L = lit_size(U)
        S = rl.score(L, F.SESS)
        h = lambda s: (f"PF {o['lit'][s]['pf']} net {o['lit'][s]['net']:+,} (${o['lit'][s]['per_month']:,}/mo) DD {o['lit'][s]['dd']:,} "
                       f"2w {o['lit'][s]['p10']}/{o['lit'][s]['f10']}")
        e = lambda s: (f"PF {o['eval'][s]['pf']} net {o['eval'][s]['net']:+,} 2w {o['eval'][s]['p10']}/{o['eval'][s]['f10']} "
                       f"(MC {o['eval'][s]['mc']['p10']}/{o['eval'][s]['mc']['f10']}) dec10 {o['eval'][s]['dec10']} med {o['eval'][s]['pass_med']}")
        ver = (f"LIT size: H1 {h('H1')}; H2 {h('H2')}; 2021-25 ref {h('2021-25')}. Eval path (two_week): H1 {e('H1')}; H2 {e('H2')}. "
               f"2026-10-28 live trade: {o['today']['exit']} ${o['today']['usd']:+,} (live -$437).")
        rl.save(rid, f"LIT reversal exit: {nm}", fam,
                "Owner 2026-10-28 after the first live LIT trade (0.95R then full stop): profit-protect on a violent reversal, "
                "trail after MFE >= kR, near-1R BE, stop at the first highs",
                params={**LIVE, "x_rev": V[nm]}, trades=L, scored=S, status=st, verdict=ver,
                notes="tools/lit_rev_exit.py: live LIT trades (tools/lit_final.run, == lit_live), post-fill re-managed on true 1m bars "
                      "(2026; 5m in 2021-25), LIT size rule; eval columns in the verdict = live two_week sizing.",
                writeup="lit-reversal-exit", tags=["lit", "lit_rev_exit"])
        print("saved", rid)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        check()
    elif cmd == "grid":
        grid(sys.argv[2:] or None)
    elif cmd == "save":
        save()
