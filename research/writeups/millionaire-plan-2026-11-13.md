---
title: The millionaire plan (M1, 2026-11-13) - from prop-firm evals to $1M. In a market like Jul-Oct 2026, 10 LIT accounts pay about $6,900 a month in year 1 and $100K in about 14-18 months; $1M from prop payouts alone takes about 10 years, and about 4-5 years only if a personal account compounds the same edge. In a 2021-25 market it pays nothing, and the only protection is a stop rule on eval buying
family: risk
date: 2026-11-13
status: adopt-candidate (one rule, owner decides; paper only, nothing live changed) - the "stop" reset rule for every account (an account stops buying evals once its own running net is 5 eval prices below its best): it cuts the eval cash a 2021-25-like market eats by 90-96% and costs 1-3% in a 2026-like market.
summary: Owner 2026-11-12 - "You're gonna make me a million of trading prop firms and eventually live accounts, so think like a millionaire." The whole business was run as a Monte Carlo (tools/millionaire_mc.py, 400 paths of 10 years, whole weeks of real LIT trades drawn from Jan-Jun 2026 = H1 pick, Jul-Oct 2026 = H2 check, 2021-25 = REF). Each account = the uprisk engine (MFFU Builder eval on the live two_week sizing, 2 sessions of paperwork, Sim Funded on the live funded preset, 80% payouts, lost or 5 payouts then the next eval), all accounts on the same market path (copies are one bet), $1.90 a micro. H2, year 1, $ a month after every eval fee - 1 account $874, 3 (the MFFU cap) $1,629, 5 $3,221, 10 $6,886; the ladder (3, then 5 at the first payout, then 10 at $10K net) $4,903, then $8,457 a month in years 2-3, $100K after a median 18 months. $1M from prop payouts alone - 36% of H2 paths in 10 years, 0% in 5. With a personal futures account (seeded with $25K once $30K is kept after tax, LIT at 1% of the account a trade) - $1M after a median 52 months (85% within 5 years); in a 2021-25 market 0%. REF - every fleet loses a little (1 account +$5, 10 accounts -$148 a month) and keeps buying evals - $4.6K to $57K of eval cash at the 95th percentile; the stop rule caps that at $459 (1 account) to $4,603 (10). Firm prices and codes checked on the web 2026-11-13 (sources below; the firms' own pages cannot be opened from this machine, so every price is unconfirmed until checkout).
runs: none (business Monte Carlo, not a strategy test; stored in research/lab/millionaire_mc.json)
---

Team M1, 2026-11-13. Paper research only. Tools: `python -X utf8 tools/millionaire_mc.py` (400 paths x 120 months, about
45 minutes; `--quick` 1 minute; `check` = the account engine equals `tools/uprisk.py` on the same paths) and
`python tools/money/prop_plan.py` (the plan card JSON for the Money page, `tools/web_public/money/prop_plan.json`).

## 1. Money first

H2 = trades of Jul-Oct 2026 (the check half, the one to quote). REF = 2021-25 (LIT shows no edge there). $ a month after
every eval fee, before tax. "Cash to keep" = the most the eval fees ran ahead of payouts (95th percentile): the money you need
on hand so the plan never stops for lack of cash.

| Fleet | Year 1 $ a month (H2) | Worst 1 in 10, year 1 | Years 2-3 $ a month | Cash to keep for evals | $100K (median months) | $1M within 5 years: prop only / with a personal account | 2021-25 market: $ a month, cash to keep (no stop rule / stop rule) |
|---|---:|---:|---:|---:|---:|---|---|
| 1 account (Zlarior 50K) | **$874** | $518 | $956 | $275 | 106 | 0% / 0% (median 103 months) | +$5, $4,553 / **$459** |
| 3 accounts (MFFU's cap: 50K + 25K + 25K) | **$1,629** | $1,006 | $1,822 | $682 | 57 | 0% / 1% (median 80) | -$12, $9,835 / **$963** |
| 5 accounts (+ 2 other-firm 50Ks from day 1) | **$3,221** | $2,000 | $3,718 | $1,347 | 29 | 0% / 39% (median 64) | -$53, $22,125 / **$2,003** |
| 10 accounts (from day 1) | **$6,886** | $4,227 | $8,462 | $2,676 | 14 | 0% / 93% (median 49) | -$148, $57,276 / **$4,603** |
| **The ladder** (3 now, 5 at the first payout, 10 at $10K net) | **$4,903** | $1,732 | **$8,457** | **$682** | **18** | 0% / **85%** (median **52**) | -$24, $24,057 / **$963** |

H1 (Jan-Jun 2026) gives the same picture, a little better: ladder $5,253 / $8,623 a month, $100K in 17 months, $1M with a
personal account in a median 43 months. Prop payouts alone reach $1M within 10 years on 36% (H2) / 44% (H1) of paths: the
ladder's 10-year median is $958K.

**What the numbers say, plainly:**
- **The edge pays, the evals are cheap.** One LIT 50K account makes about $10,500 in its first year (H2) on about $214 of
  evals: about $49 for every $1 of eval fees. A 25K copy makes $33 per $1, an other-firm 50K (at $130 an eval) $35 per $1.
- **More accounts = more money, almost in a straight line, but they are one bet.** All copies trade the same LIT signal, so a
  bad month hits all of them together. Each account can only cost you its eval price.
- **The ladder is the best shape.** It earns about 70% of the 10-account fleet's year 1, needs only $682 of cash (a quarter),
  and in a 2021-25 market it never grows: only 32% of those paths ever buy account 4 (with the stop rule).
- **$1M is a 4-5 year goal only if the edge holds AND a personal account compounds it.** Prop payouts alone are capped by the
  firms (payout caps, 5 payouts an account, account caps per firm): about $100K a year at 10 accounts.
- **In a 2021-25 market none of this works.** Every fleet is about break-even to slightly negative and keeps buying evals.
  The stop rule is what keeps that cheap.

## 2. Each account, per strategy and per firm

One account alone, 6 months of eval -> funded -> payouts -> next eval, net of every eval (`research/lab/rd_money.json`, 1,000
paths; 2-week pass / fail from `research/lab/millionaire_mc.json`, 1,000 fresh 60-session evals). H1 / H2 / REF.

| Account (strategy, firm, price) | $ a month to you | 2-week pass / fail % | Median sessions to pass | Year-1 $ per $1 of eval fees (H2) |
|---|---|---|---:|---:|
| **Zlarior LIT, MFFU Builder 50K, $91.80** | $823 / **$798** / -$7 | 52.9/17.8, 58.6/20.9, 20.7/24.9 | 6 / 5 / 8 | **$49** |
| ATLAS, MFFU Builder 25K, $43 | $568 / **$382** / -$2 | 65.5/0.8 (H1, `atlas-funded.md`) | - | - |
| LIT copy, MFFU Builder 25K, $63 (room 0.8) | $375 / **$331** / -$15 | 55.0/10.6, 57.8/17.3, 20.0/23.2 | 6 / 5 / 7 | $33 |
| BLITZ, MFFU Builder 25K, $63 | $286 / **$52** / -$39 | 47.9/23.5, 36.2/21.7, 24.7/48.4 | - | - |
| LIT, other-firm 50K (Lucid / FundedNext, MFFU 50K rules as the proxy, $130) | $812 / **$788** / -$25 | as the MFFU 50K | 6 / 5 / 8 | $35 |

- ATLAS is the best second signal: its daily results do not move with LIT's (-0.01 / -0.03 / +0.11), while LIT copies move
  together (0.8-0.9). The E2 / E3 studies (2026-11-13) found no other stream: new NQ families, ES and other sessions all fail.
- BLITZ is the weakest slot. A LIT copy on that 25K pays more in all three spans (`2026-11-03-money-plan.md`), once MFFU says
  yes in writing to the same bot on two of your accounts.
- **Eval sizing (team G2, `eval-guard-2026-11-13.md`, a proposal):** risking 40% of the room per trade instead of 80% is worth
  about $835-1,000 more per fresh eval (2-week fail 0.5% instead of 22-26%). This plan uses today's live sizing; with the
  proposal every number above gets a little better.

### The firms (checked on the web 2026-11-13; the firms' own pages are DNS-blocked here, so every value is a search reading)

| Firm, plan | Your price / list | Codes seen (unconfirmed) | Drawdown, daily loss | Consistency | Payouts, split | Accounts | Bots, copying your own accounts |
|---|---|---|---|---|---|---|---|
| **MFFU Builder 50K** | **$91.80** (your 40% code) / $153 | rotating 5-50%; "FundedTrading" (Jul 2026); activation fee removed 2026-08-25, one-time | $2,000 EOD trailing, locks +$100; $1,000 soft daily | none in the eval; funded best day <= 50% | $500-2,000 a cycle, 80%; 5 sim payouts then live | 1 funded 50K + 2 funded 25K per person (house rule found 2026-11-03; other sites say 5 funded, 10 evals) | bots with you present for live; **copying: sources conflict - ask MFFU in writing** |
| MFFU Builder 25K | **$63** (ATLAS's $43) / $105 | same | $1,000 EOD; $600 soft daily | same | $250-1,000, 80% | in the cap above | same |
| **LucidPro 50K** | about $115-135 with a code / $192 | DGT 30% -> $134.40; PFD / VIBES 35-50% (claims) | $2,000 EOD; $1,200 soft daily (optional) | none in the eval; funded best day <= 40% | $2,000 then $2,500, 90%; 5 payouts then a live review | 5 funded per household | **bots and trade copiers allowed** in Lucid's terms (edited 2026-08-26) |
| **FundedNext Rapid 50K** | about $160-200 list (sources conflict) | FT 55%, VIBES 30%, up to 47% (Aug 2026) | $2,000 EOD; $1,000 soft daily (Rapid Daily) | none (Rapid Daily) | $250-1,200 any day, 90%; live review after 15 rewards | copying up to 5 accounts / $300K (sources conflict) | bots allowed |
| Topstep 50K | $49 a month | - | - | best day 50% | - | - | **ruled out**: no NinjaTrader for new sign-ups, bots banned on Live |
| Bulenox 50K | about $115 a month (promos $30-50) | - | $2,500 EOD | best day 40% | weekly, 100% of the first $10K | Masters merged into one at live | approval needed, copying unclear: not yet |
| Apex, Take Profit Trader, Alpha, Elite, Tradeify | - | - | - | - | - | - | **ruled out** for this bot (automation banned or same-bot-elsewhere banned; `prop-firms-hub.md`) |

**When to buy:** Black Friday is 2026-11-27; last year the futures firms ran sales from about Nov 19 to Dec 1 (FundedNext
15-25%), and MFFU ran a January sale in 2025. No firm has confirmed a 2026 sale yet. If the next purchase is due in late
November, wait for that week; never delay a step by more than a month for a code (one month of a 50K is worth ~$800).

## 3. Scaling: how to grow without blowing up

- **Parallel evals, a week apart.** Each new account starts 5 sessions after the last one, so they do not pass or fail on the
  same days. In the ladder (H2) account 4 starts in a median 1.9 months (at the first payout) and account 6 in 5.1 months.
- **Copy trading.** The plan needs one signal on many accounts. Lucid allows copiers in writing. FundedNext and MFFU sources
  conflict: get a written yes from each firm before putting the same bot on two accounts there.
- **Reset policy (tested three ways, same paths):**

| Rule | 10 accounts, H2 year 1 / years 2-3 $ a month | Ladder, H2 year 1 / years 2-3 | Ladder 10-year median (H2) | 2021-25: cash to keep, 1 account / 10 / ladder |
|---|---|---|---:|---|
| Rebuy the next day (today) | $6,886 / $8,462 | $4,903 / $8,457 | $958K | $4,553 / $57,276 / $24,057 |
| Breaker: 3 fails in a row -> pause 2 months | $6,851 / $8,417 | (not run) | - | $4,000 / $54,279 / - |
| **Stop: an account 5 eval prices below its best buys no more** | **$6,819 / $8,260** | **$4,864 / $8,209** | **$942K** | **$459 / $4,603 / $963** |

  The breaker barely helps (a 2021-25 market is not 3 fails in a row, it is pass, lose the funded account, fail, pass...). The
  stop rule caps every account's worst case at about 5 eval prices ($460 on a 50K, $315 on a 25K) for 1-3% less in a good
  market. **Adopt it.** Restarting a stopped account is the owner's call, after the live results are back in the backtest's band.
- **Risk of ruin, honestly.** The business cannot lose more than the eval fees (the funded accounts are the firm's money). With
  the stop rule the worst case is the cash-to-keep column: $459 for one account, $963 for the ladder in a 2021-25 market. The
  real risk is not ruin, it is **time**: in a 2021-25-like market the plan earns about $0 for years.
- **Variance.** Even in H2, a single account has a $0-or-less month about half the time in year 1 (waiting for a pass, the
  paperwork, a lost account). The ladder's worst 1 in 10 year 1 is $1,732 a month against a median $4,903.
- **Not in the model:** the $3,000 cross-account risk cap of `scale-plan.md` (proposed, not built). At 10 LIT copies one trade
  risks $5,000-8,000 of firm money at once; the cap would cut that and the $ above with it.

## 4. Your own live account (short; not financial or tax advice)

- **Two different "live":** a prop firm moves a good funded account to its own live account (MFFU after 5 sim payouts, Lucid
  after 5 payouts, FundedNext after 15 rewards). That is still the firm's money. A **personal** account is your money, at a
  futures broker, with no firm to absorb a loss.
- **When (the rule in the model):** once $30,000 is kept after a 30% tax set-aside AND 3 months of live fills are within the
  backtest's band. Put $25,000 in, plus half of every later after-tax prop month.
- **How much:** LIT at 1% of the account a trade (MNQ micros = 1% / the stop's risk, so a $25K account trades 2-6 micros).
  No firm rules, no daily payouts, no consistency rule; the stop-loss discipline is yours.
- **Model result (H2):** the switch happens after a median 11 months on the ladder; wealth (kept cash + the account) is a
  median $163K at 2 years, $1.59M at 5 years (1 in 10: $839K). **In a 2021-25 market the account never starts on 81% of
  paths** (the $30K trigger is never reached), and where it does, it loses.
- **Read the 5-year line as "possible if the edge holds", not as a forecast.** It compounds 2026's edge (profit factor 2.9)
  for 5 years. Beyond 5 years the model's numbers ($47M median at 10 years) are not real: NQ liquidity, slippage at size and
  edge decay are not modelled. Taxes: prop payouts are usually contractor income; personal futures gains are 60/40 (Section
  1256). Ask a tax professional before the first payout.

## 5. The step ladder (also on the Money page, `prop_plan.json`)

| Step | When | Buy | Accounts | $ a month, year 1 (H2 / 2021-25) |
|---|---|---|---:|---|
| **0. Pass the two live evals (now)** | now: Zlarior 50K ($1,145 room, $3,687 to go) and ATLAS 25K ($822, $1,678 to go), BLITZ 25K on paper | nothing | 3 | $0 until a pass |
| 1. Funded at MFFU | an eval passes ($53,000 / $26,500) | nothing; a failed eval is bought again the next day, under the stop rule | 3 | $1,629 / -$12 (3 LIT-type accounts) |
| 2. Two LIT 50Ks at Lucid / FundedNext | the first payout is in your bank AND each firm said yes in writing to bots + copying | LucidPro 50K + FundedNext Rapid 50K, a week apart (about $300) | 5 | $3,221 / -$53 |
| 3. Ten accounts | $10,000 net paid out, no funded account lost in the last 2 weeks | 4 more LucidPro 50K + 1 FundedNext 50K, one a week (about $700) | 10 | $6,886 / -$148 |
| 4. Your own live account | $30,000 kept after tax AND 3 months of live fills within the backtest's band | $25,000 into a personal futures account; LIT at 1% a trade | 10 + 1 | $1M within 5 years on 85% of H2 paths, 0% of 2021-25 paths |

**Stop rules (all steps):** an account 5 eval prices below its best buys no more evals; live results 30 trades behind the
backtest (profit factor under 1.0) -> buy no new evals anywhere until they recover; never long on one account and short on
another; keep 30% of every payout for tax.

Today the owner is on step 0: about $1,180 a month once both live evals are funded (Zlarior $798 + ATLAS $382, H2), -$9 in a
2021-25 market.

## 6. Honest limits

- **Everything rests on 2026.** H1 has 26 weeks and H2 15 weeks of trades; the 10-year paths re-draw those weeks. LIT has no
  edge in 2021-25 (profit factor about 1.0). If 2027 looks like 2021-25, the plan makes about $0 and the stop rule keeps the
  loss to a few hundred dollars.
- **No live fills yet.** Real slippage is not yet measured (`eval-guard-2026-11-13.md` step 2: the modelled gap is about $100
  a month at LIT size). Backtests overstate.
- **Other firms are modelled with MFFU's 50K rules** (80% split, MFFU's payout caps). Lucid and FundedNext pay 90% but have
  their own caps and consistency rules; the per-firm numbers in `lit-funded-firms.md` (H2 6-month net: Lucid ~$631, FundedNext
  ~$561, MFFU 50K ~$562 a month at the older sizing) are the closer read.
- **Firm rules and prices change**, and every value in the firm table is a search-engine reading of affiliate and review
  pages (2026-11-13), not the firms' own pages. Confirm the price at checkout and the copy / bot rules in writing.
- **Firm risk is not modelled:** a firm refusing a payout, closing accounts, changing rules mid-way or going out of business.
  Spread accounts over firms (the ladder does).
- **The fleet is all LIT** (one signal). ATLAS on more accounts would lower the correlation but pays less per account; not
  modelled at other firms.
- The $3,000 cross-account cap and a 10-copies detection risk at a firm are not modelled.

## Sources (web, read 2026-11-13; unconfirmed until checkout)

- MFFU: [dev.to review 2026 (rotating codes 5-50%)](https://dev.to/propfirmkey/my-funded-futures-review-2026-rules-pricing-scaling-discount-code-win-50-off-4m45),
  [fundedtrading.com (code, Jul 2026)](https://fundedtrading.com/propfirm/my-funded-futures/),
  [eltraderfinanciado (activation fee removed 2026-08-25)](https://www.eltraderfinanciado.com/th/discounts/myfundedfutures),
  [proptradingvibes position limits](https://proptradingvibes.com/blog/myfundedfutures-position-limits),
  [tradecopia (5 sim-funded, copying)](https://tradecopia.com/propfirms/my-funded-futures),
  [LuxAlgo (copying allowed)](https://www.luxalgo.com/prop-firms/my-funded-futures/),
  [TradingFinder (says bots / copying banned)](https://tradingfinder.com/props/my-funded-futures/rules); house facts in
  `research/props/firms.json` and `2026-11-03-money-plan.md`.
- Lucid: [damnpropfirms LucidPro 50K ($192, DGT 30% -> $134.40)](https://damnpropfirms.com/account-plans/lucid-trading-pro-50000/),
  [proptradingvibes (VIBES ~35%)](https://proptradingvibes.com/blog/lucid-trading-discount),
  [flux.ai (PFD claims)](https://www.flux.ai/lucid-trading-coupon-code-pfd),
  [The Defiant (live program overhaul)](https://thedefiant.io/news/markets/lucid-trading-rolls-out-major-live-program-overhaul-and-launches-lucidmaxx);
  rules in `lit-funded-firms.md`.
- FundedNext: [propfirmmatch Rapid Daily 50K](https://propfirmmatch.com/futures/prop-firm-challenges/fundednext-futures-rapid-daily-1-step-50k),
  [JP Trading Capital (up to 47%, Aug 2026)](https://www.jptradingcapital.com/blog/en/fundednext-discount-codes),
  [proptradingvibes (VIBES 30%)](https://proptradingvibes.com/blog/fundednext-promo-code),
  [thegodfunded (copying limits)](https://thegodfunded.com/en/firms/fundednextfutures),
  [Save On Prop Firms Black Friday page (2026 sales not confirmed)](https://saveonpropfirms.com/black-friday).
- Topstep: [Topstep pricing (help centre)](https://intercom.help/topstep-llc/en/articles/9208217-topstep-pricing). Bulenox:
  [Topstep vs Bulenox 2026](https://w1337-cyber.github.io/aurafy-growth-assets/blog/topstep-vs-bulenox-2026/).

## Rerun

```
python -X utf8 tools/millionaire_mc.py check          # account engine == tools/uprisk.py
python -X utf8 tools/millionaire_mc.py                # 400 x 10 years -> research/lab/millionaire_mc.json (~45 min)
python tools/money/prop_plan.py                       # -> tools/web_public/money/prop_plan.json
python -X utf8 -m tests.test_prop_plan
```
