"""Overture Maps check of the website leads (lead 2026-11-21: 'about half the no-website leads already have a working site').

    python tools/web_leads_overture.py                 latest Overture release -> cache -> check every lead -> write agency/leads/towns/*.json
    python tools/web_leads_overture.py --no-http       verdicts from the data only (no site is fetched; site_down needs --http)
    python tools/web_leads_overture.py --places FILE   use a local places parquet (tests: tests/fixtures/overture/places.parquet)

Free: DuckDB + anonymous S3 (overturemaps-us-west-2, Overture Maps Foundation, CDLA-Permissive-2.0 / ODbL by source). Per lead:
  web.verdict  has_site   Overture lists a website whose domain shares a word with the business name AND it answers HTTP 200
               site_down  the domain matches the name but the site does not answer 200 (DNS error, 4xx/5xx, timeout)
               none       no website, or only a site that isn't theirs (Facebook, Yelp, an ordering page)
  has_site -> lead.website = the url (the factory, the caller portal and the first-100 list skip it; it goes to agency/leads/redesign.json)
  phone    -> filled from Overture when the lead has none (phone_src "overture")
New leads: Overture places in the 16 town boxes with a phone and NO website, open, not a chain / brand, in a trade we sell to
(non-businesses like churches, parks, schools, offices of government are dropped); id "ovt-<id>", source "overture".
Never copied: Overture emails (no email goes onto a public page from here).
"""
from __future__ import annotations

import concurrent.futures as cf
import datetime as dt
import json
import math
import os
import re
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import site_factory as F  # noqa: E402

TOWNS_DIR = os.path.join(F.WEB, "leads", "towns")
CACHE = os.path.join(ROOT, "scratch", "overture")
REDESIGN = os.path.join(F.WEB, "leads", "redesign.json")
BUCKET = "https://overturemaps-us-west-2.s3.us-west-2.amazonaws.com/"
CREDIT = "Data (c) OpenStreetMap contributors (ODbL) and Overture Maps Foundation (CDLA-Permissive-2.0 / ODbL), overturemaps.org"
MATCH_M = 150                      # a lead and an Overture place this close with a similar name = the same business
NOT_THEIRS = ("facebook.", "instagram.", "yelp.", "linktr.ee", "doordash.", "grubhub.", "ubereats.", "toasttab.", "google.", "tripadvisor.",
              "nextdoor.", "twitter.", "x.com", "tiktok.", "youtube.", "booksy.", "vagaro.", "styleseat.", "schedulicity.", "square.site",
              "wixsite.", "godaddysites.", "business.site", "mapquest.", "yellowpages.", "bbb.org", "chamberofcommerce.", "opentable.", "seamless.")
STOP = {"the", "and", "of", "llc", "inc", "co", "company", "corp", "ltd", "md", "at", "by", "a", "an", "&", "s", "shop", "store", "service", "services"}

# Overture basic_category -> the factory's niche (anything else is not a business we sell to: dropped)
NICHE = {
    "home_service": "trades", "building_or_construction_service": "trades", "technical_service": "trades",
    "personal_or_beauty_service": "beauty", "personal_care_and_beauty_store": "beauty",
    "automotive_service": "auto",
    "dental_clinic": "health", "health_care": "health", "behavioral_or_mental_health_clinic": "health", "specialized_health_care": "health",
    "complementary_and_alternative_medicine": "health", "primary_care_or_general_clinic": "health", "physical_medicine_and_rehabilitation": "health",
    "vision_or_eye_care_clinic": "health", "medical_service": "health", "wellness_service": "health",
    "restaurant": "food", "casual_eatery": "food", "bar": "food", "cafe": "food", "bakery": "food", "coffee_shop": "food",
    "sport_or_fitness_facility": "gym", "gym": "gym",
    "attorney_or_law_firm": "pro", "legal_service": "pro", "professional_service": "pro", "design_service": "pro", "media_service": "pro",
    "travel_service": "pro", "financial_service": "pro",
    "laundry_service": "services", "event_or_party_service": "services", "printing_service": "services", "animal_or_pet_service": "services",
    "fashion_and_apparel_store": "retail", "flowers_and_gifts_store": "retail", "specialty_store": "retail", "second_hand_store": "retail",
    "electronics_store": "retail", "sporting_goods_store": "retail", "hardware_home_and_garden_store": "retail", "food_and_beverage_store": "retail",
}
NICHE_NAME = {"food": "Restaurant / food", "trades": "Contractor / trades", "beauty": "Salon / beauty", "auto": "Auto", "gym": "Gym / fitness",
              "health": "Health", "pro": "Professional services", "services": "Local services", "retail": "Shop"}


# ---------------------------------------------------------------- data
def latest_release(http_get=None) -> str:
    get = http_get or (lambda u: urllib.request.urlopen(u, timeout=30).read().decode())
    xml = get(BUCKET + "?list-type=2&prefix=release/&delimiter=/")
    rel = sorted(re.findall(r"<Prefix>release/([0-9]{4}-[0-9]{2}-[0-9]{2}\.[0-9]+)/</Prefix>", xml))
    if not rel:
        raise RuntimeError("no Overture release listed")
    return rel[-1]


def fetch(release: str, bbox=(39.04, -77.77, 39.68, -76.76)) -> str:
    """the places in one box -> scratch/overture/places_<release>.parquet (about 100k rows, a few seconds). Anonymous S3."""
    import duckdb
    os.makedirs(CACHE, exist_ok=True)
    out = os.path.join(CACHE, f"places_{release}.parquet")
    if os.path.exists(out):
        return out
    for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):     # anonymous: never send a key
        os.environ.pop(k, None)
    s, w, n, e = bbox
    c = duckdb.connect()
    c.execute("INSTALL httpfs; LOAD httpfs; CREATE SECRET anon (TYPE s3, PROVIDER config, KEY_ID '', SECRET '', REGION 'us-west-2');")
    c.execute(f"""COPY (SELECT id, names.primary AS name, websites, phones, basic_category AS cat, taxonomy.primary AS tax,
      addresses[1].freeform AS street, addresses[1].locality AS town, addresses[1].postcode AS zip, addresses[1].region AS region,
      (bbox.xmin+bbox.xmax)/2 AS lon, (bbox.ymin+bbox.ymax)/2 AS lat, confidence, operating_status, brand.wikidata AS brand_wd
      FROM read_parquet('s3://overturemaps-us-west-2/release/{release}/theme=places/type=place/*')
      WHERE bbox.xmin BETWEEN {w} AND {e} AND bbox.ymin BETWEEN {s} AND {n}) TO '{out}' (FORMAT parquet)""")
    return out


def load_places(path: str) -> list:
    import duckdb
    c = duckdb.connect()
    cols = [d[0] for d in c.execute(f"DESCRIBE SELECT * FROM read_parquet('{path}')").fetchall()]
    want = ["id", "name", "websites", "phones", "cat", "tax", "street", "town", "zip", "region", "lon", "lat", "confidence", "operating_status", "brand_wd"]
    sel = ", ".join(x if x in cols else f"NULL AS {x}" for x in want)
    return [dict(zip(want, r)) for r in c.execute(f"SELECT {sel} FROM read_parquet('{path}')").fetchall()]


# ---------------------------------------------------------------- matching
def words(name: str) -> list:
    return [w for w in re.findall(r"[a-z0-9]+", str(name or "").lower().replace("'", "")) if w not in STOP]


# words every second business has: sharing only these is not the same business ('Oxygen Salon & Day Spa' != 'Perez Salon & Day Spa')
GENERIC = set("""salon spa day nail nails hair beauty barber barbershop auto body repair tire tires car cars care center centre clinic dental
dentistry family health medical grill pizza pizzeria restaurant cafe kitchen bar pub house deli market food foods sub subs bakery coffee
tea china chinese thai mexican indian italian sushi grocery liquor liquors wine gym fitness studio martial arts yoga dance cleaners cleaning
laundry dry pet pets animal hospital vet law office group associates insurance tax home homes design construction plumbing electric
electrical heating cooling hvac roofing landscaping lawn services store shop shops boutique gallery jewelry mart express plus new best
main street rockville frederick gaithersburg columbia germantown hagerstown westminster maryland md city""".split())


def same_name(a: str, b: str) -> bool:
    x, y = set(words(a)), set(words(b))
    if not x or not y:
        return False
    ca, cb = "".join(words(a)), "".join(words(b))
    if len(ca) >= 5 and (ca in cb or cb in ca) and set(words(a if len(ca) <= len(cb) else b)) - GENERIC:           # 'BLT Grill' / 'BLT Grill Rockville'
        return True
    shared = x & y
    return len(shared) / len(x | y) >= 0.5 and bool(shared - GENERIC)


def strict_name(a: str, b: str) -> bool:
    """for copying a PHONE: the name is contained in the other, or most of the distinctive words are shared"""
    ca, cb = "".join(words(a)), "".join(words(b))
    if len(ca) >= 5 and (ca in cb or cb in ca) and set(words(a if len(ca) <= len(cb) else b)) - GENERIC:
        return True
    dx, dy = set(words(a)) - GENERIC, set(words(b)) - GENERIC
    return bool(dx and dy) and len(dx & dy) / max(len(dx), len(dy)) >= 0.67


def meters(lat1, lon1, lat2, lon2) -> float:
    k = math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot((lat2 - lat1) * 111_320, (lon2 - lon1) * 111_320 * k)


class Grid:
    def __init__(self, places, cell=0.003):
        self.cell, self.g = cell, {}
        for p in places:
            if p.get("lat") is None or p.get("lon") is None:
                continue
            self.g.setdefault((int(p["lat"] / cell), int(p["lon"] / cell)), []).append(p)

    def near(self, lat, lon):
        i, j = int(lat / self.cell), int(lon / self.cell)
        for a in (i - 1, i, i + 1):
            for b in (j - 1, j, j + 1):
                yield from self.g.get((a, b), [])


def match(lead: dict, grid: Grid):
    lat, lon = lead.get("lat"), lead.get("lon")
    if lat is None or lon is None:
        return None
    best = None
    for p in grid.near(lat, lon):
        d = meters(lat, lon, p["lat"], p["lon"])
        if d <= MATCH_M and same_name(lead.get("name"), p.get("name")) and (best is None or d < best[0]):
            best = (d, p)
    return best[1] if best else None


def host(url: str) -> str:
    h = re.sub(r"^[a-z]+://", "", str(url or "").strip().lower()).split("/")[0].split(":")[0]
    return h[4:] if h.startswith("www.") else h


def domain_is_theirs(url: str, name: str) -> bool:
    """the domain shares a word with the name (pearlfectiondentistry.com ~ 'Pearlfection Dentistry'); social / booking / ordering pages don't count"""
    h = host(url)
    if not h or any(x in h for x in NOT_THEIRS):
        return False
    label = re.sub(r"[^a-z0-9]", "", h.rsplit(".", 1)[0])
    ws = [w for w in words(name) if len(w) >= 4 and w not in GENERIC]     # 'deltaautobody.com' is not 'Calfax Auto Body'

    joined = "".join(words(name))
    return any(w in label for w in ws) or (len(label) >= 5 and label in joined) or (len(joined) >= 5 and joined in label)


UP_CODES = {200, 202, 401, 403, 409, 429}      # answered: 401/403/429 = the site is there but turns away robots (not 'down')


def _get(u, timeout):
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
                                                           "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1", "Accept": "text/html"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except urllib.error.URLError as e:
        return "dns" if "Name or service not known" in str(e.reason) or "getaddrinfo" in str(e.reason) or "nodename" in str(e.reason) else type(e.reason).__name__
    except Exception as e:                       # noqa: BLE001 - timeout, reset: retried / 'down'
        return type(e).__name__


def http_ok(url: str, timeout=8) -> tuple:
    """(up, status): the listed page, then the site's home page over https and http (a deep link can 404 while the site is fine)"""
    u = url if re.match(r"^https?://", url or "") else "http://" + str(url)
    tries = [u, "https://" + host(u) + "/", "http://" + host(u) + "/"]
    st = None
    for t in dict.fromkeys(tries):
        st = _get(t, timeout)
        if st in UP_CODES:
            return True, st
        if st == "dns":
            return False, st
    return False, st


def phone10(p) -> str:
    d = re.sub(r"\D", "", str(p or ""))
    d = d[1:] if len(d) == 11 and d.startswith("1") else d
    return d if len(d) == 10 and d[0] not in "01" else ""


def fmt_phone(d: str) -> str:
    return f"({d[:3]}) {d[3:6]}-{d[6:]}"


def chainish(p: dict) -> bool:
    return bool(p.get("brand_wd")) or F.chain_of(p.get("name"))


# ---------------------------------------------------------------- the run
def run(places: list, towns_dir: str = TOWNS_DIR, checker=http_ok, today=None, write=True, threads=32) -> dict:
    today = today or dt.date.today().isoformat()
    grid = Grid(places)
    files = sorted(f for f in os.listdir(towns_dir) if f.endswith(".json"))
    docs = {f: json.load(open(os.path.join(towns_dir, f), encoding="utf-8")) for f in files}
    from tools.web_leads import TOWNS
    used, todo = set(), []                       # Overture ids already tied to a lead; (lead, url) pairs to fetch
    for f, d in docs.items():
        for L in d.get("leads", []):
            if str(L.get("id", "")).startswith("ovt-"):
                used.add(L["id"][4:])
                continue
            p = match(L, grid)
            web = {"verdict": "none", "src": "overture", "checked": today}
            if p:
                used.add(p["id"])
                if not phone10(L.get("phone")) and strict_name(L.get("name"), p.get("name")):
                    ph = next((phone10(x) for x in (p.get("phones") or []) if phone10(x)), "")
                    if ph:
                        L["phone"], L["phone_src"] = fmt_phone(ph), "overture"
                site = next((u for u in (p.get("websites") or []) if domain_is_theirs(u, L.get("name"))), "")
                if site:
                    web["url"] = site
                    todo.append((L, site))
            L["web"] = web
    # the HTTP check, in parallel (one GET per site)
    if todo:
        with cf.ThreadPoolExecutor(max_workers=threads) as ex:
            for (L, site), (ok, st) in zip(todo, ex.map(lambda t: checker(t[1]), todo)):
                L["web"].update({"verdict": "has_site" if ok else "site_down", "status": st})
                if ok:
                    L["website"] = site
    # new no-website places with a phone, per town box
    have_names = [(L.get("lat"), L.get("lon"), L.get("name")) for d in docs.values() for L in d.get("leads", [])]
    new_by_file, dropped = {}, {"chain": 0, "not a business we sell to": 0, "closed": 0, "has a website": 0, "no phone": 0}
    town_file = {d.get("town"): f for f, d in docs.items()}
    for p in places:
        if p["id"] in used or p.get("lat") is None:
            continue
        town = next((t for t, (s, w, n, e) in TOWNS.items() if t in town_file and s <= p["lat"] <= n and w <= p["lon"] <= e), None)
        if not town:
            continue
        if p.get("websites"):
            dropped["has a website"] += 1
            continue
        ph = next((phone10(x) for x in (p.get("phones") or []) if phone10(x)), "")
        if not ph:
            dropped["no phone"] += 1
            continue
        if p.get("operating_status") not in (None, "open"):
            dropped["closed"] += 1
            continue
        niche = NICHE.get(p.get("cat") or "")
        if not niche or not str(p.get("name") or "").strip() or (p.get("confidence") or 0) < 0.4:
            dropped["not a business we sell to"] += 1
            continue
        if chainish(p):
            dropped["chain"] += 1
            continue
        if any(la is not None and meters(la, lo, p["lat"], p["lon"]) <= MATCH_M and same_name(nm, p["name"]) for la, lo, nm in have_names
               if la is not None and abs(la - p["lat"]) < 0.002):
            continue
        street = str(p.get("street") or "").strip()[:80]
        zipc = (re.match(r"\d{5}", str(p.get("zip") or "")) or [""])[0]
        kind = str(p.get("tax") or p.get("cat") or "").replace("_", " ")
        L = {"id": "ovt-" + p["id"][:24], "name": str(p["name"]).strip()[:80], "niche": {"gym": "fitness", "trades": "contractor"}.get(niche, niche),
             "niche_name": NICHE_NAME[niche], "kind": "overture=" + str(p.get("cat")), "town": town, "city": town, "state": "MD",
             "phone": fmt_phone(ph), "email": "", "street": street, "zip": zipc,
             "address": (street + ", " + town + (" MD " + zipc if zipc else ""))[:120] if street else "", "addr_src": "overture" if street else "",
             "lat": round(p["lat"], 6), "lon": round(p["lon"], 6), "mailable": bool(re.match(r"\d+\w?\s+\S+", street) and zipc), "hours": "",
             "facebook": False, "category": kind[:40], "score": 6 + (2 if street else 0), "heat": "hot" if street else "warm",
             "why": ["no website (Overture Maps)", "a phone to call"] + (["a street address (real storefront)"] if street else []),
             "source": "overture", "web": {"verdict": "none", "src": "overture", "checked": today}}
        new_by_file.setdefault(town_file[town], []).append(L)
        have_names.append((L["lat"], L["lon"], L["name"]))
    counts = {"leads": 0, "has_site": 0, "site_down": 0, "none": 0, "phone_filled": 0, "new": 0, "new_by_town": {}, "dropped_new": dropped}
    redesign = []
    for f, d in docs.items():
        d["leads"] += new_by_file.get(f, [])
        d["license"] = CREDIT
        for L in d["leads"]:
            counts["leads"] += 1
            v = (L.get("web") or {}).get("verdict", "none")
            counts[v] = counts.get(v, 0) + 1
            counts["phone_filled"] += L.get("phone_src") == "overture"
            if v == "has_site":
                redesign.append({"id": L["id"], "name": L["name"], "town": L.get("town"), "niche": L.get("niche"), "phone": phone10(L.get("phone")),
                                 "url": L.get("website"), "why": "has a working site: offer a redesign / speed + Google audit, not a first site"})
        if new_by_file.get(f):
            counts["new_by_town"][d.get("town")] = len(new_by_file[f])
            counts["new"] += len(new_by_file[f])
        if write:
            with open(os.path.join(towns_dir, f), "w", encoding="utf-8") as fh:
                json.dump(d, fh, indent=1)
                fh.write("\n")
    if write:
        with open(REDESIGN if towns_dir == TOWNS_DIR else os.path.join(towns_dir, "..", "redesign.json"), "w", encoding="utf-8") as fh:
            json.dump({"v": 1, "kind": "redesign-list", "built": today, "credit": CREDIT, "count": len(redesign),
                       "note": "leads that already have a working site: not for the 'we built you a site' call; a redesign / audit offer instead",
                       "leads": sorted(redesign, key=lambda r: (r["town"] or "", r["name"]))}, fh, indent=1)
            fh.write("\n")
    return counts


def main(argv) -> int:
    if "--places" in argv:
        path = argv[argv.index("--places") + 1]
    else:
        rel = latest_release()
        print(f"Overture release {rel}")
        path = fetch(rel)
    places = load_places(path)
    checker = (lambda u: (False, "skipped")) if "--no-http" in argv else http_ok
    c = run(places, checker=checker)
    print(json.dumps(c, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
