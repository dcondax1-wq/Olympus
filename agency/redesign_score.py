"""REDESIGN SCORE for the businesses that already have a site (day-a11y 2026-11-22; the caller portal's Redesign tab).

One GET of each home page (the url the Overture check found: agency/leads/redesign.json), at most 600 KB, 10 s, a plain generic User-Agent; never
a second page, never a form, no cookies kept. Only technical facts of the page are kept, never a name, an email, a phone or any text of the page:

  not secure (http)         the final address is not https                          +3
  not mobile-friendly       no <meta name="viewport">                               +3
  old copyright             the newest (c) year on the page is 3+ years old         +2
  slow                      the page took more than 2.5 s to arrive                 +2
  heavy                     more than 1.5 MB of html                                +1  (counted to the 600 KB cap: then "heavy")
  old code                  jQuery 1.x, Flash or frames                             +1
  down now                  no answer / not 200                                     (kept apart: lane site_down is for those)

    python -m agency.redesign_score            check every redesign lead -> tools/agency_site_scores.json (public facts only; re-run monthly)
    python -m agency.redesign_score --limit 20 a quick sample
Higher score = more dated / slower = a better redesign call. Stdlib only."""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REDESIGN = os.path.join(ROOT, "tools", "web_public", "agency", "leads", "redesign.json")
OUT = os.path.join(ROOT, "tools", "agency_site_scores.json")
UA = "Mozilla/5.0 (compatible; SiteCheck/1.0; one home-page check)"
CAP = 600_000


def fetch(url: str, timeout: float = 10.0):
    """(final url, status, bytes (capped), seconds). Raises on a network error."""
    t0 = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read(CAP + 1)
        return r.geturl(), r.status, body, time.time() - t0


def score(final_url: str, status: int, body: bytes, secs: float, now_year: int) -> dict:
    html = body.decode("utf-8", "replace").lower()
    why, s = [], 0
    if not str(final_url).lower().startswith("https://"):
        s += 3
        why.append("not secure (http)")
    if not re.search(r"<meta[^>]+name=[\"']?viewport", html):
        s += 3
        why.append("not mobile-friendly")
    years = [int(y) for y in re.findall(r"(?:©|&copy;|&#169;|copyright)\s*(?:\d{4}\s*[-–]\s*)?((?:19|20)\d\d)", html)]
    newest = max(years) if years else None
    if newest and newest <= now_year - 3:
        s += 2
        why.append(f"old copyright (© {newest})")
    if secs > 2.5:
        s += 2
        why.append(f"slow ({secs:.1f} s)")
    if len(body) > CAP:
        s += 1
        why.append("heavy page")
    if re.search(r"jquery[-.]1\.\d|\.swf\b|<frameset|<iframe[^>]+name=[\"']?main", html):
        s += 1
        why.append("old code")
    return {"score": s, "why": why, "secs": round(secs, 1), "https": str(final_url).lower().startswith("https://"), "status": status}


def check_one(lead: dict, now_year: int, get=fetch) -> dict:
    url = str(lead.get("url") or "")
    if not re.match(r"^https?://", url):
        return {"score": 0, "why": ["no address"], "down": True}
    try:
        final, st, body, secs = get(url)
    except Exception as e:  # noqa: BLE001
        return {"score": 0, "why": ["down now (" + type(e).__name__ + ")"], "down": True}
    if st != 200:
        return {"score": 0, "why": [f"down now ({st})"], "down": True}
    return score(final, st, body, secs, now_year)


def run(leads: list, get=fetch, workers: int = 8, today: dt.date | None = None) -> dict:
    today = today or dt.date.today()
    out = {}
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(check_one, L, today.year, get): L["id"] for L in leads if isinstance(L, dict) and L.get("id")}
        for f in cf.as_completed(futs):
            out[futs[f]] = dict(f.result(), checked=today.isoformat())
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Redesign score: one home-page check per business that already has a site")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(argv)
    leads = (json.load(open(REDESIGN, encoding="utf-8")).get("leads") or []) if os.path.exists(REDESIGN) else []
    if a.limit:
        leads = leads[: a.limit]
    res = run(leads)
    doc = {"v": 1, "kind": "redesign-scores", "checked": dt.date.today().isoformat(), "count": len(res),
           "note": "technical facts of each home page only (https, viewport, newest (c) year, speed, size, old code); no personal data, no page text",
           "scores": dict(sorted(res.items()))}
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=1)
        f.write("\n")
    up = [v for v in res.values() if not v.get("down")]
    print(f"  [OK] {len(res)} sites checked, {len(up)} up; score >= 5: {sum(1 for v in up if v['score'] >= 5)} -> {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
