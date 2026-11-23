"""CRM DATA: the lead list as the OLYMPUS Agency page reads it (tools/web_public/agency/leads.json + its jarvis.json card).

    python -m agency.publish --leads agency/out/<city>/leads.json [--built ID ...] [--sample] [--out DIR]

Per lead: the plain facts (name, trade, address, phone, current site, score, why, reasons), the map / demo links, the
recommended package and price, and the words (30-second opener, voicemail, email subject and text) from agency/pitch.py.
It never contains the owner's notes or stages: those stay in his phone's browser. Business data (c) OpenStreetMap
contributors (ODbL), so the file carries the attribution.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time

from . import ATTRIBUTION, CRM_DIR, ensure_dir
from . import categories as C
from . import config as CFG
from . import hours as H
from . import money as M
from . import pitch as P
from .build_site import maps_links


def crm_lead(lead: dict, cfg: dict, demo_url: str, built: bool) -> dict:
    k = P.kit(lead, cfg, demo_url)
    addr = lead.get("address") or {}
    google, _ = maps_links({"name": lead["name"], "address_line": addr.get("line", ""), "city": addr.get("city", ""), "lat": lead.get("lat"), "lon": lead.get("lon")})
    return {
        "id": lead["id"], "name": lead["name"], "category": lead["category"], "trade_label": C.BY_KEY[lead["category"]].label, "template": lead.get("template", ""),
        "score": lead.get("score", 0), "tier": lead.get("tier", "C"), "why": lead.get("why", ""), "reasons": (lead.get("reasons") or [])[:5], "site_status": lead.get("site_status", ""),
        "phone": lead.get("phone", ""), "phone_e164": lead.get("phone_e164", ""), "address_line": addr.get("line", ""), "city": addr.get("city", ""), "email": lead.get("email", ""),
        "website": lead.get("website", ""), "osm_url": lead.get("osm_url", ""), "map_url": google, "distance_km": lead.get("distance_km"),
        "hours": H.summary(H.parse(lead.get("opening_hours", ""))), "demo_url": demo_url, "demo_built": bool(built),
        "package": k["package"], "setup": k["setup"], "monthly": k["monthly"], "opener": k["opener"], "voicemail": k["voicemail"], "subject": k["subject"], "email_body": k["email"],
    }


def crm_data(doc: dict, cfg: dict, built_ids=(), sample=False, demo=False, note="") -> dict:
    meta = doc.get("meta") or {}
    place = meta.get("place") or {}
    leads = [crm_lead(l, cfg, P.demo_url_for(l, cfg), l["id"] in set(built_ids)) for l in doc.get("leads", [])]
    plan = M.plan(cfg, M.load_pricing())
    city = place.get("name", "").split(",")[0] if place.get("name") else ""
    if place.get("city"):
        city = place["city"] + (f", {place['state_code']}" if place.get("state_code") else "")
    return {
        "v": 1, "kind": "agency-crm-data", "made": dt.datetime.now().isoformat(timespec="seconds"), "demo": bool(demo), "sample": bool(sample), "note": note,
        "meta": {"city": city, "radius_km": meta.get("radius_km"), "coverage": meta.get("coverage"), "osm_base": meta.get("osm_base", ""), "attribution": ATTRIBUTION},
        "agency": {"name": (cfg.get("agency") or {}).get("name", ""), "ready": CFG.sender_ready(cfg)},
        "goal": plan["goal"], "packages": [{k: p.get(k) for k in ("id", "name", "setup", "monthly", "pitch")} for p in cfg.get("packages") or []],
        "plan": {k: plan[k] for k in ("goal", "avg_setup", "avg_monthly", "churn", "rows", "pace", "care_clients_for_goal_alone")},
        "attribution": ATTRIBUTION, "leads": leads,
    }


def jarvis_card(data: dict) -> dict:
    """The status card Jarvis / the launcher reads (docs/JARVIS_APPS.md contract: <= 3 kpis, <= 3 lines of 120)."""
    leads = data["leads"]
    a = sum(1 for l in leads if l["tier"] == "A")
    built = sum(1 for l in leads if l["demo_built"])
    level = "off" if data["demo"] else "ok" if leads else "warn"
    label = "Demo leads" if data["demo"] else ("Sample city" if data["sample"] else f"{len(leads)} leads ready")
    lines = [f"{len(leads)} leads in {data['meta']['city'] or 'your city'}: {a} top ones, {built} demo sites built."[:120],
             f"Plan: {data['plan']['pace']['new_per_month']} new clients a month reaches ${data['goal']:,.0f} a month in about {data['plan']['pace']['months_to_goal']} months."[:120]]
    return {"v": 1, "name": "Agency", "status": {"level": level, "label": label[:48]},
            "kpis": [{"label": "Leads", "value": str(len(leads))}, {"label": "Top leads (A)", "value": str(a)}, {"label": "Demo sites", "value": str(built)}],
            "lines": lines, "t": int(time.time()), "open": "#", "theme": "#14110e", "stale_after": 7 * 86400}


def write(data: dict, out_dir: str = CRM_DIR, name: str = "leads.json", card: bool = True) -> str:
    ensure_dir(out_dir)
    p = os.path.join(out_dir, name)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    if card:
        with open(os.path.join(out_dir, "jarvis.json"), "w", encoding="utf-8") as fh:
            json.dump(jarvis_card(data), fh, ensure_ascii=False, separators=(",", ":"))
            fh.write("\n")
    return p


def _fake(i, name, cat, street, phone, hours, website="", status="none", issues=None, score=95):
    from .leads import tier
    lead = {"id": f"x{i}", "name": name, "slug": f"example-{i}", "category": cat, "template": C.BY_KEY[cat].template, "lat": 40.0 + i / 1000, "lon": -105.0,
            "address": {"line": f"{street}, Maple Falls, ST 00000", "street_line": street, "city": "Maple Falls", "state": "ST", "has_street": True},
            "phone": phone, "phone_e164": "+1555" + phone[-8:-5] + phone[-4:], "email": "", "website": website, "osm_url": "", "opening_hours": hours,
            "distance_km": round(0.4 + i * 0.7, 1), "site_status": status, "issues": issues or [], "score": score, "tier": tier(score)}
    lead["reasons"] = [x["text"] for x in lead["issues"]] or ["No website listed on OpenStreetMap (search the name on Google before you call)"]
    lead["why"] = lead["reasons"][0] + "."
    return lead


def fixture_doc() -> dict:
    """EXAMPLE leads for the page's DEMO mode: invented businesses in an invented town, 555-01xx numbers (reserved for fiction)."""
    bad = [{"code": "no_viewport", "weight": 25, "text": "Not built for phones: on a phone it shows a tiny desktop page you have to pinch and zoom"},
           {"code": "no_https", "weight": 20, "text": "No padlock: the site has no HTTPS, so Chrome labels it 'Not secure'"}]
    leads = [_fake(1, "Maple Falls Plumbing", "plumber", "14 River Road", "(555) 555-0101", "Mo-Fr 07:00-17:00", score=100),
             _fake(2, "Oak Street Barbers", "barber", "210 Oak Street", "(555) 555-0102", "Tu-Sa 09:00-18:00", score=96),
             _fake(3, "Sunrise Family Dental", "dentist", "88 Hill Avenue", "(555) 555-0103", "Mo-Th 08:00-17:00", score=99),
             _fake(4, "Corner Auto Care", "auto_repair", "5 Mill Street", "(555) 555-0104", "Mo-Fr 08:00-18:00; Sa 09:00-13:00", "http://cornerauto.example", "bad", bad, 88),
             _fake(5, "Green Thumb Landscaping", "landscaper", "301 Meadow Lane", "(555) 555-0105", "", score=98),
             _fake(6, "La Mesa Kitchen", "restaurant", "42 Main Street", "(555) 555-0106", "Tu-Su 11:00-21:00", score=95),
             _fake(7, "Bloom Nail Studio", "beauty", "9 Park Plaza", "(555) 555-0107", "Mo-Sa 10:00-19:00", score=96),
             _fake(8, "Peak Fitness Club", "gym", "77 Ridge Road", "(555) 555-0108", "Mo-Su 05:00-22:00", "http://peakfit.example", "bad", bad[:1], 81)]
    return {"meta": {"place": {"city": "Maple Falls", "state_code": "ST"}, "radius_km": 8, "coverage": {"n": 8, "phone": 1.0, "website": 0.25, "hours": 0.88, "street_address": 1.0}}, "leads": leads}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m agency.publish", description="Write the Agency page's data (leads.json) from a lead list.")
    ap.add_argument("--leads", help="a leads.json from agency.leads / agency.run")
    ap.add_argument("--built", action="append", default=[], help="ids of leads whose demo site is built")
    ap.add_argument("--sample", action="store_true", help="mark it as a sample city (the committed demo)")
    ap.add_argument("--fixture", action="store_true", help="write the page's DEMO fixture.json (invented businesses) instead")
    ap.add_argument("--out", default=CRM_DIR)
    args = ap.parse_args(argv)
    if args.fixture:
        cfg = CFG.load(CFG.EXAMPLE)
        d = crm_data(fixture_doc(), cfg, ["x1", "x3"], demo=True, note="EXAMPLE leads, not real: invented businesses in an invented town. Run the website machine (tools/bat/RUN_AGENCY.bat) for your own city.")
        p = write(d, args.out, "fixture.json", card=False)
        print(f"Agency DEMO fixture: {p}")
        return 0
    if not args.leads:
        ap.error("give --leads FILE (or --fixture)")
    with open(args.leads, encoding="utf-8") as fh:
        doc = json.load(fh)
    # the owner's own data is my_leads.json (gitignored, read first by the page); only --sample writes the tracked leads.json + card
    p = write(crm_data(doc, CFG.load(), args.built, sample=args.sample), args.out, "leads.json" if args.sample else "my_leads.json", card=args.sample)
    print(f"Agency page data: {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
