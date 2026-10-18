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

Data: Yahoo Finance futures quotes (free, may be delayed). For real-money execution use your broker's feed:
data_source "ninjatrader" reads the real CME bars NinjaTrader writes (ninjatrader/LE_BarFeed.cs), Yahoo as fallback.
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
                                # (LE_BarFeed CSVs, engine.ninjatrader.NinjaTraderBars); both fall back to yahoo
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
        self._nt_feed = None             # engine.ninjatrader.NinjaTraderBars for data_source "ninjatrader"
        self._nt_notes = {}              # rate limit for the ninjatrader feed notes: key -> (text, unix time logged)
        self._modify_gaveup = set()      # (entry_t, stop) the broker refused 3 times: not retried again
        self._week_prev = []             # LIT weekly stop: this ISO week's routed exits from earlier days (live_state.json)
        self._eval_prev = {}             # LIT safe_eval: routed P&L per earlier trading day of the eval (live_state.json)

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
        except Exception as e:
            df, why, full = None, f"{e.__class__.__name__}: {e}", False
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
        if cfg.get("data") and "data_source" not in cfg:
            self.cfg["data_source"] = cfg["data"]          # {"data": "ninjatrader"} is accepted as a short form
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
            qty = self._open_qty if self._open_routed == pos.get("entry_t") and self._open_qty else pos.get("qty")
            self._route({"sym": self.cfg.get("sym", "NQ"), "side": "exit", "qty": qty, "reason": "KILL SWITCH",
                         "entry_t": pos.get("entry_t")})
            self._flattened.add(pos.get("entry_t"))
            self._open_routed = None
        elif getattr(self.adapter, "kill_flattens_all", False):
            # broker adapters that can flatten the whole account (NinjaTrader FLATTENEVERYTHING) are told even when the
            # model shows no position: the broker may still hold one (desync, manual order, late fill)
            self._route({"sym": self.cfg.get("sym", "NQ"), "side": "exit", "reason": "KILL SWITCH", "entry_t": None})
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

    def _adapter_tick(self):
        """Adapters that manage broker orders between bars (NinjaTrader: late fill reports, bracket health, flat-time
        safety) get one tick() per poll, before the data fetch so a failing feed cannot skip it. Never raises."""
        ad = self.adapter
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
        if block and not self.health["entries_blocked"]:
            self._log("risk", f"Feed stale for {self.health['stale_polls']} polls inside an entry window: NEW entries blocked "
                              "(open positions are still managed)")
        if not block and self.health["entries_blocked"]:
            self._log("system", "Feed recovered: new entries allowed again")
        self.health["entries_blocked"] = block
        base = from_frame(sym, tf, df)
        if model == "lit":
            from . import lit_live
            df1 = self._lit_1m(sym, now, int(df_full["time"].min())) if lit_p.get("tf") == "1m" else None
            res = lit_live.run(df_full, lit_p, one_min=df1, now=now, sym=sym, week_hist=self.lit_week_hist())
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
        self.state["strategy"] = {"model": model, "label": lm.get("label", ""),
                                  "params": eng_params if model == "engine" else lit_p if model == "lit"
                                  else (self.cfg.get("model_params") or lm["params"])}
        # equity-curve filter: every finished signal goes into the shadow ledger; entries trade only while it's positive
        # (the real bot only: test harnesses run with their own state_path and must not touch the shared ledger)
        from . import equity_filter as _eqf
        self._eqf_cfg = lm.get("equity_filter") if self.state_path == STATE_PATH else None
        self._sizing_cfg = lm.get("sizing") if self.state_path == STATE_PATH else None   # late-entry size, fast-eval press
        self._lit_sizing = (self.cfg.get("lit_sizing") or lm.get("lit_sizing")) if model == "lit" else None   # normal/fast_eval/safe_eval
        self._live_params = lm.get("params") or {}
        if self._eqf_cfg:
            try:
                _eqf.record(res["trades"])
            except Exception as e:
                self._note_error(f"shadow ledger update failed: {e}")
        self.state["equity_filter"] = eqf = _eqf.status(self._eqf_cfg)
        if self.state_path == STATE_PATH:
            self._narrate_filter(eqf, lm)
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

    def _lit_1m(self, sym, now, t_min):
        """1m bars for LIT's entry (stored data/<sym>_1m.csv + fresh 1m, Yahoo caps 1m at 7 days). Never raises and never
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

    def eval_days(self):
        """Routed P&L per trading day of the eval (earlier days from live_state.json + today's ledger), from cfg eval_start."""
        start = str(self.cfg.get("eval_start") or "")
        days = {d: v for d, v in self._eval_prev.items() if not start or d >= start}
        today = trading_day(self.clock())
        days.pop(today, None)
        for r in self.ledger:
            if r.get("side") == "exit" and (not start or trading_day(r["t"]) >= start):
                d = trading_day(r["t"])
                days[d] = round(days.get(d, 0.0) + float(r.get("pnl") or 0), 2)
        return days

    def eval_room(self):
        """MFFU 50K room: eval balance minus the trailing max-loss floor (engine/sizing.mffu_eval)."""
        from . import sizing as _sz
        return _sz.mffu_eval(self.eval_days())["cushion"]

    def eval_profit(self):
        """The eval account's routed profit ($) since cfg eval_start (yyyy-mm-dd; default: everything in the ledger).
        Used by the fast-eval press (engine/sizing.py); None when the ledger is empty."""
        start = str(self.cfg.get("eval_start") or "")
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
                room = self.eval_room() if (lsz or {}).get("mode") in ("safe_eval", "eval") else None
                r = _sz.lit_qty(int(qty), pos or {}, lsz, room=room)
            else:
                r = _sz.route_qty(int(qty), pos or {}, mult, getattr(self, "_sizing_cfg", None), getattr(self, "_live_params", None),
                                  self.eval_profit() if getattr(self, "_sizing_cfg", None) and self._sizing_cfg.get("press") else None)
        except Exception as e:
            self._note_error(f"sizing failed, entry allowed at the engine's size: {e}")
            return qty
        if r["qty"] != qty:
            why = "; ".join(r["reasons"]) or st.get("reason", "")
            self._log("risk", f"Entry at {_et(entry_t):%H:%M} ET at {r['qty']} instead of {qty}: {why}")
        return r["qty"]

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
            elif not (q := self._equity_qty(pos["entry_t"], pos["qty"], pos)):
                self._blocked_entries.add(pos["entry_t"])
            else:
                self._open_routed = pos["entry_t"]
                self._open_qty = q
                d = 1 if pos["dir"] == 1 else -1
                rr = self._route({"sym": sym, "side": "buy" if d == 1 else "sell", "qty": q,
                                  "stop": tick_px(pos["stop"], d), "target": tick_px(pos["target"], d, target=True),
                                  "entry": pos["entry"], "entry_t": pos["entry_t"]})
                self._push_fill(pos, q, sym, rr)
        if pos and self._open_routed == pos.get("entry_t") and getattr(self.adapter, "route_stop_moves", False):
            self._route_stop_move(pos, sym)
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
                if self.cfg["adapter"] == "paper" or tr["exit_reason"] == "TIME" or getattr(self.adapter, "route_all_exits", False):
                    # brackets handle stop/target at the broker; the bot only flattens on time exits (adapters with
                    # route_all_exits also get TIME STOP / giveback / news exits, and a harmless sync flatten after a bracket fill)
                    self._route({"sym": sym, "side": "exit", "qty": qty, "reason": tr["exit_reason"],
                                 "pnl": round(tr["pnl"] * qty / tr["qty"], 2) if tr["qty"] else tr["pnl"],
                                 "entry_t": tr["entry_t"], "exit_t": tr["exit_t"]})
                if routed:
                    self._remember(tr, sym)      # every completed routed trade feeds the persistent memory
                    self._push_outcome(tr, qty, sym)

    # ------------------------------------------------------------------ phone notifications (engine/push.py, Web Push)
    def _push_src(self):
        """'PC paper' / 'PC NinjaTrader Sim' / 'PC Tradovate demo' ...: the same words the NinjaTrader adapter uses, so the
        adapter's real-fill notice and this one share a de-dup key."""
        name = str(self.cfg.get("adapter") or "paper")
        if name == "paper":
            return "PC paper"
        env = getattr(self.adapter, "env", None)
        if name == "ninjatrader":
            return f"PC NinjaTrader {'Sim' if env != 'live' else 'LIVE'}"
        return f"PC {name.capitalize()}{' ' + str(env) if env else ''}"

    def _push_model(self):
        m = ((self.state or {}).get("strategy") or {}).get("model") or self.cfg.get("model") or "engine"
        return "LIT" if m == "lit" else "Engine" if m == "engine" else str(m)

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
        try:
            from . import push
            res = res or {}
            if getattr(self.adapter, "reports_fills", False):
                return                      # NinjaTrader: the adapter notifies the real fill (and its own problems)
            if res.get("ok") is False:
                self._push_send(push.text_payload(self._push_src(), "risk", f"{self._push_model()} entry NOT placed",
                                                  f"{'LONG' if pos.get('dir') == 1 else 'SHORT'} {qty} @ {float(pos.get('entry') or 0):,.2f}: "
                                                  f"{str(res.get('error') or 'refused')[:300]}", key=f"refused:{int(pos['entry_t'])}"))
                return
            name = str(self.cfg.get("adapter") or "paper")
            why = "; ".join(pos.get("size_why") or [])
            self._push_send(push.fill_payload(
                self._push_src(), sym, "LONG" if pos.get("dir") == 1 else "SHORT", qty, pos.get("entry"), pos.get("stop0", pos.get("stop")),
                pos.get("target"), pos["entry_t"], risk_pts=pos.get("risk_pts"), model=self._push_model(),
                setup=" · ".join(x for x in (f"target {pos['target_label']}" if pos.get("target_label") else "",
                                             "" if name == "paper" else f"order sent to {name} (fill not confirmed by it)") if x),
                note=f"Size: {why}" if why else ""))
        except Exception as e:
            self._log("warn", f"phone notification failed: {e.__class__.__name__}")

    def _push_outcome(self, tr, qty, sym):
        try:
            from . import push
            from . import sizing as _sz
            ev = _sz.mffu_eval(self.eval_days()) if self.cfg.get("eval_start") else None
            usd = float(tr.get("pnl") or 0) * qty / tr["qty"] if tr.get("qty") else float(tr.get("pnl") or 0)
            self._push_send(push.outcome_payload(
                self._push_src(), sym, "LONG" if tr.get("dir") == 1 else "SHORT", tr.get("exit_reason"), tr.get("pnl_r"), usd,
                tr["entry_t"], tr.get("exit_t"), qty=qty, balance=ev["balance"] if ev else None, to_target=ev["to_target"] if ev else None,
                model=self._push_model()))
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
