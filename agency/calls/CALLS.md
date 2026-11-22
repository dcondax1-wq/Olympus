# Dial sheet for Mon 2026-11-23 (agency/calls/2026-11-23.csv)

Built by `python -X utf8 tools/dial_sheet.py --day 2026-11-23` from the caller list (tools/web_public/agency/portal/calllist.json)
and the lead rows (tools/web_public/agency/leads/towns/*.json). **Human dialing only**: no AI, robo or auto-dialed calls (illegal in
Maryland; docs/COLD_CALLING_RULES.md). Max 1 call a day per number, 3 in 24 hours, never Sundays or holidays.

**Before the first dial: the do-not-call scrub.** The sheet says `do-not-call: NOT SCRUBBED`: the registry check runs only on the PC
(`python -m agency.dnc_scrub`, then rebuild the sheet). Do not dial a number that has not been scrubbed.

## What is on it

| What | Count |
|---|---|
| Rows | **150** Maryland businesses with **no website**, all with a phone and a concept site link (`concept_site`, e.g. `f/bbf9erxz/` under the caller portal's site address) |
| Trades | 76 dentists / clinics / vets, 61 contractors / home services, 13 offices / professional services |
| Towns | Gaithersburg 40, Frederick 29, Rockville 25, Hagerstown 16, Ellicott City 15, Westminster 10, Germantown 6, others 9 |
| Call windows (Mon, ET) | clinics 10:00-11:30 am or 2:00-4:00 pm (front desk; ask for the office manager) / contractors 8:00-9:00 am or 4:00-6:00 pm (they are on job sites) / offices 9:00-11:00 am or 2:00-4:30 pm. Restaurants (not in today's top 150 by $) would be 9:30-11 am or 2-4 pm, never the lunch or dinner rush; salons are skipped on Mondays (often closed) |
| Left out | yesterday's first 100, 412 without a phone, 50 duplicate numbers, 519 with no legal window on Monday, every business with a working site |

Each row has a 2-line opener for its trade (from the call rules' own hook / issue words), the first-year ticket and the likely $.

**Ranking** = first-year ticket for the trade (price book: starter $1,500 + $79/month x 12, 10-20% call engine) x how likely the
trade buys (tools/first_calls weights: contractors / health 3, beauty / auto 2, services / food 1, retail 0.5) x hours open x heat
(hot 1.0, warm 0.75) x lane (no site 1.0, site down 0.6). **Not in the data:** review counts (OpenStreetMap / Overture carry none)
and, for these 150, opening hours (Overture leads have none: the hours factor is the neutral 0.6 for all of them). The lead's own
heat score breaks ties.

## What to expect (no real call results yet)

The repo has no logged call outcomes (the caller's log lives on the phone / PC). Two planning views:

| View (source) | Conversations | Demos / sample views | Sales | First-year $ | $ an hour (12.5 h of dialing, 5 min a dial) |
|---|---|---|---|---|---|
| Planning funnel (agency/pricing.json: 4 dials a talk, 2 talks a demo view, 4 views a sale) | ~37 | ~19 | **~4.7** | ~$13,000 (setups ~$7,000) | ~$560 setup $ / hour |
| Portal daily targets (callrules.json: 40 dials -> 8 talks -> 2 demos, 1 close a WEEK of ~200 dials) | ~30 | ~7.5 | **~0.75** | ~$2,100 (setup ~$1,125) | ~$90 setup $ / hour (~$167 first-year) |

Honest middle: plan on **1-2 sales** from 150 dials (about **$1,500-$3,000 of setups**, $79-$299 a month each after), and replace
these guesses with the portal's own numbers after the first week (`python -m agency.portal scorecard`). A hired caller is paid
$300 a cleared sale + $40 a booked call that shows (agency/pricebook.json).
