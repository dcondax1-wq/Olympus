# PANTHEON: the gods of free market data

PANTHEON is the OLYMPUS section where each free data source is a Greek god. Each god reads one public, key-less source,
says what it means for NQ today, and votes risk-on / risk-off in the **Council of the Gods**. Every vote is checked against
NQ futures (the TradingView CME `NQ1!` daily export, 2021-11 -> 2026-10). Nothing passes the bar, so the page says
**context, not a signal**. Research and display only: PANTHEON never trades, sizes or filters a trade, and never touches
`live_model*.json`.

- Code: `tools/pantheon/` (`sources.py` fetchers and parsers, `stats.py`, `gods.py`, `council.py`, `build.py`).
- Outputs: `research/pantheon/pantheon.json` (the page data) and `research/pantheon/states.json` (for Data City).
- Page: `tools/web_public/pantheon/` (3D Mount Olympus hall; `fixture.json` is the demo copy). Jarvis card: `jarvis.json`,
  opens `#council`.
- Refresh: the CRONOS nightly task `pantheon` (`tools/cronos/`, `.github/workflows/cronos.yml`). It takes about 1 billed
  minute a night and also runs in Actions saver mode.
- Test: `python -X utf8 -m tests.test_pantheon` (`fast` skips the browser). It reads only the recorded fixtures in
  `tests/fixtures/pantheon/`, never the network.

## The gods

| God | Domain | Why this god | Source (free, no key) | Votes |
|---|---|---|---|---|
| POSEIDON | Liquidity | God of the sea: the tide of money that lifts every boat | FRED `WALCL` (Fed balance sheet) - `WTREGEN` (TGA) - `RRPONTSYD` (reverse repo) = net liquidity | yes: 4-week change, up = risk-on |
| ZEUS | Rates and the curve | King of the gods: the price of money rules every other price | FRED `DGS10`, `DGS2`, `T10Y2Y`, `DFF`; US Treasury daily par curve (home.treasury.gov CSV) | yes: 10y 4-week change, down = risk-on |
| ARES | Volatility | God of war: fear, its term structure, dealer gamma | CBOE `VIX`, `VIX9D`, `VIX3M`, `VXN`, `SKEW` (cdn.cboe.com); SqueezeMetrics DIX + GEX | yes: VIX / VIX3M, low = risk-on |
| ATHENA | The macro calendar | Goddess of strategy: know the battle dates | `data/news/events.csv` (bls.gov, federalreserve.gov) + ForexFactory's free weekly JSON | no (no direction): adds a caution |
| DEMETER | Positioning (COT) | Goddess of the harvest: who planted which side | CFTC Traders in Financial Futures, E-mini Nasdaq-100 (publicreporting.cftc.gov) | yes: asset-manager net long % OI, 4-report change |
| HELIOS | The dollar | The sun every market orbits | FRED `DTWEXBGS` (broad dollar) | yes: 4-week % change, down = risk-on |
| NYX | Credit stress | Goddess of the night: spreads widen before the dark | FRED `BAMLH0A0HYM2` (HY OAS; FRED keeps only 3 years), `NFCI` | yes: 4-week change, tighter = risk-on |
| ARTEMIS | Crypto risk appetite | The huntress: Bitcoin runs with risk appetite | FRED `CBBTCUSD` (Coinbase). **Not futures data: display only** | never |

Names already used elsewhere were avoided: Hermes, Fates, Tyche, Prometheus, Daphne, Oracle, Odeon, Mind, Cronos, Atlas.

**Skipped:**
- CBOE put/call ratios: the free CSVs stopped in Oct 2019.
- The FRED release calendar: the FRED API needs a key.
- The CFTC's `newcot` text files: they return 403 to scripts. The public-reporting API serves the same report without a key.

## How each card is made

- **Reading:** the latest value. **Change:** over 4 weeks (ARES: 1 week).
- **Percentile:** where the latest value sits in the last 5 years (NYX: 3 years, the FRED limit).
- **Sparkline:** the last year.
- **Meaning:** one plain sentence. **Regime now:** the states that are true for the next session.
- **Vote:** the driver's z-score against the last 5 years (rolling, past only), halved and clipped to -1..+1.
- **Council:** the mean of the six council votes (at least 3 needed). The gauge is (score + 1) x 50. RISK-ON at >= +0.20,
  RISK-OFF at <= -0.20, MIXED in between.
- **No look-ahead:** a value counts for session D only once it was published before D. FRED daily and weekly data:
  1 business day after its date. CFTC: Tuesday's positions are published Friday (3 business days). CBOE and SqueezeMetrics:
  the same evening. Each value is compared with NQ's return of session D (close D / close D-1).
- **Honest check:** per period (2021-25 and 2026), the correlation and the hit rate against chance. Chance is the hit rate
  the votes would get if they were unrelated to NQ.
  - **Weak signal:** corr >= 0.05 and the hit rate beats chance by 2 points or more, in both periods.
  - **Inverse:** the same bar the other way, in both periods. This is reported, never flipped.
  - **Context, not a signal:** everything else.

## Results (2026-11-03 build, NQ1! daily 2021-10-19 -> 2026-10-16)

| God | Corr 2021-25 | Corr 2026 | Hit - chance 2021-25 | Hit - chance 2026 | Verdict |
|---|---|---|---|---|---|
| COUNCIL | +0.04 | +0.03 | -0.2 | +1.9 | context, not a signal |
| POSEIDON | +0.05 | +0.05 | +0.1 | +1.6 | context |
| ZEUS | +0.08 | -0.05 | +2.7 | -6.6 | context (flips sign in 2026) |
| ARES | -0.05 | -0.13 | -3.6 | -3.9 | **inverse**: high fear was followed by NQ bounces in both periods |
| ATHENA | event-day move 1.40x | 1.09x | | | context (bigger moves on event days, but only 1.09x in 2026) |
| DEMETER | +0.01 | +0.07 | -1.2 | +2.2 | context |
| HELIOS | +0.00 | +0.08 | -1.3 | +1.1 | context |
| NYX | +0.07 | +0.10 | +8.3 | +1.2 | context (closest to a signal; 2021-25 has only ~1 year of z-scores) |
| ARTEMIS | +0.00 | +0.02 | +0.5 | -7.0 | context (display only) |

ARES's inverse result (fear -> next-day bounce) is a lead for its own research run, not a change: a filter or flip would
need the full LIT test (2026 halves, 2-4 trades a week, the eval speed). Nothing here was adopted.

## `research/pantheon/states.json` (the Data City contract)

Daily regime states per god, for Data City to use as new while-states. The site also publishes it at `pantheon/states.json`,
and CRONOS puts it on the `cronos` branch at `pantheon/states.json`.

```json
{
  "v": 1, "app": "pantheon", "t": 1793721819, "built": "2026-11-03 11:10 ET",
  "sessions": {"first": "2021-11-01", "last": "2026-11-04", "calendar": "Mon-Fri"},
  "rule": "A state listed for session D used only data published by the close of session D-1 (no look-ahead). ...",
  "gods": ["poseidon", "zeus", "ares", "athena", "demeter", "helios", "nyx", "artemis"],
  "states": [
    {"id": "zeus.curve_inverted", "god": "zeus", "label": "Curve inverted (10y - 2y < 0)", "from": "2021-11-01",
     "now": false, "days_on": 563, "on": [["2022-07-07", "2024-09-05"], ["2024-09-10", "2024-09-10"]]}
  ]
}
```

| Field | Meaning |
|---|---|
| `sessions.first` / `last` | the Mon-Fri session dates covered; `last` is the **next** session after the build |
| `id` | `<god>.<state>`; stable, safe to key on |
| `label` | plain language, for the UI |
| `from` | the first session with data. Before it, false means unknown (NYX starts 2023-11 because of FRED's 3-year ICE limit) |
| `on` | the sessions where the state is true, as sorted inclusive `[first, last]` session-date ranges. Expand with a Mon-Fri calendar; holidays inside a range simply have no bar |
| `days_on` | the Mon-Fri days inside `on` |
| `now` | true for the next session (`sessions.last`) |

States: POSEIDON `net_liquidity_rising`, `net_liquidity_falling`, `rrp_falling`, `rrp_drained`, `tga_rising`, `fed_qt`.
ZEUS `yields_rising`, `yields_falling`, `high_rates`, `curve_inverted`, `curve_steepening`. ARES `backwardation`,
`vix_above_20`, `vix_above_30`, `vix_spike`, `vix9d_above_vix`, `vxn_above_25`, `gex_negative`. ATHENA `event_day`,
`event_tomorrow`, `fomc_day`. DEMETER `am_net_long_rising`, `am_net_long_falling`, `lev_funds_net_short`,
`lev_funds_covering`. HELIOS `dollar_rising`, `dollar_falling`, `dollar_above_200d`. NYX `spreads_widening`,
`spreads_tightening`, `credit_stress`, `conditions_tight`. ARTEMIS `btc_above_50d`, `btc_drawdown_20` (display only: not
futures data, keep them out of any strategy test).

## Commands

- `python -X utf8 -m tools.pantheon`: fetch, build and write `research/pantheon/` and the page copies.
- `python -X utf8 -m tools.pantheon --offline`: no network. It uses the cache `data/pantheon_cache/` (gitignored), then
  the repo's own files.
- `python -X utf8 -m tools.pantheon --fixture-json`: also refreshes the page's demo copy.
- `python -X utf8 -m tools.pantheon.record`: trims the last downloads into the test fixtures.
- `python -X utf8 -m tools.cronos --task pantheon --out <dir>`: the nightly task, run by hand.

## 2026-11-04: history charts, "what if", the verdict timeline, flip alerts, the daily note

`pantheonplus.js` (pure functions + small DOM parts; read-only context, nothing here changes a strategy):

| Part | What it does |
|---|---|
| God card, History | a chart of the god's last 64 readings (low / high marked, drag a finger along it for "Reading k of N, x% vs now", the 5-year percentile) |
| Council panel, What would the Council say if... | one slider per voting god (-1 .. +1) and a sit-out button; the verdict uses the build's own rule (mean of the votes, at least 3 voices, risk-on from +0.20, risk-off from -0.20, gauge = (score + 1) x 50), checked against `tools/pantheon/council.py` in `tests/test_pantheon.py`; the 3D orb takes the pretend verdict's colour; closing the panel puts the real one back; nothing is saved |
| Council panel, Verdict timeline | the last year as runs of one verdict (RISK-ON / MIXED / RISK-OFF), newest first, "about N weeks" (a reading is about 0.8 weeks apart) |
| Flip alert | this phone remembers the last verdict (`localStorage` `pantheon.last`, `pantheon.flips`, nothing else); when it differs a banner says "The Council changed its mind: A to B" (gold laurel leaves for risk-on, embers for risk-off, nothing on reduced motion) and the flip is listed on the timeline |
| Today's Council note | 3-4 lines of at most 120 characters (verdict, the sentence, the caution, the honest check): Copy, or Show on Jarvis (inside Jarvis the note and a flip line go on her Pantheon card) |
| Effects | `fx-core.js` + the OLYMPUS effects: light shafts onto the Council orb, dust, fireflies (GPU tiers only; each one optional) |

