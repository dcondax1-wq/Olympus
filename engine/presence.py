"""'I'm at the desk' presence check-in (competitor-features.md #2).

MFFU allows automated trading only with the trader monitoring it (third-party wording, the TradersPost guide quoted in
research/writeups/competitor-features.md). This module keeps a plain log of when the owner said "I'm here":

  data/presence.jsonl (gitignored)   one JSON line per tap: {"t", "kind": "in" | "out", "src": "pc" | "phone", "hours"}
                                     "in" opens a presence window of `hours` (default 4 h, guards.presence_hours); a later
                                     "in" extends it; "out" ("I'm leaving") closes it.

Sources of a tap: the PC dashboard's Bot page (POST /api/next/presence/checkin, engine/presence_api.py) and the phone's
Remote page through the existing control branch (engine/remote_ctl.py command "present").

Optional guard (OFF by default, live_model.json / start cfg "guards"):
  presence_required  False   True = no NEW entry unless there was a check-in in the last presence_hours. Open trades keep
                             their stop / target. It can only block an entry, never add one.
  presence_hours     4       length of a check-in window.
While the guard is on and nobody is checked in, the bot pushes "Check in to keep trading" once per trading day and window
(from 01:40 ET, weekdays, until the 15:30 entry cutoff). With the guard off nothing here changes what the bot does.

The presence log page (log_view): the windows, every bot trade (entry time) and whether the owner was checked in then.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "presence.jsonl")
DEFAULT_HOURS = 4.0
MAX_HOURS = 16.0
REMIND_FROM = 1 * 60 + 40          # 01:40 ET
REMIND_TO = 15 * 60 + 30           # 15:30 ET (the LIT entry cutoff)


def _et(t) -> dt.datetime:
    return dt.datetime.fromtimestamp(int(t), ET)


def _hm(t) -> str:
    return _et(t).strftime("%H:%M")


def _dhm(t) -> str:
    return _et(t).strftime("%a %H:%M")


def trading_day(t) -> str:
    return (_et(t) + dt.timedelta(hours=6)).strftime("%Y-%m-%d")


def path_for(bot=None) -> str:
    """data/presence.jsonl beside the bot's state file (one per person, not per account); PATH without a bot."""
    sp = getattr(bot, "state_path", None) if bot is not None else None
    return os.path.join(os.path.dirname(sp), "presence.jsonl") if sp else PATH


def _hours(h, default=DEFAULT_HOURS) -> float:
    try:
        x = float(h)
    except (TypeError, ValueError):
        return float(default)
    return min(MAX_HOURS, max(0.25, x)) if x == x else float(default)


# ---------------------------------------------------------------------------------------------- the log
def record(kind: str, src: str = "pc", now=None, hours=None, path: str = PATH, note: str | None = None) -> dict:
    kind = "out" if str(kind).lower() in ("out", "away", "leave", "checkout") else "in"
    src = str(src or "pc")[:12]
    row = {"t": int(time.time() if now is None else now), "kind": kind, "src": src}
    if kind == "in":
        row["hours"] = _hours(hours)
    if note:
        row["note"] = str(note)[:80]
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
    return row


def check_in(src="pc", hours=None, now=None, path: str = PATH) -> dict:
    return record("in", src, now, hours, path)


def check_out(src="pc", now=None, path: str = PATH) -> dict:
    return record("out", src, now, None, path)


def events(path: str = PATH) -> list:
    out = []
    try:
        with open(path, encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    r = json.loads(ln)
                except Exception:
                    continue
                if isinstance(r, dict) and isinstance(r.get("t"), (int, float)) and r.get("kind") in ("in", "out"):
                    out.append(r)
    except FileNotFoundError:
        pass
    return sorted(out, key=lambda r: r["t"])


def windows(evs: list, now=None) -> list:
    """Merged presence windows [{"from", "to", "src", "open", "ended": "expired" | "checked out" | None}]."""
    now = int(time.time() if now is None else now)
    out, cur = [], None
    for r in evs:
        t = int(r["t"])
        if t > now:
            break
        if cur and cur["to"] <= t:                      # the window ran out before this tap
            cur["ended"] = "expired"
            out.append(cur)
            cur = None
        if r["kind"] == "in":
            end = t + int(_hours(r.get("hours")) * 3600)
            if cur:
                cur["to"] = max(cur["to"], end)
                cur["taps"] += 1
            else:
                cur = {"from": t, "to": end, "src": r.get("src") or "pc", "taps": 1, "ended": None}
        elif cur:
            cur["to"] = t
            cur["ended"] = "checked out"
            out.append(cur)
            cur = None
    if cur:
        if cur["to"] <= now:
            cur["ended"] = "expired"
        out.append(cur)
    for w in out:
        w["open"] = w["ended"] is None and w["from"] <= now < w["to"]
        w["minutes"] = int((min(w["to"], now) - w["from"]) // 60)
    return out


def present_at(t, wins: list) -> bool:
    return any(w["from"] <= t < w["to"] for w in wins)


def status(now=None, path: str = PATH, cfg: dict | None = None) -> dict:
    """{"present", "since", "until", "last_t", "last_src", "line", "guard", "hours"} for the dashboards."""
    now = int(time.time() if now is None else now)
    cfg = cfg or {}
    evs = events(path)
    wins = windows(evs, now)
    cur = next((w for w in reversed(wins) if w["open"]), None)
    last = next((r for r in reversed(evs) if r["kind"] == "in" and r["t"] <= now), None)
    if cur:
        line = f"Present since {_hm(cur['from'])} ET (until {_hm(cur['to'])} ET)"
    elif last:
        line = f"Not checked in (last check-in {_dhm(last['t'])} ET from the {last.get('src') or 'pc'})"
    else:
        line = "Not checked in yet"
    return {"present": bool(cur), "since": cur["from"] if cur else None, "until": cur["to"] if cur else None,
            "last_t": last["t"] if last else None, "last_src": (last or {}).get("src"), "line": line,
            "guard": bool(cfg.get("presence_required")), "hours": _hours(cfg.get("presence_hours"))}


# ---------------------------------------------------------------------------------------------- the guard (OFF by default)
def problem(c: dict, now, path: str = PATH) -> str | None:
    """guards.entry_problems: a reason when presence_required is on and nobody checked in within presence_hours."""
    if not c.get("presence_required"):
        return None
    now = int(now)
    h = _hours(c.get("presence_hours"))
    wins = windows(events(path), now)
    if present_at(now, wins):
        return None
    last = max((w["from"] for w in wins), default=None)
    return (f"no check-in in the last {h:g} h (presence_required is on; tap I'm here on the Bot page or the phone's Remote "
            f"page){'' if last is None else f'; last check-in {_dhm(last)} ET'}")


def tick(bot, c: dict, now) -> bool:
    """guards.tick: the 'Check in to keep trading' push while the guard is on and nobody is checked in (weekdays from
    01:40 ET to the 15:30 entry cutoff), once per trading day and last check-in. Returns True when it pushed."""
    if not c.get("presence_required") or not getattr(bot, "running", False):
        return False
    now = int(now)
    e = _et(now)
    mod = e.hour * 60 + e.minute
    if e.weekday() >= 5 or not (REMIND_FROM <= mod < REMIND_TO):
        return False
    p = path_for(bot)
    wins = windows(events(p), now)
    if present_at(now, wins):
        return False
    last = max((w["from"] for w in wins), default=0)
    key = f"presence:{trading_day(now)}:{last}"
    if getattr(bot, "_presence_pushed", None) == key:
        return False
    bot._presence_pushed = key
    body = (f"presence_required is on: no new entry until you tap I'm here (Bot page or phone Remote page). "
            f"{'Last check-in ' + _dhm(last) + ' ET.' if last else 'No check-in yet.'} Open trades keep their stop and target.")
    try:
        bot._log("risk", f"PRESENCE: {body}")
    except Exception:
        pass
    try:
        from . import push
        pl = push.text_payload("PC", "ops", "Check in to keep trading", body, key=key, t=now, url="#/remote")
        pl["tag"] = "le-presence"
        bot._push_send(pl)
    except Exception:
        pass
    return True


# ---------------------------------------------------------------------------------------------- the presence log page
def _ledger_rows(bot=None, ledger_path: str | None = None) -> list:
    rows = []
    if ledger_path is None:
        ledger_path = os.path.join(ROOT, "logs", "exec_audit", "ledger.jsonl")     # engine/fill_audit.collect copies
    try:
        with open(ledger_path, encoding="utf-8") as fh:
            for ln in fh:
                try:
                    r = json.loads(ln)
                except Exception:
                    continue
                if isinstance(r, dict):
                    rows.append(r)
    except FileNotFoundError:
        pass
    rows += list(getattr(bot, "ledger", None) or [])
    return rows


def bot_trades(rows: list) -> list:
    """The bot's routed trades from ledger rows: [{"entry_t", "exit_t", "side", "qty", "reason"}] (no duplicates)."""
    tr = {}
    for r in rows:
        et_ = r.get("entry_t")
        if not et_:
            continue
        k = int(et_)
        if r.get("side") in ("buy", "sell") and (r.get("result") or {}).get("ok", True) is not False:
            d = tr.setdefault(k, {"entry_t": k, "exit_t": None, "side": "LONG" if r["side"] == "buy" else "SHORT",
                                  "qty": r.get("qty"), "reason": None})
            d["routed_t"] = int(r.get("t") or k)
        elif r.get("side") == "exit" and k in tr:
            tr[k]["exit_t"] = int(r.get("t") or 0) or None
            tr[k]["reason"] = r.get("reason")
    return [v for k, v in sorted(tr.items()) if v.get("reason") != "NO TRADE"]


def log_view(now=None, days: int = 14, path: str = PATH, bot=None, ledger_path: str | None = None, cfg: dict | None = None) -> dict:
    now = int(time.time() if now is None else now)
    since = now - days * 86400
    wins = windows(events(path), now)
    trades = []
    for t in bot_trades(_ledger_rows(bot, ledger_path)):
        if t["entry_t"] < since:
            continue
        end = t["exit_t"] or min(now, t["entry_t"] + 3600)
        ov = sum(max(0, min(end, w["to"]) - max(t["entry_t"], w["from"])) for w in wins)
        trades.append({**t, "day": trading_day(t["entry_t"]), "time": f"{_dhm(t['entry_t'])} ET",
                       "present": present_at(t["entry_t"], wins), "overlap_min": int(ov // 60),
                       "trade_min": int(max(0, end - t["entry_t"]) // 60)})
    ws = [{**w, "label": f"{_dhm(w['from'])}-{_hm(min(w['to'], now))} ET", "day": trading_day(w["from"])}
          for w in wins if w["to"] >= since]
    n_p = sum(1 for t in trades if t["present"])
    return {"t": now, "days": days, "status": status(now, path, cfg), "windows": ws[::-1], "trades": trades[::-1],
            "summary": {"trades": len(trades), "present_for": n_p, "absent_for": len(trades) - n_p,
                        "present_h": round(sum(w["minutes"] for w in ws) / 60.0, 1),
                        "line": (f"present for {n_p} of {len(trades)} trades" if trades else "no bot trades in this period")}}


def compact(now=None, path: str = PATH, cfg: dict | None = None) -> dict:
    """The heartbeat / live.json block (via engine/remote_ctl.hb_field): small."""
    s = status(now, path, cfg)
    return {k: s[k] for k in ("present", "since", "until", "last_t", "line", "guard")}
