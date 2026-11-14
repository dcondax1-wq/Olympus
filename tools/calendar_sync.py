#!/usr/bin/env python3
"""CALENDAR SYNC (team X2 "connect the day", 2026-11-14; owner: "connect to everything: my finances, work schedules, internet").

The owner pastes his calendars' READ-ONLY subscription addresses once on the PC (Google Calendar "Secret address in iCal format",
an iCloud public calendar link, an Outlook "publish calendar" ICS link, or a work-shift app's ICS export: When I Work, Deputy,
7shifts, Homebase, Sling, HotSchedules). Every 15 minutes (the PC report task, tools/pc_report.py, calls maybe_run) this reads
them and writes ONE private file the phone apps read through the PC's own link (docs/LIVE_DASHBOARD.md):

  data/day/day.json   (gitignored; served ONLY by the PC's bot server at /site/day/day.json, never copied into a site folder,
                       so PUBLISH_NQ / Netlify / GitHub Pages never carry it)
    days      per New York day: the work shifts, the busy time, the free blocks, how the shift overlaps the bot's entry window
              (LIT 02:00-15:30 ET), the news of that day (pythia/events.json) and ONE plain sentence ("You work 9-5 today: the
              bot trades alone; check at lunch 12:30.")
    events    the calendar entries of the next two weeks (title, NY times, which calendar, work or not; never a location,
              a description, an attendee or an address)
    week      "hours worked vs $ made trading": hours at work this week, the pay (the money team's import if present, else the
              wage you typed once), trading cash (tools/money_scoreboard.py) and how much of the paycheck it covers
    weather / headlines / inbox   (tools/day_feeds.py, engine/day_inbox.py)

PRIVACY. The addresses (each one is a secret: anyone with it can read that calendar) live only in
%USERPROFILE%\\.olympus\\calendars.json (OLYMPUS_HOME overrides), outside the repo, never in day.json, never printed in full
(--list shows the host). No password is ever asked or stored: the subscription address is all a read-only feed needs.
Nothing here writes to a calendar, trades or sends anything anywhere: it only GETs the addresses you gave.

  python tools/calendar_sync.py --setup              asks for the addresses, work or not, your city and your pay (CONNECT_DAY.bat)
  python tools/calendar_sync.py --add "<address>" [--work] [--name Work]
  python tools/calendar_sync.py --list | --remove <name> | --city "Columbus, OH" (or "39.96,-83.00") | --wage 18.50 | --wage-week 720
  python tools/calendar_sync.py                      sync now and print today's card
  python tools/calendar_sync.py --print              print today's card from the last sync (no network)
  options: --config FILE  --out DIR  --now EPOCH_S  --offline (no network: the cached copies only)
Tests: python -X utf8 -m tests.test_calendar_sync (fixtures: Google, iCloud, Outlook, shift apps, RRULE, DST, overlap).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from tools import ics_parse as I  # noqa: E402

UTC = dt.timezone.utc

VERSION = 1
OUT_DEFAULT = os.path.join(ROOT, "data", "day")
WEB = os.path.join(HERE, "web_public")
SITE_CANDIDATES = (os.path.join(ROOT, "data", "pc_publish", "site"), os.path.join(ROOT, "data", "live_site", "site"))
UA = "olympus-calendar/1 (personal read-only calendar sync)"
FETCH_TIMEOUT_S = 20
MAX_ICS_BYTES = 5 * 1024 * 1024
MAX_CALENDARS = 12
SYNC_EVERY_S = 14 * 60            # the PC report runs every 15 minutes
DAYS_BACK, DAYS_AHEAD = 7, 14
MAX_EVENTS = 400
ENTRY_FROM, ENTRY_TO = 120, 930   # LIT entries 02:00-15:30 ET (CLAUDE.md)
FLAT_AT = 955                     # 15:55 the bot is flat
SLOTS = (("01:45", 105, "morning plan"), ("10:45", 645, "midday plan"), ("16:05", 965, "day summary"))   # the Jarvis copilot cards
AWAKE_DEFAULT = ("07:00", "23:00")
MIN_FREE = 30
WEEKS_PER_MONTH = 52 / 12
# shift apps: a calendar from these hosts is a work calendar unless you say otherwise
SHIFT_HOSTS = ("wheniwork.com", "deputy.com", "7shifts.com", "joinhomebase.com", "homebase.com", "getsling.com", "sling.is", "hotschedules.com",
               "fourth.com", "schedulefly.com", "humanity.com", "shiftboard.com", "workjam.com")
SHIFT_NAME_RX = re.compile(r"\b(shifts?|work schedule|my schedule|schedule|roster|rota|work)\b", re.I)
WORK_TITLE_RX = re.compile(r"^(?:work|shift)\b|\bshift\b|\bon duty\b|\bclock(?:ed)? in\b", re.I)
NOT_SHIFT_RX = re.compile(r"\b(time off|pto|vacation|holiday request|unavailable|unavailability|availability|available|open shift|shift (?:swap|trade|offer)|day off|leave)\b", re.I)
BREAK_RX = re.compile(r"\b(lunch|break)\b", re.I)
EMAIL_RX = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
URL_RX = re.compile(r"https?://\S+|webcal://\S+", re.I)
PAY_RX = re.compile(r"\b(pay ?check|payroll|salary|wages?|direct deposit|job|employer|work pay)\b", re.I)


# ------------------------------------------------------------------------------------------------ small helpers
def olympus_dir(env=None) -> str:
    env = os.environ if env is None else env
    return env.get("OLYMPUS_HOME") or os.path.join(env.get("USERPROFILE") or os.path.expanduser("~"), ".olympus")


def config_path(env=None) -> str:
    return os.path.join(olympus_dir(env), "calendars.json")


def out_dir(env=None) -> str:
    env = os.environ if env is None else env
    return env.get("LE_DAY_DIR") or OUT_DEFAULT


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def write_json(path: str, obj, private: bool = True) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1, default=str)
    os.replace(tmp, path)
    if private:
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    return path


def obj(x) -> dict:
    return x if isinstance(x, dict) else {}


def arr(x) -> list:
    return x if isinstance(x, list) else []


def num(v):
    try:
        x = float(str(v).replace("$", "").replace(",", "").strip()) if isinstance(v, str) else float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x and abs(x) != float("inf") else None


def clean(s, n=120) -> str:
    """plain one-line text with no e-mail address or link in it"""
    t = URL_RX.sub("(link)", EMAIL_RX.sub("(email)", str(s or "")))
    return re.sub(r"[\x00-\x1f<>]", " ", re.sub(r"\s+", " ", t)).strip()[:n]


def short_id(*parts) -> str:
    return hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:12]


def ny():
    return I.new_york()


def hm(mins: int) -> str:
    m = int(mins) % 1440 if mins != 1440 else 1440
    return "24:00" if m == 1440 else f"{m // 60:02d}:{m % 60:02d}"


def hm_mins(s: str):
    m = re.match(r"^([01]?\d|2[0-3]):([0-5]\d)$", str(s or "").strip())
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def word_time(mins: int, suffix: bool = True) -> str:
    """09:00 -> '9', 12:30 -> '12:30', 17:00 -> '5' (+ ' pm' with suffix)"""
    m = int(mins) % 1440
    h, mi = divmod(m, 60)
    h12 = h % 12 or 12
    base = f"{h12}" + (f":{mi:02d}" if mi else "")
    if not suffix:
        return base
    if m == 0:
        return "midnight"
    if m == 720:
        return "noon"
    return base + (" am" if h < 12 else " pm")


def say_time(mins: int) -> str:
    """the time as said: '12:30' at lunch (no am / pm needed), '5 pm', '9:30 am'"""
    m = int(mins) % 1440
    return word_time(m, suffix=not (720 < m < 780))


def span_words(a: int, b: int) -> str:
    """the owner's way to say a shift: 9-5, 7 am-3:30 pm, 5-11 pm, 10 pm-6 am"""
    ah, bh = (a % 1440) // 60, (b % 1440) // 60
    a_am, b_am = ah < 12, bh < 12 or b >= 1440
    if a_am and not b_am and 6 <= ah and bh <= 19 and b - a <= 12 * 60:      # a day shift: "9-5"
        return f"{word_time(a, False)}-{word_time(b, False)}"
    if a_am == b_am and b > a and b < 1440:
        return f"{word_time(a, False)}-{word_time(b)}"
    return f"{word_time(a)}-{word_time(b)}"


def dur_words(mins: int) -> str:
    h, m = divmod(int(round(mins)), 60)
    if not h:
        return f"{m} min"
    return f"{h} h" + (f" {m} min" if m else "")


def day_of(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts, tz=ny()).date().isoformat()


def week_start(day: str) -> str:
    d = dt.date.fromisoformat(day)
    return (d - dt.timedelta(days=d.weekday())).isoformat()


def add_days(day: str, n: int) -> str:
    return (dt.date.fromisoformat(day) + dt.timedelta(days=n)).isoformat()


# ------------------------------------------------------------------------------------------------ the owner's settings (outside the repo)
def normalize_url(raw: str) -> str | None:
    """webcal:// -> https://; only https; no spaces, no user:password@ in the address. None = not a calendar address."""
    u = str(raw or "").strip().strip('"').strip("'").strip("<>")
    if not u or len(u) > 2000 or any(c.isspace() for c in u):
        return None
    if u.lower().startswith("webcal://") or u.lower().startswith("webcals://"):
        u = "https://" + u.split("://", 1)[1]
    p = urllib.parse.urlsplit(u)
    if p.scheme.lower() != "https" or not p.hostname or p.username or p.password:
        return None
    return u


def host_of(url: str) -> str:
    try:
        return (urllib.parse.urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def is_shift_host(url: str) -> bool:
    h = host_of(url)
    return any(h == s or h.endswith("." + s) for s in SHIFT_HOSTS)


def load_config(path: str | None = None) -> dict:
    c = read_json(path or config_path(), {}) or {}
    c = c if isinstance(c, dict) else {}
    cals = []
    for x in arr(c.get("calendars")):
        if isinstance(x, dict) and normalize_url(x.get("url")):
            cals.append({"name": clean(x.get("name"), 40) or f"Calendar {len(cals) + 1}", "url": normalize_url(x["url"]),
                         "work": x.get("work") if isinstance(x.get("work"), bool) else None, "on": x.get("on", True) is not False})
    c["calendars"] = cals[:MAX_CALENDARS]
    return c


def save_config(c: dict, path: str | None = None) -> str:
    p = path or config_path()
    return write_json(p, c, private=True)


def add_calendar(c: dict, url: str, name: str | None = None, work: bool | None = None) -> tuple[dict, str]:
    u = normalize_url(url)
    if not u:
        raise ValueError("that is not a calendar address: it must start with https:// or webcal:// (copy the whole link)")
    cals = [x for x in arr(c.get("calendars")) if x.get("url") != u]
    if len(cals) >= MAX_CALENDARS:
        raise ValueError(f"at most {MAX_CALENDARS} calendars")
    nm = clean(name, 40) or ("Work" if (work or is_shift_host(u)) else f"Calendar {len(cals) + 1}")
    if any(x.get("name") == nm for x in cals):
        nm = f"{nm} {len(cals) + 1}"
    cals.append({"name": nm, "url": u, "work": work if work is not None else (True if is_shift_host(u) else None), "on": True})
    c["calendars"] = cals
    return c, nm


def masked(url: str) -> str:
    return f"{host_of(url) or '?'} (the secret part of the address is hidden)"


# ------------------------------------------------------------------------------------------------ the network (only the addresses you gave)
def fetch(url: str, opener=None, timeout: float = FETCH_TIMEOUT_S) -> str:
    """GET one calendar. opener(url, headers, timeout) -> (status, bytes) for tests. Raises on failure."""
    headers = {"User-Agent": UA, "Accept": "text/calendar, text/plain;q=0.8, */*;q=0.5"}
    if opener is not None:
        status, body = opener(url, headers, timeout)
    else:
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as r:     # noqa: S310  (https only: normalize_url)
            status, body = r.status, r.read(MAX_ICS_BYTES + 1)
    if status != 200:
        raise OSError(f"HTTP {status}")
    if len(body) > MAX_ICS_BYTES:
        raise OSError("the calendar is larger than 5 MB")
    text = body.decode("utf-8", "replace") if isinstance(body, (bytes, bytearray)) else str(body)
    if "BEGIN:VCALENDAR" not in text[:4096].upper():
        raise OSError("the address did not return a calendar (it may be the wrong link, or a sign-in page)")
    return text


def cache_file(work_dir: str, url: str) -> str:
    return os.path.join(work_dir, "cache", short_id(url) + ".ics")


# ------------------------------------------------------------------------------------------------ the day, from the calendars
def _is_work(cal_cfg: dict, cal: I.Calendar, title: str, all_day: bool) -> bool:
    if all_day or NOT_SHIFT_RX.search(title or "") or BREAK_RX.search(title or ""):
        return False
    flag = cal_cfg.get("work")
    if flag is True:
        return True
    if flag is False:
        return False
    if is_shift_host(cal_cfg.get("url", "")) or SHIFT_NAME_RX.search(cal_cfg.get("name", "")) or SHIFT_NAME_RX.search(cal.name or ""):
        return True
    return bool(WORK_TITLE_RX.search(title or ""))


def _segments(s: dt.datetime, e: dt.datetime) -> list:
    """an instance in New York days: [(day, from_min, to_min)], a night shift is cut at midnight"""
    z = ny()
    a, b = s.astimezone(UTC).astimezone(z), e.astimezone(UTC).astimezone(z)      # through UTC: a wall time that does not exist is normalised
    out = []
    cur = a
    while True:
        d = cur.date()
        nxt = dt.datetime.combine(d + dt.timedelta(days=1), dt.time(), tzinfo=z)
        end = min(b, nxt)
        fm = cur.hour * 60 + cur.minute
        tm = 1440 if end >= nxt else end.hour * 60 + end.minute
        if tm > fm or (tm == fm and a == b):
            out.append((d.isoformat(), fm, tm))
        if b <= nxt:
            break
        cur = nxt
        if len(out) > 40:
            break
    return out


def collect(cal_texts: list, now_s: float, titles: bool = True) -> dict:
    """cal_texts: [(cfg {name, url, work}, ics text or None, meta {ok, error, t})] -> {events, per_day, calendars}"""
    z = ny()
    today = day_of(now_s)
    d0 = dt.date.fromisoformat(today) - dt.timedelta(days=DAYS_BACK)
    d1 = dt.date.fromisoformat(today) + dt.timedelta(days=DAYS_AHEAD + 1)
    w_start = dt.datetime.combine(d0, dt.time(), tzinfo=z)
    w_end = dt.datetime.combine(d1, dt.time(), tzinfo=z)
    events, per_day, cals = [], {}, []
    for cfg, text, meta in cal_texts:
        row = {"name": cfg.get("name"), "host": host_of(cfg.get("url", "")), "work": None, "ok": bool(meta.get("ok")), "events": 0, "skipped_rules": 0,
               "bad": 0, "t": meta.get("t"), "error": clean(meta.get("error"), 160) or None, "cached": bool(meta.get("cached"))}
        if text:
            cal = I.parse(text, default_tz=z)
            occ = I.occurrences(cal, w_start, w_end)
            row["bad"], row["skipped_rules"] = cal.bad, cal.skipped
            any_work = False
            for o in occ:
                title_raw = clean(o["title"], 80) or "Busy"
                work = _is_work(cfg, cal, title_raw, o["all_day"])
                any_work = any_work or work
                title = title_raw if titles else ("Work shift" if work else "Busy")
                if o["all_day"]:
                    day = o["start"].isoformat()
                    last = (o["end"] - dt.timedelta(days=1)) if o["end"] > o["start"] else o["start"]
                    ev = {"id": short_id(cfg.get("url"), o["uid"], day), "day": day, "end_day": last.isoformat(), "all_day": True, "start": "", "end": "",
                          "title": title, "cal": cfg.get("name"), "work": False, "busy": False, "brk": False}
                    events.append(ev)
                    d = dt.date.fromisoformat(day)
                    while d <= last and d < d1:
                        if d >= d0:
                            per_day.setdefault(d.isoformat(), {"segs": [], "allday": []})["allday"].append(title)
                        d += dt.timedelta(days=1)
                    continue
                segs = _segments(o["start"], o["end"])
                a = o["start"].astimezone(UTC).astimezone(z)
                b = o["end"].astimezone(UTC).astimezone(z)
                ev = {"id": short_id(cfg.get("url"), o["uid"], o["start"].isoformat()), "day": a.date().isoformat(), "end_day": b.date().isoformat(),
                      "all_day": False, "start": f"{a.hour:02d}:{a.minute:02d}", "end": f"{b.hour:02d}:{b.minute:02d}", "mins": int((b - a).total_seconds() // 60),
                      "title": title, "cal": cfg.get("name"), "work": work, "busy": bool(o["busy"]), "brk": bool(BREAK_RX.search(title_raw))}
                events.append(ev)
                for (d, fm, tm) in segs:
                    per_day.setdefault(d, {"segs": [], "allday": []})["segs"].append({"from": fm, "to": tm, "work": work, "busy": bool(o["busy"]), "brk": ev["brk"], "title": title})
            row["events"] = len(occ)
            row["work"] = True if (cfg.get("work") is True or (cfg.get("work") is None and any_work)) else (False if cfg.get("work") is False else None)
        cals.append(row)
    events.sort(key=lambda e: (e["day"], e["start"] or "", e["title"]))
    return {"events": events, "per_day": per_day, "calendars": cals}


def merge(spans: list) -> list:
    out = []
    for a, b in sorted(spans):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def overlap(spans: list, a: int, b: int) -> int:
    return sum(max(0, min(y, b) - max(x, a)) for x, y in spans)


# ------------------------------------------------------------------------------------------------ the market's day (pythia/events.json)
def market_of(pythia) -> dict:
    """{day: {"closed": bool, "early": "13:15" | None, "news": [{time, title, impact}]}}"""
    out = {}
    for e in arr(obj(pythia).get("events")):
        if not isinstance(e, dict) or not re.match(r"^\d{4}-\d{2}-\d{2}$", str(e.get("date") or "")):
            continue
        m = out.setdefault(e["date"], {"closed": False, "early": None, "news": []})
        if e.get("closed") is True:
            m["closed"] = True
        if e.get("kind") == "early":
            m["early"] = e.get("close_et") if hm_mins(e.get("close_et")) is not None else (e.get("time") if hm_mins(e.get("time")) is not None else None)
        if e.get("impact") in ("high", "med") and hm_mins(e.get("time")) is not None and e.get("kind") not in ("early", "holiday"):
            m["news"].append({"time": e["time"], "title": clean(e.get("title"), 60), "impact": e["impact"]})
    for m in out.values():
        m["news"].sort(key=lambda n: n["time"])
    return out


def find_pythia(site_dir: str | None = None):
    for d in ([site_dir] if site_dir else []) + list(SITE_CANDIDATES) + [WEB]:
        j = read_json(os.path.join(d, "pythia", "events.json"))
        if isinstance(j, dict):
            return j
    return None


# ------------------------------------------------------------------------------------------------ ONE sentence per day
def check_time(shifts: list, breaks: list) -> tuple[int | None, str]:
    """when to look at the phone on a work day: a lunch / break in your calendar, else 3 h 30 into a long shift, else after it"""
    if not shifts:
        return None, ""
    main = max(shifts, key=lambda s: s[1] - s[0])
    for a, b in sorted(breaks):
        if main[0] <= a < main[1] and a < ENTRY_TO:
            return a, "on your break"
    if main[1] - main[0] >= 5 * 60:
        t = main[0] + 210
        t -= t % 30
        if t < ENTRY_TO + 25:
            return t, "at lunch" if 660 <= t < 870 else "on a break"
    if main[1] < FLAT_AT:
        return main[1], "when you finish"
    return None, ""


def advise(day: str, info: dict, mkt: dict, live_needed: bool = False) -> dict:
    """the day's plain sentence and its details. info = {"segs": [...], "allday": [...]}; mkt = market_of()[day]"""
    d = dt.date.fromisoformat(day)
    segs = arr(info.get("segs"))
    shifts = merge([[s["from"], s["to"]] for s in segs if s.get("work")])
    breaks = [[s["from"], s["to"]] for s in segs if s.get("brk")]
    work_mins = sum(b - a for a, b in shifts)
    entry_to = ENTRY_TO
    early = mkt.get("early") if mkt else None
    if early and hm_mins(early) is not None:
        entry_to = min(ENTRY_TO, hm_mins(early) - 30)
    ov = overlap(shifts, ENTRY_FROM, entry_to)
    weekend = d.weekday() >= 5
    closed = weekend or bool(mkt and mkt.get("closed"))
    shift_txt = ", ".join(span_words(a, b) for a, b in shifts)
    notes, check_at, check_word = [], None, ""
    if closed:
        tone = "info"
        lead = ("Weekend" if weekend else "Market closed today") + ": the bot does not trade."
        text = lead + (f" You work {shift_txt}." if shifts else " No work in your calendar.")
    elif not shifts:
        tone = "ok"
        text = "No work today: you are free for the whole session (entries 02:00-15:30 ET)."
        check_at, check_word = 645, "for the midday plan"
    elif ov == 0:
        tone = "ok"
        if shifts[0][0] >= entry_to:
            text = f"You work {shift_txt} today, after the session: read the 10:45 plan and the 16:05 summary before you go."
        else:
            text = f"You work {shift_txt} today, outside the bot's entry window: the session is yours to watch."
        check_at, check_word = 645, "for the midday plan"
    else:
        tone = "warn" if ov >= 120 else "info"
        check_at, check_word = check_time(shifts, breaks)
        lead = f"You work {shift_txt} today: the bot trades alone"
        if check_at is not None:
            text = f"{lead}; check {check_word} {say_time(check_at)}."
        else:
            text = f"{lead}; look at the 16:05 summary after work."
        end_last = shifts[-1][1]
        if end_last < entry_to:
            left = entry_to - max(end_last, ENTRY_FROM)
            notes.append(f"You are free from {say_time(end_last)}: {dur_words(left)} of the entry window left.")
    if mkt and not closed:
        if early:
            notes.append(f"Early close {early} ET: the bot is flat before then.")
        for n in arr(mkt.get("news")):
            t = hm_mins(n["time"])
            inside = any(a <= t < b for a, b in shifts)
            if n["impact"] == "high" or inside:
                notes.append(f"{n['title']} {n['time']} ET" + (" lands during your shift: the bot follows its own rules, nothing to do." if inside else "."))
    if shifts and not closed:
        bits = []
        for sid, m, label in SLOTS:
            sh = next(((a, b) for a, b in shifts if a <= m < b), None)
            if not sh or (check_at is not None and abs(check_at - m) <= 20):
                continue
            if check_at is not None and check_at > m:
                bits.append(f"the {sid} {label}: read it {check_word} {say_time(check_at)}")
            else:
                bits.append(f"the {sid} {label}: read it after work ({say_time(sh[1])})")
        if bits:
            notes.append("At work you miss " + "; ".join(bits) + ".")
    if live_needed and shifts and not closed and ov:
        notes.append("A live account needs you present: only the eval / Sim runs while you work (the bot never arms live by itself).")
    return {"day": day, "weekday": d.strftime("%A"), "closed": closed, "work": [{"start": hm(a), "end": hm(b), "mins": b - a} for a, b in shifts],
            "work_mins": work_mins, "overlap_mins": ov, "entry_window": [hm(ENTRY_FROM), hm(entry_to)], "check_at": hm(check_at) if check_at is not None else None,
            "text": text, "notes": notes[:5], "tone": tone, "news": arr(obj(mkt).get("news"))[:4], "early": early}


def free_blocks(info: dict, awake=AWAKE_DEFAULT) -> list:
    a0, a1 = hm_mins(awake[0]) or 420, hm_mins(awake[1]) or 1380
    busy = merge([[s["from"], s["to"]] for s in arr(info.get("segs")) if s.get("busy")])
    out, cur = [], a0
    for a, b in busy:
        if b <= cur:
            continue
        if a > cur:
            e = min(a, a1)
            if e - cur >= MIN_FREE:
                out.append({"start": hm(cur), "end": hm(e), "mins": e - cur})
        cur = max(cur, b)
        if cur >= a1:
            break
    if a1 - cur >= MIN_FREE:
        out.append({"start": hm(cur), "end": hm(a1), "mins": a1 - cur})
    return out


# ------------------------------------------------------------------------------------------------ hours worked vs $ made trading
def newest_site() -> str | None:
    best = None
    for d in SITE_CANDIDATES:
        try:
            t = os.path.getmtime(os.path.join(d, "index.html"))
        except OSError:
            continue
        if best is None or t > best[0]:
            best = (t, d)
    return best[1] if best else None


def paychecks(ledger_path: str | None = None, inbox_path: str | None = None) -> list:
    """the money team's import: income entries that look like a paycheck in data/money_ledger.json (a Ledger export) and
    paycheck lines in the money inbox (POST /inbox/money, type paycheck). -> [(date, usd)]; notes are read, never kept."""
    out = []
    led = read_json(ledger_path or os.path.join(ROOT, "data", "money_ledger.json"), {}) or {}
    for e in arr(obj(led).get("entries")):
        if not isinstance(e, dict) or e.get("kind") != "income":
            continue
        blob = " ".join(str(e.get(k) or "") for k in ("acct", "note", "title", "source", "tag", "tags"))
        amt = num(e.get("amount"))
        if amt and amt > 0 and PAY_RX.search(blob) and re.match(r"^\d{4}-\d{2}-\d{2}$", str(e.get("date") or "")):
            out.append((e["date"], round(amt, 2)))
    ip = inbox_path or os.path.join(ROOT, "data", "inbox", "money.jsonl")
    try:
        with open(ip, encoding="utf-8") as fh:
            for line in fh:
                try:
                    j = json.loads(line)
                except ValueError:
                    continue
                if isinstance(j, dict) and str(j.get("type") or "").lower() in ("paycheck", "pay", "salary", "wage"):
                    amt = num(j.get("usd", j.get("amount")))
                    d = str(j.get("date") or "")[:10] or (day_of(j["t"]) if num(j.get("t")) else "")
                    if amt and amt > 0 and re.match(r"^\d{4}-\d{2}-\d{2}$", d):
                        out.append((d, round(amt, 2)))
    except OSError:
        pass
    return sorted(out)


def pay_of(cfg: dict, checks: list, today: str, hours_week: float) -> dict:
    """{"week_usd", "month_usd", "src", "text"}: the paychecks of the last 8 weeks first, else the wage you typed"""
    cut = add_days(today, -56)
    recent = [(d, a) for d, a in checks if cut < d <= today]
    if recent:
        # one paycheck covers the days until the next one: the average gap between them (a single one: every 2 weeks)
        first, last = dt.date.fromisoformat(recent[0][0]), dt.date.fromisoformat(recent[-1][0])
        gap = (last - first).days / (len(recent) - 1) if len(recent) > 1 else 14
        gap = min(31, max(7, gap))
        week = (sum(a for _, a in recent) / len(recent)) / (gap / 7)
        return {"week_usd": round(week, 2), "month_usd": round(week * WEEKS_PER_MONTH, 2), "src": "import", "every_days": round(gap),
                "text": f"{len(recent)} paycheck{'s' if len(recent) != 1 else ''} in the last 8 weeks, about every {round(gap)} days (your money import)"}
    w = obj(cfg.get("wage"))
    hourly, weekly = num(w.get("hourly")), num(w.get("weekly"))
    if hourly and hourly > 0:
        week = hourly * hours_week
        avg_h = num(w.get("hours_week")) or hours_week or 0
        return {"week_usd": round(week, 2), "month_usd": round(hourly * avg_h * WEEKS_PER_MONTH, 2) if avg_h else None, "src": "wage", "hourly": hourly,
                "text": f"${hourly:,.2f} an hour (the wage you typed)"}
    if weekly and weekly > 0:
        return {"week_usd": round(weekly, 2), "month_usd": round(weekly * WEEKS_PER_MONTH, 2), "src": "wage", "text": "the weekly pay you typed"}
    return {"week_usd": None, "month_usd": None, "src": None, "text": "no pay yet: type it once with --wage 18.50 (or import your paychecks in the Ledger)"}


def usd(x, sign=False) -> str:
    v = num(x)
    if v is None:
        return "?"
    a = abs(round(v))
    return ("-" if v < 0 and a else "+" if sign and v > 0 else "") + f"${a:,}"


def trading_of(now_s: float, site_dir: str | None = None, sb=None) -> dict:
    """the money scoreboard's numbers (tools/money_scoreboard.py): cash really made trading + the eval P&L (paper until a payout)"""
    try:
        if sb is None:
            from tools import money_scoreboard as MS
            g = MS.gather(site=site_dir or newest_site())
            sb = MS.build(g, now_s, include_ledger=True)
            accts = MS.accounts_of(g.get("home"))
        else:
            accts = obj(sb.get("_accounts"))
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "why": f"{e.__class__.__name__}"}
    tot = obj(sb.get("totals"))
    rr = obj(sb.get("run_rate"))
    eval_week = sum(num(a.get("week")) or 0 for a in accts.values() if isinstance(a, dict) and a.get("has") and not a.get("paper"))
    return {"ok": True, "cash_week": num(obj(tot.get("week")).get("net")), "cash_month": num(obj(tot.get("month")).get("net")),
            "cash_per_month": num(rr.get("cash_per_month")), "plan_per_month": num(obj(rr.get("plan")).get("per_month")),
            "eval_week": round(eval_week, 2), "rate_text": str(rr.get("text") or "")[:160]}


def week_line(today: str, days: dict, pay: dict, trade: dict, now_s: float) -> dict:
    ws = week_start(today)
    wk = [add_days(ws, i) for i in range(7)]
    now_min = dt.datetime.fromtimestamp(now_s, tz=ny())
    now_m = now_min.hour * 60 + now_min.minute
    total = done = 0
    for d in wk:
        for s in arr(obj(days.get(d)).get("work")):
            a, b = hm_mins(s["start"]), (1440 if s["end"] == "24:00" else hm_mins(s["end"]))
            if a is None or b is None:
                continue
            total += b - a
            if d < today:
                done += b - a
            elif d == today:
                done += max(0, min(b, now_m) - a)
    hours = round(total / 60, 1)
    pay_week = pay.get("week_usd")
    if pay.get("src") == "wage" and pay.get("hourly"):
        pay_week = round(pay["hourly"] * total / 60, 2)
    parts = [f"This week: {hours:g} h at work" + (f" ({round(done / 60, 1):g} h done)" if done and done < total else "")
             + (f", about {usd(pay_week)} pay" if pay_week else "") + "."]
    cover = None
    if trade.get("ok"):
        cw, ev = trade.get("cash_week"), trade.get("eval_week")
        parts.append(f"Trading: {usd(cw or 0, True)} cash this week" + (f", eval P&L {usd(ev, True)} (not cash until a payout)" if ev else "") + ".")
        pm, cpm, plan = pay.get("month_usd"), trade.get("cash_per_month"), trade.get("plan_per_month")
        if pm:
            if cpm is not None:
                cover = max(0, round(100 * cpm / pm))
                parts.append(f"To quit: the paycheck is about {usd(pm)} a month; trading cash covers {cover}% of it.")
            else:
                parts.append(f"To quit: the paycheck is about {usd(pm)} a month; no trading cash rate yet" + (f" (the plan estimate {usd(plan)} a month would cover {round(100 * plan / pm)}%)." if plan else "."))
    else:
        parts.append("Trading: the money scoreboard is not readable here.")
    return {"from": ws, "to": wk[-1], "work_hours": hours, "done_hours": round(done / 60, 1), "pay_week": pay_week, "pay": pay, "trading": trade,
            "covers_pct": cover, "line": " ".join(parts)}


# ------------------------------------------------------------------------------------------------ the file
def build(cal_texts: list, now_s: float, cfg: dict | None = None, pythia=None, trade: dict | None = None, checks: list | None = None,
          live_needed: bool = False, extras: dict | None = None) -> dict:
    cfg = obj(cfg)
    today = day_of(now_s)
    col = collect(cal_texts, now_s, titles=cfg.get("titles", True) is not False)
    mkt = market_of(pythia)
    awake = tuple(cfg.get("awake")) if isinstance(cfg.get("awake"), list) and len(cfg["awake"]) == 2 else AWAKE_DEFAULT
    days = {}
    for i in range(-DAYS_BACK, DAYS_AHEAD + 1):
        d = add_days(today, i)
        info = col["per_day"].get(d, {"segs": [], "allday": []})
        a = advise(d, info, mkt.get(d) or {}, live_needed=live_needed)
        a["free"] = free_blocks(info, awake)
        a["all_day"] = info.get("allday", [])[:6]
        days[d] = a
    week_mins = sum(x["mins"] for i in range(7) for x in obj(days.get(add_days(week_start(today), i))).get("work", []))
    pay = pay_of(cfg, checks or [], today, week_mins / 60)
    week = week_line(today, days, pay, trade or {"ok": False}, now_s)
    ev = [e for e in col["events"] if add_days(today, -1) <= e["day"] <= add_days(today, DAYS_AHEAD)][:MAX_EVENTS]
    out = {"v": VERSION, "kind": "olympus-day", "t": int(now_s), "built": dt.datetime.fromtimestamp(now_s, tz=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "tz": "America/New_York", "today": today, "private": True,
           "about": "Your day from your own calendars, made on your PC. Private: only the PC's own link serves it; it is never on the public site.",
           "calendars": col["calendars"], "connected": bool(col["calendars"]), "days": days, "events": ev, "week": week,
           "windows": {"entries": [hm(ENTRY_FROM), hm(ENTRY_TO)], "flat": hm(FLAT_AT), "slots": [s[0] for s in SLOTS]}}
    for k, v in obj(extras).items():
        out[k] = v
    return out


def card_text(d: dict) -> str:
    t = obj(obj(d.get("days")).get(d.get("today")))
    lines = [f"  Today ({d.get('today')}): {t.get('text', 'no calendar yet')}"]
    for n in arr(t.get("notes"))[:3]:
        lines.append(f"    - {n}")
    lines.append(f"  {obj(d.get('week')).get('line', '')}")
    for c in arr(d.get("calendars")):
        lines.append(f"  [{'OK' if c.get('ok') else '..'}] {c.get('name')}: {c.get('events')} entries" + (" (work)" if c.get("work") else "")
                     + (f", {c.get('error')}" if c.get("error") else "") + (" (last good copy)" if c.get("cached") else ""))
    return "\n".join(lines)


def live_needed_of(site_dir: str | None) -> bool:
    """a funded / live account on the board (home.json): the presence note goes into the work-day advice"""
    for d in ([site_dir] if site_dir else []) + [x for x in SITE_CANDIDATES]:
        h = read_json(os.path.join(d, "home.json"))
        if isinstance(h, dict):
            b = obj(h.get("board"))
            return any(str(obj(b.get(k)).get("stage") or obj(b.get(k)).get("kind") or "").lower() in ("funded", "live") for k in ("lit", "atlas", "blitz"))
    return False


def sync(now_s: float | None = None, cfg_path: str | None = None, work_dir: str | None = None, opener=None, offline: bool = False,
         site_dir: str | None = None, trade: dict | None = None, feeds: bool = True, say=print) -> dict | None:
    """Read every calendar (or its last good copy), write data/day/day.json. None when no calendar is set up. Never raises on a
    calendar that fails: that one is marked and its last good copy is used."""
    now_s = time.time() if now_s is None else now_s
    work_dir = work_dir or out_dir()
    cfg = load_config(cfg_path)
    cals = [c for c in cfg["calendars"] if c.get("on", True)]
    if not cals and not cfg.get("city"):
        return None
    texts = []
    for c in cals:
        cf = cache_file(work_dir, c["url"])
        meta = {"ok": False, "error": None, "t": None, "cached": False}
        text = None
        if not offline:
            try:
                text = fetch(c["url"], opener=opener)
                os.makedirs(os.path.dirname(cf), exist_ok=True)
                with open(cf, "w", encoding="utf-8") as fh:
                    fh.write(text)
                try:
                    os.chmod(cf, 0o600)
                except OSError:
                    pass
                meta.update(ok=True, t=int(now_s))
            except Exception as e:  # noqa: BLE001
                meta["error"] = f"{e.__class__.__name__}: {e}"[:160]
        if text is None:
            try:
                with open(cf, encoding="utf-8") as fh:
                    text = fh.read()
                meta.update(cached=True, t=int(os.path.getmtime(cf)), ok=offline)
            except OSError:
                pass
        texts.append((c, text, meta))
    site = site_dir or newest_site()
    extras = {}
    if feeds:
        try:
            from tools import day_feeds
            extras = day_feeds.gather(cfg, now_s, work_dir=work_dir, opener=opener, offline=offline, say=say)
        except Exception as e:  # noqa: BLE001
            extras = {"feeds_error": f"{e.__class__.__name__}"}
    out = build(texts, now_s, cfg, pythia=find_pythia(site), trade=trade if trade is not None else trading_of(now_s, site),
                checks=paychecks(), live_needed=live_needed_of(site), extras=extras)
    write_json(os.path.join(work_dir, "day.json"), out)
    st_path = os.path.join(work_dir, "state.json")
    st = read_json(st_path, {}) or {}
    st.update(last_t=int(now_s), calendars=len(cals), ok=sum(1 for _, _, m in texts if m.get("ok")))
    write_json(st_path, st)
    return out


def maybe_run(now_s: float | None = None, work_dir: str | None = None, cfg_path: str | None = None, say=print, opener=None, env=None) -> dict | None:
    """The hook tools/pc_report.py calls every 15 minutes. Quiet when nothing is set up; never raises; LE_CALENDAR=0 turns it off."""
    try:
        e = os.environ if env is None else env
        if str(e.get("LE_CALENDAR", "1")) == "0":
            return None
        now_s = time.time() if now_s is None else now_s
        work_dir = work_dir or out_dir(e)
        p = cfg_path or config_path(e)
        if not os.path.exists(p):
            return None
        st = read_json(os.path.join(work_dir, "state.json"), {}) or {}
        if now_s - (num(st.get("last_t")) or 0) < SYNC_EVERY_S:
            return None
        out = sync(now_s, cfg_path=p, work_dir=work_dir, opener=opener, say=say)
        if out:
            t = obj(obj(out.get("days")).get(out.get("today")))
            say(f"  [OK]  your day: {t.get('text', '')}")
        return out
    except Exception as ex:  # noqa: BLE001
        say(f"  [..] calendar sync skipped: {ex.__class__.__name__}: {str(ex)[:120]}")
        return None


# ------------------------------------------------------------------------------------------------ the owner's one-time setup
def setup(ask=input, say=print, cfg_path: str | None = None, geocode=None) -> dict:
    """CONNECT_DAY.bat: paste each calendar address (Enter on an empty line ends), work or not, the city, the pay."""
    p = cfg_path or config_path()
    cfg = load_config(p)
    say("Connect your day. Nothing here can change your calendars: these addresses are read-only.")
    say("Paste one calendar address (Google 'Secret address in iCal format', iCloud public link, Outlook ICS, or your shift app's")
    say("calendar link). Press Enter on an empty line when you are done.")
    while True:
        raw = (ask("  Calendar address (or Enter to finish): ") or "").strip()
        if not raw:
            break
        u = normalize_url(raw)
        if not u:
            say("  [FIX] that is not a calendar address: it starts with https:// or webcal://. Try again.")
            continue
        shift = is_shift_host(u)
        w = (ask(f"  Is this your WORK schedule? [{'Y/n' if shift else 'y/N'}]: ") or "").strip().lower()
        work = (w != "n") if shift else (w == "y")
        name = (ask("  A short name for it (Enter = " + ("Work" if work else "Personal") + "): ") or "").strip() or ("Work" if work else "Personal")
        try:
            cfg, nm = add_calendar(cfg, u, name, work)
            say(f"  [OK]  saved {nm}: {masked(u)}")
        except ValueError as e:
            say(f"  [FIX] {e}")
    city = (ask("  Your city for the weather (like Columbus, OH), Enter to skip: ") or "").strip()
    if city:
        try:
            from tools import day_feeds
            place = day_feeds.set_city(cfg, city, geocode=geocode)
            say(f"  [OK]  weather for {place}")
        except Exception as e:  # noqa: BLE001
            say(f"  [..] city not set: {e}")
    wage = (ask("  Your pay an hour in $ (like 18.50), Enter to skip: ") or "").strip()
    if wage:
        v = num(wage)
        if v and 0 < v < 1000:
            cfg["wage"] = {"hourly": round(v, 2)}
            say(f"  [OK]  ${v:,.2f} an hour")
        else:
            say("  [..] pay not saved (type a number like 18.50)")
    save_config(cfg, p)
    say(f"  [OK]  saved in {p} (outside the bot folder; never uploaded)")
    return cfg


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Your calendars -> data/day/day.json (private, read on the PC's own link).")
    ap.add_argument("--setup", action="store_true")
    ap.add_argument("--add")
    ap.add_argument("--work", action="store_true")
    ap.add_argument("--name")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--remove")
    ap.add_argument("--city")
    ap.add_argument("--wage", type=float)
    ap.add_argument("--wage-week", type=float)
    ap.add_argument("--print", action="store_true", dest="show")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--config")
    ap.add_argument("--out")
    ap.add_argument("--now", type=float)
    a = ap.parse_args(argv)
    p = a.config or config_path()
    work_dir = a.out or out_dir()
    if a.setup:
        setup(cfg_path=p)
        a.add = None
    cfg = load_config(p)
    changed = False
    if a.add:
        try:
            cfg, nm = add_calendar(cfg, a.add, a.name, True if a.work else None)
            print(f"  [OK]  saved {nm}: {masked(normalize_url(a.add))}")
            changed = True
        except ValueError as e:
            print(f"  [FIX] {e}")
            return 1
    if a.remove:
        before = len(cfg["calendars"])
        cfg["calendars"] = [c for c in cfg["calendars"] if c["name"].lower() != a.remove.lower()]
        print(f"  [OK]  removed {a.remove}" if len(cfg["calendars"]) < before else f"  [..] no calendar named {a.remove}")
        changed = True
    if a.city:
        try:
            from tools import day_feeds
            print(f"  [OK]  weather for {day_feeds.set_city(cfg, a.city)}")
            changed = True
        except Exception as e:  # noqa: BLE001
            print(f"  [FIX] city not set: {e}")
    if a.wage:
        cfg["wage"] = {"hourly": round(a.wage, 2)}
        changed = True
    if a.wage_week:
        cfg["wage"] = {"weekly": round(a.wage_week, 2)}
        changed = True
    if changed:
        save_config(cfg, p)
    if a.list:
        for c in cfg["calendars"]:
            print(f"  {c['name']}: {masked(c['url'])}" + (" (work)" if c.get("work") else ""))
        if not cfg["calendars"]:
            print("  no calendars yet: python tools/calendar_sync.py --add \"<address>\"")
        return 0
    if a.show:
        d = read_json(os.path.join(work_dir, "day.json"))
        print(card_text(d) if isinstance(d, dict) else "  no sync yet")
        return 0
    if a.setup or changed or not (a.list or a.show):
        out = sync(a.now, cfg_path=p, work_dir=work_dir, offline=a.offline)
        print(card_text(out) if out else "  nothing to sync yet: add a calendar first (CONNECT_DAY.bat)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
