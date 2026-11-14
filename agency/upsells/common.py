"""Shared helpers for the agency add-ons: the client file, colours, hours, escaping, output folders.

The client file is the agency's shared client record (B1/CRM fields) plus two optional sections for the add-ons:
    {"id", "name", "trade", "city", "phone", "email", "site_url", "demo_url", "status", "package", "setup_usd", "monthly_usd", "notes",
     "chat": {...},      Front-desk chat settings (make_chat.py)
     "review": {...}}    Review booster settings (make_review.py)
Real client files live in data/agency/ (kept out of git); the fake demo clients are in agency/upsells/fixtures/.
"""
from __future__ import annotations

import html
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SHARED_FIELDS = ("id", "name", "trade", "city", "phone", "email", "site_url", "demo_url", "status", "package", "setup_usd", "monthly_usd", "notes")
DAYS = ("sun", "mon", "tue", "wed", "thu", "fri", "sat")          # index = JavaScript getDay()
DAY_NAMES = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")


class ClientError(ValueError):
    """a problem in the client file the owner has to fix (said in plain words)"""


def load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_client(path: str) -> dict:
    try:
        c = load_json(path)
    except FileNotFoundError:
        raise ClientError(f"no client file at {path}")
    except json.JSONDecodeError as e:
        raise ClientError(f"{path} is not valid JSON (line {e.lineno}: {e.msg})")
    if not isinstance(c, dict):
        raise ClientError(f"{path} must hold one client (a JSON object)")
    missing = [k for k in ("id", "name", "phone") if not str(c.get(k) or "").strip()]
    if missing:
        raise ClientError(f"the client file needs {', '.join(missing)}")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,48}", c["id"]):
        raise ClientError(f"id {c['id']!r}: use lowercase letters, digits and dashes only (like 'joes-barbers')")
    todo = unfilled(c)
    if todo:
        raise ClientError("fill these in first (they still say FILL): " + ", ".join(todo[:10]) + (f" and {len(todo) - 10} more" if len(todo) > 10 else ""))
    return c


def unfilled(value, path: str = "") -> list:
    """every field that still holds a FILL placeholder (a starter file's sample facts must be confirmed, never shipped)"""
    if isinstance(value, dict):
        return [p for k, v in value.items() for p in unfilled(v, f"{path}.{k}" if path else str(k))]
    if isinstance(value, list):
        return [p for i, v in enumerate(value) for p in unfilled(v, f"{path}[{i}]")]
    return [path] if isinstance(value, str) and "FILL" in value else []


def default_out(client: dict) -> str:
    """real client output goes next to the real client data (data/agency/, not in git)"""
    return os.path.join(ROOT, "data", "agency", "upsells", client["id"])


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def digits(phone: str) -> str:
    return re.sub(r"\D", "", str(phone or ""))


def tel(phone: str, country: str = "1") -> str:
    """'(813) 555-0142' -> '+18135550142' (US numbers by default; a number that starts with + keeps its own code; 'ext. 12' is dropped)"""
    p = re.split(r"\s*(?:ext\.?|extension|x)\s*\d+\s*$", str(phone or "").strip(), flags=re.I)[0]
    d = digits(p)
    if not d:
        return ""
    if p.startswith("+"):
        return "+" + d
    if len(d) == 10:
        return "+" + country + d
    if len(d) == 11 and d.startswith(country):
        return "+" + d
    return "+" + d


# ---------------------------------------------------------------------------------------------------------------- colours
def rgb(hexcol: str) -> tuple:
    h = str(hexcol or "").strip().lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", h):
        raise ClientError(f"colour {hexcol!r} must look like #0f766e")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def hexof(c: tuple) -> str:
    return "#" + "".join(f"{max(0, min(255, round(v))):02x}" for v in c)


def luminance(hexcol: str) -> float:
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb(hexcol)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def mix(a: str, b: str, t: float) -> str:
    ra, rb = rgb(a), rgb(b)
    return hexof(tuple(x + (y - x) * t for x, y in zip(ra, rb)))


def ink_on(bg: str) -> str:
    """white or near-black text, whichever reads better on the brand colour"""
    return "#ffffff" if contrast("#ffffff", bg) >= contrast("#111827", bg) else "#111827"


def readable(color: str, bg: str, ratio: float = 4.5) -> str:
    """the brand colour, darkened (on a light page) or lightened (on a dark one) just enough for text contrast >= ratio"""
    toward = "#000000" if luminance(bg) > 0.4 else "#ffffff"
    for i in range(0, 101):
        c = mix(color, toward, i / 100)
        if contrast(c, bg) >= ratio:
            return c
    return toward


def palette(brand: str) -> dict:
    """everything the widget and the review page need from one brand colour, all WCAG AA (4.5:1) for text"""
    brand = hexof(rgb(brand))
    fill, ink = brand, ink_on(brand)
    if contrast(ink, fill) < 4.5:                      # a mid-tone brand: darken the fill just enough for white text
        fill, ink = readable(brand, "#ffffff", 4.5), "#ffffff"
    return {"brand": brand, "fill": fill, "ink": ink, "accent": readable(brand, "#ffffff"), "accent_dark": readable(brand, "#14181f"),
            "soft": mix(brand, "#ffffff", 0.88), "soft_dark": mix(brand, "#14181f", 0.78)}


# ---------------------------------------------------------------------------------------------------------------- hours
_T = re.compile(r"^\s*(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm|a|p|a\.m\.|p\.m\.)?\s*$", re.I)


def _clock(t: str):
    m = _T.match(t)
    if not m:
        raise ClientError(f"time {t!r}: write it like 9:00, 9am, 18:30 or 6:30pm")
    h, mi, ap = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or "").lower()[:1]
    if mi > 59 or h > 24 or (ap and (h > 12 or h == 0)):
        raise ClientError(f"time {t!r} is not a real time")
    return h, mi, ap


def _mins(h: int, mi: int, ap: str) -> int:
    if ap == "p" and h != 12:
        h += 12
    if ap == "a" and h == 12:
        h = 0
    return h * 60 + mi


def parse_day(spec) -> list:
    """'9:00-19:00' | '9am-7pm' | '9-7pm' | '9-5' (= 9 am-5 pm) | '11-14, 17-22' | '18:00-02:00' (past midnight) | '24h' | 'closed'
    -> [[start_min, end_min], ...]; an end past midnight is stored as end + 1440 (the widget counts it on the next morning)"""
    s = str(spec or "").strip().lower()
    if s in ("", "closed", "off", "-", "no", "none"):
        return []
    if s in ("24h", "24/7", "24 hours", "open 24 hours", "all day"):
        return [[0, 1440]]
    out = []
    for part in re.split(r"\s*[,;&]\s*|\s+and\s+", s):
        if not part:
            continue
        bits = re.split(r"\s*(?:-|–|—|\bto\b)\s*", part)
        if len(bits) != 2:
            raise ClientError(f"hours {spec!r}: write each range like 9:00-17:00")
        (h1, m1, a1), (h2, m2, a2) = _clock(bits[0]), _clock(bits[1])
        if a2 and not a1:                              # '9-7pm' = 9 am-7 pm, '1-5pm' = 1 pm-5 pm
            a1 = a2 if _mins(h1, m1, a2) < _mins(h2, m2, a2) else ("a" if a2 == "p" else "p")
        if a1 and not a2:                              # '9am-5' = 9 am-5 pm
            a2 = a1 if _mins(h2, m2, a1) > _mins(h1, m1, a1) else ("p" if a1 == "a" else "a")
        a, b = _mins(h1, m1, a1), _mins(h2, m2, a2)
        if not a1 and not a2 and h1 <= 12 and h2 < 12 and b <= a:
            b += 720                                   # '9-5', '12-8', '10-10': shop hours, the end is in the afternoon
        if b <= a:
            b += 1440                                  # '18-2': past midnight
        if b - a > 1440:
            raise ClientError(f"hours {spec!r}: a range can't be longer than a day")
        out.append([a, b])
    out.sort()
    return out


def parse_hours(hours: dict) -> list:
    """{'mon': '9-17', ..., 'weekdays': ..., 'weekend': ...} -> 7 lists indexed Sunday=0 (JavaScript getDay())"""
    if not isinstance(hours, dict) or not hours:
        raise ClientError("chat.hours is missing: give each day, like {\"mon\": \"9:00-17:00\", ..., \"sun\": \"closed\"}")
    week = [None] * 7
    groups = {"weekdays": (1, 2, 3, 4, 5), "weekend": (0, 6), "everyday": tuple(range(7)), "daily": tuple(range(7))}
    for key in ("everyday", "daily", "weekdays", "weekend"):
        if key in hours:
            for d in groups[key]:
                week[d] = parse_day(hours[key])
    for k, v in hours.items():
        k3 = k.strip().lower()[:3]
        if k.strip().lower() in groups:
            continue
        if k3 not in DAYS:
            raise ClientError(f"hours: unknown day {k!r} (use mon, tue, wed, thu, fri, sat, sun, weekdays, weekend)")
        week[DAYS.index(k3)] = parse_day(v)
    missing = [DAY_NAMES[i] for i, d in enumerate(week) if d is None]
    if missing:
        raise ClientError(f"hours: say what {', '.join(missing)} {'is' if len(missing) == 1 else 'are'} (a time range or \"closed\")")
    return week


def fmt_time(m: int) -> str:
    m %= 1440
    h, mi = divmod(m, 60)
    ap = "am" if h < 12 else "pm"
    h12 = h % 12 or 12
    return f"{h12}{':%02d' % mi if mi else ''} {ap}"


def week_text(week: list) -> list:
    """['Mon-Fri 9 am-7 pm', 'Sat 8 am-4 pm', 'Sun closed'] (Monday first, like a shop door)"""
    order = [1, 2, 3, 4, 5, 6, 0]
    short = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")

    def txt(ranges):
        if not ranges:
            return "closed"
        if ranges == [[0, 1440]]:
            return "open 24 hours"
        return ", ".join(f"{fmt_time(a)}–{fmt_time(b)}" for a, b in ranges)

    lines, i = [], 0
    while i < 7:
        j = i
        while j + 1 < 7 and week[order[j + 1]] == week[order[i]]:
            j += 1
        name = short[order[i]] if i == j else f"{short[order[i]]}–{short[order[j]]}"
        lines.append(f"{name} {txt(week[order[i]])}")
        i = j + 1
    return lines


def write(path: str, text: str) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return path


def insert_block(page: str, marker: str, block: str, before: str = "</body>") -> str:
    """put block in the page between <!-- marker:start --> and <!-- marker:end -->, replacing an earlier copy (so reruns don't stack)"""
    start, end = f"<!-- {marker}:start -->", f"<!-- {marker}:end -->"
    new = f"{start}\n{block.strip()}\n{end}"
    if start in page and end in page:
        a, b = page.index(start), page.index(end) + len(end)
        return page[:a] + new + page[b:]
    idx = page.lower().rfind(before.lower())
    if idx < 0:
        return page + "\n" + new + "\n"
    return page[:idx] + new + "\n" + page[idx:]
