"""Monday-morning readiness (2026-10-30, owner: "automatic in a few weeks"): one phone push every Sunday 17:30 ET, before
the 18:00 open, that says whether the PC is ready for the week (read-only: nothing here changes what the bot does).

  python -X utf8 -m engine.pc_health --readiness [--send]     build it now (prints it; --send pushes it too)

The push (kind "readiness", on / silent / off in the app), one line per fact:
  * version (git HEAD) and the PC self-test (engine/pc_selftest: the Sunday 15:30 run)
  * "Run switch is ON / OFF" (data/autostart.json = the dashboard switch on Run) and whether the bot runs
  * both accounts' room to the floor and the eval day N of 10 (the live board: engine/board_api.board_view), funded / passed
  * BLITZ's account C: off / Sim test / set, not armed / armed (engine/go.blitz_status)
  * this week's big US news (high-impact USD events Monday-Friday: engine/news.upcoming_events)
  * early closes / closed days this week (engine/cme_calendar)
  * the clock change when it falls this week (2026-11-01: clocks went back this morning; every bot time is New York time)
build() is pure (facts in, title / body / lines out); gather() reads the running bot and the files, every part wrapped so
a broken one becomes "unknown" and never stops the push.
"""
from __future__ import annotations

import datetime as dt
import time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
WD = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _et(t) -> dt.datetime:
    return dt.datetime.fromtimestamp(float(t), ET)


def week_days(now) -> list:
    """The trading dates (Mon-Fri) of the week the readiness push is for: on Sunday (and Saturday) the coming week, on a
    weekday the rest of this one."""
    d = _et(now).date()
    mon = d + dt.timedelta(days=(7 - d.weekday()) % 7) if d.weekday() >= 5 else d - dt.timedelta(days=d.weekday())
    return [mon + dt.timedelta(days=i) for i in range(5) if mon + dt.timedelta(days=i) >= d]


def dst_note(now) -> str | None:
    """The clock change when it falls today or in the 7 days ahead (New York rules from zoneinfo), else None."""
    e = _et(now)
    start = dt.datetime.combine(e.date(), dt.time(0, 0), ET)
    off0 = start.utcoffset()
    for h in range(1, 8 * 24 + 1):
        t = start + dt.timedelta(hours=h)
        t = dt.datetime.fromtimestamp(t.timestamp(), ET)
        if t.utcoffset() != off0:
            back = t.utcoffset() < off0
            when = "this morning" if t.date() == e.date() and t <= e else f"on {WD[t.weekday()]} {t:%b %d}"
            verb = ("went back" if t <= e else "go back") if back else ("went forward" if t <= e else "go forward")
            return (f"Clocks {verb} one hour {when} ({'to EST' if back else 'to EDT'}): every bot time is New York "
                    "time, nothing to do; check the PC clock shows the new time.")
    return None


def calendar_lines(days) -> list:
    """['Thu Nov 26 closed', 'Fri Nov 27 early close 13:15 ET (no new entry after 13:00)']"""
    out = []
    try:
        from . import cme_calendar as C
    except Exception:
        return ["calendar unknown"]
    for d in days:
        try:
            if C.full_closure(d):
                out.append(f"{WD[d.weekday()]} {d:%b %d} closed")
                continue
            ec = C.early_close(d)
            if ec is not None:
                cut = ec - 15
                out.append(f"{WD[d.weekday()]} {d:%b %d} early close {ec // 60:02d}:{ec % 60:02d} ET (no new entry after "
                           f"{cut // 60:02d}:{cut % 60:02d})")
        except Exception:
            continue
    return out


def news_lines(events, days, n: int = 6) -> list:
    """High-impact USD events on the week's trading dates: ['Wed 14:00 FOMC Statement', ...] (at most n, then '+k more')."""
    want = {d.isoformat() for d in days}
    rows, seen = [], set()
    for e in events or []:
        try:
            if str(e.get("impact") or "").lower() != "high" or str(e.get("currency") or "USD") != "USD":
                continue
            t = _et(int(e["t"]))
            if t.date().isoformat() not in want:
                continue
            k = (t.strftime("%a %H:%M"), str(e.get("event") or "")[:24])
            if k in seen:
                continue
            seen.add(k)
            rows.append((int(e["t"]), f"{WD[t.weekday()]} {t:%H:%M} {str(e.get('event') or '').strip()}"))
        except Exception:
            continue
    rows.sort()
    out = [r[1] for r in rows[:n]]
    if len(rows) > n:
        out.append(f"+{len(rows) - n} more")
    return out


def _money(x) -> str:
    try:
        return f"${float(x):,.0f}"
    except Exception:
        return "?"


def account_line(name: str, a: dict | None) -> str:
    """'Zlarior 50K: drawdown left $1,640 of $2,000' (funded / passed / failed / not set up said so)."""
    a = a if isinstance(a, dict) else {}
    if not a or a.get("error"):
        return f"{name}: unknown (no board)"
    st = str(a.get("status") or "").lower()
    room = a.get("room")
    head = f"{name}: " + ((f"drawdown left {_money(room)}" + (f" of {_money(a['mll'])}" if a.get("mll") else "")) if room is not None else "drawdown unknown")
    if st in ("passed", "failed"):
        return f"{name}: eval {st.upper()}" + (f" (drawdown left {_money(room)})" if room is not None else "")
    if st == "not set up":
        return f"{name}: not set up"
    if a.get("sessions") is None and a.get("session") is not None:
        return head + ", funded"
    return head                                   # owner 2026-11-03: no "eval day N of 10" counter


def blitz_line(bs: dict | None) -> str:
    bs = bs if isinstance(bs, dict) else {}
    if not bs:
        return "BLITZ 25K: unknown"
    if not bs.get("on"):
        return "BLITZ 25K: off (paper shadow only)"
    if bs.get("sim"):
        return f"BLITZ 25K: Sim test on {bs.get('name')}"
    if bs.get("armed"):
        return f"BLITZ 25K: ARMED on {bs.get('name')}" + (" (funded)" if bs.get("stage") == "funded" else "")
    return f"BLITZ 25K: set to {bs.get('name')}, not armed (Sim only until you arm it)"


def build(f: dict, now) -> dict:
    """facts -> {"title", "body", "lines", "level", "problems"}. f: version, selftest (engine/pc_selftest result),
    run_switch (bool), running (bool), board {"lit", "atlas"}, blitz (go.blitz_status), events (news rows), update
    (autoupdate.status)."""
    days = week_days(now)
    problems = []
    ver = f.get("version") or "?"
    st = f.get("selftest") if isinstance(f.get("selftest"), dict) else {}
    if st:
        from .pc_selftest import summary_line
        age_h = (float(now) - float(st.get("t") or 0)) / 3600
        st_txt = f"self-test {summary_line(st)}" + (f" ({_et(st['t']):%a %H:%M})" if age_h > 6 and st.get("t") else "")
        if st.get("failed"):
            problems.append(f"self-test: {(st.get('first') or [{}])[0].get('label')}")
        elif age_h > 8 * 24:
            problems.append("no self-test this week")
    else:
        st_txt = "self-test not run yet"
        problems.append("no self-test result")
    upd = f.get("update") if isinstance(f.get("update"), dict) else {}
    if upd.get("result") in ("rolled_back", "failed"):
        problems.append(f"last update {upd.get('result').replace('_', ' ')}")
    sw = f.get("run_switch")
    sw_txt = "Run switch is ON" if sw else "Run switch is OFF" if sw is False else "Run switch unknown"
    if sw:
        sw_txt += " (bot running)" if f.get("running") else " (bot not running yet: it resumes by itself)"
    elif sw is False:
        problems.append("Run switch is OFF")
        sw_txt += ": press Run on the dashboard before 18:00 ET"
    b = f.get("board") if isinstance(f.get("board"), dict) else {}
    acc = [account_line("Zlarior 50K", b.get("lit")), account_line("ATLAS 25K", b.get("atlas")), blitz_line(f.get("blitz"))]
    try:                                   # hidden bots (engine/hidden_bots.py, owner 2026-11-15): no BLITZ line while it is hidden
        from . import hidden_bots
        if hidden_bots.is_hidden("blitz"):
            acc = acc[:2]
    except Exception:
        pass
    nl = news_lines(f.get("events"), days)
    cl = calendar_lines(days)
    dn = dst_note(now)
    lines = [f"Version {ver} · {st_txt}", sw_txt, *acc,
             "News: " + ("; ".join(nl) if nl else ("none high-impact" if f.get("events") is not None else "unknown")),
             "This week: " + ("; ".join(cl) if cl else "normal hours (no early close)")]
    if dn:
        lines.append(dn)
    title = "Ready for Monday" if not problems else f"Before Monday: {problems[0]}"
    if len(problems) > 1:
        title += f" (+{len(problems) - 1})"
    body = ". ".join(ln.rstrip(".") for ln in lines) + "."
    return {"title": title[:120], "body": body[:600], "lines": lines, "level": "good" if not problems else "warn",
            "problems": problems}


def gather(bot, now, news_fn=None) -> dict:
    """The facts build() needs, each read on its own (a failing part = missing, never an exception)."""
    f: dict = {}
    try:
        from . import pc_selftest
        f["version"] = (pc_selftest.version() or {}).get("sha")
        f["selftest"] = pc_selftest.last()
    except Exception:
        pass
    try:
        from . import autoupdate
        f["update"] = autoupdate.status()
    except Exception:
        pass
    try:
        from . import watchdog
        f["run_switch"] = bool(watchdog.load(watchdog.AUTOSTART_PATH))
    except Exception:
        pass
    f["running"] = bool(getattr(bot, "running", False)) if bot is not None else None
    if bot is not None:
        try:
            from . import board_api
            f["board"] = board_api.board_view(bot, int(now))
        except Exception:
            pass
    try:
        from . import go
        f["blitz"] = go.blitz_status()
    except Exception:
        pass
    try:
        if news_fn is not None:
            f["events"] = news_fn(now)
        else:
            from . import news
            f["events"] = news.upcoming_events(int(now), days=7)
    except Exception:
        pass
    return f


def notice(bot, now=None, manual: bool = False, facts: dict | None = None) -> dict:
    """The push payload (kind readiness, key per Sunday date; manual = a fresh key so a test send is not a duplicate)."""
    now = time.time() if now is None else now
    r = build(facts if facts is not None else gather(bot, now), now)
    from . import push
    day = _et(now).date().isoformat()
    key = f"readiness:{day}" + (f":manual:{int(now)}" if manual else "")
    p = push.text_payload("PC", "readiness", r["title"], r["body"], key=key, t=int(now), url="#/accounts")
    p["lines"] = r["lines"]
    return p


# ====================================================================================================================
# READY VERDICT (day-ready 2026-11-22). Owner: tonight two avoidable errors (a PC clock 24.5 s behind, ATLAS unarmed) stopped
# the bots from trading and nobody noticed for hours. ONE function says, BEFORE the trading window, whether the bot can trade:
#
#   ready_verdict(now=None, facts=None) -> {"ready": bool, "level": "READY" | "WARN" | "NOT_READY", "window": "02:00",
#        "blockers": [{"what", "why_plain_words", "exact_fix", "needs_owner_at_pc", "level"}] (worst first, max 5), "n", "t"}
#
# READ-ONLY on trading: it checks and reports; it never starts, stops, arms or changes anything. It reuses engine/ops_checks
# (the NinjaTrader folder / connection, LE_BarFeed freshness, internet + clock drift, disk, Windows update, the heartbeat),
# engine/preflight.arms (each account armed / held), engine/clock7 (the MFFU 7-day deadline) and the guard's own clock limit
# (engine/guards DEFAULTS clock_max_s, 5 s: ops_checks only turns red at 30 s, but the bot blocks entries at 5 s).
# evaluate(facts, now) is pure (tests hand it fake facts); gather_facts() reads the PC.
#
# tick(now) is the scheduled part (engine/ops_checks.tick calls it every 5 min; server start calls it once, 90 s after boot):
# slots 17:30 ET Sun-Thu (before the 18:00 open), 01:15 ET Mon-Fri (45 min before 02:00), 08:45 ET Mon-Fri, at bot start, and
# whenever a NEW blocker appears. NOT READY -> ONE alert through engine/alert_bus (Telegram / Discord first, ntfy / Web Push
# backup), at most once an hour, and never the same blocker twice within 30 min. READY -> one quiet line at the 17:30 slot only.
# The last verdict is written to data/ready_last.json; tools/pc_report puts rd() (<= 200 bytes, plain words, no ids) in the ext post.
# Docs: docs/OWNER_MANUAL.md "What READY means".
# ====================================================================================================================
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAST_PATH = os.path.join(ROOT, "data", "ready_last.json")      # gitignored: the last verdict (tools/pc_report reads it)
STATE_PATH = os.path.join(ROOT, "data", "ready_state.json")    # gitignored: alert de-dup + slots done
READY, WARN, NOT_READY = "READY", "WARN", "NOT_READY"
MAX_SHOWN = 5
CLOCK_MAX_S = 5.0                 # engine/guards DEFAULTS clock_max_s (read live in clock_max())
SAME_BLOCKER_S = 30 * 60          # never the same blocker twice within 30 min
REPEAT_S = 60 * 60                # a NOT READY alert repeats at most once an hour
MIN_GAP_S = 10 * 60               # and never two loud alerts within 10 min, whatever changed
RD_MAX_BYTES = 200                # the status post's "rd" block
STALE_VERDICT_S = 3 * 3600        # a verdict file older than this is not posted (the phone says "unknown")
SLOTS = (("1730", 17 * 60 + 30, (6, 0, 1, 2, 3)), ("0115", 75, (0, 1, 2, 3, 4)), ("0845", 8 * 60 + 45, (0, 1, 2, 3, 4)))
SLOT_GRACE_MIN = 25               # a slot still fires up to 25 min late (the ops task runs every 5 min; the PC may just have woken)


def _dd(x) -> dict:
    return x if isinstance(x, dict) else {}


def _ll(x) -> list:
    return x if isinstance(x, list) else []


def clock_max() -> float:
    try:
        from . import guards
        return float(guards.DEFAULTS.get("clock_max_s") or CLOCK_MAX_S)
    except Exception:
        return CLOCK_MAX_S


def window_label(now) -> str:
    """The entry window the check is for: '02:00' (LIT / ATLAS's first), '09:30', 'now' inside the trading day, or 'Mon 02:00'."""
    e = _et(now)
    mod, wd = e.hour * 60 + e.minute, e.weekday()
    if wd < 5 and mod < 120:
        return "02:00"
    if wd < 5 and mod < 570:
        return "09:30"
    if wd < 5 and mod < 15 * 60 + 30:
        return "now"
    # after 15:30 / weekend: the next trading morning
    d = e.date()
    for i in range(1, 8):
        n = d + dt.timedelta(days=i)
        if n.weekday() < 5:
            try:
                from .cme_calendar import full_closure
                if full_closure(n):
                    continue
            except Exception:
                pass
            return "02:00" if i == 1 else f"{WD[n.weekday()]} 02:00"
    return "02:00"


def proven_drift(net: dict) -> float | None:
    """engine/guards.clock_probe's math (red team 2026-11-23): the Date header is whole seconds and the round trip adds doubt,
    so only the part of the drift the probe can prove counts. The guard blocks on this number, so READY uses it too."""
    try:
        d = net.get("drift_s")
        if d is None:
            return None
        h = max(0.0, float(net.get("unc_s") or 1.0) - 1.0)
        lo, hi = float(d) - h, float(d) + 1.0 + h
        return lo if lo > 0 else hi if hi < 0 else 0.0
    except Exception:
        return None


def _b(level, what, why, fix, owner=True, key=None) -> dict:
    return {"key": key or what.lower()[:40], "level": level, "what": what, "why_plain_words": why, "exact_fix": fix,
            "needs_owner_at_pc": bool(owner)}


def evaluate(f: dict, now) -> dict:
    """Pure: facts in, verdict out. f = {hb, checks (engine/ops_checks rows), drift_s, k7 (clock7 rows), disk_free_gb, closed (str|None)}.
    Never raises (a broken part becomes one NOT READY blocker saying the check itself failed)."""
    try:
        return _evaluate(_dd(f), now)
    except Exception as e:  # noqa: BLE001
        bl = [_b(NOT_READY, "Ready check failed", f"The self-check itself broke ({e.__class__.__name__}).",
                 "On the PC: double-click HEALTH_CHECK.bat and read the first red line.", key="check_failed")]
        return _pack(bl, now)


def _evaluate(f: dict, now) -> dict:
    hb = _dd(f.get("hb"))
    paper_only = False
    by = {c.get("key"): c for c in _ll(f.get("checks")) if isinstance(c, dict)}
    out = []
    if f.get("closed"):                      # a full CME closure day (holiday): nothing to trade, nothing to nag about
        v = _pack([], now)
        v["note"] = str(f["closed"])[:60]
        return v
    # 1 the PC itself: dashboard server, the bot, the heartbeat
    for k, nm in (("server", "Dashboard server"), ("bot", "Bot"), ("heartbeat", "Bot heartbeat")):
        c = by.get(k)
        if c and c.get("level") == "bad":
            out.append(_b(NOT_READY, f"{nm} is not running" if k != "heartbeat" else "The bot is not reporting",
                          f"{c.get('text')}. Nothing can trade until it runs.",
                          str(c.get("fix") or "On the PC: double-click START_BOT.bat (type the phrase yourself)."), True, k))
    # 2 the clock: the guard blocks every entry above clock_max_s
    d, mx = f.get("drift_s"), clock_max()
    if d is not None and abs(float(d)) > mx:
        n = int(abs(float(d)) + 0.5)
        out.append(_b(NOT_READY, f"PC clock {n} s {'behind' if d > 0 else 'ahead'}",
                      f"The bot blocks every new entry while the PC clock is more than {mx:.0f} s off internet time.",
                      "On the PC: Settings > Time & language > Date & time > turn 'Set time automatically' on, then press 'Sync now'. "
                      "No restart needed.", True, "clock"))
    # 3 NinjaTrader: the folder and the connection
    c = by.get("nt_folder")
    if c and c.get("level") == "bad":
        out.append(_b(NOT_READY, "NinjaTrader order folder missing", f"{c.get('text')}. The bot cannot send orders.",
                      str(c.get("fix") or "Open NinjaTrader 8 once on this Windows user."), True, "nt_folder"))
    c = by.get("nt_conn")
    if c and c.get("level") in ("bad", "warn"):
        out.append(_b(NOT_READY, "NinjaTrader is not connected", f"{c.get('text')}. No bars, no orders.",
                      "On the PC: open NinjaTrader 8 > Connections > pick your connection (a green dot = connected).", True, "nt_conn"))
    # 4 bars: the LE_BarFeed files
    for k, m in (("feed_1m", 1), ("feed_5m", 5)):
        c = by.get(k)
        if c and c.get("level") == "bad":
            out.append(_b(NOT_READY, f"Price bars are stale ({m} min feed)", f"{c.get('text')}. The bot will not enter on old prices.",
                          "On the PC: NinjaTrader > the MNQ chart with LE_BarFeed > press F5 to reload; check the connection dot is green.",
                          False if k == "feed_5m" else True, k))
            break
    c = by.get("feed_open")
    if c and c.get("level") == "warn":
        out.append(_b(WARN, "1-minute open file is not updating", f"{c.get('text')}. Sizing waits for the bar close.",
                      str(c.get("fix") or "Reload the MNQ chart in NinjaTrader (F5)."), False, "feed_open"))
    # 5 each account armed / held / locked, the kill switch
    try:
        from .preflight import arms
        rows = list(arms(hb)) if hb else []
        live_any = any(str(txt).upper().startswith("LIVE") for _, _, txt in rows)
        if rows and not live_any:
            paper_only = True              # red team 2026-11-23: a Sim / paper-only day is no reason to wake the owner
        for nm, ok, txt in rows:
            if ok or "off" in txt:
                continue
            if "DISABLED" in txt or str(txt).upper().startswith("LIVE"):
                dis = "DISABLED" in txt
                out.append(_b(NOT_READY, f"{nm} is not armed" if not dis else f"{nm} orders are disabled",
                              f"{nm}: {txt}. It will not place a trade until you arm it.",
                              f"On the PC: double-click TRADE_HOME.bat, press 2 (Start bot) and type your arm phrase yourself "
                              f"(Claude never types it).", True, "arm:" + nm.lower()[:20]))
            elif live_any:                 # Sim while another account is LIVE: worth a look, not a NOT READY
                out.append(_b(WARN, f"{nm} is on Sim", f"{nm}: {txt}. It trades Sim, not the real account.",
                              "Only if you meant it to trade for real: TRADE_HOME.bat > 2 and arm it yourself.", True,
                              "sim:" + nm.lower()[:20]))
    except Exception:
        pass
    h = _dd(hb.get("health"))
    if h.get("kill"):
        out.append(_b(NOT_READY, "Kill switch is ON", "The kill switch is on for today: no new orders.",
                      "On the PC dashboard: clear the kill switch only when you are sure (it resets tomorrow).", True, "kill"))
    for r in _ll(h.get("accounts")):
        if isinstance(r, dict) and r.get("locked"):
            nm = {"b25k_2": "Zlarior 25K #2", "rapid": "Rapid EOD"}.get(str(r.get("id") or ""), str(r.get("name") or "An account")[:24])
            out.append(_b(NOT_READY, f"{nm} is halted today", f"{nm} is locked out for today: {str(r.get('locked'))[:80]}.",
                          "Nothing to fix: it unlocks on the next trading day. Check the reason on the dashboard.", False, "locked:" + nm.lower()[:16]))
    # 6 the MFFU 7-day deadline (within 2 days and no keep-alive covering it)
    for r in _ll(f.get("k7")):
        if not isinstance(r, dict):
            continue
        left, ses = r.get("left"), r.get("ses")
        ses = ses if isinstance(ses, (int, float)) else None
        if left is not None and (left <= 2 or (ses is not None and ses <= 2)) and r.get("on") is not True:
            nm = str(r.get("nm") or "An account")[:24]
            hard = left <= 1 or (ses is not None and ses <= 1)       # clock7's own red: 1 day or 1 session left
            out.append(_b(NOT_READY if hard else WARN, f"{nm}: MFFU 7-day deadline in {max(0, int(left))} day(s)"
                          + (f", {int(ses)} session(s) to trade" if ses is not None else ""),
                          "MFFU closes an account with no filled trade in 7 days; the keep-alive is off.",
                          "On the PC: double-click TRADE_HOME.bat, press 3, type KEEP ALIVE ON yourself (or let the bot take a trade).",
                          True, "k7:" + nm.lower()[:16]))
    # 7 a pending update / restart
    c = by.get("winupdate")
    if c and c.get("level") == "warn" and "pending" in str(c.get("text")):
        out.append(_b(WARN, "Windows restart is pending", f"{c.get('text')}.",
                      "On the PC: restart it yourself after 16:00 ET, never during the night session.", True, "winupdate"))
    # 8 disk, internet
    gb = f.get("disk_free_gb")
    if gb is not None and gb < 2:
        out.append(_b(NOT_READY, f"Disk almost full ({gb:.1f} GB free)", "The bot cannot write its state or logs.",
                      "On the PC: double-click CLEAN_STORAGE.bat (or Settings > System > Storage > Cleanup).", True, "disk"))
    elif gb is not None and gb < 10:
        out.append(_b(WARN, f"Disk getting low ({gb:.0f} GB free)", "It can fill up within days.",
                      "On the PC: double-click CLEAN_STORAGE.bat this week.", True, "disk"))
    c = by.get("internet")
    if c and c.get("level") == "bad":
        out.append(_b(NOT_READY, "PC has no internet", "No site answered; prices, pushes and the clock check fail.",
                      "Check the Wi-Fi / router. NinjaTrader must reconnect too.", True, "internet"))
    v = _pack(out, now)
    if paper_only:
        v["paper_only"] = True
    return v


def _pack(bl: list, now) -> dict:
    bl = sorted(bl, key=lambda b: 0 if b["level"] == NOT_READY else 1)       # stable: worst first, then check order
    level = NOT_READY if any(b["level"] == NOT_READY for b in bl) else WARN if bl else READY
    return {"ready": level != NOT_READY, "level": level, "window": window_label(now), "t": int(now), "n": len(bl),
            "blockers": [{k: v for k, v in b.items()} for b in bl[:MAX_SHOWN]]}


def gather_facts(now=None, ctx=None, checks=None) -> dict:
    """What the PC knows now (every part wrapped: a failing one is simply absent). ctx / checks: ops_checks.tick's, to share its probes."""
    now = time.time() if now is None else now
    f: dict = {}
    try:
        from . import ops_checks as OC
        ctx = ctx or OC.gather(now, light=True)
        checks = list(checks) if checks is not None else OC.run_checks({**ctx, "light": True})
        try:
            checks.append(OC.check_windows_update(now))
        except Exception:
            pass
        f["checks"], f["hb"] = checks, ctx.get("hb") or {}
        f["drift_s"] = proven_drift(_dd(ctx.get("net"))) if _dd(ctx.get("net")).get("up") else None
        try:
            f["disk_free_gb"] = shutil.disk_usage(ROOT).free / 1e9
        except Exception:
            pass
        try:
            from . import clock7, preflight
            f["k7"] = _ll(_dd(clock7.build(_dd(preflight.last_ext()).get("mf"), _dd(f["hb"]).get("keepalive"), now)).get("a"))
        except Exception:
            pass
        try:
            from .cme_calendar import full_closure
            e = _et(now)
            nxt = e.date() if e.hour * 60 + e.minute < 17 * 60 + 30 else e.date() + dt.timedelta(days=1)
            if nxt.weekday() < 5 and full_closure(nxt):
                f["closed"] = "market closed"
        except Exception:
            pass
    except Exception:
        pass
    return f


def ready_verdict(now=None, facts=None, ctx=None, checks=None) -> dict:
    """THE function. facts: tests hand fake facts (see evaluate); ctx / checks: the caller's ops_checks.gather / run_checks."""
    now = time.time() if now is None else now
    return evaluate(facts if facts is not None else gather_facts(now, ctx=ctx, checks=checks), now)


# ------------------------------------------------------------------------------------------------ words + the public block
def headline(v: dict) -> str:
    """'NOT READY for 02:00: PC clock 25 s behind' / 'READY for the next window' / 'READY, 1 to watch: ...'."""
    b = _ll(v.get("blockers"))
    w = v.get("window") or "02:00"
    if v.get("level") == NOT_READY:
        return f"NOT READY for {w}: {b[0]['what']}" if b else f"NOT READY for {w}"
    if v.get("level") == WARN:
        return f"READY, 1 to watch: {b[0]['what']}" if b else "READY, 1 to watch"
    return "READY for the next window" if w != "now" else "READY to trade"


def rd(v: dict | None, max_bytes: int = RD_MAX_BYTES, fix: bool = True) -> dict | None:
    """The public status post's block (ext key "rd"): {"s": "ok" | "warn" | "no", "w": window, "b": first blocker, "f": its fix,
    "n": blockers}. Plain words, no ids, no time (the post is dated), <= max_bytes. None when there is no verdict."""
    if not isinstance(v, dict) or v.get("level") not in (READY, WARN, NOT_READY):
        return None
    bl = _ll(v.get("blockers"))
    o = {"s": {READY: "ok", WARN: "warn", NOT_READY: "no"}[v["level"]], "w": str(v.get("window") or "")[:10]}
    if bl:
        o["n"] = int(v.get("n") or len(bl))
        o["b"] = str(bl[0].get("what") or "")[:60]
        fx = str(bl[0].get("exact_fix") or "")
        if fix:
            o["f"] = fx[:100]
    size = lambda x: len(json.dumps(x, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))  # noqa: E731
    for k, step in (("f", 60), ("f", 30), ("f", 0), ("b", 40), ("b", 24)):
        if size(o) <= max_bytes:
            break
        if k in o:
            o[k] = o[k][:step].rstrip()
            if not o[k]:
                o.pop(k)
    while size(o) > max_bytes and o.get("b"):
        o["b"] = o["b"][:-6]
    return o


def read_last(path: str = LAST_PATH, now=None, max_age: int = STALE_VERDICT_S) -> dict | None:
    """The last written verdict, or None when missing / older than max_age (pc_report: the phone then shows 'unknown')."""
    try:
        with open(path, encoding="utf-8") as fh:
            v = json.load(fh)
    except Exception:
        return None
    now = time.time() if now is None else now
    return v if isinstance(v, dict) and now - float(v.get("t") or 0) <= max_age else None


def _write(path: str, obj: dict) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, separators=(",", ":"))
        os.replace(tmp, path)
    except Exception:
        pass


def _read(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            x = json.load(fh)
        return x if isinstance(x, dict) else {}
    except Exception:
        return {}


# ------------------------------------------------------------------------------------------------ the alert + de-dup
def active_period(now) -> bool:
    """Sun 17:25 ET -> Fri 15:30 ET, outside the 15:30-17:25 afternoon: when a NEW blocker is worth a phone alert (the PC
    hibernates Fri evening -> Sun by design; a closed market or a holiday is no reason to wake anyone)."""
    e = _et(now)
    mod, wd = e.hour * 60 + e.minute, e.weekday()
    if wd == 5 or (wd == 4 and mod >= 15 * 60 + 30) or (wd == 6 and mod < 17 * 60 + 25):
        return False
    return not (15 * 60 + 30 <= mod < 17 * 60 + 25)


def due_slot(now, st: dict) -> str | None:
    """'1730' / '0115' / '0845' when its slot is open (up to 25 min late) and not yet done today (once per ET date)."""
    e = _et(now)
    mod = e.hour * 60 + e.minute
    for name, start, days in SLOTS:
        if e.weekday() in days and start <= mod <= start + SLOT_GRACE_MIN and f"{e.date().isoformat()}:{name}" not in _dd(st.get("slots")):
            return name
    return None


def plan_alert(v: dict, st: dict, now, slot: str | None, reason: str = "") -> dict | None:
    """Pure de-dup: the alert to send ({"key", "title", "body", "quiet"}) or None. Mutates st (the caller saves it).
    NOT READY: at most one an hour, and a blocker already told within 30 min is not told again (a changed blocker list
    that holds only fresh blockers goes at once, with the hour rule lifted). READY: one quiet line, only at the 17:30 slot."""
    sent = st.setdefault("sent", {})                 # blocker key -> last time it was in an alert
    if v.get("level") == READY or v.get("level") == WARN:
        if slot == "1730" and v.get("level") == READY:
            return {"key": f"ready:ok:{_et(now).date().isoformat()}", "title": headline(v), "body": "PC, NinjaTrader, bars and accounts look good.", "quiet": True}
        return None
    if v.get("paper_only"):
        return None
    if not active_period(now) and not slot:
        return None
    if now - float(st.get("last_alert", 0)) < MIN_GAP_S:
        return None
    bl = [b for b in _ll(v.get("blockers")) if b["level"] == NOT_READY]
    fresh = [b for b in bl if now - float(sent.get(b["key"], 0)) >= SAME_BLOCKER_S]
    if not fresh:
        return None
    new = [b for b in bl if b["key"] not in _dd(st.get("last_keys"))       # appeared since the last check, and not told
           and now - float(sent.get(b["key"], 0)) >= REPEAT_S]               # within the hour (a flapping blocker is not new)
    if now - float(st.get("last_alert", 0)) < REPEAT_S and not new:
        return None
    top = fresh[0]
    body = f"{top['why_plain_words']} Fix: {top['exact_fix']}"
    more = len(bl) - 1
    if more > 0:
        body += f" (+{more} more: double-click HEALTH_CHECK.bat)"
    for b in fresh:
        sent[b["key"]] = now
    st["last_alert"] = now
    return {"key": f"ready:no:{int(now)}", "title": headline({**v, "blockers": [top], "level": NOT_READY}), "body": body[:600], "quiet": False}


def send_alert(a: dict, sender=None) -> str:
    """Telegram / Discord first (engine/alert_bus), ntfy / Web Push as its fallbacks; with the bus off the old ops path
    (push.pc_send_now). Returns 'bus' | 'push' | 'none'. Never raises."""
    try:
        if sender is not None:
            sender(a)
            return "sender"
        from . import alert_bus as AB
        if AB.active():
            r = AB.send({"kind": "problem", "key": a["key"], "title": a["title"], "body": a["body"], "notify_type": "problems",
                         "report": True, "soft": bool(a.get("quiet"))}, wait=True)
            return "bus" if r in ("sent", "queued") else "none"
        from . import ops_checks as OC
        from . import push
        push.pc_send_now(OC._payload("ready", a["title"], a["body"], a["key"], time.time()))
        return "push"
    except Exception:
        return "none"


def tick(now=None, ctx=None, checks=None, reason: str = "", sender=None, facts=None, last_path: str = LAST_PATH,
         state_path: str = STATE_PATH) -> dict:
    """One scheduled run: the verdict (written to data/ready_last.json), and the alert when one is due. Never raises."""
    now = time.time() if now is None else now
    try:
        st = _read(state_path)
        v = ready_verdict(now, facts=facts, ctx=ctx, checks=checks)
        slot = due_slot(now, st)
        if reason == "start" and not slot and active_period(now):
            slot = "start"
        a = plan_alert(v, st, now, slot, reason)
        via = send_alert(a, sender) if a else None
        if slot in ("1730", "0115", "0845"):
            st.setdefault("slots", {})[f"{_et(now).date().isoformat()}:{slot}"] = int(now)
            st["slots"] = dict(list(st["slots"].items())[-12:])
        st["last_keys"] = {b["key"]: int(now) for b in _ll(v.get("blockers"))}
        _write(state_path, st)
        _write(last_path, v)
        return {"verdict": v, "alert": a, "via": via, "slot": slot}
    except Exception as e:  # noqa: BLE001
        return {"error": e.__class__.__name__}


def start_after_boot(delay_s: float = 90.0) -> None:
    """server.py: once, 90 s after the bot server starts (so ATLAS has had its chance to arm), a verdict + a NOT READY alert."""
    import threading
    if os.environ.get("LE_PC_WATCH") == "0" or os.environ.get("LE_NO_AUTOSTART") == "1" or os.environ.get("LE_SELFTEST_CHILD") == "1" \
            or os.environ.get("LE_READY") == "0":
        return                             # red team 2026-11-23: a dev / test server or the self-test's sealed child never alerts

    def run():
        time.sleep(delay_s)
        tick(reason="start")
    threading.Thread(target=run, name="ready-start", daemon=True).start()


def print_verdict(v: dict) -> None:
    print(headline(v))
    for b in _ll(v.get("blockers")):
        print(f" - {b['what']}: {b['why_plain_words']}\n     fix: {b['exact_fix']}" + ("  (you, at the PC)" if b["needs_owner_at_pc"] else ""))


def main(argv=None) -> int:
    """python -X utf8 -m engine.readiness [--tick]   prints the verdict now (--tick: also writes it and sends an alert if due)."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--tick" in argv:
        r = tick(reason="manual")
        v = r.get("verdict") or {}
    else:
        v = ready_verdict()
    print_verdict(v)
    return 0 if v.get("ready") else 1


if __name__ == "__main__":
    sys.exit(main())
