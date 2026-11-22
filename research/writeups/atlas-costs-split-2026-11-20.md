---
title: ATLAS with split costs (late entry 10 ticks, resting stop 1-3, target 0) - about +$25 a month and safer than the 10/10 stress, but no long-run edge and room 40% stays right; a nightly real-cost alarm built
family: second
date: 2026-11-20
status: info - no change, no Decide card. tools/cost_alarm.py built (alarm only, research/lab/costs.json).
summary: Every ATLAS study today charged the resting stop the same 10 ticks as the late market entry. Priced apart (entry 10, stop 2, target 0) on the live setup (room 40% + 2 losses -> 1 micro), from today's $1,401 room - funded 25K $539 / $459 a month (Jan-Jun / Jul-Oct-like) vs $514 / $436 at 10/10, lost in 6 months 5.4 / 3.6% vs 6.9 / 5.7%; fixed $250 view 2026 PF 2.59 / 2.24, 2025 PF 1.00, 2021-24 PF 0.89 (0.80 at 10/10) - still no long-run edge in a calm market. 25K eval 2-week pass 59.7 / 40.6% (57.1 / 39.1 at 10/10). Room 60% vs 40% at stop 1 / 2 / 3: 40% stays safer every time (no card). No real exit fill exists yet, so the stop cost is a scenario. The alarm reads NOT ENOUGH FILLS for both bots (3 ATLAS, 1 Zlarior fill); at the measured costs the last 40 sessions are PF 2.27 (ATLAS) and 3.38 (Zlarior).
runs: tools/atlas_costs_split.py run -> research/second/atlas_costs_split.json; tools/cost_alarm.py -> research/lab/costs.json; design research/second/atlas_costs_split_design.md (committed before any run)
---

# ATLAS with split costs + a nightly real-cost alarm (2026-11-20)

## For the owner (one minute)

**If ATLAS's stops slip 1-3 ticks (not 10 like its entries), it makes about $25 a month more than we've been assuming, and
the funded 25K is a bit safer. It doesn't change anything to do: keep room 40% + the streak rule.** A new nightly check
will warn if either bot stops being profitable at its real fill costs.

Live setup (room 40% + 2 losses -> 1 micro), from today's $1,401 room, next 6 months:

| Cost assumption (ticks a side) | Jan-Jun-like: $ a month, 1st payout, lost | Jul-Oct-like | 2021-25-like (calm) |
|---|---|---|---|
| Backtest (1 / 1) | $603, Dec 14, 3.0% | $487, Dec 28, 2.4% | $62, none, 81.4% |
| Today's stress (entry 10, stop 10) | $514, Dec 22, 6.9% | $436, Jan 4, 5.7% | $32, none, 91.6% |
| **Entry 10, stop 2 (likely)** | **$539, Dec 18, 5.4%** | **$459, Dec 31, 3.6%** | $42, none, 87.2% |
| Entry 10, stop 1 / stop 3 | $542 / $538 | $463 / $456 | $43 / $40 |
| Entry 13 (the real fills' mean), stop 1 | $533, Dec 21, 5.8% | $451, Dec 31, 4.1% | $38, none, 89.4% |

**Next for you:** nothing.

## #8 split costs (pre-registered: research/second/atlas_costs_split_design.md)

No real ATLAS exit price is in reach (no PC data branch on the remote, none in the board rows; the 3 real fills are entries:
10 / 12 / 16 ticks past the open), so the stop's cost is a scenario: 1, 2 or 3 ticks.

Fixed $250 a trade (trades a week / PF / $ a month / max DD):

| Scenario | 2026 Jan-Jun | Jul-Oct 16 | 2025 | 2021-24 |
|---|---|---|---|---|
| 1 / 1 | 4.06 / 2.92 / $3,012 / -$1,062 | 2.95 / 2.55 / $1,415 / -$876 | 4.30 / 1.17 / $364 / -$4,871 | 4.71 / 1.06 / $152 / -$11,403 |
| 10 / 10 | 2.39 / $2,614 / -$1,476 | 2.07 / $1,172 / -$1,177 | 0.90 / -$269 / -$8,781 | 0.80 / -$638 / -$34,062 |
| 10 / 1 | 2.62 / $2,782 / -$1,188 | 2.26 / $1,272 / -$1,033 | 1.01 / $24 / -$6,927 | 0.91 / -$269 / -$22,961 |
| 10 / 2 | 2.59 / $2,763 / -$1,220 | 2.24 / $1,261 / -$1,049 | 1.00 / -$8 / -$7,133 | 0.89 / -$310 / -$24,194 |
| 10 / 3 | 2.56 / $2,745 / -$1,252 | 2.22 / $1,250 / -$1,065 | 0.98 / -$41 / -$7,339 | 0.88 / -$351 / -$25,428 |
| 13 / 1 | 2.53 / $2,705 / -$1,294 | 2.18 / $1,224 / -$1,086 | 0.97 / -$89 / -$7,612 | 0.86 / -$410 / -$27,107 |

25K eval (tools/atlas_v2.score, ATLAS's eval rule; 2-week pass %, fail %, median sessions to pass):

| Scenario | 2026 Jan-Jun | Jul-Oct | 2025 | 2021-24 |
|---|---|---|---|---|
| 1 / 1 | 61.3 / 0 / 6 | 43.5 / 0 / 7 | 24.9 / 0 / 5 | 19.3 / 0 / 4 |
| 10 / 10 | 57.1 / 0 / 6 | 39.1 / 0 / 7 | 20.5 / 0 / 5 | 16.4 / 0 / 4 |
| 10 / 2 | 59.7 / 0 / 6 | 40.6 / 0 / 8 | 22.1 / 0 / 6 | 17.4 / 0 / 5 |

Answers (fixed by the design):
- **Does the edge change?** A little, not the verdict: 2021-24 PF 0.80 -> 0.89 (still under 1.0) and 2025 0.90 -> 1.00.
  ATLAS is still a 2026-market strategy with no long-run edge at real entry costs.
- **Does the sizing change?** No. Room 60% (with the streak rule) vs the live 40% at stop 1 / 2 / 3: 60% loses the account more
  often every time (H1 5.4 -> 6.6%, 5.4 -> 6.9%, 5.3 -> 7.1%; H2 2.7 -> 4.8%, 3.6 -> 5.5%, 3.7 -> 6.4%) for +$3-11 a month.
  No card.
- What it does change: every ATLAS study today used 10 / 10, so its $ was about $20-25 a month low and its loss odds 1.5-2
  points high, the same way for every option compared; the decisions taken today (room 40%, streak) stand at either cost.

## #14 the nightly real-cost alarm (tools/cost_alarm.py, alarm only)

Each night per bot: the measured entry cost = the median of its real fills vs the model price (tools/fill_cost on the pulled
PC days; else the stored fill study), the stop at 2 ticks, a target at 0. The bot's model trades of the last 40 sessions and of
2026 H1 are re-priced at that cost (R per trade at a fixed risk): **RED** when the last-40 PF < 1.0, **AMBER** under 1.3 or
under half of its 2026 H1, **NOT ENOUGH FILLS** while fewer than 5 real fills exist (no alarm on noise). Writes
research/lab/costs.json; changes no bot.

Tonight:
- ATLAS at real costs: NOT ENOUGH FILLS · last 40 sessions PF 2.27 vs 2026 H1 2.57 at +11 ticks a fill (median of 3)
- Zlarior at real costs: NOT ENOUGH FILLS · last 40 sessions PF 3.38 vs 2026 H1 3.20 at +3 ticks a fill (median of 1)

Both would read GREEN with enough fills. tests/test_cost_alarm.py 9/9. Wiring (lead): one call in the nightly job
(tools/learn_night.py or the PC's daily report) and the line on the ZEUS card next to the fills line.

## Files

tools/atlas_costs_split.py, tools/cost_alarm.py, tests/test_cost_alarm.py, research/second/atlas_costs_split_design.md,
research/second/atlas_costs_split.json, research/lab/costs.json. No engine file, no model file changed.
