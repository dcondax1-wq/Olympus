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
research/writeups/lit-two-week-eval.md, run lit_2wk_rec = config C); eval_clock() is the session clock (no reset since
2026-10-18, owner: one-time fee). 2026-10-18 additions (research/writeups/lit-funded-sizing.md): mode "funded" (funded_qty,
funded_state: the MFFU sim-funded account), mode "auto" (two_week until the eval is passed, then funded), two_week_until +
after_mode (the eval goes on in another mode after session N), the opt-in day guard (lit_sizing.guard, day_guard), $1.90
commission and the minimum-days trade in two_week.
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


GUARD_DEFAULT = {"max_per_day": 1, "stop_at_target": True, "target": 3000.0, "slip_ticks": 2, "est_pad_pts": 2.0,
                 "breach": "skip", "dll": 1000.0, "max_micros": 40}
EVAL_MODES = ("eval", "safe_eval", "fast_eval", "two_week")


def lit_qty(qty: int, trade: dict, cfg: dict | None = None, room: float | None = None, max_micros: int = 40,
            state: dict | None = None, learning="auto") -> dict:
    """lit_qty_core below, then the day-level guard when cfg["guard"] is set (risk audit 2026-10-18,
    research/writeups/lit-funded-sizing.md; off = exactly the old sizing). cfg["guard"] = {} (GUARD_DEFAULT) or a dict:
      max_per_day     1: state["n_today"] (entries already routed today) >= this -> 0 (the router's own 1-a-day cap)
      stop_at_target  True, eval modes only: state profit + cum >= target -> 0 (the eval is passed: never risk it)
      slip_ticks      2: ticks of stop slippage in the worst-case loss; est_pad_pts 2.0: extra pts when the stop distance
                      is an estimate (trade["est"]: the 1m CISD close, the real open can widen the stop)
      floor           room (state["room"], else the room argument): a worst-case stop-out must stay < room;
      dll             a worst-case stop-out must stay < dll + today's closed P&L (state["cum"])
      breach          "skip" (default): when even 1 micro breaks the floor / dll -> 0 | "one": keep 1 micro (old rule)
      max_micros      40
    Unknown room / state: that check is skipped and said in the reasons."""
    c = cfg or {}
    wl = c.get("wk_loss_usd")
    if wl and (c.get("mode") or "normal") in EVAL_MODES and state is not None and qty > 0:
        # eval weekly loss stop (default off; research/writeups/lit-risk-money.md, run lit_risk_m_wk1200): once this eval's
        # closed P&L of the current calendar week (state["wk_pnl"], from eval_state(..., today=)) is <= -wk_loss_usd, no new
        # entry until the next week. Week P&L unknown: no effect (reason logged).
        w = _num(state.get("wk_pnl"))
        if w is not None and w <= -float(wl):
            why = f"eval weekly loss stop: this week ${w:,.0f} <= -${float(wl):,.0f}: no new trade until next week"
            log.info("lit_qty %s", why)
            return {"qty": 0, "mult": 0.0, "reasons": list(trade.get("size_why") or []) + [why]}
        if w is None:
            r0 = lit_qty_core(qty, trade, c, room=room, max_micros=max_micros, state=state, learning=learning)
            r0["reasons"] = list(r0.get("reasons") or []) + ["eval weekly loss stop: week P&L unknown (eval_state today=), not applied"]
            return r0 if c.get("guard") is None else day_guard(r0, trade, c, room=room, state=state)
    r = lit_qty_core(qty, trade, c, room=room, max_micros=max_micros, state=state, learning=learning)
    if c.get("guard") is None:
        return r
    return day_guard(r, trade, c, room=room, state=state)


def day_guard(r: dict, trade: dict, cfg: dict, room: float | None = None, state: dict | None = None) -> dict:
    """The day-level guard on one sizing result r = {"qty", "mult", "reasons"} (see lit_qty)."""
    g = {**GUARD_DEFAULT, **(cfg.get("guard") or {})}
    mode = cfg.get("mode") or "normal"
    q0 = int(r.get("qty") or 0)
    out = {**r, "reasons": list(r.get("reasons") or [])}
    if q0 <= 0:
        return out
    st = state or {}

    def stop(why):
        out.update(qty=0, mult=0.0, guard=why)
        out["reasons"].append(f"guard: {why}")
        log.warning("lit_qty guard: %s", why)
        return out
    n_today = _num(st.get("n_today"))
    if g["max_per_day"] and n_today is not None and n_today >= int(g["max_per_day"]):
        return stop(f"{int(n_today)} entr{'y' if n_today == 1 else 'ies'} already routed today (max {int(g['max_per_day'])}): no trade")
    cum = float(_num(st.get("cum"), 0.0))
    prof = _num(st.get("profit"))
    if g["stop_at_target"] and mode in EVAL_MODES and prof is not None and prof + cum >= float(g["target"]):
        return stop(f"eval at +${prof + cum:,.0f}, target ${float(g['target']):,.0f} reached: no new trade")
    risk = _num(trade.get("risk_pts"))
    if risk is None and trade.get("entry") is not None and trade.get("stop0", trade.get("stop")) is not None:
        risk = abs(float(trade["entry"]) - float(trade.get("stop0", trade.get("stop"))))
    if not risk or risk <= 0:
        out["reasons"].append("guard: stop distance unknown, floor / daily checks skipped")
        return out
    pad = float(g["est_pad_pts"]) if trade.get("est") else 0.0
    loss1 = (risk + pad + 0.25 * float(g["slip_ticks"])) * TW_PV + TW_COMM
    q = min(q0, int(g["max_micros"]))
    rm = _num(st.get("room")) if st.get("room") is not None else _num(room)
    lims = [(float(g["dll"]) + cum, f"soft daily loss (${float(g['dll']):,.0f}, day {cum:+,.0f})")]
    if rm is not None:
        lims.insert(0, (rm, f"${rm:,.0f} room to the max-loss floor"))
    else:
        out["reasons"].append("guard: room to the floor unknown, floor check skipped")
    for lim, lab in lims:
        cap = math.ceil(lim / loss1) - 1 if lim > 0 else 0          # largest q with q x loss1 < lim
        if cap < q:
            if cap < 1:
                if g["breach"] == "skip":
                    return stop(f"1 micro's worst-case stop-out ${loss1:,.0f} would reach the {lab}: no trade")
                q = 1
                out["reasons"].append(f"guard: 1 micro's worst case ${loss1:,.0f} reaches the {lab} (breach rule 'one': kept 1)")
            else:
                q = cap
                out["reasons"].append(f"guard: worst case ${loss1:,.0f}/micro ({risk + pad:.1f} pts + {int(g['slip_ticks'])} ticks) "
                                      f"inside the {lab} -> {q}")
    if q != q0:
        out["qty"] = q
        out["mult"] = round(out.get("mult", 1.0) * q / q0, 4) if q0 else 0.0
    return out


def lit_qty_core(qty: int, trade: dict, cfg: dict | None = None, room: float | None = None, max_micros: int = 40,
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
    (the would-be multiplier is returned under "learn"). two_week mode honours a learned skip and a learned cut below 1x,
    never a size-up.
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
    if mode == "auto":
        # eval until it is passed, then the funded rules (2026-10-18). state = eval_state() (+ "days_traded"); the eval counts
        # as passed once profit (earlier sessions) >= the target: the minimum-days trade first (two_week, 1 micro while
        # days_traded < min_days), then mode "funded" on state["funded"] (= funded_state() of the funded account; missing ->
        # the funded fallback, the smallest size). Never "one winner passes" sizing on a passed / funded account.
        st = state or {}
        tgt_usd = float(((c.get("two_week") or {}).get("acct") or {}).get("target", TW_50K["target"]))
        passed = state is not None and _num(st.get("profit")) is not None and float(st["profit"]) >= tgt_usd
        if passed:
            mind = (c.get("two_week") or {}).get("min_days", TW_DEFAULT["min_days"])
            if mind and _num(st.get("days_traded"), 1.0) < float(mind):
                mode = "two_week"
            else:
                out = lit_qty_core(qty, trade, {**c, "mode": "funded"}, room=None, max_micros=max_micros,
                                   state=st.get("funded"), learning=learning)
                out["reasons"] = ["auto: eval passed -> funded sizing"] + list(out.get("reasons") or [])
                return out
        else:
            mode = c.get("eval_mode") or "two_week"
    if mode == "two_week" and c.get("two_week_until") and state is not None and _num(state.get("session")) is not None \
            and float(state["session"]) > float(c["two_week_until"]):
        # owner 2026-10-18: no reset; after session two_week_until the eval goes on in lit_sizing.after_mode (default eval)
        mode = c.get("after_mode") or "eval"
        reasons.append(f"session {int(state['session'])} > {int(c['two_week_until'])}: {mode} sizing")
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
            q = two_week_qty({"risk_pts": float(risk), "tgt_pts": float(tgt), "size_mult": _wk_of(trade), **_idm_keys(trade)},
                             st, {**tw, **({"idm": c["idm"]} if "idm" in c else {})}, acct=acct, why=why)
            reasons += [f"two week: {w}" for w in why]
            if q <= 0:
                return {"qty": 0, "mult": 0.0, "reasons": reasons}
            q = min(q, max_micros)
            if lm < 1.0 - 1e-9:                # learned cut (never a size-up: the two-week caps already sit at the limit)
                q = max(1, int(q * lm + 1e-9))
                reasons += L["reasons"]
            out = {"qty": q, "mult": round(q / qty, 4), "reasons": reasons}
            if L.get("mode"):
                out["learn"] = L
            return out
    if mode == "funded":
        # the funded account (funded_qty above, cfg["funded"]); state = funded_state() {room, cum, locked}; state None ->
        # room = the `room` argument (locked unknown = not locked), or the smallest size when that is unknown too
        st = state if state is not None else ({"room": room, "cum": 0.0, "locked": False} if room is not None else None)
        why: list = []
        acct = {**(c.get("acct") or {})}
        acct.setdefault("max_micros", int(max_micros))
        if st is None:
            fallback = "funded: account state unknown -> smallest size, no room cap"
            log.warning("lit_qty %s", fallback)
        q = funded_qty({"risk_pts": _num(risk), "tgt_pts": trade.get("tgt_pts", trade.get("tgt")), "entry": trade.get("entry"),
                        "target": trade.get("target"), "size_mult": _wk_of(trade), **_idm_keys(trade)}, st,
                       {**(c.get("funded") or {}), **({"idm": c["idm"]} if "idm" in c else {})}, acct=acct, why=why)
        reasons += [f"funded: {w}" for w in why] + ([fallback] if fallback else [])
        if q <= 0:
            out = {"qty": 0, "mult": 0.0, "reasons": reasons}
            if fallback:
                out["fallback"] = fallback
            return out
        q = min(q, max_micros)
        if lm < 1.0 - 1e-9:                    # learned cut only, never a size-up (the funded caps sit at the limit)
            q = max(1, int(q * lm + 1e-9))
            reasons += L["reasons"]
        out = {"qty": q, "mult": round(q / qty, 4), "reasons": reasons}
        if L.get("mode"):
            out["learn"] = L
        if fallback:
            out["fallback"] = fallback
        return out
    if mode == "fast_eval" and risk:
        from .lit import qty_for
        base = qty_for(float(risk), 800.0, float(c.get("fast_ref_stop", 40.0)), max_micros)
        q = _idm_round(base, trade, lm, risk, max_micros, c.get("idm", "both"), reasons)
        reasons.append(f"fast eval: $800 up to a {float(c.get('fast_ref_stop', 40.0)):g}-pt stop -> {q} micros")
    if mode == "eval" and risk:
        # the eval mode (2026-10-18, run lit_tight_eval_800_25_room60): $800 up to an eval_ref_stop (25) pt stop, then
        # 800x25/stop, times the weekly stop, rounded once; then the safe_eval room cap below
        from .lit import qty_for
        base = qty_for(float(risk), 800.0, float(c.get("eval_ref_stop", 25.0)), max_micros)
        q = _idm_round(base, trade, lm, risk, max_micros, c.get("idm", "both"), reasons)
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
    out = {"qty": q, "mult": round(q / qty, 4), "reasons": reasons + L["reasons"]}
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


# ------------------------------------------------------------------------------------------------ inducement-count size
# engine/lit.py option idm_size (research/writeups/lit-new-entries.md; off = None) puts on each trade "idm_m" (the raw
# multiplier: up on 2+ inducements taken first, down on the rest), "idm_cap" (a size-up never risks more than this, full stop
# + 1 tick + $1.90) and "wk_m" (the rest of the model's multiplier: how_out x weekly stop). The model's "size_mult" is their
# product (capped at the LIT size). Modes that re-size from the stop (two_week, eval, fast_eval, funded) apply idm_m to their
# own base and re-check idm_cap, BEFORE their eval / account caps (60% room, soft daily loss, max micros), so a size-up can
# never pass those. normal / safe_eval route the model's micros, which already carry it. No "idm_m" on the trade = exactly
# the old sizing. lit_sizing "idm" (or two_week / funded "idm"): "both" (default) | "cut" (only the < 1x cut) | "off".
def _idm_keys(trade):
    return {k: trade[k] for k in ("idm_m", "idm_cap") if trade.get(k) is not None}


def _wk_of(trade):
    """The model's multiplier without the inducement part (= size_mult when the trade has no idm_m)."""
    if trade.get("idm_m") is not None:
        return _num(trade.get("wk_m"), 1.0)
    return trade.get("size_mult", 1.0)


def _idm_mult(trade, mode="both"):
    """(multiplier, $ cap) of the inducement-count size on this trade, or None (absent / 1x / switched off)."""
    m = _num(trade.get("idm_m"))
    if m is None or abs(m - 1.0) < 1e-9 or mode in (None, False, "off") or (mode == "cut" and m > 1.0):
        return None
    return m, _num(trade.get("idm_cap"))


def idm_apply(q: int, trade: dict, risk, max_micros: int = 40, mode="both", why: list | None = None) -> int:
    """q micros x the inducement-count multiplier (floor 1 on a cut; a size-up at most max_micros and never more than
    idm_cap at risk, but never below q). Unchanged when the trade has no idm_m."""
    I = _idm_mult(trade, mode)
    if I is None or q <= 0:
        return q
    m, cap = I
    if m < 1.0:
        q2 = max(1, int(q * m + 1e-9))
    else:
        q2 = min(int(max_micros), int(q * m + 1e-9))
        if cap and risk:
            q2 = min(q2, max(int(q), int(float(cap) / ((float(risk) + TW_SLIP) * TW_PV + TW_COMM))))
    if why is not None:
        why.append(f"inducements taken first x{m:g} -> {q2}")
    return q2


def _idm_round(base, trade, lm, risk, max_micros, mode, reasons):
    """eval / fast_eval: base x (weekly stop x learned x inducement) in one rounding, the size-up capped at idm_cap."""
    I = _idm_mult(trade, mode)
    wk = float(_wk_of(trade) or 1.0)
    q0 = _one_round(base, wk * lm, lm, risk, max_micros)
    if I is None:
        return q0
    m, cap = I
    q = _one_round(base, wk * lm * m, lm, risk, max_micros)
    if m > 1.0 and cap and risk:
        q = min(q, max(q0, int(float(cap) / ((float(risk) + TW_SLIP) * TW_PV + TW_COMM))))
    reasons.append(f"inducements taken first x{m:g} -> {q}")
    return q


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
#   min_days   2: after the target was reached on an earlier session, one 1-micro "minimum-days trade" while the eval has fewer
#              than min_days traded days (state "days_traded", unknown = 1); None = never
# Always: at least 1 micro (the room / daily caps never go below 1), at most max_micros.
# state = {"profit": eval profit at the start of the day ($, vs the start balance), "cum": today's closed P&L ($),
#          "room": balance + cum - trailing floor ($), "session": eval session number (1 = first day), "n_today": trades so far}
# trade = {"risk_pts" | "risk": stop distance at entry (pts), "tgt_pts" | "tgt" | (entry, target): target distance (pts),
#          "size_mult" | "wk_m": weekly-stop multiplier}
TW_PV, TW_COMM, TW_SLIP = 2.0, 1.90, 0.25   # MFFU MNQ round trip $1.90 (research/lit/mffu_rules.json; was 1.40 until 2026-10-18)
TW_DLL_SLIP = 0.5                            # the soft daily loss cap assumes 2 ticks of stop slippage (2026-10-18)
TW_50K = {"target": 3000.0, "mll": 2000.0, "lock": 100.0, "dll": 1000.0, "max_micros": 40, "scale": 1.0}
TW_25K = {"target": 1500.0, "mll": 1000.0, "lock": 100.0, "dll": 600.0, "max_micros": 20, "scale": 0.5}
TW_DEFAULT = {"base": "need", "need_buf": 1.0, "usd": 800.0, "ref": 25.0, "max_usd": None, "wk": True,
              "press_at": None, "press_mult": 1.0, "press_room": None, "protect_over": None, "protect_keep": 0.0,
              "room_f": 0.6, "dll_cap": True, "stop_at_target": True, "min_days": 2}
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
        # MFFU may need 2 trading days (help guide 1, plan page 2): once the target was reached on an EARLIER session and the
        # eval has fewer than min_days traded days, ONE 1-micro trade on a later session (state days_traded; unknown = 1)
        dtr = _num(state.get("days_traded"), 1.0)
        if (c.get("min_days") and profit >= float(A["target"]) and cum == 0 and not state.get("n_today")
                and dtr < float(c["min_days"])):
            note(f"minimum-days trade: target reached, {int(dtr)} of {int(c['min_days'])} trading days -> 1 micro")
            return 1
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
    q = idm_apply(q, trade, risk, maxq, c.get("idm", "both"), why)   # inducement-count size (idm_m; absent = unchanged)
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
        loss_d = (risk + TW_DLL_SLIP) * PV + COMM                 # 2 ticks of stop slippage (2026-10-18)
        caps.append((int(max(0.0, float(A["dll"]) + cum) / loss_d), f"soft daily loss ${float(A['dll']):,.0f}"))
    for cap, lab in caps:
        if cap < q:
            q = max(1, cap)
            note(f"{lab} -> {q}")
    return int(min(q, maxq))


def scale_in_qty(q_base: int, q_full: int, risk_pts: float, adds: list, f=1.0, state: dict | None = None,
                 room_f: float = 0.6, dll: float = TW_50K["dll"], max_micros: int = 40) -> list:
    """Micros for each add of a scaled-in LIT trade (engine/lit.py option "scale_in", research/writeups/lit-big-ideas.md;
    off by default). q_base = the micros of the first entry, q_full = the micros the sizing gave before any start multiplier
    (= q_base normally), risk_pts = the first entry's stop distance. adds = the trade's adds in order, each {"rk": the add's
    stop distance at its fill (pts), "prev_rk": [the open risk pts of every earlier add at that moment]}.
    Each add wants int(f x q_full) micros (f "max" = as many as the budget allows) and gets at most what keeps the open risk
    of all adds (a full stop-out incl. 1 tick + commission) inside the budget = the first entry's $ risk (q_full x stop x $2),
    and with an eval state also inside room_f x the room to the trailing floor and the soft daily loss left today
    (dll + state["cum"]); the whole position never above max_micros. 0 = that add is skipped."""
    PV, COMM, SLIP = TW_PV, TW_COMM, TW_SLIP
    budget = float(q_full) * float(risk_pts) * PV
    if state is not None:
        if _num(state.get("room")) is not None:
            budget = min(budget, float(room_f) * max(0.0, float(state["room"])))
        budget = min(budget, float(dll) + float(_num(state.get("cum"), 0.0)))
    tot = int(q_base)
    out: list = []
    for a in adds or []:
        per = (float(a["rk"]) + SLIP) * PV + COMM
        open_r = sum(qq * float(rk) * PV for qq, rk in zip(out, a.get("prev_rk") or []))
        cap = int(max(0.0, budget - open_r) / per) if per > 0 else 0
        want = cap if f == "max" else int(float(f) * q_full + 1e-9)
        n = max(0, min(want, cap, int(max_micros) - tot))
        out.append(n)
        tot += n
    return out


def eval_state(day_pnl: dict, today_cum: float = 0.0, plan: dict | None = None, session: int | None = None,
               today: str | None = None) -> dict:
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
    out = {"profit": round(bal, 2), "cum": float(today_cum), "room": round(bal + today_cum - floor, 2),
           "session": int(session) if session is not None else len(day_pnl) + 1, "n_today": 0,
           "days_traded": sum(1 for v in day_pnl.values() if abs(float(v)) > 1e-9)}   # earlier sessions with a closed trade
    if today:
        # this calendar (ISO) week's closed eval P&L incl. today (lit_sizing "wk_loss_usd"); only when today is given
        out["wk_pnl"] = round(eval_week_pnl(day_pnl, today, today_cum), 2)
    return out


def eval_week_pnl(day_pnl: dict, today: str, today_cum: float = 0.0) -> float:
    """The eval's closed P&L of today's ISO calendar week: the earlier sessions of that week in day_pnl (yyyy-mm-dd keys)
    + today's closed P&L."""
    try:
        wk = _dt.date.fromisoformat(str(today)[:10]).isocalendar()[:2]
    except ValueError:
        return float(today_cum)
    s = float(today_cum)
    for d, v in (day_pnl or {}).items():
        try:
            if str(d)[:10] < str(today)[:10] and _dt.date.fromisoformat(str(d)[:10]).isocalendar()[:2] == wk:
                s += float(v)
        except ValueError:
            continue
    return s


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
    days = {d: float(v) for d, v in (day_pnl or {}).items() if not start or d >= str(start) or d == "0000-00-00"}   # + the prior P&L
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
    # owner 2026-10-18: no reset (one-time fee, no monthly cost): an open eval just keeps going; "reset" stays False
    reset = False
    if status == "open":
        to_go = max(0.0, float(A["target"]) - bal)
        text = (f"session {sess} of {EVAL_SESSIONS}, {max(0, EVAL_SESSIONS - done)} left, ${to_go:,.0f} to go" if done < EVAL_SESSIONS
                else f"session {sess}, ${to_go:,.0f} to go")
    elif status == "not started":
        text = "not started yet"
    elif status == "unknown":
        text = "eval start unknown (lit_sizing.eval_start)"
    else:
        text = f"eval {status} in {sess} sessions: buy the next one and set lit_sizing.eval_start"
    return {"start": start, "session": sess, "sessions_done": done, "limit": EVAL_SESSIONS, "status": status,
            "profit": round(bal, 2), "room": st["room"], "to_target": round(float(A["target"]) - bal, 2),
            "reset": bool(reset), "text": text}


# ------------------------------------------------------------------------------------------------ LIT funded (after the eval)
# lit_sizing mode "funded" (2026-10-18, research/writeups/lit-funded-sizing.md, tools/lit_funded.py): the MFFU Builder 50K
# funded / sim-funded account, where the goal is payouts without losing the account. Same floor rule as the eval (EOD high
# - $2,000, locked at start + $100), $1,000 soft daily loss; payouts need balance - $2,100 buffer >= $500 (max $2,000 a
# request, best day <= 50% of the cycle's profit, 5 sim payouts, 80% split). cfg = lit_sizing["funded"] (every $ x acct scale):
#   tiers      [[cushion_from, usd], ...]: $ risk by the room to the floor (the last tier whose cushion_from <= room)
#   pre_lock_usd   None | $ risk while the floor has not locked yet (min with the tier)
#   pct        None | $ risk = pct x room (fractional Kelly on the room), clamped to [pct_min_usd, pct_max_usd]; replaces tiers
#   ref        20: size follows the stop: usd up to a ref-pt stop, then usd x ref / stop (the LIT rule)
#   wk         True: x the weekly stop's multiplier (trade["size_mult"])
#   room_f     0.6 | None: a full stop-out (stop + slip_ticks, commission) <= room_f x room
#   dll_cap    True: a full stop-out may not take the day below -dll
#   max_win    None | $: the target's $ may not exceed this (keeps the best day small for the 50% payout rule)
#   slip_ticks 2: ticks of slippage assumed on the stop in every cap
#   skip_breach True: when even 1 micro's full stop-out would reach the floor or the soft daily loss -> 0 (skip). The soft caps
#              (room_f, max_win) never go below 1 micro.
# state = {"room": balance + today's closed P&L - trailing floor ($), "cum": today's closed P&L, "locked": floor at the lock}
FD_50K = {"mll": 2000.0, "lock": 100.0, "dll": 1000.0, "buffer": 2100.0, "pay_min": 500.0, "pay_max": 2000.0, "split": 0.8,
          "cons": 0.5, "cycle_days": 2, "first_wait": 2, "max_payouts": 5, "max_micros": 40, "scale": 1.0}
FD_DEFAULT = {"tiers": [[0.0, 800.0]], "pre_lock_usd": None, "pct": None, "pct_min_usd": 100.0, "pct_max_usd": 1000.0,
              "ref": 20.0, "wk": True, "room_f": 0.6, "dll_cap": True, "max_win": None, "slip_ticks": 2, "skip_breach": True}


def funded_qty(trade: dict, state: dict | None, cfg: dict | None = None, acct: dict | None = None, why: list | None = None) -> int:
    """Micros for one LIT entry on a funded account. 0 = no trade (stop distance unknown, or even 1 micro could breach)."""
    c = {**FD_DEFAULT, **(cfg or {})}
    A = {**FD_50K, **(acct or {})}
    sc = float(A.get("scale", 1.0))
    note = (lambda s: why.append(s)) if why is not None else (lambda s: None)
    risk = _num(trade.get("risk_pts", trade.get("risk")))
    if risk is None and trade.get("entry") is not None and trade.get("stop0", trade.get("stop")) is not None:
        risk = abs(float(trade["entry"]) - float(trade.get("stop0", trade.get("stop"))))
    if not risk or risk <= 0:
        note("stop distance unknown: no trade")
        return 0
    tgt = _num(trade.get("tgt_pts", trade.get("tgt")))
    if tgt is None and trade.get("entry") is not None and trade.get("target") is not None:
        tgt = abs(float(trade["target"]) - float(trade["entry"]))
    st = state or {}
    room = _num(st.get("room"))
    cum = float(_num(st.get("cum"), 0.0))
    locked = bool(st.get("locked"))
    tiers = sorted((float(a) * sc, float(u) * sc) for a, u in (c["tiers"] or [[0.0, 800.0]]))
    if room is None:                                   # unknown room: the smallest tier, no room cap (reason logged)
        usd = tiers[0][1] if c["pct"] is None else float(c["pct_min_usd"]) * sc
        note(f"room to the floor unknown: smallest size ${usd:,.0f}")
    elif c["pct"] is not None:
        usd = min(max(float(c["pct"]) * max(0.0, room), float(c["pct_min_usd"]) * sc), float(c["pct_max_usd"]) * sc)
        note(f"{float(c['pct']) * 100:g}% of ${room:,.0f} room -> ${usd:,.0f}")
    else:
        usd = tiers[0][1]
        for a, u in tiers:
            if room >= a:
                usd = u
        if c["pre_lock_usd"] is not None and not locked and usd > float(c["pre_lock_usd"]) * sc:
            usd = float(c["pre_lock_usd"]) * sc
            note(f"floor not locked yet: ${usd:,.0f}")
        note(f"${usd:,.0f} at ${room:,.0f} room")
    ref = float(c["ref"] or 0)
    r = usd if not ref or risk <= ref else usd * ref / risk
    q = max(1, int(r / (risk * TW_PV) + 1e-9))
    if c["wk"]:
        m = _num(trade.get("size_mult", trade.get("wk_m")), 1.0)
        if m < 1:
            q = max(1, int(q * m + 1e-9))
            note(f"weekly stop x{m:g} -> {q}")
    q = idm_apply(q, trade, risk, int(A["max_micros"]), c.get("idm", "both"), why)   # inducement-count size (absent = unchanged)
    loss1 = (risk + 0.25 * float(c["slip_ticks"])) * TW_PV + TW_COMM        # a full stop-out of 1 micro, $
    if c["max_win"] and tgt and tgt * TW_PV - TW_COMM > 0:
        cap = int(float(c["max_win"]) * sc / (tgt * TW_PV - TW_COMM))
        if cap < q:
            q = max(1, cap)
            note(f"best day <= ${float(c['max_win']) * sc:,.0f} -> {q}")
    if c["room_f"] and room is not None:
        cap = int(float(c["room_f"]) * max(0.0, room) / loss1)
        if cap < q:
            q = max(1, cap)
            note(f"{float(c['room_f']) * 100:.0f}% of ${room:,.0f} room -> {q}")
    hard = []                                          # never past these (the account rules), stop + slip + commission
    if room is not None:
        hard.append((room, f"${room:,.0f} room to the floor"))
    if c["dll_cap"]:
        hard.append((float(A["dll"]) * sc + cum, f"soft daily loss ${float(A['dll']) * sc:,.0f}"))
    for lim, lab in hard:
        cap = int(max(0.0, lim) / loss1 - 1e-9) if lim > loss1 else 0
        if lim <= loss1 and c["skip_breach"]:
            note(f"1 micro's stop-out ${loss1:,.0f} would reach the {lab}: no trade")
            return 0
        if cap < q:
            q = max(1, cap)
            note(f"{lab} -> {q}")
    return int(min(q, int(A["max_micros"])))


def funded_state(day_pnl: dict, today_cum: float = 0.0, payouts: dict | None = None, plan: dict | None = None) -> dict:
    """state for funded_qty from the funded account's closed P&L per earlier day + today's closed P&L. payouts = {day: $
    withdrawn at that day's end}: they lower the balance, never the floor (the floor only moves up and locks at start + lock)."""
    A = {**FD_50K, **(plan or {})}
    bal = peak = 0.0
    floor = -float(A["mll"])
    pay = payouts or {}
    for d in sorted(set(day_pnl) | set(pay)):
        bal += float(day_pnl.get(d, 0.0))
        peak = max(peak, bal)
        floor = min(max(floor, peak - float(A["mll"])), float(A["lock"]))
        bal -= float(pay.get(d, 0.0))
    return {"balance": round(bal, 2), "cum": float(today_cum), "room": round(bal + today_cum - floor, 2),
            "floor": round(floor, 2), "locked": floor >= float(A["lock"]) - 1e-9}


def selftest() -> bool:
    t_late ={"dir": 1, "m15_trend": 1, "risk_pts": 44.0}
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
    assert fresh == {"profit": 0.0, "cum": 0.0, "room": 2000.0, "session": 1, "n_today": 0, "days_traded": 0}, fresh
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
    ck = eval_clock({"2026-10-20": 500.0}, "2026-10-19", "2026-10-30", session_over=True)
    assert not ck["reset"] and ck["text"] == "session 10, $2,500 to go", ck                 # no reset (owner 2026-10-18)
    ck = eval_clock({"2026-10-20": 500.0}, "2026-10-19", "2026-11-02")
    assert not ck["reset"] and ck["status"] == "open" and ck["text"] == "session 11, $2,500 to go", ck
    assert eval_clock({"2026-10-20": 3100.0}, "2026-10-19", "2026-11-02")["status"] == "passed"
    assert eval_clock({"2026-10-20": -2000.0}, "2026-10-19", "2026-10-21")["status"] == "failed"
    assert eval_clock({}, "2026-10-19", "2026-10-18")["status"] == "not started"
    assert eval_clock({"2026-10-16": -900.0}, "2026-10-19", "2026-10-19")["room"] == 2000.0   # days before the start ignored
    # ---- the day guard (opt-in lit_sizing.guard; off = the old sizing exactly)
    G = {**C, "guard": {}}
    assert lit_qty(3, {"risk_pts": 40.0, "tgt_pts": 200.0}, G, state=fresh)["qty"] == 8                 # nothing binds
    r = lit_qty(3, {"risk_pts": 40.0, "tgt_pts": 200.0}, G, state={**fresh, "n_today": 1})
    assert r["qty"] == 0 and "already routed today" in r["guard"], r                                   # 1 trade a day
    r = lit_qty(3, {"risk_pts": 44.0}, {"mode": "eval", "guard": {}}, room=2000.0, state={"profit": 3050.0, "cum": 0.0, "room": 2000.0})
    assert r["qty"] == 0 and "target" in r["guard"], r                                                 # eval passed: stop
    assert lit_qty(3, {"risk_pts": 44.0}, {"mode": "normal", "guard": {}}, state={"profit": 3050.0, "cum": 0.0})["qty"] == 3  # not an eval mode
    # min 1 micro vs the floor: safe_eval at $50 room, 47-pt stop: old rule 1 micro (a $96 stop-out breaks the floor)
    assert lit_qty(3, lt, {"mode": "safe_eval"}, room=50.0)["qty"] == 1
    r = lit_qty(3, lt, {"mode": "safe_eval", "guard": {}}, room=50.0)
    assert r["qty"] == 0 and "would reach" in r["guard"], r
    assert lit_qty(3, lt, {"mode": "safe_eval", "guard": {"breach": "one"}}, room=50.0)["qty"] == 1
    # an 88-pt widened stop with 2 ticks: 1 micro = (88 + 0.5) x 2 + 1.40 = $178.40; room $500 -> 2 (3 x 178.4 = 535 > 500)
    assert lit_qty(9, {"risk_pts": 88.0}, {"mode": "normal", "guard": {}}, room=500.0)["qty"] == 2
    # an estimated stop (1m CISD close) is padded 2 pts: 40 + 2 + 0.5 = 42.5 x 2 + 1.4 = $86.40; room $300 -> 3 (not 3.6)
    assert lit_qty(9, {"risk_pts": 40.0, "est": True}, {"mode": "normal", "guard": {}}, room=300.0)["qty"] == 3
    assert lit_qty(9, {"risk_pts": 40.0}, {"mode": "normal", "guard": {}}, room=300.0)["qty"] == 3      # 300 / 82.4 = 3.6 -> 3
    # the soft daily loss with today's loss: day -$900 -> $100 left, 1 micro of a 40-pt stop = $82.40 -> 1
    assert lit_qty(9, {"risk_pts": 40.0}, {"mode": "normal", "guard": {}}, state={"cum": -900.0, "room": 5000.0})["qty"] == 1
    # max 40 micros even if the mode said more
    assert lit_qty(60, {"risk_pts": 5.0}, {"mode": "normal", "guard": {}}, max_micros=60, room=1e6)["qty"] == 40
    # ---- funded (lit_sizing mode "funded")
    FC = {"mode": "funded", "funded": {"pct": 0.4, "pct_min_usd": 100, "pct_max_usd": 800, "ref": 20, "room_f": None, "max_win": 1500}}
    f0 = funded_state({})
    assert f0 == {"balance": 0.0, "cum": 0.0, "room": 2000.0, "floor": -2000.0, "locked": False}, f0
    # fresh: 40% of $2,000 = $800, 40-pt stop -> 800 x 20/40 = 400 / 80 = 5 micros; target 200 pts: 1500 / 398.6 = 3 -> 3
    r = lit_qty(3, {"risk_pts": 40.0, "tgt_pts": 200.0}, FC, state=f0)
    assert r["qty"] == 3 and any("best day" in w for w in r["reasons"]), r
    assert lit_qty(3, {"risk_pts": 40.0, "tgt_pts": 60.0}, FC, state=f0)["qty"] == 5
    # after -$1,500: room $500 -> $200 -> 200 x 20/40 / 80 = 1 micro
    s1 = funded_state({"d1": -1500.0})
    assert s1["room"] == 500.0 and lit_qty(3, {"risk_pts": 40.0, "tgt_pts": 60.0}, FC, state=s1)["qty"] == 1
    # room below 1 micro's worst case: skip (never lose the funded account on a 1-micro trade)
    r = lit_qty(3, {"risk_pts": 60.0, "tgt_pts": 120.0}, FC, state={"room": 100.0, "cum": 0.0, "locked": True})
    assert r["qty"] == 0, r
    # payouts lower the balance, never the floor: +$4,500 then a $2,000 payout -> floor locked at +$100, room $2,400
    s2 = funded_state({"d1": 2500.0, "d2": 2000.0}, payouts={"d2": 2000.0})
    assert s2["locked"] and s2["floor"] == 100.0 and s2["room"] == 2400.0, s2
    # state unknown: the smallest size, fallback said
    r = lit_qty(3, {"risk_pts": 40.0, "tgt_pts": 60.0}, FC)
    assert r["qty"] == 1 and "state unknown" in r["fallback"], r                  # $100 -> 100 x 0.5 / 80 = 0.6 -> 1
    # tiers by the floor's lock
    TC = {"mode": "funded", "funded": {"tiers": [[0, 800]], "pre_lock_usd": 400, "room_f": None}}
    assert lit_qty(3, {"risk_pts": 20.0}, TC, state=f0)["qty"] == 10 and lit_qty(3, {"risk_pts": 20.0}, TC, state=s2)["qty"] == 20
    # ---- minimum-days trade, session switch, auto (2026-10-18)
    won = {"profit": 3100.0, "cum": 0.0, "room": 2000.0, "session": 3, "n_today": 0}
    r = lit_qty(3, {"risk_pts": 40.0, "tgt_pts": 200.0}, C, state={**won, "days_traded": 1})
    assert r["qty"] == 1 and any("minimum-days trade" in w for w in r["reasons"]), r
    assert lit_qty(3, {"risk_pts": 40.0, "tgt_pts": 200.0}, C, state={**won, "days_traded": 2})["qty"] == 0     # once only
    assert lit_qty(3, {"risk_pts": 40.0, "tgt_pts": 200.0}, C, state={**won, "cum": 50.0, "days_traded": 1})["qty"] == 0  # same day
    U = {**C, "two_week_until": 10, "after_mode": "eval"}
    assert lit_qty(3, {"risk_pts": 44.0, "tgt_pts": 100.0}, U, room=2000.0, state={**fresh, "session": 10})["qty"] == 11   # 16 -> room 13 -> dll 1000 / 90.9 = 11
    r = lit_qty(3, {"risk_pts": 44.0, "tgt_pts": 100.0}, U, room=2000.0, state={**fresh, "session": 11})
    assert r["qty"] == 5 and "eval sizing" in r["reasons"][0], r                        # $800 up to 25 pts: 5 micros
    AU = {**U, "mode": "auto", "funded": FC["funded"]}
    assert lit_qty(3, {"risk_pts": 40.0, "tgt_pts": 200.0}, AU, room=2000.0, state=fresh)["qty"] == 8        # eval: two_week
    r = lit_qty(3, {"risk_pts": 40.0, "tgt_pts": 200.0}, AU, state={**won, "days_traded": 2, "funded": f0})
    assert r["qty"] == 3 and "auto: eval passed -> funded sizing" in r["reasons"], r                         # funded rules
    assert lit_qty(3, {"risk_pts": 40.0, "tgt_pts": 200.0}, AU, state={**won, "days_traded": 1, "funded": f0})["qty"] == 1
    es = eval_state({"a": 3100.0, "b": 0.0}, 0.0, session=3)
    assert es["days_traded"] == 1 and lit_qty(3, {"risk_pts": 40.0, "tgt_pts": 200.0}, C, state=es)["qty"] == 1   # min-days trade
    assert eval_state({"a": 2000.0, "b": 0.0, "c": 1100.0}, 0.0)["days_traded"] == 2
    # ---- inducement-count size (engine/lit.py idm_size: idm_m / idm_cap / wk_m on the trade; absent = the old sizing)
    UP, DN = {"idm_m": 1.5, "idm_cap": 990.0, "wk_m": 1.0, "size_mult": 1.5}, {"idm_m": 0.75, "idm_cap": 990.0, "wk_m": 1.0, "size_mult": 0.75}
    t40 = {"risk_pts": 40.0, "tgt_pts": 200.0}
    assert lit_qty(3, {**t40, **UP}, C, state=fresh)["qty"] == 12        # 8 x 1.5 = 12; cap 990 / 82.4 = 12; dll 12
    assert lit_qty(3, {**t40, **DN}, C, state=fresh)["qty"] == 6         # 8 x 0.75 = 6
    r = lit_qty(3, {**t40, **UP}, C, state=fresh)
    assert any("inducements taken first x1.5" in w for w in r["reasons"]), r
    assert lit_qty(3, {**t40, **UP}, {**C, "idm": "cut"}, state=fresh)["qty"] == 8     # cut only: the size-up is ignored
    assert lit_qty(3, {**t40, **DN}, {**C, "idm": "cut"}, state=fresh)["qty"] == 6
    assert lit_qty(3, {**t40, **DN}, {**C, "idm": "off"}, state=fresh)["qty"] == 8
    # a size-up never passes the eval caps: 1.5R target wants 26, x1.5 = 39 -> $990 cap 12, room 15, dll 12 -> 12
    assert lit_qty(3, {"risk_pts": 40.0, "tgt_pts": 60.0, **UP}, C, state=fresh)["qty"] == 12
    assert lit_qty(3, {"risk_pts": 40.0, "tgt_pts": 60.0, **UP}, C, state=st)["qty"] == 7    # after -$1,000: 60% room 7
    t20 = {"risk_pts": 20.0, "tgt_pts": 200.0}                            # need 8; $400 cap: 400 / 42.4 = 9; $200 cap: never < 8
    assert lit_qty(3, {**t20, **UP, "idm_cap": 400.0}, C, state=fresh)["qty"] == 9
    assert lit_qty(3, {**t20, **UP, "idm_cap": 200.0}, C, state=fresh)["qty"] == 8
    # the weekly part (wk_m) still works with two_week wk on, and size_mult (the product) is not double-counted
    CW = {**C, "two_week": {**C["two_week"], "wk": True}}
    assert lit_qty(3, {**t40, **DN, "wk_m": 0.5, "size_mult": 0.375}, CW, state=fresh)["qty"] == 3      # 8 -> 4 -> 3
    assert lit_qty(3, {**t40, "size_mult": 0.5}, CW, state=fresh)["qty"] == 4                          # no idm_m: old rule
    # eval: 44-pt stop -> 5 micros; x1.5 = 7 (cap 990 / 90.4 = 10, room 13); x0.75 = 3; fast_eval 47-pt: 7 -> 10 (cap 10)
    assert lit_qty(3, {"risk_pts": 44.0, **UP}, {"mode": "eval"}, room=2000.0)["qty"] == 7
    assert lit_qty(3, {"risk_pts": 44.0, **DN}, {"mode": "eval"}, room=2000.0)["qty"] == 3
    assert lit_qty(3, {"risk_pts": 44.0, **UP}, {"mode": "eval"}, room=300.0)["qty"] == 2              # 60% room still caps
    assert lit_qty(3, {"risk_pts": 47.0, **UP}, {"mode": "fast_eval"})["qty"] == 10
    # funded: 40-pt stop, 60-pt target -> 5; x0.75 = 3; x1.5 = 7 (cap 12, dll 12)
    assert lit_qty(3, {"risk_pts": 40.0, "tgt_pts": 60.0, **DN}, FC, state=f0)["qty"] == 3
    assert lit_qty(3, {"risk_pts": 40.0, "tgt_pts": 60.0, **UP}, FC, state=f0)["qty"] == 7
    # normal / safe_eval: the model's micros already carry it
    assert lit_qty(6, {"risk_pts": 40.0, **UP}, {"mode": "normal"})["qty"] == 6
    assert lit_qty(6, {"risk_pts": 40.0, **UP}, {"mode": "safe_eval"}, room=300.0)["qty"] == 2          # 180 / 80
    # absent / None / 1x: unchanged
    assert lit_qty(3, {**t40, "idm_m": None}, C, state=fresh)["qty"] == 8 and lit_qty(3, {**t40, "idm_m": 1.0}, C, state=fresh)["qty"] == 8
    assert idm_apply(5, {"risk_pts": 40.0}, 40.0) == 5 and idm_apply(5, {"idm_m": 0.5}, 40.0) == 2 and idm_apply(1, {"idm_m": 0.5}, 40.0) == 1
    print("sizing selftest OK")
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if selftest() else 1)
