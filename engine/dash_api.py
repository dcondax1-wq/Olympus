"""/api/dash/* routes (contract: research/DASHBOARD_API.md). Mounted by server.py in the DASH EXTRAS block:

    from engine import dash_api as _dash
    _dash.bind(watchdog=WATCHDOG, live_arm=_live_arm)
    app.include_router(_dash.router)
    app.router.add_event_handler("startup", _dash.startup)

Every route is a read-only GET. Heavy work (backtests, five-year windows, data coverage, Yahoo ES) runs in a
below-normal-priority subprocess (engine/dash_data.py); routes only read cached JSON and the live bot's memory.
"""
from __future__ import annotations

import asyncio
import json
import math
import threading
import time

from fastapi import APIRouter, Request
from fastapi.responses import Response, StreamingResponse

from . import dash_data as D
from . import dash_market as MK
from . import dash_metrics as M
from . import dash_system as SY

router = APIRouter()
LAUNCH_DAY = "2026-10-18"


def bind(**kw):
    SY.bind(**kw)


def _clean(o):
    """numpy -> Python, NaN/inf -> null (browsers reject NaN in JSON)."""
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if hasattr(o, "item") and not isinstance(o, (str, bytes)):
        try:
            return _clean(o.item())
        except Exception:
            pass
    if hasattr(o, "tolist"):
        return _clean(o.tolist())
    return o


def J(obj, status=200):
    body = {"ok": status < 400, **obj, "as_of": int(time.time())}
    body.setdefault("status", "ok" if status < 400 else "error")
    return Response(json.dumps(_clean(body), separators=(",", ":"), default=str, allow_nan=False),
                    media_type="application/json", status_code=status, headers={"Cache-Control": "no-store"})


def _err(e, status=400):
    return J({"error": f"{e.__class__.__name__}: {e}" if not isinstance(e, str) else e}, status)


def guarded(fn):
    """Route body wrapper: any exception -> 400/500 JSON instead of a stack-trace page."""
    import functools

    @functools.wraps(fn)
    def inner(*a, **k):
        try:
            return fn(*a, **k)
        except ValueError as e:
            return _err(e, 400)
        except Exception as e:
            return _err(e, 500)
    return inner


def _ds(source, days_from, days_to):
    """-> (data | None, meta, early_response | None)."""
    data, meta = D.dataset(source, days_from or None, days_to or None)
    if data is None:
        return None, meta, J({"status": meta["status"], "meta": meta, "message": meta.get("message"),
                              "retry_after_s": meta.get("retry_after_s"), "job": meta.get("job")})
    return data, meta, None


def _plan():
    from .analytics import PLANS
    return PLANS["builder_50k"]


# ------------------------------------------------------------------ index
ENDPOINTS = [
    ("/api/dash/index", "", "this list"),
    ("/api/dash/overview", "", "home screen in one call"),
    ("/api/dash/eval", "since, balance, peak_eod, today_pnl", "MFFU 50K eval tracker"),
    ("/api/dash/montecarlo", "source, days_from, days_to, n, horizon, from_state (+ eval overrides)", "eval pass probability"),
    ("/api/dash/equity", "source, days_from, days_to, start", "equity curve + drawdown"),
    ("/api/dash/calendar", "source, days_from, days_to", "daily P&L heatmap"),
    ("/api/dash/heatmap", "source, days_from, days_to, metric", "hour x weekday"),
    ("/api/dash/rdist", "source, days_from, days_to, bin", "R-multiple histogram"),
    ("/api/dash/streaks", "source, days_from, days_to", "win/loss streaks"),
    ("/api/dash/maemfe", "source, days_from, days_to", "MAE/MFE scatter"),
    ("/api/dash/breakdown", "source, days_from, days_to, by", "performance by dimension"),
    ("/api/dash/frequency", "source, days_from, days_to", "trades/week vs the 2-4 band"),
    ("/api/dash/history", "by", "five-year per year / quarter / month"),
    ("/api/dash/regime", "", "volatility / regime gauges"),
    ("/api/dash/liquidity", "max", "liquidity map"),
    ("/api/dash/sessions", "", "today's session ranges"),
    ("/api/dash/intermarket", "days", "NQ vs ES"),
    ("/api/dash/news", "days, impact", "news + blackout timeline"),
    ("/api/dash/feed", "since, types, limit", "bot event log"),
    ("/api/dash/stream", "since", "SSE: log + tick"),
    ("/api/dash/drift", "", "paper vs backtest"),
    ("/api/dash/memory", "", "memory insights"),
    ("/api/dash/confluence", "status, sort", "confluence leaderboard"),
    ("/api/dash/health", "", "system health"),
    ("/api/dash/coverage", "", "data coverage"),
    ("/api/dash/replay", "entry_t, source, before, after, tf", "bars around a trade"),
    ("/api/dash/launch", "", "launch checklist"),
    ("/api/dash/clock", "", "killzones + countdowns"),
    ("/api/dash/ticker", "n", "price ticker + sparkline"),
    ("/api/dash/model", "", "model state, setups, position"),
    ("/api/dash/bias", "", "MTF bias, structure, profile"),
    ("/api/dash/rolling", "source, days_from, days_to, window", "rolling edge"),
    ("/api/dash/exits", "source, days_from, days_to", "exit reasons + signals"),
    ("/api/dash/trades", "source, days_from, days_to, limit, offset, sort, order, dir, grade, exit, win", "trade table"),
    ("/api/dash/jobs", "refresh", "background jobs"),
    ("/api/dash/prep", "", "session prep card"),
]


PLANNED: set = set()                 # paths listed in the contract but not deployed yet (the UI only calls "live" ones)


@router.get("/api/dash/index")
def dash_index():
    deployed = {getattr(r, "path", None) for r in router.routes}
    rows = [{"path": p, "status": "live" if p in deployed and p not in PLANNED else "planned",
             "params": [x.strip() for x in q.split(",") if x.strip()], "desc": d} for p, q, d in ENDPOINTS]
    return J({"endpoints": rows, "live": sum(1 for r in rows if r["status"] == "live"), "planned": sum(1 for r in rows if r["status"] == "planned"),
              "contract": "research/DASHBOARD_API.md"})


# ------------------------------------------------------------------ dataset analytics
@router.get("/api/dash/equity")
@guarded
def dash_equity(source: str = "backtest", days_from: str = "", days_to: str = "", start: float = 50000.0):
    data, meta, early = _ds(source, days_from, days_to)
    return early or J({"meta": meta, **M.equity(data["trades"], data["days"], start)})


@router.get("/api/dash/calendar")
@guarded
def dash_calendar(source: str = "backtest", days_from: str = "", days_to: str = ""):
    data, meta, early = _ds(source, days_from, days_to)
    return early or J({"meta": meta, **M.calendar(data["trades"], data["days"])})


@router.get("/api/dash/heatmap")
@guarded
def dash_heatmap(source: str = "backtest", days_from: str = "", days_to: str = "", metric: str = "avg_r"):
    if metric not in ("avg_r", "pnl", "wr", "n"):
        raise ValueError("metric must be avg_r, pnl, wr or n")
    data, meta, early = _ds(source, days_from, days_to)
    return early or J({"meta": meta, **M.heatmap(data["trades"], metric)})


@router.get("/api/dash/rdist")
@guarded
def dash_rdist(source: str = "backtest", days_from: str = "", days_to: str = "", bin: float = 0.25):
    data, meta, early = _ds(source, days_from, days_to)
    return early or J({"meta": meta, **M.rdist(data["trades"], max(0.05, min(float(bin), 2.0)))})


@router.get("/api/dash/streaks")
@guarded
def dash_streaks(source: str = "backtest", days_from: str = "", days_to: str = ""):
    data, meta, early = _ds(source, days_from, days_to)
    return early or J({"meta": meta, **M.streaks(data["trades"], data["days"])})


@router.get("/api/dash/maemfe")
@guarded
def dash_maemfe(source: str = "backtest", days_from: str = "", days_to: str = ""):
    data, meta, early = _ds(source, days_from, days_to)
    return early or J({"meta": meta, **M.maemfe(data["trades"])})


@router.get("/api/dash/breakdown")
@guarded
def dash_breakdown(source: str = "backtest", days_from: str = "", days_to: str = "", by: str = ""):
    data, meta, early = _ds(source, days_from, days_to)
    dims = [x.strip() for x in by.split(",") if x.strip()] or None
    return early or J({"meta": meta, "groups": M.breakdown(data["trades"], dims), "dims": list(M.DIMS)})


@router.get("/api/dash/frequency")
@guarded
def dash_frequency(source: str = "backtest", days_from: str = "", days_to: str = ""):
    data, meta, early = _ds(source, days_from, days_to)
    if early:
        return early
    cw = M.iso_week(D.today_session())
    out = M.frequency(data["trades"], data["days"], current_week=cw)
    paper = D.paper_dataset()
    out["this_week"] = {"key": cw, "paper": sum(1 for t in paper["trades"] if M.iso_week(t["day"]) == cw),
                        source: sum(1 for t in data["trades"] if M.iso_week(t["day"]) == cw)}
    return J({"meta": meta, **out})


@router.get("/api/dash/history")
@guarded
def dash_history(by: str = "quarter"):
    if by not in ("year", "quarter", "month"):
        raise ValueError("by must be year, quarter or month")
    data, meta, early = _ds("5y", None, None)
    return early or J({"meta": meta, **M.periods(data["trades"], data["days"], by)})


@router.get("/api/dash/rolling")
@guarded
def dash_rolling(source: str = "backtest", days_from: str = "", days_to: str = "", window: int = 20):
    data, meta, early = _ds(source, days_from, days_to)
    return early or J({"meta": meta, **M.rolling(data["trades"], max(5, min(int(window), 200)))})


@router.get("/api/dash/exits")
@guarded
def dash_exits(source: str = "backtest", days_from: str = "", days_to: str = ""):
    data, meta, early = _ds(source, days_from, days_to)
    return early or J({"meta": meta, **M.exits(data["trades"], data.get("exit_signals"))})


@router.get("/api/dash/trades")
@guarded
def dash_trades(source: str = "backtest", days_from: str = "", days_to: str = "", limit: int = 50, offset: int = 0,
                sort: str = "entry_t", order: str = "desc", dir: int = 0, grade: str = "", exit: str = "", win: int = -1):
    data, meta, early = _ds(source, days_from, days_to)
    if early:
        return early
    ts = data["trades"]
    if dir in (1, -1):
        ts = [t for t in ts if t.get("dir") == dir]
    if grade:
        g = {x.strip() for x in grade.split(",")}
        ts = [t for t in ts if t.get("grade") in g]
    if exit:
        ts = [t for t in ts if exit.lower() in str(t.get("exit_reason") or "").lower()]
    if win in (0, 1):
        ts = [t for t in ts if (float(t.get("pnl") or 0) > 0) == bool(win)]
    if sort not in ("entry_t", "r", "pnl", "mfe", "mae"):
        raise ValueError("sort must be entry_t, r, pnl, mfe or mae")
    ts = sorted(ts, key=lambda t: (t.get(sort) is None, t.get(sort) or 0), reverse=order != "asc")
    lim, off = max(1, min(int(limit), 1000)), max(0, int(offset))
    page = [{**t, "killzone": M.killzone(t), "pool_family": M.pool_family(t)} for t in ts[off:off + lim]]
    return J({"meta": meta, "total": len(ts), "offset": off, "limit": lim, "trades": page})


# ------------------------------------------------------------------ eval tracker + Monte Carlo
def _eval(since=LAUNCH_DAY, balance=None, peak_eod=None, today_pnl=None):
    plan = _plan()
    from .model import DEFAULTS
    paper = D.paper_dataset(since=since or LAUNCH_DAY)
    st = M.eval_state(paper["days"], plan, balance, peak_eod)
    bot = SY._bot()
    tp = float(today_pnl) if today_pnl is not None else (bot.day_pnl_routed() if bot.cfg else 0.0)
    target = plan["start"] + plan["target"]
    cushion = st["balance"] - st["mll"]
    internal = float(DEFAULTS.get("daily_max_loss") or 600)
    out = {"plan": {"name": plan["name"], "start": plan["start"], "target": plan["target"], "mll": plan["mll"], "dll": plan.get("dll"),
                    "lock_at": st["lock"], "internal_daily_stop": internal, "max_minis": plan.get("max_minis"),
                    "eval_consistency": plan.get("eval_consistency")},
           "state": {"source": "override" if balance is not None else "paper", "since": since or LAUNCH_DAY, "balance": round(st["balance"], 2),
                     "profit": round(st["balance"] - plan["start"], 2), "peak_eod": round(st["peak_eod"], 2),
                     "trading_days": sum(1 for d in paper["days"] if d["trades"]), "sessions": len(paper["days"]), "trades": len(paper["trades"])},
           "target": {"level": target, "remaining": round(max(0.0, target - st["balance"]), 2),
                      "pct": round(min(100.0, max(0.0, (st["balance"] - plan["start"]) / plan["target"] * 100)), 1)},
           "mll": {"level": round(st["mll"], 2), "cushion": round(cushion, 2), "pct_cushion_left": round(cushion / plan["mll"] * 100, 1),
                   "locked": st["locked"], "lock_needs": round(max(0.0, st["lock"] + plan["mll"] - st["peak_eod"]), 2),
                   "note": "EOD trailing: trails the best end-of-day balance by $2,000, locks at $50,100"},
           "dll": {"soft_limit": plan.get("dll"), "today_pnl": round(tp, 2), "used": round(max(0.0, -tp), 2),
                   "pct_used": round(max(0.0, -tp) / plan["dll"] * 100, 1) if plan.get("dll") else None,
                   "internal_stop": internal, "internal_left": round(internal + min(0.0, tp), 2)},
           "days": st["days"]}
    if paper["from"] is None and balance is None:
        out["message"] = f"No paper trades since {since or LAUNCH_DAY}: the account sits at its starting balance."
    return out, st


@router.get("/api/dash/eval")
@guarded
def dash_eval(since: str = LAUNCH_DAY, balance: float | None = None, peak_eod: float | None = None, today_pnl: float | None = None):
    out, st = _eval(since, balance, peak_eod, today_pnl)
    data, meta = D.dataset("backtest")
    proj = {"basis": None}
    if data and data["days"]:
        avg = sum(d["pnl"] for d in data["days"]) / len(data["days"])
        rem = out["target"]["remaining"]
        mc = M.mc_eval(data["days"], _plan(), 2000, 60, st["balance"], st["peak_eod"])
        proj = {"avg_day_pnl": round(avg, 2), "days_to_pass_linear": round(rem / avg, 1) if avg > 0 and rem > 0 else (0 if rem <= 0 else None),
                "mc_median_days": mc["days_to_pass"]["median"] if mc else None, "mc_pass_prob": mc["pass_prob"] if mc else None,
                "mc_fail_prob": mc["fail_prob"] if mc else None, "mc_horizon": 60,
                "basis": f"backtest {meta.get('from')}..{meta.get('to')} ({meta.get('sessions')} sessions)", "stale": meta.get("stale")}
    else:
        proj["message"] = meta.get("message")
    return J({**out, "projection": proj})


@router.get("/api/dash/montecarlo")
@guarded
def dash_mc(source: str = "backtest", days_from: str = "", days_to: str = "", n: int = 3000, horizon: int = 60, from_state: int = 0,
            since: str = LAUNCH_DAY, balance: float | None = None, peak_eod: float | None = None, seed: int = 7):
    data, meta, early = _ds(source, days_from, days_to)
    if early:
        return early
    n, horizon = max(100, min(int(n), 20000)), max(5, min(int(horizon), 250))
    sb = pe = None
    if from_state:
        _, st = _eval(since, balance, peak_eod)
        sb, pe = st["balance"], st["peak_eod"]
    mc = M.mc_eval(data["days"], _plan(), n, horizon, sb, pe, seed=seed)
    if mc is None:
        return J({"status": "no_data", "meta": meta, "message": "no sessions to bootstrap"})
    return J({"meta": meta, **mc})


# ------------------------------------------------------------------ market side
@router.get("/api/dash/ticker")
@guarded
def dash_ticker(n: int = 78):
    return J(MK.ticker(max(10, min(int(n), 600))))


@router.get("/api/dash/clock")
@guarded
def dash_clock():
    return J(MK.clock())


@router.get("/api/dash/regime")
@guarded
def dash_regime():
    return J(MK.ttl(("regime", int(time.time() // 30)), 30, MK.regime))


@router.get("/api/dash/liquidity")
@guarded
def dash_liquidity(max: int = 30):
    return J(MK.liquidity(int(max)))


@router.get("/api/dash/sessions")
@guarded
def dash_sessions():
    return J(MK.ttl(("sessions", int(time.time() // 20)), 20, MK.sessions))


@router.get("/api/dash/intermarket")
@guarded
def dash_intermarket(days: int = 60):
    d = max(10, min(int(days), 500))
    return J(MK.ttl(("im", d, int(time.time() // 30)), 30, lambda: MK.intermarket(d)))


@router.get("/api/dash/news")
@guarded
def dash_news(days: int = 7, impact: str = "medium"):
    if impact not in ("low", "medium", "high"):
        raise ValueError("impact must be low, medium or high")
    return J(MK.news(int(days), impact))


@router.get("/api/dash/model")
@guarded
def dash_model():
    return J(MK.model())


@router.get("/api/dash/bias")
@guarded
def dash_bias():
    return J(MK.bias())


@router.get("/api/dash/prep")
@guarded
def dash_prep():
    return J(MK.ttl(("prep", int(time.time() // 60)), 60, MK.prep))


# ------------------------------------------------------------------ system side
@router.get("/api/dash/health")
@guarded
def dash_health():
    return J(SY.health())


@router.get("/api/dash/coverage")
@guarded
def dash_coverage():
    return J(SY.coverage())


@router.get("/api/dash/feed")
@guarded
def dash_feed(since: int = 0, types: str = "", limit: int = 100):
    return J(SY.feed(int(since), types, max(1, min(int(limit), 400))))


@router.get("/api/dash/drift")
@guarded
def dash_drift():
    return J(SY.drift())


@router.get("/api/dash/memory")
@guarded
def dash_memory():
    return J(SY.memory_insights())


@router.get("/api/dash/confluence")
@guarded
def dash_confluence(status: str = "", sort: str = "lift"):
    return J(SY.confluence(status, sort))


@router.get("/api/dash/launch")
@guarded
def dash_launch():
    return J(MK.ttl(("launch", int(time.time() // 15)), 15, SY.launch))


@router.get("/api/dash/jobs")
@guarded
def dash_jobs(refresh: int = 0):
    queued = []
    if refresh:
        for spec in (D.backtest_spec(), {"kind": "5y", "sym": "NQ"}, SY.coverage_spec()):
            if D.JOBS_MGR.submit(spec, force=True):
                queued.append(D.spec_key(spec))
    files = []
    import os
    if os.path.isdir(D.CACHE):
        for f in sorted(os.listdir(D.CACHE)):
            if f.endswith(".json"):
                o = D.read_cache(f[:-5]) or {}
                files.append({"key": f[:-5], "computed_at": o.get("computed_at"), "secs": o.get("secs"), "version": o.get("version"),
                              "size_kb": round(os.path.getsize(os.path.join(D.CACHE, f)) / 1024, 1)})
    return J({"jobs": D.JOBS_MGR.all(), "cache": files, "queued": queued, "model_version": D.code_version()})


# ------------------------------------------------------------------ trade replay
@router.get("/api/dash/replay")
@guarded
def dash_replay(entry_t: int, source: str = "backtest", days_from: str = "", days_to: str = "", before: int = 36, after: int = 24, tf: str = "5m"):
    if source == "backtest" and not days_from and not days_to:
        data, meta = D.dataset("backtest")
        if data is not None and not any(abs(t["entry_t"] - entry_t) <= 600 for t in data["trades"]):
            data, meta = D.dataset("5y")                    # older trade: look in the five-year set too
    else:
        data, meta = D.dataset(source, days_from or None, days_to or None)
    if data is None:
        return J({"status": meta["status"], "meta": meta, "message": meta.get("message"), "retry_after_s": meta.get("retry_after_s")})
    cand = [t for t in data["trades"] if abs(t["entry_t"] - int(entry_t)) <= 600]
    if not cand:
        return J({"status": "no_data", "meta": meta, "message": f"no trade with entry_t {entry_t} in {meta['source']}"})
    tr = min(cand, key=lambda t: abs(t["entry_t"] - int(entry_t)))
    if tf not in ("5m", "1m"):
        raise ValueError("tf must be 5m or 1m")
    secs = 300 if tf == "5m" else 60
    a = tr["entry_t"] - int(before) * secs
    z = (tr.get("exit_t") or tr["entry_t"]) + int(after) * secs
    rec = MK.bars("NQ") if tf == "5m" else None
    if rec is not None and len(rec) and a >= int(rec["time"].iloc[0]):
        seg = rec[(rec["time"] >= a) & (rec["time"] <= z)]
        bars = {"t": seg["time"].astype(int).tolist(), "o": seg["open"].tolist(), "h": seg["high"].tolist(), "l": seg["low"].tolist(),
                "c": seg["close"].tolist(), "v": seg["volume"].tolist()}
    else:
        from .data import load
        try:
            b = load("NQ", tf)
        except OSError:
            raise ValueError(f"no NQ {tf} history on disk")
        i0, i1 = int((b.t < a).sum()), int((b.t <= z).sum())
        bars = {"t": b.t[i0:i1].tolist(), "o": b.o[i0:i1].tolist(), "h": b.h[i0:i1].tolist(), "l": b.l[i0:i1].tolist(),
                "c": b.c[i0:i1].tolist(), "v": b.v[i0:i1].tolist()}
    marks = [{"t": tr["entry_t"], "price": tr.get("entry"), "kind": "entry", "dir": tr.get("dir")}]
    if tr.get("signal_t"):
        marks.insert(0, {"t": tr["signal_t"], "price": None, "kind": "signal"})
    if tr.get("exit_t"):
        marks.append({"t": tr["exit_t"], "price": tr.get("exit_price"), "kind": "exit", "reason": tr.get("exit_reason")})
    lines = [{"price": tr.get("stop0"), "kind": "stop"}, {"price": tr.get("target"), "kind": "target", "label": tr.get("target_label")}]
    if tr.get("sweep_ext") is not None:
        lines.append({"price": tr["sweep_ext"], "kind": "sweep_extreme"})
    return J({"meta": meta, "trade": tr, "bars": {"tf": tf, **bars}, "markers": marks, "lines": [x for x in lines if x["price"] is not None],
              **({"note": "no bars in that range for this timeframe"} if not bars["t"] else {})})


# ------------------------------------------------------------------ overview
@router.get("/api/dash/overview")
@guarded
def dash_overview():
    bot = SY._bot()
    st = bot.state or {}
    h = bot.health or {}
    now = int(time.time())
    out = {"bot": {"running": bool(bot.running), "adapter": (bot.cfg or {}).get("adapter"),
                   "armed_live": bool((SY.BOUND.get("live_arm") or {}).get("armed")), "kill": bool(bot.kill),
                   "model_state": st.get("model_state"), "position": st.get("position") and {k: st["position"].get(k) for k in
                                                                                             ("dir", "entry", "stop", "target", "qty", "entry_t", "grade")},
                   "last_poll": bot.last_poll, "poll_ms": h.get("poll_ms"), "errors": bot.errors, "started_at": bot.started_at}}
    try:
        tk = MK.ticker(78)
        out["price"] = {k: tk.get(k) for k in ("last", "t", "chg", "chg_pct", "day_high", "day_low", "prev_close", "session")}
    except Exception as e:
        out["price"] = {"error": str(e)[:200]}
    out["today"] = {"date": D.today_session(), "pnl_routed": bot.day_pnl_routed() if bot.cfg else 0.0,
                    "trades": bot.trades_today() if bot.cfg else 0, "engine_day_pnl": st.get("day_pnl"), "engine_day_trades": st.get("day_trades")}
    cw = M.iso_week(D.today_session())
    paper = D.paper_dataset()
    wk_n = sum(1 for t in paper["trades"] if M.iso_week(t["day"]) == cw)
    data, meta = D.dataset("backtest")
    btw = None
    if data:
        btw = M.frequency(data["trades"], data["days"])["summary"]["tpw_overall"]
    lo, hi = M.BAND
    out["week"] = {"key": cw, "trades": wk_n, "target_min": lo, "target_max": hi,
                   "status": "in" if lo <= wk_n <= hi else ("below" if wk_n < lo else "above"), "backtest_tpw": btw,
                   "message": f"{wk_n} paper trade{'s' if wk_n != 1 else ''} this week (target {lo}-{hi})"}
    try:
        ev, _ = _eval()
        out["eval"] = {"balance": ev["state"]["balance"], "profit": ev["state"]["profit"], "target": ev["plan"]["target"],
                       "pct_to_target": ev["target"]["pct"], "mll": ev["mll"]["level"], "cushion": ev["mll"]["cushion"],
                       "dll_used": ev["dll"]["used"], "source": ev["state"]["source"], "trades": ev["state"]["trades"]}
    except Exception as e:
        out["eval"] = {"error": str(e)[:200]}
    try:
        ck = MK.clock(now)
        out["next_killzone"] = ck["next_entry_window"]
        out["market"] = {"open": ck["market_open"], "next_open_t": ck["next_open_t"], "next_close_t": ck["next_close_t"], "now_et": ck["now_et"]}
    except Exception as e:
        out["next_killzone"] = {"error": str(e)[:200]}
    try:
        nw = MK.news(14, "medium", now)
        out["next_blackout"] = nw["next_blackout"]
        out["next_event"] = nw["next_event"]
        out["in_blackout"] = nw["in_blackout"]
    except Exception as e:
        out["next_blackout"] = {"error": str(e)[:200]}
    out["data"] = {"age_s": h.get("data_age_s"), "stale": h.get("stale"), "market_open": h.get("market_open"), "source": h.get("data_source"),
                   "last_bar_t": h.get("last_bar_t")}
    wd = SY.BOUND.get("watchdog")
    try:
        ws = wd.status() if wd else {}
    except Exception:
        ws = {}
    issues = list(ws.get("issues") or []) + ([] if bot.running else ["bot not running"])
    out["health"] = {"ok": not issues, "issues": issues, "watchdog_ok": ws.get("ok"), "keepawake": (ws.get("keepawake") or {}).get("held")}
    lt = int(SY.LAUNCH.timestamp())
    out["launch"] = {"t": lt, "in_s": lt - now, "label": "Sun 2026-10-18 18:00 ET", "launched": now >= lt}
    out["datasets"] = {"backtest": meta.get("status"), "backtest_stale": meta.get("stale")}
    return J(out)


# ------------------------------------------------------------------ SSE stream
@router.get("/api/dash/stream")
async def dash_stream(request: Request, since: int = 0):
    bot = SY._bot()

    async def gen():
        seen = set()
        backlog = [e for e in reversed(list(bot.log)) if e.get("t", 0) > since] if since else []
        for e in list(bot.log):
            seen.add(id(e))
        yield "retry: 3000\n\n"
        for e in backlog[-100:]:
            yield f"event: log\ndata: {json.dumps(_clean({k: v for k, v in e.items() if k != 'result'}))}\n\n"
        last_tick = 0.0
        while True:
            if await request.is_disconnected():
                break
            cur = list(bot.log)
            fresh = [e for e in cur if id(e) not in seen]
            for e in reversed(fresh):
                yield f"event: log\ndata: {json.dumps(_clean({k: v for k, v in e.items() if k != 'result'}))}\n\n"
            seen = {id(e) for e in cur}
            if time.time() - last_tick >= 5:
                last_tick = time.time()
                st = bot.state or {}
                h = bot.health or {}
                tick = {"t": int(time.time()), "price": st.get("price"), "bar_t": st.get("t"), "model_state": st.get("model_state"),
                        "running": bool(bot.running), "data_age_s": h.get("data_age_s"), "last_poll": bot.last_poll,
                        "day_pnl_routed": bot.day_pnl_routed() if bot.cfg else 0.0,
                        "position": st.get("position") and {k: st["position"].get(k) for k in ("dir", "entry", "stop", "target", "qty", "entry_t")}}
                yield f"event: tick\ndata: {json.dumps(_clean(tick))}\n\n"
            await asyncio.sleep(1.0)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no", "Connection": "keep-alive"})


# ------------------------------------------------------------------ start-up warm-up
def startup():
    def work():
        time.sleep(45)                   # let the bot resume and finish its first poll first
        try:
            D.warm()
            SY.coverage()
            SY.task_installed()
        except Exception as e:
            print(f"[dash] warm-up error: {e}", flush=True)
    threading.Thread(target=work, name="dash-warm", daemon=True).start()
