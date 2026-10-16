"""Live / paper trading loop.

The live bot runs the *same* Engine as the backtester on a rolling window of the latest bars every poll,
so live decisions and backtest decisions can never drift apart. New entries/exits detected after the bot
was started are routed to the selected broker adapter.

Adapters
  paper       - default. Simulated fills recorded in the ledger (no external calls).
  traderspost - POSTs JSON signals to YOUR TradersPost webhook (MFFU supports TradersPost-style automation).
  tradovate   - REST skeleton for Tradovate (demo endpoint by default). Requires your own API credentials in
                environment variables; disabled unless explicitly armed. Test on demo first.

Data: Yahoo Finance futures quotes (free, may be delayed). For real-money execution use your broker's feed.
"""
from __future__ import annotations

import json
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
ADAPTERS = {"paper": PaperAdapter, "traderspost": TradersPostAdapter, "tradovate": _TvAdapter,
            "tradovate-demo": _TvAdapter, "tradovate-live": _TvAdapter}


STATE_PATH = os.path.join(DATA_DIR, "live_state.json")
ET_TZ = ZoneInfo("America/New_York")
LIVE_DEFAULTS = {
    "sym": "NQ", "tf": "5m", "poll_sec": 60, "adapter": "paper", "params": {}, "armed": False,
    "data_source": "yahoo",     # yahoo (free, ~10 min delayed) | tradovate (engine.tradovate.TradovateData, falls back to yahoo)
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
        self._blocked_entries = set()    # entry_t of engine entries we deliberately did not route
        self._flattened = set()          # entry_t of positions the clock-based safety flatten already closed
        self._restored = None

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
            return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
        df = pd.read_csv(path)
        # same hygiene as engine.data.load(): weekend/maintenance junk bars never reach the live engine either
        return df[~((df["high"] == df["low"]) & (df["volume"] <= 0))]

    def _fetch_recent(self, sym, interval, period="5d"):
        """Fresh bars from the configured data_source; tradovate falls back to yahoo (logged once per poll)."""
        src = self.cfg.get("data_source", "yahoo")
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

    def _merged(self, sym, tf, now, secs, period="5d"):
        """Stored history + fresh bars, cleaned. A failing fresh fetch degrades to history (never raises for that)."""
        hist = self.read_hist(sym, tf)
        try:
            recent = self.fetch_recent(sym, tf, period)
            if recent is None:
                recent = pd.DataFrame()
            self.health["fetch_ok"] = True
        except Exception as e:
            recent = pd.DataFrame()
            self.health["fetch_ok"] = False
            self._note_error(f"data refresh failed ({sym} {tf}): {e.__class__.__name__}: {e}")
        frames = [f for f in (hist, recent) if f is not None and len(f)]
        df = pd.concat(frames) if frames else pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
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
        if self.cfg["adapter"] != "paper" and not self.cfg.get("armed"):
            return {"ok": False, "error": "non-paper adapters must be explicitly armed (armed=true)"}
        if self.cfg["adapter"] not in ADAPTERS:
            return {"ok": False, "error": f"unknown adapter {self.cfg['adapter']}"}
        self.adapter = ADAPTERS[self.cfg["adapter"]](self.cfg)
        self.started_at = int(self.clock())
        self.health["data_source"] = self.cfg.get("data_source", "yahoo")
        self._restore(clear_kill=bool(cfg.get("clear_kill")))
        self.running = True
        self.stop_flag.clear()
        if spawn:
            self.thread = threading.Thread(target=self._loop, args=(self._gen,), daemon=True)
            self.thread.start()
        self._log("system", f"Bot started | {self.cfg['sym']} {self.cfg['tf']} | adapter={self.cfg['adapter']} | "
                            f"data={self.cfg['data_source']} | window={self.cfg['window_days']}d")
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
            self._route({"sym": self.cfg.get("sym", "NQ"), "side": "exit", "qty": pos.get("qty"), "reason": "KILL SWITCH",
                         "entry_t": pos.get("entry_t")})
            self._flattened.add(pos.get("entry_t"))
            self._open_routed = None
        self.stop()
        self._log("risk", "KILL SWITCH: flattened and stopped")
        self._save_state()
        return {"ok": True}

    def _route(self, action):
        if self.adapter is None:
            self.adapter = ADAPTERS["paper"](self.cfg)
        try:
            res = self.adapter.send(action)
        except Exception as e:  # never let a broker error kill the loop
            res = {"ok": False, "error": str(e)}
            self._note_error(f"adapter {getattr(self.adapter, 'name', '?')} send failed: {e}")
        self.ledger.append({"t": int(self.clock()), **action, "result": res})
        self._log("order", f"{action['side'].upper()} {action.get('qty', '')} {action['sym']} -> {res.get('ok')}", result=res)
        self._save_state()
        return res

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
                "open_routed": self._open_routed, "open_qty": self._open_qty, "blocked_entries": sorted(self._blocked_entries),
                "flattened": sorted(self._flattened),
                "seen": [list(k) for k in list(self.seen)[-2000:]], "ledger": self.ledger[-300:],
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
        if s.get("day") != today or s.get("sym") != self.cfg.get("sym") or s.get("tf") != self.cfg.get("tf"):
            self._log("system", f"Ignoring live_state.json from {s.get('day')} {s.get('sym')} {s.get('tf')} (today is {today})")
            return
        self.ledger = list(s.get("ledger") or [])
        self.seen = {tuple(k) for k in s.get("seen") or []}
        self._eod_sent = s.get("eod_sent")
        self._guard_key = s.get("guard_key")
        self._open_routed = s.get("open_routed")
        self._open_qty = s.get("open_qty")
        self._blocked_entries = set(s.get("blocked_entries") or [])
        self._flattened = set(s.get("flattened") or [])
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
        self._refresh_guard()
        df, drops = self._merged(sym, tf, now, secs)
        if len(df) == 0:
            raise RuntimeError("no bars available (history empty and refresh failed)")
        self.health["dropped"] = drops
        if drops["misaligned"] or drops["malformed"]:
            self._log("warn", f"dropped {drops['misaligned']} misaligned / {drops['malformed']} malformed bars from the feed")
        self._detect_revisions(df, secs)
        window_days = float(self.cfg.get("window_days") or 0)
        if window_days > 0:
            df = df[df["time"] >= df["time"].max() - window_days * 86400]
        # ---- freshness: age = seconds since the last closed bar's close
        last_close = int(df["time"].max()) + secs
        age = now - last_close
        stale = age > 2 * secs + 60
        mopen = market_open(now)
        et_mod = _et(now).hour * 60 + _et(now).minute
        params = merge_params({**self.cfg.get("params", {}), "live": True})
        self._params = params
        in_entry_window = any(a <= et_mod < z for a, z in params["entry_windows"])
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
        if block and not self.health["entries_blocked"]:
            self._log("risk", f"Feed stale for {self.health['stale_polls']} polls inside an entry window: NEW entries blocked "
                              "(open positions are still managed)")
        if not block and self.health["entries_blocked"]:
            self._log("system", "Feed recovered: new entries allowed again")
        self.health["entries_blocked"] = block
        base = from_frame(sym, tf, df)
        partner = self._partner(sym, tf, now, secs, int(df["time"].min()))
        htf = self._htf(sym, now)
        eng = Engine(base, htf=htf, partner=partner, params=params).run()
        res = eng.result()
        self.state = res["state"]
        self.last_poll = now
        self.bars_tail = base.to_records(max(0, len(base) - 400))
        self._emit_events(res, sym)
        self._eod_summary(res, sym, now)
        self._route_signals(res, sym, now, secs)
        self.health["poll_ms"] = int((time.perf_counter() - t0) * 1000)
        self.health["last_ok_poll"] = now
        self.health["ok"] = not (self.health["stale"] and mopen) and not self.health["desync"]
        self._save_state()
        return self.state

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
            rec = self.fetch_recent(sym, "1h", "5d")
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

    def _route_signals(self, res, sym, now, secs):
        """Turn the engine's position / completed trades into adapter calls, exactly once each."""
        start = self.started_at
        pos = self.state.get("position")
        late_after = 2 * secs + 60
        # desync: we routed an entry the engine no longer knows about (no open position, no completed trade with it)
        if self._open_routed is not None:
            known = (pos and pos.get("entry_t") == self._open_routed) or any(t["entry_t"] == self._open_routed for t in res["trades"])
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
            self._route({"sym": sym, "side": "exit", "qty": self._open_qty or pos.get("qty"), "reason": "TIME SAFETY",
                         "entry_t": self._open_routed})
            self._open_routed = None
        if pos and pos["entry_t"] >= start - secs and ("entry", pos["entry_t"]) not in self.seen:
            self.seen.add(("entry", pos["entry_t"]))
            age = now - (pos["entry_t"] + secs)
            if self.health["entries_blocked"]:
                self._blocked_entries.add(pos["entry_t"])
                self._log("risk", f"Entry at {_et(pos['entry_t']):%H:%M} ET NOT routed: feed stale")
            elif age > late_after:
                self._blocked_entries.add(pos["entry_t"])
                self._log("risk", f"Entry at {_et(pos['entry_t']):%H:%M} ET NOT routed: seen {age // 60} min late (restart / feed gap) - not chasing")
            else:
                self._open_routed = pos["entry_t"]
                self._open_qty = pos["qty"]
                self._route({"sym": sym, "side": "buy" if pos["dir"] == 1 else "sell", "qty": pos["qty"],
                             "stop": pos["stop"], "target": pos["target"], "entry": pos["entry"], "entry_t": pos["entry_t"]})
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
                if self._open_routed == tr["entry_t"]:
                    self._open_routed = None
                if self.cfg["adapter"] == "paper" or tr["exit_reason"] == "TIME":
                    # brackets handle stop/target at the broker; the bot only flattens on time exits
                    self._route({"sym": sym, "side": "exit", "qty": tr["qty"], "reason": tr["exit_reason"],
                                 "pnl": tr["pnl"], "entry_t": tr["entry_t"], "exit_t": tr["exit_t"]})
                if routed:
                    self._remember(tr, sym)      # every completed routed trade feeds the persistent memory

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
            self.stop_flag.wait(self.cfg.get("poll_sec", 60))

    def snapshot(self):
        return {"running": self.running, "cfg": {k: v for k, v in self.cfg.items() if k != "webhook_url"},
                "state": self.state, "log": list(self.log)[:200], "ledger": self.ledger[-100:],
                "last_poll": self.last_poll, "started_at": self.started_at, "errors": self.errors,
                "health": dict(self.health), "kill": self.kill,
                "day_pnl_routed": self.day_pnl_routed() if self.cfg else 0.0,
                "trades_today": self.trades_today() if self.cfg else 0,
                "bars": self.bars_tail}


BOT = LiveBot()
