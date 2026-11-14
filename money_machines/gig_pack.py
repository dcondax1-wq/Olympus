"""GIG PACK: 8 productized freelance gigs the agency machines can deliver, ready to paste into Fiverr / Upwork / Contra.

    python -m money_machines.gig_pack --check                    # is every gig's tool installed here? (team B1-B5 modules + ours)
    python -m money_machines.gig_pack --md                       # rewrite docs/GIG_PACK.md from gig_pack.json (the copy-paste pack)
    python -m money_machines.gig_pack --validate                 # Fiverr limits: title <= 80, 5 tags <= 20 chars, description <= 1,200 ...
    python -m money_machines.gig_pack order --gig local-website --name "Rivera Plumbing" --category plumber --city "Fort Collins, CO" \
        --phone "(970) 555-0142" --email owner@example.com    # one-lead file for the agency site builder (B1), then its command
    python -m money_machines.gig_pack checklist --gig gbp-setup --business "Rivera Plumbing" --out DIR   # the GBP checklist deliverable
    python -m money_machines.gig_pack report --url https://example.com --business "Rivera Plumbing" --out DIR   # speed/SEO report

The data is gig_pack.json (titles, tags, descriptions, 3 priced packages, FAQ, requirements, the tool, the delivery checklist,
Upwork proposal templates, the daily routine). Everything here PREPARES words and files: nothing logs in to a platform, sends a
message, bids, scrapes or posts. The owner sends, accepts and delivers by hand (see "stays_human" and "never_build").
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PACK = os.path.join(HERE, "gig_pack.json")
DOC = os.path.join(ROOT, "docs", "GIG_PACK.md")
OUT = os.path.join(HERE, "out")

# Fiverr's limits as found on 2026-11-14 (help center + guides; see docs/MONEY_MACHINES.md). Checked by --validate and the test.
LIMITS = {"title": 80, "tags": 5, "tag_len": 20, "description": 1200, "faq_q": 70, "faq_a": 300, "packages": 3, "minutes_core": 60}


def load(path: str = PACK) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def gig(pack: dict, gid: str) -> dict:
    for g in pack["gigs"]:
        if g["id"] == gid:
            return g
    raise SystemExit(f"no gig {gid!r}; one of: " + ", ".join(x["id"] for x in pack["gigs"]))


# ------------------------------------------------------------------------------------------------ checks
def validate(pack: dict) -> list:
    """Problems as plain lines; [] = every gig fits the platform limits and our own rules."""
    p = []
    ids = [g["id"] for g in pack["gigs"]]
    if not 6 <= len(ids) <= 8:
        p.append(f"{len(ids)} gigs (the pack is 6-8)")
    if len(set(ids)) != len(ids):
        p.append("duplicate gig ids")
    for g in pack["gigs"]:
        i = g["id"]
        if not g["title"].startswith("I will ") or len(g["title"]) > LIMITS["title"]:
            p.append(f"{i}: title must start 'I will' and be <= {LIMITS['title']} chars ({len(g['title'])})")
        if len(g["tags"]) > LIMITS["tags"] or any(len(t) > LIMITS["tag_len"] for t in g["tags"]):
            p.append(f"{i}: at most {LIMITS['tags']} tags of <= {LIMITS['tag_len']} chars")
        if len(g["description"]) > LIMITS["description"]:
            p.append(f"{i}: description {len(g['description'])} chars > {LIMITS['description']}")
        if len(g["packages"]) != LIMITS["packages"]:
            p.append(f"{i}: needs exactly 3 packages")
        else:
            prices = [k["price"] for k in g["packages"]]
            if prices != sorted(prices) or len(set(prices)) != 3 or min(prices) < 5:
                p.append(f"{i}: package prices must rise and start at $5 or more ({prices})")
            if any(k["minutes"] > LIMITS["minutes_core"] for k in g["packages"][:2]):
                p.append(f"{i}: the two smaller packages must take under an hour")
            if any(not k.get("includes") or k["revisions"] < 1 or k["days"] < 1 for k in g["packages"]):
                p.append(f"{i}: every package needs includes, days and revisions")
        for f in g["faq"]:
            if len(f["q"]) > LIMITS["faq_q"] or len(f["a"]) > LIMITS["faq_a"]:
                p.append(f"{i}: FAQ too long: {f['q'][:40]}")
        if len(g["faq"]) < 4:
            p.append(f"{i}: at least 4 FAQ")
        if not g.get("requirements") or not g.get("delivery_checklist") or not g.get("stays_human") or not g.get("never"):
            p.append(f"{i}: requirements, delivery_checklist, stays_human and never are all needed")
        t = g.get("tool") or {}
        if not t.get("module") or not t.get("steps"):
            p.append(f"{i}: the tool needs a module and steps")
        if i not in pack["upwork"]["templates"]:
            p.append(f"{i}: no Upwork proposal template")
        text = " ".join([g["title"], g["description"]] + [f["a"] for f in g["faq"]]).lower()
        if re.search(r"\bguarantee[sd]?\b(?! a ranking)|#1 on google|first page guaranteed|100% satisf", text) and "no one can" not in text and "nobody can" not in text:
            p.append(f"{i}: promises a result")
        if "ai" not in text.split() and "ai-assisted" not in text and "image ai" not in text:
            p.append(f"{i}: says nothing about AI use")
    for k in ("stays_human", "never_build", "daily_routine", "revision_policy", "ai_line"):
        if not pack.get(k):
            p.append(f"pack: {k} missing")
    return p


def tool_status() -> list:
    """[(gig id, module, installed?)] for --check."""
    out = []
    pack = load()
    for g in pack["gigs"]:
        mod = g["tool"]["module"]
        try:
            ok = importlib.util.find_spec(mod) is not None
        except (ImportError, ValueError):
            ok = False
        out.append((g["id"], mod, ok, g["tool"]["status"]))
    return out


# ------------------------------------------------------------------------------------------------ the copy-paste pack
def render_md(pack: dict) -> str:
    L = [f"# Gig pack: 8 productized gigs (built {pack['asof']}, generated from `money_machines/gig_pack.json`)", "",
         "Copy-paste ready for Fiverr (and Upwork Project Catalog / Contra). **Prices:** " + pack["price_note"], "",
         "Regenerate after editing the JSON: `python -m money_machines.gig_pack --md`. Check the tools: `python -m money_machines.gig_pack --check`.", "",
         "| Gig | Packages ($) | Your time (min) | Start here |", "|---|---|---|---|"]
    for g in pack["gigs"]:
        L.append(f"| {g['title'][7:]} | {' / '.join(str(k['price']) for k in g['packages'])} | "
                 f"{' / '.join(str(k['minutes']) for k in g['packages'])} | {'yes' if g.get('start_here') else 'later'} |")
    L += ["", "## What stays human (always)", ""] + [f"- {x}" for x in pack["stays_human"]]
    L += ["", "## Never build or buy these (they break the platforms' rules)", ""] + [f"- {x}" for x in pack["never_build"]]
    L += ["", "## AI line (paste into every gig and proposal)", "", f"> {pack['ai_line']}", "",
          "## Revision policy (paste into every gig)", "", f"> {pack['revision_policy']}", ""]
    for n, g in enumerate(pack["gigs"], 1):
        L += [f"## {n}. {g['title']}", "", f"- **Category:** {g['category']}", f"- **Search tags (5):** {', '.join(g['tags'])}",
              f"- **Start here:** {'yes' if g.get('start_here') else 'later (Fiverr limits new sellers to a few gigs)'}", "",
              "**Description** (paste as is):", "", "```", g["description"], "```", "", "| Package | Price | Days | Revisions | Includes | Your time |",
              "|---|---|---|---|---|---|"]
        for k in g["packages"]:
            L.append(f"| {k['name']} | ${k['price']} | {k['days']} | {k['revisions']} | {'; '.join(k['includes'])} | {k['minutes']} min |")
        L += ["", "**Questions to ask the buyer (requirements):**", ""] + [f"- {r}" for r in g["requirements"]]
        L += ["", "**FAQ:**", ""] + [f"- **{f['q']}** {f['a']}" for f in g["faq"]]
        t = g["tool"]
        L += ["", f"**The tool:** {t['what']} Module `{t['module']}` ({t['status']}).", ""] + [f"    {s}" for s in t["steps"]]
        L += ["", "**Delivery checklist:**", ""] + [f"{i}. {s}" for i, s in enumerate(g["delivery_checklist"], 1)]
        L += ["", "**Stays human:** " + "; ".join(g["stays_human"]) + ".", "", "**Never:** " + "; ".join(g["never"]) + ".", ""]
    up = pack["upwork"]
    L += ["## Upwork proposal templates", "", up["rules"], ""]
    for gid, tpl in up["templates"].items():
        L += [f"### {gid}", "", "```", tpl, "```", ""]
    r = pack["daily_routine"]
    L += [f"## Daily routine (about {r['morning_min']} min in the morning + {r['evening_min']} min in the evening)", "",
          "| When | Do |", "|---|---|"] + [f"| {s['when']} | {s['do']} |" for s in r["steps"]]
    L += ["", "**Limits:**", ""] + [f"- {x}" for x in r["limits"]] + [""]
    return "\n".join(L)


# ------------------------------------------------------------------------------------------------ order -> B1 lead file
FALLBACK_CATS = {"plumber": ("Plumber", "pro"), "hvac": ("Heating and cooling", "pro"), "electrician": ("Electrician", "pro"),
                 "roofer": ("Roofer", "pro"), "painter": ("Painter", "pro"), "builder": ("Builder and carpenter", "pro"),
                 "landscaper": ("Landscaper", "fresh"), "cleaner": ("Cleaner", "fresh"), "florist": ("Florist", "fresh"),
                 "restaurant": ("Restaurant", "table"), "cafe": ("Cafe", "table"), "bakery": ("Bakery", "table"),
                 "barber": ("Barbershop", "studio"), "salon": ("Hair salon", "bloom"), "beauty": ("Beauty salon", "bloom"),
                 "auto_repair": ("Auto repair", "garage"), "dentist": ("Dentist", "clinic"), "gym": ("Gym", "pulse")}


def slugify(s: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")[:48] or "client"


def make_lead(name, category, city="", phone="", email="", website="", street="", hours="", description="", gig_id="local-website") -> dict:
    """A one-lead file in the B1 'agency-leads' v1 shape (agency/demo/*/leads.json), so agency.build_site can read it."""
    key = (category or "").strip().lower()
    label, template = FALLBACK_CATS.get(key, (key.replace("_", " ").capitalize() or "Local business", "pro"))
    try:
        from agency import categories as C          # B1's own table, when the agency kit is installed
        c = C.BY_KEY.get(C.ALIASES.get(key, key))
        if c:
            key, label, template = c.key, c.label, c.template
    except Exception:
        pass
    cty, st = (city.split(",", 1) + [""])[:2]
    digits = re.sub(r"\D", "", phone)
    e164 = ("+1" + digits[-10:]) if len(digits) >= 10 else ""
    slug = slugify(name)
    line = ", ".join(x for x in (street, cty.strip(), " ".join(x for x in (st.strip(),) if x)) if x)
    lead = {"id": slug, "osm": "", "osm_url": "", "name": name, "slug": slug, "category": key, "category_label": label, "template": template,
            "address": {"housenumber": "", "street": street, "unit": "", "city": cty.strip(), "state": st.strip(), "postcode": "",
                        "city_guess": False, "line": line, "street_line": street, "has_street": bool(street)},
            "phone": phone, "phone_e164": e164, "email": email, "website": website, "facebook": "", "instagram": "",
            "opening_hours": hours, "cuisine": "", "description": description, "tag_count": 0, "source": "order", "check_date": "",
            "score": 0, "tier": "order", "need": 0, "reach": 0, "value": 0, "site_status": "order", "issues": [], "reasons": [],
            "why": f"Paid order ({gig_id})", "hours": []}
    return {"v": 1, "kind": "agency-leads", "meta": {"source": "money_machines.gig_pack order", "gig": gig_id,
                                                     "place": {"query": city, "city": cty.strip(), "state_code": st.strip()}},
            "leads": [lead]}


# ------------------------------------------------------------------------------------------------ deliverables
PAGE_CSS = ("body{margin:0;font-family:-apple-system,'Segoe UI',system-ui,sans-serif;background:#f6f3ec;color:#1d1a16;line-height:1.5}"
            "main{max-width:860px;margin:0 auto;padding:24px 16px 64px}h1,h2{font-family:Georgia,'Palatino Linotype',serif}"
            "h2{border-bottom:2px solid #c8a24a;padding-bottom:4px;margin-top:1.6em}table{border-collapse:collapse;width:100%;background:#fff}"
            "td,th{border-bottom:1px solid #e4ddcf;padding:8px;text-align:left;vertical-align:top}.box{background:#fff;border-radius:14px;padding:14px 16px;"
            "box-shadow:0 2px 8px rgba(0,0,0,.06);margin:12px 0}.muted{color:#6b6256;font-size:.92em}.w{font-weight:600}")


def checklist_files(pack: dict, gid: str, business: str, out: str) -> list:
    items = pack["checklists"].get(gid)
    if not items:
        raise SystemExit(f"no checklist for {gid}")
    os.makedirs(out, exist_ok=True)
    today = dt.date.today().isoformat()
    md = [f"# {business}: Google Business Profile checklist ({today})", "", "Mark each line: OK, FIXED (by us), or TO DO (by you).", "",
          "| # | Area | Check | Status | Note |", "|---|---|---|---|---|"]
    md += [f"| {i} | {x['area']} | {x['check']} |  |  |" for i, x in enumerate(items, 1)]
    md += ["", "Why each line matters:", ""] + [f"- **{x['area']}**: {x['why']}" for x in items]
    md += ["", "Rules we follow: your real business name, a real address or a service area, honest reviews only. No one can promise a ranking."]
    rows = "".join(f"<tr><td>{i}</td><td class='w'>{html.escape(x['area'])}</td><td>{html.escape(x['check'])}<div class='muted'>{html.escape(x['why'])}</div></td>"
                   f"<td>&#9744; OK<br>&#9744; Fixed<br>&#9744; To do</td></tr>" for i, x in enumerate(items, 1))
    page = (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{html.escape(business)} Google profile checklist</title><style>{PAGE_CSS}</style></head><body><main>"
            f"<h1>{html.escape(business)}</h1><p>Google Business Profile checklist, {today}</p><table><tr><th>#</th><th>Area</th><th>Check</th><th>Status</th></tr>{rows}</table>"
            "<p class='muted'>We follow Google's guidelines: real name, real address or service area, honest reviews only. No one can promise a ranking.</p>"
            "</main></body></html>\n")
    slug = slugify(business)
    files = [os.path.join(out, f"{slug}_gbp_checklist.md"), os.path.join(out, f"{slug}_gbp_checklist.html")]
    for p, body in zip(files, ("\n".join(md) + "\n", page)):
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(body)
    return files


GENERIC_FIXES = [
    ("Compress and resize images (WebP or JPEG, no wider than 1600 px)", "The biggest speed win on most small sites"),
    ("Load chat, maps and video after the page (lazy load)", "Third-party widgets often slow the first view"),
    ("Make the phone number tap-to-call (tel: link) in the header", "Most local visitors are on a phone"),
    ("One clear button above the fold: Call, Book or Get a quote", "Visitors should know the next step in 3 seconds"),
    ("Unique page title and Google description on every page", "What Google shows in search results"),
    ("https everywhere (padlock), and http redirects to https", "Chrome marks http sites 'Not secure'"),
    ("Name, address and phone the same as the Google Business Profile", "Consistent details help local search"),
    ("Contact form tested: it sends to the right inbox", "Broken forms lose leads silently"),
    ("Text size 16 px or more on phones, buttons at least 44 px tall", "Easy to read and tap"),
    ("Remove unused plugins, fonts and scripts", "Less code, faster pages"),
]


def report_html(business: str, url: str, audit: dict | None, today: str) -> str:
    issues = sorted((audit or {}).get("issues") or [], key=lambda x: -int(x.get("weight", 0)))
    facts = (audit or {}).get("facts") or {}
    found = "".join(f"<tr><td>{html.escape(str(i.get('text', '')))}</td><td>{int(i.get('weight', 0))}</td></tr>" for i in issues) or \
        "<tr><td colspan='2'>The automatic check found no basic problems (or could not run: see the note below).</td></tr>"
    fact_rows = "".join(f"<tr><td>{html.escape(str(k))}</td><td>{html.escape(str(v))}</td></tr>" for k, v in facts.items())
    fixes = "".join(f"<li><span class='w'>{html.escape(a)}</span><div class='muted'>{html.escape(b)}</div></li>" for a, b in GENERIC_FIXES)
    note = "" if audit else "<p class='muted'>Automatic check not available here (the agency kit is not installed or the site could not be reached). The checks below were done by hand.</p>"
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{html.escape(business)} website report</title><style>{PAGE_CSS}</style></head><body><main>"
            f"<h1>{html.escape(business)}: website report</h1><p>{html.escape(url)} &middot; checked {today}</p>{note}"
            "<h2>Speed on a phone (Google PageSpeed Insights, Mobile)</h2><div class='box'><table>"
            "<tr><td>Performance</td><td>__ / 100</td></tr><tr><td>Accessibility</td><td>__ / 100</td></tr>"
            "<tr><td>Best practices</td><td>__ / 100</td></tr><tr><td>SEO</td><td>__ / 100</td></tr>"
            "<tr><td>Largest Contentful Paint</td><td>__ s</td></tr></table><p class='muted'>Measured at pagespeed.web.dev on the date above. Scores move from run to run; re-test after the fixes.</p></div>"
            f"<h2>What the check found</h2><div class='box'><table><tr><th>Problem</th><th>Weight</th></tr>{found}</table></div>"
            + (f"<h2>Facts</h2><div class='box'><table>{fact_rows}</table></div>" if fact_rows else "") +
            f"<h2>Top fixes, easiest and biggest first</h2><div class='box'><ol>{fixes}</ol></div>"
            "<p class='muted'>No one can promise a ranking or a score. This report shows what was measured on the date above and what will help customers on phones.</p>"
            "</main></body></html>\n")


def run_report(url: str, business: str, out: str, use_audit: bool = True) -> str:
    result = None
    if use_audit:
        try:
            from agency import audit as A               # B1's polite one-page check (robots.txt obeyed, one fetch, cached)
            result = A.audit(url)
        except Exception as e:                           # kit missing or the site unreachable: the report says so
            print(f"  (automatic check skipped: {type(e).__name__})")
    os.makedirs(out, exist_ok=True)
    p = os.path.join(out, f"{slugify(business)}_website_report.html")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(report_html(business, url, result, dt.date.today().isoformat()))
    return p


# ------------------------------------------------------------------------------------------------ CLI
def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ("order", "checklist", "report"):
        cmd, rest = argv[0], argv[1:]
        ap = argparse.ArgumentParser(prog=f"python -m money_machines.gig_pack {cmd}")
        if cmd == "order":
            ap.add_argument("--gig", default="local-website")
            ap.add_argument("--name", required=True)
            ap.add_argument("--category", required=True, help="plumber, cafe, salon ... (B1's lead categories)")
            ap.add_argument("--city", default="")
            ap.add_argument("--phone", default="")
            ap.add_argument("--email", default="")
            ap.add_argument("--website", default="")
            ap.add_argument("--street", default="")
            ap.add_argument("--hours", default="", help='OpenStreetMap style, e.g. "Mo-Fr 08:00-17:00; Sa 09:00-13:00"')
            ap.add_argument("--description", default="")
            ap.add_argument("--out", default=None)
            a = ap.parse_args(rest)
            gig(load(), a.gig)
            data = make_lead(a.name, a.category, a.city, a.phone, a.email, a.website, a.street, a.hours, a.description, a.gig)
            slug = data["leads"][0]["slug"]
            out = a.out or os.path.join(OUT, "orders", slug)
            os.makedirs(out, exist_ok=True)
            p = os.path.join(out, "lead.json")
            with open(p, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=1)
            print(f"order file: {p}")
            print(f"next: python -m agency.build_site --leads {p} --id {slug}")
            return 0
        ap.add_argument("--gig", default="gbp-setup")
        ap.add_argument("--business", required=True)
        ap.add_argument("--out", default=None)
        if cmd == "report":
            ap.add_argument("--url", required=True)
            ap.add_argument("--no-audit", action="store_true", help="do not open the site (hand checks only)")
        a = ap.parse_args(rest)
        out = a.out or os.path.join(OUT, "orders", slugify(a.business))
        if cmd == "checklist":
            for p in checklist_files(load(), a.gig, a.business, out):
                print(p)
        else:
            print(run_report(a.url, a.business, out, use_audit=not a.no_audit))
        return 0
    ap = argparse.ArgumentParser(prog="python -m money_machines.gig_pack", description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="is each gig's tool installed here?")
    ap.add_argument("--md", nargs="?", const=DOC, help="write the Markdown pack (default docs/GIG_PACK.md)")
    ap.add_argument("--validate", action="store_true")
    a = ap.parse_args(argv)
    pack = load()
    rc = 0
    if a.validate or not (a.check or a.md):
        probs = validate(pack)
        print("gig pack: OK (all 8 gigs inside Fiverr's limits and our rules)" if not probs else "\n".join(probs))
        rc = 1 if probs else 0
    if a.check:
        for gid, mod, ok, status in tool_status():
            print(f"{'ready  ' if ok else 'waiting'}  {gid:18s} {mod:30s} {status}")
    if a.md:
        with open(a.md, "w", encoding="utf-8") as fh:
            fh.write(render_md(pack))
        print(f"wrote {a.md}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
