"""Build the demo pages for both add-ons on the fake clients in fixtures/ (committed under agency/upsells/demo/).

    python agency/upsells/build_demos.py           rebuild agency/upsells/demo/
    python agency/upsells/build_demos.py --check   exit 1 when the committed demo differs from a fresh build

Each demo is a small fake business homepage with the real install steps applied to it: make_chat.py --site adds the chat
(script tag + hidden Netlify form), make_review.py --site adds /review/. The kit/ folder holds what the owner would print or
paste (cards, QR, request templates, the answer preview). Everything is fake: 555 numbers, .example domains, DEMO labels.
"""
from __future__ import annotations

import filecmp
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from agency.upsells import common as K  # noqa: E402
from agency.upsells import make_chat, make_review  # noqa: E402

DEMO = os.path.join(HERE, "demo")
FIXTURES = [("harborline", "demo_barber.json", "Fresh cuts, sharp fades, hot towel shaves.", "Book a chair"),
            ("blueline", "demo_plumber.json", "Plumbing and AC repair, done right the first time.", "Book a visit"),
            ("casamarina", "demo_restaurant.json", "Coastal Mexican kitchen on the harbor.", "Reserve a table")]


def homepage(client: dict, tagline: str, cta: str) -> str:
    chat = client.get("chat") or {}
    pal = K.palette(chat.get("brand_color") or "#0f766e")
    e = K.esc
    week = K.week_text(K.parse_hours(chat["hours"]))
    services = "".join(f"<li><span>{e(s['name'])}</span><b>{e(s['price'])}</b></li>" for s in (chat.get("services") or [])[:6])
    services_block = f'<section><h2>Services &amp; prices</h2><ul class="svc">{services}</ul></section>' if services else \
        f'<section><h2>Menu</h2><p>Seasonal coastal Mexican: tacos, ceviche, grilled fish, margaritas. <a href="#">See the full menu</a></p></section>'
    where = e(chat.get("address") or ("Serving " + ((chat.get("area") or {}).get("text") or client.get("city", ""))))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex">
<title>{e(client['name'])} · {e(client.get('city', ''))} (demo)</title>
<style>
:root{{--f:{pal['fill']};--i:{pal['ink']};--a:{pal['accent']};--s:{pal['soft']}}}
*{{box-sizing:border-box}}body{{margin:0;font:17px/1.55 Georgia,"Times New Roman",serif;color:#1f2430;background:#fbfaf7}}
.demo{{background:#111827;color:#fff;font:600 12px/1.4 system-ui,sans-serif;text-align:center;padding:6px 10px;letter-spacing:.02em}}
header{{background:var(--f);color:var(--i);padding:22px 20px 34px}}
.brand{{font:800 21px/1.2 system-ui,-apple-system,sans-serif}}
.hero h1{{font-size:34px;line-height:1.1;margin:22px 0 10px}}
.hero p{{margin:0 0 18px;opacity:.92;font-size:18px}}
.cta{{display:inline-block;background:var(--i);color:var(--f);font:700 16px system-ui,sans-serif;padding:13px 20px;border-radius:12px;text-decoration:none;margin:0 8px 8px 0}}
.cta.ghost{{background:transparent;color:var(--i);border:2px solid var(--i)}}
main{{max-width:760px;margin:0 auto;padding:8px 20px 120px}}
section{{margin:28px 0}}h2{{font:800 20px/1.2 system-ui,sans-serif;margin:0 0 12px;color:var(--a)}}
.svc{{list-style:none;margin:0;padding:0;border-top:1px solid #e5e2da}}.svc li{{display:flex;justify-content:space-between;gap:14px;padding:11px 0;border-bottom:1px solid #e5e2da}}
.hours li{{margin:2px 0}}.hours{{padding-left:18px}}
.rev{{background:var(--s);border-radius:16px;padding:18px}}.rev a{{color:var(--a);font-weight:700}}
footer{{text-align:center;color:#6b7280;font:14px system-ui,sans-serif;padding:20px}}
</style>
</head>
<body>
<div class="demo">DEMO SITE: a fake business made to show the agency's add-ons. Nothing here is real.</div>
<header>
  <div class="brand">{e(client['name'])}</div>
  <div class="hero"><h1>{e(tagline)}</h1><p>{e(client.get('city', ''))} · <a href="tel:{e(K.tel(client['phone']))}" style="color:inherit">{e(client['phone'])}</a></p>
  <a class="cta" href="{e(chat.get('booking_url') or '#')}">{e(cta)}</a><a class="cta ghost" href="tel:{e(K.tel(client['phone']))}">Call us</a></div>
</header>
<main>
  {services_block}
  <section><h2>Hours</h2><ul class="hours">{''.join(f'<li>{e(x)}</li>' for x in week)}</ul></section>
  <section><h2>Find us</h2><p>{where}</p></section>
  <section class="rev"><h2>Been here?</h2><p>Tell us how we did: <a href="review/">leave a review</a>. Good or bad, we read every one.</p></section>
</main>
<footer>© {e(client['name'])} (demo) · Questions? Tap the chat bubble.</footer>
</body>
</html>
"""


def hub() -> str:
    rows = "".join(f'<li><a href="{slug}/">{K.esc(K.load_client(os.path.join(HERE, "fixtures", fx))["name"])}</a> · '
                   f'<a href="{slug}/review/">review page</a> · <a href="{slug}/kit/print/card-a6.html">A6 card</a> · '
                   f'<a href="{slug}/kit/print/card-business.html">business card</a> · <a href="{slug}/kit/chat-demo-{slug}-preview.html">chat answers</a></li>'
                   for slug, fx, _, _ in FIXTURES)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex">
<title>Monthly add-ons demo</title>
<style>body{{font:16px/1.6 system-ui,-apple-system,sans-serif;max-width:720px;margin:0 auto;padding:20px;color:#1f2430}}li{{margin:8px 0}}a{{color:#0f5f58}}</style></head>
<body><h1>Monthly add-ons: demo</h1>
<p>Two add-ons for the sites we build, on three fake businesses: the <b>Front-desk chat</b> (the bubble in the corner) and the
<b>Review booster</b> (a QR card that opens a review page). Fake data only.</p>
<ul>{rows}</ul></body></html>
"""


def build(dest: str) -> None:
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    os.makedirs(dest)
    for slug, fx, tagline, cta in FIXTURES:
        path = os.path.join(HERE, "fixtures", fx)
        client = K.load_client(path)
        site = os.path.join(dest, slug)
        K.write(os.path.join(site, "index.html"), homepage(client, tagline, cta))
        make_chat.build(path, out=os.path.join(site, "kit"), site=site, quiet=True)
        make_review.build(path, out=os.path.join(site, "kit"), site=site, quiet=True)
        shutil.rmtree(os.path.join(site, "kit", "review"))      # the same page is already the site's /review/
    K.write(os.path.join(dest, "index.html"), hub())


def same_tree(a: str, b: str) -> list:
    diff = []
    cmp = filecmp.dircmp(a, b)
    diff += [os.path.join(a, x) for x in cmp.left_only + cmp.right_only + cmp.diff_files + cmp.funny_files]
    for sub in cmp.common_dirs:
        diff += same_tree(os.path.join(a, sub), os.path.join(b, sub))
    return diff


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--check" in argv:
        with tempfile.TemporaryDirectory() as tmp:
            fresh = os.path.join(tmp, "demo")
            build(fresh)
            diff = same_tree(DEMO, fresh) if os.path.isdir(DEMO) else ["(no demo folder)"]
        print("demo is " + ("up to date" if not diff else "STALE: " + ", ".join(os.path.relpath(d, DEMO) for d in diff[:8])))
        return 0 if not diff else 1
    build(DEMO)
    print("demo written to", DEMO)
    return 0


if __name__ == "__main__":
    sys.exit(main())
