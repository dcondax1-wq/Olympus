#!/usr/bin/env python3
"""Agency storefront builder: config.json + src/ + examples/ -> dist/site/ (plain static files) + dist/storefront.zip.

The zip is what goes on Netlify Drop (app.netlify.com/drop): every page sits at its root, no build step on Netlify,
no CDN, no tracking, no secrets. Standard library only, so it runs on the PC's plain Python.

    python agency/storefront/build.py               build the site + the zip, then list what is still a placeholder
    python agency/storefront/build.py --serve       build, then preview at http://localhost:8790 (forms print to the console)
    python agency/storefront/build.py --check       exit 1 when dist/storefront.zip is not what the sources make
    python agency/storefront/build.py --preset ocean    build with another colour preset (coral | ocean | forest)
    python agency/storefront/build.py --out DIR     build the site folder into DIR only (no zip; tests and screenshots)
"""
from __future__ import annotations

import argparse
import hashlib
import html
import http.server
import json
import os
import re
import shutil
import socketserver
import sys
import urllib.parse
import zipfile
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "src"
EXAMPLES = HERE / "examples"
DIST = HERE / "dist"
ZIP_PATH = DIST / "storefront.zip"
CONFIG = HERE / "config.json"
SHARED_CONFIG = HERE.parent / "config.json"     # agency/config.json (the agency-wide file), when it exists
SHARED_KEYS = ("agency_name", "city", "phone", "email", "brand_color")
PRESETS = ("coral", "ocean", "forest")           # their colours live in src/assets/site.css only (css_presets reads them)
TRADES = ("barber", "plumber", "restaurant")
FIXED_TIME = (2026, 1, 1, 0, 0, 0)          # zip entry dates: the same bytes in, the same zip out
TEXT_EXT = {".html", ".css", ".js", ".json", ".svg", ".txt", ".xml", ""}
NAV = [("work.html", "work", "Work"), ("pricing.html", "pricing", "Pricing"), ("grader.html", "grader", "Free website check"),
       ("faq.html", "faq", "FAQ"), ("contact.html", "contact", "Contact")]
PAGES = ["index.html", "work.html", "pricing.html", "grader.html", "faq.html", "contact.html", "privacy.html", "terms.html",
         "thanks.html", "404.html"]
NO_INDEX = {"thanks.html", "404.html"}


class BuildError(Exception):
    """A problem the owner can fix in config.json (said in plain words)"""


# ------------------------------------------------------------------------------------------------ small helpers
def esc(s) -> str:
    return html.escape(str(s), quote=True)


def read_text(p: Path) -> str:
    """text with LF line endings (a Windows checkout may hand us CRLF: the zip must not change because of it)"""
    return p.read_bytes().decode("utf-8").replace("\r\n", "\n")


def money(n) -> str:
    n = float(n)
    return "$" + (f"{n:,.0f}" if n == int(n) else f"{n:,.2f}")


def digits(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def tel_of(phone: str) -> str:
    d = digits(phone)
    if len(d) == 10:
        return "+1" + d
    if len(d) == 11 and d.startswith("1"):
        return "+" + d
    return ("+" + d) if (phone or "").strip().startswith("+") else d


def initials(name: str) -> str:
    words = [w for w in re.split(r"[\s&+/-]+", name or "") if w and w[0].isalnum()]
    if not words:
        return "A"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[1][0]).upper()


def load_json(p: Path, what: str) -> dict:
    raw = read_text(p)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        line = raw.splitlines()[e.lineno - 1] if 0 < e.lineno <= len(raw.splitlines()) else ""
        raise BuildError(f"{what} has a typo on line {e.lineno} (column {e.colno}): {e.msg}.\n    {line.strip()}\n"
                         "    Check the quotes and the commas around that line.") from None


# ------------------------------------------------------------------------------------------------ colours
def hex_rgb(h: str) -> tuple:
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_hex(rgb) -> str:
    return "#%02X%02X%02X" % tuple(max(0, min(255, round(x))) for x in rgb)


def luminance(h: str) -> float:
    def ch(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = hex_rgb(h)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def mix(a: str, b: str, t: float) -> str:
    return rgb_hex(x + (y - x) * t for x, y in zip(hex_rgb(a), hex_rgb(b)))


def toward(h: str, target: str, ok, start: float = 0.0) -> str:
    """the first mix of h toward target (black or white) that passes ok()"""
    for i in range(0, 41):
        c = mix(h, target, min(1.0, start + i * 0.025))
        if ok(c):
            return c
    return target


def css_presets(css: str | None = None) -> dict:
    """{preset: {'--brand': '#C8432A', ...}} read from the stylesheet (the one place the palettes are written)"""
    css = css if css is not None else read_text(SRC / "assets" / "site.css")
    out = {}
    for m in re.finditer(r'(?:^|\n)([^{}\n]*\[data-preset="(\w+)"\][^{}\n]*)\{([^}]*)\}', css):
        out[m.group(2)] = dict(re.findall(r"(--[\w-]+)\s*:\s*(#[0-9A-Fa-f]{3,6})\b", m.group(3)))
    return out


def base_preset(hex_: str) -> str:
    """the preset whose background tints suit a custom brand colour (by hue)"""
    r, g, b = [x / 255 for x in hex_rgb(hex_)]
    mx, mn = max(r, g, b), min(r, g, b)
    if mx - mn < 0.08:
        return "coral"
    if mx == r:
        hue = (60 * ((g - b) / (mx - mn))) % 360
    elif mx == g:
        hue = 60 * ((b - r) / (mx - mn)) + 120
    else:
        hue = 60 * ((r - g) / (mx - mn)) + 240
    if hue < 50 or hue >= 300:
        return "coral"
    return "forest" if hue < 165 else "ocean"


def brand_vars(hex_: str, pal: dict) -> dict:
    """the brand variables for any colour, each pair kept readable (WCAG AA 4.5:1)"""
    ink, bg2, dark = pal["--ink"], pal["--bg-2"], pal["--dark"]
    if contrast("#FFFFFF", hex_) >= 4.5:
        brand, on = hex_, "#FFFFFF"
    elif contrast(ink, hex_) >= 4.5:
        brand, on = hex_, ink                                   # a light colour: dark text on it
    else:
        brand, on = toward(hex_, "#000000", lambda c: contrast("#FFFFFF", c) >= 4.5), "#FFFFFF"
    hover = toward(brand, "#000000", lambda c: contrast(on, c) >= 4.5, 0.12) if on == "#FFFFFF" else mix(brand, "#000000", 0.08)
    if contrast(on, hover) < 4.5:
        hover = brand
    return {"--brand": brand, "--brand-hover": hover, "--brand-ink": on,
            "--brand-text": toward(hex_, "#000000", lambda c: contrast(c, bg2) >= 4.7),
            "--brand-soft": mix(hex_, "#FFFFFF", 0.86),
            "--brand-on-dark": toward(hex_, "#FFFFFF", lambda c: contrast(c, dark) >= 5.5)}


def parse_brand(value) -> dict:
    """brand_color: a preset name, or any #RRGGBB colour (built on the nearest preset's background tints)"""
    v = str(value or "coral").strip()
    if v.lower() in PRESETS:
        pal = css_presets()[v.lower()]
        return {"preset": v.lower(), "hex": pal["--brand"], "custom": None}
    if re.fullmatch(r"#?[0-9A-Fa-f]{6}|#?[0-9A-Fa-f]{3}", v):
        hx = rgb_hex(hex_rgb(v))
        base = base_preset(hx)
        return {"preset": base, "hex": hx, "custom": brand_vars(hx, css_presets()[base])}
    raise BuildError(f"brand_color must be coral, ocean, forest or a colour like #1E6B47 (it is {v!r})")


# ------------------------------------------------------------------------------------------------ the config (+ the shared agency file)
def shared_values(path: Path = SHARED_CONFIG) -> dict:
    """agency_name / city / phone / email / brand_color from agency/config.json, when that file exists"""
    if not path.exists():
        return {}
    data = load_json(path, "agency/config.json")
    out = {}
    for k in SHARED_KEYS + ("brand_colour",):
        v = data.get(k)
        if v in (None, "") and isinstance(data.get("agency"), dict):
            v = data["agency"].get(k)
        if v not in (None, ""):
            out["brand_color" if k == "brand_colour" else k] = v
    return out


def normalize(c: dict, shared_from: str = "") -> dict:
    """the flat file the owner edits -> the shape the build uses"""
    a = {"name": c.get("agency_name", ""), "owner": c.get("owner_name", ""), "city": c.get("city", ""), "state": c.get("state", ""),
         "service_area": c.get("service_area") or c.get("city", ""), "phone": c.get("phone", ""), "texts_ok": c.get("texts_ok", True) is not False,
         "email": c.get("email", ""), "hours": c.get("hours", ""), "booking_url": (c.get("booking_url") or "").strip(),
         "site_url": (c.get("site_url") or "").strip(), "legal_name": c.get("legal_name") or c.get("agency_name", ""),
         "founded": c.get("founded") or 2026, "legal_reviewed": bool(c.get("legal_reviewed"))}
    return {"agency": a, "brand_color": c.get("brand_color", "coral"), "offer": c.get("offer") or {}, "packages": c.get("packages"),
            "addons": c.get("addons") or [], "faq": c.get("faq") or [], "testimonials": c.get("testimonials") or [], "shared_from": shared_from}


def load_config(path: Path = CONFIG, shared_path: Path | None = SHARED_CONFIG) -> dict:
    raw = load_json(path, "config.json")
    shared = shared_values(shared_path) if shared_path else {}
    raw.update(shared)
    return normalize(raw, str(shared_path) if shared else "")


# ------------------------------------------------------------------------------------------------ icons (own simple strokes)
ICONS = {
    "phone": "M6.5 3h3l1.6 4.2-2.1 1.5a11.5 11.5 0 0 0 6.3 6.3l1.5-2.1 4.2 1.6v3a2 2 0 0 1-2.1 2A17.5 17.5 0 0 1 4.5 5.1 2 2 0 0 1 6.5 3z",
    "check": "M5 12.5l4.5 4.5L19 7.5",
    "x": "M7 7l10 10M17 7L7 17",
    "arrow": "M5 12h14M13 6l6 6-6 6",
    "calendar": "M4.5 6.5A1.5 1.5 0 0 1 6 5h12a1.5 1.5 0 0 1 1.5 1.5v12A1.5 1.5 0 0 1 18 20H6a1.5 1.5 0 0 1-1.5-1.5zM4.5 10h15M8.5 3v4M15.5 3v4",
    "mail": "M3.5 6.5A1.5 1.5 0 0 1 5 5h14a1.5 1.5 0 0 1 1.5 1.5v11A1.5 1.5 0 0 1 19 19H5a1.5 1.5 0 0 1-1.5-1.5zM4 7l8 6 8-6",
    "message": "M4.5 5h15v10.5H10l-5.5 4z",
    "pin": "M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21zM12 12a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z",
    "clock": "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 7.5V12l3 2",
    "shield": "M12 3l7 3v5.5c0 4.4-3 8.1-7 9.5-4-1.4-7-5.1-7-9.5V6zM9 12l2 2 4-4",
    "bolt": "M13 3L5 13.5h6L10 21l8-10.5h-6z",
    "pencil": "M4 20h4L19 9l-4-4L4 16zM13.5 6.5l4 4",
    "search": "M10.5 18a7.5 7.5 0 1 0 0-15 7.5 7.5 0 0 0 0 15zM16 16l5 5",
    "chat": "M20 11.5c0 4.1-3.6 7.5-8 7.5-1.2 0-2.3-.2-3.3-.6L4 20l1.3-3.7C4.5 15 4 13.3 4 11.5 4 7.4 7.6 4 12 4s8 3.4 8 7.5z",
    "server": "M4.5 4.5h15v6h-15zM4.5 13.5h15v6h-15zM8 7.5h.01M8 16.5h.01",
    "star": "M12 3.6l2.5 5.2 5.7.8-4.1 4 1 5.7-5.1-2.7-5.1 2.7 1-5.7-4.1-4 5.7-.8z",
    "menu": "M4 7h16M4 12h16M4 17h16",
    "chart": "M4 19.5h16M6.5 15l4-4 3 3 5-6",
    "spark": "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z",
    "globe": "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM3 12h18M12 3c2.4 2.6 3.6 5.6 3.6 9s-1.2 6.4-3.6 9c-2.4-2.6-3.6-5.6-3.6-9S9.6 5.6 12 3z",
}


def icon(name: str, cls: str = "i") -> str:
    return (f'<svg class="{cls}" viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
            f'<path d="{ICONS[name]}"/></svg>')


# ------------------------------------------------------------------------------------------------ config: check + placeholders
def validate(cfg: dict) -> list[str]:
    """problems that stop the build, in plain words"""
    bad = []
    a = cfg.get("agency") or {}
    for k, key in (("name", "agency_name"), ("city", "city"), ("phone", "phone"), ("email", "email"), ("hours", "hours")):
        if not str(a.get(k, "")).strip():
            bad.append(f"{key} is empty")
    if len(digits(a.get("phone", ""))) < 7:
        bad.append("phone needs at least 7 digits")
    if "@" not in str(a.get("email", "")):
        bad.append("email needs an @")
    for k in ("booking_url", "site_url"):
        v = str(a.get(k, "") or "").strip()
        if v and not re.match(r"^https://[^\s\"'<>]+$", v):
            bad.append(f"{k} must start with https:// (or stay empty)")
    try:
        parse_brand(cfg.get("brand_color"))
    except BuildError as e:
        bad.append(str(e))
    o = cfg.get("offer") or {}
    if not str(o.get("headline", "")).strip():
        bad.append("offer.headline is empty")
    for k in ("demo_days", "launch_days"):
        if not isinstance(o.get(k), int) or o.get(k) < 1:
            bad.append(f"offer.{k} must be a whole number of days")
    pk = cfg.get("packages")
    if not isinstance(pk, list) or not 1 <= len(pk) <= 4:
        bad.append("packages must be a list of 1 to 4 plans")
        pk = []
    ids = set()
    for i, p in enumerate(pk, 1):
        for k in ("id", "name", "for", "pages", "edits"):
            if not str(p.get(k, "")).strip():
                bad.append(f"package {i}: {k} is empty")
        for k in ("setup_usd", "monthly_usd"):
            if not isinstance(p.get(k), (int, float)) or p.get(k) < 0:
                bad.append(f"package {i} ({p.get('name')}): {k} must be a number like 499")
        if not isinstance(p.get("features"), list) or not p.get("features"):
            bad.append(f"package {i} ({p.get('name')}): features must be a list")
        ids.add(p.get("id"))
    if sum(1 for p in pk if p.get("popular")) > 1:
        bad.append("only one package can be popular")
    for ad in cfg.get("addons") or []:
        for k in ("name", "price", "what"):
            if not str(ad.get(k, "")).strip():
                bad.append(f"add-on {ad.get('name') or '?'}: {k} is empty")
        for pid in ad.get("included_in") or []:
            if pid not in ids:
                bad.append(f"add-on {ad.get('name')}: included_in names a plan that does not exist ({pid})")
    for f in cfg.get("faq") or []:
        if not str(f.get("q", "")).strip() or not str(f.get("a", "")).strip():
            bad.append("a FAQ entry needs both q and a")
    for t in cfg.get("testimonials") or []:
        if not str(t.get("quote", "")).strip() or not str(t.get("name", "")).strip():
            bad.append("a testimonial needs quote and name (only real ones, with permission)")
    return bad


def placeholders(cfg: dict) -> list[str]:
    """what still needs the owner's real details (the site builds anyway)"""
    a = cfg["agency"]
    out = []
    for k, label in (("name", "agency_name"), ("owner", "owner_name"), ("city", "city"), ("state", "state"),
                     ("service_area", "service_area"), ("legal_name", "legal_name")):
        if "YOUR " in str(a.get(k, "")) or str(a.get(k, "")).endswith("YOUR"):   # the placeholders are in capitals: YOUR CITY
            out.append(f"{label}: still '{a.get(k)}'")
    if digits(a.get("phone", "")).startswith("555") or "555555" in digits(a.get("phone", "")):
        out.append(f"phone: still the placeholder {a.get('phone')}")
    if str(a.get("email", "")).endswith(".example"):
        out.append(f"email: still the placeholder {a.get('email')}")
    if not a.get("booking_url"):
        out.append("booking link: empty, so the Book buttons open the contact form (add a free Cal.com or Calendly link)")
    if not a.get("site_url"):
        out.append("site address: empty (add https://yourdomain.com once you have one: share previews and the sitemap use it)")
    if not a.get("legal_reviewed"):
        out.append("privacy + terms: still templates (read and edit them, then set legal_reviewed to true)")
    return out


# ------------------------------------------------------------------------------------------------ templates
TOKEN = re.compile(r"\{\{\{\s*([\w.]+)\s*\}\}\}|\{\{>\s*([\w-]+)\s*\}\}|\{\{\s*([\w.]+)\s*\}\}")
PAGE_META = re.compile(r"\A<!--page\s+(\{.*?\})\s*-->\n?", re.S)


def lookup(ctx: dict, key: str):
    cur = ctx
    for part in key.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            raise BuildError(f"template asks for '{key}', which does not exist")
    return cur


def render(tpl: str, ctx: dict, partials: dict, depth: int = 0) -> str:
    if depth > 6:
        raise BuildError("partials nest too deep")

    def sub(m):
        raw, part, plain = m.groups()
        if part:
            if part not in partials:
                raise BuildError(f"missing partial '{part}'")
            return render(partials[part], ctx, partials, depth + 1)
        if raw:
            return str(lookup(ctx, raw))
        return esc(lookup(ctx, plain))
    return TOKEN.sub(sub, tpl)


def fill(s: str, tok: dict) -> str:
    """{city}-style tokens inside config text"""
    return re.sub(r"\{(\w+)\}", lambda m: str(tok.get(m.group(1), m.group(0))), str(s))


# ------------------------------------------------------------------------------------------------ blocks (pre-rendered HTML)
def b_promises(cfg, tok) -> str:
    li = "".join(f"<li>{icon('check')}<span>{esc(fill(p, tok))}</span></li>" for p in cfg["offer"].get("promises") or [])
    return f'<ul class="promises" role="list">{li}</ul>' if li else ""


def b_plans(cfg, tok, full: bool) -> str:
    cards = []
    for p in cfg["packages"]:
        pop = bool(p.get("popular"))
        feats = p["features"] if full else p["features"][:4]
        li = "".join(f"<li>{icon('check')}<span>{esc(fill(f, tok))}</span></li>" for f in feats)
        more = "" if full or len(p["features"]) <= 4 else f'<li class="more"><a href="pricing.html#plan-{esc(p["id"])}">+ {len(p["features"]) - 4} more</a></li>'
        badge = '<p class="plan-badge">Most popular</p>' if pop else ""
        cta = f'contact.html?plan={urllib.parse.quote(p["id"])}#quote'
        cards.append(
            f'<article class="plan{" plan-pop" if pop else ""}" id="plan-{esc(p["id"])}" aria-labelledby="pl-{esc(p["id"])}">'
            f'{badge}<h3 class="plan-name" id="pl-{esc(p["id"])}">{esc(p["name"])}</h3>'
            f'<p class="plan-for">{esc(fill(p["for"], tok))}</p>'
            f'<p class="plan-price"><span class="amt">{money(p["setup_usd"])}</span><span class="per">setup</span></p>'
            f'<p class="plan-monthly">+ <strong>{money(p["monthly_usd"])}</strong> a month</p>'
            f'<p class="plan-meta">{esc(p["pages"])} · {esc(p["edits"])}</p>'
            f'<ul class="ticks" role="list">{li}{more}</ul>'
            f'<a class="btn {"btn-primary" if pop else "btn-ghost"} btn-block" href="{cta}">Start with {esc(p["name"])}</a>'
            "</article>")
    return f'<div class="plans plans-{len(cards)}">{"".join(cards)}</div>'


def b_compare(cfg) -> str:
    pk = cfg["packages"]
    head = "".join(f'<th scope="col">{esc(p["name"])}</th>' for p in pk)
    rows = [("Setup, once", [money(p["setup_usd"]) for p in pk]),
            ("Monthly", [money(p["monthly_usd"]) for p in pk]),
            ("Pages", [esc(p["pages"]) for p in pk]),
            ("Edits", [esc(p["edits"]).replace(" a month", "") for p in pk]),
            ("Hosting, padlock, backups", [icon("check", "i ok") + '<span class="sr">Included</span>'] * len(pk)),
            ("Tap-to-call, map and hours", [icon("check", "i ok") + '<span class="sr">Included</span>'] * len(pk))]
    for ad in cfg.get("addons") or []:
        if not ad.get("included_in"):
            continue
        rows.append((esc(ad["name"]), [icon("check", "i ok") + '<span class="sr">Included</span>' if p["id"] in ad["included_in"]
                                       else f'<span class="addon-cell">Add-on<br>{esc(ad["price"])}</span>' for p in pk]))
    body = "".join(f'<tr><th scope="row">{name}</th>' + "".join(f"<td>{c}</td>" for c in cells) + "</tr>" for name, cells in rows)
    return (f'<div class="table-wrap"><table class="compare"><caption class="sr">Plans side by side</caption>'
            f'<thead><tr><td></td>{head}</tr></thead><tbody>{body}</tbody></table></div>')


def b_addons(cfg) -> str:
    names = {p["id"]: p["name"] for p in cfg["packages"]}
    out = []
    for ad in cfg.get("addons") or []:
        inc = [names[i] for i in ad.get("included_in") or [] if i in names]
        note = (f'<p class="addon-inc">{icon("check")}Free with {esc(" and ".join(inc))}</p>' if inc else '<p class="addon-inc addon-any">Any plan</p>')
        out.append(f'<li class="addon"><h3>{esc(ad["name"])}</h3><p class="addon-price">{esc(ad["price"])}</p>'
                   f'<p>{esc(ad["what"])}</p>{note}</li>')
    return f'<ul class="addons" role="list">{"".join(out)}</ul>'


def b_faq(items, tok) -> str:
    out = []
    for f in items:
        out.append(f'<details class="qa"><summary><span>{esc(fill(f["q"], tok))}</span><span class="qa-sign" aria-hidden="true"></span></summary>'
                   f'<p>{esc(fill(f["a"], tok))}</p></details>')
    return f'<div class="faq">{"".join(out)}</div>'


def b_testimonials(cfg) -> str:
    t = cfg.get("testimonials") or []
    if not t:
        return ""
    cards = "".join(f'<figure class="quote"><blockquote><p>{esc(x["quote"])}</p></blockquote>'
                    f'<figcaption><strong>{esc(x["name"])}</strong>{(" · " + esc(x["business"])) if x.get("business") else ""}</figcaption></figure>'
                    for x in t)
    return ('<section class="sec" id="reviews"><div class="wrap"><header class="sec-head"><p class="eyebrow">Kind words</p>'
            f'<h2>What our clients say</h2></header><div class="quotes">{cards}</div></div></section>')


def shot(trade: str, kind: str) -> str:
    return f"img/ex/{trade}-{kind}.webp"


def b_examples(ex: dict, full: bool) -> str:
    out = []
    for c in ex["clients"]:
        t = c["trade"]
        sh = ex["show"][c["id"]]
        minus = "".join(f"<li>{icon('x')}<span>{esc(x)}</span></li>" for x in sh["before"])
        plus = "".join(f"<li>{icon('check')}<span>{esc(x)}</span></li>" for x in sh["after"])
        phones = (f'<div class="ba-phones">'
                  f'<figure class="phone phone-before"><img src="{shot(t, "before")}" width="540" height="1169" loading="lazy" decoding="async" '
                  f'alt="Before: a typical older {esc(sh["trade_label"].lower())} website on a phone, made for a desktop, with text too small to read">'
                  f'<figcaption>Before</figcaption></figure>'
                  f'<figure class="phone phone-after"><img src="{shot(t, "after")}" width="540" height="1169" loading="lazy" decoding="async" '
                  f'alt="After: the {esc(c["name"])} example website on a phone, with big buttons to call and book">'
                  f'<figcaption>After</figcaption></figure></div>')
        if not full:
            out.append(f'<article class="ba">{phones}<div class="ba-copy"><p class="tag">{esc(sh["trade_label"])}</p>'
                       f'<h3>{esc(c["name"])}</h3><ul class="ba-list ba-minus" role="list">{minus}</ul>'
                       f'<ul class="ba-list ba-plus" role="list">{plus}</ul>'
                       f'<a class="link-arrow" href="{esc(c["demo_url"])}">Open the live demo {icon("arrow")}</a></div></article>')
            continue
        changed = "".join(f"<li>{icon('spark')}<span>{esc(x)}</span></li>" for x in sh["changed"])
        out.append(
            f'<article class="case" id="{esc(t)}" aria-labelledby="case-{esc(t)}">'
            f'<header class="case-head"><p class="tag">{esc(sh["trade_label"])}</p><h2 id="case-{esc(t)}">{esc(c["name"])}</h2></header>'
            f'<div class="case-grid">{phones}'
            f'<figure class="browser"><div class="browser-bar" aria-hidden="true"><i></i><i></i><i></i><span>{esc(sh["domain"])}</span></div>'
            f'<img src="{shot(t, "desktop")}" width="960" height="600" loading="lazy" decoding="async" '
            f'alt="The {esc(c["name"])} example website on a computer screen"></figure></div>'
            f'<div class="case-notes"><div><h3>Before</h3><ul class="ba-list ba-minus" role="list">{minus}</ul></div>'
            f'<div><h3>After</h3><ul class="ba-list ba-plus" role="list">{plus}</ul></div>'
            f'<div><h3>What we built</h3><ul class="ba-list ba-spark" role="list">{changed}</ul></div></div>'
            f'<p class="case-cta"><a class="btn btn-primary" href="{esc(c["demo_url"])}">Open the live demo {icon("arrow")}</a></p></article>')
    return f'<div class="{"cases" if full else "bas"}">{"".join(out)}</div>'


def b_hero_phones(ex: dict) -> str:
    names = {c["trade"]: c["name"] for c in ex["clients"]}
    order = [("plumber", "fan-l"), ("barber", "fan-c"), ("restaurant", "fan-r")]
    figs = []
    for t, cls in order:
        load = ' fetchpriority="high"' if cls == "fan-c" else ' loading="lazy"'
        figs.append(f'<figure class="phone {cls}"><img src="{shot(t, "after")}" width="540" height="1169" decoding="async"{load} '
                    f'alt="Example website for {esc(names.get(t, t))} on a phone"></figure>')
    figs = "".join(figs)
    pins = ('<p class="pin pin-1">' + icon("phone") + 'Tap to call</p><p class="pin pin-2">' + icon("calendar") +
            'Book online</p><p class="pin pin-3">' + icon("clock") + 'Open now</p>')
    return f'<div class="fan">{figs}<div class="pins" aria-hidden="true">{pins}</div></div>'


def b_quiz(quiz: dict, tok: dict) -> str:
    out = []
    for n, q in enumerate(quiz["questions"], 1):
        qid = q["id"]
        opts = "".join(f'<label><input type="radio" name="q_{esc(qid)}" value="{v}"><span>{lab}</span></label>'
                       for v, lab in (("yes", "Yes"), ("no", "No"), ("unsure", "Not sure")))
        out.append(f'<fieldset class="q" data-q="{esc(qid)}" data-w="{int(q["w"])}" data-fix="{esc(fill(q["fix"], tok))}">'
                   f'<legend><span class="qn">{n}</span><span class="qt">{esc(fill(q["q"], tok))}</span></legend>'
                   f'<p class="how">{icon("search")}<span>{esc(fill(q["how"], tok))}</span></p>'
                   f'<div class="seg">{opts}</div></fieldset>')
    return "".join(out)


def b_nav(current: str, root: str) -> str:
    cur = ' aria-current="page"'
    return "".join(f'<a href="{root}{href}"{cur if key == current else ""}>{esc(label)}</a>' for href, key, label in NAV)


def b_jsonld(cfg, url: str) -> str:
    a = cfg["agency"]
    d = {"@context": "https://schema.org", "@type": "ProfessionalService", "name": a["name"], "telephone": tel_of(a["phone"]),
         "email": a["email"], "areaServed": a.get("service_area") or a["city"],
         "description": "Websites for local businesses: design, hosting, edits and Google profile help.",
         "address": {"@type": "PostalAddress", "addressLocality": a["city"], "addressRegion": a.get("state", "")}}
    if url:
        d["url"] = url
    if a.get("booking_url"):
        d["potentialAction"] = {"@type": "ReserveAction", "target": a["booking_url"]}
    body = json.dumps(d, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'<script type="application/ld+json">{body}</script>'


# ------------------------------------------------------------------------------------------------ the build
def minify_css(css: str) -> str:
    """comments out, whitespace squeezed; quoted strings (the data: icon) are left exactly as written"""
    out, i, n = [], 0, len(css)
    while i < n:
        ch = css[i]
        if ch in "\"'":
            j = i + 1
            while j < n and css[j] != ch:
                j += 2 if css[j] == "\\" else 1
            out.append(css[i:j + 1])
            i = j + 1
        elif css.startswith("/*", i):
            j = css.find("*/", i + 2)
            i = n if j < 0 else j + 2
        elif ch.isspace():
            while i < n and css[i].isspace():
                i += 1
            out.append(" ")
        else:
            out.append(ch)
            i += 1
    s = "".join(out)
    s = re.sub(r" ?([{};,>]) ?", r"\1", s)        # never around ':' (descendant pseudo-classes need their space)
    return s.replace(";}", "}").strip() + "\n"


def hashed(name: str, data: bytes) -> str:
    stem, ext = os.path.splitext(name)
    return f"{stem}.{hashlib.sha256(data).hexdigest()[:10]}{ext}"


def favicon(initial: str, color: str) -> str:
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="16" fill="' + color + '"/>'
            '<text x="32" y="42" text-anchor="middle" font-family="system-ui,-apple-system,Segoe UI,Arial,sans-serif" font-size="'
            + ("30" if len(initial) > 1 else "36") + '" font-weight="800" fill="#fff">' + esc(initial) + "</text></svg>\n")


def tokens(cfg: dict) -> dict:
    a, o, pk = cfg["agency"], cfg["offer"], cfg["packages"]
    return {"agency": a["name"], "city": a["city"], "state": a.get("state", ""), "phone": a["phone"], "email": a["email"],
            "service_area": a.get("service_area") or a["city"], "demo_days": o["demo_days"], "launch_days": o["launch_days"],
            "reply_time": o.get("reply_time", "within 1 business day"),
            "from_setup": money(min(p["setup_usd"] for p in pk)), "from_monthly": money(min(p["monthly_usd"] for p in pk))}


def build(out_dir: Path, preset: str | None = None, cfg: dict | None = None) -> dict:
    """write the whole site into out_dir (emptied first); returns {files, warnings, placeholders}"""
    cfg = cfg if cfg is not None else load_config()
    bad = validate(cfg)
    if bad:
        raise BuildError("config.json needs a fix:\n  - " + "\n  - ".join(bad))
    if preset and preset not in PRESETS:
        raise BuildError(f"unknown preset {preset!r}: use one of {', '.join(PRESETS)}")
    brand = parse_brand(preset or cfg["brand_color"])
    preset = brand["preset"]
    quiz = load_json(SRC / "quiz.json", "src/quiz.json")
    ex = load_json(EXAMPLES / "examples.json", "examples/examples.json")
    warnings = []
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    files: dict[str, bytes] = {}

    a = cfg["agency"]
    tok = tokens(cfg)
    site_url = (a.get("site_url") or "").rstrip("/")
    css_text = read_text(SRC / "assets" / "site.css")
    if brand["custom"]:                         # your own colour: its readable shades go on top of the nearest preset
        css_text += ("\n/* brand_color " + brand["hex"] + " (build.py) */\n.brand-custom[data-preset] { "
                     + " ".join(f"{k}: {v};" for k, v in brand["custom"].items()) + " }\n")
    css = minify_css(css_text).encode()
    js = read_text(SRC / "assets" / "site.js").encode()
    css_name = "assets/" + hashed("site.css", css)
    js_name = "assets/" + hashed("site.js", js)
    files[css_name], files[js_name] = css, js
    files["favicon.svg"] = favicon(initials(a["name"]), (brand["custom"] or {}).get("--brand", brand["hex"])).encode()

    # images: the example screenshots + the share picture for this preset
    img_dir = SRC / "img"
    for p in sorted(img_dir.rglob("*")) if img_dir.exists() else []:
        if p.is_file() and not p.name.startswith("og-"):
            files["img/" + p.relative_to(img_dir).as_posix()] = p.read_bytes()
    og = img_dir / f"og-{preset}.png"
    if og.exists():
        files["img/og.png"] = og.read_bytes()
    else:
        warnings.append(f"share picture missing (src/img/og-{preset}.png): run python agency/storefront/shots.py")
    for t in TRADES:
        for kind in ("after", "before", "desktop"):
            if "img/ex/%s-%s.webp" % (t, kind) not in files:
                warnings.append(f"example screenshot missing: img/ex/{t}-{kind}.webp (run python agency/storefront/shots.py)")

    book_href = a.get("booking_url") or "contact.html#quote"
    book_ext = bool(a.get("booking_url"))
    partials = {p.stem: read_text(p) for p in sorted((SRC / "partials").glob("*.html"))}
    headline = esc(fill(cfg["offer"]["headline"], tok))
    headline = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", headline)
    faq = cfg.get("faq") or []
    pricing_faq = [f for f in faq if re.search(r"\b(cost|fee|contract|own|pay)\b", f["q"], re.I)]
    base = {
        "a": {**{k: (v if not isinstance(v, str) else fill(v, tok)) for k, v in a.items()}, "tel": tel_of(a["phone"]),
              "sms": "sms:" + tel_of(a["phone"]), "initials": initials(a["name"])},
        "offer": {"headline_html": headline, "subline": fill(cfg["offer"].get("subline", ""), tok),
                  "guarantee": fill(cfg["offer"].get("guarantee", ""), tok), "demo_days": cfg["offer"]["demo_days"],
                  "launch_days": cfg["offer"]["launch_days"], "reply_time": tok["reply_time"]},
        "from": {"setup": tok["from_setup"], "monthly": tok["from_monthly"]},
        "preset": preset, "brand_hex": (brand["custom"] or {}).get("--brand", brand["hex"]),
        "html_class": ' class="brand-custom"' if brand["custom"] else "", "asset": {"css": css_name, "js": js_name},
        "icons": {k: icon(k) for k in ICONS},
        "book": {"href": book_href, "label": "Book a 15-minute call" if book_ext else "Ask for a call back",
                 "attrs": ' target="_blank" rel="noopener"' if book_ext else ""},
        "blocks": {"promises": b_promises(cfg, tok), "plans_short": b_plans(cfg, tok, False), "plans_full": b_plans(cfg, tok, True),
                   "compare": b_compare(cfg), "addons": b_addons(cfg), "faq_all": b_faq(faq, tok),
                   "faq_top": b_faq([f for f in faq if f.get("top")] or faq[:4], tok), "faq_pricing": b_faq(pricing_faq or faq[:4], tok),
                   "testimonials": b_testimonials(cfg), "examples_home": b_examples(ex, False), "examples_work": b_examples(ex, True),
                   "hero_phones": b_hero_phones(ex), "quiz": b_quiz(quiz, tok), "quiz_count": str(len(quiz["questions"])),
                   "sms_foot": (f'<li><a href="sms:{esc(tel_of(a["phone"]))}">{icon("message")}Send a text</a></li>' if a["texts_ok"] else ""),
                   "sms_way": (f'<a class="way" href="sms:{esc(tel_of(a["phone"]))}"><span class="way-ico">{icon("message")}</span>'
                               "<span><strong>Text</strong><span>Send a text, we reply fast</span></span></a>" if a["texts_ok"] else ""),
                   "legal_note": "" if a.get("legal_reviewed") else (
                       '<div class="template-note" role="note"><strong>Template: edit before going live.</strong> '
                       "A plain starting point, not legal advice. Read it, change what does not fit your business, then remove this note "
                       "(set legal_reviewed to true in config.json).</div>")},
    }
    sitemap = []
    for name in PAGES:
        tpl = read_text(SRC / "pages" / name)
        m = PAGE_META.match(tpl)
        if not m:
            raise BuildError(f"src/pages/{name} has no <!--page {{...}} --> header")
        meta = json.loads(m.group(1))
        tpl = tpl[m.end():]
        root = "/" if name == "404.html" else ""
        url = f"{site_url}/{'' if name == 'index.html' else name}" if site_url else ""
        og_img = (f"{site_url}/img/og.png" if site_url else f"{root}img/og.png") if "img/og.png" in files else ""
        head_extra = []
        if url and name not in NO_INDEX:
            head_extra.append(f'<link rel="canonical" href="{esc(url)}">')
            head_extra.append(f'<meta property="og:url" content="{esc(url)}">')
            sitemap.append(url)
        if og_img:
            head_extra.append(f'<meta property="og:image" content="{esc(og_img)}">')
            head_extra.append('<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">')
        if name in NO_INDEX:
            head_extra.append('<meta name="robots" content="noindex">')
        ctx = dict(base)
        ctx["root"] = root
        ctx["nav"] = b_nav(meta.get("nav", ""), root)
        ctx["page"] = {"title": fill(meta["title"], tok), "description": fill(meta["description"], tok), "file": name,
                       "head_extra": "\n".join(head_extra), "body_class": meta.get("body", ""),
                       "json_ld": b_jsonld(cfg, site_url) if name == "index.html" else ""}
        files[name] = render(tpl, ctx, partials).encode()

    # the three example demo sites (their own look; a ribbon links back here)
    files["examples/demo.js"] = read_text(EXAMPLES / "demo.js").encode()
    for t in TRADES:
        d = EXAMPLES / t
        ectx = {"agency": {"name": a["name"]}, "back": "../../index.html", "contact": "../../contact.html#quote"}
        files[f"examples/{t}/index.html"] = render(read_text(d / "index.html"), ectx, {}).encode()
        files[f"examples/{t}/style.css"] = read_text(d / "style.css").encode()

    robots = "User-agent: *\nAllow: /\nDisallow: /examples/\nDisallow: /thanks.html\n"
    if site_url:
        robots += f"Sitemap: {site_url}/sitemap.xml\n"
        files["sitemap.xml"] = ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                + "".join(f"  <url><loc>{esc(u)}</loc></url>\n" for u in sitemap) + "</urlset>\n").encode()
    files["robots.txt"] = robots.encode()
    files["_headers"] = read_text(SRC / "_headers").encode()

    for rel, data in files.items():
        p = out_dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    return {"files": sorted(files), "warnings": warnings, "placeholders": placeholders(cfg), "preset": preset,
            "brand": brand["hex"] + ("" if not brand["custom"] else f" (own colour, on the {preset} tints)"),
            "shared_from": cfg.get("shared_from", "")}


def make_zip(site: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = zip_path.with_suffix(".tmp")
    with zipfile.ZipFile(tmp, "w") as z:
        for p in sorted(site.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(site).as_posix()
            zi = zipfile.ZipInfo(rel, date_time=FIXED_TIME)
            zi.external_attr = 0o644 << 16
            stored = p.suffix.lower() in (".webp", ".png", ".jpg", ".jpeg", ".woff2")
            zi.compress_type = zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED
            z.writestr(zi, p.read_bytes(), compresslevel=None if stored else 9)
    os.replace(tmp, zip_path)


def zip_manifest(zip_path: Path) -> dict:
    with zipfile.ZipFile(zip_path) as z:
        return {i.filename: (i.CRC, i.file_size) for i in z.infolist()}


def dir_manifest(site: Path) -> dict:
    out = {}
    for p in sorted(site.rglob("*")):
        if p.is_file():
            data = p.read_bytes()
            out[p.relative_to(site).as_posix()] = (zlib.crc32(data) & 0xFFFFFFFF, len(data))
    return out


# ------------------------------------------------------------------------------------------------ preview server
class Preview(http.server.SimpleHTTPRequestHandler):
    """serves the built site; a form POST prints its fields and lands on thanks.html, like Netlify would"""

    def do_POST(self):  # noqa: N802
        n = int(self.headers.get("Content-Length") or 0)
        fields = urllib.parse.parse_qs(self.rfile.read(n).decode("utf-8", "replace"))
        name = (fields.get("form-name") or ["?"])[0]
        shown = {k: v[0][:80] for k, v in fields.items() if k not in ("form-name", "bot-field")}
        print(f"\n[form '{name}'] {json.dumps(shown, ensure_ascii=False)}\n  (on Netlify this lands in Forms; here it only prints)", flush=True)
        self.send_response(303)
        self.send_header("Location", "/thanks.html")
        self.end_headers()

    def log_message(self, fmt, *args):
        pass


def serve(site: Path, port: int) -> None:
    handler = lambda *a, **k: Preview(*a, directory=str(site), **k)  # noqa: E731
    with socketserver.ThreadingTCPServer(("127.0.0.1", port), handler) as httpd:
        print(f"Preview: http://localhost:{port}/   (Ctrl+C stops)", flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


# ------------------------------------------------------------------------------------------------ command line
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build the agency storefront (static site + Netlify Drop zip).")
    ap.add_argument("--preset", choices=sorted(PRESETS))
    ap.add_argument("--out", help="build the site folder here only (no zip)")
    ap.add_argument("--check", action="store_true", help="exit 1 when dist/storefront.zip is out of date")
    ap.add_argument("--serve", action="store_true", help="preview the site on this computer after building")
    ap.add_argument("--port", type=int, default=8790)
    args = ap.parse_args(argv)
    try:
        if args.check:
            import tempfile
            with tempfile.TemporaryDirectory() as td:
                build(Path(td) / "site", args.preset)
                fresh = dir_manifest(Path(td) / "site")
            if not ZIP_PATH.exists():
                print("NOT BUILT: dist/storefront.zip is missing. Run: python agency/storefront/build.py")
                return 1
            old = zip_manifest(ZIP_PATH)
            diff = sorted(k for k in set(old) | set(fresh) if old.get(k) != fresh.get(k))
            if diff:
                print("STALE: dist/storefront.zip differs from the sources in " + ", ".join(diff[:12]) + ("..." if len(diff) > 12 else ""))
                print("Run: python agency/storefront/build.py")
                return 1
            print(f"OK: dist/storefront.zip matches the sources ({len(fresh)} files)")
            return 0
        out = Path(args.out).resolve() if args.out else DIST / "site"
        res = build(out, args.preset)
        if not args.out:
            make_zip(out, ZIP_PATH)
        pages = [f for f in res["files"] if f.endswith(".html")]
        print(f"Built {len(res['files'])} files ({len(pages)} pages, colour {res['brand']}) in {out}")
        if res["shared_from"]:
            print(f"agency_name, city, phone, email and brand_color come from {res['shared_from']} (the shared file wins)")
        if not args.out:
            print(f"Zip for Netlify Drop: {ZIP_PATH}  ({ZIP_PATH.stat().st_size // 1024} KB)")
        for w in res["warnings"]:
            print("  ! " + w)
        if res["placeholders"]:
            print("Still placeholders (edit agency/storefront/config.json):")
            for p in res["placeholders"]:
                print("  - " + p)
        if args.serve:
            serve(out, args.port)
        return 0
    except BuildError as e:
        print("BUILD STOPPED: " + str(e))
        return 2


if __name__ == "__main__":
    sys.exit(main())
