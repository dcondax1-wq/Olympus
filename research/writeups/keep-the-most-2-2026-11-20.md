---
title: Keep the most, part 2 - 2027 health cover, the MFFU question list, Saver's Match, closing 2026, payout plumbing (2026-11-20)
family: money
date: 2026-11-20
status: info - education, not tax or insurance advice. Research + plain owner steps only; nothing filed, no account opened, nothing live changed. Ideas #6, #7, #19, #20, #25 of research/handoff/2026-11-20/TOP25_IDEAS.txt.
summary: Maryland. (6) Health cover for 2027 - Maryland Health Connection open enrollment Nov 1 2026 - Jan 15 2027, enroll by Dec 31 for Jan 1; enhanced federal credits expired, Maryland Premium Assistance replaces them (100% under 200% FPL = $31,920) and the Young Adult Subsidy (18-33, fades to 37); Medicaid at <= $1,835 a month current income. Worth ~$1,500-4,000 a year if he has no cover. (7) One MFFU message drafted (live move freezes other accounts? bot on live? 1099 gross/net, one or two forms? EIN?). (19) 2027 Saver's Match: at $30k profit, $7,500 traditional Solo 401(k) gets the full $1,000 match + ~$1,204 tax saved vs ~$508 with Roth only. (20) Close 2026: log ~$315+ of 2026 evals, Claude plan, PC share; keep 2026 tax $0 -> no 2027 penalty; buy gear in January. (25) Tax pot in a Treasury money fund (~3.5-3.9%, mostly Maryland-tax-free) at a big broker, Rise -> bank the same day. Math: tools/money/keep_most.py magi_dial / savers_match -> research/lab/keep_most.json.
---

# Keep the most, part 2 (2026-11-20)

Education, not tax or insurance advice. Maryland, single filer. Builds on `research/writeups/keep-the-most-2026-11-20.md`.
Nothing here opens an account or files anything; the owner does each step himself.

## For the owner

| What | $ | Do it by |
|---|---|---|
| **Health cover for 2027** (only if you have none from a job / parent / spouse) | about $1,500 - $4,000 a year of help, or free Medicaid | **Dec 31** for Jan 1 (last day Jan 15 for Feb 1) |
| **2027 Saver's Match** (free federal money) | **up to $1,000 a year**: at $30k profit put $7,500 in a *traditional* Solo 401(k) -> $1,000 match + ~$1,204 less tax; Roth-only gets ~$508 | open the Solo 401(k) in 2027; claim on the 2027 return |
| **Close 2026 on purpose** | keeps 2026 tax at $0 -> no 2027 penalty at all; ~$80 - $150 by buying gear in January | **Dec 31** |
| **Tax pot in a Treasury money fund** | about $120 - $200 a year, mostly free of Maryland tax | before the first payout |
| **One message to MFFU** (draft below) | protects about $1,500 - $2,500 a month of 2027 payouts | send this week |

**Owner to-do (max 3):**
1. Tell Claude: do you have health cover for 2027 (job / parent / spouse / none), and are you under 34?
2. Copy the MFFU message below into MFFU support chat and paste their answer back here.
3. Before the first payout: open a free brokerage account with a Treasury money fund for the tax pot (Fidelity, Schwab or Vanguard; 20 minutes).

## 6. 2027 health cover (Maryland)

| Fact | Value | Source (checked 2026-11-20) |
|---|---|---|
| Open enrollment for 2027 | **Nov 1, 2026 - Jan 15, 2027**; enroll by **Dec 31** for a Jan 1 start; Jan 1-15 -> Feb 1 start. Medicaid: any time | WYPR, 2026-11-02 (marylandhealthconnection.gov refused automated reads) |
| 2026 poverty line, 1 person | $15,960 | HHS ASPE poverty guidelines |
| Maryland Medicaid, adult | **$1,835 a month** (138% FPL, $22,025 a year), from Feb 1, 2026; judged on **current monthly income** (a predictable rise can be counted) | Maryland Dept. of Health income limits; 42 CFR 435.603(h) |
| Federal enhanced credits | **expired after 2025**, no 2027 extension; the 400% FPL cliff ($63,840) is back | KFF, 2026-10-30 |
| Maryland Premium Assistance (state) | from Jan 1, 2026, continues in 2027: replaces **100%** of the lost federal help under 200% FPL ($31,920), about 50% at 250-400% | MHBE 2027 state subsidy parameters (Aug 2026) |
| Young Adult Subsidy | ages **18-33** under 400% FPL pay 2.5 points less of income; fades out to 37; none at 38+ | same (2027 at 2026 settings; confirm the adopted terms) |
| 2027 premiums | up 14.6% on average | same |

What it means: the subsidy is set on **expected 2027 MAGI** (profit minus half the SE tax minus traditional retirement
money minus the self-employed health deduction). The fleet plan's expected year (~$30-60k) is 190-375% FPL: under
$31,920 MAGI Maryland covers the full lost federal help; a traditional Solo 401(k) can pull MAGI under that line (and
under $35,500 for the Saver's Match, section 19). Write a conservative estimate on the application and update it when
income changes (too low an estimate = credit paid back at filing; above 400% FPL the whole credit can be clawed back).
Medicaid now: if he has no cover and Nov-Dec income is near $0, he may qualify today on current monthly income; the
expected January payout can be counted and Medicaid is re-checked, so treat it as a bridge, not a plan. Premiums for a
plan you pay yourself are deductible (self-employed health insurance deduction, Schedule 1) only for months with no
employer plan available. $ effect: ~$1,500-4,000 a year if uninsured (idea #6 estimate); $0 if he already has cover.

## 7. The MFFU support message (draft - the owner sends it himself)

> Hi, I trade Builder accounts (a 50K eval, two 25K, one funded) and a Rapid EOD 25K, all with an automated strategy on
> NinjaTrader that I set up myself. Before my first payouts, could you confirm in writing:
> 1. When a Builder account moves to live after its 5th payout, do my other sim-funded and eval accounts pause or go
>    dormant? Can I keep trading them, and what happens to their balances?
> 2. Is my automated strategy (my own settings, NinjaTrader) allowed on the live account, including while I am not at
>    the screen?
> 3. Is the 1099 for the GROSS amount you pay out or NET of your 20% / 10% split? Will I get one form, or one from MFFU
>    (ACH payouts) and another from Rise?
> 4. Can payouts be made to a business (an LLC or S-corp with its own EIN and W-9) instead of to me personally?
> 5. Is it OK to run a 2nd Builder 50K eval and a 2nd 25K eval while my current ones are running (within the 10-eval limit)?
> Thank you!

Why each one is worth asking: (1) MFFU's rulebook says once live, sim accounts go dormant (research/lit/mffu_rules.json
`sim_live_together`) - that could stop about $1,500-2,500 a month of 2027 fleet payouts, so the 5th payout of each Builder
should be planned around the answer; (2) the rulebook only says live automation "must follow CME rules"; (3) the form
should match what lands (80% / 90%): if the 1099 shows the gross, the 20% they keep must be shown as not his income, or he
over-pays ~$1,000-5,000 or gets an IRS letter; (4) unblocks the S-corp step later (~$1,460 a year at $60k); (5) is the
already-approved ask-mffu-parallel card. No account ids, no name - he sends it from his own login.

## 19. 2027 Saver's Match with a traditional Solo 401(k)

IRS Notice 2026-48 (Aug 7, 2026): from tax year 2027 the Saver's Match replaces the Saver's Credit: **50% of up to $2,000
of retirement contributions = up to $1,000**, single MAGI **$20,500 -> $35,500** (sliding, no cliff; e.g. ~19% at
$30,000), claimed on new Form 8880-A on the 2027 return, paid from 2028 **into a traditional IRA or pre-tax 401(k)** (not
straight into a Roth; the account must be registered with Treasury). Roth contributions count toward the $2,000 but do
not lower MAGI; traditional ones do. Not taxed when deposited. Students and dependents are not eligible.

keep_most.magi_dial (2027, Maryland highest county, no other income):
| Profit | MAGI before | Roth $2,000 only: match | Traditional needed for the full $1,000 | Match + tax saved |
|---|---|---|---|---|
| $20,000 | $18,587 | $1,000 | $2,000 | $1,320 |
| $25,000 | $23,234 | $818 | $3,000 | $1,482 |
| $30,000 | $27,881 | $508 | $7,500 | **$2,204** |
| $40,000 | $37,174 | $0 | $17,000 | $3,802 (a lot locked away) |
| $50,000 | $46,468 | $0 | $26,000 | $5,395 (most of the year) |
Change to the ladder in part 1: in a $20-35k profit year, **traditional beats Roth** (the match and Maryland's subsidy both
key off MAGI). Above ~$40k reaching the band means locking away more than half the year's income - only if he can live
without it. Confirm with the Solo 401(k) provider that it accepts the match deposit; otherwise a traditional IRA receives it.

## 20. Close 2026 on purpose

Goal: 2026 ends with **$0 total tax** (if he has no day job), which makes **every 2027 estimate penalty-free**, however big
2027 gets (IRS Pub 505: no penalty if last year's tax was $0 for a full year).
- **Log every 2026 cost by Dec 31** (Ledger app, category "trading costs" / "software & AI"): Builder 50K $91.80, each
  Builder 25K ($63 / $43), Rapid EOD 25K $97.20, every earlier or failed eval and reset (MFFU order history), market data,
  NinjaTrader, the business share of the Claude plan, of internet and of the PC. Tonight's four accounts alone are ~$315.
- **A December payout** (payday plan: 8 in 10 runs Dec 8 - Feb 26) is 2026 income. With the fees logged, $800 minus
  ~$315+ leaves under ~$485 of profit: SE tax applies only from $400 of SE earnings (~$68 at $485), income tax $0 under the
  standard deduction. If a request becomes possible in the last days of December, asking on Jan 1 instead moves it to 2027
  and keeps 2026 at exactly $0 (his choice; it costs a few days).
- **Buy deductible gear in January** (e.g. the mini PC): a 2026 deduction is worth ~$0 in a $0-tax year, the same buy in
  2027 is worth ~25-30% (federal + SE + Maryland), about $80-150 on a $249-500 item.
- **The Claude plan**: the business-use share is a software cost (Schedule C line "other expenses"); keep the monthly
  receipts and one line on how the % was picked. Worth ~$300-750 a year in a profitable year depending on the plan.
- With a day job, 2026 tax will not be $0; then 100% of the 2026 tax (110% for Maryland) is the 2027 target instead.

## 25. Payout plumbing

| Bucket | Where it lives | Why |
|---|---|---|
| Landing | Rise (USDC balance) or MFFU ACH -> checking | Rise -> US bank by ACH is free, usually 1 business day (Rise help center; its older blog says $20 - check the screen). **Sweep the same day**: a Rise balance is a stablecoin, not FDIC-insured; never keep tax money there or in "Rise Earn" |
| Tax pot (30-40%) | **Treasury money fund** at a free brokerage: Vanguard VUSXX (~3.8-3.9% Oct 2026, $3,000 min), Fidelity FDLXX/SPAXX (~3.5%, $0), Schwab SNSXX (~3.5%, $0) | the US-government share of its dividends is subtracted on Maryland Form 502SU (no 50% test), so ~3.8% there ~ a 4.1% savings account after Maryland tax; pay IRS / Maryland straight from it |
| Eval reserve ($320) | checking | buys and re-buys the same night |
| Retirement (10%) | Roth IRA / Solo 401(k) at the same brokerage | one login |
| Live fund (to $5,000) | the same brokerage, cash or the same Treasury fund | grows until the trigger (part 1) |
| Yours | checking | |
Interest: ~$120-200 a year on a pot of $3,000-5,000. Main value: the tax money is never spent by accident and no more than
one payout ever sits at one firm. Yields move; check the fund page on the day.

## Sources (checked 2026-11-20)
- Maryland open enrollment 2027: https://www.wypr.org/wypr-news/2026-11-02/maryland-health-insurance-open-enrollment-begins-for-2027
- HHS poverty guidelines 2026: https://aspe.hhs.gov/topics/poverty-economic-mobility/poverty-guidelines
- Maryland Medicaid income limits: https://health.maryland.gov/mmcp/eligibility/Pages/incomelimits.aspx ; 42 CFR 435.603: https://www.ecfr.gov/current/title-42/chapter-IV/subchapter-C/part-435/subpart-B/section-435.603
- KFF 2027 open enrollment: https://kff.org/affordable-care-act/9-things-to-watch-for-the-2027-aca-open-enrollment-period/
- MHBE 2027 state subsidy parameters: https://www.marylandhbe.com/wp-content/uploads/2026/08/2027-Final-State-Subsidy-and-Estimated-Reinsurance-Parameters.pdf
- IRS Notice 2026-48 (Saver's Match): https://www.irs.gov/pub/irs-drop/n-26-48.pdf ; IRS news: https://www.irs.gov/newsroom/treasury-irs-begin-implementing-executive-order-14403-by-announcing-intent-to-issue-proposed-regulations-on-savers-match-which-will-benefit-millions-of-low-and-moderate-income-taxpayers
- Money fund yields: https://investor.vanguard.com/investment-products/money-markets , https://www.schwabassetmanagement.com/products/money-fund-yields (Fidelity from a secondary review)
- Maryland subtraction for US obligations: https://mgaleg.maryland.gov/2026RS/Statute_Web/gtg/10-207.pdf
- MFFU first payout / Rise: https://help.myfundedfutures.com/en/articles/11542406-guide-to-your-first-payout-quick-and-easy-process ; Rise withdrawals: https://help.riseworks.io/en/articles/10091403-withdrawal-fees-minimums
- MFFU rules (dormant after live): research/lit/mffu_rules.json
