#!/usr/bin/env python3
"""Website audit for a prospect: the owner's sales weapon (day-web-audit 2026-11-20, Agency app).

    python -X utf8 tools/site_audit.py https://www.example.com              audit one home page -> agency/audit/<slug>.html + .png
    python -X utf8 tools/site_audit.py URL --visitors 1500 --value 120      + a $ estimate (monthly phone visitors, $ a new customer is worth)
    python -X utf8 tools/site_audit.py --index                               rebuild agency/audit/index.html from audits.json
    options: --out DIR (default tools/web_public/agency/audit)  --slug NAME  --no-robots (only for your OWN site)  --name "Shown name"

What it does (polite, free, no key): reads robots.txt and stops when the page is not allowed; opens the ONE home page once (no
crawling) in the pre-installed Chromium as a phone (390 x 844, touch, CPU slowed x4, Lighthouse's mobile line: 150 ms round trip
x 3.75 = 562.5 ms, 1.6 Mbit/s x 0.9 down, the same numbers PageSpeed Insights uses for "mobile"); waits 8 s; measures:
  speed      first paint, largest paint (Google's LCP), total blocking time (long tasks), MB downloaded, requests
  jumps      layout shift (Google's CLS) and what moved
  phone      zoom-able viewport, sideways scroll, tap targets under 44 px, text under 12 px
  basics     page title, description, tap-to-call, map, opening hours, HTTPS, a Google Business Profile link, schema.org data,
             favicon, share image (agency/audit.py's checks + these)
  access     axe-core (vendored, tools/a11y/axe.min.js, WCAG 2 A / AA rules) -> a 0-100 score and the top problems
then writes ONE shareable page: plain words, a grade, "3 things that lose you customers" each with $ framing and the source of
the number, every measurement, a phone screenshot. The report has no script, no tracking, no font or image from anywhere else.
Never contacts the business, never logs in, never submits a form. Demo audits are of big brands only (no small business shamed).
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import io
import json
import math
import os
import re
import sys
import time
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
OUT = os.path.join(ROOT, "tools", "web_public", "agency", "audit")
AXE = os.path.join(ROOT, "tools", "a11y", "axe.min.js")
W, H = 390, 844
LINE = {"offline": False, "latency": 562.5, "downloadThroughput": 1.6e6 * 0.9 / 8, "uploadThroughput": 750e3 * 0.9 / 8}
SETTLE_MS = 8000
UA_PHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 "
            "Safari/604.1 OLYMPUS-site-audit/1 (one-time look at one page)")

# where every number in the report comes from (shown at the bottom of each report)
SOURCES = {
    "bounce": ("Google / SOASTA Research, 2017: as a mobile page's load time goes from 1 s to 3 s the chance a visitor leaves (bounces) "
               "rises 32 %; 1 s to 5 s: 90 %; to 6 s: 106 %; to 10 s: 123 %.",
               "https://www.thinkwithgoogle.com/marketing-strategies/app-and-mobile/page-load-time-statistics/"),
    "53": ("Google DoubleClick, 2016 (\"The Need for Mobile Speed\"): 53 % of mobile site visits are abandoned when a page takes longer "
           "than 3 seconds to load.",
           "https://www.thinkwithgoogle.com/marketing-strategies/app-and-mobile/mobile-page-speed-new-industry-benchmarks/"),
    "deloitte": ("Deloitte for Google, 2020 (\"Milliseconds Make Millions\"): a 0.1 s faster mobile site lifted retail conversions "
                 "8.4 % and travel conversions 10.1 %.",
                 "https://www.thinkwithgoogle.com/_qs/documents/9757/Milliseconds_Make_Millions_report_hQYAbZJ.pdf"),
    "nearby": ("Think with Google, 2016: 76 % of people who search on a phone for something nearby visit a related business "
               "within a day, and 28 % of those searches end in a purchase.",
               "https://www.thinkwithgoogle.com/consumer-insights/consumer-trends/mobile-search-trends-consumers-to-stores/"),
    "vitals": ("Google web.dev, Core Web Vitals: good = largest paint within 2.5 s, layout shift under 0.1, quick response to taps; "
               "Google uses these for search ranking.", "https://web.dev/articles/vitals"),
    "ada": ("UsableNet and Level Access lawsuit tracking, 2025: about 3,100-3,900 federal website accessibility (ADA) lawsuits, over "
            "5,000 counting state courts; about 2 in 3 were against companies under $50M revenue.", "https://www.usablenet.com/"),
    "webaim": ("WebAIM Million, 2024: 95.9 % of the top one million home pages had detectable accessibility (WCAG) failures.",
               "https://webaim.org/projects/million/"),
}
# Google 2017: bounce probability increase vs a 1 s page, by load time (s) -> percent; linear between points
BOUNCE_CURVE = [(1, 0), (3, 32), (5, 90), (6, 106), (10, 123)]

MORE = r"""
(() => {
  window.__sa = { lt: [], cls: 0, shifts: [], fcp: 0, lcp: 0, lcp_el: '' };
  const who = (n) => { try { if (!n || !n.tagName) return '?'; return n.tagName.toLowerCase() + (n.id ? '#' + n.id : '') +
    (typeof n.className === 'string' && n.className.trim() ? '.' + n.className.trim().split(/\s+/)[0] : ''); } catch (e) { return '?'; } };
  const po = (type, fn) => { try { new PerformanceObserver((l) => l.getEntries().forEach(fn)).observe({ type, buffered: true }); } catch (e) {} };
  po('longtask', (e) => window.__sa.lt.push(e.duration));
  po('layout-shift', (e) => { if (!e.hadRecentInput) { window.__sa.cls += e.value; if (e.value >= 0.01) window.__sa.shifts.push([+e.value.toFixed(3), (e.sources || []).slice(0, 2).map((x) => who(x.node)).join(' + ')]); } });
  po('paint', (e) => { if (e.name === 'first-contentful-paint') window.__sa.fcp = e.startTime; });
  po('largest-contentful-paint', (e) => { window.__sa.lcp = e.startTime; const n = e.element;
    window.__sa.lcp_el = n ? ((n.innerText || n.getAttribute('alt') || '').trim().replace(/\s+/g, ' ').slice(0, 60) || (n.tagName || '').toLowerCase()) : ''; });
})();
"""
COLLECT = r"""
(() => {
  const sa = window.__sa || {}, res = performance.getEntriesByType('resource'), nav = performance.getEntriesByType('navigation')[0] || {};
  const bytes = (nav.transferSize || 0) + res.reduce((s, r) => s + (r.transferSize || 0), 0);
  const vis = (e) => { const r = e.getBoundingClientRect(), s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  let small = 0, smallText = 0, smallEx = [];
  for (const e of document.querySelectorAll('a[href], button, input:not([type=hidden]), select, textarea, [role=button]')) {
    if (!vis(e)) continue; const r = e.getBoundingClientRect();
    if (r.width < 44 && r.height < 44) { small++; if (smallEx.length < 3) smallEx.push((e.innerText || e.getAttribute('aria-label') || e.tagName).trim().slice(0, 30)); }
  }
  const walker = document.createTreeWalker(document.body || document.documentElement, NodeFilter.SHOW_TEXT);
  const seen = new Set(); let n;
  while ((n = walker.nextNode())) { const p = n.parentElement; if (!p || seen.has(p) || n.textContent.trim().length < 4) continue; seen.add(p);
    if (vis(p) && parseFloat(getComputedStyle(p).fontSize) < 12) smallText++; }
  const vp = (document.querySelector('meta[name=viewport]') || {}).content || '';
  return { fcp: sa.fcp || 0, lcp: sa.lcp || sa.fcp || 0, lcp_el: sa.lcp_el || '', text: (document.body ? document.body.innerText : '').slice(0, 600), cls: sa.cls || 0, shifts: (sa.shifts || []).sort((a, b) => b[0] - a[0]).slice(0, 3),
    tbt: (sa.lt || []).reduce((s, d) => s + Math.max(0, d - 50), 0), lt_max: Math.max(0, ...(sa.lt || [0])), bytes, requests: res.length + 1,
    load: nav.loadEventEnd || 0, sideways: document.documentElement.scrollWidth > innerWidth + 2, small_taps: small, small_tap_examples: smallEx,
    small_text: smallText, viewport: vp, zoom_blocked: /user-scalable\s*=\s*(no|0)|maximum-scale\s*=\s*1(\.0)?\b/i.test(vp),
    html: document.documentElement.outerHTML.slice(0, 2500000), final_url: location.href, title: document.title };
})()
"""


# ------------------------------------------------------------------------------------------------ pure (unit-tested)
BLOCK_RX = re.compile(r"access denied|just a moment|attention required|are you a robot|verify you are human|captcha|request blocked|"
                      r"pardon our interruption|bot protection|unusual traffic", re.I)


def blocked(raw: dict) -> str:
    """'' or why the page we saw is a bot wall, not the business's site (then no report is written: it would be about the wall)"""
    if int(raw.get("status") or 0) in (401, 403, 429, 503):
        return f"the site answered {raw.get('status')} (it blocks automatic checks)"
    t = f"{raw.get('title') or ''} {(raw.get('text') or '')[:400]}"
    m = BLOCK_RX.search(t)
    return f"the site showed a bot check ('{m.group(0)}')" if m else ""


def slug_of(url: str) -> str:
    h = (urllib.parse.urlsplit(url if "://" in url else "https://" + url).hostname or "site").lower()
    h = re.sub(r"^www\.", "", h)
    return re.sub(r"[^a-z0-9]+", "-", h).strip("-")[:60] or "site"


def bounce_up(seconds: float) -> int:
    """Google 2017: % more likely to bounce than on a 1 s page (linear between the published points, flat after 10 s)"""
    s = max(1.0, float(seconds or 0))
    for (x0, y0), (x1, y1) in zip(BOUNCE_CURVE, BOUNCE_CURVE[1:]):
        if s <= x1:
            return int(round(y0 + (y1 - y0) * (s - x0) / (x1 - x0)))
    return BOUNCE_CURVE[-1][1]


def basics(html_text: str, final_url: str) -> dict:
    """what a local business site should have, from the rendered page (True = present)"""
    t = html_text or ""
    low = t.lower()
    ld = re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', t, re.S | re.I)
    types = set()
    for blob in ld:
        types |= set(re.findall(r'"@type"\s*:\s*"([A-Za-z]+)"', blob))
        for arr in re.findall(r'"@type"\s*:\s*\[([^\]]*)\]', blob):
            types |= set(re.findall(r'"([A-Za-z]+)"', arr))
    m = re.search(r'<meta[^>]+name=["\']description["\'][^>]*content=["\']([^"\']{10,})', t, re.I) or \
        re.search(r'<meta[^>]+content=["\']([^"\']{10,})["\'][^>]*name=["\']description["\']', t, re.I)
    title = re.search(r"<title[^>]*>\s*([^<]{3,})", t, re.I)
    days = len(re.findall(r"\b(mon(day)?|tue(sday)?|wed(nesday)?|thu(rsday)?|fri(day)?|sat(urday)?|sun(day)?)\b", low))
    return {
        "https": final_url.lower().startswith("https://"),
        "title": bool(title),
        "description": bool(m),
        "tap_to_call": 'href="tel:' in low or "href='tel:" in low,
        "map": bool(re.search(r"google\.[a-z.]+/maps|maps\.google\.|maps\.app\.goo\.gl|goo\.gl/maps|maps\.apple\.com|openstreetmap\.org|"
                              r"api\.mapbox\.com|bing\.com/maps|<iframe[^>]+map", low)),
        "hours": "openinghours" in low or bool(re.search(r"\bhours\b|\bopen (today|now|daily)\b", low)) and days >= 2,
        "google_business": bool(re.search(r"g\.page/|business\.google\.com|maps\.google\.[a-z.]+/?\?cid=|google\.[a-z.]+/maps/place/|"
                                          r"maps\.app\.goo\.gl|search\.google\.com/local/writereview", low)),
        "schema": bool(types),
        "schema_types": sorted(types)[:8],
        "local_schema": bool(types & {"LocalBusiness", "Restaurant", "Store", "Organization", "Corporation", "FoodEstablishment",
                                      "ProfessionalService", "HomeAndConstructionBusiness", "MedicalBusiness", "AutoRepair", "Dentist"}),
        "favicon": bool(re.search(r'<link[^>]+rel=["\'][^"\']*icon', t, re.I)),
        "share_image": "og:image" in low,
    }


HAVE = {"https": "Padlock (HTTPS)", "title": "Page title", "description": "Search description", "tap_to_call": "Tap-to-call phone number",
        "map": "Map or directions link", "hours": "Opening hours", "google_business": "Link to the Google Business Profile",
        "local_schema": "Business data for Google (schema.org)", "favicon": "Site icon", "share_image": "Share picture"}
BASIC_WORDS = {   # key -> (what is missing, in plain words, why it matters)
    "https": ("No padlock (HTTPS)", "Chrome marks the site 'Not secure'; people leave and Google ranks it lower."),
    "title": ("No page title", "Google shows a blank or random headline for the business."),
    "description": ("No search description", "Google writes its own snippet; you lose the chance to say why people should click."),
    "tap_to_call": ("Phone number is not tap-to-call", "On a phone people have to copy the number by hand; many just don't call."),
    "map": ("No map or directions link", "People who want to visit can't see where you are in one tap."),
    "hours": ("No opening hours on the page", "The #1 question before a visit; without it people pick a place that shows them."),
    "google_business": ("No link to the Google Business Profile", "Reviews and 'Directions' live there; the site does not send people to them."),
    "local_schema": ("No business data for Google (schema.org)", "Google can't read the name, address, hours and phone for rich results."),
    "favicon": ("No site icon", "Tabs and bookmarks show a blank icon: looks unfinished."),
    "share_image": ("No share picture", "A link shared in a text or on Facebook shows no picture."),
}


def a11y_score(violations: list) -> int:
    """0-100 from axe violations: each rule costs by impact (critical 10, serious 6, moderate 3, minor 1) + 1 per extra 10 elements"""
    cost = {"critical": 10, "serious": 6, "moderate": 3, "minor": 1}
    pts = 0.0
    for v in violations or []:
        pts += cost.get(v.get("impact") or "minor", 1) + min(5, len(v.get("nodes") or []) // 10)
    return max(0, int(round(100 - pts)))


def grade(m: dict) -> str:
    """A-F from the four that matter most to a phone visitor: speed (LCP), jumps (CLS), phone basics, accessibility"""
    pts = 0
    lcp = m.get("lcp_s") or 99
    pts += 40 if lcp <= 2.5 else 28 if lcp <= 4 else 15 if lcp <= 6 else 5
    cls = m.get("cls") or 0
    pts += 15 if cls <= 0.1 else 8 if cls <= 0.25 else 2
    b = m.get("basics") or {}
    have = sum(1 for k in ("https", "title", "description", "tap_to_call", "map", "hours", "local_schema") if b.get(k))
    pts += round(25 * have / 7)
    pts += round(20 * (m.get("a11y") or 0) / 100)
    return "A" if pts >= 85 else "B" if pts >= 70 else "C" if pts >= 55 else "D" if pts >= 40 else "F"


def losses(m: dict, visitors: int | None = None, value: float | None = None) -> list:
    """the 3 things that lose this business the most customers, ranked, each: {title, why, money, source}"""
    out = []
    lcp = m.get("lcp_s") or 0
    if lcp > 2.5:
        up = bounce_up(lcp)
        money = (f"Compared with a 1-second page, a phone visitor is about {up} % more likely to leave before doing anything "
                 f"(Google). " + (f"Over 3 seconds, Google measured that about half of phone visits are abandoned.") if lcp > 3 else
                 f"Compared with a 1-second page, a phone visitor is about {up} % more likely to leave (Google).")
        out.append({"w": 100 + up, "title": f"The page takes {lcp:.1f} s to show its main content on a phone",
                    "why": "Google's bar is 2.5 s. Every extra second, more people give up and pick the next result.",
                    "money": money, "src": ["bounce", "53", "vitals"]})
    b = m.get("basics") or {}
    if not b.get("tap_to_call"):
        out.append({"w": 90, "title": "No tap-to-call button",
                    "why": "Most local customers decide on a phone; a number you can't tap is a call that never happens.",
                    "money": "76 % of people who search nearby on a phone visit a business within a day (Google): every step in their "
                             "way sends them to a competitor who is one tap away.", "src": ["nearby"]})
    missing_local = [k for k in ("hours", "map", "google_business", "local_schema") if not b.get(k)]
    if missing_local:
        names = ", ".join(HAVE[k][0].lower() + HAVE[k][1:] for k in missing_local[:3])
        out.append({"w": 60 + 8 * len(missing_local), "title": f"Missing the basics people look for before a visit: {names}",
                    "why": "Hours, directions and reviews are what a nearby searcher checks; when the site hides them, Google and the "
                           "customer go elsewhere.", "money": "28 % of nearby phone searches end in a purchase (Google): the shop that shows "
                           "hours and directions gets it.", "src": ["nearby"]})
    cls = m.get("cls") or 0
    if cls > 0.1:
        out.append({"w": 55 + int(min(40, cls * 100)), "title": f"The page jumps while it loads (layout shift {cls:.2f})",
                    "why": "Buttons move as pictures and banners arrive, so people tap the wrong thing; Google's bar is under 0.1.",
                    "money": "Google uses this in its ranking (Core Web Vitals): a jumpy page sits lower in search.", "src": ["vitals"]})
    if (m.get("a11y") if m.get("a11y") is not None else 100) < 90:
        out.append({"w": 70 + (90 - m["a11y"]), "title": f"Hard to use for some customers, and a legal risk (accessibility {m['a11y']}/100)",
                    "why": "Low contrast, unlabeled buttons or tiny tap targets: older customers and screen-reader users struggle, and "
                           "these are the problems website accessibility lawsuits cite.",
                    "money": "Over 5,000 website accessibility (ADA) lawsuits were filed in 2025, about 2 in 3 against companies under "
                             "$50M revenue; about 96 % of top home pages fail basic checks.", "src": ["ada", "webaim"]})
    if m.get("zoom_blocked") or m.get("sideways") or (m.get("small_taps") or 0) >= 10:
        bits = [x for x, on in (("pinch-zoom is blocked", m.get("zoom_blocked")), ("the page scrolls sideways", m.get("sideways")),
                                (f"{m.get('small_taps')} buttons / links are smaller than a fingertip", (m.get("small_taps") or 0) >= 10)) if on]
        out.append({"w": 45, "title": "Awkward on a phone: " + ", ".join(bits), "why": "People can't read or tap comfortably and leave.",
                    "money": "Most local searches happen on a phone (Google).", "src": ["nearby"]})
    if not b.get("https"):
        out.append({"w": 95, "title": "No padlock: Chrome shows 'Not secure'", "why": "People don't fill in a form or pay on a 'Not secure' page.",
                    "money": "Google ranks HTTPS pages first.", "src": ["vitals"]})
    out.sort(key=lambda x: -x["w"])
    top = out[:3]
    if visitors and value and top and lcp > 2.5:
        lost = visitors * min(0.5, bounce_up(lcp) / 100 * 0.5) * 0.03 * value
        top[0]["estimate"] = (f"With {visitors:,} phone visitors a month, 3 % becoming customers worth ${value:,.0f}: a slow first screen "
                              f"costs roughly ${lost:,.0f} a month (estimate: Google's bounce curve, half of it applied).")
    return top


def page_html(m: dict, name: str, png: str, when: str) -> str:
    """the shareable one-page report: no script, no external file, no tracking; the screenshot is the only other file"""
    e = html.escape
    g = m.get("grade", "?")
    col = {"A": "#1f8a4c", "B": "#5b8a1f", "C": "#b07a12", "D": "#c0561b", "F": "#b3261e"}.get(g, "#555")
    b = m.get("basics") or {}
    used = []
    rows = []
    for i, x in enumerate(m.get("losses") or [], 1):
        for s in x["src"]:
            if s not in used:
                used.append(s)
        refs = "<sup>" + ",".join(f'<a href="#s{used.index(s) + 1}">{used.index(s) + 1}</a>' for s in x["src"]) + "</sup>"
        rows.append(f'<li><h3>{i}. {e(x["title"])}</h3><p>{e(x["why"])}</p><p class="m">{e(x["money"])}{refs}</p>'
                    + (f'<p class="est">{e(x["estimate"])}</p>' if x.get("estimate") else "") + "</li>")
    for s in ("ada", "vitals"):
        if s not in used:
            used.append(s)

    def ok(v, good, label_good, label_bad):
        return f'<span class="{"ok" if v else "bad"}">{e(label_good if v else label_bad)}</span>'
    lcp, cls, tbt = m.get("lcp_s") or 0, m.get("cls") or 0, m.get("tbt_ms") or 0
    lcp_note = f'good is 2.5 s or less. The biggest thing on screen was: "{m["lcp_el"]}"' if m.get("lcp_el") else "good is 2.5 s or less"
    speed = [("Main content shows after", f"{lcp:.1f} s", lcp <= 2.5, lcp_note),
             ("First thing on screen after", f"{(m.get('fcp_s') or 0):.1f} s", (m.get("fcp_s") or 0) <= 1.8, "good is 1.8 s or less"),
             ("Page jumps while loading", f"{cls:.2f}", cls <= 0.1, "good is under 0.1"),
             ("Frozen while loading (blocking time)", f"{tbt / 1000:.1f} s", tbt <= 600, "good is under 0.6 s on this phone"),
             ("Downloaded on first visit", f"{(m.get('mb') or 0):.1f} MB in {m.get('requests', 0)} files", (m.get("mb") or 0) <= 2.5,
              "lean is under 2.5 MB")]
    sp = "".join(f'<tr><td>{e(a)}</td><td class="{"ok" if g_ else "bad"}">{e(v)}</td><td class="n">{e(n)}</td></tr>' for a, v, g_, n in speed)
    phone = [("Pinch-zoom allowed", not m.get("zoom_blocked")), ("No sideways scrolling", not m.get("sideways")),
             (f"Tap targets big enough ({m.get('small_taps', 0)} too small)", (m.get("small_taps") or 0) < 10),
             (f"Text big enough ({m.get('small_text', 0)} bits under 12 px)", (m.get("small_text") or 0) < 10)]
    ph = "".join(f'<li class="{"ok" if v else "bad"}">{"✓" if v else "✗"} {e(t)}</li>' for t, v in phone)
    bl = "".join(f'<li class="{"ok" if b.get(k) else "bad"}">{"✓" if b.get(k) else "✗"} {e(HAVE[k])}'
                 + ("" if b.get(k) else f'<small>{e(BASIC_WORDS[k][1])}</small>') + "</li>" for k in BASIC_WORDS)
    ax = "".join(f'<li><b>{e(v["impact"] or "minor")}</b> {e(v["help"])} <small>({v["n"]} on the page)</small></li>' for v in (m.get("a11y_top") or []))
    src = "".join(f'<li id="s{i}">{e(SOURCES[s][0])} <a href="{e(SOURCES[s][1])}" rel="noopener noreferrer">{e(SOURCES[s][1])}</a></li>'
                  for i, s in enumerate(used, 1))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow"><meta name="referrer" content="no-referrer">
<title>Website check: {e(name)}</title>
<style>
:root{{--bg:#f7f5f0;--card:#fff;--ink:#1d1b18;--mut:#5d5850;--ok:#1f7a45;--bad:#b3261e;--line:#e6e1d6}}
@media (prefers-color-scheme:dark){{:root{{--bg:#14130f;--card:#1e1c18;--ink:#f2efe8;--mut:#b5ae9f;--ok:#5fc489;--bad:#ff8a7d;--line:#36322b}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 -apple-system,system-ui,Segoe UI,Roboto,sans-serif}}
main{{max-width:760px;margin:0 auto;padding:20px 16px 48px}}h1{{font-size:26px;line-height:1.2;margin:4px 0}}h2{{font-size:19px;margin:28px 0 8px}}
h3{{font-size:17px;margin:0 0 4px}}.sub{{color:var(--mut);margin:0}}.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;margin:12px 0}}
.top{{display:flex;gap:16px;align-items:center}}.grade{{flex:none;width:76px;height:76px;border-radius:18px;background:{col};color:#fff;font:800 44px/76px system-ui;text-align:center}}
ol.loss{{list-style:none;padding:0;margin:0}}ol.loss li{{border-top:1px solid var(--line);padding:12px 0}}ol.loss li:first-child{{border-top:0}}
.m{{font-weight:600}}.est{{background:color-mix(in srgb,var(--bad) 10%,transparent);border-radius:8px;padding:8px}}
table{{width:100%;border-collapse:collapse}}td{{padding:8px 4px;border-top:1px solid var(--line);vertical-align:top}}td.n{{color:var(--mut);font-size:14px}}
.ok{{color:var(--ok)}}.bad{{color:var(--bad)}}ul.chk{{list-style:none;padding:0;margin:0}}ul.chk li{{padding:6px 0;border-top:1px solid var(--line)}}
ul.chk small{{display:block;color:var(--mut)}}.shot{{display:block;width:100%;max-width:300px;border-radius:24px;border:1px solid var(--line);margin:8px auto}}
sup a{{color:var(--mut);text-decoration:none;padding:0 1px}}.src{{font-size:13px;color:var(--mut)}}.src a{{color:inherit;word-break:break-all}}footer{{font-size:13px;color:var(--mut);margin-top:24px}}
</style></head>
<body><main>
<p class="sub">Website check · {e(when)}</p>
<div class="top"><div class="grade" aria-label="Grade {e(g)}">{e(g)}</div><div><h1>{e(name)}</h1>
<p class="sub">{e(m.get("final_url") or "")}</p><p class="sub">Checked as a typical phone on a slow 4G line (the way Google tests mobile pages).</p></div></div>

<div class="card"><h2 style="margin-top:0">3 things that lose you customers</h2><ol class="loss">{"".join(rows) or "<li><h3>Nothing big: this page does the basics well.</h3></li>"}</ol></div>

<div class="card"><h2 style="margin-top:0">Accessibility: {m.get("a11y", 0)}/100 <span class="{"ok" if (m.get("a11y") or 0) >= 90 else "bad"}">{"good" if (m.get("a11y") or 0) >= 90 else "needs work"}</span></h2>
<p>Can everyone use this page, including people with poor eyesight or a screen reader? Over 5,000 website accessibility (ADA)
lawsuits were filed in 2025, about 2 in 3 against companies under $50M revenue.<sup><a href="#s{used.index("ada") + 1}">{used.index("ada") + 1}</a></sup>
{m.get("a11y_n", 0)} kinds of problem found by automatic WCAG 2 A/AA checks (axe-core).</p><ul class="chk">{ax or "<li class='ok'>No automatic accessibility problems found.</li>"}</ul></div>

<h2>Speed on a phone</h2><div class="card"><table>{sp}</table></div>
<h2>On a phone</h2><div class="card"><ul class="chk">{ph}</ul></div>
<h2>The basics a customer looks for</h2><div class="card"><ul class="chk">{bl}</ul></div>
<h2>What a phone visitor sees first</h2><img class="shot" src="{e(png)}" alt="The page on a phone screen, as it looked during the check" width="390" height="844">

<h2>Where the numbers come from</h2><ol class="src">{src}</ol>
<footer>One look at one page, as a phone. No login, no form sent, nothing stored about visitors. Numbers change from visit to visit;
the trend matters more than the decimal. This page has no tracking.</footer>
</main></body></html>
"""


def index_html(rows: list) -> str:
    e = html.escape
    items = "".join(f'<li><a href="{e(r["slug"])}.html"><b>{e(r["name"])}</b> <span class="g g{e(r["grade"])}">{e(r["grade"])}</span></a>'
                    f'<small>{e(r["when"])} · main content {r["lcp_s"]:.1f} s · jumps {r["cls"]:.2f} · access {r["a11y"]}/100</small></li>'
                    for r in sorted(rows, key=lambda r: r["when"], reverse=True))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow"><title>Website checks</title>
<style>:root{{--bg:#f7f5f0;--card:#fff;--ink:#1d1b18;--mut:#5d5850;--line:#e6e1d6}}
@media (prefers-color-scheme:dark){{:root{{--bg:#14130f;--card:#1e1c18;--ink:#f2efe8;--mut:#b5ae9f;--line:#36322b}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 -apple-system,system-ui,sans-serif}}main{{max-width:760px;margin:0 auto;padding:20px 16px 48px}}
a{{color:inherit}}ul{{list-style:none;padding:0}}li{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px;margin:10px 0}}
li a{{text-decoration:none;display:flex;justify-content:space-between;align-items:center;min-height:44px}}small{{color:var(--mut)}}
.g{{font-weight:800;border-radius:8px;padding:2px 10px;color:#fff;background:#555}}.gA{{background:#1f8a4c}}.gB{{background:#5b8a1f}}.gC{{background:#b07a12}}
.gD{{background:#c0561b}}.gF{{background:#b3261e}}code{{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:2px 6px;word-break:break-all}}
.back{{display:inline-block;min-height:44px;line-height:44px}}</style></head>
<body><main><a class="back" href="../">‹ Agency</a>
<h1>Website checks</h1><p>A one-page report you can send a business owner: how their home page does on a phone, the 3 things that lose them
customers (with the source of every number), and what is missing. The two samples are big brands, so no small business is named here.</p>
<ul>{items or "<li>No checks yet.</li>"}</ul>
<h2>Run one (on the PC or here)</h2>
<p><code>python -X utf8 tools/site_audit.py https://their-site.com</code></p>
<p>Add <code>--visitors 1500 --value 120</code> for a $ estimate (their phone visitors a month, what a new customer is worth).
The report lands in <code>tools/web_public/agency/audit/&lt;name&gt;.html</code> with its screenshot; send the link or the file.
It reads robots.txt, opens the one home page once, and never contacts anyone.</p>
</main></body></html>
"""


# ------------------------------------------------------------------------------------------------ the browser run
def launch(pw):
    import glob
    args = ["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
    kw = {}
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if proxy:
        kw["proxy"] = {"server": proxy}
    exe = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))
    if exe:
        kw["executable_path"] = exe[-1]
    return pw.chromium.launch(args=args, **kw)


def measure(url: str, png_path: str, say=print) -> dict:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        br = launch(pw)
        ctx = br.new_context(viewport={"width": W, "height": H}, device_scale_factor=2, is_mobile=True, has_touch=True,
                             user_agent=UA_PHONE, service_workers="block", ignore_https_errors=False, locale="en-US")
        ctx.add_init_script(MORE)
        pg = ctx.new_page()
        try:
            cdp = ctx.new_cdp_session(pg)
            cdp.send("Network.enable")
            cdp.send("Network.setCacheDisabled", {"cacheDisabled": True})
            cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
            cdp.send("Network.emulateNetworkConditions", LINE)
            wire = {"bytes": 0, "n": 0}

            def done(ev):
                wire["bytes"] += int(ev.get("encodedDataLength") or 0)
                wire["n"] += 1
            cdp.on("Network.loadingFinished", done)            # every file over the wire, other sites' too (the page itself sees 0 for those)
            t0 = time.time()
            resp = pg.goto(url, wait_until="load", timeout=120000)
            pg.wait_for_timeout(SETTLE_MS)
            raw = pg.evaluate(COLLECT)
            raw["status"] = resp.status if resp else 0
            if wire["bytes"]:
                raw["bytes"], raw["requests"] = wire["bytes"], max(raw.get("requests") or 0, wire["n"])
            raw["wall_s"] = round(time.time() - t0, 1)
            cdp.send("Emulation.setCPUThrottlingRate", {"rate": 1})
            cdp.send("Network.emulateNetworkConditions", {"offline": False, "latency": 0, "downloadThroughput": -1, "uploadThroughput": -1})
            pg.evaluate("window.scrollTo(0, 0)")
            pg.wait_for_timeout(400)
            pg.screenshot(path=png_path)
            raw["axe"] = run_axe(pg)
        finally:
            ctx.close()
            br.close()
    return raw


def run_axe(pg) -> list:
    try:
        pg.add_script_tag(content=open(AXE, encoding="utf-8").read())
        r = pg.evaluate("axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa']}, resultTypes: ['violations']})"
                        ".then((x) => x.violations.map((v) => ({id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.map(() => 1)})))")
        return r or []
    except Exception as e:  # noqa: BLE001  (a page whose CSP blocks the injected script: no score, said so)
        return [{"id": "axe-blocked", "impact": None, "help": f"could not run the accessibility check ({e.__class__.__name__})", "nodes": []}]


def shrink_png(path: str):
    """the screenshot at 2x, 256 colours: ~5x smaller, still sharp text"""
    try:
        from PIL import Image
        im = Image.open(path).convert("RGB")
        im.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(path, optimize=True)
    except Exception:  # noqa: BLE001
        pass


def build(raw: dict, visitors=None, value=None) -> dict:
    ax = [v for v in raw.get("axe") or [] if v.get("id") != "axe-blocked"]
    m = {"final_url": raw.get("final_url"), "status": raw.get("status"), "title": raw.get("title"),
         "fcp_s": round((raw.get("fcp") or 0) / 1000, 2), "lcp_s": round((raw.get("lcp") or 0) / 1000, 2), "lcp_el": raw.get("lcp_el") or "", "cls": round(raw.get("cls") or 0, 3),
         "shifts": raw.get("shifts") or [], "tbt_ms": int(raw.get("tbt") or 0), "lt_max": int(raw.get("lt_max") or 0),
         "mb": round((raw.get("bytes") or 0) / 1e6, 2), "requests": raw.get("requests") or 0, "sideways": bool(raw.get("sideways")),
         "small_taps": raw.get("small_taps") or 0, "small_tap_examples": raw.get("small_tap_examples") or [], "small_text": raw.get("small_text") or 0,
         "zoom_blocked": bool(raw.get("zoom_blocked")), "basics": basics(raw.get("html") or "", raw.get("final_url") or ""),
         "a11y": a11y_score(ax) if raw.get("axe") and not any(v.get("id") == "axe-blocked" for v in raw["axe"]) else (100 if raw.get("axe") == [] else 0),
         "a11y_n": len(ax), "a11y_top": sorted([{"impact": v.get("impact"), "help": v.get("help"), "n": len(v.get("nodes") or [])} for v in ax],
                                               key=lambda v: ({"critical": 0, "serious": 1, "moderate": 2}.get(v["impact"], 3), -v["n"]))[:6]}
    m["grade"] = grade(m)
    m["losses"] = losses(m, visitors, value)
    return m


def write_index(out: str):
    try:
        rows = json.load(open(os.path.join(out, "audits.json"), encoding="utf-8"))
    except (OSError, ValueError):
        rows = []
    with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(index_html(rows))
    with open(os.path.join(out, "summary.json"), "w", encoding="utf-8") as fh:      # the Agency HQ tile (HUB team's shape)
        json.dump({"n": len(rows), "label": f"{len(rows)} website check{'s' if len(rows) != 1 else ''}",
                   "next": "Check a prospect's site: python tools/site_audit.py <their URL>", "t": int(time.time())}, fh)


def audit(url: str, out: str = OUT, slug: str | None = None, name: str | None = None, robots: bool = True, visitors=None, value=None,
          say=print) -> dict:
    if "://" not in url:
        url = "https://" + url
    if robots:
        try:
            from agency.audit import robots_ok
            if not robots_ok(url):
                raise SystemExit(f"robots.txt of {url} does not allow a tool to open this page: not checked (polite).")
        except SystemExit:
            raise
        except Exception:  # noqa: BLE001  (robots.txt unreachable = allowed, as the standard says)
            pass
    slug = slug or slug_of(url)
    os.makedirs(out, exist_ok=True)
    png = os.path.join(out, slug + ".png")
    say(f"checking {url} as a phone on a slow 4G line (one page, ~30 s) ...")
    raw = measure(url, png, say)
    why = blocked(raw)
    if why:
        try:
            os.remove(png)
        except OSError:
            pass
        raise SystemExit(f"not checked: {why}. Open the site on your own phone instead, or run this from the PC's normal internet line.")
    shrink_png(png)
    m = build(raw, visitors, value)
    when = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    name = name or (raw.get("title") or slug).split("|")[0].split(" - ")[0].strip()[:60] or slug
    with open(os.path.join(out, slug + ".html"), "w", encoding="utf-8") as fh:
        fh.write(page_html(m, name, slug + ".png", when))
    try:
        rows = json.load(open(os.path.join(out, "audits.json"), encoding="utf-8"))
    except (OSError, ValueError):
        rows = []
    rows = [r for r in rows if r.get("slug") != slug] + [{"slug": slug, "name": name, "url": m["final_url"], "when": when, "grade": m["grade"],
                                                           "lcp_s": m["lcp_s"], "cls": m["cls"], "a11y": m["a11y"]}]
    with open(os.path.join(out, "audits.json"), "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=1)
    write_index(out)
    say(f"grade {m['grade']}: main content {m['lcp_s']:.1f} s, jumps {m['cls']:.2f}, access {m['a11y']}/100 -> {os.path.join(out, slug + '.html')}")
    for i, x in enumerate(m["losses"], 1):
        say(f"  {i}. {x['title']}")
    return m


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("url", nargs="?")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--slug")
    ap.add_argument("--name")
    ap.add_argument("--visitors", type=int)
    ap.add_argument("--value", type=float)
    ap.add_argument("--no-robots", action="store_true")
    ap.add_argument("--index", action="store_true")
    a = ap.parse_args(argv)
    if a.index:
        write_index(a.out)
        return 0
    if not a.url:
        ap.print_help()
        return 2
    audit(a.url, a.out, a.slug, a.name, not a.no_robots, a.visitors, a.value)
    return 0


if __name__ == "__main__":
    sys.exit(main())
