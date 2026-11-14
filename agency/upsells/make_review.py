"""Review booster: build one client's review kit (a review page for their site, a QR code, print-ready cards, request templates).

    python agency/upsells/make_review.py data/agency/clients/joes-barbers.json            -> data/agency/upsells/joes-barbers/
    python agency/upsells/make_review.py client.json --out <folder>
    python agency/upsells/make_review.py client.json --site <site folder>                  also copy review/ into the site (as /review/)

Writes:
    review/index.html            the page the QR opens ("How was your visit?"), upload it to the client's site as /review/
    print/qr-<id>.svg            the QR code alone (vector: any size, any print shop)
    print/card-a6.html           A6 counter card (105 x 148 mm), print-ready
    print/card-business.html     business card (3.5 x 2 in), front + back
    print/cards-letter-10.html   10 business cards on US Letter (Avery 8371 / 5371 layout) for home printing
    print/requests.txt           what to say, the email and the text message (with opt-out wording)

Compliance (Google's review policy, the FTC rule on reviews): everyone can reach the Google review link, before and after rating,
whatever the stars; the private message is an extra option, never a filter. No incentives, no "5-star" wording anywhere.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from urllib.parse import quote, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from agency.upsells import common as K  # noqa: E402
from agency.upsells import qr as Q  # noqa: E402

TEMPLATES = os.path.join(HERE, "review")
GOOGLE_HOSTS = ("g.page", "search.google.com", "www.google.com", "google.com", "maps.google.com", "maps.app.goo.gl", "goo.gl")
GICON = ('<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M21.6 12.2c0-.7-.1-1.4-.2-2H12v3.8h5.4a4.6 4.6 0 0 1-2 3v2.5h3.2c1.9-1.8 3-4.4 3-7.3z"/>'
         '<path fill="currentColor" opacity=".8" d="M12 22c2.7 0 5-.9 6.6-2.5l-3.2-2.5c-.9.6-2 1-3.4 1-2.6 0-4.8-1.8-5.6-4.1H3.1v2.6A10 10 0 0 0 12 22z"/>'
         '<path fill="currentColor" opacity=".6" d="M6.4 13.9a6 6 0 0 1 0-3.8V7.5H3.1a10 10 0 0 0 0 9z"/>'
         '<path fill="currentColor" opacity=".7" d="M12 6c1.5 0 2.8.5 3.8 1.5l2.9-2.9A10 10 0 0 0 3.1 7.5l3.3 2.6C7.2 7.8 9.4 6 12 6z"/></svg>')
# words that would make a review request an incentive or a request for a good rating (checked on everything a customer sees)
INCENTIVE = re.compile(r"\b(discount|coupon|free|gift|reward|prize|raffle|drawing|percent off|% off)\b|\b(5|five)[- ]stars? (review|rating)|\bpositive review|\bgood review", re.I)


def visible_text(html: str) -> str:
    html = re.sub(r"<(script|style|noscript)\b.*?</\1>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<!--.*?-->", " ", html, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def check_wording(where: str, html: str) -> None:
    hit = INCENTIVE.search(visible_text(html))
    if hit:
        raise RuntimeError(f"{where}: wording must not offer a reward or ask for a good rating ({hit.group(0)!r})")


def google_link(rv: dict) -> str:
    url = (rv.get("google_review_url") or "").strip()
    if not url and rv.get("place_id"):
        url = "https://search.google.com/local/writereview?placeid=" + quote(str(rv["place_id"]).strip())
    if not url or url.startswith("FILL"):
        raise K.ClientError("review.google_review_url is missing: in Google Business Profile tap 'Ask for reviews' and paste the link "
                            "(it looks like https://g.page/r/.../review), or give review.place_id")
    u = urlparse(url)
    if u.scheme != "https" or u.hostname not in GOOGLE_HOSTS:
        raise K.ClientError(f"review.google_review_url {url!r} is not a Google review link (https://g.page/r/... or https://search.google.com/local/writereview?placeid=...)")
    return url


def page_url(client: dict, rv: dict) -> str:
    url = (rv.get("page_url") or "").strip() or (client.get("site_url") or "").rstrip("/") + "/review/"
    u = urlparse(url)
    if u.scheme not in ("https", "http") or not u.hostname:
        raise K.ClientError("review.page_url (or the client's site_url) must be a full https:// address: the QR code opens it")
    try:
        url.encode("ascii")
    except UnicodeEncodeError:
        raise K.ClientError("review.page_url must be plain ASCII (use the punycode form of the domain)")
    return url


def initials(name: str) -> str:
    return "".join(w[0] for w in re.sub(r"[^A-Za-z0-9 ]", "", name).split()[:2]).upper()


def render(template: str, values: dict) -> str:
    text = open(os.path.join(TEMPLATES, template), encoding="utf-8").read()
    out = re.sub(r"\{\{([a-z_]+)\}\}", lambda m: values[m.group(1)], text)
    left = re.findall(r"\{\{[a-z_]+\}\}", out)
    if left:
        raise RuntimeError(f"{template}: unfilled {left}")
    return out


def short(url: str) -> str:
    return re.sub(r"^https?://(www\.)?", "", url).rstrip("/")


def a6_page(v: dict) -> str:
    return (f'<div class="page a6"><div class="band"><div class="av">{v["initials"]}</div><div class="nm">{v["name"]}</div><div class="ct">{v["city"]}</div></div>'
            f'<div class="h">How was your visit?</div><div class="p">Scan to tell us. It takes 30 seconds, and we read every review.</div>'
            f'<div class="qr">{v["qr"]}</div><div class="scan">Open your phone camera and point it at the code</div><div class="url">{v["short"]}</div>'
            f'<div class="foot">Thank you for choosing {v["name"]}!</div></div>')


def bc_front(v: dict, page: bool = True) -> str:
    cls = "page bc" if page else "bc"
    return (f'<div class="{cls}"><div class="qr">{v["qr"]}</div><div><div class="h">How did we do?</div>'
            f'<div class="p">Scan with your phone camera to leave a quick review. We read every one.</div>'
            f'<div class="nm">{v["name"]}</div><div class="url">{v["short"]}</div></div></div>')


def bc_back(v: dict) -> str:
    site = f'<div class="ln">{v["site_short"]}</div>' if v["site_short"] else ""
    return (f'<div class="page bc back"><div class="nm">{v["name"]}</div><div class="p">Thanks for your visit!</div>'
            f'<div class="ln">{v["phone"]}</div>{site}</div>')


def requests_text(client: dict, rv: dict, purl: str, glink: str, warnings: list) -> str:
    name, owner = client["name"], rv.get("owner_name") or "the owner"
    addr = (client.get("chat") or {}).get("address") or ""
    if not addr:
        warnings.append("requests.txt: add the business's mailing address under the email (US CAN-SPAM rule for commercial email)")
    sms = f"Hi [first name], thanks for visiting {name}! How did we do? {purl} Reply STOP to opt out."
    if len(sms.replace("[first name]", "Christopher")) > 160:
        sms = f"Thanks for visiting {name}! How did we do? {purl} Reply STOP to opt out."
    return f"""REVIEW REQUESTS FOR {name.upper()}
Ask EVERY customer the same way, happy or not. Never offer anything in return for a review (no discount, gift or entry):
Google and the FTC both forbid it. The review page shows the Google link to everyone; the private message is an extra choice.

Review page (the QR code opens it): {purl}
Google review link (straight to Google): {glink}

1) IN PERSON, at checkout or when the job is done
   "Thanks for coming in! If you have 30 seconds, we'd love a review, good or bad. It helps us get better.
   The code's right here." (point at the card)

2) EMAIL, the same day or the next (one email; at most one reminder)
   Subject: How was your visit to {name}?

   Hi [first name],

   Thanks for choosing {name}! Would you take 30 seconds to tell us how it went? Good or bad, we read every review.

   Leave a review: {purl}
   Or go straight to Google: {glink}

   Thank you,
   {owner}, {name}
   {client["phone"]}{(" · " + addr) if addr else ""}

   You're getting this one-time email because you visited {name.rstrip(".")}. Don't want emails like this? Reply "unsubscribe"
   and we won't email you again.

3) TEXT MESSAGE: ONLY to customers who said yes to a text
   First ask, and note who said yes: "Can we text you a quick link to tell us how we did? It's just one text."
   Then send (one SMS, under 160 characters):

   {sms}

   Rules: one text per visit and no follow-ups; send during the day (8 am - 9 pm their time); anyone who replies STOP
   (or "stop texting me", "unsubscribe", "cancel"...) never gets another text: keep a do-not-text list.

Not legal advice. Texts: US TCPA consent + CTIA opt-out practice; email: CAN-SPAM (address + opt-out). See docs/AGENCY_UPSELLS.md.
"""


def build(client_path: str, out: str | None = None, site: str | None = None, quiet: bool = False) -> dict:
    client = K.load_client(client_path)
    rv = dict(client.get("review") or {})
    chat = client.get("chat") or {}
    warnings: list = []
    glink, purl = google_link(rv), page_url(client, rv)
    pal = K.palette(rv.get("brand_color") or chat.get("brand_color") or "#0f766e")
    form = rv.get("form_name") or "review-feedback"
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,60}", form):
        raise K.ClientError("review.form_name: letters, digits, - and _ only")
    owner = rv.get("owner_name") or "the owner"
    code = Q.make(purl, ecl="Q")
    qr_svg = code.svg(dark="#111111", title=f"QR code: review {client['name']}")
    e = K.esc
    v = {"name": e(client["name"]), "city": e(client.get("city", "")), "initials": e(initials(client["name"])), "fill": pal["fill"], "ink": pal["ink"],
         "accent": pal["accent"], "soft": pal["soft"], "google": e(glink), "google_json": json.dumps(glink), "phone": e(client["phone"]),
         "phone_json": json.dumps(client["phone"]), "tel": e(K.tel(client["phone"])), "owner": e(owner), "form": e(form), "gicon": GICON,
         # same_for_all: every rating gets the same two choices (Google or a private message) and nothing redirects by itself
         "same_json": json.dumps(bool(rv.get("same_for_all"))),
         "hint": "Then pick: a Google review or a private message." if rv.get("same_for_all") else "4 or 5 stars opens our Google review page."}
    page = render("page.html", v)
    check_wording("review page", page)
    out = out or K.default_out(client)
    K.write(os.path.join(out, "review", "index.html"), page)
    pv = dict(v, qr=qr_svg, short=e(short(purl)), site_short=e(short(client.get("site_url") or "")))
    common = {"name": v["name"], "fill": pal["fill"], "ink": pal["ink"], "accent": pal["accent"], "cut_toggle": ""}
    K.write(os.path.join(out, "print", f"qr-{client['id']}.svg"), qr_svg + "\n")
    cards = {
        "card-a6.html": dict(common, title="Review card, A6 (105 x 148 mm)", page_w="105mm", page_h="148mm",
                             help="For a counter stand or a table: print on A6 card stock at 100% (Actual size), or send this page as a PDF to a print shop.",
                             pages=a6_page(pv)),
        "card-business.html": dict(common, title="Review card, business card size (3.5 x 2 in)", page_w="3.5in", page_h="2in",
                                   help="Page 1 is the front (QR code), page 2 the back. For a print shop: save as PDF (2 pages, 3.5 x 2 in). At home use the 10-per-sheet file.",
                                   pages=bc_front(pv) + "\n" + bc_back(pv)),
        "cards-letter-10.html": dict(common, title="10 review cards on US Letter", page_w="8.5in", page_h="11in",
                                     help="Fits Avery 8371 / 5371 / 5911 business card sheets, or plain card stock (cut along the dashed lines). Print at 100% (Actual size).",
                                     cut_toggle='<label><input type="checkbox" id="cut" checked> dashed cut lines</label>',
                                     pages='<div class="page sheet">' + "".join(bc_front(pv, page=False) for _ in range(10)) + "</div>"),
    }
    for fname, values in cards.items():
        html = render("card.html", values)
        check_wording(fname, html)
        K.write(os.path.join(out, "print", fname), html)
    K.write(os.path.join(out, "print", "requests.txt"), requests_text(client, rv, purl, glink, warnings))
    if site:
        dst = os.path.join(site, "review")
        if os.path.isdir(dst):
            shutil.rmtree(dst)
        shutil.copytree(os.path.join(out, "review"), dst)
    res = {"out": out, "page_url": purl, "google": glink, "qr_version": code.version, "qr_modules": code.size, "warnings": warnings, "form": form}
    if not quiet:
        print(f"review kit for {client['name']}: QR -> {purl} (version {code.version}, level Q), Google link -> {glink}")
        print(f"  upload {os.path.join(out, 'review')} to the site as /review/ (it holds the private-message form '{form}'); print from {os.path.join(out, 'print')}")
        for w in warnings:
            print("  check:", w)
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build a client's review kit (review page, QR, cards, request templates).")
    ap.add_argument("client", help="the client file (JSON)")
    ap.add_argument("--out", help="output folder (default data/agency/upsells/<id>/)")
    ap.add_argument("--site", help="also copy review/ into this site folder")
    a = ap.parse_args(argv)
    try:
        build(a.client, a.out, a.site)
        return 0
    except K.ClientError as e:
        print("can't build the review kit:", e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
