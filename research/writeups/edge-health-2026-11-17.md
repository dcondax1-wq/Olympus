# Edge health, 2026-11-17: is the market still the 2026 kind?

| What | Result |
|---|---|
| Light now | **GREEN**: LIT's last 40 sessions (to Nov 6) made 2.3R a week, PF 3.84, about $3,440/month (2026 Jan-Jun median PF 3.91; 2021-25 median PF 1.1, about $180/month) |
| But fading | The 3 newest weeks (Oct 19 - Nov 6): 3-4 trades, about -1R to -1.8R, about -$140 at the backtest size. Stops were wide (70-78 pts), so 1 micro |
| Data | TradingView files end **Oct 16**; the PC's NinjaTrader bars (heartbeat) end **Nov 6**; VIX (CBOE) to Nov 16. **6 sessions missing** (Nov 9-16) |
| Market "weather" warning | **Nothing works.** One feature (the share of the day's range made overnight) splits 2021-25 from 2026, but it just rises a little every year. Before 2026 its "2026-like" days were followed by a *worse* LIT, not a better one. Not used |
| False alarms | On Jul-Oct (the check months, the light never saw them) the light was RED 8.6% of days (one 8-session run in August). LIT then made +1.1R a trade over the next 40 sessions, so that RED was a false alarm |
| What it can and cannot do | It tells you what the last ~8 weeks looked like, not what comes next. It is slow: with no trades at all from Nov 9 it would go AMBER about Nov 30 and RED about Dec 10 |
| Before buying more evals | GREEN today, but on data that is 11 days old. Export the missing bars first (below), then rerun |

1. Export the missing bars: in TradingView open `CME_MINI:NQ1!` at 1 minute (all hours, B-ADJ off), Export chart data from
   Oct 16 to today, save it in `data/tv_exports/`, then run
   `python data/import_futures.py csv NQ data/tv_exports/<file>.csv` (do the same for 5 minutes and `CME_MINI:ES1!` 5 minutes).
   Or simply start the PC bot: its heartbeat pushes the NinjaTrader bars and this check reads them.
2. Rerun: `python tools/edge_health.py --fetch` (then `python tools/biz_publish.py --fixture` to refresh the Business card).
3. Buy rule of thumb: GREEN = fine to buy; AMBER = wait for the next payout; RED = do not buy, the edge looks like 2021-25 (about $0).

A warning, not a switch. The bots trade exactly the same whatever the light says. A drift switch (cut size after losses)
was tested and rejected (0/51, `drift-switch-2026-11-17.md`); this does not trade.

## How it was built (`tools/edge_health.py` -> `research/lab/edge_health.json`)

### 1. Data freshness
- `data/NQ_1m.csv`, `NQ_5m.csv`, `ES_5m.csv` (TradingView NQ1!/ES1!): last bar 2026-10-16 15:55-15:59 ET.
- Heartbeat branch (PC NinjaTrader bars, last push 2026-11-07 01:05 ET): 5m from 2026-10-04 to 2026-11-06 16:55 ET, 1m only
  from 2026-11-04 01:06 ET. On the 2,760 shared 5m bars the price basis is identical (median close difference 0.00, shift 0).
- VIX: `data/VIX_1d.csv` ends 2026-10-16; CBOE's own daily file (free, the bots' VIX source) adds Oct 19 - Nov 16.
- Missing to today: Nov 9-13 and Nov 16 (6 sessions), plus today. The PC has not reported since 2026-11-07.

### 2. LIT edge on the freshest bars
- The exact live settings (`live_model.json` "lit", `engine/lit.run_x`), on the TradingView history with the PC's bars
  appended. Up to Oct 16 it reproduces run `lit_live` trade for trade (631/631, checked every run; it stops otherwise).
- Oct 19 - Nov 6 (15 sessions) run on 5-minute bars (no 1m bars in the cloud before Nov 4), so a trade can differ: this
  replay took Oct 26 BE, Oct 27 STOP -1.01R, Oct 29 BE (-1.0R). The PC's own 1m backtest (heartbeat reviews) took Oct 26 BE,
  Oct 27 STOP -1.00R, Oct 28 STOP -1.01R, Nov 3 TIME +0.21R (-1.8R). The bot itself was off those days.
- $ = run lit_live's LIT size rule (up to $800 risk, smaller on wide stops), not today's eval size (room_f 0.4).

| LIT, window ending Nov 6 | trades/wk | win % | PF | $/month | median PF H1 / H2 / 2021-25 | median $/mo H1 / H2 / 2021-25 |
|---|---|---|---|---|---|---|
| last 20 sessions | 1.25 | 80 | 26.6 (5 trades) | 3,789 | 4.23 / 2.05 / 0.96 | 6,082 / 1,708 / -44 |
| last 40 sessions | 2.5 | 55 | 3.84 | 3,440 | 3.91 / 2.85 / 1.10 | 4,808 / 1,864 / 177 |
| last 60 sessions | 2.42 | 59 | 4.34 | 3,545 | 4.07 / 2.89 / 1.08 | 4,620 / 2,386 / 173 |

At the last export day (Oct 16) the 40-session window was PF 4.8, $5,469/month, 3.1 trades/week: the newest weeks pulled it down.
The last-20 window is thin (5 trades, one +5.5R winner on Oct 13).

ATLAS (stored run `atlas_deep_zombie`, not re-run on fresh bars, ends Oct 16): last 40 sessions 3.0 trades/week, win 58%, PF
1.41, $411/month vs medians 2.86 / 2.80 / 1.07 (H1 / H2 / 2021-25) and $3,070 / $2,248 / $163 a month: ATLAS was already
weak into mid-October. Its PC paper members Oct 19 - Nov 6 (heartbeat): EMA 3 stops, MACD -1R, -1R, +8R, S/R -1R, +2R.

### 3. Market features (the "weather" test): none used
Five day features, each a 40-session mean: VIX (prior close), RTH range % of price, overnight share of the day's range,
RTH trend efficiency (|close-open| / path), and how often a prior-day high/low sweep closed back inside. Each cut was picked
on 2021-25 (no edge) vs 2026 H1 (edge) only; a feature is kept at balanced accuracy >= 0.75.

| Feature | pick-set balanced accuracy | 2022 H1 (LIT's good year) | 2025 H1 | 2026 H1 | 2026 H2 |
|---|---|---|---|---|---|
| VIX | 0.62 | 26.3 | 21.2 | 19.4 | 16.5 |
| RTH range % | 0.67 | 2.09 | 1.74 | 1.50 | 1.34 |
| overnight share | **0.94 (kept)** | 0.55 | 0.62 | 0.65 | 0.70 |
| trend efficiency | 0.60 | 0.153 | 0.126 | 0.132 | 0.122 |
| sweep reclaim | 0.59 | 0.37 | 0.41 | 0.39 | 0.38 |

The overnight share rises almost every half-year (0.50 in late 2021 -> 0.70 now). It calls 2022 (LIT's one good year
before 2026, +$13.9k) "2021-25-like". Inside 2021-25 its 2026-like days were followed by -0.04R a trade over the next 40
sessions vs +0.07R on its other days. It marks the calendar, not the edge, so it is NOT used. Feature vs next-40-session LIT
correlations flip sign from year to year (VIX: +0.10 in 2022, -0.46 in 2023, +0.32 in 2024, -0.36 in 2025).

### 4. The light: LIT's own last 40 sessions
- R a week over the last 40 sessions (size-free). Cuts from the 2021-25 windows only: GREEN above 1.16R/week (2021-25's best
  10%; 2026 H1's worst 10% is 1.18), RED at or below 0.0R/week (2021-25's median: nothing made in 8 weeks), AMBER between.
- Pick (2026 H1): GREEN 89.8%, AMBER 10.2%, RED 0%. Reference 2021-25: GREEN 10.4%, AMBER 39.5%, RED 50.1% (23 RED runs,
  the longest 79 sessions).
- **Check (2026 H2, not used to pick): GREEN 54.8%, AMBER 36.6%, RED 8.6% = the false-alarm rate** (one run, Aug 13-24,
  8 sessions; the next 40 sessions made +1.15R a trade).
- It does not forecast: in 2021-25, LIT's next 40 sessions after GREEN days averaged -0.05R a trade (-$156/month) vs +0.04R
  after RED days. The same as the drift switch: past weeks do not predict the next ones. Read it as "has the 2026 kind of
  market continued", a reason to pause new eval purchases, never a reason to change the bots.

### Honest limits
- The light needs fresh bars; today it is 6 sessions behind. On the PC (data/nt_bars/) it is current whenever the bot runs.
- 2021-25 runs on 5m bars only (no 1m history), 2026 mostly on 1m. Part of "2021-25 had no edge" may be the coarser bars,
  which no market feature can see.
- LIT was tuned on 2026 H1, so H1 looks best by construction; H2 is the honest check.

Files: `tools/edge_health.py`, `research/lab/edge_health.json`, Business card data `edge` in
`tools/web_public/business/fixture.json` (from `tools/biz_publish.py`).
