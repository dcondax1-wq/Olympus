"""Shared parts of the digital products (team D2, 2026-11-14): platform fees, listing copy, the upload zip, the honesty word lists,
Chromium renders for covers and PDFs.

Products that use it (each has its own build script, `python -m money_machines.products.build_<name> --zip`):
    site_templates   5 one-page website templates for local businesses + an offline no-code editor + a publish guide
    social_kit       30-day social media kit: an offline post maker (30 editable designs, 3 sizes), 150 captions, the 30-day plan
    agency_kit       "first clients" agency starter kit: scripts, proposal, service agreement, onboarding, invoice and tracker
    trader_planner   trader's daily routine planner (printable PDF, Letter + A4) + a spreadsheet journal; process only, no signals

Every product folder holds `buyer/` (exactly what goes into the zip, under one top folder) and `shop/` (listing.md, listing.json and
the 6 cover pictures: cover_1..3.jpg 1280 x 720 for Gumroad / Payhip, cover_1..3_square.jpg 2000 x 2000 for Etsy).
Importing this module needs the standard library only, so `--zip` works with plain Python on Windows. Rebuilding files needs
openpyxl / python-docx / Chromium (playwright) / pypdf / Pillow, imported only where used.
"""
from __future__ import annotations

import base64
import glob
import json
import os
import re
import struct
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(os.environ.get("MONEY_MACHINES_OUT") or os.path.join(ROOT, "money_machines", "out"), "products")
ZIP_DATE = (2026, 11, 14, 0, 0, 0)          # fixed time stamps: the same files always make the same zip
LOCK = "/tmp/olympus_browser.lock"           # renders run as: flock -w 2400 /tmp/olympus_browser.lock python -m ...

# The shop's own web address(es), once the owner has a store (for example "yourname.payhip.com"). The ONLY outside link a buyer file
# may carry. Empty: no shop yet, so the files say "message me through the shop where you bought this".
SHOP_HOSTS: tuple = ()

# Third-party brand names and trademarks: never in a buyer file or the listing copy (tests.test_digital_products checks every file and
# field, whole words, case-sensitive). Seller-only notes (the fee table in listing.md) may name the platforms they are about.
TRADEMARKS = (
    "Canva", "Instagram", "Facebook", "Meta", "TikTok", "Pinterest", "YouTube", "LinkedIn", "Twitter", "Snapchat", "WhatsApp",
    "Nextdoor", "Yelp", "Google", "Gmail", "Android", "Apple", "iPhone", "iPad", "macOS", "iOS", "Windows", "Microsoft", "Excel",
    "PowerPoint", "Outlook", "Keynote", "Chrome", "Safari", "Firefox", "Etsy", "Gumroad", "Payhip", "Shopify", "Wix",
    "Squarespace", "WordPress", "Webflow", "GoDaddy", "Netlify", "Vercel", "GitHub", "Cloudflare", "Stripe", "PayPal", "Venmo", "Zelle",
    "Square", "QuickBooks", "Xero", "Fiverr", "Upwork", "Calendly", "Zoom", "Notion", "Mailchimp", "Dropbox", "Adobe", "Photoshop", "Figma",
    "TradingView", "NinjaTrader", "Tradovate", "Rithmic", "MetaTrader", "Topstep", "Apex", "MyFundedFutures", "FTMO", "Nasdaq", "CME",
    "Dow Jones", "S&P", "Robinhood", "Coinbase", "Binance", "Bitcoin", "ChatGPT", "OpenAI", "Claude", "Anthropic",
)

# Promise words: a product may never promise income, results, rankings or a pass. A match is allowed only right after a negation
# ("no guarantee", "does not promise"), which is how the honest disclaimers read.
PROMISES = (
    r"guarantee[sd]?", r"promise[sd]?", r"passive income", r"get rich", r"make money", r"earn (?:up to )?\$", r"make (?:up to )?\$\d",
    r"(?:income|profit|profits) of \$", r"\$\d[\d,]*\+? (?:a|per) (?:month|week|day) (?:income|profit|in profit|passive)",
    r"6[- ]figure", r"six[- ]figure", r"double your", r"triple your", r"skyrocket", r"explode your", r"go viral", r"rank #?1", r"first page of",
    r"top of (?:search|the map)", r"pass your (?:eval|evaluation|challenge)", r"funded in", r"winning (?:trades|strategy|system)", r"profitable (?:strategy|system|trader)",
    r"risk[- ]free", r"proven to", r"100% (?:win|success|results)", r"more (?:clients|customers|sales|followers) (?:fast|guaranteed)", r"instant results",
)
NEGATIONS = ("no ", "not ", "never ", "n't ", "without ", "nor ", "nothing ", "none ", "no-", "nobody ", "cannot ")
NEGATED_AFTER = (" nothing", " no ", " none", " not ")

# Things that look like links but are vocabulary names, never fetched: XML namespaces and the structured-data vocabulary.
NOT_LINKS = ("http://www.w3.org/", "https://www.w3.org/", "http://schema.org", "https://schema.org", "http://schemas.openxmlformats.org/",
             "http://schemas.microsoft.com/", "http://purl.org/", "http://ns.adobe.com/", "http://www.inkscape.org/")

CARD = (0.029, 0.30)                          # card processing assumed for Payhip and Gumroad: 2.9% + $0.30
PLATFORMS = {
    "Payhip (free plan)": "5% + card fees (Stripe/PayPal, about 2.9% + $0.30)",
    "Gumroad": "10% + $0.50 per sale + card fees (30% on sales its Discover page brings)",
    "Etsy": "$0.20 listing + 6.5% transaction + 3% + $0.25 processing (US); Offsite Ads 12-15% only on sales they bring",
}
COVERS = [("cover_%d.jpg" % i, 1280, 720) for i in (1, 2, 3)] + [("cover_%d_square.jpg" % i, 2000, 2000) for i in (1, 2, 3)]


def fees(price: float) -> dict:
    """What you keep from one sale on each platform's basic plan (the same estimate as the eval tracker, docs/MONEY_MACHINES.md section 3)."""
    card = price * CARD[0] + CARD[1]
    return {"Payhip (free plan)": round(price - price * 0.05 - card, 2),
            "Gumroad": round(price - price * 0.10 - 0.50 - card, 2),
            "Etsy": round(price - 0.20 - price * 0.065 - (price * 0.03 + 0.25), 2)}


def fee_table(price: float) -> list:
    net = fees(price)
    return [{"platform": k, "fees": v, "fee_usd": round(price - net[k], 2), "net_usd": net[k], "fee_pct": round(100 * (price - net[k]) / price, 1)}
            for k, v in PLATFORMS.items()]


# ------------------------------------------------------------------------------------------------ listing copy
def listing_md(L: dict) -> str:
    p = L["price_usd"]
    out = [f"# Listing: {L['title']}", "", f"**Price:** ${p} (one-time, instant download). **Version:** {L['version']}.", "",
           f"**Short line:** {L['short']}", "", "## Description (paste as is)", "", "```"] + L["description"] + ["```", "",
           f"## Etsy tags ({len(L['tags_etsy'])}, each <= 20 characters)", "", ", ".join(L["tags_etsy"]), "", "## FAQ", ""]
    out += [f"- **{q}** {a}" for q, a in L["faq"]]
    out += ["", "## Refund line", "", L["refund"], "", "## Files in the zip", "", f"`{L['zip']}` unpacks to one folder `{L['top']}/`:", ""]
    out += [f"- {f}" for f in L["files"]]
    out += ["", "## Pictures (shop/)", ""] + [f"- {n} ({w} x {h}){': ' + L['image_notes'][i] if L.get('image_notes') else ''}"
                                             for i, (n, w, h) in enumerate(COVERS)]
    out += ["", "## Price and why", "", L["price_reasoning"], "", "Comparable listings (search-engine reading of each page on the date shown; "
            "the pages themselves could not be opened from the build machine, so re-check before relying on a number):", ""]
    out += [f"- {c['what']}: {c['price']} on {c['where']} ({c['seen']}): {c['url']}" for c in L["comparables"]]
    out += ["", f"## What you keep from one ${p} sale (estimates; card fees assumed 2.9% + $0.30)", "", "| Platform | Fees | Fee $ | You keep |", "|---|---|---|---|"]
    out += [f"| {r['platform']} | {r['fees']} | ${r['fee_usd']:.2f} ({r['fee_pct']}%) | **${r['net_usd']:.2f}** |" for r in fee_table(p)]
    out += ["", "## Rules for this listing", ""] + [f"- {r}" for r in L["rules"]] + [""]
    return "\n".join(out)


def write_listing(shop_dir: str, L: dict) -> list:
    os.makedirs(shop_dir, exist_ok=True)
    md, js = os.path.join(shop_dir, "listing.md"), os.path.join(shop_dir, "listing.json")
    with open(md, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(listing_md(L))
    with open(js, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(dict(L, net_per_sale_usd=fees(L["price_usd"]), fee_table=fee_table(L["price_usd"]),
                                 covers=[{"file": n, "width": w, "height": h} for n, w, h in COVERS]), indent=1, ensure_ascii=False) + "\n")
    return [md, js]


# ------------------------------------------------------------------------------------------------ files and the zip
def buyer_files(buyer_dir: str) -> list:
    """Every file under buyer/ as a posix path, sorted (this list IS the zip's content)."""
    out = []
    for base, dirs, files in os.walk(buyer_dir):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for f in files:
            if f.startswith(".") or f.endswith((".pyc", ".tmp")):
                continue
            out.append(os.path.relpath(os.path.join(base, f), buyer_dir).replace(os.sep, "/"))
    return sorted(out)


def make_zip(buyer_dir: str, top: str, zip_name: str, out: str | None = None) -> str:
    """Pack buyer/ into OUT/<zip_name> under one top folder. Plain Python (zipfile); the same files always give the same bytes."""
    out = out or OUT
    os.makedirs(out, exist_ok=True)
    z = os.path.join(out, zip_name)
    files = buyer_files(buyer_dir)
    if not files:
        raise SystemExit(f"nothing to pack: {buyer_dir} is empty (run the build without --zip first)")
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in files:
            zi = zipfile.ZipInfo(f"{top}/{rel}", date_time=ZIP_DATE)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            with open(os.path.join(buyer_dir, rel), "rb") as fh:
                zf.writestr(zi, fh.read(), compresslevel=9)
    return z


def write_text(path: str, text: str) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\r\n" if path.lower().endswith(".txt") else "\n") as fh:
        fh.write(text)
    return path


def jpeg_size(path: str) -> tuple:
    """(width, height) of a JPEG from its SOF marker (no Pillow needed)."""
    with open(path, "rb") as fh:
        data = fh.read()
    if data[:2] != b"\xff\xd8":
        raise ValueError(f"{path} is not a JPEG")
    i = 2
    while i < len(data) - 9:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        seg = struct.unpack(">H", data[i + 2:i + 4])[0]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return w, h
        i += 2 + seg
    raise ValueError(f"{path}: no size marker")


# ------------------------------------------------------------------------------------------------ honesty scans (used by the tests and the builds)
URL_RE = re.compile(r"\b(?:https?|ftp)://[^\s\"'<>)\]}]+", re.I)


def outside_links(text: str) -> list:
    """http(s) addresses in text that are neither a vocabulary name (NOT_LINKS) nor on the shop's own host."""
    bad = []
    for m in URL_RE.finditer(text):
        u = m.group(0)
        if u.startswith(NOT_LINKS):
            continue
        host = re.sub(r"^[a-z]+://", "", u, flags=re.I).split("/")[0].lower()
        if SHOP_HOSTS and any(host == h or host.endswith("." + h) for h in SHOP_HOSTS):
            continue
        bad.append(u)
    return bad


def trademark_hits(text: str) -> list:
    hits = []
    for w in TRADEMARKS:
        if re.search(r"(?<![A-Za-z0-9])" + re.escape(w) + r"(?![A-Za-z0-9])", text):
            hits.append(w)
    return hits


def promise_hits(text: str) -> list:
    hits = []
    low = text.lower()
    for pat in PROMISES:
        for m in re.finditer(r"(?<![a-z])" + pat, low):
            before = re.split(r"[.!?;:\n]", low[max(0, m.start() - 40):m.start()])[-1]      # the same sentence only
            if any(n in " " + before for n in NEGATIONS) or low[m.end():m.end() + 9].startswith(NEGATED_AFTER):
                continue
            hits.append(low[max(0, m.start() - 30):m.end() + 20].replace("\n", " "))
    return hits


def ooxml_text(path: str) -> tuple:
    """(visible text, outside hyperlink targets) of a .docx / .xlsx / .pptx: w:t, a:t, shared strings and inline strings; the
    relationship parts' External targets."""
    texts, links = [], []
    with zipfile.ZipFile(path) as z:
        for n in z.namelist():
            if not n.endswith(".xml") and not n.endswith(".rels"):
                continue
            raw = z.read(n).decode("utf-8", "replace")
            if n.endswith(".rels"):
                for m in re.finditer(r'<Relationship\b[^>]*>', raw):
                    tag = m.group(0)
                    if 'TargetMode="External"' in tag:
                        t = re.search(r'Target="([^"]+)"', tag)
                        links.append(t.group(1) if t else tag)
                continue
            for m in re.finditer(r"<(?:w:t|a:t|t)(?:\s[^>]*)?>([^<]*)</(?:w:t|a:t|t)>", raw):
                texts.append(m.group(1))
            if n.startswith(("docProps/core", "docProps/app")):
                texts.append(re.sub(r"<[^>]+>", " ", raw))
    import html as _h
    return _h.unescape(" ".join(texts)), links


def pdf_text(path: str) -> tuple:
    """(text, link targets) of a PDF: pypdf when installed (the build machine), else ('', raw /URI targets)."""
    raw = open(path, "rb").read()
    uris = [u.decode("latin-1") for u in re.findall(rb"/URI\s*\(([^)]*)\)", raw)]
    try:
        from pypdf import PdfReader
    except Exception:
        return "", uris
    r = PdfReader(path)
    txt = "\n".join((pg.extract_text() or "") for pg in r.pages)
    meta = r.metadata or {}
    txt += "\n" + " ".join(str(v) for v in meta.values())
    for pg in r.pages:
        for a in (pg.get("/Annots") or []):
            try:
                o = a.get_object()
                act = o.get("/A")
                if act and act.get_object().get("/URI"):
                    uris.append(str(act.get_object().get("/URI")))
            except Exception:
                pass
    return txt, sorted(set(uris))


TEXT_EXT = (".html", ".htm", ".css", ".js", ".txt", ".md", ".csv", ".json", ".svg", ".xml")


def file_text(path: str) -> tuple:
    """(text, links) for any buyer file: text files as is, office files via ooxml_text, PDFs via pdf_text, pictures: ('', [])."""
    low = path.lower()
    if low.endswith(TEXT_EXT):
        t = open(path, encoding="utf-8").read()
        return t, outside_links(t)
    if low.endswith((".docx", ".xlsx", ".pptx")):
        t, rel = ooxml_text(path)
        return t, rel + outside_links(t)
    if low.endswith(".pdf"):
        t, uris = pdf_text(path)
        return t, [u for u in uris if outside_links(u) or not u.startswith(("http", "mailto", "tel"))] + outside_links(t)
    return "", []


def listing_text(L: dict) -> str:
    """Every buyer-facing field of a listing (not the seller notes: fee table, rules, comparables)."""
    parts = [L["title"], L["short"], *L["description"], *L["tags_etsy"], L["refund"]]
    for q, a in L["faq"]:
        parts += [q, a]
    return "\n".join(parts)


# ------------------------------------------------------------------------------------------------ Chromium (build machine only)
def chromium(pw):
    exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
    return pw.chromium.launch(args=["--no-sandbox", "--disable-gpu", "--font-render-hinting=none"], **({"executable_path": exe} if exe else {}))


def b64(data: bytes, mime: str = "image/jpeg") -> str:
    return f"data:{mime};base64," + base64.b64encode(data).decode()


def save_jpeg(png_or_jpeg: bytes, path: str, quality: int = 82) -> str:
    """Re-encode a screenshot as an optimised progressive JPEG (Pillow), so the covers stay small."""
    from io import BytesIO

    from PIL import Image
    im = Image.open(BytesIO(png_or_jpeg)).convert("RGB")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.save(path, "JPEG", quality=quality, optimize=True, progressive=True, subsampling="4:2:0")
    return path


def shoot(br, html: str, w: int, h: int, path: str, quality: int = 82, scale: float = 1, wait_ms: int = 150) -> str:
    """Render an HTML string at w x h CSS pixels (x scale) and save it as a JPEG."""
    pg = br.new_page(viewport={"width": w, "height": h}, device_scale_factor=scale)
    pg.set_content(html, wait_until="load")
    pg.wait_for_timeout(wait_ms)
    qa = os.environ.get("D2_QA_LOG")
    if qa:                                    # layout check for the build machine: anything that sticks out of the picture
        out = pg.evaluate("""() => { const W = innerWidth, H = innerHeight, out = [];
          for (const el of document.querySelectorAll('body *')) { const r = el.getBoundingClientRect();
            if (!r.width || !r.height) continue;
            if (r.right > W + 4 || r.bottom > H + 4 || r.left < -4 || r.top < -4)
              out.push(el.tagName + '.' + (el.className || '') + ' [' + [r.left, r.top, r.right, r.bottom].map(Math.round).join(',') + ']'); }
          return out.slice(0, 8); }""")
        with open(qa, "a", encoding="utf-8") as fh:
            fh.write(f"{os.path.basename(path)} {w}x{h}: {'OK' if not out else 'OUTSIDE ' + '; '.join(out)}\n")
    png = pg.screenshot(type="png", full_page=False)
    pg.close()
    return save_jpeg(png, path, quality)


def html_pdf(br, html: str, path: str, size: str = "Letter", title: str = "", landscape: bool = False) -> str:
    """Print an HTML string to PDF with Chromium, then set neutral metadata (title, no tool names) with pypdf."""
    pg = br.new_page()
    pg.set_content(html, wait_until="load")
    pg.wait_for_timeout(100)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pg.pdf(path=path, format=size, print_background=True, landscape=landscape, prefer_css_page_size=True)
    pg.close()
    pdf_meta(path, title)
    return path


def pdf_meta(path: str, title: str) -> None:
    try:
        from pypdf import PdfReader, PdfWriter
    except Exception:
        return
    r = PdfReader(path)
    w = PdfWriter(clone_from=r)
    w.metadata = None
    w.add_metadata({"/Title": title, "/Author": "Independent maker", "/Creator": "Hand-built product files", "/Producer": "Hand-built product files"})
    tmp = path + ".tmp"
    with open(tmp, "wb") as fh:
        w.write(fh)
    os.replace(tmp, path)


def pdf_pages_png(pdf: str, out_dir: str, dpi: int = 60) -> list:
    """Each PDF page as a PNG (poppler's pdftoppm, build machine only) for cover thumbnails."""
    import shutil
    import subprocess
    exe = shutil.which("pdftoppm")
    if not exe:
        return []
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.join(out_dir, "p")
    subprocess.run([exe, "-r", str(dpi), "-png", pdf, base], check=True, capture_output=True)
    return sorted(glob.glob(base + "-*.png"))


# ------------------------------------------------------------------------------------------------ the shop look (covers)
SERIF = "'Iowan Old Style','Palatino Linotype',Palatino,Caladea,Georgia,serif"
SANS = "-apple-system,'Segoe UI',Inter,Roboto,'Helvetica Neue',Arial,sans-serif"


def cover_css(w: int, h: int, bg: str = "#14110e", ink: str = "#f3ece0", soft: str = "#cfc4b2", accent: str = "#c8a24a") -> str:
    """The shared cover frame: warm night or ivory background, a serif title with a gold rule, check-mark bullets, a foot line."""
    k = min(w / 1280, h / 720) if w != h else w / 1280
    return f"""*{{margin:0;padding:0;box-sizing:border-box}}html,body{{width:{w}px;height:{h}px;overflow:hidden}}
body{{background:{bg};color:{ink};font-family:{SANS};position:relative;-webkit-font-smoothing:antialiased}}
h1{{font-family:{SERIF};font-weight:700;line-height:1.02;letter-spacing:-.01em;color:{ink}}}
.rule{{width:{int(110 * k)}px;height:{max(4, int(7 * k))}px;background:{accent};border-radius:4px}}
.soft{{color:{soft}}}.acc{{color:{accent}}}
ul.checks{{list-style:none}}ul.checks li{{display:flex;gap:{int(12 * k)}px;align-items:baseline}}
ul.checks li:before{{content:"";flex:none;width:{int(14 * k)}px;height:{int(8 * k)}px;border-left:{max(2, int(3 * k))}px solid {accent};
border-bottom:{max(2, int(3 * k))}px solid {accent};transform:translateY(-{int(4 * k)}px) rotate(-45deg)}}
.chip{{display:inline-block;border:1.5px solid {accent};color:{accent};border-radius:999px;font-weight:700}}
.shadow{{box-shadow:0 {int(18 * k)}px {int(48 * k)}px rgba(0,0,0,.45)}}
.phone{{position:relative;background:#1b1916;border-radius:14%/7%;padding:3.2%;box-shadow:0 {int(22 * k)}px {int(50 * k)}px rgba(0,0,0,.38),inset 0 0 0 2px #3b3631}}
.phone img{{display:block;width:100%;border-radius:10%/5%}}
.phone:after{{content:"";position:absolute;top:.4%;left:50%;width:1.8%;aspect-ratio:1;margin-left:-.9%;background:#4a443d;border-radius:50%}}
.win{{background:#fbfaf7;border-radius:{max(8, int(14 * k))}px;overflow:hidden;box-shadow:0 {int(24 * k)}px {int(56 * k)}px rgba(0,0,0,.35);border:1px solid rgba(0,0,0,.12)}}
.win .tb{{display:flex;gap:{max(4, int(8 * k))}px;align-items:center;height:{max(18, int(34 * k))}px;padding:0 {int(14 * k)}px;background:#ece7de;border-bottom:1px solid rgba(0,0,0,.08)}}
.win .tb i{{width:{max(6, int(11 * k))}px;height:{max(6, int(11 * k))}px;border-radius:50%;background:#cfc6b6}}
.win .tb b{{flex:1;height:{max(8, int(16 * k))}px;margin-left:{int(18 * k)}px;border-radius:99px;background:#f8f5ef}}
.win img{{display:block;width:100%}}"""


def phone(src: str, width: int, extra: str = "") -> str:
    """A phone frame around a screenshot (data URI), width in px."""
    return f'<div class="phone" style="width:{width}px;{extra}"><img src="{src}" alt=""></div>'


def window(src: str, width: int, extra: str = "") -> str:
    """A plain browser-window frame (no address text) around a screenshot."""
    return f'<div class="win" style="width:{width}px;{extra}"><div class="tb"><i></i><i></i><i></i><b></b></div><img src="{src}" alt=""></div>'


# ------------------------------------------------------------------------------------------------ office files: neutral metadata
APP_XML = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/'
           'extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application></Application>'
           '<DocSecurity>0</DocSecurity></Properties>')


def core_xml(title: str) -> str:
    from xml.sax.saxutils import escape
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/'
            'metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            f'<dc:title>{escape(title)}</dc:title><dc:creator>Independent maker</dc:creator><cp:lastModifiedBy>Independent maker</cp:lastModifiedBy>'
            '<dcterms:created xsi:type="dcterms:W3CDTF">2026-11-14T00:00:00Z</dcterms:created>'
            '<dcterms:modified xsi:type="dcterms:W3CDTF">2026-11-14T00:00:00Z</dcterms:modified></cp:coreProperties>')


def clean_ooxml(path: str, title: str) -> str:
    """Rewrite a .docx/.xlsx with neutral properties (no tool or app names, fixed dates) and fixed zip time stamps."""
    with zipfile.ZipFile(path) as z:
        items = [(i, z.read(i.filename)) for i in z.infolist()]
    tmp = path + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zo:
        for info, data in items:
            if info.filename == "docProps/app.xml":
                data = APP_XML.encode()
            elif info.filename == "docProps/core.xml":
                data = core_xml(title).encode()
            zi = zipfile.ZipInfo(info.filename, date_time=ZIP_DATE)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zo.writestr(zi, data)
    os.replace(tmp, path)
    return path


def recalc_xlsx(path: str) -> str:
    """Store formula results in the file (LibreOffice through the xlsx skill's recalc.py, when present) so file previews show numbers;
    the spreadsheet apps recompute on open either way."""
    import subprocess
    import sys
    cands = [os.environ.get("XLSX_RECALC", "")] + sorted(glob.glob("/mnt/skills/public/xlsx/scripts/recalc.py")) + \
        sorted(glob.glob(os.path.expanduser("~/.claude/skills/**/xlsx/scripts/recalc.py"), recursive=True))
    script = next((c for c in cands if c and os.path.exists(c)), None)
    if not script:
        return "note: results not cached (no recalc script)"
    r = subprocess.run([sys.executable, script, path, "120"], capture_output=True, text=True, timeout=300, cwd=os.path.dirname(script))
    try:
        res = json.loads(r.stdout)
    except ValueError:
        return f"note: recalc did not run ({(r.stderr or r.stdout)[:200]})"
    if res.get("status") != "success":
        raise SystemExit(f"{path}: formula errors: {res}")
    return f"recalculated {os.path.basename(path)}: {res.get('total_formulas')} formulas, {res.get('total_errors')} errors"
