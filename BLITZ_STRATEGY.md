# BLITZ, the scalper: the exact rule, how it should perform, and when the bot stops it

Market: NQ futures, traded as MNQ micros ($2 a point). 1-minute candles, New York time (ET). One rule, written once in
`engine/blitz.py` (`DEFAULT_PARAMS` = the researched rule below), used three ways:
- **two PAPER shadow ledgers** (since 2026-10-28, never routed): a simulated Builder 25K eval and "BLITZ on a funded 50K next
  to LIT" (`engine/blitz.py`, heartbeat `blitz`, Live View purple layer);
- **its own MFFU Builder 25K = account C** (built 2026-10-29, `engine/account_c.py`): **OFF by default**. It trades a Sim
  account until the owner arms a real 25K himself on the Start page (typed I ACCEPT LIVE RISK). Switch: Start page >
  "BLITZ · 25K", or `python -X utf8 -m engine.account_c --account "<Name>" --plan builder25k --start <day>` / `off`.

Research: `research/writeups/scalp-na-mffu.md` (the rule, runs `scalp_na_blitz`, `scalp_na_blitz_lit50k`) and
`research/writeups/blitz-25k.md` (BLITZ as account C on its own 25K, 1,997 variants, verdict **no change to the rule**,
`research/scalp/blitz_25k_pick.json`). Picked on 2026 H1, checked on 2026 H2, 2021-25 on 5m bars as the reference. Costs in
everywhere: $1.90 a micro round trip + 1 tick on every market and stop fill.

## Money first (honest)

**On its own 25K, BLITZ is mostly an eval experiment: its real edge per trade is small.** Nothing "like a person"
(structure stops, liquidity targets, swing trails, change-of-character exits) beat today's rule in 2026 H1, H2 and 2021-25.
The whole account slot (buy the eval, pass, get funded, payouts at 80% to you, a new eval after a fail) pays **+$270 a
month (2026 H1), +$37 (2026 H2), -$40 (2021-25)**. In H2 random directions on the same signals make about the same ($30):
outside H1 the 25K is an eval lottery ($63 tickets, about 1 in 3 pass), not BLITZ's edge. Once funded, a 25K gets stuck
near its floor before it pays much (funded **$108 / $0 / $2 a month**). The best use the research found is BLITZ on LIT's
funded 50K while LIT is flat (+$290-300 a month per account slot), which needs LIT's 50K funded first: not built here.
Account C is built so you can **see how BLITZ performs on its own account** next to Zlarior and ATLAS, with a kill switch.

**BLITZ as account C trades** (today's rule, never against Zlarior or ATLAS; $150 risk a trade; 2026 on 1m bars, 2021-25
the same rule on 5m):

| Span | Trades | / week | Weeks with 2+ | Win % | Avg R | PF | Net $ | **$ a month** | Max drawdown |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026 H1 (pick) | 217 | 8.5 | 89% | 56.7% | +0.165 | 1.70 | +$5,873 | **+$963** | -$1,152 |
| **2026 H2 (check)** | 106 | 6.8 | 75% | 56.6% | +0.200 | **1.62** | **+$2,478** | **+$667** | -$815 |
| 2021-25 (5m reference) | 1,841 | 8.6 | 80% | 50.1% | +0.013 | 1.05 | +$3,765 | +$73 | -$5,512 |

(BLITZ alone, without the no-hedging rule: PF 1.63 / 1.49 / 1.06, +$912 / +$577 / +$89 a month. The no-hedging rule costs
nothing in 2026: the 12 trades it skips averaged -0.14R; about $16 a month in 2021-25.) By year at $150 a trade (BLITZ
alone): 2022 +$264 a month, 2023 +$111, **2024 -$144**, 2025 +$139, 2026 +$785. It trades on about 43% of days and takes
5-6 trades on trend days: **it is a trend-day machine**; quiet weeks lose a little.

**The 25K eval at account C's size** (40% of the room for the first 4 sessions, then the full room from session 5, see below):

| Builder 25K eval | 2026 H1 (pick) | **2026 H2 (check)** | 2021-25 (reference) |
|---|---:|---:|---:|
| Pass / fail within **2 weeks** (10 sessions) | 36.1% / 37.8% | **36.2% / 34.8%** | 20.4% / 50.2% |
| Decided within 2 weeks | 74% | 71% | 71% |
| Pass / fail within 3 weeks | 45.6% / 46.5% | 32.8% / 57.8% | 23.8% / 64.8% |
| Pass / fail within **1 month** (20 sessions) | 48.6% / 49.5% | 27.1% / 72.9% | 25.3% / 70.8% |
| Median sessions to pass | 6 | 5 | 6 |
| Passes slower than 3 weeks | 10% | 0% | 6% |
| **Whole account slot, $ a month to you** | **+$270** | **+$37** | **-$40** |
| (the paper ledger's flat 40%: decided in 2 weeks, slot) | 41%, $251 | 39%, $40 | 29%, -$34 |

The size changes **how fast** an eval ends, not the money: the owner's rule "passed or failed within 2 weeks" is met for
71-74% of evals (the flat 40% leaves about 60% undecided). The price: in 2026 about as many evals fail as pass, in 2021-25
two fail for every pass ($63 each).

**Account C's own live loop on 2026** (`tests/test_account_c.py` part 2: the paper adapter, minute polls, one eval at a
time, a new $63 eval after each pass / fail / stuck, no Zlarior / ATLAS trades in the replay): every one of the 330 BLITZ
trades seen exactly as the research; **H1 182 / H2 82 routed, +$10,900 / +$4,709 inside the evals (PF in $ 1.62 / 1.60), 14
evals passed, 0 failed, 12 stuck** (room under $249.56: the eval is dead before the floor), the kill switch never fired.
Inside-eval money is not paid money: it reaches you only through a funded account's payouts, which is why the slot line
above is the honest one.

## The rule (exact)

1. **Day filter.** Trade a day only if **yesterday's 09:30-16:00 range was at least 0.8 x the average of the last 14 such
   ranges** (yesterday's included). Known before the open. (The one filter that held in 2026 H1, H2 and 2021-25.)
2. **Noise band.** For each minute of the day: sigma = the average over the last 14 sessions of |close / 09:30 open - 1| at
   that minute (today never included). Upper band = today's 09:30 open x (1 + sigma), lower = open x (1 - sigma).
3. **Checks** only at the 1-minute closes of **11:00, 11:30, 12:00 ... 15:30** (10 checks). A close **above the upper band
   = BUY**, below the lower band = SELL. While flat, a later check can enter again.
4. **Entry:** at market at the next bar's open, right after the signal close (the bot sends it about 2 s after the close;
   a signal first seen more than 50 s late is not chased).
5. **Stop:** the signal close -/+ **1.5 x the 5-minute ATR** (14 bars, Wilder; about 60 points in 2026). It sits at
   NinjaTrader as a stop order from the entry on, with an OCO limit at 20R that is never reached in practice.
6. **Trailing:** after **+1R** the stop trails **1.5R behind the best price** (a stop change at NinjaTrader, only ever tighter).
7. **Time exit:** out at market after **30 one-minute bars**, and always **flat by 15:55** (on a CME early-close day 5 minutes
   before the halt, and no entry in the last 15 minutes before it).
8. **Limits:** one position, at most **6 trades a day**, no new trade after **-3R** on the day.

How 2026's trades ended: 73% at the 30-minute clock, 20% at the stop (first stop or trail), 7% at 15:55.
Changing the rule is a config change only (`data/account_c.json` "params", `engine/blitz.rule_params`); the default stays
this rule until a research pick passes both 2026 halves and 2021-25 and the owner adopts it.

## Size and the account rules (MFFU Builder 25K)

- **Eval size (research/scalp/blitz_25k_pick.json "eval_25k"):** risk = **40% of the room** to the trailing floor for
  sessions 1-4, then **the full room from session 5**, always at most **$600** and at most **0.9 x what is left of today's
  $600 soft daily loss**, divided by the stop's cost per micro ((stop + 1 tick) x $2 + $1.90), **max 20 micros**; 1 micro
  while that still fits half the room. Example: $1,000 room, 60-point stop = $122.40 a micro: session 1-4 $400 -> 3 micros,
  from session 5 $540 -> 4. A wide stop gets fewer micros (size follows the stop). `"sizing": "paper"` in
  data/account_c.json keeps the paper ledger's flat 40% instead.
- **Eval:** pass at +$1,500 (no new trade, push "EVAL PASSED: run the funded switch"; **never automatic**), fail when the
  room is gone ($1,000 EOD trailing max loss, locked at start + $100), **stuck** when the room is under $249.56 (2 x
  BLITZ's median stop-out: 1 micro no longer fits; push "buy a new one"), the **$600 soft daily loss** = no new entry today.
- **Funded** (after the owner's switch to the new funded Name, disarmed until he arms it): 10% of the room, at most $150 a
  trade, no new trade after +$400 on the day (the research's 25K funded pick), the payout tracker as ATLAS's.
- **Never against your other accounts** (MFFU bans long + short on one underlying across your own accounts): no BLITZ
  entry while Zlarior holds, enters or has a setup armed the other way, or ATLAS holds the other side. **Zlarior first, then
  ATLAS, then BLITZ:** if Zlarior or ATLAS enters the other way while BLITZ is in a trade, BLITZ is closed at market first and
  their order goes out only once NinjaTrader shows BLITZ flat. Same direction is allowed.
- An order NinjaTrader refused or never took is never booked (push "order NOT placed" with NinjaTrader's reason).
- A signal skipped by the no-hedging rule is no trade at all (a later check may enter, as the research measured it); a
  signal blocked for another reason (eval over, size 0, the daily loss, a late signal) keeps its 30-minute model trade on
  paper, so BLITZ waits for it and never chases a later price.
- Order checks: at most 20 micros, a stop over 250 points is refused (BLITZ's stop is 1.5 x the 5m ATR: 37 of 2026's 330
  stops were wider than Zlarior's 100-point cap, the widest 202).
- **The later-break size, ON** (approved by the owner 2026-10-31; research/writeups/atlas-blitz-edge-2026-10-30.md).
  `"later_break": false` in data/account_c.json turns it off. On the eval the day's FIRST band break on a side trades at half size and a
  LATER same-side break (2nd, 3rd ... check close beyond the band that day) at 1.75 x (never more than the room; the $600 cap
  scales to $1,050). Same trades, different sizes: 25K 2-week pass / fail H1 47.9 / 23.5 (today 36.1 / 37.8), H2 36.2 / 21.7
  (36.2 / 34.8), 2021-25 24.7 / 48.4 (20.4 / 50.2); account slot +$286 / +$52 / -$39 a month (+$270 / +$37 / -$40). Per
  trade the gain is within chance; a later break risks more (the $ cap scales to $1,050, still inside the room and 90% of
  the $600 soft daily loss left). Funded and paper sizing are unchanged.

## How it should perform (the bands to judge it by)

| What | Expected (2026 H1 / H2) | Weak year (2021-25) |
|---|---|---|
| Trades a week | 7-9 (8.5 / 6.8), on ~43% of days, up to 6 on a trend day | 8.6 |
| Win rate | ~57% | ~50% |
| Average R a trade | +0.17 / +0.20 | +0.013 |
| PF | 1.70 / 1.62 | 1.05 |
| $ a month at $150 a trade | +$963 / +$667 | +$73 |
| Worst drawdown at $150 a trade | -$1,152 / -$815 | -$5,512 |
| Losing days in a row (R) | 3 at worst in 2026 | longer |
| Eval passed within 2 weeks / 1 month | 36% / 27-49% | 20% / 25% |
| Eval failed within 2 weeks / 1 month | 35-38% / 50-73% | 50% / 71% |
| Whole 25K slot, $ a month to you | +$270 / +$37 | -$40 |

## Kill switch (the performance contract, in the code: `engine/account_c.score`)

The bot pauses BLITZ on its account by itself (no new entry on account C, one push "BLITZ PAUSED"; Zlarior and ATLAS keep
trading) when, after its own finished trades:
1. **20 or more trades** and the **average R** or the **PF (in R)** is under the 5th percentile of what 2026's 330 research
   trades give for that many trades (bootstrap). The floors:

   | Finished trades | 20 | 30 | 40 | 60 | 100 | 200 |
   |---|---:|---:|---:|---:|---:|---:|
   | Average R under | -0.150 | -0.095 | -0.061 | -0.021 | +0.019 | +0.061 |
   | PF (R) under | 0.62 | 0.74 | 0.83 | 0.94 | 1.06 | 1.19 |
   | (expected) | +0.15R, PF 1.58 | | | | | |

2. **6 losing days in a row** (a day's BLITZ trades, routed or not, sum under 0R: the research's count; 2026's worst was 3).

Also stopping it: the eval's fail / stuck (no new trade), the $600 soft daily loss (rest of the day), 6 trades or -3R in a
day. **Resume is the owner's decision:** `python -X utf8 -m engine.account_c --resume` (the pause lifts at the next poll).
What to watch on the dashboards: the account card's scorecard (trades, win %, avg R, PF, $, losing days) next to the
floor; BLITZ's paper shadow keeps running as the comparison.

## Why BLITZ did not trade today

The BLITZ card says why. On a filtered day it says, for example, *"BLITZ skipped today: yesterday's 09:30-16:00 range 239 pts < 0.8 x
its 14-day mean 404 pts"*. That was 2026-10-29, and Oct 30 is skipped too (0.66 x). On other days no 1-minute close left the band
at the 10 checks. On 2026-10-28 the nearest was the 11:00 close, 25 points inside the lower band. In 2026, 1 day in 3 was filtered,
and BLITZ traded on 45% of days.

## Turn it on (owner, next week)

The steps are in **`docs/BLITZ_GO_LIVE.md`**: 3 steps, then the go-live check
(`python -X utf8 -m engine.account_c --preflight`, or the Start page card's Go-live check). That file also shows what the
phone says on the first day.

(Console instead of the Start page: `python -X utf8 -m engine.account_c --account "<the 25K Name>" --plan builder25k --start 2026-11-02`.)
