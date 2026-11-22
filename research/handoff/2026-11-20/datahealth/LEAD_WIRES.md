# LEAD_WIRES: data health (day-brief, 2026-11-20). Nothing lands before the weekend (your note).

1. **engine/ninjatrader.py (yours; helpers never edit engine/*)**: `git apply research/handoff/2026-11-20/datahealth/ninjatrader_es_feed.patch`
   then `python -m engine.ninjatrader --selftest` (expect 80 PASS, 0 FAIL) and `python -X utf8 -m tests.test_roll_now`
   (43/43). After it lands, drop the last check of tests/test_data_health.py ("this branch does NOT edit the live
   engine/ninjatrader.py") or flip it: it pins today's state on purpose.
   Owner side: none (the bot rewrites le_feed\feed_instruments.txt within 3 min; the LE_Feed add-on picks up MES). Chart mode
   (no add-on) needs an MES chart with LE_BarFeed to get ES bars: say so in STATE if the PC runs chart mode.
2. **tests/run_area.py**: `AREAS["nq"].append("data_health")`  (test_dec_roll is already in the area).
3. **STATE.md line**: Data health (day-brief 2026-11-20, research/handoff/2026-11-20/datahealth/REPORT.md): board.py read
   has a DATA line (stale = more than 3 sessions, one Board note per newly stale file); data_pull records the Dec roll from
   the PC's bars when the offset is steady (test_dec_roll E); ES feed patch waiting for the lead (MES with MNQ).
4. CLAUDE_REFERENCE "Key commands": `python tools/data_health.py` (one line per data file).
