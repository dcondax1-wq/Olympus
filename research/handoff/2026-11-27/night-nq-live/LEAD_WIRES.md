# night-nq-live: what the lead wires (files I do not own)

1. **Register the test in run_area nq**: add `tests/test_nq_live_trades.py` (`python -X utf8 -m tests.test_nq_live_trades`, browser part with `--shots`) to the `nq` area in `tests/run_area.py`.
2. **Longer trade history in the feed** (pc_report / status post): the journal now shows up to 30 closed trades, but the feed only carries the newest ~4 per account (`at`) plus board trades. Ask: carry the last 30 real closed trades (same row shape `[entry_t, exit_t, dir, qty, entry, stop, target, exit_kind, usd, r]`, BLITZ excluded) either as more `at` rows or a new `jr` block. livecore.journal() already merges whatever rows arrive; no page change needed for more `at` rows (a `jr` block needs a 1-line read in livecore.build).
3. **Fill quality for more trades**: `fq.fc` covers 36 h / 4 rows. Widening it to the same 30 trades lets every journal row show "entry +N ticks" (slip grade clean <=1, ok <=4, poor >4).
4. **sw.js cache list**: live.js / livecore.js / live.css are now imported with `?v=2`; bump the nq entries in sw.js if it pins versions.
5. Optional: a "Journal" link to `nq/live.html#jr` from the NQ hub tile.
