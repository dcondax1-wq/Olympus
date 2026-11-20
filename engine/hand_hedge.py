"""Hand-trade hedge guard (idea #1 of research/handoff/2026-11-20/TOP25_IDEAS.txt, branch day-redteam2, 2026-11-20).

The gap: the cross-account hedging guards (engine/multi_account.AccountRouter.opposite_open / others_opposite, account_b,
account_c, fleet) read only the BOT's own ledgers. A trade the owner places by hand in NinjaTrader is invisible to them, so a
bot entry the other way on another MFFU account would be long + short on NQ across his accounts (MFFU: a hedging breach on
every account involved).

The rule (opposite_hand): before a bot entry of direction d, read NinjaTrader's own position files (outgoing\\
<instrument>_<account>_Position.txt, the same files engine/guards._broker_net reads) for every NON-Sim account. A NQ / MNQ
position on the other side, on an account that is not the caller's own and that no bot lane explains (no open bracket of any
bot adapter on that account, no fleet follower position there), refuses the entry. Same side = allowed (copying is fine).
A position the bot holds stays with the existing ledger checks (LIT closes ATLAS first, the Rapid's shared lanes, ...).

Stale files: NinjaTrader writes a position file only when the position changes and wipes outgoing\\ when it restarts, so a file's
age says nothing. What says the files are current is NinjaTrader running: its LE_BarFeed 1-minute file is fresh (<= STALE_S).
When it is not, this check steps aside (the ledger checks still run, as before) and pushes ONE notice a day.

Hand-trade window (optional, the owner's own command; never set by the bot):
    python -X utf8 -m engine.hand_hedge --hand-trade 60     (minutes, at most 240)
    python -X utf8 -m engine.hand_hedge --off
    python -X utf8 -m engine.hand_hedge --status
While it is open, engine/guards.reconcile_tick does not CLOSEPOSITION a position the bot's ledger does not explain on the bot's
own account (it still pushes "Position mismatch" once). The hedge rule above stays on in the window.
Read-only apart from data/hand_trade.json. Never raises. Tests: python -X utf8 -m tests.test_cross_hedge
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WINDOW_PATH = os.path.join(ROOT, "data", "hand_trade.json")
STALE_S = 300                 # NinjaTrader's 1m feed older than this = its outgoing files are not trusted
CACHE_S = 2.0                 # the position scan is reused this long (several lanes ask in the same poll)
WINDOW_MAX_MIN = 240
ROOTS = ("NQ", "MNQ")
_C: dict = {"t": 0.0, "folder": None, "rows": None}
_PUSHED: set = set()


def _side(d: int) -> str:
    return "LONG" if int(d) == 1 else "SHORT"


def folder_of(bot) -> str | None:
    """The NinjaTrader folder the bot routes through, or None (paper / no NinjaTrader adapter: nothing to read)."""
    ad = getattr(bot, "adapter", None)
    f = getattr(ad, "folder", None)
    if f and os.path.isdir(os.path.join(f, "outgoing")):
        return f
    return None


def scan(folder: str, now: float | None = None) -> list:
    """[{"account", "instrument", "side", "qty"}] of every non-FLAT NQ / MNQ position file of a non-Sim account. Cached CACHE_S."""
    now = time.time() if now is None else float(now)
    if _C["rows"] is not None and _C["folder"] == folder and abs(now - _C["t"]) < CACHE_S:
        return _C["rows"]
    rows = []
    try:
        from .ninjatrader import inst_key, is_sim, parse_position
        og = os.path.join(folder, "outgoing")
        for n in sorted(os.listdir(og)):
            if not n.lower().endswith("_position.txt"):
                continue
            inst, _, acct = n[:-len("_position.txt")].partition("_")   # instruments have no "_"; an account Name may
            if not inst or not acct or is_sim(acct):
                continue
            k = inst_key(inst)
            if not k or k[0] not in ROOTS:
                continue
            try:
                with open(os.path.join(og, n), encoding="utf-8-sig", errors="replace") as fh:
                    p = parse_position(fh.read())
            except OSError:
                continue
            if p and p["side"] in ("LONG", "SHORT") and p["qty"]:
                rows.append({"account": acct, "instrument": inst, "side": p["side"], "qty": int(p["qty"])})
    except OSError:
        rows = []
    _C.update(t=now, folder=folder, rows=rows)
    return rows


def nt_fresh(folder: str, now: float | None = None) -> bool:
    try:
        from .ninjatrader import last_1m_age
        age = last_1m_age(folder, now)
        return age is not None and age <= STALE_S
    except Exception:
        return False


def _open_legs(ad) -> bool:
    try:
        from .ninjatrader import OPEN_STATUSES
        return any(lg.get("status") in OPEN_STATUSES for lg in getattr(ad, "legs", None) or []) or \
            any((w.get("watch") or {}).get("leftover") for w in getattr(ad, "watch", None) or [])
    except Exception:
        return True


def bot_held(bot, router=None) -> set:
    """Lower-case NinjaTrader account names on which a bot lane explains a position: an open bracket of any of the bot's
    adapters (LIT, ATLAS account B, account C, the Rapid's ATLAS lane, every extra account) or a fleet follower's position."""
    out = set()
    ads = [getattr(bot, "adapter", None)] + [getattr(getattr(bot, a, None), "adapter", None) for a in ("acct_b", "acct_r", "acct_c")]
    ads += [getattr(a, "adapter", None) for a in (getattr(router, "accounts", None) or [])]
    for ad in ads:
        acct = str(getattr(ad, "account", "") or "").strip().lower()
        if acct and _open_legs(ad):
            out.add(acct)
    for f in getattr(getattr(bot, "fleet", None), "followers", None) or []:
        acct = str(getattr(getattr(f, "adapter", None), "account", "") or "").strip().lower()
        if acct and getattr(f, "pos", None) is not None:
            out.add(acct)
    return out


def opposite_hand(d: int, bot, router=None, own=None, now=None, notify=None) -> str | None:
    """Why a bot entry of direction d must not go (a position no bot lane explains holds the other side on another MFFU
    account), else None. own: the caller's own NinjaTrader account name(s) (never a cross-account hedge with itself).
    notify(title, body, key): the one stale-feed notice a day. Never raises (an error = None: the ledger checks still run)."""
    try:
        folder = folder_of(bot)
        if not folder:
            return None
        now = time.time() if now is None else float(now)
        if not nt_fresh(folder, now):
            day = _dt.datetime.fromtimestamp(now).strftime("%Y-%m-%d")
            if callable(notify) and day not in _PUSHED and scan(folder, now):
                _PUSHED.add(day)
                notify("Hand-trade check off", "NinjaTrader's bar feed is not fresh, so its position files are not trusted: the "
                       "bot cannot see hand trades right now (its own trades are still checked). Do not hold a hand trade while "
                       "the bot can enter.", f"handhedge:stale:{day}")
            return None
        mine = {str(x).strip().lower() for x in ([own] if isinstance(own, str) else (own or [])) if x}
        held = bot_held(bot, router)
        for r in scan(folder, now):
            a = r["account"].strip().lower()
            if a in mine or a in held:
                continue
            if (1 if r["side"] == "LONG" else -1) == -int(d):
                return (f"hedging guard: NinjaTrader shows {r['side']} {r['qty']} {r['instrument']} on account ..{r['account'][-4:]} "
                        f"that no bot trade explains (a hand trade?): no {_side(d)} entry on another account")
        return None
    except Exception:
        return None


# ------------------------------------------------------------------------------------------------ the hand-trade window
def window(path: str | None = None, now: float | None = None) -> dict | None:
    """The open window {"until", "set_at"} or None."""
    try:
        with open(path or WINDOW_PATH, encoding="utf-8") as fh:
            w = json.load(fh)
        now = time.time() if now is None else float(now)
        return w if isinstance(w, dict) and float(w.get("until") or 0) > now else None
    except Exception:
        return None


def set_window(minutes: float, path: str | None = None, now: float | None = None) -> dict:
    now = time.time() if now is None else float(now)
    m = max(1.0, min(float(WINDOW_MAX_MIN), float(minutes)))
    w = {"until": int(now + 60 * m), "set_at": int(now), "minutes": m}
    p = path or WINDOW_PATH
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(w, fh)
    os.replace(tmp, p)
    return w


def clear_window(path: str | None = None) -> None:
    try:
        os.remove(path or WINDOW_PATH)
    except OSError:
        pass


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="engine.hand_hedge")
    ap.add_argument("--hand-trade", type=float, default=None, help="minutes the bot leaves a hand trade on its own account alone")
    ap.add_argument("--off", action="store_true")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args(argv)
    if a.hand_trade is not None:
        w = set_window(a.hand_trade)
        print(f"  [OK] Hand-trade window open until {_dt.datetime.fromtimestamp(w['until']):%H:%M} (PC time): the bot will not close "
              "a position it did not open on its own account. It still never takes the opposite side of it on another account.")
        return 0
    if a.off:
        clear_window()
        print("  [OK] Hand-trade window closed.")
        return 0
    w = window()
    print("  Hand-trade window: " + (f"open until {_dt.datetime.fromtimestamp(w['until']):%H:%M}" if w else "closed"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
