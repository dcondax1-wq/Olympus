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
    none = L.suppression(os.path.join(TMP, "no-suppress.txt"), exports=[])
    sp = os.path.join(TMP, "suppress.txt")
    open(sp, "w", encoding="utf-8").write("# people who said stop\n(970) 694-2949   # Cinco Brothers asked\nn10\nWild Mane Salon\nhttps://www.taqueria-elsewhere.example/\n")
    ex = os.path.join(TMP, "crm_export.json")
    json.dump({"kind": "agency-crm", "v": 1, "state": {"leads": {"w4": {"stage": "dnc"}, "n11": {"stage": "won"}}}}, open(ex, "w"))
    sup = L.suppression(sp, exports=[ex])
    gone = L.run(PLACE, 8, C.DEFAULT_KEYS, top=20, fetch=fake, audit_fn=lambda u, refresh=False: {"issues": [], "checked": "2026-11-14"}, log=lambda *a: None, suppress=sup)
    check("a. the do-not-contact list is honoured on every run: a phone, a lead id, a name (suppress.txt) and a 'Do not contact' lead in a saved page export are never listed again",
          [l["name"] for l in gone["leads"]] == ["Taqueria Sol"] and gone["meta"]["skipped"]["do_not_contact"] == 4 and "taqueria-elsewhere.example" in sup["domains"]
          and sup["ids"] == {"n10", "w4"}, ([l["name"] for l in gone["leads"]], sup))
    res = L.run(PLACE, 8, C.DEFAULT_KEYS, top=20, fetch=fake, audit_fn=lambda u, refresh=False: {"issues": [], "checked": "2026-11-14"}, log=lambda *a: None, suppress=none)
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


# ================================================================================================ b. the site generator
DEMO_LEADS = os.path.join(ROOT, "agency", "demo", "fort-collins", "leads.json")
CLAIMS = re.compile(r"\blicen[cs]ed\b|\binsured\b|24/7|free estimate|since (19|20)\d\d|\bbest in\b|#1\b|award", re.I)
HOTLINK = re.compile(r"""(?:src|srcset|poster|data)\s*=\s*["']?\s*(?:https?:)?//|<link[^>]+href=["']?(?:https?:)?//|url\(\s*["']?(?:https?:)?//|@import""", re.I)


def lead_fixture(**over):
    d = {"id": "n1", "slug": "joes-barber-co", "name": "Joe's <b>\"Best\"</b> Barber & Co", "category": "barber", "template": "studio", "lat": 40.58, "lon": -105.08,
         "address": {"housenumber": "120", "street": "West Olive Street", "unit": "", "city": "Fort Collins", "state": "CO", "postcode": "80524", "city_guess": False,
                     "line": "120 West Olive Street, Fort Collins, CO 80524", "street_line": "120 West Olive Street", "has_street": True},
         "phone": "(970) 555-0142", "phone_e164": "+19705550142", "email": "", "website": "", "facebook": "", "instagram": "",
         "opening_hours": "Tu-Fr 09:00-18:00; Sa 08:00-15:00", "cuisine": "", "osm_url": "https://www.openstreetmap.org/node/1", "issues": [], "reasons": []}
    d.update(over)
    return d


def test_sites():
    from agency import build_site as B
    from agency import sitecheck as SC
    cfg = CFG.load()
    out = os.path.join(TMP, "sites")
    check("b. 8 templates (5+ asked), each with its own look file, picture, palette and fonts; every trade maps to one",
          len(B.TEMPLATE_IDS) == 8 and all(os.path.isfile(os.path.join(ROOT, "agency", "templates", d, f"{t}.{e}")) for t in B.TEMPLATE_IDS for d, e in (("themes", "css"), ("art", "svg")))
          and set(c.template for c in C.CATEGORIES) <= set(B.TEMPLATE_IDS) and len({B.THEMES[t]["palette"]["accent"] for t in B.TEMPLATE_IDS}) == 8
          and len({B.THEMES[t]["display"] for t in B.TEMPLATE_IDS}) >= 5)
    css_all = " ".join(open(os.path.join(ROOT, "agency", "templates", "themes", f"{t}.css"), encoding="utf-8").read() for t in B.TEMPLATE_IDS)
    lic = open(os.path.join(ROOT, "agency", "templates", "themes.json"), encoding="utf-8").read()
    check("b. original art only: CSS + inline SVG, no photo files, CC0 stated", "CC0" in lic and not [f for f in os.listdir(os.path.join(ROOT, "agency", "templates", "art")) if not f.endswith(".svg")]
          and "url(http" not in css_all)
    built = {}
    for t in B.TEMPLATE_IDS:
        s = B.site_from_lead(lead_fixture(), cfg, t)
        s["slug"] = f"joes-{t}"
        built[t] = B.write_site(s, out)
    oks = {t: (r["check"]["ok"], r["check"]["scores"], r["check"]["hard_fails"]) for t, r in built.items()}
    check("b. every template builds a site that passes the self-check: valid HTML, no hotlink, viewport, contrast, labels, one h1 (all 8)",
          all(v[0] for v in oks.values()) and all(min(v[1].values()) >= 90 for v in oks.values()), {t: v for t, v in oks.items() if not v[0] or min(v[1].values()) < 90})
    idx = {t: open(os.path.join(r["site_dir"], "index.html"), encoding="utf-8").read() for t, r in built.items()}
    check("b. no external hotlinks in any file (no remote img / script / stylesheet / font / css url): only links people tap (maps, tel)",
          not any(HOTLINK.search(h) for h in idx.values()) and all("https://www.google.com/maps/search/?api=1&amp;query=" in h for h in idx.values()), [t for t, h in idx.items() if HOTLINK.search(h)])
    h = idx["studio"]
    check("b. the name is escaped everywhere (no markup from data): Joe&#x27;s &lt;b&gt;&quot;Best&quot;&lt;/b&gt;",
          "<b>\"Best\"</b>" not in h and "Joe&#x27;s &lt;b&gt;&quot;Best&quot;&lt;/b&gt; Barber &amp; Co" in h)
    check("b. a demo: the preview bar names the agency from the ONE settings file, not indexed (noindex + robots.txt), the form does not post (data-preview)",
          'class="demo"' in h and "by YOUR AGENCY" in h and 'content="noindex, nofollow"' in h and "data-preview" in h
          and open(os.path.join(built["studio"]["site_dir"], "robots.txt")).read() == "User-agent: *\nDisallow: /\n")
    check("b. the contact form: Netlify Forms attributes, the hidden form-name, a honeypot, labels, a thank-you page; tel: link in E.164; Apple + Google maps",
          'data-netlify="true"' in h and 'netlify-honeypot="company"' in h and 'name="form-name" value="contact"' in h and '<label for="f-phone">' in h
          and 'href="tel:+19705550142"' in h and "maps.apple.com" in h and os.path.isfile(os.path.join(built["studio"]["site_dir"], "thanks.html")))
    check("b. reviews are clearly marked samples (a 'Sample' tag on each, 'not real ones' above them)", h.count('<span class="tag">Sample</span>') == 3 and "These are sample reviews, not real ones." in h)
    check("b. no invented claims (licensed, insured, 24/7, free estimates, since 19xx, best in town) in any template", not any(CLAIMS.search(re.sub(r"<[^>]+>", " ", x)) for x in idx.values()))
    check("b. hours: a table grouped by day with today marked by the script; schema.org JSON-LD with the opening hours and the phone",
          '<tr data-days="1,2,3,4"><th scope="row">Tue - Fri</th><td>9 AM - 6 PM</td></tr>' in h and '"openingHoursSpecification"' in h and '"telephone": "+19705550142"' in h)
    sizes = {t: r["check"]["sizes"]["index.html"] for t, r in built.items()}
    check("b. fast: every home page under 60 KB with the CSS and pictures inline, 3 small files besides the pages", max(sizes.values()) < 60_000 and all(len([n for n in r["check"]["sizes"] if not n.endswith((".html", ".txt", "_headers"))]) <= 3 for r in built.values()), sizes)
    js = open(os.path.join(built["studio"]["site_dir"], "site.js"), encoding="utf-8").read()
    check("b. the one script is the site's own (same folder, deferred), fetches nothing, no web address in it", 'src="site.js" defer' in h and not re.search(r"fetch\(|XMLHttpRequest|https?://", js))
    hdr = open(os.path.join(built["studio"]["site_dir"], "_headers"), encoding="utf-8").read()
    check("b. security headers for Netlify / Cloudflare: a strict Content-Security-Policy (scripts only from the site itself), nosniff, frame and referrer rules",
          "script-src 'self';" in hdr and "X-Content-Type-Options: nosniff" in hdr and "frame-ancestors 'self'" in hdr)
    import zipfile as Z
    with Z.ZipFile(built["studio"]["zip"]) as z:
        names = z.namelist()
    check("b. the zip has index.html at the top (Cloudflare Pages drag and drop takes it as is; Netlify Drop takes the folder next to it)",
          "index.html" in names and all("/" not in n for n in names) and {"site.js", "favicon.svg", "404.html", "_headers"} <= set(names), names)
    nf = open(os.path.join(built["studio"]["site_dir"], "404.html"), encoding="utf-8").read()
    check("b. the 404 page works at any depth (root links: /site.js, /favicon.svg, /)", 'src="/site.js"' in nf and 'href="/favicon.svg"' in nf and 'href="/"' in nf)
    # the self-check really catches problems
    bad_dir = os.path.join(TMP, "bad")
    shutil.copytree(built["pro"]["site_dir"], bad_dir)
    with open(os.path.join(bad_dir, "index.html"), "r+", encoding="utf-8") as fh:
        t = fh.read().replace("<main id=\"main\">", "<main id=\"main\"><div><img src=\"https://stock.example.com/plumber.jpg\" alt=\"\">", 1)
        fh.seek(0)
        fh.write(t)
        fh.truncate()
    rb = SC.check_dir(bad_dir, B.THEMES["pro"]["palette"], B.CONTRAST)
    low = dict(B.THEMES["pro"]["palette"], muted="#b9c2cc")
    rc = SC.check_dir(built["pro"]["site_dir"], low, B.CONTRAST)
    check("b. the self-check catches a hotlinked stock photo and a <div> left open (hard fails), and grey-on-white text below 4.5:1",
          not rb["ok"] and any("another site" in f for f in rb["hard_fails"]) and any("not closed" in f or "never closed" in f for f in rb["hard_fails"])
          and not rc["ok"] and any("low contrast" in f for f in rc["hard_fails"]), (rb["hard_fails"], rc["hard_fails"]))
    # no phone, no hours, 3 pages, final mode
    s2 = B.site_from_lead(lead_fixture(phone="", phone_e164="", opening_hours="", name="Green Leaf Lawn", category="landscaper", slug="green-leaf"), cfg)
    r2 = B.write_site(s2, out, pages=3)
    h2 = open(os.path.join(r2["site_dir"], "index.html"), encoding="utf-8").read()
    check("b. no phone and no hours: 'Send a message' and 'Call us for today's hours' instead of a dead button; 3 pages link to each other",
          r2["check"]["ok"] and "tel:+1970" not in h2 and "Send a message" in h2 and "Call us for today" in h2 and 'href="services.html#services"' in h2
          and all(os.path.isfile(os.path.join(r2["site_dir"], f)) for f in ("services.html", "contact.html")) and s2["theme"] == "fresh", r2["check"]["hard_fails"])
    s3 = B.site_from_lead(lead_fixture(), cfg)
    s3["copy"]["headline"] = "Fresh fades on Olive Street"
    sj = os.path.join(TMP, "edited-site.json")
    json.dump(s3, open(sj, "w", encoding="utf-8"))
    rc3 = B.main(["--site", sj, "--final", "--url", "https://joesbarber.example", "--out", out])
    live = os.path.join(out, "joes-barber-co-live", "site")
    h3 = open(os.path.join(live, "index.html"), encoding="utf-8").read()
    check("b. an owner-edited site.json rebuilds as the LIVE site: the new headline, no preview bar, indexable, the form posts, canonical + sitemap",
          rc3 == 0 and "Fresh fades on Olive Street" in h3 and 'class="demo"' not in h3 and 'content="index, follow"' in h3 and "data-preview" not in h3
          and '<link rel="canonical" href="https://joesbarber.example/">' in h3 and os.path.isfile(os.path.join(live, "sitemap.xml")))
    check("b. the demo address follows the settings file's pattern ({slug}-demo.netlify.app)", s3["demo_url"] == "https://joes-barber-co-demo.netlify.app")
    real = json.load(open(DEMO_LEADS, encoding="utf-8"))["leads"]
    check("b. the committed demo: 20 real Fort Collins leads, every one with a name, trade, score, why line and an OpenStreetMap link",
          len(real) == 20 and all(l["name"] and l["category"] and l["why"] and l["osm_url"].startswith("https://www.openstreetmap.org/") for l in real))


# ================================================================================================ c. the pitch kit
def test_pitch():
    from agency import money as M
    from agency import pitch as P
    from agency import sitecheck as SC
    cfg = CFG.load()
    lead = dict(lead_fixture(), **L.score(lead_fixture()))
    k = P.kit(lead, cfg, "https://joes-barber-co-demo.netlify.app")
    check("c. the 30-second opener: at most 80 words, says who calls, the business, the city, the problem and the free preview, and asks one question",
          k["opener_words"] <= 80 and "YOUR NAME" in k["opener"] and "Joe's" in k["opener"] and "Fort Collins" in k["opener"] and "free preview" in k["opener"]
          and k["opener"].rstrip().endswith("?"), (k["opener_words"], k["opener"]))
    e = k["email"]
    check("c. the email with placeholders is marked NOT READY TO SEND (CAN-SPAM needs a real sender and postal address)", e.startswith("NOT READY TO SEND") and not k["ready"])
    check("c. the email: honest subject, the demo link, the price from the settings file, an ad line, the postal address, an opt-out",
          "Subject: A free website preview for Joe's" in e and "https://joes-barber-co-demo.netlify.app" in e and "$499 to set it up" in e and "$49 a month" in e
          and "This is a one-time offer of web design services" in e and "YOUR STREET ADDRESS" in e and 'Reply "no thanks"' in e)
    filled = json.load(open(CFG.EXAMPLE, encoding="utf-8"))
    filled["agency"].update(name="Pine Street Web", your_name="Sam Rivera", phone="(970) 555-0177", email="sam@pinestreetweb.example", postal_address="12 Pine St, Fort Collins, CO 80521")
    filled["packages"][0]["setup"] = 599
    json.dump(filled, open(os.environ["AGENCY_CONFIG"], "w", encoding="utf-8"))
    cfg2 = CFG.load()
    k2 = P.kit(lead, cfg2, "https://joes-barber-co-demo.netlify.app")
    check("c. after the owner fills the ONE settings file: ready, From = his name and email, his postal address, his new price ($599), no placeholder left",
          k2["ready"] and "From: Sam Rivera <sam@pinestreetweb.example>" in k2["email"] and "12 Pine St, Fort Collins, CO 80521" in k2["email"] and "$599 to set it up" in k2["email"]
          and not re.search(r"YOUR (NAME|AGENCY|STREET)", k2["email"] + k2["phone_script"] + k2["html"]), k2["email"][:300])
    ph = k2["phone_script"]
    check("c. the phone sheet: dial by hand (no auto-dialer), a voicemail line, four answers (have a site / price / send me / not interested -> Do not contact)",
          "never an auto-dialer" in ph and "VOICEMAIL" in ph and all(q in ph for q in ('"We already have a website."', '"How much?"', '"Send me something."', '"Not interested."'))
          and "Do not contact" in ph and "(970) 555-0177" in ph)
    pg = SC.Page()
    pg.feed(k2["html"])
    pg.close()
    check("c. the one-pager is valid, self-contained HTML (no hotlink): what customers find today, the demo link, 3 packages with the best fit marked, next steps",
          not pg.errors and not pg.stack and not HOTLINK.search(k2["html"]) and "What customers find today" in k2["html"] and "joes-barber-co-demo.netlify.app" in k2["html"]
          and k2["html"].count("<tr class=") == 3 and k2["html"].count("Best fit") == 1 and "Next step" in k2["html"], (pg.errors, pg.stack))
    roof = dict(lead_fixture(name="Highroad Roofing", category="roofer", slug="highroad-roofing", website="https://highroadroofing.example/"))
    roof.update(L.score(roof, {"issues": [A.issue("site_down", 55, "Their website does not open (error 500)")]}))
    kr = P.kit(roof, cfg2, "https://highroad-roofing-demo.netlify.app")
    check("c. a roofer with a broken site: the Growth package ($999 + $79), the email names the problem (did not open), the one-pager lists it",
          kr["package"] == "growth" and kr["setup"] == 999 and kr["monthly"] == 79 and "did not open" in kr["email"] and "The site did not open" in kr["html"], (kr["package"], kr["problem"]))
    plan = M.plan(CFG.load(CFG.EXAMPLE), M.load_pricing())
    four = next(r for r in plan["rows"] if r["new_per_month"] == 4)
    check("c. the money math: average sale $799 + $66 a month; 4 new clients a month passes $5,000 a month in month 8 (128 calls a month, about 6 a day)",
          (plan["avg_setup"], plan["avg_monthly"]) == (799.0, 66.0) and four["months_to_goal"] == 8 and plan["pace"]["new_per_month"] == 4 and plan["pace"]["dials"] == 128
          and plan["care_clients_for_goal_alone"] == 76, (plan["avg_setup"], plan["avg_monthly"], four, plan["pace"]))
    pr = M.load_pricing()
    check("c. the pricing research lists its sources with links and the date it was read", pr["checked"] == "2026-11-14" and len(pr["market"]) >= 8
          and all(x["url"].startswith("https://") and x["source"] for x in pr["market"] + pr["hosting"] + pr["rules"]))
    os.remove(os.environ["AGENCY_CONFIG"])
    raw = open(os.path.join(ROOT, "RUN_AGENCY.bat"), "rb").read()
    txt = raw.decode("ascii", "replace")
    labels = {ln.strip()[1:].split()[0].lower() for ln in txt.split("\r\n") if ln.strip().startswith(":") and not ln.strip().startswith("::")} | {"eof"}
    gotos = {m.lower() for m in re.findall(r"(?i)\bgoto\s+:([A-Za-z0-9_]+)", txt)}
    check("c. RUN_AGENCY.bat (the owner's double-click): CRLF, ASCII, every goto label exists, first run copies the example settings and opens Notepad, then runs agency.run; it sends nothing",
          b"\n" not in raw.replace(b"\r\n", b"") and raw.endswith(b"\r\n") and all(b < 128 for b in raw) and gotos <= labels and 'copy /y "agency\\config.example.json" "agency\\config.json"' in txt
          and "python -X utf8 -m agency.run %*" in txt and not re.search(r"(?i)\b(curl|blat|sendmail|powershell)\b", txt), (sorted(gotos - labels)))
    gi = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
    check("c. no secrets or personal data in the repo: the owner's settings, cache, batches and do-not-contact list are gitignored; the committed example has placeholders only",
          all(x in gi for x in ("agency/config.json", "agency/cache/", "agency/out/", "agency/suppress.txt")) and set(CFG.placeholders(CFG.load(CFG.EXAMPLE))) >= {"agency.name", "agency.your_name", "agency.email", "agency.postal_address", "search.city"})


# ================================================================================================ d. the CRM page (tools/web_public/agency/)
APP = "agency"
CORE_HARNESS = r"""
import(process.argv[2]).then((C) => {
  const fs = require('fs'), o = {}, T = '2026-11-14';
  const data = C.normData(JSON.parse(fs.readFileSync(process.argv[3], 'utf8')));
  const fx = C.normData(JSON.parse(fs.readFileSync(process.argv[4], 'utf8')));
  o.data = [data.leads.length, data.sample, data.demo, data.city, data.agency.ready, data.packages.map((p) => p.id).join(','), fx.demo, fx.leads.length];
  const junk = C.normData({ leads: [{ id: 'bad id!', name: 'x' }, { id: 'ok1', name: '<b>A</b>', score: 250, phone_e164: '12345', website: 'javascript:alert(1)', map_url: 'http://x.example' }, { id: 'ok1', name: 'dup' }] });
  o.junk = [junk.leads.length, junk.leads[0].score, junk.leads[0].tel, junk.leads[0].website, junk.leads[0].map, C.normData({ leads: [] }), C.normData('x')];
  o.links = [C.telHref('+19705550142'), C.telHref('970'), C.safeUrl('https://a.example/x'), C.safeUrl('http://a.example'), C.safeUrl('https://a b'), C.mailHref('x@y.com', 'Hi there', 'Body & more').startsWith('mailto:x@y.com?subject=Hi%20there&body=Body%20%26%20more'), C.mailHref('nope', 'a', 'b')];
  const id0 = data.leads[0].id, id1 = data.leads[1].id, built = data.leads.find((l) => l.demo_built);
  let s = C.emptyState();
  const v0 = C.views(data, s);
  o.defaults = [C.stageOf(data.leads.find((l) => !l.demo_built), s), built ? C.stageOf(built, s) : 'none', v0.filter((v) => v.stage === 'demo').length];
  s = C.update(s, id0, { called: true }, T);
  s = C.update(s, id0, { stage: 'callback', callback: '2026-11-13' }, T);
  s = C.update(s, id1, { stage: 'won', price: 1200, monthly: 99 }, T);
  s = C.update(s, id1, { notes: 'Owner is Sam. Wants a gallery.' }, T);
  const e0 = C.entry(s, id0), e1 = C.entry(s, id1);
  o.update = [e0.stage, e0.calls, e0.last_call, e0.callback, e1.stage, e1.won, e1.price, e1.monthly, e1.notes, s.log.length];
  const vs = C.views(data, s), p = C.pipeline(vs, T, 5000);
  o.pipe = [p.won, p.won_setup_month, p.mrr, p.month_total, Math.round(p.goal_frac * 1000), p.calls_week, p.by.won, p.by.callback, p.open > 0, p.weighted < p.open, p.active];
  const today = C.callToday(vs, T, 5);
  o.today = [today.length, today[0].id === id0, today.every((v) => v.tel), today.filter((v) => v.stage === 'won').length];
  o.filter = [C.filterSort(vs, { stage: 'won' }).length, C.filterSort(vs, { q: 'gallery' }).length, C.filterSort(vs, { stage: 'all', sort: 'name' })[0].name <= C.filterSort(vs, { stage: 'all', sort: 'name' })[1].name,
    C.filterSort(vs, { sort: 'value' })[0].id === id1, C.trades(vs).length > 3, C.filterSort(vs, { trade: 'Dentist' }).every((v) => v.trade === 'Dentist')];
  const ex = C.exportJson(s, T), back = C.parseImport(ex);
  o.io = [JSON.parse(ex).kind, back.ok, back.count, C.entry(back.state, id1).price, C.parseImport('{nope').ok, C.parseImport('{nope').error.includes('not valid JSON'), C.parseImport('{"kind":"other"}').ok, C.parseImport('{}').ok, C.parseImport('').ok];
  const csv = C.toCSV(vs);
  const Q = String.fromCharCode(34);
  o.csv = [csv.split('\r\n')[0].startsWith('name,trade,stage,score'), csv.split('\r\n').length - 2, csv.includes('Won'), C.toCSV([{ ...vs[0], name: '=SUM(A1)' }]).includes(Q + "'=SUM(A1)" + Q),
    C.toCSV([{ ...vs[0], notes: 'a, ' + Q + 'b' + Q }]).includes(Q + 'a, ' + Q + Q + 'b' + Q + Q + Q)];
  const s2 = C.update(s, id1, { stage: 'lost' }, T);
  o.lost = [C.entry(s2, id1).won, C.update(s2, id0, { stage: 'dnc' }, T).leads[id0].callback, C.money(1234.5), C.money(-3), C.weekStart('2026-11-14'), C.addDays('2026-12-31', 1)];
  o.words = [C.heroLine(C.pipeline(C.views(data, C.emptyState()), T, 5000)).startsWith('No client yet'), C.heroLine(p).startsWith('1 client: $1,200 in setup fees this month + $99 a month'), C.planRows(data.plan).length];
  console.log(JSON.stringify(o));
});
"""


def test_crm_static():
    AK.static_kit(APP, "Agency", reads=("./leads.json",), storage=True)
    d = os.path.join(AK.WEB, APP)
    js = AK.read(os.path.join(d, "agency.js")) + AK.read(os.path.join(d, "agencycore.js"))
    check("d. the only thing kept in the browser is the owner's own notes (one key, try / catch); no sessionStorage / indexedDB / cookies",
          len(re.findall(r"localStorage\.", js)) == 2 and "agency.crm.v1" in js and not re.search(r"sessionStorage|indexedDB|document\.cookie", js))
    check("d. it never sends or dials by itself: no fetch other than the two files, tel: / mailto: only as links the owner taps, no SMS, no form post",
          js.count("fetch(") == 1 and "sms:" not in js and not re.search(r"method:\s*['\"]POST|navigator\.sendBeacon|\.submit\(\)", js) and "telHref" in js and "mailHref" in js)
    css = AK.read(os.path.join(d, "agency.css"))
    raw_colours = [c for c in re.findall(r"#[0-9a-fA-F]{3,8}\b", css)]
    check("d. themes reach it: every colour in agency.css is an --ag-* / --oly-* token (no raw hex)", not raw_colours and css.count("var(--ag-") > 60, raw_colours[:5])
    html = AK.read(os.path.join(d, "index.html"))
    check("d. page order: this month ($ and the goal), call today, the pipeline (stages, search, list), the lead, the plan, your notes (export / CSV / import)",
          html.index('id="heroNum"') < html.index('id="today"') < html.index('id="stages"') < html.index('id="list"') < html.index('id="detail"') < html.index('id="planTable"') < html.index('id="exportBtn"')
          and all(x in html for x in ('id="csvBtn"', 'id="importBtn"', 'id="ioText"', 'id="copyOpener"', 'id="copyEmail"', 'id="mailBtn"')))
    data = json.load(open(os.path.join(d, "leads.json"), encoding="utf-8"))
    fx = json.load(open(os.path.join(d, "fixture.json"), encoding="utf-8"))
    check("d. the published data: the 20 Fort Collins leads (marked sample city), 3 demo sites built, the attribution, no owner data (placeholders only), every opener under 80 words",
          len(data["leads"]) == 20 and data["sample"] is True and sum(l["demo_built"] for l in data["leads"]) == 3 and "OpenStreetMap" in data["attribution"]
          and data["agency"] == {"name": "YOUR AGENCY", "ready": False} and all(len(l["opener"].split()) <= 80 for l in data["leads"]) and data["plan"]["pace"]["new_per_month"] == 4)
    check("d. the DEMO fixture: invented businesses in an invented town with 555-01xx numbers, labelled 'EXAMPLE ... not real'",
          fx["demo"] is True and "not real" in fx["note"] and all(l["phone"].startswith("(555) 555-01") for l in fx["leads"]) and all("Maple Falls" in l["address_line"] for l in fx["leads"]))
    out = AK.node(APP, CORE_HARNESS, os.path.join(d, "leads.json"), os.path.join(d, "fixture.json"))
    if out is None:
        check("d. node is not installed: core skipped", True)
        return
    check("d. node: no error in the harness", "_error" not in out, out.get("_error"))
    if "_error" in out:
        return
    o = out
    check("d. core: the data reads 20 leads, sample city, Fort Collins, CO, the three packages; the fixture is DEMO with 8 leads",
          o["data"] == [20, True, False, "Fort Collins, CO", False, "starter,growth,pro", True, 8], o["data"])
    check("d. core: junk is dropped or neutralised: bad ids, duplicates, a 250 score -> 100, a bad phone -> no tel link, javascript: and http:// links -> empty; no leads -> null",
          o["junk"] == [1, 100, "", "", "", None, None], o["junk"])
    check("d. core: only safe links: tel:+1..., https:// only, mailto with the subject and body encoded", o["links"] == ["tel:+19705550142", "", "https://a.example/x", "", "", True, ""], o["links"])
    check("d. core: a lead starts as New lead, a built demo as Demo built (3 of them)", o["defaults"] == ["new", "demo", 3], o["defaults"])
    check("d. core: Call marks it contacted (1 call, today); a call-back day keeps the date; Won keeps the day, the price $1,200 + $99, the note; every stage change is logged",
          o["update"] == ["callback", 2, "2026-11-14", "2026-11-13", "won", "2026-11-14", 1200, 99, "Owner is Sam. Wants a gallery.", 3], o["update"])
    check("d. core: the money: 1 won = $1,200 setup this month + $99 care = $1,299 (26% of $5,000), 1 called this week, the open deals and a smaller weighted figure",
          o["pipe"][:9] == [1, 1200, 99, 1299, 260, 1, 1, 1, True] and o["pipe"][9] is True and o["pipe"][10] == 19, o["pipe"])
    check("d. core: Call today = the due call-back first, then new leads with a phone, never a won one", o["today"] == [5, True, True, 0], o["today"])
    check("d. core: filters by stage, search in the notes, sort by name / value, trade filter", all(x is True or x == 1 for x in o["filter"]), o["filter"])
    check("d. core: export -> import gives the same notes back; broken JSON, another kind, an empty object and empty text are refused in plain words",
          o["io"] == ["agency-crm", True, 2, 1200, False, True, False, False, False], o["io"])
    check("d. core: CSV with a header and one row per lead, stage names, formula injection blocked ('=SUM -> '\\'=SUM), quotes escaped", o["csv"] == [True, 20, True, True, True], o["csv"])
    check("d. core: Lost clears the won day, Do not contact clears the call-back; money and day maths", o["lost"] == [None, None, "$1,235", "-$3", "2026-11-09", "2027-01-01"], o["lost"])
    check("d. core: plain words for the hero and the plan rows from the published plan", o["words"] == [True, True, 6], o["words"])


def test_crm_page():
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("d. page tests skipped: no Playwright", True)
        return
    srv, origin = AK.serve()
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?demo=1", hook="AGENCY")
            d = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, note: document.querySelector('#sampleNote').textContent, rows: document.querySelectorAll('#list .lrow').length,
              today: document.querySelectorAll('#today .lrow').length, chips: document.querySelectorAll('#stages .chip').length, hero: document.querySelector('#heroNum').textContent,
              font: getComputedStyle(document.querySelector('h1')).fontFamily, bg: getComputedStyle(document.body).backgroundColor, status: document.querySelector('#status').textContent })""")
            check("d. DEMO (?demo=1): the chip and the EXAMPLE note, 8 invented leads, 5 to call today, 8 stage chips, $0 this month, AGORA serif title, warm dark page",
                  d["demo"] and "EXAMPLE" in d["note"] and d["rows"] == 8 and d["today"] == 5 and d["chips"] == 8 and d["hero"] == "$0"
                  and any(f in d["font"] for f in ("Palatino", "Iowan", "Georgia")) and "Maple Falls" in d["status"], d)
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin)
            p.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=origin)
            AK.open_app(p, origin, APP, "", hook="AGENCY")
            r = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, sample: !document.querySelector('#sample').hidden, note: document.querySelector('#sampleNote').textContent,
              rows: document.querySelectorAll('#list .lrow').length, first: document.querySelector('#today .lrow b').textContent, tel: document.querySelector('#today .lrow a.call').getAttribute('href'),
              plan: document.querySelectorAll('#planTable tbody tr').length, pace: document.querySelectorAll('#planTable tr.pace').length, lead: document.querySelector('#planLead').textContent })""")
            check("d. the real published data: no DEMO chip, SAMPLE CITY chip and note, 20 leads, a tel: Call button on the call list, the plan table with the pace row",
                  not r["demo"] and r["sample"] and "Fort Collins" in r["note"] and r["rows"] == 20 and r["tel"].startswith("tel:+1970") and r["plan"] == 6 and r["pace"] == 1
                  and "4 new clients a month" in r["lead"], r)
            AK.shot(p, "agency-crm")
            p.locator("#list .leadbtn").first.click()
            p.wait_for_timeout(250)
            det = p.evaluate("""() => ({ shown: !document.querySelector('#detail').hidden, name: document.querySelector('#detName').textContent, opener: document.querySelector('#detOpenerText').textContent,
              email: document.querySelector('#detEmailText').textContent, ready: document.querySelector('#detReady').textContent, mail: document.querySelector('#mailBtn').hidden,
              acts: [...document.querySelectorAll('#detActions a')].map((a) => a.textContent), stages: document.querySelectorAll('#detStages .chip').length })""")
            check("d. tap a lead: its card opens with the opener, the email (NOT READY until the settings file is filled, so no Open-in-Mail button), Call / Demo / Map links, 7 stages",
                  det["shown"] and det["name"] and det["name"] in det["opener"] and "NOT READY TO SEND" in det["email"] and "Not ready to send" in det["ready"] and det["mail"]
                  and det["acts"][0].startswith("Call (970)") and "Demo site" in det["acts"] and det["stages"] == 7, det)
            name = det["name"]
            p.locator("#detStages .chip", has_text="Won").click()
            p.wait_for_timeout(200)
            p.fill("#detNotes", "Owner said yes on the phone.")
            p.locator("#detNotes").dispatch_event("change")
            p.wait_for_timeout(200)
            w = p.evaluate("() => ({ store: localStorage.getItem('agency.crm.v1'), hero: document.querySelector('#heroNum').textContent, won: document.querySelector('#stages .chip[data-stage=won]').textContent, msg: document.querySelector('#detMsg').textContent })")
            check("d. mark it Won and add a note: saved in this browser, the hero shows this month's money, the Won chip counts 1",
                  '"stage":"won"' in w["store"] and "Owner said yes" in w["store"] and w["hero"] not in ("$0", "") and w["won"] == "Won 1" and "Notes saved" in w["msg"], w)
            p.reload()
            p.wait_for_function("window.AGENCY && window.AGENCY.ready()", timeout=60000)
            p.wait_for_timeout(300)
            check("d. it survives a reload (this browser only)", p.evaluate("() => document.querySelector('#stages .chip[data-stage=won]').textContent") == "Won 1")
            p.locator("#stages .chip[data-stage=won]").click()
            p.wait_for_timeout(150)
            check("d. the Won chip filters the list to that one lead", p.evaluate("() => [...document.querySelectorAll('#list .lrow b')].map((b) => b.textContent)") == [name])
            p.locator("#stages .chip[data-stage=all]").click()
            p.fill("#q", "dental")
            p.wait_for_timeout(150)
            check("d. search finds the dentists", 1 <= p.evaluate("() => document.querySelectorAll('#list .lrow').length") <= 3)
            p.fill("#q", "")
            with p.expect_download() as dl:
                p.locator("#csvBtn").click()
            path = dl.value.path()
            text = open(path, encoding="utf-8").read()
            check("d. Download CSV gives every lead with its stage (Won for the one we marked)", text.startswith("name,trade,stage") and text.count("\r\n") == 21 and ",Won," in text, text[:200])
            p.locator("#exportBtn").click()
            ex = p.evaluate("() => [document.querySelector('#ioText').value, document.querySelector('#ioMsg').textContent]")
            check("d. Export puts the notes as JSON in the box and says how many leads", '"kind": "agency-crm"' in ex[0] and "Owner said yes" in ex[0] and "on 1 lead." in ex[1], ex[1])
            p.evaluate("() => { window.confirm = () => true; }")
            p.locator("#clearBtn").click()
            p.wait_for_timeout(150)
            cleared = p.evaluate("() => document.querySelector('#stages .chip[data-stage=won]').textContent")
            p.fill("#ioText", ex[0])
            p.locator("#importBtn").click()
            p.wait_for_timeout(150)
            back = p.evaluate("() => [document.querySelector('#stages .chip[data-stage=won]').textContent, document.querySelector('#ioMsg').textContent]")
            check("d. Start over clears the notes; Import brings them back", cleared == "Won 0" and back[0] == "Won 1" and "Imported your notes on 1 lead" in back[1], (cleared, back))
            p.fill("#ioText", "{ nope")
            p.locator("#importBtn").click()
            check("d. a broken import changes nothing and says why", "not valid JSON" in p.evaluate("() => document.querySelector('#ioMsg').textContent"))
            t = AK.taps(p)
            check("d. every tap target is at least 44 x 44 px (leads, Call, chips, fields, buttons)", not t, t[:6])
            check("d. no sideways scroll at 390 px; the orb's corner is free; no console error; nothing loaded from another site", AK.no_sideways(p) and not AK.corner(p) and not errs and not off, (AK.corner(p)[:3], errs[:3], off[:3]))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, APP, "?lead=" + json.load(open(os.path.join(AK.WEB, APP, "leads.json"), encoding="utf-8"))["leads"][2]["id"], hook="AGENCY")
            sm = p.evaluate("() => [!document.querySelector('#detail').hidden, document.documentElement.scrollWidth <= innerWidth + 1]")
            check("d. 375 x 667, LITE, reduced motion: ?lead= opens that lead, no sideways scroll, taps >= 44 px, no error", sm == [True, True] and not AK.taps(p) and not errs, (sm, AK.taps(p)[:3], errs[:2]))
            ctx.close()
            ctx = br.new_context(viewport={"width": 1280, "height": 900})
            p = ctx.new_page()
            p.goto(f"{origin}/{APP}/")
            p.wait_for_function("window.AGENCY && window.AGENCY.ready()", timeout=60000)
            cols = p.evaluate("() => getComputedStyle(document.querySelector('#app')).gridTemplateColumns.split(' ').length")
            check("d. desktop (1280 px): two columns", cols == 2, cols)
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    fast = "--fast" in sys.argv
    try:
        test_leads()
        test_sites()
        test_pitch()
        test_crm_static()
        if not fast:
            test_crm_page()
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    AK.finish()
