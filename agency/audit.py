"""A polite one-time check of a business's current website: what is wrong with it, in plain words a shop owner understands.

Polite = robots.txt is read and obeyed, the home page is fetched ONCE (no crawling), at most 2.5 MB is read, 15 s timeout,
a clear User-Agent, 1 s between sites, and the answer is cached for 30 days so a re-run never asks again.
Facebook / Instagram / Yelp links are judged by the address alone (no fetch: they block tools and need a login).

analyze() is pure (HTML text in, issues out) so the tests can feed it fixture pages.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser

from . import CACHE_DIR, UA, ensure_dir

AUDIT_TTL = 30 * 86400
MAX_BYTES = 2_500_000
ROBOT_NAME = "OLYMPUS-agency"

SOCIAL = {
    "facebook.com": "a Facebook page", "fb.com": "a Facebook page", "instagram.com": "an Instagram page", "yelp.com": "a Yelp page",
    "linktr.ee": "a Linktree page", "tiktok.com": "a TikTok page", "nextdoor.com": "a Nextdoor page", "x.com": "an X (Twitter) page",
    "twitter.com": "an X (Twitter) page", "g.page": "a Google listing", "maps.google.com": "a Google Maps listing", "goo.gl": "a Google link",
}
DEAD_HOSTS = {"business.site": "Google Business Profile", "negocio.site": "Google Business Profile"}
FREE_HOSTS = {"wixsite.com": "a free Wix address", "godaddysites.com": "a free GoDaddy address", "weebly.com": "a free Weebly address",
              "wordpress.com": "a free WordPress.com address", "blogspot.com": "a free Blogger address", "square.site": "a free Square address",
              "sites.google.com": "a free Google Sites address", "webnode.com": "a free Webnode address", "jimdosite.com": "a free Jimdo address"}
CTA = re.compile(r"\b(book|schedule|appointment|reserve|reservation|order|quote|estimate|call (?:us|now|today)|get started|contact us|request|free consult)\w*", re.I)
PARKED = re.compile(r"domain (?:name )?(?:is|may be) for sale|buy this domain|this domain is parked|parked (?:free|domain)|domain parking|"
                    r"future home of|website (?:is )?coming soon|site (?:is )?under construction|account (?:has been )?suspended|"
                    r"this site is (?:temporarily )?unavailable|site (?:has )?expired|renew (?:your|this) (?:domain|site)", re.I)
OLD_TOOLS = re.compile(r"frontpage|dreamweaver|iweb|adobe muse|microsoft word|homestead|intuit|web\.com sitebuilder|wordpress [1-4]\.|joomla! 1\.|yahoo sitebuilder", re.I)


def _host(url: str) -> str:
    return (urllib.parse.urlsplit(url).hostname or "").lower().removeprefix("www.").removeprefix("m.")


def _endswith(host: str, table: dict):
    for k, v in table.items():
        if host == k or host.endswith("." + k):
            return v
    return None


def issue(code, weight, text):
    return {"code": code, "weight": int(weight), "text": text}


def judge_address(url: str):
    """Issues visible from the address alone (no fetch needed), and whether to fetch at all."""
    host = _host(url)
    social = _endswith(host, SOCIAL)
    if social:
        return [issue("social_only", 55, f"Their only web address is {social}: no website of their own for Google to show")], False
    dead = _endswith(host, DEAD_HOSTS)
    if dead:
        return [issue("dead_gbp_site", 60, "Their site was a free Google Business Profile site: Google shut all of those down in 2024")], False
    free = _endswith(host, FREE_HOSTS)
    if free:
        return [issue("free_subdomain", 12, f"The site lives on {free} instead of their own name (.com)")], True
    return [], True


def analyze(html_text: str, final_url: str, status: int = 200, elapsed_s: float = 0.0, size: int = 0, headers=None, year=None) -> dict:
    """Pure: the page -> {issues, facts}. Weights add up into the lead's 'need' score (capped at 65 in leads.score)."""
    year = year or dt.date.today().year
    low = html_text or ""
    issues, facts = [], {}
    if status >= 400:
        issues.append(issue("site_down", 55, f"Their website does not open (error {status})"))
        return {"issues": issues, "facts": {"status": status}}
    if PARKED.search(re.sub(r"<[^>]+>", " ", low)[:20000]):
        issues.append(issue("parked", 55, "Their address shows a parked or 'coming soon' page, not a real website"))
    https = urllib.parse.urlsplit(final_url).scheme == "https"
    facts["https"] = https
    if not https:
        issues.append(issue("no_https", 20, "No padlock: the site has no HTTPS, so Chrome labels it 'Not secure'"))
    vp = re.search(r"<meta[^>]+name=[\"']?viewport[\"']?[^>]*>", low, re.I)
    facts["viewport"] = bool(vp and re.search(r"width\s*=\s*device-width", vp.group(0), re.I))
    if not facts["viewport"]:
        issues.append(issue("no_viewport", 25, "Not built for phones: on a phone it shows a tiny desktop page you have to pinch and zoom"))
    facts["tel"] = bool(re.search(r"href=[\"']?\s*tel:", low, re.I))
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", low)
    text = re.sub(r"<[^>]+>", " ", text)
    phone_text = bool(re.search(r"\(?\b\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b", text))
    if not facts["tel"]:
        issues.append(issue("no_tel", 10, "The phone number is not tap-to-call" if phone_text else "No phone number on the home page"))
    links = " ".join(re.findall(r"(?is)<(?:a|button)\b[^>]*>(.*?)</(?:a|button)>", low))
    facts["cta"] = bool(CTA.search(re.sub(r"<[^>]+>", " ", links)))
    if not facts["cta"]:
        issues.append(issue("no_cta", 8, "No clear button to call, book or get a quote"))
    t = re.search(r"(?is)<title[^>]*>(.*?)</title>", low)
    facts["title"] = re.sub(r"\s+", " ", t.group(1)).strip()[:120] if t else ""
    desc = re.search(r"<meta[^>]+name=[\"']?description[\"']?[^>]*content=[\"']([^\"']*)", low, re.I)
    if not facts["title"]:
        issues.append(issue("no_title", 5, "No page title, so Google shows a blank or random headline"))
    elif not (desc and desc.group(1).strip()):
        issues.append(issue("no_description", 3, "No description for Google's search results"))
    years = [int(y) for y in re.findall(r"(?:&copy;|©|copyright)\s*(?:\d{4}\s*[-–]\s*)?((?:19|20)\d{2})", low, re.I)]
    facts["copyright_year"] = max(years) if years else None
    if years and max(years) <= year - 3:
        issues.append(issue("dated", 10, f"Looks unmaintained: the footer still says © {max(years)}"))
    gen = re.search(r"<meta[^>]+name=[\"']?generator[\"']?[^>]*content=[\"']([^\"']+)", low, re.I)
    facts["generator"] = gen.group(1)[:60] if gen else ""
    if gen and OLD_TOOLS.search(gen.group(1)):
        issues.append(issue("old_tool", 10, f"Built with an old tool ({gen.group(1)[:40]})"))
    if re.search(r"\.swf\b|application/x-shockwave-flash", low, re.I):
        issues.append(issue("flash", 25, "Uses Flash, which no browser has played since 2021"))
    old_tags = len(re.findall(r"<font\b|<center>|<marquee|<frameset|\bbgcolor=", low, re.I))
    if old_tags >= 3:
        issues.append(issue("old_html", 8, "Old-style code from the early 2000s (font / table layout)"))
    facts["elapsed_s"] = round(elapsed_s, 2)
    facts["bytes"] = int(size or len(low.encode("utf-8", "ignore")))
    if elapsed_s > 5:
        issues.append(issue("slow", 10, f"Slow: the home page took {elapsed_s:.1f} s to arrive (people leave after about 3 s)"))
    elif elapsed_s > 3:
        issues.append(issue("slowish", 5, f"A bit slow: {elapsed_s:.1f} s for the home page"))
    if facts["bytes"] > 1_500_000:
        issues.append(issue("heavy", 5, f"Heavy page: {facts['bytes'] / 1e6:.1f} MB of code before any picture"))
    return {"issues": issues, "facts": facts}


# ------------------------------------------------------------------------------------------------ the network part
_RESOLVER: list = []


def proxied() -> bool:
    """Behind an HTTPS proxy (a company network, a cloud sandbox) a failure can be the proxy's, not the site's."""
    return bool(urllib.request.getproxies().get("https"))


def resolver_works() -> bool:
    """Can this computer look up names itself? Only then does 'the domain does not exist' prove anything."""
    if not _RESOLVER:
        try:
            socket.getaddrinfo("example.com", 443)
            _RESOLVER.append(True)
        except OSError:
            _RESOLVER.append(False)
    return _RESOLVER[0]


def _open(url, timeout):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5", "Accept-Language": "en-US,en;q=0.8"})
    return urllib.request.urlopen(req, timeout=timeout)          # follows redirects (urllib stops after 10)


def robots_ok(url: str, timeout=8) -> bool:
    """True unless the site's robots.txt says no to us (a missing or unreadable robots.txt = allowed)."""
    parts = urllib.parse.urlsplit(url)
    rp = urllib.robotparser.RobotFileParser()
    try:
        with _open(f"{parts.scheme}://{parts.netloc}/robots.txt", timeout) as r:
            if r.status >= 400:
                return True
            rp.parse(r.read(200_000).decode("utf-8", "replace").splitlines())
    except Exception:  # noqa: BLE001 - any failure to read robots.txt means it does not forbid us
        return True
    return rp.can_fetch(ROBOT_NAME, url)


def _kind(err) -> str:
    """One word for why a fetch failed: dns / ssl / timeout / refused / reset / tunnel / other."""
    reason = getattr(err, "reason", err)
    if isinstance(reason, ssl.SSLCertVerificationError) or isinstance(reason, ssl.SSLError):
        return "ssl"
    if isinstance(reason, socket.gaierror):
        return "dns"
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return "timeout"
    if isinstance(reason, ConnectionRefusedError):
        return "refused"
    if isinstance(reason, ConnectionResetError):
        return "reset"
    if "tunnel connection failed" in str(reason).lower():
        return "tunnel"
    return "other"


def fetch_page(url: str, timeout=15) -> dict:
    """GET once. -> {status (0 = no answer), final_url, text, elapsed_s, size, headers, error}."""
    t0 = time.monotonic()
    out = {"status": 0, "final_url": url, "text": "", "elapsed_s": 0.0, "size": 0, "headers": {}, "error": ""}
    try:
        with _open(url, timeout) as r:
            raw = r.read(MAX_BYTES + 1)
            enc = r.headers.get_content_charset() or "utf-8"
            out.update(status=r.status, final_url=r.geturl(), text=raw[:MAX_BYTES].decode(enc, "replace"), size=len(raw), headers=dict(r.headers))
    except urllib.error.HTTPError as e:
        out.update(status=e.code, error=f"http {e.code}")
    except (urllib.error.URLError, OSError, ValueError) as e:
        out["error"] = _kind(e)
    out["elapsed_s"] = time.monotonic() - t0
    return out


def candidates(url: str):
    """An http:// address is tried as https:// first (most sites have it now; and some networks only carry https)."""
    if url.lower().startswith("http://"):
        return ["https://" + url[7:], url]
    return [url]


def audit(url: str, refresh=False, robots=True, fetch=fetch_page, pause=1.0, sleep=time.sleep) -> dict:
    """The full check of one site, cached 30 days. -> {url, checked, fetched, issues, facts, note}.

    A site is called dead or down only when that is certain: a name lookup that fails on a computer whose lookups work,
    or no answer twice without a proxy in the way. Anything less = 'could not check it' (no points either way)."""
    path = os.path.join(ensure_dir(CACHE_DIR), "audit.json")
    try:
        with open(path, encoding="utf-8") as fh:
            store = json.load(fh)
    except (OSError, ValueError):
        store = {}
    hit = store.get(url)
    if hit and not refresh and time.time() - hit.get("t", 0) < AUDIT_TTL:
        return hit
    res = {"url": url, "t": int(time.time()), "checked": dt.date.today().isoformat(), "fetched": False, "issues": [], "facts": {}, "note": ""}
    pre, go = judge_address(url)
    res["issues"] = pre
    if go:
        tries = candidates(url)
        if robots and not robots_ok(tries[0]):
            res["note"] = "Their robots.txt asks tools not to read the site: check it by hand"
        else:
            if pause:
                sleep(pause)
            got, errors, soft = None, [], None
            for i, u in enumerate(tries):
                r = fetch(u)
                if r["status"] in (401, 403, 429) or (proxied() and r["status"] in (502, 503, 504) and not (r.get("headers") or {}).get("Server")):
                    # a bot wall, or an error our own proxy made up (no Server header): it says nothing about the site
                    errors.append(f"blocked {r['status']}")
                    continue
                upgraded = i == 0 and len(tries) == 2          # our https:// try of an http:// address: only a working page counts
                if r["status"] and (not upgraded or r["status"] < 400):
                    got = r
                    break
                if r["status"]:
                    soft = r
                errors.append(r["error"] or f"http {r['status']}")
            if got is None and soft is not None and not proxied():
                got = soft                                   # https answers with an error and http does not answer at all
            if got is None and not proxied() and set(errors) & {"timeout", "reset", "refused", "other"}:
                sleep(3)                                     # one more try before saying it is down
                r = fetch(tries[0])
                got = r if r["status"] and r["status"] not in (401, 403, 429) else None
                errors.append(r["error"])
            res["fetched"] = got is not None
            if got is None and any(e.startswith("blocked") for e in errors):
                res["note"] = "The site blocks automatic checks: open it on your phone before you call"
            elif got is not None:
                a = analyze(got["text"], got["final_url"], got["status"], got["elapsed_s"], got["size"], got["headers"])
                res["issues"] += a["issues"]
                res["facts"] = a["facts"]
                res["final_url"] = got["final_url"]
            elif "dns" in errors and resolver_works():
                res["issues"].append(issue("dead_domain", 60, "Their web address no longer works (the domain does not exist)"))
            elif "ssl" in errors and not proxied() and len(set(errors)) == 1:
                res["issues"].append(issue("bad_cert", 30, "Visitors get a red security warning (the site's certificate is broken)"))
            elif not proxied() and errors:
                res["issues"].append(issue("site_down", 45, "Their website did not open when we checked twice (open it yourself before you call)"))
            else:
                res["note"] = "Could not open the site from this computer: open it on your phone before you call"
            res["errors"] = errors
    res["issues"].sort(key=lambda i: -i["weight"])
    store[url] = res
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(store, fh, ensure_ascii=False)
    os.replace(tmp, path)
    return res
