"""FATES: the MFFU evaluation rules, as plain state you can step one session at a time.

Everything here is pure (no bot, no data): an eval account is a balance, a trailing floor and a few counters, and
`EvalBook.close_session` applies MFFU's rules to one session's result. The bots' own engines (tools/fates/sources.py)
only say what a session made (pnl), how deep it went while open (worst) and whether a trade was placed.

The rules (research/lit/mffu_rules.json "limits", checked against the owner's MFFU dashboard 2026-10-26):
  floor       end-of-day trailing max loss: moves up only at the close, to the day's best end balance minus the max
              loss, and stops at start + $100. Open losses count: equity at or below the floor at ANY moment fails.
  daily loss  soft: when the day's loss reaches the limit the day is over (the account stays open). apply_dll() caps a
              trade that would cross it at the limit plus one tick of slippage, as the bots' engines do.
  target      balance >= target AND at least min_days traded days = passed.
  inactivity  no trade for 7 calendar days closes the account. The owner's Jarvis tells him to place 1 MNQ by hand on
              quiet day 6 (KEEPALIVE_AT); the simulator models that keep-alive trade unless told not to.
  stuck       a bot behaviour, not an MFFU rule: the bot stops trading when the room to the floor is under its minimum
              (LIT 50K $200, 25K and ATLAS $100), so the eval is as good as failed and a new one is bought.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from dataclasses import dataclass, field

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RULES_FILE = os.path.join(ROOT, "research", "lit", "mffu_rules.json")

KEEPALIVE_AT = 6                    # Jarvis: day 6 with no trade = red, "place 1 MNQ by hand today"
KEEPALIVE_COST = 1.90 + 2 * 0.25    # 1 micro: $1.90 round trip + about a tick of slippage ($0.50) each way, flat at once

PASS, FAIL, STUCK, CLOSED = "pass", "fail", "stuck", "closed"
DEAD = (FAIL, STUCK, CLOSED)        # outcomes that end the eval without a pass


@dataclass(frozen=True)
class Rules:
    """One MFFU eval plan in $ relative to the start balance."""
    key: str
    name: str
    target: float
    mll: float
    lock: float
    dll: float
    min_days: int
    inactivity_days: int
    price: float
    max_micros: int
    buffer: float = 0.0
    pay_min: float = 0.0
    pay_max: float = 0.0
    split: float = 0.8
    max_payouts: int = 5

    def as_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


def load_rules(plan: str, price: float | None = None, path: str = RULES_FILE) -> Rules:
    """builder50k / builder25k from mffu_rules.json; price = the owner's real price unless given (other firms)."""
    J = json.load(open(path, encoding="utf-8"))
    key = {"builder50k": "builder_50k", "builder25k": "builder_25k"}[plan]
    L = J["limits"][key]
    if plan == "builder50k":
        ev = J["builder_50k"]["eval"]
        paid = float(ev["price"]["value"]["owner_paid"])
        min_days = int(ev["min_trading_days_eval"]["value"] or 1)
        name = "MFFU Builder 50K"
    else:
        paid = float(J["builder_25k"]["price"]["value"]["owner_paid"])
        min_days = int(J["builder_50k"]["eval"]["min_trading_days_eval"]["value"] or 1)   # the 25K guide gives none: same as 50K
        name = "MFFU Builder 25K"
    return Rules(key=plan, name=name, target=float(L["target"]), mll=float(L["mll"]), lock=float(L["lock"]), dll=float(L["dll"]),
                 min_days=min_days, inactivity_days=int(L["inactivity_days"]), price=float(price if price is not None else paid),
                 max_micros=int(L["max_micros"]), buffer=float(L["buffer"]), pay_min=float(L["pay_min"]),
                 pay_max=float(L["pay_max"]), split=float(L["split"]), max_payouts=int(L["max_payouts"]))


def apply_dll(cum: float, pnl: float, low: float, dll: float, slip_usd: float) -> tuple[float, float]:
    """A trade inside a day: cum = the day's closed P&L before it, pnl / low = its result and its worst open P&L.
    If the trade's worst point reaches the soft daily loss, it is closed there (plus slippage): -> (pnl, low)."""
    if cum + low <= -dll:
        pnl = -dll - cum - slip_usd
        low = pnl
    return pnl, low


@dataclass
class EvalBook:
    """One eval account, in $ relative to the start balance."""
    rules: Rules
    bal: float = 0.0
    peak: float = 0.0
    floor: float | None = None
    session: int = 0                      # sessions already closed
    days_traded: int = 0
    last_trade: dt.date | None = None     # the last day with a trade (or the day the eval started)
    stuck_below: float | None = None      # the bot stops under this much room (None = never)
    history: list = field(default_factory=list)

    def __post_init__(self):
        if self.floor is None:
            self.floor = -self.rules.mll

    @property
    def room(self) -> float:
        return self.bal - self.floor

    def quiet_days(self, day: dt.date) -> int:
        return (day - self.last_trade).days if self.last_trade else 0

    def close_session(self, day: dt.date, pnl: float, worst: float, traded: bool) -> str | None:
        """Apply one session: pnl = closed P&L, worst = the lowest open P&L of the day (<= 0, relative to the session
        start), traded = a trade was placed. -> PASS / FAIL / STUCK / CLOSED / None (still open)."""
        R = self.rules
        self.session += 1
        if self.bal + min(0.0, worst) <= self.floor + 1e-9:          # open losses count: an intraday touch fails
            self.bal = self.floor
            self.history.append(round(self.bal, 2))
            return FAIL
        self.bal += pnl
        if traded:
            self.days_traded += 1
            self.last_trade = day
        self.history.append(round(self.bal, 2))
        if self.bal <= self.floor + 1e-9:
            return FAIL
        self.peak = max(self.peak, self.bal)
        self.floor = min(max(self.floor, self.peak - R.mll), R.lock)     # end-of-day trailing, locks at start + $100
        if self.bal >= R.target - 1e-9 and self.days_traded >= R.min_days:
            return PASS
        if self.stuck_below is not None and self.room < self.stuck_below:
            return STUCK
        if not traded and self.last_trade is not None and (day - self.last_trade).days >= R.inactivity_days:
            return CLOSED
        return None


def needs_keepalive(book_last_trade: dt.date | None, day: dt.date, at: int = KEEPALIVE_AT) -> bool:
    """The owner's keep-alive (Jarvis, day 6 red): no bot trade today and `at`+ calendar days since the last trade."""
    return book_last_trade is not None and (day - book_last_trade).days >= at


def trading_days(start: dt.date, n: int) -> list[dt.date]:
    """The next n weekdays from start (inclusive): the calendar the simulated futures are laid on."""
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += dt.timedelta(days=1)
    return out
