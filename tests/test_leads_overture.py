"""Overture Maps check of the website leads (tools/web_leads_overture.py) on a small fixture parquet + the committed results.

    python tests/test_leads_overture.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import web_leads_overture as W  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "overture", "places.parquet")
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("  [OK]  " if ok else "  [FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"))


PLACES = [  # id, name, websites, phones, emails, cat, tax, street, town, zip, lon, lat, confidence, status, brand
    ("p-a", "Pearl Dental Arts", ["https://www.pearldentalarts.com/"], ["+1 301 555 0101"], ["a@x.com"], "dental_clinic", "dentist", "1 Main St", "Frederick", "21701", -77.4100, 39.4200, 0.9, "open", None),
    ("p-b", "Gonzo Plumbing", ["http://gonzoplumbing.net"], ["3015550102"], [], "home_service", "plumbing", "2 Main St", "Frederick", "21701", -77.4200, 39.4250, 0.9, "open", None),
    ("p-c", "Tasty Thai Kitchen", ["https://facebook.com/tastythai"], ["(301) 555-0103"], [], "restaurant", "thai_restaurant", "3 Main St", "Frederick", "21701", -77.4300, 39.4300, 0.9, "open", None),
    ("p-d", "Zeno Barber Lounge", None, ["301-555-0104"], [], "personal_or_beauty_service", "barber", "4 Main St", "Frederick", "21701", -77.4400, 39.4350, 0.9, "open", None),
    ("p-e", "Hub City Thrift", None, ["301-555-0105"], [], "second_hand_store", "thrift_store", "5 Main St", "Frederick", "21701", -77.4000, 39.4100, 0.9, "open", None),
    ("p-new", "Ridge Roofing Co", None, ["+13015550106"], ["owner@ridge.example"], "home_service", "roofing", "6 Oak Ave", "Frederick", "21702", -77.3900, 39.4400, 0.8, "open", None),
    ("p-chain", "Brand Burger", None, ["3015550107"], [], "restaurant", "burger_restaurant", "7 Oak Ave", "Frederick", "21702", -77.3950, 39.4450, 0.9, "open", "Q123"),
    ("p-church", "First Church", None, ["3015550108"], [], "christian_place_of_worship", "church", "8 Oak Ave", "Frederick", "21702", -77.3960, 39.4460, 0.9, "open", None),
    ("p-closed", "Old Diner", None, ["3015550109"], [], "restaurant", "diner", "9 Oak Ave", "Frederick", "21702", -77.3970, 39.4470, 0.9, "permanently_closed", None),
    ("p-site", "Bright Web Cafe", ["https://brightwebcafe.com"], ["3015550110"], [], "restaurant", "cafe", "10 Oak Ave", "Frederick", "21702", -77.3980, 39.4480, 0.9, "open", None),
    ("p-far", "Far Away Spa", None, ["3015550111"], [], "personal_or_beauty_service", "spa", "1 Far Rd", "Nowhere", "21000", -70.0, 30.0, 0.9, "open", None),
]
LEADS = [
    {"id": "osm-a", "name": "Pearl Dental Arts", "lat": 39.42005, "lon": -77.41005, "phone": "", "town": "Frederick", "niche": "health"},
    {"id": "osm-b", "name": "Gonzo Plumbing LLC", "lat": 39.4250, "lon": -77.4201, "phone": "(301) 555-0999", "town": "Frederick", "niche": "contractor"},
    {"id": "osm-c", "name": "Tasty Thai Kitchen", "lat": 39.4300, "lon": -77.4300, "phone": "", "town": "Frederick", "niche": "food"},
    {"id": "osm-d", "name": "Zeno Barber Lounge", "lat": 39.4350, "lon": -77.4400, "phone": "", "town": "Frederick", "niche": "beauty"},
    {"id": "osm-e", "name": "Hub City Convenience Store", "lat": 39.4100, "lon": -77.4000, "phone": "", "town": "Frederick", "niche": "retail"},
]


def make_fixture():
    import duckdb
    os.makedirs(os.path.dirname(FIX), exist_ok=True)
    c = duckdb.connect()
    c.execute("""CREATE TABLE p (id VARCHAR, name VARCHAR, websites VARCHAR[], phones VARCHAR[], emails VARCHAR[], cat VARCHAR, tax VARCHAR, street VARCHAR,
                 town VARCHAR, zip VARCHAR, lon DOUBLE, lat DOUBLE, confidence DOUBLE, operating_status VARCHAR, brand_wd VARCHAR)""")
    c.executemany("INSERT INTO p VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", PLACES)
    c.execute(f"COPY p TO '{FIX}' (FORMAT parquet)")


def main() -> int:
    if not os.path.exists(FIX) or "--remake" in sys.argv:
        make_fixture()
    places = W.load_places(FIX)
    check("a. the fixture parquet loads (11 places; Overture emails are not even read)", len(places) == 11 and "emails" not in places[0], list(places[0]))
    check("a. domain rule: pearldentalarts.com ~ 'Pearl Dental Arts'; facebook / toasttab never count; a stranger's domain doesn't",
          W.domain_is_theirs("https://www.pearldentalarts.com/", "Pearl Dental Arts") and not W.domain_is_theirs("https://facebook.com/tastythai", "Tasty Thai")
          and not W.domain_is_theirs("https://www.toasttab.com/tasty-thai", "Tasty Thai") and not W.domain_is_theirs("http://deltaautobody.com", "Calfax Auto Body"))
    check("a. names: shared generic words are not a match ('Calfax Auto Body' / 'Delta Auto Body'); phones need the strict match",
          not W.same_name("Calfax Auto Body", "Delta Auto Body") and W.same_name("Blue Moon Foot Spa", "Blue Moon Spa")
          and not W.strict_name("Hub City Convenience Store", "Hub City Thrift") and W.strict_name("Pooshan Rugs", "Pooshan Rug Services"))
    with tempfile.TemporaryDirectory() as t:
        towns = os.path.join(t, "leads", "towns")
        os.makedirs(towns)
        json.dump({"v": 1, "kind": "web_leads_town", "town": "Frederick", "leads": LEADS}, open(os.path.join(towns, "frederick.json"), "w"))
        up = {"https://www.pearldentalarts.com/": (True, 200), "http://gonzoplumbing.net": (False, "dns")}
        c = W.run(places, towns_dir=towns, checker=lambda u: up.get(u, (False, 404)), today="2026-11-21")
        d = json.load(open(os.path.join(towns, "frederick.json")))
        by = {L["id"]: L for L in d["leads"]}
        check("b. verdicts: own domain + 200 = has_site (website set), own domain + no answer = site_down, a Facebook page = none",
              by["osm-a"]["web"]["verdict"] == "has_site" and by["osm-a"].get("website") == "https://www.pearldentalarts.com/"
              and by["osm-b"]["web"]["verdict"] == "site_down" and not by["osm-b"].get("website") and by["osm-c"]["web"]["verdict"] == "none", by)
        check("b. phone filled from Overture when missing (strict name), kept when present, not copied on a loose match",
              by["osm-d"]["phone"] == "(301) 555-0104" and by["osm-d"].get("phone_src") == "overture" and by["osm-b"]["phone"] == "(301) 555-0999"
              and by["osm-e"]["phone"] == "", by)
        new = [L for L in d["leads"] if L["id"].startswith("ovt-")]
        check("b. new leads: only the open, non-chain business with a phone and no website, in a town box (church, chain, closed, has-site, far: dropped)",
              [L["name"] for L in new] == ["Ridge Roofing Co"] and new[0]["phone"] == "(301) 555-0106" and new[0]["source"] == "overture"
              and new[0]["niche"] == "contractor" and new[0]["mailable"], [L["name"] for L in new])
        check("b. no Overture email copied anywhere; the town file carries the OSM + Overture credit",
              "ridge.example" not in json.dumps(d) and "a@x.com" not in json.dumps(d) and "Overture" in d["license"])
        rd = json.load(open(os.path.join(t, "leads", "redesign.json")))
        check("b. has_site leads go to the redesign list; counts add up", [r["id"] for r in rd["leads"]] == ["osm-a"] and c["has_site"] == 1 and c["site_down"] == 1
              and c["new"] == 1 and c["leads"] == 6, c)
        c2 = W.run(places, towns_dir=towns, checker=lambda u: up.get(u, (False, 404)), today="2026-11-21")
        check("b. a second run adds nothing twice (ids kept, no duplicate new leads)", c2["new"] == 0 and c2["leads"] == 6, c2)
    # d. the county search (tools/web_leads_counties.py) on the same fixture + one fixture county outline
    import duckdb
    from tools import web_leads_counties as C
    from tools import lead_value as V
    with tempfile.TemporaryDirectory() as t:
        shapes = os.path.join(t, "counties.parquet")
        c = duckdb.connect()
        c.execute("INSTALL spatial; LOAD spatial;")
        c.execute(f"""COPY (SELECT 'Howard County' AS county, ST_AsWKB(ST_GeomFromText('POLYGON((-77.45 39.40, -77.38 39.40, -77.38 39.45, -77.45 39.45, -77.45 39.40))')) AS wkb)
                      TO '{shapes}' (FORMAT parquet)""")
        up = {"https://www.pearldentalarts.com/": (True, 200), "http://gonzoplumbing.net": (False, "dns")}
        r = C.run(FIX, shapes, os.path.join(t, "out"), checker=lambda u: up.get(u, (False, 404)), top=2, today="2026-11-22")
        names = [L["name"] for L in r["leads_list"]]
        check("d. county search: no-website places with a phone in the county, high-ticket sites that don't load = site_down; chain / church / closed / "
              "a working site / outside the county dropped", set(names) == {"Gonzo Plumbing", "Zeno Barber Lounge", "Ridge Roofing Co", "Hub City Thrift"}
              and next(L for L in r["leads_list"] if L["name"] == "Gonzo Plumbing")["web"]["verdict"] == "site_down", names)
        check("d. ranked by $ (roofing / plumbing first), the top N marked build_site, county file written with the credit, no email",
              names[:2] == ["Gonzo Plumbing", "Ridge Roofing Co"] and [L["build_site"] for L in r["leads_list"]] == [True, True, False, False]
              and os.path.exists(os.path.join(t, "out", "howard-county.json")) and "Overture" in json.load(open(os.path.join(t, "out", "howard-county.json")))["license"]
              and "ridge.example" not in open(os.path.join(t, "out", "howard-county.json")).read(), [(L["name"], L["usd_score"]) for L in r["leads_list"]])
    check("d. the $ score: roofing > plumbing > dental > beauty > restaurant; site_down and a phone add",
          V.trade({"category": "roofing"})[0] > V.trade({"category": "plumbing"})[0] > V.trade({"category": "dentist"})[0] > V.trade({"category": "barber"})[0]
          > V.trade({"category": "thai restaurant"})[0] and V.score({"category": "barber", "phone": "3015550100", "web": {"verdict": "site_down"}})
          > V.score({"category": "barber"}) and V.trade({"name": "Tasty Thai Kitchen", "category": "thai_restaurant"})[0] == 1)
    # e. site-down proof (tools/site_down_proof.py): what failed + when; parked / for-sale pages get their own honest opener
    from tools import site_down_proof as SD
    from tools import first_calls as FC
    cls = [SD.classify("dns", ""), SD.classify("TimeoutError", ""), SD.classify("ssl", ""), SD.classify(404, "<h1>Not Found</h1>"),
           SD.classify(503, ""), SD.classify(200, "<p>This domain is for sale! Make an offer</p>"), SD.classify(200, "<p>This web page is parked FREE, courtesy of GoDaddy</p>"),
           SD.classify(200, "<h1>Joe's Roofing</h1>"), SD.classify(403, "")]
    check("e. reasons: dns_gone, timeout, ssl, not_found, server_error, for_sale, parked; a real page / 403 = up",
          cls == ["dns_gone", "timeout", "ssl", "not_found", "server_error", "for_sale", "parked", "up", "up"], cls)
    pl = SD.proof_line("joesroofing.com", "dns_gone", "2026-11-22T05:57Z", "2026-11-22T07:00Z")
    check("e. the proof line the caller reads out: domain, plain reason, two check times in ET",
          pl == "Your site joesroofing.com didn't load: the address no longer points anywhere. Checked Sun 11-22 12:57am and 2am ET.", pl)
    with tempfile.TemporaryDirectory() as t:
        p = os.path.join(t, "counties", "x.json")
        os.makedirs(os.path.dirname(p))
        json.dump({"leads": [{"id": "a", "name": "A Roofing", "web": {"verdict": "site_down", "url": "http://aroof.com", "checked2": "2026-11-22T05:57Z"}},
                             {"id": "b", "name": "B HVAC", "web": {"verdict": "site_down", "url": "http://bhvac.com"}},
                             {"id": "c", "name": "C Plumbing", "web": {"verdict": "site_down", "url": "http://cplumb.com"}}]}, open(p, "w"))
        fake = {"http://aroof.com": ("dns", ""), "http://bhvac.com": (200, "<h1>B HVAC</h1>"), "http://cplumb.com": (200, "Buy this domain")}
        r = SD.run([p], fetcher=lambda u: fake[u], now="2026-11-22T07:00Z")
        d = {L["id"]: L for L in json.load(open(p))["leads"]}
    check("e. a re-check: a site that answers again is dropped; the rest store reason + proof", r["came_back_up"] == 1 and "b" not in d
          and d["a"]["web"]["reason"] == "dns_gone" and "12:57am and 2am" in d["a"]["web"]["proof"] and d["c"]["web"]["reason"] == "for_sale", (r, d))
    op = FC.opener_for({"web": {"reason": "for_sale", "domain": "cplumb.com"}}, "site_down", "C Plumbing")
    check("e. a for-sale / parked domain gets its own opener naming the old address", "cplumb.com" in op and "for sale" in op
          and FC.opener_for({"web": {"reason": "dns_gone"}}, "site_down", "A").startswith("I tried your website"), op)
    # c. the committed results
    import glob
    leads = [x for p in glob.glob(os.path.join(W.TOWNS_DIR, "*.json")) for x in json.load(open(p))["leads"]]
    from tools import site_factory as F
    sites = {s["id"] for s in json.load(open(os.path.join(F.WEB, "factory", "sites.json")))["sites"]}
    has = [L for L in leads if (L.get("web") or {}).get("verdict") == "has_site"]
    check("c. every committed lead has an Overture verdict", all((L.get("web") or {}).get("verdict") in ("has_site", "site_down", "none") for L in leads))
    check("c. leads with a working site get no concept site and are not on the call lists",
          not any(L["id"] in sites for L in has) and not any(r["id"] in {L["id"] for L in has}
                                                            for r in json.load(open(os.path.join(F.WEB, "portal", "first100.json")))["leads"]), len(has))
    check("c. no Overture-sourced lead carries an email", all(not L.get("email") for L in leads if L.get("source") == "overture"))
    fl = json.load(open(os.path.join(F.WEB, "portal", "first100.json")))
    check("c. first100: lanes (no_site / site_down) with an opener each, the OSM + Overture credit",
          {r["lane"] for r in fl["leads"]} <= {"no_site", "site_down"} and all(r["opener"] for r in fl["leads"]) and "Overture" in fl["credit"])
    print(f"{sum(RES)} passed, {len(RES) - sum(RES)} failed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
