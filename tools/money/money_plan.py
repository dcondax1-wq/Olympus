"""MONEY PLAN (2026-11-18 night, night-money; the owner's goal: the fastest path to real payouts, in dollars). PAPER RESEARCH
ONLY: reads stored trades; writes research/lab/money_plan.json, the Money plan page data tools/web_public/business/plan.json
and the VALUE fields of the open Decide-card items in tools/web_public/business/decisions.json (usd_month, usd_month_by,
risk, recommend, recommend_why, impact, impact_usd, valued). Changes nothing live (no live_model*.json, no engine file).

Tonight's real accounts (python tools/board.py read, 2026-11-18 18:19 ET), ALL on the SAME Monte Carlo paths (tools/uprisk.mc_paths
seed 23, 5-session blocks, 126 sessions from 2026-11-19) so a bad week hits every account at once (they trade the same signals):
  Z50  Zlarior, Builder 50K eval: $49,193 = $3,807 to pass with $1,025 of room, session 24 on Nov 19, LIT live two_week
       (builder_levers GEv from the hole). Funded: LIT alone (tonight's setup, uprisk UP50). Fail / stuck -> re-buy $91.80.
  N25  Zlarior 25K #2, Builder 25K eval from $25,000 (started Nov 18): LIT at 40% of the room to session 80, then safe 60%
       (= the mffu_builder_25k preset, tools/money/builder25k_eval.Ev25). Funded: LIT alone (UP25). Re-buy $63.
  A25  ATLAS, Builder 25K FUNDED: $24,887 (-$113 on Nov 18, $887 room), ATLAS alone at the funded preset (60% of the room,
       <= $750, a winner <= $1,000); the bot pings at $750 above the $1,100 buffer and you ask then (funded_life ask_above).
       Lost / 5 payouts -> a fresh 25K eval ($63) on ATLAS's eval sizing.
  R25  Rapid EOD 25K, bought tonight / tomorrow at $97.20 (CLUB), first session Nov 20: LIT + ATLAS $250, the 30% best-day
       guard, payouts keep $500 above the $1,100 buffer (engine/rapid.PLANS = tools/money/rapid25.py "25K, keep $500").
  R2   the NEXT BUY = the 5th funded slot (MFFU: 5 funded at once): a Rapid EOD 50K ($165 CLUB, LIT + ATLAS $500, keep $1,000)
       bought the session after the payouts in hand (after the 30% tax pot) reach $165 (paid from payouts, not your pocket).
       The bot runs ONE Rapid at a time today: R2 needs your yes and a small code change, so the totals are given both ways.

Every Decide-card item = ONE change on one account, everything else as tonight, the same paths (its $ = the change in that
account's 6-month cash to you, after fees and MFFU's split, before the 30% tax pot, per month):
  payout-ping-1000     A25 + N25 (once funded): ask at $1,000 above the buffer instead of $750 (tools/money/payout25.py)
  zlarior-funded25     A25: LIT + ATLAS $250 on the funded 25K (funded25.by_shared = the engine/lit25 one-account rule)
  rapid25-lit-bank     R25: LIT takes 1 micro banked at the day's 30% room (rapid25_lit_lane "b")
  atlas-on-50k-funded  Z50 funded: LIT + ATLAS $500 (builder_levers F50_LA)
  atlas-on-rapid       R25: ATLAS $250 next to LIT (built ON); its value = tonight's R25 minus LIT alone
  keep-1000-rapid      R25: keep $1,000 above the buffer instead of $500 (the 50K preset keeps $1,000 already)
  ask-mffu-parallel, cloud-alerts: no $ change (protection only)
Markets: H2 = 2026 Jul-Oct-like (the fair row: LIT was picked on Jan-Jun), H1 = 2026 Jan-Jun-like (good), REF = 2021-25-like
(the bots had no edge). Costs in: $1.90 a micro + 1 tick, every eval fee and re-buy, the MFFU split (80% Builder, 90% Rapid).

    python -X utf8 tools/money/money_plan.py              # n = 1000 paths a market (~10-25 min on a busy box)
    python -X utf8 tools/money/money_plan.py --n 200      # quicker, noisier
    python -X utf8 tools/money/money_plan.py --no-save    # print only
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import builder_levers as BL  # noqa: E402
import builder25k_eval as B25  # noqa: E402
import fleet_plan as FP  # noqa: E402
import funded25 as F25  # noqa: E402
import rapid25 as R25  # noqa: E402
import rapid25_lit_lane as RLL  # noqa: E402
import rapid_levers as RL  # noqa: E402

SA, U, np = BL.SA, BL.U, BL.np
ROOT = BL.ROOT
OUT = os.path.join(ROOT, "research", "lab", "money_plan.json")
PAGE = os.path.join(ROOT, "tools", "web_public", "business", "plan.json")
DECISIONS = os.path.join(ROOT, "tools", "web_public", "business", "decisions.json")
TODAY = "2026-11-18"
START = "2026-11-19"                     # the first session after tonight
P50, P25, PR25, PR50 = 91.80, 63.00, 97.20, 165.00     # the owner's real prices (CLUB)
TAX, BUDGET = 0.30, 150.0
LEN, GAP, MO = BL.LEN, BL.GAP, BL.MO
SPANS = ("H2", "H1", "REF")
MKT = {"H2": "2026 Jul-Oct-like", "H1": "2026 Jan-Jun-like", "REF": "2021-25-like"}
# tonight (board.py read 2026-11-18 18:19 ET)
ZLARIOR = {"room": 1025.0, "to_go": 3807.0, "session": 23}      # GEv adds 1 before the first step: Nov 19 = session 24
A25_PNL = -113.0                                                   # ATLAS funded $24,887: floor $24,000 = $887 room
R25_JOIN = 1                                                       # bought tonight / tomorrow: trades from Nov 20 (k = 1)
NOW = [
    {"key": "Z50", "name": "Zlarior 50K", "plan": "Builder 50K", "stage": "eval", "balance": 49193, "to_pass": 3807, "room": 1025,
     "bots": "Zlarior (LIT)"},
    {"key": "N25", "name": "Zlarior 25K #2", "plan": "Builder 25K", "stage": "eval", "balance": 25000, "to_pass": 1500, "room": 1000,
     "bots": "Zlarior (LIT) at 40% of the room"},
    {"key": "A25", "name": "ATLAS funded 25K", "plan": "Builder 25K", "stage": "funded", "balance": 24887, "to_pass": None, "room": 887,
     "bots": "ATLAS"},
    {"key": "R25", "name": "Rapid EOD 25K", "plan": "Rapid EOD 25K", "stage": "buy tonight", "balance": None, "to_pass": 1500, "room": 1000,
     "bots": "Zlarior + ATLAS", "price": PR25},
]
NAMES = {"Z50": "Zlarior 50K", "N25": "Zlarior 25K #2", "A25": "ATLAS funded 25K", "R25": "Rapid EOD 25K", "R2": "Rapid EOD 50K (next buy)"}
PRICE_OF = {"Z50": P50, "N25": P25, "A25": P25, "R25": PR25, "R2": PR50}
DECIDE_IDS = ("payout-ping-1000", "zlarior-funded25", "rapid25-lit-bank", "atlas-on-50k-funded", "atlas-on-rapid",
              "keep-1000-rapid", "ask-mffu-parallel", "cloud-alerts")


# ================================================================================================ the trade streams
_BY = {}


def by():
    """Per session: LIT / ATLAS / LIT + ATLAS (stack) / LIT + ATLAS on ONE account (the lit25 rule)."""
    if not _BY:
        _BY["L"] = BL.by_mix(("LIT",))
        _BY["A"] = BL.by_mix(("ATLAS",))
        _BY["LA"] = BL.by_mix(("LIT", "ATLAS"))
        _BY["S"], _ = F25.by_shared()
    return _BY


# ================================================================================================ the seats (one account each)
STUCK_F = 100.0          # a FUNDED account with less room than this is dead: the bot stops trading it (engine/account_b MIN_ROOM,
                         # multi_account min_room), then MFFU's 7-day rule closes it -> counted as lost and a fresh eval is bought


class BSeat(FP.BSeat):
    """fleet_plan.BSeat (builder_levers.Seat on its trade lists) + a stuck funded account (room < $100 after the session,
    floor at start + $100 after a payout) counted as LOST and replaced by a fresh eval (the research seats left it idle)."""

    def step(self, k, si):
        o0 = self.s.owner
        self.s.step(k, self.BYe[si], self.BYf[si])
        f = self.s.f
        if f is not None and f.state == "on":
            floor = max(f.floor, f.A["lock"]) if f.pays else f.floor
            if f.bal - floor < STUCK_F:
                self.s.lost += 1
                self.s.f = None
                self.s._fresh()
        c, self.c0 = self.s.cost - self.c0, self.s.cost
        return self.s.owner - o0, c

    @property
    def lost(self):
        return self.s.lost


class RSeat:
    """One Rapid EOD slot (tools/money/rapid25.Slot: eval -> 2 sessions -> funded -> lost -> buy again, the fee from its
    spec) that may join late: bought (fee) on its first step, trades from session `join` on."""

    def __init__(self, sp, join=0):
        self.sp, self.join, self.s, self.c0 = sp, join, None, 0.0

    def step(self, k, si):
        if self.s is None:
            self.s = R25.Slot(self.sp)
        if k >= self.join:
            o0 = self.s.owner
            self.s.step(k, si)
            o = self.s.owner - o0
            f = self.s.f
            if f is not None and f.state == "on" and f.bal - f.floor < STUCK_F:     # stuck funded = lost, buy again
                self.s.lost += 1
                self.s.f = None
                self.s._buy()
        else:
            o = 0.0
        c, self.c0 = self.s.cost - self.c0, self.s.cost
        return o, c

    def funded(self):
        return self.s is not None and self.s.f is not None

    @property
    def first_pay(self):
        return self.s.first_pay if self.s is not None else None

    @property
    def lost(self):
        return self.s.lost if self.s is not None else 0


def r25_spec(pol=("cushion", 500.0), atlas=True, lane="skip"):
    """The Rapid EOD 25K as built (LIT + ATLAS $250, keep $500), or LIT alone, or another payout keep / LIT lane rule."""
    if lane != "skip":
        sp = RLL.spec(lane)
        if pol != ("cushion", 500.0):
            raise ValueError("lane variants keep $500")
        return sp
    sp = R25.acct("25k", pol)
    if atlas:
        return sp
    E, F = R25.rules("25k")
    ec, z, mix = sp["ecfg"], {}, ("LIT",)
    sp.update(z=z, BYe=RL.mix_by(mix), BYf=RL.mix_by(mix, news=True), mix_f=mix,
              fund=lambda: RL.Rapid(U.UP25, F, z, pol), ev=lambda: RL.Ev(ec, E, z, "guard"))
    return sp


def r50_spec():
    return R25.acct("50k", ("cushion", 1000.0))


def z50_seat(atlas=False, parallel=False):
    """Zlarior's 50K from its hole; parallel = a FRESH Builder 50K eval bought now next to it on the same signal (MFFU funds
    one Builder 50K: the first pass is kept, the other dropped; builder_levers lever 1 "+ fresh eval now")."""
    B = by()
    fz = BL.F50_LA if atlas else BL.F50_LIT
    ev0 = [BL.GEv(BL.E50, BL.Zlit50(), start=ZLARIOR)] + ([BL.GEv(BL.E50, BL.Zlit50())] if parallel else [])
    s = BL.Seat(lambda _=None: BL.GEv(BL.E50, BL.Zlit50()), lambda: BL.GF("builder50k", U.UP50, fz), P50, ev0,
                cost0=P50 if parallel else 0.0)
    return BSeat(s, B["L"], B["LA"] if atlas else B["L"])


def n25_ev():
    e = B25.Ev25(B25.BASE)
    return e


def n25_seat(ask=None, atlas=False):
    B = by()
    fz = {"LIT": ("fq", None), "ATLAS": ("stack", 250.0, 0.3)} if atlas else {"LIT": ("fq", None)}
    e0 = n25_ev()
    e0.s = 1                                        # Nov 18 = session 1 of the eval (no trade)
    s = BL.Seat(lambda _=None: n25_ev(), lambda: BL.GF("builder25k", U.UP25, fz, ask=ask), P25, [e0])
    return BSeat(s, B["L"], B["S"] if atlas else B["L"])


def a25_funded(z, ask=None):
    f = BL.GF("builder25k", U.UP25, z, ask=ask)
    f.bal = f.trade_pnl = A25_PNL                   # Nov 18: one traded day, -$113 (floor still $24,000)
    f.cyc = [A25_PNL]
    f.first_trade, f.elig_from = "2027-01-01", U.cal(1)    # the 48 h first wait ends on Nov 20 (k = 1)
    return f


def a25_seat(ask=None, lit=False):
    B = by()
    z = {"LIT": ("fq", None), "ATLAS": ("stack", 250.0, 0.3)} if lit else {"ATLAS": ("fq", None)}
    s = BL.Seat(lambda _=None: BL.GEv(BL.E25, BL.Zatlas25(), stuck=200.0), lambda: BL.GF("builder25k", U.UP25, z, ask=ask),
                P25, [])
    s.evals, s.f, s.wait = [], a25_funded(z, ask), 0
    return BSeat(s, B["A"], B["S"] if lit else B["A"])


def r25_seat(**kw):
    return RSeat(r25_spec(**kw), join=R25_JOIN)


def r2_seat():
    return RSeat(r50_spec(), join=0)


BASE = {"Z50": lambda: z50_seat(), "N25": lambda: n25_seat(), "A25": lambda: a25_seat(), "R25": lambda: r25_seat()}
# the variants: decision id -> {account: maker} (one change each; atlas-on-rapid's maker is the NO side = LIT alone)
VARIANTS = {
    "payout-ping-1000": {"A25": lambda: a25_seat(ask=1000.0), "N25": lambda: n25_seat(ask=1000.0)},
    "zlarior-funded25": {"A25": lambda: a25_seat(lit=True)},
    "rapid25-lit-bank": {"R25": lambda: r25_seat(lane="bank1")},
    "atlas-on-50k-funded": {"Z50": lambda: z50_seat(atlas=True)},
    "atlas-on-rapid": {"R25": lambda: r25_seat(atlas=False)},
    "keep-1000-rapid": {"R25": lambda: r25_seat(pol=("cushion", 1000.0))},
    "_n25-atlas-funded": {"N25": lambda: n25_seat(atlas=True)},            # info only (not on the Decide card)
    "ask-mffu-parallel": {"Z50": lambda: z50_seat(parallel=True)},         # what a written yes unlocks (a $91.80 buy)
}
UNLOCKS = {"ask-mffu-parallel"}          # the $ needs a purchase after the yes: never in Claude's picks run
EVAL_SPEC = {"rapid25-lit-bank": lambda: r25_spec(lane="bank1"), "atlas-on-rapid": lambda: r25_spec(atlas=False)}
NO_SIDE = {"atlas-on-rapid"}             # the variant is the NO answer: the value of YES = base - variant


# ================================================================================================ running
def run_fleet(paths, makers, r2=True):
    """Every account on the same paths; R2 bought once payouts in hand (after the tax pot) reach $165."""
    n = len(paths)
    keys = list(makers) + (["R2"] if r2 else [])
    own = {k: np.zeros((n, LEN)) for k in keys}
    fee = {k: np.zeros((n, LEN)) for k in keys}
    fund = {k: np.zeros((n, LEN), dtype=bool) for k in keys}
    lost = {k: np.zeros(n) for k in keys}
    r2_buy = np.full(n, -1)
    for p, seq in enumerate(paths):
        A = {k: m() for k, m in makers.items()}
        paid_net = 0.0
        for k, si in enumerate(seq[:LEN]):
            for nm, a in A.items():
                o, c = a.step(k, si)
                own[nm][p, k], fee[nm][p, k] = o, c
                fund[nm][p, k] = a.funded()
                if nm != "R2":
                    paid_net += o * (1 - TAX)
            if r2 and "R2" not in A and paid_net >= PR50:
                A["R2"] = r2_seat()                  # bought after today's close: trades from the next session
                r2_buy[p] = k + 1
        for nm, a in A.items():
            lost[nm][p] = float(getattr(a, "lost", 0) or getattr(getattr(a, "s", None), "lost", 0) or 0)
    return {"own": own, "fee": fee, "fund": fund, "lost": lost, "r2_buy": r2_buy}


def run_seat(paths, maker):
    n = len(paths)
    own, fee = np.zeros((n, LEN)), np.zeros((n, LEN))
    fund = np.zeros((n, LEN), dtype=bool)
    lost = np.zeros(n)
    for p, seq in enumerate(paths):
        a = maker()
        for k, si in enumerate(seq[:LEN]):
            o, c = a.step(k, si)
            own[p, k], fee[p, k], fund[p, k] = o, c, a.funded()
        lost[p] = float(getattr(a, "lost", 0) or getattr(getattr(a, "s", None), "lost", 0) or 0)
    return {"own": own, "fee": fee, "fund": fund, "lost": lost}


def eval_now(paths, key, h=60, sp=None):
    """The CURRENT eval only (no re-buy), from tonight's state, on the first h sessions of the same paths:
    pass / fail within 10 / 20 / 60 sessions and the median session of a pass (sessions from Nov 19). sp = a Rapid spec
    (a variant) instead of tonight's R25."""
    B = by()
    res = []
    sp = sp or (r25_spec() if key == "R25" else None)
    for seq in paths:
        if key == "Z50":
            e, BYe, off = BL.GEv(BL.E50, BL.Zlit50(), start=ZLARIOR), B["L"], 0
        elif key == "N25":
            e, BYe, off = n25_ev(), B["L"], 0
            e.s = 1
        else:
            e, BYe, off = sp["ev"](), sp["BYe"], R25_JOIN
        out, used = "open", h
        for k, si in enumerate(seq[off:off + h]):
            r, _ = e.step(BYe[si])
            if r:
                out, used = ("pass" if r == "pass" else "fail"), k + 1 + off
                break
        res.append((out, used))
    n = len(res)
    pas = sorted(u for o, u in res if o == "pass")
    return {"p10": round(100.0 * sum(1 for u in pas if u <= 10) / n, 1), "p20": round(100.0 * sum(1 for u in pas if u <= 20) / n, 1),
            "p60": round(100.0 * len(pas) / n, 1), "f60": round(100.0 * sum(1 for o, _ in res if o == "fail") / n, 1),
            "open60": round(100.0 * sum(1 for o, _ in res if o == "open") / n, 1),
            "pass_med": float(np.median(pas)) if pas else None}


# ================================================================================================ stats
def _first(mask_rows):
    return np.array([int(np.argmax(r)) if r.any() else -1 for r in mask_rows])


def acct_stats(own, fee, fund, lost, cal, months, mi):
    n = own.shape[0]
    cash = own - fee
    fp = _first(own > 0)
    got = fp[fp >= 0]
    amt = np.array([own[p, fp[p]] for p in range(n) if fp[p] >= 0])
    ff = _first(fund)
    fg = ff[ff >= 0]
    dec = cal.index(next(d for d in cal if d > "2026-12-31"))
    jan = cal.index(next(d for d in cal if d > "2027-01-31"))
    return {"cash_m": round(float(cash.sum(1).mean()) / MO), "net_m": round(float((own * (1 - TAX) - fee).sum(1).mean()) / MO),
            "cash_6m": round(float(cash.sum(1).mean())), "paid_6m": round(float(own.sum(1).mean())), "fees_6m": round(float(fee.sum(1).mean()), 2),
            "first_pay": cal[int(np.median(got))] if len(got) else None, "first_pay_k": float(np.median(got)) + 1 if len(got) else None,
            "first_pay_p25": cal[int(np.percentile(got, 25))] if len(got) else None,
            "first_pay_p75": cal[int(np.percentile(got, 75))] if len(got) else None,
            "first_pay_usd": round(float(np.median(amt))) if len(amt) else None,
            "p_pay_by_dec31": round(100.0 * float(((fp >= 0) & (fp < dec)).mean()), 1),
            "p_pay_by_jan31": round(100.0 * float(((fp >= 0) & (fp < jan)).mean()), 1),
            "p_no_pay_6m": round(100.0 * float((fp < 0).mean()), 1),
            "funded_med": cal[int(np.median(fg))] if len(fg) else None, "p_funded_6m": round(100.0 * len(fg) / n, 1),
            "lost_6m": round(100.0 * float((lost > 0).mean()), 1),
            "month_cash": [round(float(cash[:, mi == m].sum(1).mean())) for m in range(len(months))]}


def fleet_stats(R, keys, cal, months, mi):
    own = sum(R["own"][k] for k in keys)
    fee = sum(R["fee"][k] for k in keys)
    cash, net = own - fee, own * (1 - TAX) - fee
    rows = []
    for m, mk in enumerate(months):
        sel = mi == m
        cum = net[:, mi <= m].sum(1)
        rows.append({"month": mk, "sessions": int(sel.sum()), "cash_mean": round(float(cash[:, sel].sum(1).mean())),
                     "net_mean": round(float(net[:, sel].sum(1).mean())), "fees_mean": round(float(fee[:, sel].sum(1).mean())),
                     "cum_net_p10": FP.pct(cum, 10), "cum_net_p50": FP.pct(cum, 50), "cum_net_p90": FP.pct(cum, 90)})
    fa = _first(own > 0)
    dec = cal.index(next(d for d in cal if d > "2026-12-31"))
    jan = cal.index(next(d for d in cal if d > "2027-01-31"))
    dn = np.maximum.accumulate(-np.cumsum(net, axis=1), axis=1)[:, -1]
    spring = [i for i, mk in enumerate(months) if mk in ("2027-03", "2027-04")]
    return {"months": rows, "cash_m": round(float(cash.sum(1).mean()) / MO), "net_m": round(float(net.sum(1).mean()) / MO),
            "cash_6m": round(float(cash.sum(1).mean())), "net_6m": round(float(net.sum(1).mean())),
            "net_6m_p10": FP.pct(net.sum(1), 10), "net_6m_p50": FP.pct(net.sum(1), 50), "net_6m_p90": FP.pct(net.sum(1), 90),
            "spring_cash_m": round(sum(rows[i]["cash_mean"] for i in spring) / max(1, len(spring))),
            "spring_net_m": round(sum(rows[i]["net_mean"] for i in spring) / max(1, len(spring))),
            "first_any": cal[int(np.median(fa[fa >= 0]))] if (fa >= 0).any() else None,
            "p_pay_by_dec31": round(100.0 * float(((fa >= 0) & (fa < dec)).mean()), 1),
            "p_no_pay_by_jan31": round(100.0 * float(1 - ((fa >= 0) & (fa < jan)).mean()), 1),
            "p_no_pay_6m": round(100.0 * float((fa < 0).mean()), 1),
            "p_net_negative_6m": round(100.0 * float((net.sum(1) < 0).mean()), 1),
            "pocket_p90": FP.pct(dn, 90), "pocket_p95": FP.pct(dn, 95), "fees_6m": round(float(fee.sum(1).mean()))}


def plain_mixes(sp):
    """Fixed-$ trade stats of the mixes the decisions use (trades / week, PF, $ a month, max DD at $250 a trade)."""
    B = by()
    return {"LIT": BL.plain(B["L"], sp, {"LIT": 250.0}), "ATLAS": BL.plain(B["A"], sp, {"ATLAS": 250.0}),
            "LIT + ATLAS (one account)": BL.plain(B["S"], sp, {"LIT": 250.0, "ATLAS": 250.0})}


# ================================================================================================ the decision values
KEEP_D = ("cash_m", "first_pay", "first_pay_usd", "p_no_pay_6m", "lost_6m", "eval")


def delta(base, var, no_side=False):
    """Change of one account's 6-month numbers (variant - base, or base - variant for a NO-side variant). "with" = the
    numbers when the owner says YES, "without" = when he says NO."""
    a, b = (var, base) if no_side else (base, var)
    return {"usd_month": b["cash_m"] - a["cash_m"], "net_month": b["net_m"] - a["net_m"],
            "first_pay_days": (round(b["first_pay_k"] - a["first_pay_k"], 1) if a["first_pay_k"] and b["first_pay_k"] else None),
            "no_pay_pts": round(b["p_no_pay_6m"] - a["p_no_pay_6m"], 1), "lost_pts": round(b["lost_6m"] - a["lost_6m"], 1),
            "with": {k: b[k] for k in KEEP_D if k in b}, "without": {k: a[k] for k in KEEP_D if k in a}}


def usd(v, sign=False):
    v = round(float(v))
    return ("+" if sign and v > 0 else "-" if v < 0 else "") + "$" + f"{abs(v):,}"


ACCT_WORD = {"Z50": "Zlarior 50K", "N25": "25K #2", "A25": "ATLAS 25K", "R25": "Rapid 25K"}


def risk_words(x):
    """Plain risk words from one decision's per-account deltas in the fair market (YES vs NO)."""
    out = []
    for k, d in (x.get("per_account") or {}).items():
        w, wo = d.get("with") or {}, d.get("without") or {}
        nm = ACCT_WORD.get(k, k)
        for key, word in (("p_no_pay_6m", "no payout in 6 months"), ("lost_6m", "funded account lost")):
            a, b = wo.get(key), w.get(key)
            if a is not None and b is not None and abs(b - a) >= 0.5:
                out.append(f"{nm} {word} {a:g}% -> {b:g}%")
        ea, eb = wo.get("eval") or {}, w.get("eval") or {}
        if ea and eb:
            if abs((eb.get("f60") or 0) - (ea.get("f60") or 0)) >= 0.3:
                out.append(f"{nm} eval fails in 3 months {ea['f60']:g}% -> {eb['f60']:g}%")
            if ea.get("pass_med") and eb.get("pass_med") and abs(eb["pass_med"] - ea["pass_med"]) >= 1:
                out.append(f"{nm} eval passes in about {eb['pass_med']:.0f} trading days instead of {ea['pass_med']:.0f}")
    return out


# the risks each decision really moves (a decision that only changes the eval is judged on the eval: its funded account is
# then simply funded longer, which raises "lost in 6 months" by itself)
RISK_KEYS = {"rapid25-lit-bank": ("eval", "p_no_pay_6m")}


def judge(did, D):
    """-> (recommend, why, risk words, impact line) for one decision from its per-market deltas D[span]."""
    h1, h2, rf = (D.get(s) or {} for s in ("H1", "H2", "REF"))
    if not h2:
        return None
    m1, m2, m3 = h1.get("usd_month", 0), h2.get("usd_month", 0), rf.get("usd_month", 0)
    fd = h2.get("first_pay_days")
    days = ("" if fd is None or abs(fd) < 1 else f"; first payout about {abs(fd):.0f} trading days {'sooner' if fd < 0 else 'later'}")
    imp = f"{usd(m2, True)} a month in a Jul-Oct-like market ({usd(m1, True)} Jan-Jun-like, {usd(m3, True)} 2021-25-like){days}."
    bits = risk_words(h2)
    both_up, both_down = m1 > 0 and m2 > 0, m1 < 0 and m2 < 0
    keys = RISK_KEYS.get(did, ("p_no_pay_6m", "lost_6m"))
    worse_w = []
    for k, d in (h2.get("per_account") or {}).items():
        w, wo = d.get("with") or {}, d.get("without") or {}
        for key in keys:
            if key == "eval":
                a, b = (wo.get("eval") or {}).get("f60"), (w.get("eval") or {}).get("f60")
                word = "its eval fails"
            else:
                a, b = wo.get(key), w.get(key)
                word = {"p_no_pay_6m": "no payout in 6 months", "lost_6m": "the funded account is lost"}[key]
            if a is not None and b is not None and b - a > 2.0:
                worse_w.append(f"{ACCT_WORD.get(k, k)}: {word} {b:.0f} in 100 times instead of {a:.0f}")
    worse = bool(worse_w)
    if did == "atlas-on-rapid":
        rec = "yes" if m2 > 0 and m1 > 0 else "no"
        why = ("Keep ATLAS on the Rapid (it is already built that way): without it the 30% rule skips most of Zlarior's trades "
               "and half of the runs see no payout in 6 months." if rec == "yes"
               else "ATLAS does not pay its way on the Rapid 25K in both 2026 halves: turn it off there.")
    elif did == "keep-1000-rapid":
        rec = "yes" if both_up and not worse else "no"
        why = ("Keep $1,000 in the Rapid 25K too: more money in both halves." if rec == "yes" else
               "Keep $500 on the Rapid 25K (as built): payouts come sooner for about the same money. $1,000 is the safer "
               "choice (fewer accounts lost), so a yes is fine if you prefer safety. A Rapid 50K keeps $1,000 already.")
    elif did == "payout-ping-1000":
        rec = "yes" if m2 >= 0 and m1 >= 0 and not worse else "no"
        why = ("Ask for the full $1,000: the same or a bit more money and fewer small requests." if rec == "yes" else
               "Keep the $750 ping: waiting for $1,000 pays a little less and each payout comes about 2 trading days later.")
    else:
        rec = "yes" if both_up and not worse else "no" if both_down or worse else "later"
        why = {"yes": "More money in both 2026 halves without a real jump in risk.",
               "no": ("More money, but more risk: " + "; ".join(worse_w) + ". Not worth it now." if both_up and worse
                      else "Not worth it: less money in the fair test."),
               "later": "Mixed: it helps in one 2026 half only. Wait for more live trades."}[rec]
    risk = "; ".join(bits) if bits else "about the same risk (the no-payout and lost-account chances move less than 1 point)"
    if m3 < 0:
        risk += f"; in a 2021-25-like market it costs {usd(-m3)} a month"
    return rec, why, risk, imp


STATIC = {
    "ask-mffu-parallel": ("yes", "Free, and it protects every future payout: send the message (Claude drafts it). Buy the fresh "
                                 "50K only when your budget round allows ($91.80).",
                          "None to ask: one support message. Without a written yes, a rules question could hold up payouts."),
    "cloud-alerts": ("yes", "Free, and a silent PC is the biggest threat to the funded accounts (7 days without a trade wipes "
                            "a funded account's profit).",
                     "None: free GitHub minutes on the backup repo; it only reads the PC's report."),
}


# tonight's facts for the items whose old "why" / "applies" described the Rapid 50K or an older model ({...} = filled in)
WHY = {
    "payout-ping-1000": "The bot pings you when $750 sits above the $1,100 buffer; waiting for the full $1,000 (balance $27,100) "
                        "means fewer, bigger requests.",
    "zlarior-funded25": "Two strategies on ATLAS's funded 25K: more trades and a sooner first payout, but bigger swings on a "
                        "$1,000 floor.",
    "atlas-on-rapid": "On the Rapid 25K the 30% best-day rule skips most of Zlarior's trades: alone it passes in about {lit} "
                      "trading days, with ATLAS about {both}.",
    "keep-1000-rapid": "Leaving more in the Rapid after each payout gives the bot more room, so fewer funded accounts get stuck; "
                       "each payout is smaller and comes later.",
}
APPLIES = {
    "atlas-on-rapid": "Rapid preset already built LIT + ATLAS ($250 on the 25K, $500 on a 50K); a no turns ATLAS off there",
    "keep-1000-rapid": "Rapid funded payout rule: the 25K keeps $500 above the buffer today (a yes raises it to $1,000); the 50K "
                       "preset keeps $1,000 already",
}


def decision_values(res):
    out = {}
    for did in DECIDE_IDS:
        if did in UNLOCKS:
            rec, why, risk = STATIC[did]
            D = {sp: res["rows"][sp]["decisions"].get(did) or {} for sp in SPANS}
            m1, m2, m3 = (int((D[sp] or {}).get("usd_month") or 0) for sp in ("H1", "H2", "REF"))
            fd = (D["H2"] or {}).get("first_pay_days")
            out[did] = {"usd_month": m2, "usd_month_by": {"jan_jun": m1, "jul_oct": m2, "y2021_25": m3}, "risk": risk,
                        "recommend": rec, "recommend_why": why, "unlocks": True,
                        "impact": (f"Free to ask. A written yes lets you run a fresh Builder 50K ($91.80) next to Zlarior's: "
                                   f"{usd(m2, True)} a month Jul-Oct-like ({usd(m1, True)} Jan-Jun-like, {usd(m3, True)} 2021-25-like)"
                                   + (f", the 50K's first payout about {abs(fd):.0f} trading days {'sooner' if fd < 0 else 'later'}"
                                      if fd is not None and abs(fd) >= 1 else "") + ". It also protects every payout from a rules dispute.")}
            continue
        if did in STATIC:
            rec, why, risk = STATIC[did]
            out[did] = {"usd_month": 0, "usd_month_by": {"jan_jun": 0, "jul_oct": 0, "y2021_25": 0}, "risk": risk,
                        "recommend": rec, "recommend_why": why}
            continue
        D = {sp: res["rows"][sp]["decisions"].get(did) for sp in SPANS}
        j = judge(did, D)
        if not j:
            continue
        rec, why, risk, imp = j
        out[did] = {"usd_month": int(D["H2"]["usd_month"]),
                    "usd_month_by": {"jan_jun": int(D["H1"]["usd_month"]), "jul_oct": int(D["H2"]["usd_month"]),
                                     "y2021_25": int(D["REF"]["usd_month"])},
                    "risk": risk, "recommend": rec, "recommend_why": why, "impact": imp}
    for did, w in WHY.items():
        if did in out:
            ev = (((res["rows"]["H2"]["decisions"].get(did) or {}).get("per_account") or {}).get("R25") or {})
            both = ((ev.get("with") or {}).get("eval") or {}).get("pass_med")
            lit = ((ev.get("without") or {}).get("eval") or {}).get("pass_med")
            out[did]["why"] = w.format(lit=f"{lit:.0f}" if lit else "?", both=f"{both:.0f}" if both else "?")
    for did, a in APPLIES.items():
        if did in out:
            out[did]["applies"] = a
    return out


# ================================================================================================ main study
def study(n=1000, log=print):
    import logging
    logging.getLogger("engine.sizing").setLevel(logging.ERROR)
    import payout_plan as PP
    cal = PP.calendar(LEN + 5, START)
    months = sorted({d[:7] for d in cal[:LEN]})
    mi = np.array([months.index(d[:7]) for d in cal[:LEN]])
    S = SA.data()["S"]
    by()
    res = {"v": 2, "date": TODAY, "start": START, "end": cal[LEN - 1], "n": n, "sessions": LEN, "markets": MKT, "months": months,
           "prices": {"builder50k": P50, "builder25k": P25, "rapid_eod25k": PR25, "rapid_eod50k": PR50}, "tax": TAX,
           "budget": BUDGET, "now": NOW, "names": NAMES, "spans": U.SPAN, "rows": {}}
    t0 = time.time()
    for sp in SPANS:
        t1 = time.time()
        paths = U.mc_paths(S, sp, n, length=LEN, seed=BL.A4.SEED_LIFE)
        R = run_fleet(paths, BASE)
        acc = {k: acct_stats(R["own"][k], R["fee"][k], R["fund"][k], R["lost"][k], cal, months, mi) for k in R["own"]}
        rb = R["r2_buy"]
        acc["R2"]["buy_med"] = cal[int(np.median(rb[rb >= 0]))] if (rb >= 0).any() else None
        acc["R2"]["p_bought"] = round(100.0 * float((rb >= 0).mean()), 1)
        ev = {k: eval_now(paths, k) for k in ("Z50", "N25", "R25")}
        for k, e in ev.items():
            e["pass_date"] = cal[int(e["pass_med"]) - 1] if e["pass_med"] else None
            acc[k]["eval"] = e
        a5 = _first(np.all([R["fund"][k] for k in list(BASE) + ["R2"]], axis=0))     # all five funded on the same session
        row = {"accounts": acc, "fleet": {"four": fleet_stats(R, list(BASE), cal, months, mi),
                                          "five": fleet_stats(R, list(BASE) + ["R2"], cal, months, mi)},
               "fill5": {"p_all5_6m": round(100.0 * float((a5 >= 0).mean()), 1),
                         "all5_med": cal[int(np.median(a5[a5 >= 0]))] if (a5 >= 0).any() else None},
               "decisions": {}, "info": {}, "plain": plain_mixes(sp)}
        log(f"{sp} base fleet {time.time() - t1:.0f}s: 4 accts ${row['fleet']['four']['cash_m']:,}/mo cash "
            f"(${row['fleet']['four']['net_m']:,} after tax), 5 accts ${row['fleet']['five']['cash_m']:,}/mo; first any "
            f"{row['fleet']['four']['first_any']}; R2 bought {acc['R2']['buy_med']} ({acc['R2']['p_bought']}%)")
        for k, a in acc.items():
            log(f"    {NAMES[k]:24s} ${a['cash_m']:>6,}/mo 1st pay {a['first_pay']} (${a['first_pay_usd']}) by Jan31 {a['p_pay_by_jan31']}% "
                f"none {a['p_no_pay_6m']}% funded {a['funded_med']} ({a['p_funded_6m']}%) lost {a['lost_6m']}%"
                + (f" | eval now: pass {a['eval']['p60']}% in 60 (fail {a['eval']['f60']}%), med {a['eval']['pass_med']} = {a['eval']['pass_date']}"
                   if "eval" in a else ""))
        for did, mk in VARIANTS.items():
            dd = {}
            for k, maker in mk.items():
                V = run_seat(paths, maker)
                vs = acct_stats(V["own"], V["fee"], V["fund"], V["lost"], cal, months, mi)
                if did in EVAL_SPEC:
                    vs["eval"] = eval_now(paths, k, sp=EVAL_SPEC[did]())
                dd[k] = delta(acc[k], vs, did in NO_SIDE)
            tot = {"usd_month": sum(x["usd_month"] for x in dd.values()), "net_month": sum(x["net_month"] for x in dd.values())}
            k0 = max(dd, key=lambda k: abs(dd[k]["usd_month"]))
            one = {**dd[k0], **tot, "per_account": dd} if len(dd) > 1 else {**dd[k0], "per_account": dd}
            (row["info"] if did.startswith("_") else row["decisions"])[did] = one
            log(f"    {did:22s} {'+' if one['usd_month'] >= 0 else ''}{one['usd_month']}/mo, first pay {one['first_pay_days']} d, "
                f"no-pay {one['no_pay_pts']:+} pts, lost {one['lost_pts']:+} pts ({time.time() - t1:.0f}s)")
        res["rows"][sp] = row
    # Claude's picks (every recommendation applied) on the same paths: one more fleet run
    vals = decision_values(res)
    res["decision_values"] = vals
    rec = {d: v.get("recommend") for d, v in vals.items()}
    picks = {k: _combo(k, rec) for k in BASE}
    res["picks"] = {d: r for d, r in rec.items() if d in VARIANTS and d not in UNLOCKS and not d.startswith("_")}
    for sp in SPANS:
        paths = U.mc_paths(S, sp, n, length=LEN, seed=BL.A4.SEED_LIFE)
        R = run_fleet(paths, picks)
        res["rows"][sp]["picks"] = {"four": fleet_stats(R, list(BASE), cal, months, mi),
                                    "five": fleet_stats(R, list(BASE) + ["R2"], cal, months, mi),
                                    "accounts": {k: acct_stats(R["own"][k], R["fee"][k], R["fund"][k], R["lost"][k], cal, months, mi)
                                                 for k in R["own"]}}
        p4 = res["rows"][sp]["picks"]["four"]
        log(f"{sp} with Claude's picks {res['picks']}: 4 accts ${p4['cash_m']:,}/mo (${p4['net_m']:,} after tax)")
    log(f"{time.time() - t0:.0f}s")
    return res


def _combo(k, rec):
    """One account with every recommendation that touches it (rec: decision id -> yes / no / later)."""
    yes = lambda d: rec.get(d) == "yes"                                  # noqa: E731
    ask = 1000.0 if yes("payout-ping-1000") else None
    if k == "A25":
        return lambda: a25_seat(ask=ask, lit=yes("zlarior-funded25"))
    if k == "N25":
        return lambda: n25_seat(ask=ask)
    if k == "Z50":
        return lambda: z50_seat(atlas=yes("atlas-on-50k-funded"))
    if k == "R25":
        atlas = rec.get("atlas-on-rapid") != "no"
        lane = "bank1" if yes("rapid25-lit-bank") and atlas else "skip"
        pol = ("cushion", 1000.0) if yes("keep-1000-rapid") and lane == "skip" else ("cushion", 500.0)
        return lambda: r25_seat(pol=pol, atlas=atlas, lane=lane)
    return BASE[k]


# ================================================================================================ the page + the Decide card
def page(res):
    """plan.json for business/plan.html: small, every number the page shows, nothing private."""
    out = {k: res[k] for k in ("v", "date", "start", "end", "n", "sessions", "markets", "months", "prices", "tax", "budget", "now", "names", "picks")}
    out["kind"], out["built_by"] = "olympus-money-plan", "tools/money/money_plan.py"
    out["rows"] = {}
    for sp, r in res["rows"].items():
        keep = ("cash_m", "net_m", "cash_6m", "first_pay", "first_pay_p25", "first_pay_p75", "first_pay_usd", "p_pay_by_dec31",
                "p_pay_by_jan31", "p_no_pay_6m", "funded_med", "p_funded_6m", "lost_6m", "fees_6m", "buy_med", "p_bought", "eval")
        out["rows"][sp] = {"accounts": {k: {kk: v for kk, v in a.items() if kk in keep} for k, a in r["accounts"].items()},
                           "fleet": r["fleet"], "fill5": r["fill5"], "picks": {k: r["picks"][k] for k in ("four", "five")},
                           "info": {d: {kk: v for kk, v in x.items() if kk != "per_account"} for d, x in r["info"].items()},
                           "decisions": {d: {kk: v for kk, v in x.items() if kk != "per_account"} for d, x in r["decisions"].items()}}
    out["decision_values"] = res["decision_values"]
    return out


def write_decisions(vals, path=DECISIONS, today=TODAY):
    """Write ONLY the value fields of the items this tool values; every other item / field stays as it is (other helpers add
    their own proposals to the same file)."""
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    for it in doc.get("items") or []:
        v = vals.get(it.get("id"))
        if not v:
            continue
        for k in ("usd_month", "usd_month_by", "risk", "recommend", "recommend_why"):
            it[k] = v[k]
        for k in ("why", "applies", "unlocks"):
            if v.get(k) is not None:
                it[k] = v[k]
        if v.get("impact"):
            it["impact"] = v["impact"]
        it["impact_usd"] = int(v["usd_month"])
        it["valued"] = f"{today} tools/money/money_plan.py (same paths for every account; $ a month to you after fees and MFFU's cut, before the 30% tax pot)"
    doc["updated"] = today
    raw = json.dumps(doc, ensure_ascii=False, indent=1)
    with open(path + ".tmp", "w", encoding="utf-8") as fh:
        fh.write(raw + "\n")
    os.replace(path + ".tmp", path)
    return path


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--no-save", action="store_true")
    ap.add_argument("--no-decisions", action="store_true", help="do not touch business/decisions.json")
    a = ap.parse_args(argv)
    res = study(a.n)
    for d, v in res["decision_values"].items():
        print(f"  {d:22s} {v['recommend']:5s} {v.get('impact') or ''} | risk: {v['risk']}")
    if not a.no_save:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=1, default=float)
        with open(PAGE, "w", encoding="utf-8") as fh:
            json.dump(page(res), fh, separators=(",", ":"), default=float)
        print("wrote", os.path.relpath(OUT, ROOT), "and", os.path.relpath(PAGE, ROOT))
        if not a.no_decisions:
            print("wrote", os.path.relpath(write_decisions(res["decision_values"]), ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
