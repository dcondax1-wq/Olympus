"""Real balance from NinjaTrader (2026-10-25, owner: "the bot should adapt to the balance like a person").

ninjatrader/LE_BarFeed.cs writes Documents\\NinjaTrader 8\\le_feed\\accounts.csv once a minute and on account updates:

    name,time,cash,realized,unrealized,netliq        time = unix seconds (UTC); netliq empty / 0 = not available

This module reads it (fresh < 3 min, sane values, never a Sim / Playback account) and, per NinjaTrader account Name:

  (a) AUTO-ANCHOR at the day close: the last fresh CashValue of a trading day (the CME close 17:00 ET; the value seen last
      before 18:00) becomes that day's eval anchor {"as_of", "balance", "floor"} (engine/sizing.eval_anchor):
      balance = the real balance, floor = max(previous floor, real EOD balance - MLL), locked at start + lock (MFFU: 50K
      MLL $2,000, 25K $1,000, lock +$100); never above the balance (a failed eval reads room 0). The bot's book then starts
      from the broker's own number every day, so commissions ($1.90 real vs $1.40 booked), slippage and manual trades are
      absorbed. The anchors live in data/broker_balance.json (gitignored), next to the bot's state file.
  (b) ROOM CAP intraday: sizing uses min(ledger room, real room) where real room = NetLiquidation (or cash + unrealized)
      - the book's floor. Never more than either.
  (c) DRIFT: real cash vs the bot's closed-ledger balance differ by more than $50 for 5+ minutes -> one push a day
      "Balance differs" with both numbers.
  (d) Stale / missing / insane file -> nothing at all changes (the ledger + eval_anchor.json behaviour exactly).

Switch: start cfg or lit_sizing "broker_balance": true / false; unset = on for the real bot (data/live_state.json) whenever
the file is present and fresh (test harnesses with their own state file never read the owner's NinjaTrader folder).
Read-only towards the broker: it never sends, arms or routes anything.

  python -m engine.broker_balance            what the bot reads now (every account row, fresh / stale, sane)
  python -m engine.broker_balance --selftest
"""
from __future__ import annotations

import datetime as _dt
import json
import math
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEED_DIR = "le_feed"
FILE = "accounts.csv"
STATE_FILE = "broker_balance.json"       # gitignored (data/): {"v", "accounts": {name: {"eval_start", "last", "anchor", ...}}}
MAX_AGE_S = 180                          # a row older than 3 minutes is stale
DRIFT_USD = 50.0                         # real vs ledger difference that pushes "Balance differs"
DRIFT_HOLD_S = 300                       # ... when it lasts this long (a fill and the bot's ledger line arrive minutes apart)
SIM = re.compile(r"^(Sim|Playback|Backtest)\d*$", re.I)
R50K = {"start": 50000.0, "target": 3000.0, "mll": 2000.0, "lock": 100.0}
R25K = {"start": 25000.0, "target": 1500.0, "mll": 1000.0, "lock": 100.0}


def _f(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _trading_day(ts) -> str:
    from .live import trading_day
    return trading_day(ts)


# ------------------------------------------------------------------------------------------------ parse / read
def parse(text: str) -> dict:
    """accounts.csv text -> {name: {"name", "t", "cash", "realized", "unrealized", "netliq"}}; the newest row per name.
    Bad lines are skipped; a missing number is None."""
    out: dict = {}
    for ln in (text or "").splitlines():
        p = [s.strip() for s in ln.split(",")]
        if len(p) < 3 or p[0].lower() == "name" or not p[0]:
            continue
        t = _f(p[1])
        if t is None:
            continue
        row = {"name": p[0], "t": int(t), "cash": _f(p[2]),
               "realized": _f(p[3]) if len(p) > 3 else None,
               "unrealized": _f(p[4]) if len(p) > 4 else None,
               "netliq": _f(p[5]) if len(p) > 5 else None}
        old = out.get(row["name"])
        if old is None or row["t"] >= old["t"]:
            out[row["name"]] = row
    return out


def sane(row: dict | None, rules: dict | None = None) -> tuple:
    """(ok, why). A plausible eval account: cash > 0 and, with rules, within start - mll - $1,000 .. start + target + $10,000
    (a Sim101 at $100,000 or a different account is refused); |unrealized| < $25,000."""
    if not row or row.get("cash") is None:
        return False, "no cash value"
    c = float(row["cash"])
    if c <= 0:
        return False, f"cash ${c:,.2f} is not a balance"
    u = row.get("unrealized")
    if u is not None and abs(float(u)) > 25000:
        return False, f"unrealized ${float(u):,.2f} is not plausible"
    if rules:
        lo = float(rules["start"]) - float(rules["mll"]) - 1000.0
        hi = float(rules["start"]) + float(rules["target"]) + 10000.0
        if not lo <= c <= hi:
            return False, f"cash ${c:,.2f} is outside the plan's ${lo:,.0f}-${hi:,.0f}"
    return True, ""


def read(folder: str | None = None, now=None, max_age: float = MAX_AGE_S, path: str | None = None) -> dict:
    """{"ok", "why", "path", "rows": {name: row with "age_s", "fresh"}}. ok = the file exists and at least one row is fresh."""
    if path is None:
        from .ninjatrader import default_folder
        path = os.path.join(folder or default_folder(), FEED_DIR, FILE)
    now = int(now if now is not None else time.time())
    out = {"ok": False, "why": "", "path": path, "rows": {}}
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            rows = parse(fh.read())
    except FileNotFoundError:
        out["why"] = "no accounts.csv (LE_BarFeed with the account export not running)"
        return out
    except OSError as e:
        out["why"] = f"accounts.csv unreadable: {e.__class__.__name__}"
        return out
    for n, r in rows.items():
        r["age_s"] = now - int(r["t"])
        r["fresh"] = -120 <= r["age_s"] <= max_age
    out["rows"] = rows
    out["ok"] = any(r["fresh"] for r in rows.values())
    if not rows:
        out["why"] = "accounts.csv has no account row"
    elif not out["ok"]:
        out["why"] = f"accounts.csv is stale ({min(r['age_s'] for r in rows.values())} s old)"
    return out


# ------------------------------------------------------------------------------------------------ the math
def rules_for(rules: dict | None) -> dict:
    r = {**R50K, **(rules or {})}
    return {k: float(r[k]) for k in ("start", "target", "mll", "lock")}


def next_floor(prev_floor: float | None, eod: float, rules: dict | None = None) -> float:
    """MFFU EOD trailing floor after a day that closed at `eod`: max(previous floor, eod - MLL), locked at start + lock,
    never above eod (a failed eval = room 0)."""
    R = rules_for(rules)
    lock = R["start"] + R["lock"]
    f = eod - R["mll"] if prev_floor is None else max(float(prev_floor), eod - R["mll"])
    f = min(f, lock) if (prev_floor is None or float(prev_floor) <= lock) else float(prev_floor)
    return round(min(f, eod), 2)


def real_equity(row: dict) -> float:
    """NetLiquidation when NinjaTrader gives one (> 0), else cash + unrealized."""
    nl = row.get("netliq")
    if nl is not None and float(nl) > 0:
        return float(nl)
    return float(row["cash"]) + float(row.get("unrealized") or 0.0)


def cap_room(ledger_room, row: dict | None, floor) -> tuple:
    """(room, real_room): min(ledger room, real equity - floor). No row / floor -> (ledger room, None)."""
    if row is None or floor is None or ledger_room is None:
        return ledger_room, None
    rr = round(real_equity(row) - float(floor), 2)
    return round(min(float(ledger_room), rr), 2), rr


# ------------------------------------------------------------------------------------------------ the per-bot reader
class Broker:
    """One per bot process (for_bot). Reads accounts.csv (cached by modification time), keeps the daily anchors."""

    def __init__(self, path: str, state_path: str, clock=time.time):
        self.path, self.state_path, self.clock = path, state_path, clock
        self._snap = None
        self._mt = None
        self.state = self._load()
        self.drift_seen: dict = {}

    # ---- file
    def snap(self, now=None) -> dict:
        now = int(now if now is not None else self.clock())
        try:
            mt = os.path.getmtime(self.path)
        except OSError:
            mt = None
        if self._snap is None or mt != self._mt or mt is None:
            self._snap = read(now=now, path=self.path)
            self._mt = mt
        else:                                      # same file: only the ages move
            for r in self._snap["rows"].values():
                r["age_s"] = now - int(r["t"])
                r["fresh"] = -120 <= r["age_s"] <= MAX_AGE_S
            self._snap["ok"] = any(r["fresh"] for r in self._snap["rows"].values())
        return self._snap

    def row(self, name: str | None, rules: dict | None = None, now=None) -> dict | None:
        """This account's fresh, sane row; None otherwise (missing / stale / Sim / insane)."""
        if not name or SIM.match(str(name).strip()):
            return None
        r = self.snap(now)["rows"].get(str(name).strip())
        if not r or not r.get("fresh"):
            return None
        return r if sane(r, rules_for(rules))[0] else None

    # ---- stored anchors
    def _load(self) -> dict:
        try:
            with open(self.state_path, encoding="utf-8") as fh:
                d = json.load(fh)
            if isinstance(d, dict) and isinstance(d.get("accounts"), dict):
                return d
        except Exception:
            pass
        return {"v": 1, "accounts": {}}

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
            tmp = self.state_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self.state, fh, indent=1)
            os.replace(tmp, self.state_path)
        except OSError:
            pass

    def _rec(self, name: str, eval_start: str | None) -> dict:
        acc = self.state.setdefault("accounts", {})
        rec = acc.get(name)
        if not isinstance(rec, dict) or rec.get("eval_start") != (eval_start or None):
            rec = acc[name] = {"eval_start": eval_start or None}      # a new eval on this Name: start over
        return rec

    def anchor(self, name: str | None, eval_start: str | None) -> dict | None:
        """The last real-EOD anchor of this account for this eval (None when there is none)."""
        if not name:
            return None
        rec = (self.state.get("accounts") or {}).get(str(name).strip())
        if not isinstance(rec, dict) or rec.get("eval_start") != (eval_start or None):
            return None
        from . import sizing as sz
        a = sz.eval_anchor(rec.get("anchor"))
        if a and eval_start and a["as_of"] < str(eval_start):
            return None
        return a

    def observe(self, name: str | None, eval_start: str | None, rules: dict | None, book_floor=None, now=None) -> dict | None:
        """Every poll: remember the last fresh real cash of the trading day; once that day is over (trading_day(now) is later)
        it becomes the day's anchor (floor = next_floor(previous anchor floor or the book's floor, eod)). Returns the new
        anchor when one was just made, else None. book_floor = callable() -> the bot's floor now (only for the first anchor)."""
        now = int(now if now is not None else self.clock())
        if not name or not eval_start:
            return None
        name = str(name).strip()
        r = self.row(name, rules, now)
        rec = self._rec(name, eval_start)
        made = None
        today = _trading_day(now)
        last = rec.get("last")
        if isinstance(last, dict) and last.get("day") and last["day"] < today and last.get("done") is not True:
            prev = (rec.get("anchor") or {}).get("floor")
            if prev is None and callable(book_floor):
                try:
                    prev = book_floor()
                except Exception:
                    prev = None
            if last["day"] >= str(eval_start):
                fl = next_floor(prev, float(last["cash"]), rules)
                made = rec["anchor"] = {"as_of": last["day"], "balance": round(float(last["cash"]), 2), "floor": fl,
                                        "src": "ninjatrader", "set_t": now}
            last["done"] = True
        if r is not None:
            d = _trading_day(int(r["t"]))
            if d >= str(eval_start) and (not isinstance(rec.get("last"), dict) or rec["last"].get("day") != d
                                         or int(r["t"]) >= int(rec["last"].get("t") or 0)):
                rec["last"] = {"day": d, "cash": round(float(r["cash"]), 2), "t": int(r["t"]), "done": False}
        if made is not None or r is not None:
            self._save()
        return made

    def drift(self, name: str | None, ledger_balance, rules: dict | None = None, now=None) -> dict | None:
        """{"real", "ledger", "diff"} once a day when real cash and the closed-ledger balance differ by > $50 for 5+
        minutes; None otherwise."""
        now = int(now if now is not None else self.clock())
        r = self.row(name, rules, now)
        if r is None or ledger_balance is None:
            return None
        diff = round(float(r["cash"]) - float(ledger_balance), 2)
        key = str(name).strip()
        day = _trading_day(now)
        s = self.drift_seen.setdefault(key, {})
        if abs(diff) <= DRIFT_USD:
            s.pop("since", None)
            return None
        s.setdefault("since", now)
        if now - s["since"] < DRIFT_HOLD_S or s.get("pushed") == day:
            return None
        s["pushed"] = day
        return {"real": round(float(r["cash"]), 2), "ledger": round(float(ledger_balance), 2), "diff": diff, "day": day}

    def cap_state(self, st: dict | None, name: str | None, rules: dict | None = None, now=None) -> dict | None:
        """An eval sizing state with room = min(ledger room, real room); st["broker"] = what the bot read. No fresh sane
        row: st unchanged (the same object)."""
        if not st or st.get("room") is None:
            return st
        r = self.row(name, rules, now)
        if r is None:
            return st
        R = rules_for(rules)
        bal = R["start"] + float(st.get("profit") or 0) + float(st.get("cum") or 0)
        floor = round(bal - float(st["room"]), 2)
        room, rr = cap_room(float(st["room"]), r, floor)
        out = dict(st)
        out["room"] = room
        out["broker"] = {"name": str(name), "cash": round(float(r["cash"]), 2), "equity": round(real_equity(r), 2),
                         "floor": floor, "real_room": rr, "ledger_room": round(float(st["room"]), 2), "room": room,
                         "age_s": int(r.get("age_s") or 0)}
        return out


_REG: dict = {}


def enabled(bot) -> bool:
    """The switch: cfg / lit_sizing "broker_balance" true / false; unset = the real bot only (its default state file)."""
    cfg = getattr(bot, "cfg", None) or {}
    v = cfg.get("broker_balance")
    if v is None:
        v = (getattr(bot, "_lit_sizing", None) or {}).get("broker_balance")
    if v is not None:
        return bool(v)
    try:
        from .live import STATE_PATH
        return os.path.abspath(getattr(bot, "state_path", "") or "") == os.path.abspath(STATE_PATH)
    except Exception:
        return False


def for_bot(bot) -> Broker | None:
    """The bot's Broker (one per bot), or None when the switch is off. Never raises."""
    try:
        if bot is None or not enabled(bot):
            return None
        b = getattr(bot, "_broker_bal", None)
        if isinstance(b, Broker):
            return b
        from .ninjatrader import default_folder
        cfg = getattr(bot, "cfg", None) or {}
        path = cfg.get("broker_balance_file") or os.path.join(cfg.get("nt_folder") or default_folder(), FEED_DIR, FILE)
        sp = getattr(bot, "state_path", None) or os.path.join(ROOT, "data", "live_state.json")
        b = Broker(path, os.path.join(os.path.dirname(os.path.abspath(sp)), STATE_FILE), clock=getattr(bot, "clock", time.time))
        try:
            bot._broker_bal = b
        except Exception:
            pass
        return b
    except Exception:
        return None


def drift_payload(label: str, name: str, d: dict, now) -> dict:
    from . import push
    body = (f"NinjaTrader {name}: ${d['real']:,.2f}; bot ledger ${d['ledger']:,.2f} (difference ${d['diff']:+,.2f}). The bot "
            "sizes from the lower room now and takes the real balance as the eval anchor at the day close.")
    return push.text_payload("PC", "risk", f"{label} balance differs", body, key=f"baldiff:{name}:{d['day']}", t=int(now),
                             url="#/accounts")


def line(info: dict | None) -> str | None:
    """The Bot Brain / heartbeat sizing line."""
    if not info:
        return None
    return (f"balance from NinjaTrader ${info['equity']:,.2f}, floor ${info['floor']:,.2f}, room ${info['room']:,.2f}"
            + (f" (ledger room ${info['ledger_room']:,.2f})" if abs(info["ledger_room"] - info["room"]) > 0.005 else ""))


# ------------------------------------------------------------------------------------------------ CLI
def selftest() -> bool:
    import tempfile
    ok = True

    def check(name, cond):
        nonlocal ok
        print(("PASS " if cond else "FAIL ") + name)
        ok = ok and bool(cond)
    now = 1_790_000_000
    rows = parse("name,time,cash,realized,unrealized,netliq\nMFFU1,%d,49800.5,-12,30,\nbad line\n" % now)
    check("parse", rows["MFFU1"]["cash"] == 49800.5 and rows["MFFU1"]["netliq"] is None)
    check("floor trails / locks", next_floor(48000, 50500) == 48500 and next_floor(48500, 52500) == 50100
          and next_floor(50100, 53000) == 50100 and next_floor(48000, 47900) == 47900)
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, FILE)
        with open(p, "w") as fh:
            fh.write("name,time,cash,realized,unrealized,netliq\nMFFU1,%d,49800,0,-100,\n" % now)
        b = Broker(p, os.path.join(td, STATE_FILE), clock=lambda: now + 10)
        st = b.cap_state({"profit": 0.0, "cum": 0.0, "room": 2000.0}, "MFFU1")
        check("room = min(ledger, real)", st["room"] == 1700.0)
    print("broker_balance selftest:", "PASS" if ok else "FAIL")
    return ok


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--selftest" in argv:
        return 0 if selftest() else 1
    s = read()
    print(f"{s['path']}: {'fresh' if s['ok'] else s['why']}")
    for n, r in s["rows"].items():
        good, why = sane(r)
        nl = "-" if r["netliq"] is None else f"${r['netliq']:,.2f}"
        print(f"  {n}: cash ${r['cash'] or 0:,.2f}, unrealized ${r['unrealized'] or 0:,.2f}, netliq {nl}, {r['age_s']} s old"
              f"{'' if good else ' (' + why + ')'}{' SIM: ignored' if SIM.match(n) else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
