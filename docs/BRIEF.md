# BRIEF: the premarket brief JSON contract (`tools/web_public/nq/brief.json`, v 1)

Built by `python -X utf8 tools/premarket_brief.py` (pure, deterministic, futures data only, read-only: it never places,
changes or arms anything). Same inputs + same `--now` = byte-identical file. The only field that churns is `built_at`.
Size < 20 KB. Readers: nq/ + trading/ pages (day-nqdash3), helios/ morning brief (day-arenas), Jarvis.

Readers MUST: treat any field as possibly `null`; ignore unknown fields; check `v == 1`; show `data.stale` lines when the
list is not empty; never show a bias call as advice when `bias.context_only` is true (show it grey, "context").

Units: prices = NQ index points (float, 2 dp); `*_pts` = points; `$` amounts = US dollars at MNQ $2 a point a micro;
times = ET wall clock "HH:MM" strings; dates = "YYYY-MM-DD" (ET); `*_t` = unix seconds (int).

## Top level
| field | type | meaning |
|---|---|---|
| `v` | int | contract version, 1 |
| `built_at` | str | ISO UTC time the file was built (the ONLY churn field) |
| `day` | str | the trading day this brief is for (ET date; after 18:00 ET it is the NEXT day, CME rule) |
| `weekday` | str | "Fri" |
| `phase` | str | `pre` (before 09:30 ET), `rth` (09:30-16:00), `post` (after 16:00: `recap` filled), `closed` (weekend / CME full closure) |
| `early_close` | str\|null | "13:00" on a CME early-close day, else null |
| `headline` | str | one plain line for a phone card, e.g. "Gap up 45 pts above yesterday's high. CPI 08:30 (Tier 1). Bias: none (coin)." |
| `data` | obj | where the numbers came from and how old they are |
| `market` | obj | levels and volatility |
| `news` | obj | today + this week, tiered, and what each bot does around news |
| `bias` | obj | the pre-registered day call with its measured hit rate |
| `bots` | list | one entry per bot / leg: window today, what it waits for, levels it watches |
| `recap` | obj\|null | after the close: what happened vs the brief; null before 16:00 ET |
| `prev_recap` | obj\|null | (added v 1.1, additive) the same recap for the PREVIOUS trading day + `day`; filled every morning (the cloud gets the day's bars only after the PC pushes them at 17:05 ET, so `recap` can stay empty on the day itself) |
| `notes` | list[str] | plain-words caveats (max 5) |

## `data`
| field | type | meaning |
|---|---|---|
| `bars` | str | "NQ 5m (TradingView CME NQ1! + NinjaTrader)" |
| `bars_to` | str | ET "YYYY-MM-DD HH:MM" of the last 5m bar used |
| (no age field) | | age = `built_at` - `bars_to`: compute it on the page (an age field would churn the file every build) |
| `vix_date` / `vxn_date` | str\|null | date of the VIX / VXN daily close used |
| `stale` | list[str] | plain-words warnings, e.g. "VIX is from 2026-10-16 (35 days old)"; empty = all fresh |

## `market`
| field | type | meaning |
|---|---|---|
| `last` | float | last price (close of the last 5m bar) |
| `prior_day` | obj | `{day, high, low, close}` = yesterday's CME day (18:00-17:00 ET), = LIT's PDH / PDL |
| `prior_rth_close` | float\|null | yesterday's 16:00 close (the gap is measured from it) |
| `overnight` | obj\|null | `{high, low, from: "18:00", to: "HH:MM"}` today's session from 18:00 to 09:30 (or to now if earlier) |
| `rth_open` | float\|null | today's 09:30 open, null before 09:30 |
| `gap_pts` | float\|null | (rth_open, or last price before 09:30) - prior_rth_close |
| `gap_atr` | float\|null | gap_pts / atr_pts |
| `atr_pts` | float | mean of the last 14 completed CME-day ranges |
| `vix` / `vxn` | obj\|null | `{value, date, band, day_move_pts}`; band = `calm` <15, `normal` 15-20, `elevated` 20-30, `high` >=30; `day_move_pts` = last x value/100/sqrt(252) = LIT's 1-VIX target band size |
| `where` | str | `above_pdh`, `below_pdl`, `inside` (vs the prior CME day range) |
| `where_text` | str | plain words: "Price 26,510 is inside yesterday's range, 42 pts under its high" |
| `levels` | list | `[{name, price, dist_pts}]` sorted by price high to low: PDH, PDL, PDC, ONH, ONL, PWH, PWL, RTH open; dist_pts = price - last |

## `news`
| field | type | meaning |
|---|---|---|
| `today` | list | `[{time, event, tier, source}]` US releases today; tier 1 = high impact, 2 = medium |
| `week` | list | `[{date, weekday, time, event, tier}]` Mon-Fri of this week, tier 1 and 2 |
| `next_tier1` | obj\|null | `{date, time, event, in_days}` the next Tier-1 release from now |
| `rules` | list | `[{bot, rule}]` what each bot does around news, as coded (read-only), plain words |
| `tier1_today` | bool | any Tier-1 release today |

## `bias`
| field | type | meaning |
|---|---|---|
| `call` | str | `up`, `down` or `none` (rule B1, pre-registered: `research/lab/brief_bias_prereg_2026-11-20.md`) |
| `rule_id` | str | "B1" |
| `rule` | str | plain words of the rule |
| `inputs` | obj | `{overnight_move_pts, atr_pts, threshold_pts, at: "08:00"}`; null values before 08:00 ET (call = "none", `why_none` says so) |
| `why_none` | str\|null | why there is no call today (move too small, before 08:00, data missing) |
| `measured` | obj | per period key `2021-25`, `2026H1`, `2026H2`: `{n, hits, hit_pct, base_pct, p}`; n = days with a call; base_pct = drift baseline; p = one-sided binomial vs 50% |
| `alt` | obj | rule B2 (fade yesterday) with the same `call`, `measured` fields |
| `works` | bool | true only if the pre-registered bar is met in all three periods |
| `context_only` | bool | = not works; the page shows the call grey as "context, no better than a coin" |
| `verdict` | str | plain words of the result, e.g. "B1 hit 52% of 640 days (2021-25), 49% (H1), 55% (H2): no better than a coin" |
| `not_reliable` | list[str] | today's flags: Tier-1 at/after 08:30, VIX high, early close, data stale |

## `bots` (list; order fixed: Zlarior, ATLAS legs, Rapid)
| field | type | meaning |
|---|---|---|
| `id` | str | `lit`, `atlas_ema`, `atlas_macd`, `atlas_sr`, `rapid` |
| `name` | str | "Zlarior (LIT)", "ATLAS EMA", "ATLAS MACD", "ATLAS S/R", "Rapid EOD 25K" |
| `accounts` | list[str] | plain account names it trades on (no ids) |
| `windows` | list | `[{from, to}]` ET entry windows TODAY (early close applied: ends 15 min before the halt); empty = no entries today |
| `state` | str | `before`, `open`, `done` (all windows over), `off_today` (e.g. Monday for EMA, closure) |
| `max_trades` | int | max entries a day for this bot / leg |
| `waiting_for` | str | the setup it is waiting for, plain words |
| `watch` | list | `[{name, price}]` the levels this bot watches today (from `market.levels`) |
| `news_rule` | str | what it does around news, as coded |
| `size_rule` | str | plain words of how it sizes (no $ promises) |

## `recap` (null before 16:00 ET; filled in phase `post`)
| field | type | meaning |
|---|---|---|
| `rth_open` / `rth_close` | float | 09:30 open, 16:00 close |
| `body_pts` | float | rth_close - rth_open |
| `high` / `low` | float | today's CME-day high / low so far |
| `took` | list[str] | which levels were taken: "PDH", "PDL", "ONH", "ONL" |
| `bias_call` | str | the morning call (B1) |
| `bias_held` | bool\|null | call matched the RTH body; null when the call was none |
| `alt_call` | str | that day's B2 call |
| `alt_held` | bool\|null | same for B2 |
| `trades` | list | `[{bot, account, side, time, r, usd, src}]` the day's trades the cloud can see (trades.json live / paper rows); src = `live` / `paper`; a bot with live rows shows only those (its paper twin is the same trade) |
| `traded` | str | plain words: "Zlarior: 1 trade (SHORT 03:43, -$437, live). ATLAS: no trade." or "no trade data for today yet" |

## Results so far (2026-11-20, `research/lab/brief_bias.json`)
B1 and B2 are NO better than a coin (see the write-up `research/writeups/premarket-brief-2026-11-20.md`): `works` = false,
`context_only` = true. Readers show the call grey.

## Example
`research/handoff/2026-11-20/brief/brief_today.json` (2026-11-20, a normal day) and `brief_tier1.json` (a Tier-1 day: CPI 2026-11-10 at 08:05 ET), `brief_tier1_recap.json` (the same day at 16:30 ET).
