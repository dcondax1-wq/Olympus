"""Telegram commands to the PC bot (day-handsfree 2026-11-25; owner: "I don't want to go on my PC and restart it every single
time ... I want an easier process").

The owner already has a Telegram bot for alerts (ALERTS_SETUP.bat -> %USERPROFILE%\\.olympus\\alerts.json, engine/alert_bus). Since
today a reply to that bot is read too: the PC asks Telegram for new messages (getUpdates, short poll, every POLL_S) and runs an
ALLOW-LISTED command through the SAME path as the phone's control branch (engine/remote_ctl.RemoteControl: every gate holds:
flat, outside 01:50-16:00 ET on a weekday for update / restart, LE_SUPERVISED, each id once, 15-minute age). The receipt is a
Telegram reply to the owner's message.

  /status            the bot's status (accounts, armed, open trade, today's $)
  /today             where are we: every account's $ / today / to pass / $ left before the floor or daily limit, the funded
                     payout state, the open trade, the LIT setup, today's + tomorrow's big news (engine/today_brief; read-only,
                     answered here, never through the control path)
                       + the payouts (engine/payout_engine, READ-ONLY): per funded account "request today" or the next one's $ and
                     date, the buffer to keep and what blocks it (big-payout 2026-11-26; it never requests a payout)
  /update            the auto-update now (parks a blocking hand edit with git stash; strategy / account files are not parked)
  /update force      the same, and ALSO parks the strategy / account / rule files that block it (git stash: nothing is lost,
                     'git stash list' / 'git stash pop' bring it back). Only ever sent by the owner after a "Bot update stuck" push.
  /restart           restart the server (an opted-in eval comes back armed through engine/autoresume)
  /pause [HH:MM | tomorrow | YYYY-MM-DD]   no NEW entries until then (default: tomorrow); an open trade keeps its stop / target
  /resume            lift the pause
  /oflane on|off|status   the order-flow lane on a NinjaTrader SIMULATION account (engine/of_lane; night-of-lane-ready
                     2026-11-27): on = the switch for Sim102 (or Sim101 when Sim102 is missing and Sim101 is free) + today's paper
                     stats, off = off, status = account, today's trades, the forward ladder step. Answered here (never the control
                     path); a real / MFFU account is always refused (it takes no account name at all)
  /preview           one example of each alert style (day-tgpretty: short, emoji first) + an example chart picture. Answered here,
                     read-only, examples only (no account, no trade)
  /insta [YYYY-MM-DD]   day-insta: re-send a green day's Insta card (1080 x 1350, engine/insta_card; default: the newest one).
                     Read-only, answered here
  /help              this list

Never accepted from Telegram: kill, stop, flatten, start, add_account, switch, arming, anything about sizing or strategy. Unknown
text gets the /help list back. Who: ONLY the configured owner chat (alerts.json chat_id), and only a PRIVATE chat with the owner
himself (chat.type "private", chat.id == from.id == chat_id). A group / channel chat id turns commands off (the alerts still go).
Anyone else's message is dropped without a reply (a stranger learns nothing); the count rides in status().

State: data/tg_cmd.json (gitignored): the getUpdates offset, the last poll result. Off: LE_TG_CMD=0. Nothing here places an order.
"""
from __future__ import annotations

import json
import os
import re
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(ROOT, "data", "tg_cmd.json")          # gitignored
POLL_S = 15.0
BACK_AFTER_S = 90.0                     # the "PC is back up" receipt after a /restart or /update: this long after the server start
BACK_MAX_S = 30 * 60                    # ... for a command at most this old
MAX_TEXT = 80
ALLOW = ("status", "today", "update", "restart", "pause", "resume", "help", "preview", "insta")
TO_CMD = {"status": "status", "update": "update", "restart": "restart", "pause": "pause", "resume": "resume_entries"}
REFUSED_WORDS = ("kill", "stop", "flatten", "start", "arm", "add_account", "switch", "present", "buy", "sell", "long", "short")
PAUSE_ARG = re.compile(r"^(tomorrow|\d{1,2}:\d{2}|\d{4}-\d{2}-\d{2})$")
HELP = ("PC commands (reply here):\n/status - how the bot is doing\n/oflane on|off|status - order flow on the practice (Sim) "
        "account, no real money\n/today - where are we: accounts, $ today, $ left, payouts, open trade, "
        "setup, news\n/update - install the newest code now (outside 01:50-16:00 ET, "
        "flat)\n/restart - restart the PC server (your eval comes back armed by itself)\n/pause [HH:MM|tomorrow] - no new entries "
        "until then\n/resume - lift the pause\n/preview - one example of each alert style\n/insta [YYYY-MM-DD] - a green day's Insta card again\nTrading, arming, stop and flatten are never done from Telegram.")


def enabled(env=None) -> bool:
    e = os.environ if env is None else env
    return str(e.get("LE_TG_CMD", "1")).strip().lower() not in ("0", "off", "false")


def owner_chat(cfg: dict | None) -> str | None:
    """The owner's private chat id from engine/alert_bus.config, or None (no Telegram / a group or channel chat)."""
    tg = (cfg or {}).get("telegram") or {}
    chat = str(tg.get("chat_id") or "").strip()
    return chat if re.fullmatch(r"\d{1,20}", chat) else None   # a negative id = a group / channel: commands off


def is_owner(msg: dict, chat: str | None) -> bool:
    if not chat or not isinstance(msg, dict):
        return False
    c, f = msg.get("chat") or {}, msg.get("from") or {}
    # red team 2026-11-25: a FORWARDED message (or one sent through an inline bot) carries the owner as `from` but someone else's
    # words: never a command (a forwarded "/update force" from anyone would otherwise run)
    if any(msg.get(k) for k in ("forward_origin", "forward_from", "forward_from_chat", "forward_sender_name", "forward_date",
                                 "via_bot", "is_automatic_forward")):
        return False
    return (str(c.get("type")) == "private" and str(c.get("id")) == chat and str(f.get("id")) == chat
            and not f.get("is_bot"))


def parse_text(text: str) -> tuple:
    """(command dict | None, reply text | None). The dict has cmd (+ until / force); never an id / ts (the caller adds them)."""
    t = str(text or "").strip()[:MAX_TEXT]
    if not t:
        return None, None
    words = t.split()
    head = words[0].lower().lstrip("/")
    head = head.split("@", 1)[0]                              # /status@MyBot in a chat with several bots
    args = [w.lower() for w in words[1:]]
    if head in ("help", "start", "commands") and len(words) == 1:   # Telegram's own /start opens a chat: answer with the list
        return None, HELP
    if head == "oflane":
        if len(args) > 1 or (args and args[0] not in ("on", "off", "status")):
            return None, ("/oflane takes on, off or status. The account is chosen for you (Sim102, or Sim101 when it is free): "
                          "a real or MFFU account is never used.")
        return {"cmd": "oflane", "arg": args[0] if args else "status"}, None
    if head not in ALLOW:
        if head in REFUSED_WORDS:
            return None, f"'{head}' is never done from Telegram (only /status /update /restart /pause /resume)."
        return None, "Not a command I take. " + HELP
    if head == "help":
        return None, HELP
    if head == "today":
        if args:
            return None, "/today takes no words after it."
        return {"cmd": "today"}, None
    if head == "insta":
        if len(args) > 1 or (args and not re.match(r"^\d{4}-\d{2}-\d{2}$", args[0])):
            return None, "/insta takes nothing (the newest card) or a day: /insta 2026-11-27"
        return {"cmd": "insta", "day": args[0] if args else None}, None
    if head == "preview":
        if args:
            return None, "/preview takes no words after it."
        return {"cmd": "preview"}, None
    c = {"cmd": TO_CMD[head]}
    if head == "pause":
        until = args[0] if args else "tomorrow"
        if not PAUSE_ARG.match(until) or len(args) > 1:
            return None, "pause takes one of: HH:MM (ET), tomorrow, YYYY-MM-DD. Example: /pause 14:00"
        c["until"] = until
    elif head == "update":
        if args == ["force"]:
            c["force"] = True
        elif args:
            return None, "update takes nothing, or 'force' (also parks strategy / account files): /update or /update force"
    elif args:
        return None, f"/{head} takes no words after it."
    return c, None


def oflane_reply(arg: str, root: str | None = None, now=None) -> str:
    """/oflane on|off|status (engine/of_lane.tg_text: simulation accounts only). Never raises."""
    try:
        from . import of_lane
        return of_lane.tg_text(arg, root or of_lane.ROOT, now)[:3500]
    except Exception as e:  # noqa: BLE001
        return f"/oflane: error {e.__class__.__name__} (nothing was changed)."


def today_text() -> str:
    """/today: the payout plan in plain words (engine/payout_engine.today_line). Never raises."""
    try:
        from . import payout_engine
        return payout_engine.today_line()[:3500]
    except Exception as e:  # noqa: BLE001
        return f"Payouts: could not read the accounts ({e.__class__.__name__})."


def today_reply(now, live_fn=None) -> str:
    """/today's text (engine/today_brief) from the server's own live view (live_fn() for tests). Never raises."""
    try:
        from . import today_brief
        if live_fn is not None:
            live = live_fn()
        else:
            from .live_site import _live
            live = _live()
        txt = today_brief.text(live, now)
        pay = today_text()                               # red team 2026-11-26: big-payout's plan joins guard2's /today
        lines = txt.split("\n")
        key = lines.pop() if lines and lines[-1].startswith("PC signing key:") else None   # the key line stays LAST
        return "\n".join(lines + ([pay] if pay else []) + ([key] if key else []))[:3500]
    except Exception as e:  # noqa: BLE001
        return f"/today failed ({e.__class__.__name__}); /status still works."


# ------------------------------------------------------------------------------------------------ state + Telegram calls
def preview_reply(token: str, chat: str, reply_to=None, http=None, photo: bool = True) -> int:
    """/preview (day-tgpretty): one message per alert style (engine/tg_pretty.samples: examples, no account), then an example chart
    picture on a daemon thread (never holds the poll). Returns how many texts went. Never raises."""
    n = 0
    try:
        from . import tg_pretty
        for i, txt in enumerate(tg_pretty.preview_texts()):
            n += 1 if send_reply(token, chat, txt, reply_to if i == 0 else None, http) else 0
    except Exception:  # noqa: BLE001
        return n
    if photo:
        import threading
        threading.Thread(target=_preview_photo, args=(token, chat), name="tg-preview", daemon=True).start()
    return n


def insta_reply(token: str, chat: str, day=None, reply_to=None, http=None, wait: bool = False) -> str:
    """/insta [day]: the saved Insta card through sendPhoto on a daemon thread (the poll never waits), or a one-line reason.
    Returns "sending" / the reason. Never raises."""
    try:
        from . import insta_card
        path = insta_card.load(day)
        if not path:
            say = (f"\U0001F4F8 No Insta card for {day}: cards are made on green days after the day summary (16:20 ET)." if day else
                   "\U0001F4F8 No Insta card yet: one is made on a green day after the day summary (16:20 ET).")
            send_reply(token, chat, say, reply_to, http)
            return say
        import threading

        def go():
            try:
                from . import alert_bus as AB
                d = day or os.path.basename(path)[6:16]
                AB.send_telegram_photo({"token": token, "chat_id": chat}, path, f"\U0001F4F8 Insta card {d} · ready to post", True)
            except Exception:  # noqa: BLE001
                pass
        th = threading.Thread(target=go, name="tg-insta", daemon=True)
        th.start()
        if wait:
            th.join(30)
        return "sending"
    except Exception as e:  # noqa: BLE001
        return f"error {e.__class__.__name__}"


def _preview_photo(token: str, chat: str) -> bool:
    """An example entry chart (made-up candles, OLYMPUS NIGHT) through sendPhoto. Never raises."""
    try:
        import tempfile
        from . import png_chart as PC, alert_bus as AB
        t0 = int(time.time()) - 90 * 60
        bars, p = [], 25600.0
        for i in range(90):
            o = p
            p += (1.6 if i % 3 else -2.2) + (2.5 if 60 <= i < 70 else 0)
            bars.append((t0 + i * 60, o, max(o, p) + 1.2, min(o, p) - 1.2, p))
        et_ = t0 + 62 * 60
        png = PC.render(bars, [(25760.0, PC.GREEN, et_, False, "TARGET"), (25650.0, PC.GOLD, et_, True, "ENTRY"),
                               (25630.0, PC.RED, et_, False, "STOP"), (25628.0, PC.LILAC, None, True, "SWEEP")],
                        [(et_, 25650.0, PC.GOLD, "entry")],
                        head={"bot": "LIT", "account": "Zlarior 50K", "side": "LONG", "qty": 3, "hero": "5.5R", "hero_col": PC.GOLD,
                              "sub": "RISK $120 \u00b7 TARGET +$660", "tag": "EXAMPLE"},
                        foot="Example chart: swept London low, CISD confirmed",
                        zones=[(25650.0, 25760.0, et_, PC.UP), (25650.0, 25630.0, et_, PC.DOWN)])
        if not png:
            return False
        path = os.path.join(tempfile.gettempdir(), "olympus_preview_chart.png")
        with open(path, "wb") as fh:
            fh.write(png)
        r, _why = AB.send_telegram_photo({"token": token, "chat_id": chat}, path,
                                         "\U0001F4C8 Example chart · gold = entry · red = stop · mint = target · violet = sweep", True)
        return bool(r)
    except Exception:  # noqa: BLE001
        return False


def load_state(path: str = STATE_PATH) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save_state(d: dict, path: str = STATE_PATH) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(d, fh)
        from .fsutil import replace as _replace
        _replace(tmp, path)
    except Exception:
        pass


def _http(method, url, body=None):
    from . import alert_bus
    fn = alert_bus._HTTP or alert_bus._http
    return fn(method, url, body, {"Content-Type": "application/json"} if body is not None else None)


def get_updates(token: str, offset: int | None, http=None) -> tuple:
    """(ok, [updates] | error text). Short poll (timeout=0): never holds a thread."""
    q = {"timeout": 0, "allowed_updates": ["message"]}
    if offset:
        q["offset"] = int(offset)
    try:
        code, txt = (http or _http)("POST", f"https://api.telegram.org/bot{token}/getUpdates", json.dumps(q).encode())
    except Exception as e:  # noqa: BLE001
        return False, f"{e.__class__.__name__}"
    try:
        d = json.loads(txt or "{}")
    except Exception:
        d = {}
    if code == 409:
        return False, "Telegram has a webhook set on this bot (getUpdates refused): commands need it removed (deleteWebhook)"
    if code != 200 or not d.get("ok"):
        return False, f"Telegram said {code}"
    return True, [u for u in d.get("result") or [] if isinstance(u, dict)]


def send_reply(token: str, chat: str, text: str, reply_to=None, http=None) -> bool:
    body = {"chat_id": chat, "text": str(text)[:3500], "disable_web_page_preview": True}
    if reply_to:
        body["reply_to_message_id"] = int(reply_to)
        body["allow_sending_without_reply"] = True
    try:
        code, _ = (http or _http)("POST", f"https://api.telegram.org/bot{token}/sendMessage", json.dumps(body).encode())
        return code == 200
    except Exception:  # noqa: BLE001
        return False


# ------------------------------------------------------------------------------------------------ one poll
class TgCommands:
    """Polls Telegram and hands owner commands to a RemoteControl (rc.run_external). cfg_fn -> engine/alert_bus.config()."""

    def __init__(self, rc, cfg_fn=None, http=None, path: str = STATE_PATH, clock=time.time, env=None, started_at=None,
                 today_live=None):
        self.rc = rc
        self.today_live = today_live                 # tests: a function -> the live view for /today
        self.oflane_root = None                      # tests: a temp repo root for /oflane
        self.cfg_fn = cfg_fn
        self.http = http
        self.path = path
        self.clock = clock
        self.env = env
        self.started_at = clock() if started_at is None else started_at
        self.back_done = False

    def _cfg(self) -> dict:
        try:
            if self.cfg_fn:
                return self.cfg_fn() or {}
            from . import alert_bus
            return alert_bus.config()
        except Exception:  # noqa: BLE001
            return {}

    def tick(self, now=None) -> list:
        """One poll. Returns [(cid, cmd, status, msg)] like RemoteControl.tick. Never raises."""
        now = self.clock() if now is None else now
        out = []
        if not enabled(self.env):
            return out
        cfg = self._cfg()
        tg = cfg.get("telegram") or {}
        token, chat = tg.get("token"), owner_chat(cfg)
        st = load_state(self.path)
        if not token:
            return out
        if not chat:
            if st.get("off") != "group":
                st["off"] = "group"
                save_state(st, self.path)
            return out
        try:
            self._back_up(token, chat, now)
        except Exception:  # noqa: BLE001
            pass
        if getattr(self.rc, "busy", False):
            return out                                # the control-branch pass runs: try again next poll (nothing consumed)
        ok, ups = get_updates(token, st.get("offset"), self.http)
        st["poll"] = {"t": int(now), "ok": bool(ok), **({} if ok else {"error": str(ups)[:160]})}
        if not ok:
            save_state(st, self.path)
            return out
        for u in ups:
            uid = u.get("update_id")
            if isinstance(uid, int):
                st["offset"] = max(int(st.get("offset") or 0), uid + 1)
            msg = u.get("message") or {}
            if not is_owner(msg, chat):
                st["strangers"] = int(st.get("strangers") or 0) + (1 if msg else 0)
                continue
            c, say = parse_text(msg.get("text"))
            mid = msg.get("message_id")
            if c is None:
                if say:
                    send_reply(token, chat, say, mid, self.http)
                continue
            if c.get("cmd") == "oflane":             # the Sim lane's own switch file: answered here, never the control path
                send_reply(token, chat, oflane_reply(c["arg"], self.oflane_root, now), mid, self.http)
                continue
            if c.get("cmd") == "insta":              # read-only: the saved card, answered here, never through the control path
                insta_reply(token, chat, c.get("day"), mid, self.http)
                continue
            if c.get("cmd") == "preview":            # examples only: answered here, never through the control path
                preview_reply(token, chat, mid, self.http)
                continue
            if c.get("cmd") == "today":              # read-only: answered here, never through the control path
                send_reply(token, chat, today_reply(now, self.today_live), mid, self.http)
                continue
            c.update(id=f"tg-{uid}", ts=msg.get("date"))
            reply = (lambda text, _m=mid: send_reply(token, chat, text, _m, self.http))
            save_state(st, self.path)                # the offset is saved BEFORE it runs (a restart never re-reads it)
            try:
                out += self.rc.run_external([c], now, reply=reply, tg={"mid": mid})
            except SystemExit:
                raise
            except Exception as e:  # noqa: BLE001
                send_reply(token, chat, f"{c['cmd']}: error {e.__class__.__name__} (nothing was changed)", mid, self.http)
        save_state(st, self.path)
        return out

    def _back_up(self, token, chat, now):
        """After a Telegram /restart or /update restarted the server: ONE reply 'PC is back up', BACK_AFTER_S after the start."""
        if self.back_done or now - self.started_at < BACK_AFTER_S:
            return
        self.back_done = True
        from .remote_ctl import bot_status_text, load_done, save_done
        d = load_done(self.rc.done_path)
        last = d.get("last") or {}
        cid = str(last.get("id") or "")
        if not cid.startswith("tg-") or last.get("cmd") not in ("restart", "update") or last.get("back"):
            return
        if not str(last.get("msg") or "").count("restart") or now - float(last.get("t") or 0) > BACK_MAX_S:
            return
        sha = ""
        try:
            from .autoupdate import Shell
            c, o = Shell().git("rev-parse", "--short", "HEAD")
            sha = o.strip() if c == 0 else ""
        except Exception:  # noqa: BLE001
            pass
        text = f"PC is back up{' on ' + sha if sha else ''}. {bot_status_text(self.rc.bot)}"
        send_reply(token, chat, text[:900], (last.get("tg") or {}).get("mid"), self.http)
        last["back"] = int(now)
        d["last"] = last
        save_done(d, self.rc.done_path)

    def status(self) -> dict:
        st = load_state(self.path)
        return {"poll": st.get("poll"), "strangers": st.get("strangers", 0), "off": st.get("off")}
