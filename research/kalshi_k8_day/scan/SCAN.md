# Is there a second K8-style clock edge on other Kalshi short markets? (run 2026-11-20, exactly PREREG_scan.md)

**Verdict: none.** No (series, time of day, side) cleared the pre-registered bar, so stage 2 (pricing the trades) did not run
and there are no dollar numbers to report. Nothing goes to any bot.

| what | result |
|---|---|
| Series Kalshi lists as 15-minute or hourly | 120 |
| In the test (one market per window, YES = "at least the start", markets on most weekdays) | 12: BTC, ETH, SOL, XRP, DOGE, BNB, HYPE, NEAR, ZEC (crypto), WTI oil, natural gas, copper |
| Cells tried (series x ET open time x UP/DOWN, >= 40 weekday windows Aug 3 - Oct 21) | 1,982 |
| Bar a cell had to clear | win rate >= 62% and p < 0.05 / 1,982 = 0.000025 |
| Cells that won >= 62% | 105. Pure coin flips would give about 87, so this is noise |
| Best cell | BNB UP at 22:30 ET: won 41 of 58 (71%), p = 0.0011, 44 times too weak for the bar |
| Next best | BTC DOWN 09:15, BTC UP 16:00, XRP DOWN 06:00: each 40 of 58 (69%), p = 0.0027 |
| Candidates, so stage 2 ($2.50 bets at +20 s, 70c cap, fees in) | 0, so no dollar figures |
| Kalshi requests made | 338 public GETs in total (discovery and stage 1), 1 a second, none refused, no errors |

## Why the other 108 were left out (full list with the reason for each is in scan.json "series_found")
- **Ladders and range buckets (42):** every hourly series (gold, silver, platinum, palladium, WTI hourly, S&P/Nasdaq/Dow, FX,
  Treasury yields, crypto "D"/range, the weather series) has 5 to 200 strikes per hour, so YES is not "above the start". The
  prereg leaves these out.
- **Too new, thin data (15):** Kalshi only started these series after early September, so they have markets on fewer than
  half of the 58 find weekdays: Brent (from Oct 21), S&P 500 15m (from November), EUR/USD, GBP/USD and USD/JPY 15m (21 days),
  AUD/USD and USD/CAD 15m (11), platinum and palladium 15m (25), the 2/5/10/30-year yield 15m series (3), and KPOW 15m and hourly (0).
- **No settled markets at all (live or historical) (47):** Nasdaq 15m, Dow 15m, ADA, BCH, TON, coffee and others.
- **Not a price market (1):** KXTPSMYANMAR.
- **K8's own (2):** KXGOLD15M, KXSILVER15M. **Test series (1):** KXGBPUSD15MTEST.

## Read this before trusting "none"
- The bar is strict. I ran the same results-only count on K8's own four legs as a power check (they are not in the test).
  Only silver UP at 16:45 (45 of 58, 78%) would have cleared it. Gold DOWN at 05:15 (72%, p = 0.0004) would not have.
  So a K8-sized edge on a new series could be missed here. The data does not show one, and with 1,982 cells and about
  58 days each the scan could not have proven a weaker one.
- Natural gas and copper only have data from Aug 27 (40 find days), so their cells barely reach the 40-window minimum.
- The scan used weekdays only (ET), like K8. Crypto weekend windows were not tested.

## Files
- `scan.py`: rerunnable (`python research/kalshi_k8_day/scan/scan.py`). It caches every Kalshi answer at
  `/home/user/kalshi_cache/scan` (not committed), so a rerun makes 0 new requests for data it already has.
- `kget.py`: the public GET client. It sends GET only, with no key, no auth header and no orders, waits at least 1.05 s
  between requests, and logs each request.
- `scan.json`: every series found with its keep/exclude reason, the rules, all 1,982 cells as [series, time, side, n, won],
  the top 25 by z-score, the K8 power check and the request count.
