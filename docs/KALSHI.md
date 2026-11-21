# KALSHI: the one page (K8 gold/silver clock bets, $55, live from Monday 2026-11-23)

Updated 2026-11-20 (day-kalshi). Older Kalshi docs (KALSHI_GO_LIVE, KALSHI_VM_UPDATE, KALSHICITY, KALSHI_PUBLISH, the planner
comparison) are about the retired crypto bot on the Oracle VM and the old kalshi-feed; **this page is the current one**.

## What it is (plain words)

Three small bets a weekday on Kalshi's 15-minute gold and silver markets, at fixed clock times when the price usually moves one way:

| Bet | When (ET) | Side | Live? |
|---|---|---|---|
| gold DOWN | 05:15-05:30 (London 10:15, the gold auction) | DOWN | **live** |
| gold UP | 16:45-17:00 | UP | **live** |
| silver UP | 16:45-17:00 | UP | **live** |
| silver DOWN 05:15, silver DOWN 16:00 | | | paper only (too thin / weaker) |

The bot buys 20 seconds after the window opens, holds to the result (15 minutes), never sells early.

**The $55 rule** (engine/kalshi_clock.bankroll_rule, research/lab/kalshi_clock.json): $2.50 a bet (4-6 contracts at 41-58c),
at most 3 bets a day. Every order is checked first with every open bet counted as already lost:

| Stop | $ | What happens |
|---|---|---|
| A day | -$8.00 | no more bets today |
| A week (Mon-Fri) | -$13.75 | no more bets this week |
| From the best point | -$19.25 | live OFF until Claude and you look |
| Win rate | under 58% won after 60 live bets | live OFF |
| Price creep | the last 30 bets paid over 58c on average | live OFF (others are copying the clock) |
| Price cap | over 70c | that bet is skipped |

Fees are Kalshi's exact taker fee: 4 contracts pay 7c (1.75c each), 1-3 contracts pay 2c each.

## What runs, where

| What | Where | File |
|---|---|---|
| The bot (paper always, live only when armed) | your PC, started by the 15-minute report | `engine/kalshi_clock.py` (ClockLoop), kept alive by `tools/pc_report.py` -> `engine.kalshi_live.maybe_run` |
| The private phone page (key, bet size, phrase, STOP) | your PC, Tailscale only: `https://<your PC link>:8444/kalshi-live/` | `engine/kalshi_web.py` |
| The live switch + the key check | your PC | `engine/kalshi_live.py` (arm / arm_state; the phrase `I ACCEPT KALSHI LIVE RISK`) |
| The settings you arm | the repo | `research/lab/kalshi_clock.json` (any change = live OFF until you type the phrase again) |
| The weekly re-test (may only SHRINK a leg) | your PC, weekends | `engine/kalshi_adapt.py` -> `data/kalshi_live/clock_adapt.json` |
| The public Kalshi page (K8 card, countdowns, bet log, stops, edge health) | the site | `tools/web_public/kalshi/` (reads the PC's card + `k8.json`) |
| Edge health from Kalshi's public results | the repo | `tools/kalshi_k8_feed.py` -> `tools/web_public/kalshi/k8.json` |
| Your key | your PC only, OUTSIDE the repo (`OLYMPUS_HOME\kalshi\`) | never in the repo, never in a chat |

On the PC, everything the bot writes is in `data/kalshi_live/` (gitignored): `clock_paper.json` / `clock_live.json` = the bet
ledgers (the counters come from these, so a restart keeps them), `clock_state.json` = windows done, `arm.json` = the live switch,
`KILL` = the kill switch, `clock_loop.log` = the log. `python -X utf8 -m engine.kalshi_live --clock-report` prints it all.

## Your Monday steps (only you can do these)

The one-page version with what you should see at each step: `docs/KALSHI_MONDAY.md`. The executor moved to 2026-11-21.1 (a
safety fix: a bet whose answer from Kalshi is lost is never forgotten), so type the phrase AFTER the PC has updated.

1. On kalshi.com: Account > Profile Settings > API Keys > Create New API Key. Keep the page open (Key ID + the private key).
2. On your phone open your PC link with `:8444/kalshi-live/` at the end. Paste the Key ID and the key, tap Save: it must say
   "Key OK · balance $55.00".
3. Pick **$2.50** (marked "the rule"), type the phrase below, tap Start LIVE. Before 4:44 PM ET = Monday's 16:45 bets; after 6 PM =
   the first bet is Tuesday 05:15 ET. STOP on that page turns it off at once.

```
I ACCEPT KALSHI LIVE RISK
```

## What your phone shows

| When | Push (ntfy) | Example |
|---|---|---|
| A bet goes in (05:15:20, 16:45:20) | one push per window | **Kalshi LIVE 16:45 ET: 2 bets in** - gold UP 16:45-17:00 ET: 4 at 53c ($2.12); silver UP 16:45-17:00 ET: 4 at 55c ($2.20). Results about 16 minutes after the open. |
| It settles (05:30, 17:00) | one push per window | **Kalshi LIVE 17:00: gold WON +$2.41, silver LOST -$2.54** - Today +$1.48 on 3 bets. Live so far: 3 bets, 2 won (67%), +$1.48. |
| End of day (17:05) | one quiet push | **Kalshi K8 Mon Nov 23: LIVE +$1.48 \| paper +$5.47** - today, since the start, live ON/OFF, the kill rule |
| A stop fires | one loud push | **Kalshi K8 STOPPED: ...** - why, open bets settle by themselves, how to restart |
| No bet in a window | one quiet push | **Kalshi LIVE 05:15 ET: no bet** - which stop / cap / thin book skipped it |

The Kalshi page's **K8 status** card shows LIVE / PAPER, today's windows with countdowns, the price paid vs the fair price,
the last 5 bets, the day / week / peak stops as bars, and edge health (win rate last 30 / 60 vs 58%, the average price vs 58c).

## Calendar

| Days | Bets |
|---|---|
| Mon-Wed Nov 23-25 | all 3 |
| Thu Nov 26 (Thanksgiving), Fri Nov 27 | 05:15 gold only (the CME closes early: the evening skips) |
| Dec 24, Dec 25, Jan 1, Mar 26 | evening skips; Dec 25, Dec 28, Jan 1, Mar 26, Mar 29: morning skips (no London auction) |

## Checks (Claude)

`python tests/run_area.py kalshi` (includes `tests/test_kalshi_k8_day.py`: Monday rehearsal, every stop, restarts, no order without
the key + phrase) · `python research/kalshi_k8_day/rehearsal.py` · `python tools/kalshi_k8_feed.py` (refresh k8.json after
`python research/kalshi_k8_day/fetch.py`, public GET, 1 a second) · `python research/kalshi_k8_day/noise.py`.
