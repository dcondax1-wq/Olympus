"""Build the 30-DAY SOCIAL MEDIA KIT FOR LOCAL BUSINESSES (team D2, 2026-11-14): an offline Post Maker (30 editable designs, 8 looks,
3 sizes, photo and logo upload, PNG / zip download), 150 captions, the 30-day plan (PDF + CSV) and a how-to guide.

    python -m money_machines.products.build_social_kit --zip    # the owner: pack the committed files (plain Python)
                                                                 #   -> money_machines/out/products/local_social_media_kit_v1.0.zip
    python -m money_machines.products.build_social_kit          # rebuild everything (Chromium: designs, PDFs, covers; run under the lock)

Sources: social_kit/src/post_maker.html (the app + the canvas designs) and social_kit_data.py (looks, designs, the 30 days, the caption
bank). The pictures in the plan, the contact sheet and the covers are drawn by the app's own PostKit.draw, so they match what buyers get.
"""
from __future__ import annotations

import argparse
import base64
import csv
import io
import json
import os
import re
import sys

from money_machines.products import kit as K
from money_machines.products import social_kit_data as D

HERE = os.path.dirname(os.path.abspath(__file__))
PROD = os.path.join(HERE, "social_kit")
SRC, BUYER, SHOP = (os.path.join(PROD, x) for x in ("src", "buyer", "shop"))
VERSION = "1.0"
TOP = "30-Day-Local-Social-Media-Kit"
ZIP = f"local_social_media_kit_v{VERSION}.zip"
APP = os.path.join(BUYER, "Post_Maker.html")
DEMO_BRAND = {"name": "Your Business", "town": "Your Town", "contact": "(555) 010-0100", "palette": "ivory", "fonts": "classic", "logo": "", "custom": None}
PLAIN = {"{name}": "[Your business]", "{town}": "[Your town]", "{contact}": "[your phone or website]"}


def plain(t: str) -> str:
    for k, v in PLAIN.items():
        t = t.replace(k, v)
    return t


def kit_json() -> dict:
    return {"version": VERSION, "palettes": D.PALETTES, "fonts": D.FONTS, "layouts": D.LAYOUTS, "days": D.DAYS, "bank": D.bank()}


def app_html() -> str:
    src = open(os.path.join(SRC, "post_maker.html"), encoding="utf-8").read()
    blob = json.dumps(kit_json(), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    out, n = re.subn(r"/\*KIT\*/\{\}/\*END\*/", lambda m: "/*KIT*/" + blob + "/*END*/", src)
    if n != 1:
        raise SystemExit("post_maker.html: the /*KIT*/{}/*END*/ marker is missing")
    return out


# ------------------------------------------------------------------------------------------------ text files
LICENSE = f"""30-DAY LOCAL SOCIAL MEDIA KIT v{VERSION}: LICENCE

What you may do
- Use the Post Maker, the designs and the captions for your own business, as often as you like.
- Make posts for your clients' businesses with them (for example as a social media helper or agency). The finished posts
  belong to you or your client.
- Change anything: words, colours, designs.

What you may not do
- Resell, share, upload or give away the Post Maker, the designs or the caption bank themselves, edited or not, as templates
  or as part of a template kit.

Good to know
- The designs are original. Photos and logos you add are your responsibility: use your own or ones you have permission to use.
- Only post true claims and real reviews. Disclose paid partnerships and gifted products clearly (for example "Ad" or "#ad"
  at the start of the caption).
- Provided as is, without warranty. If something does not work as described, message the seller through the shop where you
  bought this within 14 days and we will help you or refund you.
"""

README = f"""30-DAY LOCAL SOCIAL MEDIA KIT v{VERSION}: QUICK START

1. Open Post_Maker.html in your web browser (double-click it). It works offline, on a computer, tablet or phone.
2. Type your business name, town and contact line, pick your colours and fonts, and add your logo if you have one.
3. Click a day, change the words if you like, add a photo where there is a photo frame, and press "Download this post"
   (or "Download all 30" for a zip with every post and a captions sheet).
4. Copy the caption under the post, paste it into your post, and publish or schedule it.

Also inside
  30_Day_Plan.pdf / .csv   the plan: what to post each day, the caption, alt text and a tip
  Caption_Bank.pdf / .txt  150 captions in 13 groups (the Post Maker's "Caption bank" tab fills in your name for you)
  All_30_Designs.jpg       all 30 designs at a glance
  How_to_use.pdf           the guide: making posts, posting and scheduling, the rules that keep you safe

Sizes: portrait 4:5 (1080 x 1350, the most space in a feed), 1:1 (1080 x 1080) and story (1080 x 1920).
"Save my work" keeps everything (text, logo, photos) in one file you can open on another computer with "Open saved work".
Nothing you type or add leaves your computer: the Post Maker has no server and loads nothing from the internet.
"""


def plan_csv() -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(["Day", "Theme", "Design", "Headline on the image", "Caption", "Alt text", "Tip"])
    for i, d in enumerate(D.DAYS, 1):
        w.writerow([i, d["theme"], D.LAYOUTS[d["layout"]]["label"], plain(d["headline"]), plain(d["caption"]), plain(d["alt"]), d["tip"]])
    return "﻿" + buf.getvalue()


def bank_txt() -> str:
    lines = [f"CAPTION BANK v{VERSION}: 150 captions for a local business", "",
             "Replace the words in [brackets] with your own. Use at most 3 to 5 hashtags a post.",
             "Only real reviews, true claims and clearly disclosed ads (\"Ad\" or \"#ad\" at the start of a paid post).", ""]
    n = 0
    groups = {}
    for b in D.bank():
        groups.setdefault(b["cat"], []).append(b["text"])
    for cat, items in groups.items():
        lines += ["=" * 72, cat.upper(), "=" * 72, ""]
        for t in items:
            n += 1
            lines += [f"{n}. {plain(t)}", ""]
    return "\n".join(lines)


def page_css(size: str = "Letter") -> str:
    return f"""@page{{size:{size};margin:14mm 15mm 15mm}}
body{{font-family:Inter,'Segoe UI',Arial,sans-serif;color:#1d1a16;font-size:10.4pt;line-height:1.48;margin:0}}
h1{{font-family:{K.SERIF};font-size:26pt;line-height:1.05;margin:0 0 6pt}}
h2{{font-family:{K.SERIF};font-size:15pt;margin:14pt 0 6pt;padding-bottom:3pt;border-bottom:2px solid #c8a24a;break-after:avoid}}
h3{{font-size:11pt;margin:9pt 0 3pt;break-after:avoid}}p{{margin:0 0 7pt}}ul,ol{{margin:0 0 8pt;padding-left:17pt}}li{{margin:0 0 3pt}}
.sub{{color:#5a5145;font-size:12pt;margin-bottom:12pt}}.small{{color:#6b6256;font-size:8.8pt}}
.box{{background:#f6f2ea;border-radius:8pt;padding:8pt 11pt;margin:8pt 0;break-inside:avoid}}.pb{{break-before:page}}
table{{border-collapse:collapse;width:100%;font-size:9.4pt}}td,th{{border-bottom:1px solid #ddd5c6;padding:4pt 5pt;text-align:left;vertical-align:top}}th{{background:#f1ece2}}"""


def plan_html(thumbs: list) -> str:
    cal = "".join(f'<div class="c"><b>{i}</b><span>{d["theme"]}</span><i>{D.LAYOUTS[d["layout"]]["label"]}</i></div>' for i, d in enumerate(D.DAYS, 1))
    days = []
    for i, d in enumerate(D.DAYS, 1):
        img = f'<img src="{thumbs[i - 1]}" alt="">' if thumbs else ""
        cap = plain(d["caption"]).replace("\n", "<br>")
        days.append(f'<div class="d">{img}<div><h3>Day {i}: {d["theme"]}</h3><p class="meta">Design: {D.LAYOUTS[d["layout"]]["label"]}</p>'
                    f'<p>{cap}</p><p class="meta"><b>Alt text:</b> {plain(d["alt"])}</p><p class="meta"><b>Tip:</b> {d["tip"]}</p>'
                    + (f'<p class="rule">{d["rule"]}</p>' if d["rule"] else "") + "</div></div>")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><style>{page_css()}
.cal{{display:grid;grid-template-columns:repeat(6,1fr);gap:5pt;margin:8pt 0 12pt}}
.c{{border:1px solid #ddd5c6;border-radius:6pt;padding:5pt 6pt;min-height:52pt;background:#fffdf9}}.c b{{display:block;font-family:{K.SERIF};font-size:13pt;color:#94661f}}
.c span{{display:block;font-weight:700;font-size:8.6pt;line-height:1.2}}.c i{{display:block;font-style:normal;color:#6b6256;font-size:7.4pt;margin-top:2pt}}
.d{{display:grid;grid-template-columns:96pt 1fr;gap:11pt;padding:9pt 0;border-bottom:1px solid #e6dfd2;break-inside:avoid}}
.d img{{width:96pt;border-radius:5pt;border:1px solid #ddd5c6}}.d h3{{margin-top:0}}.meta{{color:#5a5145;font-size:9pt;margin-bottom:4pt}}
.rule{{font-size:8.8pt;background:#fdf1e7;border-left:3pt solid #9a3412;padding:3pt 6pt;border-radius:3pt}}</style></head><body>
<h1>The 30-Day Plan</h1><p class="sub">One post a day for 30 days: what to post, the caption and a tip. Start any day of the week.</p>
<div class="cal">{cal}</div>
<div class="box"><b>How to use it:</b> open the Post Maker, set your name and colours once, then make each day's picture. Copy the caption
from the Post Maker (it fills in your business name) or from this plan, change the words in [brackets], and post or schedule it.
Short on time? Make a week of posts in one sitting and schedule them with your platform's free scheduler.</div>
<h2 class="pb">Day by day</h2>{''.join(days)}
<p class="small" style="margin-top:12pt">Hashtags: use 3 to 5 that fit (your town, your trade). Paid partnerships and gifted products must be disclosed at the start
of the caption ("Ad" or "#ad"). Real reviews only. No result or follower numbers are promised: posting regularly is a habit, not a guarantee.</p></body></html>"""


def bank_html() -> str:
    groups = {}
    for b in D.bank():
        groups.setdefault(b["cat"], []).append(b["text"])
    n, parts = 0, []
    for cat, items in groups.items():
        lis = []
        for t in items:
            n += 1
            lis.append(f'<li value="{n}">{plain(t).replace(chr(10), "<br>")}</li>')
        parts.append(f"<h2>{cat} ({len(items)})</h2><ol>{''.join(lis)}</ol>")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><style>{page_css()}
ol{{padding-left:22pt}}li{{margin:0 0 6pt;break-inside:avoid}}</style></head><body>
<h1>Caption Bank</h1><p class="sub">150 captions for a local business, in 13 groups. Replace the words in [brackets].</p>
<div class="box">The Post Maker's <b>Caption bank</b> tab shows the same captions with your business name and town filled in, with a
Copy button. Keep each caption honest: true claims, real reviews, and "Ad" or "#ad" at the start of any paid or gifted post.</div>
{''.join(parts)}</body></html>"""


def howto_html(shot: str) -> str:
    img = f'<img src="{shot}" alt="" style="width:100%;border:1px solid #ddd5c6;border-radius:6pt;margin:4pt 0 8pt">' if shot else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><style>{page_css()}</style></head><body>
<h1>30-Day Local Social Media Kit</h1><p class="sub">How to use it, in 10 minutes. Version {VERSION}.</p>
<h2>1. Set up your look (once)</h2>
<ol><li>Open <b>Post_Maker.html</b> in your web browser (double-click). It works offline.</li>
<li>Type your <b>business name</b>, <b>town</b> and a <b>contact line</b> (phone, website or handle). They appear on every post and in the captions.</li>
<li>Pick one of the 8 <b>colour looks</b> or "Use my own brand colours" (it checks that the text stays readable), and a <b>font</b> style.</li>
<li>Add your <b>logo</b> (optional): it sits in a circle at the bottom of each post. No logo? Your initials are used.</li>
<li>Choose the <b>size</b>: portrait 4:5 for feeds, 1:1 square, or story 9:16.</li></ol>
{img}
<h2>2. Make the 30 posts</h2>
<ol><li>Click a day at the bottom (or use Previous / Next). The big preview shows the post.</li>
<li>Change the words in the <b>Edit</b> panel. Lines in the text box become list items or steps in designs that use them.</li>
<li>Designs with a photo frame say "Add your photo": choose a photo from your device. It stays on your device.</li>
<li>Press <b>Download this post</b> for a PNG, or <b>Download all 30</b> for a zip with every post and a captions sheet (captions.csv).</li>
<li>Your work is saved in this browser as you go. To move it to another computer, press <b>Save my work</b> and open the file there with <b>Open saved work</b>. To start a post again, press "Reset this post".</li></ol>
<h2 class="pb">3. Post or schedule</h2>
<ul><li>Copy the caption from the Post Maker (your name is filled in), change the [bracket] words, and paste it into your post.</li>
<li>Add the <b>alt text</b> (the description for people who use screen readers) in your app's accessibility or alt-text setting.</li>
<li>Most platforms have a free scheduler for business accounts: make a week of posts in one sitting and schedule them.</li>
<li>Reply to comments and messages yourself, the same day if you can. That is the part that builds trust.</li></ul>
<h2>4. The rules that keep you safe</h2>
<ul><li><b>Reviews:</b> share only real reviews, word for word, with the customer's permission. Never write, buy or reward reviews,
and never hide honest negative ones. In the US the FTC's rule on consumer reviews bans fake reviews, with large fines.</li>
<li><b>Ads:</b> if you are paid, given something free or use an affiliate link, say so at the start of the caption ("Ad" or "#ad").</li>
<li><b>Photos and people:</b> use your own photos. Ask before you show a customer, their home or their work.</li>
<li><b>Offers and contests:</b> say what the offer is, who it is for and when it ends. Contest and giveaway rules differ by place and by
platform: read them before you run one.</li>
<li><b>Automation:</b> scheduling is fine; bots that like, follow or comment for you break most platforms' rules.</li></ul>
<h2>5. What to expect</h2>
<p>Posting every day for a month builds a habit and gives people a reason to remember you. It does not guarantee followers, customers
or sales: that depends on your business, your area and how you reply to people. Use the "Your turn" post on day 30 to plan next month.</p>
<h2>6. Licence and help</h2>
<p>Use the kit for your own business and for clients' businesses. Don't resell or share the Post Maker, designs or captions themselves.
Questions? Message me through the shop where you bought this. Full licence: LICENSE.txt.</p>
<p class="small">Made with the help of AI tools; designed, checked and supported by a person. The designs contain no third-party images,
fonts or code. Not legal advice.</p></body></html>"""


# ------------------------------------------------------------------------------------------------ pictures (Chromium)
def open_app(br, w=1400, h=1000, scale=1):
    html = open(APP, encoding="utf-8").read()
    pg = br.new_page(viewport={"width": w, "height": h}, device_scale_factor=scale)
    pg.route("**/*", lambda route: route.fulfill(status=200, content_type="text/html", body=html))
    pg.goto("http://maker.local/")
    pg.wait_for_timeout(600)
    return pg


DRAW_JS = """([i, size, k, brand, palette]) => {
  const s = PostKit.SIZES[size], c = document.createElement('canvas'); c.width = Math.round(s[0] * k); c.height = Math.round(s[1] * k);
  const st = PostKit.defaults(); st.brand = Object.assign(st.brand, brand); st.size = size; st.edits = {};
  if (palette) st.edits[i] = {palette: palette};
  PostKit.draw(c.getContext('2d'), i, st, {photos: {}, logo: null}, k);
  return c.toDataURL('image/jpeg', 0.86);
}"""


def draw(pg, i: int, size="portrait", k=0.5, brand=None, palette=None) -> bytes:
    url = pg.evaluate(DRAW_JS, [i, size, k, brand or DEMO_BRAND, palette])
    return base64.b64decode(url.split(",", 1)[1])


def contact_sheet(pg, path: str) -> str:
    cols, tw, th, gap, pad = 5, 240, 300, 14, 28
    rows = 6
    imgs = [K.b64(draw(pg, i, k=tw / 1080)) for i in range(30)]
    W, H = pad * 2 + cols * tw + (cols - 1) * gap, pad * 2 + 70 + rows * (th + 26) + (rows - 1) * gap
    cells = "".join(f'<div class="t"><img src="{u}"><b>Day {i + 1}</b></div>' for i, u in enumerate(imgs))
    html = f"""<!doctype html><html><head><meta charset="utf-8"><style>*{{margin:0;box-sizing:border-box}}body{{width:{W}px;height:{H}px;background:#efe8db;
font-family:Inter,Arial,sans-serif;padding:{pad}px}}h1{{font:700 34px/1.1 {K.SERIF};color:#1d1a16;margin-bottom:26px}}h1 span{{font:500 18px Inter,Arial;color:#5a5145;margin-left:12px}}
.g{{display:grid;grid-template-columns:repeat({cols},{tw}px);gap:{gap}px}}.t img{{width:{tw}px;height:{th}px;border-radius:8px;display:block;box-shadow:0 4px 12px rgba(0,0,0,.12)}}
.t b{{display:block;font-size:14px;color:#5a5145;margin-top:6px}}</style></head><body><h1>All 30 designs<span>sample text; every word, colour and photo is editable</span></h1><div class="g">{cells}</div></body></html>"""
    from playwright.sync_api import Page  # noqa: F401  (type only)
    br = pg.context.browser
    return K.shoot(br, html, W, H, path, quality=80)


def covers(br, pg, app_shot: bytes) -> list:
    done = []
    # five posts in different looks for the fan; the 30-grid; the same post in four looks
    fan = [(0, "ivory"), (2, "navy"), (9, "blush"), (18, "sage"), (11, "night")]
    fan_u = [K.b64(draw(pg, i, k=0.6, palette=p)) for i, p in fan]
    grid_u = [K.b64(draw(pg, i, k=0.25)) for i in range(30)]
    looks = [K.b64(draw(pg, 27, k=0.42, palette=p)) for p in ("ivory", "tomato", "teal", "slate")]
    app_u = K.b64(app_shot)
    bg, ink, soft, acc = "#f6f2ea", "#1d1a16", "#5a5145", "#94661f"
    for name, w, h in K.COVERS:
        sq, k, n = w == h, w / 1280, name.split("_")[1][0]
        css = K.cover_css(w, h, bg=bg, ink=ink, soft=soft, accent=acc) + f"""
.pad{{position:absolute;inset:0;padding:{int(60 * k)}px}}.kick{{font-size:{int(21 * k)}px;padding:{int(7 * k)}px {int(18 * k)}px;margin-bottom:{int(22 * k)}px}}
h1{{font-size:{int((76 if sq else 56) * k)}px}}.lead{{font-size:{int((30 if sq else 24) * k)}px;line-height:1.35;margin-top:{int(20 * k)}px;color:{soft}}}
ul.checks li{{font-size:{int((28 if sq else 22) * k)}px;margin:{int(11 * k)}px 0}}
.foot{{position:absolute;left:{int(60 * k)}px;bottom:{int(26 * k)}px;font-size:{int((19 if sq else 16) * k)}px;color:#7a6f60}}
.post{{position:absolute;border-radius:{int(14 * k)}px;box-shadow:0 {int(20 * k)}px {int(44 * k)}px rgba(0,0,0,.25)}}"""
        if n == "1":
            text = (f'<span class="chip kick">30 designs + 150 captions</span><h1>30-Day Social Media Kit for Local Businesses</h1>'
                    f'<div class="rule" style="margin-top:{int(22 * k)}px"></div><p class="lead">A month of posts in an afternoon: your name, your colours, your photos.</p>'
                    f'<ul class="checks" style="margin-top:{int(16 * k)}px"><li>30 editable designs, 8 colour looks</li><li>150 captions, your name filled in</li>'
                    f'<li>4:5, 1:1 and story sizes</li><li>Works offline: no account, no subscription</li></ul>')
            if sq:
                pos = [(70, 690, -9), (285, 650, -3), (500, 630, 3), (715, 650, 8), (930, 690, 13)]
                pw = 243
                body = f'<div class="pad">{text}</div>' + "".join(
                    f'<img class="post" src="{u}" style="left:{int(x * k)}px;top:{int(y * k)}px;width:{int(pw * k)}px;transform:rotate({r}deg)">' for u, (x, y, r) in zip(fan_u, pos))
            else:
                pos = [(585, 150, -10), (690, 120, -4), (795, 110, 2), (900, 130, 8), (990, 170, 14)]
                pw = 250
                body = f'<div class="pad" style="width:{int(590 * k)}px">{text}</div>' + "".join(
                    f'<img class="post" src="{u}" style="left:{int(x * k)}px;top:{int(y * k)}px;width:{int(pw * k)}px;transform:rotate({r}deg)">' for u, (x, y, r) in zip(fan_u, pos))
            body += '<div class="foot">Sample text shown. Add your own photos and logo.</div>'
        elif n == "2":
            cols = 6 if sq else 10
            tw = 212 if sq else 108
            cells = "".join(f'<img src="{u}" style="width:{tw}px;border-radius:{max(4, int(8 * k))}px;box-shadow:0 {int(6 * k)}px {int(14 * k)}px rgba(0,0,0,.15)">' for u in grid_u)
            top = 470 if sq else 190
            body = (f'<div class="pad" style="text-align:center"><h1 style="font-size:{int((76 if sq else 46) * k)}px">30 editable post designs</h1>'
                    f'<p class="lead" style="margin-top:{int(12 * k)}px">One for every day of the month: tips, offers, hours, questions, events, thank-yous.</p></div>'
                    f'<div style="position:absolute;top:{top}px;left:0;right:0;display:grid;grid-template-columns:repeat({cols},{tw}px);gap:{26 if sq else 12}px;justify-content:center">{cells}</div>')
        else:
            text = (f'<span class="chip kick">The Post Maker</span><h1>Your colours, your words, in seconds</h1><div class="rule" style="margin-top:{int(22 * k)}px"></div>'
                    f'<ul class="checks" style="margin-top:{int(20 * k)}px"><li>Pick a look or use your brand colours</li><li>Add your logo and photos</li>'
                    f'<li>Download one post or all 30 as a zip</li><li>Caption bank with copy buttons</li></ul>')
            lw = 300 if sq else 135
            row = "".join(f'<img src="{u}" style="width:{lw}px;border-radius:{max(5, int(10 * k))}px;box-shadow:0 {int(10 * k)}px {int(24 * k)}px rgba(0,0,0,.2)">' for u in looks)
            if sq:
                body = (f'<div class="pad">{text}</div><div style="position:absolute;left:94px;top:1010px">{K.window(app_u, 1150)}</div>'
                        f'<div style="position:absolute;right:94px;top:1010px;display:grid;grid-template-columns:300px 300px;gap:28px">{row}</div>')
            else:
                body = (f'<div class="pad" style="width:{int(560 * k)}px">{text}</div>'
                        f'<div style="position:absolute;left:{int(600 * k)}px;top:{int(70 * k)}px">{K.window(app_u, int(640 * k))}</div>'
                        f'<div style="position:absolute;left:{int(600 * k)}px;top:{int(530 * k)}px;display:flex;gap:{int(14 * k)}px">{row}</div>')
            body += '<div class="foot">Works offline in your browser. Nothing you add leaves your device.</div>'
        html = f"<!doctype html><html><head><meta charset='utf-8'><style>{css}</style></head><body>{body}</body></html>"
        done.append(K.shoot(br, html, w, h, os.path.join(SHOP, name), quality=80 if sq else 84))
    return done


def build_media(log=print) -> list:
    from playwright.sync_api import sync_playwright
    out = []
    with sync_playwright() as pw:
        br = K.chromium(pw)
        pg = open_app(br)
        thumbs = [K.b64(draw(pg, i, k=0.2)) for i in range(30)]
        out.append(contact_sheet(pg, os.path.join(BUYER, "All_30_Designs.jpg")))
        out.append(K.html_pdf(br, plan_html(thumbs), os.path.join(BUYER, "30_Day_Plan.pdf"), "Letter", "The 30-Day Plan"))
        out.append(K.html_pdf(br, bank_html(), os.path.join(BUYER, "Caption_Bank.pdf"), "Letter", "Caption Bank: 150 captions"))
        demo = open_app(br, 1400, 900, 1)
        demo.evaluate("""() => { const set = (id, v) => { const e = document.getElementById(id); e.value = v; e.dispatchEvent(new Event('input')); };
          set('b-name', 'Corner Table Cafe'); set('b-town', 'Oak Hill'); set('b-contact', '(555) 010-0118'); }""")
        demo.wait_for_timeout(700)
        app_shot = demo.screenshot(type="jpeg", quality=86)
        out.append(K.html_pdf(br, howto_html(K.b64(app_shot)), os.path.join(BUYER, "How_to_use.pdf"), "Letter", "30-Day Local Social Media Kit: how to use it"))
        out += covers(br, pg, app_shot)
        br.close()
    return out


def build(images: bool = True, log=print) -> list:
    os.makedirs(BUYER, exist_ok=True)
    done = [K.write_text(APP, app_html())]
    done.append(K.write_text(os.path.join(BUYER, "LICENSE.txt"), LICENSE))
    done.append(K.write_text(os.path.join(BUYER, "README.txt"), README))
    done.append(K.write_text(os.path.join(BUYER, "Caption_Bank.txt"), bank_txt()))
    p = os.path.join(BUYER, "30_Day_Plan.csv")
    with open(p, "w", encoding="utf-8", newline="") as fh:
        fh.write(plan_csv())
    done.append(p)
    if images:
        done += build_media(log)
    done += K.write_listing(SHOP, dict(LISTING, files=K.buyer_files(BUYER)))
    return done


LISTING = {
    "id": "social-kit", "version": VERSION, "price_usd": 14, "top": TOP, "zip": ZIP,
    "title": "30 Day Social Media Kit for Local Small Business, 30 Editable Post Designs, 150 Captions, Content Calendar, Offline Post Maker",
    "short": "A month of posts for a local business: 30 editable designs in your colours, 150 captions with your name filled in, and a 30-day plan.",
    "description": [
        "Posting every day is easier with a plan and designs that already look good. This kit gives a local business a whole month: what to post, the picture and the words.",
        "WHAT YOU GET",
        "- The Post Maker: an offline page with 30 editable post designs. Type your business name once, pick your colours (8 looks or your own brand colours), add your logo and photos, and download PNGs",
        "- 3 sizes for every design: portrait 4:5 (1080 x 1350), 1:1 (1080 x 1080) and story (1080 x 1920)",
        "- 150 captions in 13 groups (introductions, behind the scenes, tips, services, offers, seasons, community, team, honest review requests, questions, hiring and events, listing updates), with your name filled in and a copy button",
        "- The 30-day plan as a PDF and a spreadsheet (CSV): the theme, the caption, alt text and a tip for each day",
        "- A how-to guide and all 30 designs on one picture",
        "WORKS FOR",
        "- Cafes, salons, barbers, trades, cleaners, shops, studios and other local businesses. Captions have [brackets] for your own details",
        "- Business owners who post themselves, and helpers who make posts for clients (client use is allowed)",
        "GOOD TO KNOW",
        "- No account, no subscription, no app to install: open the file in your browser. Nothing you add leaves your device",
        "- This is not a template for a design website or app; the designs are edited in the included Post Maker",
        "- Honest by design: the review posts ask for honest reviews (no rewards), offers include their terms, and nothing promises followers or sales",
        "Instant download. Original designs; made with the help of AI tools, designed, checked and supported by me.",
    ],
    "tags_etsy": ["social media kit", "small business post", "content calendar", "caption ideas", "post templates", "local business",
                  "30 day content plan", "social media posts", "editable templates", "salon social media", "cafe social media", "business captions", "marketing planner"],
    "faq": [
        ["Do I need a design app or an account?", "No. The Post Maker is a page that opens in your web browser and works offline. You type, pick colours and download the pictures."],
        ["Can I use my own colours, logo and photos?", "Yes: 8 ready looks or your own colours (it checks that text stays readable), your logo in a circle on every post, and your photos in the photo frames."],
        ["Which sizes do I get?", "Every design in portrait 4:5 (1080 x 1350), 1:1 (1080 x 1080) and story (1080 x 1920)."],
        ["Can I use it for clients?", "Yes, you can make posts for clients' businesses. You may not resell or share the kit itself."],
        ["Does it post for me?", "No. You download the pictures and post or schedule them yourself (most platforms have a free scheduler)."],
        ["Will this get me more customers or followers?", "Nobody can promise that. The kit makes regular, good-looking posts easy; results depend on your business, your area and how you reply to people."],
    ],
    "refund": "Digital download: files can't be returned, but if something does not work as described, message me within 14 days and I will fix it or refund you.",
    "price_reasoning": ("$14 sits in the middle of comparable kits: 30-day small-business kits with templates and captions list at $9 (Getly), "
                        "$12-15 (Gumroad), $19.50 (Payhip); Etsy trade post packs run about $5-15, many on sale. Ours adds an offline editor (no "
                        "account), 3 sizes and 150 captions, but the market expects low prices and buyers often look for a design-app version, "
                        "so we stay mid-range. Try $12 if views do not turn into sales; $17 after 10 good reviews."),
    "comparables": [
        {"what": "30-Day Small Business Social Media Content Kit (templates, captions, calendar)", "price": "$9 (name your price, $5 minimum)", "where": "Getly", "url": "https://www.getly.store/product/30-day-small-business-social-media-content-kit", "seen": "2026-11-14"},
        {"what": "6 ready 30-day content calendars with captions and hashtags", "price": "$12", "where": "Gumroad", "url": "https://milidoesthis.gumroad.com/l/fxeko", "seen": "2026-11-14"},
        {"what": "30-Day Social Media Content System (prompts, calendar, caption templates)", "price": "$15", "where": "Gumroad", "url": "https://kacieturley.gumroad.com/l/vpeffy", "seen": "2026-11-14"},
        {"what": "30-Day Content Calendar Bundle", "price": "$19.50", "where": "Payhip", "url": "https://payhip.com/b/xyjkC", "seen": "2026-11-14"},
        {"what": "Builder / HVAC editable post packs (40-50 posts)", "price": "about $5 to $15 (sale $8.84 from $14.73)", "where": "Etsy", "url": "https://www.etsy.com/listing/1472114060", "seen": "2026-11-14"},
    ],
    "image_notes": ["five posts in five looks", "all 30 designs", "the Post Maker + the same post in 4 looks", "square version of 1", "square version of 2", "square version of 3"],
    "rules": [
        "No brand names in the title, tags or pictures (no app or platform names): descriptive words only.",
        "No follower, reach or sales promises.",
        "Etsy: 'I did' (made by a seller), digital download; the description says AI tools helped.",
        "The comparable listings' links are for the seller's own price checks; never put them in the product.",
    ],
}


def make_zip(out: str | None = None) -> str:
    return K.make_zip(BUYER, TOP, ZIP, out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m money_machines.products.build_social_kit")
    ap.add_argument("--zip", action="store_true")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--no-images", action="store_true")
    a = ap.parse_args(argv)
    if a.zip and not a.build:
        print(make_zip())
        return 0
    for p in build(images=not a.no_images):
        print(p)
    if a.zip:
        print(make_zip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
