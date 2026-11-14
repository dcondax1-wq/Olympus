# The website agency: business basics and a 30-day plan to $1,000 a month

Team B6, 2026-11-14. **Not legal or tax advice.** Rules and fees differ by state and change; check your state's own websites or ask
a CPA before you rely on a number. I researched this on 2026-11-14 with web searches; the official pages (IRS, state sites) could
not be opened from this session, so figures come from search results that quote them. Sources and dates are at the end.

## The short version

| What | What to do | What it costs |
|---|---|---|
| Business form | Start as a **sole proprietor** (you, your own name, your SSN). Think about an LLC once clients pay steadily | $0 now. An LLC: $35-$500 to file, plus a yearly fee in many states |
| Business name | Using a name that is not your own ("Harbor Web Co")? Register it as a DBA ("doing business as") with your county or state | Small, varies by place |
| EIN | Free at IRS.gov/EIN, online, same day. Optional for a sole proprietor with no staff, but it keeps your SSN off client forms | $0 (never pay a website for it) |
| Bank account | One separate checking account for the agency only; Stripe pays into it | Free accounts exist |
| Sales tax | Check if YOUR state taxes website design or hosting (a few do) before your first invoice | Varies |
| Income tax | Put **25-30% of every payment** aside; pay quarterly estimates if you will owe $1,000+ | - |
| Books | 20 minutes a month: the kit's ledger + receipts in one folder | $0 |

## 1. Sole proprietor or LLC

- **Sole proprietor:** you are one the moment you sell your first site. Nothing to file (except a DBA if you use a business
  name). The income goes on your own tax return (Schedule C). You are personally responsible for the business's debts and claims.
- **LLC (limited liability company):** a separate legal company you register with your state. Its main benefit is that a claim
  against the business usually cannot reach your personal savings, **as long as you keep the money fully separate**. A one-person
  LLC is taxed exactly like a sole proprietor by default, so it does not lower taxes by itself.
- **What an LLC costs varies a lot by state** (2026 roundups of state fees): filing from about **$35 (Montana) to $500
  (Massachusetts)**, about $132 on average; yearly costs such as Montana $20, Tennessee $300, Delaware $300, Arkansas $150, Texas
  $0 (a margin tax only above $1.23M of revenue). **California charges an $800 franchise tax every year**; sources disagree on
  whether a first-year exemption still applies, so check the Franchise Tax Board. Look up your own state's Secretary of State site.
- US-formed companies no longer file the federal "beneficial ownership" (BOI) report (FinCEN rule of March 2025).
- A common path: test the offer as a sole proprietor for the first month or two (with the service agreement's liability limits and
  a separate bank account), then form an LLC once you have steady clients, sooner if your state's fee is small. Ask about
  business insurance too: for a web business it can matter as much as the LLC.

## 2. EIN (free)

- The IRS gives an Employer Identification Number **free**, online at IRS.gov/EIN, usually in one session. Sites that charge for
  one are middlemen.
- A sole proprietor with no employees can use his SSN instead (Stripe accepts an SSN for a sole proprietor). Many get an EIN anyway
  so they never give their SSN to clients or on W-9 forms.
- One EIN covers all your trade names as a sole proprietor. An LLC or a partner later means a new EIN.

## 3. A separate bank account

- Open one checking account used **only** for the agency. Stripe payouts land there; business costs (domains, hosting, tools)
  are paid from it. It makes taxes and bookkeeping simple, and for an LLC it is what keeps the liability protection real.
- Banks usually ask for ID, your SSN or EIN, and the DBA paper if you use a business name.

## 4. Sales tax on website services: check your state

Most states do not tax web design, but a growing number tax some digital or web services, and the rules changed recently:

| State (examples) | What sources say (2026) |
|---|---|
| Washington | Custom website development **taxable since 2025-10-01** (WA Department of Revenue); hosting and domain names excluded |
| Maryland | A 3% tax on some data / IT services, including web hosting, since 2025-07-01 (a vendor blog: confirm with the state) |
| Connecticut | Taxes website design and development (Avalara) |
| New York, Wisconsin | Website design delivered electronically is exempt (Avalara) |
| Virginia | A 2026 bill to tax hosting and design died in committee |

How to check yours in 10 minutes:
1. Go to your state's Department of Revenue (or Taxation) website and search "website design", "web hosting", "digital
   automated services" and "software as a service".
2. Check whether a **bundle** (design + hosting in one monthly price) is taxed as a whole unless the invoice lists the parts
   separately. The kit can list them as separate lines (`--item`).
3. Still unsure: call the Department of Revenue or ask a CPA. If it is taxable, get a sales tax permit **before** you charge it,
   then set the rate once: `python -m agency.billing setup --tax-rate 6.5` (your rate).

## 5. Self-employment tax, in plain numbers

- On your **profit** (client payments minus business costs) you pay **self-employment tax of 15.3%**: 12.4% for Social Security
  (on earnings up to **$184,500 in 2026**) and 2.9% for Medicare (no cap; 0.9% more above $200,000 single). It is worked out on
  92.35% of the profit, and half of it is deductible. Then income tax (federal, and state where there is one) comes on top.
- Example: $12,000 profit in a year ($1,000 a month): self-employment tax is about $12,000 x 0.9235 x 15.3% = **$1,696**, plus
  income tax at your bracket.
- **Quarterly estimates:** if you expect to owe $1,000 or more for the year beyond what a job withholds, pay estimated tax with Form
  1040-ES: for 2026 the dates are **April 15, June 15, September 15, 2026 and January 15, 2027**. (With a W-2 job you can instead
  raise your withholding at work.)
- Stripe, Square and PayPal send a 1099-K only above $20,000 and 200 payments a year (restored by the 2025 law, retroactive per
  IRS Fact Sheet 2025-08). **The income is taxable either way.**
- Prop-firm payouts from trading are a separate question for a CPA.

## 6. Keep 25-30% aside

Move 25-30% of every client payment (after Stripe's fee) into a separate savings account the day it lands. Why that number:
self-employment tax is about 14% of profit (15.3% of 92.35%), federal income tax on a first-year profit is often 10-12%, and
state tax is 0-10%. 25-30% covers most people; a high-tax state or a big year needs more. At $1,000 MRR that is **$250-$300 a
month** set aside.

## 7. Simple bookkeeping (20 minutes a month)

| When | What |
|---|---|
| Each new client | `python -m agency.billing kit <client> --open`, then `paid INV-...` when the first month is paid |
| Once a month | Stripe > Payments > Export CSV, then `python -m agency.billing import <file>.csv`; `python -m agency.billing summary` for MRR, churn and cash |
| Once a month | Add business costs (domain, hosting, tools, phone share) in the Ledger app; snap receipts into one folder |
| Once a month | Move the 25-30% to tax savings; check unpaid invoices (`python -m agency.billing list`) |
| Each quarter | Pay the estimated tax (dates above) |
| Each year | Schedule C (profit or loss) and Schedule SE (self-employment tax) with your 1040; keep records at least 3 years |

The kit's summary also feeds the money scoreboard (`python tools/money_scoreboard.py --private` shows it next to trading and
Kalshi); it holds totals only, never client names. Payment set-up (Stripe links, fees, payout times): `agency/billing/PAYMENTS.md`.

## 8. The 30-day plan to the first $1,000 MRR

**The target:** $1,000 of monthly recurring revenue = **7 clients on Growth ($149)**, or 11 on Starter ($99), or a mix (for
example 3 Growth + 3 Starter + 1 Pro = $993). At about $38 of card fees a month, that is roughly $960 a month to you before
your own costs and taxes.

**The funnel this plan assumes (assumptions, not facts):**

| Step | Rate assumed | Why |
|---|---|---|
| Dial -> talk to the owner | 20% | B2B sales benchmarks are 5-10% per dial (2026 vendor studies); a local trade's number is public and the owner often answers it himself. Measure yours |
| Talk -> "yes, send me the demo" | 25% | The ask is small: a site already built for him, free to look at |
| Demo sent -> he looks and talks again | 50% | You follow up the same day and the next |
| Demo talk -> signs and pays | 20% | $0 setup, no long contract, 30 days notice |

So **100 dials -> 20 talks -> 5 demo links -> 2.5 demo talks -> about 0.5 clients**. Seven clients take about 1,400 dials at these
rates; the plan below aims at ~1,000 dials and counts on follow-ups and referrals for the rest. **After the first 300 dials, put
your real rates in this table and redo the daily numbers.** B2B benchmarks range from 1 meeting per 95 dials to 1 per 370, so
the truth could be much better or worse than this.

**Daily numbers (weekdays):**

| Days | Leads added | Demo sites built | Dials | Owner talks | Demo links sent | Demo talks | New clients | MRR at the end |
|---|---|---|---|---|---|---|---|---|
| 1-2 | set-up: Stripe links, bank, business basics | - | - | - | - | - | - | $0 |
| 3-4 | 75 a day (150) | 10 a day (20) | - | - | - | - | - | $0 |
| 5-7 | 25 a day | 5 a day | 40 a day | 8 a day | 2 a day | 1 a day | 1 in the week | $149 |
| 8-14 | 25 a day | 5 a day | 60 a day | 12 a day | 3 a day | 1-2 a day | 2 | $447 |
| 15-21 | 25 a day | 5 a day | 60 a day | 12 a day | 3 a day | 1-2 a day | 2 | $745 |
| 22-30 | 25 a day | 5 a day | 60 a day | 12 a day | 3 a day | 1-2 a day | 2 | **$1,043** |
| **Total** | **~600** | **~120** | **~1,000** | **~200** | **~50** | **~25** | **7** | **7 x $149** |

**Every day, in this order:** 1. Call for 2.5 hours (60 dials). 2. Send every promised demo link within 10 minutes, by text.
3. Follow up yesterday's demo links. 4. Build tomorrow's 5 demo sites. 5. Close: `python -m agency.billing kit <client> --open`,
send the three files, and run `paid` when they pay.

**Every Friday:** `python -m agency.billing summary` (MRR, who paid, open invoices) and compare the week's real rates with the
table. If talks per dial are low, change the calling hours (early morning and after 4 pm often reach owners); if demo talks do not
close, change the demo or the offer, not the price.

**Honest limits.** These are planning numbers from general sales benchmarks, not results; a month can easily end with 3 clients
instead of 7. Local businesses also leave: the summary shows churn every month, and a plan that keeps 7 clients needs new ones
every month to replace the ones that cancel.

## Sources (searched 2026-11-14)

- LLC fees: [Inc Authority, 2026 LLC costs](https://www.incauthority.com/blog/how-much-does-an-llc-cost), [VentureSmarter breakdown by state](https://venturesmarter.com/how-much-does-an-llc-cost-y-complete-breakdown-by-state/),
  [Zenind, California 2026](https://www.zenind.com/help/post/california-llc-filing-fees-in-2026-what-it-really-costs-to-form-and-maintain-an-llc), [LLC University, California](https://www.llcuniversity.com/california-llc/costs/)
  (they disagree on California's first-year $800).
- EIN: [IRS-based guides, e.g. Xero](https://www.xero.com/us/guides/how-to-get-an-ein-number/), [TRUiC (updated 2026-04-01)](https://www.howtostartanllc.com/what-is-an-ein); Stripe and an SSN:
  [Stripe support](https://support.stripe.com/questions/signing-up-for-stripe-as-a-sole-proprietor-without-employer-id-number).
- BOI report: FinCEN's interim rule of March 2025 removed it for US-formed companies ([FinCEN BOI page](https://www.fincen.gov/boi); not re-checked
  in this session: confirm before you form an LLC).
- Sales tax: [Washington DOR, custom website development](https://www.dor.wa.gov/taxes-rates/retail-sales-tax/services-newly-subject-retail-sales-tax/custom-website-development),
  [Avalara: should web designers charge sales tax](https://www.avalara.com/us/en/blog/should-web-designers-and-developers-charge-sales-tax.html),
  [Sales Tax Institute, SaaS expansion by state](https://www.salestaxinstitute.com/resources/saas-sales-tax-expansion-by-state),
  [DLA Piper, January 2026 alert](https://www.dlapiper.com/en/insights/publications/indirect-tax-monthly-alert-series/2026/indirect-tax-monthly-alert-january-2026/states-continue-the-push-to-impose-sales-tax-on-electronic-services).
- Self-employment tax and the 2026 wage base ($184,500): [The Tax Adviser, 2025-10](https://www.thetaxadviser.com/news/2025/oct/social-security-wage-base-and-cola-announced-for-2026/),
  [Journal of Accountancy](https://www.journalofaccountancy.com/news/2025/oct/social-security-wage-base-and-cola-announced-for-2026/).
- Estimated tax dates for 2026 and the $1,000 rule: [Yahoo Finance](https://finance.yahoo.com/personal-finance/taxes/article/when-are-quarterly-taxes-due-210746837.html),
  [OnPay, Form 1040-ES](https://onpay.com/insights/estimated-taxes-quarterly-payments/) (confirm on IRS.gov).
- 1099-K threshold: [RSM](https://www.rsmus.com/insights/services/business-tax/irs-updates-obbba-new-reporting-thresholds),
  [CPA Practice Advisor](https://cpapracticeadvisor.com/2025/07/30/one-big-beautiful-bill-act-changes-1099-thresholds/165863/).
- Cold-call benchmarks (B2B, vendor studies, 2026): [Belkins, 175,000+ dials](https://belkins.io/blog/cold-calling-benchmarks),
  [Prospeo summary of Gong / Cognism](https://prospeo.io/s/cold-calling-success-rate), [GrowthSpree](https://www.growthspreeofficial.com/blogs/b2b-saas-cold-call-connect-rate-benchmarks-2026-dial-attempts-conversation-rate-meeting-conversion).
