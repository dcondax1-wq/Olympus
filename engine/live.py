"""Live / paper trading loop.

The live bot runs the *same* Engine as the backtester on a rolling window of the latest bars every poll,
so live decisions and backtest decisions can never drift apart. New entries/exits detected after the bot
was started are routed to the selected broker adapter.

Adapters
  paper       - default. Simulated fills recorded in the ledger (no external calls).
  traderspost - POSTs JSON signals to YOUR TradersPost webhook (MFFU supports TradersPost-style automation).
  tradovate   - REST skeleton for Tradovate (demo endpoint by default). Requires your own API credentials in
                environment variables; disabled unless explicitly armed. Test on demo first.
  ninjatrader - NinjaTrader 8 ATI order files (engine/ninjatrader.py): the route into the MFFU account through
                NinjaTrader Desktop. Sim101 by default; a real account needs armed + phrase + NINJATRADER_LIVE=1.

Data: no Yahoo by default (owner 2026-10-19, "no_yahoo": live_model.json / start cfg, engine/pcbars.py): history from
the TradingView exports (data/NQ_5m.csv, data/NQ_1m.csv) + the bot's own archive of NinjaTrader bars (data/nt_bars/), fresh
bars from NinjaTrader only (data_source "ninjatrader": the real CME bars ninjatrader/LE_BarFeed.cs writes). When that feed
is missing or stale, NEW entries are blocked (FEED STALE) and an open trade keeps its broker brackets; nothing falls back
to Yahoo. With "no_yahoo": false the old behaviour returns (data_source "yahoo", or Yahoo as the NinjaTrader fallback).
"""
from __future__ import annotations

import json
import math
import os
import threading
import time
import traceback
import urllib.request
from collections import deque

import pandas as pd

from .data import DATA_DIR, from_frame, load
from .instruments import PARTNER
from .model import Engine, merge_params
from . import pcbars
import datetime as _dt
from zoneinfo import ZoneInfo

import numpy as np

from .data import TF_SECONDS

YAHOO = {"NQ": "NQ=F", "ES": "ES=F"}


def _yahoo_recent(sym: str, interval="5m", period="5d") -> pd.DataFrame:
    import yfinance as yf
    df = yf.download(YAHOO[sym], period=period, interval=interval, progress=False, auto_adjust=False, prepost=True)
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].dropna()
    idx = df.index.tz_convert("UTC") if df.index.tz is not None else df.index.tz_localize("UTC")
    secs = (idx - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta(seconds=1)
    df = df.reset_index(drop=True)
    df.insert(0, "time", pd.Series(secs, dtype="int64").values)
    return df


class PaperAdapter:
    name = "paper"

    def __init__(self, cfg):
        self.cfg = cfg

    def send(self, action: dict):
        return {"ok": True, "adapter": "paper", "note": "simulated"}


class TradersPostAdapter:
    """Sends {ticker, action, quantity, stopLoss, takeProfit} to a TradersPost webhook URL you supply."""
    name = "traderspost"

    def __init__(self, cfg):
        self.url = cfg.get("webhook_url") or os.environ.get("TRADERSPOST_WEBHOOK", "")
        self.ticker_map = cfg.get("ticker_map", {"NQ": "MNQ1!", "ES": "MES1!"})

    def send(self, action: dict):
        if not self.url:
            return {"ok": False, "error": "no webhook url configured"}
        body = {"ticker": self.ticker_map.get(action["sym"], action["sym"]), "action": action["side"],
                "quantity": action["qty"], "orderType": "market"}
        if action.get("stop"):
            body["stopLoss"] = {"type": "stop", "stopPrice": round(action["stop"], 2)}
        if action.get("target"):
            body["takeProfit"] = {"limitPrice": round(action["target"], 2)}
        if action["side"] == "exit":
            body = {"ticker": body["ticker"], "action": "exit"}
        req = urllib.request.Request(self.url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return {"ok": 200 <= r.status < 300, "status": r.status, "sent": body}


class TradovateAdapter:
    """Minimal Tradovate REST client (bracket orders via placeOSO). Demo environment unless TRADOVATE_ENV=live.
    Credentials come only from environment variables on your machine: TRADOVATE_USER, TRADOVATE_PASS,
    TRADOVATE_APP_ID, TRADOVATE_CID, TRADOVATE_SECRET, TRADOVATE_ACCOUNT_ID, TRADOVATE_ACCOUNT_SPEC."""
    name = "tradovate"

    def __init__(self, cfg):
        env = os.environ.get("TRADOVATE_ENV", "demo")
        self.base = "https://live.tradovateapi.com/v1" if env == "live" else "https://demo.tradovateapi.com/v1"
        self.token = None
        self.contract_map = cfg.get("contract_map", {})  # e.g. {"NQ": "MNQZ6"}

    def _post(self, path, body, auth=True):
        headers = {"Content-Type": "application/json"}
        if auth:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(self.base + path, data=json.dumps(body).encode(), headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())

    def _auth(self):
        e = os.environ
        need = ["TRADOVATE_USER", "TRADOVATE_PASS", "TRADOVATE_APP_ID", "TRADOVATE_CID", "TRADOVATE_SECRET"]
        if any(not e.get(k) for k in need):
            raise RuntimeError("Tradovate credentials not set in environment")
        r = self._post("/auth/accesstokenrequest", {"name": e["TRADOVATE_USER"], "password": e["TRADOVATE_PASS"],
                                                     "appId": e["TRADOVATE_APP_ID"], "appVersion": "1.0",
                                                     "cid": int(e["TRADOVATE_CID"]), "sec": e["TRADOVATE_SECRET"]}, auth=False)
        self.token = r.get("accessToken")
        if not self.token:
            raise RuntimeError(f"auth failed: {r}")

    def send(self, action: dict):
        if self.token is None:
            self._auth()
        e = os.environ
        symbol = self.contract_map.get(action["sym"])
        if not symbol:
            return {"ok": False, "error": "set contract_map, e.g. {'NQ': 'MNQZ6'}"}
        if action["side"] == "exit":
            r = self._post("/order/liquidateposition", {"accountId": int(e["TRADOVATE_ACCOUNT_ID"]), "contractId": action.get("contract_id"), "admin": False})
            return {"ok": True, "resp": r}
        side = "Buy" if action["side"] == "buy" else "Sell"
        opp = "Sell" if side == "Buy" else "Buy"
        body = {"accountSpec": e["TRADOVATE_ACCOUNT_SPEC"], "accountId": int(e["TRADOVATE_ACCOUNT_ID"]), "action": side,
                "symbol": symbol, "orderQty": int(action["qty"]), "orderType": "Market", "isAutomated": True,
                "bracket1": {"action": opp, "orderType": "Limit", "price": round(action["target"], 2)},
                "bracket2": {"action": opp, "orderType": "Stop", "stopPrice": round(action["stop"], 2)}}
        return {"ok": True, "resp": self._post("/order/placeOSO", body)}


from .tradovate import TradovateAdapter as _TvAdapter  # full REST adapter with live gates (engine/tradovate.py)
from .ninjatrader import NinjaTraderAdapter as _NtAdapter  # NinjaTrader 8 order files with live gates (engine/ninjatrader.py)
ADAPTERS = {"paper": PaperAdapter, "traderspost": TradersPostAdapter, "tradovate": _TvAdapter,
            "tradovate-demo": _TvAdapter, "tradovate-live": _TvAdapter, "ninjatrader": _NtAdapter}
# Optional adapter capability flags, read with getattr(adapter, flag, False) (paper and Tradovate set none of them):
#   loop_tick         tick() is called at the start of every poll
#   route_stop_moves  the model's stop moves (breakeven at 1R) are sent as {"side": "modify", "stop": px}
#   route_all_exits   every model exit is routed (TIME STOP, giveback, ...), not only TIME; a flatten when flat is harmless
#   kill_flattens_all the kill switch is routed even when the model shows no position


STATE_PATH = os.path.join(DATA_DIR, "live_state.json")
ET_TZ = ZoneInfo("America/New_York")
LIVE_DEFAULTS = {
    "sym": "NQ", "tf": "5m", "poll_sec": 60, "adapter": "paper", "params": {}, "armed": False,
    "data_source": "yahoo",     # yahoo (free, ~10 min delayed) | tradovate (engine.tradovate.TradovateData) | ninjatrader
                                # (LE_BarFeed CSVs, engine.ninjatrader.NinjaTraderBars); both fall back to yahoo only with
                                # no_yahoo off. no_yahoo on (the default, engine/pcbars.py): "yahoo" becomes "ninjatrader"
    "window_days": 20,          # calendar days of base bars fed to the Engine each poll (verified identical to the full run)
    "stale_polls_block": 3,     # block NEW entries once the feed has been stale this many polls in a row inside an entry window
}
STATE_VERSION = 1


def _et(ts):
    return _dt.datetime.fromtimestamp(int(ts), ET_TZ)


def trading_day(ts) -> str:
    """Trading-day label: 18:00 ET rolls to the next calendar date (same convention as engine.data)."""
    return (_et(ts) + _dt.timedelta(hours=6)).strftime("%Y-%m-%d")


def market_open(ts) -> bool:
    """Is CME Globex expected to be printing bars at `ts`? Sun 18:00 ET -> Fri 17:00 ET, daily break 17:00-18:00."""
    e = _et(ts)
    mod = e.hour * 60 + e.minute
    if e.weekday() == 5:
        return False
    if e.weekday() == 6 and mod < 1080:
        return False
    if e.weekday() == 4 and mod >= 1020:
        return False
    return not (1020 <= mod < 1080)


TICK = 0.25


def tick_px(px, d: int = 1, target: bool = False):
    """A price on the 0.25 tick grid before it is routed. Stops: nearest tick (LIT's stop is already 1 tick beyond the sweep
    extreme). Targets: rounded TOWARD the entry (a long's target down, a short's up), so the broker's limit sits at or in
    front of the model's target and fills whenever the model counts the target (LIT's VIX-band target is not a tick price)."""
    if px is None:
        return None
    x = float(px) / TICK
    if target:
        q = math.floor(x + 1e-9) if d == 1 else math.ceil(x - 1e-9)
    else:
        q = round(x)
    return round(q * TICK, 2)


def _jsonable(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (set, tuple)):
        return list(o)
    return str(o)


def _cover_gap(hist: pd.DataFrame, now: int, period: str, max_days: int) -> str:
    """Yahoo period long enough to reach back to the end of the stored history (plus 2 days of overlap), so the rolling
    window never has a hole once the CSV history goes stale. Yahoo caps 5m at 60 days and 1h at 730 days."""
    if hist is None or not len(hist):
        return f"{max_days}d"
    lag = int((now - int(hist["time"].max())) / 86400) + 2
    return period if lag <= 5 else f"{min(lag, max_days)}d"


def clean_bars(df: pd.DataFrame, secs: int, now: int, grid: bool = True):
    """Closed, well-formed, de-duplicated bars only (grid-aligned too when `grid`; 1h holiday half-days sit at :30).
    Returns (frame, drop counts)."""
    cols = ["time", "open", "high", "low", "close", "volume"]
    drops = {"malformed": 0, "misaligned": 0, "duplicate": 0, "forming": 0}
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=cols), drops
    df = df[[c for c in cols if c in df.columns]].copy()
    if "volume" not in df.columns:
        df["volume"] = 0.0
    n0 = len(df)
    df = df.dropna(subset=["time", "open", "high", "low", "close"])
    df = df[(df["high"] >= df["low"]) & (df["low"] > 0) & (df["high"] >= df["open"]) & (df["high"] >= df["close"])
            & (df["low"] <= df["open"]) & (df["low"] <= df["close"])]
    drops["malformed"] = n0 - len(df)
    df["time"] = df["time"].astype("int64")
    if grid:
        n0 = len(df)
        df = df[df["time"] % secs == 0]
        drops["misaligned"] = n0 - len(df)
    n0 = len(df)
    df = df.drop_duplicates("time", keep="last").sort_values("time")
    drops["duplicate"] = n0 - len(df)
    n0 = len(df)
    df = df[df["time"] + secs <= now]            # drop the still-forming bar: only closed bars drive decisions
    drops["forming"] = n0 - len(df)
    return df.reset_index(drop=True), drops


def forming_open(df, secs: int, now: int):
    """(open time, open) of the bar still forming at `now` in a fresh fetch (Yahoo shows it from its first trade), or None.
    clean_bars drops that bar; only its open is used (LIT sizes an entry decided on the 1m CISD close from it)."""
    try:
        if df is None or not len(df) or "time" not in df or "open" not in df:
            return None
        t = df["time"].astype("int64")
        r = df[(t % secs == 0) & (t <= now) & (t + secs > now)]
        if not len(r):
            return None
        o = float(r["open"].iloc[-1])
        return (int(r["time"].iloc[-1]), o) if o > 0 and math.isfinite(o) else None
    except Exception:
        return None


def next_wake(now: float, offsets=(2.0, 32.0)) -> float:
    """The next poll time after `now`: `offsets` seconds after each minute boundary (2 s after a bar closes, and a mid-minute
    poll). The old loop slept 60 s after each poll (not aligned to the minute, ~31 s late on average)."""
    m = math.floor(now / 60.0) * 60.0
    for base in (m, m + 60.0):
        for o in sorted(float(x) for x in offsets):
            if base + o > now + 0.05:
                return base + o
    return m + 120.0


class LiveBot:
    """Same Engine as the backtester, re-run on a rolling window every poll; decisions are a pure function of the bars.

    Pluggable for the dry-run harness: `clock()` (unix seconds), `read_hist(sym, tf)` (stored CSV as a frame) and
    `fetch_recent(sym, interval, period)` (fresh bars) are instance attributes that tests may replace."""

    def __init__(self):
        self.thread = None
        self.stop_flag = threading.Event()
        self.lock = threading.Lock()
        self._gen = 0
        self.clock = time.time
        self.read_hist = self._read_hist
        self.fetch_recent = self._fetch_recent
        self.state_path = STATE_PATH
        self.reset()

    def reset(self):
        self._guard_key = None
        self._eod_sent = None
        self.running = False
        self.cfg = {}
        self.log = deque(maxlen=400)
        self.ledger = []
        self.seen = set()
        self.state = None
        self.last_poll = None
        self.started_at = None
        self.errors = 0
        self.bars_tail = []
        self.kill = False
        self.adapter = None
        self.health = {"data_source": None, "data_age_s": None, "stale": False, "stale_polls": 0, "fallback": False,
                       "last_error": None, "last_error_t": None, "last_ok_poll": None, "consecutive_errors": 0,
                       "poll_ms": None, "entries_blocked": False, "desync": False, "revisions": 0, "dropped": {},
                       "market_open": None, "ok": True}
        self._last_bars = {}             # time -> (o,h,l,c) of the last closed bars seen (revision detector)
        self._open_routed = None         # entry_t of the entry we routed and still believe is open
        self._open_qty = None
        self._open_adds = []             # LIT scale_in: adds routed to the open position [{"entry_t", "n", "qty", "px", "t"}]
        self._blocked_entries = set()    # entry_t of engine entries we deliberately did not route
        self._flattened = set()          # entry_t of positions the clock-based safety flatten already closed
        self._no_entries_day = None      # trading day a remote "flatten" ended (engine/remote_ctl.py): no new entries that day
        self._restored = None
        self._nt_feed = None             # engine.ninjatrader.NinjaTraderBars for data_source "ninjatrader"
        self._nt_notes = {}              # rate limit for the ninjatrader feed notes: key -> (text, unix time logged)
        self._modify_gaveup = set()      # (entry_t, stop) the broker refused 3 times: not retried again
        self._week_prev = []             # LIT weekly stop: this ISO week's routed exits from earlier days (live_state.json)
        self._forming = {}               # (sym, secs) -> (open time, open) of the bar forming at the last fetch (LIT sizing)
        self._nt_forming = {}            # (sym, secs) -> the same from NinjaTrader's LE_BarFeed open file
        self._provisional = {}           # entry_t -> what was routed for a LIT entry decided on the 1m CISD close
        self._nt_repoll = None           # minute boundary already re-polled for a late NinjaTrader 1m bar
        self._eval_prev = {}             # LIT safe_eval / eval / two_week: routed P&L per earlier trading day of the eval (live_state.json)
        self._lit_sizing = None          # live_model.json lit_sizing (or the start cfg's), set on every poll
        self.no_yahoo = pcbars.no_yahoo()  # no Yahoo anywhere (engine/pcbars.py); start() reads the start cfg's "no_yahoo" too
        self._nt_last = {}               # (sym, tf) -> the last NinjaTrader frame (the heartbeat pushes it to the cloud)
        self._nt_forming_last = None     # (open time, open) of the forming 1m bar (heartbeat "bars" block)
        self._arc = {}                   # (sym, tf) -> the NinjaTrader archive in memory (data/nt_bars, engine/pcbars.py)
        self.accts = None                # engine/multi_account.AccountRouter: the start cfg's extra accounts (None = one account)
        self.brain = None                # engine/brain.py: the Bot Brain snapshot of the last poll (read-only, built after routing)
        self.second = None               # engine/second.py: the paper second strategies' last run (never routed)
        self._brain_log = None           # engine/brain.BrainLog: today's thought log (data/brain/YYYY-MM-DD.jsonl for the real bot)

    # ------------------------------------------------------------------ plumbing
    def _log(self, kind, text, **kw):
        self.log.appendleft({"t": int(self.clock()), "type": kind, "text": text, **kw})

    def _alert(self, text, kind):
        """alerts.send never raises by contract, but a bug there must never stop order routing."""
        try:
            from . import alerts
            return alerts.send(text, kind)
        except Exception as e:
            self._note_error(f"alert failed: {e}")
            return None

    def _note_error(self, text):
        self.health["last_error"] = text
        self.health["last_error_t"] = int(self.clock())
        self._log("error", text)

    def _read_hist(self, sym, tf):
        path = os.path.join(DATA_DIR, f"{sym}_{tf}.csv")
        if not os.path.exists(path):
            df = pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
        else:
            st_ = os.stat(path)
            hit = getattr(self, "_hist_cache", {}).get(path)
            if hit and hit[0] == (st_.st_mtime_ns, st_.st_size):
                df = hit[1]                              # the export only changes when the owner refreshes it
            else:
                df = pd.read_csv(path)
                # same hygiene as engine.data.load(): weekend/maintenance junk bars never reach the live engine either
                df = df[~((df["high"] == df["low"]) & (df["volume"] <= 0))]
                if self.no_yahoo:
                    df = pcbars.tidy(df)
                    self._hist_cache = {**getattr(self, "_hist_cache", {}), path: ((st_.st_mtime_ns, st_.st_size), df)}
        if self.no_yahoo and tf in ("1m", "5m"):
            # TradingView export + the bot's own NinjaTrader archive (bridges the export's end once LE_BarFeed's 30 days move on)
            arc = self._archive(sym, tf)
            if len(arc):
                df, sh = pcbars.merge_basis(df, arc)
                if sh:
                    self._nt_note(f"basis:{sym}:{tf}", "warn", f"{sym} {tf}: the TradingView history sits {-sh:+.2f} pts from "
                                  "NinjaTrader's bars (a contract roll): history back-adjusted onto NinjaTrader's contract", every_s=86400)
        return df

    def _arc_root(self):
        """Where the NinjaTrader archive lives: cfg "nt_archive", else data/nt_bars for the real bot only (test harnesses
        run with their own state_path and never write into data/)."""
        return self.cfg.get("nt_archive") or (pcbars.ARCHIVE_DIR if self.state_path == STATE_PATH else None)

    def _archive(self, sym, tf):
        """The NinjaTrader archive (data/nt_bars/<sym>_<tf>.csv) in memory; read from disk once per bot start."""
        root = self._arc_root()
        if root is None:
            return pcbars.tidy(None)
        if (sym, tf) not in self._arc:
            self._arc[(sym, tf)] = pcbars.archive_read(sym, tf, root)
        return self._arc[(sym, tf)]

    def _archive_add(self, sym, tf, df):
        if tf not in ("1m", "5m") or df is None or not len(df) or self._arc_root() is None:
            return
        secs = TF_SECONDS[tf]
        closed = df[df["time"] + secs <= int(self.clock())]
        old = self._archive(sym, tf)
        if len(old) and len(closed) and int(closed["time"].max()) <= int(old["time"].max()):
            return                                       # nothing new since the last poll
        r = pcbars.archive_add(sym, tf, closed, root=self._arc_root(), now=int(self.clock()), prev=old)
        if r.get("error"):
            self._nt_note(f"archive:{sym}:{tf}", "warn", f"NinjaTrader archive {sym} {tf} not written: {r['error']}", every_s=3600)
            return
        if r.get("rewritten") or r.get("shift"):
            self._arc.pop((sym, tf), None)               # re-read the rewritten file next time
        else:
            new = closed[closed["time"] > (int(old["time"].max()) if len(old) else -1)]
            self._arc[(sym, tf)] = pcbars.tidy(pd.concat([old, new])) if len(new) else old

    def _fetch_recent(self, sym, interval, period="5d"):
        """Fresh bars from the configured data_source; tradovate falls back to yahoo (logged once per poll).
        no_yahoo on: NinjaTrader (or Tradovate) only; None when it has no usable bars (never Yahoo)."""
        src = self.cfg.get("data_source", "yahoo")
        if self.no_yahoo:
            if src == "tradovate":
                try:
                    from . import tradovate as _tv
                    df = _tv.TradovateData().recent_bars(sym, interval, period)
                    if df is not None and len(df):
                        return df
                    why = "returned no bars"
                except Exception as e:
                    why = f"{e.__class__.__name__}: {e}"
                if sym == self.cfg.get("sym", "NQ"):
                    self.health["nt_down" if interval != "1m" else "nt_down_1m"] = f"Tradovate feed {why}"
                return None
            return self._ninjatrader_recent(sym, interval, period)
        if src == "ninjatrader":
            df = self._ninjatrader_recent(sym, interval, period)
            if df is not None:
                return df
        if src == "tradovate":
            try:
                from . import tradovate as _tv
                df = _tv.TradovateData().recent_bars(sym, interval, period)
                if df is not None and len(df):
                    return df
                reason = "returned no bars"
            except Exception as e:
                reason = f"{e.__class__.__name__}: {e}"
            if not self.health.get("fallback"):
                self._log("warn", f"data_source=tradovate {reason} - falling back to Yahoo for this poll")
            self.health["fallback"] = True
        return _yahoo_recent(sym, interval=interval, period=period)

    def _nt_note(self, key, kind, text, every_s=900):
        """Log a ninjatrader feed note when it changes, and at most every 15 min while it stays the same."""
        prev = self._nt_notes.get(key)
        now = int(self.clock())
        if prev is None or prev[0] != text or now - prev[1] >= every_s:
            self._nt_notes[key] = (text, now)
            self._log(kind, text)

    def _ninjatrader_recent(self, sym, interval, period):
        """Real CME bars NinjaTrader writes (ninjatrader/LE_BarFeed.cs -> Documents\\NinjaTrader 8\\le_feed). None = use
        Yahoo for this fetch (logged; health.fallback for the bot's own symbol). When the feed holds fewer days than the
        gap to the stored history, or has holes, Yahoo fills in underneath and NinjaTrader's bars win wherever both exist."""
        primary = sym == self.cfg.get("sym", "NQ")
        try:
            from . import ninjatrader as _nt
            if self._nt_feed is None:
                self._nt_feed = _nt.NinjaTraderBars(folder=self.cfg.get("nt_folder"), roots=self.cfg.get("nt_feed_roots"))
            df, why, full = self._nt_feed.recent_bars(sym, interval, period, now=int(self.clock()))
            if interval == "1m" and df is not None and callable(getattr(self._nt_feed, "forming_open", None)):
                self._nt_forming[(sym, 60)] = self._nt_feed.forming_open(sym, now=int(self.clock()))
                if primary:
                    self._nt_forming_last = self._nt_forming[(sym, 60)]
        except Exception as e:
            df, why, full = None, f"{e.__class__.__name__}: {e}", False
        if self.no_yahoo:
            # NinjaTrader only: its bars (kept in the archive, pushed to the cloud), or None + the reason (entries blocked)
            if df is not None and len(df):
                if interval in ("1m", "5m"):
                    self._nt_last[(sym, interval)] = df
                    self._archive_add(sym, interval, df)
                if not full:
                    self._nt_note(f"fill:{sym}:{interval}", "system",
                                  f"data_source=ninjatrader {sym} {interval}: {why} - no Yahoo (no_yahoo): the TradingView "
                                  "history + the NinjaTrader archive cover the rest", every_s=3600)
                return df
            if primary:
                self.health["nt_down" if interval != "1m" else "nt_down_1m"] = why
                self._nt_note(f"down:{sym}:{interval}", "warn",
                              f"FEED STALE: NinjaTrader {sym} {interval}: {why} - no Yahoo fallback (no_yahoo): new entries blocked "
                              "until NinjaTrader's bars are fresh again (an open trade keeps its brackets at the broker)", every_s=300)
            else:
                self._nt_note(f"partner:{sym}", "system", f"data_source=ninjatrader: no {sym} {interval} bars ({why}); no Yahoo "
                              "(no_yahoo): features that need them are unknown", every_s=3600)
            return None
        if df is not None and len(df):
            if full:
                return df
            self._nt_note(f"fill:{sym}:{interval}", "warn" if primary else "system",
                          f"data_source=ninjatrader {sym} {interval}: {why} - Yahoo fills the gaps, NinjaTrader bars win")
            try:
                y = _yahoo_recent(sym, interval=interval, period=period)
            except Exception as e:
                self._note_error(f"Yahoo gap fill failed ({sym} {interval}): {e.__class__.__name__}: {e}")
                y = None
            if y is None or not len(y):
                return df
            return pd.concat([y, df]).drop_duplicates("time", keep="last").sort_values("time").reset_index(drop=True)
        if primary:
            if not self.health.get("fallback"):
                self._nt_note(f"fallback:{sym}", "warn", f"data_source=ninjatrader {why} - falling back to Yahoo for this poll",
                              every_s=300)
            self.health["fallback"] = True
        else:
            self._nt_note(f"partner:{sym}", "system", f"data_source=ninjatrader: {sym} {interval} bars from Yahoo ({why})",
                          every_s=3600)
        return None

    def _merged(self, sym, tf, now, secs, period="5d", max_days=58):
        """Stored history + fresh bars, cleaned. A failing fresh fetch degrades to history (never raises for that)."""
        hist = self.read_hist(sym, tf)
        period = _cover_gap(hist, now, period, max_days=max_days)   # stored history ends days ago: fetch enough to bridge it
        try:
            recent = self.fetch_recent(sym, tf, period)
            if recent is None:
                recent = pd.DataFrame()
            self.health["fetch_ok"] = True
        except Exception as e:
            recent = pd.DataFrame()
            self.health["fetch_ok"] = False
            self._note_error(f"data refresh failed ({sym} {tf}): {e.__class__.__name__}: {e}")
        if self.no_yahoo:
            # back-adjust the history onto the feed's contract when they sit a constant offset apart (a roll), and note a
            # hole between the history's end and the feed's first bar (TradingView export end vs NinjaTrader's 30 days)
            if sym == self.cfg.get("sym", "NQ") and tf in ("1m", "5m"):
                gap = pcbars.hist_gap(hist, recent, secs)
                key = f"gap:{sym}:{tf}"
                self.health.setdefault("hist_gap", {})[tf] = None if gap is None else \
                    {"from": int(gap[0]), "to": int(gap[1]), "bars": int(gap[2])}
                if gap is not None:
                    self._nt_note(key, "warn", f"{sym} {tf}: {gap[2]} bars missing between the stored history "
                                  f"({_et(gap[0]):%m-%d %H:%M} ET) and the NinjaTrader feed ({_et(gap[1]):%m-%d %H:%M} ET): "
                                  "load more days on the NinjaTrader chart, or refresh the TradingView export", every_s=6 * 3600)
            df, sh = pcbars.merge_basis(hist, recent)
            if sh:
                self._nt_note(f"basis:{sym}:{tf}:feed", "warn", f"{sym} {tf}: the stored history sits {-sh:+.2f} pts from the "
                              "feed's contract (a roll): back-adjusted onto the feed's prices", every_s=86400)
        else:
            frames = [f for f in (hist, recent) if f is not None and len(f)]
            df = pd.concat(frames) if frames else pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
        self._forming[(sym, secs)] = self._nt_forming.pop((sym, secs), None) or forming_open(recent, secs, now)
        return clean_bars(df, secs, now)

    # ------------------------------------------------------------------ lifecycle
    def start(self, cfg: dict, spawn: bool = True):
        """spawn=False (harness / tests): configure, restore state and arm routing, but do not start the poll thread."""
        if self.running:
            return {"ok": False, "error": "already running"}
        old = self.thread
        self._gen += 1                                  # any older loop thread retires after its current poll
        self.stop_flag.set()
        if old is not None and old.is_alive() and old is not threading.current_thread():
            old.join(timeout=3)
        self.reset()
        self.cfg = {**LIVE_DEFAULTS, **cfg}
        if cfg.get("data") and "data_source" not in cfg:
            self.cfg["data_source"] = cfg["data"]          # {"data": "ninjatrader"} is accepted as a short form
        self.no_yahoo = pcbars.no_yahoo(cfg)
        if self.no_yahoo and self.cfg.get("data_source", "yahoo") == "yahoo":
            self.cfg["data_source"] = "ninjatrader"          # no Yahoo (owner 2026-10-19): NinjaTrader's bars are the feed
        if self.cfg["adapter"] != "paper" and not self.cfg.get("armed"):
            return {"ok": False, "error": "non-paper adapters must be explicitly armed (armed=true)"}
        if self.cfg["adapter"] not in ADAPTERS:
            return {"ok": False, "error": f"unknown adapter {self.cfg['adapter']}"}
        self.adapter = ADAPTERS[self.cfg["adapter"]](self.cfg)
        self.started_at = int(self.clock())
        self.health["data_source"] = self.cfg.get("data_source", "yahoo")
        self.health["no_yahoo"] = self.no_yahoo
        self._restore(clear_kill=bool(cfg.get("clear_kill")))
        self._start_accounts()
        self.running = True
        self.stop_flag.clear()
        if spawn:
            self.thread = threading.Thread(target=self._loop, args=(self._gen,), daemon=True)
            self.thread.start()
        self._log("system", f"Bot started | {self.cfg['sym']} {self.cfg['tf']} | adapter={self.cfg['adapter']} | "
                            f"data={self.cfg['data_source']}{' (no Yahoo)' if self.no_yahoo else ''} | window={self.cfg['window_days']}d")
        if self.kill:
            self._log("risk", "KILL flag restored from a previous run today: no orders will be routed. "
                              "Start again with clear_kill=true (or delete data/live_state.json) to re-arm.")
        self._save_state()
        return {"ok": True, "restored": self._restored}

    def stop(self):
        self.stop_flag.set()
        self._gen += 1
        self.running = False
        self._log("system", "Bot stopped")
        self._save_state()
        return {"ok": True}

    def kill_switch(self):
        """Flatten + stop. On paper this closes the simulated position. The flag persists for the rest of the day."""
        self.kill = True
        if self.state and self.state.get("position"):
            pos = self.state["position"]
            qty = self._open_qty if self._open_routed == pos.get("entry_t") and self._open_qty else pos.get("qty")
            q1 = int(qty or 0)
            qty = q1 + self._adds_qty(pos.get("entry_t"))
            # book the flatten's P&L (marked at the market now) like every other exit: without it the kill exit counted
            # $0 in day_pnl_routed / eval_days, so the eval clock, the next trade's two_week size and the soft daily
            # loss all saw a loss that never happened as flat
            pnl = self._kill_pnl(pos, q1)
            self._route({"sym": self.cfg.get("sym", "NQ"), "side": "exit", "qty": qty, "reason": "KILL SWITCH",
                         "entry_t": pos.get("entry_t"), "exit_t": int(self.clock()),
                         **({"pnl": pnl, "pnl_est": True} if pnl is not None else {})})
            self._flattened.add(pos.get("entry_t"))
            self._open_routed = None
        elif getattr(self.adapter, "kill_flattens_all", False):
            # broker adapters that can flatten the whole account (NinjaTrader FLATTENEVERYTHING) are told even when the
            # model shows no position: the broker may still hold one (desync, manual order, late fill)
            self._route({"sym": self.cfg.get("sym", "NQ"), "side": "exit", "reason": "KILL SWITCH", "entry_t": None})
        if self.accts is not None:                  # every extra account is flattened too (engine/multi_account.py)
            self.accts.kill(self.cfg.get("sym", "NQ"))
        self.stop()
        self._log("risk", "KILL SWITCH: flattened and stopped")
        self._save_state()
        return {"ok": True}

    def flatten_now(self, reason: str = "REMOTE FLATTEN"):
        """Close the open position now and keep the bot running (engine/remote_ctl.py "flatten"). No kill flag; no new
        entries for the rest of this trading day (the bot trades again on the next one); the model's own later exit of this
        entry is not sent again (_flattened). With no model position but an order of ours still working at the broker (a
        pending entry, a desync), that order / position is closed too. Extra accounts are flattened as well."""
        sym = (self.cfg or {}).get("sym", "NQ")
        self._no_entries_day = trading_day(self.clock())
        pos = (self.state or {}).get("position")
        res = {"ok": True, "note": "flat: nothing to close"}
        legs = [lg for lg in (getattr(self.adapter, "legs", None) or []) if isinstance(lg, dict)
                and lg.get("status") in ("entry_sent", "pending", "cancel_pending", "protected", "unprotected")]
        if pos:
            qty = self._open_qty if self._open_routed == pos.get("entry_t") and self._open_qty else pos.get("qty")
            qty = int(qty or 0) + self._adds_qty(pos.get("entry_t"))
            res = self._route({"sym": sym, "side": "exit", "qty": qty, "reason": reason, "entry_t": pos.get("entry_t")})
            self._flattened.add(pos.get("entry_t"))
            self._open_routed = None
        elif self._open_routed is not None or legs:
            res = self._route({"sym": sym, "side": "exit", "qty": self._open_qty, "reason": reason, "entry_t": self._open_routed})
            if self._open_routed is not None:
                self._flattened.add(self._open_routed)
            self._open_routed = None
        extras = []
        if self.accts is not None:                  # the extra accounts (engine/multi_account.py), without their kill flag
            for acc in list(getattr(self.accts, "accounts", None) or []):
                if getattr(acc, "adapter", None) is not None and getattr(acc, "open_t", None) is not None:
                    r = acc.kill(sym)
                    extras.append({"id": acc.id, "ok": bool(r.get("ok")), "error": r.get("error")})
            try:
                self.accts.save()
            except Exception:
                pass
        self._log("risk", f"{reason}: " + ("position closed" if pos else "no open position") +
                  "; the bot keeps running, no new entries until the next trading day")
        self._save_state()
        return {"ok": bool(res.get("ok")), "had_position": bool(pos), "result": res, "extras": extras}

    def _kill_mark_px(self, pos):
        """The market at the kill: the forming 1m bar's open (NinjaTrader LE_BarFeed), else the model's last close."""
        sym = self.cfg.get("sym", "NQ")
        try:
            fo = self._nt_feed.forming_open(sym, now=int(self.clock())) if self._nt_feed is not None else None
            if fo:
                return float(fo[1])
        except Exception:
            pass
        px = (self.state or {}).get("price")
        if px:
            return float(px)
        q, u = pos.get("qty"), pos.get("unrealized")
        if q and u is not None and pos.get("entry") is not None:
            from . import lit as _lit
            d = 1 if pos.get("dir", 1) == 1 else -1
            return float(pos["entry"]) + d * (float(u) / float(q) + _lit.COMM) / _lit.PV
        return None

    def _kill_pnl(self, pos, qty):
        """$ of the kill-switch flatten at the routed size (first entry + every routed add), at the market now, costs in."""
        try:
            from . import lit as _lit
            px = self._kill_mark_px(pos)
            if px is None or pos.get("entry") is None or not qty:
                return None
            d = 1 if pos.get("dir", 1) == 1 else -1
            pnl = int(qty) * (d * (px - float(pos["entry"])) * _lit.PV - _lit.COMM)
            self._sync_adds(pos.get("entry_t"))
            for a in self._open_adds:
                if a.get("entry_t") == pos.get("entry_t"):
                    pnl += int(a["qty"]) * (d * (px - float(a["px"])) * _lit.PV - _lit.COMM)
            return round(pnl, 2)
        except Exception as e:
            self._note_error(f"kill switch P&L not booked: {e.__class__.__name__}: {e}")
            return None

    def _route(self, action):
        if self.adapter is None:
            self.adapter = ADAPTERS["paper"](self.cfg)
        hedge = self.accts.opposite_open(1 if action.get("side") == "buy" else -1) \
            if self.accts is not None and action.get("side") in ("buy", "sell") else None
        try:
            # extra accounts: never long on one account and short on another (engine/multi_account.opposite_open)
            res = {"ok": False, "error": "REFUSED: " + hedge} if hedge else self.adapter.send(action)
        except Exception as e:  # never let a broker error kill the loop
            res = {"ok": False, "error": str(e)}
            self._note_error(f"adapter {getattr(self.adapter, 'name', '?')} send failed: {e}")
        self.ledger.append({"t": int(self.clock()), **action, "result": res})
        self._log("order", f"{action['side'].upper()} {action.get('qty', '')} {action['sym']} -> {res.get('ok')}", result=res)
        self._save_state()
        return res

    def _adapter_tick(self):
        """Adapters that manage broker orders between bars (NinjaTrader: late fill reports, bracket health, flat-time
        safety) get one tick() per poll, before the data fetch so a failing feed cannot skip it. Never raises."""
        ad = self.adapter
        if self.accts is not None and not self.kill:
            self.accts.tick()                       # the extra accounts' adapters (never raises)
        if self.kill or not getattr(ad, "loop_tick", False) or not callable(getattr(ad, "tick", None)):
            return
        try:
            ad.tick()
        except Exception as e:
            self._note_error(f"adapter {getattr(ad, 'name', '?')} tick failed: {e.__class__.__name__}: {e}")

    def _broker_stop(self, entry_t):
        """The stop the broker was last given for this entry: its bracket, then every modify it accepted."""
        stop = None
        for r in self.ledger:
            if r.get("entry_t") != entry_t:
                continue
            if r.get("side") in ("buy", "sell"):
                stop = r.get("stop")
            elif r.get("side") == "modify" and (r.get("result") or {}).get("ok"):
                stop = r.get("stop")
        return stop

    def _route_stop_move(self, pos, sym):
        """The model moved the stop of the routed position (breakeven at 1R): tell the broker once per new level. A refused
        modify is retried on the next polls, at most 3 times per level. Stops are only ever tightened."""
        et_, new = pos.get("entry_t"), tick_px(pos.get("stop"), 1 if pos.get("dir", 1) == 1 else -1)
        last = self._broker_stop(et_)
        if new is None or last is None or abs(float(new) - float(last)) < 1e-9:
            return
        d = 1 if pos.get("dir", 1) == 1 else -1
        if (float(new) - float(last)) * d < 0:
            return
        if (et_, new) in self._modify_gaveup:
            return
        ready = getattr(self.adapter, "has_open_bracket", None)
        if callable(ready) and not ready(et_):
            return          # nothing at the broker to move yet (entry refused, or its stop not placed yet): next poll
        tries = sum(1 for r in self.ledger if r.get("entry_t") == et_ and r.get("side") == "modify" and r.get("stop") == new)
        if tries >= 3:
            self._modify_gaveup.add((et_, new))
            self._log("risk", f"Broker refused the stop move to {new:.2f} three times: the broker stop stays at {last:.2f}. "
                              "Check the stop in the broker platform by hand.")
            return
        reason = "BE" if (float(new) - float(pos.get("entry") or new)) * d >= 0 else "STOP MOVE"
        self._route({"sym": sym, "side": "modify", "qty": self._open_qty or pos.get("qty"), "stop": new, "reason": reason,
                     "entry_t": et_})

    # ------------------------------------------------------------------ LIT scale-in (engine/lit.py "scale_in", default off)
    def _adds_qty(self, entry_t) -> int:
        """Micros of the scale-in adds routed to the position of entry_t (0 without adds), from the broker's real fills."""
        self._sync_adds(entry_t)
        return sum(int(a.get("qty") or 0) for a in self._open_adds if a.get("entry_t") == entry_t)

    def _routed_pnl(self, tr, qty):
        """$ P&L of a finished trade at the routed size: the first entry's qty, plus every scale-in add routed to it at its
        own price (the model's add qty may differ from the routed one: the eval caps size the routed adds)."""
        self._sync_adds(tr["entry_t"])
        adds = [a for a in self._open_adds if a.get("entry_t") == tr["entry_t"]]
        if not tr.get("adds") and not adds:
            return round(tr["pnl"] * qty / tr["qty"], 2) if tr["qty"] else tr["pnl"]
        from . import lit as _lit
        d = 1 if tr.get("dir", 1) == 1 else -1
        xp = float(tr["exit_price"])
        pts = float(tr["pts"]) if tr.get("pts") is not None else d * (xp - float(tr["entry"]))
        pnl = qty * (pts * _lit.PV - _lit.COMM)
        for a in adds:                     # a["px"]: the broker's fill when reported (_sync_adds), else the model's price
            pnl += int(a["qty"]) * (d * (xp - float(a["px"])) * _lit.PV - _lit.COMM)
        return round(pnl, 2)

    def _add_qty(self, pos, an) -> int:
        """Micros for a scale-in add, as the backtest sizes it.
        Normal mode (the LIT rule, no eval caps): the model's add (engine/lit.py simulate_x + scale_trade, i.e. what run_x
        books) at the routed size: int(model add x routed micros / model micros), = the model's add when the bot routes the
        model's size. Eval modes (two_week / eval / safe_eval, as the research eval path tools/lit_big_ideas.py sizes them):
        engine/sizing.scale_in_qty at the ROUTED size: the add's open risk inside the first entry's $ risk, 60% of the room
        to the trailing floor and the $1,000 soft daily loss left today. The whole position at most max_micros.
        Fails closed (0) in an eval mode."""
        from . import sizing as _sz
        lsz = getattr(self, "_lit_sizing", None) or {}
        mode = str(lsz.get("mode") or "")
        try:
            si = ((self.state or {}).get("strategy") or {}).get("params", {}).get("scale_in") or {}
            q0 = int(self._open_qty or pos.get("qty") or 0)
            maxq = min(40, int((self.cfg.get("params") or {}).get("max_micros") or 40))
            if mode not in ("two_week", "eval", "safe_eval", "funded"):
                qm = int(pos.get("qty") or 0)
                n = int(int(an.get("qty") or 0) * q0 / qm + 1e-9) if qm else 0
                return max(0, min(n, maxq - q0 - self._adds_qty(pos.get("entry_t"))))
            state = None
            if mode in ("two_week", "eval", "safe_eval"):
                st = self.eval_state() or {}
                if st and lsz.get("pass_lock") is not False and float(st.get("profit") or 0) + float(st.get("cum") or 0) \
                        >= float(((lsz.get("two_week") or {}).get("acct") or {}).get("target", _sz.TW_50K["target"])):
                    return 0                      # a passed eval (the 1-micro minimum-days trade): never add to it
                state = {"room": self.eval_room(), "cum": float(st.get("cum", self.day_pnl_routed()) or 0.0)}
            prev = [{"rk": float(a["rk"]), "prev_rk": list(a.get("prev_rk") or [])} for a in (pos.get("adds") or [])][:int(an["n"]) - 1]
            qa = _sz.scale_in_qty(q0, q0, float(pos["risk_pts"]), prev + [{"rk": float(an["rk"]), "prev_rk": list(an.get("prev_rk") or [])}],
                                  f=si.get("f", an.get("f", 1.0)), state=state, max_micros=maxq)
            return int(qa[-1])
        except Exception as e:
            self._note_error(f"scale-in sizing failed ({mode or 'normal'}): {e.__class__.__name__}: {e}")
            return 0

    def _route_add(self, pos, sym):
        """LIT scale_in: the model decided an add on the close of its 1m CISD candle (position "add_now"): route it at market
        at once, exactly once (the backtest fills it at the next 1m open + 1 tick). The stop and target then cover the whole
        position (NinjaTrader: the bracket's quantity grows, engine/ninjatrader.py add_to_position). An add the model filled
        before this process saw its decision is never chased."""
        et_ = pos.get("entry_t")
        for i, a in enumerate(pos.get("adds") or []):
            key = ("add", et_, i + 1)
            if key not in self.seen:
                self.seen.add(key)
                self._log("risk", f"Scale-in add {i + 1} at {_et(int(a['t'])):%H:%M} ET NOT routed: seen after its fill bar - not chasing")
        routed_n = {int(a["n"]) for a in self._open_adds if a.get("entry_t") == et_}
        if len(pos.get("adds") or []) < max(routed_n or {0}) and not pos.get("add_now") and not getattr(self, "_add_warned", None) == et_:
            self._add_warned = et_
            self._log("warn", f"Scale-in: an add was routed for the {_et(et_):%H:%M} ET entry but the model's trade has none once its "
                              "fill bar closed (priced from an estimate); the broker keeps it under the same stop/target")
        an = pos.get("add_now")
        if not an:
            return
        key = ("add", et_, int(an["n"]))
        if key in self.seen:
            return
        self.seen.add(key)
        self._save_state()          # marked done BEFORE the broker call: a crash / restart mid-call never sends this add again
        if not (self.cfg.get("adapter") == "paper" or getattr(self.adapter, "route_adds", False)):
            self._log("risk", f"Scale-in add NOT routed: adapter {self.cfg.get('adapter')} cannot add to a position")
            return
        if self.health.get("entries_blocked"):
            self._log("risk", f"Scale-in add at {_et(int(an['t'])):%H:%M} ET NOT routed: feed stale")
            return
        age = int(self.clock()) - int(an["t"])
        max_age = float(self.cfg.get("add_max_age_s", 20))
        if age > max_age:            # the backtest fills the add at the open of the bar after its CISD candle: never chase it
            self._log("risk", f"Scale-in add at {_et(int(an['t'])):%H:%M} ET NOT routed: seen {age} s after its 1m CISD candle "
                              f"closed (limit {max_age:.0f} s) - not chasing")
            return
        d = 1 if pos.get("dir", 1) == 1 else -1
        if getattr(self.adapter, "route_stop_moves", False):
            # the add is sized at the breakeven risk: the broker's stop must be at the model's (breakeven incl. be_off) stop
            want, have = tick_px(pos.get("stop"), d), self._broker_stop(et_)
            if have is None or want is None or abs(float(have) - float(want)) > 1e-9:
                msg = (f"Scale-in add at {_et(int(an['t'])):%H:%M} ET NOT routed: the broker stop is "
                       f"{'unknown' if have is None else f'{float(have):.2f}'}, the add was sized at the breakeven stop "
                       f"{'?' if want is None else f'{float(want):.2f}'} (stop move refused or not sent yet)")
                self._log("risk", msg)
                try:
                    from . import push
                    self._push_send(push.text_payload("PC", "risk", "Scale-in add skipped", msg, key=f"addbe:{et_}:{int(an['n'])}"))
                except Exception:
                    pass
                return
        q = self._add_qty(pos, an)
        if q < 1:
            self._log("risk", f"Scale-in add at {_et(int(an['t'])):%H:%M} ET skipped: 0 micros inside the risk budget / eval caps")
            return
        self._log("system", f"LIT scale-in: CISD closed at {_et(int(an['cisd_t'])):%H:%M} ET, MARKET add of {q} sent at once "
                            f"({int(self.clock()) - int(an['t'])} s after the close)" + ("; priced from the CISD close" if an.get("est") else ""))
        rr = self._route({"sym": sym, "side": "add", "qty": q, "dir": d, "stop": tick_px(pos.get("stop"), d),
                          "target": tick_px(pos.get("target"), d, target=True), "entry": an["px"], "entry_t": et_,
                          "n": int(an["n"]), "add_t": int(an["t"])})
        if rr.get("ok") or rr.get("pending") or (rr.get("add_id") and int(rr.get("filled") or 0) > 0):
            # the broker's real fill when it reported one (qty, price); a pending / partial add is corrected from the
            # adapter's fills later (_sync_adds: late fill, cancel after 45 s, partial)
            fq = int(rr.get("filled") or 0)
            self._open_adds.append({"entry_t": et_, "n": int(an["n"]), "qty": fq if fq > 0 else q,
                                    "px": float(rr["fill_px"]) if fq > 0 and rr.get("fill_px") else float(an["px"]),
                                    "t": int(an["t"]), "est": bool(an.get("est")), "asked": q,
                                    "real": fq > 0 and bool(rr.get("fill_px"))})
            self._save_state()

    def _sync_adds(self, entry_t):
        """The adds of entry_t from the adapter's real fills (NinjaTrader add_fills): a late fill, a partial fill, an add
        cancelled unfilled after 45 s (-> 0 micros). Paper / adapters without fill reports: unchanged. Never raises."""
        fn = getattr(self.adapter, "add_fills", None)
        if not callable(fn):
            return
        try:
            real = {int(a["n"]): a for a in fn(entry_t) or []}
        except Exception as e:
            self._note_error(f"scale-in fills not read: {e.__class__.__name__}: {e}")
            return
        changed = False
        known = {int(a.get("n") or 0) for a in self._open_adds if a.get("entry_t") == entry_t}
        for n, r in sorted(real.items()):
            # an add the broker has but this ledger lost (a crash between the adapter's order file and LiveBot's save):
            # booked from the broker's real fill, never at a guessed size
            if n not in known and int(r.get("filled") or 0) > 0 and r.get("fill_px"):
                self._open_adds.append({"entry_t": entry_t, "n": n, "qty": int(r["filled"]), "px": float(r["fill_px"]),
                                        "t": None, "est": False, "asked": int(r.get("qty") or 0), "real": True,
                                        "restored": True})
                self._log("risk", f"Scale-in add {n} for the {_et(int(entry_t)):%H:%M} ET entry found in NinjaTrader's fills "
                                  f"({int(r['filled'])} @ {float(r['fill_px']):.2f}) but not in the ledger: booked from the fill")
                changed = True
        for a in self._open_adds:
            if a.get("entry_t") != entry_t or int(a.get("n") or 0) not in real:
                continue
            r = real[int(a["n"])]
            if int(r.get("filled") or 0) > 0 and r.get("fill_px"):
                new = {"qty": int(r["filled"]), "px": float(r["fill_px"]), "real": True}
            elif r.get("status") in ("rejected", "cancelled"):
                new = {"qty": 0, "real": True}
            else:
                continue                                  # still working: keep the asked size until the broker says more
            if any(a.get(k) != v for k, v in new.items()):
                a.update(new)
                changed = True
        if changed:
            self._save_state()

    def _learn_es(self, sym, tf, now, secs):
        """ES 5m bars for the learning loop's ES features, fetched at most every 5 minutes; None when unavailable."""
        if self.state_path != STATE_PATH:      # test harnesses: no extra feed (the ES features are then unknown)
            return None
        c = getattr(self, "_es_cache", None)
        if c and now - c[0] < 300:
            return c[1]
        es = None
        if PARTNER.get(sym) in YAHOO:
            keep = dict(self.health)
            try:
                es, _ = self._merged(PARTNER[sym], tf, now, secs)
            except Exception as e:
                self._note_error(f"partner {PARTNER.get(sym)} unavailable (learning features): {e}")
            self.health.clear(); self.health.update(keep)
            if self.no_yahoo and es is not None and (not len(es) or (market_open(now) and int(es["time"].max()) + 1800 < now)):
                es = None                      # no fresh ES without Yahoo (no MES chart in NinjaTrader): features unknown, not stale
        self._es_cache = (now, es)
        return es

    def _journal(self, tr, qty):
        """The LIT learning loop's journal (engine/lit_learn.py): one record per routed LIT exit, source "pc", with the
        routed micros and $ (the real bot only; test harnesses run with their own state_path). Never raises into routing."""
        if self.state_path != STATE_PATH or (self.state or {}).get("model") != "lit":
            return
        try:
            from . import lit_learn
            lr = tr.get("learn") or {}
            pnl = round(tr["pnl"] * qty / tr["qty"], 2) if tr.get("qty") else tr["pnl"]
            rec = lit_learn.record(tr, "pc", f=lr.get("f"), post=tr.get("post"), qty=qty, pnl=pnl,
                                   learn=getattr(self, "_learn_at", {}).get(tr["entry_t"]))
            if lit_learn.append_journal([rec]):
                self._log("system", f"Learning journal: {rec['exit']} {rec['r']:+.2f}R"
                                    + (f", cause {rec['cause']}" if rec.get("cause") else ""))
        except Exception as e:
            self._note_error(f"learning journal failed: {e}")

    def _remember(self, tr, sym, note=None):
        """Persistent trade memory (engine/memory.py): store a completed routed trade. Never raises into routing.
        Source: 'live' only for a real-money adapter (Tradovate env=live, TradersPost); paper and demo are 'paper'."""
        try:
            from .memory import MEMORY
            name = str(self.cfg.get("adapter") or "paper")
            env = getattr(self.adapter, "env", None)
            if name == "paper":
                source = "paper"
            elif env is not None:            # Tradovate adapters know their own environment
                source = "live" if env == "live" else "paper"
            else:                            # TradersPost webhook: a real broker account
                source = "live"
            row = dict(tr, **({"memory_note": note} if note else {}))
            tid, new = MEMORY.record_trade(row, source, sym, self.cfg.get("tf"), getattr(self, "_params", None) or self.cfg.get("params"))
            if new:
                self._log("system", f"Memory: stored {source} trade #{tid} ({tr.get('exit_reason')} {float(tr.get('pnl_r') or 0):+.2f}R)")
        except Exception as e:
            self._note_error(f"memory record failed: {e}")

    # ------------------------------------------------------------------ persistence (restart safety)
    def _state_blob(self):
        return {"version": STATE_VERSION, "saved_at": int(self.clock()), "day": trading_day(self.clock()),
                "sym": self.cfg.get("sym"), "tf": self.cfg.get("tf"), "adapter": self.cfg.get("adapter"),
                "started_at": self.started_at, "kill": self.kill, "eod_sent": self._eod_sent, "guard_key": self._guard_key,
                "open_routed": self._open_routed, "open_qty": self._open_qty, "open_adds": self._open_adds,
                "blocked_entries": sorted(self._blocked_entries),
                "flattened": sorted(self._flattened), "no_entries_day": self._no_entries_day, "provisional": {str(k): v for k, v in self._provisional.items()},
                "seen": [list(k) for k in list(self.seen)[-2000:]], "ledger": self.ledger[-300:],
                "week_exits": self.lit_week_hist() if self.cfg else [], "eval_days": self.eval_days() if self.cfg else {},
                "day_pnl_routed": self.day_pnl_routed(), "trades_today": self.trades_today()}

    def _save_state(self):
        if not self.cfg:
            return
        try:
            os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
            tmp = self.state_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._state_blob(), f, default=_jsonable)
            os.replace(tmp, self.state_path)
        except Exception as e:
            self.health["last_error"] = f"state save failed: {e}"

    def _restore(self, clear_kill=False):
        """Pick up today's ledger / kill flag / alert de-dup keys after a server restart. Older files are ignored."""
        if not os.path.exists(self.state_path):
            return
        try:
            with open(self.state_path, encoding="utf-8") as f:
                s = json.load(f)
        except Exception as e:
            self._log("warn", f"live_state.json unreadable ({e}) - starting clean")
            return
        today = trading_day(self.clock())
        if s.get("sym") == self.cfg.get("sym"):
            # kept across days: the LIT weekly stop needs this week's earlier stop-outs, safe_eval the eval's daily P&L
            from .lit import iso_week
            wk = iso_week(today)
            self._week_prev = [r for r in (s.get("week_exits") or []) if r.get("day") and r["day"] != today and iso_week(r["day"]) == wk]
            self._eval_prev = {d: float(v) for d, v in (s.get("eval_days") or {}).items() if d != today}
        if s.get("day") != today or s.get("sym") != self.cfg.get("sym") or s.get("tf") != self.cfg.get("tf"):
            self._log("system", f"Ignoring live_state.json from {s.get('day')} {s.get('sym')} {s.get('tf')} (today is {today})")
            return
        self.ledger = list(s.get("ledger") or [])
        self.seen = {tuple(k) for k in s.get("seen") or []}
        self._eod_sent = s.get("eod_sent")
        self._guard_key = s.get("guard_key")
        self._open_routed = s.get("open_routed")
        self._open_qty = s.get("open_qty")
        self._open_adds = [a for a in (s.get("open_adds") or []) if isinstance(a, dict)]
        self._blocked_entries = set(s.get("blocked_entries") or [])
        self._flattened = set(s.get("flattened") or [])
        self._no_entries_day = s.get("no_entries_day")
        self._provisional = {int(k): v for k, v in (s.get("provisional") or {}).items()}
        if s.get("started_at"):
            self.started_at = min(self.started_at, int(s["started_at"]))
        self.kill = bool(s.get("kill")) and not clear_kill
        self._restored = {"ledger": len(self.ledger), "open_routed": self._open_routed, "kill": self.kill,
                          "started_at": self.started_at, "saved_at": s.get("saved_at")}
        self._log("system", f"Restored live state from {os.path.basename(self.state_path)} (saved {_et(s.get('saved_at', 0)):%H:%M:%S} ET): "
                            f"{len(self.ledger)} ledger rows, open routed position {'@' + _et(self._open_routed).strftime('%H:%M') if self._open_routed else 'none'}, "
                            f"kill={'ON' if self.kill else 'off'}, day P&L routed ${self.day_pnl_routed():+,.0f}, {self.trades_today()} trades today")

    def day_pnl_routed(self):
        day = trading_day(self.clock())
        return round(sum(float(r.get("pnl") or 0) for r in self.ledger if r.get("side") == "exit" and trading_day(r["t"]) == day), 2)

    def trades_today(self):
        day = trading_day(self.clock())
        return sum(1 for r in self.ledger if r.get("side") in ("buy", "sell") and trading_day(r["t"]) == day)

    # ------------------------------------------------------------------ one decision cycle
    def poll_once(self):
        t0 = time.perf_counter()
        sym, tf = self.cfg["sym"], self.cfg["tf"]
        secs = TF_SECONDS[tf]
        now = int(self.clock())
        if self.last_poll is not None and now < self.last_poll - 5:
            self._log("warn", f"clock moved backwards by {self.last_poll - now}s (last poll {_et(self.last_poll):%H:%M:%S} ET, now {_et(now):%H:%M:%S})")
        self.health["fallback"] = False
        self.health["nt_down"] = self.health["nt_down_1m"] = None      # set by this poll's NinjaTrader fetches (no_yahoo)
        self._adapter_tick()
        self._refresh_guard()
        df, drops = self._merged(sym, tf, now, secs)
        if len(df) == 0:
            raise RuntimeError("no bars available (history empty and refresh failed)")
        self.health["dropped"] = drops
        if drops["misaligned"] or drops["malformed"]:
            self._log("warn", f"dropped {drops['misaligned']} misaligned / {drops['malformed']} malformed bars from the feed")
        self._detect_revisions(df, secs)
        df_full = df                          # LIT keeps the previous month (its levels), engine/lit_live.py trims it
        window_days = float(self.cfg.get("window_days") or 0)
        if window_days > 0:
            df = df[df["time"] >= df["time"].max() - window_days * 86400]
        # ---- freshness: age = seconds since the last closed bar's close
        last_close = int(df["time"].max()) + secs
        age = now - last_close
        stale = age > 2 * secs + 60
        mopen = market_open(now)
        et_mod = _et(now).hour * 60 + _et(now).minute
        from .lab_adapter import engine_model, live_model
        lm = live_model()                     # live_model.json: which strategy the paper bot / cloud monitor trades
        model = self.cfg.get("model") or lm["model"]
        if model != lm["model"] and model == "engine":
            lm = engine_model()               # cfg pins the old engine while live_model.json runs another model
        eng_params = self.cfg.get("params") or (lm["params"] if model == "engine" else {})
        params = merge_params({**eng_params, "live": True})
        self._params = params
        lit_p = None
        if model == "lit":
            from . import lit as _lit
            lit_p = {**_lit.DEFAULTS, **(self.cfg.get("model_params") or lm.get("lit") or {})}
        windows = lit_p["window"] if lit_p else params["entry_windows"]
        in_entry_window = any(a <= et_mod < z for a, z in windows)
        was_stale = self.health["stale"]
        self.health.update({"data_age_s": int(age), "stale": bool(stale), "market_open": mopen, "last_bar_t": int(df["time"].max())})
        if stale and mopen:
            self.health["stale_polls"] += 1
            if not was_stale:
                self._log("warn", f"DATA STALE: last closed bar {_et(df['time'].max()):%H:%M} ET, age {age // 60} min "
                                  f"(source {self.cfg.get('data_source')}{', fallback' if self.health['fallback'] else ''})")
        else:
            if was_stale and mopen:
                self._log("system", f"Data fresh again (age {age}s)")
            self.health["stale_polls"] = 0
        block = bool(stale and mopen and in_entry_window and self.health["stale_polls"] > int(self.cfg.get("stale_polls_block", 3)))
        was_blocked = self.health["entries_blocked"]
        if block and not was_blocked:
            self._log("risk", f"Feed stale for {self.health['stale_polls']} polls inside an entry window: NEW entries blocked "
                              "(open positions are still managed)")
        self.health["entries_blocked"] = block
        base = from_frame(sym, tf, df)
        if model == "lit":
            from . import lit_live
            df1 = self._lit_1m(sym, now, int(df_full["time"].min())) if lit_p.get("tf") == "1m" else None
            # forming / early: an entry is decided the moment its 1m CISD candle closes and routed at market at once
            # (state "enter_now"), sized from the forming 1m bar's open when the feed shows it (research/writeups/lit-live-fills.md)
            brain_keep = {}                   # the Bot Brain reads this run's market after the poll (engine/brain.py)
            res = lit_live.run(df_full, lit_p, one_min=df1, now=now, sym=sym, week_hist=self.lit_week_hist(),
                               forming=self._forming.get((sym, 60)) if df1 is not None else None, early=True,
                               learn=True, es_df=self._learn_es(sym, tf, now, secs),   # learning loop (engine/lit_learn.py)
                               keep=brain_keep)
            last1 = int(df1["time"].max()) if df1 is not None and len(df1) else None
            self.health["last_1m_bar_t"] = last1
            self.health["bar_1m_behind"] = bool(last1 is not None and mopen and last1 + 60 < now - now % 60)
        elif model.startswith("lab:"):
            from . import lab_adapter
            es_df = None
            if PARTNER.get(sym) in YAHOO:
                try:
                    es_df, _ = self._merged(PARTNER[sym], tf, now, secs)
                    es_df = es_df[es_df["time"] >= int(df["time"].min())]
                except Exception as e:
                    self._note_error(f"partner {PARTNER.get(sym)} unavailable: {e}")
            res = lab_adapter.run(model[4:], df, self.cfg.get("model_params") or lm["params"], es_df)
        else:
            partner = self._partner(sym, tf, now, secs, int(df["time"].min()))
            htf = self._htf(sym, now)
            eng = Engine(base, htf=htf, partner=partner, params=params).run()
            res = eng.result()
        self.state = res["state"]
        # no Yahoo: a NinjaTrader feed that is down blocks NEW entries at once (no 3-poll grace, nothing to fall back to)
        nt_why = (self.health.get("nt_down") or (self.health.get("nt_down_1m") if model == "lit" else None)) if self.no_yahoo else None
        nt_block = bool(nt_why and mopen and in_entry_window)
        if nt_block and not self.health["entries_blocked"] and not was_blocked:
            self._log("risk", f"FEED STALE: NinjaTrader bars missing or stale ({nt_why}) - NEW entries blocked, no Yahoo fallback "
                              "(an open position keeps its broker stop / target and is still managed)")
        self.health["feed_block"] = nt_why if nt_block else (f"feed stale for {self.health['stale_polls']} polls" if block else None)
        self.health["entries_blocked"] = block = bool(block or nt_block)
        if not block and was_blocked:
            self._log("system", "Feed recovered: new entries allowed again")
        self.state["strategy"] = {"model": model, "label": lm.get("label", ""),
                                  "params": eng_params if model == "engine" else lit_p if model == "lit"
                                  else (self.cfg.get("model_params") or lm["params"])}
        # equity-curve filter: every finished signal goes into the shadow ledger; entries trade only while it's positive
        # (the real bot only: test harnesses run with their own state_path and must not touch the shared ledger)
        from . import equity_filter as _eqf
        self._eqf_cfg = lm.get("equity_filter") if self.state_path == STATE_PATH else None
        self._sizing_cfg = lm.get("sizing") if self.state_path == STATE_PATH else None   # late-entry size, fast-eval press
        self._lit_sizing = (self.cfg.get("lit_sizing") or lm.get("lit_sizing")) if model == "lit" else None   # normal/eval/fast_eval/safe_eval/two_week
        self._live_params = lm.get("params") or {}
        if self._eqf_cfg:
            try:
                _eqf.record(res["trades"])
            except Exception as e:
                self._note_error(f"shadow ledger update failed: {e}")
        self.state["equity_filter"] = eqf = _eqf.status(self._eqf_cfg)
        if model == "lit":
            try:
                self.state["eval_2wk"] = self.eval_clock()      # the two-week eval clock and the reset reminder
            except Exception as e:
                self._note_error(f"eval clock failed: {e}")
            self._eval_life_tick()                              # pass / fail day, min-days, weekly loss stop
        if self.state_path == STATE_PATH:
            self._narrate_filter(eqf, lm)
        self.last_poll = now
        self.bars_tail = base.to_records(max(0, len(base) - 400))
        self._emit_events(res, sym)
        self._eod_summary(res, sym, now)
        self._route_signals(res, sym, now, secs)
        self._guards_tick(now)
        self._alerts_tick(now)
        self.health["poll_ms"] = int((time.perf_counter() - t0) * 1000)
        self.health["last_ok_poll"] = now
        self.health["ok"] = not (self.health["stale"] and mopen) and not self.health["desync"]
        self._save_state()
        if model == "lit":                    # after routing and the state save: never delays an order
            self._brain_tick(res, lit_p, now, brain_keep)
            self._second_tick(df_full, df1, res, now)
        return self.state

    def _second_tick(self, df5, df1, res, now):
        """Second strategies, PAPER ONLY (engine/second.py, second_model.json): EMA / MACD on this poll's bars, after LIT's
        routing and the state save, in a background thread (never delays LIT, never routes: engine/second.py has no adapter);
        once per new closed 1m / 5m bar; the heartbeat carries the result as "second". A failure only logs an error."""
        if self.state_path != STATE_PATH and not self.cfg.get("second"):
            return                            # test harnesses: off unless asked
        try:
            key = (int(df5["time"].max()), int(df1["time"].max()) if df1 is not None and len(df1) else 0)
        except Exception:
            return
        if key == getattr(self, "_second_key", None) or getattr(self, "_second_busy", False):
            return
        self._second_key, self._second_busy = key, True
        from . import second as _second
        lit_w = _second.lit_windows(res)

        def run():
            try:
                cfg = _second.load_cfg()
                cfg["strategies"] = {k: v for k, v in cfg["strategies"].items() if not v.get("cloud_only")}   # e.g. LIT + Asia
                if any(s.get("on", True) for s in cfg["strategies"].values()):
                    self.second = _second.run(df5, one_min=df1, now=now, cfg=cfg, lit=lit_w)
                else:
                    self.second = None
            except Exception as e:
                self._note_error(f"second strategies failed: {e.__class__.__name__}: {e}")
            finally:
                self._second_busy = False
        threading.Thread(target=run, name="second-paper", daemon=True).start()

    def _brain_tick(self, res, P, now, keep):
        """The Bot Brain (engine/brain.py): what LIT is thinking at this poll, read from this poll's result. Read-only,
        built after the routing; a failure only logs an error. The real bot keeps the thought log in data/brain/."""
        try:
            from . import brain
            if self._brain_log is None:
                self._brain_log = brain.BrainLog(brain.BRAIN_DIR if self.state_path == STATE_PATH else None)
            self.brain = brain.build(res, P, now, keep=keep, ctx=brain.bot_ctx(self, now), log=self._brain_log)
        except Exception as e:
            self._note_error(f"bot brain failed: {e.__class__.__name__}: {e}")

    def _lit_1m(self, sym, now, t_min):
        """1m bars for LIT's entry (stored data/<sym>_1m.csv + the NinjaTrader archive + NinjaTrader's 1m file; with no_yahoo
        off: + Yahoo 1m, capped at 7 days). Never raises and never
        changes the feed-health flags of the bot's own 5m feed; None = LIT executes that day on 5m bars."""
        keep = {k: self.health.get(k) for k in ("fallback", "fetch_ok", "last_error", "last_error_t")}
        try:
            df1, _ = self._merged(sym, "1m", now, 60, period="5d", max_days=7)
            # remember what was fetched: a failed fetch or the 7-day cap must not take a traded day's 1m bars away
            store = getattr(self, "_lit_1m_store", None)
            if store is not None and len(store):
                df1 = pd.concat([store, df1]).drop_duplicates("time", keep="last").sort_values("time")
            df1 = df1[df1["time"] >= t_min].reset_index(drop=True)
            self._lit_1m_store = df1[df1["time"] >= int(df1["time"].max()) - 12 * 86400] if len(df1) else df1
            return df1 if len(df1) else None
        except Exception:
            return None
        finally:
            self.health.update(keep)

    def _refresh_guard(self):
        """Refresh the news calendar (archived into the engine's event list) and VIX; log guard transitions."""
        try:
            from . import news
            news.ff_calendar()
            news.volatility()
            g = news.guard(now=int(self.clock()), params={**self.cfg.get("params", {})})
            if not g["allowed"]:
                self._log("news", "Guard: " + "; ".join(g["reasons"]))
            gkey = "|".join(g["reasons"]) or "clear"
            if gkey != self._guard_key:
                if self._guard_key is not None:
                    self._alert(("⚠️ STAND DOWN: " + "; ".join(g["reasons"])) if g["reasons"] else "✅ Guard clear: trading allowed again", "guard")
                self._guard_key = gkey
        except Exception as e:
            self._note_error(f"news refresh failed: {e}")

    def _detect_revisions(self, df, secs):
        """A closed bar whose OHLC changes between polls means the feed revised history: the engine's decisions may flip."""
        tail = df.tail(60)
        cur = {int(t): (float(o), float(h), float(l), float(c)) for t, o, h, l, c in
               zip(tail["time"], tail["open"], tail["high"], tail["low"], tail["close"])}
        changed = [t for t, v in cur.items() if t in self._last_bars and any(abs(a - b) > 1e-9 for a, b in zip(self._last_bars[t], v))]
        if changed:
            self.health["revisions"] += len(changed)
            self._log("warn", f"feed revised {len(changed)} already-closed bar(s), e.g. {_et(changed[0]):%H:%M} ET - decisions may change")
        self._last_bars = cur

    def _partner(self, sym, tf, now, secs, t_min):
        ps = PARTNER.get(sym)
        if ps not in YAHOO:
            return None
        try:
            pdf, _ = self._merged(ps, tf, now, secs)
            pdf = pdf[pdf["time"] >= t_min]
            return from_frame(ps, tf, pdf) if len(pdf) else None
        except Exception as e:
            self._note_error(f"partner {ps} unavailable: {e}")
            return None

    def _htf(self, sym, now):
        """Stored 1h history merged with fresh 1h bars so HTF structure stays current."""
        hist = self.read_hist(sym, "1h")
        try:
            rec = self.fetch_recent(sym, "1h", _cover_gap(hist, now, "5d", max_days=700))
            if rec is not None and len(rec):
                hist = pd.concat([hist, rec])
        except Exception as e:
            self._note_error(f"data refresh failed ({sym} 1h): {e.__class__.__name__}: {e}")
        h1, _ = clean_bars(hist, 3600, now, grid=False)
        return from_frame(sym, "1h", h1)

    def _emit_events(self, res, sym):
        start = self.started_at
        for ev in res["events"]:
            key = (ev["t"], ev["type"], ev["text"])
            if ev["t"] < start - 3600 or key in self.seen:
                continue
            self.seen.add(key)
            self._log(ev["type"], ev["text"], bar_t=ev["t"])
            if ev["type"] in ("sweep", "signal", "entry", "exit"):
                icon = {"sweep": "🧲", "signal": "🎯", "entry": "🟢" if ev.get("dir", 1) == 1 else "🔴", "exit": "🏁"}[ev["type"]]
                self._alert(f"{icon} {sym} {ev['type'].upper()}\n{ev['text']}", ev["type"])

    def _eod_summary(self, res, sym, now):
        """Once per session after 16:05 ET."""
        try:
            et = _et(now)
            day = et.strftime("%Y-%m-%d")
            if et.hour * 60 + et.minute >= 965 and self._eod_sent != day and self.state:
                self._eod_sent = day
                st = _et(self.started_at or now)
                if st.strftime("%Y-%m-%d") == day and st.hour * 60 + st.minute >= 965:
                    return      # started after the close: nothing was watched today, no summary
                todays = [t for t in res["trades"] if t.get("exit_t", 0) >= now - 12 * 3600]
                pnl = sum(t["pnl"] for t in todays)
                lines = [f"📊 {sym} end of day {day}", f"Trades: {len(todays)} · P&L ${pnl:+,.0f}"]
                lines += [f"{'L' if t['dir'] == 1 else 'S'} {t.get('grade', '')} {t['trigger']} → {t['exit_reason']} {t['pnl_r']:+.2f}R" for t in todays]
                lines.append(f"Model now: {self.state.get('model_state')}")
                self._log("daily", "\n".join(lines))
                self._alert("\n".join(lines), "daily")
        except Exception as e:
            self._note_error(f"daily summary failed: {e}")

    def _narrate_filter(self, eqf, lm):
        """Say in the bot log which strategy is locked in (once per start) and every time the cold-streak filter flips."""
        if not getattr(self, "_strategy_announced", False):
            self._strategy_announced = True
            self._log("system", f"Strategy locked: {lm.get('label') or lm.get('model')}"
                                f"{' (owner pick ' + lm['chosen'] + ')' if lm.get('chosen') else ''}. {eqf['reason']}.")
        if not eqf.get("enabled"):
            return
        prev = getattr(self, "_eqf_last_on", None)
        self._eqf_last_on = eqf["on"]
        if prev is None or prev == eqf["on"]:
            return
        if eqf["on"]:
            text = f"Cold streak over: last {eqf['n']} signals {eqf['sum_r']:+.2f}R. Back to full size."
        elif eqf.get("mult"):
            text = (f"Cold streak: last {eqf['n']} signals {eqf['sum_r']:+.2f}R. Still taking every setup at {eqf['mult']:g}x size "
                    f"until they add back up above 0R.")
        else:
            text = (f"Cold streak: last {eqf['n']} signals {eqf['sum_r']:+.2f}R. Sitting out; every setup is still tracked "
                    f"on paper and trading resumes when they add back up above 0R.")
        self._log("risk", text)
        self._alert(("⏸️ " if not eqf["on"] else "▶️ ") + text, "guard")

    def _exit_rows(self):
        """This process's routed exits as weekly-stop rows (engine/lit.py week_stops)."""
        out = []
        for r in self.ledger:
            if r.get("side") != "exit" or r.get("entry_t") is None:
                continue
            out.append({"day": trading_day(r["entry_t"]), "entry_t": int(r["entry_t"]), "exit": r.get("reason"),
                        "exit_t": int(r.get("exit_t") or r["t"]), "pnl": float(r.get("pnl") or 0.0)})
        return out

    def lit_week_hist(self):
        """LIT weekly stop: this ISO week's routed exits (earlier days restored from live_state.json + today's ledger)."""
        from .lit import iso_week
        wk = iso_week(trading_day(self.clock()))
        rows = {(r["day"], r.get("entry_t")): r for r in self._week_prev if iso_week(r["day"]) == wk}
        for r in self._exit_rows():
            rows[(r["day"], r["entry_t"])] = r
        return sorted(rows.values(), key=lambda r: r["exit_t"])

    def eval_start(self):
        """First session of the current eval (yyyy-mm-dd): the start cfg's "eval_start" (PC override), else live_model.json
        lit_sizing.eval_start (LIT); "" = unknown (every ledger day counts, the two_week sizer falls back to eval)."""
        return str(self.cfg.get("eval_start") or (getattr(self, "_lit_sizing", None) or {}).get("eval_start") or "")

    def eval_days(self):
        """Routed P&L per trading day of the eval (earlier days from live_state.json + today's ledger), from eval_start()."""
        start = self.eval_start()
        days = {d: v for d, v in self._eval_prev.items() if not start or d >= start}
        today = trading_day(self.clock())
        days.pop(today, None)
        for r in self.ledger:
            if r.get("side") == "exit" and (not start or trading_day(r["t"]) >= start):
                d = trading_day(r["t"])
                days[d] = round(days.get(d, 0.0) + float(r.get("pnl") or 0), 2)
        prior = float(self.cfg.get("eval_prior_pnl") or (getattr(self, "_lit_sizing", None) or {}).get("eval_prior_pnl") or 0.0)
        if prior:                            # the eval's P&L before eval_start (owner's account, e.g. -$100): one day before all
            days["0000-00-00"] = prior
        return days

    def eval_room(self):
        """MFFU 50K room: eval balance minus the trailing max-loss floor (engine/sizing.mffu_eval)."""
        from . import sizing as _sz
        return _sz.mffu_eval(self.eval_days())["cushion"]

    def eval_state(self):
        """The two_week sizer's eval state (engine/sizing.eval_state): routed P&L of the eval's earlier days (live_state.json
        eval_days), today's routed P&L so far, the session number since eval_start(). None when the eval start is unknown."""
        from . import sizing as _sz
        start = self.eval_start()
        if not start:
            return None
        today = trading_day(self.clock())
        days = self.eval_days()
        st = _sz.eval_state({d: v for d, v in days.items() if d < today}, float(days.get(today, 0.0)),
                            session=max(1, _sz.eval_session(start, today) or 1), today=today)   # today: wk_pnl (wk_loss_usd)
        st["n_today"] = int(self.trades_today())
        return st

    def eval_life(self):
        """State key eval_life (engine/eval_life.view): eval open / passed / failed, the minimum-days trade, the eval weekly
        loss stop (off / armed / tripped). None when the eval start is unknown or the sizing is not an eval mode."""
        from . import eval_life as _el
        lsz = getattr(self, "_lit_sizing", None) or {}
        start = self.eval_start()
        if not start or (lsz.get("mode") or "") not in _el.EVAL_MODES:
            return None
        e = _et(self.clock())
        over = e.weekday() < 5 and e.hour * 60 + e.minute >= 16 * 60
        return _el.view(self.eval_days(), start, trading_day(self.clock()), lsz, session_over=over, n_today=self.trades_today())

    def _eval_life_tick(self):
        """Every poll (LIT): the eval lifecycle into the state, a log line + one push on the pass day, the fail day and when
        the weekly loss stop trips (each push once: engine/push keeps the keys)."""
        try:
            v = self.eval_life()
        except Exception as e:
            self._note_error(f"eval lifecycle failed: {e}")
            return
        self.state["eval_life"] = v
        if not v:
            return
        from . import eval_life as _el
        seen = getattr(self, "_eval_life_seen", None)
        if seen is None:
            seen = self._eval_life_seen = set()
        for p in _el.notices(v, self._push_account(), self.clock()):
            if p["key"] in seen:
                continue
            seen.add(p["key"])
            self._log("risk", f"{p['title']}: {v['trading']}")
            self._push_send(p)

    def eval_clock(self):
        """State key eval_2wk: session x of 10 since eval_start(), reset recommended after session 10 (engine/sizing.eval_clock)."""
        from . import sizing as _sz
        e = _et(self.clock())
        over = e.weekday() < 5 and e.hour * 60 + e.minute >= 16 * 60          # after the 15:55 flat: today's session is done
        return _sz.eval_clock(self.eval_days(), self.eval_start() or None, trading_day(self.clock()), session_over=over)

    def eval_profit(self):
        """The eval account's routed profit ($) since cfg eval_start (yyyy-mm-dd; default: everything in the ledger).
        Used by the fast-eval press (engine/sizing.py); None when the ledger is empty."""
        start = self.eval_start()
        rows = [r for r in self.ledger if r.get("side") == "exit" and (not start or trading_day(r["t"]) >= start)]
        return round(sum(float(r.get("pnl") or 0) for r in rows), 2) if self.ledger else None

    def _equity_qty(self, entry_t, qty, pos=None):
        """Size to route for one entry (0 = hold it back): the engine's micros x cold-streak size x late-entry size, with
        the fast-eval press when configured (engine/sizing.py). Logged whenever it differs from the engine's micros."""
        try:
            from . import equity_filter as _eqf
            from . import sizing as _sz
            st = _eqf.status(getattr(self, "_eqf_cfg", None), before_t=entry_t)
            mult = st.get("mult", 1.0 if st["on"] else 0.0)
            if mult <= 0:
                self._log("risk", f"Entry at {_et(entry_t):%H:%M} ET NOT traded: {st['reason']}")
                return 0
            lsz = getattr(self, "_lit_sizing", None)
            if (self.state or {}).get("model") == "lit":
                # LIT: the model's micros already carry the weekly stop; lit_sizing (normal / fast_eval / safe_eval) re-sizes
                # from the stop with one rounding (engine/sizing.lit_qty)
                mode = (lsz or {}).get("mode")
                room = self.eval_room() if mode in ("safe_eval", "eval", "two_week") else None
                if mode in ("funded", "auto"):         # the funded account's balance / trailing floor / payouts
                    from .multi_account import primary_state
                    st_ = primary_state(self, mode)
                else:
                    # every eval mode gets the eval state (2026-10-20): the pass / fail lock and the weekly loss stop
                    # (engine/sizing.eval_lock, wk_loss_usd); eval / safe_eval / fast_eval size from the room as before
                    st_ = self.eval_state() if mode in ("two_week", "eval", "safe_eval", "fast_eval") else None
                r = _sz.lit_qty(int(qty), pos or {}, lsz, room=room, state=st_)
                if r.get("learn"):             # the learning loop's multiplier at this entry (applied, or would-be in observe)
                    if not hasattr(self, "_learn_at"):
                        self._learn_at = {}
                    self._learn_at[entry_t] = {k: r["learn"].get(k) for k in ("mode", "mult", "would", "skip", "would_skip", "buckets")}
                if r.get("fallback"):
                    self._log("risk", f"Entry at {_et(entry_t):%H:%M} ET sizing: {r['fallback']}")
            else:
                r = _sz.route_qty(int(qty), pos or {}, mult, getattr(self, "_sizing_cfg", None), getattr(self, "_live_params", None),
                                  self.eval_profit() if getattr(self, "_sizing_cfg", None) and self._sizing_cfg.get("press") else None)
        except Exception as e:
            mode = str((getattr(self, "_lit_sizing", None) or {}).get("mode") or "")
            if (self.state or {}).get("model") == "lit" and mode in ("two_week", "eval", "safe_eval", "funded"):
                # an eval / funded account: never route without the room caps (fail closed)
                self._note_error(f"sizing failed ({mode}): {e.__class__.__name__}: {e}")
                self._log("risk", f"Entry at {_et(entry_t):%H:%M} ET NOT traded: the {mode} sizing failed, so the eval room caps "
                                  "could not be applied")
                return 0
            self._note_error(f"sizing failed, entry allowed at the engine's size: {e}")
            return qty
        if r["qty"] != qty:
            why = "; ".join(r["reasons"]) or st.get("reason", "")
            self._log("risk", f"Entry at {_et(entry_t):%H:%M} ET at {r['qty']} instead of {qty}: {why}")
        return r["qty"]

    def _confirm_provisional(self, pos, en, res, sym):
        """A LIT entry routed on its 1m CISD close (before its fill bar existed), checked once the model has that bar: the
        same trade -> nothing to do (micros / target compared when the size came from an estimate); no trade any more (the
        real open failed a check the estimate passed, e.g. the 1.5R minimum) -> the routed position is flattened at once."""
        et_ = self._open_routed
        pv = self._provisional.get(et_) if et_ is not None else None
        if not pv or pv.get("done") or (en and en.get("entry_t") == et_):
            return
        cur = pos if pos and pos.get("entry_t") == et_ else next((t for t in res["trades"] if t["entry_t"] == et_), None)
        if cur is None and not self._fill_bar_seen(et_):
            # the feed has not shown the fill bar yet (LE_BarFeed / Yahoo writes it on the next minute's first tick; at a 5m
            # boundary the 5m bar can lag too, and then the setup itself is out of the model's window): no verdict yet, the
            # broker bracket keeps protecting the position; checked again on the next poll
            self._pv_wait = et_
            if not pv.get("wait_logged"):
                pv["wait_logged"] = True
                self._log("warn", f"LIT entry {_et(et_):%H:%M} ET: its fill bar is not in the feed yet; the routed position is "
                                  "kept (stop/target at the broker) until the model can check it")
            return
        self._pv_wait = None
        pv["done"] = True
        if cur is None:
            self._log("risk", f"LIT entry routed at the {_et(et_):%H:%M} ET 1m CISD close is not the model's trade once its fill bar "
                              "closed (sized from an estimate): flattening the routed position")
            self._flattened.add(et_)
            self._route({"sym": sym, "side": "exit", "qty": self._open_qty, "reason": "NO TRADE", "entry_t": et_, "pnl": 0.0})
            self._open_routed = None
            return
        d = pv["dir"]
        if int(cur["qty"]) != int(pv["model_qty"]):
            self._log("warn", f"LIT entry {_et(et_):%H:%M} ET: routed {pv['qty']} micros sized from the CISD close; the model's trade "
                              f"(sized from the real open) has {int(cur['qty'])}. The broker keeps {pv['qty']}.")
        tg = tick_px(cur["target"], d, target=True)
        if tg is not None and abs(float(tg) - float(pv["target"])) > 1e-9:
            self._log("warn", f"LIT entry {_et(et_):%H:%M} ET: broker target {pv['target']:.2f} (from the estimate), the model's "
                              f"target is {tg:.2f}; the model's exit is still routed when it comes")

    def _fill_bar_seen(self, et_):
        """True when this poll's model had the bars to decide the LIT entry with fill bar et_: the 1m feed holds that bar
        (closed) and the 5m bars reach the 5m bar containing it (closed, or added as the forming 5m bar in early mode)."""
        l1 = self.health.get("last_1m_bar_t")
        l5 = self.health.get("last_bar_t")
        if l1 is None or l5 is None or int(l1) < int(et_):
            return False
        b5 = int(et_) - int(et_) % 300
        f5 = bool(((self.state or {}).get("lit") or {}).get("forming_5m"))
        return int(l5) >= b5 or (f5 and int(l5) + 300 >= b5)

    # ------------------------------------------------------------------ extra accounts (engine/multi_account.py, off by default)
    def _start_accounts(self):
        """The start cfg's "accounts" list: one router for every extra account (None without the list: one account)."""
        self.accts = None
        if not self.cfg.get("accounts"):
            return
        try:
            from . import multi_account
            self.accts = multi_account.build(self, self.cfg)
        except Exception as e:
            self.accts = None
            self._note_error(f"extra accounts NOT started: {e.__class__.__name__}: {e}")
            self._log("risk", f"Extra accounts NOT started ({e.__class__.__name__}: {e}): only the bot's own account trades")

    def _route_signals(self, res, sym, now, secs):
        """The bot's own account (_route_primary) and, when configured, every extra account at the same time."""
        if self.accts is None:
            return self._route_primary(res, sym, now, secs)
        job = None
        try:
            job = self.accts.begin(res, sym, now, secs, entry_block="feed stale" if self.health.get("entries_blocked") else None)
        except Exception as e:
            self._note_error(f"extra accounts routing failed: {e.__class__.__name__}: {e}")
        try:
            return self._route_primary(res, sym, now, secs)
        finally:
            try:
                self.accts.finish(job)
            except Exception as e:
                self._note_error(f"extra accounts routing failed: {e.__class__.__name__}: {e}")

    def _route_primary(self, res, sym, now, secs):
        """Turn the engine's position / completed trades into adapter calls, exactly once each."""
        start = self.started_at
        pos = self.state.get("position")
        # LIT: an entry decided on its 1m CISD close (lit_live state "enter_now"), routed at market at once; the open
        # position with the same entry_t appears once its fill bar has closed (then it is already routed, and checked)
        en = self.state.get("enter_now") if not pos else None
        late_after = 2 * secs + 60
        self._confirm_provisional(pos, en, res, sym)
        # desync: we routed an entry the engine no longer knows about (no open position, no completed trade with it)
        if self._open_routed is not None:
            known = (pos and pos.get("entry_t") == self._open_routed) or (en and en.get("entry_t") == self._open_routed) \
                or getattr(self, "_pv_wait", None) == self._open_routed or any(t["entry_t"] == self._open_routed for t in res["trades"])
            if not known and not self.health["desync"]:
                self.health["desync"] = True
                self._log("risk", f"DESYNC: entry routed at {_et(self._open_routed):%H:%M} ET is no longer in the model (feed revision?). "
                                  "Check the broker position by hand.")
        if self.kill:
            return
        # clock-based safety net: the Engine's TIME flatten only fires on a bar it has seen. If the feed stalls across
        # flat_mod, flatten the routed position from the wall clock instead (prop rule: never hold through the close).
        flat_mod = int(merge_params(self.cfg.get("params", {}))["flat_mod"])
        e = _et(now)
        if self._open_routed is not None and e.hour * 60 + e.minute >= flat_mod + 3 and self._open_routed not in self._flattened \
                and pos is not None and pos.get("entry_t") == self._open_routed:
            self._log("risk", f"SAFETY FLATTEN: {e:%H:%M} ET is past flat time {flat_mod // 60:02d}:{flat_mod % 60:02d} and the model still shows "
                              f"the position (feed age {self.health.get('data_age_s')}s) - flattening from the clock")
            self._flattened.add(self._open_routed)
            self._route({"sym": sym, "side": "exit", "qty": int(self._open_qty or pos.get("qty") or 0) + self._adds_qty(self._open_routed),
                         "reason": "TIME SAFETY", "entry_t": self._open_routed})
            self._open_routed = None
        ent = pos or en
        if ent and ent["entry_t"] >= start - secs and ("entry", ent["entry_t"]) not in self.seen:
            self.seen.add(("entry", ent["entry_t"]))
            age = now - (ent["entry_t"] + secs)
            if self.health["entries_blocked"]:
                self._blocked_entries.add(ent["entry_t"])
                self._log("risk", f"Entry at {_et(ent['entry_t']):%H:%M} ET NOT routed: feed stale")
            elif self._no_entries_day is not None and self._no_entries_day == trading_day(now):
                self._blocked_entries.add(ent["entry_t"])
                self._log("risk", f"Entry at {_et(ent['entry_t']):%H:%M} ET NOT routed: the owner flattened remotely today "
                                  "(no new entries until the next trading day)")
            elif age > late_after:
                self._blocked_entries.add(ent["entry_t"])
                self._log("risk", f"Entry at {_et(ent['entry_t']):%H:%M} ET NOT routed: seen {age // 60} min late (restart / feed gap) - not chasing")
            elif not (q := self._equity_qty(ent["entry_t"], ent["qty"], ent)):
                self._blocked_entries.add(ent["entry_t"])
            elif (gb := self._guard_entry(ent, q, sym, now)):
                self._blocked_entries.add(ent["entry_t"])          # engine/guards.py: only ever blocks
                self._log("risk", f"Entry at {_et(ent['entry_t']):%H:%M} ET NOT routed: GUARD {gb}")
            else:
                self._open_routed = ent["entry_t"]
                self._open_qty = q
                self._open_adds = []
                d = 1 if ent["dir"] == 1 else -1
                if ent is en:
                    self._provisional[int(en["entry_t"])] = {"qty": q, "model_qty": int(en["qty"]), "dir": d, "est": bool(en.get("est")),
                                                             "target": tick_px(en["target"], d, target=True), "t": int(self.clock())}
                    self._log("system", f"LIT 1m CISD closed at {_et(en['entry_t']):%H:%M} ET: MARKET entry sent at once "
                                        f"({int(self.clock()) - int(en['entry_t'])} s after the close; the backtest fills at this bar's open)"
                                        + ("; size from the CISD close, the feed did not show this bar's open yet" if en.get("est") else ""))
                rr = self._route(self._entry_action(ent, q, sym))
                self._guard_routed(ent["entry_t"])
                self._push_fill(ent, q, sym, rr)
        if pos and self._open_routed == pos.get("entry_t") and getattr(self.adapter, "route_stop_moves", False):
            self._route_stop_move(pos, sym)
        if pos and self._open_routed == pos.get("entry_t") and (pos.get("add_now") or pos.get("adds")):
            self._route_add(pos, sym)
        for tr in res["trades"]:
            if tr["exit_t"] >= start - secs and ("exit", tr["entry_t"]) not in self.seen:
                self.seen.add(("exit", tr["entry_t"]))
                if tr["entry_t"] in self._blocked_entries:
                    self._log("system", f"Exit {tr['exit_reason']} for the un-routed entry at {_et(tr['entry_t']):%H:%M} ET - nothing to flatten")
                    continue
                if tr["entry_t"] in self._flattened:
                    self._log("system", f"Model exit {tr['exit_reason']} for the position already safety-flattened at the close - not sent again")
                    if ("entry", tr["entry_t"]) in self.seen:
                        self._remember(tr, sym, note="safety/kill flattened before the model exit: broker fill may differ")
                    continue
                routed = ("entry", tr["entry_t"]) in self.seen
                if not routed:
                    # the model entered during a gap (bot down / feed burst): no order of ours exists for it
                    if self.cfg["adapter"] == "paper":
                        self._log("warn", f"Exit {tr['exit_reason']} for an entry never routed (model entered {_et(tr['entry_t']):%H:%M} ET during a gap) - "
                                          "nothing to flatten on paper")
                        continue
                    self._log("warn", f"Exit {tr['exit_reason']} for an entry this process never routed (model entered {_et(tr['entry_t']):%H:%M} ET during a gap): "
                                      "flatten sent in case a broker position exists - verify by hand")
                qty = tr["qty"]
                if self._open_routed == tr["entry_t"]:
                    self._open_routed = None
                    qty = self._open_qty or tr["qty"]          # what we actually routed (half size in a cold streak)
                pnl_x = self._routed_pnl(tr, qty)
                q_add = self._adds_qty(tr["entry_t"])          # LIT scale_in: the adds routed to this position
                if self.cfg["adapter"] == "paper" or tr["exit_reason"] == "TIME" or getattr(self.adapter, "route_all_exits", False):
                    # brackets handle stop/target at the broker; the bot only flattens on time exits (adapters with
                    # route_all_exits also get TIME STOP / giveback / news exits, and a harmless sync flatten after a bracket fill)
                    self._route({"sym": sym, "side": "exit", "qty": qty + q_add, "reason": tr["exit_reason"], "pnl": pnl_x,
                                 "entry_t": tr["entry_t"], "exit_t": tr["exit_t"]})
                if routed:
                    self._remember(tr, sym)      # every completed routed trade feeds the persistent memory
                    self._journal(tr, qty)       # and the LIT learning loop's journal (data/lit_journal.jsonl)
                    self._push_outcome(tr, qty, sym)

    # ------------------------------------------------------------------ safety guards (engine/guards.py: block / close only)
    @staticmethod
    def _entry_action(ent, q, sym):
        d = 1 if ent["dir"] == 1 else -1
        return {"sym": sym, "side": "buy" if d == 1 else "sell", "qty": q,
                "stop": tick_px(ent["stop"], d), "target": tick_px(ent["target"], d, target=True),
                "entry": ent["entry"], "entry_t": ent["entry_t"]}

    def _guard_entry(self, ent, q, sym, now):
        """A reason not to route this entry (order sanity, duplicate, daily loss, clock, news, calendar), else None."""
        try:
            from . import guards
            return guards.entry_block(self, ent, self._entry_action(ent, q, sym), q, now)
        except Exception as e:
            self._note_error(f"guards failed: {e.__class__.__name__}: {e}")
            return None

    def _guard_routed(self, entry_t):
        try:
            from . import guards
            guards.note_routed(self, entry_t)
        except Exception as e:
            self._note_error(f"guards failed: {e.__class__.__name__}: {e}")

    def _guards_tick(self, now):
        """Once per poll, after routing: room alarm, NinjaTrader reconcile, 17:00 P&L reconcile, clock probe."""
        try:
            from . import guards
            guards.tick(self, now)
        except Exception as e:
            self._note_error(f"guards failed: {e.__class__.__name__}: {e}")

    def _alerts_tick(self, now):
        """After routing: the "LIT setup armed" / "Setup expired" pushes (engine/alerts_plus.py). Real bot only; read-only
        (the push goes out in a thread); never raises."""
        if self.state_path != STATE_PATH:
            return
        try:
            from . import alerts_plus
            alerts_plus.pc_setup_tick(self, now)
        except Exception as e:
            self._note_error(f"setup alerts failed: {e.__class__.__name__}: {e}")

    # ------------------------------------------------------------------ phone notifications (engine/push.py, Web Push)
    def _push_account(self):
        """The account label of a PC notification: "Paper", the NinjaTrader account name ("Sim101"), or live_model.json
        "account": {"name"} (default "MFFU 50K") for a real account."""
        from . import push
        from .lab_adapter import live_model
        name = str(self.cfg.get("adapter") or "paper")
        if name == "paper":
            return "Paper"
        env = getattr(self.adapter, "env", None)
        acct = getattr(self.adapter, "account", None)
        if env != "live":
            return str(acct or "Demo")
        try:
            return push.account_label(live_model(), "live")
        except Exception:
            return "MFFU 50K"

    def _push_send(self, payload):
        """Only the real bot sends (harnesses run with their own state_path). Never raises into routing."""
        if self.state_path != STATE_PATH:
            return None
        try:
            from . import push
            return push.pc_notify(payload)
        except Exception as e:
            self._log("warn", f"phone notification failed: {e.__class__.__name__}")
            return None

    def _push_fill(self, pos, qty, sym, res):
        """ENTRY notice for a routed entry (paper: the fill; NinjaTrader notifies its own real fill)."""
        try:
            from . import push
            res = res or {}
            if getattr(self.adapter, "reports_fills", False) or res.get("ok") is False:
                return
            self._push_send(push.entry_payload(self._push_account(), "LONG" if pos.get("dir") == 1 else "SHORT", qty, pos["entry_t"],
                                               src="pc", contract="MNQ" if sym == "NQ" else "MES" if sym == "ES" else sym,
                                               entry=pos.get("entry"), stop=pos.get("stop0", pos.get("stop")), target=pos.get("target")))
        except Exception as e:
            self._log("warn", f"phone notification failed: {e.__class__.__name__}")

    def _push_outcome(self, tr, qty, sym):
        try:
            from . import push
            usd = float(tr.get("pnl") or 0) * qty / tr["qty"] if tr.get("qty") else float(tr.get("pnl") or 0)
            self._push_send(push.outcome_payload(self._push_account(), "LONG" if tr.get("dir") == 1 else "SHORT", tr.get("exit_reason"),
                                                 usd, tr["entry_t"], tr.get("exit_t"), src="pc", R=tr.get("pnl_r"), qty=qty))
        except Exception as e:
            self._log("warn", f"phone notification failed: {e.__class__.__name__}")

    # ------------------------------------------------------------------ background loop
    def _loop(self, gen=None):
        gen = self._gen if gen is None else gen
        while not self.stop_flag.is_set() and gen == self._gen:
            try:
                self.poll_once()
                self.errors = 0
                self.health["consecutive_errors"] = 0
            except Exception as e:
                self.errors += 1
                self.health["consecutive_errors"] += 1
                self._note_error(f"poll failed: {e.__class__.__name__}: {e}")
                self.health["ok"] = False
                traceback.print_exc()
            self.stop_flag.wait(self._sleep_s())

    def _sleep_s(self):
        """Seconds to the next poll: aligned to the minute (cfg poll_offsets, default 2 s and 32 s after each minute boundary,
        so a closed 1m bar is acted on ~2 s after it closes and exits get a mid-minute look). cfg poll_align false, or a
        poll_sec under 30 (test harnesses), keeps the plain poll_sec sleep. With NinjaTrader's 1m feed, a 1m bar not yet in
        the file at the 2 s poll (LE_BarFeed writes it on the first tick of the next minute) is re-polled the moment the file
        changes (up to 20 s after the boundary)."""
        ps = float(self.cfg.get("poll_sec", 60) or 60)
        if self.cfg.get("poll_align") is False or ps < 30:
            return ps
        now = float(self.clock())
        if self._await_nt_bar(now):
            return 0.0
        return max(0.0, next_wake(now, self.cfg.get("poll_offsets") or (2.0, 32.0)) - now)

    def _await_nt_bar(self, now, limit_s=20.0, step=0.25):
        """True (poll again now) once NinjaTrader's 1m file changed after the poll found the minute's bar missing."""
        boundary = int(now // 60 * 60)
        if self.cfg.get("data_source") != "ninjatrader" or not self.health.get("bar_1m_behind") or self._nt_repoll == boundary \
                or now - boundary >= limit_s or self._nt_feed is None:
            return False
        self._nt_repoll = boundary
        path = self._nt_feed.file_for(self.cfg.get("sym", "NQ"), 1)
        if not path:
            return False
        try:
            m0 = os.stat(path).st_mtime_ns
        except OSError:
            return False
        t_end = time.time() + max(0.0, limit_s - (now - boundary))
        while time.time() < t_end and not self.stop_flag.is_set():
            self.stop_flag.wait(step)
            try:
                if os.stat(path).st_mtime_ns != m0:
                    return True
            except OSError:
                return False
        return False

    def snapshot(self):
        cfg = {k: v for k, v in self.cfg.items() if k not in ("webhook_url", "confirm")}   # never the typed phrase
        if isinstance(cfg.get("accounts"), list):    # no per-account phrase in the API answer
            cfg["accounts"] = [{k: v for k, v in a.items() if k != "confirm"} if isinstance(a, dict) else a for a in cfg["accounts"]]
        return {"running": self.running, "cfg": cfg,
                "state": self.state, "log": list(self.log)[:200], "ledger": self.ledger[-100:],
                "last_poll": self.last_poll, "started_at": self.started_at, "errors": self.errors,
                "health": dict(self.health), "kill": self.kill,
                "day_pnl_routed": self.day_pnl_routed() if self.cfg else 0.0,
                "trades_today": self.trades_today() if self.cfg else 0,
                "bars": self.bars_tail}


BOT = LiveBot()
