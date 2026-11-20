---
tags:
  - zeus/research
  - family/other
  - verdict/adopt-candidate
  - bot/zlarior
type: "research"
date: "2026-10-23"
status: "adopt-candidate"
source: "research/writeups/lit-ablation.md"
aliases:
  - "LIT ablation"
---

# LIT ablation

> [!success] Verdict: adopt-candidate
> adopt-candidate

**Full title:** LIT ablation - what each rule earns, what can go, which knobs sit on a cliff

## Summary

Every rule of the live LIT was taken away alone (17 components, 46 neighbours / alternatives, 5 eval-cap settings), a greedy "minimal LIT" dropped whatever cost nothing in 2026 H1, 22 numeric knobs got a sensitivity map, a sampled Shapley split shows who earns the money, and every variant got a paired bootstrap (106 changed variants in all). Four rules carry LIT - the displacement filter (without it H2 is -$1.3k instead of +$9.5k), the 1m CISD entry, the VIX-band target and the inducement - plus the Monday rule and the 15-minute check on the eval path. Two rules do nothing on the live eval: the weekly stop (two_week sizing ignores it) and the $1,000 soft-daily-loss cap (never binds under the 60% room cap). A simpler LIT without the weekly stop, the 1.5R floor, the 15:55 flat and the BE costs holds up as well (H1 +$34.9k, H2 +$9.6k, eval 2-week 57.1/6.7 and 52.2/0.0). Spiky knobs: displacement 0.8, the 8R bank, inducement distance 1.0, the 02:00 start and the 1m CISD window 20 (one bar from a cliff). Recommended for approval - (1) cisd1m 20 -> 22 (same H1 to the dollar, H2 +$426, eval unchanged: insurance off a cliff), (2) optional two_week room cap 60% -> 55% (H1 2-week fails 5.9% -> 2.5%, H2 2-week unchanged, H2 1-month fails 0 -> 1.7%). The weekly stop can go (eval identical) but Shapley shows it is insurance worth ~$22k when LIT works badly (2021-25 contexts): keep it. The inducement-age lead (+$4.8k in H2) is one trade - not adopted.

## Money first

- LIT's money comes from four rules (displacement, the 1m CISD entry, the VIX target, the inducement), plus the Monday rule,
  the 15-minute check, the 8R bank and the room cap on the eval. Keep all of them.
- About a third of the rules are passengers. A 4-rules-shorter LIT makes the same money (H1 +$34.9k, H2 +$9.6k), so simpler
  is possible - but not better. Nothing big can be taken away, and the one idle rule (the weekly stop) is cheap insurance.
- Two knobs are the main overfitting risk: displacement 0.8 and the 8R bank. Nothing better is available; recheck them with
  new data. The 1m CISD window can move off its cliff for free (20 → 22).
- Nothing in this study is a new edge. With 106 variants, the "better in both halves" count is what chance gives. The
  inducement-age lead is one trade.
- Nothing in live_model.json changed. Changes 1-2 wait for the owner's OK.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-23]]
- Strategies: [[Zlarior (LIT)]]
- Runs: `lit_live, lit_adopt_t15_be_off_eval, abl_rec_cisd22_room055, abl_rec_cisd22_room055_eval, abl_rm_wk_stop, abl_rm_monday, abl_rm_t_check, abl_rm_be_off, abl_rm_be, abl_rm_idm, abl_rm_disp, abl_rm_depth, abl_rm_wait, abl_rm_cisd1m, abl_rm_stops, abl_rm_min_rr, abl_rm_max_rr, abl_rm_vix, abl_rm_flat, a`
- Source: `research/writeups/lit-ablation.md`
- Back to [[ZEUS Home]]
