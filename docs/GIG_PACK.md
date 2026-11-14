# Gig pack: 8 productized gigs (built 2026-11-14, generated from `money_machines/gig_pack.json`)

Copy-paste ready for Fiverr (and Upwork Project Catalog / Contra). **Prices:** Launch prices for a new seller (no reviews yet), set inside the ranges competing gigs showed on 2026-11-14 (docs/MONEY_MACHINES.md, Sources). Raise each tier about 30% after 5 five-star reviews. Fiverr keeps 20% of every order; the buyer also pays Fiverr a service fee on top.

Regenerate after editing the JSON: `python -m money_machines.gig_pack --md`. Check the tools: `python -m money_machines.gig_pack --check`.

| Gig | Packages ($) | Your time (min) | Start here |
|---|---|---|---|
| build a fast mobile website for your local business | 120 / 260 / 480 | 35 / 55 / 90 | yes |
| design a simple modern logo and brand kit for your small business | 25 / 55 / 95 | 20 / 35 / 50 | yes |
| set up and optimize your Google Business Profile with a full checklist | 35 / 75 / 140 | 25 / 50 / 75 | yes |
| set up an honest Google review system with QR cards and message scripts | 30 / 60 / 110 | 15 / 30 / 50 | yes |
| audit your website speed and SEO and send a clear fix report | 35 / 70 / 140 | 25 / 45 / 90 | later |
| build a fast landing page for your offer, event or local service | 70 / 140 / 250 | 25 / 45 / 75 | later |
| create a month of social media posts with images for your local business | 45 / 85 / 140 | 30 / 45 / 70 | later |
| install a free live chat widget on your website and set it up | 25 / 55 / 95 | 15 / 35 / 55 | later |

## What stays human (always)

- The account: one account per person, in the owner's real name, ID and selfie verified by him. Never shared, rented, sold or run for someone else.
- Every message to a client: AI may draft it, the owner reads, edits and sends it himself. No auto-replies beyond the platform's own saved replies.
- Saying yes to an order, the price and any custom offer.
- The final review of every deliverable on his own phone before he presses Deliver (names, phone, address, prices, spelling, no claims the client did not give).
- Honesty about AI: answer truthfully when asked, follow the client's no-AI request, and never present raw AI output as finished work.
- Payments only through the platform; no outside payment before an order exists.

## Never build or buy these (they break the platforms' rules)

- Auto-bidding or auto-proposal bots (Upwork bans unapproved automation and proposal spam even with an API key).
- Scrapers of job lists, profiles or messages (Upwork Terms 3.5, Fiverr Terms 8.8).
- Mass-message or auto-DM bots (Fiverr Community Standards).
- Fake reviews, review swaps, paid or incentivised reviews, review gating (Fiverr, Google and the FTC rule of 2024-10-21).
- A second account, a borrowed identity, a VPN to hide location, or 'agency' accounts run by bots.
- Anything that promises rankings, sales or other results nobody controls.

## AI line (paste into every gig and proposal)

> I use AI-assisted tools for first drafts and code; I check and finish every deliverable myself before you see it. If you don't want any AI used on your project, tell me before you order and I'll work without it.

## Revision policy (paste into every gig)

> A revision is a change inside the original brief (words, colours, photos, order of sections). New pages, new features or a new direction are a new order (custom offer). Send all changes for one round in one message. I answer revision requests within 2 business days. Fiverr marks a delivered order complete if the buyer does nothing for 3 days (check the Help Center for the current rule).

## 1. I will build a fast mobile website for your local business

- **Category:** Programming & Tech > Website Development (business website)
- **Search tags (5):** business website, small business, local business, mobile website, website design
- **Start here:** yes

**Description** (paste as is):

```
Your customers search on their phone. If your business has no website, or one that is slow and hard to use on a phone, they call the next company on Google.

I build fast, clean websites for local businesses: plumbers, salons, cafes, dentists, landscapers and more.

Every site includes:
- A design that works on phones first
- Tap-to-call button, opening hours and a map
- A contact form that sends to your email
- Your services, area and photos
- Google basics: page titles, description, fast loading, padlock (https)

You own everything: the files and the hosting account (free plan on your own Netlify account). Your domain stays yours.

How it works: order, answer the short questions, get a preview in a few days, ask for changes, go live.

Not a fit: online shops with many products, or sites that must be WordPress.

I use AI-assisted tools for first drafts and code; I check and finish every page myself.
```

| Package | Price | Days | Revisions | Includes | Your time |
|---|---|---|---|---|---|
| One page | $120 | 3 | 1 | 1 page: services, hours, map, tap-to-call, contact form; Mobile-first, fast, https; Page title and Google description; Set-up on your own free hosting account | 35 min |
| Up to 4 pages | $260 | 5 | 2 | Everything in One page; Up to 4 pages (a page per main service); Photo gallery and a quote or booking form; Link to your Google profile and your review link | 55 min |
| Up to 7 pages + words | $480 | 7 | 3 | Everything in 4 pages; Up to 7 pages, the words written for you; FAQ page, local business details for Google (schema), sitemap; 30 days of small edits after launch | 90 min |

**Questions to ask the buyer (requirements):**

- Business name exactly as customers see it
- Trade and the towns you serve
- Phone, email for the form, address (or service area only)
- Opening hours
- Your services and starting prices (if you show them)
- Your logo and photos (or say if free stock photos are fine)
- Do you own a domain name? Which one?

**FAQ:**

- **Do I pay for hosting?** No monthly fee from me. The site goes on a free hosting plan in your own account. A domain name costs about $10-15 a year, paid by you to the domain company, so it is always yours.
- **Who owns the website?** You do: the files, the hosting account and the domain. I hand everything over at delivery.
- **Do you use AI?** Yes, for first drafts and code. I check and finish every page by hand. If you don't want AI used, tell me before ordering.
- **Can you put me first on Google?** Nobody can promise that. I set up the basics properly (speed, phone layout, titles, your Google profile link) so Google can understand your business.
- **Can you build it in WordPress?** No. I build fast static sites that need no plugins or updates. If you need WordPress, this gig is not the right fit.
- **Can I make changes later?** Yes. Small edits are included for 30 days in the top package; after that I send a custom offer for each change.

**The tool:** Agency site generator (team B1): a lead file in, a finished phone-first site folder + zip out (no web fonts, no trackers). Module `agency.build_site` (B1 (agency/build_site.py)).

    python -m money_machines.gig_pack order --gig local-website --name "<business>" --category <trade> --city "<city, ST>" --phone "<phone>" --email <email>
    python -m agency.build_site --leads money_machines/out/orders/<slug>/lead.json --id <slug> --pages 3   (leave out --pages for the one-page package)
    edit the site.json it writes (their words, services, hours), then: python -m agency.build_site --site <out>/<slug>/site.json --final
    python -m money_machines.brand_kit --name "<business>" --industry <trade> --out money_machines/out/orders/<slug>/brand   (only if they have no logo)

**Delivery checklist:**

1. Read the answers; ask one question if anything is missing (5 min)
2. Make the order file and build the site with the tool (5 min)
3. Swap in their photos, logo and words; delete every placeholder (15 min)
4. Phone check at 375 px: tap-to-call dials the right number, the form sends a test email, the map shows the right place (5 min)
5. Read every word once: name, phone, address, hours, prices, spelling. Remove any claim they did not give you (licensed, insured, years, 'best') (5 min)
6. Zip it, upload a preview, write the delivery note with the 3 steps to go live (5 min)

**Stays human:** Choosing photos the client has the right to use; The final read of every claim on the page; Explaining how to go live, in your own words.

**Never:** Copying another company's site, logo or photos; Fake reviews or testimonials on the page; Claims the client did not give (licences, awards, years in business).

## 2. I will design a simple modern logo and brand kit for your small business

- **Category:** Graphics & Design > Logo Design (minimalist)
- **Search tags (5):** logo design, brand kit, minimalist logo, small business logo, brand identity
- **Start here:** yes

**Description** (paste as is):

```
A clean, simple logo that looks good on a sign, a van, a website and an Instagram profile picture.

You get 3 concepts to choose from. Each one is built from original shapes and clear letters, in colours that pass readability checks (good contrast on screens and print).

The brand kit includes:
- Your logo in 4 layouts (wide, stacked, symbol only, name only)
- Dark and light versions for any background
- Colour palette with hex and RGB codes
- Free font names for your website
- Favicon, profile picture and banner sizes
- A one-page brand guide

Files: SVG (sharp at any size) and PNG.

Good for: trades, salons, cafes, clinics, shops and new businesses that need a professional look fast.

Not a fit: hand-drawn illustrations, mascots or complex artwork.

The logos are drawn by code from simple shapes, not by an image AI. I check every concept myself.
```

| Package | Price | Days | Revisions | Includes | Your time |
|---|---|---|---|---|---|
| 3 concepts | $25 | 2 | 1 | 3 logo concepts on one board; Your chosen logo as SVG and PNG; Colour codes | 20 min |
| Logo + brand kit | $55 | 3 | 2 | Everything in 3 concepts; 4 layouts + dark and light versions; Favicon, profile picture, banner; One-page brand guide (colours, fonts, rules) | 35 min |
| Full kit + print | $95 | 4 | 3 | Everything in Logo + brand kit; Business card front and back (print size); 2 extra colour versions; Source SVG files for every piece | 50 min |

**Questions to ask the buyer (requirements):**

- Business name exactly as it should read
- Tagline (optional)
- Your trade
- Colours you like or must use (a hex code if you have one)
- Logos you like (for the feel, not to copy)
- For business cards: name, phone, email, website

**FAQ:**

- **Do I own the logo?** Yes. When the order is complete you own the logo and can use it anywhere.
- **Is this made with AI?** The logos are drawn by code from simple original shapes, not by an image AI. I choose and check every concept.
- **Can you trademark it for me?** No. I don't do legal searches. Search your state's business register and the USPTO trademark search before you print.
- **Which files will I get?** SVG files (sharp at any size, for printers and sign makers) and PNG files for the web and social media.
- **Can you copy a logo I like?** No, but send it: I use it to understand the style you like and make something original.

**The tool:** Brand kit generator (this folder). Module `money_machines.brand_kit` (built here (money_machines/brand_kit.py)).

    python -m money_machines.brand_kit --name "<business>" --tagline "<tagline>" --industry <trade> --out money_machines/out/orders/<slug>/brand --png
    Send concepts.svg (as PNG) and ask the client to pick 1, 2 or 3
    python -m money_machines.brand_kit --name "<business>" --industry <trade> --concept <n> [--primary #hex] --phone ... --email ... --out .../final --png

**Delivery checklist:**

1. Run the tool with their name and trade (2 min)
2. Look at the 3 concepts on your phone; re-run with --palette/--mark if one looks off (8 min)
3. Send the concepts board; wait for their pick (0 min of your time)
4. Run the final kit with their choice and contact details (3 min)
5. Open brand_guide.html: spelling of the name, colours, business card details (5 min)
6. Zip the folder and deliver with one line on which file to use where (5 min)

**Stays human:** Judging that a concept is not too close to a famous logo; Spelling and the client's contact details.

**Never:** Copying or tracing another logo; Promising a trademark; Using an image AI and calling it hand-made.

## 3. I will set up and optimize your Google Business Profile with a full checklist

- **Category:** Digital Marketing > Local SEO
- **Search tags (5):** google business, local seo, google maps, business profile, gmb optimization
- **Start here:** yes

**Description** (paste as is):

```
When people search 'plumber near me' or 'best cafe in town', Google shows the map first. Your Google Business Profile decides if they see you, and whether they call.

I check every part of your profile and fix what holds it back:
- The right main and extra categories
- Services, service area and hours (holiday hours too)
- A clear description in plain words
- Photos: what to add and in what order
- Your review link, ready to share
- Posts: what to post each week

You get a scored checklist showing what was wrong, what I fixed and what is left for you.

All work follows Google's guidelines: your real business name (no keyword stuffing), your real address or service area, and honest reviews only. Breaking those rules can get a profile suspended, so I never do it.

No one can guarantee a ranking. I set up the profile the way Google asks so it can show you to the right people.

I use AI-assisted tools for first drafts; I check and finish everything myself.
```

| Package | Price | Days | Revisions | Includes | Your time |
|---|---|---|---|---|---|
| Audit + checklist | $35 | 2 | 1 | Full review of your profile; Scored checklist with every fix in plain words; Your review link | 25 min |
| Done for you | $75 | 3 | 2 | Everything in Audit; I make the fixes (you add me as a manager); Description, services, categories, hours, attributes; 4 ready-to-post Google updates | 50 min |
| Done + review kit | $140 | 5 | 3 | Everything in Done for you; Printable review QR card; 12 weeks of post ideas; List of free directories to claim | 75 min |

**Questions to ask the buyer (requirements):**

- Link to your Google Business Profile (or the business name and town)
- For Done for you: add me as a Manager (not Owner) in Business Profile settings > Managers
- Your services and the area you serve
- Your real opening hours, including holidays
- Photos you own (outside, inside, team, work)

**FAQ:**

- **Will this put me in the top 3 on Google Maps?** No one can promise that. Distance, reviews and competition matter. I make your profile complete and correct, which is what Google asks for.
- **Do you need my password?** No. You add me as a Manager in your profile settings and remove me when we are done.
- **Can you add keywords to my business name?** No. Google wants your real-world name; extra keywords can get a profile suspended.
- **Can you get me reviews?** I set up an easy way to ask every customer. I never write, buy or swap reviews.
- **I don't have a profile yet. Can you make one?** Yes, in Done for you. Google sends the verification to you (postcard, call or video), so you finish that step.

**The tool:** Google Business Profile checklist (this folder) + the review kit from team B4. Module `money_machines.gig_pack` (built here (gig_pack.py checklist)).

    python -m money_machines.gig_pack checklist --gig gbp-setup --business "<business>" --out money_machines/out/orders/<slug>
    Work through the checklist in the profile (Manager access); tick each line in the file
    Done + review kit: the review booster (python agency/upsells/make_review.py ..., team B4)

**Delivery checklist:**

1. Make the checklist file (1 min)
2. Open their profile as Manager and score each line (15 min)
3. Make the fixes for Done for you (20 min)
4. Write 4 posts and the review link (10 min)
5. Re-read the name, phone, address and hours against their website (3 min)
6. Deliver the checklist with what was fixed and what is left for them (5 min)

**Stays human:** Every change inside the client's Google account; Choosing the categories that are true for the business.

**Never:** Keyword-stuffed names, fake addresses or virtual offices; Writing, buying or swapping reviews; Promising rankings.

## 4. I will set up an honest Google review system with QR cards and message scripts

- **Category:** Digital Marketing > Local SEO (reviews)
- **Search tags (5):** google reviews, review qr code, review cards, reputation, local business
- **Start here:** yes

**Description** (paste as is):

```
Most happy customers never leave a review because nobody asked at the right moment, or the link was hard to find.

I set up a simple, honest system that makes asking easy:
- Your direct Google review link (one tap, no searching)
- A print-ready QR card for the counter, receipts or the van
- Short email and text messages to send after each job
- Replies you can copy for good and bad reviews

It follows Google's rules and the FTC's 2024 rule on reviews:
- Ask every customer, not only the happy ones
- No discounts or gifts in exchange for reviews
- No fake, bought or swapped reviews, ever

That keeps your profile safe and your reviews real.

Good for: trades, salons, restaurants, clinics, shops.

I use AI-assisted tools for first drafts; I check and finish everything myself.
```

| Package | Price | Days | Revisions | Includes | Your time |
|---|---|---|---|---|---|
| Link + QR card | $30 | 2 | 1 | Your direct review link; Print-ready QR card in your colours (SVG + PNG) | 15 min |
| Card + scripts | $60 | 3 | 2 | Everything in Link + QR; Email and text request messages; Counter sign; 10 reply templates for good and bad reviews | 30 min |
| Full system | $110 | 5 | 3 | Everything in Card + scripts; A 'Leave us a review' page for your website; A 30-second script for your staff; A check-in after 30 days | 50 min |

**Questions to ask the buyer (requirements):**

- Link to your Google Business Profile
- Your logo and colours (or say 'use simple colours')
- How you usually reach customers after a job (email, text, in person)
- For the website page: access to your site or your web person's email

**FAQ:**

- **Can I offer a discount for a review?** No. Google does not allow incentives for reviews, and the FTC's 2024 rule bans rewards tied to a positive review. Just ask, every time.
- **Can it send only happy customers to Google?** No. Filtering out unhappy customers (review gating) breaks Google's rules. The system asks everyone; reply to every review, good or bad.
- **Will you write reviews for me?** Never. Fake reviews can get your profile restricted and break the law.
- **Do you send the messages for me?** No. You or your staff send them; I give you the words and the timing.

**The tool:** Review booster (team B4): review page, vector QR, print-ready cards, request messages; Google's and the FTC's rules built in. Script `agency/upsells/make_review.py` (B4 (agency/upsells/make_review.py)).

    python -m money_machines.gig_pack order --gig review-booster --name "<business>" --category <trade> --city "<city, ST>" --review-url <their Google review link>
    python agency/upsells/make_review.py money_machines/out/orders/<slug>/client.json --out money_machines/out/orders/<slug>/reviews
    scan the printed QR with your own phone before you deliver

**Delivery checklist:**

1. Get the review link from their profile (Ask for reviews > Share link) and open it once to test (3 min)
2. Make the QR card and scan it with your own phone (5 min)
3. Fill the message and reply templates with their name and trade (10 min)
4. Check that nothing offers a reward or filters unhappy customers (2 min)
5. Deliver with a one-line 'how to use it' (5 min)

**Stays human:** Scanning the printed QR yourself before delivery; Telling the client the rules (no incentives, ask everyone).

**Never:** Fake, bought or swapped reviews; Review gating (happy customers to Google, unhappy ones elsewhere); Rewards for reviews.

## 5. I will audit your website speed and SEO and send a clear fix report

- **Category:** Programming & Tech > Website Maintenance > Speed Optimization
- **Search tags (5):** website audit, page speed, seo audit, core web vitals, website speed
- **Start here:** later (Fiverr limits new sellers to a few gigs)

**Description** (paste as is):

```
Is your website slow on phones, hard to use, or missing from Google? I check it and tell you exactly what to fix, in plain words, ranked by how much each fix matters.

The report covers:
- Speed on a phone (Google PageSpeed Insights, mobile)
- Phone layout, tap-to-call and the contact form
- Padlock (https) and broken pages
- Page titles and Google descriptions
- Your Google Business Profile link and reviews
- The 10 fixes that matter most, easiest first

Every number shows the date it was measured, so you can re-test after the fixes.

In the top package I also make the fixes on simple HTML sites, or give you step-by-step instructions for WordPress, Wix or Squarespace.

No one can promise a ranking or a perfect score. I report what I measured and what will help.

I use AI-assisted tools to draft the report; I run the checks and write the advice myself.
```

| Package | Price | Days | Revisions | Includes | Your time |
|---|---|---|---|---|---|
| Home page report | $35 | 2 | 1 | Speed + on-page check of your home page; Top 10 fixes in plain words; HTML report you can forward | 25 min |
| 5-page report | $70 | 3 | 2 | Everything in Home page; Up to 5 pages; Phone layout and contact form test; Fix plan by priority | 45 min |
| Report + fixes | $140 | 5 | 2 | Everything in 5-page report; I apply the fixes on simple HTML sites, or write step-by-step guides for WordPress, Wix or Squarespace; Re-test with before and after | 90 min |

**Questions to ask the buyer (requirements):**

- Your website address
- Which pages matter most (home, services, contact...)
- Your platform if you know it (WordPress, Wix, Squarespace, custom)
- For Report + fixes: access for the fixes (a site user, or your web person's email)

**FAQ:**

- **Will my score be 100 after this?** Maybe not, and it does not need to be. I focus on what makes the site faster and easier for real customers on phones.
- **Do you need my password?** Not for the reports. For fixes, add me as a user and remove me after.
- **Do you do WordPress plugins?** I recommend and explain what to change. On simple HTML sites I make the fixes myself.
- **Will this get me to the top of Google?** No one can promise rankings. A fast, clear site with correct titles helps Google and customers understand you.

**The tool:** Website grader (team B3): one polite visit, a one-page report (https, phone layout, tap-to-call, button, Google profile link, speed, weight, title, schema) + PageSpeed Insights by hand. Script `agency/storefront/grade.py` (B3 (agency/storefront/grade.py)).

    python agency/storefront/grade.py <their site> --name "<business>" --city <city> --pdf
    open pagespeed.web.dev with the site, Mobile tab: add the 4 scores and the top 3 'opportunities' with today's date to your delivery note
    put the fixes in order for this business (easiest and biggest first)

**Delivery checklist:**

1. Run the report tool (3 min)
2. Run PageSpeed Insights on mobile and paste the numbers with today's date (5 min)
3. Open the site on your phone: tap-to-call, the form, the menu (5 min)
4. Put the 10 fixes in order, easiest and biggest first (7 min)
5. Deliver the HTML report with a 3-line summary (5 min)

**Stays human:** The order of the fixes and the plain-words advice; Checking the site on a real phone.

**Never:** Crawling a site that blocks robots; Promising scores or rankings; Buying links or 'traffic'.

## 6. I will build a fast landing page for your offer, event or local service

- **Category:** Programming & Tech > Website Development > Landing Pages
- **Search tags (5):** landing page, sales page, one page website, lead generation, event page
- **Start here:** later (Fiverr limits new sellers to a few gigs)

**Description** (paste as is):

```
One page, one goal: calls, bookings, sign-ups or quote requests.

I build a fast landing page that works on phones and makes the next step obvious:
- A clear headline and one main button
- Your offer and why it is worth it
- Real reviews or photos of your work (only real ones)
- Questions customers ask, answered
- A form that sends to your email, or tap-to-call

It loads fast, has the padlock (https), and goes on a free hosting plan in your own account. Your domain stays yours.

Good for: a seasonal offer, an event, a new service, an ad campaign, or a business that needs one good page now.

Not a fit: online shops or pages that must be built inside WordPress or Shopify.

I use AI-assisted tools for first drafts and code; I check and finish every page myself.
```

| Package | Price | Days | Revisions | Includes | Your time |
|---|---|---|---|---|---|
| Simple page | $70 | 2 | 1 | One section page from your words; Button to call or a form; Mobile-first, https, set up on your free hosting | 25 min |
| Full landing page | $140 | 3 | 2 | Headline, benefits, proof, FAQ, form; Tap-to-call and map if local; Share picture and Google description | 45 min |
| Page + words | $250 | 5 | 3 | Everything in Full landing page; The words written for you; 2 headline versions to test; Your analytics code added (you provide it) | 75 min |

**Questions to ask the buyer (requirements):**

- What the page is for (one goal)
- Your offer, price and deadline if any
- Business name, phone, email for the form
- Real reviews or photos you can use
- Colours and logo (or order the logo gig)
- Your domain, if you have one

**FAQ:**

- **Do I pay for hosting?** No. It goes on a free plan in your own account. A domain costs about $10-15 a year if you want your own address.
- **Can you write the words?** Yes, in Page + words. In the other packages you send the words and I shape them.
- **Can you add fake reviews to look busy?** No. Only real reviews from real customers, with their permission.
- **Do you use AI?** Yes, for first drafts and code. I check and finish every page myself.

**The tool:** Agency site generator (team B1), one page. Module `agency.build_site` (B1 (agency/build_site.py)).

    python -m money_machines.gig_pack order --gig landing-page --name "<business>" --category <trade> --city "<city, ST>" --phone "<phone>" --email <email>
    python -m agency.build_site --leads money_machines/out/orders/<slug>/lead.json --id <slug>
    edit site.json (headline, offer, FAQ, real reviews), then: python -m agency.build_site --site <out>/<slug>/site.json --final

**Delivery checklist:**

1. Read the goal; write the headline first (5 min)
2. Build with the tool (3 min)
3. Put in their words, offer, reviews and photos (12 min)
4. Phone check at 375 px: the button, the form test, the phone number (5 min)
5. Read every claim against what they gave you (3 min)
6. Deliver with the 3 steps to go live (5 min)

**Stays human:** The headline and the offer wording; Checking every review and claim is real.

**Never:** Fake reviews, fake countdowns or fake scarcity; Claims the client did not give.

## 7. I will create a month of social media posts with images for your local business

- **Category:** Digital Marketing > Social Media Marketing (content)
- **Search tags (5):** social media posts, instagram posts, content calendar, facebook posts, social media
- **Start here:** later (Fiverr limits new sellers to a few gigs)

**Description** (paste as is):

```
Posting every week is hard when you are running a business. I make a month of posts for you (12 or 20), ready to schedule.

Each post has:
- A designed image in your colours (square for the feed, plus a story version)
- A short caption in your voice, with a clear next step (call, book, visit)
- A few useful hashtags (no spam lists)
- The date to post it

The mix: tips your customers care about, your services, behind the scenes, offers, seasonal days, and reviews you already have (with permission).

In the top package I schedule the posts for you in your free Meta Business Suite (Facebook and Instagram).

No fake claims, no stock photos pretending to be your team, no bought followers.

I use AI-assisted tools for first drafts; every caption is read, edited and approved by me before you see it.
```

| Package | Price | Days | Revisions | Includes | Your time |
|---|---|---|---|---|---|
| 12 posts | $45 | 3 | 1 | 12 posts (3 a week) with designed images; Captions with a few hashtags; Posting calendar and schedule sheet | 30 min |
| 20 posts + stories | $85 | 4 | 2 | 20 posts with designed images; A story version of every post; Captions, calendar and schedule sheet | 45 min |
| 20 posts scheduled | $140 | 5 | 2 | Everything in 20 posts + stories; I schedule them in your Meta Business Suite (you give me access); An approval message so nothing posts without your OK | 70 min |

**Questions to ask the buyer (requirements):**

- Business name, trade, town
- Logo and colours
- Your services and any offers this month
- Photos you own (work, team, place)
- 3 things customers always ask you
- For scheduling: add me to your Meta Business Suite (Settings > People / Partners)

**FAQ:**

- **Which platforms?** Instagram and Facebook (the same posts fit both). Square or 4:5 images.
- **Do you use AI?** Yes, for first drafts. I edit every caption and design every image myself; nothing is posted without your OK.
- **Will this get me followers?** I can't promise numbers. Regular, useful posts give people a reason to follow and to call you.
- **Do you post for me?** In the top package I schedule them in your Meta Business Suite. You stay the owner of your accounts.

**The tool:** Social post machine (team B5): designed square + story images from code (no AI images), captions, schedule sheet, approval message. Script `agency/content/make_posts.py` (B5 (agency/content/make_posts.py)).

    python -m money_machines.gig_pack order --gig social-month --name "<business>" --category <trade> --city "<city, ST>" --phone ... --email ...
    python agency/content/make_posts.py money_machines/out/orders/<slug>/client.json --month next --posts 12   (20 for the bigger packages; --colors "#hex,#hex" for their brand)
    send client_message.txt for their OK, then schedule by hand in their Meta Business Suite > Planner (free) or hand over posts.csv

**Delivery checklist:**

1. Fill the client brief (name, trade, offers, colours) (5 min)
2. Run the social-post machine (5 min)
3. Read all captions: no claims they did not give, no prices you are not sure of, spelling (15 min)
4. Look at every image on your phone (5 min)
5. Deliver the images, captions sheet and calendar (5 min)

**Stays human:** Reading every caption before delivery; Using only photos the client owns.

**Never:** Bought followers or engagement; Fake reviews or testimonials in posts; Stock people presented as the client's team.

## 8. I will install a free live chat widget on your website and set it up

- **Category:** Programming & Tech > Website Development > Customization (chat)
- **Search tags (5):** live chat, chat widget, website chat, tawk to, customer support
- **Start here:** later (Fiverr limits new sellers to a few gigs)

**Description** (paste as is):

```
Some customers will never call, but they will type a quick question. A chat box on your website catches those leads.

I install a free chat widget on your site and set it up so it is useful from day one:
- The chat box in your colours, on every page
- A friendly greeting and your opening hours
- Saved answers to the questions you get most
- Alerts on your phone when someone writes
- An offline form that sends the message to your email

The chat account is yours (a free plan of a well-known chat service, or our own light widget in the top package). No monthly fee from me.

Works with most sites: HTML, WordPress, Wix, Squarespace, Shopify.

I never ask for your passwords: you create the chat account and invite me, or paste one line of code with my instructions.

I use AI-assisted tools for first drafts; I check and finish everything myself.
```

| Package | Price | Days | Revisions | Includes | Your time |
|---|---|---|---|---|---|
| Install | $25 | 1 | 1 | Free chat widget on your site (your account); Your colours and position; Phone app alerts set up | 15 min |
| Install + answers | $55 | 2 | 2 | Everything in Install; Greeting and opening hours; 10 saved answers from your FAQ; Offline messages to your email | 35 min |
| FAQ widget | $95 | 3 | 2 | Everything in Install + answers; Our light FAQ answer widget with your answers (no monthly fee); A lead form that emails you | 55 min |

**Questions to ask the buyer (requirements):**

- Your website address and platform
- The 10 questions customers ask most, with your answers
- Your opening hours
- The email and phone that should get alerts
- Site access, or a person who can paste one line of code

**FAQ:**

- **Is there a monthly fee?** Not from me. The chat services I use have free plans; their paid extras are optional and your choice.
- **Will a robot answer my customers?** Only with your own saved answers. Real conversations go to you on your phone.
- **Do you need my password?** No. You create the chat account and invite me, or paste one line of code I send you.
- **Does it slow my site down?** Slightly. I load it after the page so your site stays fast; the FAQ widget is very light.

**The tool:** Front-desk chat (team B4): one script tag, answers only from the client's facts; or a free chat service installed by hand. Script `agency/upsells/make_chat.py` (B4 (agency/upsells/make_chat.py)).

    Install / Install + answers: the client opens a free account at a chat service (for example tawk.to or crisp.chat) and invites you; paste its snippet before </body>
    FAQ widget: python -m money_machines.gig_pack order --gig chat-widget --name "<business>" --category <trade> --city "<city, ST>" --phone ... --email ...
    python agency/upsells/make_chat.py money_machines/out/orders/<slug>/client.json --out money_machines/out/orders/<slug>/chat   (fill the facts it lists under 'check with the client')

**Delivery checklist:**

1. Get the invite or the site access (2 min)
2. Paste the snippet, set colours and greeting (10 min)
3. Add the saved answers and hours (15 min)
4. Send a test chat from your phone; check the alert arrives (3 min)
5. Deliver with how to answer from the phone app (5 min)

**Stays human:** The answers in the widget (the client approves every one); The test chat from your own phone.

**Never:** Storing the client's passwords; A bot that pretends to be a person; Collecting data the client did not ask for.

## Upwork proposal templates

Write 2 sentences only for this client in every proposal (what they asked, one detail from their post). Never paste the same text twice. Send by hand. One proposal per job.

### local-website

```
Hi {name},

You need {their need in their words} for {their business}, and {one detail from their post}. That is exactly what I build: fast, phone-first websites for local businesses, live in days, on hosting you own.

For you I would do:
1. A home page with your services, hours, map and a tap-to-call button
2. {their extra: booking form / service pages / gallery}
3. The Google basics: titles, description, your Google profile and review link

Example: {link to a sample site}
Timeline: {days} days. Fixed price: ${price}, with {revisions} rounds of changes.

One question: {a real question about their post}?

{your first name}

I use AI-assisted tools for first drafts and code and finish every page myself. If you prefer no AI on your project, tell me and I will work without it.
```

### logo-brand-kit

```
Hi {name},

A clean logo for {their business} that works on {where they will use it: van, sign, Instagram}. I make simple, modern logos from original shapes, with a brand kit so everything matches.

You would get 3 concepts first, then the full kit for the one you pick: dark and light versions, colours with codes, favicon, profile picture and a one-page guide. SVG and PNG files.

Example: {link to a concepts board}
Timeline: {days} days. Fixed price: ${price}, with {revisions} rounds of changes.

Quick question: {colours or style they mentioned}?

{your first name}

The logos are drawn by code from simple shapes, not by an image AI; I choose and check every concept.
```

### gbp-setup

```
Hi {name},

Your Google Business Profile for {their business} {their problem: not showing on Maps / missing info / no reviews}. I set up profiles the way Google's guidelines ask: real name, right categories, services, hours, photos and posts.

Plan:
1. Audit every field and score it (you get the checklist)
2. Fix it with Manager access (no password needed)
3. Your review link and 4 ready posts

I don't promise rankings and I never touch reviews except to help you ask for them.

Timeline: {days} days. Fixed price: ${price}.

Is the profile already verified?

{your first name}

I use AI-assisted tools for drafts and do every change in your profile myself.
```

### review-booster

```
Hi {name},

You want more Google reviews for {their business}. The honest way works: ask every customer at the right moment with a one-tap link.

I set up your review link, a print-ready QR card in your colours, short email and text messages, and replies for good and bad reviews. It follows Google's rules and the FTC's 2024 review rule: no incentives, no filtering of unhappy customers, no fake reviews.

Timeline: {days} days. Fixed price: ${price}.

How do you usually contact customers after a job?

{your first name}

I use AI-assisted tools for first drafts and finish everything myself.
```

### speed-seo-report

```
Hi {name},

You said {their site} is {their problem: slow / not on Google / not getting calls}. I can check it today and send a report in plain words: speed on phones (PageSpeed Insights), phone layout, https, titles, the contact form and your Google profile, with the 10 fixes that matter most, easiest first.

{if they asked for fixes: I can also make the fixes on simple HTML sites, or give step-by-step guides for WordPress/Wix/Squarespace.}

Timeline: {days} days. Fixed price: ${price}.

Which pages bring you the most customers?

{your first name}

I use AI-assisted tools to draft the report; I run the checks and write the advice myself.
```

### landing-page

```
Hi {name},

One page, one goal: {their goal: bookings / sign-ups / calls} for {their offer}. I build fast landing pages that work on phones: headline, benefits, real proof, FAQ and a form or tap-to-call.

Example: {link}
Timeline: {days} days. Fixed price: ${price}, with {revisions} rounds of changes.

Do you have the words, or should I write them?

{your first name}

I use AI-assisted tools for first drafts and code and finish every page myself. If you prefer no AI, tell me.
```

### social-month

```
Hi {name},

A month of posts for {their business}, so you don't have to think about it every week. Each post gets a designed image in your colours, a short caption in your voice with a clear next step, and a posting date. In the top package I schedule them in your Meta Business Suite.

Example posts: {link}
Timeline: {days} days. Fixed price: ${price}.

Any offers or events this month I should plan around?

{your first name}

I use AI-assisted tools for first drafts; I edit every caption and design every image myself.
```

### chat-widget

```
Hi {name},

A chat box on {their site} so customers who won't call can still reach you. I install a free chat widget (your account), set your greeting, hours and saved answers, and make sure alerts reach your phone.

No passwords needed: you create the account and invite me, or paste one line of code.

Timeline: {days} days. Fixed price: ${price}.

What platform is your site on?

{your first name}

I use AI-assisted tools for drafts and finish everything myself.
```

## Daily routine (about 20 min in the morning + 35 min in the evening)

| When | Do |
|---|---|
| Morning, before work (10 min) | Fiverr and Upwork inboxes: answer every new message (Fiverr shows your response time to buyers). Accept or ask a question on new orders. |
| Morning (10 min) | Upwork, by hand: open your 2 saved searches (posted in the last 24 h, payment verified, fixed price, US/UK/CA/AU). Pick at most 2 jobs that match a gig below. Send at most 2 proposals from the templates, each with 2 sentences written only for that client. |
| Evening (25 min) | Deliver what is due in the next 48 h: run the gig's tool, review on your phone with the checklist, deliver with a short note. |
| Evening (10 min) | Revisions and follow-ups. Log each order in the money ledger (amount after the platform's cut). |
| Sunday (30 min) | Look at the gig stats (impressions, clicks, orders). Change ONE thing on the weakest gig (first picture, title or price). Add one finished job to your portfolio if the client said yes. |

**Limits:**

- Upwork: 1-2 proposals per weekday at most. Each costs Connects ($0.15 each, a proposal usually 6-16 Connects). The free plan gives about 10 Connects a month; Freelancer Plus is $19.99 a month for 100. Start on Fiverr (free to list) and add Upwork Plus only after your first 3 Fiverr reviews.
- Fiverr: a new seller can only have a few gigs live (4 to 7 depending on the source): start with the 4 marked 'start here'.
- Contra: list the same 4 services there too (no commission on client work); put the Contra link in the Instagram bio.
- Freelancer.com: skip at the start (about 6 free bids a month, a 10% or $5 fee); try it later if the others are slow.
