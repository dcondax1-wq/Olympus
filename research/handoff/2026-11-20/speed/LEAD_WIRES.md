# LEAD_WIRES: day-speed (2026-11-20)

Branch `day-speed`. Nothing here touches a live file: every bot change below is an exact patch for the lead, with its test.
None changes a trading decision (same bars, same frames, same orders: proven in the replay harness and by frame-equality
tests). Ranked by time saved on the entry poll.

| # | Patch | File | Entry poll saved (replay, cloud) | Decision change | Test |
|---|---|---|---:|---|---|
| 1 | Tail reader for LE_BarFeed's bar files | engine/ninjatrader.py `NinjaTraderBars.load` | **-68 ms** (493 -> 425) | none (same frame) | tests/test_speed_tail_load.py 11/11 (+ on the patched copy), NT selftest 79/79 on the patched copy |
| 2 | History capped to 150 days before the per-poll merge | engine/live.py `_read_hist` (+ `HIST_KEEP_DAYS`) | **-193 ms** (493 -> 301); 1+2 together **-274 ms** (-> 219, -56%) | none on LIT (replay: same ledger + same model_state every poll) | replay (research/speed/replay_harness.py --patch hist_cap); lead: tests.test_lit_live --quick, test_second_*, test_account_b* |
| 3 | Fast entry (poll on the first tick) ON | data/fast_entry.json (switch, no code) | ~1.8 s (not code time: the 2 s wait) | none (same ledger ON vs OFF in replay) | tests/test_fast_entry.py 21/21; NOT proposed as a card (see REPORT.md) |

## 1. Tail reader (patch_1_tail_load.diff)

Today `NinjaTraderBars.load` re-parses the whole bar file with pandas' python engine every time it changes, i.e. every
minute for the 1m file (up to 21,000 lines: ~70 ms here, more on the PC) and every 5 minutes for the 5m file (~30 ms). LE_BarFeed
and LE_Feed only APPEND one line per closed bar between trims, so the patch parses only the new tail when the file only grew:
same file id (st_ino), same first 256 bytes, same 64 bytes before the old end, at most 16 KB more, and a full read in the last
15 minutes (backstop). Anything else (trim, startup write, rewrite, File.Copy fallback, a catch-up burst) is a full read,
exactly as today. The torn-last-line rule is kept (only lines ending in "\n" are parsed).

Apply: `git apply research/handoff/2026-11-20/speed/patch_1_tail_load.diff`
Check: `python -X utf8 -m tests.test_speed_tail_load` (compares the engine's load, after the patch, with a frozen copy of
today's load through appends, a torn line, a trim, an in-place same-length correction, junk / header / duplicate lines, empty
file) and `python -m engine.ninjatrader --selftest`.
Known difference: a file whose LAST byte is a lone "\r" (a CRLF line cut between \r and \n): today keeps that line, the
patch waits one read for its "\n". LE_BarFeed / LE_Feed write "\n" only, so it cannot happen with them.

## 2. History cap (patch_2_hist_cap.diff)

`_read_hist` hands the poll the whole TradingView export (5 years of 5m = 360k rows, all of 2026 in 1m = 320k rows); every
poll then merges it with the NinjaTrader archive (`pcbars.merge_basis`: concat + de-duplicate + sort), merges the feed again,
and `clean_bars` it, for 5m AND 1m. LIT (`lit_live.window_start`) and ATLAS (`second._window`) keep only the previous
month's first day minus 8 days (<= ~70 days). The patch keeps the last 150 days of the bot's clock (NQ 1m / 5m only; ES,
1h and other symbols untouched; start cfg `"hist_keep_days": 0` = today's behaviour) BEFORE those merges.

Apply: `git apply research/handoff/2026-11-20/speed/patch_2_hist_cap.diff`
Proof so far: research/speed/replay_harness.py, 2026-11-16..18 (2,304 polls each): ledger and LIT model_state identical on
every poll vs unpatched. NOT yet proven for the other readers of `df_full` (account C / second strategies, Bot Brain,
trade charts, `_detect_revisions`): they read windows too as far as I could see, but run before wiring:
`python -X utf8 -m tests.test_lit_live --quick`, `python tests/run_area.py nq`, the ATLAS tests (test_second_account_b,
test_account_b_funded). If any differs, drop patch 2 (patch 1 stands alone).

## 3. Fast entry

No wiring needed: it is built and OFF. Measured in the replay: ON vs OFF same ledger, same entry, the order 2 s earlier;
its wait loop costs 0.025 ms a check (~1 ms a minute). Not proposed as a Decide card (pre-registered rule: only if the low
end of the $ band is > $0; it is $0, and an overshoot-then-revert minute can make an earlier fill worse). If the lead wants
the measurement anyway, the only way to get it without tick data is to run it ON and compare fills (tools/research/fill_timing.py
reads sent_at / fill_mtime from the PC's day files): a strategy yes/no for the owner, ~$0 to +$160 a month expected, at most
a few $ a trade either way. The switch: `python -X utf8 -m engine.fast_entry --on` (PC, any time; `--off` undoes).

## Do not wire

- Moving ATLAS earlier in the poll: it routes after LIT + state save + Bot Brain, but those take < 5 ms in the replay.
- Lower poll offset than 2 s without fast entry: the 1m open file may not be there yet (LIT would size from a missing open).

## Files on day-speed

research/speed/PREREG.md, replay_harness.py, speedups.py, fast_entry_value.py(+json); tools/research/fill_timing.py;
tests/test_speed_tail_load.py; research/handoff/2026-11-20/speed/{REPORT.md, LEAD_WIRES.md, patch_1_tail_load.diff,
patch_2_hist_cap.diff, replay_*.json}; research/writeups/nq-speed-fills-2026-11-20.md.

Lead: after merging, rerun `python tools/writeups_index.py` (new write-up research/writeups/nq-speed-fills-2026-11-20.md; not run on this branch to keep INDEX.md free of merge conflicts with the other day helpers).

## ROUND 2 (2026-11-20 afternoon): patches 1 + 2 APPLIED on day-speed (lead review + red team before any merge)

Branch: `day-speed` (this session may only push day-speed; the lead asked for day-speed2). origin/pc merged first (bbec63b0),
then ONE bot-file commit "speed round 2: patches 1 (tail reader) + 2 (history cap) applied to the bot files": engine/ninjatrader.py
(`NinjaTraderBars.load` + `TAIL_FULL_EVERY_S` / `TAIL_MAX_GROWTH`) and engine/live.py (`HIST_KEEP_DAYS` + 5 lines in `_read_hist`).
Cherry-pick that commit alone if you want it without the research files. Undo on the PC without code: start cfg
`"hist_keep_days": 0` turns patch 2 off; patch 1 has no switch (revert the commit).

| Proof "no decision change" | Patched (day-speed) | Unpatched origin/pc |
|---|---|---|
| tests.test_lit_live FULL | 120/120 day-end trades identical; intraday 9,923 polls 0 differences (+29 on the known 2026-04-03); LiveBot 2/2 entries + exits | (the same numbers are the shipped baseline) |
| Replay through the REAL file path, LIT + ATLAS (account B paper), 2026-11-06 / 16 / 17 / 18, 3,072 polls | LIT ledger, ATLAS ledger, log lines, LIT state on every poll: identical to unpatched | ATLAS Nov 6 04:00 SELL (stop 27,078.75) and Nov 17 08:20 SELL (stop 27,432.75) = the real live stops; Zlarior Nov 16 06:16 BUY (stop 27,735.25) |
| Poll time in that replay (median / p90) | 206 / 622 ms | 504 / 961 ms |
| engine.ninjatrader --selftest | 79 pass / 0 fail | - |
| tail reader (tests/test_speed_tail_load.py) | 17/17: appends, torn line, trim, same-length in-place fix, junk, empty; NEW: read while being written in pieces (never a cut bar), file shorter than the tail, missing file, restart mid-stream | - |
| history cap (tests/test_speed_hist_cap.py) | 6/6: last 150 days only, exactly today's newest rows, hist_keep_days 0 = all, ES / 1h never cut, LIT window <= 69 days in 2026 | - |
| ATLAS / Rapid / multi-account / NT suites | account_b_funded 67/67, account_b_local 28/28, account_b_min_room 21/21, acctb_not_placed 44/44, atlas_armed PASS, atlas_funded_switches 35/35, combo_50k 56/56, combo_account 45/45, datafeed 42/42, fast_entry 21/21, fleet 131/131, lit25 26/26, multi_account 55/55, nq_live_reliability 119/119, nt_exec_audit 46/46, nt_outgoing 26/26, nt_roll_guard 10/10, pc_bars 75/75, rapid 60/60, rapid25 94/94, rapid_launch 11/11 | - |
| Pre-existing fails (same on unpatched origin/pc) | test_second_account_b 114/115 (d. "2026-08-18 25K pass lock"), test_poll_timing 14/15 ("other threads named with their CPU") | the same 2 fail there |

Found on the way (not fixed, not mine): engine/account_b.AccountB.start raises `TypeError: unsupported format string passed
to NoneType.__format__` when its block has no eval_start (room None in the "ready" line, account_b.py ~line 626): account B then
does not start ("account B NOT started" in the log). The PC's real block has eval_start, so ATLAS runs; a block written without
it would silently not trade.

Fast entry: Decide card `fast-entry` added to tools/web_public/business/decisions.json (status open, $0 / ~$100 / ~$161 a month,
recommend yes as a 2-week test, tests.test_decide 14/14). Apply note (after the owner's YES): on the PC, `python -X utf8 -m
engine.fast_entry --on`; off again `--off`.

Still coming tonight (16:05 ET check-in): today's 03:45 ET ATLAS short through the patched vs unpatched loop (needs today's
bars from the PC) and the PC's exact open -> sent -> filled times (tools/research/fill_timing.py).

## ROUND 2 evening additions

- Today's 03:45 ET ATLAS short (Fri 2026-11-20) through origin/pc e3bf212d vs day-speed 77cead01, on the PC's own bars of
  today (data/pc_days/2026-11-20/bars, appended to a scratch copy of data/): tools/update_gate.py SAME, 768 polls; both trade
  SELL 1, stop 26,419.50, target 26,122.75, exit TARGET +$514.28 = the PC's real trade (PC booked +$514.18, its BE modify row
  is not in the replay ledger). research/handoff/2026-11-20/updategate-replay/gate_fri_2026-11-20.json.
- Today's real fill: 26,375.50 vs the 1m open 26,381.00 = 22 ticks (5th fill; ATLAS median now 14 ticks).
  tools/research/fill_timing.py now reads the day bundles' trades.jsonl.gz -> research/handoff/2026-11-20/speed/fill_timing.json.
- Proposal (lead's call, engine/datapipe.py): put the NinjaTrader legs' sent_at / fill_mtime (logs/exec_audit/legs.json,
  account ids cut) into the day bundle, so the cloud can split open -> sent -> filled; today only the post-fill ledger stamp
  travels. Needed to measure fast entry if the owner says yes.

## Fill times in the day bundle (lead YES 2026-11-20 evening, data only) - commit 858111c6

- engine/datapipe.py `day_fills(day)` -> `fills.jsonl.gz` in the day bundle, packed by BOTH `datapipe.pack_day` (nightly) and
  `datafeed.pack_day` (the ntfy answer the PC actually uses). One row per MARKET entry order of the day, every account
  (Zlarior main, ATLAS acctb_, account C, fleet tags): `sent_t` = the OIF file name's millisecond stamp (logs/ninjatrader_oif.log,
  written by the adapter since October), `fill_t` / `fill_px` / `filled` / `state` = NinjaTrader's own outgoing order-state file
  (time = its mtime, archived every minute in logs/exec_audit/orders.jsonl), `leg_sent_t` = the adapter leg's sent_at when
  logs/exec_audit/legs.json has it; `sent_s_after_open`, `fill_s_after_sent`. Account names = last 4 (scrub). Read-only: it
  reads files the PC already writes; no file in the trade path changed (engine/live.py, ninjatrader.py, account_b.py untouched by
  this commit). A bad value packs the day without fill rows, never raises. NinjaTrader gives no separate exchange timestamp in
  the ATI files: the order-state file time is the best "order's own" time available.
- tools/fill_speed.py: per account, entries, seconds open -> sent and sent -> filled (median / worst), ticks past the fill bar's
  open (median / worst), $ past the backtest's 1 tick (median / worst / total). Days packed before this change fall back to the
  ledger stamp ("stamp only"). Today: atlas 4 entries, median 14 / worst 22 ticks, $45.50 past the backtest in total; zlarior 1
  entry, 4 ticks, $1.50. Seconds appear from the first day packed with this code (the PC needs the update).
- Proof: tests/test_datapipe_fills.py 15/15; test_datapipe 36/36, test_datafeed 42/42, test_fill_audit 30/30,
  test_nq_live_reliability 119/119; smoke 9/10 (test_zenith_mode: no playwright module in this container);
  update gate origin/pc e3bf212d vs 858111c6 on today's bars: SAME, 768 polls (updategate-replay/gate_fri_fills.json).
