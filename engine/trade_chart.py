"""Trade pictures: one chart renderer for every strategy's trades (owner 2026-10-23: "In ATLAS's brain I want to see
pictures of the trades it takes ... clear, very clear high-quality images with markups on it").

Strategies: LIT (live), LIT + Asia slot (cloud paper shadow), the ATLAS members ema_lon_vix / macd_sweep / sr_nyreclaim and
the stop-hunt candidates sh_asia / sh_trend. Read-only: nothing here decides, sizes or routes a trade.

The markups come from the strategies' own code, never re-derived guesses:
  LIT / LIT+Asia   engine/lit_live.run(keep=) (the live executor) -> its candidate + raw trade -> tools/lit_chart_data.record_of
                   (swept levels, sweep, inducement swings, 5m CISD, limit, tap, 1m CISD, breakeven) + engine/brain._checks
  ATLAS members    engine/second.run with cfg "_marks" -> each plugin's marks (engine/second.py _ema_marks / _md_marks /
  stop hunts       _sr_marks / _sh_marks: swings, EMA 21/50, MACD + divergence, the day's levels, the hunted pool ...)
                   + the strategy brain's rule checks
on bars cut at the moment of the picture (closed bars only). The picture separates "what the bot saw" from "what happened":
every candle that closed by the entry and every markup known at the entry is drawn bright ("k:" artists); the plan lines
(entry / stop / target) start at the entry ("plan:"); later candles, the breakeven move, the 15-minute check and the exit are
drawn faded / dashed ("a:"). tests/test_trade_chart.py checks it on every artist.

Picture: 1600 x 900 px (8 x 4.5 in at 200 dpi), dark theme of the apps, 5m candles from ~2 h before the setup to the exit,
a 1m panel around the entry when 1m bars exist, a "why it entered" panel with the rule checks, a legend, session shading
(Asia / London / New York) and an ET time axis. Palette PNG (~100-250 KB).

Where pictures are made:
  cloud    tools/cloud_monitor.py -> cloud_hook(): every new paper trade (each strategy) at entry, again at the exit;
           <out>/charts/<strategy>/<trade-id>.png + charts/index.json (newest KEEP per strategy) on the dashboard branch;
           tools/build_web_dashboard.py copies them to the site (data.json "charts").
  PC       engine/live.py LiveBot._chart_tick -> PcCharts (one background thread after routing; never delays LIT) ->
           logs/charts/, served by engine/chart_api.py at /api/next/charts and /api/next/chart/<id>.
  examples python -m engine.trade_chart backfill --strategy all --since 2026-07-01 [--n 20] -> research/lab/chart_examples/
           (backtest trades for the pages' examples, ~20 per strategy).
  one      python -m engine.trade_chart one --strategy ema_lon_vix --day 2026-10-13 [--out file.png]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import shutil
import sys
import threading
import time
from zoneinfo import ZoneInfo

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
ET = ZoneInfo("America/New_York")
VERSION = 1
PV, TICK = 2.0, 0.25
DPI, SIZE = 200, (8.0, 4.5)                      # 1600 x 900 px
KEEP = 60                                        # pictures kept per strategy (cloud / PC)
MAX_NEW = 10                                     # pictures drawn per cloud run at most
BUDGET_S = 50.0                                  # wall time of one cloud run's pictures
EXAMPLES = os.path.join(ROOT, "research", "lab", "chart_examples")
PC_DIR = os.path.join(ROOT, "logs", "charts")
DIR = "charts"

# the apps' dark theme (tools/web_public/index.html :root, tools/lit_trade_charts.py)
C = {"page": "#07080c", "panel": "#0d1016", "grid": "#1a1f2b", "ink": "#eef1f8", "ink2": "#a9b1c3", "muted": "#6f788b",
     "up": "#2ebd8f", "dn": "#f0506e", "good": "#2ee59d", "bad": "#ff5a7a", "warn": "#f7b955", "gold": "#f2c35b",
     "accent": "#6d7cff", "teal": "#3ee0c8", "bsl": "#ff9b5c", "ssl": "#6d9bff", "entry": "#d7dbe6", "pink": "#ff7ad9",
     "ema21": "#3ee0c8", "ema50": "#f7b955", "violet": "#b197fc"}
SESS = (("Asia", 1200, 1440, "#6d7cff"), ("London", 120, 300, "#f7b955"), ("New York", 570, 960, "#3ee0c8"))
EXIT_C = {"TARGET": C["good"], "STOP": C["bad"], "BE": C["ink2"], "EOD": C["warn"], "TIME": C["warn"], "FLAT": C["warn"],
          "CUT_T15": C["warn"], "CUT": C["warn"], "T15": C["warn"], "OPEN": C["accent"], "LIT": C["warn"]}
EXIT_TXT = {"TARGET": "target hit", "STOP": "stopped out", "BE": "breakeven stop", "EOD": "flat at 15:55", "TIME": "flat at 15:55",
            "FLAT": "flat (session end)", "CUT_T15": "cut by the 15-minute check", "CUT": "cut by the 15-minute check",
            "T15": "cut by the 15-minute check", "OPEN": "still open", "LIT": "closed when LIT entered"}

STRATS = {
    "lit": {"label": "live strategy (the 50K)", "short": "LIT", "group": "LIT · 50K", "be": (1.0, 1.25), "t15": True},
    "lit_asia": {"label": "LIT + Asia slot (paper shadow)", "short": "LIT+Asia", "group": "LIT shadow", "be": (1.0, 1.25), "t15": True},
    "ema_lon_vix": {"label": "London EMA trend pullback", "short": "EMA", "group": "ATLAS", "be": (1.0, 1.25), "t15": False},
    "macd_sweep": {"label": "MACD divergence at a liquidity sweep", "short": "MACD", "group": "ATLAS", "be": None, "t15": True},
    "sr_nyreclaim": {"label": "NY sweep-and-reclaim (S/R)", "short": "S/R", "group": "ATLAS", "be": None, "t15": True},
    "sh_asia": {"label": "Asia resweep hunt", "short": "Asia hunt", "group": "Candidate", "be": (1.0, 1.25), "t15": False},
    "sh_trend": {"label": "Trend inducement hunt", "short": "Trend hunt", "group": "Candidate", "be": (1.0, 1.25), "t15": False},
}
ORDER = list(STRATS)
LEVEL_WORDS = {"PDH": "previous day high", "PDL": "previous day low", "PWH": "previous week high", "PWL": "previous week low",
               "PMH": "previous month high", "PML": "previous month low", "NWOG": "weekly opening gap", "NDOG": "daily opening gap",
               "EQH": "equal highs (build-up)", "EQL": "equal lows (build-up)"}

_MPL_LOCK = threading.Lock()                     # pyplot is not thread safe: one picture at a time per process


# ------------------------------------------------------------------------------------------------ small helpers
def _et(t):
    return dt.datetime.fromtimestamp(int(t), ET)


def hm(t):
    return _et(t).strftime("%H:%M") if t is not None else "-"


def tday(t) -> str:
    return str((_et(t) + dt.timedelta(hours=6)).date())


def fpx(p) -> str:
    return "-" if p is None else f"{round(float(p) * 4) / 4:,.2f}"


def fusd(v) -> str:
    v = float(v or 0)
    return ("+" if v > 0 else "-" if v < 0 else "") + f"${abs(v):,.0f}"


def fr(v) -> str:
    v = float(v or 0)
    return ("+" if v > 0 else "-" if v < 0 else "") + f"{abs(v):.2f}R"


def _f(x, nd=2):
    try:
        v = float(x)
        return round(v, nd) if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def side_of(d) -> str:
    return "LONG" if int(d) > 0 else "SHORT"


def trade_id(t) -> str:
    """<day>_<HHMM ET of the entry>_<long|short> (tools/lit_chart_data.trade_id)."""
    return f"{t.get('day') or tday(t['entry_t'])}_{_et(t['entry_t']):%H%M}_{side_of(t['dir']).lower()}"


def chart_id(key, t) -> str:
    return f"{key}.{trade_id(t)}"


def level_words(lbl: str) -> str:
    """'PDL' -> 'previous day low (PDL)', 'Asia L' -> 'Asia low'."""
    if lbl in LEVEL_WORDS:
        return f"{LEVEL_WORDS[lbl]} ({lbl})"
    s = str(lbl)
    if s.endswith(" H"):
        s = s[:-2] + " high"
    elif s.endswith(" L"):
        s = s[:-2] + " low"
    return s


def lit_level_label(nm) -> str:
    try:
        from tools.lit_chart_data import level_label
        return level_words(level_label(nm))
    except Exception:
        return str(nm)


def norm_trade(t: dict) -> dict:
    """Any trade dict (engine/second rows, a cloud ledger row, lit_live / research LIT rows) -> the common keys."""
    if t.get("_norm"):
        return t
    d = t.get("dir")
    d = int(d) if d is not None else (1 if str(t.get("side", "")).upper() == "LONG" else -1)
    first = lambda *ks: next((t[k] for k in ks if t.get(k) is not None), None)
    ex = t.get("exit")
    kind = first("exit_kind", "exit_reason") or (ex if isinstance(ex, str) else None)
    kind = str(kind or "OPEN").upper()
    if kind in ("TIME", "TIME SAFETY"):
        kind = "EOD"
    xpx = first("exit_price", "exit_px")
    if xpx is None and isinstance(ex, (int, float)) and not isinstance(ex, bool):
        xpx = ex
    xt = t.get("exit_t") if isinstance(t.get("exit_t"), (int, float)) and not isinstance(t.get("exit_t"), bool) else t.get("exit_ts")
    out = {"_norm": True, "day": t.get("day") or tday(int(t["entry_t"])), "entry_t": int(t["entry_t"]), "dir": d,
           "exit_t": int(xt) if isinstance(xt, (int, float)) and kind != "OPEN" else None,
           "entry": _f(first("entry", "entry_px")), "stop": _f(first("stop0", "stop", "stop_px")),
           "target": _f(first("target", "target_px")), "exit": _f(xpx), "exit_kind": kind,
           "r": _f(first("r", "pnl_r", "R"), 3), "usd": _f(first("usd", "pnl_usd", "pnl")), "qty": int(first("qty") or 0),
           "risk_pts": _f(first("risk_pts")), "stop_now": _f(t.get("stop_now")), "last": _f(t.get("last"))}
    if out["risk_pts"] is None and out["entry"] is not None and out["stop"] is not None:
        out["risk_pts"] = round(abs(out["entry"] - out["stop"]), 2)
    return out


def _bars(x):
    """5m / 1m bars (DataFrame with time/open/high/low/close, engine.data.Bars or engine.lit XBars) -> dict of arrays."""
    if x is None:
        return None
    if isinstance(x, dict):
        return x
    if hasattr(x, "t") and hasattr(x, "o"):
        t = np.asarray(x.t, np.int64)
        return {"t": t, "o": np.asarray(x.o, float), "h": np.asarray(x.h, float), "l": np.asarray(x.l, float), "c": np.asarray(x.c, float)}
    if not len(x):
        return None
    d = x.sort_values("time").drop_duplicates("time", keep="last")
    return {"t": d["time"].to_numpy(np.int64), "o": d["open"].to_numpy(float), "h": d["high"].to_numpy(float),
            "l": d["low"].to_numpy(float), "c": d["close"].to_numpy(float)}


def _cut(B, a, z):
    if B is None:
        return None
    i, j = int(np.searchsorted(B["t"], a)), int(np.searchsorted(B["t"], z))
    if j <= i:
        return None
    return {k: v[i:j] for k, v in B.items()}


# ------------------------------------------------------------------------------------------------ specs
# A spec = everything one picture shows (no drawing code): the trade, the decision time, the markups by kind, the rule
# checks and a plain-words summary (the image's alt text). Built by lit_spec / second_spec / plain_spec.
def _base_spec(key, t, src):
    s = STRATS.get(key, {"label": key, "short": key})
    return {"v": VERSION, "key": key, "label": s["label"], "short": s["short"], "group": s.get("group"), "src": src,
            "trade": t, "known_t": int(t["entry_t"]), "levels": [], "points": [], "candles": [], "hlines": [], "spans": [],
            "lines": [], "boxes": [], "sub": None, "be": None, "tcheck": None, "notes": [], "checks": [], "setup": "",
            "target_label": None, "stop_label": None, "inset": None}


def _plan_words(sp):
    t = sp["trade"]
    rk = abs((t["entry"] or 0) - (t["stop"] or 0))
    rr = abs((t["target"] or t["entry"] or 0) - (t["entry"] or 0)) / rk if rk else 0
    return rk, rr


def summary(sp) -> str:
    """The picture in plain words (alt text): what it did, why, the plan and the result."""
    t = sp["trade"]
    rk, rr = _plan_words(sp)
    e = _et(t["entry_t"])
    res = ("still open" if t["exit_kind"] == "OPEN" else
           f"{EXIT_TXT.get(t['exit_kind'], t['exit_kind'].lower())} {fusd(t['usd'])} ({fr(t['r'])})")
    return (f"{sp['short']} {side_of(t['dir']).lower()} on {e:%a %Y-%m-%d} at {e:%H:%M} ET, entry {fpx(t['entry'])}"
            + (f": {sp['setup']}" if sp.get("setup") else "") +
            f". Stop {fpx(t['stop'])} ({rk:.1f} pts{', ' + sp['stop_label'] if sp.get('stop_label') else ''}), target "
            f"{fpx(t['target'])} ({sp.get('target_label') or f'{rr:.1f}R'}). Result: {res}.")


def plain_spec(key, t, src="paper", why=None):
    """A picture from the trade's own prices only (the setup could not be rebuilt on these bars)."""
    sp = _base_spec(key, t, src)
    sp["notes"].append(why or "setup markers unavailable: the bars at hand did not rebuild this trade; the prices are the trade's own")
    sp["summary"] = summary(sp)
    return sp


# ---- LIT (live strategy) and the LIT + Asia slot shadow
def lit_params(key="lit"):
    from engine import lit
    with open(os.path.join(ROOT, "live_model.json"), encoding="utf-8") as fh:
        base = json.load(fh).get("lit") or {}
    P = {**lit.DEFAULTS, **base}
    if key == "lit_asia":
        try:
            from engine import second
            sc = second.load_cfg()["strategies"].get("lit_asia") or {}
            P = {**P, **(sc.get("overrides") or {})}
        except Exception:
            pass
    return P


def lit_keep(df5, one_min, now, P):
    """engine/lit_live.run on bars closed by `now` (the live executor), returning its keep dict (M, C, R, B1, P)."""
    from engine import lit_live
    cut5 = df5[df5["time"] + 300 <= int(now)]
    keep = {}
    lit_live.run(cut5, P, one_min=one_min, now=int(now), keep=keep)
    return keep


def _lit_match(keep, t):
    R = keep.get("R") or {}
    best = None
    for x in (R.get("trades") or []) + (R.get("enter_now") or []):
        if int(x.get("dir", 0)) != int(t["dir"]) or x.get("entry_t") is None:
            continue
        gap = abs(int(x["entry_t"]) - int(t["entry_t"]))
        if gap <= 900 and (best is None or gap < best[0]):
            best = (gap, x)
    if best is None:
        return None, None
    x = best[1]
    z = next((c for c in keep.get("C") or [] if int(c["i"]) == int(x.get("i", -1)) and int(c["dir"]) == int(x["dir"])), None)
    return x, z


def lit_spec(key, t, keep, src="paper"):
    """The LIT picture of trade t from the live executor's own market / candidate / raw trade (keep = lit_live.run keep)."""
    from engine import lit
    M, P, B1 = keep.get("M"), keep.get("P") or lit_params(key), keep.get("B1")
    raw, z = _lit_match(keep, t)
    if M is None or raw is None or z is None:
        return plain_spec(key, t, src)
    t = dict(t)
    for k_, rk_ in (("entry", "entry_px"), ("stop", "stop_px"), ("target", "target_px"), ("exit", "exit_px")):
        if t.get(k_) is None and raw.get(rk_) is not None:
            t[k_] = round(float(raw[rk_]), 2)
    if t.get("risk_pts") is None and t.get("entry") is not None and t.get("stop") is not None:
        t["risk_pts"] = round(abs(t["entry"] - t["stop"]), 2)
    if not t.get("qty") and raw.get("qty"):
        t["qty"] = int(raw["qty"])
    sp = _base_spec(key, t, src)
    d = int(z["dir"])
    sp["_bars1"] = B1
    rec = None
    if raw.get("exit") != "OPEN":
        try:
            from tools.lit_chart_data import record_of
            B5 = lit.bars_5m(M)
            rec, _miss = record_of(M, B5, B1, z, raw, P)
        except Exception:
            rec = None
    lo = "low" if d > 0 else "high"
    # swept levels (the candidate's own names and prices; the bar each became known)
    L = M.levels(z["k"])
    for nm, pd_ in sorted(z["sw"].items(), key=lambda kv: -kv[1] * d):
        px = pd_ * d
        ki = next((x[2] for x in L if x[3] == nm and abs(x[1] - px) < 1e-6), None)
        t0 = int(M.t[ki]) if ki is not None and ki >= 0 else int(M.t[max(0, z["sweep_i"] - 60)])
        sp["levels"].append({"px": round(px, 2), "label": lit_level_label(nm), "t0": t0, "t1": int(M.t[z["ext_i"]]) + 300,
                             "role": "swept", "gid": "level"})
    sw_t, ext_t = int(M.t[z["sweep_i"]]), int(M.t[z["ext_i"]])
    sp["points"].append({"kind": "sweep", "t": ext_t, "px": round(z["ext_d"] * d, 2), "wick": True,
                         "label": f"sweep {lo} {fpx(z['ext_d'] * d)} · {z['depth_atr']:.2f} ATR"})
    # inducement swings (the I-a swings LIT counts: <= idm_a distance / age)
    gate = P.get("idm_a") or [9e9, 10 ** 9, 0]
    hi5, lo5 = (M.h, M.l) if d > 0 else (-M.l, -M.h)
    for dist, age in z.get("idm_a") or []:
        if dist <= gate[0] and age <= gate[1]:
            m = z["sweep_i"] - age
            seg = lo5[m + 1:z["ext_i"] + 1] < lo5[m]
            tk = m + 1 + int(np.argmax(seg)) if seg.any() else None
            sp["points"].append({"kind": "idm", "t": int(M.t[m]), "px": round(float(lo5[m]) * d, 2),
                                 "taken_t": int(M.t[tk]) if tk is not None else None,
                                 "label": f"IDM {fpx(lo5[m] * d)}"})
    # displacement: the biggest body between the extreme and the trigger (engine/lit.py candidates "disp")
    o_d, c_d = (M.o, M.c) if d > 0 else (-M.o, -M.c)
    ee, i = int(z["ext_i"]), int(z["i"])
    if i > ee:
        body = (c_d[ee + 1:i + 1] - o_d[ee + 1:i + 1]) / np.maximum(M.atr[ee + 1:i + 1], 1e-9)
        q = ee + 1 + int(np.argmax(body))
        sp["candles"].append({"kind": "disp", "t": int(M.t[q]), "label": f"displacement {z['disp']:.2f} ATR"})
    sp["hlines"].append({"kind": "cisd", "px": round(float(z["ref_d"]) * d, 2), "t0": int(M.t[z["ref_i"]]), "t1": int(M.t[i]) + 300,
                         "label": f"5m CISD {fpx(z['ref_d'] * d)}"})
    ep = min(float(z["ref_d"]), z["trig_c"])
    t0 = int(M.t[z["entry_i"]])
    lim = (rec or {}).get("limit") or {"px": round(ep * d, 2), "t0": t0, "t1": t0 + int(P["wait"]) * 300, "tap_t": None}
    t1 = lim.get("tap_t") or min(lim["t1"], int(t["entry_t"]))
    sp["hlines"].append({"kind": "limit", "px": lim["px"], "t0": lim["t0"], "t1": max(t1, lim["t0"] + 60), "tap_t": lim.get("tap_t"),
                         "label": f"limit {fpx(lim['px'])}" + (f" · tapped {hm(lim['tap_t'])}" if lim.get("tap_t") else f" ({int(P['wait']) * 5} min)")})
    c1 = (rec or {}).get("cisd1")
    if c1:
        sp["hlines"].append({"kind": "cisd1", "px": c1["px"], "t0": c1["ref_t"], "t1": c1["t"] + 60, "tf": 1,
                             "label": f"1m CISD {fpx(c1['px'])}"})
    elif raw.get("tf") == 1 or raw.get("trigger") == "LIT-1m":
        sp["points"].append({"kind": "cisd1", "t": int(t["entry_t"]) - 60, "px": None, "tf": 1, "label": "1m CISD close -> entry"})
    for bx in (rec or {}).get("boxes") or []:
        sp["boxes"].append({"label": bx["k"], "t0": bx["t0"], "t1": bx["t1"], "hi": bx["hi"], "lo": bx["lo"]})
    # breakeven (+1R, stop to entry + be_off) and the 15-minute check
    be_off = float(P.get("be_off") or 0.0)
    if rec and rec.get("be"):
        sp["be"] = {"t": rec["be"]["t"], "px": round(t["entry"] + d * be_off, 2)}
    tc = P.get("t_check")
    if tc:
        sp["tcheck"] = {"t": int(t["entry_t"]) + int(tc.get("at", 15)) * 60, "cut": t["exit_kind"] in ("CUT_T15", "CUT"),
                        "text": f"15-min check: cut if < +{tc.get('mfe', 0.5)}R so far and closing {tc.get('x', 0.3)}R below entry"}
    names = ", ".join(level_words(_short(nm)) for nm in z["swept"][:3])
    sp["setup"] = (f"swept the {names} by {z['depth_atr']:.2f} ATR, {len([p for p in sp['points'] if p['kind'] == 'idm'])} inducement "
                   f"swing(s) taken first, displacement {z['disp']:.2f} ATR, 5m CISD close through {fpx(z['ref_d'] * d)}, limit at "
                   f"{fpx(lim['px'])}" + (", 1m CISD entry" if raw.get("trigger") == "LIT-1m" or raw.get("tf") == 1 else ""))
    sp["stop_label"] = f"1 tick beyond the sweep {lo} {fpx(z['ext_d'] * d)}"
    sp["target_label"] = (rec or {}).get("target_label") or "VIX band"
    rk, rr = _plan_words(sp)
    sp["target_label"] = f"{sp['target_label']} · {rr:.1f}R"
    try:
        from engine import brain
        sp["checks"] = [{"name": c.get("label") or c["key"], "ok": None if c.get("ok") is None else bool(c["ok"]), "val": c.get("text")}
                        for c in brain._checks(M, z, P, False)]
    except Exception:
        pass
    if key == "lit_asia":
        m = _et(t["entry_t"]).hour * 60 + _et(t["entry_t"]).minute
        sp["notes"].append("Asia slot trade (18:00-02:00 ET, banked at 3R)" if (m >= 1080 or m < 120) else "LIT day trade (02:00-15:30 ET)")
    sp["summary"] = summary(sp)
    return sp


def _short(nm):
    try:
        from tools.lit_chart_data import level_label
        return level_label(nm)
    except Exception:
        return nm


# ---- the second strategies (engine/second.py marks)
def second_cfg(key):
    from engine import second
    return second.load_cfg()["strategies"].get(key)


def second_run(key, df5, one_min, now, lit=None):
    """engine/second.run for one strategy with its chart marks, on bars closed by `now`."""
    from engine import second
    sc = second_cfg(key)
    if not sc:
        raise KeyError(f"{key} is not in second_model.json")
    cut5 = df5[df5["time"] + 300 <= int(now)]
    cut1 = one_min
    if one_min is not None and hasattr(one_min, "slice"):
        cut1 = one_min.slice(0, int(np.searchsorted(np.asarray(one_min.t) + 60, int(now), side="right")))
    elif one_min is not None:
        cut1 = one_min[one_min["time"] + 60 <= int(now)]
    r = second.run(cut5, one_min=cut1, now=int(now), cfg={"strategies": {key: {**sc, "_marks": True}}}, lit=lit or [])
    return r["strategies"][key]


def second_spec(key, t, res, src="paper"):
    """The picture of trade t of strategy `key` from that strategy's run result (second_run: trades, brain, marks)."""
    mk = (res or {}).get("marks") or {}
    m = mk.get(str(int(t["entry_t"])))
    if not m:
        return plain_spec(key, t, src, (res or {}).get("error") or mk.get("error"))
    sp = _base_spec(key, t, src)
    d = int(t["dir"])
    lo, up = ("low", "up") if d > 0 else ("high", "down")
    kind = m["kind"]
    if kind == "ema":
        if m.get("swing"):
            s = m["swing"]
            sp["points"].append({"kind": "swing", "t": s["t"], "px": s["px"], "taken_t": s.get("taken_t"),
                                 "label": f"swing {lo} {fpx(s['px'])} (swept)"})
        sp["spans"].append({"kind": "pullback", "t0": m["run"]["t0"], "t1": m["run"]["t1"] + 300,
                            "label": f"pullback to the EMA 50" + (" (touched)" if m["touch50"]["ok"] else "")})
        sp["points"].append({"kind": "sweep", "t": m["ext"]["t"], "px": m["ext"]["px"], "wick": True,
                             "label": f"pullback {lo} {fpx(m['ext']['px'])}"})
        sp["hlines"].append({"kind": "cisd", "px": m["cisd"]["px"], "t0": m["cisd"]["ref_t"], "t1": m["cisd"]["t"] + 300,
                             "label": f"5m CISD {fpx(m['cisd']['px'])}"})
        sp["candles"].append({"kind": "cisd_close", "t": m["cisd"]["t"], "label": "CISD close"})
        rows = (m.get("ema") or {}).get("rows") or []
        if rows:
            sp["lines"].append({"name": "EMA 21 (5m)", "gid": "ema21", "color": C["ema21"], "pts": [[r[0] + 300, r[1]] for r in rows]})
            sp["lines"].append({"name": "EMA 50 (5m)", "gid": "ema50", "color": C["ema50"], "pts": [[r[0] + 300, r[2]] for r in rows]})
        sp["notes"].append("Trend: " + m["trend"]["text"])
        sp["setup"] = (f"15m and 1h trend {up} (EMA 21 vs 50), a pullback to the 5m EMA 50 swept the swing {lo} "
                       f"{fpx((m.get('swing') or {}).get('px'))}, then a 5m CISD close back {up} through {fpx(m['cisd']['px'])}")
        sp["stop_label"] = f"1 tick beyond the pullback {lo} {fpx(m['ext']['px'])}"
        sp["target_label"] = "VIX band"
    elif kind == "macd":
        lv = m["level"]
        lv = {**lv, "label": lit_level_label(lv["name"]) if lv.get("name") else lv["label"]}
        sp["levels"].append({"px": lv["px"], "label": lv["label"], "t0": lv["t"] - 3 * 3600,
                             "t1": m["sweep"]["ext_t"] + 300, "role": "swept", "gid": "level"})
        sp["points"].append({"kind": "sweep", "t": m["sweep"]["ext_t"], "px": m["sweep"]["ext_px"], "wick": True,
                             "label": f"sweep {lo} {fpx(m['sweep']['ext_px'])} · {m['sweep']['depth'] or 0:.2f} ATR"})
        sp["hlines"].append({"kind": "cisd", "px": m["cisd"]["px"], "t0": m["sweep"]["ext_t"], "t1": m["cisd"]["t"] + 300,
                             "label": f"5m CISD {fpx(m['cisd']['px'])}"})
        sp["candles"].append({"kind": "cisd_close", "t": m["cisd"]["t"], "label": "CISD close"})
        p1, p2 = m["div"]["p1"], m["div"]["p2"]
        sub = {"kind": "macd", "cols": m["macd"]["cols"], "rows": [[r[0] + 300] + r[1:] for r in m["macd"]["rows"]],
               "div": {"p1": [p1[0] + 300 if p1[0] else None, p1[2]], "p2": [p2[0] + 300, p2[2]]}, "osc": m["macd"].get("osc")}
        sp["sub"] = sub
        if p1[0]:
            sp["div"] = {"p1": [p1[0], p1[1]], "p2": [p2[0], p2[1]]}
        hl = "lower low" if d > 0 else "higher high"
        sp["setup"] = (f"the {lv['label']} {fpx(lv['px'])} was swept by {m['sweep']['depth'] or 0:.2f} ATR to a {hl} while the MACD "
                       f"line made a {'higher low' if d > 0 else 'lower high'} ({p1[2]:.1f} -> {p2[2]:.1f}): divergence; "
                       f"then a 5m CISD close through {fpx(m['cisd']['px'])}")
        sp["stop_label"] = f"1 tick beyond the sweep {lo} {fpx(m['sweep']['ext_px'])}"
        sp["target_label"] = "VIX band"
    elif kind == "sr":
        et_ = int(t["entry_t"])
        for x in m.get("levels") or []:
            this = bool(x.get("this"))
            sp["levels"].append({"px": x["px"], "label": x["label"], "t0": x["known_t"],
                                 "t1": (m["sweep"]["ext_t"] or m["sweep"]["t"]) + 300 if this else et_,
                                 "role": "swept" if this else ("taken" if x.get("swept_t") and x["swept_t"] < et_ else "level"),
                                 "gid": "level" if this else "sr_level"})
        sp["points"].append({"kind": "sweep", "t": m["sweep"]["ext_t"] or m["sweep"]["t"], "px": m["sweep"]["ext_px"], "wick": True,
                             "label": f"sweep {lo} {fpx(m['sweep']['ext_px'])}"})
        if m.get("idm"):
            sp["points"].append({"kind": "idm", "t": m["idm"]["t"], "px": m["idm"]["px"], "label": f"IDM {fpx(m['idm']['px'])}"})
        rc = m["reclaim"]
        sp["candles"].append({"kind": "reclaim", "t": rc["t"], "label": f"reclaim close {rc['body_atr'] or 0:.2f} ATR"})
        sp["setup"] = (f"the {m['level']['label']} {fpx(m['level']['px'])} was swept after an inducement and a strong 5m close "
                       f"(body {rc['body_atr'] or 0:.2f} ATR) reclaimed it")
        sp["stop_label"] = f"1 tick beyond the sweep {lo} {fpx(m['sweep']['ext_px'])}"
        sp["target_label"] = "2R"
        sp["notes"].append(f"Levels of the day known at the entry: {len(m.get('levels') or [])}")
    elif kind == "stophunt":
        pl = m["pool"]
        sp["levels"].append({"px": pl["px"], "label": f"pool: {pl['label']}", "t0": pl["t"] - 2 * 3600,
                             "t1": (m["hunt"]["ext_t"] or pl["t"]) + 300, "role": "swept", "gid": "pool"})
        sp["points"].append({"kind": "sweep", "t": m["hunt"]["ext_t"] or m["hunt"]["t"], "px": m["hunt"]["ext_px"], "wick": True,
                             "label": f"hunt {lo} {fpx(m['hunt']['ext_px'])} · {m['hunt']['depth'] or 0:.2f} ATR"})
        if m.get("resweep") and m.get("mode") in ("rs", "rs_pool", "rs_ext", "rs_idm", "rs_or_idm"):
            sp["points"].append({"kind": "resweep", "t": m["resweep"]["t"], "px": None, "label": "resweep"})
        if m.get("idm") and m["idm"].get("t"):
            sp["points"].append({"kind": "idm", "t": m["idm"]["t"], "px": m["idm"]["px"], "label": f"IDM {fpx(m['idm']['px'])}"})
        dp = m["disp"]
        sp["candles"].append({"kind": "disp", "t": dp["t"],
                              "label": f"strong candle {dp['atr_x'] or 0:.2f} ATR"})
        if m.get("mss") and m["mss"].get("px") is not None:
            sp["hlines"].append({"kind": "mss", "px": m["mss"]["px"], "t0": m["mss"]["t"] - 1800, "t1": m["mss"]["t"] + 300,
                                 "label": f"structure {fpx(m['mss']['px'])}"})
        if m.get("limit"):
            L = m["limit"]
            sp["hlines"].append({"kind": "limit", "px": L["px"], "t0": L["t0"], "t1": max(L["t0"] + 60, min(L["t1"], int(t["entry_t"]))),
                                 "label": f"limit {fpx(L['px'])} (30 min)"})
        sp["notes"].append("Target: " + str(m.get("dol") or "2R"))
        sp["setup"] = (f"the {pl['label']} {fpx(pl['px'])} was run by {m['hunt']['depth'] or 0:.2f} ATR"
                       + (", a resweep followed" if any(p["kind"] == "resweep" for p in sp["points"]) else "")
                       + (", an inducement swing was taken" if m.get("idm") else "")
                       + f", then a {dp['atr_x'] or 0:.2f} ATR candle closed back through the pool and the last swing")
        sp["stop_label"] = f"1 tick beyond the hunt {lo} {fpx(m['hunt']['ext_px'])}"
        sp["target_label"] = "2R"
    # rule checks: the marks' own (EMA / stop hunts), else the brain's when it is about this trade
    ch = m.get("checks")
    b = (res or {}).get("brain") or {}
    if not ch and (b.get("focus") or {}).get("t") == int(t["entry_t"]):
        ch = b.get("checks")
    sp["checks"] = [{"name": c.get("name"), "ok": None if c.get("ok") is None else bool(c["ok"]), "val": c.get("val")} for c in (ch or [])]
    be = STRATS.get(key, {}).get("be")
    if be:
        sp["be_rule"] = be
    if STRATS.get(key, {}).get("t15"):
        sp["tcheck"] = {"t": int(t["entry_t"]) + 900, "cut": t["exit_kind"] in ("CUT", "CUT_T15", "T15"),
                        "text": "15-min check: cut if the trade is not working after 15 minutes"}
    rk, rr = _plan_words(sp)
    sp["target_label"] = f"{sp['target_label']} · {rr:.1f}R" if sp["target_label"] != "2R" else f"2R ({rr:.1f}R)"
    sp["summary"] = summary(sp)
    return sp


# ------------------------------------------------------------------------------------------------ drawing
class _Labels:
    """Annotation placer: each label moves up / down in steps until it overlaps no earlier one (tools/lit_trade_charts)."""

    def __init__(self):
        self.L = []

    def add(self, ax, x, y, text, col, ha="left", va="bottom", dy=2, dx=0, fs=5.6, bold=False, bg=True, prio=2, box=None, mx=None,
            gid=None):
        a = ax.annotate(text, xy=(x, y), xytext=(dx, dy), textcoords="offset points", ha=ha, va=va, fontsize=fs, color=col,
                        fontweight="bold" if bold else "normal", zorder=15, annotation_clip=True,
                        bbox=box or (dict(boxstyle="round,pad=0.18", fc=C["panel"], ec="none", alpha=0.62) if bg else None))
        a._mx = mx
        if gid:
            a.set_gid(gid)
        self.L.append((prio, len(self.L), a))
        return a

    def place(self, fig, fixed=()):
        rr = fig.canvas.get_renderer()
        placed = [f.get_window_extent(rr).padded(2) for f in fixed]
        k_pt = 72.0 / fig.dpi
        for _p, _i, a in sorted(self.L, key=lambda z: z[:2]):
            bb = a.get_window_extent(rr)
            ab = a.axes.bbox
            if bb.x1 > ab.x1 - 2:                      # keep it inside the panel horizontally
                a.xyann = (a.xyann[0] - (bb.x1 - ab.x1 + 4) * k_pt, a.xyann[1])
            elif bb.x0 < ab.x0 + 2:
                a.xyann = (a.xyann[0] + (ab.x0 - bb.x0 + 4) * k_pt, a.xyann[1])
            base = tuple(a.xyann)
            best = None
            tries = [(k, 0) for k in (0, 1, -1, 2, -2, 3, -3, 4, -4, 5, -5, 6, -6, 8, -8, 10, -10)]
            tries += [(k, hx) for hx in (-45, 45, -90, 90) for k in (0, 1, -1, 2, -2, 3, -3)]
            for k, hx in tries:
                if a._mx is not None and abs(k) > a._mx:
                    continue
                a.xyann = (base[0] + hx, base[1] + k * 7.0)
                bb = a.get_window_extent(rr).padded(2.0)
                ab = a.axes.bbox
                inside = bb.y0 >= ab.y0 - 1 and bb.y1 <= ab.y1 + 1 and bb.x0 >= ab.x0 - 2 and bb.x1 <= ab.x1 + 2
                if inside and not any(bb.overlaps(p) for p in placed):
                    best = bb
                    break
            if best is None:
                if a._mx is not None:
                    a.set_visible(False)
                    continue
                a.xyann = base
                best = a.get_window_extent(rr).padded(2.0)
            placed.append(best)


class _X:
    """unix seconds -> x (bar i spans [i, i+1), gaps removed like a trading chart)."""

    def __init__(self, t, secs):
        self.t = np.asarray(t, np.int64)
        self.s = int(secs)

    def __call__(self, ts):
        if ts is None:
            return None
        i = int(np.searchsorted(self.t, int(ts), side="right")) - 1
        if i < 0:
            return (int(ts) - int(self.t[0])) / self.s
        if i == len(self.t) - 1:
            return i + (int(ts) - int(self.t[i])) / self.s
        return i + min(1.0, (int(ts) - int(self.t[i])) / self.s)


def _fade(hex_col, k=0.45):
    """a colour mixed toward the panel (faded = after the entry)."""
    import matplotlib.colors as mc
    a = np.array(mc.to_rgb(hex_col)); b = np.array(mc.to_rgb(C["panel"]))
    return tuple(a * k + b * (1 - k))


def _candles(ax, B, X, known_t, secs, reg, w=0.64, gid="candles"):
    from matplotlib.collections import LineCollection, PolyCollection
    n = len(B["t"])
    known = (B["t"] + secs) <= known_t
    for flag, tag in ((True, "k"), (False, "a")):
        idx = np.flatnonzero(known == flag)
        if not len(idx):
            continue
        up = B["c"][idx] >= B["o"][idx]
        cols = [(C["up"] if u else C["dn"]) if flag else _fade(C["up"] if u else C["dn"], 0.42) for u in up]
        segs = [[(i + 0.5, B["l"][i]), (i + 0.5, B["h"][i])] for i in idx]
        lc = LineCollection(segs, colors=cols, linewidths=0.75 if secs == 300 else 0.7, zorder=3, capstyle="butt")
        lc.set_gid(f"{tag}:{gid}")
        ax.add_collection(lc)
        polys = []
        for i in idx:
            lo_, hi_ = min(B["o"][i], B["c"][i]), max(B["o"][i], B["c"][i])
            if hi_ - lo_ < 0.25:
                hi_ = lo_ + 0.25
            polys.append([(i + 0.5 - w / 2, lo_), (i + 0.5 + w / 2, lo_), (i + 0.5 + w / 2, hi_), (i + 0.5 - w / 2, hi_)])
        pc = PolyCollection(polys, facecolors=cols, edgecolors=cols, linewidths=0.3, zorder=3)
        pc.set_gid(f"{tag}:{gid}")
        ax.add_collection(pc)
        reg.append({"gid": f"{tag}:{gid}", "t0": int(B["t"][idx[0]]), "t1": int(B["t"][idx[-1]]) + secs, "n": int(len(idx))})


def _tag(ax, y, text, col, ink="#0b0d12", gid=None):
    a = ax.annotate(text, xy=(1.0, y), xycoords=("axes fraction", "data"), xytext=(3, 0), textcoords="offset points", va="center",
                    ha="left", fontsize=5.9, fontweight="bold", color=ink, annotation_clip=False, zorder=20,
                    bbox=dict(boxstyle="round,pad=0.25,rounding_size=0.25", fc=col, ec="none"))
    if gid:
        a.set_gid(gid)
    return a


def _spread(ys, gap):
    order = sorted(range(len(ys)), key=lambda i: ys[i])
    out = list(ys)
    for a, b in zip(order, order[1:]):
        if out[b] - out[a] < gap:
            out[b] = out[a] + gap
    return out


def _bar_at(B, ts):
    if ts is None:
        return None
    i = int(np.searchsorted(B["t"], int(ts), side="right")) - 1
    return i if 0 <= i < len(B["t"]) else None


def _exit_bar(B, t, secs):
    """index of the bar the exit happened in (the bar at exit_t or the one before, whichever traded the exit price)."""
    xt, px = t.get("exit_t"), t.get("exit")
    if xt is None:
        return len(B["t"]) - 1
    cands = [i for i in (_bar_at(B, xt), _bar_at(B, xt - 1)) if i is not None]
    for i in cands:
        if px is None or B["l"][i] - 0.26 <= px <= B["h"][i] + 0.26:
            return i
    return cands[0] if cands else len(B["t"]) - 1


def _be_move(B, t, rule, secs):
    """(time, stop price) of the breakeven move: the first bar after the fill whose extreme reached +1R (display: the
    strategy's own rule be_at / be_off; the walk itself is the strategy's)."""
    if not rule or t.get("entry") is None or t.get("stop") is None:
        return None
    at, off = rule
    d = int(t["dir"])
    risk = abs(t["entry"] - t["stop"])
    if risk <= 0:
        return None
    lvl = t["entry"] + d * at * risk
    i0 = int(np.searchsorted(B["t"], int(t["entry_t"])))
    i1 = int(np.searchsorted(B["t"], int(t["exit_t"]) if t.get("exit_t") else int(B["t"][-1]) + 1, side="right"))
    for i in range(i0, min(i1, len(B["t"]))):
        if (B["h"][i] >= lvl) if d > 0 else (B["l"][i] <= lvl):
            return {"t": int(B["t"][i]), "px": round(t["entry"] + d * off, 2)}
        if (B["l"][i] <= t["stop"]) if d > 0 else (B["h"][i] >= t["stop"]):
            return None
    return None


def render(sp, bars5, bars1=None, path=None, dpi=DPI, size=SIZE) -> dict:
    """Draw spec sp on 5m bars (and 1m bars for the entry panel) -> PNG at path. Returns meta: path, w, h, bytes, alt,
    marks (every drawn markup: gid, times) for the tests."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import FancyBboxPatch, Patch, Rectangle
    with _MPL_LOCK:
        plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 6.0, "axes.edgecolor": C["grid"], "text.color": C["ink"],
                             "axes.labelcolor": C["ink2"], "xtick.color": C["muted"], "ytick.color": C["muted"]})
        return _render(sp, _bars(bars5), _bars(bars1) if bars1 is not None else None, path, dpi, size, plt, Line2D, FancyBboxPatch,
                       Patch, Rectangle)


def _window(sp, B5):
    t = sp["trade"]
    times = [p["t"] for p in sp["points"] if p.get("t")] + [x["t0"] for x in sp["hlines"] if x.get("t0")] + \
            [x["t0"] for x in sp["spans"] if x.get("t0")] + [c["t"] for c in sp["candles"] if c.get("t")]
    if sp.get("div"):
        times.append(sp["div"]["p1"][0])
    setup_t = min([x for x in times if x] + [int(t["entry_t"])])
    setup_t = max(setup_t, int(t["entry_t"]) - 8 * 3600)                 # a level known days ago: start near the setup
    a = min(setup_t - 2 * 3600, int(t["entry_t"]) - int(2.5 * 3600))
    end = int(t["exit_t"]) + 1800 if t.get("exit_t") else int(B5["t"][-1]) + 300
    end = max(end, int(t["entry_t"]) + 3600)
    w = _cut(B5, a, end)
    if w is not None and len(w["t"]) > 300:                               # a long trade: keep the setup, trim the start
        w = {k: v[-300:] for k, v in w.items()}
    return w


def _render(sp, B5, B1, path, dpi, size, plt, Line2D, FancyBboxPatch, Patch, Rectangle):
    t = sp["trade"]
    d = int(t["dir"])
    known_t = int(t["entry_t"])                       # what the bot saw: every bar closed by the entry
    reg = []
    W = _window(sp, B5)
    if W is None or not len(W["t"]):
        raise ValueError("no 5m bars around the trade")
    X = _X(W["t"], 300)
    n = len(W["t"])
    has_sub = bool(sp.get("sub") and (sp["sub"].get("rows") or []))
    inset = None
    if B1 is not None:
        inset = _cut(B1, int(t["entry_t"]) - 1500, min(int(t["exit_t"]) + 300 if t.get("exit_t") else int(t["entry_t"]) + 1800,
                                                       int(t["entry_t"]) + 1800))
        if inset is not None and (len(inset["t"]) < 8 or not (inset["t"][0] <= int(t["entry_t"]) <= inset["t"][-1])):
            inset = None
    fig = plt.figure(figsize=size, dpi=dpi, facecolor=C["page"])
    L = _Labels()
    left, right_main = 0.012, 0.705
    top = 0.865
    if has_sub:
        ax = fig.add_axes([left, 0.33, right_main - left, top - 0.33])
        axs = fig.add_axes([left, 0.155, right_main - left, 0.165], sharex=ax)
    else:
        ax = fig.add_axes([left, 0.155, right_main - left, top - 0.155])
        axs = None
    ax.set_facecolor(C["panel"])
    for s_ in ax.spines.values():
        s_.set_color(C["grid"])
    # y range: bars + plan; a far target becomes an edge tag
    ys = list(W["l"]) + list(W["h"]) + [v for v in (t["stop"], t["entry"], t.get("exit")) if v is not None]
    lo, hi = min(ys), max(ys)
    rng = max(hi - lo, 4.0)
    tgt_in = t["target"] is not None and (lo - 0.6 * rng <= t["target"] <= hi + 0.6 * rng)
    if tgt_in:
        lo, hi = min(lo, t["target"]), max(hi, t["target"])
    pad = (hi - lo) * 0.07 + 2
    ax.set_ylim(lo - pad * 1.6, hi + pad * 2.2)
    ax.set_xlim(0, n + 4)
    fixed, keyart = [], []
    ax.grid(axis="y", color=C["grid"], lw=0.45, zorder=0)
    ax.yaxis.tick_right()
    ax.tick_params(axis="both", length=0, labelsize=5.6, pad=2)
    from matplotlib.ticker import FuncFormatter
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    # ET time axis: every hour (30 min when short), the date at each new day
    span_h = (int(W["t"][-1]) - int(W["t"][0])) / 3600
    step = 1800 if span_h <= 5 else 3600 if span_h <= 12 else 7200
    off = lambda ts: int(_et(ts).utcoffset().total_seconds())
    ticks = [(i, int(ts)) for i, ts in enumerate(W["t"]) if (int(ts) + off(ts)) % step == 0 and 1 <= i <= n - 2]
    tick_ax = axs if axs is not None else ax
    tick_ax.set_xticks([i for i, _ in ticks])
    tick_ax.set_xticklabels([(_et(ts).strftime("%H:%M") if _et(ts).hour or _et(ts).minute else _et(ts).strftime("%a %H:%M"))
                             for _, ts in ticks])
    if axs is not None:
        plt.setp(ax.get_xticklabels(), visible=False)
    tick_ax.set_xlabel("time (ET)", fontsize=5.4, color=C["muted"], labelpad=1.5)
    # session shading (Asia 20:00-00:00, London 02:00-05:00, New York 09:30-16:00), a band + its name on top
    mods = np.array([_et(ts).hour * 60 + _et(ts).minute for ts in W["t"]])
    for name, a0, a1, col in SESS:
        inside = (mods >= a0) & (mods < a1)
        if not inside.any():
            continue
        runs = np.split(np.flatnonzero(inside), np.flatnonzero(np.diff(np.flatnonzero(inside)) > 1) + 1)
        for r_ in runs:
            if not len(r_):
                continue
            sp_ = ax.axvspan(r_[0], r_[-1] + 1, color=col, alpha=0.045, lw=0, zorder=0)
            sp_.set_gid("sessions")
            if axs is not None:
                axs.axvspan(r_[0], r_[-1] + 1, color=col, alpha=0.045, lw=0, zorder=0)
            fixed.append(ax.text(r_[0] + 0.3, 0.992, name, transform=ax.get_xaxis_transform(), ha="left", va="top", fontsize=5.0,
                                 color=col, alpha=0.9, zorder=2))
    # LIT session boxes (levels)
    for bx in sp.get("boxes") or []:
        if bx["t1"] > known_t:                         # a box still forming at the entry: its closed bars only
            m_ = (W["t"] >= bx["t0"]) & ((W["t"] + 300) <= known_t)
            if not m_.any():
                continue
            bx = {**bx, "t1": known_t, "hi": float(W["h"][m_].max()), "lo": float(W["l"][m_].min())}
        x0, x1 = X(bx["t0"]), X(bx["t1"])
        if x1 <= 0 or x0 >= n:
            continue
        col = {"Asia": "#6d7cff", "London": "#f7b955", "NY": "#3ee0c8"}.get(bx["label"], C["muted"])
        ax.add_patch(Rectangle((max(0, x0), bx["lo"]), x1 - max(0, x0), bx["hi"] - bx["lo"], facecolor=col, alpha=0.05, edgecolor=col,
                               lw=0.5, ls=(0, (2, 2)), zorder=1, gid="k:box"))
        reg.append({"gid": "k:box", "t0": bx["t0"], "t1": bx["t1"]})
    _candles(ax, W, X, known_t, 300, reg)
    # what the bot saw | what happened
    xe = X(known_t)
    ax.axvline(xe, color=C["ink2"], lw=0.5, ls=(0, (1, 2)), zorder=2, alpha=0.7)
    fixed.append(ax.text(xe - 0.4, 0.008, "what the bot saw", transform=ax.get_xaxis_transform(), ha="right", va="bottom", fontsize=5.0,
                         color=C["ink2"], zorder=2))
    fixed.append(ax.text(xe + 0.4, 0.008, "what happened", transform=ax.get_xaxis_transform(), ha="left", va="bottom", fontsize=5.0,
                         color=C["muted"], zorder=2))
    lvl_col = C["ssl"] if d > 0 else C["bsl"]
    # levels
    for lv in sp["levels"]:
        x0 = max(0.0, X(lv["t0"]) if lv.get("t0") else 0.0)
        x1 = X(min(lv.get("t1") or known_t, known_t))
        if x1 is None or x1 <= x0:
            x1 = x0 + 1
        swept = lv.get("role") == "swept"
        col = lvl_col if swept else (C["muted"] if lv.get("role") == "taken" else C["violet"])
        ls = (0, (4, 2.5)) if swept else (0, (2, 2.5))
        gid = f"k:{lv.get('gid') or 'level'}"
        ln, = ax.plot([x0, x1], [lv["px"], lv["px"]], color=col, lw=1.0 if swept else 0.7, ls=ls, zorder=5, gid=gid)
        reg.append({"gid": gid, "t0": lv.get("t0"), "t1": min(lv.get("t1") or known_t, known_t)})
        L.add(ax, x0 + 0.3, lv["px"], f"{lv['label']} {fpx(lv['px'])}" + (" (swept)" if swept else ""), col,
              va="bottom" if (d > 0) == swept else "top", dy=1.5 if (d > 0) == swept else -1.5, prio=2 if swept else 4,
              mx=None if swept else 3, fs=5.4, gid=gid)
    # spans (EMA pullback)
    for s_ in sp["spans"]:
        x0, x1 = X(s_["t0"]), X(min(s_["t1"], known_t))
        r = ax.axvspan(x0, x1, ymin=0.0, ymax=0.035, color=C["gold"], alpha=0.55, lw=0, zorder=4)
        r.set_gid("k:span")
        reg.append({"gid": "k:span", "t0": s_["t0"], "t1": min(s_["t1"], known_t)})
        L.add(ax, x0, ax.get_ylim()[0], s_["label"], C["gold"], va="bottom", dy=6, fs=5.2, bg=False, prio=4, mx=3, gid="k:span")
    # extra lines (EMA 21 / 50): bright up to the entry, faded after
    for ln_ in sp["lines"]:
        pts = [p for p in ln_["pts"] if p[1] is not None]
        kp = [p for p in pts if p[0] <= known_t and X(p[0]) >= 0]
        ap = [p for p in pts if p[0] >= known_t - 300 and X(p[0]) >= 0]
        if kp:
            ax.plot([X(p[0]) for p in kp], [p[1] for p in kp], color=ln_["color"], lw=0.95, zorder=4, gid=f"k:{ln_['gid']}")
            reg.append({"gid": f"k:{ln_['gid']}", "t0": kp[0][0], "t1": kp[-1][0]})
        if ap:
            ax.plot([X(p[0]) for p in ap], [p[1] for p in ap], color=_fade(ln_["color"], 0.55), lw=0.8, ls=(0, (3, 2)), zorder=4,
                    gid=f"a:{ln_['gid']}")
            reg.append({"gid": f"a:{ln_['gid']}", "t0": ap[0][0], "t1": ap[-1][0]})
    # highlighted candles (displacement / CISD close / reclaim / strong candle)
    ccol = {"disp": C["accent"], "cisd_close": C["accent"], "reclaim": C["teal"]}
    for cd in sp["candles"]:
        i = _bar_at(W, cd["t"])
        if i is None or W["t"][i] + 300 > known_t:
            continue
        col = ccol.get(cd["kind"], C["accent"])
        keyart.append(ax.add_patch(FancyBboxPatch((i + 0.08, W["l"][i]), 0.84, W["h"][i] - W["l"][i],
                                                  boxstyle="round,pad=0.05,rounding_size=0.2", facecolor="none", edgecolor=col, lw=0.9,
                                                  zorder=16, gid=f"k:{cd['kind']}")))
        reg.append({"gid": f"k:{cd['kind']}", "t0": int(W["t"][i]), "t1": int(W["t"][i]) + 300})
        if cd["kind"] != "cisd_close":
            L.add(ax, i + 0.5, W["h"][i] if d > 0 else W["l"][i], cd["label"], col, ha="center", va="bottom" if d > 0 else "top",
                  dy=3 if d > 0 else -3, fs=5.3, prio=3, mx=5, gid=f"k:{cd['kind']}")
    # horizontal segments (CISD, limit, 1m CISD, last swing)
    hcol = {"cisd": C["accent"], "limit": C["teal"], "cisd1": C["pink"], "mss": C["violet"]}
    for h_ in sp["hlines"]:
        if h_.get("tf") == 1:
            continue
        col = hcol.get(h_["kind"], C["accent"])
        x0, x1 = X(h_["t0"]), X(min(h_["t1"], known_t))
        gid = f"k:{h_['kind']}"
        ax.plot([x0, max(x1, x0 + 0.6)], [h_["px"], h_["px"]], color=col, lw=1.1 if h_["kind"] == "cisd" else 0.9,
                ls="-" if h_["kind"] == "cisd" else (0, (2, 1.5)), zorder=6, gid=gid)
        reg.append({"gid": gid, "t0": h_["t0"], "t1": min(h_["t1"], known_t)})
        if h_.get("tap_t") and h_["tap_t"] <= known_t:
            ax.plot([X(h_["tap_t"]) + 0.1], [h_["px"]], marker="D", ms=2.8, color=col, zorder=9, gid=gid)
        L.add(ax, max(x1, x0 + 0.6), h_["px"], h_["label"], col, ha="right", va="top" if d > 0 else "bottom", dy=-2 if d > 0 else 2,
              fs=5.3, prio=2, mx=6, gid=gid)
    # points: sweep extreme (wick highlight), inducement, swing, resweep, 1m CISD
    for p in sp["points"]:
        if p.get("tf") == 1 or p.get("t") is None or p["t"] > known_t:
            continue
        i = _bar_at(W, p["t"])
        if i is None:
            continue
        xi = i + 0.5
        gid = f"k:{p['kind']}"
        if p["kind"] == "sweep":
            col = C["warn"]
            lv = next((x["px"] for x in sp["levels"] if x.get("role") == "swept"), None)
            y0 = W["l"][i] if d > 0 else W["h"][i]
            y1 = (lv if lv is not None else (min(W["o"][i], W["c"][i]) if d > 0 else max(W["o"][i], W["c"][i])))
            yb, yt = min(y0, y1), max(y0, y1)
            keyart.append(ax.add_patch(FancyBboxPatch((i + 0.18, yb), 0.64, max(yt - yb, 0.5), boxstyle="round,pad=0.06,rounding_size=0.25",
                                                      facecolor=col, alpha=0.30, edgecolor=col, lw=0.8, zorder=16, gid=gid)))
            keyart += ax.plot([xi], [p["px"]], marker="o", ms=4.6, mfc="none", mec=col, mew=1.2, zorder=17, gid=gid)
            L.add(ax, xi, p["px"], p["label"], col, ha="center", va="top" if d > 0 else "bottom", dy=-5 if d > 0 else 5, prio=1, fs=5.5,
                  gid=gid)
        elif p["kind"] in ("idm", "swing"):
            col = C["gold"]
            x1 = (X(p["taken_t"]) + 0.5) if p.get("taken_t") and p["taken_t"] <= known_t else xi + 3
            ax.plot([xi, x1], [p["px"], p["px"]], color=col, lw=0.9, ls=(0, (1, 1.3)), zorder=6, gid=gid)
            keyart += ax.plot([xi], [p["px"]], marker="^" if d > 0 else "v", ms=4.6, color=col, mec=C["page"], mew=0.4, zorder=17, gid=gid)
            L.add(ax, xi, p["px"], p["label"], col, ha="center", va="top" if d > 0 else "bottom", dy=-4 if d > 0 else 4, prio=2, fs=5.3,
                  mx=6, gid=gid)
        elif p["kind"] == "resweep":
            col = C["pink"]
            y = W["l"][i] if d > 0 else W["h"][i]
            keyart += ax.plot([xi], [y], marker="*", ms=5, color=col, zorder=17, gid=gid)
            L.add(ax, xi, y, p["label"], col, ha="center", va="top" if d > 0 else "bottom", dy=-4 if d > 0 else 4, fs=5.2, prio=3, mx=5, gid=gid)
        reg.append({"gid": gid, "t0": p["t"], "t1": int(W["t"][i]) + 300 if p["kind"] != "idm" else p["t"] + 300})
    # MACD divergence (price): a line through the two extremes
    if sp.get("div"):
        p1, p2 = sp["div"]["p1"], sp["div"]["p2"]
        ax.plot([X(p1[0]) + 0.5, X(p2[0]) + 0.5], [p1[1], p2[1]], color=C["pink"], lw=1.1, zorder=9, gid="k:div_price")
        reg.append({"gid": "k:div_price", "t0": p1[0], "t1": p2[0] + 300})
        L.add(ax, (X(p1[0]) + X(p2[0])) / 2 + 0.5, (p1[1] + p2[1]) / 2, "price: " + ("lower low" if d > 0 else "higher high"), C["pink"],
              ha="center", va="top" if d > 0 else "bottom", dy=-4 if d > 0 else 4, fs=5.3, prio=2, mx=5, gid="k:div_price")
    # the position (plan: entry -> exit), stop and target
    ent, stp, tgt = t["entry"], t["stop"], t["target"]
    xi_e = X(int(t["entry_t"]))
    ix = _exit_bar(W, t, 300)
    xx = (ix + 0.5) if t.get("exit_t") else n
    xx = max(xx, xi_e + 0.8)
    if tgt is not None and tgt_in:
        ax.add_patch(Rectangle((xi_e, min(ent, tgt)), xx - xi_e, abs(tgt - ent), facecolor=C["good"], alpha=0.07, edgecolor="none",
                               zorder=2, gid="plan:box"))
    ax.add_patch(Rectangle((xi_e, min(ent, stp)), xx - xi_e, abs(stp - ent), facecolor=C["bad"], alpha=0.09, edgecolor="none",
                           zorder=2, gid="plan:box"))
    ax.plot([xi_e, xx], [ent, ent], color=C["entry"], lw=0.8, zorder=6, gid="plan:entry")
    ax.plot([xi_e, xx], [stp, stp], color=C["bad"], lw=1.1, zorder=6, gid="plan:stop")
    reg += [{"gid": "plan:entry", "t0": int(t["entry_t"]), "t1": None}, {"gid": "plan:stop", "t0": int(t["entry_t"]), "t1": None}]
    rk = abs(ent - stp)
    flip = xi_e > 0.55 * n
    xl, hal = (xi_e - 0.6, "right") if flip else (xi_e + 0.6, "left")
    L.add(ax, xl, stp, f"stop {fpx(stp)} · {sp.get('stop_label') or ''} ({rk:.1f} pts)", C["bad"], ha=hal,
          va="top" if d > 0 else "bottom", dy=-2 if d > 0 else 2, prio=0, fs=5.6, bold=True, bg=True, gid="plan:stop")
    if tgt is not None:
        if tgt_in:
            ax.plot([xi_e, xx], [tgt, tgt], color=C["good"], lw=1.1, zorder=6, gid="plan:target")
            L.add(ax, xl, tgt, f"target {fpx(tgt)} · {sp.get('target_label') or ''}", C["good"], ha=hal,
                  va="bottom" if d > 0 else "top", dy=2 if d > 0 else -2, prio=0, fs=5.6, bold=True, gid="plan:target")
        else:
            y0e, y1e = ax.get_ylim()
            yy = y1e if (tgt > hi) else y0e
            ax.annotate("", xy=(xi_e + 1.2, yy), xytext=(xi_e + 1.2, yy - (y1e - y0e) * 0.09 * (1 if tgt > hi else -1)),
                        arrowprops=dict(arrowstyle="-|>", color=C["good"], lw=1.1, mutation_scale=8), zorder=6, gid="plan:target")
            L.add(ax, xi_e + (1.6 if not flip else -0.6), yy, f"target {fpx(tgt)} · {sp.get('target_label') or ''} (off the chart {'up' if tgt > hi else 'down'})",
                  C["good"], ha=hal, va="top" if tgt > hi else "bottom", dy=-3 if tgt > hi else 3, prio=0, fs=5.6, bold=True, gid="plan:target")
        reg.append({"gid": "plan:target", "t0": int(t["entry_t"]), "t1": None})
    # entry arrow
    ya = ent + d * rk * 0.45
    ax.annotate("", xy=(xi_e, ent), xytext=(xi_e - 2.0, ya),
                arrowprops=dict(arrowstyle="-|>", color=C["entry"], lw=1.0, mutation_scale=7), zorder=12, gid="k:entry")
    reg.append({"gid": "k:entry", "t0": int(t["entry_t"]), "t1": int(t["entry_t"])})
    L.add(ax, xi_e - 2.0, ya, f"{side_of(d)} {t['qty'] or ''} @ {fpx(ent)}".replace("  ", " "),
          C["ink"], ha="right", va="bottom" if d > 0 else "top", dy=1 if d > 0 else -1, prio=0, fs=5.8, bold=True,
          box=dict(boxstyle="round,pad=0.25,rounding_size=0.3", fc="#1d2230", ec=C["entry"], lw=0.5), gid="k:entry")
    # breakeven move (after the entry)
    be = sp.get("be") or _be_move(B1 if B1 is not None else W, t, sp.get("be_rule"), 60 if B1 is not None else 300)
    if be is None and sp.get("be_rule") and t["exit_kind"] == "BE":
        be = _be_move(W, t, sp.get("be_rule"), 300)
    if be:
        xb = X(be["t"]) + 0.5
        ax.plot([xb, max(xx, xb + 0.5)], [be["px"], be["px"]], color=_fade(C["ink"], 0.8), lw=0.8, ls=(0, (1, 1.2)), zorder=7, gid="a:be")
        ax.plot([xb], [ent], marker="s", ms=3.0, color=_fade(C["ink"], 0.8), zorder=10, gid="a:be")
        reg.append({"gid": "a:be", "t0": be["t"], "t1": None})
        L.add(ax, xb + 0.6, be["px"], f"breakeven {hm(be['t'])}: stop -> {fpx(be['px'])} (+1R reached)", _fade(C["ink"], 0.8),
              va="top" if d < 0 else "bottom", dy=-2 if d < 0 else 2, fs=5.2, prio=3, mx=5, gid="a:be")
    # 15-minute check
    tc = sp.get("tcheck")
    if tc and (t.get("exit_t") is None or t["exit_t"] >= tc["t"] - 60 or tc.get("cut")):
        xc = X(tc["t"])
        if 0 <= xc <= n:
            col = C["warn"] if tc.get("cut") else _fade(C["teal"], 0.75)
            ax.axvline(xc, color=col, lw=0.7, ls=(0, (2, 2)), zorder=4, gid="a:tcheck")
            reg.append({"gid": "a:tcheck", "t0": tc["t"], "t1": tc["t"]})
            L.add(ax, xc, ax.get_ylim()[1], "15-min check: cut" if tc.get("cut") else "15-min check: passed", col, ha="center",
                  va="top", dy=-10, fs=5.0, prio=3, mx=4, gid="a:tcheck")
    # exit
    ek = t["exit_kind"]
    ec = EXIT_C.get(ek, C["ink2"])
    if t.get("exit_t") and t.get("exit") is not None:
        xk = ix + 0.5
        ax.plot([xi_e, xk], [ent, t["exit"]], color=_fade(ec, 0.8), lw=0.7, ls=(0, (3, 2)), zorder=7, gid="a:exit")
        keyart += ax.plot([xk], [t["exit"]], marker="X", ms=5.2, color=ec, mec=C["page"], mew=0.5, zorder=17, gid="a:exit")
        reg.append({"gid": "a:exit", "t0": int(W["t"][ix]), "t1": int(W["t"][ix]) + 300})
        right = xk > 0.72 * (n + 4)
        L.add(ax, xk, t["exit"], f"exit {fpx(t['exit'])} · {EXIT_TXT.get(ek, ek.lower())} · {fusd(t['usd'])} · {fr(t['r'])}", "#0b0d12",
              ha="right" if right else "left", va="center", dy=0, dx=-7 if right else 7, fs=5.8, bold=True, prio=0,
              box=dict(boxstyle="round,pad=0.3,rounding_size=0.3", fc=ec, ec="none"), gid="a:exit")
    elif ek == "OPEN":
        L.add(ax, n - 0.5, t.get("last") or ent, "still open", C["accent"], ha="right", va="center", fs=5.8, bold=True, prio=0, gid="a:exit")
    # right-axis price tags
    items = [(ent, fpx(ent), C["entry"], "plan:entry"), (stp, fpx(stp), C["bad"], "plan:stop")]
    if tgt is not None and tgt_in:
        items.append((tgt, fpx(tgt), C["good"], "plan:target"))
    if t.get("exit") is not None and t.get("exit_t") and all(abs(t["exit"] - y) > 0.01 for y, *_ in items):
        items.append((t["exit"], fpx(t["exit"]), ec, "a:exit"))
    y0_, y1_ = ax.get_ylim()
    yy = _spread([y for y, *_ in items], (y1_ - y0_) * 0.042)
    for (y, txt, col, g), y2 in zip(items, yy):
        _tag(ax, y2, txt, col, gid=g)
    # MACD subpanel
    if axs is not None:
        _macd_panel(axs, sp["sub"], X, known_t, n, d, reg, L, Line2D)
    # 1m entry panel
    ax1 = None
    if inset is not None:
        ax1 = fig.add_axes([0.785, 0.575, 0.175, 0.29])
        _panel_1m(ax1, sp, inset, known_t, d, reg, L)
    # header
    e = _et(t["entry_t"])
    sc = C["good"] if d > 0 else C["bad"]
    rc = EXIT_C.get(ek, C["ink"])
    res_txt = "OPEN" if ek == "OPEN" else f"{EXIT_TXT.get(ek, ek.lower())}  {fusd(t['usd'])} · {fr(t['r'])}"
    grp = sp.get("group") or ""
    x = 0.014
    rr_ = fig.canvas.get_renderer()
    Wf = fig.get_window_extent(rr_).width
    for txt, col, fs, fw in ((f"{sp['short']}", C["ink"], 9.5, "bold"), (f"· {sp['label']}", C["ink2"], 7.2, "normal"),
                             (f"· {e:%a %Y-%m-%d %H:%M} ET", C["ink"], 7.6, "bold"), (side_of(d), sc, 9.0, "bold")):
        tx = fig.text(x, 0.955, txt, fontsize=fs, fontweight=fw, color=col, va="center")
        x += tx.get_window_extent(rr_).width / Wf + 0.008
    fig.text(0.988, 0.955, res_txt, fontsize=8.6, fontweight="bold", color=rc, va="center", ha="right", gid="a:result")
    sub = sp.get("setup") or ""
    sub = ("Setup: " + sub) if sub else "Setup markers unavailable"
    srcw = {"paper": "paper trade", "backtest": "backtest example", "live": "live trade", "pc": "PC paper"}.get(sp.get("src"), sp.get("src") or "")
    sub = f"{grp + ' · ' if grp else ''}{srcw} · {sub}"
    import textwrap
    lines = textwrap.wrap(sub, 165)[:2]
    for k_, ln_t in enumerate(lines):
        fig.text(0.014, 0.912 - k_ * 0.026, ln_t, fontsize=5.6, color=C["muted"] if k_ else C["ink2"], va="center")
    # "why it entered" panel
    _why_panel(fig, sp, top=0.535 if ax1 is not None else 0.86)
    # legend
    _legend(fig, sp, Line2D, Patch, has_sub)
    fig.text(0.782, 0.040, "CME NQ futures 5m / 1m bars · times ET", fontsize=4.6, color=C["muted"], ha="left", va="bottom")
    fig.text(0.782, 0.012, "bright = seen at the entry · faded = after it", fontsize=4.6, color=C["muted"], ha="left", va="bottom")
    L.place(fig, fixed + keyart)
    out = {"alt": sp.get("summary") or summary(sp), "marks": reg, "w": int(size[0] * dpi), "h": int(size[1] * dpi)}
    if path:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        fig.savefig(path, dpi=dpi, facecolor=C["page"])
        _shrink(path)
        out.update(path=path, bytes=os.path.getsize(path))
    out["fig"] = fig if not path else None
    if path:
        plt.close(fig)
    return out


def _macd_panel(axs, sub, X, known_t, n, d, reg, L, Line2D):
    axs.set_facecolor(C["panel"])
    for s_ in axs.spines.values():
        s_.set_color(C["grid"])
    axs.yaxis.tick_right()
    axs.tick_params(axis="both", length=0, labelsize=5.2, pad=2)
    axs.grid(axis="y", color=C["grid"], lw=0.4, zorder=0)
    rows = [r for r in sub["rows"] if X(r[0]) >= 0 and X(r[0]) <= n + 1]
    if not rows:
        return
    xs = np.array([X(r[0]) - 0.5 for r in rows])        # the value at a bar's close, drawn at that bar's middle
    line = np.array([np.nan if r[1] is None else r[1] for r in rows])
    sig = np.array([np.nan if r[2] is None else r[2] for r in rows])
    hist = np.array([np.nan if r[3] is None else r[3] for r in rows])
    known = np.array([r[0] <= known_t for r in rows])
    for flag, tag in ((True, "k"), (False, "a")):
        m = known if flag else (~known)
        if not m.any():
            continue
        k_ = 1.0 if flag else 0.5
        cols = [(_fade(C["up"], 0.7 * k_) if h >= 0 else _fade(C["dn"], 0.7 * k_)) for h in hist[m]]
        axs.bar(xs[m], hist[m], width=0.6, color=cols, zorder=2, gid=f"{tag}:macd")
        mm = m.copy()
        if not flag:                                      # join the faded part to the bright one
            j = np.flatnonzero(known)
            if len(j):
                mm[j[-1]] = True
        axs.plot(xs[mm], line[mm], color=C["accent"] if flag else _fade(C["accent"], 0.5), lw=0.9, zorder=3, gid=f"{tag}:macd",
                 ls="-" if flag else (0, (3, 2)))
        axs.plot(xs[mm], sig[mm], color=C["warn"] if flag else _fade(C["warn"], 0.5), lw=0.7, zorder=3, gid=f"{tag}:macd",
                 ls="-" if flag else (0, (3, 2)))
        rk = [r[0] for r, f in zip(rows, m) if f]
        reg.append({"gid": f"{tag}:macd", "t0": rk[0], "t1": rk[-1]})
    axs.axhline(0, color=C["grid"], lw=0.6, zorder=1)
    axs.axvline(X(known_t), color=C["ink2"], lw=0.5, ls=(0, (1, 2)), zorder=2, alpha=0.7)
    dv = sub.get("div") or {}
    if dv.get("p1") and dv["p1"][0]:
        (t1, o1), (t2, o2) = dv["p1"], dv["p2"]
        axs.plot([X(t1) - 0.5, X(t2) - 0.5], [o1, o2], color=C["pink"], lw=1.2, zorder=5, gid="k:div_macd", marker="o", ms=2.6)
        reg.append({"gid": "k:div_macd", "t0": t1 - 300, "t1": t2})
        L.add(axs, (X(t1) + X(t2)) / 2 - 0.5, max(o1, o2) if d > 0 else min(o1, o2),
              "MACD: " + ("higher low = bullish divergence" if d > 0 else "lower high = bearish divergence"), C["pink"], ha="center",
              va="bottom" if d > 0 else "top", dy=3 if d > 0 else -3, fs=5.2, prio=1, gid="k:div_macd")
    axs.text(0.004, 0.94, f"MACD (12, 26, 9) {sub.get('osc') or 'line'} · 5m", transform=axs.transAxes, fontsize=5.2, color=C["ink2"],
             va="top", ha="left")


def _panel_1m(ax1, sp, B, known_t, d, reg, L):
    t = sp["trade"]
    X1 = _X(B["t"], 60)
    n = len(B["t"])
    ax1.set_facecolor(C["panel"])
    for s_ in ax1.spines.values():
        s_.set_color(C["grid"])
    ys = list(B["l"]) + list(B["h"]) + [t["stop"], t["entry"]]
    lo, hi = min(ys), max(ys)
    pad = (hi - lo) * 0.08 + 1
    ax1.set_ylim(lo - pad, hi + pad)
    ax1.set_xlim(0, n + 1)
    ax1.yaxis.tick_right()
    ax1.tick_params(axis="both", length=0, labelsize=4.8, pad=1.5)
    ax1.grid(axis="y", color=C["grid"], lw=0.4, zorder=0)
    from matplotlib.ticker import FuncFormatter
    ax1.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    tk = [(i, int(ts)) for i, ts in enumerate(B["t"]) if int(ts) % 600 == 0]
    ax1.set_xticks([i for i, _ in tk])
    ax1.set_xticklabels([hm(ts) for _, ts in tk])
    _candles(ax1, B, X1, known_t, 60, reg, w=0.66, gid="1m:candles")
    xe = X1(int(t["entry_t"]))
    ax1.axvline(xe, color=C["ink2"], lw=0.5, ls=(0, (1, 2)), zorder=2, alpha=0.7)
    ax1.plot([xe, n], [t["stop"], t["stop"]], color=C["bad"], lw=0.9, zorder=6, gid="plan:stop")
    ax1.plot([xe, n], [t["entry"], t["entry"]], color=C["entry"], lw=0.7, zorder=6, gid="plan:entry")
    ax1.plot([xe], [t["entry"]], marker=">", ms=4, color=C["entry"], zorder=10, gid="k:entry")
    hcol = {"limit": C["teal"], "cisd1": C["pink"], "cisd": C["accent"]}
    for h_ in sp["hlines"]:
        if h_["kind"] not in ("limit", "cisd1"):
            continue
        x0, x1 = X1(h_["t0"]), X1(min(h_["t1"], known_t))
        if x1 < 0 or x0 > n:
            continue
        col = hcol[h_["kind"]]
        ax1.plot([max(0, x0), max(x1, max(0, x0) + 0.6)], [h_["px"], h_["px"]], color=col, lw=0.9, ls=(0, (2, 1.5)) if h_["kind"] == "limit" else "-",
                 zorder=6, gid=f"k:{h_['kind']}")
        reg.append({"gid": f"k:{h_['kind']}", "t0": h_["t0"], "t1": min(h_["t1"], known_t)})
        if h_["kind"] == "cisd1":
            L.add(ax1, max(0, x0), h_["px"], f"1m CISD {fpx(h_['px'])}", col, ha="right", va="center", dx=-3,
                  dy=0, fs=4.9, prio=0, mx=6, gid="k:cisd1")
        else:
            L.add(ax1, max(0, x0) + 0.3, h_["px"], f"limit {fpx(h_['px'])}" + (f" · tap {hm(h_['tap_t'])}" if h_.get("tap_t") else ""), col,
                  va="bottom" if d > 0 else "top", dy=1.5 if d > 0 else -1.5, fs=4.9, prio=2, mx=4, gid="k:limit")
    for p in sp["points"]:
        if p["kind"] == "cisd1" and p.get("t"):
            i = _bar_at(B, p["t"])
            if i is not None:
                y = B["c"][i]
                ax1.plot([i + 0.5], [y], marker="o", ms=3.4, mfc="none", mec=C["pink"], mew=1.0, zorder=9, gid="k:cisd1")
                reg.append({"gid": "k:cisd1", "t0": int(B["t"][i]), "t1": int(B["t"][i]) + 60})
                L.add(ax1, i + 0.5, y, "1m CISD close", C["pink"], ha="right", va="center", dx=-4, dy=0, fs=4.9, prio=1, mx=4, gid="k:cisd1")
    L.add(ax1, xe, t["entry"], f"entry {hm(t['entry_t'])}", C["ink"], ha="left", va="bottom" if d < 0 else "top", dx=4,
          dy=2 if d < 0 else -2, fs=5.0, prio=0, bold=True, gid="k:entry")
    ax1.set_title("1m · the entry minutes", fontsize=5.6, color=C["ink2"], loc="left", pad=2.5)


def _why_panel(fig, sp, top=0.86):
    """The rule checks (the strategy's own, in its engine's order) and the notes, as plain text."""
    import textwrap
    x, y = 0.782, top
    fig.text(x, y, "Why it entered", fontsize=6.6, fontweight="bold", color=C["ink"], va="top")
    y -= 0.034
    lines = []
    for c in sp.get("checks") or []:
        mark = "✓" if c.get("ok") is True else "✗" if c.get("ok") is False else "·"
        col = C["good"] if c.get("ok") is True else C["bad"] if c.get("ok") is False else C["muted"]
        txt = str(c.get("name") or "")
        if c.get("val"):
            txt += f": {c['val']}"
        lines.append((mark, col, txt))
    for nt in sp.get("notes") or []:
        lines.append(("•", C["ink2"], nt))
    if not lines:
        lines.append(("•", C["ink2"], "Rule checks not available for this trade."))
    budget = int((y - 0.08) / 0.0255)
    wrap = 41
    used = 0
    for mark, col, txt in lines:
        parts = textwrap.wrap(txt, wrap) or [""]
        if used + len(parts) > budget:
            parts = parts[:max(0, budget - used)]
            if not parts:
                break
            parts[-1] = parts[-1][:wrap - 1] + "…"
        fig.text(x, y, mark, fontsize=5.6, color=col, va="top", fontweight="bold")
        for p in parts:
            fig.text(x + 0.011, y, p, fontsize=5.0, color=C["ink2"], va="top")
            y -= 0.0255
            used += 1
        if used >= budget:
            break


def _legend(fig, sp, Line2D, Patch, has_sub):
    d = int(sp["trade"]["dir"])
    H = [Line2D([], [], color=C["entry"], marker=">", lw=0.8, ms=4, label="entry"),
         Line2D([], [], color=C["bad"], lw=1.1, label="stop"), Line2D([], [], color=C["good"], lw=1.1, label="target")]
    kinds = {p["kind"] for p in sp["points"]} | {h["kind"] for h in sp["hlines"]} | {c["kind"] for c in sp["candles"]}
    if any(x.get("role") == "swept" for x in sp["levels"]):
        H.append(Line2D([], [], color=C["ssl"] if d > 0 else C["bsl"], lw=1.0, ls=(0, (4, 2.5)),
                        label="hunted pool" if sp["key"].startswith("sh_") else "swept level"))
    if any(x.get("role") != "swept" for x in sp["levels"]):
        H.append(Line2D([], [], color=C["violet"], lw=0.7, ls=(0, (2, 2.5)), label="levels of the day"))
    if "sweep" in kinds:
        H.append(Patch(facecolor=C["warn"], alpha=0.45, edgecolor=C["warn"], label="sweep wick"))
    if kinds & {"idm", "swing"}:
        H.append(Line2D([], [], color=C["gold"], marker="^" if d > 0 else "v", ls=(0, (1, 1.3)), lw=0.8, ms=3.5,
                        label="swept swing" if "swing" in kinds else "inducement"))
    if "resweep" in kinds:
        H.append(Line2D([], [], color=C["pink"], marker="*", lw=0, ms=5, label="resweep"))
    if "disp" in kinds:
        H.append(Patch(facecolor="none", edgecolor=C["accent"], label="strong candle" if sp["key"].startswith("sh_") else "displacement"))
    if "reclaim" in kinds:
        H.append(Patch(facecolor="none", edgecolor=C["teal"], label="reclaim candle"))
    if "cisd" in kinds:
        H.append(Line2D([], [], color=C["accent"], lw=1.1, label="5m CISD"))
    if "limit" in kinds:
        H.append(Line2D([], [], color=C["teal"], lw=0.9, ls=(0, (2, 1.5)), label="limit"))
    if "cisd1" in kinds:
        H.append(Line2D([], [], color=C["pink"], lw=0.9, label="1m CISD"))
    if "mss" in kinds:
        H.append(Line2D([], [], color=C["violet"], lw=0.9, ls=(0, (2, 1.5)), label="last swing (structure)"))
    for ln in sp["lines"]:
        H.append(Line2D([], [], color=ln["color"], lw=0.95, label=ln["name"]))
    if sp.get("div"):
        H.append(Line2D([], [], color=C["pink"], lw=1.1, label="divergence"))
    if sp.get("be") or sp.get("be_rule"):
        H.append(Line2D([], [], color=_fade(C["ink"], 0.8), lw=0.8, ls=(0, (1, 1.2)), marker="s", ms=2.6, label="breakeven move"))
    if sp.get("tcheck"):
        H.append(Line2D([], [], color=C["teal"], lw=0.7, ls=(0, (2, 2)), label="15-min check"))
    H.append(Line2D([], [], color=C["ink2"], marker="X", lw=0, ms=4.5, label="exit"))
    H.append(Patch(facecolor=_fade(C["up"], 0.42), edgecolor="none", label="after the entry (faded)"))
    ax = fig.add_axes([0.012, 0.0, 0.70, 0.085])
    ax.axis("off")
    lg = ax.legend(handles=H, loc="center left", ncol=max(4, (len(H) + 1) // 2), fontsize=4.9, frameon=False, handlelength=1.8,
                   columnspacing=1.1, handletextpad=0.5, labelcolor=C["ink2"], borderaxespad=0.0)
    lg.set_gid("legend")
    return lg


def _shrink(path, colors=160):
    """Palette PNG: about a third of the size, still crisp (the chart has few colours). Never fails the picture."""
    try:
        from PIL import Image
        im = Image.open(path).convert("RGB")
        im.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(path, optimize=True)
    except Exception:
        pass


def _hash(path) -> str:
    try:
        with open(path, "rb") as fh:
            return hashlib.sha1(fh.read()).hexdigest()[:10]
    except OSError:
        return ""


# ------------------------------------------------------------------------------------------------ one trade -> one picture
def build_spec(key, t, df5, one_min=None, now=None, lit=None, src="paper", keep=None, res=None):
    """The spec of trade t (any trade dict) of strategy `key` on bars closed by `now` (default: just after the exit, or the
    last bar for an open trade). keep / res: an existing LIT keep / second run result to reuse (the cloud's own run)."""
    t = norm_trade(t)
    if now is None:
        now = (int(t["exit_t"]) + 300) if t.get("exit_t") else int(df5["time"].max()) + 300
    now = int(now)
    try:
        if key in ("lit", "lit_asia"):
            if keep is None or not _lit_match(keep, t)[0]:
                keep = lit_keep(df5, one_min, now, lit_params(key))
            sp = lit_spec(key, t, keep, src)
        else:
            if res is None or str(int(t["entry_t"])) not in ((res.get("marks") or {})):
                res = second_run(key, df5, one_min, now, lit)
            sp = second_spec(key, t, res, src)
    except Exception as e:
        sp = plain_spec(key, t, src, f"setup markers unavailable ({e.__class__.__name__}: {e})")
    return sp


def make(key, t, df5, one_min=None, path=None, now=None, lit=None, src="paper", keep=None, res=None) -> dict:
    """Spec + picture of one trade. Returns the index row (id, key, day, side, r, usd, exit_kind, open, alt, file, hash, ...)."""
    sp = build_spec(key, t, df5, one_min, now, lit, src, keep, res)
    b1 = sp.pop("_bars1", None)
    if b1 is None and one_min is not None:
        b1 = one_min
    B5 = _bars(df5)
    tt = sp["trade"]
    w = _cut(B5, int(tt["entry_t"]) - 2 * 86400, (int(tt["exit_t"]) if tt.get("exit_t") else int(tt["entry_t"])) + 2 * 3600)
    if w is not None and now is not None:
        w = {k: v[(w["t"] + 300) <= int(now)] for k, v in w.items()}
    b1d = _bars(b1) if b1 is not None else None
    if b1d is not None and now is not None:
        keep1 = (b1d["t"] + 60) <= int(now)
        b1d = {k: v[keep1] for k, v in b1d.items()}
    meta = render(sp, w, b1d, path)
    return row_of(key, sp, meta, path)


def row_of(key, sp, meta, path=None):
    t = sp["trade"]
    return {"id": chart_id(key, t), "key": key, "short": sp["short"], "label": sp["label"], "tid": trade_id(t), "day": t["day"],
            "entry_t": t["entry_t"], "exit_t": t.get("exit_t"), "side": side_of(t["dir"]), "dir": t["dir"], "entry": t["entry"],
            "stop": t["stop"], "target": t["target"], "exit": t.get("exit"), "exit_kind": t["exit_kind"], "r": t.get("r"),
            "usd": t.get("usd"), "qty": t.get("qty"), "open": t["exit_kind"] == "OPEN", "src": sp.get("src"), "alt": meta["alt"],
            "w": meta["w"], "h": meta["h"], "bytes": meta.get("bytes"), "hash": _hash(path) if path else None,
            "markers": not bool(sp["notes"] and str(sp["notes"][0]).startswith("setup markers unavailable")), "made": int(time.time()),
            "sig": sig_of(t)}


def sig_of(t) -> str:
    """What makes a picture stale: the trade's exit (OPEN -> closed) and its result."""
    t = norm_trade(t)
    return f"{t.get('exit_kind')}|{t.get('exit_t')}|{t.get('r')}"


# ------------------------------------------------------------------------------------------------ the picture store
class Store:
    """<root>/<key>/<tid>.png + <root>/index.json {v, t, strategies: {key: [rows newest first]}}; the newest `keep` per strategy."""

    def __init__(self, root, keep=KEEP):
        self.root, self.keep = root, keep
        self.ix = self._load()

    def _load(self):
        try:
            with open(os.path.join(self.root, "index.json"), encoding="utf-8") as fh:
                ix = json.load(fh)
            if isinstance(ix, dict) and isinstance(ix.get("strategies"), dict):
                return ix
        except Exception:
            pass
        return {"v": VERSION, "t": None, "strategies": {}}

    def path(self, key, t):
        return os.path.join(self.root, key, trade_id(norm_trade(t)) + ".png")

    def row(self, key, t):
        cid = chart_id(key, norm_trade(t))
        return next((r for r in self.ix["strategies"].get(key) or [] if r.get("id") == cid), None)

    def stale(self, key, t):
        """True when trade t has no picture yet or its picture shows an older state (open -> closed)."""
        r = self.row(key, t)
        if r is None or not os.path.exists(os.path.join(self.root, key, r["tid"] + ".png")):
            return True
        return r.get("sig") != sig_of(norm_trade(t))

    def put(self, key, row):
        L = [r for r in self.ix["strategies"].get(key) or [] if r.get("id") != row["id"]]
        L.append(row)
        L.sort(key=lambda r: -int(r.get("entry_t") or 0))
        for old in L[self.keep:]:
            try:
                os.remove(os.path.join(self.root, key, old["tid"] + ".png"))
            except OSError:
                pass
        self.ix["strategies"][key] = L[:self.keep]

    def save(self, now=None):
        self.ix["t"] = int(now or time.time())
        self.ix["v"] = VERSION
        os.makedirs(self.root, exist_ok=True)
        tmp = os.path.join(self.root, "index.json.tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.ix, fh, indent=1, default=str)
        os.replace(tmp, os.path.join(self.root, "index.json"))


SLIM = ("id", "key", "short", "tid", "day", "entry_t", "exit_t", "side", "dir", "entry", "stop", "target", "exit", "exit_kind", "r",
        "usd", "qty", "open", "src", "alt", "w", "h", "hash", "markers")


def _slim(r):
    return {k: r.get(k) for k in SLIM if r.get(k) is not None or k in ("open",)}


def index_view(ix, base="charts/", n=12, examples=None, ex_base=None) -> dict:
    """The apps' cut of an index: per strategy the newest n rows with their image URL (base + key/tid.png?v=hash) and, when
    a strategy has no picture yet, its backtest examples (examples = research/lab/chart_examples/index.json)."""
    out = {"v": VERSION, "t": (ix or {}).get("t"), "strategies": {}}
    keys = [k for k in ORDER if k in ((ix or {}).get("strategies") or {}) or k in ((examples or {}).get("strategies") or {})]
    for k in keys:
        rows = [{**_slim(r), "url": f"{base}{k}/{r['tid']}.png" + (f"?v={r['hash']}" if r.get("hash") else "")}
                for r in ((ix or {}).get("strategies") or {}).get(k) or []][:n]
        ex = [{**_slim(r), "url": f"{ex_base if ex_base is not None else base}{k}/{r['tid']}.png" + (f"?v={r['hash']}" if r.get("hash") else ""),
               "example": True} for r in ((examples or {}).get("strategies") or {}).get(k) or []][:n]
        out["strategies"][k] = {"label": STRATS.get(k, {}).get("label", k), "short": STRATS.get(k, {}).get("short", k),
                                "items": rows, "examples": ex}
    return out


def site_copy(charts_dir, out, n=24, n_ex=20, examples_dir=EXAMPLES) -> dict:
    """The phone site's pictures (tools/build_web_dashboard.py): the cloud's newest n per strategy (<dash>/charts) ->
    <site>/charts/<key>/, the backtest examples -> <site>/charts/examples/<key>/; returns the data.json "charts" view."""
    dst = os.path.join(out, DIR)
    shutil.rmtree(dst, ignore_errors=True)
    ix = Store(charts_dir).ix if charts_dir and os.path.isdir(charts_dir) else {"strategies": {}}
    ex = load_examples() if examples_dir == EXAMPLES else (Store(examples_dir).ix if os.path.isdir(examples_dir) else {"strategies": {}})
    n_c = n_e = 0
    for src_root, rows_of, sub, nn in ((charts_dir, ix, "", n), (examples_dir, ex, "examples", n_ex)):
        for k, rows in (rows_of.get("strategies") or {}).items():
            if k not in STRATS:
                continue
            keep = []
            for r in (rows or [])[:nn]:
                tid = str(r.get("tid") or "")
                if not tid or "/" in tid or "\\" in tid or ".." in tid:
                    continue
                src = os.path.join(src_root, k, tid + ".png")
                if os.path.exists(src):
                    os.makedirs(os.path.join(dst, sub, k), exist_ok=True)
                    shutil.copy(src, os.path.join(dst, sub, k, tid + ".png"))
                    keep.append(r)
            rows_of["strategies"][k] = keep
            if sub:
                n_e += len(keep)
            else:
                n_c += len(keep)
    view = index_view(ix, base=f"{DIR}/", n=max(n, n_ex), examples=ex, ex_base=f"{DIR}/examples/")
    view["counts"] = {"live": n_c, "examples": n_e}
    return view


def compact_view(view, n=3) -> dict:
    """home.json's cut: the newest n pictures (or examples) per strategy."""
    if not isinstance(view, dict):
        return None
    out = {k: view.get(k) for k in ("v", "t")}
    out["strategies"] = {k: {**{kk: s.get(kk) for kk in ("label", "short")}, "items": (s.get("items") or [])[:n],
                             "examples": (s.get("examples") or [])[:n if not s.get("items") else 0]}
                         for k, s in (view.get("strategies") or {}).items()}
    return out


def load_examples() -> dict:
    try:
        with open(os.path.join(EXAMPLES, "index.json"), encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {"strategies": {}}


# ------------------------------------------------------------------------------------------------ the cloud monitor
def cloud_trades(state) -> dict:
    """Every paper trade of a cloud state per strategy key: LIT's ledger (taken trades) and the second strategies' ledgers."""
    out = {}
    L = []
    for k, v in (state.get("ledger") or {}).items():
        if not str(k).isdigit() or not isinstance(v, dict) or v.get("taken") is False:
            continue
        side = str(v.get("side") or "").upper()
        L.append({"day": v.get("day") or tday(int(k)), "entry_t": int(k), "dir": 1 if side == "LONG" else -1,
                  "exit_t": v.get("exit_ts"), "entry": v.get("entry_px"), "stop": v.get("stop_px"), "target": v.get("target_px"),
                  "exit": v.get("exit_px"), "exit_kind": "OPEN" if not v.get("exit_ts") or v.get("exit") in (None, "OPEN") else v.get("exit"),
                  "r": v.get("R"), "usd": v.get("usd"), "qty": v.get("qty"), "risk_pts": v.get("risk_pts")})
    if L:
        out["lit"] = L
    for key, s in ((state.get("second") or {}).get("strategies") or {}).items():
        rows = [dict(r) for r in ((s or {}).get("ledger") or {}).values() if isinstance(r, dict) and r.get("entry_t")]
        if rows:
            out[key] = rows
    return out


def cloud_hook(out, state, df5, df1=None, keep=None, now=None, max_new=MAX_NEW, budget_s=BUDGET_S, max_age_d=12) -> dict:
    """Pictures of the cloud's paper trades: each new trade at its entry, again when it finished; the newest KEEP per strategy
    in <out>/charts/ (restored every run with the dashboard branch). keep = the cloud LIT run's keep (reused, no re-run).
    Returns {"made": [...], "index": <index_view>, "error"?}. Never raises; at most max_new pictures / budget_s seconds."""
    t0 = time.time()
    made, errors = [], []
    try:
        st = Store(os.path.join(out, DIR))
        now = int(now or time.time())
        todo = []
        for key, rows in cloud_trades(state).items():
            for r in rows:
                try:
                    t = norm_trade(r)
                except Exception:
                    continue
                if now - int(t["entry_t"]) > max_age_d * 86400 or not st.stale(key, t):
                    continue
                todo.append((key, t))
        todo.sort(key=lambda x: -x[1]["entry_t"])
        res_cache = {}
        for key, t in todo[:max_new]:
            if time.time() - t0 > budget_s:
                break
            try:
                res = None
                if key not in ("lit", "lit_asia"):
                    if key not in res_cache:
                        res_cache[key] = second_run(key, df5, df1, now)
                    res = res_cache[key]
                p = st.path(key, t)
                row = make(key, t, df5, df1, path=p, now=now, src="paper", keep=keep if key == "lit" else None, res=res)
                st.put(key, row)
                made.append(row["id"])
            except Exception as e:
                errors.append(f"{key} {t.get('entry_t')}: {e.__class__.__name__}: {e}")
        st.save(now)
        res = {"made": made, "n": sum(len(v) for v in st.ix["strategies"].values()), "secs": round(time.time() - t0, 1)}
        if errors:
            res["errors"] = errors[:5]
        return res
    except Exception as e:
        return {"made": made, "error": f"{e.__class__.__name__}: {e}"}


# ------------------------------------------------------------------------------------------------ the PC bot
class PcCharts:
    """The PC bot's pictures (engine/live.py LiveBot._chart_tick): one background worker, called after routing; it never
    blocks the poll (a busy worker skips the tick) and never raises into the bot."""

    def __init__(self, root=PC_DIR):
        self.root = root
        self.busy = False
        self.last = None
        self.error = None

    def tick(self, lit_trades, second_res, df5, df1, now, keep=None):
        if self.busy:
            return False
        self.busy = True

        def run():
            try:
                st = Store(self.root)
                jobs = []
                for t in lit_trades or []:
                    tt = norm_trade(t)
                    if now - tt["entry_t"] <= 12 * 86400 and st.stale("lit", tt):
                        jobs.append(("lit", tt, None))
                for key, s in ((second_res or {}).get("strategies") or {}).items():
                    for t in s.get("trades") or []:
                        tt = norm_trade(t)
                        if now - tt["entry_t"] <= 12 * 86400 and st.stale(key, tt):
                            jobs.append((key, tt, None))
                jobs.sort(key=lambda j: -j[1]["entry_t"])
                cache = {}
                for key, tt, _ in jobs[:MAX_NEW]:
                    try:
                        res = None
                        if key != "lit":
                            if key not in cache:
                                cache[key] = second_run(key, df5, df1, now)
                            res = cache[key]
                        row = make(key, tt, df5, df1, path=st.path(key, tt), now=now, src="pc", keep=keep if key == "lit" else None, res=res)
                        st.put(key, row)
                    except Exception as e:
                        self.error = f"{key}: {e.__class__.__name__}: {e}"
                st.save(now)
                self.last = int(now)
            except Exception as e:
                self.error = f"{e.__class__.__name__}: {e}"
            finally:
                self.busy = False
        threading.Thread(target=run, name="trade-charts", daemon=True).start()
        return True


# ------------------------------------------------------------------------------------------------ backtest examples
def _research_trades(key, since="2026-07-01", until="2026-10-16"):
    if key == "lit":
        from tools import runlib as rl
        r = rl.load("lit_live")
        T = [dict(zip(r["trade_cols"], a)) for a in r["trades"]]
    elif key == "lit_asia":
        from tools import runlib as rl
        r = rl.load("lit_more_ent_asia_slot_rr3")
        T = [dict(zip(r["trade_cols"], a)) for a in r["trades"]]
    else:
        f = {"ema_lon_vix": "research/second/ema_best.json", "macd_sweep": "research/second/md_best.json",
             "sr_nyreclaim": "research/second/sr_best.json", "sh_asia": "research/stophunt/sh_asia_resweep.json",
             "sh_trend": "research/stophunt/sh_trend_idm5.json"}[key]
        with open(os.path.join(ROOT, f), encoding="utf-8") as fh:
            T = json.load(fh)["trades"]
    return sorted([t for t in T if since <= str(t["day"]) <= until], key=lambda t: t["entry_t"])


_DATA = {}


def research_bars():
    """data/NQ_5m.csv (2025-10 on) + the research-clean 1m bars (engine.data.load_ltf), loaded once."""
    if "df5" not in _DATA:
        import pandas as pd
        from engine.data import load, load_ltf
        df5 = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
        t0 = int(dt.datetime(2025, 9, 1, tzinfo=ET).timestamp())
        df5 = df5[df5["time"] >= t0].reset_index(drop=True)
        b1, _ = load_ltf("NQ", load("NQ", "5m"))
        b1 = b1.slice(int(np.searchsorted(b1.t, int(df5["time"].min()))), len(b1))
        _DATA.update(df5=df5, b1=b1)
    return _DATA["df5"], _DATA["b1"]


def _lit_windows_research():
    from tools import runlib as rl
    r = rl.load("lit_live")
    return sorted(({"entry_t": int(a[1]), "exit_t": int(a[2])} for a in r["trades"]), key=lambda x: x["entry_t"])


def pick_examples(T, n):
    """n trades spread over the period: the newest, winners and losers both, every exit kind."""
    if len(T) <= n:
        return T
    T = sorted(T, key=lambda t: t["entry_t"])
    idx = sorted(set(np.linspace(0, len(T) - 1, n).round().astype(int).tolist()))
    pick = [T[i] for i in idx]
    return pick[:n]


def backfill(keys=None, since="2026-07-01", until="2026-10-16", n=20, out=EXAMPLES, verbose=True) -> dict:
    """Pictures of the backtest trades (the pages' examples): ~n per strategy spread over [since, until], from the stored
    research trades, each rebuilt by the strategy's own code on the bars closed just after its exit."""
    keys = [k for k in (keys or ORDER) if k in STRATS]
    df5, b1 = research_bars()
    st = Store(out, keep=max(n, 1))
    done = {}
    for key in keys:
        T = pick_examples(_research_trades(key, since, until), n)
        st.ix["strategies"][key] = [r for r in st.ix["strategies"].get(key) or [] if any(chart_id(key, norm_trade(t)) == r["id"] for t in T)]
        ok = 0
        for t in T:
            t0 = time.time()
            tt = norm_trade(t)
            now = (int(tt["exit_t"]) + 300) if tt.get("exit_t") else int(tt["entry_t"]) + 86400
            try:
                row = make(key, tt, df5, b1, path=st.path(key, tt), now=now, src="backtest")
                st.put(key, row)
                ok += 1
                if verbose:
                    print(f"  {key:13s} {row['tid']}  {row['exit_kind']:8s} {fr(row['r'] or 0):>7s}  {row['bytes'] // 1024} KB"
                          f"  {'markers' if row['markers'] else 'PLAIN'}  {time.time() - t0:.1f}s", flush=True)
            except Exception as e:
                print(f"  {key} {tt['day']} failed: {e.__class__.__name__}: {e}", flush=True)
        done[key] = ok
    st.save()
    return done


def main(argv=None):
    ap = argparse.ArgumentParser(description="Trade pictures (engine/trade_chart.py)")
    sub = ap.add_subparsers(dest="cmd")
    b = sub.add_parser("backfill", help="pictures of the backtest trades (the pages' examples)")
    b.add_argument("--strategy", default="all")
    b.add_argument("--since", default="2026-07-01")
    b.add_argument("--until", default="2026-10-16")
    b.add_argument("--n", type=int, default=20)
    b.add_argument("--out", default=EXAMPLES)
    o = sub.add_parser("one", help="one backtest trade's picture")
    o.add_argument("--strategy", required=True)
    o.add_argument("--day", required=True)
    o.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    if a.cmd == "backfill":
        keys = ORDER if a.strategy == "all" else [k.strip() for k in a.strategy.split(",")]
        print(backfill(keys, a.since, a.until, a.n, a.out))
        return 0
    if a.cmd == "one":
        df5, b1 = research_bars()
        T = [t for t in _research_trades(a.strategy, a.day, a.day)]
        if not T:
            print("no trade that day")
            return 1
        tt = norm_trade(T[0])
        p = a.out or os.path.join(ROOT, "logs", "charts_one", f"{a.strategy}_{trade_id(tt)}.png")
        now = (int(tt["exit_t"]) + 300) if tt.get("exit_t") else int(tt["entry_t"]) + 86400
        row = make(a.strategy, tt, df5, b1, path=p, now=now, src="backtest")
        print(p, row["bytes"] // 1024, "KB", "markers" if row["markers"] else "PLAIN")
        print(row["alt"])
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
