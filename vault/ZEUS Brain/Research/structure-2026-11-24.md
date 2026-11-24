---
tags:
  - zeus/research
  - family/other
  - verdict/research
type: "research"
date: "2026-11-24"
source: "research/writeups/structure-2026-11-24.md"
aliases:
  - "Market structure"
---

# Market structure

> [!abstract] Verdict: research
> (no status line)

**Full title:** Market structure: expansion and retracement base rates + 8 pre-registered ideas (2026-11-24)

## Summary

Owner: "Expansion, retracements, look at these stuff. There's more to trading than the classic strategies. Give it one last push, then we keep what's good." PAPER RESEARCH ONLY: no live file, sizing or arming changed. Data: NQ futures 5m bars (`data/NQ_5m.csv`: TradingView NQ1! + the PC's NinjaTrader bars), Oct 2021 - 2026-11-20, 1,303 full CME sessions. Code: `research/structure/study.py` (base rates -> `STRUCTURE_ATLAS.json`), `research/structure/variants.py` (the 8 ideas -> `variants.json`), rules written first in `research/structure/DESIGN.md`.

## Money first

**0 of 8 ideas pass. Nothing to switch on.** The base rates are kept: they now feed the Brain (journal + market read).

| Idea | Jan-Jun 2026 | Jul 2026-now | 2021-25 | Verdict |
|---|---|---|---|---|
| S1 buy the 0.5 pullback of an expansion leg, stop beyond the leg start, target the extreme | 1.5/wk, PF 0.68, -$2,459 | PF 1.11, +$531 | PF 0.88, -$5,799 | FAIL |
| S2 deep 0.79 pullback -> 1.272 extension | 0.6/wk, PF 0.75, -$1,162 | PF 1.75, +$1,441 | PF 0.90, -$4,590 | FAIL (too few, loses 2 of 3) |
| S3 after a big day / big overnight: first 5m displacement 09:30-11:00, 2R | 2.5/wk, PF 0.99, -$142, 50K 2-wk pass 4% / fail 22% | PF 1.01, +$156 | PF 0.98, -$1,806 | FAIL (coin flip) |
| F1 LIT skip "late chase" (displacement our way in the last 30 min) | $33,901 -> $32,460 | $9,919 -> $9,373 | ($1,265 -> $12,782) | FAIL (loses money in both 2026 halves) |
| F2 LIT skip "mid-retrace fade" | $33,901 -> $34,929 | 0 trades hit: unchanged | ($1,265 -> $3,488) | FAIL (nothing to check on) |
| F3 LIT x1.5 at the day's extreme (start of a move) | $33,901 -> $47,214, 50K path +$5.5k | $9,919 -> $10,438 (+$519) | ($1,265 -> $3,336) | FAIL (H2 gain = random luck: placebo p 0.65) |
| F4 ATLAS skip entries 50-80% into the day's range | $25,737 -> $19,550 | $8,228 -> $5,956 | $15,493 -> $24,251 | FAIL |
| F5 BLITZ skip half-used days (0.5-0.8 ATR) | $5,513 -> $4,513 | $3,375 -> $4,172 | $4,570 -> $6,480 | FAIL (loses Jan-Jun; placebo p 0.03 vs bar 0.006) |

LIT numbers are the live trades risk-matched (run `lit_live`, costs in, `tools/stops_targets_time` engine as day-stopstime).
Honesty note: the base rates were measured on every span before the 8 ideas were written, so the check half was not blind;
that is why the bar was "every span + placebo at 0.05 / 8". F3 is the only one worth watching (big in Jan-Jun, small in Jul-Oct);
the Brain journals it as rejected and Market Learn's weekly loop will see it again if it keeps showing (st_pos=extreme lens).

## Links

- Family: [[Family other]]
- Day: [[Day 2026-11-24]]
- Source: `research/writeups/structure-2026-11-24.md`
- Back to [[ZEUS Home]]
