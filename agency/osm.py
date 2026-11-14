"""OpenStreetMap access for the lead finder: Overpass (the business list) and Nominatim (one geocode per city). Stdlib only.

House rules we follow (checked 2026-11-14):
  * Overpass (wiki.openstreetmap.org/wiki/Overpass_API): one query at a time (a lock file stops a second copy of this
    tool), a User-Agent that names the app, cache every answer (7 days by default), pause 30 s after HTTP 429 / 406 / 504.
    The main instance (overpass-api.de, FOSSGIS) asks COMMERCIAL users to self-host or pay, so for North America we
    default to the free North America instance on the same wiki list (ovp.dresel.systems/api-na: "free to use, no API
    key, 4 parallel queries per IP"); --endpoint picks another one.
  * Nominatim (operations.osmfoundation.org/policies/nominatim): at most 1 request per second, a real User-Agent, results
    cached on our side, attribution shown, and NEVER used to list businesses ("downloading all POIs in an area" is
    forbidden there). We call it once per new city name to find the centre point, then never again for that city.
    --center LAT,LON skips it completely.
  * The data is ODbL: every output carries "(c) OpenStreetMap contributors".
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from . import ATTRIBUTION, CACHE_DIR, UA, ensure_dir
from . import categories as C

ENDPOINTS = {
    "na": "https://ovp.dresel.systems/api-na/interpreter",     # North America (Geofabrik NA extract, nightly)
    "eu": "https://ovp.dresel.systems/api/interpreter",        # Europe
    "main": "https://overpass-api.de/api/interpreter",         # the world (FOSSGIS): non-commercial / one-off use
}
NA_COUNTRIES = {"us", "ca", "mx", "pr"}
NOMINATIM = "https://nominatim.openstreetmap.org/search"
OVERPASS_TTL = 7 * 86400
LOCK_STALE = 15 * 60


class SourceError(RuntimeError):
    """A data source could not answer (network, server busy, bad reply). The message is one plain sentence."""


# ------------------------------------------------------------------------------------------------ small helpers
def _cache(*parts) -> str:
    return os.path.join(ensure_dir(CACHE_DIR), *parts)


def _read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def _write_json(path, data):
    ensure_dir(os.path.dirname(path))
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)
    os.replace(tmp, path)


def http(url, data=None, timeout=60, headers=None):
    """One GET (or form POST when data is a dict). Returns (status, headers, body bytes). Raises SourceError on network failure."""
    h = {"User-Agent": UA, "Accept": "application/json"}
    h.update(headers or {})
    body = urllib.parse.urlencode(data).encode() if isinstance(data, dict) else data
    req = urllib.request.Request(url, data=body, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {}), e.read() if hasattr(e, "read") else b""
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise SourceError(f"could not reach {urllib.parse.urlsplit(url).netloc}: {getattr(e, 'reason', e)}") from e


class OneAtATime:
    """A lock file in the cache folder: a second copy of the lead finder waits instead of querying in parallel."""

    def __init__(self, name="overpass.lock", wait=600):
        self.path, self.wait, self.fd = _cache(name), wait, None

    def __enter__(self):
        t0 = time.time()
        while True:
            try:
                self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self.fd, f"{os.getpid()} {time.time():.0f}".encode())
                return self
            except FileExistsError:
                try:
                    if time.time() - os.path.getmtime(self.path) > LOCK_STALE:
                        os.remove(self.path)          # left behind by a crashed run
                        continue
                except OSError:
                    continue
                if time.time() - t0 > self.wait:
                    raise SourceError("another copy of the lead finder is still querying OpenStreetMap; try again in a few minutes")
                time.sleep(2)

    def __exit__(self, *exc):
        try:
            os.close(self.fd)
            os.remove(self.path)
        except OSError:
            pass


# ------------------------------------------------------------------------------------------------ Nominatim: the centre of a city
def geocode(place: str, refresh=False, fetch=None) -> dict:
    """'Fort Collins, CO' -> {lat, lon, name, city, state, state_code, country_code, bbox}. Cached for good (one request per city ever)."""
    key = re.sub(r"\s+", " ", place.strip().lower())
    store_path = _cache("geocode.json")
    store = _read_json(store_path, {}) or {}
    if key in store and not refresh:
        return store[key]
    fetch = fetch or http
    last = store.get("_last_request", 0)
    if time.time() - last < 1.1:                     # Nominatim: an absolute maximum of 1 request per second
        time.sleep(1.1 - (time.time() - last))
    q = urllib.parse.urlencode({"q": place, "format": "jsonv2", "limit": 1, "addressdetails": 1})
    status, _, body = fetch(f"{NOMINATIM}?{q}", timeout=30)
    store["_last_request"] = time.time()
    _write_json(store_path, store)
    if status != 200:
        raise SourceError(f"the city search answered HTTP {status}; pass --center LAT,LON instead")
    try:
        hits = json.loads(body)
    except ValueError as e:
        raise SourceError("the city search sent something that is not JSON; pass --center LAT,LON instead") from e
    if not hits:
        raise SourceError(f"no place called '{place}' was found; add the state, e.g. 'Fort Collins, CO'")
    h = hits[0]
    a = h.get("address") or {}
    iso = a.get("ISO3166-2-lvl4") or ""
    res = {
        "query": place, "lat": float(h["lat"]), "lon": float(h["lon"]), "name": h.get("display_name", place),
        "city": a.get("city") or a.get("town") or a.get("village") or a.get("municipality") or place.split(",")[0].strip(),
        "state": a.get("state", ""), "state_code": iso.split("-")[-1] if "-" in iso else "", "country_code": (a.get("country_code") or "").lower(),
        "bbox": [float(x) for x in h.get("boundingbox", [])][:4], "source": "nominatim", "t": int(time.time()),
    }
    store[key] = res
    _write_json(store_path, store)
    return res


def center_from(text: str) -> dict:
    """'40.585,-105.084' -> a centre without any network call."""
    m = re.match(r"^\s*(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)\s*$", text or "")
    if not m:
        raise ValueError("--center must look like 40.585,-105.084")
    lat, lon = float(m.group(1)), float(m.group(2))
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("--center is outside the map")
    return {"query": text, "lat": lat, "lon": lon, "name": text, "city": "", "state": "", "state_code": "", "country_code": "", "bbox": [], "source": "center"}


# ------------------------------------------------------------------------------------------------ Overpass: the business list
def build_query(lat, lon, radius_m, keys, timeout=90) -> str:
    """One union query: every wanted tag, named places only, within radius_m of the centre; `out center tags` gives ways a point."""
    by_key: dict = {}
    for k, v in C.overpass_filters(keys):
        by_key.setdefault(k, []).append(v)
    around = f"(around:{int(radius_m)},{lat:.6f},{lon:.6f})"
    lines = []
    for k, vals in by_key.items():
        exact = [v for v in vals if not v.startswith("~")]
        regex = [v[1:] for v in vals if v.startswith("~")]
        if exact:
            sel = f'["{k}"="{exact[0]}"]' if len(exact) == 1 else f'["{k}"~"^({"|".join(sorted(exact))})$"]'
            lines.append(f'  nwr{sel}["name"]{around};')
        for r in regex:
            lines.append(f'  nwr["{k}"~"{r}",i]["name"]{around};')
    return f"[out:json][timeout:{timeout}][maxsize:268435456];\n(\n" + "\n".join(lines) + "\n);\nout center tags;"


def endpoint_for(country_code: str) -> str:
    return ENDPOINTS["na"] if (country_code or "us").lower() in NA_COUNTRIES else ENDPOINTS["main"]


def overpass(query: str, endpoint: str, ttl=OVERPASS_TTL, refresh=False, fetch=None, sleep=time.sleep, tries=3) -> dict:
    """POST one query (cached by its text). Returns the JSON. One at a time; 30 s pause after 429 / 406 / 504 (the wiki's rule)."""
    key = hashlib.sha1(f"{endpoint}\n{query}".encode()).hexdigest()[:20]
    path = _cache("overpass", key + ".json")
    hit = _read_json(path)
    if hit and not refresh and time.time() - hit.get("t", 0) < ttl:
        hit["data"]["_cache"] = {"hit": True, "age_h": round((time.time() - hit["t"]) / 3600, 1)}
        return hit["data"]
    fetch = fetch or http
    last = ""
    with OneAtATime():
        for attempt in range(tries):
            status, _, body = fetch(endpoint, data={"data": query}, timeout=150)
            if status == 200:
                try:
                    data = json.loads(body)
                except ValueError:
                    last = "the map server sent something that is not JSON"
                else:
                    if "remark" in data and not data.get("elements") and "runtime error" in str(data.get("remark", "")):
                        last = "the map server stopped the query: " + str(data["remark"])[:160]
                    else:
                        _write_json(path, {"t": time.time(), "endpoint": endpoint, "query": query, "data": data})
                        data["_cache"] = {"hit": False, "age_h": 0}
                        return data
            else:
                last = f"the map server answered HTTP {status}" + (" (busy)" if status in (429, 504) else "")
            if attempt < tries - 1:
                sleep(30 * (attempt + 1))
    if hit:                                          # an old answer beats no answer: say how old
        hit["data"]["_cache"] = {"hit": True, "stale": True, "age_h": round((time.time() - hit["t"]) / 3600, 1)}
        return hit["data"]
    raise SourceError(last + "; try again later (the free server is sometimes busy)")


# ------------------------------------------------------------------------------------------------ one element -> one plain lead
def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def phone_parts(raw: str):
    """'+1-970-224-9791;+1 970 ...' -> ('(970) 224-9791', '+19702249791'). Non-US numbers keep their digits."""
    if not raw:
        return "", ""
    first = re.split(r"[;,/]| or ", raw)[0].strip()
    ext = ""
    m = re.search(r"(?:ext\.?|x)\s*(\d{1,6})\s*$", first, re.I)
    if m:
        ext, first = m.group(1), first[:m.start()].strip()
    digits = re.sub(r"\D", "", first)
    if first.startswith("+") and not digits.startswith("1"):
        return first, "+" + digits
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        return first, ("+" + digits) if digits else ""
    disp = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}" + (f" ext. {ext}" if ext else "")
    return disp, "+1" + digits


def clean_url(raw: str) -> str:
    u = (raw or "").strip().split(";")[0].strip()
    if not u:
        return ""
    if not re.match(r"^[a-z][a-z0-9+.-]*://", u, re.I):
        u = "http://" + u.lstrip("/")
    return u if re.match(r"^https?://[^\s/$.?#].[^\s]*$", u, re.I) else ""


def address_of(tags: dict, place: dict) -> dict:
    a = {k: tags.get(f"addr:{k}", "") for k in ("housenumber", "street", "unit", "city", "state", "postcode")}
    a["unit"] = a["unit"] or tags.get("addr:suite", "")
    a["city_guess"] = not a["city"]
    a["city"] = a["city"] or place.get("city", "")
    a["state"] = a["state"] or place.get("state_code", "")
    street = " ".join(x for x in (a["housenumber"], a["street"]) if x)
    if street and a["unit"]:
        street += f", {'Suite ' + a['unit'] if a['unit'].isalnum() and len(a['unit']) < 6 else a['unit']}"
    tail = " ".join(x for x in (a["state"], a["postcode"].split("-")[0] if a["postcode"] else "") if x)
    a["line"] = ", ".join(x for x in (street, a["city"], tail) if x)
    a["street_line"] = street
    a["has_street"] = bool(a["street"])
    return a


def slug(text: str, n=40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower().replace("&", " and ").replace("'", "")).strip("-")
    return (s[:n].rstrip("-")) or "business"


def normalize(el: dict, place: dict, wanted=C.DEFAULT_KEYS, source="overpass"):
    """One Overpass / extract element -> a lead dict, or None (no name, a chain, closed, not a wanted trade)."""
    tags = el.get("tags") or {}
    name = (tags.get("name") or "").strip()
    if not name or any(k in tags for k in ("disused:shop", "disused:amenity", "was:shop", "end_date")) or tags.get("opening_hours") == "closed":
        return None
    cat = C.classify(tags, wanted)
    if not cat or C.is_chain(tags):
        return None
    lat = el.get("lat", (el.get("center") or {}).get("lat"))
    lon = el.get("lon", (el.get("center") or {}).get("lon"))
    if lat is None or lon is None:
        return None
    cobj = C.BY_KEY[cat]
    disp, e164 = phone_parts(tags.get("phone") or tags.get("contact:phone") or tags.get("contact:mobile") or "")
    site = clean_url(tags.get("website") or tags.get("contact:website") or tags.get("url") or "")
    addr = address_of(tags, place)
    otype, oid = el.get("type", "node"), el.get("id", 0)
    social = {k: tags.get(f"contact:{k}") or tags.get(k) or "" for k in ("facebook", "instagram")}
    return {
        "id": f"{otype[0]}{oid}", "osm": f"{otype}/{oid}", "osm_url": f"https://www.openstreetmap.org/{otype}/{oid}",
        "name": name, "slug": slug(name), "category": cat, "category_label": cobj.label, "template": cobj.template,
        "lat": round(float(lat), 6), "lon": round(float(lon), 6),
        "distance_km": round(haversine_km(place["lat"], place["lon"], float(lat), float(lon)), 2),
        "address": addr, "phone": disp, "phone_e164": e164,
        "email": (tags.get("email") or tags.get("contact:email") or "").split(";")[0].strip(),
        "website": site, "facebook": social["facebook"], "instagram": social["instagram"],
        "opening_hours": tags.get("opening_hours", ""), "cuisine": tags.get("cuisine", "").replace("_", " ").replace(";", ", "),
        "description": tags.get("description", "")[:240], "tag_count": len(tags), "source": source,
        "check_date": tags.get("check_date") or tags.get("survey:date") or "",
    }


def find(place: dict, radius_km: float, keys, endpoint=None, refresh=False, fetch=None, sleep=time.sleep):
    """The raw lead list (unscored) for a place, deduplicated by name + street. Returns (leads, meta)."""
    endpoint = endpoint or endpoint_for(place.get("country_code"))
    q = build_query(place["lat"], place["lon"], radius_km * 1000, keys)
    data = overpass(q, endpoint, refresh=refresh, fetch=fetch, sleep=sleep)
    els = data.get("elements") or []
    leads, seen, skipped = [], set(), {"no_name_or_closed": 0, "chain": 0, "other_trade": 0, "duplicate": 0}
    for el in els:
        tags = el.get("tags") or {}
        lead = normalize(el, place, keys)
        if lead is None:
            if tags.get("name") and C.classify(tags, keys) and C.is_chain(tags):
                skipped["chain"] += 1
            elif tags.get("name") and not C.classify(tags, keys):
                skipped["other_trade"] += 1
            else:
                skipped["no_name_or_closed"] += 1
            continue
        host = (urllib.parse.urlsplit(lead["website"]).hostname or "").removeprefix("www.") if lead["website"] else ""
        keys_seen = {(lead["name"].lower(), "street", lead["address"]["street"].lower())}
        if host:
            keys_seen.add((lead["name"].lower(), "site", host))       # two map points of one business with one website
        if lead["phone_e164"]:
            keys_seen.add((lead["name"].lower(), "phone", lead["phone_e164"]))
        if keys_seen & seen:
            skipped["duplicate"] += 1
            continue
        seen |= keys_seen
        leads.append(lead)
    osm_base = (data.get("osm3s") or {}).get("timestamp_osm_base", "")
    meta = {"endpoint": endpoint, "elements": len(els), "kept": len(leads), "skipped": skipped, "osm_base": osm_base,
            "cache": data.get("_cache", {}), "attribution": ATTRIBUTION, "query": q}
    return leads, meta
