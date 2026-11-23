"""Hand-trade hedge guard (idea #1 of research/handoff/2026-11-20/TOP25_IDEAS.txt, branch day-redteam2, 2026-11-20).

The gap: the cross-account hedging guards (engine/multi_account.AccountRouter.opposite_open / others_opposite, account_b,
account_c, fleet) read only the BOT's own ledgers. A trade the owner places by hand in NinjaTrader is invisible to them, so a
bot entry the other way on another MFFU account would be long + short on NQ across his accounts (MFFU: a hedging breach on
every account involved).

The rule (opposite_hand): before a bot entry of direction d, read NinjaTrader's own position files (outgoing\\
<instrument>_<account>_Position.txt, the same files engine/guards._broker_net reads) for every NON-Sim account. A NQ / MNQ
position on the other side that no bot lane explains (no open bracket of any bot adapter on that account, no fleet follower
position there) refuses the entry, ALSO on the entering account itself (fix-trade 2026-11-21: a hand NQ mini, or another
contract month, against the bot's MNQ on one account is a hedge too; the adapter only checks the instruments it sends).
Same side = allowed (copying is fine). A position the bot holds stays with the existing ledger checks (LIT closes ATLAS
first, the Rapid's shared lanes, ...). Blind spot closed (fix-trade): le_feed\\accounts.csv shows open P&L on a real
account with no position file that explains it (NinjaTrader restarted: the file comes back only when the position changes)
-> the side is unknown, so no entry either way. Only accounts NinjaTrader is connected to can be seen at all.

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
_C: dict = {"t": 0.0, "folder": None, "rows": None, "all": None}
PNL_MIN = 0.5                 # accounts.csv |unrealized| at or above this = an open position on that account
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


def _files(folder: str, now: float) -> list:
    """Every position file of a non-Sim account, any instrument: [{"account", "instrument", "side", "qty", "mtime", "nq"}]."""
    out = []
    try:
        from .ninjatrader import inst_key, is_sim, parse_position
        og = os.path.join(folder, "outgoing")
        for n in sorted(os.listdir(og)):
            if not n.lower().endswith("_position.txt"):
                continue
            inst, _, acct = n[:-len("_position.txt")].partition("_")   # instruments have no "_"; an account Name may
            if not inst or not acct or is_sim(acct):
                continue
            fp = os.path.join(og, n)
            try:
                with open(fp, encoding="utf-8-sig", errors="replace") as fh:
                    p = parse_position(fh.read())
                mt = os.path.getmtime(fp)
            except OSError:
                continue
            if not p:
                continue
            k = inst_key(inst)
            out.append({"account": acct, "instrument": inst, "side": p["side"], "qty": int(p.get("qty") or 0), "mtime": mt,
                        "nq": bool(k and k[0] in ROOTS)})
    except OSError:
        out = []
    return out


def _all(folder: str, now: float | None = None) -> list:
    now = time.time() if now is None else float(now)
    if _C["rows"] is not None and _C.get("all") is not None and _C["folder"] == folder and abs(now - _C["t"]) < CACHE_S:
        return _C["all"]
    allf = _files(folder, now)
    rows = [{k: r[k] for k in ("account", "instrument", "side", "qty")} for r in allf
            if r["nq"] and r["side"] in ("LONG", "SHORT") and r["qty"]]
    _C.update(t=now, folder=folder, rows=rows, all=allf)
    return allf


def scan(folder: str, now: float | None = None) -> list:
    """[{"account", "instrument", "side", "qty"}] of every non-FLAT NQ / MNQ position file of a non-Sim account. Cached CACHE_S."""
    _all(folder, now)
    return _C["rows"] or []


def pnl_blind(folder: str, now: float | None = None, held: set | None = None) -> str | None:
    """Why no entry may go because NinjaTrader's files cannot say the side (None = they can): le_feed\\accounts.csv (LE_BarFeed,
    every minute) shows open P&L on a real account that no bot lane holds, while no position file of that account explains
    it (none non-FLAT, none written after that row: a FLAT file newer than the row = the row predates the close). That is
    NinjaTrader restarted with a position open (outgoing\\ wiped, the file is back only when the position changes)."""
    try:
        from .broker_balance import SIM, read as _bb
        from .ninjatrader import is_sim
        now = time.time() if now is None else float(now)
        held = held or set()
        files = {}
        for r in _all(folder, now):
            files.setdefault(r["account"].strip().lower(), []).append(r)
        for n, row in ((_bb(folder, now=now) or {}).get("rows") or {}).items():
            nm = str(n).strip()
            a = nm.lower()
            if not row.get("fresh") or SIM.match(nm) or is_sim(nm) or a in held:
                continue
            try:
                u = abs(float(row.get("unrealized") or 0))
            except (TypeError, ValueError):
                continue
            if u < PNL_MIN:
                continue
            fs = files.get(a) or []
            if any(f["side"] in ("LONG", "SHORT") and f["qty"] for f in fs):
                continue                          # a file shows its position (NQ ones are the scan's; ES / CL are no hedge)
            if any(f["mtime"] >= float(row.get("t") or 0) for f in fs):
                continue                          # it went FLAT after this row was written: the row's P&L is stale
            return (f"hedging guard: NinjaTrader shows open P&L ${u:,.0f} on account ..{nm[-4:]} but no position file for it "
                    "(NinjaTrader restarted?): the side is unknown, so no entry until that account is flat or its file is back")
        return None
    except Exception:
        return None


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
        return False                       # unreadable = not the bot's: a position there is a hand trade (entries only)


def bot_held(bot, router=None) -> set:
    """Lower-case NinjaTrader account names on which a bot lane explains a position: an open bracket of any of the bot's
    adapters (LIT, ATLAS account B, account C, the Rapid's ATLAS lane, every extra account) or a fleet follower's position."""
    out = set()
    ads = [getattr(bot, "adapter", None)] + [getattr(getattr(bot, a, None), "adapter", None)
                                             for a in ("acct_b", "acct_r", "acct_r2", "acct_c")]
    ads += [getattr(a, "adapter", None) for a in (getattr(router, "accounts", None) or [])]
    ads += [getattr(x, "adapter", None) for x in (getattr(bot, "acct_x", None) or {}).values()]   # engine/combo25 (off = {})
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
    """Why a bot entry of direction d must not go (a position no bot lane explains holds the other side on an MFFU account,
    the entering one included; or an account shows open P&L its files do not explain), else None. own: the caller's account
    (kept for the callers; it is checked like every other one: a hand NQ mini against the bot's MNQ there is a hedge too).
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
        held = bot_held(bot, router)
        for r in scan(folder, now):
            a = r["account"].strip().lower()
            if a in held:                       # a bot lane explains it: the ledger checks own that case
                continue
            if (1 if r["side"] == "LONG" else -1) == -int(d):
                return (f"hedging guard: NinjaTrader shows {r['side']} {r['qty']} {r['instrument']} on account ..{r['account'][-4:]} "
                        f"that no bot trade explains (a hand trade?): no {_side(d)} entry on any account")
        return pnl_blind(folder, now, held)
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
    from . import fsutil as _fsutil
    _fsutil.replace(tmp, p)
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
              "a position it did not open on its own account. It still never takes the opposite side of it on any account "
              "NinjaTrader is connected to (accounts it is not connected to cannot be seen).")
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
