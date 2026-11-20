# Web · Offers (agency/offers/): the money side of the website business

`tools/web_public/agency/offers/` is a new page (phone first, AGORA look, no backend). It has five tabs:

| Tab | What it does |
|---|---|
| Prices | 3 packages from the research team's estimates: **Starter site $1,500 + $79/mo, Call engine $500 + $299/mo (Most picked, 3-month minimum), 3D Signature from $2,500 + $79/mo**. Each card shows what's included, delivery days, the monthly plan, and **what the owner keeps per hour** after hard costs, compared with his hourly target (editable, default $60/h). Plus the research extras: missed-call text-back $199 + $149/mo, phone-scan 3D tour $500 a scan + $25/mo, Google profile clean-up $499 a location, before/after showcase, service-area pages, accessibility + speed fix, copy per page. Monthly extras add to the monthly plan. |
| Proposal | Pick the business (names from the Agency's leads list), the package, extras, rush (+25 %, half the days) and a discount. It shows a clean one-page proposal (lines, total, 50 % deposit / balance, monthly plan, days, what's included, valid 14 days). **Save as PDF** prints only the sheet (iPhone print/share sheet -> Save to Files / send). **Share as text** sends it as a message. **Make the deposit invoice** adds it to Money. The owner-only margin line is never printed. |
| Terms | 9 plain-words items to agree on (50 % deposit, written scope, 2 rounds of changes, client sends content, hosting + domain in the client's name, who owns what, monthly plan 30 days notice / 3-month minimum on Growth, late payment, logins). Tick boxes. Labelled **Not legal advice**. |
| Money | Monthly clients (MRR, next due on the same day each month, clamped to month end, LATE in red with words, Paid / Stop / Delete). Invoices (open total, Paid, PDF per invoice). Download / load a copy (JSON). |
| Goal | For $1,000 / $3,000 / $5,000 a month: the gap from today's MRR, how many monthly clients of each plan, or how many builds a month (and the hours). A progress bar on the top card. |

- **Prices are the research estimates** (`offers.json`, source: research/handoff/2026-11-20/web/research/offers.json, day-archive 3110fc34), the same as the Agency showcase.
  The page says they are estimates. To change a price: `offers.json` only.
- **The HQ tile:** every save writes localStorage `agency.offers.summary` = {n, label, next, t, pipe: {proposal, paid}, mrr} (the HUB team's shape).
  proposal = proposals sent (Save as PDF / Share), paid = paying monthly clients, mrr = $ a month.
- **Saved on the phone only:** localStorage `agency.offers.v1` plus a downloaded copy. Nothing is sent, and there is no paid service, no key and no owner detail.
- **Checks:** `python -X utf8 -m tests.test_web_offers` 55/55. Static: no network but its own JSON, no innerHTML, not-legal-advice, print rules.
  Node: margins, quote, rush/discount/deposit, proposal text, month-end due dates, MRR/late, goals, junk state. Browser at 390 and 320:
  no sideways scroll, every control >= 44 px, proposal $648, the PDF holds only the sheet, the deposit invoice, the client survives a reload,
  arrow-key tabs, row buttons named for VoiceOver. a11y sweep (12 screens) **100/100, CLS 0**. smoke 10/10.
  It's in run_area: `AREAS["agency"].append("web_offers")` (above main()).
- **Gotcha found and fixed:** the kit hides `main#app` (veil) until the page calls `OLYMPUS.ready()`. Without that call the page stays blank for 12 s.
  Any new Agency sub-page must call it.
