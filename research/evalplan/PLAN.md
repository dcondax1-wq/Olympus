# Order flow on the evals and the funded account: the honest rollout plan (2026-11-27)

PAPER RESEARCH ONLY. Nothing here arms, sizes or switches anything. Design (committed before the run): research/evalplan/DESIGN.md.
Sim: `python -X utf8 research/evalplan/sim.py` -> results.json; tables: `python -X utf8 research/evalplan/render.py`.

## Verdict for next week
**Paper forward only.** Lane A (absorption level fade, engine/of_paper.py) keeps running on paper; no eval or funded account
trades it next week. Why, in plain words:
1. **Too little proof.** 40 trades on 43 real tick days, all Sep 28 - Nov 26 2026 (one market regime). The older 20 won 12
   (+0.79R a trade); the **newer 20 won 8 (+0.20R, $365 at 1 micro)**. The edge is already shrinking, and the strategy rule
   says both 2026 halves + 2021-25: we have neither (ticks start Sep 2026).
2. **It trades too often for the house rule**: ~4.7 trades a week (rule: 2-4), so even a pass needs a cap (1 a day, 3 a week).
3. **Forward clock**: at ~0.9 trades a day, 30 forward paper trades take ~33 trading days = **about mid-January** (gate 0 = the pre-registered lane A gate, night-of-lanea-gate 2026-11-27). That is the
   earliest a real eval could see it (~early January), not next week.
4. **The sim (below) fails the pre-registered bar on every account.** All 4 accounts, small size, Jul-Oct-like market, 6 months:
   edge as measured **+$5,872**; 1/4 of the edge **+$695**; NO edge **-$1,097** (and the 25K #2 eval's fail rate goes 2% -> 20%).
   The bar was "no edge costs at most one eval price": it costs $72-$547 per account. The safest form (post-hoc, labelled):
   **small AND only on days the account's own bots did not trade**: measured +$2,699, NO edge only **-$229** for all 4.
   The prior (edges shrink out of sample; our newer half already did) says expect between 1/4 edge and none = about break-even.

## 1. Which account, which lane, what size
- **Lane: A standalone only.** OF as a LIT filter (lane B) is TOO FEW: 0 of 20 real Zlarior trades have an OF read; on the
  LIT replay the filter would have COST $2,936 on 18 trades (skip placebo p 0.86). Keep it as the nightly learner only.
- **Size: SMALL, quiet days only** (no lane A on a day the account's own LIT / ATLAS traded or is in a position) = $100 a trade on a 25K, $200 on the 50K (= min(that, 30% of the room, the day's loss left)). Stops over
  that are skipped (lane A's stops run 4-222 pts; at $100 about half the trades are skipped). ATLAS-size ($250 / $500)
  only after 60 forward trades.
- **First account: Zlarior 25K #2 eval** (cheapest re-buy $63, LIT-only so the fewest lane conflicts, worst-case cost small).
  Then the 50K eval. **Rapid EOD 25K last among evals** (30% best-day rule + it already runs LIT+ATLAS). **ATLAS funded
  last of all** (the only account that pays; keep its first $1,000 payout clean).

## What MFFU rules bite
| rule | how it bites lane A | handled by |
|---|---|---|
| Daily loss (soft): 50K $1,000, 25K $600, Rapid $500 option | lane A only gets what LIT/ATLAS left today | sizing: min(lane $, day left) |
| EOD trailing max loss, open losses count | a 222-pt stop at 1 micro = $444 = 44% of a 25K's room | stop > lane $ = no trade |
| Rapid EOD eval: best day <= 30% of profit | a 2R lane A win on a LIT win day can make the "best day" too big | the fleet best-day guard (cons_cap) caps size |
| Builder funded: best day <= 50% of the cycle | delays ATLAS's payout (not a breach) | funded last; payout push unchanged |
| Rapid funded: news banned -2/+2 min | lane A must skip the news window | bot's news window (-3/+2.5) if ever on Rapid funded |
| Max contracts 20 / 40 micros | never binds (lane A = 1-5 micros) | - |
| Hedging banned across ALL accounts (NQ = MNQ) | lane A short on one account while LIT is long on another = a rule break | engine/firms.hedge_conflict + live._hedge_clear_fleet before every lane A entry |
| Inactivity 7 days | helps: lane A trades most days | - |
| One position per account | lane A must never sit beside LIT / ATLAS | plan: quiet days only (sim 'quiet'); main sim placed it after the account's own trades |

## 2. Simulation on the real engines (1,000 paths a market, from today's balances)
Engines: research/alloc/alloc.py (today's state of each account, today's book) on research/onebook/book.py + research/plans/rank.py
(live LIT two_week sizing, ATLAS at real fills, MFFU rules, re-buy on a fail). Lane A trades drawn from the 40 real ones
(stop sizes as measured, one target +2R or the stop -1R), 0.93 a day; the edge is a dial: as measured (50% won, +0.5R),
1/4 of it (37.5%, +0.12R), none (33%, 0R), bad (24%, -0.28R = the skipped group). Markets: Jan-Jun 2026-like, Jul-Oct
2026-like, 2021-25-like. Honest limit: the order-flow draw does not know the market (we only have Sep-Nov 2026 ticks).

### Zlarior 50K eval (LIT)

| lane A | pass % (60 days) Jan-Jun / Jul-Oct / 2021-25 | days to pass (Jul-Oct) | fail % Jul-Oct | 6 months net $ Jan-Jun / Jul-Oct / 2021-25 | vs today Jul-Oct |
|---|---|---|---|---|---|
| no order flow (today) | 72% / 70% / 13% | 16 | 24% | $4,421 / $4,210 / $-88 | +0 |
| small, edge as measured | 78% / 77% / 35% | 14 | 22% | $6,348 / $6,311 / $776 | +2,101 |
| small, 1/4 of the edge | 64% / 61% / 16% | 14 | 38% | $4,612 / $4,543 / $-44 | +333 |
| small, NO edge | 60% / 55% / 11% | 14 | 44% | $4,014 / $3,884 / $-175 | -326 |
| small, bad (losing) | 46% / 42% / 6% | 13 | 58% | $2,822 / $2,629 / $-371 | -1,581 |
| ATLAS-size, as measured | 76% / 77% / 42% | 11 | 23% | $10,044 / $9,692 / $4,287 | +5,482 |
| ATLAS-size, 1/4 edge | 56% / 52% / 16% | 12 | 47% | $4,686 / $4,334 / $270 | +124 |
| ATLAS-size, NO edge | 47% / 43% / 10% | 13 | 56% | $3,144 / $2,812 / $-171 | -1,398 |
| ATLAS-size, bad | 28% / 24% / 4% | 12 | 75% | $737 / $483 / $-566 | -3,727 |
| small, as measured, only on quiet days | 75% / 74% / 24% | 15 | 23% | $5,366 / $5,476 / $270 | +1,266 |
| small, NO edge, only on quiet days | 67% / 61% / 13% | 15 | 38% | $4,402 / $4,145 / $-113 | -65 |

### Zlarior 25K #2 eval (LIT)

| lane A | pass % (60 days) Jan-Jun / Jul-Oct / 2021-25 | days to pass (Jul-Oct) | fail % Jul-Oct | 6 months net $ Jan-Jun / Jul-Oct / 2021-25 | vs today Jul-Oct |
|---|---|---|---|---|---|
| no order flow (today) | 88% / 83% / 28% | 8 | 2% | $2,192 / $1,927 / $-42 | +0 |
| small, edge as measured | 88% / 87% / 43% | 9 | 8% | $2,870 / $2,700 / $211 | +773 |
| small, 1/4 of the edge | 83% / 78% / 30% | 8 | 16% | $2,265 / $2,058 / $-29 | +131 |
| small, NO edge | 80% / 74% / 27% | 8 | 20% | $2,041 / $1,855 / $-77 | -72 |
| small, bad (losing) | 75% / 67% / 20% | 7 | 28% | $1,581 / $1,409 / $-147 | -518 |
| ATLAS-size, as measured | 90% / 86% / 58% | 8 | 9% | $4,544 / $4,261 / $1,553 | +2,334 |
| ATLAS-size, 1/4 edge | 75% / 67% / 30% | 8 | 26% | $2,232 / $2,029 / $41 | +102 |
| ATLAS-size, NO edge | 69% / 60% / 23% | 8 | 32% | $1,552 / $1,361 / $-94 | -566 |
| ATLAS-size, bad | 55% / 46% / 12% | 7 | 46% | $509 / $330 / $-221 | -1,597 |
| small, as measured, only on quiet days | 89% / 85% / 36% | 9 | 7% | $2,492 / $2,363 / $50 | +436 |
| small, NO edge, only on quiet days | 85% / 75% / 28% | 8 | 12% | $2,162 / $1,907 / $-56 | -20 |

### Rapid EOD 25K eval (LIT+ATLAS)

| lane A | pass % (60 days) Jan-Jun / Jul-Oct / 2021-25 | days to pass (Jul-Oct) | fail % Jul-Oct | 6 months net $ Jan-Jun / Jul-Oct / 2021-25 | vs today Jul-Oct |
|---|---|---|---|---|---|
| no order flow (today) | 79% / 85% / 7% | 26 | 2% | $11,359 / $4,893 / $-202 | +0 |
| small, edge as measured | 94% / 92% / 22% | 22 | 3% | $14,811 / $6,925 / $-32 | +2,032 |
| small, 1/4 of the edge | 81% / 83% / 11% | 24 | 9% | $11,238 / $5,004 / $-221 | +111 |
| small, NO edge | 74% / 79% / 8% | 24 | 12% | $9,968 / $4,346 / $-261 | -547 |
| small, bad (losing) | 55% / 68% / 4% | 25 | 20% | $7,326 / $3,156 / $-356 | -1,737 |
| ATLAS-size, as measured | 92% / 91% / 40% | 15 | 6% | $19,813 / $11,214 / $725 | +6,321 |
| ATLAS-size, 1/4 edge | 68% / 73% / 16% | 18 | 19% | $10,580 / $4,626 / $-162 | -267 |
| ATLAS-size, NO edge | 56% / 65% / 10% | 19 | 25% | $7,737 / $3,095 / $-315 | -1,798 |
| ATLAS-size, bad | 25% / 45% / 3% | 21 | 43% | $2,772 / $866 / $-486 | -4,027 |
| small, as measured, only on quiet days | 85% / 86% / 10% | 25 | 2% | $12,025 / $5,353 / $-186 | +460 |
| small, NO edge, only on quiet days | 78% / 83% / 8% | 26 | 4% | $10,927 / $4,833 / $-208 | -60 |

### ATLAS 25K funded (ATLAS)

| lane A | 6 months net $ Jan-Jun / Jul-Oct / 2021-25 | worst 10% Jul-Oct | lose the account % Jul-Oct | vs today Jul-Oct |
|---|---|---|---|---|
| no order flow (today) | $2,986 / $1,665 / $-105 | $-63 | 16% | +0 |
| small, edge as measured | $3,575 / $2,631 / $-12 | $737 | 13% | +966 |
| small, 1/4 of the edge | $3,081 / $1,785 / $-123 | $-63 | 32% | +120 |
| small, NO edge | $2,893 / $1,513 / $-157 | $-126 | 40% | -152 |
| small, bad (losing) | $2,488 / $996 / $-221 | $-126 | 60% | -669 |
| ATLAS-size, as measured | $4,754 / $4,134 / $479 | $800 | 22% | +2,469 |
| ATLAS-size, 1/4 edge | $3,028 / $1,654 / $-70 | $-126 | 56% | -11 |
| ATLAS-size, NO edge | $2,478 / $983 / $-168 | $-189 | 71% | -682 |
| ATLAS-size, bad | $1,333 / $149 / $-312 | $-189 | 94% | -1,516 |
| small, as measured, only on quiet days | $3,246 / $2,202 / $-76 | $-63 | 16% | +537 |
| small, NO edge, only on quiet days | $2,935 / $1,581 / $-109 | $-63 | 34% | -84 |

Pre-registered rule (worth a forward plan = as-measured AND 1/4-edge beat today in both 2026 halves, and NO edge costs <= one eval price in Jul-Oct):

| account | small | ATLAS-size |
|---|---|---|
| Zlarior 50K eval (LIT) | no (beats both halves: yes; no-edge cost $326 vs price $91.8) | no (beats both halves: yes; no-edge cost $1,398 vs price $91.8) |
| Zlarior 25K #2 eval (LIT) | no (beats both halves: yes; no-edge cost $72 vs price $63.0) | no (beats both halves: yes; no-edge cost $566 vs price $63.0) |
| Rapid EOD 25K eval (LIT+ATLAS) | no (beats both halves: no; no-edge cost $547 vs price $97.2) | no (beats both halves: no; no-edge cost $1,798 vs price $97.2) |
| ATLAS 25K funded (ATLAS) | no (beats both halves: yes; no-edge cost $152 vs price $63.0) | no (beats both halves: no; no-edge cost $682 vs price $63.0) |

## 3. The gate ladder (each step has its stop rule set NOW, before any forward trade)
Win counts below are out of lane A's 2:1 trades (won = hit +2R). Pass chances from the binomial: with NO edge (33% won) / 1/4
edge (37.5%) / as measured (50%).
| step | where | go to the next step when | stop rule (switch OFF, back to paper) | earliest |
|---|---|---|---|---|
| 0 | paper bot (running; scored nightly by tools/of_ladder.py -> research/evalplan/ladder.json) | judged ONCE on the first 30 forward trades (from Nov 27), the pre-registered gate of research/orderflow/DESIGN_lanea_proof.md: **mean >= +0.20R after costs, PF ($) >= 1.30, taken > skipped, both halves >= 0R, max DD <= 6R** | after 10 forward trades <= 2 won, or forward sum <= -6R, or max DD > 6R at any time | ~mid-Jan |
| | | false pass if no edge 19%, if 1/4 edge 32%, real edge passes 75% | | |
| 1 | NinjaTrader Sim101, same rules, real order path (fills, slippage, the hedge guard with the live lanes) | 10 Sim101 trades, fills within 2 ticks of paper on average, 0 hedge / one-position conflicts | any hedge conflict, or fills worse than paper by > 4 ticks average | ~2 weeks after step 0 |
| 2 | ONE eval: Zlarior 25K #2, SMALL ($100), quiet days only, cap 1 a day / 3 a week; owner's yes + phrase | pooled forward (paper + Sim101 + eval) **40 trades with >= 17 won** (+0.28R; false pass 14% / 31% / real 87%) | lane A's own sum on the account <= -$300 (3 full losses), or 10 eval trades <= 2 won, or the account's room under $400 | mid/late Jan |
| 3 | the other evals (50K at $200, Rapid 25K at $100 with the news window) | 60 forward trades, mean >= +0.25R in both halves of the forward | same as step 2 per account ($600 on the 50K) | Feb |
| 4 | ATLAS funded 25K, SMALL, after its first $1,000 payout | 2 months of step 3 with lane A $ > 0 on every account | lane A sum <= -$250 on the funded account = off for good | Mar+ |
ATLAS-size ($250 / $500) is a separate later question, only after step 3, with its own card.

## 4. The Decide card
Draft: research/handoff/2026-11-27/evalplan/card.json (lead wires it into tools/web_public/business/decisions.json).
Recommend: **later** (paper forward first; nothing to approve next week). What a YES would change: nothing live; it only
lets the lead build the Sim101 lane A route (step 1), switch default OFF.
