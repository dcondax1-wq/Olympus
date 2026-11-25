"""ATLAS + Zlarior on ONE extra Builder account: the Builder 25K #2 (owner 2026-11-23 "Yes do it": the combo on BOTH Zlarior
accounts). BUILT, OFF BY DEFAULT. The 50K (the bot's own account) is engine/combo50k.py; this file is the same rules on an
extra account of engine/multi_account (the start cfg / data/accounts.json entry with preset mffu_builder_25k).

ON / OFF: the same owner's switch file data/combo_50k.json (local, gitignored), its "accounts" list:
    python -X utf8 -m engine.combo50k --on --account "<the 25K #2's NinjaTrader Name>"     (types I ACCEPT LIVE RISK)
    python -X utf8 -m engine.combo50k --off --account "<the 25K #2's NinjaTrader Name>"    (that account only)
Claude never writes it. Not in the list (or no file) = OFF = the bot is exactly today's: no lane object exists, every hook
below is "no lane" = today's code path. Test harnesses: the account entry's own "combo" key (rule values or True), honoured
only when the bot is not the real one (the PC's switch is never read by a harness, a harness key never counts on the PC).

What runs on that account while ON (the 50K's rules, research/lab/combo_50k.json, sized on the 25K's numbers):
  LIT lane    the extra account itself (engine/multi_account.Account): Zlarior's LIT signals, sized as today (two_week on the
              mffu_builder_25k preset: 40% of the room, $600 soft day, 20 micros), on the account's ONE book (its closes + ATLAS's).
  ATLAS lane  ComboAtlas below (engine/account_b code on the SAME NinjaTrader account, its own order tag "<id>x_"): ATLAS's raw
              stream (engine/combo50k.atlas_pick: one ATLAS trade at a time, max 2 a day, EMA > MACD > S/R on a tie), sized by
              engine/combo50k.atlas_qty on the builder25k preset (need size in the eval, funded_qty once funded) x
              atlas_size_factor (eval 0.5, funded 1.0), max 20 micros; no ATLAS entry under $200 of eval room ($100 funded).
  ONE position on the account, first_in: while either bot holds it (a position, an entry going out, a bracket still open at
  NinjaTrader) the other bot's entry is skipped; a Zlarior signal whose entry falls inside ATLAS's trade (entry <= it < ATLAS's
  exit) is skipped on this account (the simulator's rule), also when that ATLAS trade was closed early.
  ONE direction across every account (no hedging): ATLAS here never opens against LIT / ATLAS / BLITZ / a follower elsewhere;
  LIT entering the other way on ANOTHER account closes ATLAS here at market first (LIT > ATLAS, as the Rapid's ATLAS lane and
  ATLAS's 25K); the other accounts see this lane like the Rapid's (others_opposite, hand-trade check, update wait).
  Shared room: one balance, one trailing floor, one day $ (Account.all_closes / ComboAtlas.all_closes).

Parity proof: tests/test_combo_25k.py replays 2026 days through the REAL LiveBot (fake NinjaTrader, a Sim 50K primary + a Sim
25K #2) and checks the 25K's trade list == tools/money/combo_account.Eval (b25, Z+A, first, ATLAS x0.5) on the same days.
"""
from __future__ import annotations

import os

from . import account_b as AB
from . import combo50k as CB
from .rapid import RapidAtlas, _open_leg

PLAN_OF = {"mffu_builder_25k": "builder25k", "mffu_builder_50k": "builder50k"}
TAG = "x"                      # the ATLAS lane's NinjaTrader order-file tag: "<account id>x_"


def _num(x, d=None):
    try:
        v = float(x)
        return d if v != v else v
    except (TypeError, ValueError):
        return d


def label_of(acc) -> str:
    return f"ATLAS on {getattr(acc, 'name', None) or 'the extra account'}"


def spec_for(bot, acc) -> dict | None:
    """The combo spec for this extra account, None = OFF (today's account), or {"off_why"} (on but not usable). Real bot: the
    owner's switch lists the account's NinjaTrader Name. Harness: the account entry's own "combo" key."""
    s = getattr(acc, "spec", None) or {}
    if getattr(acc, "problem", None) is not None:
        return None
    plan = PLAN_OF.get(str(s.get("preset") or ""))
    if s.get("lane"):
        return None                                   # the Rapid / LIT-on-the-25K lanes have their own ATLAS
    try:
        real = acc.router.real_bot()
    except Exception:
        real = True
    over = s.get("combo")
    if not real:
        if not over:
            return None
        rules = CB.normalize({k: v for k, v in over.items() if k != "time_size"} if isinstance(over, dict) else {},
                             plan=plan or CB.PLAN)
        src = "account entry 'combo' (test harness)"
        tsz = AB.time_size_norm(over.get("time_size")) if isinstance(over, dict) else None
    else:
        nm = str(s.get("nt_account") or "").strip()
        if not CB.switch_on_for(nm):
            return None
        rules = CB.load_rules(plan=plan or CB.PLAN)
        src = CB.SWITCH_REL
        tsz = AB.read_time_size()
    if plan is None:
        return {"off_why": f"{acc.name}: the combo is built for the Builder 25K / 50K presets, not {s.get('preset')}: OFF"}
    if s.get("adapter") == "ninjatrader" and not str(s.get("nt_account") or "").strip():
        return {"off_why": f"{acc.name}: no NinjaTrader Name: OFF"}
    if rules.get("problem"):
        return {"off_why": f"{acc.name}: combo rules not usable ({rules['problem']}): OFF"}
    out = {"on": True, "account": s.get("nt_account") or acc.id, "acc_id": acc.id, "plan": plan, "conflict": rules["conflict"],
           "atlas_size_factor": dict(rules["atlas_size_factor"]), "guards": dict(rules["guards"]),
           "unknown": list(rules.get("unknown") or []), "keys": list(CB.MEMBERS), "label": label_of(acc), "src": src,
           "max_micros": 40}
    if tsz:
        out["time_size"] = tsz                         # engine/account_b time_size (OFF = absent = today's spec)
    return out


def ab_block(acc, combo) -> dict:
    """The engine/account_b block of the ATLAS lane: the account's Name, the combo's plan, its eval / funded start."""
    s = acc.spec
    b = {"account": s.get("nt_account") or acc.id, "plan": combo["plan"], "eval_start": s.get("eval_start") or "",
         "strategies": list(CB.MEMBERS), "armed": s.get("armed") is True, "prior_pnl": float(s.get("eval_prior_pnl") or 0.0)}
    if s.get("mode") == "funded":
        F = s.get("funded") or {}
        b.update({"stage": "funded", "funded_start": F.get("start") or "", "payouts": dict(F.get("payouts") or {})})
        if F.get("balance") is not None:
            b["funded_balance"] = F.get("balance")
    return b


def build(bot, acc, combo, adapter_factory=None):
    spec = AB.normalize(ab_block(acc, combo), lit_account=None)
    if not spec:
        return None
    return ComboAtlas(bot, acc, combo, spec, adapter_factory=adapter_factory).start()


class ComboAtlas(RapidAtlas):
    """ATLAS on an extra Builder account (LiveBot.acct_x[acc.id]): account B's code on the SAME NinjaTrader account as the
    LIT lane, first_in on one position (engine/rapid.RapidAtlas's book / lane plumbing; LIT priority only ACROSS accounts)."""
    PUSH_SUFFIX = ":acctx"
    combo_lane = True
    START_CMDS = {"eval": 'python -X utf8 -m engine.multi_account --set --id {name} --eval-start <first eval day yyyy-mm-dd>',
                  "funded": 'python -X utf8 -m engine.multi_account --set --id {name} --mode funded --funded-start <first funded day>'}

    def __init__(self, bot, acc, combo, spec, state_path=None, adapter_factory=None):
        self.acc_id = acc.id
        self.combo = combo
        self.slot = f"combo:{acc.id}"
        self.PUSH_SUFFIX = f":{acc.id}:acctx"
        sp = state_path or _state_path(getattr(bot, "state_path", None), acc.id)
        AB.AccountB.__init__(self, bot, spec, state_path=sp, adapter_factory=adapter_factory)
        self.P = {"plan": combo["plan"], "label": acc.name}
        self.label = label_of(acc)
        self.spec["label"] = self.label

    # ---- the LIT lane on this account (the extra account object)
    def lane(self):
        ac = getattr(self.bot, "accts", None)
        return next((a for a in (getattr(ac, "accounts", None) or []) if a.id == self.acc_id), None)

    def life_key(self) -> str:
        ln = self.lane()
        return ln.life_key() if ln is not None else f"x:{self.acc_id}"

    def adapter_cfg(self) -> dict:
        ln = self.lane()
        c = self.bot.accts.adapter_cfg(ln)
        t = f"{self.acc_id}{TAG}"
        return {**c, "nt_file_tag": t + "_", "nt_state_path": os.path.join(os.path.dirname(c["nt_state_path"]), f"ninjatrader_state_{t}.json"),
                "nt_audit_log": os.path.join(os.path.dirname(c["nt_audit_log"]), f"ninjatrader_oif_{t}.log")}

    def kind(self) -> str:
        ln = self.lane()
        return ln.label() if ln is not None else "PAPER"

    # ---- one book (the LIT lane's state = the same balance, floor, room, day $)
    def anchor(self):
        ln = self.lane()
        return ln.anchor() if ln is not None else None

    def _state_raw(self, now=None):
        today = AB.trading_day(now if now is not None else self.clock())
        if self.funded():
            return self._funded_state(today)
        ln = self.lane()
        if ln is None or not self.spec.get("eval_start"):
            return None
        st = ln.state(today, mode="two_week", raw=True)
        return None if st is None else {**st, "n_today": self.entries_today(today)}

    def eval_state(self, now=None):
        today = AB.trading_day(now if now is not None else self.clock())
        if self.funded():
            return self._funded_state(today)
        ln = self.lane()
        if ln is None or not self.spec.get("eval_start"):
            return None
        st = ln.state(today, mode="two_week")          # min(ledger room, the account's real room): the LIT lane's own cap
        return None if st is None else {**st, "n_today": self.entries_today(today)}

    def funded_days(self, today=None) -> dict:
        F = self.spec.get("funded") or {}
        days = {}
        for d, _, p, *_ in self.all_closes():
            if F.get("start") and str(d) >= F["start"] and (today is None or str(d) <= today):
                days[str(d)] = round(days.get(str(d), 0.0) + float(p), 2)
        return days

    def eval_view(self, now=None) -> dict:
        return AB.AccountB.eval_view(self, now)        # a Builder: no best-day / 4-day rule in the eval (not the Rapid's)

    def funded_view(self, now=None) -> dict:
        return AB.AccountB.funded_view(self, now)

    def _lifecycle(self, now):
        return None                                    # the LIT lane / engine/lifecycle speak for the account (one push each)

    def news_at(self, now, pre=None, post=None):
        ln = self.lane()
        try:
            return ln.in_news(int(now)) if ln is not None else None
        except Exception:
            return None

    # ---- size: engine/combo50k.atlas_qty on this plan (x atlas_size_factor), ATLAS's stop lines
    def stage(self) -> str:
        return "funded" if self.funded() else "eval"

    def size(self, trade: dict, state, key=None) -> dict:
        g = self.combo.get("guards") or {}
        stg = self.stage()
        if state is None:
            return {"qty": 0, "reasons": ["account state unknown (eval_start / funded_start missing?): not traded"], "lock": None}
        room = _num(state.get("room"))
        if stg == "eval" and g.get("atlas_in_eval") is False:
            return {"qty": 0, "reasons": ["guard atlas_in_eval false: ATLAS trades this account only once it is funded"], "lock": None}
        line = float(g.get("atlas_min_room_funded", 100.0) if stg == "funded" else g.get("atlas_min_room", 200.0))
        if room is not None and room < line:
            return {"qty": 0, "reasons": [f"room ${room:,.0f} under ATLAS's ${line:,.0f} {stg} stop line"], "lock": None}
        mr = g.get("atlas_eval_min_room_usd")
        if stg == "eval" and mr is not None and room is not None and room < float(mr):
            return {"qty": 0, "reasons": [f"guard atlas_eval_min_room_usd: room ${room:,.0f} < ${float(mr):,.0f}"], "lock": None}
        F = self.spec.get("funded") if stg == "funded" else None
        r = CB.atlas_qty(self.combo, trade, state, self.spec.get("eval_start"), base=None, stage=stg, funded=F, key=key)
        return {"qty": int(r.get("qty") or 0), "reasons": list(r.get("reasons") or []), "lock": r.get("lock")}

    # ---- one position (first_in) on this account, one direction across every account
    def _lit_entering(self):
        """Zlarior's model entry this account's LIT lane will still take (routed later this poll / waiting for a hedge close)."""
        ln = self.lane()
        st = getattr(self.bot, "state", None) or {}
        ent = st.get("enter_now") or st.get("position")
        if ln is None or not ent or ent.get("entry_t") is None:
            return None
        et_ = int(ent["entry_t"])
        start = int(getattr(self.bot, "started_at", 0) or 0)
        try:
            from .live import TF_SECONDS
            secs = int(TF_SECONDS[str((self.bot.cfg or {}).get("tf") or "5m")])
        except Exception:
            secs = 300
        if et_ in ln.blocked or ("exit", et_) in ln.seen or ln.open_t == et_ or et_ < start - secs:
            return None
        if ("entry", et_) in ln.seen:
            return None
        return ent

    def lit_opposite(self, d: int):
        side = lambda x: "LONG" if x == 1 else "SHORT"
        ln = self.lane()
        g = self.combo.get("guards") or {}
        if ln is not None and ln.open_t is not None:
            return f"one position on {ln.name}: Zlarior holds it (first in keeps the account)"
        if ln is not None:
            try:
                lg = _open_leg(getattr(ln, "adapter", None))
            except Exception:
                return "Zlarior's lane: NinjaTrader state unreadable (fails closed)"
            if lg:
                return f"one position on {ln.name}: Zlarior's NinjaTrader bracket is {lg.get('status')} (not confirmed flat)"
        en = self._lit_entering()
        if en is not None:
            return f"one position on {getattr(ln, 'name', '')}: Zlarior is entering {side(int(en.get('dir') or 1))}"
        b = self.bot
        st = getattr(b, "state", None) or {}
        if g.get("atlas_lit_armed_block", False):
            su = st.get("setups") or {}
            opp = "short" if d == 1 else "long"
            if su.get(opp):
                return f"no hedging: Zlarior has a {side(-d)} setup armed"
        ac = getattr(b, "accts", None)
        if ac is not None:
            try:
                h = ac.opposite_open(d, exclude=ln if ln is not None else object())
                if h:
                    return h
            except Exception:
                return "the extra accounts' state is unreadable (fails closed)"
        ab = getattr(b, "acct_b", None)
        try:
            if ab is not None and ab.open_t is not None and int((ab.prov.get(int(ab.open_t)) or {}).get("dir") or 0) == -d:
                return f"no hedging: ATLAS's 25K (account B) holds a {side(-d)} position"
            for _, pv in (ab.closing_open() if ab is not None else []):
                if int(pv.get("dir") or 0) == -d:
                    return f"no hedging: ATLAS's 25K (account B) is closing a {side(-d)} position (not confirmed yet)"
        except Exception:
            return "account B state unreadable (fails closed)"
        lanes = list(getattr(b, "_rapid_atlases", lambda: [])() or [])
        for ar in lanes:
            if ar is self or getattr(ar, "open_t", None) is None:
                continue
            try:
                if int((ar.prov.get(int(ar.open_t)) or {}).get("dir") or 0) == -d:
                    return f"no hedging: {getattr(ar, 'label', 'ATLAS on another account')} holds a {side(-d)} position"
            except Exception:
                return "another ATLAS lane's state is unreadable (fails closed)"
        # red team 2026-11-23 (day-rapidsize): BLITZ (account C) and BLITZ on a Rapid EOD 25K eval (engine/rapid_blitz.py;
        # absent = nothing) holding or still closing the other side is a hedge too
        for attr, who in (("acct_c", "BLITZ (account C)"), ("acct_rb", "BLITZ on the Rapid EOD"),
                          ("acct_rb2", "BLITZ on the Rapid EOD #2")):
            o = getattr(b, attr, None)
            if o is None or o is self:
                continue
            try:
                if o.open_t is not None and int(((o.prov or {}).get(int(o.open_t)) or {}).get("dir") or 0) == -d:
                    return f"no hedging: {who} holds a {side(-d)} position"
                for _, pv in (o.closing_open() or []):
                    if int(pv.get("dir") or 0) == -d:
                        return f"no hedging: {who} is closing a {side(-d)} position (not confirmed yet)"
            except Exception:
                return f"{who}: state unreadable (fails closed)"
        ot = getattr(b, "_open_routed", None)
        if ot is not None and getattr(b, "_open_src", None):
            pv = (getattr(b, "_second_prov", None) or {}).get(int(ot)) or {}
            if int(pv.get("dir") or 0) == -d:
                return f"no hedging: ATLAS on the bot's own account holds a {side(-d)} position"
        fl = getattr(b, "fleet", None)
        if fl is not None:
            try:
                h = fl.opposite_open(d, max_rank=0)
                if h:
                    return h
            except Exception:
                return "fleet state unreadable (fails closed)"
        return None

    def holds_at(self, entry_t: int, sym=None, now=None, d=None):
        """For the LIT lane: why ATLAS holds this account at Zlarior's entry minute entry_t (its trade entered at or before it
        and was not over by then: still open, closing, or its exit after entry_t) so this LIT copy is SKIPPED, else None.
        Zlarior the OTHER way (d) is never skipped here: no hedging across Zlarior's accounts means the 50K's LIT closes this
        ATLAS trade anyway (LIT > ATLAS across accounts), so on this account too ATLAS is closed at market first and LIT routes
        once that close is confirmed (Account._process's shared() yield) = the simulator's close_on_opposite (zprio); the
        same side = first in keeps the account; conflict lit_priority = never skipped (zfull). ATLAS's open trade is first
        brought up to this poll's bars (refresh: its exit bar may just have closed: the simulator frees the account at
        ATLAS's exit minute). Unknown fails closed."""
        try:
            if sym is not None and now is not None:
                self.refresh(sym, now)
            if self.combo.get("conflict") == "lit_priority":
                return None
            et_ = int(entry_t)
            ex = {int(c[3]): int(c[1]) for c in self.closes if len(c) > 3}
            for t, pv in sorted(self.prov.items()):
                if not isinstance(pv, dict) or pv.get("refused") or int(t) > et_:
                    continue
                if pv.get("void") or pv.get("never_placed"):
                    continue
                open_now = self.open_t is not None and int(self.open_t) == int(t)
                cl = pv.get("closing") or {}
                xt = ex.get(int(t))
                if open_now or (cl and not cl.get("done")) or (xt is not None and xt > et_):
                    if d is not None and int(pv.get("dir") or 0) == -int(d):
                        if open_now or (cl and not cl.get("done")):
                            return None                # LIT the other way: ATLAS is closed first (the yield), then LIT
                        continue                       # an ATLAS trade already closed for it (HEDGE / LIT first): the account is free
                    side = "LONG" if int(pv.get("dir") or 1) == 1 else "SHORT"
                    return (f"one position on {getattr(self.lane(), 'name', '')}: {self.label} holds a {side} {pv.get('short') or pv.get('key')} "
                            f"trade from {AB._et(int(t)):%H:%M} ET (conflict rule {self.combo.get('conflict')}: the first bot in keeps the account)")
            return None
        except Exception as e:
            return f"{self.label}'s state unreadable ({e.__class__.__name__}): fails closed"

    def refresh(self, sym, now) -> bool:
        """ATLAS's open trade managed on THIS poll's bars right now (as tick's manage; the same view key). Never raises."""
        fr = getattr(self.bot, "_combo_frames", None)
        if not fr or fr[2] != int(now):
            return False
        with self.mx:
            try:
                from . import second as _second
                live_prov = [p.get("key") for p in self.prov.values() if isinstance(p, dict) and not p.get("final")]
                if not live_prov:
                    return False
                df5, df1 = fr[0], fr[1]
                scfg = _second.load_cfg()
                S = scfg.get("strategies") or {}
                mk = list(dict.fromkeys([k for k in self.spec["keys"] if isinstance(S.get(k), dict)] + [k for k in live_prov if k]))
                last5 = int(df5["time"].max())
                self.settle_closing(sym, now)
                vk = (last5, int(df1["time"].max()) if df1 is not None and len(df1) else 0, tuple(mk))
                if vk != self.view_key or self.view is None:
                    sub_v = {**scfg, "strategies": {k: {**S[k], "route": True} for k in live_prov if k in S}}
                    self.view = _second.run(df5, one_min=df1, now=now, cfg=sub_v, lit=[])
                    self.view_key = vk
                self.manage(self.view, sym, now, last5)
                return True
            except Exception as e:
                self.log("error", f"refresh failed: {e.__class__.__name__}: {e}")
                return False

    def tick(self, df5, df1, sym, now):
        with self.mx:
            return super().tick(df5, df1, sym, now)

    # ---- ATLAS's entry on this account (the raw stream, = engine/combo50k / the simulator)
    def entry(self, df5, df1, sub, keys, sym, now):
        import pandas as pd
        from . import second as _second
        tb = int(df5["time"].max()) + 300
        age = int(now) - tb
        if age < 0 or age > CB.MAX_AGE_S:
            return
        if ("probe", tb) in self.seen or getattr(self.bot, "kill", False):
            return
        self.seen.add(("probe", tb))
        px, est = self.mark(sym, now, bar_t=tb)
        if px is None:
            self._hold(tb, None, "no price for the open")
            return
        cols = ["time", "open", "high", "low", "close", "volume"]
        bar = pd.DataFrame([{"time": tb, "open": px, "high": px, "low": px, "close": px, "volume": 1.0}])
        df5x = pd.concat([df5[cols], bar], ignore_index=True)
        df1x = df1
        if df1 is not None and len(df1) and int(df1["time"].max()) < tb:
            df1x = pd.concat([df1[cols], bar], ignore_index=True)
        pr = _second.run(df5x, one_min=df1x, now=now, cfg=sub, lit=[])
        for k in keys:
            s = (pr.get("strategies") or {}).get(k) or {}
            if s.get("error"):
                self.note(("err", k), "warn", f"{k}: {s['error']} (no entry from it this bar)")
        day = AB.trading_day(tb)
        pick, why_s, sigs = CB.atlas_pick(pr, keys, tb, day)
        if not sigs:
            return
        if pick is None:
            k0, t0 = sigs[0]
            nm0 = (sub["strategies"].get(k0) or {}).get("short") or k0
            self.log("system", f"{nm0} {'LONG' if int(t0['dir']) == 1 else 'SHORT'} at the {AB._et(tb):%H:%M} ET open is not "
                               f"ATLAS's trade: {why_s}")
            self._hold(tb, k0, why_s)
            return
        k, t = pick
        nm = (sub["strategies"].get(k) or {}).get("short") or k
        d = 1 if int(t["dir"]) == 1 else -1
        head = f"{nm} {'LONG' if d == 1 else 'SHORT'} at the {AB._et(tb):%H:%M} ET open"
        ln = self.lane()
        g = self.combo.get("guards") or {}
        why = None
        if self.open_t is not None:
            why = "one position: ATLAS's earlier trade still holds the account"
        if not why:
            try:
                if _open_leg(self.adapter) is not None:
                    why = "one position: an ATLAS order on this account is still working at NinjaTrader"
            except Exception:
                why = "ATLAS's NinjaTrader state unreadable (fails closed)"
        if not why and ln is None:
            why = "the account's LIT lane is not running"
        if not why and getattr(self.bot.accts, "killed", lambda: False)():
            why = "kill switch"
        if not why and ln.disabled_reason():
            why = f"account disabled: {ln.disabled_reason()}"
        mx = int(g.get("atlas_max_per_day", AB.MAX_PER_DAY))
        if not why and self.entries_today(day) >= mx:
            why = f"{self.entries_today(day)} ATLAS entries on this account today already (max {mx} a day)"
        if not why and (self.bot.health or {}).get("entries_blocked"):
            why = "feed stale"
        if not why:
            why = self.startup_block(now)
        if not why and getattr(self.bot, "_no_entries_day", None) == AB.trading_day(now):
            why = "the owner flattened remotely today"
        if not why:
            why = self.life_block(now)
        if not why and self.lock and self.lock.get("day") == day:
            why = f"locked out today: {self.lock['reason']}"
        if not why and ln.lock and ln.lock.get("day") == day:
            why = f"the account is locked out today: {ln.lock['reason']}"
        ds = g.get("eval_day_stop_usd")
        if not why and ds is not None and self.stage() == "eval" and self.day_pnl(day) <= -float(ds):
            why = f"eval day stop: today's closed ${self.day_pnl(day):,.0f} <= -${float(ds):,.0f}"
        ev = self.eval_view(now) if not why else {}
        if not why and ev.get("status") in AB.STOP_STATUSES:
            why = f"{'funded account' if self.funded() else 'eval'} {ev['status']} (room ${(ev.get('room') or 0):,.0f})"
        if not why:
            why = self.lit_opposite(d)
        risk = abs(float(t["entry"]) - float(t["stop"]))
        tgt = abs(float(t["target"]) - float(t["entry"]))
        sz = {"qty": 0, "reasons": []}
        if not why:
            try:
                sz = self.size({"risk_pts": risk, "tgt_pts": tgt, "entry_t": t.get("entry_t")}, self.eval_state(now), k)
            except Exception as e:
                sz = {"qty": 0, "reasons": [f"sizing failed ({e.__class__.__name__}: {e}): not traded"]}
            self.last_size = {"qty": sz["qty"], "key": k, "reasons": [str(x)[:120] for x in sz["reasons"]][-6:], "t": int(now)}
            if sz["qty"] < 1:
                why = "size 0 (" + "; ".join(sz["reasons"][-3:]) + ")"
        act = {"sym": sym, "side": "buy" if d == 1 else "sell", "qty": int(sz["qty"]), "stop": AB._tick(float(t["stop"]), d),
               "target": AB._tick(float(t["target"]), d, target=True), "entry": float(t["entry"]), "entry_t": tb, "src": k,
               "strategy": f"{nm} ({self.label})", "combo": "atlas25", "who": self.label}
        if not why:
            why = self.guard(act, tb, now)
        if not why:
            why_c = self._c_yield(d, tb, sym, now, act.get("entry"))
            if why_c:
                self.seen.discard(("probe", tb))
                self.log("risk", f"{head} NOT routed yet: {why_c} (tried again at the next poll while the open is fresh)")
                return
        if why:
            self.log("risk", f"{head} NOT routed on {getattr(ln, 'name', self.name)}: {why}")
            self._hold(tb, k, why)
            return
        q = int(sz["qty"])
        self.open_t = tb
        self.prov[tb] = {"key": k, "short": nm, "qty": q, "model_qty": int(t.get("qty") or 0), "dir": d, "est": est,
                         "entry": float(t["entry"]), "stop": act["stop"], "target": act["target"], "t": int(self.clock()),
                         "risk_pts": risk, "day": day, "combo": True}
        self.seen.add(("entry", k, tb))
        self.log("system", f"{head}: ROUTED MARKET {q} MNQ on {self.name} ({int(self.clock()) - tb} s after the open), stop "
                           f"{act['stop']:,.2f}, target {act['target']:,.2f}; size {'; '.join(sz['reasons'][-3:])}")
        rr = self.route(act)
        if rr.get("ok") is not False:
            self._push_entry(act, q)
            if self.real_bot():
                CB.board_note(self.label, "LONG" if d == 1 else "SHORT", q, nm)
        elif self.never_placed(tb, rr):
            self._drop_unplaced(tb, rr, now)
        else:
            self._unconfirmed(tb, rr)

    def info(self, now=None) -> dict:
        out = super().info(now)
        return {**out, "combo": {"on": True, "label": self.label, "conflict": self.combo.get("conflict"),
                                 "atlas_size_factor": self.combo.get("atlas_size_factor"), "stage": self.stage()}}

    def _push_text(self, title, body, key):
        return AB.AccountB._push_text(self, title, body, f"combo25:{key}")


def _state_path(bot_state_path: str | None, acc_id: str) -> str:
    p = bot_state_path or os.path.join(AB.ROOT, "data", "live_state.json")
    base, ext = os.path.splitext(p)
    return base + f"_acct{acc_id}{TAG}" + (ext or ".json")
