---
title: ZEUS Lab - 10 new Zlarior (LIT) ideas, 2026-11-18
summary: Ten genuinely untested Zlarior ideas (time stop, NY-open exit / breakeven, news exit / breakeven, stall exit, breakeven on a close, NR7 size-up, London build-up size-up, 18:00 gap against size-down), one pre-declared version each, run through the ZEUS Lab's full proof (2026 Jan-Jun pick, Jul-Oct check, LIT size + live two_week eval path, costs in, 2-4 trades a week, sign-flip placebo under the many-tests bar). All 10 rejected; none goes to shadow; nothing live changed.
runs: tools/zeus_lab.py run --publish (night-labx); ideas in tools/lit_lab_ideas.py, registry research/lab/zeus_lab/registry.json
---

# ZEUS Lab: 10 new Zlarior ideas (2026-11-18)

## For the owner

| Idea (one version each) | Jan-Jun $/month | Jul-Oct $/month | Verdict |
|---|---:|---:|---|
| Time stop: out after 60 min without +1R | -$695 | -$945 | Rejected (kills slow winners) |
| Out before the NY open (09:29) if not at breakeven | -$317 | +$33 | Rejected (5 + 2 trades, loses H1) |
| Breakeven before the NY open if +0.5R | $0 | $0 | Rejected (changes nothing) |
| Out 2 min before big US news if not at breakeven | +$64 | $0 | Rejected (1 trade in 2026) |
| Breakeven 2 min before big news if +0.5R | $0 | $0 | Rejected (changes nothing) |
| After breakeven, out after 60 min with no new best price | -$1,516 | -$457 | Rejected |
| Breakeven only on a 1-min close at +1R | -$326 | $0 | Rejected |
| x1.25 the day after an NR7 (narrow day) | -$24 | -$11 | Rejected (eval +$66 / +$149, LIT size down) |
| x1.25 on London build-up sweeps (owner's A+ idea) | +$295 | +$14 | Rejected, nearest miss: eval H1 -$4 a month, 2-week pass 44.5 -> 41.2% |
| x0.75 when the 18:00 open gapped against the trade | -$408 | -$188 | Rejected |

$ = change vs today's Zlarior at the LIT size rule ($800 up to a 20-pt stop), costs in. Today: $5,562 / $2,670 a month
(Jan-Jun / Jul-Oct). **0 of 10 pass; nothing moves to shadow; Zlarior stays as it is.** What survives: nothing. The London
build-up size-up is the only one that made money in both halves at the LIT size, but it lost a little on the eval path in
Jan-Jun and lowered the 2-week pass rate, so the proof says no.

## What was tested and how

Each idea is one small, pre-declared change (no grid: each cell raises the Lab's many-tests bar for everything else; the run
had 53 cells, so a pass needed p <= 0.0038 in both halves). Ideas already in `docs/TESTED_AND_REJECTED.md` were discarded
first:

- **Discarded as already covered:** a second target leg / partial at 4R (partials, "2nd target", scale-outs at 2R / 3R:
  lit-losses, lit-adv-management, rule-native layer); skipping a level swept the day before (re-sweep `x_resweep`, old /
  many-times-touched level tilts); weekday / OpEx / month-end (calendar + S2 edge); a bigger 5m displacement body (walk-forward
  disp 0.7-0.9, displacement quality 1.5-3x, body > 1.3 / 1.5 ATR); the opposite sweep after a failed one (continuation / flip
  2nd trade, re-entry after a cut / BE); sweep volume (10 PVSRA vector filters). A volatility-scaled stop buffer was not run:
  the stop 1 tick beyond the sweep extreme is a hard rule (CLAUDE.md), and wider stops were rejected in lit-loss-learning.
- **Engine:** `tools/lit_lab_ideas.py` re-walks the 631 live LIT trades (run lit_live) after the fill with `manage_x` =
  `tools/lit_edge.manage` with options off (`check`: 0 of 631 differ) + the new exit options; size ideas give a multiplier.
  `tools/lit_edge.evaluate(U=...)` scores the LIT size rule, the live two_week eval path (room_f 0.4 to session 80) and the
  eval odds. New Lab kind `lit_idea` (tools/zeus_lab.py); the gap rule is a plain `lit_tilt` on the trade-intel fact `gap`.
- Decisions on closed bars, act at the next open - 1 tick (like the 15-minute check). News times: data/news/events.csv
  (high impact: CPI, jobs, PPI 08:30, FOMC 14:00 / 14:30); 2021-23 has FOMC only, so the 2021-25 news line is partial.

## Numbers (change vs today; LIT size net $ H1 / H2 / 2021-25, eval path net $ H1 / H2, trades changed H1 / H2)

| Experiment | LIT size | Eval path | Changed | 2-week pass H1 / H2 (today 44.5 / 39.1) | Why rejected |
|---|---|---|---|---|---|
| `lit_time_stop_60` | -$4,236 / -$3,512 / -$19,213 | -$8,420 / -$6,361 | 19 / 17 | 49.6 / 26.1 | loses both halves |
| `lit_ny_open_out` | -$1,932 / +$120 / -$5,119 | -$2,922 / +$399 | 5 / 2 | 43.7 / 39.1 | too few changed, loses H1 (one 6.5R target cut at -0.4R) |
| `lit_ny_open_be` | $0 / $0 / -$744 | $0 / $0 | 0 / 0 | same | no 2026 outcome changes (the 2 trades it moved reached +1R before coming back) |
| `lit_news_out` | +$392 / $0 / +$777 | +$110 / $0 | 1 / 0 | same | 3 trades in 2026 are open across a release; 1 changed |
| `lit_news_be` | $0 / $0 / $0 | $0 / $0 | 0 / 0 | same | no trade changes |
| `lit_stall_60` | -$9,237 / -$1,700 / -$1,463 | -$11,535 / -$3,876 | 18 / 7 | 19.3 / 39.1 | banks too early: LIT's targets come after 2-4 hours |
| `lit_be_on_close` | -$1,989 / $0 / +$6,241 | -$2,529 / $0 | 4 / 0 | same | loses H1, nothing in H2 (2021-25 5m-only: +$6.2k, a reference line only) |
| `lit_nr7_x1.25` | -$143 / -$44 / -$257 | +$404 / +$552 | 6 / 9 | same | LIT size down both halves |
| `lit_buildup_london_x1.25` | +$1,800 / +$50 / -$947 | -$25 / +$451 | 26 / 12 | 41.2 / 39.1 | eval H1 -$25, H1 max DD -$2,196 -> -$2,458, sign-flip p 0.15 / 0.51 (needs 0.0038) |
| `lit_gap_against_x0.75` | -$2,485 / -$700 / +$16 | -$6,274 / -$728 | 20 / 10 | 40.3 / 34.8 | loses both halves: gap-against trades are good trades |

Trades a week unchanged everywhere (3.12 / 2.56); no idea raised 2-week fails (0.0 / 0.0 at today's room 0.4).

## Read this honestly

- **Clock exits hurt Zlarior.** Every rule that closes a trade by the clock (60-min time stop, stall after breakeven, the NY
  open) loses Jan-Jun money; the targets need hours (half the target hits come after 2-4 hours). This confirms the
  2026-10-28 reversal-exit and loss-learning finding from a new angle.
- **The NY open and the news are not where Zlarior gets hurt.** Only 24 of the 2026 trades are open at 09:29 and only 3
  across a high-impact release; most London trades are already resolved or at breakeven by then. These rules are thin by
  nature (too few trades to ever be trusted).
- **The London build-up size-up is the one to keep an eye on** (LIT size +$295 / +$14 a month), but its Jul-Oct gain is $14
  a month and the sign-flip test says it could be luck. It stays in the Lab as Rejected and is re-tested every night on the
  new bars from the PC; if the newer weeks lift it, the Lab will move it to shadow by itself.
- Nothing changed live. `live_model*.json` untouched (Lab hash check: untouched = True).
