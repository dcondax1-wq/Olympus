"""The agency's OWN launch site (lead 2026-11-21): home, work (concept sites by trade), pricing, FAQ, contact, 16 local pages
"Website design for <trade> in <town>, MD", sitemap, robots, schema.org LocalBusiness. Export-ready for the neutral host.

    python tools/agency_site.py                 preview into tools/web_public/agency/launch/ (noindex; links to ../f/<id>/)
    (tools/site_factory.py --export <dir> calls build_files(prefix="") and puts it at the neutral site's root)

Honest by construction: no reviews, testimonials, awards, client counts or invented results. Prices = tools/web_public/agency/offers/offers.json.
Local pages use real numbers from the leads (how many businesses of that trade in that town list no website on OpenStreetMap).
Until the owner picks a name the site says AGENCY_NAME and stays noindex. No owner name, handle, home address or PC address anywhere.
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import site_factory as F  # noqa: E402

WEB = os.path.join(ROOT, "tools", "web_public", "agency")
OUT = os.path.join(WEB, "launch")
OFFERS = os.path.join(WEB, "offers", "offers.json")

TRADE = {  # factory niche -> (plural for page titles, singular kind, what their customers look for first)
    "food": ("restaurants and cafes", "restaurant", ["today's hours", "the menu", "a phone number to order or book", "directions and parking"]),
    "beauty": ("salons and barbers", "salon", ["prices or a service list", "how to book", "hours", "photos of the work"]),
    "health": ("health practices", "practice", ["whether you take new patients", "insurance questions answered by phone", "hours", "directions"]),
    "auto": ("auto shops", "shop", ["what you fix", "hours", "a phone number that is answered", "directions"]),
    "gym": ("gyms and studios", "gym", ["class times", "how to try it", "membership questions", "directions"]),
    "trades": ("contractors", "contractor", ["the jobs you take", "the area you cover", "a fast way to ask for a quote", "photos of past work"]),
    "services": ("local services", "service", ["what you do", "how to book", "hours", "directions"]),
    "pro": ("professional offices", "office", ["what you help with", "how to set up a first call", "hours", "directions"]),
    "retail": ("shops", "shop", ["hours", "what you carry", "a phone number to ask about stock", "directions"]),
}


def esc(s) -> str:
    return html.escape(str(s or ""), quote=True)


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")


def offers():
    d = json.load(open(OFFERS, encoding="utf-8"))
    pk = {p["id"]: p for p in d.get("packages", [])}
    return pk, d.get("terms", [])


WEIGHT = {"trades": 3, "health": 3, "beauty": 2, "auto": 2, "gym": 2, "pro": 2, "services": 1, "food": 1, "retail": 0.5}


def town_trades(sites):
    """one page per town; its trade = the best mix of how many no-website businesses of that trade the town has and how likely they
    are to buy (trades / health first), spread so the 16 pages don't all say 'restaurants' (near-duplicate pages help nobody)"""
    by = defaultdict(Counter)
    for s in sites:
        by[s["town"]][s["niche"]] += 1
    used, out = Counter(), []
    for town, c in sorted(by.items(), key=lambda kv: -sum(kv[1].values())):
        best = max(c, key=lambda n: (c[n] * WEIGHT.get(n, 1) / (1 + 1.5 * used[n]) if c[n] >= 2 else -1, c[n]))
        used[best] += 1
        out.append((town, best, c[best], sum(c.values()), c))
    return out


def portfolio(sites, per=2):
    """the best concept sites per trade: a phone and hours first, then a street address"""
    by = defaultdict(list)
    for s in sites:
        by[s["niche"]].append(s)
    pick = []
    for n in ["trades", "health", "beauty", "auto", "food", "gym", "services", "pro", "retail"]:
        xs = sorted(by.get(n, []), key=lambda s: (not s["phone"], not s["hours"], not s["ready"], s["name"].lower()))
        pick += xs[:per]
    return pick


CSS = """*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}body{margin:0;background:#fbfaf7;color:#15171a;
font:17px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}a{color:#1d4ed8}
.w{max-width:980px;margin:0 auto;padding:0 18px}header{position:sticky;top:0;z-index:5;background:rgba(251,250,247,.92);
backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);border-bottom:1px solid #e7e4dc}
header .w{display:flex;align-items:center;gap:14px;min-height:58px;padding-top:env(safe-area-inset-top)}
.brand{font-weight:800;letter-spacing:-.01em;color:#15171a;text-decoration:none;margin-right:auto}
nav a{color:#3c4148;text-decoration:none;font-size:.95rem;margin-left:12px}nav a[aria-current]{color:#15171a;font-weight:700}
@media (max-width:620px){nav a.opt{display:none}}
.btn{display:inline-flex;align-items:center;justify-content:center;min-height:48px;padding:0 20px;border-radius:999px;
background:#15171a;color:#fff;text-decoration:none;font-weight:700;border:2px solid #15171a}.btn.alt{background:transparent;color:#15171a}
.hero{padding:56px 0 40px}h1{font-size:clamp(2.1rem,7vw,3.4rem);line-height:1.05;letter-spacing:-.025em;margin:0 0 14px}
.lede{font-size:1.15rem;color:#4a4f57;max-width:640px;margin:0 0 24px}.row{display:flex;flex-wrap:wrap;gap:10px}
section{padding:36px 0;border-top:1px solid #e7e4dc}h2{font-size:1.6rem;letter-spacing:-.015em;margin:0 0 14px}h3{margin:0 0 6px;font-size:1.1rem}
.grid{display:grid;gap:14px;grid-template-columns:repeat(auto-fill,minmax(250px,1fr))}
.card{background:#fff;border:1px solid #e7e4dc;border-radius:18px;padding:18px}.card p{margin:0;color:#4a4f57}
.price{font-size:2rem;font-weight:800;letter-spacing:-.02em;margin:6px 0 2px}.per{color:#4a4f57;font-size:.95rem}
.card ul{margin:12px 0 0;padding-left:20px;color:#3c4148}.card li{margin:4px 0}.tag{display:inline-block;font-size:.75rem;font-weight:800;
letter-spacing:.06em;text-transform:uppercase;color:#1d4ed8}.steps{counter-reset:s;list-style:none;padding:0;margin:0;display:grid;gap:12px}
.steps li{counter-increment:s;position:relative;padding-left:46px}.steps li:before{content:counter(s);position:absolute;left:0;top:0;width:32px;
height:32px;border-radius:50%;background:#15171a;color:#fff;display:grid;place-items:center;font-weight:800}
.shot{display:block;text-decoration:none;color:inherit}.shot .k{font-size:.8rem;color:#6b7078}.muted{color:#6b7078}
details{background:#fff;border:1px solid #e7e4dc;border-radius:14px;padding:14px 16px;margin:0 0 10px}summary{font-weight:700;cursor:pointer}
details p{margin:10px 0 0;color:#4a4f57}footer{padding:30px 0 calc(30px + env(safe-area-inset-bottom));color:#6b7078;font-size:.9rem;border-top:1px solid #e7e4dc}
.stat{font-size:2.4rem;font-weight:800;letter-spacing:-.02em}a:focus-visible,.btn:focus-visible,summary:focus-visible{outline:3px solid #93c5fd;outline-offset:2px}"""

NAV = [("index.html", "Home"), ("work.html", "Work"), ("pricing.html", "Pricing"), ("faq.html", "FAQ"), ("contact.html", "Contact")]


class Ctx:
    def __init__(self, cfg, prefix, base):
        self.cfg = cfg
        self.name = (cfg.get("agency_name") or "").strip() or "AGENCY_NAME"
        self.named = bool((cfg.get("agency_name") or "").strip())
        self.prefix = prefix                      # how a page here reaches the concept sites: '' on the neutral host, '../' in the preview
        self.base = (base or "https://PUBLIC_BASE/").rstrip("/") + "/"
        self.t = F.tel(cfg.get("phone"))
        self.phone = cfg.get("phone_label") or cfg.get("phone") or "AGENCY_PHONE"
        self.email = (cfg.get("agency_email") or "").strip() or "AGENCY_EMAIL"


def call_btn(c: Ctx, alt=False):
    cls = "btn alt" if alt else "btn"
    return (f'<a class="{cls}" href="tel:{c.t}">Call {esc(c.phone)}</a>' if c.t else
            f'<a class="{cls}" href="contact.html">Phone: {esc(c.phone)}</a>')


def mail_btn(c: Ctx, subject="A website for my business", alt=True):
    cls = "btn alt" if alt else "btn"
    from urllib.parse import quote
    return f'<a class="{cls}" href="mailto:{esc(c.email)}?subject={quote(subject)}">Email us</a>'


def schema(c: Ctx, towns):
    d = {"@context": "https://schema.org", "@type": "LocalBusiness", "name": c.name, "url": c.base,
         "description": "Fast, phone-first websites for local businesses in Maryland.",
         "telephone": c.phone if c.t else "AGENCY_PHONE", "email": c.email, "priceRange": "$$",
         "areaServed": [{"@type": "City", "name": t + ", MD"} for t in towns]}
    return '<script type="application/ld+json">' + json.dumps(d, separators=(",", ":")).replace("</", "<\\/") + "</script>"


def page(c: Ctx, path: str, title: str, desc: str, body: str, towns, depth=0, extra_head=""):
    up = "../" * depth
    robots = "index, follow" if c.named else "noindex, nofollow"
    nav = "".join(f'<a href="{up}{h}"{" aria-current=page" if h == path else ""}{" class=opt" if h in ("faq.html",) else ""}>{esc(t)}</a>'
                  for h, t in NAV[1:])
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="{robots}">
<meta name="referrer" content="strict-origin-when-cross-origin">
<meta name="color-scheme" content="light">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{esc(c.base + ('' if path == 'index.html' else path))}">
<link rel="stylesheet" href="{up}style.css">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%2315171a'/%3E%3Cpath d='M8 22V10l8 7 8-7v12' fill='none' stroke='%23fff' stroke-width='2.6' stroke-linejoin='round'/%3E%3C/svg%3E">
{schema(c, towns) if path == "index.html" else ""}{extra_head}
</head>
<body>
<header><div class="w"><a class="brand" href="{up}index.html">{esc(c.name)}</a><nav aria-label="Main">{nav}</nav></div></header>
<main>
{body}
</main>
<footer><div class="w"><p style="margin:0 0 6px"><b>{esc(c.name)}</b> · Websites for local businesses in Maryland · <a href="mailto:{esc(c.email)}">{esc(c.email)}</a> · {esc(c.phone)}</p>
<p style="margin:0">Areas: {" · ".join(f'<a href="{up}{a}">{esc(t)}</a>' for t, a in towns.items())}</p></div></footer>
</body>
</html>
"""


def build_files(cfg=None, prefix="../", base=""):
    cfg = cfg or F.agency_cfg()
    c = Ctx(cfg, prefix, base or cfg.get("public_base", ""))
    sites = [s for s in json.load(open(os.path.join(WEB, "factory", "sites.json"), encoding="utf-8"))["sites"] if not s.get("chain")]
    pk, terms = offers()
    tt = town_trades(sites)
    towns = {t: f"areas/{slug(TRADE[n][0])}-{slug(t)}-md.html" for t, n, _k, _a, _c in tt}
    st, ce = pk.get("starter", {}), pk.get("callengine", {})
    files = {"style.css": CSS + "\n"}

    def pkg_cards():
        cards = [
            ("Starter site", f"${st.get('price', 1500):,}", f"+ ${st.get('monthly', 79)}/month care plan",
             ["The site we already made for you, finished with your words, logo and photos", "Up to 5 pages, built for phones first",
              "Tap-to-call, hours, map and a contact email", "Your own domain, in your name", "Care plan: hosting, updates, small edits every month"]),
            ("Nothing upfront", "$149/month", "for 12 months, then the $79 care plan",
             ["Everything in Starter", "No upfront payment", "Same site, same care plan", "Best if cash flow matters more than total cost"]),
            ("Call engine", f"${ce.get('price', 500):,}", f"+ ${ce.get('monthly', 299)}/month ({ce.get('min_months', 3)}-month minimum)",
             ["A one-page call site or a tune-up of your current one", "Google Business Profile set up and kept fresh",
              "Review requests by text after every job (you approve the wording)", "A plain one-page report each month"]),
        ]
        return "".join(f'<div class="card">{"<span class=tag>Most asked</span>" if i == 0 else ""}<h3>{esc(n)}</h3><div class="price">{esc(p)}</div>'
                       f'<div class="per">{esc(per)}</div><ul>{"".join(f"<li>{esc(x)}</li>" for x in inc)}</ul></div>'
                       for i, (n, p, per, inc) in enumerate(cards))

    # ---- home
    total = len(sites)
    body = f"""<div class="hero"><div class="w">
<span class="tag">Local websites, Maryland</span>
<h1>Your website is already built. Look before you pay.</h1>
<p class="lede">We make a finished, phone-first site for local businesses that don't have one: your hours, phone, address and a map. You see it first. Say yes and it can be live within 24 hours.</p>
<div class="row">{call_btn(c)}{mail_btn(c)}<a class="btn alt" href="work.html">See the work</a></div>
</div></div>
<section><div class="w"><h2>How it works</h2><ol class="steps">
<li><b>We build it first.</b> A real, working site made from your public business listing. No cost, no obligation.</li>
<li><b>You look at it on your phone.</b> The link is on the card or email you got. Change anything you like.</li>
<li><b>You say yes.</b> Pick a plan below. We add your words, logo and photos.</li>
<li><b>It goes live on your own domain.</b> The domain is in your name. We look after hosting and small edits every month.</li>
</ol></div></section>
<section><div class="w"><h2>Pricing, in plain numbers</h2><div class="grid">{pkg_cards()}</div>
<p class="muted" style="margin-top:12px">50% to start, the rest the day it goes live. Monthly plans stop with 30 days notice. Full terms on the <a href="pricing.html">pricing page</a>.</p></div></section>
<section><div class="w"><h2>Where we work</h2><p class="muted">We have made {total:,} sample sites for local businesses in {len(towns)} Maryland towns that list no website on OpenStreetMap.</p>
<div class="grid">{"".join(f'<a class="card shot" href="{a}"><h3>{esc(t)}</h3><p>{esc(TRADE[n][0].capitalize())} and more</p></a>' for (t, n, _k, _a, _c), a in zip(tt, towns.values()))}</div></div></section>
<section><div class="w"><h2>Questions?</h2><p>Read the <a href="faq.html">FAQ</a>, or just call or email. A person answers email; calls go to our assistant, which takes a message.</p>
<div class="row">{call_btn(c)}{mail_btn(c)}</div></div></section>"""
    files["index.html"] = page(c, "index.html", f"{c.name}: websites for local businesses in Maryland",
                               "Fast, phone-first websites for local Maryland businesses. We build it first; you look before you pay.", body, towns)
    # ---- work
    pf = portfolio(sites)
    cards = "".join(f'<a class="card shot" href="{c.prefix}f/{s["path"].split("/")[1]}/" rel="noopener"><span class="k">{esc(F.NICHES[s["niche"]]["label"])} · {esc(s["town"])}</span>'
                    f'<h3>{esc(s["name"])}</h3><p>{esc(s["kind"])}: a sample site made from the public listing.</p></a>' for s in pf)
    body = f"""<div class="hero"><div class="w"><span class="tag">Work</span><h1>Sample sites, by trade</h1>
<p class="lede">Each of these is a real sample we built for a local business from its public listing, before talking to them. They are concepts, not live sites, and the businesses have not endorsed us. Tap one on your phone.</p></div></div>
<section><div class="w"><div class="grid">{cards}</div>
<p class="muted" style="margin-top:14px">Every sample is built the same way: phone first, loads in about a second, tap-to-call, hours, map. Your finished site adds your own words, logo and photos.</p></div></section>"""
    files["work.html"] = page(c, "work.html", f"Sample websites by trade | {c.name}", "Sample websites we built for local Maryland businesses, by trade.", body, towns)
    # ---- pricing
    tl = "".join(f'<details><summary>{esc(t["title"])}</summary><p>{esc(t["text"])}</p></details>' for t in terms)
    body = f"""<div class="hero"><div class="w"><span class="tag">Pricing</span><h1>Clear prices, no surprises</h1>
<p class="lede">Three ways to start. Every plan keeps your domain and your Google profile in your name.</p></div></div>
<section><div class="w"><div class="grid">{pkg_cards()}</div></div></section>
<section><div class="w"><h2>Terms</h2>{tl}</div></section>
<section><div class="w"><div class="row">{call_btn(c)}{mail_btn(c, "Pricing question")}</div></div></section>"""
    files["pricing.html"] = page(c, "pricing.html", f"Pricing | {c.name}", "Starter site $1,500 + $79/month, or $149/month with nothing upfront, or the Call engine.", body, towns)
    # ---- faq
    faq = [
        ("Why did you build a site for my business without asking?", "Because it is easier to decide when you can see it. It costs you nothing and nothing goes live without your yes. If you don't want it, tell us and we take it down."),
        ("Where did you get my business details?", "From public map listings (OpenStreetMap): your name, phone, address and hours as they are listed there. If something is wrong, we fix it."),
        ("Who owns the domain and the site?", "You do. The domain is bought in your name. Once paid in full, your words, photos and logo are yours."),
        ("How fast can it go live?", "The sample is already built. After your yes and your photos and words, the finished site can be live within 24 hours on a free address, and on your own domain as soon as it is connected (usually the same day)."),
        ("What does the care plan cover?", "Hosting, security updates, keeping your hours and details current, and small edits each month."),
        ("Can I stop the monthly plan?", "Yes, with 30 days notice. The Call engine has a 3-month minimum. If you stop, we hand the site over or switch it off after 30 days."),
        ("Do you write fake reviews or buy ads for me?", "No. We never write reviews. The Call engine sends your real customers a polite review request that you approve."),
        ("Do you call businesses with robocalls?", "No. We never use auto-dialers or recorded calls. Calls to our number are answered by our assistant, which takes a message for a person."),
    ]
    q = "".join(f"<details><summary>{esc(a)}</summary><p>{esc(b)}</p></details>" for a, b in faq)
    ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": a, "acceptedAnswer": {"@type": "Answer", "text": b}} for a, b in faq]}
    body = f"""<div class="hero"><div class="w"><span class="tag">FAQ</span><h1>Straight answers</h1></div></div>
<section><div class="w">{q}<div class="row" style="margin-top:16px">{call_btn(c)}{mail_btn(c, "A question")}</div></div></section>"""
    files["faq.html"] = page(c, "faq.html", f"FAQ | {c.name}", "Answers about our sample sites, pricing, ownership and the care plan.", body, towns,
                             extra_head='<script type="application/ld+json">' + json.dumps(ld, separators=(",", ":")).replace("</", "<\\/") + "</script>")
    # ---- contact (no paid form service: mailto + phone)
    body = f"""<div class="hero"><div class="w"><span class="tag">Contact</span><h1>Talk to us</h1>
<p class="lede">Email is the fastest way to reach a person. Calls go to our assistant, which takes your message. If you got a card from us, include the code on it (like FR-27) so we pull up your sample site.</p>
<div class="row">{mail_btn(c, "A website for my business", alt=False)}{call_btn(c, alt=True)}</div></div></div>
<section><div class="w"><h2>Not interested?</h2><p>Email us "remove" with your business name and we take your sample site down and never contact you again.</p>
<div class="row"><a class="btn alt" href="mailto:{esc(c.email)}?subject=Remove%20my%20business">Email "remove"</a></div></div></section>"""
    files["contact.html"] = page(c, "contact.html", f"Contact | {c.name}", "Email or call us about a website for your business.", body, towns)
    # ---- 16 local pages
    for (t, n, k, alln, cnt), a in zip(tt, towns.values()):
        plural, one, wants = TRADE[n]
        others = ", ".join(f"{v} {TRADE[x][0]}" for x, v in cnt.most_common() if x != n and v)[:200]
        samples = [s for s in pf if s["town"] == t][:2] or sorted([s for s in sites if s["town"] == t and s["niche"] == n],
                                                                  key=lambda s: (not s["phone"], not s["hours"], s["name"].lower()))[:2]
        sm = "".join(f'<a class="card shot" href="../{c.prefix}f/{s["path"].split("/")[1]}/"><span class="k">{esc(s["kind"])}</span><h3>{esc(s["name"])}</h3>'
                     f'<p>A sample site made from the public listing (a concept, not endorsed by the business).</p></a>' for s in samples)
        body = f"""<div class="hero"><div class="w"><span class="tag">{esc(t)}, MD</span><h1>Website design for {esc(plural)} in {esc(t)}, MD</h1>
<p class="lede">People in {esc(t)} look up a {esc(one)} on their phone before they call or drive over. If the map shows no website, many pick the next one that has one.</p>
<div class="row">{call_btn(c)}{mail_btn(c, f"A website for my {one} in {t}")}</div></div></div>
<section><div class="w"><h2>The local picture</h2><div class="grid">
<div class="card"><div class="stat">{k}</div><p>{esc(plural)} in and around {esc(t)} list no website on OpenStreetMap (our count, {esc(F.NICHES.get(n, {}).get("label", ""))} only).</p></div>
<div class="card"><div class="stat">{alln}</div><p>local businesses in total around {esc(t)} with no website listed{(": " + esc(others)) if others else ""}.</p></div></div>
<p class="muted" style="margin-top:10px">Map listings are not always up to date, so some of these may have a site the map doesn't know about.</p></div></section>
<section><div class="w"><h2>What a {esc(one)} website needs</h2><p>Visitors to a {esc(one)} site usually want, in this order:</p>
<ol class="steps">{"".join(f"<li>{esc(w[0].upper() + w[1:])}.</li>" for w in wants)}</ol>
<p style="margin-top:14px">So that is what we put first, on one fast page that works on any phone, with a big tap-to-call button and directions that open the map. Extra pages (services, about, contact) come after, only if they help.</p></div></section>
<section><div class="w"><h2>Built the same way for every {esc(one)}</h2><div class="grid">
<div class="card"><h3>Phone first</h3><p>Most local searches happen on a phone. Big text, big buttons, no pinching.</p></div>
<div class="card"><h3>Fast</h3><p>No heavy themes or plug-ins: pages load in about a second, even on a weak signal.</p></div>
<div class="card"><h3>Your details right</h3><p>Hours, phone and address match your Google profile, so customers and search engines see one story.</p></div></div></div></section>
{f'<section><div class="w"><h2>Samples from {esc(t)}</h2><div class="grid">{sm}</div></div></section>' if sm else ""}
<section><div class="w"><h2>Price</h2><p>Starter site ${st.get("price", 1500):,} + ${st.get("monthly", 79)}/month care plan, or $149/month with nothing upfront. <a href="../pricing.html">All prices and terms</a>.</p>
<div class="row">{call_btn(c)}{mail_btn(c, f"A website for my {one} in {t}")}</div></div></section>"""
        body = body.replace('href="contact.html"', 'href="../contact.html"').replace('href="work.html"', 'href="../work.html"')
        files[a] = page(c, a, f"Website design for {plural} in {t}, MD | {c.name}",
                        f"Phone-first websites for {plural} in {t}, Maryland. {k} local {plural} list no website on the map. See a sample first.",
                        body, towns, depth=1)
    # ---- area index, sitemap, robots
    body = f"""<div class="hero"><div class="w"><span class="tag">Areas</span><h1>Where we work</h1></div></div>
<section><div class="w"><div class="grid">{"".join(f'<a class="card shot" href="../{a}"><h3>{esc(t)}, MD</h3><p>Website design for {esc(TRADE[n][0])}</p></a>' for (t, n, _k, _a, _c), a in zip(tt, towns.values()))}</div></div></section>"""
    files["areas/index.html"] = page(c, "areas/index.html", f"Areas we serve | {c.name}", "Maryland towns where we build websites for local businesses.", body, towns, depth=1)
    urls = ["", "work.html", "pricing.html", "faq.html", "contact.html", "areas/index.html"] + list(towns.values())
    files["sitemap.xml"] = ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                            + "".join(f"  <url><loc>{esc(c.base + u)}</loc></url>\n" for u in urls) + "</urlset>\n")
    return files


def write(out=OUT, prefix="../"):
    files = build_files(prefix=prefix)
    if os.path.isdir(out):
        import shutil
        shutil.rmtree(out)
    for k, v in files.items():
        p = os.path.join(out, *k.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(v)
    return files


if __name__ == "__main__":
    fs = write()
    print(f"agency site: {len(fs)} files in {os.path.relpath(OUT, ROOT)} ({sum(len(v) for v in fs.values()) // 1024} KB)")
