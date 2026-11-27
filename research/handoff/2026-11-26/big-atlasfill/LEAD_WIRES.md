# big-atlasfill: what the lead wires (2026-11-26)

Write-up: research/writeups/atlasfill-2026-11-26.md. Nothing here touches the live bot; engine/atlas_exec.py is OFF and Sim-only.

1. engine/live.py (two lines, lead only; ready as `live_py_fast_lane.patch` here: `git apply research/handoff/2026-11-26/big-atlasfill/live_py_fast_lane.patch`).
   The helper could not commit it: helpers never edit engine/live.py, and the permission check held to that. In the poll's `if model == "lit":` block, right after the state save and BEFORE
   `self._account_c_tick(...)`:
       from . import atlas_exec as _ax
       _ax.early(self, df_full, df1, sym, now)
   and the existing line becomes:
       if not _ax.done(self, now): self._account_b_tick(df_full, df1, sym, now)           # account B (OFF by default)
   With the switch OFF (default) early() returns "off" at once and done() is False, so the poll is exactly today's.
   Note the ordering trade-off already in the comment there: BLITZ (account C) wants the next-bar open too. ATLAS going first on
   a 5m close delays account C by account B's tick (BLITZ is paper / hidden today).
2. Sim101 week (owner, one command): `python -X utf8 -m engine.atlas_exec --sim-week on` (refuses unless account B and every
   Rapid / combo ATLAS lane is Sim; prints what changed). EOD line: `engine.atlas_exec.report()['words']` (fills n, avg ticks
   worse vs the 14 baseline); `--report`. fast_entry stays its own yes (it also moves Zlarior's real-account timing). After 10+ ATLAS fills: then re-run
   `python -X utf8 research/atlasfill/forensics.py` + `entries.py all` with the new fills (the calibration reads them).
3. Field names for the zeroerr / big-execution helpers (fills.jsonl.gz): lane, side, qty, intended, filled, ticks, order_type,
   signal_t, send_t, ack_t, fill_t (engine/atlas_exec.FIELDS). atlas_exec.log_fill(row) writes logs/atlas_exec_fills.jsonl until
   the shared fills file exists; the adapter's send / ack / fill times are what is still missing from the PC ledger.
Tests: python -X utf8 -m tests.test_atlas_exec (area nq + pc).
