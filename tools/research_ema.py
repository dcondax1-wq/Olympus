"""Moving averages (EMA / SMA) as confluence for the live Liquidity Engine setups (family "filters", runs ema_*).

The owner's question: could EMAs / moving averages be extra confluence, while keeping a decent number of trades a week?
Answered post-hoc on the exact live-loop replay of the live strategy (tools/runlib.replay, cached; costs included): every
moving-average fact is computed at each trade's decision time from data/NQ_5m.csv (TradingView CME NQ1!, back-adjusted)
using ONLY bars that had closed when the entry order went in (the engine fills at the open of the bar after the signal bar,
so the signal bar itself is the last bar it may use). 15m, 1h and daily bars are built from the same 5m file (the daily
file data/NQ_1d.csv is from another source with another close time and is not back-adjusted, so it is not used).
Each idea is then applied as a size rule (runlib.size rule=..., on top of the live cold-streak half size) or, only as a
check, as a skip, and stored as a run (runlib.save, research/runs/ema_*.json). Write-up: research/writeups/moving-averages.md

  python tools/research_ema.py all        # check + explore + every run + summary
  python tools/research_ema.py check      # no-look-ahead self-test of the MA features (recomputed on cut-off data)
  python tools/research_ema.py explore    # univariate scan of every MA fact on 2021-25 ONLY (the selection table)
  python tools/research_ema.py oos        # the same scan on 2026 (only looked at after the selection was fixed)
  python tools/research_ema.py runs       # save every ema_* run
  python tools/research_ema.py years [id] # year-by-year table of a rule (default ema_knife_half)
  python tools/research_ema.py noise      # placebo: half size on 80 random 2021-25 setups, 200 draws (slow, ~3 min)
  python tools/research_ema.py summary    # headline numbers of every ema_* run vs the baseline

Selection protocol (CLAUDE.md, anti-overfitting): rules and parameters are chosen on 2021-25 only, then 2026 is checked
untouched; a rule needs a market mechanism, at most two parameters, and its neighbouring parameter values must point the
same way. A post-hoc skip only approximates an engine filter (the engine could take a later signal that day instead).
"""
from __future__ import annotations

import json
import math
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import runlib as rl  # noqa: E402

WRITEUP = "research/writeups/moving-averages.md"
TF_SEC = {"5m": 300, "15m": 900, "1h": 3600}
EMA_LENS = (9, 20, 50, 100, 200)
DSMA_LENS = (10, 20, 50, 100, 200)
SEL, OOS = ("2021-01-01", "2025-12-31"), ("2026-01-01", "2026-12-31")


# ------------------------------------------------------------------------------------------------ bars + MAs
_BARS, _RAW5 = {}, {}


def bars(path=None, cut_t=None):
    """{"5m"|"15m"|"1h": DataFrame(t, o, h, l, c, close_t, ema_n..., atr), "1d": DataFrame(session, o, h, l, c, sma_n...,
    ema_n..., adr)}. All built from the 5m TradingView NQ1! file. cut_t: drop every 5m bar that opens at or after cut_t
    (the look-ahead self-test recomputes everything on data that ends at the decision time)."""
    key = (path, cut_t)
    if key in _BARS:
        return _BARS[key]
    if path not in _RAW5:
        m = pd.read_csv(path or os.path.join(ROOT, "data", "NQ_5m.csv"))
        m = m.rename(columns={"time": "t", "open": "o", "high": "h", "low": "l", "close": "c"})
        m = m.sort_values("t").reset_index(drop=True)
        et = pd.to_datetime(m.t, unit="s", utc=True).dt.tz_convert("America/New_York")
        m["sess"] = (et + pd.Timedelta(hours=6)).dt.strftime("%Y-%m-%d")  # CME session: 18:00 ET -> 17:00 ET
        _RAW5[path] = m
    m = _RAW5[path]
    if cut_t is not None:
        m = m[m.t < cut_t].reset_index(drop=True)
    out = {}
    for tf, sec in TF_SEC.items():
        if sec == 300:
            b = m[["t", "o", "h", "l", "c"]].copy()
        else:
            k = (m.t // sec) * sec
            b = m.groupby(k).agg(o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last")).reset_index()
            b = b.rename(columns={b.columns[0]: "t"})
        b["close_t"] = b.t + sec
        for n in EMA_LENS:
            b[f"ema{n}"] = b.c.ewm(span=n, adjust=False).mean()
        pc = b.c.shift(1)
        tr = np.maximum(b.h - b.l, np.maximum((b.h - pc).abs(), (b.l - pc).abs()))
        b["atr"] = tr.rolling(14, min_periods=14).mean()                 # simple 14-bar mean true range
        b["atr_rma"] = tr.ewm(alpha=1 / 14, adjust=False).mean()           # Wilder ATR (TradingView ta.atr) for the check
        out[tf] = b.reset_index(drop=True)
    d = m.groupby("sess").agg(o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last")).reset_index()
    for n in DSMA_LENS:
        d[f"sma{n}"] = d.c.rolling(n, min_periods=n).mean()
    for n in (20, 50):
        d[f"ema{n}"] = d.c.ewm(span=n, adjust=False).mean()
        d.loc[d.index < n - 1, f"ema{n}"] = np.nan                         # no value until n sessions of history
    d["adr"] = (d.h - d.l).rolling(20, min_periods=20).mean()
    out["1d"] = d
    _BARS[key] = out
    return out


def _last_closed(b, entry_t):
    """Index of the last bar of frame b that had closed when the entry order went in (close_t <= entry_t)."""
    i = int(np.searchsorted(b.close_t.values, entry_t, side="right")) - 1
    return i


def features(t, B=None):
    """Every moving-average fact for trade t at its decision time (signed by the trade's direction: + = on the trade's
    side). Uses only bars closed at entry_t (5m signal bar and earlier; closed 15m / 1h bars; prior sessions)."""
    B = B or bars()
    d, et_ = int(t["dir"]), int(t["entry_t"])
    b5 = B["5m"]
    i5 = _last_closed(b5, et_)
    px = float(b5.c.iat[i5])                                   # close of the signal bar (the decision price)
    ext = float(t.get("sweep_ext") or px)
    tgt = float(t.get("target") or px)
    F = {"px": px, "bar5_t": int(b5.t.iat[i5])}
    for tf in ("5m", "15m", "1h"):
        b = B[tf]
        i = i5 if tf == "5m" else _last_closed(b, et_)
        atr = float(b.atr.iat[i]) if i >= 0 and not math.isnan(b.atr.iat[i]) else float("nan")
        F[f"atr_{tf}"] = atr
        for n in EMA_LENS:
            if i < 3 * n:                                      # not enough history for a settled EMA
                F[f"{tf}_e{n}"] = float("nan"); continue
            e = float(b[f"ema{n}"].iat[i])
            F[f"{tf}_e{n}"] = e
            F[f"{tf}_e{n}_side"] = d * (px - e) / atr          # >0: price on the trade's side (above it for a long)
            k = 4 if tf != "5m" else 6
            F[f"{tf}_e{n}_slope"] = d * (e - float(b[f"ema{n}"].iat[i - k])) / atr   # >0: rising for a long
            F[f"{tf}_e{n}_tag"] = int(d * (ext - e) <= 0 < d * (px - e))           # sweep wick through it, closed back
            F[f"{tf}_e{n}_path"] = int(0 < d * (e - px) < d * (tgt - px))            # sits between entry and target
            F[f"{tf}_e{n}_ext"] = d * (ext - e) / atr                                # sweep extreme vs the MA
        if all(not math.isnan(F.get(f"{tf}_e{n}", float("nan"))) for n in (20, 50, 200)):
            a, bb, c = F[f"{tf}_e20"], F[f"{tf}_e50"], F[f"{tf}_e200"]
            F[f"{tf}_stack"] = d * (1 if a > bb > c else -1 if a < bb < c else 0)
        if tf == "1h" and not math.isnan(F.get("1h_e20", float("nan"))):
            F["1h_e20_side_rma"] = d * (px - F["1h_e20"]) / float(b.atr_rma.iat[i])
    dd = B["1d"]
    j = int(np.searchsorted(dd.sess.values, t["day"], side="left")) - 1   # last session before the trade day
    F["sess_prev"] = dd.sess.iat[j] if j >= 0 else None
    adr = float(dd.adr.iat[j]) if j >= 0 and not math.isnan(dd.adr.iat[j]) else float("nan")
    F["adr"] = adr
    for name in [f"sma{n}" for n in DSMA_LENS] + ["ema20", "ema50"]:
        v = float(dd[name].iat[j]) if j >= 0 else float("nan")
        F[f"1d_{name}"] = v
        if math.isnan(v):
            continue
        F[f"1d_{name}_side"] = d * (px - v) / adr
        v5 = float(dd[name].iat[j - 5]) if j >= 5 else float("nan")
        F[f"1d_{name}_slope"] = d * (v - v5) / adr if not math.isnan(v5) else float("nan")
        F[f"1d_{name}_tag"] = int(d * (ext - v) <= 0 < d * (px - v))
        F[f"1d_{name}_path"] = int(0 < d * (v - px) < d * (tgt - px))
    if all(not math.isnan(F.get(f"1d_sma{n}", float("nan"))) for n in (20, 50, 200)):
        a, bb, c = F["1d_sma20"], F["1d_sma50"], F["1d_sma200"]
        F["1d_stack"] = d * (1 if a > bb > c else -1 if a < bb < c else 0)
    return F


_FEAT = {}


def feature_table(raw):
    """{entry_t: features} for every trade of a replay (cached per replay)."""
    k = id(raw)
    if k not in _FEAT:
        B = bars()
        _FEAT[k] = {int(t["entry_t"]): features(t, B) for t in raw["trades"]}
    return _FEAT[k]


# ------------------------------------------------------------------------------------------------ helpers
_BASE = {}


def base():
    if not _BASE:
        raw = rl.replay(quiet=True)
        T = rl.size(raw)
        _BASE.update(raw=raw, T=T, S=rl.score(T, raw), F=feature_table(raw))
    return _BASE["raw"], _BASE["T"], _BASE["S"], _BASE["F"]


def _money(x):
    return f"-${-x:,.0f}" if x < 0 else f"+${x:,.0f}"


def _md(rows, head):
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" if i == 0 else "---:" for i in range(len(head))) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


# ------------------------------------------------------------------------------------------------ exploration (selection)
def scan_features():
    """(feature, label, test) for the univariate scan. test(F) -> True (group A: 'with'), False (group B), None (no value)."""
    out = []

    def side(k):
        return lambda F: None if k not in F or F[k] != F[k] else F[k] > 0

    def flag(k):
        return lambda F: None if k not in F else bool(F[k])

    for tf in ("5m", "15m", "1h"):
        for n in EMA_LENS:
            out.append((f"{tf}_e{n}_side", f"price on the trade's side of the {tf} EMA{n}", side(f"{tf}_e{n}_side")))
    for nm in [f"sma{n}" for n in DSMA_LENS] + ["ema20", "ema50"]:
        out.append((f"1d_{nm}_side", f"price on the trade's side of the daily {nm.upper()}", side(f"1d_{nm}_side")))
    for tf in ("15m", "1h"):
        for n in (20, 50, 200):
            out.append((f"{tf}_e{n}_slope", f"{tf} EMA{n} sloping the trade's way", side(f"{tf}_e{n}_slope")))
    for nm in ("sma20", "sma50", "sma200"):
        out.append((f"1d_{nm}_slope", f"daily {nm.upper()} sloping the trade's way (5 sessions)", side(f"1d_{nm}_slope")))
    for tf in ("15m", "1h", "1d"):
        k = f"{tf}_stack"
        out.append((k + "+", f"{tf} MAs stacked the trade's way (20>50>200 for a long)",
                    lambda F, k=k: None if k not in F else F[k] > 0))
        out.append((k + "-", f"{tf} MAs stacked against the trade",
                    lambda F, k=k: None if k not in F else F[k] < 0))
    for tf, ns in (("15m", (20, 50, 200)), ("1h", (20, 50, 200))):
        for n in ns:
            out.append((f"{tf}_e{n}_tag", f"sweep wick pierced the {tf} EMA{n} and the trigger closed back", flag(f"{tf}_e{n}_tag")))
    for nm in ("sma20", "sma50"):
        out.append((f"1d_{nm}_tag", f"sweep wick pierced the daily {nm.upper()} and closed back", flag(f"1d_{nm}_tag")))
    for tf, ns in (("15m", (50, 200)), ("1h", (20, 50, 200))):
        for n in ns:
            out.append((f"{tf}_e{n}_path", f"{tf} EMA{n} sits between entry and target", flag(f"{tf}_e{n}_path")))
    for nm in ("sma20", "sma50"):
        out.append((f"1d_{nm}_path", f"daily {nm.upper()} sits between entry and target", flag(f"1d_{nm}_path")))
    for tf in ("5m", "15m", "1h"):
        k = f"{tf}_e20_side"
        out.append((f"{tf}_e20_far", f"stretched: price 2+ ATR from the {tf} EMA20 (either side)",
                    lambda F, k=k: None if k not in F or F[k] != F[k] else abs(F[k]) >= 2.0))
    return out


def _grp(rows):
    if not rows:
        return {"n": 0}
    r = np.array([x[0] for x in rows]); p = np.array([x[1] for x in rows])
    gl = -p[p < 0].sum()
    return {"n": len(rows), "r": float(r.mean()), "sd": float(r.std(ddof=1)) if len(rows) > 1 else 0.0, "win": 100 * float((r > 0).mean()),
            "net": float(p.sum()), "pf": float(p[p > 0].sum() / gl) if gl else float("nan")}


def scan(span=SEL, verbose=True, subsplit=True):
    """Univariate table: for every MA fact, trades with it vs without (engine R per trade, and $ under live sizing)."""
    raw, T, S, F = base()
    a, z = span
    rows, res = [], []
    tr = [t for t in T if a <= t["day"] <= z]
    for key, label, test in scan_features():
        A, Bg, A1, B1, A2, B2 = [], [], [], [], [], []
        for t in tr:
            v = test(F[int(t["entry_t"])])
            if v is None:
                continue
            x = (float(t["r"]), float(t["pnl"]))
            (A if v else Bg).append(x)
            early = t["day"] <= "2023-12-31"
            if v:
                (A1 if early else A2).append(x)
            else:
                (B1 if early else B2).append(x)
        ga, gb = _grp(A), _grp(Bg)
        if not ga["n"] or not gb["n"]:
            continue
        diff = ga["r"] - gb["r"]
        se = math.sqrt(ga["sd"] ** 2 / ga["n"] + gb["sd"] ** 2 / gb["n"]) if ga["n"] > 1 and gb["n"] > 1 else float("nan")
        h1 = _grp(A1)["r"] - _grp(B1)["r"] if A1 and B1 else float("nan")
        h2 = _grp(A2)["r"] - _grp(B2)["r"] if A2 and B2 else float("nan")
        res.append({"key": key, "label": label, "A": ga, "B": gb, "diff": diff, "t": diff / se if se else float("nan"), "h1": h1, "h2": h2})
        rows.append([key, label, f"{ga['n']}/{gb['n']}", f"{ga['r']:+.2f} / {gb['r']:+.2f}", f"{diff:+.2f}", f"{diff / se:+.1f}",
                     f"{h1:+.2f} / {h2:+.2f}" if subsplit else "", f"{_money(ga['net'])} / {_money(gb['net'])}",
                     f"{ga['pf']:.2f} / {gb['pf']:.2f}"])
    if verbose:
        print(f"### Univariate scan {a[:4]}-{z[:4]}: {len(res)} moving-average facts, trades WITH the fact vs WITHOUT it")
        print(_md(rows, ["key", "fact", "n with/without", "avg R with/without", "diff R", "t", "diff R 21-23 / 24-25",
                         "net $ with/without", "PF with/without"]))
    return res


# ------------------------------------------------------------------------------------------------ rules and runs
def knife(key="1h_e20_side", k=3.0):
    """Falling knife: price at least k ATR on the WRONG side of the MA at the decision (a long far below the 1h EMA20,
    a short far above it), i.e. the setup fades a strong one-way move."""
    return lambda F: F.get(key, float("nan")) < -k


def side_with(key):
    return lambda F: F.get(key, float("nan")) > 0


def side_against(key):
    return lambda F: F.get(key, float("nan")) <= 0


def is_flag(key):
    return lambda F: bool(F.get(key))


def mult_rule(test, hit, miss=1.0):
    """runlib size rule: multiplier `hit` when test(features) is true, else `miss` (0 = skip the trade)."""
    raw, T, S, F = base()

    def rule(t, ctx):
        return hit if test(F[int(t["entry_t"])]) else miss
    return rule


Q_KNIFE = ("Should the bot trade smaller when the setup fades a strong one-way move, i.e. price is stretched far from the "
           "1-hour EMA 20 on the wrong side (a 'falling knife')?")
Q_TREND = "Do the classic moving-average trend filters (trade with the EMA / SMA trend) help the Liquidity Engine?"
Q_DAILY = "Does the position versus the daily 50-day average (with or against the daily trend) matter?"
Q_TAG = "Is a sweep that tags a higher-timeframe EMA (dynamic support / resistance) worth more size?"
KNIFE_MECH = ("Mechanism: a sweep-and-reverse setup bets that the sweep was a stop hunt. When price is already 3+ hourly ATRs "
              "away from its 20-hour average on the wrong side, a strong one-way move (displacement) is running and the sweep "
              "is more often continuation than a stop hunt. In 2021-25 these setups won 7% of the time (rest: 22%).")

# (id, title, question, family-key, test, hit multiplier, miss multiplier, status override or None, mechanism / note)
RUNS = (
    # primary rule, chosen on 2021-25 only (before 2026 was looked at)
    ("ema_knife_half", "Half size on a 'falling knife' (price 3+ ATR on the wrong side of the 1h EMA20)", Q_KNIFE, "knife",
     knife("1h_e20_side", 3.0), 0.5, 1.0, None, KNIFE_MECH + " Chosen on 2021-25 only: EMA 20 and 3 ATR are the middle of the "
     "neighbours tried (EMA 9/20/50, 2-4 ATR), all of which point the same way."),
    ("ema_knife_quarter", "Quarter size on a falling knife (1h EMA20, 3 ATR)", Q_KNIFE, "knife", knife("1h_e20_side", 3.0), 0.25, 1.0,
     None, "Stronger cut of the same rule."),
    ("ema_knife_skip", "Check: skip the falling knife setups (1h EMA20, 3 ATR)", Q_KNIFE, "knife", knife("1h_e20_side", 3.0), 0.0, 1.0,
     "info", "Check only: skipping cuts the number of trades. A post-hoc skip only approximates an engine filter (the engine "
     "could take a later signal that day instead)."),
    # neighbours (robustness, not separately selected)
    ("ema_knife_k2_half", "Neighbour: half size at 2+ ATR from the 1h EMA20", Q_KNIFE, "knife", knife("1h_e20_side", 2.0), 0.5, 1.0, None,
     "Neighbouring threshold (main rule: 3 ATR)."),
    ("ema_knife_k25_half", "Neighbour: half size at 2.5+ ATR from the 1h EMA20", Q_KNIFE, "knife", knife("1h_e20_side", 2.5), 0.5, 1.0, None,
     "Neighbouring threshold (main rule: 3 ATR)."),
    ("ema_knife_k35_half", "Neighbour: half size at 3.5+ ATR from the 1h EMA20", Q_KNIFE, "knife", knife("1h_e20_side", 3.5), 0.5, 1.0, None,
     "Neighbouring threshold (main rule: 3 ATR)."),
    ("ema_knife_e9_half", "Neighbour: half size at 3+ ATR from the 1h EMA9", Q_KNIFE, "knife", knife("1h_e9_side", 3.0), 0.5, 1.0, None,
     "Neighbouring EMA length (main rule: EMA 20)."),
    ("ema_knife_e50_half", "Neighbour: half size at 3+ ATR from the 1h EMA50", Q_KNIFE, "knife", knife("1h_e50_side", 3.0), 0.5, 1.0, None,
     "Neighbouring EMA length (main rule: EMA 20)."),
    ("ema_knife_15m50_half", "Neighbour: half size at 3+ (15m) ATR from the 15m EMA50", Q_KNIFE, "knife", knife("15m_e50_side", 3.0), 0.5,
     1.0, None, "Neighbouring timeframe: the 15m EMA 50 spans ~12 hours (main rule: 1h EMA 20, 20 hours)."),
    ("ema_knife_rma_half", "Neighbour: falling knife measured with the Wilder ATR (TradingView ta.atr)", Q_KNIFE, "knife",
     knife("1h_e20_side_rma", 3.0), 0.5, 1.0, None, "Same rule with TradingView's ATR (Wilder smoothing) instead of a plain 14-bar mean, "
     "to show the Pine port would behave the same."),
    # classic trend-following uses of moving averages (what most traders mean by 'EMA confluence')
    ("ema_1h50_trend_half", "Textbook: half size when price is on the wrong side of the 1h EMA50", Q_TREND, "trend",
     side_against("1h_e50_side"), 0.5, 1.0, None, "Textbook intraday trend filter (long only above the 1h EMA 50)."),
    ("ema_1h50_trend_x125", "Textbook: 1.25x size when price is on the right side of the 1h EMA50", Q_TREND, "trend",
     side_with("1h_e50_side"), 1.25, 1.0, None, "Same filter, leaning in instead of cutting."),
    ("ema_15m_stack_half", "Textbook: half size when the 15m EMAs 20/50/200 are stacked against the trade", Q_TREND, "trend",
     lambda F: F.get("15m_stack", 0) < 0, 0.5, 1.0, None, "EMA stack order (20 below 50 below 200 for a long = downtrend)."),
    ("ema_d200_trend_half", "Textbook: half size against the daily 200-day average (bull / bear market)", Q_TREND, "trend",
     side_against("1d_sma200_side"), 0.5, 1.0, None, "Classic bull / bear market line. Needs 200 sessions of 5m history, so it "
     "only applies from August 2022 (earlier trades keep full size)."),
    ("ema_d50_trend_half", "Textbook: half size against the daily 50-day average", Q_DAILY, "daily", side_against("1d_sma50_side"),
     0.5, 1.0, None, "Classic daily trend filter (long only above the 50-day average)."),
    # the data-driven daily idea (the opposite of the textbook): 2021-25 says counter-daily-trend setups did better
    ("ema_d50_with_half", "Half size WITH the daily 50-day average (long above it, short below it)", Q_DAILY, "daily",
     side_with("1d_sma50_side"), 0.5, 1.0, None, "2021-25 scan: setups against the daily 50-day average averaged +0.09R, with it "
     "-0.14R, for longs and shorts alike (multi-day mean reversion). But the gap came from 2022-23 only; in 2024 it reversed."),
    ("ema_d50_against_x125", "1.25x size AGAINST the daily 50-day average", Q_DAILY, "daily", side_against("1d_sma50_side"), 1.25, 1.0,
     None, "Same idea, leaning in instead of cutting."),
    # sweep tags a higher-timeframe EMA
    ("ema_tag50h_x125", "1.25x size when the sweep wick pierced the 1h EMA50 and the trigger closed back", Q_TAG, "tag",
     is_flag("1h_e50_tag"), 1.25, 1.0, None, "Dynamic support: liquidity and the ~2-day EMA at the same price. The 15m EMA 200 "
     "is almost the same line (200 x 15 min = 50 h). 2021-25: +0.13R vs the rest, t = 1.0 (weak)."),
    ("ema_tag50h_x150", "1.5x size when the sweep wick pierced the 1h EMA50 and the trigger closed back", Q_TAG, "tag",
     is_flag("1h_e50_tag"), 1.5, 1.0, None, "Same, bigger lean."),
)


def status_of(S, B, min_tpw=2.0):
    """adopt-candidate: better than the baseline in BOTH periods on net and PF, with 2+ trades a week in both, and the
    1-month MFFU eval (pass % - fail %) not worse by more than 1 point (so a plain size-up that only adds risk does not
    count); promising: clearly helps one period and does not hurt the other; else rejected."""
    a, b = S["spans"]["2026"], S["spans"]["2021-25"]
    A, Bb = B["spans"]["2026"], B["spans"]["2021-25"]
    if (a.get("tpw") or 0) < min_tpw or (b.get("tpw") or 0) < min_tpw:
        return "rejected"

    def ev(x):
        return x["p20"] - x["f20"]

    def better(x, y):
        return x["net"] > y["net"] and (x["pf"] or 0) >= (y["pf"] or 0) and ev(x) >= ev(y) - 1.0

    def clearly(x, y):
        return x["net"] > y["net"] * 1.05 + 300 and (x["pf"] or 0) > (y["pf"] or 0) and ev(x) >= ev(y) - 1.0

    def not_worse(x, y):
        return x["net"] >= 0.97 * y["net"] - 150 and (x["pf"] or 0) >= (y["pf"] or 0) - 0.03 and ev(x) >= ev(y) - 1.0

    if better(a, A) and better(b, Bb):
        return "adopt-candidate"
    if (clearly(a, A) and not_worse(b, Bb)) or (clearly(b, Bb) and not_worse(a, A)):
        return "promising"
    return "rejected"


def verdict_of(S, B, status, hits):
    a, b = S["spans"]["2026"], S["spans"]["2021-25"]
    A, Bb = B["spans"]["2026"], B["spans"]["2021-25"]
    head = {"adopt-candidate": "Better than the live strategy in both periods", "promising": "Helps one period without hurting the other",
            "rejected": "Not better in both periods", "info": "Check only"}[status]
    if min(a.get("tpw") or 0, b.get("tpw") or 0) < 2.0:
        head = "Fewer than 2 setups a week" if status != "info" else "Check only: fewer than 2 setups a week"
    return (f"{head}. 2026: net {_money(a['net'])} (live {_money(A['net'])}), PF {a['pf']} ({A['pf']}), max DD {_money(a['dd'])} "
            f"({_money(A['dd'])}), {a['tpw']} trades/week. 2021-25: net {_money(b['net'])} ({_money(Bb['net'])}), PF {b['pf']} ({Bb['pf']}), "
            f"max DD {_money(b['dd'])} ({_money(Bb['dd'])}), {b['tpw']}/week. Rule hit {hits[0]} setups in 2021-25 and {hits[1]} in 2026.")


EXTRA_VERDICT = {
    "ema_knife_half": " This is the rule chosen on 2021-25 before 2026 was looked at. In 2021-25 the 80 setups it hits won 7% of "
                      "the time (rest 22%) and lost money in every year. In 2026 it hits only 6 of 89 setups; one of them was a "
                      "+4.0R winner (2026-10-06, a short at 3.14 ATR, just past the line), which alone costs the $1,150.",
    "ema_knife_rma_half": " Same EMA 20 and 3-ATR line, but the ATR is TradingView's / the engine's Wilder ATR, which is a bit "
                          "wider, so it hits fewer setups (51 in 2021-25, 3 in 2026). This is the version the engine and the Pine "
                          "script would naturally use. Honest caveat: it was a robustness check, noticed as the natural "
                          "implementation only after 2026 had been seen; in 2026 it is simply unchanged (+$28).",
    "ema_knife_k35_half": " A neighbour check, not the chosen rule: it passes only because it leaves out the one 2026 winner at 3.14 ATR.",
    "ema_1h50_trend_x125": " Looks better on money only because it adds size to 37% of setups (more risk, no edge: these setups "
                           "averaged +0.01R vs -0.01R); the 2021-25 drawdown and eval fail rate get worse.",
}


def run_one(spec, save=True, eqf="live"):
    id, title, q, fam, test, hit, miss, st, note = spec
    raw, T0, B, F = base()
    T = rl.size(raw, eqf=eqf, rule=mult_rule(test, hit, miss))
    S = rl.score(T, raw)
    hits = (sum(1 for t in raw["trades"] if t["day"] <= "2025-12-31" and test(F[int(t["entry_t"])])),
            sum(1 for t in raw["trades"] if t["day"] >= "2026-01-01" and test(F[int(t["entry_t"])])))
    status = st or status_of(S, B)
    verdict = verdict_of(S, B, status, hits) + EXTRA_VERDICT.get(id, "")
    if save:
        rl.save(id, title, "filters", q, sizing={"rule": title, "hit_mult": hit, "else_mult": miss, "group": fam,
                                                  "cold_streak": "live" if eqf == "live" else "off"},
                trades=T, scored=S, status=status, verdict=verdict, writeup=WRITEUP, tags=["ema", fam],
                notes=note + " Method: exact live-loop replay of the live strategy (cached), moving averages computed from "
                "TradingView CME NQ1! 5m bars closed before the entry (15m / 1h / daily bars built from the same file), the "
                "size rule applied on top of the live cold-streak half size (runlib.size: P&L, commission and slippage scale "
                "with the micros; max 40 micros, a cut never goes below 1 micro); costs included. Selection on 2021-25 only, "
                "2026 checked untouched.")
    return S, status, hits


def cmd_runs(quiet=False):
    raw, T0, B, F = base()
    rows = []
    for spec in RUNS:
        S, status, hits = run_one(spec)
        a, b = S["spans"]["2026"], S["spans"]["2021-25"]
        rows.append([spec[0], spec[1], f"{hits[0]}/{hits[1]}", f"{a['tpw']}", _money(a["net"]), a["pf"], _money(a["dd"]),
                     f"{a['p10']:.0f}/{a['f10']:.0f}", f"{a['p20']:.0f}/{a['f20']:.0f}", f"{b['tpw']}", _money(b["net"]), b["pf"],
                     _money(b["dd"]), f"{b['p10']:.1f}/{b['f10']:.1f}", f"{b['p20']:.1f}/{b['f20']:.1f}", b["b2b"], status])
    # combination check (c): the main rule with and without the live cold-streak filter
    spec = RUNS[0]
    S_nc, _, hits = run_one(("ema_knife_half_nocold",) + spec[1:], save=False, eqf=None)
    T_nc = rl.size(raw, eqf=None)
    S_base_nc = rl.score(T_nc, raw)
    rl.save("ema_knife_half_nocold", "Check: falling-knife half size with the cold-streak filter OFF", "filters", Q_KNIFE,
            sizing={"rule": spec[1], "hit_mult": 0.5, "else_mult": 1.0, "group": "knife", "cold_streak": "off"},
            trades=rl.size(raw, eqf=None, rule=mult_rule(spec[4], 0.5, 1.0)), scored=S_nc, status="info", writeup=WRITEUP,
            tags=["ema", "knife"],
            verdict=(f"Check only: without the cold-streak filter the knife rule moves 2026 net {_money(S_base_nc['spans']['2026']['net'])} -> "
                     f"{_money(S_nc['spans']['2026']['net'])} and 2021-25 {_money(S_base_nc['spans']['2021-25']['net'])} -> "
                     f"{_money(S_nc['spans']['2021-25']['net'])} (PF {S_base_nc['spans']['2021-25']['pf']} -> {S_nc['spans']['2021-25']['pf']}), "
                     f"so the two rules work on different setups and add up."),
            notes="Same rule as ema_knife_half but on the raw engine size (no cold-streak half size), compared with the cold filter "
                  "switched off alone (run loss_no_cold). Shows whether the knife rule and the cold-streak filter overlap.")
    A, Bb = B["spans"]["2026"], B["spans"]["2021-25"]
    print(f"### ema_* runs ({len(RUNS) + 1}) vs live (2026: {A['tpw']}/wk, {_money(A['net'])}, PF {A['pf']}, DD {_money(A['dd'])}, "
          f"evals {A['p20']:.0f}/{A['f20']:.0f}; 2021-25: {Bb['tpw']}/wk, {_money(Bb['net'])}, PF {Bb['pf']}, DD {_money(Bb['dd'])}, "
          f"evals {Bb['p20']:.0f}/{Bb['f20']:.0f}, b2b {Bb['b2b']})")
    print(_md(rows, ["run", "rule", "hits 21-25/26", "26 /wk", "26 net", "26 PF", "26 DD", "26 eval 2w p/f", "26 eval 1m p/f",
                     "21-25 /wk", "21-25 net", "21-25 PF", "21-25 DD", "21-25 eval 2w p/f", "21-25 eval 1m p/f", "21-25 b2b", "status"]))
    print(f"no-cold check: base no-cold 2026 {_money(S_base_nc['spans']['2026']['net'])} PF {S_base_nc['spans']['2026']['pf']}, "
          f"2021-25 {_money(S_base_nc['spans']['2021-25']['net'])} PF {S_base_nc['spans']['2021-25']['pf']}; knife-half no-cold "
          f"2026 {_money(S_nc['spans']['2026']['net'])} PF {S_nc['spans']['2026']['pf']}, 2021-25 {_money(S_nc['spans']['2021-25']['net'])} "
          f"PF {S_nc['spans']['2021-25']['pf']}")


def cmd_check(n=80, seed=11):
    """No look-ahead: recompute the features of n random trades on data cut off at the entry (every 5m bar that opens at or
    after entry_t removed) and compare with the full-data features."""
    raw, T, S, F = base()
    rng = np.random.default_rng(seed)
    pick = rng.choice(len(raw["trades"]), size=min(n, len(raw["trades"])), replace=False)
    bad = 0
    for k in pick:
        t = raw["trades"][int(k)]
        Bc = bars(cut_t=int(t["entry_t"]))
        Fc = features(t, Bc)
        Ff = F[int(t["entry_t"])]
        _BARS.pop((None, int(t["entry_t"])), None)
        for key, v in Ff.items():
            w = Fc.get(key)
            if isinstance(v, float) and isinstance(w, float) and (math.isnan(v) and math.isnan(w)):
                continue
            if isinstance(v, float) and isinstance(w, float) and abs(v - w) <= 1e-6 * max(1.0, abs(v)):
                continue
            if v != w:
                bad += 1
                print("MISMATCH", t["day"], key, v, w)
                break
        if int(Ff["bar5_t"]) != int(t["signal_t"]):
            bad += 1
            print("signal bar mismatch", t["day"], Ff["bar5_t"], t["signal_t"])
    print(f"look-ahead check: {len(pick)} trades recomputed on data cut at the entry, {bad} mismatches")
    return bad


def cmd_years(spec_id="ema_knife_half"):
    """Year-by-year net / PF of the main rule vs live, and the rule's hits in each year."""
    raw, T0, B, F = base()
    spec = next(s for s in RUNS if s[0] == spec_id)
    T = rl.size(raw, rule=mult_rule(spec[4], spec[5], spec[6]))
    S = rl.score(T, raw)
    rows = []
    for y in sorted(S["years"]):
        hit = [t for t in T0 if t["day"][:4] == y and spec[4](F[int(t["entry_t"])])]
        r = np.array([t["r"] for t in hit]) if hit else np.array([np.nan])
        rows.append([y, B["years"][y]["n"], _money(B["years"][y]["net"]), B["years"][y]["pf"], _money(S["years"][y]["net"]), S["years"][y]["pf"],
                     len(hit), f"{np.nanmean(r):+.2f}" if hit else "-", f"{100 * np.mean(r > 0):.0f}%" if hit else "-",
                     _money(sum(t['pnl'] for t in hit))])
    print(f"### {spec_id} by year")
    print(_md(rows, ["year", "trades", "live net", "live PF", "rule net", "rule PF", "knife setups", "their avg R", "their win %",
                     "their live $"]))


def cmd_noise(draws=200, n_hit=80, seed=7):
    """Placebo: how much does 'half size on n_hit random 2021-25 setups' improve 2021-25 by chance? (main rule: +$4,629)"""
    raw, T0, B, F = base()
    rng = np.random.default_rng(seed)
    ids = [t["entry_t"] for t in raw["trades"] if t["day"] <= "2025-12-31"]
    gain = []
    for _ in range(draws):
        m = set(rng.choice(ids, size=n_hit, replace=False).tolist())
        S = rl.score(rl.size(raw, rule=lambda t, c, m=m: 0.5 if t["entry_t"] in m else 1.0), raw)
        gain.append(S["spans"]["2021-25"]["net"] - B["spans"]["2021-25"]["net"])
    g = np.array(gain)
    spec = RUNS[0]
    S = rl.score(rl.size(raw, rule=mult_rule(spec[4], spec[5], spec[6])), raw)
    real = S["spans"]["2021-25"]["net"] - B["spans"]["2021-25"]["net"]
    print(f"noise check: half size on {n_hit} random 2021-25 setups, {draws} draws: mean {_money(g.mean())}, 95th percentile "
          f"{_money(np.percentile(g, 95))}, best {_money(g.max())}; the knife rule {_money(real)} beats {100 * (g < real).mean():.1f}% of them")


def cmd_summary():
    B = rl.load("baseline")
    rows = []
    for p in sorted(os.listdir(rl.RUNS)):
        if not p.startswith("ema_") or not p.endswith(".json"):
            continue
        r = rl.load(p[:-5])
        a, b = r["spans"]["2026"], r["spans"]["2021-25"]
        rows.append([r["id"], r["status"], a["tpw"], a["wk2"], _money(a["net"]), a["pf"], _money(a["dd"]), f"{a['p10']:.0f}/{a['f10']:.0f}",
                     f"{a['p20']:.0f}/{a['f20']:.0f}", a["b2b"], b["tpw"], b["wk2"], _money(b["net"]), b["pf"], _money(b["dd"]),
                     f"{b['p10']:.1f}/{b['f10']:.1f}", f"{b['p20']:.1f}/{b['f20']:.1f}", b["b2b"]])
    A, Bb = B["spans"]["2026"], B["spans"]["2021-25"]
    rows.insert(0, ["baseline", "baseline", A["tpw"], A["wk2"], _money(A["net"]), A["pf"], _money(A["dd"]), f"{A['p10']:.0f}/{A['f10']:.0f}",
                    f"{A['p20']:.0f}/{A['f20']:.0f}", A["b2b"], Bb["tpw"], Bb["wk2"], _money(Bb["net"]), Bb["pf"], _money(Bb["dd"]),
                    f"{Bb['p10']:.1f}/{Bb['f10']:.1f}", f"{Bb['p20']:.1f}/{Bb['f20']:.1f}", Bb["b2b"]])
    print(_md(rows, ["run", "status", "26 /wk", "26 wk2+ %", "26 net", "26 PF", "26 DD", "26 eval 2w", "26 eval 1m", "26 b2b",
                     "21-25 /wk", "21-25 wk2+ %", "21-25 net", "21-25 PF", "21-25 DD", "21-25 eval 2w", "21-25 eval 1m", "21-25 b2b"]))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "explore"
    if cmd == "explore":
        scan(SEL)
    elif cmd == "oos":
        scan(OOS, subsplit=False)
    elif cmd == "check":
        cmd_check()
    elif cmd == "runs":
        cmd_runs()
    elif cmd == "years":
        cmd_years(sys.argv[2] if len(sys.argv) > 2 else "ema_knife_half")
    elif cmd == "noise":
        cmd_noise()
    elif cmd == "summary":
        cmd_summary()
    elif cmd == "all":
        cmd_check()
        scan(SEL)
        cmd_runs()
        cmd_years("ema_knife_half")
        cmd_years("ema_knife_rma_half")
        scan(OOS, subsplit=False)
        cmd_noise()
        cmd_summary()
    elif cmd == "feat":
        raw, T, S, F = base()
        t = sorted(raw["trades"], key=lambda x: x["entry_t"])[int(sys.argv[2]) if len(sys.argv) > 2 else 100]
        print(json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in F[int(t["entry_t"])].items()}, indent=0))
