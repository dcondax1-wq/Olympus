# Missed-money audit: every bot lane on every account, Oct 19 - Nov 27 2026

The lead's question (after today's ATLAS funded miss): for EVERY lane x account since Oct 19, did each account that should have
traded each backtest signal route it, at the right size, and fill near the model? Every miss with its $ and cause.
READ-ONLY research plus bot-side fixes on branch `day-moneyaudit-bot` (no live setting touched).

- **Data.** `tools/money_audit.py` -> `research/moneyaudit/AUDIT.json` (every row with its evidence).
- **Twins.** Re-run on the PC's bars to Nov 27 13:10 ET:
  - LIT: `engine/lit.run_x`, live params.
  - ATLAS: `engine/second.run`, its 3 members, its own one-position rule.
- **Live side.**
  - The PC's day folders, all 30 pulled tonight: trades, fills, uptime, and the bot's own "not routed" lines.
  - `trading/trades.json`.
  - The PC's status post.
- **Sizes.** Every lane is sized by its OWN rule, using the real functions:
  - LIT: two_week.
  - The Rapid: `stack_qty` + its 30% best-day rule.
  - The combos: `combo50k.atlas_qty`.
  - ATLAS funded: `funded_qty` (Nov 20 and Nov 27).
  - ATLAS's eval: its live micros (2). Its need sizing needs its PC state, so this is labelled an estimate.

Sign: **live minus twin**. Minus = money left on the table; plus = the miss dodged a loser.

## The table

| Lane | Account | Misses | $ (live - twin) | Cause | Fixed? |
|---|---|---|---|---|---|
| ATLAS | ATLAS funded 25K | 1 (Nov 27 S/R +1.99R) | **-$302** | **BUG**: STARTUP DISARMED all day. Its NinjaTrader state file was found torn at the Nov 26 22:01 ET restart, and the hold only a FLAT position file could clear never cleared: NinjaTrader writes none for a flat account after its restart | **YES** (this branch): `ninjatrader._flat_by_account_row` + live_guard alarm |
| ATLAS combo | Zlarior 25K #2 | 1 (Nov 27 S/R) | **-$302** | **BUG**: the same torn-state hold (`ninjatrader_state_b25k_2x.json`). The combo WAS on | **YES** (same fix) |
| ATLAS | ATLAS 25K (its eval) | 1 (Oct 27 03:30 MACD LONG 3, +7.97R) | **-$1,657** | order REFUSED: the account Name without the 'R' (the same bug as LIT that day). Missing from the Nov 27 audit | yes, Oct 27 (`_nt_said_no_account`) |
| ATLAS | ATLAS 25K (its eval) | 5 (Nov 10-13) | +$917 | PC bot OFF Nov 9 15:55 -> Nov 15 20:39 ET (5 losers dodged) | yes (report task, hands-free, Telegram /status) |
| LIT | Zlarior 50K | 1 (Oct 27 06:12) | +$690 | order refused: account Name bug (a loser) | yes, Oct 27 |
| LIT | Zlarior 50K | 2 (Nov 10, 11) | +$390 | PC bot off (losers) | yes |
| LIT | Zlarior 50K | 1 (Nov 3 15:39) | -$54 | not armed: re-set up by hand after the signal | owner step (now hands-free) |
| LIT | Zlarior 50K | 1 (Oct 26 08:37) | -$1 | bot / feed gap 08:30-08:45 | watch (a BE trade) |
| ATLAS | Rapid EOD 25K | 0 | $0 | Nov 20 EMA +6.6R: **by design, size 0**. Its 30% best-day rule caps a winner at $427.50 and 1 micro paid $512.30. The Nov 27 audit's "-$1,659 not armed" was wrong (corrected) | - |
| ATLAS combo | Zlarior 50K | 0 | $0 | Nov 27 S/R traded 1 micro +$304.10 = its rule (eval x0.5) | - |
| ATLAS | Rapid EOD 25K | 0 | $0 | Nov 27 S/R traded 1 micro +$304.10 = its rule | - |
| LIT | Zlarior 25K #2, Rapid EOD 25K (LIT lane) | 0 | $0 | no LIT twin signal since they started (Nov 18 / Nov 20) | - |

**Left on the table: -$2,316.10** = $1,657 + $302 + $302 + $54 + $1. **Losers the misses dodged: +$1,996.73.**
**Size:** every trade that went through matched its lane's own size. **Fills:** every fill within $5 of the twin; today's
fill was 9 ticks better.

Not a gap: the PC's own log has one more. On Nov 20 at 06:20 ET its model entered during a short gap, never routed; that trade
stopped out, a dodged loser. The cloud twin, on the same day's bars, had no trade there. Also: ATLAS twin trades of Oct 20 -
Nov 5 (except Oct 27) are not counted. No ATLAS live row exists before Nov 6 in the cloud or the PC's day folders (their
trade files are empty before Nov 4), and the Nov 17 balance fits trades from Nov 6 on.

## What was wrong and is now fixed (branch `day-moneyaudit-bot`, red team next)
1. **The torn-state hold that never cleared** (`engine/ninjatrader.py`). A JSONDecodeError on the NinjaTrader state file blocks
   new entries until the account is proven flat. The only proof was a FLAT position file for every contract, and a flat
   account has none after a NinjaTrader restart. So ATLAS funded and the 25K #2's combo lane sat out all of Nov 27, and the
   hold is SAVED, so they would sit out Monday too. Second proof, same never-guess rule:
   - the account's own fresh `le_feed\accounts.csv` row reads unrealized $0.00
   - on 3 reads over >= 5 min
   - while the chart moved >= 1 pt (one micro would show >= $2)
   - no position file says otherwise
   - no leg is open
   - the orphan-order cancel still runs.
2. **No alarm** (`engine/live_guard.py`). The instant MISSED push read B's held "STARTUP DISARMED" as the account's own rule,
   and read an old open record as "in a trade". Now a disarm / feed-stale / guards-failed hold, a late check and an EARLIER
   day's record all push. The combo lanes (`acct_x`) are checked and get the 01:55 / 09:00 armed lines.
3. **Nothing showed the lanes.**
   - The feed's core `ab` now carries `cb` (the combo switch's accounts, last 4) and the ext block `abl` (each Rapid / combo ATLAS
     lane: open record, today's skips).
   - The PC's day folders carry every lane's skip reasons (`datapipe` `held_atlas`).
   - trade_watch checks every lane.
4. **The Rapid's ATLAS trades never reached the phone** (`engine/feed_trades.py`). They live in the lane's own state file, so the
   Trading page / Week in Review said "1 live trade +$304" on a +$608 day.
5. **Cloud data corrected:**
   - the Nov 20 Rapid row in `research/livegap/missed_2026-11-27.json` + its write-up is now NOT A GAP
   - `nq/week_review.json` rebuilt ("Skipped by design").

## Still open
- What tore BOTH state files in the same second (Nov 26 22:01:57 ET)? The saves are tmp + replace. Look at the two
  `.corrupt-1795748517` files on the PC (empty? cut short?).
- `data/pc_days` before Nov 4 have no trade rows: the PC's ledger archive started later, so October live trades are only in
  `trades.json`.
