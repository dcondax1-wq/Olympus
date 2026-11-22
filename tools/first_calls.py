"""The first 100 calls for the human caller (lead 2026-11-21), in the caller-portal list format (agency/portal/calllist.json).

    python tools/first_calls.py            -> tools/web_public/agency/portal/first100.json
    python tools/first_calls.py --n 50

Only businesses with a phone (a person dials by hand; Maryland bans cold AI / auto-dialed calls). Ranked by:
  heat (hot > warm), open on weekdays during calling hours (9-17 ET, from the listed opening hours), how likely the trade is to buy
  (contractors / health first, retail last), a street address on file (a real storefront), then name.
Chains and businesses with a website are left out (the factory already drops them). Public map data only.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import lead_value as V  # noqa: E402
from tools import site_factory as F  # noqa: E402

OUT = os.path.join(F.WEB, "portal", "first100.json")
OUT_NEXT = os.path.join(F.WEB, "portal", "next500.json")
WEIGHT = {"trades": 3, "health": 3, "beauty": 2, "auto": 2, "gym": 2, "pro": 2, "services": 1, "food": 1, "retail": 0.5}
PORTAL_NICHE = {"gym": "fitness", "trades": "trades", "services": "home", "pro": "other"}   # the portal's niche words


def _mins(t: str):
    m = re.fullmatch(r"(\d{1,2})(?::(\d\d))?\s*(am|pm)|(midnight)", t.strip())
    if not m:
        return None
    if m.group(4):
        return 24 * 60
    h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    h = h % 12 + (12 if ap == "pm" else 0)
    return h * 60 + mi


def weekday_open_days(hours: str) -> int:
    """how many of Mon-Fri the business is open for 2+ hours between 9:00 and 17:00 (the calling window); 0 when unknown"""
    rows = F.parse_hours(hours) or []
    n = 0
    for day, txt in rows[:5]:
        if txt == "Open 24 hours":
            n += 1
            continue
        best = 0
        for span in txt.split(", "):
            a, _, b = span.partition(" - ")
            x, y = _mins(a), _mins(b)
            if x is None or y is None:
                continue
            if y <= x:
                y += 24 * 60
            best = max(best, min(y, 17 * 60) - max(x, 9 * 60))
        n += best >= 120
    return n


def score(L: dict, s: dict) -> tuple:
    """the $ score (tools/lead_value.py: high-ticket trades first, a phone, site_down, a storefront) + open in calling hours"""
    od = weekday_open_days(L.get("hours"))
    return V.score(L) + (5 if od >= 4 else 2 if od else 0), od


OPENER = {
    "no_site": "I noticed {name} doesn't show a website on the map, so we built a sample one for you. It's free to look at. Can I text or email you the link?",
    "site_down": "I tried to open {name}'s website and it didn't load for me. Did you know it's down? We fix that, and we already built a fresh sample site you can look at.",
}


def blocked() -> tuple:
    """the do-not-call scrub: 'no' / 'do not call' from the caller portal (agency_never.json), the opt-outs and the registry-listed
    numbers of agency/calls (optouts.json, dnc_checked.json). They live only on the PC (git-ignored): in the cloud this is empty."""
    ids, phones = set(), set()
    try:
        from agency import portal as AP
        ids |= set(AP.never_ids())
    except Exception:                            # noqa: BLE001 - no PC files here: nothing blocked by them
        pass
    out = os.path.join(ROOT, "agency", "calls", "out")
    for fn, key in (("optouts.json", "phones"), ("dnc_checked.json", "numbers")):
        try:
            d = json.load(open(os.path.join(out, fn), encoding="utf-8")).get(key) or {}
        except (OSError, ValueError, AttributeError):
            continue
        if isinstance(d, dict):
            d = [p for p, v in d.items() if isinstance(v, dict) and v.get("dnc") == "listed"]
        phones |= {re.sub(r"\D", "", str(p))[-10:] for p in d}
    return ids, phones


def build(n: int = 100, skip: int = 0) -> dict:
    sites = {s["id"]: s for s in json.load(open(os.path.join(F.WEB, "factory", "sites.json"), encoding="utf-8"))["sites"]}
    rows, (never, dnc) = [], blocked()
    for L in F.load_leads():
        s = sites.get(L["id"])
        ph = re.sub(r"\D", "", str(L.get("phone") or ""))
        if not s or s.get("chain") or len(ph) not in (10, 11) or L["id"] in never or ph[-10:] in dnc:
            continue
        lane = "site_down" if (L.get("web") or {}).get("verdict") == "site_down" else "no_site"
        pts, od = score(L, s)
        tv, tl = V.trade(L)
        why = [w for w, ok in (("high-ticket trade: " + tl, tv >= 7), ("website is down", lane == "site_down"), ("hot lead", L.get("heat") == "hot"),
                               (f"open {od} weekdays in calling hours", od > 0),
                               ("storefront address", F.ready(L) and bool(L.get("address")))) if ok]
        rows.append({"id": L["id"], "name": s["name"][:80], "phone": ph[-10:], "town": s["town"][:40], "state": str(L.get("state") or "MD")[:2].upper(),
                     "niche": PORTAL_NICHE.get(s["niche"], s["niche"]), "kind": s["kind"][:40], "code": s.get("code", ""), "site": s["path"],
                     "heat": str(L.get("heat") or ""), "score": round(pts, 1), "open_weekdays": od, "why": why, "trade": tl,
                     "county": str(L.get("county") or ""),
                     "lane": lane, "opener": OPENER[lane].format(name=s["name"][:80]), "src": "overture" if L.get("source") == "overture" or L.get("phone_src") == "overture" else "osm"})
    nophone = sum(1 for L in F.load_leads() if len(re.sub(r"\D", "", str(L.get("phone") or ""))) not in (10, 11))
    rows.sort(key=lambda r: (-r["score"], -r["open_weekdays"], r["town"], r["name"].lower()))
    rows = rows[skip:skip + n]
    for i, r in enumerate(rows, skip + 1):
        r["rank"] = i
    return {"v": 1, "kind": "caller-portal-list", "list": "first-100" if not skip else f"next-{n}", "built": time.strftime("%Y-%m-%d"), "count": len(rows),
            "note": "public map data only; ranked: hot, open in calling hours, trade, storefront. A person dials; never an auto-dialer. "
                    "Lanes: no_site (we built you one) / site_down (your website is down). Leads with a working site are not here (agency/leads/redesign.json).",
            "credit": "Data (c) OpenStreetMap contributors (ODbL) and Overture Maps Foundation (CDLA-Permissive-2.0 / ODbL), overturemaps.org",
            "skipped": {"no phone": nophone},
            "leads": rows}


def main(argv) -> int:
    n = int(argv[argv.index("--n") + 1]) if "--n" in argv else 100
    doc = build(n)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
        f.write("\n")
    nxt = build(500, skip=n)                     # the 'next 500' (ranks n+1 .. n+500), same format
    with open(OUT_NEXT, "w", encoding="utf-8") as f:
        json.dump(nxt, f, separators=(",", ":"))
        f.write("\n")
    top = doc["leads"][:3]
    print(f"first calls: {doc['count']} in {os.path.relpath(OUT, ROOT)}; top: " + "; ".join(f"{r['name']} ({r['town']}, {r['score']})" for r in top))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
