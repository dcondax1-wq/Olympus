"""Read-only API for the PC dashboard's operator tools (web_next/js/next/pcops.js, pulse.js, keys.js): the live pulse behind
the sound / desktop alerts and the tab badge, the live chart with the LIT levels, the bot log viewer, the NinjaTrader panel,
the session timeline, the live settings explained and the morning report.

Mounted by engine/next_api.py (router.include_router), so server.py needs no change. Every route is a GET and only READS:
the bot (engine/live.BOT through pcdash_api._bot: cfg, state, ledger, log, health, bars, adapter), the logs/ folder (fixed
file name patterns only), Documents\\NinjaTrader 8 (engine/botctl.folder_probe / feed_probe) and live_model.json. Nothing
here starts, arms, routes, kills or changes anything; no response carries the confirm phrase, a webhook URL or a file path.

  GET /api/next/pc/pulse               light poll (every ~5 s): running / kill / feed stale / position + unrealized $ / today's
                                       P&L, and today's events (entry, exit, kill, feed stale, feed back) with stable ids
  GET /api/next/pc/chart?tf=5m|1m      today's bars (the bot's feed, else the last session of data/NQ_5m.csv / NQ_1m.csv), the
                                       LIT levels the bot watches (engine/botctl.plan_view = engine/lit_brief), swept levels,
                                       armed limits, the open trade's entry / stop / target / BE lines, killzones
  GET /api/next/pc/logs                today's bot log (memory) + logs/server-*.log + logs/ninjatrader_oif.log + logs/update-*.log
                                       + logs/ops-*.log, each row tagged orders / signals / errors / system; ?cat= ?q= ?day=
  GET /api/next/pc/nt                  NinjaTrader panel: connection, bar ages (bot + LE_BarFeed files), last OIF files sent /
                                       reports received, account positions, the bot's open brackets; every red row has its fix
  GET /api/next/pc/timeline            today 18:00 -> 17:00 ET: killzones, entry window, news, signals, entries / exits,
                                       restarts, updates, feed problems
  GET /api/next/pc/settings            live_model.json switches in plain words with their tested numbers and the file to edit
  GET /api/next/pc/morning             what happened overnight (16:00 ET yesterday -> now): trades, alerts, feed gaps,
                                       restarts, errors, plus today's news and the bot's state now
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import time
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from fastapi.responses import Response

from . import accounts

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS = os.path.join(ROOT, "logs")
PV = 2.0
router = APIRouter()
_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_URL = re.compile(r"https?://\S+", re.I)
_TOK = re.compile(r"(?i)\b(token|secret|key|password|passwd|webhook|chat_id|bot\d{6,})\b\s*[=:]\s*\S+")
_ACCESS = re.compile(r'"(GET|POST|HEAD|PUT|DELETE|OPTIONS) /')
TAIL_BYTES = 1_500_000


def _J(obj, status=200):
    return Response(json.dumps(obj, separators=(",", ":"), default=str), media_type="application/json", status_code=status)


def _err(e):
    return _J({"error": f"{e.__class__.__name__}: {accounts.clean_text(e, 120)}"}, 500)


def _bot():
    from . import pcdash_api
    return pcdash_api._bot()


def _now(bot) -> int:
    try:
        return int(bot.clock())
    except Exception:
        return int(time.time())


def _lm() -> dict:
    try:
        with open(os.path.join(ROOT, "live_model.json"), encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def safe(text, n=400):
    """One log line for the page: file paths, URLs and anything that looks like a credential or the confirm phrase removed."""
    if text is None:
        return None
    s = accounts.clean_text(text, 2000) or ""
    s = _URL.sub("<url>", s)
    s = _TOK.sub(lambda m: m.group(1) + "=<hidden>", s)
    try:
        from .botctl import REDACT, _phrase
        ph = _phrase()
        if ph and ph in s:
            s = s.replace(ph, REDACT)
    except Exception:
        pass
    return s[:n]


def _et(t):
    return dt.datetime.fromtimestamp(int(t), ET)


def session_bounds(now: int):
    """(t0, t1, day): the LIT trading day containing `now`, 18:00 ET of the day before -> 17:00 ET."""
    day = accounts.trading_day(now)
    d = dt.date.fromisoformat(day)
    p = d - dt.timedelta(days=1)
    t0 = int(dt.datetime(p.year, p.month, p.day, 18, 0, tzinfo=ET).timestamp())
    t1 = int(dt.datetime(d.year, d.month, d.day, 17, 0, tzinfo=ET).timestamp())
    return t0, t1, day


def _ledger(bot):
    return [r for r in list(getattr(bot, "ledger", None) or []) if isinstance(r, dict) and r.get("t")]


def _today(rows, day):
    return [r for r in rows if r.get("t") and accounts.trading_day(r["t"]) == day]


# ------------------------------------------------------------------------------------------------ 1-3: pulse
def _position(bot, now):
    st = getattr(bot, "state", None) or {}
    try:
        acct = accounts.pc_activity(bot, now=now, max_trades=5, max_orders=5)
        pos = acct.get("position")
    except Exception:
        pos = None
    if not pos:
        p = st.get("position")
        if not isinstance(p, dict) or not p.get("entry"):
            return None
        d = int(p.get("dir") or 1)
        pos = {"side": "LONG" if d > 0 else "SHORT", "dir": d, "qty": p.get("qty"), "entry": p.get("entry"), "stop": p.get("stop"),
               "stop0": p.get("stop0") or p.get("stop"), "target": p.get("target"), "entry_t": p.get("entry_t"), "paper": True}
    try:
        from .pcdash_api import _position_view
        return _position_view(bot, pos, now)
    except Exception:
        return pos


def events_today(bot, now) -> list:
    """Today's alert-worthy events with stable ids (the page sounds / notifies each id once)."""
    t0, t1, day = session_bounds(now)
    out = []
    for r in _today(_ledger(bot), day):
        side, res = r.get("side"), (r.get("result") or {})
        if side in ("buy", "sell"):
            legs = res.get("legs") or [{}]
            px = (legs[0] or {}).get("fill_px") or r.get("entry")
            out.append({"id": f"entry:{r.get('entry_t') or r['t']}", "t": int(r["t"]), "kind": "entry",
                        "title": f"ENTRY {'LONG' if side == 'buy' else 'SHORT'} {r.get('qty')} MNQ",
                        "text": safe(f"@ {accounts._f(px)} · stop {accounts._f(r.get('stop'))} · target {accounts._f(r.get('target'))}"
                                     + ("" if res.get("ok", True) else f" · NOT confirmed: {res.get('error')}"), 200)})
        elif side == "exit":
            pnl = r.get("pnl")
            out.append({"id": f"exit:{r.get('entry_t') or ''}:{r['t']}", "t": int(r["t"]), "kind": "exit",
                        "title": f"EXIT {r.get('reason') or ''}".strip() + (f" {'+' if (pnl or 0) >= 0 else '-'}${abs(float(pnl)):,.0f}" if pnl is not None else ""),
                        "text": safe(f"{r.get('qty') or ''} micros closed" + (f" · {res.get('error')}" if res.get("error") else ""), 200),
                        "pnl": accounts._f(pnl)})
    for r in list(getattr(bot, "log", None) or []):
        t = r.get("t")
        if not t or not (t0 <= int(t) <= t1):
            continue
        txt = str(r.get("text") or "")
        up = txt.upper()
        if "KILL SWITCH" in up and "restored" not in txt.lower():
            out.append({"id": f"kill:{int(t)}", "t": int(t), "kind": "kill", "title": "KILL SWITCH", "text": safe(txt, 200)})
        elif "FEED STALE" in up:
            out.append({"id": f"stale:{int(t)}", "t": int(t), "kind": "stale", "title": "FEED STALE: entries blocked", "text": safe(txt, 200)})
        elif re.search(r"feed (is )?(back|fresh|ok)|bars (are )?back", txt, re.I):
            out.append({"id": f"fresh:{int(t)}", "t": int(t), "kind": "fresh", "title": "Feed back", "text": safe(txt, 200)})
    if getattr(bot, "kill", False) and not any(e["kind"] == "kill" for e in out):
        out.append({"id": f"kill:{day}", "t": now, "kind": "kill", "title": "KILL SWITCH is on", "text": "no orders until tomorrow's session"})
    seen, uniq = set(), []
    for e in sorted(out, key=lambda e: e["t"]):
        if e["id"] not in seen:
            seen.add(e["id"])
            uniq.append(e)
    return uniq[-60:]


def pulse_view(bot, now: int | None = None) -> dict:
    now = int(now or _now(bot))
    h = accounts.pc_health(bot, now)
    f = h.get("feed") or {}
    pos = _position(bot, now)
    led = _today(_ledger(bot), accounts.trading_day(now))
    realized = round(sum(float(r.get("pnl") or 0) for r in led if r.get("side") == "exit"), 2)
    unreal = (pos or {}).get("unrealized_usd")
    stale = bool(f.get("stale") or f.get("entries_blocked") or f.get("block") or f.get("nt_down"))
    from .live import market_open
    pv = None
    if pos:
        pv = {k: pos.get(k) for k in ("side", "qty", "entry", "stop", "target", "price", "unrealized_usd", "unrealized_r_now", "entry_t")}
    return {"t": now, "running": bool(getattr(bot, "running", False)), "kill": bool(getattr(bot, "kill", False)),
            "account": (h.get("account") or {}).get("label"), "market_open": market_open(now),
            "feed": {"stale": stale and market_open(now), "age_1m_s": f.get("age_1m_s"), "age_5m_s": f.get("age_5m_s"),
                     "why": safe(f.get("block") or f.get("nt_down"), 160)},
            "position": pv, "realized": realized, "unrealized": unreal,
            "day_pnl": round(realized + float(unreal or 0), 2), "price": accounts._f((getattr(bot, "state", None) or {}).get("price")),
            "events": events_today(bot, now)}


@router.get("/api/next/pc/pulse")
def r_pulse():
    try:
        return _J(pulse_view(_bot()))
    except Exception as e:
        return _err(e)


# ------------------------------------------------------------------------------------------------ 4: live chart
def chart_view(bot, tf: str = "5m", now: int | None = None, plan: dict | None = None) -> dict:
    from . import botctl, pcdash_api
    now = int(now or _now(bot))
    tf = "1m" if tf == "1m" else "5m"
    t0, t1, day = session_bounds(now)
    b5, b1 = pcdash_api.bot_bars(bot, t0)
    bars, src = (b1 if tf == "1m" else b5), "the bot's NinjaTrader feed"
    if not bars:                                  # bot not running / no feed yet: the last session in data/NQ_<tf>.csv
        df = pcdash_api._csv("NQ", tf)
        if df is not None and len(df):
            last = int(df["time"].iloc[-1])
            lt0, lt1, lday = session_bounds(min(now, last))
            sub = df[(df["time"] >= lt0) & (df["time"] <= lt1)]
            bars = pcdash_api._rows_from_frame(sub)
            src, day, t0, t1 = f"data/NQ_{tf}.csv (last session {lday}: the bot has no bars yet)", lday, lt0, lt1
    bars = bars[-(720 if tf == "1m" else 300):]
    if plan is None:
        try:
            plan = botctl.plan_view(bot, now)
        except Exception as e:
            plan = {"error": accounts.clean_text(f"{e.__class__.__name__}: {e}", 120)}
    levels = []
    for lv in (plan.get("watched") or []):
        levels.append({"label": lv.get("label"), "price": accounts._f(lv.get("price")), "side": lv.get("side"), "kind": lv.get("kind"),
                       "taken": False})
    for lv in (plan.get("swept") or []):
        levels.append({"label": lv.get("label"), "price": accounts._f(lv.get("price")), "side": lv.get("side"), "kind": lv.get("kind"),
                       "taken": True, "taken_t": accounts._i(lv.get("taken_t")), "depth_atr": lv.get("depth_atr")})
    lines = []
    pos = _position(bot, now)
    if pos:
        lines += [{"id": "entry", "label": f"Entry {pos.get('side')} {pos.get('qty')}", "price": accounts._f(pos.get("entry"))},
                  {"id": "stop", "label": "Stop", "price": accounts._f(pos.get("stop"))},
                  {"id": "target", "label": "Target" + (f" ({pos.get('target_label')})" if pos.get("target_label") else ""),
                   "price": accounts._f(pos.get("target"))}]
        if pos.get("be_trigger") is not None and pos.get("stop") != pos.get("entry"):
            lines.append({"id": "be", "label": "BE trigger (+1R)", "price": accounts._f(pos.get("be_trigger"))})
    for s in (plan.get("armed") or []):
        lines.append({"id": "limit", "label": f"Armed {s.get('side')} limit", "price": accounts._f(s.get("limit")), "t1": s.get("expires_t")})
    marks = []
    for r in _today(_ledger(bot), accounts.trading_day(now)):
        if r.get("side") in ("buy", "sell", "exit"):
            res = r.get("result") or {}
            px = ((res.get("legs") or [{}])[0] or {}).get("fill_px") or r.get("entry") or r.get("exit_px") or r.get("price")
            marks.append({"t": int(r["t"]), "kind": "entry" if r["side"] != "exit" else "exit", "side": r["side"],
                          "price": accounts._f(px), "pnl": accounts._f(r.get("pnl")), "qty": r.get("qty")})
    return {"t": now, "day": day, "tf": tf, "t0": t0, "t1": t1, "bars": bars, "source": src, "levels": levels, "lines": lines,
            "marks": marks, "price": accounts._f((getattr(bot, "state", None) or {}).get("price")) or (bars[-1][4] if bars else None),
            "killzones": botctl.KILLZONES, "plan_error": plan.get("error"), "plan_day": plan.get("day"),
            "model_state": safe((getattr(bot, "state", None) or {}).get("model_state"), 200)}


@router.get("/api/next/pc/chart")
def r_chart(tf: str = "5m"):
    try:
        return _J(chart_view(_bot(), tf))
    except Exception as e:
        return _err(e)


# ------------------------------------------------------------------------------------------------ 5: log viewer
CATS = ("orders", "signals", "errors", "system")
_RX_ERR = re.compile(r"error|traceback|exception|failed|rejected|refused|not routed|stale|kill|crash|\bwarn", re.I)
_RX_ORD = re.compile(r"\boif\b|order|bracket|place;|change;|cancel|flatten|fill|filled|routed|position", re.I)
_RX_SIG = re.compile(r"signal|setup|sweep|swept|cisd|inducement|displacement|limit|tapped|entry|exit|target|\blit\b|breakeven|\bbe\b", re.I)


def categorize(kind, text, src="bot") -> str:
    k = str(kind or "").lower()
    if k in ("error", "warn", "kill") or (k in ("risk", "") and _RX_ERR.search(text or "")) or (src != "oif" and _RX_ERR.search(text or "")):
        return "errors"
    if src == "oif" or k in ("order", "broker") or _RX_ORD.search(text or ""):
        return "orders"
    if k in ("signal", "sweep", "entry", "exit", "skip", "risk") or _RX_SIG.search(text or ""):
        return "signals"
    return "system"


def _tail_lines(path, nbytes=TAIL_BYTES):
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as fh:
            if size > nbytes:
                fh.seek(size - nbytes)
                fh.readline()
            data = fh.read()
    except OSError:
        return []
    return data.decode("utf-8", errors="replace").splitlines()


_TS = re.compile(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}):(\d{2}):(\d{2})")


def _parse_t(line, tz=ET):
    m = _TS.search(line[:60])
    if not m:
        return None
    try:
        d = dt.date.fromisoformat(m.group(1))
        return int(dt.datetime(d.year, d.month, d.day, int(m.group(2)), int(m.group(3)), int(m.group(4)), tzinfo=tz).timestamp())
    except ValueError:
        return None


def file_rows(day: str, logs_dir: str | None = None) -> tuple[list, dict]:
    """Rows from logs/ for LIT trading day `day` (18:00 ET the day before -> 17:00): server, update and ops logs of both
    calendar days, and the NinjaTrader OIF audit. Fixed file names only; uvicorn access lines are counted, not listed."""
    logs_dir = logs_dir or LOGS
    d = dt.date.fromisoformat(day)
    p = d - dt.timedelta(days=1)
    t0 = int(dt.datetime(p.year, p.month, p.day, 18, 0, tzinfo=ET).timestamp())
    t1 = int(dt.datetime(d.year, d.month, d.day, 17, 0, tzinfo=ET).timestamp())
    rows, info = [], {"files": [], "access_lines": 0}
    for cal in (p, d):
        stamp = cal.strftime("%Y%m%d")
        for pre, src in (("server", "server"), ("update", "update"), ("ops", "ops")):
            path = os.path.join(logs_dir, f"{pre}-{stamp}.log")
            if not os.path.exists(path):
                continue
            info["files"].append(os.path.basename(path))
            last_t = int(dt.datetime(cal.year, cal.month, cal.day, 0, 0, tzinfo=ET).timestamp())
            for ln in _tail_lines(path):
                if not ln.strip():
                    continue
                if _ACCESS.search(ln):
                    info["access_lines"] += 1
                    continue
                t = _parse_t(ln)
                if t is None:
                    t = last_t
                else:
                    last_t = t
                if not (t0 <= t <= t1):
                    continue
                txt = safe(ln.strip(), 400)
                kind = "supervisor" if "[supervisor]" in ln else ("error" if re.search(r"traceback|error", ln, re.I) else src)
                rows.append({"t": t, "src": src, "type": kind, "text": txt, "cat": categorize(kind if kind == "error" else "", txt, src)})
    oif = os.path.join(logs_dir, "ninjatrader_oif.log")
    if os.path.exists(oif):
        info["files"].append("ninjatrader_oif.log")
        for ln in _tail_lines(oif, 600_000):
            t = _parse_t(ln)
            if t is None or not (t0 <= t <= t1):
                continue
            rows.append({"t": t, "src": "oif", "type": "oif", "text": safe(ln.strip(), 400), "cat": "orders"})
    return rows, info


def logs_view(bot, cat: str = "", q: str = "", day: str = "", limit: int = 800, now: int | None = None, logs_dir=None) -> dict:
    now = int(now or _now(bot))
    day = day if (day and _DAY.match(day)) else accounts.trading_day(now)
    d = dt.date.fromisoformat(day)
    p = d - dt.timedelta(days=1)
    t0 = int(dt.datetime(p.year, p.month, p.day, 18, 0, tzinfo=ET).timestamp())
    t1 = int(dt.datetime(d.year, d.month, d.day, 17, 0, tzinfo=ET).timestamp())
    rows = []
    for r in list(getattr(bot, "log", None) or []):
        t = r.get("t")
        if not t or not (t0 <= int(t) <= t1):
            continue
        txt = safe(r.get("text"), 400)
        rows.append({"t": int(t), "src": "bot", "type": r.get("type"), "text": txt, "cat": categorize(r.get("type"), txt)})
    for r in _today(_ledger(bot), day):
        res = r.get("result") or {}
        txt = f"ledger: {r.get('side')} {r.get('qty') or ''}" + (f" stop {r['stop']}" if r.get("stop") is not None else "") + \
              (f" target {r['target']}" if r.get("target") is not None else "") + (f" {r.get('reason')}" if r.get("reason") else "") + \
              (f" pnl {r['pnl']:+.2f}" if isinstance(r.get("pnl"), (int, float)) else "") + \
              ("" if res.get("ok", True) else f" | REFUSED: {res.get('error')}")
        rows.append({"t": int(r["t"]), "src": "ledger", "type": "order", "text": safe(txt, 400),
                     "cat": "errors" if res.get("ok") is False else "orders"})
    frows, info = file_rows(day, logs_dir)
    rows += frows
    counts = {c: 0 for c in CATS}
    for r in rows:
        counts[r["cat"]] = counts.get(r["cat"], 0) + 1
    cat = cat if cat in CATS else ""
    ql = (q or "").strip().lower()[:80]
    sel = [r for r in rows if (not cat or r["cat"] == cat) and (not ql or ql in (r["text"] or "").lower())]
    sel.sort(key=lambda r: -r["t"])
    lim = max(1, min(int(limit or 800), 3000))
    return {"t": now, "day": day, "cat": cat or "all", "q": ql, "counts": counts, "total": len(rows), "matched": len(sel),
            "rows": sel[:lim], "files": info["files"], "access_lines": info["access_lines"],
            "sources": {"bot": "the bot's in-memory log (last 400 rows)", "ledger": "order ledger", "server": "logs/server-YYYYMMDD.log",
                        "oif": "logs/ninjatrader_oif.log (every order line written)", "update": "logs/update-YYYYMMDD.log",
                        "ops": "logs/ops-YYYYMMDD.log"}}


@router.get("/api/next/pc/logs")
def r_logs(cat: str = "", q: str = "", day: str = "", limit: int = 800):
    try:
        return _J(logs_view(_bot(), cat, q, day, limit))
    except Exception as e:
        return _err(e)


# ------------------------------------------------------------------------------------------------ 6: NinjaTrader panel
def _row(rid, label, ok, detail="", fix=""):
    return {"id": rid, "label": label, "ok": ok, "detail": safe(detail, 220) if detail else "", "fix": safe(fix, 260) if fix else ""}


def _ago(s):
    from .botctl import _ago as a
    return a(s)


def _oif_sent(n=10, logs_dir=None) -> list:
    """The last OIF files written (logs/ninjatrader_oif.log: '<ET stamp> ET  <account>  <file>  <line>'), one row per file."""
    path = os.path.join(logs_dir or LOGS, "ninjatrader_oif.log")
    files = {}
    for ln in _tail_lines(path, 300_000):
        parts = re.split(r"\s{2,}", ln.strip(), maxsplit=3)
        if len(parts) < 4:
            continue
        t = _parse_t(parts[0])
        name = parts[2]
        r = files.setdefault(name, {"t": t, "file": safe(name, 60), "account": safe(parts[1], 40), "lines": []})
        r["lines"].append(safe(parts[3], 160))
        r["t"] = t or r["t"]
    rows = sorted(files.values(), key=lambda r: -(r["t"] or 0))[:n]
    for r in rows:
        first = (r["lines"] or [""])[0].split(";")[0].upper()
        r["action"] = first or "?"
    return rows


def _outgoing(folder, n=12) -> list:
    out = os.path.join(folder, "outgoing")
    rows = []
    try:
        names = os.listdir(out)
    except OSError:
        return rows
    for nm in names:
        if not nm.lower().endswith(".txt"):
            continue
        p = os.path.join(out, nm)
        try:
            mt = int(os.path.getmtime(p))
            with open(p, encoding="utf-8", errors="replace") as fh:
                raw = fh.read(120).strip()
        except OSError:
            continue
        kind = "position" if nm.lower().endswith("_position.txt") else ("connection" if raw.upper() in ("CONNECTED", "DISCONNECTED") else "order")
        rows.append({"t": mt, "file": safe(nm, 80), "kind": kind, "content": safe(raw, 100)})
    rows.sort(key=lambda r: -r["t"])
    return rows[:n]


def nt_view(bot, now: int | None = None, folder: str | None = None, logs_dir=None) -> dict:
    from . import botctl
    from .live import market_open
    now = int(now or _now(bot))
    wall = int(time.time())
    folder = folder or botctl.nt_folder(bot)
    probe = botctl.folder_probe(folder, wall)
    feed = botctl.feed_probe(folder, wall)
    h = accounts.pc_health(bot, now)
    hf, ha = h.get("feed") or {}, h.get("account") or {}
    mopen = market_open(now)
    ad = getattr(bot, "adapter", None)
    is_nt = getattr(ad, "name", None) == "ninjatrader" or (getattr(bot, "cfg", None) or {}).get("adapter") == "ninjatrader"
    rows = []
    rows.append(_row("folder", "NinjaTrader folder", probe["exists"], "Documents\\NinjaTrader 8 found" if probe["exists"] else "not found",
                     "" if probe["exists"] else "Open NinjaTrader 8 once on this Windows user (it creates Documents\\NinjaTrader 8), "
                     "or set NINJATRADER_FOLDER / nt_folder if Documents is elsewhere."))
    ati = probe["incoming"] and probe["outgoing"]
    stuck = bool(probe["leftovers"]) and (probe["oldest_leftover_s"] or 0) > 30
    rows.append(_row("ati", "AT Interface (order files picked up)", bool(ati and not stuck),
                     ("incoming + outgoing found" if ati else f"incoming {'ok' if probe['incoming'] else 'MISSING'}, outgoing {'ok' if probe['outgoing'] else 'MISSING'}")
                     + (f"; {probe['leftovers']} order file(s) waiting for {_ago(probe['oldest_leftover_s'])}" if probe["leftovers"] else ""),
                     "" if ati and not stuck else
                     ("NinjaTrader is not reading the order files: keep NinjaTrader open and turn on Tools > Options > Automated trading "
                      "interface > AT Interface. The bot withdraws files that wait too long, so nothing runs late." if stuck else
                      "In NinjaTrader: Tools > Options > Automated trading interface > tick 'AT Interface', then restart NinjaTrader.")))
    conns = probe["connections"]
    up = [k for k, v in conns.items() if v == "CONNECTED"]
    rows.append(_row("connection", "Connection", bool(up), ", ".join(f"{k} {v}" for k, v in conns.items()) or "no connection file yet",
                     "" if up else "In NinjaTrader's Control Center: Connections > connect your MFFU / Tradovate login (Sim101 needs the "
                     "Simulated Data Feed or your data connection). The file appears once a connection changes state."))
    for tf, lim in (("5m", 420), ("1m", 180)):
        fb = feed.get(tf) or {}
        age = fb.get("age_s")
        if not fb.get("ok"):
            ok, det = False, fb.get("why") or "no LE_BarFeed file"
        else:
            ok = True if age is not None and age <= lim else (False if mopen else None)
            det = f"last bar {_ago(age)} old" + ("" if mopen else " (market closed)")
        rows.append(_row(f"feed{tf}", f"LE_BarFeed MNQ {tf} file", ok, det, "" if ok else
                         f"Open an MNQ {'5-minute' if tf == '5m' else '1-minute'} chart in NinjaTrader with the LE_BarFeed indicator on it "
                         "(ninjatrader/SETUP.md), load at least 30 days and leave it open. A stale feed blocks new entries (FEED STALE)."))
    for tf in ("5m", "1m"):
        age = hf.get(f"age_{tf}_s")
        lim = 420 if tf == "5m" else 180
        if not getattr(bot, "running", False):
            ok, det = None, "the bot is stopped"
        elif age is None:
            ok, det = (False if mopen else None), "no bar read yet"
        else:
            ok = True if age <= lim else (False if mopen else None)
            det = f"last {tf} bar the bot read is {_ago(age)} old"
        rows.append(_row(f"bot{tf}", f"Bot reads the {tf} bars", ok, det, "" if ok is not False else
                         "The bot is not getting fresh bars: check the LE_BarFeed rows above; if they are green, press Stop then Start on "
                         "Bot Control (it re-reads the feed folder)."))
    if is_nt:
        dis = ha.get("disabled")
        rows.append(_row("adapter", "Bot can send orders", dis is None and not getattr(bot, "kill", False),
                         "kill switch used today" if getattr(bot, "kill", False) else (dis or f"account {ha.get('name')} ({ha.get('label')})"),
                         "" if dis is None and not getattr(bot, "kill", False) else
                         ("The kill switch was used today: the bot sends nothing until tomorrow's session." if getattr(bot, "kill", False) else
                          "Fix the reason shown, then Stop and Start the bot on Bot Control.")))
        le = getattr(ad, "last_error", None)
        rows.append(_row("last_error", "Last NinjaTrader error", None if le else True, le or "none",
                         "Read the error; most are fixed by the AT Interface or the connection rows above. Check NinjaTrader's Orders tab."
                         if le else ""))
    # positions: NinjaTrader's files vs the bot's open bracket
    nt_pos = []
    out = os.path.join(folder, "outgoing")
    for p in probe["positions"]:
        raw = None
        try:
            fn = [n for n in os.listdir(out) if n.lower().endswith("_position.txt") and n[:-len("_position.txt")].endswith("_" + p["account"])
                  and n.startswith(p["instrument"])]
            if fn:
                with open(os.path.join(out, fn[0]), encoding="utf-8", errors="replace") as fh:
                    raw = fh.read(80).strip()
        except OSError:
            pass
        parts = (raw or "").split(";")
        side = parts[0].upper() if parts else ""
        qty = accounts._i(parts[1]) if len(parts) > 1 else None
        nt_pos.append({"instrument": p["instrument"], "account": p["account"], "side": side or "?", "qty": qty,
                       "avg": accounts._f(parts[2]) if len(parts) > 2 else None})
    legs = []
    for lg in (getattr(ad, "legs", None) or []) if is_nt else []:
        legs.append({k: lg.get(k) for k in ("instrument", "status", "filled", "fill_px", "stop", "target", "dir", "entry_t")})
    acct = ha.get("name")
    open_nt = [p for p in nt_pos if p["side"] not in ("FLAT", "?", "") and (not acct or p["account"] == acct)]
    bot_pos = _position(bot, now)
    if is_nt or nt_pos:
        same = bool(open_nt) == bool(bot_pos or legs)
        rows.append(_row("positions", "NinjaTrader position = the bot's", True if same else False,
                         (", ".join(f"{p['instrument']} {p['side']} {p['qty']}" for p in open_nt) or "NinjaTrader flat")
                         + " · bot " + (f"{bot_pos.get('side')} {bot_pos.get('qty')}" if bot_pos else "flat"),
                         "" if same else "They disagree: look at NinjaTrader's Positions tab. If NinjaTrader holds a position the bot does not "
                         "know, flatten it there by hand (or HOLD TO KILL on Bot Control); if the bot shows one NinjaTrader does not, "
                         "Stop and Start the bot so it re-reads the outgoing files."))
    red = [r for r in rows if r["ok"] is False]
    return {"t": now, "folder_found": probe["exists"], "rows": rows, "red": len(red), "ok": not red, "market_open": mopen,
            "connections": conns, "leftovers": probe["leftovers"], "positions": nt_pos, "legs": legs,
            "bars": {"bot_5m_age_s": hf.get("age_5m_s"), "bot_1m_age_s": hf.get("age_1m_s"),
                     "file_5m_age_s": (feed.get("5m") or {}).get("age_s"), "file_1m_age_s": (feed.get("1m") or {}).get("age_s")},
            "sent": _oif_sent(logs_dir=logs_dir), "received": _outgoing(folder),
            "account": {"name": ha.get("name"), "label": ha.get("label"), "adapter": ha.get("adapter")}}


@router.get("/api/next/pc/nt")
def r_nt():
    try:
        return _J(nt_view(_bot()))
    except Exception as e:
        return _err(e)


# ------------------------------------------------------------------------------------------------ 7: session timeline
def timeline_view(bot, now: int | None = None) -> dict:
    from . import botctl
    now = int(now or _now(bot))
    t0, t1, day = session_bounds(now)
    d = dt.date.fromisoformat(day)

    def at(mod):
        return int(dt.datetime(d.year, d.month, d.day, mod // 60, mod % 60, tzinfo=ET).timestamp())
    bands = [{"id": z["id"], "label": z["label"], "t0": at(z["from"]), "t1": at(z["to"]), "kind": "killzone"} for z in botctl.KILLZONES]
    bands.append({"id": "window", "label": "LIT entry window 02:00-15:30", "t0": at(120), "t1": at(930), "kind": "window"})
    bands.append({"id": "halt", "label": "Flat 15:55 · halt 17:00", "t0": at(955), "t1": t1, "kind": "close"})
    ev = []
    for e in events_today(bot, now):
        ev.append({"t": e["t"], "kind": e["kind"], "text": e["title"] + (" · " + e["text"] if e.get("text") else "")})
    st = getattr(bot, "state", None) or {}
    for s in ((st.get("lit") or {}).get("signals_today") or []):
        if isinstance(s, dict) and s.get("t"):
            row = accounts._signal_row(s)
            ev.append({"t": int(s["t"]), "kind": "signal", "text": safe(f"setup {row.get('side')} · {row.get('level') or ''} · limit "
                                                                         f"{accounts._f(s.get('limit_px'))}", 200)})
    have = {e["t"] for e in ev}
    try:
        for r in botctl.health_timeline(bot, now, n=80):
            if t0 <= r["t"] <= t1 and r["kind"] in ("start", "update", "feed", "error", "kill"):
                if r["t"] in have and r["kind"] in ("feed", "kill", "error"):
                    continue
                ev.append({"t": r["t"], "kind": {"start": "restart"}.get(r["kind"], r["kind"]), "text": safe(r["text"], 200)})
    except Exception:
        pass
    news = []
    try:
        nv = botctl.news_view(now)
        for x in nv.get("events") or []:
            t = accounts._i(x.get("t"))
            if t is None and x.get("time"):
                try:
                    hh, mm = str(x["time"]).split(":")[:2]
                    t = at(int(hh) * 60 + int(mm))
                except Exception:
                    t = None
            if t is not None:
                news.append({"t": t, "title": safe(x.get("title"), 80), "tier1": bool(x.get("tier1")), "impact": x.get("impact")})
    except Exception:
        pass
    seen, uniq = set(), []
    for e in sorted(ev, key=lambda e: e["t"]):
        k = (e["t"], e["kind"], e["text"])
        if k not in seen:
            seen.add(k)
            uniq.append(e)
    return {"t": now, "day": day, "t0": t0, "t1": t1, "bands": bands, "events": uniq, "news": news,
            "marks": [{"t": at(120), "label": "02:00"}, {"t": at(570), "label": "09:30"}, {"t": at(930), "label": "15:30"}]}


@router.get("/api/next/pc/timeline")
def r_timeline():
    try:
        return _J(timeline_view(_bot()))
    except Exception as e:
        return _err(e)


# ------------------------------------------------------------------------------------------------ 9: settings viewer
EDIT = ("live_model.json AND live_model_lit.json (keep them identical), the \"lit\" block; then run python tools/lit_losses.py live "
        "(it checks the trades against the stored run of the switch set) and the dashboard data, then Stop / Start the bot.")
SETTINGS = [
    # (path, name, plain words, tested, group)
    ("model", "Strategy", "Which strategy the bot trades. \"lit\" = Liquidity Inducement (the locked strategy).",
     "LIT 2026 (run lit_live): 120 trades, 2.91/week, PF 4.07, +$43,385 ($4,423/mo), max DD -$2,196; H1 PF 4.98 / H2 (check) PF 2.69 +$9,493",
     "core"),
    ("locked", "Locked", "The rule set is frozen: changes only after a research run proves them on 2026 H1 and H2.", "", "core"),
    ("no_yahoo", "No Yahoo", "Bars come only from NinjaTrader (MNQ) and the TradingView exports. A stale NinjaTrader feed blocks new entries "
     "(FEED STALE) instead of falling back to Yahoo.", "owner rule 2026-10-19", "core"),
    ("params.risk_usd", "Risk per trade", "Dollars risked per trade under the LIT size rule, up to the reference stop.", "$800 to a 20-pt stop", "size"),
    ("params.risk_ref_stop", "Reference stop", "Stops wider than this get fewer micros: risk = $800 x 20 / stop (wide stop = less risk).", "", "size"),
    ("params.max_micros", "Max micros", "Never more than this many MNQ micros on one trade.", "", "size"),
    ("params.max_trades_day", "Trades a day", "At most one trade a day.", "", "size"),
    ("lit.window", "Entry window", "Minutes after midnight ET when entries are allowed: [120, 930] = 02:00-15:30 ET.",
     "95 of 120 2026 trades enter 02:00-08:00 ET (NinjaTrader must run from ~01:55)", "entry"),
    ("lit.depth", "Sweep depth", "A level only counts as swept when price ran at least this many ATRs through it.", "0.5 ATR", "entry"),
    ("lit.idm_a", "Inducement", "An inducement swing must be taken first: [max size in ATR, max bars, how many].", "<= 1 ATR, <= 36 bars", "entry"),
    ("lit.disp", "Displacement", "The move away must have a candle body of at least this many ATRs.", "0.8 ATR", "entry"),
    ("lit.ref", "Entry reference", "Where the limit sits: the 5m CISD level.", "", "entry"),
    ("lit.wait", "Limit wait", "How many 5m bars the limit at the CISD level waits (6 = 30 minutes).", "", "entry"),
    ("lit.tf", "Entry timeframe", "After the limit is tapped, the entry comes from a 1m CISD (needs 1m bars).",
     "5m-only entries make +$6.6k in 2026 instead of +$43k", "entry"),
    ("lit.cisd1m", "1m CISD bars", "The 1m CISD must come within this many 1m bars, then the bot buys / sells at the next 1m open.", "", "entry"),
    ("lit.stop_buf", "Stop buffer", "The stop sits this many points (1 tick) beyond the sweep extreme, never a fixed distance.", "", "risk"),
    ("lit.min_stop", "Min stop", "Skip setups whose stop is closer than this (points).", "", "risk"),
    ("lit.max_stop", "Max stop", "Skip setups whose planned stop is wider than this (points); the 1m fill can widen it to ~88.", "", "risk"),
    ("lit.classes", "Target", "The target is the 18:00 open +/- one VIX one-day move.", "", "exit"),
    ("lit.vix_k", "VIX band size", "How many VIX one-day moves the target sits away.", "", "exit"),
    ("lit.min_rr", "Min reward:risk", "Skip setups whose target is closer than this many R.", "1.5R", "exit"),
    ("lit.max_rr", "Bank at", "Take the money at this many R even when the target is farther.", "8R", "exit"),
    ("lit.be_r", "Breakeven at", "Move the stop to breakeven once the trade is this many R in profit.",
     "BE stays: it removes ~1 recovery per 7 full losses saved (lit-adv-management.md)", "exit"),
    ("lit.be_off", "Breakeven + costs", "The breakeven stop sits this many points beyond entry so a BE exit pays its commission.", None, "switch"),
    ("lit.t_check", "15-minute check", "15 minutes after the fill, cut a trade that is under +0.3R and never reached +0.5R.", None, "switch"),
    ("lit.scale_in", "Scale-in after breakeven", "Add one more position on a pull-back after breakeven (OFF until the Sim101 roundtrip passes).", None, "switch"),
    ("lit.flat_mod", "Flat time", "Minutes after midnight ET when every trade is closed: 955 = 15:55.", "", "exit"),
    ("lit.max_per_day", "Setups a day", "One LIT trade a day.", "", "entry"),
    ("lit.monday", "Monday rule", "Once Monday took Friday's high, only shorts; once it took Friday's low, only longs.",
     "loss pack (with the weekly stop): 2026 PF 3.66 +$41,734 at adoption, both halves better (lit-losses.md)", "pack"),
    ("lit.wk_stop", "Weekly stop", "[2, 0.5]: after 2 stop-outs in a calendar week, half size for the rest of it (not under two_week sizing).",
     "loss pack: helped both halves and the eval (lit-losses.md)", "pack"),
    ("lit.how_out", "Eval-safe switch", "1.0 = off. 0.5 = half size when the sweep extreme is outside Tue 03:00 - Wed 11:30 ET.",
     "0.5: 2026 +$27.8k (PF 3.17) instead of +$38.9k, max DD -$2.3k instead of -$3.1k, pass rate 86% instead of 80%", "switch"),
    ("lit.nwog_discount", "NWOG discount", "Research option, off.", "", "entry"),
    ("lit.mw_filter", "M/W filter", "Research option, off.", "", "entry"),
    ("lit.extra_boxes", "Extra session boxes", "Research option: more session boxes as levels (empty = off).", "", "entry"),
    ("lit.sweep_names", "Level list", "null = every LIT level (session boxes, PDH/PDL, PWH/PWL, PMH/PML, NWOG/NDOG, build-ups).", "", "entry"),
    ("lit.fallback_rr", "Fallback target", "null = no fallback target (no VIX band, no trade).", "", "exit"),
    ("lit_sizing.mode", "Sizing mode", "two_week = \"one winner passes\": micros so the target covers what is left to +$3,000, capped at 60% of "
     "the eval room and the $1,000 soft daily loss, max 40, min 1.",
     "run lit_2wk_rec: 2-week pass H1 52.9% / H2 50.7%, fail 8.4% / 2.9%; live eval path now (t_check + be_off) 57.1/5.9 and 52.2/0.0", "eval"),
    ("lit_sizing.eval_start", "Eval start", "First session of the eval (sessions are counted from here).", "", "eval"),
    ("lit_sizing.eval_prior_pnl", "Eval P&L before the bot", "The eval's P&L when the bot started (owner: -$100).", "", "eval"),
    ("lit_sizing.two_week_until", "Two-week sessions", "two_week sizing runs for this many sessions, then after_mode.", "", "eval"),
    ("lit_sizing.after_mode", "After session 10", "No reset: the eval goes on in this mode (safe_eval = micros capped at 60% of the room).",
     "eventual pass ~80% / 77% (H1 / H2, tools/lit_eventual.py)", "eval"),
    ("lit_sizing.safe_cap", "Safe cap", "Share of the room to the trailing floor a safe_eval trade may risk.", "", "eval"),
    ("lit_sizing.fast_ref_stop", "Fast-eval reference stop", "Used only by mode fast_eval ($800 up to a 40-pt stop).",
     "fast_eval: 2-week passes H1 52% / H2 47% but 21-27% fail", "eval"),
    ("lit_sizing.eval_ref_stop", "Eval reference stop", "Used only by mode eval ($800 up to a 25-pt stop + 60% room cap).",
     "eval: 2-week passes H1 37.5% / H2 29.5%", "eval"),
    ("lit_sizing.two_week", "two_week details", "The knobs of two_week sizing (room_f 0.6 = 60% of the room, dll_cap = $1,000 daily cap).", "", "eval"),
    ("lit_sizing.funded", "Funded sizing", "Sizing after the pass. NOT on: needs the funded state wiring first.",
     "run lit_funded_rec: ~$740-770/mo paid, ~1% lost in 6 months", "eval"),
    ("equity_filter", "Cold-streak filter", "null = off (that was the old engine's filter; LIT has none).", "", "core"),
    ("sizing", "Old engine sizing", "null = off for LIT.", "", "core"),
]
_GROUPS = {"core": "Strategy and data", "switch": "Switches (on / off)", "pack": "Loss pack", "entry": "Entry rules", "risk": "Stop",
           "exit": "Target and exits", "size": "Size (LIT rule)", "eval": "Eval sizing (MFFU 50K)"}


def _get(d, path):
    cur = d
    for p in path.split("."):
        if not isinstance(cur, dict) or p not in cur:
            return ("__missing__",)
        cur = cur[p]
    return cur


def _is_on(v):
    return v not in (None, False, 0, {}, [], ("__missing__",), 1.0) if not isinstance(v, bool) else v


def settings_view(lm: dict | None = None, lm_lit: dict | None = None) -> dict:
    from . import botctl
    lm = _lm() if lm is None else lm
    if lm_lit is None:
        try:
            with open(os.path.join(ROOT, "live_model_lit.json"), encoding="utf-8") as fh:
                lm_lit = json.load(fh)
        except Exception:
            lm_lit = None
    try:
        sw = {r["key"]: r for r in botctl.switches_view(lm).get("switches") or []}
    except Exception:
        sw = {}

    def swnum(key):
        r = sw.get(key) or {}
        h1, h2 = (r.get("rule") or {}).get("H1") or {}, (r.get("rule") or {}).get("H2") or {}
        e1, e2 = (r.get("eval") or {}).get("H1") or {}, (r.get("eval") or {}).get("H2") or {}
        bits = []
        if h1 or h2:
            bits.append(f"alone: H1 PF {h1.get('pf')} ${h1.get('net') or 0:,.0f} / H2 PF {h2.get('pf')} ${h2.get('net') or 0:,.0f}")
        if e1 or e2:
            bits.append(f"eval 2-week pass/fail H1 {e1.get('p10')}/{e1.get('f10')} · H2 {e2.get('p10')}/{e2.get('f10')}")
        if r.get("note"):
            bits.append(r["note"])
        return " · ".join(bits) or "research/lit/adopt_combo.json"
    known = set()
    rows = []
    for path, name, what, tested, grp in SETTINGS:
        known.add(path)
        v = _get(lm, path)
        if v == ("__missing__",):
            continue
        key = path.split(".")[-1]
        if tested is None:
            tested = swnum(key)
        on = None
        if grp == "switch":
            on = _is_on(v) if key != "how_out" else (v not in (None, 1, 1.0))
        same = None
        if lm_lit is not None and path.startswith("lit."):
            same = _get(lm_lit, path) == v
        rows.append({"path": path, "name": name, "value": v, "what": what, "tested": tested or "", "group": grp,
                     "group_label": _GROUPS.get(grp, grp), "on": on, "same_in_lit_file": same,
                     "file": "live_model.json + live_model_lit.json" if path.startswith(("lit.", "lit_sizing", "params")) else "live_model.json"})
    other = []
    for blk in ("lit", "lit_sizing", "params"):
        for k, v in ((lm.get(blk) or {}) if isinstance(lm.get(blk), dict) else {}).items():
            p = f"{blk}.{k}"
            if p not in known and not k.endswith("note") and k not in ("modes",):
                other.append({"path": p, "value": v})
    drift = [r["path"] for r in rows if r["same_in_lit_file"] is False]
    return {"label": lm.get("label"), "chosen": lm.get("chosen"), "locked": lm.get("locked"), "lock_note": safe(lm.get("lock_note"), 600),
            "rows": rows, "other": other, "groups": _GROUPS, "drift": drift, "edit": EDIT, "read_only": True,
            "modes": lm.get("lit_sizing", {}).get("modes"), "results": {
                "2026": "120 trades, 2.91/wk, win 55.0%, PF 4.07, +$43,385 ($4,423/mo), DD -$2,196 (run lit_live)",
                "H1": "PF 4.98, +$33,891 (picked)", "H2": "PF 2.69, +$9,493, ~$2,550/mo (the check: quote this one)",
                "eval": "two_week path: H1 PF 4.02 +$34,234 / H2 PF 2.20 +$9,059; 2-week pass/fail 57.1/5.9 and 52.2/0.0",
                "2021-25": "reference only: PF 1.01, +$1,211, DD -$19,436"}}


@router.get("/api/next/pc/settings")
def r_settings():
    try:
        return _J(settings_view())
    except Exception as e:
        return _err(e)


# ------------------------------------------------------------------------------------------------ 10: morning report
def bar_gaps(rows, secs, t0, t1, min_missing=3) -> list:
    """Gaps in [[t,...], ...] while the market was open: {from, to, missing} where at least min_missing bars are absent."""
    from .live import market_open
    ts = sorted({int(r[0]) for r in rows or [] if t0 <= int(r[0]) <= t1})
    out = []
    for a, b in zip(ts, ts[1:]):
        if b - a <= secs:
            continue
        miss = sum(1 for x in range(a + secs, b, secs) if market_open(x))
        if miss >= min_missing:
            out.append({"from": a + secs, "to": b, "missing": miss, "minutes": miss * secs // 60})
    return out


def morning_view(bot, now: int | None = None) -> dict:
    from . import botctl, pcdash_api
    now = int(now or _now(bot))
    s0, s1, day = session_bounds(now)
    t0 = s0 - 2 * 3600                       # 16:00 ET the afternoon before (after the 15:55 flat)
    led = [r for r in _ledger(bot) if t0 <= int(r["t"]) <= now]
    trades = []
    try:
        acct = accounts.pc_activity(bot, now=now, max_trades=50, max_orders=50)
        for t in acct.get("trades") or []:
            if t.get("entry_t") and t0 <= int(t["entry_t"]) <= now:
                trades.append({k: t.get(k) for k in ("entry_t", "exit_t", "side", "qty", "entry_px", "exit_px", "exit", "pnl", "r")})
    except Exception:
        pass
    orders = [{"t": int(r["t"]), "side": r.get("side"), "qty": r.get("qty"), "ok": (r.get("result") or {}).get("ok", True),
               "error": safe((r.get("result") or {}).get("error"), 160), "pnl": accounts._f(r.get("pnl")), "reason": r.get("reason")}
              for r in led]
    logs = [r for r in list(getattr(bot, "log", None) or []) if r.get("t") and t0 <= int(r["t"]) <= now]
    errs = [{"t": int(r["t"]), "type": r.get("type"), "text": safe(r.get("text"), 220)} for r in logs
            if r.get("type") in ("error", "kill") or (r.get("type") in ("warn", "risk") and _RX_ERR.search(str(r.get("text") or "")))]
    stale = [e for e in errs if "STALE" in (e["text"] or "").upper()]
    b5, b1 = pcdash_api.bot_bars(bot, t0, now)
    gaps = [{"tf": "1m", **g} for g in bar_gaps(b1, 60, t0, now)] + [{"tf": "5m", **g} for g in bar_gaps(b5, 300, t0, now, 2)]
    restarts, updates = [], []
    try:
        for r in botctl.health_timeline(bot, now, n=80):
            if t0 <= r["t"] <= now:
                if r["kind"] == "start":
                    restarts.append(r)
                elif r["kind"] == "update":
                    updates.append(r)
    except Exception:
        pass
    alerts = []
    try:
        alerts = [a for a in (botctl.alerts_log(40).get("rows") or []) if a.get("t") and t0 <= a["t"] <= now]
    except Exception:
        pass
    st = getattr(bot, "state", None) or {}
    sigs = [accounts._signal_row(s) for s in ((st.get("lit") or {}).get("signals_today") or []) if isinstance(s, dict)]
    try:
        news = botctl.news_view(now)
    except Exception:
        news = {"events": []}
    h = accounts.pc_health(bot, now)
    try:
        v = accounts.verdict({"present": True, "t": now, "running": bool(getattr(bot, "running", False)), "health": h}, now)
    except Exception:
        v = None
    pnl = round(sum(float(r.get("pnl") or 0) for r in led if r.get("side") == "exit"), 2)
    bits = []
    n_ent = sum(1 for r in led if r.get("side") in ("buy", "sell"))
    bits.append(f"{n_ent} entr{'y' if n_ent == 1 else 'ies'}" + (f", {'+' if pnl >= 0 else '-'}${abs(pnl):,.0f} closed" if any(r.get("side") == "exit" for r in led) else ""))
    if gaps or stale:
        bits.append(", ".join(x for x in (f"{len(gaps)} feed gap(s)" if gaps else "", f"{len(stale)} FEED STALE warning(s)" if stale else "") if x))
    if restarts:
        bits.append(f"{len(restarts)} restart(s)")
    if [e for e in errs if e not in stale]:
        bits.append(f"{len([e for e in errs if e not in stale])} error(s)")
    quiet = not n_ent and not gaps and not stale and not restarts and not errs
    head = "All quiet overnight: no trades, no feed gaps, no restarts, no errors" if quiet else "Overnight: " + " · ".join(bits)
    return {"t": now, "from": t0, "day": day, "headline": head, "quiet": quiet, "verdict": v, "trades": trades, "orders": orders,
            "pnl": pnl, "errors": errs[:30], "feed_stale": stale[:20], "gaps": gaps[:30], "restarts": restarts[:20], "updates": updates[:20],
            "alerts": alerts[:30], "setups": sigs, "news": {"events": (news.get("events") or [])[:12], "text": news.get("text")},
            "position": _position(bot, now), "model_state": safe(st.get("model_state"), 200), "eval_clock": st.get("eval_2wk"),
            "running": bool(getattr(bot, "running", False)), "kill": bool(getattr(bot, "kill", False))}


@router.get("/api/next/pc/morning")
def r_morning():
    try:
        return _J(morning_view(_bot()))
    except Exception as e:
        return _err(e)
