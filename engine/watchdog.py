"""Unattended-run support: auto-resume record + in-process heartbeat watchdog.

Auto-resume record (data/autostart.json): {"cfg": <last successful /api/live/start body, secrets stripped>,
"saved_at": unix, "mode": "paper"|"demo"|"live"|"other"}. Written by /api/live/start, deleted by /api/live/stop and
/api/live/kill (an intentional stop stays stopped). On server start `decide_resume()` says whether to restart the bot.
Only paper and Tradovate DEMO resume automatically; anything that could place real orders (tradovate-live, the
generic "tradovate" adapter while TRADOVATE_ENV=live, TradersPost webhooks) never auto-resumes.

Watchdog: a daemon thread that every `interval_s` checks the bot and sends one alert per condition (rate-limited
to once per 30 min per condition) plus one "recovered" message when it clears:
  * poll_overdue  - bot running and the last successful poll is older than 3 x poll_sec
  * thread_dead   - bot marked running but its poll thread is not alive
  * stale_feed    - health.stale continuously for > 10 min during 09:00-16:00 ET on a weekday
It also drives engine.keepawake (keep the PC awake exactly while the bot runs).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import threading
import time
import traceback
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUTOSTART_PATH = os.path.join(ROOT, "data", "autostart.json")
MAX_AGE_S = 7 * 86400
ALERT_EVERY_S = 30 * 60
STALE_ALERT_S = 10 * 60
AUTO_MODES = ("paper", "demo")              # modes that may resume without a human
_SECRET_KEY = re.compile(r"(pass|secret|token|webhook|api_?key|confirm|phrase|^cid$|^sec$|clear_kill)", re.I)


# ---------------------------------------------------------------------- autostart record
def sanitize(cfg, phrases=()):
    """Copy of cfg without credential-like keys (recursive) and without any value equal to a confirm phrase."""
    if isinstance(cfg, dict):
        return {k: sanitize(v, phrases) for k, v in cfg.items()
                if not _SECRET_KEY.search(str(k)) and not (isinstance(v, str) and v.strip() in phrases)}
    if isinstance(cfg, list):
        return [sanitize(v, phrases) for v in cfg]
    return cfg


def mode_of(cfg: dict, tradovate_env: str = "demo") -> str:
    adapter = (cfg or {}).get("adapter", "paper")
    if adapter == "paper":
        return "paper"
    if adapter == "tradovate-demo":
        return "demo"
    if adapter == "tradovate":
        return "live" if (tradovate_env or "demo").lower() == "live" else "demo"
    if adapter == "tradovate-live":
        return "live"
    if adapter == "ninjatrader":             # NinjaTrader's own Sim101 / SimNNN accounts are demo; any other account is live
        from .ninjatrader import is_sim, resolve_account
        return "demo" if is_sim(resolve_account(cfg)) else "live"
    return "other"


def save(cfg: dict, tradovate_env: str = "demo", path: str = AUTOSTART_PATH, now: float | None = None, phrases=()) -> dict:
    rec = {"cfg": sanitize(dict(cfg or {}), phrases), "saved_at": int(now if now is not None else time.time()),
           "mode": mode_of(cfg, tradovate_env)}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=1)
    os.replace(tmp, path)
    return rec


def load(path: str = AUTOSTART_PATH):
    try:
        with open(path, encoding="utf-8") as f:
            rec = json.load(f)
        return rec if isinstance(rec, dict) else None
    except FileNotFoundError:
        return None
    except Exception:
        return {"_corrupt": True}


def clear(path: str = AUTOSTART_PATH) -> bool:
    try:
        os.remove(path)
        return True
    except FileNotFoundError:
        return False


def decide_resume(rec, now: float | None = None, tradovate_env: str = "demo") -> dict:
    """Pure decision: {"resume": bool, "cfg": dict|None, "mode": str|None, "reason": str}."""
    now = time.time() if now is None else now
    if not rec:
        return {"resume": False, "cfg": None, "mode": None, "reason": "no autostart record (last stop was intentional or never started)"}
    if rec.get("_corrupt") or not isinstance(rec.get("cfg"), dict):
        return {"resume": False, "cfg": None, "mode": None, "reason": "autostart record unreadable"}
    age = now - float(rec.get("saved_at") or 0)
    cfg = dict(rec["cfg"])
    mode = mode_of(cfg, tradovate_env)       # recomputed now: the env may have changed since the save
    if age > MAX_AGE_S or age < -300:
        return {"resume": False, "cfg": None, "mode": mode, "reason": f"autostart record is {age / 86400:.1f} days old (limit 7)"}
    if mode not in AUTO_MODES:
        return {"resume": False, "cfg": None, "mode": mode,
                "reason": f"adapter {cfg.get('adapter')} ({mode}) never auto-resumes: start it by hand"}
    cfg.pop("clear_kill", None)              # a kill flag restored from today's state must keep blocking
    return {"resume": True, "cfg": cfg, "mode": mode, "reason": f"resuming {mode} bot saved {age / 3600:.1f} h ago"}


# ---------------------------------------------------------------------- heartbeat
def _in_rth(now: float) -> bool:
    e = dt.datetime.fromtimestamp(now, ET)
    return e.weekday() < 5 and 9 * 60 <= e.hour * 60 + e.minute < 16 * 60


class Watchdog:
    def __init__(self, bot, send=None, clock=time.time, interval_s: float = 30.0, keepawake=None, log=print):
        self.bot = bot
        self.clock = clock
        self.interval_s = interval_s
        self.keepawake = keepawake
        self._send = send
        self._print = log
        self.server_started_at = int(clock())
        self.issues: list = []
        self._last_alert: dict = {}          # condition -> unix time of last alert
        self._active: set = set()
        self._stale_since = None
        self.last_check = None
        self.autostart_info: dict = {}
        self._thread = None
        self._stop = threading.Event()

    def alert(self, text: str):
        self._print(f"[watchdog] {time.strftime('%Y-%m-%d %H:%M:%S')} {text}")
        try:
            if self._send:
                self._send(text)
        except Exception as e:
            self._print(f"[watchdog] alert failed: {e}")

    def evaluate(self, now: float | None = None) -> list:
        """Return the list of current issues: [{"key", "text"}]. Pure apart from the stale timer."""
        now = self.clock() if now is None else now
        b = self.bot
        issues = []
        h = getattr(b, "health", {}) or {}
        if getattr(b, "running", False):
            poll_sec = float((getattr(b, "cfg", {}) or {}).get("poll_sec") or 60)
            last_ok = h.get("last_ok_poll") or getattr(b, "started_at", None) or now
            age = now - float(last_ok)
            if age > 3 * poll_sec:
                issues.append({"key": "poll_overdue", "text": f"no successful poll for {int(age)} s (poll_sec {int(poll_sec)}); "
                                                             f"last error: {h.get('last_error') or 'none'}"})
            th = getattr(b, "thread", None)
            if th is not None and not th.is_alive():
                issues.append({"key": "thread_dead", "text": "bot is marked running but its poll thread is dead"})
            if h.get("stale"):
                self._stale_since = self._stale_since or now
                if _in_rth(now) and now - self._stale_since > STALE_ALERT_S:
                    issues.append({"key": "stale_feed", "text": f"data feed stale for {int((now - self._stale_since) / 60)} min "
                                                               f"(data_age_s {h.get('data_age_s')})"})
            else:
                self._stale_since = None
        else:
            self._stale_since = None
        return issues

    def check(self, now: float | None = None) -> list:
        now = self.clock() if now is None else now
        issues = self.evaluate(now)
        keys = {i["key"] for i in issues}
        for i in issues:
            if now - self._last_alert.get(i["key"], 0) >= ALERT_EVERY_S:
                self._last_alert[i["key"]] = now
                self.alert(f"WATCHDOG: {i['text']}")
        for k in self._active - keys:
            if k in self._last_alert:
                self.alert(f"WATCHDOG recovered: {k}")
                self._last_alert.pop(k, None)
        self._active = keys
        self.issues = issues
        self.last_check = int(now)
        if self.keepawake is not None:
            self.keepawake.set(bool(getattr(self.bot, "running", False)))
        return issues

    def _run(self):
        while not self._stop.is_set():
            try:
                self.check()
            except Exception:
                traceback.print_exc()
            self._stop.wait(self.interval_s)

    def start(self):
        if self._thread is None or not self._thread.is_alive():
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="watchdog", daemon=True)
            self._thread.start()

    def status(self) -> dict:
        now = self.clock()
        return {"ok": not self.issues, "issues": self.issues, "server_started_at": self.server_started_at,
                "uptime_s": int(now - self.server_started_at), "last_check": self.last_check,
                "thread_alive": bool(self._thread and self._thread.is_alive()),
                "bot_running": bool(getattr(self.bot, "running", False)),
                "keepawake": self.keepawake.status() if self.keepawake is not None else None,
                "autostart": self.autostart_info}
