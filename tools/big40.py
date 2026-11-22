"""BIG 40 (lead 2026-11-22): the top high-ticket Maryland businesses (dentists, law, HVAC / roofing / plumbing / electric, med spas,
vets, chiropractors / orthodontists) whose website is DATED or BROKEN, for a redesign call. Human dialing only (Maryland bans
cold AI / auto-dialed calls). Public facts only.

    python -X utf8 tools/big40.py [--n 40]   -> agency/calls/BIG40.csv

Sources: agency/redesign_score.py's tools/agency_site_scores.json (technical facts of each home page: down, https, viewport, newest
(c) year, speed, size, old code) joined to tools/web_public/agency/leads/redesign.json + the town lead rows (category, phone).
Package and price from agency/pricebook.json. Rank = first-year ticket x how bad the site is (down = 8 points, else the score's
problem points) - a business with a working, modern site is not on the list.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agency.calls import core as C  # noqa: E402

WEB = os.path.join(ROOT, "tools", "web_public", "agency")
OUT = os.path.join(ROOT, "agency", "calls", "BIG40.csv")
GROUPS = [   # (group, keywords in category / kind / name, package id(s))
    ("law firm", ("attorney", "law", "legal"), ("signature3d",)),
    ("med spa", ("med spa", "medspa", "medical spa", "aesthetic", "botox", "laser"), ("signature3d",)),
    ("dentist / orthodontist", ("dent", "orthodont"), ("starter", "callengine")),
    ("veterinarian", ("vet", "animal hospital", "animal clinic"), ("starter", "callengine")),
    ("chiropractor", ("chiropract",), ("starter",)),
    ("HVAC / roofing / plumbing / electric", ("hvac", "heating", "cooling", "air condition", "roof", "plumb", "electric"), ("starter", "callengine")),
    # second tier (labelled): other high-ticket health / professional offices, only after the five asked-for kinds
    ("other high-ticket (2nd tier): eye / therapy / skin / CPA / insurance / mortgage",
     ("optometr", "optician", "eye care", "physical therap", "physio", "dermatolog", "podiatr", "accountant", "cpa", "tax",
      "insurance", "mortgage", "financial"), ("starter",)),
]
TIER2 = GROUPS[-1][0]


def plain(why: list, down: bool) -> str:
    if down:
        return "the website does not load right now"
    out = []
    for w in why:
        m = re.search(r"\(©\s*(\d{4})\)", w)
        if w.startswith("down"):
            out.append("the website does not load right now")
        elif w.startswith("not secure"):
            out.append("no padlock: browsers show 'Not secure'")
        elif w.startswith("not mobile"):
            out.append("hard to use on a phone")
        elif w.startswith("old copyright"):
            out.append(f"looks out of date (© {m.group(1)} at the bottom)" if m else "looks out of date")
        elif w.startswith("slow"):
            out.append("slow to open")
        elif w.startswith("heavy"):
            out.append("very heavy page (slow on phones)")
        elif w.startswith("old code"):
            out.append("built with old web code")
        elif w.startswith("no address"):
            out.append("no address on the home page")
        else:
            out.append(w)
    return "; ".join(out)


def package(pb, ids):
    P = {p["id"]: p for p in pb["packages"]}
    setup = sum(P[i]["setup"] for i in ids)
    monthly = sum(P[i]["monthly"] for i in ids)
    names = " + ".join(P[i]["name"] for i in ids)
    return names, setup, monthly, setup + 12 * monthly


def build(n=40):
    pb = json.load(open(os.path.join(ROOT, "agency", "pricebook.json"), encoding="utf-8"))
    sc = json.load(open(os.path.join(ROOT, "tools", "agency_site_scores.json"), encoding="utf-8"))["scores"]
    red = {x["id"]: x for x in json.load(open(os.path.join(WEB, "leads", "redesign.json"), encoding="utf-8"))["leads"]}
    full = {}
    for f in glob.glob(os.path.join(WEB, "leads", "towns", "*.json")):
        for x in json.load(open(f, encoding="utf-8")).get("leads", []):
            full[x["id"]] = x
    for lid, x in full.items():                       # + the leads whose own domain did not load at the Overture check
        if lid not in sc and (x.get("web") or {}).get("verdict") == "site_down":
            sc[lid] = {"score": 0, "why": ["down at the 2026-11-21 check"], "down": True, "checked": (x.get("web") or {}).get("checked")}
            red.setdefault(lid, {**x, "url": (x.get("web") or {}).get("url") or x.get("website")})
    rows, seen = [], set()
    for lid, s in sc.items():
        x = {**full.get(lid, {}), **red.get(lid, {})}
        if not x:
            continue
        txt = " ".join(str(x.get(k) or "") for k in ("category", "kind", "name")).lower()
        grp = next((g for g in GROUPS if any(k in txt for k in g[1])), None)
        if grp is None:
            continue
        url = str(x.get("url") or x.get("website") or "").lower()
        if "/locations/" in url or "/location/" in url or "utm_" in url or "america's best" in txt:   # a chain's store page
            continue
        down = bool(s.get("down"))
        pts = 8 if down else int(s.get("score") or 0)
        if pts <= 0:
            continue
        ph = C.norm_phone(x.get("phone"))
        if not ph or ph in seen:
            continue
        seen.add(ph)
        names, setup, monthly, first_year = package(pb, grp[2])
        rows.append({"name": x.get("name"), "town": x.get("town"), "phone": C.pretty_phone(ph), "kind": grp[0],
                     "category": x.get("category") or x.get("kind") or "", "website": x.get("url") or x.get("website") or "",
                     "whats_wrong": plain(s.get("why") or [], down), "problem_points": pts,
                     "package": names, "price": f"${setup:,} setup + ${monthly}/month", "first_year_usd": first_year,
                     "checked": s.get("checked"), "id": lid, "_rank": first_year * pts})
    rows.sort(key=lambda r: (r["kind"] == TIER2, -r["_rank"], r["name"] or ""))
    rows = rows[:n]
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    a = ap.parse_args(argv)
    rows = build(a.n)
    cols = ["rank", "name", "town", "phone", "kind", "category", "website", "whats_wrong", "problem_points", "package", "price",
            "first_year_usd", "checked", "id"]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        fh.write("# BIG 40 redesign leads - HUMAN dialing only (no AI / robo / auto-dial: illegal in Maryland). Do-not-call: scrub on the PC "
                 "(python -m agency.dnc_scrub) before dialing. Site facts: agency/redesign_score.py (public home page checks). "
                 "Data: OpenStreetMap contributors (ODbL); Overture Maps Foundation\n")
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    import collections
    print(f"{len(rows)} rows -> {os.path.relpath(OUT, ROOT)}", collections.Counter(r["kind"] for r in rows).most_common(),
          "first-year $ total", sum(r["first_year_usd"] for r in rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
