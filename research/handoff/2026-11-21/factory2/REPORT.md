# Website Factory 2: inbound + close + deliver (2026-11-21)

Branch **day-cities3** (this session may push only there; land from it). Base: origin/pc 7adf312d + origin/day-kalshi (16 towns' leads) merged.

| # | What | Result |
|---|---|---|
| 1 | Concept sites from all 16 towns | **1,571 sites** (1,577 leads minus 6 chains / big health systems), noindex, no reviews/prices/awards, codes per town (FR-n, GA-n, ...), gallery + `agency/sites/index.json`. 1,149 "ready" (phone or street address), **138 with a phone**. Largest page 11.9 KB. |
| 2 | Agency launch site | `tools/agency_site.py`: home, work (2 best concept sites per trade), pricing (from offers.json: Starter $1,500 + $79/mo · $149/mo nothing upfront · Call engine $500 + $299/mo), FAQ (+FAQPage schema), contact (mailto + phone, no paid form), **16 local pages** "Website design for <trade> in <town>, MD" with that town's real counts from the leads and trade-specific advice (trades spread: health, salons, gyms, auto, offices, shops, restaurants), area index, sitemap, LocalBusiness schema with AGENCY_NAME / AGENCY_PHONE / AGENCY_EMAIL placeholders. noindex until `agency_name` is set. Preview: `agency/launch/`; the neutral export puts it at the root. |
| 3 | Google profile + directories | `GBP_LAUNCH.md`: service-area profile (no home address), category, 16 towns, verification, description to paste, then Bing (import), Apple Business Connect, Yelp, Nextdoor, Facebook, LinkedIn. |
| 4 | Yes -> live in 24 h | `tools/client_deliver.py <code or id> edits.json`: concept + client edits (name, phone, hours, address, tagline, about, services, logo, photos) -> `site/` (indexable, canonical to their domain, CNAME, _headers, robots, sitemap, 404) + `PUBLISH.md` (GitHub Pages A records / Cloudflare Pages, domain filled in) + `CARE_PLAN.md` ($79/mo checklist). Refuses bad domains, missing/fake/2 MB+ images, script SVGs, fake-review words. Output goes to `scratch/clients/` (gitignored: client files never land in the public site). |
| 5 | First 100 calls | `tools/first_calls.py` -> `agency/portal/first100.json` (caller-portal format + rank, score, why): hot, open on weekdays 9-17, buying trade, storefront. Only 138 leads have a phone, so this is most of them. |
| Tests | | test_factory2 23/23 (with browser), test_site_factory 28/28, smoke 11/11, privacy scan of every new public file: 0 findings. |

## What the owner must do (3 lines)
1. Pick the agency name + make the free agency Gmail and phone number (then `GBP_LAUNCH.md`, 30 min).
2. Create the neutral host (`../factory/HOST_SETUP.md`, 5 min) and send the lead its address.
3. Hire / be the caller for `first100.json` (commission-only: $300 a sale), or say "send postcards".

## The $ path (estimates, not results)
- Each sale: **$1,500 + $79/mo** (or $149/mo x 12 = $1,788 the first year). After the caller's $300: **$1,200 + $79/mo to you**.
- 100 calls at a 1-3% close (typical for cold local web calls) = **1-3 clients = $1,200-$3,600 + $79-$237/mo**.
- Postcards to the 1,149 ready leads (~$1 each, the plan's 1% response x 1/3 close = ~4 clients) = **~$4,800 + $316/mo for ~$1,150 of cards**.
- Delivery cost per client: ~1-2 h of Claude + the owner's 0 minutes (the bundle + PUBLISH.md); care plan ~20 min/month each.
- Rule from the plan: 0 sales after 200 contacts = change niche/offer before spending more.
