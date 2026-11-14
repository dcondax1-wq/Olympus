"""ICS LITE: a small stdlib reader of iCalendar (.ics) files for tools/calendar_sync.py (team X2 "connect the day", 2026-11-14).

It reads what the owner's calendars publish as a read-only subscription address: Google Calendar ("secret address in iCal
format"), iCloud (public calendar link, webcal://), Outlook / Office 365 ("publish a calendar", ICS link) and the work-shift apps
that export ICS (When I Work, Deputy, 7shifts, Homebase, Sling, HotSchedules). Nothing here touches the network or a file.

  parse(text)                       -> Calendar: .events (master VEVENTs), .overrides (RECURRENCE-ID), .name, .tz (X-WR-TIMEZONE)
  occurrences(cal, start, end)      -> [Occ]: every instance that overlaps [start, end) (aware datetimes), recurring ones expanded
  Occ = { uid, title, start, end, all_day, busy, status, day_start/day_end (dates for all-day) }

Supported: line folding, escaped text, DTSTART / DTEND / DURATION, VALUE=DATE (all day), UTC "Z", TZID (IANA names, Outlook's
Windows names such as "Eastern Standard Time", the "/mozilla.org/.../America/New_York" style), floating times (the calendar's
X-WR-TIMEZONE, else New York), the file's own VTIMEZONE rules when the zone is unknown to Python, RRULE FREQ=DAILY / WEEKLY /
MONTHLY / YEARLY with INTERVAL, COUNT, UNTIL, BYDAY (MO, 2TU, -1FR), BYMONTHDAY (also negative), BYMONTH, BYSETPOS (single
values, MONTHLY), EXDATE, RDATE, RECURRENCE-ID overrides (moved or cancelled instances), STATUS:CANCELLED, TRANSP:TRANSPARENT
(shown, not busy). Repeats follow the event's own wall clock, so a 09:00 shift stays at 09:00 through the clock change.
Not supported (honest limits): BYWEEKNO, BYYEARDAY, BYHOUR / BYMINUTE / BYSECOND, FREQ below DAILY, RRULEs inside VTIMEZONE other
than the yearly "Nth weekday of a month" kind. An unsupported rule keeps the first instance only and is counted in .skipped.
Test: python -X utf8 -m tests.test_calendar_sync
"""
from __future__ import annotations

import datetime as dt
import re

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except Exception:  # noqa: BLE001  (very old Python: rules below only)
    ZoneInfo = None
    ZoneInfoNotFoundError = Exception

UTC = dt.timezone.utc
MAX_INSTANCES = 3000          # per event and window: a broken RRULE never runs away
MAX_STEPS = 20000
WD = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}

# Outlook / Exchange publish Windows zone names; the common ones -> IANA (CLDR windowsZones, the "001" territory)
WINDOWS_TZ = {
    "eastern standard time": "America/New_York", "us eastern standard time": "America/Indiana/Indianapolis",
    "central standard time": "America/Chicago", "mountain standard time": "America/Denver", "us mountain standard time": "America/Phoenix",
    "pacific standard time": "America/Los_Angeles", "alaskan standard time": "America/Anchorage", "hawaiian standard time": "Pacific/Honolulu",
    "atlantic standard time": "America/Halifax", "newfoundland standard time": "America/St_Johns", "eastern standard time (mexico)": "America/Cancun",
    "central standard time (mexico)": "America/Mexico_City", "canada central standard time": "America/Regina", "sa pacific standard time": "America/Bogota",
    "gmt standard time": "Europe/London", "greenwich standard time": "Atlantic/Reykjavik", "w. europe standard time": "Europe/Berlin",
    "romance standard time": "Europe/Paris", "central europe standard time": "Europe/Budapest", "central european standard time": "Europe/Warsaw",
    "e. europe standard time": "Europe/Chisinau", "gtb standard time": "Europe/Bucharest", "fle standard time": "Europe/Kiev",
    "russian standard time": "Europe/Moscow", "india standard time": "Asia/Kolkata", "china standard time": "Asia/Shanghai",
    "tokyo standard time": "Asia/Tokyo", "aus eastern standard time": "Australia/Sydney", "utc": "UTC", "coordinated universal time": "UTC",
    "puerto rico standard time": "America/Puerto_Rico", "sa western standard time": "America/La_Paz", "e. south america standard time": "America/Sao_Paulo",
}
# when Python has no zone database (Windows without the tzdata package): the US zones by the 2007 rule, a few fixed ones
US_RULE = {"America/New_York": -5, "America/Detroit": -5, "America/Indiana/Indianapolis": -5, "America/Kentucky/Louisville": -5, "America/Toronto": -5,
           "America/Chicago": -6, "America/Winnipeg": -6, "America/Denver": -7, "America/Boise": -7, "America/Edmonton": -7,
           "America/Los_Angeles": -8, "America/Vancouver": -8, "America/Anchorage": -9, "America/Halifax": -4}
FIXED = {"UTC": 0, "Etc/UTC": 0, "GMT": 0, "Etc/GMT": 0, "America/Phoenix": -7, "Pacific/Honolulu": -10, "America/Puerto_Rico": -4,
         "America/Regina": -6, "Asia/Kolkata": 5.5, "Asia/Shanghai": 8, "Asia/Tokyo": 9}


# ------------------------------------------------------------------------------------------------ rule-based zones (no database needed)
def nth_weekday(year: int, month: int, weekday: int, n: int) -> dt.date:
    """the n-th (1..5, or -1 = last) weekday (0 = Monday) of a month"""
    if n > 0:
        d = dt.date(year, month, 1)
        d += dt.timedelta(days=(weekday - d.weekday()) % 7)
        d2 = d + dt.timedelta(weeks=n - 1)
        while d2.month != month:               # a 5th that does not exist: the last one
            d2 -= dt.timedelta(weeks=1)
        return d2
    last = dt.date(year + (month == 12), month % 12 + 1, 1) - dt.timedelta(days=1)
    d = last - dt.timedelta(days=(last.weekday() - weekday) % 7)
    return d - dt.timedelta(weeks=(-n) - 1)


class RuleTZ(dt.tzinfo):
    """A zone with one standard offset and (optionally) a yearly daylight rule: start / end = (month, weekday, n, minutes local)."""

    def __init__(self, name: str, std_min: int, dst_min: int | None = None, start=None, end=None):
        self.name, self.std, self.dst_off = name, dt.timedelta(minutes=std_min), dt.timedelta(minutes=dst_min if dst_min is not None else std_min)
        self.start, self.end = start, end

    def _range(self, year):
        if not (self.start and self.end) or self.dst_off == self.std:
            return None
        s = dt.datetime.combine(nth_weekday(year, self.start[0], self.start[1], self.start[2]), dt.time()) + dt.timedelta(minutes=self.start[3])
        e = dt.datetime.combine(nth_weekday(year, self.end[0], self.end[1], self.end[2]), dt.time()) + dt.timedelta(minutes=self.end[3])
        return s, e        # local wall times: s in standard time, e in daylight time

    def _is_dst(self, naive: dt.datetime, fold: int) -> bool:
        r = self._range(naive.year)
        if not r:
            return False
        s, e = r
        gap = self.dst_off - self.std
        if s < e:                                      # northern hemisphere
            if s <= naive < s + gap:                   # the hour that does not exist (PEP 495, as zoneinfo): fold 0 = the offset before
                return fold == 1
            if e - gap <= naive < e:                   # the repeated hour: fold 0 = the first (daylight)
                return fold == 0
            return s <= naive < e
        if e - gap <= naive < e:
            return fold == 0
        return not (e <= naive < s)                    # southern hemisphere: daylight over the new year

    def utcoffset(self, d):
        if d is None:
            return self.std
        return self.dst_off if self._is_dst(d.replace(tzinfo=None), getattr(d, "fold", 0)) else self.std

    def dst(self, d):
        if d is None:
            return dt.timedelta(0)
        return (self.dst_off - self.std) if self._is_dst(d.replace(tzinfo=None), getattr(d, "fold", 0)) else dt.timedelta(0)

    def tzname(self, d):
        return self.name

    def fromutc(self, d):
        u = d.replace(tzinfo=None)
        r = self._range(u.year)
        if r:
            s_utc, e_utc = r[0] - self.std, r[1] - self.dst_off
            in_dst = (s_utc <= u < e_utc) if s_utc < e_utc else not (e_utc <= u < s_utc)
            if in_dst:
                return (u + self.dst_off).replace(tzinfo=self)
            local = u + self.std
            gap = self.dst_off - self.std
            if s_utc < e_utc and e_utc <= u < e_utc + gap:          # the repeated hour, second time round
                return local.replace(tzinfo=self, fold=1)
            return local.replace(tzinfo=self)
        return (u + self.std).replace(tzinfo=self)


def us_rule(name: str, std_hours: float) -> RuleTZ:
    m = int(round(std_hours * 60))
    return RuleTZ(name, m, m + 60, (3, 6, 2, 120), (11, 6, 1, 120))     # 2nd Sunday of March 02:00 -> 1st Sunday of November 02:00


_ZONES: dict = {}


def zone(name: str | None, vtz: dict | None = None):
    """A tzinfo for a TZID (IANA, Windows or mozilla style), else None. vtz = the file's own VTIMEZONE rules."""
    if not name:
        return None
    raw = str(name).strip().strip('"')
    key = raw
    low = raw.lower()
    if low in WINDOWS_TZ:
        key = WINDOWS_TZ[low]
    elif "/" in raw and raw.startswith("/"):                # /mozilla.org/20050126_1/America/New_York, /softwarestudio.org/...
        parts = [p for p in raw.split("/") if p]
        key = "/".join(parts[-2:]) if len(parts) >= 2 else parts[-1]
    if key in _ZONES:
        return _ZONES[key]
    z = None
    if ZoneInfo is not None:
        try:
            z = ZoneInfo(key)
        except (ZoneInfoNotFoundError, ValueError, OSError, KeyError):
            z = None
    if z is None and vtz and raw in vtz:
        z = vtz[raw]
    if z is None and key in US_RULE:
        z = us_rule(key, US_RULE[key])
    if z is None and key in FIXED:
        z = RuleTZ(key, int(FIXED[key] * 60))
    if z is None:
        m = re.match(r"^(?:UTC|GMT)\s*([+-])\s*(\d{1,2})(?::?(\d\d))?$", raw, re.I)
        if m:
            mins = int(m.group(2)) * 60 + int(m.group(3) or 0)
            z = RuleTZ(raw, mins if m.group(1) == "+" else -mins)
    _ZONES[key] = z
    return z


def new_york():
    return zone("America/New_York")


# ------------------------------------------------------------------------------------------------ the text
def unfold(text: str) -> list:
    out = []
    for line in str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line[:1] in (" ", "\t") and out:
            out[-1] += line[1:]
        elif line.strip():
            out.append(line)
    return out


def split_prop(line: str):
    """'DTSTART;TZID="A:B";X=1:20261114T090000' -> ('DTSTART', {'TZID': 'A:B', 'X': '1'}, '20261114T090000')"""
    q, i, n = False, 0, len(line)
    while i < n:
        c = line[i]
        if c == '"':
            q = not q
        elif c == ":" and not q:
            break
        i += 1
    head, value = line[:i], line[i + 1:] if i < n else ""
    bits, cur, q = [], "", False
    for c in head:
        if c == '"':
            q = not q
            continue
        if c == ";" and not q:
            bits.append(cur)
            cur = ""
            continue
        cur += c
    bits.append(cur)
    params = {}
    for b in bits[1:]:
        if "=" in b:
            k, v = b.split("=", 1)
            params[k.strip().upper()] = v.strip()
    return bits[0].strip().upper(), params, value


def untext(v: str) -> str:
    out, i = [], 0
    while i < len(v):
        c = v[i]
        if c == "\\" and i + 1 < len(v):
            nx = v[i + 1]
            out.append("\n" if nx in "nN" else nx)
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


DUR_RX = re.compile(r"^([+-])?P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$")


def duration(v: str):
    m = DUR_RX.match(str(v or "").strip().upper())
    if not m:
        return None
    sign = -1 if m.group(1) == "-" else 1
    w, d, h, mi, s = (int(x or 0) for x in m.groups()[1:])
    return sign * dt.timedelta(weeks=w, days=d, hours=h, minutes=mi, seconds=s)


DT_RX = re.compile(r"^(\d{4})(\d{2})(\d{2})(?:T(\d{2})(\d{2})(\d{2})?(Z)?)?$")


def parse_dt(value: str, params: dict, default_tz, vtz=None):
    """-> (datetime aware | date, all_day) or (None, False). A floating time takes default_tz."""
    v = str(value or "").strip().upper()
    m = DT_RX.match(v)
    if not m:
        return None, False
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        if m.group(4) is None or (params.get("VALUE", "").upper() == "DATE"):
            return dt.date(y, mo, d), True
        t = dt.datetime(y, mo, d, int(m.group(4)), int(m.group(5)), int(m.group(6) or 0))
    except ValueError:
        return None, False
    if m.group(7):
        return t.replace(tzinfo=UTC), False
    tz = zone(params.get("TZID"), vtz) if params.get("TZID") else None
    return t.replace(tzinfo=tz or default_tz or UTC), False


def parse_rrule(v: str) -> dict:
    r = {}
    for part in str(v or "").split(";"):
        if "=" in part:
            k, val = part.split("=", 1)
            r[k.strip().upper()] = val.strip().upper()
    return r


# ------------------------------------------------------------------------------------------------ VTIMEZONE (only when Python does not know the zone)
def _vtz_rule(props: list):
    off = None
    rule = start = None
    for name, params, value in props:
        if name == "TZOFFSETTO":
            m = re.match(r"^([+-])(\d\d)(\d\d)", value.strip())
            if m:
                off = (int(m.group(2)) * 60 + int(m.group(3))) * (1 if m.group(1) == "+" else -1)
        elif name == "RRULE":
            rule = parse_rrule(value)
        elif name == "DTSTART":
            mm = DT_RX.match(value.strip())
            if mm and mm.group(4):
                start = int(mm.group(4)) * 60 + int(mm.group(5))
    spec = None
    if rule and rule.get("FREQ") == "YEARLY" and rule.get("BYMONTH") and rule.get("BYDAY"):
        bm = re.match(r"^([+-]?\d)?(MO|TU|WE|TH|FR|SA|SU)$", rule["BYDAY"])
        if bm:
            spec = (int(rule["BYMONTH"].split(",")[0]), WD[bm.group(2)], int(bm.group(1) or 1), start or 120)
    return off, spec


def build_vtz(blocks: list) -> dict:
    """blocks: [(tzid, {'STANDARD': [props], 'DAYLIGHT': [props]})] -> {tzid: RuleTZ}"""
    out = {}
    for tzid, parts in blocks:
        std_off, std_spec = _vtz_rule(parts.get("STANDARD") or [])
        dl_off, dl_spec = _vtz_rule(parts.get("DAYLIGHT") or [])
        if std_off is None and dl_off is None:
            continue
        if std_off is None:
            std_off = dl_off
        if dl_off is not None and dl_spec and std_spec:
            out[tzid] = RuleTZ(tzid, std_off, dl_off, dl_spec, std_spec)
        else:
            out[tzid] = RuleTZ(tzid, std_off)
    return out


# ------------------------------------------------------------------------------------------------ the calendar
class Calendar:
    def __init__(self):
        self.name, self.tz_name, self.events, self.overrides, self.skipped, self.bad = "", "", [], {}, 0, 0


def parse(text: str, default_tz=None) -> Calendar:
    """Read an .ics text. Never raises on bad input: a broken event is counted in .bad and left out."""
    cal = Calendar()
    lines = unfold(text)
    raw_events, vtz_blocks = [], []
    stack, cur, tz_cur, tz_part = [], None, None, None
    for line in lines:
        name, params, value = split_prop(line)
        if name == "BEGIN":
            comp = value.strip().upper()
            stack.append(comp)
            if comp == "VEVENT" and len(stack) >= 1 and "VTIMEZONE" not in stack:
                cur = []
            elif comp == "VTIMEZONE":
                tz_cur = ["", {}]
            elif comp in ("STANDARD", "DAYLIGHT") and tz_cur is not None:
                tz_part = comp
                tz_cur[1].setdefault(comp, [])
            continue
        if name == "END":
            comp = value.strip().upper()
            if stack and stack[-1] == comp:
                stack.pop()
            if comp == "VEVENT" and cur is not None:
                raw_events.append(cur)
                cur = None
            elif comp == "VTIMEZONE" and tz_cur is not None:
                vtz_blocks.append((tz_cur[0], tz_cur[1]))
                tz_cur = None
            elif comp in ("STANDARD", "DAYLIGHT"):
                tz_part = None
            continue
        inside = stack[-1] if stack else ""
        if inside == "VEVENT" and cur is not None:
            cur.append((name, params, value))
        elif inside in ("STANDARD", "DAYLIGHT") and tz_cur is not None and tz_part:
            tz_cur[1][tz_part].append((name, params, value))
        elif inside == "VTIMEZONE" and tz_cur is not None and name == "TZID":
            tz_cur[0] = value.strip()
        elif inside == "VCALENDAR":
            if name == "X-WR-CALNAME":
                cal.name = untext(value).strip()[:80]
            elif name == "X-WR-TIMEZONE":
                cal.tz_name = value.strip()
    vtz = build_vtz(vtz_blocks)
    dflt = zone(cal.tz_name, vtz) if cal.tz_name else None
    dflt = dflt or default_tz or new_york() or UTC
    for props in raw_events:
        try:
            ev = _event(props, dflt, vtz)
        except Exception:  # noqa: BLE001
            ev = None
        if ev is None:
            cal.bad += 1
            continue
        if ev["recurrence_id"] is not None:
            cal.overrides.setdefault(ev["uid"], []).append(ev)
        else:
            cal.events.append(ev)
    return cal


def _event(props: list, dflt, vtz) -> dict | None:
    e = {"uid": "", "title": "", "start": None, "end": None, "all_day": False, "dur": None, "rrule": None, "exdates": [], "rdates": [],
         "recurrence_id": None, "status": "CONFIRMED", "busy": True}
    for name, params, value in props:
        if name == "UID":
            e["uid"] = value.strip()[:200]
        elif name == "SUMMARY":
            e["title"] = untext(value).replace("\n", " ").strip()[:120]
        elif name == "DTSTART":
            e["start"], e["all_day"] = parse_dt(value, params, dflt, vtz)
        elif name == "DTEND":
            e["end"], _ = parse_dt(value, params, dflt, vtz)
        elif name == "DURATION":
            e["dur"] = duration(value)
        elif name == "RRULE":
            e["rrule"] = parse_rrule(value)
        elif name == "EXDATE":
            for v in value.split(","):
                x, _ = parse_dt(v, params, dflt, vtz)
                if x is not None:
                    e["exdates"].append(x)
        elif name == "RDATE" and params.get("VALUE", "").upper() != "PERIOD":
            for v in value.split(","):
                x, _ = parse_dt(v, params, dflt, vtz)
                if x is not None:
                    e["rdates"].append(x)
        elif name == "RECURRENCE-ID":
            e["recurrence_id"], _ = parse_dt(value, params, dflt, vtz)
        elif name == "STATUS":
            e["status"] = value.strip().upper()
        elif name == "TRANSP":
            e["busy"] = value.strip().upper() != "TRANSPARENT"
    if e["start"] is None:
        return None
    if e["end"] is None:
        if e["dur"] is not None:
            e["end"] = e["start"] + (dt.timedelta(days=max(1, e["dur"].days)) if e["all_day"] else e["dur"])
        elif e["all_day"]:
            e["end"] = e["start"] + dt.timedelta(days=1)
        else:
            e["end"] = e["start"]
    if e["all_day"] and isinstance(e["end"], dt.datetime):
        e["end"] = e["end"].date()
    if not e["all_day"] and not isinstance(e["end"], dt.datetime):        # a date end on a timed start: read as "no end"
        e["end"] = e["start"]
    if e["end"] < e["start"]:
        e["end"] = e["start"]
    if not e["uid"]:
        e["uid"] = f"nouid-{e['title']}-{e['start']}"
    return e


# ------------------------------------------------------------------------------------------------ RRULE
def _local(x):
    """the event's own wall clock: aware datetime -> naive in its zone; date stays a date"""
    return x.replace(tzinfo=None) if isinstance(x, dt.datetime) else x


def _attach(naive, tz):
    if isinstance(naive, dt.datetime):
        return naive.replace(tzinfo=tz)
    return naive


def _byday(spec: str):
    out = []
    for p in (spec or "").split(","):
        m = re.match(r"^([+-]?\d{1,2})?(MO|TU|WE|TH|FR|SA|SU)$", p.strip())
        if m:
            out.append((int(m.group(1)) if m.group(1) else 0, WD[m.group(2)]))
    return out


def _ints(spec: str):
    out = []
    for p in (spec or "").split(","):
        try:
            out.append(int(p))
        except ValueError:
            pass
    return out


def _month_days(y: int, mo: int, rr: dict, d0: dt.date) -> list:
    """the days of one month an RRULE picks (MONTHLY, or YEARLY within its BYMONTH)"""
    last = (dt.date(y + (mo == 12), mo % 12 + 1, 1) - dt.timedelta(days=1)).day
    days = []
    bd, bmd = _byday(rr.get("BYDAY")), _ints(rr.get("BYMONTHDAY"))
    if bd:
        for n, wd in bd:
            if n == 0:
                d = dt.date(y, mo, 1) + dt.timedelta(days=(wd - dt.date(y, mo, 1).weekday()) % 7)
                while d.month == mo:
                    days.append(d)
                    d += dt.timedelta(days=7)
            else:
                d = nth_weekday(y, mo, wd, n) if -5 <= n <= 5 else None
                if d and d.month == mo:
                    # a 5th that does not exist is not "the last": nth_weekday falls back, so check it really is the n-th
                    if n > 0 and (d.day - 1) // 7 + 1 != n:
                        continue
                    days.append(d)
        if bmd:
            keep = {(x if x > 0 else last + 1 + x) for x in bmd}
            days = [d for d in days if d.day in keep]
    elif bmd:
        for x in bmd:
            dd = x if x > 0 else last + 1 + x
            if 1 <= dd <= last:
                days.append(dt.date(y, mo, dd))
    else:
        if d0.day <= last:
            days.append(dt.date(y, mo, d0.day))
    days = sorted(set(days))
    sp = _ints(rr.get("BYSETPOS"))
    if sp and days:
        picked = []
        for p in sp:
            i = p - 1 if p > 0 else len(days) + p
            if 0 <= i < len(days):
                picked.append(days[i])
        days = sorted(set(picked))
    return days


SUPPORTED = {"FREQ", "INTERVAL", "COUNT", "UNTIL", "BYDAY", "BYMONTHDAY", "BYMONTH", "WKST", "BYSETPOS"}


def expand_starts(ev: dict, win_end_local, until_cap=None) -> tuple[list, bool]:
    """All instance starts (naive local wall clock or dates) from DTSTART up to win_end_local. (starts, supported)"""
    s0 = _local(ev["start"])
    rr = ev.get("rrule")
    if not rr:
        return [s0], True
    if set(rr) - SUPPORTED or rr.get("FREQ") not in ("DAILY", "WEEKLY", "MONTHLY", "YEARLY"):
        return [s0], False
    try:
        interval = max(1, int(rr.get("INTERVAL", "1")))
    except ValueError:
        interval = 1
    count = None
    if rr.get("COUNT"):
        try:
            count = max(0, int(rr["COUNT"]))
        except ValueError:
            count = None
    until = None
    if rr.get("UNTIL"):
        u, _ = parse_dt(rr["UNTIL"], {}, ev["start"].tzinfo if isinstance(ev["start"], dt.datetime) else None)
        if isinstance(u, dt.datetime) and isinstance(ev["start"], dt.datetime):
            until = u.astimezone(ev["start"].tzinfo).replace(tzinfo=None) if u.tzinfo else u
        elif isinstance(u, dt.datetime):
            until = u.date()
        elif isinstance(u, dt.date):
            until = dt.datetime.combine(u, dt.time(23, 59, 59)) if isinstance(s0, dt.datetime) else u
    end_cap = win_end_local
    is_dt = isinstance(s0, dt.datetime)
    d0 = s0.date() if is_dt else s0
    tod = s0.time() if is_dt else None
    bymonth = set(_ints(rr.get("BYMONTH")))
    bd = _byday(rr.get("BYDAY"))
    out, steps = [], 0
    freq = rr["FREQ"]

    def mk(d):
        return dt.datetime.combine(d, tod) if is_dt else d

    def done(x):
        return (until is not None and x > until) or x > end_cap or (count is not None and len(out) >= count) or len(out) >= MAX_INSTANCES

    def emit(cands):
        for d in cands:
            x = mk(d)
            if x < s0:
                continue
            if done(x):
                return False
            out.append(x)
        return True

    if freq == "DAILY":
        d = d0
        while steps < MAX_STEPS:
            steps += 1
            ok = (not bymonth or d.month in bymonth) and (not bd or d.weekday() in {w for _, w in bd}) and (not rr.get("BYMONTHDAY") or d.day in _ints(rr["BYMONTHDAY"]))
            if ok and not emit([d]):
                break
            d += dt.timedelta(days=interval)
            if mk(d) > end_cap or (until is not None and mk(d) > until):
                break
    elif freq == "WEEKLY":
        days = sorted({w for _, w in bd}) if bd else [d0.weekday()]
        wk = d0 - dt.timedelta(days=d0.weekday())        # WKST=MO
        while steps < MAX_STEPS:
            steps += 1
            cands = [wk + dt.timedelta(days=w) for w in days]
            cands = [c for c in cands if not bymonth or c.month in bymonth]
            if not emit(cands):
                break
            wk += dt.timedelta(weeks=interval)
            if mk(wk) > end_cap or (until is not None and mk(wk) > until):
                break
    elif freq == "MONTHLY":
        y, mo = d0.year, d0.month
        while steps < MAX_STEPS:
            steps += 1
            if not bymonth or mo in bymonth:
                if not emit(_month_days(y, mo, rr, d0)):
                    break
            mo += interval
            while mo > 12:
                mo -= 12
                y += 1
            if mk(dt.date(y, mo, 1)) > end_cap:
                break
    else:  # YEARLY
        y = d0.year
        months = sorted(bymonth) if bymonth else [d0.month]
        while steps < MAX_STEPS:
            steps += 1
            cands = []
            for mo in months:
                if bd or rr.get("BYMONTHDAY"):
                    cands += _month_days(y, mo, rr, d0)
                else:
                    try:
                        cands.append(dt.date(y, mo, d0.day))
                    except ValueError:
                        pass                               # 29 February in a year without one
            if not emit(sorted(cands)):
                break
            y += interval
            if mk(dt.date(y, 1, 1)) > end_cap:
                break
    return out, True


def _same(a, b) -> bool:
    if isinstance(a, dt.datetime) and isinstance(b, dt.datetime):
        if a.tzinfo and b.tzinfo:
            return a.astimezone(UTC) == b.astimezone(UTC)
        return a.replace(tzinfo=None) == b.replace(tzinfo=None)
    da = a.date() if isinstance(a, dt.datetime) else a
    db = b.date() if isinstance(b, dt.datetime) else b
    return da == db


def occurrences(cal: Calendar, start: dt.datetime, end: dt.datetime) -> list:
    """Every instance overlapping [start, end) (aware). All-day instances overlap when their dates touch the window's
    New York dates. Cancelled masters and cancelled overrides are left out. -> [dict] sorted by start."""
    ny = new_york() or UTC
    out = []
    d_from, d_to = start.astimezone(ny).date(), end.astimezone(ny).date()
    for ev in cal.events:
        if ev["status"] == "CANCELLED":
            continue
        tz = ev["start"].tzinfo if isinstance(ev["start"], dt.datetime) else None
        length = ev["end"] - ev["start"]
        if isinstance(ev["start"], dt.datetime):
            win_end_local = end.astimezone(tz).replace(tzinfo=None) + dt.timedelta(days=1)
        else:
            win_end_local = d_to + dt.timedelta(days=1)
        starts, ok = expand_starts(ev, win_end_local)
        if not ok:
            cal.skipped += 1
        for r in ev["rdates"]:
            starts.append(_local(r.astimezone(tz)) if isinstance(r, dt.datetime) and tz else _local(r))
        ovs = cal.overrides.get(ev["uid"], [])
        seen = set()
        for s in sorted(set(starts), key=lambda x: (x if isinstance(x, dt.datetime) else dt.datetime.combine(x, dt.time()))):
            inst_start = _attach(s, tz)
            if any(_same(inst_start, x) for x in ev["exdates"]):
                continue
            ov = next((o for o in ovs if _same(inst_start, o["recurrence_id"])), None)
            if ov is not None:
                seen.add(id(ov))
                if ov["status"] == "CANCELLED":
                    continue
                _add(out, ov, ov["start"], ov["end"], d_from, d_to, start, end)
                continue
            if isinstance(inst_start, dt.datetime):
                # the wall-clock end: same length in local time, so an 8-hour shift stays 8 hours on the clock-change night too
                inst_end = _attach(s + length, tz) if isinstance(s, dt.datetime) else inst_start + length
            else:
                inst_end = inst_start + length
            _add(out, ev, inst_start, inst_end, d_from, d_to, start, end)
        for o in ovs:                                  # an override of an instance the rule no longer makes (moved in from elsewhere)
            if id(o) not in seen and o["status"] != "CANCELLED" and not ev.get("rrule"):
                _add(out, o, o["start"], o["end"], d_from, d_to, start, end)
    out.sort(key=lambda o: (o["sort"], o["title"]))
    return out


def _add(out, ev, s, e, d_from, d_to, w_start, w_end):
    if isinstance(s, dt.datetime):
        if not (s < w_end and (e > w_start or (e == s and s >= w_start))):
            return
        srt = s.astimezone(UTC)
        out.append({"uid": ev["uid"], "title": ev["title"], "start": s, "end": e, "all_day": False, "busy": ev["busy"], "status": ev["status"], "sort": srt})
    else:
        last = e - dt.timedelta(days=1) if e > s else s
        if last < d_from or s > d_to:
            return
        srt = dt.datetime.combine(s, dt.time(), tzinfo=UTC)
        out.append({"uid": ev["uid"], "title": ev["title"], "start": s, "end": e, "all_day": True, "busy": ev["busy"], "status": ev["status"], "sort": srt})
