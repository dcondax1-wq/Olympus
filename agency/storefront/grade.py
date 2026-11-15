#!/usr/bin/env python3
"""Website grader for local businesses: one polite visit to a home page, then a one-page report to email back.

    python agency/storefront/grade.py joesplumbing.com
    python agency/storefront/grade.py joesplumbing.com --name "Joe's Plumbing" --city Springfield --pdf --open
    python agency/storefront/grade.py --batch data/agency/clients.json     every site_url in the shared client records

One visit means: one GET of the home page (redirects followed, at most 5 MB read), a HEAD request for up to 25 of the
files that page loads (pictures, styles, scripts) to weigh it, and one HEAD of the plain http:// address to see whether
it moves to https://. Nothing else is opened, no form is sent, nothing is stored about the visitor. A single check is
done for a business that asked for its report; --batch (cold leads) also reads robots.txt and skips a site that asks
tools to stay away, with 1 second between sites.
It checks: HTTPS, the phone layout (viewport), tap-to-call, a clear call / book / quote button, a Google Business Profile
link, load time, page weight, the title and Google snippet, whether Google may list the page, the main headline,
business details for Google (schema), how up to date it looks and picture descriptions.

Reports go to data/agency/reports/ (that folder keeps itself out of git): <date>-<host>.html (print it, or --pdf) and
.json (the raw numbers). The report wears the agency's name, phone and colour from agency/storefront/config.json.
Standard library only. Exit 0 = graded, 2 = the site did not open (a report saying so is still written), 3 = bad input.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import shutil
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import zlib
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import build  # noqa: E402  (the agency config, colours and prices)

REPORTS = ROOT / "data" / "agency" / "reports"
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 "
      "Mobile/15E148 Safari/604.1 WebsiteCheck/1.0")
MAX_BYTES = 5_000_000
MAX_ASSETS = 25
TIMEOUT = 15
GRADES = ((90, "A"), (75, "B"), (60, "C"), (45, "D"), (0, "F"))
VERDICT = {"A": "In great shape. A few small touches could still bring more calls.",
           "B": "Good, with some easy wins that would bring more calls.",
           "C": "Customers find it, but some leave before they call.",
           "D": "It is turning customers away. Every item below can be fixed in days.",
           "F": "Most people who find this site will call someone else."}


def esc(s) -> str:
    return html.escape(str(s), quote=True)


# ------------------------------------------------------------------------------------------------ fetching (one visit)
class _Recorder(urllib.request.HTTPRedirectHandler):
    def __init__(self):
        super().__init__()
        self.chain = []

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.chain.append([code, newurl])
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class _NoFollow(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _local(url: str) -> bool:
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    return host in ("localhost", "127.0.0.1", "::1") or host.endswith(".localhost")


def _opener(url: str, *handlers):
    hs = list(handlers)
    if _local(url):
        hs.append(urllib.request.ProxyHandler({}))       # tests serve fixtures on this computer: never through a proxy
    return urllib.request.build_opener(*hs)


def normalize_url(raw: str) -> str:
    v = (raw or "").strip()
    if not v:
        raise ValueError("no website address given")
    if not re.match(r"^https?://", v, re.I):
        v = "https://" + v
    u = urllib.parse.urlsplit(v)
    if not u.hostname or ("." not in u.hostname and not _local(v)):
        raise ValueError(f"'{raw}' does not look like a website address")
    return urllib.parse.urlunsplit((u.scheme.lower(), u.netloc.lower(), u.path or "/", u.query, ""))


def _decode(raw: bytes, enc: str) -> bytes:
    """gzip / deflate undone, never past MAX_BYTES (a hostile page cannot blow up in memory)"""
    enc = (enc or "").lower()
    modes = {"gzip": [16 + zlib.MAX_WBITS], "x-gzip": [16 + zlib.MAX_WBITS], "deflate": [zlib.MAX_WBITS, -zlib.MAX_WBITS]}.get(enc)
    for wbits in modes or []:
        try:
            return zlib.decompressobj(wbits).decompress(raw, MAX_BYTES)
        except zlib.error:
            continue
    return raw


def _charset(headers, body: bytes) -> str:
    m = re.search(r"charset=([\w-]+)", headers.get("Content-Type", "") or "", re.I)
    if not m:
        m = re.search(rb"<meta[^>]+charset=[\"']?([\w-]+)", body[:4096], re.I)
    cs = (m.group(1).decode() if m and isinstance(m.group(1), bytes) else (m.group(1) if m else "utf-8"))
    try:
        "".encode(cs)
        return cs
    except LookupError:
        return "utf-8"


def fetch_page(url: str, timeout: float = TIMEOUT) -> dict:
    """GET the page once. Never raises: problems come back in 'error'."""
    rec = _Recorder()
    op = _opener(url, rec)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5",
                                               "Accept-Language": "en-US,en;q=0.8", "Accept-Encoding": "gzip, deflate"})
    out = {"url_in": url, "final_url": url, "status": None, "error": "", "error_kind": "", "headers": {}, "html": "",
           "wire_bytes": 0, "html_bytes": 0, "ttfb_ms": None, "total_ms": None, "redirects": rec.chain}
    t0 = time.perf_counter()
    try:
        resp = op.open(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        resp = e                                           # 404 / 500 still has a page to read
    except urllib.error.URLError as e:
        r = e.reason
        out["error_kind"] = "certificate" if isinstance(r, ssl.SSLError) or "CERTIFICATE" in str(r).upper() else (
            "timeout" if isinstance(r, socket.timeout) or "timed out" in str(r) else "connect")
        out["error"] = str(r)
        out["total_ms"] = round((time.perf_counter() - t0) * 1000)
        return out
    except (socket.timeout, TimeoutError) as e:
        out.update(error=f"no answer within {timeout:.0f} seconds ({e})", error_kind="timeout")
        return out
    except (ValueError, OSError, ssl.SSLError) as e:
        out.update(error=str(e), error_kind="connect")
        return out
    t1 = time.perf_counter()
    try:
        raw = resp.read(MAX_BYTES + 1)
    except (OSError, socket.timeout) as e:
        raw = b""
        out["error"], out["error_kind"] = f"the page stopped loading ({e})", "timeout"
    t2 = time.perf_counter()
    headers = {k.lower(): v for k, v in (resp.headers.items() if resp.headers else [])}
    body = _decode(raw[:MAX_BYTES], headers.get("content-encoding", ""))
    out.update(status=getattr(resp, "status", None) or resp.getcode(), final_url=resp.geturl() or url, headers=headers,
               wire_bytes=len(raw[:MAX_BYTES]), html_bytes=len(body), ttfb_ms=round((t1 - t0) * 1000), total_ms=round((t2 - t0) * 1000),
               html=body.decode(_charset(resp.headers or {}, body), "replace"))
    if out["status"] and out["status"] >= 400 and not out["error"]:
        out["error"], out["error_kind"] = f"the home page answered with error {out['status']}", "http"
    return out


def head_size(url: str, timeout: float = 10) -> tuple:
    """(bytes or None, status) for one file, by HEAD (no download)"""
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
    try:
        resp = _opener(url).open(req, timeout=timeout)
        n = resp.headers.get("Content-Length")
        return (int(n) if n and n.isdigit() else None), resp.status
    except urllib.error.HTTPError as e:
        return None, e.code
    except (urllib.error.URLError, OSError, ValueError):
        return None, None


def robots_allows(url: str, timeout: float = 10):
    """True / False from the site's robots.txt for this tool, None = no robots.txt or it could not be read (= allowed)"""
    import urllib.robotparser
    u = urllib.parse.urlsplit(url)
    robots = urllib.parse.urlunsplit((u.scheme, u.netloc, "/robots.txt", "", ""))
    try:
        resp = _opener(robots).open(urllib.request.Request(robots, headers={"User-Agent": UA}), timeout=timeout)
        lines = resp.read(200_000).decode("utf-8", "replace").splitlines()
    except (urllib.error.URLError, OSError, ValueError):
        return None
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(lines)
    return rp.can_fetch("WebsiteCheck", url)


def http_moves_to_https(url: str, timeout: float = 10):
    """True / False / None (could not tell): does http://host/ send visitors on to https://?"""
    u = urllib.parse.urlsplit(url)
    plain = urllib.parse.urlunsplit(("http", u.netloc, "/", "", ""))
    req = urllib.request.Request(plain, method="HEAD", headers={"User-Agent": UA})
    try:
        resp = _opener(plain, _NoFollow()).open(req, timeout=timeout)
        return False if resp.status < 300 else None
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 303, 307, 308):
            return (e.headers.get("Location") or "").lower().startswith("https://")
        return None
    except (urllib.error.URLError, OSError, ValueError):
        return None


def visit(url: str, assets: bool = True, max_assets: int = MAX_ASSETS, pause: float = 0.1) -> tuple:
    """the whole polite visit -> (net facts, parsed page)"""
    net = fetch_page(url)
    if net["error_kind"] in ("connect", "timeout") and url.startswith("https://") and not net["status"]:
        alt = fetch_page("http://" + url[len("https://"):])           # no https at all? try the plain address once
        if alt["status"]:
            alt["https_failed"] = net["error"]
            net = alt
    elif net["error_kind"] == "certificate":
        alt = fetch_page("http://" + url[len("https://"):])
        if alt["status"]:
            alt["https_failed"] = "certificate problem: " + net["error"]
            net = alt
    page = analyse(net.get("html") or "", net.get("final_url") or url)
    net["assets"] = []
    net["http_to_https"] = None
    if net.get("status") and net["final_url"].startswith("https://") and not _local(net["final_url"]):
        net["http_to_https"] = http_moves_to_https(net["final_url"])
    if assets and net.get("status") and net["status"] < 400:
        t_end = time.monotonic() + 40                               # weighing never takes more than about 40 seconds
        for a in page["assets"][:max_assets]:
            if time.monotonic() > t_end:
                break
            size, st = head_size(a["url"])
            net["assets"].append({**a, "bytes": size, "status": st})
            time.sleep(pause)
    net["assets_total"] = len(page["assets"])
    return net, page


# ------------------------------------------------------------------------------------------------ reading the page
CTA_RX = re.compile(r"\b(call(?: us| now| today)?|text us|book(?:ing)?(?: now| online| a| an| your)?|schedule|appointments?|"
                    r"(?:get|request)(?: a| your)?(?: free)? (?:quote|estimate|appointment|service)|free (?:quote|estimate|consultation)|"
                    r"contact us|reserve|reservations?|order (?:now|online|pickup|delivery)|get started|hire us)\b", re.I)
BOOKING_HOSTS = ("calendly.com", "cal.com", "acuityscheduling.com", "squareup.com", "square.site", "booksy.com", "vagaro.com",
                 "fresha.com", "opentable.com", "resy.com", "toasttab.com", "housecallpro.com", "getjobber.com", "jobber.com",
                 "schedulicity.com", "setmore.com", "styleseat.com", "zocdoc.com", "yelp.com/reservations", "tock.com")
GOOGLE_RX = re.compile(r"(google\.[a-z.]{2,6}/maps|maps\.google\.|goo\.gl/maps|maps\.app\.goo\.gl|g\.page/|business\.google\.com|"
                       r"search\.google\.com/local|g\.co/kgs|share\.google/|google\.[a-z.]{2,6}/search\?[^\s\"']*(?:ludocid|kgmid))", re.I)
PHONE_RX = re.compile(r"(?:\+?1[\s.\-]?)?\(?\b[2-9]\d{2}\)?[\s.\-]\d{3}[\s.\-]\d{4}\b|\+\d{1,3}[\s.\-]\(?\d{1,4}\)?(?:[\s.\-]\d{2,4}){2,4}")
YEAR_RX = re.compile(r"(?:\u00a9|\(c\)|copyright)\s*(?:\d{4}\s*(?:-|\u2013|to)\s*)?((?:19|20)\d{2})", re.I)
ADDRESS_RX = re.compile(r"\b\d{1,5}\s+\w+(?:\s\w+)?\s(?:street|st\.?|avenue|ave\.?|road|rd\.?|boulevard|blvd\.?|drive|dr\.?|lane|ln\.?|way|square|sq\.?|suite)\b", re.I)
LOCAL_TYPES = {"localbusiness", "professionalservice", "homeandconstructionbusiness", "plumber", "electrician", "hvacbusiness",
               "roofingcontractor", "generalcontractor", "housepainter", "locksmith", "movingcompany", "hairsalon", "beautysalon",
               "nailsalon", "dayspa", "healthandbeautybusiness", "restaurant", "cafeorcoffeeshop", "foodestablishment", "bakery",
               "barorpub", "autorepair", "automotivebusiness", "autobodyshop", "dentist", "medicalbusiness", "store", "cleaningservice"}
SKIP_TEXT = {"script", "style", "noscript", "template", "svg", "title"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class _Reader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lang = None
        self.title = ""
        self.metas, self.linktags, self.anchors, self.buttons, self.imgs = [], [], [], [], []
        self.scripts, self.iframes, self.jsonld, self.h1, self.styles = [], [], [], [], []
        self.text = []
        self.forms = 0
        self.order = 0
        self.old = set()
        self.stack = []
        self._skip = 0
        self._title = False
        self._ld = None
        self._style = None
        self._a = None
        self._btn = None
        self._h1 = None

    def _in_header(self) -> bool:
        for tag, attrs in self.stack:
            if tag in ("header", "nav"):
                return True
            ident = (attrs.get("id", "") + " " + attrs.get("class", "")).lower()
            if re.search(r"\b(header|masthead|topbar|top-bar|navbar)\b", ident):
                return True
        return False

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        self.order += 1
        if tag in ("marquee", "blink", "font", "center", "frameset", "frame", "applet"):
            self.old.add(tag)
        if tag in ("embed", "object") and ".swf" in (a.get("src", "") + a.get("data", "")).lower():
            self.old.add("flash")
        if tag == "html":
            self.lang = a.get("lang") or None
        elif tag == "title":
            self._title = True
        elif tag == "meta":
            self.metas.append(a)
        elif tag == "link":
            self.linktags.append(a)
        elif tag == "a":
            self._a = {"href": a.get("href", ""), "text": "", "label": a.get("aria-label", "") + " " + a.get("title", ""),
                       "order": self.order, "top": self._in_header()}
        elif tag == "button" or (tag == "input" and a.get("type", "").lower() in ("submit", "button")):
            b = {"text": a.get("value", ""), "label": a.get("aria-label", ""), "order": self.order, "top": self._in_header()}
            self.buttons.append(b)
            if tag == "button":
                self._btn = b
        elif tag == "img":
            self.imgs.append({"src": a.get("src", "") or a.get("data-src", ""), "alt": a.get("alt"), "order": self.order})
        elif tag == "script":
            t = a.get("type", "").lower()
            if a.get("src"):
                self.scripts.append(a["src"])
            if t == "application/ld+json":
                self._ld = []
        elif tag == "iframe":
            self.iframes.append(a.get("src", ""))
        elif tag == "form":
            self.forms += 1
        elif tag == "h1":
            self._h1 = []
        elif tag == "style":
            self._style = []
        if tag in SKIP_TEXT:
            self._skip += 1
        if tag not in VOID:
            self.stack.append((tag, a))

    def handle_endtag(self, tag):
        if tag == "title":
            self._title = False
        elif tag == "a" and self._a is not None:
            self.anchors.append(self._a)
            self._a = None
        elif tag == "button":
            self._btn = None
        elif tag == "h1" and self._h1 is not None:
            self.h1.append(" ".join("".join(self._h1).split()))
            self._h1 = None
        elif tag == "script" and self._ld is not None:
            self.jsonld.append("".join(self._ld))
            self._ld = None
        elif tag == "style" and self._style is not None:
            self.styles.append("".join(self._style))
            self._style = None
        if tag in SKIP_TEXT and self._skip:
            self._skip -= 1
        for i in range(len(self.stack) - 1, -1, -1):          # pop back to the matching tag (forgiving of sloppy HTML)
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        if self._title:
            self.title += data
        if self._ld is not None:
            self._ld.append(data)
        if self._style is not None:
            self._style.append(data)
        if self._skip:
            return
        self.text.append(data)
        if self._a is not None:
            self._a["text"] += data
        if self._btn is not None:
            self._btn["text"] += data
        if self._h1 is not None:
            self._h1.append(data)


def _types(node, out):
    if isinstance(node, dict):
        t = node.get("@type")
        for x in (t if isinstance(t, list) else [t]):
            if isinstance(x, str):
                out.add(x.lower())
        for v in node.values():
            _types(v, out)
    elif isinstance(node, list):
        for v in node:
            _types(v, out)


def analyse(page_html: str, base_url: str) -> dict:
    """everything the checks need, from the page's own HTML"""
    r = _Reader()
    try:
        r.feed(page_html)
        r.close()
    except Exception:  # noqa: BLE001  (a broken page is graded on what could be read)
        pass
    meta = {}
    for m in r.metas:
        key = (m.get("name") or m.get("property") or m.get("http-equiv") or "").lower()
        if key and key not in meta:
            meta[key] = m.get("content", "")
    text = " ".join(" ".join(r.text).split())
    abs_url = lambda u: urllib.parse.urljoin(base_url, u.strip())  # noqa: E731
    host = (urllib.parse.urlsplit(base_url).hostname or "").lower()
    assets = []
    for l in r.linktags:
        if "stylesheet" in l.get("rel", "").lower() and l.get("href"):
            assets.append({"url": abs_url(l["href"]), "kind": "style"})
    assets += [{"url": abs_url(s), "kind": "script"} for s in r.scripts if s.strip()]
    assets += [{"url": abs_url(i["src"]), "kind": "image"} for i in r.imgs if i["src"].strip() and not i["src"].startswith("data:")]
    seen, uniq = set(), []
    for a in assets:
        if a["url"].startswith(("http://", "https://")) and a["url"] not in seen:
            seen.add(a["url"])
            a["third_party"] = (urllib.parse.urlsplit(a["url"]).hostname or "").lower() != host
            uniq.append(a)
    types = set()
    for block in r.jsonld:
        try:
            _types(json.loads(block), types)
        except ValueError:
            continue
    clickable = [dict(x, kind="a") for x in r.anchors] + [dict(x, kind="button", href="") for x in r.buttons]
    years = [int(y) for y in YEAR_RX.findall(text)]
    return {
        "lang": r.lang, "title": " ".join(r.title.split()), "meta": meta, "text_len": len(text), "elements": max(1, r.order),
        "h1": r.h1, "anchors": r.anchors, "clickable": clickable, "imgs": r.imgs, "iframes": [abs_url(i) for i in r.iframes if i],
        "forms": r.forms, "old": sorted(r.old), "jsonld_types": sorted(types), "assets": uniq,
        "phones_text": sorted(set(m.strip() for m in PHONE_RX.findall(text)))[:5], "address_text": bool(ADDRESS_RX.search(text)),
        "copyright_year": max(years) if years else None, "styles_media": any("@media" in s for s in r.styles),
        "linked_css": sum(1 for a in uniq if a["kind"] == "style"),
    }


# ------------------------------------------------------------------------------------------------ the checks
def _near_top(item: dict, page: dict) -> bool:
    return bool(item.get("top")) or item.get("order", 10 ** 9) <= max(40, page["elements"] * 0.3)


def kb(n) -> str:
    if n is None:
        return "?"
    return f"{n / 1_000_000:.1f} MB" if n >= 1_000_000 else f"{max(1, round(n / 1000))} KB"


def check_all(net: dict, page: dict, city: str = "", today: dt.date | None = None) -> list:
    """[{id, label, status pass|warn|fail, points, max, found, fix, plan}] in a fixed order"""
    today = today or dt.date.today()
    C = []

    def add(cid, label, mx, status, pts, found, fix, plan="starter", critical=False):
        C.append({"id": cid, "label": label, "max": mx, "status": status, "points": pts if status != "pass" else mx,
                  "found": found, "fix": fix if status != "pass" else "", "plan": plan, "critical": critical and status != "pass"})

    final = net.get("final_url") or ""
    https = final.startswith("https://")
    mixed = [a["url"] for a in net.get("assets") or page["assets"] if https and a["url"].startswith("http://")]
    if net.get("https_failed"):
        add("https", "Secure padlock (HTTPS)", 14, "fail", 0, "The secure address does not work: " + net["https_failed"][:90],
            "Turn on HTTPS (the padlock). Browsers warn 'Not secure' today and many visitors leave.")
    elif not https:
        add("https", "Secure padlock (HTTPS)", 14, "fail", 0, "The site opens without the padlock (http://).",
            "Turn on HTTPS (the padlock). Browsers show 'Not secure' and many visitors leave.")
    elif mixed:
        add("https", "Secure padlock (HTTPS)", 14, "warn", 10, f"Padlock on, but {len(mixed)} file(s) still load unsafely over http://.",
            "Load every picture and script over https:// so the padlock stays clean.")
    elif net.get("http_to_https") is False:
        add("https", "Secure padlock (HTTPS)", 14, "warn", 10, "Padlock works, but the plain http:// address does not move to it.",
            "Send the plain address on to https:// so everyone gets the padlock.")
    else:
        add("https", "Secure padlock (HTTPS)", 14, "pass", 14, "Padlock on" + (", and http:// moves to it." if net.get("http_to_https") else "."), "")

    vp = page["meta"].get("viewport", "")
    if "width=device-width" in vp.replace(" ", "").lower():
        zoom = re.search(r"user-scalable\s*=\s*(no|0)|maximum-scale\s*=\s*1(\.0+)?\b", vp, re.I)
        if zoom:
            add("mobile", "Works on phones", 14, "warn", 10, "Made for phones, but it stops people zooming in.",
                "Let people zoom (remove user-scalable=no / maximum-scale=1): it helps anyone with weaker eyes.")
        else:
            add("mobile", "Works on phones", 14, "pass", 14, "Set up for phone screens.", "")
    else:
        add("mobile", "Works on phones", 14, "fail", 0, "No phone layout: phones show a shrunken desktop page" + (" (viewport set to a fixed width)." if vp else "."),
            "Rebuild it mobile-first. Most local customers look you up on a phone, and tiny text sends them away.")

    tels = [a for a in page["anchors"] if a["href"].lower().startswith("tel:")]
    if tels:
        top = any(_near_top(a, page) for a in tels)
        num = re.sub(r"[^\d+]", "", urllib.parse.unquote(tels[0]["href"][4:])) or "number"
        add("tap_call", "Tap-to-call", 14, "pass" if top else "warn", 14 if top else 10,
            f"Tap-to-call {'near the top' if top else 'only lower down the page'} ({num[:24]}).",
            "Move the tap-to-call button to the top of the page so it is the first thing people can tap.")
    elif page["phones_text"]:
        add("tap_call", "Tap-to-call", 14, "warn", 4, f"Phone number shown ({page['phones_text'][0]}) but it can't be tapped.",
            "Make your phone number a tap-to-call button. Today people have to copy it by hand.")
    else:
        add("tap_call", "Tap-to-call", 14, "fail", 0, "No phone number found on the home page.",
            "Put your phone number at the top as a big tap-to-call button.")

    ms = net.get("total_ms")
    if ms is None:
        add("speed", "Opens fast", 10, "fail", 0, "The page did not finish loading.", "Find out why the page does not load, then make it light and fast.")
    else:
        st = "pass" if ms <= 1000 else "warn" if ms <= 2500 else "fail"
        add("speed", "Opens fast", 10, st, {"pass": 10, "warn": 5, "fail": 0}[st],
            f"Home page arrived in {ms / 1000:.1f} s" + (f" (first byte {net['ttfb_ms'] / 1000:.1f} s)." if net.get("ttfb_ms") is not None else "."),
            "Speed up the server and the page: people leave a slow site within seconds.")

    measured = [a for a in net.get("assets") or [] if a.get("bytes")]
    total = (net.get("wire_bytes") or 0) + sum(a["bytes"] for a in measured)
    big = [a for a in measured if a["kind"] == "image" and a["bytes"] > 400_000]
    n_files = net.get("assets_total", len(page["assets"]))
    note = f"About {kb(total)} for the page and {len(measured)} of its {n_files} files"
    if big:
        note += f"; {len(big)} picture(s) over 400 KB"
    st = "pass" if total <= 1_500_000 and not big else "warn" if total <= 3_000_000 else "fail"
    add("weight", "Light page", 8, st, {"pass": 8, "warn": 4, "fail": 0}[st], note + ".",
        "Shrink the big pictures and drop heavy add-ons: a light page opens fast on mobile data.")

    ctas = [c for c in page["clickable"] if CTA_RX.search((c.get("text") or "") + " " + (c.get("label") or ""))
            or any(h in (c.get("href") or "").lower() for h in BOOKING_HOSTS)]
    if any(_near_top(c, page) for c in ctas):
        add("cta", "Clear next step (call, book, quote)", 8, "pass", 8, "A clear call / book / quote button near the top.", "")
    elif ctas or page["forms"]:
        add("cta", "Clear next step (call, book, quote)", 8, "warn", 4, "The next step is only further down the page." if ctas else "A form, but no clear button saying what to do.",
            "Put one big button at the top: 'Call now', 'Book online' or 'Get a free quote'.")
    else:
        add("cta", "Clear next step (call, book, quote)", 8, "fail", 0, "No button telling people to call, book or ask for a quote.",
            "Add one big button at the top: 'Call now', 'Book online' or 'Get a free quote'.")

    g = [a["href"] for a in page["anchors"] if GOOGLE_RX.search(a["href"])] + [s for s in page["iframes"] if GOOGLE_RX.search(s)]
    if g:
        add("google", "Google Business Profile linked", 8, "pass", 8, "Links to your Google map / reviews.", "", "growth")
    else:
        add("google", "Google Business Profile linked", 8, "fail", 0,
            "Your address is on the page, but nothing links to your Google profile." if page["address_text"] else "No link to a Google Business Profile or map.",
            "Link your Google Business Profile (map and reviews) from the site, and keep the profile filled in.", "growth")

    t = page["title"]
    if not t:
        add("title", "Page title for Google", 7, "fail", 0, "No page title.", "Give the page a title like 'Plumber in Springfield | Joe's Plumbing'.")
    elif len(t) < 10 or len(t) > 65:
        add("title", "Page title for Google", 7, "warn", 3, f"Title is {len(t)} characters: '{t[:60]}'.",
            "Write a 30-60 character title with your trade and town, e.g. 'Plumber in Springfield | Joe's Plumbing'.")
    elif city and city.lower() not in t.lower():
        add("title", "Page title for Google", 7, "warn", 4, f"Title '{t[:60]}' does not mention {city}.",
            f"Put your town in the title, e.g. 'Plumber in {city} | your business name'.")
    else:
        add("title", "Page title for Google", 7, "pass", 7, f"'{t[:60]}'.", "")

    d = page["meta"].get("description", "").strip()
    if not d:
        add("description", "Google snippet (description)", 5, "fail", 0, "No description for Google to show.",
            "Add a one-sentence description: what you do, where, and why call you.")
    elif not 50 <= len(d) <= 170:
        add("description", "Google snippet (description)", 5, "warn", 2, f"Description is {len(d)} characters.",
            "Write a 50-160 character description: what you do, where, and why call you.")
    else:
        add("description", "Google snippet (description)", 5, "pass", 5, f"{len(d)} characters.", "")

    robots = (page["meta"].get("robots", "") + " " + page["meta"].get("googlebot", "") + " " + (net.get("headers") or {}).get("x-robots-tag", "")).lower()
    if "noindex" in robots:
        add("indexable", "Allowed on Google", 4, "fail", 0, "The page tells Google NOT to list it (noindex).",
            "Remove the 'noindex' setting, or Google will keep this page out of search results.", critical=True)
    else:
        add("indexable", "Allowed on Google", 4, "pass", 4, "Google may list it.", "")

    h = page["h1"]
    if len(h) == 1:
        add("h1", "Main headline", 3, "pass", 3, f"'{h[0][:60]}'.", "")
    elif not h:
        add("h1", "Main headline", 3, "fail", 0, "No main headline (H1).", "Start the page with one clear headline: what you do and where.")
    else:
        add("h1", "Main headline", 3, "warn", 2, f"{len(h)} main headlines (H1) instead of one.", "Keep one main headline (H1) that says what you do and where.")

    lt = [x for x in page["jsonld_types"] if x in LOCAL_TYPES or x.endswith(("business", "contractor", "salon", "shop", "store", "restaurant"))]
    if lt:
        add("local_data", "Business details for Google", 2, "pass", 2, "Business details marked up (" + ", ".join(lt[:2]) + ").", "")
    else:
        add("local_data", "Business details for Google", 2, "warn", 0, "No business details (name, hours, phone) marked up for Google.",
            "Add LocalBusiness details (schema) so Google shows your hours and phone correctly.")

    y = page["copyright_year"]
    old = page["old"]
    if old:
        add("fresh", "Looks up to date", 2, "warn", 0, "Old web tech on the page: " + ", ".join(old) + (f"; © {y}." if y else "."),
            "Replace the old-style parts: they look dated and break on phones.")
    elif y and y < today.year - 1:
        add("fresh", "Looks up to date", 2, "warn", 0, f"The page says \u00a9 {y}: it looks like nobody has touched it since.",
            "Update the year, prices and hours. An old date makes people think you closed.")
    else:
        add("fresh", "Looks up to date", 2, "pass", 2, f"\u00a9 {y}." if y else "No old dates found.", "")

    imgs = page["imgs"]
    ok = sum(1 for i in imgs if i["alt"] is not None)
    if not imgs or ok / len(imgs) >= 0.8:
        add("alt", "Picture descriptions", 1, "pass", 1, f"{ok} of {len(imgs)} pictures described." if imgs else "No pictures to describe.", "")
    else:
        add("alt", "Picture descriptions", 1, "warn", 0, f"Only {ok} of {len(imgs)} pictures have a description (alt text).",
            "Describe each picture in a few words: it helps blind visitors and Google Images.")
    return C


def summarize(checks: list) -> dict:
    score = round(sum(c["points"] for c in checks) * 100 / max(1, sum(c["max"] for c in checks)))
    letter = next(g for lim, g in GRADES if score >= lim)
    todo = [c for c in checks if c["status"] != "pass"]
    todo.sort(key=lambda c: (not c.get("critical"), -(c["max"] - c["points"]), -c["max"]))   # a page hidden from Google comes first
    return {"score": score, "grade": letter, "verdict": VERDICT[letter], "fixes": todo[:3], "plan": "growth" if any(c["plan"] == "growth" for c in todo) else "starter"}


def grade_offline(page_html: str, url: str = "https://example.test/", net: dict | None = None, city: str = "", today: dt.date | None = None) -> dict:
    """grade HTML you already have (tests, saved pages); net = the visit numbers if known"""
    page = analyse(page_html, url)
    n = {"final_url": url, "status": 200, "total_ms": 400, "ttfb_ms": 150, "wire_bytes": len(page_html.encode()), "assets": [],
         "assets_total": len(page["assets"]), "http_to_https": True, "headers": {}}
    n.update(net or {})
    checks = check_all(n, page, city, today)
    return {"url": url, "net": n, "page": page, "checks": checks, **summarize(checks)}


# ------------------------------------------------------------------------------------------------ the report
def agency_brand() -> dict:
    try:
        cfg = build.load_config()
        b = build.parse_brand(cfg["brand_color"])
        pal = build.css_presets()[b["preset"]]
        if b["custom"]:
            pal = {**pal, **b["custom"]}
        pk = {p["id"]: p for p in cfg["packages"]}
        return {"agency": cfg["agency"], "pal": pal, "packages": pk, "offer": cfg["offer"]}
    except Exception:  # noqa: BLE001  (the report still renders, plainly, if the config is broken)
        return {"agency": {"name": "Website check", "phone": "", "email": "", "booking_url": ""},
                "pal": {"--brand": "#1F3B5C", "--brand-ink": "#FFFFFF", "--brand-soft": "#E5ECF4", "--ink": "#17181C", "--muted": "#5C606B",
                        "--line": "#E2E2E2", "--bg": "#FFFFFF"}, "packages": {}, "offer": {}}


def report_html(res: dict, business: str = "", when: dt.datetime | None = None) -> str:
    when = when or dt.datetime.now()
    br = agency_brand()
    a, pal = br["agency"], br["pal"]
    host = urllib.parse.urlsplit(res["url"]).hostname or res["url"]
    who = business or host
    color = {"A": "#1E7A4C", "B": "#3B7A2E", "C": "#9A5B00", "D": "#B42A2F", "F": "#B42A2F"}[res["grade"]]
    ring = 326.73
    off = ring * (1 - res["score"] / 100)
    sym = {"pass": ("\u2713", "ok"), "warn": ("!", "warn"), "fail": ("\u2717", "bad")}
    rows = "".join(f'<tr class="{sym[c["status"]][1]}"><td class="s">{sym[c["status"]][0]}</td><td class="l">{esc(c["label"])}</td>'
                   f'<td class="f">{esc(c["found"])}</td></tr>' for c in res["checks"])
    if res.get("down"):
        rows = (f'<tr class="bad"><td class="s">{sym["fail"][0]}</td><td class="l">Website opens</td>'
                f'<td class="f">{esc(res["down"])}</td></tr>')
    if res.get("fixes"):
        fixes = "".join(f"<li><strong>{esc(c['label'])}</strong><span>{esc(c['fix'])}</span></li>" for c in res["fixes"])
        fixes_html = f'<section class="fixes"><h2>Your top {len(res["fixes"])} fixes</h2><ol>{fixes}</ol></section>'
    else:
        fixes_html = '<section class="fixes"><h2>Nothing urgent</h2><p>Every check passed. Nice work.</p></section>'
    plan = br["packages"].get(res.get("plan", "starter")) or next(iter(br["packages"].values()), None)
    offer = ""
    if plan:
        offer = (f'<p class="offer-main">We can fix {"all of this" if res.get("fixes") else "the small stuff"} with our <b>{esc(plan["name"])}</b> plan: '
                 f'{build.money(plan["setup_usd"])} setup + {build.money(plan["monthly_usd"])} a month, live in {esc(br["offer"].get("launch_days", 7))} days. '
                 "We build a free demo first, so you see it before you pay.</p>")
    contact = " · ".join(x for x in (esc(a.get("phone", "")), esc(a.get("email", "")), esc(a.get("booking_url", ""))) if x)
    down = res.get("down")
    day = f"{when:%B} {when.day}, {when.year}"                  # no %-d: Windows does not know it
    clock = when.strftime("%I:%M %p").lstrip("0")
    lead = (f"We could not open this website on {day}: {esc(down)}. Customers may be seeing the same thing." if down else esc(res["verdict"]))
    n_meas = len([x for x in res["net"].get("assets") or [] if x.get("bytes")])
    how = (f"How we checked: one visit to the home page from our office computer on {day} at {clock}"
           + (f", {res['net']['total_ms'] / 1000:.1f} s" if res["net"].get("total_ms") is not None else "")
           + (f", {n_meas} of its files weighed" if n_meas else "")
           + ". A phone on mobile data will be slower. For Google's own test, open pagespeed.web.dev and type your address.")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Website check: {esc(who)} | {esc(a.get('name', ''))}</title>
<style>
@page {{ size: letter; margin: 11mm 12mm; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: #EEECE8; color: {pal['--ink']}; font: 400 10.5pt/1.42 -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, Arial, sans-serif; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
.sheet {{ max-width: 8.5in; margin: 18px auto; padding: 30px 34px 22px; background: #fff; border-radius: 6px; box-shadow: 0 10px 40px -18px rgba(0,0,0,.35); }}
.rh {{ display: flex; justify-content: space-between; align-items: center; padding-bottom: 12px; border-bottom: 3px solid {pal['--brand']}; }}
.brand {{ display: flex; align-items: center; gap: 9px; font-weight: 800; letter-spacing: .06em; text-transform: uppercase; font-size: 10pt; }}
.mark {{ display: inline-grid; place-items: center; width: 30px; height: 30px; border-radius: 9px; background: {pal['--brand']}; color: {pal['--brand-ink']}; font-size: 9pt; letter-spacing: 0; }}
.meta {{ color: {pal['--muted']}; font-size: 9pt; }}
.top {{ display: flex; gap: 22px; align-items: center; margin: 18px 0 8px; }}
.ring {{ position: relative; width: 116px; height: 116px; flex: none; }}
.ring svg {{ width: 116px; height: 116px; transform: rotate(-90deg); }}
.ring .num {{ position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; margin: 0; font-size: 30pt; font-weight: 800; letter-spacing: -.04em; }}
.ring .num small {{ font-size: 8.5pt; color: {pal['--muted']}; margin: 16px 0 0 1px; letter-spacing: 0; }}
.badge {{ display: inline-block; padding: 3px 10px; border-radius: 7px; background: {color}; color: #fff; font-weight: 800; font-size: 10pt; }}
h1 {{ margin: 6px 0 2px; font-size: 19pt; letter-spacing: -.02em; line-height: 1.1; }}
.url {{ margin: 0 0 6px; color: {pal['--muted']}; font-size: 9pt; word-break: break-all; }}
.lead {{ margin: 0; font-size: 11pt; }}
h2 {{ margin: 14px 0 6px; font-size: 9pt; letter-spacing: .14em; text-transform: uppercase; color: {pal['--muted']}; }}
.fixes ol {{ margin: 0; padding: 0; list-style: none; counter-reset: f; display: grid; gap: 6px; }}
.fixes li {{ position: relative; padding: 7px 10px 7px 38px; border-radius: 8px; background: {pal['--brand-soft']}; counter-increment: f; }}
.fixes li::before {{ content: counter(f); position: absolute; left: 9px; top: 7px; width: 20px; height: 20px; border-radius: 6px; background: {pal['--brand']}; color: {pal['--brand-ink']}; font-weight: 800; font-size: 9pt; display: grid; place-items: center; }}
.fixes strong {{ display: block; }}
table {{ width: 100%; border-collapse: collapse; font-size: 9pt; }}
td {{ padding: 4px 6px; border-bottom: 1px solid #ECE7DF; vertical-align: top; }}
td.s {{ width: 22px; text-align: center; font-weight: 800; }}
td.l {{ width: 34%; font-weight: 650; }}
tr.ok td.s {{ color: #1E7A4C; }} tr.warn td.s {{ color: #9A5B00; }} tr.bad td.s {{ color: #B42A2F; }}
.offer {{ margin-top: 14px; padding: 12px 14px; border-radius: 10px; border: 1.5px solid {pal['--brand']}; }}
.offer p {{ margin: 0; }}
.offer .contact {{ margin-top: 4px; font-weight: 700; }}
.how {{ margin-top: 10px; color: {pal['--muted']}; font-size: 8pt; }}
@media print {{ body {{ background: #fff; }} .sheet {{ margin: 0; padding: 0; max-width: none; box-shadow: none; border-radius: 0; }} }}
</style>
</head>
<body>
<main class="sheet">
  <header class="rh"><p class="brand"><span class="mark">{esc(build.initials(a.get('name', '')))}</span>{esc(a.get('name', ''))}</p><p class="meta">Website check · {day}</p></header>
  <section class="top">
    <div class="ring"><svg viewBox="0 0 120 120" aria-hidden="true"><circle cx="60" cy="60" r="52" fill="none" stroke="#ECE7DF" stroke-width="12"/><circle cx="60" cy="60" r="52" fill="none" stroke="{color}" stroke-width="12" stroke-linecap="round" stroke-dasharray="{ring}" stroke-dashoffset="{off:.1f}"/></svg><p class="num">{res['score']}<small>/100</small></p></div>
    <div><span class="badge">Grade {res['grade']}</span><h1>{esc(who)}</h1><p class="url">{esc(res['net'].get('final_url') or res['url'])}</p><p class="lead">{lead}</p></div>
  </section>
  {fixes_html}
  <section><h2>Everything we checked</h2><table>{rows}</table></section>
  <section class="offer">{offer}<p class="contact">{contact}</p></section>
  <p class="how">{esc(how)}</p>
</main>
</body>
</html>
"""


# ------------------------------------------------------------------------------------------------ running it
def reports_dir(path: Path | None = None) -> Path:
    d = Path(path) if path else REPORTS
    d.mkdir(parents=True, exist_ok=True)
    gi = d / ".gitignore"
    if not path and not gi.exists():
        gi.write_text("# prospects' reports: never committed\n*\n", encoding="utf-8")
    return d


def slug(host: str) -> str:
    return re.sub(r"[^a-z0-9.-]+", "-", host.lower()).strip("-.")[:60] or "site"


def find_browser() -> str | None:
    cands = [os.environ.get("CHROME_PATH", "")]
    for name in ("msedge", "chrome", "google-chrome", "chromium", "chromium-browser"):
        cands.append(shutil.which(name) or "")
    cands += [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]
    cands += sorted(str(p) for p in Path("/opt/pw-browsers").glob("chromium-*/chrome-linux/chrome")) if Path("/opt/pw-browsers").exists() else []
    return next((c for c in cands if c and Path(c).exists()), None)


def to_pdf(html_path: Path) -> Path | None:
    exe = find_browser()
    if not exe:
        return None
    pdf = html_path.parent / (html_path.name[:-5] + ".pdf" if html_path.name.endswith(".html") else html_path.name + ".pdf")
    args = [exe, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--print-to-pdf-no-header", f"--print-to-pdf={pdf}", html_path.resolve().as_uri()]
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        args.insert(1, "--no-sandbox")
    try:
        subprocess.run(args, capture_output=True, timeout=90)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return pdf if pdf.exists() and pdf.stat().st_size > 500 else None


def grade_url(raw_url: str, out_dir: Path | None = None, business: str = "", city: str = "", assets: bool = True, pdf: bool = False,
              today: dt.date | None = None) -> dict:
    url = normalize_url(raw_url)
    net, page = visit(url, assets=assets)
    checks = check_all(net, page, city, today)
    res = {"url": url, "net": {k: v for k, v in net.items() if k != "html"}, "checks": checks, **summarize(checks),
           "checked_at": dt.datetime.now().isoformat(timespec="seconds"), "business": business}
    if not net.get("status") or (net.get("status") or 0) >= 400:
        res.update(score=0, grade="F", verdict=VERDICT["F"], down=net.get("error") or "no answer",
                   fixes=[{"label": "Your website did not open", "fix": "Get it back online first: every visitor sees this error today.", "max": 100, "points": 0}])
    d = reports_dir(out_dir)
    host = urllib.parse.urlsplit(net.get("final_url") or url).hostname or "site"
    stem = f"{dt.date.today():%Y-%m-%d}-{slug(host)}"          # joesplumbing.com keeps its .com (no with_suffix)
    page_file, data_file = d / f"{stem}.html", d / f"{stem}.json"
    page_file.write_text(report_html(res, business), encoding="utf-8")
    data_file.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    res["report"] = str(page_file)
    if pdf:
        p = to_pdf(page_file)
        res["pdf"] = str(p) if p else ""
    return res


def read_batch(path: Path) -> list:
    raw = path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except ValueError:
        return [{"id": "", "name": "", "site_url": ln.strip()} for ln in raw.splitlines() if ln.strip() and not ln.startswith("#")]
    if isinstance(data, dict):
        data = data.get("clients") or data.get("leads") or []
    return [c for c in data if isinstance(c, dict)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Grade a local business website and write a one-page report.")
    ap.add_argument("url", nargs="?", help="the website, e.g. joesplumbing.com")
    ap.add_argument("--name", default="", help="the business name for the report")
    ap.add_argument("--city", default="", help="their town (the title check looks for it)")
    ap.add_argument("--out", help="folder for the reports (default data/agency/reports)")
    ap.add_argument("--batch", help="a JSON file of client records (site_url) or a text file with one address per line")
    ap.add_argument("--pdf", action="store_true", help="also save a PDF (uses Edge or Chrome if installed)")
    ap.add_argument("--open", action="store_true", help="open the report when done")
    ap.add_argument("--page-only", action="store_true", help="skip weighing the page's files")
    args = ap.parse_args(argv)
    out = Path(args.out) if args.out else None
    if args.batch:
        rows = read_batch(Path(args.batch))
        summary = []
        for i, c in enumerate(rows):
            site = (c.get("site_url") or "").strip()
            if not site:
                summary.append({"id": c.get("id", ""), "name": c.get("name", ""), "site_url": "", "score": None, "grade": None,
                                "note": "no website: a perfect lead for a free demo"})
                continue
            try:
                if robots_allows(normalize_url(site)) is False:      # a cold lead's site that asks tools to stay away: we do
                    summary.append({"id": c.get("id", ""), "name": c.get("name", ""), "site_url": site, "score": None, "grade": None,
                                    "note": "skipped: its robots.txt asks tools not to visit (call them instead)"})
                    continue
                r = grade_url(site, out, c.get("name", ""), c.get("city", ""), not args.page_only, args.pdf)
            except ValueError as e:
                summary.append({"id": c.get("id", ""), "name": c.get("name", ""), "site_url": site, "score": None, "grade": None, "note": str(e)})
                continue
            summary.append({"id": c.get("id", ""), "name": c.get("name", ""), "site_url": site, "score": r["score"], "grade": r["grade"],
                            "top_fix": r["fixes"][0]["label"] if r["fixes"] else "", "report": r["report"]})
            print(f"{site}: {r['score']}/100 ({r['grade']})", flush=True)
            if i < len(rows) - 1:
                time.sleep(1.0)
        d = reports_dir(out)
        (d / "grades.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"{len(summary)} rows -> {d / 'grades.json'}")
        return 0
    if not args.url:
        ap.print_help()
        return 3
    try:
        r = grade_url(args.url, out, args.name, args.city, not args.page_only, args.pdf)
    except ValueError as e:
        print(f"Not a website address: {e}")
        return 3
    print(f"{r['url']}: {r['score']}/100, grade {r['grade']}. {r['verdict']}")
    for i, f in enumerate(r["fixes"], 1):
        print(f"  {i}. {f['label']}: {f['fix']}")
    print(f"Report: {r['report']}" + (f"\nPDF: {r['pdf']}" if r.get("pdf") else ("\n(no Edge/Chrome found for the PDF: open the report and Print > Save as PDF)" if args.pdf else "")))
    if args.open:
        webbrowser.open(Path(r.get("pdf") or r["report"]).resolve().as_uri())
    return 2 if r.get("down") else 0


if __name__ == "__main__":
    sys.exit(main())
