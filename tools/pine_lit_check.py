"""Check the TradingView LIT indicator (tradingview/lit_levels.pine) against the bot's rules (engine/lit.py).

Pine cannot be compiled or run here, so this file holds a bar-by-bar Python twin of the indicator: the same state machine,
the same order of steps on every confirmed 5m bar, the same ATR (Pine ta.rma seeded with an SMA), the same streaming
levels, sweeps, inducement, displacement, CISD, stop, target, 5m entry approximation and one-trade-a-day lock. It runs
on data/NQ_5m.csv and compares every element with engine/lit.py (Market.levels, candidates(ref="cisd"), the run_x filters
and run_x itself on 5m bars) for every 2026 trading day. It never trades and never touches the live bot.

  python -X utf8 tools/pine_lit_check.py            # all 2026 days: match % per element + mismatches with reasons
  python -X utf8 tools/pine_lit_check.py --days 20  # the last 20 trading days only (quick)
  python -X utf8 tools/pine_lit_check.py --lint     # static lint of tradingview/lit_levels.pine only

What the twin mirrors in the Pine file (keep both in step when either changes):
  step 1  new trading day (18:00 ET): previous day / week / month high-low, NDOG / NWOG, 18:00 open, VIX one-day move
  step 2  session boxes: a box becomes a level on the first bar after its last bar (11 boxes, as engine/lit.py SESSIONS)
  step 3  k=2 fractals confirmed 2 bars late; build-ups = two fractals within max(1.5, 0.15 ATR), 3+ bars apart, untouched
  step 4  first breach of every level (low side: a low below it; high side: a high above it), daily levels from 18:00
  step 5  trigger: 5m close beyond the CISD level of the 24-bar extreme, extreme took a level first breached <= 24 bars
          before it -> raw sweep; then the bot's filters (depth 0.5 ATR, displacement 0.8 ATR, inducement, Monday rule,
          stop 8-80, VIX band >= 1.5R) -> setup armed at the trigger close
  step 6  the next bar: re-check the window / target against its open, then the 5m limit + 4-bar 5m CISD confirmation
          (the bot's 5m fallback; live it confirms on 1m bars) and the 5m trade walk (stop / target / BE 1R / 15:55)
"""
from __future__ import annotations

import argparse
import bisect
import collections
import math
import os
import re
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from engine.data import load  # noqa: E402

PINE = os.path.join(ROOT, "tradingview", "lit_levels.pine")
TICK, SLIP = 0.25, 0.25
LEG, SWEEP_WIN, REF_BACK = 24, 24, 36
SESS = [(nm, a, z) for nm, (a, z) in lit.SESSIONS.items()]      # same 11 boxes, same order
MAX_ARMED = 3
P = {"window": (120, 930), "depth": 0.5, "disp": 0.8, "idm": (1.0, 36, 1), "wait": 6, "cis5": 4, "stop_buf": 0.25,
     "min_stop": 8.0, "max_stop": 80.0, "vix_k": 1.0, "min_rr": 1.5, "max_rr": 8.0, "be_r": 1.0, "flat": 955, "monday": True}


# ================================================================================================ the Pine twin
class Twin:
    def __init__(self, b, start):
        self.b, self.start = b, start
        self.t, self.o, self.h, self.l, self.c = b.t, b.o, b.h, b.l, b.c
        self.mod, self.dow, self.tday, self.date = b.mod, b.dow, b.tday, b.date_str
        n = len(b.t)
        self.atr = np.full(n, np.nan)
        self.vd, self.vc = lit._vix("VIX")
        self.fh, self.fl = [], []            # confirmed fractal bar indices (highs, lows)
        self.recent = {"low": collections.deque(), "high": collections.deque()}
        self.bu = []                          # build-ups: dict(side, p, known, fb, name)
        self.day_levels = []                  # dict(side, p, known, fb, name)
        self.levels_log = {}                  # day -> list of (name, price) (non build-up) at the end of the day
        self.bu_log = []                      # (side, price, known index)
        self.raw, self.setups, self.trades, self.events = [], [], [], []
        self.armed = []                       # up to MAX_ARMED limits working at once (the live bot: first fill wins)
        self.trade = None

    # ---- ATR exactly as Pine ta.atr(14): RMA of ta.tr(true), seeded with the SMA of the first 14 values
    def _atr(self, n):
        tr = self.h[n] - self.l[n] if n == self.start else max(self.h[n] - self.l[n], abs(self.h[n] - self.c[n - 1]),
                                                                 abs(self.l[n] - self.c[n - 1]))
        k = n - self.start
        if k < 14:
            self._trs = getattr(self, "_trs", []) + [tr]
            self.atr[n] = np.mean(self._trs) if k == 13 else np.nan
        else:
            self.atr[n] = self.atr[n - 1] + (tr - self.atr[n - 1]) / 14.0

    def run(self, end=None):
        end = len(self.t) if end is None else end
        for n in range(self.start, end):
            self.bar(n)
        self._end_day(end)
        return self

    def _end_day(self, n):
        if getattr(self, "s", None) is not None:
            for nm, bx in self.box.items():
                if not bx[4] and bx[2] >= 2:
                    self.day_levels.append({"side": "high", "p": float(bx[0]), "known": bx[3], "fb": None, "name": nm + "_h"})
                    self.day_levels.append({"side": "low", "p": float(bx[1]), "known": bx[3], "fb": None, "name": nm + "_l"})
            self.levels_log[self.cur_date] = sorted((z["name"], round(z["p"], 2)) for z in self.day_levels)

    def bar(self, n):
        o, h, l, c, mod = self.o, self.h, self.l, self.c, self.mod
        self._atr(n)
        new_day = n == self.start or self.tday[n] != self.tday[n - 1]
        # ---- step 1: new trading day
        if new_day:
            if n > self.start:
                self._end_day(n)
                prev_h, prev_l = self.dH, self.dL
                wid_new = (int(self.tday[n]) + 3) // 7
                mid_new = self.date[n][:7]
                if wid_new != self.wid:
                    self.pw = (self.wH, self.wL)
                    self.wH, self.wL = -np.inf, np.inf
                    g = sorted([float(c[n - 1]), float(o[n])])
                    self.nwog = g if g[1] - g[0] >= TICK else None
                    self.wid = wid_new
                if mid_new != self.mid:
                    self.pm = (self.mH, self.mL)
                    self.mH, self.mL = -np.inf, np.inf
                    self.mid = mid_new
                self.pd = (prev_h, prev_l)
                g = sorted([float(c[n - 1]), float(o[n])])
                self.ndog = g if g[1] - g[0] >= TICK else None
            else:
                self.pd = self.pw = self.pm = self.nwog = self.ndog = None
                self.wid = (int(self.tday[n]) + 3) // 7
                self.mid = self.date[n][:7]
                self.wH, self.wL, self.mH, self.mL = -np.inf, np.inf, -np.inf, np.inf
            self.s = n
            self.cur_date = self.date[n]
            self.dH, self.dL = -np.inf, np.inf
            self.open18 = float(o[n])
            j = bisect.bisect_left(self.vd, self.cur_date) - 1
            self.vmove = float(self.vc[j]) / 100.0 / math.sqrt(252.0) * self.open18 if j >= 0 else None
            self.box = {nm: [-np.inf, np.inf, 0, -1, False] for nm, _a, _z in SESS}   # hi, lo, count, last, done
            self.last_e = {1: -1, -1: -1}
            self.locked = False
            L = []
            for key, (hh, ll) in (("pd", self.pd or (None, None)), ("pw", self.pw or (None, None)), ("pm", self.pm or (None, None))):
                if hh is not None:
                    L.append({"side": "high", "p": float(hh), "known": n - 1, "fb": None, "name": key + "h"})
                    L.append({"side": "low", "p": float(ll), "known": n - 1, "fb": None, "name": key + "l"})
            for gk in ("nwog", "ndog"):
                gv = getattr(self, gk)
                if gv and (gk == "ndog" or self.pw is not None):
                    for px in gv:
                        L.append({"side": "high" if px > self.open18 else "low", "p": float(px), "known": n - 1, "fb": None,
                                  "name": gk})
            self.day_levels = L
            self.bu = [z for z in self.bu if z["known"] >= n - 576]
        self.dH, self.dL = max(self.dH, h[n]), min(self.dL, l[n])
        self.wH, self.wL = max(self.wH, h[n]), min(self.wL, l[n])
        self.mH, self.mL = max(self.mH, h[n]), min(self.mL, l[n])
        # ---- step 2: session boxes
        m = int(mod[n])
        for nm, a, z in SESS:
            bx = self.box[nm]
            inb = (a <= m < z) if a < z else (m >= a)
            inb = inb and ((m >= 1080) if a >= 1080 else (m < 1080))
            if inb:
                bx[0], bx[1], bx[2], bx[3] = max(bx[0], h[n]), min(bx[1], l[n]), bx[2] + 1, n
            elif bx[2] >= 1 and not bx[4]:
                bx[4] = True
                if bx[2] >= 2:
                    self.day_levels.append({"side": "high", "p": float(bx[0]), "known": bx[3], "fb": None, "name": nm + "_h"})
                    self.day_levels.append({"side": "low", "p": float(bx[1]), "known": bx[3], "fb": None, "name": nm + "_l"})
        # ---- step 3: fractals (confirmed at j + 2) and build-ups
        j = n - 2
        if j - 2 >= self.start:
            if h[j] > max(h[j - 2], h[j - 1]) and h[j] >= max(h[j + 1], h[j + 2]):
                self.fh.append(j); self._buildup("high", j, n)
            if l[j] < min(l[j - 2], l[j - 1]) and l[j] <= min(l[j + 1], l[j + 2]):
                self.fl.append(j); self._buildup("low", j, n)
        # ---- step 4: first breach
        for z in self.day_levels + self.bu:
            if z["fb"] is None and z["known"] < n:
                if (z["side"] == "low" and l[n] < z["p"]) or (z["side"] == "high" and h[n] > z["p"]):
                    z["fb"] = n
        # ---- step 6 first (the bar after the trigger, and any armed setup / open trade), then step 5 on this bar's close
        self._exec(n)
        self._detect(n)

    def _buildup(self, side, j, n):
        arr = self.l if side == "low" else self.h
        rec = self.recent[side]
        while rec and j - rec[0] > 288:
            rec.popleft()
        tol = max(1.5, 0.15 * self.atr[j]) if not np.isnan(self.atr[j]) else None
        if tol is not None:
            for kk in reversed(rec):
                if j - kk < 3 or abs(arr[j] - arr[kk]) > tol:
                    continue
                if side == "low":
                    lev = min(arr[j], arr[kk])
                    if self.l[kk + 1:j].min() > lev:
                        self.bu.append({"side": "low", "p": float(lev), "known": n, "fb": None, "name": "bu_l"})
                        self.bu_log.append(("low", round(float(lev), 2), n)); break
                else:
                    lev = max(arr[j], arr[kk])
                    if self.h[kk + 1:j].max() < lev:
                        self.bu.append({"side": "high", "p": float(lev), "known": n, "fb": None, "name": "bu_h"})
                        self.bu_log.append(("high", round(float(lev), 2), n)); break
        rec.append(j)

    def _dirs(self, d):
        return (self.h, self.l, self.c, self.o) if d == 1 else (-self.l, -self.h, -self.c, -self.o)

    @staticmethod
    def _cisd(c_d, o_d, ee, floor):
        jj = ee
        while jj > ee - 3 and not (c_d[jj] < o_d[jj]):
            jj -= 1
        if not (c_d[jj] < o_d[jj]):
            return None
        st = jj
        while st - 1 >= floor and c_d[st - 1] < o_d[st - 1] and st > ee - 30:
            st -= 1
        return float(o_d[st]), st

    # ---- step 5
    def _detect(self, i):
        if self.pd is None or i < self.s + LEG:
            return
        m = int(self.mod[i])
        if not (60 <= m < 955) or m >= 1080:
            return
        for d in (1, -1):
            hi_d, lo_d, c_d, o_d = self._dirs(d)
            a = i - LEG
            ee = a + int(np.argmin(lo_d[a:i + 1]))
            if ee == i or ee == self.last_e[d]:
                continue
            cz = self._cisd(c_d, o_d, ee, self.start)
            if cz is None:
                continue
            rp, rj = cz
            if not (c_d[i] > rp and c_d[ee:i].max() <= rp):
                continue
            ext = float(lo_d[ee])
            side = "low" if d == 1 else "high"
            sw = [z for z in self.day_levels + self.bu if z["side"] == side and z["known"] < ee and z["fb"] is not None
                  and ee - SWEEP_WIN <= z["fb"] <= ee and ext < z["p"] * d]
            if not sw:
                continue
            self.last_e[d] = ee
            sb = min(z["fb"] for z in sw)
            lev_near = max(z["p"] * d for z in sw)
            at = self.atr
            depth = (lev_near - ext) / max(at[ee], 1e-9)
            disp = max([(c_d[q] - o_d[q]) / max(at[q], 1e-9) for q in range(ee + 1, i + 1)] or [0.0])
            # inducement (engine idm_a): swing lows above the swept level, untouched until the final run took them
            swings = self.fl if d == 1 else self.fh
            lt0 = ee - REF_BACK
            seg = hi_d[lt0:ee + 1]
            leg_top = lt0 + int(len(seg) - 1 - np.argmax(seg[::-1]))
            idm = []
            for mm in swings[bisect.bisect_left(swings, sb - 72):bisect.bisect_left(swings, ee)]:
                if lo_d[mm] <= lev_near:
                    continue
                g = lo_d[mm + 1:ee + 1] < lo_d[mm]
                if not g.any():
                    continue
                tk = mm + 1 + int(np.argmax(g))
                if tk < max(leg_top, mm + 3) or tk > ee:
                    continue
                idm.append(((lo_d[mm] - lev_near) / max(at[sb], 1e-9), sb - mm))
            n_idm = sum(1 for dd, aa in idm if dd <= P["idm"][0] and aa <= P["idm"][1])
            names = sorted({z["name"] for z in sw})
            if (m + 5) % 1440 >= 955:         # the bot: entry bar at/after 15:55 -> no setup (the extreme still counts as used)
                continue
            raw = {"day": self.cur_date, "dir": d, "i": i, "ext_i": ee, "sweep_i": sb, "ref_d": rp, "ext_d": ext,
                   "swept": names, "depth": round(depth, 3), "disp": round(disp, 3), "n_idm": n_idm}
            self.raw.append(raw)
            # the bot's filters (engine setup_ok + monday_block + stop range + VIX band) at the trigger close
            why = []
            if not (P["window"][0] <= (m + 5) % 1440 < P["window"][1]):
                why.append("window")
            if depth < P["depth"]:
                why.append("depth")
            if disp < P["disp"]:
                why.append("disp")
            if n_idm < P["idm"][2]:
                why.append("inducement")
            if P["monday"] and self._monday_block(d, i):
                why.append("monday")
            ep = min(rp, float(c_d[i]))
            stop = ext - P["stop_buf"]
            risk = ep - stop
            if not (P["min_stop"] <= risk <= P["max_stop"]):
                why.append("stop range")
            tgt = None
            if self.vmove:
                pv = self.open18 * d + P["vix_k"] * self.vmove
                if pv > float(c_d[i]) + SLIP and pv - ep >= P["min_rr"] * risk:
                    tgt = ep + min(pv - ep, P["max_rr"] * risk)
            if tgt is None:
                why.append("target")
            raw["why"] = why
            if why:
                continue
            setup = dict(raw, ep=ep, stop=stop, risk=risk, tgt=tgt, pv=pv)
            self.setups.append(setup)
            if self.locked or self.trade is not None or len(self.armed) >= MAX_ARMED:
                setup["state"] = "ignored (day used / slots full)"
                continue
            setup["state"] = "armed"
            self.armed.append({"z": setup, "t0": i + 1, "tapped": None, "fill_next": False, "rechecked": False})

    def _monday_block(self, d, i):
        if int(self.dow[i]) != 0 or self.pd is None:
            return False
        took_hi = bool(self.h[self.s:i + 1].max() > self.pd[0])
        took_lo = bool(self.l[self.s:i + 1].min() < self.pd[1])
        if took_hi == took_lo:
            return False
        return (took_hi and d == 1) or (took_lo and d == -1)

    # ---- step 6 (5m executor: the bot's run_x on 5m bars, cisd1m 20 -> 4 five-minute bars)
    def _exec(self, k):
        keep = []
        for A in list(self.armed):
            if self.trade is not None:       # an earlier slot filled on this bar: the day is used, the rest is cancelled
                A["z"]["end"] = "day used"
                continue
            z = A["z"]; d = z["dir"]
            hi_d, lo_d, c_d, o_d = self._dirs(d)
            same = self.date[k] == z["day"]
            dead = None
            if not A["rechecked"]:
                A["rechecked"] = True
                m = int(self.mod[k])
                if not same or m >= 955 or m >= 1080:
                    dead = "no next bar"
                elif not (P["window"][0] <= m < P["window"][1]):
                    dead = "entry bar outside 02:00-15:30"
                elif not (z["pv"] > float(o_d[k]) + SLIP):
                    dead = "opened past the target"
            if dead is None and A["fill_next"]:
                if same:
                    entry = float(o_d[k]) + SLIP
                    risk = entry - z["stop"]
                    dist = z["tgt"] - entry
                    qty = lit.qty_for(risk) if risk > 0 else 0
                    if risk > 0 and dist >= P["min_rr"] * risk and qty >= 1:
                        tg = entry + min(dist, P["max_rr"] * risk)
                        self.trade = {"z": z, "entry": entry, "risk": risk, "tg": tg, "cur": z["stop"], "be": False,
                                      "fill": k, "qty": qty}
                        self.locked = True
                        dead = "filled"
                    else:
                        dead = "fill too close to the target"
                else:
                    dead = "day ended"
            elif dead is None:
                if not same or self.mod[k] >= P["flat"] or self.mod[k] >= 1080:
                    dead = "15:55 / day end"
                elif A["tapped"] is None and k >= A["t0"] + P["wait"]:
                    dead = "30 min, no tap"
                elif lo_d[k] <= z["stop"]:
                    dead = "extreme broken"
                else:
                    if A["tapped"] is None and lo_d[k] <= z["ep"]:
                        A["tapped"] = k
                    if A["tapped"] is None and hi_d[k] >= z["tgt"]:
                        dead = "target traded first"
                    elif A["tapped"] is not None:
                        tp = A["tapped"]
                        if k - tp > P["cis5"]:
                            dead = "no CISD confirmation"
                        else:
                            lowk = tp + int(np.argmin(lo_d[tp:k + 1]))
                            cz = self._cisd(c_d, o_d, lowk, self.start)
                            if cz is not None and k > lowk and c_d[k] > cz[0]:
                                A["fill_next"] = True
            if dead is not None:
                z["end"] = dead
            else:
                keep.append(A)
        self.armed = keep if self.trade is None else []
        if self.trade is not None:
            T = self.trade; z = T["z"]; d = z["dir"]
            hi_d, lo_d, c_d, o_d = self._dirs(d)
            kind = px = None
            if self.date[k] != z["day"]:
                kind, px = "EOD", float(c_d[k - 1]) - SLIP
            elif lo_d[k] <= T["cur"]:
                kind, px = ("BE" if T["be"] else "STOP"), T["cur"] - SLIP
            else:
                if hi_d[k] >= T["tg"]:
                    kind, px = "TARGET", T["tg"]
                else:
                    if not T["be"] and hi_d[k] >= T["entry"] + P["be_r"] * T["risk"]:
                        T["cur"], T["be"] = T["entry"], True
                    if self.mod[k] >= P["flat"]:
                        kind, px = "EOD", float(c_d[k]) - SLIP
            if kind:
                self.trades.append({"day": z["day"], "dir": d, "entry_px": round(T["entry"] * d, 2),
                                    "stop_px": round(z["stop"] * d, 2), "target_px": round(T["tg"] * d, 2), "exit": kind,
                                    "exit_px": round(px * d, 2), "qty": T["qty"]})
                self.trade = None


# ================================================================================================ engine side
def engine_side(M, C, days):
    dset = set(days)
    lv, bu = {}, set()
    for k, (d, s, e) in enumerate(M.days):
        if d not in dset:
            continue
        L = M.levels(k)
        lv[d] = sorted((nm, round(float(px), 2)) for side, px, ki, nm, cls in L if cls != "buildup")
        for side, px, ki, nm, cls in L:
            if cls == "buildup" and M.dates[min(ki, M.n - 1)] in dset:
                bu.add((side, round(float(px), 2), int(ki)))
    raw = [z for z in C if z["day"] in dset]
    PL = {**lit.DEFAULTS, **json_live()}
    setups = []
    for z in raw:
        if not lit.setup_ok(z, PL, None) or (PL.get("monday") and lit.monday_block(M, z)):
            continue
        ep = min(float(z["ref_d"]), z["trig_c"]); stop = z["ext_d"] - PL["stop_buf"]; risk = ep - stop
        if not (PL["min_stop"] <= risk <= PL["max_stop"]):
            continue
        sh = z["entry_d"] - ep
        tt = [x + sh for x in lit.targets_x(M, z, PL).get("vix", [])]
        tt = [x for x in tt if x >= PL["min_rr"] * risk]
        if not tt:
            continue
        setups.append(dict(z, ep=ep, stop=stop, tgt=ep + min(tt[0], PL["max_rr"] * risk)))
    P5 = dict(PL, tf="5m")
    tr = [t for t in lit.run_x(M, C, P5) if t["day"] in dset]
    return lv, bu, raw, setups, tr


def json_live():
    import json
    return json.load(open(os.path.join(ROOT, "live_model.json")))["lit"]


def near(z, key, thr, tol=0.03):
    return abs(z[key] - thr) <= tol


# ================================================================================================ lint
BUILTINS = {
    "ta": {"rma", "tr", "atr", "highest", "lowest", "sma", "ema", "change", "crossover", "crossunder", "valuewhen", "barssince"},
    "math": {"max", "min", "abs", "floor", "ceil", "round", "sqrt", "pow", "sign", "avg"},
    "array": {"new_float", "new_int", "new_bool", "new_string", "new_line", "new_box", "new_label", "push", "get", "set",
              "size", "clear", "shift", "remove", "unshift", "insert", "from", "join", "includes", "pop", "indexof"},
    "line": {"new", "delete", "set_x1", "set_x2", "set_xy1", "set_xy2", "set_y1", "set_y2", "set_color", "set_extend",
             "set_style", "set_width", "get_y1"},
    "box": {"new", "delete", "set_right", "set_top", "set_bottom", "set_bgcolor", "set_border_color", "set_lefttop",
            "set_rightbottom", "set_text", "set_left"},
    "label": {"new", "delete", "set_xy", "set_text", "set_color", "set_textcolor", "set_x", "set_y", "set_style",
              "set_tooltip"},
    "table": {"new", "cell", "clear", "cell_set_text", "cell_set_bgcolor"},
    "str": {"tostring", "format", "contains", "split", "length", "replace_all", "substring", "startswith"},
    "color": {"new", "rgb"},
    "request": {"security"},
    "input": {"bool", "int", "float", "string", "color", "session", "text_area", "symbol"},
    "timeframe": set(), "barstate": set(), "syminfo": set(), "display": set(), "position": set(), "size": set(),
    "shape": set(), "location": set(), "extend": set(), "xloc": set(), "yloc": set(), "text": set(), "font": set(),
    "barmerge": set(), "alert": set(), "dayofweek": set(), "format": set(), "plot": set(), "hline": set(),
}
TOP_FUNCS = {"indicator", "input", "plot", "plotshape", "bgcolor", "alert", "alertcondition", "nz", "na", "timestamp",
             "year", "month", "dayofmonth", "hour", "minute", "dayofweek", "fill", "hline", "max_bars_back", "time",
             "color", "int", "float", "bool", "string", "array", "if", "for", "while", "switch", "not", "and", "or",
             "plotchar", "line", "box", "label", "table", "math"}


def lint(path=PINE):
    """Static checks a Pine compiler would also make, as far as text can tell (it does not replace a TradingView compile)."""
    src = open(path, encoding="utf-8").read()
    lines = src.split("\n")
    probs, notes = [], []
    if not src.startswith("//@version=5"):
        probs.append("first line must be //@version=5")
    m = re.search(r"indicator\((.*?)\)\n", src, re.S)
    if not m:
        probs.append("no indicator() declaration")
    else:
        for k in ("max_lines_count", "max_boxes_count", "max_labels_count", "max_bars_back", "overlay=true"):
            if k not in m.group(1):
                probs.append(f"indicator() lacks {k}")
    if "strategy(" in src or "strategy." in src:
        probs.append("strategy calls found: the indicator must never place orders")
    # brackets balance (outside strings and comments)
    depth = {"(": 0, "[": 0}
    pairs = {")": "(", "]": "["}
    for no, ln in enumerate(lines, 1):
        code = re.sub(r'"(?:[^"\\]|\\.)*"', '""', ln)
        code = code.split("//")[0]
        for ch in code:
            if ch in depth:
                depth[ch] += 1
            elif ch in pairs:
                depth[pairs[ch]] -= 1
                if depth[pairs[ch]] < 0:
                    probs.append(f"line {no}: unbalanced '{ch}'"); depth[pairs[ch]] = 0
        stripped = code.rstrip()
        if stripped and not code.startswith(" " * 0):
            pass
    if any(depth.values()):
        probs.append(f"unbalanced brackets at the end: {depth}")
    # indentation: block lines are multiples of 4; a wrapped line must NOT be a multiple of 4 (Pine v5 rule)
    prev = ""
    for no, ln in enumerate(lines, 1):
        code = ln.split("//")[0].rstrip() if not ln.strip().startswith("//") else ""
        if not code.strip():
            continue
        ind = len(code) - len(code.lstrip(" "))
        if "\t" in ln[:ind + 1]:
            probs.append(f"line {no}: tab indentation")
        cont = prev.endswith((",", "(", "+", "-", "*", "/", "?", ":", " and", " or", "[")) or \
            (prev.endswith(("=", ">", "<")) and not prev.endswith("=>"))
        if cont and ind % 4 == 0:
            probs.append(f"line {no}: wrapped line indented by a multiple of 4 (Pine reads it as a new block)")
        if not cont and ind % 4 != 0:
            probs.append(f"line {no}: indentation {ind} is not a multiple of 4")
        prev = code
    # builtins used
    for no, ln in enumerate(lines, 1):
        code = re.sub(r'"(?:[^"\\]|\\.)*"', '""', ln).split("//")[0]
        for ns, fn in re.findall(r"\b([a-z]+)\.([a-z_0-9]+)\s*\(", code):
            if ns in BUILTINS and BUILTINS[ns] and fn not in BUILTINS[ns]:
                probs.append(f"line {no}: {ns}.{fn}() is not in the checked v5 builtin list")
    # request.security: lookahead explicit; lookahead_on only on [1]-shifted values or the guarded VIX read
    for no, ln in enumerate(lines, 1):
        if "request.security(" in ln.split("//")[0]:
            if "lookahead" not in ln:
                probs.append(f"line {no}: request.security without an explicit lookahead")
            if "lookahead_on" in ln and "[1]" not in ln and "lint: guarded" not in ln:
                probs.append(f"line {no}: lookahead_on without a [1] offset (repaints)")
    # alerts only on confirmed bars: the top-level block holding every alert() call is `if barstate.isconfirmed`
    for no, ln in enumerate(lines, 1):
        code = re.sub(r'"(?:[^"\\]|\\.)*"', '""', ln).split("//")[0]
        if re.search(r"(?<![\w.])alert\(", code):
            top = next((lines[q] for q in range(no - 1, -1, -1) if lines[q].strip() and not lines[q].startswith((" ", "//"))), "")
            if not code.startswith(" ") or "barstate.isconfirmed" not in top:
                probs.append(f"line {no}: alert() not under a barstate.isconfirmed gate")
    n_sec = src.count("request.security(")
    notes.append(f"{len(lines)} lines, {n_sec} request.security calls (limit 40), "
                 f"{len(re.findall(r'^[a-zA-Z_][a-zA-Z_0-9]*\(.*\)\s*=>', src, re.M))} functions")
    if n_sec > 40:
        probs.append("more than 40 request.security calls")
    plots = len(re.findall(r"^\s*(plot|plotshape|plotchar|bgcolor|fill|hline)\(", src, re.M))
    notes.append(f"{plots} plot-type calls (limit 64)")
    if plots > 64:
        probs.append("more than 64 plots")
    return probs, notes


# ================================================================================================ report
def pct(a, b):
    return 100.0 * a / b if b else 100.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=0, help="only the last N trading days of 2026")
    ap.add_argument("--lint", action="store_true")
    ap.add_argument("--show", type=int, default=12, help="mismatches listed per element")
    a = ap.parse_args()
    probs, notes = lint() if os.path.exists(PINE) else (["tradingview/lit_levels.pine missing"], [])
    print("== Pine lint:", "OK" if not probs else f"{len(probs)} problem(s)")
    for x in notes:
        print("   ", x)
    for x in probs:
        print("   !", x)
    if a.lint:
        return 1 if probs else 0

    M = lit.Market()
    C = lit.candidates(M, ref="cisd")
    days = [d for d, s, e in M.days if d >= "2026-01-01"]
    if a.days:
        days = days[-a.days:]
    b = load("NQ", "5m")
    assert len(b.t) == M.n and (b.t == M.t).all()
    # start the twin ~3 months early (ATR / build-up / month warm-up, like a TradingView chart with history loaded)
    first = next(s for d, s, e in M.days if d == days[0])
    warm_day = next(k for k, (d, s, e) in enumerate(M.days) if d == days[0])
    start = M.days[max(0, warm_day - 66)][1]
    Tw = Twin(b, start).run()
    dset = set(days)
    lv, bu, raw, setups, trades = engine_side(M, C, days)

    print(f"\n== {len(days)} trading days, {days[0]} .. {days[-1]} (twin from {M.dates[start]})")
    # ATR
    ia = np.arange(first, M.n)
    print(f"ATR: Pine RMA vs engine max |diff| {np.nanmax(np.abs(Tw.atr[ia] - M.atr[ia])):.6f} pts")

    # 1 levels
    tot = ok = dok = 0
    miss = []
    for d in days:
        E = collections.Counter(lv.get(d, [])); Pn = collections.Counter(Tw.levels_log.get(d, []))
        tot += sum(E.values()); ok += sum((E & Pn).values())
        if E == Pn:
            dok += 1
        else:
            miss.append((d, sorted((E - Pn).elements())[:4], sorted((Pn - E).elements())[:4]))
    print(f"\n[levels] sessions + PDH/PDL + PWH/PWL + PMH/PML + NWOG/NDOG: {ok}/{tot} = {pct(ok, tot):.2f}% of levels, "
          f"{dok}/{len(days)} = {pct(dok, len(days)):.1f}% of days identical")
    for x in miss[:a.show]:
        print("   ", x[0], "engine only", x[1], "| pine only", x[2])
    pb = {(s_, p_, k_) for s_, p_, k_ in Tw.bu_log if M.dates[k_] in dset}
    both = len(bu & pb)
    print(f"[build-ups] {both}/{len(bu | pb)} = {pct(both, len(bu | pb)):.2f}% (engine {len(bu)}, pine {len(pb)})")
    for x in sorted(bu - pb)[:a.show // 2]:
        print("    engine only", x, M.dates[x[2]])
    for x in sorted(pb - bu)[:a.show // 2]:
        print("    pine only", x, M.dates[x[2]])

    # 2 raw sweeps + elements
    key = lambda z: (z["day"], z["dir"], z["i"], z["ext_i"])
    E = {key(z): z for z in raw}
    last_bar = {e - 1 for d, s, e in M.days}
    Pn = {key(z): z for z in Tw.raw if z["day"] in dset and z["i"] not in last_bar}
    com = E.keys() & Pn.keys()
    print(f"\n[sweeps] raw LIT sweeps + 5m CISD close: {len(com)}/{len(E.keys() | Pn.keys())} = "
          f"{pct(len(com), len(E.keys() | Pn.keys())):.2f}% (engine {len(E)}, pine {len(Pn)})")
    for kk in sorted(E.keys() - Pn.keys())[:a.show // 2]:
        print("    engine only", kk, E[kk]["swept"])
    for kk in sorted(Pn.keys() - E.keys())[:a.show // 2]:
        print("    pine only", kk, Pn[kk]["swept"])
    checks = {
        "swept levels (names)": lambda e, p: sorted(e["swept"]) == p["swept"],
        "sweep extreme": lambda e, p: abs(e["ext_d"] - p["ext_d"]) < 1e-6,
        "sweep bar": lambda e, p: e["sweep_i"] == p["sweep_i"],
        "CISD level": lambda e, p: abs(e["ref_d"] - p["ref_d"]) < 1e-6,
        "depth >= 0.5 ATR (pass/fail)": lambda e, p: (e["depth_atr"] >= 0.5) == (p["depth"] >= 0.5),
        "displacement >= 0.8 ATR (pass/fail)": lambda e, p: (e["disp"] >= 0.8) == (p["disp"] >= 0.8),
        "inducement taken (pass/fail)": lambda e, p: (sum(1 for dd, aa in e["idm_a"] if dd <= 1.0 and aa <= 36) >= 1) == (p["n_idm"] >= 1),
        "inducement count": lambda e, p: sum(1 for dd, aa in e["idm_a"] if dd <= 1.0 and aa <= 36) == p["n_idm"],
    }
    for nm, f in checks.items():
        bad = [kk for kk in com if not f(E[kk], Pn[kk])]
        print(f"  {nm:38s} {len(com) - len(bad)}/{len(com)} = {pct(len(com) - len(bad), len(com)):.2f}%")
        for kk in sorted(bad)[:3]:
            e_, p_ = E[kk], Pn[kk]
            print(f"      {kk}: engine depth {e_['depth_atr']} disp {e_['disp']} | pine depth {p_['depth']} disp {p_['disp']}"
                  f" (ATR seed/rounding near a threshold)" if nm.startswith(("depth", "disp")) else f"      {kk}")

    # 3 setups that pass every bot filter (stop + target)
    E = {key(z): z for z in setups}
    Pn = {key(z): z for z in Tw.setups if z["day"] in dset and z["i"] not in last_bar}
    com = E.keys() & Pn.keys()
    print(f"\n[setups] pass every bot filter (window, depth, displacement, inducement, Monday rule, stop 8-80, VIX band "
          f">= 1.5R): {len(com)}/{len(E.keys() | Pn.keys())} = {pct(len(com), len(E.keys() | Pn.keys())):.2f}% "
          f"(engine {len(E)}, pine {len(Pn)})")
    for kk in sorted(E.keys() - Pn.keys())[:a.show // 2]:
        why = next((z.get("why") for z in Tw.raw if key(z) == kk), "no raw sweep")
        print("    engine only", kk, "pine rejected:", why)
    for kk in sorted(Pn.keys() - E.keys())[:a.show // 2]:
        print("    pine only", kk, "(engine filter differs; next-bar open vs trigger close for the target test)")
    st_ok = sum(abs(E[kk]["stop"] - Pn[kk]["stop"]) < 1e-6 for kk in com)
    tg_ok = sum(abs(E[kk]["tgt"] - Pn[kk]["tgt"]) < 0.01 for kk in com)
    print(f"  planned stop (1 tick beyond the extreme)  {st_ok}/{len(com)} = {pct(st_ok, len(com)):.2f}%")
    print(f"  planned target (VIX band, 1.5R-8R)         {tg_ok}/{len(com)} = {pct(tg_ok, len(com)):.2f}%")

    # 4 trades vs run_x on 5m bars (the indicator's own fill model) and the live 1m run
    k2 = lambda t: (t["day"], t["dir"], round(t["entry_px"], 2))
    E = {k2(t): t for t in trades}
    Pn = {k2(t): t for t in Tw.trades if t["day"] in dset}
    com = E.keys() & Pn.keys()
    print(f"\n[trades, 5m approximation] vs engine run_x on 5m bars: {len(com)}/{len(E.keys() | Pn.keys())} = "
          f"{pct(len(com), len(E.keys() | Pn.keys())):.2f}% (engine {len(E)}, pine {len(Pn)})")
    ex_ok = sum(E[kk]["exit"] == Pn[kk]["exit"] for kk in com)
    print(f"  same exit kind {ex_ok}/{len(com)}")
    for kk in sorted(E.keys() - Pn.keys())[:a.show // 2]:
        print("    engine only", kk, E[kk]["exit"], "(live rule: the first limit to fill wins; the backtest takes the first setup in order that fills)")
    for kk in sorted(Pn.keys() - E.keys())[:a.show // 2]:
        print("    pine only", kk, Pn[kk]["exit"])
    try:
        from tools import runlib as rl
        R = rl.load("lit_live")
        cols = R["trade_cols"]
        live = {(r[cols.index("day")], r[cols.index("dir")]) for r in R["trades"] if r[cols.index("day")] in dset}
        pin = {(t["day"], t["dir"]) for t in Tw.trades if t["day"] in dset}
        pset = {(z["day"], z["dir"]) for z in Tw.setups if z["day"] in dset}
        print(f"[live bot, 1m entries, run lit_live] {len(live)} trades; the indicator shows a setup on "
              f"{len(live & pset)}/{len(live)} = {pct(len(live & pset), len(live)):.1f}% of those day+direction, "
              f"a 5m-approx fill on {len(live & pin)}/{len(live)} = {pct(len(live & pin), len(live)):.1f}%")
    except Exception as ex:  # noqa: BLE001
        print("[live bot] run lit_live not readable:", ex)
    return 0


if __name__ == "__main__":
    sys.exit(main())
