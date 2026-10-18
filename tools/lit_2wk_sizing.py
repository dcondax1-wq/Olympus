"""Two-week eval sizing for LIT (owner order 2026-10-18: an MFFU eval must be passed within 10 sessions). Research:
tools/lit_2wk.py, research/writeups/lit-two-week-eval.md.

two_week_qty() is self-contained (no imports from the repo) so the coordinator can move it into engine/sizing.py as the
lit_sizing mode "two_week" (lit_qty: `if mode == "two_week": return two_week_qty(trade, state, cfg)`).

Config (live_model.json "lit_sizing", mode "two_week"; every $ figure is for the 50K and is multiplied by acct["scale"]):
  base       "need" (default) = one winner passes: micros so the trade's target $ covers what is still needed to the eval
             target, ceil(need x need_buf / (target pts x $2 - $1.40)) | "lit" = $usd up to a ref-pt stop, then usd x ref / stop
  need_buf   1.0
  usd, ref   800, 25 (base "lit" only)
  max_usd    None | $ cap of a full stop-out per trade (stop + 1 tick, commission in)
  wk         True = times the weekly stop's multiplier (trade["size_mult"], half after 2 stop-outs in the week)
  press_at, press_mult, press_room    from eval session press_at on (not passed yet): micros x press_mult (before the caps)
                                      and the room cap at press_room instead of room_f (None = unchanged)
  protect_over, protect_keep    once the eval profit is >= protect_over, a full stop-out may not take the profit below
                                protect_keep x profit
  room_f     0.6 | None: micros <= room_f x room / (stop x $2), room = balance - trailing max-loss floor (as today's safe cap)
  dll_cap    True: a full stop-out (stop + 1 tick, commission) may not take the day below -dll (the MFFU soft daily loss)
  stop_at_target  True: no new trade once the day's P&L already reaches the eval target (never risk the pass)
Always: at least 1 micro (the room / daily caps never go below 1), at most max_micros.

state = {"profit": eval profit at the start of the day ($, vs the start balance), "cum": today's closed P&L ($),
         "room": balance + cum - trailing floor ($), "session": eval session number (1 = first day), "n_today": trades so far}
trade = {"risk_pts" | "risk": stop distance at entry (pts), "tgt_pts" | "tgt" | (entry, target): target distance (pts),
         "size_mult" | "wk_m": weekly-stop multiplier}
"""
from __future__ import annotations

import math

PV, COMM, SLIP = 2.0, 1.40, 0.25
MFFU_50K = {"target": 3000.0, "mll": 2000.0, "lock": 100.0, "dll": 1000.0, "max_micros": 40, "scale": 1.0}
MFFU_25K = {"target": 1500.0, "mll": 1000.0, "lock": 100.0, "dll": 600.0, "max_micros": 20, "scale": 0.5}
DEFAULT = {"base": "need", "need_buf": 1.0, "usd": 800.0, "ref": 25.0, "max_usd": None, "wk": True,
           "press_at": None, "press_mult": 1.0, "press_room": None, "protect_over": None, "protect_keep": 0.0,
           "room_f": 0.6, "dll_cap": True, "stop_at_target": True}


def _num(x, d=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def two_week_qty(trade: dict, state: dict, cfg: dict | None = None, acct: dict | None = None, why: list | None = None) -> int:
    """Micros for one LIT entry in a two-week eval. 0 = no trade (only when the day already reached the target)."""
    c = {**DEFAULT, **(cfg or {})}
    A = {**MFFU_50K, **(acct or {})}
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


# ------------------------------------------------------------------------------------------------ live adapter
def eval_state(day_pnl: dict, today_cum: float = 0.0, plan: dict | None = None) -> dict:
    """state for two_week_qty from the eval's closed P&L per session since the eval started (every session, 0 on days without a
    trade; sorted keys) + today's closed P&L. Same floor rule as engine/sizing.mffu_eval: EOD high - max loss, locked at
    start + lock."""
    A = {**MFFU_50K, **(plan or {})}
    bal = peak = 0.0
    floor = -float(A["mll"])
    for d in sorted(day_pnl):
        bal += float(day_pnl[d])
        peak = max(peak, bal)
        floor = min(max(floor, peak - float(A["mll"])), float(A["lock"]))
    return {"profit": round(bal, 2), "cum": float(today_cum), "room": round(bal + today_cum - floor, 2),
            "session": len(day_pnl) + 1, "n_today": 0}
