# BLITZ real fills + the one-account book (2026-11-23) - pre-registered, committed BEFORE any scored run

Question (lead): the one-account study (research/writeups/one-account-book-2026-11-22.md) found BLITZ $300 on the Rapid EOD 50K
book makes the most money but left it out: BLITZ had no real-fill check (stored fills = 1 tick a side) and fails more evals.
PAPER RESEARCH ONLY. No live change, no live_model*.json, nothing armed.

## Why a fill check is needed (measured before this design, input only, no book scored)
BLITZ never traded real money (paper shadow), so it has no real fills. It enters with a MARKET order at the 1m open right
after a half-hour check close (11:00 ... 15:30 ET) - the same mechanism as ATLAS (a market order a few seconds after a
widely seen bar close), whose 3 real fills were 10 / 12 / 16 ticks past the open, at 29 / 50 / 38 % (mean 39 %) of the way
from the open to that minute's extreme in the trade's direction (research/writeups/atlas-fills-2026-11-20.md).
BLITZ's 385 entries of 2026 (1m data/NQ_1m.csv): the entry minute reaches a median 9.25 pts (mean 12.9) the trade's way;
ATLAS's 150 entries of 2026: median 4.6 pts. BLITZ is a momentum break: the first seconds run harder than ATLAS's.

## Fill variants (6, fixed now)
F0 stored        1 tick entry + 1 tick on every exit (the 2026-11-22 study's BLITZ)
FM measured      per trade: entry = 1 tick + 0.39 x the entry minute's reach the trade's way (ticks, rounded down); exits 1
                 tick. 2021-25 (5m trades, no 1m bars): the 2026 median of FM's entry ticks for every trade. PRIMARY.
FL measured-low  as FM with 0.29 (ATLAS's best real fill)
T3 / T6 / T10    N ticks on the entry AND on every exit (BLITZ has no resting target: time / flat / trailing-stop exits are
                 all market or stop orders)
Pricing = tools/atlas_fills.priced (pts minus the extra ticks; w1 worse by the extra entry ticks); sizes unchanged (decided
before the fill).

## Books (Rapid EOD 50K, $165; research/onebook/book.py engine, rank.py real fills, ATLAS at 10 ticks; same paths:
1,000 x 126 sessions seed 23 for the 6-month slot, 1,000 x 60 seed 7 for the eval)
P  = B11 (the picked plain book: LIT + ATLAS first-come, LIT x0.5 in the eval)          - no BLITZ, 1 run
PB = B11 + BLITZ $300 lane (f 0.3), BLITZ in the eval and funded                        - per fill variant (6)
QB = B12 (B03 + BLITZ $300) as in the 2026-11-22 study                                  - per fill variant (6)
B01 (LIT only) for the fail bar. Counted: 15 runs, 12 BLITZ variants.
Reported: trades/wk, PF, fixed net $ (BLITZ alone at $300 and the book), max DD, eval pass/fail % + median days, 6-month net
$ after fees, $/month, first payout, for H1 = 2026 Jan-Jun, H2 = 2026 Jul-Oct, REF = 2021-11..2025.

## Verdict rule (fixed now)
BLITZ joins the book only if, at FM (primary): PB's 6-month net $ > P's in H1 AND in H2, AND PB's H1 eval fail % <= B01's H1
fail % + 2 points (the onebook bar), AND PB's REF net $ >= P's REF net $ (the onebook "not worse 2021-25" bar).
Robustness note (not the rule): the same at T6. A Decide card only if the rule holds; else a dated line in
docs/TESTED_AND_REJECTED.md and research/writeups/blitz-fills-2026-11-23.md.
