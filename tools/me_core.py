"""ME CORE (team ME1, 2026-11-14, docs/ME_HUB.md): the small shared helpers of the Me hub's PC tools (me_cards, me_health, me_home,
me_life, me_hub). Stdlib only, no network, no clock but the one passed in.

Where things live (both PRIVATE):
  %USERPROFILE%\\.olympus\\me\\   what you type once (cards.json, car.json, dates.json, freedom.json, devices.json, health_goals.json) and
                                 the PC's own history (health_history.json from the Health export, home_state.json); OLYMPUS_HOME overrides
  data/me/                       what the phone reads through the PC's own link (me.json, health.json, home.json) + state.json (which
                                 reminders went out); LE_ME_DIR overrides; gitignored, never copied to a site folder
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DEFAULT = os.path.join(ROOT, "data", "me")
CTRL_RX = re.compile(r"[\x00-\x1f\x7f<>]")
LONG_DIGITS_RX = re.compile(r"\d{9,}")          # an account / card number: masked in anything the phone gets
CARDLIKE_RX = re.compile(r"\d{4,}")             # in a nickname: a card number or its last 4 (after spaces, dashes and dots are taken out)


def olympus_dir(env=None) -> str:
    env = os.environ if env is None else env
    return env.get("OLYMPUS_HOME") or os.path.join(env.get("USERPROFILE") or os.path.expanduser("~"), ".olympus")


def me_dir(env=None) -> str:
    """the private inputs: %USERPROFILE%\\.olympus\\me"""
    return os.path.join(olympus_dir(env), "me")


def out_dir(env=None) -> str:
    """the phone files: data/me (LE_ME_DIR overrides; engine/live_site.py serves only this folder at /site/me/)"""
    env = os.environ if env is None else env
    return env.get("LE_ME_DIR") or OUT_DEFAULT


def read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return default


def write_json(path, obj, compact=False) -> str:
    """atomic write, owner-only on POSIX (the files are private)"""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        if compact:
            json.dump(obj, fh, separators=(",", ":"), ensure_ascii=False, default=str)
        else:
            json.dump(obj, fh, indent=1, ensure_ascii=False, default=str)
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


def obj(x) -> dict:
    return x if isinstance(x, dict) else {}


def arr(x) -> list:
    return x if isinstance(x, list) else []


def num(x):
    if isinstance(x, bool) or x is None:
        return None
    try:
        v = float(str(x).replace(",", "").replace("$", "").strip()) if isinstance(x, str) else float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and v not in (float("inf"), float("-inf")) else None


def clean(s, n: int = 80) -> str:
    return re.sub(r"\s+", " ", CTRL_RX.sub(" ", str(s if s is not None else ""))).strip()[:n]


def scrub(s: str) -> str:
    """mask a long run of digits (an account or card number) in a phone string"""
    return LONG_DIGITS_RX.sub("•••", s)


def scrub_doc(x):
    """every string of a phone file, scrubbed (amounts are numbers, so they are untouched)"""
    if isinstance(x, str):
        return scrub(x)
    if isinstance(x, list):
        return [scrub_doc(v) for v in x]
    if isinstance(x, dict):
        return {k: scrub_doc(v) for k, v in x.items()}
    return x


def cardlike(s) -> bool:
    """True when a text holds a card number or a last-4: 4+ digits in a row once spaces, dashes, dots and stars are taken out"""
    return bool(CARDLIKE_RX.search(re.sub(r"[\s\-.*·•_/]", "", str(s or ""))))


# ------------------------------------------------------------------------------------------------ the clock (New York)
def ny_tz():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("America/New_York")
    except Exception:  # noqa: BLE001
        return dt.timezone(dt.timedelta(hours=-5))


def ny_dt(now_s: float) -> dt.datetime:
    return dt.datetime.fromtimestamp(float(now_s), tz=ny_tz())


def ny_day(now_s: float, plus: int = 0) -> str:
    return (ny_dt(now_s).date() + dt.timedelta(days=plus)).isoformat()


def parse_day(s):
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except (TypeError, ValueError):
        return None


def add_days(day: str, n: int) -> str:
    return (dt.date.fromisoformat(day) + dt.timedelta(days=n)).isoformat()


def days_between(a: str, b: str) -> int:
    """b - a in days"""
    return (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days


def day_epoch(day: str, hour: int = 12) -> int:
    """a day at hour:00 New York, as epoch seconds (the age of a day's data)"""
    d = dt.date.fromisoformat(day)
    return int(dt.datetime(d.year, d.month, d.day, hour, tzinfo=ny_tz()).timestamp())


def month_end(day: str) -> str:
    d = dt.date.fromisoformat(day)
    nxt = dt.date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return (nxt - dt.timedelta(days=1)).isoformat()


def on_day_of_month(year: int, month: int, dom: int) -> dt.date:
    """the dom-th of that month, clamped to its last day (a due day 31 is Feb 28 / 29)"""
    nxt = dt.date(year + (month == 12), month % 12 + 1, 1)
    last = (nxt - dt.timedelta(days=1)).day
    return dt.date(year, month, min(max(1, int(dom)), last))


def next_on_day(today: str, dom: int) -> str:
    """the next date (today included) that falls on day dom of its month"""
    t = dt.date.fromisoformat(today)
    y, m = t.year, t.month
    for _ in range(3):
        d = on_day_of_month(y, m, dom)
        if d >= t:
            return d.isoformat()
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return on_day_of_month(y, m, dom).isoformat()


def short_day(day: str) -> str:
    """'Fri Nov 28'"""
    d = parse_day(day)
    return d.strftime("%a %b ") + str(d.day) if d else str(day or "")


def in_days(n: int) -> str:
    return "today" if n == 0 else "tomorrow" if n == 1 else "yesterday" if n == -1 else (f"in {n} days" if n > 0 else f"{-n} days ago")


# ------------------------------------------------------------------------------------------------ words
def money(x, sign: bool = False, cents: bool = False) -> str:
    v = num(x)
    if v is None:
        return "-"
    if cents or (abs(v) < 10 and round(v) != v):
        a = f"{abs(v):,.2f}"
    else:
        a = f"{abs(round(v)):,.0f}"
    s = "-" if v < 0 and float(a.replace(",", "")) != 0 else ("+" if sign and v > 0 else "")
    return f"{s}${a}"


def plural(n, word: str, many: str | None = None) -> str:
    n = int(n)
    return f"{n:,} {word if n == 1 else (many or word + 's')}"


def pct(x, nd: int = 0) -> str:
    v = num(x)
    return "-" if v is None else f"{v:.{nd}f}%"


def worst(levels) -> str:
    order = {"bad": 3, "warn": 2, "ok": 1}
    best = ""
    for lv in levels:
        if order.get(lv or "", 0) > order.get(best, 0):
            best = lv
    return best
