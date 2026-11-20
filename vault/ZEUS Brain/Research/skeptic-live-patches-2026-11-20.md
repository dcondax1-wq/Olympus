---
tags:
  - zeus/research
  - family/second
  - verdict/research
  - bot/atlas
  - lane/rapid
type: "research"
date: "2026-11-20"
status: "account_b.patch FIX FIRST (one line: scope the repo-wide FUNDED_ON default to the builder25k plan, else it also cuts ATLAS on a funded combo 50K); engine/rapid.py atlas_slip patch SAFE; card ..."
source: "research/writeups/skeptic-live-patches-2026-11-20.md"
aliases:
  - "Skeptic check of the two live sizing patches"
---

# Skeptic check of the two live sizing patches

> [!abstract] Verdict: research
> account_b.patch FIX FIRST (one line: scope the repo-wide FUNDED_ON default to the builder25k plan, else it also cuts ATLAS on a funded combo 50K); engine/rapid.py atlas_slip patch SAFE; card rapid-atlas-size-10t HOLDS. Nothing live changed by this helper.

**Full title:** Skeptic check of the two live sizing patches (ATLAS funded switches in engine/account_b.py, ATLAS 10-tick sizing on the Rapid in engine/rapid.py) and card rapid-atlas-size-10t - both patches SAFE after one scope fix; the card HOLDS

## Summary

Lead round 4 (owner said YES; the lead applies this weekend). (1) rapid-atlas-size-10t re-run with day-rapid's own tools/money/rapid25_launch.py on 1,000 paths at 10 ticks - week blocks (the card): lost Rapids 27.2 -> 24.0% / 38.0 -> 34.5%, -$141 / -$31 a month, DLL-pause days 1.13 -> 0 per 100 (exact); day blocks: 37.5 -> 32.2% / 40.7 -> 35.5%, -$93 / -$31; another seed: 26.5 -> 24.7% / 37.0 -> 32.5%, -$134 / -$38. Holds. Note: a flat $200 ATLAS cap is as safe or safer and pays more in a Jul-Oct-like market ($803 / 31.9%) but leaves 0.65 DLL-pause days per 100. (2) account_b.patch applied to a pc copy with FUNDED_ON = {funded_room_pct 0.4, streak_shrink 2}: never a larger size than today on 3,168 funded states (882 smaller), eval stage identical, Rapid lane untouched (RapidAtlas.size uses stack_qty), restart-safe (streak from saved closes), BE scratch books -$3.80 net = a loss (as the research). One real issue: FUNDED_ON is applied in account_b.normalize to EVERY spec, and engine/combo50k.ab_spec builds its funded ATLAS spec with that normalize -> room 40% would also cut ATLAS on a funded combo 50K, which no card covers. Exact fix given. The day-atlasedge test file fails 6 checks with the switch ON only because those checks assume OFF (APPLY_ON_YES step 3 says to update them); listed. (3) engine/rapid.py atlas_slip patch: loss1 only grows, PLANS key per plan, no crash path; SAFE.

## Links

- Family: [[Family second]]
- Day: [[Day 2026-11-20]]
- Strategies: [[ATLAS]], [[Rapid lanes]]
- Runs: `none (research/skeptic/rapid10t.py -> research/skeptic/rapid10t_{week,day,seed}.json; research/skeptic/on_check.py on a patched pc copy)`
- Source: `research/writeups/skeptic-live-patches-2026-11-20.md`
- Back to [[ZEUS Home]]
