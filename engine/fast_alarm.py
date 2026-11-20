"""Fast alarm (night-nqlive 2026-11-20, owner: "the live bot must take EVERY trade the backtest takes"): a phone push within
2 minutes when the PC bot is ON a real or Sim account in the entry hours but cannot take a trade.

Why: since 2026-11-18 ("important only") the in-process watchdog's alerts (engine/watchdog.py, kind "system") and the execution
audit's "Missed trade" notices (engine/fill_audit, kind "pc") stop at engine/push.pc_app_ok, so a stalled poll loop or a dead
feed in the entry hours reached the phone only through the 15-minute report (tools/pc_report.py conditions), up to ~15 minutes
later; LIT's entry is not chased after 90 s (engine/live.LIT_MAX_LATE_S), so one such gap is one lost trade.

Conditions (each one push when it starts, one "back to normal" when it clears; the 15-minute report then skips its own copy of
the same condition: engine/notify.problem_dup):
  bot_down    the bot is running but no good poll for over POLL_LIMIT_S (90 s; a normal gap is <= ~32 s: polls at +2 s and
              +32 s each minute; a PC whose last poll itself took long gets 1.5 x that + 35 s), or its poll thread is dead.
              Report condition "bot_down".
  feed_stale  polls are fine but the NinjaTrader 1-minute feed is behind: the newest 1m bar is over FEED_LIMIT_S (120 s = two
              bars) old, or the bot itself blocked new entries for a stale feed (health feed_block). Report "feed_stale".
  bot_stopped the bot is NOT running although data/autostart.json says it was (Stop / kill clear that file) and this server
              started over 3 min ago: a restart that did not resume (no auto-resume, NinjaTrader not connected). Report
              "bot_stopped". (The server's own "bot NOT resumed" alert is kind "system": since 2026-11-18 not on the phone.)
Only while: LE_FAST_ALARM is not "0", notify_settings.json "problems" is on (IMPORTANT, default on), the bot runs on a broker
adapter (not paper), a weekday 01:58-15:55 ET (LIT's 02:00-15:30 entry window + its 15:55 flat, ATLAS's windows inside it),
CME Globex open (engine/live.market_open: holidays / early halts excluded), and the bot started over START_GRACE_S ago.
Delivery: engine/notify.instant_problem (the private ntfy alert topic, high priority, rings in quiet hours).
Read-only: never starts, stops, arms, routes or sizes anything; it reads bot.health / bot.running / bot.cfg only.
Driven by engine/watchdog.Watchdog.check (every 30 s, server.py) -> worst case ~2 minutes from the last good poll / bar.
Tests: python -X utf8 -m tests.test_fast_alarm
"""
from __future__ import annotations

import datetime as dt
import os
import time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
POLL_LIMIT_S = 90
FEED_LIMIT_S = 120
START_GRACE_S = 180
WIN_FROM, WIN_TO = 1 * 60 + 58, 15 * 60 + 55          # ET minutes, weekdays
COND = {"bot_down": "bot_down", "feed_stale": "feed_stale", "bot_stopped": "bot_stopped"}   # -> tools/pc_report.py condition code
TITLE = {"bot_down": "ZEUS not polling", "feed_stale": "FEED STALE", "bot_stopped": "Bot stopped"}


def enabled(env=None) -> bool:
    e = os.environ if env is None else env
    return str(e.get("LE_FAST_ALARM", "1")).strip() != "0"


def in_hours(now) -> bool:
    e = dt.datetime.fromtimestamp(float(now), ET)
    m = e.hour * 60 + e.minute
    if e.weekday() >= 5 or not (WIN_FROM <= m < WIN_TO):
        return False
    try:
        from .live import market_open
        return bool(market_open(now))
    except Exception:
        return True


def _span(s) -> str:
    s = int(max(0, s))
    return f"{s} s" if s < 120 else f"{s // 60} min"


def evaluate(bot, now, server_started_at=None, autostart=None) -> dict:
    """{code: text} of what stops the bot from taking a trade right now (empty outside the hours / for a paper bot). Pure.
    server_started_at / autostart (engine/watchdog: this server's start, data/autostart.json = the bot was running and nobody
    pressed Stop / kill since): a bot that is NOT running in the entry hours although it should be -> "bot_stopped"."""
    out: dict = {}
    if bot is None:
        return out
    if not getattr(bot, "running", False):
        rec = autostart if isinstance(autostart, dict) else None
        acfg = (rec or {}).get("cfg") if isinstance((rec or {}).get("cfg"), dict) else None
        if acfg and str(acfg.get("adapter") or "paper") != "paper" and in_hours(now) and server_started_at \
                and now - float(server_started_at) >= START_GRACE_S:
            out["bot_stopped"] = ("The bot is stopped in the entry hours, although it was running and nobody pressed Stop: it "
                                  "cannot take a trade (a restart that did not resume, or NinjaTrader not connected). On the "
                                  "PC: GO_LIVE_EVAL.bat (you type the phrase).")
        return out
    cfg = getattr(bot, "cfg", None) or {}
    if str(cfg.get("adapter") or "paper") == "paper" or not in_hours(now):
        return out
    started = float(getattr(bot, "started_at", None) or 0)
    if not started or now - started < START_GRACE_S:
        return out
    h = getattr(bot, "health", None) or {}
    last_ok = float(h.get("last_ok_poll") or started)
    age = now - last_ok
    th = getattr(bot, "thread", None)
    dead = th is not None and hasattr(th, "is_alive") and not th.is_alive()
    try:                                  # a slow PC poll (its own last duration) is not a stuck one: the limit grows with it
        limit = max(float(POLL_LIMIT_S), 1.5 * float(h.get("poll_ms") or 0) / 1000.0 + 35.0)
    except (TypeError, ValueError):
        limit = float(POLL_LIMIT_S)
    if dead or age > limit:
        err = str(h.get("last_error") or "")[:120]
        out["bot_down"] = (("The bot's poll thread stopped" if dead else f"No good poll for {_span(age)}")
                           + " while it is on in the entry hours: it cannot take a trade."
                           + (f" Last error: {err}." if err else "")
                           + " Open the PC: if it stays, STOP BOT, then GO_LIVE_EVAL.bat (you type the phrase).")
        return out
    fb = h.get("feed_block")
    last1 = h.get("last_1m_bar_t")
    age1 = (now - (float(last1) + 60.0)) if last1 else None
    if fb or (age1 is not None and age1 > FEED_LIMIT_S):
        out["feed_stale"] = ("FEED STALE: " + (f"the newest NinjaTrader 1-minute bar is {_span(age1)} old" if age1 is not None
                                                else "NinjaTrader bars missing")
                             + (f" ({str(fb)[:80]})" if fb else "")
                             + ": the bot cannot take a new entry. Check NinjaTrader is connected; re-add LE_BarFeed on the "
                               "MNQ 5-minute chart if it stays.")
    return out


class FastAlarm:
    """One push per condition when it starts and one when it clears (the watchdog calls step() every 30 s)."""

    def __init__(self, send=None, clock=time.time):
        self.clock = clock
        self._send = send                      # tests: send(payload) -> "sent" | why
        self.active: dict = {}                 # code -> {"since", "key", "sent"}
        self.last: dict = {}

    def send(self, p: dict) -> str:
        try:
            if self._send is not None:
                return self._send(p)
            from . import notify
            return notify.instant_problem(p)
        except Exception as e:
            return f"failed: {e.__class__.__name__}"

    def step(self, bot, now=None, server_started_at=None, autostart=None) -> list:
        """Evaluate and push what changed. -> [(key, result)]. Never raises."""
        now = float(self.clock() if now is None else now)
        done = []
        try:
            if not enabled():
                return done
            cur = evaluate(bot, now, server_started_at, autostart)
            for code, text in cur.items():
                a = self.active.get(code)
                if a is None:
                    key = f"fast:{code}:{int(now)}"
                    r = self.send({"key": key, "code": code, "cond": COND[code], "title": TITLE[code], "body": text})
                    self.active[code] = {"since": int(now), "key": key, "sent": r == "sent"}
                    done.append((key, r))
            for code in [c for c in self.active if c not in cur]:
                a = self.active.pop(code)
                if a.get("sent"):
                    key = f"fast:{code}:back:{int(now)}"
                    r = self.send({"key": key, "code": code, "cond": COND[code], "back": True, "title": "Back to normal",
                                   "body": {"bot_down": "The bot polls again.", "bot_stopped": "The bot runs again."}.get(
                                       code, "NinjaTrader bars are fresh again.")
                                   + f" It was out for {_span(now - a['since'])}.", "tags": "white_check_mark"})
                    done.append((key, r))
            self.last = {"t": int(now), "active": sorted(self.active), "sent": done[-4:]}
        except Exception as e:
            self.last = {"t": int(now), "error": f"{e.__class__.__name__}: {e}"}
        return done
