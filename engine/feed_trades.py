"""FEED TRADES (2026-11-18, owner: the Trading page's LIVE trades stopped at Nov 7). The small per-account trade block the PC adds to
its ntfy "le-live-ext" post (tools/pc_report.py, ext key "at"; tools/web_public/pc_feed.js lays it top level), so the Trading page
(tools/web_public/trading/) shows today's and the last few LIVE trades of EVERY real account, not only the board's last 3.
Read only: it never trades, arms, routes or sizes.

compact(L) -> {"t", "a": [{"id", "l4", "tr": [[entry_t, exit_t, dir, qty, entry, stop, target, exit_kind, usd, r], ...]}]} or None
  id   the PC account id (mffu50k_eval = Zlarior 50K, b25k_2 = Zlarior 25K #2, atlas = ATLAS's account B, a Rapid id ...)
  l4   the broker account's last 4 digits only (never the full name; the same rule as engine/mffu_view.last4)
  tr   the newest N_TRADES trades of the account, oldest first; exit_t / exit_kind None = still open; dir 1 long / -1 short
From the PC's full live.json L (engine/live_publish.build): each real account's own closed trades (accounts[].trades: the bot's
ledger, engine/accounts.trade_row) and ATLAS's routed trades (board.trades acct "atlas", src "live"). Paper, cloud and BLITZ rows
are never in it. ~70 bytes a trade. Tests: tests/test_trading_page.py (feed part).
"""
from __future__ import annotations

from .mffu_view import last4

N_TRADES = 4


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _l(x) -> list:
    return x if isinstance(x, list) else []


def _f(v, nd=2):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return round(x, nd) if x == x and abs(x) != float("inf") else None


def _i(v):
    x = _f(v, 6)
    return None if x is None else int(round(x))


def _dir(side) -> int:
    return -1 if str(side or "").upper().startswith(("S", "SELL")) else 1


def _row(t: dict, open_=False) -> list | None:
    et = _i(t.get("entry_t"))
    if not et:
        return None
    k = t.get("exit") if isinstance(t.get("exit"), str) else t.get("exit_kind")
    is_open = open_ or t.get("open") is True or str(k or "").upper() == "OPEN"
    usd = _f(t.get("pnl") if t.get("pnl") is not None else t.get("usd"))
    r = _f(t.get("r") if t.get("r") is not None else t.get("R"), 2)
    return [et, None if is_open else _i(t.get("exit_t")), _dir(t.get("side")), _i(t.get("qty")), _f(t.get("entry")), _f(t.get("stop")),
            _f(t.get("target")), None if is_open else (str(k or "").upper()[:12] or None), usd, r]


def _real(a: dict) -> bool:
    return bool(a.get("id")) and not a.get("error") and a.get("kind") in ("eval", "funded") and a.get("source") not in ("cloud", "pc_blitz") \
        and a.get("id") != "acct_c" and "blitz" not in str(a.get("id")).lower()


LANE_ACCT = {"r": "rapid", "r2": "rapid2"}          # ATLAS lane state file -> the account id it trades on ("x:<id>" -> <id>)


def lane_trades(data_dir: str | None = None) -> dict:
    """day-moneyaudit (2026-11-27): {account id: [trade dicts]} of the ATLAS lanes that trade ON another account (the Rapid EOD's
    ATLAS lane, the combo lane on an extra Builder): their trades live in their own state file (engine/account_b ledger + closes),
    not in the account's ledger, so today's Rapid +$304 (ATLAS S/R) never reached the "at" block. Account B ("b") is its own
    account (board.trades). Refused / never-placed entries are left out. Never raises."""
    import json as _json
    out = {}
    try:
        from . import account_b as AB
        files = AB.lane_files(data_dir)
    except Exception:
        return out
    for lane, p in files:
        if lane == "b":
            continue
        aid = LANE_ACCT.get(lane) or (lane[2:] if lane.startswith("x:") else None)
        if not aid:
            continue
        try:
            b = _json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        led = [r for r in _l(b.get("ledger")) if isinstance(r, dict)]
        closes = {_i(c[3]): c for c in _l(b.get("closes")) if isinstance(c, list) and len(c) > 3}
        prov = _d(b.get("prov"))
        for r in led:
            if r.get("side") not in ("buy", "sell") or r.get("entry_t") is None or _d(r.get("result")).get("ok") is False:
                continue
            et = _i(r["entry_t"])
            pv = _d(prov.get(str(et)))
            if pv.get("not_placed"):
                continue
            ex = next((x for x in reversed(led) if x.get("side") == "exit" and _i(x.get("entry_t")) == et), {})
            c = closes.get(et)
            t = {"entry_t": et, "side": "LONG" if r["side"] == "buy" else "SHORT", "qty": r.get("qty"),
                 "entry": pv.get("fill") or r.get("entry"), "stop": r.get("stop"), "target": r.get("target")}
            if c is not None:
                t.update(exit_t=c[1], pnl=c[2], exit=str(ex.get("reason") or (pv.get("flat") or {}).get("reason") or "CLOSED"))
            elif _i(b.get("open_t")) == et:
                t["open"] = True
            else:
                continue                                   # neither closed nor open: a record the lane dropped
            out.setdefault(aid, []).append(t)
    return out


def compact(L: dict | None, n: int = N_TRADES, data_dir: str | None = None) -> dict | None:
    """The "at" block of the ntfy ext post. Never raises; None when no real account has a trade. data_dir: the lane state files
    (engine/account_b.lane_files; default the bot's data/)."""
    try:
        L = _d(L)
        rows = []
        lanes = lane_trades(data_dir)
        for a in _l(L.get("accounts")):
            a = _d(a)
            if not _real(a):
                continue
            tr = [x for x in (_row(_d(t)) for t in _l(a.get("trades"))) if x]
            for t in lanes.pop(str(a["id"]), []):          # the ATLAS lane trading on this account (day-moneyaudit)
                x = _row(t, open_=bool(t.get("open")))
                if x and not any(y[0] == x[0] for y in tr):
                    tr.append(x)
            pos = _d(a.get("position"))
            if pos.get("entry_t") and not any(x[0] == _i(pos.get("entry_t")) for x in tr):
                x = _row(pos, open_=True)
                if x:
                    tr.append(x)
            if not tr:
                continue
            row = {"id": str(a["id"])[:24], "tr": sorted(tr, key=lambda x: x[0])[-n:]}
            l4 = last4(a.get("broker_account"))
            if l4:
                row["l4"] = l4
            rows.append(row)
        for aid, ts in lanes.items():                      # a lane whose account has no row of its own yet
            tr = [x for x in (_row(t, open_=bool(t.get("open"))) for t in ts) if x]
            if tr:
                rows.append({"id": str(aid)[:24], "tr": sorted(tr, key=lambda x: x[0])[-n:]})
        bd = _d(L.get("board"))
        if not any(r["id"] == "atlas" for r in rows):
            tr = [x for x in (_row(_d(t)) for t in _l(bd.get("trades"))
                              if _d(t).get("acct") == "atlas" and _d(t).get("src") == "live") if x]
            if tr:
                row = {"id": "atlas", "tr": sorted(tr, key=lambda x: x[0])[-n:]}
                S = _d(_d(L.get("pc")).get("second"))
                ab = _d(_d(S.get("route")).get("account_b")) or _d(S.get("account_b"))
                l4 = last4(_d(bd.get("atlas")).get("broker") or ab.get("account"))
                if l4:
                    row["l4"] = l4
                rows.append(row)
        if not rows:
            return None
        return {"t": _i(bd.get("data_t")) or _i(L.get("t")), "a": rows[:6]}
    except Exception:  # noqa: BLE001
        return None


def cut(at: dict | None, n: int) -> None:
    """Keep only the newest n trades of every account, in place (0 = drop them all)."""
    for r in _l(_d(at).get("a")):
        if isinstance(r, dict):
            r["tr"] = _l(r.get("tr"))[-n:] if n > 0 else []
