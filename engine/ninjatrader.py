"""NinjaTrader 8 execution adapter and bar feed (ATI File Interface: Order Instruction Files).

Why: the MFFU account clears through Tradovate, and Tradovate gives prop accounts no API keys, so engine/tradovate.py
cannot reach it. NinjaTrader 8 Desktop can trade the same account (its Tradovate connection) and executes Order
Instruction Files (OIF) that any program writes into Documents\\NinjaTrader 8\\incoming\\. No credentials are involved.

Same contract as live.PaperAdapter / tradovate.TradovateAdapter. LiveBot builds it with the start config and calls
send(action) with
  {"side": "buy"|"sell", "qty": micros, "stop": px, "target": px, "entry": px, "sym": "NQ", "entry_t": t}  -> bracket
  {"side": "exit", "reason": ..., "entry_t": t}   -> CLOSEPOSITION, then cancel any of our legs still working
  {"side": "exit", "reason": "KILL SWITCH"}       -> kill(): THIS account only (CLOSEPOSITION + CANCEL by id; account B,
                                                     extra accounts, remote flatten)
  {"side": "exit", "reason": "KILL SWITCH", "scope": "global"} -> kill(scope="global"): FLATTENEVERYTHING (every account
                                                     connected in NinjaTrader; only the owner's kill, LiveBot.kill_switch)
  {"side": "modify", "stop": px}                  -> CHANGE the stop order (breakeven at 1R)
  {"side": "add", "qty": n, "dir": d, "entry_t": t} -> LIT scale-in: MARKET add, then CHANGE the qty of the OCO stop and
                                                     target to the whole position (add_to_position)
  {"side": "cancel"}                              -> CANCEL our working orders
plus status(), positions(), kill() and tick() (LiveBot calls tick() once per poll). Public methods return a dict with
"ok" and never raise into the bot loop.

OIF grammar (NinjaTrader 8 Help Guide > Automated Trading Interface; links in ninjatrader/SETUP.md). One command per
line, 13 semicolon-separated fields:
  COMMAND;ACCOUNT;INSTRUMENT;ACTION;QTY;ORDER TYPE;LIMIT PRICE;STOP PRICE;TIF;OCO ID;ORDER ID;STRATEGY;STRATEGY ID
Files go to incoming\\ named oif*.txt; NinjaTrader processes a file the moment it is written and then deletes it.
NinjaTrader answers in outgoing\\ (wiped when NinjaTrader restarts):
  <ORDER ID>.txt                                  "ORDER STATE;FILLED AMOUNT;AVERAGE FILL PRICE"
  <instrument> <exchange>_<account>_Position.txt  "LONG|SHORT|FLAT;QUANTITY;AVERAGE ENTRY PRICE"
  <connection name>.txt                           "CONNECTED" | "DISCONNECTED"

Bracket = MARKET entry first; only when NinjaTrader reports the fill, a STOPMARKET stop and a LIMIT target sharing one
OCO id (never a naked stop/limit that could open a position by itself if the entry failed).

Safety gates (non-negotiable, same spirit as engine/tradovate.py):
  * NinjaTrader's own simulation accounts (Sim101, SimNNN, PlaybackNNN) by default. Any other account (the MFFU account)
    only when the start config has armed=true AND confirm == LIVE_PHRASE AND the server runs with NINJATRADER_LIVE=1.
  * orders above max_micros (40) or 4 minis are refused, not clamped; no new entry at/after the flat time (15:55 ET),
    before 08:00 ET, on a weekend, while the kill switch is on, or while a position / bracket is still open.
  * an order file NinjaTrader has not picked up within a few seconds is withdrawn (deleted), so it can never execute
    late; a rejected stop or target flattens the position at once; tick() flattens anything still open at flat time.
  * every OIF line is logged (bot log + logs/ninjatrader_oif.log). OIF needs no credentials and none are written.

Bar feed: NinjaTraderBars reads the CSVs that ninjatrader/LE_Feed.cs (no chart) or LE_BarFeed.cs (a chart) writes
(Documents\\NinjaTrader 8\\le_feed\\MNQ_5m.csv ...) and returns the same frame as live._yahoo_recent (time = bar OPEN, unix seconds). engine/live.py uses
it for data_source "ninjatrader". When the file is missing or stale the bot blocks NEW entries (FEED STALE; no Yahoo,
owner 2026-10-19, engine/pcbars.py); only with "no_yahoo": false does it fall back to Yahoo, with a logged warning.

  python -m engine.ninjatrader --selftest       offline self-test: simulated NinjaTrader folders, no network
  python -m engine.ninjatrader --help           status, Sim101 checks, start / stop / kill the PC bot
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import secrets
import sys
import threading
import time
import zlib
from collections import deque
from zoneinfo import ZoneInfo

from .tradovate import LIVE_PHRASE, MAX_MICROS_HARD, MAX_MINIS, MICRO, MINI, TICK, front_month

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(ROOT, "data", "ninjatrader_state.json")      # gitignored: open brackets survive a restart
AUDIT_PATH = os.path.join(ROOT, "logs", "ninjatrader_oif.log")         # every OIF line ever written (logs/ is ignored)
LIVE_ENV = "NINJATRADER_LIVE"            # must be "1" in the SERVER's environment before a non-Sim account can trade
# account allowlist (pre-launch audit 2026-10-25): a non-Sim account trades only when its exact NinjaTrader Name is listed in
# data/nt_accounts_allow.json (gitignored; `python -m engine.ninjatrader --allow-account "<Name>"`) or in NINJATRADER_ALLOW
# (comma list, .env.local.ps1). Sim101 / SimNNN / PlaybackNNN are always allowed. Every PLACE / CLOSEPOSITION line must also
# name the adapter's own account, and FLATTENEVERYTHING / CANCELALLORDERS go out only on the owner's global kill.
ALLOW_PATH = os.path.join(ROOT, "data", "nt_accounts_allow.json")
ALLOW_ENV = "NINJATRADER_ALLOW"
LOCK_DIR = "le_locks"                    # <NinjaTrader 8>\le_locks\<account>.lock: one bot process per account (OS file lock)
_LOCKS: dict = {}                        # lock path -> open file handle held by THIS process (released when it exits)
FEED_DIR = "le_feed"
SIM_ACCOUNT = re.compile(r"^(Sim|Playback)\d+$")     # NinjaTrader's own simulation accounts: Sim101, Sim102, Playback101

# ---------------------------------------------------------------------- the documented OIF grammar
FIELDS = ("COMMAND", "ACCOUNT", "INSTRUMENT", "ACTION", "QTY", "ORDER TYPE", "LIMIT PRICE", "STOP PRICE", "TIF",
          "OCO ID", "ORDER ID", "STRATEGY", "STRATEGY ID")
# Verbatim from the help guide page "Order Instruction Files (OIF)": <> = required, [] = optional, empty = must be empty.
DOC_FORMATS = {
    "CANCEL": "CANCEL;;;;;;;;;;<ORDER ID>;;[STRATEGY ID]",
    "CANCELALLORDERS": "CANCELALLORDERS;;;;;;;;;;;;",
    "CHANGE": "CHANGE;;;;<QUANTITY>;;<LIMIT PRICE>;<STOP PRICE>;;;<ORDER ID>;;[STRATEGY ID]",
    "CLOSEPOSITION": "CLOSEPOSITION;<ACCOUNT>;<INSTRUMENT>;;;;;;;;;;",
    "CLOSESTRATEGY": "CLOSESTRATEGY;;;;;;;;;;;;<STRATEGY ID>",
    "FLATTENEVERYTHING": "FLATTENEVERYTHING;;;;;;;;;;;;",
    "PLACE": "PLACE;<ACCOUNT>;<INSTRUMENT>;<ACTION>;<QTY>;<ORDER TYPE>;[LIMIT PRICE];[STOP PRICE];<TIF>;[OCO ID];[ORDER ID];[STRATEGY];[STRATEGY ID]",
    "REVERSEPOSITION": "REVERSEPOSITION;<ACCOUNT>;<INSTRUMENT>;<ACTION>;<QTY>;<ORDER TYPE>;[LIMIT PRICE];[STOP PRICE];<TIF>;[OCO ID];[ORDER ID];[STRATEGY];[STRATEGY ID]",
}
# "Commands and Valid Parameters": the values each field accepts
VALID = {"ACTION": {"BUY", "SELL"}, "ORDER TYPE": {"MARKET", "LIMIT", "STOPMARKET", "STOPLIMIT"}, "TIF": {"DAY", "GTC"}}
_PRICE = re.compile(r"^\d+(\.\d+)?$")        # "use decimals not commas (1212.25 for example)"
_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")   # ours: ids double as outgoing file names, so keep them file-name safe

# order states (NinjaTrader 8 "Order State Definitions"; the file spelling is normalised: upper case, no spaces)
MAX_ENTRIES_DAY = 8                      # entry files per account per trading day, whatever the strategy (BLITZ max is 6)
FILLED, PARTFILLED = "FILLED", "PARTFILLED"
DEAD = {"CANCELLED", "CANCELED", "REJECTED"}
LIVE_STATES = {"INITIALIZED", "SUBMITTED", "ACCEPTED", "TRIGGERPENDING", "WORKING", "CHANGEPENDING", "CHANGESUBMITTED",
               "CANCELPENDING", "CANCELSUBMITTED", "PENDINGSUBMIT", "PENDINGCHANGE", "PENDINGCANCEL"}
KNOWN_STATES = {FILLED, PARTFILLED, "UNKNOWN"} | DEAD | LIVE_STATES
OPEN_STATUSES = ("entry_sent", "pending", "cancel_pending", "protected", "unprotected", "closing")
# cancel_pending: a CANCEL of an unfilled entry was sent; only NinjaTrader's CANCELLED/REJECTED resolves it, and a fill that
# arrives meanwhile is protected like any other (LIT report ch.27: an execution can arrive while a cancel is pending).


def _template_regex(fmt: str):
    parts = []
    for f in fmt.split(";"):
        if f.startswith("<"):
            parts.append(r"[^;\r\n]+")
        elif f.startswith("["):
            parts.append(r"[^;\r\n]*")
        else:
            parts.append(re.escape(f))
    return re.compile("^" + ";".join(parts) + "$")


DOC_REGEX = {k: _template_regex(v) for k, v in DOC_FORMATS.items()}


def validate_line(line: str) -> list:
    """Problems with one OIF line against the documented format and valid values ([] = valid)."""
    if not isinstance(line, str) or "\n" in line or "\r" in line:
        return ["not a single line"]
    f = line.split(";")
    if len(f) != 13:
        return [f"{len(f)} fields, the format has 13 (12 semicolons)"]
    cmd = f[0]
    if cmd not in DOC_REGEX:
        return [f"unknown command {cmd!r}"]
    out = [] if DOC_REGEX[cmd].match(line) else [f"does not match the documented {cmd} format {DOC_FORMATS[cmd]}"]
    named = dict(zip(FIELDS, f))
    for k, allowed in VALID.items():
        if named[k] and named[k] not in allowed:
            out.append(f"{k} {named[k]!r} not one of {sorted(allowed)}")
    if named["QTY"] and not named["QTY"].isdigit():
        out.append(f"QTY {named['QTY']!r} is not an integer")
    if cmd in ("PLACE", "REVERSEPOSITION") and named["QTY"].isdigit() and int(named["QTY"]) < 1:
        out.append("QTY must be >= 1")
    for k in ("LIMIT PRICE", "STOP PRICE"):
        if named[k] and not _PRICE.match(named[k]):
            out.append(f"{k} {named[k]!r} is not a US decimal")
    for k in ("OCO ID", "ORDER ID"):
        if named[k] and not _ID.match(named[k]):
            out.append(f"{k} {named[k]!r} has characters outside A-Z a-z 0-9 _ -")
    if cmd in ("PLACE", "REVERSEPOSITION"):
        ot = named["ORDER TYPE"]
        if ot in ("LIMIT", "STOPLIMIT") and not _positive(named["LIMIT PRICE"]):
            out.append(f"{ot} needs a LIMIT PRICE")
        if ot in ("STOPMARKET", "STOPLIMIT") and not _positive(named["STOP PRICE"]):
            out.append(f"{ot} needs a STOP PRICE")
    return out


def _positive(s):
    try:
        return float(s) > 0
    except (TypeError, ValueError):
        return False


def _tick(px: float) -> float:
    return round(round(float(px) / TICK) * TICK, 2)


def fmt_px(px) -> str:
    """US decimal, tick-rounded ("24990.25"); 0 / None -> "0" (the documented 'leave unchanged / not used' value)."""
    if not px:
        return "0"
    return f"{_tick(px):.2f}"


def oif_line(cmd, account="", instrument="", action="", qty="", order_type="", limit="", stop="", tif="", oco="",
             order_id="", strategy="", strategy_id="") -> str:
    fields = [cmd, account, instrument, action, qty, order_type, limit, stop, tif, oco, order_id, strategy, strategy_id]
    fields = ["" if v is None else str(v) for v in fields]
    for v in fields:
        if ";" in v or "\n" in v or "\r" in v:
            raise ValueError(f"OIF field {v!r} contains a separator")
    return ";".join(fields)


def place_line(account, instrument, action, qty, order_type, limit=0, stop=0, oco="", order_id="", tif="DAY"):
    return oif_line("PLACE", account, instrument, action, int(qty), order_type, fmt_px(limit), fmt_px(stop), tif, oco, order_id)


def change_line(order_id, qty=0, limit=0, stop=0):
    """CHANGE;;;;<QUANTITY>;;<LIMIT PRICE>;<STOP PRICE>;;;<ORDER ID>;; - zero = leave that parameter unchanged."""
    return oif_line("CHANGE", qty=int(qty or 0), limit=fmt_px(limit), stop=fmt_px(stop), order_id=order_id)


def cancel_line(order_id):
    return oif_line("CANCEL", order_id=order_id)


def close_line(account, instrument):
    return oif_line("CLOSEPOSITION", account, instrument)


FLATTEN_EVERYTHING = oif_line("FLATTENEVERYTHING")
RESET_OK_NAME = "ninjatrader_reset_ok.json"  # next to the state file: the owner's "account checked after a NinjaTrader restart"


# ---------------------------------------------------------------------- parsing NinjaTrader's outgoing files
def _norm_state(s: str) -> str:
    return re.sub(r"[\s_]", "", str(s or "")).upper()


def parse_order_state(raw):
    """'FILLED;2;25020.25' -> {"state", "filled", "avg"}; None when the text is not an order state line."""
    if raw is None:
        return None
    lines = [ln.strip() for ln in str(raw).replace("﻿", "").splitlines() if ln.strip()]
    if not lines:
        return None
    f = [x.strip() for x in lines[-1].split(";")]
    state = _norm_state(f[0])
    if not state or not state.isalpha():
        return None
    try:
        filled = int(float(f[1])) if len(f) > 1 and f[1] else 0
    except ValueError:
        return None
    try:
        avg = float(f[2]) if len(f) > 2 and f[2] else None
    except ValueError:
        avg = None
    return {"state": state, "filled": filled, "avg": avg or None, "known": state in KNOWN_STATES}


def parse_position(raw):
    """'LONG;2;25020.25' (the guide shows spaces after the semicolons; both parse) -> {"side", "qty", "avg"}."""
    if raw is None:
        return None
    lines = [ln.strip() for ln in str(raw).replace("﻿", "").splitlines() if ln.strip()]
    if not lines:
        return None
    f = [x.strip() for x in lines[-1].split(";")]
    side = f[0].upper()
    if side not in ("LONG", "SHORT", "FLAT"):
        return None
    try:
        qty = abs(int(float(f[1]))) if len(f) > 1 and f[1] else 0
        avg = float(f[2]) if len(f) > 2 and f[2] else None
    except ValueError:
        return None
    return {"side": side, "qty": 0 if side == "FLAT" else qty, "avg": avg or None}


_MONTHS = {m: i + 1 for i, m in enumerate(("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"))}


def inst_key(name):
    """(ROOT, month, 2-digit year) of an instrument name in any of NinjaTrader's spellings, else None:
    'MNQ 12-26' / 'MNQ 12-26 Globex' (NinjaTrader 8), 'MNQ DEC26' / 'MNQ Dec26 Globex' (display style), 'MNQ 1226'
    (NinjaTrader 7 style). The exchange suffix (anything after the expiry) is ignored."""
    s = re.sub(r"\s+", " ", str(name or "").strip().upper())
    m = re.match(r"^([A-Z0-9]+) (\d{2})-(\d{2})(?: |$)", s) or re.match(r"^([A-Z0-9]+) (\d{2})(\d{2})(?: |$)", s)
    if m:
        mm = int(m.group(2))
        return (m.group(1), mm, int(m.group(3))) if 1 <= mm <= 12 else None
    m = re.match(r"^([A-Z0-9]+) ([A-Z]{3})(\d{2})(?: |$)", s)
    if m and m.group(2) in _MONTHS:
        return (m.group(1), _MONTHS[m.group(2)], int(m.group(3)))
    return None


def same_instrument(file_inst, inst) -> bool:
    """True when the instrument part of an outgoing position file name ('MNQ 12-26 Globex', 'MNQ DEC26 Globex') is the
    contract `inst` ('MNQ 12-26') the bot trades."""
    a, b = str(file_inst or ""), str(inst or "")
    if not a or not b:
        return False
    if a == b or a.startswith(b + " "):
        return True
    ka, kb = inst_key(a), inst_key(b)
    return ka is not None and ka == kb


_CONN_SEEN: dict = {}       # outgoing file path -> ((mtime_ns, size), its text upper-cased): NinjaTraderAdapter.connections
_CONN_LOCK = threading.Lock()


def _read_text(path):
    for _ in range(3):
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                return fh.read()
        except FileNotFoundError:
            return None
        except OSError:                  # NinjaTrader is writing it right now: try again in a moment
            time.sleep(0.02)
    return None


# ---------------------------------------------------------------------- naming, folders, time
def _session_from(cfg: dict) -> int:
    """First ET minute of the trading session the adapter accepts entries in (and before which it flattens a leftover
    trade): cfg nt_session_from, else the LIT entry window's start (02:00) when the bot trades LIT (cfg model, else
    live_model.json), else 08:00 (the Liquidity Engine)."""
    if cfg.get("nt_session_from") is not None:
        return int(cfg["nt_session_from"])
    try:
        from .lab_adapter import live_model
        lm = live_model()
        model = cfg.get("model") or lm.get("model")
        if model == "lit":
            from . import lit as _lit
            lp = cfg.get("model_params") or lm.get("lit") or {}
            w = lp.get("window") or _lit.DEFAULTS["window"]
            if _all_hours(cfg):               # the window's first minute in trading-day order (18:00 for the Asia slot)
                return int(min((int(a) for a, _ in w), key=_tday))
            return int(min(a for a, _ in w))
    except Exception:
        pass
    return 480


def _all_hours(cfg: dict) -> bool:
    """LIT all_hours on (the Asia slot, research/writeups/lit-more-entries.md): cfg nt_all_hours, else the LIT params the bot
    trades (cfg model_params, else live_model.json "lit"). Then the session is the CME trading day 18:00 -> 17:00 (entries
    and the flat check in trading-day order); off (today) = the clock-day rules, unchanged."""
    if cfg.get("nt_all_hours") is not None:
        return bool(cfg["nt_all_hours"])
    try:
        from .lab_adapter import live_model
        lm = live_model()
        if (cfg.get("model") or lm.get("model")) == "lit":
            return bool((cfg.get("model_params") or lm.get("lit") or {}).get("all_hours"))
    except Exception:
        pass
    return False


def _tday(mod: int) -> int:
    """ET minute in CME trading-day order (18:00 = 0)."""
    return (int(mod) - 1080) % 1440


def entry_never_placed(adapter, entry_t, res, now=None) -> bool:
    """True only when the entry entry_t provably never became a position (2026-10-27: ATLAS's 03:30 entry was refused, yet
    kept "open" and its paper P&L was about to be booked): the order's answer `res` is NOT OK, no leg of it reported a
    fill, no leg of the adapter is open / pending for it (legs + this process's retired history), and NinjaTrader shows no
    position on the order contracts. An answer with a leg still working ("fill not reported yet") counts only once the
    adapter retired that leg unfilled. Anything unclear = False (kept, managed and booked as before). Used by LIT
    (engine/live.py) and account B (engine/account_b.py). A rejection with MFFU's risk-desk text ("maximum order quantity",
    "Limit: 0", a risk rule) is a LOCKED account, not a bug: locked_reject() below, engine/lifecycle.py."""
    if not isinstance(res, dict) or res.get("ok") is not False:
        return False
    rl = [x for x in res.get("legs") or [] if isinstance(x, dict)]
    if any(int(x.get("filled") or 0) > 0 for x in rl):
        return False
    mine = [lg for lg in list(getattr(adapter, "legs", None) or []) + list(getattr(adapter, "history", None) or [])
            if isinstance(lg, dict) and int(lg.get("entry_t") or 0) == int(entry_t)]
    if any(lg.get("status") in OPEN_STATUSES or int(lg.get("filled") or 0) > 0 for lg in mine):
        return False
    if rl and not all(x.get("state") in DEAD for x in rl) and not mine and not _no_trace(adapter, entry_t, rl, now):
        return False                                      # a leg was still working when it answered: unknown since
    try:
        insts = set((adapter._instruments() or {}).values()) if callable(getattr(adapter, "_instruments", None)) else set()
        for inst in insts:
            p = adapter.position_for(inst)
            if p and p.get("side") not in (None, "FLAT") and int(p.get("qty") or 0) != 0:
                return False
    except Exception:
        pass
    return True


# A LOCKED account, not a bug (2026-11-17): ATLAS's Builder 25K passed ($26,946.10 vs $26,500) and MFFU locked it; every
# order came back "Your maximum order quantity has been met... Limit: 0 Current: 1. Scope: MNQ Rule #3787". The risk desk's
# text is only in NinjaTrader's Log (the order file just says REJECTED). engine/lifecycle.py stands that account down
# (no retries), keeps the others trading and pushes once.
LOCK_RE = re.compile(r"maximum order quantity|\blimit:\s*0\b|\brule\s*#\s*\d+|\brisk rule|account (is )?(locked|disabled|suspended|"
                     r"closed|liquidat\w*)|trading (is )?(disabled|locked|halted|not allowed)|auto[- ]?liquidat|liquidat\w* only|"
                     r"max(imum)? (position|contracts?)( size)? (has been |is )?(met|reached|exceeded)", re.I)


def lock_reason(text) -> str | None:
    """The risk desk's refusal in a broker / NinjaTrader text ("...Limit: 0 Current: 1. Scope: MNQ Rule #3787"), one line of at
    most 200 characters around it; None for anything else (a plain REJECTED, a connection problem, the bot's own REFUSED)."""
    s = re.sub(r"\s+", " ", str(text or "")).strip()
    if not s or s.upper().startswith("REFUSED"):
        return None
    m = LOCK_RE.search(s)
    if not m:
        return None
    a = max(0, m.start() - 90)
    return (("..." if a else "") + s[a:a + 200]).strip()


def nt_reject_text(adapter, entry_t) -> str | None:
    """NinjaTrader's Log (the newest 3 log.*.txt) rejecting an order of this entry (LE<entry_t>) with a risk-desk text: that
    text (lock_reason), else None. Read-only, never raises."""
    try:
        import glob as _glob
        folder = getattr(adapter, "folder", None)
        if not folder or not entry_t:
            return None
        tag = f"LE{int(entry_t)}"
        fs = sorted(_glob.glob(os.path.join(folder, "log", "log.*.txt")), key=os.path.getmtime)[-3:]
        for f in reversed(fs):
            with open(f, encoding="utf-8", errors="replace") as fh:
                for ln in fh:
                    if tag in ln and "reject" in ln.lower():
                        why = lock_reason(ln)
                        if why:
                            return why
    except Exception:
        return None
    return None


def locked_reject(adapter, entry_t, res, now=None) -> str | None:
    """The risk desk's text when this entry's NOT-OK answer is an account lock (MFFU "maximum order quantity" / "Limit: 0" /
    a risk rule) AND it provably never became a position (entry_never_placed); else None (a normal rejection = a bug or a
    broker problem, handled as before)."""
    if not isinstance(res, dict) or res.get("ok") is not False:
        return None
    why = res.get("locked") or lock_reason(res.get("error")) or nt_reject_text(adapter, entry_t)
    if not why:
        return None
    try:
        return why if entry_never_placed(adapter, entry_t, res, now=now) else None
    except Exception:
        return None


NO_TRACE_S = 600


def _nt_said_no_account(adapter, entry_t) -> bool:
    """NinjaTrader's Log (<NinjaTrader 8>\\log\\log.*.txt, the newest 3) has the PLACE of this entry (LE<entry_t>) refused
    with "account does not exist": it never became an order (2026-10-27: every MFFU order went to a Name without the R)."""
    try:
        import glob as _glob
        folder = getattr(adapter, "folder", None)
        if not folder:
            return False
        tag = f"LE{int(entry_t)}"
        fs = sorted(_glob.glob(os.path.join(folder, "log", "log.*.txt")), key=os.path.getmtime)[-3:]
        for f in fs:
            with open(f, encoding="utf-8", errors="replace") as fh:
                for ln in fh:
                    if tag in ln and "PLACE;" in ln and "account does not exist" in ln.lower():
                        return True
    except Exception:
        return False
    return False


def _no_trace(adapter, entry_t, rl, now=None) -> bool:
    """A "fill not reported yet" entry the adapter no longer knows (a restart lost its retired legs) never became a position
    when, NO_TRACE_S after it: NinjaTrader wrote no order file for any of its orders (outgoing\\ holds no name with
    LE<entry_t>) AND it shows a FLAT position file for every contract of it (2026-10-27: Zlarior's 06:12 SELL 7 and
    ATLAS's 03:30 BUY 3 were picked up, never answered, the accounts flat). A missing position file proves nothing."""
    try:
        if _nt_said_no_account(adapter, entry_t):
            return True                               # NinjaTrader's Log: this order went to an account it does not have
        if (time.time() if now is None else float(now)) - float(entry_t) < NO_TRACE_S:
            return False
        if not callable(getattr(adapter, "_listing", None)) or not callable(getattr(adapter, "position_for", None)):
            return False
        tag = f"LE{int(entry_t)}"
        if any(tag in n for n in adapter._listing()):
            return False
        insts = {x.get("instrument") for x in rl if x.get("instrument")}
        if not insts:
            return False
        for inst in insts:
            p = adapter.position_for(inst)
            if not p or p.get("side") != "FLAT":
                return False
        return True
    except Exception:
        return False


def is_sim(account: str) -> bool:
    return bool(SIM_ACCOUNT.match(str(account or "").strip()))


def resolve_account(cfg: dict | None = None) -> str:
    cfg = cfg or {}
    return str(cfg.get("nt_account") or os.environ.get("NINJATRADER_ACCOUNT") or "Sim101").strip()


def _publish(src: str, dst: str):
    """Move a finished order file into incoming\\ in one step, never replacing a file already there (FileExistsError).
    Windows: os.rename refuses an existing target. POSIX: a hard link refuses it too, then the source name is dropped."""
    if os.name == "nt":
        os.rename(src, dst)
        return
    try:
        os.link(src, dst)
    except FileExistsError:
        raise
    except OSError:                      # a file system without hard links: check, then rename (tiny race, POSIX tests only)
        if os.path.exists(dst):
            raise FileExistsError(dst)
        os.replace(src, dst)
        return
    try:
        os.remove(src)
    except OSError:
        pass


def allowed_accounts(path: str | None = None) -> set:
    """The owner's account allowlist: data/nt_accounts_allow.json {"accounts": [...]} + NINJATRADER_ALLOW (comma list)."""
    out = {a.strip() for a in os.environ.get(ALLOW_ENV, "").split(",") if a.strip()}
    try:
        with open(path or ALLOW_PATH, encoding="utf-8") as fh:
            d = json.load(fh)
        out |= {str(a).strip() for a in (d.get("accounts") or []) if str(a).strip()}
    except Exception:
        pass
    return out


def allow_account(name: str, path: str | None = None, remove: bool = False) -> list:
    """Add (or remove) one exact account Name in the allowlist file; returns the new list."""
    name = str(name or "").strip()
    if not name or any(c in name for c in ";\r\n,"):
        raise ValueError("give the account Name exactly as NinjaTrader's Accounts tab shows it")
    p = path or ALLOW_PATH
    try:
        with open(p, encoding="utf-8") as fh:
            cur = [str(a).strip() for a in (json.load(fh).get("accounts") or [])]
    except Exception:
        cur = []
    cur = [a for a in cur if a != name] + ([] if remove else [name])
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"accounts": cur, "note": "NinjaTrader account Names the bot may send orders to (Sim accounts always)"}, fh, indent=1)
    from .fsutil import replace as _fs_replace   # retried: Windows / OneDrive lock the target a moment
    _fs_replace(tmp, p)
    return cur


def nt_instrument(root: str = "MNQ", today: dt.date | None = None) -> str:
    """NinjaTrader's name for the front quarterly contract, e.g. 'MNQ 12-26'. Same roll rule as tradovate.front_month:
    the next contract from 8 days before the 3rd-Friday expiry (Dec 2026 -> Mar 2027 on 2026-12-10)."""
    today = today or dt.datetime.now(ET).date()
    code = front_month(root, today)                      # e.g. MNQZ6
    month = {"H": 3, "M": 6, "U": 9, "Z": 12}[code[-2]]
    year = today.year - today.year % 10 + int(code[-1])
    if year < today.year:
        year += 10
    return f"{root} {month:02d}-{year % 100:02d}"


# ---------------------------------------------------------------------- which chart LIT decides on: MNQ (default) or NQ
# research/writeups/mnq-vs-nq-feed.md (2026-10-26): about a third of LIT's setups differ between MNQ and NQ bars (MNQ's
# thinner book prints other wicks), and the backtest is NQ. signal_root "NQ" = the bot reads an NQ chart's LE_BarFeed files
# (le_feed\NQ_5m.csv, NQ_1m.csv, NQ_1m_open.csv, NQ_instrument.txt; LE_BarFeed names its files after the chart's
# instrument root, so they never clash with the MNQ chart's) for every decision, and still sends every order to MNQ:
# same index points, same 0.25 tick, stops / targets at the same prices, size at MNQ's $2 a point (engine/lit.py PV).
# No NQ file -> the MNQ chart's files, exactly as before. Default "MNQ": nothing changes.
SIGNAL_ROOTS = ("MNQ", "NQ")
SIGNAL_ROOT_ENV = "LE_SIGNAL_ROOT"
_SR_CACHE: dict = {}


def _model_signal_root():
    """live_model.json "signal_root" (LE_LIVE_MODEL, the tests' model override, first); re-read only when the file changes."""
    if os.environ.get("LE_LIVE_MODEL"):
        try:
            return json.loads(os.environ["LE_LIVE_MODEL"]).get("signal_root")
        except Exception:
            return None
    p = os.path.join(ROOT, "live_model.json")
    try:
        st = os.stat(p)
    except OSError:
        return None
    key = (st.st_mtime_ns, st.st_size)
    hit = _SR_CACHE.get(p)
    if hit and hit[0] == key:
        return hit[1]
    try:
        with open(p, encoding="utf-8") as fh:
            v = json.load(fh).get("signal_root")
    except Exception:
        v = None
    _SR_CACHE[p] = (key, v)
    return v


def signal_root(cfg: dict | None = None) -> str:
    """"MNQ" (default) or "NQ": cfg["signal_root"] > LE_SIGNAL_ROOT > live_model.json "signal_root" > "MNQ"."""
    v = (cfg or {}).get("signal_root") or os.environ.get(SIGNAL_ROOT_ENV) or _model_signal_root() or "MNQ"
    v = str(v).strip().upper()
    return v if v in SIGNAL_ROOTS else "MNQ"


def feed_roots(cfg: dict | None = None) -> dict:
    """{sym: chart roots in the order their LE_BarFeed files are looked for}: cfg["nt_feed_roots"] when set (the start cfg),
    else MNQ first (default) or NQ first (signal_root "NQ"). NinjaTraderBars reads ONE root per symbol (root_for)."""
    if cfg and cfg.get("nt_feed_roots"):
        return cfg["nt_feed_roots"]
    return {"NQ": ["NQ", "MNQ"] if signal_root(cfg) == "NQ" else ["MNQ", "NQ"], "ES": ["MES", "ES"]}


def contract_expiry(name):
    """(yy, mm) of a dated NinjaTrader contract name ("MNQ 12-26" -> (26, 12)), None for "MNQ ##-##" / unknown."""
    m = re.search(r"(\d{2})-(\d{2})$", str(name or "").strip())
    return (int(m.group(2)), int(m.group(1))) if m else None


def contract_problem(chart, insts) -> str | None:
    """The roll guard's verdict: None when the LE_BarFeed chart (`chart`, e.g. "MNQ 12-26" or "NQ 12-26") is on the same
    contract month as every order instrument in `insts` (the root may differ: an NQ chart prices MNQ orders), else the
    one-line refusal. Unknown or continuous chart -> None (NinjaTraderAdapter warns about a continuous one itself)."""
    ce = contract_expiry(chart)
    if not chart or ce is None:
        return None
    for inst in insts:
        oe = contract_expiry(inst)
        if oe and ce != oe:
            want = f"{str(chart).split(' ')[0]} {str(inst).split(' ')[-1]}"
            if ce < oe:
                return f"Chart is on the old contract ({chart}): switch it to {want}. Entry not sent (orders go to {inst})."
            return f"Chart is on {chart} but orders go to {inst}: switch the chart to {want}. Entry not sent."
    return None


# ---------------------------------------------------------------------- no-chart mode: the LE_Feed add-on (2026-11-02)
# ninjatrader/LE_Feed.cs (a NinjaScript AddOn, Custom\AddOns) writes the same le_feed files as the LE_BarFeed chart with
# no chart open, re-requests a stale series by itself, and reads which contracts to write from le_feed\feed_instruments.txt
# (the bot writes it: sync_feed_instruments). It reports once a minute in le_feed\le_feed_status.txt:
#     <unix time>,source=addon,instruments=MNQ 12-26;NQ 12-26,last_1m=<unix open of the last closed 1m bar>,resubs=N,connected=1
# Read-only on both sides: nothing here changes a trading decision (the bars are read exactly as before).
FEED_INSTRUMENTS = "feed_instruments.txt"
FEED_STATUS = "le_feed_status.txt"
ADDON_FRESH_S = 300                     # the add-on rewrites its status every minute: older than 5 min = NinjaTrader closed


def feed_instruments(cfg: dict | None = None, today: dt.date | None = None) -> list:
    """The contracts the LE_Feed add-on should write bars for: the micro the bot orders (the roll's current contract, or the
    nt_instrument pinned in the config), plus the NQ contract when signal_root is "NQ" (the bot then decides on NQ bars)."""
    cfg = cfg or {}
    today = today or dt.datetime.now(ET).date()
    sym = cfg.get("sym", "NQ")
    out = [str(cfg.get("nt_instrument") or nt_instrument(MICRO.get(sym, "MNQ"), today)).strip()]
    if signal_root(cfg) == "NQ":
        nq = nt_instrument("NQ", today)
        if nq not in out:
            out.append(nq)
    return out


def sync_feed_instruments(folder: str | None = None, cfg: dict | None = None, today: dt.date | None = None) -> bool:
    """Write le_feed\\feed_instruments.txt (one contract per line) when its content changes; True = written. Only into an
    existing NinjaTrader folder (never creates Documents\\NinjaTrader 8 on a machine without NinjaTrader)."""
    folder = folder or default_folder()
    if not os.path.isdir(folder):
        return False
    text = "".join(f"{n}\n" for n in feed_instruments(cfg, today))
    d = os.path.join(folder, FEED_DIR)
    p = os.path.join(d, FEED_INSTRUMENTS)
    if _read_text(p) == text:
        return False
    os.makedirs(d, exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    from .fsutil import replace as _fs_replace   # retried: Windows / OneDrive lock the target a moment
    _fs_replace(tmp, p)
    return True


def parse_feed_status(line: str) -> dict | None:
    """One le_feed_status.txt line -> {"time", "source", "instruments": [...], "last_1m", "resubs", "connected"}; None when
    it is not a status line."""
    parts = [x.strip() for x in str(line or "").strip().split(",")]
    if not parts or not parts[0]:
        return None
    try:
        t = int(float(parts[0]))
    except ValueError:
        return None
    kv = {}
    for x in parts[1:]:
        k, sep, v = x.partition("=")
        if sep:
            kv[k.strip()] = v.strip()
    if "source" not in kv:
        return None

    def _int(v):
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return None
    return {"time": t, "source": kv["source"], "instruments": [s for s in kv.get("instruments", "").split(";") if s.strip()],
            "last_1m": _int(kv.get("last_1m")), "resubs": _int(kv.get("resubs")) or 0,
            "connected": None if kv.get("connected") in (None, "") else kv.get("connected") == "1"}


def read_feed_status(folder: str | None = None, now=None) -> dict | None:
    """The LE_Feed add-on's status (parse_feed_status + "age_s", "fresh"), None when the file is missing (chart mode)."""
    txt = _read_text(os.path.join(folder or default_folder(), FEED_DIR, FEED_STATUS))
    if not txt or not txt.strip():
        return None
    st = parse_feed_status(txt.strip().splitlines()[-1])
    if st is None:
        return None
    now = int(time.time() if now is None else now)
    st["age_s"] = max(0, now - st["time"])
    st["fresh"] = st["age_s"] <= ADDON_FRESH_S
    return st


ADDON_NOT_STARTED = ("LE_Feed is installed but has not started (no le_feed_status.txt): in NinjaTrader press F5 in the "
                     "NinjaScript Editor; New > NinjaScript Output must say 'LE_Feed: started'")


def addon_installed(folder: str | None = None) -> bool:
    """bin\\Custom\\AddOns\\LE_Feed.cs is in the NinjaTrader folder (NO_CHART_MODE.bat copied it)."""
    try:
        return os.path.isfile(os.path.join(folder or default_folder(), "bin", "Custom", "AddOns", "LE_Feed.cs"))
    except Exception:
        return False


def feed_addon_line(folder: str | None = None, now=None) -> str | None:
    """The health line: feed_status_text of the status file; with no status file but the add-on installed, the plain
    'installed but has not started' hint (2026-11-03: the owner's F5 that showed nothing); None = chart mode."""
    st = read_feed_status(folder, now)
    if st:
        return feed_status_text(st)
    return ADDON_NOT_STARTED if addon_installed(folder) else None


def feed_status_text(st: dict | None) -> str | None:
    """One line for the health block / --status: "bars from LE_Feed (no chart), 2 re-subscribes", None in chart mode."""
    if not st:
        return None
    n = st.get("resubs") or 0
    out = f"bars from LE_Feed (no chart), {n} re-subscribe{'' if n == 1 else 's'}"
    if st.get("instruments"):
        out += f" ({', '.join(st['instruments'])})"
    if not st.get("fresh"):
        age = int(st.get("age_s") or 0)
        out += f"; status {age // 60} min old (NinjaTrader closed?)" if age < 7200 else f"; status {age // 3600} h old (NinjaTrader closed?)"
    elif st.get("connected") is False:
        out += "; no price connection"
    return out


# ---------------------------------------------------------------------- is NinjaTrader connected? (2026-11-03)
# NinjaTrader's AT Interface writes outgoing\<connection>.txt (CONNECTED / DISCONNECTED) when a connection CHANGES state
# while the ATI runs, and NinjaTrader empties outgoing\ when it starts: a connection that came up before the ATI wrote its
# file (Connect on startup) can have no file at all. 2026-11-02: outgoing\ held only "Simulation=CONNECTED" while the MFFU
# connection fed live prices and its account traded. So the files are one piece of evidence; the others are NinjaTrader's
# own account list (le_feed\accounts.csv, written from Account.All every minute by LE_Feed / LE_BarFeed: a fresh row of a
# non-Sim account) and live bars (a 1-minute bar closed in the last 4 minutes, or LE_Feed's status "connected=1").
# Display and health only, plus the "every connection DISCONNECTED" refusal (NinjaTraderAdapter._all_disconnected).
SIM_CONNECTION = re.compile(r"^(Simulation|Sim\d*|Playback.*|Replay.*)$", re.I)
LIVE_BAR_S = 240                         # a 1-minute bar that closed this recently = prices are flowing


def live_accounts(folder: str | None = None, now=None) -> list:
    """Non-simulation accounts with a fresh row in le_feed\\accounts.csv (NinjaTrader lists an account while its connection
    is up). [] when the file is missing / stale. Never raises."""
    try:
        from .broker_balance import SIM, read as _bb_read
        r = _bb_read(folder or default_folder(), now=now)
        return sorted(n for n, row in (r.get("rows") or {}).items() if row.get("fresh") and not SIM.match(n))
    except Exception:
        return []


def last_1m_age(folder: str | None = None, now=None, roots=("MNQ", "NQ")) -> int | None:
    """Seconds since the newest le_feed\\<ROOT>_1m.csv bar CLOSED (time = bar open + 60), None = no file / no bar."""
    now = time.time() if now is None else now
    best = None
    for root in roots:
        p = os.path.join(folder or default_folder(), FEED_DIR, f"{root}_1m.csv")
        try:
            with open(p, "rb") as fh:
                fh.seek(0, os.SEEK_END)
                fh.seek(max(0, fh.tell() - 1024))
                tail = fh.read().decode("utf-8", "replace").strip().splitlines()
        except OSError:
            continue
        for ln in reversed(tail):
            head = ln.split(",")[0].strip()
            if head.isdigit():
                best = max(best or 0, int(head))
                break
    return None if best is None else int(now - best - 60)


def connection_files(folder: str | None = None) -> dict:
    """{connection name: CONNECTED | DISCONNECTED} from <NinjaTrader 8>\\outgoing\\<connection>.txt, read straight from disk
    (the adapter's connections() is the cached twin for its poll loop). Position files are skipped; {} = no folder."""
    out = {}
    d = os.path.join(folder or default_folder(), "outgoing")
    try:
        names = os.listdir(d)
    except OSError:
        return out
    for n in names:
        if not n.lower().endswith(".txt") or "_position" in n.lower():
            continue
        try:
            with open(os.path.join(d, n), encoding="utf-8", errors="replace") as fh:
                v = fh.read(64).strip().upper()
        except OSError:
            continue
        if v in ("CONNECTED", "DISCONNECTED"):
            out[n[:-4]] = v
    return out


def connection_view(conns: dict | None, folder: str | None = None, now=None) -> dict:
    """{"connected": True / False / None, "via": [...], "live_accounts": n, "note"}. connected: any CONNECTED file, or a
    live account in accounts.csv, or live bars; False only when there are connection files, every one DISCONNECTED and
    nothing else says connected; None = no file and no evidence (NinjaTrader closed or just started). Never raises."""
    conns = dict(conns or {})
    out = {"connected": None, "via": [], "live_accounts": 0, "note": None}
    try:
        up = [k for k, v in conns.items() if v == "CONNECTED"]
        if up:
            out["via"].append("connection file")
        accts = live_accounts(folder, now)
        out["live_accounts"] = len(accts)
        if accts:
            out["via"].append("live account in accounts.csv")
        age = last_1m_age(folder, now)
        st = read_feed_status(folder, now)
        if (age is not None and -60 <= age <= LIVE_BAR_S) or (st and st.get("fresh") and st.get("connected")):
            out["via"].append("live bars")
        out["connected"] = True if out["via"] else (False if conns else None)
        if out["connected"] and not [k for k in up if not SIM_CONNECTION.match(k)] and (accts or "live bars" in out["via"]):
            shown = ", ".join(f"{k}={v}" for k, v in conns.items()) or "no connection file"
            out["note"] = (f"outgoing shows {shown} only: NinjaTrader writes a connection file when a connection changes "
                           "state, so a connection already up may have none; " +
                           (f"{len(accts)} live account(s) in accounts.csv" if accts else "live bars are arriving") + ": connected")
    except Exception as e:
        out["error"] = e.__class__.__name__
        if out["connected"] is None and conns:
            out["connected"] = any(v == "CONNECTED" for v in conns.values())
    return out


def default_folder() -> str:
    """Documents\\NinjaTrader 8 (NINJATRADER_FOLDER overrides). Follows OneDrive-redirected Documents on Windows."""
    env = os.environ.get("NINJATRADER_FOLDER")
    if env:
        return env
    cands = []
    if os.name == "nt":
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(1024)
            if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0:     # CSIDL_PERSONAL = Documents
                cands.append(os.path.join(buf.value, "NinjaTrader 8"))
        except Exception:
            pass
    home = os.path.expanduser("~")
    cands += [os.path.join(home, "Documents", "NinjaTrader 8"), os.path.join(home, "OneDrive", "Documents", "NinjaTrader 8")]
    for c in cands:
        if os.path.isdir(c):
            return c
    return cands[0]


def folder_ready(folder: str | None = None) -> bool:
    """NinjaTrader's incoming folder exists (AT Interface was enabled once on this Windows user)."""
    try:
        return os.path.isdir(os.path.join(folder or default_folder(), "incoming"))
    except Exception:
        return False


def _et(ts):
    return dt.datetime.fromtimestamp(float(ts), ET)


def _trading_day(ts) -> str:
    return (_et(ts) + dt.timedelta(hours=6)).strftime("%Y-%m-%d")      # 18:00 ET opens the next trading day


def _nonce(n=4) -> str:
    return "".join(secrets.choice("ABCDEFGHJKMNPQRSTUVWXYZ23456789") for _ in range(n))


# ---------------------------------------------------------------------- the adapter
class NinjaTraderAdapter:
    name = "ninjatrader"
    # LiveBot capability flags (engine/live.py reads them with getattr(..., False); paper and Tradovate do not set them)
    loop_tick = True            # LiveBot calls tick() at the start of every poll
    route_stop_moves = True     # LiveBot sends {"side": "modify"} when the model moves the stop (breakeven at 1R)
    route_all_exits = True      # LiveBot routes every model exit (TIME STOP, giveback, ...): a CLOSEPOSITION when flat is harmless
    route_adds = True           # LiveBot routes LIT scale-in adds ({"side": "add"}): a MARKET add, then the OCO bracket's quantity
                                # grows to the whole position (CHANGE qty of the stop and the target; add_to_position)
    kill_flattens_all = True    # the kill switch reaches NinjaTrader even when the model shows no position
    reports_fills = True        # phone notifications: this adapter notifies the real fill (LiveBot does not send its own)

    def __init__(self, cfg: dict | None = None, readonly: bool = False, clock=None):
        cfg = dict(cfg or {})
        self.cfg = cfg
        self.readonly = readonly                       # status / checks only: never writes, never withdraws
        p = cfg.get("params") or {}
        self.sym = cfg.get("sym", "NQ")
        self.flat_mod = int(p.get("flat_mod", 955))
        self.session_from = _session_from(cfg)          # first ET minute an entry may go in (LIT 02:00, the engine 08:00)
        self.all_hours = _all_hours(cfg)                # LIT all_hours: sessions are CME trading days 18:00 -> 17:00
        self.max_micros = min(MAX_MICROS_HARD, int(p.get("max_micros", cfg.get("max_micros", MAX_MICROS_HARD))))
        mode = str(cfg.get("nt_contract") or "micro").lower()
        self.contract_mode = mode if mode in ("micro", "auto") else "auto"   # micro: MNQ only | auto: 10+ micros as NQ minis
        self.account = resolve_account(cfg)
        self.folder = cfg.get("nt_folder") or default_folder()
        self.incoming = os.path.join(self.folder, "incoming")
        self.outgoing = os.path.join(self.folder, "outgoing")
        # "move" (default since the 2026-10-20 rehearsal): the order file is written in le_outbox\ and moved into incoming\
        # whole. "direct" creates the file in incoming\ and then writes it: in between, NinjaTrader's folder watcher can read
        # an EMPTY file and delete it, so the order (a bracket!) is lost silently (seen in the rehearsal under load: an entry
        # filled with no stop / target at the broker for 94 minutes). nt_write_mode "direct" keeps the old way.
        self.write_mode = "direct" if cfg.get("nt_write_mode") == "direct" else "move"
        # several accounts on one bot (engine/multi_account.py): each adapter's order files carry its own tag, so two
        # accounts writing in the same millisecond never collide ("" = the single-account names, unchanged)
        self.file_tag = re.sub(r"[^A-Za-z0-9_]", "", str(cfg.get("nt_file_tag") or ""))[:24]
        self.inst_override = {"micro": cfg.get("nt_instrument"), "mini": cfg.get("nt_instrument_mini")}
        # the guide says CLOSEPOSITION wants "the instrument name including the exchange name": if NinjaTrader ignores
        # "CLOSEPOSITION;Sim101;MNQ 12-26" on your install (--sim-roundtrip step 3 fails), set nt_close_suffix " Globex"
        self.close_suffix = str(cfg.get("nt_close_suffix") or "")
        self.ack_wait = float(cfg.get("nt_ack_wait_s", 4.0))         # NinjaTrader must pick a file up within this
        self.fill_wait = float(cfg.get("nt_fill_wait_s", 6.0))       # ... and report the market entry fill within this
        self.verify_wait = float(cfg.get("nt_verify_wait_s", 4.0))   # ... and the bracket / the flat position within this
        self.pending_timeout = float(cfg.get("nt_pending_timeout_s", 45.0))
        self.state_path = cfg.get("nt_state_path") or STATE_PATH
        self.audit_path = cfg.get("nt_audit_log") or AUDIT_PATH
        self.clock = clock or time.time
        self._sleep = time.sleep                       # the self-test swaps in a simulated NinjaTrader here
        self._alert_fn = None                          # None = the bot's phone alerts (guard kind); the self-test captures
        # phone notices of a SUB-account's adapter (owner 2026-11-20: entry + exit alerts on every account, the moment NinjaTrader
        # fills): {"account": its label, "suffix": ":acctb" / ":<id>", "nm": the owner's name} set by its route (engine/account_b,
        # engine/rapid, engine/multi_account) for the real bot only; None = only the bot's own adapter (STATE_PATH) notifies
        self.push_as = None
        self.lock = threading.RLock()
        self.trace = deque(maxlen=300)
        self.legs: list = []                           # open brackets we placed (one per instrument)
        self.withdrawn: list = []                      # entries we withdrew unprocessed: watched in case they ran anyway
        self.history = deque(maxlen=20)
        self.unparsed: dict = {}                       # outgoing file -> text we could not parse (logged once each)
        self.last_error = None
        self.killed = False
        self._flat_tries: dict = {}
        self._outside_flat: dict = {}
        self._cont_warned = None
        self.watch: list = []                          # retired legs with an order that may still fill (late add / slow cancel)
        # S1 2026-11-15: entry files sent this trading day, a hard cap independent of the bot's own guards (dup_entry,
        # account B's 2 a day, BLITZ's 6 a day): a looping bug can never fire entry after entry. nt_max_entries_day, default 8
        self.entries_day: dict = {"day": None, "n": 0}
        self.max_entries_day = int(cfg.get("nt_max_entries_day", MAX_ENTRIES_DAY))
        # night-risk 2026-11-18: every order file counted (engine/msg_throttle.py): runaway alarm ON; the entry block is OFF until
        # `python -X utf8 -m engine.msg_throttle --block-on`. Stops / cancels / closes / flatten are never throttled.
        try:
            from .msg_throttle import Throttle, path_for
            self.throttle = None if readonly else Throttle(cfg.get("nt_msg_path") or path_for(self.state_path), self.account, cfg)
        except Exception:
            self.throttle = None
        # NinjaTrader restart (it wipes outgoing\\ when it starts): a position file / an order file of an open bracket we had
        # seen that is gone again. Never read as flat: new entries / adds are refused and the owner is alerted until the
        # position file is written again or the owner confirms (python -m engine.ninjatrader --confirm-reset)
        self.seen_pos: dict = {}                       # outgoing position file name -> its last {"side", "qty", "instrument"}
        self.nt_reset = None                           # {"since", "files", "insts"} while the reset is unresolved
        self.reset_ok_path = cfg.get("nt_reset_ok_path") or os.path.join(os.path.dirname(self.state_path), RESET_OK_NAME)
        self._conn_alert_at = 0.0
        self._seq = 0
        self.sim = is_sim(self.account)
        self.env = "demo" if self.sim else "live"      # LiveBot._remember: memory source paper / live
        self.state_problem = None                      # the state file was unreadable: entries blocked until the account is flat
        self._global_kill = False                      # True only inside kill(scope="global"): FLATTENEVERYTHING may be written
        self.disabled = self._live_gate()
        self.lock_problem = None if self.disabled else self._acquire_lock()
        if self.lock_problem:
            self.disabled = self.lock_problem
        self._restore()
        if not readonly and not self.lock_problem:
            self._sweep_stale_oifs(max_age=10.0)
            self._sweep_outbox(max_age=10.0)
        fs = self.folder_status()
        self._log("system", f"NinjaTrader adapter: account {self.account} ({'SIM' if self.sim else 'LIVE ACCOUNT'}), "
                            f"{' + '.join(self._instruments().values()) if self.contract_mode == 'auto' else self._instruments()['micro']}, "
                            f"folder {self.folder}{'' if fs['incoming'] else ' (incoming NOT FOUND)'}, "
                            + (f"DISABLED ({self.disabled})" if self.disabled else "ready")
                            + (f", restored {len(self.legs)} open bracket(s)" if self.legs else ""))

    # ------------------------------------------------------------------ plumbing
    def _live_gate(self):
        if not self.account or any(c in self.account for c in ";\r\n"):
            return "account name missing or invalid"
        if self.sim:
            return None
        if not self.cfg.get("armed"):
            return f"LIVE account {self.account} refused: start config is not armed"
        if (self.cfg.get("confirm") or "").strip() != LIVE_PHRASE:
            return f"LIVE account {self.account} refused: confirm phrase missing (type exactly '{LIVE_PHRASE}')"
        if os.environ.get(LIVE_ENV, "") != "1":
            return f"LIVE account {self.account} refused: start the server with {LIVE_ENV}=1"
        if self.account not in allowed_accounts(self.cfg.get("nt_allow_path")):
            return (f"LIVE account {self.account} refused: not in the account allowlist (run once: python -m engine.ninjatrader "
                    f"--allow-account \"{self.account}\")")
        return None

    def _acquire_lock(self):
        """One bot process per NinjaTrader account: an OS lock on <NinjaTrader 8>\\le_locks\\<account>.lock, held for the
        life of the process (the OS releases it when the process exits or crashes, so it never goes stale). Several adapters
        in ONE process share it (a restarted LiveBot; LIT and account B lock different names). None = ours, else why not."""
        if self.readonly or not os.path.isdir(self.folder) or self.cfg.get("nt_lock") is False:
            return None
        d = os.path.join(self.folder, LOCK_DIR)
        path = os.path.join(d, re.sub(r"[^A-Za-z0-9_.-]", "_", self.account) + ".lock")
        key = os.path.normcase(os.path.abspath(path))
        if key in _LOCKS:
            self._lock_key = key
            return None
        try:
            os.makedirs(d, exist_ok=True)
            fh = open(path, "a+")
        except OSError as e:
            return f"account lock {path} could not be opened ({e.__class__.__name__}: {e})"
        try:
            if os.name == "nt":
                import msvcrt
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            try:
                with open(path + ".info", encoding="utf-8") as f2:
                    who = json.load(f2)
            except Exception:
                who = {}
            return (f"another bot process already trades account {self.account} (pid {who.get('pid', '?')}, started "
                    f"{who.get('started', '?')}, folder {who.get('root', '?')}): this copy sends NO orders. Stop the other "
                    "copy first (scripts\\stop_bot.ps1), then start again")
        _LOCKS[key] = fh
        self._lock_key = key
        try:
            with open(path + ".info", "w", encoding="utf-8") as f2:
                json.dump({"pid": os.getpid(), "started": dt.datetime.now(ET).strftime("%Y-%m-%d %H:%M:%S ET"), "root": ROOT,
                           "account": self.account}, f2)
        except OSError:
            pass
        return None

    def release_lock(self):
        """The bot stopped (LiveBot.stop): give the account back so a Sim check or another start can take it. Never raises."""
        key = getattr(self, "_lock_key", None)
        fh = _LOCKS.pop(key, None) if key else None
        self._lock_key = None
        if fh is None:
            return
        try:
            if os.name == "nt":
                import msvcrt
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        try:
            fh.close()
        except OSError:
            pass

    def _log(self, kind, text, **kw):
        self.trace.append({"t": int(self.clock()), "type": kind, "text": text, **kw})
        try:
            from .live import BOT
            BOT._log(kind, text, **kw)
        except Exception:
            print(f"[ninjatrader] {kind}: {text}")

    def _alert(self, text):
        try:
            if self._alert_fn is not None:
                self._alert_fn(text)
                return
            from .live import BOT
            BOT._alert("⚠️ NinjaTrader: " + text, "guard")
            self._push(lambda P: P.text_payload("PC", "risk", "NinjaTrader needs a look", text,
                                                key=f"risk:{int(self.clock()) // 60}:{abs(hash(text)) % 10**6}"))
        except Exception:
            pass

    # ------------------------------------------------------------------ phone notifications (engine/push.py)
    def _push_account(self):
        if self.sim:
            return self.account                  # "Sim101" (a Sim account is never a phone alert: engine/notify.real_trade)
        if self.push_as:
            return str(self.push_as.get("account") or self.account)
        try:
            from . import push
            from .lab_adapter import live_model
            return push.account_label(live_model(), "live")
        except Exception:
            return "MFFU 50K"

    def _push(self, make):
        """Send one phone notification (background thread, once per key). Only the real bot: never the self-test or a
        harness with its own state file. Never raises."""
        pa = self.push_as if isinstance(self.push_as, dict) else None
        if self._alert_fn is not None or self.readonly or (self.state_path != STATE_PATH and pa is None):
            return
        try:
            from . import push
            p = make(push)
            if pa is not None and p.get("kind") in ("fill", "outcome"):    # a sub-account: its own key (one alert per account)
                p["key"] = f"{p['key']}{pa.get('suffix') or ''}"
                p["tag"] = f"{p.get('tag', '')}{(pa.get('suffix') or '').replace(':', '-')}"
                for k in ("nm", "url"):
                    if pa.get(k):
                        p[k] = pa[k]
            elif pa is not None:
                return                               # its route sends its own other notices
            push.pc_notify(p)
        except Exception:
            pass

    def _push_fill(self, lg):
        """ENTRY: NinjaTrader reported the entry fill."""
        inst = lg["instrument"].split(" ")[0]
        if lg.get("who"):                    # ATLAS + Zlarior on ONE account (engine/combo50k.py): say which bot traded the 50K
            def mk(P):
                from .combo50k import entry_text
                p = P.entry_payload(self._push_account(), "LONG" if lg["dir"] == 1 else "SHORT", lg["filled"], lg["entry_t"],
                                    src="pc", contract=inst, entry=lg["fill_px"], stop=lg.get("stop0") or lg["stop"],
                                    target=lg["target"], who=lg["who"])
                p["title"] = entry_text(lg["who"], "LONG" if lg["dir"] == 1 else "SHORT")
                return p
            self._push(mk)
            return
        self._push(lambda P: P.entry_payload(self._push_account(), "LONG" if lg["dir"] == 1 else "SHORT", lg["filled"], lg["entry_t"],
                                             src="pc", contract=inst, entry=lg["fill_px"], stop=lg.get("stop0") or lg["stop"],
                                             target=lg["target"]))

    def _push_exit(self, lg, name, x):
        """OUTCOME: the bracket closed the trade (stop or target filled at NinjaTrader): $ from the real fills, before costs."""
        u = lg["instrument"].upper()
        pv = 2.0 if u.startswith("MNQ") else 5.0 if u.startswith("MES") else 20.0 if u.startswith("NQ") else 50.0
        fill, ex = float(lg["fill_px"] or 0), float(x.get("avg") or 0)
        usd = (ex - fill) * lg["dir"] * int(x.get("filled") or lg["bracket_qty"] or 0) * pv
        reason = "TARGET" if name == "TARGET" else ("BE" if abs(ex - fill) <= 1.0 else "STOP")
        if lg.get("who"):                    # the combo (engine/combo50k.py): "ATLAS on Zlarior 50K: LONG closed"
            def mk(P):
                p = P.outcome_payload(self._push_account(), "LONG" if lg["dir"] == 1 else "SHORT", reason, usd,
                                      lg["entry_t"], int(self.clock()), src="pc", exit_px=ex, qty=x.get("filled"), who=lg["who"])
                p["title"] = f"{lg['who']}: {'LONG' if lg['dir'] == 1 else 'SHORT'} closed"
                return p
            self._push(mk)
            return
        self._push(lambda P: P.outcome_payload(self._push_account(), "LONG" if lg["dir"] == 1 else "SHORT", reason, usd,
                                               lg["entry_t"], int(self.clock()), src="pc", exit_px=ex, qty=x.get("filled")))

    def _risk(self, text, alert=False):
        self.last_error = text
        self._log("risk", "NinjaTrader: " + text)
        if alert:
            self._alert(text)

    def _wait(self, cond, timeout, step=0.05) -> bool:
        """Poll cond() every `step` for up to `timeout` (an iteration count, so a simulated sleep stays bounded)."""
        for _ in range(max(1, int(timeout / step))):
            try:
                if cond():
                    return True
            except Exception:
                pass
            self._sleep(step)
        try:
            return bool(cond())
        except Exception:
            return False

    def folder_status(self) -> dict:
        return {"folder": self.folder, "exists": os.path.isdir(self.folder), "incoming": os.path.isdir(self.incoming),
                "outgoing": os.path.isdir(self.outgoing)}

    def _instruments(self) -> dict:
        today = _et(self.clock()).date()
        return {"micro": self.inst_override["micro"] or nt_instrument(MICRO.get(self.sym, "MNQ"), today),
                "mini": self.inst_override["mini"] or nt_instrument(MINI.get(self.sym, "NQ"), today)}

    def _our_instruments(self) -> list:
        insts = self._instruments()
        out = [insts["micro"]] + ([insts["mini"]] if self.contract_mode == "auto" else [])
        for leg in self.legs:
            if leg["instrument"] not in out:
                out.append(leg["instrument"])
        return out

    # ------------------------------------------------------------------ writing order instruction files
    def _audit(self, name, lines):
        try:
            os.makedirs(os.path.dirname(self.audit_path), exist_ok=True)
            stamp = _et(time.time()).strftime("%Y-%m-%d %H:%M:%S")
            with open(self.audit_path, "a", encoding="utf-8") as fh:
                for ln in lines:
                    fh.write(f"{stamp} ET  {self.account}  {name}  {ln}\n")
        except Exception:
            pass

    def _write_oif(self, lines: list, label: str) -> dict:
        if self.readonly:
            return {"ok": False, "error": "REFUSED: read-only adapter"}
        if not os.path.isdir(self.incoming):
            msg = (f"NinjaTrader folder not found: {self.incoming}. Is NinjaTrader 8 installed for this Windows user? "
                   "Set nt_folder (or NINJATRADER_FOLDER) if Documents is elsewhere.")
            self.last_error = msg
            self._log("error", msg)
            return {"ok": False, "error": msg}
        for ln in lines:
            bad = validate_line(ln) or self._scope_problem(ln)
            if bad:                                  # a bug guard: a malformed line is never handed to NinjaTrader
                msg = f"internal: refused to write invalid OIF line {ln!r}: {'; '.join(bad)}"
                self.last_error = msg
                self._log("error", msg)
                return {"ok": False, "error": msg}
        data = ("\r\n".join(lines) + "\r\n").encode("ascii", errors="strict")
        err = None
        for attempt in range(3):
            self._seq += 1
            name = f"oif_le_{self.file_tag}{time.time_ns() // 1_000_000}_{self._seq}.txt"
            path = os.path.join(self.incoming, name)
            try:
                if self.write_mode == "move":
                    # "Move or directly write OIF files to the incoming folder" (help guide): written next door, then moved in whole
                    box = os.path.join(self.folder, "le_outbox")
                    os.makedirs(box, exist_ok=True)
                    tmp = os.path.join(box, name)
                    with open(tmp, "wb") as fh:
                        fh.write(data)
                    _publish(tmp, path)          # never over an existing file (a name reused by another process)
                else:
                    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0))
                    try:
                        os.write(fd, data)                   # one write, then close (the file exists empty before it)
                    finally:
                        os.close(fd)
                self._audit(name, lines)
                self._log("broker", f"NinjaTrader {label} -> {name}: " + " | ".join(lines))
                self._note_msgs(lines)
                return {"ok": True, "file": name, "path": path, "lines": list(lines)}
            except FileExistsError as e:         # that name is taken in incoming\: never overwrite it, take a new name
                err = e
                if self.write_mode == "move":
                    try:
                        os.remove(os.path.join(self.folder, "le_outbox", name))
                    except OSError:
                        pass
                self._log("warn", f"NinjaTrader order file name {name} already in incoming (another writer?): new name")
            except OSError as e:
                err = e
                time.sleep(0.2 * (attempt + 1))
        msg = f"could not write the order file ({err.__class__.__name__}: {err})"
        self.last_error = msg
        self._log("error", "NinjaTrader " + msg)
        return {"ok": False, "error": msg}

    def _note_msgs(self, lines):
        """Count one written order file (engine/msg_throttle); a new trip = critical alert + one Board event. Never raises."""
        th = getattr(self, "throttle", None)
        if th is None:
            return
        try:
            rec = th.note(lines, self.clock())
            if not rec:
                return
            from .msg_throttle import say
            title, body = say(rec)
            self._risk(f"{title} {body}", alert=True)
            if self._alert_fn is None and os.path.dirname(os.path.abspath(self.state_path)) == os.path.dirname(STATE_PATH):
                from .board_events import emit
                emit("risk_alert", "", f"{title} {body}"[:300], {"what": "throttle", "code": rec["code"], "last4": rec.get("acct4"),
                                                                 "block": bool(rec.get("block"))})
        except Exception:
            pass

    def _scope_problem(self, line: str) -> list:
        """Account scope of one OIF line (pre-launch audit 2026-10-25): PLACE / CLOSEPOSITION / REVERSEPOSITION must name this
        adapter's own account; CANCEL / CHANGE only our own order ids (LE...); FLATTENEVERYTHING / CANCELALLORDERS (they act
        on EVERY account and connection in NinjaTrader) only inside the owner's global kill. [] = fine."""
        f = line.split(";")
        cmd = f[0]
        if cmd in ("PLACE", "CLOSEPOSITION", "REVERSEPOSITION") and f[1] != self.account:
            return [f"account {f[1]!r} is not this adapter's account {self.account!r}"]
        if cmd in ("CANCEL", "CHANGE") and not f[10].startswith("LE"):
            return [f"order id {f[10]!r} is not one of the bot's (LE...)"]
        if cmd in ("FLATTENEVERYTHING", "CANCELALLORDERS") and not self._global_kill:
            return [f"{cmd} acts on every account: only the owner's global kill may send it"]
        if cmd == "CLOSESTRATEGY":
            return ["CLOSESTRATEGY is never used by the bot"]
        return []

    def _sweep_outbox(self, max_age: float):
        """A crash between writing le_outbox\\<name> and moving it into incoming\\ leaves the file in le_outbox: it was never
        published (NinjaTrader never saw it), so it is deleted, never moved in late."""
        box = os.path.join(self.folder, "le_outbox")
        try:
            names = os.listdir(box)
        except OSError:
            return
        for n in names:
            if not n.startswith(f"oif_le_{self.file_tag}"):
                continue
            p = os.path.join(box, n)
            try:
                if time.time() - os.path.getmtime(p) >= max_age:
                    os.remove(p)
                    self._log("warn", f"NinjaTrader: removed {n} from le_outbox (a write interrupted before it was published; "
                                      "it never reached NinjaTrader)")
            except OSError:
                continue

    def _withdraw(self, path) -> bool:
        """Delete our unprocessed file so NinjaTrader can never run it late. True = we removed it (it did not run)."""
        try:
            os.remove(path)
            return True
        except OSError:
            return False                 # gone already (NinjaTrader took it at the last moment) or locked (taking it now)

    def _send_lines(self, lines: list, label: str) -> dict:
        w = self._write_oif(lines, label)
        if not w["ok"]:
            return w
        if self._wait(lambda: not os.path.exists(w["path"]), self.ack_wait):
            return {**w, "picked_up": True}
        if self._withdraw(w["path"]):
            msg = (f"NinjaTrader did not pick up {w['file']} within {self.ack_wait:.0f}s, so it was withdrawn and NOT executed. "
                   "Is NinjaTrader running, connected, with Tools > Options > Automated trading interface > AT Interface ticked?")
            self.last_error = msg
            self._log("error", msg)
            return {**w, "ok": False, "picked_up": False, "withdrawn": True, "error": msg}
        return {**w, "picked_up": True, "late": True}

    def _sweep_stale_oifs(self, max_age: float):
        """Withdraw any of our order files NinjaTrader left unprocessed (it was off): they must never run late."""
        try:
            names = os.listdir(self.incoming)
        except OSError:
            return
        for n in names:
            if not n.startswith("oif_le_"):
                continue
            p = os.path.join(self.incoming, n)
            try:
                age = time.time() - os.path.getmtime(p)
            except OSError:
                continue
            if age >= max_age and self._withdraw(p):
                self._risk(f"withdrew {n}: NinjaTrader had not processed it for {age:.0f}s (NinjaTrader off or AT Interface disabled?)")

    # ------------------------------------------------------------------ reading NinjaTrader's reports
    def _listing(self) -> list:
        try:
            return os.listdir(self.outgoing)
        except OSError:
            return []

    def _unparsable(self, name, raw):
        if name not in self.unparsed:
            self.unparsed[name] = (raw or "")[:120]
            self._log("warn", f"NinjaTrader outgoing file {name} not understood: {(raw or '')[:80]!r} (ignored)")

    def read_order(self, order_id: str, listing: list | None = None):
        """{"state", "filled", "avg", "mtime"} from outgoing/<ORDER ID>.txt; None when NinjaTrader has not written it."""
        path = os.path.join(self.outgoing, f"{order_id}.txt")
        raw = _read_text(path)
        if raw is None:                  # defensive: a file whose name carries our id in some other way
            for n in (listing if listing is not None else self._listing()):
                if order_id in n and n.lower().endswith(".txt") and "_position" not in n.lower():
                    path = os.path.join(self.outgoing, n)
                    raw = _read_text(path)
                    break
        if raw is None:
            return None
        st = parse_order_state(raw)
        if st is None:
            self._unparsable(os.path.basename(path), raw)
            return None
        if not st["known"]:
            self._unparsable(os.path.basename(path) + " (state)", raw)
        try:
            st["mtime"] = os.path.getmtime(path)
        except OSError:
            st["mtime"] = None
        return st

    def positions(self) -> dict:
        """Every position NinjaTrader reports for our account (outgoing/*_<account>_Position.txt)."""
        suffix = f"_{self.account.lower()}_position.txt"
        out = []
        for n in self._listing():
            if not n.lower().endswith(suffix):
                continue
            path = os.path.join(self.outgoing, n)
            raw = _read_text(path)
            pos = parse_position(raw)
            if pos is None:
                if raw is not None:
                    self._unparsable(n, raw)
                continue
            inst = n[:-len(suffix)]
            if not inst or "_" in inst:
                continue                 # another account whose name ends in ours ("X_Sim101"): instruments have no "_"
            try:
                mtime = os.path.getmtime(path)
            except OSError:
                mtime = None
            out.append({"instrument": inst, **pos, "file": n, "mtime": mtime})
        return {"ok": True, "account": self.account, "positions": out}

    def position_for(self, instrument: str):
        """The position file of one instrument ('MNQ 12-26' matches 'MNQ 12-26 Globex_Sim101_Position.txt' and
        'MNQ DEC26 Globex_Sim101_Position.txt'); None = no file (which never proves flat: NinjaTrader wipes outgoing\\ when
        it restarts)."""
        for p in self.positions()["positions"]:
            if same_instrument(p["instrument"], instrument):
                return p
        return None

    def _all_disconnected(self, conn: dict) -> bool:
        """Every connection file says DISCONNECTED (the old rule) AND NinjaTrader does not list this bot's own account as live
        in le_feed\\accounts.csv. A connection file is written only when a connection changes state (connection_view), so a
        stale "Simulation=DISCONNECTED" next to a live MFFU connection with no file must not refuse the MFFU account's
        entry. Simulation accounts keep the old rule. Any error -> the old rule."""
        if not (conn and all(v == "DISCONNECTED" for v in conn.values())):
            return False
        try:
            if SIM_ACCOUNT.match(str(self.account or "")):
                return True
            return str(self.account) not in live_accounts(self.folder, self.clock())
        except Exception:
            return True

    def connections(self) -> dict:
        """{connection name: CONNECTED | DISCONNECTED} from outgoing/<connection>.txt. NinjaTrader's outgoing folder also
        holds one <order id>.txt per order it has seen, and every call used to open all of them (2026-10-26: 604 file
        reads per poll with 300 orders, times two adapters; on the owner's OneDrive-synced Documents every open goes
        through the sync filter). A file is read again only when its size or modified time changed (_CONN_SEEN, shared
        by every adapter of this process); the answer is the same."""
        out = {}
        try:
            entries = list(os.scandir(self.outgoing))
        except OSError:
            entries = []
        live = set()
        for e in entries:
            n = e.name
            if not n.lower().endswith(".txt") or "_position" in n.lower():
                continue
            try:
                st = e.stat()
                key = (st.st_mtime_ns, st.st_size)
            except OSError:
                continue
            live.add(e.path)
            with _CONN_LOCK:
                hit = _CONN_SEEN.get(e.path)
            if hit is not None and hit[0] == key:
                v = hit[1]
            else:
                raw = _read_text(e.path)
                if raw is None:
                    continue
                v = raw.strip().upper()
                with _CONN_LOCK:
                    _CONN_SEEN[e.path] = (key, v)
            if v in ("CONNECTED", "DISCONNECTED"):
                out[n[:-4]] = v
        pre = os.path.join(self.outgoing, "")
        with _CONN_LOCK:
            for p in [p for p in _CONN_SEEN if p.startswith(pre) and p not in live]:
                _CONN_SEEN.pop(p, None)             # a file NinjaTrader removed (its restart wipes outgoing\)
        return out

    def _flat_since(self, instrument, since):
        """True when NinjaTrader's position file says FLAT and was written at/after `since` (an older FLAT proves nothing)."""
        p = self.position_for(instrument)
        return bool(p and p["side"] == "FLAT" and (since is None or (p.get("mtime") or 0) >= since - 0.001))

    # ------------------------------------------------------------------ gates
    def _gate(self, kind: str):
        if self.disabled:
            return {"ok": False, "error": "REFUSED: " + self.disabled}
        if self.readonly:
            return {"ok": False, "error": "REFUSED: read-only adapter"}
        if kind == "entry":
            if self.killed:
                return {"ok": False, "error": "REFUSED: kill switch is engaged"}
            try:
                from .live import BOT
                if getattr(BOT, "kill", False):
                    return {"ok": False, "error": "REFUSED: kill switch is engaged"}
            except Exception:
                pass
            th = getattr(self, "throttle", None)          # engine/msg_throttle: only when its BLOCK is switched on (OFF by default)
            blk = th.entry_block(self.clock()) if th is not None else None
            if blk:
                return {"ok": False, "error": "REFUSED: " + blk}
            e = _et(self.clock())
            mod = e.hour * 60 + e.minute
            cut = self._flat_today(e, entry=True)
            if self.all_hours:                # trading-day order: Sun 18:00 opens Monday; the 17:00-18:00 halt is closed
                wd = e.weekday()
                shut = wd == 5 or (wd == 6 and mod < 1080) or (wd == 4 and mod >= 1020) or 1020 <= mod < 1080
                refuse = shut or _tday(mod) >= _tday(cut) or _tday(mod) < _tday(self.session_from)
            else:
                refuse = e.weekday() >= 5 or mod >= cut or mod < self.session_from
            if refuse:
                return {"ok": False, "error": f"REFUSED: entry outside the session ({e:%a %H:%M} ET; entries "
                                              f"{self.session_from // 60:02d}:{self.session_from % 60:02d}-"
                                              f"{cut // 60:02d}:{cut % 60:02d} ET on weekdays"
                                              + (", CME early close today" if cut < self.flat_mod else "") + ")"}
            try:                              # 2026-10-29: a CME full-closure date (Christmas, New Year) never takes an entry
                from .cme_calendar import full_closure
                if full_closure(_trading_day(self.clock())):
                    return {"ok": False, "error": f"REFUSED: {_trading_day(self.clock())} is a CME holiday (no session)"}
            except Exception:
                pass
        return None

    def _flat_today(self, e, entry=False) -> int:
        """Flat time (ET minute) for the date of `e`: flat_mod, or on a CME early-close day (engine/lit_live.early_close)
        5 minutes before the halt, so nothing is held into it; entries stop 15 minutes before the halt (LIT report ch.28)."""
        try:
            from .lit_live import early_close
            ec = early_close(e.date().isoformat())
        except Exception:
            ec = None
        if ec is None or e.hour * 60 + e.minute >= 1080:
            return self.flat_mod
        return min(self.flat_mod, ec - (15 if entry else 5))

    def _split(self, action: dict) -> dict:
        qty = int(action.get("qty") or 0)
        if qty < 1:
            return {"ok": False, "error": "REFUSED: qty < 1"}
        if "minis" in action or "micros" in action:
            minis, micros = int(action.get("minis") or 0), int(action.get("micros") or 0)
        elif self.contract_mode == "auto":
            minis, micros = qty // 10, qty % 10
        else:
            minis, micros = 0, qty
        total = minis * 10 + micros
        if minis > MAX_MINIS:
            return {"ok": False, "error": f"REFUSED: {minis} minis exceeds the {MAX_MINIS}-mini cap"}
        if total > self.max_micros or total > MAX_MICROS_HARD:
            return {"ok": False, "error": f"REFUSED: {total} micros exceeds max_micros {self.max_micros}"}
        if total < 1:
            return {"ok": False, "error": "REFUSED: nothing to trade"}
        return {"ok": True, "minis": minis, "micros": micros}

    # ------------------------------------------------------------------ orders
    def place_bracket(self, action: dict) -> dict:
        g = self._gate("entry")
        if g:
            return g
        sp = self._split(action)
        if not sp["ok"]:
            return sp
        if not action.get("stop") or not action.get("target"):
            return {"ok": False, "error": "REFUSED: a bracket needs stop and target"}
        side = "BUY" if action.get("side") == "buy" else "SELL"
        d = 1 if side == "BUY" else -1
        stop, target = _tick(action["stop"]), _tick(action["target"])
        ref = action.get("entry")
        if ref and not ((ref - stop) * d > 0 and (target - ref) * d > 0):
            return {"ok": False, "error": f"REFUSED: stop {stop} / target {target} on the wrong side of entry {ref} for a {side}"}
        if (target - stop) * d <= 0:
            return {"ok": False, "error": "REFUSED: target is not beyond the stop"}
        open_legs = [lg for lg in self.legs if lg["status"] in OPEN_STATUSES]
        if open_legs:
            return {"ok": False, "error": f"REFUSED: the bracket of the entry at {_et(open_legs[0]['entry_t']):%H:%M} ET is still open"}
        if self.nt_reset:
            return {"ok": False, "error": "REFUSED: " + self._reset_text()}
        if self.state_problem and not self._state_problem_resolved():
            return {"ok": False, "error": "REFUSED: " + self.state_problem["text"] + ": no new entry until NinjaTrader shows the "
                                                     "account FLAT or you run python -m engine.ninjatrader --confirm-reset"}
        day = _trading_day(self.clock())
        if self.entries_day.get("day") != day:
            self.entries_day = {"day": day, "n": 0}
        if self.entries_day["n"] >= self.max_entries_day:
            self._risk(f"{self.entries_day['n']} entries already sent on {self.account} this trading day (hard cap "
                       f"{self.max_entries_day}): entry refused. A bug repeating entries? Check the Live page log.", alert=True)
            return {"ok": False, "error": f"REFUSED: {self.max_entries_day} entries already sent today on {self.account} (hard cap)"}
        insts = self._instruments()
        plan = [(insts["mini"], sp["minis"], "N"), (insts["micro"], sp["micros"], "M")]
        plan = [x for x in plan if x[1] > 0]
        bad = self._contract_mismatch([inst for inst, _, _ in plan])
        if bad:
            self._risk(bad, alert=True)
            return {"ok": False, "error": "REFUSED: " + bad}
        for inst, _, _ in plan:
            p = self.position_for(inst)
            if p and p["side"] != "FLAT":
                return {"ok": False, "error": f"REFUSED: NinjaTrader shows {p['side']} {p['qty']} {inst} on {self.account}: not adding to it"}
        conn = self.connections()
        if self._all_disconnected(conn):
            return {"ok": False, "error": f"REFUSED: NinjaTrader reports every connection DISCONNECTED ({', '.join(conn)})"}
        ts = int(action.get("entry_t") or self.clock())
        tag = _nonce()
        legs = []
        for inst, qty, kind in plan:
            base = f"LE{ts}{tag}{kind}"
            legs.append({"instrument": inst, "qty": qty, "side": side, "dir": d, "entry_t": ts, "stop": stop, "target": target,
                         "entry_id": base + "E", "stop_id": base + "S", "target_id": base + "T", "oco": base + "O",
                         "status": "entry_sent", "filled": 0, "fill_px": None, "fill_mtime": None, "bracket_qty": 0, "stop0": stop,
                         "sent_at": self.clock(), "ref": float(ref) if ref else None,
                         **({"who": str(action["who"])[:40]} if action.get("who") else {})})   # engine/combo50k: which bot (only while on)
        # S1 2026-11-15, write-ahead: the legs are saved BEFORE the entry file goes out, so a crash between the order file
        # and the state save restores an "entry_sent" leg (the next tick finds its fill and places the stop / target)
        # instead of a position no bracket of the bot explains
        self.legs = legs
        self.entries_day["n"] += 1                     # counted before the file goes out (a crash right after still counts)
        self._save()
        r = self._send_lines([place_line(self.account, lg["instrument"], side, lg["qty"], "MARKET", order_id=lg["entry_id"])
                              for lg in legs], "ENTRY")
        if not r["ok"]:
            self.legs = []
            if r.get("withdrawn"):
                self.withdrawn += [{"entry_id": lg["entry_id"], "leg": lg, "t": self.clock()} for lg in legs]
            self._save()
            return {"ok": False, "adapter": self.name, "account": self.account, "error": r["error"], "oif": r.get("file")}
        self._save()
        self._wait(lambda: all(self._entry_settled(lg) for lg in legs), self.fill_wait)
        out, errors, locked = [], [], None
        for lg in legs:
            st = self.read_order(lg["entry_id"])
            self._note_fill(lg, st)
            gap = self._fill_gap(lg)
            if gap is not None:
                fl = self._gap_flatten(lg, gap)
                errors.append(f"{lg['instrument']}: fill {gap:.0f} pts from the chart price, flattened"
                              + ("" if fl["ok"] else " (flatten NOT confirmed)"))
                out.append({"instrument": lg["instrument"], "qty": lg["qty"], "ok": False, "filled": lg["filled"],
                            "fill_px": lg["fill_px"], "note": "fill gap: flattened"})
                continue
            if lg["filled"] > 0:
                res = self._protect(lg)
                out.append({"instrument": lg["instrument"], "qty": lg["qty"], "filled": lg["filled"], "fill_px": lg["fill_px"], **res})
                if not res["ok"]:
                    errors.append(f"{lg['instrument']}: {res.get('error')}")
            elif st and st["state"] in DEAD:
                lg["status"] = "rejected"
                why = nt_reject_text(self, ts) if st["state"] == "REJECTED" else None    # an MFFU lock: engine/lifecycle.py
                locked = locked or why
                errors.append(f"{lg['instrument']}: entry {st['state']}" + (f" ({why})" if why else ""))
                out.append({"instrument": lg["instrument"], "qty": lg["qty"], "ok": False, "state": st["state"]})
            else:
                lg["status"] = "pending"
                note = "fill not reported yet: the stop and target go in the moment NinjaTrader reports it (next poll)"
                errors.append(f"{lg['instrument']}: {note}")
                out.append({"instrument": lg["instrument"], "qty": lg["qty"], "ok": False, "state": st and st["state"], "note": note})
        self._retire([lg for lg in legs if lg["status"] == "rejected"], "entry rejected")
        self._save()
        ok = not errors
        return {"ok": ok, "adapter": self.name, "account": self.account, "env": self.env, "side": side,
                "legs": out, **({} if ok else {"error": "; ".join(errors)}), **({"locked": locked} if locked else {})}

    def _fill_gap(self, lg):
        """The roll guard's backstop: pts between the entry fill and the chart price the stop / target were computed on
        (lg["ref"]) when that is more than nt_max_fill_gap_pct (default 0.3%) of the price, else None. Normal LIT fills sit
        within 0.08% of the model price (2026: worst 1m entry bar incl. the CISD close, 120 trades, p99 0.07%); the last
        8 NQ rolls were 0.86-1.36% (one weekend open jump 0.56%): 0.3% catches a 0.5% gap with a 3.7x margin over the
        worst normal fill."""
        ref = lg.get("ref")
        if not ref or not lg.get("filled") or not lg.get("fill_px"):
            return None
        gap = abs(float(lg["fill_px"]) - float(ref))
        return gap if gap > float(self.cfg.get("nt_max_fill_gap_pct", 0.3)) / 100.0 * float(ref) else None

    def _gap_flatten(self, lg, gap) -> dict:
        """Filled a roll gap away from the chart price (the chart on the old contract): never place that bracket (its stop
        / target are priced on the other contract), flatten at once + alert."""
        self._risk(f"Chart is on the old contract? {lg['instrument']} filled @ {lg['fill_px']}, {gap:.2f} pts from the "
                   f"chart's price {float(lg['ref']):.2f}: stop/target not placed, flattening. Switch the LE_BarFeed chart to "
                   f"{lg['instrument']}.", alert=True)
        return self._close([lg], why="fill a roll gap away from the chart price")

    def _protect_late(self, lg):
        """A fill reported after place_bracket returned (pending / cancel pending / withdrawn): the same fill-gap check as
        the first fill, then the stop and target."""
        gap = self._fill_gap(lg)
        if gap is not None:
            return self._gap_flatten(lg, gap)
        return self._protect(lg)

    def _contract_mismatch(self, insts) -> str | None:
        """The roll guard: the LE_BarFeed chart's contract (le_feed/<ROOT>_instrument.txt) must be the one the orders go to,
        or the stop/target (priced from the chart's bars) land a roll gap (~300 pts) off the fill. Unknown chart contract
        (older LE_BarFeed): no check (the fill-gap guard in place_bracket still applies)."""
        try:
            # 2026-10-29: an order contract pinned in the config (nt_instrument / nt_instrument_mini, e.g. "MNQ 12-26" typed
            # once) never follows the roll: past its roll date (8 days before expiry) it is refused for every account, even
            # when the chart is left on the same old contract (the chart check below would pass: both old).
            today = dt.datetime.fromtimestamp(self.clock(), ET).date()
            for kind, pin in (self.inst_override or {}).items():
                pe = contract_expiry(pin) if pin and pin in insts else None
                if pe is None:
                    continue
                root = str(pin).split()[0]
                front = nt_instrument(root, today)
                fe = contract_expiry(front)
                if fe and pe < fe:
                    return (f"Order contract pinned to {pin} in the bot's settings (nt_instrument), but it rolled: orders belong "
                            f"on {front} now. Remove the pinned contract (Start page > Accounts, or the nt_instrument line) "
                            "and put the chart on " + front)
        except Exception:
            pass
        try:
            # the chart the bot decides on (signal_root: the MNQ chart, or the NQ chart when it is on): its prices are the
            # stop / target sent to the MNQ order contract
            chart = NinjaTraderBars(self.folder, roots=self.cfg.get("nt_feed_roots")).chart_instrument(self.sym)
        except Exception:
            chart = None
        if not chart:
            return None
        if contract_expiry(chart) is None:
            # a continuous contract ("MNQ ##-##"): the contract check cannot run, only the fill-gap backstop guards a roll
            day = _trading_day(self.clock())
            if self._cont_warned != (chart, day):
                self._cont_warned = (chart, day)
                self._risk(f"The LE_BarFeed chart is on a continuous contract ({chart}): the roll check is OFF (only the fill "
                           f"gap backstop is left). Put the chart on the dated contract the orders go to ({', '.join(insts)}).",
                           alert=True)
            return None
        return contract_problem(chart, insts)

    def _entry_settled(self, lg) -> bool:
        st = self.read_order(lg["entry_id"])
        return bool(st and (st["state"] == FILLED or st["state"] in DEAD))

    def _note_fill(self, lg, st):
        if st and st["filled"] > lg["filled"]:
            first = not lg["filled"]
            lg["filled"] = min(st["filled"], lg["qty"])
            lg["fill_px"] = st["avg"]
            lg["fill_mtime"] = st.get("mtime")
            if first:
                self._push_fill(lg)

    def _protect(self, lg) -> dict:
        """Stop (STOPMARKET) + target (LIMIT) as one OCO pair for the filled quantity."""
        q = lg["filled"]
        opp = "SELL" if lg["side"] == "BUY" else "BUY"
        if lg["status"] != "unprotected" and (self.read_order(lg["stop_id"]) is not None or self.read_order(lg["target_id"]) is not None):
            # S1 2026-11-15: this bracket already reached NinjaTrader (a crash after the bracket file, before the state
            # save): never send the same ids twice; the regular tick manages it (and resizes it to the filled quantity)
            lg["status"] = "protected"     # bracket_qty stays as saved (0 = unknown): the tick resizes both legs to the fill
            lg.setdefault("bracket_at", self.clock())
            self._log("system", f"NinjaTrader: the stop/target of {lg['instrument']} were already at NinjaTrader: not sent again")
            self._save()
            return {"ok": True, "stop": lg["stop"], "target": lg["target"], "note": "bracket already placed"}
        lines = [place_line(self.account, lg["instrument"], opp, q, "STOPMARKET", stop=lg["stop"], oco=lg["oco"], order_id=lg["stop_id"]),
                 place_line(self.account, lg["instrument"], opp, q, "LIMIT", limit=lg["target"], oco=lg["oco"], order_id=lg["target_id"])]
        r = self._send_lines(lines, "BRACKET")
        if not r["ok"]:
            lg["status"] = "unprotected"
            self._risk(f"{lg['side']} {q} {lg['instrument']} filled but the stop/target could not be delivered "
                       f"({r.get('error')}). Position UNPROTECTED: the bot retries every poll; watch NinjaTrader.", alert=True)
            self._save()
            return {"ok": False, "error": "bracket not delivered: " + str(r.get("error"))}
        lg["bracket_qty"] = q
        lg["status"] = "protected"
        lg["bracket_at"] = self.clock()
        self._wait(lambda: self.read_order(lg["stop_id"]) is not None and self.read_order(lg["target_id"]) is not None, self.verify_wait)
        s, t = self.read_order(lg["stop_id"]), self.read_order(lg["target_id"])
        bad = [f"{name} {st['state']}" for name, st in (("stop", s), ("target", t)) if st and st["state"] == "REJECTED"]
        if bad:
            self._risk(f"{', '.join(bad)} for {lg['instrument']}: flattening at once (never hold without both legs)", alert=True)
            fl = self._close([lg], why="bracket rejected")
            return {"ok": False, "error": f"{', '.join(bad)}: position flattened" + ("" if fl["ok"] else " (flatten NOT confirmed)")}
        self._save()
        return {"ok": True, "stop": lg["stop"], "target": lg["target"], "stop_state": s and s["state"], "target_state": t and t["state"]}

    def modify_stop(self, new_stop, action: dict | None = None) -> dict:
        g = self._gate("modify")
        if g:
            return g
        if not new_stop:
            return {"ok": False, "error": "modify needs a stop price"}
        legs = [lg for lg in self.legs if lg["status"] == "protected"]
        et_ = (action or {}).get("entry_t")
        if et_:
            legs = [lg for lg in legs if lg["entry_t"] == int(et_)] or legs
        if not legs:
            return {"ok": False, "error": "no protected bracket to modify"}
        px = _tick(new_stop)
        for lg in legs:
            if (px - lg["target"]) * lg["dir"] >= 0:
                return {"ok": False, "error": f"REFUSED: new stop {px} is at/beyond the target {lg['target']}"}
        r = self._send_lines([change_line(lg["stop_id"], stop=px) for lg in legs], "MOVE STOP")
        if not r["ok"]:
            return {"ok": False, "error": r.get("error")}
        self._sleep(min(0.5, self.verify_wait))
        out, ok = [], True
        for lg in legs:
            st = self.read_order(lg["stop_id"])
            if st and st["state"] in DEAD:
                ok = False
                out.append({"instrument": lg["instrument"], "ok": False, "state": st["state"]})
                continue
            if st and st["state"] == FILLED:
                out.append({"instrument": lg["instrument"], "ok": True, "note": "the stop had already filled"})
                continue
            lg["stop"] = px
            out.append({"instrument": lg["instrument"], "ok": True, "state": st and st["state"]})
        self._save()
        return {"ok": ok, "stop": px, "legs": out, "note": "NinjaTrader reports the order state, not its price: check the stop line on the chart",
                **({} if ok else {"error": "stop change not accepted"})}

    # ------------------------------------------------------------------ LIT scale-in add (engine/lit.py "scale_in", off by default)
    @staticmethod
    def _total(lg) -> int:
        """Micros (or minis) held on one leg: the entry's fill + every add's fill."""
        return int(lg.get("filled") or 0) + sum(int(a.get("filled") or 0) for a in lg.get("adds") or [])

    def add_to_position(self, action: dict) -> dict:
        """One scale-in add to the open, protected bracket (LIT scale_in after breakeven).

        OIF route (the cleanest NinjaTrader ATI supports; no second bracket, no new OCO group):
          1. PLACE <account>;<inst>;BUY|SELL;<n>;MARKET;0;0;DAY;;<entry id minus E>A<k>;;   - the add, same side as the entry
          2. once NinjaTrader reports its fill: CHANGE;;;;<total>;;0;0;;;<stop id>;; and the same for the target id - the one
             OCO pair (STOPMARKET + LIMIT) now covers the whole position at the stop / target already working
        The bracket is grown only after the fill, never before: a stop/target bigger than the position would REVERSE it if
        it filled before the add did (an add that is late, cancelled after pending_timeout or only partly filled leaves the
        position smaller than the bracket). The cost is a short window (add fill -> CHANGE picked up) in which the bracket
        covers only the old quantity; if a leg fills in that window, tick() closes the remainder at once (CLOSEPOSITION +
        alert). CHANGE with QUANTITY only and 0 in LIMIT/STOP PRICE: the help guide's CHANGE text is "pass in zero (0) values
        for price and quantity if you do not wish to change these order parameters" (quoted on the NinjaTrader forum).
        A fill reported late is protected by tick() on the next poll (the same path as a partial entry fill). Refused: no
        protected bracket for that entry, the kill switch / outside the session (entry gate), no stop in the action or the
        live bracket's stop not at or better than it (the add is sized at the breakeven risk: never add while the broker stop
        is still the first stop), an add number already sent for this entry (a restart re-sending it; the add numbers live in
        the state file), a side that does not match, the position file disagreeing with the bracket, the whole position above
        max_micros, an all-minis bracket (adds are micros)."""
        g = self._gate("entry")
        if g:
            return g
        if self.nt_reset:
            return {"ok": False, "error": "REFUSED: " + self._reset_text()}
        qty = int(action.get("qty") or 0)
        if qty < 1:
            return {"ok": False, "error": "REFUSED: add qty < 1"}
        if not action.get("stop"):
            return {"ok": False, "error": "REFUSED: an add needs the stop it was sized at (breakeven)"}
        et_ = action.get("entry_t")
        legs = [lg for lg in self.legs if lg["status"] == "protected" and (not et_ or lg["entry_t"] == int(et_))]
        if not legs:
            return {"ok": False, "error": "REFUSED: no protected bracket to add to"}
        inst = self._instruments()["micro"]
        lg = next((x for x in legs if x["instrument"] == inst), None)
        if lg is None:
            return {"ok": False, "error": f"REFUSED: the open bracket has no {inst} leg to add micros to"}
        d = 1 if int(action.get("dir") or lg["dir"]) == 1 else -1
        if d != lg["dir"]:
            return {"ok": False, "error": "REFUSED: the add's side does not match the open position"}
        want_stop = _tick(action["stop"])
        if (float(lg["stop"]) - want_stop) * d < -1e-9:
            return {"ok": False, "error": f"REFUSED: the broker stop is {lg['stop']}, the add was sized at a stop of {want_stop} "
                                          "(breakeven): not adding while the stop is not there"}
        n_req = int(action.get("n") or 0)
        if n_req and any(int(a.get("n") or 0) == n_req for a in lg.get("adds") or []):
            return {"ok": False, "error": f"REFUSED: add {n_req} was already sent for this entry (restart?): not adding twice"}
        tot = sum(self._total(x) * (10 if x["instrument"] != inst else 1) for x in legs)
        if tot + qty > min(self.max_micros, MAX_MICROS_HARD):
            return {"ok": False, "error": f"REFUSED: {tot} + {qty} micros exceeds max_micros {self.max_micros}"}
        if any(a.get("status") == "sent" for a in lg.get("adds") or []):
            return {"ok": False, "error": "REFUSED: the previous add is not filled yet"}
        p = self.position_for(lg["instrument"])
        want = "LONG" if d == 1 else "SHORT"
        if p is None or p["side"] != want or int(p["qty"]) != self._total(lg):
            return {"ok": False, "error": f"REFUSED: NinjaTrader shows {p and p['side']} {p and p['qty']} {lg['instrument']}, "
                                          f"the bot's bracket holds {want} {self._total(lg)}: not adding"}
        conn = self.connections()
        if self._all_disconnected(conn):
            return {"ok": False, "error": f"REFUSED: NinjaTrader reports every connection DISCONNECTED ({', '.join(conn)})"}
        n = len(lg.get("adds") or []) + 1
        aid = f"{lg['entry_id'][:-1]}A{n}"
        a = {"id": aid, "qty": qty, "filled": 0, "fill_px": None, "status": "sent", "sent_at": self.clock(),
             "n": int(action.get("n") or n), "add_t": action.get("add_t")}
        # saved BEFORE the order file is written: a crash in between leaves an add the next process watches (tick: its
        # fill grows the bracket, the ledger reads it through add_fills; never filled -> cancelled after pending_timeout)
        lg.setdefault("adds", []).append(a)
        self._save()
        r = self._send_lines([place_line(self.account, lg["instrument"], lg["side"], qty, "MARKET", order_id=aid)], "ADD")
        if not r["ok"]:
            if r.get("withdrawn") or not r.get("file"):    # withdrawn unprocessed / never written: it cannot run
                a["status"] = "rejected"
                a["note"] = "not delivered"
            self._save()
            return {"ok": False, "adapter": self.name, "error": r["error"], "oif": r.get("file")}
        self._wait(lambda: self._add_settled(a), self.fill_wait)
        self._note_add(lg, a)
        if a["filled"] > 0:
            res = self._grow_bracket(lg)
            return {"ok": res["ok"], "adapter": self.name, "account": self.account, "add_id": aid, "filled": a["filled"],
                    "fill_px": a["fill_px"], "bracket_qty": lg["bracket_qty"], **({} if res["ok"] else {"error": res.get("error")})}
        if a["status"] == "rejected":
            return {"ok": False, "adapter": self.name, "add_id": aid, "error": "add rejected by NinjaTrader"}
        return {"ok": False, "pending": True, "adapter": self.name, "add_id": aid,
                "note": "add fill not reported yet: the bracket grows the moment NinjaTrader reports it (next poll)"}

    def _add_settled(self, a) -> bool:
        st = self.read_order(a["id"])
        return bool(st and (st["state"] == FILLED or st["state"] in DEAD))

    def _note_add(self, lg, a):
        st = self.read_order(a["id"])
        if st and st["filled"] > a["filled"]:
            a["filled"] = min(int(st["filled"]), int(a["qty"]))
            a["fill_px"] = st["avg"]
        if st and st["state"] == FILLED:
            a["status"] = "filled"
        elif st and st["state"] in DEAD:
            a["status"] = "rejected" if not a["filled"] else "filled"

    def _grow_bracket(self, lg) -> dict:
        """The OCO stop + target cover the whole position (entry + adds filled): CHANGE their quantity."""
        q = self._total(lg)
        if q <= lg["bracket_qty"]:
            return {"ok": True}
        r = self._send_lines([change_line(lg["stop_id"], qty=q), change_line(lg["target_id"], qty=q)], "BRACKET QTY (add)")
        if not r["ok"]:
            self._risk(f"scale-in add filled but the stop/target could not be resized to {q} ({r.get('error')}): "
                       f"{q - lg['bracket_qty']} micros UNPROTECTED; the bot retries every poll", alert=True)
            return {"ok": False, "error": "bracket resize not delivered: " + str(r.get("error"))}
        self._log("system", f"NinjaTrader: scale-in add filled; stop and target resized from {lg['bracket_qty']} to {q}")
        lg["bracket_qty"] = q
        self._save()
        return {"ok": True}

    def add_fills(self, entry_t) -> list:
        """The real state of the scale-in adds of one entry (open legs, then closed ones): [{"n", "id", "qty" (asked),
        "filled", "fill_px", "status"}] for LiveBot's ledger P&L and the eval state. [] when the adapter never saw that entry."""
        out = []
        for lg in list(self.legs) + list(self.history):
            if int(lg.get("entry_t") or 0) != int(entry_t or 0):
                continue
            for a in lg.get("adds") or []:
                if any(o["id"] == a["id"] for o in out):
                    continue
                out.append({"n": int(a.get("n") or 0), "id": a["id"], "qty": int(a.get("qty") or 0),
                            "filled": int(a.get("filled") or 0), "fill_px": a.get("fill_px"), "status": a.get("status")})
        return out

    def _close(self, legs: list, why: str) -> dict:
        """CLOSEPOSITION for the legs' instruments; once NinjaTrader shows them flat, cancel any leg still working."""
        insts = sorted({lg["instrument"] for lg in legs}) or self._our_instruments()
        r = self._send_lines([close_line(self.account, i + self.close_suffix) for i in insts], f"CLOSE ({why})")
        if not r["ok"]:
            self._risk(f"flatten ({why}) could not be delivered: {r.get('error')}. Flatten {', '.join(insts)} in NinjaTrader "
                       "or the Tradovate app NOW.", alert=True)
            for lg in legs:
                lg["status"] = "closing"
                lg["close_sent"] = None
            self._save()
            return {"ok": False, "error": r.get("error"), "instruments": insts}
        sent = time.time()
        since = {lg["instrument"]: lg.get("fill_mtime") for lg in legs}
        flat = self._wait(lambda: all(self._is_flat(i, since.get(i)) for i in insts), self.verify_wait)
        leftovers = []
        if flat:
            leftovers = self._cancel_working(legs, "after flatten")
            self._retire(legs, why)
        else:
            for lg in legs:
                lg["status"] = "closing"
                lg["close_sent"] = sent
            self._risk(f"FLATTEN NOT CONFIRMED ({why}): NinjaTrader still shows a position on {', '.join(insts)} after "
                       f"{self.verify_wait:.0f}s. The stop stays in place; the bot retries. Check NinjaTrader now.", alert=True)
        self._save()
        return {"ok": flat, "instruments": insts, "flat_confirmed": flat, "cancelled_leftovers": leftovers, "oif": r.get("file"),
                **({} if flat else {"error": "flatten sent, not confirmed by NinjaTrader yet"})}

    def _is_flat(self, instrument, since):
        p = self.position_for(instrument)
        if p is None:
            # never a position file: flat only if we never had a fill on it, and never while NinjaTrader's reports were
            # reset (a restart wiped outgoing\\: a missing file proves nothing)
            return since is None and not self.nt_reset
        return p["side"] == "FLAT" and (since is None or (p.get("mtime") or 0) >= since - 0.001)

    def _cancel_working(self, legs, why) -> list:
        ids = []
        for lg in legs:
            adds = tuple(a["id"] for a in lg.get("adds") or [] if a.get("status") in ("sent", "cancel_sent"))
            for oid in (lg["stop_id"], lg["target_id"]) + adds + ((lg["entry_id"],) if lg["status"] in ("pending", "entry_sent", "cancel_pending") else ()):
                st = self.read_order(oid)
                if st and st["state"] in LIVE_STATES | {PARTFILLED}:
                    ids.append(oid)
        if ids:
            self._send_lines([cancel_line(i) for i in ids], f"CANCEL ({why})")
        return ids

    def _retire(self, legs, why):
        for lg in legs:
            if lg in self.legs:
                self.legs.remove(lg)
            self.history.append({**lg, "closed": why, "closed_at": int(self.clock())})
            self._start_watch(lg, why)

    # ------------------------------------------------------------------ retired legs whose orders can still fill
    def _watch_ids(self, lg) -> list:
        return [lg["entry_id"], lg["stop_id"], lg["target_id"]] + [a["id"] for a in lg.get("adds") or []]

    def _start_watch(self, lg, why):
        """A retired leg stays watched while one of its orders can still fill: an add still 'sent' / 'cancel_sent' (its
        cancel may come too late: NinjaTrader keeps a MARKET order working in a thin market) or a stop / target / entry
        NinjaTrader still shows working (a slow cancel). Every fill seen after the retirement leaves a position nobody
        protects: _tick_watch closes it at once (CLOSEPOSITION) + alert, and cancels what is still working."""
        if any(w is lg for w in self.watch):
            return
        snap = {}
        live = False
        for oid in self._watch_ids(lg):
            st = self.read_order(oid)
            snap[oid] = int(st["filled"]) if st else 0
            live = live or bool(st and st["state"] in LIVE_STATES | {PARTFILLED})
        unresolved = any(a.get("status") in ("sent", "cancel_sent") for a in lg.get("adds") or [])
        if live or unresolved:
            lg["watch"] = {"since": self.clock(), "why": why, "filled": snap, "cancel_at": 0.0, "close_at": 0.0, "leftover": 0}
            self.watch.append(lg)

    def _tick_watch(self, now):
        keep = []
        for lg in self.watch:
            w = lg.setdefault("watch", {"since": now, "why": "?", "filled": {}, "cancel_at": 0.0, "close_at": 0.0, "leftover": 0})
            inst = lg["instrument"]
            for a in lg.get("adds") or []:
                if a.get("status") in ("sent", "cancel_sent"):
                    self._note_add(lg, a)
            late, live = [], []
            for oid in self._watch_ids(lg):
                st = self.read_order(oid)
                if not st:
                    continue
                if int(st["filled"]) > int(w["filled"].get(oid, 0)):
                    late.append(f"{oid} +{int(st['filled']) - int(w['filled'].get(oid, 0))} @ {st['avg']}")
                    w["filled"][oid] = int(st["filled"])
                if st["state"] in LIVE_STATES | {PARTFILLED}:
                    live.append(oid)
            open_same = any(x["instrument"] == inst and x["status"] in OPEN_STATUSES for x in self.legs)
            p = self.position_for(inst)
            held = bool(p and p["side"] != "FLAT")
            if late:
                w["leftover"] = 1
                w["close_at"] = 0.0
                self._risk(f"an order of the closed {lg['side']} trade ({lg['entry_id']}) filled AFTER the bot closed it "
                           f"({'; '.join(late)}): NinjaTrader shows {p and p['side']} {p and p['qty']} {inst} with no stop - "
                           + ("CLOSEPOSITION sent at once" if held and not open_same else "watching"), alert=True)
            if w["leftover"] and held and not open_same and now - float(w["close_at"] or 0) >= 30:
                w["close_at"] = now
                self._send_lines([close_line(self.account, inst + self.close_suffix)], "CLOSE (late fill after the exit)")
                p = self.position_for(inst)
                held = bool(p and p["side"] != "FLAT")
            if w["leftover"] and not held:
                w["leftover"] = 0
                self._log("system", f"NinjaTrader: the late-fill leftover on {inst} is closed")
            if live and now - float(w["cancel_at"] or 0) >= 30:
                w["cancel_at"] = now
                self._send_lines([cancel_line(i) for i in live], "CANCEL (closed trade's order still working)")
            if not live and not w["leftover"] and not any(a.get("status") in ("sent", "cancel_sent") for a in lg.get("adds") or []):
                lg.pop("watch", None)
                continue
            if now - float(w["since"]) > 4 * 3600:
                self._risk(f"stopped watching the closed trade {lg['entry_id']} after 4 h: orders {live or 'none'} still "
                           f"reported working, {p and p['side']} {p and p['qty']} {inst}: check NinjaTrader", alert=bool(held or live))
                lg.pop("watch", None)
                continue
            keep.append(lg)
        self.watch = keep

    def flatten(self, action: dict | None = None) -> dict:
        if self.disabled or self.readonly:
            return {"ok": False, "error": "REFUSED: " + (self.disabled or "read-only")}
        action = action or {}
        why = str(action.get("reason") or "exit")
        et_ = action.get("entry_t")
        legs = [lg for lg in self.legs if lg["status"] in OPEN_STATUSES]
        if et_ and legs and all(lg["entry_t"] != int(et_) for lg in legs):
            note = (f"exit {why} belongs to the entry at {_et(int(et_)):%H:%M} ET; the open bracket belongs to the entry at "
                    f"{_et(legs[0]['entry_t']):%H:%M} ET: not touched")
            self._log("system", "NinjaTrader: " + note)
            return {"ok": True, "note": note}
        res = self._close(legs, why)
        return {"adapter": self.name, "account": self.account, **res}

    def has_open_bracket(self, entry_t=None) -> bool:
        """LiveBot asks this before sending a stop move: True once a stop of ours is working for that entry."""
        return any(lg["status"] == "protected" and (entry_t is None or lg["entry_t"] == int(entry_t)) for lg in self.legs)

    def cancel_all(self) -> dict:
        if self.disabled or self.readonly:
            return {"ok": False, "error": "REFUSED: " + (self.disabled or "read-only")}
        ids = self._cancel_working(self.legs, "cancel")
        return {"ok": True, "cancelled": len(ids), "ids": ids}

    def kill(self, scope: str = "account") -> dict:
        """The kill switch on this adapter. Works even when the account is disabled for new orders; no new entry after it.

        scope "account" (the default; account B, the extra accounts, a remote flatten): ONLY this account - CLOSEPOSITION for
        every instrument NinjaTrader shows a position on for this account (and ours), then CANCEL by id for every order of
        ours still working (entries / adds always; the stop / target once NinjaTrader shows flat, so a failed close never
        leaves the position without its stop). Never FLATTENEVERYTHING / CANCELALLORDERS: with LIT 50K + account B 25K on one
        NinjaTrader those would also close the other account (help guide: they act on all accounts and connections).
        scope "global" (only the owner's HOLD TO KILL / remote kill / --kill on the primary): FLATTENEVERYTHING."""
        if self.readonly:
            return {"ok": False, "error": "REFUSED: read-only adapter"}
        self.killed = True
        legs = list(self.legs)
        if scope == "global":
            self._global_kill = True
            try:
                r = self._send_lines([FLATTEN_EVERYTHING], "KILL")
            finally:
                self._global_kill = False
            if r["ok"]:
                self._retire(legs, "kill switch")
                self._risk("KILL: FLATTENEVERYTHING sent (every account and connection in NinjaTrader)")
            else:
                self._risk(f"KILL could not reach NinjaTrader ({r.get('error')}). Flatten the account in NinjaTrader or the "
                           "Tradovate/MFFU app NOW.", alert=True)
            self._save()
            return {"ok": r["ok"], "adapter": self.name, "scope": "global", "oif": r.get("file"),
                    **({} if r["ok"] else {"error": r.get("error")})}
        return self._kill_account(legs)

    def _kill_account(self, legs) -> dict:
        insts = list(self._our_instruments())
        for p in self.positions()["positions"]:
            if p["side"] != "FLAT" and not any(same_instrument(p["instrument"], i) for i in insts):
                insts.append(p["instrument"])
        held = [i for i in insts if (lambda p: p and p["side"] != "FLAT")(self.position_for(i))]
        ids_all = self._live_ids(legs + list(self.watch))
        risky = [i for i in ids_all if not any(i in (lg["stop_id"], lg["target_id"]) for lg in legs + list(self.watch))]
        lines = [close_line(self.account, i + self.close_suffix) for i in (held or insts[:1])] + [cancel_line(i) for i in risky]
        r = self._send_lines(lines, "KILL (this account only)")
        if not r["ok"]:
            self._risk(f"KILL ({self.account}) could not reach NinjaTrader ({r.get('error')}). Flatten {self.account} in "
                       "NinjaTrader or the Tradovate/MFFU app NOW.", alert=True)
            self._save()
            return {"ok": False, "adapter": self.name, "scope": "account", "error": r.get("error")}
        since = {lg["instrument"]: lg.get("fill_mtime") for lg in legs}
        flat = self._wait(lambda: all(self._is_flat(i, since.get(i)) for i in held), self.verify_wait) if held else True
        left = [i for i in self._live_ids(legs + list(self.watch)) if i not in risky] if flat else []
        if left:
            self._send_lines([cancel_line(i) for i in left], "CANCEL (kill, after flat)")
        if flat:
            self._retire(legs, "kill switch")
            self._risk(f"KILL: {self.account} flattened (CLOSEPOSITION {', '.join(held) or 'none held'}; cancelled "
                       f"{len(risky) + len(left)} order(s) by id). Other accounts untouched.")
        else:
            for lg in legs:
                lg["status"], lg["close_sent"] = "closing", time.time()
            self._risk(f"KILL ({self.account}): CLOSEPOSITION sent but NinjaTrader does not show flat yet on {', '.join(held)}: "
                       "the stop stays working. Check NinjaTrader / the MFFU app now.", alert=True)
        self._save()
        return {"ok": flat, "adapter": self.name, "scope": "account", "oif": r.get("file"), "closed": held,
                "cancelled": risky + left, **({} if flat else {"error": "kill sent, flat not confirmed yet"})}

    def _live_ids(self, legs) -> list:
        """Our order ids NinjaTrader still reports working (or with no report yet for an entry / add in flight)."""
        out = []
        for lg in legs:
            ids = [lg["entry_id"], lg["stop_id"], lg["target_id"]] + [a["id"] for a in lg.get("adds") or []]
            for oid in ids:
                st = self.read_order(oid)
                if (st and st["state"] in LIVE_STATES | {PARTFILLED}) and oid not in out:
                    out.append(oid)
        return out

    def send(self, action: dict) -> dict:
        """LiveBot entry point. Never raises."""
        try:
            with self.lock:
                side = action.get("side")
                if side in ("buy", "sell"):
                    return self.place_bracket(action)
                if side == "exit":
                    if str(action.get("reason") or "").upper() == "KILL SWITCH":
                        # account-scoped unless the owner's global kill (LiveBot.kill_switch, primary only) says "global"
                        return self.kill(scope="global" if action.get("scope") == "global" else "account")
                    return self.flatten(action)
                if side == "modify":
                    return self.modify_stop(action.get("stop"), action)
                if side == "add":
                    return self.add_to_position(action)
                if side == "cancel":
                    return self.cancel_all()
                return {"ok": False, "error": f"unknown action side {side!r}"}
        except Exception as e:
            self.last_error = f"{e.__class__.__name__}: {e}"
            self._log("error", f"NinjaTrader adapter exception: {self.last_error}")
            return {"ok": False, "error": self.last_error}

    # ------------------------------------------------------------------ once per poll
    def tick(self) -> dict:
        """LiveBot calls this at the start of every poll: late fill reports, bracket health, leftovers, flat-time safety."""
        try:
            with self.lock:
                if self.disabled or self.readonly:
                    return {"ok": True, "idle": self.disabled or "read-only"}
                now = self.clock()
                self._sweep_stale_oifs(max_age=max(10.0, 2 * self.ack_wait))
                self._tick_outgoing(now)
                if self.state_problem:
                    if self.state_problem.pop("alert", None):
                        self._alert(self.state_problem["text"] + ". No new entry until NinjaTrader shows this account FLAT or "
                                    "you check NinjaTrader and run python -m engine.ninjatrader --confirm-reset. Check "
                                    "NinjaTrader Orders + Positions now.")
                    self._state_problem_resolved()
                self._tick_withdrawn(now)
                for lg in list(self.legs):
                    self._tick_leg(lg, now)
                self._tick_watch(now)
                self._tick_flat_time(now)
                self._save()
                return {"ok": True, "legs": len(self.legs)}
        except Exception as e:
            self.last_error = f"tick: {e.__class__.__name__}: {e}"
            self._log("error", "NinjaTrader " + self.last_error)
            return {"ok": False, "error": self.last_error}

    # ------------------------------------------------------------------ an unreadable state file (pre-launch audit 2026-10-25)
    def _audit_ids(self) -> list:
        """Order ids this account PLACEd, from the tail of the OIF audit log (the record that survives a torn state file)."""
        out = []
        try:
            with open(self.audit_path, encoding="utf-8", errors="replace") as fh:
                rows = fh.read().splitlines()[-3000:]
        except OSError:
            return out
        for row in rows:
            parts = row.split("  ")
            if len(parts) < 4 or parts[1].strip() != self.account:
                continue
            f = parts[-1].split(";")
            if f[0] == "PLACE" and len(f) == 13 and f[10] and f[10] not in out:
                out.append(f[10])
        return out

    def _state_problem_resolved(self) -> bool:
        """The state file was unreadable: resolved once the owner confirmed (--confirm-reset), or once NinjaTrader shows every
        instrument of ours FLAT and no order of ours (audit log) is still working - such an orphan is cancelled by id first
        (cancelling an order on a flat account can never add risk)."""
        sp = self.state_problem
        if not sp:
            return True
        if self._reset_confirmed(sp.get("since")):
            self.state_problem = None
            self._log("system", "NinjaTrader: the owner confirmed the account after the unreadable state file: entries allowed")
            return True
        if not all((lambda p: bool(p and p["side"] == "FLAT"))(self.position_for(i)) for i in self._our_instruments()):
            return False
        orphans = [oid for oid in self._audit_ids()
                   if (lambda st: bool(st and st["state"] in LIVE_STATES | {PARTFILLED}))(self.read_order(oid))]
        if orphans:
            if time.time() - float(sp.get("cancel_at") or 0) >= 30:
                sp["cancel_at"] = time.time()
                self._risk(f"account flat, but {len(orphans)} order(s) of the bot are still working with no trade of its own: "
                           f"cancelling {', '.join(orphans)}", alert=True)
                self._send_lines([cancel_line(i) for i in orphans], "CANCEL (orphan orders, state file lost)")
            return False
        self.state_problem = None
        self._log("system", "NinjaTrader: the account is FLAT and no order of the bot is working: entries allowed again "
                            "(the state file had been unreadable)")
        return True

    # ------------------------------------------------------------------ NinjaTrader restart / disconnect while the bot runs
    def _reset_text(self) -> str:
        r = self.nt_reset or {}
        return (f"NinjaTrader's reports in outgoing were reset at {_et(r.get('since') or 0):%H:%M} ET (NinjaTrader restarted?): "
                f"{', '.join((r.get('files') or [])[:4])} gone. A missing file never means flat: no new entry until NinjaTrader "
                "writes the position file again, or you check the account in NinjaTrader and run "
                "python -m engine.ninjatrader --confirm-reset")

    def _reset_confirmed(self, since) -> bool:
        try:
            with open(self.reset_ok_path, encoding="utf-8") as fh:
                return float(json.load(fh).get("t") or 0) >= float(since or 0)
        except Exception:
            return False

    def _tick_outgoing(self, now):
        """Once per tick: notice NinjaTrader wiping outgoing (a restart) while a position or one of our open brackets
        exists, and an all-DISCONNECTED NinjaTrader while a trade is open. Only blocks / alerts / protects; never opens."""
        names = set(self._listing())
        cur = {p["file"]: p for p in self.positions()["positions"]}
        open_legs = [lg for lg in self.legs if lg["status"] in OPEN_STATUSES]
        open_insts = sorted({lg["instrument"] for lg in open_legs})
        gone, insts = [], set(open_insts)
        for fn, last in list(self.seen_pos.items()):
            if fn in cur:
                continue
            if last.get("side") != "FLAT" or any(same_instrument(last.get("instrument"), i) for i in open_insts):
                gone.append(fn)
                if last.get("instrument"):
                    insts.add(last["instrument"])
            elif not self.nt_reset:
                self.seen_pos.pop(fn, None)      # it was FLAT and no bracket of ours is open: a restart cannot open a position
        for lg in open_legs:
            seen = lg.setdefault("seen_ids", [])
            for oid in (lg["entry_id"], lg["stop_id"], lg["target_id"]):
                if f"{oid}.txt" in names:
                    if oid not in seen:
                        seen.append(oid)
                elif oid in seen:
                    gone.append(f"{oid}.txt")
        for fn, p in cur.items():
            self.seen_pos[fn] = {"side": p["side"], "qty": p["qty"], "instrument": p["instrument"]}
        if gone and not self.nt_reset:
            self.nt_reset = {"since": now, "wall": time.time(), "files": gone, "insts": sorted(insts)}
            held = ", ".join(f"{lg['side']} {lg['filled'] or lg['qty']} {lg['instrument']} ({lg['status']})" for lg in open_legs)
            self._risk(f"NinjaTrader's outgoing reports vanished ({', '.join(gone[:4])}): NinjaTrader restarted or its folder was "
                       "cleared. The bot does NOT assume flat. "
                       + (f"Open: {held}. The stop / target should still be working at the broker: check NinjaTrader Orders + "
                          "Positions now. " if held else "")
                       + "New entries are blocked until NinjaTrader writes the position file again or you run "
                         "python -m engine.ninjatrader --confirm-reset.", alert=True)
            self._save()
        elif self.nt_reset:
            since = float(self.nt_reset.get("wall") or self.nt_reset.get("since") or 0)
            back = bool(cur) and all(any(same_instrument(p["instrument"], i) and (p.get("mtime") or 0) >= since - 1
                                         for p in cur.values()) for i in (self.nt_reset.get("insts") or []))
            ok = self._reset_confirmed(since)
            if back or ok:
                self._log("system", "NinjaTrader: " + ("the owner confirmed the account after the NinjaTrader restart" if ok else
                          "NinjaTrader writes the position file again") + ": new entries allowed again")
                self.nt_reset = None
                self.seen_pos = {fn: v for fn, v in self.seen_pos.items() if fn in cur}   # NinjaTrader's files from now on
                self._after_reset()
                self._save()
        conn = self.connections()
        if open_legs and self._all_disconnected(conn) and now - self._conn_alert_at >= 600:
            self._conn_alert_at = now
            self._risk(f"NinjaTrader reports every connection DISCONNECTED ({', '.join(conn)}) with the bot's trade open: the stop "
                       "and target sit at the broker, but the bot cannot see fills or move the stop. Reconnect NinjaTrader; if it "
                       "stays down, check the position in the MFFU / Tradovate app.", alert=True)

    def _after_reset(self):
        """The position files are back after a NinjaTrader restart: an entry of ours that was still in flight (its order
        report gone) and now shows as a position in its direction gets its stop and target (never a naked position); an
        open bracket whose stop / target reports did not come back is flagged for a manual look."""
        for lg in [x for x in self.legs if x["status"] in OPEN_STATUSES]:
            p = self.position_for(lg["instrument"])
            held = bool(p and p["side"] != "FLAT")
            if lg["status"] in ("entry_sent", "pending", "cancel_pending") and not lg["filled"] and held \
                    and p["side"] == ("LONG" if lg["dir"] == 1 else "SHORT"):
                lg["filled"], lg["fill_px"], lg["fill_mtime"] = min(int(p["qty"]), int(lg["qty"])), p.get("avg"), p.get("mtime")
                self._risk(f"after the NinjaTrader restart {p['side']} {p['qty']} {lg['instrument']} is open and the entry "
                           f"{lg['entry_id']} report is gone: treating it as filled, placing the stop and target", alert=True)
                self._protect_late(lg)
            elif lg["status"] == "protected" and held:
                miss = [n for n, oid in (("stop", lg["stop_id"]), ("target", lg["target_id"])) if self.read_order(oid) is None]
                if miss:
                    self._risk(f"after the NinjaTrader restart the {' and '.join(miss)} report of the open {lg['instrument']} trade "
                               "did not come back: check in NinjaTrader's Orders tab that both are still working (the bot keeps "
                               "managing the trade and routes its exit).", alert=True)
            lg["seen_ids"] = [oid for oid in (lg["entry_id"], lg["stop_id"], lg["target_id"]) if self.read_order(oid) is not None]
            lg["after_reset"] = True       # a working order NinjaTrader does not re-report is not "never placed"

    def _tick_withdrawn(self, now):
        keep = []
        for w in self.withdrawn:
            st = self.read_order(w["entry_id"])
            if st and st["filled"] > 0:
                lg = w["leg"]
                self._risk(f"an entry the bot had withdrawn ({w['entry_id']}) was executed by NinjaTrader after all: "
                           f"{st['filled']} {lg['instrument']} @ {st['avg']}. Protecting it now.", alert=True)
                lg["status"] = "pending"
                self.legs.append(lg)
            elif st is None and now - w["t"] < self.pending_timeout:
                keep.append(w)
        self.withdrawn = keep

    def _tick_leg(self, lg, now):
        st = self.read_order(lg["entry_id"])
        self._note_fill(lg, st)
        if lg["status"] in ("pending", "entry_sent"):
            if lg["filled"] > 0:
                self._log("system", f"NinjaTrader: entry {lg['entry_id']} filled {lg['filled']} @ {lg['fill_px']}: placing the stop and target")
                self._protect_late(lg)
            elif st and st["state"] in DEAD:
                self._retire([lg], f"entry {st['state'].lower()}")
                self._log("risk", f"NinjaTrader: entry {lg['entry_id']} {st['state']}: nothing was opened")
            elif now - lg["sent_at"] > self.pending_timeout:
                self._send_lines([cancel_line(lg["entry_id"])], "CANCEL (entry never filled)")
                lg["status"], lg["cancel_sent"] = "cancel_pending", now
                self._save()
                self._risk(f"entry {lg['entry_id']} not confirmed by NinjaTrader within {self.pending_timeout:.0f}s: "
                           f"cancel sent (CANCEL PENDING: a late fill is still protected). Check NinjaTrader's Orders and Log tabs "
                           f"(is the account name '{self.account}' and the instrument '{lg['instrument']}' right?).", alert=True)
            return
        if lg["status"] == "cancel_pending":
            if lg["filled"] > 0:
                self._risk(f"NinjaTrader: entry {lg['entry_id']} filled {lg['filled']} @ {lg['fill_px']} while its cancel was pending: "
                           "placing the stop and target", alert=True)
                self._protect_late(lg)
            elif st and st["state"] in DEAD:
                self._retire([lg], f"entry {st['state'].lower()} (cancel confirmed)")
                self._log("system", f"NinjaTrader: entry {lg['entry_id']} {st['state']}: nothing was opened")
            elif now - lg.get("cancel_sent", now) > 20 * self.pending_timeout and self._is_flat(lg["instrument"], None):
                self._retire([lg], "cancel never confirmed, account flat")
                self._risk(f"NinjaTrader never confirmed the cancel of {lg['entry_id']}; the account is flat on {lg['instrument']}: "
                           "stopped watching it", alert=True)
            return
        if lg["status"] == "unprotected":
            s, t = self.read_order(lg["stop_id"]), self.read_order(lg["target_id"])
            if s is not None or t is not None:      # the bracket file was processed after all: never send those ids twice
                lg["status"], lg["bracket_qty"] = "protected", lg["filled"]
                self._log("system", f"NinjaTrader: the stop/target of {lg['instrument']} arrived late (stop {s and s['state']}, "
                                    f"target {t and t['state']})")
            elif self._flat_since(lg["instrument"], (lg.get("fill_mtime") or 0) + 0.001):
                self._retire([lg], "closed while unprotected")      # no position left: a stop/target now would be naked
                self._log("risk", f"NinjaTrader: {lg['instrument']} is flat again; the missing stop/target are not placed")
            else:
                self._protect(lg)
            return
        if lg["status"] == "closing":
            if self._is_flat(lg["instrument"], lg.get("fill_mtime")):
                self._cancel_working([lg], "after flatten")
                self._retire([lg], "flattened (confirmed late)")
                self._log("system", f"NinjaTrader: {lg['instrument']} now flat")
            elif not lg.get("close_sent") or time.time() - lg["close_sent"] > 30:
                self._close([lg], why="retry")
            return
        # protected: a scale-in add filled after add_to_position returned (late report) / one that never fills is cancelled
        for a in lg.get("adds") or []:
            if a.get("status") == "sent":
                self._note_add(lg, a)
                if a["status"] == "sent" and now - float(a.get("sent_at") or now) > self.pending_timeout:
                    self._send_lines([cancel_line(a["id"])], "CANCEL (add never filled)")
                    a["status"] = "cancel_sent"
                    self._risk(f"scale-in add {a['id']} not filled within {self.pending_timeout:.0f}s: cancel sent")
            elif a.get("status") == "cancel_sent":
                self._note_add(lg, a)
        # protected: the entry grew (partial fill completed) or an add filled -> grow the bracket
        if self._total(lg) > lg["bracket_qty"]:
            q = self._total(lg)
            r = self._send_lines([change_line(lg["stop_id"], qty=q), change_line(lg["target_id"], qty=q)], "BRACKET QTY")
            if r["ok"]:
                self._log("system", f"NinjaTrader: entry now filled {q}; stop and target resized from {lg['bracket_qty']} to {q}")
                lg["bracket_qty"] = q
        s, t = self.read_order(lg["stop_id"]), self.read_order(lg["target_id"])
        # an exit leg partly filled (LIT report ch.27): the sibling must shrink to the quantity still open, or a later full fill
        # of the sibling would open an opposite position
        for name, x, other_id in (("stop", s, lg["target_id"]), ("target", t, lg["stop_id"])):
            if x and x["state"] == PARTFILLED and 0 < x["filled"] < lg["bracket_qty"]:
                rest = lg["bracket_qty"] - x["filled"]
                if lg.get("sibling_qty", {}).get(other_id) != rest:
                    r = self._send_lines([change_line(other_id, qty=rest)], "BRACKET QTY (partial exit)")
                    if r["ok"]:
                        lg.setdefault("sibling_qty", {})[other_id] = rest
                        self._risk(f"NinjaTrader: {name} of {lg['instrument']} partly filled ({x['filled']} of {lg['bracket_qty']}): "
                                   f"the other leg resized to {rest}")
                        self._save()
        hit = [(name, x) for name, x in (("STOP", s), ("TARGET", t)) if x and x["state"] == FILLED]
        if hit:
            name, x = hit[0]
            other_id, other = (lg["target_id"], t) if name == "STOP" else (lg["stop_id"], s)
            if other and other["state"] in LIVE_STATES:
                self._send_lines([cancel_line(other_id)], "CANCEL (OCO leftover)")
                self._risk(f"{name} filled but the other leg was still working: cancel sent ({other_id})")
            # the leg filled for less than the position (a scale-in add filled before the bracket was resized): the rest
            # has no stop. Close it at once. Also when NinjaTrader's position file, written after that fill, is not flat.
            # what the other leg filled first (a partial exit: it was resized to the rest) is gone too
            rest = self._total(lg) - int(x.get("filled") or 0) - int((other or {}).get("filled") or 0)
            p = self.position_for(lg["instrument"])
            after = p is not None and (p.get("mtime") or 0) >= (x.get("mtime") or 0) - 0.001
            if after:
                rest = 0 if p["side"] == "FLAT" else max(rest, int(p["qty"]))   # the position file, written after the fill, decides
            if rest > 0:
                self._risk(f"{name} filled {x['filled']} {lg['instrument']} but the bot's position was {self._total(lg)} "
                           f"(NinjaTrader shows {p and p['side']} {p and p['qty']}): the rest had no stop - CLOSEPOSITION sent",
                           alert=True)
                self._close([lg], why=f"{name.lower()} filled, remainder closed")
                self._push_exit(lg, name, x)
                return
            self._retire([lg], f"{name.lower()} filled")
            self._log("system", f"NinjaTrader: bracket closed the trade: {name} filled {x['filled']} {lg['instrument']} @ {x['avg']}")
            self._push_exit(lg, name, x)
            return
        dead = [name for name, x in (("stop", s), ("target", t)) if x and x["state"] in DEAD]
        if dead:
            self._risk(f"{' and '.join(dead)} of the open {lg['instrument']} trade {('were' if len(dead) > 1 else 'was')} "
                       "cancelled/rejected outside the bot: flattening (never hold without both legs)", alert=True)
            self._close([lg], why="bracket leg lost")
            return
        if s is None and self._bracket_never_reported(lg, st, now):
            return
        if self._flat_since(lg["instrument"], (lg.get("fill_mtime") or 0) + 0.001):
            seen = self._outside_flat.get(lg["entry_id"], 0) + 1
            self._outside_flat[lg["entry_id"]] = seen
            if seen >= 2:                       # two polls in a row: closed by hand in NinjaTrader / the Tradovate app
                ids = self._cancel_working([lg], "position closed outside the bot")
                self._retire([lg], "closed outside the bot")
                self._log("risk", f"NinjaTrader: {lg['instrument']} was closed outside the bot; leftover orders cancelled: {ids or 'none'}")
        else:
            self._outside_flat.pop(lg["entry_id"], None)

    def _bracket_never_reported(self, lg, st, now) -> bool:
        """S1 robustness (2026-11-15): the bracket file was picked up (deleted from incoming) but NinjaTrader never wrote a
        report for the STOP (it read the file empty / dropped it: the 2026-10-20 rehearsal's 94 naked minutes). The
        entry's own report is there, so NinjaTrader's outgoing works: the stop order does not exist. After
        nt_bracket_report_s (30 s) the position is flattened (CLOSEPOSITION also cancels working orders) and the stop /
        target ids are cancelled blind (a CANCEL of an unknown id is harmless); never re-placed under new ids, which could
        double the exit if the old ones were only slow. Not while NinjaTrader's reports were reset (a restart rewrites
        nothing for orders already working) or for a stop report that was seen before (the reset logic owns that).
        True = handled this tick."""
        if self.nt_reset or lg.get("after_reset") or st is None or lg["stop_id"] in (lg.get("seen_ids") or []):
            return False
        if any(lg["stop_id"] in n for n in self._listing()):
            return False                       # a report is there (only unreadable / unparsable right now): not missing
        p = self.position_for(lg["instrument"])
        if p is not None and p["side"] == "FLAT" and (p.get("mtime") or 0) >= (lg.get("fill_mtime") or 0):
            return False                       # flat: the closed-outside-the-bot logic below retires it
        since = lg.setdefault("bracket_at", now)           # a leg restored from an older state file: count from now
        if now - float(since) < float(self.cfg.get("nt_bracket_report_s", 30.0)):
            return False
        self._risk(f"the STOP of the open {lg['side']} {lg['filled']} {lg['instrument']} was never reported by NinjaTrader "
                   f"{now - float(since):.0f}s after the bracket was sent (order {lg['stop_id']} missing in outgoing while the "
                   "entry's report is there): the position may have NO stop at the broker. Flattening now (never hold "
                   "without a stop). Check NinjaTrader Orders + Positions.", alert=True)
        self._close([lg], why="stop never reported")
        self._send_lines([cancel_line(lg["stop_id"]), cancel_line(lg["target_id"])], "CANCEL (bracket never reported)")
        return True

    def _tick_flat_time(self, now):
        e = _et(now)
        mod = e.hour * 60 + e.minute
        if e.weekday() >= 5:
            return
        flat = self._flat_today(e)
        for lg in [x for x in self.legs if x["status"] in ("protected", "unprotected", "pending", "cancel_pending")]:
            past = (_tday(mod) >= _tday(flat) or _tday(mod) < _tday(self.session_from)) if self.all_hours \
                else (mod >= flat or mod < self.session_from)
            if past:
                self._risk(f"flat time {flat // 60:02d}:{flat % 60:02d} ET{' (CME early close)' if flat < self.flat_mod else ''} "
                           f"passed with the bot's {lg['instrument']} trade open: flattening", alert=False)
                self._close([lg], why="flat time")
        if not (flat <= mod < 1020):                  # the account itself: only between flat time and the 17:00 close
            return
        for inst in self._our_instruments():
            p = self.position_for(inst)
            if p and p["side"] != "FLAT" and time.time() - self._flat_tries.get(inst, 0) > 30:
                self._flat_tries[inst] = time.time()
                self._risk(f"{p['side']} {p['qty']} {inst} still open on {self.account} after the flat time: CLOSEPOSITION sent")
                self._send_lines([close_line(self.account, inst + self.close_suffix)], "CLOSE (flat time)")

    # ------------------------------------------------------------------ persistence / status
    def _save(self):
        if self.readonly:
            return
        blob = {"version": 1, "day": _trading_day(self.clock()), "account": self.account, "saved_at": int(self.clock()),
                "legs": self.legs, "withdrawn": self.withdrawn, "watch": self.watch, "killed": self.killed,
                "seen_pos": self.seen_pos, "nt_reset": self.nt_reset, "state_problem": self.state_problem,
                "entries_day": self.entries_day}
        try:
            os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
            tmp = self.state_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(blob, fh, indent=1, default=str)
            from .fsutil import replace as _replace
            _replace(tmp, self.state_path)            # retried: Windows refuses a replace while a reader has it open
        except Exception as e:
            self.last_error = f"state save failed: {e}"

    def _restore(self):
        try:
            with open(self.state_path, encoding="utf-8") as fh:
                s = json.load(fh)
            if not isinstance(s, dict) or not isinstance(s.get("legs", []), list):
                raise ValueError("not a state object")
        except FileNotFoundError:
            return
        except Exception as e:
            # a torn / corrupted file: the open bracket it held is unknown. Never read that as flat: kept aside for a look,
            # new entries blocked until NinjaTrader shows this account flat (position files) or the owner confirms
            mine = not self.readonly and not getattr(self, "lock_problem", None)
            bad = f"{self.state_path}.corrupt-{int(time.time())}"
            try:
                if mine:
                    os.replace(self.state_path, bad)
                else:
                    bad = self.state_path
            except OSError:
                bad = self.state_path
            self.state_problem = {"since": time.time(), "text": f"the bot's NinjaTrader state file was unreadable ({e.__class__.__name__}"
                                  f"; kept as {os.path.basename(bad)}): the open bracket it held is unknown"}
            if mine:
                self._save()                 # the problem itself survives a restart (the torn file was moved aside)
                self.state_problem["alert"] = 1          # the phone alert goes out at the first tick() (after the bot is wired)
                self._risk(self.state_problem["text"] + ". New entries are blocked until NinjaTrader shows this account FLAT "
                           "or you check NinjaTrader and run python -m engine.ninjatrader --confirm-reset. An open trade's stop "
                           "and target stay at the broker; check NinjaTrader Orders + Positions now.")
            return
        if s.get("account") != self.account or s.get("day") != _trading_day(self.clock()):
            return
        self.legs = [lg for lg in (s.get("legs") or []) if isinstance(lg, dict) and lg.get("status") in OPEN_STATUSES]
        self.withdrawn = [w for w in (s.get("withdrawn") or []) if isinstance(w, dict)]
        self.watch = [lg for lg in (s.get("watch") or []) if isinstance(lg, dict) and isinstance(lg.get("watch"), dict)]
        self.seen_pos = {k: v for k, v in (s.get("seen_pos") or {}).items() if isinstance(v, dict)}
        self.nt_reset = s.get("nt_reset") if isinstance(s.get("nt_reset"), dict) else None
        self.state_problem = s.get("state_problem") if isinstance(s.get("state_problem"), dict) else None
        ed = s.get("entries_day")
        if isinstance(ed, dict) and ed.get("day") == s.get("day"):
            self.entries_day = {"day": ed.get("day"), "n": int(ed.get("n") or 0)}

    def status(self) -> dict:
        fs = self.folder_status()
        try:
            pos = self.positions()["positions"]
        except Exception:
            pos = []
        return {"adapter": self.name, "account": self.account, "sim": self.sim, "env": self.env, "disabled": self.disabled,
                "readonly": self.readonly, **fs, "instruments": self._our_instruments(), "contract_mode": self.contract_mode,
                "write_mode": self.write_mode, "connections": self.connections(), "positions": pos, "legs": self.legs,
                "withdrawn": self.withdrawn, "history": list(self.history)[-5:], "unparsed": dict(list(self.unparsed.items())[-5:]),
                "last_error": self.last_error, "killed": self.killed, "max_micros": self.max_micros, "flat_mod": self.flat_mod,
                "nt_reset": self.nt_reset, "state_problem": self.state_problem, "lock_problem": self.lock_problem,
                "audit_log": self.audit_path, "state_file": self.state_path}

    def startup_problems(self) -> list:
        """What the PC bot's startup reconcile (engine/guards.startup_problems) needs from NinjaTrader before the first entry:
        folders there, this process owns the account, the account allowed, no NinjaTrader reset / unreadable state open,
        not every connection DISCONNECTED, the chart on the contract the orders go to, every open bracket of ours with its
        stop and target reports present, and no position on this account that no bracket of ours explains. [] = reconciled."""
        out = []
        fs = self.folder_status()
        if not fs["incoming"] or not fs["outgoing"]:
            out.append(f"NinjaTrader folders missing ({self.incoming} / {self.outgoing})")
        if self.disabled:
            out.append(f"adapter disabled: {self.disabled}")
        if self.nt_reset:
            out.append("NinjaTrader reports reset (restart?): waiting for the position file or --confirm-reset")
        if self.state_problem and not self._state_problem_resolved():
            out.append(self.state_problem["text"])
        conn = self.connections()
        if self._all_disconnected(conn):
            out.append(f"every NinjaTrader connection DISCONNECTED ({', '.join(conn)})")
        insts = self._our_instruments()
        bad = self._contract_mismatch(insts)
        if bad:
            out.append(bad)
        open_legs = [lg for lg in self.legs if lg["status"] in OPEN_STATUSES]
        for lg in open_legs:
            if lg["status"] == "protected":
                miss = [n for n, oid in (("stop", lg["stop_id"]), ("target", lg["target_id"])) if self.read_order(oid) is None]
                if miss:
                    out.append(f"open {lg['instrument']} trade: {' and '.join(miss)} report missing in outgoing (check NinjaTrader Orders)")
        for p in self.positions()["positions"]:
            if p["side"] != "FLAT" and not any(same_instrument(p["instrument"], lg["instrument"]) for lg in open_legs):
                out.append(f"NinjaTrader shows {p['side']} {p['qty']} {p['instrument']} on {self.account} that no bracket of the bot explains")
        return out


# ---------------------------------------------------------------------- bar feed (LE_BarFeed.cs -> CSV -> the bot)
class NinjaTraderBars:
    """Reads Documents\\NinjaTrader 8\\le_feed\\<ROOT>_<N>m.csv (written by ninjatrader/LE_BarFeed.cs: time = bar OPEN in
    unix seconds, open, high, low, close, volume) and returns the frame live._yahoo_recent returns. 15m / 1h bars are
    built from the 5m file. recent_bars() -> (frame | None, reason, covers_period)."""
    MINUTES = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60}

    def __init__(self, folder=None, roots=None, stale_s=None):
        self.dir = os.path.join(folder or default_folder(), FEED_DIR)
        self.roots = roots or feed_roots()          # MNQ first; NQ first with signal_root "NQ" (live_model.json)
        self.stale_s = stale_s
        self._cache: dict = {}

    def root_for(self, sym):
        """The ONE chart root the bot reads `sym` from: the first of its roots with a 5m or 1m file, else None. Every file
        (5m, 1m, the forming 1m open, the chart's contract) then comes from that chart, so 5m and 1m bars never mix two
        instruments (an NQ 5m bar does not rebuild from MNQ 1m bars: the live 1m rule would drop the window)."""
        for root in self.roots.get(sym, [sym]):
            if any(os.path.exists(os.path.join(self.dir, f"{root}_{m}m.csv")) for m in (5, 1)):
                return root
        return None

    def file_for(self, sym, minutes):
        root = self.root_for(sym)
        if root is None:
            return None
        p = os.path.join(self.dir, f"{root}_{minutes}m.csv")
        return p if os.path.exists(p) else None

    def chart_instrument(self, sym="NQ"):
        """The contract of the LE_BarFeed chart the bot reads ("MNQ 12-26" / "NQ 12-26", from <ROOT>_instrument.txt), None
        when unknown (an older LE_BarFeed that does not write the file). No bar file at all: the first instrument file of
        the roots (as before)."""
        root = self.root_for(sym)
        for r in ([root] if root else self.roots.get(sym, [sym])):
            txt = _read_text(os.path.join(self.dir, f"{r}_instrument.txt"))
            if txt and txt.strip():
                return txt.strip().splitlines()[0].strip()
        return None

    TAIL_FULL_EVERY_S = 900.0    # day-speed 2026-11-20: a full read at least every 15 min (backstop)
    TAIL_MAX_GROWTH = 16384      # more than ~350 new lines at once (a catch-up / rewrite): full read

    def load(self, path):
        """The bar file as a frame. LE_BarFeed / LE_Feed append one line per closed bar; a file that only GREW since the
        last read (everything up to the old end byte-identical: CRC32 of that prefix, < 16 KB more, a full read in the last
        15 min) is parsed from the last complete line on (~7 ms instead of ~70 ms for 21,000 1m lines); a trim, rewrite or
        replace is a full read exactly as before. Same frame either way (tests/test_speed_tail_load.py). redteam 2026-11-21:
        the whole prefix is checked (reading it is ~1 ms; only the parse is slow), so a same-size rewrite in place (LE_Feed's
        File.Copy fallback) that corrects a middle bar is read at once, not up to 15 min later."""
        import io
        import pandas as pd
        try:
            st = os.stat(path)
        except OSError:
            return None
        key = (st.st_mtime_ns, st.st_size)
        hit = self._cache.get(path)
        if hit and hit[0] == key:
            return hit[1]
        cols = ["time", "open", "high", "low", "close", "volume"]
        tails = self.__dict__.setdefault("_tail", {})
        prev = tails.get(path)
        try:
            with open(path, "rb") as fh:
                data = fh.read()                       # the whole file (~1 MB, ~1 ms): only the parse below is slow
        except OSError:
            return None
        o = int(prev["off"]) if prev else -1
        if prev and o <= len(data) <= o + self.TAIL_MAX_GROWTH and time.time() - prev["full_t"] < self.TAIL_FULL_EVERY_S \
                and zlib.crc32(memoryview(data)[:o]) == prev["crc"]:
            new, base, off0 = data[o:], prev["raw"], o    # byte-identical up to the old end: only appended since the last read
        else:
            new, base, off0 = data, None, 0
        # (2026-11-03) every line LE_Feed / LE_BarFeed writes ends with "\n": a last line without it is still being
        # appended, and a cut number ("21000.5" read as "2100") would parse as a valid but wrong close. Not parsed; the
        # next read (the file's size changes, so the cache misses) has it whole.
        cut = new.rfind(b"\n") + 1
        body = new[:cut]
        try:
            part = pd.read_csv(io.BytesIO(body), header=None, names=cols, usecols=range(6), on_bad_lines="skip", dtype=str,
                               engine="python") if body.strip() else pd.DataFrame(columns=cols, dtype=str)
        except Exception:
            return None
        for c in cols:
            part[c] = pd.to_numeric(part[c], errors="coerce")
        part = part.dropna(subset=["time", "open", "high", "low", "close"])          # header row, junk line
        part["volume"] = part["volume"].fillna(0.0)
        raw = part if base is None else pd.concat([base, part], ignore_index=True)
        tails[path] = {"off": off0 + cut, "crc": zlib.crc32(memoryview(data)[:off0 + cut]), "raw": raw,
                       "full_t": prev["full_t"] if base is not None else time.time()}
        df = raw.copy()
        df["time"] = df["time"].astype("int64")
        df = df.drop_duplicates("time", keep="last").sort_values("time").reset_index(drop=True)
        for c in ("open", "high", "low", "close", "volume"):
            df[c] = df[c].astype(float)
        self._cache[path] = (key, df)
        return df

    @staticmethod
    def aggregate(df, secs):
        g = (df["time"] // secs) * secs
        out = df.groupby(g).agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"),
                                volume=("volume", "sum"))
        out.index.name = "time"
        out = out.reset_index()
        out["time"] = out["time"].astype("int64")
        return out

    def recent_bars(self, sym, interval="5m", period="5d", now=None):
        from .live import market_open
        now = int(now if now is not None else time.time())
        if interval not in self.MINUTES:
            return None, f"interval {interval} not supported", False
        mins = self.MINUTES[interval]
        base_m = mins if mins in (1, 5) else 5
        path = self.file_for(sym, base_m)
        if path is None and mins == 5 and self.file_for(sym, 1):
            path, base_m = self.file_for(sym, 1), 1               # only a 1m chart: build 5m from it
        if path is None:
            return None, (f"no feed file {FEED_DIR}/{self.roots.get(sym, [sym])[0]}_{base_m}m.csv (is LE_BarFeed on a "
                          f"{self.roots.get(sym, [sym])[0]} {base_m}-minute chart in NinjaTrader?)"), False
        df = self.load(path)
        if df is None or df.empty:
            return None, f"feed file {os.path.basename(path)} is empty or unreadable", False
        bsecs = base_m * 60
        last_open = int(df["time"].iloc[-1])
        if last_open > now + 60:
            return None, f"{os.path.basename(path)} has bars in the future: check NinjaTrader's time zone / LE_BarFeed", False
        recent = df[df["time"] >= now - 7 * 86400]
        bad = 0
        for t in recent["time"].values[-3000:]:
            e = _et(int(t))
            if e.weekday() < 5 and 1020 <= e.hour * 60 + e.minute < 1080:
                bad += 1                    # CME index futures never print 17:00-17:59 ET: the stamps are shifted
        if bad:
            return None, (f"{os.path.basename(path)}: {bad} bars stamped 17:00-17:59 ET, when CME is closed. Bar times "
                          "look shifted (NinjaTrader time zone or bar-close stamps)"), False
        age = now - (last_open + bsecs)
        # a 1m file may skip a minute without trades (quiet overnight): stale only after 7 minutes; 5m after 7 minutes too
        stale_s = self.stale_s if self.stale_s is not None else max(bsecs + 120, 420)
        if market_open(now) and market_open(now - stale_s) and age > stale_s:
            return None, (f"{os.path.basename(path)} is stale: last bar {_et(last_open):%a %H:%M} ET, {age // 60} min ago "
                          "(NinjaTrader closed, disconnected, or the chart was removed?)"), False
        if mins != base_m:
            df = self.aggregate(df, mins * 60)
            # BUG_FIX (A1 audit 2026-10-25, tests/test_a1_timing.py): a bar built from finer bars is complete only when the
            # feed has closed a base bar at or past its last slot. LE_BarFeed writes a 1m bar on the first tick AFTER it
            # closes, so at 10:05:01 a 1m-only feed may still end at 10:03: the 10:00 5m bar then held 4 minutes and passed
            # live.clean_bars (time + 300 <= now) as closed. Same rule as pcbars.CloudFeed (the minute-4 bar is in).
            df = df[df["time"] + mins * 60 <= last_open + bsecs]
            if df.empty:
                return None, f"{os.path.basename(path)}: no complete {interval} bar yet", False
        m = re.fullmatch(r"(\d+)d", str(period or "5d"))
        start = now - (int(m.group(1)) if m else 5) * 86400
        full = int(df["time"].iloc[0]) <= start + 3600
        why = "ok" if full else f"feed starts {_et(int(df['time'].iloc[0])):%m-%d %H:%M} ET, later than the {period} asked for"
        gaps = self._gap_ratio(df[df["time"] >= now - 3 * 86400], mins * 60, market_open)
        if gaps > 0.10:
            full = False
            why = f"feed is missing {gaps:.0%} of the bars of the last 3 days (ETH trading hours on the chart?)"
        return df.reset_index(drop=True), why, full

    def forming_open(self, sym, now=None):
        """(open time, open) of the 1-minute bar forming now, from LE_BarFeed's <ROOT>_1m_open.csv (one line "time,open",
        rewritten on the first trade of every minute), or None (no file, unreadable, or not the current minute). The live
        loop sizes a LIT entry decided on the 1m CISD close from it (the backtest fills at that bar's open + 1 tick)."""
        now = int(now if now is not None else time.time())
        root = self.root_for(sym)                   # the chart the bars come from (never another instrument's open)
        p = os.path.join(self.dir, f"{root}_1m_open.csv") if root else None
        if p is None or not os.path.exists(p):
            return None
        try:
            with open(p, encoding="utf-8") as fh:
                lines = [x.strip() for x in fh.read().splitlines() if x.strip()]
            t_s, px_s = lines[-1].split(",")[:2]
            t, px = int(float(t_s)), float(px_s)
        except (OSError, ValueError, IndexError):
            return None
        if t % 60 or not (t <= now < t + 60) or not (px > 0):
            return None
        return (t, px)

    @staticmethod
    def _gap_ratio(df, secs, market_open):
        if df is None or len(df) < 2:
            return 0.0
        t0, t1 = int(df["time"].iloc[0]), int(df["time"].iloc[-1])
        have = set(int(x) for x in df["time"].values)
        slots = [t for t in range(t0 - t0 % secs, t1 + 1, secs) if market_open(t) and market_open(t + secs - 1)]
        if not slots:
            return 0.0
        return sum(1 for t in slots if t not in have) / len(slots)


# ---------------------------------------------------------------------- command line
def _http(port, path, body=None, timeout=20):
    import urllib.request
    url = f"http://127.0.0.1:{port}{path}"
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST" if body is not None else "GET")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))      # the local server: never through a proxy
    with opener.open(req, timeout=timeout) as r:
        return json.loads(r.read().decode() or "{}")


def _last_price(folder):
    feed = NinjaTraderBars(folder)
    p = feed.file_for("NQ", 5) or feed.file_for("NQ", 1)
    df = feed.load(p) if p else None
    if df is not None and len(df):
        return float(df["close"].iloc[-1]), f"{os.path.basename(p)} last close"
    try:
        from .data import load
        return float(load("NQ", "5m").c[-1]), "data/NQ_5m.csv last close"
    except Exception:
        return None, "no price available"


def _cli_status(cfg):
    ad = NinjaTraderAdapter(cfg, readonly=True)
    st = ad.status()
    print(f"NinjaTrader folder : {st['folder']}  (exists {st['exists']}, incoming {st['incoming']}, outgoing {st['outgoing']})")
    print(f"Account            : {st['account']}  ({'Sim' if st['sim'] else 'LIVE: needs armed + phrase + ' + LIVE_ENV + '=1'})")
    print(f"Instrument(s)      : {', '.join(st['instruments'])}  (contract mode {st['contract_mode']})")
    print(f"Connections        : {st['connections'] or 'no connection file yet (connect, or NinjaTrader just restarted)'}")
    print(f"Positions          : {[(p['instrument'], p['side'], p['qty'], p['avg']) for p in st['positions']] or 'none reported'}")
    print(f"Open brackets      : {len(st['legs'])} (state file {st['state_file']})")
    feed = NinjaTraderBars(cfg.get("nt_folder"), roots=cfg.get("nt_feed_roots"))
    root = feed.root_for("NQ")
    bad = contract_problem(feed.chart_instrument("NQ"), st["instruments"])
    print(f"Signals from       : {root + ' chart' if root else 'no LE_BarFeed chart'} ({feed.chart_instrument('NQ') or 'contract unknown'}; "
          f"signal_root {signal_root(cfg)}) -> orders {', '.join(st['instruments'])}" + (f"  ** {bad}" if bad else ""))
    fst = read_feed_status(cfg.get("nt_folder"))
    last1 = f", last 1m bar {_et(fst['last_1m']):%a %H:%M} ET" if fst and fst.get("last_1m") else ""
    print(f"Bar source         : {(feed_status_text(fst) + last1) if fst else (feed_addon_line(cfg.get('nt_folder')) or 'the LE_BarFeed chart (no LE_Feed add-on status file)')}")
    print(f"Feed instruments   : {', '.join(feed_instruments(cfg))}  (le_feed\\{FEED_INSTRUMENTS}: what the LE_Feed add-on writes)")
    for interval in ("5m", "1m", "1h"):
        df, why, full = feed.recent_bars("NQ", interval, "5d")
        if df is None:
            print(f"Bar feed {interval:3}       : NOT USABLE - {why}")
        else:
            print(f"Bar feed {interval:3}       : {len(df)} bars, last open {_et(int(df['time'].iloc[-1])):%a %m-%d %H:%M} ET ({why})")
    leftovers = [n for n in os.listdir(ad.incoming) if n.startswith("oif")] if st["incoming"] else []
    if leftovers:
        print(f"WARNING            : {len(leftovers)} unprocessed file(s) in incoming: {leftovers[:5]} (is the AT Interface on?)")
    return 0


def _cli_sim_check(cfg, roundtrip=False, add=False):
    ad = NinjaTraderAdapter(cfg)
    if not ad.sim:
        print(f"REFUSED: --sim-check / --sim-roundtrip run on Sim accounts only (got {ad.account})")
        return 2
    if ad.disabled:
        print(f"REFUSED: {ad.disabled}")
        return 2
    px, src = _last_price(ad.folder)
    if not px:
        print("No reference price (put LE_BarFeed on an MNQ 5-minute chart first)")
        return 2
    inst = ad._instruments()["micro"]
    print(f"Account {ad.account}, instrument {inst}, reference price {px:.2f} ({src})")
    if not roundtrip:
        oid = f"LECHK{int(time.time())}{_nonce()}"
        far = _tick(px * 0.8)
        r = ad._send_lines([place_line(ad.account, inst, "BUY", 1, "LIMIT", limit=far, order_id=oid)], "SIM CHECK")
        print(("OK  " if r["ok"] else "FAIL") + f" 1. file picked up by NinjaTrader: {r.get('file')} {r.get('error') or ''}")
        if not r["ok"]:
            return 1
        ok = ad._wait(lambda: ad.read_order(oid) is not None, 6)
        st = ad.read_order(oid)
        print(("OK  " if ok and st and st["state"] not in DEAD else "FAIL") + f" 2. order report outgoing/{oid}.txt: {st}")
        r2 = ad._send_lines([cancel_line(oid)], "SIM CHECK CANCEL")
        ok2 = ad._wait(lambda: (ad.read_order(oid) or {}).get("state") in DEAD, 6)
        print(("OK  " if ok2 else "FAIL") + f" 3. CANCEL -> {ad.read_order(oid)} {r2.get('error') or ''}")
        print(f"   connections reported: {ad.connections() or 'none'}")
        return 0 if ok and ok2 else 1
    # round trip: real (simulated) fills, so the market must be open. The session-time gate is relaxed for Sim only.
    fresh, why, _ = NinjaTraderBars(ad.folder).recent_bars("NQ", "5m", "1d")
    if fresh is None:
        print(f"REFUSED: the round trip needs a fresh price from LE_BarFeed ({why})")
        return 2
    px = float(fresh["close"].iloc[-1])
    ad._gate = lambda kind: None if kind != "entry" else (None if not ad.killed else {"ok": False, "error": "killed"})
    r = ad.send({"sym": ad.sym, "side": "buy", "qty": 1, "stop": px - 40, "target": px + 80, "entry_t": int(time.time())})
    print(("OK  " if r["ok"] else "FAIL") + f" 1. bracket: {json.dumps(r.get('legs'), default=str)} {r.get('error') or ''}")
    if not ad.legs:
        return 1
    lg = ad.legs[0]
    fill = lg["fill_px"] or px
    if add:
        return _cli_roundtrip_add(ad, lg, fill)
    m = ad.send({"side": "modify", "stop": fill - 20})
    print(("OK  " if m["ok"] else "FAIL") + f" 2. stop moved {lg['stop'] if m['ok'] else ''} -> {fill - 20:.2f}: {m.get('legs')} {m.get('error') or ''}")
    p = ad.position_for(lg["instrument"])
    print(f"   position file: {p}")
    x = ad.send({"side": "exit", "reason": "SIM ROUNDTRIP", "entry_t": lg["entry_t"]})
    print(("OK  " if x["ok"] else "FAIL") + f" 3. CLOSEPOSITION: flat confirmed {x.get('flat_confirmed')}, leftovers cancelled {x.get('cancelled_leftovers')} {x.get('error') or ''}")
    print(f"   stop {ad.read_order(lg['stop_id'])}, target {ad.read_order(lg['target_id'])}, position {ad.position_for(lg['instrument'])}")
    return 0 if r["ok"] and m["ok"] and x["ok"] else 1


def _cli_roundtrip_add(ad, lg, fill):
    """--sim-roundtrip-add, after step 1 (1 MNQ + stop/target): the scale-in route on Sim101. 2. the stop moves up (stands in
    for the breakeven: 10 pts under the fill, so a Sim stop cannot trigger at once), 3. a refused add (stop not yet where it
    was sized), 4. add 1 MNQ at market -> the one OCO pair resized to 2, 5. the PROOF (2026-10-26, no Orders-tab photo
    needed): the target is moved 20 pts under the market, so it fills at once; it must fill BOTH micros, the position must
    end flat and the OCO stop must be cancelled, i.e. NinjaTrader really holds the bracket at quantity 2, 6. CLOSEPOSITION
    (a safety net: flat already when the proof passed)."""
    be = _tick(fill - 10)
    m = ad.send({"side": "modify", "stop": be, "entry_t": lg["entry_t"]})
    print(("OK  " if m["ok"] else "FAIL") + f" 2. stop moved to {be:.2f} (stands in for breakeven): {m.get('legs')} {m.get('error') or ''}")
    bad = ad.send({"side": "add", "qty": 1, "dir": 1, "entry_t": lg["entry_t"], "n": 1, "stop": _tick(fill + 5)})
    print(("OK  " if not bad["ok"] else "FAIL") + f" 3. add sized at a stop the broker does not have -> refused: {bad.get('error')}")
    a = ad.send({"side": "add", "qty": 1, "dir": 1, "entry_t": lg["entry_t"], "n": 1, "stop": be, "target": lg["target"]})
    pos = ad.position_for(lg["instrument"])
    print(("OK  " if a["ok"] else "FAIL") + f" 4. add 1 MNQ: filled {a.get('filled')} @ {a.get('fill_px')}, bracket qty "
          f"{lg.get('bracket_qty')} {a.get('error') or a.get('note') or ''}")
    print(f"   position file: {pos}  (expected LONG 2)")
    print(f"   stop {ad.read_order(lg['stop_id'])}, target {ad.read_order(lg['target_id'])}")
    print(f"   NinjaTrader's Orders tab now: Sell 2 Stop Market @ {be:.2f} (id {lg['stop_id']}) and Sell 2 Limit "
          f"@ {lg['target']:.2f} (id {lg['target_id']}), one OCO group. The next step proves it by itself.")
    proof = _add_proof(ad, lg, min(float(fill), float(a.get("fill_px") or fill))) if a["ok"] else {"ok": False, "why": "no add"}
    print(("OK  " if proof["ok"] else "FAIL") + f" 5. proof: target moved under the market -> filled {proof.get('filled')} of 2, "
          f"position {proof.get('pos')}, OCO stop {proof.get('stop_state')} {proof.get('why') or ''}")
    x = ad.send({"side": "exit", "reason": "SIM ROUNDTRIP ADD", "entry_t": lg["entry_t"]})
    print(("OK  " if x["ok"] else "FAIL") + f" 6. CLOSEPOSITION (safety net): flat confirmed {x.get('flat_confirmed')}, leftovers "
          f"cancelled {x.get('cancelled_leftovers')} {x.get('error') or ''}")
    print(f"   position {ad.position_for(lg['instrument'])}")
    ok = m["ok"] and not bad["ok"] and a["ok"] and pos and pos["side"] == "LONG" and int(pos["qty"]) == 2 \
        and lg.get("bracket_qty") == 2 and proof["ok"] and x["ok"]
    if ok:
        print("SCALE-IN READY: NinjaTrader resized and filled the whole bracket (2 micros). Tell Claude it passed.")
    return 0 if ok else 1


def _add_proof(ad, lg, ref_px, wait_s=15.0) -> dict:
    """The scale-in proof: CHANGE the target of the resized OCO pair to 20 pts under ref_px (a long's sell limit under the
    market fills at once) and wait for it. Passes only when the target filled the whole position (2), the position file
    reads flat and the OCO stop is no longer working."""
    tgt = _tick(float(ref_px) - 20.0)
    r = ad._send_lines([change_line(lg["target_id"], limit=tgt)], "SIM PROOF: TARGET UNDER THE MARKET")
    if not r.get("ok"):
        return {"ok": False, "why": f"CHANGE not picked up: {r.get('error')}"}
    done = ad._wait(lambda: (ad.read_order(lg["target_id"]) or {}).get("state") == FILLED, wait_s)
    t = ad.read_order(lg["target_id"]) or {}
    ad._wait(lambda: (ad.position_for(lg["instrument"]) or {}).get("side") in (None, "FLAT")
             and (ad.read_order(lg["stop_id"]) or {}).get("state") in DEAD, 5.0)
    p = ad.position_for(lg["instrument"]) or {}
    st = (ad.read_order(lg["stop_id"]) or {}).get("state")
    filled = int(t.get("filled") or 0)
    flat = p.get("side") in (None, "FLAT") or int(p.get("qty") or 0) == 0
    ok = bool(done) and filled == 2 and flat and st in DEAD
    why = "" if ok else ("target not filled" if not done else f"filled {filled} (needs 2)" if filled != 2 else
                         "position not flat" if not flat else f"stop still {st}")
    return {"ok": ok, "filled": filled, "pos": f"{p.get('side') or 'FLAT'} {p.get('qty') or 0}", "stop_state": st, "why": why}


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="python -m engine.ninjatrader", description="NinjaTrader 8 route for the Liquidity Engine bot")
    ap.add_argument("--selftest", action="store_true", help="offline self-test (simulated NinjaTrader folders, no network)")
    ap.add_argument("--status", action="store_true", help="what the bot sees in NinjaTrader's folders and the bar feed")
    ap.add_argument("--sim-check", action="store_true", help="Sim only: far-away 1-lot MNQ limit order, then cancel it")
    ap.add_argument("--sim-roundtrip", action="store_true", help="Sim only, market open: 1 MNQ + stop/target, move the stop, flatten")
    ap.add_argument("--sim-roundtrip-add", action="store_true",
                    help="Sim only, market open: 1 MNQ + stop/target, stop up, scale-in add 1 (stop/target qty -> 2), flatten")
    ap.add_argument("--start", action="store_true", help="start the PC bot (server.py running) on NinjaTrader")
    ap.add_argument("--stop", action="store_true", help="stop the PC bot")
    ap.add_argument("--kill", action="store_true", help="kill switch: server kill, or FLATTENEVERYTHING directly when the server is down")
    ap.add_argument("--enable-auto-resume", action="store_true",
                    help="owner opt-in (once): the bot comes back on this exact real --account by itself after a crash, an update "
                         "or a reboot; needs --account and --confirm; every live lock still applies (engine/autoresume.py)")
    ap.add_argument("--disable-auto-resume", action="store_true", help="turn the real-account auto-resume off")
    ap.add_argument("--extra", action="store_true", help="with --enable-auto-resume: --account is one of the EXTRA accounts "
                                                          "(data/accounts.json); the bot's own account opt-in stays as it is")
    ap.add_argument("--account", default=None, help="NinjaTrader account name (Accounts tab 'Name'), default Sim101")
    ap.add_argument("--folder", default=None, help="Documents\\NinjaTrader 8 folder if not the default")
    ap.add_argument("--data", default="ninjatrader", choices=["ninjatrader", "yahoo"], help="bar source for --start (no_yahoo on, the default in live_model.json: always ninjatrader)")
    ap.add_argument("--confirm", default="", help=f"LIVE accounts only: the phrase '{LIVE_PHRASE}'")
    ap.add_argument("--instrument", default=None, help="force the instrument name, e.g. 'MNQ 12-26'")
    ap.add_argument("--contract", default=None, choices=["micro", "auto"], help="micro = MNQ only (default); auto = 10+ micros as NQ minis")
    ap.add_argument("--close-suffix", default=None, help="text added to the CLOSEPOSITION instrument, e.g. ' Globex'")
    ap.add_argument("--write-mode", default=None, choices=["direct", "move"], help="how order files reach incoming (default move)")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8766)))
    ap.add_argument("--confirm-reset", action="store_true",
                    help="after a NinjaTrader restart: you checked the account (positions / orders) in NinjaTrader; new entries are allowed again")
    ap.add_argument("--allow-account", default=None, metavar="NAME",
                    help="owner, once per real account: let the bot send orders to this exact NinjaTrader account Name "
                         "(data/nt_accounts_allow.json; Sim accounts are always allowed)")
    ap.add_argument("--disallow-account", default=None, metavar="NAME", help="remove a Name from the account allowlist")
    ap.add_argument("--list-allowed", action="store_true", help="print the account allowlist")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    if a.allow_account or a.disallow_account:
        try:
            cur = allow_account(a.allow_account or a.disallow_account, remove=bool(a.disallow_account))
        except ValueError as e:
            print(f"Not changed: {e}.")
            return 1
        print(("Allowed" if a.allow_account else "Removed") + f": {a.allow_account or a.disallow_account}. Allowlist now: "
              + (", ".join(cur) or "(empty: Sim accounts only)") + ". A running bot reads it at its next start.")
        return 0
    if a.list_allowed:
        cur = sorted(allowed_accounts())
        print("Accounts the bot may send orders to: " + (", ".join(cur) or "none") + " (+ every Sim / Playback account)")
        return 0
    opts = {"nt_account": a.account, "nt_folder": a.folder, "nt_instrument": a.instrument, "nt_contract": a.contract,
            "nt_close_suffix": a.close_suffix, "nt_write_mode": a.write_mode}
    cfg = {"adapter": "ninjatrader", "sym": "NQ", **{k: v for k, v in opts.items() if v}}
    if a.selftest:
        return 0 if selftest(verbose=not a.quiet) else 1
    if a.confirm_reset:
        path = os.path.join(os.path.dirname(STATE_PATH), RESET_OK_NAME)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"t": time.time(), "by": "owner: --confirm-reset"}, fh)
        print("Noted: you checked the account in NinjaTrader after its restart. The bot allows new entries again at its next poll.")
        return 0
    if a.status:
        return _cli_status(cfg)
    if a.sim_check or a.sim_roundtrip or a.sim_roundtrip_add:
        cfg.setdefault("nt_ack_wait_s", 15.0)            # Sim tests only: a busy NinjaTrader (chart just loaded) may take > 4 s
        if a.sim_roundtrip_add:
            cfg["nt_state_path"] = os.path.join(ROOT, "data", "ninjatrader_state_simcheck.json")   # never the bot's own state
        rc = _cli_sim_check(cfg, roundtrip=a.sim_roundtrip or a.sim_roundtrip_add, add=a.sim_roundtrip_add)
        if a.sim_roundtrip or a.sim_roundtrip_add:      # the launch checklist's "Sim roundtrip" line (data/sim_roundtrip_last.json)
            try:
                from . import launch_check
                launch_check.save_sim_result("add" if a.sim_roundtrip_add else "roundtrip", rc == 0,
                                             cfg.get("nt_account") or os.environ.get("NINJATRADER_ACCOUNT") or "Sim101",
                                             [f"exit code {rc}"])
            except Exception:
                pass
        return rc
    if a.disable_auto_resume:
        from . import autoresume
        was = autoresume.disable("owner: --disable-auto-resume")
        print("Auto-resume is OFF" + (" (it was on)." if was else " (it was not on).")
              + " The bot keeps running until you stop it; after a crash or reboot you start it by hand.")
        return 0
    if a.enable_auto_resume:
        from . import autoresume
        body = {"sym": "NQ", "tf": "5m", "adapter": "ninjatrader", "armed": True, "present": True, "poll_sec": 60,
                "data_source": a.data, **{k: v for k, v in cfg.items() if k.startswith("nt_")}}
        try:
            if a.extra:
                rec = autoresume.enable_extra(a.account or "", a.confirm)
                print(f"Auto-resume is ON for the extra account {a.account} too (with the bot's own account {rec['account']}).")
                return 0
            rec = autoresume.enable(a.account or "", a.confirm, body)
        except ValueError as e:
            print(f"Auto-resume NOT enabled: {e}.")
            return 1
        print(f"Auto-resume is ON for account {rec['account']} (accepted {rec['accepted_on']}). After a crash, an update or a "
              "Windows restart the bot starts again on this account by itself, only when NINJATRADER_LIVE=1 is in "
              ".env.local.ps1, NinjaTrader is connected, the kill switch was not used and there was no daily loss today.")
        print("Turn it off: python -m engine.ninjatrader --disable-auto-resume (the kill switch also turns it off).")
        try:
            st = _http(a.port, "/api/live/state")
        except Exception:
            print(f"The server is not running on port {a.port}: start scripts\\run_bot.ps1, then run this command again "
                  "(or --start with the same account) so the bot runs now.")
            return 0
        if st.get("running"):
            print("The bot is already running: nothing else to do (it was not restarted).")
            return 0
        a.start = True                                   # start it now, exactly as --start would
    if a.start:
        body = {"sym": "NQ", "tf": "5m", "adapter": "ninjatrader", "armed": True, "present": True, "poll_sec": 60,
                "data_source": a.data, **{k: v for k, v in cfg.items() if k.startswith("nt_")}}
        if a.confirm:
            body["confirm"] = a.confirm
        try:                                             # extra accounts (data/accounts.json, engine/multi_account.py)
            from . import multi_account
            body = multi_account.merge_into_start(body, a.confirm)
            if body.get("accounts"):
                print(f"Extra accounts: {', '.join(str(x.get('id')) for x in body['accounts'])} (python -m engine.multi_account --list)")
        except Exception as e:
            print(f"Extra accounts not read ({e.__class__.__name__}: {e}): starting the one account only")
        try:
            r = _http(a.port, "/api/live/start", body)
        except Exception as e:
            print(f"Server not reachable on port {a.port} ({e}). Start it first: scripts\\run_bot.ps1 (or python server.py).")
            return 2
        print("Bot start:", "OK" if r.get("ok") else r.get("error"))
        try:
            for ln in reversed(_http(a.port, "/api/live/state").get("log", [])[:8]):
                print("  ", _et(ln["t"]).strftime("%H:%M:%S"), ln["type"], ln["text"][:160])
        except Exception:
            pass
        return 0 if r.get("ok") else 1
    if a.stop:
        try:
            print(_http(a.port, "/api/live/stop", {}))
            return 0
        except Exception as e:
            print(f"Server not reachable ({e})")
            return 2
    if a.kill:
        try:
            from . import autoresume
            if autoresume.disable("kill switch (command line)"):
                print("Auto-resume turned OFF by the kill switch.")
        except Exception:
            pass
        try:
            print("Server kill switch:", _http(a.port, "/api/live/kill", {}))
            return 0
        except Exception as e:
            print(f"Server not reachable ({e}): writing FLATTENEVERYTHING to NinjaTrader directly")
        ad = NinjaTraderAdapter({**cfg, "nt_state_path": os.path.join(ROOT, "data", "ninjatrader_state.json")})
        r = ad.kill(scope="global")                      # the owner typed --kill: the global kill
        print("FLATTENEVERYTHING", "picked up by NinjaTrader" if r["ok"] else f"FAILED: {r.get('error')}")
        return 0 if r["ok"] else 1
    ap.print_help()
    return 0


# ---------------------------------------------------------------------- offline self-test
class _FakeNT:
    """Plays NinjaTrader 8 for the self-test: consumes oif*.txt from incoming/ and deletes it (as NinjaTrader does),
    checks every line against the documented grammar, simulates fills for one price and writes the documented
    outgoing/ files (order state, position, connection)."""

    def __init__(self, folder, price=25020.0, exchange="Globex"):
        self.inc, self.out = os.path.join(folder, "incoming"), os.path.join(folder, "outgoing")
        os.makedirs(self.inc, exist_ok=True)
        os.makedirs(self.out, exist_ok=True)
        self.exchange = exchange
        self.price = price
        self.orders: dict = {}
        self.pos: dict = {}                 # (account, instrument) -> [signed qty, avg]
        self.files: list = []               # (file name, [lines]) in processing order
        self.errors: list = []
        self.running = True
        self.reject = set()                 # order types NinjaTrader rejects
        self.hold_partial = False           # fill market orders half now, the rest on release()
        self.close_cancels = True           # CLOSEPOSITION cancels the working orders (documented)
        self.budget = None                  # process at most this many more files, then stop (a freeze mid-trade)
        self.hold_market = False            # accept market orders without filling them (a slow / thin market)
        self.slow_cancel = False            # CANCEL leaves the order CANCELPENDING (it can still fill)
        self.fill_on_change = False         # a CHANGE that makes a working order marketable fills it (the add proof)
        self.drop_types = set()             # order types taken but never created / reported (a file read empty, dropped)
        self._held: list = []
        self._write("Tradovate.txt", "CONNECTED")

    def _write(self, name, text):
        with open(os.path.join(self.out, name), "w", encoding="utf-8") as fh:
            fh.write(text)

    def _state(self, oid, o):
        avg = f"{o['avg']:.2f}" if o.get("avg") else "0"
        self._write(f"{oid}.txt", f"{o['state']};{o['filled']};{avg}")

    def _write_pos(self, acct, inst):
        q, avg = self.pos.get((acct, inst), [0, 0.0])
        side = "LONG" if q > 0 else "SHORT" if q < 0 else "FLAT"
        self._write(f"{inst} {self.exchange}_{acct}_Position.txt", f"{side};{abs(q)};{avg if q else 0}")

    def _fill(self, oid, qty, px):
        o = self.orders[oid]
        prev = o["filled"]
        o["filled"] += qty
        o["avg"] = ((o["avg"] or 0) * prev + px * qty) / o["filled"]
        o["state"] = FILLED if o["filled"] >= o["qty"] else PARTFILLED
        self._state(oid, o)
        key = (o["account"], o["instrument"])
        q, avg = self.pos.get(key, [0, 0.0])
        dq = qty if o["action"] == "BUY" else -qty
        nq = q + dq
        if q == 0 or (q > 0) == (dq > 0):
            avg = (avg * abs(q) + px * abs(dq)) / abs(nq) if nq else 0.0
        self.pos[key] = [nq, round(avg, 2) if nq else 0.0]
        self._write_pos(*key)
        if o["state"] == FILLED and o["oco"]:
            for k, x in self.orders.items():
                if k != oid and x["oco"] == o["oco"] and x["state"] in LIVE_STATES:
                    x["state"] = "CANCELLED"
                    self._state(k, x)

    def release(self):
        for oid, rest in self._held:
            self._fill(oid, rest, self.price)
        self._held = []

    def process(self, *_):
        if not self.running:
            return
        for name in sorted(os.listdir(self.inc)):
            if self.budget is not None:
                if self.budget <= 0:
                    return
                self.budget -= 1
            path = os.path.join(self.inc, name)
            with open(path, "rb") as fh:
                raw = fh.read()
            os.remove(path)
            if not (name.lower().startswith("oif") and name.lower().endswith(".txt")):
                self.errors.append((name, "Unknown OIF file type"))
                continue
            if raw.startswith(b"\xef\xbb\xbf"):
                self.errors.append((name, "byte-order mark"))
            lines = raw.decode("ascii").splitlines()
            self.files.append((name, lines))
            for ln in lines:
                self._do(ln)

    def _do(self, line):
        bad = validate_line(line)
        if bad:
            self.errors.append((line, bad))
            return
        f = line.split(";")
        cmd = f[0]
        if cmd == "PLACE" and f[5] in self.drop_types:
            return
        if cmd == "PLACE":
            oid = f[10]
            o = {"account": f[1], "instrument": f[2], "action": f[3], "qty": int(f[4]), "type": f[5], "limit": float(f[6] or 0),
                 "stop": float(f[7] or 0), "oco": f[9], "filled": 0, "avg": None, "state": "ACCEPTED"}
            self.orders[oid] = o
            if o["type"] in self.reject:
                o["state"] = "REJECTED"
                self._state(oid, o)
            elif o["type"] == "MARKET" and self.hold_market:
                self._state(oid, o)
            elif o["type"] == "MARKET":
                if self.hold_partial and o["qty"] > 1:
                    self._fill(oid, o["qty"] // 2, self.price)
                    self._held.append((oid, o["qty"] - o["qty"] // 2))
                else:
                    self._fill(oid, o["qty"], self.price)
            else:
                o["state"] = "WORKING"
                self._state(oid, o)
        elif cmd == "CHANGE":
            o = self.orders.get(f[10])
            if o and o["state"] in LIVE_STATES:
                o["qty"] = int(f[4]) or o["qty"]
                o["limit"] = float(f[6]) or o["limit"]
                o["stop"] = float(f[7]) or o["stop"]
                self._state(f[10], o)
                if self.fill_on_change:            # a limit / stop changed through the market fills at once
                    self.move(self.price)
        elif cmd == "CANCEL":
            o = self.orders.get(f[10])
            if o and o["state"] in LIVE_STATES:
                o["state"] = "CANCELPENDING" if self.slow_cancel else "CANCELLED"
                self._state(f[10], o)
        elif cmd in ("CLOSEPOSITION", "FLATTENEVERYTHING"):
            keys = [(f[1], f[2])] if cmd == "CLOSEPOSITION" else list(self.pos)
            for k, o in self.orders.items():
                if o["state"] in LIVE_STATES and ((o["account"], o["instrument"]) in keys or cmd == "FLATTENEVERYTHING") \
                        and (self.close_cancels or cmd == "FLATTENEVERYTHING"):
                    o["state"] = "CANCELLED"
                    self._state(k, o)
            for key in keys:
                q = self.pos.get(key, [0, 0.0])[0]
                if q:
                    cid = f"NTCLOSE{len(self.orders)}"
                    self.orders[cid] = {"account": key[0], "instrument": key[1], "action": "SELL" if q > 0 else "BUY", "qty": abs(q),
                                        "type": "MARKET", "limit": 0, "stop": 0, "oco": "", "filled": 0, "avg": None, "state": "ACCEPTED"}
                    self._fill(cid, abs(q), self.price)

    def move(self, price):
        self.price = price
        for oid, o in list(self.orders.items()):
            if o["state"] not in LIVE_STATES:
                continue
            buy = o["action"] == "BUY"
            if o["type"] == "STOPMARKET" and ((buy and price >= o["stop"]) or (not buy and price <= o["stop"])):
                self._fill(oid, o["qty"] - o["filled"], o["stop"])
            elif o["type"] == "LIMIT" and ((buy and price <= o["limit"]) or (not buy and price >= o["limit"])):
                self._fill(oid, o["qty"] - o["filled"], o["limit"])


def selftest(verbose=True) -> bool:
    """Bracket -> fill report -> stop to breakeven -> flatten -> kill against simulated NinjaTrader folders, with the exact
    OIF lines checked against the documented formats; the live gates; failure paths; the bar feed; LiveBot wiring."""
    import shutil
    import tempfile
    import pandas as pd
    tmp = tempfile.mkdtemp(prefix="le_nt_selftest_")
    saved_env = {k: os.environ.get(k) for k in (LIVE_ENV, "NINJATRADER_ACCOUNT", "NINJATRADER_FOLDER", ALLOW_ENV)}
    for k in saved_env:
        os.environ.pop(k, None)
    checks = []

    def check(name, cond, detail=""):
        checks.append((name, bool(cond), detail))
        if verbose:
            print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  -- {detail}" if detail and not cond else ""))
        return bool(cond)

    try:
        folder = os.path.join(tmp, "NinjaTrader 8")
        fake = _FakeNT(folder)
        now = [dt.datetime(2026, 10, 21, 10, 5, tzinfo=ET).timestamp()]      # Wednesday 10:05 ET
        alerts = []

        def make(cfg_extra=None, nt=fake):
            cfg = {"adapter": "ninjatrader", "sym": "NQ", "armed": True, "nt_folder": folder, "params": {"max_micros": 40, "flat_mod": 955},
                   "nt_max_entries_day": 999, "nt_state_path": os.path.join(tmp, "nt_state.json"), "nt_audit_log": os.path.join(tmp, "oif.log"), **(cfg_extra or {})}
            ad = NinjaTraderAdapter(cfg, clock=lambda: now[0])
            ad._sleep = lambda s: (nt.process(), now.__setitem__(0, now[0] + s))
            ad._alert_fn = alerts.append
            return ad

        def lines_since(k):
            return [ln for _, ls in fake.files[k:] for ln in ls]

        if verbose:
            print("NinjaTrader 8 ATI offline self-test")
        # ---- 0. grammar: our builders produce exactly the documented formats
        check("grammar: documented templates compile and FLATTENEVERYTHING has 12 semicolons",
              FLATTEN_EVERYTHING == "FLATTENEVERYTHING;;;;;;;;;;;;" and all(len(v.split(";")) == 13 for v in DOC_FORMATS.values()))
        check("grammar: the validator rejects a wrong field count, a comma decimal and an unknown order type",
              validate_line("PLACE;Sim101;MNQ 12-26;BUY;1;MARKET;0;0;DAY;;;") and validate_line("CHANGE;;;;0;;0;25020,25;;;X;;")
              and validate_line("PLACE;Sim101;MNQ 12-26;BUY;1;STOP;0;1;DAY;;;;"))
        check("instrument: front month in NinjaTrader naming with the 8-day roll",
              nt_instrument("MNQ", dt.date(2026, 10, 17)) == "MNQ 12-26" and nt_instrument("MNQ", dt.date(2026, 12, 9)) == "MNQ 12-26"
              and nt_instrument("MNQ", dt.date(2026, 12, 10)) == "MNQ 03-27" and nt_instrument("NQ", dt.date(2029, 12, 20)) == "NQ 03-30",
              f"{nt_instrument('MNQ', dt.date(2026, 10, 17))} / {nt_instrument('MNQ', dt.date(2026, 12, 10))}")
        check("accounts: Sim101 / Sim102 / Playback101 are simulation; MFFU-style names are not",
              is_sim("Sim101") and is_sim("Sim102") and is_sim("Playback101") and not is_sim("SIM-MFFU-1") and not is_sim("MFFUEV12345") and not is_sim("Sim"))

        # ---- 1. bracket: market entry, then the OCO stop + target once the fill is reported
        ad = make()
        check("adapter: Sim101 enabled, folder found, front month MNQ 12-26", not ad.disabled and ad.folder_status()["incoming"]
              and ad._instruments()["micro"] == "MNQ 12-26", str(ad.disabled))
        T = int(dt.datetime(2026, 10, 21, 10, 0, tzinfo=ET).timestamp())
        k = len(fake.files)
        r = ad.send({"sym": "NQ", "side": "buy", "qty": 2, "stop": 24990.13, "target": 25080.0, "entry": 25020.0, "entry_t": T})
        lg = ad.legs[0] if ad.legs else {}
        E, S, TG, O = lg.get("entry_id"), lg.get("stop_id"), lg.get("target_id"), lg.get("oco")
        exp_entry = [f"PLACE;Sim101;MNQ 12-26;BUY;2;MARKET;0;0;DAY;;{E};;"]
        exp_bracket = [f"PLACE;Sim101;MNQ 12-26;SELL;2;STOPMARKET;0;24990.25;DAY;{O};{S};;",
                       f"PLACE;Sim101;MNQ 12-26;SELL;2;LIMIT;25080.00;0;DAY;{O};{TG};;"]
        got = [ls for _, ls in fake.files[k:]]
        check("bracket: ok, entry file = 1 MARKET line, then 1 file with the STOPMARKET + LIMIT OCO pair (exact lines)",
              r["ok"] and got == [exp_entry, exp_bracket], json.dumps(got))
        _box = os.path.join(ad.folder, "le_outbox")
        check("order files: written whole in le_outbox\\ then renamed into incoming\\ (never copied, never written in place)",
              ad.write_mode == "move" and os.path.isdir(_box) and not os.listdir(_box)
              and os.path.dirname(os.path.abspath(_box)) == os.path.dirname(os.path.abspath(ad.incoming)),
              f"mode {ad.write_mode}, outbox {os.listdir(_box) if os.path.isdir(_box) else 'missing'}")
        check("bracket: NinjaTrader shows LONG 2 MNQ, stop + target WORKING, leg protected",
              ad.position_for("MNQ 12-26")["side"] == "LONG" and ad.position_for("MNQ 12-26")["qty"] == 2
              and ad.read_order(S)["state"] == "WORKING" and ad.read_order(TG)["state"] == "WORKING" and lg["status"] == "protected")
        check("bracket: one position at a time (a second entry is refused while the bracket is open)",
              "still open" in ad.send({"sym": "NQ", "side": "buy", "qty": 1, "stop": 24990, "target": 25080, "entry": 25020})["error"])
        # ---- 2. breakeven: CHANGE the stop
        k = len(fake.files)
        r = ad.send({"side": "modify", "stop": 25020.25, "entry_t": T})
        check("breakeven: one CHANGE line, quantity and limit 0 (= unchanged), new stop price, our stop order id",
              r["ok"] and lines_since(k) == [f"CHANGE;;;;0;;0;25020.25;;;{S};;"] and fake.orders[S]["stop"] == 25020.25, json.dumps(lines_since(k)))
        # ---- 3. restart: a new adapter picks the open bracket up from the state file
        ad2 = make()
        check("restart: open bracket restored from the state file (same ids)", len(ad2.legs) == 1 and ad2.legs[0]["stop_id"] == S)
        # ---- 4. flatten
        k = len(fake.files)
        r = ad2.send({"sym": "NQ", "side": "exit", "qty": 2, "reason": "TIME STOP", "entry_t": T})
        check("exit: CLOSEPOSITION;Sim101;MNQ 12-26;;;;;;;;;; -> flat confirmed, bracket cancelled, nothing left to cancel",
              r["ok"] and lines_since(k) == ["CLOSEPOSITION;Sim101;MNQ 12-26;;;;;;;;;;"] and r["flat_confirmed"]
              and fake.orders[S]["state"] == "CANCELLED" and fake.orders[TG]["state"] == "CANCELLED" and not ad2.legs, json.dumps(lines_since(k)))
        ad = ad2
        r = ad.send({"sym": "NQ", "side": "exit", "reason": "TARGET", "entry_t": T})
        check("exit: a sync exit when already flat is harmless (CLOSEPOSITION, ok)", r["ok"])
        # ---- 5. leftovers: if CLOSEPOSITION left a leg working, the adapter cancels it once flat is confirmed
        fake.close_cancels = False
        now[0] += 600
        r = ad.send({"sym": "NQ", "side": "sell", "qty": 3, "stop": 25060.0, "target": 24950.0, "entry": 25020.0, "entry_t": T + 600})
        lg = ad.legs[0]
        k = len(fake.files)
        r2 = ad.send({"sym": "NQ", "side": "exit", "reason": "GIVEBACK", "entry_t": T + 600})
        check("exit: legs still working after CLOSEPOSITION -> CANCEL;;;;;;;;;;<id>;; for each",
              r["ok"] and r2["ok"] and lines_since(k) == ["CLOSEPOSITION;Sim101;MNQ 12-26;;;;;;;;;;", f"CANCEL;;;;;;;;;;{lg['stop_id']};;",
                                                          f"CANCEL;;;;;;;;;;{lg['target_id']};;"], json.dumps(lines_since(k)))
        fake.close_cancels = True
        # ---- 6. the bracket closes the trade on its own (target), tick() notices
        now[0] += 600
        r = ad.send({"sym": "NQ", "side": "buy", "qty": 1, "stop": 25000.0, "target": 25040.0, "entry": 25020.0, "entry_t": T + 1200})
        lg = ad.legs[0]
        fake.move(25041.0)
        ad.tick()
        check("bracket: target fills, OCO cancels the stop, tick() retires the leg",
              r["ok"] and not ad.legs and ad.history[-1]["closed"] == "target filled" and fake.orders[lg["stop_id"]]["state"] == "CANCELLED")
        # ---- 7. partial fill: bracket the filled part, resize when the rest fills
        fake.move(25020.0)
        now[0] += 600
        fake.hold_partial = True
        r = ad.send({"sym": "NQ", "side": "buy", "qty": 4, "stop": 25000.0, "target": 25060.0, "entry": 25020.0, "entry_t": T + 1800})
        lg = ad.legs[0]
        part_ok = r["ok"] and lg["bracket_qty"] == 2 and fake.orders[lg["stop_id"]]["qty"] == 2
        fake.hold_partial = False
        fake.release()
        k = len(fake.files)
        ad.tick()
        check("partial fill: stop/target for the 2 filled, then CHANGE;;;;4;;0;0;;;<id>;; on both once all 4 fill",
              part_ok and lines_since(k) == [f"CHANGE;;;;4;;0;0;;;{lg['stop_id']};;", f"CHANGE;;;;4;;0;0;;;{lg['target_id']};;"]
              and fake.orders[lg["target_id"]]["qty"] == 4, json.dumps(lines_since(k)))
        # ---- 8. kill: the owner's global kill = FLATTENEVERYTHING, then no new entries (account-scoped kill: tests/test_nt_exec_audit.py)
        k = len(fake.files)
        r = ad.send({"sym": "NQ", "side": "exit", "reason": "KILL SWITCH", "scope": "global"})
        check("kill: FLATTENEVERYTHING;;;;;;;;;;;; -> NinjaTrader flat, legs retired, new entries refused",
              r["ok"] and lines_since(k) == ["FLATTENEVERYTHING;;;;;;;;;;;;"] and ad.position_for("MNQ 12-26")["side"] == "FLAT" and not ad.legs
              and "kill" in ad.send({"sym": "NQ", "side": "buy", "qty": 1, "stop": 25000, "target": 25040, "entry": 25020})["error"])
        # ---- 9. gates
        ad = make()
        ad.killed = False
        n0 = len(fake.files)
        r41 = ad.send({"sym": "NQ", "side": "buy", "qty": 41, "stop": 25000, "target": 25040, "entry": 25020})
        r5m = ad.send({"sym": "NQ", "side": "buy", "qty": 50, "minis": 5, "micros": 0, "stop": 25000, "target": 25040, "entry": 25020})
        rside = ad.send({"sym": "NQ", "side": "buy", "qty": 1, "stop": 25030, "target": 25040, "entry": 25020})
        late = now[0]
        now[0] = dt.datetime(2026, 10, 21, 15, 56, tzinfo=ET).timestamp()
        rlate = ad.send({"sym": "NQ", "side": "buy", "qty": 1, "stop": 25000, "target": 25040, "entry": 25020})
        now[0] = dt.datetime(2026, 10, 24, 10, 0, tzinfo=ET).timestamp()
        rwknd = ad.send({"sym": "NQ", "side": "buy", "qty": 1, "stop": 25000, "target": 25040, "entry": 25020})
        now[0] = late
        check("gates: 41 micros / 5 minis / stop on the wrong side / 15:56 ET / Saturday are all refused, no file written",
              "exceeds max_micros" in r41["error"] and "5 minis" in r5m["error"] and "wrong side" in rside["error"]
              and "outside the session" in rlate["error"] and "outside the session" in rwknd["error"] and len(fake.files) == n0)
        auto = make({"nt_contract": "auto"})
        k = len(fake.files)
        r = auto.send({"sym": "NQ", "side": "sell", "qty": 12, "stop": 25060.0, "target": 24950.0, "entry": 25020.0, "entry_t": T + 3600})
        entry_lines = fake.files[k][1] if len(fake.files) > k else []
        check("contract auto: 12 micros -> 1 NQ 12-26 + 2 MNQ 12-26, one entry file with both lines, each leg bracketed",
              r["ok"] and [ln.split(";")[2:5] for ln in entry_lines] == [["NQ 12-26", "SELL", "1"], ["MNQ 12-26", "SELL", "2"]]
              and len(auto.legs) == 2 and all(x["status"] == "protected" for x in auto.legs), json.dumps(entry_lines))
        auto.send({"sym": "NQ", "side": "exit", "reason": "TIME", "entry_t": T + 3600})
        os.environ.pop(LIVE_ENV, None)
        live1 = make({"nt_account": "MFFUEV12345", "armed": False})
        n0 = len(fake.files)
        rl = live1.send({"sym": "NQ", "side": "buy", "qty": 1, "stop": 25000, "target": 25040, "entry": 25020})
        live2 = make({"nt_account": "MFFUEV12345", "confirm": "i accept"})
        live3 = make({"nt_account": "MFFUEV12345", "confirm": LIVE_PHRASE})
        os.environ[LIVE_ENV] = "1"
        allow = os.path.join(tmp, "allow.json")
        live6 = make({"nt_account": "MFFUEV12345", "confirm": LIVE_PHRASE, "nt_allow_path": allow})     # not allowlisted yet
        allow_account("MFFUEV12345", path=allow)
        live4 = make({"nt_account": "MFFUEV12345", "confirm": LIVE_PHRASE, "nt_allow_path": allow})
        live5 = make({"nt_account": "MFFUEV12345", "confirm": LIVE_PHRASE, "armed": False, "nt_allow_path": allow})
        os.environ.pop(LIVE_ENV, None)
        check("live gate: a non-Sim account is refused without armed, without the exact phrase, without NINJATRADER_LIVE=1, "
              "or when its Name is not in the account allowlist",
              live1.disabled and "not armed" in live1.disabled and "REFUSED" in rl["error"] and len(fake.files) == n0
              and "phrase" in live2.disabled and LIVE_ENV in live3.disabled and live5.disabled
              and "allowlist" in (live6.disabled or ""), f"{live1.disabled} | {live2.disabled} | {live3.disabled} | {live6.disabled}")
        check("live gate: armed + phrase + NINJATRADER_LIVE=1 + allowlisted enables it (env 'live' for the trade memory)",
              live4.disabled is None and live4.env == "live" and not live4.sim, str(live4.disabled))
        # ---- 10. NinjaTrader not running: the file is withdrawn, never left to run late
        fake.running = False
        ad = make()
        now[0] += 600
        r = ad.send({"sym": "NQ", "side": "buy", "qty": 1, "stop": 25000, "target": 25040, "entry": 25020, "entry_t": T + 4200})
        left = [n for n in os.listdir(fake.inc) if n.startswith("oif")]
        check("NinjaTrader off: entry not picked up -> withdrawn (deleted), ok False, nothing left in incoming",
              not r["ok"] and "did not pick up" in r["error"] and not left and not ad.legs and len(ad.withdrawn) == 1, r.get("error", ""))
        fake.running = True
        now[0] += 120
        ad.tick()
        check("NinjaTrader off: the withdrawn entry is watched, then dropped after the timeout", not ad.withdrawn)
        # ---- 11. rejections
        fake.reject = {"MARKET"}
        r = ad.send({"sym": "NQ", "side": "buy", "qty": 1, "stop": 25000, "target": 25040, "entry": 25020, "entry_t": T + 4800})
        check("entry REJECTED: no stop/target sent, ok False, nothing tracked", not r["ok"] and "REJECTED" in r["error"] and not ad.legs
              and fake.files[-1][1][0].split(";")[5] == "MARKET")
        # an MFFU LOCK (2026-11-17, ATLAS's passed 25K): the order file says REJECTED, NinjaTrader's Log has the risk desk's text
        fake.reject = {"MARKET"}
        os.makedirs(os.path.join(folder, "log"), exist_ok=True)
        with open(os.path.join(folder, "log", "log.20261021.00000.txt"), "w", encoding="utf-8") as fh:
            fh.write(f"2026-10-21 10:06:00:000|1|4|Order='LE{int(T + 4860)}abcdE/Sim101' Name='LE{int(T + 4860)}abcdE' New state='Rejected' "
                     "Instrument='MNQ 12-26' Action='Buy' Native error='Your maximum order quantity has been met. Please contact "
                     "support. Limit: 0 Current: 1. Scope: MNQ Rule #3787'\n")
        r = ad.send({"sym": "NQ", "side": "buy", "qty": 1, "stop": 25000, "target": 25040, "entry": 25020, "entry_t": T + 4860})
        lk = locked_reject(ad, T + 4860, r, now=now[0])
        check("entry REJECTED by MFFU's risk desk (Limit: 0, Rule #3787): answer carries 'locked', locked_reject() says so; "
              "a plain REJECTED / the bot's REFUSED are not a lock",
              not r["ok"] and "Limit: 0" in str(r.get("locked")) and lk and "Rule #3787" in lk and not ad.legs
              and lock_reason("MNQ 12-26: entry REJECTED") is None and lock_reason("REFUSED: kill switch is engaged") is None
              and locked_reject(ad, T + 4800, {"ok": False, "error": "MNQ 12-26: entry REJECTED"}, now=now[0]) is None, r)
        fake.reject = {"STOPMARKET"}
        k = len(fake.files)
        r = ad.send({"sym": "NQ", "side": "buy", "qty": 1, "stop": 25000, "target": 25040, "entry": 25020, "entry_t": T + 5400})
        check("stop REJECTED after the fill: flattened at once (CLOSEPOSITION), alert raised, ok False",
              not r["ok"] and "flattened" in r["error"] and lines_since(k)[-1] == "CLOSEPOSITION;Sim101;MNQ 12-26;;;;;;;;;;"
              and ad.position_for("MNQ 12-26")["side"] == "FLAT" and any("REJECTED" in a for a in alerts), r.get("error", ""))
        fake.reject = set()
        fake.budget = 1                       # NinjaTrader takes the entry file, then freezes before the bracket file
        r = ad.send({"sym": "NQ", "side": "buy", "qty": 1, "stop": 25000, "target": 25040, "entry": 25020, "entry_t": T + 6000})
        lg = ad.legs[0] if ad.legs else {}
        unprot = not r["ok"] and lg.get("status") == "unprotected" and any("UNPROTECTED" in a for a in alerts)
        fake.budget = None
        ad.tick()                             # NinjaTrader is back: the withdrawn bracket goes in with the same ids
        check("freeze after the fill: alert + 'unprotected', the next tick places the stop and target",
              unprot and lg.get("status") == "protected" and fake.orders[lg["stop_id"]]["state"] == "WORKING", r.get("error", ""))
        ad.send({"sym": "NQ", "side": "exit", "reason": "TIME", "entry_t": T + 6000})
        fake.budget = 1
        r = ad.send({"sym": "NQ", "side": "buy", "qty": 1, "stop": 25000, "target": 25040, "entry": 25020, "entry_t": T + 6600})
        lg = ad.legs[0] if ad.legs else {}
        fake.budget = None
        fake._do(close_line("Sim101", "MNQ 12-26"))           # closed by hand while the bracket was missing
        k = len(fake.files)
        ad.tick()
        check("freeze, then closed by hand: no stop/target is placed afterwards (they would be naked)",
              not ad.legs and len(fake.files) == k and ad.history[-1]["closed"] == "closed while unprotected")
        # ---- 11a. S1 2026-11-15: the bracket file is picked up but dropped (no stop report ever): flattened, never naked
        fake.drop_types = {"STOPMARKET", "LIMIT"}
        r = ad.send({"sym": "NQ", "side": "buy", "qty": 1, "stop": 25000, "target": 25040, "entry": 25020, "entry_t": T + 6900})
        fake.drop_types = set()
        lg = ad.legs[0] if ad.legs else {}
        silent = lg.get("status") == "protected" and lg.get("stop_id") not in fake.orders
        ad.tick()
        early = bool(ad.legs) and ad.position_for("MNQ 12-26")["side"] == "LONG"
        now[0] += 31
        k = len(fake.files)
        ad.tick()
        check("bracket dropped by NinjaTrader (no stop report 30 s after the fill): alert + CLOSEPOSITION + blind CANCEL of "
              "the bracket ids; untouched before 30 s",
              silent and early and not ad.legs and ad.position_for("MNQ 12-26")["side"] == "FLAT"
              and "CLOSEPOSITION;Sim101;MNQ 12-26;;;;;;;;;;" in lines_since(k)
              and f"CANCEL;;;;;;;;;;{lg.get('stop_id')};;" in lines_since(k) and any("never reported" in a for a in alerts),
              f"silent={silent} early={early} legs={len(ad.legs)} lines={lines_since(k)}")
        # ---- 11a2. S1 2026-11-15: a crash right after an order file (before the state save) never leaves a naked position
        class _Crash(Exception):
            pass

        def _crash_after(label_want, _orig=ad._send_lines):
            def f(lines, label):
                r_ = _orig(lines, label)
                if label == label_want:
                    raise _Crash(label)
                return r_
            return f
        ad._send_lines = _crash_after("ENTRY")
        try:
            ad.place_bracket({"sym": "NQ", "side": "buy", "qty": 1, "stop": 25000, "target": 25040, "entry": 25020, "entry_t": T + 6950})
        except _Crash:
            pass
        del ad._send_lines
        ad3 = make()
        lg3 = ad3.legs[0] if ad3.legs else {}
        ad3.tick()
        n_stop = sum(1 for _, ls in fake.files for ln in ls if lg3.get("stop_id") and lg3["stop_id"] in ln and ln.startswith("PLACE"))
        check("crash after the entry file, before the state save: the restarted adapter finds the leg (write-ahead), sees "
              "the fill and places the stop + target once",
              lg3.get("status") == "protected" and fake.orders.get(lg3.get("stop_id"), {}).get("state") == "WORKING" and n_stop == 1,
              f"legs={len(ad3.legs)} status={lg3.get('status')} n_stop={n_stop}")
        ad3.send({"sym": "NQ", "side": "exit", "reason": "TIME", "entry_t": T + 6950})
        ad._restore()
        ad._send_lines = _crash_after("BRACKET")
        try:
            ad.place_bracket({"sym": "NQ", "side": "buy", "qty": 1, "stop": 25000, "target": 25040, "entry": 25020, "entry_t": T + 6970})
        except _Crash:
            pass
        del ad._send_lines
        ad3 = make()
        lg3 = ad3.legs[0] if ad3.legs else {}
        k = len(fake.files)
        ad3.tick()
        ad3.tick()
        n_stop = sum(1 for _, ls in fake.files for ln in ls if lg3.get("stop_id") and lg3["stop_id"] in ln and ln.startswith("PLACE"))
        check("crash after the bracket file, before the state save: the restarted adapter never sends the stop / target ids "
              "twice (one PLACE each), the leg is protected and the bracket sized to the fill",
              lg3.get("status") == "protected" and n_stop == 1 and lg3.get("bracket_qty") == 1
              and fake.orders.get(lg3.get("stop_id"), {}).get("state") == "WORKING",
              f"status={lg3.get('status')} n_stop={n_stop} bq={lg3.get('bracket_qty')} lines={lines_since(k)}")
        ad3.send({"sym": "NQ", "side": "exit", "reason": "TIME", "entry_t": T + 6970})
        ad._restore()
        # ---- 11a3. S1 2026-11-15: the per-day entry cap, independent of the bot's guards (persisted over a restart)
        ad.max_entries_day = ad.entries_day["n"]
        k = len(fake.files)
        r = ad.send({"sym": "NQ", "side": "buy", "qty": 1, "stop": 25000, "target": 25040, "entry": 25020, "entry_t": T + 6990})
        ad_r = make({"nt_max_entries_day": ad.entries_day["n"]})
        r2 = ad_r.send({"sym": "NQ", "side": "buy", "qty": 1, "stop": 25000, "target": 25040, "entry": 25020, "entry_t": T + 6995})
        check("entry cap: past nt_max_entries_day entries on the trading day the entry is refused (no file), also after a "
              "restart (the count is in the state file)",
              not r["ok"] and "hard cap" in r["error"] and not r2["ok"] and "hard cap" in r2["error"] and len(fake.files) == k
              and ad_r.entries_day["n"] > 1, f"{r.get('error')} / {r2.get('error')} n={ad_r.entries_day}")
        ad.max_entries_day = 999
        # ---- 11b. order states from the LIT report ch.27: CANCEL PENDING and partial exit fills
        fake.hold_market, fake.slow_cancel = True, True
        r = ad.send({"sym": "NQ", "side": "buy", "qty": 2, "stop": 25000, "target": 25040, "entry": 25020, "entry_t": T + 7200})
        lg = ad.legs[0] if ad.legs else {}
        pend = not r["ok"] and lg.get("status") == "pending"
        now[0] += ad.pending_timeout + 1
        ad.tick()                             # timeout: CANCEL sent, NinjaTrader leaves it CANCELPENDING
        cp = lg.get("status") == "cancel_pending" and lg in ad.legs and fake.orders[lg["entry_id"]]["state"] == "CANCELPENDING"
        refused = not ad.send({"sym": "NQ", "side": "buy", "qty": 1, "stop": 25000, "target": 25040, "entry": 25020,
                               "entry_t": T + 7260})["ok"]
        fake._fill(lg["entry_id"], 2, fake.price)          # the execution arrives while the cancel is pending
        ad.tick()
        check("cancel pending: an unfilled entry's CANCEL keeps the leg watched; a late fill gets its stop + target",
              pend and cp and refused and lg.get("status") == "protected" and fake.orders[lg["stop_id"]]["state"] == "WORKING"
              and fake.orders[lg["stop_id"]]["qty"] == 2, f"pend={pend} cp={cp} refused={refused} status={lg.get('status')}")
        ad.send({"sym": "NQ", "side": "exit", "reason": "TIME", "entry_t": T + 7200})
        fake.slow_cancel = False
        r = ad.send({"sym": "NQ", "side": "buy", "qty": 1, "stop": 25000, "target": 25040, "entry": 25020, "entry_t": T + 7800})
        lg = ad.legs[0] if ad.legs else {}
        now[0] += ad.pending_timeout + 1
        ad.tick()                             # CANCEL sent and confirmed CANCELLED by NinjaTrader
        ad.tick()
        check("cancel confirmed: CANCELLED resolves the unfilled entry, nothing protected, the leg retired",
              not ad.legs and ad.history[-1]["closed"].startswith("entry cancelled") and lg.get("stop_id") not in fake.orders,
              ad.history[-1]["closed"] if ad.history else "")
        fake.hold_market = False
        r = ad.send({"sym": "NQ", "side": "buy", "qty": 4, "stop": 25000, "target": 25060, "entry": 25020, "entry_t": T + 8400})
        lg = ad.legs[0] if ad.legs else {}
        fake._fill(lg["stop_id"], 1, 25000.0)              # the stop fills 1 of 4: 3 still open
        k = len(fake.files)
        ad.tick()
        check("partial exit: the stop fills 1 of 4 -> the target is resized to 3 (CHANGE;;;;3;;0;0;;;<id>;;)",
              r["ok"] and lines_since(k) == [f"CHANGE;;;;3;;0;0;;;{lg['target_id']};;"] and fake.orders[lg["target_id"]]["qty"] == 3,
              json.dumps(lines_since(k)))
        ad.send({"sym": "NQ", "side": "exit", "reason": "TIME", "entry_t": T + 8400})
        # ---- 11c. CME early close (LIT report ch.28): entries stop 15 min and positions go flat 5 min before the halt
        from .lit_live import early_close
        ecs = [early_close(x) for x in ("2026-11-27", "2026-12-24", "2026-09-07", "2026-04-03", "2026-10-21")]
        keep_now = now[0]
        now[0] = dt.datetime(2026, 11, 27, 12, 0, tzinfo=ET).timestamp()
        r_ok = ad.send({"sym": "NQ", "side": "buy", "qty": 1, "stop": 25000, "target": 25040, "entry": 25020, "entry_t": int(now[0])})
        lg = ad.legs[0] if ad.legs else {}
        now[0] = dt.datetime(2026, 11, 27, 13, 11, tzinfo=ET).timestamp()
        k = len(fake.files)
        ad.tick()
        flat_ok = not ad.legs and ad.history[-1]["closed"] == "flat time" and "CLOSEPOSITION;Sim101;MNQ 12-26;;;;;;;;;;" in lines_since(k)
        now[0] = dt.datetime(2026, 11, 27, 13, 2, tzinfo=ET).timestamp()
        r_late = ad.send({"sym": "NQ", "side": "buy", "qty": 1, "stop": 25000, "target": 25040, "entry": 25020, "entry_t": int(now[0])})
        check("early close: halts 13:15 (Black Friday, Dec 24) / 13:00 (Labor Day) / 09:15 (Good Friday); a 12:00 entry is "
              "flattened at 13:11, a 13:02 entry is refused",
              ecs == [795, 795, 780, 555, None] and r_ok["ok"] and flat_ok and not r_late["ok"] and "early close" in r_late["error"],
              f"{ecs} ok={r_ok['ok']} flat={flat_ok} late={r_late.get('error')}")
        now[0] = keep_now
        # ---- 12. defensive parsing
        with open(os.path.join(fake.out, "garbage.txt"), "w") as fh:
            fh.write("hello;;world")
        with open(os.path.join(fake.out, "LEBROKEN.txt"), "w") as fh:
            fh.write("FILLED;two;x")
        with open(os.path.join(fake.out, f"MNQ 12-26 Globex_Sim102_Position.txt"), "w") as fh:
            fh.write("LONG; 3; 25010.5")
        check("parsing: spaces after semicolons, junk files and bad numbers never raise",
              parse_position("LONG; 3; 25010.5") == {"side": "LONG", "qty": 3, "avg": 25010.5} and ad.read_order("LEBROKEN") is None
              and parse_order_state("Filled;2;25020.25")["state"] == FILLED and parse_order_state("") is None
              and isinstance(ad.status(), dict) and ad.tick()["ok"] and "LEBROKEN.txt" in ad.unparsed)
        check("files: every OIF written matched the documented grammar, no byte-order mark, all named oif*.txt",
              not fake.errors and all(n.startswith("oif_le_") and n.endswith(".txt") for n, _ in fake.files), str(fake.errors[:3]))
        rows = [ln.rstrip("\n").split("  ") for ln in open(os.path.join(tmp, "oif.log"), encoding="utf-8")]
        audit = [r_[-1] for r_ in rows]
        processed = [ln for _, ls in fake.files for ln in ls]
        written, seen = {r_[2] for r_ in rows}, {n for n, _ in fake.files}
        check("audit: every OIF line written is in logs/ninjatrader_oif.log; files never processed were all withdrawn",
              seen <= written and all(ln in audit for ln in processed) and len(written - seen) >= 3
              and not [n for n in os.listdir(fake.inc) if n.startswith("oif")], f"{len(written)} written, {len(seen)} processed")

        # ---- 13. bar feed
        feed_dir = os.path.join(folder, FEED_DIR)
        os.makedirs(feed_dir, exist_ok=True)
        fnow = int(dt.datetime(2026, 10, 21, 10, 7, 30, tzinfo=ET).timestamp())
        last = fnow - fnow % 300 - 300                   # 10:00 bar = the last closed one at 10:07:30
        rows = [(t, 25000 + i * 0.25, 25001 + i * 0.25, 24999 + i * 0.25, 25000.5 + i * 0.25, 100 + i)
                for i, t in enumerate(range(last - 600 * 300, last + 1, 300))]
        rows = [r_ for r_ in rows if market_open_local(r_[0])]
        body = "time,open,high,low,close,volume\n" + "".join(f"{a},{b},{c},{d},{e},{f}\n" for a, b, c, d, e, f in rows) + f"{last + 300},250"
        with open(os.path.join(feed_dir, "MNQ_5m.csv"), "w") as fh:
            fh.write(body)
        feed = NinjaTraderBars(folder)
        df, why, full = feed.recent_bars("NQ", "5m", "2d", now=fnow)
        check("feed: MNQ_5m.csv -> the Yahoo frame layout (time int64 = bar open, float OHLCV), half-written last line dropped",
              df is not None and list(df.columns) == ["time", "open", "high", "low", "close", "volume"] and str(df["time"].dtype) == "int64"
              and int(df["time"].iloc[-1]) == last and full, why)
        h1, why1, _ = feed.recent_bars("NQ", "1h", "1d", now=fnow)
        sub = df[(df["time"] >= last - 3600) & (df["time"] < last - 3600 + 3600)]
        hrow = h1[h1["time"] == last - 3600] if h1 is not None else None
        check("feed: 1h bars are built from the 5m file (open first, high max, low min, close last, volume sum)",
              hrow is not None and len(hrow) == 1 and float(hrow["open"].iloc[0]) == float(sub["open"].iloc[0])
              and float(hrow["high"].iloc[0]) == float(sub["high"].max()) and float(hrow["close"].iloc[0]) == float(sub["close"].iloc[-1])
              and float(hrow["volume"].iloc[0]) == float(sub["volume"].sum()), why1)
        st_df, st_why, _ = feed.recent_bars("NQ", "5m", "2d", now=fnow + 1800)
        check("feed: stale during market hours -> None with the reason (the bot blocks new entries; no Yahoo)", st_df is None and "stale" in st_why, st_why)
        es_df, es_why, _ = feed.recent_bars("ES", "5m", "2d", now=fnow)
        check("feed: no file for a symbol -> None with the file name to create", es_df is None and "MES_5m.csv" in es_why, es_why)
        shifted = "time,open,high,low,close,volume\n" + "".join(f"{a + 3600},{b},{c},{d},{e},{f}\n" for a, b, c, d, e, f in rows)
        with open(os.path.join(feed_dir, "MNQ_1m.csv"), "w") as fh:
            fh.write(shifted)
        sh_df, sh_why, _ = NinjaTraderBars(folder, roots={"NQ": ["MNQ"]}).recent_bars("NQ", "1m", "2d", now=fnow + 3600)
        check("feed: bar times shifted by an hour (bars at 17:xx ET) are detected and refused", sh_df is None and "shifted" in sh_why, sh_why)

        # ---- 13b. no-chart mode: the LE_Feed add-on's instrument list and status file (ninjatrader/LE_Feed.cs)
        d_oct, d_roll = dt.date(2026, 11, 2), dt.date(2026, 12, 10)
        check("LE_Feed: feed_instruments = the MNQ contract the bot orders (follows the 8-day roll), + NQ with signal_root NQ, "
              "a pinned nt_instrument wins",
              feed_instruments({"signal_root": "MNQ"}, d_oct) == ["MNQ 12-26"]
              and feed_instruments({"signal_root": "MNQ"}, d_roll) == ["MNQ 03-27"]
              and feed_instruments({"signal_root": "NQ"}, d_oct) == ["MNQ 12-26", "NQ 12-26"]
              and feed_instruments({"signal_root": "MNQ", "nt_instrument": "MNQ 03-27"}, d_oct) == ["MNQ 03-27"],
              str([feed_instruments({"signal_root": "MNQ"}, d_oct), feed_instruments({"signal_root": "NQ"}, d_oct)]))
        afold = os.path.join(tmp, "NT addon")
        os.makedirs(afold)
        ip = os.path.join(afold, FEED_DIR, FEED_INSTRUMENTS)
        w1 = sync_feed_instruments(afold, {"signal_root": "MNQ"}, d_oct)
        w2 = sync_feed_instruments(afold, {"signal_root": "MNQ"}, d_oct)
        txt1 = _read_text(ip)
        w3 = sync_feed_instruments(afold, {"signal_root": "MNQ"}, d_roll)
        txt3 = _read_text(ip)
        nofold = os.path.join(tmp, "no NinjaTrader here")
        w4 = sync_feed_instruments(nofold, {"signal_root": "MNQ"}, d_oct)
        check("LE_Feed: feed_instruments.txt is written once, rewritten only when the contract changes (the roll), never "
              "into a folder without NinjaTrader",
              w1 and not w2 and txt1 == "MNQ 12-26\n" and w3 and txt3 == "MNQ 03-27\n" and not w4 and not os.path.exists(nofold),
              str([w1, w2, txt1, w3, txt3, w4]))
        ok_line = "1793458800,source=addon,instruments=MNQ 12-26;NQ 12-26,last_1m=1793458680,resubs=3,connected=1"
        pst = parse_feed_status(ok_line)
        check("LE_Feed: a status line parses (time, source, instruments, last 1m bar, re-subscribes, connected); junk -> None",
              pst == {"time": 1793458800, "source": "addon", "instruments": ["MNQ 12-26", "NQ 12-26"], "last_1m": 1793458680,
                      "resubs": 3, "connected": True}
              and parse_feed_status("") is None and parse_feed_status("hello,world") is None
              and parse_feed_status("1793458800,instruments=x") is None
              and parse_feed_status("1793458800,source=addon,last_1m=,resubs=")["last_1m"] is None, str(pst))
        no_st = read_feed_status(afold, now=1793458800)
        with open(os.path.join(afold, FEED_DIR, FEED_STATUS), "w", encoding="utf-8", newline="\r\n") as fh:
            fh.write(ok_line + "\n")
        fresh = read_feed_status(afold, now=1793458800 + 70)
        old = read_feed_status(afold, now=1793458800 + 1800)
        t_fresh, t_old = feed_status_text(fresh), feed_status_text(old)
        check("LE_Feed: status file -> 'bars from LE_Feed (no chart), 3 re-subscribes'; 30 min old -> 'NinjaTrader closed?'; "
              "no file -> None (chart mode)",
              no_st is None and feed_status_text(None) is None and fresh and fresh["fresh"] and fresh["age_s"] == 70
              and t_fresh.startswith("bars from LE_Feed (no chart), 3 re-subscribes") and "old" not in t_fresh
              and old and not old["fresh"] and "30 min old (NinjaTrader closed?)" in t_old
              and feed_status_text({"resubs": 1, "fresh": True}) == "bars from LE_Feed (no chart), 1 re-subscribe",
              str([t_fresh, t_old]))

        # ---- 14. LiveBot wiring (no Engine run: routing is driven with a hand-made model state)
        from . import live
        bot = live.LiveBot()
        bot.clock = lambda: now[0]
        bot.state_path = os.path.join(tmp, "live_state.json")
        bot._remember = lambda *a, **kw: None           # never touch data/memory.db from a test
        r0 = bot.start({"sym": "NQ", "tf": "5m", "adapter": "ninjatrader", "nt_folder": folder}, spawn=False)
        check("LiveBot: adapter ninjatrader refused unless armed", not r0["ok"] and "armed" in r0["error"])
        now[0] = dt.datetime(2026, 10, 22, 10, 5, 3, tzinfo=ET).timestamp()
        # this self-test checks the adapter's own refusals: engine/guards.py would refuse its synthetic entries first (a 2nd
        # entry the same day, a 1.35R target), so those two guards are off here (tests/test_guards.py covers them)
        st_guards = {"dup_entry": False, "order_sanity": False}
        r1 = bot.start({"sym": "NQ", "tf": "5m", "adapter": "ninjatrader", "armed": True, "data": "ninjatrader", "nt_folder": folder,
                        "nt_state_path": os.path.join(tmp, "nt_state2.json"), "nt_audit_log": os.path.join(tmp, "oif.log"),
                        "guards": st_guards}, spawn=False)
        bad = bot.adapter
        check("LiveBot: ADAPTERS['ninjatrader'] selected, 'data' alias -> data_source ninjatrader",
              r1["ok"] and type(bad).__name__ == "NinjaTraderAdapter" and bot.cfg["data_source"] == "ninjatrader",
              f"{r1} {type(bad).__name__} {bot.cfg.get('data_source')}")
        bad.clock = lambda: now[0]
        bad._sleep = lambda s: (fake.process(), now.__setitem__(0, now[0] + s))
        bad._alert_fn = alerts.append
        t_in = int(dt.datetime(2026, 10, 22, 10, 0, tzinfo=ET).timestamp())
        pos = {"entry_t": t_in, "dir": 1, "qty": 2, "entry": 25020.0, "stop": 24990.0, "target": 25080.0}
        bot.state = {"position": dict(pos)}
        res = {"trades": [], "events": []}
        bot.started_at = t_in - 3600
        k = len(fake.files)
        bot._route_signals(res, "NQ", int(now[0]), 300)
        entry_ok = any(x["side"] == "buy" and x["result"]["ok"] for x in bot.ledger) and len(bad.legs) == 1
        bot._route_signals(res, "NQ", int(now[0]), 300)             # same stop: nothing new
        n_after_entry = len(fake.files)
        bot.state = {"position": {**pos, "stop": 25020.25, "managed": True}}
        bot._route_signals(res, "NQ", int(now[0]), 300)
        mod_rows = [x for x in bot.ledger if x["side"] == "modify"]
        bot._route_signals(res, "NQ", int(now[0]), 300)             # already moved: not sent again
        check("LiveBot: entry routed as a bracket; the model's breakeven becomes ONE modify -> CHANGE of the stop",
              entry_ok and n_after_entry == k + 2 and len(mod_rows) == 1 and mod_rows[0]["result"]["ok"]
              and len([x for x in bot.ledger if x["side"] == "modify"]) == 1
              and fake.files[-1][1] == [f"CHANGE;;;;0;;0;25020.25;;;{bad.legs[0]['stop_id']};;"], json.dumps([x["side"] for x in bot.ledger]))
        k = len(fake.files)
        bot.state = {"position": None}
        trade = {"entry_t": t_in, "exit_t": t_in + 1800, "exit_reason": "TIME STOP", "qty": 2, "pnl": -12.0, "pnl_r": -0.1, "dir": 1}
        bot._route_signals({"trades": [trade], "events": []}, "NQ", int(now[0]), 300)
        check("LiveBot: a TIME STOP exit (not only TIME) is routed to NinjaTrader as CLOSEPOSITION",
              [x["side"] for x in bot.ledger][-1] == "exit" and lines_since(k)[:1] == ["CLOSEPOSITION;Sim101;MNQ 12-26;;;;;;;;;;"]
              and not bad.legs, json.dumps(lines_since(k)))
        t2 = t_in + 3600                    # an entry the adapter refuses (a hand-opened position is open): no stop moves follow
        now[0] = t2 + 303
        fake._do("PLACE;Sim101;MNQ 12-26;BUY;1;MARKET;0;0;DAY;;BYHAND1;;")
        pos2 = {"entry_t": t2, "dir": -1, "qty": 2, "entry": 25020.0, "stop": 25050.0, "target": 24960.0}
        bot.state = {"position": dict(pos2)}
        k = len(fake.files)
        bot._route_signals({"trades": [], "events": []}, "NQ", int(now[0]), 300)
        refused = [x for x in bot.ledger if x.get("entry_t") == t2 and x["side"] == "sell"]
        for _ in range(4):
            bot.state = {"position": {**pos2, "stop": 25019.75, "managed": True}}
            bot._route_signals({"trades": [], "events": []}, "NQ", int(now[0]), 300)
        check("LiveBot: when the adapter refuses an entry, the model's breakeven is not sent (no bracket to move)",
              refused and not refused[0]["result"]["ok"] and not [x for x in bot.ledger if x.get("entry_t") == t2 and x["side"] == "modify"]
              and len(fake.files) == k and "not adding" in refused[0]["result"].get("error", ""),
              json.dumps([[x["side"], x["result"].get("error")] for x in bot.ledger if x.get("entry_t") == t2]))
        bot._open_routed = None
        fake._do(close_line("Sim101", "MNQ 12-26"))
        orig_y = live._yahoo_recent
        calls = []
        live._yahoo_recent = lambda sym, interval="5m", period="5d": calls.append((sym, interval)) or pd.DataFrame(
            [{"time": 1, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 0.0}])
        noy0 = bot.no_yahoo
        try:
            now[0] = fnow
            bot.no_yahoo = True
            got = bot._fetch_recent("NQ", "5m", "2d")
            fresh_ok = len(got) == len(df) and not calls and not bot.health.get("fallback")
            now[0] = fnow + 1800
            bot.health.update(fallback=False, nt_down=None)
            got_ny = bot._fetch_recent("NQ", "5m", "2d")
            ny_ok = got_ny is None and not calls and "stale" in str(bot.health.get("nt_down")) and not bot.health["fallback"] \
                and any("FEED STALE" in x["text"] and "no Yahoo" in x["text"] for x in bot.log)
            bot.no_yahoo = False                      # "no_yahoo": false (the old behaviour): Yahoo is the fallback
            got2 = bot._fetch_recent("NQ", "5m", "2d")
            check("LiveBot: data_source ninjatrader serves the feed (no Yahoo call); stale -> no_yahoo: None + FEED STALE, "
                  "no Yahoo call; no_yahoo off: Yahoo fallback + warning + flag",
                  fresh_ok and ny_ok and calls == [("NQ", "5m")] and len(got2) == 1 and bot.health["fallback"]
                  and any("falling back to Yahoo" in x["text"] for x in bot.log), f"calls={calls} ny={ny_ok}")
        finally:
            live._yahoo_recent = orig_y
            bot.no_yahoo = noy0
        now[0] = dt.datetime(2026, 10, 22, 11, 0, tzinfo=ET).timestamp()
        k = len(fake.files)
        bot.state = {"position": None}
        bot.kill_switch()
        check("LiveBot: kill switch with no model position still reaches NinjaTrader (FLATTENEVERYTHING) and stops the bot",
              lines_since(k) == ["FLATTENEVERYTHING;;;;;;;;;;;;"] and bot.kill and not bot.running, json.dumps(lines_since(k)))
        from .watchdog import mode_of
        check("autostart: ninjatrader on Sim101 counts as demo (may resume), any other account as live (never resumes)",
              mode_of({"adapter": "ninjatrader"}) == "demo" and mode_of({"adapter": "ninjatrader", "nt_account": "Sim101"}) == "demo"
              and mode_of({"adapter": "ninjatrader", "nt_account": "MFFUEV12345"}) == "live")
        # ---- 15. LIT on NinjaTrader: London entry (02:00+), VIX-band target on the tick grid, BE at 1R, 15:55 flatten, 1m feed
        check("LIT: the adapter's session starts at the LIT window (02:00 ET) for model lit, 08:00 for the engine",
              _session_from({"model": "lit", "model_params": {"window": [[120, 930]]}}) == 120 and _session_from({"model": "engine"}) == 480
              and _session_from({"nt_session_from": 300}) == 300)
        # LIT all_hours (the Asia slot, research/writeups/lit-more-entries.md; off by default): CME trading day 18:00 -> 17:00
        ah_p = {"window": [[1080, 1440], [0, 930]], "all_hours": True}
        keep_now = now[0]

        def gate_at(ad_, *ymdhm):
            now[0] = dt.datetime(*ymdhm, tzinfo=ET).timestamp()
            return ad_._gate("entry")
        aad = make({"model": "lit", "model_params": ah_p, "nt_state_path": os.path.join(tmp, "nt_state_ah.json")})
        oad = make({"model": "lit", "model_params": {"window": [[120, 930]]}, "nt_state_path": os.path.join(tmp, "nt_state_off.json")})
        check("LIT all_hours: the adapter's session starts 18:00 ET (trading-day order); off: 02:00 and the clock-day gate",
              aad.all_hours and aad.session_from == 1080 and not oad.all_hours and oad.session_from == 120
              and _session_from({"model": "lit", "model_params": ah_p}) == 1080)
        check("LIT all_hours: entries allowed Tue 20:41, Tue 23:28, Wed 00:37, Wed 10:00 and Sun 18:30 ET (Monday's session)",
              all(gate_at(aad, *x) is None for x in ((2026, 9, 1, 20, 41), (2026, 9, 1, 23, 28), (2026, 9, 2, 0, 37),
                                                     (2026, 9, 2, 10, 0), (2026, 10, 25, 18, 30))))
        check("LIT all_hours: refused 15:55 / 16:30 / 17:30 ET, Fri 20:00, Sat, Sun 17:30; today's adapter still refuses 20:41",
              all(gate_at(aad, *x) for x in ((2026, 9, 1, 15, 55), (2026, 9, 1, 16, 30), (2026, 9, 1, 17, 30), (2026, 10, 23, 20, 0),
                                             (2026, 10, 24, 10, 0), (2026, 10, 25, 17, 30)))
              and gate_at(oad, 2026, 9, 1, 20, 41) and gate_at(oad, 2026, 9, 2, 10, 0) is None)
        closed_ = []
        aad._close = lambda legs, why="": closed_.append(why)
        aad.legs = [{"status": "protected", "instrument": "MNQ 12-26", "entry_id": "x"}]
        aad._our_instruments = lambda: []
        for x in ((2026, 9, 1, 20, 45), (2026, 9, 2, 1, 0), (2026, 9, 2, 10, 0)):
            aad._tick_flat_time(dt.datetime(*x, tzinfo=ET).timestamp())
        quiet = not closed_
        aad._tick_flat_time(dt.datetime(2026, 9, 2, 15, 55, tzinfo=ET).timestamp())
        check("LIT all_hours: the flat-time watch leaves a 20:45 / 01:00 / 10:00 ET Asia trade open and flattens it at 15:55",
              quiet and closed_ == ["flat time"], closed_)
        aad.legs = []
        now[0] = keep_now
        fake.move(25020.0)
        now[0] = dt.datetime(2026, 10, 22, 2, 35, 3, tzinfo=ET).timestamp()        # Thursday 02:35 ET (London)
        lbot = live.LiveBot()
        lbot.clock = lambda: now[0]
        lbot.state_path = os.path.join(tmp, "live_state_lit.json")
        lbot._remember = lambda *a, **kw: None
        r2 = lbot.start({"sym": "NQ", "tf": "5m", "adapter": "ninjatrader", "armed": True, "data": "ninjatrader", "nt_folder": folder,
                         "model": "lit", "model_params": {"window": [[120, 930]]}, "guards": st_guards,
                         "nt_state_path": os.path.join(tmp, "nt_state3.json"), "nt_audit_log": os.path.join(tmp, "oif.log")}, spawn=False)
        lad = lbot.adapter
        lad.clock = lambda: now[0]
        lad._sleep = lambda s_: (fake.process(), now.__setitem__(0, now[0] + s_))
        lad._alert_fn = alerts.append
        t_l = int(dt.datetime(2026, 10, 22, 2, 35, tzinfo=ET).timestamp())
        lpos = {"entry_t": t_l, "dir": 1, "qty": 3, "entry": 25020.0, "stop": 24970.25, "stop0": 24970.25, "target": 25087.37,
                "risk_pts": 49.75, "setup": "LIT"}
        lbot.state = {"model": "lit", "position": dict(lpos)}
        lbot.started_at = t_l - 3600
        k = len(fake.files)
        lbot._route_signals({"trades": [], "events": []}, "NQ", int(now[0]), 300)
        lg = lad.legs[0] if lad.legs else {}
        got = [ls for _, ls in fake.files[k:]]
        check("LIT: a 02:35 ET entry is routed (not refused as outside the session); the VIX-band target 25087.37 goes in as "
              "LIMIT 25087.25 (tick, toward the entry), the stop as STOPMARKET 24970.25",
              r2["ok"] and lad.session_from == 120 and len(got) == 2 and got[0][0].split(";")[3:6] == ["BUY", "3", "MARKET"]
              and got[1] == [f"PLACE;Sim101;MNQ 12-26;SELL;3;STOPMARKET;0;24970.25;DAY;{lg.get('oco')};{lg.get('stop_id')};;",
                             f"PLACE;Sim101;MNQ 12-26;SELL;3;LIMIT;25087.25;0;DAY;{lg.get('oco')};{lg.get('target_id')};;"],
              json.dumps(got))
        from .live import tick_px
        check("LIT: tick rounding: stops to the nearest tick, targets toward the entry (long down, short up)",
              tick_px(25087.37, 1, True) == 25087.25 and tick_px(24912.63, -1, True) == 24912.75 and tick_px(25000.0, 1, True) == 25000.0
              and tick_px(24970.13, 1) == 24970.25 and tick_px(24970.12, -1) == 24970.0)
        now[0] += 60
        lad.tick()
        check("LIT: the adapter's flat-time watch leaves a 02:36 ET London trade alone (no CLOSEPOSITION before 08:00)",
              lad.legs and lad.legs[0]["status"] == "protected" and not any(ln.startswith("CLOSEPOSITION") for ln in lines_since(k)))
        lbot.state = {"model": "lit", "position": {**lpos, "stop": 25020.0, "be": True}}
        k = len(fake.files)
        lbot._route_signals({"trades": [], "events": []}, "NQ", int(now[0]), 300)
        check("LIT: breakeven at 1R (model stop = the fill) -> one CHANGE of the stop to 25020.00",
              lines_since(k) == [f"CHANGE;;;;0;;0;25020.00;;;{lg.get('stop_id')};;"], json.dumps(lines_since(k)))
        now[0] = dt.datetime(2026, 10, 22, 15, 55, 4, tzinfo=ET).timestamp()
        lbot.state = {"model": "lit", "position": None}
        k = len(fake.files)
        ltr = {"entry_t": t_l, "exit_t": int(now[0]) - 4, "exit_reason": "TIME", "qty": 3, "pnl": 120.0, "pnl_r": 0.4, "dir": 1}
        lbot._route_signals({"trades": [ltr], "events": []}, "NQ", int(now[0]), 300)
        check("LIT: the 15:55 flat (model exit EOD -> TIME) is routed as CLOSEPOSITION and the bracket is retired",
              lines_since(k)[:1] == ["CLOSEPOSITION;Sim101;MNQ 12-26;;;;;;;;;;"] and not lad.legs, json.dumps(lines_since(k)))
        # 1m bars for LIT's entry come from LE_BarFeed's MNQ_1m.csv (data_source ninjatrader); stale -> no Yahoo (no_yahoo)
        f1now = int(dt.datetime(2026, 10, 22, 3, 7, 30, tzinfo=ET).timestamp())
        last1 = f1now - f1now % 60 - 60
        rows1 = [(t, 25000 + i * 0.25, 25000.5 + i * 0.25, 24999.75 + i * 0.25, 25000.25 + i * 0.25, 10 + i)
                 for i, t in enumerate(range(last1 - 8 * 1440 * 60, last1 + 1, 60)) if market_open_local(t)]
        with open(os.path.join(feed_dir, "MNQ_1m.csv"), "w") as fh:
            fh.write("time,open,high,low,close,volume\n" + "".join(f"{a},{b},{c},{d},{e},{f}\n" for a, b, c, d, e, f in rows1))
        lbot.cfg["data_source"] = "ninjatrader"
        lbot._nt_feed = None
        lbot.read_hist = lambda sym, tf: pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
        calls = []
        live._yahoo_recent = lambda sym, interval="5m", period="5d": calls.append((sym, interval)) or pd.DataFrame(
            [{"time": 60, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 0.0}])
        try:
            now[0] = f1now
            with open(os.path.join(feed_dir, "MNQ_1m_open.csv"), "w") as fh:
                fh.write(f"{last1 + 60},25123.5\n")             # LE_BarFeed: the forming minute's first trade
            got1 = lbot._lit_1m("NQ", f1now, f1now - 5 * 86400)
            ok1 = got1 is not None and int(got1["time"].iloc[-1]) == last1 and not calls and len(got1) == len([r_ for r_ in rows1 if r_[0] >= f1now - 5 * 86400])
            fo1 = lbot._forming.get(("NQ", 60))
            now[0] = f1now + 1800
            lbot.no_yahoo = True
            lbot.health["nt_down_1m"] = None
            got2 = lbot._lit_1m("NQ", f1now + 1800, f1now - 5 * 86400)
            check("LIT: 1m bars from NinjaTrader's MNQ_1m.csv (no Yahoo call); a stale 1m file -> no Yahoo call, the bars "
                  "already seen are kept, nt_down_1m flagged (entries blocked), fallback flag untouched",
                  ok1 and not calls and got2 is not None and len(got2) == len(got1) and "stale" in str(lbot.health.get("nt_down_1m"))
                  and not lbot.health.get("fallback"), f"calls={calls}")
            check("LIT: the forming minute's open from MNQ_1m_open.csv (sizes an entry decided on the 1m CISD close); an old "
                  "minute in it is ignored", fo1 == (last1 + 60, 25123.5) and lbot._forming.get(("NQ", 60)) is None
                  and NinjaTraderBars(folder=folder).forming_open("NQ", now=f1now + 1800) is None, f"{fo1}")
        finally:
            live._yahoo_recent = orig_y
        # ---- 16. LIT adopt-candidates on the route: breakeven at entry + 1.25 (be_off), scale-in add, 15-minute cut
        now[0] = dt.datetime(2026, 10, 22, 3, 0, 3, tzinfo=ET).timestamp()
        fake.move(25020.0)
        sad = make({"model": "lit", "model_params": {"window": [[120, 930]]}, "nt_state_path": os.path.join(tmp, "nt_state_si.json")})
        t_s = int(dt.datetime(2026, 10, 22, 3, 0, tzinfo=ET).timestamp())
        r = sad.send({"sym": "NQ", "side": "buy", "qty": 2, "stop": 24990.0, "target": 25100.0, "entry": 25020.0, "entry_t": t_s})
        sl = sad.legs[0] if sad.legs else {}
        S_, T_ = sl.get("stop_id"), sl.get("target_id")
        k = len(fake.files)
        r_be = sad.send({"side": "modify", "stop": 25021.25, "entry_t": t_s})
        check("be_off: breakeven at entry + 1.25 pts -> one CHANGE of the stop to 25021.25 (5 ticks above the 25020 entry)",
              r["ok"] and r_be["ok"] and lines_since(k) == [f"CHANGE;;;;0;;0;25021.25;;;{S_};;"] and fake.orders[S_]["stop"] == 25021.25,
              json.dumps(lines_since(k)))
        fake.move(25040.0)
        k = len(fake.files)
        r_add = sad.send({"sym": "NQ", "side": "add", "qty": 3, "dir": 1, "entry_t": t_s, "n": 1, "stop": 25021.25, "target": 25100.0})
        aid = f"{sl.get('entry_id', 'X')[:-1]}A1"
        check("scale-in: MARKET add of 3 (same side, own order id), then the ONE OCO pair resized to the whole position: "
              "CHANGE qty 5 on the stop and the target (no second bracket)",
              r_add["ok"] and lines_since(k) == [f"PLACE;Sim101;MNQ 12-26;BUY;3;MARKET;0;0;DAY;;{aid};;",
                                                 f"CHANGE;;;;5;;0;0;;;{S_};;", f"CHANGE;;;;5;;0;0;;;{T_};;"]
              and fake.pos.get(("Sim101", "MNQ 12-26"), [0])[0] == 5 and fake.orders[S_]["qty"] == 5 and fake.orders[T_]["qty"] == 5
              and sl.get("bracket_qty") == 5 and r_add.get("fill_px") == 25040.0, json.dumps([lines_since(k), r_add]))
        k = len(fake.files)
        r_big = sad.send({"side": "add", "qty": 36, "dir": 1, "entry_t": t_s, "stop": 25021.25})
        r_side = sad.send({"side": "add", "qty": 1, "dir": -1, "entry_t": t_s, "stop": 25021.25})
        fake._do("PLACE;Sim101;MNQ 12-26;BUY;1;MARKET;0;0;DAY;;BYHAND2;;")      # a hand-placed micro: position 6, bracket 5
        r_desync = sad.send({"side": "add", "qty": 1, "dir": 1, "entry_t": t_s, "stop": 25021.25})
        fake._do("PLACE;Sim101;MNQ 12-26;SELL;1;MARKET;0;0;DAY;;BYHAND3;;")
        now_save = now[0]
        now[0] = dt.datetime(2026, 10, 22, 15, 56, 3, tzinfo=ET).timestamp()
        r_late = sad.send({"side": "add", "qty": 1, "dir": 1, "entry_t": t_s, "stop": 25021.25})
        now[0] = now_save
        check("scale-in: refused (no order file) above max_micros (5 + 36 > 40), on the other side, when NinjaTrader's position "
              "disagrees with the bracket, and after the entry cutoff",
              not r_big["ok"] and "max_micros" in r_big["error"] and not r_side["ok"] and "side" in r_side["error"]
              and not r_desync["ok"] and "not adding" in r_desync["error"] and not r_late["ok"] and "outside the session" in r_late["error"]
              and not any(ln.startswith("PLACE") and ";MARKET;" in ln and "BYHAND" not in ln for ln in lines_since(k)),
              json.dumps([r_big, r_side, r_desync, r_late]))
        fake.move(25021.0)                       # the breakeven stop (entry + 1.25) is hit: it sells all 5
        sad.tick()
        check("scale-in: the resized stop closes the whole position (5) -> flat, bracket retired",
              fake.pos.get(("Sim101", "MNQ 12-26"), [0])[0] == 0 and not sad.legs and fake.orders[S_]["filled"] == 5)
        r_none = sad.send({"side": "add", "qty": 1, "dir": 1, "entry_t": t_s, "stop": 25021.25})
        check("scale-in: no protected bracket -> refused", not r_none["ok"] and "no protected bracket" in r_none["error"])
        # an add whose fill NinjaTrader reports late: pending, then tick() grows the bracket
        t_s2 = t_s + 1800
        now[0] = t_s2 + 3
        fake.move(25000.0)
        sad.send({"sym": "NQ", "side": "sell", "qty": 2, "stop": 25030.0, "target": 24900.0, "entry": 25000.0, "entry_t": t_s2})
        sl2 = sad.legs[0] if sad.legs else {}
        fake.move(24985.0)
        r_nobe = sad.send({"side": "add", "qty": 2, "dir": -1, "entry_t": t_s2, "n": 1, "stop": 24998.75})
        sad.send({"side": "modify", "stop": 24998.75, "entry_t": t_s2})          # breakeven (entry - 1.25) for the short
        check("scale-in: an add sized at breakeven is refused while the broker stop is still the first stop (25030)",
              not r_nobe["ok"] and "not adding while the stop" in r_nobe["error"] and not sl2.get("adds"), json.dumps(r_nobe))
        fake.hold_market = True
        r_p = sad.send({"side": "add", "qty": 2, "dir": -1, "entry_t": t_s2, "n": 1, "stop": 24998.75})
        fake.hold_market = False
        aid2 = f"{sl2.get('entry_id', 'X')[:-1]}A1"
        k = len(fake.files)
        fake._fill(aid2, 2, 24990.0)
        sad.tick()
        check("scale-in: an add filled after the call returned (pending) -> the next tick() resizes the stop and target to 4",
              not r_p["ok"] and r_p.get("pending") and lines_since(k) == [f"CHANGE;;;;4;;0;0;;;{sl2.get('stop_id')};;",
                                                                         f"CHANGE;;;;4;;0;0;;;{sl2.get('target_id')};;"]
              and sl2.get("bracket_qty") == 4, json.dumps([r_p, lines_since(k)]))
        # LiveBot: the model's add_now -> ONE add route; the exit flattens the whole position with the adds' P&L
        sbot = live.LiveBot()
        sbot.clock = lambda: now[0]
        sbot.state_path = os.path.join(tmp, "live_state_si.json")
        sbot._remember = lambda *a, **kw: None
        sbot.start({"sym": "NQ", "tf": "5m", "adapter": "ninjatrader", "armed": True, "data": "ninjatrader", "nt_folder": folder,
                    "model": "lit", "model_params": {"window": [[120, 930]]}, "nt_state_path": os.path.join(tmp, "nt_state_si2.json"),
                    "nt_audit_log": os.path.join(tmp, "oif.log")}, spawn=False)
        bad2 = sbot.adapter
        bad2.clock = lambda: now[0]
        bad2._sleep = lambda s_: (fake.process(), now.__setitem__(0, now[0] + s_))
        bad2._alert_fn = alerts.append
        fake._do(close_line("Sim101", "MNQ 12-26"))
        sad.legs = []
        t_b = t_s2 + 1800
        now[0] = t_b + 2
        fake.move(25020.0)
        bpos = {"entry_t": t_b, "dir": 1, "qty": 4, "entry": 25020.0, "stop": 24990.0, "stop0": 24990.0, "target": 25110.0,
                "risk_pts": 30.0, "setup": "LIT"}
        sbot.state = {"model": "lit", "position": dict(bpos), "strategy": {"params": {"scale_in": {"f": 1.0}}}}
        sbot.started_at = t_b - 3600
        sbot._route_signals({"trades": [], "events": []}, "NQ", int(now[0]), 300)
        now[0] = t_b + 9 * 60 + 2
        fake.move(25045.0)
        an = {"n": 1, "t": t_b + 9 * 60, "cisd_t": t_b + 8 * 60, "px": 25045.25, "est": False, "rk": 25.0, "prev_rk": [], "dist": 25.0,
              "qty": 4, "f": 1.0}
        sbot.state = {"model": "lit", "position": {**bpos, "stop": 25021.25, "be": True, "add_now": an},
                      "strategy": {"params": {"scale_in": {"f": 1.0}}}}
        # eval sizing of the add (two_week): budget min(4 x 30 x $2 = $240, 60% of a $300 room = $180, $1,000 - $900 lost
        # today = $100) / ((25 + 0.25) x $2 + $1.90 = $52.40) -> 3 with the room, 1 with the soft daily loss
        sbot._lit_sizing = {"mode": "two_week"}
        sbot.eval_room, sbot.eval_state = (lambda: 300.0), (lambda: {"cum": 0.0})
        q_room = sbot._add_qty(sbot.state["position"], an)
        sbot.eval_room, sbot.eval_state = (lambda: 2000.0), (lambda: {"cum": -900.0})
        q_dll = sbot._add_qty(sbot.state["position"], an)
        sbot.eval_room = lambda: (_ for _ in ()).throw(RuntimeError("injected"))
        q_fail = sbot._add_qty(sbot.state["position"], an)
        del sbot.eval_room, sbot.eval_state
        sbot._lit_sizing = None
        check("LiveBot: scale-in add sizing in an eval mode = engine/sizing.scale_in_qty at the routed size (60% room -> 3, "
              "soft daily loss left -> 1, sizing error -> 0 = no add); normal mode = the model's add (4)",
              q_room == 3 and q_dll == 1 and q_fail == 0 and sbot._add_qty(sbot.state["position"], an) == 4, f"{q_room} {q_dll} {q_fail}")
        k = len(fake.files)
        sbot._route_signals({"trades": [], "events": []}, "NQ", int(now[0]), 300)
        sbot._route_signals({"trades": [], "events": []}, "NQ", int(now[0]), 300)      # same decision: not sent twice
        adds_r = [x for x in sbot.ledger if x["side"] == "add"]
        check("LiveBot: the model's add_now becomes ONE add route (the model's add at the routed size) after the breakeven "
              "CHANGE to entry + 1.25",
              len(adds_r) == 1 and adds_r[0]["qty"] == 4 and adds_r[0]["result"]["ok"] and sbot._adds_qty(t_b) == 4
              and [ln.split(";")[0] for ln in lines_since(k)] == ["CHANGE", "PLACE", "CHANGE", "CHANGE"]
              and lines_since(k)[0].split(";")[7] == "25021.25", json.dumps([lines_since(k), [x["side"] for x in sbot.ledger]]))
        now[0] = t_b + 40 * 60
        btr = {"entry_t": t_b, "exit_t": int(now[0]) - 2, "exit_reason": "CUT_T15", "qty": 4, "pnl": 0.0, "pnl_r": 0.0, "dir": 1,
               "entry": 25020.0, "exit_price": 25060.0, "pts": 40.0, "adds": [{"px": 25045.25, "qty": 4, "pts": 14.75}]}
        sbot.state = {"model": "lit", "position": None}
        k = len(fake.files)
        sbot._route_signals({"trades": [btr], "events": []}, "NQ", int(now[0]), 300)
        xr = [x for x in sbot.ledger if x["side"] == "exit"][-1]
        from . import lit as _lit
        from .sizing import LIVE_COMM                    # routed P&L is booked at the live $1.90 commission
        want_pnl = round(4 * (40.0 * _lit.PV - LIVE_COMM) + 4 * ((25060.0 - 25045.0) * _lit.PV - LIVE_COMM), 2)
        check("LiveBot: a model exit (CUT_T15) after an add is routed as CLOSEPOSITION for the whole position (qty 8) with the "
              "add's P&L at its REAL fill (25045.00, the model priced 25045.25) in the ledger",
              lines_since(k)[:1] == ["CLOSEPOSITION;Sim101;MNQ 12-26;;;;;;;;;;"] and xr["qty"] == 8
              and abs(xr["pnl"] - want_pnl) < 0.01 and not bad2.legs, json.dumps([xr, want_pnl, lines_since(k)]))
        blob = open(os.path.join(tmp, "oif.log"), encoding="utf-8").read() + json.dumps(list(ad.trace))
        check("secrets: no confirm phrase or credential in the OIF audit log / trace", LIVE_PHRASE not in blob)
    finally:
        for k_, v in saved_env.items():
            if v is None:
                os.environ.pop(k_, None)
            else:
                os.environ[k_] = v
        shutil.rmtree(tmp, ignore_errors=True)
    npass = sum(1 for _, ok, _ in checks if ok)
    if verbose:
        print(f"\nNinjaTrader offline self-test: {'PASS' if npass == len(checks) else 'FAIL'} ({npass}/{len(checks)})")
        if npass == len(checks):
            print("Exact OIF lines (long 2 MNQ on Sim101, stop 24990.13 -> 24990.25 tick-rounded, target 25080):")
            print("  entry    PLACE;Sim101;MNQ 12-26;BUY;2;MARKET;0;0;DAY;;<id>E;;")
            print("  bracket  PLACE;Sim101;MNQ 12-26;SELL;2;STOPMARKET;0;24990.25;DAY;<id>O;<id>S;;")
            print("           PLACE;Sim101;MNQ 12-26;SELL;2;LIMIT;25080.00;0;DAY;<id>O;<id>T;;")
            print("  BE       CHANGE;;;;0;;0;25020.25;;;<id>S;;")
            print("  add      PLACE;Sim101;MNQ 12-26;BUY;3;MARKET;0;0;DAY;;<id>A1;;   (LIT scale_in, off by default)")
            print("           CHANGE;;;;5;;0;0;;;<id>S;;  CHANGE;;;;5;;0;0;;;<id>T;;   (the one OCO pair covers all 5)")
            print("  exit     CLOSEPOSITION;Sim101;MNQ 12-26;;;;;;;;;;   (+ CANCEL;;;;;;;;;;<id>S;; for any leg still working)")
            print("  kill     FLATTENEVERYTHING;;;;;;;;;;;;")
        for name, ok, detail in checks:
            if not ok:
                print(f"  FAIL  {name}  {detail}")
    return npass == len(checks)


def market_open_local(ts) -> bool:
    from .live import market_open
    return market_open(ts)


if __name__ == "__main__":
    # run the canonical engine.ninjatrader module (the one engine.live imports), not a second copy named __main__
    from engine import ninjatrader as _canonical
    sys.exit(_canonical.main())
