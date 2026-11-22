# K8 live re-check: pre-registration (written 2026-11-21 20:50 UTC, BEFORE fetching or computing anything new)

Purpose: before the owner goes live Monday 2026-11-23 at $2.50 a bet with $55, re-check K8's edge on the freshest free data
and give the expected $/week and the odds of hitting the stops. No rule is changed by this; it is a check, not a search.

## Legs (fixed, the 3 LIVE legs of engine/kalshi_clock.DEFAULT; nothing else is scored)
- gold DOWN 05:15-05:30 ET (KXGOLD15M, buy NO), gold UP 16:45-17:00 ET (KXGOLD15M, YES), silver UP 16:45-17:00 ET (KXSILVER15M, YES).
- Calendar = the executor's own (KC.leg_open / KC.skipped: London clock for the morning leg, UK / CME holiday skips).

## Data
- Public Kalshi GET only (no key, <= 1 request/s, generic User-Agent), via engine.kalshi_adapt.fetch_tape: Kalshi's result +
  the first 45 s of public trades of every leg market. Start from the existing caches (research/kalshi_k8_day/data/tape.jsonl,
  research/kalshi_k8_monday/data/tape_fresh.jsonl), copy them to research/kalshi_k8_live/data/tape.jsonl and only add what is missing.
- Windows: (a) full history Aug 3 - latest settled (in-sample: the friend picked the windows from Aug-Nov 18), (b) last 4 weeks
  (Oct 26 - Nov 20, still in-sample up to Nov 18), (c) OUT-OF-SAMPLE = every settled live-leg window after Nov 18 = Thu Nov 19 and
  Fri Nov 20 only: at most 6 bets. **That is far too few to prove or disprove anything; it is reported only as a first look.**
  Note: Nov 19 was already seen by the Nov 20 write-up (kalshi-k8-monday), so only Nov 20 is truly unseen by anyone.

## Entry price and costs (fixed)
- Primary: a $2.50 (or $1.00) taker order walking the public fills of our side from +20.0 s (k8m_data.walk_from, prices <= 70c cap,
  until 45 s; under half the wanted contracts = no bet). Contracts = whole, cost <= stake. Secondary (reported only): the first
  trade of our side at/after 20 s.
- Fee per order = ceil-to-cent(0.07 x C x P x (1-P)) (research/kalshi_red_team/verify.fee = engine/kalshi_clock.fee). Hold to settle.

## Numbers reported (for each window a/b/c, 3 live legs, $2.50, fees in)
bets, win rate, average price paid, $ per bet, bets/week (actual and planned = 3 x 5 minus calendar skips), expected $/week,
95% interval of $/week (bootstrap of whole days, 5,000 draws). Plus the HAIRCUT planning case: win rate 10 points under the
full-history rate (winners turned into losers at random, prices kept).

## Monte Carlo (20,000 runs each; starting $55; the real calendar from Mon Nov 23, 4 and 12 weeks)
- Draw whole historical days (keeps the gold/silver 17:00 correlation); each drawn day gives the bets it had on the legs used.
- Executor rules applied before every bet with open bets counted as lost: day stop -$8, week stop -$13.75 (rest of the week
  skipped), drawdown stop -$19.25 from the peak (bet refused -> bot OFF for good), kill under 58% won after 60 bets, kill if the
  last 30 bets averaged over 58c (both -> OFF). Balance must cover the bet.
- Report: P(week stop hit at least once), P(bot OFF by the drawdown stop), P(any OFF), P(balance below $30 at any point),
  median and 5th percentile ending balance, expected $ after 4 weeks.
- Settings: (1) $2.50, 3 legs (current), (2) $2.50 gold only (2 legs), (3) $1.00, 3 legs. Each under the full-history bootstrap,
  the last-4-weeks bootstrap, and the haircut case.

## Checks
- Fill: on each live leg, share of days on which other takers bought >= our wanted contracts of our side in 20-30 s and in 20-45 s;
  median contracts traded on our side in 20-30 s.
- Price creep: average price paid by ISO week.

## Verdict rule (fixed now)
- "Edge still there" if the full-history and last-4-weeks $/bet are both > 0 with the 95% interval of the last 4 weeks above 0.
  The OOS 2 days cannot change the verdict either way unless they show a fill or price failure (e.g. average price > 58c).
- "Safer setting better" if it gives a lower P(bot OFF) without dropping expected $/week by more than half.
