---
title: Prop economics - the firm's payout math, not only edge. Searched eval/funded sizing, lanes, payout asks, close rules, account count and re-buy rules on the real trade lists; picked on Jan-Jun 2026, reported on Jul-Oct and 2021-25
family: money
date: 2026-11-23
status: done - research only, nothing bought, nothing armed, no live file touched (live_model*.json, engine/* unchanged)
summary: Built on the repo's real-fills engine (research/plans/rank.py via research/onebook/book.py and research/fleet/fleet.py; LIT as stored, ATLAS at 10-tick fills, BLITZ as stored, $1.90 a micro, soft-day cuts, MFFU Rapid news window). Stage 1 = one account slot, 6 account types x 100 phase policies x 3 markets x 500 paths. Stage 2 = the whole business under a $150 / $300 / $500 monthly budget, 432 fleets searched on Jan-Jun 2026 paths only (300 paths), top 3 per budget + today's plan re-scored on 1,000 paths in all three markets. Best policy at $300 / $500 - rotate Rapid EOD 50K -> FundedNext 50K -> LucidPro 50K and add the BLITZ lane (at $300 risk) to every NEW eval, funded books as today, close Builders after payout 4, no re-buy stop - beats today's plan by +$2.1k / +$2.5k a month (Jan-Jun / Jul-Oct-like) at $300 and +$3.5k / +$3.5k at $500. At $150 the best is Rapid EOD 50K first, then Lucid, BLITZ in the eval (+$4.4k / +$1.8k a month). Blunt part - in a 2021-25-like market NO policy found is +EV: the best loses about 20% of its fees; the "break-even strategy can still be +EV" idea does not hold on our 2021-25 trades, because eval pass rates fall to 15-28% and 80-100% of funded accounts die before paying. Two inputs are not approved/verified - BLITZ is paper-only/hidden, Lucid's price ($126) and account cap (3) are assumptions and the owner's rule today is "MFFU only". A clean alternative that needs no new strategy is given.
runs: research/propecon/unit.py -> unit_results.json; evformula.py -> evformula.json; search.py search -> search_h1.json; search.py final -> final.json; decomp.py -> decomp.json; litonly.py -> litonly.json (post-hoc); fill.py -> fill.json
---

## For the owner (one minute)

| Budget a month | Today's plan: $/month (Jan-Jun-like / Jul-Oct-like / 2021-25-like) | Best policy found | Its $/month (same 3 markets) | Gain a month (Jan-Jun / Jul-Oct) |
|---|---|---|---|---|
| $150 | $5,783 / $4,455 / -$22 | **#2** Rapid EOD 50K first, then Lucid, BLITZ in the eval | $10,218 / $6,281 / -$70 | **+$4,435 / +$1,826** |
| $300 | $12,608 / $7,335 / -$122 | **#1** rotate Rapid EOD 50K -> FundedNext 50K -> Lucid, BLITZ in the eval | $14,678 / $9,869 / -$139 | **+$2,070 / +$2,534** |
| $500 | $13,415 / $7,952 / -$234 | **#1** (same) | $16,945 / $11,495 / -$252 | **+$3,530 / +$3,543** |

$/month = the 6-month net (payouts to you after the split, minus every fee) / 6, mean of 1,000 paths. Months 1-2 are low (the first eval has to pass): month-by-month at $300 #1 in a Jan-Jun-like market: $1.1k, $9.4k, $15.5k, $18.5k, $20.8k, $22.8k.

- **The big lever is the firm, not the size.** Rapid EOD 50K (no payout cap, daily payouts, 90%) earns $87-200 per eval dollar in 2026-like markets; Builder 25K earns $31-35. Most of today's money already comes from that choice.
- **"Aggressive in the eval" only works where the eval has a consistency rule.** On Builder / FundedNext / Lucid evals, doubling size cuts the pass rate from 84% to 55%: you fail fast and cheap, but under a budget that is a loss. On the Rapid EOD eval (best day <= 30%), adding the BLITZ lane gives more small winning days: pass 79% -> 87% (25K), 10% -> 17% in 2021-25-like markets (50K), and about 8 sessions sooner.
- **Conservative funded beats aggressive funded.** Never size the funded account up. LIT-only on the funded account halves the 2021-25 loss but costs about 40% of the 2026 money; today's funded books stay.
- **Never take Builder payout 5.** It moves you live and every MFFU sim account goes dormant: -$2,661 a month at $300 (Jan-Jun-like), 59% of paths hit it.
- **No re-buy stop, no stagger.** Stopping after 3 dead accounts in a row cost $0.4-3.1k a month in Jan-Jun-like markets; spacing buys a week apart cost $0-480. Re-buy whenever the budget allows.
- **The honest bad case:** if the market goes back to 2021-25, every policy loses its fees slowly (-$22 to -$307 a month; 80-90% of paths are negative after 6 months). No sizing or payout trick fixed that. The best we found in that world (LIT only in both phases on Builder 50K + FundedNext 50K) still loses about 20% of the fees in 6 months.

**Your yes is needed for two things before any of this is real:** (1) BLITZ in new evals only (it is paper and hidden today, a strategy change by our own rules), and (2) Lucid accounts (you said "MFFU only"; Lucid's $126 price and the cap of 3 are not verified). Without both, use the clean option below.

## The top 3 policies (exact rules)

All three keep these common rules (they were tested and won or tied):
1. **Firm rules exactly** (docs/ACCOUNT_RULES.md): MFFU at most 5 accounts in eval + funded together, per type Builder 50K 1, Builder 25K 2, Rapid EOD 3 per size; FundedNext at most 2 at once and stop at its 15th payout (live review); Lucid at most 3 (ASSUMED). Bulenox is out (copying across your own accounts is banned + bots need approval); Tradeify, Apex, Alpha, Take Profit Trader, Topstep out (bots / NinjaTrader).
2. **No hedging:** every account trades the same three streams (LIT, ATLAS, BLITZ), and the stored streams are already built so ATLAS never enters against LIT and BLITZ never against LIT or ATLAS (ATLAS / BLITZ close first when LIT turns). So no account is ever opposite another, in any firm. Copying our own bot across our own accounts is allowed at MFFU, FundedNext (own accounts only) and Lucid.
3. **Budget:** $B arrives at the start of each month, unused money rolls over, payouts are never spent on fees. Buy the first type in the order below that fits the budget and the caps; buy as many as fit (no stagger); a failed eval or a dead funded account is replaced the next session (no re-buy stop).
4. **Funded:** today's funded books (LIT funded preset UP50 / UP25 + ATLAS lane $500 50K / $250 25K, never sized up). Payout asks as today: Builder / FundedNext / Lucid ask the cap ($2,000 / $1,000 / $1,200 / $2,000-2,500), Rapid EOD the bot's rule (keep $1,000 / $500 above the buffer, $500 / $250 net since the last payout).
5. **Close a Builder after payout 4** (never take the 5th). Rapid EOD: never a $10,000 day (our sizing tops out near $2,000).
6. **Your 4 accounts today stay exactly as they are** (sunk; Zlarior 50K eval LIT, ATLAS 25K funded, Rapid EOD 25K eval, Zlarior 25K #2 eval). The policy only changes NEW buys.

| # | Name | Buy order (new evals) | Eval book (new evals) | Funded book | Jan-Jun / Jul-Oct / 2021-25 $/month at $150 · $300 · $500 |
|---|---|---|---|---|---|
| **1** | Rotate 3 firms + BLITZ eval | Rapid EOD 50K ($165) -> FundedNext Rapid Daily 50K ($149.99) -> LucidPro 50K ($126 assumed), taking turns | LIT + ATLAS as today **+ BLITZ at $300 risk a trade** (30% of the room cap) | today's | $7,228 / $5,135 / -$46 · **$14,678 / $9,869 / -$139** · **$16,945 / $11,495 / -$252** |
| **2** | Rapid EOD 50K + Lucid, BLITZ eval | Rapid EOD 50K first (up to 3), then LucidPro 50K | same as #1 | today's | **$10,218 / $6,281 / -$70** · $14,017 / $8,713 / -$165 · $14,838 / $9,354 / -$307 |
| **3** | Rotate 3 firms, BLITZ 2x on Rapid only | as #1 | Rapid EOD evals: LIT x2 + ATLAS x2 + BLITZ $300; every other eval as today | today's | $6,981 / $4,706 / -$32 (at $150 Rapid-only order: $9,830 / $4,713 / -$42) · $13,781 / $8,627 / -$114 · $15,813 / $10,050 / -$207 |
| today | fleet plan (research/fleet) | $150: FundedNext 50K, then Rapid EOD 50K; $300 / $500: Rapid EOD 50K + FundedNext 50K taking turns | LIT + ATLAS (Rapid EOD 50K: LIT x0.5) | today's | $5,783 / $4,455 / -$22 · $12,608 / $7,335 / -$122 · $13,415 / $7,952 / -$234 |
| clean | no new strategy (Lucid only) | as #1 | today's | today's | $6,536 / $4,522 / -$40 · $12,805 / $8,254 / -$145 · $14,531 / $9,571 / -$251 |

Pick per budget (pre-set rule: best Jan-Jun-like 6-month net): **$150 -> #2, $300 -> #1, $500 -> #1.** Jul-Oct agrees at $300 and $500 (#1 is also the best Jul-Oct row); at $150 #2 is also the best Jul-Oct row.

Where the gain comes from ($300, $/month Jan-Jun / Jul-Oct, 1,000 paths): BLITZ in the eval alone (today's buy order) +$980 / +$488; Lucid in the rotation alone +$197 / +$919; both together +$2,070 / +$2,534 (they help each other: BLITZ passes evals faster, Lucid gives the faster evals somewhere to go once MFFU's 5 slots and FundedNext's 2 are full). Noise: the standard error of a 6-month net is about $1,000-1,300 (about $200 a month), so the gains above are 2-12 standard errors; the BLITZ-alone Jul-Oct gain is the weakest (about 2).

## EV per eval dollar (one account, fresh, 6 months of funded life)

EV = P(pass within 60 sessions) x E(your $ from that funded account before it dies or is closed) - fee. Activation is $0 on every plan here.
Today's books, 1,000 paths. ("x" = EV per $1 of fee.)

| Plan (price) | Jan-Jun-like: pass %, E(funded $), EV, x | Jul-Oct-like | 2021-25-like | Funded lost (2021-25) |
|---|---|---|---|---|
| MFFU Rapid EOD 50K ($165) | 94%, $35,280, **+$32,963, x200** | 90%, $16,212, +$14,378, x87 | 10%, $770, -$90, x-0.54 | 100% |
| MFFU Rapid EOD 25K ($97.20) | 79%, $16,357, +$12,874, x132 | 86%, $6,445, +$5,413, x56 | 7%, $349, -$73, x-0.75 | 100% |
| LucidPro 50K ($126 assumed) | 84%, $7,690, +$6,318, x50 | 85%, $8,149, +$6,768, x54 | 19%, $127, -$101, x-0.80 | 97% |
| MFFU Builder 50K ($91.80), close after payout 4 | 84%, $5,395, +$4,429, x48 | 85%, $5,355, +$4,439, x48 | 19%, $186, -$56, x-0.61 | 97% |
| MFFU Builder 25K ($63), close after payout 4 | 88%, $2,605, +$2,221, x35 | 83%, $2,446, +$1,972, x31 | 20%, $92, -$45, x-0.72 | 97% |
| FundedNext Rapid Daily 50K ($149.99) | 84%, $4,551, +$3,664, x24 | 85%, $4,531, +$3,683, x25 | 19%, $490, -$55, x-0.37 | 97% |

Same table, other phase policies (research/propecon/evformula.json):
- **Aggressive eval (BLITZ + 2x size):** static evals pass 55-59% instead of 84%, in 3-5 sessions instead of 7: x48 -> x31 on Builder 50K. Rapid EOD evals pass MORE often and sooner: Rapid 25K 79% -> 87% (25 vs 33 sessions), Rapid 50K 2021-25-like 10% -> 17% (x-0.54 -> x-0.21).
- **LIT only in both phases, $min asks:** the only policy that is slightly positive per eval in 2021-25-like markets: Builder 50K **+$19 (x+0.21)**, FundedNext 50K **+$26 (x+0.18)** (pass 28%, funded accounts lost 83-88%). In 2026-like markets it costs 10-30% of the money. As a whole fleet over 6 months (post-hoc, labelled) it is still -$24 / -$39 a month in 2021-25-like markets, because accounts bought late have no time to pay. **So "a break-even strategy is still +EV at a prop" holds only barely, only for LIT-only on Builder 50K / FundedNext, and only over more than 6 months. It is not money worth planning on.**

## What else was searched (and lost)

| Lever | Tested | Result (pick market Jan-Jun, checked Jul-Oct / 2021-25) |
|---|---|---|
| Eval size | LIT x0.5 / 1 / 1.5 / 2, add-ons x1 / x2 | x2 helps only on Rapid EOD evals (consistency rule); hurts static evals under a budget |
| Eval lanes | LIT / LIT + ATLAS / + BLITZ $300 / LIT x2 | + BLITZ wins on every type in 2026; costs a little more in 2021-25 (more re-buys) |
| Funded size | LIT x0.5 / 0.75 / 1, ATLAS x0.5 / 1 | x1 wins in 2026; x0.5 nearly ends funded losses but costs $700-1,400 per slot |
| Funded lanes | LIT + ATLAS / LIT only | LIT + ATLAS wins in 2026; LIT only is the 2021-25 defence |
| Payout ask | the cap vs the minimum | within +-$150 per 6 months (noise); keep the cap on Builders (it saves payout slots) |
| Close rule | Builder after payout 4 vs 5 | 5 = live move, every MFFU sim dormant: -$2,661 a month ($300, Jan-Jun) |
| Re-buy stop | none vs stop after 3 dead in a row | the stop loses $0.4-3.1k a month in 2026-like markets |
| Stagger | buy at once vs max 1 a week | the stagger loses $0-480 a month |
| Account count / order | 9 buy orders x 3 budgets (432 fleets) | more firms help only when the budget can buy them; Builder-only orders are last |

## How it was run

- Trades: LIT 631 stored trades (120 live-sized 2026 + 511 2021-25), ATLAS 1,149 at 10-tick real fills, BLITZ 2,226 (noise-area scalp, mode "lit+atlas"). Futures bars only. Costs in. Sizing: LIT eval = live two_week sizing, LIT funded = UP50 / UP25 preset, ATLAS / BLITZ lanes = min($ lane, 30% of room, soft-day left), capped at the plan's micros.
- Firm rules: research/props/firm_rules.json via tools/account4_sim.rules, MFFU caps and the live trap from docs/ACCOUNT_RULES.md (fleet.py). Prices: owner's real MFFU prices ($91.80, $63, $97.20, $165), FundedNext $149.99 (code RAPID), Lucid $126 ASSUMED.
- Monte Carlo: 5-session week blocks drawn from each market; every account of a fleet on the SAME path (bad weeks hit all copies). Stage 1: 500 paths; search: 300 paths on Jan-Jun 2026 only; final: 1,000 paths (seed 23) in all three markets. Start = the board 2026-11-23 balances.
- **Not modelled / caveats:** payout denials and the Builder 48-hour first-trade wait; the MFFU Risk team's discretionary Rapid live move; FundedNext + NinjaTrader is still unconfirmed in writing (fastest-money-2026-11-23); Lucid price and cap unverified; BLITZ has never traded real money and "burns room" in live paper; the 2026 trades are what the strategies were tuned on (LIT picked on Jan-Jun), so 2026 numbers are optimistic and the 2021-25 row is the honest floor; other rejected lanes on day-* branches were not used (no stored trade list in this engine's format).
- Re-run: `python -X utf8 research/propecon/unit.py 500 research/propecon/unit_results.json H1,H2,REF`, `python -X utf8 research/propecon/search.py search 300`, `python -X utf8 research/propecon/search.py final 1000`, then decomp.py / litonly.py / fill.py / evformula.py.
