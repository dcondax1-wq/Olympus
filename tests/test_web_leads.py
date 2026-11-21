"""WEB LEADS (day-web-leads 2026-11-20): tools/web_leads.py (OpenStreetMap -> agency/leads/leads.json) + the phone list agency/leads/.
Offline: a FICTIONAL Overpass answer (tests/fixtures/web_leads_overpass.json) and a fake HTTP; no network, nobody contacted.

  t. the finder   no website tag = a lead; a real site or a chain (brand tags) or a closed / nameless place = left out; a Facebook-only
                  page counts as "no real site"; phones formatted; duplicates merged; score + heat + why + best offer + the call app's trade
  p. politeness   one query per business type, >= 1 s apart; the next public server only after a failure; a User-Agent that names no
                  person and no repo; nothing written when every server fails (stale beats invented); the OSM licence in the file
  w. the page     (node Playwright) the list from leads.json, the filters, a mark kept on the phone after a reload, "Call with script" opens the
                  call app on that business with its trade's script; no leads.json = one plain sentence; 44 px taps, no sideways scroll

  python -X utf8 -m tests.test_web_leads
"""
from __future__ import annotations

import json
import urllib.parse
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import web_leads as W  # noqa: E402

FX = os.path.join(ROOT, "tests", "fixtures", "web_leads_overpass.json")
RES: list = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + ("" if cond else f"  -> {str(info)[:600]}"), flush=True)
    return bool(cond)


def part_finder():
    out = W.build({"Frederick": json.load(open(FX, encoding="utf-8"))})
    by = {L["name"]: L for L in out["leads"]}
    check("t1. leads = named, non-chain, open businesses with no real website: the plumber, the nail salon (Facebook only), the auto shop, the gym (Facebook as its 'website')",
          set(by) == {"Example Plumbing Co (fictional)", "Test Nails (fictional)", "Placeholder Auto (fictional)", "Mock Gym (fictional)"}, sorted(by))
    check("t2. left out and counted: a real website, a chain (brand tags), no name, closed (disused), a duplicate",
          out["skipped"] == {"has_site": 1, "chain": 1, "no_name": 1, "closed": 1, "duplicate": 1}, out["skipped"])
    p = by["Example Plumbing Co (fictional)"]
    check("t3. the plumber: hot (no site + phone + hours + street + a trade), phone (301) 555-0101, contractor -> the call app's 'contractor' script, a lead-site offer, the OSM link",
          p["heat"] == "hot" and p["score"] == 10 and p["phone"] == "(301) 555-0101" and p["trade"] == "contractor" and "quote form" in p["offer"]
          and p["osm"] == "https://www.openstreetmap.org/node/1001" and p["address"].startswith("12 Sample St") and len(p["why"]) == 5, p)
    n, a, g = by["Test Nails (fictional)"], by["Placeholder Auto (fictional)"], by["Mock Gym (fictional)"]
    check("t4. Facebook only = 'only a Facebook page' (one point less); no phone = still listed, never hot; phones in any format -> (301) 555-01xx",
          n["facebook"] and "only a Facebook page" in n["why"][0] and n["trade"] == "salon" and n["phone"] == "(301) 555-0104"
          and a["phone"] == "" and a["heat"] != "hot" and g["phone"] == "(301) 555-0108" and g["trade"] == "fitness", (n, a, g))
    check("t5. sorted best first; the file says where it comes from and carries the OSM licence; demo false (real runs)",
          out["leads"][0]["name"] == "Example Plumbing Co (fictional)" and "OpenStreetMap" in out["license"] and "ODbL" in out["license"]
          and out["demo"] is False and out["kind"] == "web_leads" and out["towns"][0]["leads"] == 4, out["towns"])


def part_polite(tmp):
    calls, sleeps = [], []

    def http(url, body):
        calls.append(url.split("/")[2])
        if "overpass-api.de" in url:
            return 504, b""
        return 200, json.dumps({"elements": [{"type": "node", "id": len(calls), "tags": {"name": f"X{len(calls)}", "craft": "roofer", "phone": "301-555-0199"}}]}).encode()
    j = W.fetch("Frederick", W.TOWNS["Frederick"], http=http, sleep=sleeps.append, say=lambda *a: None, backoff=(20,))
    parts = len(W.parts(W.TOWNS["Frederick"]))
    check(f"p1. {parts} small queries for a town (the 6 business types, the big ones split: one union times out on the public gateways); "
          "a busy main server (504) is asked once more after a 20 s wait, then the mirror; >= 1 s between any two requests",
          j and j["_parts_ok"] == parts and calls.count("overpass-api.de") == 2 * parts and calls.count("maps.mail.ru") == parts
          and "overpass.kumi.systems" not in calls and sleeps.count(20) == parts and min(sleeps) >= 1.0 and j["_failed"] == [], (calls[:6], sleeps[:6]))
    calls.clear()

    def http2(url, body):
        calls.append(url.split("/")[2])
        if '"craft"' in urllib.parse.unquote_plus(body.decode()):
            return 200, b'{"elements": []}'
        raise ConnectionResetError()
    j2 = W.fetch("Frederick", W.TOWNS["Frederick"], http=http2, sleep=lambda s: None, say=lambda *a: None, backoff=(20,))
    check("p1b. a refused connection is not asked again (no backoff); the kinds no server answered are listed (the PC run fills them)",
          j2 and j2["_parts_ok"] == 1 and len(j2["_failed"]) == parts - 1 and "trades" not in j2["_failed"] and len(calls) == 1 + 3 * (parts - 1), (j2 and j2["_failed"], len(calls)))
    check("p2. the User-Agent names the tool only: no person, no email, no repository", "olympus-web-leads" in W.UA and "@" not in W.UA
          and "github" not in W.UA.lower() and "dcondax" not in W.UA.lower(), W.UA)
    out = os.path.join(tmp, "leads.json")
    with open(out, "w") as fh:
        fh.write('{"keep": 1}')
    orig = W.fetch
    W.fetch = lambda *a, **k: None
    try:
        rc = W.main(["--town", "Frederick", "--out", out])
    finally:
        W.fetch = orig
    check("p3. every server failed: exit 2 and the old leads.json is left as it was (stale beats invented)", rc == 2 and json.load(open(out)) == {"keep": 1}, rc)
    rc = W.main(["--town", "Frederick", "--from-file", FX, "--out", out])
    check("p4. --from-file (offline) writes the list", rc == 0 and len(json.load(open(out))["leads"]) == 4)
    sm = json.load(open(os.path.join(tmp, "summary.json")))
    L = json.load(open(out))["leads"]
    check("p4b. summary.json beside it for the Agency HQ tile {n, label, next, t, pipe}; offers carry the research prices (starter site $1,500, gym site + 3D $2,500)",
          sm["n"] == 4 and sm["label"] == "4 leads found" and sm["pipe"] == {"leads": 4, "called": 0} and "hot" in sm["next"]
          and all(x["offer_usd"] in (1500, 2500) and "$" in x["offer"] for x in L) and next(x for x in L if x["niche"] == "fitness")["offer_usd"] == 2500, (sm, [x["offer"] for x in L]))
    q = W.parts(None, "Bel Air")[0]
    check("p5. a town without a preset box: the town's area by name inside Maryland (US-MD)", 'area["name"="Bel Air"]' in q and '"ISO3166-2"="US-MD"' in q, q)


def part_page(tmp):
    out = os.path.join(tmp, "leads.json")
    W.main(["--town", "Frederick", "--from-file", FX, "--out", out])
    js = os.path.join(ROOT, "tests", "web_leads_page.cjs")
    try:
        # tests/browser_lock: run_area already holds the lock around this suite (an outer `flock` here waited on its own parent until the
        # 600 s timeout: QUALITY 2026-11-21); by hand it takes the lock itself
        sys.path.insert(0, os.path.join(ROOT, "tests"))
        import browser_lock
        with browser_lock.hold(browser_lock.DEFAULT, 2400):
            r = subprocess.run(["node", js, os.path.join(ROOT, "tools", "web_public"), out], capture_output=True, text=True, timeout=600)
    except Exception as e:  # noqa: BLE001
        check("w. the browser harness ran", False, e)
        return
    try:
        steps = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        check("w. the browser harness ran", False, (r.stdout[-500:], r.stderr[-800:]))
        return
    for name, ok, info in steps:
        check("w. " + name, ok, info)


def part_run(tmp):
    out = os.path.join(tmp, "run", "leads.json")
    fx = json.load(open(FX, encoding="utf-8"))
    W.main(["--town", "Frederick", "--from-file", FX, "--out", out])
    fx2 = {"elements": [dict(e, id=e["id"] + 9000) for e in fx["elements"]] + [{"type": "node", "id": 5001, "tags": {"name": "Hagerstown Roofing (fictional)", "craft": "roofer", "phone": "301-555-0150"}}]}
    f2 = os.path.join(tmp, "fx2.json")
    json.dump(fx2, open(f2, "w"))
    W.main(["--town", "Hagerstown", "--from-file", f2, "--out", out])
    j = W.load(out)
    by = {t["town"]: t for t in j["towns"]}
    check("r1. town by town: Hagerstown is added and Frederick kept; the same businesses (same name + phone) are not listed twice (5 leads, not 9)",
          set(by) == {"Frederick", "Hagerstown"} and len(j["leads"]) == 5 and by["Hagerstown"]["leads"] == 5 and sum(1 for x in j["leads"] if x["town"] == "Frederick") == 4, (by, len(j["leads"])))
    W.main(["--town", "Frederick", "--from-file", FX, "--out", out])
    j = W.load(out)
    check("r2. running a town again replaces only that town (still 2 towns, Frederick's 4 back)", len(j["towns"]) == 2 and sum(1 for x in j["leads"] if x["town"] == "Frederick") == 4, [t["town"] for t in j["towns"]])
    t = W.counts(j)
    check("r3. the counts table: one row per town + All, a column per niche, the kinds still missing", "| Frederick |" in t and "| Hagerstown |" in t and "**All**" in t
          and "Contractor / trades" in t and "Kinds missing" in t, t)
    big = {"v": 1, "kind": "web_leads", "towns": [{"town": "A"}, {"town": "B"}], "skipped": {}, "leads": [{"id": f"x{i}", "name": "N" * 200, "town": "A" if i % 2 else "B", "score": 1} for i in range(2000)]}
    bp = os.path.join(tmp, "big", "leads.json")
    W.save(big, bp)
    idx = json.load(open(bp))
    back = W.load(bp)
    check("r4. over 300 KB: leads.json becomes an index with one file per town (towns/a.json, towns/b.json), read back whole",
          idx.get("files") == ["towns/a.json", "towns/b.json"] and idx["leads"] == [] and idx["count"] == 2000 and len(back["leads"]) == 2000
          and os.path.getsize(bp) < 300_000, (idx.get("files"), os.path.getsize(bp)))
    W.main(["--town", "Frederick", "--from-file", FX, "--out", out])
    tt = next(x for x in W.load(out)["towns"] if x["town"] == "Frederick")
    check("r5. each town records the kinds answered / missing (offline file = all answered by convention: parts_ok None -> not 'done')", "missing" in tt and "parts" in tt, tt)


def part_post(tmp):
    """Postcards (lead 2026-11-20): chains dropped (tags + names), email kept, the map point kept, missing streets filled by
    Nominatim reverse (1 a second, cached), mailable = house number + street + town + ZIP."""
    els = [{"type": "node", "id": 1, "lat": 39.41, "lon": -77.41, "tags": {"name": "Glory Days Grill", "amenity": "restaurant"}},
           {"type": "node", "id": 2, "lat": 39.41, "lon": -77.41, "tags": {"name": "Sample Cafe (fictional)", "amenity": "cafe", "operator": "Starbucks"}},
           {"type": "node", "id": 3, "lat": 39.4143, "lon": -77.4105, "tags": {"name": "Example Bakery (fictional)", "shop": "bakery", "contact:email": "hi@example.com"}},
           {"type": "way", "id": 4, "center": {"lat": 39.42, "lon": -77.42}, "tags": {"name": "Demo Tailor (fictional)", "shop": "tailor", "addr:housenumber": "5",
            "addr:street": "Main Street", "addr:city": "Frederick", "addr:postcode": "21701-1234", "contact:phone": "301-555-0177"}}]
    out = W.build({"Frederick": {"elements": els}})
    by = {L["name"]: L for L in out["leads"]}
    check("q1. chains dropped by name (Glory Days) and by operator (a cafe run by Starbucks); counted per town",
          set(by) == {"Example Bakery (fictional)", "Demo Tailor (fictional)"} and out["towns"][0]["chains"] == 2, (sorted(by), out["towns"][0]))
    b, t = by["Example Bakery (fictional)"], by["Demo Tailor (fictional)"]
    check("q2. contact:email kept (+1 score), contact:phone kept, the map point kept (way = its center); a full map address with ZIP = mailable",
          b["email"] == "hi@example.com" and "an email on the map" in b["why"] and b["lat"] == 39.4143 and t["lat"] == 39.42 and t["phone"] == "(301) 555-0177"
          and t["mailable"] is True and t["zip"] == "21701" and t["address"] == "5 Main Street, Frederick MD 21701" and b["mailable"] is False, (b, t))
    calls, sleeps = [], []

    def http(url, body):
        calls.append(url)
        return 200, json.dumps({"address": {"house_number": "9", "road": "East Patrick Street", "city": "Frederick", "postcode": "21701", "state": "Maryland"}}).encode()
    cache = os.path.join(tmp, "geo.json")
    st = W.geocode(out["leads"], cache, http=http, sleep=sleeps.append, say=lambda *a: None)
    check("q3. Nominatim reverse only for the lead with no street (1 call, nearest address marked, now mailable); the tailor's own address untouched",
          st["asked"] == 1 and len(calls) == 1 and "nominatim.openstreetmap.org/reverse" in calls[0] and "lat=39.414300" in calls[0]
          and b["street"] == "9 East Patrick Street" and b["addr_src"] == "nearest" and b["mailable"] and t["addr_src"] == "map", (st, b))
    b2 = dict(b, street="", mailable=False, addr_src="")
    st2 = W.geocode([b2, dict(b2, id="z", lat=39.5, lon=-77.5)], cache, http=http, sleep=sleeps.append, say=lambda *a: None)
    check("q4. the cache: the same point is not asked again; a new point waits until 1.1 s after the previous request, across runs (Nominatim: max 1 a second)",
          st2["cached"] == 1 and st2["asked"] == 1 and len(calls) == 2 and len(sleeps) == 1 and sleeps[0] >= 1.0, (st2, sleeps))
    o = {"towns": [{"town": "A", "leads": 2, "hot": 0, "missing": ["food places"], "parts": 9, "parts_ok": 8, "businesses": 10}],
         "leads": [{"id": "x1", "town": "A", "name": "One", "phone": "1", "heat": "warm"}, {"id": "x2", "town": "A", "name": "Two", "phone": "2", "heat": "hot"}]}
    n = {"towns": [{"town": "A", "leads": 1, "hot": 0, "missing": ["trades"], "parts": 9, "parts_ok": 8, "businesses": 4}],
         "leads": [{"id": "x1", "town": "A", "name": "One", "phone": "1", "heat": "hot"}, {"id": "x3", "town": "A", "name": "Three", "phone": "3", "heat": "warm"}]}
    m = W.merge(o, n)
    ta = m["towns"][0]
    check("q6. asking a town again ADDS (the 2026-11-20 run shrank Frederick 180 -> 75): old business kept, new one added, the same one updated, "
          "a kind missing only if both runs missed it, counts recounted",
          sorted(x["id"] for x in m["leads"]) == ["x1", "x2", "x3"] and next(x for x in m["leads"] if x["id"] == "x1")["heat"] == "hot"
          and ta["missing"] == [] and ta["leads"] == 3 and ta["hot"] == 2 and ta["businesses"] == 10 and ta["parts_ok"] == 9, (m["leads"], ta))
    t3 = W.counts({"towns": out["towns"], "leads": out["leads"]})
    check("q5. the counts table has Chains dropped, Phone, Email, Mailable", all(w in t3 for w in ("Chains dropped", "| Phone |", "| Email |", "| Mailable |")) and "| Frederick | 2 | 2 |" in t3, t3)


def main():
    tmp = tempfile.mkdtemp(prefix="webleads-")
    part_finder()
    part_polite(tmp)
    part_run(tmp)
    part_post(tmp)
    part_page(tmp)
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
