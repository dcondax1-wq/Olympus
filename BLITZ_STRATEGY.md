# BLITZ, the scalper: the exact rule, how it should perform, and when the bot stops it

Market: NQ futures, traded as MNQ micros ($2 a point). 1-minute candles, New York time (ET). One rule, written once in
`engine/blitz.py` (`DEFAULT_PARAMS` = the researched rule below), used three ways:
- **two PAPER shadow ledgers** (since 2026-10-28, never routed): a simulated Builder 25K eval and "BLITZ on a funded 50K next
  to LIT" (`engine/blitz.py`, heartbeat `blitz`, Live View purple layer);
- **its own MFFU Builder 25K = account C** (built 2026-10-29, `engine/account_c.py`): **OFF by default**. It trades a Sim
  account until the owner arms a real 25K himself on the Start page (typed I ACCEPT LIVE RISK). Switch: Start page >
  "BLITZ · 25K", or `python -X utf8 -m engine.account_c --account "<Name>" --plan builder25k --start <day>` / `off`.

Research: `research/writeups/scalp-na-mffu.md` (runs `scalp_na_blitz`, `scalp_na_blitz_lit50k`), trades of 2026 in
`research/scalp/na_best_trades.json` (330). Picked on 2026 H1, checked on 2026 H2, 2021-25 on 5m bars as the reference.
Costs in everywhere: $1.90 a micro round trip + 1 tick on every market and stop fill.

## Money first (honest)

**BLITZ makes money as a trade rule, but its own 25K account is a weak business.** The research's whole-slot numbers (buy
the eval, pass, get funded, payouts at 80% to you, a new eval after a fail) for BLITZ alone on a 25K are **+$224 a month
(2026 H1), +$3 (2026 H2), -$40 (2021-25)**. Only about a third of evals pass within 2 weeks and most are still undecided
then, so the owner's "passed or failed within 2 weeks" rule is missed. The best use the research found is BLITZ on LIT's
funded 50K while LIT is flat (+$290-300 a month per account slot), which needs LIT's 50K funded first: not built here.
Account C is built so you can **see how BLITZ performs on its own account** next to Zlarior and ATLAS, with a kill switch.

| BLITZ alone on its own MFFU 25K | 2026 H1 (pick) | **2026 H2 (check)** | 2021-25 (reference) |
|---|---:|---:|---:|
| Eval pass / fail within **2 weeks** (10 sessions) | 31.1% / 10.1% | **34.8% / 2.9%** | 16.8% / 13.6% |
| Decided within 2 weeks | 41% | 38% | 30% |
| Pass / fail within 3 weeks | 44.7% / 21.9% | 42.2% / 18.8% | 21.8% / 27.8% |
| Pass / fail within **1 month** | 52.3% / 38.5% | 42.4% / 40.7% | 24.8% / 37.7% |
| Median sessions to pass | 8.5 | 6.5 | 6 |
| Passes slower than 3 weeks | 15% | 7% | 12% |
| **Whole account slot, $ a month to you** | **+$224** | **+$3** | **-$40** |

**The trades themselves** ($150 risk a trade, the research table; 2026 on 1m bars, 2021-25 the same rule on 5m):

| Span | Trades | / week | Weeks with 2+ | Win % | Avg R | PF | Net $ | **$ a month** | Max drawdown |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026 H1 (pick) | 221 | 8.6 | 89% | 55.7% | +0.150 | 1.63 | +$5,560 | **+$912** | -$1,314 |
| **2026 H2 (check)** | 109 | 7.0 | 75% | 55.0% | +0.171 | **1.49** | **+$2,143** | **+$577** | -$903 |
| 2021-25 (5m reference) | 1,869 | 8.7 | 81% | 50.3% | +0.016 | 1.06 | +$4,570 | +$89 | -$4,783 |

By year at $150 a trade: 2022 +$264 a month, 2023 +$111, **2024 -$144**, 2025 +$139, 2026 +$785. It trades on about 43% of
days and takes 5-6 trades on trend days: **it is a trend-day machine**; quiet weeks lose a little.

**On the eval size** (40% of the room, the live sizing below; the bot's own replay of 2026 through the paper shadow, a new
$63 eval after each pass / fail / stuck): 25K eval path **+$7,193 (H1) / +$4,726 (H2)**, 4 / 2 and 3 / 2 pass / (fail +
stuck), about **+$1,108 / +$1,188 a month after the eval fees**. That is profit inside evals, not money paid to you: an
eval's profit is paid only through a funded account's payouts, which is why the whole-slot line above is the honest one.
**Account C's own live loop on 2026** (`tests/test_account_c.py` part 2: the paper adapter, minute polls, one eval at a
time, a new $63 eval after each pass / fail / stuck): every one of the 330 BLITZ trades seen exactly as the research;
**H1 182 / H2 88 routed, +$8,262 / +$5,559 inside the evals (PF in $ 1.60 / 2.11), 9 evals passed, 0 failed, 6 stuck**
(room under $249.56), the kill switch never fired. Again: inside-eval money, not payouts.

## The rule (exact)

1. **Day filter.** Trade a day only if **yesterday's 09:30-16:00 range was at least 0.8 x the average of the last 14 such
   ranges** (yesterday's included). Known before the open. (The one filter that held in 2026 H1, H2 and 2021-25.)
2. **Noise band.** For each minute of the day: sigma = the average over the last 14 sessions of |close / 09:30 open - 1| at
   that minute (today never included). Upper band = today's 09:30 open x (1 + sigma), lower = open x (1 - sigma).
3. **Checks** only at the 1-minute closes of **11:00, 11:30, 12:00 ... 15:30** (11 checks). A close **above the upper band
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

- **Eval size:** risk = **40% of the room** to the trailing floor, at most **$600** and at most **0.9 x what is left of
  today's $600 soft daily loss**, divided by the stop's cost per micro ((stop + 1 tick) x $2 + $1.90), **max 20 micros**;
  1 micro while that still fits half the room. Example: $1,000 room, 60-point stop = $122.40 a micro -> $400 -> 3 micros.
  A wide stop gets fewer micros (size follows the stop).
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
- A blocked signal still uses BLITZ's slot (its 30-minute trade runs on paper): the bot never chases a later price.

## How it should perform (the bands to judge it by)

| What | Expected (2026 H1 / H2) | Weak year (2021-25) |
|---|---|---|
| Trades a week | 7-9 (8.6 / 7.0), on ~43% of days, up to 6 on a trend day | 8.7 |
| Win rate | ~55% | ~50% |
| Average R a trade | +0.15 / +0.17 | +0.016 |
| PF | 1.63 / 1.49 | 1.06 |
| $ a month at $150 a trade | +$912 / +$577 | +$89 |
| Worst drawdown at $150 a trade | -$1,314 / -$903 | -$4,783 |
| Losing days in a row (R) | 3 at worst in 2026 | longer |
| Eval passed within 2 weeks / 1 month | 31-35% / 42-52% | 17% / 25% |
| Eval failed within 2 weeks / 1 month | 3-10% / 39-41% | 14% / 38% |

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

2. **6 losing days in a row** (a day's trades sum under 0R; 2026's worst was 3).

Also stopping it: the eval's fail / stuck (no new trade), the $600 soft daily loss (rest of the day), 6 trades or -3R in a
day. **Resume is the owner's decision:** `python -X utf8 -m engine.account_c --resume` (the pause lifts at the next poll).
What to watch on the dashboards: the account card's scorecard (trades, win %, avg R, PF, $, losing days) next to the
floor; BLITZ's paper shadow keeps running as the comparison.

## Turn it on (owner, next week)

1. Buy the MFFU Builder 25K for BLITZ (your price, $63 or $43 with a code) and connect it in NinjaTrader.
2. Start page > **BLITZ · 25K**: type its Name exactly as NinjaTrader shows it, press **Set BLITZ's 25K**, then **Arm BLITZ**
   (type I ACCEPT LIVE RISK). Try **Sim test** first if you want to watch it on Sim101 for a day.
3. Press **Start trading**.

(Console instead of step 2: `python -X utf8 -m engine.account_c --account "<the 25K Name>" --plan builder25k --start 2026-11-02`.)
