"""Trade Intelligence (owner 2026-10-21: "more data for all the trades it has taken - backtested, paper, whatever - what
signs show wins, what shows losses").

One row per LIT trade from every source, ~60 columns each, and the win / loss signs per feature:
  backtest  run lit_live (the live config replayed by engine/lit.py run_x: 2026 + the 2021-25 reference) with the
            per-trade report fields of research/lab/backtest_live.json (tools/export_backtest.py)
  paper     the cloud monitor's paper ledger (dash/state.json "ledger") + the journal's "cloud" records (features "f")
  live      the PC bot's routed trades (heartbeat "acct" trades in the cloud state) + the journal's "pc" records

Entry columns (when = "entry") are known when the order goes in; outcome columns (when = "after") are not. Nothing here is
re-derived when a study already computes it: the 50 causal features of tools/lit_select.py feats (the same ones the
learning loop journals live, engine/lit_learn.live_features), the setup-quality features of tools/lit_batch3a.features
(ICT macros, level age / touches, sweep rejection, level class), the dealer-gamma day context of tools/lit_context.context,
the 4H features of engine/lit_learn.h4_feats and the daily ATR of tools/lit_batch3b.atr_d. Paper / live rows carry what
their ledger and journal record hold (the journal's "f" are the same lit_select features); the rest stays empty.

Signs: every entry feature is cut in buckets (terciles on 2026 H1 = the half LIT was picked on, applied unchanged to H2 and
2021-25; categories as they are) with trades, win %, avg R, PF and $ for 2026 H1, H2 and 2021-25. A feature is
"consistent" when the better side (top vs bottom tercile, or a category vs the rest) is the same in H1 AND H2 with >= 8
trades on each side in both halves; 2021-25 is noted (holds / not), never a gate. Descriptive only: most of these were
already tested as rules (research/writeups/lit-batch3a.md, lit-batch3b.md, lit-bias-discretion.md, lit-market-context.md,
lit-new-entries.md, lit-trade-selection.md) and none passed; buckets of 10-20 trades are noise.

    python -X utf8 tools/trade_intel.py            # rebuild research/lab/trade_intel.json if run lit_live changed
    python -X utf8 tools/trade_intel.py --force    # rebuild anyway (~1 min)
    python -X utf8 tools/trade_intel.py --check    # say whether the file is current (exit 1 when stale)
    python -X utf8 tools/trade_intel.py --exit-eff # add / refresh the exit-efficiency block in the stored file (no engine run)
Exit efficiency (competitor-features #11, exit_eff()): per trade the share of the best move it kept (capture = exit R / MFE R),
the giveback after +1R (MFE - exit R on trades that reached +1R), how far a loser was up before its stop, and the heat
taken before +1R; by exit type, by month (the trend line) and by span. It explains why BE / the 15-minute check / the 8R
bank behave as they do. It is not a rule.
The cloud build (tools/build_web_dashboard.py) only appends the paper / live rows (merge_live, a few ms): no engine run.
Read-only: no trading logic, nothing in live_model.json changes.
"""
from __future__ import annotations

import collections
import datetime as dt
import hashlib
import json
import math
import os
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "research", "lab", "trade_intel.json")
RUN_ID = "lit_live"
ET = ZoneInfo("America/New_York")
VERSION = 1
SPANS = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-12-31"), "2021-25": ("2021-01-01", "2025-12-31")}
MIN_SIDE = 8                   # trades on each side of a comparison, in each half, before a sign can be "consistent"
WIN_R, LOSS_R = 0.5, -0.5      # win = R >= +0.5, loss = R <= -0.5, scratch in between (a breakeven exit is a scratch)
MACROS = [(153, 180), (243, 270), (530, 550), (590, 610), (650, 670), (710, 730), (790, 820), (915, 945)]   # = lit_batch3a
WRITEUPS = [("lit-batch3a", "Batch 3a: macros, volume, rejection, level age / touches, level type"),
            ("lit-batch3b", "Batch 3b: ES, news, Asia / London range, FVGs, seasonality"),
            ("lit-bias-discretion", "Daily bias and discretionary reads"),
            ("lit-market-context", "Gamma / GEX, VIX term structure, options calendar"),
            ("lit-new-entries", "New entries, inducement count"),
            ("lit-trade-selection", "Trade selection model (the 50 features)"),
            ("lit-losses", "Loss anatomy and the loss pack")]

# ------------------------------------------------------------------------------------------------ columns
# (key, label, kind num|cat|bool|text, when entry|after|id, group, description)
COLS = [
    ("source", "Source", "cat", "id", "id", "backtest (run lit_live), paper (cloud ledger) or live (PC bot)"),
    ("day", "Day", "text", "id", "id", "trading day (18:00 -> 17:00 ET)"),
    ("entry_t", "Entry time (unix)", "num", "id", "id", "fill time"),
    ("span", "Span", "cat", "id", "id", "2026 H1 (picked on), 2026 H2 (check), 2021-25 (reference), or paper / live"),
    ("week", "ISO week", "text", "entry", "time", "calendar week of the trading day"),
    ("month", "Month", "text", "entry", "time", "YYYY-MM"),
    ("weekday", "Weekday", "cat", "entry", "time", "weekday of the trading day"),
    ("entry_hm", "Entry (ET)", "text", "entry", "time", "fill time, ET"),
    ("entry_min", "Entry minute (ET)", "num", "entry", "time", "minutes after midnight ET of the fill"),
    ("session", "Session", "cat", "entry", "time", "London 02-05, London late 05-08, NY pre 08-09:30, NY AM 09:30-11:30, NY midday, NY PM 13:30+"),
    ("killzone", "Killzone", "cat", "entry", "time", "London KZ 02:00-05:00, NY AM KZ 08:30-11:00, NY PM KZ 13:30-15:30, none"),
    ("macro", "ICT macro (fill)", "bool", "entry", "time", "the fill minute is inside an ICT macro window (02:33-03:00, 04:03-04:30, 08:50-09:10, ... 15:15-15:45)"),
    ("macro_trig", "ICT macro (CISD close)", "bool", "entry", "time", "the 5m CISD bar closed inside a macro window (lit_batch3a mac_trig)"),
    ("since_open", "Min since session open", "num", "entry", "time", "minutes since 02:00 (London) or 09:30 (NY cash open), whichever came last"),
    ("side", "Side", "cat", "entry", "setup", "LONG / SHORT"),
    ("swept", "Swept levels", "text", "entry", "setup", "every level the sweep took"),
    ("lvl_type", "Primary level type", "cat", "entry", "setup", "class of the nearest swept level: session box, PDH/PDL, PWH/PWL, PMH/PML, gap, build-up"),
    ("n_lvls", "Levels swept", "num", "entry", "setup", "how many levels the sweep took"),
    ("major", "Major level swept", "bool", "entry", "setup", "a PDH/PDL, PWH/PWL, PMH/PML or gap level was in the sweep"),
    ("lvl_age_h", "Level age (h)", "num", "entry", "setup", "hours since the primary swept level was printed"),
    ("lvl_touches", "Level touches", "num", "entry", "setup", "times price came within 0.1 ATR of the level before the sweep"),
    ("depth_pts", "Sweep depth (pts)", "num", "entry", "setup", "how far past the level the sweep went"),
    ("depth_atr", "Sweep depth (ATR)", "num", "entry", "setup", "the same in 5m ATR"),
    ("wick", "Wick rejection", "num", "entry", "setup", "wick of the sweep-extreme bar as a share of its range"),
    ("close_back", "Closed back inside", "bool", "entry", "setup", "the extreme bar closed back inside the swept level"),
    ("idm_n", "Inducements", "num", "entry", "setup", "inducement swings taken first (<= 1 ATR, <= 36 bars)"),
    ("idm_dist", "Inducement distance (ATR)", "num", "entry", "setup", "closest inducement swing's distance from the level"),
    ("disp", "Displacement body (ATR)", "num", "entry", "setup", "biggest candle body between the extreme and the CISD"),
    ("vec", "Vector candle", "bool", "entry", "setup", "a PVSRA climax candle in the trade's direction in the displacement"),
    ("sweep_bars", "Bars sweep -> CISD", "num", "entry", "setup", "5m bars from the first breach to the CISD close"),
    ("leg_bars", "Bars extreme -> CISD", "num", "entry", "setup", "5m bars from the extreme to the CISD close"),
    ("wait_min", "CISD -> entry (min)", "num", "entry", "entry", "minutes from the 5m CISD close to the fill"),
    ("fill", "Fill kind", "cat", "entry", "entry", "limit at the CISD level, or 1m CISD (next 1m open)"),
    ("stop_pts", "Stop (pts)", "num", "entry", "entry", "entry to stop (1 tick beyond the sweep extreme)"),
    ("stop_atr", "Stop (ATR)", "num", "entry", "entry", "the same in 5m ATR"),
    ("rr", "R:R to target", "num", "entry", "entry", "planned target distance / stop"),
    ("tgt_pts", "Target (pts)", "num", "entry", "entry", "distance to the VIX-band target (banked at 8R)"),
    ("obst_r", "Nearest opposing level (R)", "num", "entry", "entry", "distance to the nearest unbroken level on the target side, in R"),
    ("vix", "VIX", "num", "entry", "context", "prior VIX close"),
    ("vxn", "VXN", "num", "entry", "context", "prior VXN close"),
    ("vix_chg", "VIX change", "num", "entry", "context", "prior day's VIX change (points)"),
    ("gex_pos", "GEX positive", "bool", "entry", "context", "SqueezeMetrics SPX gamma exposure of the last close > 0"),
    ("gex_pct", "GEX percentile", "num", "entry", "context", "the last GEX reading's 1-year percentile"),
    ("atr_regime", "ATR / VIX move", "num", "entry", "context", "5m ATR over the VIX one-day move (how busy the tape is vs implied)"),
    ("atr_d", "Daily ATR (pts)", "num", "entry", "context", "average true range of the 14 days before"),
    ("day_rng", "Range so far (VIX moves)", "num", "entry", "context", "the day's range from 18:00 to the CISD, in VIX one-day moves"),
    ("asia_rng", "Asia range (VIX moves)", "num", "entry", "context", "18:00-24:00 range over the VIX one-day move"),
    ("lon_rng", "London range (ATR)", "num", "entry", "context", "02:00-05:00 box over the daily ATR (only once the box closed)"),
    ("gap", "Gap with trade (ATR)", "num", "entry", "context", "18:00 open minus the prior close, + = in the trade's direction, over the daily ATR"),
    ("prev_day", "Prior day with trade", "num", "entry", "context", "prior day's open->close in VIX moves, + = the trade's way"),
    ("prev_week", "Prior week with trade", "num", "entry", "context", "prior week's open->close in VIX moves, + = the trade's way"),
    ("pd18", "Entry vs 18:00 open", "num", "entry", "context", "entry minus the 18:00 open in VIX moves (+ = premium for a long)"),
    ("how", "High/low-of-week window", "bool", "entry", "context", "the sweep extreme fell Tue 03:00 - Wed 11:30 ET"),
    ("h4_draw", "4H draw with trade", "num", "entry", "context", "+1 nearest untaken 4H swing on the target side, -1 on the stop side"),
    ("es_swept", "ES swept too", "bool", "entry", "context", "ES took its own 3-hour low/high at the sweep"),
    ("monday", "Monday (rule on)", "bool", "entry", "rules", "Monday: the Monday rule decides the side"),
    ("wk_stops", "Stop-outs this week", "num", "entry", "rules", "LIT stop-outs earlier in the calendar week"),
    ("wk_half", "Weekly stop (half size)", "bool", "entry", "rules", "the trade ran at half size after 2 stop-outs this week"),
    ("news_day", "News day", "bool", "entry", "rules", "a scheduled high-impact US release that day"),
    ("news_next", "Min to next news", "num", "entry", "rules", "minutes from the entry to the next high-impact release (600 = none)"),
    ("micros", "Micros", "num", "entry", "size", "MNQ micros (backtest: the LIT size rule; paper / live: what was routed)"),
    ("risk_usd", "$ at risk", "num", "entry", "size", "micros x stop x $2"),
    ("exit", "Exit", "cat", "after", "outcome", "STOP, BE, CUT_T15 (15-minute check), TARGET or TIME (15:55 flat)"),
    ("outcome", "Outcome", "cat", "after", "outcome", "win (R >= +0.5), scratch, loss (R <= -0.5)"),
    ("r", "R", "num", "after", "outcome", "result in R (costs in)"),
    ("pnl", "$", "num", "after", "outcome", "result in $ (costs in)"),
    ("mfe", "MFE (R)", "num", "after", "outcome", "best open profit"),
    ("mae", "MAE (R)", "num", "after", "outcome", "worst open loss"),
    ("mins", "Minutes in trade", "num", "after", "outcome", "fill to exit"),
    ("t1r", "Min to +1R", "num", "after", "outcome", "fill to the first +1R touch (empty = never)"),
    ("heat", "Heat before BE (R)", "num", "after", "outcome", "worst open loss before the +1R touch (the whole trade when it never got there)"),
    ("gave_back", "+1R then gave it back", "bool", "after", "outcome", "reached +1R, ended under +0.5R"),
    ("clean_win", "Clean win", "bool", "after", "outcome", "hit the target and never went 0.5R under water"),
    ("chart", "Chart", "text", "id", "id", "trade chart id (replays)"),
]
KEYS = [c[0] for c in COLS]
# signs: every entry column except the clock minute (session / killzone / since-open cover it) and the size columns (micros
# and $ at risk follow the stop and the weekly stop by rule: a "sign" there is the stop's)
ENTRY = [c for c in COLS if c[3] == "entry" and c[2] in ("num", "cat", "bool") and c[0] != "entry_min" and c[4] != "size"]
MIN_GAP = 0.10                 # avg-R gap (each half) a consistent sign needs


def _num(x, nd=3):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if v != v or v in (float("inf"), float("-inf")):
        return None
    return round(v, nd)


def et_of(ts):
    return dt.datetime.fromtimestamp(int(ts), ET)


def macro_in(m0, m1):
    return any(m0 < b and m1 > a for a, b in MACROS)


def time_cols(day, entry_t):
    """Calendar / clock columns of a fill (known at entry)."""
    e = et_of(entry_t)
    m = e.hour * 60 + e.minute
    d = dt.date.fromisoformat(day)
    iso = d.isocalendar()
    sess = ("Asia" if m < 120 or m >= 1080 else "London 02-05" if m < 300 else "London late 05-08" if m < 480 else
            "NY pre 08-09:30" if m < 570 else "NY AM 09:30-11:30" if m < 690 else "NY midday" if m < 810 else "NY PM 13:30+")
    kz = ("London KZ" if 120 <= m < 300 else "NY AM KZ" if 510 <= m < 660 else "NY PM KZ" if 810 <= m < 930 else "none")
    so = m - 570 if m >= 570 else m - 120 if m >= 120 else None
    return {"week": "%d-W%02d" % (iso[0], iso[1]), "month": day[:7], "weekday": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][d.weekday()],
            "entry_hm": e.strftime("%H:%M"), "entry_min": m, "session": sess, "killzone": kz, "macro": macro_in(m, m + 1),
            "since_open": so}


def span_of(day, source="backtest"):
    if source != "backtest":
        return source
    for k, (a, z) in SPANS.items():
        if a <= day <= z:
            return k
    return "other"


def outcome_of(r):
    if r is None:
        return None
    return "win" if r >= WIN_R else "loss" if r <= LOSS_R else "scratch"


# ------------------------------------------------------------------------------------------------ feature context
class Ctx:
    """The market and every per-study helper the entry features need. M, C: the LIT market and its candidates (the full
    history, or a window cut at an entry for the look-ahead test)."""

    def __init__(self, M, C, B1=None, B5=None):
        from engine import lit
        from tools import lit_batch3a as B3
        from tools import lit_select as S
        self.M, self.C = M, C
        self.B1, self.B5 = B1, B5 or lit.bars_5m(M)
        K = object.__new__(B3.Mk)                      # lit_batch3a's market bundle, on this M
        K.M, K.C = M, C
        K.tod = B3.Mk._tod_avg(M)
        K.delta, K.dsrc = B3.Mk._delta(M)
        K.adj_t, K.adj_cum = B3.Mk._rolls()
        K.ncls = B3.Mk._name_cls(K)
        self.K = K
        self.ES = S.es_aligned(M)
        self.NEWS = S.news_cal()
        self.WK = S.week_open_close(M)
        from tools import lit_context as LC
        self.day_ctx = LC.context()
        self.dk = {str(d): k for k, (d, s, e) in enumerate(M.days)}
        self.R = type("R", (), {"M": M})()             # lit_batch3b helpers take a bundle with .M
        from tools import lit_batch3b as B3B
        B3B._ATRD.clear()                              # its daily-ATR cache is keyed by day index: one market at a time
        self.cand = {(z["day"], int(z["dir"]), int(z["i"])): z for z in C}


def plans_by_day(X: "Ctx", P, days):
    """{(day, i, dir): (z, plan, earlier accepted setups that day)}: what engine/lit_learn.live_features hands to feats."""
    from tools import lit_select as S
    acc = collections.defaultdict(list)
    out = {}
    for z in X.C:
        if z["day"] not in days:
            continue
        pl = S.plan_of(X.M, z, P)
        if pl is None:
            continue
        out[(z["day"], int(z["i"]), int(z["dir"]))] = (z, pl, list(acc[z["day"]]))
        acc[z["day"]].append(z)
    return out


def entry_feats(X: Ctx, z, pl, same, hist, t):
    """Every entry column of trade t (setup z, plan pl). Uses bars up to the trade's fill only (z: candidates(), known at
    the CISD close; hist: finished trades before the CISD close; day context: prior closes)."""
    import numpy as np
    from engine import lit
    from engine import lit_learn as LL
    from tools import lit_batch3a as B3
    from tools import lit_batch3b as B3B
    from tools import lit_select as S
    M = X.M
    f = S.feats(M, z, pl, X.ES, X.NEWS, X.WK, same, hist)
    f.update(LL.h4_feats(M, z["i"], z["dir"]))
    g = B3.features(X.K, z)
    d, k, i = int(z["dir"]), int(z["k"]), int(z["i"])
    x = M.ctx[k]
    ad = B3B.atr_d(X.R, k)
    dc = X.day_ctx.get(z["day"]) or {}
    lev = max(z["sw"].values())
    o = {
        "macro_trig": bool(g["mac_trig"]), "side": "LONG" if d == 1 else "SHORT", "swept": " ".join(z["swept"]),
        "lvl_type": {"pd": "PDH/PDL", "pw": "PWH/PWL", "pm": "PMH/PML", "gap": "gap", "asia": "Asia box", "london": "London box",
                     "ny": "NY box", "pre": "premarket box", "x_ny": "NY box", "buildup": "build-up"}.get(g["prim_cls"], g["prim_cls"]),
        "n_lvls": int(g["n_lvls"]), "major": bool(f["major"]), "lvl_age_h": _num(g["age_h"], 2), "lvl_touches": int(g["tc1"]),
        "depth_pts": _num(lev - z["ext_d"], 2), "depth_atr": _num(z["depth_atr"]), "wick": _num(g["rj_wick_rng"]),
        "close_back": bool(g["rj_back"]), "idm_n": int(f["idm_n"]), "idm_dist": _num(f["idm_dist"]), "disp": _num(z["disp"]),
        "vec": bool(z["vec"]), "sweep_bars": int(g["sp_sweep"]), "leg_bars": int(g["sp_ext"]),
        "wait_min": _num((int(t["entry_t"]) - (int(M.t[i]) + 300)) / 60.0, 1),
        "stop_pts": _num(t["risk_pts"], 2), "stop_atr": _num(float(t["risk_pts"]) / max(float(M.atr[i]), 1e-9)),
        "rr": _num(abs(float(t["target_px"]) - float(t["entry_px"])) / float(t["risk_pts"]), 2),
        "tgt_pts": _num(abs(float(t["target_px"]) - float(t["entry_px"])), 2), "obst_r": _num(f["obst_r"]),
        "vix": _num(x.get("vix"), 2), "vxn": _num(x.get("vxn"), 2), "vix_chg": _num(f["vix_chg"], 2),
        "gex_pos": (dc["gex"] > 0) if dc.get("gex") is not None else None, "gex_pct": _num(dc.get("gex_pct")),
        "atr_regime": _num(f["atr_vm"], 4), "atr_d": _num(ad, 1), "day_rng": _num(f["rng_used"]), "asia_rng": _num(f["asia_rng"]),
        "prev_day": _num(f["prev_day"]), "prev_week": _num(f["prev_week"]), "pd18": _num(f["pd18"]), "how": bool(z["how"]),
        "h4_draw": _num(f["h4_draw"], 0), "es_swept": None if f["es_swept"] != f["es_swept"] else bool(f["es_swept"]),
        "monday": int(z["dow"]) == 0, "wk_stops": int(f["wk_stops"]), "news_day": bool(f["news_day"]), "news_next": _num(f["news_next"], 0),
    }
    lb = x.get("lon25")                            # London box 02:00-05:00, only once its last bar closed before the CISD close
    o["lon_rng"] = _num((lb[0] - lb[1]) / ad, 3) if (lb and ad and lb[2] <= i) else None
    if k > 0 and ad:
        pc = float(M.c[M.days[k - 1][2] - 1])
        o["gap"] = _num((float(x["open18"]) - pc) * d / ad, 3)
    else:
        o["gap"] = None
    return o


def outcome_cols(X: Ctx, t):
    """Outcome columns ('after'): walk the executor bars of the trade (1m when it ran on 1m, else 5m)."""
    import numpy as np
    B = X.B1 if (int(t.get("tf") or 5) == 1 and X.B1 is not None) else X.B5
    d = int(t["dir"])
    hd, ld, _, _ = B.dirs(d)
    ep, risk = float(t["entry_px"]) * d, float(t["risk_pts"])
    a = int(np.searchsorted(B.t, int(t["entry_t"])))
    b = int(np.searchsorted(B.t, int(t["exit_t"]) - B.secs, side="right"))
    t1r, heat = None, 0.0
    for j in range(a, max(a + 1, b)):
        if j >= B.n:
            break
        if (hd[j] - ep) / risk >= 1.0:
            t1r = round((int(B.t[j]) + B.secs - int(t["entry_t"])) / 60.0, 1)
            break
        heat = max(heat, (ep - ld[j]) / risk)
    if t1r is None or float(t["mfe"]) < 1.0:        # the engine's MFE decides (a bar that hit the stop first never counts)
        t1r, heat = None, float(t["mae"])
    r = _num(t["r"])
    mfe, mae = _num(t["mfe"]), _num(t["mae"])
    return {"exit": t["exit"], "outcome": outcome_of(r), "r": r, "pnl": _num(t["pnl"], 2), "mfe": mfe, "mae": mae,
            "mins": _num((int(t["exit_t"]) - int(t["entry_t"])) / 60.0, 1), "t1r": t1r, "heat": _num(heat),
            "gave_back": bool(mfe is not None and mfe >= 1.0 and r is not None and r < 0.5),
            "clean_win": bool(t["exit"] == "TARGET" and mae is not None and mae < 0.5)}


# ------------------------------------------------------------------------------------------------ backtest rows
def _run_stamp():
    from tools import runlib as rl
    run = rl.load(RUN_ID)
    c = run["trade_cols"]
    key = [(r[c.index("day")], r[c.index("entry_t")], r[c.index("pnl")]) for r in run["trades"]]
    return run, hashlib.sha1(json.dumps(key).encode()).hexdigest()[:12]


def live_params():
    from engine import lit
    lm = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))
    return {**lit.DEFAULTS, **lm["lit"]}


def backtest_trades(P=None):
    """The live LIT config replayed (== run lit_live), with the market it ran on."""
    from tools import lit_final as F
    P = P or live_params()
    M, C = F.market(P["ref"], P["extra_boxes"])
    B1, B5 = F.bars(M, "1m"), F.bars(M, "5m")
    T = F.run(P)
    return M, C, B1, B5, T, P


def hist_of(T):
    return sorted([{"r1": float(t["r"]), "exit": t["exit"], "day": t["day"], "exit_t": int(t["exit_t"])} for t in T],
                  key=lambda h: h["exit_t"])


def rows_for(X: Ctx, T, P, report=None, charts=None, T_hist=None):
    """One row per trade of T (run_x trades with i / dir / day), entry features + outcomes + report fields."""
    days = {t["day"] for t in T}
    plans = plans_by_day(X, P, days)
    H = hist_of(T_hist if T_hist is not None else T)
    report = report or {}
    charts = charts or {}
    rows = []
    for t in T:
        key = (t["day"], int(t["i"]), int(t["dir"]))
        z, pl, same = plans[key]
        t_sig = int(X.M.t[z["i"]]) + 300
        hist = [h for h in H if h["exit_t"] <= t_sig]
        rw = {"source": "backtest", "day": t["day"], "entry_t": int(t["entry_t"]), "span": span_of(t["day"])}
        rw.update(time_cols(t["day"], t["entry_t"]))
        rw.update(entry_feats(X, z, pl, same, hist, t))
        bt = report.get((t["day"], int(t["entry_t"]))) or {}
        rw["fill"] = "limit" if bt.get("entry_kind") == "limit" else ("1m CISD" if int(t.get("tf") or 5) == 1 else "5m CISD (no 1m data)")
        rw["wk_half"] = bool(bt.get("weekly_stop")) if bt else bool(t.get("size_mult") and t["size_mult"] < 1)
        rw["micros"] = int(t["qty"])
        rw["risk_usd"] = _num(t["risk_usd"], 2)
        rw.update(outcome_cols(X, t))
        rw["chart"] = charts.get((t["day"], int(t["entry_t"])))
        rows.append(rw)
    return rows


# ------------------------------------------------------------------------------------------------ paper / live rows
def _journal(path):
    out = []
    try:
        with open(path, encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if ln:
                    try:
                        out.append(json.loads(ln))
                    except ValueError:
                        pass
    except OSError:
        pass
    return out


def _from_f(f):
    """Journal features (tools/lit_select.py feats, the same as the backtest's) -> intel columns."""
    if not isinstance(f, dict):
        return {}
    g = lambda k, nd=3: _num(f.get(k), nd)
    b = lambda k: None if f.get(k) is None or _num(f.get(k)) is None else bool(f.get(k))
    return {"n_lvls": None, "major": b("major"), "depth_atr": g("depth"), "idm_n": None if g("idm_n") is None else int(f["idm_n"]),
            "idm_dist": g("idm_dist"), "disp": g("disp"), "vec": b("vec"), "leg_bars": None if g("leg_bars") is None else int(f["leg_bars"]),
            "stop_atr": g("stop_atr"), "obst_r": g("obst_r"), "vix": g("vix", 2), "vix_chg": g("vix_chg", 2),
            "atr_regime": g("atr_vm", 4), "day_rng": g("rng_used"), "asia_rng": g("asia_rng"), "prev_day": g("prev_day"),
            "prev_week": g("prev_week"), "pd18": g("pd18"), "how": b("how"), "h4_draw": g("h4_draw", 0), "es_swept": b("es_swept"),
            "wk_stops": None if g("wk_stops") is None else int(f["wk_stops"]), "news_day": b("news_day"), "news_next": g("news_next", 0)}


def _paper_row(source, day, entry_t, side, entry_px, stop_px, target_px, risk_pts, qty, exit_, r, pnl, exit_t=None,
               mfe=None, mae=None, swept=None, f=None, wk_mult=None):
    rw = {k: None for k in KEYS}
    rw.update({"source": source, "day": day, "entry_t": int(entry_t), "span": source})
    rw.update(time_cols(day, entry_t))
    rw["side"] = side
    if swept:
        rw["swept"] = " ".join(swept)
        rw["n_lvls"] = len(swept)
    risk = _num(risk_pts, 2) or (abs(float(entry_px) - float(stop_px)) if entry_px and stop_px else None)
    rw["stop_pts"] = _num(risk, 2)
    if target_px and entry_px and risk:
        rw["tgt_pts"] = _num(abs(float(target_px) - float(entry_px)), 2)
        rw["rr"] = _num(rw["tgt_pts"] / risk, 2)
    rw["micros"] = int(qty) if qty else None
    rw["risk_usd"] = _num(risk * 2.0 * int(qty), 2) if (risk and qty) else None
    rw["monday"] = dt.date.fromisoformat(day).weekday() == 0
    if wk_mult is not None:
        rw["wk_half"] = float(wk_mult) < 1.0
    for k, v in _from_f(f).items():
        if v is not None:
            rw[k] = v
    rr = _num(r)
    rw.update({"exit": exit_, "r": rr, "outcome": outcome_of(rr), "pnl": _num(pnl, 2), "mfe": _num(mfe), "mae": _num(mae)})
    if exit_t:
        rw["mins"] = _num((int(exit_t) - int(entry_t)) / 60.0, 1)
    if rw["mfe"] is not None and rr is not None:
        rw["gave_back"] = rw["mfe"] >= 1.0 and rr < 0.5
    if rw["mae"] is not None:
        rw["clean_win"] = exit_ == "TARGET" and rw["mae"] < 0.5
    return rw


def live_rows(state=None, journal=None):
    """Paper (cloud ledger) and live (PC) rows from the cloud state and the learning journal, newest last. A trade on
    both is listed once per source; the journal adds its features to the ledger row of the same entry."""
    state = state or {}
    J = journal or []
    jf = {}
    for r in J:
        if r.get("source") in ("cloud", "pc") and r.get("entry_t"):
            jf[(r["source"], int(r["entry_t"]))] = r
    rows = {}
    for k, v in (state.get("ledger") or {}).items():
        if not str(k).isdigit() or not isinstance(v, dict) or v.get("taken") is False:
            continue
        if not v.get("exit") or v.get("exit") == "OPEN":
            continue
        et_ = int(k)
        jr = jf.get(("cloud", et_)) or {}
        rows[("paper", et_)] = _paper_row("paper", v.get("day") or jr.get("day"), et_, v.get("side"), v.get("entry_px"), v.get("stop_px"),
                                          v.get("target_px"), v.get("risk_pts"), v.get("qty"), v.get("exit"), v.get("R"), v.get("usd"),
                                          exit_t=v.get("exit_ts"), mfe=jr.get("mfe"), mae=jr.get("mae"), swept=jr.get("swept"),
                                          f=jr.get("f"), wk_mult=jr.get("wk_mult"))
    acct = ((state.get("pc") or {}).get("acct") or {}) if isinstance(state.get("pc"), dict) else {}
    for t in acct.get("trades") or []:
        if not t.get("entry_t") or not t.get("exit"):
            continue
        et_ = int(t["entry_t"])
        jr = jf.get(("pc", et_)) or {}
        rows[("live", et_)] = _paper_row("live", t.get("day") or jr.get("day") or et_of(et_).date().isoformat(), et_, t.get("side"),
                                         t.get("entry"), t.get("stop"), t.get("target"), t.get("risk_pts"), t.get("qty"), t.get("exit"),
                                         t.get("r"), t.get("pnl"), exit_t=t.get("exit_t"), mfe=t.get("mfe") if t.get("mfe") is not None else jr.get("mfe"),
                                         mae=jr.get("mae"), swept=t.get("swept") or jr.get("swept"), f=jr.get("f"))
    for (src, et_), r in jf.items():                 # journal records whose ledger row is gone (the ledger keeps recent days)
        s = "paper" if src == "cloud" else "live"
        if (s, et_) in rows or not r.get("day") or not r.get("exit"):
            continue
        rows[(s, et_)] = _paper_row(s, r["day"], et_, r.get("side"), r.get("entry_px"), r.get("stop_px"), r.get("target_px"),
                                    r.get("risk_pts"), r.get("qty"), r.get("exit"), r.get("r"), r.get("pnl"), exit_t=r.get("exit_t"),
                                    mfe=r.get("mfe"), mae=r.get("mae"), swept=r.get("swept"), f=r.get("f"), wk_mult=r.get("wk_mult"))
    return [rows[k] for k in sorted(rows, key=lambda k: k[1])]


# ------------------------------------------------------------------------------------------------ signs
def stats(rows):
    """trades, win % ($ > 0, as every LIT report counts it), avg R, PF ($), net $ of rows."""
    n = len(rows)
    if not n:
        return {"n": 0, "win": None, "avg_r": None, "pf": None, "net": 0.0}
    rs = [r["r"] or 0.0 for r in rows]
    ps = [r["pnl"] or 0.0 for r in rows]
    gw, gl = sum(p for p in ps if p > 0), -sum(p for p in ps if p < 0)
    return {"n": n, "win": round(100.0 * sum(1 for p in ps if p > 0) / n, 1), "avg_r": round(sum(rs) / n, 3),
            "pf": round(gw / gl, 2) if gl > 0 else (None if gw == 0 else 99.0), "net": round(sum(ps), 2)}


def terciles(vals):
    """Two cut points at the 1/3 and 2/3 quantiles (lower-inclusive buckets); None when the values do not split."""
    v = sorted(x for x in vals if x is not None)
    if len(v) < 9:
        return None
    q = lambda p: v[min(len(v) - 1, int(math.floor(p * (len(v) - 1) + 0.5)))]
    a, b = q(1 / 3), q(2 / 3)
    if a == b:
        if a == v[0] and b != v[-1]:
            b = next(x for x in v if x > a)
        elif b == v[-1] and a != v[0]:
            a = max(x for x in v if x < b)
        else:
            return None
    return [a, b]


def bucket_of(v, kind, cuts):
    if v is None:
        return None
    if kind == "bool":
        return "yes" if v else "no"
    if kind == "cat":
        return str(v)
    if cuts is None:
        return None
    a, b = cuts
    return "low" if v <= a else "mid" if v <= b else "high"


def _fmt(x):
    return ("%g" % round(x, 2)) if isinstance(x, (int, float)) else str(x)


def bucket_label(kind, b, cuts):
    if kind != "num" or cuts is None:
        return b
    a, z = cuts
    return {"low": f"<= {_fmt(a)}", "mid": f"{_fmt(a)} - {_fmt(z)}", "high": f"> {_fmt(z)}"}[b]


def signs(rows):
    """Per entry feature: buckets x spans (H1 / H2 / 2021-25) with trades, win %, avg R, PF, $; a verdict per feature."""
    by_span = {s: [r for r in rows if r["source"] == "backtest" and r["span"] == s] for s in SPANS}
    out = []
    for key, label, kind, when, group, desc in ENTRY:
        vals_h1 = [r.get(key) for r in by_span["H1"]]
        cuts = terciles(vals_h1) if kind == "num" else None
        if kind == "num" and cuts is None:
            continue
        cats = []
        for s in SPANS:
            for r in by_span[s]:
                b = bucket_of(r.get(key), kind, cuts)
                if b is not None and b not in cats:
                    cats.append(b)
        if kind == "num":
            cats = [c for c in ("low", "mid", "high") if c in cats]
        elif kind == "bool":
            cats = [c for c in ("yes", "no") if c in cats]
        else:
            n_h1 = collections.Counter(bucket_of(r.get(key), kind, cuts) for r in by_span["H1"])
            cats = sorted(cats, key=lambda c: -n_h1.get(c, 0))
        if len(cats) < 2:
            continue
        B = []
        for c in cats:
            row = {"b": c, "label": bucket_label(kind, c, cuts)}
            for s in SPANS:
                row[s] = stats([r for r in by_span[s] if bucket_of(r.get(key), kind, cuts) == c])
            B.append(row)
        v = verdict(key, kind, cats, by_span, cuts)
        out.append({"key": key, "label": label, "kind": kind, "group": group, "desc": desc, "cuts": cuts, "buckets": B, **v})
    out.sort(key=lambda s: (not s["consistent"], -(s.get("strength") or 0)))
    return out


def verdict(key, kind, cats, by_span, cuts):
    """Which side does better in H1 and in H2: numeric = high vs low tercile; bool = yes vs no; category = the H1-best
    category (>= MIN_SIDE trades) vs every other trade. Consistent = same side better in both halves, >= MIN_SIDE trades
    per side per half. Strength = the smaller of the two avg-R gaps."""
    def sides(span):
        R = by_span[span]
        bk = [(bucket_of(r.get(key), kind, cuts), r) for r in R]
        if kind == "num":
            return [r for b, r in bk if b == "high"], [r for b, r in bk if b == "low"]
        if kind == "bool":
            return [r for b, r in bk if b == "yes"], [r for b, r in bk if b == "no"]
        return [r for b, r in bk if b == pick], [r for b, r in bk if b is not None and b != pick]
    pick = None
    if kind == "cat":
        best = None
        for c in cats:
            R = [r for r in by_span["H1"] if bucket_of(r.get(key), kind, cuts) == c]
            rest = [r for r in by_span["H1"] if bucket_of(r.get(key), kind, cuts) not in (None, c)]
            if len(R) < MIN_SIDE or len(rest) < MIN_SIDE:
                continue
            gap = stats(R)["avg_r"] - stats(rest)["avg_r"]
            if best is None or abs(gap) > abs(best[1]):
                best = (c, gap)
        if best is None:
            return {"consistent": False, "why": f"no category with {MIN_SIDE}+ trades on each side in H1", "a": None, "b": None}
        pick = best[0]
    gaps, ns = {}, {}
    for s in SPANS:
        A, Bb = sides(s)
        ns[s] = (len(A), len(Bb))
        sa, sb = stats(A), stats(Bb)
        gaps[s] = (sa["avg_r"] - sb["avg_r"]) if (A and Bb) else None
    a_lab = {"num": "high", "bool": "yes", "cat": pick}[kind]
    b_lab = {"num": "low", "bool": "no", "cat": "the rest"}[kind]
    ok_n = all(min(ns[s]) >= MIN_SIDE for s in ("H1", "H2"))
    g1, g2, g5 = gaps["H1"], gaps["H2"], gaps["2021-25"]
    same = g1 is not None and g2 is not None and g1 * g2 > 0
    cons = bool(ok_n and same and min(abs(g1), abs(g2)) >= MIN_GAP)
    better = a_lab if (g1 or 0) > 0 else b_lab
    held5 = None if g5 is None else (g5 * (g1 or 0) > 0 and abs(g5) >= MIN_GAP / 2)   # 2021-25: same side by >= 0.05R
    why = (f"{better} better in H1 ({g1:+.2f}R) and H2 ({g2:+.2f}R)" if cons else
           (f"too few trades (H1 {ns['H1'][0]}/{ns['H1'][1]}, H2 {ns['H2'][0]}/{ns['H2'][1]})" if not ok_n else
            f"same side but small: H1 {g1:+.2f}R, H2 {g2:+.2f}R (under {MIN_GAP}R)" if same else
            f"flips: H1 {g1:+.2f}R, H2 {g2:+.2f}R" if (g1 is not None and g2 is not None) else "no comparison"))
    return {"consistent": cons, "a": a_lab, "b": b_lab, "better": better if cons else None, "gap_h1": _num(g1), "gap_h2": _num(g2),
            "gap_5y": _num(g5), "held_5y": held5, "n_sides": ns, "strength": _num(min(abs(g1), abs(g2)) if cons else 0.0),
            "why": why}


def chance_level(rows, n=20, seed=7):
    """How many features look 'consistent' when the 2026 outcomes are shuffled inside each half (no real link between
    feature and result): the average count over n shuffles. The real count is only worth something above this."""
    import random
    rng = random.Random(seed)
    oc = ("r", "pnl")
    base = [r for r in rows if r["source"] == "backtest"]
    cnt = []
    for _ in range(n):
        sh = []
        for s in SPANS:
            R = [r for r in base if r["span"] == s]
            res = [(r["r"], r["pnl"]) for r in R]
            rng.shuffle(res)
            sh += [{**r, "r": a, "pnl": b} for r, (a, b) in zip(R, res)]
        cnt.append(sum(1 for x in signs(sh) if x["consistent"]))
    return round(sum(cnt) / len(cnt), 1)


def summary(sg, rows, chance=None):
    """Plain-language 'what winners / losers have in common' from the consistent signs."""
    lab = {r[0]: r[1] for r in COLS}
    win_s, lose_s = [], []
    for s in sg:
        if not s["consistent"]:
            continue
        good = s["better"]
        bad = s["b"] if good == s["a"] else s["a"]
        def desc(side):
            if s["kind"] == "num":
                cut = s["cuts"][1] if side == "high" else s["cuts"][0]
                return f"{s['label']} {'above' if side == 'high' else 'at or below'} {_fmt(cut)}"
            if s["kind"] == "bool":
                return s["label"] + (": yes" if side == "yes" else ": no")
            if side == "the rest":
                return f"{s['label']}: not {s['a']}"
            return f"{s['label']}: {side}"
        line = lambda side, g: (f"{desc(side)} (avg R {abs(s['gap_h1']):.2f} higher in H1, {abs(s['gap_h2']):.2f} in H2 than the other side; "
                                + ("2021-25 " + (f"{s['gap_5y'] * (1 if good == s['a'] else -1):+.2f}R" if s['gap_5y'] is not None else "n/a")) + ")")
        win_s.append({"key": s["key"], "text": line(good, 1), "strength": s["strength"], "held_5y": s["held_5y"]})
        lose_s.append({"key": s["key"], "text": desc(bad) + f" (avg R {abs(s['gap_h1']):.2f} lower in H1, {abs(s['gap_h2']):.2f} in H2)",
                       "strength": s["strength"], "held_5y": s["held_5y"]})
    bt26 = [r for r in rows if r["source"] == "backtest" and r["span"] in ("H1", "H2")]
    gb = [r for r in bt26 if r.get("gave_back")]
    cw = [r for r in bt26 if r.get("clean_win")]
    def med(R, k):
        v = sorted(x[k] for x in R if x.get(k) is not None)
        return v[len(v) // 2] if v else None
    comp_keys = ["stop_pts", "rr", "depth_atr", "disp", "idm_n", "vix", "atr_regime", "entry_min", "t1r", "mins", "heat"]
    groups = {"gave_back": {"n": len(gb), "net": round(sum(r["pnl"] or 0 for r in gb), 2), "med": {k: med(gb, k) for k in comp_keys}},
              "clean_win": {"n": len(cw), "net": round(sum(r["pnl"] or 0 for r in cw), 2), "med": {k: med(cw, k) for k in comp_keys}},
              "all_2026": {"n": len(bt26), "net": round(sum(r["pnl"] or 0 for r in bt26), 2), "med": {k: med(bt26, k) for k in comp_keys}},
              "labels": {k: lab.get(k, k) for k in comp_keys}}
    n_tot = sum(1 for s in sg)
    n_cons = sum(1 for s in sg if s["consistent"])
    return {"winners": win_s[:12], "losers": lose_s[:12], "n_features": n_tot, "n_consistent": n_cons, "chance": chance,
            "min_gap": MIN_GAP, "groups": groups,
            "warning": ("Descriptive, not rules. These are averages of past trades: most of these features were already tested "
                        "as filters or size tilts in the write-ups below and none passed the adopt test. With 120 trades in 2026 "
                        "a bucket holds 15-40 trades, so a gap of a few tenths of an R is often noise; 'consistent' only means the "
                        "same side was better in both 2026 halves by at least " + f"{MIN_GAP}R" + ". Shuffled outcomes (no real link) make "
                        + (f"{chance} of {n_tot}" if chance is not None else "several") + " features look consistent too."),
            "writeups": [{"slug": s, "label": l} for s, l in WRITEUPS]}


def span_totals(rows):
    out = {}
    for s in list(SPANS) + ["paper", "live"]:
        R = [r for r in rows if r["span"] == s]
        out[s] = stats(R)
    return out


# ------------------------------------------------------------------------------------------------ build / merge
def build(force=False):
    run, stamp = _run_stamp()
    old = _load(OUT)
    if old and not force and old.get("meta", {}).get("run_stamp") == stamp and old.get("meta", {}).get("v") == VERSION:
        print(f"trade_intel: current (run {RUN_ID} {stamp})")
        return old
    import time
    t0 = time.time()
    M, C, B1, B5, T, P = backtest_trades()
    c = run["trade_cols"]
    k_run = sorted((r[c.index("day")], int(r[c.index("entry_t")])) for r in run["trades"])
    k_now = sorted((t["day"], int(t["entry_t"])) for t in T)
    if k_run != k_now:
        raise SystemExit(f"live_model.json lit no longer reproduces run {RUN_ID}: rerun tools/lit_losses.py live first")
    X = Ctx(M, C, B1, B5)
    bt = _load(os.path.join(ROOT, "research", "lab", "backtest_live.json")) or {}
    report = {(t.get("day"), int(t.get("entry_t") or 0)): t for t in bt.get("trades") or []}
    rp = _load(os.path.join(ROOT, "research", "lab", "replays.json")) or {}
    charts = {(r.get("day"), int((r.get("entry") or {}).get("t") or 0)): cid for cid, r in (rp.get("charts") or {}).items()}
    rows = rows_for(X, T, P, report, charts)
    data = assemble(rows, {"run": RUN_ID, "run_stamp": stamp, "run_built": run.get("built"), "v": VERSION,
                           "built": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "seconds": round(time.time() - t0, 1)})
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(data, fh, separators=(",", ":"))
    print(f"trade_intel -> {OUT}: {len(rows)} backtest rows, {data['summary']['n_consistent']}/{data['summary']['n_features']} "
          f"consistent signs, {os.path.getsize(OUT) // 1024} KB, {data['meta']['seconds']} s")
    return data


def _med(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def _eff_stats(R):
    """Exit efficiency of a set of trade rows (dicts with r, mfe, mae, heat, exit)."""
    R = [r for r in R if r.get("r") is not None and r.get("mfe") is not None]
    up = [r for r in R if r["mfe"] >= 1.0]                              # reached +1R (BE moves there)
    pos = [r for r in R if r["mfe"] > 0.25]
    cap = [max(-1.0, min(1.0, r["r"] / r["mfe"])) for r in pos]         # share of the best move kept (clipped -100..100%)
    loss = [r for r in R if r["r"] <= LOSS_R]
    rnd = lambda v, nd=2: None if v is None else round(float(v), nd)
    return {"n": len(R), "capture_med": rnd(100 * _med(cap), 1) if cap else None,
            "capture_avg": rnd(100 * sum(cap) / len(cap), 1) if cap else None,
            "capture_sum": rnd(100 * sum(r["r"] for r in pos) / sum(r["mfe"] for r in pos), 1) if pos else None,
            "mfe_avg": rnd(sum(r["mfe"] for r in R) / len(R)) if R else None, "r_avg": rnd(sum(r["r"] for r in R) / len(R)) if R else None,
            "capture_up1": rnd(100 * _med([max(-1.0, min(1.0, r["r"] / r["mfe"])) for r in up]), 1) if up else None,
            "capture_up1_sum": rnd(100 * sum(r["r"] for r in up) / sum(r["mfe"] for r in up), 1) if up else None,
            "n_up1": len(up), "giveback_avg": rnd(sum(r["mfe"] - r["r"] for r in up) / len(up)) if up else None,
            "gave_back": sum(1 for r in up if r["r"] < 0.5),
            "loss_n": len(loss), "loss_mfe_avg": rnd(sum(r["mfe"] for r in loss) / len(loss)) if loss else None,
            "heat_avg": rnd(sum(r["heat"] for r in R if r.get("heat") is not None) / max(1, sum(1 for r in R if r.get("heat") is not None)))
            if any(r.get("heat") is not None for r in R) else None}


def exit_eff(rows):
    """rows: dict rows (backtest + paper / live). -> spans, by exit type (2026), by month (2026 + paper / live: the trend),
    the 2026 trade list (for the scatter) and a plain-language summary."""
    span = lambda s: [r for r in rows if r.get("span") == s]
    r26 = [r for r in rows if r.get("source") == "backtest" and r.get("span") in ("H1", "H2")]
    out = {"spans": {s: _eff_stats(span(s)) for s in ("H1", "H2", "2021-25", "paper", "live")},
           "y2026": _eff_stats(r26)}
    ex = collections.defaultdict(list)
    for r in r26:
        ex[r.get("exit") or "?"].append(r)
    out["by_exit"] = [{"exit": k, **_eff_stats(v)} for k, v in sorted(ex.items(), key=lambda kv: -len(kv[1]))]
    mo = collections.defaultdict(list)
    for r in rows:
        if r.get("day") and (r.get("source") != "backtest" or r.get("span") in ("H1", "H2")):
            mo[(r["day"][:7], "backtest" if r.get("source") == "backtest" else r.get("source"))].append(r)
    out["by_month"] = [{"month": m, "source": s, **_eff_stats(v)} for (m, s), v in sorted(mo.items())]
    out["trades"] = [[r["day"], r.get("source"), r.get("exit"), r.get("r"), r.get("mfe"), r.get("mae")]
                     for r in r26 + [r for r in rows if r.get("source") != "backtest"] if r.get("mfe") is not None]
    y = out["y2026"]
    if y["n"]:
        out["text"] = (f"2026: the trades kept {y['capture_sum']:.0f}% of all the open profit they saw (exit R / best R, summed). "
                       f"{y['n_up1']} of {y['n']} reached +1R: they kept {y['capture_up1_sum']:.0f}% of their best move (median trade "
                       f"{y['capture_up1']:.0f}%) and gave back {y['giveback_avg']:.1f}R on average; {y['gave_back']} of them ended "
                       f"under +0.5R (mostly breakeven exits). Losers were up {y['loss_mfe_avg']:.2f}R on average before the stop.")
    return out


def assemble(rows, meta):
    sg = signs(rows)
    ch = chance_level(rows)
    return {"meta": {**meta, "win_rule": f"win = R >= +{WIN_R}, loss = R <= {LOSS_R}, scratch in between",
                     "spans": {k: list(v) for k, v in SPANS.items()}, "min_side": MIN_SIDE,
                     "sources": dict(collections.Counter(r["source"] for r in rows))},
            "cols": [{"key": k, "label": l, "kind": kd, "when": w, "group": g, "desc": d} for k, l, kd, w, g, d in COLS],
            "rows": [[r.get(k) for k in KEYS] for r in rows], "signs": sg, "summary": summary(sg, rows, ch), "totals": span_totals(rows),
            "exit_eff": exit_eff(rows)}


def _load(p):
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def merge_live(data, state=None, journal=None):
    """The stored backtest file + the paper / live rows of now (fast: no engine). Signs stay the backtest's (paper samples
    are a handful of trades); totals gain the paper / live lines."""
    if not data:
        return None
    ix = data["cols"]
    keys = [c["key"] for c in ix]
    base = [r for r in data["rows"] if r[keys.index("source")] == "backtest"]
    extra = live_rows(state, journal)
    rows = base + [[r.get(k) for k in keys] for r in extra]
    out = {**data, "rows": rows}
    meta = dict(data.get("meta") or {})
    meta["sources"] = {**{k: v for k, v in (meta.get("sources") or {}).items() if k == "backtest"},
                       **collections.Counter(r["source"] for r in extra)}
    meta["merged"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    out["meta"] = meta
    dicts = [dict(zip(keys, r)) for r in rows]
    out["totals"] = span_totals(dicts)
    out["exit_eff"] = exit_eff(dicts)
    return out


def compact(full):
    """The small cut for data.json: meta, totals, the plain-language summary, the consistent signs (without bucket rows
    for the rest) and the paper / live rows. The full file goes to the site as intel.json (lazy)."""
    if not full:
        return None
    keys = [c["key"] for c in full["cols"]]
    si = keys.index("source")
    cons = [s for s in full["signs"] if s["consistent"]][:10]
    return {"meta": full["meta"], "totals": full["totals"], "summary": full["summary"],
            "top": [{k: s[k] for k in ("key", "label", "kind", "better", "a", "b", "gap_h1", "gap_h2", "gap_5y", "held_5y", "why", "buckets", "cuts")}
                    for s in cons],
            "cols": keys, "live_rows": [r for r in full["rows"] if r[si] != "backtest"][-60:], "full": "intel.json",
            "exit_eff": {k: v for k, v in (full.get("exit_eff") or {}).items() if k != "trades"} or None}


def main(argv):
    if "--check" in argv:
        run, stamp = _run_stamp()
        old = _load(OUT) or {}
        ok = (old.get("meta") or {}).get("run_stamp") == stamp
        print(f"trade_intel: {'current' if ok else 'STALE'} (run {RUN_ID} {stamp}, file {(old.get('meta') or {}).get('run_stamp')})")
        return 0 if ok else 1
    if "--exit-eff" in argv:
        d = _load(OUT)
        if not d:
            raise SystemExit("research/lab/trade_intel.json missing: run python -X utf8 tools/trade_intel.py")
        keys = [c["key"] for c in d["cols"]]
        d["exit_eff"] = exit_eff([dict(zip(keys, r)) for r in d["rows"]])
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(d, fh, separators=(",", ":"))
        print(d["exit_eff"].get("text"))
        return 0
    build(force="--force" in argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
