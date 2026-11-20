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
    j = W.fetch("Frederick", W.TOWNS["Frederick"], http=http, sleep=sleeps.append, say=lambda *a: None)
    parts = len(W.parts(W.TOWNS["Frederick"]))
    check(f"p1. {parts} small queries for a town (one per business type; one big union times out on the public gateways), each tried on the main server first, "
          "the next server only after a failure, >= 1 s between any two requests",
          j and j["_parts_ok"] == parts and calls.count("overpass-api.de") == parts and calls.count("maps.mail.ru") == parts
          and "overpass.kumi.systems" not in calls and len(sleeps) == 2 * parts - 1 and min(sleeps) >= 1.0, (calls, sleeps))
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
        r = subprocess.run(["flock", "-w", "2400", "/tmp/olympus_browser.lock", "node", js, os.path.join(ROOT, "tools", "web_public"), out],
                           capture_output=True, text=True, timeout=600)
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


def main():
    tmp = tempfile.mkdtemp(prefix="webleads-")
    part_finder()
    part_polite(tmp)
    part_page(tmp)
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
