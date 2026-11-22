"""A dollar score for a website lead (lead 2026-11-22: 'find big leads'): who is most likely to pay, and pay more.

usd_score = trade value x 10 (roofing / HVAC / plumbing / electrical first, restaurants last) + a phone (a person can call)
            + site_down (they already paid for a site once and it's broken) + a street address + listed hours + map confidence.
Overture has no ratings or review counts, so they are not part of the score (said, not guessed).
"""
from __future__ import annotations

import re

# (keywords in the category / kind / name, value 1-10): first match wins, high-ticket first
TRADE_VALUE = [
    (r"roof", 10, "roofing"), (r"hvac|heating|air_condition|air condition|furnace", 10, "HVAC"), (r"plumb|drain|septic|water_heater", 9, "plumbing"),
    (r"electric(?!al_supply)|electrician|generator", 9, "electrical"), (r"solar", 9, "solar"),
    (r"remodel|renovat|kitchen_and_bath|kitchen_remodel|cabinet|bathroom|basement|contractor|construction|builder|carpent|flooring|tile|paint|drywall|siding|window_install|windows_and_doors|garage_door|"
     r"gutter|fence|deck|paving|asphalt|concrete|masonry|foundation|insulation|handyman|home_improvement|garage_door|pool", 8, "remodeling / trades"),
    (r"landscap|lawn|tree|garden_service|irrigation|snow", 8, "landscaping"),
    (r"pest|exterminat|mold|restoration|water_damage|locksmith|moving|movers|junk|cleaning|maid|carpet|pressure_wash|chimney", 6, "home services"),
    (r"auto|car_repair|mechanic|body_shop|collision|tire|transmission|brake|oil_change|towing|detailing|car_wash", 7, "auto"),
    (r"dent|orthodont|endodont|periodont", 7, "dental"),
    (r"chiropract|physical_therap|physiotherap|med_spa|medspa|dermatolog|optometr|eye_care|vision|veterinar|animal_hospital|podiatr|"
     r"hearing|massage_therap|acupunct", 6, "health (medical-adjacent)"),
    (r"attorney|law|lawyer|legal|accountant|accounting|tax|cpa|insurance|financial|real_estate", 5, "professional"),
    (r"gym|fitness|yoga|pilates|martial|dance|crossfit|boxing", 4, "fitness"),
    (r"salon|barber|beauty|nail|spa|hair|lash|brow|wax|tattoo", 4, "beauty"),
    (r"health|clinic|medical|doctor|physician|pharmacy|therap|counsel|mental", 5, "health"),
    (r"store|shop|retail|boutique|florist|jewel|furniture|clothing|apparel|gift|thrift|hardware", 2, "retail"),
    (r"restaurant|cafe|coffee|bar|pub|pizza|food|bakery|deli|eatery|grill|diner|ice_cream|sushi|taco|burger|kitchen_restaurant", 1, "restaurant / food"),
]
NICHE_DEFAULT = {"contractor": 8, "trades": 8, "auto": 7, "health": 5, "pro": 5, "services": 5, "beauty": 4, "fitness": 4, "gym": 4,
                 "retail": 2, "food": 1}


def trade(L: dict) -> tuple:
    """(value 1-10, label) from the lead's category / kind / name; the niche when nothing matches"""
    text = " ".join(str(L.get(k) or "") for k in ("category", "kind", "name")).lower().replace(" ", "_")
    for rx, v, label in TRADE_VALUE:
        if re.search(rx, text):
            return v, label
    n = str(L.get("niche") or "")
    return NICHE_DEFAULT.get(n, 3), n or "other"


def has_phone(L: dict) -> bool:
    return len(re.sub(r"\D", "", str(L.get("phone") or ""))[-10:]) == 10


def score(L: dict) -> int:
    v, _ = trade(L)
    s = v * 10
    s += 10 if has_phone(L) else 0
    s += 15 if (L.get("web") or {}).get("verdict") == "site_down" else 0
    s += 5 if re.match(r"\d+\w?\s+\S+", str(L.get("street") or L.get("address") or "")) else 0
    s += 3 if L.get("hours") else 0
    s += 3 if L.get("heat") == "hot" else 0
    return s
