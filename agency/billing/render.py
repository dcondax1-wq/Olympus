"""AGENCY BILLING render (team B6, 2026-11-14): the three client documents as ONE self-contained HTML file each.

  proposal_html    one page (US Letter when printed): what they get, the price ($0 setup + monthly), the demo link, 3 steps, sign line
  agreement_html   a plain-English service agreement TEMPLATE (scope, plan, payment, cancellation, who owns the site and the domain,
                   liability limits). Marked on screen and on every printed page: template, have it reviewed, not legal advice.
  invoice_html     a numbered invoice (one page): lines, tax, total, paid, balance, and the "Pay online" box with your payment link

Offline by design: all CSS is inline, system fonts only, no script / image / font / stylesheet from the network, so a page opens the
same with no internet and prints the same on any PC or phone. The only web addresses are plain links the reader can click (the
demo site, the payment link, your website). Everything the client record holds is HTML-escaped; a link that is not http(s),
mailto or tel is shown as text, never as a link. to_pdf() prints a page to PDF with Edge or Chrome when one is installed
(headless, a throwaway profile); otherwise open the .html and choose Print > Save as PDF.
"""
from __future__ import annotations

import glob
import html
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
from urllib.parse import urlsplit

from . import core as C

DEFAULT_ACCENT = "#1f5f55"
TEMPLATE_NOTE = "Template: have it reviewed by a lawyer licensed in your state before you use it. This is not legal advice."


# ------------------------------------------------------------------------------------------------ small helpers
def esc(v) -> str:
    return html.escape(C.text(v, 2000) if not isinstance(v, str) else v, quote=True)


def safe_url(u) -> str | None:
    """the link itself when it is http(s), mailto or tel and has no spaces or quotes, else None (then it is shown as text)"""
    s = (u or "").strip() if isinstance(u, str) else ""
    if not s or any(ch in s for ch in " \t\r\n\"'<>`") or len(s) > 600:
        return None
    try:
        p = urlsplit(s)
    except ValueError:
        return None
    if p.scheme in ("http", "https") and p.netloc:
        return s
    if p.scheme in ("mailto", "tel") and len(s) > 5:
        return s
    return None


def link(u, label=None, cls="") -> str:
    href = safe_url(u)
    shown = esc(label if label is not None else (u or ""))
    klass = ' class="' + esc(cls) + '"' if cls else ""
    if not href:
        return "<span" + klass + ">" + shown + "</span>" if cls else shown
    return "<a href=\"" + esc(href) + "\"" + klass + ">" + shown + "</a>"


def tel(phone) -> str:
    digits = re.sub(r"[^\d+]", "", phone or "")
    return link("tel:" + digits, phone) if len(digits) >= 7 else esc(phone or "")


def mail(email) -> str:
    return link("mailto:" + email, email) if C.EMAIL_RE.match(email or "") else esc(email or "")


def short_url(u) -> str:
    s = (u or "").strip()
    return re.sub(r"^https?://(www\.)?", "", s).rstrip("/")


def hex_rgb(h) -> tuple[int, int, int]:
    m = re.fullmatch(r"#?([0-9a-fA-F]{6})", (h or "").strip()) if isinstance(h, str) else None
    s = m.group(1) if m else DEFAULT_ACCENT[1:]
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def mix(h, other: tuple[int, int, int], t: float) -> str:
    r, g, b = hex_rgb(h)
    return "#{:02x}{:02x}{:02x}".format(*(round(a + (o - a) * t) for a, o in zip((r, g, b), other)))


def luminance(h) -> float:
    def ch(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = hex_rgb(h)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def colours(accent) -> dict:
    a = "#{:02x}{:02x}{:02x}".format(*hex_rgb(accent))
    light = luminance(a) > 0.32                       # a pale brand colour gets dark text on its band
    return {"accent": a, "on": "#14202b" if light else "#ffffff", "soft": mix(a, (255, 255, 255), 0.9), "line": mix(a, (255, 255, 255), 0.72),
            "deep": mix(a, (0, 0, 0), 0.35) if not light else mix(a, (0, 0, 0), 0.6)}


def monogram(name) -> str:
    words = [w for w in re.findall(r"[A-Za-z0-9]+", name or "") if w.lower() not in ("the", "and", "of", "co", "llc", "inc", "sample")]
    return esc("".join(w[0] for w in words[:2]).upper() or "W")


def biz_name(biz) -> str:
    return C.text(biz.get("business_name"), 80) or "[Your business name]"


# ------------------------------------------------------------------------------------------------ the shared page
CSS = """
:root{--accent:%(accent)s;--on:%(on)s;--soft:%(soft)s;--aline:%(line)s;--deep:%(deep)s;--ink:#17212b;--muted:#5b6573;--line:#e3e6eb;--paper:#ffffff;--bg:#eef0f3}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%%;text-size-adjust:100%%}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif}
a{color:var(--deep);text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:2px;overflow-wrap:anywhere}
h1,h2,h3,.serif{font-family:Georgia,"Iowan Old Style","Palatino Linotype","Book Antiqua",Palatino,"Times New Roman",serif;font-weight:600;letter-spacing:-.01em}
.toolbar{max-width:8.5in;margin:18px auto 0;padding:0 16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap;color:var(--muted);font-size:13px}
.toolbar button{font:inherit;font-weight:600;color:var(--on);background:var(--accent);border:0;border-radius:8px;padding:9px 16px;cursor:pointer}
.sheet{max-width:8.5in;margin:14px auto 28px;background:var(--paper);border-radius:12px;box-shadow:0 1px 2px rgba(16,24,40,.06),0 10px 30px rgba(16,24,40,.08);overflow:hidden}
.band{background:var(--accent);color:var(--on);padding:26px 40px 24px}
.brand{display:flex;align-items:center;gap:12px}
.mark{width:42px;height:42px;border-radius:11px;display:grid;place-items:center;font:700 19px/1 Georgia,serif;background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.35)}
.brand b{display:block;font-size:16px;letter-spacing:.01em}
.brand small{display:block;font-size:12px;opacity:.85}
.top{display:flex;justify-content:space-between;align-items:flex-start;gap:20px}
.meta{text-align:right;font-size:12.5px;line-height:1.55;opacity:.95}
.kicker{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;padding:3px 9px;border-radius:999px;background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.35);margin-bottom:6px}
.band h1{font-size:30px;line-height:1.15;margin:20px 0 6px}
.lede{margin:0;max-width:40em;font-size:15px;opacity:.95}
.body{padding:24px 40px 26px}
.grid{display:grid;grid-template-columns:1.15fr 1fr;gap:16px}
.card{border:1px solid var(--line);border-radius:10px;padding:16px 18px;background:var(--paper)}
.card.tint{background:var(--soft);border-color:var(--aline)}
.label{font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin:0 0 6px}
h2{font-size:18px;margin:20px 0 8px}
.card h2{margin-top:0}
.price{display:flex;align-items:baseline;gap:18px;flex-wrap:wrap;margin:2px 0 6px}
.price .n{font:600 34px/1 Georgia,serif;color:var(--deep)}
.price .u{font-size:13px;color:var(--muted);display:block;margin-top:4px}
.fine{margin:8px 0 0;padding:0;list-style:none;font-size:12.5px;color:var(--muted)}
.fine li{margin:2px 0}
.checks{margin:0;padding:0;list-style:none;columns:2;column-gap:26px}
.checks li{break-inside:avoid;padding-left:22px;position:relative;margin:0 0 7px;font-size:14px}
.checks li::before{content:"";position:absolute;left:2px;top:.42em;width:9px;height:5px;border-left:2px solid var(--accent);border-bottom:2px solid var(--accent);transform:rotate(-45deg)}
.steps{margin:0;padding:0;list-style:none;display:grid;grid-template-columns:repeat(3,1fr);gap:12px;counter-reset:s}
.steps li{counter-increment:s;border-top:3px solid var(--accent);padding-top:9px;font-size:13.5px}
.steps li::before{content:counter(s);font:600 20px/1 Georgia,serif;color:var(--deep);display:block;margin-bottom:4px}
.demo a.go{display:inline-block;margin-top:6px;font-weight:700;color:var(--on);background:var(--accent);text-decoration:none;border-radius:8px;padding:8px 14px}
.demo .url{display:block;margin-top:6px;font-size:12.5px;color:var(--muted);overflow-wrap:anywhere}
.need{font-size:13.5px;color:var(--ink);margin:0}
.sign{display:grid;grid-template-columns:1.4fr 1fr 1fr;gap:18px;margin-top:22px}
.sign div{border-top:1px solid #9aa3ae;padding-top:5px;font-size:12px;color:var(--muted)}
.foot{border-top:1px solid var(--line);padding:12px 40px 16px;font-size:12px;color:var(--muted);display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap}
table.lines{width:100%%;border-collapse:collapse;margin-top:6px;font-size:14px}
table.lines th{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);text-align:left;font-weight:700;border-bottom:2px solid var(--ink);padding:8px 6px}
table.lines td{border-bottom:1px solid var(--line);padding:10px 6px;vertical-align:top}
table.lines .r{text-align:right;white-space:nowrap}
.totals{margin:12px 0 0 auto;width:min(320px,100%%);font-size:14px}
.totals div{display:flex;justify-content:space-between;padding:4px 6px}
.totals .grand{border-top:2px solid var(--ink);margin-top:4px;padding-top:8px;font-weight:700;font-size:16px}
.totals .due{background:var(--soft);border-radius:8px;padding:9px 10px;margin-top:6px;font-weight:700;color:var(--deep)}
.parties{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:8px}
.parties p{margin:0;font-size:14px;line-height:1.55}
.facts{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:0 0 18px}
.facts div{background:var(--soft);border-radius:8px;padding:8px 10px}
.facts b{display:block;font-size:14px}
.facts span{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);font-weight:700}
.pay{margin-top:18px;border:2px solid var(--accent);border-radius:12px;padding:14px 18px;display:flex;gap:18px;align-items:center;justify-content:space-between;flex-wrap:wrap}
.pay .btn{display:inline-block;font-weight:700;font-size:15px;color:var(--on);background:var(--accent);text-decoration:none;border-radius:9px;padding:11px 20px;white-space:nowrap}
.pay .url{display:block;font-size:12.5px;color:var(--muted);margin-top:3px;overflow-wrap:anywhere}
.stamp{position:absolute;right:46px;top:150px;transform:rotate(-12deg);border:3px solid currentColor;border-radius:8px;padding:4px 14px;font:700 26px/1.1 Georgia,serif;letter-spacing:.12em;opacity:.8}
.stamp.paid{color:#1d7a46}.stamp.void{color:#a12a2a}
.rel{position:relative}
.banner{background:#fff6db;border:1px solid #e8c766;color:#5b4300;border-radius:10px;padding:10px 14px;font-size:13.5px;margin:0 0 16px}
.banner b{color:#3d2d00}
.warn{background:#fdecec;border:1px solid #e9a6a6;color:#6b1a1a;border-radius:10px;padding:10px 14px;font-size:13.5px;margin:0 0 14px}
.legal h2{font-size:16px;margin:18px 0 6px}
.legal p,.legal li{font-size:14px}
.legal ul{margin:4px 0 8px;padding-left:20px}
.legal li{margin:2px 0}
.blank{display:inline-block;min-width:150px;border-bottom:1px solid #9aa3ae}
.pfoot{display:none}
@media (max-width:640px){
  .band{padding:20px 16px}.body{padding:18px 16px}.foot{padding:12px 16px}.sheet{margin:10px 0 18px;border-radius:0}
  .grid,.parties{grid-template-columns:1fr}.steps{grid-template-columns:1fr}.checks{columns:1}.facts{grid-template-columns:1fr 1fr}
  .top{flex-direction:column}.meta{text-align:left}.band h1{font-size:25px}.sign{grid-template-columns:1fr}.stamp{top:110px;right:20px;font-size:20px}
}
@page{size:Letter;margin:.45in}
@media print{
  *{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  body{background:#fff;font-size:12.5px}
  .noprint{display:none!important}
  .sheet{max-width:none;margin:0;border-radius:0;box-shadow:none;overflow:visible}
  .band{padding:18px 26px 16px;border-radius:10px}
  .band h1{font-size:25px;margin:12px 0 4px}.lede{font-size:13px}
  .body{padding:14px 4px 6px}.foot{padding:8px 4px 0}
  h2{font-size:15.5px;margin:12px 0 6px}
  .card{padding:11px 14px}.checks li{font-size:12.5px;margin-bottom:4px}.steps li{font-size:12px}
  .price .n{font-size:28px}.need{font-size:12.5px}.sign{margin-top:14px}
  .card,.pay,.steps li,.totals,.legal h2,.sign{break-inside:avoid}
  .legal h2{break-after:avoid}
  .pfoot{display:block;position:fixed;bottom:0;left:0;right:0;text-align:center;font-size:9.5px;color:#7a5a00}
  .legal{padding-bottom:14px}
}
"""

TOOLBAR = ("<div class=\"toolbar noprint\"><button type=\"button\" onclick=\"window.print()\">Print or save as PDF</button>"
           "<span>On a phone: Share, then Print, then pinch out on the preview and Share again to save the PDF.</span></div>")


def page(title: str, body: str, accent=None, extra_head: str = "") -> str:
    css = CSS % colours(accent or DEFAULT_ACCENT)
    return ("<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<meta name=\"robots\" content=\"noindex\"><title>{esc(title)}</title><style>{css}</style>{extra_head}</head>"
            f"<body>{TOOLBAR}{body}</body></html>\n")


def brand(biz) -> str:
    sub = C.text(biz.get("tagline"), 80) or "Websites for local businesses"
    return (f"<div class=\"brand\"><span class=\"mark\" aria-hidden=\"true\">{monogram(biz_name(biz))}</span>"
            f"<div><b>{esc(biz_name(biz))}</b><small>{esc(sub)}</small></div></div>")


def contact_line(biz) -> str:
    bits = [esc(biz_name(biz))]
    if biz.get("owner_name"):
        bits.append(esc(biz["owner_name"]))
    if biz.get("phone"):
        bits.append(tel(biz["phone"]))
    if biz.get("email"):
        bits.append(mail(biz["email"]))
    if biz.get("website"):
        bits.append(link(biz["website"], short_url(biz["website"])))
    return " &middot; ".join(bits)


def setup_warning(biz) -> str:
    if biz.get("configured"):
        return ""
    return ("<div class=\"warn noprint\"><b>Fill in your business details first:</b> "
            "python -m agency.billing setup --name \"Your Business\" --email you@example.com --phone \"555-0100\"</div>")


def money(v) -> str:
    d = C.dec(v)
    if d is None:
        return "-"
    return C.usd(d, whole=(d == d.to_integral_value()))


def pay_link_for(biz, package_id) -> str | None:
    links = biz.get("pay_links") if isinstance(biz.get("pay_links"), dict) else {}
    return safe_url(links.get(package_id) or links.get("default") or "")


# ------------------------------------------------------------------------------------------------ (a) the proposal
def proposal_html(client: dict, pkg: dict, biz: dict, today: str, valid_days: int = 14) -> str:
    name, trade = client["name"], C.text(client.get("trade"), 60) or "local business"
    city = C.text(client.get("city"), 60)
    setup, monthly = C.dec(pkg.get("setup_usd")) or C.ZERO, C.dec(pkg.get("monthly_usd")) or C.ZERO
    notice = int(pkg.get("notice_days") or 30)
    term = int(pkg.get("min_term_months") or 0)
    where = f"in {city}" if city else "near them"
    lede = (f"When someone {where} needs a {trade}, they search on their phone and call the first business that looks trustworthy. "
            f"This plan gives {name} a fast, clear website that turns those searches into calls.")
    demo = safe_url(client.get("demo_url"))
    if demo:
        demo_card = (f"<div class=\"card tint demo\"><p class=\"label\">Your new site</p><h2>It is already built. Have a look.</h2>"
                     f"<a class=\"go\" href=\"{esc(demo)}\">Open your demo site</a><span class=\"url\">{esc(short_url(demo))}</span></div>")
    else:
        demo_card = (f"<div class=\"card tint demo\"><p class=\"label\">Your new site</p><h2>Live in about {int(pkg.get('live_days') or 7)} days.</h2>"
                     "<p class=\"need\">We build the first version from your photos and details, you check it, and it goes live when you are happy.</p></div>")
    terms = [f"No long contract: cancel any time with {notice} days notice" if term <= 0 else f"Minimum {term} months, then cancel with {notice} days notice",
             "Hosting, security and monthly edits included", "You own your domain name and your content"]
    price = (f"<div class=\"card\"><p class=\"label\">{esc(pkg.get('name') or 'Website')} plan</p><div class=\"price\">"
             f"<div><span class=\"n\">{money(setup)}</span><span class=\"u\">setup</span></div>"
             f"<div><span class=\"n\">{money(monthly)}</span><span class=\"u\">per month</span></div></div>"
             f"<ul class=\"fine\">{''.join(f'<li>{esc(t)}</li>' for t in terms)}</ul></div>")
    pay = pay_link_for(biz, pkg.get("id"))
    step2 = f"Pay the first month ({money(monthly)}) by card or bank, online" + (", with the link we send you." if pay else ".") + " It renews monthly."
    steps = ["<b>Say yes.</b> Sign the short agreement (plain English, no fine print tricks).", f"<b>Pay online.</b> {esc(step2)}",
             f"<b>Go live.</b> Send your logo and a few photos; your site is live in about {int(pkg.get('live_days') or 7)} days."]
    inc = "".join(f"<li>{esc(x)}</li>" for x in pkg.get("includes") or C.GENERIC_INCLUDES)
    valid = C.add_days(today, valid_days)
    body = (f"<main class=\"sheet\"><header class=\"band\"><div class=\"top\">{brand(biz)}<div class=\"meta\"><span class=\"kicker\">Website proposal</span><br>"
            f"Prepared {esc(C.nice_date(today))}<br>Valid until {esc(C.nice_date(valid))}</div></div>"
            f"<h1>More calls for {esc(name)}</h1><p class=\"lede\">{esc(lede)}</p></header>"
            f"<div class=\"body\">{setup_warning(biz)}<div class=\"grid\">{demo_card}{price}</div>"
            f"<h2>What you get</h2>" + (f"<p class=\"need\" style=\"margin:-2px 0 8px\">{esc(pkg['tagline'])}</p>" if pkg.get("tagline") else "")
            + f"<ul class=\"checks\">{inc}</ul>"
            f"<h2>How it works</h2><ol class=\"steps\">{''.join(f'<li>{s}</li>' for s in steps)}</ol>"
            "<h2>What we need from you</h2><p class=\"need\">Your logo (a photo of your truck or card is fine), 5 to 10 photos of your work, "
            "the services and towns you cover, your hours, and your license number if your trade has one.</p>"
            f"<div class=\"sign\"><div>Accepted for {esc(name)} (name and signature)</div><div>Date</div><div>{esc(biz_name(biz))}</div></div>"
            f"</div><footer class=\"foot\"><span>{contact_line(biz)}</span><span>Proposal for {esc(name)}</span></footer></main>")
    return page(f"Website proposal for {name}", body, biz.get("accent"))


# ------------------------------------------------------------------------------------------------ (b) the service agreement template
def agreement_html(client: dict, pkg: dict, biz: dict, today: str) -> str:
    name = client["name"]
    trade, city = C.text(client.get("trade"), 60) or "business", C.text(client.get("city"), 60)
    b, owner = biz_name(biz), C.text(biz.get("owner_name"), 80) or "[owner name]"
    setup, monthly = C.dec(pkg.get("setup_usd")) or C.ZERO, C.dec(pkg.get("monthly_usd")) or C.ZERO
    notice, term = int(pkg.get("notice_days") or 30), int(pkg.get("min_term_months") or 0)
    late, liab = int(C.dec(biz.get("late_days")) or 10), int(C.dec(biz.get("liability_months")) or 3)
    buy = int(C.dec(biz.get("buyout_months")) or 6)
    state = C.text(biz.get("state"), 40)
    blank = "<span class=\"blank\">&nbsp;</span>"
    inc = "".join(f"<li>{esc(x)}</li>" for x in pkg.get("includes") or C.GENERIC_INCLUDES)
    term_txt = ("This agreement runs month to month." if term <= 0 else
                f"This agreement runs for a minimum of {term} months, then month to month.")
    sections = [
        ("1. Who this agreement is between",
         f"<p>{esc(b)} (\"we\", \"us\"), run by {esc(owner)}, and {esc(name)}, a {esc(trade)}" + (f" in {esc(city)}" if city else "")
         + f" (\"you\"). It starts on the date you sign it or pay the first invoice, whichever comes first: {blank}.</p>"),
        ("2. What we will do",
         f"<p>Build, host and look after your website on the <b>{esc(pkg.get('name') or 'Website')}</b> plan:</p><ul>{inc}</ul>"
         f"<ul><li>Keep the site online on a reputable host, with a security certificate (https) and regular backups.</li>"
         f"<li>Make up to {int(pkg.get('edits_per_month') or 1)} small content edit(s) a month (text, photos, hours, prices). Bigger changes, such as new pages or a redesign, are quoted first and only done if you agree.</li>"
         f"<li>Answer support requests within {int(pkg.get('support_days') or 2)} business day(s).</li>"
         f"<li>Put the first version live within about {int(pkg.get('live_days') or 7)} business days after we receive what we need from you (section 3).</li></ul>"),
        ("3. What you will do",
         "<ul><li>Send your logo, photos, services and business details, and approve the site before it goes live.</li>"
         "<li>Make sure everything you send is accurate and that you have the right to use it (photos, logos, text, reviews, licenses).</li>"
         "<li>Tell us when something changes (phone number, hours, license) so the site stays correct.</li>"
         "<li>Your business's own legal duties stay yours: licenses, the claims you make, and any privacy or terms text your customers need. We publish text you give us.</li></ul>"),
        ("4. Price and payment",
         f"<ul><li>Setup: <b>{money(setup)}</b>. Monthly plan: <b>{money(monthly)} a month</b>, paid in advance on the same day each month, starting with your first payment.</li>"
         "<li>You pay by card or bank transfer (ACH) through our payment processor. By signing you allow us to charge the payment method you save there each month until this agreement ends. You can update it at any time with the link in your receipt.</li>"
         f"<li>If a payment fails we will tell you. If it is still unpaid {late} days after the due date, we may pause the site until it is paid.</li>"
         f"<li>We will give you at least {notice} days notice by email before any price change; you may cancel before it starts.</li>"
         "<li>Prices do not include sales tax. If your state taxes this service, the tax is added to the invoice.</li></ul>"),
        ("5. Term and cancellation",
         f"<ul><li>{esc(term_txt)} Either of us can cancel with {notice} days notice in writing (email counts).</li>"
         "<li>Months already paid are not refunded, unless the law requires it.</li>"
         "<li>We may end this agreement at once if the site is used for anything illegal or abusive, or if payment stays unpaid as described in section 4.</li></ul>"),
        ("6. Who owns what",
         "<ul><li><b>Your domain name</b> (for example yourbusiness.com) is registered in your name and belongs to you. If we register or renew it for you, we do it in your name and hand over the login whenever you ask.</li>"
         "<li><b>Your content</b> (logo, photos, the text and reviews you gave us) belongs to you.</li>"
         "<li><b>The design, code and templates</b> we made are licensed to you while your plan is active. When the plan ends you keep your domain and your content, and we send you a copy of your text and images.</li>"
         f"<li><b>Buyout:</b> if you want to take the finished site files with you, you can buy them for a one-time {money(monthly * buy)} ({buy} times the monthly price). Change or delete this line before signing if you agree something else.</li>"
         "<li>Third-party parts (stock photos, fonts, plugins) stay under their own licenses.</li></ul>"),
        ("7. Hosting, uptime and backups",
         "<p>We take reasonable steps to keep the site online, secure and backed up, but no website can be online 100% of the time. Short outages, or outages caused by the host, internet providers or events outside our control, are not a breach of this agreement.</p>"),
        ("8. Limits of liability",
         "<ul><li>Neither of us is responsible to the other for lost profits, lost leads or other indirect or consequential losses.</li>"
         f"<li>Our total responsibility for any claim about the service is limited to what you paid us in the {liab} months before the claim.</li>"
         "<li>Nothing here limits responsibility that the law does not allow to be limited.</li></ul>"),
        ("9. Your customers' messages and data",
         "<p>Messages your customers send through the site's forms go to you. We do not sell them or use them for anything else, and we keep them only as long as needed to deliver them and in normal backups.</p>"),
        ("10. Changes and the rest",
         f"<ul><li>Changes to this agreement must be in writing (email is fine) and agreed by both of us.</li>"
         "<li>This is the whole agreement about the website service. If one part cannot be enforced, the rest still applies.</li>"
         f"<li>The laws of the State of {esc(state) if state else blank} apply.</li></ul>"),
    ]
    secs = "".join(f"<h2>{esc(t)}</h2>{h}" for t, h in sections)
    body = (f"<main class=\"sheet\"><header class=\"band\"><div class=\"top\">{brand(biz)}<div class=\"meta\"><span class=\"kicker\">Template</span><br>"
            f"Drafted {esc(C.nice_date(today))}</div></div><h1>Website service agreement</h1>"
            f"<p class=\"lede\">Between {esc(b)} and {esc(name)}, in plain English.</p></header>"
            f"<div class=\"body legal\">{setup_warning(biz)}<div class=\"banner\"><b>Template, not legal advice.</b> Have it reviewed by a lawyer "
            "licensed in your state before you use it. Rules on automatic renewals, cancellations and sales tax differ by state.</div>"
            f"{secs}<h2>Signatures</h2><div class=\"sign\"><div>{esc(name)}: name, title and signature</div><div>Date</div><div></div></div>"
            f"<div class=\"sign\"><div>{esc(b)}: {esc(owner)}, signature</div><div>Date</div><div></div></div>"
            f"</div><footer class=\"foot\"><span>{contact_line(biz)}</span><span>{esc(TEMPLATE_NOTE)}</span></footer>"
            f"<div class=\"pfoot\">{esc(TEMPLATE_NOTE)}</div></main>")
    return page(f"Website service agreement (template): {name}", body, biz.get("accent"))


# ------------------------------------------------------------------------------------------------ (c) the invoice
def invoice_html(inv: dict, client: dict, biz: dict) -> str:
    no, status = esc(inv.get("no") or "DRAFT"), inv.get("status") or "open"
    lines = inv.get("lines") or []
    rows = "".join(f"<tr><td>{esc(l['desc'])}</td><td class=\"r\">{C.dec(l['qty']).normalize():f}</td><td class=\"r\">{C.usd(l['unit_usd'])}</td>"
                   f"<td class=\"r\">{C.usd(l['amount_usd'])}</td></tr>" for l in lines)
    tax = C.dec(inv.get("tax_usd")) or C.ZERO
    rate = C.dec(inv.get("tax_rate_pct")) or C.ZERO
    tot = [f"<div><span>Subtotal</span><span>{C.usd(inv.get('subtotal_usd'))}</span></div>"]
    if tax > 0 or rate > 0:
        tot.append(f"<div><span>Sales tax ({rate.normalize():f}%)</span><span>{C.usd(tax)}</span></div>")
    tot.append(f"<div class=\"grand\"><span>Total</span><span>{C.usd(inv.get('total_usd'))}</span></div>")
    paid = C.dec(inv.get("paid_usd")) or C.ZERO
    if paid > 0:
        tot.append(f"<div><span>Paid{(' ' + esc(C.nice_date(inv['paid_on']))) if C.is_date(inv.get('paid_on')) else ''}</span><span>-{C.usd(paid)}</span></div>")
    bal = C.dec(inv.get("balance_usd"))
    bal = C.dec(inv.get("total_usd")) if bal is None else bal
    tot.append(f"<div class=\"due\"><span>Balance due</span><span>{C.usd(bal if status != 'void' else 0)}</span></div>")
    pay_url = safe_url(inv.get("pay_link"))
    if status == "void":
        pay = "<div class=\"pay\"><div><b>This invoice was cancelled (void).</b> Nothing is due.</div></div>"
    elif status == "paid" or (bal is not None and bal <= 0):
        pay = "<div class=\"pay\"><div><b>Paid in full. Thank you!</b><span class=\"url\">Keep this page as your receipt.</span></div></div>"
    elif inv.get("autopay"):
        pay = ("<div class=\"pay\"><div><b>Nothing to do: this is charged automatically</b>"
               f"<span class=\"url\">to the card or bank account you saved, on {esc(C.nice_date(inv.get('due') or inv.get('issued')))}.</span></div></div>")
    elif pay_url:
        pay = (f"<div class=\"pay\"><div><b>Pay online in a minute</b><span class=\"url\">{esc(C.text(biz.get('pay_note'), 160))}</span>"
               f"<span class=\"url\">{esc(pay_url)}</span></div><a class=\"btn\" href=\"{esc(pay_url)}\">Pay {C.usd(bal)} now</a></div>")
    else:
        pay = ("<div class=\"pay\"><div><b>How to pay</b><span class=\"url\">"
               f"{esc(C.text(biz.get('pay_note'), 200) or 'Reply to this email and we will send a secure payment link.')}</span></div></div>")
    stamp = "<div class=\"stamp paid\">PAID</div>" if status == "paid" else "<div class=\"stamp void\">VOID</div>" if status == "void" else ""
    bill = [f"<b>{esc(client.get('name') or inv.get('client_name') or '')}</b>"]
    for k in ("trade", "city"):
        if client.get(k):
            bill.append(esc(client[k]))
    if client.get("email"):
        bill.append(mail(client["email"]))
    if client.get("phone"):
        bill.append(tel(client["phone"]))
    frm = [f"<b>{esc(biz_name(biz))}</b>"] + [esc(biz[k]) for k in ("owner_name",) if biz.get(k)]
    frm += [esc(", ".join(x for x in (biz.get("city"), biz.get("state")) if x))] if biz.get("city") or biz.get("state") else []
    frm += [mail(biz["email"])] if biz.get("email") else []
    frm += [tel(biz["phone"])] if biz.get("phone") else []
    period = C.month_name(inv["period"]) if C.is_month(inv.get("period")) else "-"
    due = C.nice_date(inv["due"]) if C.is_date(inv.get("due")) else "On receipt"
    terms = int(C.dec(biz.get("terms_days")) or 7)
    note = (f"Payment is due within {terms} days. If it stays unpaid {int(C.dec(biz.get('late_days')) or 10)} days after the due date the site may be paused "
            "until it is paid. Thank you for your business.")
    body = (f"<main class=\"sheet rel\"><header class=\"band\"><div class=\"top\">{brand(biz)}<div class=\"meta\"><span class=\"kicker\">Invoice</span><br>"
            f"<b style=\"font-size:17px\">{no}</b></div></div></header>{stamp}"
            f"<div class=\"body\">{setup_warning(biz)}<div class=\"facts\"><div><span>Issued</span><b>{esc(C.nice_date(inv['issued'])) if C.is_date(inv.get('issued')) else '-'}</b></div>"
            f"<div><span>Due</span><b>{esc(due)}</b></div><div><span>For</span><b>{esc(period)}</b></div>"
            f"<div><span>Status</span><b>{esc({'paid': 'Paid', 'void': 'Void'}.get(status, 'Open'))}</b></div></div>"
            f"<div class=\"parties\"><div><p class=\"label\">Bill to</p><p>{'<br>'.join(bill)}</p></div><div><p class=\"label\">From</p><p>{'<br>'.join(frm)}</p></div></div>"
            f"<table class=\"lines\"><thead><tr><th>Description</th><th class=\"r\">Qty</th><th class=\"r\">Price</th><th class=\"r\">Amount</th></tr></thead>"
            f"<tbody>{rows}</tbody></table><div class=\"totals\">{''.join(tot)}</div>{pay}"
            f"<p class=\"need\" style=\"margin-top:16px;color:var(--muted);font-size:12.5px\">{esc(note)}</p></div>"
            f"<footer class=\"foot\"><span>{contact_line(biz)}</span><span>Invoice {no}</span></footer></main>")
    return page(f"Invoice {inv.get('no') or 'draft'}: {client.get('name') or ''}", body, biz.get("accent"))


# ------------------------------------------------------------------------------------------------ files and PDF
def write(path: str, doc: str) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(doc)
    os.replace(tmp, path)
    return path


def find_browser() -> str | None:
    """Edge or Chrome (Windows / macOS / Linux), else the Playwright Chromium of this repo's tests; AGENCY_BROWSER wins"""
    env = os.environ.get("AGENCY_BROWSER")
    cands = [env] if env else []
    pf = [os.environ.get(k) for k in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA") if os.environ.get(k)]
    for base in pf:
        cands += [os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe"), os.path.join(base, "Google", "Chrome", "Application", "chrome.exe")]
    cands += ["/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
    cands += [shutil.which(n) for n in ("msedge", "microsoft-edge", "google-chrome", "google-chrome-stable", "chromium", "chromium-browser")]
    for pat in ("/opt/pw-browsers/chromium-*/chrome-linux/chrome", os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux/chrome"),
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "ms-playwright", "chromium-*", "chrome-win", "chrome.exe")):
        cands += sorted(glob.glob(pat))[-1:]
    for c in cands:
        if c and os.path.isfile(c):
            return c
    return None


def to_pdf(html_path: str, pdf_path: str | None = None, browser: str | None = None, timeout: float = 90) -> tuple[str | None, str]:
    """print one page to PDF with a headless Edge / Chrome. -> (pdf path or None, what happened in plain words)"""
    exe = browser or find_browser()
    if not exe:
        return None, "No Edge or Chrome found: open the .html file and choose Print > Save as PDF."
    pdf = os.path.abspath(pdf_path or os.path.splitext(html_path)[0] + ".pdf")
    url = pathlib.Path(html_path).resolve().as_uri()
    with tempfile.TemporaryDirectory(prefix="agency-pdf-") as prof:
        cmd = [exe, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check", "--disable-extensions",
               f"--user-data-dir={prof}", "--no-pdf-header-footer", "--print-to-pdf-no-header", f"--print-to-pdf={pdf}", url]
        if os.name != "nt" and hasattr(os, "geteuid") and os.geteuid() == 0:
            cmd.insert(1, "--no-sandbox")
        try:
            subprocess.run(cmd, capture_output=True, timeout=timeout, stdin=subprocess.DEVNULL)
        except (OSError, subprocess.TimeoutExpired) as e:
            return None, f"The browser could not print it ({e.__class__.__name__}): open the .html and choose Print > Save as PDF."
    if os.path.isfile(pdf) and os.path.getsize(pdf) > 800:
        return pdf, "PDF saved"
    return None, "The browser did not write a PDF: open the .html and choose Print > Save as PDF."
