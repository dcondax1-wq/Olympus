"""LIVE vs BACKTEST, daily (night-livevsbt 2026-11-23): does real trading drift from what the backtest says on the same futures bars?

READ ONLY: never trades, sizes, routes or changes a setting. Per live bot (LIT = Zlarior, ATLAS), from tools/reconcile_live (the
PC's day folders: the ledger rows, NinjaTrader's fills, engine/fill_audit's nightly backtest twin):
  each real trade vs its model: entry slippage (ticks past the model, which already counts 1), exit slippage, $ real - $ model
  a MISSED trade (the backtest took it, the account did not: refused, held back, a gap) = -its model $
  an EXTRA trade (the account traded, the backtest on the same bars did not) = +its real $
over the rolling last N_TRADES (10) events. It speaks when the window holds a missed or an extra trade, or the average entry
slippage is above SLIP_TICKS (2 ticks past the model):
  phone (ONE line a day per bot, key lvb:<bot>:<day>, after 16:20 ET on a CME day, through tools/pc_guard's push list):
      "LIT live is $X behind the backtest over the last 10 trades: 1 missed (refused by the broker), entry slippage +3.1 ticks avg"
  brief: one line "Live vs backtest: LIT -$37 over 4 trades (ok) · ATLAS -$120 over 10 trades (slippage +3.1 ticks)"
Result cache: logs/live_vs_bt.json (the brief reads it; rebuilt when older than CACHE_S).

    python -X utf8 -m engine.live_vs_bt          print the check (no phone)
Tests: python -X utf8 -m tests.test_live_vs_bt (fixture day folders)
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ET = ZoneInfo("America/New_York")
OUT = os.path.join(ROOT, "logs", "live_vs_bt.json")
N_TRADES = 10
SLIP_TICKS = 2.0
CACHE_S = 6 * 3600
PUSH_FROM = 16 * 60 + 20
NAME = {"Zlarior": "LIT", "ATLAS": "ATLAS"}


def _f(v):
    try:
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def _usd(x) -> str:
    return ("-" if x < 0 else "") + "${:,.0f}".format(abs(x))


def gather(RL=None):
    """(trades, missed, extra entry times) from the day folders. Never raises."""
    try:
        if RL is None:
            sys.path.insert(0, ROOT)
            from tools import reconcile_live as RL
        T, missed = RL.from_folders()
        extra = set()
        for f in RL.day_folders():
            tw = RL._js(os.path.join(f, "twin.json.gz")) or {}
            for r in ((tw.get("nightly") or {}).get("rows") or []):
                if r.get("status") == "extra" and r.get("entry_t") is not None:
                    extra.add(int(r["entry_t"]))
        return T, missed, extra
    except Exception:
        return [], [], set()


def evaluate(T, missed, extra=(), n: int = N_TRADES) -> dict:
    """{bot name: {"n", "gap", "missed", "extra", "slip", "entry_usd", "exit_usd", "flag", "why", "line", "short"}}."""
    extra = set(int(x) for x in extra or ())
    out = {}
    for bot, name in NAME.items():
        ev = []
        for t in T:
            if t.get("bot") != bot:
                continue
            et = int(t.get("entry_t") or 0)
            if et in extra:
                ev.append({"t": et, "kind": "extra", "gap": _f(t.get("real_usd")) or 0.0, "ticks": _f(t.get("entry_ticks")),
                           "entry_usd": _f(t.get("entry_usd")) or 0.0, "exit_usd": _f(t.get("exit_usd")) or 0.0})
            elif _f(t.get("diff_usd")) is not None:
                ev.append({"t": et, "kind": "trade", "gap": float(t["diff_usd"]), "ticks": _f(t.get("entry_ticks")),
                           "entry_usd": _f(t.get("entry_usd")) or 0.0, "exit_usd": _f(t.get("exit_usd")) or 0.0})
        for m in missed or []:
            if m.get("bot") == bot:
                ev.append({"t": int(m.get("entry_t") or 0), "kind": "missed", "gap": -(_f(m.get("model_usd")) or 0.0), "ticks": None,
                           "cause": str(m.get("cause") or "missed"), "entry_usd": 0.0, "exit_usd": 0.0})
        ev.sort(key=lambda e: e["t"])
        w = ev[-n:]
        gap = round(sum(e["gap"] for e in w), 2)
        ticks = [e["ticks"] for e in w if e["ticks"] is not None]
        slip = round(sum(ticks) / len(ticks), 1) if ticks else None
        nm = [e for e in w if e["kind"] == "missed"]
        nx = [e for e in w if e["kind"] == "extra"]
        ent, exi = round(sum(e["entry_usd"] for e in w), 2), round(sum(e["exit_usd"] for e in w), 2)
        why = []
        if nm:
            causes = sorted({e["cause"] for e in nm})
            why.append(f"{len(nm)} missed ({', '.join(causes)[:60]})")
        if nx:
            why.append(f"{len(nx)} extra (the backtest had no trade there)")
        if slip is not None and slip > SLIP_TICKS:
            why.append(f"entry slippage {slip:+.1f} ticks avg ({_usd(ent)})")
        flag = bool(why)
        if not why:
            why.append(f"fills close to the model (entry {slip:+.1f} ticks avg)" if slip is not None else "fills close to the model")
        if exi and abs(exi) >= 10:
            why.append(f"exits {_usd(exi)}")
        k = len(w)
        word = "behind" if gap < 0 else "ahead of"
        line = (f"{name} live is {_usd(abs(gap))} {word} the backtest over the last {k} trade{'s' if k != 1 else ''}: "
                + ", ".join(why)) if k else f"{name}: no live trade to compare yet"
        short = (f"{name} {'+' if gap >= 0 else '-'}{_usd(abs(gap))} over {k} trade{'s' if k != 1 else ''} "
                 + (f"({why[0]})" if flag else "(ok)")) if k else f"{name} no live trades yet"
        out[name] = {"n": k, "gap": gap, "missed": len(nm), "extra": len(nx), "slip": slip, "entry_usd": ent, "exit_usd": exi,
                     "flag": flag, "why": why, "line": line, "short": short}
    return out


def run(now=None, RL=None) -> dict:
    now = int(time.time() if now is None else now)
    T, missed, extra = gather(RL)
    return {"t": now, "bots": evaluate(T, missed, extra)}


def save(res, path=None) -> None:
    try:
        p = path or OUT
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p + ".tmp", "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=1)
        try:
            from .fsutil import replace as _rep
        except Exception:  # noqa: BLE001
            _rep = os.replace
        _rep(p + ".tmp", p)
    except Exception:
        pass


def cached(now=None, path=None, max_age=CACHE_S, RL=None) -> dict | None:
    """The last result when fresh, else a new run (saved). Never raises."""
    now = int(time.time() if now is None else now)
    try:
        with open(path or OUT, encoding="utf-8") as fh:
            d = json.load(fh)
        if isinstance(d, dict) and now - int(d.get("t") or 0) <= max_age:
            return d
    except Exception:
        pass
    try:
        d = run(now, RL)
        save(d, path)
        return d
    except Exception:
        return None


def last_line(now=None, path=None, max_age=30 * 3600) -> str:
    """The brief's line from the last saved check (the 16:20 ET run of the day before), '' when none / too old. Reads only."""
    try:
        now = int(time.time() if now is None else now)
        with open(path or OUT, encoding="utf-8") as fh:
            d = json.load(fh)
        return brief_line(d) if now - int(d.get("t") or 0) <= max_age else ""
    except Exception:
        return ""


def brief_line(res) -> str:
    """'Live vs backtest: LIT -$37 over 4 trades (ok) · ATLAS ...' or '' when no bot has a live trade yet."""
    b = (res or {}).get("bots") or {}
    parts = [v["short"] for v in b.values() if v.get("n")]
    return ("Live vs backtest: " + " · ".join(parts)) if parts else ""


def pushes(now, sent, res=None, trading_day=None) -> list:
    """tools/pc_guard's hook: [one push per flagged bot] once a day after 16:20 ET on a CME trading day, else []."""
    try:
        e = dt.datetime.fromtimestamp(int(now), ET)
        if e.hour * 60 + e.minute < PUSH_FROM or e.weekday() >= 5:
            return []
        if trading_day is None:
            from . import cme_calendar as C
            if C.full_closure(e.date()):
                return []
        res = res if res is not None else cached(now)
        out = []
        for name, v in ((res or {}).get("bots") or {}).items():
            k = f"lvb:{name}:{e.date().isoformat()}"
            if v.get("flag") and k not in (sent or {}):
                out.append({"key": k, "kind": "problems", "title": v["line"][:110], "body": v["line"][:600], "priority": "default",
                            "tags": "chart_with_downwards_trend"})
        return out
    except Exception:
        return []


def main(argv=None) -> int:
    res = run()
    save(res)
    for v in res["bots"].values():
        print(("[FLAG] " if v["flag"] else "[ok]   ") + v["line"])
    bl = brief_line(res)
    if bl:
        print(bl)
    return 0


if __name__ == "__main__":
    sys.exit(main())
