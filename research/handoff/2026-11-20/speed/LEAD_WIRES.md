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
