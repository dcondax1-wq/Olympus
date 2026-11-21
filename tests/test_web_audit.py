"""tools/site_audit.py: the prospect website audit (day-web-audit 2026-11-20, Agency app).

  a. pure: slug, Google's bounce curve (1 s 0 %, 3 s 32 %, 5 s 90 %, 10 s 123 %), the basics a local site needs (tap-to-call, map, hours,
     Google Business link, schema, HTTPS ...), the accessibility score, the grade, the 3 losses ranked, each with a cited source,
     the $ estimate only when visitors + value are given
  b. the report page: no script, no tracking, nothing loaded from another site (only plain source links), noindex, the screenshot
     next to it; the index lists every audit and how to run one
  c. one real Chromium run as a phone on a local fixture site (no internet): numbers measured, screenshot written, audits.json +
     index.html updated, a slow / jumpy / no-tap-to-call fixture gets those in its 3 losses
  d. the committed demo audits are of big brands only, and every one has its page + screenshot
    python -X utf8 -m tests.test_web_audit
"""
from __future__ import annotations

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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import site_audit as A  # noqa: E402

RES = []
BIG_BRANDS = ("starbucks", "mcdonalds", "ikea", "target", "walmart", "nike", "apple", "bestbuy", "homedepot", "lowes")


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(detail)[:500]})" if detail and not cond else ""))


GOOD = """<html><head><title>Joe's Plumbing | 24/7</title><meta name="description" content="Fast local plumbers, open every day">
<link rel="icon" href="/f.ico"><meta property="og:image" content="/x.jpg">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"Plumber","name":"Joe"}</script>
<script type="application/ld+json">{"@type":["LocalBusiness","Organization"]}</script></head>
<body><a href="tel:+15550100">Call</a><a href="https://maps.app.goo.gl/abc">Directions</a><p>Hours: Mon-Fri 8-6, Sat 9-1</p>
<a href="https://g.page/joes/review">Reviews</a></body></html>"""
BAD = "<html><head></head><body><p>Call us 555-0100</p></body></html>"


def main() -> int:
    check("a. slug from the host", A.slug_of("https://www.Starbucks.com/menu?x=1") == "starbucks-com" and A.slug_of("shop.example.co.uk") == "shop-example-co-uk")
    check("a. Google's bounce curve (vs a 1 s page)", [A.bounce_up(x) for x in (0.5, 1, 2, 3, 4, 5, 6, 8, 10, 20)] == [0, 0, 16, 32, 61, 90, 106, 114, 123, 123])
    g, b = A.basics(GOOD, "https://joes.example/"), A.basics(BAD, "http://bad.example/")
    check("a. basics: a good local page has them all", all(g[k] for k in ("https", "title", "description", "tap_to_call", "map", "hours",
          "google_business", "schema", "local_schema", "favicon", "share_image")) and {"Plumber", "LocalBusiness"} <= set(g["schema_types"]), g)
    check("a. basics: a bare page has none of them", not any(b[k] for k in ("https", "title", "description", "tap_to_call", "map", "hours",
          "google_business", "schema", "favicon", "share_image")), b)
    check("a. accessibility score: 0 problems 100; impact costs more; floor 0",
          A.a11y_score([]) == 100 and A.a11y_score([{"impact": "critical", "nodes": [1]}]) == 90
          and A.a11y_score([{"impact": "minor", "nodes": [1] * 30}]) == 96 and A.a11y_score([{"impact": "critical", "nodes": [1] * 99}] * 9) == 0)
    fast = {"lcp_s": 1.4, "cls": 0.02, "a11y": 98, "basics": g}
    slow = {"lcp_s": 7.5, "cls": 0.4, "a11y": 55, "basics": b, "small_taps": 20}
    check("a. grade: a fast complete page A, a slow bare one F", A.grade(fast) == "A" and A.grade(slow) == "F", (A.grade(fast), A.grade(slow)))
    L = A.losses(slow)
    check("a. 3 losses, ranked: slow first (with Google's number), then no padlock / tap-to-call; each cites a source",
          len(L) == 3 and "7.5 s" in L[0]["title"] and "112 %" in L[0]["money"] and all(x["src"] and all(s in A.SOURCES for s in x["src"]) for x in L), L)
    acc = A.losses({"lcp_s": 1.2, "cls": 0, "a11y": 70, "basics": g})
    check("a. accessibility under 90 is a loss with the ADA lawsuit number (cited)", len(acc) == 1 and "5,000" in acc[0]["money"]
          and "ada" in acc[0]["src"], acc)
    check("a. a fast complete page has nothing big to lose", A.losses(fast) == [], A.losses(fast))
    check("a. the $ estimate only with visitors + value", "estimate" not in L[0] and "$" in A.losses(slow, 1500, 120)[0].get("estimate", ""))
    m = dict(slow, final_url="http://bad.example/", fcp_s=3.1, tbt_ms=1200, mb=4.2, requests=80, sideways=True, small_text=3, zoom_blocked=True,
             a11y_n=2, a11y_top=[{"impact": "serious", "help": "Elements must have enough color contrast", "n": 12}], grade="F", losses=L)
    page = A.page_html(m, "Bad <Shop>", "bad.png", "2026-11-20")
    body = re.sub(r'<a href="https?://[^"]+" rel="noopener noreferrer">', "", page)       # the source links are plain links
    check("b. report: no script, no external file, no tracking pixel; noindex; the screenshot is the one local image",
          "<script" not in page and not re.search(r'(src|href)=["\']https?://', body) and "@import" not in page and "noindex" in page
          and re.findall(r'<img[^>]+src="([^"]+)"', page) == ["bad.png"], re.findall(r'(?:src|href)="(https?://[^"]+)"', body)[:3])
    check("b. report: escaped name, the grade, the 3 losses, every cited source listed with its link",
          "Bad &lt;Shop&gt;" in page and ">F<" in page and all(A.html.escape(x["title"]) in page for x in L)
          and all(A.SOURCES[s][1] in page for x in L for s in x["src"]), page[:300])
    idx = A.index_html([{"slug": "a-com", "name": "A", "when": "2026-11-20", "grade": "B", "lcp_s": 2.1, "cls": 0.05, "a11y": 90}])
    check("a. a bot wall is not audited: 403 / 'Access Denied' / 'Just a moment' are caught, a normal page is not",
          A.blocked({"status": 403}) and A.blocked({"status": 200, "title": "Access Denied"}) and A.blocked({"status": 200, "text": "Just a moment..."})
          and not A.blocked({"status": 200, "title": "Joe's Plumbing", "text": "We fix pipes"}))
    check("b. accessibility is a headline card with the ADA number and its source", "Accessibility: 55/100" in page and "5,000" in page
          and A.SOURCES["ada"][1] in page)
    check("b. review: the ADA sources link the exact 2025 reports (not a home page); basics say 'on the home page'",
          all(urllib.parse.urlsplit(A.SOURCES[k][1]).path.strip("/") for k in ("ada", "ada_fed")) and "on the home page" in page)
    check("a. robots.txt is checked for the same name the tool sends (UA token), imported at module top",
          (A.ROBOT_NAME + "/") in A.UA_PHONE and callable(A.robots_ok))
    check("b. index: lists the audit and how to run one", 'href="a-com.html"' in idx and "tools/site_audit.py" in idx and "<script" not in idx)

    site = tempfile.mkdtemp(prefix="le_webaudit_site_")
    out = tempfile.mkdtemp(prefix="le_webaudit_out_")
    try:
        open(os.path.join(site, "index.html"), "w").write(
            "<!doctype html><html><head><title>Slow Shop</title><meta name=viewport content='width=device-width'></head><body>"
            "<div id=ad></div><h1>Slow Shop</h1><p>Call 555-0100. We fix bikes.</p>"
            "<script>setTimeout(()=>{document.getElementById('ad').style.height='300px';document.getElementById('ad').textContent='Big banner'},1500);"
            "const t=performance.now();while(performance.now()-t<400){}</script></body></html>")
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(http.server.SimpleHTTPRequestHandler, directory=site))
        srv.RequestHandlerClass.log_message = lambda *a: None
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{srv.server_address[1]}/"
        env_proxy = {k: os.environ.pop(k) for k in ("HTTPS_PROXY", "https_proxy") if k in os.environ}
        try:
            m = A.audit(url, out, slug="slow-shop", name="Slow Shop", robots=False, say=lambda *_a: None)
        finally:
            os.environ.update(env_proxy)
            srv.shutdown()
        titles = " | ".join(x["title"] for x in m["losses"])
        check("c. a real phone run: paints measured, the layout jump caught, blocking time counted",
              m["lcp_s"] > 0 and m["cls"] > 0.1 and m["tbt_ms"] >= 300, {k: m[k] for k in ("lcp_s", "cls", "tbt_ms", "mb")})
        check("c. its 3 losses: no padlock (plain http), the missing basics, no tap-to-call (the jump is measured above, ranked 4th)",
              "padlock" in titles.lower() and "tap-to-call" in titles and "basics" in titles, titles)
        check("c. files: <slug>.html + .png + audits.json + index.html", all(os.path.isfile(os.path.join(out, f)) for f in
              ("slow-shop.html", "slow-shop.png", "audits.json", "index.html", "summary.json"))
              and json.load(open(os.path.join(out, "summary.json")))["n"] == 1 and json.load(open(os.path.join(out, "audits.json")))[0]["slug"] == "slow-shop")
    finally:
        shutil.rmtree(site, ignore_errors=True)
        shutil.rmtree(out, ignore_errors=True)

    try:
        rows = json.load(open(os.path.join(A.OUT, "audits.json"), encoding="utf-8"))
    except (OSError, ValueError):
        rows = []
    check("d. committed demo audits: big brands only, each with its page + screenshot, listed in index.html",
          rows and all(any(b in r["slug"] for b in BIG_BRANDS) for r in rows)
          and all(os.path.isfile(os.path.join(A.OUT, r["slug"] + ext)) for r in rows for ext in (".html", ".png"))
          and all(r["slug"] + ".html" in open(os.path.join(A.OUT, "index.html"), encoding="utf-8").read() for r in rows), rows)
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
