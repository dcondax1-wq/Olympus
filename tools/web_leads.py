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
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "tools", "web_public", "agency", "leads", "leads.json")
UA = "olympus-web-leads/1.0 (small-business website lead finder; one query per town)"
SERVERS = ("https://overpass-api.de/api/interpreter", "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
           "https://overpass.kumi.systems/api/interpreter")
# 3 towns across Maryland (west, centre, bay); the owner's county is unknown: any town is a setting (--town NAME --bbox S,W,N,E)
TOWNS = {"Frederick": (39.380, -77.470, 39.470, -77.360), "Annapolis": (38.940, -76.540, 39.000, -76.460),
         "Hagerstown": (39.610, -77.760, 39.670, -77.690)}
STATE = "US-MD"
GAP_S = 1.1
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
OFFER = {"food": "1-page site: menu, hours, map, online-order link + Google profile",
         "contractor": "lead site: services, service area, quote form, reviews",
         "beauty": "booking site: services + prices, online booking, Instagram feed",
         "auto": "service site: services + prices, book a repair, hours, map",
         "fitness": "class site: schedule, trial-pass form, coaches",
         "health": "patient site: services, new-patient form, insurance, map",
         "pro": "trust site: services, about, contact form, reviews",
         "services": "1-page site: services + prices, hours, map, contact form",
         "retail": "shop site: hours, map, what's in stock, Google profile"}
TRADE = {"food": "restaurant", "beauty": "salon", "contractor": "contractor", "health": "medical", "auto": "auto", "fitness": "fitness",
         "retail": "retail", "services": "retail", "pro": "professional"}           # agency/callrules.json trades (the call script)
VALUE = {"contractor": 2, "health": 2, "auto": 1, "beauty": 1, "fitness": 1, "pro": 1, "food": 0, "services": 0, "retail": 0}
NAME = {"food": "Restaurant / food", "contractor": "Contractor / trades", "beauty": "Salon / beauty", "auto": "Auto",
        "fitness": "Gym / fitness", "health": "Health", "pro": "Professional services", "services": "Local services", "retail": "Shop"}


def parts(bbox=None, town="") -> list:
    """The Overpass queries for one town: one per business type (a single union times out on the public mirrors' gateways)."""
    amen = "|".join(sorted({v for n, k, rx in NICHES if k == "amenity" for v in re.findall(r"[a-z_]+", rx)}))
    if bbox:
        where, head = "(" + ",".join(f"{x:.4f}" for x in bbox) + ")", ""
    else:
        where = "(area.t)"
        head = (f'area["ISO3166-2"="{STATE}"]["admin_level"="4"]->.st;'
                f'area["name"="{town}"]["boundary"~"^(administrative|census)$"](area.st)->.t;')
    sel = ['["shop"]["name"]', '["craft"]["name"]', '["office"]["name"]', '["healthcare"]["name"]',
           '["leisure"~"^(fitness_centre|sports_centre|dance)$"]["name"]', f'["amenity"~"^({amen})$"]["name"]']
    return [f"[out:json][timeout:50];{head}nwr{x}{where};out center tags;" for x in sel]


def query(town: str, bbox=None) -> str:                        # kept for the docs / tests: the first part
    return parts(bbox, town)[0]


def ask(q: str, http=None, servers=SERVERS, sleep=time.sleep, say=print):
    """One Overpass query: each public server once, in order, >= 1 s apart. -> (elements, server) or (None, '')."""
    body = urllib.parse.urlencode({"data": q}).encode()
    for i, url in enumerate(servers):
        if i:
            sleep(GAP_S)
        host = url.split("/")[2]
        try:
            if http:
                st, raw = http(url, body)
            else:
                req = urllib.request.Request(url, data=body, headers={"User-Agent": UA, "Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=90) as r:
                    st, raw = r.status, r.read()
            if st == 200:
                j = json.loads(raw)
                if isinstance(j, dict) and isinstance(j.get("elements"), list):
                    return j["elements"], host
            say(f"  [..] {host} answered {st}")
        except Exception as e:  # noqa: BLE001
            say(f"  [..] {host}: {getattr(e, 'code', '') or e.__class__.__name__}")
    return None, ""


def fetch(town: str, bbox=None, http=None, servers=SERVERS, sleep=time.sleep, say=print) -> dict | None:
    """Every business-type query for one town, 1+ s apart; a part that fails on every server is skipped (said).
    -> {"elements", "_server", "_parts_ok"} or None when no part worked."""
    els, seen, ok, hosts = [], set(), 0, set()
    for i, q in enumerate(parts(bbox, town)):
        if i:
            sleep(GAP_S)
        got, host = ask(q, http, servers, sleep, say)
        if got is None:
            continue
        ok += 1
        hosts.add(host)
        for e in got:
            k = (e.get("type"), e.get("id"))
            if k not in seen:
                seen.add(k)
                els.append(e)
    return {"elements": els, "_server": ", ".join(sorted(hosts)), "_parts_ok": ok} if ok else None


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


def lead_of(el: dict, town: str) -> tuple:
    """(lead dict | None, reason it was left out)"""
    t = el.get("tags") or {}
    name = str(t.get("name") or "").strip()
    if not name:
        return None, "no_name"
    if t.get("brand") or t.get("brand:wikidata") or t.get("operator:wikidata"):
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
    street = " ".join(x for x in (str(t.get("addr:housenumber") or ""), str(t.get("addr:street") or "")) if x).strip()
    city = str(t.get("addr:city") or town)
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
    if VALUE[niche]:
        score += VALUE[niche]
        why.append(f"{NAME[niche].lower()}: customers search for this online")
    heat = "hot" if score >= 8 else "warm" if score >= 6 else "cold"
    typ, osm_id = el.get("type", "node"), el.get("id")
    return {"id": f"osm-{typ[0]}{osm_id}", "name": name[:80], "niche": niche, "niche_name": NAME[niche], "kind": kind, "town": town,
            "city": city[:60], "state": "MD", "phone": phone, "address": (street + (", " + city if street else ""))[:120], "hours": hours,
            "facebook": bool(fb), "trade": TRADE[niche], "category": kind.split("=")[-1].replace("_", " "), "score": score, "heat": heat, "why": why, "offer": OFFER[niche],
            "osm": f"https://www.openstreetmap.org/{typ}/{osm_id}"}, ""


def build(answers: dict, now=None) -> dict:
    """answers = {town: overpass json}. -> the leads.json dict."""
    now = now or dt.datetime.now(dt.timezone.utc)
    leads, towns, skipped = [], [], {}
    seen = set()
    for town, j in answers.items():
        n0 = len(leads)
        for el in (j or {}).get("elements") or []:
            L, why = lead_of(el, town)
            if not L:
                skipped[why] = skipped.get(why, 0) + 1
                continue
            key = (L["name"].lower(), L["phone"] or L["address"])
            if key in seen:
                skipped["duplicate"] = skipped.get("duplicate", 0) + 1
                continue
            seen.add(key)
            leads.append(L)
        mine = leads[n0:]
        towns.append({"town": town, "state": "MD", "businesses": len((j or {}).get("elements") or []), "leads": len(mine),
                      "hot": sum(1 for x in mine if x["heat"] == "hot"), "server": (j or {}).get("_server", "")})
    leads.sort(key=lambda x: (-x["score"], x["town"], x["name"]))
    return {"v": 1, "kind": "web_leads", "demo": False, "fetched": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": "OpenStreetMap via the public Overpass API (one query per town)", "license": LICENSE,
            "about": "Businesses on OpenStreetMap with no website tag. OSM can be out of date: check the business before you call.",
            "towns": towns, "skipped": skipped, "leads": leads}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--town", action="append", help="a Maryland town / city (repeat); default: " + ", ".join(TOWNS))
    ap.add_argument("--bbox", help="south,west,north,east for ONE --town not in the presets (faster than the name lookup)")
    ap.add_argument("--from-file", help="an Overpass JSON answer to use instead of the network (one --town)")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)
    towns = a.town or list(TOWNS)
    answers = {}
    if a.from_file:
        with open(a.from_file, encoding="utf-8") as fh:
            answers[towns[0]] = json.load(fh)
    else:
        for i, t in enumerate(towns):
            if i:
                time.sleep(GAP_S)
            print(f"[..] {t}, MD: asking OpenStreetMap (Overpass) once")
            bb = tuple(float(x) for x in a.bbox.split(",")) if a.bbox and len(towns) == 1 else TOWNS.get(t)
            j = fetch(t, bb)
            if j is None:
                print(f"  [!!] {t}: every Overpass server failed; skipped")
                continue
            answers[t] = j
    if not answers:
        print("[!!] nothing fetched: leads.json left as it was")
        return 2
    out = build(answers)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
    for t in out["towns"]:
        print(f"[OK] {t['town']}: {t['businesses']} businesses on the map, {t['leads']} with no website ({t['hot']} hot) via {t['server']}")
    print(f"[OK] {len(out['leads'])} leads -> {os.path.relpath(a.out, ROOT)}; left out: {out['skipped']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
