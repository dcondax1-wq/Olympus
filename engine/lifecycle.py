"""MFFU account lifecycle for every routed account (2026-11-17: ATLAS's Builder 25K passed at $26,946.10 vs a $26,500 target,
MFFU locked it, every order came back "Your maximum order quantity has been met... Limit: 0 Current: 1. Scope: MNQ Rule
#3787", and nobody was told). Read-only towards the broker: it only STOPS orders and tells the owner; it never arms,
never switches to a new account, never requests a payout.

Accounts (keys): "lit" (Zlarior, LIT's own eval), "atlas" (account B, engine/account_b.py), "rapid" (the Rapid EOD 50K: the
LIT lane of engine/multi_account + RapidAtlas of engine/rapid.py, ONE account, one book), "x:<id>" (extra accounts of
engine/multi_account.py). No NinjaTrader Name is stored or shown: a short hash of it tells a NEW account (fresh row).

Stages (from what the bot already has: the ledger / anchor balance, NinjaTrader's real cash (engine/broker_balance.py),
the EOD floor, the plan rules of engine/multi_account PRESETS + research/lit/mffu_rules.json "limits"):
  eval          trading the eval
  passed        balance >= start + target AND the minimum days (Builder: MFFU's 1, LIT's own eval_life 2; Rapid EOD 4 AND
                its 30% best-day rule)                                                     -> stand down, push
  failed        the closed (EOD) balance <= the max-loss floor                             -> stand down, push
  locked        NinjaTrader refused an entry with MFFU's risk-desk text ("maximum order quantity", "Limit: 0", a risk rule;
                engine/ninjatrader.locked_reject): a locked account, not a bug             -> stand down at once, no retries, push
  funded        trading the funded account
  payout_ready  funded: balance >= start + buffer (+ the Rapid's $1,000 cushion) + MFFU's minimum payout AND the
                consistency / traded-days rules (engine/funded_life.track for Builder)     -> push the $ allowed + the checks
  lost          funded: the balance reached the floor                                      -> stand down, push
Outside hours (16:10-18:00 ET weekdays = MFFU flat time, and the weekend): no entry; a refusal then is never a lock.
passed / failed / locked / lost stick until the account changes (the owner sends Claude the new Name, it goes into the
config, the row starts fresh) or `--clear <key>`. The other accounts always keep trading.

Pushes (engine/push.text_payload via the bot's _push_send, stable keys: once each; board event engine/board_events.emit;
the heartbeat "life" block carries the last ones for the PC report's ntfy push):
  ATLAS 25K PASSED: $26,946        MFFU locks it until the funded account is issued. Send Claude the new account name. ...
  ATLAS 25K LOCKED by MFFU         Orders are refused (...Limit: 0 Current: 1. Scope: MNQ Rule #3787). The bot stopped ...
  Zlarior 50K FAILED: $47,980      The balance reached the max-loss floor $48,000. ...
  ATLAS 25K PAYOUT READY: up to $1,000   $800 to you (80%). Rules: $1,250 above the $1,100 buffer ok, best day 38% ...

  python -X utf8 -m engine.lifecycle                 every account's stage now (data/lifecycle.json)
  python -X utf8 -m engine.lifecycle --clear atlas   start that account's row fresh (after the owner's new account is set)
Tests: python -X utf8 -m tests.test_lifecycle
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import sys
import threading
import time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_PATH = os.path.join(ROOT, "research", "lit", "mffu_rules.json")
FILE = "lifecycle.json"                 # gitignored, next to the bot's state file (data/)
VERSION = 1
STAND_DOWN = ("passed", "failed", "locked", "lost")
STAGES = ("eval", "funded", "payout_ready") + STAND_DOWN
FLAT_FROM, OPEN_AT = 16 * 60 + 10, 18 * 60      # MFFU: flat by 16:10 ET, the next session opens 18:00 ET
TICK_EVERY_S = 30                       # facts are re-read at most this often (a refusal is handled at once)
RECHECK_S = 180                         # a REJECTED without the risk text yet: NinjaTrader's Log is re-read this long
PRICES = {"25K": "$63 (or $43 with a code)", "50K": "$91.80", "Rapid": "about $94 with a code"}
_RULES: dict = {}


def _num(x, d=None):
    try:
        v = float(x)
        return d if v != v else v
    except (TypeError, ValueError):
        return d


def money(x) -> str:
    v = _num(x)
    return "-" if v is None else ("-" if v < 0 else "") + "${:,.0f}".format(abs(v))


def acct_hash(name) -> str | None:
    """A short hash of the NinjaTrader Name (the Name itself is never stored): a different hash = a new account."""
    s = str(name or "").strip()
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:10] if s else None


def _et(t) -> _dt.datetime:
    return _dt.datetime.fromtimestamp(float(t), ET)


def outside_hours(now) -> bool:
    """MFFU's flat time: 16:10-18:00 ET on weekdays, Friday 16:10 to Sunday 18:00. (CME holidays: engine/cme_calendar via
    each account's own guards.)"""
    e = _et(now)
    wd, m = e.weekday(), e.hour * 60 + e.minute
    if wd == 5:
        return True
    if wd == 6:
        return m < OPEN_AT
    if wd == 4 and m >= FLAT_FROM:
        return True
    return FLAT_FROM <= m < OPEN_AT


# ------------------------------------------------------------------------------------------------ the plan numbers
def _rules_file() -> dict:
    if "limits" not in _RULES:
        try:
            with open(RULES_PATH, encoding="utf-8") as fh:
                _RULES["limits"] = (json.load(fh) or {}).get("limits") or {}
        except Exception:
            _RULES["limits"] = {}
    return _RULES["limits"]


def limits(plan: str | None) -> dict:
    """The lifecycle numbers of a plan ("builder50k" / "builder25k" / "rapideod50k" or the multi_account preset name):
    start, target, mll, buffer, pay_min, pay_max, split, cons, cycle_days, min_days, best_day, cushion, size."""
    p = str(plan or "").lower().replace("mffu_", "").replace("_", "")
    if "rapid" in p:
        from . import rapid as R
        if "25k" in p:                                   # the Rapid EOD 25K (engine/rapid.PLANS)
            P = R.plan_info("mffu_rapid_eod_25k")
            return {"start": P["start"], "target": P["target"], "mll": 1000.0, "buffer": P["buffer"], "pay_min": R.PAY_MIN,
                    "pay_max": None, "split": R.SPLIT, "cons": None, "cycle_days": None, "min_days": R.MIN_DAYS,
                    "best_day": R.BEST_DAY, "cushion": P["cushion"], "size": "Rapid", "daily": True}
        return {"start": 50000.0, "target": 3000.0, "mll": 2000.0, "buffer": R.BUFFER, "pay_min": R.PAY_MIN, "pay_max": None,
                "split": R.SPLIT, "cons": None, "cycle_days": None, "min_days": R.MIN_DAYS, "best_day": R.BEST_DAY,
                "cushion": R.CUSHION, "size": "Rapid", "daily": True}
    k = "builder_25k" if "25k" in p else "builder_50k"
    L = {**({"target": 1500.0, "mll": 1000.0, "buffer": 1100.0, "pay_min": 250.0, "pay_max": 1000.0, "split": 0.8, "cons": 0.5,
             "cycle_days": 2} if k == "builder_25k" else
            {"target": 3000.0, "mll": 2000.0, "buffer": 2100.0, "pay_min": 500.0, "pay_max": 2000.0, "split": 0.8, "cons": 0.5,
             "cycle_days": 2}), **{kk: v for kk, v in (_rules_file().get(k) or {}).items() if kk in
                                    ("target", "mll", "buffer", "pay_min", "pay_max", "split", "cons", "cycle_days")}}
    return {**L, "start": 25000.0 if k == "builder_25k" else 50000.0, "min_days": 1, "best_day": None, "cushion": 0.0,
            "size": "25K" if k == "builder_25k" else "50K", "daily": False}


# ------------------------------------------------------------------------------------------------ the pure checks
def payout_check(balance, L: dict, cycle_profit=None, best_day=None, cycle_days=None, paid_today: bool = False) -> dict:
    """Funded: may the owner ask MFFU for a payout now, and how much. balance >= start + buffer (+ cushion) + the minimum,
    the consistency rule (best day <= cons x the cycle's profit) and the cycle's traded days when the plan has them."""
    start = float(L["start"])
    line = start + float(L["buffer"]) + float(L.get("cushion") or 0.0)
    above = round(float(balance) - line, 2)
    checks = [("buffer", above >= float(L["pay_min"]),
               f"{money(max(0.0, above))} above the {money(line)} line (min {money(L['pay_min'])})")]
    if L.get("cons") and cycle_profit is not None:
        cp, bd = float(cycle_profit or 0.0), float(best_day or 0.0)
        pct = round(100.0 * bd / cp) if cp > 0 else None
        checks.append(("consistency", cp > 0 and bd <= float(L["cons"]) * cp + 1e-9,
                       f"best day {pct if pct is not None else '-'}% of the cycle (max {float(L['cons']) * 100:.0f}%)"))
    if L.get("cycle_days") and cycle_days is not None:
        checks.append(("days", int(cycle_days) >= int(L["cycle_days"]), f"{int(cycle_days)}/{int(L['cycle_days'])} traded days"))
    if L.get("daily") and paid_today:
        checks.append(("daily", False, "already paid today"))
    ok = all(c[1] for c in checks)
    amt = max(0.0, above)
    if L.get("pay_max"):
        amt = min(amt, float(L["pay_max"]))
    amt = float(int(amt)) if ok else 0.0
    return {"ok": ok, "amount": amt, "to_you": round(amt * float(L.get("split") or 0.8), 2), "split": float(L.get("split") or 0.8),
            "checks": [{"rule": r, "ok": bool(o), "text": t} for r, o, t in checks]}


def from_track(t: dict) -> dict:
    """engine/funded_life.track (Builder funded) -> the payout_check shape (its "eligible" = MFFU's rules)."""
    t = t or {}
    checks = [{"rule": "buffer", "ok": _num(t.get("above_buffer"), 0) >= _num(t.get("request_min"), 0),
               "text": f"{money(max(0.0, _num(t.get('above_buffer'), 0)))} above the {money(t.get('buffer'))} buffer "
                       f"(min {money(t.get('request_min'))})"},
              {"rule": "consistency", "ok": bool(t.get("cons_ok")),
               "text": f"best day {t.get('best_day_pct') if t.get('best_day_pct') is not None else '-'}% of the cycle "
                       f"(max {_num(t.get('cons_limit_pct'), 50):.0f}%)"},
              {"rule": "days", "ok": int(t.get("cycle_days") or 0) >= int(t.get("cycle_days_need") or 0),
               "text": f"{int(t.get('cycle_days') or 0)}/{int(t.get('cycle_days_need') or 0)} traded days"}]
    ok = bool(t.get("eligible"))
    return {"ok": ok, "amount": float(t.get("max_request") or 0.0) if ok else 0.0, "to_you": float(t.get("to_you") or 0.0) if ok else 0.0,
            "split": float(t.get("split") or 0.8), "checks": checks, "cycle": t.get("cycle_start"), "why": list(t.get("why") or [])[:3],
            "habit_ready": t.get("status") == "ready"}


def detect(f: dict) -> dict:
    """The stage from one account's facts (pure). f: kind eval | funded, start, target, balance (the bot's book), real_balance
    (NinjaTrader's cash, wins when given), floor, days_traded, min_days, best_day_rule (Rapid 0.3), best_day, payout
    (payout_check / from_track), lost. -> {stage, why, balance, src, floor, ...}."""
    kind = "funded" if f.get("kind") == "funded" else "eval"
    start = float(f.get("start") or 0.0)
    real = _num(f.get("real_balance"))
    bal = real if real is not None else _num(f.get("balance"))
    floor = _num(f.get("floor"))
    out = {"kind": kind, "balance": round(bal, 2) if bal is not None else None, "src": "NinjaTrader" if real is not None else "ledger",
           "floor": round(floor, 2) if floor is not None else None}
    if bal is None:
        return {**out, "stage": kind, "why": "no balance yet"}
    if kind == "funded":
        if f.get("lost") or (floor is not None and bal <= floor + 1e-9):
            return {**out, "stage": "lost", "why": f"balance {money(bal)} reached the floor {money(floor)}"}
        p = f.get("payout") or {}
        if p.get("ok") and float(p.get("amount") or 0) > 0:
            return {**out, "stage": "payout_ready", "why": f"up to {money(p['amount'])} allowed", "payout": p}
        return {**out, "stage": "funded", "why": "; ".join(p.get("why") or []) or "building to the payout line", "payout": p or None}
    if floor is not None and bal <= floor + 1e-9:
        return {**out, "stage": "failed", "why": f"balance {money(bal)} at or below the max-loss floor {money(floor)}"}
    goal = start + float(f.get("target") or 0.0)
    out["goal"] = round(goal, 2)
    if bal >= goal - 1e-9:
        days, mind = int(f.get("days_traded") or 0), int(f.get("min_days") or 0)
        ok_days = days >= mind or mind <= 1                      # the target needs a traded day: 1 day is always met
        rule, best, prof = _num(f.get("best_day_rule")), _num(f.get("best_day")), bal - start
        ok_best = rule is None or best is None or best <= rule * prof + 1e-9
        if ok_days and ok_best:
            return {**out, "stage": "passed", "why": f"balance {money(bal)} >= the {money(goal)} target, {days} traded days"}
        wait = []
        if not ok_days:
            wait.append(f"{days} of {mind} days")
        if not ok_best:
            wait.append(f"best day {money(best)} is over {rule * 100:.0f}% of {money(prof)}")
        return {**out, "stage": "eval", "why": "target reached, waiting: " + ", ".join(wait)}
    return {**out, "stage": "eval", "why": f"{money(goal - bal)} to the target"}


# ------------------------------------------------------------------------------------------------ the texts
def texts(stage: str, label: str, d: dict) -> tuple:
    """(title, body) of a stage's push, $ first, plain words."""
    size = "Rapid" if "Rapid" in label else "25K" if "25K" in label else "50K"
    if stage == "passed":
        return (f"{label} PASSED: {money(d.get('balance'))}",
                "MFFU locks it until the funded account is issued. Send Claude the new account name. No more orders go to it; "
                "the other accounts keep trading.")
    if stage == "locked":
        return (f"{label} LOCKED by MFFU",
                f"Orders are refused ({d.get('why') or 'risk rule'}). The bot stopped sending orders to it (no retries); the other "
                "accounts keep trading. If it just passed: send Claude the new funded account name.")
    if stage == "failed":
        return (f"{label} FAILED: {money(d.get('balance'))}",
                f"The balance reached the max-loss floor {money(d.get('floor'))}. No more orders go to it; the other accounts keep "
                f"trading. Buy a new one at your price ({PRICES[size]}), then send Claude the new account name.")
    if stage == "lost":
        return (f"{label} funded account LOST: {money(d.get('balance'))}",
                f"The balance reached the floor {money(d.get('floor'))}. No more orders go to it; the other accounts keep trading. "
                f"Buy a new eval at your price ({PRICES[size]}).")
    if stage == "payout_ready":
        p = d.get("payout") or {}
        rules = ", ".join(f"{c['text']} {'ok' if c['ok'] else 'NO'}" for c in p.get("checks") or [])
        return (f"{label} PAYOUT READY: up to {money(p.get('amount'))}",
                f"{money(p.get('to_you'))} to you ({float(p.get('split') or 0.8) * 100:.0f}%). Rules: {rules}. Request it in the MFFU "
                "dashboard; the bot never requests it.")
    return (f"{label}: {stage}", str(d.get("why") or ""))


# ------------------------------------------------------------------------------------------------ the book
class Book:
    """Every account's stage, persisted (data/lifecycle.json next to the bot's state file). send(payload) = the bot's phone
    push (None = silent); emit(kind, key, text, data) = the comms board (engine/board_events.emit by default)."""

    def __init__(self, path: str, send=None, emit=None, clock=time.time):
        self.path, self.send, self.clock = path, send, clock
        self.emit = emit
        self.mx = threading.RLock()
        self.rows: dict = {}
        self.events: list = []
        self.pending: list = []
        self.last_tick = 0.0
        self._load()

    # ---- file
    def _load(self):
        try:
            with open(self.path, encoding="utf-8") as fh:
                d = json.load(fh) or {}
            self.rows = {str(k): v for k, v in (d.get("rows") or {}).items() if isinstance(v, dict)}
            self.events = [e for e in (d.get("events") or []) if isinstance(e, dict)][-10:]
        except Exception:
            self.rows, self.events = {}, []

    def save(self):
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump({"v": VERSION, "rows": self.rows, "events": self.events[-10:]}, fh, indent=1, sort_keys=True)
            from .fsutil import replace as _fs_replace   # retried on a Windows / OneDrive lock
            _fs_replace(tmp, self.path)
        except Exception:
            pass

    # ---- rows
    def _row(self, key: str, label: str, acct: str | None) -> dict:
        r = self.rows.get(key)
        h = acct_hash(acct) if acct else None
        if r is None or (h and r.get("acct") and r["acct"] != h):
            r = self.rows[key] = {"stage": None, "since": None, "why": "", "label": label, "acct": h, "notified": []}
        if h and not r.get("acct"):
            r["acct"] = h
        r["label"] = label
        return r

    def stage(self, key: str) -> str | None:
        return (self.rows.get(key) or {}).get("stage")

    def block(self, key: str, now=None) -> str | None:
        """Why this account takes no new entry (None = it may). Stood-down stages first, then MFFU's flat time."""
        r = self.rows.get(key) or {}
        if r.get("stage") in STAND_DOWN:
            return f"{r.get('label') or key} {r['stage'].upper()}: stood down ({r.get('why') or '-'}), no orders to it"
        if outside_hours(self.clock() if now is None else now):
            return "outside MFFU hours (flat 16:10-18:00 ET and the weekend)"
        return None

    def _set(self, key: str, label: str, d: dict, now, acct=None, push: bool = True) -> dict | None:
        stage = d["stage"]
        with self.mx:
            r = self._row(key, label, acct)
            old = r.get("stage")
            if old in STAND_DOWN and stage not in STAND_DOWN:
                return None                                   # sticky until a new account / --clear
            if old in STAND_DOWN and stage in STAND_DOWN and not (old == "locked" and stage in ("passed", "failed", "lost")):
                return None                                   # locked -> passed / failed is more precise; nothing else moves
            changed = old != stage
            r.update({"why": str(d.get("why") or "")[:200], "bal": d.get("balance"), "src": d.get("src")})
            if changed:
                r["stage"], r["since"] = stage, int(now)
            if stage not in STAND_DOWN and stage != "payout_ready":
                if changed:
                    self.save()
                return None
            nkey = f"life:{stage}:{key}:{r.get('acct') or '-'}" + (f":{(d.get('payout') or {}).get('cycle') or _et(now).date()}"
                                                                  if stage == "payout_ready" else "")
            if nkey in r["notified"]:
                if changed:
                    self.save()
                return None
            r["notified"] = (r["notified"] + [nkey])[-20:]
            title, body = texts(stage, label, d)
            ev = {"t": int(now), "key": key, "stage": stage, "title": title, "body": body, "push": nkey}
            self.events = (self.events + [ev])[-10:]
            self.save()
        self._tell(ev, d, push)
        return ev

    def _tell(self, ev: dict, d: dict, push: bool):
        try:
            em = self.emit
            if em is None:
                from . import board_events
                em = board_events.emit
            em(f"life_{ev['stage']}", ev["key"], f"{ev['title']}. {ev['body']}",
               {"stage": ev["stage"], "balance": d.get("balance"), "floor": d.get("floor"), "src": d.get("src"),
                **({"payout": {k: (d.get("payout") or {}).get(k) for k in ("amount", "to_you")}} if ev["stage"] == "payout_ready" else {})})
        except Exception:
            pass
        if not push or self.send is None:
            return
        try:
            from . import push as P
            self.send(P.text_payload("PC", "risk", ev["title"][:120], ev["body"][:600], key=ev["push"], t=ev["t"], url="#/accounts"))
        except Exception:
            pass

    # ---- inputs
    def update(self, key: str, label: str, facts: dict | None, now=None, push: bool = True) -> dict | None:
        """One account's facts -> its stage; the event when it moved to a stand-down / payout stage (pushed once)."""
        if not facts:
            return None
        now = self.clock() if now is None else now
        d = detect(facts)
        if d["stage"] == "payout_ready" and (d.get("payout") or {}).get("habit_ready"):
            push = False                                      # engine/funded_life pushes "PAYOUT READY: request" right now
        return self._set(key, label, d, now, facts.get("acct"), push=push and not facts.get("pushed"))

    def on_reject(self, key: str, label: str, adapter, action: dict, res: dict, now=None, acct=None) -> dict | None:
        """An entry's NOT-OK answer: MFFU's risk-desk text = LOCKED (stand down at once). Outside hours never a lock."""
        try:
            if (action or {}).get("side") not in ("buy", "sell") or not isinstance(res, dict) or res.get("ok") is not False:
                return None
            now = self.clock() if now is None else now
            if outside_hours(now):
                return None
            from .ninjatrader import locked_reject
            et_ = int((action or {}).get("entry_t") or 0)
            why = locked_reject(adapter, et_, res, now=now)
            if not why:
                if "REJECTED" in str(res.get("error") or "").upper() and getattr(adapter, "folder", None):
                    with self.mx:                             # NinjaTrader's Log may write the reason a moment later
                        self.pending = (self.pending + [(key, label, adapter, et_, res, float(now), acct)])[-10:]
                return None
            return self._set(key, label, {"stage": "locked", "why": why}, now, acct)
        except Exception:
            return None

    def recheck(self, now=None) -> list:
        now = self.clock() if now is None else now
        out, keep = [], []
        with self.mx:
            pend, self.pending = self.pending, []
        for key, label, ad, et_, res, t0, acct in pend:
            try:
                from .ninjatrader import nt_reject_text
                why = nt_reject_text(ad, et_)
                if why:
                    ev = self._set(key, label, {"stage": "locked", "why": why}, now, acct)
                    if ev:
                        out.append(ev)
                elif now - t0 < RECHECK_S:
                    keep.append((key, label, ad, et_, res, t0, acct))
            except Exception:
                continue
        with self.mx:
            self.pending = keep + self.pending
        return out

    def clear(self, key: str) -> bool:
        with self.mx:
            hit = self.rows.pop(key, None) is not None
            self.save()
        return hit

    def hb_block(self) -> dict | None:
        """The heartbeat's "life" block (< 1.5 KB): each account's stage + the last 3 events (the PC report pushes them)."""
        if not self.rows:
            return None
        return {"v": VERSION,
                "acc": {k: {"label": r.get("label"), "stage": r.get("stage"), "since": r.get("since"), "why": str(r.get("why") or "")[:100],
                            "bal": r.get("bal")} for k, r in sorted(self.rows.items())},
                "ev": [{k: e.get(k) for k in ("t", "key", "stage", "title", "body", "push")} for e in self.events[-3:]]}


# ------------------------------------------------------------------------------------------------ the bot's glue
def book_for(bot, create: bool = True) -> Book | None:
    """The bot's Book (one per bot, data/lifecycle.json next to its state file). Never raises."""
    try:
        b = getattr(bot, "_life_book", None)
        if isinstance(b, Book) or not create or bot is None:
            return b if isinstance(b, Book) else None
        sp = getattr(bot, "state_path", None) or os.path.join(ROOT, "data", "live_state.json")
        b = Book(os.path.join(os.path.dirname(os.path.abspath(sp)), FILE), send=getattr(bot, "_push_send", None),
                 clock=getattr(bot, "clock", time.time))
        bot._life_book = b
        return b
    except Exception:
        return None


def block(bot, key: str, now=None) -> str | None:
    """Entry gate for one account (None = route). A lifecycle bug never blocks trading (fails open)."""
    try:
        b = book_for(bot)
        return b.block(key, now) if b is not None else None
    except Exception:
        return None


def is_stood_down(bot, key: str) -> bool:
    b = book_for(bot, create=False)
    return bool(b) and b.stage(key) in STAND_DOWN


def after_route(bot, key: str, label: str, adapter, action: dict, res: dict, acct=None):
    """After an order: a refused entry with MFFU's risk text locks that account. Never raises."""
    try:
        if (action or {}).get("side") in ("buy", "sell") and isinstance(res, dict) and res.get("ok") is False:
            b = book_for(bot)
            if b is not None:
                return b.on_reject(key, label, adapter, action, res, acct=acct)
    except Exception:
        return None
    return None


def label_of(key: str, obj=None) -> str:
    if key == "lit":
        return "Zlarior 50K"
    if key in ("rapid", "rapid2"):
        lab = "Rapid EOD 25K" if "25k" in str(((getattr(obj, "spec", None) or {}).get("preset")) or "") else "Rapid EOD 50K"
        return lab + (" (#2)" if key == "rapid2" else "")
    if key == "atlas":
        plan = str(((getattr(obj, "spec", None) or {}).get("plan")) or "")
        return "ATLAS " + ("50K" if "50k" in plan else "25K")
    return str((getattr(obj, "spec", None) or {}).get("name") or getattr(obj, "name", None) or key)


def key_of(obj) -> str:
    """The lifecycle key of an account object: RapidAtlas / the rapid lane -> "rapid", AccountB -> "atlas", extra -> x:<id>."""
    spec = getattr(obj, "spec", None) or {}
    if spec.get("lane") == "rapid" or callable(getattr(obj, "yield_to_lit", None)):
        # the 2nd Rapid (engine/rapid slot "rapid2") has its own key: one Rapid passing / failing never stands the other down
        return "rapid2" if (spec.get("slot") == "rapid2" or getattr(obj, "slot", None) == "rapid2") else "rapid"
    if hasattr(obj, "prov"):
        return "atlas"
    return f"x:{getattr(obj, 'id', None) or spec.get('id') or '?'}"


def _cash(broker, name, rules) -> float | None:
    try:
        row = broker.row(name, rules) if broker is not None and name else None
        return _num(row.get("cash")) if row else None
    except Exception:
        return None


def _today_pnl(obj, today) -> float:
    try:
        return float(obj.day_pnl(today) or 0.0)
    except Exception:
        return 0.0


def lit_facts(bot, now) -> dict | None:
    v = (getattr(bot, "state", None) or {}).get("eval_life")
    if not isinstance(v, dict) or v.get("status") not in ("open", "passed", "failed") or v.get("balance") is None:
        return None
    from . import eval_life as EL
    start = float(EL.START_BAL)
    cfg = getattr(bot, "cfg", None) or {}
    name = cfg.get("nt_account") or getattr(getattr(bot, "adapter", None), "account", None)
    real = None
    if cfg.get("adapter") == "ninjatrader":
        from . import broker_balance as BB
        real = _cash(BB.for_bot(bot), name, {"start": start, "target": 3000.0, "mll": 2000.0, "lock": 100.0})
    floor = v.get("floor")
    if floor is None and v.get("room") is not None:
        floor = float(v["balance"]) - float(v["room"])
    return {"kind": "eval", "start": start, "target": float(v.get("target_balance") or start + 3000.0) - start,
            "balance": v["balance"], "real_balance": real, "floor": floor, "days_traded": v.get("days_traded"),
            "min_days": v.get("min_days") or 2, "acct": name or "lit",
            "pushed": v.get("status") in ("passed", "failed")}   # engine/eval_life pushes EVAL PASSED / FAILED itself


def atlas_facts(ab, now) -> dict | None:
    ev = ab.eval_view(now)
    if not isinstance(ev, dict) or ev.get("error") or ev.get("room") is None or ev.get("balance") is None:
        return None
    L = limits(ab.spec.get("plan"))
    if ev.get("stage") == "funded":
        return {"kind": "funded", "start": ev.get("plan_start") or L["start"], "balance": ev["balance"], "floor": ev.get("floor"),
                "lost": ev.get("status") == "lost", "payout": from_track(ev.get("funded") or {}), "acct": ab.name,
                "pushed": ev.get("status") == "lost"}         # engine/funded_life pushes FUNDED ACCOUNT LOST itself
    from . import account_b as AB
    today = AB.trading_day(now)
    real = _cash(ab._broker(), ab.name, ab.rules)
    return {"kind": "eval", "start": ev["start_balance"], "target": float(ev["target"]) - float(ev["start_balance"]),
            "balance": ev["balance"], "real_balance": real, "floor": ev.get("floor"),
            "days_traded": int(ev.get("days_traded") or 0) + (1 if abs(_today_pnl(ab, today)) > 1e-9 else 0),
            "min_days": L["min_days"], "acct": ab.name,
            "pushed": ev.get("status") in ("passed", "failed")}  # account B pushes EVAL PASSED / FAILED from its own book


def rapid_facts(ra, lane, now) -> dict | None:
    """The Rapid EOD 50K (one account, one book): RapidAtlas when on, else the LIT lane (engine/multi_account)."""
    from . import multi_account as MA
    pre = str(((getattr(ra, "spec", None) or getattr(lane, "spec", None) or {}).get("preset")) or "")
    L = limits("rapideod25k" if "25k" in pre else "rapideod50k")
    start = float(L["start"])
    today = MA.trading_day(now)
    if ra is not None:
        ev = ra.eval_view(now)
        if not isinstance(ev, dict) or ev.get("error") or ev.get("balance") is None:
            return None
        if ra.funded():
            t = ra.funded_view(now)
            pays = (ra.spec.get("funded") or {}).get("payouts") or {}
            p = payout_check(t.get("balance") or 0.0, L, paid_today=today in pays)
            p["habit_ready"] = bool(t.get("ready"))           # RapidAtlas pushes "Rapid EOD: request $X" itself
            if t.get("since_short") is not None:              # the 25K: MFFU's >= $250 net since the last payout
                p["checks"].append({"rule": "since", "ok": False, "text": f"{money(t['since_short'])} more since the last payout"})
                p.update({"ok": False, "amount": 0.0, "to_you": 0.0})
            return {"kind": "funded", "start": start, "balance": t.get("balance"), "floor": ev.get("floor"),
                    "lost": ev.get("status") == "lost", "payout": p, "acct": ra.name, "pushed": ev.get("status") == "lost"}
        dd = {d: v for d, v in ra.days(today).items() if abs(v) > 1e-9}
        return {"kind": "eval", "start": start, "target": L["target"], "balance": ev["balance"],
                "real_balance": _cash(ra._broker(), ra.name, ra.rules), "floor": ev.get("floor"), "days_traded": len(dd),
                "min_days": L["min_days"], "best_day_rule": L["best_day"], "best_day": max(dd.values()) if dd else 0.0, "acct": ra.name,
                "pushed": ev.get("status") in ("passed", "failed")}   # RapidAtlas (account B's code) pushes them itself
    if lane is None:
        return None
    funded = lane.mode == "funded"
    st = lane.state(today, raw=True)
    if not st:
        return None
    if funded:
        bal = start + float(st.get("balance") or 0.0) + float(st.get("cum") or 0.0)
        pays = (lane.spec.get("funded") or {}).get("payouts") or {}
        return {"kind": "funded", "start": start, "balance": bal, "floor": start + float(st.get("floor") or 0.0),
                "payout": payout_check(bal, L, paid_today=today in pays), "acct": lane.spec.get("nt_account") or lane.id}
    bal = start + float(st.get("profit") or 0.0) + float(st.get("cum") or 0.0)
    dd = {d: v for d, v in lane.eval_days().items() if d != "0000-00-00" and abs(v) > 1e-9}
    return {"kind": "eval", "start": start, "target": L["target"], "balance": bal,
            "real_balance": _cash(lane._broker(), lane._broker_name(), lane.rules), "floor": bal - float(st.get("room") or 0.0),
            "days_traded": len(dd), "min_days": L["min_days"], "best_day_rule": L["best_day"],
            "best_day": max(dd.values()) if dd else 0.0, "acct": lane.spec.get("nt_account") or lane.id}


def _extra_min_days(a) -> int:
    """An extra account's minimum days: its rules' "min_days", else the sizer's two_week min_days (default 2: after the
    target the sizer trades one 1-micro minimum-days trade on a later session; standing down before it would skip it)."""
    if a.rules.get("min_days"):
        return int(a.rules["min_days"])
    try:
        from . import sizing as SZ
        tw = (_sizing_of(a) or {}).get("two_week") or {}
        return int(tw.get("min_days", SZ.TW_DEFAULT["min_days"]) or 1)
    except Exception:
        return 2


def _sizing_of(a) -> dict:
    from . import multi_account as MA
    return MA.sizing_cfg(getattr(a.router, "base_sizing", lambda: {})(), a.spec)


def extra_facts(a, now) -> dict | None:
    from . import multi_account as MA
    from . import funded_life as FL
    today = MA.trading_day(now)
    R = a.rules
    start = float(R.get("start") or 50000.0)
    if a.mode == "funded":
        f = a.spec.get("funded") or {}
        days = {d: v for d, v in a.eval_days().items() if d != "0000-00-00"}
        t = FL.track(days, f.get("payouts") or {}, FL.plan_of(a.spec.get("preset")), today=today, start=f.get("start"), name=a.name)
        return {"kind": "funded", "start": start, "balance": t.get("balance"), "floor": t.get("floor"), "lost": bool(t.get("lost")),
                "payout": from_track(t), "acct": a.spec.get("nt_account") or a.id, "pushed": bool(t.get("lost"))}
    if a.mode not in MA.EVAL_MODES:
        return None
    st = a.state(today, raw=True)
    if not st:
        return None
    bal = start + float(st.get("profit") or 0.0) + float(st.get("cum") or 0.0)
    dd = {d: v for d, v in a.eval_days().items() if d != "0000-00-00" and abs(v) > 1e-9}
    best_rule = _num(R.get("best_day"))
    return {"kind": "eval", "start": start, "target": float(R.get("target") or 3000.0), "balance": bal,
            "real_balance": _cash(a._broker(), a._broker_name(), R), "floor": bal - float(st.get("room") or 0.0),
            "days_traded": len(dd), "min_days": _extra_min_days(a), "best_day_rule": best_rule,
            "best_day": max(dd.values()) if dd else 0.0, "acct": a.spec.get("nt_account") or a.id}


def tick(bot, now=None, force: bool = False) -> list:
    """Once per poll (throttled to TICK_EVERY_S): every routed account's facts -> its stage; late NinjaTrader Log reasons.
    Never raises; one account's error never touches the others."""
    out = []
    b = book_for(bot)
    if b is None:
        return out
    now = b.clock() if now is None else now
    try:
        out += b.recheck(now)
    except Exception:
        pass
    if not force and now - b.last_tick < TICK_EVERY_S:
        return out
    b.last_tick = now
    jobs = []
    if (getattr(bot, "state", None) or {}).get("model", "lit") == "lit":
        jobs.append(("lit", None, lambda: lit_facts(bot, now)))
    ab = getattr(bot, "acct_b", None)
    if ab is not None and not getattr(ab, "problem", None):
        jobs.append(("atlas", ab, lambda: atlas_facts(ab, now)))
    ra = getattr(bot, "acct_r", None)
    accts = list(getattr(getattr(bot, "accts", None), "accounts", None) or [])
    lane = next((a for a in accts if (a.spec or {}).get("lane") == "rapid" and (a.spec or {}).get("slot") != "rapid2"), None)
    if ra is not None or lane is not None:
        jobs.append(("rapid", ra or lane, lambda: rapid_facts(ra, lane, now)))
    ra2 = getattr(bot, "acct_r2", None)              # the 2nd Rapid (data/rapid2.json): its own key "rapid2"
    lane2 = next((a for a in accts if (a.spec or {}).get("lane") == "rapid" and (a.spec or {}).get("slot") == "rapid2"), None)
    if ra2 is not None or lane2 is not None:
        jobs.append(("rapid2", ra2 or lane2, lambda: rapid_facts(ra2, lane2, now)))
    for a in accts:
        if a is not lane and a is not lane2 and not getattr(a, "problem", None):
            jobs.append((f"x:{a.id}", a, (lambda a=a: extra_facts(a, now))))
    for key, obj, fn in jobs:
        try:
            ev = b.update(key, label_of(key, obj), fn(), now)
            if ev:
                out.append(ev)
        except Exception:
            continue
    return out


def hb_block(bot) -> dict | None:
    b = book_for(bot, create=False)
    try:
        return b.hb_block() if b is not None else None
    except Exception:
        return None


# ------------------------------------------------------------------------------------------------ CLI
def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="MFFU account lifecycle (read-only; never arms or switches accounts)")
    ap.add_argument("--clear", help="start this account's row fresh (lit / atlas / rapid / x:<id>)")
    ap.add_argument("--path", default=os.path.join(ROOT, "data", FILE))
    a = ap.parse_args(argv)
    b = Book(a.path)
    if a.clear:
        print(f"{a.clear}: {'cleared' if b.clear(a.clear) else 'no row'}")
        return 0
    if not b.rows:
        print("no account seen yet (the bot writes data/lifecycle.json once it runs)")
    for k, r in sorted(b.rows.items()):
        since = _et(r["since"]).strftime("%a %b %d %H:%M ET") if r.get("since") else "-"
        print(f"{r.get('label') or k:16s} {str(r.get('stage') or '-').upper():13s} since {since}  {money(r.get('bal'))}  {r.get('why') or ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
