# LIT drought Oct 15 - Nov 26 2026: why so few trades (2026-11-27, research only)

**Answer:** the market, not a broken rule. NQ's 5m ATR roughly doubled (median 36.6 pts in the drought, 47.4 Nov 17-26, vs
~25 in 2026 H1/Jul-Oct and 14.8 in 2021-25). LIT's stop goes 1 tick beyond the sweep extreme, so in a market this wide most
setups need a stop over 80 pts and are skipped. Widening the stop cap was tested 4 ways (pre-registered): **all rejected**,
and every one would have **lost more** in the drought. Nothing live changed. Expected NO, got NO.

## 1) Funnel (funnel.py -> funnel.json; live_model.json "lit", own session list from data/NQ_5m.csv to 2026-11-26)
Setups found are normal everywhere (~31-35 a week after sweep + CISD shift); they die at the stop rule.

| per week | 2021-25 | 2026 H1 | Jul 1-Oct 14 | Oct 15-Nov 26 | Nov 17-26 |
|---|---|---|---|---|---|
| sweeps of a level | 129.6 | 119.9 | 106.8 | 116.6 | 113.1 |
| sweep + CISD shift (candidates) | 33.9 | 32.6 | 31.5 | 34.5 | 31.2 |
| after depth >= 0.5 ATR | 28.6 | 27.5 | 26.3 | 28.1 | 24.4 |
| after inducement | 18.9 | 18.8 | 17.3 | 18.9 | 16.9 |
| after displacement >= 0.8 ATR | 13.4 | 12.9 | 10.9 | 12.4 | 11.3 |
| after stop 8-80 pts | 11.1 | 8.8 | 7.3 | **5.8** | **1.9** |
| after VIX-band target >= 1.5R | 10.9 | 8.7 | 7.1 | 5.0 | 1.9 |
| filled (1m CISD within the wait) | 3.1 | 4.7 | 3.8 | 1.6 | 0.0 |
| trades (1 a day) | 2.40 | 3.11 | 2.63 | 1.13 | 0 |
| **share killed by the stop rule** | 13.7% | 24.0% | 22.5% | **40.2%** | **56.0%** |
| share failing displacement | 30.2% | 31.3% | 35.7% | 36.0% | 34.0% |
| median 5m ATR (pts) | 14.8 | 25.9 | 24.8 | 36.6 | 47.4 |

- Displacement is NOT the choke: its fail rate is flat (30-36%) and the median displacement is unchanged.
- Hidden second gate: `lit.qty_for` gives 0 micros above ~89 pts (800 x 20 / stop / $2 per pt < 1), so the cap is ~89 pts
  even if max_stop were raised.
- **Chance check:** 30-session windows with <= 7 trades happened in 1.8% of 2021-25 windows (19 of 1,056; median 14).
  Rare, but seen before: **April 2025 (tariff crash) had two 10-session dry spells with the same signature** (stop rule
  killed 39.5%, ATR 38). The other past dry spells (Jul 2023, Nov 2025) were normal-ATR chance (stop kills 4-16%).

## 2) Variants (DESIGN.md committed first, 6cd42db9; variants.py -> variants.json)
1-micro floor for stops 80-150 pts in every variant; costs in; raw engine sizing ($800 risk to 20 pts). Pass = better net $,
PF not lower by > 0.05, DD not worse by > 25% in H1 AND Jul-Oct AND 2021-25, 2-4 trades/week, Holm p < 0.05.

| variant | H1 tr/wk / PF / net | Jul-Oct tr/wk / PF / net | 2021-25 net | drought net | eval pass (H1 / Jul-Oct) | Holm p | verdict |
|---|---|---|---|---|---|---|---|
| live (cap 80) | 3.11 / 5.20 / $34,261 | 2.63 / 2.91 / $9,919 | $5,180 | -$858 | 83.5% / 100% | - | - |
| V1 cap 120 pts | 3.62 / 4.07 / $29,955 | 3.22 / 2.37 / $8,640 | $8,153 | -$1,637 | 66.7% / 68.0% | 1.0 | REJECTED |
| V2 max(80, 3 ATR) | 3.46 / 4.71 / $34,028 | 2.96 / 2.73 / $9,589 | $6,383 | -$1,938 | 83.5% / 100% | 1.0 | REJECTED |
| V3 VIX >= 22: 120 | 3.31 / 4.99 / $34,452 | 2.76 / 2.91 / $9,920 | $7,703 | -$916 | 83.5% / 100% | 1.0 | REJECTED (H1 PF -0.21; +$191 / +$1 = noise) |
| V4 3.2 ATR [40,150] | 3.15 / 4.43 / $31,126 | 2.89 / 2.69 / $9,505 | $8,020 | -$1,938 | 87.4% / 100% | 1.0 | REJECTED |

$/month and max DD per span are in variants.json (live H1 $5,665/mo, DD -$2,196; Jul-Oct $2,741/mo, DD -$1,396).
Wide-stop trades help a little in 2021-25 only (+$1-3k over 4 years) and cost money in 2026 and the drought.

## What it means for the owner
- LIT is doing what it was built to do: skipping wide, high-VIX setups. Those setups lost money when allowed in.
- Expect slow weeks while NQ's ATR stays ~2x normal (like April 2025). Trades come back as volatility calms.
- No change proposed. Added to docs/TESTED_AND_REJECTED.md.
