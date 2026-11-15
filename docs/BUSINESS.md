# BUSINESS: every money model beside the trading (team BIZ, 2026-11-15)

Owner: "how are the other business models doing, build those". All $ are **ESTIMATES** taken from the teams' own docs
(`docs/AGENCY.md`, `docs/MONEY_MACHINES.md`), not promises. Nothing here posts, sends, emails or calls: you press every button.

| Model | Built | Still missing before the first $ | $ / month at 1 month | at 3 months | Your hours / week |
|---|---|---|---|---|---|
| **Website agency** | lead finder, demo sites, pitch kits, call list, Agency page, storefront, proposal / invoice / payment kit, upsells | your details in `agency/config.json`; free Netlify + Stripe accounts; about 60 calls by hand | $0-550 | $0-2,000 | 5-7 |
| **Freelance gigs** | 8 gig texts with prices, brand-kit and checklist tools | Fiverr account with ID check; publish 2 gigs | $0-100 | $0-400 | 6-10 |
| **Digital products** | 5 products, zips, covers, the listing kit | a free Payhip shop; upload 5 zips (15 min each) | $0-50 | $0-100 | 1-2 |
| Instagram: local tips | 30-day plan, images, posting sheet | the account; schedule in Meta Business Suite | $0 | $0-100 (agency clients it brings) | 2-3 |
| Instagram: eval journal | 30-day plan, images | the account; tracker link in bio | $0 | $0-30 | 2-3 |
| Rank-and-rent | plan only | a $12 domain (not free) and 3-12 months | $0 | $0 | 0 (paused) |
| Kalshi | bot, page, research | paused: no proven edge | $0 | $0 | 0 |
| **All** | | | **$0-700** | **$0-2,630** | **16-25** |

Why the agency month 3 is $0-2,000: one Starter sale is $499 + $49 a month; the range assumes 0-2 sales a month. The docs'
plan (4 sales a month, $5,000 a month by month 8) needs about 6 calls every working day and call rates that are still guesses.

## The one price list (fixed 2026-11-15)
Prices live in ONE place: `packages` in `agency/config.example.json` (your copy `agency/config.json` wins), read through
`agency.config.prices()`. The pitch, the email, the storefront, the Agency page, the money math, the billing kit (proposal,
agreement, invoice) and the Business page all read it. `agency/billing/packages.json` now holds only the wording of each plan.
Default: Starter $499 + $49 a month, Growth $999 + $79, Pro $1,999 + $129 (change them in your `agency/config.json`).

## What is new
| What | How |
|---|---|
| Business page (phone) | `tools/web_public/business/`: every model's next action, money range and the 7-day checklist. Reads `business.json` (made on the PC by `python tools/biz_publish.py`, gitignored) else `fixture.json` (DEMO) |
| The agency day in one double-click | **`AGENCY_DAY.bat`** = `python -m agency.day`: leads in your city -> 3 demo sites + pitch kits -> the call list -> the Business page -> `agency/out/TODAY.txt` |
| Listing kit | `docs/BUSINESS_LISTING_KIT.md` (`python -m money_machines.products.listing_kit`): the 5 products' titles, descriptions, tags, prices, covers and where to list free |
| Tests | `python -X utf8 -m tests.test_biz_models` |

## 7-day launch checklist
1. **Day 1, set up (1 h):** double-click `AGENCY_DAY.bat`, fill in `agency/config.json` (name, phone, email, postal address, city), save;
   make the free accounts (Netlify, Stripe, Payhip, Fiverr with your real name and ID check); double-click `AGENCY_DAY.bat` again.
2. **Day 2, first calls (1 h):** drop the 3 site folders on app.netlify.com/drop and press Publish; call 10 owners from Call today, by
   hand, 10:00-12:00 or 14:00-16:00; mark every call on the card.
3. **Day 3, shop and gigs (1 h):** upload the 5 products to Payhip with `docs/BUSINESS_LISTING_KIT.md`; publish the logo and
   Google-profile gigs on Fiverr (`docs/GIG_PACK.md`); make one Stripe payment link per plan.
4. **Day 4, calls and Instagram (1 h):** `AGENCY_DAY.bat`, 10 calls; new Instagram (Professional), schedule week 1 in Meta Business
   Suite; the shop link in the bio.
5. **Day 5, follow up (1 h):** call back everyone who asked; send the demo link only to those who said send it; 10 new calls;
   answer every Fiverr message the same day.
6. **Day 6, close (1 h):** a yes -> `python -m agency.billing kit` for the proposal and invoice with your payment link; tell Claude
   "Agency: <business> said yes" to build the live site; 10 calls.
7. **Day 7, count (15 min):** Agency page > Export; count calls, talks, demos, yeses; tell Claude the counts so the guessed call
   rates become yours.

## The rules that stay
Calls by hand, business hours, never a robot or a recording; anyone who says stop is marked Do not contact at once
(`docs/COLD_CALLING_RULES.md`). Emails only with your real name, email and postal address (CAN-SPAM). No fake reviews, no
income or ranking promises, the agreement is NOT LEGAL ADVICE. No paid services: every account above is a free plan.
