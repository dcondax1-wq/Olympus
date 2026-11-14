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
| Fast mobile website for a local business | 120 / 260 / 480 | 35 / 55 / 90 | B1 demo-site generator (`python -m agency.build_site`), fed by `python -m money_machines.gig_pack order ...` | when the agency kit is merged |
| Simple logo + brand kit | 25 / 55 / 95 | 20 / 35 / 50 | `python -m money_machines.brand_kit` (built here) | yes |
| Google Business Profile set-up + checklist | 35 / 75 / 140 | 25 / 50 / 75 | `python -m money_machines.gig_pack checklist` (built here) | yes |
| Honest review system (QR card + scripts) | 30 / 60 / 110 | 15 / 30 / 50 | B4 review booster (`agency/upsells`) | QR maker yes, card maker when merged |
| Website speed + SEO fix report | 35 / 70 / 140 | 25 / 45 / 90 | `python -m money_machines.gig_pack report` (wraps B1's `agency.audit`) + PageSpeed Insights by hand | yes (hand checks); automatic part when merged |
| Landing page | 70 / 140 / 250 | 25 / 45 / 75 | B1 demo-site generator (one page) | when merged |
| A month of social posts + images | 45 / 85 / 150 | 30 / 45 / 70 | B5 social-post machine | when merged |
| Chat widget install | 25 / 55 / 95 | 15 / 35 / 55 | free chat service by hand, or B4's widget | by hand yes |

`python -m money_machines.gig_pack --check` prints which tools are installed. Prices are launch prices inside the ranges competing gigs
showed on 2026-11-14 (websites $150-800 for 3-6 pages and $400-1,200 in Fiverr's own guide; landing pages $25-250; 30 posts with
graphics $30-115; logos mostly $15-50 basic; review QR cards from $25; Google profile gigs "up to $50"). Raise them about 30% after 5
five-star reviews. **Fiverr keeps 20%**, so a $120 order pays $96.

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
