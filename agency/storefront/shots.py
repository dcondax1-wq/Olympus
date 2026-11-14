#!/usr/bin/env python3
"""Pictures for the storefront. Run by Claude / the lead after the demo sites change (never needed for a config edit).

    flock -w 2400 /tmp/olympus_browser.lock python agency/storefront/shots.py              both parts
    flock -w 2400 /tmp/olympus_browser.lock python agency/storefront/shots.py --examples   the pictures the site shows
    flock -w 2400 /tmp/olympus_browser.lock python agency/storefront/shots.py --review     docs/shots/agency_storefront/*.png

--examples: each demo site on a phone (390 x 844) and a desktop (1440 x 900), the matching made-up "before" page on a phone,
            and one share picture per colour preset -> src/img/ex/*.webp, src/img/og-*.png.
            The demos are shot in screenshot mode (?shot: no ribbon, a fixed Friday-evening clock), so no picture shows
            the agency name and a new name never needs new pictures.
--review:   every storefront page at 390 x 844 and 1440 wide, the other two presets, the three demos, for a human look.
Needs Playwright + Chromium and Pillow (WebP). Standard library otherwise.
"""
from __future__ import annotations

import argparse
import functools
import http.server
import io
import shutil
import sys
import tempfile
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
import build  # noqa: E402

IMG = HERE / "src" / "img"
EX = IMG / "ex"
REVIEW = ROOT / "docs" / "shots" / "agency_storefront"
PHONE = {"viewport": {"width": 390, "height": 844}, "device_scale_factor": 2, "is_mobile": True, "has_touch": True}
DESK = {"viewport": {"width": 1440, "height": 900}, "device_scale_factor": 1}


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve(folder: Path):
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(folder)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


def launch(pw):
    try:
        from tests import browser_kit as BK
        return BK.launch(pw)
    except Exception:  # noqa: BLE001  (no repo test kit: the plain Playwright Chromium)
        return pw.chromium.launch()


def settle(page):
    """every lazy picture loaded and the fonts in, so a full-page shot has no holes"""
    page.evaluate("""() => { document.querySelectorAll('img[loading=lazy]').forEach(i => { i.loading = 'eager'; }); }""")
    page.wait_for_function("() => Array.from(document.images).every(i => i.complete)", timeout=20000)
    page.evaluate("() => document.fonts ? document.fonts.ready.then(() => true) : true")
    page.wait_for_timeout(150)


def webp(png: bytes, size: tuple, out: Path, q: int = 74) -> int:
    from PIL import Image
    im = Image.open(io.BytesIO(png)).convert("RGB").resize(size, Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=q, method=6)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(buf.getvalue())
    return len(buf.getvalue())


def png_small(png: bytes, out: Path) -> int:
    from PIL import Image
    im = Image.open(io.BytesIO(png)).convert("RGB")
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(buf.getvalue())
    return len(buf.getvalue())


def og_html(preset: str) -> str:
    """the share picture: the three demo phones on the preset's colours (the freshly made pictures, inlined)"""
    import base64
    pal = build.css_presets()[preset]
    phones = "".join(f'<figure class="p p{i}"><img src="data:image/webp;base64,'
                     f'{base64.b64encode((EX / f"{t}-after.webp").read_bytes()).decode()}"></figure>'
                     for i, t in enumerate(("plumber", "barber", "restaurant")))
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0;width:1200px;height:630px;overflow:hidden}}
body{{background:radial-gradient(900px 520px at 80% 0%, {pal['--brand-soft']}, transparent 62%), {pal['--bg']};position:relative}}
body::before{{content:"";position:absolute;inset:0;background-image:radial-gradient({pal['--line-2']} 1.2px, transparent 1.5px);background-size:26px 26px;opacity:.7}}
.blob{{position:absolute;width:720px;height:720px;right:-120px;top:-60px;border-radius:50%;background:{pal['--brand']};opacity:.14;filter:blur(2px)}}
.p{{position:absolute;margin:0;width:250px;border-radius:38px;background:#0D0E11;padding:9px;box-shadow:0 40px 70px -30px rgba(0,0,0,.55)}}
.p img{{display:block;width:100%;border-radius:30px}}
.p0{{left:290px;top:120px;transform:rotate(-8deg)}}
.p1{{left:475px;top:58px;z-index:2;width:270px}}
.p2{{left:680px;top:120px;transform:rotate(8deg)}}
.bar{{position:absolute;left:0;right:0;bottom:0;height:16px;background:{pal['--brand']}}}
</style></head><body><div class="blob"></div>{phones}<div class="bar"></div></body></html>"""


def shoot_examples(br, url: str) -> list[str]:
    done = []
    for t in build.TRADES:
        ctx = br.new_context(**PHONE, reduced_motion="reduce")
        p = ctx.new_page()
        p.goto(f"{url}/examples/{t}/index.html?shot", wait_until="load")
        settle(p)
        n = webp(p.screenshot(), (540, 1169), EX / f"{t}-after.webp")
        done.append(f"img/ex/{t}-after.webp {n // 1024} KB")
        p.goto(f"{url}/_mockups/before-{t}.html", wait_until="load")
        settle(p)
        n = webp(p.screenshot(), (540, 1169), EX / f"{t}-before.webp", q=70)
        done.append(f"img/ex/{t}-before.webp {n // 1024} KB")
        ctx.close()
        ctx = br.new_context(**DESK, reduced_motion="reduce")
        p = ctx.new_page()
        p.goto(f"{url}/examples/{t}/index.html?shot", wait_until="load")
        settle(p)
        n = webp(p.screenshot(), (960, 600), EX / f"{t}-desktop.webp")
        done.append(f"img/ex/{t}-desktop.webp {n // 1024} KB")
        ctx.close()
    for preset in build.PRESETS:
        ctx = br.new_context(viewport={"width": 1200, "height": 630}, device_scale_factor=1)
        p = ctx.new_page()
        p.set_content(og_html(preset), wait_until="load")
        settle(p)
        n = png_small(p.screenshot(), IMG / f"og-{preset}.png")
        done.append(f"img/og-{preset}.png {n // 1024} KB")
        ctx.close()
    return done


def answer_quiz(p):
    p.fill("#g-site", "joesplumbing.com")
    p.click("#g-start")
    picks = ["yes", "no", "yes", "unsure", "no", "yes", "yes", "no", "no", "yes"]
    for fs, v in zip(p.query_selector_all("fieldset.q"), picks):
        fs.query_selector(f'input[value="{v}"]').evaluate("el => el.click()")
    p.wait_for_timeout(200)


def shoot_review(br, url: str) -> list[str]:
    REVIEW.mkdir(parents=True, exist_ok=True)
    done = []
    pages = ["index", "work", "pricing", "grader", "contact", "faq", "privacy"]

    def snap(ctx_kw, path, name, full=True, prep=None):
        ctx = br.new_context(**ctx_kw, reduced_motion="reduce")
        p = ctx.new_page()
        p.goto(url + path, wait_until="load")
        settle(p)
        if prep:
            prep(p)
            settle(p)
        n = png_small(p.screenshot(full_page=full), REVIEW / name)
        done.append(f"{name} {n // 1024} KB")
        ctx.close()

    phone1 = dict(PHONE, device_scale_factor=1)
    for pg in pages:
        prep = answer_quiz if pg == "grader" else None
        snap(phone1, f"/{pg}.html", f"phone-{pg}.png", True, prep)
        snap(DESK, f"/{pg}.html", f"desktop-{pg}.png", True, prep)
    snap(PHONE, "/index.html", "phone-home-top.png", False)
    snap(DESK, "/index.html", "desktop-home-top.png", False)
    snap(PHONE, "/index.html", "phone-menu-open.png", False, lambda p: p.click(".menu-btn"))
    for preset in ("ocean", "forest"):
        snap(PHONE, f"/index.html?preset={preset}", f"phone-home-{preset}.png", False)
        snap(DESK, f"/index.html?preset={preset}", f"desktop-home-{preset}.png", False)
    for t in build.TRADES:
        snap(phone1, f"/examples/{t}/index.html", f"phone-demo-{t}.png", True)
        snap(DESK, f"/examples/{t}/index.html", f"desktop-demo-{t}.png", False)
    return done


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Storefront pictures (example screenshots, share pictures, review shots).")
    ap.add_argument("--examples", action="store_true")
    ap.add_argument("--review", action="store_true")
    args = ap.parse_args(argv)
    both = not (args.examples or args.review)
    from playwright.sync_api import sync_playwright
    tmp = Path(tempfile.mkdtemp(prefix="storefront-shots-"))
    try:
        with sync_playwright() as pw:
            br = launch(pw)
            if both or args.examples:
                build.build(tmp / "site")
                shutil.copytree(HERE / "mockups", tmp / "site" / "_mockups")
                httpd, url = serve(tmp / "site")
                for line in shoot_examples(br, url):
                    print("  " + line)
                httpd.shutdown()
            if both or args.review:
                build.build(tmp / "site2")
                httpd, url = serve(tmp / "site2")
                for line in shoot_review(br, url):
                    print("  " + line)
                httpd.shutdown()
            br.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
