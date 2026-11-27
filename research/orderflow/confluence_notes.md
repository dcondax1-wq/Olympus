## Plain reading (written after the run; the numbers above are the pre-registered ones)

- **Nothing is proven, and nothing can be with these days.** 17 LIT + 11 ATLAS trades in ~8 weeks, all inside 2026 H2. The
  strategy protocol needs a 2026 Jan-Jun pick and a Jul-Oct check (LIT) or 2021-25 (others): tick data does not exist there.
  Every CI above straddles $0.
- **"Absorbed at the sweep" is the normal case, not a signal**: 14 of 17 LIT sweeps and 9 of 11 ATLAS sweeps read absorbed.
  The one LIT trade that did NOT read absorbed (2026-10-13) was the biggest winner (+$3,169). That is why the skip filter
  (OF1) cut good trades, and why C-b (1.5x when absorbed) is mostly just "1.5x almost always" = more leverage on a winning
  sample, not an edge. C-b also changes nothing on 1-micro trades (1 x 1.5 rounds to 1).
- **C-a (enter on the first absorbed bar)** reads CANDIDATE by the frozen words (both halves up), but its whole gain is one
  trade: 2026-10-01 gets a 52-tick-better entry, so the stop is closer and the size bigger (+$5,260); without it the idea
  LOSES. It also turns the 10-13 winner (+$3,169) into +$13 and misses 5 trades (2 of them winners, +$1,350). Treat as
  NOT a candidate; log it forward only because it costs nothing to log.
- **C-c (exit on a hard flip before BE)** never fired on LIT (0 of 17) and once on ATLAS (+$118). The 0.25 x volume flip is
  rare on 5m NQ bars; LIT's own 15-minute check already does this job. Nothing to wire beyond logging.
- **C-d (ATLAS waits for a non-adverse delta bar)** changed 2 of 11 trades (+$164): one entry 14 ticks better (10-27), one
  37 ticks WORSE (11-18, smaller loss only because the wider stop meant fewer micros). It does NOT fix ATLAS's 14-tick real
  slippage on this sample. Log forward.

## LEAD_WIRES (forward logging on the PC - cheap fields, research only, never changes an order)

Everything below can be computed after the close from what the PC already saves (the nightly tick summary
`engine/ofsum` bars5m + fp5m, and the bot ledgers). The wire is ONE nightly row per real LIT / ATLAS trade, appended to
`data/of_confluence_log.jsonl` (gitignored) by the same nightly step that runs `engine/oflive.journal_kick`, using
`research/orderflow/of_confluence.py`'s definitions (frozen; import, do not copy). Fields:

| field | for | how |
|---|---|---|
| `day`, `bot` (LIT / ATLAS), `dir`, `entry_t`, `fill_px` (real), `signal_px` (the backtest's price: LIT limit / next open, ATLAS next 5m open + 1 tick), `stop_px`, `target_px`, `qty`, `exit_t`, `exit_px`, `exit_kind`, `pnl_usd` (real, after costs) | all | from the ledgers the bot already writes |
| `slip_ticks` = (fill_px - signal_px) x dir / 0.25 | C-d, ATLAS slippage | ledger |
| `sweep_read`, `sweep_vz`, `sweep_dz` | C-b | `oflive.said_at` (already computed nightly) - store it ON the trade row |
| `abs1_t`, `abs1_px` = close time of the first absorbed closed 5m bar within 30 min after the fill, and the next 1m open + 1 tick | C-a | summary bars + fp |
| `flip1_t`, `flip1_share`, `flip1_vol_x_med` = the first bar before BE with delta against the trade (and its \|delta\|/volume, volume / prior RTH median) - logged even below the 0.25 bar, so the threshold is not tuned later on the same days | C-c | summary bars |
| `sig_delta`, `sig_vol` (ATLAS signal bar), `nonadv1_t`, `nonadv1_px` (first non-adverse closed bar within 30 min, next open + 1 tick) | C-d | summary bars |
| `bars` = per closed 5m bar from fill to exit: [t, delta, volume] (<= 80 small numbers) | replay of all four | summary bars |

**When each idea can be judged**: LIT ~2-3 trades a week + ATLAS ~1.5 -> by ~end of Feb 2027 ~30 LIT / ~20 ATLAS forward
trades. Score then with the frozen rules above on forward days only (from 2026-11-28): an idea is worth an owner card only if
its $ gain is > 0 in both halves of the forward days AND without its single best trade, with the C-b / C-a size effect
shown separately. Until then: no live change; the dashboard can say "order flow confluence: logging, n = x of 30".
