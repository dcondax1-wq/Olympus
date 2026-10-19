"""The LIT backtest in the shape the PC dashboard pages expect from /api/backtest (engine/backtest.py run()), so the Command
Center, Chart, Replays, Journal, Reports and Weekly Review read LIT while the previous strategy's pages (Archive) keep
/api/backtest.

Sources (read-only, nothing is re-simulated):
  research/lab/backtest_live.json   the LIT live-loop replay (tools/export_backtest.py): trades with their reports, days
  data/NQ_5m.csv (+ data/NQ_1m.csv)  the LIT levels and session boxes of every day (engine/lit.py Market), the sweep bar of
                                     each trade, and, when the PC bot is not running LIT, the LIT state at the last bar
                                     (engine/lit_live.py run on the last ~2 months, the live loop's own window)
  engine.live.BOT.state             the PC paper bot's live LIT state when it runs LIT (levels, session boxes, setups)
Built once per file mtime (about 5 s), then cached.  period: "2026" (default, LIT is judged on 2026) | "all" (2021-26).
Paper only: this is a read of backtest files and bars.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import threading
from zoneinfo import ZoneInfo

import numpy as np

from . import analytics

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BT = os.path.join(ROOT, "research", "lab", "backtest_live.json")
D5 = os.path.join(ROOT, "data", "NQ_5m.csv")
D1 = os.path.join(ROOT, "data", "NQ_1m.csv")
ET = ZoneInfo("America/New_York")
PLAN = "builder_50k"
_lock = threading.Lock()
_cache: dict = {}

# the session boxes the dashboards draw (litkit.js DEF_BOXES): key, label, start / end ET minute, kind
BOXES = [("asia20", "Asia 20-00", 1200, 1440, "asia"), ("lon23", "Frankfurt 02-03", 120, 180, "london"),
         ("lon34", "London 03-04", 180, 240, "london"), ("pre", "Premarket", 240, 570, "pre"),
         ("ny89", "NY 08-09", 480, 540, "ny")]
LEVEL_NAMES = {"pdh": "PDH", "pdl": "PDL", "pwh": "PWH", "pwl": "PWL", "pmh": "PMH", "pml": "PML", "nwog": "NWOG", "ndog": "NDOG"}


def _mt(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def _read_bt():
    with open(BT, encoding="utf-8") as fh:
        return json.load(fh)


def _trade(t, i):
    """A backtest_live.json LIT trade in the engine trade's fields (page-chart tradeCard, journal, reports, stats)."""
    d = 1 if str(t.get("side", "")).upper().startswith("L") else -1
    qty = int(t.get("qty") or 0)
    rep = t.get("report") or {}
    return {
        "i": i, "day": t["day"], "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "dir": d, "side": t.get("side"),
        "entry": t["entry"], "stop": t["stop"], "stop0": t["stop"], "target": t["target"], "exit_price": t.get("exit_price"),
        "exit_reason": t.get("exit") or "", "pnl": float(t.get("pnl") or 0.0), "pnl_r": float(t.get("r") or 0.0),
        "qty": qty, "qty_label": f"{qty} MNQ", "risk_pts": t.get("risk_pts"), "risk_usd": t.get("risk_usd"),
        "rr": t.get("plan_rr"), "trigger": "LIT", "grade": "", "score": None, "checklist": None, "mtf_bias": None,
        "pools": t.get("pools") or [], "swept": t.get("swept") or [], "sweep_ext": t.get("sweep_ext"),
        "target_label": t.get("target_label") or "VIX band", "conf_tags": t.get("conf_tags") or [],
        "mfe": t.get("mfe"), "mae": None, "bars_held": t.get("bars_held") or 0, "comm": round(1.40 * qty, 2),
        "cisd_level": t.get("cisd_level"), "entry_kind": t.get("entry_kind"), "trigger_tf": t.get("trigger_tf"),
        "depth_atr": t.get("depth_atr"), "disp": t.get("disp"), "idm_n": t.get("idm_n"), "how": t.get("how"),
        "half": bool(t.get("half")), "weekly_stop": bool(t.get("weekly_stop")), "size_why": t.get("size_why") or [],
        "report": rep,
    }


def _days(raw_days, plan):
    """Daily rows with the simulated MFFU balance and end-of-day trailing MLL (locks at start + lock_above), as the engine."""
    bal = peak = float(plan["start"])
    mll = bal - plan["mll"]
    lock = plan["start"] + plan["lock_above"]
    out = []
    for d in raw_days:
        bal += float(d.get("pnl") or 0.0)
        peak = max(peak, bal)
        mll = min(max(mll, peak - plan["mll"]), lock)
        out.append({"date": d["date"], "pnl": round(float(d.get("pnl") or 0.0), 2), "trades": int(d.get("trades") or 0),
                    "low_intraday": round(float(d.get("low") or min(0.0, d.get("pnl") or 0.0)), 2),
                    "balance": round(bal, 2), "mll": round(mll, 2)})
    return out


def _epoch(date: str, mod: int) -> int:
    """ET wall time (trading date, minute of day) -> epoch; minutes >= 18:00 belong to the evening before the date."""
    d = dt.date.fromisoformat(date)
    if mod >= 1080:
        d -= dt.timedelta(days=1)
    return int(dt.datetime.combine(d, dt.time(mod // 60 % 24, mod % 60), ET).timestamp())


def _market(first_day: str):
    """engine/lit.py Market over the 5m bars from a month before first_day (the previous-month levels need them)."""
    from . import lit
    from .data import load
    b = load("NQ", "5m")
    t0 = _epoch(first_day, 0) - 40 * 86400
    i = int(np.searchsorted(b.t, t0))
    return lit.Market(bars=b.slice(i, len(b)))


def _level_label(nm: str, side: str) -> str:
    from .lit_live import _sweep_names
    if nm in ("bu_h", "bu_l"):
        return "EQH" if side == "high" else "EQL"
    if nm in LEVEL_NAMES:
        return LEVEL_NAMES[nm]
    return _sweep_names([nm])[0]


def _chart_layers(M, first_day: str, trades: list):
    """Per-day LIT levels (pools, with the time each was taken), session boxes and each trade's sweep bar."""
    from .lit_live import STRENGTH
    t, h, l = M.t, M.h, M.l
    pools, boxes = [], []
    k_of = {}
    for k, (d, s, e) in enumerate(M.days):
        d = str(d)
        k_of[d] = k
        if d < first_day:
            continue
        x = M.ctx[k]
        day_end = int(t[e - 1]) + 300
        seen = {}
        for side, px, ki, nm, cls in M.levels(k):
            px = round(float(px), 2)
            key = (side, px)
            st = STRENGTH.get(cls, 1)
            if key in seen and seen[key]["strength"] >= st:
                continue
            a = max(int(ki) + 1, s)
            if side == "high":
                hit = np.flatnonzero(h[a:e] >= px)
            else:
                hit = np.flatnonzero(l[a:e] <= px)
            t_known = int(t[max(int(ki), s - 1)]) if ki >= 0 else int(t[s])
            row = {"t0": t_known, "t1": int(t[a + hit[0]]) if len(hit) else None, "t2": day_end, "price": px,
                   "side": "H" if side == "high" else "L", "kind": cls, "strength": st, "eq": cls == "buildup",
                   "label": _level_label(nm, side)}
            seen[key] = row
        pools.extend(seen.values())
        mod = M.mod[s:e]
        for key, lab, a_m, z_m, kind in BOXES:
            if key not in x:
                continue
            hi, lo, last_i = x[key]
            ii = np.flatnonzero((mod >= a_m) & (mod < z_m)) if a_m < z_m else np.flatnonzero(mod >= a_m)
            ii = ii[mod[ii] >= 1080] if a_m >= 1080 else ii[mod[ii] < 1080]
            if not len(ii):
                continue
            boxes.append({"day": str(d), "key": key, "label": lab, "kind": kind, "t0": int(t[s + ii[0]]), "t1": int(t[s + ii[-1]]) + 300,
                          "hi": round(float(hi), 2), "lo": round(float(lo), 2)})
    # the sweep bar of each trade: the last bar of its day, before the entry, that reached the sweep extreme
    sweep_t = {}
    for tr in trades:
        k = k_of.get(tr["day"])
        ext = tr.get("sweep_ext")
        if k is None or ext is None:
            continue
        _d, s, e = M.days[k]
        z = int(np.searchsorted(t, tr["entry_t"], side="right"))
        z = min(max(z, s), e)
        seg = np.flatnonzero(h[s:z] >= ext - 0.25) if tr["dir"] == -1 else np.flatnonzero(l[s:z] <= ext + 0.25)
        if len(seg):
            sweep_t[tr["i"]] = int(t[s + seg[-1]])
    return pools, boxes, sweep_t


def _events(trades, sweep_t):
    ev = []
    for tr in trades:
        rep = tr.get("report") or {}
        side = "LONG" if tr["dir"] == 1 else "SHORT"
        st = sweep_t.get(tr["i"])
        if st:
            ev.append({"t": st, "type": "sweep", "dir": tr["dir"],
                       "text": f"Sweep of {', '.join(tr['pools']) or 'a LIT level'} (extreme {tr['sweep_ext']:,.2f})"})
        why = rep.get("why") or []
        ev.append({"t": tr["entry_t"] - 1, "type": "signal", "dir": tr["dir"],
                   "text": f"LIT {side} setup: " + ("; ".join(why[1:3]) if len(why) > 1 else ", ".join(tr["conf_tags"][:3]))})
        ev.append({"t": tr["entry_t"], "type": "entry", "dir": tr["dir"],
                   "text": f"{side} LIT @ {tr['entry']:,.2f} stop {tr['stop']:,.2f} target {tr['target']:,.2f} qty {tr['qty']} "
                           f"({tr.get('entry_kind') or 'entry'}, {tr['risk_pts']:.2f} pts, ${tr['risk_usd'] or 0:,.0f} at risk)"})
        ev.append({"t": tr["exit_t"], "type": "exit", "pnl": tr["pnl"],
                   "text": f"EXIT {tr['exit_reason']} {side} LIT | {tr['pnl_r']:+.2f}R | ${tr['pnl']:+,.0f}"
                           + (f" - {rep['lessons'][0]}" if rep.get("lessons") else "")})
    ev.sort(key=lambda e: (e["t"], e["type"]))
    return ev


def _bars_state():
    """The LIT state at the last bar of the data files (engine/lit_live.py on the live loop's window) when no bot runs LIT."""
    import pandas as pd
    from . import lit_live
    from .data import load
    lm = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))
    P = lm.get("lit") or {}
    b5 = load("NQ", "5m")                              # cached by engine.data (the server has it loaded already)
    i = int(np.searchsorted(b5.t, int(b5.t[-1]) - 75 * 86400))
    df5 = pd.DataFrame({"time": b5.t[i:], "open": b5.o[i:], "high": b5.h[i:], "low": b5.l[i:], "close": b5.c[i:], "volume": b5.v[i:]})
    one = None
    if P.get("tf") == "1m" and os.path.exists(D1):
        try:
            b1 = load("NQ", "1m")
            one = b1.slice(int(np.searchsorted(b1.t, int(df5["time"].min()))), len(b1))
        except Exception:
            one = None
    r = lit_live.run(df5, P, one_min=one)
    st = r["state"]
    st["source"] = "bars"
    st["lit"]["today"] = str(st["lit"].get("today"))
    return st


def _build(period: str):
    raw = _read_bt()
    plan = analytics.PLANS[PLAN]
    first = "2026-01-01" if period == "2026" else "0000"
    rows = [t for t in raw.get("trades") or [] if t["day"] >= first]
    trades = [_trade(t, i) for i, t in enumerate(rows)]
    days = _days([d for d in raw.get("days") or [] if d["date"] >= first], plan)
    chart_from = max(first, "2026-01-01")             # levels / boxes: 2026 (LIT's period; 1m data), even for "all"
    try:
        M = _market(days[0]["date"] if period == "2026" and days else chart_from)
        pools, boxes, sweep_t = _chart_layers(M, chart_from, trades)
        err = None
    except Exception as e:                            # bars missing: the trades and numbers still load
        pools, boxes, sweep_t, err = [], [], {}, f"{e.__class__.__name__}: {e}"
    ifvgs = []
    for tr in trades:                                 # the 5m CISD level each trade came from (chart layer 'Triggers')
        cl = tr.get("cisd_level")
        if cl is None or tr["i"] not in sweep_t:
            continue
        lo, hi = sorted([float(cl), float(tr["entry"])])
        if hi - lo < 1.0:
            hi, lo = hi + 0.5, lo - 0.5
        ifvgs.append({"t0": sweep_t[tr["i"]], "t1": tr["entry_t"], "top": hi, "bottom": lo, "dir": tr["dir"], "type": "CISD"})
    meta = raw.get("meta") or {}
    st = analytics.stats([{**t, "mae": 0.0, "mfe": t["mfe"] or 0.0} for t in trades], days)
    st["avg_mae"] = None                              # LIT trades carry MFE only
    pnls = [d["pnl"] for d in days]
    lows = [d["low_intraday"] for d in days]
    out = {
        "model": "lit", "sym": "NQ", "tf": "5m", "period": period,
        "strategy": meta.get("strategy"), "built": meta.get("built"),
        "params": {**(meta.get("params") or {}), "risk_usd": 800, "risk_ref_stop": 20, "max_micros": 40, "max_trades_day": 1,
                   "start_balance": plan["start"]},
        "stats": st, "trades": trades, "days": days, "exit_signals": [], "account_resets": [],
        "breakdowns": {}, "equity": analytics.equity_curve(trades, plan["start"]),
        "eval": analytics.simulate_eval(pnls, plan, lows), "rolling": analytics.rolling_evals(days, plan),
        "events": _events(trades, sweep_t), "signals": [], "pools": pools, "boxes": boxes, "ifvgs": ifvgs,
        "profiles": {}, "structure": [], "htf_fvgs": [], "mtf_events": [], "learner_log": [], "shadows": [],
        "plan": plan, "range": [days[0]["date"], days[-1]["date"]] if days else ["", ""],
        "periods": raw.get("periods") or {}, "months": raw.get("months") or {}, "chart_error": err,
        "sizing": meta.get("sizing"), "loss_rules": meta.get("loss_rules"), "rules": meta.get("rules"),
    }
    out["rolling"].pop("runs", None)
    return out


def _live_state():
    try:
        from .live import BOT
        st = BOT.state
        if st and st.get("model") == "lit":
            return {**st, "source": "bot"}
    except Exception:
        pass
    return None


def backtest(period: str = "2026") -> dict:
    period = "all" if period == "all" else "2026"
    key = (period, _mt(BT), _mt(D5))
    with _lock:
        hit = _cache.get(("bt", period))
        if hit and hit[0] == key:
            res = hit[1]
        else:
            res = None
    if res is None:
        res = _build(period)
        with _lock:
            _cache[("bt", period)] = (key, res)
    st = _live_state()
    if st is None:
        skey = (_mt(D5), _mt(D1))
        with _lock:
            hit = _cache.get("state")
        if hit and hit[0] == skey:
            st = hit[1]
        else:
            try:
                st = _bars_state()
            except Exception as e:
                st = {"model": "lit", "source": "none", "model_state": f"LIT state unavailable ({e.__class__.__name__}: {e})",
                      "active_pools": [], "session": {}, "setups": {}, "position": None, "price": None, "t": None, "lit": {}}
            with _lock:
                _cache["state"] = (skey, st)
    return {**res, "state": st}
