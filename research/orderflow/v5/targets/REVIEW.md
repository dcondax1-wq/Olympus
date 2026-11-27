# REVIEW: v5 / targets (adversarial reviewer, 2026-11-27)

Scope: DESIGN.md, study.py, oos.py, results*.json, frozen.json, RESULT.md. No author file was edited.
Re-run myself (read-only, write=False): 1m path and 5m path both reproduce exactly (B2R +$2,833.5, T3R +$3,448.5 / +0.85R /
DD $629 / halves +1,658 / +1,790 / placebo 0.0003; 5m rows identical to results_5m.json). Paired sign-flip T3R-B2R p = 0.224.

## Checks that PASS (no refutation found)
- Look-ahead: t_dec = t_sig + 300 (signal bar close); E5 starts at the 1m bar opening at t_dec (min fill time - t_dec = 0).
  NQ_1m.csv stamps are bar OPEN times: aggregating 1m bars [t, t+5m) matches the 5m summary bars (mean |dH| 0.41 pt);
  shifting by +-1 minute is 8-12x worse. So no 1m bar inside the signal bar is used.
- Fills: level fill needs 1 tick through; fill bar checks stop only (no same-bar target on intra fills); stop-and-target bar =
  stop first; stop +2 ticks or the gapped open; market +18 ticks; targets need 1 tick through. Costs $1.90 rt are in every row.
- TOPP levels (PD H/L, Globex <09:30, ORB only for signals >= 10:00) are all known at the signal bar.
- Overlap: under every variant, 0 taken trades enter while an earlier taken trade of the same variant is still open
  (checked per day on fill time vs exit time). No double-counting from the frozen 2R busy chain.
- Halves: first 26 / last 25 days, n 22 / 18, as pre-registered. /week and /month arithmetic correct. Holm over the 6 tested.
- Pre-registration: DESIGN.md 09:21:35 < results_5m 09:25:41 < results 09:26:33; 6 tested variants in code = 6 in DESIGN;
  TS30 kept descriptive. study.py was touched at 09:26:04 (between the two runs), but the current code reproduces the
  earlier 5m file byte-for-byte, so that edit did not change the 5m numbers.

## Problems (none breaks the headline, all weaken "T3R")
1. The pre-registered placebo cannot test an exit. It shuffles taken vs skipped labels on the same entries, so every exit
   passes (Holm 0.002-0.034). The authors say this. Consequence: the "YES-candidate (exit edge)" label that study.py prints for
   T3R (the pre-registered verdict) is not evidence about the exit. The only exit-specific test (paired, p 0.22) was added after
   the run; it is the right test, and it fails.
2. The verdict word is off-protocol. By DESIGN.md's own definitions T3R is "YES-candidate (exit edge)", not "weak" ("weak" =
   fails placebo/Holm). Downgrading is the conservative direction and I agree with it, but it should be stated as a post-hoc
   downgrade, not as the pre-registered result.
3. The +$615 gain rests on a few trades. 20 of 40 trades are identical under 2R and 3R. Per-trade gains: +402, +325, +198
   (sum +925) vs -387, -250, -205. Remove the single best trade and the gain is +$212. That is one runner's worth.
4. 5m path favours wide targets more than the 1m path (T3R minus 2R: +$1,076 on 5m vs +$615 on 1m, same days). Most OOS days
   will run on 5m bars (no 1m before 2025-12-28), so a pooled OOS pass will be flattered. Judge T3R on the 1m-path OOS rows
   (oos.py prints them separately) and on the 5m rows against the in-sample 5m reference, not pooled.
5. The 1m path is a different feed: residual ~1.6 ticks mean |diff| on bar highs/lows after the offset. The "1 tick through"
   target and level rules sit inside that noise; it hits all variants alike, so it does not bias the comparison.
6. Multiplicity across families: v5 has 9 sibling families (combo, delta, exhaustion, levels, profile, sessions, targets,
   trapped, ...) on the same 51 days. Holm here only covers the 6 exits of this family.

## Verdict of the review
Claim HOLDS as stated (weak; edge is in the entry; T3R's gain over 2R unproven, p 0.22). Numbers reproduce. Do not switch the
paper target to 3R on this evidence; the frozen OOS test (1m-path rows weighted, paired p vs 2R) is the only thing that can.
