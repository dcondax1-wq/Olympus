"""Build the LOCAL BUSINESS WEBSITE TEMPLATES product (team D2, 2026-11-14): 5 one-page sites + an offline no-code Site Editor + a guide.

    python -m money_machines.products.build_site_templates --zip     # the owner: pack the committed files into the upload zip (plain Python)
                                                                     #   -> money_machines/out/products/local_business_website_templates_v1.0.zip
    python -m money_machines.products.build_site_templates           # rebuild everything (Node or Chromium for the templates, Chromium for
                                                                     #   the guide PDF and the 6 covers; run under the browser lock)

Sources: site_templates/src/ (editor.html with the renderer, base.css, themes/*.css, art/*.svg, icons.json: original work, the art and
icons first drawn by team B1 for the agency demo sites, CC0) + site_templates_data.py (the 5 looks and the sample text). The 5 template
files are rendered by the editor's own renderer (SiteKit.render), so the editor and the templates can never disagree.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

from money_machines.products import kit as K
from money_machines.products import site_templates_data as D

HERE = os.path.dirname(os.path.abspath(__file__))
PROD = os.path.join(HERE, "site_templates")
SRC, BUYER, SHOP = (os.path.join(PROD, x) for x in ("src", "buyer", "shop"))
VERSION = "1.0"
TOP = "Local-Business-Website-Templates"
ZIP = f"local_business_website_templates_v{VERSION}.zip"
EDITOR = os.path.join(BUYER, "Site_Editor.html")


def read(*p) -> str:
    with open(os.path.join(SRC, *p), encoding="utf-8") as fh:
        return fh.read()


def kit_json() -> dict:
    icons = json.loads(read("icons.json"))
    icons.pop("_about", None)
    themes = {}
    for tid in D.ORDER:
        t = dict(D.THEMES[tid])
        t["css"] = read("themes", tid + ".css").strip()
        t["svg"] = read("art", tid + ".svg").strip()
        themes[tid] = t
    return {"version": VERSION, "base_css": read("base.css").strip(), "themes": themes, "icons": icons, "samples": D.SAMPLES, "schema_types": D.SCHEMA_TYPES}


def editor_html() -> str:
    src = read("editor.html")
    blob = json.dumps(kit_json(), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    out, n = re.subn(r"/\*KIT\*/\{\}/\*END\*/", lambda m: "/*KIT*/" + blob + "/*END*/", src)
    if n != 1:
        raise SystemExit("editor.html: the /*KIT*/{}/*END*/ marker is missing")
    return out


def sitekit_js(html: str) -> str:
    m = re.search(r'<script id="sitekit">(.*?)</script>', html, re.S)
    if not m:
        raise SystemExit("no sitekit script in the editor")
    return m.group(1)


NODE_RUN = r"""
const fs = require('fs'), vm = require('vm');
const code = fs.readFileSync(process.argv[2], 'utf8');
const ctx = {}; ctx.globalThis = ctx; vm.createContext(ctx); vm.runInContext(code, ctx);
const SK = ctx.SiteKit, out = {};
for (const id of JSON.parse(process.argv[3])) out[id] = SK.render(id, SK.sample(id), {demo: true, year: '2026'});
process.stdout.write(JSON.stringify(out));
"""


def node_exe() -> str | None:
    return shutil.which("node") or next((p for p in ("/opt/node22/bin/node",) if os.path.exists(p)), None)


def render_all(html: str) -> dict:
    """{template id: finished index.html} from the editor's own renderer (Node; Chromium when Node is missing)."""
    js = sitekit_js(html)
    node = node_exe()
    if node:
        tmp = tempfile.mkdtemp(prefix="d2_site_")
        try:
            p, r = os.path.join(tmp, "kit.js"), os.path.join(tmp, "run.js")
            open(p, "w", encoding="utf-8").write(js)
            open(r, "w", encoding="utf-8").write(NODE_RUN)
            res = subprocess.run([node, r, p, json.dumps(D.ORDER)], capture_output=True, text=True, encoding="utf-8", timeout=120)
            if res.returncode:
                raise SystemExit("node render failed: " + res.stderr[:800])
            return json.loads(res.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        br = K.chromium(pw)
        pg = br.new_page()
        pg.set_content("<script>" + js + "</script>")
        out = pg.evaluate("(ids) => Object.fromEntries(ids.map(id => [id, SiteKit.render(id, SiteKit.sample(id), {demo: true, year: '2026'})]))", D.ORDER)
        br.close()
    return out


def template_path(tid: str) -> str:
    return os.path.join(BUYER, "templates", D.THEMES[tid]["folder"], "index.html")


# ------------------------------------------------------------------------------------------------ text files
LICENSE = f"""ONE-PAGE WEBSITE TEMPLATES v{VERSION}: LICENCE

What you may do
- Use the templates and the Site Editor to make websites for your own business.
- Make websites for your clients with them, as many as you like. Each finished site belongs to you or your client.
- Change anything: text, colours, layout, drawings, icons.

What you may not do
- Resell, share, upload or give away the templates, the Site Editor or edited copies of them as templates, themes or kits
  (for example in a template shop or a download bundle).

Good to know
- The drawings and icons are original artwork made for these templates; you may use them on the sites you make.
- The sample businesses, people, phone numbers (555-01xx) and addresses are made up. Replace every one of them.
- Only publish claims that are true for the business (licences, insurance, prices, reviews).
- The files are provided as is, without warranty of any kind. If something does not work as described, message the seller
  through the shop where you bought this within 14 days and we will help you or refund you.
"""

README = f"""ONE-PAGE WEBSITE TEMPLATES v{VERSION}: QUICK START

1. Open Site_Editor.html in your web browser (double-click it). It works offline.
2. Pick one of the 5 looks, fill in your details, add your photos if you like, and watch the preview.
3. Press "Download my site": you get index.html, your finished one-page website.
4. Put it online: Guide.pdf shows the free and simple ways, step by step.

Prefer to edit by hand? The 5 finished templates are in the templates folder:
  templates/1-trades        plumbers, electricians, heating and cooling, roofers, painters, handymen
  templates/2-home-garden   landscapers, lawn care, gardeners, cleaners, pet groomers
  templates/3-cafe          cafes, bakeries, small restaurants, food trucks
  templates/4-salon         hair, nail and beauty salons
  templates/5-barber        barbers, tattoo studios, grooming
Each one is a single index.html file: open it in any plain text editor, change the words, save, refresh the browser.

Save your answers ("Save my answers") to keep a copy or to move to another computer.
Nothing you type leaves your computer: the editor has no server and loads nothing from the internet.
"""


def guide_html(thumbs: dict) -> str:
    """The 8-page guide (US Letter). thumbs: {template id: data URI of a phone screenshot} or {} for a text-only build."""
    cards = "".join(f'<div class="tc"><img src="{thumbs[t]}" alt=""><b>{D.THEMES[t]["label"]}</b><span>{D.THEMES[t]["for"]}</span></div>'
                    for t in D.ORDER if t in thumbs)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><style>
@page{{size:Letter;margin:15mm 16mm 16mm}}
body{{font-family:Inter,'Segoe UI',Arial,sans-serif;color:#1d1a16;font-size:10.6pt;line-height:1.5;margin:0}}
h1{{font-family:{K.SERIF};font-size:27pt;line-height:1.05;margin:0 0 6pt}}
h2{{font-family:{K.SERIF};font-size:15.5pt;margin:16pt 0 6pt;padding-bottom:3pt;border-bottom:2px solid #c8a24a;break-after:avoid}}
h3{{font-size:11pt;margin:10pt 0 3pt;break-after:avoid}}
p{{margin:0 0 7pt}}ol,ul{{margin:0 0 8pt;padding-left:17pt}}li{{margin:0 0 3pt}}
.sub{{color:#5a5145;font-size:12pt;margin-bottom:12pt}}
.box{{background:#f6f2ea;border-radius:8pt;padding:8pt 11pt;margin:8pt 0;break-inside:avoid}}
.warn{{background:#fdf1e7;border-left:4pt solid #9a3412}}
.small{{color:#6b6256;font-size:8.8pt}}
table{{border-collapse:collapse;width:100%;font-size:9.6pt;margin:4pt 0 9pt}}td,th{{border-bottom:1px solid #ddd5c6;padding:4pt 6pt;text-align:left;vertical-align:top}}
th{{background:#f1ece2}}code{{font-family:'DejaVu Sans Mono',Consolas,monospace;font-size:9pt;background:#f1ece2;padding:0 3pt;border-radius:3pt}}
.grid{{display:grid;grid-template-columns:repeat(5,1fr);gap:7pt;margin:8pt 0 10pt}}
.tc img{{width:100%;border-radius:6pt;border:1px solid #ddd5c6}}.tc b{{display:block;font-size:9.5pt;margin-top:3pt}}.tc span{{display:block;font-size:7.6pt;color:#6b6256;line-height:1.3}}
.check li{{list-style:none;margin-left:-14pt}}.check li:before{{content:"\\2610  ";font-size:11pt}}
.pb{{break-before:page}}
</style></head><body>
<h1>One-Page Website Templates</h1><p class="sub">The guide: edit your site without code, put it online, and check it before you share it. Version {VERSION}.</p>
<h2>1. What is inside</h2>
<div class="grid">{cards}</div>
<table><tr><th>File</th><th>What it is</th></tr>
<tr><td><b>Site_Editor.html</b></td><td>The no-code editor. Open it in your browser, fill in a form, see the preview, download your finished site.</td></tr>
<tr><td><b>templates/</b></td><td>The 5 finished templates (one index.html each) with sample text, for people who like to edit by hand.</td></tr>
<tr><td><b>Guide.pdf</b>, README.txt, LICENSE.txt</td><td>This guide, a quick start and the licence (you may make sites for clients).</td></tr></table>
<p>Every template is one file with everything inside: no images to upload, no fonts or scripts loaded from other sites, no cookies,
no tracking. That keeps it fast on a phone and simple to host. Each page has: a header with your phone number, a big first section with
your main button, services, a section made for the trade (steps, seasons, a menu or a price list), why customers choose you, your story,
photos, real reviews, questions, opening hours and location, a contact section and a call bar on phones.</p>

<h2>2. Make your site with the Site Editor (no code)</h2>
<ol><li><b>Open Site_Editor.html</b> (double-click). It works without the internet. Your answers are kept in this browser as you type.</li>
<li><b>Pick a look</b> at the top. You can switch any time: your text stays.</li>
<li><b>Fill in the groups</b> from top to bottom. Anything you leave empty is left out of the site, so you never publish a blank box.</li>
<li><b>Add your photos</b> (optional): a big photo for the top, one next to your story and up to 6 for the gallery. They are shrunk
automatically and saved inside the site file. Use only photos you took or have the rights to.</li>
<li><b>Check the preview</b> in Phone and Computer view. On a phone, use the Edit / Preview tabs.</li>
<li><b>Download my site.</b> You get <code>index.html</code>. Also press <b>Save my answers</b> to keep a file you can open later to make changes.</li></ol>
<div class="box"><b>Colour.</b> Each look has a tested colour scheme. In the Colour group you can pick your own main colour: the editor
tells you if button text would be hard to read and darkens link colours automatically so they stay readable.</div>

<h2 class="pb">3. Put it online for free</h2>
<p>Your site is one file, <code>index.html</code>. Any web host that serves plain files (often called <b>static hosting</b>) can put it
online, and several well-known hosts have a free plan where you simply drag a folder into the browser. The steps are nearly the same everywhere:</p>
<ol><li>Make a new folder on your computer, for example <code>my-site</code>, and put <code>index.html</code> in it (keep that name).</li>
<li>Search for <b>free static website hosting drag and drop</b> and create an account with a host you trust.</li>
<li>Choose the option to deploy or upload a folder, and drop <code>my-site</code> on it. Within a minute you get a web address.</li>
<li>Open that address on your phone and tap every button (call, text, email, directions).</li>
<li>To change the site later: edit in the Site Editor, download again, and upload the new <code>index.html</code> the same way.</li></ol>
<h3>Already have a web host?</h3>
<p>Open your host's file manager, go to the main web folder (often called <code>public_html</code> or <code>www</code>), keep a copy of the
old home page, then upload your <code>index.html</code>. Visit your address and refresh.</p>
<h3>Your own domain name</h3>
<p>A domain (like yourbusiness.com) is bought from a domain registrar, usually for a yearly fee. In your hosting account choose
<b>add a custom domain</b> and follow its steps: usually you copy one or two records into the registrar's DNS settings. It can take up to a
day or two to work everywhere. Turn on HTTPS (the padlock) in the host's settings if it is not on by default.</p>

<h2>4. Before you share it: the launch check</h2>
<ul class="check"><li>The Call button dials the right number; the Text button opens a text message (on a phone).</li>
<li>The message form opens your email app with the message filled in, sent to the right address.</li>
<li>Business name, address, phone and hours are correct and the same as on your other listings.</li>
<li>Every claim is true: licences, insurance, prices, "free quote", years in business.</li>
<li>No sample text is left: search the page for "Riverton", "555" and "example.com".</li>
<li>Photos are yours or you have permission; reviews are real (see section 6).</li>
<li>It reads well on a small phone and on a computer; nothing is cut off.</li>
<li>The page title and description (in "Search engines and the footer") say what you do and where.</li></ul>

<h2 class="pb">5. Help local customers find you (no promises, just good basics)</h2>
<p>Nobody can promise a position in search results. These steps help search engines and people understand your business:</p>
<ol><li><b>Same details everywhere.</b> Use exactly the same business name, address and phone number on your site, your free business
profiles on the big search and map sites, and your social pages.</li>
<li><b>Link to your site</b> from those profiles and pages.</li>
<li><b>Say what and where.</b> Your headline and page title should name your service and your town, in normal words.</li>
<li><b>Ask every customer for an honest review</b> after the job, and reply politely to all of them, good and bad.</li>
<li><b>Keep it current.</b> Update hours before holidays, add new photos, refresh a service now and then.</li></ol>
<p>The template already includes a page title, a description, phone-friendly layout, fast loading and structured data (a short
machine-readable summary of your business: name, phone, address, hours) that search engines can read.</p>

<h2>6. The rules that keep you safe</h2>
<ul><li><b>Reviews:</b> show only real reviews from real customers, in their words, with their permission. Never write reviews yourself,
never pay or reward people for reviews, and never hide the honest negative ones. In the US the FTC's rule on consumer reviews bans fake
reviews and buying them, with large fines. The review section only appears when you tick the "real reviews" box.</li>
<li><b>Photos and words:</b> use your own photos and your own text, or ones you have permission to use.</li>
<li><b>Claims:</b> only state licences, insurance, guarantees and prices that are true.</li>
<li><b>Privacy:</b> the site stores nothing and uses no cookies, so it needs no cookie banner as it is. If you add analytics, a booking
widget, a chat or a form service later, add a short privacy notice that says what they collect.</li></ul>

<h2 class="pb">7. Editing by hand (optional)</h2>
<p>Open <code>index.html</code> in a plain text editor (the one that comes with your computer works). Then:</p>
<ul><li><b>Colours and fonts</b> are the first lines inside <code>&lt;style&gt;</code>: <code>--accent</code> is the main colour,
<code>--bg</code> the page background, <code>--ink</code> the text colour. Change the colour codes (like <code>#c2410c</code>) and save.</li>
<li><b>Each section starts with a comment</b> such as <code>&lt;!-- ===== SERVICES ===== --&gt;</code>. Change the words between the tags.</li>
<li><b>Remove a section:</b> delete from its comment down to the next section's comment. Also remove its link in the menu near the top.</li>
<li><b>Check after every change:</b> save, then refresh the page in your browser.</li></ul>
<div class="box"><b>Tip:</b> keep the Site Editor as the main way to change your site, and save your answers file somewhere safe. Editing the
answers is easier than editing HTML, and you can download a fresh site any time.</div>

<h2>8. Licence and help</h2>
<p>You may use these templates for your own business and to make sites for clients (as many as you like). You may not resell or share the
templates or the editor themselves. The sample businesses and people are made up. Full text: LICENSE.txt.</p>
<p>Questions or a problem? Message me through the shop where you bought this. I usually reply within one working day.</p>
<p class="small">Made with the help of AI tools; designed, checked and supported by a person. The templates contain no third-party code,
fonts or images. Not legal advice: rules on reviews, advertising and privacy differ by place, so check the ones that apply to you.</p>
</body></html>"""


# ------------------------------------------------------------------------------------------------ listing copy
LISTING = {
    "id": "site-templates", "version": VERSION, "price_usd": 24, "top": TOP, "zip": ZIP,
    "title": "5 One-Page Website Templates for Local Businesses, No-Code Site Editor, Phone-First HTML for Trades, Cafe, Salon, Barber, Garden",
    "short": "Five ready one-page websites for local businesses and an offline editor: fill in a form, download your site, put it online.",
    "description": [
        "A good local website does three things fast: says what you do and where, shows your prices or services, and makes it one tap to call. These five one-page templates do exactly that, on a phone first.",
        "WHAT YOU GET",
        "- 5 one-page website templates, each designed for a kind of local business: Trades (plumbers, electricians, heating, roofers), Home and Garden (lawn care, landscapers, cleaners), Cafe (with a menu board), Salon (with a price list), Barber (dark, with a price board)",
        "- The Site Editor: an offline page where you fill in a form (name, services, prices, hours, photos, colours) and download your finished site. No code, no account, no subscription",
        "- An 8-page guide: edit without code, put it online for free, use your own domain, a launch checklist, local-search basics and the rules on reviews",
        "WHAT EACH SITE HAS",
        "- Big tap-to-call button and a call bar on phones, text and email buttons, a message form that opens the visitor's email app",
        "- Services, a section made for the trade (steps, seasons, menu or price list), why choose you, your story, photos, real reviews, questions, opening hours and location",
        "- Fast and private: one file, no cookies, no tracking, nothing loaded from other sites. Page title, description and structured data for search engines included",
        "- Accessible colours (tested contrast), keyboard friendly, works on phones, tablets and computers",
        "HOW IT WORKS",
        "1. Open the Site Editor in your browser. 2. Fill in your details and pick a look. 3. Download index.html and put it online (the guide shows free ways, step by step).",
        "GOOD TO KNOW",
        "- Licence: use them for your own business and for client websites (unlimited). No reselling of the templates themselves.",
        "- Hosting and a domain name are not included; free static hosting works, a domain usually costs a yearly fee.",
        "- This is a plain HTML website, not a template for a website-builder app.",
        "- No ranking or customer promises: the templates give you a fast, clear site; results depend on your business and your area.",
        "Instant download. Original designs; made with the help of AI tools, designed, checked and supported by me.",
    ],
    "tags_etsy": ["website template", "html template", "small business site", "landing page", "one page website", "local business",
                  "plumber website", "salon website", "cafe website", "barber website", "landscaping website", "web design template", "no code website"],
    "faq": [
        ["Do I need to know code?", "No. Open the Site Editor, fill in the form and download your site. If you like code, the templates are clean, commented HTML."],
        ["How do I put it online?", "The guide shows the simple ways: drag the file into a free static hosting service, or upload it to the web host you already have."],
        ["Can I use it for my clients?", "Yes: make as many client sites as you like. You may not resell or share the templates themselves."],
        ["Can I add my own photos and colours?", "Yes. Photos are shrunk automatically and saved inside the site; the colour picker warns you if text would be hard to read."],
        ["Is there a monthly fee?", "Not from me: it is a one-time purchase. Hosting and a domain name are separate (free hosting plans exist)."],
        ["Will it get me more customers?", "Nobody can promise that. It gives you a fast, clear, phone-friendly site with the basics search engines read; results depend on your business."],
    ],
    "refund": "Digital download: files can't be returned, but if something does not work as described, message me within 14 days and I will fix it or refund you.",
    "price_reasoning": ("$24 for 5 templates + the no-code editor + the guide (about $5 a template). Single one-page HTML templates list from $1 to $20 "
                        "(Gumroad $1, $5 and $12, Getly $19.99) and Etsy trade website templates run from about $6 to about $97 (most of the top end needs "
                        "a website-builder app). Five ready designs plus an editor a non-coder can use sit in the upper middle of that range. Launch at $24; "
                        "if it gets views but no sales in 30 days try $19; after 10 good reviews try $29."),
    "comparables": [
        {"what": "One-page Tailwind business site (BrightPixel)", "price": "$1", "where": "Gumroad", "url": "https://webstercompany.gumroad.com/l/brightpixel", "seen": "2026-11-14"},
        {"what": "Small business landing page template (one page, no builder)", "price": "$12", "where": "Gumroad", "url": "https://adelinamiron.gumroad.com/l/small-business-landing-page", "seen": "2026-11-14"},
        {"what": "Landing theme: hero, features, pricing, FAQ, commercial licence", "price": "$19.99", "where": "Getly", "url": "https://www.getly.store/product/nova-landing-theme-muhcrtdd", "seen": "2026-11-14"},
        {"what": "Responsive HTML/CSS business landing template", "price": "about 50 NOK (about $5)", "where": "Etsy", "url": "https://www.etsy.com/listing/4442821091/responsive-website-template-html-css", "seen": "2026-11-14"},
        {"what": "Plumber website templates (mostly for a website builder), range across listings", "price": "about $6.45 to $97", "where": "Etsy (search results)", "url": "https://www.etsy.com/listing/4455941773", "seen": "2026-11-14"},
    ],
    "image_notes": ["laptop + phones, the hero picture", "the 5 looks on phones", "the Site Editor", "square version of 1 (Etsy first photo)", "square version of 2", "square version of 3"],
    "rules": [
        "Never name a website-builder app, a hosting company or any other brand in the title, tags or pictures (descriptive words only).",
        "No ranking, traffic or customer promises anywhere.",
        "Etsy: 'I did' (made by a seller), 'a finished product', digital download; the description says AI tools helped (Etsy's creativity rule).",
        "The sample businesses are made up: the pictures show 555-01xx numbers and example.com emails only.",
    ],
}


# ------------------------------------------------------------------------------------------------ pictures (Chromium)
def screenshots(br, files: dict) -> dict:
    """Phone (390 x 844 at 2x) and computer (1280 x 800) screenshots of each template + the editor, as JPEG bytes."""
    shots = {}
    for tid, path in files.items():
        html = open(path, encoding="utf-8").read()
        for kind, vp, scale in (("phone", (390, 844), 2), ("desk", (1280, 800), 1)):
            pg = br.new_page(viewport={"width": vp[0], "height": vp[1]}, device_scale_factor=scale)
            pg.set_content(html, wait_until="load")
            pg.wait_for_timeout(120)
            shots[(tid, kind)] = pg.screenshot(type="jpeg", quality=88)
            pg.close()
    ed = open(EDITOR, encoding="utf-8").read()
    pg = br.new_page(viewport={"width": 1280, "height": 800}, device_scale_factor=1.5)
    pg.route("**/*", lambda route: route.fulfill(status=200, content_type="text/html", body=ed))
    pg.goto("http://editor.local/")
    pg.wait_for_timeout(900)
    pg.evaluate("() => { const g = document.querySelectorAll('details.grp'); if (g[3]) g[3].open = true; }")
    pg.wait_for_timeout(400)
    shots[("editor", "desk")] = pg.screenshot(type="jpeg", quality=88)
    pg.close()
    return shots


def covers(br, shots: dict) -> list:
    u = {k: K.b64(v) for k, v in shots.items()}
    done = []
    bg, ink, soft, acc = "#f6f2ea", "#1d1a16", "#5a5145", "#a0772c"
    for name, w, h in K.COVERS:
        sq = w == h
        k = w / 1280
        css = K.cover_css(w, h, bg=bg, ink=ink, soft=soft, accent=acc) + f"""
.pad{{position:absolute;inset:0;padding:{int(60 * k)}px}}
.kick{{font-size:{int(21 * k)}px;padding:{int(7 * k)}px {int(18 * k)}px;margin-bottom:{int(22 * k)}px}}
h1{{font-size:{int((74 if sq else 56) * k)}px}} .lead{{font-size:{int((30 if sq else 24) * k)}px;line-height:1.35;margin-top:{int(20 * k)}px;color:{soft}}}
ul.checks li{{font-size:{int((27 if sq else 22) * k)}px;margin:{int(11 * k)}px 0}}
.foot{{position:absolute;left:{int(60 * k)}px;bottom:{int(26 * k)}px;font-size:{int((19 if sq else 16) * k)}px;color:#7a6f60}}
.lbl{{font-weight:800;font-size:{int((24 if sq else 18) * k)}px;text-align:center;margin-top:{int(12 * k)}px}}
.lbl small{{display:block;font-weight:500;font-size:{int((17 if sq else 13) * k)}px;color:{soft};line-height:1.3;margin-top:{int(4 * k)}px}}
.band{{position:absolute;left:0;right:0;bottom:0;height:{int((300 if sq else 160) * k)}px;background:#e9e1d2}}"""
        n = name.split("_")[1][0]
        if n == "1":
            text = (f'<span class="chip kick">5 templates + a no-code editor</span><h1>One-Page Website Templates for Local Businesses</h1><div class="rule" style="margin-top:{int(22 * k)}px"></div>'
                    f'<p class="lead">Phone-first, fast, yours to edit. Fill in a form and download your site.</p>'
                    f'<ul class="checks" style="margin-top:{int(18 * k)}px"><li>Trades, home &amp; garden, cafe, salon, barber</li><li>Tap-to-call, hours, prices, photos, reviews</li>'
                    f'<li>No code, no subscription, works offline</li><li>Guide: put it online for free</li></ul>')
            if sq:
                body = (f'<div class="pad">{text}</div><div class="band"></div>'
                        f'<div style="position:absolute;left:{int(80 * k)}px;top:{int(1040 * k)}px">{K.window(u[("trades", "desk")], int(1180 * k))}</div>'
                        f'<div style="position:absolute;right:{int(70 * k)}px;top:{int(860 * k)}px">{K.phone(u[("salon", "phone")], int(330 * k))}</div>'
                        f'<div style="position:absolute;right:{int(400 * k)}px;top:{int(1010 * k)}px">{K.phone(u[("barber", "phone")], int(300 * k))}</div>')
            else:
                body = (f'<div class="pad" style="width:{int(600 * k)}px">{text}</div><div class="band"></div>'
                        f'<div style="position:absolute;left:{int(640 * k)}px;top:{int(80 * k)}px">{K.window(u[("trades", "desk")], int(600 * k))}</div>'
                        f'<div style="position:absolute;left:{int(1000 * k)}px;top:{int(250 * k)}px">{K.phone(u[("salon", "phone")], int(210 * k))}</div>'
                        f'<div style="position:absolute;left:{int(800 * k)}px;top:{int(330 * k)}px">{K.phone(u[("barber", "phone")], int(185 * k))}</div>')
            body += '<div class="foot">Sample businesses are made up. Hosting and domain not included.</div>'
        elif n == "2":
            labels = [(t, D.THEMES[t]["label"], D.THEMES[t]["for"].split(",")[0].strip() + ", " + D.THEMES[t]["for"].split(",")[1].strip()) for t in D.ORDER]
            if sq:
                pw = int(330 * k)
                ph = lambda t, l, f: f'<div style="width:{pw}px">{K.phone(u[(t, "phone")], pw)}<div class="lbl">{l}<small>{f}</small></div></div>'
                row1 = "".join(ph(*x) for x in labels[:3])
                row2 = "".join(ph(*x) for x in labels[3:])
                body = (f'<div class="pad" style="text-align:center"><h1>5 looks, one for each kind of local business</h1><div class="rule" style="margin:{int(22 * k)}px auto 0"></div></div>'
                        f'<div style="position:absolute;top:{int(330 * k)}px;left:0;right:0;display:flex;justify-content:center;gap:{int(70 * k)}px">{row1}</div>'
                        f'<div style="position:absolute;top:{int(1170 * k)}px;left:0;right:0;display:flex;justify-content:center;gap:{int(70 * k)}px">{row2}</div>')
            else:
                pw = int(196 * k)
                body = (f'<div class="pad" style="padding-bottom:0"><h1 style="font-size:{int(44 * k)}px">5 looks, one for each kind of local business</h1>'
                        f'<div class="rule" style="margin-top:{int(16 * k)}px"></div></div>'
                        f'<div style="position:absolute;top:{int(175 * k)}px;left:0;right:0;display:flex;justify-content:center;gap:{int(34 * k)}px">'
                        + "".join(f'<div style="width:{pw}px">{K.phone(u[(t, "phone")], pw)}<div class="lbl">{l}</div></div>' for t, l, f in labels) + "</div>")
            body += '<div class="foot">Sample text shown. Every word, colour and photo is yours to change.</div>'
        else:
            steps = (f'<ol style="list-style:none;margin-top:{int(26 * k)}px">' + "".join(
                f'<li style="display:flex;gap:{int(16 * k)}px;align-items:flex-start;margin:{int(16 * k)}px 0;font-size:{int((27 if sq else 21) * k)}px">'
                f'<b style="flex:none;width:{int(46 * k)}px;height:{int(46 * k)}px;border-radius:50%;background:{acc};color:#fff;display:grid;place-items:center;font-size:{int(22 * k)}px">{i}</b>'
                f'<span><b>{t}</b><br><span class="soft" style="font-size:.85em">{s}</span></span></li>'
                for i, (t, s) in enumerate([("Pick a look", "five designs, switch any time"), ("Fill in your details", "services, prices, hours, photos, colours"),
                                            ("Download your site", "one file, index.html, ready to put online")], 1)) + "</ol>")
            text = (f'<span class="chip kick">Included: the Site Editor</span><h1>Edit your site without code</h1><div class="rule" style="margin-top:{int(22 * k)}px"></div>{steps}')
            if sq:
                body = (f'<div class="pad">{text}</div><div class="band"></div>'
                        f'<div style="position:absolute;left:{int(80 * k)}px;top:{int(1000 * k)}px">{K.window(u[("editor", "desk")], int(1400 * k))}</div>')
            else:
                body = (f'<div class="pad" style="width:{int(520 * k)}px">{text}</div><div class="band"></div>'
                        f'<div style="position:absolute;left:{int(560 * k)}px;top:{int(92 * k)}px">{K.window(u[("editor", "desk")], int(670 * k))}</div>')
            body += '<div class="foot">Works offline in your browser. Nothing you type leaves your computer.</div>'
        html = f"<!doctype html><html><head><meta charset='utf-8'><style>{css}</style></head><body>{body}</body></html>"
        done.append(K.shoot(br, html, w, h, os.path.join(SHOP, name), quality=80 if sq else 84))
    return done


def build_media(log=print) -> list:
    from playwright.sync_api import sync_playwright
    files = {t: template_path(t) for t in D.ORDER}
    out = []
    with sync_playwright() as pw:
        br = K.chromium(pw)
        shots = screenshots(br, files)
        thumbs = {}
        from io import BytesIO

        from PIL import Image
        for t in D.ORDER:
            im = Image.open(BytesIO(shots[(t, "phone")])).convert("RGB")
            im = im.crop((0, 0, im.width, int(im.width * 1.55))).resize((300, 465))
            b = BytesIO()
            im.save(b, "JPEG", quality=70, optimize=True)
            thumbs[t] = K.b64(b.getvalue())
        out.append(K.html_pdf(br, guide_html(thumbs), os.path.join(BUYER, "Guide.pdf"), "Letter", "One-Page Website Templates: the guide"))
        out += covers(br, shots)
        br.close()
    return out


def build(images: bool = True, log=print) -> list:
    os.makedirs(BUYER, exist_ok=True)
    html = editor_html()
    done = [K.write_text(EDITOR, html)]
    for tid, page in render_all(html).items():
        done.append(K.write_text(template_path(tid), page))
    done.append(K.write_text(os.path.join(BUYER, "LICENSE.txt"), LICENSE))
    done.append(K.write_text(os.path.join(BUYER, "README.txt"), README))
    if images:
        done += build_media(log)
    L = dict(LISTING, files=K.buyer_files(BUYER))
    done += K.write_listing(SHOP, L)
    return done


def make_zip(out: str | None = None) -> str:
    return K.make_zip(BUYER, TOP, ZIP, out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m money_machines.products.build_site_templates")
    ap.add_argument("--zip", action="store_true", help="pack the committed files into the upload zip (no rebuild; add --build to rebuild first)")
    ap.add_argument("--build", action="store_true", help="with --zip: rebuild first")
    ap.add_argument("--no-images", action="store_true", help="rebuild without Chromium (no guide PDF, no covers)")
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
