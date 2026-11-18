"""BOARD (owner 2026-11-17: "make a communication board so you and the bot know what's happening ... I don't want to keep being a
middleman between you and the bot. Like the eval pass, I should have known that."). docs/BOARD.md.

One event log that the bot, the owner and Claude all write to and all read:

  data/board/events.jsonl   the PC's own log (gitignored): what the bot saw. emit() appends one line, never raises.
  data/board/shared.jsonl   Claude -> bot (TRACKED, ships with the repo the PC auto-pulls): claude_note / plan_changed / owner
                            facts Claude was told in chat (python tools/board.py note|owner|plan). Text privacy-cleaned on write.
  data/inbox/board.jsonl    owner -> both: POST /inbox/board from the phone (engine/day_inbox.py kind "board", the Board page's
                            note box or an iPhone Shortcut). "ATLAS passed", "new funded name ends 1234", "Zlarior 49,192.78".
  tools/web_public/business/accounts.json   the plan (Claude keeps it current): account rows start from it, labelled PLAN.

build() turns them into the board: one row per account (stage chip eval / PASSED / funded / locked / failed / planned, balance,
room, to pass, locked?, last event, where the number came from and when), the newest events, the owner notes nobody answered and
"waiting on you" (accounts.json decisions). public() is the privacy pass (broker ids to the last 4 digits, no PC name, no folder,
no email; hidden bots, BLITZ by default, dropped). It travels:
  heartbeat.json "board"          (engine/heartbeat.py, every beat, ~6 KB)
  ntfy status "brd"               (tools/pc_report.lite, ~700 bytes: newest events + one short row per account)
  /site/board/board.json          (engine/live_site.py on the PC, built live from these files)
  tools/web_public/board/board.json   the published copy (python tools/board.py publish / note)
and the Board page (tools/web_public/board/) draws it. Claude reads it with `python tools/board.py read`.

Kinds: KINDS below. emit(kind, account_key, text, data=None) is the one call the bot side needs (night-life's account
lifecycle code calls it). account_key: an accounts.json key (zlarior, atlas, rapid1, ...) or an alias (lit, builder50k, b ...),
"" / "pc" for the whole PC. data: small JSON (balance, room, floor, to_pass, target_balance, last4, reason ...).
Nothing here trades, arms, routes or sizes; it only appends lines and reads files.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOARD_DIR = os.path.join(ROOT, "data", "board")
INBOX_DIR = os.path.join(ROOT, "data", "inbox")
PLAN_PATH = os.path.join(ROOT, "tools", "web_public", "business", "accounts.json")
EVENTS, SHARED, INBOX = "events.jsonl", "shared.jsonl", "board.jsonl"
KINDS = ("eval_passed", "eval_failed", "account_locked", "order_rejected", "payout_ready", "payout_requested", "balance",
         "bot_started", "bot_stopped", "pc_silent", "owner_note", "claude_note", "plan_changed")
LOUD = {"eval_passed", "eval_failed", "account_locked", "order_rejected", "payout_ready", "pc_silent"}
MAX_TEXT = 300
MAX_DATA = 2000
MAX_LINES, KEEP_LINES = 5000, 3000
STALE_S = 30 * 60                       # the PC reports every 5 (heartbeat) / 15 (ntfy) minutes: 30 min quiet = STALE
ALIASES = {"lit": "zlarior", "zlarior": "zlarior", "builder50k": "zlarior", "a": "zlarior", "acct_a": "zlarior",
           "atlas": "atlas", "builder25k": "atlas", "b": "atlas", "acct_b": "atlas", "account_b": "atlas", "second": "atlas",
           "rapid": "rapid1", "rapid1": "rapid1", "rapid_eod": "rapid1", "blitz": "blitz", "c": "blitz", "acct_c": "blitz",
           "pc": "", "all": "", "": ""}
RULES = {"Rapid EOD 50K": (50000.0, 3000.0, 2000.0), "Builder 50K": (50000.0, 3000.0, 2000.0), "Builder 25K": (25000.0, 1500.0, 1000.0)}
SRC_LABEL = {"bot": "PC", "owner": "owner, typed", "claude": "Claude", "plan": "PLAN", "cloud": "cloud"}
_LOCK = threading.Lock()
_S: dict = {"running": None}

_CTRL = re.compile(r"[\x00-\x1f\x7f<>]")
_LOCK_RX = re.compile(r"limit\s*0\b|max(imum)?\s+order\s+quantity|account\s+(is\s+)?(locked|disabled|halted)", re.I)
_MONEY = r"\$?\s?(\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d{4,6}(?:\.\d{1,2})?)"
_BAL_RX = re.compile(r"balance\s*(?:is|=|:|of)?\s*" + _MONEY, re.I)
_PLAN_BAL_RX = re.compile(r"balance\s+\$?([\d,]+(?:\.\d+)?)\s*\(owner,\s*([A-Za-z]{3,9}\s+\d{1,2})\)", re.I)
_PLAN_ROOM_RX = re.compile(r"\$([\d,]+)\s+of\s+room", re.I)
_LAST4_RX = re.compile(r"(?:ends?(?:\s+in|\s+with)?|last\s*4|last\s+four|…|\.\.\.)\s*:?\s*(\d{4})\b", re.I)


# ------------------------------------------------------------------------------------------------ small helpers
def _f(v):
    try:
        x = float(str(v).replace(",", "").replace("$", "")) if isinstance(v, str) else float(v)
        return x if x == x and abs(x) != float("inf") else None
    except (TypeError, ValueError):
        return None


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def clean(s, n: int = MAX_TEXT) -> str:
    return re.sub(r"\s+", " ", _CTRL.sub(" ", str(s if s is not None else ""))).strip()[:n]


def key_of(account_key) -> str:
    k = re.sub(r"[^a-z0-9_]", "", str(account_key or "").strip().lower())[:24]
    return ALIASES.get(k, k)


def dirs(env=None) -> tuple:
    env = os.environ if env is None else env
    return env.get("LE_BOARD_DIR") or BOARD_DIR, env.get("LE_INBOX_DIR") or INBOX_DIR


def _ny(t) -> dt.datetime:
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.fromtimestamp(float(t), tz=ZoneInfo("America/New_York"))
    except Exception:  # noqa: BLE001
        return dt.datetime.utcfromtimestamp(float(t) - 5 * 3600)


def et_text(t, with_day: bool = True) -> str:
    try:
        d = _ny(t)
        return d.strftime("%b %d %H:%M ET" if with_day else "%H:%M ET").replace(" 0", " ")
    except Exception:  # noqa: BLE001
        return "?"


def day_text(t) -> str:
    try:
        return _ny(t).strftime("%b %d").replace(" 0", " ")
    except Exception:  # noqa: BLE001
        return "?"


def ago(sec) -> str:
    s = _f(sec)
    if s is None:
        return "never"
    s = max(0, int(s))
    if s < 90:
        return "just now"
    if s < 5400:
        return f"{s // 60} min ago"
    if s < 2 * 86400:
        return f"{s // 3600} h ago"
    return f"{s // 86400} days ago"


def usd(v) -> str:
    x = _f(v)
    return "-" if x is None else ("-$" if x < 0 else "$") + f"{abs(x):,.0f}"


def _data(data) -> dict:
    if not isinstance(data, dict):
        return {}
    try:
        raw = json.dumps(data, default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        return {}
    if len(raw) > MAX_DATA:
        return {k: v for k, v in data.items() if isinstance(v, (int, float, bool)) or (isinstance(v, str) and len(v) < 120)}
    return json.loads(raw)


def make(kind, account_key, text, data=None, src: str = "bot", t=None) -> dict | None:
    """One event record, or None when the kind is unknown. id = a short hash of what it says (the same event merged once)."""
    kind = str(kind or "").strip().lower()
    if kind not in KINDS:
        return None
    t = int(_f(t) or time.time())
    rec = {"t": t, "kind": kind, "acct": key_of(account_key), "text": clean(text) or kind.replace("_", " "),
           "src": src if src in SRC_LABEL else "bot"}
    dd = _data(data)
    if dd:
        rec["data"] = dd
    rec["id"] = hashlib.sha1(f"{rec['src']}|{t}|{kind}|{rec['acct']}|{rec['text']}".encode("utf-8")).hexdigest()[:12]
    return rec


def read_jsonl(path: str) -> list:
    out = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    j = json.loads(line)
                except ValueError:
                    continue
                if isinstance(j, dict):
                    out.append(j)
    except OSError:
        pass
    return out


def _trim(path: str):
    rows = read_jsonl(path)
    if len(rows) <= MAX_LINES:
        return
    with open(path + ".tmp", "w", encoding="utf-8") as fh:
        for r in rows[-KEEP_LINES:]:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    from .fsutil import replace as _fs_replace   # retried on a Windows / OneDrive lock (tests.test_selfheal)
    _fs_replace(path + ".tmp", path)


def append(rec: dict, path: str) -> dict:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with _LOCK:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        try:
            if os.path.getsize(path) > MAX_LINES * 200:
                _trim(path)
        except OSError:
            pass
    return rec


def emit(kind, account_key, text, data=None):
    """THE bot-side call: append one event to data/board/events.jsonl. Never raises; -> the record, or None (unknown kind / no disk)."""
    try:
        rec = make(kind, account_key, text, data, src="bot")
        if rec is None:
            return None
        return append(rec, os.path.join(dirs()[0], EVENTS))
    except Exception:  # noqa: BLE001
        return None


def order_rejected(account_key, reason, data=None):
    """An order the broker refused: one order_rejected, plus account_locked when the reason says the account takes no orders
    (MFFU's "max order quantity, Limit 0, Scope MNQ" on a passed eval, 2026-11-17). Never raises; -> the records."""
    out = []
    try:
        why = clean(reason, 200)
        out.append(emit("order_rejected", account_key, f"Order rejected: {why}", {**_d(data), "reason": why}))
        if _LOCK_RX.search(why):
            out.append(emit("account_locked", account_key, "Account takes no orders (Limit 0): passed or locked by MFFU. Bot stays off it.",
                            {**_d(data), "reason": why}))
    except Exception:  # noqa: BLE001
        pass
    return [r for r in out if r]


# ------------------------------------------------------------------------------------------------ owner notes (POST /inbox/board)
def owner_parse(text: str, plan_accounts=None) -> dict:
    """What an owner's note says about an account: {acct, balance, stage, last4}. 'ATLAS passed', 'Zlarior 49,192.78',
    'new funded name ends 1234'. Only what is plainly there."""
    s = clean(text)
    low = s.lower()
    out: dict = {}
    names = {"zlarior": "zlarior", "lit": "zlarior", "atlas": "atlas", "rapid": "rapid1"}
    for a in plan_accounts or []:
        if isinstance(a, dict) and a.get("key") and a.get("name"):
            names.setdefault(str(a["name"]).lower(), str(a["key"]))
    for nm, k in sorted(names.items(), key=lambda x: -len(x[0])):
        if re.search(r"\b" + re.escape(nm) + r"\b", low):
            out["acct"] = k
            break
    m = _BAL_RX.search(s) or (re.search(r"(?<![\d.])" + _MONEY + r"(?![\d])", s) if out.get("acct") else None)
    if m:
        v = _f(m.group(1))
        if v is not None and 1000 <= v <= 500000 and not re.fullmatch(r"\d{4}", m.group(1)):
            out["balance"] = round(v, 2)
    if re.search(r"\b(passed|pass(ed)? the eval)\b", low):
        out["stage"] = "passed"
    elif re.search(r"\b(failed|blew|busted|lost the (eval|account))\b", low):
        out["stage"] = "failed"
    elif re.search(r"\bfunded\b", low):
        out["stage"] = "funded"
    if re.search(r"\blocked\b|limit\s*0", low):
        out["locked"] = True
    m = _LAST4_RX.search(s)
    if m:
        out["last4"] = m.group(1)
    return out


def validate_owner(body, now_s: float):
    """engine/day_inbox kind "board": {"text": "..."} or plain text, 200 characters. -> (record, '') or (None, why)"""
    if isinstance(body, str):
        body = {"text": body}
    if not isinstance(body, dict):
        return None, "send {\"text\": \"...\"} or plain text"
    text = clean(body.get("text") or body.get("note"), 200)
    if not text:
        return None, "nothing to add: the note is empty"
    rec = {"text": text}
    acct = key_of(body.get("acct") or "")
    if acct:
        rec["acct"] = acct
    return rec, ""


def say_owner(rec: dict) -> str:
    p = owner_parse(rec.get("text") or "")
    bits = []
    if p.get("balance") is not None:
        bits.append(f"balance {usd(p['balance'])}")
    if p.get("stage"):
        bits.append(p["stage"])
    if p.get("last4"):
        bits.append(f"ends {p['last4']}")
    return "On the board" + (f" ({', '.join(bits)})" if bits else "") + ". The bot and Claude both see it."


def _inbox_events(path: str, plan_accounts=None) -> list:
    out = []
    for r in read_jsonl(path):
        text = clean(r.get("text"))
        if not text:
            continue
        p = owner_parse(text, plan_accounts)
        acct = key_of(r.get("acct") or p.pop("acct", "") or "")
        p.pop("acct", None)
        ev = {"id": "o" + str(r.get("id") or hashlib.sha1(text.encode()).hexdigest()[:11]), "t": int(_f(r.get("t")) or 0),
              "kind": "owner_note", "acct": acct, "text": text, "src": "owner"}
        if p:
            ev["data"] = p
        out.append(ev)
    return out


# ------------------------------------------------------------------------------------------------ reading it all
def plan(path: str | None = None) -> dict:
    try:
        with open(path or PLAN_PATH, encoding="utf-8") as fh:
            j = json.load(fh)
        return j if isinstance(j, dict) else {}
    except (OSError, ValueError):
        return {}


def merge(*lists) -> list:
    """Events from several places, each id once, oldest first."""
    seen, out = set(), []
    for lst in lists:
        for e in lst or []:
            if not isinstance(e, dict) or e.get("kind") not in KINDS:
                continue
            i = str(e.get("id") or "")
            if not i:
                i = hashlib.sha1(json.dumps(e, sort_keys=True, default=str).encode()).hexdigest()[:12]
                e = {**e, "id": i}
            if i in seen:
                continue
            seen.add(i)
            out.append(e)
    out.sort(key=lambda e: (_f(e.get("t")) or 0, str(e.get("id"))))
    return out


def load(env=None, plan_doc=None, shared_path: str | None = None) -> list:
    """Every event this machine has: the PC log + the shared (repo) notes + the owner's inbox notes, oldest first."""
    bd, ib = dirs(env)
    pa = _d(plan_doc if plan_doc is not None else plan()).get("accounts")
    return merge(read_jsonl(os.path.join(bd, EVENTS)), read_jsonl(shared_path or shared_file(env)), _inbox_events(os.path.join(ib, INBOX), pa))


def shared_file(env=None) -> str:
    """data/board/shared.jsonl: the tracked file Claude writes and the PC pulls (LE_BOARD_SHARED overrides, for tests)."""
    env = os.environ if env is None else env
    return env.get("LE_BOARD_SHARED") or os.path.join(ROOT, "data", "board", SHARED)


def _hidden() -> tuple:
    try:
        from engine import hidden_bots
        return tuple(hidden_bots.hidden())
    except Exception:  # noqa: BLE001
        return ("blitz",)


def _rules(plan_name: str):
    for k, v in RULES.items():
        if k.lower() in str(plan_name or "").lower():
            return v
    return None


def _plan_balance(a: dict, plan_doc: dict):
    m = _PLAN_BAL_RX.search(str(a.get("next") or ""))
    if not m:
        return None, None
    bal = _f(m.group(1))
    when = m.group(2).strip()
    return bal, when


def account_rows(events: list, plan_doc: dict, live: dict | None = None, now: float | None = None) -> list:
    """One row per account of the plan (plus any account an event names that the plan does not have).
    live: {key: {balance, room, floor, to_pass, t, stage}} from the PC's live numbers (newer wins)."""
    now = float(now or time.time())
    live = _d(live)
    hide = set(_hidden())
    accts = [a for a in _d(plan_doc).get("accounts") or [] if isinstance(a, dict) and a.get("key")]
    known = {str(a["key"]) for a in accts}
    for e in events:
        k = str(e.get("acct") or "")
        if k and k not in known and k not in hide and k in ALIASES.values():
            accts.append({"key": k, "name": k.upper() if len(k) <= 5 else k.title(), "plan": "", "stage": "eval", "status": "live"})
            known.add(k)
    rows = []
    for a in accts:
        key = str(a["key"])
        if key in hide:
            continue
        rules = _rules(a.get("plan"))
        row = {"key": key, "name": a.get("name") or key, "plan": a.get("plan") or "", "status": a.get("status") or "",
               "stage": str(a.get("stage") or "eval"), "balance": None, "room": None, "floor": None, "to_pass": None,
               "locked": False, "last4": None, "src": "PLAN", "src_t": None, "last": None}
        bal, when = _plan_balance(a, plan_doc)
        if bal is not None:
            row.update(balance=bal, src=f"PLAN (owner, {when})")
        m = _PLAN_ROOM_RX.search(str(a.get("next") or ""))
        if m and row["stage"] == "eval":
            row["room"] = _f(m.group(1))
        for e in [e for e in events if e.get("acct") == key]:
            d = _d(e.get("data"))
            k = e.get("kind")
            t = int(_f(e.get("t")) or 0)
            src = str(e.get("src") or "bot")
            lab = SRC_LABEL.get(src, src) + (f", {day_text(t)}" if src in ("owner", "claude") and t else "")
            if _f(d.get("balance")) is not None:
                row.update(balance=_f(d["balance"]), src=lab, src_t=t)
                if src != "bot":
                    row["room"] = None                       # an owner-typed balance: the old room no longer holds
            for f in ("room", "floor", "to_pass"):
                if _f(d.get(f)) is not None:
                    row[f] = _f(d[f])
            if d.get("last4"):
                row["last4"] = str(d["last4"])[-4:]
            stage = d.get("stage")
            if k == "eval_passed":
                stage = "passed"
            elif k == "eval_failed":
                stage = "failed"
            if stage in ("eval", "passed", "funded", "failed"):
                row["stage"] = stage
                if stage in ("funded", "eval"):
                    row["locked"] = False
            if k == "account_locked" or d.get("locked") is True:
                row["locked"] = True
            if k != "balance" or not row["last"]:
                row["last"] = {"t": t, "kind": k, "text": clean(e.get("text"), 140), "src": src}
        lv = _d(live.get(key))
        if lv and (_f(lv.get("t")) or 0) >= (row["src_t"] or 0):
            for f in ("balance", "room", "floor", "to_pass"):
                if _f(lv.get(f)) is not None:
                    row[f] = _f(lv[f])
            if lv.get("stage") in ("eval", "funded"):
                row["stage"] = lv["stage"] if row["stage"] not in ("passed", "failed") or lv["stage"] == "funded" else row["stage"]
            row.update(src="PC live", src_t=int(_f(lv.get("t")) or now))
        if rules and row["balance"] is not None and row["stage"] in ("eval", "passed"):
            start, target, mll = rules
            row["target_balance"] = start + target
            row["to_pass"] = round(max(0.0, start + target - row["balance"]), 2)
            if row["to_pass"] <= 0:
                row["stage"] = "passed"                     # over the target: PASSED even before MFFU says so (2026-11-17)
            if row["floor"] is not None:
                row["room"] = round(row["balance"] - row["floor"], 2)
        if row["stage"] in ("passed", "failed"):
            row["room"] = None
        if row["stage"] != "eval":
            row["to_pass"] = 0.0 if row["stage"] == "passed" else None
        row["chip"] = chip(row)
        row["age_s"] = int(now - row["src_t"]) if row["src_t"] else None
        rows.append(row)
    return rows


def chip(row: dict) -> str:
    st = row.get("stage")
    if st == "failed":
        return "failed"
    if st == "passed":
        return "PASSED"
    if row.get("locked"):
        return "locked"
    if st == "funded":
        return "funded"
    if row.get("status") in ("buying", "waiting") and row.get("src") == "PLAN":
        return "planned"
    return "eval"


def open_notes(events: list) -> list:
    """Owner notes no Claude note answered yet (claude_note data.answers holds their ids; one told to Claude in chat counts as answered)."""
    done = set()
    for e in events:
        if e.get("kind") == "claude_note":
            for i in _d(e.get("data")).get("answers") or []:
                done.add(str(i))
    return [e for e in events if e.get("kind") == "owner_note" and str(e.get("id")) not in done and not _d(e.get("data")).get("via")]


def build(events=None, plan_doc=None, live=None, pc=None, now=None, n_events: int = 40, src: str = "pc") -> dict:
    """The board (not yet privacy-passed: give it to public() before it leaves the PC).
    pc: {"t": the PC's last report, "via": "heartbeat" | "ntfy" | "this PC"}."""
    now = int(now or time.time())
    plan_doc = plan() if plan_doc is None else plan_doc
    events = load(plan_doc=plan_doc) if events is None else merge(events)
    hide = set(_hidden())
    events = [e for e in events if str(e.get("acct") or "") not in hide]
    pc = _d(pc)
    pt = _f(pc.get("t"))
    age = int(now - pt) if pt else None
    board = {"v": 1, "kind": "olympus-board", "t": now, "src": src,
             "pc": {"t": int(pt) if pt else None, "age_s": age, "via": pc.get("via") or "", "stale": age is None or age > STALE_S},
             "accounts": account_rows(events, plan_doc, live, now),
             "events": [{k: e.get(k) for k in ("id", "t", "kind", "acct", "text", "src", "data") if e.get(k) not in (None, "", {})}
                        for e in reversed(events[-n_events:])],
             "open_notes": [{k: e.get(k) for k in ("id", "t", "acct", "text")} for e in open_notes(events)][-10:],
             "waiting": [clean(x, 200) for x in _d(plan_doc).get("decisions") or [] if clean(x)][:8],
             "plan_updated": _d(plan_doc).get("updated")}
    return board


def public(board: dict) -> dict:
    """The privacy pass for anything that leaves the PC: broker ids to the last 4 digits, no PC name / login / folder / email
    (tools/site_privacy.public_status). If it cannot run, only the plan-free bare shape goes out."""
    try:
        from tools import site_privacy
        out = site_privacy.public_status(board)
        return out if isinstance(out, dict) else {}
    except Exception:  # noqa: BLE001
        return {k: board.get(k) for k in ("v", "kind", "t", "src", "pc")}


# ------------------------------------------------------------------------------------------------ what travels
def _note_running(bot):
    """bot_started / bot_stopped when the bot's running flag changes between two heartbeats (the first beat records only a start).
    Only the real bot server's heartbeat (LE_HEARTBEAT=1, run_bot.ps1) or a test with its own LE_BOARD_DIR records it: before
    2026-11-18 every test that built a heartbeat payload (the PC self-test, UPDATE's after-update tests) wrote a fake
    "Bot running (PC server started)" into the real board (the owner's "bot started 5 times today")."""
    try:
        env = os.environ
        if not env.get("LE_BOARD_DIR") and (env.get("LE_HEARTBEAT") != "1" or env.get("LE_SELFTEST_CHILD") == "1"):
            return
        run = bool(getattr(bot, "running", False))
        was = _S.get("running")
        if was is None:
            _S["running"] = run
            if run:
                emit("bot_started", "pc", "Bot running (PC server started)")
            return
        if run != was:
            _S["running"] = run
            emit("bot_started" if run else "bot_stopped", "pc", "Bot started" if run else "Bot stopped")
    except Exception:  # noqa: BLE001
        pass


def hb_block(bot=None, max_bytes: int = 6000, now=None) -> dict | None:
    """heartbeat.json "board": the public board of this PC, cut to max_bytes. Never raises."""
    try:
        if bot is not None:
            _note_running(bot)
        now = int(now or time.time())
        b = public(build(pc={"t": now, "via": "this PC"}, now=now, n_events=30))
        for n in (20, 12, 6, 3, 0):
            if len(json.dumps(b, ensure_ascii=False)) <= max_bytes:
                break
            b["events"] = (b.get("events") or [])[:n]
            for e in b["events"]:
                e.pop("data", None)
            b["trimmed"] = True
        return b
    except Exception:  # noqa: BLE001
        return None


def status_block(board: dict | None = None, max_bytes: int = 700) -> dict | None:
    """ntfy status "brd": tiny. {"t", "ev": [[t, kind, acct, text<=90]] newest first, "ac": [[key, chip, balance, room, to_pass, locked]],
    "on": open owner notes count}. Public-passed. Never raises."""
    try:
        b = board if board is not None else public(build(pc={"t": time.time(), "via": "this PC"}, n_events=8))
        out = {"t": b.get("t"),
               "ac": [[r.get("key"), r.get("chip"), _r0(r.get("balance")), _r0(r.get("room")), _r0(r.get("to_pass")), 1 if r.get("locked") else 0]
                      for r in b.get("accounts") or [] if r.get("chip") != "planned"],
               "ev": [[e.get("t"), e.get("kind"), e.get("acct") or "", clean(e.get("text"), 90)] for e in (b.get("events") or [])[:6]
                      if e.get("kind") != "balance" or e.get("src") != "bot"],
               "on": len(b.get("open_notes") or [])}
        while len(json.dumps(out, ensure_ascii=False)) > max_bytes and out["ev"]:
            out["ev"].pop()
        return public(out)
    except Exception:  # noqa: BLE001
        return None


def _r0(v):
    x = _f(v)
    return None if x is None else round(x)


def from_status(brd: dict, src: str = "bot") -> tuple:
    """Undo status_block: (events, live rows {key: {...}}) for tools/board.py and the page."""
    evs, live = [], {}
    if not isinstance(brd, dict):
        return evs, live
    for x in brd.get("ev") or []:
        if isinstance(x, list) and len(x) >= 4 and x[1] in KINDS:
            e = make(x[1], x[2], x[3], src=src, t=x[0])
            if e:
                evs.append(e)
    t = _f(brd.get("t"))
    for x in brd.get("ac") or []:
        if isinstance(x, list) and len(x) >= 6 and x[0]:
            live[str(x[0])] = {"balance": x[2], "room": x[3], "to_pass": x[4], "locked": bool(x[5]), "t": t, "chip": x[1]}
    return evs, live


def site_json(now=None) -> dict:
    """/site/board/board.json on the PC (engine/live_site.py): the public board built live from this PC's files."""
    now = int(now or time.time())
    try:
        hb_t = None
        try:
            with open(os.path.join(ROOT, "logs", "heartbeat_last.json"), encoding="utf-8") as fh:
                hb_t = _f(_d(json.load(fh).get("payload")).get("t"))
        except (OSError, ValueError):
            pass
        return public(build(pc={"t": hb_t, "via": "this PC (last heartbeat)"}, now=now))
    except Exception as e:  # noqa: BLE001
        return {"v": 1, "kind": "olympus-board", "t": now, "error": f"the board could not be built ({e.__class__.__name__})"}


if __name__ == "__main__":                                    # python -m engine.board_events   prints this PC's board
    print(json.dumps(public(build()), indent=1, ensure_ascii=False)[:6000])
