"""OpenStreetMap opening_hours -> a week the demo site can show (and an 'Open now' badge can use).

The common forms only: 'Mo-Fr 08:00-17:00; Sa 09:00-12:00; Su off', '24/7', 'Mo-Su 11:00-14:00,17:00-22:00', '10:00-18:00'.
Days no rule mentions are closed (that is the OSM meaning). Anything else (months, weeks, sunrise) keeps the raw text and
says ok=False, so the site writes 'Call to confirm' instead of guessing.
"""
from __future__ import annotations

import re

DAYS = ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")
NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
LONG = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
_DAY = r"(?:Mo|Tu|We|Th|Fr|Sa|Su)"
_TIME = re.compile(r"^(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})$")


def _days(sel: str):
    out = []
    for part in sel.split(","):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(rf"({_DAY})(?:-({_DAY}))?", part)
        if not m:
            return None
        a = DAYS.index(m.group(1))
        b = DAYS.index(m.group(2)) if m.group(2) else a
        i = a
        while True:
            if i not in out:
                out.append(i)
            if i == b:
                break
            i = (i + 1) % 7
    return out


def _times(sel: str):
    out = []
    for part in sel.split(","):
        m = _TIME.match(part.strip())
        if not m:
            return None
        h1, m1, h2, m2 = (int(x) for x in m.groups())
        if h1 > 24 or h2 > 48 or m1 > 59 or m2 > 59:
            return None
        s, e = h1 * 60 + m1, h2 * 60 + m2
        if e <= s:
            e += 24 * 60                     # past midnight: '18:00-02:00'
        out.append([s, e])
    return out


def parse(raw: str) -> dict:
    """-> {ok, raw, week: [[[start_min, end_min], ...] x 7 (Mon..Sun)]}. Unmentioned days = closed."""
    raw = (raw or "").strip()
    week = [[] for _ in range(7)]
    res = {"ok": False, "raw": raw, "week": week}
    if not raw:
        return res
    if raw in ("24/7", "Mo-Su 00:00-24:00", "00:00-24:00"):
        for i in range(7):
            week[i] = [[0, 1440]]
        res["ok"] = True
        return res
    text = re.sub(r'"[^"]*"', "", raw)                                   # comments
    text = re.sub(rf",\s*(?=(?:{_DAY}|PH)\b)", "; ", text)               # 'Mo-Fr 7-18, Sa 8-17' written with a comma
    ok, any_rule = True, False
    for rule in re.split(r"\s*(?:;|\|\|)\s*", text):
        rule = rule.strip()
        if not rule:
            continue
        if re.match(r"^(PH|SH)\b", rule):
            continue                          # public / school holidays: not on a weekly table
        m = re.match(rf"^((?:{_DAY}(?:\s*-\s*{_DAY})?\s*,?\s*)+)(.*)$", rule)
        if m:
            days = _days(re.sub(r"\s+", "", m.group(1)).rstrip(","))
            rest = re.sub(r"^,?\s*PH\s*", "", m.group(2).strip())
        else:
            days, rest = list(range(7)), rule
        if days is None:
            ok = False
            continue
        if rest.lower() in ("off", "closed"):
            for d in days:
                week[d] = []
            any_rule = True
            continue
        times = _times(rest)
        if times is None:
            ok = False
            continue
        for d in days:
            week[d] = [list(t) for t in times]
        any_rule = True
    res["ok"] = ok and any_rule
    return res


def clock(minutes: int) -> str:
    """540 -> '9 AM', 1020 -> '5 PM', 570 -> '9:30 AM', 720 -> 'noon', 0 / 1440 -> 'midnight', 1500 -> '1 AM'."""
    if minutes in (0, 1440):
        return "midnight"
    minutes %= 1440
    if minutes == 720:
        return "noon"
    h, m = divmod(minutes, 60)
    suffix = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return f"{h12}:{m:02d} {suffix}" if m else f"{h12} {suffix}"


def span(t) -> str:
    s, e = t
    if s == 0 and e >= 1440:
        return "Open 24 hours"
    return f"{clock(s)} - {clock(e)}"


def rows(parsed: dict):
    """Group equal neighbouring days: [('Mon - Fri', '8 AM - 5 PM'), ('Sat', '9 AM - noon'), ('Sun', 'Closed')]."""
    if not parsed.get("ok"):
        return []
    out, week, i = [], parsed["week"], 0
    while i < 7:
        j = i
        while j + 1 < 7 and week[j + 1] == week[i]:
            j += 1
        label = NAMES[i] if i == j else f"{NAMES[i]} - {NAMES[j]}"
        out.append((label, ", ".join(span(t) for t in week[i]) if week[i] else "Closed"))
        i = j + 1
    return out


def summary(parsed: dict) -> str:
    """One short line for a pitch or a card: 'Mon - Fri 8 AM - 5 PM; Sat 9 AM - noon'."""
    return "; ".join(f"{a} {b}" for a, b in rows(parsed) if b != "Closed")


def schema_spec(parsed: dict):
    """schema.org openingHoursSpecification for the JSON-LD block."""
    out = []
    if not parsed.get("ok"):
        return out
    for d, ts in enumerate(parsed["week"]):
        for s, e in ts:
            e = 1439 if e >= 1440 else e
            out.append({"@type": "OpeningHoursSpecification", "dayOfWeek": LONG[d], "opens": f"{s // 60:02d}:{s % 60:02d}", "closes": f"{e // 60:02d}:{e % 60:02d}"})
    return out
