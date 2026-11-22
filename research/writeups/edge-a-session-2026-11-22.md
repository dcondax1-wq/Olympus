# Edge hunt lane A: NQ RTH session structure (2026-11-22)

**Headline: no winner. 14 variants tried, 0 positive in both 2026 halves.** Every trend-following variant (ORB, IB extension,
gap-and-go, first-hour drive) made money Jan-Jun 2026 and lost it Jul-Oct; the two failed-IB-break fades did the exact opposite.
That is a regime flip, not an edge: nothing beats costs in both halves, so nothing is recommended and no decide card was made.

Paper research only. No live file touched. Code: `research/edge_hunt/a/session_edges.py` (numbers: `session_edges.json`).

## How it was run
- Engine: the repo's 5m execution (`tools/div_search.py walk`, same as E2 / third-strategy): entry at the next 5m open + 1 tick,
  stop fills 1 tick through, target needs a trade-through, stop+target in one bar = stop, flat 15:55, $1.90 a micro round trip.
  Stops 1 tick beyond a structural extreme (a stop under 8 pts is widened to 8). Size from the stop at **$500 risk a trade**
  (the repo's standard for new edges; not LIT's $800 / two-week eval sizing). One target (2R, or the IB midpoint for B4). One trade a day.
- Data: `data/NQ_5m.csv` 2021-10 -> 2026-10-16, NQ futures only (1m exists only from 2026-01, so 5m is used for all spans). ES / VIX
  not needed by any variant.
- Rules: the pick rule was set before the run (H1 2026 only: n >= 12, PF >= 1.2, best $), then H2 (Jul-Oct 16, untouched) and
  2021-25 read. A winner must be positive in both halves AND 2021-25, 2-4 trades/week.
- LIT correlation: daily P&L vs `research/lab/backtest_live.json` (LIT live run).
- MFFU: one trade a day at $500 risk is inside the $1,000 soft daily loss; no best-day rule in the eval.

## All 14 variants (H1 pick span / H2 check / 2021-25 reference; corr = daily P&L vs LIT in the same three spans)
| variant | 2026 Jan-Jun | 2026 Jul-Oct | 2021-25 | corr LIT H1 / H2 / 21-25 | holds all 3 |
|---|---|---|---|---|---|
| A5_orb5 | 4.37/wk, 41.5%, PF 1.04, $910 ($155/mo), DD $-7,649 | 4.52/wk, 35.8%, PF 0.88, $-2,353 ($-494/mo), DD $-4,507 | 4.64/wk, 39.4%, PF 1.1, $26,459 ($531/mo), DD $-12,884 | 0.074 / -0.068 / -0.02 | no |
| A15_orb15 | 3.96/wk, 48.6%, PF 1.18, $3,208 ($548/mo), DD $-3,595 | 3.62/wk, 38.2%, PF 0.66, $-4,980 ($-1,046/mo), DD $-5,801 | 4.5/wk, 45.9%, PF 1.19, $36,227 ($727/mo), DD $-5,432 | 0.113 / -0.099 / -0.071 | no |
| A30_orb30 | 3.11/wk, 54.8%, PF 1.4, $4,023 ($687/mo), DD $-1,907 | 2.86/wk, 43.3%, PF 0.81, $-1,858 ($-390/mo), DD $-4,047 | 4.03/wk, 50.1%, PF 1.12, $16,657 ($334/mo), DD $-4,419 | 0.065 / -0.119 / -0.045 | no |
| B1_ibx_narrow | 0.59/wk, 62.5%, PF 1.37, $521 ($89/mo), DD $-529 | 0.71/wk, 33.3%, PF 0.44, $-1,068 ($-224/mo), DD $-1,136 | 1.38/wk, 53.1%, PF 1.1, $4,285 ($86/mo), DD $-5,032 | -0.053 / 0.021 / -0.04 | no |
| B2_ibx_all | 2.22/wk, 55.0%, PF 1.41, $2,099 ($358/mo), DD $-815 | 2.05/wk, 39.5%, PF 0.59, $-2,055 ($-432/mo), DD $-2,801 | 3.66/wk, 54.3%, PF 1.13, $11,435 ($230/mo), DD $-5,239 | 0.055 / -0.039 / -0.057 | no |
| B3_ibfail_2R | 2.22/wk, 33.3%, PF 0.93, $-1,320 ($-225/mo), DD $-6,878 | 1.9/wk, 47.5%, PF 1.76, $6,519 ($1,369/mo), DD $-2,329 | 2.02/wk, 33.6%, PF 0.9, $-14,415 ($-289/mo), DD $-22,766 | 0.094 / 0.107 / -0.016 | no |
| B4_ibfail_mid | 1.67/wk, 31.1%, PF 0.81, $-2,669 ($-456/mo), DD $-4,769 | 1.62/wk, 41.2%, PF 1.7, $5,707 ($1,198/mo), DD $-1,894 | 1.73/wk, 32.9%, PF 0.97, $-3,203 ($-64/mo), DD $-16,191 | 0.282 / 0.086 / -0.018 | no |
| C1_on_sweep_fade | 2.89/wk, 35.9%, PF 1.02, $404 ($69/mo), DD $-4,142 | 2.86/wk, 26.7%, PF 0.65, $-6,419 ($-1,348/mo), DD $-8,539 | 2.95/wk, 31.8%, PF 0.84, $-32,309 ($-649/mo), DD $-38,702 | 0.01 / 0.103 / -0.02 | no |
| C2_gap_go_on | 0 trades | 0 trades | 0.0/wk, 0.0%, PF 0.0, $-508 ($-10/mo), DD $-508 | - / - / 0.0 | no |
| C3_gap_go_big | 0 trades | 0 trades | 0 trades | - / - / - | no |
| T1_drive | 1.44/wk, 35.9%, PF 0.64, $-3,286 ($-561/mo), DD $-3,933 | 1.14/wk, 37.5%, PF 0.71, $-1,750 ($-367/mo), DD $-2,714 | 1.2/wk, 48.3%, PF 1.46, $24,581 ($493/mo), DD $-4,832 | -0.156 / -0.06 / -0.028 | no |
| T2_drive_strict | 0.22/wk, 33.3%, PF 0.96, $-57 ($-10/mo), DD $-924 | 0.19/wk, 25.0%, PF 0.44, $-482 ($-101/mo), DD $-864 | 0.26/wk, 53.4%, PF 1.63, $6,021 ($121/mo), DD $-1,821 | -0.076 / -0.017 / 0.014 | no |
| C2b_gap_go_outside_PDR | 1.04/wk, 46.4%, PF 1.32, $1,839 ($314/mo), DD $-1,410 | 0.95/wk, 20.0%, PF 0.37, $-3,907 ($-820/mo), DD $-4,339 | 0.86/wk, 42.1%, PF 1.19, $9,115 ($183/mo), DD $-5,273 | 0.202 / -0.119 / -0.022 | no |
| C3b_gap_go_big | 1.33/wk, 50.0%, PF 1.74, $5,189 ($886/mo), DD $-1,818 | 1.43/wk, 26.7%, PF 0.55, $-3,740 ($-785/mo), DD $-3,740 | 1.2/wk, 42.6%, PF 1.21, $13,489 ($271/mo), DD $-5,731 | 0.124 / -0.14 / 0.016 | no |

C2 / C3 (open outside the overnight range) traded ~never: the overnight range includes the 09:25 bar, so the open is almost never
outside it. That was my definition error; I logged it and added C2b / C3b (open outside the prior-day range / gap >= 0.25 x 14-day
range) as replacements. Count tried = 12 + 2 = 14. Chance twins (coin-flip direction, 20 seeds) are in the json: net swings of
$-3k to +$10k on H1 alone, so none of the H1 profits is distinguishable from luck at this n.

## Picks
- H1 pick (rule above): A30 (ORB 30 min, PF 1.40, $4,023, 3.1/wk). H2: PF 0.81, -$1,858. **Rejected.** Own 50K eval (target $3,000,
  trail $2,000, a start on every session): never passes in 10 sessions, fails 31% / 69% in 40 sessions on H1 / H2.
- Next in H1: B2 (IB extension, PF 1.41; H2 PF 0.59), C3b (gap-and-go >= 0.25 range, PF 1.74; H2 PF 0.55), A15 (H2 PF 0.66). All rejected.
- Opposite sign: B3 / B4 (failed IB break fade) lose H1 (-$1.3k / -$2.7k) and win H2 (+$6.5k / +$5.7k) but lose over 2021-25
  (-$14k / -$3k). Also rejected.
- T1 (first-hour drive) is the one with a long history: 2021-25 PF 1.46, +$24.6k, 1.2/wk, but 2026 loses in both halves (PF 0.64 / 0.71).

## Correlation with LIT
Daily correlation is ~0 for all of them (|corr| <= 0.28), because LIT trades one sweep a day and these trade the open / first hour.
The independence is real but there is nothing to diversify with: no variant makes money.

## Tried and failed (13 of 14 clear failures; C2 / C3 void)
ORB 5 / 15 / 30 min; IB extension (narrow and all); failed-IB-break fade (2R and to midpoint); ON-high/low sweep fade (H1 PF 1.02, H2 0.65,
2021-25 -$32k, overlaps the strategy-tree overnight roots); gap-and-go outside the prior-day range and by gap size; first-hour drive
(loose and strict). Strict drive T2 only has 6 / 4 trades in 2026.

## Honest read
1. Plain session breakouts were positive in 2021-25 (PF 1.1-1.2) and in Jan-Jun 2026, and flipped negative Jul-Oct 2026. If that regime
   persists, the failed-break fades (B3 / B4) are the mirror trade, but they lose over 2021-25 and the only reason to pick them is
   H2 hindsight. Switching sides on the half-year would be p-hacking, so it is **a lead for a future walk-forward test, not a finding.**
2. Costs are not the issue (stops 60-150 pts, 1-3 micros); the sign of the edge changes with the regime.
3. No change to LIT, ATLAS or BLITZ. Nothing to put in front of the owner.

## Process note
`.claude/skills/strategy-test/SKILL.md` and `docs/ACCOUNT_RULES.md` do not exist in this checkout, so I followed CLAUDE.md "Strategy
changes" (pick on Jan-Jun, check Jul-Oct, 2021-25, 2-4/week, costs in) and `docs/ADD_ACCOUNT.md` for MFFU rules. Several families the
brief called untested were partly in `docs/TESTED_AND_REJECTED.md` (ORB 2nd side, gap fade G1, strategy-tree overnight / OR roots);
the variants here are the new angles (IB, trend-day drive, gap-and-go, plain ORB on this engine as a control).
