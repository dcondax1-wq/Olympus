"""Short Telegram messages with an emoji (day-tgpretty 2026-11-27, owner: "work Telegram notifications, I need them simplified,
with emojis with what's happening, with possible live chart pictures").

ONE function for every Telegram alert the bus sends (engine/alert_bus._one): fmt(ev, title, body) -> at most 3 short lines:
  line 1  emoji + what happened + $        "🟢 Zlarior 50K LONG in · risk $303 · target +$4,557"
  line 2  one plain detail (optional)      "3 MNQ @ 25,650.00 · stop 25,630.00 · target 25,760.00"
  line 3  the bot's reason (optional)      "LIT: swept London low; CISD confirmed"
Never an account id (engine/notify.mask_ids + alert_bus.redact: token / chat / topic / ids), never a wall of text (each line cut at
LINE_MAX). Discord / ntfy / the Olympus app keep their own texts (alert_bus.text). Pure: no network, no files, never raises (any
trouble = the bus's old title / body, cut to 3 lines).

Rate limit (allow): at most RATE_N Telegram messages per RATE_S for the chatty kinds (setup steps, progress, other notices);
entries, exits, problems, room alarms, bot stopped, PC silent and every "dual" emergency always go. A message over the limit waits in the daily digest (alert_bus.digest_add).
Paper / Sim / BLITZ (is_paper): an entry / exit of such an account never goes to Telegram (the money channel).
Tests: python -X utf8 -m tests.test_tg_pretty
"""
from __future__ import annotations

import re
import threading
import time

LINE_MAX = 150
MAX_LINES = 3
RATE_N = 6                       # chatty messages ...
RATE_S = 10 * 60                 # ... per 10 minutes
CHATTY = ("setup_progress", "eval_milestones", "other")      # the only kinds the rate limit may hold back (+ kind "setup")
ALWAYS = ("entry", "exit", "bot_stopped", "pc_silent", "hedge_risk", "test", "channel_down", "daily", "payout_ready")
PAPER_WORDS = ("paper", "sim", "demo", "playback", "replay", "blitz", "acctc", "acct_c")
MINUS = "-"                      # the same minus as every other channel ("-$310": searchable, never a look-alike)

E_LONG, E_SHORT = "\U0001F7E2", "\U0001F7E2"          # 🟢 an entry (the side word says long / short)
E_TARGET, E_STOP, E_BE, E_WIN, E_LOSS = "✅", "\U0001F6D1", "⚖️", "✅", "\U0001F53B"   # ✅ 🛑 ⚖️ ✅ 🔻
E_SETUP, E_ARMED, E_CANCEL = "\U0001F440", "\U0001F3AF", "✖️"                                  # 👀 🎯 ✖️
E_ALARM, E_WARN, E_PAUSE, E_DAY, E_WEEK = "\U0001F6A8", "⚠️", "⏸️", "\U0001F4CA", "\U0001F5D3️"  # 🚨 ⚠️ ⏸️ 📊 🗓️
E_MONEY, E_CAL, E_HAND, E_SUN, E_UPD = "\U0001F4B0", "\U0001F4C5", "✋", "☀️", "\U0001F504"        # 💰 📅 ✋ ☀️ 🔄
E_GOAL, E_UP, E_BACK, E_DISH, E_INFO, E_TEST = "\U0001F3C6", "\U0001F4C8", "\U0001F49A", "\U0001F4E1", "ℹ️", "\U0001F9EA"  # 🏆 📈 💚 📡 ℹ️ 🧪

_LEAD_JUNK = re.compile(r"^[\W_]+", re.UNICODE)       # a title's own leading emoji / bullets / dashes (never two emojis)
_WS = re.compile(r"\s+")


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
    if v < -0.004:
        return MINUS + s
    return ("+" + s) if sign and v > 0.004 else s


def px(x) -> str:
    v = _f(x)
    return "" if v is None else f"{v:,.2f}"


def _clean(s, n: int = LINE_MAX, strip: bool = True) -> str:
    s = _WS.sub(" ", str(s or "")).strip()
    if strip and s and not s[0].isalnum() and s[0] not in "+-$(" + MINUS:
        s = _LEAD_JUNK.sub("", s).strip()
    s = re.sub(r"(?<![\w$])-\$", MINUS + "$", s)          # "-$310" -> "−$310"
    return s if len(s) <= n else s[: n - 1].rstrip(" ,;:·-") + "…"


def _join(*parts) -> str:
    return " · ".join(p for p in (str(x or "").strip() for x in parts) if p)


def _first(body, n: int = LINE_MAX) -> str:
    """The first real sentence / line of a body."""
    for ln in str(body or "").splitlines():
        ln = ln.strip(" -*•\t")
        if ln:
            return _clean(ln, n)
    return ""


def _lines(body) -> list:
    return [ln.strip(" -*•\t") for ln in str(body or "").splitlines() if ln.strip(" -*•\t")]


def is_paper(ev: dict) -> bool:
    """An entry / exit of a Paper / Sim / demo / BLITZ account: never on Telegram (the money channel)."""
    try:
        if not isinstance(ev, dict) or ev.get("kind") not in ("entry", "exit"):
            return False
        web = ev.get("web") if isinstance(ev.get("web"), dict) else {}
        words = " ".join(str(x or "") for x in (ev.get("account"), web.get("account"), web.get("strategy"), ev.get("key"),
                                                web.get("key"))).lower()
        return any(w in words for w in PAPER_WORDS)
    except Exception:
        return False


# ------------------------------------------------------------------------------------------------ one message per kind
def _entry(ev) -> list:
    side = str(ev.get("side") or "").upper()
    who = _clean(ev.get("account") or "Your account", 40)
    l1 = _join(f"{E_LONG if side == 'LONG' else E_SHORT} {who} {side} in".replace("  ", " "),
               f"risk {usd(ev.get('risk'))}" if _f(ev.get("risk")) is not None else "",
               f"target {usd(ev.get('gain'), True)}" if _f(ev.get("gain")) is not None else "")
    q = _f(ev.get("qty"))
    l2 = _join(f"{int(q)} {ev.get('contract') or 'MNQ'} @ {px(ev.get('price'))}" if q and _f(ev.get("price")) is not None else "",
               f"stop {px(ev.get('stop'))}" if _f(ev.get("stop")) is not None else "",
               f"target {px(ev.get('target'))}" if _f(ev.get("target")) is not None else "")
    return [l1, l2, _why(ev)]


def _why(ev) -> str:
    """The trade card's reason line (engine/trade_card "more": the bot's words first, then the $ risk line)."""
    more = _lines(ev.get("more"))
    return _clean(more[0], LINE_MAX) if more else ""


def _exit(ev) -> list:
    v, r = _f(ev.get("usd")), _f(ev.get("R"))
    why_txt = str(ev.get("reason") or "").strip()
    why = why_txt.lower()
    who = _clean(ev.get("account") or "", 40)
    if "target" in why or why == "banked" or why.startswith("banked"):
        head = f"{E_TARGET} Target hit {usd(v, True)}" if v is not None else f"{E_TARGET} Target hit"
        if why not in ("target",):
            head += f" ({why_txt})"
    elif why in ("stop",) or "stop" in why and "time" not in why:
        head = f"{E_STOP} Stopped {usd(v, True)}" if v is not None else f"{E_STOP} Stopped out"
    elif "breakeven" in why or (v is not None and abs(v) < 0.5):
        head = f"{E_BE} Break-even {usd(v, True) or '$0'}"
    elif v is not None:
        head = f"{E_WIN if v > 0 else E_LOSS} Closed {usd(v, True)}" + (f" ({why_txt})" if why_txt else "")
    else:
        head = f"{E_INFO} Trade closed" + (f" ({why_txt})" if why_txt else "")
    l1 = _join(head, who)
    side = str(ev.get("side") or "").upper()
    l2 = _join(f"{r:+.1f}R".replace("-", MINUS) if r is not None else "", side, str(ev.get("after") or ""))
    return [l1, l2]


def _setup(ev, title, body) -> list:
    t = _clean(title)
    low = t.lower()
    if "cancel" in low:
        return [f"{E_CANCEL} {t}", _first(body)]
    if "armed" in low:
        return [f"{E_ARMED} {t}", _first(body)]
    m = re.search(r"(\d{1,2})/10", t)
    if m:                                                 # "Zlarior LONG swept London low 4/10" -> "👀 Setup forming: swept London low (4/10)"
        words = _clean(re.sub(r"\s*\d{1,2}/10\s*$", "", t))
        words = re.sub(r"^(Zlarior|LIT)\s+(LONG|SHORT)\s*", "", words, flags=re.I).strip() or words
        side = re.search(r"\b(LONG|SHORT)\b", t)
        return [f"{E_SETUP} Setup forming{' ' + side.group(1) if side else ''}: {words} ({m.group(1)}/10)", _first(body)]
    return [f"{E_SETUP} {t}", _first(body)]


def _daily(ev, title, body) -> list:
    rows = ev.get("rows") if isinstance(ev.get("rows"), list) else None
    if rows is not None:
        tot = sum(_f((r or {}).get("usd")) or 0 for r in rows if isinstance(r, dict))
        l2 = _join(*[f"{_clean((r or {}).get('account'), 24)} {usd((r or {}).get('usd'), True) or '$0'}" for r in rows if isinstance(r, dict)][:4])
        return [f"{E_DAY} Day {usd(tot, True) or '$0'}" + (f" · {ev.get('day')}" if ev.get("day") else ""), l2 or "No trades today."]
    return [f"{E_DAY} {_clean(title)}", *(_clean(x) for x in _lines(body)[:2])]


def _emoji_for(ev, title, body) -> str:
    """The emoji of a report / problem / notice, from its key, its notify type and its words."""
    k = str(ev.get("key") or "")
    nt = str(ev.get("notify_type") or "")
    t = f"{title} {body}".lower()
    tl = str(title or "").lower()
    if ev.get("kind") == "test" or tl.startswith("test"):
        return E_TEST
    if k.startswith("pc_back:") or "is back" in tl:
        return E_BACK
    if k.startswith("pc_silent:") or nt == "pc_silent" or "silent" in tl:
        return E_ALARM
    if ev.get("kind") == "bot_stopped" or ev.get("dual") or "no stop" in t or "stop missing" in t or "halt" in tl:
        return E_ALARM
    if k.startswith("guard:goal:") or "target reached" in tl or "passed" in tl:
        return E_GOAL if ("reached" in tl or "passed" in tl or k.endswith(":100")) else E_UP
    if k.startswith(("payout", "life:")) or "payout" in tl:
        return E_MONEY
    if k.startswith("guard:week:") or tl.startswith("week"):
        return E_WEEK
    if k.startswith("guard:day:") or nt == "daily_summary" or tl.startswith("day "):
        return E_DAY
    if k.startswith("guard:quiet:") or "no trade for" in tl:
        return E_CAL
    if "no trade today" in t or "missed" in t or "skipped" in tl or "paused" in tl:
        return E_PAUSE
    if k.startswith("guard:brief:") or nt == "morning_brief" or "brief" in tl or "good morning" in tl:
        return E_SUN
    if "update" in tl:
        return E_UPD
    if k.startswith(("guard:dd:", "guard:dll:", "guard:risk:", "rapid10k:", "risk:")) or nt in ("room_low", "problems") \
            or ev.get("kind") == "problem" or "limit" in tl or "warn" in tl or "fail" in tl or "error" in tl:
        return E_WARN
    if "hand trade" in tl or "hedge" in t:
        return E_HAND
    return E_INFO


_SENT_RX = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9$(\-+])")
ACTION_RX = re.compile(r"\b(place|press|request|run|wait|check|open|type|restart|start bot|stop bot|trade by|call|log in|tap)\b", re.I)


def _sentences(body) -> list:
    out = []
    for ln in _lines(body):
        out += [x.strip() for x in _SENT_RX.split(ln) if x.strip()]
    return out


def _action(body, have: str = "") -> str:
    """The sentence that tells the owner what to DO (or, else, the next one with a $ amount), not already shown."""
    ss = [x for x in _sentences(body) if _clean(x) and _clean(x) not in have]
    for x in ss:
        if ACTION_RX.search(x):
            return _clean(x)
    for x in ss:
        if "$" in x and re.search(r"\b(at most|max|worst|up to)\b", x, re.I):
            return _clean(x)                              # the cap ("at most -$23") before any other $ line
    for x in ss:
        if "$" in x:
            return _clean(x)
    return ""


def _repeats(x: str, title: str) -> bool:
    """A sentence that mostly says the title again ("No 50K trade for 5 days" under "50K: no trade for 5 days")."""
    w = set(re.findall(r"[a-z0-9]+", x.lower()))
    t = set(re.findall(r"[a-z0-9]+", str(title or "").lower()))
    return bool(w) and len(w & t) / len(w) >= 0.5


def _generic(ev, title, body) -> list:
    e = _emoji_for(ev, title, body)
    t = _clean(title) or _first(body)
    ss = [x for x in _sentences(body) if _clean(x) and _clean(x) != t]
    ss = [x for x in ss if not _repeats(x, t)] or ss
    out = [f"{e} {t}"]
    if ss:
        out.append(_clean(ss[0]))
    k = str(ev.get("key") or "")
    if ev.get("kind") in ("brief", "daily") or k.startswith(("guard:day:", "guard:week:")):
        if len(ss) > 1:
            out.append(_clean(ss[1]))                    # a summary: its second line
    elif len(ss) > 1:
        act = _action("\n".join(ss[1:]), out[-1])
        if act:
            out.append(act)                              # what to do / the $ (never dropped by the cut)
    return out


def _alarm(ev, title, body) -> list:
    k = ev.get("kind")
    if k == "pc_silent":
        mins = _f(ev.get("minutes"))
        return [f"{E_ALARM} PC silent" + (f" {int(mins)} min" if mins else ""), "Check the PC: STOP BOT, then START BOT."]
    if k == "bot_stopped":
        return [f"{E_ALARM} Bot stopped: {_clean(ev.get('bot') or title or 'Zlarior', 40)}",
                _clean(ev.get("why") or _first(body) or "Open the PC and press START BOT.")]
    return []


def _room(ev) -> list:
    k = ev.get("kind")
    who = _clean(ev.get("account") or "Your account", 40)
    lim, left = _f(ev.get("limit")), _f(ev.get("left"))
    pct = _f(ev.get("pct")) or (100 * (1 - left / lim) if lim and left is not None else 80)
    what = "daily loss limit" if k == "dll_near" else "max drawdown"
    return [f"{E_WARN} {who}: {what} {pct:.0f}% used", f"{usd(left)} left of {usd(lim)}." if left is not None and lim else ""]


def fmt(ev: dict, title: str = "", body: str = "") -> str:
    """The Telegram text for one bus event: <= 3 short lines, emoji first, ids masked. Never raises."""
    try:
        ev = ev if isinstance(ev, dict) else {}
        k = ev.get("kind")
        if k == "test":                                   # TEST_ALERT / the Alerts box: its own words, exactly (+ nothing in front)
            return mask(f"{title}\n{body}".strip())
        if k == "entry" and not ev.get("report"):
            ls = _entry(ev)
        elif k == "exit" and not ev.get("report"):
            ls = _exit(ev)
        elif k in ("pc_silent",) and not ev.get("report") or k == "bot_stopped" and not ev.get("report"):
            ls = _alarm(ev, title, body)
        elif k in ("dll_near", "dd_near"):
            ls = _room(ev)
        elif k == "seven_day":
            ls = [f"{E_CAL} {_clean(ev.get('account') or 'Your account', 40)}: day {int(_f(ev.get('day')) or 5)} of 7 with no trade",
                  f"Trade by {ev.get('deadline') or 'day 7'} (MFFU's 7-day rule)."]
        elif k == "payout_ready":
            ls = [f"{E_MONEY} {_clean(ev.get('account') or 'Your account', 40)}: payout ready {usd(ev.get('amount') or 1000)}",
                  "Request it on MFFU today."]
        elif k == "hedge_risk":
            nf = [str(x) for x in ev.get("not_flat") or []]
            t0 = _clean(title) if title and not str(title).startswith(("Hand trade", "Olympus")) else "Hand trade: wait"
            ls = [f"{E_HAND} {t0}", f"Not flat: {', '.join(nf)}. Wait until every account is flat." if nf else _first(body),
                  *([_action(body, _first(body))] if not nf else [])]
        elif k == "channel_down":
            ls = [f"{E_DISH} Alerts: {_clean(title).replace('Alerts: ', '')}", _first(body)]
        elif k == "setup":
            ls = _setup(ev, title, body)
        elif k == "daily" and not ev.get("report"):
            ls = _daily(ev, title, body)
        else:
            ls = _generic(ev, title, body)
        ls = [_clean(x, LINE_MAX + 4, strip=False) for x in ls if _clean(x, strip=False)][:MAX_LINES]
        if not ls:
            raise ValueError("empty")
        return mask("\n".join(ls))
    except Exception:
        t = _clean(title) or "Olympus alert"
        b = _first(body)
        return mask(f"{E_INFO} {t}" + (f"\n{b}" if b else ""))


def mask(s: str) -> str:
    try:
        from . import alert_bus as AB
        return AB.redact(s)
    except Exception:
        try:
            from . import notify as N
            return N.mask_ids(s)
        except Exception:
            return str(s)


def caption(ev: dict) -> str:
    """The chart picture's one-line caption (the text went first): what the picture shows."""
    k = ev.get("kind") if isinstance(ev, dict) else None
    who = _clean((ev or {}).get("account") or "", 40)
    if k == "entry":
        return mask(f"\U0001F4C8 {who} entry chart · gold = entry · red = stop · mint = target · violet = sweep".strip())
    if k == "exit":
        return mask(f"\U0001F4C8 {who} trade chart · white ring = exit".strip())
    return "\U0001F4CA Today on one picture"


# ------------------------------------------------------------------------------------------------ rate limit
_RATE_LOCK = threading.Lock()
_SENT: list = []


def allow(ev: dict, now=None) -> bool:
    """True = send to Telegram now. Entries / exits / alarms / emergencies always; the chatty rest at most RATE_N per RATE_S."""
    try:
        if not isinstance(ev, dict):
            return True
        if ev.get("kind") in ALWAYS or ev.get("dual"):
            return True
        if not (ev.get("kind") == "setup" or str(ev.get("notify_type") or "") in CHATTY):
            return True                                   # problems, room, account news: always (never held back)
        t = time.time() if now is None else float(now)
        with _RATE_LOCK:
            _SENT[:] = [x for x in _SENT if t - x < RATE_S]
            if len(_SENT) >= RATE_N:
                return False
            _SENT.append(t)
        return True
    except Exception:
        return True


def _reset_rate() -> None:
    with _RATE_LOCK:
        _SENT.clear()


# ------------------------------------------------------------------------------------------------ /preview (engine/tg_cmd)
PREVIEW_HEAD = "\U0001F9EA Preview: how your alerts look now (examples, no trade was placed)"


def samples() -> list:
    """[(ev, title, body)]: one of each style, with made-up example numbers (the owner's /preview). Never real accounts / ids."""
    return [
        ({"kind": "entry", "account": "Zlarior 50K", "side": "LONG", "qty": 3, "contract": "MNQ", "price": 25650.0, "stop": 25630.0,
          "target": 25760.0, "risk": 120.0, "gain": 660.0, "more": "LIT: swept London low; CISD confirmed"}, "", ""),
        ({"kind": "exit", "account": "Zlarior 50K", "side": "LONG", "usd": 660.0, "R": 5.5, "reason": "target",
          "after": "today +$660, $1,540 to pass"}, "", ""),
        ({"kind": "exit", "account": "ATLAS 25K", "side": "SHORT", "usd": -52.0, "R": -1.0, "reason": "stop", "after": "today -$52"}, "", ""),
        ({"kind": "setup", "key": "setup:preview"}, "Zlarior LONG swept London low 4/10", "Waiting for the CISD on the 5-minute chart."),
        ({"kind": "report", "key": "cond:preview:notrade", "notify_type": "problems"}, "No trade today: FOMC day",
         "The bot sits out big news days by design."),
        ({"kind": "pc_silent", "minutes": 20}, "", ""),
        ({"kind": "bot_stopped", "bot": "Zlarior", "why": "The server is not running in trading hours"}, "", ""),
        ({"kind": "dll_near", "account": "ATLAS 25K", "limit": 500.0, "left": 100.0}, "", ""),
        ({"kind": "report", "key": "guard:day:preview", "notify_type": "daily_summary"}, "Day Fri Nov 27: +$608",
         "Zlarior 50K: +$660 today, $1,540 to pass\nATLAS 25K: -$52 today"),
    ]


def preview_texts() -> list:
    return [PREVIEW_HEAD] + [fmt(ev, t, b) for ev, t, b in samples()]
