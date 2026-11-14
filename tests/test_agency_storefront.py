"""Agency storefront (agency/storefront/, team B3 2026-11-14): the agency's own website + the free Website Grader.
  a. static (no browser): config.json (the shared keys agency_name / city / phone / email / brand_color, the three plans),
     the build (every page, valid HTML, one h1, labels, ids, links that resolve, no inline script, no style= for the CSP,
     no external hotlink, Netlify Forms attributes + honeypot, page weight budgets, WCAG AA colour pairs for the three presets
     and for any brand colour, placeholders listed, the shared agency/config.json wins, texts_ok, legal template note,
     _headers CSP, the committed zip matches the sources (build.py --check), zip deterministic, index.html at the zip root)
  b. grade.py offline: the fixtures (healthy A, dated F, noindex first fix, hostile text escaped), the report (one page,
     no script, the agency's name), the polite visit against a local server (redirects, HEAD weights, a heavy picture,
     404 / dead port = an honest "did not open" report), file names, batch mode on the shared client shape,
     reports kept out of git, the demo sites grade A and the made-up "before" pages grade F
  c. Chromium under the shared lock (AS_NO_BROWSER=1 skips): every page at 390 x 844 and 1440 x 900 (no errors, no 404s,
     no sideways scroll, pictures load), the phone menu, the dock, tap targets, the grader end to end (score, fixes, the
     Netlify POST carries the answers), the contact form with ?plan=, presets, the demo sites' open-now badge and demo forms,
     reduced motion, the PDF report is one page
    python -X utf8 -m tests.test_agency_storefront
    flock -w 2400 /tmp/olympus_browser.lock python -X utf8 -m tests.test_agency_storefront     (part c needs the browser lock)
"""
from __future__ import annotations

import datetime as dt
import functools
import http.server
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import urllib.parse
import zipfile
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SF = ROOT / "agency" / "storefront"
sys.path.insert(0, str(SF))
sys.path.insert(0, str(ROOT))
import build  # noqa: E402
import grade  # noqa: E402

RES: list = []
FIX = SF / "fixtures" / "grade"
PAGES = build.PAGES
DEMOS = [f"examples/{t}/index.html" for t in build.TRADES]


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


# ------------------------------------------------------------------------------------------------ helpers
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
BLOCK = {"div", "ul", "ol", "table", "section", "form", "h1", "h2", "h3", "h4", "h5", "h6", "figure", "header", "footer", "nav",
         "p", "main", "aside", "article", "blockquote", "details", "fieldset", "dl", "pre", "hr"}


class Doc(HTMLParser):
    """a strict reading of one page: every non-void tag closed in order, nothing block-level inside a <p>"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.errors, self.tags, self.doctype = [], [], [], ""
        self.ids = Counter()
        self.text = []
        self.inline_scripts = []
        self._script = None
        self._label_depth = 0

    def handle_decl(self, decl):
        self.doctype = decl

    def _start(self, tag, attrs, closing):
        a = {k: (v if v is not None else "") for k, v in attrs}
        line = self.getpos()[0]
        a["_in_label"] = self._label_depth > 0
        self.tags.append((tag, a, line))
        if "id" in a:
            self.ids[a["id"]] += 1
        if tag in BLOCK and any(t == "p" for t, _ in self.stack):
            self.errors.append(f"line {line}: <{tag}> inside an open <p>")
        if tag == "script" and not a.get("src"):
            self._script = [a.get("type", "")]
        if tag == "label":
            self._label_depth += 1
        if tag not in VOID and not closing:
            self.stack.append((tag, line))

    def handle_starttag(self, tag, attrs):
        self._start(tag, attrs, False)

    def handle_startendtag(self, tag, attrs):
        self._start(tag, attrs, True)

    def handle_endtag(self, tag):
        line = self.getpos()[0]
        if tag in VOID:
            self.errors.append(f"line {line}: </{tag}> for a void element")
            return
        if tag == "label":
            self._label_depth = max(0, self._label_depth - 1)
        if tag == "script" and self._script is not None:
            self.inline_scripts.append(self._script)
            self._script = None
        if self.stack and self.stack[-1][0] == tag:
            self.stack.pop()
            return
        names = [t for t, _ in self.stack]
        if tag in names:
            i = len(names) - 1 - names[::-1].index(tag)
            self.errors.append(f"line {line}: </{tag}> closes <{self.stack[-1][0]}> (opened line {self.stack[-1][1]}) early")
            del self.stack[i:]
        else:
            self.errors.append(f"line {line}: </{tag}> with nothing to close")

    def handle_data(self, data):
        self.text.append(data)
        if self._script is not None:
            self._script.append(data)

    def find(self, tag=None, **want):
        out = []
        for t, a, line in self.tags:
            if tag and t != tag:
                continue
            if all((a.get(k) == v) if v is not True else (k in a) for k, v in want.items()):
                out.append(a)
        return out


def parse(text: str) -> Doc:
    d = Doc()
    d.feed(text)
    d.close()
    if d.stack:
        d.errors.append("never closed: " + ", ".join(f"<{t}> line {ln}" for t, ln in d.stack[-5:]))
    return d


def build_to(tmp: Path, **kw) -> dict:
    return build.build(tmp, **kw)


class Rec(http.server.SimpleHTTPRequestHandler):
    """serves a folder; a form POST is recorded and lands on /thanks.html, like Netlify; extra = headers sent with every answer"""
    posts: list = []
    extra: dict = {}

    def end_headers(self):
        for k, v in Rec.extra.items():
            self.send_header(k, v)
        super().end_headers()

    def do_POST(self):  # noqa: N802
        n = int(self.headers.get("Content-Length") or 0)
        Rec.posts.append(urllib.parse.parse_qs(self.rfile.read(n).decode("utf-8", "replace")))
        self.send_response(303)
        self.send_header("Location", "/thanks.html")
        self.end_headers()

    def log_message(self, *a):
        pass


def serve(folder: Path, handler=Rec):
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(handler, directory=str(folder)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


# ------------------------------------------------------------------------------------------------ a. static
def part_a(tmp: Path):
    raw = json.loads((SF / "config.json").read_text(encoding="utf-8"))
    check("a. config.json: the shared keys sit at the top level with exactly these names (agency_name, city, phone, email, brand_color)",
          all(k in raw for k in build.SHARED_KEYS) and list(raw)[1:6] == list(build.SHARED_KEYS), list(raw)[:7])
    check("a. ... and they are placeholders, never real data (YOUR AGENCY, YOUR CITY, a 555 number, a .example email, a preset)",
          raw["agency_name"] == "YOUR AGENCY" and raw["city"] == "YOUR CITY" and build.digits(raw["phone"]).startswith("555")
          and raw["email"].endswith(".example") and raw["brand_color"] in build.PRESETS, {k: raw[k] for k in build.SHARED_KEYS})
    pk = raw["packages"]
    check("a. three plans with the placeholder prices (Starter $499 + $49, Growth $999 + $79, Pro $1,999 + $129), one popular",
          [(p["name"], p["setup_usd"], p["monthly_usd"]) for p in pk] == [("Starter", 499, 49), ("Growth", 999, 79), ("Pro", 1999, 129)]
          and sum(1 for p in pk if p.get("popular")) == 1, [(p["name"], p["setup_usd"], p["monthly_usd"]) for p in pk])
    names = {a["name"] for a in raw["addons"]}
    check("a. the upsells are add-ons (review booster, website chat, Google profile help), each saying which plans include it",
          {"Review booster", "Website chat", "Google profile tune-up"} <= names and all("included_in" in a for a in raw["addons"]), names)
    quiz = json.loads((SF / "src" / "quiz.json").read_text(encoding="utf-8"))["questions"]
    check("a. the self-check has 10 questions whose weights add up to 100", len(quiz) == 10 and sum(q["w"] for q in quiz) == 100,
          (len(quiz), sum(q["w"] for q in quiz)))
    ex = json.loads((SF / "examples" / "examples.json").read_text(encoding="utf-8"))
    shape = ["id", "name", "trade", "city", "phone", "email", "site_url", "demo_url", "status", "package", "setup_usd", "monthly_usd", "notes"]
    check("a. the three example businesses use the shared client record shape, all fictional (555 numbers, .example emails)",
          [list(c) for c in ex["clients"]] == [shape] * 3 and all(build.digits(c["phone"]).startswith("555") and c["email"].endswith(".example")
                                                                 for c in ex["clients"]), [list(c) for c in ex["clients"]][:1])

    site = tmp / "site"
    res = build_to(site)
    files = set(res["files"])
    check("a. the build makes every page, the three demo sites, _headers, robots.txt and the favicon",
          set(PAGES) | set(DEMOS) | {"_headers", "robots.txt", "favicon.svg", "examples/demo.js"} <= files, sorted(files)[:40])
    check("a. no build warnings (every example screenshot and the share picture are there)", not res["warnings"], res["warnings"])
    ph = " | ".join(res["placeholders"])
    check("a. the build lists what is still a placeholder (name, city, phone, email, booking link, site address, legal templates)",
          all(w in ph for w in ("agency_name", "city", "phone", "email", "booking link", "site address", "privacy + terms")), ph)

    docs = {}
    for f in sorted(x for x in files if x.endswith(".html")):
        docs[f] = (site / f).read_text(encoding="utf-8")
    bad = {}
    for f, text in docs.items():
        d = parse(text)
        errs = list(d.errors)
        if d.doctype.lower() != "doctype html":
            errs.append("no <!doctype html>")
        html_tag = d.find("html")
        if not html_tag or not html_tag[0].get("lang"):
            errs.append("<html> without lang")
        if not d.find("meta", charset=True):
            errs.append("no meta charset")
        vp = [m for m in d.find("meta") if m.get("name") == "viewport"]
        if not vp or "width=device-width" not in vp[0].get("content", ""):
            errs.append("no phone viewport")
        if not [m for m in d.find("meta") if m.get("name") == "description" and len(m.get("content", "")) >= 15]:
            errs.append("no meta description")
        dup = [i for i, n in d.ids.items() if n > 1]
        if dup:
            errs.append(f"duplicate ids {dup[:5]}")
        if len(d.find("h1")) != 1:
            errs.append(f"{len(d.find('h1'))} h1")
        for img in d.find("img"):
            if "alt" not in img or not img.get("width") or not img.get("height"):
                errs.append(f"img without alt/size: {img.get('src')}")
        ids = set(d.ids)
        labels_for = {a.get("for") for a in d.find("label") if a.get("for")}
        for tag in ("input", "select", "textarea"):
            for a in d.find(tag):
                if a.get("type") in ("hidden", "submit", "button"):
                    continue
                if not (a.get("id") in labels_for or a.get("_in_label") or a.get("aria-label") or a.get("aria-labelledby")):
                    errs.append(f"<{tag} name={a.get('name')}> has no label")
        for t, a, line in d.tags:
            for ref in ("aria-labelledby", "aria-describedby", "aria-controls", "for"):
                if a.get(ref) and any(x not in ids for x in a[ref].split()):
                    errs.append(f"line {line}: {ref}={a[ref]} points nowhere")
            if any(k.startswith("on") for k in a if not k.startswith("_")):
                errs.append(f"line {line}: inline event handler on <{t}>")
            if "style" in a:
                errs.append(f"line {line}: style= attribute (the CSP allows only the stylesheet)")
            if any(str(v).strip().lower().startswith("javascript:") for v in a.values()):
                errs.append(f"line {line}: javascript: URL")
        for s in d.inline_scripts:
            if s[0] != "application/ld+json":
                errs.append("inline <script> (the CSP blocks it)")
            else:
                try:
                    json.loads("".join(s[1:]))
                except ValueError as e:
                    errs.append(f"broken JSON-LD: {e}")
        if errs:
            bad[f] = errs[:6]
    check(f"a. all {len(docs)} pages are valid HTML: doctype, lang, charset, phone viewport, description, one h1, unique ids, "
          "labelled fields, alt + size on every picture, no inline script / handler / style= / javascript: (CSP-clean)", not bad, bad)

    # links and hotlinks
    missing, external, hot = [], set(), []
    for f, text in docs.items():
        d = parse(text)
        base = urllib.parse.urljoin("http://site.test/", f)
        for t, a, line in d.tags:
            for attr in ("href", "src", "action"):
                v = a.get(attr)
                if not v or v.startswith(("tel:", "sms:", "mailto:", "data:")):
                    continue
                u = urllib.parse.urlsplit(urllib.parse.urljoin(base, v))
                if u.hostname != "site.test":
                    if t in ("script", "link", "img", "iframe", "source", "video", "audio", "embed", "object") or attr != "href":
                        hot.append(f"{f}: <{t} {attr}={v}>")
                    else:
                        external.add(u.hostname)
                    continue
                path = u.path.lstrip("/") or "index.html"
                if path.endswith("/"):
                    path += "index.html"
                if path not in files:
                    missing.append(f"{f}: {v}")
                elif u.fragment and path.endswith(".html"):
                    if u.fragment not in parse(docs[path]).ids:
                        missing.append(f"{f}: {v} (no #{u.fragment})")
    check("a. every internal link, picture, script, style and form action points at a file (and #anchor) that exists", not missing, missing[:8])
    check("a. no external hotlinks: no CDN, font, script, picture or frame from another site (only plain links leave the site)", not hot, hot[:6])
    check("a. the only external links are the demos' 'Get directions' map searches (plus the booking link once it is set)",
          external <= {"www.google.com"}, external)
    css = [f for f in files if f.startswith("assets/") and f.endswith(".css")]
    js = [f for f in files if f.endswith(".js")]
    blob = "".join((site / f).read_text(encoding="utf-8") for f in css + js + [f"examples/{t}/style.css" for t in build.TRADES])
    check("a. the css and js never reach out: no @import, no url(http...), no fetch / XHR / beacon / websocket, no analytics",
          not re.search(r"@import|url\(\s*['\"]?(https?:)?//|fetch\(|XMLHttpRequest|sendBeacon|WebSocket|gtag|google-analytics|googletagmanager|facebook\.net",
                        blob), re.findall(r"@import|url\(\s*['\"]?https?:|fetch\(|XMLHttpRequest|sendBeacon|gtag", blob)[:5])
    check("a. the css and js files are fingerprinted (site.<hash>.css / .js) so _headers can cache them for a year",
          len(css) == 1 and re.fullmatch(r"assets/site\.[0-9a-f]{10}\.css", css[0]) and any(re.fullmatch(r"assets/site\.[0-9a-f]{10}\.js", f) for f in js), css + js)

    # Netlify Forms
    for fname, form in (("contact.html", "quote"), ("grader.html", "grader")):
        d = parse(docs[fname])
        fs = d.find("form", name=form)
        f0 = fs[0] if fs else {}
        hid = [a for a in d.find("input", type="hidden") if a.get("name") == "form-name"]
        hp = [a for a in d.find("input") if a.get("name") == "bot-field"]
        hp_box = re.search(r'<p class="hp" aria-hidden="true"><label>[^<]*<input name="bot-field" tabindex="-1" autocomplete="off"></label></p>', docs[fname])
        check(f"a. {fname}: Netlify form '{form}': method POST, data-netlify=true, netlify-honeypot=bot-field, action=/thanks.html, "
              "hidden form-name, a hidden honeypot field kept out of tab order and screen readers",
              f0.get("method") == "POST" and f0.get("data-netlify") == "true" and f0.get("netlify-honeypot") == "bot-field"
              and f0.get("action") == "/thanks.html" and hid and hid[0].get("value") == form and len(hp) == 1 and hp_box, (f0, hid, hp))
        named = [a.get("name") for t, a, _ in d.tags if t in ("input", "select", "textarea") and a.get("name")]
        dup = [n for n, c in Counter(named).items() if c > 1 and not [a for t, a, _ in d.tags if a.get("name") == n and a.get("type") == "radio"]]
        check(f"a. {fname}: every field has a name, names are unique (radio groups aside), the must-haves are required with the right types",
              not dup and all(a.get("name") for t, a, _ in d.tags if t in ("select", "textarea")), dup)
    q = parse(docs["contact.html"])
    req = {a.get("name") for a in q.find("input") if "required" in a}
    check("a. quote form: name, business and phone are required; phone is type=tel, email is type=email (optional)",
          req == {"name", "business", "phone"} and q.find("input", name="phone")[0].get("type") == "tel"
          and q.find("input", name="email")[0].get("type") == "email", req)
    g = parse(docs["grader.html"])
    radios = Counter(a["name"] for a in g.find("input", type="radio"))
    check("a. grader form: 10 questions x (yes / no / not sure) inside the Netlify form, the hidden score + grade fields in the static HTML "
          "(Netlify only keeps fields it saw at deploy), name + email required",
          len(radios) == 10 and set(radios.values()) == {3} and g.find("input", name="score") and g.find("input", name="grade")
          and {a.get("name") for a in g.find("input") if "required" in a} == {"name", "email"}, radios)
    check("a. the grader is honest: it says the browser cannot look inside another site, and the full report is a real scan we run",
          "can't look inside another website" in docs["grader.html"] and "real scan" in docs["grader.html"])
    demo_forms = [f for f in DEMOS if "data-netlify" in docs[f]]
    demo_submit = [f for f in DEMOS if re.search(r'<button[^>]*type="submit"', docs[f]) or "<form" in docs[f]]
    check("a. the demo sites' forms are demos: no Netlify attributes (no junk submissions), no real form, buttons are type=button",
          not demo_forms and not demo_submit, demo_forms + demo_submit)

    # weight budgets
    def weight(page: str) -> int:
        d = parse(docs[page])
        total = len(docs[page].encode())
        here = urllib.parse.urljoin("http://site.test/", page)
        for t, a, _ in d.tags:
            ref = a.get("href") if t == "link" else a.get("src") if t in ("script", "img") else None
            if not ref or ref.startswith("data:"):
                continue
            path = urllib.parse.urlsplit(urllib.parse.urljoin(here, ref)).path.lstrip("/")
            if path.startswith("img/ex/") or path.startswith("img/og"):
                continue                                           # the example screenshots are left out of the budget
            if path in files:
                total += (site / path).stat().st_size
        return total
    w = {p: weight(p) for p in PAGES}
    check("a. every storefront page is under 100 KB with its css + js (example screenshots excluded)", max(w.values()) < 100_000,
          {k: v // 1000 for k, v in w.items()})
    wd = {p: weight(p) for p in DEMOS}
    check("a. every demo site is under 60 KB with its css + js (they are what the agency sells: fast)", max(wd.values()) < 60_000,
          {k: v // 1000 for k, v in wd.items()})
    shots = [f for f in files if f.startswith("img/")]
    sizes = {f: (site / f).stat().st_size for f in shots}
    check("a. the 9 example screenshots are WebP under 90 KB each, the share picture under 400 KB",
          len([f for f in shots if f.startswith("img/ex/") and f.endswith(".webp")]) == 9
          and all(v < 90_000 for f, v in sizes.items() if f.startswith("img/ex/")) and sizes.get("img/og.png", 10 ** 9) < 400_000,
          {k: v // 1000 for k, v in sizes.items()})

    # colours
    pres = build.css_presets()
    pairs = [("--ink", "--bg"), ("--ink-2", "--bg"), ("--muted", "--bg"), ("--muted", "--bg-2"), ("--muted", "--card"), ("--brand-ink", "--brand"),
             ("--brand-ink", "--brand-hover"), ("--brand-text", "--bg"), ("--brand-text", "--bg-2"), ("--brand-text", "--card"),
             ("--brand-text", "--brand-soft"), ("--on-dark", "--dark"), ("--on-dark-muted", "--dark"), ("--on-dark-muted", "--dark-2"),
             ("--brand-on-dark", "--dark"), ("--brand-on-dark", "--dark-2")]
    low = [(p, a, b, round(build.contrast(pres[p][a], pres[p][b]), 2)) for p in build.PRESETS for a, b in pairs
           if build.contrast(pres[p][a], pres[p][b]) < 4.5]
    check("a. the three presets (coral, ocean, forest) are all in the stylesheet and every text / background pair passes WCAG AA (4.5:1)",
          set(build.PRESETS) <= set(pres) and not low, low)
    ring = [(p, bg, round(build.contrast(pres[p]["--brand"], pres[p][bg]), 2)) for p in build.PRESETS for bg in ("--bg", "--bg-2", "--card")
            if build.contrast(pres[p]["--brand"], pres[p][bg]) < 3]
    ring += [(p, "dark", round(build.contrast(pres[p]["--brand-on-dark"], pres[p][d]), 2)) for p in build.PRESETS for d in ("--dark", "--dark-2")
             if build.contrast(pres[p]["--brand-on-dark"], pres[p][d]) < 3]
    css_src = (SF / "src" / "assets" / "site.css").read_text()
    check("a. the keyboard focus ring shows everywhere (3:1): the brand colour on light sections, the on-dark brand colour on dark ones",
          not ring and ".sec-dark :focus-visible, .cta-final :focus-visible, .foot :focus-visible { outline-color: var(--brand-on-dark); }" in css_src, ring)
    lowc = []
    for hx in ("#FFD400", "#7C3AED", "#00A3A3", "#E11D48", "#111111", "#F5F5F5", "#3B82F6"):
        b = build.parse_brand(hx)
        pal = {**pres[b["preset"]], **b["custom"]}
        for a1, b1 in [("--brand-ink", "--brand"), ("--brand-ink", "--brand-hover"), ("--brand-text", "--bg"), ("--brand-text", "--bg-2"),
                       ("--brand-on-dark", "--dark")]:
            if build.contrast(pal[a1], pal[b1]) < 4.5:
                lowc.append((hx, a1, b1, round(build.contrast(pal[a1], pal[b1]), 2)))
    check("a. any brand colour works: yellow, purple, teal, red, near-black, near-white and blue each get readable shades (AA)", not lowc, lowc)
    try:
        build.parse_brand("sparkly")
        okb = False
    except build.BuildError:
        okb = True
    check("a. a typo in brand_color stops the build with a plain message", okb)

    # misc rules
    allt = "".join(docs[p] for p in PAGES)
    check("a. config tokens are all filled ({city}, {from_setup}, ... never reach a page) and the prices come from the config",
          not re.search(r"\{(city|agency|launch_days|demo_days|from_setup|from_monthly|reply_time|phone|email)\}", allt)
          and "$499" in docs["index.html"] and "$1,999" in docs["pricing.html"] and "$129" in docs["pricing.html"])
    check("a. click-to-call everywhere: the header, the phone dock and the footer call the config phone (tel:+15555550100)",
          all(docs[p].count('href="tel:+15555550100"') >= 3 for p in ("index.html", "pricing.html", "contact.html")))
    check("a. no booking link set yet: the Book button falls back to the contact form (never a dead link)",
          'href="contact.html#quote"><span class="way-ico">' in docs["contact.html"] and "Ask for a call back" in docs["contact.html"])
    check("a. legal pages carry the 'Template: edit before going live' note while legal_reviewed is false",
          all("Template: edit before going live" in docs[p] for p in ("privacy.html", "terms.html")))
    check("a. no fake reviews: the reviews section stays hidden while testimonials is empty; demo reviews say 'Sample review'",
          'id="reviews"' not in docs["index.html"] and all(docs[f].count("Sample review") >= 3 for f in DEMOS))
    check("a. thanks and 404 are kept out of Google (noindex); the 404 uses root links so it works at any depth",
          all('name="robots" content="noindex"' in docs[p] for p in ("thanks.html", "404.html"))
          and 'href="/assets/' in docs["404.html"] and 'href="/index.html"' in docs["404.html"])
    hd = (site / "_headers").read_text()
    check("a. _headers: a strict Content-Security-Policy (only the site's own files, forms post to itself, no framing) + year-long cache for /assets/*",
          all(x in hd for x in ("default-src 'self'", "script-src 'self'", "style-src 'self'", "form-action 'self'", "frame-ancestors 'none'",
                                "object-src 'none'", "max-age=31536000, immutable")), hd)
    rb = (site / "robots.txt").read_text()
    check("a. robots.txt keeps the fictional demo businesses and the thanks page out of search", "Disallow: /examples/" in rb and "Disallow: /thanks.html" in rb, rb)
    check("a. the demo sites show the agency's name in their 'Example website by' ribbon (from the config) and hide it in screenshot mode",
          all("Example website by <a href=\"../../index.html\">YOUR AGENCY</a>" in docs[f] for f in DEMOS)
          and all(".shot .demo-ribbon { display: none; }" in (SF / "examples" / t / "style.css").read_text() for t in build.TRADES))

    # the shared agency file (flat names, or team B1's nested format), texts_ok, own colour, legal reviewed
    nope = tmp / "nope.json"
    shared = tmp / "shared.json"
    shared.write_text(json.dumps({"agency_name": "Brightside Web Co", "city": "Tampa", "phone": "(813) 555-0199", "email": "hi@brightside.co",
                                  "brand_colour": "#7C3AED", "other_team_key": 1}))
    cfg = build.load_config(shared_path=shared, example_path=nope)
    r2 = build.build(tmp / "site2", cfg=cfg)
    idx = (tmp / "site2" / "index.html").read_text()
    css2 = (tmp / "site2" / next(f for f in r2["files"] if f.endswith(".css"))).read_text()
    check("a. agency/config.json (the owner's PC copy) with the flat names: agency_name / city / phone / email / brand colour win",
          "Brightside Web Co" in idx and "Tampa" in idx and 'tel:+18135550199' in idx and "hi@brightside.co" in (tmp / "site2" / "contact.html").read_text()
          and cfg["shared_from"] == str(shared), cfg["shared_from"])
    check("a. ... an own brand colour (#7C3AED) becomes readable shades on top of the nearest preset (class brand-custom, no inline style)",
          'class="brand-custom"' in idx and ".brand-custom[data-preset]{--brand:#7C3AED" in css2 and "style=" not in idx, css2[-300:])
    example = tmp / "config.example.json"                     # team B1's committed file, in its own (nested) format
    example.write_text(json.dumps({"agency": {"name": "YOUR AGENCY", "your_name": "YOUR NAME", "phone": "(555) 555-0100", "email": "you@example.com",
                                              "website": ""}, "search": {"city": "YOUR CITY, ST"},
                                   "packages": [{"id": "starter", "name": "Starter", "setup": 499, "monthly": 49, "includes": ["The one-page site you saw", "Hosting"]},
                                                {"id": "growth", "name": "Growth", "setup": 999, "monthly": 79, "includes": ["Everything in Starter", "5 pages"]}]}))
    owner = tmp / "owner.json"
    owner.write_text(json.dumps({"agency": {"name": "Peak Sites", "your_name": "Dee", "phone": "(970) 555-0123", "email": "dee@peaksites.co",
                                            "website": "peaksites.co"}, "search": {"city": "Fort Collins, CO"},
                                 "packages": [{"id": "starter", "name": "Starter", "setup": 399, "monthly": 39, "includes": ["The one-page site you saw", "Hosting"]},
                                              {"id": "growth", "name": "Growth", "setup": 899, "monthly": 69, "includes": ["Everything in Starter", "5 pages"]}],
                                 "storefront": {"booking_url": "https://cal.com/peak/15", "legal_reviewed": True}}))
    c5 = build.load_config(shared_path=owner, example_path=example)
    build.build(tmp / "site5", cfg=c5)
    i5, p5, t5 = ((tmp / "site5" / f).read_text() for f in ("index.html", "pricing.html", "terms.html"))
    check("a. team B1's nested format works too: agency.name, agency.phone, agency.email, search.city, agency.website, packages setup/monthly",
          "Peak Sites" in i5 and "Fort Collins, CO" in i5 and "tel:+19705550123" in i5 and "$399" in p5 and "$69" in p5 and "$1,999" not in p5
          and c5["agency"]["site_url"] == "https://peaksites.co" and 'rel="canonical" href="https://peaksites.co/"' in i5, c5["sources"])
    check("a. ... its plan bullets are used as they are (one source with the pitches; no contradicting page / edit line); a removed plan drops out",
          "The one-page site you saw" in p5 and "30 min of edits" not in p5 and 'id="plan-pro"' not in p5 and "Free with Growth" in p5, re.findall(r"Free with [^<]+", p5))
    check("a. ... the state comes from 'Fort Collins, CO', the 'storefront' block overrides storefront keys (booking link, legal reviewed)",
          "laws of CO" in t5 and "https://cal.com/peak/15" in i5 + p5 + (tmp / "site5" / "contact.html").read_text() and "Template: edit before going live" not in t5)
    c6 = build.load_config(shared_path=nope, example_path=example)
    check("a. a placeholder never hides a real value: B1's example ('YOUR AGENCY', you@example.com) leaves the storefront's own values; without any shared file the storefront config is used",
          c6["agency"]["name"] == "YOUR AGENCY" and c6["agency"]["email"] == "hello@your-agency.example" and c6["sources"]["packages"] == "agency/config.example.json"
          and build.load_config(shared_path=nope, example_path=nope)["agency"]["name"] == "YOUR AGENCY", c6["sources"])
    plain = SF / "owner-copy-test.json"                       # not ignored by git: must not be made
    ignored = SF / "dist" / "owner-copy-test.json"            # dist/ is ignored: may be made
    made_plain = build.ensure_owner_copy(plain, example)
    ignored.parent.mkdir(exist_ok=True)
    made_ignored = build.ensure_owner_copy(ignored, example)
    ok_copy = not made_plain and not plain.exists() and made_ignored and json.loads(ignored.read_text())["agency"]["name"] == "YOUR AGENCY"
    for p in (plain, ignored):
        if p.exists():
            p.unlink()
    check("a. the owner's copy (agency/config.json, from B1's example) is only ever made where git ignores it: a tracked file edited "
          "on the PC would stop the bot's auto-update", ok_copy, (made_plain, made_ignored))
    cfg3 = build.load_config(shared_path=None)
    cfg3["agency"]["texts_ok"] = False
    cfg3["agency"]["legal_reviewed"] = True
    cfg3["agency"]["booking_url"] = "https://cal.com/example/15min"
    build.build(tmp / "site3", cfg=cfg3)
    allt3 = "".join((tmp / "site3" / p).read_text() for p in PAGES)
    check("a. texts_ok false removes every 'Send a text' link; legal_reviewed true removes the template note; a booking link opens in a new tab",
          "sms:" not in allt3 and "Template: edit before going live" not in allt3
          and 'href="https://cal.com/example/15min" target="_blank" rel="noopener"' in allt3, re.findall(r"sms:[^\"]+", allt3)[:2])
    bad_cfg = build.load_config(shared_path=None)
    bad_cfg["packages"][0]["setup_usd"] = "lots"
    try:
        build.build(tmp / "site4", cfg=bad_cfg)
        stopped = False
    except build.BuildError as e:
        stopped = "setup_usd must be a number" in str(e)
    check("a. a wrong price in config.json stops the build and says which plan and field", stopped)
    typo = tmp / "typo.json"
    typo.write_text('{\n  "agency_name": "X",\n  "city": "Y"\n  "phone": "1"\n}')
    try:
        build.load_config(path=typo, shared_path=None)
        said = ""
    except build.BuildError as e:
        said = str(e)
    check("a. a missing comma in config.json is reported with its line number, in plain words", "line 4" in said and "commas" in said, said)

    # the zip
    check("a. build.py --check says the config builds (and writes nothing)", build.main(["--check"]) == 0)
    z1, z2 = tmp / "a.zip", tmp / "b.zip"
    build.make_zip(site, z1)
    build.build(tmp / "again")
    build.make_zip(tmp / "again", z2)
    names = zipfile.ZipFile(z1).namelist()
    check("a. the zip has index.html at its root (Netlify Drop serves the root), every page, no build folders, under 1.5 MB",
          "index.html" in names and set(PAGES) <= set(names) and not any(n.startswith(("dist/", "site/", "_mockups")) for n in names)
          and z1.stat().st_size < 1_500_000, (names[:5], z1.stat().st_size))
    check("a. two builds give the same zip byte for byte (fixed dates, sorted names)", z1.read_bytes() == z2.read_bytes())
    tracked = os.popen(f"git -C {ROOT} ls-files agency/storefront/dist").read().split()
    check("a. dist/ (the site folder and the zip) is never tracked, so a build on the PC changes no tracked file",
          not tracked and build.git_ignored(SF / "dist" / "storefront.zip") is True, tracked)


# ------------------------------------------------------------------------------------------------ b. grade.py
def part_b(tmp: Path):
    today = dt.date(2026, 11, 14)
    good = grade.grade_offline((FIX / "good.html").read_text(), "https://joes.example/", city="Springfield", today=today)
    bad = grade.grade_offline((FIX / "bad.html").read_text(), "http://bobs.example/", {"final_url": "http://bobs.example/"}, today=today)
    noi = grade.grade_offline((FIX / "noindex.html").read_text(), "https://sunny.example/", today=today)
    host = grade.grade_offline((FIX / "hostile.html").read_text(), "https://evil.example/", today=today)
    by = lambda r: {c["id"]: c for c in r["checks"]}  # noqa: E731
    check("b. the healthy fixture grades A (100) with nothing to fix", good["grade"] == "A" and good["score"] >= 90 and not good["fixes"],
          (good["score"], [c["id"] for c in good["checks"] if c["status"] != "pass"]))
    check("b. the dated fixture grades F; its top fixes are the padlock, the phone layout and tap-to-call",
          bad["grade"] == "F" and bad["score"] < 45 and [f["id"] for f in bad["fixes"]] == ["https", "mobile", "tap_call"], (bad["score"], [f["id"] for f in bad["fixes"]]))
    b = by(bad)
    check("b. ... it sees the number that can't be tapped, the address with no Google link, no button, the old tech and the old year",
          b["tap_call"]["status"] == "warn" and "555-555-0122" in b["tap_call"]["found"] and "address is on the page" in b["google"]["found"]
          and b["cta"]["status"] == "fail" and "marquee" in b["fresh"]["found"] and "2015" in b["fresh"]["found"], {k: v["found"] for k, v in b.items()})
    n = by(noi)
    check("b. a page hidden from Google (noindex) is always fix number 1; blocked zoom and two H1s are warnings",
          noi["fixes"][0]["id"] == "indexable" and n["mobile"]["status"] == "warn" and n["h1"]["status"] == "warn", [f["id"] for f in noi["fixes"]])
    rep = grade.report_html(host, business="<b>Evil</b> & Co")
    rd = parse(rep)
    evil = [(t, a) for t, a, _ in rd.tags if t in ("script", "img", "iframe", "object", "embed")
            or any(k.startswith("on") for k in a if not k.startswith("_"))]
    check("b. hostile text from a page (script tags, onerror, a tel: injection) comes out escaped in the report: no script, no handler",
          not evil and "&lt;script&gt;" in rep and "&lt;b&gt;Evil&lt;/b&gt; &amp; Co" in rep and not rd.errors, (evil[:3], rd.errors[:3]))
    rep_bad = grade.report_html(bad, business="Bob's Barber Shop")
    d2 = parse(rep_bad)
    check("b. the report: valid HTML, the agency's name and phone, the grade, top fixes, 14 checked rows, print CSS (@page), under 40 KB, no external file",
          not d2.errors and "YOUR AGENCY" in rep_bad and "(555) 555-0100" in rep_bad and "Grade F" in rep_bad and rep_bad.count("<tr") == 14
          and "@page" in rep_bad and len(rep_bad) < 40_000 and not re.search(r'(src|href)="https?:', rep_bad), d2.errors[:3])
    check("b. the report offers the plan that fixes it (Growth when the Google profile is missing) at the config's prices",
          "Growth</b> plan: $999 setup + $79 a month" in rep_bad, re.findall(r"offer-main\">[^<]+<b>[^<]+</b>[^<]+", rep_bad))
    for raw, want in (("joes.com", "https://joes.com/"), ("HTTP://Joes.COM/menu", "http://joes.com/menu"), (" https://a.b.example ", "https://a.b.example/")):
        check(f"b. normalize_url({raw!r}) -> {want}", grade.normalize_url(raw) == want, grade.normalize_url(raw))
    for raw in ("", "not a website", "joes"):
        try:
            grade.normalize_url(raw)
            ok = False
        except ValueError:
            ok = True
        check(f"b. normalize_url({raw!r}) is refused in plain words", ok)

    # the polite visit, against a local server
    web = tmp / "web"
    web.mkdir()
    shutil.copy(FIX / "good.html", web / "index.html")
    (web / "style.css").write_text("body{}" * 50)
    (web / "app.js").write_text("//" + "x" * 3000)
    (web / "van.webp").write_bytes(b"\0" * 900_000)
    (web / "team.webp").write_bytes(b"\0" * 40_000)
    (web / "old").mkdir()
    shutil.copy(FIX / "bad.html", web / "old" / "index.html")

    class Moved(Rec):
        def do_GET(self):  # noqa: N802
            if self.path == "/moved":
                self.send_response(301)
                self.send_header("Location", "/")
                self.end_headers()
                return
            super().do_GET()

        def do_HEAD(self):  # noqa: N802
            Moved.heads.append(self.path)
            super().do_HEAD()
    Moved.heads = []
    httpd, url = serve(web, Moved)
    out = tmp / "reports"
    try:
        r = grade.grade_url(url + "/moved", out, "Joe's Plumbing", "Springfield")
        w = {c["id"]: c for c in r["checks"]}["weight"]
        check("b. a real visit: the redirect is followed and recorded, the page and its 4 files are weighed by HEAD (no downloads)",
              r["net"]["redirects"] and r["net"]["redirects"][0][0] == 301 and len(r["net"]["assets"]) == 4
              and sorted(Moved.heads) == ["/app.js", "/style.css", "/team.webp", "/van.webp"], (r["net"]["redirects"], Moved.heads))
        check("b. ... a 900 KB picture is called out in the weight check; http:// is graded as no padlock",
              w["status"] == "warn" and "1 picture(s) over 400 KB" in w["found"] and {c["id"]: c for c in r["checks"]}["https"]["status"] == "fail", w)
        files = sorted(p.name for p in out.iterdir())
        stem = f"{dt.date.today():%Y-%m-%d}-127.0.0.1"
        check("b. the report and the raw numbers are saved as <date>-<host>.html / .json (the host's last part is kept)",
              f"{stem}.html" in files and f"{stem}.json" in files and json.loads((out / f"{stem}.json").read_text())["score"] == r["score"], files)
        rc = grade.main([url + "/nothing-here.html", "--out", str(out)])
        j = json.loads((out / f"{stem}.json").read_text())
        check("b. a page that answers 404 gets an honest 'did not open' report (grade F, exit code 2)", rc == 2 and j["grade"] == "F" and "404" in j["down"], j.get("down"))
        rc = grade.main(["http://127.0.0.1:9/", "--out", str(out)])
        check("b. a site that does not answer at all: the same honest report, exit code 2", rc == 2)
        clients = tmp / "clients.json"
        clients.write_text(json.dumps({"clients": [
            {"id": "c1", "name": "Joe's Plumbing", "trade": "plumber", "city": "Springfield", "phone": "", "email": "", "site_url": url + "/",
             "demo_url": "", "status": "lead", "package": "", "setup_usd": 0, "monthly_usd": 0, "notes": ""},
            {"id": "c2", "name": "Bob's Barber", "trade": "barber", "city": "Springfield", "phone": "", "email": "", "site_url": "",
             "demo_url": "", "status": "lead", "package": "", "setup_usd": 0, "monthly_usd": 0, "notes": ""}]}))
        grade.main(["--batch", str(clients), "--out", str(out / "batch"), "--page-only"])
        gj = json.loads((out / "batch" / "grades.json").read_text())
        check("b. batch mode reads the shared client records: one row per client, a score for the site (86: all but the padlock, "
              "a local server has no https), 'perfect lead' for no website",
              [g["id"] for g in gj] == ["c1", "c2"] and gj[0]["score"] == 86 and gj[0]["top_fix"] == "Secure padlock (HTTPS)"
              and gj[1]["score"] is None and "perfect lead" in gj[1]["note"], gj)
        shy = tmp / "shy"
        shy.mkdir()
        shutil.copy(FIX / "good.html", shy / "index.html")
        (shy / "robots.txt").write_text("User-agent: *\nDisallow: /\n")
        httpd3, url3 = serve(shy)
        (tmp / "shy.txt").write_text(url3 + "/\n")
        grade.main(["--batch", str(tmp / "shy.txt"), "--out", str(out / "batch2")])
        httpd3.shutdown()
        g2 = json.loads((out / "batch2" / "grades.json").read_text())
        check("b. batch mode (cold leads) obeys robots.txt: a site that asks tools to stay away is skipped, with a plain note",
              g2[0]["score"] is None and "robots.txt" in g2[0]["note"], g2)
        demo_site = tmp / "demo_site"
        build.build(demo_site)
        shutil.copytree(SF / "mockups", demo_site / "_mockups")
        httpd2, url2 = serve(demo_site)
        demos = {}
        for t in build.TRADES:
            demos[t] = grade.grade_url(f"{url2}/examples/{t}/index.html", tmp / "r2")
        befores = {t: grade.grade_url(f"{url2}/_mockups/before-{t}.html", tmp / "r3") for t in build.TRADES}
        httpd2.shutdown()
        nonhttps = lambda r: [c["id"] for c in r["checks"] if c["status"] != "pass" and c["id"] != "https"]  # noqa: E731
        check("b. practice what we preach: the three demo sites pass every check but the padlock (a local test server has no https)",
              all(not nonhttps(r) for r in demos.values()), {t: nonhttps(r) for t, r in demos.items()})
        check("b. ... and the made-up 'before' pages grade D or F, at least 40 points below their demo",
              all(r["score"] < 60 and demos[t]["score"] - r["score"] >= 40 for t, r in befores.items()),
              {t: (r["score"], demos[t]["score"]) for t, r in befores.items()})
    finally:
        httpd.shutdown()
    import gzip

    class Zipped(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            body = gzip.compress((FIX / "good.html").read_bytes()) if self.path == "/" else gzip.compress(b"<p>" + b"0" * 20_000_000)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass
    zs = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Zipped)
    threading.Thread(target=zs.serve_forever, daemon=True).start()
    zu = f"http://127.0.0.1:{zs.server_address[1]}"
    try:
        f1 = grade.fetch_page(zu + "/")
        f2 = grade.fetch_page(zu + "/bomb")
    finally:
        zs.shutdown()
    check("b. a gzip page is unpacked and read (its title found); a 'gzip bomb' (20 MB of zeros in 20 KB) stops at the 5 MB cap",
          grade.analyse(f1["html"], zu)["title"] == "Plumber in Springfield | Joe's Plumbing" and f1["wire_bytes"] < f1["html_bytes"]
          and f2["html_bytes"] == grade.MAX_BYTES and f2["wire_bytes"] < 100_000, (f1["html_bytes"], f2["html_bytes"], f2["wire_bytes"]))
    old = grade.REPORTS
    try:
        grade.REPORTS = tmp / "data" / "agency" / "reports"
        d = grade.reports_dir()
        check("b. the default reports folder (data/agency/reports) keeps itself out of git (.gitignore with *)",
              (d / ".gitignore").read_text().strip().endswith("*"))
    finally:
        grade.REPORTS = old
    check("b. nothing private is tracked: no report or prospect data in git",
          not os.popen(f"git -C {ROOT} ls-files data/agency").read().split())


# ------------------------------------------------------------------------------------------------ c. the browser
def part_c(tmp: Path):
    from playwright.sync_api import sync_playwright
    from tests import browser_kit as BK
    site = tmp / "bsite"
    build.build(site)
    Rec.posts = []
    hd = (site / "_headers").read_text()
    csp = re.search(r"Content-Security-Policy:\s*(.+)", hd).group(1).strip()
    Rec.extra = {"Content-Security-Policy": csp}          # the browser runs the site under its real Netlify policy
    httpd, url = serve(site)
    phone = {"viewport": {"width": 390, "height": 844}, "device_scale_factor": 2, "is_mobile": True, "has_touch": True}
    desk = {"viewport": {"width": 1440, "height": 900}}
    try:
        with sync_playwright() as pw:
            br = BK.launch(pw)

            def opened(kw, path, motion="reduce"):
                ctx = br.new_context(**kw, reduced_motion=motion)
                p = ctx.new_page()
                p.errs, p.bad = [], []
                p.on("pageerror", lambda e: p.errs.append(str(e)))
                p.on("console", lambda m: p.errs.append(m.text) if m.type == "error" else None)
                p.on("response", lambda r: p.bad.append(f"{r.status} {r.url}") if r.status >= 400 else None)
                p.goto(url + path, wait_until="load")
                p.evaluate("() => document.querySelectorAll('img[loading=lazy]').forEach(i => { i.loading = 'eager'; })")
                p.wait_for_function("() => Array.from(document.images).every(i => i.complete)", timeout=20000)
                return ctx, p

            for label, kw in (("390 x 844", phone), ("1440 x 900", desk)):
                bad = {}
                for pg in PAGES + DEMOS:
                    ctx, p = opened(kw, "/" + pg)
                    side = p.evaluate("document.documentElement.scrollWidth - innerWidth")
                    broken = p.evaluate("Array.from(document.images).filter(i => !i.naturalWidth).map(i => i.src)")
                    if p.errs or p.bad or side > 0 or broken:
                        bad[pg] = {"errors": p.errs[:2], "404": p.bad[:2], "sideways": side, "broken": broken[:2]}
                    ctx.close()
                check(f"c. {label}: all {len(PAGES + DEMOS)} pages load under the site's own strict CSP with no script error or blocked "
                      "style, no missing file, no sideways scroll, every picture shown", not bad, bad)

            ctx, p = opened(phone, "/index.html")
            nav_hidden = p.evaluate("getComputedStyle(document.getElementById('site-nav')).display") == "none"
            p.click(".menu-btn")
            opened_ok = p.evaluate("document.getElementById('site-nav').classList.contains('open')") and p.get_attribute(".menu-btn", "aria-expanded") == "true"
            p.keyboard.press("Escape")
            closed = p.get_attribute(".menu-btn", "aria-expanded") == "false"
            check("c. phone: the menu button opens the menu (aria-expanded), Escape closes it", nav_hidden and opened_ok and closed, (nav_hidden, opened_ok, closed))
            small = p.evaluate("""() => Array.from(document.querySelectorAll('.btn, .dock a, .menu-btn, .seg span, .chips span'))
                .filter(e => e.offsetParent && e.getBoundingClientRect().height < 44).map(e => e.textContent.trim().slice(0, 30))""")
            dock = p.evaluate("getComputedStyle(document.querySelector('.dock')).position === 'fixed' && document.querySelector('.dock').getBoundingClientRect().bottom <= innerHeight + 1")
            check("c. phone: the Call / Get a free demo dock sits at the bottom; every button is at least 44 px tall", dock and not small, (dock, small))
            hero = p.evaluate("document.querySelector('.hero h1').getBoundingClientRect().top < innerHeight && document.querySelector('.hero .btn-primary').getBoundingClientRect().bottom < innerHeight")
            check("c. phone: the headline and the main button are on the first screen", hero)
            ctx.close()
            ctx, p = opened(desk, "/index.html")
            vis = p.evaluate("[getComputedStyle(document.getElementById('site-nav')).display, getComputedStyle(document.querySelector('.menu-btn')).display, getComputedStyle(document.querySelector('.dock')).display]")
            check("c. desktop: the full menu shows, no menu button, no phone dock", vis == ["flex", "none", "none"], vis)
            anim = p.evaluate("document.getAnimations().length")
            ctx.close()
            ctx, p = opened(desk, "/index.html", motion="no-preference")
            anim2 = p.evaluate("document.getAnimations().length")
            check("c. reduced motion: no animation at all; without it the hero gently rises in", anim == 0 and anim2 > 0, (anim, anim2))
            ctx.close()

            for pre in build.PRESETS:
                ctx, p = opened(phone, f"/index.html?preset={pre}")
                got = p.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--brand').trim()").upper()
                check(f"c. ?preset={pre} previews that colour preset ({got})", got == build.css_presets()[pre]["--brand"].upper(), got)
                ctx.close()

            ctx, p = opened(phone, "/grader.html")
            p.click("#g-start")
            stopped = p.evaluate("document.activeElement.id") == "g-site" and "Type your website" in p.inner_text("#g-site-help")
            p.fill("#g-site", "joesplumbing.com")
            p.click("#g-start")
            host = p.inner_text("#g-host")
            href = p.get_attribute("#g-open", "href")
            check("c. grader: Start without an address asks for it; with one it shows the host and an 'open it in a new tab' link",
                  stopped and host == "joesplumbing.com" and href == "https://joesplumbing.com", (stopped, host, href))
            picks = ["yes", "no", "yes", "unsure", "no", "yes", "yes", "no", "no", "yes"]
            boxes = p.query_selector_all("fieldset.q")
            for fs, v in zip(boxes[:3], picks):
                fs.query_selector(f'input[value="{v}"]').evaluate("el => el.click()")
            part = p.inner_text("#g-sub")
            for fs, v in zip(boxes[3:], picks[3:]):
                fs.query_selector(f'input[value="{v}"]').evaluate("el => el.click()")
            quiz = json.loads((SF / "src" / "quiz.json").read_text())["questions"]
            want = round(100 * sum(q["w"] * {"yes": 1, "no": 0, "unsure": .5}[v] for q, v in zip(quiz, picks)) / 100)
            score = int(p.inner_text("#g-score"))
            fixes = p.query_selector_all("#g-fixes li")
            check(f"c. grader: partial answers say 'Based on 3 of 10'; all ten give the weighted score ({want}), a grade and 3 fixes",
                  "Based on 3 of 10" in part and score == want and p.inner_text("#g-grade") in "ABCDF" and len(fixes) == 3,
                  (part, score, want, len(fixes)))
            check("c. grader: the hidden score and grade fields are filled for the report request",
                  p.input_value("#g-score-in") == str(want) and p.input_value("#g-grade-in") == p.inner_text("#g-grade"))
            p.fill("#g-name", "Joe")
            p.fill("#g-email", "joe@joes.example")
            with p.expect_navigation():
                p.click("#report button[type=submit]")
            post = Rec.posts[-1] if Rec.posts else {}
            check("c. grader: sending posts the Netlify form (form-name grader, the site, all 10 answers, the score) and lands on thanks",
                  p.url.endswith("/thanks.html") and post.get("form-name") == ["grader"] and post.get("website") == ["https://joesplumbing.com"]
                  and len([k for k in post if k.startswith("q_")]) == 10 and post.get("score") == [str(want)] and not post.get("bot-field", [""])[0],
                  {k: v for k, v in post.items()})
            ctx.close()
            ctx, p = opened(phone, "/grader.html")
            p.check("#g-nosite")
            check("c. grader: 'I don't have a website yet' swaps the quiz for the free-demo offer",
                  p.is_visible("#g-nosite-box") and not p.is_visible("#quiz"))
            ctx.close()

            ctx, p = opened(phone, "/contact.html?plan=growth")
            picked = p.evaluate("document.querySelector('input[name=plan]:checked').value")
            p.fill("#q-name", "Maria")
            p.fill("#q-biz", "Maria's Bakery")
            p.fill("#q-phone", "555 555 0144")
            with p.expect_navigation():
                p.click("#quote button[type=submit]")
            post = Rec.posts[-1]
            check("c. contact: ?plan=growth (from a pricing button) picks Growth; sending posts form 'quote' with the fields and lands on thanks",
                  picked == "growth" and post.get("form-name") == ["quote"] and post.get("plan") == ["growth"] and post.get("business") == ["Maria's Bakery"]
                  and p.url.endswith("/thanks.html"), (picked, post))
            ctx.close()

            ctx, p = opened(phone, "/examples/restaurant/index.html?now=2026-11-13T18:30")
            o1 = p.inner_text(".open")
            ctx.close()
            ctx, p = opened(phone, "/examples/restaurant/index.html?now=2026-11-13T03:00")
            o2 = p.inner_text(".open")
            p.click("[data-demo-send]")
            note = p.inner_text("[data-demo-msg]")
            ctx.close()
            check("c. demo restaurant: 'Open now · until 11pm' on a Friday evening, 'Closed now · opens 5pm today' at 3am; its booking form only explains it is a demo",
                  o1 == "Open now · until 11pm" and o2 == "Closed now · opens 5pm today" and "nothing was sent" in note, (o1, o2, note))
            ctx, p = opened(phone, "/examples/barber/index.html?shot")
            rib = p.evaluate("getComputedStyle(document.querySelector('.demo-ribbon')).display")
            ctx.close()
            check("c. screenshot mode (?shot) hides the agency ribbon on the demos", rib == "none", rib)
            br.close()
    finally:
        httpd.shutdown()
        Rec.extra = {}

    exe = grade.find_browser()
    if exe:
        r = grade.grade_offline((FIX / "bad.html").read_text(), "http://bobs.example/", {"final_url": "http://bobs.example/"})
        h = tmp / "2026-11-14-bobs.example.html"
        h.write_text(grade.report_html(r, "Bob's Barber Shop"))
        pdf = grade.to_pdf(h)
        pages = len(re.findall(rb"/Type\s*/Page[^s]", pdf.read_bytes())) if pdf else 0
        check("c. --pdf: Edge / Chrome prints the report to a PDF of exactly one page", pdf and pdf.name == "2026-11-14-bobs.example.pdf" and pages == 1, (pdf, pages))


def main():
    tmp = Path(tempfile.mkdtemp(prefix="agency-sf-"))
    try:
        part_a(tmp)
        part_b(tmp)
        if os.environ.get("AS_NO_BROWSER") != "1":
            part_c(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
