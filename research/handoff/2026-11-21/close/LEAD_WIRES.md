# LEAD_WIRES: close kit (day-caller2, 2026-11-21)

New files only: `research/handoff/2026-11-21/close/*`, `tools/web_public/agency/intake/index.html`, `tests/test_intake_page.py`.

1. **Intake page** `tools/web_public/agency/intake/` (self-contained, no Olympus file, mailto only, noindex, no-referrer). It reads the
   studio address from `../portal/portal.json` "agency_email" (public), or `?to=`. `?code=FR-27` prefills the code. Wire it into the agency
   publish set and the sw/app tables if wanted (helpers don't touch those). It lives next to `portal/`, so the same public host works.
2. **run_area:** `AREAS["agency"].append("intake_page")   # day-caller2 2026-11-21: the client intake page (static checks + edits.json keys)`
3. **client_deliver.py lives on day-cities3 only** (not on pc 7adf312d). The intake's JSON keys match its docstring: domain, name, phone,
   email, hours, address, town, tagline, about, services [[name, line]], plus logo/photos added by Claude from the attachments.
   The intake also sends `code` and `need_domain`, which client_deliver ignores.
4. **Owner decision (STATE "Waiting on the owner"):** Maryland's 3% sales tax on IT/data services (HB 352, from 2025-07-01, NAICS
   5415/518) most likely covers web design and hosting. A free MD sales tax license and one email to the Comptroller are needed before
   the first invoice (PAYMENTS_INVOICES.md).
5. **Offers page:** the agreement uses the offers.json terms (50% deposit, 2 rounds, 14-day invoices, 30-day notice, ownership).
   If those change, change the agreement too.

Checks: `python -X utf8 -m tests.test_intake_page`; the page was rendered at 390 px in Chromium (no sideways scroll, no console errors,
the edits JSON is exact).
