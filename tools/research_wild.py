"""Unexpected factors study (run prefix "wild_", 2026-10-17).

Brainstorms ~30 unusual but mechanism-backed conditions that were knowable at entry (volatility context from VIX / VXN /
GEX / DIX, the day's structure from the 5m bars, the week's own trade history, the setup's micro-structure) and asks
whether any of them separates the locked strategy's trades. Ranked on 2021-25 only (avg R gap, n >= 60 on both sides),
then 2026 is shown untouched for the top 8, those 8 are tested as size rules with rl.size(rule=...), and the best one gets
a shuffle test (single-factor and "best of 30" multiple-comparison versions).

  python tools/research_wild.py              # tables + size-rule runs (wild_*) + research/lab/unexpected_factors.json
  python tools/research_wild.py --no-save    # tables only

Nothing here looks ahead: every feature uses bars up to the signal bar, daily data up to the previous session, and
trades that had finished before the entry.
"""
from __future__ import annotations

import bisect
import collections
import csv
import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import runlib as rl  # noqa: E402

ET = ZoneInfo("America/New_York")
SPANS = {"2026": ("2026-01-01", "2026-12-31"), "2021-25": ("2021-01-01", "2025-12-31")}
OUT_JSON = os.path.join(ROOT, "research", "lab", "unexpected_factors.json")


# ------------------------------------------------------------------------------------------------ data
def load_bars():
    a = np.genfromtxt(os.path.join(ROOT, "data", "NQ_5m.csv"), delimiter=",", skip_header=1)
    t = a[:, 0].astype(np.int64)
    o, h, l, c, v = a[:, 1], a[:, 2], a[:, 3], a[:, 4], a[:, 5]
    # true range + ATR14 (5m)
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
    atr = np.convolve(tr, np.ones(14) / 14, mode="full")[:len(tr)]
    # ET calendar fields
    et = [dt.datetime.fromtimestamp(int(x), ET) for x in t]
    date = np.array([d.strftime("%Y-%m-%d") for d in et])
    mins = np.array([d.hour * 60 + d.minute for d in et])
    return {"t": t, "o": o, "h": h, "l": l, "c": c, "v": v, "atr": atr, "date": date, "mins": mins}


def daily_table(B):
    """Per ET session date: RTH open/high/low/close (09:30-16:00), overnight range (prev 18:00 -> 09:30), first 15 min range.
    Everything is keyed by the session date; features use the PREVIOUS session's row, or the current row's open-time data."""
    dates = sorted(set(B["date"]))
    idx = {d: np.where(B["date"] == d)[0] for d in dates}
    rows = {}
    for i, d in enumerate(dates):
        ix = idx[d]; m = B["mins"][ix]
        rth = ix[(m >= 570) & (m < 960)]
        if len(rth) < 30:
            continue
        pre = ix[m < 570]
        on_ix = list(pre)
        if i > 0:
            pix = idx[dates[i - 1]]; pm = B["mins"][pix]
            on_ix = list(pix[pm >= 1080]) + on_ix
        on_ix = np.array(on_ix, dtype=int)
        f15 = ix[(m >= 570) & (m < 585)]
        rows[d] = {"open": float(B["o"][rth[0]]), "high": float(B["h"][rth].max()), "low": float(B["l"][rth].min()),
                   "close": float(B["c"][rth[-1]]), "range": float(B["h"][rth].max() - B["l"][rth].min()),
                   "on_hi": float(B["h"][on_ix].max()) if len(on_ix) else None, "on_lo": float(B["l"][on_ix].min()) if len(on_ix) else None,
                   "f15": float(B["h"][f15].max() - B["l"][f15].min()) if len(f15) else None,
                   "rth_vol": float(B["v"][rth].sum())}
    days = sorted(rows)
    for i, d in enumerate(days):
        r = rows[d]
        prev = [rows[x] for x in days[max(0, i - 20):i]]
        r["adr20"] = float(np.mean([p["range"] for p in prev])) if len(prev) >= 10 else None
        r["pd"] = rows[days[i - 1]] if i else None
        # inside days before this one, up/down streak, days since a 2% day: all from sessions strictly before d
        k, j = 0, i - 1
        while j >= 1 and rows[days[j]]["high"] < rows[days[j - 1]]["high"] and rows[days[j]]["low"] > rows[days[j - 1]]["low"]:
            k += 1; j -= 1
        r["inside_days"] = k
        s, j = 0, i - 1
        while j >= 1:
            ch = rows[days[j]]["close"] - rows[days[j - 1]]["close"]
            sg = 1 if ch > 0 else -1
            if s == 0 or (s > 0) == (sg > 0):
                s += sg; j -= 1
            else:
                break
        r["close_streak"] = s
        n, j = 0, i - 1
        while j >= 1:
            if abs(rows[days[j]]["close"] / rows[days[j - 1]]["close"] - 1) >= 0.02:
                break
            n += 1; j -= 1
        r["days_since_2pct"] = n if j >= 1 else 99
        # prior week's range vs the 4 weeks before it (ISO weeks, sessions strictly before d)
        wk = collections.OrderedDict()
        for x in days[max(0, i - 30):i]:
            w = dt.date.fromisoformat(x).isocalendar()[:2]
            wk.setdefault(w, []).append(rows[x])
        ws = list(wk.values())
        cur_w = dt.date.fromisoformat(d).isocalendar()[:2]
        if ws and list(wk.keys())[-1] == cur_w:
            ws = ws[:-1]
        if len(ws) >= 3:
            rng = [max(p["high"] for p in w) - min(p["low"] for p in w) for w in ws]
            r["pw_range_ratio"] = rng[-1] / np.mean(rng[-5:-1]) if len(rng) >= 2 and np.mean(rng[-5:-1]) > 0 else None
        else:
            r["pw_range_ratio"] = None
    return rows, days


def load_series(name, col):
    out = {}
    with open(os.path.join(ROOT, "data", name), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            try:
                v = float(r[col])
            except (ValueError, KeyError):
                continue
            if v != 0:
                out[r["date"]] = v
    return out


def prev_val(series_days, series, day, back=1):
    """Value `back` trading days before `day` (strictly before)."""
    i = bisect.bisect_left(series_days, day) - back
    return (series_days[i], series[series_days[i]]) if i >= 0 else (None, None)


# ------------------------------------------------------------------------------------------------ features
def build_features(raw):
    B = load_bars()
    D, days = daily_table(B)
    vix = load_series("VIX_1d.csv", "close"); vxn = load_series("VXN_1d.csv", "close")
    gex = load_series("GEX_1d.csv", "gex"); dix = load_series("GEX_1d.csv", "dix")
    vd, xd, gd = sorted(vix), sorted(vxn), sorted(gex)
    T = sorted(raw["trades"], key=lambda t: t["entry_t"])
    tarr = B["t"]
    # (date, minute) -> volume, for relative volume
    vol_key = {}
    for i in range(len(tarr)):
        vol_key[(B["date"][i], int(B["mins"][i]))] = float(B["v"][i])
    F = {}
    week_count = collections.Counter(); last_day_result = {}
    fin_by_day = collections.defaultdict(list)
    for t in T:
        d = t["day"]; f = {}
        row = D.get(d); pd_ = row["pd"] if row else None
        adr = row["adr20"] if row else None
        si = int(np.searchsorted(tarr, int(t["signal_t"])))
        if si >= len(tarr) or tarr[si] != int(t["signal_t"]):
            si = max(0, si - 1)
        ei = int(np.searchsorted(tarr, int(t["entry_t"])))
        ei = min(ei, len(tarr) - 1)
        atr = float(B["atr"][si]) or 1.0
        sig_min = int(B["mins"][si])
        ent_min = int(B["mins"][ei])
        dirn = int(t["dir"])
        # --- the day's structure (previous session / today's open) ---
        if row and adr and pd_:
            f["pd_range_adr"] = pd_["range"] / adr
            f["on_share"] = (row["on_hi"] - row["on_lo"]) / adr if row["on_hi"] is not None else None
            gap = (row["open"] - pd_["close"]) / adr
            f["gap_abs_adr"] = abs(gap)
            f["gap_with_trade"] = 1 if gap * dirn > 0 else 0
            f["f15_adr"] = row["f15"] / adr if row["f15"] else None
            f["inside_days"] = row["inside_days"]
            f["close_streak_with"] = 1 if row["close_streak"] * dirn > 0 else 0
            f["close_streak_len"] = abs(row["close_streak"])
            f["days_since_2pct"] = row["days_since_2pct"]
            f["pw_range_ratio"] = row["pw_range_ratio"]
            f["pd_close_pos"] = (pd_["close"] - pd_["low"]) / pd_["range"] if pd_["range"] else None
            # entry relative to the 09:30 open, in ADR, signed with the trade (positive = entering on the trade's side of the open)
            f["entry_vs_open"] = (float(t["entry"]) - row["open"]) / adr * dirn
            # the day's range already used when the signal fired (bars from 09:30 up to the signal bar)
            ix = np.where((B["date"] == d) & (B["mins"][...] >= 570))[0]
            ix = ix[ix <= si]
            f["range_used"] = (B["h"][ix].max() - B["l"][ix].min()) / adr if len(ix) else None
            # sweep extreme bar: the first 5m bar (from 08:00 ET today) that touched the sweep extreme before the signal
            ix2 = np.where((B["date"] == d) & (B["mins"][...] >= 480))[0]
            ix2 = ix2[ix2 <= si]
            sw = None
            for i in ix2:
                if (dirn > 0 and B["l"][i] <= float(t["sweep_ext"]) + 1e-9) or (dirn < 0 and B["h"][i] >= float(t["sweep_ext"]) - 1e-9):
                    sw = i; break
            if sw is not None:
                f["sweep_premarket"] = 1 if B["mins"][sw] < 570 else 0
                f["sweep_to_trigger_min"] = (int(t["signal_t"]) - int(tarr[sw])) / 60
                f["sweep_bar_atr"] = float(B["h"][sw] - B["l"][sw]) / atr
        # --- volatility context (previous day's values only) ---
        _, v1 = prev_val(vd, vix, d, 1); _, v6 = prev_val(vd, vix, d, 6)
        _, x1 = prev_val(xd, vxn, d, 1)
        i20 = bisect.bisect_left(vd, d)
        if v1:
            f["vix_prev"] = v1
            f["vix_5d_chg"] = v1 / v6 - 1 if v6 else None
            f["vix_vs_20d"] = v1 / np.mean([vix[x] for x in vd[max(0, i20 - 20):i20]]) if i20 >= 10 else None
            f["vxn_minus_vix"] = (x1 - v1) if x1 else None
        gday, g1 = prev_val(gd, gex, d, 1)
        if g1 is not None:
            f["gex_pos"] = 1 if g1 > 0 else 0
            j = bisect.bisect_left(gd, d)
            hist = [gex[x] for x in gd[max(0, j - 250):j]]
            f["gex_pct"] = float(np.mean([x <= g1 for x in hist])) if len(hist) >= 60 else None
            f["dix"] = dix.get(gday)
        # --- the setup's micro-structure ---
        f["zone_atr"] = abs(float(t["zone"][1]) - float(t["zone"][0])) / atr
        f["n_pools"] = len(t["pools"])
        f["trigger_bar_atr"] = float(B["h"][si] - B["l"][si]) / atr
        f["rr_plan"] = t["f"].get("rr_plan")
        f["depth_atr"] = t["f"].get("depth_atr")
        f["target_pts_atr"] = abs(float(t["target"]) - float(t["entry"])) / atr
        kz0 = 570 if ent_min < 780 else 810
        f["kz_minutes"] = ent_min - kz0
        f["signal_entry_gap_bars"] = (int(t["entry_t"]) - int(t["signal_t"])) / 300
        # relative volume of the signal bar vs the same clock bar over the prior 20 sessions
        di = days.index(d) if d in days else None
        if di:
            ref = [vol_key.get((x, sig_min)) for x in days[max(0, di - 20):di]]
            ref = [x for x in ref if x]
            f["rvol"] = float(B["v"][si]) / np.mean(ref) if len(ref) >= 10 and np.mean(ref) > 0 else None
        # pool age class from the labels (overnight sessions = hours old; prior day/week = days old; intraday = minutes)
        lab = " ".join(t["pools"])
        f["pool_age"] = 2 if any(k in lab for k in ("PDH", "PDL", "PWH", "PWL")) else (1 if any(k in lab for k in ("ONH", "ONL", "LOH", "LOL", "ASH", "ASL")) else 0)
        # --- the week's own trade history (finished trades only) ---
        wk = dt.date.fromisoformat(d).isocalendar()[:2]
        f["trades_this_week"] = week_count[wk]
        fin = [x for x in T if x["exit_t"] and int(x["exit_t"]) < int(t["entry_t"])]
        last10 = [float(x["r"]) for x in fin[-10:]]
        f["last10_sum_r"] = sum(last10) if len(last10) == 10 else None
        f["last5_sum_r"] = sum(float(x["r"]) for x in fin[-5:]) if len(fin) >= 5 else None
        prev_days = sorted({x["day"] for x in fin if x["day"] < d})
        if prev_days:
            ld = prev_days[-1]
            f["prev_trade_won"] = 1 if sum(float(x["r"]) for x in fin if x["day"] == ld) > 0 else 0
            f["days_since_trade"] = (dt.date.fromisoformat(d) - dt.date.fromisoformat(ld)).days
        mtd = [float(x["r"]) for x in fin if x["day"][:7] == d[:7]]
        f["mtd_r"] = sum(mtd) if mtd else 0.0
        f["mtd_trades"] = len(mtd)
        week_count[wk] += 1
        F[int(t["entry_t"])] = f
    return F


# the factors: (key, plain label, kind, split). kind "num" -> above / below the 2021-25 median (or the given threshold);
# "bin" -> 1 vs 0; "cat3" -> threshold list. The "mechanism" column is the story behind the test (written for the write-up).
FACTORS = [
    ("pd_range_adr", "Yesterday's range vs 20-day ADR", "num", None, "a big day yesterday leaves fewer fresh pools and a tired tape"),
    ("on_share", "Overnight range vs ADR", "num", None, "a wide overnight session has already used part of the day's travel"),
    ("gap_abs_adr", "Size of the 09:30 gap vs ADR", "num", None, "gaps attract fills: a big gap means a fight at the open"),
    ("gap_with_trade", "Gap in the trade's direction", "bin", None, "trading with the gap is continuation; against it is the gap fill"),
    ("f15_adr", "Opening 15-minute range vs ADR", "num", None, "a wild open means the sweep was made by the opening drive"),
    ("inside_days", "Yesterday was an inside day", "bin", 1, "compression before expansion: inside days precede range days"),
    ("close_streak_with", "3+ closes in a row in the trade's direction", "bin", None, "a stretched streak means the sweep is a late continuation"),
    ("days_since_2pct", "Days since the last 2% day (recent vs old)", "num", 10, "fresh shocks mean fatter tails and less respect for pools"),
    ("pw_range_ratio", "Last week's range vs the prior 4 weeks", "num", None, "a quiet week sets up a lively one"),
    ("pd_close_pos", "Where yesterday closed in its range", "num", None, "a close at the extreme means the overnight builds the next pool"),
    ("entry_vs_open", "Entry on the trade's side of the 09:30 open", "num", 0.0, "buying above the open is chasing; buying below it is a discount vs the open"),
    ("range_used", "Range already travelled before the signal vs ADR", "num", None, "the day has a budget; a late sweep has less left"),
    ("sweep_premarket", "Sweep extreme made before 09:30", "bin", None, "a pre-market sweep is run by the overnight book, not the cash session"),
    ("sweep_to_trigger_min", "Minutes from the sweep to the trigger", "num", None, "a fast reclaim means a true stop-run; a slow one is acceptance"),
    ("sweep_bar_atr", "Size of the sweep bar vs 5m ATR", "num", None, "a climactic sweep bar flushes stops at once"),
    ("vix_5d_chg", "VIX change over 5 days", "num", 0.0, "rising fear raises the odds a pool holds"),
    ("vix_vs_20d", "VIX vs its 20-day average", "num", 1.0, "vol above its own norm means wider ranges, wider stops"),
    ("vxn_minus_vix", "VXN minus VIX (tech vol premium)", "num", None, "when tech vol is dear vs the S&P, NQ is the one moving"),
    ("gex_pos", "Dealer gamma positive (SqueezeMetrics GEX)", "bin", None, "positive gamma pins price, negative gamma lets it run"),
    ("gex_pct", "GEX percentile (1 year)", "num", None, "extreme gamma = extreme pinning / extreme trend"),
    ("dix", "DIX (dark-pool buying) above its median", "num", None, "quiet institutional buying supports the long side"),
    ("zone_atr", "IFVG / CISD zone height vs 5m ATR", "num", None, "a tall gap means a violent reversal; a thin one is noise"),
    ("n_pools", "Pools swept at once (1 vs 2+)", "num", 1, "a stacked raid takes more stops and has more fuel"),
    ("trigger_bar_atr", "Trigger candle size vs 5m ATR", "num", None, "a big trigger candle means part of the move is spent"),
    ("target_pts_atr", "Distance to target vs 5m ATR", "num", None, "a far pool is a long trip through noise"),
    ("kz_minutes", "Minutes into the killzone at entry", "num", 45, "the first 45 minutes of a killzone are the manipulation leg"),
    ("rvol", "Signal-bar volume vs the same clock bar (20 days)", "num", 1.0, "a quiet trigger bar has no one behind it"),
    ("pool_age", "Swept pool is a prior-day / prior-week level", "num", 1, "older levels hold more resting orders"),
    ("trades_this_week", "Trades already taken this week", "num", 1, "the third setup of the week is the leftover one"),
    ("last10_sum_r", "Equity slope: last 10 trades net positive", "num", 0.0, "hot and cold stretches cluster beyond the 15-trade filter"),
    ("prev_trade_won", "The last trading day's trade won", "bin", None, "a winner yesterday means the regime is paying"),
    ("days_since_trade", "Days since the previous trade (gap of 2+ days)", "num", 1, "a quiet spell means the market had no clean pools"),
    ("mtd_r", "Month-to-date R positive", "num", 0.0, "months trend"),
]


def in_span(day, span):
    a, z = SPANS[span]
    return a <= day <= z


def split(F, T, key, kind, thr, span):
    rows = [(t, F[int(t["entry_t"])].get(key)) for t in T if in_span(t["day"], span)]
    rows = [(t, v) for t, v in rows if v is not None]
    if not rows:
        return None, None, None
    if kind == "num" and thr is None:
        thr = float(np.median([v for _, v in rows if in_span(_["day"], "2021-25")] or [v for _, v in rows]))
    if kind == "bin":
        hi = [t for t, v in rows if v >= (thr if thr is not None else 1)]; lo = [t for t, v in rows if v < (thr if thr is not None else 1)]
    else:
        hi = [t for t, v in rows if v > thr]; lo = [t for t, v in rows if v <= thr]
    return hi, lo, thr


def stat(T):
    if not T:
        return {"n": 0}
    r = np.array([float(t["r"]) for t in T]); p = np.array([float(t["pnl"]) for t in T])
    gl = -p[p < 0].sum()
    return {"n": len(T), "avg_r": round(float(r.mean()), 3), "win": round(100 * float((r > 0).mean()), 1),
            "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None, "net": round(float(p.sum()))}


def welch_t(a, b):
    a, b = np.array(a, float), np.array(b, float)
    if len(a) < 2 or len(b) < 2:
        return 0.0
    se = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    return float((a.mean() - b.mean()) / se) if se else 0.0


def rank(F, raw, min_n=60):
    T = sorted(raw["trades"], key=lambda t: t["entry_t"])
    table = []
    for key, label, kind, thr, mech in FACTORS:
        hi, lo, th = split(F, T, key, kind, thr, "2021-25")
        if hi is None or len(hi) < min_n or len(lo) < min_n:
            table.append({"key": key, "label": label, "mechanism": mech, "thr": th, "old": None, "skip": f"n={len(hi or [])}/{len(lo or [])}"})
            continue
        sh, sl = stat(hi), stat(lo)
        tt = welch_t([t["r"] for t in hi], [t["r"] for t in lo])
        hi6, lo6, _ = split(F, T, key, kind, th if kind == "num" else thr, "2026")
        s6h, s6l = stat(hi6), stat(lo6)
        table.append({"key": key, "label": label, "mechanism": mech, "thr": None if th is None else round(float(th), 3),
                      "old": {"hi": sh, "lo": sl, "gap": round(sh["avg_r"] - sl["avg_r"], 3), "t": round(tt, 2)},
                      "new": {"hi": s6h, "lo": s6l, "gap": round((s6h.get("avg_r") or 0) - (s6l.get("avg_r") or 0), 3)},
                      "same_sign": (sh["avg_r"] - sl["avg_r"]) * ((s6h.get("avg_r") or 0) - (s6l.get("avg_r") or 0)) > 0})
    ranked = sorted([r for r in table if r["old"]], key=lambda r: -abs(r["old"]["gap"]))
    return table, ranked


def shuffle_test(F, raw, key, kind, thr, draws=5000, seed=11):
    """How often does a random relabelling of the 2021-25 trades (same group sizes) produce an avg-R gap at least as big?
    Also the multiple-comparison version: the biggest |gap| across ALL factors on shuffled data."""
    rng = np.random.default_rng(seed)
    T = [t for t in sorted(raw["trades"], key=lambda t: t["entry_t"]) if in_span(t["day"], "2021-25")]
    R = np.array([float(t["r"]) for t in T])
    hi, lo, th = split(F, T, key, kind, thr, "2021-25")
    obs = abs(stat(hi)["avg_r"] - stat(lo)["avg_r"]); nh = len(hi)
    masks = []
    for k, lab, kd, tr, _ in FACTORS:
        h, l, _t = split(F, T, k, kd, tr, "2021-25")
        if h and l and len(h) >= 60 and len(l) >= 60:
            ids = {int(t["entry_t"]) for t in h}
            masks.append(np.array([int(t["entry_t"]) in ids for t in T]))
    single = 0; family = 0
    for _ in range(draws):
        perm = rng.permutation(len(R)); Rp = R[perm]
        m = np.zeros(len(R), bool); m[:nh] = True
        g = abs(Rp[m].mean() - Rp[~m].mean())
        single += g >= obs
        best = 0.0
        for mk in masks:
            best = max(best, abs(Rp[mk].mean() - Rp[~mk].mean()))
        family += best >= obs
    return {"observed_gap": round(obs, 3), "p_single": round(single / draws, 3), "p_family": round(family / draws, 3), "factors_tested": len(masks)}


def make_rule(F, key, kind, thr, mult_hi, mult_lo):
    def rule(t, ctx):
        v = F.get(int(t["entry_t"]), {}).get(key)
        if v is None:
            return 1.0
        if kind == "bin":
            return mult_hi if v >= (thr if thr is not None else 1) else mult_lo
        return mult_hi if v > thr else mult_lo
    return rule


def judge(S, S0):
    a, b = S["spans"]["2026"], S["spans"]["2021-25"]; A, B = S0["spans"]["2026"], S0["spans"]["2021-25"]
    both = a["net"] > A["net"] and a["pf"] >= A["pf"] and b["net"] > B["net"] and b["pf"] >= B["pf"]
    one = (b["net"] > B["net"] and b["pf"] >= B["pf"]) or (a["net"] > A["net"] and a["pf"] >= A["pf"])
    return "adopt-candidate" if both and rl.passes(S) else ("promising" if one else "rejected")


def main(save=True):
    raw = rl.replay()
    T0 = rl.size(raw); S0 = rl.score(T0, raw)
    print("baseline", rl.line(S0, "2026")); print("baseline", rl.line(S0, "2021-25"))
    F = build_features(raw)
    table, ranked = rank(F, raw)
    cov = {k: sum(1 for f in F.values() if f.get(k) is not None) for k, *_ in FACTORS}
    print("coverage", cov)
    print(f"\n{'factor':48s} {'thr':>7s} | {'old hi n':>8s} {'avgR':>6s} {'PF':>5s} | {'old lo n':>8s} {'avgR':>6s} {'PF':>5s} | {'gap':>6s} {'t':>5s} | 2026 gap same?")
    for r in ranked:
        o, n = r["old"], r["new"]
        print(f"{r['label'][:48]:48s} {str(r['thr']):>7s} | {o['hi']['n']:8d} {o['hi']['avg_r']:6.3f} {str(o['hi']['pf']):>5s} | {o['lo']['n']:8d} {o['lo']['avg_r']:6.3f} {str(o['lo']['pf']):>5s} | {o['gap']:6.3f} {o['t']:5.2f} | {n['gap']:6.3f} {'yes' if r['same_sign'] else 'NO'} ({n['hi'].get('n',0)}/{n['lo'].get('n',0)})")
    skipped = [r for r in table if not r["old"]]
    print("skipped (too few on one side):", [(r["key"], r["skip"]) for r in skipped])

    top = ranked[:8]
    runs = []
    for r in top:
        spec = next(x for x in FACTORS if x[0] == r["key"]); kind, thr = spec[2], (r["thr"] if spec[2] == "num" else spec[3])
        worse_is_hi = r["old"]["gap"] < 0
        for tag, mh, ml in (("half", 0.5, 1.0), ("x125", 1.25, 1.0)):
            # half: half size on the worse side; x125: 1.25x on the better side
            if tag == "half":
                mult_hi, mult_lo = (0.5, 1.0) if worse_is_hi else (1.0, 0.5)
            else:
                mult_hi, mult_lo = (1.0, 1.25) if worse_is_hi else (1.25, 1.0)
            T = rl.size(raw, rule=make_rule(F, r["key"], kind, thr, mult_hi, mult_lo)); S = rl.score(T, raw)
            st = judge(S, S0)
            rid = f"wild_{r['key']}_{tag}"
            side = ("above" if worse_is_hi else "at/below") if tag == "half" else ("at/below" if worse_is_hi else "above")
            print(f"\n{rid} [{st}]  ({'half size' if tag=='half' else '1.25x'} when {r['label']} is {side} {r['thr']})")
            print(" ", rl.line(S, "2026")); print(" ", rl.line(S, "2021-25"))
            runs.append({"id": rid, "key": r["key"], "tag": tag, "status": st, "spans": {k: S["spans"][k] for k in ("2026", "2021-25", "all")}})
            if save:
                rl.save(rid, f"{'Half size' if tag=='half' else '1.25x size'} when {r['label'].lower()} is {side} {r['thr']}", "filters",
                        f"Unexpected factor: {spec[4]}", params={}, sizing={"rule": r["key"], "side": side, "mult": 0.5 if tag == "half" else 1.25},
                        trades=T, scored=S, status=st if st != "adopt-candidate" else "promising",
                        verdict=f"2021-25 avg R gap {r['old']['gap']:+.3f} (t={r['old']['t']}); 2026 gap {r['new']['gap']:+.3f}. "
                                f"{'Better in both periods on the size rule.' if st=='adopt-candidate' else 'Does not beat the baseline in both periods.'}",
                        notes="Study wild_: 33 unusual factors ranked on 2021-25 only, top 8 tested as size rules. Multiple-comparison warning applies.",
                        writeup="unexpected-factors.md", tags=["wild", "unexpected"])
    best = ranked[0]
    spec = next(x for x in FACTORS if x[0] == best["key"])
    sh = shuffle_test(F, raw, best["key"], spec[2], best["thr"] if spec[2] == "num" else spec[3])
    print("\nshuffle test for", best["label"], sh)
    # a second shuffle for the best factor whose 2026 sign agrees
    agree = [r for r in ranked if r["same_sign"]]
    sh2 = None
    if agree and agree[0]["key"] != best["key"]:
        sp2 = next(x for x in FACTORS if x[0] == agree[0]["key"])
        sh2 = shuffle_test(F, raw, agree[0]["key"], sp2[2], agree[0]["thr"] if sp2[2] == "num" else sp2[3])
        print("shuffle test for", agree[0]["label"], sh2)
    if save:
        os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
        json.dump({"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "study": "wild", "writeup": "unexpected-factors.md",
                   "baseline": {k: S0["spans"][k] for k in ("2026", "2021-25")}, "factors": table, "ranked_keys": [r["key"] for r in ranked],
                   "coverage": cov, "runs": runs, "shuffle_best": {"key": best["key"], **sh},
                   "shuffle_best_agreeing": ({"key": agree[0]["key"], **sh2} if sh2 else None)},
                  open(OUT_JSON, "w", encoding="utf-8"), indent=1)
        print("wrote", OUT_JSON)
    return table, ranked, runs


if __name__ == "__main__":
    main(save="--no-save" not in sys.argv)
