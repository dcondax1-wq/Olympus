# web / SHOWCASE: the owner's own agency website (2026-11-20, branch day-cities3 — this session may push only there)

`tools/web_public/agency/showcase/` = the page a prospect sees. Open: `agency/showcase/` (phone first, 390 x 844).

## What it is
- **Hero:** "Websites that win local customers, live in 7 days." + two buttons (free mockup / prices) + a **small glowing 3D night city**:
  one tower per demo (8: restaurant, salon, plumber/HVAC, dentist, gym, real estate, landscaping, auto), each in its colour with a floating
  name; a tap on a tower or its name opens that demo (`../demos/#<slug>`). Filler blocks = one InstancedMesh; three.js r160 from the site.
- **Prices (from the research offers.json, Nov 20):** Starter site $1,500 + $79/mo care; Call engine (site + Google profile + review requests + every review answered) $500 setup + $299/mo, "most picked"; 3D Signature (3D tour or 3D product pages) from $2,500 + $79/mo. Each card's button picks that plan in the form.
- **What you get in 7 days:** six plain steps. **Results:** 3 case-study placeholders (each links a demo). **Questions:** 4 FAQs.
- **Contact form, no backend:** name, business, type, plan, what you need -> "Send by email" opens the phone's mail app (mailto: with subject +
  body filled), "Send by text" opens Messages (sms: body=...). Nothing is stored or sent by the page. Missing name -> a plain prompt.
- **One file to change the brand:** `agency/showcase/brand.json` (name, tagline, area, city/region, phone, SMS, email, site URL, hours, accent
  colour, offers + prices, the 7-day plan, case studies, demos). Placeholders only: "Your Studio", hello@example.com, +1-555-0100.
- **Local SEO:** LocalBusiness JSON-LD (name, phone, email, address, areaServed, openingHours, priceRange, 3 Offers in USD), kept in step with
  brand.json; canonical link; title + description. **Share card:** og:title / description / image (og.jpg 1200 x 630, rendered from the page), Twitter large card.
- **Phone details:** sticky Call / Free mockup bar (hides while the form is on screen), 44 px taps, 15 px+ text, light + dark, skip link, focus ring.

## Speed (phone profile, 4x CPU, 390 x 844)
First contentful paint **152 ms** (budget 1.5 s); layout shift **0.000** with the 3D on (budget 0.05). The words, prices and form are plain HTML;
brand.json repeats the same defaults (no jump); the 3D is a dynamic import after `load` + idle, never under reduced motion, data saver / 2G-3G,
< 3 GB memory or no WebGL (a drawn SVG skyline stays). Pixel ratio <= 1.75, ~40 fps cap, sleeps off screen and in a hidden tab.

## Tests
`python -X utf8 -m tests.test_web_showcase` = **23/23** (static: files, brand.json, content-first, share card 1200 x 630, JSON-LD, no backend,
stores nothing, text only, 3D rules; browser: brand applied incl. JSON-LD, demo list, mailto / sms messages, missing name, 44 px taps, no sideways
scroll, 3D live, no console error / nothing off the site; 4x CPU FCP + CLS; reduced motion = still, three.js never fetched). Added to
`tests/run_area.py` AREAS["agency"].

## Files
index.html, showcase.js, city.js, brand.json, og.jpg, icon.svg. Shots: showcase-1-hero-dark/light, -2-prices, -3-week, -4-contact; video showcase.webm.
- Agency HQ tile: `agency/showcase/summary.json` = {"n": 3, "label": "offers on your website", "next": "Put your name, phone and email in brand.json", "t": ...}.
