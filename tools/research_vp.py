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
    # --- prior RTH profile (yesterday), naked POCs, prior-week composite, last-5-session composite
    prior = [j for j in range(k - 1, max(-1, k - 1 - 15), -1) if j in B.prof]
    if not prior:
        return F
    P = B.prof[prior[0]]
    F.update({"poc": P["poc"], "vah": P["vah"], "val": P["val"]})
    edge_against = P["val"] if d == 1 else P["vah"]                          # the value edge the sweep ran through
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

# neighbour sets for the ideas with a threshold (checked only for the finalists chosen on 2021-25)
NEIGHBOURS = {
    "vwap_chase1": [("vwap_chase05", 0.5), ("vwap_chase15", 1.5), ("vwap_chase2", 2.0)],
    "vwap_deep1": [("vwap_deep05", 0.5), ("vwap_deep15", 1.5)],
    "vwap_sweep2": [("vwap_sweep15", 1.5), ("vwap_sweep25", 2.5)],
    "vp_sweep_level5": [("vp_sweep_level3", 3.0), ("vp_sweep_level8", 8.0)],
    "vp_target_level5": [("vp_target_level3", 3.0), ("vp_target_level8", 8.0)],
    "vp_thin_path": [("vp_thin_path06", 0.6), ("vp_thin_path08", 0.8), ("vp_thin_path10", 1.0)],
}


def neighbour_fn(base, x):
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


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "info"
    B, raw, FE = all_features()
    print(f"features for {len(FE)}/{len(raw['trades'])} trades")
    if cmd in ("check", "all"):
        check(B, raw, FE)
    if cmd in ("info", "all"):
        T0 = rl.size(raw)
        info(T0, FE)
