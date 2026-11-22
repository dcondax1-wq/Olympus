"""CLOSE-THE-SALE KIT, PC side (day-a11y 2026-11-22): the caller portal's proposal reads its numbers from ONE small file, made here from the
one price book (agency/pricebook.json), so a proposal can never quote another price.

    python -m agency.proposal            write tools/web_public/agency/portal/price.json (run after changing the price book)
    python -m agency.proposal --check    exit 1 when price.json is not what the price book says (agency.pricebook.check runs it too)

The proposal itself is drawn on the phone (portal/proposal.html + portalcore.js proposalFor): the business's concept link, the package and
price, the 7-day timeline, what we need from them and the deposit step. The agreement: docs/agency/AGREEMENT.md. Stdlib only."""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOK = os.path.join(ROOT, "agency", "pricebook.json")
OUT = os.path.join(ROOT, "tools", "web_public", "agency", "portal", "price.json")
VALID_DAYS = 14          # a proposal's prices hold for 14 days


def price_doc(book: dict | None = None) -> dict:
    b = book or json.load(open(BOOK, encoding="utf-8"))
    st = next(x for x in b["packages"] if x["id"] == "starter")
    nu, cp = b.get("no_upfront") or {}, b.get("care_plan") or {}
    dep = round(st["setup"] * b.get("deposit_pct", 50) / 100)
    return {"v": 1, "kind": "proposal-prices", "as_of": b.get("as_of", ""), "from": "agency/pricebook.json (python -m agency.proposal)",
            "package": {"name": st["name"], "setup": st["setup"], "monthly": st["monthly"], "pages": st.get("pages", 5), "days": st.get("days", 7)},
            "deposit_pct": b.get("deposit_pct", 50), "deposit": dep, "balance": st["setup"] - dep,
            "no_upfront": {"monthly": nu.get("monthly"), "months": nu.get("months")},
            "care": {"monthly": cp.get("monthly"), "term_months": cp.get("term_months"), "notice_days": cp.get("notice_days"), "edit_minutes": cp.get("edit_minutes")},
            "tax_pct": b.get("md_sales_tax_pct"), "invoice_due_days": (b.get("invoice") or {}).get("due_days"), "revision_rounds": b.get("revision_rounds"),
            "valid_days": VALID_DAYS}


def problems() -> list:
    try:
        have = json.load(open(OUT, encoding="utf-8"))
    except (OSError, ValueError):
        return ["tools/web_public/agency/portal/price.json is missing: run python -m agency.proposal"]
    want = price_doc()
    return [] if have == want else ["tools/web_public/agency/portal/price.json is not what the price book says: run python -m agency.proposal"]


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--check" in argv:
        p = problems()
        print("\n".join(p) or "  [OK] the proposal prices match the price book")
        return 1 if p else 0
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(price_doc(), f, indent=1)
        f.write("\n")
    print("  [OK] wrote tools/web_public/agency/portal/price.json from agency/pricebook.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
