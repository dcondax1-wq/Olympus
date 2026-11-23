"""THE LAUNCH CARD (Monday launch kit, 2026-11-14: Zlarior on the MFFU 50K eval and ATLAS on its 25K eval go live Monday
2026-11-16 02:00 ET). One look on the phone: per bot, today, is it armed, is the feed fresh, its trades, its $, the drawdown
left and any flag; then are the phone alerts working. docs/LAUNCH_DAY.md is the first-day checklist next to it.

READ ONLY: it only reads the bot's live numbers, the fill check (tools/fill_check.py) and the 15-minute report's own last run
(data/pc_report/last.json). It never writes, sends, arms, routes or changes anything; the private ntfy topic is never shown.

  bots(live, now)                     per bot (Zlarior 50K, ATLAS 25K, BLITZ 25K when its account is on): mode LIVE / SIM / PAPER /
                                      OFF, armed, running, feed, trades today, today's $, room / max loss, drawdown used, the
                                      open position with its $ risk, flags [{level, text, fix}], level
  build(live, revs, report, now)      the whole card (engine/live_site.py GET /api/site/launch.json; tools/web_public/gate/launch.js
                                      draws it on the Gate when the PC serves the site)
  report_state(work, env, now)        is the 15-minute phone report running (last run, sends OK, an alert topic set)
  payload(live, now)                  build() with the fill check's reviews (cached 30 s) and report_state(): the route's answer
  ready_push(snap, now)               the 01:45 ET push (tools/pc_guard.py): "Ready for 02:00 ET" (low priority, silent) or
                                      "NOT ready" (high), once per CME trading day, 01:35-01:59 ET
Tests: tests/test_launch_kit.py part 3.
"""
from __future__ import annotations

import datetime as dt
import os
import threading
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ET = ZoneInfo("America/New_York")
WORK_DEFAULT = os.path.join(ROOT, "data", "pc_report")     # tools/pc_report.WORK_DEFAULT
CHECKLIST = "gate/launch_day.json"                         # the first-day checklist the card shows (tools/launch_day.py)
FILLS_TTL_S = 30
REPORT_LATE_S = 35 * 60                                    # the report runs every 15 min: two missed runs = late
FEED_WARN_S = 180                                          # a 1m bar older than 3 min while the market is open
DD_WARN, DD_BAD, DLL_NEAR = 0.50, 0.75, 0.70               # tools/pc_guard.py DD_LEVELS / DLL_NEAR
READY_FROM, READY_TO = 95, 120                             # 01:35-01:59 ET: the first report run before LIT's 02:00 window
USD_PT, COMM_MICRO = 2.0, 1.90
NAMES = {"lit": "Zlarior", "atlas": "ATLAS", "blitz": "BLITZ"}
SIZES = {"lit": "50K", "atlas": "25K", "blitz": "25K"}
RANK = {"bad": 3, "warn": 2, "info": 1, "ok": 0}
FIX = {
    "stopped": "On the PC double-click tools/bat/GO_LIVE_EVAL.bat (it starts the bot; you type the phrase for the real accounts).",
    "down": "On the PC double-click tools/bat/GO_LIVE_EVAL.bat (it brings the bot back; you type the phrase); still red: HEALTH_CHECK.bat, send Claude a photo.",
    "feed": "In NinjaTrader: log in, open the MNQ 5-minute chart, right-click > Indicators > LE_BarFeed > Add.",
    "nt": "Open NinjaTrader on the PC and log in (Control Center > Connections).",
    "armed": "Arm it yourself at the PC: double-click tools/bat/GO_LIVE_EVAL.bat and type the phrase when it asks.",
    "dd": "Nothing to do: the bot sizes from the drawdown left by itself. Check the MFFU dashboard shows the same.",
    "dll": "Nothing to do: the bot keeps its own stops and stops for the day at the limit.",
    "risk": "Open NinjaTrader > Positions now: check the position and its stop; flatten there by hand if it is wrong.",
    "report": "On the PC double-click tools/bat/BOTS_BACK.bat: it reinstalls the 15-minute report and shows your alert topic.",
}


# ------------------------------------------------------------------------------------------------ small helpers
def _f(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _l(x) -> list:
    return x if isinstance(x, list) else []


def money(x) -> str:
    v = _f(x)
    return "-" if v is None else ("-" if v < 0 else "") + "${:,.0f}".format(abs(v))


def signed(x) -> str:
    v = _f(x)
    return "-" if v is None else ("+" if v >= 0 else "-") + "${:,.0f}".format(abs(v))


def span(sec) -> str:
    s = _f(sec)
    if s is None:
        return "?"
    s = max(0, int(s))
    return f"{s} s" if s < 90 else f"{s // 60} min" if s < 5400 else f"{s // 3600} h" if s < 172800 else f"{s // 86400} days"


def _flag(level, text, fix="", code="") -> dict:
    return {"level": level, "text": " ".join(str(text).split()), "fix": fix, "code": code}


def _worst(levels) -> str:
    out = "ok"
    for lv in levels:
        if RANK.get(lv, 0) > RANK.get(out, 0):
            out = lv
    return out


def risk_usd(p) -> float | None:
    """$ the position loses at its stop, costs in (tools/pc_report.risk_usd)."""
    p = _d(p)
    q, e, s = _f(p.get("qty")), _f(p.get("entry")), _f(p.get("stop"))
    if not q or e is None or s is None:
        return None
    return round(q * (abs(e - s) * USD_PT + COMM_MICRO), 2)


# ------------------------------------------------------------------------------------------------ per bot
def feed_of(pc: dict, now: int | None = None) -> dict:
    """The NinjaTrader bar feed all three bots trade on: {"ok" True / False / None, "text"}."""
    fd = _d(_d(_d(pc).get("health")).get("feed"))
    if not fd:
        return {"ok": None, "text": "not reported"}
    a1 = _f(fd.get("age_1m_s"))
    if fd.get("stale") or (fd.get("entries_blocked") and "stale" in str(fd.get("block") or "").lower()):
        return {"ok": False, "text": "FEED STALE" + (f": {str(fd.get('block'))[:90]}" if fd.get("block") else "") + ", no new entries"}
    if fd.get("market_open") is False:
        return {"ok": True, "text": "market closed", "closed": True}
    if a1 is not None and a1 > FEED_WARN_S:
        return {"ok": False, "text": f"last 1-minute bar {span(a1)} old"}
    return {"ok": True, "text": "fresh" + (f" (1-minute bar {span(a1)} old)" if a1 is not None else "")}


def _mode(k: str, card: dict, pc: dict) -> str:
    if k == "lit":
        acc = _d(_d(_d(pc).get("health")).get("account"))
        ad = acc.get("adapter") or _d(pc).get("adapter")
        if ad in (None, "paper"):
            return "PAPER"
        return "LIVE" if acc.get("is_live") or acc.get("label") == "LIVE" else "SIM"
    c = _d(card)
    if not c or c.get("off") or c.get("configured") is False or str(c.get("status") or "") in ("not set up", "off"):
        return "OFF"
    b = str(c.get("badge") or "").upper()
    if c.get("real") or b == "LIVE":
        return "LIVE"
    return "SIM" if b == "SIM" else "PAPER"


def _armed(k: str, mode: str, card: dict, pc: dict) -> bool:
    if mode != "LIVE":
        return False
    facts = _d(_d(_d(pc).get("launch")).get("facts"))
    if k == "lit":
        acc = _d(_d(_d(pc).get("health")).get("account"))
        return bool((acc.get("armed") or facts.get("lit_armed")) and acc.get("enabled", True) is not False and not acc.get("disabled"))
    off = any(str(_d(b).get("kind")) == "account" for b in _l(_d(card).get("blocks")))
    want = _d(facts.get("b" if k == "atlas" else "c")).get("armed")
    return not off and want is not False


def bots(live: dict | None, now: int | None = None, revs: list | None = None) -> list:
    """The card's rows, one per bot the board knows (BLITZ only while its own account is on). Never raises."""
    now = int(now or time.time())
    L = _d(live)
    pc, bd = _d(L.get("pc")), _d(L.get("board"))
    feed = feed_of(pc, now)
    running = pc.get("running")
    today = None
    try:
        from engine.live_board import trading_day
        today = trading_day(now)
    except Exception:
        pass
    out = []
    for k in ("lit", "atlas", "blitz"):
        c = _d(bd.get(k))
        if k == "blitz" and (not c or c.get("off")):
            continue
        if not c or c.get("error"):
            continue
        mode = _mode(k, c, pc)
        armed = _armed(k, mode, c, pc)
        room, mll = _f(c.get("room")), _f(c.get("mll"))
        used = None if room is None or not mll else max(0.0, min(1.0, 1.0 - room / mll))
        pos = _d(c.get("position")) or None
        row = {"id": k, "name": NAMES[k], "label": f"{NAMES[k]} {SIZES[k]}", "plan": c.get("plan"), "mode": mode, "armed": armed,
               "state": ("LIVE, armed" if armed else "real account, NOT armed") if mode == "LIVE" else
                        {"SIM": "Sim", "PAPER": "paper", "OFF": "not set up"}.get(mode, mode.lower()),
               "running": bool(running) if running is not None else None, "feed": feed, "trades": c.get("trades_today"),
               "max_day": c.get("max_day"), "today": _f(c.get("today_pnl")), "room": room, "mll": mll,
               "used": None if used is None else round(used, 4), "status": c.get("status"), "window": _d(c.get("window")).get("text"),
               "position": None}
        if pos:
            rk = risk_usd(pos)
            row["position"] = {**{x: pos.get(x) for x in ("side", "qty", "entry", "stop", "target", "entry_t", "unrealized_usd") if pos.get(x) is not None},
                               "risk_usd": rk}
        fl = []                          # the bot stopped, the feed and NinjaTrader are the whole PC's: build() says them once
        if mode == "LIVE" and not armed:
            fl.append(_flag("bad", f"{row['label']} is on its real account but not armed: its entries are refused.", FIX["armed"], "armed"))
        for b in _l(c.get("blocks")):
            b = _d(b)
            if b.get("text"):
                fl.append(_flag("info" if b.get("kind") == "passed" else "bad", b["text"], b.get("fix") or "", "block"))
        live_eval = str(c.get("status") or "open") not in ("passed", "failed", "lost", "graduated", "stuck")
        if used is not None and live_eval and mode != "OFF":
            if used >= DD_BAD:
                fl.append(_flag("bad", f"{used * 100:.0f}% of the drawdown used: {money(room)} of {money(mll)} left.", FIX["dd"], "dd"))
            elif used >= DD_WARN:
                fl.append(_flag("warn", f"{used * 100:.0f}% of the drawdown used: {money(room)} of {money(mll)} left.", FIX["dd"], "dd"))
        dll = _f(c.get("dll"))
        if dll and live_eval and mode != "OFF":
            unreal = _f(_d(pos).get("unrealized_usd")) or 0.0
            loss = max(0.0, -((_f(c.get("today_pnl")) or 0.0) + min(0.0, unreal)), _f(c.get("dll_used")) or 0.0)
            if loss >= DLL_NEAR * dll:
                fl.append(_flag("bad", f"Down {money(loss)} today of the {money(dll)} daily loss limit ({loss / dll * 100:.0f}%).", FIX["dll"], "dll"))
        if row["position"] and row["position"].get("risk_usd") is not None and room is not None and row["position"]["risk_usd"] > room:
            fl.append(_flag("bad", f"The open trade's stop would cost {money(row['position']['risk_usd'])}, more than the {money(room)} "
                                   "drawdown left.", FIX["risk"], "risk"))
        if row["position"] and _f(row["position"].get("stop")) is None:
            fl.append(_flag("bad", "The open trade shows no stop in the bot's report.", FIX["risk"], "nostop"))
        for r in revs or []:
            if _d(r).get("acct") != k:
                continue
            if today is not None:
                try:
                    from engine.live_board import trading_day
                    if trading_day(int(r["entry_t"])) != today:
                        continue
                except Exception:
                    pass
            for f in _l(r.get("flags")):
                fl.append(_flag("bad" if f.get("level") == "bad" else "warn", f"Fill check: {f.get('text')}", f.get("fix") or "", "fill:" + str(f.get("code"))))
        row["flags"] = fl
        row["fills"] = [r.get("line") for r in revs or [] if _d(r).get("acct") == k][:3]
        row["level"] = _worst(f["level"] for f in fl)
        if mode == "OFF":                  # an account that is not set up trades nothing: a note, not an alarm
            for f in fl:
                f["level"] = "warn" if f["level"] == "bad" else f["level"]
            row["level"] = _worst(f["level"] for f in fl)
        out.append(row)
    return out


def global_flags(live: dict | None, now: int | None = None) -> list:
    """What stops every account at once: the bot stopped, the feed, NinjaTrader, then the board's own global blocks (kill switch,
    the bot's guards, silence, critical alerts) with their fixes."""
    L = _d(live)
    pc, bd = _d(L.get("pc")), _d(L.get("board"))
    out = []
    if pc.get("running") is False:
        out.append(_flag("bad", "The bot is stopped on the PC: no new trades on any account.", FIX["stopped"], "stopped"))
    fd = feed_of(pc, now)
    if fd.get("ok") is False:
        out.append(_flag("bad", fd["text"] + ".", FIX["feed"], "feed"))
    nt = _d(_d(pc.get("health")).get("nt"))
    if _d(_d(pc.get("health")).get("account")).get("adapter") == "ninjatrader" and nt and nt.get("connected") is False:
        out.append(_flag("bad", "NinjaTrader is not connected.", FIX["nt"], "nt"))
    have = {f["code"] for f in out}
    for b in _l(bd.get("blocks")):
        b = _d(b)
        kind = str(b.get("kind") or "")
        if not b.get("text") or kind in have or (kind == "stopped" and "stopped" in have):
            continue
        out.append(_flag("bad", b["text"], b.get("fix") or "", kind or "block"))
        have.add(kind)
    return out


# ------------------------------------------------------------------------------------------------ the phone report
def report_state(work: str | None = None, env=None, now=None) -> dict:
    """Is the 15-minute phone report (tools/pc_report.py, task OlympusPCReport) running and sending? From its own last run only
    (data/pc_report/last.json, "alerts_on" = an alert topic is set and on): the bot server never reads the private ntfy settings."""
    now = int(now or time.time())
    work = work or WORK_DEFAULT
    try:
        import json as _json
        with open(os.path.join(work, "last.json"), "r", encoding="utf-8") as fh:
            last = _json.load(fh)
        last = last if isinstance(last, dict) else {}
    except Exception:
        last = {}
    t = _f(last.get("t"))
    alerts = last.get("alerts_on") if isinstance(last.get("alerts_on"), bool) else None     # None: a report from before 2026-11-14
    out = {"t": int(t) if t else None, "age_s": (now - int(t)) if t else None, "ok": last.get("ok"), "alerts": alerts,
           "last_push_t": _d(last.get("alerts_last")).get("t"), "status_t": last.get("status_t"),
           "errors": [str(e)[:140] for e in _l(last.get("errors"))][:2]}
    if t is None:
        out.update(level="warn", text="The 15-minute phone report has not run on this PC yet.", fix=FIX["report"])
    elif now - int(t) > REPORT_LATE_S:
        out.update(level="warn", text=f"The phone report last ran {span(now - int(t))} ago (it runs every 15 minutes).", fix=FIX["report"])
    elif alerts is False:
        out.update(level="warn", text="Phone alerts are not set up on this PC.", fix=FIX["report"])
    elif out["errors"]:
        out.update(level="warn", text=f"The last phone report could not send everything: {out['errors'][0]}", fix=FIX["report"])
    else:
        lp = _f(out["last_push_t"])
        out.update(level="ok", text=("Phone alerts on" if alerts else "Phone report") + f": last check {span(now - int(t))} ago"
                   + (f", last push {span(now - int(lp))} ago" if lp else "") + ".", fix="")
    return out


# ------------------------------------------------------------------------------------------------ the card
def headline(rows: list, glob: list) -> str:
    """One sentence on top: the first bad thing, else who is armed, the feed and how many notes."""
    live = [r for r in rows if r["mode"] != "OFF"]
    if glob:
        return glob[0]["text"]
    for r in live:
        bad = [f for f in r["flags"] if f["level"] == "bad"]
        if bad:
            more = sum(1 for x in live for f in x["flags"] if f["level"] == "bad") - 1
            return f"{r['label']}: {bad[0]['text']}" + (f" (+{more} more)" if more > 0 else "")
    armed = [r["name"] for r in rows if r["armed"]]
    others = [f"{r['name']} {r['state']}" for r in rows if not r["armed"]]
    who = (" and ".join(armed) + " armed") if armed else "No real account armed"
    if others:
        who += (", " if armed else ": ") + ", ".join(others)
    feed = next((r["feed"] for r in rows), {})
    n_warn = sum(1 for r in rows for f in r["flags"] if f["level"] == "warn")
    return f"{who}; feed {feed.get('text') or 'unknown'}; " + (f"{n_warn} note{'s' if n_warn != 1 else ''}." if n_warn else "no flags.")


def build(live: dict | None, revs: list | None = None, report: dict | None = None, now=None) -> dict:
    """The Launch card. live = the bot's live.json (engine/live_publish.build, /api/site/live.json); revs = tools/fill_check
    reviews; report = report_state(). Never raises."""
    now = int(now or time.time())
    try:
        L = _d(live)
        if L.get("kind") != "le-live":
            return {"ok": True, "v": 1, "kind": "le-launch", "t": now, "live": False, "level": "bad", "bots": [],
                    "headline": "The bot's live numbers are not available on this server.", "global": [_flag("bad", "No live numbers from the bot.", FIX["down"], "down")],
                    "report": report or {}, "checklist": CHECKLIST}
        pc = _d(L.get("pc"))
        rows = bots(L, now, revs)
        glob = global_flags(L, now)
        rep = report if isinstance(report, dict) else {}
        if rep.get("level") == "warn":
            glob.append(_flag("warn", rep.get("text") or "Phone alerts: check the report.", rep.get("fix") or FIX["report"], "report"))
        try:
            from tools import fill_check
            fsum = fill_check.summary(revs or [], now)
        except Exception:
            fsum = None
        v = _d(L.get("pc_verdict"))
        lit = _d(_d(L.get("board")).get("lit"))
        out = {"ok": True, "v": 1, "kind": "le-launch", "t": now, "live": True, "live_t": L.get("t"), "running": pc.get("running"),
               "verdict": {k: v.get(k) for k in ("code", "label", "level", "reason")} if v else None,
               "feed": feed_of(pc, now), "window": _d(lit.get("window")).get("text"), "bots": rows, "global": glob,
               "report": rep, "fills": fsum, "checklist": CHECKLIST}
        out["level"] = _worst([f["level"] for f in glob] + [r["level"] for r in rows])
        out["headline"] = headline(rows, [g for g in glob if g["level"] == "bad"])
        return out
    except Exception as e:
        return {"ok": False, "v": 1, "kind": "le-launch", "t": now, "error": f"{e.__class__.__name__}: {str(e)[:160]}", "bots": []}


_CACHE = {"t": 0.0, "revs": None, "lock": threading.Lock()}


def cached_reviews(now=None, root: str = ROOT, ttl: float = FILLS_TTL_S) -> list:
    """tools/fill_check.reviews at most every ttl seconds (the route may be asked every few seconds). Never raises."""
    now = float(now or time.time())
    with _CACHE["lock"]:
        if _CACHE["revs"] is not None and now - _CACHE["t"] < ttl:
            return _CACHE["revs"]
        try:
            from tools import fill_check
            revs = fill_check.reviews(root, int(now))
        except Exception:
            revs = []
        _CACHE.update(t=now, revs=revs)
        return revs


def payload(live: dict | None, now=None, root: str = ROOT, work: str | None = None, env=None) -> dict:
    """engine/live_site.py GET /api/site/launch.json: the card for the bot's live numbers, with the fill check and the report."""
    now = int(now or time.time())
    return build(live, cached_reviews(now, root), report_state(work, env, now), now)


# ------------------------------------------------------------------------------------------------ the 01:45 ET push
def ready_push(snap: dict, now=None) -> list:
    """[push] once per CME trading day, at the first report run 01:35-01:59 ET: every bot's mode and drawdown left, the bot,
    NinjaTrader and the feed, and what is wrong with its one action. Silent (low) when all is well, high when not. The 15-minute
    report's own condition codes come in snap["cond"] (tools/pc_report.conditions)."""
    now = int(now or snap.get("t") or time.time())
    if not isinstance(snap, dict) or "hb_age" not in snap:
        return []                       # only the 15-minute report's own look at the PC (tools/pc_report.gather) can say ready or not
    e = dt.datetime.fromtimestamp(now, ET)
    m = e.hour * 60 + e.minute
    if e.weekday() >= 5 or not (READY_FROM <= m < READY_TO):
        return []
    try:
        from engine import cme_calendar
        if cme_calendar.full_closure(e.date()):
            return []
    except Exception:
        pass
    day = e.date().isoformat()
    cond = _d(snap.get("cond"))
    fresh = snap.get("hb_age") is not None and snap["hb_age"] <= 900
    rows = bots(snap.get("live"), now, snap.get("fills")) if fresh else []
    probs = []
    for code in ("bot_down", "bot_stopped", "nt_down", "feed_stale"):
        if cond.get(code):
            probs.append(str(cond[code]))
    if not fresh and not probs:
        probs.append("The bot has not reported" + (f" for {span(snap.get('hb_age'))}" if snap.get("hb_age") is not None else "") + ". "
                     + FIX["down"])
    if fresh and not cond.get("bot_stopped") and _d(snap.get("hb")).get("running") is False:
        probs.append("The bot is stopped on the PC. " + FIX["stopped"])    # before 01:50 the report's own 'stopped' alert is not on yet
    for r in rows:                      # what stops an account from trading at 02:00 (drawdown / daily loss have their own pushes)
        for f in r["flags"]:
            if f["level"] == "bad" and (f["code"] in ("armed", "block", "risk", "nostop") or f["code"].startswith("fill:")):
                probs.append(f"{r['label']}: {f['text']} {f['fix']}".strip())
    parts = []
    for r in rows:
        parts.append(f"{r['label']}: {r['state']}" + (f", drawdown left {money(r['room'])} of {money(r['mll'])}" if r["room"] is not None else ""))
    feed = next((r["feed"] for r in rows), None)
    tail = ("Bot running" if snap.get("server") and _d(snap.get("hb")).get("running") else "Bot NOT running") \
        + (", NinjaTrader on" if snap.get("nt") is not False else ", NinjaTrader CLOSED") + (f", feed {feed['text']}" if feed else "") + "."
    ok = not probs
    word = {"LIVE": "LIVE", "SIM": "Sim", "PAPER": "paper", "OFF": "not set up"}
    names = [f"{r['name']} " + (("LIVE armed" if r["armed"] else "LIVE NOT armed") if r["mode"] == "LIVE" else word.get(r["mode"], r["mode"])) for r in rows]
    title = ("Ready for 02:00 ET: " + ", ".join(names)) if ok else ("NOT ready for 02:00 ET: " + (probs[0].split(".")[0][:70]))
    body = ("; ".join(parts) + ". " if parts else "") + tail + (" Entries from 02:00 ET." if ok else " Fix: " + " ".join(probs[:3]))
    # one key each: "NOT ready" at 01:36 and, once you fixed it, "Ready" at 01:51; neither is said twice in a day
    return [{"key": f"guard:{'ready' if ok else 'notready'}:{day}", "title": "".join(ch if ord(ch) < 128 else "-" for ch in title)[:118],
             "body": " ".join(body.split()), "priority": "low" if ok else "high", "tags": "white_check_mark" if ok else "warning", "night": True}]
