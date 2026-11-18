"""LIVE TRADES from the PC's data branch (2026-11-18): every real MFFU trade per account, for the Trading page and Odeon.

The PC packs each CME day on the backup repo branch `data` (engine/datapipe.py); tools/data_pull.py (git fetch olympus data) copies the
day folders to data/pc_days/<day>/ (gitignored). This reads them: trades.jsonl.gz (every ledger row, live AND paper, tagged src / bot /
acct / mode; account names already cut to "...1234") and bars/<ROOT>_1m.csv.gz (the PC's NinjaTrader futures bars, never Yahoo).
Read only: nothing here trades, sizes or routes.

  ACCOUNTS               the shown accounts: key -> name, bot, the PC / ledger ids that mean it
  acct_key(acct, bot)    a ledger / PC id -> the account key ("zlarior" and "mffu50k_eval" -> z50k, "b25k_2" -> z25k2, ...)
  pair(rows)             ledger rows -> closed live trades (entry row placed OK + its exit row), one dict each, sorted
  load(pc_days)          every closed live trade of every pulled day; [] when there is no data/pc_days yet (the branch is new)
  bars_paths(pc_days)    the 1m bar files of every pulled day (NQ chart first, else MNQ), for Odeon's replay tape
  fetch_days(remote)     git fetch <remote> data + copy the day folders (tools/data_pull, no bar import) -> (ok, note)
Privacy: an account is its key + the last 4 digits only (a4); balances are not in the trade rows. tests/test_trading_page.py.
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import os
import re
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PC_DAYS = os.path.join(ROOT, "data", "pc_days")
ET = ZoneInfo("America/New_York")
USD_PT = 2.0                                   # MNQ: $2 a point a micro (every bot trades MNQ micros)
ATLAS_KEYS = {"ema_lon_vix": "EMA", "macd_sweep": "MACD", "sr_nyreclaim": "S/R"}
# key: (name, bot or None = from the row, ids that mean it). Order = the order the page shows them.
ACCOUNTS = {
    "z50k": ("Zlarior 50K", "LIT", ("zlarior", "mffu50k_eval", "lit", "main", "fleet")),
    "z25k2": ("Zlarior 25K #2", "LIT", ("b25k_2",)),
    "atlas25f": ("ATLAS funded 25K", "ATLAS", ("atlas", "acctb", "account_b")),
    "rapid25": ("Rapid 25K", None, ("rapid", "acctr", "rapid25k", "rapid_25k", "rapideod", "rapid_eod")),
}
HIDDEN = re.compile(r"blitz|acctc|acct_c|atlas_v2", re.I)      # BLITZ is hidden (owner 2026-11-15); ATLAS v2 is paper only


def acct_key(acct, bot=None) -> str | None:
    a = str(acct or "").strip().lower()
    if not a or HIDDEN.search(a):
        return None
    a = a.split("/")[-1]
    for k, (_n, _b, ids) in ACCOUNTS.items():
        if a in ids or (k == "rapid25" and a.startswith("rapid")):
            return k
    if re.fullmatch(r"[a-z0-9_]{2,24}", a):
        return a                                # a new account the PC added: its own key (the page names it by its id)
    return None


def acct_name(key: str) -> str:
    return ACCOUNTS[key][0] if key in ACCOUNTS else f"Account {key}"


def _f(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x and abs(x) != float("inf") else None


def _fill(e: dict):
    """the entry's fill price (the broker legs' average when the result has them), else the model entry"""
    res = e.get("result") if isinstance(e.get("result"), dict) else {}
    legs = [lg for lg in (res.get("legs") or []) if isinstance(lg, dict) and lg.get("filled")]
    if legs:
        q = sum(int(lg.get("filled") or 0) for lg in legs)
        if q:
            return round(sum(float(lg.get("fill_px") or 0) * int(lg.get("filled") or 0) for lg in legs) / q, 2)
    return _f(res.get("fill_px")) or _f(e.get("entry"))


def _a4(e: dict) -> str | None:
    res = e.get("result") if isinstance(e.get("result"), dict) else {}
    d = re.findall(r"\d", str(res.get("account") or e.get("account") or ""))
    return "".join(d[-4:]) if len(d) >= 4 and not str(res.get("account") or "").lower().startswith("sim") else None


def pair(rows) -> list:
    """Closed LIVE trades of ledger rows: an entry (buy / sell, placed OK, mode live) and its exit row (same acct + entry_t). A
    refused entry, a NO TRADE exit, paper / sim rows and hidden bots are left out."""
    ent, ex = {}, {}
    for r in rows or []:
        if not isinstance(r, dict) or r.get("mode") != "live" or r.get("entry_t") is None or str(r.get("src") or "").startswith("fleet"):
            continue
        ak = acct_key(r.get("acct"), r.get("bot"))
        if not ak or HIDDEN.search(str(r.get("bot") or "")):
            continue
        try:
            k = (ak, int(r["entry_t"]))
        except (TypeError, ValueError):
            continue
        if r.get("side") in ("buy", "sell"):
            if (r.get("result") or {}).get("ok") is not False:
                ent[k] = r
        elif r.get("side") == "exit" and str(r.get("reason") or "").upper() != "NO TRADE":
            ex[k] = r
    out = []
    for k, e in ent.items():
        x = ex.get(k)
        if not x:
            continue
        ak, et = k
        d = 1 if e.get("side") == "buy" else -1
        q = int(x.get("qty") or e.get("qty") or 0) or 1
        entry, stop = _fill(e), _f(e.get("stop"))
        pnl = _f(x.get("pnl"))
        risk = abs(entry - stop) if entry is not None and stop is not None else None
        xpx = _f(x.get("exit_px")) or _f(x.get("fill_px"))
        if xpx is None and entry is not None and pnl is not None:
            xpx = round(entry + d * pnl / (USD_PT * q), 2)          # from the booked $ (the ledger has no exit fill price)
        strat = str(e.get("strategy") or x.get("strategy") or "")          # the ATLAS member (datapipe's "src" is the state file)
        member = ATLAS_KEYS.get(strat) or (strat if strat in ATLAS_KEYS.values() else "")
        _name, bot, _ids = ACCOUNTS.get(ak, (None, None, ()))
        bot = bot or ("ATLAS" if member or str(e.get("bot")) == "atlas" else "LIT")
        xt = int(x.get("exit_t") or x.get("t") or 0) or None
        out.append({"ak": ak, "an": acct_name(ak), "a4": _a4(e), "bot": bot, "m": member if bot == "ATLAS" else "",
                    "t": et, "xt": xt, "side": "LONG" if d == 1 else "SHORT", "q": q, "e": entry, "s": stop, "tg": _f(e.get("target")),
                    "x": xpx, "k": str(x.get("reason") or "").upper()[:12], "usd": pnl if pnl is not None else 0.0,
                    "r": round(pnl / (risk * USD_PT * q), 2) if pnl is not None and risk else None,
                    "risk_usd": round(risk * USD_PT * q, 2) if risk else None,
                    "day": f"{_session_day(et)}"})
    out.sort(key=lambda t: (t["t"], t["ak"]))
    return out


def _session_day(t: int) -> str:
    d = dt.datetime.fromtimestamp(int(t), ET)
    if d.hour >= 18:
        d = d + dt.timedelta(days=1)
    while d.weekday() >= 5:
        d = d + dt.timedelta(days=1)
    return f"{d:%Y-%m-%d}"


def _jsonl_gz(path: str) -> list:
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
        raw = gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw
    except OSError:
        return []
    out = []
    for ln in raw.decode("utf-8", "replace").splitlines():
        try:
            j = json.loads(ln)
        except ValueError:
            continue
        if isinstance(j, dict):
            out.append(j)
    return out


def days(pc_days: str = PC_DAYS) -> list:
    try:
        return sorted(d for d in os.listdir(pc_days) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) and os.path.isdir(os.path.join(pc_days, d)))
    except OSError:
        return []


def load(pc_days: str = PC_DAYS) -> list:
    """every closed live trade of every pulled day (a trade is paired across the day folders: entry and exit can sit in two)"""
    rows = []
    for d in days(pc_days):
        rows += _jsonl_gz(os.path.join(pc_days, d, "trades.jsonl.gz"))
    seen, out = set(), []
    for t in pair(rows):
        k = (t["ak"], t["t"])
        if k not in seen:
            seen.add(k)
            out.append(t)
    return out


def bars_paths(pc_days: str = PC_DAYS) -> list:
    out = []
    for d in days(pc_days):
        for root in ("NQ", "MNQ"):
            p = os.path.join(pc_days, d, "bars", f"{root}_1m.csv.gz")
            if os.path.exists(p):
                out.append(p)
                break
    return out


def bar_days(pc_days: str = PC_DAYS) -> set:
    return {os.path.basename(os.path.dirname(os.path.dirname(p))) for p in bars_paths(pc_days)}


def fetch_days(remote: str = "olympus", out_dir: str = PC_DAYS) -> tuple:
    """git fetch <remote> data, then copy its day folders to out_dir (no bar import: tools/data_pull.py does that). Never raises."""
    try:
        from tools import data_pull
        ok, err = data_pull.fetch(remote)
        if not ok:
            return False, f"no branch data on {remote} yet ({err or 'fetch failed'}): LIVE rows come from the PC feed and the old heartbeat only"
        c, o, _e = data_pull.git(["rev-parse", "FETCH_HEAD"])
        ref = o.strip() if c == 0 and o.strip() else "FETCH_HEAD"
        got = data_pull.copy_days(ref, out_dir)
        return True, f"branch data: {len(data_pull.list_days(ref))} days, {len(got)} new copied"
    except Exception as e:  # noqa: BLE001
        return False, f"data branch not read ({e.__class__.__name__})"
