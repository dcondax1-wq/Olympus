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
