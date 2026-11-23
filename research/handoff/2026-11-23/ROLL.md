# December 2026 roll: MNQ 12-26 -> MNQ 03-27 (night-roll audit, 2026-11-23)

**Verdict: ready. If the owner does nothing, no money is put at risk. The cost is missed entries until the chart is switched.**
The owner's best path is still one click on Wed Dec 9 evening (ROLL.bat, or TRADING HOME > R). The phone reminds him Mon-Wed.

## The dates (cited)

| What | Date | Source |
|---|---|---|
| Dec contract (Z26) last trading day / expiry | Fri **Dec 18 2026**, 09:30 ET (SOQ) | CME Equity Index roll dates page, https://www.cmegroup.com/trading/equity-index/rolldates.html |
| CME's *customary* roll date (lead month changes) | **Mon Dec 14 2026** ("the Monday prior to the third Friday"; 2026: 3/16, 6/15, 9/14, 12/14) | same CME page |
| **The bot's order switch** | **Thu Dec 10 2026, 00:00 ET** (8 days before expiry: `engine/ninjatrader.nt_instrument`) | code (`docs/ROLL_DEC_2026.md`) |
| TradingView NQ1! / ES1! switch (research exports) | Mon Dec 14, 18:00 ET (Sep was Mon Sep 14 18:00, `data/NQ_rolls.json`) | data on file |

**The Thursday vs Monday difference (for the lead, no change made).** CME's convention moved to the Monday, while the bot rolls
on the Thursday before. Keeping Thursday is deliberate and fine:
- What matters is that chart and orders share one contract: the roll guard enforces that whatever date NinjaTrader's own
  rollover list uses (I could not confirm NinjaTrader's Dec date online. The owner can see it under Tools > Database
  Management > Rollover, but it is not needed).
- By Thu Dec 10 the March contract trades heavy volume. It is not the thin back month that MFFU's fair-play rule is aimed at.
- Moving the bot to the Monday would change the routing date in about 10 places, and every roll test and reminder is built on
  Dec 10. That is not worth it two weeks before the roll.

**MFFU's rules.** I found no written MFFU rollover rule. Its help centre says positions are closed at session end, so
nothing is held overnight on any plan the bot uses. Its fair-play rules ban profiting from "stale or unrealistic fills in
low-liquidity contracts (including back-month contracts)":
https://help.myfundedfutures.com/en/articles/8444599-fair-play-and-prohibited-trading-practices.
The bot follows the rule: it trades the contract it switches to on Dec 10 (by then the most active one) and never trades
the expiring one after the switch. Builder guide: https://help.myfundedfutures.com/en/articles/14290805-builder-plan-50k-a-comprehensive-guide

## What happens, step by step (tests: `tests/test_roll_dec_audit.py` 24/24 + `test_dec_roll` 37/37, `test_roll` 23/23, `test_nt_roll_guard` 10/10)

| When (ET) | Owner does nothing | Owner runs ROLL.bat Wed evening |
|---|---|---|
| Thu Dec 3 | Launch checklist / Start page: "roll Thu Dec 10" info line | same |
| Mon Dec 7 - Wed Dec 9 | One ntfy push a day; Wed's READY check shows **WARN "Contract roll tomorrow"** (new) | same |
| Wed Dec 9 15:55 | Every bot flat (flat_mod 955). No entry is possible until 02:00 (test B1), so nothing is open at the switch | ROLL.bat waits for flat, shows the click (chart > MNQ 03-27), checks it, removes an old pinned contract |
| Thu Dec 10 00:00 | Orders switch to MNQ 03-27 for every account (Zlarior, ATLAS, 25K #2, Rapid, keep-alive; one adapter class) | same |
| Thu Dec 10 00:00+ | The LE_Feed add-on (no-chart mode, not used yet) follows by itself: `feed_instruments.txt` is rewritten | same |
| Thu 01:15 / 01:40 | **READY check: NOT READY "Chart still on MNQ 12-26"**, fix ROLL.bat (new); the ops tick pushes "Chart still on MNQ 12-26: no new entries" | READY, "Roll done" push |
| Thu 02:00 onward | **Every entry refused** by the roll guard: LIT, ATLAS, the extra accounts and the **keep-alive** (test B3/B4). No order goes to the expiring contract and no December-priced stop goes to March. Missed trades = the only cost | trades as usual on March; older bars back-adjusted (`engine/pcbars.merge_basis`) |
| any time | A pinned `nt_instrument: MNQ 12-26` is refused past the roll even if the chart stays on 12-26 | ROLL.bat removes the pin |
| a leg still on 12-26 after 00:00 (cannot happen with the 15:55 flat; tested anyway) | closed on **MNQ 12-26**, its own contract (test B2) | - |
| Fri Dec 18 | Dec expires; nothing is held overnight, nothing to roll | same |

**Bars (back-adjusted or not).** Entries, stops and targets are priced from the chart the bot reads and sent to the order
contract. The roll guard refuses any entry while those two are on different months, so no adjusted or December price is ever
sent to March. With the chart on 03-27, NinjaTrader's "Merge back adjusted" history plus `pcbars.merge_basis` shift older bars
onto March, and LIT's levels and trades come out identical (`test_dec_roll` A, both MNQ and NQ charts). A fill more than 0.3%
from the chart price (about 300 pts = a roll gap) is flattened at once with no bracket (`test_nt_roll_guard` 3, 6).

**Research data (TOP25 #5 "survives the Dec 10 roll").** Already built (day-brief 2026-11-20). `tools/data_pull.import_bars`
runs `roll_from_pc` for **NQ and ES** before importing. When the PC's chart is on 03-27 it measures the steady offset from
shared bars, records the NQZ26 -> NQH27 (ESZ26 -> ESH27) roll in `data/<SYM>_rolls.json` (with a backup) and shifts the
history once. If there are no shared bars or the offset is noisy, it records nothing and says why (`test_dec_roll` E). Anchors
today: NQZ26 / ESZ26 (test F1). The nightly jobs therefore do not freeze. A later TradingView export with `--roll` stays optional.

**Thanksgiving week (Nov 23-27).** No interaction with the roll. CME closes early Thu Nov 26 at 13:00 ET and Fri Nov 27 at
13:15 ET (`lit_live.early_close`), neither is a full closure, and no roll push or "soon" line appears that week. The countdown
starts Mon Dec 7 and the "soon" line Thu Dec 3 (tests E1-E4).

## Gaps found tonight, and fixed

1. **The 02:00 READY check never looked at the roll.** A chart left on 12-26 read READY while every entry was refused. Now
   `engine/readiness` reads `roll_watch.fact`: NOT READY with the ROLL.bat fix, plus one WARN the day before.
2. **TRADING HOME had no roll step.** Added **R Contract roll**: it runs ROLL.bat and reads the result back. The status
   screen shows "Roll: ... (new entries are BLOCKED)" and puts the R fix first.
3. **The three roll suites were in no test area** (`test_roll`, `test_dec_roll`, `test_nt_roll_guard`), so no landing ran
   them. They are now in the `nq` area with `test_roll_dec_audit`.
4. **Clock wording:** pc_cc_api / alerts_plus / golive now say FIX_CLOCK.bat (ops_checks already did; its test still said
   'Sync now', fixed). guards.py and live_board.py are handled on night-clockauto. readiness.py:380 still says 'Sync now'
   (another builder's line, and test_ready asserts it).

Not built, on purpose: switching the chart automatically. NinjaTrader cannot change a chart's instrument from outside, and
the LE_Feed add-on that would make it automatic is not compiled on the PC yet (docs/CLAUDE_REFERENCE.md "No-chart mode").
Following the old contract after the switch was also rejected (MFFU fair-play, and a live-money choice).

## What the owner does

1. **Wed Dec 9, after 16:00 ET:** double-click **TRADE_HOME.bat > R** (or ROLL.bat). Do the one NinjaTrader click it shows.
   It says **Roll ready**.
2. If he forgets: the 01:15 READY alert and the "Chart still on MNQ 12-26" push say the same thing. Same step, any time.
