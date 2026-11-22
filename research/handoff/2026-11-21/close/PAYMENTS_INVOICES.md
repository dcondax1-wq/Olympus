# Getting paid (free tools) + invoice and receipt templates

## Which way to get paid

| Way | Cost to set up | Fee on a $750 deposit | Fee on $79/month | Best for |
|---|---|---|---|---|
| **Stripe Payment Link: bank (ACH)** | $0 | 0.8%, max $5 -> **$5.00** | $0.63 + 0.7% Billing = $1.19 | Deposits and launch payments (cheapest by far) |
| **Stripe Payment Link: card** | $0 | 2.9% + 30c -> **$22.05** | $2.59 + 0.7% Billing = $3.14 | Clients who want to use a card |
| Square Payment Link (card) | $0 | 3.3% + 30c -> $25.05 | $2.91 | Only if you already use Square |
| **Zelle** (your business bank) | $0 | **$0** | not automatic | Clients who already use Zelle; you send the receipt |

Stripe's prices: stripe.com/pricing and stripe.com/billing/pricing (card 2.9% + 30c; ACH 0.8% capped at $5; subscriptions 0.7% of
Billing volume, no monthly fee). Square: squareup.com help "fees and payments FAQs" (payment links 3.3% + 30c). Checked 2026-11-21.
No monthly fee anywhere: you pay only when money comes in.

**Maryland sales tax: please check this first.** Since 2025-07-01 Maryland charges **3% sales tax on "data or information technology
services"** (NAICS 518, 519, 5415: HB 352, Comptroller Technical Bulletin 56). Custom web design and hosting fall under those codes
(5415 includes custom web page design; 518 includes hosting), so **the build and the care plan are most likely taxable at 3%**.
Before the first invoice: (1) get a **free Maryland sales and use tax license** at Maryland Business Express (businessexpress.maryland.gov),
(2) ask the Comptroller (taxhelp@marylandtaxes.gov) to confirm for "small-business website design + hosting". The templates below have a
tax line. Leave it at $0 only if the Comptroller says these services are exempt.

## Stripe: exact steps (15 minutes, once)

1. **stripe.com -> Start now**: sign up with the **agency Gmail**. Business type: Individual / sole proprietor (or your LLC). Add your bank
   account for payouts and your SSN or EIN (Stripe needs it by law). Use your business name on the statement descriptor (e.g. "<AGENCY> WEB").
2. **Payment Links -> + New** (once per product, reuse for every client):
   - "Website deposit (50%)": one-time **$750** -> **Payment methods**: turn on **US bank account (ACH)** and cards.
   - "Website launch payment (50%)": one-time **$750**, same settings.
   - "Care plan": **recurring, $79 monthly**.
   - "Website, nothing upfront": **recurring, $149 monthly**, and end it after 12 months (or cancel by hand at month 12, then start the care plan).
   - If the 3% Maryland tax applies, set prices tax-inclusive or add it with Stripe Tax (Stripe Tax has its own fee). Simplest: a separate
     line "Maryland sales tax 3%" on the invoice, and links for $772.50 / $81.37 / $153.47.
3. Under each link: **After payment -> Show confirmation page** with "Thank you! We'll email your receipt and next steps." Stripe also
   emails the client a receipt automatically (Settings -> Customer emails -> Successful payments: ON).
4. Copy each link into `tools/caller/settings.json` "payment_link" (the AI receptionist) and the agency offer page (lead).

**Zelle:** in your bank app, enroll the agency email or business phone for Zelle. Tell clients: "Zelle to <agency email>, memo: <code>". Send
the receipt the same day (below). Zelle has no buyer protection, so never accept Zelle for a refund-type dispute; use it only for normal invoices.

## Invoice (copy, fill the <>, send as an email or a PDF from Google Docs)

```
INVOICE <INV-2026-001>                                  Date: <date>      Due: <date + 14 days>
From: <Agency> · <postal address> · <agency email> · <agency phone> · MD sales tax license <number>
To:   <Client business> · <client contact name> · <client email>

Item                                              Qty   Price
Starter website (5 pages, <domain>): 50% deposit   1    $750.00
Maryland sales tax 3% (data/IT services)                $22.50
TOTAL DUE                                               $772.50

Pay: <Stripe link> (bank transfer: lowest fee; or card)  ·  or Zelle to <agency email>, memo <INV-2026-001>
Terms: due in 14 days (Website Services Agreement dated <date>). Questions: reply to this email.
```

## Receipt (send the same day the money arrives)

```
RECEIPT <RCPT-2026-001> for invoice <INV-2026-001>       Paid: <date>     Method: <Stripe bank / card / Zelle>
From: <Agency> · <postal address> · <agency email>
To:   <Client business>

Paid: Starter website, 50% deposit                       $750.00
Maryland sales tax 3%                                    $22.50
TOTAL PAID                                               $772.50       Balance remaining: $772.50 (due on launch day)

Thank you! Next step: the intake form <intake link>. We go live within 7 days of your content.
```

Keep every invoice and receipt in a Google Drive folder "Invoices 2026" (free). They're your income records for taxes.
