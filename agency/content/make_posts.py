"""Social post machine: a month of ready-to-post content for one local business, made from code ($0 per client).

    python agency/content/make_posts.py client.json --month 2026-12
    python agency/content/make_posts.py data/agency/clients.json --id fade-co --month next --posts 20
    python agency/content/make_posts.py data/agency/clients.json --all --month next          every paying client
options: --posts N (12-20; default from the package: basic 12, pro 20, else 16)  --out DIR  --no-images  --no-emoji
         --colors "#14213D,#D4A24C" (the client's own brand colours)  --reviews FILE (real review lines: text | name)  --seed N

client.json is the shared agency client record {"id","name","trade","city","phone","email","site_url","demo_url","status","package",
"setup_usd","monthly_usd","notes"} (one record, a list, or {"clients": [...]}); optional extras it reads when present:
"brand_colors", "reviews" [{"text","name"}], "review_url".

Out (default data/agency/content/<id>/<YYYY-MM>/, gitignored): posts/NN_<date>_square.png (1080x1080) + _story.png (1080x1920),
posts.csv (the schedule sheet: Excel / Google Sheets / copy into Meta Business Suite), captions.txt (phone copy-paste),
contact_sheet.html (owner's working page with Copy buttons), contact_sheet.png (preview for the client), client_message.txt
(the approval text with every yes/no question), posts.json, HOW_TO_POST.txt.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import random
import re
import sys
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from agency.content import designs as D  # noqa: E402
from agency.content import packs as P  # noqa: E402
from agency.content import seasons as S  # noqa: E402

PAYING = {"active", "client", "won", "paying", "live", "signed", "customer"}
CSV_COLUMNS = ["post", "date", "time", "weekday", "platforms", "kind", "layout", "caption", "hashtags", "caption_with_hashtags",
               "square_image", "story_image", "alt_text", "check_with_client", "photo_idea"]
KIND_LABEL = {"tip": "Tip", "service": "Service spotlight", "offer": "Offer", "season": "Season", "bts": "Behind the scenes",
              "team": "Meet the team", "review": "Reviews", "faq": "FAQ", "local": "Local love", "engage": "Conversation",
              "booking": "Book ahead", "checklist": "Checklist", "holiday": "Holiday"}
BASE_MIX = [("tip", 3.0), ("service", 2.0), ("offer", 1.6), ("season", 1.2), ("bts", 1.2), ("review", 1.0), ("faq", 1.0),
            ("local", 0.9), ("booking", 0.9), ("engage", 0.8), ("checklist", 0.8), ("team", 0.5)]
TRADE_EMOJI = {"barber": "💈", "salon": "✨", "restaurant": "🍽️", "plumber": "🔧", "landscaper": "🌿", "auto": "🚗", "gym": "💪", "dentist": "🦷"}
KIND_EMOJI = {"tip": "💡", "offer": "🎁", "bts": "👀", "team": "👋", "review": "⭐", "faq": "❓", "local": "📍", "engage": "💬",
              "booking": "📅", "checklist": "✅"}
SEASON_EMOJI = {"winter": "❄️", "spring": "🌷", "summer": "☀️", "fall": "🍂"}
HOLIDAY_EMOJI = {"christmas": "🎄", "christmas_eve": "🎄", "nye": "🥂", "new_year": "🎉", "hanukkah": "🕎", "kwanzaa": "🕯️", "valentines": "❤️",
                 "st_patricks": "☘️", "easter": "🌷", "july4": "🎆", "halloween": "🎃", "thanksgiving": "🍂", "mothers_day": "💐",
                 "fathers_day": "👔", "winter": "❄️", "spring": "🌷", "summer": "☀️", "fall": "🍂", "back_to_school": "🎒",
                 "small_business_saturday": "🛍️", "earth_day": "🌎", "labor_day": "🛠️", "dst_start": "⏰", "dst_end": "⏰"}
HOLIDAY_TAG = {"christmas": "#MerryChristmas", "christmas_eve": "#ChristmasEve", "nye": "#NewYearsEve", "new_year": "#HappyNewYear",
               "hanukkah": "#HappyHanukkah", "kwanzaa": "#HappyKwanzaa", "winter": "#FirstDayOfWinter", "mlk": "#MLKDay",
               "valentines": "#ValentinesDay", "presidents": "#PresidentsDay", "st_patricks": "#StPatricksDay", "easter": "#HappyEaster",
               "earth_day": "#EarthDay", "mothers_day": "#MothersDay", "memorial_day": "#MemorialDay", "fathers_day": "#FathersDay",
               "juneteenth": "#Juneteenth", "july4": "#FourthOfJuly", "labor_day": "#LaborDay", "halloween": "#Halloween",
               "veterans_day": "#VeteransDay", "thanksgiving": "#Thanksgiving", "small_business_saturday": "#SmallBusinessSaturday",
               "dst_start": "#DaylightSaving", "dst_end": "#DaylightSaving", "spring": "#FirstDayOfSpring", "summer": "#HelloSummer",
               "fall": "#HelloFall", "back_to_school": "#BackToSchool", "dental_month": "#ChildrensDentalHealthMonth",
               "hygiene_month": "#DentalHygieneMonth", "world_plumbing": "#WorldPlumbingDay", "lawn_month": "#LawnCareMonth",
               "car_care_spring": "#CarCareMonth", "car_care_fall": "#CarCareMonth", "fitness_month": "#FitnessMonth"}
KIND_TAG = {"tip": ["#ProTip", "#TipTuesday", "#GoodToKnow"], "offer": ["#ShopLocal", "#SupportLocal"], "bts": ["#BehindTheScenes"],
            "team": ["#MeetTheTeam"], "review": ["#CustomerLove", "#ThankYou"], "faq": ["#AskUs"], "local": ["#ShopLocal", "#SupportLocal"],
            "engage": ["#TellUs"], "booking": ["#BookNow"], "checklist": ["#Checklist"], "service": ["#SmallBusiness"], "season": []}
SEASON_TAG = {"winter": "#WinterReady", "spring": "#SpringTime", "summer": "#SummerReady", "fall": "#FallVibes"}
GENERAL_TAGS = ["#SmallBusiness", "#ShopLocal", "#SupportLocal", "#LocalBusiness"]


# ---------------------------------------------------------------------------------------------------------------- utilities
def crc(*parts) -> int:
    return zlib.crc32("|".join(str(p) for p in parts).encode("utf-8"))


def strip_stars(t: str) -> str:
    return (t or "").replace("*", "")


ABBR = re.compile(r"\b(Co|Inc|Ltd|Dr|Mr|Mrs|Ms|Jr|Sr|St|Mt|vs|No)\.")    # 'Fade & Co. Barbershop', 'Dr. King' are not sentence ends
HOLD = "․"


def _hold(t: str) -> str:
    return ABBR.sub(lambda m: m.group(1) + HOLD, t or "")


def first_sentence(t: str, limit: int = 118) -> str:
    t = _hold((t or "").strip())
    m = re.match(r"(.+?[.!?])(\s|$)", t)
    s = m.group(1) if m else t
    if len(s) > limit:
        cut = s[:limit].rsplit(" ", 1)[0].rstrip(",;:")
        s = cut + "..."
    return s.replace(HOLD, ".")


def sub_line(t: str, limit: int = 118) -> str:
    """the image's small line: the first sentence, or the first two when the first is very short ('Yes.', 'Busy season?')"""
    s = first_sentence(t, limit)
    if len(s) < 45:
        two = lead_text(t, limit)
        if len(two) <= limit:
            return two
    return s


def lead_text(t: str, limit: int = 170) -> str:
    """as many whole sentences as fit in `limit` characters (at least the first, shortened if it must be)"""
    parts = re.findall(r"[^.!?]+[.!?]+(?:\s|$)|[^.!?]+$", _hold((t or "").strip()))
    out = ""
    for s in parts:
        s = s.strip()
        if not out:
            out = s
        elif len(out) + 1 + len(s) <= limit:
            out += " " + s
        else:
            break
    out = out.replace(HOLD, ".")
    return out if len(out) <= limit else first_sentence(out, limit)


def tag_word(text: str) -> str:
    return "".join(w[:1].upper() + w[1:] for w in re.findall(r"[A-Za-z0-9]+", text or ""))


def display_site(url: str) -> str:
    u = (url or "").strip()
    u = re.sub(r"^https?://", "", u, flags=re.I)
    u = re.sub(r"^www\.", "", u, flags=re.I)
    return u.rstrip("/")


def fmt_time(hhmm: str) -> str:
    h, m = (int(x) for x in hhmm.split(":"))
    return f"{(h % 12) or 12}:{m:02d} {'am' if h < 12 else 'pm'}"


class SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def fill(t: str, ctx: dict) -> str:
    return (t or "").format_map(SafeDict(ctx))


# ------------------------------------------------------------------------------------------------------------- the client
def load_clients(path: str) -> list[dict]:
    with open(path, encoding="utf-8-sig") as fh:
        data = json.load(fh)
    if isinstance(data, dict) and isinstance(data.get("clients"), list):
        return data["clients"]
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    raise ValueError(f"{path}: expected a client record, a list of them, or {{\"clients\": [...]}}")


def choose_clients(clients: list[dict], cid: str | None, all_: bool) -> list[dict]:
    if cid:
        hit = [c for c in clients if str(c.get("id", "")).lower() == cid.lower()]
        if not hit:
            raise SystemExit(f"no client with id {cid!r} (ids: {', '.join(str(c.get('id')) for c in clients)})")
        return hit
    if len(clients) == 1:
        return clients
    if all_:
        return [c for c in clients if str(c.get("status", "")).strip().lower() in PAYING and has_social(c)]
    raise SystemExit("this file has several clients: add --id <id> (or --all for every paying client with social posts)\n  ids: "
                     + ", ".join(str(c.get("id")) for c in clients))


def social_words(client: dict) -> str:
    """the social add-on as written on the client record: in `package` ('growth + social pro'), an `addons` list, or `social`"""
    parts = [str(client.get("package") or "")]
    addons = client.get("addons") or []
    parts += [str(a) for a in (addons if isinstance(addons, list) else [addons])]
    if client.get("social"):
        parts.append("social " + (client["social"] if isinstance(client["social"], str) else ""))
    return " ".join(p for p in parts if "social" in p.lower()).lower()


def has_social(client: dict) -> bool:
    return bool(social_words(client))


def default_posts(client: dict) -> int:
    """from the SOCIAL add-on only (the website plans are also called starter / growth / pro, so 'pro + social basic' is 12):
    social basic 12, social pro 20, social alone 16"""
    tiers = re.findall(r"social[\s:_\-]*([a-z0-9$]+)?", social_words(client))
    tier = " ".join(t for t in tiers if t)
    if any(w in tier for w in ("pro", "plus", "premium", "299")):
        return 20
    if any(w in tier for w in ("basic", "starter", "149", "lite")):
        return 12
    return 16


def read_reviews(path: str | None, client: dict) -> list[dict]:
    out = []
    for r in client.get("reviews") or []:
        if isinstance(r, dict) and r.get("text"):
            out.append({"text": str(r["text"]).strip(), "who": str(r.get("name") or r.get("who") or "").strip()})
    if path:
        with open(path, encoding="utf-8-sig") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                text, _, who = line.partition("|")
                out.append({"text": text.strip().strip('"'), "who": who.strip()})
    for r in out:
        r["who"] = short_name(r["who"]) if r["who"] else "a happy customer"
    return out


def short_name(name: str) -> str:
    """'Maria Lopez' -> 'Maria L.' (first name + initial: friendly, and private)"""
    parts = name.split()
    if len(parts) >= 2 and parts[0][:1].isalpha() and parts[-1][:1].isalpha():
        return f"{parts[0]} {parts[-1][0].upper()}."
    return name


def brand_for(client: dict, trade: str, colors: str | None = None) -> dict:
    pack = P.PACKS[trade]
    raw = colors or client.get("brand_colors")
    if isinstance(raw, list):
        raw = ",".join(raw)
    pal = None
    if raw:
        cs = [c.strip() for c in str(raw).split(",") if re.fullmatch(r"#?[0-9A-Fa-f]{6}", c.strip())]
        if cs:
            cs = [c if c.startswith("#") else "#" + c for c in cs]
            pal = D.brand_palette(cs[0], cs[1] if len(cs) > 1 else None)
    if pal is None:
        pal = pack["palettes"][crc(client.get("id") or client.get("name")) % len(pack["palettes"])]
    city, state = S.parse_city(client.get("city", ""))
    site = display_site(client.get("site_url") or client.get("demo_url") or "")
    return {"name": (client.get("name") or "Your business").strip(), "city": city, "state": state, "site": site,
            "phone": (client.get("phone") or "").strip(), "web": site or (client.get("phone") or "").strip(),
            "initials": D.initials(client.get("name", "")), "fonts": pack["fonts"], "motif": pack["motif"], "palette": pal,
            "vars": D.palette_vars(pal), "trade": trade}


# --------------------------------------------------------------------------------------------------------------- the plan
def _split_item(item) -> dict:
    """a pack tuple -> fields: (headline, body, [check | tag | months | zones] ...) in any order after the first two.
    A set of numbers = the months it runs in; a set of words = the climate zones it fits (cold, mild, warm, rainy)."""
    out = {"headline": item[0], "body": item[1], "check": "", "tag": "", "months": None, "zones": None, "extra": None}
    for x in item[2:]:
        if isinstance(x, (set, frozenset)) and x and all(isinstance(v, str) for v in x):
            out["zones"] = x
        elif isinstance(x, (set, frozenset)):
            out["months"] = x
        elif isinstance(x, list):
            out["extra"] = x
        elif isinstance(x, str) and x in ("p", "h", "ph"):
            out["tag"] = x
        elif isinstance(x, str):
            out["check"] = x
    return out


def _pool(items, month: int, trade_flags: str, zone: str | None = None) -> list[dict]:
    res = []
    for it in items or []:
        f = _split_item(it)
        if f["months"] is not None and month not in f["months"]:
            continue
        if f["zones"] is not None and zone and zone not in f["zones"]:
            continue
        if f["tag"] and trade_flags and not set(f["tag"]) & set(trade_flags):
            continue
        res.append(f)
    return res


SEASON_START = {"winter": 12, "spring": 3, "summer": 6, "fall": 9}


def _season_months(season: str) -> list[int]:
    return {"winter": [12, 1, 2], "spring": [3, 4, 5], "summer": [6, 7, 8], "fall": [9, 10, 11]}[season]


def _candidates(pack: dict, year: int, month: int, flags: str, reviews, zone: str | None = None) -> dict:
    """every kind's items for one month, freshest first (pure: the same month always gives the same lists)"""
    season = S.season_of(month)
    pos = (month - SEASON_START[season]) % 12                          # 0, 1 or 2 inside the season
    rot = year * 12 + month
    pool = lambda items: _pool(items, month, flags, zone)  # noqa: E731
    seasonal = [f for j, it in enumerate(pack["tips"].get(season) or []) if j % 3 == pos for f in pool([it])]
    hooks = pool(pack["season"].get(season))
    first = lambda f: min(f["months"] & set(_season_months(season)), key=lambda mm: (mm - SEASON_START[season]) % 12)  # noqa: E731
    tagged = [f for f in hooks if f["months"] and month == first(f)]
    plain = [f for f in hooks if not f["months"]]
    offers = pool(pack["offers"])
    # a timed offer runs in its months; one with a long window (a battery test Oct-Feb) runs every other month
    timed = [f for f in offers if f["months"] and (len(f["months"]) <= 2 or (rot + crc(f["headline"])) % 2 == 0)]
    checklists = [{"headline": c[0], "body": "", "items": c[1], "check": "", "months": (c[2] if len(c) > 2 else None)}
                  for c in pack["checklists"] if (len(c) < 3 or c[2] is None or month in c[2])
                  and (len(c) < 4 or not zone or zone in c[3])]

    def half(raw, parity=None):
        """odd and even months draw from the two halves of a pool (by position in the pack, so a month filter never shifts
        them): two neighbouring months can never share an item; inside its half each month turns one step"""
        par = rot % 2 if parity is None else parity
        mine = [f for j, it in enumerate(raw or []) if j % 2 == par for f in pool([it])]
        return _rotate(mine, rot // 2)

    tips_mine, tips_other = half(pack["tips"]["any"]), half(pack["tips"]["any"], 1 - rot % 2)
    svc_mine, svc_other = half(pack["services"]), half(pack["services"], 1 - rot % 2)
    return {
        "tip": seasonal + tips_mine + tips_other, "tip_fresh": len(seasonal) + len(tips_mine),
        "service": svc_mine + svc_other, "service_fresh": min(3, len(svc_mine)),
        "offer_timed": _rotate(timed, rot), "offer_ever": half([o for o in pack["offers"] if _split_item(o)["months"] is None]),
        "season": tagged or ([plain[pos]] if pos < len(plain) else []),
        "bts": half(pack["bts"]), "team": half(P.TEAM), "review": half(P.REVIEW_ASK), "faq": half(pack["faq"]),
        "local": half(P.LOCAL), "engage": half(list(pack["engage"]) + P.ENGAGE), "booking": half(list(pack["booking"]) + P.BOOKING),
        "checklist": _rotate(checklists, rot // 3) if rot % 3 == 0 else [],
    }


def _rotate(lst: list, k: int) -> list:
    return lst[k % len(lst):] + lst[:k % len(lst)] if lst else lst


def allocate(r: int, caps: dict) -> dict:
    """the content mix of the non-holiday posts: one each of tip / service / offer / review first, then always the kind furthest
    below its BASE_MIX share that still has fresh items. The sum can be below r when the fresh pools run dry (the caller tops up)."""
    mix = [(k, w) for k, w in BASE_MIX if caps.get(k, 0) > 0]
    got = {k: 0 for k, _ in mix}
    for k in ("tip", "service", "offer", "review"):
        if k in got and sum(got.values()) < r:
            got[k] = 1
    tot = sum(w for _, w in mix) or 1
    while sum(got.values()) < r:
        room = [(k, w) for k, w in mix if got[k] < caps[k]]
        if not room:
            break
        k = max(room, key=lambda kw: kw[1] * r / tot - got[kw[0]])[0]
        got[k] += 1
    return {k: v for k, v in got.items() if v > 0}


def spread_dates(year: int, month: int, n: int, pinned: list[dt.date], allowed_wd: set) -> list[dt.date]:
    """n posting days: the pinned holiday days plus evenly spread days on the trade's best weekdays (one post a day)"""
    last = S.days_in(year, month)
    targets = [1 + (i + 0.5) * last / n for i in range(n)]
    for p in sorted(set(pinned)):
        if not targets:
            break
        j = min(range(len(targets)), key=lambda i: abs(targets[i] - p.day))
        targets.pop(j)
    used = set(pinned)
    free = [dt.date(year, month, d) for d in range(1, last + 1) if dt.date(year, month, d).weekday() in allowed_wd]
    spare = [dt.date(year, month, d) for d in range(1, last + 1)]
    out = list(sorted(set(pinned)))
    for t in sorted(targets):
        cands = [d for d in free if d not in used] or [d for d in spare if d not in used]
        if not cands:
            break
        d = min(cands, key=lambda d: (abs(d.day - t), d.day))
        used.add(d)
        out.append(d)
    return sorted(out)


def plan_month(client: dict, year: int, month: int, n_posts: int | None = None, seed: int | None = None, reviews=None,
               emoji: bool = True, colors: str | None = None) -> dict:
    trade = P.trade_of(client.get("trade", ""))
    pack = P.PACKS[trade]
    n = n_posts or default_posts(client)
    if not 12 <= n <= 20:
        raise ValueError("posts per month must be 12-20")
    brand = brand_for(client, trade, colors)
    seed = crc(client.get("id") or brand["name"], year, month) if seed is None else seed
    season, zone = S.season_of(month), S.zone_of(client.get("city", ""))
    flags = ""
    if trade == "plumber":
        tr = client.get("trade", "")
        flags = ("h" if P.is_hvac(tr) else "") + ("p" if P.is_plumbing(tr) or not P.is_hvac(tr) else "")
    rot = year * 12 + month
    ny, nm = S.shift_month(year, month, 1)
    wlist = P.WEATHER.get((season, zone)) or ["the weather"]
    ctx = {"name": brand["name"], "city": brand["city"] or "town", "pro": pack["pro"], "pros": pack["pros"], "visit": pack["visit"], "season": season,
           "month": S.month_name(month), "next_month": S.month_name(nm), "year": year, "next_year": year + 1, "last_year": year - 1,
           "site": brand["site"] or "our website", "phone": brand["phone"] or "us", "zone": zone, "trade_text": client.get("trade", "")}

    # holidays: the trade's relevant ones, the heaviest first, about 3 in 10 posts
    hol = [h for h in S.holidays(year, month) if h["trades"] is None or trade in h["trades"]]
    k = min(len(hol), max(2, round(n * 0.28)))
    chosen = sorted(sorted(hol, key=lambda h: (-h["weight"], h["date"]))[:k], key=lambda h: h["post_date"])
    taken = set()
    for h in chosen:                                                   # two holidays on one day: move the lighter one a day earlier
        while h["post_date"] in taken and h["post_date"].day > 1:
            h["post_date"] -= dt.timedelta(days=1)
        taken.add(h["post_date"])

    # the content pools, fresh every month (_candidates): a season's own items are spread over its three months, tips and
    # services take turns by halves, and the small pools give odd and even months different halves (no repeats month to month)
    cur = _candidates(pack, year, month, flags, reviews, zone)
    nxt = _candidates(pack, ny, nm, flags, reviews, zone)

    def fresh(kind, k=1):
        return cur[kind][:k]

    pools = {
        "tip": cur["tip"][:cur["tip_fresh"]],
        "service": cur["service"][:cur["service_fresh"]],
        "offer": fresh("offer_timed") + fresh("offer_ever"),
        "season": fresh("season"),
        "review": [{"headline": "", "body": "", "real": r} for r in _rotate(list(reviews or []), rot)][:2] + fresh("review"),
        "checklist": fresh("checklist"),
    }
    for kind in ("bts", "team", "faq", "local", "engage", "booking"):
        pools[kind] = fresh(kind)
    caps = {k: len(v) for k, v in pools.items()}
    caps["review"] = min(caps["review"], 2 if reviews else 1)
    mix = allocate(n - len(chosen), caps)
    short = n - len(chosen) - sum(mix.values())
    for kind in ("local", "booking", "review"):                        # a big month with few holidays: a second local / booking / thank-you
        if short <= 0 or (kind == "review" and reviews):
            continue
        two = fresh(kind, 2)
        if len(two) == 2 and mix.get(kind, 0) == 1:
            pools[kind] = two
            mix[kind] = 2
            short -= 1
    if short > 0:                                                      # still short: borrow, next month's items last
        soon = {f["headline"] for f in nxt["tip"][:nxt["tip_fresh"]] + nxt["service"][:nxt["service_fresh"]]}
        rest = [f for f in cur["tip"][cur["tip_fresh"]:] + cur["service"][cur["service_fresh"]:] if f not in pools["tip"] + pools["service"]]
        reserve = [f for f in rest if f["headline"] not in soon] + [f for f in rest if f["headline"] in soon]
        while len(reserve) < short:
            reserve += cur["tip"] or cur["service"]
        for f in reserve[:short]:
            kind = "service" if f in cur["service"] else "tip"
            pools[kind].append(f)
            mix[kind] = mix.get(kind, 0) + 1

    dates = spread_dates(year, month, n, [h["post_date"] for h in chosen], set(pack["times"]))
    hol_by_date = {h["post_date"]: h for h in chosen}
    free_dates = [d for d in dates if d not in hol_by_date]

    # order the non-holiday kinds across the month: early season/booking/offers, reviews later, no kind twice in a row
    rnd = random.Random(seed)
    bag = [kk for kk, c in mix.items() for _ in range(c)]
    pref = {"season": lambda f: 1.2 - f, "booking": lambda f: 1.0 - f, "offer": lambda f: 0.85 - 0.5 * f, "review": lambda f: 0.3 + 0.6 * f}
    seq, prev = [], None
    for i, _ in enumerate(free_dates):
        f = i / max(1, len(free_dates) - 1)
        best = max(sorted(set(bag)), key=lambda kk: pref.get(kk, lambda _: 0.55)(f) + rnd.uniform(-0.18, 0.18) - (2 if kk == prev else 0)
                   + 0.06 * bag.count(kk))
        bag.remove(best)
        seq.append(best)
        prev = best
    kinds_by_date = dict(zip(free_dates, seq))

    used = {kk: 0 for kk in pools}
    posts, prev_layout, tipno = [], None, 0
    for i, d in enumerate(dates):
        h = hol_by_date.get(d)
        kind = "holiday" if h else kinds_by_date[d]
        if kind == "checklist" and not pools["checklist"]:
            kind = "tip"
        it = None
        if kind != "holiday":
            pool = pools[kind]
            if used[kind] < len(pool):
                it = pool[used[kind]]
                used[kind] += 1
            else:
                kind = "tip"
                it = pools["tip"][used["tip"] % len(pools["tip"])]
                used["tip"] += 1
        ctx["weather"] = wlist[(i + rot) % len(wlist)]
        post = compose(kind, it, h, d, pack, trade, brand, ctx, seed + i, emoji, i, prev_layout)
        if kind in ("tip",):
            tipno += 1
            post["number"] = tipno
        prev_layout = post["layout"]
        post["n"] = i + 1
        hh = pack["times"].get(d.weekday(), "10:00")
        if kind == "holiday" and h and h["post_date"] == h["date"]:
            hh = "09:00" if h["key"] not in ("nye",) else "12:00"
        post["time"] = hh
        post["date"] = d.isoformat()
        post["weekday"] = d.strftime("%A")
        posts.append(post)

    _dedupe(posts)
    for p in posts:
        p["hashtags"] = hashtags(p, pack, brand, season, seed)
        p["alt"] = alt_text(p, brand)
        stem = f"{p['n']:02d}_{p['date']}"
        p["square"], p["story"] = f"posts/{stem}_square.png", f"posts/{stem}_story.png"
    checks = []
    for p in posts:
        if p["check"] and p["check"] not in checks:
            checks.append(p["check"])
    return {"v": 1, "client": {k: client.get(k) for k in ("id", "name", "trade", "city", "phone", "email", "site_url", "package")},
            "trade": trade, "trade_label": pack["label"], "month": f"{year}-{month:02d}", "label": f"{S.month_name(month)} {year}",
            "season": season, "zone": zone, "seed": seed, "palette": brand["palette"], "fonts": brand["fonts"], "times_note": pack["times_note"],
            "posts": posts, "checks": checks, "holidays": [h["name"] for h in sorted(chosen, key=lambda h: h["date"])], "brand": {k: brand[k] for k in ("name", "city", "site", "phone", "initials")},
            "generated": dt.datetime.now().isoformat(timespec="seconds")}


def _cta(pack: dict, ctx: dict, brand: dict, i: int) -> str:
    opts = []
    counter = re.search(r"caf|coffee|bakery|bagel|donut|deli", str(ctx.get("trade_text", "")).lower())
    for c in pack["cta"]:
        if "{site}" in c and not brand["site"]:
            continue
        if "{phone}" in c and not brand["phone"]:
            continue
        if counter and "Reserve" in c:                                 # a cafe or bakery: no table reservations
            continue
        opts.append(c)
    if not opts:
        return "Send us a message to book."
    return fill(opts[i % len(opts)], ctx)


def compose(kind, it, h, d, pack, trade, brand, ctx, seed, emoji, i, prev_layout) -> dict:
    """one post: image words (label, headline, sub, layout, icon) + the caption"""
    e = lambda s: (s + " ") if emoji and s else ""  # noqa: E731
    cta = _cta(pack, ctx, brand, i)
    city = brand["city"] or "town"
    icons = pack["icons"]
    p = {"kind": kind, "check": "", "photo_idea": "", "icon": icons[i % len(icons)], "motif": None, "seed": seed, "items": None,
         "quote": None, "tile": None, "holiday": None}
    if kind == "holiday":
        key = h["key"]
        words = (pack.get("holiday", {}).get(key) or P.HOLIDAY.get(key) or [(h["name"], "")])
        if key in P.OBSERVANCE_TRADES and not pack.get("holiday", {}).get(key):
            words = [(h["name"], "")]
        pick = words[seed % len(words)]
        hl, body = pick[0], pick[1]
        ctx2 = dict(ctx, year_of_date=h["date"].year)
        hl, body = fill(hl, ctx2), fill(body, ctx2)
        p.update(headline=hl, holiday=h["name"], holiday_key=key, motif=h["motif"], icon=h["icon"] if h["icon"] in D.ICONS else icons[0],
                 check=pick[2] if len(pick) > 2 else "")             # holiday words that assume a service ask the client too
        tile = {"mon": h["date"].strftime("%b").upper(), "day": str(h["date"].day), "dow": h["date"].strftime("%A"), "event": h["name"]}
        if h["respect"]:
            p.update(layout="minimal", label=h["name"], sub=sub_line(body, 160))
            cap = f"{hl.replace('*', '')}\n\n{body}"
        elif h["post_date"] != h["date"] or h["kind"] == "observance":
            p.update(layout="date", label=("Coming up" if h["post_date"] != h["date"] else "This month"), sub=sub_line(body), tile=tile)
            cap = f"{e(HOLIDAY_EMOJI.get(key, '📅'))}{strip_stars(hl)}\n\n{body}\n\n{cta}"
        else:
            p.update(layout="holiday", label=_holiday_label(h), sub=sub_line(body))
            cap = f"{e(HOLIDAY_EMOJI.get(key, '✨'))}{strip_stars(hl)}\n\n{body}"
        p["caption"] = cap
        return p

    hl, body = fill(it["headline"], ctx), fill(it["body"], ctx)
    p["check"] = it.get("check", "")
    p["sub_long"] = lead_text(body, 170)
    p["go"] = _cta(pack, ctx, brand, 0).rstrip(".")
    if kind == "tip":
        p.update(layout="tip", label=["Quick tip", "Pro tip", "Good to know"][seed % 3], headline=hl, sub=sub_line(body))
        opener = [f"{e('💡')}{strip_stars(hl)}", f"{e('💡')}Quick tip from your {city} {pack['pro']}: {strip_stars(hl)[0].lower() + strip_stars(hl)[1:]}"][seed % 2]
        p["caption"] = f"{opener}\n\n{body}\n\nSave this for later. {cta}"
    elif kind == "service":
        lay = "split" if prev_layout != "split" else "bold"
        p.update(layout=lay, label="Service spotlight", headline=hl, sub=sub_line(body))
        p["caption"] = f"{e(TRADE_EMOJI.get(trade, '⭐'))}Spotlight: {strip_stars(hl)}\n\n{body}\n\n{cta}"
    elif kind == "offer":
        gift = "gift" in (hl + body).lower()
        p.update(layout="offer", label="Gift idea" if gift else "This month", headline=hl, sub=sub_line(body), icon="gift" if gift else icons[0],
                 cta_short=(brand["phone"] or brand["site"] or ""))
        lead = {11: "Holiday shopping starts here. ", 12: "Still shopping? "}.get(d.month, "") if gift else ""
        p["caption"] = f"{e('🎁' if gift else '⭐')}{strip_stars(hl)}\n\n{lead}{body}\n\n{cta}"
    elif kind == "season":
        lay = "bold" if prev_layout != "bold" else "split"
        p.update(layout=lay, label=f"{ctx['season'].title()} in {city}", headline=hl, sub=sub_line(body),
                 icon=("sun" if ctx.get("zone") == "warm" and ctx["season"] == "winter" else {"winter": "snowflake", "spring": "flower", "summer": "sun", "fall": "leaf"}.get(ctx["season"], icons[0])))
        p["caption"] = f"{e(SEASON_EMOJI.get(ctx['season'], ''))}{strip_stars(hl)}\n\n{body}\n\n{cta}"
    elif kind in ("bts", "team"):
        p.update(layout="frame", label="Behind the scenes" if kind == "bts" else "Meet the team", headline=hl, sub=sub_line(body))
        idea = (it.get("check") or "a photo of the team at work") if kind == "bts" else "a team photo (with everyone's OK)"
        p["check"] = ""                                                # a BTS tuple's third field is the photo idea, not a question
        p["photo_idea"] = "Better with a real photo: " + idea
        p["caption"] = f"{e(KIND_EMOJI[kind])}{strip_stars(hl)}\n\n{body}\n\nFollow along for more from {brand['name']}."
    elif kind == "review":
        real = it.get("real")
        if real:
            txt = real["text"] if len(real["text"]) <= 190 else real["text"][:187].rsplit(" ", 1)[0] + "..."
            p.update(layout="quote", label="Customer love", headline="What our customers say", sub="", quote={"text": txt, "who": real["who"] + ", Google review"})
            p["caption"] = (f"{e('⭐')}What our customers say\n\n\"{real['text']}\" - {real['who']}\n\nThank you! Reviews like this make our whole week.\n\n{cta}")
        else:
            p.update(layout="quote", label="Thank you", headline=hl, sub=sub_line(body))
            p["caption"] = f"{e('⭐')}{strip_stars(hl)}\n\n{body}"
            p["check"] = ""
    elif kind == "faq":
        p.update(layout="qa", label="You asked", headline=hl, sub=sub_line(body, 150))
        p["caption"] = f"{e('❓')}{strip_stars(hl)}\n\n{body}\n\nGot a question? Ask it in the comments and we will answer.\n\n{cta}"
    elif kind == "local":
        p.update(layout="minimal", label=f"Proudly {city}", headline=hl, sub=sub_line(body), icon="pin")
        p["caption"] = f"{e('📍')}{strip_stars(hl)}\n\n{body}"
    elif kind == "engage":
        lay = "minimal" if prev_layout != "minimal" else "bold"
        p.update(layout=lay, label="Your turn", headline=hl, sub=sub_line(body))
        p["caption"] = f"{e('💬')}{strip_stars(hl)}\n\n{body}"
    elif kind == "booking":
        p.update(layout="bold", label=f"{d.strftime('%B')} bookings", headline=hl, sub=sub_line(body), icon="calendar")
        p["caption"] = f"{e('📅')}{strip_stars(hl)}\n\n{body}\n\n{cta}"
    elif kind == "checklist":
        items = [fill(x, ctx) for x in it["items"]]
        p.update(layout="checklist", label="Save this", headline=hl, sub="", items=items)
        lines = "\n".join(("✅ " if emoji else "- ") + x for x in items)
        p["caption"] = f"{e('📋')}{strip_stars(hl)}\n\n{lines}\n\nSave this list for later. {cta}"
    return p


def _holiday_label(h: dict) -> str:
    if h["key"] in ("christmas", "hanukkah", "kwanzaa"):
        return "Happy holidays"
    if h["kind"] == "season":
        return h["name"]
    return f"{h['date'].strftime('%B')} {h['date'].day}"


def _dedupe(posts: list) -> None:
    seen = {}
    for p in posts:
        key = re.sub(r"\W+", " ", p["caption"].lower()).strip()
        if key in seen:
            p["caption"] += f"\n\n(Post {p['n']} of the month.)"
        seen[key] = p["n"]


def hashtags(p: dict, pack: dict, brand: dict, season: str, seed: int) -> list[str]:
    city, st = tag_word(brand["city"]), brand["state"]
    out = []
    if city:                                                           # 2 local tags, 2 trade tags, 1 for the topic, 1 general: 6
        out += [f"#{city}{pack['city_tag']}", (f"#{city}{st}" if st and p["n"] % 2 else f"#{city}")]
    tags = pack["tags"]
    k = (seed + p["n"] * 3) % len(tags)
    out += [tags[k % len(tags)], tags[(k + 3) % len(tags)]]
    if p["kind"] == "holiday":
        out.insert(0, HOLIDAY_TAG.get(p.get("holiday_key") or "", "") or "#" + tag_word(p.get("holiday") or "Holidays"))
    elif p["kind"] == "season":
        out.append(SEASON_TAG.get(season, "#ShopLocal"))
    else:
        kt = KIND_TAG.get(p["kind"]) or []
        if kt:
            out.append(kt[p["n"] % len(kt)])
    out.append(GENERAL_TAGS[p["n"] % len(GENERAL_TAGS)])
    res = []
    for t in out:
        if t and t != "#" and t.lower() not in [x.lower() for x in res]:
            res.append(t)
    return res[:6]


def alt_text(p: dict, brand: dict) -> str:
    words = strip_stars(p.get("headline") or "")
    if p.get("quote"):
        words = f"\"{p['quote']['text']}\" - {p['quote']['who']}"
    if p.get("items"):
        words += ": " + ", ".join(p["items"])
    t = f"Graphic for {brand['name']}" + (f" in {brand['city']}" if brand["city"] else "") + f": {words}"
    if p.get("sub"):
        t += f". {p['sub']}"
    return t[:240]


# ---------------------------------------------------------------------------------------------------------------- outputs
def caption_full(p: dict) -> str:
    return p["caption"] + "\n\n" + " ".join(p["hashtags"])


def write_csv(plan: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(CSV_COLUMNS)
        for p in plan["posts"]:
            w.writerow([p["n"], p["date"], p["time"], p["weekday"], "Facebook + Instagram", KIND_LABEL.get(p["kind"], p["kind"]), p["layout"],
                        p["caption"], " ".join(p["hashtags"]), caption_full(p), p["square"], p["story"], p["alt"], p["check"], p["photo_idea"]])


def write_captions(plan: dict, path: str) -> None:
    lines = [f"{plan['brand']['name']} - {plan['label']} - {len(plan['posts'])} posts (+ a story for each)", ""]
    for p in plan["posts"]:
        d = dt.date.fromisoformat(p["date"])
        lines += ["=" * 60, f"#{p['n']:02d}  {d.strftime('%a %b')} {d.day}  {fmt_time(p['time'])}  ({KIND_LABEL.get(p['kind'], p['kind'])})",
                  f"Image: {p['square']}   Story: {p['story']}"]
        if p["check"]:
            lines.append(f"CHECK WITH CLIENT FIRST: {p['check']}")
        lines += ["-" * 60, caption_full(p), ""]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def client_message(plan: dict) -> str:
    name = plan["brand"]["name"]
    n = len(plan["posts"])
    text = [f"Hi! Here is the {plan['label']} social plan for {name}: {n} posts, each with a matching story, scheduled at the best times "
            f"for your customers. The preview picture is attached."]
    if plan["holidays"]:
        text.append("This month covers: " + ", ".join(plan["holidays"]) + ".")
    if plan["checks"]:
        text.append("Before I schedule them, a few quick yes/no questions so every post is accurate:")
        text += [f"  {i}. {q}" for i, q in enumerate(plan["checks"], 1)]
    ideas = [p for p in plan["posts"] if p["photo_idea"]]
    if ideas:
        text.append("Optional: these posts look even better with a real photo from you (just text it to me):")
        text += [f"  - {p['date']}: {p['photo_idea'].replace('Better with a real photo: ', '')}" for p in ideas]
    text.append("Reply YES (plus any answers) and I will schedule everything.")
    return "\n".join(text) + "\n"


HOW_TO = """HOW TO POST THIS MONTH ({label}, {name})

1. Send client_message.txt and contact_sheet.png to the client. Wait for YES (and fix any post they say no to).
2. On a computer: open contact_sheet.html (double-click). Open business.facebook.com > Planner in a second window.
   Click the day > Schedule post > add the square image from the posts folder > tap Copy caption on the sheet and paste >
   tick Facebook + Instagram > Schedule at the time shown. Stories: Create story > story image > Schedule.
3. Tick each card on the sheet as you go. Meta schedules about a month ahead: do it on the 1st (or the day before).

Meta Business Suite has no free CSV import for page posts (see docs/AGENCY_CONTENT.md), so posts.csv is the
schedule sheet: open it in Excel / Google Sheets, or use it with a scheduler that imports CSV files.
"""


def write_outputs(plan: dict, out_dir: str, render: bool = True, renderer=None, quiet: bool = False) -> dict:
    from agency.content import sheet as SH
    from agency.content import render as R
    os.makedirs(os.path.join(out_dir, "posts"), exist_ok=True)
    _guard_gitignore(out_dir)
    trade = plan["trade"]
    client = plan["client"]
    brand = brand_for(client, trade, None)
    brand["palette"] = plan["palette"]
    brand["vars"] = D.palette_vars(plan["palette"])
    made = {"images": 0, "renderer": "none"}
    if render:
        own = renderer is None
        r = renderer or R.Renderer()
        try:
            made["renderer"] = r.kind + (f" ({os.path.basename(r.detail)})" if r.detail else "")
            if r.ok:
                for p in plan["posts"]:
                    for fmt, key in (("square", "square"), ("story", "story")):
                        w, h = D.SIZES[fmt]
                        r.png(D.page(p, brand, fmt), os.path.join(out_dir, p[key]), w, h)
                        made["images"] += 1
                    if not quiet:
                        print(f"  drew post {p['n']:02d}/{len(plan['posts'])} ({p['layout']})", flush=True)
            else:
                for p in plan["posts"]:                              # no browser at all: keep the pages so they can be opened
                    for fmt, key in (("square", "square"), ("story", "story")):
                        with open(os.path.join(out_dir, p[key].replace(".png", ".html")), "w", encoding="utf-8") as fh:
                            fh.write(D.page(p, brand, fmt))
        finally:
            if own:
                r.close()
    with open(os.path.join(out_dir, "posts.json"), "w", encoding="utf-8") as fh:
        json.dump(plan, fh, indent=1, ensure_ascii=False, default=str)
    write_csv(plan, os.path.join(out_dir, "posts.csv"))
    write_captions(plan, os.path.join(out_dir, "captions.txt"))
    with open(os.path.join(out_dir, "client_message.txt"), "w", encoding="utf-8") as fh:
        fh.write(client_message(plan))
    with open(os.path.join(out_dir, "HOW_TO_POST.txt"), "w", encoding="utf-8") as fh:
        fh.write(HOW_TO.format(label=plan["label"], name=plan["brand"]["name"]))
    with open(os.path.join(out_dir, "contact_sheet.html"), "w", encoding="utf-8") as fh:
        fh.write(SH.contact_sheet(plan, brand, images=made["images"] > 0, html_pages=render and made["images"] == 0))
    if render and made["images"]:
        r = renderer or R.Renderer()
        try:
            prev = os.path.join(out_dir, "_preview.html")
            with open(prev, "w", encoding="utf-8") as fh:
                fh.write(SH.preview_page(plan, brand))
            r.full_png(prev, os.path.join(out_dir, "contact_sheet.png"), 1600, h_hint=SH.preview_height(plan))
            os.remove(prev)
        finally:
            if renderer is None:
                r.close()
    return made


def _guard_gitignore(out_dir: str) -> None:
    """real client work never lands in git: a self-ignoring .gitignore at the top of data/agency/ (inside the repo only)"""
    ab = os.path.abspath(out_dir)
    data = os.path.join(ROOT, "data", "agency")
    if ab.startswith(data + os.sep) or ab == data:
        top = os.path.join(data, "content") if ab.startswith(os.path.join(data, "content")) else data
        gi = os.path.join(top, ".gitignore")
        if not os.path.exists(gi):
            os.makedirs(top, exist_ok=True)
            with open(gi, "w", encoding="utf-8") as fh:
                fh.write("# real client content: never committed (agency/content/make_posts.py)\n*\n")


def client_slug(client: dict) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", str(client.get("id") or client.get("name") or "client")).strip("-").lower() or "client"


def default_out(client: dict, month: str) -> str:
    return os.path.join(ROOT, "data", "agency", "content", client_slug(client), month)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Make a month of social posts for a local business client.")
    ap.add_argument("client", nargs="?", default=os.path.join(ROOT, "data", "agency", "clients.json"), help="client JSON (one, a list, or {clients: [...]})")
    ap.add_argument("--month", default="next", help="YYYY-MM, or next / this (default next)")
    ap.add_argument("--id", dest="cid")
    ap.add_argument("--all", action="store_true", help="every paying client whose package has social posts")
    ap.add_argument("--posts", type=int, default=0, help="12-20 (default from the social add-on: social basic 12, social pro 20, otherwise 16)")
    ap.add_argument("--out")
    ap.add_argument("--colors", help='the client brand colours, e.g. "#14213D,#D4A24C"')
    ap.add_argument("--reviews", help="a text file of real reviews, one per line: text | name")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--no-images", action="store_true")
    ap.add_argument("--no-emoji", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    if not os.path.isfile(a.client):
        print(f"client file not found: {a.client}\n  make one like agency/content/fixtures/client_barber.json", file=sys.stderr)
        return 2
    y, m = S.parse_month(a.month)
    clients = choose_clients(load_clients(a.client), a.cid, a.all)
    if not clients:
        print("No paying client has social posts yet. Write it in the client's package (e.g. \"growth + social basic\" or "
              "\"social pro\"), or make one client's month with --id <client id>.", file=sys.stderr)
        return 1
    skipped = []
    for c in clients:
        try:
            P.trade_of(c.get("trade", ""))
        except ValueError as e:                                        # a trade with no pack: say so, carry on with the others
            skipped.append(f"{c.get('name') or c.get('id')}: {e}")
            continue
        plan = plan_month(c, y, m, a.posts or None, a.seed, read_reviews(a.reviews, c), not a.no_emoji, a.colors)
        out = a.out if (a.out and len(clients) == 1) else (os.path.join(a.out, str(c.get("id"))) if a.out else default_out(c, plan["month"]))
        if not a.quiet:
            print(f"{plan['brand']['name']} ({plan['trade_label']}, {plan['brand']['city'] or '-'}) - {plan['label']}: {len(plan['posts'])} posts", flush=True)
        made = write_outputs(plan, out, render=not a.no_images, quiet=a.quiet)
        if not a.quiet:
            layouts = sorted({p["layout"] for p in plan["posts"]})
            print(f"  {len(plan['posts'])} posts, {made['images']} images ({made['renderer']}), {len(layouts)} designs, "
                  f"{len(plan['checks'])} questions for the client\n  folder: {out}")
    for s in skipped:
        print(f"skipped {s}", file=sys.stderr)
    return 1 if skipped and len(skipped) == len(clients) else 0


if __name__ == "__main__":
    sys.exit(main())
