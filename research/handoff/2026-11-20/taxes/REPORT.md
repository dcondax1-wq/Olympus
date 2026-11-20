# Keep the most of every payout - report (day-taxes, 2026-11-20)

Education, not tax advice. Federal 2026 + 2027 numbers checked on IRS.gov today; Maryland checked on the Comptroller / SDAT sites today. County unknown: $ shown as a range (2.25% - 3.30%).

| What | Result |
|---|---|
| Tax pot (Maryland) | **30% of every payout** for our expected year (~$30-60k, no day job). **40% if you have a day job.** (15% at $5k a year ... 35% at $100k) |
| Waterfall the day money lands | 30% tax, 10% eval reserve (until $320), 10% retirement, 20% live fund (until $5,000), rest yours |
| First ATLAS payout ($1,000 asked = $800 landed) | $240 tax / $80 reserve / $80 retirement / $160 live fund / **$240 yours** |
| $5,000 asked ($4,000 landed) | $1,200 / $320 / $400 / $800 / **$1,280 yours** |
| No penalty, ever | IRS: pay 100% of your 2026 tax in 4 parts (110% if income > $150k); $0 tax in 2026 = no 2027 penalty. Maryland: 110% of last year's MD tax |
| Next IRS date | **Jan 15, 2027** (then Apr 15, Jun 15, Sep 15, 2027) |
| Retirement | Under $15k a year: Roth IRA ($7,500). From $15k: free Solo 401(k). 10% of $60k in = $1,059-$1,670 less tax (Maryland counts it too) |
| S-corp / LLC | Not yet. Maryland S-corp break-even ~$49k; +$1,464 at $60k, +$2,580 at $100k. LLC = liability only, $100 + $300 a year in Maryland |
| Live futures account | Open at **$5,000 from payouts + 4 payouts received**, 1 MNQ per bot, stop at $2,500 |
| Why live (later) | Your own futures = 60/40 federally, no 15.3% SE tax: $30k of gains ~$1,840 (all Maryland) vs ~$6,850 as prop payouts (no job) |
| Live risk at $5,000 | Lose half in a year: 0% in a 2026-like market, 8.5% if it turns like 2021-25. Makes ~$1,540/mo (Jul-Oct-like) or ~$120 (2021-25-like) |
| Phone | Business -> Taxes: type a payout -> the 5 buckets in $ + the due date; the % table; the ladder; the live trigger |

Your steps:
1. Tell Claude your county and whether you have a day job (one line: `County: __, day job: yes/no`).
2. Open a separate savings account for the tax pot before the first payout lands.
3. When ATLAS pays: open Business -> Taxes, type what landed, move the money as it says.

Built: tools/money/keep_most.py -> research/lab/keep_most.json; page tools/web_public/business/taxes.html + taxes.js (v2);
write-up research/writeups/keep-the-most-2026-11-20.md; tests tests/test_business_taxes.py 30/30 (+ added to the money area).
Shots (390x844, x2): taxes-top-dark.png, taxes-s-pot-dark.png, taxes-s-pot-4000-dayjob-dark.png, taxes-s-pct/pen/ladder/live-dark.png.
Honest limits: the S-corp needs MFFU/Rise to pay a business (unconfirmed); QBI for prop payouts is likely, not certain (left out of the
pot % on purpose); 2027 Form 1040-ES not posted yet; Maryland 2027 figures not out; the 2% MD surcharge on 1256 gains is unsettled (only above $350k); backtests overstate; CME margin page was down
(broker pages used). Business pages render dark only (same as the other business pages), so no light shot.
