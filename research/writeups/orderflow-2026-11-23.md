---
title: Order flow - what we have, what we need, first (proxy) results
family: research
date: 2026-11-23
status: plan + proxy rejection; real test waits on tick data
summary: We own zero tick / bid-ask / footprint data, only OHLCV bars. A read-only tick recorder (engine/tickrec.py + ninjatrader/LE_TickRec.cs, OFF by default) and an importer for NinjaTrader's free historical ticks are on branch day-orderflow for red-team. On a 5m bar-shape proxy of delta, none of the three proxy-testable setups holds in all of 2021-25, 2026 H1 and 2026 H2, so nothing changes in the live strategy. The real test runs by itself once 60+ days of NQ ticks are on disk.
runs: research/orderflow/of_study.py -> research/orderflow/results.json
---

## Short answer

| What | Result |
|---|---|
| Tick / bid-ask / footprint data in the repo | **None.** No tick files, no Market Replay (.nrd) files, no NinjaTrader tick exports |
| Volume data we do have | NQ 5m OHLCV 2021-10 → 2026-11 (361k bars), NQ 1m 2025-12 → 2026-11, ES 5m. Volume per bar only: no buy/sell split, no volume at each price |
| Tick recorder | Built, **OFF**, read-only, 18/18 tests pass. Branch `day-orderflow` only, not on `pc` |
| Proxy test of the 4 setups | All 3 we could test **fail** at least one span. Stacked imbalance can't be tested without ticks |
| Live strategy | **Unchanged.** Nothing was armed and no live file was touched |

## 1. What data we have (inventory)

- `data/NQ_5m.csv`: 2021-10-17 → 2026-11-19, volume on every bar (TradingView NQ1! + NinjaTrader bars).
- `data/NQ_1m.csv`: 2025-12-28 → 2026-11-19. `data/ltf/NQJ_1m.csv`: about 11.6k rows of 1m bars (a few imported days).
- `data/tv_exports/`: TradingView chunks, OHLC + volume only. `data/clean/raw/`: unadjusted 5m with contract names.
- NinjaTrader side (`ninjatrader/LE_Feed.cs`, `LE_BarFeed.cs`): writes **closed bars** and the first trade of each minute. Nothing
  records single trades, bid/ask or volume at each price.
- Searched the whole container: no `.nrd` Market Replay files, no tick CSV, no parquet.

**So: there is no real order flow anywhere.** Delta, CVD, absorption, imbalances, big prints and footprint POC all need every
trade tagged buy or sell, which we don't have.

## 2. What was built (branch `day-orderflow`, for red-team)

| File | What it does |
|---|---|
| `ninjatrader/LE_TickRec.cs` | NinjaTrader 8 AddOn. While `Documents\NinjaTrader 8\le_ticks\enabled.txt` exists, it writes every NQ/ES trade with its size and the bid/ask at that moment to `le_ticks\<ROOT>_<date>.csv` (buffered, one disk write a second). It has no Account, Order or ATI code, so it can't touch a trade. **It has not been compiled**: there is no NinjaTrader or mono here. A NinjaScript file that won't compile blocks F5 for *every* script, LE_Feed included, so install it only after review, on a quiet evening |
| `engine/tickrec.py` | `enable` / `disable` (the switch, OFF by default), `ingest` (recorder CSVs → `data/ticks/YYYY-MM-DD.parquet`), `import` (NinjaTrader historical tick export → same files), `status`, `footprint()` (delta, CVD, POC per bar). Buy/sell side: quote rule, then tick rule. Nothing in the bot imports it |
| `tests/test_tickrec.py` | 18 checks: off by default, the switch files, side rule, export parsing (with and without bid/ask), no duplicates on re-import, time-zone check, ingest of torn files, footprint math, and static safety (no trading imports, no OIF strings, no order calls in the .cs, nobody imports tickrec). Area `pc` |
| `research/orderflow/of_study.py` | The 4 setups with fixed rules. PROXY mode now. REAL mode switches on by itself at 60+ tick days (smoke-tested on synthetic ticks) |

Needs `pip install pyarrow` (free) for parquet. Without it, files are saved as `.csv.gz` with the same columns.
`data/ticks/` and `data/tickrec.json` are gitignored.

## 3. The 4 setups: rules fixed before the first run

The LIT trades come from `tools/lit_losses.run()`, the live LIT replay with costs in (662 trades, 2021-11 → 2026-10).
Entry is at the open of the entry bar, so only bars before it are used.

- **S1 Delta divergence at the LIT sweep.** Over the 3 bars ending at the sweep extreme, delta has the trade's sign (new low
  but net buying, or the mirror) → "div".
- **S2 Absorption at the RTH session high/low** (a stand-alone trade). Between 10:00 and 15:00 ET a bar makes a new RTH high
  (or low) on at least 2x its 20-bar average volume, with delta against the push (proxy: the bar closes in its lower 40% at a
  high). Fade it at the next open. Stop 1 tick beyond the bar, target 2R, flat at 15:55, first signal of the day only.
  $500 risk per trade, $1.40 per micro round trip plus 0.25 pt slippage each side.
- **S3 Stacked-imbalance continuation.** 3 or more stacked 300% diagonal imbalances in a bar that closes the same way. Enter
  at the next open, stop beyond the bar, 2R target. **Needs bid and ask volume at each price, which bars can't give.**
- **S4 LIT confirmed vs refuted by delta.** Delta from the sweep extreme to the bar before entry has the trade's sign →
  "confirmed". The question: does skipping refuted trades make more money in all 3 spans?

**Proxy delta** = volume × close location ((2·close − high − low) / range). It is a guess at delta from the bar's shape, not
order flow. It can kill an idea cheaply but can never prove one.

## 4. First results (PROXY, 5m bars): net $

| Setup | 2021-25 | 2026 H1 | 2026 H2 | Verdict |
|---|---|---|---|---|
| LIT baseline (all trades) | 535 tr, PF 1.04, **+$4,106** | 85 tr, PF 3.55, **+$30,666** | 42 tr, PF 2.19, **+$8,212** | reference |
| S1: div trades only | 103 tr, PF 1.58, +$14,013 | 18 tr, PF 2.27, +$4,077 | 7 tr, PF 0.74, −$339 | **fail**: helps 2021-25, but in 2026 the div trades are the *weaker* ones (no-div PF 4.02 / 2.53) |
| S4: skip refuted | +$5,662 better (PF 1.10) | **−$14,211 worse** | **−$4,244 worse** | **fail**: in 2026 the refuted trades were the best ones (PF 6.39 / 3.49) |
| S2: absorption fade | 271 tr (1.2/wk), PF 1.10, +$7,808 | 20 tr, PF 1.38, +$1,936 | 20 tr, PF 0.75, **−$1,616** | **fail**: 2026 H2 loses, and about 1 trade a week |
| S3: stacked imbalance | n/a | n/a | n/a | **not testable** without ticks |

What this means: the bar-shape proxy flips sign between 2021-25 and 2026, which is what a candle-shape artifact does, not an
edge. Nothing here earns a change to LIT. The one thing worth checking first on real ticks is **S1**: in 2021-25 the div
trades made +$14,013 while the rest lost −$9,907, a gap too large to dismiss before seeing true delta.

## 5. The plan

1. Owner downloads about 12 months of NQ ticks (steps below) and runs the import. No code changes needed.
2. Rerun `python research/orderflow/of_study.py`. At 60+ tick days it switches to REAL mode by itself: true delta for S1 and
   S4 on the LIT trades, real absorption for S2, real stacked imbalances for S3.
3. Usual bar: a setup must beat the baseline in 2026 H1 *and* 2026 H2, costs in, 2-4 trades a week. 12 months of ticks
   covers only 2026, so 2021-25 stays proxy-only, and a tick result is a candidate, not proof.
4. After review: install `LE_TickRec.cs` and run `python -m engine.tickrec enable` so new days record forward. Free, and it
   stays read-only.

## 6. Owner steps: download NinjaTrader's free historical NQ ticks

NinjaTrader's historical data server (the same one LE_Feed pulls bars from) serves tick history to a connected NinjaTrader 8
at no cost. How far back it goes is set by NinjaTrader. Ask for 12 months; any month that comes back empty is not on the
server.

1. Open NinjaTrader 8 and connect as usual (Control Center → Connections → your connection; it must show green).
2. **Control Center → Tools → Historical Data**. Under **Download**: open the **NQ** folder and pick a contract. Set
   **Type = Tick**, **Data = Last**, start and end dates, then **Download**. Do one contract per front-month window:
   - `NQ 12-25`: 2025-11-24 → 2025-12-11
   - `NQ 03-26`: 2025-12-12 → 2026-03-12
   - `NQ 06-26`: 2026-03-13 → 2026-06-11
   - `NQ 09-26`: 2026-06-12 → 2026-09-10
   - `NQ 12-26`: 2026-09-11 → today

   Run it overnight or on a weekend: it's large (expect several GB of text for a year).
3. Same window, **Export** section: same contract, **Type = Tick**, **Data = Last**, same dates. Save as
   `Documents\NinjaTrader 8\le_ticks\export\NQ_12-25.txt` (one file per contract).
4. Check the time zone: **Tools → Options → General → Time zone** (e.g. Eastern). Use it as `--tz` below.
5. In the Olympus folder (once per file, then delete the .txt to free disk):
   `pip install pyarrow && python -m engine.tickrec import "%USERPROFILE%\Documents\NinjaTrader 8\le_ticks\export\NQ_12-25.txt" --root NQ --tz America/New_York`
   It prints `OK busiest minute 09:30 ET`. Anything else means `--tz` is wrong: delete the `data\ticks` folder and rerun with the right
   `--tz`.
6. `python research/orderflow/of_study.py`: the REAL results land in `research/orderflow/results.json`.

Optional, for exact order-book replays: Tools → Historical Data → Market Replay can download single days of Level 1/2
replay data. Not needed for these four tests.

## Safety

- Never armed, no order path touched. `engine/tickrec.py` imports no trading module. `LE_TickRec.cs` has no Account or
  Order calls. Both are OFF until `enable`.
- Bot code is on branch `day-orderflow` only, for red-team, not merged to `pc`, so the PC does not auto-update to it.
- Not verified: `LE_TickRec.cs` was never compiled, and the NT8 export line format (`yyyyMMdd HHmmss fffffff;last;bid;ask;volume`)
  is assumed. The importer also accepts the 3-field form without bid/ask (it then falls back to the tick rule).
