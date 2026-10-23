"""High-probability mean reversion at EXHAUSTION (owner 2026-10-23: "a strategy that trades 2+ times a week, high-quality
setups, with high probability and high profit").

Four setup families, all fading a move that is already stretched, with a CLOSE target (VWAP / a midpoint / 1-1.5R) so the hit
rate can be high, and a structural stop 1 tick beyond the exhaustion extreme:
  ex  stretched day: the trading day's range (from 18:00) is already >= rr x the 14-day mean daily range, price takes out
      the day's high (low) set >= 30 min earlier, then a 5m rejection close (reclaim / CISD / displacement) -> back toward
      the session VWAP, the RTH VWAP or the day's midpoint
  bx  both sides of a box swept: the overnight (18:00-09:30), London (02:00-05:00) or Asia (20:00-00:00) range has had its
      high AND its low traded through, the second sweep is rejected back inside -> to the box middle (sides=1 = the plain
      one-side reclaim of allday.md, kept as the control)
  vx  stretched from VWAP into a higher-timeframe pool: price >= k x the 5m ATR from the session VWAP sweeps an untaken
      PDH/PDL, PWH/PWL or PMH/PML, then a rejection close back through the level -> to VWAP / 1-1.5R
  of  failed opening-range breakout 10:00-11:30: a 5m close (or a wick) beyond the 09:30-09:45 / 09:30-10:00 range, then
      within N bars a close back inside -> to the range middle / the other side / VWAP
  every family can add the exhaustion overlay (day range >= 1.0 x ADR) - the new angle of this study.

Execution (no look-ahead, costs in): a signal is known at a 5m bar close (all features use bars <= the signal bar, the
14-day mean range uses prior days only, VWAP includes the signal bar); market entry at the next 5m open + 1 tick; stop 1
tick beyond the extreme from the sweep to the signal bar (6-80 pts); target = a limit filled on a trade-through; stop and
target in one bar = stop; stop / time exits - 1 tick; breakeven (when on) = entry + 1.25 pts once +be R was reached (from
the next bar). True 1m bars on 2026 days with full 1m coverage, 5m before. Time exit 2 h after the entry or 15:55 ET.
One trade a day per setup. $1.90 a micro round trip. Money at $500 risk a trade: floor(500 / (stop x $2)) micros, max 50
(eval views use the plan's own sizing: tools/second_account_b.py and tools/second_mix.py executors via tools/allday.py).

    python -X utf8 tools/hq_revert.py grid      # every variant -> research/hq/grid.json (stats per span)
    python -X utf8 tools/hq_revert.py pick      # H1 picks + pre-2025 re-pick, checks, placebo, chance -> research/hq/picks.json
    python -X utf8 tools/hq_revert.py evals     # 25K alone / next to LIT on the 50K, LIT correlation -> research/hq/evals.json
    python -X utf8 tools/hq_revert.py audit     # look-ahead re-derivation on data cut at the signal close
    python -X utf8 tools/hq_revert.py save      # rl.save runs hq_rev_* + research/hq/<pick>.json (common trade format)
Paper only. Edits no engine file and no live_model*.json / second_model.json.
"""
from __future__ import annotations

import collections
import datetime as dt
import hashlib
import itertools
import json
import os
import pickle
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from tools import allday as A  # noqa: E402

OUT = os.path.join(ROOT, "research", "hq")
CACHE = os.path.join(ROOT, "research", "runs", "_cache")
TICK, PV, COMM, RISK_USD, MAXQ = 0.25, 2.0, 1.90, 500.0, 50
BE_OFF = 1.25
SPANS = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-12-31"), "2025": ("2025-01-01", "2025-12-31"),
         "2021-24": ("2021-01-01", "2024-12-31")}
CHECK = ("H1", "H2", "2025", "2021-24")
NMAX = 6          # bars a rejection may take after the sweep starts (ORF: up to 12)
AGE = 6           # the day's extreme must be >= 6 bars (30 min) old to count as swept (family ex)
WINDOWS = {"lon": (120, 480), "ny": (480, 925), "am": (570, 720), "all": (120, 925)}


def _dump(obj, path, **kw):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, **kw)
    os.replace(tmp, path)


# ================================================================================================ data + features
_X = {}


def ctx():
    """allday.data() (lit.Market, 1m bars, sessions, the 14-day mean daily range, 18:00 VWAP) + the RTH VWAP (from 09:30)
    and the running day high / low (through each bar, inclusive)."""
    if "M" in _X:
        return _X
    D = A.data()
    M = D["M"]
    tp = (M.h + M.l + M.c) / 3.0
    v = np.maximum(M.v, 1.0)
    rv = np.full(M.n, np.nan)
    dh = np.zeros(M.n)
    dl = np.zeros(M.n)
    for d, s, e in M.days:
        dh[s:e] = np.maximum.accumulate(M.h[s:e])
        dl[s:e] = np.minimum.accumulate(M.l[s:e])
        ii = np.flatnonzero((M.mod[s:e] >= 570) & (M.mod[s:e] < 1080))
        if len(ii):
            a = s + ii[0]
            z = s + ii[-1] + 1
            rv[a:z] = np.cumsum(tp[a:z] * v[a:z]) / np.cumsum(v[a:z])
    _X.update(D=D, M=M, rv=rv, dh=dh, dl=dl, vw=D["vwap"], adr=D["adr"])
    return _X


# --------------------------------------------------------------------------------------------- rejection confirm
def confirms(M, j, lv, dr, end, nmax=NMAX):
    """After a sweep that starts at bar j through level lv (dr = trade direction: -1 short after a high was taken, +1 long
    after a low was taken), the first bar m in j..j+nmax-1 (m < end, same day) of each rejection type:
      rc     a close back inside the level
      cisd   a close back inside that is also beyond the open of the candle run into the extreme (change in state of delivery)
      d05 / d08  a close back inside with a body >= 0.5 / 0.8 x the 5m ATR (displacement rejection)
    Returns {type: (m, extreme through m)}. Only bars <= m are read for the m returned."""
    out = {}
    ext, ext_i = (-np.inf, j) if dr == -1 else (np.inf, j)
    for m in range(j, min(end, j + nmax)):
        if dr == -1:
            if M.h[m] > ext:
                ext, ext_i = float(M.h[m]), m
            inside = M.c[m] < lv
        else:
            if M.l[m] < ext:
                ext, ext_i = float(M.l[m]), m
            inside = M.c[m] > lv
        if not inside:
            continue
        if "rc" not in out:
            out["rc"] = (m, ext)
        body = (M.c[m] - M.o[m]) * dr
        at = float(M.atr[m])
        if body >= 0.5 * at and "d05" not in out:
            out["d05"] = (m, ext)
        if body >= 0.8 * at and "d08" not in out:
            out["d08"] = (m, ext)
        if "cisd" not in out:
            # the run of candles into the extreme: same-colour (with the sweep) candles ending at ext_i
            q = ext_i
            if dr == -1:
                while q - 1 >= 0 and M.day_of[q - 1] == M.day_of[ext_i] and M.c[q - 1] > M.o[q - 1]:
                    q -= 1
                if M.c[ext_i] <= M.o[ext_i] and q == ext_i:
                    ref = float(M.o[ext_i])
                else:
                    ref = float(M.o[q])
                if M.c[m] < ref:
                    out["cisd"] = (m, ext)
            else:
                while q - 1 >= 0 and M.day_of[q - 1] == M.day_of[ext_i] and M.c[q - 1] < M.o[q - 1]:
                    q -= 1
                if M.c[ext_i] >= M.o[ext_i] and q == ext_i:
                    ref = float(M.o[ext_i])
                else:
                    ref = float(M.o[q])
                if M.c[m] > ref:
                    out["cisd"] = (m, ext)
    return out


def _ev(X, k, j, m, dr, ext, conf, fam, extra):
    """One event (a signal at bar m's close): stop 1 tick beyond the extreme, the levels known at m."""
    M = X["M"]
    adr = X["adr"][k]
    rr = (X["dh"][m] - X["dl"][m]) / adr if adr == adr and adr > 0 else 0.0
    lv = {"vwap": float(X["vw"][m]), "mid": float((X["dh"][m] + X["dl"][m]) / 2.0)}
    if X["rv"][m] == X["rv"][m]:
        lv["rvwap"] = float(X["rv"][m])
    lv.update(extra.pop("lv", {}))
    return {"k": k, "day": str(M.days[k][0]), "j": j, "i": m, "mod": int(M.mod[m]), "dir": dr, "stop": float(ext - dr * TICK),
            "conf": conf, "nb": m - j + 1, "rr": round(float(rr), 3), "depth": 0.0, "lv": lv, "fam": fam, **extra}


# --------------------------------------------------------------------------------------------- family generators
def gen_ex(X, days=None):
    """Stretched day + sweep of the day's extreme (set >= AGE bars earlier) + rejection. All events (any rr; filtered later)."""
    M = X["M"]
    ev = []
    for k, (d, s, e) in enumerate(M.days):
        if days is not None and k not in days:
            continue
        if str(d) not in X["D"]["sset"]:
            continue
        hi, hi_i, lo, lo_i = -np.inf, s, np.inf, s
        for j in range(s, e):
            md = int(M.mod[j])
            ok = (md >= 100 and md < 925) and j > s + 6
            if ok and M.h[j] > hi and j - hi_i >= AGE:
                for cf, (m, ext) in confirms(M, j, hi, -1, e).items():
                    if 120 <= M.mod[m] < 925:
                        x = _ev(X, k, j, m, -1, ext, cf, "ex", {})
                        x["depth"] = round((ext - hi) / float(M.atr[m]), 3)
                        ev.append(x)
            if ok and M.l[j] < lo and j - lo_i >= AGE:
                for cf, (m, ext) in confirms(M, j, lo, 1, e).items():
                    if 120 <= M.mod[m] < 925:
                        x = _ev(X, k, j, m, 1, ext, cf, "ex", {})
                        x["depth"] = round((lo - ext) / float(M.atr[m]), 3)
                        ev.append(x)
            if M.h[j] > hi:
                hi, hi_i = float(M.h[j]), j
            if M.l[j] < lo:
                lo, lo_i = float(M.l[j]), j
    return ev


BOXES = {"on": ((1080, 570), 570), "lon": ((120, 300), 300), "asia": ((1200, 1440), 0)}


def _box_bars(M, s, e, a, z):
    md = M.mod[s:e]
    if a < z:
        ii = np.flatnonzero((md >= a) & (md < z))
    else:                                            # wraps midnight (18:00 -> 09:30)
        rr = (md - 1080) % 1440
        ii = np.flatnonzero(rr < (z - 1080) % 1440)
    return ii


def gen_bx(X, days=None):
    """Box (overnight / London / Asia) swept on one or both sides, then a rejection back inside -> the box middle."""
    M = X["M"]
    ev = []
    for k, (d, s, e) in enumerate(M.days):
        if days is not None and k not in days:
            continue
        if str(d) not in X["D"]["sset"]:
            continue
        for bn, ((a, z), start) in BOXES.items():
            ii = _box_bars(M, s, e, a, z)
            if len(ii) < 6:
                continue
            b0, b1 = s + ii[0], s + ii[-1] + 1
            bh, bl = float(M.h[b0:b1].max()), float(M.l[b0:b1].min())
            mid = (bh + bl) / 2.0
            if bh - bl < 4.0:
                continue
            hi_sw = lo_sw = None                     # first bar each side was traded through (after the box)
            for j in range(b1, e):
                md = int(M.mod[j])
                if md >= 925 and md < 1080:
                    break
                for side, dr in (("hi", -1), ("lo", 1)):
                    lv = bh if dr == -1 else bl
                    through = M.h[j] > lv if dr == -1 else M.l[j] < lv
                    prev_in = (M.c[j - 1] <= lv) if dr == -1 else (M.c[j - 1] >= lv)
                    if not (through and prev_in):
                        continue
                    other = lo_sw if dr == -1 else hi_sw
                    sides = 2 if (other is not None and other < j) else 1
                    for cf, (m, ext) in confirms(M, j, lv, dr, e).items():
                        if not (int(M.mod[m]) < 925 or int(M.mod[m]) >= 1080):
                            continue
                        x = _ev(X, k, j, m, dr, ext, cf, "bx", {"box": bn, "sides": sides,
                                                                 "lv": {"bmid": mid, "opp": bl if dr == -1 else bh}})
                        x["depth"] = round(abs(ext - lv) / float(M.atr[m]), 3)
                        ev.append(x)
                if M.h[j] > bh and hi_sw is None:
                    hi_sw = j
                if M.l[j] < bl and lo_sw is None:
                    lo_sw = j
    return ev


POOLS = {"d": ("pdh", "pdl"), "w": ("pwh", "pwl"), "m": ("pmh", "pml")}


def gen_vx(X, days=None):
    """Stretched from the 18:00 VWAP into an untaken higher-timeframe pool, then a rejection back through it."""
    M = X["M"]
    ev = []
    for k, (d, s, e) in enumerate(M.days):
        if days is not None and k not in days:
            continue
        if str(d) not in X["D"]["sset"]:
            continue
        cx = M.ctx[k]
        lvls = []
        for pn, (hk, lk) in POOLS.items():
            if cx.get(hk) is not None:
                lvls.append((pn, float(cx[hk]), -1))
                lvls.append((pn, float(cx[lk]), 1))
        for pn, lv, dr in lvls:
            for j in range(s + 1, e):
                md = int(M.mod[j])
                if md >= 925 and md < 1080:
                    break
                if dr == -1:
                    if X["dh"][j - 1] >= lv:          # taken earlier today: no longer an untaken pool
                        break
                    if M.h[j] <= lv:
                        continue
                else:
                    if X["dl"][j - 1] <= lv:
                        break
                    if M.l[j] >= lv:
                        continue
                for cf, (m, ext) in confirms(M, j, lv, dr, e).items():
                    if not (120 <= int(M.mod[m]) < 925):
                        continue
                    st = (ext - float(X["vw"][m])) * (-dr) / float(M.atr[m])
                    x = _ev(X, k, j, m, dr, ext, cf, "vx", {"pool": pn, "stretch": round(float(st), 3)})
                    x["depth"] = round(abs(ext - lv) / float(M.atr[m]), 3)
                    ev.append(x)
                break                                 # one sweep per pool per day (the first time it is taken)
    return ev


def gen_of(X, days=None):
    """Failed opening-range breakout: a close (or wick) beyond the 09:30 range, then a close back inside within N bars."""
    M = X["M"]
    ev = []
    for k, (d, s, e) in enumerate(M.days):
        if days is not None and k not in days:
            continue
        if str(d) not in X["D"]["sset"]:
            continue
        ii = np.flatnonzero(M.mod[s:e] == 570)
        if not len(ii):
            continue
        a = s + int(ii[0])
        for orm in (15, 30):
            nb = orm // 5
            if a + nb >= e or any(int(M.mod[a + q]) != 570 + 5 * q for q in range(nb)):
                continue
            oh, ol = float(M.h[a:a + nb].max()), float(M.l[a:a + nb].min())
            w = oh - ol
            if w < 4.0:
                continue
            for bo in ("close", "wick"):
                done = {1: False, -1: False}
                for j in range(a + nb, e):
                    md = int(M.mod[j])
                    if md >= 690:
                        break
                    for dr in (-1, 1):                # dr = the fade direction (short after an upside breakout)
                        if done[dr]:
                            continue
                        lv = oh if dr == -1 else ol
                        if bo == "close":
                            brk = M.c[j] > lv if dr == -1 else M.c[j] < lv
                        else:
                            brk = M.h[j] > lv + TICK if dr == -1 else M.l[j] < lv - TICK
                        if not brk:
                            continue
                        done[dr] = True
                        for cf, (m, ext) in confirms(M, j, lv, dr, e, nmax=12).items():
                            if not (600 <= int(M.mod[m]) < 690) or cf not in ("rc", "cisd"):
                                continue
                            x = _ev(X, k, j, m, dr, ext, cf, "of", {"orm": orm, "bo": bo, "orw": w,
                                                                     "ext_w": round(abs(ext - lv) / w, 3),
                                                                     "lv": {"omid": (oh + ol) / 2.0, "opp": ol if dr == -1 else oh}})
                            x["depth"] = round(abs(ext - lv) / float(M.atr[m]), 3)
                            ev.append(x)
    return ev


GENS = {"ex": gen_ex, "bx": gen_bx, "vx": gen_vx, "of": gen_of}


# ================================================================================================ grids (setup filters)
SETUP = {
    "ex": {"win": ("lon", "ny", "am", "all"), "rr": (0.8, 1.0, 1.2, 1.5), "depth": (0.0, 0.25, 0.5), "conf": ("rc", "cisd", "d08"),
           "nb": (3, 6)},
    "bx": {"box": ("on", "lon", "asia"), "sides": (1, 2), "depth": (0.0, 0.25), "conf": ("rc", "cisd", "d08"), "nb": (3, 6),
           "end": (720, 925), "exh": (0.0, 1.0)},
    "vx": {"pool": ("d", "w", "m", "dwm"), "k": (1.5, 2.0, 3.0, 4.0), "conf": ("rc", "cisd", "d05", "d08"), "nb": (3, 6),
           "win": ("lon", "ny", "all")},
    "of": {"orm": (15, 30), "bo": ("close", "wick"), "nb": (3, 6, 12), "ext": (0.0, 0.25), "exh": (0.0, 1.0), "conf": ("rc", "cisd")},
}
TGTS = {"ex": ("L:vwap", "LX:vwap", "L:mid", "LX:mid", "L:rvwap", "LX:rvwap", "R1", "R1.5"),
        "bx": ("L:bmid", "LX:bmid", "L:vwap", "LX:vwap", "R1", "R1.5"),
        "vx": ("L:vwap", "LX:vwap", "L:mid", "R1", "R1.5"),
        "of": ("L:omid", "LX:omid", "L:opp", "LX:vwap", "R1", "R1.5")}
BES = (None, 0.75)
HOLDS = ("2h", "eod")
NUMERIC = {"rr", "depth", "nb", "k", "end", "exh", "ext", "orm", "sides"}


def match(fam, ev, p):
    """Does event ev pass setup parameters p?"""
    if ev["conf"] != p["conf"] or ev["nb"] > p["nb"]:
        return False
    if fam == "ex":
        a, z = WINDOWS[p["win"]]
        return a <= ev["mod"] < z and ev["rr"] >= p["rr"] and ev["depth"] >= p["depth"]
    if fam == "bx":
        if ev["box"] != p["box"] or ev["depth"] < p["depth"] or ev["rr"] < p["exh"]:
            return False
        if p["sides"] == 2 and ev["sides"] != 2:
            return False
        if p["sides"] == 1 and ev["sides"] != 1:
            return False
        md = ev["mod"]
        return (md < p["end"]) or md >= 1080
    if fam == "vx":
        a, z = WINDOWS[p["win"]]
        if not (a <= ev["mod"] < z) or ev["stretch"] < p["k"]:
            return False
        return p["pool"] == "dwm" or ev["pool"] == p["pool"]
    if fam == "of":
        return ev["orm"] == p["orm"] and ev["bo"] == p["bo"] and ev["ext_w"] >= p["ext"] and ev["rr"] >= p["exh"]
    raise ValueError(fam)


def setups(fam):
    g = SETUP[fam]
    for vals in itertools.product(*g.values()):
        yield dict(zip(g.keys(), vals))


def exits(fam):
    return list(itertools.product(TGTS[fam], BES, HOLDS))


def vkey(fam, p, ex):
    return fam + "|" + ",".join(f"{k}={v}" for k, v in p.items()) + "|" + f"{ex[0]},{ex[1]},{ex[2]}"


def parse(key):
    fam, ps, es = key.split("|")
    p = {}
    for kv in ps.split(","):
        k, v = kv.split("=")
        p[k] = type(SETUP[fam][k][0])(v) if not isinstance(SETUP[fam][k][0], str) else v
    t, be, h = es.split(",")
    return fam, p, (t, None if be == "None" else float(be), h)


# ================================================================================================ simulation
def tpath(X, k, i_entry, hold):
    M = X["M"]
    B1 = X["D"]["B1"]
    d, s, e = M.days[k]
    t0 = int(M.t[i_entry])
    tf = int(M.t[s]) + (A.rel(955) - A.rel(int(M.mod[s]))) * 60
    if hold == "2h":
        tf = min(tf, t0 + 7200)
    if k in X["D"]["full"]:
        a = int(np.searchsorted(B1.t, t0))
        z = int(np.searchsorted(B1.t, tf))
        if z > a and int(B1.t[a]) == t0:
            return B1.t[a:z], B1.o[a:z], B1.h[a:z], B1.l[a:z], B1.c[a:z], 60
    z = min(e, int(np.searchsorted(M.t, tf)))
    return M.t[i_entry:z], M.o[i_entry:z], M.h[i_entry:z], M.l[i_entry:z], M.c[i_entry:z], 300


def qty(risk):
    return max(0, min(MAXQ, int(RISK_USD / (risk * PV))))


def sim(X, ev, ex, _pc={}):
    """One event through one exit (tgt 'L:<lv>' = that level, skip if < 1R; 'LX:<lv>' = that level but at least 1R; 'R1' /
    'R1.5' = fixed R; level targets capped at 4R). Returns a trade (common format + pts / risk / r / rn) or None."""
    M = X["M"]
    tgt, be, hold = ex
    k, i, d = ev["k"], ev["i"], ev["dir"]
    if i + 1 >= M.n or M.day_of[i + 1] != k:
        return None
    pk = (k, i, hold)
    if pk not in _pc:
        if len(_pc) > 400000:
            _pc.clear()
        _pc[pk] = tpath(X, k, i + 1, hold)
    T, O, H, L, C, secs = _pc[pk]
    if len(T) == 0:
        return None
    if d == 1:
        o, h, l, cl = O, H, L, C
    else:
        o, h, l, cl = -O, -L, -H, -C
    e = float(o[0]) + TICK
    sp = ev["stop"] * d
    risk = e - sp
    if not (6.0 <= risk <= 80.0):
        return None
    if tgt.startswith("L"):
        mode, lvn = tgt.split(":")
        lvp = ev["lv"].get(lvn)
        if lvp is None:
            return None
        tg = lvp * d
        if mode == "L" and tg - e < 1.0 * risk:
            return None
        tg = max(tg, e + 1.0 * risk) if mode == "LX" else tg
        tg = min(tg, e + 4.0 * risk)
    else:
        tg = e + float(tgt[1:]) * risk
    n = len(l)
    s0 = A._first(l <= sp)
    tt = A._first(h >= tg + TICK)
    b = A._first(h >= e + be * risk) if be else n
    bes = e + BE_OFF
    s_pre = s0 if s0 <= b else n
    s_post = A._first(l <= bes, b + 1) if (b < n and s_pre == n) else n
    si = s_pre if s_pre < n else s_post
    if si <= tt and si < n:
        j = si
        lv = sp if si == s_pre else bes
        px, kind = min(float(o[j]), lv) - TICK, ("STOP" if si == s_pre else "BE")
    elif tt < n:
        j = tt
        px, kind = max(float(o[j]), tg), "TARGET"
    else:
        j = n - 1
        px, kind = float(cl[j]) - TICK, "TIME"
    pts = px - e
    w1 = float(min(0.0, l[:j + 1].min() - e))
    if kind != "TIME":
        w1 = max(w1, -(risk + TICK))
    q = qty(risk)
    if q <= 0:
        return None
    pnl = (pts * PV - COMM) * q
    return {"day": ev["day"], "entry_t": int(T[0]), "exit_t": int(T[j]) + secs, "dir": d, "entry": round(e * d, 2),
            "stop": round(sp * d, 2), "target": round(tg * d, 2), "exit": round(px * d, 2), "exit_kind": kind,
            "r": round(pts / risk, 3), "rn": round(pnl / (risk * PV * q), 3), "qty": q, "pnl_usd": round(pnl, 2),
            "risk": round(risk, 2), "pts": round(pts, 4), "w1": round(w1, 4), "tgt_r": round((tg - e) / risk, 3),
            "setup": ev.get("label", ev["fam"]), "sig_i": int(i)}


# ================================================================================================ stats
_SESS = {}


def sessions(span):
    if span not in _SESS:
        a, z = SPANS[span]
        _SESS[span] = [d for d in ctx()["D"]["sess"] if a <= d <= z]
    return _SESS[span]


def week_of(day):
    y, w, _ = dt.date.fromisoformat(day).isocalendar()
    return y * 100 + w


def stats(T, span):
    a, z = SPANS[span]
    ss = sessions(span)
    TT = [t for t in T if a <= t["day"] <= z]
    nw = max(1.0, len(ss) / 5.0)
    if not TT:
        return {"n": 0, "tpw": 0.0, "net": 0, "pf": None, "win": None, "w05": None, "w1": None, "be": None, "avgw": None,
                "exp_r": None, "exp_usd": None, "per_month": 0, "dd": 0, "wk2": 0.0}
    p = np.array([t["pnl_usd"] for t in TT])
    r = np.array([t["r"] for t in TT])
    rn = np.array([t["rn"] for t in TT])
    gl = -p[p < 0].sum()
    eq = np.cumsum(p)
    dd = float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min())
    wk = collections.Counter(week_of(t["day"]) for t in TT)
    weeks = sorted({week_of(d) for d in ss})
    W = r >= 0.5
    return {"n": len(TT), "tpw": round(len(TT) / nw, 2), "win": round(100.0 * float((p > 0).mean()), 1),
            "w05": round(100.0 * float(W.mean()), 1), "w1": round(100.0 * float((r >= 0.99).mean()), 1),
            "be": round(100.0 * float(np.mean([t["exit_kind"] == "BE" for t in TT])), 1),
            "avgw": round(float(r[W].mean()), 2) if W.any() else None,
            "exp_r": round(float(rn.mean()), 3), "exp_usd": round(float(p.mean()), 1),
            "pf": round(float(p[p > 0].sum() / gl), 2) if gl > 0 else 99.0, "net": round(float(p.sum())),
            "per_month": round(float(p.sum()) / max(1.0, len(ss) / 21.0)), "dd": round(dd),
            "wk2": round(100.0 * sum(1 for w in weeks if wk.get(w, 0) >= 2) / max(1, len(weeks)), 1),
            "sumr": round(float(rn.sum()), 2)}


def drop_best(T, span, n=5):
    a, z = SPANS[span]
    TT = sorted([t for t in T if a <= t["day"] <= z], key=lambda t: -t["pnl_usd"])
    return round(sum(t["pnl_usd"] for t in TT[n:]))


def months(T, a="2026-01-01", z="2026-12-31"):
    m = collections.defaultdict(lambda: [0, 0.0, 0])
    for t in T:
        if a <= t["day"] <= z:
            x = m[t["day"][:7]]
            x[0] += 1; x[1] += t["pnl_usd"]; x[2] += t["r"] >= 0.5
    return {k: {"n": v[0], "net": round(v[1]), "w05": v[2]} for k, v in sorted(m.items())}


def years(T):
    m = collections.defaultdict(float)
    for t in T:
        m[t["day"][:4]] += t["pnl_usd"]
    return {k: round(v) for k, v in sorted(m.items())}


# ================================================================================================ 1. grid
EV_PKL = os.path.join(CACHE, "hq_events.pkl")


def events():
    if "ev" in _X:
        return _X["ev"]
    if os.path.exists(EV_PKL):
        _X["ev"] = pickle.load(open(EV_PKL, "rb"))
        return _X["ev"]
    X = ctx()
    E = {}
    for fam, g in GENS.items():
        t0 = time.time()
        E[fam] = g(X)
        print(f"  {fam}: {len(E[fam])} events {time.time() - t0:.0f}s", flush=True)
    os.makedirs(CACHE, exist_ok=True)
    pickle.dump(E, open(EV_PKL, "wb"))
    _X["ev"] = E
    return E


def trades_of(key, label=None):
    """The trades of one variant: the first matching event of each trading day, through its exit."""
    fam, p, ex = parse(key)
    X = ctx()
    E = events()[fam]
    first = {}
    for ev in E:
        if match(fam, ev, p):
            cur = first.get(ev["k"])
            if cur is None or ev["i"] < cur["i"]:
                first[ev["k"]] = ev
    out = []
    for k in sorted(first):
        ev = dict(first[k])
        ev["label"] = label or key
        t = sim(X, ev, ex)
        if t is not None:
            out.append(t)
    return out


def _fam_job(fam):
    X = ctx()
    E = events()[fam]
    EX = exits(fam)
    res = {}
    cache = {}
    t0 = time.time()
    for p in setups(fam):
        first = {}
        for ix, ev in enumerate(E):
            if match(fam, ev, p):
                cur = first.get(ev["k"])
                if cur is None or ev["i"] < E[cur]["i"]:
                    first[ev["k"]] = ix
        sel = [first[k] for k in sorted(first)]
        for ex in EX:
            T = []
            for ix in sel:
                ck = (ix, ex)
                if ck not in cache:
                    cache[ck] = sim(X, E[ix], ex)
                if cache[ck] is not None:
                    T.append(cache[ck])
            res[vkey(fam, p, ex)] = {s: stats(T, s) for s in CHECK}
    print(f"  {fam}: {len(res)} variants, {len(cache)} sims, {time.time() - t0:.0f}s", flush=True)
    return res


def cmd_grid(procs=4):
    events()
    from multiprocessing import Pool
    with Pool(procs) as pool:
        R = pool.map(_fam_job, list(GENS))
    S = {}
    for r in R:
        S.update(r)
    _dump(S, os.path.join(CACHE, "hq_grid.json"), separators=(",", ":"))
    print(len(S), "variants", flush=True)
    return S


def grid():
    if "grid" not in _X:
        _X["grid"] = json.load(open(os.path.join(CACHE, "hq_grid.json")))
    return _X["grid"]


# ================================================================================================ 2. picks
def neighbours(key):
    """One step in one setup parameter (numeric: the next value; categorical: any other value) or one exit setting."""
    fam, p, ex = parse(key)
    out = []
    for k, vals in SETUP[fam].items():
        ix = vals.index(p[k])
        cand = [vals[j] for j in (ix - 1, ix + 1) if 0 <= j < len(vals)] if k in NUMERIC else [v for v in vals if v != p[k]]
        for v in cand:
            out.append(vkey(fam, {**p, k: v}, ex))
    t, be, h = ex
    tl = TGTS[fam]
    for tt in tl:
        if tt != t and (tt.split(":")[-1] == t.split(":")[-1] or tt.startswith("R") == t.startswith("R")):
            out.append(vkey(fam, p, (tt, be, h)))
    for b2 in BES:
        if b2 != be:
            out.append(vkey(fam, p, (t, b2, h)))
    for h2 in HOLDS:
        if h2 != h:
            out.append(vkey(fam, p, (t, be, h2)))
    return out


def gate(s, min_n, w05=55.0, pf=1.3, avgw=1.0):
    return (s["n"] >= min_n and s["w05"] is not None and s["w05"] >= w05 and (s["avgw"] or 0) >= avgw and (s["pf"] or 0) >= pf
            and s["net"] > 0)


def plateau(S, key, span):
    nb = [S[n][span]["net"] for n in neighbours(key) if n in S]
    return 0.5 * S[key][span]["net"] + 0.5 * (float(np.median(nb)) if nb else 0.0), nb


def pick(S, on="H1", min_n=20, w05=55.0, pf=1.3):
    """Per family: the eligible variant (on span `on`) with the best plateau score; plus its shortlist."""
    out = {}
    for fam in GENS:
        el = [k for k in S if k.startswith(fam + "|") and gate(S[k][on], min_n, w05, pf)]
        sc = []
        for k in el:
            v, nb = plateau(S, k, on)
            sc.append((v, k, nb))
        sc.sort(reverse=True)
        if not sc:
            out[fam] = None
            continue
        v, k, nb = sc[0]
        out[fam] = {"key": k, "score": round(v), "nb_on_pos": f"{sum(1 for x in nb if x > 0)}/{len(nb)}",
                    "eligible": len(el), "shortlist": [x[1] for x in sc[:10]]}
    return out


def placebo(T, span, fam_win, n_draw=300, seed=11):
    """Random entries in the same span on the same days' windows: the same count, long/short mix, stop sizes, target R
    and exit rule (breakeven, hold). Share of random draws with net >= the pick (and with w05 >= the pick's)."""
    X = ctx()
    M = X["M"]
    a_, z_ = SPANS[span]
    TT = [t for t in T if a_ <= t["day"] <= z_]
    if len(TT) < 5:
        return None
    s = stats(T, span)
    rng = np.random.default_rng(seed)
    days = sessions(span)
    lo, hi = fam_win
    risks = np.array([t["risk"] for t in TT])
    rr = np.array([t["tgt_r"] for t in TT])
    pl = float(np.mean([t["dir"] == 1 for t in TT]))
    be, hold = TT[0]["_be"], TT[0]["_hold"]
    nets, w05s = [], []
    for _ in range(n_draw):
        P = []
        for _j in range(len(TT)):
            for _try in range(30):
                d = days[int(rng.integers(len(days)))]
                k = X["D"]["dmap"][d]
                _, s0, e0 = M.days[k]
                md = M.mod[s0:e0]
                ii = np.flatnonzero((md >= lo) & (md < hi))
                if len(ii) < 2:
                    continue
                m = s0 + int(ii[int(rng.integers(len(ii) - 1))])
                dr = 1 if rng.random() < pl else -1
                q = int(rng.integers(len(TT)))
                e0p = float(M.o[m + 1]) + TICK * dr
                ev = {"k": k, "day": d, "i": m, "dir": dr, "stop": e0p - dr * float(risks[q]), "lv": {}, "fam": "placebo"}
                t = sim(X, ev, (f"R{float(rr[q])}", be, hold))
                if t is not None:
                    P.append(t)
                    break
        p = np.array([t["pnl_usd"] for t in P])
        nets.append(float(p.sum()))
        w05s.append(100.0 * float(np.mean([t["r"] >= 0.5 for t in P])))
    nets, w05s = np.array(nets), np.array(w05s)
    return {"span": span, "n": len(TT), "draws": n_draw, "p_net": round(float((nets >= s["net"]).mean()), 3),
            "p_w05": round(float((w05s >= s["w05"]).mean()), 3), "rand_net_p50": round(float(np.median(nets))),
            "rand_net_p90": round(float(np.percentile(nets, 90))), "rand_w05_p50": round(float(np.median(w05s)), 1)}


def fam_window(key):
    fam, p, ex = parse(key)
    if fam in ("ex", "vx"):
        return WINDOWS[p["win"]]
    if fam == "of":
        return (600, 690)
    return {"on": (570, p["end"]), "lon": (300, p["end"]), "asia": (0, p["end"])}[p["box"]]


def with_ex(T, key):
    _, _, ex = parse(key)
    return [{**t, "_be": ex[1], "_hold": ex[2]} for t in T]


def chance(S, n_strat=200, seed=5):
    """Chance level: random-entry strategies (random bar in a random variant's window, random side, that variant's stop
    sizes / target R / exit rule, the same days) - how often they pass the win gate and are positive in all 4 spans."""
    X = ctx()
    M = X["M"]
    rng = np.random.default_rng(seed)
    keys = [k for k in S if S[k]["H1"]["n"] >= 20]
    pos4 = gate4 = n = 0
    for _ in range(n_strat):
        k = keys[int(rng.integers(len(keys)))]
        TT = trades_of(k)
        if len(TT) < 40:
            continue
        lo, hi = fam_window(k)
        _, _, ex = parse(k)
        R = []
        for t in TT:
            kk = X["D"]["dmap"][t["day"]]
            _, s0, e0 = M.days[kk]
            md = M.mod[s0:e0]
            ii = np.flatnonzero((md >= lo) & (md < hi))
            if len(ii) < 2:
                continue
            m = s0 + int(ii[int(rng.integers(len(ii) - 1))])
            dr = 1 if rng.random() < 0.5 else -1
            e0p = float(M.o[m + 1]) + TICK * dr
            ev = {"k": kk, "day": t["day"], "i": m, "dir": dr, "stop": e0p - dr * t["risk"], "lv": {}, "fam": "chance"}
            x = sim(X, ev, (f"R{t['tgt_r']}", ex[1], ex[2]))
            if x:
                R.append(x)
        n += 1
        ss = [stats(R, s) for s in CHECK]
        pos4 += all(s["net"] > 0 for s in ss)
        gate4 += all(s["n"] >= 5 and (s["w05"] or 0) >= 55 and (s["avgw"] or 0) >= 1.0 and s["net"] > 0 for s in ss)
    return {"strategies": n, "positive_all_4": pos4, "rate_pos4": round(pos4 / max(1, n), 4), "gate_all_4": gate4,
            "rate_gate4": round(gate4 / max(1, n), 4)}


def summary_counts(S):
    keys = list(S)
    o = {"variants": len(keys), "by_family": collections.Counter(k.split("|")[0] for k in keys)}
    h1 = [k for k in keys if gate(S[k]["H1"], 20)]
    o["h1_gate"] = len(h1)
    o["h1_gate_pos_h2"] = sum(1 for k in h1 if S[k]["H2"]["net"] > 0)
    o["h1_gate_pos_h2_2025_2124"] = sum(1 for k in h1 if all(S[k][s]["net"] > 0 for s in ("H2", "2025", "2021-24")))
    o["all_pos4"] = sum(1 for k in keys if S[k]["H1"]["n"] >= 20 and all(S[k][s]["net"] > 0 for s in CHECK))
    o["all_gate4"] = sum(1 for k in keys if all(S[k][s]["n"] >= 5 and (S[k][s]["w05"] or 0) >= 55 and (S[k][s]["avgw"] or 0) >= 1.0
                                                and S[k][s]["net"] > 0 for s in CHECK))
    o["n_h1_20"] = sum(1 for k in keys if S[k]["H1"]["n"] >= 20)
    o["pos_rate"] = {s: round(100.0 * np.mean([S[k][s]["net"] > 0 for k in keys if S[k][s]["n"] >= 10]), 1) for s in CHECK}
    o["w05_med"] = {s: float(np.median([S[k][s]["w05"] for k in keys if S[k][s]["n"] >= 10])) for s in CHECK}
    o["exp_r_mean"] = {s: round(float(np.mean([S[k][s]["exp_r"] for k in keys if S[k][s]["n"] >= 10])), 3) for s in CHECK}
    # per family: average expectancy in R and the share positive (the 'is there anything here' view)
    fam = {}
    for f in GENS:
        kk = [k for k in keys if k.startswith(f + "|")]
        fam[f] = {s: {"exp_r": round(float(np.mean([S[k][s]["exp_r"] for k in kk if S[k][s]["n"] >= 10])), 3),
                      "pos": round(100.0 * np.mean([S[k][s]["net"] > 0 for k in kk if S[k][s]["n"] >= 10]), 1),
                      "w05": round(float(np.median([S[k][s]["w05"] for k in kk if S[k][s]["n"] >= 10])), 1)} for s in CHECK}
    o["family"] = fam
    # rank correlation H1 -> H2 (does H1 say anything about H2?)
    from scipy.stats import spearmanr  # noqa
    a = [(S[k]["H1"]["exp_r"], S[k]["H2"]["exp_r"], S[k]["2025"]["exp_r"], S[k]["2021-24"]["exp_r"]) for k in keys
         if min(S[k][s]["n"] for s in CHECK) >= 10]
    a = np.array(a)
    o["rank_corr"] = {"H1_H2": round(float(spearmanr(a[:, 0], a[:, 1])[0]), 3), "H1_2025": round(float(spearmanr(a[:, 0], a[:, 2])[0]), 3),
                      "2124_2025": round(float(spearmanr(a[:, 3], a[:, 2])[0]), 3), "2124_H2": round(float(spearmanr(a[:, 3], a[:, 1])[0]), 3)}
    return o


def exhaustion_effect(S):
    """The new angle: does the exhaustion overlay (day range >= x ADR) help? Pairs of variants that differ only in it."""
    out = {}
    for fam, kname in (("bx", "exh"), ("of", "exh"), ("ex", "rr")):
        diffs = collections.defaultdict(list)
        for k in S:
            if not k.startswith(fam + "|"):
                continue
            f, p, ex = parse(k)
            vals = SETUP[fam][kname]
            if p[kname] != vals[0]:
                continue
            for v in vals[1:]:
                k2 = vkey(fam, {**p, kname: v}, ex)
                if k2 in S:
                    for s in CHECK:
                        a, b = S[k][s], S[k2][s]
                        if a["n"] >= 10 and b["n"] >= 10:
                            diffs[(v, s)].append((b["exp_r"] - a["exp_r"], (b["w05"] or 0) - (a["w05"] or 0)))
        out[fam] = {f"{v}|{s}": {"pairs": len(L), "d_exp_r": round(float(np.mean([x[0] for x in L])), 3),
                                 "d_w05": round(float(np.mean([x[1] for x in L])), 1),
                                 "better_share": round(100.0 * np.mean([x[0] > 0 for x in L]), 1)} for (v, s), L in diffs.items() if L}
    return out


def detail(key):
    T = trades_of(key)
    S = {s: stats(T, s) for s in CHECK}
    return T, S


def cmd_pick():
    S = grid()
    res = {"counts": summary_counts(S), "exhaustion": exhaustion_effect(S)}
    print(json.dumps(res["counts"], default=str)[:3000], flush=True)
    res["h1"] = pick(S, "H1", 20)
    res["long"] = pick(S, "2021-24", 150, 55.0, 1.15)
    # looser H1 gate (the owner's 55% "true winners" floor kept, PF 1.2) for the record
    res["h1_loose"] = pick(S, "H1", 20, 55.0, 1.2)
    for mode in ("h1", "long"):
        for fam, pk in res[mode].items():
            if not pk:
                continue
            k = pk["key"]
            T = with_ex(trades_of(k), k)
            pk["spans"] = {s: stats(T, s) for s in CHECK}
            pk["drop5"] = {s: drop_best(T, s) for s in CHECK}
            pk["months_2026"] = months(T)
            pk["years"] = years(T)
            nb = [n for n in neighbours(k) if n in S]
            chk = ("H2", "2025", "2021-24") if mode == "h1" else ("2025", "H1", "H2")
            pk["nb_check_pos"] = {s: f"{sum(1 for n in nb if S[n][s]['net'] > 0)}/{len(nb)}" for s in chk}
            pk["placebo"] = {s: placebo(T, s, fam_window(k)) for s in chk}
            sl = pk["shortlist"]
            pk["shortlist_check"] = {s: f"{sum(1 for x in sl if S[x][s]['net'] > 0)}/{len(sl)}" for s in chk}
            print(mode, fam, k, {s: (pk["spans"][s]["n"], pk["spans"][s]["w05"], pk["spans"][s]["pf"], pk["spans"][s]["net"]) for s in CHECK},
                  pk["placebo"].get("H2" if mode == "h1" else "2025"), flush=True)
    res["chance"] = chance(S)
    print("chance", res["chance"], flush=True)
    _dump(res, os.path.join(OUT, "picks.json"), indent=1, default=str)
    return res


# ================================================================================================ 3. books, evals, correlation
def merge(lists, max_day=2):
    allt = sorted([(t, j) for j, L in enumerate(lists) for t in L], key=lambda x: (x[0]["entry_t"], x[1]))
    out, nday, busy = [], collections.Counter(), -1
    for t, j in allt:
        if nday[t["day"]] >= max_day or t["entry_t"] < busy:
            continue
        out.append(t)
        nday[t["day"]] += 1
        busy = t["exit_t"]
    return out


def lit_daily():
    from tools import runlib as rl
    r = rl.load("lit_live")
    c = r["trade_cols"]
    by = collections.defaultdict(float)
    for row in r["trades"]:
        t = dict(zip(c, row))
        by[t["day"]] += t["pnl"]
    return by


def corr_lit(T, span):
    L = lit_daily()
    ss = sessions(span)
    a = collections.defaultdict(float)
    for t in T:
        a[t["day"]] += t["pnl_usd"]
    x = np.array([a.get(d, 0.0) for d in ss])
    y = np.array([L.get(d, 0.0) for d in ss])
    if x.std() == 0 or y.std() == 0:
        return None
    both = sum(1 for d in ss if a.get(d) and L.get(d))
    return {"r": round(float(np.corrcoef(x, y)[0, 1]), 3), "both_days": both,
            "same_day_both_lose": sum(1 for d in ss if a.get(d, 0) < 0 and L.get(d, 0) < 0)}


def lit_plus(T, span):
    """LIT (run lit_live, LIT size) + the setup at $500 risk on separate sizing: does the combined daily equity smooth?"""
    L = lit_daily()
    ss = sessions(span)
    a = collections.defaultdict(float)
    for t in T:
        a[t["day"]] += t["pnl_usd"]
    out = {}
    for nm, f in (("lit", lambda d: L.get(d, 0.0)), ("lit+hq", lambda d: L.get(d, 0.0) + a.get(d, 0.0))):
        p = np.array([f(d) for d in ss])
        eq = np.cumsum(p)
        dd = float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min())
        out[nm] = {"net": round(float(p.sum())), "dd": round(dd), "sharpe_d": round(float(p.mean() / p.std() * np.sqrt(252)), 2) if p.std() else None,
                   "neg_days": int((p < 0).sum())}
    return out


def eval_views(T, src):
    from tools import second_mix as SM
    U = A.my_units([{k: v for k, v in t.items()} for t in T], src)
    UL = list(SM.units()["LIT"])
    UUn = SM.no_hedge(U)
    o = {"acct25k": {}, "50k_need0.5": {}, "50k_usd300": {}}
    for s in CHECK:
        o["acct25k"][s] = A.score_acct(UUn, "builder25k", s, 2)[0]
        o["50k_need0.5"][s] = A.score_50k(UL + U, "need0.5", s, 2)[0]
        o["50k_usd300"][s] = A.score_50k(UL + U, "usd300_safe_dll", s, 2)[0]
    return o


def lit_alone_50k():
    from tools import second_mix as SM
    UL = list(SM.units()["LIT"])
    return {s: A.score_50k(UL, "usd300", s, 2)[0] for s in CHECK}


# the one setup that passes the win gate in all four spans - found by LOOKING at all four (peeked), ~0.25 trades a week
PEEKED = "bx|box=lon,sides=2,depth=0.0,conf=rc,nb=3,end=925,exh=1.0|R1,None,eod"


def runner_trades(key, lvn="opp", label=None):
    """Post-hoc management check on a pick: half the micros at 1R, the other half to the level lvn (at least 1R, at most 4R)
    with breakeven (entry + 1.25) once +1R was reached. Same entries as the pick."""
    fam, p, ex = parse(key)
    X = ctx()
    E = events()[fam]
    first = {}
    for ev in E:
        if match(fam, ev, p):
            cur = first.get(ev["k"])
            if cur is None or ev["i"] < cur["i"]:
                first[ev["k"]] = ev
    out = []
    for k in sorted(first):
        ev = dict(first[k])
        ev["label"] = label or key + " +runner"
        a = sim(X, ev, ("R1", None, ex[2]))
        b = sim(X, ev, (f"LX:{lvn}", 1.0, ex[2]))
        if a is None or b is None:
            continue
        q = a["qty"]
        if q < 2:
            continue
        q1 = q // 2
        q2 = q - q1
        pnl = (a["pts"] * PV - COMM) * q1 + (b["pts"] * PV - COMM) * q2
        pts = (a["pts"] * q1 + b["pts"] * q2) / q
        d = a["dir"]
        t = {**b, "exit_t": max(a["exit_t"], b["exit_t"]), "exit": round(a["entry"] + d * pts, 2),
             "exit_kind": a["exit_kind"] if b["exit_kind"] == "STOP" else b["exit_kind"], "r": round(pts / a["risk"], 3),
             "rn": round(pnl / (a["risk"] * PV * q), 3), "qty": q, "pnl_usd": round(pnl, 2), "pts": round(pts, 4),
             "w1": min(a["w1"], b["w1"]), "tgt_r": a["tgt_r"]}
        out.append(t)
    return out


def cmd_evals(keys=None):
    P = json.load(open(os.path.join(OUT, "picks.json")))
    cands, seen = {}, set()
    for mode in ("h1", "long"):
        for fam, pk in P[mode].items():
            if pk and pk["key"] not in seen:
                cands[f"{mode}_{fam}"] = pk["key"]
                seen.add(pk["key"])
    cands["peeked_bx"] = PEEKED
    cands.update(keys or {})
    res = {"lit_alone_50k": lit_alone_50k(), "cands": {}}
    lists = {}
    for nm, k in cands.items():
        T = trades_of(k, label=nm)
        lists[nm] = T
    of = P["h1"].get("of")
    if of:
        lists["h1_of_runner"] = runner_trades(of["key"], "opp", "h1_of_runner")
        cands["h1_of_runner"] = of["key"] + " +runner(opp)"
    # books: the H1 picks together (one position, max 2 a day), and the pre-2025 picks together
    for bn, pref in (("book_h1", "h1_"), ("book_long", "long_")):
        L = [lists[n] for n in lists if n.startswith(pref) and "runner" not in n]
        if pref == "long_" and of:
            L.append(lists["h1_of"])                 # the pre-2025 re-pick chose the same failed-ORB setup
        if L:
            lists[bn] = merge(L, 2)
    for nm, T in lists.items():
        r = {"key": cands.get(nm), "spans": {s: stats(T, s) for s in CHECK}, "drop5": {s: drop_best(T, s) for s in CHECK},
             "months_2026": months(T), "years": years(T), "corr_lit": {s: corr_lit(T, s) for s in CHECK},
             "lit_plus": {s: lit_plus(T, s) for s in CHECK}}
        r["evals"] = eval_views(T, nm)
        res["cands"][nm] = r
        e = r["evals"]
        print(nm, {s: (r["spans"][s]["n"], r["spans"][s]["w05"], r["spans"][s]["net"]) for s in CHECK},
              "25k", {s: (e["acct25k"][s]["p10"], e["acct25k"][s]["dead10"]) for s in CHECK},
              "50k", {s: (e["50k_need0.5"][s]["p10"], e["50k_need0.5"][s]["f10"]) for s in CHECK}, flush=True)
    _dump(res, os.path.join(OUT, "evals.json"), indent=1, default=str)
    return res


# ================================================================================================ 4. look-ahead audit
def cmd_audit(n=40, seed=3):
    """Re-derive picks' trades on data CUT at the signal bar's close (arrays truncated to bars <= signal, ATR / VWAP / day
    high-low recomputed on the cut arrays): the same event (bar, side, stop, target levels) must come out."""
    P = json.load(open(os.path.join(OUT, "picks.json")))
    X = ctx()
    M = X["M"]
    rng = np.random.default_rng(seed)
    keys = [pk["key"] for mode in ("h1", "long") for pk in P[mode].values() if pk]
    res = {"checked": 0, "same": 0, "diff": []}

    class Cut:
        pass
    for key in keys:
        fam, p, ex = parse(key)
        T = trades_of(key)
        pickt = [T[int(i)] for i in rng.choice(len(T), size=min(len(T), max(1, n // len(keys))), replace=False)]
        for t in pickt:
            m = t["sig_i"]
            z = m + 1
            C = Cut()
            for a in ("t", "o", "h", "l", "c", "v", "mod", "day_of"):
                setattr(C, a, getattr(M, a)[:z])
            C.atr = lit.atr(C.h, C.l, C.c)
            C.n = z
            k = int(M.day_of[m])
            d, s, e = M.days[k]
            C.days = list(M.days[:k]) + [(d, s, z)]
            C.ctx = M.ctx
            tp = (C.h + C.l + C.c) / 3.0
            v = np.maximum(C.v, 1.0)
            vw = np.cumsum(tp[s:z] * v[s:z]) / np.cumsum(v[s:z])
            Y = {"M": C, "D": X["D"], "adr": X["adr"], "vw": np.r_[np.zeros(s), vw], "dh": np.r_[np.zeros(s), np.maximum.accumulate(C.h[s:z])],
                 "dl": np.r_[np.zeros(s), np.minimum.accumulate(C.l[s:z])]}
            md = C.mod[s:z]
            ii = np.flatnonzero((md >= 570) & (md < 1080))
            rv = np.full(z, np.nan)
            if len(ii):
                a0 = s + ii[0]
                rv[a0:z] = np.cumsum(tp[a0:z] * v[a0:z]) / np.cumsum(v[a0:z])
            Y["rv"] = rv
            ev = [x for x in GENS[fam](Y, days={k}) if match(fam, x, p)]
            ev.sort(key=lambda x: x["i"])
            res["checked"] += 1
            full = [x for x in events()[fam] if x["k"] == k and match(fam, x, p)]
            full.sort(key=lambda x: x["i"])
            ok = bool(ev) and ev[0]["i"] == full[0]["i"] == m and ev[0]["dir"] == full[0]["dir"] and abs(ev[0]["stop"] - full[0]["stop"]) < 1e-6 \
                and all(abs(ev[0]["lv"].get(q, 0) - full[0]["lv"].get(q, 0)) < 1e-6 for q in full[0]["lv"])
            if ok:
                res["same"] += 1
            else:
                res["diff"].append({"key": key, "day": t["day"], "cut": ev[0] if ev else None, "full": {kk: full[0][kk] for kk in ("i", "dir", "stop", "lv")}})
    print(res["checked"], "checked,", res["same"], "identical", flush=True)
    _dump(res, os.path.join(OUT, "audit.json"), indent=1, default=str)
    return res


# ================================================================================================ 5. store
COMMON = ("day", "entry_t", "exit_t", "dir", "entry", "stop", "target", "exit", "exit_kind", "r", "qty", "pnl_usd", "setup")

RULES = {
    "ex": "Stretched day: the trading day's range from 18:00 is >= {rr} x the 14-day mean daily range; price trades through the "
          "day's high (low) that was set at least 30 minutes earlier{dep}; within {nb} bars a 5m {cf}; window {win}.",
    "bx": "Box swept: the {box} range; {sides}{dep}; within {nb} bars a 5m {cf}; entries until {end}{exh}.",
    "vx": "Stretched into a higher-timeframe pool: an untaken {pool} is swept while the extreme is >= {k} x the 5m ATR away from "
          "the 18:00 VWAP; within {nb} bars a 5m {cf}; window {win}.",
    "of": "Failed opening-range breakout: the 09:30-{orend} range; a 5m {bo} beyond it, then within {nb} bars a 5m {cf}; signal "
          "10:00-11:30{ext}{exh}.",
}
CFW = {"rc": "close back inside the level", "cisd": "close back inside that is also beyond the open of the candle run into the "
       "extreme (CISD)", "d05": "close back inside with a body >= 0.5 x ATR (displacement)", "d08": "close back inside with a body "
       ">= 0.8 x ATR (displacement)"}


def rules_of(key):
    fam, p, ex = parse(key)
    q = dict(p)
    q["cf"] = CFW.get(p.get("conf"), p.get("conf"))
    q["dep"] = f" by >= {p['depth']} x the 5m ATR" if p.get("depth") else ""
    if fam in ("ex", "vx"):
        a, z = WINDOWS[p["win"]]
        q["win"] = f"{a // 60:02d}:{a % 60:02d}-{z // 60:02d}:{z % 60:02d} ET"
    if fam == "bx":
        q["box"] = {"on": "overnight 18:00-09:30", "lon": "London 02:00-05:00", "asia": "Asia 20:00-00:00"}[p["box"]]
        q["sides"] = ("its high AND its low have both been traded through since the box closed; the second sweep" if p["sides"] == 2
                      else "the first sweep of one side")
        q["end"] = f"{p['end'] // 60:02d}:{p['end'] % 60:02d} ET"
        q["exh"] = f"; only when the day's range is already >= {p['exh']} x the 14-day mean range" if p["exh"] else ""
    if fam == "vx":
        q["pool"] = {"d": "prior-day high/low", "w": "prior-week high/low", "m": "prior-month high/low",
                     "dwm": "prior-day/week/month high/low"}[p["pool"]]
    if fam == "of":
        q["orend"] = "09:45" if p["orm"] == 15 else "10:00"
        q["bo"] = "close" if p["bo"] == "close" else "wick (a trade 1 tick through)"
        q["ext"] = f"; the breakout ran >= {p['ext']} x the range width" if p["ext"] else ""
        q["exh"] = f"; only when the day's range is already >= {p['exh']} x the 14-day mean range" if p["exh"] else ""
    t, be, h = ex
    tg = {"R1": "1R", "R1.5": "1.5R"}.get(t)
    if tg is None:
        mode, lv = t.split(":")
        nm = {"vwap": "the 18:00 session VWAP", "rvwap": "the RTH VWAP (from 09:30)", "mid": "the day's midpoint so far",
              "bmid": "the box middle", "omid": "the opening range middle", "opp": "the other side of the range"}[lv]
        tg = nm + (" (skip if closer than 1R)" if mode == "L" else " (at least 1R)") + ", at most 4R"
    return [RULES[fam].format(**q),
            "Trade against the swept side (short after a high, long after a low) at the next 5m open + 1 tick; stop 1 tick beyond "
            "the extreme from the sweep to the signal bar (6-80 pts, else no trade).",
            f"Target {tg}." + (f" Breakeven (entry + 1.25 pts) once +{be}R was reached." if be else " No breakeven."),
            "Time exit " + ("2 hours after the entry" if h == "2h" else "15:55 ET") + "; one trade a day; $500 risk "
            "(floor(500 / (stop x $2)) micros, max 50); $1.90 a micro + 1 tick on entries, stop and time exits."]


def slip_stress(T, span, ticks=1):
    """One extra tick on the entry and on every non-limit exit."""
    a, z = SPANS[span]
    s = 0.0
    for t in T:
        if a <= t["day"] <= z:
            extra = ticks * TICK * PV * t["qty"] * (1 + (t["exit_kind"] != "TARGET"))
            s += t["pnl_usd"] - extra
    return round(s)


def cmd_save():
    from tools import runlib as rl
    D = ctx()["D"]
    sess = D["sess"]
    P = json.load(open(os.path.join(OUT, "picks.json")))
    EV = json.load(open(os.path.join(OUT, "evals.json")))
    Q = ("Owner 2026-10-23: a strategy that trades 2+ times a week with high-quality, high-probability, high-profit setups - "
         "mean reversion at exhaustion (stretched range / both sides swept / stretched into a HTF pool / failed ORB).")
    S = grid()
    # compact grid (every variant: n, w05, pf, net per span) for the record
    _dump({"cols": ["n", "w05", "avgw", "pf", "net"], "spans": list(CHECK),
           "v": {k: [[S[k][s].get(c) for c in ("n", "w05", "avgw", "pf", "net")] for s in CHECK] for k in S}},
          os.path.join(OUT, "grid_compact.json"), separators=(",", ":"))
    how = {"h1_bx": "H1 pick (2026 Jan-Jun, 20+ trades, true winners >= 55%, avg winner >= 1R, PF >= 1.3, plateau score)",
           "h1_vx": "H1 pick", "h1_of": "H1 pick AND the pre-2025 re-pick (2021-24, same gate) - both chose it",
           "long_bx": "pre-2025 re-pick (2021-24)", "peeked_bx": "found by looking at all four periods (peeked)",
           "h1_of_runner": "post-hoc management check on the failed-ORB pick (half at 1R, half to the range's other side, BE at 1R)",
           "book_h1": "the three H1 picks together (one position, max 2 a day)", "book_long": "the pre-2025 picks together"}
    status = {k: "rejected" for k in how}
    status["h1_of"] = "promising"
    index = {}
    for nm, r in EV["cands"].items():
        key = r.get("key")
        if nm == "h1_of_runner":
            T = runner_trades(P["h1"]["of"]["key"], "opp", nm)
        elif nm.startswith("book_"):
            parts = [trades_of(EV["cands"][x]["key"], label=x) for x in EV["cands"] if x.startswith("h1_" if nm == "book_h1" else "long_")
                     and "runner" not in x]
            if nm == "book_long":
                parts.append(trades_of(P["h1"]["of"]["key"], label="h1_of"))
            T = merge(parts, 2)
        else:
            T = trades_of(key, label=nm)
        sp = {s: stats(T, s) for s in CHECK}
        rec = {"id": f"hq_rev_{nm}", "key": key, "how_picked": how.get(nm), "rules": rules_of(key) if key and "|" in key and "runner" not in key else None,
               "spans": sp, "drop_best5": r["drop5"], "slip_plus1tick": {s: slip_stress(T, s) for s in CHECK},
               "months_2026": r["months_2026"], "years": r["years"], "corr_lit_daily": r["corr_lit"], "lit_plus": r["lit_plus"],
               "evals": r["evals"], "costs": "$1.90 a micro round trip + 1 tick on market entries, stop and time exits",
               "size": "$500 risk a trade (eval views: the plan's own sizing)",
               "data": "TradingView CME NQ1! 5m (data/NQ_5m.csv); true 1m for the 2026 trade path (data/NQ_1m.csv)",
               "trade_format": list(COMMON), "trades": [{c: t.get(c) for c in COMMON} for t in T]}
        if key and nm in ("h1_bx", "h1_vx", "h1_of", "long_bx"):
            mode, fam = nm.split("_")
            pk = P[mode][fam]
            rec.update(placebo=pk["placebo"], neighbours_check=pk["nb_check_pos"], shortlist_check=pk["shortlist_check"])
        _dump(rec, os.path.join(OUT, f"{nm}.json"), separators=(",", ":"))
        index[nm] = {"key": key, "how": how.get(nm), "spans": {s: {x: sp[s][x] for x in ("n", "tpw", "w05", "pf", "net")} for s in CHECK}}
        TT = A.run_trades(T)
        e = r["evals"]
        f = lambda s: (f"{s}: {sp[s]['n']} trades ({sp[s]['tpw']}/wk), true win {sp[s]['w05']}%, PF {sp[s]['pf']}, net {sp[s]['net']:+,} "  # noqa: E731
                       f"(${sp[s]['per_month']:,}/mo), DD {sp[s]['dd']:,}")
        g = lambda s: (f"{s} 25K alone 2-wk {e['acct25k'][s]['p10']}/{e['acct25k'][s]['dead10']}, next to LIT on the 50K "  # noqa: E731
                       f"{e['50k_need0.5'][s]['p10']}/{e['50k_need0.5'][s]['f10']}")
        rl.save(f"hq_rev_{nm}", f"HQ reversion: {nm.replace('_', ' ')} ({how.get(nm, '').split(' (')[0]})", "winrate", Q,
                params={"key": key, "rules": rec["rules"]}, sizing={"risk_usd": RISK_USD, "max_micros": MAXQ, "comm": COMM},
                trades=TT, scored=rl.score(TT, sess), status=status.get(nm, "rejected"),
                verdict="$500 risk, costs in. " + ". ".join(f(s) for s in CHECK) + ". Evals (pass/fail-or-dead %): " + "; ".join(g(s) for s in CHECK) + ".",
                notes=f"tools/hq_revert.py; {how.get(nm)}", writeup="hq-reversion", tags=["hq_revert", nm.split("_")[-1]])
        print("saved", nm, flush=True)
    _dump({"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "files": index}, os.path.join(OUT, "index.json"), indent=1)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "grid"
    if cmd == "events":
        events()
    elif cmd == "grid":
        cmd_grid()
    elif cmd == "pick":
        cmd_pick()
    elif cmd == "evals":
        cmd_evals()
    elif cmd == "audit":
        cmd_audit()
    elif cmd == "save":
        cmd_save()
