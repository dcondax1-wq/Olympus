"""Agency SHOWCASE (tools/web_public/agency/showcase/, day-web 2026-11-20): the owner's own agency website, the page a prospect sees.
  a. static: the files; brand.json (name, offers with prices, the 7-day plan, demos); the page is content-first plain HTML with the
     default words; share card (og:image 1200 x 630, og.jpg in the folder); LocalBusiness JSON-LD; the form has no backend (no action,
     no POST, no fetch to send); nothing stored (no localStorage / cookies); three.js from the site; no innerHTML
  b. Chromium 390 x 844: brand.json is applied (a changed brand shows its name, prices and JSON-LD), the demo list, the contact form opens
     mailto: / sms: with the message filled in (and asks for a missing name), every tap >= 44 px, no sideways scroll, no console error
  c. speed: 4x CPU: first contentful paint < 1.5 s, layout shift < 0.05 with the 3D on; the 3D comes after the words (idle) and is skipped
     under reduced motion / ?3d=0 (a still skyline)
    python -X utf8 -m tests.test_web_showcase           (--static: part a only)
"""
from __future__ import annotations

import json
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

check = AK.check
D = os.path.join(AK.WEB, "agency", "showcase")
FILES = ("index.html", "showcase.js", "city.js", "brand.json", "og.jpg", "icon.svg")


def jpeg_size(path):
    with open(path, "rb") as f:
        b = f.read()
    i = 2
    while i < len(b):
        if b[i] != 0xFF:
            i += 1
            continue
        m = b[i + 1]
        if m in (0xC0, 0xC1, 0xC2):
            h, w = struct.unpack(">HH", b[i + 5:i + 9])
            return w, h
        i += 2 + struct.unpack(">H", b[i + 2:i + 4])[0]
    return None


def test_static():
    have = [f for f in FILES if os.path.isfile(os.path.join(D, f))]
    check("a. the files are there (%s)" % ", ".join(FILES), len(have) == len(FILES), sorted(set(FILES) - set(have)))
    html, js, city = (AK.read(os.path.join(D, f)) for f in ("index.html", "showcase.js", "city.js"))
    B = json.load(open(os.path.join(D, "brand.json"), encoding="utf-8"))
    check("a. brand.json: a name, a tagline, contact placeholders, 3 offers with numeric prices (one marked best), a 6-step week, 8 demos with slugs + colours",
          B.get("name") and B.get("tagline") and B.get("phone") and B.get("email") and len(B["offers"]) == 3 and all(isinstance(o["price"], (int, float)) for o in B["offers"])
          and sum(1 for o in B["offers"] if o.get("best")) == 1 and len(B["week"]) == 6 and len(B["demos"]) == 8
          and all(re.fullmatch(r"[a-z0-9-]+", x["slug"]) and re.fullmatch(r"#[0-9a-fA-F]{6}", x["color"]) for x in B["demos"]), B.get("name"))
    check("a. no real contact data shipped: example.com email, a 555 phone, placeholders the owner fills", B["email"].endswith("@example.com") and "555" in B["phone"])
    check("a. content first: the words, prices, the 7-day plan and the form are in the HTML itself (readable with no script); one h1; skip link",
          html.count("<h1") == 1 and "$999" in html and "Day 7" in html and 'id="form"' in html and 'class="skip"' in html and "Websites that" in html)
    check("a. share card: og:title / og:description / og:image (og.jpg, 1200 x 630) + twitter large card + canonical",
          all(x in html for x in ('property="og:title"', 'property="og:description"', 'property="og:image" content="og.jpg"', 'name="twitter:card" content="summary_large_image"', 'rel="canonical"'))
          and jpeg_size(os.path.join(D, "og.jpg")) == (1200, 630), jpeg_size(os.path.join(D, "og.jpg")))
    m = re.search(r'<script type="application/ld\+json" id="ld">(.*?)</script>', html, re.S)
    ld = json.loads(m.group(1)) if m else {}
    check("a. local SEO: LocalBusiness JSON-LD (name, telephone, address with locality / region / country, areaServed, priceRange, three Offers in USD)",
          ld.get("@type") == "LocalBusiness" and ld.get("telephone") and set(ld.get("address", {})) >= {"addressLocality", "addressRegion", "addressCountry"}
          and ld.get("areaServed") and ld.get("priceRange") and len(ld.get("makesOffer", [])) == 3 and all(o["priceCurrency"] == "USD" for o in ld["makesOffer"]), ld)
    check("a. no backend: the form has no action / method, the script never POSTs or sends; it only builds a mailto: or sms: link",
          not re.search(r'<form[^>]*(action|method)=', html) and not re.search(r"method:\s*['\"]POST|XMLHttpRequest|sendBeacon|WebSocket", js + city)
          and "'mailto:'" in js and "'sms:'" in js and "location.href = href" in js)
    check("a. stores nothing: no localStorage / sessionStorage / cookies / indexedDB", not re.search(r"localStorage|sessionStorage|document\.cookie|indexedDB", js + city))
    check("a. text only (no innerHTML / insertAdjacentHTML / document.write), fetch only of brand.json",
          not re.search(r"innerHTML|insertAdjacentHTML|document\.write", js + city) and re.findall(r"fetch\('([^']+)'", js) == ["brand.json"])
    check("a. the 3D: three.js from the site (no CDN), loaded by a dynamic import after the page is idle, skipped under reduced motion / data saver / low memory / no WebGL",
          "from '../../jarvis/three.module.min.js'" in city and not re.search(r"https?://", city) and "import('./city.js" in js and "requestIdleCallback" in js
          and all(x in js for x in ("reduced motion", "saveData", "deviceMemory", "no WebGL")))
    check("a. phone-safe 3D: pixel ratio <= 1.75, one InstancedMesh for the filler, sleeps off screen / hidden", "Math.min(window.devicePixelRatio || 1, 1.75)" in city and "InstancedMesh" in city
          and "IntersectionObserver" in city and "document.hidden" in city)


def brand_override(name):
    B = json.load(open(os.path.join(D, "brand.json"), encoding="utf-8"))
    B["name"] = name
    B["offers"][1]["price"] = 1234
    B["email"] = "owner@example.com"
    return json.dumps(B)


INIT = """window.__lt = []; window.__cls = 0; window.__showcaseNoNav = true; try {
 new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__lt.push([Math.round(e.startTime), Math.round(e.duration)]); }).observe({ type: 'longtask', buffered: true });
 new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; }).observe({ type: 'layout-shift', buffered: true }); } catch (e) {}"""


def test_page():
    srv, origin = AK.serve({"/agency/showcase/brand.json": brand_override("Bright Pixel Studio")})
    with AK.browser() as br:
        ctx, p, errs, seen, off = AK.page(br, origin)
        p.add_init_script(INIT)
        p.goto(f"{origin}/agency/showcase/?3d=1")
        p.wait_for_function("window.__showcase && window.__showcase.brand", timeout=30000)
        p.wait_for_timeout(600)
        r = p.evaluate("""() => ({ title: document.title, name: document.querySelector('.brand span').textContent, prices: [...document.querySelectorAll('#offerList .amt')].map((e) => e.textContent),
          ld: JSON.parse(document.querySelector('#ld').textContent), demos: document.querySelectorAll('#demoList a').length, href: document.querySelector('#demoList a').getAttribute('href'),
          week: document.querySelectorAll('#weekList li').length, sel: [...document.querySelectorAll('#offerSel option')].map((o) => o.value) })""")
        check("b. brand.json applied: the name in the header and title, the changed price ($1,234), JSON-LD follows, the plan picker lists the offers",
              r["name"] == "Bright Pixel Studio" and r["title"].startswith("Bright Pixel Studio") and "$1,234" in r["prices"] and r["ld"]["name"] == "Bright Pixel Studio"
              and r["sel"] == ["starter", "growth", "signature", "unsure"] and r["week"] == 6, r)
        check("b. the demo list: one card per demo, each opening ../demos/#<slug>", r["demos"] == 8 and r["href"] == "../demos/#restaurant", r)
        # the contact form
        p.click("#offerList [data-offer=signature]")
        p.fill("input[name=name]", "Ana"); p.fill("input[name=biz]", "Ana's Tacos"); p.select_option("#kindSel", "Restaurant"); p.fill("textarea[name=msg]", "online menu")
        p.click("button[data-via=email]")
        mail = p.evaluate("window.__showcase.form")
        p.click("button[data-via=sms]")
        sms = p.evaluate("window.__showcase.form")
        check("b. the form opens the phone's mail app: mailto:owner@example.com with subject 'Website for Ana's Tacos' and the plan picked on its price card",
              mail.startswith("mailto:owner@example.com?subject=Website%20for%20Ana's%20Tacos") and "3D%20Signature" in mail and "online%20menu" in mail, mail)
        check("b. ... or the messages app: sms: with the same message in body=", sms.startswith("sms:+15550100") and "body=Website%20for" in sms, sms)
        p.fill("input[name=name]", "")
        p.click("button[data-via=email]")
        check("b. a missing name is asked for in plain words, nothing opens", "Please add your name" in p.evaluate("document.querySelector('#formNote').textContent"))
        t = AK.taps(p)
        check("b. every tap target >= 44 x 44 px, no sideways scroll", not t and AK.no_sideways(p), t[:4])
        p.wait_for_function("window.__showcase.three === 'live' || window.__showcase.three === 'failed' || window.__showcase.three === 'still'", timeout=60000)
        s3 = p.evaluate("window.__showcase")
        check("b. the 3D city came up after the page (state live), with a canvas and floating demo names that open demos",
              s3["three"] == "live" and p.locator("#stage canvas").count() == 1 and p.evaluate("[...document.querySelectorAll('#tags a')].every((a) => a.getAttribute('href').startsWith('../demos/#'))"), s3)
        check("b. no console error, nothing off the site", not errs and not off, (errs[:3], off[:3]))
        ctx.close()

        # speed at 4x CPU (phone profile), the 3D on
        ctx, p, errs, seen, off = AK.page(br, origin)
        p.add_init_script(INIT)
        cdp = ctx.new_cdp_session(p); cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
        p.goto(f"{origin}/agency/showcase/?3d=1")
        p.wait_for_timeout(9000)
        perf = p.evaluate("() => ({ fcp: Math.round((performance.getEntriesByName('first-contentful-paint')[0] || {}).startTime || 0), cls: window.__cls, lt: window.__lt, three: window.__showcase.three })")
        check("c. 4x CPU: first contentful paint %d ms < 1500, layout shift %.3f < 0.05 (3D %s)" % (perf["fcp"], perf["cls"], perf["three"]),
              0 < perf["fcp"] < 1500 * AK_mult() and perf["cls"] < 0.05, perf)
        ctx.close()

        # reduced motion: the still skyline, no three.js
        ctx, p, errs, seen, off = AK.page(br, origin, reduced=True)
        p.goto(f"{origin}/agency/showcase/")
        p.wait_for_timeout(2500)
        s = p.evaluate("window.__showcase")
        check("c. reduced motion: no 3D (state still, why 'reduced motion'), the drawn skyline stays, three.js never fetched",
              s["three"] == "still" and s["why"] == "reduced motion" and p.locator("#stage svg.sky").count() == 1 and not any("three.module" in u for u in seen), s)
        ctx.close()
    srv.shutdown()


def AK_mult():
    try:
        sys.path.insert(0, os.path.join(AK.ROOT, "tests"))
        import browser_kit as BK
        return max(1.0, BK.multiplier())
    except Exception:
        return 1.0


def main():
    test_static()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()


if __name__ == "__main__":
    sys.exit(main())
