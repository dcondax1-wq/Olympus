# Multi-strategy books (2026-11-23): design, fixed before any book was scored

Paper research only. Branch `day-books`. No live file, no `live_model*.json`, nothing armed.

Honest note on timing: the lane file (`tools/books/lanes.py`) was built and the grid-cell picks printed (H1 numbers of
single cells) before this file was written; no book, no account and no Jul-Oct / 2021-25 number had been looked at.

## Lanes (29)
LIT Z, ATLAS A (as live), ATLAS members E / M / S, BLITZ B, post-close P, stop hunt H (Asia resweep) and T (trend idm5)
(= the two halves of the "ATLAS v2 hunts"), edge-a ORB-30 O, edge-c Monday long W, and one cell per grid family (19):
new-strategy-hunt lsq / fav / d80 / lxf, E2 orb2 / pdx / rs / gapf / vwr / eod / news, diversifier NA / IB, ATLAS-plus
vwp / odc / pva / ksq / poc, third-strategy cam / tds. Grid cells picked on 2026 Jan-Jun only (net $ at $500, real fills).
Not lanes: edge-b (no trade list: no winner), edge-d (a LIT size rule, not a strategy), edge-e (a book of A-D, all
rejected), day-hunt ESD (a LIT variant that replaces LIT; rejected, loses $ vs LIT in both 2026 halves), branch
day-markets (does not exist on the remote).

## Fills and costs
Main = real fills: stored fills (1 tick a fill, $1.90 a micro) + 2 more entry ticks for LIT and 10 for every other lane
(live reconciliation 2026-11-21: Zlarior 3 ticks late, ATLAS 9-15). Sensitivity = model fills (stored only).

## Accounts and rules
`tools/money/combo_account.py` unchanged (MFFU Builder 50K $91.80, Builder 25K $63, Rapid EOD 25K $97.20, Rapid EOD 50K
$165; eval + funded rules, drawdown and daily limits, 30% best-day guard on Rapid, Tier-1 news on Rapid funded, move to live
after payout 5, 6-month slots net of fees). Sizing: Builder = each engine bot its own size, other lanes the lane rule
(min($125 a 25K / $250 a 50K, 30% room, day loss left)); Rapid = "lanes" (the Rapid preset: first bot own size, all others
lane-sized). Conflict rule, both tried for every book: `first` (one position at a time) and `adds` (same-side stacking,
capped at the plan's max micros and the room left after every open trade's full stop; opposite signals never taken).

## Selection (2026 Jan-Jun = H1 ONLY)
1. Lane gate: a lane enters books only if its H1 stand-alone result at $250 a trade (real fills) is > $0.
2. Book screen: every book of 2-5 gated lanes (ATLAS A never with its own members E/M/S). H1 plain stream at $250 a
   trade, first-in. Keep the top 40 by H1 $ a month AND the top 25 by H1 $ a month among books with >= 5 trades a week.
3. Account stage: each kept book + each single lane in it + today's setups, on all 4 accounts x both conflict rules,
   300 paths x 126 sessions, H1 only. Per account pick (a) the most H1 6-month $ a month after fees, (b) the most among
   books with >= 5 trades a week (H1 plain stream under that rule).
4. Report the picks UNTOUCHED (2,000 paths) on H1, Jul-Oct 2026 and 2021-25, plus model fills, vs today's setup
   (Builder 50K = LIT alone; Builder 25K = ATLAS alone; Rapid = LIT + ATLAS lanes).

## Multiple testing
N = grid cells tried + books screened + account rows tried. Test of each pick: one-sided paired t on the H1 real days of
(book daily $ - today's setup daily $) at $250 a trade; Bonferroni needs p < 0.05 / N. Also a White reality check
(5-day block bootstrap, max-t over every screened book). Out-of-sample Jul-Oct and 2021-25 decide whether to trust it.

## Amendment (written after the stage-2 screen printed its top 10, before any account-stage number)
The H1 screen's top books are all built on grid cells picked on H1 (tds, NA, cam), which lose money in Jul-Oct and 2021-25 on
their own (stage-1 table). The main pick stays exactly as above. A SECOND pool is added and picked by the same H1-only rules:
books made only of the 11 fixed-rule lanes (Z, A, E, M, S, B, P, H, T, O, W: no cell chosen by this study). Top 15 by H1 $
and top 10 among >= 5 trades a week go to the account stage; picks reported side by side. Its books are already inside the
114,506 screened, so N does not grow beyond the extra account rows.
