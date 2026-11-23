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
No storm (redteam 2026-11-20): a condition that starts again within REPEAT_S of its last push stays silent (a flapping feed is
one alarm, not one every minute) unless it stays PERSIST_S (5 min: not a blip, after a "back to normal" the owner must hear it
again) or is still there REPEAT_S after that push; at most DAY_MAX alarm pushes an ET day (each
with its one "back to normal"), so a bad night can never use up ntfy's daily room that the trade alerts need. A silent one is
still in the 15-minute report (its own condition, not skipped as a duplicate).
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
REPEAT_S = 30 * 60                                    # the same condition again within this of its last push: no new push
DAY_MAX = 6                                           # alarm pushes (starts) an ET day at most
PERSIST_S = 5 * 60                                    # a held repeat that lasts this long is pushed anyway (not a blip)
WIN_FROM, WIN_TO = 1 * 60 + 58, 15 * 60 + 55          # ET minutes, weekdays
COND = {"bot_down": "bot_down", "feed_stale": "feed_stale", "bot_stopped": "bot_stopped", "halt_open": "halt_open",
        "no_stop": "no_stop"}   # -> pc_report code
TITLE = {"bot_down": "ZEUS not polling", "feed_stale": "FEED STALE", "bot_stopped": "Bot stopped",
         "halt_open": "CLOSE THE TRADE NOW", "no_stop": "TRADE HAS NO STOP"}
NO_STOP_AGE_S = 60                                    # the state file's open leg is this old with the bot stopped
# redteam2 2026-11-20: a CME half day (Thanksgiving 11-26 halt 13:00, 11-27 and 12-24 13:15 ET). MFFU does NOT auto-close at a
# half-day halt ("the trader is responsible for closing the positions ... failure ... will result in breaching", help center
# 'Permitted Times to Trade'); the adapter's own flat (halt - 5 min) only runs while the bot runs. A STOP, a crash / restart
# that did not resume, or a refused CLOSEPOSITION leaves the broker position open into the halt = the account fails.
HALT_WARN_MIN = 10                                    # bot NOT running: warn from halt - 10 min
HALT_LATE_MIN = 4                                     # bot running: its own flat is at halt - 5; still open at halt - 4 = warn


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


def _real_positions(folder) -> list:
    """["SHORT 2 MNQ 12-26 on <acct ..1234>"] for every non-FLAT NinjaTrader position file of a NON-Sim account (outgoing/
    <instrument>_<account>_Position.txt). Read-only, never raises."""
    out = []
    try:
        from .ninjatrader import is_sim, parse_position
        og = os.path.join(folder, "outgoing")
        for n in sorted(os.listdir(og)):
            if not n.lower().endswith("_position.txt"):
                continue
            parts = n[:-len("_position.txt")].rsplit("_", 1)
            if len(parts) != 2 or not parts[0] or is_sim(parts[1]):
                continue
            try:
                with open(os.path.join(og, n), encoding="utf-8-sig", errors="replace") as fh:
                    pos = parse_position(fh.read())
            except OSError:
                continue
            if pos and pos["side"] != "FLAT":
                out.append(f"{pos['side']} {pos['qty']} {parts[0]} on account ..{parts[1][-4:]}")
    except Exception:
        pass
    return out


def no_stop(bot, now, folder=None, state_dir=None) -> str | None:
    """redteam2 2026-11-20: the bot is NOT running and a state file of its NinjaTrader adapters (data/ninjatrader_state*.json:
    LIT, ATLAS, account C, the extra accounts, the Rapid lanes) holds a leg whose entry went out but whose stop / target was
    never placed ("entry_sent" / "pending" / "unprotected"), while NinjaTrader shows that real account in a position: a crash /
    restart between the entry fill and the bracket that did not resume (an eval without auto-resume) = a trade with NO stop at
    the broker. The restarted adapter places the bracket only once the bot runs again. Read-only, never raises."""
    try:
        if getattr(bot, "running", False):
            return None
        import glob
        import json
        from . import ninjatrader as NT
        sd = state_dir or os.path.dirname(NT.STATE_PATH)
        if folder is None:
            folder = (getattr(bot, "cfg", None) or {}).get("nt_folder") or NT.default_folder()
        og = os.path.join(folder, "outgoing")
        out = []
        for p in sorted(glob.glob(os.path.join(sd, "ninjatrader_state*.json"))):
            if "simcheck" in os.path.basename(p):
                continue
            try:
                with open(p, encoding="utf-8") as fh:
                    st = json.load(fh)
            except Exception:
                continue
            acct = str((st or {}).get("account") or "")
            if not acct or NT.is_sim(acct) or st.get("day") != NT._trading_day(now):
                continue                               # another day's file: the adapter itself ignores it
            for lg in st.get("legs") or []:
                if not isinstance(lg, dict) or lg.get("status") not in ("entry_sent", "pending", "unprotected"):
                    continue
                if now - float(lg.get("sent_at") or st.get("saved_at") or now) < NO_STOP_AGE_S:
                    continue
                inst = str(lg.get("instrument") or "")
                suffix = f"_{acct.lower()}_position.txt"
                try:
                    names = [n for n in os.listdir(og) if n.lower().endswith(suffix)]
                except OSError:
                    names = []
                for n in names:
                    if not NT.same_instrument(n[:-len(suffix)], inst):
                        continue
                    try:
                        with open(os.path.join(og, n), encoding="utf-8-sig", errors="replace") as fh:
                            pos = NT.parse_position(fh.read())
                    except OSError:
                        pos = None
                    if pos and pos["side"] != "FLAT":
                        out.append(f"{pos['side']} {pos['qty']} {inst} on account ..{acct[-4:]}")
        if not out:
            return None
        return ("The bot is stopped and " + "; ".join(out[:3]) + " has NO stop or target at the broker (the PC restarted between "
                "the entry and its bracket). Start the bot (tools/bat/GO_LIVE_EVAL.bat: it places the stop at once) or close the trade in "
                "NinjaTrader now.")
    except Exception:
        return None


def halt_open(bot, now, folder=None) -> str | None:
    """A broker position still open just before a CME early close (see HALT_WARN_MIN), else None. Only inside the last
    HALT_WARN_MIN minutes before the halt of an early-close day (3 days a year here: no file read at any other time)."""
    try:
        from . import cme_calendar as C
        e = dt.datetime.fromtimestamp(float(now), ET)
        if e.weekday() >= 5 or e.hour >= 18:
            return None
        ec = C.early_close(e.date())
        m = e.hour * 60 + e.minute
        if ec is None or not (ec - HALT_WARN_MIN <= m < ec):
            return None
        running = bool(getattr(bot, "running", False))
        if running and m < ec - HALT_LATE_MIN:
            return None                                # the running bot flattens at halt - 5 itself
        if folder is None:
            folder = (getattr(bot, "cfg", None) or {}).get("nt_folder")
        if not folder:
            from .ninjatrader import default_folder
            folder = default_folder()
        pos = _real_positions(folder)
        if not pos:
            return None
        return (f"CME closes early today at {ec // 60:02d}:{ec % 60:02d} ET and MFFU does NOT close trades on a half day: "
                f"{'; '.join(pos[:3])} is still open" + ("" if running else " and the bot is stopped")
                + ". Close it in NinjaTrader NOW (right-click the position > Close), or the account fails at the halt.")
    except Exception:
        return None


def _halt_passed(now) -> bool:
    try:
        from . import cme_calendar as C
        e = dt.datetime.fromtimestamp(float(now), ET)
        ec = C.early_close(e.date())
        return ec is not None and e.hour * 60 + e.minute >= ec
    except Exception:
        return True


def evaluate(bot, now, server_started_at=None, autostart=None, run_seen=None) -> dict:
    """{code: text} of what stops the bot from taking a trade right now (empty outside the hours / for a paper bot). Pure.
    server_started_at / autostart (engine/watchdog: this server's start, data/autostart.json = the bot was running and nobody
    pressed Stop / kill since): a bot that is NOT running in the entry hours although it should be -> "bot_stopped"."""
    out: dict = {}
    if bot is None:
        return out
    ho = halt_open(bot, now)
    if ho:
        out["halt_open"] = ho                          # whatever else is wrong: this one costs the account
    ns = no_stop(bot, now)
    if ns:
        out["no_stop"] = ns
    if not getattr(bot, "running", False):
        rec = autostart if isinstance(autostart, dict) else None
        acfg = (rec or {}).get("cfg") if isinstance((rec or {}).get("cfg"), dict) else None
        if acfg and str(acfg.get("adapter") or "paper") != "paper" and in_hours(now) and server_started_at \
                and now - float(server_started_at) >= START_GRACE_S:
            out["bot_stopped"] = ("The bot is stopped in the entry hours, although it was running and nobody pressed Stop: it "
                                  "cannot take a trade (a restart that did not resume, or NinjaTrader not connected). On the "
                                  "PC: tools/bat/GO_LIVE_EVAL.bat (you type the phrase).")
        return out
    cfg = getattr(bot, "cfg", None) or {}
    if str(cfg.get("adapter") or "paper") == "paper" or not in_hours(now):
        return out
    started = float(getattr(bot, "started_at", None) or 0)
    if run_seen:
        # redteam 2026-11-20: LiveBot.started_at is the trading day's FIRST start (min with the restored state) and
        # health.last_ok_poll survives a STOP: a START / Re-arm / server restart in the entry hours read "no good poll for
        # 3 h" before its first poll. The grace and the age count from when this run was first seen running.
        started = max(started, float(run_seen))
    if not started or now - started < START_GRACE_S:
        return out
    h = getattr(bot, "health", None) or {}
    last_ok = max(float(h.get("last_ok_poll") or 0), started)
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
                           + " Open the PC: if it stays, STOP BOT, then tools/bat/GO_LIVE_EVAL.bat (you type the phrase).")
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
        self.active: dict = {}                 # code -> {"since", "key", "sent", "held"}
        self.last: dict = {}
        self.pushed: dict = {}                 # code -> time of its last start push (REPEAT_S)
        self.run_seen = None                   # when the bot was first seen running in this run (a START / restart resets it)
        self._was_running = False
        self.day_n: dict = {}                  # ET day -> start pushes that day (DAY_MAX)

    def _may_push(self, code, now, since=None) -> str | None:
        """None = this start may go to the phone; else why it stays silent (rate limits). since: when this (held) occurrence
        began: one that lasted PERSIST_S is not a blip and goes out despite the repeat wait (never past DAY_MAX)."""
        lp = self.pushed.get(code)
        if lp is not None and now - lp < REPEAT_S and not (since is not None and now - float(since) >= PERSIST_S):
            return f"held: {code} pushed {_span(now - lp)} ago"
        day = dt.datetime.fromtimestamp(float(now), ET).date().isoformat()
        if int(self.day_n.get(day) or 0) >= DAY_MAX and code not in ("halt_open", "no_stop"):   # the account: never capped
            return f"held: {DAY_MAX} alarm pushes today already"
        return None

    def _start(self, code, text, now, since=None) -> tuple:
        key = f"fast:{code}:{int(now)}"
        held = self._may_push(code, now, since)
        if held:
            return key, held
        r = self.send({"key": key, "code": code, "cond": COND[code], "title": TITLE[code], "body": text})
        if r == "sent":
            self.pushed[code] = float(now)
            day = dt.datetime.fromtimestamp(float(now), ET).date().isoformat()
            self.day_n = {d: n for d, n in self.day_n.items() if d >= day} | {day: int(self.day_n.get(day) or 0) + 1}
        return key, r

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
            running = bool(getattr(bot, "running", False))
            if running and not self._was_running:
                self.run_seen = now
            self._was_running = running
            cur = evaluate(bot, now, server_started_at, autostart, run_seen=self.run_seen if running else None)
            for code, text in cur.items():
                a = self.active.get(code)
                if a is None or (a.get("held") and not a.get("sent") and self._may_push(code, now, a.get("since")) is None):
                    key, r = self._start(code, text, now, a.get("since") if a else None)   # new, or a held one that lasted
                    self.active[code] = {"since": int(a["since"]) if a else int(now), "key": key, "sent": r == "sent",
                                         "held": str(r).startswith("held")}
                    done.append((key, r))
            for code in [c for c in self.active if c not in cur]:
                a = self.active.pop(code)
                if code == "halt_open" and (not a.get("sent") or _halt_passed(now)):
                    continue                           # the halt came: "back to normal" would read as "it is closed"
                if a.get("sent") and code in ("bot_down", "feed_stale") and not running:
                    # cleared because the bot was STOPPED (the owner's STOP / kill, often his answer to this alarm): never a
                    # "Back to normal: the bot polls again" (redteam 2026-11-20); a stop that should not be is "Bot stopped"
                    continue
                if a.get("sent"):
                    key = f"fast:{code}:back:{int(now)}"
                    r = self.send({"key": key, "code": code, "cond": COND[code], "back": True, "title": "Back to normal",
                                   "body": {"bot_down": "The bot polls again.", "bot_stopped": "The bot runs again.",
                                            "halt_open": "NinjaTrader shows the account flat before the halt.",
                                            "no_stop": "The bot runs again (it places the stop at its first poll) or the trade is closed."}.get(
                                       code, "NinjaTrader bars are fresh again.")
                                   + f" It was out for {_span(now - a['since'])}.", "tags": "white_check_mark"})
                    done.append((key, r))
            self.last = {"t": int(now), "active": sorted(self.active), "sent": done[-4:]}
        except Exception as e:
            self.last = {"t": int(now), "error": f"{e.__class__.__name__}: {e}"}
        return done
