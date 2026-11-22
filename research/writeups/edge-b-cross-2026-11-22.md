---
title: Edge hunt lane B (2026-11-22) - cross-asset NQ triggers (dealer gamma, vol term structure, ES/NQ relative strength)
family: other
date: 2026-11-22
status: no winner, nothing to adopt, no decide card
summary: 128 pre-logged variants on CME NQ1! 5m (+ES1! 5m from 2025-04). The gamma day-type switch (negative gamma = trend, positive gamma = fade) fails in both 2026 halves and 2021-24. VIX term structure and VXN-VIX spread do not predict next-day direction. ES/NQ relative strength at a sweep loses in every variant. One paper lead holds in all four spans but with the OPPOSITE sign to the hypothesis, t < 1.2, and about $230 a month.
---

## Headline (honest)

**No new edge.** The idea the lane was built on (negative-gamma days trend, positive-gamma days mean-revert, switch the entry by gamma) does not work here:
the literal switch loses in H2 (PF 0.87) and in 2021-24 (PF 0.92, -$11.9k). Prior-day GEX does predict the **size of the next day's range**
(2021-25 mean RTH range 198 bps on the lowest-third gamma days vs 105 bps on the highest third; same order in H1 and H2), but that is volatility
clustering, and it does not tell you which way to trade.

Setup notes: no `strategy-test` SKILL.md and no `docs/ACCOUNT_RULES.md` exist in this repo (`.claude/skills` holds only `land-helper`), so the rules came from CLAUDE.md,
`tools/div_search.py` / `tools/e2_new_strats.py` (engine, costs: $1.90 a micro round trip, 1 tick on every fill, size = $500 / (stop x $2 + $1.90), 1-40 micros, 5m RTH) and `research/writeups/mffu-rules.md`.

## Data limits (where things stop)
- NQ 5m 2021-11 to 2026-10-16 used (the file runs later, GEX / VIX / VXN / ES all end 2026-10-16). H1 = 2026 Jan-Jun (the only pick span), H2 = Jul 1 - Oct 16, 2021-24, 2025.
- GEX (SqueezeMetrics, S&P 500) 2011+, **previous day's print only** (known after the close); VIX/VXN prior close; same for the 1-year percentile ranks (trailing, no look-ahead).
- CBOE VIX3M/VIX9D end **2026-09-17** (term-structure cells have 5 trades in H2: untestable there).
- ES 5m / 1d only from **2025-04-14**: family 3 has H1, H2 and 2025 Apr-Dec; **2021-24 cannot be tested**, so no family-3 variant could ever meet the "positive 2021-25" rule.

## Variant count (every one logged in `research/edge_hunt/b/*.json`)
- Family 1/2 day-type grid: 8 entries (4 opening-range trend breaks: stop far OR side / OR midpoint x exit EOD / 2R; 4 fades: failed OR break to mid / 2R, prior-day high-low sweep to VWAP / 2R)
  x (unconditional + 3 features [GEX pct, VXN-VIX spread pct, VIX/VIX3M pct] x 2 cuts [50, 33/67] x 2 sides) = **104 cells**, + **6 switches** (best H1 trend + best H1 fade per feature/cut).
- Family 3: 8 (PDH/PDL sweep + relative strength) + 10 (rolling 12-bar sweep, 2 signs x 2 z x 2 targets + 2 controls) = **18**. Total **128**.
- Daily screen (no trading): 6 features x 3 buckets x 3 spans (`screen.json`).

## Results

**Family 2, direction.** No feature predicts the next day's direction: the sign of the bucket means flips between H1, H2 and 2021-25 for VXN-VIX spread, VIX change, VIX/VIX3M, VIX9D/VIX (noise is about +-20-30 bps on 20-60 days). Rejected.
Range does track vol (VIX high, backwardation, low gamma => wider range) but that is what the VIX already says.

**Family 1, the switch.** Trend entry on low gamma loses in H2 (ORB far stop, GEX < median: H1 +$3.9k PF 1.63, H2 -$3.8k PF 0.26). Fade on high gamma loses 2021-24 (-$20k). Best-by-H1 switches:

| Switch (picked on H1) | H1 PF / $ | H2 PF / $ | 2025 PF / $ | 2021-24 PF / $ |
|---|---|---|---|---|
| GEX < median: ORB far-stop trend; else failed-OR-break fade | 1.52 / +8.1k | 0.87 / -1.8k | 0.98 / -0.8k | 0.92 / -11.9k |
| GEX 33/67 version | 1.49 / +5.3k | 0.89 / -1.0k | 1.00 / 0 | 0.87 / -12.8k |
| VXN-VIX spread version (2) | 0.79-0.88 / loses | 0.5 / loses | | loses |
| VIX/VIX3M version (2) | 1.3 / +4-7.6k | 0.6-0.9 / loses | 1.2 / | ~1.0 |

**Family 3, ES/NQ relative strength at a sweep.** At the prior-day sweep there are 1-6 trades per half-year (no sample). At a rolling 12-bar sweep (about 1.3-4.6 a week): every variant loses in H1 or H2 (best "lag z 0.5, VWAP target": H1 -$4.3k, H2 +$6.3k, 2025 -$3.0k; "lead z 0.5, VWAP": H1 +$3.7k, H2 -$5.0k). The unfiltered control (sweeps) is also negative in 2 of 3 spans, so relative strength adds no stable lift. Read why the SMT trigger failed first (`lit-adv-audit-smt.md`, E2 `rs` at 10:00): same result here with a continuous strength measure.

**The only cell that holds everywhere (paper lead G1):** ORB trend (first 5m close beyond the 09:30-10:00 range, 10:00-13:00, stop 1 tick beyond the far side, hold to 15:55) taken only on days whose **prior GEX is at or above its 1-year median**. This is the OPPOSITE of the gamma hypothesis (trend on positive gamma).

| G1 | trades/wk | win % | PF | net $ | $/month (50K, $500 risk) | max DD |
|---|---|---|---|---|---|---|
| H1 2026 | 1.26 | 50 | 1.35 | +1,334 | +228 | -1,100 |
| H2 Jul-Oct16 | 1.48 | 52 | 1.31 | +1,042 | +219 | -1,761 |
| 2025 | 2.53 | 49 | 1.10 | +1,973 | +168 | -4,380 |
| 2021-24 | 2.48 | 50 | 1.14 | +9,653 | +254 | -6,493 |

Corr with LIT daily P&L: +0.05 (2026), -0.05 (2021-25). t-statistic 0.4-1.1 in every span. MFFU 50K eval (block bootstrap, owner eval sizing 0.4 x room): pass within 10 sessions 1.6 / 1.3 / 5.9 / 4.8 %, within 60 sessions 20 / 20 / 25 / 23 %, median 19-31 sessions
(the "fail 0%" is an artefact of sizing by remaining room: it shrinks as it loses; it is slow, not safe). Not an eval vehicle: ~$230 a month at $500 risk against LIT's $5.5k.
Why it is not a winner: chosen from 128 cells, wrong sign vs the stated hypothesis (so it is a post-hoc finding), placebo: random half of the same ORB days holds in all four spans 2.4% of the time and 7.8% of the ones that pass the H1 gate (p ~ 0.08), t < 1.2. Plain ORB without the filter: +$5.2k PF 1.53 in H1, -$2.8k PF 0.67 in H2 (the known dead ORB).

## Tried and failed (all of it)
1. Gamma switch (low GEX trend / high GEX fade), 2 cuts. 2. VXN-VIX spread day-type switch. 3. VIX/VIX3M day-type switch. 4-6. Same three as filters on each of 8 entries. 7. Daily direction from spread / VIX change / term structure / VIX9D (screen). 8. PDH/PDL sweep + ES relative strength (8). 9. Rolling-sweep + ES relative strength, lag and lead, z 0.5 / 1.0 (8) + 2 controls.

## Next (recommend only)
Nothing to switch on, no decide card. If anyone revisits: G1 as a **funded add-on** at 3-4% of room (like NA in `diversifier-search.md`) needs a placebo p < 0.05 first; the 2021-24 ES history does not exist, so ES ideas wait for more data (a 2027 re-check).

Code: `research/edge_hunt/b/` (`feat.py` features, `screen.py`, `run_b.py` grid, `holds_b.py`, `fam3_b.py`, `fam3b_b.py`, `final_b.py`; outputs `*.json`). Smoke: 7/8 green; `tests.test_zenith_mode` fails only because Playwright is not installed in this sandbox (unrelated to this change).
