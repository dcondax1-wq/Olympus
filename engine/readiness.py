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
    """'Zlarior 50K: $1,640 room to the floor, eval day 3 of 10' (funded / passed / failed / not set up said so)."""
    a = a if isinstance(a, dict) else {}
    if not a or a.get("error"):
        return f"{name}: unknown (no board)"
    st = str(a.get("status") or "").lower()
    room = a.get("room")
    head = f"{name}: " + (f"{_money(room)} room to the floor" if room is not None else "room unknown")
    if st in ("passed", "failed"):
        return f"{name}: eval {st.upper()}" + (f" ({_money(room)} room)" if room is not None else "")
    if st == "not set up":
        return f"{name}: not set up"
    if a.get("sessions") is None and a.get("session") is not None:
        return head + f", funded day {a.get('session')}"
    if a.get("session") is not None:
        return head + f", eval day {int(a['session'])} of {int(a.get('sessions') or 10)}"
    return head


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
