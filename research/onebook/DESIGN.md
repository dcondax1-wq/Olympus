# One-account book (lane E, 2026-11-22): pre-registered design, committed BEFORE any scored run

Question (owner via lead): "combine strategies on accounts to get more trades; what should we do with ONE account?"
Paper research only. Nothing live, no live_model*.json, no orders.

## Engine (reused, not rebuilt)
research/plans/rank.py (the real-fills plan engine): eval = live LIT two_week sizing on the plan's numbers + added lanes
(rapid_levers.q_add: $ = min(lane $, 30% of room, soft day left)) + the 30% best-day guard where the eval has a consistency
rule; funded = the plan's own payout rules (buffer, min, caps, 50% best day on Builder, 5 payouts Builder, daily Rapid with
the bot's $500/$1,000 keep), stuck line, re-buy on fail / dead / graduated; Tier-1 news flat on Rapid funded.
ATLAS at its measured real fills (atlas_risk.T_at(10), 10 ticks a side). BLITZ at its stored fills (1 tick), mode "lit+atlas"
(never opposite LIT / ATLAS). Hedge ban: ATLAS units never enter opposite LIT and are closed when LIT enters opposite
(account_b rule, already in the stored units). Same paths for every book: 1,000 x 126 sessions (seed 23) for the 6-month slot,
1,000 x 60 (seed 7) for the eval; 5-session week blocks; H1 = 2026 Jan-Jun, H2 = 2026 Jul-Oct, REF = 2021-11..2025.

## Accounts (owner's real prices)
Builder 50K $91.80, Builder 25K $63, Rapid EOD 25K $97.20, Rapid EOD 50K $165 (CLUB price, as rank.py).

## Books (13 per account = 52, + today's setup = 53 counted)
B01 LIT only | B02 ATLAS only | B03 LIT + ATLAS first-come (one shared soft day) | B04 B03, LIT-priority budget: ATLAS may
use at most 50% of the soft day (no ATLAS entry once the day is down 50%, ATLAS $ <= 50% + today's P&L) | B05 time split:
ATLAS only from 09:30 ET (NY members) | B06 time split: ATLAS only before 09:30 ET (London) | B07 strict windows: LIT only
before 09:30, ATLAS only from 09:30 | B08 B03 with ATLAS x0.5 in the eval (2026-11-19 final rule) | B09 LIT alone in the
eval, LIT + ATLAS once funded (approved card atlas-on-50k-funded) | B10 size split: LIT x0.75 eval and funded (lower
best-day share) | B11 LIT x0.5 in the eval, full funded | B12 B03 + BLITZ $300 lane | B13 B03 with the ATLAS lane doubled.
Not re-run: MES filler (rejected 2026-11-19 lit-more-money: -$66/mo 2021-25, H1 worse; ES has no 2021-24 bars, so the
2021-25 check is impossible) and ES-LIT (rejected 2026-11-13 e3). Counted as 0 new books.

Today's setup = LIT on a Builder 50K slot + ATLAS alone on a Builder 25K slot (two slots, two fees), summed.

## Reported per book x span
trades/wk, PF, net $, max DD (fixed view: LIT $500 / $250, lanes at their $, no account rules), eval pass % / fail % within
60 sessions + median days to pass, 6-month slot: net $ after fees, $/month, owner $ / fees $, first payout (median sessions
from the buy), no-payout %, lost-funded %.

## Pick rule (fixed now)
1. Eligible: H1 eval fail % <= the account's B01 (LIT alone) H1 fail % + 2 points.
2. The best book = the highest H1 6-month net $ among eligible books over all 4 accounts (pick on Jan-Jun only).
3. Check: the picked book's H2 net $ > today's setup H2 net $ AND REF net $ >= today's setup REF net $.
   (one account vs today's two accounts, fees included). Decide card only if both hold AND H1 also beats today.
4. Also reported (not the pick): the same book vs the 50K slot alone, and the best book per account.
Lanes A-D candidates that passed both 2026 halves are added as extra books at ~06:30 ET if any exist (counted).
