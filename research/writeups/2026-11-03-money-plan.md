---
title: The money plan on today's settings (2026-11-03 night) - put Zlarior on the free MFFU 25K instead of BLITZ (+$217-279 a month H2), then add LIT 50K copies at other firms (~$790 a month each); about $3,900 a month with 6 accounts in a Jul-Oct-2026 market
family: risk
date: 2026-11-03
status: adopt-candidate (owner decides; needs MFFU's written OK on copying between your own accounts) - a Zlarior copy on the third MFFU slot (the free Builder 25K) pays $334 / $269 / -$7 a month (fleet preset, today's code) or $375 / $331 / -$15 (the 50K's room 0.8, needs a small fleet option) vs BLITZ on that 25K $286 / $52 / -$39 (H1 / H2 / 2021-25)
summary: Owner 2026-11-02 "overall the amount of money we will make". MFFU lets one person hold 1 funded Builder 50K and 2 funded Builder 25Ks. Today - Zlarior (LIT) on the 50K, ATLAS on one 25K, the other 25K (BLITZ's) off. Every slot was priced the same way - 6 months of eval -> 2 sessions of paperwork -> funded -> MFFU payouts -> the next eval, net of every eval, 1,000 Monte Carlo paths of the real sessions, live eval and funded sizing, $1.90 a micro. Per month (H1 Jan-Jun 2026 / H2 Jul-Oct 2026 / 2021-25 reference) - LIT 50K $823 / $798 / -$7; ATLAS 25K $568 / $382 / -$2; LIT 25K $375 / $331 / -$15 (room 0.8) or $334 / $269 / -$7 (the fleet's 25K preset, 50% room); BLITZ 25K $286 / $52 / -$39. So the free 25K earns most as a Zlarior copy - better than BLITZ in all three spans. The three bots' daily results are uncorrelated (LIT-ATLAS -0.01 / -0.03 / +0.11), while Zlarior copies move together (0.8-0.9). Beyond MFFU every extra LIT 50K-type account adds about $790 a month in a 2026-like market and costs about $25 a month (its evals) in a 2021-25-like one. The plan - MFFU 50K (LIT) + 25K (ATLAS) + 25K (LIT), then LIT 50K copies at LucidPro / FundedNext up to 6 accounts (the $3,000 at-once risk cap of scale-plan.md) - about $3,900 a month on Jul-Oct trades, $4,200 on Jan-Jun, and about -$100 a month of eval fees in a 2021-25 market. Paper only; nothing live changed.
runs: rd_lit25k_preset_eval, rd_lit25k_rf80_eval
---

## Money first

| Account slot (6 months, net of every eval) | $ a month H1 / H2 / 2021-25 | 2-week pass / fail H1 / H2 / 2021-25 | evals bought per 6 months (H2) | $ to you per eval bought (H2, 6 months) |
|---|---|---|---|---|
| Zlarior (LIT) MFFU 50K, live | **$823 / $798 / -$7** | 52.9/17.8, 58.6/20.9, 20.7/24.9 | 1.67 | ~$2,870 |
| ATLAS MFFU 25K, live (atx_funded_day.json "today") | $568 / $382 / -$2 | 65.5/0.8 (H1) | 1.44 | ~$1,590 |
| **Zlarior MFFU 25K, room 0.8 (the 50K's rule at half scale)** | **$375 / $331 / -$15** | 55.0/10.6, 57.8/17.3, 20.0/23.2 | 1.57 | ~$1,270 |
| Zlarior MFFU 25K, the fleet's 25K preset (50% room) | $334 / $269 / -$7 | 53.0/0.9, 50.6/0.8, 15.1/1.3 | 1.14 | ~$1,420 |
| BLITZ MFFU 25K (adopted later-break pick) | $286 / $52 / -$39 | 47.9/23.5, 36.2/21.7, 24.7/48.4 | - | - |
| Zlarior copy on a LucidPro / FundedNext 50K (MFFU 50K rules as the proxy, $130 an eval) | $812 / $788 / -$25 | as the 50K | 1.67 | ~$2,830 |

The 25K at $43 (the discount of 2026-10-26) instead of $63 adds $5-9 a month.

## The proposal (owner decides)

**Use the free MFFU Builder 25K for a Zlarior copy, not BLITZ.** It pays more in all three spans:

| MFFU's three slots | $ a month H1 / H2 / 2021-25 |
|---|---|
| today's plan: LIT 50K + ATLAS 25K + BLITZ 25K | $1,677 / $1,232 / -$48 |
| **LIT 50K + ATLAS 25K + LIT 25K (fleet preset, today's code)** | **$1,711 / $1,475 / -$16** (+$34 / +$243 / +$32) |
| LIT 50K + ATLAS 25K + LIT 25K (room 0.8, needs a fleet option) | $1,755 / $1,538 / -$24 (+$78 / +$306 / +$24) |
| LIT 50K + LIT 25K + LIT 25K | $1,562 / $1,468 / -$34 (ATLAS on its 25K is worth more than a 2nd LIT 25K) |

- **The switch (today's code):** `python -X utf8 -m engine.fleet --add --id lit25k --lead zlarior --plan mffu_builder_25k --account "<Name>" --start <day>`
  (the fleet copies Zlarior's routed trades, sized by the two_week rule on the 25K preset). A real account copies only after
  the owner arms it himself (`--arm lit25k` + the live phrase).
- **Before buying:** ask MFFU support in writing whether one bot may trade the same signals on your own Builder 50K and
  Builder 25K. Their fair-play page bans copying "for an unfair advantage" and never mentions your own accounts
  (lit-builder-25k.md). Hedging is not an issue (always the same side).
- **Start it about a week after the 50K's eval** (lit-builder-25k.md: the two evals then decouple; same-day copies are 0.92
  correlated).
- **Watch-out, the preset's small room share:** on the real 2021-25 order the 25K preset eval gets stuck near its floor (it
  cannot fit even 1 micro on wide LIT stops) and sits 7+ calendar days without a trade in 6 of 6 evals (MFFU's inactivity
  rule may close such an account); room 0.8 behaves like the 50K (38% vs 33% of evals). The room 0.8 version also pays more.
  It needs a per-account sizing option in `engine/fleet.py` (today only "plan" or "fixed"): **build that before the 25K
  goes on**, then use it with room_f 0.8.
- **Inactivity (all accounts):** 14% (2026) / 33% (2021-25) of live 50K evals also have a 5+ session stretch with no LIT
  trade. Jarvis already counts the MFFU 7-day no-trade days (amber day 5, red day 6). A 1-micro keep-alive trade would remove
  the risk, but it is engine work (not built tonight).

## How many accounts (Jul-Oct 2026 trades = the number to quote)

| Accounts | What | $ a month H2 / H1 / 2021-25 |
|---:|---|---|
| 2 | today: LIT 50K + ATLAS 25K | $1,180 / $1,391 / -$9 |
| 3 | + Zlarior on the free MFFU 25K (room 0.8) | $1,538 / $1,755 / -$24 |
| 4 | + 1 LIT 50K at LucidPro / FundedNext | $2,326 / $2,567 / -$49 |
| 5 | + 2 | $3,135 / $3,353 / -$82 |
| **6** | **+ 3 (the $3,000 at-once risk cap of scale-plan.md)** | **$3,914 / $4,167 / -$101** |
| 7 | + 4 | $4,696 / $4,984 / -$132 |
| 9 | + 6 | $6,287 / $6,523 / -$154 |

- Every extra LIT 50K adds about $790 a month in a 2026 market and loses about $25 a month (just its evals) in a 2021-25
  market, so more accounts are worth it while 2026 lasts. The downside is small because each account can only lose its eval
  price.
- But Zlarior copies are one bet (0.87-0.91 correlated): in a bad month they all go flat together. ATLAS is the only real
  diversifier (daily correlation with LIT -0.01 / -0.03 / +0.11; all three bots lost the same week 0% of 2026 weeks and 15% of
  2021-25 weeks).
- 6 accounts is the sweet spot because the worst at-once risk passes the proposed $3,000 cap at 8 (scale-plan.md: worst
  $3,184 at 6, $3,930 at 8). LucidPro / FundedNext allow bots and copying your own accounts (scale-plan.md); firm-specific
  funded rates are $938 (LucidPro) and $629 (FundedNext) a month H2 (lit-funded-combo.md), around the $790 proxy.
- Paper lead, not in the table: BLITZ as an add-on on LIT's funded 50K (scalp-na-mffu.md) +$301 / +$290 / +$16 a month on
  older funded sizing.

## How it was done

`python -X utf8 tools/rd_money.py slots|fleet|corr|idle|save` (results `research/lab/rd_money.json`). LIT slots and books on
tools/uprisk.py (the A4-checked eval + MFFU funded engine; 1,000 paths of 126 sessions in 5-session blocks, seed 23; the 25K a
week after the 50K on the same paths; other-firm accounts a week apart). ATLAS and BLITZ from their own stored slot engines
(their means add; they cannot share the LIT paths), the runs `rd_lit25k_*` store the back-to-back 25K eval path on the real
order (their eval columns use the 50K scorer: read this table).
