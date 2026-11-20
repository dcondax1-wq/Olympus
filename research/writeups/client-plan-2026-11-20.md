---
title: How we get website clients without cold calls (the Website Factory plan)
family: money
date: 2026-11-20
status: plan; building tonight; owner yes needed for anything that costs money or goes out in his name
summary: Owner 17:35 ET "what's our best way to get clients if cold calling is illegal? plan everything out". Answer - mail every business a personal postcard with a QR code to the website we ALREADY built for it; their site then lets them ask our AI to call them, claim the site with a payment link, or call our AI receptionist. Legal, about $1 a card, nearly zero owner time.
---

# How we get clients (owner-plain, $ first)

**The one-line answer:** mail every business a postcard that says "*<Business>*, your new website is already built - scan to see it". The QR code opens the site we built for them. On that site they can (1) tap **"Have our assistant call me"** (that tap is their consent, so the AI may call), (2) tap **"Claim this site"** and pay, or (3) call our number, where the AI receptionist answers. You never dial anyone.

## Channels, best first

| # | Channel | Legal? | Your time | Cost | Why |
|---|---|---|---|---|---|
| 1 | **Personal postcard + QR to their finished site** (printed and mailed by a print-and-mail service through its API) | Yes: mail needs no consent | 0 | ~$1 a card | They see their OWN site. Nobody else shows up with the product already built |
| 2 | **Their site's buttons**: "Have our assistant call me" / "Claim this site" / call us | Yes: they ask first | 0 | ~12 cents a talk-minute (only when they ask) | Turns a scan into a sale without you |
| 3 | **Email autopilot** (only where a business email is public; OpenStreetMap rarely has one) | Yes (CAN-SPAM: honest subject, opt-out, postal address) | 0 | $0 | Free, but few emails exist |
| 4 | **Inbound**: our own agency site + a free Google Business Profile ("website design Frederick MD"), AI receptionist answers | Yes | 20 min once (verify the profile) | $0 | Slow (months), compounds, free |
| 5 | Optional, fastest money: walk into 5 businesses with your phone and show them their site | Yes | ~1 hour | $0 | Highest close rate of anything here |
| 6 | Optional: a commission-only human caller (paid only from sales) | Yes (a person dialing by hand) | Hire once | ~$200-300 a sale | Calls without you |
| - | AI cold calls, cold texts | **No** (Md. Com. Law 14-4502(a)(3); TCPA) | - | $500-1,500 a call fine | Never |

## The numbers (guesses until the first batch tells us)

| Batch | Cost | If 1 in 100 buys | If 3 in 100 buy |
|---|---|---|---|
| 100 postcards | ~$100 | 1 client = $1,500 + $79/mo | 3 clients = $4,500 + $237/mo |
| 300 postcards a week, 4 weeks | ~$1,200 | 12 clients = $18,000 + $948/mo | 36 clients = $54,000 + $2,844/mo |

Rule: send 2 batches of 100 (a follow-up card goes on day 10 to anyone who did not respond). **0 sales after 200 cards** = change the niche or the offer before spending more. **1+ sale** = scale to 300 a week. Every card carries a short code (e.g. FR-27) so we know which card worked.

## Who does what

| Step | Who |
|---|---|
| Find businesses with no website (OpenStreetMap, Frederick area first, then Maryland), drop chains, fill street addresses | Claude (running) |
| Build a finished site for each one (67 built so far) | Claude (done for Frederick) |
| Design + mail the postcards, follow-ups, the opt-out list | Claude (building; OFF until you type SEND POSTCARDS) |
| Answer replies, calls and the "call me" requests; book; send the payment link | Claude + the AI caller / receptionist (built in simulation; OFF until your yes) |
| After a sale: the real site, their domain, hosting, Google profile, monthly care | Claude (the client buys their own domain) |
| **You, once (about 30 minutes, when you choose):** pick the business name; a return address (a P.O. box, about $20-40 for 6 months, keeps your home address private); a free Gmail; a free payment account (Stripe or Square); the print-and-mail account; optional: the phone service + a Claude API key for the AI caller | You (passwords and sign-ups only) |

## Timeline

- **Tonight (until 20:00 ET):** sites, leads, outreach kit, email autopilot, AI caller (simulation) built; postcards being built; Home reorganised (6 arenas).
- **Sat 10:00 ET:** the lead list with addresses, sample postcards, the exact card price and the setup steps.
- **Sat 12:00 ET:** security check of the AI caller (it would run on the trading PC).
- **Your 30-minute setup (any time after):** then Claude mails the first 100 cards (best niches first: trades and contractors, dentists and health, salons, auto, restaurants).
- **Day 10:** follow-up cards. **Week 2-4:** measure by card code, then scale or change.
