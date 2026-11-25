# day-ofmax (2026-11-25): order flow at full strength - what landed on day-proedge and what the PC needs

Paper / research only. Nothing trades, arms or routes. Commits on `day-proedge` (on top of pc 1c759cfbd): 9d8e77840 (1+2),
88bab8cea (DESIGN2 pre-registration, before code), f6232b463 (3), 07dec2c57 (4) + the checks commit.

## 1. Backfill: why it stopped at 2026-09-14, and the fix
- **Cause (from the code):** LE_TickRec asks for the FRONT contract of each date. Before Sep 11 that is the expired "NQ 09-26".
  An unknown contract (GetInstrument null) or an empty answer counted toward "7 empty weekdays in a row = end of history". So
  every pass wrote `bf_NQ_end.txt` at the roll and stopped there: oldest = 2026-09-14 (the first Monday on NQ 12-26), and the
  later passes never looked further.
- **Fix:** an unknown contract is marked `.none` "v2 unknown contract ..." and NEVER counts toward the end; an empty answer
  first tries the other contract alive that day (the expiring one in its last 8 days); the end marker is now `bf_NQ_end2.txt`
  (the old `end.txt` is ignored) and an old-format `.none` is asked once more. Status line adds `bf_unknown=N`. Driver checks
  44/44 (mono, against the stubs): with "NQ 09-26" unknown, the June days behind it are fetched.
- **If NinjaTrader really has no ticks for an expired contract** (a server limit, not our code), the status line will show a
  growing `bf_unknown` / `.none` "no ticks ... NQ 09-26": then the history is the current contract only (~2.5 months), plus
  forward days. The tiny line (`tr.h` holes, `tr.e` errors) shows which on the phone.
- **Realistic depth:** NinjaTrader's own historical data servers keep about 1 year of tick data for futures (staff: "the past
  360 days", some popular instruments longer); Rithmic / CQG-type connections draw their history from those servers. That
  is ~245 NQ trading days. A plain Tradovate data feed can be far shorter (users report ~2 weeks of ticks without an add-on).
  The 23 days we already got going back 2 months says the PC's connection uses NinjaTrader's servers. Market Replay
  downloads (they hold Level 2 depth) are ~90 days and only replay inside NinjaTrader: not used.
- **Pace:** one request at a time, 5 s apart, outside 02:00-16:05 ET on weekdays (all weekend). A day of NQ ticks is one
  BarsRequest (minutes). Expect roughly 40-80 days an evening and the full year over a weekend.

## 2. Depth (market depth, forward only)
- LE_TickRec now also records NQ's top 10 levels each side ON CHANGE, at most 4 snapshots a second, to
  `le_ticks\depth\NQ_<day>.csv` (`le_ticks\depth.txt` lists roots, default NQ; `le_ticks\depth_off.txt` turns it off).
  Every MarketDepth call goes through reflection (type found by name, event bound with Delegate.CreateDelegate, Bids / Asks /
  Price / Volume as property OR field), so a NinjaTrader build with other member names gives `depth=unavailable` in the
  status line and the add-on still compiles. Python: `engine/tickrec.ingest_depth` -> `data/depth/NQ_<day>.parquet`; the
  cloud gets `of/NQ_depth5m.csv.gz` (per 5m bar: top-5 sizes, imbalance, walls, pulls / stacks, spread) with the summaries.
- **Disk (worst case, measured on a synthetic full day of 4 snapshots/s for 23 h):** raw CSV 38.5 MB/day, kept 7 days
  (~270 MB), stored parquet 7.8 MB/day (~2 GB a year), cloud summary ~4 KB/day. The 10 GB free-disk guard stops writes.
- **CPU:** the depth event handler only compares a timestamp; the snapshot (20 rows through cached reflection) runs <= 4
  times a second. Negligible next to NinjaTrader itself.
- **Recompile: NinjaTrader does NOT pick up a replaced .cs by itself unless the NinjaScript Editor is open** (it auto-compiles
  on a file change only while the editor is open). One-time PC step, quiet evening, bot flat:
  1. `copy ninjatrader\LE_TickRec.cs "%USERPROFILE%\Documents\NinjaTrader 8\bin\Custom\AddOns\"`
  2. NinjaTrader: New > NinjaScript Editor, press **F5**. Green = done. Red error in LE_TickRec: delete the file from AddOns\, F5 again.
  Until then the old recorder keeps running (no depth, the Sep 14 wall stays).

## 3. Cloud path
- One `"what": "of"` ask a night (the cloud remembers it in `data/pc_days/_of_ask.json`; the PC answers at most one of-ask a
  day), answered with up to 4 pages (<= 1.85 MB each, newest days first so the cloud's range grows backwards with no gaps),
  never more than DAILY_CAP - 2 answers a day. ~55-120 KB a day of summary -> 60-130 days a night: 250 days in 2-4 nights.
  `python tools/data_pull.py --latest --of`.
- Newer days (60 days back) ride along with every normal `--latest` pull (W2).

## 4. Battery, idea mill, Brain room
- Battery looks at 40 / 60 / 120 / 250 days (DESIGN.md note), run by the PC itself the night a look is reached
  (`engine/tickrec.battery_kick`, results under `logs/orderflow/`, one phone line via `data/orderflow_battery_note.json`, which
  pc_report now pushes), and by the cloud after every `--latest`.
- Idea mill (`research/orderflow/of_mill.py`, DESIGN2.md): 49 features x {LIT, ATLAS MD, level fades} x {hi, lo} = 294
  variants; gates: Discovery + Benjamini-Hochberg q 0.10, Holdout, deflated Sharpe >= 0.95, 20 forward days. Runs at every
  battery look. `of_mill.candidates()` = the rows the research helper's `research/ideamill` can take (not on any branch yet).
  Selftest: a planted signal passes all 3 data gates; of 163 other variants only 1 related one does.
- Brain Order Flow room (`engine/brain_feed.of_bot` + `engine/oflive`): live PAPER read from the live tick file's tail (delta
  5 / 15 min; at LIT's armed sweep level the OF1 zone read: absorbed / not / not tested) + the newest journal line
  ("Nov 25: LIT long 09:45: flow said ABSORBED -> won $312 (flow was right)", running "flow right N of M"), inside the bf cap.
  **Lead to wire (pages are yours):** the Brain page already shows the "of" bot's think lines; a dedicated room card is optional.

## ETA for the first real order-flow result
The night the PC has 40 summary days. With the new LE_TickRec F5'd: the backfill passes the Sep 14 wall the same evening, so
look 1 (battery + idea mill) can run that night or the next (Nov 26-27 if installed on Nov 25-26). Without the F5: 23 days + 1
a day = about Dec 18. Expect "TOO FEW" on the LIT filters at 40 days (about 20 LIT trades); 120-250 days are the real looks.
