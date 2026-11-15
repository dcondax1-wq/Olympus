"""THE LISTING KIT (team BIZ, 2026-11-15): every digital product's upload sheet in ONE file, ready to copy into a free shop.

    python -m money_machines.products.listing_kit            -> docs/BUSINESS_LISTING_KIT.md (+ money_machines/products/listing_kit.json)
    python -m money_machines.products.listing_kit --check    exit 1 when a product, zip name, cover or listing text is missing

It reads the catalog (catalog.json) and each product's own listing (shop/listing.json, the eval tracker's listing.json), so it
never invents a price or a claim. It uploads nothing: the owner makes the accounts and presses Publish.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DOC = os.path.join(ROOT, "docs", "BUSINESS_LISTING_KIT.md")
JSON_OUT = os.path.join(HERE, "listing_kit.json")
FOLDER = {"prop-eval-tracker": "eval_tracker", "local-site-templates": "site_templates", "social-post-pack": "social_kit",
          "agency-starter-kit": "agency_kit", "trader-routine-planner": "trader_planner"}
ZIP_FALLBACK = {"prop-eval-tracker": "prop_eval_tracker_v1.0.zip"}

SHOPS = [
    {"name": "Payhip (start here)", "cost": "free plan: 5% a sale + card fees", "url": "payhip.com",
     "steps": ["Sign up free, connect PayPal or Stripe for payouts", "Products > Add new > Digital download", "Upload the zip, paste title / description / FAQ, add the 3 wide covers, set the price, Publish"]},
    {"name": "Gumroad (second shop)", "cost": "free: 10% + $0.50 a sale (30% on sales its Discover page brings)", "url": "gumroad.com",
     "steps": ["Sign up free, add your bank for payouts (identity check before bigger payouts)", "New product > Digital product", "Upload the zip, paste the text, the 3 wide covers, the price, Publish"]},
    {"name": "Etsy (search traffic)", "cost": "$0.20 a listing (4 months) + 6.5% + payment fees", "url": "etsy.com/sell",
     "steps": ["Open a shop (Etsy asks for a card and ID; the $0.20 listing fee is the one cost here)", "Add a listing: Digital, 'I did', made with the help of AI tools in the description",
               "The 3 square covers, the 13 tags, the price, the zip as the digital file"]},
]


def _read(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def products() -> list:
    cat = _read(os.path.join(HERE, "catalog.json"))
    out = []
    for c in cat["products"]:
        folder = os.path.join(HERE, FOLDER.get(c["id"], ""))
        lp = os.path.join(folder, "shop", "listing.json")
        if not os.path.isfile(lp):
            lp = os.path.join(folder, "listing.json")
        li = _read(lp) if os.path.isfile(lp) else {}
        shop = os.path.join(folder, "shop") if os.path.isdir(os.path.join(folder, "shop")) else folder
        covers = sorted(f for f in os.listdir(shop) if f.lower().endswith(".jpg") and ("cover" in f or "screenshot" in f)) if os.path.isdir(shop) else []
        desc = li.get("description")
        out.append({"id": c["id"], "name": c["name"], "price_usd": float(li.get("price_usd") or c["price_usd"]),
                    "title": li.get("title", ""), "short": li.get("short", ""),
                    "description": "\n\n".join(desc) if isinstance(desc, list) else str(desc or ""),
                    "tags": list(li.get("tags_etsy") or [])[:13], "faq": [list(x) for x in li.get("faq") or [] if isinstance(x, (list, tuple)) and len(x) == 2],
                    "refund": li.get("refund", "Digital download: if something does not work as described, message me within 14 days and I will fix it or refund you."),
                    "zip": li.get("zip") or ZIP_FALLBACK.get(c["id"], ""), "build": c["build"],
                    "covers_wide": [os.path.relpath(os.path.join(shop, f), ROOT).replace(os.sep, "/") for f in covers if "square" not in f],
                    "covers_square": [os.path.relpath(os.path.join(shop, f), ROOT).replace(os.sep, "/") for f in covers if "square" in f],
                    "net": li.get("net_per_sale_usd") or {}, "sales_month_est": c.get("sales_month_est", ""),
                    "listing_md": os.path.relpath(os.path.join(shop, "listing.md") if os.path.isfile(os.path.join(shop, "listing.md")) else os.path.join(folder, "listing.md"), ROOT).replace(os.sep, "/"),
                    "risk": c.get("risk", "")})
    return out


def problems(ps: list) -> list:
    bad = []
    for p in ps:
        for k in ("title", "description", "zip"):
            if not p[k]:
                bad.append(f"{p['id']}: no {k}")
        if len(p["tags"]) < 5:
            bad.append(f"{p['id']}: fewer than 5 tags")
        if not p["covers_wide"] or not p["covers_square"]:
            bad.append(f"{p['id']}: covers missing")
        for c in p["covers_wide"] + p["covers_square"]:
            if not os.path.isfile(os.path.join(ROOT, c)):
                bad.append(f"{p['id']}: {c} not found")
    return bad


def markdown(ps: list) -> str:
    L = ["# Listing kit: the 5 digital products, ready to upload (generated)", "",
         "Made by `python -m money_machines.products.listing_kit` from each product's own listing (no new claims). Nothing is uploaded",
         "for you: you make the free accounts and press Publish. Sales are ESTIMATES: expect 0-10 a month per product until an Instagram",
         "bio or search sends buyers.", "",
         "| Product | Price | You keep (Payhip / Gumroad / Etsy) | Upload zip | Sales a month (estimate) |", "|---|---|---|---|---|"]
    for p in ps:
        n = p["net"]
        keep = " / ".join(f"${v:,.2f}" for v in n.values()) if n else "-"
        L.append(f"| {p['name'].split(':')[0].split('(')[0].strip()} | ${p['price_usd']:,.0f} | {keep} | `{p['zip']}` | {p['sales_month_est']} |")
    L += ["", "## Step 1: make the 5 zips (PC, 1 minute)", "", "```", "python -m money_machines.products.build_all --zip", "```",
          "They land in `money_machines/out/products/`. Plain Python, no browser needed.", "", "## Step 2: where to list (all free to start)", ""]
    for s in SHOPS:
        L.append(f"**{s['name']}** ({s['url']}): {s['cost']}.")
        L += [f"{i}. {x}" for i, x in enumerate(s["steps"], 1)] + [""]
    L += ["## Step 3: each product (copy, paste, upload)", ""]
    for p in ps:
        L += [f"### {p['title'] or p['name']}", "", f"- **Price:** ${p['price_usd']:,.0f}", f"- **Zip:** `money_machines/out/products/{p['zip']}` (made by `{p['build']}`)",
              f"- **Wide covers (Payhip, Gumroad):** " + ", ".join(f"`{c}`" for c in p["covers_wide"]),
              f"- **Square covers (Etsy):** " + ", ".join(f"`{c}`" for c in p["covers_square"]),
              f"- **Etsy tags (13):** " + ", ".join(p["tags"]), f"- **Full listing with the price reasoning and fee table:** `{p['listing_md']}`", "",
              "**Short line:** " + p["short"], "", "**Description:**", "", p["description"], ""]
        if p["faq"]:
            L += ["**FAQ:**", ""] + [f"- **{q}** {a}" for q, a in p["faq"]] + [""]
        L += [f"**Refund line:** {p['refund']}", "", f"**Watch out:** {p['risk']}", ""]
    L += ["## The rules (keep them)", "",
          "- No brand or platform names in titles, tags or pictures; no income, ranking, pass or result promises.",
          "- Etsy: say the files were made with the help of AI tools; real reviews only, never bought or swapped.",
          "- Trading products: no results, no signals, no firm names; keep the risk line.",
          "- The agency kit's agreement is NOT LEGAL ADVICE (it says so in the file, the licence and the listing).", ""]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="One listing kit for the 5 digital products (uploads nothing).")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    ps = products()
    bad = problems(ps)
    if a.check:
        print("\n".join(bad) if bad else f"OK: {len(ps)} products ready to list")
        return 1 if bad else 0
    with open(DOC, "w", encoding="utf-8") as fh:
        fh.write(markdown(ps))
    with open(JSON_OUT, "w", encoding="utf-8") as fh:
        json.dump({"v": 1, "kind": "listing-kit", "shops": SHOPS, "products": ps}, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print(f"Wrote {DOC} and {JSON_OUT} ({len(ps)} products{'; problems: ' + '; '.join(bad) if bad else ''})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
