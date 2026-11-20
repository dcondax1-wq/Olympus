---
title: NQ bot speed and fills - where the 2.7 s from bar open to order go, 2 free speed-ups (-56% bot work, same trades), fast entry not provable from 1-minute bars
family: other
date: 2026-11-20
status: finding - 2 read-only speed-up patches for the lead (same ledger, same LIT state on 2,304 replayed polls); fast entry stays OFF (pre-registered rule - $ low end is $0); 4 real fills, all timing slippage
summary: Owner - "NQ bot to its max - read data faster, better fills, timing." A replay harness runs the real LiveBot (paper, frozen clock) on LE_BarFeed-format files that grow bar by bar, through the real NinjaTrader read, history merge, clean and LIT model, on 2026-11-16..18 (reproduces the Nov 16 06:16 Zlarior BUY with its real stop). An entry leaves ~2.65 s after the fill bar opens - 2.0 s is the poll offset by design, ~0.5 s the bot's poll (1m bars 240 ms, 5m bars 155 ms, LIT 62 ms), ~0.15 s NinjaTrader / broker; the ledger's 3-5 s stamp is taken after the fill + bracket. Patch 1 (parse only the appended tail of the bar file) -68 ms, patch 2 (history cut to 150 days before the per-poll merges; LIT / ATLAS read <= ~70) -193 ms, together 493 -> 219 ms median, identical decisions. Fast entry ON - same trades, order 2 s earlier; worth $0 to ~$160 a month depending on the unknown price path in the first seconds, so no card. Fills - ATLAS 10 / 12 / 16 ticks past the open, Zlarior 4: almost all of it timing, ~1 tick spread.
runs: research/speed/replay_harness.py (base / tail / cap / both / fast, 2,304 polls each -> research/handoff/2026-11-20/speed/replay_results.json); research/speed/fast_entry_value.py (-> research/speed/fast_entry_value.json); tools/research/fill_timing.py; tests/test_speed_tail_load.py; pre-registration research/speed/PREREG.md (committed a6bfa536 before any run)
---

# NQ bot speed and fills (2026-11-20)

## For the owner (one minute)

**From the first trade of a new minute to the order: about 2.7 seconds. 2.0 of it is a deliberate wait, ~0.5 s is the bot's
own work, ~0.15 s NinjaTrader and the broker. Two free fixes halve the bot's work with exactly the same trades. Skipping the
2-second wait ("fast entry", built and OFF) gives the same trades ~1.8 s sooner, but whether that is worth $0 or ~$160 a month
cannot be measured from 1-minute bars, so it stays OFF.**

| What | Today | After |
|---|---|---|
| Bot's poll (read bars, model, order), replay median | 0.49 s | 0.22 s with both patches (same trades, same model state every poll) |
| Order sent after the bar opens | ~2.65 s | ~2.4 s with the patches; ~0.85 s with fast entry too |
| ATLAS entry fills | 10 / 12 / 16 ticks past the open (backtest 1) | unknown until measured |

## Method (pre-registered: research/speed/PREREG.md)

research/speed/replay_harness.py: the real `engine.live.LiveBot`, paper adapter, frozen clock, `data_source` "ninjatrader"
with no Yahoo, `nt_folder` pointing at a temp NinjaTrader folder whose `le_feed/NQ_1m.csv` / `NQ_5m.csv` are written in
LE_BarFeed's format and grow bar by bar (up to 20,000 1m + 8,000 5m lines, trimmed like LE_BarFeed), `NQ_1m_open.csv` rewritten
each minute; history = the TradingView export cut 10 days before the replay (`engine.live.DATA_DIR` patched); its own
NinjaTrader archive; `engine.poll_timing` installed. Days 2026-11-16, 17, 18; polls every minute 01:30-12:00 ET and every 5
minutes otherwise, 2,304 polls a run. It reproduces the real Nov 16 06:16 ET Zlarior BUY (stop 27,735.25, the PC's own).
Speed-ups are monkeypatched in the harness only (research/speed/speedups.py). All five runs ran 3 at a time on this 4-core
cloud machine, so the absolute ms are inflated; the differences are like for like.

## Results

| Run | Poll median | p90 | Signal -> route | Ledger vs today | LIT model_state every poll |
|---|---:|---:|---:|---|---|
| today (+2 s) | 493.6 ms | 646.5 | 487 ms | - | - |
| patch 1 tail reader | 425.2 | 542.0 | 416 | same | (not recorded in that run) |
| patch 2 history cap | 300.9 | 446.4 | 293 | same + same log lines | 2,304 / 2,304 same |
| patches 1 + 2 | **219.3** | **334.6** | 211 | same + same log lines | 2,304 / 2,304 same |
| fast entry ON (+0.2 s) | 505.9 | 656.3 | 497 | same, routed at +0 s (vs +2 s) | (not recorded in that run) |

Stages (today, median per poll): 1m bars 240 ms = bar file parse 82 + history & archive merge 44 + feed merge 46 + clean 23;
5m bars 155 ms = history & archive merge 54 + feed merge 52 + clean 28; LIT model 62 ms; Bot Brain 4; bar object 2; save 1.
The history part is the TradingView export: 360k 5m rows (5 years) and 320k 1m rows (2026) re-merged, de-duplicated, sorted and
cleaned every poll, while LIT (`lit_live.window_start`) and ATLAS (`second._window`) read only from the previous month's first
day minus 8 days.

Patch 1 (tests/test_speed_tail_load.py, 11/11, also on a copy with the patch applied; NT selftest 79/79 on it): a file that only
grew (same file id, same first 256 bytes, same 64 bytes before the old end, < 16 KB more, a full read in the last 15 min) is
parsed from the last complete line; a 21,000-line file 70 ms -> 5 ms a read. Patch 2: `_read_hist` cuts NQ 1m / 5m to the last
150 days of the bot's clock before the archive merge (ES, 1h, other symbols untouched; cfg `hist_keep_days: 0` = all).

## Fast entry

Same decisions ON vs OFF (ledger identical; the poll is a pure function of the bars, and LE_BarFeed only writes closed bars).
Wait loop 0.025 ms a check. $ (research/speed/fast_entry_value.py): order ~2.65 s -> ~0.85 s after the open. If the price
move builds like sqrt(time): ATLAS -5.1 ticks, LIT -1.3 a trade = ~$103 a month (ATLAS 15.4 trades x 2 micros, LIT 12.8 x 3);
linear: ~$161; all on the first tick: $0; overshoot-and-revert minutes can make it worse. Low end $0 -> no card (pre-registered).
It matters beyond $: ATLAS at 10 ticks a side has 2021-25 PF 0.80 vs 1.06 at 1 tick (atlas-fills-2026-11-20).

## Fills

ATLAS 3 MARKET entries at the 5m open: 10 / 12 / 16 ticks past the open (2 micros: $9 / $11 / $15 more than its backtest);
Zlarior 1 MARKET entry: 4 ticks ($1.50 on 1 micro). Exits (bracket STOPMARKET / LIMIT, CLOSEPOSITION): no fill prices recorded.
Split: ~1 tick is the spread (already in the backtests); the rest is the market moving before the order arrives, ~75% of that
time being the 2 s wait. The 3-5 s "routed after the open" of night-nqlive is the ledger stamp, taken after the fill and the
bracket are confirmed (engine/live._route stamps after `adapter.send` returns; ninjatrader.send waits for the fill and the
bracket). Exact send / fill times are in the PC's legs (`sent_at`, `fill_mtime`): tools/research/fill_timing.py reads them
from data/pc_days once pulled. 4 fills: a small sample.

## Tests

tests/test_speed_tail_load.py 11/11 (branch and patched copy). Branch: no live file changed; smoke 7/8 (test_zenith_mode needs
the Python playwright module, missing in this container: not this branch); run_area nq, test_lit_live --quick, NT selftest:
see research/handoff/2026-11-20/speed/REPORT.md.
