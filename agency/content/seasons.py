"""The US calendar the content machine writes around: holidays and observances in a month, the season, and a rough climate
zone from the client's state (so a Phoenix plumber is not told about snow).

Every date here is computed (nth weekday, Easter by the Gregorian computus) or a fixed date, except Hanukkah, which follows the
Hebrew calendar: its first-candle evenings are a short table checked against Hebcal (2026-11-14). Outside the table it is skipped,
never guessed.
"""
from __future__ import annotations

import calendar
import datetime as dt
import re

# first candle, in the evening (Hebcal: hebcal.com/holidays/chanukah-2026, -2027, -2028)
HANUKKAH_FIRST_EVENING = {2025: (12, 14), 2026: (12, 4), 2027: (12, 24), 2028: (12, 12)}

SEASON_OF_MONTH = {12: "winter", 1: "winter", 2: "winter", 3: "spring", 4: "spring", 5: "spring",
                   6: "summer", 7: "summer", 8: "summer", 9: "fall", 10: "fall", 11: "fall"}

# rough winter climate by state: cold = real winters with snow and freezes, mild = cold snaps but rare snow, warm = no real winter,
# rainy = the wet, grey Pacific Northwest. Unknown state -> mild (no snow claims).
ZONE_OF_STATE = {
    "warm": {"FL", "HI", "AZ", "PR"},
    "mild": {"TX", "LA", "MS", "AL", "GA", "SC", "NC", "TN", "AR", "OK", "CA", "NV", "NM", "VA", "DC", "KY"},
    "rainy": {"WA", "OR"},
}
STATE_NAMES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA", "colorado": "CO", "connecticut": "CT",
    "delaware": "DE", "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA",
    "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI",
    "minnesota": "MN", "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV", "new hampshire": "NH",
    "new jersey": "NJ", "new mexico": "NM", "new york": "NY", "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC", "south dakota": "SD", "tennessee": "TN",
    "texas": "TX", "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV", "wisconsin": "WI",
    "wyoming": "WY", "district of columbia": "DC", "puerto rico": "PR",
}
ALL_STATES = set(STATE_NAMES.values())


def parse_city(city: str) -> tuple[str, str]:
    """'Austin, TX' -> ('Austin', 'TX'); 'Tampa, Florida' -> ('Tampa', 'FL'); 'Denver' -> ('Denver', '')"""
    text = (city or "").strip()
    if not text:
        return "", ""
    parts = [p.strip() for p in text.split(",") if p.strip()]
    name = parts[0]
    state = ""
    for p in parts[1:]:
        p2 = re.sub(r"\d{5}(-\d{4})?", "", p).strip()                  # drop a ZIP code
        if p2.upper() in ALL_STATES:
            state = p2.upper()
            break
        if p2.lower() in STATE_NAMES:
            state = STATE_NAMES[p2.lower()]
            break
    return name, state


def zone_of(city: str) -> str:
    _, st = parse_city(city)
    for zone, states in ZONE_OF_STATE.items():
        if st in states:
            return zone
    return "cold" if st else "mild"


def season_of(month: int) -> str:
    return SEASON_OF_MONTH[month]


def nth_weekday(year: int, month: int, weekday: int, n: int) -> dt.date:
    """weekday 0 = Monday; n = 1..5, or -1 for the last one in the month"""
    if n > 0:
        first = dt.date(year, month, 1)
        shift = (weekday - first.weekday()) % 7
        return first + dt.timedelta(days=shift + 7 * (n - 1))
    last = dt.date(year, month, calendar.monthrange(year, month)[1])
    return last - dt.timedelta(days=(last.weekday() - weekday) % 7)


def easter(year: int) -> dt.date:
    """Gregorian Easter Sunday (the anonymous Gregorian algorithm)"""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    month, day = divmod(h + l_ - 7 * m + 114, 31)
    return dt.date(year, month, day + 1)


# key, name, icon, motif, weight (0-10 how much a local business should post about it), respect (no selling on this day),
# trades (None = every trade, else only these), lead (post this many days BEFORE the date, e.g. a booking push)
def _h(key, name, date, icon, motif, weight, respect=False, trades=None, lead=0, kind="holiday"):
    return {"key": key, "name": name, "date": date, "icon": icon, "motif": motif, "weight": weight, "respect": respect,
            "trades": trades, "lead": lead, "kind": kind}


def holidays(year: int, month: int) -> list[dict]:
    """the holidays and observances of one month, each with the date of the day itself (post_date may be earlier: see `lead`)"""
    D = lambda m, d: dt.date(year, m, d)  # noqa: E731
    out = []
    if month == 1:
        out += [_h("new_year", "New Year's Day", D(1, 1), "spark", "confetti", 9),
                _h("mlk", "Martin Luther King Jr. Day", nth_weekday(year, 1, 0, 3), "star", "stars", 4, respect=True)]
    elif month == 2:
        out += [_h("valentines", "Valentine's Day", D(2, 14), "heart", "hearts", 8, lead=2),
                _h("presidents", "Presidents' Day", nth_weekday(year, 2, 0, 3), "star", "stars", 2),
                _h("dental_month", "Children's Dental Health Month", D(2, 3), "tooth", "bubbles", 8, trades={"dentist"}, kind="observance")]
    elif month == 3:
        out += [_h("world_plumbing", "World Plumbing Day", D(3, 11), "droplet", "drops", 7, trades={"plumber"}, kind="observance"),
                _h("st_patricks", "St. Patrick's Day", D(3, 17), "clover", "clovers", 6),
                _h("dst_start", "Clocks spring forward", nth_weekday(year, 3, 6, 2), "clock", "dots", 4),
                _h("spring", "First day of spring", D(3, 20), "flower", "flowers", 6, kind="season")]
    elif month == 4:
        out += [_h("earth_day", "Earth Day", D(4, 22), "leaf", "leaves", 4),
                _h("lawn_month", "National Lawn Care Month", D(4, 2), "leaf", "leaves", 8, trades={"landscaper"}, kind="observance"),
                _h("car_care_spring", "National Car Care Month", D(4, 3), "car", "chevrons", 8, trades={"auto"}, kind="observance")]
    elif month == 5:
        out += [_h("fitness_month", "National Fitness & Sports Month", D(5, 1), "dumbbell", "bars", 8, trades={"gym"}, kind="observance"),
                _h("mothers_day", "Mother's Day", nth_weekday(year, 5, 6, 2), "heart", "flowers", 9, lead=3),
                _h("memorial_day", "Memorial Day", nth_weekday(year, 5, 0, -1), "star", "stars", 6, respect=True)]
    elif month == 6:
        out += [_h("fathers_day", "Father's Day", nth_weekday(year, 6, 6, 3), "star", "dots", 8, lead=3),
                _h("summer", "First day of summer", D(6, 21), "sun", "suns", 6, kind="season"),
                _h("juneteenth", "Juneteenth", D(6, 19), "star", "stars", 3, respect=True)]
    elif month == 7:
        out += [_h("july4", "Independence Day", D(7, 4), "star", "stars", 9, lead=1)]
    elif month == 8:
        out += [_h("back_to_school", "Back to school", D(8, 10), "calendar", "dots", 8,
                   trades={"barber", "salon", "dentist", "auto", "gym", "restaurant"}, kind="season", lead=4)]
    elif month == 9:
        out += [_h("labor_day", "Labor Day", nth_weekday(year, 9, 0, 1), "star", "stars", 6),
                _h("fall", "First day of fall", D(9, 22), "leaf", "leaves", 7, kind="season")]
    elif month == 10:
        out += [_h("hygiene_month", "National Dental Hygiene Month", D(10, 1), "tooth", "bubbles", 8, trades={"dentist"}, kind="observance"),
                _h("car_care_fall", "Fall Car Care Month", D(10, 2), "car", "chevrons", 8, trades={"auto"}, kind="observance"),
                _h("halloween", "Halloween", D(10, 31), "pumpkin", "leaves", 8, lead=1)]
    elif month == 11:
        tg = nth_weekday(year, 11, 3, 4)
        out += [_h("dst_end", "Clocks fall back", nth_weekday(year, 11, 6, 1), "clock", "dots", 4),
                _h("veterans_day", "Veterans Day", D(11, 11), "star", "stars", 6, respect=True),
                _h("thanksgiving", "Thanksgiving", tg, "leaf", "leaves", 9, lead=1),
                _h("small_business_saturday", "Small Business Saturday", tg + dt.timedelta(days=2), "gift", "confetti", 8, lead=1)]
    elif month == 12:
        out += [_h("winter", "First day of winter", D(12, 21), "snowflake", "snow", 5, kind="season"),
                _h("christmas_eve", "Christmas Eve", D(12, 24), "gift", "snow", 7, lead=4),
                _h("christmas", "Christmas", D(12, 25), "gift", "snow", 10),
                _h("kwanzaa", "Kwanzaa", D(12, 26), "candles7", "stars", 3),
                _h("nye", "New Year's Eve", D(12, 31), "spark", "confetti", 9)]
    if easter(year).month == month:                                    # March or April
        out.append(_h("easter", "Easter", easter(year), "flower", "flowers", 6))
    hk = HANUKKAH_FIRST_EVENING.get(year)
    if hk and hk[0] == month:
        out.append(_h("hanukkah", "Hanukkah", D(*hk), "menorah", "stars", 5))
    for h in out:
        h["post_date"] = h["date"] - dt.timedelta(days=h["lead"])
        if h["post_date"].month != month:                              # never post outside the month
            h["post_date"] = h["date"]
    out.sort(key=lambda h: h["date"])
    return out


def month_name(month: int) -> str:
    return calendar.month_name[month]


def days_in(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def parse_month(text: str, today: dt.date | None = None) -> tuple[int, int]:
    """'2026-12' -> (2026, 12); 'next' / 'this' / 'last' relative to today"""
    today = today or dt.date.today()
    t = (text or "next").strip().lower()
    if t in ("next", "this", "last", "current", "previous", "prev"):
        y, m = today.year, today.month
        if t == "next":
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        elif t in ("last", "previous", "prev"):
            y, m = (y - 1, 12) if m == 1 else (y, m - 1)
        return y, m
    mm = re.fullmatch(r"(\d{4})-(\d{1,2})", t)
    if not mm or not 1 <= int(mm.group(2)) <= 12:
        raise ValueError(f"month must look like 2026-12 (or next / this / last), got {text!r}")
    return int(mm.group(1)), int(mm.group(2))


def shift_month(year: int, month: int, by: int) -> tuple[int, int]:
    n = year * 12 + (month - 1) + by
    return n // 12, n % 12 + 1
