# LEAD_WIRES: one price book + the safe caller commission (day-caller2, 2026-11-21, base pc 89f538e5)

## The book: `agency/pricebook.json` (+ `agency/pricebook.py`)
Starter site **$1,500 + $79/month** (or **$149/month x 12**, nothing upfront) · Call engine **$500 + $299/month** (3-month minimum) ·
3D Signature **from $2,500 + $79/month** · 50% deposit ($750) · invoices due in 14 days · 2 revision rounds ·
**care plan $79/month with a 12-month term**, then month to month with 30 days' notice, edits up to 30 min a month · MD sales tax 3% (to confirm).
**Commission:** $300 per sale OR $40 per booked call that shows, **one per business** (first caller to log it), owed only after the client's
money **cleared** (deposit + launch, or the 3rd $149 payment), paid within 3 days, **clawed back** if refunded within 30 days of clearing.

`python -m agency.pricebook --check` reads every place below and lists anything that disagrees. `tests/test_pricebook.py` runs it (5/5)
and also proves a changed number is caught.

## What disagreed today, now fixed
| Where | Was | Now |
|---|---|---|
| `agency/config.example.json` + `agency/storefront/config.json` (the "one source" for pitch, billing, storefront, money math) | Starter $499 + $49, Growth $999 + $79, Pro $1,999 + $129 | the book's 3 packages (ids kept: starter / growth = Call engine / pro = 3D Signature) |
| `tools/web_public/agency/agencycore.js` (Agency page built-in defaults) | $499 / $999 / $1,999 | the book |
| `tools/web_public/agency/offers/offers.json` terms.monthly | "cancel with 30 days notice" | 12-month care-plan term, then 30 days' notice |
| `SERVICES_AGREEMENT.md`, `client_deliver.py` CARE_PLAN | care plan cancel any time | 12-month term, then 30 days |
| `agency/portal.py` commissions | paid at the caller's own "Won", both $300 + $40 possible per caller | paid only after `paid` ledger shows cleared money; one per business; 30-day clawback; new `python -m agency.portal paid <id/code> deposit|launch|monthly|refund [date]` |
| Caller pack, contractor terms, job post, targets, docs/HUMAN_CALLER.md | "pick one plan", paid at client payment | one per business, after it clears, clawback; targets recomputed (middle: $1,120 + $79/mo to the owner) |
| `agency/pitch.py` | roofers etc. pitched "Growth $999" | every concept-site pitch sells the Starter site |
| `agency/pricing.json` package_mix | 60/30/10 | 90% Starter / 10% Call engine (avg sale $1,400 + $101) |
| `tools/biz_publish.py`, `business/work.json`, `business/fixture.json`, `agency/fixture.json`, `agency/leads.json` (sample), the Fort Collins demo pitch kits, `call_fixture.json`, `call.html` | $499 / $999 / $49 a month | the book (fixtures regenerated) |
| `docs/AGENCY.md`, `docs/BUSINESS.md`, `agency/billing/PAYMENTS.md` | old 3-package prices | the book |

Not changed on purpose: `agency/pricing.json` market research ranges, `agency/storefront/examples/examples.json` (other agencies'
prices), client-report fixtures, `$49 a month for 4 posts` (a different service), `docs/COLD_CALLING_RULES.md` history.
The AI receptionist (`tools/caller/`) is not on pc. When it lands, `pricebook.check` also checks its `price_line`.

## Wires (lead)
1. run_area: `AREAS["agency"].append("pricebook")   # day-caller2 2026-11-21: one price book, every place in sync`
2. Pages whose content changed (cache tags / sw are the lead's): agency/agencycore.js, agency/call.html, agency/call_fixture.json,
   agency/leads.json, agency/fixture.json, agency/offers/offers.json, business/work.json, business/fixture.json.
3. STATE "Waiting on the owner": record cleared client money with `python -m agency.portal paid ...` (that is what pays the caller).

## Tests run here
pricebook 5/5 · agency 104/104 · biz_models 51/51 · agency_billing 85/85 · cold_calls 115/115 · web_offers 35/35 · factory2 22/22 ·
agency_autopilot 55/55 · web_outreach 31/31 · web_portal 38/38 (browser part skipped: no Python Playwright here) · business_work 15/15 ·
dnc_scrub 9/9 · intake_page 6/6 · web_research 8/8 · smoke 10/11 (zenith_mode: no Python Playwright here, unrelated).
agency_storefront: parts a + b pass (prices, report); part c is browser-only and could not run here: **please run it on landing.**
