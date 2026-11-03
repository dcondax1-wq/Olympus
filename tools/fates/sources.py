"""FATES: the bots' real per-session results and how each bot sizes them.

A source answers three questions for the simulator, one session at a time:
  units(date)                 the bot's candidate trades on that real market day (its live-settings replay)
  play_eval(units, book, d)   the day's result on an eval account in the state `book` (rules.EvalBook):
                              (pnl, worst open P&L, traded?) with the bot's own live eval sizing
  new_funded()                a funded account (its own engine: MFFU buffer, payout cycle, 50% consistency, 5 payouts)

Sources:
  LitSource    Zlarior (LIT). Trades = run lit_live, the live-settings replay (research/lab/backtest_live.json; the unit
               details - stop, target, worst open point - from its trade ledger research/handoff/2026-10-25/
               COMPLETE_TRADE_LEDGER.csv, read by tools/uprisk.py). Eval sizing = live_model.json lit_sizing (two_week,
               room 0.8, safe_eval after session 10), funded = the live uprisk preset (60% of the room, <= $1,500 a
               trade, a winner <= $2,000; the 25K at half scale). The engine is tools/uprisk.py, the one
               tools/rd_money.py (the money plan) runs on.
  AtlasSource  ATLAS (account B on the 25K). Trades = its members' replay (tools/atx_edge "today": EMA, MACD, S/R),
               eval = engine/account_b need size through tools/second_mix.play_day, funded = the 25K funded preset
               (tools/atx_edge.Funded). Its libraries take ~25 s to load, so they load on first use.

Paper only: nothing here routes an order or changes a live setting.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for p in (ROOT, os.path.join(ROOT, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

from tools.fates.rules import apply_dll  # noqa: E402

BACKTEST_LIVE = os.path.join(ROOT, "research", "lab", "backtest_live.json")
PERIODS = {
    "2026": ("2026-01-01", "2026-10-16", "2026 sample (Jan 2 - Oct 16 2026: the market LIT was tuned on and checked in)"),
    "2021-25": ("2021-11-01", "2025-12-31", "2021-25 sample (Nov 2021 - Dec 2025: 4 years LIT was never tuned on; a much weaker edge)"),
    "H2": ("2026-07-01", "2026-10-16", "Jul-Oct 2026 (the H2 check, the rate to quote)"),
}


def _uprisk():
    import uprisk as U  # noqa: E402  (tools/uprisk.py)
    return U


class FundedRun:
    """A funded account behind one interface: step(units, real_day) -> (event, $ to the owner, traded)."""

    def __init__(self, step):
        self._step = step

    def step(self, units, real_day):
        return self._step(units, real_day)


class LitSource:
    """Zlarior (LIT) on an MFFU Builder 50K or 25K."""

    bot = "zlarior"
    name = "Zlarior"

    def __init__(self, plan: str = "builder50k"):
        U = _uprisk()
        self.U, self.plan = U, plan
        self.ecfg = U.ecfg_of({}, plan=plan)                 # live two_week eval sizing (room 0.8; safe_eval after s10)
        self.fcfg = U.UP50 if plan == "builder50k" else U.UP25
        self.E = U.EPLAN[plan]
        self.stuck = float(self.E["stuck"])
        self._by = None
        self._sessions = None

    # -------------------------------------------------------------------------------- data
    def _load(self):
        if self._by is None:
            self._by = self.U.trades()
            self._sessions = self.U.sessions()
        return self._by

    def sessions(self) -> list[str]:
        self._load()
        return list(self._sessions)

    def units(self, day: str) -> list:
        return self._load().get(day, [])

    def check_against_replay(self) -> dict:
        """The ledger the units come from == the live-settings replay (research/lab/backtest_live.json): same trade days."""
        bt = json.load(open(BACKTEST_LIVE, encoding="utf-8"))
        days_bt = sorted(t["day"] for t in bt["trades"])
        days_led = sorted(d for d, ts in self._load().items() for _ in ts)
        return {"replay_trades": len(days_bt), "ledger_trades": len(days_led), "same_days": days_bt == days_led,
                "replay_built": bt["meta"]["built"], "replay_strategy": bt["meta"]["strategy"]}

    # -------------------------------------------------------------------------------- the eval (= tools/uprisk.Eval.step)
    def play_eval(self, units, book, real_day=None):
        from engine import sizing as SZ
        from engine.lit import qty_for
        U, c, R = self.U, self.ecfg, book.rules
        sub = {k: v for k, v in c.items() if not k.startswith("_")}
        sc = self.E["scale"]
        session = book.session + 1
        cum, worst, traded = 0.0, 0.0, False
        for t in units:
            if cum <= -R.dll:
                break
            m0 = qty_for(t["risk"])
            if sc != 1.0:
                m0 = max(1, int(m0 * sc)) if m0 else 0
            if not m0:
                continue
            st = {"profit": book.bal, "cum": cum, "room": book.bal + cum - book.floor, "session": session, "n_today": 0,
                  "wk_pnl": 0.0, "days_traded": book.days_traded}
            q = SZ.lit_qty(m0, {"risk_pts": t["risk"], "tgt_pts": t["tgt"], "size_mult": 1.0}, sub, room=st["room"], state=st,
                           learning=None, max_micros=c["_maxq"])["qty"]
            q = min(q, c["_maxq"])
            if q <= 0:
                continue
            traded = True
            pnl = t["pts"] * U.PV * q - U.COMM * q
            low = min(0.0, t["w1"] * U.PV * q - U.COMM * q, pnl)
            pnl, low = apply_dll(cum, pnl, low, R.dll, U.SLIP * U.PV * q)
            worst = min(worst, cum + low)
            if book.bal + cum + low <= book.floor:
                break
            cum += pnl
        return cum, worst, traded

    # -------------------------------------------------------------------------------- funded
    def new_funded(self):
        f = self.U.Funded(self.plan, self.fcfg)

        def step(units, real_day):
            n0 = f.n_tr
            ev, x = f.step(units)
            return ev, float(x or 0.0), f.n_tr > n0
        return FundedRun(step)

    @contextlib.contextmanager
    def active(self):
        yield self


class AtlasSource:
    """ATLAS on the MFFU Builder 25K (account B)."""

    bot = "atlas"
    name = "ATLAS"
    plan = "builder25k"
    stuck = 100.0                                         # tools/atx_edge.Eval: the bot stops under $100 of room

    def __init__(self):
        self._x = None

    def _libs(self):
        if self._x is None:
            import logging
            logging.getLogger("engine.sizing").setLevel(logging.ERROR)
            from tools import atx_edge as X
            from tools import atlas_funded as AF
            from engine import funded_life as FL
            V2, A, M, EAB = X.libs()
            Ve = X.today()
            by = M.by_day(A.account_units(Ve))
            self._x = {"X": X, "AF": AF, "A": A, "M": M, "V": Ve, "by": by, "P": dict(FL.plan_of("builder25k")),
                       "sessions": list(M.units()["sessions"])}
        return self._x

    def sessions(self) -> list[str]:
        return list(self._libs()["sessions"])

    def units(self, day: str) -> list:
        return self._libs()["by"].get(day, ())

    @contextlib.contextmanager
    def active(self):
        """ATLAS's sizing lives in module patches (the 25K plan and the funded sizer): on only inside this block."""
        x = self._libs()
        with x["A"].Plan(x["V"]):
            with x["AF"].Sizer(x["X"].funded_q(x["X"].FZ_LIVE, x["V"])):
                yield self

    def play_eval(self, units, book, real_day=None):
        M = self._libs()["M"]
        cum, recs, failed = M.play_day(units, real_day, book.bal, book.floor, book.session + 1, "atlas", False, 2, None,
                                       reserve=False)
        worst, run = 0.0, 0.0
        for r in recs:
            worst = min(worst, run + r["low"])
            run += r["pnl"]
        if failed:
            worst = min(worst, book.floor - book.bal - 0.01)
        return cum, worst, bool(recs)

    def new_funded(self):
        x = self._libs()
        f = x["X"].Funded(x["M"], dict(x["P"]))

        def step(units, real_day):
            paid, recs = f.step(units, real_day)
            if f.done:
                return ("grad" if f.why == "grad" else "lost"), float(paid), bool(recs)
            return ("paid" if paid > 0 else None), float(paid), bool(recs)
        return FundedRun(step)


def period_dates(sessions: list[str], period: str) -> list[str]:
    a, z, _ = PERIODS[period]
    return [d for d in sessions if a <= d <= z]


def today_state_defaults() -> dict:
    """Fallbacks when the live feed cannot be read (owner's numbers on 2026-11-03)."""
    return {
        "zlarior": {"room": 1106.0, "to_target": 3726.0, "session": 12, "quiet_days": 0, "plan": "builder50k"},
        "atlas": {"room": 746.0, "to_target": 1754.0, "session": 7, "quiet_days": 0, "plan": "builder25k"},
    }


def as_date(s) -> dt.date:
    return s if isinstance(s, dt.date) else dt.date.fromisoformat(str(s)[:10])
