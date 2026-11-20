---
tags:
  - zeus/research
  - family/risk
  - verdict/adopt-candidate
  - bot/atlas
type: "research"
date: "2026-10-22"
status: "adopt-candidate (unchanged rules; built, OFF; paper / Sim first)"
source: "research/writeups/atlas.md"
aliases:
  - "ATLAS"
---

# ATLAS

> [!success] Verdict: adopt-candidate
> adopt-candidate (unchanged rules; built, OFF; paper / Sim first)

**Full title:** ATLAS - account B (EMA + MACD + S/R) tuned as a whole for the Builder 25K (nothing beats today; kept as is)

## Summary

Owner (2026-10-22) - LIT on the 50K eval, the new strategy now called ATLAS (account B - London EMA pullback + MACD sweep divergence + S/R NY reclaim) on a Builder 25K; "keep tweaking this strategy, make it ready to trade my other account". ATLAS was scored under the REAL account-B rules, now including the one the research lacked (no ATLAS entry while LIT has an ARMED setup the other way). With it, today's ATLAS on a Builder 25K passes 72.3% of evals within 2 weeks in 2026 H1 (0.0% fail, 5.0% stuck) and 43.5% in H2 (0.0 / 0.0), eval-path +$19,737 ($3,238/mo) and +$5,448 ($1,467/mo), about $1,840 paid out in the first 3 funded months (H1 starts), +$1,549 per $63 eval bought. 358 tweaks were tested (members, Asia slot, per-member size weights down AND up, priority, 25K sizing incl. room 40-60% / safe / hybrid / daily cap, entry windows, weekdays, VIX filters and VIX size, per-member exits, a latency-proof limit entry) and picked on H1, checked on H2. Only 5 different ones beat today in both halves, about what chance gives (3.1), and none is a plateau - the best, S/R entries only until 11:00, wins H1 only by skipping three 11:00 stop-outs (11:05 gives today's H1 exactly). The limit entry does not fix the late-entry weakness and costs about a third of the money. The confluence job's 2 hand-off candidates (EMA big-range-day skip, EMA 15-minute check) fail this rule too. Fixed on the way - account B's size now never lets one stop-out exceed the rest of the soft daily loss (no change on the 25K). Verdict - keep ATLAS exactly as it is; account B stays off until the paper scorecard says ready. It is still a 2026 bet - in 2025 / 2021-24 about a third of evals get stuck within 2 weeks and an eval is worth about $10.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-10-22]]
- Strategies: [[ATLAS]]
- Refers to: [[atlas-confluences|ATLAS]], [[second-prelaunch|Account B before launch]]
- Runs: `atlas_base, atlas_base_published, atlas_sr_until1100, atlas_ema_nothu, atlas_plus_asia, atlas_limit_close2, atlas_late_mkt, atlas_late_limit2, acctb_25k_need`
- Source: `research/writeups/atlas.md`
- Back to [[ZEUS Home]]
