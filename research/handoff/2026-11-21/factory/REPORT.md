# Website Factory: the site factory (day-cities3, 2026-11-21)

| what | result |
|---|---|
| Sites built | **67** (every Frederick lead in `agency/leads/leads.json`): food 47, health 8, gym 8, auto 4. Largest 10.9 KB (budget 100 KB) |
| Where | `agency/f/<8 random chars>/` (folder kept forever in `tools/site_factory_ids.json`, so a sent link never changes); `agency/f/` itself shows "Not found" |
| Gallery | `agency/factory/` (noindex): name, niche, town, phone yes/no, the link, live phone-width preview, Copy link / Share, niche filter, search |
| Look | 8 niche looks (health, food, auto, gym, salon, trades, cleaning, retail), 1-3 palettes each picked per business; SVG line icons per category (tooth, cross, paw, plate, cup, glass, cone, car, dumbbell...); soft moving hero, sticky call dock; respects reduced motion. Not the Olympus look |
| Content | Only the lead's facts: name, town, phone (click-to-call), address, hours (OSM hours parsed; unclear -> "call to ask"), OpenStreetMap link (no Google). Generic sections true for any business of that kind |
| Honesty | no reviews/testimonials/awards/prices/licences/years/photos; footer "Concept made for X - not live, not affiliated" + OSM credit; noindex/nofollow/noarchive, no-referrer; nothing loaded from other sites; nothing else links to it (checked) |
| Tests | `test_site_factory` 17/17 static + browser (5 random sites + gallery at 390 px: no error, no sideways scroll, call button reachable) = 18/18; in `run_area agency`. smoke 10/10 |
| Shots | `site-1..5.png` (urgent care, car wash, gym, restaurant, ice cream), `gallery.png` |

## Money truth (read before sending links)
1. **Only 8 of 67 leads have a phone on the map; 43 have neither phone nor street address.** Those sites are thin (name, kind, map link). The owner can't text a link to a business with no number: walk in, or use its Facebook/Instagram.
2. **9 look like chains that already have websites** (Exxon Car Wash, America's Best Wings, Anchor Bar, Bonefish, Bruster's, Glory Days, Crunch Fitness, Frederick YMCA, MedStar urgent care). The gallery marks them "Probably a chain: check before you send". The leads team should drop chains + public gyms upstream.
3. `mailto`: the leads carry no email, so there is no email button (it appears automatically when a lead gets an `email`). Call + map are the contact paths.

## For the lead
- Rebuild after the leads team adds towns: `python tools/site_factory.py` (new leads get new folders; leads that leave the list lose their site; existing links stay).
- `tests/test_public_build_privacy.py` allow_reviewed: business phone/street on `agency/f/<id>/index.html` allowed (they are the business's public OSM listing; needed for click-to-call). The publish scrub leaves them intact (checked).
- Heads-up (not mine): `site_privacy.PRIVATE_NAMES` has `leads.json`, so the public build drops `agency/leads/leads.json` (the leads page reads it). The factory pages are self-contained, so they are unaffected.
- Nothing to wire in sw.js/apps.js (the factory must stay off the Home, apps lists and the service worker).

## Add-on (lead 2026-11-20 evening)
- **Agency band** on every concept page ("Like this site for X?"): **Call us** (agency number placeholder: set `phone` in `tools/site_factory_agency.json`, rebuild) and **Have our assistant call me** = a marked slot (`<!-- CALLER-FORM-SLOT -->`, `#caller-slot`) until day-caller sends the consent form; then put its markup in `caller_html` of the same file and rebuild. Placeholders show greyed "(coming)". Maryland: the assistant only calls businesses that ask. No third-party form service, no secret (test d2).
- **`agency/sites/index.json`** = {"sites": {"<lead id>": "f/<id>/"}} (relative to agency/), for the outreach page + email autopilot. Owner-facing; nothing else links to it.
- test_site_factory 20/20 static (+ browser 1).

## Caller form wired (day-caller a25838cf)
- `caller_form()` fills each site's hidden `lead_id` + `business`; refuses a form without them. The form opens from a "Have our assistant call me" button (details/summary) inside the agency band, styled via the callme hooks. Checked at 390 px: no error, no sideways scroll.
- Stays EMPTY (greyed placeholder) until `tools/site_factory_agency.json` has `caller_html` = `python -m tools.caller.siteform --endpoint <PUBLIC>` output, which needs the PC's Funnel address (owner runs CALLER_ON.bat first). Then `python tools/site_factory.py`.
- **Blocker for the lead:** `tools/site_privacy.py` mask_net() rewrites every `<pc>.<tailnet>.ts.net` in the published site, so the form's endpoint would be masked at publish and the form would break. Needs a reviewed exception for agency/f/*/index.html's form action (and the PC renamed to a neutral name), or a different public endpoint.
- day-caller's generated text still carries placeholders ("(555) 555-0100", "YOUR AGENCY"): fill them before turning the form on.

## Claim + codes (lead 2026-11-20 17:32 ET)
- Every concept page: the offer "Starter $1,500 + $79/mo, or $149/mo with nothing upfront." + **Claim this site** (a button to `pay_url` in `tools/site_factory_agency.json` once the owner sets an https payment link; until then the line "Claim this site: call us / have our assistant call me").
- Per-lead code **FR-1 ... FR-67** ("Your code: FR-n", small, in the band), kept forever in `tools/site_factory_codes.json` (2 town letters + next number); in `agency/sites/index.json` ("codes") and the gallery for the postcards.
- test_site_factory 24/24 (with browser).

## Final for 2026-11-20 (lead decision: no PC address on public pages)
- The consent form is OFF on every concept page (code `caller_form()` kept, unused). The band is now: offer + "Claim this site" + "Call <agency number>: our AI assistant answers" (voice only, a tel: button once `phone` is set in `tools/site_factory_agency.json`; "number coming" until then) + "Your code: FR-n".
- Test d2 now fails any page with a form, `.ts.net` or a 100.x.y.z (Tailscale) address. test_site_factory 24/24 with browser.

## Saturday 2026-11-21 (resume after merging origin/pc)
| what | result |
|---|---|
| Neutral-host export | `python tools/site_factory.py --export <dir>`: standalone site (all `f/<id>/`, a neutral "Local web studio" landing, 404, robots, `_headers`, `.nojekyll`). Reads `public_base` from `tools/site_factory_agency.json`; **refuses (exit 2, writes nothing)** without it, with plain http, or with the owner's github.io / Olympus / PC address. Scans every file for Olympus / github.io / owner handle / Jarvis / ntfy / ts.net / 100.x / `../` and stops if any appear. Landing + robots stay noindex/`Disallow: /` until `agency_name` is set; concept sites always noindex. |
| Bigger lead list | Reads `agency/leads/leads.json` + `agency/leads/towns/*.json` (day-kalshi's per-town files), dedupes by id, new niches `pro` (Professional services) and `services` (Local services), `contractor` -> trades. Each site marked `ready` (phone or full street address); the gallery lists ready + non-chain first and has a **Ready to send** filter. |
| Leads today | origin/pc still has the 67 Frederick leads; the 812-lead run is not pushed yet (day-kalshi's branch only has its geocode cache). When it lands: `python tools/site_factory.py`. Of the 67: **20 ready to send** (phone or street address, not a chain). |
| Host setup | `HOST_SETUP.md`: Option A, a neutral GitHub org `<name>.github.io` (iPhone, Claude pushes updates); Option B, Cloudflare Pages upload (PC once per update). |
| Tests | test_site_factory 26/26 (new h.: 3 refusals, full export, named-agency mode). |
