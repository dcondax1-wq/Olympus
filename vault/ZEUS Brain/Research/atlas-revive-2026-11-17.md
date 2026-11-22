---
tags:
  - zeus/research
  - family/risk
  - verdict/research
  - bot/atlas
type: "research"
date: "2026-11-17"
status: "nothing to switch. Lead only (paper tally): skip ATLAS on days whose prior VIX close is under 15. second_model.json, data/account_b.json, live_model*.json untouched."
source: "research/writeups/atlas-revive-2026-11-17.md"
aliases:
  - "ATLAS revive"
---

# ATLAS revive

> [!abstract] Verdict: research
> nothing to switch. Lead only (paper tally): skip ATLAS on days whose prior VIX close is under 15. second_model.json, data/account_b.json, live_model*.json untouched.

**Full title:** ATLAS revive (2026-11-17) - the fade is a low-VIX summer plus eval sizing, not a broken member; no weight / drop / add passes the proof rule, one post-hoc lead (skip VIX < 15) is a knife edge

## Summary

Edge health showed ATLAS's stored run at PF 1.41 / ~$411 a month over its last 40 sessions (to Oct 16) vs a 2026 median PF 2.8. At a fixed risk the same 24 trades are +8.0R, PF 1.89 (+0.33R a trade vs +0.92R in Jan-Jun); the $ PF 1.41 is the eval's need size (losers on tight stops got 4-6 micros, winners 1-2). The R that is missing comes from the VIX regime - Sep 1 - Oct 16 had 0 sessions with VIX >= 18 (Jan-Jun 69 of 128), so the VIX-band targets shrank (target winners +2.5R vs +4.3R) and ATLAS's best bucket (VIX 18-22) never traded. No member is broken - S/R is the flattest lately (+0.04R on 7 trades) but dropping or halving it costs Jan-Jun money. On the freshest data (the PC's own member paper trades Oct 19 - Nov 6) the three members made +8.6R on 11 trades, PF 2.2, and VIX is back at 17-28. 19 variants scored on the funded 25K (ATLAS alone, MFFU builder25k funded rules, 600 paths x 126 sessions - reproduces funded25.py exactly) - drops, member weights down, adds from the candidate pool, and low-VIX rules. Only the post-hoc low-VIX rules pass the money gate - skip VIX < 15 lifts the funded 25K to $599 / $582 a month (vs $592 / $497), first payout 18 / 23 sessions (vs 18 / 26), no payout 4.3 / 1.0% (vs 5.0 / 5.5%), and 0 of 40 random skips match it - but Jan-Jun cannot pick it (4 trades, +$7), it was found by looking at Jul-Oct, and its neighbours swing (VIX < 15.5 - Jul-Oct $490, < 16 - $330). Not adopted.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-11-17]]
- Strategies: [[ATLAS]]
- Refers to: [[atlas|ATLAS]], [[atlas-funded-one-a-day-2026-10-31|ATLAS funded 25K]], [[atlas-v2|ATLAS v2]]
- Runs: `none (research/second/atlas_revive_diag.json, atlas_revive.json, atlas_revive_placebo.json; tools/atlas_revive.py)`
- Source: `research/writeups/atlas-revive-2026-11-17.md`
- Back to [[ZEUS Home]]
