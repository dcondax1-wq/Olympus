# More money machines (team F1, 2026-11-14)

Owner: "I want more money making machines ... freelance work automatically, or Instagram accounts." This is the honest plan:
what each machine is, what it costs, how many hours it takes and what it can really earn. The agency kit (`agency/`, teams
B1-B6: lead finder, demo sites, storefront, chat widget, review booster, social posts, billing) is the main machine; everything
here plugs into it instead of rebuilding it.

| Machine | Startup cost | Hours / week | Realistic $ / month at 3 months | at 12 months | Risk | First 3 steps |
|---|---|---|---|---|---|---|
| **1. Freelance gigs** (Fiverr first, then Upwork and Contra; 8 gigs in `docs/GIG_PACK.md`) | $0 (Upwork Plus $19.99/mo optional later) | 6-10 | $0-400 | $500-2,000 | Low money risk. Account ban if a platform rule is broken. Slow start (new sellers wait weeks for the first order). | 1. Fiverr seller account in your real name, finish the ID check. 2. Publish the logo and Google-profile gigs today (their tools are ready). 3. Answer every message the same day; deliver with the checklist. |
| **2. Instagram: local business growth tips** (feeds the agency) | $0 | 3 | $0-100 | $100-600 (agency clients it brings, not Instagram pay) | Low. Slow growth; posting alone does not sell. | 1. New Instagram, switch to a Professional account. 2. Schedule the 30-day plan in Meta Business Suite (free). 3. Send interested owners to the free website check. |
| **3. Instagram: the eval journal** (trading routines, no results) | $0 | 2-3 | $0-30 | $50-400 (tracker sales + disclosed affiliate links) | Medium: strict rules (no profit claims, #ad on every paid link). | 1. Second Instagram, Professional account. 2. Schedule the 30-day plan. 3. Link the eval tracker in the bio. |
| **4. Digital products** (eval tracker built; 4 more listed) | $0 (Payhip/Gumroad free plans; Etsy $0.20 a listing) | 1-2 | $0-100 | $50-500 | Low. Most listings sell little without an audience. | 1. Free Payhip or Gumroad account. 2. Upload the eval tracker zip, cover and listing text ($17). 3. Put the link in the eval journal bio. |
| **5. Rank-and-rent sites** (research and plan only) | about $12 a year per domain + $1.15/mo per call-tracking number (your choice) | 3-5 per site | $0 | $0-750 per rented site | Medium-high: 3-12 months to rank, maybe no tenant, legal care needed. | 1. Decide if one $12 domain is worth a 6-month test. 2. Pick one trade + small town with weak competition. 3. Build the site with the agency tool and wait. |

**All together, honestly:** about 15-20 hours a week could make **$0-600 a month after 3 months** and **roughly $700-4,000 a month after
12 months** if the gigs get good reviews and the agency signs clients. None of this replaces a salary in 3 months. The fastest real
money is still the agency (local websites, B1-B6) and the freelance gigs, because a client pays for a finished job; content and
products are slow and compound.

What to do first: **the freelance gigs** (no cost, the tools are ready) and **the local-growth Instagram** (it feeds the agency).
Start the eval journal and the tracker product only when those run by themselves.

---

## 1. Freelance gig machine (productized; the owner delivers, the tools do the heavy lifting)

The pack: **`docs/GIG_PACK.md`** (generated from `money_machines/gig_pack.json`): 8 gigs, each with title, 5 search tags,
description, 3 priced packages, FAQ, buyer questions, the delivery checklist, the exact command that makes the deliverable and the
revision policy, plus Upwork proposal templates and the daily routine.

| Gig | Packages ($) | Owner's time (min) | Tool that makes it | Ready? |
|---|---|---|---|---|
| Fast mobile website for a local business | 120 / 260 / 480 | 35 / 55 / 90 | B1 site generator (`python -m agency.build_site`) | when the agency kit is merged |
| Simple logo + brand kit | 25 / 55 / 95 | 20 / 35 / 50 | `python -m money_machines.brand_kit` (built here) | yes |
| Google Business Profile set-up + checklist | 35 / 75 / 140 | 25 / 50 / 75 | `python -m money_machines.gig_pack checklist` (built here) | yes |
| Honest review system (QR card + scripts) | 30 / 60 / 110 | 15 / 30 / 50 | B4 review booster (`agency/upsells/make_review.py`) | when merged |
| Website speed + SEO fix report | 35 / 70 / 140 | 25 / 45 / 90 | B3 website grader (`agency/storefront/grade.py`) + PageSpeed Insights by hand | when merged |
| Landing page | 70 / 140 / 250 | 25 / 45 / 75 | B1 site generator (one page) | when merged |
| A month of social posts + images (12 or 20) | 45 / 85 / 140 | 30 / 45 / 70 | B5 social-post machine (`agency/content/make_posts.py`) | when merged |
| Chat widget install | 25 / 55 / 95 | 15 / 35 / 55 | a free chat service by hand, or B4's widget (`agency/upsells/make_chat.py`) | by hand yes |

A paid order becomes the agency tools' input with one line: `python -m money_machines.gig_pack order --gig <gig> --name ... --category ...
--city ...` writes `lead.json` (for B1's site generator) and `client.json` (the shared client record B4's and B5's tools read) and prints
the next command. `python -m money_machines.gig_pack --check` prints which tools are installed. Prices are launch prices inside the ranges competing gigs
showed on 2026-11-14 (websites $150-800 for 3-6 pages and $400-1,200 in Fiverr's own guide; landing pages $25-250; 30 posts with
graphics $30-115; logos mostly $15-50 basic; review QR cards from $25; Google profile gigs "up to $50"). Raise them about 30% after 5
five-star reviews. **Fiverr keeps 20%**, so a $120 order pays $96. What the brand kit makes: `docs/shots/money_machines/brand_kit_concepts.jpg` (3 concepts for one
client; the full kit adds 4 logo layouts, dark/light versions, favicon, profile picture, banner, business cards, palette and a guide).

### The platforms' rules (searched 2026-11-14; check the official page before relying on a number)

| | Fiverr | Upwork | Contra | Freelancer.com |
|---|---|---|---|---|
| **Identity** | Government ID + a live selfie, done on a phone, when Fiverr asks; 14 days to finish or the account is restricted; 5 tries. One account per person (a Team seat is the only exception). | Passport, driver's licence or national ID; sometimes a short video call with an agent; 7 days to finish; profile photo must clearly be you and the country must match. | Identity check (Persona) before the wallet / payouts. | Can refuse any account; the KYC steps were not in the search results: check the site. |
| **Bots and automation** | Bans automated mass messages, scraping (Terms 8.8, even by hand), ranking manipulation, and services that automate other platforms against their rules. | Bans any script, program or browser extension that acts faster than a human; only an approved API key is allowed, and even then no proposal spam or scraping. Its own **MCP server** (2026-08-10) lets an AI tool find jobs and draft proposals with **your confirmation on every action**. | Nothing specific found: treat it like Upwork. | Bans bots that cheat or get around its systems. |
| **AI use** | Hiding AI use is a breach of trust; generic, unedited AI output fails its quality standard; follow a client's no-AI request. | User Agreement 3.2: no generative AI where the client restricts it; Upwork recommends telling clients up front. | Nothing found. | Nothing found. |
| **Fees** | 20% of every order. The buyer pays a 5.5% service fee (+ $3.50 on orders under $200). | Variable service fee, 0-15% per contract (since 2025-05-01; often about 10%). Connects $0.15 each, 6-16 per proposal; 10 free a month; Freelancer Plus $19.99/mo = 100. | 0% commission on client work; the free plan has fees on some client payments; Pro $29/mo; Stripe fees apply. | 10% or $5 (fixed price), 10% hourly; about 6 free bids a month. |
| **When you get paid** | 14 days after the order completes (7 days for Top Rated, Seller Plus and Pro); early payout 1% for those eligible. | Fixed price: the client has 14 days to approve, then a 5-day security hold. Hourly: billed weekly, released the following week. | Through Stripe (bank, debit card or USDC). | When the client releases a milestone. |

**What stays human (always):** the account (one, in his real name, verified by him); every message to a client (AI may draft, he sends);
accepting orders and prices; the final check of every deliverable on his phone; honesty about AI; payments only on the platform.

**What we never build** (it breaks the platforms' rules): auto-bidding or auto-proposal bots, scrapers of jobs or profiles, mass-message
bots, fake / bought / swapped reviews or review gating, a second account or a hidden location, anything that promises rankings or results.

**Daily routine** (about 20 minutes before work + 35 after): answer both inboxes; on Upwork pick at most 2 jobs by hand from 2 saved
searches and send at most 2 personal proposals; deliver what is due within 48 h with the tool + checklist; log each order. Sunday: change
one thing on the weakest gig. Start on Fiverr (free); add Upwork Plus only after 3 Fiverr reviews (10 free Connects a month cover 1-3 proposals).

---

## 2. Content accounts (Instagram): two accounts, a 30-day plan each, posting only with the owner's own token

### The rules that matter (searched 2026-11-14)

- **Automation:** Instagram's terms ban automated data collection and artificial likes, follows and comments, and Meta has sued
  automation services. Scheduling and publishing through Meta's own tools or the official API is allowed. So: **we post, we never
  like, follow, comment or DM by bot.**
- **The free scheduler:** Meta Business Suite (Planner) schedules Instagram posts, carousels, Reels and Stories, reported as up to
  **75 days ahead** (older pages say 29) and about 25 scheduled posts a day. No token, no code, free.
- **The publishing API (Instagram Graph API):** a **professional account** (Business or Creator); a free Meta developer app with
  `instagram_business_content_publish` (Instagram Login, no Facebook Page needed) or `instagram_content_publish` (Facebook Login +
  a Page). For your own account the app's Standard Access works while you have a role on the app (third-party guides say no App
  Review is needed; check Meta's page). Images: **JPEG on a public https address**, 4:5 to 1.91:1, up to 8 MB. Two calls: create a
  container, then publish. **Limit: 100 API posts per rolling 24 h in Meta's guide, "currently 50" on its reference page:** read
  `content_publishing_limit` before each post. Tokens: short-lived 1 hour, long-lived **60 days**, refresh after the first 24 h.
- **Hashtags:** Instagram has been rolling out a **5-hashtag limit** since December 2025 (some 2026 pages still say 30). We use at most 5.
- **FTC (US):** disclose any paid or affiliate relationship **in the caption, before "more"**, not only in the bio or in a pile of
  hashtags; "#ad" or "Ad" works. Fake reviews and sentiment-based rewards are banned by the 2024 rule. Earnings claims must be
  typical and backed up ("results not typical" does not fix a misleading claim); the FTC proposed in January 2025 to extend its
  earnings-claim rule to money-making and coaching offers.
- **Trading content:** CFTC Rule 4.41 requires a set warning when simulated results are shown by trading advisors; whether a creator
  counts as one is a legal question we avoid by **never showing results, simulated or real**: only rules, routines and labelled math examples.

### The two accounts

| | **Main Street Growth** (`local_growth`) | **The Eval Journal** (`eval_journal`) |
|---|---|---|
| For | local business owners | traders in prop-firm evaluations |
| Makes money by | sending owners to the agency's free website check (one client = B1's Starter $499 + $49/mo) | the eval tracker product ($17), later disclosed affiliate links, sponsored posts once it has an audience |
| Plan | 30 posts from Mon 2026-11-16, 11:45 ET; Thanksgiving, Black Friday, Small Business Saturday and holiday-hours posts land on their days | 30 posts from Mon 2026-11-16, 07:30 ET (before the open); a holiday-week post on 11-23 |
| Look | AGORA ivory (light) | AGORA night (dark) |
| Hard rules | no ranking promises; examples labelled; honest-review advice only | education only; every caption ends with the risk line; numbers only in "Example only" posts; no results, profits, passes, payouts or signals; a paid link starts the caption with "Ad" |
| Plan files | `money_machines/plans/local_growth_30d.md` (+ `.json`) | `money_machines/plans/eval_journal_30d.md` (+ `.json`) |
| Sample image | `docs/shots/money_machines/local_growth_day01.jpg` | `docs/shots/money_machines/eval_journal_day04.jpg` |

Make the images (Chromium, about 10 seconds for 30): `python -m money_machines.content_plan --all --render` writes
`money_machines/out/content/<account>/dayNN.jpg` (1080 x 1350 JPEG), `index.html` (the posting sheet: image, caption, alt text) and
`schedule.csv`. A new month: `--fresh` (next Monday) or `--start YYYY-MM-DD`. When team B5's content kit is installed
(`agency/content/designs.py`), the cards use its embedded open fonts (Fraunces, Manrope) like the agency's own posts; `--style FILE`
overrides colours and fonts.

### How to post (simplest first)

1. **Meta Business Suite, by hand (recommended):** open the posting sheet, then Planner > Create post: upload the image, paste the
   caption, add the alt text, pick the time. A week takes about 15 minutes. No token, nothing to break.
2. **The API, automatic (optional, later):** make a free Meta developer app, add your own Instagram as a tester, put the long-lived
   token in a private file outside the repo (`~/.config/olympus/instagram.json`), put the images online at a public https folder, then
   once a day: `python -m money_machines.ig_post --plan money_machines/plans/local_growth_30d.json --image-base-url https://.../ --live`.
   Without `--live` it is a dry run. It reads Instagram's own limit first, posts at most 1 a day (our cap, never above 25), keeps a
   ledger so a day is never posted twice, stops on any rate-limit error and never prints the token.

**Stays human:** replying to comments and DMs (no auto-DM tools), approving each week's posts, the accounts themselves.

### Growth and money, honestly

- There is no good public data for brand-new accounts. Buffer's 2026 benchmark is about 7.5% follower growth a month across its
  accounts, and Socialinsider reports engagement down about 24% year on year. **Plan for 100-1,000 followers in the first 3 months**
  at one post a day (our estimate, not a promise).
- Sponsored posts: published 2026 rate cards put nano creators (1k-10k followers) at about **$10-250 a post** and micro (10k-100k)
  at $100-1,500, with finance 2-3x higher. Instagram's own pay features need followers first (Gifts about 500, Subscriptions about 10,000).
- So the money is **indirect**: agency clients from the local account, product sales and disclosed affiliate links from the eval journal.
  Prop-firm affiliate programs are team B6's research; join one only with a clear "Ad / affiliate link" first line every time.

---

## 3. Digital products (passive once listed)

### Where to sell them (fees and rules, searched 2026-11-14)

| | Payhip (free plan) | Gumroad | Etsy |
|---|---|---|---|
| Fees | 5% a sale + Stripe/PayPal fees; Plus $29/mo = 2%, Pro $99/mo = 0% | 10% + $0.50 a sale (30% on sales its Discover page brings); card fees on top in third-party 2026 guides | $0.20 a listing (4 months) + 6.5% + 3% + $0.25 processing (US); Offsite Ads 12-15% only on sales they bring |
| You keep from $17 | about **$15.36** | about **$14.01** | about **$14.94** |
| Paid out | straight to your PayPal / Stripe | to your bank; a 2026 newsletter reports a $100 minimum until you verify identity ($10 after) | Etsy Payments to your bank |
| Rules that matter here | sells digital files; tax handling not confirmed in the search | lists "prohibited investments" and reviews online-trading and stock-market products more closely | digital files must be your own work (no resold templates); AI-made items are "designed by" and disclosed in the description |
| Best for | the first store (lowest fee, no monthly cost) | a second store (its Discover page can bring buyers) | search traffic for templates and planners |

### Built end to end: the Prop Eval Tracker ($17)

`money_machines/products/eval_tracker/`: **`Prop_Eval_Tracker.xlsx`** (Rules, Log, Dashboard, Size; works in Excel and Google Sheets;
1,424 formulas, recalculated with LibreOffice: 0 errors), **`prop_eval_tracker.html`** (the same tracker as an offline web page with a
chart, CSV export and backups; a Content-Security-Policy blocks every network call), **`How_to_use.pdf`** (2 pages), `LICENSE.txt`,
`README.txt`, the listing copy (`listing.md` / `listing.json`: title, description, 13 Etsy tags, FAQ, fee table, rules), and the
pictures (`cover.jpg` 1280 x 720, `cover_square.jpg` 2000 x 2000, `app_screenshot.jpg`).

- It tracks **the buyer's own rules**: EOD trailing, intraday trailing or static max loss, where the trail stops, daily loss limit,
  consistency rule, minimum days; per day the net P&L and, if known, the day's low and high. It shows drawdown left, the max-loss
  level, target left, the consistency check and a status (OK / CAREFUL / DAILY LIMIT / BREACHED / TARGET MET), and sizes the next
  trade with our "size follows the stop" rule (contracts = risk / (stop x $ per point + costs)).
- One math in three places: `eval_math.py` (Python), the spreadsheet formulas and the web page's JavaScript. LibreOffice recomputes the
  spreadsheet in 3 scenarios and Chromium runs the JavaScript: both equal the Python (`--verify`, `tests.test_money_machines e`).
- It names no prop firm, shows no results, promises nothing and says it is not affiliated with anyone; the description says AI coding
  tools helped (Etsy's rule).
- The upload file: `python -m money_machines.products.build_eval_tracker --zip` packs the 5 buyer files into
  `money_machines/out/products/prop_eval_tracker_v1.0.zip` (plain Python, works on the PC). Rebuilding the files themselves (no flag) needs openpyxl and Chromium.

**List it (owner, about 20 minutes):** 1. Free Payhip account. 2. New product > Digital download: upload the zip, paste the title and
description from `listing.md`, add `cover.jpg` and `app_screenshot.jpg`, price $17. 3. Put the link in the Eval Journal bio.

### Four more (planned; `money_machines/products/catalog.json`)

| Product | Price | Effort | Made from | Honest note |
|---|---|---|---|---|
| 5 one-page website templates for local trades (HTML) | $24 | 5 h | the agency demo-site themes (B1) | buyers often want Canva/Wix; add a "put it online free" guide |
| 60 Instagram post templates + 120 captions for local businesses | $14 | 4 h | the content-plan cards (+ B5's style) | crowded; most buyers expect Canva links |
| Google Business Profile checklist + 52 weekly post prompts | $9 | 2.5 h | the GBP gig checklist | low risk; keep Google's rules in it |
| Honest review request kit (QR cards, scripts, replies) | $11 | 2 h | B4's review booster + the gig scripts | must teach: ask everyone, no rewards, no gating |

Expect **0-10 sales a month per product** until the Instagram accounts or search send buyers; comparable listings: an Etsy prop-firm
challenge tracker about $16.68 (on sale from $22.24), trading journals $9.90-35, 100-template Canva packs about $10-15.

---

## 4. Rank-and-rent / lead-gen sites (research and plan only; nothing built, nothing bought)

**How it works.** Build a small website for one service in one town ("emergency plumber, Loveland CO"), get it into Google's
results, then rent the whole site to one local business for a monthly fee, or sell it the calls and form requests (pay per lead).
Calls go through a tracking number that forwards to the business, so both sides can count them.

**What it costs.**

| Item | Cost | Note |
|---|---|---|
| Domain (.com) | about $10-15 a year | the owner's choice; nothing here buys one |
| Hosting | $0 | a static site on a free plan, the same way as the agency's demo sites |
| Call tracking (optional) | $1.15 a month per local number + $0.0085 a minute for incoming calls | Twilio's US price page (Aug 2026); without it you cannot prove the calls |
| Building the site | 6-10 hours | with the agency site generator (B1) and your own writing |
| Keeping it alive | 1-2 hours a month | one useful page a month, check Search Console (free) |

**No Google Business Profile.** Google's guidelines do not allow profiles for lead-generation businesses or at virtual offices, and a
fake listing gets suspended (and misleads people). So rank-and-rent here means the normal (organic) results only, which is harder
than the map.

**How long to rank.** SEO agency estimates for a new local site: **3-12 months**, a brand-new domain at the slow end, crowded trades and
big cities longer. AI answers in Google take clicks from "how to" searches; urgent "near me" service searches still bring calls (one
2026 guide's view).

**What it pays.** One 2025 guide: $500-3,000 a month flat, or $20-100 per exclusive lead (not checked for 2026). For a small town and a
quiet trade, **$300-750 a month** is a more careful first rent. If the business stops paying, the site earns $0 until a new one rents it.

**Legal and fair-play notes (not legal advice).**
1. Say what the site is: a referral service, not the business itself ("We connect you with a local licensed plumber"). Once rented,
   show the tenant's real name, address and licence numbers (theirs). Misleading people is an unfair practice under the FTC Act.
2. Never claim a licence, insurance, years in business, awards or reviews the tenant does not have. No fake reviews (the FTC's 2024 rule).
3. Recording calls: in all-party-consent states (California, Delaware, Florida, Illinois, Maryland, Massachusetts, Montana, Nevada,
   New Hampshire, Pennsylvania, Washington) everyone must agree: play "this call may be recorded" or do not record.
4. The site only receives calls: no cold texts or robocalls (the TCPA).
5. Forms: a short privacy page, ask only for what the tenant needs (name, phone, the job); California visitors have privacy rights.
6. No brand names in domains ("carrier-ac-repair-..."), no copied photos.
7. Some states regulate referral services in some trades, and lawyers and doctors have strict advertising rules: avoid those niches,
   check the state's rules before renting in home improvement.
8. A simple monthly agreement (team B6's agreement template): what is included, one month's notice, the domain stays yours.
9. Rent is business income (team B6's business setup notes).

**The plan, if the owner wants to try (one site, a 6-month test).**
1. Pick one high-ticket trade (plumbing, heating, roofing, tree service, garage doors) in one small town (20,000-80,000 people) where
   the agency's lead finder shows many businesses without a website: weak online competition.
2. Week 1: one domain (about $12), a 5-page site from the agency generator (services, the town, FAQ, about, contact), free hosting,
   Google Search Console (free) with the sitemap.
3. Months 1-6: one useful page a month (costs, how to choose a pro, seasonal checks). Watch impressions and clicks in Search Console.
4. When the site brings about 5 calls or forms a month, offer it to 3 local businesses with the agency pitch kit: "these calls come from
   my site; a free first month, then $X a month".
5. Stop rule: nothing on page 1 after 6 months, stop paying for the domain, or turn the site into a portfolio piece for the agency.

Honest view: the slowest and least certain machine here (**$0 at 3 months, $0-750 a month per site at 12 months**). Do it only after
the gigs and the agency are running.

---

## Sources (web search on 2026-11-14; the official pages could not be opened from this sandbox, so each line is the search engine's reading of the page: re-check before relying on a number)

Freelance platforms
- Fiverr clearance 14 / 7 days, early payout 1%: [order process](https://help.fiverr.com/hc/en-us/articles/360010639617-Managing-your-orders-A-freelancer-s-guide-to-the-Fiverr-order-process), [Early Payout](https://help.fiverr.com/hc/en-us/articles/4402267122449-Early-Payout)
- Fiverr ID + selfie, 14 days, 5 tries: [Verify your identity](https://help.fiverr.com/hc/en-us/articles/13127850435345-Verify-your-identity), [new freelancer verification](https://help.fiverr.com/hc/en-us/articles/6348992414097-Verifying-your-identity-as-a-new-freelancer)
- Fiverr bots, scraping, mass messages, one account, fake reviews, guaranteed results: [Community Standards](https://help.fiverr.com/hc/en-us/articles/32242973123985-Our-Community-Standards), [Prohibited services](https://help.fiverr.com/hc/en-us/articles/49174165608593-Prohibited-services-on-Fiverr), [Terms of Service](https://learn.fiverr.com/pages/terms-of-service)
- Fiverr AI: [Using AI on Fiverr](https://help.fiverr.com/hc/en-us/articles/37333301560593-Using-AI-on-Fiverr-Guidelines-for-freelancers-and-clients); buyer fee 5.5% + $3.50 under $200: [Paying for orders](https://help.fiverr.com/hc/en-us/articles/360050216133-Paying-for-orders-extras-or-custom-offers); 20% seller fee: [vaultleap 2026](https://vaultleap.com/blog/fiverr-fees-explained-2026)
- Fiverr gig limits (description 1,200 official; title 80, 5 tags of 20 chars, FAQ sizes from guides): [Creating a Gig](https://help.fiverr.com/hc/en-us/articles/360010451397-Creating-a-Gig), [eduearnhub](https://eduearnhub.com/fiverr-character-limits/); gigs per level (4-7 for new sellers): [zenlance](https://zenlance.net/fiverr-seller-levels/)
- Upwork bots: [Use bots and other automation properly](https://support.upwork.com/hc/en-us/articles/43342677368467-Use-bots-and-other-automation-properly), [Legal center](https://www.upwork.com/legal#terms-of-use); MCP server 2026-08-10: [press release](https://www.upwork.com/press/releases/upwork-talent-is-now-everywhere-ai-works), [upwork.com/ai/mcp](https://www.upwork.com/ai/mcp)
- Upwork identity: [Verify your identity as a freelancer](https://support.upwork.com/hc/en-us/articles/360001176427-Verify-your-identity-as-a-freelancer); payments: [fixed price](https://support.upwork.com/hc/en-us/articles/211063718-How-payments-for-milestones-and-fixed-price-contracts-work), [hourly](https://support.upwork.com/hc/en-us/articles/211063668-How-payments-for-hourly-contracts-work)
- Upwork AI: [AI preferences](https://support.upwork.com/hc/en-us/articles/23808634769683-How-to-control-your-AI-preferences-on-Upwork); fee and Connects: [is Upwork free](https://www.upwork.com/resources/is-upwork-free), [golance 2026](https://golance.com/blogs/upwork-fees-explained-2026)
- Contra: [identity](https://help.contra.com/en/articles/9322955-how-to-verify-your-identity-on-contra), [payouts FAQ](https://contra.com/faq/independents/general-payouts), [fastlancer review](https://www.fastlancer.org/en/fastlancer-blog/contra-review/)
- Freelancer.com: [fees and charges](https://www.freelancer.ie/feesandcharges), [projects violating terms](https://www.freelancer.cz/support/project/projects-violating-our-terms-and-conditions), [bidding FAQ](https://www.freelancer.mx/faq/topic.php?id=5)

Competing gig prices
- Websites: [Fiverr web design cost guide](https://www.fiverr.com/resources/guides/graphic-design/website-design-costs), [website-builder guide](https://website-builder-d1x.pages.dev/posts/2025/12/fiverr-website-building-guide-for-small-businesses); landing pages: [Fiverr front-end cost guide](https://www.fiverr.com/resources/guides/costs/front-end-web-developer)
- Social posts: [30-post gig](https://fiverr.com/m_safeer/design-30-social-media-post-quotes-graphics), [Upwork calendar](https://www.upwork.com/services/product/writing-translation-a-social-media-calendar-for-one-month-1426282614399123456); logos: [Fiverr graphic design prices](https://www.fiverr.com/resources/guides/graphic-design/graphic-design-cost), [review42](https://resources.review42.com/how-much-to-charge-for-logo-design/)
- Google profile gigs: [example](https://fiverr.com/elena_whittmore/setup-and-optimize-your-google-business-profile); review QR cards: [example](https://www.fiverr.com/utopia_lab/design-qr-code-sticker-card-with-call-to-action); speed audits and chat installs: listings showed no prices (our prices are set from the neighbouring categories)

Reviews (for the review and Google-profile gigs)
- FTC Consumer Reviews and Testimonials Rule, in force 2024-10-21: [press release](https://www.ftc.gov/news-events/news/press-releases/2024/08/federal-trade-commission-announces-final-rule-banning-fake-reviews-testimonials), [Q&A](https://www.ftc.gov/business-guidance/resources/consumer-reviews-testimonials-rule-questions-answers), [2025-12 warning letters](https://www.ftc.gov/news-events/news/press-releases/2025/12/ftc-warns-10-companies-about-possible-violations-agencys-new-consumer-review-rule)
- Google: no incentives, no selective asking: [prohibited content](https://support.google.com/business/answer/7400114), [tips to get more reviews](https://support.google.com/business/answer/3474122)

Instagram and Meta
- Publishing limit 100 vs 50, `content_publishing_limit`: [reference](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/content_publishing_limit), [content publishing guide](https://developers.facebook.com/docs/instagram-platform/content-publishing/), [adaptlypost on the two numbers](https://adaptlypost.com/blog/content-publishing-limit-instagram-api)
- Permissions, professional accounts, public URL: [Instagram API with Instagram Login](https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-instagram-login), [Business Login](https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-instagram-login/business-login); JPEG, 4:5-1.91:1, 8 MB: [adaptlypost image requirements](https://adaptlypost.com/blog/instagram-api-image-requirements); 60-day tokens: [getphyllo guide](https://www.getphyllo.com/post/instagram-api-guide)
- Meta Business Suite 75 days: [OneUp](https://www.oneupapp.io/blog/schedule-facebook-and-instagram-posts-more-than-29-days-into-future.md), [SocialBee](https://socialbee.com/blog/meta-planner-30-day-post-scheduling-restriction/)
- Automation and lawsuits: [Meta newsroom](https://about.fb.com/news/2020/06/automation-software-lawsuits/); 5 hashtags: [Later](https://later.com/blog/instagram-hashtags/amp), [InstantDM](https://instantdm.com/blog/instagram-hashtags), [Circleboom (still 30)](https://circleboom.com/blog/how-many-hashtags-should-you-use-on-instagram-in-2026/)
- Growth: [Buffer benchmarks](https://buffer.com/insights/instagram-benchmarks), [Socialinsider 2026](https://www.socialinsider.io/blog/instagram-benchmarks/?RewriteStatus=1); rates: [Influencer Marketing Hub](https://influencermarketinghub.com/instagram-influencer-rates/), [Later 2026 benchmarks](https://later.com/blog/influencer-pricing-benchmarks-the-complete-2026-guide/), [influee](https://influee.co/blog/instagram-influencer-pricing); pay features: [influencermarketinghub](https://influencermarketinghub.com/instagram-subscriptions-gifts/)
- FTC disclosures: [Endorsement Guides FAQ](https://www.ftc.gov/business-guidance/resources/ftcs-endorsement-guides-what-people-are-asking), [Disclosures 101](https://www.ftc.gov/business-guidance/resources/disclosures-101-social-media-influencers); earnings claims: [FTC 2025 proposal](https://www.ftc.gov/business-guidance/blog/2025/01/concerned-about-deceptive-earnings-claims-sos-ftc-we-want-your-feedback); CFTC Rule 4.41: [Federal Register 2007](https://www.federalregister.gov/documents/2007/02/23/E7-3122/advertising-by-commodity-pool-operators-commodity-trading-advisors-and-the-principals-thereof)

Digital product platforms
- Gumroad 10% + $0.50, Discover 30%, card fees extra: [checkoutpage 2026](https://checkoutpage.com/blog/gumroad-fees), [dodopayments](https://dodopayments.com/blogs/gumroad-fees-explained); payout minimum change (single source): [roo newsletter](https://roo.beehiiv.com/p/gumroad-fees-2026); prohibited products: [gumroad.com/prohibited](https://gumroad.com/prohibited), [help: things not allowed](https://help.gumroad.com/article/155-things-you-cant-sell-on-gumroad)
- Etsy fees: [craftybase guide](https://app.craftybase.com/blog/the-complete-guide-to-etsy-fees), [checkoutpage](https://checkoutpage.com/blog/etsy-fees); creativity standards and AI disclosure: [Etsy house rules](https://www.etsy.com/legal/creativity), [listadum summary](https://www.listadum.com/blog/etsy-creativity-standards)
- Payhip plans 5% / 2% / 0%: [sellfy summary](https://sellfy.com/blog/payhip-pricing/), [passivekit](https://passivekit.com/payhip-pricing/)
- Comparable products: [Etsy prop firm challenge tracker](https://www.etsy.com/listing/4606983180), [Etsy trading journal](https://www.etsy.com/listing/4601752496), [Etsy 100 Instagram templates](https://www.etsy.com/listing/900701313/100-instagram-post-templates-instagram?pro=1), [Etsy HTML website template](https://www.etsy.com/listing/4442821091/responsive-website-template-html-css)
- Contract values ($ per point) in the tracker: the exchanges' contract specifications (MNQ $2, NQ $20, MES $5, ES $50, M2K $5, RTY $50, MYM $0.50, YM $5, MGC $10, GC $100, MCL $100, CL $1,000 per 1.00)

Rank-and-rent
- How it works and prices: [Search Engine Journal](https://www.searchenginejournal.com/rank-and-rent/321315/), [Alejandro Rioja 2026 guide](https://alejandrorioja.com/rank-and-rent/), [Ippei local lead-gen guide](https://ippei.com/local-lead-generation-guide/), [Side Hustle Nation](https://www.sidehustlenation.com/rank-and-rent-websites/)
- Google Business Profile: [guidelines (service-area / virtual offices)](https://support.google.com/business/answer/3038177), [Search Engine Journal on suspensions](https://www.searchenginejournal.com/google-business-profile-suspended/448553/), [PaperStreet on virtual offices](https://www.paperstreet.com/blog/can-i-list-my-business-on-google-maps-using-a-virtual-office/)
- Time to rank: [BrightLocal](https://www.brightlocal.com/research/long-take-rank-local-search/), [SEO Discovery](https://www.seodiscovery.com/blog/how-long-does-it-take-for-seo-to-work/), [PushLeads](https://pushleads.com/how-to-improve-google-rankings/how-long-rank-google/)
- Call tracking price: [Twilio US voice pricing](https://www.twilio.com/en-us/voice/pricing/us); all-party consent states: [Layer3 Labs (Aug 2026)](https://www.layer3labs.io/guides/two-party-consent-states), [Scribbl](https://scribbl.co/post/do-you-have-to-tell-people-youre-recording)
