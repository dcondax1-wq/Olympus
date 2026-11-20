# day-speed REPORT (2026-11-20): the NQ bot's speed and fills

## For the owner (one minute)

**The bot reacts in about 2.7 seconds; 2 of those are a built-in wait. The code part can be cut by more than half for free
(same trades). The 2-second wait is where the money is, but I can't prove the $ without tick data, so no switch is
proposed today.**

| What | Result | $ a month (real fills) |
|---|---|---|
| Real entry fills so far (4) | ATLAS 10 / 12 / 16 ticks worse than the bar's open, Zlarior 4 (backtest counts 1) | ATLAS ~$5.50 a micro a trade below its backtest |
| Where the time goes | 2.0 s wait (by design) + ~0.5 s bot work + ~0.15 s NinjaTrader / broker | - |
| 2 free speed-ups (same trades, proven on 2,304 replayed polls) | bot work 0.49 s -> 0.22 s (-56%) | ~$10-25 (est., not provable) |
| Fast entry (built, OFF): skip the 2 s wait | order ~1.8 s sooner, same trades | $0 to ~$160 (central ~$100); can't be proven from 1-minute bars |

Next: nothing for you. The lead wires the 2 speed-ups (no trade changes). Fast entry stays OFF unless you want to try it
as a test (your yes/no, through the lead).

## 1. The live loop, measured (job 1)

Order of events on the PC for an entry (engine/live.py `_loop` / `poll_once`, engine/ninjatrader.py `send`):

| Step | Time after the fill bar opens | Source |
|---|---|---|
| First trade of the new minute: LE_BarFeed appends the closed 1m bar (and 5m at a 5m close) and writes the minute's open | ~0 s | ninjatrader/LE_BarFeed.cs (OnBarClose + OnMarketData) |
| Bot waits for its poll | until +2.0 s | engine/live.next_wake offsets (2, 32) |
| Poll: read files, merge with history, clean, LIT model, route | +2.0 -> ~+2.5 s (replay median 0.49 s, p90 0.65 s) | research/speed/replay_harness.py (this cloud machine, 3 replays at once) |
| Order file written + moved into incoming\, NinjaTrader picks it up, broker / CME | ~+2.65 s (est. 0.15 s) | engine/ninjatrader._send_lines (waits for pick-up) |
| Fill confirmed, bracket sent and verified, THEN the ledger row is stamped | +3 to +5 s | the 3-5 s in night-nqlive's table is this stamp, after the fill: the order itself left ~1-2 s earlier |

Where the 0.49 s of bot work goes (replay, median per poll): 1m bars 240 ms (file parse 82, merge with history + archive 90,
clean 23), 5m bars 155 ms (history + archive merge 54 + feed merge 52, clean 28), LIT model 62 ms, everything else < 5 ms
(state save 1, Bot Brain 4, routing 2). ATLAS routes after LIT in the same poll; the parts in between take < 5 ms.

Exact PC numbers (send time, fill time) exist only on the PC: every NinjaTrader leg keeps `sent_at` and `fill_mtime`
(engine/fill_audit `_leg_view`). `tools/research/fill_timing.py` splits every fill into open -> sent -> filled as soon as the
PC's day files are pulled (`python tools/data_pull.py --latest`, answered after 16:00 ET). Asked today (request sent
11:15 UTC); see the end of this report for whether it arrived before the deadline.

## 2. Fast entry (job 2)

Replay (2026-11-16..18, 2,304 polls, the Nov 16 06:16 Zlarior BUY reproduced with its real stop 27,735.25): ON vs OFF give the
same ledger (same side, size, stop, target, exit, $) and the order 2 s earlier (route stamp +0 s vs +2 s after the bar's
open). Risks checked: double orders - no (one first-tick poll per minute, `_tick_b`; routing is once per entry_t); partial
bars - no (LE_BarFeed writes a bar only when it has closed; fast entry also waits for the 5m file at a 5m close and for the
minute's open); CPU - 0.025 ms a check, ~1 ms a minute; a quiet minute falls back to today's +2 s.

$: unknown in sign for a single fill. The 4 fills all moved the trade's way between the open and the fill, so earlier would
have helped IF the move builds over the seconds (sqrt path: ATLAS -5 ticks, LIT -1.3 per entry = ~$100 a month; linear:
~$160), not at all if it all happened on the first tick, and a minute that overshoots and reverts (Nov 6: down 8.5 then
up 12) can make an earlier fill worse. research/speed/fast_entry_value.py(+json). Pre-registered rule: a "turn on" card only
if the low end is above $0. It is $0, so **no card**. What would settle it: a few weeks ON with `sent_at` / `fill_mtime`
recorded (the cost of being wrong is a few $ a trade either way), or MNQ tick data from NinjaTrader.

Why it matters more than $100: at real fills ATLAS has no long-run edge (2021-25 PF 0.80 at 10 ticks a side vs 1.06 at 1;
research/writeups/atlas-fills-2026-11-20.md). Half the entry slippage back would move ATLAS a long way toward its backtest.

## 3. Cheap speed-ups, no decision change (job 3), ranked

| # | Change | Poll saved (replay) | Proof |
|---|---|---:|---|
| 1 | engine/ninjatrader `load`: parse only the appended tail of LE_BarFeed's file | -68 ms (493 -> 425) | same frame in 11 cases incl. trim / torn / rewrite (tests/test_speed_tail_load.py); NT selftest 79/79 patched; replay same ledger |
| 2 | engine/live `_read_hist`: NQ 1m / 5m history cut to 150 days before the per-poll merges (LIT / ATLAS read <= ~70) | -193 ms (493 -> 301) | replay: same ledger, same log lines, same LIT state on all 2,304 polls |
| 1+2 | both | **-274 ms (493 -> 219, -56%)**; p90 646 -> 335 ms | same |

Exact patches + how to check: LEAD_WIRES.md (patch_1_tail_load.diff, patch_2_hist_cap.diff). On the slower PC the saving
is likely larger in ms. Worth ~$10-25 a month at ATLAS's measured drift (~4 ticks a second if linear; less if front-loaded).

## 4. Fills (job 4): small sample (4 entries, 0 priced exits)

| Bot | Order type | Fills | vs the bar open | vs backtest (1 tick) | Timing part | Price part |
|---|---|---:|---|---|---|---|
| ATLAS | MARKET entry at the 5m open | 3 | 10 / 12 / 16 ticks | +9 / +11 / +15 ticks = $9 / $11 / $15 (2 micros) | ~9-15 ticks | ~1 tick (spread) |
| Zlarior (LIT) | MARKET entry at the 1m open | 1 | 4 ticks | +3 ticks = $1.50 (1 micro) | ~3 ticks | ~1 tick |
| both | exits: bracket STOPMARKET + LIMIT, CLOSEPOSITION | 0 priced | unknown (no exit fill prices in the rows) | - | - | - |

Timing vs price: with 1-2 micros there is no book-depth cost; the spread is the 1 tick the backtest already counts. The rest
of the gap is the market moving during the ~2.65 s before the order arrives: by the clock, ~75% of that time is the 2 s wait,
~19% the bot's work, ~6% NinjaTrader / broker. Sample: 4 fills. Not enough for a strategy change (atlas-fills write-up has
the cost study at 3 / 6 / 10 ticks).

## Tests

No live file changed on this branch (only research/, tools/research/, one new test).

| Check | Branch | Copy with patches 1 + 2 applied |
|---|---|---|
| tests/test_speed_tail_load.py | 11/11 | 11/11 |
| `python -m engine.ninjatrader --selftest` | 79 pass / 0 fail | 79 / 0 |
| `python -X utf8 -m tests.test_lit_live --quick` | OK (120/120 identical, LiveBot 1/1 entry + exit) | OK (same) |
| tests.test_fast_entry / test_account_b_funded | - | 21/21, 67/67 |
| tests.test_second_account_b | - | 71 pass / 0 fail, stopped at my 15-min cap before the end |
| `python tests/smoke.py` | 7/8: test_zenith_mode needs the Python playwright module (missing in this container) | - |
| `python tests/run_area.py nq` | ran to the 40-min cap; FAIL only in holidays / eval_lifecycle / live_board = `No module named 'fastapi'` (container, not this branch); every other suite PASS | - |
