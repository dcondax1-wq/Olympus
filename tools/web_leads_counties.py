"""No-website leads beyond Frederick (lead 2026-11-22: 'find big leads'), from Overture Maps, by county.

    python tools/web_leads_counties.py                     the 8 counties -> agency/leads/counties/<county>.json + COUNTS.md
    python tools/web_leads_counties.py --top 1000          how many of the NEW leads get a concept site (repo size), by $ score
    python tools/web_leads_counties.py --no-http           skip the site checks (no site_down lane)

Counties: Baltimore County, Baltimore City, Anne Arundel, Howard, Montgomery, Prince George's, Harford, Carroll (county outlines =
Overture divisions). Same rules as the town search (tools/web_leads_overture.py): open, no chain / brand, a trade we sell to, a phone,
no website, no Overture email. Plus the site_down lane: places in high-ticket trades whose own website does not load.
Every lead gets usd_score (tools/lead_value.py). Leads already in the 16-town list are skipped. The do-not-call scrub runs on the PC
(tools/first_calls.py: the caller portal's never-again list + agency/calls opt-outs / registry-listed numbers).
"""
from __future__ import annotations

import concurrent.futures as cf
import datetime as dt
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import lead_value as V  # noqa: E402
from tools import site_factory as F  # noqa: E402
from tools import web_leads_overture as W  # noqa: E402

COUNTIES = ["Baltimore County", "Baltimore", "Anne Arundel County", "Howard County", "Montgomery County", "Prince George's County",
            "Harford County", "Carroll County"]
LABEL = {"Baltimore": "Baltimore City"}
OUT_DIR = os.path.join(F.WEB, "leads", "counties")
COUNTS_MD = os.path.join(ROOT, "research", "handoff", "2026-11-22", "leads", "COUNTS.md")
PLACES = os.path.join(W.CACHE, "places_central_2026-11-18.0.parquet")
COUNTY_SHAPES = os.path.join(W.CACHE, "md_counties.parquet")
SITE_CHECK_MIN_VALUE = 7          # check websites only for trades worth >= this (roofing ... auto / dental): the site_down lane


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def fetch(release="2026-11-18.0"):
    """central Maryland places + the Maryland county outlines -> scratch/overture/ (anonymous S3, a few seconds each)"""
    import duckdb
    os.makedirs(W.CACHE, exist_ok=True)
    for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        os.environ.pop(k, None)
    c = duckdb.connect()
    c.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial; CREATE SECRET anon (TYPE s3, PROVIDER config, KEY_ID '', SECRET '', REGION 'us-west-2');")
    if not os.path.exists(COUNTY_SHAPES):
        c.execute(f"""COPY (SELECT names.primary AS county, ST_AsWKB(geometry) AS wkb FROM
          read_parquet('s3://overturemaps-us-west-2/release/{release}/theme=divisions/type=division_area/*')
          WHERE country='US' AND region='US-MD' AND subtype='county' AND is_land) TO '{COUNTY_SHAPES}' (FORMAT parquet)""")
    if not os.path.exists(PLACES):
        c.execute(f"""COPY (SELECT id, names.primary AS name, websites, phones, basic_category AS cat, taxonomy.primary AS tax,
          addresses[1].freeform AS street, addresses[1].locality AS town, addresses[1].postcode AS zip, addresses[1].region AS region,
          (bbox.xmin+bbox.xmax)/2 AS lon, (bbox.ymin+bbox.ymax)/2 AS lat, confidence, operating_status, brand.wikidata AS brand_wd
          FROM read_parquet('s3://overturemaps-us-west-2/release/{release}/theme=places/type=place/*')
          WHERE bbox.xmin BETWEEN -77.55 AND -75.95 AND bbox.ymin BETWEEN 38.53 AND 39.73) TO '{PLACES}' (FORMAT parquet)""")


def candidates(places_path=PLACES, shapes_path=COUNTY_SHAPES, counties=COUNTIES) -> list:
    """the places in the counties that could be leads: open, a phone, a sellable trade, no brand (website or not: decided after)"""
    import duckdb
    c = duckdb.connect()
    c.execute("INSTALL spatial; LOAD spatial;")
    cats = ", ".join("'" + k + "'" for k in W.NICHE)
    names = ", ".join("'" + x.replace("'", "''") + "'" for x in counties)
    q = f"""SELECT p.*, s.county FROM read_parquet('{places_path}') p JOIN
            (SELECT county, ST_GeomFromWKB(wkb) g FROM read_parquet('{shapes_path}') WHERE county IN ({names})) s
            ON ST_Contains(s.g, ST_Point(p.lon, p.lat))
            WHERE p.phones IS NOT NULL AND len(p.phones) > 0 AND (p.operating_status IS NULL OR p.operating_status = 'open')
              AND p.brand_wd IS NULL AND p.cat IN ({cats}) AND coalesce(p.confidence, 0) >= 0.4"""
    cols = [d[0] for d in c.execute(f"DESCRIBE {q}").fetchall()]
    return [dict(zip(cols, r)) for r in c.execute(q).fetchall()]


def lead_of(p: dict, county: str, today: str, verdict="none", url="") -> dict:
    niche = W.NICHE[p["cat"]]
    ph = next((W.phone10(x) for x in (p.get("phones") or []) if W.phone10(x)), "")
    street = str(p.get("street") or "").strip()[:80]
    zipc = (re.match(r"\d{5}", str(p.get("zip") or "")) or [""])[0]
    town = str(p.get("town") or "").strip()[:40] or LABEL.get(county, county)
    L = {"id": "ovt-" + p["id"][:24], "name": str(p["name"]).strip()[:80], "niche": {"gym": "fitness", "trades": "contractor"}.get(niche, niche),
         "niche_name": W.NICHE_NAME[niche], "kind": "overture=" + str(p.get("cat")), "town": town, "city": town, "county": LABEL.get(county, county),
         "state": "MD", "phone": W.fmt_phone(ph), "email": "", "street": street, "zip": zipc,
         "address": (street + ", " + town + (" MD " + zipc if zipc else ""))[:120] if street else "", "lat": round(p["lat"], 6), "lon": round(p["lon"], 6),
         "mailable": bool(re.match(r"\d+\w?\s+\S+", street) and zipc), "hours": "", "category": str(p.get("tax") or p.get("cat") or "").replace("_", " ")[:40],
         "heat": "hot" if street else "warm", "source": "overture", "web": {"verdict": verdict, "src": "overture", "checked": today}}
    if url:
        L["web"]["url"] = url
    L["usd_score"] = V.score(L)
    L["trade"] = V.trade(L)[1]
    return L


def run(places_path=PLACES, shapes_path=COUNTY_SHAPES, out_dir=OUT_DIR, checker=W.http_ok, top=1000, today=None, write=True, threads=48) -> dict:
    today = today or dt.date.today().isoformat()
    existing = [x for p in glob.glob(os.path.join(F.WEB, "leads", "towns", "*.json")) for x in json.load(open(p))["leads"]]
    have_ids = {x["id"][4:] for x in existing if str(x.get("id", "")).startswith("ovt-")}
    grid = W.Grid([{"id": x["id"], "name": x["name"], "lat": x["lat"], "lon": x["lon"]} for x in existing if x.get("lat") is not None])
    cands = candidates(places_path, shapes_path)
    leads, to_check, dropped = [], [], Counter()
    for p in cands:
        if p["id"] in have_ids or W.F.chain_of(p.get("name")) or not W.phone10((p.get("phones") or [""])[0] if p.get("phones") else ""):
            dropped["already listed / chain / bad phone"] += 1
            continue
        if any(W.meters(p["lat"], p["lon"], q["lat"], q["lon"]) <= W.MATCH_M and W.same_name(p["name"], q["name"]) for q in grid.near(p["lat"], p["lon"])):
            dropped["already listed / chain / bad phone"] += 1
            continue
        if p.get("websites"):
            site = next((u for u in p["websites"] if W.domain_is_theirs(u, p["name"])), "")
            probe = {"category": str(p.get("tax") or p.get("cat") or ""), "name": p["name"], "niche": W.NICHE[p["cat"]]}
            if site and V.trade(probe)[0] >= SITE_CHECK_MIN_VALUE and checker is not None:
                to_check.append((p, site))
            else:
                dropped["has a website"] += 1
            continue
        leads.append(lead_of(p, p["county"], today))
    if to_check:
        with cf.ThreadPoolExecutor(max_workers=threads) as ex:
            for (p, site), (ok, st) in zip(to_check, ex.map(lambda t: checker(t[1]), to_check)):
                if ok:
                    dropped["has a website (checked, up)"] += 1
                else:
                    L = lead_of(p, p["county"], today, "site_down", site)
                    L["web"]["status"] = st
                    L["why"] = ["their website does not load", "a phone to call"]
                    leads.append(L)
    leads.sort(key=lambda L: (-L["usd_score"], L["county"], L["name"].lower()))
    for i, L in enumerate(leads):
        L["build_site"] = i < top                   # only the top N get a concept site (repo size); the rest wait for their turn
    by = defaultdict(list)
    for L in leads:
        by[L["county"]].append(L)
    if write:
        os.makedirs(out_dir, exist_ok=True)
        for cty, ls in by.items():
            with open(os.path.join(out_dir, slug(cty) + ".json"), "w", encoding="utf-8") as f:
                json.dump({"v": 1, "kind": "web_leads_county", "county": cty, "built": today, "license": W.CREDIT,
                           "about": "Overture Maps places with a phone and no website (or a website that does not load), open, not a chain. "
                                    "Maps can be out of date: check before you call.", "leads": ls}, f, separators=(",", ":"))
                f.write("\n")
    return {"candidates": len(cands), "leads": len(leads), "site_checked": len(to_check), "dropped": dict(dropped), "by_county": {k: len(v) for k, v in by.items()},
            "top": top, "leads_list": leads}


def counts_md(res: dict, path=COUNTS_MD):
    leads = res["leads_list"]
    trades = [t for t, _ in Counter(L["trade"] for L in leads).most_common()]
    rows = defaultdict(Counter)
    for L in leads:
        rows[L["county"]][L["trade"]] += 1
    lines = ["# Big leads beyond Frederick: counts by county and trade (Overture Maps, 2026-11-18.0 release)", "",
             f"{res['leads']:,} new leads with a phone in 8 counties ({sum(L['web']['verdict'] == 'site_down' for L in leads):,} of them in the "
             f"'your website is down' lane). Top {res['top']:,} by $ score got a concept site. Sorted high-ticket trades first. "
             "Overture has no ratings / review counts, so they are not in the score.", "",
             "| County | Leads | site down | concept sites | " + " | ".join(trades) + " |", "|---|---|---|---|" + "---|" * len(trades)]
    for cty in sorted(rows, key=lambda c: -sum(rows[c].values())):
        ls = [L for L in leads if L["county"] == cty]
        lines.append(f"| {cty} | {len(ls):,} | {sum(L['web']['verdict'] == 'site_down' for L in ls)} | {sum(L['build_site'] for L in ls)} | "
                     + " | ".join(str(rows[cty][t]) for t in trades) + " |")
    tot = Counter(L["trade"] for L in leads)
    lines.append(f"| **All** | **{len(leads):,}** | **{sum(L['web']['verdict'] == 'site_down' for L in leads)}** | **{sum(L['build_site'] for L in leads)}** | "
                 + " | ".join(f"**{tot[t]}**" for t in trades) + " |")
    lines += ["", "## Top 25 by $ score", "", "| # | Business | Trade | County | Lane | Score |", "|---|---|---|---|---|---|"]
    for i, L in enumerate(leads[:25], 1):
        lines.append(f"| {i} | {L['name']} | {L['trade']} | {L['county']} | {L['web']['verdict'].replace('none', 'no site')} | {L['usd_score']} |")
    lines += ["", (f"Dropped: {json.dumps(res['dropped'])}. " if res.get("dropped") else "")
              + "Data (c) Overture Maps Foundation (CDLA-Permissive-2.0 / ODbL). site_down = the business's own domain did not load "
                "(DNS gone, error page, or no answer in 20 s on a second try).", ""]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def rerank(top=1000, out_dir=OUT_DIR, write=True) -> dict:
    """after a recheck edits the county files: the top N by $ score across ALL counties get build_site; COUNTS.md again"""
    files = sorted(glob.glob(os.path.join(out_dir, "*.json")))
    docs = {p: json.load(open(p, encoding="utf-8")) for p in files}
    leads = sorted((L for d in docs.values() for L in d["leads"]), key=lambda L: (-L["usd_score"], L["county"], L["name"].lower()))
    for i, L in enumerate(leads):
        L["build_site"] = i < top
    if write:
        for p, d in docs.items():
            d["leads"].sort(key=lambda L: (-L["usd_score"], L["name"].lower()))
            with open(p, "w", encoding="utf-8") as f:
                json.dump(d, f, separators=(",", ":"))
                f.write("\n")
    return {"leads": len(leads), "top": top, "leads_list": leads, "dropped": {}}


def main(argv) -> int:
    top = int(argv[argv.index("--top") + 1]) if "--top" in argv else 1000
    if "--rerank" in argv:
        res = rerank(top)
        counts_md(res)
        print(f"reranked {res['leads']} county leads, top {top} build a site")
        return 0
    fetch()
    res = run(checker=None if "--no-http" in argv else W.http_ok, top=top)
    counts_md(res)
    print(json.dumps({k: v for k, v in res.items() if k != "leads_list"}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
