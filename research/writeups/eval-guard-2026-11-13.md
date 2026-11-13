---
title: Eval guard (2026-11-13) - from today's room, risking 80% of it fails Zlarior's eval 4 times in 10; 40% is worth about $1,000 more per eval
family: risk
date: 2026-11-13
status: proposal - nothing live changed (live_model*.json, second_model.json and the engine untouched)
summary: Risk of ruin of the two evals the owner trades live from tonight, started from their real state (Zlarior 50K $1,145 of room and $3,687 still to make; ATLAS 25K $822 of room and $1,678 to make), with the real sizing code per trade, whole weeks drawn from Jan-Jun 2026 (pick) and Jul-Oct 2026 (check). Today's code is past session 10 on both evals, so it sizes in safe_eval (Zlarior 60% of the room, ATLAS 30%), not in two_week 80% as docs/TONIGHT_EVAL.md says. Two-week 80% from here passes Zlarior in 2 weeks 35/40% of the time but fails it 41/42% of the time and is worth $2,617 / $2,697 per eval. Two-week 40% (kept past session 10) passes 32/27%, fails 3.5/3.5% and is worth $3,908 / $3,776: +$1,291 / +$1,079 per eval, and it beats today's code too (+$379 / +$538, 4 times fewer 2-week fails). The same holds for a fresh eval (+$1,000 / +$835). ATLAS: keep 50% of the room but keep two_week past session 10: 2-week passes 37 -> 57% (H1) and 14.5 -> 34.5% (H2) at about the same $ and under 2% fails. Proposal below; the lead or the owner decides.
runs: eval_guard_zlarior_as_coded, eval_guard_zlarior_hold_80, eval_guard_zlarior_hold_50, eval_guard_zlarior_hold_40, eval_guard_zlarior_tw_80_prot1000, eval_guard_atlas_as_coded, eval_guard_atlas_hold_80, eval_guard_atlas_hold_50, eval_guard_atlas_hold_40
---

Team G2 "eval guard + real costs", 2026-11-13. Paper research only. Tool: `python -X utf8 tools/eval_guard.py --n 2000
--worlds --sens --slip --runs` (data: `research/lit/eval_guard.json`, runs `eval_guard_*`).

## 1. Risk of ruin from where the two evals stand tonight

### The state the study starts from

| | Zlarior (LIT, Builder 50K) | ATLAS (EMA + MACD + S/R, Builder 25K) |
|---|---|---|
| Room to the max-loss floor (owner's last report, 2026-11-07) | $1,145 of $2,000 | $822 of $1,000 |
| Balance assumed | $49,313.20 (the 2026-10-23 anchor floor $48,168.20 + $1,145; the floor only moves up and the room fell) | $24,822 (no anchor in the repo: EOD high = the start) |
| Still needed to pass | **$3,686.80** | **$1,678** |
| Eval session tonight (from eval_start) | 20 (eval_start 2026-10-19) | 14 (first session after the 2026-10-25 launch prep) |
| What the code sizes tonight | **safe_eval**: the $800 LIT size capped at 60% of the room (`two_week_until` 10, `after_mode` safe_eval) | **safe_eval at 30%** (25K preset: `two_week_until` 10, `safe_cap` 0.3) |

**Finding 0 (before any proposal):** `docs/TONIGHT_EVAL.md` says "two-week mode, never more than 80% of the room (Zlarior: at
most about $916)". The code does not do that tonight: `engine/sizing.lit_qty_core` switches to `after_mode` once the eval
session is above `two_week_until` (10), and both evals are past session 10 unless the PC start cfg carries a newer
`eval_start`. Check the Start page line "eval session N of 10" before arming. If it shows 10 or less, the 80% row below is
what runs, and it is the riskiest row in the table.

### Method

- Trades: Zlarior = the 120 live LIT trades of 2026 (run `lit_live`, the handoff ledger with stop, target and worst open
  point per trade; 2021-25 = the 511 reference rows, 5m only). ATLAS = `tools/atlas.account_units(BASE)` (163 trades in 2026,
  LIT's open trades and armed setups block an opposite ATLAS entry as on the PC). $1.90 a micro, 1 tick in the prices.
- Size per trade: the real code. Zlarior `engine/sizing.lit_qty` on live_model.json `lit_sizing`; ATLAS
  `tools/atlas.q_variant` = `engine/account_b.qty` on the 25K preset with its day guard, 2 trades a day, one position.
- MFFU rules: EOD trailing floor (locks at start + $100), open losses count, soft daily loss ($1,000 / $600) closes the day.
  "Stuck" (room under $200 / $100, not even 1 micro of a normal stop fits) counts as a fail: the eval is dead, no reset.
- Monte Carlo: whole calendar weeks drawn with replacement from one half, 2,000 paths of 60 sessions, seed 7. **H1 = Jan-Jun
  2026 (pick), H2 = Jul-Oct 2026 (check)**, REF = 2021-25 (reference, never a gate). Second layer (`--worlds`): the half's
  weeks are themselves resampled, 100 worlds x 200 paths, for an 80% band.
- **$ per eval** = P(pass within 60 sessions) x what a funded account pays the owner in 6 months - the eval price.
  Funded value: 50K $929 / $915 a month H1 / H2 at the live funded rule (`uprisk.md`), 25K ATLAS $582 / $517 (`atlas-funded.md`),
  2021-25 ~$66 / ~$50. Prices: $91.80 (Builder 50K) and $43 (the ATLAS 25K). Both evals are already paid, so "$ from now" is
  the same number plus the price.

### Zlarior (50K, $1,145 room, $3,687 to go) - H1 pick / H2 check

| Rule | Pass in 2 wk (10 sessions) | Fail in 2 wk | Pass in 60 | Days to decide (mean) | $ per eval | Max $ on 1 trade | 2021-25 fail in 2 wk |
|---|---|---|---|---|---|---|---|
| **As coded tonight** (safe_eval 60%) | 28.9 / 16.3 | 14.5 / 16.2 | 65.0 / 60.6 | 15 / 21 | $3,529 / $3,238 | $867 | 20.9 |
| Two-week 80% (what TONIGHT_EVAL.md describes) | 35.4 / 39.5 | **40.8 / 42.4** | 48.6 / 50.8 | 8 / 7 | **$2,617 / $2,697** | $995 | 50.9 |
| Two-week 60% (10 sessions, then safe_eval) | 35.9 / 34.0 | 23.8 / 27.4 | 57.8 / 55.9 | 12 / 13 | $3,130 / $2,974 | $995 | 28.2 |
| Two-week 50% | 32.9 / 30.8 | 13.5 / 14.2 | 62.5 / 63.0 | 15 / 15 | $3,389 / $3,370 | $995 | 17.3 |
| **Two-week 40%** (kept past session 10) | 31.9 / 27.4 | **3.5 / 3.5** | 71.8 / 70.5 | 20 / 21 | **$3,908 / $3,776** | $794 | 4.5 |
| 80% + protect (room < $1,000: a stop-out <= 35% of the room) | 33.8 / 38.1 | 7.7 / 10.0 | 66.7 / 59.0 | 21 / 19 | $3,623 / $3,147 | $991 | 19.1 |
| 60% + protect (room < $700) | 34.0 / 30.2 | 3.3 / 7.5 | 69.7 / 60.6 | 21 / 22 | $3,790 / $3,238 | $940 | 6.4 |
| safe_eval 40% (the $800 size, 40% cap) | 27.4 / 12.3 | 2.4 / 1.6 | 72.9 / 67.1 | 22 / 28 | $3,972 / $3,592 | $867 | 3.4 |

80% bands when the half's weeks themselves are resampled (H2, pass / fail in 2 weeks): 80% [21-58] / [25-64]; 40%
[9-48] / [0-7]; as coded [2-31] / [2-27]. The pass bands overlap (15 weeks of H2 is a thin sample), **the fail bands do
not**: risking 80% of a $1,145 room fails the eval in 2 weeks 1 time in 4 even in the luckiest worlds.

**Why 80% loses money here:** with $3,687 to make, "one winner passes" wants ~20-30 micros, so the 80% cap binds: the first
trade risks about $916. One stop-out leaves ~$230 of room, and the eval is as good as dead. At 40% the first loss costs ~$460
and leaves ~$690, enough for two more tries; LIT's 2026 winners are 2-8R, so a smaller size still passes, only later.

**Fresh eval** (the next purchase, $0 start, same code): 80% -> 2-week pass / fail H1 46.5 / 21.9, H2 55.9 / 26.4, $3,473 /
$3,457 per eval; **40% -> 44.1 / 0.5, 47.4 / 0.6, $4,473 / $4,292** (+$1,000 / +$835, pass median 10 / 7 sessions). The
`uprisk.md` MC (5-session blocks, weekly stop off) gave 52.9 / 17.8 and 58.6 / 20.9 for 80%: same picture.

### ATLAS (25K, $822 room, $1,678 to go) - H1 / H2

| Rule | Pass in 2 wk | Fail in 2 wk | Pass in 60 | Days (mean) | $ per eval | Max $ on 1 trade | 2021-25 fail in 2 wk |
|---|---|---|---|---|---|---|---|
| **As coded tonight** (safe_eval 30%) | 37.0 / 14.5 | 0.0 / 0.0 | 88.6 / 70.2 | 22 / 35 | $3,053 / $2,133 | $413 | 0.8 |
| Two-week 80% (kept past session 10) | 66.1 / 41.5 | **17.1 / 17.4** | 78.0 / 60.8 | 7 / 11 | $2,682 / $1,840 | $767 | 62.4 |
| Two-week 60% | 62.0 / 36.4 | 7.0 / 5.8 | 84.2 / 62.7 | 14 / 28 | $2,897 / $1,901 | $640 | 45.8 |
| **Two-week 50% kept past session 10** (today's room share) | **57.3 / 34.5** | 1.9 / 0.1 | 86.7 / 68.2 | 11 / 22 | $2,986 / $2,070 | $640 | 31.4 |
| Two-week 40% kept past session 10 | 48.2 / 28.6 | 0.2 / 0.0 | 89.3 / 74.5 | 15 / 27 | $3,077 / $2,266 | $512 | 13.1 |
| 80% + protect (room < $400) | 57.5 / 40.0 | 1.1 / 1.4 | 83.0 / 58.6 | 19 / 31 | $2,855 / $1,774 | $767 | 19.8 |

Bands (H2 pass / fail in 2 weeks): 50% kept [18-56] / [0-1]; 80% [26-63] / [5-26]; as coded [3-35] / [0-0].
On 2021-25 ATLAS has no edge (every row ~$20-35 per eval) and 80% fails 62% of evals in 2 weeks.

### Sensitivity to the assumed balance

If the EOD high moved up after the anchor (Zlarior balance $49,645, need $3,355; ATLAS balance $25,122, need $1,378), H2:
Zlarior 80% p10 / f10 44.9 / 40.5 ($2,832), 40% 29.1 / 3.5 ($3,592), as coded 20.4 / 16.2 ($3,326); ATLAS 80% 43.9 / 17.6,
50% 40.1 / 0.1, as coded 16.6 / 0.0. Same ranking.

### Verdict and proposal (do NOT apply without the owner; the lead edits the files)

Picked on H1 by $ per eval among the rules that keep 2-week passes near today's, checked on H2:

- **Zlarior: two-week at 40% of the room, kept past session 10.** H1 $3,908 vs $2,617 at 80% (+$1,291), H2 $3,776 vs $2,697
  (+$1,079); 2-week fails 3.5 / 3.5% vs 41 / 42%; 2-week passes 31.9 / 27.4 vs 35.4 / 39.5 (-3.5 / -12.1 points). Versus
  today's code (safe_eval 60%): +$379 / +$538, fails 14.5 / 16.2 -> 3.5 / 3.5, passes 28.9 / 16.3 -> 31.9 / 27.4: better
  on all three in both halves. 2021-25: fails 51% -> 4.5% (no money either way there).
  Exact change, both `live_model.json` and `live_model_lit.json`, "lit_sizing":
  ```json
  "two_week": { ..., "room_f": 0.4, ... },     // was 0.8
  "two_week_until": 80                          // was 10 (keep two_week sizing for the rest of this eval; after_mode untouched)
  ```
  then `tests/sizing_pins.py` OWNER `"two_week.room_f": 0.4`, the docs (CLAUDE.md headline, CLAUDE_REFERENCE "Live
  strategy", STRATEGY.md, TONIGHT_EVAL.md "$916" -> about $458), `research/lit/uprisk_eval.json` row read by
  `tools/build_web_dashboard._live_eval_odds`, and `python tools/lit_losses.py live` + `tests.test_lit_live` (sizing only;
  the 120 trades do not change). Do not change `eval_start` to restart the count: it also selects the P&L days of the eval book.
- **ATLAS: keep 50% of the room, keep two-week past session 10.** 2-week passes 37.0 / 14.5 -> 57.3 / 34.5, fails 0 -> 1.9 /
  0.1, $ per eval -$67 / -$63 (inside the noise). 40% is +$91 / +$196 but slower: not a clear win, not proposed.
  The ATLAS knob is NOT in live_model.json: the 25K preset overrides it. Exact change (engine code, the lead's call):
  `engine/multi_account.py` PRESETS["mffu_builder_25k"]["sizing"]["two_week_until"] 10 -> 80 (`tests.test_second_account_b`,
  `tests.test_multi_account --quick`).
- **Not proposed:** the "protect when room < $X" rule. It cuts 80%'s fails to 8-10% and keeps the passes, but on H2 it earns
  less than plain 40% ($3,147 vs $3,776) and needs a new engine knob; plain 40% is a config change.
- **Speed, honestly:** from this state no rule meets "pass within 2 weeks, never more than 3": the best 2-week pass rate is
  ~40% and comes with ~42% fails. The eval already lost 43% of its room; that is the price of being behind.

### Honest limits

- The balance is inferred (anchor of 2026-10-23 + the $1,145 room); ATLAS's is assumed. Refresh the PC anchor
  (`python -m engine.eval_life --anchor`) with MFFU's own numbers before arming: the bot sizes from its own book.
- H2 is 15 weeks, 163 ATLAS and 120 LIT trades in all of 2026: the 2-week pass bands are 30-40 points wide. Only the fail
  differences are clearly outside the noise.
- 2021-25 LIT is 5m-only reference data with no edge; the funded value there is near zero, so its $ column is ~$0 for every rule.
- The funded value is a 6-month window from the uprisk / atlas-funded MCs at the live funded rules, not re-simulated here.
- Real fills (step 2) are not in these numbers beyond the backtest's 1 tick; +2 extra ticks moves $ per eval by $15-120.

## 2. Real costs: recorded fills vs the backtest's costs

### What real fills exist (searched 2026-11-13)

**None.** No real NinjaTrader / MFFU fill of either bot is recorded anywhere this repo or this machine can see:

| Source | What it holds |
|---|---|
| `logs/learning/costs.json` (gitignored, last written 2026-10-27) | Zlarior `fills 0, obs 0, learned false`; ATLAS the same: "no real fills yet - sizing assumes 1 tick of slippage and $1.90 a micro" |
| `logs/exec_audit/summary.json` (fill audit, 2026-10-27) | `trades 0`, "No live trades to audit yet." |
| `research/handoff/*` | backtest ledgers, `COMMISSION_DRIFT.csv` ($1.40 vs $1.90 re-pricing), no broker fills |
| heartbeat / dashboard branches | not in this checkout (the owner's GitHub account is suspended, `docs/QA_ROUND6.md`) |

The drawdown the two evals already lost ($855 and $178 of room) did not come through a recorded bot fill. So every number
below is the **modelled** gap, and the first real number comes from the PC's own fill audit after tonight.

### What the backtest assumes vs what MFFU charges

| Item | Backtest / research runs | Live booking and sizing | Real (MFFU, searched 2026-11-13) |
|---|---|---|---|
| Commission MNQ | $1.40 a micro round trip (`engine/lit.COMM`, every stored run) | $1.90 (`engine/sizing.LIVE_COMM`, eval book, caps, ATLAS) | **$1.90 round trip** (MFFU futures instrument list) |
| Entry | market at the next 1m open + 1 tick (LIT); 5m open + 1 tick (ATLAS) | market, routed ~3 s after the 1m CISD close (timing fix 2026-10-18) | half the spread + book depth: ~0.5 tick NY, ~0.75 London, ~1 Asia (`lit-live-fills.md`) |
| Stop | stop-market, touch -> 1 tick worse | STOPMARKET | 1-2 ticks normally, more on fast bars / news; a bar that opens through the stop fills at its open |
| Target | limit, filled on touch | LIMIT 1 tick toward the entry | sure fill (0 of 25 2026 targets would miss with 2 ticks of trade-through), up to 1 tick of rounding |
| Breakeven | from the next bar | CHANGE ~35 s into the next bar, may be refused | ~$500 a year at the LIT size |

### $ a month the gap costs

- **Commission:** the live books already use $1.90. Only the stored research runs are $0.50 a micro too kind: run `lit_live`
  2026 +$43,820 -> +$43,502 at $1.90 (-$33 a month at the LIT size).
- **Each extra tick of slippage per round trip** (on top of the 1 tick already in the prices), from this study's eval paths
  (`--slip`, micros actually traded per eval month): **Zlarior $21-38 a month** (42-75 micros a month; 40% room: ~$16-24),
  **ATLAS $11-22 a month** (21-44 micros). Per eval: +2 ticks costs Zlarior $15-118 of $ per eval and 0-3 points of
  2-week fails; ATLAS $17-40. +8 ticks: Zlarior 80% $2,697 -> $2,565 (H2), ATLAS 50% $2,018 -> $1,850. The ranking of
  the rules does not change at any slippage.
- **The realistic total** (`lit-live-fills.md` fill model: $1.90, stop slippage, spread, target rounding, BE lag): about
  **$1,200 a year = ~$100 a month** at the LIT size, ~4% of the H2 rate ($2,670 a month); ATLAS about $16 a month per tick
  (`2026-11-03-slippage.md`).
- **The one cost that can fail an eval** is not the average slip but a stop that slips past the room, because MFFU counts
  open losses. Room left after the planned stop-out, divided by the micros: at 80% of a $1,145 room a 20-micro stop can
  slip only **5.7 pts** (23 ticks) before the account fails intraday; at 40% it can slip **17 pts**. 3 of the 120 2026 LIT
  trades were open across an NFP release, where 15-20+ tick stop slips are reported. This is a second reason for 40%.

### Proposed fixes (none applied; order = value)

1. **Measure first (no code):** after every session the PC fill audit writes `logs/learning/costs.json`. After 5 real fills
   per bot, read `reserve_ticks`: if it is 2 or more, set `lit_sizing.learn_costs: true` (it only ever sizes down, never up).
   The PC cannot push it while GitHub is off: copy the file's `text` lines into the chat.
2. **Room share 0.4 (step 1):** the cheapest protection against a slipped stop on the eval (17 pts of slack instead of 6).
3. **Keep the order types:** market entry (the "limit at the CISD level" is a watched price, not a resting order, so there
   is no queue risk; a resting limit there misses the fast winners), stop-market stop (a stop-limit can leave a runaway
   loser open), target limit 1 tick toward the entry.
4. **Optional, Sim first:** a protected entry (limit = the 1m open + 3 ticks instead of a bare market) for the 02:00-08:00
   London entries, where the book is ~10x thinner. It caps the worst entry slip at 3 ticks for a small chance of a
   missed fill; worth testing on Sim101 only once real fills show London entries slipping more than 2 ticks.
5. **Timing:** already fixed (decide on the 1m CISD close, route ~3 s later; ATLAS skips a 5m open seen more than 45 s
   late). Keep NinjaTrader and the PC up from ~01:55 ET: 95 of 120 LIT entries are 02:00-08:00.
