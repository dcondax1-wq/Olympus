"""FATES: the Monte Carlo. Thousands of futures, each a run of real market days drawn from a sample period.

bootstrap()   circular 5-session block bootstrap (a week of real days at a time, so streaks and quiet weeks survive);
              every real day is equally likely, so the bootstrap keeps the per-session mean. Seeded: same seed, same futures.
run_eval()    one eval from today's state (or a fresh one), session by session, under the MFFU rules (rules.EvalBook):
              pass / fail / stuck / closed / still open, the balance after every session.
run_money()   a book of account slots on the same futures: eval -> 2 sessions of MFFU paperwork -> funded -> payouts
              (80% to the owner) -> lost or 5 payouts -> buy the next eval. Slots start a week apart (the money plan's
              rule), the live evals from today's state at no cost (already paid). Returns every slot's money events, so a
              book of N accounts is the first N slots.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import numpy as np

from tools.fates.rules import CLOSED, DEAD, FAIL, KEEPALIVE_COST, PASS, STUCK, EvalBook, Rules, needs_keepalive

BLOCK = 5
GAP = 2                         # sessions from an eval pass to the first funded session (MFFU paperwork)

# money event codes (exported as-is to the page)
EV_BUY, EV_PASS, EV_DEAD, EV_LOST, EV_PAY, EV_GRAD = 0, 1, 2, 3, 4, 5


def bootstrap(n_days: int, n_paths: int, length: int, seed: int, block: int = BLOCK) -> np.ndarray:
    """(n_paths, length) indices into a period's day list: circular blocks of `block` consecutive days."""
    rng = np.random.default_rng(seed)
    nb = -(-length // block)
    starts = rng.integers(0, n_days, size=(n_paths, nb))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]) % n_days
    return idx.reshape(n_paths, nb * block)[:, :length]


@dataclass
class Start:
    """An eval's state at the start of the simulation, in $ relative to its start balance."""
    profit: float = 0.0
    peak: float = 0.0
    floor: float | None = None
    session: int = 0
    days_traded: int = 0
    last_trade: dt.date | None = None

    def book(self, rules: Rules, stuck: float | None) -> EvalBook:
        return EvalBook(rules=rules, bal=self.profit, peak=self.peak, floor=self.floor if self.floor is not None else -rules.mll,
                        session=self.session, days_traded=self.days_traded, last_trade=self.last_trade, stuck_below=stuck)


def eval_session(src, book: EvalBook, units, real_day: str, day: dt.date, keepalive: bool) -> tuple[str | None, bool]:
    """One session of an eval: the bot's trades, the owner's keep-alive trade when due, then MFFU's rules.
    -> (outcome, keep-alive placed)."""
    pnl, worst, traded = src.play_eval(units, book, real_day)
    ka = False
    if not traded and keepalive and needs_keepalive(book.last_trade, day):
        pnl, worst, traded, ka = pnl - KEEPALIVE_COST, min(worst, pnl - KEEPALIVE_COST), True, True
    return book.close_session(day, pnl, worst, traded), ka


def run_eval(src, rules: Rules, start: Start, dates: list[str], paths: np.ndarray, cal: list[dt.date],
             keepalive: bool = True) -> dict:
    """Every path from `start` for len(paths[0]) sessions. -> {"out": [outcome | "open"], "at": [sessions used],
    "hist": [[balance after each session]], "ka": [keep-alive trades]}."""
    H = paths.shape[1]
    out, at, hist, kas = [], [], [], []
    with src.active():
        for seq in paths:
            book = start.book(rules, src.stuck)
            book.history = []
            res, used, n_ka = "open", H, 0
            for k in range(H):
                d = dates[seq[k]]
                o, ka = eval_session(src, book, src.units(d), d, cal[k], keepalive)
                n_ka += ka
                if o:
                    res, used = o, k + 1
                    break
            out.append(res)
            at.append(used)
            hist.append(list(book.history))
            kas.append(n_ka)
    return {"out": out, "at": at, "hist": hist, "ka": kas}


def eval_summary(r: dict, start: Start, rules: Rules, cal: list[dt.date]) -> dict:
    """The owner's eval-speed numbers (CLAUDE.md): p10 / f10 / dec10 / p15 / f15 / slow_pass / pass_med, counted from
    today's session, plus the odds at the horizon and the days-to-pass histogram."""
    n = len(r["out"])
    H = max(len(h) for h in r["hist"]) if r["hist"] else 0
    out, at = r["out"], r["at"]
    pas = [a for o, a in zip(out, at) if o == PASS]
    dead = [a for o, a in zip(out, at) if o in DEAD]
    pct = lambda x: round(100.0 * x / n, 1)  # noqa: E731
    hist = [0] * (max(at) if at else 0)
    for a in pas:
        hist[a - 1] += 1
    dec = sorted(pas + dead)
    cal_days = [(cal[a - 1] - cal[0]).days + 1 for a in pas]
    return {
        "paths": n, "horizon": max(at) if at else 0,
        "pass": pct(len(pas)), "fail": pct(sum(1 for o in out if o in (FAIL, STUCK))), "closed": pct(sum(1 for o in out if o == CLOSED)),
        "stuck": pct(sum(1 for o in out if o == STUCK)), "open": pct(sum(1 for o in out if o == "open")),
        "p10": pct(sum(1 for a in pas if a <= 10)), "f10": pct(sum(1 for a in dead if a <= 10)),
        "dec10": pct(sum(1 for a in pas + dead if a <= 10)),
        "p15": pct(sum(1 for a in pas if a <= 15)), "f15": pct(sum(1 for a in dead if a <= 15)),
        "slow_pass": round(100.0 * sum(1 for a in pas if a > 15) / max(1, len(pas)), 1),
        "pass_med": float(np.median(pas)) if pas else None,
        "pass_p25": float(np.percentile(pas, 25)) if pas else None, "pass_p75": float(np.percentile(pas, 75)) if pas else None,
        "pass_cal_med": float(np.median(cal_days)) if cal_days else None,
        "decide_med": float(np.median(dec)) if dec else None,
        "pass_hist": hist[:H],
        "keepalive_trades": round(float(np.mean(r["ka"])), 2),
        "sessions_from": start.session + 1,
    }


# ------------------------------------------------------------------------------------------------ money
@dataclass
class Slot:
    """One account slot of the book: a bot on a plan; start = a live eval state (paid already) or None (buy at `offset`)."""
    src: object
    rules: Rules
    label: str
    start: Start | None = None
    offset: int = 0


class _SlotRun:
    def __init__(self, s: Slot, keepalive: bool):
        self.s, self.ka = s, keepalive
        self.phase = "idle"
        self.book, self.funded, self.wait = None, None, 0
        self.last_trade = None
        self.cash, self.paid = 0.0, 0.0
        self.evals, self.funded_n, self.pays, self.lost, self.grads = 0, 0, 0, 0, 0
        self.first_pay = None
        self.events = []

    def _buy(self, k, day):
        self.cash -= self.s.rules.price
        self.evals += 1
        self.book = Start(last_trade=day).book(self.s.rules, self.s.src.stuck)
        self.phase = "eval"
        self.events.append((k, EV_BUY, -self.s.rules.price))

    def step(self, k: int, units, real_day: str, day: dt.date):
        s = self.s
        if self.phase == "idle":
            if s.start is not None and k == 0:
                self.book = s.start.book(s.rules, s.src.stuck)
                self.phase = "eval"
            elif s.start is None and k == s.offset:
                self._buy(k, day)
            else:
                return
        if self.phase == "eval":
            o, ka = eval_session(s.src, self.book, units, real_day, day, self.ka)
            if ka:
                self.cash -= KEEPALIVE_COST
            if o == PASS:
                self.phase, self.wait = "wait", GAP
                self.funded_n += 1
                self.events.append((k, EV_PASS, 0.0))
            elif o in DEAD:
                self.events.append((k, EV_DEAD, 0.0))
                self._buy(k, day)
        elif self.phase == "wait":
            self.wait -= 1
            if self.wait == 0:
                self.funded, self.phase, self.last_trade = s.src.new_funded(), "funded", day
        elif self.phase == "funded":
            ev, amt, traded = self.funded.step(units, real_day)
            if traded:
                self.last_trade = day
            elif self.ka and needs_keepalive(self.last_trade, day):
                self.cash -= KEEPALIVE_COST
                self.last_trade = day
            if amt > 0:
                self.cash += amt
                self.paid += amt
                self.pays += 1
                self.first_pay = self.first_pay or k + 1
                self.events.append((k, EV_PAY, round(amt, 2)))
            if ev in ("lost", "grad"):
                if ev == "lost":
                    self.lost += 1
                    self.events.append((k, EV_LOST, 0.0))
                else:
                    self.grads += 1
                    self.events.append((k, EV_GRAD, 0.0))
                self._buy(k, day)


def run_money(slots: list[Slot], dates: list[str], paths: np.ndarray, cal: list[dt.date], keepalive: bool = True) -> list[list[dict]]:
    """-> per path, per slot: {"cash": [$ net after each session], "events": [(k, code, $)], "first_pay", counts}."""
    H = paths.shape[1]
    srcs = []
    for s in slots:
        if all(s.src is not x for x in srcs):
            srcs.append(s.src)
    R = []
    import contextlib
    with contextlib.ExitStack() as st:
        for x in srcs:
            st.enter_context(x.active())
        for seq in paths:
            runs = [_SlotRun(s, keepalive) for s in slots]
            cash = np.zeros((len(slots), H))
            for k in range(H):
                d = dates[seq[k]]
                for j, r in enumerate(runs):
                    r.step(k, r.s.src.units(d), d, cal[k])
                    cash[j, k] = r.cash
            R.append([{"cash": cash[j], "events": r.events, "first_pay": r.first_pay, "evals": r.evals, "funded": r.funded_n,
                       "pays": r.pays, "paid": r.paid, "lost": r.lost, "grads": r.grads} for j, r in enumerate(runs)])
    return R


def money_summary(R: list[list[dict]], slots: list[int], cal: list[dt.date], goal: float) -> dict:
    """A book of the slots `slots` (indices): $ a month (net of every eval bought) p10 / p50 / p90 and mean at 6 and 12 months,
    the chance of a payout within 30 calendar days, of ending behind, of reaching the goal."""
    H = len(R[0][0]["cash"])
    tot = book_cash(R, slots)           # (paths, H)
    out = {"paths": len(R), "accounts": len(slots)}
    for label, k in (("6m", min(H, 126)), ("12m", H)):
        v = tot[:, k - 1] / (k / 21.0)
        out[label] = {"pm_p10": round(float(np.percentile(v, 10))), "pm_p50": round(float(np.percentile(v, 50))),
                      "pm_p90": round(float(np.percentile(v, 90))), "pm_mean": round(float(v.mean())),
                      "net_p50": round(float(np.percentile(tot[:, k - 1], 50))), "behind": round(100.0 * float((tot[:, k - 1] < 0).mean()), 1),
                      "evals": round(float(np.mean([sum(p[j]["evals"] for j in slots) for p in R])) * k / H, 2)}
    in30 = [i for i, d in enumerate(cal) if (d - cal[0]).days < 30]
    k30 = (in30[-1] + 1) if in30 else 0
    first = [min((p[j]["first_pay"] for j in slots if p[j]["first_pay"]), default=None) for p in R]
    out["pay30"] = round(100.0 * sum(1 for f in first if f is not None and f <= k30) / len(R), 1)
    fp = [f for f in first if f is not None]
    out["first_pay_med"] = float(np.median(fp)) if fp else None
    out["any_pay"] = round(100.0 * len(fp) / len(R), 1)
    out["goal"] = goal
    out["goal_pct"] = round(100.0 * float((tot.max(axis=1) >= goal).mean()), 1)
    out["ahead"] = round(100.0 * float((tot[:, -1] > 0).mean()), 1)
    out["behind"] = round(100.0 * float((tot[:, -1] < 0).mean()), 1)
    out["funded"] = round(float(np.mean([sum(p[j]["funded"] for j in slots) for p in R])), 2)
    out["payouts"] = round(float(np.mean([sum(p[j]["pays"] for j in slots) for p in R])), 2)
    out["lost"] = round(float(np.mean([sum(p[j]["lost"] for j in slots) for p in R])), 2)
    return out


def book_cash(R: list[list[dict]], slots: list[int]) -> np.ndarray:
    """(paths, sessions): the book's $ net to the owner after each session."""
    return np.array([sum(p[j]["cash"] for j in slots) for p in R])


def quantile_bands(M: np.ndarray, qs=(10, 25, 50, 75, 90), every: int = 1) -> list[list[float]]:
    """M (paths, T) -> per quantile, the value at every `every`-th step."""
    cols = list(range(0, M.shape[1], every))
    if cols[-1] != M.shape[1] - 1:
        cols.append(M.shape[1] - 1)
    return [[round(float(x), 3) for x in np.percentile(M[:, cols], q, axis=0)] for q in qs]
