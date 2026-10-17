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
_BARS = {}


def bars(path=None, cut_t=None):
    """{"5m"|"15m"|"1h": DataFrame(t, o, h, l, c, close_t, ema_n..., atr), "1d": DataFrame(session, o, h, l, c, sma_n...,
    ema_n..., adr)}. All built from the 5m TradingView NQ1! file. cut_t: drop every 5m bar that opens at or after cut_t
    (the look-ahead self-test recomputes everything on data that ends at the decision time)."""
    key = (path, cut_t)
    if key in _BARS:
        return _BARS[key]
    m = pd.read_csv(path or os.path.join(ROOT, "data", "NQ_5m.csv"))
    m = m.rename(columns={"time": "t", "open": "o", "high": "h", "low": "l", "close": "c"})
    if cut_t is not None:
        m = m[m.t < cut_t]
    m = m.sort_values("t").reset_index(drop=True)
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
    et = pd.to_datetime(m.t, unit="s", utc=True).dt.tz_convert("America/New_York")
    m["sess"] = (et + pd.Timedelta(hours=6)).dt.strftime("%Y-%m-%d")      # CME session: 18:00 ET -> 17:00 ET
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


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "explore"
    if cmd == "explore":
        scan(SEL)
    elif cmd == "oos":
        scan(OOS, subsplit=False)
    elif cmd == "feat":
        raw, T, S, F = base()
        t = sorted(raw["trades"], key=lambda x: x["entry_t"])[int(sys.argv[2]) if len(sys.argv) > 2 else 100]
        print(json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in F[int(t["entry_t"])].items()}, indent=0))
