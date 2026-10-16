"""
Multi-timeframe context: FVG respect/disrespect bias per timeframe, HTF PD arrays (FVGs + inversions),
and higher-timeframe bar construction with explicit close times (no lookahead).

Bias logic (Blake-style "FVG respect"):
  * a bullish FVG that price trades into and closes back above      -> respected  -> bullish order flow
  * a bullish FVG that price closes through (below its bottom)      -> disrespected/inverted -> bearish order flow
  * mirror for bearish FVGs.
  The most recent respect/disrespect event on a timeframe sets that timeframe's bias; it fades to neutral
  after `stale_bars` bars without a new event.
"""
from __future__ import annotations

import numpy as np

from .data import Bars


class HTFBars:
    """Bars with explicit close times so a consumer only sees fully closed bars."""

    def __init__(self, tf, t_open, t_close, o, h, l, c):
        self.tf = tf
        self.t, self.tc = np.asarray(t_open), np.asarray(t_close)
        self.o, self.h, self.l, self.c = map(np.asarray, (o, h, l, c))

    def __len__(self):
        return len(self.t)


def from_bars(b: Bars, secs: int) -> HTFBars:
    return HTFBars(b.tf, b.t, b.t + secs, b.o, b.h, b.l, b.c)


def build_4h(h1: Bars) -> HTFBars:
    off = 22 * 3600  # anchor buckets to the 18:00 ET Globex open (EDT)
    bucket = (h1.t - off) // 14400 * 14400 + off
    return _group(h1, bucket, lambda k, idx: k + 14400, "4h")


def build_1d(h1: Bars) -> HTFBars:
    return _group(h1, h1.tday, lambda k, idx: int(h1.t[idx[-1]]) + 3600, "1d")


def _group(b, keys, close_fn, tf):
    t0, tc, o, h, l, c = [], [], [], [], [], []
    start = 0
    n = len(keys)
    for i in range(1, n + 1):
        if i == n or keys[i] != keys[start]:
            idx = np.arange(start, i)
            t0.append(int(b.t[start])); tc.append(int(close_fn(int(keys[start]), idx)))
            o.append(b.o[start]); h.append(b.h[start:i].max()); l.append(b.l[start:i].min()); c.append(b.c[i - 1])
            start = i
    return HTFBars(tf, t0, tc, o, h, l, c)


class FVGTracker:
    """Tracks fair value gaps on one timeframe and derives respect/disrespect order flow."""

    def __init__(self, tf: str, min_size: float, max_age: int = 60, stale_bars: int = 40):
        self.tf = tf
        self.min_size = min_size
        self.max_age = max_age
        self.stale_bars = stale_bars
        self.h, self.l, self.c, self.t, self.tc = [], [], [], [], []
        self.active = []        # dicts: dir, top, bot, k, t0, state(fresh|tested|inverted), inv_t
        self.log = []           # finished/expired gaps for charting
        self.bias = 0
        self.last_event_k = -10**9
        self.last_event = None

    def add(self, t, tc, h, l, c):
        self.t.append(t); self.tc.append(tc); self.h.append(h); self.l.append(l); self.c.append(c)
        k = len(self.h) - 1
        events = []
        keep = []
        for g in self.active:
            if k - g["k"] > self.max_age:
                g["t1"] = tc
                self.log.append(g)
                continue
            if g["state"] != "inverted":
                if g["dir"] == 1:
                    if c < g["bot"]:                      # closed through a bullish gap -> disrespect, inverts to resistance
                        g["state"], g["inv_t"] = "inverted", tc
                        events.append((-1, "disrespected bullish", g))
                    elif l <= g["top"] and c >= g["bot"] and g["state"] == "fresh":
                        g["state"] = "tested"
                        events.append((1, "respected bullish", g))
                else:
                    if c > g["top"]:
                        g["state"], g["inv_t"] = "inverted", tc
                        events.append((1, "disrespected bearish", g))
                    elif h >= g["bot"] and c <= g["top"] and g["state"] == "fresh":
                        g["state"] = "tested"
                        events.append((-1, "respected bearish", g))
            else:
                # an inverted gap that price closes back through is spent
                if (g["dir"] == 1 and c > g["top"]) or (g["dir"] == -1 and c < g["bot"]):
                    g["t1"] = tc
                    self.log.append(g)
                    continue
            keep.append(g)
        self.active = keep
        if k >= 2:
            if self.l[k] - self.h[k - 2] >= self.min_size:
                self.active.append({"dir": 1, "top": self.l[k], "bot": self.h[k - 2], "k": k, "t0": self.t[k - 2],
                                    "tf": self.tf, "state": "fresh", "inv_t": None, "t1": None})
            elif self.l[k - 2] - self.h[k] >= self.min_size:
                self.active.append({"dir": -1, "top": self.l[k - 2], "bot": self.h[k], "k": k, "t0": self.t[k - 2],
                                    "tf": self.tf, "state": "fresh", "inv_t": None, "t1": None})
        if events:
            d, txt, g = events[-1]
            self.bias = d
            self.last_event_k = k
            self.last_event = txt
        elif k - self.last_event_k > self.stale_bars:
            self.bias = 0
        return events

    def zones(self, d):
        """PD arrays that support a trade in direction d: fresh/tested gaps of d, inverted gaps of -d."""
        out = []
        for g in self.active:
            if (g["dir"] == d and g["state"] != "inverted") or (g["dir"] == -d and g["state"] == "inverted"):
                out.append(g)
        return out

    def records(self):
        allg = self.log + self.active
        return [{"tf": g["tf"], "dir": g["dir"], "top": float(g["top"]), "bot": float(g["bot"]), "t0": int(g["t0"]),
                 "t1": None if g["t1"] is None else int(g["t1"]), "inv_t": None if g["inv_t"] is None else int(g["inv_t"])}
                for g in allg]


class MTF:
    """Feeds 1D / 4H / 1H / 15m bars into FVG trackers as they close."""

    def __init__(self, h1: Bars, m15: HTFBars, min_fvg_base: float):
        self.series = {
            "1D": build_1d(h1),
            "4H": build_4h(h1),
            "1H": from_bars(h1, 3600),
            "15m": m15,
        }
        mult = {"1D": 8.0, "4H": 4.0, "1H": 2.5, "15m": 1.5}
        self.trk = {tf: FVGTracker(tf, min_fvg_base * mult[tf], max_age={"1D": 30, "4H": 40, "1H": 60, "15m": 80}[tf],
                                   stale_bars={"1D": 10, "4H": 18, "1H": 30, "15m": 40}[tf]) for tf in self.series}
        self.ptr = {tf: 0 for tf in self.series}
        self.events = []

    def advance(self, t_now: int, record_from: int):
        for tf, s in self.series.items():
            k = self.ptr[tf]
            while k < len(s) and s.tc[k] <= t_now:
                ev = self.trk[tf].add(int(s.t[k]), int(s.tc[k]), float(s.h[k]), float(s.l[k]), float(s.c[k]))
                if ev and s.tc[k] >= record_from and tf != "15m":
                    d, txt, g = ev[-1]
                    self.events.append({"t": int(s.tc[k]), "tf": tf, "dir": d, "text": f"{tf} {txt} FVG {g['bot']:.2f}-{g['top']:.2f}"})
                k += 1
            self.ptr[tf] = k

    def bias(self):
        return {tf: tr.bias for tf, tr in self.trk.items()}

    def keylevel(self, d, price, tol):
        """Return the highest-TF PD array (FVG / inverted FVG supporting direction d) that `price` traded into."""
        for tf in ("1D", "4H", "1H"):
            for g in self.trk[tf].zones(d):
                if g["bot"] - tol <= price <= g["top"] + tol:
                    return f"{tf} {'IFVG' if g['state'] == 'inverted' else 'FVG'}"
        return None

    def records(self):
        out = []
        for tf in ("1D", "4H", "1H"):
            out.extend(self.trk[tf].records())
        return out
