# Agency content: social posts + monthly client report

Two tools in `agency/content/` that turn each website client into a monthly subscriber, at **$0 cost to make**:

| What | Result |
|---|---|
| Social post machine (`make_posts.py`) | A month of posts per client: 12-20 posts, each with a caption, hashtags, a best time, a square image (1080 x 1080) and a story image (1080 x 1920) drawn from code. 8 trade packs, 11 designs, US holidays, local + weather angle. |
| Monthly report (`client_report.py`) | One good-looking page per client per month (PDF + HTML) and the email to send with it: what we did, website check, form leads, Google reviews, next month's plan, one suggestion. |
| Your time | About 30 min per client per month on Basic, about 50 on Pro (most of it is scheduling in Meta, see below). |
| What it costs | $0: no stock photos, no AI image service, no paid scheduler. Fonts are free (SIL Open Font License). |

Screenshots: `docs/shots/agency_content/` (contact sheet and report on a phone and a desktop, the client preview, sample posts).

## Your 3 steps each month

1. **On the 25th:** double-click `agency\content\MAKE_POSTS.bat`, then text each client its `contact_sheet.png` and `client_message.txt` (the questions it needs answered, e.g. "Do you sell gift cards?").
2. **On the 1st, after their YES:** open the client's `contact_sheet.html`, and in Meta Business Suite > Planner schedule each post: Copy caption, paste, add the square image, set the time shown (stories the same way).
3. **On the 1st:** double-click `agency\content\CLIENT_REPORT.bat` (it asks for the review counts and the form export), then email the client `report.pdf` with the text from `email.txt`.

## Price and time per client

| Package | Price | What the client gets | Your time a month |
|---|---|---|---|
| Social Basic | **$149/mo** | 12 posts + 12 stories, written for their trade and town, approved by them, scheduled | about 30 min (5 min to make and send for OK, about 2 min a post and story in Meta) |
| Social Pro | **$299/mo** | 20 posts + 20 stories, review shout-outs, seasonal offers, the monthly report | about 50 min (+5 min for the report) |
| Report alone | add to any website plan | the monthly one-pager | about 5 min |

The tool picks the post count from the client's `package` field ("Basic" -> 12, "Pro" -> 20, anything else 16); `--posts N` overrides (12-20).

## What a month contains

`data/agency/content/<client>/<YYYY-MM>/` (gitignored: the tool also writes a `.gitignore` there so real client work never reaches git):

| File | What it is for |
|---|---|
| `posts/NN_<date>_square.png`, `_story.png` | The images (1080 x 1080 feed, 1080 x 1920 story) |
| `contact_sheet.html` | Your working page: the month calendar, the questions for the client, every post with its images, date, time, caption, hashtags, a **Copy caption** button (44 px) and a **Scheduled** tick (remembered in that browser). Works offline, phone and desktop. |
| `contact_sheet.png` | The preview picture you send the client for their OK |
| `client_message.txt` | The approval text: what the month covers, every yes/no question, the posts that would look better with a real photo |
| `posts.csv` | The schedule sheet (Excel / Google Sheets; UTF-8 with BOM so emoji show) |
| `captions.txt` | All captions in order with date, time and image name: easy to copy from a phone |
| `posts.json`, `HOW_TO_POST.txt` | Machine-readable plan (the report reads it) and the 3 steps |

**How the words are written.** Each post is one of: holiday (only the holidays of that month, the heaviest first, about 3 in 10 posts),
season (the client's climate from the state in `city`: a Tampa plumber is never told about snow), tip, service spotlight, offer, behind
the scenes, meet the team, review ask, FAQ, local love, conversation starter, booking reminder, checklist. Captions open with a hook,
carry a local angle and end with the client's own call to action (site and/or phone). Six hashtags: 2 local (#AustinBarber, #AustinTX),
2 trade, 1 topic or holiday, 1 general. Posting times are per trade (e.g. barbers Tue-Fri 11:30 am, Thu 5:30 pm, Sat 8:30 am; gyms 6 am
and 5 pm). After a month, look at the page's Insights and move the times toward the hours that got the most reach.

**Honesty rules built in** (tested): nothing invented about the business (no prices, hours, years, star counts); any post that assumes a
service (gift cards, catering, discounts, free tests, warranties) carries a yes/no question that lands in `client_message.txt` and on
the contact sheet; review posts never quote a customer unless you give real reviews (`--reviews FILE`, one per line `text | name`, or
`"reviews"` in the client record; names are cut to first name + initial); respect days (MLK, Memorial Day, Juneteenth, Veterans Day)
never sell; behind-the-scenes posts say which real photo would beat the graphic.

**No repeats.** Consecutive months never share a caption (tested over 12 months for every trade); only the November / December
gift-card offer runs twice, with different words. The packs hold about 70 lines per trade, so content cycles after a few months on the
20-post plan; add lines to `agency/content/packs.py` to stretch it.

**Trade packs** (`packs.py`): barber, salon, restaurant, plumber / HVAC (plumbing-only and HVAC-only clients get only their tips),
landscaper, auto repair, gym, dentist. Each: 3 colour palettes (one is picked per client; `--colors "#hex,#hex"` or `"brand_colors"`
uses the client's own), its fonts, icons and background motif. **Designs** (`designs.py`): 11 layouts (bold, split, tip, quote, offer,
holiday, date, checklist, Q&A, polaroid frame, minimal), each month uses 6 or more. A trade the tool has no pack for is refused with
the list of packs, never given the wrong one.

## Meta Business Suite: is there a free CSV import? (checked 2026-11-14)

**No documented one.** Meta's help center documents scheduling page posts and stories one at a time in the Planner / calendar, on
desktop and in the mobile app ([calendar][m1], [save and schedule posts][m2], [mobile app][m3]), and bulk upload of *media* into
File Manager ([File Manager][m4]). Meta's documented CSV / spreadsheet imports are for ads, catalogs and leads ([ads bulk import][m5],
[catalog feed template][m6]), not for organic posts. Third-party guides disagree: one describes a 25-post CSV upload in Business Suite
with images given as web links and no stories ([SocialRails][t1]); others say Business Suite has no bulk CSV import and each post is
scheduled by hand ([Kompozy][t2], [SocialBu][t3]). Instagram posts and stories can be scheduled about 30 days ahead without a paid
Meta One plan ([Meta One help][m7], [stories][m8]), which is why scheduling is on the 1st.

**So the fastest free path is manual, with everything pre-made:** drag all of the month's images into Business Suite once, then for
each post on the contact sheet: Planner > the day > Schedule post > pick the image > Copy caption on the sheet > paste > tick
Facebook and Instagram > time > Schedule (about a minute each; a story about 30 seconds). If your Business Suite ever shows a
"Bulk upload" / "Create multiple posts" option, `posts.csv` already holds the date, time, caption with hashtags and image name for
each row; that option (per the guide above) wants image web links, which these local images are not.

`posts.csv` columns: `post, date, time, weekday, platforms, kind, layout, caption, hashtags, caption_with_hashtags, square_image,
story_image, alt_text, check_with_client, photo_idea`.

[m1]: https://www.facebook.com/business/help/1170295510042639
[m2]: https://www.facebook.com/business/help/2223502627919449
[m3]: https://www.facebook.com/business/help/609176706604372
[m4]: https://www.facebook.com/business/help/4385385538174614
[m5]: https://www.facebook.com/business/help/1454442884773208
[m6]: https://www.facebook.com/business/help/1898524300466211
[m7]: https://www.meta.com/help/subscriptions/1931535524918664/
[m8]: https://www.meta.com/help/subscriptions/1066097999375427/
[t1]: https://socialrails.com/blog/bulk-social-media-scheduling-guide
[t2]: https://kompozy.io/how-to/bulk-upload-scheduled-social-posts
[t3]: https://socialbu.com/blog/bulk-schedule-facebook-posts

## The monthly report

`data/agency/reports/<client>/<YYYY-MM>/report.html` (print or save as PDF), `report.pdf` (when a browser is there), `email.txt`.

| Box | Where the number comes from |
|---|---|
| Website leads | The form export CSV you download from the site's form tool (Netlify, Formspree, Google Forms, Tally, Jotform...). The date column is found by its name; rows marked spam and the same person twice on one day are left out; shown with last month and by week. |
| Website | A live check when the report is made: up or down, how fast it answered, https or not. With `--uptime 99.98` it shows the month's % from a free monitor (e.g. UptimeRobot) instead. `--offline` skips it ("check skipped", never a made-up result). |
| Google reviews | The two counts you type (now and a month ago) and the rating. |
| Social posts | The month's `posts.json` from the post machine. |
| Next month | Next month's plan (its holidays and post count) + your `--plan` lines. |
| Our suggestion | One, from the numbers (`agency/content/offers.json`): no social package -> Social Basic; under 4 new reviews -> review booster; 8+ leads -> website chat; Basic -> Pro; nothing left -> none. Prices not set in `offers.json` print "Ask us". |

The page is one Letter page in print (tested), readable on a phone, and loads nothing from the internet (fonts inside, the chart is
inline SVG). Your agency name, email and phone come from `--agency-name` or `data/agency/agency.json` (`{"name","email","phone","site"}`).

## Commands (for the lead chat)

```
python -X utf8 agency/content/make_posts.py agency/content/fixtures/client_barber.json --month 2026-12        # one client file
python -X utf8 agency/content/make_posts.py data/agency/clients.json --all --month next                      # every paying client
python -X utf8 agency/content/client_report.py data/agency/clients.json --id fade-co --month last --leads form.csv --reviews 47 --reviews-before 41
python -X utf8 -m tests.test_agency_content --no-browser                                                      # parts a-e, about 1 min
flock -w 2400 /tmp/olympus_browser.lock python -X utf8 -m tests.test_agency_content                           # + part f (Chromium)
flock -w 2400 /tmp/olympus_browser.lock python -X utf8 agency/content/shots.py                                # refresh docs/shots/agency_content/
```

The client record is the shared one (`id, name, trade, city, phone, email, site_url, demo_url, status, package, setup_usd, monthly_usd,
notes`); the file can hold one record, a list, or `{"clients": [...]}`. `--all` takes the paying statuses (active, client, won,
paying, live, signed, customer). Optional extras it reads: `brand_colors`, `reviews`.

**Images on the owner's PC:** no install needed. Without Playwright the tool drives Microsoft Edge (or Chrome) in headless mode
with its own `--screenshot` (tested here with the same Chromium); with Playwright it uses that. With no browser at all it keeps the
HTML of each image (open and screenshot by hand) and says so.

## Honest limits

- Meta has no documented free bulk import, so scheduling stays manual (about 1 minute a post). That is most of the monthly time.
- The images are typographic graphics, not photos. They look professional, but real photos of the business do better: the
  approval message asks the client for the 1-3 photos that would help most.
- Holidays and observances are US. Hanukkah follows a checked table (2025-2028) and is skipped after that; the rest is computed.
- Posting times are sensible starting points per trade, not measured for each client: adjust after a month of Insights.
- The website check is one check at report time unless you pass a monitor's monthly `--uptime`.
- Lead counts are only as good as the form export: phone calls and walk-ins are not in it.
- The words are good, general and honest; they do not know the business's own story. A line or two from the client (`--reviews`,
  the questions) makes them better.

## Files

`agency/content/`: `make_posts.py` (CLI, planner, captions, outputs), `packs.py` (8 trade packs + shared words), `seasons.py` (US
holidays, seasons, climate zones), `designs.py` (11 layouts, icons, motifs, palettes), `sheet.py` (contact sheet + preview),
`render.py` (Playwright or the browser's own headless mode), `client_report.py`, `offers.json`, `shots.py`, `MAKE_POSTS.bat`,
`CLIENT_REPORT.bat`, `fonts/` (OFL fonts + licences), `fixtures/` (fictional clients with 555-01xx numbers and `.example` sites,
a demo form export). Tests: `tests/test_agency_content.py`.
