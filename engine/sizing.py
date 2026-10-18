"""Live-loop sizing: one multiplier on top of the engine's micros, applied in exactly the same way by the PC bot
(engine/live.py), the cloud monitor (tools/cloud_monitor.py), the dashboard's replay (tools/export_backtest.py) and the
research library (tools/runlib.py). Research 2026-10-17: research/writeups/risk-summary.md.

Config, live_model.json:
  "equity_filter": {"lookback": 15, "min_sum_r": 0.0, "cold_mode": "half", "cold_size": 0.25}   cold streak -> x cold_size
  "sizing": {"late_mult": 0.5,                 late entry (15m trend already points the trade's way) -> x late_mult
             "press": {"floor": -1000, "ref": 60} | null}
                                               fast-eval mode: while the eval's profit is >= floor ($), size as if the
                                               wide-stop reference were `ref` pts ($800 on any stop up to 60) instead of
                                               params.risk_ref_stop; off when null (default)
The engine's micros already carry the $ risk and the wide-stop scaling. The multipliers are combined, rounded down
ONCE, floor 1 micro, cap max_micros. cold 0 (skip mode) means no trade.

LIT (live_model.json "lit_sizing": {"mode": "normal" | "eval" | "fast_eval" | "safe_eval" | "two_week"}, default normal):
lit_qty() below, used by the PC bot and the cloud monitor's paper ledger; mffu_eval() is the eval room for safe_eval / eval;
two_week_qty() + eval_state() + eval_session() are the two-week eval mode (owner order 2026-10-18: pass within 10 sessions;
research/writeups/lit-two-week-eval.md, run lit_2wk_rec = config C); eval_clock() is the 10-session reset reminder.
"""
from __future__ import annotations

import datetime as _dt
import logging
import math

log = logging.getLogger(__name__)

DEFAULT = {"late_mult": None, "press": None}


def is_late(trade: dict) -> bool:
    """15m structure already turned the trade's way at entry (the -1 item of the confluence score)."""
    try:
        return (float(trade.get("m15_trend") or 0) * float(trade.get("dir") or 0)) > 0
    except (TypeError, ValueError):
        return False


def engine_micros(risk_usd: float, risk_pts: float, ref_stop: float, max_micros: int = 40, pv: float = 2.0) -> int:
    """The engine's own rule (model.py): risk_usd up to ref_stop pts, then risk_usd x ref / stop; micros rounded down."""
    if risk_pts <= 0:
        return 0
    usd = risk_usd * (min(1.0, ref_stop / risk_pts) if ref_stop else 1.0)
    return int(min(max_micros, usd // (risk_pts * pv)))


def route_qty(qty: int, trade: dict, cold_mult: float, sizing: dict | None = None, params: dict | None = None,
              eval_profit: float | None = None) -> dict:
    """{"qty", "mult", "reasons": [...]} for one entry.
    qty: the engine's micros. trade: dict with dir, m15_trend, risk_pts (or entry+stop). cold_mult: equity_filter mult.
    eval_profit: the eval account's profit vs its start ($) at entry, None = unknown (press off)."""
    sz = {**DEFAULT, **(sizing or {})}
    p = params or {}
    reasons = []
    if qty <= 0 or cold_mult <= 0:
        return {"qty": 0, "mult": 0.0, "reasons": ["cold streak: paper only"] if cold_mult <= 0 else ["no size"]}
    base = int(qty)
    press = sz.get("press")
    if press and eval_profit is not None and eval_profit >= float(press.get("floor", -1000)):
        risk = trade.get("risk_pts")
        if risk is None and trade.get("entry") is not None and trade.get("stop") is not None:
            risk = abs(float(trade["entry"]) - float(trade["stop"]))
        if risk:
            pressed = engine_micros(float(p.get("risk_usd", 800)), float(risk), float(press.get("ref", 60)),
                                    int(p.get("max_micros", 40)))
            if pressed > base:
                reasons.append(f"fast eval: {pressed} instead of {base} micros (eval {eval_profit:+,.0f} vs floor {float(press.get('floor', -1000)):+,.0f})")
                base = pressed
    mult = float(cold_mult)
    if mult < 1:
        reasons.append(f"cold streak x{mult:g}")
    if sz.get("late_mult") is not None and is_late(trade):
        mult *= float(sz["late_mult"])
        reasons.append(f"late entry (15m already turned) x{float(sz['late_mult']):g}")
    q = base if mult >= 1 else max(1, int(math.floor(base * mult)))
    q = min(q, int(p.get("max_micros", 40)))
    return {"qty": q, "mult": round(q / qty, 4) if qty else 0.0, "reasons": reasons}


# ------------------------------------------------------------------------------------------------ LIT (live_model.json "lit_sizing")
MFFU_50K = {"start": 50000.0, "target": 3000.0, "mll": 2000.0, "lock": 50100.0}


def mffu_eval(day_pnl: dict, plan: dict | None = None) -> dict:
    """MFFU Builder 50K eval from P&L per trading day: balance, trailing max-loss floor (end-of-day high - $2,000, locked at
    $50,100) and the room (cushion) between them. Same rule as tools/cloud_monitor.eval_track."""
    p = {**MFFU_50K, **(plan or {})}
    bal = peak = p["start"]
    mll = p["start"] - p["mll"]
    for d in sorted(day_pnl):
        bal += float(day_pnl[d])
        peak = max(peak, bal)
        mll = min(max(mll, peak - p["mll"]), p["lock"])
    return {"balance": round(bal, 2), "profit": round(bal - p["start"], 2), "to_target": round(p["start"] + p["target"] - bal, 2),
            "trailing_mll": round(mll, 2), "cushion": round(bal - mll, 2)}


def lit_qty(qty: int, trade: dict, cfg: dict | None = None, room: float | None = None, max_micros: int = 40,
            state: dict | None = None, learning="auto") -> dict:
    """Micros to route for one LIT entry. qty = the model's micros (engine/lit.py: $800 up to a 20-pt stop, then 800x20/stop,
    times the weekly stop, rounded once). cfg = live_model.json "lit_sizing" {"mode": "normal" | "eval" | "fast_eval" |
    "safe_eval" | "two_week"}:
      two_week   one winner passes (two_week_qty below, cfg["two_week"]): micros so the trade's target covers what is still
                 needed to the eval target, capped by room_f of the room to the trailing floor, the soft daily loss and
                 max_micros, min 1; 0 = no trade (the day already reached the target). Needs the stop distance (risk_pts or
                 entry + stop0/stop), the target distance (tgt_pts or entry + target) and the eval state
                 (state = eval_state(): profit, cum, room, session). Any of them missing: the eval mode below, reason logged.
      eval       $800 up to an eval_ref_stop (25) pt stop, then 800x25/stop, times the weekly stop, then the safe_eval cap
      normal     the model's micros (default)
      fast_eval  $800 up to a fast_ref_stop (40) pt stop, then 800x40/stop, times the model's size multiplier (weekly stop),
                 rounded down once, floor 1 (run lit_x_fast_eval)
      safe_eval  the model's micros capped at safe_cap (60%) of room / (stop x $2), min 1; room = eval balance - trailing
                 max-loss floor (run lit_x_room_cap60). room None = unknown: no cap (reason logged)
    learning (engine/lit_learn.py, the learning loop): "auto" = data/lit_learning.json (env LE_LIT_LEARNING), a dict, or
    None. In mode "apply" the learned bucket multiplier (0.5-1.25x) joins the weekly stop in the one rounding (a size-up
    never risks more than $900) and a learned skip routes 0; in "observe", or with no file / no features, nothing changes
    (the would-be multiplier is returned under "learn"). two_week mode honours a learned skip only.
    Returns {"qty", "mult" (vs the model's micros), "reasons"} (+ "fallback": why two_week fell back to eval, "learn")."""
    c = cfg or {}
    mode = c.get("mode") or "normal"
    if qty <= 0:
        return {"qty": 0, "mult": 0.0, "reasons": ["no size"]}
    reasons = list(trade.get("size_why") or [])
    risk = trade.get("risk_pts")
    if risk is None and trade.get("entry") is not None and trade.get("stop0", trade.get("stop")) is not None:
        risk = abs(float(trade["entry"]) - float(trade.get("stop0", trade.get("stop"))))
    q = int(qty)
    fallback = None
    L = _learn(trade, learning)
    lm = float(L["mult"])
    if L["skip"]:
        return {"qty": 0, "mult": 0.0, "reasons": reasons + L["reasons"], "learn": L}
    if mode == "two_week":
        tgt = _num(trade.get("tgt_pts", trade.get("tgt")))
        if tgt is None and trade.get("entry") is not None and trade.get("target") is not None:
            tgt = abs(float(trade["target"]) - float(trade["entry"]))
        st = state or {}
        missing = [k for k, ok in (("stop distance", _num(risk) not in (None, 0.0)), ("target distance", bool(tgt)),
                                   ("eval state", state is not None)) if not ok]
        missing += [f"eval {k}" for k in ("profit", "cum", "room", "session") if state is not None and _num(st.get(k)) is None]
        if missing:
            fallback = f"two_week: {', '.join(missing)} unknown -> eval mode"
            reasons.append(fallback)
            log.warning("lit_qty %s", fallback)
            mode = "eval"
        else:
            tw = c.get("two_week") or {}
            acct = {**(tw.get("acct") or {})}
            acct.setdefault("max_micros", int(max_micros))
            why: list = []
            q = two_week_qty({"risk_pts": float(risk), "tgt_pts": float(tgt), "size_mult": trade.get("size_mult", 1.0)},
                             st, tw, acct=acct, why=why)
            reasons += [f"two week: {w}" for w in why]
            if q <= 0:
                return {"qty": 0, "mult": 0.0, "reasons": reasons}
            q = min(q, max_micros)
            return {"qty": q, "mult": round(q / qty, 4), "reasons": reasons}
    if mode == "fast_eval" and risk:
        from .lit import qty_for
        base = qty_for(float(risk), 800.0, float(c.get("fast_ref_stop", 40.0)), max_micros)
        m = float(trade.get("size_mult") or 1.0) * lm
        q = _one_round(base, m, lm, risk, max_micros)
        reasons.append(f"fast eval: $800 up to a {float(c.get('fast_ref_stop', 40.0)):g}-pt stop -> {q} micros")
    if mode == "eval" and risk:
        # the eval mode (2026-10-18, run lit_tight_eval_800_25_room60): $800 up to an eval_ref_stop (25) pt stop, then
        # 800x25/stop, times the weekly stop, rounded once; then the safe_eval room cap below
        from .lit import qty_for
        base = qty_for(float(risk), 800.0, float(c.get("eval_ref_stop", 25.0)), max_micros)
        m = float(trade.get("size_mult") or 1.0) * lm
        q = _one_round(base, m, lm, risk, max_micros)
        reasons.append(f"eval size: $800 up to a {float(c.get('eval_ref_stop', 25.0)):g}-pt stop -> {q} micros")
    if mode in ("normal", "safe_eval") and risk and abs(lm - 1.0) > 1e-9:
        from .lit import qty_for
        q = _one_round(qty_for(float(risk)), float(trade.get("size_mult") or 1.0) * lm, lm, risk, max_micros)
    if mode in ("safe_eval", "eval") and risk:
        if room is None:
            reasons.append("safe eval: eval room unknown, no cap")
        else:
            cap = int(float(c.get("safe_cap", 0.6)) * max(0.0, float(room)) / (float(risk) * 2.0))
            if cap < q:
                q = max(1, cap)
                reasons.append(f"safe eval: {q} micro{'s' if q != 1 else ''} = {float(c.get('safe_cap', 0.6)) * 100:.0f}% of ${float(room):,.0f} room to the max-loss floor")
    q = min(q, max_micros)
    out = {"qty": q, "mult": round(q / qty, 4), "reasons": reasons + (L["reasons"] if mode != "two_week" else [])}
    if L.get("mode"):
        out["learn"] = L
    if fallback:
        out["fallback"] = fallback
    return out


LEARN_RISK_CAP = 900.0      # engine/lit_learn.py RISK_CAP: a learned size-up never risks more than this ($1,000 soft daily loss)


def _one_round(base, m, lm, risk, max_micros):
    """base micros x (weekly stop x learned multiplier), rounded down once, floor 1, max max_micros; a size-up (lm > 1)
    never risks more than LEARN_RISK_CAP. With lm 1 this is the old rule exactly (base, or base x weekly stop, floor 1)."""
    q = int(base) if abs(m - 1.0) < 1e-9 else min(int(max_micros), int(base * m + 1e-9))
    if lm > 1.0 + 1e-9 and risk:
        q = min(q, int(LEARN_RISK_CAP / (float(risk) * 2.0 + 1.40)))
    return max(1, q)


def _learn(trade, learning):
    """engine/lit_learn.learn_mult for this entry; never raises (a failure means 1.0, nothing applied)."""
    try:
        from . import lit_learn
        L = lit_learn.load_learning() if isinstance(learning, str) and learning == "auto" else learning
        return lit_learn.learn_mult(trade, L)
    except Exception as e:                     # pragma: no cover
        log.warning("learning layer off: %s", e)
        return {"mult": 1.0, "skip": False, "would": 1.0, "would_skip": False, "mode": None, "buckets": None, "reasons": []}


# ------------------------------------------------------------------------------------------------ LIT two-week eval
# Moved here from tools/lit_2wk_sizing.py (the study keeps importing it from there). Every $ figure is for the 50K and is
# multiplied by acct["scale"].
#   base       "need" (default) = one winner passes: micros so the trade's target $ covers what is still needed to the eval
#              target, ceil(need x need_buf / (target pts x $2 - $1.40)) | "lit" = $usd up to a ref-pt stop, then usd x ref / stop
#   need_buf   1.0
#   usd, ref   800, 25 (base "lit" only)
#   max_usd    None | $ cap of a full stop-out per trade (stop + 1 tick, commission in)
#   wk         True = times the weekly stop's multiplier (trade["size_mult"], half after 2 stop-outs in the week)
#   press_at, press_mult, press_room    from eval session press_at on (not passed yet): micros x press_mult (before the caps)
#                                       and the room cap at press_room instead of room_f (None = unchanged)
#   protect_over, protect_keep    once the eval profit is >= protect_over, a full stop-out may not take the profit below
#                                 protect_keep x profit
#   room_f     0.6 | None: micros <= room_f x room / (stop x $2), room = balance - trailing max-loss floor
#   dll_cap    True: a full stop-out (stop + 1 tick, commission) may not take the day below -dll (the MFFU soft daily loss)
#   stop_at_target  True: no new trade once the day's P&L already reaches the eval target (never risk the pass)
# Always: at least 1 micro (the room / daily caps never go below 1), at most max_micros.
# state = {"profit": eval profit at the start of the day ($, vs the start balance), "cum": today's closed P&L ($),
#          "room": balance + cum - trailing floor ($), "session": eval session number (1 = first day), "n_today": trades so far}
# trade = {"risk_pts" | "risk": stop distance at entry (pts), "tgt_pts" | "tgt" | (entry, target): target distance (pts),
#          "size_mult" | "wk_m": weekly-stop multiplier}
TW_PV, TW_COMM, TW_SLIP = 2.0, 1.40, 0.25
TW_50K = {"target": 3000.0, "mll": 2000.0, "lock": 100.0, "dll": 1000.0, "max_micros": 40, "scale": 1.0}
TW_25K = {"target": 1500.0, "mll": 1000.0, "lock": 100.0, "dll": 600.0, "max_micros": 20, "scale": 0.5}
TW_DEFAULT = {"base": "need", "need_buf": 1.0, "usd": 800.0, "ref": 25.0, "max_usd": None, "wk": True,
              "press_at": None, "press_mult": 1.0, "press_room": None, "protect_over": None, "protect_keep": 0.0,
              "room_f": 0.6, "dll_cap": True, "stop_at_target": True}
EVAL_SESSIONS = 10          # the owner's rule: an eval not passed after 10 sessions is reset (a new purchase)


def _num(x, d=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def two_week_qty(trade: dict, state: dict, cfg: dict | None = None, acct: dict | None = None, why: list | None = None) -> int:
    """Micros for one LIT entry in a two-week eval. 0 = no trade (only when the day already reached the target)."""
    c = {**TW_DEFAULT, **(cfg or {})}
    A = {**TW_50K, **(acct or {})}
    PV, COMM, SLIP = TW_PV, TW_COMM, TW_SLIP
    sc = float(A.get("scale", 1.0))
    maxq = int(A["max_micros"])
    risk = _num(trade.get("risk_pts", trade.get("risk")))
    if risk is None and trade.get("entry") is not None and trade.get("stop") is not None:
        risk = abs(float(trade["entry"]) - float(trade["stop"]))
    if not risk or risk <= 0:
        return 0
    tgt = _num(trade.get("tgt_pts", trade.get("tgt")))
    if tgt is None and trade.get("entry") is not None and trade.get("target") is not None:
        tgt = abs(float(trade["target"]) - float(trade["entry"]))
    profit = float(state.get("profit") or 0.0)
    cum = float(state.get("cum") or 0.0)
    room = _num(state.get("room"))
    sess = int(state.get("session") or 1)
    need = float(A["target"]) - profit - cum
    note = (lambda s: why.append(s)) if why is not None else (lambda s: None)
    if c["stop_at_target"] and need <= 0:
        note("eval target already reached today: no new trade")
        return 0
    loss1 = (risk + SLIP) * PV + COMM                       # a full stop-out of 1 micro, $
    # ---- base size
    if c["base"] == "need" and tgt and tgt * PV - COMM > 0:
        q = math.ceil(need * float(c["need_buf"]) / (tgt * PV - COMM) - 1e-9)
        note(f"one winner passes: {q} micros x {tgt:.1f} pts target covers ${need:,.0f}")
    else:
        usd, ref = float(c["usd"]) * sc, float(c["ref"])
        r = usd if risk <= ref else usd * ref / risk
        q = int(r / (risk * PV))
        note(f"${usd:,.0f} up to a {ref:g}-pt stop -> {q} micros")
    q = max(1, q)
    if c["wk"]:
        m = _num(trade.get("size_mult", trade.get("wk_m")), 1.0)
        if m < 1:
            q = max(1, int(q * m + 1e-9))
            note(f"weekly stop x{m:g} -> {q}")
    room_f = c["room_f"]
    if c["press_at"] and sess >= int(c["press_at"]):
        if float(c["press_mult"]) != 1.0:
            q = max(1, int(q * float(c["press_mult"]) + 1e-9))
            note(f"clock press from session {int(c['press_at'])}: x{float(c['press_mult']):g} -> {q}")
        if c["press_room"] is not None:
            room_f = c["press_room"]
            note(f"clock press from session {int(c['press_at'])}: room cap {float(room_f) * 100:.0f}%")
    # ---- caps (never below 1 micro)
    caps = []
    if c["max_usd"]:
        caps.append((int(float(c["max_usd"]) * sc / loss1), f"max ${float(c['max_usd']) * sc:,.0f} a trade"))
    if c["protect_over"] is not None and profit >= float(c["protect_over"]) * sc:
        keep = float(c["protect_keep"]) * profit
        caps.append((int(max(0.0, profit + cum - keep) / loss1), f"protect: a loss keeps the profit above ${keep:,.0f}"))
    if room_f and room is not None:
        caps.append((int(float(room_f) * max(0.0, room) / (risk * PV)), f"{float(room_f) * 100:.0f}% of ${room:,.0f} room"))
    if c["dll_cap"]:
        caps.append((int(max(0.0, float(A["dll"]) + cum) / loss1), f"soft daily loss ${float(A['dll']):,.0f}"))
    for cap, lab in caps:
        if cap < q:
            q = max(1, cap)
            note(f"{lab} -> {q}")
    return int(min(q, maxq))


def eval_state(day_pnl: dict, today_cum: float = 0.0, plan: dict | None = None, session: int | None = None) -> dict:
    """state for two_week_qty from the eval's closed P&L per earlier session since the eval started (sorted keys) + today's
    closed P&L. Same floor rule as mffu_eval: EOD high - max loss, locked at start + lock. session = today's eval session
    number (eval_session()); None = len(day_pnl) + 1, i.e. day_pnl holds every earlier session (0 on days without a trade)."""
    A = {**TW_50K, **(plan or {})}
    bal = peak = 0.0
    floor = -float(A["mll"])
    for d in sorted(day_pnl):
        bal += float(day_pnl[d])
        peak = max(peak, bal)
        floor = min(max(floor, peak - float(A["mll"])), float(A["lock"]))
    return {"profit": round(bal, 2), "cum": float(today_cum), "room": round(bal + today_cum - floor, 2),
            "session": int(session) if session is not None else len(day_pnl) + 1, "n_today": 0}


def _full_closures(y: int) -> set:
    """CME equity futures days with no session at all: New Year's Day, Good Friday, Christmas (observed). The other US
    holidays are early-close sessions and count as eval sessions."""
    def obs(d):
        return d + _dt.timedelta(days=1) if d.weekday() == 6 else d - _dt.timedelta(days=1) if d.weekday() == 5 else d
    out = {obs(_dt.date(y, 1, 1)), obs(_dt.date(y, 12, 25))}
    try:
        from .lit_live import _easter
        out.add(_easter(y) - _dt.timedelta(days=2))
    except Exception:
        pass
    return out


def eval_session(start: str | None, day: str) -> int | None:
    """Eval session number of trading day `day` (yyyy-mm-dd) for an eval started on `start` (1 = the start day): weekdays
    from start to day, without the full CME closures. None when start is unknown; 0 when day is before the start."""
    if not start:
        return None
    try:
        a, z = _dt.date.fromisoformat(str(start)[:10]), _dt.date.fromisoformat(str(day)[:10])
    except ValueError:
        return None
    if z < a:
        return 0
    shut = set().union(*(_full_closures(y) for y in range(a.year, z.year + 1)))
    n, d = 0, a
    while d <= z:
        if d.weekday() < 5 and d not in shut:
            n += 1
        d += _dt.timedelta(days=1)
    return max(1, n)


def eval_clock(day_pnl: dict, start: str | None, today: str, session_over: bool = False, plan: dict | None = None) -> dict:
    """The two-week eval clock for the dashboards (state key "eval_2wk"): session number since `start`, status (not started /
    open / passed / failed, from the closed P&L per day since the start) and the reset reminder: an eval still open after
    session EVAL_SESSIONS (10) -> reset recommended (buy a new one, set lit_sizing.eval_start to its first session)."""
    A = {**TW_50K, **(plan or {})}
    days = {d: float(v) for d, v in (day_pnl or {}).items() if not start or d >= str(start)}
    sess = eval_session(start, today)
    st = eval_state({d: v for d, v in days.items() if d < today}, days.get(today, 0.0), plan)
    bal = st["profit"] + st["cum"]
    if sess is None:
        status = "unknown"
    elif sess == 0:
        status = "not started"
    elif bal >= float(A["target"]):
        status = "passed"
    elif st["room"] <= 0:
        status = "failed"
    else:
        status = "open"
    done = 0 if not sess else sess - (0 if session_over else 1)
    reset = status == "open" and done >= EVAL_SESSIONS
    if status == "open":
        text = (f"reset recommended: {done} sessions done without a pass (the 2-week rule); buy a new eval and set "
                f"lit_sizing.eval_start to its first session" if reset else
                f"session {sess} of {EVAL_SESSIONS}, {max(0, EVAL_SESSIONS - done)} left")
    elif status == "not started":
        text = f"eval starts {start}"
    elif status == "unknown":
        text = "eval start unknown (lit_sizing.eval_start)"
    else:
        text = f"eval {status} in {sess} sessions: buy the next one and set lit_sizing.eval_start"
    return {"start": start, "session": sess, "sessions_done": done, "limit": EVAL_SESSIONS, "status": status,
            "profit": round(bal, 2), "room": st["room"], "to_target": round(float(A["target"]) - bal, 2),
            "reset": bool(reset), "text": text}


def selftest() -> bool:
    t_late = {"dir": 1, "m15_trend": 1, "risk_pts": 44.0}
    t_ok = {"dir": -1, "m15_trend": 1, "risk_pts": 44.0}
    sz = {"late_mult": 0.5, "press": None}
    assert route_qty(4, t_ok, 1.0, sz)["qty"] == 4
    assert route_qty(4, t_ok, 0.25, sz)["qty"] == 1
    assert route_qty(4, t_late, 1.0, sz)["qty"] == 2
    assert route_qty(4, t_late, 0.25, sz)["qty"] == 1            # 4 x 0.125 = 0.5 -> floor 1
    assert route_qty(9, t_late, 0.5, sz)["qty"] == 2             # one rounding: floor(9 x 0.25) = 2
    assert route_qty(4, t_ok, 0.0, sz)["qty"] == 0
    assert engine_micros(800, 44.0, 20) == 4 and engine_micros(800, 44.0, 60) == 9 and engine_micros(800, 10.0, 20) == 40
    fast = {"late_mult": 0.5, "press": {"floor": -1000, "ref": 60}}
    r = route_qty(4, t_ok, 1.0, fast, {"risk_usd": 800, "max_micros": 40}, eval_profit=0.0)
    assert r["qty"] == 9 and "fast eval" in r["reasons"][0], r
    assert route_qty(4, t_ok, 1.0, fast, {"risk_usd": 800}, eval_profit=-1500.0)["qty"] == 4
    assert route_qty(4, t_late, 0.25, fast, {"risk_usd": 800}, eval_profit=500.0)["qty"] == 1   # 9 x 0.125 = 1.1 -> 1
    lt = {"risk_pts": 47.0}
    assert lit_qty(3, lt)["qty"] == 3 and lit_qty(3, lt, {"mode": "normal"})["qty"] == 3
    assert lit_qty(3, {"risk_pts": 44.0, "size_mult": 1.0}, {"mode": "eval", "eval_ref_stop": 25})["qty"] == 5   # 800*25/44 / 88 = 5.2
    assert lit_qty(3, {"risk_pts": 44.0, "size_mult": 1.0}, {"mode": "eval", "safe_cap": 0.6}, room=300)["qty"] == 2   # 180/88
    assert lit_qty(3, lt, {"mode": "fast_eval"})["qty"] == 7                       # 800*40/47 = 680.9 / 94 = 7.2 -> 7
    assert lit_qty(1, {**lt, "size_mult": 0.5}, {"mode": "fast_eval"})["qty"] == 3  # 7 x 0.5 = 3.5 -> 3 (one rounding)
    assert lit_qty(3, lt, {"mode": "safe_eval"}, room=2000.0)["qty"] == 3           # 0.6*2000/94 = 12.8 -> no cap
    assert lit_qty(3, lt, {"mode": "safe_eval"}, room=300.0)["qty"] == 1            # 0.6*300/94 = 1.9 -> 1
    assert lit_qty(3, lt, {"mode": "safe_eval"}, room=50.0)["qty"] == 1             # min 1
    assert mffu_eval({"a": 1000, "b": -500})["trailing_mll"] == 49000.0 and mffu_eval({})["cushion"] == 2000.0
    # two_week (config C, live_model.json 2026-10-18): one winner passes, 60% of the room, no weekly stop
    C = {"mode": "two_week", "two_week": {"base": "need", "need_buf": 1.0, "room_f": 0.6, "wk": False, "dll_cap": True,
                                          "stop_at_target": True}, "eval_ref_stop": 25.0, "safe_cap": 0.6}
    fresh = eval_state({}, 0.0, session=1)
    assert fresh == {"profit": 0.0, "cum": 0.0, "room": 2000.0, "session": 1, "n_today": 0}, fresh
    # 40-pt stop, 200-pt target: ceil(3000 / 398.6) = 8; 60% room cap 1200 / 80 = 15, dll 1000 / 81.9 = 12 -> 8
    r = lit_qty(3, {"risk_pts": 40.0, "tgt_pts": 200.0}, C, state=fresh)
    assert r["qty"] == 8 and "one winner passes" in r["reasons"][0] and "fallback" not in r, r
    # target from the live position's prices (entry, stop0, target), weekly stop ignored (wk false)
    pos = {"entry": 20000.0, "stop0": 19960.0, "stop": 20000.0, "target": 20200.0, "risk_pts": 40.0, "size_mult": 0.5}
    assert lit_qty(3, pos, C, state=fresh)["qty"] == 8
    # a 1.5R target wants 26 micros: room 60% 1200 / 80 = 15, soft daily loss 1000 / 81.9 = 12 -> 12
    assert lit_qty(3, {"risk_pts": 40.0, "tgt_pts": 60.0}, C, state=fresh)["qty"] == 12
    # after a -$1,000 day: room $1,000 -> 600 / 80 = 7
    st = eval_state({"2026-10-19": -1000.0}, 0.0, session=2)
    assert st["room"] == 1000.0 and lit_qty(3, {"risk_pts": 40.0, "tgt_pts": 60.0}, C, state=st)["qty"] == 7
    # the day already reached the target: no trade
    assert lit_qty(3, {"risk_pts": 40.0, "tgt_pts": 200.0}, C, state={"profit": 2900.0, "cum": 200.0, "room": 2000.0, "session": 3})["qty"] == 0
    # max micros
    assert lit_qty(3, {"risk_pts": 8.0, "tgt_pts": 12.0}, {**C, "two_week": {**C["two_week"], "dll_cap": False, "room_f": None}},
                   state=fresh)["qty"] == 40
    # missing inputs -> the eval mode ($800 up to 25 pts, 60% room cap), reason kept
    r = lit_qty(3, {"risk_pts": 44.0}, C, room=2000.0, state=fresh)                    # no target
    assert r["qty"] == 5 and "target distance unknown" in r["fallback"], r
    r = lit_qty(3, {"risk_pts": 44.0, "tgt_pts": 100.0}, C, room=300.0)                # no eval state
    assert r["qty"] == 2 and "eval state unknown" in r["fallback"], r
    r = lit_qty(3, {"risk_pts": 44.0, "tgt_pts": 100.0}, C, room=2000.0, state={"profit": 0.0, "cum": 0.0, "room": None, "session": 1})
    assert r["qty"] == 5 and "eval room unknown" in r["fallback"], r
    # sessions: Mon 2026-10-19 = 1, Fri 10-30 = 10, Mon 11-02 = 11; Christmas / New Year / Good Friday skipped
    assert eval_session("2026-10-19", "2026-10-19") == 1 and eval_session("2026-10-19", "2026-10-30") == 10
    assert eval_session("2026-10-19", "2026-11-02") == 11 and eval_session("2026-10-19", "2026-10-18") == 0
    assert eval_session("2026-12-21", "2026-12-28") == 5 and eval_session(None, "2026-10-19") is None
    assert eval_session("2026-03-30", "2026-04-06") == 5                                  # Good Friday 2026-04-03
    # the 10-session clock and the reset reminder
    ck = eval_clock({"2026-10-20": 500.0}, "2026-10-19", "2026-10-30", session_over=False)
    assert ck["status"] == "open" and ck["session"] == 10 and not ck["reset"], ck
    assert eval_clock({"2026-10-20": 500.0}, "2026-10-19", "2026-10-30", session_over=True)["reset"]
    assert eval_clock({"2026-10-20": 500.0}, "2026-10-19", "2026-11-02")["reset"]
    assert eval_clock({"2026-10-20": 3100.0}, "2026-10-19", "2026-11-02")["status"] == "passed"
    assert eval_clock({"2026-10-20": -2000.0}, "2026-10-19", "2026-10-21")["status"] == "failed"
    assert eval_clock({}, "2026-10-19", "2026-10-18")["status"] == "not started"
    assert eval_clock({"2026-10-16": -900.0}, "2026-10-19", "2026-10-19")["room"] == 2000.0   # days before the start ignored
    print("sizing selftest OK")
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if selftest() else 1)
