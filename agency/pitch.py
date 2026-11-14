"""PITCH KIT: for one lead, a one-page pitch (what is wrong today, the demo link, the price), a CAN-SPAM email and a
30-second phone opener. All words come from the lead, its site check and agency/config.json (your name, agency,
phone, email, postal address, prices). Nothing is ever sent or dialled from here: you send and call yourself.

    python -m agency.pitch --leads agency/demo/fort-collins/leads.json --id n12212932147
    -> <out>/<slug>/pitch/pitch.html (print it or send it as a PDF), email.txt, phone.txt, pitch.json

CAN-SPAM (FTC, it covers business-to-business email too): a true From line and subject, a clear line saying it is an
ad, your valid postal address, and an easy opt-out ("reply no thanks") that you honour within 10 business days and that
keeps working for at least 30 days. The email says NOT READY TO SEND at the top until agency/config.json has your real
name, agency, email and postal address. Calls: dial by hand, business hours, honour "do not call" at once.
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

from . import OUT_DIR, TEMPLATES, ensure_dir
from . import categories as C
from . import config as CFG

PROBLEM = {   # reason code -> (short spoken phrase, one sentence for the email)
    "no_site": ("your business doesn't have a website I could find", "I looked for {name} online and couldn't find a website, so people searching for a {trade} in {city} on their phone find other places first."),
    "dead_domain": ("your website address doesn't open any more", "The website address listed for {name} no longer opens, so anyone who clicks it gets an error."),
    "site_down": ("your website wasn't loading when I checked", "When I checked, the {name} website did not open, so people who click it see an error."),
    "parked": ("your web address shows a parked page", "The web address listed for {name} shows a parked 'coming soon' page instead of your business."),
    "social_only": ("you're only on Facebook right now", "{name} is on Facebook, but has no website of its own, so Google has little to show people searching for a {trade} in {city}."),
    "dead_gbp_site": ("your Google business.site page was shut down", "Google shut down the free business.site websites in 2024, and that was the site listed for {name}."),
    "no_viewport": ("your website is hard to use on a phone", "Your current website shows a shrunken desktop page on phones, where most people look for a {trade}."),
    "no_https": ("Chrome marks your website 'Not secure'", "Chrome shows 'Not secure' next to your current website, which makes some people leave."),
    "no_https_redirect": ("visitors land on the 'Not secure' version of your site", "Visitors who type your address land on the 'Not secure' version of the site."),
    "bad_cert": ("your website shows a security warning", "Your current website shows visitors a red security warning."),
    "flash": ("your website uses Flash, which no browser plays now", "Your website still uses Flash, which no browser has played since 2021."),
    "dated": ("your website looks out of date", "Your website footer still shows an old year, so it looks out of date."),
    "slow": ("your website is slow to load", "Your current website takes a long time to load, and many people give up after a few seconds."),
    "no_tel": ("people can't tap to call you from your site", "On a phone, people can't tap your number to call you."),
    "no_cta": ("your site has no clear button to call or book", "Your current site has no clear button to call or book."),
}
DEFAULT_PROBLEM = ("your website could bring you more calls", "I think your website could bring {name} more calls with a few changes.")


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def money(x) -> str:
    return f"${float(x):,.0f}"


def main_problem(lead: dict):
    codes = [i["code"] for i in sorted(lead.get("issues") or [], key=lambda i: -i["weight"])]
    for c in codes:
        if c in PROBLEM:
            return c, PROBLEM[c]
    return "other", DEFAULT_PROBLEM


def recommend(lead: dict, cfg: dict) -> dict:
    """High-value trades (value >= 9: roofers, plumbers, HVAC, dentists, auto repair) get the Growth package; others Starter."""
    cat = C.BY_KEY.get(lead.get("category"))
    pid = "growth" if cat and cat.value >= 9 else "starter"
    return CFG.package(cfg, pid)


def context(lead: dict, cfg: dict, demo_url: str) -> dict:
    a = cfg.get("agency") or {}
    cat = C.BY_KEY.get(lead.get("category"), C.BY_KEY["restaurant"])
    city = (lead.get("address") or {}).get("city") or "town"
    pk = recommend(lead, cfg)
    code, (short, sentence) = main_problem(lead)
    fmt = {"name": lead["name"], "trade": cat.label.lower(), "city": city}
    return {
        "name": lead["name"], "trade": cat.label, "trade_lower": cat.label.lower(), "trade_plural": cat.plural, "city": city, "phone_to": lead.get("phone") or "(no phone on file)",
        "demo_url": demo_url, "your_name": a.get("your_name") or "YOUR NAME", "agency": a.get("name") or "YOUR AGENCY", "phone": a.get("phone") or "", "from_email": a.get("email") or "",
        "postal_address": a.get("postal_address") or "YOUR POSTAL ADDRESS", "terms": a.get("terms") or "Month to month: cancel any time.",
        "setup": f"{float(pk.get('setup', 0)):,.0f}", "monthly": f"{float(pk.get('monthly', 0)):,.0f}", "package": pk.get("name", ""), "package_id": pk.get("id", ""),
        "problem_code": code, "problem_short": short.format(**fmt), "problem_sentence": sentence.format(**fmt),
        "to": lead.get("email") or "(find their email on their Facebook page or ask on the phone)", "date": dt.date.today().strftime("%B %d, %Y").replace(" 0", " "),
    }


def opener(ctx: dict) -> str:
    """The 30-second phone opener (at most 80 words: about 30 s at a calm 150 words a minute)."""
    return (f"Hi, is this the owner of {ctx['name']}? Great. My name is {ctx['your_name']}, I make websites for local businesses here in {ctx['city']}. "
            f"I noticed {ctx['problem_short']}, so I built you a free preview of a new website. It's already online, with your hours, tap-to-call and directions. "
            f"Could I email or text you the link so you can take a look?")


def voicemail(ctx: dict) -> str:
    url = re.sub(r"^https?://", "", ctx["demo_url"]).rstrip("/")
    return (f"Hi, this is {ctx['your_name']} with {ctx['agency']}. I made a free preview of a new website for {ctx['name']}. "
            f"You can see it at {url}. If you like it, call me back at {ctx['phone']}. Thanks!")


def words(text: str) -> int:
    return len(text.split())


def subject(ctx: dict) -> str:
    return f"A free website preview for {ctx['name']}"


def email_text(ctx: dict, ready: bool) -> str:
    t = string.Template(open(os.path.join(TEMPLATES, "pitch", "email.txt"), encoding="utf-8").read())
    ready_line = "" if ready else ("NOT READY TO SEND: put your real name, agency, email and postal address in agency/config.json, then build the kit again.\n"
                                   "(US law, CAN-SPAM: a true sender, your postal address and an opt-out in every sales email.)\n")
    body = t.substitute(ready_line=ready_line, to=ctx["to"], your_name=ctx["your_name"], from_email=ctx["from_email"] or "YOUR EMAIL", subject=subject(ctx),
                        agency=ctx["agency"], agency_city=ctx["city"], problem_sentence=ctx["problem_sentence"], name=ctx["name"], demo_url=ctx["demo_url"],
                        setup=ctx["setup"], monthly=ctx["monthly"], terms=ctx["terms"], phone=ctx["phone"] or "YOUR PHONE", postal_address=ctx["postal_address"])
    return body.lstrip("\n")


def phone_text(ctx: dict) -> str:
    op = opener(ctx)
    t = string.Template(open(os.path.join(TEMPLATES, "pitch", "phone.txt"), encoding="utf-8").read())
    return t.substitute(name=ctx["name"], trade=ctx["trade"], city=ctx["city"], phone_to=ctx["phone_to"], words=words(op), seconds=round(words(op) / 2.5),
                        opener=op, voicemail=voicemail(ctx),
                        obj_have="Fair enough. The preview is free either way: keep the link, and if your site ever lets you down you have my number.",
                        obj_price=f"${ctx['setup']} to set it up, then ${ctx['monthly']} a month for hosting, security and small changes. {ctx['terms']}",
                        obj_send="Sure. What's the best email? I'll send the link and one page with the price.",
                        obj_no="No problem at all, thanks for your time. I'll take you off my list. (Then mark it 'Do not contact'.)")


TODAY_TEXT = {
    "no_site": ("No website to find", "Searching for a {trade} in {city} on a phone shows other businesses; there is no site for {name} to tap."),
    "dead_domain": ("The web address is dead", "The address listed for you does not open, so clicks are lost."),
    "site_down": ("The site did not open", "When we checked, the website gave an error."),
    "parked": ("A parked page", "Your address shows a 'coming soon' page instead of your business."),
    "social_only": ("Only on Facebook", "No website of your own: Google has little to show, and not everyone uses Facebook."),
    "dead_gbp_site": ("Google shut your site down", "Google switched off all business.site websites in 2024."),
    "no_viewport": ("Hard to use on a phone", "The site shows a tiny desktop page on phones."),
    "no_https": ("'Not secure' in Chrome", "No padlock: browsers warn visitors."),
    "no_https_redirect": ("Visitors land on 'Not secure'", "The secure version exists but visitors are not sent to it."),
    "bad_cert": ("Security warning", "Visitors see a red warning before the page."),
    "dated": ("Looks out of date", "An old year in the footer tells people the site is not looked after."),
    "slow": ("Slow to load", "People leave when a page takes more than a few seconds."),
    "no_tel": ("No tap-to-call", "On a phone people cannot tap your number."),
    "no_cta": ("No clear next step", "No button to call, book or ask for a quote."),
    "flash": ("Uses Flash", "No browser plays Flash any more."),
    "old_tool": ("Built with an old tool", "Hard to update and slow on phones."),
    "old_html": ("Old-style code", "Built the way sites were made around 2005."),
    "free_subdomain": ("Not on your own name", "The site lives on a free address instead of your own .com."),
}
FEATURES = ["Made for phones first, fast on any connection", "Tap-to-call and one-tap directions", "Your hours, with 'Open now' shown live",
            "A contact form that sends messages to you", "Secure (https) and ready for Google, with your business details built in", "Your real reviews and photos added once you approve"]


def pitch_html(lead: dict, ctx: dict, cfg: dict, ready: bool, palette=None) -> str:
    fmt = {"name": lead["name"], "trade": ctx["trade_lower"], "city": ctx["city"]}
    items = []
    for i in sorted(lead.get("issues") or [], key=lambda i: -i["weight"]):
        if i["code"] in TODAY_TEXT:
            h, t = TODAY_TEXT[i["code"]]
            items.append(f"<li><b>{esc(h.format(**fmt))}</b>{esc(t.format(**fmt))}</li>")
    if not items:
        items.append("<li><b>Room to grow</b>Your current site works; a faster phone-first page can bring more calls.</li>")
    rec = ctx["package_id"]
    rows = []
    for p in cfg.get("packages") or []:
        tag = '<span class="tag">Best fit</span>' if p.get("id") == rec else ""
        rows.append(f'<tr class="{"pick" if p.get("id") == rec else ""}"><td>{esc(p.get("name"))}{tag}</td><td>{money(p.get("setup", 0))}</td><td>{money(p.get("monthly", 0))}</td>'
                    f'<td>{esc("; ".join(p.get("includes", [])[:3]))}</td></tr>')
    pal = palette or {"accent": "#1f4e79", "accent_ink": "#ffffff"}
    warn = "" if ready else '<p class="warn">Placeholders: put your real name, agency, phone, email and postal address in agency/config.json before you hand this out.</p>'
    t = string.Template(open(os.path.join(TEMPLATES, "pitch", "pitch.html"), encoding="utf-8").read())
    return t.substitute(name=esc(lead["name"]), trade=esc(ctx["trade"]), city=esc(ctx["city"]), your_name=esc(ctx["your_name"]), agency=esc(ctx["agency"]), date=esc(ctx["date"]),
                        today="".join(items), features="".join(f"<li>{esc(f)}</li>" for f in FEATURES), demo_url=esc(ctx["demo_url"]),
                        demo_url_text=esc(re.sub(r"^https?://", "", ctx["demo_url"]).rstrip("/")), prices="".join(rows), terms=esc(ctx["terms"]),
                        phone=esc(ctx["phone"] or "YOUR PHONE"), email=esc(ctx["from_email"] or "YOUR EMAIL"), postal_address=esc(ctx["postal_address"]),
                        accent=pal["accent"], accent_ink=pal["accent_ink"], warn=warn)


def kit(lead: dict, cfg: dict, demo_url: str, palette=None) -> dict:
    """Everything for one lead, as text (used by the files below and by the Agency page's data)."""
    ctx = context(lead, cfg, demo_url)
    ready = CFG.sender_ready(cfg)
    op = opener(ctx)
    return {"ready": ready, "subject": subject(ctx), "email": email_text(ctx, ready), "opener": op, "opener_words": words(op), "voicemail": voicemail(ctx),
            "phone_script": phone_text(ctx), "html": pitch_html(lead, ctx, cfg, ready, palette), "package": ctx["package_id"],
            "setup": float(CFG.package(cfg, ctx["package_id"]).get("setup", 0)), "monthly": float(CFG.package(cfg, ctx["package_id"]).get("monthly", 0)),
            "problem": ctx["problem_code"], "problem_short": ctx["problem_short"]}


def write_kit(lead: dict, cfg: dict, demo_url: str, out_dir: str, palette=None) -> dict:
    k = kit(lead, cfg, demo_url, palette)
    d = ensure_dir(os.path.join(out_dir, lead["slug"], "pitch"))
    for name, key in (("pitch.html", "html"), ("email.txt", "email"), ("phone.txt", "phone_script")):
        with open(os.path.join(d, name), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(k[key])
    meta = {x: k[x] for x in ("ready", "subject", "opener", "opener_words", "voicemail", "package", "setup", "monthly", "problem", "problem_short")}
    meta.update({"lead_id": lead["id"], "name": lead["name"], "demo_url": demo_url})
    with open(os.path.join(d, "pitch.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=1)
    return {"dir": d, **meta}


def demo_url_for(lead: dict, cfg: dict) -> str:
    pattern = (cfg.get("demo_sites") or {}).get("url_pattern") or "https://{slug}-demo.netlify.app"
    return pattern.replace("{slug}", lead.get("slug") or "business")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m agency.pitch", description="Write the pitch kit (one-pager, email, phone opener) for leads.")
    ap.add_argument("--leads", required=True)
    ap.add_argument("--id", action="append", help="lead id; repeat for more; default the first 3")
    ap.add_argument("--demo-url", default="", help="the demo's real address after you dropped it on Netlify (default: config url_pattern)")
    ap.add_argument("--out", default=os.path.join(OUT_DIR, "sites"))
    args = ap.parse_args(argv)
    cfg = CFG.load()
    with open(args.leads, encoding="utf-8") as fh:
        leads = json.load(fh)["leads"]
    chosen = [l for l in leads if l["id"] in args.id] if args.id else leads[:3]
    for l in chosen:
        r = write_kit(l, cfg, args.demo_url or demo_url_for(l, cfg), args.out)
        print(f"{l['name'][:36]:36} {r['package']:8} ${r['setup']:,.0f} + ${r['monthly']:,.0f}/mo  opener {r['opener_words']} words  "
              f"{'ready' if r['ready'] else 'NOT READY (placeholders in agency/config.json)'}\n   {r['dir']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
