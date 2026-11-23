"""BLITZ on the Rapid EOD 25K EVAL (owner YES 2026-11-23 ~16:35 ET, "Yes add it"): a 3rd lane on the Rapid's ONE NinjaTrader
account, next to LIT's lane (engine/multi_account, lane "rapid") and ATLAS's lane (engine/rapid.RapidAtlas). EVAL ONLY: no new
BLITZ entry once the Rapid is funded (stage "funded" in data/rapid.json), on a Rapid EOD 50K, or with "blitz": false.

Research (research/writeups/prop-economics-2026-11-23.md, research/propecon/; picked on 2026 Jan-Jun, checked Jul-Oct and
2021-25; one position per account enforced): the 30% best-day rule makes the Rapid 25K eval slow; BLITZ's extra small winning
days pass it sooner. Rapid 25K eval, 2,000 paths x 60 sessions, BLITZ trades overlapping LIT / ATLAS dropped:
    today (LIT + ATLAS)    pass 80.5% / 85.5% / 7.5%   fail 0.5% / 2.0% / 77.0%   median 33 / 26 / 29 sessions
    + this BLITZ lane      pass 81.5% / 93.0% / 13.9%  fail 3.1% / 1.9% / 81.8%   median 26 / 19 / 22 sessions
(Jan-Jun / Jul-Oct / 2021-25). Sizing alone (LIT / ATLAS x2) gave nothing; this lane is the whole gain.

What runs: engine/account_c.AccountC's code (BLITZ's live Engine on the closed 1m bars, its exits, trailing stop, 6 trades a
day, -3R day stop, the performance contract, the early-close and 15:55 flats, never-placed handling) on the Rapid's account,
with its own order-file tag "acctrb_" (2nd Rapid: "acctrb2_") and state file live_state_acctrb*.json. What differs from C:
  * SIZE = the validated research lane (tools/money/stack_one_account.stack_q, z BLITZ {"usd": 300, "f": 0.3}):
    $ = min($300, 30% of the account's room, the $500 soft day left), micros = $ / one full stop-out of 1 micro
    ((stop + 1 tick) x $2 + $1.90), at most the plan's 20 micros; then the 30% best-day cap (engine/rapid.best_day_cap: a
    2R winner keeps the day <= 30% x $1,500 x 0.95 = $427 incl. today's closed $ of all three lanes).
  * ONE BOOK: balance, EOD trailing floor, room, today's $, the soft day lock and the pass check are the SUM of the three
    lanes' closes (LIT's lane and ATLAS read BLITZ's closes too). No pass / fail push of its own (LIT's lane and ATLAS
    report the account).
  * ONE POSITION ON THE ACCOUNT, priority LIT > ATLAS > BLITZ: no BLITZ entry while LIT's lane or ATLAS holds / closes /
    shows a NinjaTrader leg here, or LIT is in / entering a trade (any side); LIT's lane or ATLAS entering while BLITZ holds
    closes BLITZ at market FIRST and routes only once that close is CONFIRMED flat (yield_to_lit, any side).
  * NO HEDGE ACROSS ACCOUNTS: AccountC.opposite (LIT's 50K, account B, the extra accounts, hand trades, the fleet) + account C
    and the other Rapid's lanes; every other account's entry closes this lane first when it holds the other side.

    python -X utf8 -m engine.rapid --blitz off      (on = the default on a Rapid EOD 25K eval)
"""
from __future__ import annotations

import os

from . import account_c as AC
from . import rapid as RP

BLITZ_USD, BLITZ_F = 300.0, 0.3          # research z BLITZ {"usd": 300, "f": 0.3} (research/propecon/unit.py book_name)
SLIP = 0.25                              # stack_q: one full stop-out = (stop + 1 tick) x $2 + $1.90
ELIGIBLE = ("mffu_rapid_eod_25k",)       # owner: the Rapid EOD 25K EVAL only


def wanted(blk: dict | None) -> tuple:
    """(True, "") when the Rapid block gets the BLITZ lane, else (False, why)."""
    if not blk:
        return False, "no Rapid"
    if blk.get("blitz") is False:
        return False, "switched off (data/rapid.json \"blitz\": false)"
    P = RP.plan_info(blk)
    if P["preset"] not in ELIGIBLE:
        return False, f"{P['label']}: BLITZ runs on the Rapid EOD 25K eval only"
    if str(blk.get("stage") or "eval") != "eval":
        return False, "the Rapid is funded: BLITZ is eval-only"
    return True, ""


def _state_path(bot_state_path: str | None, slot: str = "rapid") -> str:
    p = bot_state_path or os.path.join(RP.ROOT, "data", "live_state.json")
    base, ext = os.path.splitext(p)
    return base + ("_acctrb2" if slot == "rapid2" else "_acctrb") + (ext or ".json")


def spec_of(blk: dict, lit_account=None, b_account=None) -> dict | None:
    """account_c.normalize on the Rapid's Name, then the Rapid's own rules / labels."""
    from . import multi_account as MA
    P = RP.plan_info(blk)
    s = AC.normalize({"account": blk.get("account"), "plan": "builder25k", "eval_start": blk.get("eval_start") or "",
                      "armed": blk.get("armed") is True}, lit_account=lit_account, b_account=b_account)
    if s is None:
        return None
    s["preset"] = P["preset"]
    s["rules"] = MA.rules_of({"preset": P["preset"]})
    s["plan_label"] = f"{P['label']} eval (BLITZ lane)"
    s["label"] = f"BLITZ Rapid {s['account'] or '?'}"
    s["min_room"] = float(P["eval_min_room"])
    s["stage"] = "eval"
    s["rapid_plan"] = P["preset"]
    return s


class RapidBlitz(AC.AccountC):
    """BLITZ on the Rapid EOD 25K eval (LiveBot.acct_rb / acct_rb2): account C's code on the Rapid's account."""

    def __init__(self, bot, spec, blk, slot: str = "rapid", state_path=None, adapter_factory=None):
        self.slot = "rapid2" if slot == "rapid2" else "rapid"
        self.blk = dict(blk or {})
        self.P = RP.plan_info(self.blk)
        super().__init__(bot, spec, state_path=state_path or _state_path(getattr(bot, "state_path", None), self.slot),
                         adapter_factory=adapter_factory)
        self.label = self.spec["label"]

    # ---- plumbing
    def tag(self) -> str:
        return "acctrb2" if self.slot == "rapid2" else "acctrb"

    def adapter_cfg(self) -> dict:
        c = super().adapter_cfg()
        d = os.path.dirname(self.state_path) if self.state_path else os.path.join(RP.ROOT, "data")
        log_dir = os.path.join(RP.ROOT, "logs") if self.real_bot() else d
        t = self.tag()
        return {**c, "nt_file_tag": t + "_", "nt_state_path": os.path.join(d, f"ninjatrader_state_{t}.json"),
                "nt_audit_log": os.path.join(log_dir, f"ninjatrader_oif_{t}.log")}

    def _push_text(self, title, body, key):
        return super()._push_text(title, body, f"rapidblitz:{key}")

    # ---- the other lanes on this account
    def lane(self):
        ac = getattr(self.bot, "accts", None)
        return next((a for a in (getattr(ac, "accounts", None) or []) if a.spec.get("lane") == "rapid"
                     and RP.slot_of(a.spec) == self.slot), None)

    def atlas(self):
        return getattr(self.bot, "acct_r2" if self.slot == "rapid2" else "acct_r", None)

    def sharers(self) -> list:
        return [x for x in (self.lane(), self.atlas()) if x is not None]

    def all_closes(self) -> list:
        out = [list(c) for c in self.closes]
        for x in self.sharers():
            out += [list(c) for c in (getattr(x, "closes", None) or [])]
        return out

    def day_pnl(self, day) -> float:
        return round(sum(float(c[2]) for c in self.all_closes() if c[0] == day), 2)

    def eval_only_block(self) -> str | None:
        """Why this lane takes no new entry from the Rapid's file now (re-read each entry: a switch to funded / off while the
        bot runs stops BLITZ at once; the open trade is still managed to its exit). The test harness passes its block."""
        try:
            b = RP.read(RP.slot_path(self.slot)) if self.real_bot() else self.blk
        except Exception as e:
            return f"Rapid file unreadable ({e.__class__.__name__}): fails closed"
        if not b or str(b.get("account") or "").strip() != self.name:
            return "the Rapid's account changed or was removed"
        ok, why = wanted(b)
        return None if ok else why

    # ---- one book (the account's three lanes)
    def _state_raw(self, now=None):
        from . import multi_account as MA
        today = AC.trading_day(now if now is not None else self.clock())
        if not self.spec.get("eval_start"):
            return None
        return MA.sizing_state("two_week", [(d, t, p) for d, t, p, *_ in self.all_closes()], today, self.spec["eval_start"],
                               self.rules, prior=float(self.spec.get("prior_pnl") or 0.0), n_today=self.entries_today(today),
                               anchor=self.anchor())

    def _broker(self):
        return None                       # LIT's lane reads the account's real balance (one account, one check)

    def broker_tick(self, now):
        return None

    def days(self, today=None) -> dict:
        start = self.spec.get("eval_start")
        out = {}
        for d, _, p, *_ in self.all_closes():
            if start and str(d) >= str(start) and (today is None or str(d) <= today):
                out[str(d)] = round(out.get(str(d), 0.0) + float(p), 2)
        return out

    def eval_view(self, now=None) -> dict:
        ev = super().eval_view(now)
        if ev.get("status") != "passed":
            return ev
        today = AC.trading_day(now if now is not None else self.clock())
        dd = {d: v for d, v in self.days(today).items() if abs(v) > 1e-9}
        prof = float(ev.get("profit") or 0.0)
        best = max(dd.values()) if dd else 0.0
        if len(dd) < RP.MIN_DAYS or best > RP.BEST_DAY * prof + 1e-9:
            ev = {**ev, "status": "open", "pass_wait": f"{len(dd)} of {RP.MIN_DAYS} days, best day ${best:,.0f} vs 30% ${RP.BEST_DAY * prof:,.0f}"}
        return ev

    def _lifecycle(self, now):
        """No pass / fail / stuck push of its own: LIT's lane and ATLAS report the Rapid (one account). The size stops."""
        return None

    # ---- size: the validated research lane
    def size_entry(self, risk, state, x=None) -> dict:
        R = self.rules
        why0 = self.eval_only_block()
        if why0:
            return {"qty": 0, "reasons": [why0]}
        if state is None:
            return {"qty": 0, "reasons": ["eval state unknown (eval_start missing?): not traded"]}
        r = AC._num(risk)
        if not r or r <= 0:
            return {"qty": 0, "reasons": ["no stop distance"]}
        room = AC._num(state.get("room"), 0.0)
        cum = AC._num(state.get("cum"), 0.0)
        if room <= 0:
            return {"qty": 0, "reasons": [f"room ${room:,.0f} to the floor: no trade"]}
        if float(state.get("profit") or 0.0) + cum >= float(R["target"]):
            return {"qty": 0, "reasons": ["eval target reached: no new trade"]}
        q, usd, loss1 = RP.stack_qty(r, room, cum, int(R["max_micros"]), float(R["dll"]), BLITZ_USD, SLIP)
        why = [f"${usd:,.0f} risk (min ${BLITZ_USD:,.0f}, 30% of the ${room:,.0f} room, the ${float(R['dll']):,.0f} day left) / "
               f"${loss1:,.2f} a micro -> {q}"]
        if q > 0:
            q2, cap = RP.best_day_cap(q, None, r, float(R["target"]), self.day_pnl(AC.trading_day(self.clock())))
            if q2 < q:
                why.append(f"best-day rule 30%: a 2R winner pays <= ${cap:,.0f} -> {q2}")
                q = q2
        return {"qty": int(q), "reasons": why}

    # ---- one position on the account, no hedge across accounts
    def same_account_busy(self) -> str | None:
        b = self.bot
        st = getattr(b, "state", None) or {}
        if st.get("position"):
            return "LIT is in a trade (its Rapid lane takes it)"
        if st.get("enter_now"):
            return "LIT is entering a trade (its Rapid lane takes it)"
        ln = self.lane()
        if ln is not None:
            if getattr(ln, "open_t", None) is not None:
                return "LIT's lane holds a trade on this account"
            try:
                lg = RP._open_leg(getattr(ln, "adapter", None))
            except Exception:
                return "LIT's lane: NinjaTrader state unreadable (fails closed)"
            if lg:
                return f"LIT's lane still shows a {lg.get('status')} bracket at NinjaTrader (not confirmed flat)"
        at = self.atlas()
        if at is not None:
            try:
                if at.open_t is not None:
                    return "ATLAS holds a trade on this account"
                if at.closing_open():
                    return "ATLAS's close on this account is not confirmed yet"
                lg = RP._open_leg(getattr(at, "adapter", None))
                if lg:
                    return f"ATLAS's lane still shows a {lg.get('status')} bracket at NinjaTrader (not confirmed flat)"
            except Exception:
                return "ATLAS's lane state unreadable (fails closed)"
        return None

    def opposite(self, d: int):
        """One position on this account first (LIT > ATLAS > BLITZ), then account C's no-hedge checks of every other account
        (LIT's 50K, account B, the extra accounts, hand trades, account C / the other Rapid's lanes, the fleet)."""
        return self.same_account_busy() or super().opposite(d)

    def yield_to_lit(self, d: int, sym: str, now: int, px=None, any_side: bool = False) -> bool:
        """LIT's lane / ATLAS on THIS account is about to enter (any_side=True): BLITZ's position here, either side, is closed at
        market first. True = flat and no BLITZ leg open at NinjaTrader. any_side=False = the opposite side only (another account)."""
        if not any_side:
            return self.yield_to(d, "LIT", sym, now, px=px)
        with self.mx:
            try:
                self.reconcile_unplaced(now)
            except Exception:
                pass
            if self.closing_open():
                self.settle_closing(sym, now)
                if self.closing_open():
                    return False
            if self.open_t is not None:
                et_ = int(self.open_t)
                pv = self.prov.get(et_) or {}
                self.log("risk", f"{'LONG' if int(d) == 1 else 'SHORT'} entry by a higher lane on {self.name}: BLITZ's trade here is "
                                 "closed at market first (one position per account: LIT > ATLAS > BLITZ)")
                if self.flatten(et_, "HEDGE", sym, now, px=AC._num(px)):
                    pv["final"] = True
                if self.open_t is not None and int(self.open_t) == et_:
                    return False
            try:
                return RP._open_leg(self.adapter) is None
            except Exception:
                return False


def build(bot, blk: dict | None, slot: str = "rapid", **kw):
    """LiveBot: BLITZ's lane of a Rapid (None when the block does not get it)."""
    ok, _ = wanted(blk)
    if not ok:
        return None
    lit_acct = b_acct = None
    try:
        if (bot.cfg or {}).get("adapter") == "ninjatrader":
            from .ninjatrader import resolve_account
            lit_acct = resolve_account(bot.cfg)
        b_acct = getattr(getattr(bot, "acct_b", None), "name", None)
    except Exception:
        pass
    spec = spec_of(blk, lit_account=lit_acct, b_account=b_acct)
    return RapidBlitz(bot, spec, blk, slot=slot, **kw).start() if spec else None
