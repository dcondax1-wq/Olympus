---
title: Zlarior ideas night 2 (2026-11-18b) - the two live evals together - zombie-eval rule, staggered size, and an audit of the other angles
family: risk
date: 2026-11-18
status: rejected - nothing passes, Zlarior stays as it is. ATLAS's zombie-eval rule on Zlarior's evals makes +$57 / +$51 a month for the pair only by killing evals faster (2-week fails 50K 4.9 -> 10.4% / 3.1 -> 6.9%, 25K 0 -> 8.1% / 0 -> 8.3%); staggered full / half size across the two evals costs -$80 / -$49 a month and slows both passes. Every other angle on the list was already tested.
summary: Zlarior trades two MFFU evals on the same signals - the Builder 50K from its hole ($1,025 room, $3,807 to go) and the fresh Builder 25K #2. New tool tools/money/lit_two_evals.py runs both on ONE Monte Carlo (same 5-session-block paths, 1,000 per span, live sizing = engine/sizing.lit_qty, costs in; base = builder25k_eval / builder_levers exactly). Two pre-declared ideas, one version each - (1) ATLAS's approved zombie-eval rule ported to Zlarior (1-micro last bullet at 80% of the room + give up under $200) - seats +$57 / +$51 a month for the pair, but both evals die together within 20 sessions 16.3% / 14.5% of the time (today 0.4% / 0.3%), 25K 60-session fails 2.6 -> 22.4% / 1.7 -> 23.1%; Lab eval path H1 -$114, 2 trades changed - rejected. (2) Stagger - the evals alternate full / half size on each signal - pair -$80 / -$49 a month, 25K 2-week pass 47.6 -> 31.2% / 47.2 -> 31.8%, first payout 4 sessions later; Lab LIT size -$1,391 / -$1,400 a month - rejected. Today the two evals almost never die together (0.3-0.4% within a month); the joint risk is waiting, not failing. Reference (a purchase, not a rule) - a fresh 50K next to the hole, re-measured from today - +$50 / +$54 a month for the 50K after its $91.80. ES confirmation, overnight range, gap size, prior-day structure, weekday x session, news, early closes and entry timing were all tested before (sources listed); no Lab cells spent on them.
runs: none (research/lab/lit_two_evals.json; ZEUS Lab lit_idea lit_eval_zombie, lit_two_eval_stagger in research/lab/zeus_lab/registry.json)
---

# Zlarior ideas, night 2 (2026-11-18b): the two live evals together

## For the owner (one minute)

**Nothing passes. Zlarior stays exactly as it is ($0 change). No Decide card proposal.**

| Idea (one version each) | Both evals, $ a month Jan-Jun / Jul-Oct (today $1,084 / $1,007) | Fails within 2 weeks, 50K / 25K, Jan-Jun and Jul-Oct (today 4.9% / 0% and 3.1% / 0%) | Verdict |
|---|---:|---|---|
| ATLAS's "zombie" rule on both evals: 1 micro when the room is too small, give up under $200 | $1,141 / $1,058 (+$57 / +$51) | 10.4% / 8.1% and 6.9% / 8.3% | Rejected: the extra money comes from killing evals faster |
| Stagger: the two evals take turns, one full size and one half size, on each signal | $1,004 / $958 (-$80 / -$49) | about the same | Rejected: both evals pass much slower |

In plain words:

- **Your worry is already handled.** With today's 40% sizing the two evals almost never die together: about **1 in 300
  within a month** (20 trading days) and 1 in 40-70 within 3 months. A losing streak makes them *wait* (the 25K skips
  trades it has no room for), it does not kill them.
- **ATLAS's zombie rule** (its one keeper) would make about $50-57 a month more for the pair, but only because it turns
  waiting evals into dead ones and buys fresh ones: about **1 in 12 fresh 25K evals would die in its first 2 weeks**
  (today none), and both evals would die together 14-16% of the time within a month. You chose 40% for fewer failed
  evals, so this goes the wrong way.
- **Staggering** just makes each eval smaller half the time. The 25K's chance to pass in 2 weeks drops from 48% to 31%,
  the first payout comes about 4 trading days later, and "both die together" barely moves (it is already tiny).
- **Where your two evals stand today:** the 25K #2 passes within 2 weeks about half the time (48% / 47%) and
  eventually 83-87% of the time; the 50K hole is the slow one: 28% / 21% within 2 weeks, about 1 in 4 dies before it
  passes. First payout from either one: about **Jan 22** (Zlarior alone on the funded accounts).
- The one thing that speeds up the 50K is not a rule but a purchase you were already asked about on 11-16: **a fresh
  50K eval next to the hole** (both trade, the first 50K pass is kept). Re-measured from today's hole: +$50 / +$54 a
  month for the 50K after its $91.80, its first payout about 6-7 trading days sooner. It is a buy, not a Zlarior change,
  so it is not on the Decide card; your call with the $150-a-round budget.
- **Every other angle** (ES confirmation, overnight range, gap size, prior-day structure, weekday x session, news, early
  closes, entry timing) was already tested in earlier write-ups (section 4). Running them again would only raise the
  Lab's bar for a real new idea (55 tests so far: each needs p <= 0.0036 in both halves).

## 1. What was tested and how

- **Checked first:** CLAUDE.md, `docs/TESTED_AND_REJECTED.md`, `research/BACKLOG.md` (the adopt bar),
  `zeus-lab-lit-ideas-2026-11-18.md` (10 rejected, nearest miss London build-up x1.25), `eval-game.md` ("a second
  account only speeds things up if it trades differently ... not part of this study"), `lit-risk-money.md` (staggered
  START dates), `builder-levers-2026-11-16.md`, `builder25k-eval-sizing-2026-11-17.md`, `2026-11-15-atlas-deep.md`
  (the zombie-eval rule). Staggered SIZING across two live evals and the zombie rule on Zlarior were never tested.
- **New tool `tools/money/lit_two_evals.py`** (paper research; writes `research/lab/lit_two_evals.json`):
  - Z50 = the Builder 50K from today's hole ($49,192.78, floor $48,168.20: $1,025 room, $3,807 to go, session 23), the
    live two_week sizing (40% of the room to session 80, then safe_eval 60%); N25 = the fresh Builder 25K #2 on the bot's
    own `mffu_builder_25k` preset (the same 40% / 80 / 60% rule).
  - Both on the SAME paths (`tools/uprisk.mc_paths`, 5-session blocks, 1,000 per span, seeds 7 / 23 as builder-levers),
    the stored live LIT trades (run lit_live), $1.90 a micro + 1 tick, MFFU EOD trailing floor, lock, soft daily loss.
  - `check`: the base reproduces `tools/money/builder25k_eval.py` (fresh 25K) and `builder_levers.GEv` (the 50K hole)
    exactly on the same paths.
  - Evals from today: one eval each, 60 sessions, no re-buy. Seats: eval -> 2 sessions paperwork -> funded (LIT alone,
    today's UP50 / UP25 funded rules) -> a fresh eval after a fail / give-up ($91.80 / $63), 126 sessions (6 months).
    "Fail" includes an eval given up for lack of room ($200 on the 50K as in every earlier study; $100 on the 25K = its
    preset's min_room).
- **The two ideas, fixed before any result (no grid, one version each):**
  1. **Zombie-eval rule** (`lit_eval_zombie`): when the live sizing says 0 micros only because 1 micro does not fit the
     room share, take 1 micro if its full stop-out (stop + 2 ticks + $1.90) fits 80% of the room, then the soft daily
     loss guard; an eval with under $200 of room is given up. ATLAS's own functions (`engine/account_b.last_bullet`,
     `dll_guard`) and ATLAS's values (0.8, $200), nothing tuned.
  2. **Stagger** (`lit_two_eval_stagger`): on the 1st, 3rd, 5th ... LIT signal the 50K takes its normal size and the
     25K half of its normal size (the engine's own multiplier path, rounded down, at least 1 micro, every live cap after
     it); on the 2nd, 4th ... the other way round. Funded accounts unchanged.
- **The adopt bar** (BACKLOG + CLAUDE.md, fixed before the run): in BOTH 2026 halves the pair's 6-month $ a month after
  fees higher, the first payout not later, and per eval the 2-week pass not lower and the 2-week fail not more than
  1 point higher; trades / week, PF, net $, $ / month and max DD shown at the LIT size and on the Lab's eval path;
  2021-25 shown, never a gate.
- **ZEUS Lab:** both registered as kind `lit_idea` (`tools/lit_lab_ideas.py`: new eval idea `last_bullet` with
  `eval_hook()`, which runs the Lab's eval path with the rule, and size idea `stagger`; `tools/zeus_lab.py` wraps the
  lit_idea evaluation in that hook). `python -X utf8 tools/lit_lab_ideas.py check`: options off = the 631 live trades,
  and the eval runner with the rule off = `tools/lit_edge.run_eval_m` on every 2026 eval start. Full Lab run: both
  Rejected, live files untouched.

## 2. Numbers

### 2a. The trades and the Lab's eval path (H1 = Jan-Jun 2026 pick / H2 = Jul-Oct 2026 check)

The zombie rule does not change a trade, so the LIT size rule is today's exactly. Stagger is shown from the 50K's side
(every 2nd signal at x0.5). Eval path = the Lab's fresh MFFU 50K, back-to-back 2-week evals, live two_week sizing.

| | Trades / week | PF | Net $ | $ / month | Max DD | 2-week pass / fail |
|---|---|---|---|---|---|---|
| Today, LIT size rule | 3.12 / 2.56 | 4.98 / 2.91 | +$33,901 / +$9,919 | $5,562 / $2,670 | -$2,196 / -$1,396 | - |
| Zombie, LIT size rule | 3.12 / 2.56 (same trades) | 4.98 / 2.91 | +$33,901 / +$9,919 | $5,562 / $2,670 | -$2,196 / -$1,396 | - |
| Stagger, LIT size rule | 3.12 / 2.56 | 4.56 / 2.11 | +$25,421 / +$4,715 | $4,171 / $1,270 | -$1,901 / -$1,100 | - |
| Today, eval path | 3.05 / 2.56 | 4.25 / 2.26 | +$33,663 / +$11,735 | $5,523 / $3,159 | -$2,491 / -$2,693 | 44.5 / 0.0 · 39.1 / 0.0 |
| Zombie, eval path | 3.12 / 2.56 | 4.21 / 2.26 | +$33,549 / +$11,735 | $5,504 / $3,159 | -$2,491 / -$2,693 | 44.5 / **2.5** · 39.1 / 0.0 |
| Stagger, eval path | 3.09 / 2.56 | 3.55 / 1.99 | +$23,615 / +$7,685 | $3,874 / $2,069 | -$2,767 / -$2,129 | **36.1** / 0.0 · **21.7** / 0.0 |

2021-25 (reference, LIT size): today PF 1.01, +$1,265 ($25 a month); stagger PF 0.88, -$9,404 (-$184 a month).
Lab verdicts: zombie "too few trades changed (2 in Jan-Jun, 0 in Jul-Oct); Jan-Jun -$114 on the eval path; 2-week
fails +2.5 pts"; stagger "-$8,480 / -$5,204 at the LIT size, -$10,048 / -$4,050 on the eval path". On a FRESH 50K the
last bullet almost never fires (2 trades in 2026); it matters on low-room evals like today's two, below.

### 2b. The two live evals from today (one eval each, 60 sessions; H1-like market · H2-like market)

| | Today | Zombie rule | Stagger |
|---|---|---|---|
| 50K hole: pass / fail within 2 weeks | 28.0 / 4.9 · 20.7 / 3.1 | 28.0 / **10.4** · 20.7 / **6.9** | **16.8** / 4.6 · **13.7** / 3.1 |
| 50K: pass / fail in 60 sessions, median sessions to pass | 72.0 / 24.8, 14 · 71.0 / 23.8, 16 | 69.2 / 29.5, 13 · 70.6 / 26.5, 16 | 71.0 / 23.3, 20 · 68.5 / 23.1, 20 |
| 25K #2: pass / fail within 2 weeks | 47.6 / 0.0 · 47.2 / 0.0 | 47.5 / **8.1** · 47.9 / **8.3** | **31.2** / 0.2 · **31.8** / 0.0 |
| 25K: pass / fail / still open in 60 sessions, median | 87.3 / 2.6 / 10.1, 9 · 82.8 / 1.7 / 15.5, 8 | 77.3 / 22.4 / 0.3, 8 · 76.2 / 23.1 / 0.7, 7 | 83.4 / 2.1 / 14.5, 14 · 82.9 / 1.4 / 15.7, 14 |
| 25K signals skipped (1 micro does not fit 40% of the room) | 21.5% · 30.7% | 4.0% · 5.2% | 17.0% · 22.4% |
| Both evals dead within 20 / 60 sessions | 0.4 / 2.6 · 0.3 / 1.4 | **16.3 / 21.3** · **14.5 / 20.5** | 0.6 / 1.8 · 0.2 / 1.3 |
| At least one passed within 2 weeks | 47.6 · 47.2 | 47.5 · 47.9 | 37.8 · 34.5 |
| Neither passed in 60 sessions | 12.7 · 15.9 | 21.6 · 21.5 | 13.7 · 16.0 |
| 2021-25-like: 50K / 25K 2-week fail, both dead in 60 | 5.6 / 0.0, 31.3 | 8.4 / 7.8, 67.6 | 5.5 / 0.0, 29.1 |

### 2c. Six months of both seats (eval -> funded LIT alone -> re-buy; $ to you after fees)

| | Today | Zombie rule | Stagger | Reference: + a fresh 50K now ($91.80) |
|---|---|---|---|---|
| 50K seat $ / month | $728 · $699 | $756 · $712 | $671 · $664 | $778 · $753 |
| 25K seat $ / month | $357 · $308 | $385 · $347 | $333 · $294 | $357 · $308 |
| **Both $ / month** (worst 10% of runs) | **$1,084** ($236) · **$1,007** ($126) | $1,141 ($318) · $1,058 ($215) | $1,004 ($133) · $958 ($104) | $1,135 ($251) · $1,061 ($209) |
| First payout, sessions: 50K / 25K / either | 53 / 45 / 45 · 51 / 44 / 45 | 51 / 44 / 44 · 50 / 44 / 44 | 59 / 50 / 49 · 57 / 49.5 / 49 | 47 / 45 / 44 · 44 / 44 / 44 |
| First payout of either (date, from 2026-11-19) | Jan 22 · Jan 22 | Jan 21 · Jan 21 | Jan 28 · Jan 28 | Jan 21 · Jan 21 |
| No payout on either in 6 months | 6.4% · 8.3% | 5.3% · 6.5% | 6.7% · 9.7% | 6.0% · 8.2% |
| 2021-25-like, both $ / month | -$6 | -$13 | -$10 | -$10 |

**Verdicts against the bar:**

- **Zombie: rejected.** More $ in both halves (+$57 / +$51 a month, worst 10% better too) and the first payout one
  session sooner, but the 2-week fail rises far beyond +1 point on both evals in both halves (50K +5.5 / +3.8 pts, 25K
  +8.1 / +8.3 pts), and the two evals die *together* 14-16% of the time within 20 sessions instead of 0.3-0.4%: the
  opposite of what was asked. 2021-25 is worse (-$13 vs -$6 a month, both dead in 60 sessions 67.6% vs 31.3%). The
  gain is "re-buy instead of wait", the same family as the Rapid give-up / re-buy levers (rapid-levers-2026-11-16:
  +$12-104 a month = noise, 2021-25 worse).
- **Stagger: rejected.** Less $ in both halves (-$80 / -$49), first payout 4 sessions later, 2-week pass 25K 47.6 ->
  31.2% / 47.2 -> 31.8%, 50K 28.0 -> 16.8% / 20.7 -> 13.7%. "Both dead within 60 sessions" falls only 2.6 -> 1.8% /
  1.4 -> 1.3% (within 20 sessions it rises 0.4 -> 0.6% in H1).
- **Reference (not an idea, not a rule):** the fresh 50K next to the hole beats today in both halves (+$50 / +$54 a
  month for the 50K, first 50K payout 53 -> 47 / 51 -> 44 sessions, 2021-25 -$9 vs -$5 a month = the extra fee). It is
  builder-levers lever 1 (2026-11-16: +$38 / +$45 then, room $1,145): the deeper hole makes it a bit stronger.
  MFFU funds one Builder 50K, so the first 50K pass is kept (`ask-mffu-parallel` on the Decide card covers asking MFFU
  in writing).

**Why the zombie rule pays and still fails the bar (explanation only, its two parts apart; not candidates):**

| Part | Both $ / month | 50K 2-week fail | 25K 2-week fail | 25K fail in 60 | Both dead in 20 |
|---|---|---|---|---|---|
| last bullet only (25K give-up stays $100) | $1,136 · $1,052 | 10.4% · 6.9% | 2.2% · 2.2% | 14.7% · 15.0% | 7.3% · 8.4% |
| give-up $200 only (no last bullet) | $1,105 · $1,038 | 4.9% · 3.1% | 4.0% · 4.2% | 17.3% · 20.3% | 7.3% · 8.8% |

Both parts raise fails. The last bullet carries most of the 50K's gain (1-micro trades at $200-400 of room either
rescue the eval or end it); the give-up line carries most of the 25K's (a waiting 25K is re-bought for $63 and the
fresh one passes in a median 8-9 sessions). Waiting evals are slow money, but you asked for fewer failed evals, and a
fail is what the rule makes.

## 3. Why the two evals rarely die together today

- The live eval sizing risks at most 40% of what is left of the room, so each loss takes a share of a shrinking room:
  after 3-4 straight losses one micro of a typical 40-80 pt stop no longer fits and the eval **skips** instead of
  trading (25K: 21.5% / 30.7% of signals skipped). Skipping cannot reach the floor, so the eval waits for a narrow-stop
  winner. That is why the 25K has 0% fails in 2 weeks and 10-16% "still open" after 60 sessions.
- So a bad week leaves both evals small, not dead. What the two evals share is the waiting (neither passed in 60
  sessions 12.7% / 15.9%), not the failing.
- Any rule that makes a low-room eval trade more (the zombie rule) or trade less (stagger) moves money and pass speed
  the expected way: more risk = faster pass or faster death, less risk = slower. Two evals on the same signals add up;
  splitting the size between them cannot add money, only move it.

## 4. The other angles on the list: already tested (no cells spent)

| Angle | Where it was tested | What it found |
|---|---|---|
| ES confirmation / divergence | `lit-losses.md` (ES SMT skip / half / x1.5 when ES confirms), `lit-bias-discretion.md` (NQ-ES SMT bias), `2026-11-15-s2-edge.md` (NQ vs ES strength from 18:00), `lit-adv-audit-smt.md` | textbook SMT is backwards in 2026; skip / half lose a half; x1.5 is leverage (2-week fails 19.5%); strength = chance in Jul-Oct |
| Overnight range | learn loop (x1.25 after a tight Asia range), `unexpected-factors.md` (overnight size), `edge-health-2026-11-17.md` (overnight share) | rejected / chance |
| Gap size | `unexpected-factors.md` (gap size), `cross-market-context.md` (big gaps x1.25: 2021-25 no better), Lab `lit_gap_against_x0.75` | rejected |
| Prior-day structure | `2026-11-04_lit_ideas_night.md` (inside / outside yesterday, prior day / week with the trade: p 0.06 / 0.45), `lit-losses.md` (day after a big day, outside day), Lab NR7 x1.25 | none beats shuffled size in both halves |
| Weekday x session | `calendar-effects.md`, `2026-11-04_lit_ideas_night.md`, `lit-edge-2026-10-30.md` (H1-mined weekday / session) | no weekday beats shuffled size |
| News | Lab news exit / breakeven (night-labx), `lit-losses.md` (CPI week, news day half), `lit-edge` news tilt | only 1 of 120 2026 trades entered within an hour before a big release (2026-05-08 08:23, 7 min before the jobs report, stopped: -$482): not testable |
| Early-close days | `2026-11-15-s2-edge.md` (holiday-thin days x0.5 / x0.75 / skip), the holiday replay | none passes; the flat-before-halt safety is already live |
| Entry timing (stop rule kept) | `lit-entry-precision.md` (43), `lit-smart-entries-2026-11-17.md` (31), `lit-ablation.md` (cisd1m 22, now live) | today's entry is best |

Two structural facts explain why these keep failing: on the eval path the "one winner passes" sizing hits its caps, so
a size-up adds little and a cut costs passes (`lit-bias-discretion.md`: 3 of 279 size tilts better in both halves);
and the 57 entry facts point the same way in both halves no more often than shuffled outcomes (`lit-trade-intel.md`:
8 of 50 vs 13.4 by chance).

## 5. Read this honestly

- These are Monte Carlo paths from the 2026 halves: 1,000 paths each, one seed pair; gaps under about 1 session, 1 point
  or $20 a month are noise. H2 has only 40 LIT trades.
- 2026 is a good LIT year; in a 2021-25-like market both evals pay about $0 a month whatever the rule (-$6 to -$13).
- The funded stage is Zlarior alone on both accounts (today's wiring). With ATLAS added on the funded accounts (Decide
  card `atlas-on-50k-funded`, `zlarior-funded25`) every row pays more, but the eval-stage comparison is the same.
- The 50K's $200 give-up line is a research assumption from earlier studies (the live bot has no give-up; you decide
  when to buy a new eval). With no give-up at all the 50K hole would show fewer fails and more "still open".
- Nothing live changed: no `live_model*.json`, preset, `engine/` file or live code path. The Lab run reported its
  live-file hash check untouched.

## 6. Files

- `tools/money/lit_two_evals.py` (new): `python -X utf8 tools/money/lit_two_evals.py [--n 1000] [--diag]`, `... check`.
- `research/lab/lit_two_evals.json`: every number above (rows per span x variant; `--diag` adds the explanation and
  reference rows).
- `tools/lit_lab_ideas.py`: eval idea `last_bullet` (`run_eval_zombie`, `eval_hook`, `eval_hits`) and size idea
  `stagger`; `check` covers both.
- `tools/zeus_lab.py`: the lit_idea evaluation runs inside `eval_hook()` (no change for every other idea).
- `research/lab/zeus_lab/registry.json`: `lit_eval_zombie`, `lit_two_eval_stagger` (55 cells now, p needed 0.00364).
