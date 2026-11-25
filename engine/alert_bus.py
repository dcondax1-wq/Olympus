"""ONE send(event) for every phone alert (owner 2026-11-21: "find a better way for notifications ... can't we do it through
Discord or something?"). Stdlib only. Read-only for trading: nothing here places, changes or arms anything, and nothing here
ever blocks or raises into the trading loop (send() only queues; a daemon thread delivers).

Channels, in this order (the first one that gives a RECEIPT wins):
  1. telegram  Telegram bot -> sendMessage to the owner's own chat id only. Receipt = the message_id.
  2. discord   a Discord webhook, POST <url>?wait=true. Receipt = the message id in the 2xx JSON.
  3. ntfy      the private ntfy alert topic (OLYMPUS_HOME/ntfy.json, engine/notify.alert_cfg). Receipt = ntfy's message id.
  4. webpush   the Olympus phone app (engine/push.app_send). Receipt = "accepted by N devices" (no read receipt: the weakest).
Entries, exits and "bot stopped" ALSO go to the next channel that gives a receipt, so one bad channel can never hide them.

  * De-dupe by key (notify's keys: fill:<t>[:acct], out:<t>[:acct], cond:..., guard:...), across restarts
    (data/alert_bus_sent.json, 3 days).
  * 3 retries with backoff 2 / 8 / 30 s on a worker thread (each pass walks the channels in order).
  * Failures -> data/alert_bus.jsonl (gitignored; tokens, webhook URLs, chat ids and topics are redacted). A failing channel
    is reported through the channel that worked: "Alerts: Telegram is not delivering", at most once an hour per channel.
  * Quiet hours = notify_settings.json (engine/notify.quiet): silent delivery, except "bot stopped" and the dual emergencies
    (hedge risk, an open trade at the halt / with no stop), which always ring, plus the settings' own ring_in_quiet_hours kinds.
    Entries and exits follow ring_in_quiet_hours like the old path (redteam 2026-11-21: the owner's yes / no is still open).
  * The status posts never touch this: they stay on ntfy's PUBLIC status topic. Alerts go Telegram / Discord first, so they
    no longer eat ntfy's 250-a-day cap.
  * INBOUND messages to the bot are ignored completely: this module only SENDS (ALERTS_SETUP.bat alone reads the bot's
    inbox, once, to learn the owner's chat id). No commands, no trading over chat.

Setup (the owner, once): ALERTS_SETUP.bat -> tools/alerts_setup.py -> %USERPROFILE%\\.olympus\\alerts.json (never the repo):
  {"telegram": {"token": "...", "chat_id": 123}, "discord": {"webhook": "https://discord.com/api/webhooks/..."}}
Cloud (the PC-silent monitor): repo secrets LE_TG_TOKEN + LE_TG_CHAT and / or LE_DISCORD_WEBHOOK (env) instead of the file.
Off switch: the file %USERPROFILE%\\.olympus\\alert_bus_off (tools/bat/ALERTS_OFF.bat) or LE_ALERT_BUS=0 -> every call site takes its
old path exactly (ntfy + Web Push). Also off when neither Telegram nor Discord is set up (nothing changes before setup).
Test: tools/bat/TEST_ALERT.bat (tools/alerts_setup.py --test). Tests: python -X utf8 -m tests.test_alert_bus

ZERO-SETUP PATH (night-notify 2026-11-22, owner: "get notifications going on your own"): send_critical(ev) is the call for the
events that must reach the phone even when the owner set up NOTHING (no Telegram, no Discord): with the bus active it is send();
otherwise it delivers through the two channels that need no secret, the private ntfy topic (made automatically once per PC by
the 15-minute report: tools/pc_report.ensure_topic, random words + digits, never derived from the PC name or an account id) AND
the installed Olympus app (Web Push), same de-dup by key. Low-priority news (an update applied, a WARN) goes to digest_add() and
reaches the phone once a day in ONE silent post (digest_flush, from the 15-minute report at DIGEST_AT ET). Every critical event
and its sender: engine/alert_map.py (tests/test_alert_map.py checks each one has a working sender).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(ROOT, "data", "alert_bus_sent.json")      # gitignored: keys sent + last "down" warnings
LOG_PATH = os.path.join(ROOT, "data", "alert_bus.jsonl")            # gitignored: failures only, redacted
CFG_NAME = "alerts.json"
OFF_NAME = "alert_bus_off"
CHANNELS = ("telegram", "discord", "ntfy", "webpush")
NAMES = {"telegram": "Telegram", "discord": "Discord", "ntfy": "ntfy", "webpush": "the Olympus app"}
BACKOFF = (2, 8, 30)                 # seconds before retry 1 / 2 / 3
TIMEOUT_S = 10
KEEP_S = 3 * 86400
DOWN_WARN_S = 3600                   # one "channel X down" warning an hour per channel
LOG_MAX_LINES = 2000
DUAL = ("entry", "exit", "bot_stopped")          # also to a second channel
# ring in quiet hours whatever the settings say: "bot stopped" only. Entries / exits follow notify_settings.json ring_in_quiet_hours
# (TRADE_RING: the owner's pending yes / no on STATE.md; until he says yes they arrive WITHOUT sound 23:00-07:00 ET, as on the old
# path). Still dual (two channels). An open trade at the halt / with no stop and a hedge risk ring through their own "dual" flag.
ALWAYS_RING = ("bot_stopped",)
TG_API = "https://api.telegram.org"
MINUS = "-"

# the bus's own event kinds -> notify_settings.json types (on / off + quiet-hour sound)
NOTIFY_TYPE = {"entry": "trade_opened", "exit": "trade_closed", "daily": "daily_summary", "pc_silent": "pc_silent",
               "bot_stopped": "problems", "problem": "problems", "dll_near": "room_low", "dd_near": "room_low",
               "seven_day": "account_status", "payout_ready": "account_status", "hedge_risk": "problems",
               "brief": "morning_brief", "setup": "setup_progress"}

_LOCK = threading.RLock()
_THREADS: list = []
_PENDING: set = set()
_SLEEP = time.sleep                  # tests swap these
_HTTP = None


# ------------------------------------------------------------------------------------------------ small helpers
def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _f(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def usd(x, sign: bool = False) -> str:
    v = _f(x)
    if v is None:
        return ""
    s = f"${abs(v):,.0f}" if abs(v - round(v)) < 0.005 or abs(v) >= 100 else f"${abs(v):,.2f}"
    if v < 0:
        return MINUS + s
    return ("+" + s) if sign else s


def px(x) -> str:
    v = _f(x)
    return "" if v is None else f"{v:,.2f}"


def _et(t) -> dt.datetime:
    from zoneinfo import ZoneInfo
    return dt.datetime.fromtimestamp(float(t), ZoneInfo("America/New_York"))


def hm(t) -> str:
    try:
        return _et(t).strftime("%I:%M %p ET").lstrip("0")
    except Exception:
        return ""


def home(env=None) -> str:
    e = os.environ if env is None else env
    return e.get("OLYMPUS_HOME") or os.path.join(e.get("USERPROFILE") or os.path.expanduser("~"), ".olympus")


# ------------------------------------------------------------------------------------------------ config
def config(env=None, path: str | None = None) -> dict:
    """{"telegram": {"token", "chat_id"} | None, "discord": {"webhook"} | None, "ntfy": bool, "webpush": bool}. The file
    OLYMPUS_HOME/alerts.json, else (the cloud) LE_TG_TOKEN + LE_TG_CHAT / LE_DISCORD_WEBHOOK. Never raises."""
    e = os.environ if env is None else env
    raw = {}
    try:
        with open(path or os.path.join(home(e), CFG_NAME), encoding="utf-8") as fh:
            raw = json.load(fh) or {}
    except Exception:
        raw = {}
    raw = _d(raw)
    tg, dc = _d(raw.get("telegram")), _d(raw.get("discord"))
    token = str(tg.get("token") or e.get("LE_TG_TOKEN") or "").strip()
    chat = str(tg.get("chat_id") or e.get("LE_TG_CHAT") or "").strip()
    hook = str(dc.get("webhook") or e.get("LE_DISCORD_WEBHOOK") or "").strip()
    out = {"telegram": None, "discord": None, "ntfy": raw.get("ntfy", True) is not False,
           "webpush": raw.get("webpush", True) is not False}
    if good_token(token) and re.fullmatch(r"-?\d{1,20}", chat) and tg.get("on", True) is not False:
        out["telegram"] = {"token": token, "chat_id": chat}
    if good_webhook(hook) and dc.get("on", True) is not False:
        out["discord"] = {"webhook": hook}
    return out


def good_token(t) -> bool:
    return bool(re.fullmatch(r"\d{5,15}:[A-Za-z0-9_-]{30,60}", str(t or "").strip()))


def good_webhook(u) -> bool:
    return bool(re.fullmatch(r"https://(?:ptb\.|canary\.)?discord(?:app)?\.com/api/webhooks/\d{5,25}/[A-Za-z0-9_-]{20,100}",
                             str(u or "").strip()))


def switched_off(env=None) -> bool:
    e = os.environ if env is None else env
    if str(e.get("LE_ALERT_BUS") or "").strip() in ("0", "off", "false"):
        return True
    return os.path.exists(os.path.join(home(e), OFF_NAME))


def active(env=None, cfg: dict | None = None) -> bool:
    """True = the call sites hand their alerts to send(). False (switched off, or no Telegram / Discord yet) = their old path,
    exactly. Never raises."""
    try:
        if switched_off(env):
            return False
        c = cfg if cfg is not None else config(env)
        return bool(c.get("telegram") or c.get("discord"))
    except Exception:
        return False


def secrets(cfg: dict | None) -> list:
    c = _d(cfg)
    out = [str(_d(c.get("telegram")).get("token") or ""), str(_d(c.get("telegram")).get("chat_id") or ""),
           str(_d(c.get("discord")).get("webhook") or "")]
    hook = out[2]
    if hook:
        out += hook.rstrip("/").split("/")[-2:]
    try:
        from . import notify
        out.append(str(notify.alert_cfg().get("topic") or ""))
    except Exception:
        pass
    return sorted({s for s in out if len(s) >= 4}, key=len, reverse=True)


_TOKEN_RX = re.compile(r"\d{5,15}:[A-Za-z0-9_-]{30,60}")
_HOOK_RX = re.compile(r"https?://(?:ptb\.|canary\.)?discord(?:app)?\.com/api/webhooks/\S+", re.I)
_BOT_RX = re.compile(r"/bot[^/\s]+")


def redact(s, cfg: dict | None = None) -> str:
    """Every secret out of a text that goes to a log, a print or a phone: the bot token, the webhook, the chat id, the topic,
    and account ids (engine/notify.mask_ids)."""
    s = str(s or "")
    for sec in secrets(cfg):
        s = s.replace(sec, "***")
    s = _HOOK_RX.sub("<discord webhook>", s)
    s = _TOKEN_RX.sub("<bot token>", s)
    s = _BOT_RX.sub("/bot***", s)
    try:
        from . import notify
        s = notify.mask_ids(s)
    except Exception:
        pass
    return s


# ------------------------------------------------------------------------------------------------ the texts
def text(ev: dict) -> tuple:
    """(title, body) in plain English with $, for one event. Never raises."""
    try:
        return _text(_d(ev))
    except Exception:
        return (str(_d(ev).get("title") or "Olympus alert")[:120], str(_d(ev).get("body") or "")[:900])


def _who(ev) -> str:
    return str(ev.get("account") or "Your account")[:40]


def _text(ev: dict) -> tuple:
    k = ev.get("kind")
    if ev.get("report") or (ev.get("title") and k not in ("entry", "exit")) or k in ("report", "problem", "test", "brief"):
        return str(ev.get("title") or "Olympus")[:120], str(ev.get("body") or "")[:900]
    if k == "entry":
        q, side, c = ev.get("qty"), str(ev.get("side") or "").upper(), str(ev.get("contract") or "MNQ")
        risk = _f(ev.get("risk"))
        title = f"{_who(ev)} {side} opened, {int(_f(q) or 0)} {c} @ {px(ev.get('price'))}"
        parts = [f"stop {px(ev.get('stop'))}" if _f(ev.get("stop")) is not None else "",
                 f"target {px(ev.get('target'))}" if _f(ev.get("target")) is not None else "",
                 f"risk {usd(risk)}" if risk is not None else "",
                 f"{usd(ev.get('gain'), True)} at target" if _f(ev.get("gain")) is not None else "",
                 hm(ev["t"]) if _f(ev.get("t")) else ""]
        return title, " · ".join(p for p in parts if p) + "."
    if k == "exit":
        v, r = _f(ev.get("usd")), _f(ev.get("R"))
        why = str(ev.get("reason") or "").strip()
        side = str(ev.get("side") or "").upper()
        bits = [f"{r:+.1f}R" if r is not None else "", why]
        title = f"{_who(ev)} closed {side + ' ' if side else ''}{usd(v, True) if v is not None else ''}".rstrip()
        title += f" ({', '.join(b for b in bits if b)})" if any(bits) else ""
        parts = [str(ev.get("after") or ""), hm(ev["t"]) if _f(ev.get("t")) else ""]
        return title, (" · ".join(p for p in parts if p) + ".") if any(parts) else "Trade closed."
    if k == "daily":
        rows = ev.get("rows") or []
        lines = [f"{_d(r).get('account')}: {usd(_d(r).get('usd'), True)} today" + (f", {usd(_d(r).get('to_pass'))} to pass"
                 if _f(_d(r).get("to_pass")) is not None else "") for r in rows]
        tot = sum(_f(_d(r).get("usd")) or 0 for r in rows)
        return f"Day {ev.get('day') or ''}: {usd(tot, True)}".replace("  ", " "), "\n".join(lines) or "No trades today."
    if k == "pc_silent":
        return ("PC silent", f"Your PC has not reported since {hm(ev['since']) if _f(ev.get('since')) else 'a while'}"
                + (f" ({int(_f(ev.get('minutes')))} min)" if _f(ev.get("minutes")) else "") + ". Check it: STOP BOT, then START BOT.")
    if k == "bot_stopped":
        return (f"Bot stopped: {ev.get('bot') or 'Zlarior'}", f"{ev.get('why') or 'The bot is not running'} in trading hours"
                + (f", {ev.get('since_hm')}" if ev.get("since_hm") else "") + ". Open the PC and press START BOT.")
    if k in ("dll_near", "dd_near"):
        what = "daily loss limit" if k == "dll_near" else "max drawdown"
        lim, left = _f(ev.get("limit")), _f(ev.get("left"))
        pct = _f(ev.get("pct")) or (100 * (1 - left / lim) if lim and left is not None else 80)
        return (f"{_who(ev)}: {what} {pct:.0f}% used",
                f"{usd(left)} left of {usd(lim)}." + (" The bot sizes down; no hand trades today." if k == "dll_near" else
                                                      " One more bad day can end this account: trade small or not at all."))
    if k == "seven_day":
        n = int(_f(ev.get("day")) or 5)
        return (f"{_who(ev)}: day {n} of 7 with no trade",
                f"MFFU's 7-day rule closes an account with no trade for 7 days. Trade by {ev.get('deadline') or 'day 7'}"
                + (" (the bot will if it gets a setup)." if n < 6 else ": tomorrow is the last day."))
    if k == "payout_ready":
        amt, bal = _f(ev.get("amount")), _f(ev.get("balance"))
        return (f"{_who(ev)}: payout ready, {usd(amt or 1000)}",
                f"Balance {usd(bal)} (the plan: request {usd(amt or 1000)} at $2,100). Request it on MFFU today.")
    if k == "hedge_risk":
        nf = [str(x) for x in ev.get("not_flat") or []]
        return ("Hand trade: wait" if nf else "Hand trade risk",
                (f"Not flat: {', '.join(nf)}. A hand trade now can hedge against the bot and break MFFU's rules. "
                 "Wait until EVERY account is flat." if nf else str(ev.get("body") or "Check every account is flat first.")))
    if k == "channel_down":
        return (f"Alerts: {NAMES.get(ev.get('channel'), ev.get('channel'))} is not delivering",
                f"{ev.get('why') or 'it failed'}. Your alerts are coming here instead. Run TEST_ALERT on the PC to check.")
    return str(ev.get("title") or "Olympus alert")[:120], str(ev.get("body") or "")[:900]


def hand_trade_check(accounts) -> dict:
    """{"ok", "not_flat"}: a hand trade is safe only when EVERY account is flat (wf-alert-fix: not just the one shown).
    accounts: [{"name", "position" / "qty"}] or {name: qty}. Unknown = not flat."""
    rows = accounts.items() if isinstance(accounts, dict) else [(_d(a).get("name") or _d(a).get("account"),
                                                                 _d(a).get("position", _d(a).get("qty"))) for a in accounts or []]
    rows, nf = list(rows), []
    for name, q in rows:
        v = _f(q)
        if v is None or abs(v) > 0:
            nf.append(str(name or "an account"))
    return {"ok": bool(rows) and not nf, "not_flat": nf}


# ------------------------------------------------------------------------------------------------ from notify's payloads
def from_trade(p: dict, what: str) -> dict:
    """A bus event from engine/push.pc_notify's fill / outcome payload (the same key). Never raises."""
    p = _d(p)
    try:
        from . import notify as N
        name = N.display_name(p)
        if str(p.get("title") or "").startswith("Keep-alive") and not name.startswith("Keep-alive"):
            name = f"Keep-alive on {name}"             # drill 2026-11-21: the keep-alive's close says what it was
        ev = {"kind": "entry" if what == "entry" else "exit", "key": str(p.get("key") or ""), "account": name,
              "side": str(p.get("side") or "").upper(), "t": _f(p.get("t")), "web": p}
        if what == "entry":
            m = N.entry_message(p)
            ev.update(qty=_f(p.get("qty")), contract=N._contract(p), price=_f(p.get("entry")), stop=_f(p.get("stop")),
                      target=_f(p.get("target")), risk=m.get("risk"), gain=m.get("gain"))
        else:
            c = N.exit_context(p)
            after = []
            if _f(c.get("day")) is not None:
                after.append(f"today {usd(c['day'], True)}")
            if _f(c.get("balance")) is not None:
                after.append(f"balance {usd(c['balance'])}")
            if _f(c.get("to_pass")) is not None:
                after.append("target reached" if c["to_pass"] <= 0.5 else f"{usd(c['to_pass'])} to pass")
            r = p.get("R") if p.get("R") is not None else p.get("r")
            reason = str(p.get("exit") or "").upper()
            ev.update(usd=_f(p.get("usd")), R=_f(r), reason=N.EXIT_WORDS.get(reason, reason.lower()), after=", ".join(after))
        return ev
    except Exception:
        return {"kind": "entry" if what == "entry" else "exit", "key": str(p.get("key") or ""), "title": str(p.get("title") or "Trade"),
                "body": str(p.get("body") or ""), "web": p, "report": True}


def from_report(m: dict) -> dict:
    """A bus event from one 15-minute report push (tools/pc_report events -> notify.apply): its own words, its key."""
    m = _d(m)
    k = str(m.get("key") or "")
    try:
        from . import notify as N
        nt = m.get("kind") or N.kind_of(k)
    except Exception:
        nt = "other"
    kind = {"trade_opened": "entry", "trade_closed": "exit", "daily_summary": "daily", "pc_silent": "pc_silent",
            "morning_brief": "brief"}.get(nt, "report")
    if k.startswith("cond:") and any(w in k for w in ("bot_down", "server_down", "not_running", "stopped")):
        kind = "bot_stopped"
    crit = k.startswith("cond:") and any(w in k for w in ("halt_open", "no_stop"))
    return {"kind": kind, "key": k, "title": str(m.get("title") or "Olympus"), "body": str(m.get("body") or ""),
            "notify_type": nt, "priority": m.get("priority"), "report": True, "dual": crit}


def from_problem(p: dict, msg: dict) -> dict:
    """A bus event from engine/notify.instant_problem (the fast alarm, a missed trade): bot down / stopped = "bot_stopped"
    (dual, always rings); an open trade at the halt / with no stop = dual too; the rest = "problem"."""
    code = str(_d(p).get("code") or "")
    kind = "bot_stopped" if code in ("bot_down", "bot_stopped") else "problem"
    return {"kind": kind, "key": str(_d(p).get("key") or ""), "title": msg.get("title"), "body": msg.get("body"),
            "notify_type": "problems", "dual": code in ("halt_open", "no_stop", "stop_missing"), "report": True, "soft": bool(_d(p).get("soft"))}


# ------------------------------------------------------------------------------------------------ state + log
def _state(path=None) -> dict:
    try:
        with open(path or STATE_PATH, encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save_state(st: dict, path=None, now=None) -> None:
    path = path or STATE_PATH
    t = time.time() if now is None else now
    st["keys"] = {k: v for k, v in _d(st.get("keys")).items() if (_f(v) or 0) >= t - KEEP_S}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(st, fh)
    from . import fsutil as _fsutil
    _fsutil.replace(tmp, path)


def was_sent(key: str, path=None) -> bool:
    return bool(key) and key in _d(_state(path).get("keys"))


def log_fail(row: dict, cfg=None, path=None) -> None:
    """One failure line (redacted) to data/alert_bus.jsonl; the file keeps its last LOG_MAX_LINES lines. Never raises."""
    try:
        path = path or LOG_PATH
        os.makedirs(os.path.dirname(path), exist_ok=True)
        line = redact(json.dumps({"t": int(time.time()), **row}, default=str, ensure_ascii=False), cfg)
        with _LOCK:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
            if os.path.getsize(path) > 400_000:
                with open(path, encoding="utf-8") as fh:
                    keep = fh.readlines()[-LOG_MAX_LINES // 2:]
                with open(path, "w", encoding="utf-8") as fh:
                    fh.writelines(keep)
    except Exception:
        pass


# ------------------------------------------------------------------------------------------------ the channels
def _http(method, url, body=None, headers=None, timeout=TIMEOUT_S) -> tuple:
    """(status, text). Never raises: a timeout / refused connection = (0, the error's name)."""
    if _HTTP is not None:
        return _HTTP(method, url, body, headers or {}, timeout)
    try:
        req = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(200_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        try:
            return e.code, e.read(2000).decode("utf-8", "replace")
        except Exception:
            return e.code, ""
    except Exception as e:
        return 0, e.__class__.__name__


def _json(txt) -> dict:
    try:
        return _d(json.loads(txt))
    except Exception:
        return {}


def send_telegram(c: dict, title: str, body: str, silent: bool) -> tuple:
    """(receipt | None, why)."""
    data = json.dumps({"chat_id": c["chat_id"], "text": f"{title}\n{body}"[:4000], "disable_notification": bool(silent),
                       "disable_web_page_preview": True}).encode("utf-8")
    st, txt = _http("POST", f"{TG_API}/bot{c['token']}/sendMessage", data, {"Content-Type": "application/json"})
    j = _json(txt)
    mid = _d(j.get("result")).get("message_id")
    if 200 <= int(st or 0) < 300 and j.get("ok") and mid is not None:
        return f"telegram:{mid}", "ok"
    return None, f"Telegram answered {st or 'nothing'} {str(j.get('description') or txt or '')[:80]}".strip()


def send_discord(c: dict, title: str, body: str, silent: bool) -> tuple:
    data = {"content": f"**{title}**\n{body}"[:1990], "allowed_mentions": {"parse": []}}
    if silent:
        data["flags"] = 4096                                    # SUPPRESS_NOTIFICATIONS: arrives without a ping
    st, txt = _http("POST", c["webhook"].split("?")[0] + "?wait=true", json.dumps(data).encode("utf-8"),
                    {"Content-Type": "application/json", "User-Agent": "Olympus-alerts (stdlib, 1.0)"})
    mid = _json(txt).get("id")
    if 200 <= int(st or 0) < 300 and mid:
        return f"discord:{mid}", "ok"
    return None, f"Discord answered {st or 'nothing'} {str(txt or '')[:80]}".strip()


def send_ntfy(title: str, body: str, silent: bool, tags: str = "") -> tuple:
    try:
        from . import notify as N
        nc = N.alert_cfg()
    except Exception:
        nc = {}
    if not nc.get("topic"):
        return None, "no private ntfy topic"
    h = {"Content-Type": "text/plain; charset=utf-8", "Title": title.encode("ascii", "replace").decode("ascii"),
         "Priority": "low" if silent else "high"}
    if tags:
        h["Tags"] = tags
    st, txt = _http("POST", f"{nc['ntfy']}/{nc['topic']}", body.encode("utf-8"), h)
    if 200 <= int(st or 0) < 300:
        try:
            from . import notify as N
            N.count_ntfy_post()                              # the day's ntfy budget (tools/pc_report keeps room for alerts)
        except Exception:
            pass
        return f"ntfy:{_json(txt).get('id') or 'ok'}", "ok"
    return None, ("ntfy rate limit (250 a day)" if st == 429 else f"ntfy answered {st or 'nothing'}")


def send_webpush(ev: dict, title: str, body: str, silent: bool) -> tuple:
    try:
        from . import push as P
        p = ev.get("web")
        if isinstance(p, dict) and p.get("kind") in ("fill", "outcome"):
            payload = P.app_payload(p)
        else:
            payload = P.report_payload({"key": ev.get("key"), "title": title, "body": body, "priority": "low" if silent else "high",
                                        "t": ev.get("t") or time.time()})
        r = P.app_send(payload)
        if int(r.get("sent") or 0) > 0:
            return f"webpush:{int(r['sent'])} device(s) accepted", "ok"
        return None, f"Web Push: {r.get('skipped') or ','.join(map(str, r.get('errors') or [])) or 'not accepted'}"
    except Exception as e:
        return None, f"Web Push failed: {e.__class__.__name__}"


def channels(cfg: dict) -> list:
    out = []
    if cfg.get("telegram"):
        out.append("telegram")
    if cfg.get("discord"):
        out.append("discord")
    if cfg.get("ntfy", True):
        out.append("ntfy")
    if cfg.get("webpush", True):
        out.append("webpush")
    return out


def _one(ch: str, cfg: dict, ev: dict, title: str, body: str, silent: bool) -> tuple:
    try:
        if ch == "telegram":
            return send_telegram(cfg["telegram"], title, body, silent)
        if ch == "discord":
            return send_discord(cfg["discord"], title, body, silent)
        if ch == "ntfy":
            return send_ntfy(title, body, silent, str(ev.get("tags") or ""))
        if ch == "webpush":
            return send_webpush(ev, title, body, silent)
    except Exception as e:
        return None, f"{ch} failed: {e.__class__.__name__}"
    return None, "unknown channel"


# ------------------------------------------------------------------------------------------------ quiet hours
def is_silent(ev: dict, now=None, s: dict | None = None) -> bool:
    """No sound: inside the quiet hours, unless the kind always rings (bot stopped, the dual emergencies) or is in
    ring_in_quiet_hours (entries / exits only when the owner put TRADE_RING there)."""
    k = ev.get("kind")
    if ev.get("silent"):
        return True                        # the daily digest: never a buzz
    if k in ALWAYS_RING or ev.get("dual"):
        return False
    try:
        from . import notify as N
        s = s or N.settings()
        if not N.quiet(time.time() if now is None else now, s):
            return False
        if ev.get("soft"):
            return True                    # drill 2026-11-21: a soft notice (keep-alive line, a rule's own hold) is silent at night,
                                           # as on the old path (notify.problem_message)
        nt = ev.get("notify_type") or NOTIFY_TYPE.get(k, "other")
        return not N.rings(nt, s)
    except Exception:
        return False


# ------------------------------------------------------------------------------------------------ deliver
def deliver(ev: dict, cfg: dict | None = None, path=None, log_path=None, now=None, s=None) -> dict:
    """Synchronous delivery of one event (the worker thread; scripts; tests). -> {"key", "receipts" {channel: id}, "failed"
    {channel: why}, "tries", "ok"}. Never raises."""
    res = {"key": str(_d(ev).get("key") or ""), "receipts": {}, "failed": {}, "tries": 0, "ok": False}
    try:
        cfg = cfg if cfg is not None else config()
        title, body = text(ev)
        silent = is_silent(ev, now=now, s=s)
        order = list(ev.get("only") or channels(cfg))
        dual = ev.get("kind") in DUAL or bool(ev.get("dual"))
        need = int(_f(ev.get("need")) or (2 if dual else 1))
        need = min(need, len(order)) or 1
        dual = dual or need > 1
        for i, delay in enumerate((0,) + tuple(ev.get("backoff", BACKOFF))):
            if delay:
                _SLEEP(delay)
            res["tries"] = i + 1
            for ch in order:
                if len(res["receipts"]) >= need:
                    break
                if ch in res["receipts"]:
                    continue
                rid, why = _one(ch, cfg, ev, title, body, silent)
                if rid:
                    res["receipts"][ch] = rid
                    res["failed"].pop(ch, None)
                else:
                    res["failed"][ch] = why
            if len(res["receipts"]) >= need:
                break
            if res["receipts"] and not dual:
                break
        res["ok"] = bool(res["receipts"])
        for ch, why in res["failed"].items():
            log_fail({"key": res["key"], "kind": ev.get("kind"), "channel": ch, "why": why, "tries": res["tries"]}, cfg, log_path)
        if not res["ok"]:
            log_fail({"key": res["key"], "kind": ev.get("kind"), "undelivered": True, "title": title}, cfg, log_path)
        if res["key"] and res["ok"] and not ev.get("no_record"):
            with _LOCK:
                st = _state(path)
                st.setdefault("keys", {})[res["key"]] = time.time() if now is None else now
                _save_state(st, path, now)
        if res["ok"] and res["failed"] and ev.get("kind") != "channel_down":
            _warn_down(res, cfg, path, log_path, now)
    except Exception as e:
        res["error"] = e.__class__.__name__
    return res


def _warn_down(res: dict, cfg: dict, path, log_path, now) -> None:
    """A channel failed while another worked: ONE warning through the one that worked, at most once an hour per channel."""
    t = time.time() if now is None else now
    due = []
    for ch, why in res["failed"].items():
        if ch == "ntfy" and "no private ntfy topic" in str(why):
            continue                                      # not set up is not "down"
        if ch == "webpush" and any(w in str(why) for w in ("no phone", "not for the phone", "not configured")):
            continue
        due.append((ch, why))
    if not due:
        return
    with _LOCK:
        st = _state(path)
        down = st.setdefault("down", {})
        due = [(ch, why) for ch, why in due if t - (_f(down.get(ch)) or 0) >= DOWN_WARN_S]
        for ch, _w in due:
            down[ch] = t
        if due:
            _save_state(st, path, now)
    if due:
        ch, why = due[0]
        if len(due) > 1:
            why = "; ".join(f"{NAMES.get(c, c)}: {w}" for c, w in due)
        deliver({"kind": "channel_down", "channel": " and ".join(NAMES.get(c, c) for c, _ in due) if len(due) > 1 else ch,
                 "why": redact(why, cfg), "key": "", "only": list(res["receipts"])[:1], "backoff": ()},
                cfg=cfg, path=path, log_path=log_path, now=now)


def send(ev: dict, on_done=None, cfg: dict | None = None, wait: bool = False, _zero: bool = False) -> str:
    """THE call for every alert: queue one event, return at once ("queued" | "dup" | "off" | "bad"). A daemon thread delivers
    (deliver). on_done(result) runs on that thread after delivery (e.g. notify.instant_record). wait=True = deliver here (a
    script). Never raises, never blocks the caller (unless wait)."""
    try:
        ev = dict(_d(ev))
        if not ev.get("kind"):
            return "bad"
        if os.environ.get("LE_SELFTEST_CHILD") == "1" and _HTTP is None:
            return "off"                                  # a PC self-test child never sends a real alert (engine/push SEALED)
        c = cfg if cfg is not None else config()
        if ev.get("kind") != "test" and not _zero and not active(cfg=c):
            return "off"
        key = str(ev.get("key") or "")
        if ev.get("kind") not in ("test", "channel_down"):
            try:
                from . import notify as N
                nt = ev.get("notify_type") or NOTIFY_TYPE.get(ev["kind"])
                if nt and not N.on(nt):
                    return "off"
            except Exception:
                pass
        with _LOCK:
            if key and (key in _PENDING or was_sent(key)):
                return "dup"
            if key:
                _PENDING.add(key)

        def run():
            r = {}
            try:
                r = deliver(ev, cfg=c)
            finally:
                with _LOCK:
                    _PENDING.discard(key)
            if on_done:
                try:
                    on_done(r)
                except Exception:
                    pass
            return r

        if wait:
            r = run()
            return "sent" if (r or {}).get("ok") else "failed"     # audit 2026-11-22 (package B): "sent" = it reached a channel
        th = threading.Thread(target=run, name="alert-bus", daemon=True)
        with _LOCK:
            _THREADS[:] = [x for x in _THREADS if x.is_alive()]
            _THREADS.append(th)
        th.start()
        return "queued"
    except Exception:
        return "bad"


def drain(timeout: float = 90.0) -> bool:
    """Wait (a script before it exits, e.g. tools/pc_report) for the queued deliveries. True = all done."""
    end = time.time() + timeout
    with _LOCK:
        ths = list(_THREADS)
    for th in ths:
        th.join(max(0.0, end - time.time()))
    return not any(th.is_alive() for th in ths)


# ------------------------------------------------------------------------------------------------ zero-setup path
ZERO = ("ntfy", "webpush")            # the channels that need no secret: the private ntfy topic + the installed Olympus app


def zero_cfg(cfg: dict | None = None) -> dict:
    """The config with Telegram / Discord taken out (the no-secret channels only)."""
    c = dict(cfg if cfg is not None else config())
    c["telegram"], c["discord"] = None, None
    return c


def send_critical(ev: dict, on_done=None, cfg: dict | None = None, wait: bool = False, no_app: bool = False) -> str:
    """A critical event that must reach the phone with ZERO setup. Bus active (Telegram / Discord set up, not switched off) =
    send(). Otherwise: the private ntfy topic AND the Olympus app (both, so an "accepted" by Apple alone never hides it), the
    same de-dup by key. ALERTS_OFF = "off" (the call sites' old path, exactly).
    Returns like send(). Never raises."""
    try:
        ev = day_key(dict(_d(ev)))
        c = cfg if cfg is not None else config()
        if active(cfg=c):
            return send(ev, on_done=on_done, cfg=c, wait=wait)
        if cfg is None and switched_off():
            return "off"                                # ALERTS_OFF = every call site's old path, exactly (as documented)
        z = zero_cfg(c)
        if no_app:
            z["webpush"] = False                        # the caller's Olympus app copy already went out (engine/push._pc_send)
        ev = dict(_d(ev))
        ev["only"] = [ch for ch in ZERO if ch in channels(z)]
        if not ev["only"]:
            return "off"
        # both no-secret channels for a critical one (not the first that answers; no forced ring); a soft notice (keep-alive line, a
        # rule's own hold) = the first that answers, so one event is one buzz
        ev.setdefault("need", 1 if ev.get("soft") else len(ev["only"]))
        if int(_f(ev.get("need")) or 0) == 1 and "webpush" in ev["only"]:
            # night-alertproof 2026-11-23: a one-channel notice tries the Olympus app FIRST. An app "sent" means a phone accepted it;
            # an ntfy "ok" only means ntfy.sh stored it, even when nobody follows the topic (the owner may have only the app)
            ev["only"] = ["webpush"] + [c for c in ev["only"] if c != "webpush"]
        return send(ev, on_done=on_done, cfg=z, wait=wait, _zero=True)
    except Exception:
        return "bad"


_ATTEMPT_KEY = re.compile(r"^(auto:update:[a-z_]+):\d{9,11}$")


def day_key(ev: dict) -> dict:
    """Red team 2026-11-23: engine/autoupdate keys each attempt by its epoch ("auto:update:failed:<t>"), and the server tries
    hourly outside trading time, so a failure that keeps happening would buzz the phone every hour all night. Same status +
    same title = ONE alert per ET day; a different failure (another title) still goes at once."""
    try:
        m = _ATTEMPT_KEY.match(str(ev.get("key") or ""))
        if m:
            import hashlib
            h = hashlib.sha1(str(ev.get("title") or "").encode("utf-8")).hexdigest()[:8]
            ev["key"] = f"{m.group(1)}:{_et(time.time()).date().isoformat()}:{h}"
    except Exception:
        pass
    return ev


DIGEST_PATH = os.path.join(ROOT, "data", "alert_digest.json")    # gitignored: low-priority items waiting for the daily digest
DIGEST_AT = 16 * 60 + 20              # ET minutes: one digest a day, after the 16:15 day summary
DIGEST_MAX = 12                       # lines kept (the oldest are dropped)


def digest_add(title: str, body: str = "", key: str = "", path=None, now=None) -> bool:
    """One low-priority line for the daily digest (no phone buzz now). Same key twice = one line. Never raises."""
    try:
        path = path or DIGEST_PATH
        t = time.time() if now is None else now
        with _LOCK:
            d = _state(path)
            items = [i for i in d.get("items") or [] if isinstance(i, dict)]
            k = str(key or title)
            if any(i.get("key") == k for i in items):
                return False
            items.append({"key": k, "t": int(t), "line": redact(f"{title}" + (f": {body}" if body else ""))[:200]})
            d["items"] = items[-DIGEST_MAX:]
            _save_state(d, path, t)
        return True
    except Exception:
        return False


def digest_peek(day: str, path=None) -> list:
    """The waiting low-priority lines for the evening message (tools/pc_guard.day_summary, night-brief 2026-11-23: ONE evening
    message, not two); marks them as carried by `day` (digest_flush then drops them instead of sending them again). Never raises."""
    try:
        path = path or DIGEST_PATH
        with _LOCK:
            d = _state(path)
            items = [i for i in d.get("items") or [] if isinstance(i, dict) and i.get("shown") in (None, day)]
            for i in items:
                i["shown"] = day
            d["items"] = [i for i in d.get("items") or [] if isinstance(i, dict)]
            if items:
                _save_state(d, path)
        return [str(i.get("line") or "") for i in items]
    except Exception:
        return []


def digest_flush(now=None, path=None, cfg: dict | None = None, force: bool = False) -> str:
    """The 15-minute report: from DIGEST_AT ET, once a day, the waiting low-priority lines as ONE silent post ("sent" / "none" /
    "not yet" / "done today"). Never raises."""
    try:
        path = path or DIGEST_PATH
        t = time.time() if now is None else now
        e = _et(t)
        day = e.date().isoformat()
        with _LOCK:
            d = _state(path)
            if not force and d.get("day") == day:
                return "done today"
            if not force and e.hour * 60 + e.minute < DIGEST_AT:
                return "not yet"
            items = [i for i in d.get("items") or [] if isinstance(i, dict)]
            trading = False
            if not force:
                try:
                    from . import cme_calendar as C
                    trading = e.weekday() < 5 and not C.full_closure(e.date())
                except Exception:
                    trading = e.weekday() < 5
            if trading:
                # a CME trading day: the 16:15 day summary carries the lines (digest_peek); drop what it showed, keep the rest
                # for tomorrow's summary: ONE evening message, never a second digest
                d["day"] = day
                d["items"] = [i for i in items if not i.get("shown")]
                _save_state(d, path, t)
                return "in the day summary"
            d["day"] = day
            d["items"] = []
            _save_state(d, path, t)
        if not items:
            return "none"
        body = "\n".join(f"- {i.get('line')}" for i in items)
        r = send_critical({"kind": "report", "key": f"digest:{day}", "title": f"Olympus daily digest ({len(items)})", "body": body,
                           "notify_type": "daily_summary", "report": True, "silent": True, "need": 1},
                          cfg=cfg, wait=True)
        return r if r in ("sent", "queued", "failed") else r
    except Exception:
        return "failed"


# ------------------------------------------------------------------------------------------------ the test alert
TEST_TITLE = "TEST: Zlarior 50K LONG opened, 6 MNQ @ 21,555.50"
TEST_BODY = "stop 21,574.00, risk $228. This is a test from TEST_ALERT: no trade was placed."


def test_all(cfg: dict | None = None) -> dict:
    """tools/bat/TEST_ALERT.bat: one fake entry through EVERY configured channel (no fallback: each on its own). {channel: (receipt, why)}."""
    cfg = cfg if cfg is not None else config()
    ev = {"kind": "test", "key": "", "title": TEST_TITLE, "body": TEST_BODY}
    out = {}
    for ch in channels(cfg):
        out[ch] = _one(ch, cfg, ev, TEST_TITLE, TEST_BODY, False)
    return out
