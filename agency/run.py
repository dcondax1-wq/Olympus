"""THE WEBSITE MACHINE, one command for the day's batch (RUN_AGENCY.bat runs this):

    python -m agency.run                                   your city / trades / prices from agency/config.json
    python -m agency.run --city "Fort Collins, CO"         another city for one run

1. finds today's leads (OpenStreetMap, the polite site check)  -> <out>/leads.json, leads.csv, all_leads.csv
2. builds a demo site for the best few (sites_per_day)          -> <out>/sites/<slug>/site/ (drop this FOLDER on app.netlify.com/drop) + <slug>.zip
3. writes each one's pitch kit                                  -> <out>/sites/<slug>/pitch/ (pitch.html, email.txt, phone.txt)
4. refreshes the Agency page's data                             -> tools/web_public/agency/leads.json (+ jarvis.json)
Nothing is sent and nobody is called: the Agency page has the call list, the opener and the email; you dial and press send.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

from . import ATTRIBUTION, CRM_DIR, OUT_DIR
from . import build_site as B
from . import config as CFG
from . import leads as L
from . import osm
from . import pitch as P
from . import publish as PUB


def choose_sites(leads, n=3):
    """The leads that get a demo today: the best one with no website, the best one with a broken site (a different pitch),
    then the best of the other looks, so the batch shows different templates. Only leads with a phone (you have to call them)."""
    callable_ = [l for l in leads if l.get("phone_e164")]
    out = []

    def take(pred):
        for l in callable_:
            if l not in out and pred(l):
                out.append(l)
                return True
        return False

    take(lambda l: l["site_status"] == "none")
    take(lambda l: l["site_status"] == "bad" and l["template"] not in {x["template"] for x in out})
    while len(out) < n and take(lambda l: l["template"] not in {x["template"] for x in out}):
        pass
    while len(out) < n and take(lambda l: True):
        pass
    return out[:n]


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m agency.run", description="The website machine: leads -> demo sites -> pitch kits -> the Agency page.")
    ap.add_argument("--city", default=None)
    ap.add_argument("--center", default=None)
    ap.add_argument("--sites", type=int, default=None, help="demo sites to build (default: search.sites_per_day)")
    ap.add_argument("--out", default=None, help="batch folder (default agency/out/<city>/)")
    ap.add_argument("--crm-out", default=CRM_DIR, help="where the Agency page's data goes")
    ap.add_argument("--sample", action="store_true", help="mark the page data as a sample city (the committed demo)")
    ap.add_argument("--no-audit", action="store_true")
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args(argv)
    if not os.environ.get("AGENCY_CONFIG"):
        CFG.ensure_owner_copy()
    cfg = CFG.load()
    if cfg.get("_error"):
        print(f"[NOTE] {cfg['_error']}")
    la = L.parser(cfg).parse_args([])
    la.city = args.city or la.city
    la.center = args.center
    la.no_audit, la.refresh = args.no_audit, args.refresh
    print("AGENCY: the website machine")
    try:
        res, out = L.find_leads(la)
    except (osm.SourceError, ValueError) as e:
        print(f"[STOP] {e}")
        return 2
    out = args.out or out
    paths = L.write(res, out)
    leads = res["leads"]
    n = args.sites if args.sites is not None else int((cfg.get("search") or {}).get("sites_per_day", 3))
    picks = choose_sites(leads, n)
    sites_dir = os.path.join(out, "sites")
    built, rows = [], []
    for l in picks:
        site = B.site_from_lead(l, cfg)
        r = B.write_site(site, sites_dir)
        k = P.write_kit(l, cfg, site["demo_url"], sites_dir, B.THEMES[site["theme"]]["palette"])
        built.append(l["id"])
        rows.append((l, site, r, k))
    data = PUB.crm_data({"meta": res["meta"], "leads": leads}, cfg, built, sample=args.sample)
    crm = PUB.write(data, args.crm_out)
    summary = {"made": dt.datetime.now().isoformat(timespec="seconds"), "city": data["meta"]["city"], "leads": len(leads), "all": res["meta"]["coverage"]["n"],
               "coverage": res["meta"]["coverage"], "sites": [{"name": l["name"], "template": s["theme"], "folder": os.path.relpath(r["site_dir"], out), "zip": os.path.relpath(r["zip"], out),
                                                              "demo_url": s["demo_url"], "scores": r["check"]["scores"], "ok": r["check"]["ok"], "kb": round(r["check"]["bytes_total"] / 1024, 1),
                                                              "package": k["package"], "setup": k["setup"], "monthly": k["monthly"]} for l, s, r, k in rows],
               "crm": os.path.relpath(crm, os.getcwd()) if crm.startswith(os.getcwd()) else crm, "sender_ready": CFG.sender_ready(cfg), "attribution": ATTRIBUTION}
    with open(os.path.join(out, "run.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1)
    print()
    print(f"{'What':34} Result")
    print(f"{'-' * 34} {'-' * 60}")
    print(f"{'Leads today':34} {len(leads)} (of {summary['all']} businesses found) in {paths['csv']}")
    for l, s, r, k in rows:
        sc = r["check"]["scores"]
        print(f"{'Demo site: ' + l['name'][:23]:34} {s['theme']} look, {summary['sites'][rows.index((l, s, r, k))]['kb']} KB, check {min(sc.values())}/100, "
              f"{k['package']} ${k['setup']:,.0f} + ${k['monthly']:,.0f}/mo")
    print(f"{'Agency page data':34} {crm}")
    print(f"{'Emails':34} {'ready to send' if summary['sender_ready'] else 'NOT ready: fill in agency/config.json (your name, email, postal address)'}")
    print()
    print("Next: 1) drag each sites/<name>/site folder onto app.netlify.com/drop  2) open the Agency page on your phone  3) call the top leads with the opener")
    print(ATTRIBUTION)
    return 0 if all(r["check"]["ok"] for _, _, r, _ in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
