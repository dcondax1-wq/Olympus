# Agency storefront: your agency's own website + the free Website Grader (2026-11-14)

The website prospects open when you call them: what you do, before/after examples, your three plans and prices, a FAQ,
a free-demo request form, tap-to-call, and a free **Website Grader** that turns visitors into leads. It is plain static
files (no CDN, no tracking, no secrets), so it hosts free on Netlify by dropping one zip.

## Your 3 steps (on the PC)

1. Put your agency name, city, phone, email and prices in `agency/config.json` (the same file the pitches and demo sites use), save, and run:
   `python agency/storefront/build.py`
2. Open app.netlify.com/drop, sign up free, and drop the `agency/storefront/dist/site` folder on it. In the new site open
   **Forms**, click **Enable form detection**, add an **email notification** to your email, then drop the folder once more on the **Deploys** page.
3. Later, when you buy a domain: Netlify **Domain management** > **Add a domain** (the padlock is free).

## What you get

| What | Result |
|---|---|
| Home page | "Websites that make your phone ring." Before/after of 3 example sites, what's included, how it works, plans, FAQ, a big free-demo button |
| Example work | 3 polished demo sites you can open and show: a barbershop, a plumber, a restaurant (made-up businesses, clearly marked) |
| Pricing | Starter $499 + $49/mo, Growth $999 + $79/mo, Pro $1,999 + $129/mo (placeholders: change them in the one config file) |
| Add-ons | Review booster, website chat, Google profile tune-up, extra edits, business email, logo (each says which plan includes it) |
| Contact | Free-demo form (lands in Netlify, emailed to you), tap-to-call, text, email, a booking link once you add one |
| Free Website Grader | A 2-minute self-check (10 questions, instant score + top 3 fixes), then "email me my full report": a lead with their website |
| Real grader for you | `grade.py` checks their site for real and writes a one-page report with your name and prices on it |
| Speed | Every page under 100 KB (plus the example pictures); the demos under 60 KB |
| Colours | 3 presets (coral, ocean, forest) or any colour you like; preview a preset by adding `?preset=ocean` to a page address |
| Legal | Privacy and terms pages, plain templates, marked "edit before going live" until you set `legal_reviewed` to true |

## When someone asks for a free report

Netlify emails you their website. Run one line, then email them the PDF:

`python agency/storefront/grade.py theirsite.com --name "Their Business" --pdf --open`

The report shows a score out of 100, a grade, their top 3 fixes in plain words, everything checked, and which of your plans
fixes it. It also works on a whole list: `--batch data/agency/clients.json` (the shared client records; a client with no
website is marked "a perfect lead for a free demo").

## Honest limits

- The Grader page on the site is a **self-check quiz**: a browser is not allowed to open another website (a privacy rule), so the real scan is `grade.py` on your PC.
- `grade.py` measures from your PC, not from the customer's phone: its speed numbers are a guide. For Google's own lab test, use pagespeed.web.dev.
- It visits only the home page, once: about 27 requests at most (the page, a HEAD for up to 25 of its files, one HEAD of the http:// address).
- Netlify Free (netlify.com/pricing as read by the agency team on 2026-11-14, and a web search): 300 credits a month; each new drop costs 15 (so about 20 drops a month), bandwidth 20 credits per GB, form submissions free on the credit plans (older free accounts: 100 a month); at zero credits every site pauses until next month. So batch your changes into one drop.
- Form detection is off by default on new Netlify sites, which is why step 2 turns it on and drops the site again.
- Step 2 drops the **folder**: Netlify's guide (read by the agency team on 2026-11-14) says a zip must be unzipped first, while its knowledge base says Drop takes a zip too. The build also writes `dist/storefront.zip` (Cloudflare Pages takes a zip, and so may Netlify).
- Build on the PC, not in a copy you edit on GitHub: the build output and `agency/config.json` stay out of git on purpose, so the trading bot's auto-update is never blocked by a changed file.
- No reviews are made up: the reviews section stays hidden until you add real ones (with the customer's OK) in `testimonials`. The demo sites say "Sample review".
- The privacy and terms pages are templates, not legal advice.
- The example screenshots were taken in a Linux browser (Inter font), so on an iPhone the live demos look slightly different (Apple's own fonts).

---

## For Claude / the lead (detail)

### Files (`agency/storefront/`, team B3)

| File | What it is |
|---|---|
| `config.json` | The storefront's words and fallbacks (tracked: Claude edits it in the chat, never the PC). Top-level shared keys `agency_name`, `city`, `phone`, `email`, `brand_color` (+ owner_name, state, service_area, hours, texts_ok, booking_url, site_url, legal_name, founded, legal_reviewed), then `offer`, `packages` (3), `addons`, `faq`, `testimonials`. Text may use `{city}`, `{agency}`, `{from_setup}`, `{from_monthly}`, `{demo_days}`, `{launch_days}`, `{reply_time}`, `{phone}`, `{email}`, `{service_area}`; `*word*` in the headline is the serif accent. |
| `build.py` | config + `src/` + `examples/` -> `dist/site/` + `dist/storefront.zip` (both gitignored, deterministic, index.html at the root). The first build on the PC makes `agency/config.json` from team B1's example when git ignores that path. `--serve` previews on http://localhost:8790 (form posts print to the console and land on thanks.html), `--check` says whether the config builds (writes nothing), `--preset`, `--out DIR`. Standard library only. Stops with a plain message (line number for a JSON typo). |
| `src/pages/*.html`, `src/partials/*.html` | The page templates: `{{x}}` escaped, `{{{x}}}` raw (blocks built in build.py), `{{> partial}}`. Each page starts with `<!--page {"title", "description", "nav"} -->`. |
| `src/assets/site.css`, `site.js` | One stylesheet (the three `[data-preset]` palettes live only here; `build.css_presets()` reads them), one small script (menu, `?preset=`, `?plan=`, the self-check scoring, one-tap send). Both fingerprinted at build (`site.<hash>.css`), CSS minified. |
| `src/quiz.json` | The 10 self-check questions (weights add up to 100, "not sure" counts half). |
| `src/_headers` | Netlify headers: strict CSP (only the site's own files, `form-action 'self'`, no framing), nosniff, referrer policy, a year of cache for `/assets/*`. |
| `src/img/ex/*.webp`, `src/img/og-*.png` | The example screenshots (phone after / before, desktop) and one share picture per preset. Made by `shots.py`; they never show the agency name, so a new name needs no new pictures. |
| `examples/` | `examples.json` (the three fictional businesses in the shared client record shape + before/after notes), `barber/`, `plumber/`, `restaurant/` (each `index.html` + `style.css`), `demo.js` (open-now badge, demo forms that send nothing, `?shot` screenshot mode, `?now=` clock). |
| `mockups/` | The made-up "before" pages (desktop-only, dated), used only for the before screenshots, never deployed. |
| `grade.py` | The real grader (below). |
| `shots.py` | `flock -w 2400 /tmp/olympus_browser.lock python agency/storefront/shots.py [--examples|--review]`: example pictures + share pictures, and the review shots in `docs/shots/agency_storefront/`. Rerun `--examples` only when a demo site changes, then `build.py`. |
| `fixtures/grade/` | Offline pages for the grader tests (healthy, dated, noindex, hostile). |

### The shared agency file (one edit for the storefront, the pitches and the demo sites)

Team B1 keeps the owner's details in `agency/config.json` (made from the committed `agency/config.example.json`, gitignored,
PC only) in a nested format: `agency.name`, `agency.your_name`, `agency.phone`, `agency.email`, `agency.website`,
`search.city`, `packages[].id/name/setup/monthly/includes`. `build.load_config()` reads that format and the flat names the
lead asked for (`agency_name`, `city`, `phone`, `email`, `brand_color`/`brand_colour`, at the top level or under `agency`).
For each shared value the first REAL value wins: `agency/config.json` > `agency/storefront/config.json` >
`agency/config.example.json`; a placeholder (YOUR ..., a 555-01xx number, an example email) never hides a real value. Plans
come from the owner's copy (else B1's example): names, prices and the `includes` bullets as they are (the storefront then
drops its own page / edit lines so nothing contradicts the pitch); a plan removed there drops out here. A `"storefront": {}`
block in the owner's copy overrides any storefront key (`booking_url`, `legal_reviewed`, `offer`, ...). The state is taken
from "City, ST" when it is still a placeholder; a bare `youragency.com` website becomes `https://youragency.com`.
`brand_color` is a preset name or any `#RRGGBB`: a custom colour gets computed shades (button text, hover, link text, tint,
on-dark) that all pass WCAG AA, layered on the nearest preset's background tints (class `brand-custom` on `<html>`,
appended to the stylesheet; no inline style, CSP-safe).

### grade.py

`python agency/storefront/grade.py URL [--name] [--city] [--pdf] [--open] [--page-only] [--out DIR]`, or `--batch FILE`
(JSON list / `{"clients": [...]}` of shared client records, or one address per line). Writes
`data/agency/reports/<date>-<host>.html` + `.json` (the folder writes its own `.gitignore` with `*`), plus `.pdf` with
`--pdf` (headless Edge / Chrome / Chromium, one Letter page) and `grades.json` for a batch. Exit 0 graded, 2 the site did
not open (an honest report is still written), 3 bad input. 14 weighted checks (100 points): padlock 14, phone layout 14,
tap-to-call 14, speed 10, weight 8, call/book/quote button 8, Google profile link 8, title 7, description 5, allowed on
Google 4 (a `noindex` is always fix number 1), H1 3, schema 2, up to date 2, alt text 1. Grades A 90+, B 75+, C 60+,
D 45+, F. Hostile page text is escaped. Library use: `grade.grade_offline(html, url)`, `grade.grade_url(url, out_dir)`.

### Tests

`python -X utf8 -m tests.test_agency_storefront` (a: static + build + zip, b: grader offline and against local servers,
c: Chromium, under `flock -w 2400 /tmp/olympus_browser.lock`; `AS_NO_BROWSER=1` skips c). No internet needed.

### Wiring needed (the lead)

- `tests/run_gate.py`: the suite is not named `test_*_page.py`, so add `"agency_storefront"` to `KNOWN_APPS` (or an `add(...)` line) if it should be in the release gate.
- `docs/CLAUDE_REFERENCE.md` "One chat" table: a row for the agency storefront (files above, ships as a zip on Netlify Drop, not via the OLYMPUS site build).
- B1's `agency/config.json` + `config.example.json` are read automatically (tested with B1's example format); nothing to change when merging. B1's `.gitignore` entry for `agency/config.json` is what lets the first build make the owner's copy.
- Optional: publish `dist/storefront.zip` on the OLYMPUS site (for example next to B1's CRM page) so the owner can download it on the iPhone; that needs `build_web_dashboard.py`, which is yours.
- Not an OLYMPUS app: no `apps.js`, `olympus.js`, `sw.js` or `build_web_dashboard.py` change.
