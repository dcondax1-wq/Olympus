"""Account B (owner 2026-10-22): the second strategies on their OWN prop account, next to LIT's eval. OFF by default.

second_model.json top level "account_b": null (default = off, the bot is exactly today's) or
  {"account": "<NinjaTrader account Name>", "plan": "builder25k" | "builder50k", "eval_start": "yyyy-mm-dd",
   "strategies": ["ema_lon_vix", "macd_sweep", "sr_nyreclaim"], "sizing": "need" | "safe"}
  optional: "prior_pnl" ($ on the account before the bot traded it), "armed": false (a REAL, non-Sim account also needs
  "armed": true, the LIVE phrase typed at the bot's start and NINJATRADER_LIVE=1: engine/ninjatrader._live_gate; the bot
  never sets any of that).
Owner switch: python -m engine.second --account-b "<Name>" --plan builder25k --start <day>  |  --account-b off
(refused when engine.ninjatrader --selftest fails; research/writeups/second-account-b.md, docs/DAILY_CHECKLIST.md).

What it does (engine/live.py calls it after LIT's routing and state save; any exception is logged and never touches LIT):
  * its own adapter (NinjaTrader OIF route to that account, own order-file tag "acctb_", own NinjaTrader state file; paper
    when the bot is on paper), own ledger, own state file (live_state_acctb.json next to the bot's), own guards;
  * its own eval: balance, EOD trailing floor (the plan's max loss, locked at start + $100), room, session count from
    eval_start, pass ($1,500 / $3,000 target reached: no new trade, push "Account B EVAL PASSED"), fail (room <= 0: no
    trade, push), stuck (room under $100: 1 micro no longer fits a stop, push "buy a new one"), the plan's soft daily loss
    ($600 / $1,000: no new entry for the rest of the day);
  * its own size per the plan (engine/sizing.py):
      need  LIT's two_week "one winner passes" on the plan (micros so the trade's target covers what is left to the target,
            capped at 60% (50K) / 50% (25K) of the room and the soft daily loss, max 40 / 20 micros, for 10 sessions; then
            safe_eval 60% / 30%) = engine/multi_account.sizing_cfg of the plan's preset + sizing.lit_qty, exactly what
            tools/second_account_b.py scores;
      safe  $300 (50K) / $150 (25K) risk, capped at 60% of the room and the soft daily loss (sizing.second_qty);
  * the strategies' own trades (engine/second.run: the research code on closed bars), entered at market at the 5m open
    after the signal close (probe with the bar's real open, as LiveBot._second_entry), checked once the fill bar closed,
    breakeven moves / 15-minute cuts / 15:55 flat / model exits routed; one position at a time on B, max 2 entries a day;
  * NEVER opposite to LIT (MFFU bans long + short on one underlying, also across your own accounts,
    research/lit/mffu_rules.json "hedging"): a B entry is blocked while LIT's account holds, enters or has an armed setup
    (limit / waiting for its 1m CISD) in the other direction, or an extra account (engine/multi_account.py) holds the other
    side; when LIT enters opposite while B is open, B is closed at market FIRST (reason HEDGE), then LIT's order goes out
    (second-mix.md no_hedge rule: skip / close at LIT's opposite entry; the armed-setup block is stricter than the research).
    Same direction as LIT is allowed (two accounts, two positions).
  * strategies on account B are never also routed on LIT's account (LiveBot._second_cfg drops them there).
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLANS = {
    "builder50k": {"preset": "mffu_builder_50k", "label": "MFFU Builder 50K", "safe_usd": 300.0, "price": 91.80},
    "builder25k": {"preset": "mffu_builder_25k", "label": "MFFU Builder 25K", "safe_usd": 150.0, "price": 63.00},
}
SIZINGS = ("need", "safe")
MAX_PER_DAY = 2
MAX_AGE_S = 45                  # a 5m open seen later than this is not probed (the research fills at the open)
MIN_ROOM = 100.0
TICK, PV, COMM = 0.25, 2.0, 1.90
ADAPTER_FACTORY = None          # tests: (spec, adapter cfg) -> adapter; None = engine/live.ADAPTERS
VERSION = 1


def _et(ts):
    from zoneinfo import ZoneInfo
    return _dt.datetime.fromtimestamp(int(ts), ZoneInfo("America/New_York"))


def trading_day(ts) -> str:
    return (_et(ts) + _dt.timedelta(hours=6)).strftime("%Y-%m-%d")


def _num(x, d=None):
    try:
        v = float(x)
        return d if v != v else v
    except (TypeError, ValueError):
        return d


def _tick(px, d=1, target=False):
    from .live import tick_px
    return tick_px(px, d, target=target)


# ---------------------------------------------------------------------------------------------------------------- config
def raw_cfg(path: str | None = None):
    """second_model.json "account_b" (None = off). Never raises."""
    from . import second
    try:
        with open(path or second.CFG_PATH, encoding="utf-8") as fh:
            c = json.load(fh)
        ab = c.get("account_b") if isinstance(c, dict) else None
        return ab if isinstance(ab, dict) else None
    except Exception:
        return None


def normalize(ab: dict | None, scfg: dict | None = None, lit_account: str | None = None) -> dict | None:
    """The account_b block -> a spec {"account", "plan", "preset", "rules", "eval_start", "strategies", "sizing", "label",
    "problem": why it cannot trade or None}; None when off."""
    if not isinstance(ab, dict) or not ab:
        return None
    from . import multi_account as MA
    from . import second
    scfg = scfg or second.load_cfg()
    plan = str(ab.get("plan") or "builder50k").lower().replace(" ", "").replace("_", "")
    P = PLANS.get(plan)
    keys = ab.get("strategies")
    keys = [str(k) for k in keys] if isinstance(keys, (list, tuple)) else ["ema_lon_vix", "macd_sweep", "sr_nyreclaim"]
    out = {"account": str(ab.get("account") or "").strip(), "plan": plan, "eval_start": str(ab.get("eval_start") or ""),
           "strategies": keys, "sizing": str(ab.get("sizing") or "need"), "prior_pnl": float(_num(ab.get("prior_pnl"), 0.0)),
           "eval_anchor": ab.get("eval_anchor"),
           "armed": ab.get("armed") is True, "problem": None}
    out["preset"] = (P or {}).get("preset") or "mffu_builder_50k"
    out["plan_label"] = (P or {}).get("label") or plan
    out["rules"] = MA.rules_of({"preset": out["preset"]})
    out["label"] = f"ATLAS {out['account'] or '?'}"      # ATLAS = the second strategy's account (was "Account B")
    S = scfg.get("strategies") or {}
    bad = [k for k in keys if not isinstance(S.get(k), dict)]
    co = [k for k in keys if isinstance(S.get(k), dict) and S[k].get("cloud_only")]
    nm = out["account"]
    if P is None:
        out["problem"] = f"unknown plan {plan!r} (builder25k or builder50k)"
    elif not nm or any(c in nm for c in ";\r\n|"):
        out["problem"] = "account name missing or invalid"
    elif lit_account and nm == str(lit_account).strip():
        out["problem"] = f"{nm} is LIT's own account: account B must be a different account"
    elif out["sizing"] not in SIZINGS:
        out["problem"] = f"unknown sizing {out['sizing']!r} (need or safe)"
    elif not keys:
        out["problem"] = "no strategies listed"
    elif bad:
        out["problem"] = f"unknown strategies {', '.join(bad)}"
    elif co:
        out["problem"] = f"{', '.join(co)} is cloud only (a paper shadow): never routed"
    elif out["eval_start"]:
        try:
            _dt.date.fromisoformat(out["eval_start"])
        except ValueError:
            out["problem"] = f"eval_start {out['eval_start']!r} is not yyyy-mm-dd"
    out["keys"] = [k for k in keys if isinstance(S.get(k), dict) and S[k].get("on", True) and not S[k].get("cloud_only")]
    return out


def keys_on_b(ab: dict | None = None) -> list:
    """The strategies account B trades (never also routed on LIT's account)."""
    ab = raw_cfg() if ab is None else ab
    if not isinstance(ab, dict) or not ab:
        return []
    k = ab.get("strategies")
    return [str(x) for x in k] if isinstance(k, (list, tuple)) else ["ema_lon_vix", "macd_sweep", "sr_nyreclaim"]


def sizing_cfg(spec: dict, base: dict | None = None) -> dict:
    """live_model.json lit_sizing + the plan preset's sizing in two_week mode (engine/multi_account.sizing_cfg): the
    sizer config of a "need" trade on account B (tools/second_account_b.sizing_cfg). The day guard of the 25K preset
    allows 2 entries a day (account B's own limit)."""
    from . import multi_account as MA
    if base is None:
        try:
            base = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8")).get("lit_sizing") or {}
        except Exception:
            base = {}
    s = MA.normalize({"id": "acctb", "preset": spec["preset"], "mode": "two_week", "adapter": "paper", "eval_start": spec.get("eval_start")})
    c = MA.sizing_cfg(base, s)
    c["mode"] = "two_week"
    c["eval_start"] = spec.get("eval_start") or ""
    if c.get("guard") is not None:
        c["guard"] = {**c["guard"], "max_per_day": MAX_PER_DAY}
    c.setdefault("two_week", {})["dll"] = float(spec["rules"]["dll"])
    c.pop("wk_loss_usd", None)
    return c


def qty(spec: dict, trade: dict, state: dict | None, base: dict | None = None) -> dict:
    """Micros for one account B entry: {"qty", "reasons", "lock"}. trade = {"risk_pts", "tgt_pts", ...}; state =
    the account's eval state (multi_account.sizing_state). Fails closed (0) on any error / unknown state."""
    from . import lit as _lit
    from . import sizing as SZ
    R = spec["rules"]
    maxq = int(R["max_micros"])
    if state is None:
        return {"qty": 0, "reasons": ["eval state unknown (eval_start missing?): not traded"], "lock": None}
    risk = _num(trade.get("risk_pts"))
    if not risk or risk <= 0:
        return {"qty": 0, "reasons": ["no stop distance"], "lock": None}
    c = sizing_cfg(spec, base)
    if spec.get("sizing") == "safe":
        r = SZ.second_qty(float(risk), PLANS[spec["plan"]]["safe_usd"], c, state=dict(state), max_micros=maxq)
        return dll_guard({"qty": min(maxq, int(r["qty"])), "reasons": list(r["reasons"]), "lock": r.get("lock")}, float(risk), R, state)
    m0 = _lit.qty_for(float(risk))
    if not m0:
        return {"qty": 0, "reasons": ["no size"], "lock": None}
    r = SZ.lit_qty(m0, {"risk_pts": float(risk), "tgt_pts": _num(trade.get("tgt_pts")), "size_mult": 1.0}, c, room=state.get("room"),
                   state=dict(state), max_micros=maxq, learning=None)
    return dll_guard({"qty": min(maxq, int(r.get("qty") or 0)), "reasons": list(r.get("reasons") or []), "lock": r.get("lock")},
                     float(risk), R, state)


def dll_guard(r: dict, risk: float, rules: dict, state: dict) -> dict:
    """The plan's soft daily loss, on EVERY account B trade (2026-10-22 fix: after session 10 safe_eval had no daily check,
    and the 50K preset had no day guard at all: one stop-out could cost $628 on the 25K / $1,255 on the 50K against a
    $600 / $1,000 limit). One trade's full stop-out, as the research models it (stop + 2 ticks of slippage, $1.90 a micro
    round trip = engine/sizing.TW_DLL_SLIP / TW_COMM), never exceeds what is left of today's soft daily loss
    (dll + today's closed P&L state["cum"]); when not even 1 micro fits: no trade."""
    from . import sizing as SZ
    q = int(r.get("qty") or 0)
    if q <= 0:
        return r
    dll = _num(rules.get("dll"))
    if not dll:
        return r
    left = float(dll) + float(_num(state.get("cum"), 0.0))
    loss1 = (float(risk) + SZ.TW_DLL_SLIP) * SZ.TW_PV + SZ.TW_COMM
    cap = int(max(0.0, left) / loss1 + 1e-9)
    if cap >= q:
        return r
    out = {**r, "reasons": list(r.get("reasons") or [])}
    if cap < 1:
        out["qty"] = 0
        out["reasons"].append(f"soft daily loss: 1 micro's full stop-out ${loss1:,.0f} > ${left:,.0f} left of today's ${float(dll):,.0f}: no trade")
    else:
        out["qty"] = cap
        out["reasons"].append(f"soft daily loss: {cap} x ${loss1:,.0f} full stop-out fits the ${left:,.0f} left of today's ${float(dll):,.0f} -> {cap}")
    return out


# ---------------------------------------------------------------------------------------------------------------- account
class AccountB:
    """Account B on one PC bot (engine/live.py LiveBot.acct_b)."""

    def __init__(self, bot, spec: dict, state_path: str | None = None, adapter_factory=None):
        self.bot = bot
        self.spec = spec
        self.rules = spec["rules"]
        self.name = spec["account"]
        self.label = spec["label"]
        self.problem = spec.get("problem")
        self.state_path = state_path or _state_path_for(getattr(bot, "state_path", None))
        self.adapter_factory = adapter_factory if adapter_factory is not None else ADAPTER_FACTORY
        self.adapter = None
        self.ledger: list = []
        self.closes: list = []            # [day, exit_t, pnl, entry_t]
        self.prov: dict = {}              # entry_t -> what was routed (key, dir, qty, entry, stop, target, ...)
        self.open_t = None                # entry_t of the open position on B
        self.seen: set = set()
        self.lock = None                  # {"day", "reason"}: no new entry today
        self.notified: list = []          # push keys already sent (pass / fail / stuck)
        self.notes: dict = {}
        self.view = None
        self.view_key = None
        self.last_size = None
        self.mx = threading.RLock()

    # ---- plumbing
    def clock(self):
        return self.bot.clock()

    def log(self, kind, text):
        try:
            self.bot._log(kind, f"[{self.label}] {text}")
        except Exception:
            print(f"[{self.label}] {kind}: {text}")

    def note(self, key, kind, text):
        if self.notes.get(key) == text:
            return
        self.notes[key] = text
        self.log(kind, text)

    def kind(self) -> str:
        ad = (self.bot.cfg or {}).get("adapter") or "paper"
        if ad != "ninjatrader":
            return "PAPER"
        from .ninjatrader import is_sim
        return "SIM" if is_sim(self.name) else "LIVE"

    def adapter_cfg(self) -> dict:
        """The bot's cfg (instrument, folder, params) WITHOUT LIT's account and arming, then account B's own name, arming,
        order-file tag and state files. A real account needs "armed": true in account_b AND the phrase typed at start AND
        NINJATRADER_LIVE=1 (the adapter's _live_gate); the bot's own arming is never inherited."""
        b = self.bot.cfg or {}
        base = {k: v for k, v in b.items() if k not in ("accounts", "armed", "confirm", "nt_account", "nt_state_path", "nt_audit_log",
                                                       "eval_start", "eval_prior_pnl", "eval_anchor", "lit_sizing", "funded",
                                                       "webhook_url", "account_b")}
        p = dict(base.get("params") or {})
        p["max_micros"] = min(int(p.get("max_micros", 40) or 40), int(self.rules["max_micros"]))
        d = os.path.dirname(self.state_path)
        real = self.real_bot()
        return {**base, "adapter": "ninjatrader" if b.get("adapter") == "ninjatrader" else "paper", "nt_account": self.name,
                "armed": bool(self.spec.get("armed")), "confirm": (b.get("confirm") or "") if self.spec.get("armed") else "",
                "params": p, "nt_file_tag": "acctb_", "nt_state_path": os.path.join(d, "ninjatrader_state_acctb.json"),
                "nt_audit_log": os.path.join(os.path.join(ROOT, "logs") if real else d, "ninjatrader_oif_acctb.log")}

    def real_bot(self) -> bool:
        try:
            from .live import STATE_PATH
            return getattr(self.bot, "state_path", None) == STATE_PATH
        except Exception:
            return False

    def start(self):
        self._load()
        if self.problem:
            self.log("risk", f"NOT trading: {self.problem}")
            return self
        try:
            cfg = self.adapter_cfg()
            if self.adapter_factory is not None:
                self.adapter = self.adapter_factory(self.spec, cfg)
            else:
                from .live import ADAPTERS
                self.adapter = ADAPTERS[cfg["adapter"]](cfg)
        except Exception as e:
            self.problem = f"adapter failed: {e.__class__.__name__}: {e}"
        dis = self.disabled_reason()
        ev = self.eval_view()
        self.log("system" if not dis else "risk",
                 f"{self.kind()} {self.name} {self.spec['plan_label']}, strategies {', '.join(self.spec['keys'])}, size {self.spec['sizing']}, "
                 f"eval from {self.spec['eval_start'] or '?'} (balance ${ev.get('balance', 0):,.0f}, room ${ev.get('room', 0):,.0f}): "
                 + (f"DISABLED ({dis})" if dis else "ready"))
        self.save()
        return self

    def disabled_reason(self):
        if self.problem:
            return self.problem
        if self.adapter is None:
            return "adapter not created"
        return getattr(self.adapter, "disabled", None)

    def route(self, action: dict) -> dict:
        try:
            res = self.adapter.send(action) if self.adapter is not None else {"ok": False, "error": "no adapter"}
        except Exception as e:
            res = {"ok": False, "error": f"{e.__class__.__name__}: {e}"}
        with self.mx:
            self.ledger.append({"t": int(self.clock()), **action, "result": res})
            self.ledger = self.ledger[-400:]
        self.log("order", f"{action['side'].upper()} {action.get('qty', '')} {action['sym']} -> {res.get('ok')}"
                 + (f" ({res.get('error')})" if res.get("ok") is False and res.get("error") else ""))
        self.save()
        return res

    def adapter_tick(self):
        ad = self.adapter
        if ad is None or self.problem or not getattr(ad, "loop_tick", False) or not callable(getattr(ad, "tick", None)):
            return
        try:
            ad.tick()
        except Exception as e:
            self.log("error", f"adapter tick failed: {e.__class__.__name__}: {e}")

    # ---- eval
    def day_pnl(self, day) -> float:
        return round(sum(float(p) for d, _, p, *_ in self.closes if d == day), 2)

    def entries_today(self, day) -> int:
        void = {int(r["entry_t"]) for r in self.ledger if r.get("side") == "exit" and r.get("reason") == "NO TRADE" and r.get("entry_t")}
        return len({int(r["entry_t"]) for r in self.ledger if r.get("side") in ("buy", "sell") and r.get("entry_t")
                    and trading_day(int(r["entry_t"])) == day and int(r["entry_t"]) not in void
                    and (r.get("result") or {}).get("ok") is not False})

    def anchor(self):
        """Account B's eval anchor (engine/sizing.eval_anchor): data/eval_anchor.json "accounts" by its NinjaTrader Name
        next to the bot's state file (`python -m engine.eval_life --anchor --account "<Name>"`), or account_b "eval_anchor";
        the newest as_of wins. None = no anchor (as before)."""
        from . import eval_life as EL
        from . import sizing as SZ
        try:
            f = EL.load_anchor(self.name, state_path=getattr(self.bot, "state_path", None), main=False) if self.name else None
        except Exception:
            f = None
        return SZ.newest_anchor(f, self.spec.get("eval_anchor"))

    def eval_state(self, now=None):
        from . import multi_account as MA
        today = trading_day(now if now is not None else self.clock())
        if not self.spec.get("eval_start"):
            return None
        return MA.sizing_state("two_week", [(d, t, p) for d, t, p, *_ in self.closes], today, self.spec["eval_start"], self.rules,
                               prior=float(self.spec.get("prior_pnl") or 0.0), n_today=self.entries_today(today),
                               anchor=self.anchor())

    def eval_view(self, now=None) -> dict:
        """Balance, trailing floor, room, pass target, session, status (open / passed / failed / stuck)."""
        R = self.rules
        try:
            st = self.eval_state(now)
        except Exception as e:
            return {"error": f"{e.__class__.__name__}: {e}"}
        start = float(R["start"])
        if st is None:
            return {"start_balance": start, "balance": start, "target": start + float(R["target"]), "status": "no eval_start",
                    "session": None, "room": None}
        prof = float(st["profit"]) + float(st["cum"])
        bal = start + prof
        floor = bal - float(st["room"])
        status = "passed" if prof >= float(R["target"]) else "failed" if st["room"] <= 0 else "stuck" if st["room"] < MIN_ROOM else "open"
        return {**({"anchor": st["anchor"]} if st.get("anchor") else {}), "start_balance": start, "balance": round(bal, 2), "profit": round(prof, 2), "today": round(float(st["cum"]), 2),
                "floor": round(floor, 2), "room": round(float(st["room"]), 2), "target": start + float(R["target"]),
                "to_target": round(max(0.0, float(R["target"]) - prof), 2), "session": st.get("session"), "status": status,
                "start": self.spec.get("eval_start"), "days_traded": st.get("days_traded"), "dll": float(R["dll"]),
                "max_micros": int(R["max_micros"]), "plan": self.spec["plan_label"], "price": PLANS[self.spec["plan"]]["price"]}

    def _lifecycle(self, now):
        """Pass / fail / stuck: one push each (key per eval start)."""
        ev = self.eval_view(now)
        stt = ev.get("status")
        if stt not in ("passed", "failed", "stuck"):
            return
        key = f"acctb:{stt}:{self.spec.get('eval_start') or '?'}:{self.name}"
        if key in self.notified:
            return
        self.notified.append(key)
        txt = {"passed": (f"{self.label} EVAL PASSED \U0001F389", f"balance ${ev['balance']:,.0f} (target ${ev['target']:,.0f}): no new "
                                                                   "trade on this eval; request the funded account in the MFFU dashboard"),
               "failed": (f"{self.label} EVAL FAILED", f"balance ${ev['balance']:,.0f} reached the max-loss floor ${ev['floor']:,.0f}: no "
                                                      "new trade on this account"),
               "stuck": (f"{self.label} stuck: room ${ev['room']:,.0f}", f"the room to the max-loss floor is under ${MIN_ROOM:,.0f}: 1 micro "
                                                                       "no longer fits a stop, the bot stops trading this account; buy a new one")}[stt]
        self.log("risk", f"{txt[0]}: {txt[1]}")
        self._push_text(txt[0], txt[1], key)

    def check_lock(self, now):
        today = trading_day(now)
        pnl = self.day_pnl(today)
        lim = float(self.rules["dll"])
        if pnl <= -lim and not (self.lock and self.lock.get("day") == today):
            self.lock = {"day": today, "reason": f"soft daily loss: today ${pnl:,.0f} (limit ${lim:,.0f})"}
            self.log("risk", f"DAILY LOSS LOCK-OUT: {self.lock['reason']}: no new entry on account B today (LIT is not affected)")
            self._push_text(f"{self.label}: locked out today", self.lock["reason"], f"acctb:lock:{today}")

    # ---- LIT's side (the no-opposite rule)
    def lit_opposite(self, d: int):
        """Why a B entry in direction d would be opposite to LIT (None = not): LIT's open position, entry in progress, armed
        setup (limit / waiting for its 1m CISD), its routed position, an extra account's position."""
        b = self.bot
        st = getattr(b, "state", None) or {}
        side = lambda x: "LONG" if x == 1 else "SHORT"
        pos = st.get("position")
        if pos and int(pos.get("dir") or 0) == -d:
            return f"LIT is in a {side(-d)} trade"
        en = st.get("enter_now")
        if en and int(en.get("dir") or 0) == -d:
            return f"LIT is entering {side(-d)}"
        su = st.get("setups") or {}
        opp = "short" if d == 1 else "long"
        if su.get(opp):
            return f"LIT has a {side(-d)} setup armed" + (" (waiting for its 1m CISD)" if su[opp].get("tapped_t") else " (limit working)")
        ot = getattr(b, "_open_routed", None)
        if ot is not None:
            e = next((r for r in reversed(getattr(b, "ledger", None) or []) if r.get("side") in ("buy", "sell") and r.get("entry_t") == ot), None)
            if e and (1 if e["side"] == "buy" else -1) == -d:
                return f"LIT's account holds a {side(-d)} position"
        ac = getattr(b, "accts", None)
        if ac is not None:
            try:
                h = ac.opposite_open(d, exclude=object())
                if h:
                    return h
            except Exception:
                pass
        return None

    def lit_entering(self, ent: dict, sym: str, now: int):
        """engine/live.py, right before LIT's entry order: B open in the OTHER direction -> closed at market first (HEDGE)."""
        if self.open_t is None:
            return
        pv = self.prov.get(int(self.open_t)) or {}
        d = 1 if int(ent.get("dir") or 1) == 1 else -1
        if int(pv.get("dir") or 0) != -d:
            return
        self.log("risk", f"no hedging: LIT enters {'LONG' if d == 1 else 'SHORT'} at {_et(ent['entry_t']):%H:%M} ET while account B "
                         f"holds the {pv.get('short') or pv.get('key')} {'SHORT' if d == 1 else 'LONG'}: B is closed at market before LIT's order")
        self.flatten(int(self.open_t), "HEDGE", sym, now, px=_num(ent.get("entry")))
        pv["final"] = True

    # ---- one poll
    def tick(self, df5, df1, sym, now):
        """After LIT's routing and state save: manage B's open position, then maybe a new entry. Never raises."""
        if self.problem or self.adapter is None:
            return
        try:
            from . import second as _second
            scfg = _second.load_cfg()
            keys = [k for k in self.spec["keys"] if isinstance((scfg.get("strategies") or {}).get(k), dict)]
            live_prov = [p.get("key") for p in self.prov.values() if not p.get("final")]
            mk = list(dict.fromkeys(keys + [k for k in live_prov if k]))
            sub = {**scfg, "strategies": {k: {**scfg["strategies"][k], "route": True} for k in mk if k in (scfg.get("strategies") or {})}}
            last5 = int(df5["time"].max())
            # the strategies' view is only needed while a B trade is live (fill check, stop moves, cuts, exits); a flat
            # account B only probes at each 5m open (entry below)
            if live_prov:
                vk = (last5, int(df1["time"].max()) if df1 is not None and len(df1) else 0, tuple(mk))
                if vk != self.view_key or self.view is None:
                    sub_v = {**sub, "strategies": {k: v for k, v in sub["strategies"].items() if k in live_prov}}
                    self.view = _second.run(df5, one_min=df1, now=now, cfg=sub_v, lit=[])
                    self.view_key = vk
                self.manage(self.view, sym, now, last5)
            self._lifecycle(now)
            if keys:
                self.entry(df5, df1, {**sub, "strategies": {k: sub["strategies"][k] for k in keys}}, keys, sym, now)
        except Exception as e:
            self.log("error", f"account B failed this poll: {e.__class__.__name__}: {e} (LIT is not affected)")
            try:
                self.bot._note_error(f"account B failed: {e.__class__.__name__}: {e}")
            except Exception:
                pass
        finally:
            self.save()

    def mark(self, sym, now, bar_t=None):
        t = int(bar_t if bar_t is not None else now - now % 60)
        fo = (getattr(self.bot, "_forming", None) or {}).get((sym, 60))
        if fo and int(fo[0]) == t and fo[1]:
            return float(fo[1]), False
        px = (getattr(self.bot, "state", None) or {}).get("price")
        return (float(px) if px else None), True

    def entry(self, df5, df1, sub, keys, sym, now):
        import pandas as pd
        from . import second as _second
        tb = int(df5["time"].max()) + 300
        age = int(now) - tb
        if age < 0 or age > MAX_AGE_S:
            return
        if self.open_t is not None or ("probe", tb) in self.seen or getattr(self.bot, "kill", False):
            return
        self.seen.add(("probe", tb))
        px, est = self.mark(sym, now, bar_t=tb)
        if px is None:
            return
        cols = ["time", "open", "high", "low", "close", "volume"]
        bar = pd.DataFrame([{"time": tb, "open": px, "high": px, "low": px, "close": px, "volume": 1.0}])
        df5x = pd.concat([df5[cols], bar], ignore_index=True)
        df1x = df1
        if df1 is not None and len(df1) and int(df1["time"].max()) < tb:
            df1x = pd.concat([df1[cols], bar], ignore_index=True)
        pr = _second.run(df5x, one_min=df1x, now=now, cfg=sub, lit=[])
        sig = None
        for k in keys:
            s = (pr.get("strategies") or {}).get(k) or {}
            if s.get("error"):
                self.note(("err", k), "warn", f"{k}: {s['error']} (no entry from it this bar)")
                continue
            t = next((t for t in s.get("trades") or [] if int(t["entry_t"]) == tb and t.get("exit_kind") == "OPEN"
                      and t.get("target") is not None), None)
            if t:
                sig = (k, t)
                break
        if not sig:
            return
        k, t = sig
        sc = sub["strategies"][k]
        nm = sc.get("short") or k
        d = 1 if int(t["dir"]) == 1 else -1
        head = f"{nm} {'LONG' if d == 1 else 'SHORT'} at the {_et(tb):%H:%M} ET open"
        day = trading_day(tb)
        why = None
        if self.entries_today(day) >= MAX_PER_DAY:
            why = f"{MAX_PER_DAY} entries on account B today already (max {MAX_PER_DAY} a day)"
        if not why and (self.bot.health or {}).get("entries_blocked"):
            why = "feed stale"
        if not why and getattr(self.bot, "_no_entries_day", None) == trading_day(now):
            why = "the owner flattened remotely today"
        if not why and self.lock and self.lock.get("day") == day:
            why = f"locked out today: {self.lock['reason']}"
        if not why:
            why = self.lit_opposite(d)
            if why:
                why = f"no hedging: {why}"
        ev = self.eval_view(now)
        if not why and ev.get("status") in ("passed", "failed", "stuck"):
            why = f"eval {ev['status']} (balance ${ev.get('balance', 0):,.0f}, room ${(ev.get('room') or 0):,.0f})"
        risk = abs(float(t["entry"]) - float(t["stop"]))
        tgt = abs(float(t["target"]) - float(t["entry"]))
        sz = {"qty": 0, "reasons": []}
        if not why:
            try:
                sz = qty(self.spec, {"risk_pts": risk, "tgt_pts": tgt}, self.eval_state(now), base=getattr(self.bot, "_lit_sizing", None))
            except Exception as e:
                sz = {"qty": 0, "reasons": [f"sizing failed ({e.__class__.__name__}: {e}): not traded"]}
            self.last_size = {"qty": sz["qty"], "key": k, "reasons": [str(x)[:120] for x in sz["reasons"]][-6:], "t": int(now)}
            if sz["qty"] < 1:
                why = "size 0 (" + "; ".join(sz["reasons"][-3:]) + ")"
        act = {"sym": sym, "side": "buy" if d == 1 else "sell", "qty": int(sz["qty"]), "stop": _tick(float(t["stop"]), d),
               "target": _tick(float(t["target"]), d, target=True), "entry": float(t["entry"]), "entry_t": tb, "src": k, "strategy": nm}
        if not why:
            why = self.guard(act, tb, now)
        if why:
            self.log("risk", f"{head} NOT routed on account B: {why}")
            return
        q = int(sz["qty"])
        self.open_t = tb
        self.prov[tb] = {"key": k, "short": nm, "qty": q, "model_qty": int(t.get("qty") or 0), "dir": d, "est": est,
                         "entry": float(t["entry"]), "stop": act["stop"], "target": act["target"], "t": int(self.clock()),
                         "risk_pts": risk, "day": day}
        self.seen.add(("entry", k, tb))
        self.log("system", f"{head}: ROUTED MARKET {q} MNQ on {self.name} ({int(self.clock()) - tb} s after the open), stop {act['stop']:,.2f}, "
                           f"target {act['target']:,.2f}; size {'; '.join(sz['reasons'][-3:])}")
        rr = self.route(act)
        if rr.get("ok") is not False:
            self._push_entry(act, q)

    def guard(self, act, entry_t, now):
        """Account B's own guards: CME calendar / session, order sanity (the plan's max micros), the bot's clock check,
        Tier-1 news (when on), the owner's pause. None = route."""
        try:
            from . import guards as G
            c = G.config(self.bot)
            out = []
            if c.get("calendar"):
                out += G.calendar(int(entry_t), int(now), session_from=120, flat_mod=955)
            if c.get("order_sanity"):
                out += G.sanity(act, act["qty"], int(self.rules["max_micros"]), c)
            p = G.clock_problem(self.bot, c)
            if p:
                out.append(p)
            if c.get("news"):
                h = G.news_hit(int(now), int(c.get("news_min") or 2))
                if h:
                    out.append(f"Tier-1 news within {int(c.get('news_min') or 2)} min: {h}")
            out += G._owner_blocks(self.bot, c, int(now))
            return "GUARD " + "; ".join(out) if out else None
        except Exception as e:
            self.log("error", f"guards failed ({e.__class__.__name__}: {e}): entry NOT routed (account B fails closed)")
            return "guards failed"

    def manage(self, view, sym, now, last5):
        for et_, pv in sorted(self.prov.items()):
            if pv.get("final"):
                continue
            k = pv.get("key")
            is_open = self.open_t is not None and int(self.open_t) == int(et_)
            if is_open and self._past_flat(pv, now):
                self.flatten(et_, "TIME", sym, now)
                continue
            s = ((view or {}).get("strategies") or {}).get(k)
            if s is None or s.get("error"):
                if is_open:
                    self.note(("err", k), "warn", f"{k}: {(s or {}).get('error') or 'not computed'} - the open position keeps its "
                                                  "broker stop / target (15:55 flat still routed)")
                continue
            tr = next((t for t in s.get("trades") or [] if int(t["entry_t"]) == int(et_)), None)
            if tr is None:
                if is_open and int(last5) >= int(et_):
                    self.log("risk", f"{pv.get('short')} entry {_et(et_):%H:%M} ET is not the strategy's trade once its fill bar closed: "
                                     "flattening account B")
                    self.flatten(et_, "NO TRADE", sym, now)
                    pv["final"] = True
                elif not is_open and trading_day(now) != pv.get("day"):
                    pv["final"] = True
                continue
            if not pv.get("checked"):
                pv["checked"] = True
                pv["fill"] = float(tr["entry"])
            if tr["exit_kind"] == "OPEN":
                if is_open:
                    pv["stop_now"] = tr.get("stop_now")
                    if tr.get("cut_now"):
                        self.flatten(et_, str(tr["cut_now"]), sym, now)
                    elif getattr(self.adapter, "route_stop_moves", False) and tr.get("stop_now") is not None:
                        self._stop_move(int(et_), pv, float(tr["stop_now"]), sym)
                continue
            kind = str(tr["exit_kind"]).upper()
            reason = "TIME" if kind in ("FLAT", "EOD") else kind
            qm = int(tr.get("qty") or 0)
            if is_open:
                q = int(pv.get("qty") or 0)
                pnl = round(float(tr.get("usd") or 0) * q / qm, 2) if qm else 0.0
                self.seen.add(("exit", k, int(et_)))
                if (self.bot.cfg or {}).get("adapter") == "paper" or reason == "TIME" or getattr(self.adapter, "route_all_exits", False):
                    self.route({"sym": sym, "side": "exit", "qty": q, "reason": reason, "pnl": pnl, "entry_t": int(et_),
                                "exit_t": tr.get("exit_t"), "src": k, "strategy": pv.get("short")})
                self.open_t = None
                self._close(int(et_), int(tr.get("exit_t") or now), pnl, now)
                self._push_outcome(pv, reason, pnl, tr.get("exit_t"), q, int(et_))
            else:
                fl = pv.get("flat") or {}
                same = (fl.get("reason") in ("CUT", "T15") and kind in ("CUT", "T15")) or (fl.get("reason") == "TIME" and reason == "TIME")
                if same and qm:
                    pnl = round(float(tr.get("usd") or 0) * int(pv.get("qty") or 0) / qm, 2)
                    for r in reversed(self.ledger):
                        if r.get("side") == "exit" and r.get("entry_t") == int(et_) and r.get("pnl_est"):
                            r["pnl"], r["pnl_est"], r["pnl_model"] = pnl, False, True
                            break
                    for c in self.closes:
                        if len(c) > 3 and int(c[3]) == int(et_):
                            c[2] = pnl
            pv["final"] = True

    def _past_flat(self, pv, now):
        try:
            from zoneinfo import ZoneInfo
            flat = int(_dt.datetime.combine(_dt.date.fromisoformat(pv["day"]), _dt.time(15, 55), ZoneInfo("America/New_York")).timestamp())
            return int(now) >= flat
        except Exception:
            return False

    def broker_stop(self, entry_t):
        stop = None
        for r in self.ledger:
            if r.get("entry_t") != entry_t:
                continue
            if r.get("side") in ("buy", "sell"):
                stop = r.get("stop")
            elif r.get("side") == "modify" and (r.get("result") or {}).get("ok"):
                stop = r.get("stop")
        return stop

    def _stop_move(self, et_, pv, stop_now, sym):
        d = int(pv.get("dir") or 1)
        new, last = _tick(stop_now, d), self.broker_stop(et_)
        if new is None or last is None or abs(float(new) - float(last)) < 1e-9 or (float(new) - float(last)) * d < 0:
            return
        if ("gaveup", et_, new) in self.seen:
            return
        ready = getattr(self.adapter, "has_open_bracket", None)
        if callable(ready) and not ready(et_):
            return
        tries = sum(1 for r in self.ledger if r.get("entry_t") == et_ and r.get("side") == "modify" and r.get("stop") == new)
        if tries >= 3:
            self.seen.add(("gaveup", et_, new))
            self.log("risk", f"broker refused the stop move to {new:.2f} three times: check account B's stop by hand")
            return
        reason = "BE" if (float(new) - float(pv.get("entry") or new)) * d >= 0 else "STOP MOVE"
        self.route({"sym": sym, "side": "modify", "qty": int(pv.get("qty") or 0), "stop": new, "reason": reason, "entry_t": et_,
                    "src": pv.get("key")})

    def flatten(self, et_, reason, sym, now, px=None):
        """Close B's position at market now (15-minute cut, 15:55, HEDGE, NO TRADE, kill, remote flatten); $ booked from the
        market now and corrected to the strategy's own exit when that is known (cut / 15:55)."""
        pv = self.prov.get(int(et_)) or {}
        q = int(pv.get("qty") or 0)
        if px is None:
            px, _ = self.mark(sym, now)
        d = int(pv.get("dir") or 1)
        e = pv.get("fill") or pv.get("entry")
        pnl = round(q * (d * (float(px) - d * TICK - float(e)) * PV - COMM), 2) if px is not None and e is not None else 0.0
        self.seen.add(("exit", pv.get("key"), int(et_)))
        self.log("risk" if reason in ("HEDGE", "NO TRADE", "KILL SWITCH") else "system",
                 f"{pv.get('short')} {_et(int(et_)):%H:%M} ET: {reason} - flatten {q} MNQ at market" + (f" (~{px:,.2f})" if px is not None else ""))
        self.route({"sym": sym, "side": "exit", "qty": q, "reason": reason, "entry_t": int(et_), "exit_t": int(now), "pnl": pnl,
                    "pnl_est": True, "src": pv.get("key"), "strategy": pv.get("short")})
        pv["flat"] = {"reason": reason, "t": int(now), "px": px}
        if self.open_t is not None and int(self.open_t) == int(et_):
            self.open_t = None
        self._close(int(et_), int(now), pnl, now)
        self._push_outcome(pv, reason, pnl, int(now), q, int(et_))

    def _close(self, entry_t, exit_t, pnl, now):
        with self.mx:
            if any(len(c) > 3 and int(c[3]) == int(entry_t) for c in self.closes):
                return
            self.closes.append([trading_day(exit_t), int(exit_t), float(pnl), int(entry_t)])
            self.closes = self.closes[-1500:]
        self.check_lock(now)
        self.save()

    def kill(self, sym):
        """Flatten B (NinjaTrader: the adapter's kill = FLATTENEVERYTHING on this account)."""
        try:
            if self.adapter is None:
                return {"ok": False, "error": "no adapter"}
            if self.open_t is not None:
                self.flatten(int(self.open_t), "KILL SWITCH", sym, int(self.clock()))
                return (self.ledger[-1].get("result") or {"ok": True}) if self.ledger else {"ok": True}
            if getattr(self.adapter, "kill_flattens_all", False):
                return self.route({"sym": sym, "side": "exit", "reason": "KILL SWITCH", "entry_t": None})
            return {"ok": True, "note": "flat"}
        except Exception as e:
            return {"ok": False, "error": f"{e.__class__.__name__}: {e}"}

    # ---- pushes (the real bot only: LiveBot._push_send)
    def _send(self, p):
        try:
            self.bot._push_send(p)
        except Exception:
            pass

    def _push_text(self, title, body, key):
        try:
            from . import push
            self._send(push.text_payload("PC", "risk", title, body, key=key, t=int(self.clock()), url="#/second"))
        except Exception:
            pass

    def _push_entry(self, act, q):
        try:
            from . import push
            if getattr(self.adapter, "reports_fills", False):
                return
            p = push.entry_payload(self.label, "LONG" if act["side"] == "buy" else "SHORT", q, act["entry_t"], src="pc",
                                   entry=act.get("entry"), stop=act.get("stop"), target=act.get("target"), strategy=act.get("strategy"))
            p["body"] = f"{p['body']} ({act.get('strategy')})"
            p["key"] = f"{p['key']}:acctb"
            self._send(p)
        except Exception:
            pass

    def _push_outcome(self, pv, reason, usd, exit_t, q, et_):
        try:
            from . import push
            if getattr(self.adapter, "reports_fills", False) and reason not in ("HEDGE", "NO TRADE", "TIME", "CUT", "T15", "KILL SWITCH"):
                return
            p = push.outcome_payload(self.label, "LONG" if pv.get("dir") == 1 else "SHORT", reason, usd, int(et_), exit_t, src="pc",
                                     qty=q, strategy=pv.get("short"))
            p["body"] = f"{p['body']} ({pv.get('short')})"
            p["key"] = f"{p['key']}:acctb"
            self._send(p)
        except Exception:
            pass

    # ---- views
    def position(self):
        if self.open_t is None:
            return None
        pv = self.prov.get(int(self.open_t)) or {}
        return {"entry_t": int(self.open_t), "dir": pv.get("dir"), "side": "LONG" if pv.get("dir") == 1 else "SHORT",
                "qty": pv.get("qty"), "entry": pv.get("fill") or pv.get("entry"), "stop": pv.get("stop_now") or pv.get("stop"),
                "target": pv.get("target"), "strategy": pv.get("short"), "key": pv.get("key")}

    def info(self, now=None) -> dict:
        """Heartbeat / live.json / dashboards / Bot Brain: "Account B <name>" with its eval tracker."""
        now = int(now if now is not None else self.clock())
        today = trading_day(now)
        rows = [{k: r.get(k) for k in ("t", "side", "qty", "reason", "pnl", "entry_t", "src", "strategy", "stop", "target")}
                for r in self.ledger if r.get("side") in ("buy", "sell", "exit")][-8:]
        return {"label": self.label, "account": self.name, "plan": self.spec["plan"], "plan_label": self.spec["plan_label"],
                "kind": self.kind(), "sizing": self.spec["sizing"], "keys": list(self.spec["keys"]), "enabled": not self.disabled_reason(),
                "disabled": self.disabled_reason(), "eval": self.eval_view(now), "open": self.position(), "routed": rows,
                "day_pnl": self.day_pnl(today), "entries_today": self.entries_today(today),
                "locked": (self.lock or {}).get("reason") if (self.lock or {}).get("day") == today else None, "size": self.last_size,
                "note": "own account: max 2 trades a day, one position, never opposite to LIT"}

    # ---- persistence
    def blob(self) -> dict:
        with self.mx:
            return {"v": VERSION, "account": self.name, "plan": self.spec["plan"], "eval_start": self.spec.get("eval_start"),
                    "saved_at": int(self.clock()), "ledger": self.ledger[-400:], "closes": list(self.closes),
                    "prov": {str(k): v for k, v in self.prov.items()}, "open_t": self.open_t,
                    "seen": [list(x) for x in list(self.seen)[-600:]], "lock": self.lock, "notified": self.notified[-50:]}

    def save(self):
        if not self.state_path:
            return
        try:
            b = self.blob()
            os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
            tmp = self.state_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(b, fh, default=str)
            os.replace(tmp, self.state_path)
        except Exception as e:
            self.log("warn", f"state save failed: {e.__class__.__name__}: {e}")

    def _load(self):
        try:
            with open(self.state_path, encoding="utf-8") as fh:
                b = json.load(fh)
        except Exception:
            return
        if not isinstance(b, dict) or b.get("account") != self.name:
            return                         # another account's file: start clean (the old one stays on disk)
        self.closes = [list(c) for c in (b.get("closes") or []) if isinstance(c, (list, tuple)) and len(c) >= 3]
        self.ledger = list(b.get("ledger") or [])
        self.prov = {int(k): v for k, v in (b.get("prov") or {}).items() if isinstance(v, dict)}
        self.open_t = b.get("open_t")
        self.seen = {tuple(x) for x in b.get("seen") or []}
        self.notified = list(b.get("notified") or [])
        lk = b.get("lock")
        self.lock = lk if lk and lk.get("day") == trading_day(self.clock()) else None
        if self.open_t is not None:
            pv = self.prov.get(int(self.open_t)) or {}
            self.log("system", f"restored: open {pv.get('short') or pv.get('key')} {'LONG' if pv.get('dir') == 1 else 'SHORT'} "
                               f"{pv.get('qty')} MNQ from {_et(int(self.open_t)):%H:%M} ET (managed to its exit)")


def _state_path_for(bot_state_path: str | None) -> str:
    p = bot_state_path or os.path.join(ROOT, "data", "live_state.json")
    base, ext = os.path.splitext(p)
    return base + "_acctb" + (ext or ".json")


def build(bot, ab: dict | None, **kw):
    """LiveBot: account B from the account_b block (None when off)."""
    if not isinstance(ab, dict) or not ab:
        return None
    lit_acct = None
    try:
        if (bot.cfg or {}).get("adapter") == "ninjatrader":
            from .ninjatrader import resolve_account
            lit_acct = resolve_account(bot.cfg)
    except Exception:
        lit_acct = None
    spec = normalize(ab, lit_account=lit_acct)
    return AccountB(bot, spec, **kw).start() if spec else None


# ---------------------------------------------------------------------------------------------------------------- switch
def set_account_b(account: str | None, plan: str = "builder25k", start: str | None = None, sizing: str = "need",
                  strategies=None, path: str | None = None, selftest=None) -> dict:
    """second_model.json "account_b" = {...} (account set) or null (account None / "off"): the one "account_b" line of
    the file. Switching on is refused when engine.ninjatrader --selftest fails or the block is invalid; the strategies on
    B get "route": false (engine.second.set_route: never also on LIT's account). The rest of the file is untouched."""
    import re
    from . import second
    path = path or second.CFG_PATH
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    c = json.loads(raw)
    old = c.get("account_b")
    if account is None or str(account).strip().lower() in ("off", "none", ""):
        new = None
    else:
        new = {"account": str(account).strip(), "plan": plan, "eval_start": start or _dt.date.today().isoformat(),
               "strategies": list(strategies or ["ema_lon_vix", "macd_sweep", "sr_nyreclaim"]), "sizing": sizing}
        spec = normalize(new, second.load_cfg(path))
        if spec["problem"]:
            return {"ok": False, "error": spec["problem"]}
        ok, line = (selftest or second._selftest_ok)()
        if not ok:
            return {"ok": False, "error": f"engine.ninjatrader --selftest failed ({line}): account B NOT switched on"}
    val = json.dumps(new, ensure_ascii=False)
    rx = re.compile(r'^ "account_b"\s*:.*?,\n(?= "strategies")', re.M | re.S)
    if rx.search(raw):
        out = rx.sub(lambda m: f' "account_b": {val},\n', raw, count=1)
    else:
        out = re.sub(r'^ "strategies"\s*:', lambda m: f' "account_b": {val},\n "strategies":', raw, count=1, flags=re.M)
    chk = json.loads(out)
    if chk.get("account_b") != new or json.dumps(chk["strategies"], sort_keys=True) != json.dumps(c["strategies"], sort_keys=True):
        return {"ok": False, "error": "second_model.json edit check failed: nothing written"}
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(out)
    os.replace(tmp, path)
    routed_off = []
    if new:
        for k in new["strategies"]:
            sc = chk["strategies"].get(k)
            if isinstance(sc, dict) and sc.get("route"):
                r = second.set_route(k, False, path=path)
                if r.get("ok"):
                    routed_off.append(k)
    sim = None
    if new:
        from .ninjatrader import is_sim
        sim = is_sim(new["account"])
    return {"ok": True, "from": old, "to": new, "routed_off": routed_off, "sim": sim}
