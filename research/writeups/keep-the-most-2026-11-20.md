---
title: Keep the most of every payout - taxes, the payout waterfall, and when to open a live account (2026-11-20)
family: money
date: 2026-11-20
status: info - education, not tax advice. Federal 2026 + 2027 numbers checked on IRS.gov 2026-11-20; MARYLAND (owner's state, lead 2026-11-20) checked on the Comptroller / SDAT / DOL sites the same day; county not known (range 2.25%-3.30%). Paper only, nothing live changed.
summary: Owner 2026-11-20 "maximize on our money, how much we keep". Maryland: set aside 15-35% of each payout by the year's profit (30% for the expected ~$30-60k year), 35-45% with a day job; 10% eval reserve until $320, 10% retirement (Roth IRA under $15k, Solo 401(k) from $15k), 20% live fund until $5,000, rest yours ($1,000 request = $800 landed -> $240 yours; $5,000 -> $1,280). Open a live futures account at $5,000 from payouts + 4 payouts received, 1 MNQ per bot (lose half in a year 0% 2026-like / 9% 2021-25-like); live gains are 60/40 federally with no SE tax but ordinary in Maryland ($30k: ~$1,840 all Maryland vs ~$6,850 as prop income). S-corp only from ~$50-60k steady profit (Maryland break-even ~$49k; saves ~$1,460 at $60k, ~$2,580 at $100k). Built on taxes-2026-11-17.md. Page tools/web_public/business/taxes.html; math tools/money/keep_most.py -> research/lab/keep_most.json.
runs: python -X utf8 tools/money/keep_most.py (~2 s); tests: python -X utf8 -m tests.test_business_taxes [--browser] (money area)
---

# Keep the most of every payout (2026-11-20)

**Education, not tax advice.** General US federal rules for a single filer, checked on IRS.gov on 2026-11-20. Where the
law is unsettled it says so and uses the safe default. The base (how payouts are taxed, deductions, records, VITA) is
`research/writeups/taxes-2026-11-17.md`; this note adds the money plan on top. Owner's state and job status are unknown:
**Maryland** (lead, 2026-11-20: the owner lives there; nothing more specific is stored). The county is not known, so
county-dependent $ are a range: 2.25% (lowest, Worcester) to 3.30% (highest, Dorchester / Kent); the % uses the highest.

## For the owner

| What | Result |
|---|---|
| Tax pot per payout (Maryland) | **30%** for the expected year (~$30-60k, no day job); **40%** with a day job (table 1) |
| The day a payout lands | 30% tax pot, 10% eval reserve (until $320), 10% retirement, 20% live fund (until $5,000), rest yours |
| First ATLAS payout ($1,000 asked = $800 landed) | $240 tax, $80 reserve, $80 retirement, $160 live fund, **$240 yours** |
| A $5,000 request ($4,000 landed) | $1,200 tax, $320 reserve, $400 retirement, $800 live fund, **$1,280 yours** |
| Retirement | Under $15k a year: Roth IRA. From $15k: free Solo 401(k) (Roth while in the 12% bracket) |
| S-corp | Not yet. Worth asking a CPA at about $60k+ steady profit (Maryland: ~$1,460 at $60k, ~$2,580 at $100k) |
| Live futures account | Open at **$5,000 in the live fund + 4 payouts received**, 1 MNQ per bot, stop at $2,500 |
| Why live is worth it later | Own futures gains = 60/40 federally, no 15.3% SE tax: $30k gains ~$1,840 (all Maryland) vs ~$6,850 as prop payouts (no other job) |

## 1. The tax money plan

### How much each payout costs in tax - Maryland, 2026 (2027 within 1 point)
Federal income tax + self-employment tax + Maryland state + county tax, single, standard deductions, **QBI left out on
purpose** (safe default: whether a prop payout is QBI from a "specified service" is not settled; below $201,750 taxable
income (2026; $208,300 in 2027) an SSTB gets the full deduction anyway, so if it applies you get 2-5 points back at filing).
Profit = payouts minus fees. $ range = county 2.25% to 3.30%.

| Profit a year (after fees) | Only trading | Pot % | + $50k day job | Pot % |
|---|---|---|---|---|
| $5,000 | $706 (14.1%) | 15 | $1,589 - $1,638 (31.8 - 32.8%) | 35 |
| $15,000 | $2,584 - $2,662 (17.2 - 17.7%) | 20 | $4,768 - $4,914 (31.8 - 32.8%) | 35 |
| $30,000 | $6,858 - $7,082 (22.9 - 23.6%) | 25 | $10,674 - $10,967 (35.6 - 36.6%) | 40 |
| $60,000 | $16,381 - $16,898 (27.3 - 28.2%) | 30 | $23,112 - $23,715 (38.5 - 39.5%) | 40 |
| $100,000 | $31,740 - $32,647 (31.7 - 32.6%) | 35 | $40,153 - $41,154 (40.2 - 41.2%) | 45 |

SE tax is 15.3% on 92.35% of profit (12.4% only up to the Social Security base: $184,500 in 2026, $192,300 in 2027).
Maryland model (keep_most.md_tax): Maryland starts from federal AGI; standard deduction $3,350 flat; personal exemption
$3,200 (AGI <= $100k; $1,600 to $125k, $800 to $150k, $0 above); state brackets 2% / 3% / 4% to $3,000, 4.75% to
$100,000, 5% / 5.25% / 5.5% / 5.75% to $125k / $150k / $250k / $500k, 6.25% to $1M, 6.5% above (2025 law, HB 352); county
tax on the same base. Anne Arundel and Frederick use banded county rates (the range covers them).

**The 30% rule from Nov 17 still fits** the expected year (fleet plan ~$40k a year, no day job: 25-30%). With a day job it
must be **40%**. The pot over-holds by ~35% of every fee (money_book.tax_true_up): keep the overage until the quarter's
estimates are paid.

### Maryland specifics (checked 2026-11-20)
| Item | Rule | Source |
|---|---|---|
| Schedule C income | same state + county rates; no Maryland self-employment tax | 2026 PV worksheet (starts from federal AGI) |
| Estimated tax | Form 502D / PV voucher or online; Apr 15, Jun 15, Sep 15, Jan 15 (same as IRS); required when tax due over withholding > $500 | 2026 PV worksheet |
| No-penalty rule | **110% of last year's Maryland tax or 90% of this year's** (no income tier, unlike the IRS 100% / 110%); interest ~0.90% a month | PV worksheet, Form 502UP |
| 60/40 futures | no lower capital-gains rate: taxed as ordinary state + county income | TB-58 |
| 2% capital-gains surcharge | on net capital gain when federal AGI > $350,000 (from 2025). Unsettled for 1256: TB-58 uses the federal definition (only the 60% long part) but Form 502CG line 1 takes total capital gain - safe default: the full gain | TB-58, Form 502CG |
| Retirement / HSA | traditional Solo 401(k), SEP, IRA, HSA deductions carry into Maryland (it starts from federal AGI) | PV worksheet |
| LLC | $100 articles + **$300 annual report every Apr 15** (Form 1), owed even with no income | SDAT fees |
| S-corp | follows the federal S election; same $300 report; optional pass-through entity tax 8.75% for individuals (Form 511) | Comptroller Tax Alert, PTE booklet |
| Unemployment tax (S-corp salary) | new employer 1.0% - 2.6% of the first $8,500 (max ~$221) | MD Labor |
| Pending | HB 411 (2026) would raise the standard deduction to $4,100; the Comptroller's 2026 worksheet still says $3,350 (used here) | - |

### Deductions (Schedule C) and the record for each
| Cost | 2026-27 amount for this business | Record to keep |
|---|---|---|
| Eval fees: Builder 50K $91.80, Builder 25K $63 / $43, Rapid EOD 25K $97.20, Rapid EOD 50K $165 | every buy and re-buy | MFFU receipt email, saved as PDF |
| Resets, activation (MFFU: $0 activation) | as paid | receipt |
| Market data, NinjaTrader licence, VPS | business share | invoice + how you chose the % |
| The PC | business share; an item up to $2,500 can be expensed at once (de minimis safe harbor) | receipt + business-use % |
| Internet, phone | business share only (e.g. 40%) | bills + one note on the % |
| Home office | only a space used regularly AND exclusively for the business: $5 / sq ft, max 300 sq ft = $1,500 | size, photo |
| Self-employed health insurance | premiums if not eligible for an employer plan (Schedule 1, not Schedule C) | 1095 / premium statements |
Each $100 of real costs saves about $15-30 of tax at these incomes. 2026 note: the evals were bought in 2026 and the first
payout lands in January 2027, so 2026 is likely a small Schedule C loss (it lowers other 2026 income if he has any; fees
paid before the business "starts" can be start-up costs instead - a preparer decides).

### Quarterly payments and never paying a penalty
- Due dates for 2026 tax: Apr 15, Jun 15, Sep 15, 2026, **Jan 15, 2027** (IRS Form 1040-ES 2026). For 2027 tax (the usual
  schedule; the 2027 1040-ES is not posted yet): Apr 15, Jun 15, Sep 15, 2027, Jan 18, 2028 (Jan 15 is a Saturday, then MLK Day).
- Safe harbor (Pub 505): no penalty if what you paid on time is at least **90% of this year's tax or 100% of last year's**
  (**110%** if last year's AGI was over $150,000). **Maryland: 110% of last year's or 90% of this year's**, always.
- **Biggest free win for 2027:** the first real payouts are in 2027. If his 2026 total tax is $0 (a full year), there is
  **no 2027 underpayment penalty at all**; if he had tax in 2026 (a day job), paying 100% of the 2026 tax in four parts
  (or raising W-4 withholding at the job, which counts as paid evenly through the year) makes any 2027 size penalty-free.
  The tax itself is still due Apr 15, 2028 - that is what the pot is for.
- Pay free at IRS Direct Pay ("Estimated tax", "1040-ES", the right year). Keep each confirmation number.

## 2. Keep more legally - the ladder

| At this profit a year | Do this | $ effect |
|---|---|---|
| Any | Separate tax-pot savings; save every receipt; write down business % | ~15-30% of every fee back |
| Under $15,000 | **Roth IRA** ($7,500 a year 2026 and 2027, +$1,100 at 50+); income tax is ~$0 so a deduction saves nothing | traditional would save $0 here (no job) |
| $15,000 - $30,000 | Free **Solo 401(k)** (Fidelity / Schwab / E*TRADE, no fee). Roth while in the 10-12% bracket | up to ~93% of profit can go in ($27,881 at $30k) |
| $30,000 - $60,000 | Solo 401(k), traditional on the part taxed at 22% | 10% of $60k in saves $1,059 federal + Maryland ($1,670 with a day job); maxed $6,073 |
| HSA (any level) | only with a high-deductible health plan (2026 min deductible $1,700 single); $4,400 / $4,500 (2026 / 2027) | deduction + tax-free growth |
| ~$60,000+, steady 12 months | CPA + **S-corp** election | Maryland break-even ~$49,000; +$1,464 at $60k, +$2,270 at $80k, +$2,580 at $100k, +$4,152 at $150k |
| LLC | liability only; a one-member LLC is taxed exactly like now (IRS "single member LLC") | $0 tax change; Maryland $100 + $300 a year |

Retirement limits (IRS Notice 2025-67 / 2026-66): 401(k) employee deferral **$24,500 (2026) / $25,500 (2027)**, catch-up
50+ $8,000 / $8,500 (60-63: $11,250 / $11,750), total additions **$72,000 / $75,000**; a sole proprietor's employer share
is 20% of (profit - half SE tax). SEP-IRA: same 20% only (no employee part), so much less at these incomes.
Deadlines (IRS Pub 560): a sole owner with no employees can adopt a Solo 401(k) for a year after Dec 31, by the filing
date without extensions, and make that first year's employee deferrals by the same date; employer money is due by the
filing date with extensions. SEP-IRA: set up and fund by the filing date with extensions.
Roth vs traditional: Roth when today's bracket is 10-12% (most of the table's no-job rows); traditional on money that would
be taxed at 22%+. Traditional money also lowers AGI, which raises ACA marketplace subsidies if he buys his own insurance.

S-corp model (keep_most.scorp): salary = the larger of $30,000 or 50% of profit (IRS: a "reasonable salary" is required;
distributions can be reclassified as wages), 15.3% payroll tax on the salary, QBI shrinks (salary is not QBI), extra costs
$600 payroll service + $1,000 extra return + $221 Maryland unemployment tax (2.6% of $8,500) + $300 SDAT report = $2,121 a
year; Maryland state + county tax is the same on salary and K-1 income (in the model on both sides). **Unsettled / check first:** whether MFFU (and Rise) will pay a business (W-9
with an EIN) rather than the person on the account - if not, the S-corp cannot receive the payouts. Safe default: stay a
sole proprietor until a CPA confirms both.

QBI (2025 law): permanent; from 2026 a minimum deduction of $400 ($415 in 2027) with at least $1,000 ($1,030) of active
QBI. It lowers income tax only. Prop payouts as QBI: likely, not certain (safe default above: do not count on it).

## 3. When to start a LIVE personal futures account

### Prop vs live in one table
| | Prop (MFFU) | Own live futures account |
|---|---|---|
| Money at risk | the eval fee only ($43-$165) | the whole account |
| Your share | 80% (Builder), 90% (Rapid) | 100% |
| Caps | Builder $250-$1,000 a payout, 5 sim payouts, then MFFU live (sim accounts go dormant); max 5 funded, 2 x Builder 25K | none |
| Tax | ordinary + **15.3% SE tax** (Schedule C/SE) | **Section 1256 60/40, no SE tax** (Form 6781) |
| Losing year | fee losses on Schedule C | net 1256 loss can be carried back 3 years against 1256 gains (Form 6781) |
| Margin | none | 1 MNQ $100 intraday at NinjaTrader / AMP ($1,000 NQ); overnight ~$4,600 MNQ / ~$46,000 NQ (checked 2026-11-20) |
| PDT rule | n/a | never applied to futures (FINRA's rule was for securities margin accounts and is being retired: Notice 26-10) |

Tax on the same $ (federal + Maryland at the highest county rate 3.30%, single; keep_most.compare_1256; QBI on for prop):
| $ a year | Prop, no job | Live 60/40, no job | Prop + $50k job | Live 60/40 + $50k job |
|---|---|---|---|---|
| $15,000 | $2,662 | $628 | $4,580 | $1,928 |
| $30,000 | $6,846 | $1,835 | $9,740 | $6,022 |
| $60,000 | $15,946 | $5,040 | $21,261 | $14,001 |
| $100,000 | $29,266 | $15,258 | $36,693 | $24,560 |
(Federal: 60% of the gain at the long-term rate - 0% up to $49,450 taxable in 2026, $51,050 in 2027 - and 40% ordinary;
NIIT 3.8% above $200k MAGI. Maryland: all of it at ordinary state + county rates; the 2% surcharge only above $350k AGI.
At $30k with no job the whole $1,835 is Maryland tax.)

### Sizing the live account - risk of ruin at 1 MNQ (the repo's real trades)
Trades: research/anatomy (costs in), $ per 1 micro. Week-block bootstrap, 52 weeks, 4,000 paths; "lose half" = the balance
touches 50% of the start at any week-end.

| At 1 MNQ | Trades/wk | PF | $ a month | Worst drawdown |
|---|---|---|---|---|
| LIT + ATLAS, 2026 Jan-Jun | 7.4 | 2.80 | $2,159 | -$901 |
| LIT + ATLAS, 2026 Jul-Oct | 5.1 | 2.80 | $1,542 | -$715 |
| LIT + ATLAS, 2021-25 | 6.3 | 1.12 | $123 | -$4,795 |

| Start with | Lose half in a year: Jan-Jun / Jul-Oct / 2021-25-like | Bad year (1 in 10), 2021-25-like |
|---|---|---|
| $1,000 | 2% / 14% / 60% | -$769 |
| $2,000 | 0.1% / 2% / 40% | -$1,206 |
| $3,000 | 0% / 0.5% / 25% | -$1,649 |
| **$5,000** | **0% / 0.1% / 8.5%** | **-$1,866** |
| $10,000 | 0% / 0% / 0.3% | -$1,396 |
ATLAS alone at $3,000: 0% / 0.1% / 14%.

**The trigger:** open live when **(a) $5,000 sits in the live fund, all from payouts, and (b) at least 4 payouts have been
received** (the bots' edge seen in real money, not just backtests). Start at **1 MNQ per bot** (at most 2 micros open), add
one micro per bot for each extra $5,000, and **stop at $2,500** (back to prop only). At 20% of each payout the fund fills in
about 6-9 months (fleet plan pace). Never fund it from savings or the tax pot. Never take the opposite side of a prop trade
in the live account (hedging across accounts breaks MFFU's rules). Arming it is the owner's job; Claude never arms live.

**Prop accounts alongside:** keep every MFFU slot full first - it risks only fees and pays 80-90%. Limits (STATE.md, MFFU
help center): 5 sim-funded at once (Builder 1 x 50K + 2 x 25K; Rapid EOD 3 x 50K), 10 evals. The 5th funded slot = Rapid
EOD 50K (money-ideas 2026-11-20). After a Builder's 5th sim payout MFFU moves it to its live program and the sim accounts go
dormant - plan the 5th payout of each Builder knowing that.

## 4. The payout waterfall (the day money lands)
Order: 1) tax pot (30% now; 15-40% by table 1 later), 2) eval reserve 10% until it holds $320, 3) retirement 10%,
4) live-account fund 20% until it holds $5,000, 5) the rest is yours. A full bucket hands its share back to you.

| Landed | Tax pot | Eval reserve | Retirement | Live fund | Yours |
|---|---|---|---|---|---|
| $800 ($1,000 asked, Builder 80%) | $240 | $80 | $80 | $160 | **$240** |
| $4,000 ($5,000 asked) | $1,200 | $320 | $400 | $800 | **$1,280** |
| $800, reserve + live fund already full | $240 | $0 | $80 | $0 | **$480** |
Then: pay the pot to the IRS by the next 1040-ES date (Jan 15, 2027 for anything landing before then).

## 5. On the phone
`tools/web_public/business/taxes.html`: the calculator (type the payout, pick your year, tick day job / state -> the %,
the five buckets in $ and the next due date), the set-aside table, "Never pay a penalty", the ladder, "When to open a live
account", "Your state: Maryland" (tell Claude your county). 390 px, CLS 0, no sideways scroll at 320 px, textContent only. Shots in
research/handoff/2026-11-20/taxes/. (The business pages render in the AGORA dark look; a saved light theme does not change
them, same as the other business pages.)

## Sources (checked 2026-11-20)
- IRS Rev. Proc. 2025-32 (2026 brackets, std deduction $16,100, LTCG, QBI threshold): https://www.irs.gov/pub/irs-drop/rp-25-32.pdf
- IRS Rev. Proc. 2026-35 + IR-2026-133, Nov 5 2026 (2027: std $16,600, brackets, LTCG $51,050, QBI $208,300 / min $415): https://www.irs.gov/pub/irs-drop/rp-26-35.pdf
- IRS Notice 2025-67 (2026 retirement limits): https://www.irs.gov/pub/irs-drop/n-25-67.pdf ; Notice 2026-66 + IR-2026-136, Nov 12 2026 (2027): https://www.irs.gov/pub/irs-drop/n-26-66.pdf
- IRS Rev. Proc. 2025-19 / 2026-24 (HSA): https://www.irs.gov/pub/irs-drop/rp-25-19.pdf , https://www.irs.gov/pub/irs-drop/rp-26-24.pdf
- Social Security base $184,500 / $192,300: SSA https://www.ssa.gov/oact/cola/cbb.html (blocked to automated reads; confirmed in IRS Pub 15 2026 and the 2027 draft)
- IRS Pub 505 (safe harbor): https://www.irs.gov/pub/irs-pdf/p505.pdf ; Form 1040-ES 2026: https://www.irs.gov/pub/irs-pdf/f1040es.pdf
- IRS Pub 560 (Solo 401(k), SEP deadlines): https://www.irs.gov/pub/irs-pdf/p560.pdf ; SEP: https://www.irs.gov/retirement-plans/plan-sponsor/simplified-employee-pension-plan-sep
- IRS Form 6781 + Pub 550 (60/40, 3-year carryback): https://www.irs.gov/pub/irs-pdf/f6781.pdf , https://www.irs.gov/pub/irs-pdf/p550.pdf
- IRS Topic 560 (additional Medicare 0.9%): https://www.irs.gov/taxtopics/tc560 ; NIIT Q&A: https://www.irs.gov/newsroom/questions-and-answers-on-the-net-investment-income-tax
- IRS S-corp reasonable salary: https://www.irs.gov/businesses/small-businesses-self-employed/s-corporation-employees-shareholders-and-corporate-officers
- IRS single-member LLC: https://www.irs.gov/businesses/small-businesses-self-employed/single-member-limited-liability-companies
- Margins: NinjaTrader https://ninjatrader.com/pricing/margins/ (table dated 2026-08-31), AMP https://www.ampfutures.com/trading-info/margins ; CME page unavailable (503) on 2026-11-20
- FINRA Regulatory Notice 26-10 (PDT rule replaced; securities only): https://www.finra.org/rules-guidance/notices/26-10
- MFFU rules: research/lit/mffu_rules.json (help center, checked 2026-11-17)
- Maryland 2026 PV worksheet (rates, deduction, exemption, dates, 110% / 90%): https://www.marylandcomptroller.gov/content/dam/mdcomp/tax/forms/worksheets/2026-pv-worksheet.pdf
- Maryland Tax Alert, 2025 session changes (rev. 12/22/2025): https://www.marylandcomptroller.gov/content/dam/mdcomp/tax/legal-publications/alerts/tax-alert-changes-to-standard-and-itemized-deductions-and-to-state-and-local-income-tax-rates-from-the-2025-legislative-session.pdf
- Maryland TB-58 (capital gains, 2% surcharge): https://www.marylandcomptroller.gov/content/dam/mdcomp/tax/legal-publications/technical-bulletins/tb-58.pdf ; Form 502CG: https://www.marylandcomptroller.gov/content/dam/mdcomp/tax/forms/2025/502cg.pdf
- Maryland 2026 county rates: https://www.marylandcomptroller.gov/content/dam/mdcomp/md/state-payroll/memos/2026/2026-maryland-state-and-local-withholding-information.pdf
- Maryland Form 502UP (underpayment interest): https://www.marylandcomptroller.gov/content/dam/mdcomp/tax/forms/2025/502up.pdf
- SDAT fees: https://dat.maryland.gov/businesses/Documents/FEES.pdf ; MD Labor UI rates: https://www.labor.maryland.gov/unemployment-insurance/employer-agent/tax-rate.shtml
