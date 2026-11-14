"""AGENCY, the website machine (agency/, tools/web_public/agency/, docs/AGENCY.md), 2026-11-14.

  a. lead finder: trades and chains, the Overpass query, one element -> one lead, phones, hours, dedupe, the cache / the
     30 s pause / one-at-a-time lock, the city search (cached, 1 per second), the site audit on fixture pages (no network),
     the conclusive-only rule for 'dead', the score and the day's list
  b. site generator: every template builds valid HTML with no external hotlink, the self-check passes, the zip, the config
  c. pitch kit: the one-pager, the CAN-SPAM email (sender, postal address, ad line, opt-out), the 30-second opener
  d. the CRM page (tools/web_public/agency/): the AGORA kit rules, the pure core in node, then Chromium at 390 x 844
    python -X utf8 -m tests.test_agency            (--fast: a-c and the static / node parts of d, no browser)
Read only for the repo: every write goes to a temp folder (AGENCY_CACHE / AGENCY_OUT / AGENCY_CONFIG point there), nothing is fetched.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import time

TMP = tempfile.mkdtemp(prefix="agency-test-")
os.environ["AGENCY_CACHE"] = os.path.join(TMP, "cache")
os.environ["AGENCY_OUT"] = os.path.join(TMP, "out")
os.environ["AGENCY_CONFIG"] = os.path.join(TMP, "config.json")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests import agora_kit as AK  # noqa: E402

from agency import audit as A  # noqa: E402
from agency import categories as C  # noqa: E402
from agency import config as CFG  # noqa: E402
from agency import hours as H  # noqa: E402
from agency import leads as L  # noqa: E402
from agency import osm  # noqa: E402

check = AK.check
PLACE = {"lat": 40.5872, "lon": -105.077, "city": "Fort Collins", "state_code": "CO", "country_code": "us", "name": "Fort Collins, CO"}


def el(i, tags, kind="node", lat=40.58, lon=-105.08, center=False):
    e = {"type": kind, "id": i, "tags": tags}
    if center:
        e["center"] = {"lat": lat, "lon": lon}
    else:
        e.update(lat=lat, lon=lon)
    return e


ELEMENTS = [
    el(1, {"name": "Cinco Brothers", "shop": "hairdresser", "hairdresser": "barber", "phone": "+1-970-694-2949", "addr:housenumber": "120", "addr:street": "West Olive Street",
           "opening_hours": "Tu-Fr 09:00-18:00; Sa 08:00-15:00"}),
    el(2, {"name": "Great Clips", "shop": "hairdresser", "brand": "Great Clips", "brand:wikidata": "Q5598967", "phone": "+1 970 224 2664"}),
    el(3, {"name": "Floyd's 99 Barbershop", "shop": "hairdresser", "note": "this is a franchise/chain shop"}),
    el(4, {"name": "Allen Plumbing & Heating", "craft": "plumber", "website": "www.allenservice.com", "phone": "970.482.1234 ext 12", "addr:street": "Main St",
           "addr:housenumber": "9"}, kind="way", center=True),
    el(5, {"name": "Wild Mane Salon", "shop": "hairdresser", "female": "yes", "phone": "(970) 226-1104"}),
    el(6, {"name": "Wild Mane Salon", "shop": "hairdresser", "female": "yes", "phone": "(970) 226-1104"}, lat=40.59),     # the same place twice
    el(7, {"shop": "hairdresser"}),                                                                                          # no name
    el(8, {"name": "Old Shop", "shop": "car_repair", "disused:shop": "car_repair"}),
    el(9, {"name": "Bike Hub", "shop": "bicycle"}),
    el(10, {"name": "Irwin Family Chiropractic", "healthcare": "alternative", "healthcare:speciality": "Chiropractic", "phone": "+19704728333"}),
    el(11, {"name": "Taqueria Sol", "amenity": "restaurant", "cuisine": "mexican;tacos", "website": "https://facebook.com/taqueriasol"}),
]


def test_leads():
    # --- trades and chains
    check("a. 26 trades, every one has a template and a value 1-10; aliases resolve; an unknown word is refused in plain words",
          len(C.CATEGORIES) == 26 and all(c.template in ("studio", "bloom", "pro", "table", "clinic", "garage", "fresh", "pulse") and 1 <= c.value <= 10 for c in C.CATEGORIES)
          and C.resolve("barbers, hvac,roofing") == ("barber", "hvac", "roofer") and C.resolve("") == C.DEFAULT_KEYS
          and _raises(lambda: C.resolve("barber,unicorns"), "unknown categories: unicorns"))
    check("a. barber vs hair salon: hairdresser=barber, 'barber' in the name or men only = barber; else salon; only the wanted one is kept",
          C.classify({"shop": "hairdresser", "hairdresser": "barber"}) == "barber" and C.classify({"shop": "hairdresser", "name": "Main St Barber Co"}) == "barber"
          and C.classify({"shop": "hairdresser", "male": "yes"}) == "barber" and C.classify({"shop": "hairdresser", "female": "yes"}) == "salon"
          and C.classify({"shop": "hairdresser", "hairdresser": "barber"}, ("salon",)) is None and C.classify({"shop": "bicycle"}) is None
          and C.classify({"healthcare:speciality": "chiropractic;sports"}) == "chiropractor")
    check("a. chains are skipped: brand tags, a franchise note, or a known chain name",
          C.is_chain({"brand:wikidata": "Q1"}) and C.is_chain({"note": "franchise"}) and C.is_chain({"name": "Jiffy Lube #12"}) and not C.is_chain({"name": "Joe's Garage"}))
    q = osm.build_query(40.5872, -105.077, 8000, ("barber", "plumber", "chiropractor"))
    check("a. ONE Overpass union query: named places only, the radius around the centre, ways get a centre point, a case-blind regex for chiropractic",
          q.startswith("[out:json][timeout:90]") and 'nwr["shop"~"^(hairdresser|plumber)$"]["name"](around:8000,40.587200,-105.077000);' in q
          and 'nwr["craft"="plumber"]' in q and '["healthcare:speciality"~"chiropractic",i]' in q and q.rstrip().endswith("out center tags;"), q)
    check("a. North America goes to the free NA instance (the main one asks commercial users to self-host); elsewhere the main one",
          osm.endpoint_for("us") == osm.ENDPOINTS["na"] and osm.endpoint_for("CA") == osm.ENDPOINTS["na"] and osm.endpoint_for("de") == osm.ENDPOINTS["main"])
    # --- phones, urls, addresses, hours
    check("a. phones: +1-970-694-2949 / 970.482.1234 ext 12 / (970) 226-1104 / 19704728333 -> one display form and E.164; a foreign number keeps its digits",
          osm.phone_parts("+1-970-694-2949;+1 970 555 0000") == ("(970) 694-2949", "+19706942949") and osm.phone_parts("970.482.1234 ext 12") == ("(970) 482-1234 ext. 12", "+19704821234")
          and osm.phone_parts("19704728333") == ("(970) 472-8333", "+19704728333") and osm.phone_parts("+44 20 7946 0958")[1] == "+442079460958" and osm.phone_parts("") == ("", ""))
    check("a. websites: 'www.x.com' gets http://, junk is dropped, the first of a list wins", osm.clean_url("www.allenservice.com") == "http://www.allenservice.com"
          and osm.clean_url("not a url") == "" and osm.clean_url("https://a.com;https://b.com") == "https://a.com")
    hp = H.parse("Tu-Fr 09:00-18:00; Sa 08:00-15:00")
    check("a. hours: 'Tu-Fr 09:00-18:00; Sa 08:00-15:00' -> Mon closed, Tue-Fri 9 AM - 6 PM, Sat 8 AM - 3 PM, Sun closed (days no rule names are closed)",
          H.rows(hp) == [("Mon", "Closed"), ("Tue - Fri", "9 AM - 6 PM"), ("Sat", "8 AM - 3 PM"), ("Sun", "Closed")], H.rows(hp))
    more = [H.rows(H.parse(x)) for x in ("24/7", "Mo-Fr 07:30-12:00,13:00-17:00; PH off", "Mo-Fr 07:00-18:00, Sa 08:00-17:00", "Mo-Su 17:00-02:00")]
    check("a. hours: 24/7, a lunch break, the common comma mistake, past midnight; months / sunrise are refused (ok False -> 'Call to confirm' on the site)",
          more[0] == [("Mon - Sun", "Open 24 hours")] and more[1][0] == ("Mon - Fri", "7:30 AM - noon, 1 PM - 5 PM") and more[2][:2] == [("Mon - Fri", "7 AM - 6 PM"), ("Sat", "8 AM - 5 PM")]
          and more[3] == [("Mon - Sun", "5 PM - 2 AM")] and not H.parse("Jan-Mar Mo-Fr 09:00-17:00")["ok"] and not H.parse("sunrise-sunset")["ok"]
          and H.clock(720) == "noon" and H.clock(570) == "9:30 AM" and len(H.schema_spec(hp)) == 5, more)
    # --- elements -> leads (fake Overpass: nothing leaves this computer)
    calls = []

    def fake(url, data=None, timeout=60, headers=None):
        calls.append(url)
        return 200, {}, json.dumps({"osm3s": {"timestamp_osm_base": "2026-11-13T21:22:20Z"}, "elements": ELEMENTS}).encode()

    leads, meta = osm.find(PLACE, 8, C.DEFAULT_KEYS, fetch=fake)
    names = [x["name"] for x in leads]
    check("a. 11 map elements -> 5 leads: chains (brand tag, franchise note), the duplicate, the unnamed, the closed and the bicycle shop are left out, and counted",
          names == ["Cinco Brothers", "Allen Plumbing & Heating", "Wild Mane Salon", "Irwin Family Chiropractic", "Taqueria Sol"]
          and meta["skipped"]["chain"] == 2 and meta["skipped"]["duplicate"] == 1 and meta["kept"] == 5 and meta["osm_base"].startswith("2026-11-13"), (names, meta["skipped"]))
    b = leads[0]
    check("a. a lead carries plain fields: barber, the studio template, a phone in two forms, the street line, hours, distance, its OSM link",
          b["category"] == "barber" and b["template"] == "studio" and b["phone"] == "(970) 694-2949" and b["phone_e164"] == "+19706942949" and b["address"]["line"].startswith("120 West Olive Street, Fort Collins, CO")
          and b["address"]["city_guess"] and b["opening_hours"].startswith("Tu-Fr") and 0 < b["distance_km"] < 3 and b["osm_url"] == "https://www.openstreetmap.org/node/1" and b["id"] == "n1", b)
    check("a. a building (way) takes its centre point; the cuisine reads 'mexican, tacos'", leads[1]["osm"] == "way/4" and leads[1]["lat"] == 40.58 and leads[4]["cuisine"] == "mexican, tacos")
    leads2, meta2 = osm.find(PLACE, 8, C.DEFAULT_KEYS, fetch=fake)
    check("a. the second identical search is answered from the cache: no request", len(calls) == 1 and meta2["cache"].get("hit") and len(leads2) == 5, (calls, meta2["cache"]))
    # --- busy server: 30 s pause, then the answer; one at a time
    seq, slept = [429, 504, 200], []

    def busy(url, data=None, timeout=60, headers=None):
        code = seq.pop(0)
        return code, {}, (json.dumps({"elements": []}).encode() if code == 200 else b"busy")

    got = osm.overpass("[out:json];node(9);out;", "https://example.invalid/api", fetch=busy, sleep=slept.append)
    check("a. a busy server (429, then 504) gets a 30 s, then a 60 s pause (the wiki's rule), then the answer", slept == [30, 60] and got.get("elements") == [] and not seq, slept)
    lock = os.path.join(os.environ["AGENCY_CACHE"], "overpass.lock")
    open(lock, "w").write("1 1")
    t0 = time.time()
    try:
        with osm.OneAtATime(wait=0.5):
            blocked = False
    except osm.SourceError as e:
        blocked = "another copy" in str(e)
    os.utime(lock, (time.time() - 3600, time.time() - 3600))
    with osm.OneAtATime(wait=1):
        stale_ok = True
    check("a. one query at a time: a fresh lock makes a second copy wait and then stop politely; a stale lock (crash) is cleared",
          blocked and stale_ok and not os.path.exists(lock) and time.time() - t0 < 10)
    # --- the city search: cached, at most 1 a second, never a POI list
    geo_calls = []

    def nomi(url, data=None, timeout=60, headers=None):
        geo_calls.append(url)
        return 200, {}, json.dumps([{"lat": "40.5852", "lon": "-105.0844", "display_name": "Fort Collins, Larimer County, Colorado, United States",
                                     "address": {"city": "Fort Collins", "state": "Colorado", "ISO3166-2-lvl4": "US-CO", "country_code": "us"}, "boundingbox": ["40.4", "40.7", "-105.2", "-104.9"]}]).encode()

    g1 = osm.geocode("Fort  Collins, CO", fetch=nomi)
    g2 = osm.geocode("fort collins, co", fetch=nomi)
    check("a. the city search: one request (limit 1, jsonv2), then the cache answers for good; state code and country read from the address",
          len(geo_calls) == 1 and "limit=1" in geo_calls[0] and "format=jsonv2" in geo_calls[0] and g1 == g2 and g1["state_code"] == "CO" and g1["country_code"] == "us" and g1["city"] == "Fort Collins")
    check("a. --center skips the city search; a bad centre is refused", osm.center_from("40.5,-105.1")["lat"] == 40.5 and _raises(lambda: osm.center_from("x"), "--center"))
    src = open(os.path.join(ROOT, "agency", "osm.py"), encoding="utf-8").read() + open(os.path.join(ROOT, "agency", "__init__.py"), encoding="utf-8").read()
    check("a. the house rules are in the code: a User-Agent naming the app (no personal data), 1 request a second for Nominatim, the NA instance, ODbL attribution",
          "OLYMPUS-agency/" in src and "1.1" in src and "ovp.dresel.systems/api-na" in src and "OpenStreetMap contributors" in src and not re.search(r"@[a-z0-9-]+\.(com|net|org)", src.split("UA =")[1].split("\n")[0]))

    # --- the site audit (pure part)
    bad = analyze_fixture(BAD_PAGE, "http://oldshop.example/", elapsed=6.2)
    codes = {i["code"] for i in bad["issues"]}
    check("a. an old site: no HTTPS, no viewport (not for phones), phone not tap-to-call, no button, (c) 2015, FrontPage, old HTML, slow -> all found in plain words",
          codes == {"no_https", "no_viewport", "no_tel", "no_cta", "dated", "old_tool", "old_html", "slow", "no_description"}
          and any("tap-to-call" in i["text"] for i in bad["issues"]) and any("2015" in i["text"] for i in bad["issues"]), sorted(codes))
    good = analyze_fixture(GOOD_PAGE, "https://goodshop.example/", elapsed=0.8)
    check("a. a good site: nothing to fix (facts: https, viewport, tel, a button, this year's (c))", good["issues"] == [] and good["facts"]["https"] and good["facts"]["viewport"] and good["facts"]["tel"] and good["facts"]["cta"], good)
    parked = analyze_fixture("<html><head><title>x</title></head><body>This domain is for sale! Buy this domain today.</body></html>", "https://parked.example/")
    down = A.analyze("", "https://x.example/", status=500)
    check("a. a parked domain and a 500 error are both 'no real website'", "parked" in {i["code"] for i in parked["issues"]} and down["issues"][0]["code"] == "site_down" and "500" in down["issues"][0]["text"])
    soc, go = A.judge_address("https://m.facebook.com/taqueriasol")
    gbp, go2 = A.judge_address("https://joes-garage.business.site/")
    wix, go3 = A.judge_address("https://joe.wixsite.com/garage")
    check("a. from the address alone: Facebook only (not fetched), a Google business.site (shut down in 2024, not fetched), a free Wix address (fetched)",
          soc[0]["code"] == "social_only" and not go and gbp[0]["code"] == "dead_gbp_site" and "2024" in gbp[0]["text"] and not go2 and wix[0]["code"] == "free_subdomain" and go3)

    # --- the site audit (network part, faked): http:// is tried as https:// first; 'dead' only when certain
    def fetcher(table):
        seen = []

        def f(u):
            seen.append(u)
            r = {"status": 0, "final_url": u, "text": "", "elapsed_s": 0.3, "size": 0, "headers": {}, "error": ""}
            r.update(table.get(u, {"error": "dns"}))
            return r
        f.seen = seen
        return f

    os.environ.pop("AGENCY_FAKE_PROXY", None)
    f1 = fetcher({"https://a.example/": {"status": 200, "text": GOOD_PAGE, "final_url": "https://a.example/"}})
    r1 = A.audit("http://a.example/", robots=False, fetch=f1, pause=0, sleep=lambda s: None)
    check("a. an http:// address is tried as https:// first; when that works the site has HTTPS and nothing is wrong", f1.seen == ["https://a.example/"] and r1["issues"] == [] and r1["fetched"], (f1.seen, r1))
    f2 = fetcher({"https://b.example/": {"status": 403}, "http://b.example/": {"error": "dns"}})
    r2 = A.audit("http://b.example/", robots=False, fetch=f2, pause=0, sleep=lambda s: None)
    check("a. a bot wall (403) proves nothing: 'open it on your phone', no points", r2["issues"] == [] and "blocks automatic checks" in r2["note"], r2)
    f3 = fetcher({})
    real_proxied, real_resolver = A.proxied, A.resolver_works
    try:
        A.proxied, A.resolver_works = (lambda: True), (lambda: False)
        r3 = A.audit("http://c.example/", robots=False, fetch=f3, pause=0, sleep=lambda s: None)
        A.proxied, A.resolver_works = (lambda: False), (lambda: True)
        r4 = A.audit("http://d.example/", robots=False, fetch=fetcher({}), pause=0, sleep=lambda s: None)
        f5 = fetcher({"https://e.example/": {"error": "timeout"}})
        r5 = A.audit("https://e.example/", robots=False, fetch=f5, pause=0, sleep=lambda s: None)
        A.proxied = lambda: True
        r6 = A.audit("https://f.example/", robots=False, fetch=fetcher({"https://f.example/": {"status": 502}}), pause=0, sleep=lambda s: None)
    finally:
        A.proxied, A.resolver_works = real_proxied, real_resolver
    check("a. 'dead' only when certain: behind a proxy without name lookups a failure = 'could not check' (no points); with working lookups a failed lookup = dead domain",
          r3["issues"] == [] and "Could not open" in r3["note"] and r4["issues"][0]["code"] == "dead_domain", (r3, r4["issues"]))
    check("a. no answer twice (no proxy) = down, after one retry; a 502 our proxy made up (no Server header) = could not check",
          r5["issues"][0]["code"] == "site_down" and f5.seen == ["https://e.example/", "https://e.example/"] and r6["issues"] == [] and "blocks" in r6["note"], (r5, f5.seen, r6))
    again = A.audit("http://a.example/", robots=False, fetch=fetcher({}), pause=0)
    check("a. a checked site is never fetched again within 30 days (the cache answers)", again["checked"] == r1["checked"] and again["issues"] == [])

    # --- the score and the day's list
    s_none = L.score(dict(leads[1], website=""))
    s_unchecked = L.score(leads[1])
    s_bad = L.score(leads[1], {"issues": bad["issues"]})
    s_good = L.score(leads[1], {"issues": []})
    s_soc = L.score(leads[4], {"issues": soc})
    check("a. score = need + reach + value: no website, a phone, a street, a plumber = 70 + 20 + 10 = 100 (A); unchecked site 55; an old site capped at 65 need (95); a fine site 30 (C)",
          (s_none["score"], s_none["tier"], s_unchecked["score"], s_bad["need"], s_bad["score"], s_good["score"], s_good["tier"]) == (100, "A", 55, 65, 95, 30, "C"),
          (s_none["score"], s_unchecked["score"], s_bad["score"], s_good["score"]))
    check("a. the why line is one plain sentence: 'No website found ... plumber Fort Collins ...'; an old site names its two worst problems; Facebook-only says so",
          s_none["why"].startswith("No website found") and "'plumber Fort Collins'" in s_none["why"] and s_bad["why"].startswith("Not built for phones") and "; no padlock" in s_bad["why"]
          and "Facebook" in s_soc["why"] and len(s_bad["why"]) <= 220, (s_none["why"], s_bad["why"], s_soc["why"]))
    pool = [dict(leads[0], id=f"x{i}", name=f"B{i}", score=99 - i, distance_km=1, category="barber") for i in range(6)] + [dict(leads[2], id="y", name="S", score=60, distance_km=2)]
    day = L.pick(pool, top=4, per_category=3)
    check("a. the day's list: best first, at most 3 of one trade, then filled with the next best", [d["id"] for d in day] == ["x0", "x1", "x2", "y"], [d["id"] for d in day])
    cov = L.coverage([L.enrich(x) for x in leads])
    check("a. coverage is measured and stored (honest about thin OSM data): phone 80%, website 40%, hours 20%", (cov["phone"], cov["website"], cov["hours"]) == (0.8, 0.4, 0.2), cov)

    # --- one full run on fake sources, files written
    res = L.run(PLACE, 8, C.DEFAULT_KEYS, top=20, fetch=fake, audit_fn=lambda u, refresh=False: {"issues": [], "checked": "2026-11-14"}, log=lambda *a: None)
    paths = L.write(res, os.path.join(TMP, "run1"))
    data = json.load(open(paths["json"], encoding="utf-8"))
    csv_head = open(paths["csv"], encoding="utf-8-sig").readline().strip().split(",")
    check("a. a run writes leads.json (v1, meta with coverage + attribution, the leads) and leads.csv / all_leads.csv with name, trade, address, phone, site, score, reasons",
          data["kind"] == "agency-leads" and data["meta"]["coverage"]["n"] == 5 and "OpenStreetMap" in data["meta"]["attribution"] and len(data["leads"]) == 5
          and all(c in csv_head for c in ("name", "category_label", "address", "phone", "website", "score", "why", "reasons")) and os.path.isfile(paths["all"]), csv_head)
    check("a. the lead finder reads the city from the ONE settings file and refuses the placeholder in plain words",
          _raises(lambda: L.place_from_args(L.parser(CFG.load()).parse_args([])), "Put your city in"))


BAD_PAGE = """<html><head><title>Old Shop</title><meta name="generator" content="Microsoft FrontPage 4.0"></head>
<body bgcolor="#ffffff"><center><font face="Arial" size="2">Welcome to Old Shop! Call 970-555-0142.</font></center>
<table><tr><td><font size="1">&copy; 2015 Old Shop</font></td></tr></table></body></html>"""
GOOD_PAGE = f"""<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width, initial-scale=1"><title>Good Shop</title>
<meta name="description" content="Repairs in town"></head><body><a href="tel:+19705550142">Call (970) 555-0142</a> <a class="btn" href="/book">Book now</a>
<footer>&copy; {time.localtime().tm_year} Good Shop</footer></body></html>"""


def analyze_fixture(html, url, elapsed=0.5):
    return A.analyze(html, url, 200, elapsed, len(html), {})


def _raises(fn, text):
    try:
        fn()
    except (ValueError, osm.SourceError, SystemExit) as e:
        return text in str(e)
    return False


if __name__ == "__main__":
    try:
        test_leads()
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    AK.finish()
