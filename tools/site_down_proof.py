"""Proof for the 'your website is down' pitch (lead 2026-11-22): what failed, on which domain, when it was checked.

    python tools/site_down_proof.py          re-check every site_down lead (county files + the 16-town files), store web.proof

Per lead (private county files keep the detail; only the plain line + reason go to the public call list):
  web.reason  dns_gone | timeout | ssl | not_found | server_error | parked | for_sale | refused | other | up (it came back: dropped)
  web.proof   "Your site example.com didn't load: the address no longer points anywhere. Checked Sun 11-22 1:00am and 2:00am ET."
Parked / for-sale domains (the page answers, but it is a registrar's parking or 'buy this domain' page) get their own honest opener.
"""
from __future__ import annotations

import concurrent.futures as cf
import datetime as dt
import glob
import json
import os
import re
import sys
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import web_leads_overture as W  # noqa: E402

COUNTY_GLOB = os.path.join(ROOT, "research", "web_leads", "counties", "*.json")
TOWN_GLOB = os.path.join(W.TOWNS_DIR, "*.json")
ET = ZoneInfo("America/New_York")
FOR_SALE = re.compile(r"(this domain|the domain)[^<]{0,40}(is|may be) (for sale|available)|buy this domain|domain (is )?for sale|make an offer|"
                      r"hugedomains|dan\.com|afternic|sedo\.com|undeveloped\.com|atom\.com/name", re.I)
PARKED = re.compile(r"parked (free|domain|by)|domain parking|this (web ?page|site) is parked|godaddy\.com/park|parkingcrew|bodis\.com|"
                    r"sedoparking|above\.com|namebright|is registered (at|with)|coming soon[^<]{0,40}(godaddy|namecheap|register)|"
                    r"future home of|this domain (name )?(has been|was) registered", re.I)
REASON = {
    "dns_gone": "the address no longer points anywhere",
    "timeout": "it never answered",
    "ssl": "browsers show a security warning (its certificate is broken)",
    "not_found": "it shows 'page not found'",
    "server_error": "it shows a server error",
    "refused": "the server refuses connections",
    "parked": "the address now shows a parked page from the domain company",
    "for_sale": "the address is now listed for sale",
    "other": "it didn't load",
}


def fetch(url: str, timeout=15):
    """(status, body head) for the site's page, then its home page"""
    u = url if re.match(r"^https?://", url or "") else "http://" + str(url)
    last = (None, "")
    for t in dict.fromkeys([u, "https://" + W.host(u) + "/", "http://" + W.host(u) + "/"]):
        req = urllib.request.Request(t, headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
                                                               "Version/17.0 Mobile/15E148 Safari/604.1", "Accept": "text/html"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read(40000).decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            try:
                body = e.read(20000).decode("utf-8", "replace")
            except Exception:                    # noqa: BLE001
                body = ""
            last = (e.code, body)
            if e.code in (401, 403, 429):
                return last
        except urllib.error.URLError as e:
            r = str(e.reason)
            if "Name or service not known" in r or "getaddrinfo" in r or "nodename" in r or "No address associated" in r:
                return "dns", ""
            last = ("ssl" if "CERTIFICATE" in r.upper() or "SSL" in r.upper() else "refused" if "refused" in r.lower() else type(e.reason).__name__, "")
        except Exception as e:                   # noqa: BLE001 - timeouts, resets
            last = (type(e).__name__, "")
    return last


def classify(status, body: str) -> str:
    b = body or ""
    if FOR_SALE.search(b):
        return "for_sale"
    if PARKED.search(b):
        return "parked"
    if status == "dns" or status == "gaierror":
        return "dns_gone"
    if status in (200, 202, 401, 403, 409, 429):
        return "up"
    if status in ("TimeoutError", "timeout", "RemoteDisconnected", "ConnectionResetError"):
        return "timeout"
    if status in ("ssl", "SSLCertVerificationError", "SSLError"):
        return "ssl"
    if status in (404, 410):
        return "not_found"
    if isinstance(status, int) and status >= 500:
        return "server_error"
    if status == "refused":
        return "refused"
    return "other"


def when(ts: str) -> str:
    try:
        t = dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(ET)
    except (ValueError, AttributeError):
        return ""
    h = t.strftime("%I:%M%p").lstrip("0").lower().replace(":00", "")
    return t.strftime("%a %m-%d ") + h


def proof_line(domain: str, reason: str, t1: str, t2: str) -> str:
    a, b = when(t1), when(t2)
    if a and b and a[:9] == b[:9]:
        b = b[10:]                               # same day: 'Sun 11-22 12:57am and 2am'
    times = " and ".join(x for x in (a, b) if x)
    return f"Your site {domain} didn't load: {REASON.get(reason, REASON['other'])}." + (f" Checked {times} ET." if times else "")


def run(files=None, fetcher=fetch, now=None, threads=32, write=True) -> dict:
    files = files or sorted(glob.glob(COUNTY_GLOB)) + sorted(glob.glob(TOWN_GLOB))
    now = now or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    docs = {p: json.load(open(p, encoding="utf-8")) for p in files}
    todo = [(p, L) for p, d in docs.items() for L in d.get("leads", []) if (L.get("web") or {}).get("verdict") == "site_down" and (L["web"].get("url"))]
    with cf.ThreadPoolExecutor(max_workers=threads) as ex:
        res = list(ex.map(lambda t: fetcher(t[1]["web"]["url"]), todo))
    tally, dropped = {}, 0
    for (p, L), (st, body) in zip(todo, res):
        reason = classify(st, body)
        w = L["web"]
        if reason == "up":
            docs[p]["leads"].remove(L)            # it answers again: not a 'site down' lead (a third check said so)
            dropped += 1
            continue
        prev = w.get("checked2") or w.get("checked")
        w.update(reason=reason, checked3=now, domain=W.host(w["url"]), proof=proof_line(W.host(w["url"]), reason, prev if "T" in str(prev) else "", now))
        tally[reason] = tally.get(reason, 0) + 1
    if write:
        for p, d in docs.items():
            with open(p, "w", encoding="utf-8") as f:
                if "counties" in p:
                    json.dump(d, f, separators=(",", ":"))
                else:
                    json.dump(d, f, indent=1)
                f.write("\n")
    return {"checked": len(todo), "came_back_up": dropped, "reasons": tally, "at": now}


if __name__ == "__main__":
    print(json.dumps(run(), indent=1))
