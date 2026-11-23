# Get NQ ticks (free)

Why: the 3 order-flow tests (research/orderflow/PREREG_ticks.md) run by themselves once **60+ days** of ticks are on disk.
Nothing here can trade. It only reads NinjaTrader's free history.

## A. Automatic (zero clicks after a one-time install; only once the red team has OK'd LE_TickRec.cs and it is on `pc`)
1. One quiet evening:
   - copy `ninjatrader\LE_TickRec.cs` to `Documents\NinjaTrader 8\bin\Custom\AddOns\`;
   - in NinjaTrader open the NinjaScript Editor and press **F5**;
   - if F5 shows a red error in LE_TickRec, delete the file and press F5 again: nothing else changes.
2. In the Olympus folder: `pip install pyarrow && python -m engine.tickrec enable`
3. That's it. From then on:
   - **Ticks:** the add-on records live ticks. Every weekday from 16:05 to 02:00 ET, and all weekend, it also fetches past
     days, newest first, up to 365 days back or as far as NinjaTrader's server goes. It never fetches while the bot trades.
     It fetches one day at a time and stops if the disk drops under 10 GB free.
   - **Study:** the PC's 15-minute report task imports the ticks outside trading hours. At 60 NQ days it runs the test
     once, and again when the backfill is finished.
   - **Result:** one line on your phone: "Order-flow test ran on N tick days: ...".
   - **Progress:** `python -m engine.tickrec status`. The recorder line shows `backfill_days=` and `oldest=`.
   - **Stop:** `python -m engine.tickrec disable` stops recording, the backfill and the study.

## B. By hand (if the automatic way is not installed yet)

## 1. Download (NinjaTrader 8, connected = green)
1. **Control Center → Tools → Historical Data**.
2. Under **Download**: tick the **NQ** contract below, **Interval = Tick**, **Data type = Last**, set start and end, then click **Download**.
   NinjaTrader keeps about the **last 12 months** of ticks. An empty month just isn't on its server.

| Contract | Start | End |
|---|---|---|
| NQ 12-25 | 2025-11-24 | 2025-12-11 |
| NQ 03-26 | 2025-12-12 | 2026-03-12 |
| NQ 06-26 | 2026-03-13 | 2026-06-11 |
| NQ 09-26 | 2026-06-12 | 2026-09-10 |
| NQ 12-26 | 2026-09-11 | today |

## 2. Export (same window)
1. Make the folder `Documents\NinjaTrader 8\le_ticks\export` (one time).
2. Under **Export**: same contract, **Interval = Tick**, **Data type = Last**, same dates, then **Export**. Save into that folder
   and keep NinjaTrader's name (`NQ 12-25.Last.txt`). Do this once per contract, so you end up with 5 files.
   They are large: expect several GB in total.

## 3. Import (Olympus folder, one line)
```
pip install pyarrow && python -m engine.tickrec import
```
- It reads every `.txt` in that folder. It takes about 30-60 minutes for a year, and re-running it is safe.
- Each file prints a line. Check two things:
  - `tz_check` should say `OK busiest minute 09:30 ET`.
  - `with_bid_ask%` should be near 100.
- NinjaTrader exports in UTC, and the import already expects that. You don't need a `--tz`.
- If it says `CHECK --tz`, delete the `data\ticks` folder and tell Claude.
- Once it works, delete the big `.txt` files to free the disk.

## 4. Run the tests
```
python research/orderflow/of_study.py
```
At 60+ tick days it switches to REAL mode by itself, and the results go to `research/orderflow/results.json`. Send Claude "ticks in".
