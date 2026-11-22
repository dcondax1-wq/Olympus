# AGENCY: the website machine

Owner, 2026-11-14: "I want a website building machine." A second income: find local businesses that need a website, build
each one a demo site before you call, pitch it, keep the pipeline on your phone. Free tools only. **Nothing here sends an
email, places a call or texts anyone: it prepares the words, you dial and press send.**

| What | Result (demo run on Fort Collins, CO, 2026-11-14) |
|---|---|
| Businesses found (OpenStreetMap, 26 trades, 8 km) | 609 places, 501 kept (101 chains and 6 duplicates left out) |
| Today's call list | 20 leads: 17 with no website, 3 with a broken one (a parked page, an error 500, not built for phones) |
| Demo sites built | 3: Roy's Quick Lube (garage look), Highroad Roofing (pro look), Rocky Mountain Dental Care (clinic look); self-check 100/100/100/100, about 37 KB a page |
| Pitch kits | a one-page pitch, an email (CAN-SPAM lines in) and a 70-word, 28-second phone opener for each |
| Agency page (OLYMPUS) | the 20 leads, Call today, the pipeline with dollars, the plan to $5,000 a month |
| Prices | Starter site $1,500 + $79 a month (or $149 a month for 12 months, nothing upfront), Call engine $500 + $299 a month (3-month minimum), 3D Signature from $2,500 + $79 a month (one price book: agency/pricebook.json) |
| The math | 4 new clients a month passes $5,000 a month in month 8 (about 6 calls a working day) |

Pictures (`docs/shots/agency/`): `templates-8-looks-390.png` (the 8 looks on real Fort Collins businesses), `site-<name>-390.png` /
`-390-full.png` / `-desktop.png` (the 3 demo sites), `crm-390.png`, `crm-390-lead.png`, `crm-desktop.png` (the Agency page),
`pitch-onepager-highroad-roofing.png` (a one-page pitch). Screenshots come from Chromium on Linux, so the fonts are the fallbacks:
on an iPhone the serif headings use Iowan Old Style / Didot and the garage look DIN Condensed.

## Your 3 steps
1. Double-click **`RUN_AGENCY.bat`**. The first time Notepad opens your settings file: put in your agency name, your name, phone,
   email, postal address and your city, save, and double-click it again. Each run makes today's leads, 3 demo sites and their pitches.
2. Drag each `site` folder it shows onto **app.netlify.com/drop** (free account), press **Publish** (new Netlify projects start
   private), and rename it to the name in its pitch (`<business>-demo.netlify.app`).
3. Open the **Agency** page on your phone and call the people under "Call today" with the opener on the card.

## The daily routine (about 1 hour)
| When | What |
|---|---|
| Morning, 5 min, PC | `RUN_AGENCY.bat`: new leads, 3 demo sites, their pitches. Drop the 3 folders on Netlify. |
| 10:00-12:00 or 14:00-16:00, 30-45 min, phone | Agency page > Call today. Before each call search the name on Google (10 seconds: the map data can miss a website). Dial, read the opener, ask to send the link. |
| After each call, 10 s | Tap the stage: Contacted, Call back (pick the day), Won, Lost, or Do not contact. Notes go on the card. |
| They said "send it" | Card > The email > Copy (or Open in Mail once your settings are real), put their address in, press send. |
| They said yes | Mark Won with the price. Tell Claude "Agency: `<business>` said yes, domain `<their domain>`": it puts their real services and words in the site's `site.json` and builds the live folder (`build_site --final`, no preview bar, open to Google, the form switched on). Drop the `-live` folder on Netlify and connect their domain. |
| Someone says stop | Mark "Do not contact" at once. On the PC, put their number (or name) on a line of `agency/suppress.txt`, or save your page export as `agency/crm_export.json`: the machine never lists them again. |
| Sunday, 5 min | Agency page > Your notes > Export (keep the file, and save it as `agency/crm_export.json` on the PC) and look at the plan: calls this week, clients this month. |

## Prices (owner-editable: `packages` in agency/config.json, the ONE source since 2026-11-15)
The pitch, storefront, Agency page, money math and the billing kit's proposal / agreement / invoice all read these prices through `agency.config.prices()` (`agency/billing/packages.json` holds only the wording). The whole day in one double-click: `AGENCY_DAY.bat` (`docs/BUSINESS.md`).

| Package | To start | Each month | What they get |
|---|---|---|---|
| Starter site | $1,500 | $79 | up to 5 pages, their logo, photos and words, their own domain, tap-to-call and a contact form, Google Business Profile linked, the care plan (12-month term, small edits up to 30 minutes a month) |
| Call engine (config id `growth`) | $500 | $299 | a one-page call site or a tune-up, Google Business Profile kept fresh, review requests, every review answered, a monthly proof report (3-month minimum) |
| 3D Signature (config id `pro`) | from $2,500 | $79 | Starter + a 3D tour or 3D product pages, AR on phones, a still fallback |

Why these numbers: a freelancer charges $1,500-$5,000 for a small-business site and an agency $5,000-$15,000, while do-it-yourself
builders cost $17-$39 a month. A ready-made one-page site sold the same day sits under the freelancer range on purpose (an easy yes),
and the monthly plan is in the usual $39-$200 care-plan range. Terms default to "month to month: cancel any time" (`agency.terms`).

### The math to $5,000 a month (`python -m agency.money`)
Average sale $799 to start + $66 a month (mix: 60% Starter, 30% Growth, 10% Pro); care plans lose 3% of clients a month.

| New clients a month | Setup $ a month | Care $ after 6 months | Total in month 6 | Total in month 12 | Months to $5,000 |
|---|---|---|---|---|---|
| 2 | $1,598 | $735 | $2,333 | $2,945 | 49 |
| 3 | $2,397 | $1,102 | $3,499 | $4,418 | 17 |
| **4** | **$3,196** | **$1,470** | **$4,666** | **$5,890** | **8** |
| 5 | $3,995 | $1,837 | $5,832 | $7,363 | 4 |
| 6 | $4,794 | $2,205 | $6,999 | $8,835 | 1 |

The pace: 4 clients a month = 16 owners who look at their demo = 32 real conversations = about 128 calls a month, **6 a working day,
about 6 hours a week**. Most of the $5,000 is new setup fees, so it needs selling every month; care plans alone would need 76 clients.
The call rates (1 in 4 calls reaches the owner, 1 in 2 conversations agrees to look, 1 in 4 who look buy) are ESTIMATES: replace them
in `agency/pricing.json` after two weeks of real calls. Costs: card fees about 2.9% + 30 cents a payment, a domain about $15 a year per
client (bill it to them), Netlify Personal $9 a month once you pass about 20 deploys a month, and taxes (set some aside).

### The research (read 2026-11-14; most price pages are vendor blogs, so they are ranges, not facts)
| What | Finding | Source |
|---|---|---|
| US small businesses with no website | 17% (83% have one); cost is the main reason for only 16% of them | Clutch survey, press release 2025-08-21 |
| Freelancer / agency price | $1,500-$5,000 / $5,000-$15,000 | Seahawk Media, TDL Web Solutions (2025), Levitate (2026) |
| DIY builders | Wix $17-$39 a month; Squarespace from about $19 after its July 2026 increase | Website Builder Expert (Feb 2026), Hostadvice (2026) |
| Care plans | basic $39-$99, typical $50-$200 a month | Fatlab, Seahawk Media, WPX guides (2025-2026) |
| Cold email | 0.45% replies per email sent (7.5 million emails) up to 4-4.5% in friendlier samples | Belkins (2025), Hunter State of Cold Email 2025 |
| Cold calls (B2B) | 6-10% of dials reach someone; 2.3-2.7% of conversations book a meeting | Belkins; Cognism Cold Calling Report 2026 |
| Demo-first selling | "3-5x" and "20-50% close on demos shown" are vendor claims and anecdotes, no audited study: measure your own | Kolonell (2026), dev.to build-then-pitch post |
| Google's free business.site sites | all shut down 2024-03-01 (redirects ended 2024-06-10): those owners lost their site | Search Engine Land (2024) |
| Phones in US web traffic | about 42% of page views (Aug 2026) | Statcounter |
| Netlify Free | 300 credits a month; a deploy costs 15 (about 20 a month); forms free and unlimited; at zero every site pauses | netlify.com/pricing, docs.netlify.com |
| Cloudflare Pages Free | drag and drop a zip or folder; 500 builds a month | developers.cloudflare.com |
Every line with its link is in `agency/pricing.json`.
Re-checked 2026-11-17: Starter sits at the bottom of the one-page freelancer range ($500-$1,500), the price book (2026-11-21) moved Starter to $1,500 + $79, inside the 5-page range ($1,500-$5,000), a Google profile fix sells for $50-$200 on Fiverr and $300-$800 locally ($149 in person). The first $1,000 plan: Business -> More Work, `research/writeups/more-work-2026-11-17.md`.

## Honest limits
- **OpenStreetMap is volunteer-made and thin on trades.** Fort Collins: 51% of places have a phone, 63% a website, 49% hours, 76% a street
  address; only 1 plumber, 1 electrician and 2 HVAC companies are mapped (contractors rarely have a storefront on the map). "No website on
  OSM" can mean OSM does not know it: always Google the name before you call.
- **What a paid source adds:** Google Places (Nearby Search Pro: 5,000 free calls a month, then $32 per 1,000) has far more businesses
  (contractors who work from a van), star ratings and review counts, open / closed status and photos. Its terms limit how long you may store
  the data and it needs a billing account, so it is not built in.
- **The house rules of the free servers** (followed in the code): Overpass, one query at a time, cached 7 days, a clear app name, a 30 s pause
  when busy; the main server asks commercial users to self-host, so North America uses the free North America server from the same OSM wiki
  list. Nominatim (the city search) is used once per city for the centre point only, never to list businesses (its policy forbids that), at
  most 1 request a second, cached for good. Business data (c) OpenStreetMap contributors (ODbL): the attribution is on every file and page.
- **When the free map server is busy** (the wiki says it often is): the machine waits and retries, reuses its last answer (7 days), and can read
  an OpenStreetMap extract file instead (`--extract FortCollins.osm.gz`, from download.bbbike.org, about 30 US cities, refreshed weekly). Tested:
  the Fort Collins extract gave 497 of the 501 businesses Overpass gave (the 4 others were mapped after the extract was made), in 10 seconds.
- **The site check is polite and careful:** it reads robots.txt, opens each home page once (https first), and calls a site "dead" only when
  that is certain. From this cloud sandbox plain-http sites could not be opened at all, so those leads say "could not check"; on your PC
  they are checked normally.
- **Demos are previews:** a bar says "Preview, not the official site", they are not indexed by Google, the form does not post, reviews are
  marked SAMPLE and no claim is invented (no "licensed", "24/7" or "free estimates"). Netlify's new free plan allows about 20 deploys a
  month across all your sites; for more use Cloudflare Pages (drag and drop the zip) or Netlify Personal ($9).
- **The law, in short (not legal advice):** sales emails, business to business included, need a true sender and subject, an "it is an offer"
  line, your postal address and an opt-out you honour within 10 business days (CAN-SPAM; up to $53,088 per bad email). The machine marks
  every email NOT READY TO SEND until your real details are in the settings file. Calls: dial by hand, business hours, never a robot or a
  recording, no texts to people who did not ask, and put "Do not contact" on anyone who says stop.
- **The conversion rates are guesses until you measure them.** The first two weeks are the real test: 60 calls, count the yeses.

## Where everything is (for future sessions)
| Part | File | Run / test |
|---|---|---|
| Settings (ONE file) | `agency/config.example.json` -> `agency/config.json` (gitignored: an edited tracked file would block the bot's auto-update) | `agency/config.py` |
| Lead finder | `agency/leads.py`, `osm.py` (Overpass + Nominatim, or an extract file), `audit.py` (site check), `categories.py`, `hours.py`, `agency/suppress.txt` (do not contact) | `python -m agency.leads --city "Fort Collins, CO"` (`--extract FILE.osm.gz`) |
| Site generator | `agency/build_site.py`, `agency/templates/` (8 looks: studio, bloom, pro, table, clinic, garage, fresh, pulse; `trades.json` = the words) | `python -m agency.build_site --leads FILE --id ID` (`--all-templates`, `--pages 3`, `--final --url`) |
| Self-check | `agency/sitecheck.py` | `python -m agency.sitecheck <site folder>` |
| Pitch kit (one-pager, email, phone opener, `short.txt` = walk-in / DM / follow-up) | `agency/pitch.py`, `agency/templates/pitch/` | `python -m agency.pitch --leads FILE --id ID` |
| Money | `agency/pricing.json` (research + funnel guesses), `agency/money.py` | `python -m agency.money` |
| The day's batch | `agency/run.py`, `RUN_AGENCY.bat` | `python -m agency.run` |
| Agency page | `tools/web_public/agency/` (reads `my_leads.json` = your batch, gitignored, then the committed sample `leads.json`, then `fixture.json` = DEMO; notes in `localStorage['agency.crm.v1']`); data by `agency/publish.py` (`--fixture` rebuilds the DEMO) | wiring: docs/NEW_APPS_WIRING.md "Wiring AGENCY" |
| Demo batch | `agency/demo/fort-collins/` (leads, all_leads.csv, 3 sites + zips + pitch kits, run.json) | screenshots `docs/shots/agency/` |
| Tests | `tests/test_agency.py` (lead scoring, every template's HTML, no hotlinks, the self-check, pitch text, the money math, the CRM page) | `python -X utf8 -m tests.test_agency` (`--fast` = no browser) |
