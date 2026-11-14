# Monthly add-ons: Front-desk chat + Review booster (agency team B4, 2026-11-14)

Two things we can add to every client site for a monthly fee. They cost us $0 a month to run: no AI service, no SMS
service, no app, no tracking. Code: `agency/upsells/`. Test: `python -X utf8 -m tests.test_agency_upsells` (70 checks without
the browser, plus the Chromium walk). Demo on three fake businesses: `agency/upsells/demo/` (screens in `docs/shots/agency_upsells/`).

| Add-on | What the customer gets | Price (proposed) | Our cost |
|---|---|---|---|
| **Front-desk chat** | A chat bubble on their site that answers hours, prices, services, area, booking, directions and payment 24/7, has Call / Text / Book buttons, says when they open next, and takes "call me back" leads | **$39/mo** | $0 |
| **Review booster** | A QR card for the counter (A6 or business card), a "How was your visit?" page, and ready-to-send email/text wording | **$29/mo** | $0 (cards: a few cents each) |
| **Both** | | **$59/mo** | $0 |

## Owner steps
1. In the client's Google Business Profile tap **Ask for reviews**, copy the link, and send it to Claude in our chat with their hours and prices.
2. Run `python agency/upsells/make_upsells.py data/agency/clients/<id>.json --site <the client's site folder>` and deploy that folder on Netlify.
3. In Netlify, under Forms, add an email notification for form submissions once, then print the cards (`print/card-a6.html` > Print at 100%) for the client.

## Prices: what the market charges (web search, 2026-11-14)

Most of these are third-party pricing pages (the big vendors don't publish prices); treat them as asking prices.

| Product | Price | Source |
|---|---|---|
| Podium (reviews + webchat + texting) | about $399/mo (Core) to $599/mo (Pro), annual contract | [Pabau](https://pabau.com/blog/podium-pricing/), [Prospeo](https://prospeo.io/s/podium-pricing-reviews-pros-and-cons) |
| Birdeye (reviews + messaging) | $299 / $349 / $449 per location per month | [CostBench, checked against Birdeye 2026-06-05](https://costbench.com/software/review-management/birdeye/) |
| NiceJob (review requests) | $75/mo Reviews, $125/mo Pro | [WiserNotify](https://wisernotify.com/blog/nicejob-alternatives/), [Dupple](https://dupple.com/reviews/nicejob) |
| GatherUp / Reviewshake (agency review tools) | from $60/mo / $199/mo agency plan | [Toolradar](https://toolradar.com/tools/gatherup/pricing), [Reviewshake](https://reviewshake.com/platform/white-label-reputation-management) |
| Managed review service, white label | about $275/mo per location wholesale | [EmbedMyReviews](https://www.embedmyreviews.com/resources/best-white-label-reputation-management-platforms-2026/) |
| Tidio (live chat widget, DIY) | $29/mo Starter ($24.17 billed yearly) | [Capterra](https://www.capterra.com/p/144040/Tidio-Chat/pricing/) |
| Agency "chatbot add-on" tiers | $99/mo basic, $199/mo pro; managed AI bots $500-2,000/mo | [ChatMaxima](https://chatmaxima.com/blog/how-agencies-can-add-5k-mrr-with-chatbot-services/), [Vantaige](https://vantaige.io/blog/sell-ai-chatbots-local-businesses-1k-5k-retainer-2026) |

Why $39 / $29 / $59: a fraction of Podium or Birdeye ($299+), next to the cheapest DIY tools (Tidio $29, NiceJob $75), and an easy
"yes" for a barber or a plumber. We are honest that it is a smaller tool than Podium: no shared text inbox, no AI replies, no review
monitoring dashboard.

### Margin math
- **Running cost per client: $0.** Netlify's free plan serves the files; since 2026-04-14 Netlify form submissions are free on every
  plan ([Netlify changelog](https://www.netlify.com/changelog/2026-04-14-pricing-updates-april-2026/)). No AI API, no text-message
  service (texts go from the client's own phone), the QR code is made on our machine.
- **Card fees** (Stripe, about 2.9% + 30¢ per charge, [CheckoutPage](https://checkoutpage.com/blog/stripe-processing-fees)): $39 keeps $37.57;
  $29 keeps $27.86; $59 keeps $56.99 a month.
- **Our time**: about 30 minutes to set up each add-on (fill the file with the client, build, deploy, one test message), then about
  10 minutes a month (new hours, a price change). The bundle is about $228 per hour of monthly upkeep.
- **Scale**: 10 clients on the bundle = $590 a month ($570 after card fees, $6,840 a year); 25 clients = $1,475 a month.

## Front-desk chat: how it works
- **One file per client**: `chat-<id>.js` holds the widget and that client's facts. The client site gets two lines: the script tag
  and a hidden form (Netlify must see the form once in the page's HTML; a form that only JavaScript draws is not detected,
  [Netlify docs](https://docs.netlify.com/manage/forms/setup)). `make_chat.py --site` adds both to every page of a site folder.
- **Answers only from the client file.** Three trade presets with tested default FAQs: barber (walk-ins, how long, kids, cancel,
  barber choice, gift cards, products, discounts, hair types), plumber/HVAC (emergency shut-off advice, gas safety, estimates,
  licence, warranty, financing, tune-ups, brands, how soon), restaurant (menu, reservations, takeout, delivery, allergies and diets,
  kids, happy hour, events, wait, patio and dogs, dress code). A preset answer that needs a fact the file doesn't have (a licence
  number, a warranty, delivery) is left out and listed under "check with the client": the chat never claims what it wasn't told.
  A starter file (`make_chat.py --new barber <id> "Name"`) marks every sample hour and price FILL, and nothing builds until they're replaced.
- **Matching without AI**: words are normalised and stemmed (hours/hour, booking/book, walk-ins/walkin), small typos are caught
  (apointment, resturant), phrases score higher than single words, and two questions in one message get two answers. A question it
  can't place gets "not sure" + suggested questions + Call / Text / Leave my number, never a guess. 48/48 sample questions pass.
- **Hours in the shop's own time zone** (a visitor in Tokyo sees Tampa's hours), holidays from `closed_dates`, past-midnight
  hours (5 pm-2 am), "open now until 5 pm" / "Closed · opens Tue 9 am" in the header, and an after-hours greeting.
- **Leads**: name + phone + what they need (prefilled with their question), sent as a form post to the site's own Netlify form
  with a honeypot. It is the only request the widget ever makes (the test watches every request).
- **Phone first**: full screen on phones, sized to the visible screen above the keyboard, 16 px inputs (no iPhone zoom), 44 px
  targets, safe-area insets, reduced motion respected, Escape closes, screen-reader labels and a live log. In a shadow root, so the
  client's CSS and ours can't clash. Brand colour in, readable text colour worked out (WCAG AA).
- **Size**: the shipped files are 24.0-24.8 KB for the three demos (10.5-10.8 KB as Netlify sends them, gzipped); the runtime
  alone is 18.9 KB. If a client's facts would push the file past 25,000 bytes, the build leaves out the last optional FAQs and says
  which; quick-button answers are never dropped.

## Review booster: how it works, and why it is allowed
- **The QR card** (made by our own QR code maker, error correction level Q, checked by the test with an independent decoder) opens
  `<site>/review/`: "How was your visit?" with five big stars.
- **4-5 stars** go straight to the Google review link. **1-3 stars** see "Post a Google review" first and, as an extra, "tell the
  owner privately" (a Netlify form). **Everyone** can reach Google at all times: the link is on the page before rating, after
  any rating and after a private message; "Message the owner privately" works without rating at all. With JavaScript off, both
  are still there. The page says before the tap what 4-5 stars do.
- **Why**: Google's Maps fake-engagement policy prohibits businesses from "discouraging or prohibiting negative reviews, or
  selectively soliciting positive reviews from customers" (Google's own report form, [support.google.com/maps/contact/14718793](https://support.google.com/maps/contact/14718793?hl=en);
  added to the contributor guidelines in October 2022, [Search Engine Roundtable](https://www.seroundtable.com/google-review-guidelines-update-34201.html);
  current policy [support.google.com/contributionpolicy/answer/7422880](https://support.google.com/contributionpolicy/answer/7422880)).
  In the US the FTC's rule on consumer reviews (16 CFR Part 465, in force since 2024-10-21, civil penalties up to $51,744 per
  violation, [FTC final rule](https://www.ftc.gov/system/files/ftc_gov/pdf/r311003consumerreviewstestimonialsfinalrulefrn.pdf))
  bans fake reviews and review suppression, and the FTC's 2023 Endorsement Guides added an example on "review gating", asking
  for feedback and inviting only the happy customers to post (summaries: [InfoLawGroup](https://www.infolawgroup.com/insights/2023/7/31/ftc-releases-updated-endorsement-guides-10-key-takeaways), [Venable](https://www.venable.com/insights/blogs/2023/07/ftc-finalizes-updated-endorsement-and-testimonial)).
  So: no customer is filtered, nothing is offered for a review, and nothing asks for a "5-star" review (the build refuses
  such wording on the page and the cards, and the test checks the messages too).
- **Strict mode** for a client who wants no difference at all by rating: `"review": {"same_for_all": true}` gives every rating
  the same two choices and never redirects by itself.
- **Print**: `print/card-a6.html` (A6 counter card), `print/card-business.html` (3.5 x 2 in, front + back), `print/cards-letter-10.html`
  (10 cards on US Letter, Avery 8371 / 5371 layout), `print/qr-<id>.svg` (vector, any print shop). Print at 100% (Actual size).
  The test prints them to PDF and checks the page sizes.
- **Asking** (`print/requests.txt`): what to say at the counter, one email (with the mailing address and an unsubscribe line,
  the CAN-SPAM basics) and one text. **Texts only to customers who said yes**, one per visit, 8 am-9 pm, ending "Reply STOP to
  opt out"; a reply like stop / quit / cancel / unsubscribe counts as opting out ([Carlton Fields on the FCC opt-out rules](https://www.carltonfields.com/insights/publications/2025/mastering-the-new-tcpa-opt-out-regulations)).
  Ask every customer the same way. Not legal advice.
- **Getting the Google link**: Business Profile > "Ask for reviews" gives `https://g.page/r/.../review`, or build it from a Place ID:
  `https://search.google.com/local/writereview?placeid=<id>` ([ReviewTrackers](https://www.reviewtrackers.com/?p=22793),
  [Google: tips to get more reviews](https://support.google.com/business/answer/7035772)). The build refuses any non-Google link.

## The client file (fields the add-ons read)
The agency's shared client record (`id, name, trade, city, phone, email, site_url, demo_url, status, package, setup_usd,
monthly_usd, notes`) plus two sections. Real files live in `data/agency/clients/` (keep them out of git); the fake ones in
`agency/upsells/fixtures/` are full examples.

| Field | Example | Notes |
|---|---|---|
| `chat.preset` | `barber` / `plumber_hvac` / `restaurant` | else picked from `trade` |
| `chat.brand_color`, `chat.timezone` | `#0f766e`, `America/New_York` | |
| `chat.hours` | `{"weekdays": "7:30-18:00", "sat": "8-14", "sun": "closed"}` | also `9-5`, `9am-7pm`, `11-14, 17-22`, `18:00-02:00`, `24h` |
| `chat.closed_dates` | `{"2026-12-25": "Christmas Day"}` | |
| `chat.services` | `[{"name": "Skin fade", "price": "$35", "time": "45 min", "keys": ["fade"]}]` | |
| `chat.booking_url`, `booking_label`, `address`, `maps_url`, `directions`, `menu_url` | | links must be https:// |
| `chat.area` | `{"text": "Brandon and Tampa", "towns": [...], "zips": [...]}` | trades that come to you |
| `chat.payments`, `chat.prices_note` | `["cash", "all major cards"]` | |
| `chat.text_phone`, `chat.emergency_phone` | `""` hides the Text button (landline) | |
| `chat.facts` | `{"license": "Yes: licensed (FL #...) and insured."}` | fills the preset answers ({tokens}) |
| `chat.answers`, `chat.faqs`, `chat.off`, `chat.chips` | | change a preset answer, add own FAQs, turn some off, pick the quick buttons |
| `chat.form_name`, `chat.form_action` | `frontdesk-chat`, `/` | a full URL posts to another Netlify site (untested) |
| `review.google_review_url` or `review.place_id` | `https://g.page/r/.../review` | required |
| `review.page_url`, `owner_name`, `form_name`, `same_for_all` | | page defaults to `<site_url>/review/` |

## Commands (for Claude and the lead)
| Command | Does |
|---|---|
| `python agency/upsells/make_upsells.py <client.json> [--site DIR]` | both add-ons, prints what to deploy, print and check |
| `python agency/upsells/make_chat.py <client.json> [--site DIR] [--out DIR]` | the chat: `chat-<id>.js`, `-form.html`, `-preview.html` (every answer, to read with the client), `-install.txt` |
| `python agency/upsells/make_chat.py --new <preset> <id> "Name"` | a starter client file in `data/agency/clients/` (FILL marks) |
| `python agency/upsells/make_review.py <client.json> [--site DIR]` | `review/index.html`, `print/` (QR, cards, requests.txt) |
| `python agency/upsells/build_demos.py [--check]` | rebuilds `agency/upsells/demo/` (fake clients) |
| `python agency/upsells/build_widget.py [--check]` | after editing `chat/widget.js`: re-minifies it into `chat/widget.min.js` (needs Node; terser 5.39.0 via npx) |
| `python -X utf8 -m tests.test_agency_upsells [--no-browser] [--shots]` | the test (browser part under `flock -w 2400 /tmp/olympus_browser.lock`) |

## Honest limits
- **Keyword matching, not AI.** It knows what the client file says and nothing else; English only. Real customers will phrase
  things we didn't foresee: read the "chat" field of the leads each month and add keys or FAQs.
- **Leads need the site on Netlify** (the hidden form must be in the deployed HTML). A full-URL `form_action` to another Netlify
  site is written but untested. Netlify itself could not be reached from here: send one real test lead after every first deploy.
- **Tested in Chromium (phone size), not on a real iPhone.** The code keeps to iPhone Safari 12+ syntax; do one real-phone check
  before the first sale.
- **No statistics by design**: no scan or chat counting. The leads and private messages in Netlify are the record (B5 can count them).
- **Texts and emails are sent by hand** (that's what keeps it at $0); bulk texting through a service would need 10DLC registration.
- **Netlify's free plan has a hard cap of 300 credits a month for the whole account**; when it runs out, every site pauses,
  forms included ([netli.fyi](https://netli.fyi/blog/netlify-free-plan-limits-2026)). The add-ons add almost nothing to it,
  but many client sites on one free account will need watching.
- **Google's wording on review gating has moved over time** (a 2022 report says a line was dropped from one page, while Google's
  report form still lists it); we follow the stricter reading. Not legal advice.
- **Size headroom is small** for data-heavy clients (the plumber demo is 24.8 KB of 25): the build then leaves optional FAQs out and says so.

## Wiring needed (the lead)
- `.gitignore`: add `data/agency/` (real client files and builds are written there by default; not ignored in this base).
- `docs/CLAUDE_REFERENCE.md` "One chat": a row `Agency add-ons | agency/upsells/ | make_upsells.py <client> --site <site>, deploy on Netlify | tests.test_agency_upsells`.
- `tests/run_area.py`: an `agency` area with `agency_upsells` (and the other agency teams' suites).
- B1 (demo sites / CRM): call `make_upsells.py --site` on a client's site folder; record the add-ons in `package` / `monthly_usd`.
- B3 (storefront): link the demo (`agency/upsells/demo/`, publish the folder) and the three prices.
- B5 (reports): count each client's Netlify submissions of `frontdesk-chat` (leads) and `review-feedback` (private messages).
- B6 (billing): line items Front-desk chat $39/mo, Review booster $29/mo, both $59/mo.
