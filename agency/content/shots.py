"""Screenshots for docs/shots/agency_content/ (and a look at the demo month): the contact sheet and the monthly report at
390 x 844 (phone) and 1440 x 900 (desktop), the client preview, and sample post images.

    flock -w 2400 /tmp/olympus_browser.lock python -X utf8 agency/content/shots.py [--out docs/shots/agency_content] [--keep DIR]

Uses the fictional demo client (fixtures/clients_demo.json, fade-co) and the demo form export; the website check is a fixed
'up, 412 ms' so the picture does not depend on the network. Needs Playwright + Chromium (the cloud machine has both).
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from agency.content import client_report as C  # noqa: E402
from agency.content import designs as D  # noqa: E402
from agency.content import make_posts as M  # noqa: E402
from agency.content import render as R  # noqa: E402

FIX = os.path.join(ROOT, "agency", "content", "fixtures")


def build_demo(work: str, renderer) -> dict:
    clients = {c["id"]: c for c in M.load_clients(os.path.join(FIX, "clients_demo.json"))}
    client = clients["fade-co"]
    plan = M.plan_month(client, 2026, 12, 16)
    month_dir = os.path.join(work, "fade-co", "2026-12")
    M.write_outputs(plan, month_dir, render=True, renderer=renderer, quiet=True)
    nov = M.plan_month(client, 2026, 11, 16)
    leads = C.read_leads(os.path.join(FIX, "leads_demo.csv"), 2026, 11)
    site = {"checked": True, "up": True, "status": 200, "ms": 412, "https": True, "url": "https://fadeandco.example", "at": "2026-12-01T09:05"}
    rep = C.build_report(client, 2026, 11, leads, site, 47, 41, 4.9, ["Added the holiday hours banner to the website"],
                         ["New photos for the gallery page"], nov, plan, {"name": "Main Street Web Co.", "email": "hello@mainstreet.example",
                                                                          "phone": "(512) 555-0100", "site": ""})
    rep_dir = os.path.join(work, "report")
    os.makedirs(rep_dir, exist_ok=True)
    with open(os.path.join(rep_dir, "report.html"), "w", encoding="utf-8") as fh:
        fh.write(rep["html"])
    with open(os.path.join(rep_dir, "email.txt"), "w", encoding="utf-8") as fh:
        fh.write(rep["email"])
    renderer.pdf(rep["html"], os.path.join(rep_dir, "report.pdf"))
    return {"plan": plan, "month_dir": month_dir, "report": os.path.join(rep_dir, "report.html")}


def shoot(br, url: str, out: str, w: int, h: int, full: bool = False, scroll_to: str | None = None, scale: int = 1):
    ctx = br.new_context(viewport={"width": w, "height": h}, device_scale_factor=scale)
    ctx.route("**/*", lambda route: route.abort() if route.request.url.startswith(("http:", "https:")) else route.continue_())
    pg = ctx.new_page()
    pg.goto(url, wait_until="load")
    pg.wait_for_function("document.documentElement.getAttribute('data-ready') === '1'", timeout=30000)
    pg.wait_for_function("Array.from(document.images).every(i => i.complete)", timeout=30000)
    if scroll_to:
        pg.evaluate(f"document.querySelector({scroll_to!r}).scrollIntoView({{block: 'start'}})")
        pg.wait_for_timeout(200)
    pg.screenshot(path=out, full_page=full)
    ctx.close()
    print("  shot", os.path.relpath(out, ROOT), flush=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "shots", "agency_content"))
    ap.add_argument("--keep", help="also keep the whole demo (posts, sheet, report) in this folder")
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    work = tempfile.mkdtemp(prefix="agency_shots_")
    try:
        with R.Renderer(prefer="playwright") as r:
            if r.kind != "playwright":
                print("needs Playwright + Chromium", file=sys.stderr)
                return 2
            demo = build_demo(work, r)
            br = r._br
            sheet = "file://" + os.path.join(demo["month_dir"], "contact_sheet.html")
            report = "file://" + demo["report"]
            shoot(br, sheet, os.path.join(a.out, "contact_sheet_390.png"), 390, 844, scale=2)
            shoot(br, sheet, os.path.join(a.out, "contact_sheet_390_posts.png"), 390, 844, scroll_to="#p02", scale=2)
            shoot(br, sheet, os.path.join(a.out, "contact_sheet_desktop.png"), 1440, 900)
            shoot(br, sheet, os.path.join(a.out, "contact_sheet_desktop_posts.png"), 1440, 900, scroll_to=".grid")
            shoot(br, report, os.path.join(a.out, "report_390.png"), 390, 844, scale=2)
            shoot(br, report, os.path.join(a.out, "report_390_full.png"), 390, 844, full=True, scale=2)
            shoot(br, report, os.path.join(a.out, "report_desktop.png"), 1440, 900, full=True)
            from PIL import Image
            prev = Image.open(os.path.join(demo["month_dir"], "contact_sheet.png")).convert("RGB")
            prev.resize((1000, round(prev.height * 1000 / prev.width)), Image.LANCZOS).save(os.path.join(a.out, "client_preview.png"), optimize=True)
            print("  made client_preview.png", flush=True)
            # sample posts: one per design, squares in a grid + four stories (made smaller for the docs)
            seen, sq, st = set(), [], []
            for p in demo["plan"]["posts"]:
                if p["layout"] not in seen:
                    seen.add(p["layout"])
                    sq.append(os.path.join(demo["month_dir"], p["square"]))
                    if len(st) < 4:
                        st.append(os.path.join(demo["month_dir"], p["story"]))
            for name, files, tw, th, cols in (("posts_square_sample.png", sq[:9], 360, 360, 3), ("posts_story_sample.png", st, 270, 480, 4)):
                rows = (len(files) + cols - 1) // cols
                g = Image.new("RGB", (cols * tw + (cols + 1) * 12, rows * th + (rows + 1) * 12), (236, 233, 226))
                for i, f in enumerate(files):
                    im = Image.open(f).convert("RGB").resize((tw, th), Image.LANCZOS)
                    g.paste(im, (12 + (i % cols) * (tw + 12), 12 + (i // cols) * (th + 12)))
                g.save(os.path.join(a.out, name), optimize=True)
                print("  made", name, flush=True)
            if a.keep:
                if os.path.exists(a.keep):
                    shutil.rmtree(a.keep)
                shutil.copytree(work, a.keep)
                print("  demo kept in", a.keep)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
