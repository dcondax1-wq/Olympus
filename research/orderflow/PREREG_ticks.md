# Pre-registration: 3 tick order-flow designs (written 2026-11-23, branch day-ofprogram, before any tick data exists)

Code: `research/orderflow/of_study.py` → `prereg()`. It runs by itself when `engine.tickrec.days_available()` holds 60 or more
days, and it writes to `results.json` under "PRE-REGISTERED (PREREG_ticks.md)". The constants are frozen at the top of the
block: `OF_ZONE_TICKS=8`, `OF_ABS_SHARE=0.20`, `OF_BLOCK_PCT=99.5`, `OF_BLOCK_DAYS=5`.

**No changes after the first look.** A failed design is logged in docs/TESTED_AND_REJECTED.md, not re-tuned. Any new
variant needs a new dated pre-registration and fresh days that the first run never saw. In practice that means days the
forward recorder captures after that first run.

Common to all three designs:
- **LIT trades:** `tools/lit_losses.run()`, the live replay with costs in.
- **Ticks:** `data/ticks` NQ, with side from the quote rule, then the tick rule.
- **Spans:** 2026 H1 and 2026 H2, limited to the days the ticks cover. There is no 2021-25 test, because there are no ticks
  for it.
- **A pass is only a candidate.** It still needs (1) 3 months of forward-recorded ticks that agree, and (2) the usual LIT
  change process: H1 pick, H2 check, live_model files, eval pass speed. **Nothing is armed by this test.**

## OF1: Sweep absorption (confirms or skips a LIT entry)
- **Claim:** this is the classic footprint read (Axia Futures, Trader Dale *Order Flow*, Dalton's "responsive" activity). A
  real stop-run reversal shows aggressive orders pushing into the extreme and getting absorbed. If the sweep has no
  aggression, nothing is trapped and the reversal has no fuel.
- **Rule:** take the sweep-extreme 5m bar of the LIT trade, and the trades within 8 ticks of that bar's tick extreme (low for
  a long, high for a short).
  - zone volume `vz` = the contracts traded in that zone.
  - zone delta `dz` = buys minus sells in that zone.
  - "absorbed" = `dz × dir < 0` and `|dz| ≥ 0.20 × vz`. For a long, that means sellers hit into the low and the low held.
  - Skip the LIT trades that are not absorbed.
- **Pass:** more net $ than all LIT trades in both halves, while keeping at least 50% of the trades.
- **Why it's here:** all three bar proxies (5m CLV, 5m BVC, 1m BVC) say the 2026 trades with flow *against* them were LIT's
  best (S4 "refuted" PF 5.2-7.4 in H1). That is the trapped-trader story, but proxies can't see it at the extreme, so the
  real test belongs to ticks.

## OF2: Block prints against the trade (skips a LIT entry)
- **Claim:** big single prints show institutional aggression. This comes from CME block / large-lot tape reading and
  well-known tape readers' material. Large aggressive prints against a fresh reversal mean real size disagrees with it.
- **Rule:** a "block" is a single trade at or above the 99.5th percentile of trade size over the previous 5 tick days.
  - Signed block volume = the sum of size × side over the blocks printed from the open of the sweep-extreme bar to the
    entry.
  - Skip the trade when that sum × dir < 0. Trades with no blocks are kept.
- **Pass:** same as OF1.
- **Caveat:** how NinjaTrader's feed bundles fills decides what one "trade" is. If `with_bid_ask%` or the size spread looks
  odd, report that and don't trust the result.

## OF3: LVN rejection on a real tick volume profile (stand-alone, uncorrelated with LIT)
- **Claim:** low-volume nodes between two high-volume nodes mark price that the auction rejected before (Trader Dale
  *Volume Profile*; Steidlmayer and Dalton auction theory). The first test of one is rejected again.
- **Bar version (B1):** on 5m bars with spread volume it was the best bar result of this program. PF 1.26 / 1.10 / 4.56 in
  2021-25 / 2026 H1 / 2026 H2, placebo p 0.004, daily correlation with LIT about -0.06. It was **rejected** for H1 PF < 1.15
  and only 0.5-0.7 trades a week.
- **Rule (A, the one that is gated):**
  - The previous day's RTH profile comes from tick volume at each price, in 2-pt bins with a centred 3-bin mean.
  - An LVN is a local minimum at no more than 35% of the POC, with a bin of at least 60% of the POC on both sides.
  - Between 10:00 and 15:00 ET, a 5m bar touches an LVN coming from above (previous close > LVN). It must close above the
    LVN, in the top half of its range, **and its tick delta must be > 0**. Then go long at the next open.
  - The short is the mirror image.
  - Stop 1 tick beyond the bar, target 2R, flat at 15:55, first signal of the day only.
  - $500 risk, $1.40 a micro round trip, 0.25 pt slippage.
- **Variant B:** the same without the delta condition. It is reported but not gated.
- **Pass:** PF ≥ 1.15 and net > 0 in each covered half, at least 0.5 trades a week (it is an add-on trade source, not a
  main strategy), and a coin-flip-direction placebo p < 0.10.

> Note added after round 2 (of_lvn.py, same day): B1 does not survive a window split (AM / PM), other markets, finer or wider
> profiles. OF3 stays exactly as registered above (no change after a look), but its prior is now low.

## What this does NOT test (needs DOM / market-by-order data, which we don't record)
DOM pulls and spoofs, iceberg refills (CME MBO keeps the OrderID on a native iceberg refresh), and queue depth. LE_TickRec
records Last trades plus the best bid and ask only.
