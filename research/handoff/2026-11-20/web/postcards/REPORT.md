# Personalised postcards: research + build (day-a11y, 2026-11-20)

**Why mail.** The map leads have no email and only 8 of 67 have a phone. Cold AI calls need signed consent in Maryland. A postcard to a business is
legal, and its QR code opens the business's **own concept site**, where "Have our assistant call me" is the only door to the AI caller.

**Real money: this is the owner's yes / no.** CLAUDE.md says "no paid services". Postcards cost about $0.91 each in real postage, so the tool is built
OFF; TEST mode is free; and LIVE needs his own provider account plus the typed phrase.

## 1. Print-and-mail APIs (4x6 First-Class postcard, print + postage included)

| Provider | 4x6 price | 6x9 price | Minimum / plan | API + test mode | Sign-up needs |
|---|---|---|---|---|---|
| **Lob** (picked) | **$0.909** on the free Developer plan; $0.649 Startup ($260/mo); $0.619 Growth ($550/mo) | ~$1.03 Developer, $0.71 Startup | none; Developer is $0/month (third parties cite a cap of about 500 / month) | REST + Basic auth, mature docs, address verification; test keys (`test_...`) are free, and nothing is printed or mailed | account + a card on file for live mail |
| PostGrid | $0.862-0.902 | $0.983-1.048 | Starter $0/month, up to about 500 / month | REST; test / live keys (test = nothing printed or billed) | account + card |
| Click2Mail | from about $0.54-0.75 (not confirmed for the API) | n/a | MOL Pro API account | REST; a staging environment | account + approval for MOL Pro |
| Stannp (US) | about $0.80 up to 1,000 (a third-party figure) | $0.99 up to 1,000 | pay as you go | REST; a test flag | account + card |

**Pick: Lob, Developer plan.** It has the only official, current price table (dated 11/01/2026), free test keys that print and mail nothing, and no monthly fee
at ~100 a week (about 430 a month, inside the Developer plan's reported cap). PostGrid is close and about $0.03 cheaper a card. Click2Mail may be cheaper,
but its API price was not confirmed. The code has a Lob adapter only (`lob_send`); a PostGrid one would be about 30 lines.

## 2. Cost at 50 / 100 / 300 cards (4x6, First Class)

| Provider | 50 cards | 100 cards | 300 cards | ~100 a week (≈433 / month) |
|---|---|---|---|---|
| **Lob Developer ($0.909)** | **$45.45** | **$90.90** | **$272.70** | **≈ $394 / month** |
| Lob Startup ($0.649 + $260/mo) | $292.45 | $324.90 | $454.70 | ≈ $541 / month (worth it only above ~1,000 / month) |
| PostGrid Starter ($0.862-0.902) | $43.10-45.10 | $86.20-90.20 | $258.60-270.60 | ≈ $373-391 / month |
| Stannp ($0.80, unconfirmed) | $40.00 | $80.00 | $240.00 | ≈ $346 / month |
| Click2Mail (~$0.61-0.75, unconfirmed) | $30.50-37.50 | $61.00-75.00 | $183.00-225.00 | ≈ $264-325 / month |

Break-even: one Starter site ($1,500) pays for about 1,650 Lob cards. At a 0.5 % close rate, 100 cards a week brings about 1 client every 2 weeks.

## 3. What was built: `tools/postcards.py`
- **Art:** a clean agency brand (white, ink and blue; not the OLYMPUS look), 4x6 plus bleed at 300 dpi.
  - **Front:** "<Business>, your new website is already built." and "Scan the code to see it. It's free to look.", with a large QR code to their concept site. The QR is made on the PC with segno, which is free.
  - **Back:** an honest note naming the business, the link and the call-me button; the sender; the return address (a **P.O. box: owner step**); and "Don't want mail from us? Email … with STOP and your business name, and we'll never send another." The address and postage block is left blank for the printer.
  - Samples: `card1..3-front/back.png` + `sample-cards.pdf` in this folder.
- **Who gets a card:** businesses with their **own concept site built** and a full street address. The leads team's structured `addr` with a ZIP comes first; otherwise the map's one-line address is cleaned. A business never gets a second card, and never one after a 'no'.
  - Today: 23 of 67 leads have a street address and none has a ZIP or a built site yet, so until the factory publishes `agency/sites/index.json` the run sends nothing and says why.
- **The gate:** OFF by default. **POSTCARD_SETUP.bat** installs Pillow + segno and asks for the Lob key (getpass, saved to `%USERPROFILE%\.olympus\postcards.json` only), the name, business, the "no more mail" email and the return address. Then the phrase:
  - `SEND POSTCARDS` + a `live_` key = LIVE;
  - anything else = TEST (a `test_` key: 3 a day, nothing printed or mailed or charged).
  - A mismatched key and mode is refused. **POSTCARD_STOP.bat** = OFF.
- **Limits:** 20 a day, 100 a week, weekdays from 10:00 ET, one batch a day (it rides the email task OlympusAgencyMail).
- **One never-again list**, shared with email: `%USERPROFILE%\.olympus\agency_never.json`, plus the email autopilot's opt-outs, bounces and suppressed addresses. An email reply saying STOP that names a business blocks that business for both channels.
- **The email autopilot stays** for leads that have an email.

Tests: `python -X utf8 -m tests.test_postcards` 27/27 (a fake Lob, never the network: art size, a blank address block, the QR, address cleaning, the never list, OFF / TEST / LIVE gate, caps, Lob's form, no key in any file or error, the .bat chain). `test_agency_autopilot` 43/43.

## Owner steps (only when he says yes to real postage)
1. A P.O. box for the return address (about $20-40 for 3 months at the post office).
2. A free Lob account (lob.com). Use the **test** key first, then add a card and use the **live** key.
3. Double-click `POSTCARD_SETUP.bat`, look at the sample PDF, and type `SEND POSTCARDS` when ready.

Sources:
- [Lob pricing details](https://help.lob.com/print-and-mail/ready-to-get-started/pricing-details)
- [Lob API documentation](https://docs.lob.com/)
- [RFP.wiki: Lob](https://www.rfp.wiki/marketing/direct-mail-automation-software/lob)
- [Lob review 2026](https://bizmailnet.com/lob-review/)
- [PostGrid print and mail pricing](https://www.postgrid.com/pricing-print-mail/)
- [PostGrid postcards](https://www.postgrid.com/print-mail-postcard/)
- [thanks.io vs PostGrid](https://thanks.io/compare/thanks-io-vs-postgrid)
- [PostGrid pricing review](https://frontdeskreview.com/software/direct-mail-automation/postgrid/)
- [AX Check: PostGrid](https://www.ax-check.com/postgrid.com)
- [Click2Mail postcards (PDF)](https://click2mail.com/media/downloads/pdf/c2m_postcards_products.pdf)
- [Click2Mail API quick start](https://rest.click2mail.com/quick-start.html)
- [Click2Mail API blog](https://blog.click2mail.com/category/api/)
- [Stannp US](https://www.stannp.com/us)
- [Stannp postcards API](https://www.stannp.com/us/direct-mail-api/postcards)
- [Sincerely: PostGrid vs Stannp](https://trysincerely.com/compare/postgrid-vs-stannp)
