---
tags:
  - zeus/research
  - family/sessions
  - verdict/rejected
  - bot/zlarior
type: "research"
date: "2026-10-22"
status: "rejected"
source: "research/writeups/lit-more-entries.md"
aliases:
  - "LIT more entries"
---

# LIT more entries

> [!failure] Verdict: rejected
> rejected

**Full title:** LIT more entries - all hours, 2-3 trades a day, re-arming, sizes, looser rules at night (with t_check and be_off on)

## Summary

The owner asked for more LIT trades ("entries all the time, not one window"), at least 3 a week, adding money in both 2026 halves without more MFFU eval fails. 498 variants on the exact live LIT with today's upgrades on (15-minute check, BE + costs, Monday rule, weekly stop), scored at the LIT size and on the real two_week eval path, picked on Jan-Jun and checked on Jul-Oct. None passes every gate. Two leads. (1) Asia as its own slot with its own 3R bank (1 Asia trade 18:00-02:00 + the normal day trade) is new and gets 4.8 / 4.1 trades a week, more money in both halves (H1 +$34.7k vs +$33.9k, H2 +$13.7k vs +$9.5k), but the eval fail rate rises 1-3 points, the H1 gain is small and comes from February, 2021-25 loses $15.5k; the PC route for it was fixed on 2026-10-22 (it stays off). (2) One London + one NY trade, the NY one 2+ hours after the first exit: no rise in eval fails (H1 2-week fails fall from 5.9% to 3.4%) and a little more money, but only 11 extra trades in 2026, one of them carries the gain, and Jul-Oct stays at 2.8 trades a week. 13 of 498 variants add money in both halves on both views, far fewer than chance would give: most extra LIT trades cost money. Today's LIT stays. Engine options are built (default off), wired through the live loop and tested. Paper only.

## Money first

- **Today's LIT stays** (02:00-15:30, 1 trade a day). No switch is recommended tonight.
- Nothing gets 3+ trades a week in both halves AND more money in both halves AND no rise in eval fails. The extra LIT trades
  exist (Asia, 2nd trades), but on today's hours they are few and edgeless, and at night they need their own bank to make
  money, which is a narrow and 2026-only result.
- **Lead 1 (Asia slot, 3R bank)** is worth a paper shadow before anything else: it is the first Asia version positive in
  both 2026 halves, at 4-5 trades a week. It needs more data (the H1 gain is February); the PC route
  (18:00-24:00 entries, the late sighting) is fixed since 2026-10-22.
- **Lead 2 (London + NY, 2 h cool-down)** is safe and route-tested but tiny: it does not reach 3 a week.

### Switch JSON (for the owner's decision only; NOT applied)

Lead 2 (PC-route ready), in `live_model.json` and `live_model_lit.json`, inside "lit":

```json
"max_per_day": 2, "per_session": ([120, 480], [480, 1080), 1], "second": {"cool": 120}
```

and at the top level of `live_model.json`: `"guards": {"max_per_day": 2}` (the PC guard allows 1 entry a day by default).

Lead 1 (PC route fixed 2026-10-22), inside "lit":

```json
"window": (1080, 1440], [0, 930), "all_hours": true, "max_per_day": 2,
"per_session": ([1080, 120], [120, 1080), 1],
"kz": (1080, 1440, {"max_rr": 3.0}], [0, 120, {"max_rr": 3.0})
```

plus `"guards": {"max_per_day": 2}` at the top level of `live_model.json`; NinjaTrader and the PC must run from 18:00 ET
(`scripts/schedule_pc.ps1` wakes at 01:30 ET and hibernates at 16:35 ET: with the Asia slot the PC must stay on from 18:00).

## Links

- Family: [[Family sessions]]
- Day: [[Day 2026-10-22]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[lit-adv-continuation|LIT advanced report ch2-4]], [[lit-all-hours|LIT all hours]], [[lit-more-setups|LIT more setups a week]], [[lit-retail-entries|LIT retail entries]]
- Runs: `lit_more_ent_asia_slot_rr3, lit_more_ent_asia_slot_rr3_eval, lit_more_ent_lonny_c120, lit_more_ent_lonny_c120_eval, lit_more_ent_asia_slot_rr3_depth075, lit_more_ent_asia_slot_rr275, lit_more_ent_asia_slot_rr3_w20, lit_more_ent_asia_slot_rr8, lit_more_ent_win_full, lit_more_ent_win_24h, lit_more_ent`
- Source: `research/writeups/lit-more-entries.md`
- Back to [[ZEUS Home]]
