"""THE ONE PRICE BOOK reader (agency/pricebook.json). Everything else reads these numbers or is checked against them.

  python -m agency.pricebook            print the book in plain words
  python -m agency.pricebook --check    every known place that shows a price or a term: in sync? (exit 1 + the list if not)
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOK = os.path.join(ROOT, "agency", "pricebook.json")


def load(path: str = BOOK) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def pkg(book: dict, pid: str) -> dict:
    return next(p for p in book["packages"] if p["id"] == pid or p.get("config_id") == pid)


def usd(x) -> str:
    return f"${x:,.0f}" if float(x) == int(x) else f"${x:,.2f}"


def words(book: dict | None = None) -> dict:
    """The sentences every page may reuse, so they never drift."""
    b = book or load()
    s, cp, nu, cm = pkg(b, "starter"), b["care_plan"], b["no_upfront"], b["commission"]
    dep = s["setup"] * b["deposit_pct"] / 100
    return {
        "starter": f"{usd(s['setup'])} + {usd(s['monthly'])}/month",
        "no_upfront": f"{usd(nu['monthly'])}/month for {nu['months']} months, nothing upfront",
        "price_line": (f"The Starter site is {usd(s['setup'])} once plus {usd(cp['monthly'])} a month for hosting and small changes, "
                       f"or {usd(nu['monthly'])} a month for {nu['months']} months with nothing upfront."),
        "deposit": usd(dep),
        "care": (f"Care plan {usd(cp['monthly'])}/month: a {cp['term_months']}-month term, then month to month; cancel with "
                 f"{cp['notice_days']} days' notice; small edits up to {cp['edit_minutes']} minutes a month"),
        "commission": (f"{usd(cm['sale'])} per sale OR {usd(cm['booked_show'])} per booked call that shows (one per business), paid within "
                       f"{cm['pay_within_days']} days after the client's money clears; clawed back if refunded within {cm['clawback_days']} days"),
    }


# ------------------------------------------------------------------------------------------------ the sync check
def _j(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return json.load(f)


def _t(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


TEXT_FILES = [   # (file, must contain each of these strings built from the book)
    "research/handoff/2026-11-21/close/SERVICES_AGREEMENT.md",
    "research/handoff/2026-11-21/close/PAYMENTS_INVOICES.md",
    "research/handoff/2026-11-21/close/YES_PLAYBOOK.md",
    "research/handoff/2026-11-21/caller/CALLER_PACK.md",
    "research/handoff/2026-11-21/caller/CONTRACTOR_TERMS.md",
    "research/handoff/2026-11-21/caller/JOB_POSTS.md",
    "research/handoff/2026-11-21/caller/TARGETS.md",
    "docs/HUMAN_CALLER.md",
    "tools/client_deliver.py",
    "tools/agency_site.py",
    "agency/billing/PAYMENTS.md",
    "docs/AGENCY.md",
    "docs/BUSINESS.md",
]
PUBLISHED = [   # generated / data files the phone pages show: no old package price may survive in them
    "tools/web_public/agency/leads.json", "tools/web_public/agency/fixture.json", "tools/web_public/agency/call_fixture.json",
    "tools/web_public/agency/call.html", "tools/web_public/business/work.json", "tools/web_public/business/fixture.json",
    "agency/demo/fort-collins/run.json",
]
STALE = re.compile(r"\$499\b|\$49 a month|\$49/mo|\$999\b|\$1,999\b|\$129\b|\$1,299\b")


def check(book: dict | None = None) -> list:
    """[(where, what is wrong)]; [] = everything says the same thing."""
    b = book or load()
    s, cs, sg = pkg(b, "starter"), pkg(b, "callengine"), pkg(b, "signature3d")
    cp, nu, cm = b["care_plan"], b["no_upfront"], b["commission"]
    bad = []

    def want(where, ok, what):
        if not ok:
            bad.append((where, what))

    # structured sources
    off = _j("tools/web_public/agency/offers/offers.json")
    got = {p["id"]: p for p in off.get("packages") or []}
    for p in b["packages"]:
        o = got.get(p["id"]) or {}
        want("offers.json", o.get("price") == p["setup"] and o.get("monthly") == p["monthly"], f"{p['id']}: {o.get('price')}/{o.get('monthly')} != {p['setup']}/{p['monthly']}")
        want("offers.json", o.get("name") == p["name"], f"{p['id']}: name {o.get('name')!r} != {p['name']!r}")
    want("offers.json", off.get("deposit") == b["deposit_pct"] / 100, f"deposit {off.get('deposit')}")
    terms = {t["id"]: t["text"] for t in off.get("terms") or []}
    want("offers.json", f"{cp['term_months']}-month" in terms.get("monthly", "") and f"{cp['notice_days']} days" in terms.get("monthly", ""),
         "terms.monthly must name the 12-month care-plan term and the 30-day notice")
    want("offers.json", f"{b['invoice']['due_days']} days" in terms.get("late", ""), "terms.late due days")
    want("offers.json", "Two rounds" in terms.get("revisions", "") and b["revision_rounds"] == 2, "terms.revisions")
    for rel, key_s, key_m in (("agency/config.example.json", "setup", "monthly"), ("agency/storefront/config.json", "setup_usd", "monthly_usd")):
        cfg = _j(rel)
        for p in b["packages"]:
            c = next((x for x in cfg.get("packages") or [] if x.get("id") == p["config_id"]), {})
            want(rel, c.get(key_s) == p["setup"] and c.get(key_m) == p["monthly"] and c.get("name") == p["name"],
                 f"{p['config_id']}: {c.get('name')} {c.get(key_s)}/{c.get(key_m)} != {p['name']} {p['setup']}/{p['monthly']}")
    portal = _j("tools/web_public/agency/portal/portal.json")
    want("portal.json", portal.get("prices", {}).get("starter") == words(b)["starter"], f"prices.starter {portal.get('prices', {}).get('starter')!r}")
    want("portal.json", portal.get("prices", {}).get("monthly") == words(b)["no_upfront"], f"prices.monthly {portal.get('prices', {}).get('monthly')!r}")
    want("portal.json", portal.get("commission", {}).get("sale") == cm["sale"] and portal.get("commission", {}).get("booked_show") == cm["booked_show"], "commission")
    ps = _t("agency/portal.py")
    want("agency/portal.py", f'"starter": "{words(b)["starter"]}"' in ps and f'"sale": {cm["sale"]}, "booked_show": {cm["booked_show"]}' in ps, "DEFAULT_CONF prices / commission")
    want("agency/portal.py", "clawback_days" in ps and "def paid_ledger" in ps, "commissions must wait for cleared payments and claw back refunds")
    # texts
    w = words(b)
    must = {
        "research/handoff/2026-11-21/close/SERVICES_AGREEMENT.md": [usd(s["setup"]), w["deposit"], usd(nu["monthly"]), f"{nu['months']} months",
                                                                    usd(cp["monthly"]), f"{cp['term_months']}-month", f"{cp['notice_days']} days",
                                                                    f"{b['invoice']['due_days']} days", "Two rounds", f"{cp['edit_minutes']} minutes"],
        "research/handoff/2026-11-21/close/PAYMENTS_INVOICES.md": [w["deposit"], usd(cp["monthly"]), usd(nu["monthly"]), f"{b['md_sales_tax_pct']}%"],
        "research/handoff/2026-11-21/close/YES_PLAYBOOK.md": [w["deposit"], usd(s["setup"]), usd(nu["monthly"]), usd(cp["monthly"])],
        "research/handoff/2026-11-21/caller/CALLER_PACK.md": [w["price_line"], usd(cm["sale"]), usd(cm["booked_show"]), f"{cm['clawback_days']} days", "cleared"],
        "research/handoff/2026-11-21/caller/CONTRACTOR_TERMS.md": [usd(cm["sale"]), usd(cm["booked_show"]), "cleared", f"{cm['clawback_days']} days", "one commission per business"],
        "research/handoff/2026-11-21/caller/JOB_POSTS.md": [usd(cm["sale"]), usd(cm["booked_show"]), usd(s["setup"]), "clears"],
        "research/handoff/2026-11-21/caller/TARGETS.md": [usd(cm["sale"]), usd(cm["booked_show"]), usd(cp["monthly"])],
        "docs/HUMAN_CALLER.md": [usd(cm["sale"]), usd(cm["booked_show"]), "clears"],
        "tools/client_deliver.py": [usd(cp["monthly"]), f"{cp['term_months']}-month", f"{cp['notice_days']} days", f"{cp['edit_minutes']} minutes"],
        "tools/agency_site.py": [usd(nu["monthly"]), f"{nu['months']} months", usd(cp["monthly"])],
        "agency/billing/PAYMENTS.md": [usd(s["setup"]), usd(cp["monthly"]), usd(nu["monthly"])],
        "docs/AGENCY.md": [usd(s["setup"]), usd(cp["monthly"])],
        "docs/BUSINESS.md": [usd(s["setup"]), usd(cp["monthly"])],
    }
    for rel in TEXT_FILES:
        try:
            t = _t(rel)
        except OSError:
            bad.append((rel, "missing"))
            continue
        for m in must.get(rel, []):
            want(rel, m in t, f"must say {m!r}")
        st = STALE.findall(t)
        want(rel, not st, f"old prices still shown: {sorted(set(st))}")
    old_setup = re.compile(r"\$499\b|\$999\b|\$1,999\b|\"setup\": 499\b|\"setup\": 999\b")
    for rel in PUBLISHED:
        hits = old_setup.findall(_t(rel))
        want(rel, not hits, f"old package prices still published: {sorted(set(hits))}")
    core = _t("tools/web_public/agency/agencycore.js")
    for p in b["packages"]:
        want("agencycore.js", f"{{ id: '{p['config_id']}', name: '{p['name']}', setup: {p['setup']}, monthly: {p['monthly']} }}" in core,
             f"built-in default for {p['config_id']}")
    # the call script and the AI receptionist (when present) say the same price line
    cs_ = _j("tools/web_public/agency/callscript.json")
    want("callscript.json", not STALE.search(json.dumps(cs_)), "old prices in the call script")
    if os.path.exists(os.path.join(ROOT, "tools", "caller", "settings.json")):
        want("tools/caller/settings.json", _j("tools/caller/settings.json").get("price_line") == w["price_line"], "price_line")
    _ = (cs, sg)
    return bad


def main(argv=None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    b = load()
    if a[:1] == ["--check"]:
        bad = check(b)
        for where, what in bad:
            print(f"  [FIX] {where}: {what}")
        print("  [OK] every place says the same prices and terms" if not bad else f"  {len(bad)} place(s) disagree with agency/pricebook.json")
        return 1 if bad else 0
    for k, v in words(b).items():
        print(f"  {k:12} {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
