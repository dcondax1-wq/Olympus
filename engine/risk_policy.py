"""Risk manager for the MFFU Builder 50K evaluation: how many MNQ micros to trade on a setup.

Generic and live-ready. `size()` is a pure function of its arguments: no I/O, no clock, no randomness, no module
state. The same inputs always give the same answer, and every answer carries a plain-English reason. It works for
any model's setups (graded or not) and any micro contract (MNQ by default, `point_value=5.0` for MES).

CALL SIGNATURE
    size(setup_grade, stop_pts, account_state, day_state, cfg=None, plan_r=None, point_value=None) -> dict

    setup_grade    "A+", "A", "B", "C", "D", "SKIP" or None/"" (ungraded). Case-insensitive.
                   Tier map (cfg["grade_map"]): A+/A -> A, B -> B, C/D -> C, SKIP -> no trade, None/unknown -> B.
                   With tiers off (flat policies) the grade is ignored.
    stop_pts       distance from the expected fill to the stop, in index points (> 0). Include the entry slippage
                   you expect (strategy_lab modules: |entry - stop| + 1 tick).
    account_state  dict, eval account as of now:
                     balance       float  current balance incl. today's closed P&L        (required)
                     mll           float  trailing max-loss level in force today           (required)
                     sod_balance   float  balance at the start of today (last EOD)         (default: balance)
                     peak_eod      float  highest end-of-day balance so far               (default: max(balance, start))
                     locked        bool   MLL locked at $50,100                            (informational)
                     days_traded   int    days with at least one trade                     (informational)
                     last_day_pnl  float  P&L of the most recent day that had trades       (default: 0)
                     loss_streak   int    consecutive losing trading days                  (informational)
                     start         float  eval start balance                               (default: 50,000)
                     target        float  profit target                                    (default: 3,000)
                     dll           float  daily loss limit                                 (default: 1,000)
    day_state      dict, today so far:
                     pnl     float  today's closed P&L ($)          (default 0)
                     trades  int    trades taken today              (default 0)
                     wins    int    winners today (pnl > 0)         (default 0)
                     losses  int    losers today (pnl < 0)          (default 0)
                     halted  bool   daily loss limit was hit        (default False)
    cfg            a POLICIES entry or any dict of DEFAULTS keys (missing keys fall back to DEFAULTS).
                   None -> POLICIES["RECOMMENDED"].
    plan_r         optional planned reward:risk of the setup (logged only; no preset uses it).
    point_value    optional $ per point per micro, overrides cfg (MNQ 2.0, MES 5.0).

    returns {"qty_micros": int, "risk_usd": float (qty x stop x $/pt), "worst_case_usd": float (incl. slippage and
             commission), "reason": str, "code": str, "tier": str,
             "contracts": {"minis": int, "micros": int}}   # the same size routed as 1 mini per 10 micros
                                                            # (1 NQ costs ~$4.50 round trip vs ~$14 for 10 MNQ)
    code: "ok" | "done" (target reached / account at MLL) | "day_rule" | "skip_grade" | "bad_stop" |
          "too_wide" (stop too wide for 1 micro at the budget) | "guard" (1 micro could reach the MLL or daily limit)

    EvalAccount (below) builds both dicts and applies the eval rules after each trade and at each session close;
    account_dead() tells when an account can no longer carry 1 micro of a normal setup (treat as failed / reset).

    from engine.risk_policy import EvalAccount, POLICIES, account_dead, size
    acct = EvalAccount()
    d = size("B", 42.0, acct.account_state(), acct.day_state())        # RECOMMENDED policy
    acct.record_trade(pnl_usd, worst_open_pnl_usd)                      # after each closed trade
    acct.end_of_day()                                                   # after the session close (trails the MLL)
    dead, why = account_dead(acct.account_state(), typical_stop=44.0)   # True -> stop and reset the eval

    RECOMMENDED (research/lab/RISK_REPORT.md): flat $350 per setup whatever its grade, never more than 35% of the
    cushion (balance - MLL), hard MLL / daily-limit guards, max 2 trades a day, stop after a winner, stop after 2
    losers or -$700 on the day.

Eval rules (engine/analytics.py PLANS["builder_50k"]): start $50,000, pass at +$3,000, trailing max loss $2,000
measured on end-of-day balances that locks at $50,100, daily loss limit $1,000 (soft: the day stops), max 4 minis /
40 micros. 1 NQ = $20/pt, 1 MNQ = $2/pt (10 MNQ = 1 NQ).

Policies (all share the same day rules and contract math; see POLICIES at the bottom):
  P0 flat $350 a trade.
  P1 confidence tiers: A = $700 budget, at most 10 MNQ (1 NQ only when stop x $20 <= $700); B = $350; C = $175.
  P2 cushion-aware: budget = min(tier budget, k x (balance - MLL)).
  P3 anti-martingale: after a losing day, cut the budget until a new end-of-day equity high (or the next winning day).
  P4 eval sprint, inside $1,000 of the target: "protect" caps the budget at $175; "finish" sizes so 1-2 winners at
     1.5R complete the target, if the cushion allows.
  P5 combinations.
Hard guards (on for every policy except the raw P0/P1 baselines): a full stop-out, plus slippage and commission, may
never reach the trailing MLL or the $1,000 daily limit.
"""
from __future__ import annotations

import math

MNQ_PV = 2.0      # $ per point, one MNQ
NQ_PV = 20.0      # $ per point, one NQ
TICK = 0.25

PLAN = {"start": 50000.0, "target": 3000.0, "mll": 2000.0, "lock": 50100.0, "dll": 1000.0, "max_micros": 40,
        "min_days": 1}

DEFAULTS = {
    "name": "custom",
    "point_value": MNQ_PV,          # $ per point per micro contract (MES would be 5.0)
    # base budget
    "flat_risk": 350.0,
    "tiers": False,                 # True = budget by setup grade (P1)
    "tier_risk": {"A": 700.0, "B": 350.0, "C": 175.0},
    "tier_max_micros": {"A": 10, "B": 40, "C": 40},
    "grade_map": {"A+": "A", "A": "A", "B": "B", "C": "C", "D": "C", "SKIP": "SKIP"},
    "default_grade": "B",           # ungraded or unknown grades are B
    # P2 cushion
    "cushion_k": None,              # e.g. 0.25 -> budget <= 0.25 x (balance - MLL)
    # P3 anti-martingale
    "dd_cut": None,                 # e.g. 0.5 -> budget x 0.5 after a losing day
    "dd_restore": "high",           # "high": until a new end-of-day equity high; "win": until a winning day
    # P4 sprint (inside sprint_zone of the target)
    "sprint": None,                 # None | "protect" | "finish"
    "sprint_zone": 1000.0,
    "protect_risk": 175.0,
    "finish_trades": 2,             # size so this many winners finish the target
    "finish_win_r": 1.5,            # what one winner is assumed to pay, in R
    "finish_k": 0.35,               # ... but never budget more than this share of the cushion
    # hard guards
    "guard": True,
    "guard_slip_pts": 1.0,          # extra adverse points assumed beyond the stop (entry + exit slippage, fast tape)
    "comm_rt": 1.40,                # round-trip commission per micro
    "guard_buffer": 25.0,           # $ left above the MLL / daily limit after a worst-case stop-out
    # day rules
    "max_trades_day": 2,
    "stop_after_win": True,
    "max_losses_day": 2,
    "day_stop": 700.0,              # stop for the day once the day's P&L is <= -$700
    # contract limit
    "max_micros": 40,
}


def _fmt(x: float) -> str:
    return f"${x:,.0f}"


def _no(code: str, reason: str, tier: str = "-") -> dict:
    return {"qty_micros": 0, "risk_usd": 0.0, "worst_case_usd": 0.0, "reason": reason, "code": code, "tier": tier,
            "contracts": {"minis": 0, "micros": 0}}


def _resolve(cfg):
    if cfg is None:
        return POLICIES["RECOMMENDED"]
    if not DEFAULTS.keys() <= cfg.keys():
        return {**DEFAULTS, **cfg}
    return cfg


def tier_of(setup_grade, cfg: dict | None = None) -> str:
    """'A' / 'B' / 'C' / 'SKIP' for a raw grade; None, '' and unknown grades -> the default grade (B)."""
    c = _resolve(cfg)
    if setup_grade is None or str(setup_grade).strip() == "":
        return c["grade_map"].get(c["default_grade"], c["default_grade"])
    return c["grade_map"].get(str(setup_grade).strip().upper(), c["default_grade"])


def size(setup_grade, stop_pts: float, account_state: dict, day_state: dict, cfg: dict | None = None,
         plan_r: float | None = None, point_value: float | None = None) -> dict:
    """How many micros to trade on one setup. See the module docstring for the exact keys."""
    c = _resolve(cfg)
    a, d = account_state, day_state
    pv = float(point_value or c["point_value"])
    start = a.get("start", PLAN["start"])
    target = a.get("target", PLAN["target"])
    dll = a.get("dll", PLAN["dll"])
    bal, mll = float(a["balance"]), float(a["mll"])
    d_pnl = d.get("pnl", 0.0)
    d_trades, d_wins, d_losses = d.get("trades", 0), d.get("wins", 0), d.get("losses", 0)
    profit = bal - start
    cushion = bal - mll

    # 0. eval status
    if bal <= mll:
        return _no("done", f"Account at the max-loss level ({_fmt(bal)} vs MLL {_fmt(mll)}): no trading.")
    if profit >= target:
        return _no("done", f"Profit target reached (+{_fmt(profit)}): stop trading the eval.")
    # 1. day rules
    if d.get("halted"):
        return _no("day_rule", "Daily loss limit was hit: done for the day.")
    if d_trades >= c["max_trades_day"]:
        return _no("day_rule", f"Day rule: {d_trades} trades already today (max {c['max_trades_day']}).")
    if c["stop_after_win"] and d_wins >= 1:
        return _no("day_rule", "Day rule: stop after a winner.")
    if d_losses >= c["max_losses_day"]:
        return _no("day_rule", f"Day rule: {d_losses} losers today (max {c['max_losses_day']}).")
    if d_pnl <= -c["day_stop"]:
        return _no("day_rule", f"Day rule: day P&L {_fmt(d_pnl)} is at or below -{_fmt(c['day_stop'])}.")
    if not stop_pts or stop_pts <= 0:
        return _no("bad_stop", f"Invalid stop distance {stop_pts!r}.")

    # 2. base budget from the grade
    if c["tiers"]:
        tier = tier_of(setup_grade, c)
        if tier == "SKIP":
            return _no("skip_grade", f"Setup graded {setup_grade}: skip.", tier)
        risk = float(c["tier_risk"][tier])
        cap_q = int(c["tier_max_micros"][tier])
        shown = "ungraded" if setup_grade in (None, "") else f"grade {setup_grade}"
        why = [f"{shown} = tier {tier}: {_fmt(risk)} budget" + (f", max {cap_q} micros" if cap_q < c["max_micros"] else "")]
    else:
        tier = "B"
        risk = float(c["flat_risk"])
        cap_q = int(c["max_micros"])
        why = [f"flat {_fmt(risk)} budget"]

    # 3. P3 anti-martingale: smaller after a losing day
    if c["dd_cut"]:
        if c["dd_restore"] == "high":
            peak = a.get("peak_eod", max(bal, start))
            active = a.get("sod_balance", bal) < peak - 0.005
            cond = f"below the end-of-day high {_fmt(peak)}"
        else:
            last = a.get("last_day_pnl", 0.0)
            active = last < 0
            cond = f"last trading day lost {_fmt(last)}"
        if active:
            risk *= (1.0 - c["dd_cut"])
            why.append(f"{cond}: cut {c['dd_cut']:.0%} -> {_fmt(risk)}")

    # 4. P4 sprint near the target (never below 1 micro, so the eval cannot get stuck just short of the target)
    remaining = target - profit
    per_micro = stop_pts * pv
    if c["sprint"] and remaining <= c["sprint_zone"]:
        if c["sprint"] == "protect":
            cap = max(float(c["protect_risk"]), per_micro)
            if risk > cap:
                risk = cap
                why.append(f"{_fmt(remaining)} from the target: protect mode, budget capped at {_fmt(risk)}")
        else:  # finish
            need = remaining / (c["finish_trades"] * c["finish_win_r"])
            cap = c["finish_k"] * cushion
            risk = min(max(need, per_micro), cap)
            why.append(f"{_fmt(remaining)} from the target: finish mode, {c['finish_trades']} winner(s) at "
                       f"{c['finish_win_r']:g}R need {_fmt(need)}"
                       + (f", capped at {c['finish_k']:.0%} of the {_fmt(cushion)} cushion" if cap < need else "")
                       + f" -> {_fmt(risk)}")

    # 5. P2 cushion cap
    if c["cushion_k"]:
        cap = c["cushion_k"] * cushion
        if risk > cap:
            risk = cap
            why.append(f"cushion {_fmt(cushion)} x {c['cushion_k']:.2f} caps it at {_fmt(cap)}")

    # 6. whole micros: floor(budget / (stop x $/pt))
    q = int(math.floor(risk / per_micro + 1e-9))
    q = min(q, cap_q, int(c["max_micros"]), PLAN["max_micros"])
    if q < 1:
        return _no("too_wide", "; ".join(why) + f"; {stop_pts:.2f}-pt stop = {_fmt(per_micro)} per micro, more than "
                   f"the {_fmt(risk)} budget: skip.", tier)

    # 7. hard guards: a worst-case stop-out must not reach the MLL or the daily loss limit
    wc_micro = (stop_pts + c["guard_slip_pts"]) * pv + c["comm_rt"]
    if c["guard"]:
        room_mll = cushion - c["guard_buffer"]
        room_dll = dll + d_pnl - c["guard_buffer"]
        q_max = int(math.floor(min(room_mll, room_dll) / wc_micro + 1e-9))
        if q > q_max:
            which = "MLL" if room_mll <= room_dll else "daily loss limit"
            if q_max < 1:
                return _no("guard", "; ".join(why) + f"; even 1 micro could lose {_fmt(wc_micro)} and only "
                           f"{_fmt(min(room_mll, room_dll) + c['guard_buffer'])} is left above the {which}: skip.", tier)
            why.append(f"guard: {q} micros could reach the {which}, cut to {q_max}")
            q = q_max

    risk_usd = round(q * per_micro, 2)
    wc = round(q * wc_micro, 2)
    minis, micros = divmod(q, 10)
    big, small = {2.0: ("NQ", "MNQ"), 5.0: ("ES", "MES")}.get(pv, ("mini", "micro"))
    label = " + ".join(x for x in (f"{minis} {big}" if minis else "", f"{micros} {small}" if micros else "") if x)
    why.append(f"{stop_pts:.2f}-pt stop = {_fmt(per_micro)}/micro -> {q} micros ({label}), {_fmt(risk_usd)} at the "
               f"stop, worst case {_fmt(wc)} vs {_fmt(cushion)} above the MLL and {_fmt(dll + d_pnl)} left today")
    return {"qty_micros": q, "risk_usd": risk_usd, "worst_case_usd": wc, "reason": "; ".join(why) + ".",
            "code": "ok", "tier": tier, "contracts": {"minis": minis, "micros": micros}}


def dead_threshold(typical_stop: float, cfg: dict | None = None, point_value: float | None = None) -> float:
    """Smallest cushion (balance - MLL) at which this policy can still trade 1 micro of a setup with
    `typical_stop` points of risk: the P2 cap needs k x cushion >= 1 micro, the MLL guard needs
    cushion - buffer >= the worst-case loss of 1 micro. 0 for policies with neither rule."""
    c = _resolve(cfg)
    pv = float(point_value or c["point_value"])
    thr = 0.0
    if c["cushion_k"]:
        thr = max(thr, typical_stop * pv / c["cushion_k"])
    if c["guard"]:
        thr = max(thr, (typical_stop + c["guard_slip_pts"]) * pv + c["comm_rt"] + c["guard_buffer"])
    return thr


def account_dead(account_state: dict, typical_stop: float, cfg: dict | None = None,
                 point_value: float | None = None) -> tuple[bool, str]:
    """(dead, reason). Dead = this policy's cushion rules (P2 cap, MLL guard) no longer allow even 1 micro of an
    ordinary setup with `typical_stop` points of risk. The eval cannot be finished from here; treat it as failed
    (reset). Day state and grade play no part, so a bad day alone never declares an account dead."""
    cushion = float(account_state["balance"]) - float(account_state["mll"])
    if cushion <= 0:
        return True, "Balance at the max-loss level."
    thr = dead_threshold(typical_stop, cfg, point_value)
    if cushion < thr:
        return True, (f"Cushion {_fmt(cushion)} is below {_fmt(thr)}, the least this policy needs to trade 1 micro "
                      f"at a {typical_stop:g}-pt stop: the eval cannot be finished, reset it.")
    return False, ""


class EvalAccount:
    """Tracks an MFFU-style eval: balance, end-of-day peak, trailing MLL (locks at $50,100), day counters, status.
    Mirrors engine/analytics.simulate_eval: the MLL moves only at the end of the day and is checked intraday against
    the worst open P&L; the daily loss limit is soft (the position is flattened at -$1,000 and the day stops)."""

    def __init__(self, plan: dict | None = None):
        p = {**PLAN, **(plan or {})}
        self.p = p
        self.balance = self.sod_balance = self.peak_eod = float(p["start"])
        self.mll = float(p["start"] - p["mll"])
        self.days = 0
        self.days_traded = 0
        self.last_day_pnl = 0.0
        self.loss_streak = 0
        self.status = "OPEN"
        self.fail_kind = None          # "mll" (touched the max-loss level) or "dead" (see account_dead)
        self._new_day()

    def _new_day(self):
        self.day_pnl = 0.0
        self.day_trades = self.day_wins = self.day_losses = 0
        self.day_low = 0.0
        self.halted = False

    @property
    def locked(self) -> bool:
        return self.mll >= self.p["lock"] - 0.005

    def account_state(self) -> dict:
        return {"balance": self.balance, "sod_balance": self.sod_balance, "peak_eod": self.peak_eod,
                "mll": self.mll, "locked": self.locked, "days_traded": self.days_traded,
                "last_day_pnl": self.last_day_pnl, "loss_streak": self.loss_streak,
                "start": self.p["start"], "target": self.p["target"], "dll": self.p["dll"]}

    def day_state(self) -> dict:
        return {"pnl": self.day_pnl, "trades": self.day_trades, "wins": self.day_wins,
                "losses": self.day_losses, "halted": self.halted}

    def record_trade(self, pnl: float, worst_open: float | None = None) -> str:
        """A closed trade: pnl = net $ result, worst_open = worst open P&L during the trade ($, <= 0).
        Returns the status after the trade (OPEN or FAIL)."""
        if self.status != "OPEN":
            return self.status
        dll = self.p["dll"]
        low = min(0.0, pnl, worst_open if worst_open is not None else pnl)
        dip = self.day_pnl + low                      # worst point of the day during this trade
        eff = max(dip, -dll)                          # the daily limit flattens the position at -$1,000
        self.day_trades += 1
        if pnl > 0:
            self.day_wins += 1
        elif pnl < 0:
            self.day_losses += 1
        if self.sod_balance + eff <= self.mll:        # trailing max loss touched intraday -> eval failed
            self.day_pnl = self.mll - self.sod_balance
            self.balance = self.mll
            self.day_low = min(self.day_low, self.day_pnl)
            self.status, self.fail_kind = "FAIL", "mll"
            return self.status
        if dip <= -dll:
            self.day_pnl = -dll
            self.halted = True
        else:
            self.day_pnl += pnl
        self.day_low = min(self.day_low, eff)
        self.balance = self.sod_balance + self.day_pnl
        return self.status

    def mark_dead(self):
        if self.status == "OPEN":
            self.status, self.fail_kind = "FAIL", "dead"

    def end_of_day(self) -> str:
        self.days += 1
        if self.day_trades:
            self.days_traded += 1
            self.last_day_pnl = self.day_pnl
            self.loss_streak = self.loss_streak + 1 if self.day_pnl < 0 else 0
        if self.status == "OPEN":
            self.peak_eod = max(self.peak_eod, self.balance)
            self.mll = min(max(self.mll, self.peak_eod - self.p["mll"]), self.p["lock"])
            if self.balance - self.p["start"] >= self.p["target"] and self.days_traded >= self.p["min_days"]:
                self.status = "PASS"
        self.sod_balance = self.balance
        self._new_day()
        return self.status


def _pol(name: str, **kw) -> dict:
    return {**DEFAULTS, "name": name, **kw}


TIERS = {"tiers": True}
POLICIES = {
    # baselines
    "P0": _pol("P0 flat $350 (current), no guard", guard=False),
    "P0g": _pol("P0 flat $350 + hard guards"),
    "P0_250": _pol("flat $250 + guards", flat_risk=250.0),
    "P0_500": _pol("flat $500 + guards", flat_risk=500.0),
    "P1": _pol("P1 tiers A$700/B$350/C$175, no guard", guard=False, **TIERS),
    "P1g": _pol("P1 tiers + hard guards", **TIERS),
    "P1b": _pol("P1b A$700 (1 NQ max), B/C $350, guards", tier_risk={"A": 700.0, "B": 350.0, "C": 350.0}, **TIERS),
    # P2 cushion-aware (tiers + cushion cap + guards)
    "P2_k20": _pol("P2 tiers, cushion k=0.20", cushion_k=0.20, **TIERS),
    "P2_k25": _pol("P2 tiers, cushion k=0.25", cushion_k=0.25, **TIERS),
    "P2_k35": _pol("P2 tiers, cushion k=0.35", cushion_k=0.35, **TIERS),
    "P2f_k25": _pol("P2 flat $350, cushion k=0.25", cushion_k=0.25),
    "P2f_k35": _pol("P2 flat $350, cushion k=0.35 (= RECOMMENDED)", cushion_k=0.35),
    # P3 anti-martingale (flat + guards)
    "P3_50h": _pol("P3 cut 50% until new high", dd_cut=0.5, dd_restore="high"),
    "P3_30h": _pol("P3 cut 30% until new high", dd_cut=0.3, dd_restore="high"),
    "P3_50w": _pol("P3 cut 50% until a winning day", dd_cut=0.5, dd_restore="win"),
    "P3_30w": _pol("P3 cut 30% until a winning day", dd_cut=0.3, dd_restore="win"),
    # P4 eval sprint (flat + guards)
    "P4a": _pol("P4a protect: $175 inside $1k", sprint="protect"),
    "P4b2": _pol("P4b finish in 2 winners", sprint="finish", finish_trades=2),
    "P4b1": _pol("P4b finish in 1 winner", sprint="finish", finish_trades=1),
    # P5 combinations
    "P5_t_c_d": _pol("P5 tiers+cushion.25+cut50h", cushion_k=0.25, dd_cut=0.5, dd_restore="high", **TIERS),
    "P5_t_c_d_pr": _pol("P5 tiers+cushion.25+cut50h+protect", cushion_k=0.25, dd_cut=0.5, dd_restore="high",
                        sprint="protect", **TIERS),
    "P5_t_c_d_f2": _pol("P5 tiers+cushion.25+cut50h+finish2", cushion_k=0.25, dd_cut=0.5, dd_restore="high",
                        sprint="finish", finish_trades=2, **TIERS),
    "P5_t_c_f2": _pol("P5 tiers+cushion.25+finish2", cushion_k=0.25, sprint="finish", finish_trades=2, **TIERS),
    "P5_f_c_d_f2": _pol("P5 flat+cushion.25+cut50h+finish2", cushion_k=0.25, dd_cut=0.5, dd_restore="high",
                        sprint="finish", finish_trades=2),
    "P5_f_c35_w30_f1": _pol("P5 flat+cushion.35+cut30w+finish1", cushion_k=0.35, dd_cut=0.3, dd_restore="win",
                            sprint="finish", finish_trades=1),
    "P5_f_c35_w30": _pol("P5 flat+cushion.35+cut30w", cushion_k=0.35, dd_cut=0.3, dd_restore="win"),
    "P5_f_c_f2": _pol("P5 flat+cushion.25+finish2", cushion_k=0.25, sprint="finish", finish_trades=2),
    "P5_f_c35_f1": _pol("P5 flat+cushion.35+finish1", cushion_k=0.35, sprint="finish", finish_trades=1),
    "P5_1b_c35_f1": _pol("P5 A$700/B,C$350+cushion.35+finish1", tier_risk={"A": 700.0, "B": 350.0, "C": 350.0},
                         cushion_k=0.35, sprint="finish", finish_trades=1, **TIERS),
}
# The policy size() uses when cfg is None (chosen in research/lab/RISK_REPORT.md, 2026-10-16):
# flat $350 per setup (grades ignored), never more than 35% of the cushion above the trailing MLL, hard MLL /
# daily-limit guards, day rules (2 trades max, stop after a winner, stop after 2 losers or -$700).
# Tiers stay OFF: no available grade (engine A..D, regime, trader brain v1/v2, ATM tiers) ranked setups out of sample.
# To size by grade anyway: cfg = {**POLICIES["RECOMMENDED"], "tiers": True}  (A = $700 / max 1 NQ, C = $175).
POLICIES["RECOMMENDED"] = {**POLICIES["P2f_k35"], "name": "RECOMMENDED: flat $350, cushion cap 35%, guards, day rules"}
TYPICAL_STOP_PTS = 44.0   # median engine stop; pass your model's own median stop to account_dead()
