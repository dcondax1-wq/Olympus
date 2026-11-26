# ICT lab proof 2026-11-25: the eval-safe forms, real engine

Lead's follow-up to `ict-lab-2026-11-25.md`. Engine = `research/plans/rank.py` + `research/onebook/book.py` (real fills: ATLAS at 10 ticks a side, LIT eval two_week sizing, funded presets, every MFFU rule), 1,000 Monte Carlo paths per span (60-session evals, 126-session slots incl. the funded stage and payouts), seeds as rank.py. Funded ATLAS = `tools/atlas_funded.py` replay with the live funded sizing (40% of room, <= $750, winner <= $1,000, soft daily loss, 2-loss streak = 1 micro). Code `research/ictlab/proof.py`, numbers `research/ictlab/proof.json`. Multipliers floor to whole micros, never below 1. Nothing in the live models changed.

## One screen

| Form | 2026 H1 $ | 2026 H2 $ | 2021-25 $ | 2025 $ | max DD 2021-25 | eval 25K H1 / H2 pass-fail | WF windows won | Verdict |
|---|---|---|---|---|---|---|---|---|
| A: LIT x0.5 on the wrong side of the 00:00 True Day Open | -$152 | -$822 | +$6.3k | +$372 | -$21.1k -> -$14.0k | 75/3% 9d -> 74/2% 10d / 80/2% 8d -> 76/1% 12d | 11 of 18 | NO CARD (fails the LIT split on $) |
| B1: ATLAS C2: x1.5 in an SB hour AND on the 20-day IPDA side | +$3.2k | +$281 | +$565 | +$619 | -$37.1k -> -$38.3k | 81/4% 11d -> 83/5% 11d / 60/5% 20d -> 73/5% 17d | 10 of 18 | CARD (weak): both 2026 halves + 2021-25 + 2025 better |
| B2: ATLAS x0.5 outside the SB hours | -$601 | -$97 | +$20.9k | +$5.9k | -$37.1k -> -$17.9k | 81/4% 11d -> 92/0% 14d / 60/5% 20d -> 67/0% 23d | 13 of 18 | CARD (eval safety): eval better in both 2026 halves, $ about flat |
| C: FUNDED ATLAS 25K x1.5 in SB hours | paid +$3.0k -> +$3.0k / 6 mo | +$2.6k -> +$2.6k | 2021-24 +$214 -> +$218 | +$492 -> +$534 | - | dead H1 4.5% -> 5.6%, H2 2.8% -> 7.2% | - | NO CARD: same payouts, more dead accounts |

$ columns = change vs ATLAS / LIT as is, fixed size (LIT at its $800 rule, ATLAS $250 a trade, real fills, costs in).
Note: with real fills (10 ticks a side) ATLAS as is LOSES in 2021-25 (-$28.2k at $250, PF 0.82), unlike the stored-fill stream in the first write-up (+$10.4k). The 2026 numbers agree.

## A: LIT x0.5 on the wrong side of the 00:00 True Day Open

**NO CARD (fails the LIT split on $).** 2026 H1 -$152 and Jul-Oct -$822 vs as-is (both halves slightly worse in $), so the house rule (pick on Jan-Jun, check on Jul-Oct, both better) fails. It is a risk reducer: 2021-25 +$6.3k, max DD -$21.1k -> -$14.0k, fewer failed evals in every span (50K H1 9.9% -> 6.8%, H2 11.1% -> 8.6%) but slower passes (H2 median 8 -> 12 days) and a lower 2025 pass rate (25% -> 18%). Paper lead only.

Trades changed: 37.6% of the strategy's trades. Walk-forward (3-month windows from 2022-05, 6-month look-back): 11 of 18 windows won, switch-on WF +$4.5k.

| Span | trades/wk | PF | net $ | $/month | max DD |
|---|---|---|---|---|---|
| 2026 Jan-Jun | 3.12 | 4.79 -> 5.27 | +$35.1k -> +$34.9k | +$5.8k -> +$5.7k | -$2.4k -> -$2.2k |
| 2026 Jul-Oct 16 | 2.56 | 2.75 -> 2.85 | +$9.6k -> +$8.8k | +$2.6k -> +$2.4k | -$1.5k -> -$1.4k |
| 2021-11..2025 | 2.37 | 0.99 -> 1.06 | -$1.4k -> +$5.0k | -$27 -> +$97 | -$21.1k -> -$14.0k |
| 2025 alone | 2.21 | 1.14 -> 1.21 | +$2.5k -> +$2.9k | +$202 -> +$233 | -$7.4k -> -$5.8k |

Eval (60 sessions, pass / fail %, median days to pass) and the 6-month slot net $ (eval fees + funded payouts), as is -> form:

| Account | 2026 Jan-Jun | 2026 Jul-Oct 16 | 2021-11..2025 | 2025 alone |
|---|---|---|---|---|
| Builder 50K | 70/10% 9d -> 73/7% 10d, slot +$3.8k -> +$3.8k | 82/11% 8d -> 81/9% 12d, slot +$4.5k -> +$3.7k | 28/56% 15d -> 26/42% 20d, slot -$111 -> -$132 | 25/43% 17d -> 18/31% 22d, slot -$80 -> -$135 |
| Builder 25K | 75/3% 9d -> 74/2% 10d, slot +$1.9k -> +$1.8k | 80/2% 8d -> 76/1% 12d, slot +$1.8k -> +$1.5k | 27/32% 14d -> 26/24% 19d, slot -$103 -> -$93 | 24/13% 17d -> 19/7% 22d, slot -$65 -> -$81 |
| Rapid EOD 25K | 25/0% 42d -> 24/0% 42d, slot +$1.3k -> +$1.3k | 41/0% 42d -> 41/0% 42d, slot +$1.1k -> +$956 | 3/3% 51d -> 3/2% 50d, slot -$131 -> -$127 | 2/0% 47d -> 2/0% 48d, slot -$95 -> -$96 |

Config diff (exact, NOT applied) - live_model.json AND live_model_lit.json (same diff in both; not applied):
```diff
"lit_sizing": {
    ...,
+   "tdo_side": {"on": true, "level": "00:00 ET 5m open (True Day Open)", "wrong_side_mult": 0.5,
+                "applies": "entries at/after 00:00 ET: long above / short below the level", "min_micros": 1}
  }
```
(needs code: engine/sizing.lit_qty + funded_qty read it (the lead wires; then lit_losses.py live, model_versions.py, tests.test_lit_live))

## B1: ATLAS C2: x1.5 in an SB hour AND on the 20-day IPDA side

**CARD (weak): both 2026 halves + 2021-25 + 2025 better.** Fixed $: H1 +$3.2k, H2 +$281, 2021-25 +$565, 2025 +$619; PF up in every span. 25K eval pass H1 81% -> 83%, H2 60% -> 73%, but fails tick up (H1 4.2% -> 5.0%, H2 4.8% -> 5.3%; 50K H2 10.4% -> 13.2%). Walk-forward 10 of 18 windows won (+$3.5k). Touches only 16% of ATLAS trades; most of the gain is 2026 H1. One of 20 pre-listed combos: treat as a small, fragile edge.

Trades changed: 16.3% of the strategy's trades. Walk-forward (3-month windows from 2022-05, 6-month look-back): 10 of 18 windows won, switch-on WF +$3.5k.

| Span | trades/wk | PF | net $ | $/month | max DD |
|---|---|---|---|---|---|
| 2026 Jan-Jun | 4.06 | 2.39 -> 2.62 | +$15.9k -> +$19.2k | +$2.6k -> +$3.1k | -$1.2k -> -$1.2k |
| 2026 Jul-Oct 16 | 2.95 | 2.07 -> 2.1 | +$4.4k -> +$4.6k | +$1.2k -> +$1.2k | -$1.2k -> -$1.1k |
| 2021-11..2025 | 4.61 | 0.82 -> 0.84 | -$28.2k -> -$27.6k | -$550 -> -$539 | -$37.1k -> -$38.3k |
| 2025 alone | 4.3 | 0.9 -> 0.92 | -$3.3k -> -$2.7k | -$269 -> -$219 | -$8.8k -> -$9.1k |

Eval (60 sessions, pass / fail %, median days to pass) and the 6-month slot net $ (eval fees + funded payouts), as is -> form:

| Account | 2026 Jan-Jun | 2026 Jul-Oct 16 | 2021-11..2025 | 2025 alone |
|---|---|---|---|---|
| Builder 50K | 84/12% 11d -> 85/12% 10d, slot +$5.1k -> +$4.7k | 74/10% 18d -> 78/13% 16d, slot +$2.5k -> +$3.0k | 17/83% 6d -> 17/83% 6d, slot -$493 -> -$512 | 20/79% 6d -> 21/78% 5d, slot -$377 -> -$361 |
| Builder 25K | 81/4% 11d -> 83/5% 11d, slot +$2.1k -> +$2.0k | 60/5% 20d -> 73/5% 17d, slot +$678 -> +$1.1k | 16/82% 7d -> 16/84% 6d, slot -$263 -> -$300 | 18/77% 6d -> 21/76% 6d, slot -$230 -> -$239 |
| Rapid EOD 25K | 51/0% 42d -> 52/0% 43d, slot +$4.2k -> +$5.5k | 66/0% 35d -> 67/1% 35d, slot +$847 -> +$1.9k | 6/66% 35d -> 6/69% 35d, slot -$284 -> -$291 | 6/55% 31d -> 6/57% 31d, slot -$233 -> -$228 |

Config diff (exact, NOT applied) - data/account_b.json on the PC (the account_b block; second_model.json ships null) - not applied:
```diff
{
  ...,
+ "time_size": {"on": true, "hours_et": [3, 10, 14], "need_ipda20_side": true, "in_mult": 1.5, "out_mult": 1.0}
}
```
(needs code: engine/account_b.qty (eval + funded) applies it before dll_guard; the 20-day range = the last 20 sessions' high/low)

## B2: ATLAS x0.5 outside the SB hours

**CARD (eval safety): eval better in both 2026 halves, $ about flat.** Fixed $: H1 -$601, H2 -$97 (flat-to-slightly-less), 2021-25 +$20.9k, 2025 +$5.9k; max DD down 30-60% in every span; PF up everywhere. Builder 25K eval: H1 pass 81% -> 92%, fail 4.2% -> 0.1%; H2 pass 60% -> 67%, fail 4.8% -> 0.2% (slower: 11 -> 14 / 20 -> 23 days). Builder 50K: fail 12.0% -> 1.1% / 10.4% -> 1.6%. Walk-forward 13 of 18 windows won (+$18.0k). NOT for the Rapid EOD 25K (pass 51% -> 36%). By the strict 'net $ both halves better' reading it misses by $601 / $97; by eval pass/fail (the money on an eval) it wins both halves.

Trades changed: 60.1% of the strategy's trades. Walk-forward (3-month windows from 2022-05, 6-month look-back): 13 of 18 windows won, switch-on WF +$18.0k.

| Span | trades/wk | PF | net $ | $/month | max DD |
|---|---|---|---|---|---|
| 2026 Jan-Jun | 4.06 | 2.39 -> 2.92 | +$15.9k -> +$15.3k | +$2.6k -> +$2.5k | -$1.2k -> -$771 |
| 2026 Jul-Oct 16 | 2.95 | 2.07 -> 2.43 | +$4.4k -> +$4.3k | +$1.2k -> +$1.1k | -$1.2k -> -$827 |
| 2021-11..2025 | 4.61 | 0.82 -> 0.93 | -$28.2k -> -$7.3k | -$550 -> -$142 | -$37.1k -> -$17.9k |
| 2025 alone | 4.3 | 0.9 -> 1.12 | -$3.3k -> +$2.6k | -$269 -> +$211 | -$8.8k -> -$3.7k |

Eval (60 sessions, pass / fail %, median days to pass) and the 6-month slot net $ (eval fees + funded payouts), as is -> form:

| Account | 2026 Jan-Jun | 2026 Jul-Oct 16 | 2021-11..2025 | 2025 alone |
|---|---|---|---|---|
| Builder 50K | 84/12% 11d -> 94/1% 13d, slot +$5.1k -> +$5.4k | 74/10% 18d -> 78/2% 20d, slot +$2.5k -> +$2.4k | 17/83% 6d -> 19/72% 11d, slot -$493 -> -$241 | 20/79% 6d -> 29/55% 11d, slot -$377 -> -$63 |
| Builder 25K | 81/4% 11d -> 92/0% 14d, slot +$2.1k -> +$2.3k | 60/5% 20d -> 67/0% 23d, slot +$678 -> +$676 | 16/82% 7d -> 18/39% 12d, slot -$263 -> -$111 | 18/77% 6d -> 27/16% 12d, slot -$230 -> -$34 |
| Rapid EOD 25K | 51/0% 42d -> 36/0% 46d, slot +$4.2k -> +$3.3k | 66/0% 35d -> 56/0% 37d, slot +$847 -> +$860 | 6/66% 35d -> 5/22% 34d, slot -$284 -> -$161 | 6/55% 31d -> 6/7% 33d, slot -$233 -> -$73 |

Config diff (exact, NOT applied) - data/account_b.json on the PC (the account_b block) - not applied:
```diff
{
  ...,
+ "time_size": {"on": true, "hours_et": [3, 10, 14], "in_mult": 1.0, "out_mult": 0.5}
}
```
(needs code: engine/account_b.qty (eval stage; keep Rapid accounts OFF), then the ATLAS tests (run_area atlas))

## C: FUNDED ATLAS 25K, x1.5 in Silver Bullet hours (live funded sizing)

Rule: an ATLAS entry 03:00-03:59 / 10:00-10:59 / 14:00-14:59 ET on the funded account sizes with room share 60% (40% x 1.5) and cap $1,125 ($750 x 1.5); the $1,000 best-day guard, the $600 soft daily loss guard and the 2-loss streak rule stay. 1,000 paths x 6 months.

| Span | paid 6 mo (owner, 80%) | $/month | payouts in 6 mo | first payout (median session) | lost % | dead % (lost + stuck < $100 room) | real path payouts / $ / lost |
|---|---|---|---|---|---|---|---|
| H1 | +$3.0k -> +$3.0k | +$495 -> +$495 | 3.71 -> 3.71 | 24.0 -> 22.0 | 0.0 -> 0.0 | 4.5 -> 5.6 | 4 / +$3.2k / 0 -> 4 / +$3.2k / 0 |
| H2 | +$2.6k -> +$2.6k | +$438 -> +$432 | 3.28 -> 3.24 | 33.0 -> 30.0 | 0.0 -> 0.0 | 2.8 -> 7.2 | 2 / +$1.6k / 0 -> 2 / +$1.6k / 0 |
| 2025 | +$492 -> +$534 | +$82 -> +$89 | 0.61 -> 0.67 | 35.0 -> 29.0 | 0.0 -> 0.0 | 74.6 -> 74.4 | 2 / +$1.6k / 0 -> 2 / +$1.6k / 0 |
| 2021-24 | +$214 -> +$218 | +$36 -> +$36 | 0.27 -> 0.27 | 37.0 -> 29.0 | 0.0 -> 0.0 | 89.5 -> 91.8 | 6 / +$4.8k / 0 -> 6 / +$4.8k / 0 |

**NO CARD.** The $1,000 best-day guard and the $600 daily loss guard appear to cap most SB-hour trades near the size they already had (max risk per trade is unchanged in every span), so the payouts do not change (H1 identical, H2 -$34), and the bigger trades that do get through leave more accounts stuck under $100 of room (H2 2.8% -> 7.2%). Config diff: none proposed.

## Lead summary
- Owner cards: **B2** (ATLAS x0.5 outside SB hours, Builder evals only: fails 4-12% -> 0-2%, $ about flat in 2026, +$20.9k 2021-25) and **B1** (C2, small: +$4.1k fixed over 2021-11..2026-10, eval pass up, fails +0.5-3 pts).
- Not cards: **A** (LIT TDO half-size: both 2026 halves slightly worse in $; paper lead as a drawdown cut) and **C** (no effect).
- All need a small engine change before they could go live; config diffs above are proposals only.
