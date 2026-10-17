"""VWAP and volume profile as confluence for the live Liquidity Engine (post-hoc on the exact live-loop replay).

  python tools/research_vp.py check      # feature sanity: engine cross-checks + a no-look-ahead truncation test
  python tools/research_vp.py info       # with / without split of every idea: 2021-25 (decides) and 2026 (untouched)
  python tools/research_vp.py all        # check + info + every sized variant -> research/runs/vp_*.json, vwap_*.json

No engine replays: the 768 baseline trades come from runlib.replay() (cached) and only their SIZE is changed
(runlib.size(raw, rule=...)), which is exact because P&L, commission and slippage are linear in micros. A skip (size 0)
only approximates an engine filter: the engine could have taken a later setup that day instead (max 1 trade a day).

Features are computed from data/NQ_5m.csv (TradingView CME NQ1!, back-adjusted, with volume) at the decision time: the
close of the signal bar (signal_t + 5 min = entry_t), i.e. only bars that closed before the entry bar opened. The engine
prices its plan at that close too (entry = signal close; the fill is the next open).

Volume profile approximation: 5m bars only, so each bar's volume is spread evenly over every tick (0.25 pt) between its
low and high. POC / value area (70%, expanded from the POC one row at a time, as engine/model.volume_profile does) are
read from 5-point rows of that tick histogram. Profiles are RTH only (09:30-16:00 ET). Naked POC = a prior RTH POC
(last 10 sessions) that no bar has traded through since that session's 16:00 close.
"""
from __future__ import annotations

import collections
import json
import math
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import runlib as rl  # noqa: E402

TICK = 0.25
ROW = 20                 # profile row = 20 ticks = 5 pts (engine profile_bin for NQ)
VA = 0.70
NAKED_DAYS = 10
COMP_DAYS = 5
WRITEUP = "vwap-volume-profile.md"


# ------------------------------------------------------------------------------------------------ bars
_CSV = {}


def _csv():
    if not _CSV:
        df = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
        ts = pd.to_datetime(df["time"].values.astype(np.int64), unit="s", utc=True).tz_convert("America/New_York")
        _CSV["df"] = df
        _CSV["mod"] = (ts.hour * 60 + ts.minute).values.astype(np.int32)
        _CSV["date"] = np.asarray((ts + pd.Timedelta(hours=6)).strftime("%Y-%m-%d"))   # trading day 18:00 -> 17:00 ET
    return _CSV


class Bars:
    def __init__(self, upto=None):
        X = _csv()
        df = X["df"] if upto is None else X["df"].iloc[:upto]
        self.t = df["time"].values.astype(np.int64)
        self.o, self.h, self.l, self.c = (df[k].values.astype(float) for k in ("open", "high", "low", "close"))
        v = df["volume"].values.astype(float)
        self.v = np.where(v > 0, v, 1.0)                     # engine: zero-volume bars count as 1
        self.mod = X["mod"][:len(self.t)]
        self.date = X["date"][:len(self.t)]
        n = len(self.t)
        new = np.r_[True, self.date[1:] != self.date[:-1]]
        self.starts = np.flatnonzero(new)
        self.ends = np.r_[self.starts[1:], n]
        self.did = np.cumsum(new) - 1                       # day index per bar
        self.days = self.date[self.starts]
        self.rth = (self.mod >= 570) & (self.mod < 960)
        tp = (self.h + self.l + self.c) / 3
        self.tp = tp
        # cumulative sums per day: ETH (from 18:00) and RTH (from 09:30), for VWAP and its standard deviation
        self.eth = self._cum(tp, np.ones(n, bool))
        self.rthv = self._cum(tp, self.rth)
        tr = np.maximum(self.h, np.r_[self.c[0], self.c[:-1]]) - np.minimum(self.l, np.r_[self.c[0], self.c[:-1]])
        cs = np.r_[0.0, np.cumsum(tr)]
        k0 = np.maximum(0, np.arange(n) - 14)
        self.atr = (cs[np.arange(n) + 1] - cs[k0]) / (np.arange(n) + 1 - k0)   # engine feature ATR: mean TR of 15 bars
        self.prof = {}                                      # day index -> RTH profile
        for k, (a, z) in enumerate(zip(self.starts, self.ends)):
            m = self.rth[a:z]
            if m.sum() < 6:
                continue
            idx = np.flatnonzero(m) + a
            lo, hist = tick_hist(self.h[idx], self.l[idx], self.v[idx])
            self.prof[k] = {"lo": lo, "hist": hist, "last": int(idx[-1]), **value_area(lo, hist)}

    def _cum(self, x, mask):
        w = np.where(mask, self.v, 0.0)
        out = []
        for arr in (w, w * x, w * x * x):
            cs = np.cumsum(arr)
            base = np.r_[0.0, cs][self.starts][self.did]
            out.append(cs - base)
        return out                                          # S(v), S(v tp), S(v tp^2) since the day / RTH start

    def vwap(self, i, which="rth"):
        s0, s1, s2 = (self.rthv if which == "rth" else self.eth)
        if s0[i] <= 0:
            return None, None
        vw = s1[i] / s0[i]
        sd = math.sqrt(max(s2[i] / s0[i] - vw * vw, 0.0))
        return vw, sd

    def idx(self, t):
        i = int(np.searchsorted(self.t, t))
        return i if i < len(self.t) and self.t[i] == t else None


def tick_hist(h, l, v):
    """Volume spread evenly over every tick of each bar's range (5m bars only: an approximation of the real profile)."""
    lt = np.round(l / TICK).astype(np.int64)
    ht = np.round(h / TICK).astype(np.int64)
    lo = int(lt.min()); n = int(ht.max()) - lo + 1
    diff = np.zeros(n + 1)
    w = v / (ht - lt + 1)
    np.add.at(diff, lt - lo, w)
    np.add.at(diff, ht - lo + 1, -w)
    return lo, np.cumsum(diff)[:n]


def value_area(lo, hist, row=ROW, va=VA):
    """POC / VAH / VAL from rows of `row` ticks anchored on absolute multiples (same expansion as engine volume_profile)."""
    r0 = (lo // row) * row
    off = lo - r0
    nr = int(math.ceil((off + len(hist)) / row))
    pad = np.zeros(nr * row)
    pad[off:off + len(hist)] = hist
    rows = pad.reshape(nr, row).sum(1)
    p = int(np.argmax(rows))
    tot, acc, a, b = rows.sum(), rows[p], p, p
    while acc < va * tot and (a > 0 or b < nr - 1):
        up = rows[b + 1] if b < nr - 1 else -1
        dn = rows[a - 1] if a > 0 else -1
        if up >= dn:
            b += 1; acc += up
        else:
            a -= 1; acc += dn
    return {"poc": (r0 + p * row + row / 2) * TICK, "vah": (r0 + (b + 1) * row) * TICK, "val": (r0 + a * row) * TICK}


def composite(profs):
    lo = min(p["lo"] for p in profs)
    hi = max(p["lo"] + len(p["hist"]) for p in profs)
    out = np.zeros(hi - lo)
    for p in profs:
        out[p["lo"] - lo:p["lo"] - lo + len(p["hist"])] += p["hist"]
    return lo, out


# ------------------------------------------------------------------------------------------------ features per trade
def trade_features(B: Bars, t: dict) -> dict | None:
    i = B.idx(int(t["signal_t"]))
    if i is None:
        return None
    d = int(t["dir"]); c = float(B.c[i]); ext = float(t["sweep_ext"]); tgt = float(t["target"])
    k = int(B.did[i])
    F = {"i": i}
    # --- session VWAPs (RTH from 09:30 = the engine's; ETH from 18:00) and their 1-SD bands
    vw, sd = B.vwap(i, "rth")
    F["rth_vwap"], F["rth_sd"] = vw, sd
    n_rth = int(B.rth[B.starts[k]:i + 1].sum())
    F["z_rth"] = None if vw is None or not sd or n_rth < 6 else (c - vw) / sd * d   # bands only from 10:00 (6 RTH bars)
    F["vwap_side"] = None if vw is None else int((vw - c) * d > 0)
    ve, se = B.vwap(i, "eth")
    F["z_eth"] = None if not se else (c - ve) / se * d
    F["vwap_eth_side"] = int((ve - c) * d > 0)
    F["vwap_atr"] = None if vw is None else (c - vw) / B.atr[i] * d
    # --- the sweep extreme bar (latest bar at/before the signal that printed the extreme) and the leg origin
    lo_i = max(B.starts[k] - 1, i - 60)
    seg = B.l[lo_i:i + 1] if d == 1 else B.h[lo_i:i + 1]
    hit = np.flatnonzero(np.abs(seg - ext) < 1e-6)
    e = int(lo_i + hit[-1]) if len(hit) else int(lo_i + (np.argmin(seg) if d == 1 else np.argmax(seg)))
    F["ext_i"] = e
    ve_x, se_x = B.vwap(e, "eth")
    F["ext_z_eth"] = None if not se_x else (ext - ve_x) / se_x * d               # < 0: swept below the ETH VWAP (long)
    o0 = max(0, e - 24)
    o = int(o0 + (np.argmax(B.h[o0:e + 1]) if d == 1 else np.argmin(B.l[o0:e + 1])))   # leg origin (<= 120 min back)
    w = B.v[o:i + 1]
    F["avwap_leg"] = float((B.tp[o:i + 1] * w).sum() / w.sum())
    F["leg_reclaim"] = int((c - F["avwap_leg"]) * d > 0)                    # closed back beyond the leg's average price
    w = B.v[e:i + 1]
    F["avwap_ext"] = float((B.tp[e:i + 1] * w).sum() / w.sum())
    F["ext_late_r"] = (c - F["avwap_ext"]) * d / float(t["risk_pts"])        # how far past the post-sweep average price
    # --- prior RTH profile (yesterday), naked POCs, prior-week composite, last-5-session composite
    prior = [j for j in range(k - 1, max(-1, k - 1 - 15), -1) if j in B.prof]
    if not prior:
        return F
    P = B.prof[prior[0]]
    F.update({"poc": P["poc"], "vah": P["vah"], "val": P["val"]})
    edge_against = P["val"] if d == 1 else P["vah"]                          # the value edge the sweep ran through
    a0 = B.starts[k]
    m_rth = np.flatnonzero(B.rth[a0:i + 1])
    if len(m_rth):
        o_rth = float(B.o[a0 + m_rth[0]])
        for va in (0.6, 0.7, 0.8):
            x = value_area(P["lo"], P["hist"], va=va)
            F[f"open_in_{int(va * 100)}"] = int(x["val"] <= o_rth <= x["vah"])
    F["sweep_out_value"] = int((edge_against - ext) * d > 0)                 # long: extreme below VAL
    F["in_prior_value"] = int(P["val"] <= c <= P["vah"])
    F["fail_auction"] = int(F["sweep_out_value"] and (c - edge_against) * d > 0)   # looked below value and closed back in
    F["poc_side"] = int((P["poc"] - c) * d > 0)                              # long below the prior POC
    naked = []
    for j in prior[:NAKED_DAYS]:
        q = B.prof[j]
        a = q["last"] + 1
        if a > i:
            continue
        if not (B.l[a:i + 1].min() <= q["poc"] <= B.h[a:i + 1].max()):
            naked.append(q["poc"])
    F["naked"] = naked
    levels = [P["poc"], P["vah"], P["val"]] + naked
    F["levels"] = levels
    F["dist_ext_level"] = min(abs(x - ext) for x in levels)
    F["dist_tgt_level"] = min(abs(x - tgt) for x in levels)
    lo_p, hi_p = sorted((c, tgt))
    F["naked_between"] = int(any(lo_p < x < hi_p for x in naked))
    F["poc_between"] = int(lo_p < P["poc"] < hi_p)
    # prior calendar week composite (RTH), its value area
    wk = lambda s: pd.Timestamp(s).isocalendar()[:2]
    cur = wk(B.days[k])
    pw = [j for j in prior if wk(B.days[j]) != cur]
    if pw:
        wkey = wk(B.days[pw[0]])
        pw = [j for j in pw if wk(B.days[j]) == wkey]
        lo_w, h_w = composite([B.prof[j] for j in pw])
        W = value_area(lo_w, h_w)
        F["sweep_out_week_value"] = int(((W["val"] if d == 1 else W["vah"]) - ext) * d > 0)
        F["in_week_value"] = int(W["val"] <= c <= W["vah"])
    # path from entry to target through the last-5-session composite: volume per tick along the path vs median
    lo_c, h_c = composite([B.prof[j] for j in prior[:COMP_DAYS]])
    a_t, b_t = int(round(lo_p / TICK)) - lo_c, int(round(hi_p / TICK)) - lo_c
    path = np.array([h_c[x] if 0 <= x < len(h_c) else 0.0 for x in range(a_t, b_t + 1)])
    med = float(np.median(h_c[h_c > 0])) if (h_c > 0).any() else 1.0
    F["path_density"] = float(path.mean() / med) if len(path) else None
    x = int(round(c / TICK)) - lo_c
    F["entry_density"] = float(h_c[x] / med) if 0 <= x < len(h_c) else 0.0
    # developing profile today (from 18:00) up to the signal bar: entry vs the developing POC
    a = B.starts[k]
    lo_d, h_d = tick_hist(B.h[a:i + 1], B.l[a:i + 1], B.v[a:i + 1])
    F["dev_poc"] = value_area(lo_d, h_d)["poc"]
    F["dev_poc_side"] = int((F["dev_poc"] - c) * d > 0)
    return F


def all_features(B=None, raw=None):
    B = B or Bars()
    raw = raw or rl.replay(quiet=True)
    out = {}
    for t in raw["trades"]:
        f = trade_features(B, t)
        if f is not None:
            out[int(t["entry_t"])] = f
    return B, raw, out


# ------------------------------------------------------------------------------------------------ the ideas (booleans)
def _engine_open_loc(t):
    return t.get("open_loc")


# id -> (family, plain question, fn(t, F) -> True/False/None). True = the condition is present.
IDEAS = {
    "vwap_side": ("vwap", "Entry on the value side of the session (09:30) VWAP: long below it, short above it",
                  lambda t, F: F.get("vwap_side")),
    "vwap_eth_side": ("vwap", "Entry on the value side of the overnight-anchored (18:00) VWAP",
                      lambda t, F: F.get("vwap_eth_side")),
    "vwap_chase1": ("vwap", "Entry already more than 1 SD beyond the 18:00 VWAP in the trade's direction (chasing)",
                    lambda t, F: None if F.get("z_eth") is None else F["z_eth"] > 1.0),
    "vwap_deep1": ("vwap", "Entry more than 1 SD on the value side of the 18:00 VWAP (deep discount / premium)",
                   lambda t, F: None if F.get("z_eth") is None else F["z_eth"] < -1.0),
    "vwap_rth_band1": ("vwap", "From 10:00: entry more than 1 SD beyond the 09:30 VWAP in the trade's direction",
                       lambda t, F: None if F.get("z_rth") is None else F["z_rth"] > 1.0),
    "vwap_atr_chase2": ("vwap", "Entry at least 2 ATR past the 09:30 VWAP in the trade's direction (stretched away from value)",
                        lambda t, F: None if F.get("vwap_atr") is None else F["vwap_atr"] >= 2.0),
    "vwap_atr_deep2": ("vwap", "Entry at least 2 ATR on the value side of the 09:30 VWAP",
                       lambda t, F: None if F.get("vwap_atr") is None else F["vwap_atr"] <= -2.0),
    "vwap_ext_late": ("vwap", "Late entry: more than 0.5R past the VWAP anchored at the sweep extreme",
                      lambda t, F: None if F.get("ext_late_r") is None else F["ext_late_r"] > 0.5),
    "vwap_sweep2": ("vwap", "The sweep extreme reached the 2-SD band of the 18:00 VWAP (stretched raid)",
                    lambda t, F: None if F.get("ext_z_eth") is None else F["ext_z_eth"] < -2.0),
    "vwap_leg": ("vwap", "Entry back beyond the VWAP anchored at the start of the sweep leg (leg's average price reclaimed)",
                 lambda t, F: F.get("leg_reclaim")),
    "vp_sweep_out": ("vp", "The sweep ran outside yesterday's value area (long: below VAL; short: above VAH)",
                     lambda t, F: F.get("sweep_out_value")),
    "vp_fail_auction": ("vp", "Failed auction: swept outside yesterday's value and the trigger closed back inside it",
                        lambda t, F: F.get("fail_auction")),
    "vp_in_value": ("vp", "Entry inside yesterday's value area (VAL..VAH)", lambda t, F: F.get("in_prior_value")),
    "vp_open_in": ("vp", "Day opened (09:30) inside yesterday's value area (balance day)",
                   lambda t, F: None if not t.get("open_loc") else t["open_loc"] == "inside"),
    "vp_open_with": ("vp", "Day opened outside value in the trade's direction (long after an open above VAH)",
                     lambda t, F: None if not t.get("open_loc") else t["open_loc"] == ("above" if t["dir"] == 1 else "below")),
    "vp_open_against": ("vp", "Day opened outside value against the trade (long after an open below VAL: back toward value)",
                        lambda t, F: None if not t.get("open_loc") else t["open_loc"] == ("below" if t["dir"] == 1 else "above")),
    "vp_poc_side": ("vp", "Entry on the value side of yesterday's POC (long below it, short above it)",
                    lambda t, F: F.get("poc_side")),
    "vp_sweep_level5": ("vp", "The sweep extreme was within 5 pts of a volume level (yesterday's POC/VAH/VAL or a naked POC)",
                        lambda t, F: None if F.get("dist_ext_level") is None else F["dist_ext_level"] <= 5.0),
    "vp_target_level5": ("vp", "The target sits within 5 pts of a volume level (yesterday's POC/VAH/VAL or a naked POC)",
                         lambda t, F: None if F.get("dist_tgt_level") is None else F["dist_tgt_level"] <= 5.0),
    "vp_naked_between": ("vp", "A naked POC lies between the entry and the target (a magnet on the way)",
                         lambda t, F: F.get("naked_between")),
    "vp_poc_between": ("vp", "Yesterday's POC lies between the entry and the target (a high-volume shelf on the way)",
                       lambda t, F: F.get("poc_between")),
    "vp_thin_path": ("vp", "Thin path: the last 5 sessions traded little volume between entry and target (< 0.7x median)",
                     lambda t, F: None if F.get("path_density") is None else F["path_density"] < 0.7),
    "vp_week_sweep_out": ("vp", "The sweep ran outside last week's value area", lambda t, F: F.get("sweep_out_week_value")),
    "vp_dev_poc_side": ("vp", "Entry on the value side of today's developing POC (from 18:00)",
                        lambda t, F: F.get("dev_poc_side")),
}

# plain wording of each side: (condition present, condition absent)
SIDES = {
    "vwap_side": ("entry on the value side of the 09:30 VWAP", "entry on the expensive side of the 09:30 VWAP"),
    "vwap_eth_side": ("entry on the value side of the 18:00 VWAP", "entry on the expensive side of the 18:00 VWAP"),
    "vwap_chase1": ("entry more than 1 SD past the 18:00 VWAP (chasing)", "entry not more than 1 SD past the 18:00 VWAP"),
    "vwap_deep1": ("entry more than 1 SD on the value side of the 18:00 VWAP", "entry not deep on the value side of the 18:00 VWAP"),
    "vwap_rth_band1": ("entry more than 1 SD past the 09:30 VWAP (from 10:00)", "entry within 1 SD of the 09:30 VWAP (from 10:00)"),
    "vwap_atr_chase2": ("entry 2+ ATR past the 09:30 VWAP", "entry less than 2 ATR past the 09:30 VWAP"),
    "vwap_atr_deep2": ("entry 2+ ATR on the value side of the 09:30 VWAP", "entry not 2 ATR on the value side of the 09:30 VWAP"),
    "vwap_ext_late": ("entry more than 0.5R past the sweep-anchored VWAP (late)", "entry within 0.5R of the sweep-anchored VWAP"),
    "vwap_sweep2": ("the sweep stretched to the 2-SD band of the 18:00 VWAP", "the sweep stayed inside the 2-SD band of the 18:00 VWAP"),
    "vwap_leg": ("entry back beyond the sweep leg's anchored VWAP", "entry still short of the sweep leg's anchored VWAP"),
    "vp_sweep_out": ("the sweep ran outside yesterday's value area", "the sweep stayed inside yesterday's value area"),
    "vp_fail_auction": ("a failed auction (swept outside value, closed back in)", "no failed auction"),
    "vp_in_value": ("entry inside yesterday's value area", "entry outside yesterday's value area"),
    "vp_open_in": ("the day opened inside yesterday's value", "the day opened outside yesterday's value"),
    "vp_open_with": ("the day opened outside value in the trade's direction", "the day did not open outside value in the trade's direction"),
    "vp_open_against": ("the day opened outside value against the trade", "the day did not open outside value against the trade"),
    "vp_poc_side": ("entry on the value side of yesterday's POC", "entry on the expensive side of yesterday's POC"),
    "vp_sweep_level5": ("the sweep extreme was within 5 pts of a volume level", "the sweep extreme was not at a volume level"),
    "vp_target_level5": ("the target sits within 5 pts of a volume level", "the target is not at a volume level"),
    "vp_naked_between": ("a naked POC lies between entry and target", "no naked POC between entry and target"),
    "vp_poc_between": ("yesterday's POC lies between entry and target", "yesterday's POC is not between entry and target"),
    "vp_thin_path": ("little volume traded between entry and target (thin path)", "the path to the target runs through traded volume"),
    "vp_week_sweep_out": ("the sweep ran outside last week's value area", "the sweep stayed inside last week's value area"),
    "vp_dev_poc_side": ("entry on the value side of today's developing POC", "entry on the expensive side of today's developing POC"),
}

# re-checks of earlier claims, sized the way they were claimed (not chosen by this study's 2021-25 rule)
RECHECKS = [
    ("vwap_side", True, "Re-check of the old conviction sizing (x1.33 for value-side entries) and the grade's 'proven' item"),
    ("vp_open_in", False, "Re-check of the confluence lab (2026-10-16): open inside value HURTS on several short test beds"),
    ("vp_open_in", True, "AMT theory as written in the engine: an open inside value is a balance day, so fading the edges "
                         "(our sweep reversals) should work better"),
]

# neighbour sets for the ideas with a threshold (checked only for the finalists chosen on 2021-25)
NEIGHBOURS = {
    "vwap_ext_late": [("vwap_ext_late04", 0.4), ("vwap_ext_late06", 0.6)],
    "vwap_atr_chase2": [("vwap_atr_chase15", 1.5), ("vwap_atr_chase3", 3.0)],
    "vwap_atr_deep2": [("vwap_atr_deep15", 1.5), ("vwap_atr_deep3", 3.0)],
    "vwap_chase1": [("vwap_chase05", 0.5), ("vwap_chase15", 1.5), ("vwap_chase2", 2.0)],
    "vwap_deep1": [("vwap_deep05", 0.5), ("vwap_deep15", 1.5)],
    "vwap_sweep2": [("vwap_sweep15", 1.5), ("vwap_sweep25", 2.5)],
    "vp_sweep_level5": [("vp_sweep_level3", 3.0), ("vp_sweep_level8", 8.0)],
    "vp_target_level5": [("vp_target_level3", 3.0), ("vp_target_level8", 8.0)],
    "vp_thin_path": [("vp_thin_path06", 0.6), ("vp_thin_path08", 0.8), ("vp_thin_path10", 1.0)],
}


def neighbour_fn(base, x):
    if base == "vwap_ext_late":
        return lambda t, F: None if F.get("ext_late_r") is None else F["ext_late_r"] > x
    if base == "vwap_atr_chase2":
        return lambda t, F: None if F.get("vwap_atr") is None else F["vwap_atr"] >= x
    if base == "vwap_atr_deep2":
        return lambda t, F: None if F.get("vwap_atr") is None else F["vwap_atr"] <= -x
    if base == "vwap_chase1":
        return lambda t, F: None if F.get("z_eth") is None else F["z_eth"] > x
    if base == "vwap_deep1":
        return lambda t, F: None if F.get("z_eth") is None else F["z_eth"] < -x
    if base == "vwap_sweep2":
        return lambda t, F: None if F.get("ext_z_eth") is None else F["ext_z_eth"] < -x
    if base == "vp_sweep_level5":
        return lambda t, F: None if F.get("dist_ext_level") is None else F["dist_ext_level"] <= x
    if base == "vp_target_level5":
        return lambda t, F: None if F.get("dist_tgt_level") is None else F["dist_tgt_level"] <= x
    if base == "vp_thin_path":
        return lambda t, F: None if F.get("path_density") is None else F["path_density"] < x
    raise KeyError(base)


def flag(fn, t, FE):
    F = FE.get(int(t["entry_t"]))
    if F is None:
        return None
    v = fn(t, F)
    return None if v is None else bool(v)


# ------------------------------------------------------------------------------------------------ checks
def check(B, raw, FE):
    """Engine cross-checks (our VWAP side vs the engine's checklist; our prior value vs the engine's open location) and a
    no-look-ahead test: recompute the features on bars cut right after the signal bar; they must not change."""
    T = raw["trades"]
    agree = n = 0
    for t in T:
        eng = dict((a, b) for a, b in (t.get("checklist") or [])).get("Entry on the value side of session VWAP")
        F = FE.get(int(t["entry_t"]))
        if eng in (1, -1) and F and F.get("vwap_side") is not None:
            n += 1; agree += (eng == 1) == bool(F["vwap_side"])
    print(f"VWAP side vs engine checklist: {agree}/{n} agree")
    agree = n = 0
    for t in T:
        F = FE.get(int(t["entry_t"]))
        if not F or "vah" not in F or not t.get("open_loc"):
            continue
        k = B.did[F["i"]]
        a = B.starts[k] + int(np.argmax(B.rth[B.starts[k]:B.ends[k]]))
        o = B.o[a]
        mine = "above" if o > F["vah"] else ("below" if o < F["val"] else "inside")
        n += 1; agree += mine == t["open_loc"]
    print(f"Open location vs prior value (engine 5-pt bins vs our tick profile): {agree}/{n} agree")
    rng = np.random.default_rng(7)
    pick = rng.choice(len(T), 20, replace=False)
    bad = 0
    for j in pick:
        t = T[j]
        i = B.idx(int(t["signal_t"]))
        Bc = Bars(upto=i + 1)
        f1, f2 = trade_features(B, t), trade_features(Bc, t)
        for key in set(f1) | set(f2):
            a, b = f1.get(key), f2.get(key)
            same = (a == b) if not isinstance(a, float) else (b is not None and abs(a - b) < 1e-6)
            if not same:
                bad += 1
                print("  look-ahead?", t["day"], key, a, b)
    print(f"No-look-ahead test (features on bars cut at the signal bar, 20 random trades): {'OK' if not bad else bad} differences")


# ------------------------------------------------------------------------------------------------ with / without split
def _pf(p):
    gl = -p[p < 0].sum()
    return round(float(p[p > 0].sum() / gl), 2) if gl > 0 else None


def split(T, fn, FE, span):
    """Avg R, $ (live size) and PF of the trades with / without the condition in one span."""
    a, z = {"2026": ("2026-01-01", "2026-12-31"), "2021-25": ("2021-01-01", "2025-12-31")}[span]
    rows = {True: [], False: []}
    for t in T:
        if a <= t["day"] <= z:
            f = flag(fn, t, FE)
            if f is not None:
                rows[f].append(t)
    out = {}
    for k, R in rows.items():
        r = np.array([t["r"] for t in R]); p = np.array([t["pnl"] for t in R])
        out[k] = {"n": len(R), "avg_r": round(float(r.mean()), 3) if len(R) else None, "net": round(float(p.sum())),
                  "pf": _pf(p) if len(R) else None, "win": round(100 * float((r > 0).mean()), 1) if len(R) else None}
    return out


def info(T, FE, ideas=None):
    ideas = ideas or {k: v[2] for k, v in IDEAS.items()}
    res = {}
    print(f"{'idea':<20}| {'2021-25: with n / avgR / net / PF':<38}| {'without n / avgR / net / PF':<34}|| {'2026: with':<30}| without")
    for name, fn in ideas.items():
        a, b = split(T, fn, FE, "2021-25"), split(T, fn, FE, "2026")
        res[name] = {"2021-25": a, "2026": b}
        f = lambda x: f"{x['n']:>3} {x['avg_r'] if x['avg_r'] is not None else '-':>6} {x['net']:>+7,} {x['pf'] if x['pf'] else '-':>5}"
        print(f"{name:<20}| {f(a[True]):<38}| {f(a[False]):<34}|| {f(b[True]):<30}| {f(b[False])}")
    return res


# ------------------------------------------------------------------------------------------------ selection (2021-25 only)
def select(res, min_dr=0.05, share=(0.05, 0.95)):
    """Pre-registered rule, 2021-25 numbers only: the with/without gap must have the same sign in avg R and in $ per trade,
    be at least min_dr R, and the condition must cover 5-95% of trades. Returns {idea: good_side} (True = present is good)."""
    out = {}
    for name, r in res.items():
        w, wo = r["2021-25"][True], r["2021-25"][False]
        n = w["n"] + wo["n"]
        if not n or not w["n"] or not wo["n"] or not share[0] <= w["n"] / n <= share[1]:
            continue
        dr = w["avg_r"] - wo["avg_r"]
        dd = w["net"] / w["n"] - wo["net"] / wo["n"]
        if abs(dr) >= min_dr and dr * dd > 0:
            out[name] = dr > 0
    return out


def perm_p(T, fn, FE, span="2021-25", n=4000, seed=1):
    """Two-sided permutation p-value of the with-minus-without avg R gap (raw R, one span)."""
    a, z = {"2026": ("2026-01-01", "2026-12-31"), "2021-25": ("2021-01-01", "2025-12-31")}[span]
    R, M = [], []
    for t in T:
        if a <= t["day"] <= z:
            f = flag(fn, t, FE)
            if f is not None:
                R.append(t["r"]); M.append(f)
    R, M = np.array(R), np.array(M)
    obs = R[M].mean() - R[~M].mean()
    rng = np.random.default_rng(seed)
    hits = 0
    for _ in range(n):
        P = rng.permutation(M)
        hits += abs(R[P].mean() - R[~P].mean()) >= abs(obs)
    return round(float(obs), 3), round((hits + 1) / (n + 1), 4)


def years_sign(T, fn, FE, good):
    """Per full year 2022-2025: does the good side beat the other side on avg R? Returns e.g. '3/4' and the gaps."""
    gaps = []
    for y in ("2022", "2023", "2024", "2025"):
        w = [t["r"] for t in T if t["day"][:4] == y and flag(fn, t, FE) is good]
        o = [t["r"] for t in T if t["day"][:4] == y and flag(fn, t, FE) is (not good)]
        gaps.append(round(float(np.mean(w) - np.mean(o)), 2) if w and o else None)
    return f"{sum(1 for g in gaps if g is not None and g > 0)}/4", gaps


# ------------------------------------------------------------------------------------------------ sized variants
KINDS = {
    "half": "x0.5 on the weak side (every trade still taken)",
    "up": "x1.25 on the strong side (every trade still taken)",
    "skip": "skip the weak side (check only: a post-hoc skip approximates an engine filter)",
    "cold": "only in cold streaks: strong-side trades go back to full size, weak side stays at half",
}


def make_rule(fn, FE, good, kind):
    def rule(t, ctx):
        f = flag(fn, t, FE)
        if f is None:
            return 1.0
        strong = f is good
        if kind == "half":
            return 1.0 if strong else 0.5
        if kind.startswith("up"):
            return (1.25 if kind == "up" else int(kind[2:]) / 100) if strong else 1.0
        if kind == "skip":
            return 1.0 if strong else 0.0
        if kind == "cold":
            return 2.0 if (strong and ctx["cold_mult"] < 1) else 1.0
        raise KeyError(kind)
    return rule


def status_of(S, base, kind):
    a, b = S["spans"]["2026"], S["spans"]["2021-25"]
    A, Bs = base["spans"]["2026"], base["spans"]["2021-25"]
    if not a.get("n") or not b.get("n"):
        return "rejected" if kind != "skip" else "info"
    if a["net"] == A["net"] and a["pf"] == A["pf"] and a["n"] == A["n"]:
        return "info"                                   # never changed a 2026 trade: untested out of sample
    freq = all(2 <= (x.get("tpw") or 0) <= 4 for x in (a, b))          # owner's rule: 2-4 trades a week in both periods
    better = lambda x, y: x["net"] > y["net"] and (x["pf"] or 0) > (y["pf"] or 0)
    if rl.passes(S, base) and better(a, A) and better(b, Bs):
        return "adopt-candidate"
    no_harm = lambda x, y: x["net"] >= y["net"] - 250 and (x["pf"] or 0) >= (y["pf"] or 0) - 0.02
    if freq and ((better(a, A) and no_harm(b, Bs)) or (better(b, Bs) and no_harm(a, A))):
        return "promising"
    return "rejected" if kind != "skip" else "info"


def title_of(name, good, kind):
    strong, weak = SIDES[name] if good else SIDES[name][::-1]
    if kind.startswith("up") and kind != "up":
        return f"{int(kind[2:]) / 100:g}x size when {strong}"
    return {"half": f"Half size when {weak}", "up": f"1.25x size when {strong}", "skip": f"Skip when {weak}",
            "cold": f"Cold streak: full size again when {strong}"}[kind]


def verdict_of(S, base, st):
    a, b = S["spans"]["2026"], S["spans"]["2021-25"]
    A, Bs = base["spans"]["2026"], base["spans"]["2021-25"]
    def one(x, y, name):
        if not x.get("n"):
            return f"{name}: no trades left"
        return (f"{name}: PF {y['pf']} -> {x['pf']}, net {y['net']:+,} -> {x['net']:+,}, max DD {y['dd']:,} -> {x['dd']:,}, "
                f"{x['tpw']}/wk")
    head = {"adopt-candidate": "Better in both periods.", "promising": "Helps one period without hurting the other.",
            "rejected": "Does not hold in both periods.",
            "info": ("Never changed a 2026 trade, so it is untested out of sample." if a.get("n") and a["net"] == A["net"]
                     and a["pf"] == A["pf"] else "Check only (post-hoc skip).")}[st]
    return f"{head} {one(a, A, '2026')}; {one(b, Bs, '2021-25')}."


def run_variants(raw, FE, base, plan):
    """plan: list of (id, idea name, fn, good, kind, question). Returns {id: record} (sized trades, scores, status)."""
    out = {}
    for vid, name, fn, good, kind, question in plan:
        T = rl.size(raw, rule=make_rule(fn, FE, good, kind))
        S = rl.score(T, raw)
        st = status_of(S, base, kind)
        out[vid] = {"name": name, "good": good, "kind": kind, "question": question, "T": T, "S": S, "status": st,
                    "verdict": verdict_of(S, base, st)}
        print(f"{vid:<26} {st:<15} 2026 {fmt(S['spans']['2026'])} | 2021-25 {fmt(S['spans']['2021-25'])}", flush=True)
    return out


def by_year(S, base):
    return {y: S["years"][y]["net"] - base["years"][y]["net"] for y in ("2022", "2023", "2024", "2025", "2026")}


def placebo(raw, base, share, m=1.25, n=200, seed=3):
    """How often does a RANDOM subset of the same share of trades, sized m, beat the baseline in both periods?"""
    rng = np.random.default_rng(seed)
    A0, B0 = base["spans"]["2026"], base["spans"]["2021-25"]
    wins = 0
    for _ in range(n):
        pick = {int(t["entry_t"]) for t in raw["trades"] if rng.random() < share}
        S = rl.score(rl.size(raw, rule=lambda t, ctx: m if int(t["entry_t"]) in pick else 1.0), raw)
        a, b = S["spans"]["2026"], S["spans"]["2021-25"]
        wins += a["net"] > A0["net"] and a["pf"] > A0["pf"] and b["net"] > B0["net"] and b["pf"] > B0["pf"]
    return wins, n


def gate(vid, R, base, neighbours):
    """Mandatory robustness checks for an adopt-candidate: every neighbour must also beat the baseline in both periods,
    and at least 3 of the 4 full years 2022-25 must improve. Returns (ok, reasons)."""
    why = []
    bad = [v for v in neighbours if v in R and R[v]["status"] != "adopt-candidate"]
    if bad:
        why.append("neighbours fail (" + ", ".join(f"{v}: 2026 PF {R[v]['S']['spans']['2026']['pf']}, 2021-25 PF "
                                                   f"{R[v]['S']['spans']['2021-25']['pf']}" for v in bad) + ")")
    yrs = by_year(R[vid]["S"], base)
    up = sum(1 for y in ("2022", "2023", "2024", "2025") if yrs[y] > 0)
    if up < 3:
        why.append(f"only {up} of 4 full years improve (" + ", ".join(f"{y} {v:+,}" for y, v in yrs.items()) + ")")
    return not why, why


def save_all(R, base, tag="posthoc"):
    for vid, r in R.items():
        fam = "vwap" if r["name"].startswith("vwap") else "vp"
        rl.save(vid, title_of(r["name"], r["good"], r["kind"]), "filters", r["question"],
                sizing={"idea": r["name"], "strong_side": "present" if r["good"] else "absent", "kind": r["kind"],
                        "rule": KINDS.get(r["kind"], f"x{int(r['kind'][2:]) / 100:g} on the strong side"),
                        "on_top_of": "live sizing incl. the cold-streak half size"},
                trades=r["T"], scored=r["S"], status=r["status"], verdict=r["verdict"],
                notes=("Post-hoc on the exact live-loop replay (768 baseline trades, costs included); only the size changes. "
                       "Features from data/NQ_5m.csv at the signal close (no look-ahead). Strong side chosen on 2021-25 only "
                       "(except the re-checks). Reproduce: python tools/research_vp.py all"), writeup=WRITEUP, tags=[tag, fam])


def fmt(s):
    if not s.get("n"):
        return "no trades"
    return (f"n={s['n']} {s['tpw']}/wk wk2={s['wk2']}% PF={s['pf']} net={s['net']:+,} DD={s['dd']:,} "
            f"eval 2wk {s['p10']}/{s['f10']} 1mo {s['p20']}/{s['f20']} slow {s.get('slow_pass')}% b2b {s['b2b']}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "info"
    B, raw, FE = all_features()
    print(f"features for {len(FE)}/{len(raw['trades'])} trades")
    if cmd in ("check", "all"):
        check(B, raw, FE)
    if cmd in ("info", "all", "dry"):
        T0 = rl.size(raw)
        res = info(T0, FE)
        sel = select(res)
        print(f"\n{len(IDEAS)} ideas tested; chosen on 2021-25 only ({len(sel)}):")
        for name, good in sel.items():
            obs, pv = perm_p(T0, IDEAS[name][2], FE)
            ys = years_sign(T0, IDEAS[name][2], FE, good)
            print(f"  {name:<20} strong side = {'present' if good else 'absent'}  2021-25 gap {obs:+.3f}R  permutation p={pv}"
                  f"  years 2022-25 agreeing {ys[0]} {ys[1]}")
    if cmd in ("all", "dry"):
        base = rl.score(rl.size(raw), raw)               # the live strategy, scored now (same trades as run "baseline")
        print("\nbaseline: 2026", fmt(base["spans"]["2026"]), "| 2021-25", fmt(base["spans"]["2021-25"]))
        plan = []
        for name, good in sel.items():
            for kind in KINDS:
                plan.append((f"{name}_{kind}", name, IDEAS[name][2], good, kind, IDEAS[name][1] + "?"))
        for name, good, why in RECHECKS:
            for kind in (KINDS if name == "vp_open_in" and good else ("half", "up")):
                vid = f"{name}_{kind}" if not (name == "vp_open_in" and good) else f"vp_balance_{kind}"
                plan.append((vid, name, IDEAS[name][2], good, kind, why + ". " + IDEAS[name][1] + "?"))
        print("\n-- sized variants (a) half / up, (b) skip check, (c) cold-streak interplay; all on top of the live sizing")
        R = run_variants(raw, FE, base, plan)
        # neighbours of the threshold ideas that were chosen, sized the same way as their best-looking 2021-25 kind
        plan = []
        for name, good in sel.items():
            if name not in NEIGHBOURS:
                continue
            for vid, x in NEIGHBOURS[name]:
                plan.append((f"{vid}_half", name, neighbour_fn(name, x), good, "half",
                             f"Neighbour check of {name}: same idea at threshold {x}. " + IDEAS[name][1] + "?"))
        print("\n-- neighbour checks (half size on the weak side)")
        R.update(run_variants(raw, FE, base, plan))
        # neighbours of the AMT balance idea: own tick profile with 60 / 70 / 80% value areas, and other multipliers
        why = "Neighbour check of the AMT balance idea"
        plan = [(f"vp_balance_va{va}_up", "vp_open_in", (lambda t, F, va=va: F.get(f"open_in_{va}")), True, "up",
                 f"{why}: open inside a {va}% value area from our own tick profile, 1.25x size?") for va in (60, 70, 80)]
        plan += [(f"vp_balance_{k}", "vp_open_in", IDEAS["vp_open_in"][2], True, k, f"{why}: other size multiplier ({k})?")
                 for k in ("up110", "up150")]
        print("\n-- neighbour checks of the AMT balance idea")
        R.update(run_variants(raw, FE, base, plan))
        # robustness gate for every adopt-candidate
        NB = {"vp_balance_up": ["vp_balance_va60_up", "vp_balance_va70_up", "vp_balance_va80_up", "vp_balance_up110",
                                "vp_balance_up150"]}
        for vid, r in R.items():
            if r["status"] != "adopt-candidate":
                continue
            ok, reasons = gate(vid, R, base, NB.get(vid, []))
            share = sum(1 for t in raw["trades"] if flag(IDEAS[r["name"]][2], t, FE) is r["good"]) / len(raw["trades"])
            k = r["kind"]
            m, sh = ((1.25 if k == "up" else int(k[2:]) / 100), share) if k.startswith("up") else (0.5, 1 - share)
            w, n = placebo(raw, base, sh, m)
            print(f"\ngate {vid}: {'PASS' if ok else 'FAIL'} {reasons}; placebo: random {sh:.0%} subsets sized x{m:g} pass "
                  f"the both-periods rule {w}/{n}")
            if not ok:
                r["status"] = "rejected"
                r["verdict"] = ("Beats the baseline in both periods by a hair, but fails the robustness checks: "
                                + "; ".join(reasons) + f"; random subsets of the same size sized x{m:g} pass {w}/{n} times. " + r["verdict"])
        if cmd == "all":
            save_all(R, base)
            print(f"\nsaved {len(R)} runs:", ", ".join(R))
        counts = collections.Counter(r["status"] for r in R.values())
        print("statuses:", dict(counts))
