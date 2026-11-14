# Getting paid for a $0-setup website plan: Stripe vs Square vs PayPal

Team B6, researched 2026-11-14. Not legal or tax advice. **I could not open the three companies' own pricing pages from this
session (the network blocks them), so every figure below comes from web search results dated 2026 that quote those pages, plus
fee guides. Check the three pricing pages yourself before you sign up; fees change.** Where sources disagreed, both numbers are
given.

## The answer

**Use Stripe Payment Links: one link per plan** (Starter $99, Growth $149, Pro $249 a month). The client taps the link, types a card
or bank account once, and Stripe charges the same amount every month by itself, emails the receipt, and lets the client update the
card or cancel from a link you switch on once. "$0 setup" simply means the first charge is the first month.

Square is a fine second choice if you want your money the next business day. Use PayPal only when a client insists on it.

## What one client costs you (fees per monthly charge)

| Plan price | Stripe link, card | Stripe link, bank (ACH) | Square invoice, card | Square invoice, bank | PayPal invoice, card / PayPal |
|---|---|---|---|---|---|
| $99 | $3.86 (keep $95.14) | $1.49 (keep $97.51) | $3.57 (keep $95.43) | $1.00 | $3.95 (keep $95.05) |
| $149 | $5.66 (keep $143.34) | $2.24 (keep $146.76) | $5.22 (keep $143.78) | $1.49 | $5.69 (keep $143.31) |
| $249 | $9.26 (keep $239.74) | $3.74 (keep $245.26) | $8.52 (keep $240.48) | $2.49 | $9.18 (keep $239.82) |
| **At $1,000 MRR (7 clients)** | **about $38 a month** | **about $15 a month** | about $35 a month | about $10 a month | about $38 a month |

How the columns are worked out:
- **Stripe card:** 2.9% + $0.30 per US card payment, plus **0.7% for Stripe Billing**, which is what makes a Payment Link
  repeat every month (pay-as-you-go, no monthly fee). **Stripe bank (ACH Direct Debit):** 0.8%, capped at $5, plus the same 0.7%.
- **Square invoice:** 3.3% + $0.30 when the client pays an invoice by card on the Free plan; bank transfer (ACH) 1%, minimum $1,
  maximum $10. Recurring invoices cost nothing extra to send. A card saved on file and charged automatically is quoted at
  3.5% + $0.15 by one guide ($5.37 on $149).
- **PayPal invoice:** 3.49% + $0.49 for a US invoice paid by card or PayPal; pay-by-bank on invoices 1% capped at $10 (from a
  November 2026 fee sheet whose text was partly garbled).

At this size the card fees are within $3 a month of each other. **The real saving is asking clients to pay by bank (ACH)**: about
$15 instead of $38 a month at $1,000 MRR. A failed bank payment costs more than a failed card (Stripe: $4 per failed ACH payment,
per fee guides), so ask only clients you trust.

## Monthly billing, payout time, sole proprietor

| | Stripe Payment Links | Square Invoices | PayPal |
|---|---|---|---|
| Repeats every month by itself | Yes: a link with a monthly price creates the subscription and saves the card | Yes: recurring invoice series (weekly, monthly...) with a card on file | Yes: recurring invoices / PayPal Subscriptions |
| Client can update the card or cancel alone | Yes: the no-code customer portal link (switch it on once) | Ask you | From their PayPal account |
| Failed payments | Stripe Billing can retry and email the client (check Billing settings) | One guide says declined recurring invoices are **not** retried automatically | Retries depend on the setup |
| When you get the money | Every 2 business days after the first payout; the **first payout takes about 7-14 days** (guides). Instant payout 1.5%, not for new accounts | **Next business day, free**; instant 1.95% (most sources; one says 1.75%) | At once in your PayPal balance; to your bank **free in 1-3 business days**; instant 1.75% (min $0.25, max $25) per most sources (one says it changed on 2026-08-01) |
| Sole proprietor, no company | Yes: pick "Individual / sole proprietor", use your SSN; an EIN is optional | Yes | Yes (business account) |
| Monthly fee | $0 | $0 on the Free plan | $0 |

Tax form: card processors send a Form 1099-K only above **$20,000 and 200 payments in a year** (the 2025 law restored that
threshold, applied back to 2023 per IRS Fact Sheet 2025-08). **All the income is taxable either way** (see
docs/AGENCY_BUSINESS_SETUP.md).

## Your 3 steps

1. Make a free Stripe account at stripe.com: business type **Individual / sole proprietor**, your SSN, your bank account.
2. In Stripe, Product catalog: add **Starter $99, Growth $149, Pro $249, "Recurring, monthly"**, and press **Create payment
   link** on each (copy the three links). Then Settings > Billing > Customer portal > **Activate link**.
3. Paste the links into the kit (one line, from the bot folder):

```
python -m agency.billing setup --pay-link starter=https://buy.stripe.com/... --pay-link growth=https://buy.stripe.com/... --pay-link pro=https://buy.stripe.com/...
```

## Where the link goes on the invoice

In the **"Pay online in a minute"** box right under the totals: a big **"Pay $149.00 now"** button, with the full link printed
under it so a paper copy still works. The kit fills it in from the client's plan (the link you pasted for that plan), so the first
invoice of every `kit` already carries it. Put the same link in the text or email you send with the invoice.

After the first payment Stripe charges the client every month by itself. The kit then needs only:
- `python -m agency.billing paid INV-2026-0001` once, when the first invoice is paid (this also starts the client's monthly plan
  in the ledger, so MRR counts it);
- once a month, Stripe > Payments > **Export** (CSV), then `python -m agency.billing import <file>.csv` (each payment is counted once,
  even if you import the same file twice);
- when a client leaves: cancel the subscription in Stripe and run `python -m agency.billing plan cancel <client> --last-day YYYY-MM-DD`.
- For a month you want an invoice anyway (some clients ask for one): `python -m agency.billing invoice <client> --autopay` says
  "charged automatically, nothing to do" instead of showing a button.

## Sources (searched 2026-11-14)

- Stripe: [stripe.com/pricing](https://stripe.com/pricing) (card 2.9% + 30c, ACH 0.8% capped at $5, as quoted in search results);
  [Stripe Billing pricing](https://stripe.com/in/billing/pricing) and [usagepricing.com Stripe Billing](https://usagepricing.com/blueprint/stripe-billing)
  (0.7% pay-as-you-go, Payment Links for subscriptions); [Stripe Invoicing pricing](https://support.stripe.com/questions/stripe-invoicing-pricing)
  (0.4% per paid invoice on Starter; the 25 free invoices ended 2023-11-01); [Instant Payouts](https://docs.stripe.com/docs/payouts/instant-payouts);
  [sole proprietor without an EIN](https://support.stripe.com/questions/signing-up-for-stripe-as-a-sole-proprietor-without-employer-id-number);
  [no-code customer portal](https://docs.stripe.com/customer-management/activate-no-code-customer-portal);
  fee guides [checkoutpage.com](https://checkoutpage.com/blog/stripe-processing-fees), [dodopayments.com payout schedule](https://dodopayments.com/blogs/stripe-payout-schedule/),
  [dodopayments.com ACH](https://dodopayments.com/blogs/stripe-ach-fees/) (failed ACH $4).
- Square: [square.com our fees](https://square.com/us/en/payments/our-fees) (invoices and Payment Links 3.3% + 30c);
  [Square help 5147](https://squareup.com/help/us/en/article/5147) and [6109](https://squareup.com/help/article/6109) (ACH invoices 1%, $1 min, $10 max; next-business-day transfers);
  [recurring invoices](https://squareup.com/us/en/invoices/features/recurring-invoices); [chargeflow.io Square recurring](https://www.chargeflow.io/blog/how-to-set-up-square-recurring-payments)
  (card on file 3.5% + 15c, no automatic retry); instant transfer [squareup.com instant transfer terms](https://squareup.com/gb/en/legal/general/instant-transfer-terms) (1.95%) and
  [joingerald.com](https://joingerald.com/learn/banking--payments/square-instant-transfer) (1.75%).
- PayPal: [merchant fees](https://www.paypal.com/us/webapps/mpp/merchant-fees) and the [US merchant fees sheet of 2026-11-04](https://www.paypalobjects.com/marketing/ua/pdf/US/us-merchant-fees-04-november-2026.pdf)
  (invoicing 3.49% + 49c; pay by bank 1% capped at $10); bank transfers [wealthvieu.com](https://wealthvieu.com/banking/paypal/fees/) and
  [moneytransfer.store](https://www.moneytransfer.store/guides/paypal-to-bank-account) (checked 2026-11-05: standard free 1-3 days, instant 1.75% max $25);
  [beancount.io](https://beancount.io/blog/2026/08/14/paypal-bank-transfer-fee-jumps-51-percent-august-2026-small-business-guide) (a change on 2026-08-01, unverified).
- 1099-K threshold: [RSM on the IRS FAQs](https://www.rsmus.com/insights/services/business-tax/irs-updates-obbba-new-reporting-thresholds),
  [CPA Practice Advisor](https://cpapracticeadvisor.com/2025/07/30/one-big-beautiful-bill-act-changes-1099-thresholds/165863/).
