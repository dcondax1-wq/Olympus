"""LEAD FINDER: local businesses that need a website, scored, with one plain 'why they need a new site' line each.

    python -m agency.leads --city "Fort Collins, CO"                         every trade, 8 km around the centre, top 20
    python -m agency.leads --city "Boise, ID" --categories barber,plumber,hvac --radius-km 12 --top 30
    python -m agency.leads --center 40.585,-105.084 --no-audit                no city search, no website checks

Writes <out>/leads.json + leads.csv (the day's top list, the input of the site builder, the pitch kit and the Agency
page) and <out>/all_leads.csv (everything found). Default <out> = agency/out/<city>/ (gitignored).

Score (0-100) = NEED (0-70: no website = 70; a broken / outdated one = its problems added up, at most 65)
              + REACH (0-20: a phone number 15, a street address 5)
              + VALUE (0-10: what a site is worth to that trade; roofers and plumbers 10, cafes 4).
Tier A >= 80 (call first), B 60-79, C < 60.

Honest about the data: OpenStreetMap is volunteer-made. It misses many businesses, and "no website on OSM" can mean OSM
simply does not know their site: always search the name on Google before you call (10 seconds). Each run prints and
stores how complete the data was (share with a phone / website / hours / street address).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import glob
import json
import os
import re
import sys

from . import ATTRIBUTION, OUT_DIR, ensure_dir
from . import audit as A
from . import categories as C
from . import config as CFG
from . import hours as H
from . import osm

NEED_NO_SITE = 70
NEED_CAP = 65
NEED_UNCHECKED = 25


def tier(score: int) -> str:
    return "A" if score >= 80 else "B" if score >= 60 else "C"


def score(lead: dict, audit=None) -> dict:
    """Pure: a lead (+ its site audit) -> {score, tier, need, reach, value, issues, why, reasons, site_status}."""
    cat = C.BY_KEY[lead["category"]]
    city = lead["address"].get("city") or "town"
    issues = []
    if not lead.get("website"):
        need, status = NEED_NO_SITE, "none"
        issues.append(A.issue("no_site", NEED_NO_SITE, "No website listed on OpenStreetMap (search the name on Google before you call)"))
        why = f"No website found: people who search '{cat.words[0] if cat.words else cat.label.lower()} {city}' on their phone find a competitor first."
    elif audit is None:
        need, status = NEED_UNCHECKED, "unchecked"
        why = "Has a website that was not checked yet."
    else:
        issues = list(audit.get("issues", []))
        need = min(NEED_CAP, sum(i["weight"] for i in issues))
        status = "bad" if need >= 30 else "fair" if need >= 10 else "good"
        if audit.get("note") and not issues:
            need, status = NEED_UNCHECKED, "unchecked"
            why = audit["note"] + "."
        elif not issues:
            why = "Their current site looks fine: a weak lead for a new site (maybe a care plan)."
        else:
            top = [i["text"] for i in sorted(issues, key=lambda i: -i["weight"])[:2]]
            why = top[0] + ("; " + top[1][0].lower() + top[1][1:] if len(top) > 1 else "") + "."
    reach = (15 if lead.get("phone_e164") else 0) + (5 if lead["address"].get("has_street") else 0)
    value = cat.value
    s = max(0, min(100, need + reach + value))
    reasons = [i["text"] for i in sorted(issues, key=lambda i: -i["weight"])]
    if not lead.get("phone_e164"):
        reasons.append("No phone number on OpenStreetMap: visit in person or find the number on Google")
    return {"score": s, "tier": tier(s), "need": need, "reach": reach, "value": value, "site_status": status,
            "issues": issues, "reasons": reasons, "why": why[:220]}


def pick(leads, top=20, per_category=3, redesign_share=0.0):
    """The day's list: best score first (then nearest), at most per_category of one trade so the list stays varied.

    redesign_share keeps up to that share of the list for businesses whose current site is bad (a different pitch: they
    already pay for a site, so they know what one is worth); those count against their own per-trade cap."""
    ranked = sorted(leads, key=lambda l: (-l["score"], l["distance_km"], l["name"]))
    out, per, per_re = [], {}, {}
    for l in ranked:
        if len(out) >= round(top * redesign_share):
            break
        if l.get("site_status") == "bad" and per_re.get(l["category"], 0) < per_category:
            out.append(l)
            per_re[l["category"]] = per_re.get(l["category"], 0) + 1
    for l in ranked:
        if len(out) >= top:
            break
        if l in out or per.get(l["category"], 0) >= per_category:
            continue
        out.append(l)
        per[l["category"]] = per.get(l["category"], 0) + 1
    if len(out) < top:                                   # not enough variety: fill with the next best
        for l in ranked:
            if l not in out:
                out.append(l)
                if len(out) >= top:
                    break
    out.sort(key=lambda l: (-l["score"], l["distance_km"], l["name"]))
    return out


def coverage(leads) -> dict:
    n = len(leads) or 1
    return {
        "n": len(leads),
        "phone": round(sum(1 for l in leads if l["phone_e164"]) / n, 3),
        "website": round(sum(1 for l in leads if l["website"]) / n, 3),
        "hours": round(sum(1 for l in leads if l["opening_hours"]) / n, 3),
        "street_address": round(sum(1 for l in leads if l["address"]["has_street"]) / n, 3),
        "email": round(sum(1 for l in leads if l["email"]) / n, 3),
    }


def enrich(lead: dict, audit=None) -> dict:
    lead = dict(lead)
    lead.update(score(lead, audit))
    if audit is not None:
        lead["audit"] = {"checked": audit.get("checked"), "fetched": audit.get("fetched"), "facts": audit.get("facts", {}), "note": audit.get("note", ""),
                         "final_url": audit.get("final_url", "")}
    lead["hours"] = H.rows(H.parse(lead.get("opening_hours", "")))
    return lead


SUPPRESS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "suppress.txt")


def suppression(path=SUPPRESS_FILE, exports=None) -> dict:
    """The do-not-contact list: agency/suppress.txt (one phone, web domain, lead id or exact business name per line, # comments)
    plus every lead marked 'Do not contact' in a saved Agency-page export (agency/crm_export*.json). Both are gitignored.
    The lead finder never puts these back on a call list (CAN-SPAM: an opt-out is for good)."""
    out = {"phones": set(), "domains": set(), "ids": set(), "names": set()}
    try:
        with open(path, encoding="utf-8-sig") as fh:
            lines = fh.read().splitlines()
    except OSError:
        lines = []
    for ln in lines:
        s = ln.split("#", 1)[0].strip()
        if not s:
            continue
        digits = "".join(ch for ch in s if ch.isdigit())
        if len(digits) >= 10 and len(digits) >= len(s.replace(" ", "")) * 0.6:
            out["phones"].add(digits[-10:])
        elif re.fullmatch(r"[nwr]\d+", s):
            out["ids"].add(s)
        elif re.fullmatch(r"(?:https?://)?(?:www\.)?([a-z0-9-]+\.)+[a-z]{2,}/?\S*", s, re.I):
            out["domains"].add(re.sub(r"^(?:https?://)?(?:www\.)?", "", s.lower()).split("/")[0])
        else:
            out["names"].add(s.lower())
    folder = os.path.dirname(path)
    for p in exports if exports is not None else sorted(glob.glob(os.path.join(folder, "crm_export*.json"))):
        try:
            with open(p, encoding="utf-8") as fh:
                d = json.load(fh)
            st = d.get("state", d) if isinstance(d, dict) else {}
            out["ids"] |= {i for i, e in (st.get("leads") or {}).items() if isinstance(e, dict) and e.get("stage") == "dnc"}
        except (OSError, ValueError, AttributeError):
            continue
    return out


def suppressed(lead: dict, sup: dict) -> bool:
    host = re.sub(r"^(?:https?://)?(?:www\.)?", "", (lead.get("website") or "").lower()).split("/")[0]
    return (lead["id"] in sup["ids"] or (lead.get("phone_e164") or "")[-10:] in sup["phones"] or (host and host in sup["domains"])
            or lead["name"].lower() in sup["names"])


def run(place: dict, radius_km=8.0, keys=C.DEFAULT_KEYS, top=20, per_category=3, audit_max=30, do_audit=True, refresh=False,
        endpoint=None, fetch=None, audit_fn=None, sleep=None, log=print, redesign_share=0.25, suppress=None, extract=None):
    """Find -> drop the do-not-contact list -> score without fetching -> check the websites of the best candidates -> rescore -> pick."""
    kw = {"fetch": fetch} if fetch else {}
    if sleep:
        kw["sleep"] = sleep
    raw, meta = osm.find(place, radius_km, keys, endpoint=endpoint, refresh=refresh, extract=extract, **kw)
    sup = suppress if suppress is not None else suppression()
    kept = [l for l in raw if not suppressed(l, sup)]
    meta["skipped"]["do_not_contact"] = len(raw) - len(kept)
    raw = kept
    log(f"  found {meta['elements']} places on OpenStreetMap, kept {len(raw)} (skipped: {meta['skipped']['chain']} chains, "
        f"{meta['skipped']['duplicate']} duplicates, {meta['skipped']['do_not_contact']} on your do-not-contact list, "
        f"{meta['skipped']['no_name_or_closed'] + meta['skipped']['other_trade']} others)")
    first = [enrich(l) for l in raw]
    audited = 0
    if do_audit:
        # check the sites of those that could make the list once their site is judged (best unchecked first), politely capped
        cands = sorted((l for l in first if l["website"]), key=lambda l: (-(l["reach"] + l["value"]), l["distance_km"]))[:audit_max]
        audit_fn = audit_fn or A.audit
        by_id = {}
        for l in cands:
            try:
                by_id[l["id"]] = audit_fn(l["website"], refresh=refresh)
            except Exception as e:  # noqa: BLE001 - one bad site never stops the run
                by_id[l["id"]] = {"issues": [], "note": f"could not check it ({type(e).__name__})", "checked": dt.date.today().isoformat()}
            audited += 1
            if audited % 5 == 0:
                log(f"  checked {audited} of {len(cands)} websites")
        first = [enrich(l, by_id.get(l["id"])) if l["id"] in by_id else l for l in first]
    day = pick(first, top=top, per_category=per_category, redesign_share=redesign_share)
    meta.update({"place": place, "radius_km": radius_km, "categories": list(keys), "audited": audited, "coverage": coverage(first),
                 "made": dt.datetime.now().isoformat(timespec="seconds"), "attribution": ATTRIBUTION})
    return {"meta": meta, "leads": day, "all": first}


CSV_COLS = ("rank", "tier", "score", "name", "category_label", "address", "phone", "website", "site_status", "why", "reasons", "distance_km",
            "hours", "email", "osm_url", "id")


def _row(i, l):
    return {"rank": i, "tier": l["tier"], "score": l["score"], "name": l["name"], "category_label": l["category_label"], "address": l["address"]["line"],
            "phone": l["phone"], "website": l["website"], "site_status": l["site_status"], "why": l["why"], "reasons": " | ".join(l["reasons"]),
            "distance_km": l["distance_km"], "hours": H.summary(H.parse(l.get("opening_hours", ""))) or l.get("opening_hours", ""),
            "email": l["email"], "osm_url": l["osm_url"], "id": l["id"]}


def write(result: dict, out_dir: str) -> dict:
    ensure_dir(out_dir)
    paths = {k: os.path.join(out_dir, n) for k, n in (("json", "leads.json"), ("csv", "leads.csv"), ("all", "all_leads.csv"))}
    meta = dict(result["meta"])
    meta.pop("query", None)
    with open(paths["json"], "w", encoding="utf-8") as fh:
        json.dump({"v": 1, "kind": "agency-leads", "meta": meta, "leads": result["leads"]}, fh, ensure_ascii=False, indent=1)
    for key, rows in (("csv", result["leads"]), ("all", sorted(result["all"], key=lambda l: (-l["score"], l["distance_km"])))):
        with open(paths[key], "w", newline="", encoding="utf-8-sig") as fh:     # utf-8-sig: Excel on Windows reads it right
            w = csv.DictWriter(fh, fieldnames=CSV_COLS)
            w.writeheader()
            for i, l in enumerate(rows, 1):
                w.writerow(_row(i, l))
    return paths


def table(leads, n=20) -> str:
    lines = [f"{'#':>2} {'T':1} {'Sc':>3}  {'Name':32} {'Trade':20} {'Phone':15} Why", "-" * 118]
    for i, l in enumerate(leads[:n], 1):
        lines.append(f"{i:>2} {l['tier']:1} {l['score']:>3}  {l['name'][:32]:32} {l['category_label'][:20]:20} {(l['phone'] or '-')[:15]:15} {l['why'][:60]}")
    return "\n".join(lines)


def place_from_args(args) -> dict:
    if args.center:
        p = osm.center_from(args.center)
        if args.city and not CFG.PLACEHOLDER.search(args.city):
            p["city"] = args.city.split(",")[0].strip()
            p["state_code"] = args.city.split(",")[1].strip()[:2].upper() if "," in args.city else ""
        p["country_code"] = args.country or "us"
        return p
    if not args.city or CFG.PLACEHOLDER.search(args.city):
        raise ValueError(f"Put your city in {CFG.path()} (search.city, e.g. \"Fort Collins, CO\") or pass --city \"Fort Collins, CO\"")
    return osm.geocode(args.city, refresh=args.refresh)


def parser(cfg: dict) -> argparse.ArgumentParser:
    s = cfg.get("search") or {}
    cats = s.get("categories", "all")
    ap = argparse.ArgumentParser(prog="python -m agency.leads", description="Find local businesses that need a website (OpenStreetMap, free). "
                                 f"Defaults come from {os.path.basename(cfg['_path'])} (search.*); a flag overrides it for one run.")
    ap.add_argument("--city", default=s.get("city"), help='"Fort Collins, CO" (default: search.city)')
    ap.add_argument("--center", help="LAT,LON instead of a city search")
    ap.add_argument("--country", default="", help="two-letter country code with --center (default us)")
    ap.add_argument("--radius-km", type=float, default=float(s.get("radius_km", 8)), help="search radius in km (8 = 5 miles)")
    ap.add_argument("--categories", default="" if cats in ("all", "", None) else (",".join(cats) if isinstance(cats, list) else cats),
                    help="comma list, e.g. barber,plumber,hvac (default: search.categories, 'all' = %d trades)" % len(C.CATEGORIES))
    ap.add_argument("--top", type=int, default=int(s.get("top", 20)))
    ap.add_argument("--per-category", type=int, default=int(s.get("per_category", 2)))
    ap.add_argument("--redesign-share", type=float, default=float(s.get("redesign_share", 0.25)), help="share of the list kept for businesses with a bad site (default 0.25)")
    ap.add_argument("--audit-max", type=int, default=int(s.get("audit_max", 30)), help="check at most this many current websites (polite)")
    ap.add_argument("--no-audit", action="store_true", help="do not open any website")
    ap.add_argument("--refresh", action="store_true", help="ignore the cache (asks the servers again)")
    ap.add_argument("--endpoint", default=None, help="another Overpass server")
    ap.add_argument("--extract", default=None, help="read a local OpenStreetMap extract (.osm / .osm.gz / .osm.bz2, e.g. from download.bbbike.org) instead of Overpass")
    ap.add_argument("--out", default=None)
    return ap


def find_leads(args, log=print):
    """The CLI's work, shared with agency.run: -> (result, out_dir)."""
    keys = C.resolve(args.categories)
    place = place_from_args(args)
    log(f"AGENCY lead finder: {place.get('name') or place.get('city')} ({place['lat']:.4f}, {place['lon']:.4f}), {args.radius_km:g} km, {len(keys)} trades")
    res = run(place, args.radius_km, keys, args.top, args.per_category, args.audit_max, not args.no_audit, args.refresh, args.endpoint, log=log,
              redesign_share=args.redesign_share, extract=getattr(args, "extract", None))
    out = args.out or os.path.join(OUT_DIR, osm.slug(args.city or args.center, 30))
    return res, out


def main(argv=None):
    cfg = CFG.load()
    args = parser(cfg).parse_args(argv)
    try:
        res, out = find_leads(args)
    except (osm.SourceError, ValueError) as e:
        print(f"[STOP] {e}")
        return 2
    paths = write(res, out)
    cov = res["meta"]["coverage"]
    print(table(res["leads"]))
    print(f"\n{len(res['leads'])} leads in {paths['csv']} (+ leads.json, all {cov['n']} in all_leads.csv). "
          f"OSM data: phone {cov['phone']:.0%}, website {cov['website']:.0%}, hours {cov['hours']:.0%}, street {cov['street_address']:.0%}.")
    print(ATTRIBUTION)
    return 0


if __name__ == "__main__":
    sys.exit(main())
