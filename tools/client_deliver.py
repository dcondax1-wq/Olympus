"""'Yes -> live in 24 h': turn a concept site + the client's edits into a production bundle for the client's own domain.

    python tools/client_deliver.py FR-27 edits.json            -> clients/<slug>/ (outside the public site; gitignored scratch by default)
    python tools/client_deliver.py osm-n123 edits.json --out DIR

edits.json (everything optional except domain; anything left out keeps the concept site's public facts):
    {"domain": "joesdiner.com", "name": "Joe's Diner", "phone": "(301) 555-0100", "email": "hello@joesdiner.com",
     "hours": "Mo-Fr 07:00-15:00; Sa 08:00-14:00; Su off", "address": "12 Main St, Frederick MD 21701",
     "tagline": "Breakfast and lunch on Main Street since you were hungry.", "about": "...",
     "services": [["Breakfast", "Eggs, pancakes ..."], ["Lunch", "..."]],
     "logo": "path/to/logo.png", "photos": ["path/a.jpg", "path/b.jpg"]}

The bundle (static files only, free hosting):
    site/         index.html (indexable, canonical = https://<domain>/), img/, robots.txt, sitemap.xml, 404.html, CNAME (GitHub Pages),
                  _headers (Cloudflare Pages), .nojekyll
    PUBLISH.md    the DNS + publish steps for GitHub Pages or Cloudflare Pages (free), with this domain filled in
    CARE_PLAN.md  the monthly care checklist ($79/mo plan)
    bundle.json   what was built (for the agency's records; no secrets)

Refuses: no domain / a bad domain, a missing photo or logo file, an image over 2 MB, a non-image file, a fake-review word in the client's text.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import site_factory as F  # noqa: E402

OUT = os.path.join(ROOT, "scratch", "clients")
IMG_OK = (".jpg", ".jpeg", ".png", ".webp", ".avif", ".svg")
MAX_IMG = 2 * 1024 * 1024
MAX_PHOTOS = 12


class Refused(Exception):
    pass


def find_lead(key: str) -> dict:
    key = str(key).strip()
    leads = F.load_leads()
    codes = json.load(open(F.CODES)) if os.path.exists(F.CODES) else {}
    by_code = {v.upper(): k for k, v in codes.items()}
    lid = by_code.get(key.upper(), key)
    for L in leads:
        if L["id"] == lid:
            return L
    raise Refused(f"no lead with id or code {key!r}")


def check_domain(d: str) -> str:
    d = str(d or "").strip().lower()
    d = re.sub(r"^https?://", "", d).strip("/")
    if d.startswith("www."):
        d = d[4:]
    if not re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}", d) or re.search(r"github\.io|pages\.dev|\.ts\.net", d):
        raise Refused(f"domain {d!r}: give the client's own domain, like joesdiner.com")
    return d


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")[:60] or "client"


def merge(lead: dict, ed: dict) -> dict:
    L = dict(lead)
    for k in ("name", "phone", "email", "hours"):
        if ed.get(k):
            L[k] = str(ed[k]).strip()
    if ed.get("address"):
        L["address"] = str(ed["address"]).strip()
    if ed.get("town"):
        L["town"] = str(ed["town"]).strip()
    L.pop("_code", None)
    return L


def text_ok(ed: dict):
    blob = " ".join(str(ed.get(k) or "") for k in ("tagline", "about")) + " " + " ".join(" ".join(map(str, x)) for x in ed.get("services") or [])
    for w in F.BANNED:
        if re.search(r"(?<![a-z])" + re.escape(w) + r"(?![0-9])", blob, re.I):
            raise Refused(f"the client's text contains {w!r}: real reviews go on their Google profile, not in made-up site text. Reword it.")


def copy_img(src: str, dst_dir: str, name: str) -> str:
    if not os.path.isfile(src):
        raise Refused(f"image not found: {src}")
    ext = os.path.splitext(src)[1].lower()
    if ext not in IMG_OK:
        raise Refused(f"not an image we publish ({ext}): {src}")
    if os.path.getsize(src) > MAX_IMG:
        raise Refused(f"image over 2 MB (resize it first, the site must stay fast): {src}")
    with open(src, "rb") as f:
        head = f.read(16)
    sig_ok = (head.startswith(b"\xff\xd8") or head.startswith(b"\x89PNG") or head[8:12] == b"WEBP" or b"ftypavi" in head
              or ext == ".svg")
    if not sig_ok:
        raise Refused(f"file does not look like a real {ext} image: {src}")
    if ext == ".svg":
        t = open(src, encoding="utf-8", errors="replace").read()
        if re.search(r"<script|on\w+\s*=|javascript:", t, re.I):
            raise Refused(f"SVG with script in it: {src}")
    os.makedirs(dst_dir, exist_ok=True)
    out = name + ext
    shutil.copyfile(src, os.path.join(dst_dir, out))
    return "img/" + out


PUBLISH = """# Put {name} live on https://{domain}/ (free hosting)

The folder `site/` is the whole website. Pick ONE host. Both are free. Time: about 15 minutes, plus DNS (minutes to a few hours).

## A. GitHub Pages
1. In the agency's GitHub organization: **New repository** -> name `{slug}` -> Public -> Create.
2. Upload every file inside `site/` (drag them in, or push with git). Keep `CNAME` and `.nojekyll`.
3. Repository **Settings -> Pages -> Source: Deploy from a branch -> main / (root) -> Save**.
4. **Custom domain** is filled from `CNAME` (`{domain}`). Tick **Enforce HTTPS** once it is offered (can take up to an hour).
5. DNS at the client's domain registrar (the client owns the domain; ask them to add these, or log in with them):
   | Type | Name | Value |
   |---|---|---|
   | A | @ | 185.199.108.153 |
   | A | @ | 185.199.109.153 |
   | A | @ | 185.199.110.153 |
   | A | @ | 185.199.111.153 |
   | CNAME | www | <your-org>.github.io |

## B. Cloudflare Pages
1. dash.cloudflare.com -> **Workers & Pages -> Create -> Pages -> Upload assets** -> project name `{slug}` -> drag the `site/` folder -> **Deploy**.
2. Project -> **Custom domains -> Set up a custom domain** -> `{domain}`, then again for `www.{domain}`.
3. If the domain's DNS is at Cloudflare, it is added for you. If not, add at the registrar: `CNAME www -> {slug}.pages.dev`, and for the bare
   domain either move DNS to Cloudflare (free) or use the registrar's forwarding from `{domain}` to `www.{domain}`.

## Before you tell the client it is live
- [ ] Open https://{domain}/ on a phone: name, phone, hours and address right; tap-to-call dials the right number; the map opens.
- [ ] HTTPS padlock shows (no warning).
- [ ] Google Business Profile -> Edit profile -> Website = https://{domain}/
- [ ] Take down the concept page: remove its lead from the concept list or rebuild the factory (its link stops working).
- [ ] Send the client the link and the care plan (CARE_PLAN.md).
"""

CARE = """# Care plan for {name} (https://{domain}/) - $79 / month

Monthly (first week of the month, about 20 minutes):
- [ ] Open the site on a phone: it loads fast, nothing broken, HTTPS valid.
- [ ] Hours, phone and address still match the Google Business Profile (holiday hours too).
- [ ] Do the client's small edits (up to ~30 minutes: text, hours, a photo swap). Bigger changes are quoted first, in writing.
- [ ] Check the domain renewal date ({domain}); remind the client 30 days before it renews (it is in their name).
- [ ] Check the host still shows the latest deploy; keep a copy of `site/` in the agency's records.
- [ ] One line to the client: what changed this month.

Quarterly:
- [ ] Run a phone speed check (PageSpeed Insights, mobile). Fix anything under 90.
- [ ] Replace old photos if the client has new ones.
- [ ] Ask for new photos / news / seasonal hours.

Never: write reviews, add awards or claims the client cannot prove, or put the client's private data on the site.
Stop: either side, 30 days notice. On stop, hand over the `site/` folder (the client owns their words, photos, logo and domain).
"""


def deliver(key: str, edits: dict, out_root: str = OUT) -> dict:
    lead = find_lead(key)
    domain = check_domain(edits.get("domain"))
    text_ok(edits)
    L = merge(lead, edits)
    name = L["name"].strip()
    sl = slug(domain.split(".")[0] if domain else name)
    root = os.path.join(out_root, sl)
    site = os.path.join(root, "site")
    if os.path.isdir(root):
        shutil.rmtree(root)
    os.makedirs(site)
    cl = {"canonical": f"https://{domain}/", "tagline": edits.get("tagline"), "about": edits.get("about"),
          "services": [x for x in (edits.get("services") or []) if isinstance(x, (list, tuple)) and len(x) == 2]}
    if edits.get("logo"):
        cl["logo"] = copy_img(edits["logo"], os.path.join(site, "img"), "logo")
    photos = list(edits.get("photos") or [])[:MAX_PHOTOS]
    cl["photos"] = [copy_img(p, os.path.join(site, "img"), f"photo-{i + 1}") for i, p in enumerate(photos)]
    html_ = F.page(L, {}, client=cl)
    for bad in ("Concept made for", "not affiliated", 'data-agency="1"', "noindex"):
        if bad in html_:
            raise Refused(f"production page still has concept text ({bad!r}): fix site_factory.page(client=...)")
    files = {
        "index.html": html_,
        "404.html": f'<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{F.esc(name)}</title>'
                    f'<p style="font:17px system-ui;padding:40px 20px">Page not found. <a href="/">Go to {F.esc(name)}</a></p>\n',
        "robots.txt": f"User-agent: *\nAllow: /\nSitemap: https://{domain}/sitemap.xml\n",
        "sitemap.xml": f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                       f'  <url><loc>https://{domain}/</loc><lastmod>{dt.date.today().isoformat()}</lastmod></url>\n</urlset>\n',
        "CNAME": domain + "\n",
        "_headers": "/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n  Permissions-Policy: camera=(), microphone=(), geolocation=()\n",
        ".nojekyll": "",
    }
    for k, v in files.items():
        with open(os.path.join(site, k), "w", encoding="utf-8", newline="\n") as f:
            f.write(v)
    with open(os.path.join(root, "PUBLISH.md"), "w", encoding="utf-8") as f:
        f.write(PUBLISH.format(name=name, domain=domain, slug=sl))
    with open(os.path.join(root, "CARE_PLAN.md"), "w", encoding="utf-8") as f:
        f.write(CARE.format(name=name, domain=domain))
    size = sum(os.path.getsize(os.path.join(b, x)) for b, _d, fs in os.walk(site) for x in fs)
    rec = {"v": 1, "kind": "client-bundle", "lead": lead["id"], "name": name, "domain": domain, "built": dt.datetime.now().isoformat(timespec="seconds"),
           "photos": len(cl["photos"]), "logo": bool(cl.get("logo")), "bytes": size, "files": sorted(os.path.relpath(os.path.join(b, x), root).replace(os.sep, "/")
                                                                                                     for b, _d, fs in os.walk(root) for x in fs)}
    with open(os.path.join(root, "bundle.json"), "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=1)
    rec["dir"] = root
    return rec


def main(argv) -> int:
    args = [a for a in argv if not a.startswith("--")]
    out = OUT
    if "--out" in argv:
        out = argv[argv.index("--out") + 1]
        args = [a for a in args if a != out]
    if len(args) != 2:
        print(__doc__.split("\n\n")[1])
        return 2
    try:
        edits = json.load(open(args[1], encoding="utf-8"))
        r = deliver(args[0], edits, out)
    except (Refused, OSError, ValueError) as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    print(f"{r['name']}: bundle in {r['dir']} for https://{r['domain']}/ ({r['bytes'] // 1024} KB, {r['photos']} photos). Next: PUBLISH.md")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
