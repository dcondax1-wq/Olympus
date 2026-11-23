"""A damaged bot state file never means a clean day (night-statesafe 2026-11-23).

Before: an unreadable data/live_state.json (LIT) or live_state_acctb.json (ATLAS, engine/account_b.py) made the bot start a
CLEAN day: the kill flag and today's ledger (so today's realized P&L, the daily-loss stops and the trade count) were gone and
the bot could trade past a daily-loss stop. Now, in this order:

  1. every save keeps the previous good copy: <state>.bak (rotate(): only when the file on disk is one this process wrote or
     read cleanly, so a damaged file never replaces a good .bak)
  2. unreadable (or missing while a .bak exists) -> the .bak, only when it was saved TODAY (ET trading day)
  3. no usable copy (LIT only) -> today's ledger and kill flag rebuilt from engine/fill_audit's minute copy (logs/exec_audit:
     ledger.jsonl + notes.json uptime samples, which carry "kill"), ONLY when it is provably complete: the copy ran after the
     last order NinjaTrader's audit log shows for this account today, and no entry of today is left without its exit
  4. still nothing -> no NEW entries for the rest of this ET trading day (exits and brackets untouched) + ONE phone message.

On a healthy day nothing here changes a decision: the only extra work is the .bak rotation at each save.
Never raises.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import threading
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXEC_STORE = os.path.join(ROOT, "logs", "exec_audit")
PUSH = None            # tests: fn(problem dict) instead of the phone


def bak_of(path: str) -> str:
    return str(path) + ".bak"


def rotate(path: str, good: bool) -> None:
    """Before a save: the current file -> <path>.bak, only when it is known good (written / read cleanly by this process)."""
    if not good:
        return
    try:
        if os.path.exists(path):
            from .fsutil import replace as _replace
            _replace(path, bak_of(path))
    except Exception:
        pass


def _read(path):
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    if not isinstance(d, dict):
        raise ValueError("not a JSON object")
    return d


def load(path: str, day_of, today: str) -> dict:
    """-> {"blob": dict | None, "src": "main" | "bak" | None, "damaged": bool, "why": str, "old_bak": dict | None}.
    day_of(blob) -> the blob's trading day. damaged = the main file exists but is unreadable, or is gone while a .bak exists."""
    out = {"blob": None, "src": None, "damaged": False, "why": "", "old_bak": None}
    main_there, bak_there = os.path.exists(path), os.path.exists(bak_of(path))
    if main_there:
        try:
            out.update(blob=_read(path), src="main")
            return out
        except Exception as e:  # noqa: BLE001
            out.update(damaged=True, why=f"{os.path.basename(path)} unreadable ({e.__class__.__name__})")
    elif bak_there:
        out.update(damaged=True, why=f"{os.path.basename(path)} missing (a save was cut off)")
    else:
        return out                                     # a first start: nothing to restore, nothing damaged
    if bak_there:
        try:
            b = _read(bak_of(path))
            if day_of(b) == today:
                out.update(blob=b, src="bak")
            else:
                out["old_bak"] = b
        except Exception:
            pass
    return out


# ------------------------------------------------------------------------------------------------ 3. LIT's rebuild
def _jl(path) -> list:
    out = []
    try:
        with open(path, encoding="utf-8") as fh:
            for ln in fh:
                try:
                    r = json.loads(ln)
                    if isinstance(r, dict):
                        out.append(r)
                except Exception:
                    continue
    except OSError:
        pass
    return out


def _last_audit_t(audit_path, account, day, trading_day) -> int | None:
    """Epoch of the last line the NinjaTrader OIF audit log holds for `account` on trading day `day` (None = none / no log)."""
    last = None
    try:
        with open(audit_path, encoding="utf-8", errors="replace") as fh:
            rows = fh.read().splitlines()[-5000:]
    except OSError:
        return None
    for row in rows:
        parts = row.split("  ")
        if len(parts) < 4 or parts[1].strip() != str(account):
            continue
        try:
            t = int(dt.datetime.strptime(parts[0].replace(" ET", "").strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=ET).timestamp())
        except ValueError:
            continue
        if trading_day(t) == day:
            last = t if last is None else max(last, t)
    return last


def rebuild_lit(day: str, trading_day, audit_path=None, account=None, store=None) -> dict | None:
    """Today's ledger + kill flag from engine/fill_audit's copy, or None when it cannot be PROVED complete."""
    try:
        st = store or EXEC_STORE
        try:
            with open(os.path.join(st, "notes.json"), encoding="utf-8") as fh:
                ups = [u for u in (json.load(fh).get("uptime") or []) if isinstance(u, dict) and u.get("t") is not None]
        except Exception:
            return None
        ups = [u for u in ups if trading_day(int(u["t"])) == day]
        if not ups:
            return None                                # the copy never ran today: nothing proves anything
        last_copy = max(int(u["t"]) for u in ups)
        if not audit_path or not account or not os.path.exists(audit_path):
            return None                                # paper / no order log: completeness cannot be proved
        la = _last_audit_t(audit_path, account, day, trading_day)
        if la is not None and la > last_copy:
            return None                                # an order went out after the last copy: the copy may miss its row
        rows, seen = [], set()
        for r in _jl(os.path.join(st, "ledger.jsonl")):
            try:
                if trading_day(int(r["t"])) != day:
                    continue
            except (KeyError, TypeError, ValueError):
                continue
            k = json.dumps({x: r.get(x) for x in ("t", "side", "entry_t", "reason", "qty")}, sort_keys=True, default=str)
            if k in seen:
                continue
            seen.add(k)
            rows.append({x: v for x, v in r.items() if x != "adapter"})
        rows.sort(key=lambda r: int(r["t"]))
        entries = {r.get("entry_t") for r in rows if r.get("side") in ("buy", "sell") and (r.get("result") or {}).get("ok") is not False}
        exits = {r.get("entry_t") for r in rows if r.get("side") == "exit"}
        if any(e not in exits for e in entries if e is not None):
            return None                                # a position may be open: its state is not in the copy
        kill = bool(sorted(ups, key=lambda u: int(u["t"]))[-1].get("kill")) or \
            any(r.get("side") == "exit" and str(r.get("reason") or "") == "KILL SWITCH" for r in rows)
        return {"ledger": rows, "kill": kill, "copy_t": last_copy}
    except Exception:
        return None


# ------------------------------------------------------------------------------------------------ 4. the one message
def alert(name: str, day: str, real: bool) -> dict:
    """ONE phone message a day per state file (engine/notify.instant_problem, its keys are kept: once across restarts)."""
    p = {"key": f"state_damaged:{name}:{day}", "code": "bot_down",
         "title": "Entries paused today: a state file was damaged",
         "body": (f"The bot's state file ({name}) was damaged and today's numbers could not be rebuilt, so NO NEW entries go in "
                  "for the rest of today. Exits and the open brackets are untouched. Nothing needs doing: trading starts again on "
                  "its own on the next trading day.")}
    if not real and PUSH is None:
        return p

    def go():
        try:
            if PUSH is not None:
                PUSH(p)
            else:
                from . import notify
                notify.instant_problem(p)
        except Exception:
            pass
    if PUSH is not None:
        go()
    else:
        try:
            threading.Thread(target=go, name="state-damaged-push", daemon=True).start()
        except Exception:
            pass
    return p
