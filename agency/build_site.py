"""SITE GENERATOR: a fast, mobile-first website for one business, from a lead (or an owner-edited site.json).

    python -m agency.build_site --leads agency/demo/fort-collins/leads.json --id n123        a DEMO (preview bar, not indexed)
    python -m agency.build_site --site agency/out/.../cinco-brothers/site.json --final        the client's LIVE site
    python -m agency.build_site --leads FILE --all-templates --out DIR                        the same lead in every template

Writes <out>/<slug>/site/ (index.html, site.js, favicon.svg, thanks.html, 404.html, robots.txt, _headers; with --pages 3
also services.html and contact.html), <out>/<slug>/<slug>.zip, <out>/<slug>/site.json (edit it, then build again with
--site) and <out>/<slug>/check.json (the self-check). Nothing is fetched: CSS and the pictures are inline, the only
script is the site's own small site.js, and there are no web fonts, photos or trackers.
Netlify Drop takes the site/ FOLDER (its docs: unzip a zip first); Cloudflare Pages' drag and drop takes the zip.
The contact form uses Netlify Forms attributes (free and unlimited on Netlify's credit plans; switch on Forms > Enable
form detection once, then drop the folder again), or "form": "formspree:<id>" / "none" in agency/config.json.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import string
import sys
import zipfile

from . import ATTRIBUTION, OUT_DIR, TEMPLATES, ensure_dir
from . import categories as C
from . import config as CFG
from . import hours as H
from . import sitecheck
from .osm import phone_parts

TZ = {"AL": "America/Chicago", "AK": "America/Anchorage", "AZ": "America/Phoenix", "AR": "America/Chicago", "CA": "America/Los_Angeles", "CO": "America/Denver",
      "CT": "America/New_York", "DE": "America/New_York", "DC": "America/New_York", "FL": "America/New_York", "GA": "America/New_York", "HI": "Pacific/Honolulu",
      "ID": "America/Boise", "IL": "America/Chicago", "IN": "America/Indiana/Indianapolis", "IA": "America/Chicago", "KS": "America/Chicago", "KY": "America/New_York",
      "LA": "America/Chicago", "ME": "America/New_York", "MD": "America/New_York", "MA": "America/New_York", "MI": "America/Detroit", "MN": "America/Chicago",
      "MS": "America/Chicago", "MO": "America/Chicago", "MT": "America/Denver", "NE": "America/Chicago", "NV": "America/Los_Angeles", "NH": "America/New_York",
      "NJ": "America/New_York", "NM": "America/Denver", "NY": "America/New_York", "NC": "America/New_York", "ND": "America/Chicago", "OH": "America/New_York",
      "OK": "America/Chicago", "OR": "America/Los_Angeles", "PA": "America/New_York", "RI": "America/New_York", "SC": "America/New_York", "SD": "America/Chicago",
      "TN": "America/Chicago", "TX": "America/Chicago", "UT": "America/Denver", "VT": "America/New_York", "VA": "America/New_York", "WA": "America/Los_Angeles",
      "WV": "America/New_York", "WI": "America/Chicago", "WY": "America/Denver", "PR": "America/Puerto_Rico"}
SKIP_WORDS = {"the", "and", "of", "a", "an", "&", "llc", "inc", "co", "dds", "pc"}
TEMPLATE_IDS = ("studio", "bloom", "pro", "table", "clinic", "garage", "fresh", "pulse")


def _read(*parts):
    with open(os.path.join(TEMPLATES, *parts), encoding="utf-8") as fh:
        return fh.read()


def _json(*parts):
    return json.loads(_read(*parts))


THEMES = _json("themes.json")["themes"]
CONTRAST = _json("themes.json")["contrast_pairs"]
TRADES = _json("trades.json")
ICONS = _json("icons.json")


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def icon(name, cls="ico", label=None) -> str:
    inner = ICONS.get(name) or ICONS["check"]
    a11y = f'role="img" aria-label="{esc(label)}"' if label else 'aria-hidden="true"'
    return (f'<svg class="{cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
            f'stroke-linejoin="round" {a11y} focusable="false">{inner}</svg>')


def initials(name: str) -> str:
    words = [w for w in re.findall(r"[A-Za-z0-9']+", name) if w.lower() not in SKIP_WORDS]
    letters = "".join(w[0] for w in words[:2]).upper()
    return letters or (name[:1].upper() or "S")


def fill(text: str, ctx: dict) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: str(ctx.get(m.group(1), m.group(0))), text or "")


# ------------------------------------------------------------------------------------------------ lead -> site.json (the owner can edit it)
def site_from_lead(lead: dict, cfg: dict, template=None) -> dict:
    cat = C.BY_KEY.get(lead.get("category"), C.BY_KEY["restaurant"])
    trade = dict(TRADES["default"])
    trade.update(TRADES.get(cat.key, {}))
    addr = lead.get("address") or {}
    city = addr.get("city") or "your town"
    cuisine = (lead.get("cuisine") or "").split(",")[0].strip()
    ctx = {"name": lead["name"], "city": city, "street": addr.get("street") or city, "label": cat.label, "label_lower": cat.label.lower(),
           "cuisine": cuisine, "cuisine_title": (cuisine.title() + " food") if cuisine else trade.get("cuisine_default", "Good food")}
    parsed = H.parse(lead.get("opening_hours", ""))
    open_days = sum(1 for d in parsed["week"] if d) if parsed["ok"] else 0
    why = []
    if addr.get("street_line"):
        why.append({"title": f"Right here in {city}", "line": addr["street_line"], "icon": "pin"})
    if open_days:
        why.append({"title": f"Open {open_days} days a week" if open_days < 7 else "Open every day", "line": "See today's hours below.", "icon": "clock"})
    if lead.get("phone"):
        why.append({"title": "Call us", "line": f"{lead['phone']}, during opening hours.", "icon": "phone"})
    why.append({"title": "Easy to reach", "line": "Send a message with the form below.", "icon": "chat"})
    ds = cfg.get("demo_sites") or {}
    slug = lead.get("slug") or "business"
    return {
        "v": 1, "slug": slug, "theme": template or cat.template, "made": dt.date.today().isoformat(),
        "business": {"name": lead["name"], "trade": cat.key, "trade_label": cat.label, "schema": cat.schema, "city": city, "state": addr.get("state", ""),
                     "street_line": addr.get("street_line", ""), "address_line": addr.get("line", ""), "postcode": (addr.get("postcode") or "").split("-")[0],
                     "phone": lead.get("phone", ""), "phone_e164": lead.get("phone_e164", ""), "email": lead.get("email", ""), "old_website": lead.get("website", ""),
                     "facebook": lead.get("facebook", ""), "instagram": lead.get("instagram", ""), "lat": lead.get("lat"), "lon": lead.get("lon"),
                     "tz": TZ.get((addr.get("state") or "").upper(), ""), "cuisine": cuisine},
        "hours": {"raw": parsed["raw"], "ok": parsed["ok"], "week": parsed["week"]},
        "copy": {"headline": fill(trade["headline"], ctx), "sub": fill(trade["sub"], ctx), "about": fill(trade["about"], ctx), "cta": trade["cta"], "cta_kind": trade["cta_kind"],
                 "form_title": trade["form_title"], "form_need": trade["form_need"], "kicker": f"{cat.label} in {city}",
                 "services": [{"title": t, "line": fill(l, ctx), "icon": i} for t, l, i in trade["services"]], "why": why},
        "agency": {k: (cfg.get("agency") or {}).get(k, "") for k in ("name", "your_name", "phone", "email", "website")},
        "form": ds.get("form", "netlify"), "pages": int(ds.get("pages", 1)),
        "demo_url": (ds.get("url_pattern") or "https://{slug}-demo.netlify.app").replace("{slug}", slug),
        "live_url": "", "source": {"osm_url": lead.get("osm_url", ""), "lead_id": lead.get("id", ""), "attribution": ATTRIBUTION},
    }


# ------------------------------------------------------------------------------------------------ site.json -> files
def maps_links(b: dict):
    q = ", ".join(x for x in (b["name"], b.get("address_line") or b.get("city")) if x)
    from urllib.parse import quote
    google = "https://www.google.com/maps/search/?api=1&query=" + quote(q)
    apple = "https://maps.apple.com/?q=" + quote(b["name"]) + (f"&ll={b['lat']},{b['lon']}" if b.get("lat") is not None else "&address=" + quote(q))
    return google, apple


def css_for(site: dict) -> str:
    th = THEMES[site["theme"]]
    p = th["palette"]
    tokens = ";".join(f"--{k.replace('_', '-')}:{v}" for k, v in p.items())
    art = ";".join(f"--art{i + 1}:{c}" for i, c in enumerate(th["art"]))
    root = f":root{{{tokens};{art};--display:{th['display']};--body:{th['body']};--radius:{th['radius']}}}"
    css = root + "\n" + _read("base.css") + "\n" + _read("themes", site["theme"] + ".css")
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)                       # comments out: smaller page
    css = re.sub(r"\n\s*\n+", "\n", css)
    return css.strip()


def jsonld(site: dict, url: str) -> str:
    b = site["business"]
    d = {"@context": "https://schema.org", "@type": b["schema"], "name": b["name"]}
    if url:
        d["url"] = url
    if b.get("phone_e164"):
        d["telephone"] = b["phone_e164"]
    if b.get("street_line") or b.get("city"):
        d["address"] = {"@type": "PostalAddress", "streetAddress": b.get("street_line", ""), "addressLocality": b.get("city", ""), "addressRegion": b.get("state", ""),
                        "postalCode": b.get("postcode", ""), "addressCountry": "US"}
    if b.get("lat") is not None:
        d["geo"] = {"@type": "GeoCoordinates", "latitude": b["lat"], "longitude": b["lon"]}
    spec = H.schema_spec(site["hours"]) if site["hours"].get("ok") else []
    if spec:
        d["openingHoursSpecification"] = spec
    if b.get("cuisine") and b["schema"] in ("Restaurant", "CafeOrCoffeeShop", "Bakery"):
        d["servesCuisine"] = b["cuisine"].title()
    same = [u for u in (b.get("facebook"), b.get("instagram")) if u and u.startswith("https://")]
    if same:
        d["sameAs"] = same
    return json.dumps(d, ensure_ascii=False).replace("</", "<\\/")


def hours_table(site: dict) -> str:
    hrs = site["hours"]
    if not hrs.get("ok"):
        raw = f'<p class="fine">Listed as: {esc(hrs["raw"])}</p>' if hrs.get("raw") else ""
        return f'<p>Call us for today\'s hours.</p>{raw}'
    rows, week, i = [], hrs["week"], 0
    while i < 7:
        j = i
        while j + 1 < 7 and week[j + 1] == week[i]:
            j += 1
        label = H.NAMES[i] if i == j else f"{H.NAMES[i]} - {H.NAMES[j]}"
        text = ", ".join(H.span(t) for t in week[i]) if week[i] else "Closed"
        days = ",".join(str(k) for k in range(i, j + 1))
        rows.append(f'<tr data-days="{days}"><th scope="row">{esc(label)}</th><td>{esc(text)}</td></tr>')
        i = j + 1
    return f'<table class="hours"><caption class="sr">Opening hours</caption><tbody>{"".join(rows)}</tbody></table>'


def form_html(site: dict, mode: str) -> str:
    c, kind = site["copy"], site.get("form", "netlify")
    if kind == "none":
        return ""
    attrs = 'name="contact" method="POST" action="thanks.html"'
    if kind == "netlify":
        attrs += ' data-netlify="true" netlify-honeypot="company"'
    elif kind.startswith("formspree:"):
        attrs = f'name="contact" method="POST" action="https://formspree.io/f/{esc(kind.split(":", 1)[1])}"'
    if mode == "demo":
        attrs += ' data-preview="1"'
    options = "".join(f"<option>{esc(s['title'])}</option>" for s in c["services"]) + "<option>Something else</option>"
    return f"""<form class="form" {attrs}>
<input type="hidden" name="form-name" value="contact">
<p class="hp"><label>Leave this empty <input name="company" tabindex="-1" autocomplete="off"></label></p>
<h3>{esc(c['form_title'])}</h3>
<div class="two"><div class="field"><label for="f-name">Your name</label><input id="f-name" name="name" autocomplete="name" required></div>
<div class="field"><label for="f-phone">Phone</label><input id="f-phone" name="phone" type="tel" inputmode="tel" autocomplete="tel" required></div></div>
<div class="field"><label for="f-email">Email (optional)</label><input id="f-email" name="email" type="email" autocomplete="email"></div>
<div class="field"><label for="f-need">{esc(c['form_need'])}</label><select id="f-need" name="service">{options}</select></div>
<div class="field"><label for="f-msg">Message</label><textarea id="f-msg" name="message" rows="4"></textarea></div>
<button class="btn primary" type="submit">{icon('arrow')}Send</button>
<p class="fine">We only use your details to answer you.</p>
<p class="formmsg" id="formmsg" role="status" aria-live="polite"></p>
</form>"""


def page_parts(site: dict, mode: str, pages: int, page: str = "index"):
    b, c = site["business"], site["copy"]
    google, apple = maps_links(b)
    tel = f"tel:{b['phone_e164']}" if b.get("phone_e164") else ""
    href = (lambda anchor, pg: f"#{anchor}") if pages == 1 else (lambda anchor, pg: f"{pg}.html#{anchor}" if pg != page else f"#{anchor}")
    nav_items = [("services", "Services", "services"), ("hours", "Hours", "index"), ("reviews", "Reviews", "index"), ("contact", "Contact", "contact")]
    nav = "".join(f'<a href="{href(a, pg if pages > 1 else "index")}">{esc(t)}</a>' for a, t, pg in nav_items)
    header_call = (f'<a class="btn primary small call" href="{tel}">{icon("phone")}<span class="lbl">Call</span><span class="sr"> {esc(b["name"])}</span></a>' if tel
                   else f'<a class="btn primary small call" href="{href("contact", "contact")}">{icon("chat")}<span class="lbl">Message</span></a>')
    to_form = href("contact", "contact")
    directions = f'<a class="btn ghost" href="{esc(google)}" rel="noopener">{icon("directions")}Directions</a>'
    if c["cta_kind"] == "quote":                       # trades: the form is the main ask, the phone right next to it
        primary = f'<a class="btn primary" href="{to_form}">{icon("calendar")}Ask for a quote</a>'
        second = f'<a class="btn ghost" href="{tel}">{icon("phone")}Call {esc(b["phone"])}</a>' if tel else directions
    elif tel:                                          # call / book / order: one tap to call
        primary = f'<a class="btn primary" href="{tel}">{icon("phone")}{esc(c["cta"])}</a>'
        second = directions
    else:                                              # no phone on file: the form, then the map
        primary = f'<a class="btn primary" href="{to_form}">{icon("chat")}Send a message</a>'
        second = directions
    facts = []
    if site["hours"].get("ok"):
        facts.append(f'<li><span data-open class="state">See today\'s hours</span></li>')
    if b.get("street_line"):
        facts.append(f'<li>{icon("pin")}{esc(b["street_line"])}</li>')
    if b.get("phone"):
        facts.append(f'<li>{icon("phone")}<a class="factlink" href="{tel}">{esc(b["phone"])}</a></li>')
    art = _read("art", site["theme"] + ".svg").strip().replace("<svg ", f'<svg role="img" aria-label="{esc(b["trade_label"])} illustration" ', 1)
    bigphone = (f'<a class="bigphone" href="{tel}"><small>Call us</small>{esc(b["phone"])}</a>' if tel and site["theme"] == "pro" else "")
    headline = esc(c["headline"])
    hero = f"""<section class="hero" aria-labelledby="h-title"><div class="wrap">
<div class="copy"><p class="eyebrow">{esc(c['kicker'])}</p><h1 id="h-title">{headline}</h1><p class="lead">{esc(c['sub'])}</p>
<div class="actions">{primary}{second}</div>{bigphone}
<ul class="facts">{''.join(facts)}</ul></div>
<div class="art">{art}</div>
</div></section>"""
    services = "".join(f'<li class="card"><span class="ic">{icon(s["icon"])}</span><h3>{esc(s["title"])}</h3><p>{esc(s["line"])}</p></li>' for s in c["services"])
    sec_services = f"""<section class="section" id="services" aria-labelledby="h-services"><div class="wrap">
<span class="kicker">What we do</span><h2 id="h-services">Services</h2><p class="intro">{esc(c['about'])}</p>
<ul class="cards">{services}</ul></div></section>"""
    why = "".join(f'<li>{icon(w["icon"])}<div><b>{esc(w["title"])}</b><span>{esc(w["line"])}</span></div></li>' for w in c["why"])
    sec_why = f"""<section class="section alt" aria-labelledby="h-why"><div class="wrap">
<span class="kicker">Why {esc(b['name'])}</span><h2 id="h-why">Easy to find, easy to reach</h2>
<ul class="why">{why}</ul></div></section>"""
    addr = esc(b.get("address_line") or b.get("city"))
    sec_visit = f"""<section class="section" id="hours" aria-labelledby="h-visit"><div class="wrap">
<span class="kicker">Visit</span><h2 id="h-visit">Hours and directions</h2>
<div class="visit"><div class="panel"><h3>{icon('clock')}Opening hours</h3>{hours_table(site)}</div>
<div class="panel"><div class="mapart" role="img" aria-label="Map pin"><span class="pin"></span></div><p class="addr">{addr}</p>
<div class="row"><a class="btn primary" href="{esc(google)}" rel="noopener">{icon('directions')}Get directions</a><a class="btn ghost" href="{esc(apple)}" rel="noopener">Apple Maps</a></div></div></div>
</div></section>"""
    samples = [("Exactly what I needed, and friendly too.", "Sample review"), ("Easy to book and right on time.", "Sample review"), ("My go-to place in town.", "Sample review")]
    stars = "".join(icon("star") for _ in range(5))
    reviews = "".join(f'<li class="sample"><span class="tag">Sample</span><div class="stars" role="img" aria-label="5 stars (sample)">{stars}</div><p>"{esc(t)}"</p><cite>{esc(w)}</cite></li>' for t, w in samples)
    sec_reviews = f"""<section class="section alt" id="reviews" aria-labelledby="h-reviews"><div class="wrap">
<span class="kicker">Reviews</span><h2 id="h-reviews">What customers say</h2>
<p class="notice">{icon('star')}<span><b>These are sample reviews, not real ones.</b> Your real Google reviews go here once the site is yours.</span></p>
<ul class="reviews">{reviews}</ul></div></section>"""
    direct = []
    if tel:
        direct.append(f'<a class="line" href="{tel}">{icon("phone")}<span>{esc(b["phone"])}<small>Call us</small></span></a>')
    if b.get("email"):
        direct.append(f'<a class="line" href="mailto:{esc(b["email"])}">{icon("mail")}<span>{esc(b["email"])}<small>Email us</small></span></a>')
    direct.append(f'<a class="line" href="{esc(google)}" rel="noopener">{icon("pin")}<span>{addr}<small>Get directions</small></span></a>')
    sec_contact = f"""<section class="section" id="contact" aria-labelledby="h-contact"><div class="wrap">
<span class="kicker">Contact</span><h2 id="h-contact">Get in touch</h2><p class="intro">Call, or send a message and {esc(b['name'])} gets back to you.</p>
<div class="contact">{form_html(site, mode)}<div class="direct">{''.join(direct)}</div></div></div></section>"""
    return {"hero": hero, "services": sec_services, "why": sec_why, "visit": sec_visit, "reviews": sec_reviews, "contact": sec_contact,
            "nav": nav, "header_call": header_call, "google": google, "tel": tel}


def footer_html(site: dict, mode: str, parts: dict) -> str:
    b, a = site["business"], site["agency"]
    year = dt.date.today().year
    hrs = H.summary(site["hours"]) if site["hours"].get("ok") else "Call for hours"
    phone = f'<p><a href="{parts["tel"]}">{esc(b["phone"])}</a></p>' if parts["tel"] else ""
    credit_name = esc(a.get("name") or "a local web designer")
    credit = f'Website by {credit_name}' + (f' · <a href="{esc(a["website"])}" rel="noopener">{esc(a["website"].split("//")[-1].rstrip("/"))}</a>' if a.get("website") else "")
    osm = f' · Listing details from <a href="https://www.openstreetmap.org/copyright" rel="noopener">OpenStreetMap</a>' if mode == "demo" else ""
    return f"""<div class="wrap"><div><h2>{esc(b['name'])}</h2><p>{esc(b['trade_label'])} in {esc(b['city'])}</p></div>
<div><h2>Visit</h2><p>{esc(b.get('address_line') or b.get('city'))}</p>{phone}</div>
<div><h2>Hours</h2><p>{esc(hrs)}</p></div></div>
<div class="credit"><div class="wrap"><span>&copy; {year} {esc(b['name'])}</span><span>{credit}{osm}</span></div></div>"""


def demo_bar(site: dict) -> str:
    a, b = site["agency"], site["business"]
    who = esc(a.get("name") or "a local web designer")
    e164 = phone_parts(a.get("phone", ""))[1]
    phone = f' · <a href="tel:{esc(e164)}">{esc(a["phone"])}</a>' if e164 else ""
    return (f'<div class="demo" role="note"><b>Preview</b> made for {esc(b["name"])} by {who}{phone}. Not the official site yet: '
            f'text and reviews are placeholders until you approve them.</div>\n')


def render(site: dict, mode: str = "demo", pages: int | None = None, url: str = "") -> dict:
    """site.json -> {relative path: text}. mode 'demo' = preview bar + not indexed + the form does not post; 'final' = the live site."""
    if site["theme"] not in THEMES:
        raise ValueError(f"unknown template '{site['theme']}' (one of {', '.join(TEMPLATE_IDS)})")
    pages = pages or int(site.get("pages", 1))
    b, c = site["business"], site["copy"]
    url = url or (site.get("live_url") if mode == "final" else "") or ""
    th = THEMES[site["theme"]]
    css = css_for(site)
    page_tpl = string.Template(_read("page.html"))
    title_base = f"{b['name']} | {b['trade_label']} in {b['city']}"
    desc = f"{c['sub']} {('Call ' + b['phone'] + '.') if b.get('phone') else ''}".strip()
    desc = (desc[:157] + "...") if len(desc) > 160 else desc
    site_data = json.dumps({"tz": b.get("tz", ""), "week": site["hours"]["week"] if site["hours"].get("ok") else None}).replace("</", "<\\/")
    files = {}

    def page(name, main_html, title, parts):
        callbar = []
        if parts["tel"]:
            callbar.append(f'<a class="btn primary" href="{parts["tel"]}">{icon("phone")}Call</a>')
        callbar.append(f'<a class="btn ghost" href="{esc(parts["google"])}" rel="noopener">{icon("directions")}Directions</a>')
        if not parts["tel"]:
            callbar.append(f'<a class="btn primary" href="{"#contact" if pages == 1 else "contact.html#contact"}">{icon("chat")}Message</a>')
        return page_tpl.substitute(
            title=esc(title), description=esc(desc), robots="noindex, nofollow" if mode == "demo" else "index, follow", theme_color=th["palette"]["bg"],
            canonical=(f'<link rel="canonical" href="{esc(url.rstrip("/") + "/" + ("" if name == "index" else name + ".html"))}">\n' if (url and mode == "final") else ""),
            css=css, jsonld=jsonld(site, url), demo_bar=demo_bar(site) if mode == "demo" else "", home_href="./" if pages == 1 else "index.html",
            initials=esc(initials(b["name"])), name=esc(b["name"]), nav=parts["nav"], header_call=parts["header_call"], menu_icon=icon("menu"),
            main=main_html, footer=footer_html(site, mode, parts), callbar="".join(callbar), site_data=site_data)

    p = page_parts(site, mode, pages, "index")
    if pages == 1:
        files["index.html"] = page("index", "\n".join(p[k] for k in ("hero", "services", "why", "visit", "reviews", "contact")), title_base, p)
    else:
        files["index.html"] = page("index", "\n".join(p[k] for k in ("hero", "services", "why", "visit", "reviews")), title_base, p)
        def head(title, sub):                          # every page has its own h1
            return (f'<section class="hero pagehead" aria-labelledby="h-title"><div class="wrap"><div class="copy"><p class="eyebrow">{esc(c["kicker"])}</p>'
                    f'<h1 id="h-title">{esc(title)}</h1><p class="lead">{esc(sub)}</p></div></div></section>')
        ps = page_parts(site, mode, pages, "services")
        files["services.html"] = page("services", head(f"Services at {b['name']}", c["about"]) + ps["services"] + ps["why"], f"Services | {b['name']}", ps)
        pc = page_parts(site, mode, pages, "contact")
        files["contact.html"] = page("contact", head("Contact and directions", f"Call, write or visit {b['name']}.") + pc["contact"] + pc["visit"], f"Contact | {b['name']}", pc)
    simple = lambda h1, txt: f"""<section class="simple"><div><h1>{esc(h1)}</h1><p>{esc(txt)}</p><div class="row">
{f'<a class="btn primary" href="{p["tel"]}">{icon("phone")}Call {esc(b["phone"])}</a>' if p["tel"] else ''}<a class="btn ghost" href="index.html">Back to the home page</a></div></div></section>"""
    files["thanks.html"] = page("thanks", simple("Thank you", f"Your message is on its way to {b['name']}. We will get back to you soon."), f"Thank you | {b['name']}", p)
    nf = page("404", simple("Page not found", "That page does not exist. The home page has everything."), f"Not found | {b['name']}", p)
    # a 404 is served at any depth (/a/b/c): every link and file of it must start at the site root
    nf = nf.replace('href="favicon.svg"', 'href="/favicon.svg"').replace('src="site.js"', 'src="/site.js"').replace('href="index.html"', 'href="/"')
    files["404.html"] = re.sub(r'href="(#[^"]*|[a-z]+\.html#[^"]*)"', lambda m: f'href="/{m.group(1)}"', nf).replace('href="./"', 'href="/"')
    files["site.js"] = _read("site.js")
    th_p = th["palette"]
    files["favicon.svg"] = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="{th_p["accent"]}"/>'
                            f'<text x="32" y="41" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-size="26" font-weight="700" fill="{th_p["accent_ink"]}">{esc(initials(b["name"]))}</text></svg>\n')
    files["robots.txt"] = ("User-agent: *\nDisallow: /\n" if mode == "demo" else "User-agent: *\nAllow: /\n" + (f"Sitemap: {url.rstrip('/')}/sitemap.xml\n" if url else ""))
    form_src = "https://formspree.io" if str(site.get("form", "")).startswith("formspree:") else ""
    files["_headers"] = ("/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n  X-Frame-Options: SAMEORIGIN\n"
                         "  Permissions-Policy: camera=(), microphone=(), geolocation=()\n"
                         f"  Content-Security-Policy: default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; "
                         f"form-action 'self'{(' ' + form_src) if form_src else ''}; frame-ancestors 'self'; base-uri 'self'\n"
                         "/site.js\n  Cache-Control: public, max-age=86400\n")
    if mode == "final" and url:
        pages_list = ["", "services.html", "contact.html"] if pages > 1 else [""]
        files["sitemap.xml"] = ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                + "".join(f"  <url><loc>{esc(url.rstrip('/') + '/' + x)}</loc></url>\n" for x in pages_list) + "</urlset>\n")
    return files


def write_site(site: dict, out_dir: str, mode="demo", pages=None, url="", make_zip=True) -> dict:
    """Write the folder + zip + site.json + check.json. -> {dir, site_dir, zip, check}."""
    files = render(site, mode, pages, url)
    root = ensure_dir(os.path.join(out_dir, site["slug"] + ("" if mode == "demo" else "-live")))
    sdir = ensure_dir(os.path.join(root, "site"))
    for old in os.listdir(sdir):
        if os.path.isfile(os.path.join(sdir, old)) and old not in files:
            os.remove(os.path.join(sdir, old))
    for name, text in files.items():
        with open(os.path.join(sdir, name), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    with open(os.path.join(root, "site.json"), "w", encoding="utf-8") as fh:
        json.dump(site, fh, ensure_ascii=False, indent=1)
    zpath = ""
    if make_zip:
        zpath = os.path.join(root, f"{site['slug']}{'' if mode == 'demo' else '-live'}.zip")
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            for name in sorted(files):                                     # index.html at the top of the zip
                zi = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                zi.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(zi, files[name])
    rep = sitecheck.check_dir(sdir, palette=THEMES[site["theme"]]["palette"], pairs=CONTRAST, mode=mode)
    with open(os.path.join(root, "check.json"), "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=1)
    return {"dir": root, "site_dir": sdir, "zip": zpath, "check": rep}


def load_leads(path):
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    return d.get("leads", d if isinstance(d, list) else [])


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m agency.build_site", description="Build a fast one-page website for a local business.")
    ap.add_argument("--leads", help="a leads.json from agency.leads")
    ap.add_argument("--id", action="append", help="lead id (n123 / w456), repeat for more; default: the first lead")
    ap.add_argument("--site", help="an owner-edited site.json instead of a lead")
    ap.add_argument("--template", choices=TEMPLATE_IDS, help="force a template (default: by trade)")
    ap.add_argument("--all-templates", action="store_true", help="build the lead once in every template (to compare)")
    ap.add_argument("--pages", type=int, choices=(1, 3), help="1 = one page (default), 3 = home + services + contact")
    ap.add_argument("--final", action="store_true", help="the client's live site: no preview bar, indexed, the form posts")
    ap.add_argument("--url", default="", help="the live address with --final (for the canonical link and sitemap)")
    ap.add_argument("--out", default=os.path.join(OUT_DIR, "sites"))
    args = ap.parse_args(argv)
    cfg = CFG.load()
    sites = []
    if args.site:
        with open(args.site, encoding="utf-8") as fh:
            s = json.load(fh)
        s["agency"] = {k: (cfg.get("agency") or {}).get(k, "") for k in ("name", "your_name", "phone", "email", "website")}
        sites.append(s)
    elif args.leads:
        leads = load_leads(args.leads)
        chosen = [l for l in leads if l["id"] in args.id] if args.id else leads[:1]
        if not chosen:
            ap.error("no lead with that --id in " + args.leads)
        for l in chosen:
            if args.all_templates:
                for t in TEMPLATE_IDS:
                    s = site_from_lead(l, cfg, t)
                    s["slug"] = f"{s['slug']}-{t}"
                    sites.append(s)
            else:
                sites.append(site_from_lead(l, cfg, args.template))
    else:
        ap.error("give --leads FILE (with --id) or --site site.json")
    bad = 0
    for s in sites:
        r = write_site(s, args.out, "final" if args.final else "demo", args.pages, args.url)
        sc = r["check"]["scores"]
        print(f"{s['business']['name'][:34]:34} {s['theme']:7} {r['check']['bytes_total'] / 1024:5.1f} KB  perf {sc['performance']:3} a11y {sc['accessibility']:3} "
              f"best {sc['best_practices']:3} seo {sc['seo']:3}  {'OK' if r['check']['ok'] else 'FIX: ' + '; '.join(r['check']['hard_fails'])[:60]}")
        print(f"   folder {r['site_dir']}\n   zip    {r['zip']}")
        bad += 0 if r["check"]["ok"] else 1
    if CFG.placeholders(cfg) and not args.final:
        print("Note: agency/config.json still has placeholders (YOUR AGENCY ...): the preview bar shows them until you fill it in.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
