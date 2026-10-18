"""NinjaTrader 8 execution adapter and bar feed (ATI File Interface: Order Instruction Files).

Why: the MFFU account clears through Tradovate, and Tradovate gives prop accounts no API keys, so engine/tradovate.py
cannot reach it. NinjaTrader 8 Desktop can trade the same account (its Tradovate connection) and executes Order
Instruction Files (OIF) that any program writes into Documents\\NinjaTrader 8\\incoming\\. No credentials are involved.

Same contract as live.PaperAdapter / tradovate.TradovateAdapter. LiveBot builds it with the start config and calls
send(action) with
  {"side": "buy"|"sell", "qty": micros, "stop": px, "target": px, "entry": px, "sym": "NQ", "entry_t": t}  -> bracket
  {"side": "exit", "reason": ..., "entry_t": t}   -> CLOSEPOSITION, then cancel any of our legs still working
  {"side": "exit", "reason": "KILL SWITCH"}       -> kill(): FLATTENEVERYTHING (every account connected in NinjaTrader)
  {"side": "modify", "stop": px}                  -> CHANGE the stop order (breakeven at 1R)
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

Bar feed: NinjaTraderBars reads the CSVs that ninjatrader/LE_BarFeed.cs writes (Documents\\NinjaTrader 8\\le_feed\\
MNQ_5m.csv ...) and returns the same frame as live._yahoo_recent (time = bar OPEN, unix seconds). engine/live.py uses
it for data_source "ninjatrader" and falls back to Yahoo, with a logged warning, when the file is missing or stale.

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
from collections import deque
from zoneinfo import ZoneInfo

from .tradovate import LIVE_PHRASE, MAX_MICROS_HARD, MAX_MINIS, MICRO, MINI, TICK, front_month

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(ROOT, "data", "ninjatrader_state.json")      # gitignored: open brackets survive a restart
AUDIT_PATH = os.path.join(ROOT, "logs", "ninjatrader_oif.log")         # every OIF line ever written (logs/ is ignored)
LIVE_ENV = "NINJATRADER_LIVE"            # must be "1" in the SERVER's environment before a non-Sim account can trade
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
            w = (cfg.get("model_params") or lm.get("lit") or {}).get("window") or _lit.DEFAULTS["window"]
            return int(min(a for a, _ in w))
    except Exception:
        pass
    return 480


def is_sim(account: str) -> bool:
    return bool(SIM_ACCOUNT.match(str(account or "").strip()))


def resolve_account(cfg: dict | None = None) -> str:
    cfg = cfg or {}
    return str(cfg.get("nt_account") or os.environ.get("NINJATRADER_ACCOUNT") or "Sim101").strip()


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
        self.max_micros = min(MAX_MICROS_HARD, int(p.get("max_micros", cfg.get("max_micros", MAX_MICROS_HARD))))
        mode = str(cfg.get("nt_contract") or "micro").lower()
        self.contract_mode = mode if mode in ("micro", "auto") else "auto"   # micro: MNQ only | auto: 10+ micros as NQ minis
        self.account = resolve_account(cfg)
        self.folder = cfg.get("nt_folder") or default_folder()
        self.incoming = os.path.join(self.folder, "incoming")
        self.outgoing = os.path.join(self.folder, "outgoing")
        self.write_mode = "move" if cfg.get("nt_write_mode") == "move" else "direct"
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
        self._seq = 0
        self.sim = is_sim(self.account)
        self.env = "demo" if self.sim else "live"      # LiveBot._remember: memory source paper / live
        self.disabled = self._live_gate()
        self._restore()
        if not readonly:
            self._sweep_stale_oifs(max_age=10.0)
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
        return None

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
            self._push(lambda P: P.text_payload(self._push_src(), "risk", "NinjaTrader needs a look", text,
                                                key=f"risk:{int(self.clock()) // 60}:{abs(hash(text)) % 10**6}"))
        except Exception:
            pass

    # ------------------------------------------------------------------ phone notifications (engine/push.py)
    def _push_account(self):
        if self.sim:
            return self.account                  # "Sim101"
        try:
            from . import push
            from .lab_adapter import live_model
            return push.account_label(live_model(), "live")
        except Exception:
            return "MFFU 50K"

    def _push(self, make):
        """Send one phone notification (background thread, once per key). Only the real bot: never the self-test or a
        harness with its own state file. Never raises."""
        if self._alert_fn is not None or self.readonly or self.state_path != STATE_PATH:
            return
        try:
            from . import push
            push.pc_notify(make(push))
        except Exception:
            pass

    def _push_fill(self, lg):
        """ENTRY: NinjaTrader reported the entry fill."""
        inst = lg["instrument"].split(" ")[0]
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
            bad = validate_line(ln)
            if bad:                                  # a bug guard: a malformed line is never handed to NinjaTrader
                msg = f"internal: refused to write invalid OIF line {ln!r}: {'; '.join(bad)}"
                self.last_error = msg
                self._log("error", msg)
                return {"ok": False, "error": msg}
        data = ("\r\n".join(lines) + "\r\n").encode("ascii", errors="strict")
        err = None
        for attempt in range(3):
            self._seq += 1
            name = f"oif_le_{time.time_ns() // 1_000_000}_{self._seq}.txt"
            path = os.path.join(self.incoming, name)
            try:
                if self.write_mode == "move":
                    # "Move or directly write OIF files to the incoming folder" (help guide): written next door, then moved in whole
                    box = os.path.join(self.folder, "le_outbox")
                    os.makedirs(box, exist_ok=True)
                    tmp = os.path.join(box, name)
                    with open(tmp, "wb") as fh:
                        fh.write(data)
                    os.replace(tmp, path)
                else:
                    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0))
                    try:
                        os.write(fd, data)                   # one write, then close: NinjaTrader never sees half a file
                    finally:
                        os.close(fd)
                self._audit(name, lines)
                self._log("broker", f"NinjaTrader {label} -> {name}: " + " | ".join(lines))
                return {"ok": True, "file": name, "path": path, "lines": list(lines)}
            except OSError as e:
                err = e
                time.sleep(0.2 * (attempt + 1))
        msg = f"could not write the order file ({err.__class__.__name__}: {err})"
        self.last_error = msg
        self._log("error", "NinjaTrader " + msg)
        return {"ok": False, "error": msg}

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
            try:
                mtime = os.path.getmtime(path)
            except OSError:
                mtime = None
            out.append({"instrument": n[:-len(suffix)], **pos, "file": n, "mtime": mtime})
        return {"ok": True, "account": self.account, "positions": out}

    def position_for(self, instrument: str):
        """The position file of one instrument ('MNQ 12-26' matches 'MNQ 12-26 Globex_Sim101_Position.txt'); None = no file."""
        for p in self.positions()["positions"]:
            if p["instrument"] == instrument or p["instrument"].startswith(instrument + " "):
                return p
        return None

    def connections(self) -> dict:
        out = {}
        for n in self._listing():
            if not n.lower().endswith(".txt") or "_position" in n.lower():
                continue
            raw = _read_text(os.path.join(self.outgoing, n))
            v = (raw or "").strip().upper()
            if v in ("CONNECTED", "DISCONNECTED"):
                out[n[:-4]] = v
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
            e = _et(self.clock())
            mod = e.hour * 60 + e.minute
            cut = self._flat_today(e, entry=True)
            if e.weekday() >= 5 or mod >= cut or mod < self.session_from:
                return {"ok": False, "error": f"REFUSED: entry outside the session ({e:%a %H:%M} ET; entries "
                                              f"{self.session_from // 60:02d}:{self.session_from % 60:02d}-"
                                              f"{cut // 60:02d}:{cut % 60:02d} ET on weekdays"
                                              + (", CME early close today" if cut < self.flat_mod else "") + ")"}
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
        insts = self._instruments()
        plan = [(insts["mini"], sp["minis"], "N"), (insts["micro"], sp["micros"], "M")]
        plan = [x for x in plan if x[1] > 0]
        for inst, _, _ in plan:
            p = self.position_for(inst)
            if p and p["side"] != "FLAT":
                return {"ok": False, "error": f"REFUSED: NinjaTrader shows {p['side']} {p['qty']} {inst} on {self.account}: not adding to it"}
        conn = self.connections()
        if conn and all(v == "DISCONNECTED" for v in conn.values()):
            return {"ok": False, "error": f"REFUSED: NinjaTrader reports every connection DISCONNECTED ({', '.join(conn)})"}
        ts = int(action.get("entry_t") or self.clock())
        tag = _nonce()
        legs = []
        for inst, qty, kind in plan:
            base = f"LE{ts}{tag}{kind}"
            legs.append({"instrument": inst, "qty": qty, "side": side, "dir": d, "entry_t": ts, "stop": stop, "target": target,
                         "entry_id": base + "E", "stop_id": base + "S", "target_id": base + "T", "oco": base + "O",
                         "status": "entry_sent", "filled": 0, "fill_px": None, "fill_mtime": None, "bracket_qty": 0, "stop0": stop,
                         "sent_at": self.clock()})
        r = self._send_lines([place_line(self.account, lg["instrument"], side, lg["qty"], "MARKET", order_id=lg["entry_id"])
                              for lg in legs], "ENTRY")
        if not r["ok"]:
            if r.get("withdrawn"):
                self.withdrawn += [{"entry_id": lg["entry_id"], "leg": lg, "t": self.clock()} for lg in legs]
            self._save()
            return {"ok": False, "adapter": self.name, "account": self.account, "error": r["error"], "oif": r.get("file")}
        self.legs = legs
        self._save()
        self._wait(lambda: all(self._entry_settled(lg) for lg in legs), self.fill_wait)
        out, errors = [], []
        for lg in legs:
            st = self.read_order(lg["entry_id"])
            self._note_fill(lg, st)
            if lg["filled"] > 0:
                res = self._protect(lg)
                out.append({"instrument": lg["instrument"], "qty": lg["qty"], "filled": lg["filled"], "fill_px": lg["fill_px"], **res})
                if not res["ok"]:
                    errors.append(f"{lg['instrument']}: {res.get('error')}")
            elif st and st["state"] in DEAD:
                lg["status"] = "rejected"
                errors.append(f"{lg['instrument']}: entry {st['state']}")
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
                "legs": out, **({} if ok else {"error": "; ".join(errors)})}

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
            return since is None          # never a position file: flat only if we never had a fill on it
        return p["side"] == "FLAT" and (since is None or (p.get("mtime") or 0) >= since - 0.001)

    def _cancel_working(self, legs, why) -> list:
        ids = []
        for lg in legs:
            for oid in (lg["stop_id"], lg["target_id"]) + ((lg["entry_id"],) if lg["status"] in ("pending", "entry_sent", "cancel_pending") else ()):
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

    def kill(self) -> dict:
        """FLATTENEVERYTHING: NinjaTrader cancels every working order and flattens every position on EVERY account and
        connection it has (not only this bot's). Works even when the account is disabled for new orders."""
        if self.readonly:
            return {"ok": False, "error": "REFUSED: read-only adapter"}
        self.killed = True
        r = self._send_lines([FLATTEN_EVERYTHING], "KILL")
        legs = list(self.legs)
        if r["ok"]:
            self._retire(legs, "kill switch")
            self._risk("KILL: FLATTENEVERYTHING sent (every account and connection in NinjaTrader)")
        else:
            self._risk(f"KILL could not reach NinjaTrader ({r.get('error')}). Flatten the account in NinjaTrader or the "
                       "Tradovate/MFFU app NOW.", alert=True)
        self._save()
        return {"ok": r["ok"], "adapter": self.name, "oif": r.get("file"), **({} if r["ok"] else {"error": r.get("error")})}

    def send(self, action: dict) -> dict:
        """LiveBot entry point. Never raises."""
        try:
            with self.lock:
                side = action.get("side")
                if side in ("buy", "sell"):
                    return self.place_bracket(action)
                if side == "exit":
                    if str(action.get("reason") or "").upper() == "KILL SWITCH":
                        return self.kill()
                    return self.flatten(action)
                if side == "modify":
                    return self.modify_stop(action.get("stop"), action)
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
                self._tick_withdrawn(now)
                for lg in list(self.legs):
                    self._tick_leg(lg, now)
                self._tick_flat_time(now)
                self._save()
                return {"ok": True, "legs": len(self.legs)}
        except Exception as e:
            self.last_error = f"tick: {e.__class__.__name__}: {e}"
            self._log("error", "NinjaTrader " + self.last_error)
            return {"ok": False, "error": self.last_error}

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
                self._protect(lg)
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
                self._protect(lg)
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
        # protected: the entry grew (partial fill completed) -> grow the bracket
        if lg["filled"] > lg["bracket_qty"]:
            q = lg["filled"]
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
        if self._flat_since(lg["instrument"], (lg.get("fill_mtime") or 0) + 0.001):
            seen = self._outside_flat.get(lg["entry_id"], 0) + 1
            self._outside_flat[lg["entry_id"]] = seen
            if seen >= 2:                       # two polls in a row: closed by hand in NinjaTrader / the Tradovate app
                ids = self._cancel_working([lg], "position closed outside the bot")
                self._retire([lg], "closed outside the bot")
                self._log("risk", f"NinjaTrader: {lg['instrument']} was closed outside the bot; leftover orders cancelled: {ids or 'none'}")
        else:
            self._outside_flat.pop(lg["entry_id"], None)

    def _tick_flat_time(self, now):
        e = _et(now)
        mod = e.hour * 60 + e.minute
        if e.weekday() >= 5:
            return
        flat = self._flat_today(e)
        for lg in [x for x in self.legs if x["status"] in ("protected", "unprotected", "pending", "cancel_pending")]:
            if mod >= flat or mod < self.session_from:
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
                "legs": self.legs, "withdrawn": self.withdrawn, "killed": self.killed}
        try:
            os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
            tmp = self.state_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(blob, fh, indent=1, default=str)
            os.replace(tmp, self.state_path)
        except Exception as e:
            self.last_error = f"state save failed: {e}"

    def _restore(self):
        try:
            with open(self.state_path, encoding="utf-8") as fh:
                s = json.load(fh)
        except FileNotFoundError:
            return
        except Exception as e:
            self._log("warn", f"NinjaTrader state file unreadable ({e}): starting with no open brackets")
            return
        if s.get("account") != self.account or s.get("day") != _trading_day(self.clock()):
            return
        self.legs = [lg for lg in (s.get("legs") or []) if isinstance(lg, dict) and lg.get("status") in OPEN_STATUSES]
        self.withdrawn = [w for w in (s.get("withdrawn") or []) if isinstance(w, dict)]

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
                "audit_log": self.audit_path, "state_file": self.state_path}


# ---------------------------------------------------------------------- bar feed (LE_BarFeed.cs -> CSV -> the bot)
class NinjaTraderBars:
    """Reads Documents\\NinjaTrader 8\\le_feed\\<ROOT>_<N>m.csv (written by ninjatrader/LE_BarFeed.cs: time = bar OPEN in
    unix seconds, open, high, low, close, volume) and returns the frame live._yahoo_recent returns. 15m / 1h bars are
    built from the 5m file. recent_bars() -> (frame | None, reason, covers_period)."""
    MINUTES = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60}

    def __init__(self, folder=None, roots=None, stale_s=None):
        self.dir = os.path.join(folder or default_folder(), FEED_DIR)
        self.roots = roots or {"NQ": ["MNQ", "NQ"], "ES": ["MES", "ES"]}
        self.stale_s = stale_s
        self._cache: dict = {}

    def file_for(self, sym, minutes):
        for root in self.roots.get(sym, [sym]):
            p = os.path.join(self.dir, f"{root}_{minutes}m.csv")
            if os.path.exists(p):
                return p
        return None

    def load(self, path):
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
        try:
            df = pd.read_csv(path, header=None, names=cols, usecols=range(6), on_bad_lines="skip", dtype=str,
                             engine="python")
        except Exception:
            return None
        for c in cols:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df = df.dropna(subset=["time", "open", "high", "low", "close"])          # header row, half-written last line
        df["volume"] = df["volume"].fillna(0.0)
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
        m = re.fullmatch(r"(\d+)d", str(period or "5d"))
        start = now - (int(m.group(1)) if m else 5) * 86400
        full = int(df["time"].iloc[0]) <= start + 3600
        why = "ok" if full else f"feed starts {_et(int(df['time'].iloc[0])):%m-%d %H:%M} ET, later than the {period} asked for"
        gaps = self._gap_ratio(df[df["time"] >= now - 3 * 86400], mins * 60, market_open)
        if gaps > 0.10:
            full = False
            why = f"feed is missing {gaps:.0%} of the bars of the last 3 days (ETH trading hours on the chart?)"
        return df.reset_index(drop=True), why, full

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
    feed = NinjaTraderBars(cfg.get("nt_folder"))
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


def _cli_sim_check(cfg, roundtrip=False):
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
    m = ad.send({"side": "modify", "stop": fill - 20})
    print(("OK  " if m["ok"] else "FAIL") + f" 2. stop moved {lg['stop'] if m['ok'] else ''} -> {fill - 20:.2f}: {m.get('legs')} {m.get('error') or ''}")
    p = ad.position_for(lg["instrument"])
    print(f"   position file: {p}")
    x = ad.send({"side": "exit", "reason": "SIM ROUNDTRIP", "entry_t": lg["entry_t"]})
    print(("OK  " if x["ok"] else "FAIL") + f" 3. CLOSEPOSITION: flat confirmed {x.get('flat_confirmed')}, leftovers cancelled {x.get('cancelled_leftovers')} {x.get('error') or ''}")
    print(f"   stop {ad.read_order(lg['stop_id'])}, target {ad.read_order(lg['target_id'])}, position {ad.position_for(lg['instrument'])}")
    return 0 if r["ok"] and m["ok"] and x["ok"] else 1


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="python -m engine.ninjatrader", description="NinjaTrader 8 route for the Liquidity Engine bot")
    ap.add_argument("--selftest", action="store_true", help="offline self-test (simulated NinjaTrader folders, no network)")
    ap.add_argument("--status", action="store_true", help="what the bot sees in NinjaTrader's folders and the bar feed")
    ap.add_argument("--sim-check", action="store_true", help="Sim only: far-away 1-lot MNQ limit order, then cancel it")
    ap.add_argument("--sim-roundtrip", action="store_true", help="Sim only, market open: 1 MNQ + stop/target, move the stop, flatten")
    ap.add_argument("--start", action="store_true", help="start the PC bot (server.py running) on NinjaTrader")
    ap.add_argument("--stop", action="store_true", help="stop the PC bot")
    ap.add_argument("--kill", action="store_true", help="kill switch: server kill, or FLATTENEVERYTHING directly when the server is down")
    ap.add_argument("--account", default=None, help="NinjaTrader account name (Accounts tab 'Name'), default Sim101")
    ap.add_argument("--folder", default=None, help="Documents\\NinjaTrader 8 folder if not the default")
    ap.add_argument("--data", default="ninjatrader", choices=["ninjatrader", "yahoo"], help="bar source for --start")
    ap.add_argument("--confirm", default="", help=f"LIVE accounts only: the phrase '{LIVE_PHRASE}'")
    ap.add_argument("--instrument", default=None, help="force the instrument name, e.g. 'MNQ 12-26'")
    ap.add_argument("--contract", default=None, choices=["micro", "auto"], help="micro = MNQ only (default); auto = 10+ micros as NQ minis")
    ap.add_argument("--close-suffix", default=None, help="text added to the CLOSEPOSITION instrument, e.g. ' Globex'")
    ap.add_argument("--write-mode", default=None, choices=["direct", "move"], help="how order files reach incoming (default direct)")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8766)))
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    opts = {"nt_account": a.account, "nt_folder": a.folder, "nt_instrument": a.instrument, "nt_contract": a.contract,
            "nt_close_suffix": a.close_suffix, "nt_write_mode": a.write_mode}
    cfg = {"adapter": "ninjatrader", "sym": "NQ", **{k: v for k, v in opts.items() if v}}
    if a.selftest:
        return 0 if selftest(verbose=not a.quiet) else 1
    if a.status:
        return _cli_status(cfg)
    if a.sim_check or a.sim_roundtrip:
        return _cli_sim_check(cfg, roundtrip=a.sim_roundtrip)
    if a.start:
        body = {"sym": "NQ", "tf": "5m", "adapter": "ninjatrader", "armed": True, "present": True, "poll_sec": 60,
                "data_source": a.data, **{k: v for k, v in cfg.items() if k.startswith("nt_")}}
        if a.confirm:
            body["confirm"] = a.confirm
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
            print("Server kill switch:", _http(a.port, "/api/live/kill", {}))
            return 0
        except Exception as e:
            print(f"Server not reachable ({e}): writing FLATTENEVERYTHING to NinjaTrader directly")
        ad = NinjaTraderAdapter({**cfg, "nt_state_path": os.path.join(ROOT, "data", "ninjatrader_state.json")})
        r = ad.kill()
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
    saved_env = {k: os.environ.get(k) for k in (LIVE_ENV, "NINJATRADER_ACCOUNT", "NINJATRADER_FOLDER")}
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
                   "nt_state_path": os.path.join(tmp, "nt_state.json"), "nt_audit_log": os.path.join(tmp, "oif.log"), **(cfg_extra or {})}
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
        # ---- 8. kill: FLATTENEVERYTHING, then no new entries
        k = len(fake.files)
        r = ad.send({"sym": "NQ", "side": "exit", "reason": "KILL SWITCH"})
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
        live4 = make({"nt_account": "MFFUEV12345", "confirm": LIVE_PHRASE})
        live5 = make({"nt_account": "MFFUEV12345", "confirm": LIVE_PHRASE, "armed": False})
        os.environ.pop(LIVE_ENV, None)
        check("live gate: a non-Sim account is refused without armed, without the exact phrase, or without NINJATRADER_LIVE=1",
              live1.disabled and "not armed" in live1.disabled and "REFUSED" in rl["error"] and len(fake.files) == n0
              and "phrase" in live2.disabled and LIVE_ENV in live3.disabled and live5.disabled, f"{live1.disabled} | {live2.disabled} | {live3.disabled}")
        check("live gate: armed + phrase + NINJATRADER_LIVE=1 enables it (env 'live' for the trade memory)",
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
        check("feed: stale during market hours -> None with the reason (the bot falls back to Yahoo)", st_df is None and "stale" in st_why, st_why)
        es_df, es_why, _ = feed.recent_bars("ES", "5m", "2d", now=fnow)
        check("feed: no file for a symbol -> None with the file name to create", es_df is None and "MES_5m.csv" in es_why, es_why)
        shifted = "time,open,high,low,close,volume\n" + "".join(f"{a + 3600},{b},{c},{d},{e},{f}\n" for a, b, c, d, e, f in rows)
        with open(os.path.join(feed_dir, "MNQ_1m.csv"), "w") as fh:
            fh.write(shifted)
        sh_df, sh_why, _ = NinjaTraderBars(folder, roots={"NQ": ["MNQ"]}).recent_bars("NQ", "1m", "2d", now=fnow + 3600)
        check("feed: bar times shifted by an hour (bars at 17:xx ET) are detected and refused", sh_df is None and "shifted" in sh_why, sh_why)

        # ---- 14. LiveBot wiring (no Engine run: routing is driven with a hand-made model state)
        from . import live
        bot = live.LiveBot()
        bot.clock = lambda: now[0]
        bot.state_path = os.path.join(tmp, "live_state.json")
        bot._remember = lambda *a, **kw: None           # never touch data/memory.db from a test
        r0 = bot.start({"sym": "NQ", "tf": "5m", "adapter": "ninjatrader", "nt_folder": folder}, spawn=False)
        check("LiveBot: adapter ninjatrader refused unless armed", not r0["ok"] and "armed" in r0["error"])
        now[0] = dt.datetime(2026, 10, 22, 10, 5, 3, tzinfo=ET).timestamp()
        r1 = bot.start({"sym": "NQ", "tf": "5m", "adapter": "ninjatrader", "armed": True, "data": "ninjatrader", "nt_folder": folder,
                        "nt_state_path": os.path.join(tmp, "nt_state2.json"), "nt_audit_log": os.path.join(tmp, "oif.log")}, spawn=False)
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
        try:
            now[0] = fnow
            got = bot._fetch_recent("NQ", "5m", "2d")
            fresh_ok = len(got) == len(df) and not calls and not bot.health.get("fallback")
            now[0] = fnow + 1800
            bot.health["fallback"] = False
            got2 = bot._fetch_recent("NQ", "5m", "2d")
            check("LiveBot: data_source ninjatrader serves the feed (no Yahoo call); stale -> Yahoo fallback + warning + flag",
                  fresh_ok and calls == [("NQ", "5m")] and len(got2) == 1 and bot.health["fallback"]
                  and any("falling back to Yahoo" in x["text"] for x in bot.log), f"calls={calls}")
        finally:
            live._yahoo_recent = orig_y
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
        fake.move(25020.0)
        now[0] = dt.datetime(2026, 10, 22, 2, 35, 3, tzinfo=ET).timestamp()        # Thursday 02:35 ET (London)
        lbot = live.LiveBot()
        lbot.clock = lambda: now[0]
        lbot.state_path = os.path.join(tmp, "live_state_lit.json")
        lbot._remember = lambda *a, **kw: None
        r2 = lbot.start({"sym": "NQ", "tf": "5m", "adapter": "ninjatrader", "armed": True, "data": "ninjatrader", "nt_folder": folder,
                         "model": "lit", "model_params": {"window": [[120, 930]]},
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
        # 1m bars for LIT's entry come from LE_BarFeed's MNQ_1m.csv (data_source ninjatrader), Yahoo only when it is stale
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
            got1 = lbot._lit_1m("NQ", f1now, f1now - 5 * 86400)
            ok1 = got1 is not None and int(got1["time"].iloc[-1]) == last1 and not calls and len(got1) == len([r_ for r_ in rows1 if r_[0] >= f1now - 5 * 86400])
            now[0] = f1now + 1800
            got2 = lbot._lit_1m("NQ", f1now + 1800, f1now - 5 * 86400)
            check("LIT: 1m bars from NinjaTrader's MNQ_1m.csv (no Yahoo call); a stale 1m file -> Yahoo 1m, bot health untouched",
                  ok1 and calls == [("NQ", "1m")] and got2 is not None and not lbot.health.get("fallback"), f"calls={calls}")
        finally:
            live._yahoo_recent = orig_y
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
