#!/usr/bin/env python3
"""WEB LEADS: local businesses that need a website, from OpenStreetMap (free, public), for the Agency's call list.

For a Maryland town the owner picks, it asks the public Overpass API ONCE for named businesses (restaurants, contractors, salons,
auto, gyms, health, professional services, shops), keeps the ones with NO website tag (a Facebook page only counts as "no real
site"), leaves out chains (brand tags), and scores each: no site + a phone + opening hours + an address = hot. It writes
tools/web_public/agency/leads/leads.json (name, niche, town, phone, address, hours, why hot, best offer, the OSM link).
Business listings only (OSM maps businesses, not people); it never contacts anyone; no key; no paid service.

Usage policy (checked 2026-11-20):
  - Overpass API: https://wiki.openstreetmap.org/wiki/Overpass_API#Public_Overpass_API_instances ("well below 10,000 queries
    per day and 1 GB a day" for the main instance; be polite, identify yourself). This tool sends ONE query per town, waits
    >= 1 s between towns, names itself in the User-Agent (no person), and caches nothing it does not need.
  - OSM data licence: ODbL, https://www.openstreetmap.org/copyright : "(c) OpenStreetMap contributors" is written into
    leads.json and shown on the page.
  - OSM operations policies: https://operations.osmfoundation.org/policies/ (no heavy use, valid User-Agent).

    python tools/web_leads.py                         # the default towns (TOWNS below), merged into one leads.json
    python tools/web_leads.py --town "Frederick" --town "Annapolis"
    python tools/web_leads.py --from-file osm.json --town Frederick   # offline: an Overpass JSON answer (tests)
Exit: 0 ok, 2 every server failed (nothing written: stale beats invented).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "tools", "web_public", "agency", "leads", "leads.json")
UA = "olympus-web-leads/1.0 (small-business website lead finder; one query per town)"
SERVERS = ("https://overpass-api.de/api/interpreter", "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
           "https://overpass.kumi.systems/api/interpreter")
# Towns (south, west, north, east boxes around each centre). The owner's area first: within ~40 miles of Frederick (lead 2026-11-20),
# then the rest of Maryland. Any other town: --town NAME --bbox S,W,N,E (or the name lookup without --bbox).
FREDERICK_AREA = {
    "Frederick": (39.380, -77.470, 39.470, -77.360), "Hagerstown": (39.610, -77.760, 39.670, -77.690),
    "Germantown": (39.140, -77.310, 39.210, -77.220), "Gaithersburg": (39.100, -77.250, 39.170, -77.160),
    "Rockville": (39.050, -77.200, 39.120, -77.100), "Columbia": (39.160, -76.920, 39.240, -76.800),
    "Ellicott City": (39.240, -76.870, 39.300, -76.770), "Westminster": (39.550, -77.040, 39.600, -76.960),
    "Mount Airy": (39.350, -77.180, 39.390, -77.130), "Urbana": (39.310, -77.380, 39.350, -77.320),
    "Middletown": (39.430, -77.560, 39.460, -77.520), "Thurmont": (39.610, -77.430, 39.640, -77.390),
    "Brunswick": (39.300, -77.650, 39.330, -77.600), "Walkersville": (39.470, -77.370, 39.500, -77.330),
    "Damascus": (39.270, -77.230, 39.310, -77.180), "Clarksburg": (39.210, -77.300, 39.260, -77.240)}
MARYLAND = {
    "Annapolis": (38.940, -76.540, 39.000, -76.460), "Bowie": (38.920, -76.790, 39.010, -76.690),
    "Laurel": (39.060, -76.900, 39.120, -76.820), "Silver Spring": (38.980, -77.060, 39.060, -76.980),
    "Bethesda": (38.960, -77.140, 39.020, -77.070), "College Park": (38.960, -76.960, 39.010, -76.900),
    "Greenbelt": (38.980, -76.910, 39.020, -76.860), "Hyattsville": (38.940, -76.970, 38.980, -76.920),
    "Towson": (39.380, -76.630, 39.420, -76.580), "Catonsville": (39.250, -76.770, 39.300, -76.700),
    "Owings Mills": (39.400, -76.820, 39.440, -76.750), "Glen Burnie": (39.140, -76.650, 39.190, -76.590),
    "Severna Park": (39.060, -76.580, 39.100, -76.520), "Odenton": (39.060, -76.730, 39.110, -76.670),
    "Dundalk": (39.240, -76.540, 39.290, -76.480), "Essex": (39.290, -76.480, 39.330, -76.420),
    "Bel Air": (39.500, -76.380, 39.570, -76.310), "Aberdeen": (39.490, -76.190, 39.530, -76.140),
    "Elkton": (39.590, -75.860, 39.630, -75.800), "Waldorf": (38.580, -76.980, 38.670, -76.870),
    "La Plata": (38.510, -76.990, 38.550, -76.950), "Lexington Park": (38.240, -76.480, 38.290, -76.420),
    "Prince Frederick": (38.520, -76.610, 38.560, -76.570), "Easton": (38.750, -76.100, 38.800, -76.040),
    "Cambridge": (38.540, -76.110, 38.590, -76.040), "Chestertown": (39.190, -76.090, 39.230, -76.040),
    "Salisbury": (38.330, -75.650, 38.400, -75.560), "Ocean City": (38.330, -75.100, 38.460, -75.050),
    "Cumberland": (39.620, -78.800, 39.680, -78.730), "Frostburg": (39.640, -78.950, 39.670, -78.910),
    "Oakland": (39.400, -79.420, 39.430, -79.390), "Baltimore": (39.200, -76.710, 39.370, -76.530)}
TOWNS = {**FREDERICK_AREA, **MARYLAND}
GROUPS = {"frederick": FREDERICK_AREA, "maryland": MARYLAND, "all": TOWNS}
STATE = "US-MD"
GAP_S = 1.1
BACKOFF_S = (20, 60)        # a busy / timed-out server: wait, then ask it again (polite backoff), then the next server
SPLIT_BYTES = 300_000
# Nominatim reverse geocoding (the missing street addresses). Policy https://operations.osmfoundation.org/policies/nominatim/ :
# at most 1 request a second, a valid app User-Agent, results cached (this file), the ODbL credit. No bulk: only leads with no address.
NOMINATIM = "https://nominatim.openstreetmap.org/reverse"
GEO_CACHE = os.path.join(ROOT, "research", "web_leads", "geocode_cache.json")
GEO_GAP_S = 1.1
_GEO_LAST = [0.0]           # the time of the last Nominatim request (monotonic), across every geocode() call       # leads.json over this: one file per town in leads/towns/
LICENSE = "Data (c) OpenStreetMap contributors, ODbL (openstreetmap.org/copyright)"

# niche: (OSM tag key, regex of values) ... first match wins
NICHES = [
    ("contractor", "craft", r"^(plumber|electrician|hvac|roofer|carpenter|painter|builder|tiler|plasterer|stonemason|"
                            r"window_construction|floorer|gardener|landscaper|locksmith|glaziery|insulation|metal_construction)$"),
    ("contractor", "shop", r"^(doityourself|trade|hardware)$"),
    ("auto", "shop", r"^(car_repair|tyres|car_parts|motorcycle|car)$"),
    ("auto", "amenity", r"^(car_repair|car_wash|vehicle_inspection)$"),
    ("beauty", "shop", r"^(hairdresser|beauty|nails|massage|cosmetics|tattoo|barber)$"),
    ("fitness", "leisure", r"^(fitness_centre|sports_centre|dance)$"),
    ("fitness", "amenity", r"^(dojo|gym)$"),
    ("health", "amenity", r"^(dentist|doctors|clinic|veterinary|chiropractor)$"),
    ("health", "healthcare", r".+"),
    ("food", "amenity", r"^(restaurant|cafe|fast_food|bar|pub|ice_cream|food_court|biergarten)$"),
    ("food", "shop", r"^(bakery|butcher|deli|confectionery|coffee|seafood|alcohol|wine|beverages)$"),
    ("pro", "office", r"^(lawyer|accountant|insurance|estate_agent|financial|tax_advisor|architect|it|consulting)$"),
    ("services", "shop", r"^(dry_cleaning|laundry|tailor|florist|pet_grooming|photo|copyshop|funeral_directors)$"),
    ("retail", "shop", r".+"),
]
# best offer per niche (research/handoff/2026-11-20/web/research/RESEARCH.md on day-archive: starter site $1,500 for 5 pages / 2 weeks;
# reviews + Google profile $199-$399 a month; phone-scan 3D tour $300-$800 for places people visit; missed-call text-back $97-$149 a month)
OFFER = {"food": "starter site $1,500 (menu, hours, map, online-order link) + reviews & Google profile $199-$399/mo",
         "contractor": "starter site $1,500 (services, service area, quote form, reviews) + missed-call text-back $97-$149/mo",
         "beauty": "starter site $1,500 with online booking + phone-scan 3D tour of the salon $300-$800",
         "auto": "starter site $1,500 (services + prices, book a repair, map) + reviews & Google profile $199-$399/mo",
         "fitness": "site + 3D tour $2,500 (schedule, trial-pass form, a phone-scan 3D tour of the gym)",
         "health": "starter site $1,500 (services, new-patient form, insurance, map) + reviews & Google profile $199-$399/mo",
         "pro": "starter site $1,500 (services, about, contact form) + reviews & Google profile $199-$399/mo",
         "services": "starter site $1,500 (services + prices, hours, map, contact form) + Google profile $199-$399/mo",
         "retail": "starter site $1,500 (hours, map, what's in stock) + Google profile $199-$399/mo"}
OFFER_USD = {"fitness": 2500}                         # the build price (the monthly add-on is in the words)
TRADE = {"food": "restaurant", "beauty": "salon", "contractor": "contractor", "health": "medical", "auto": "auto", "fitness": "fitness",
         "retail": "retail", "services": "retail", "pro": "professional"}           # agency/callrules.json trades (the call script)
VALUE = {"contractor": 2, "health": 2, "auto": 1, "beauty": 1, "fitness": 1, "pro": 1, "food": 0, "services": 0, "retail": 0}
NAME = {"food": "Restaurant / food", "contractor": "Contractor / trades", "beauty": "Salon / beauty", "auto": "Auto",
        "fitness": "Gym / fitness", "health": "Health", "pro": "Professional services", "services": "Local services", "retail": "Shop"}


def _vals(key, *niches) -> str:
    out = []
    for n, k, rx in NICHES:
        if k == key and (not niches or n in niches) and rx != r".+":
            out += re.findall(r"[a-z_]+", rx)
    return "|".join(sorted(set(out)))


def kinds() -> list:
    """The small queries of one town [(name, selector)]: the 6 business types, the big ones split so each fits the public gateways."""
    shop_named = _vals("shop")
    return [("trades", '["craft"]["name"]'), ("offices", '["office"]["name"]'), ("healthcare", '["healthcare"]["name"]'),
            ("gyms", '["leisure"~"^(fitness_centre|sports_centre|dance)$"]["name"]'),
            ("food places", f'["amenity"~"^({_vals("amenity", "food")})$"]["name"]'),
            ("health + auto places", f'["amenity"~"^({_vals("amenity", "health", "auto", "fitness")})$"]["name"]'),
            ("beauty + auto shops", f'["shop"~"^({_vals("shop", "beauty", "auto")})$"]["name"]'),
            ("food + service shops", f'["shop"~"^({_vals("shop", "food", "services", "contractor")})$"]["name"]'),
            ("other shops", f'["shop"]["shop"!~"^({shop_named})$"]["name"]')]


def parts(bbox=None, town="") -> list:
    """The Overpass query texts for one town, one per kind (a single union times out on the public mirrors' gateways)."""
    if bbox:
        where, head = "(" + ",".join(f"{x:.4f}" for x in bbox) + ")", ""
    else:
        where = "(area.t)"
        head = (f'area["ISO3166-2"="{STATE}"]["admin_level"="4"]->.st;'
                f'area["name"="{town}"]["boundary"~"^(administrative|census)$"](area.st)->.t;')
    return [f"[out:json][timeout:50];{head}nwr{sel}{where};out center tags;" for _, sel in kinds()]


def query(town: str, bbox=None) -> str:                        # kept for the docs / tests: the first part
    return parts(bbox, town)[0]


def ask(q: str, http=None, servers=SERVERS, sleep=time.sleep, say=print, backoff=BACKOFF_S):
    """One Overpass query: each public server in order, >= 1 s apart; a busy / slow answer (429 / 502-504 / timeout) = wait the
    backoff and ask that server again (polite), then the next server. -> (elements, server) or (None, '')."""
    body = urllib.parse.urlencode({"data": q}).encode()
    first = True
    for url in servers:
        host = url.split("/")[2]
        for attempt in range(1 + len(backoff)):
            if not first:
                sleep(GAP_S if attempt == 0 else backoff[attempt - 1])
            first = False
            busy = False
            try:
                if http:
                    st, raw = http(url, body)
                else:
                    req = urllib.request.Request(url, data=body, headers={"User-Agent": UA, "Accept": "application/json"})
                    with urllib.request.urlopen(req, timeout=60) as r:
                        st, raw = r.status, r.read()
                if st == 200:
                    j = json.loads(raw)
                    if isinstance(j, dict) and isinstance(j.get("elements"), list):
                        return j["elements"], host
                busy = st in (429, 502, 503, 504)
                say(f"  [..] {host} answered {st}")
            except urllib.error.HTTPError as e:
                busy = e.code in (429, 502, 503, 504)
                say(f"  [..] {host}: {e.code}")
            except TimeoutError:
                say(f"  [..] {host}: timeout (next server)")
            except Exception as e:  # noqa: BLE001  (refused / closed connection: no point asking again)
                say(f"  [..] {host}: {e.__class__.__name__}")
            if not busy:
                break
    return None, ""


def fetch(town: str, bbox=None, http=None, servers=SERVERS, sleep=time.sleep, say=print, backoff=BACKOFF_S) -> dict | None:
    """Every kind of query for one town, 1+ s apart; a kind that fails on every server is listed in _failed (the PC run fills it).
    -> {"elements", "_server", "_parts_ok", "_parts", "_failed"} or None when no kind worked."""
    els, seen, ok, hosts, failed = [], set(), 0, set(), []
    for i, (name, q) in enumerate(zip([k for k, _ in kinds()], parts(bbox, town))):
        if i:
            sleep(GAP_S)
        got, host = ask(q, http, servers, sleep, say, backoff)
        if got is None:
            failed.append(name)
            continue
        ok += 1
        hosts.add(host)
        for e in got:
            k = (e.get("type"), e.get("id"))
            if k not in seen:
                seen.add(k)
                els.append(e)
    return {"elements": els, "_server": ", ".join(sorted(hosts)), "_parts_ok": ok, "_parts": len(kinds()), "_failed": failed} if ok else None


def niche_of(tags: dict) -> tuple:
    for niche, key, rx in NICHES:
        v = str(tags.get(key) or "")
        if v and re.match(rx, v):
            return niche, f"{key}={v}"
    return None, ""


def phone_of(tags: dict) -> str:
    p = str(tags.get("phone") or tags.get("contact:phone") or "").split(";")[0].strip()
    d = re.sub(r"\D", "", p)
    if len(d) == 11 and d.startswith("1"):
        d = d[1:]
    return f"({d[:3]}) {d[3:6]}-{d[6:]}" if len(d) == 10 else ""


def site_of(tags: dict) -> tuple:
    """(real website?, facebook-only?)"""
    real = any(str(tags.get(k) or "").strip() for k in ("website", "contact:website", "url", "brand:website"))
    fb = any("facebook.com" in str(tags.get(k) or "") for k in ("contact:facebook", "facebook", "website", "contact:website", "url"))
    return (real and not (fb and not any("facebook.com" not in str(tags.get(k) or "") and str(tags.get(k) or "").strip()
                                         for k in ("website", "contact:website", "url")))), fb


# chains the map often leaves without brand tags (they have corporate sites: never a lead)
CHAIN_RX = re.compile(r"^(domino'?s|mcdonald'?s|subway|starbucks|dunkin'?( donuts)?|pizza hut|papa john'?s|wendy'?s|burger king|taco bell|"
                      r"chick-fil-a|kfc|popeyes|chipotle|panera( bread)?|arby'?s|sonic( drive-in)?|five guys|jimmy john'?s|little caesars|"
                      r"7-eleven|cvs( pharmacy)?|walgreens|rite aid|dollar general|dollar tree|family dollar|jiffy lube|valvoline|"
                      r"midas|meineke|pep boys|autozone|advance auto parts|o'?reilly auto parts|great clips|supercuts|sport clips|"
                      r"planet fitness|anytime fitness|la fitness|orangetheory( fitness)?|h&r block|jackson hewitt|state farm|allstate|"
                      r"applebee'?s|ihop|denny'?s|olive garden|red robin|chili'?s|outback steakhouse|buffalo wild wings|wawa|sheetz|royal farms|"
                      # the factory's finds (lead 2026-11-20) + common Maryland chains / franchises / banks / carriers
                      r"bonefish( grill)?|glory days( grill)?|crunch( fitness)?|bruster'?s( real ice cream)?|exxon|ymca|medstar|anchor bar|"
                      r"america'?s best wings|shell|bp|sunoco|mobil|chevron|citgo|valero|gulf|panda express|jersey mike'?s|firehouse subs|"
                      r"potbelly|qdoba|noodles( & company)?|red lobster|longhorn steakhouse|texas roadhouse|cracker barrel|bob evans|"
                      r"gold'?s gym|snap fitness|massage envy|hand & stone|european wax center|fantastic sams|kumon|mathnasium|liberty tax|"
                      r"edward jones|re/?max|keller williams|long & foster|coldwell banker|century 21|chase|bank of america|wells fargo|pnc|"
                      r"m&t( bank)?|td bank|truist|capital one|verizon|at&t|t-mobile|the ups store|fedex|walmart|target|giant|safeway|"
                      r"weis|food lion|aldi|lidl|costco|home depot|lowe'?s|petsmart|petco|ulta|sephora|gnc|vitamin shoppe|hallmark|"
                      r"goodwill|dollar general|tj maxx|marshalls|ross|kohl'?s|starbucks|tropical smoothie( cafe)?|smoothie king|"
                      r"chuck e\.? cheese|dave & buster'?s|cinnabon|auntie anne'?s|baskin|dairy queen|rita'?s|carvel|cold stone)\b", re.I)


def lead_of(el: dict, town: str) -> tuple:
    """(lead dict | None, reason it was left out)"""
    t = el.get("tags") or {}
    name = str(t.get("name") or "").strip()
    if not name:
        return None, "no_name"
    op = str(t.get("operator") or "").strip()
    if t.get("brand") or t.get("brand:wikidata") or t.get("operator:wikidata") or CHAIN_RX.match(name) or (op and op.lower() != name.lower() and CHAIN_RX.match(op)):
        return None, "chain"
    if str(t.get("disused") or t.get("abandoned") or "").lower() in ("yes", "true") or "disused:shop" in t:
        return None, "closed"
    niche, kind = niche_of(t)
    if not niche:
        return None, "other"
    real, fb = site_of(t)
    if real:
        return None, "has_site"
    phone = phone_of(t)
    hn, road = str(t.get("addr:housenumber") or "").strip(), str(t.get("addr:street") or "").strip()
    street = " ".join(x for x in (hn, road) if x).strip()
    city = str(t.get("addr:city") or town)
    zipc = (re.match(r"\d{5}", str(t.get("addr:postcode") or "")) or [""])[0]
    email = str(t.get("email") or t.get("contact:email") or "").split(";")[0].strip()
    email = email if re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", email, re.I) else ""
    lat, lon = el.get("lat"), el.get("lon")
    if lat is None and isinstance(el.get("center"), dict):
        lat, lon = el["center"].get("lat"), el["center"].get("lon")
    hours = str(t.get("opening_hours") or "")[:80]
    score, why = 4, ["no website on the map" if not fb else "only a Facebook page, no real website"]
    if fb:
        score -= 1
    if phone:
        score += 2
        why.append("a phone to call")
    if hours:
        score += 1
        why.append("opening hours listed (open, active)")
    if street:
        score += 1
        why.append("a street address (real storefront)")
    if email:
        score += 1
        why.append("an email on the map")
    if VALUE[niche]:
        score += VALUE[niche]
        why.append(f"{NAME[niche].lower()}: customers search for this online")
    heat = "hot" if score >= 8 else "warm" if score >= 6 else "cold"
    typ, osm_id = el.get("type", "node"), el.get("id")
    return {"id": f"osm-{typ[0]}{osm_id}", "name": name[:80], "niche": niche, "niche_name": NAME[niche], "kind": kind, "town": town,
            "city": city[:60], "state": "MD", "phone": phone, "email": email[:80], "street": street[:80], "zip": zipc,
            "address": (street + (", " + city if street else "") + (" MD " + zipc if street and zipc else ""))[:120], "addr_src": "map" if street else "",
            "lat": round(lat, 6) if isinstance(lat, (int, float)) else None, "lon": round(lon, 6) if isinstance(lon, (int, float)) else None,
            "mailable": bool(hn and road and city and zipc), "hours": hours,
            "facebook": bool(fb), "trade": TRADE[niche], "category": kind.split("=")[-1].replace("_", " "), "score": score, "heat": heat, "why": why, "offer": OFFER[niche], "offer_usd": OFFER_USD.get(niche, 1500),
            "osm": f"https://www.openstreetmap.org/{typ}/{osm_id}"}, ""


def build(answers: dict, now=None) -> dict:
    """answers = {town: overpass json}. -> the leads.json dict."""
    now = now or dt.datetime.now(dt.timezone.utc)
    leads, towns, skipped = [], [], {}
    seen = set()
    for town, j in answers.items():
        n0 = len(leads)
        mine_sk = {}
        for el in (j or {}).get("elements") or []:
            L, why = lead_of(el, town)
            if not L:
                skipped[why] = skipped.get(why, 0) + 1
                mine_sk[why] = mine_sk.get(why, 0) + 1
                continue
            key = (L["name"].lower(), L["phone"] or L["address"])
            if key in seen:
                skipped["duplicate"] = skipped.get("duplicate", 0) + 1
                continue
            seen.add(key)
            leads.append(L)
        mine = leads[n0:]
        towns.append({"town": town, "state": "MD", "businesses": len((j or {}).get("elements") or []), "leads": len(mine),
                      "hot": sum(1 for x in mine if x["heat"] == "hot"), "server": (j or {}).get("_server", ""),
                      "parts_ok": (j or {}).get("_parts_ok"), "parts": len(kinds()), "missing": (j or {}).get("_failed") or [],
                      "chains": mine_sk.get("chain", 0), "with_site": mine_sk.get("has_site", 0)})
    leads.sort(key=lambda x: (-x["score"], x["town"], x["name"]))
    return {"v": 1, "kind": "web_leads", "demo": False, "fetched": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": "OpenStreetMap via the public Overpass API (a few small queries per town)", "license": LICENSE,
            "about": "Businesses on OpenStreetMap with no website tag. OSM can be out of date: check the business before you call.",
            "towns": towns, "skipped": skipped, "leads": leads}


def summary(out: dict) -> dict:
    """The Agency HQ tile's shape (the hub team): {n, label, next, t, pipe {leads, called}}. Called = 0 here (the phone keeps the marks)."""
    L = out.get("leads") or []
    hot = sum(1 for x in L if x.get("heat") == "hot" and x.get("phone"))
    towns = ", ".join(t["town"] for t in out.get("towns") or [])
    return {"n": len(L), "label": f"{len(L)} leads found", "next": (f"Call the {hot} hot ones in {towns}" if hot else
            f"Look up and call the best ones in {towns}") if L else "Run the lead finder on the PC",
            "t": int(dt.datetime.now(dt.timezone.utc).timestamp()), "pipe": {"leads": len(L), "called": 0}}


def geo_key(lat, lon) -> str:
    return f"{lat:.5f},{lon:.5f}"


def reverse(lat, lon, http=None) -> dict | None:
    """One Nominatim reverse lookup -> its address dict, or None."""
    url = NOMINATIM + "?" + urllib.parse.urlencode({"format": "jsonv2", "lat": f"{lat:.6f}", "lon": f"{lon:.6f}", "zoom": 18, "addressdetails": 1})
    try:
        if http:
            st, raw = http(url, None)
        else:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                st, raw = r.status, r.read()
        if st != 200:
            return None
        j = json.loads(raw)
        return j.get("address") if isinstance(j, dict) and isinstance(j.get("address"), dict) else None
    except Exception:  # noqa: BLE001
        return None


def geocode(leads: list, cache_path=GEO_CACHE, http=None, sleep=time.sleep, say=print, limit=None) -> dict:
    """Fill the street / city / ZIP of leads with no street address from their map point (Nominatim reverse, cached, >= 1.1 s apart).
    The address found is the nearest house number on the map: marked addr_src 'nearest' (check it before mailing).
    -> {"asked", "cached", "filled", "failed"}"""
    try:
        with open(cache_path, encoding="utf-8") as fh:
            cache = json.load(fh)
    except (OSError, ValueError):
        cache = {}
    st = {"asked": 0, "cached": 0, "filled": 0, "failed": 0}
    for L in leads:
        if L.get("street") or L.get("lat") is None or L.get("lon") is None:
            continue
        k = geo_key(L["lat"], L["lon"])
        if k in cache:
            a = cache[k]
            st["cached"] += 1
        else:
            if limit is not None and st["asked"] >= limit:
                continue
            wait = GEO_GAP_S - (time.monotonic() - _GEO_LAST[0])
            if wait > 0:
                sleep(wait)
            _GEO_LAST[0] = time.monotonic()
            st["asked"] += 1
            a = reverse(L["lat"], L["lon"], http)
            if a is None:
                st["failed"] += 1
                continue
            cache[k] = {x: a.get(x) for x in ("house_number", "road", "city", "town", "village", "hamlet", "postcode", "state") if a.get(x)}
            a = cache[k]
        hn, road = str(a.get("house_number") or "").split(";")[0].strip(), str(a.get("road") or "").strip()
        city = str(a.get("city") or a.get("town") or a.get("village") or a.get("hamlet") or L.get("city") or "")
        zipc = (re.match(r"\d{5}", str(a.get("postcode") or "")) or [""])[0]
        if road and (str(a.get("state") or "Maryland") == "Maryland"):
            L["street"] = " ".join(x for x in (hn, road) if x)[:80]
            L["city"] = city[:60] or L.get("city")
            L["zip"] = zipc or L.get("zip", "")
            L["address"] = (L["street"] + ", " + L["city"] + (" MD " + L["zip"] if L["zip"] else ""))[:120]
            L["addr_src"] = "nearest"
            L["mailable"] = bool(hn and road and L["city"] and L["zip"])
            st["filled"] += 1
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as fh:
        json.dump(cache, fh, separators=(",", ":"), sort_keys=True)
    say(f"  [OK] addresses from the map point: {st['filled']} filled ({st['asked']} asked, {st['cached']} from the cache, {st['failed']} failed)")
    return st


def slug(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


def load(out_path: str) -> dict | None:
    """The saved list (one file, or the index + one file per town). None when there is none / it is not ours."""
    try:
        with open(out_path, encoding="utf-8") as fh:
            j = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(j, dict) or j.get("kind") != "web_leads":
        return None
    if j.get("files"):
        leads = []
        for f in j["files"]:
            try:
                with open(os.path.join(os.path.dirname(out_path), f), encoding="utf-8") as fh:
                    leads += json.load(fh).get("leads") or []
            except (OSError, ValueError):
                pass
        j = dict(j, leads=leads)
        j.pop("files", None)
    return j


def merge(old: dict | None, new: dict) -> dict:
    """The new towns replace their old rows; every other town is kept; one lead per business (OSM id, then name + phone / address)."""
    if not old:
        return new
    # A re-asked town ADDS to what it had (a busy server answers different kinds each time): new rows win on the same business,
    # old businesses the new answer missed stay, and a kind counts as missing only if both runs missed it.
    redo = {t["town"] for t in new.get("towns") or []}
    oldt = {t.get("town"): t for t in old.get("towns") or []}
    newids = {x.get("id") for x in new.get("leads") or []}
    newkeys = {(str(x.get("name", "")).lower(), x.get("phone") or x.get("address")) for x in new.get("leads") or []}
    keep = [x for x in old.get("leads") or [] if x.get("town") not in redo
            or (x.get("id") not in newids and (str(x.get("name", "")).lower(), x.get("phone") or x.get("address")) not in newkeys)]
    towns = [t for t in old.get("towns") or [] if t.get("town") not in redo]
    for t in new.get("towns") or []:
        o = oldt.get(t.get("town"))
        if o:
            t = dict(t)
            if "missing" in o or "missing" in t:
                t["missing"] = [k for k in (t.get("missing") or []) if k in (o.get("missing") or [])]
            if isinstance(o.get("parts_ok"), int) and isinstance(t.get("parts_ok"), int):
                t["parts_ok"] = max(t["parts_ok"], o["parts_ok"], (t.get("parts") or 0) - len(t.get("missing") or []))
            t["_again"] = True
            for k in ("businesses", "chains", "with_site"):
                if isinstance(o.get(k), int) and isinstance(t.get(k), int):
                    t[k] = max(t[k], o[k])
        towns.append(t)
    ids = {x.get("id") for x in keep}
    keys = {(str(x.get("name", "")).lower(), x.get("phone") or x.get("address")) for x in keep}
    add, dup = [], 0
    for x in new.get("leads") or []:
        k = (str(x.get("name", "")).lower(), x.get("phone") or x.get("address"))
        if x.get("id") in ids or k in keys:
            dup += 1
            continue
        ids.add(x.get("id")); keys.add(k); add.append(x)
    leads = sorted(keep + add, key=lambda x: (-x.get("score", 0), x.get("town", ""), x.get("name", "")))
    for t in towns:
        if t.pop("_again", False):
            mine = [x for x in leads if x.get("town") == t.get("town")]
            t["leads"] = len(mine)
            if "hot" in t:
                t["hot"] = sum(1 for x in mine if x.get("heat") == "hot")
    sk = dict(old.get("skipped") or {})
    for k, v in (new.get("skipped") or {}).items():
        sk[k] = sk.get(k, 0) + v
    if dup:
        sk["duplicate"] = sk.get("duplicate", 0) + dup
    return dict(new, towns=towns, leads=leads, skipped=sk)


def save(out: dict, out_path: str):
    """leads.json (+ summary.json); over SPLIT_BYTES: leads.json = the index with "files", one leads/towns/<town>.json each."""
    d = os.path.dirname(out_path)
    os.makedirs(d, exist_ok=True)
    text = json.dumps(out, indent=1, ensure_ascii=False)
    tdir = os.path.join(d, "towns")
    if len(text.encode()) > SPLIT_BYTES:
        os.makedirs(tdir, exist_ok=True)
        files = []
        for t in out.get("towns") or []:
            f = f"towns/{slug(t['town'])}.json"
            with open(os.path.join(d, f), "w", encoding="utf-8") as fh:
                json.dump({"v": 1, "kind": "web_leads_town", "town": t["town"], "license": LICENSE,
                           "leads": [x for x in out["leads"] if x.get("town") == t["town"]]}, fh, ensure_ascii=False, separators=(",", ":"))
            files.append(f)
        index = dict(out, leads=[], files=files, count=len(out["leads"]))
        text = json.dumps(index, indent=1, ensure_ascii=False)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(text)
    with open(os.path.join(d, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary(out), fh)


def counts(out: dict) -> str:
    """A markdown table by town: leads, chains dropped, hot, with a phone, with an email, mailable, a column per niche, the kinds missing."""
    L = out.get("leads") or []
    niches = sorted({x.get("niche") for x in L if x.get("niche")})
    head = ("| Town | Leads | Chains dropped | Hot | Phone | Email | Mailable | " + " | ".join(NAME.get(n, n) for n in niches) + " | Kinds missing |")
    rows = [head, "|" + "---|" * (8 + len(niches))]
    f = lambda xs, k: sum(1 for x in xs if x.get(k))                 # noqa: E731
    for t in sorted(out.get("towns") or [], key=lambda t: t["town"]):
        mine = [x for x in L if x.get("town") == t["town"]]
        rows.append(f"| {t['town']} | {len(mine)} | {t.get('chains', 0)} | {sum(1 for x in mine if x.get('heat') == 'hot')} | {f(mine, 'phone')} | "
                    f"{f(mine, 'email')} | {f(mine, 'mailable')} | " + " | ".join(str(sum(1 for x in mine if x.get("niche") == n)) for n in niches)
                    + f" | {', '.join(t.get('missing') or []) or '-'} |")
    ch = sum(t.get("chains", 0) for t in out.get("towns") or [])
    rows.append(f"| **All** | **{len(L)}** | **{ch}** | **{sum(1 for x in L if x.get('heat') == 'hot')}** | **{f(L, 'phone')}** | **{f(L, 'email')}** | "
                f"**{f(L, 'mailable')}** | " + " | ".join(f"**{sum(1 for x in L if x.get('niche') == n)}**" for n in niches) + " | |")
    return "\n".join(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--town", action="append", help="a Maryland town / city (repeat); default: the --group")
    ap.add_argument("--group", default="frederick", choices=sorted(GROUPS), help="frederick (16 towns near Frederick) | maryland | all")
    ap.add_argument("--bbox", help="south,west,north,east for ONE --town not in the presets (faster than the name lookup)")
    ap.add_argument("--from-file", help="an Overpass JSON answer to use instead of the network (one --town)")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--fresh", action="store_true", help="start a new list (default: merge into the saved one, town by town)")
    ap.add_argument("--skip-done", action="store_true", help="skip towns already saved with every kind of query answered")
    ap.add_argument("--counts", action="store_true", help="print the leads by town x niche table and stop")
    ap.add_argument("--no-geocode", action="store_true", help="do not fill missing street addresses (Nominatim reverse)")
    ap.add_argument("--geocode-only", action="store_true", help="only fill the missing street addresses of the saved list, then stop")
    a = ap.parse_args(argv)
    saved = None if a.fresh else load(a.out)
    if a.counts:
        print(counts(saved or {"towns": [], "leads": []}))
        return 0
    if a.geocode_only:
        if not saved:
            print("[!!] no saved list to fill")
            return 2
        geocode(saved["leads"])
        save(saved, a.out)
        return 0
    towns = a.town or list(GROUPS[a.group])
    if a.skip_done and saved:
        done = {t["town"] for t in saved.get("towns") or [] if t.get("parts_ok") == t.get("parts") == len(kinds())}
        towns = [t for t in towns if t not in done]
    got = 0
    out = saved
    for i, t in enumerate(towns):
        if a.from_file:
            with open(a.from_file, encoding="utf-8") as fh:
                j = json.load(fh)
        else:
            if i:
                time.sleep(GAP_S)
            print(f"[..] {t}, MD: asking OpenStreetMap (Overpass), {len(kinds())} small queries")
            bb = tuple(float(x) for x in a.bbox.split(",")) if a.bbox and len(towns) == 1 else TOWNS.get(t)
            j = fetch(t, bb)
            if j is None:
                print(f"  [!!] {t}: every Overpass server failed; skipped (run it again later or on the PC)")
                continue
        new = build({t: j})
        if not a.from_file and not a.no_geocode:
            geocode(new["leads"])               # the missing street addresses (1 a second, cached)
        out = merge(out, new)
        save(out, a.out)                      # after every town: a long run can stop and resume (--skip-done)
        got += 1
        tt = next(x for x in out["towns"] if x["town"] == t)
        print(f"[OK] {t}: {tt['businesses']} businesses on the map, {tt['leads']} with no website ({tt['hot']} hot) via {tt['server']}"
              + (f"; still missing: {', '.join(tt['missing'])}" if tt.get("missing") else ""))
        if a.from_file:
            break
    if not got:
        print("[!!] nothing fetched: leads.json left as it was")
        return 2
    print(f"[OK] {len(out['leads'])} leads in {len(out['towns'])} towns -> {os.path.relpath(a.out, ROOT)}; left out: {out['skipped']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
