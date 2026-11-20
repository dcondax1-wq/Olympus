---
tags:
  - zeus/research
  - family/other
  - verdict/promising
  - bot/atlas
type: "research"
date: "2026-10-25"
status: "promising"
source: "research/writeups/atlas-v2.md"
aliases:
  - "ATLAS v2"
---

# ATLAS v2

> [!tip] Verdict: promising
> promising

**Full title:** ATLAS v2 - making ATLAS (account B, Builder 25K) hold up outside 2026 (best lead - the two stop hunts as members 4 and 5 at half size; paper first)

## Summary

Owner (2026-10-25) - make ATLAS stronger where the audit found it weak - 2025 loses (-$2,156) and 2021-24 is flat, and its 2026 H2 money rests on a few trades. 62 variants (60 pre-declared, 2 added and counted) were scored under the real account-B rules (need size, never opposite LIT incl. LIT's armed setups, $600 soft daily loss, stuck under $100), picked on 2026 H1, checked on H2, and the 5-year reference had to not lose. Money = the eval path less the $63 fees, averaged over paths started every 5th session (the single published path hangs on one start). Today - H1 2-week pass 65.5% / 0 fails, +$8,500 ($1,417/mo); H2 43.5% / 0, +$2,029 ($580/mo); 2025 -$1,935; 2021-24 -$1,429. Best lead - add the stop-hunt candidates sh_asia + sh_trend as members at half size - H1 67.2% / 0, +$10,090 ($1,682/mo); H2 55.1% / 0, +$3,260 ($931/mo); 2025 -$854 (still negative, but half the loss); 2021-24 +$2,542. It holds as a plateau (sizes 0.4-0.75 all better in both 2026 halves and in 2021-24), it beats 20 random-time placebo members in H2 and 2021-24 (p 0.0-0.1), its flipped twin is worse everywhere, and without each member's 3 best trades it keeps H2 at 24.6% / +$819 where today falls to 11.6% / -$326. Caveats - the hunts were picked on H1 + 2025 + 2021-24 (only H2 is clean), the stop-hunt audit called sh_trend selection luck, sh_trend needs a limit entry account B cannot place yet, and 2025 still loses. Stacking a faster eval turnover on it (buy a new eval when the room is under $200 instead of $100) makes money in all four periods (+$10,876 / +$3,859 / +$240 / +$4,575) with more passes a month, at the price of more $63 evals - a post-hoc stack, so a second-tier lead. Rejected - regime gates picked on 2021-24 (the losing buckets do not stay losing - 8 of 12 are positive in 2026 H1), member drops and EMA down-weights, a buy-a-new-eval-earlier rule on today's ATLAS alone (more passes a month, but less $ per $63 eval in H1 and worse 2021-24), smaller sizes. Nothing changed in second_model.json or account_b.

## Money first

Money = eval-path $ less the $63 fees, averaged over back-to-back paths started on every 5th session. $/mo = that ÷ the
span's months (H1 6, H2 3.5, 2025 12, 2021-24 38). 2-week = pass / fail / stuck within 10 sessions.

| # | Candidate | 2026 H1 (pick) | 2026 H2 (check) | 2025 | 2021-24 | Trades / wk, % weeks 2+ (H2) | Verdict |
|---|---|---|---|---|---|---|---|
| - | **Today** | +$8,500 ($1,417/mo) · 65.5 / 0 / 0.8 | +$2,029 ($580/mo) · 43.5 / 0 / 0 | -$1,935 · 30.1 / 0 / 23.7 | -$1,429 · 22.9 / 0 / 27.1 | 1.6, 38% | baseline |
| 1 | **+ both hunts at 0.5 size** | **+$10,090 ($1,682/mo)** · 67.2 / 0 / 0 | **+$3,260 ($931/mo)** · 55.1 / 0 / 0 | -$854 · 26.5 / 0 / 20.5 | **+$2,542** · 24.5 / 0 / 25.1 | 4.7, 88% | **promising: paper first** |
| 1b | #1 + buy a new eval under $200 of room | +$10,876 ($1,813/mo) · 67.2 / 0 / 2.5 | +$3,859 ($1,103/mo) · 55.1 / 0 / 1.4 | **+$240** · 26.5 / 0 / 41.0 | **+$4,575** · 24.3 / 0 / 45.8 | 4.8, 88% | promising, post-hoc stack |
| 2 | + both hunts at 0.75 size | +$11,720 ($1,953/mo) · 68.1 / 0 / 0 | +$3,622 ($1,035/mo) · 59.4 / 0 / 0 | -$1,668 · 30.5 / 0 / 21.3 | +$5,790 · 27.3 / 0 / 25.1 | 4.4, 88% | promising, more risk |
| 3 | No EMA entry 06:00-06:59 + sh_trend evenings only (18:00-02:00), full size | +$9,678 ($1,613/mo) · 67.2 / 0 / 0.8 | +$2,432 ($695/mo) · 50.7 / 0 / 0 | **+$145** · 31.7 / 0 / 20.1 | +$1,418 · 24.8 / 0 / 26.5 | 1.9, 44% | weak (both rules near chance) |
| x | + sh_trend at full size | +$9,456 · **60.5** / 0 / 0 | +$3,208 · 62.3 / 0 / 0 | +$811 | +$7,188 | 2.4, 63% | rejected: H1 2-week pass -5 points |
| x | + sh_asia at full size | +$12,339 · 79.0 / 0 / 0 | +$2,128 · 53.6 / 0 / **1.4** | -$2,844 | +$5,059 | 1.5, 31% | rejected: H2 stuck up, 2025 worse |

More detail on the three candidates:

| | Today | #1 hunts 0.5 | #2 hunts 0.75 | #3 EMA no 06 + SHT eve |
|---|---|---|---|---|
| H1 p15 / f15, slow_pass, pass_med | 73.7 / 0, 4.3%, 5 | 79.8 / 0, 5.0%, 6 | 81.6 / 0, 5.8%, 5.5 | 71.1 / 0, 8.5%, 5 |
| H2 p15 / f15, slow_pass, pass_med | 54.7 / 0, 13.3%, 6 | 73.4 / 0, 1.9%, 7 | 68.8 / 0, 5.8%, 6 | 53.1 / 0, 0%, 3 |
| dec10 (H1 / H2) | 66.3 / 43.5 | 67.2 / 55.1 | 68.1 / 59.4 | 68.0 / 50.7 |
| $ per $63 eval (H1 / H2 / 2025 / 21-24) | +1,545 / +839 / -415 / -50 | +1,586 / +1,262 / -134 / +110 | +1,731 / +1,358 / -212 / +218 | +1,625 / +858 / +20 / +60 |
| Passes per eval bought (H1 / H2 / 2025 / 21-24) | 0.81 / 0.59 / 0.17 / 0.33 | 0.84 / 0.61 / 0.23 / 0.34 | 0.85 / 0.63 / 0.22 / 0.38 | 0.82 / 0.65 / 0.30 / 0.34 |
| One-start path (published style) H1 / H2 | +$6,481 / +$4,434 | +$13,136 / +$1,057 | +$14,580 / +$1,421 | +$8,661 / +$1,803 |
| PF / max DD on that path, H2 | 3.18 / -$816 | 1.32 / -$819 | 1.42 / -$833 | 1.80 / -$831 |
| Funded 25K, paid in 3 months (H1 / H2 starts) | $1,842 / $1,349 | $1,934 / $1,750 | $1,934 / $1,750 | $2,201 / $1,731 |

Note on the one-start path: in H2 the hunt versions start one eval on 2026-07-01 that is still open on 2026-10-16
(+$1.1k), so that single path shows less than today. Started on any other 5th session they average +$3.3k / +$3.6k.
This is why the average over starts decides here; both are shown.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-25]]
- Strategies: [[ATLAS]]
- Refers to: [[atlas|ATLAS]], [[stophunt-audit|STOP-HUNT audit]]
- Runs: `atlas_v2_base, atlas_v2_hunts_w05, atlas_v2_hunts_w05_stuck200, atlas_v2_hunts_w075, atlas_v2_ema06_shteve, atlas_v2_sht_full, atlas_v2_sha_full, atlas_v2_ema_no06, atlas_v2_stuck300, atlas_v2_idle_s15_300, atlas_v2_cap05`
- Source: `research/writeups/atlas-v2.md`
- Back to [[ZEUS Home]]
