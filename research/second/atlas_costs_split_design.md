# ATLAS split costs + nightly cost alarm - pre-registered design (2026-11-20, day-atlasedge, ideas #8 / #14)

Written and committed BEFORE any run. Tool: tools/atlas_costs_split.py -> research/second/atlas_costs_split.json.
Write-up: research/writeups/atlas-costs-split-2026-11-20.md. RESEARCH ONLY.

## #8 split costs
Real exit fills: none in reach (no PC data branch on the remote, no exit price in the board rows; the 3 known real fills are
entries, 10 / 12 / 16 ticks). So the stop cost is a scenario, not a measurement.
Scenarios (ticks a side): E1/X1 backtest; E10/X10 = what every study since this morning used (the stress); E10/X1, E10/X2,
E10/X3 = a late market entry and a resting stop that slips 1-3 ticks (BE / cut / flat / HEDGE exits counted as the stop);
E13/X1 = the 3 real fills' mean entry. Targets 0 always (tools/atlas_fills.priced).
Views, all with the LIVE setup (room 40% + 2 losses -> 1 micro, owner YES 2026-11-20):
- fixed $250 a trade (atlas_health.fixed_view): trades/week, PF, net $, $/month, max DD for 2026 H1, Jul-Oct 16, 2025, 2021-24;
- funded Builder 25K Monte Carlo (tools/atlas_edge.funded, 1,000 paths a market, H1 / H2 / REF = 2021-25) from today's account
  (the board's $25,401: room $1,401) and from the morning's $887: $/month, 1st payout, lost in 6 months;
- 25K eval (tools/atlas_v2.score, ATLAS's eval rule, one process per scenario): 2-week pass / fail, median days to pass.
Questions, answered by fixed rules:
- "Does the edge change?" = 2021-24 PF and 2025 PF at E10/X2 vs E10/X10 (stated; PF >= 1.0 = a long-run edge at that cost).
- "Does the sizing change?" = room 40% vs 60% (both with the streak rule) at E10/X1-X3, by the atlas_risk bar (lost down
  >= 0.5 pt in H1 and H2, $ >= 90%; REF within 0.5 pt / $10). If 60% passes against 40% at all three stop costs, a Decide card;
  else none. Nothing is proposed from a single scenario.

## #14 nightly cost alarm (design + a runnable check, alarm only)
Each night per bot (ATLAS, Zlarior): the measured entry cost = median ticks of its real fills (tools/fill_cost; n shown);
re-price the bot's last 40 sessions of model trades at that cost (stop = 2 ticks, target 0) and its 2026 baseline the same way.
Flags: AMBER when n >= 5 and the last-40 PF at the measured cost < 1.3 or < half its 2026 baseline; RED when PF < 1.0;
"not enough fills" while n < 5. Output research/lab/costs.json; never changes a bot.
