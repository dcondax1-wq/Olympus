# Website Factory: outreach + close kit (agency/outreach/, day-a11y 2026-11-20)

A new owner-only page, `tools/web_public/agency/outreach/` (`<meta name="robots" content="noindex, nofollow">`), with four tabs:

| Tab | What it does |
|---|---|
| Today | Today's 20 businesses: anyone Interested comes first (send the agreement), then the follow-ups that are due (day 3, day 7), then untouched leads (hot -> warm -> cold, phone first, best score). Each card has Call (`tel:`), Copy opener, Copy voicemail, Copy email (the step that is due, with its subject) and Email (`mailto:` only when the lead has an email), the demo link, and 6 status buttons: Called, Left voicemail, Emailed, Interested, Not interested, Won. |
| Words | The rules (calls by hand, never a cold text, CAN-SPAM parts, business hours, not legal advice), the 20-second opener, the voicemail, what to say when they say yes, the day-0/3/7 emails, and 8 objections with answers. |
| Close | Their business + who signs + plan (Starter $1,500 + $79/mo, Call engine $500 + $299/mo, no upfront $149/mo x 12; prices read from agency/offers/offers.json). It fills a 1-page plain-English agreement (not legal advice) and the deposit invoice, both "as PDF" through the phone's print/share. The payment line is an **OWNER STEP**: his own free payment account, no paid service. A 9-step delivery checklist marks who does each step (you / the client / Claude): the client buys the domain in their name, free static hosting, the client verifies the Google Business Profile and adds us as Manager, a launch check, then the final invoice and the review ask. |
| Me | The owner's name, business, phone, email and postal address. They are saved on the phone only and fill every message. The page shows `[Your name]` / `[Business name]` / `[postal address]` placeholders until then, so the owner's name never enters the repo. |

- **Compliance:**
  - No `sms:` link anywhere.
  - Every email has a true subject, the sender's name and business, the postal address and a "reply no thanks" line. The first one says "one-time business offer". Day 7 says it will stop.
  - Calls are dialled by hand only; no voicemail drops.
  - "Not interested" means never contact again.
- **Storage (this phone only):**
  - Status marks go in **`agency.leads.status.v1`** = `{ <lead id>: { s, t } }`, the Leads page's own key. New `s` values: `voicemail`, `emailed`, `won`; the Leads page today knows `called`, `interested`, `no`.
  - The owner's details, the touches (`{ d, k: first|bump|last }`) and the checklist ticks go in `agency.outreach.v1`.
  - The HQ tile is `agency.outreach.summary` = `{n, label, next, t, pipe: {due, interested, won}}`.
- **Demo link per lead:**
  - `../sites/index.json` from the factory: `{ "sites": { "<lead id>": "<https url or path under agency/>" } }` or `{ "sites": [{ "id", "url" }] }`.
  - Otherwise `lead.demo_url`.
  - Otherwise the closest niche demo (`agency/demos/restaurant|detailer|roofer|estate|shed/`).
  - Links are absolute (the site's own address).
- **Checks:**
  - `python -X utf8 -m tests.test_web_outreach`: 46/46 (static + the words' compliance, Node core, browser at 390 and 320).
  - a11y sweep 100.
  - test_web_offers 55/55.
  - In run_area: `AREAS["agency"].append("web_outreach")`.
- **Shots:** `today-390.png`, `today-card-390.png`, `words-390.png`, `close-390.png` (390x844 @2x).
