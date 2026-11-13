# Kalshi edge, team K3 (arbitrage, economic releases, late resolution): NO EDGE FOUND

2026-11-13. Research only, paper only. Kalshi's public market-data API (no key, GET only, about 3-4 requests a second),
plus free public data (Iowa Environmental Mesonet METAR archive, aviationweather.gov, FRED, Cleveland Fed nowcast file).
No order was placed, no account or key was used, the live bot and `engine/` were not touched.
Code and data: `research/kalshi_edge_K3/` (raw cache gitignored). Not redone: teams A, B, C, the 2026-11-04 study, and
team K1's angles (index fair value, weather vs NWS forecast, market making).

## The answer

| Edge | n | Edge per $1, train (95% range) | Edge per $1, test (95% range) | Capacity $/day | Verdict |
|---|---|---|---|---|---|
| 1a. Range-bucket arbitrage, settled history (buy every bucket's YES or NO when the set costs < $1 after fees) | 89 hits in 39,813 event-hours (9,315 events) | +0.15% (+0.12 to +0.20) | +0.24% (+0.15 to +0.41) | about $0.06 | No edge: real but microscopic, half the hits had a leg with zero volume that hour |
| 1b. Threshold-ladder arbitrage ("above X" vs "above Y") | 1 hit in 82,616 pair-hours | - | - | 0 | No edge |
| 1c. Live scan of all 21,700 open events (2 full passes) | 9 true arbs | about +0.2% over 2 years | - | $288 total, locked to 2028 | No edge (2028 nominee markets, 0.01-0.09% a year) |
| 1d. CPI m/m vs CPI y/y cross-market (same month, seasonal mapping with its own error bound) | 4 hits in 9,983 pair-hours, 43 months | +0.8c per pair, 13 contracts traded | - | under $0.01 | No edge |
| 2a. Economic releases, market calibration and taker P&L (CPI, core, y/y, payrolls, U3, claims) | 4,702 trade units, 41 cells | best cell +36% (-18 to +83), t 1.4 | same cell +8% (-37 to +46) | - | No edge: no cell beats t 2, let alone the multiple-testing bar |
| 2b. Cleveland Fed nowcast vs the CPI ladders (1 day out) | 144 train / 126 test | +3.7% (-12 to +21) at the train-picked threshold | +5.1% (-18 to +29) | - | No edge: the nowcast forecasts worse than the market (Brier 0.17 vs 0.09 train, 0.12 vs 0.10 test) |
| 2c. Jobless claims vs last week's print + 2015-24 week-on-week history | 63 weekly events, 355 train / 271 test units | best rule -8.6% (-30 to +15) | +7.9% (-9 to +25) | - | No edge: every train threshold loses; the model ties the market in test (Brier 0.105 vs 0.105) |
| 3a. Late resolution, temperature buckets: buy the known side after the METAR that kills a bucket, taker | 2,744 crossings, 57 days | before publication: +5 to +10% (looks great) | after publication (3+ min): known side under 99c in 0.1-0.4% of cases, losers among them | about $0 | No edge for a public-data bot: the price moves before the METAR is public |
| 3b. Same, resting maker order at 98c on the known side, filled by late wrong-side buyers (upper bound) | MAKER_N | - | MAKER_TE | MAKER_CAP | MAKER_VERDICT |

All numbers are after Kalshi's fee (0.07 x p x (1-p) per contract, rounded up per 100-lot order; maker fee 0.0175 x p x (1-p))
and after the spread (taker buys at the ask). 95% ranges are cluster bootstraps (by event, or by day for weather).

## 1. Internal arbitrage and consistency

**What was checked.** (a) Range events whose buckets tile the number line (weather highs and lows, S&P/Nasdaq daily
ranges, gas, FX): if the YES asks of all buckets add to less than $1 after fees, buying all pays $1 for sure; the same for
buying every NO. (b) Threshold ladders: "above 70" must cost at least "above 72". (c) A live scan of every open event on
Kalshi, twice (206,000 markets each pass), including mutually exclusive events. (d) CPI m/m against CPI y/y for the same
month: once last year's index is known, y/y is a function of m/m (plus a seasonal-factor error that I measured on 2015-2026,
126 months, worst 0.26 pt, and widened by 0.02).

**Result.** The book is consistent. History: 89 profitable hours out of 39,813, typically 0.45c per $1 set, about 6 cents
a day in total if every leg had filled at 100 lots (and in half of them one leg did not trade at all that hour). The live
scan's large "profits" are sets of nominee markets that do NOT cover every outcome (a candidate not listed can win), so they
are bets, not arbitrage; the 9 true ones are 2028 nominee markets paying 0.1-0.2% for two years of locked capital. CPI m/m
vs y/y: 4 one-hour, 1-cent gaps in 43 months, 13 contracts traded.

**Frequency, size, persistence.** Under one hit a day, sizes in single-digit dollars, and persistence cannot be shown from
hourly closes (the same event rarely shows a hit two hours in a row: 89 hits on 86 events). No edge.

## 2. Economic releases (CPI, core CPI, CPI y/y, payrolls, unemployment, jobless claims)

**Data.** Every settled market 2021-2026 on these series (old names and new KX names): 3,408 markets, hourly yes bid/ask
in the last 7 days before close. Train = events before 2025-01-01, test = 2025 onward. Fed rate markets: FED_NOTE

**Calibration** (mid price 6-24 hours before close vs how often YES won): the market is well calibrated on CPI, core CPI
and CPI y/y (e.g. CPI m/m priced 95% won 97%, priced 80% won 78%). The one visible pattern is payrolls: strikes priced
19% won 41%, priced 50% won 67% (payrolls beat the market in 2021-23). On the cell level it is +36% per $1 in train but
+8% in test with a range of -37% to +46%: a period effect, not a rule.

**Outside models.** The Cleveland Fed inflation nowcast (public, the day before) with its error spread fitted on 2013-2020
forecasts the CPI strikes worse than the Kalshi price itself (Brier 0.170 vs 0.087 train, 0.125 vs 0.101 test). Trading
its disagreements: +5% per $1 in test with a range of -18% to +29%. Jobless claims (weekly, June 2025 on): last week's print plus the 2015-2024 week-on-week spread (FRED) loses on every
train threshold (-8.6% to -44% per $1) and only ties the market price in the test half.

**Taker cost.** Buying mid-priced strikes (16-84c) costs a significant 5.7-6.4% per $1 in both halves (t -9 and -17): that
is the spread plus the fee, and nothing in the forecasts earns it back.

## 3. Late resolution (the outcome is public before the market closes)

**Idea.** A daily-high bucket is dead the minute the temperature passes it. If the market still sells the known side
under 99c after that, a bot that reads the public METAR can buy it.

**Data.** 2,744 bucket "deaths" (high and low markets, 20 stations, 2026-09-14 to 11-12, with 1-minute Kalshi quotes) from
the IEM METAR archive (routine and special reports), checked at margin 0 and 1 degree F. At margin 1 the known side never
lost (2,046 of 2,046); at margin 0, 4 lost (rounding and the 1-minute ASOS data the official report uses).

**Result.** The known side is still buyable for 2 minutes after the observation time (+7% per $1 on highs, +10% on lows,
in train and test alike), and then it is gone: from minute 3 it is buyable in 0.1-0.4% of cases, and those few were the
losers. The catch is publication: on aviationweather.gov a METAR is received a median **215 seconds (p10 187 s, p90
268 s)** after its observation time; only 5.5% are out within 3 minutes. So the price moves **before** the report is
public: someone has faster data (direct ASOS or NWS feeds). A bot on the free public feed always arrives after the move.
The 2-minute "edge" is look-ahead and cannot be traded.

MAKER_TEXT

## Paper forward logger (the only open question, measured going forward)

`research/kalshi_edge_K3/forward_logger.py` (read only: public METARs and public Kalshi listings, never an order). Every
minute it reads the latest METARs with their real receipt time, finds buckets that just became known (margin 1 F), logs
the known side's ask and size as a paper taker buy (<= 98c, up to 100 contracts) and a paper maker order at 98c, then
settles them from Kalshi's result and public trade tape. Only buckets it saw become known within 10 minutes count
(start-up backlog is logged, not scored). Self-test: `python research/kalshi_edge_K3/forward_logger.py --selftest`.

**VM rule (exact):** cron `* * * * * cd ~/nq-liquidity-engine && python3 research/kalshi_edge_K3/forward_logger.py --once >> research/kalshi_edge_K3/forward/log.txt 2>&1`
(about 30 public requests a minute, gapped 0.3 s). Decision rule, fixed now: it counts as an edge only after >= 30 settled
days and >= 100 taker or maker fills, with net $ after fees > 0 and a day-bootstrap 95% range above 0. Otherwise no edge.
Expected answer from history: no edge.

## Honest limits

- Hourly candle closes (arbitrage, econ) show one quote per hour, not the book: brief arbs inside the hour are missed, and a
  quote's size is unknown (the hour's traded volume is used as a proxy).
- Weather minute study: 57 days only (1-minute quotes exist from 2026-09-14), and the METAR receipt delay is measured on
  today's 30 hours, not on the archive (the archive has no receipt times).
- Maker fills are an upper bound: queue position and other resting orders are not modelled.
- Economic releases: about 45-65 events per series; a true edge of a few % per $1 would not be detectable.
- No consensus survey (Bloomberg/Reuters) is free, so "vs consensus" uses the Cleveland Fed nowcast and the claims history.

## Reproduce

```
python research/kalshi_edge_K3/arb_hist.py        # 1a/1b (reads team C's hourly snapshots)
python research/kalshi_edge_K3/arb_summary.py     # edge per $1, capacity
python research/kalshi_edge_K3/scan_live.py       # 1c live scan; scan_report.py summarises
python research/kalshi_edge_K3/cpi_cross.py       # 1d
python research/kalshi_edge_K3/harvest_econ.py    # 2 data;  econ_study.py -> data/econ_results.json
python research/kalshi_edge_K3/weather_minute.py  # 3a;  weather_trades.py -> data/weather_trades.json (3b)
```
