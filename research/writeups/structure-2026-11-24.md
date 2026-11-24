# Market structure: expansion and retracement base rates + 8 pre-registered ideas (2026-11-24)

Owner: "Expansion, retracements, look at these stuff. There's more to trading than the classic strategies. Give it one last
push, then we keep what's good." PAPER RESEARCH ONLY: no live file, sizing or arming changed.
Data: NQ futures 5m bars (`data/NQ_5m.csv`: TradingView NQ1! + the PC's NinjaTrader bars), Oct 2021 - 2026-11-20, 1,303 full
CME sessions. Code: `research/structure/study.py` (base rates -> `STRUCTURE_ATLAS.json`), `research/structure/variants.py`
(the 8 ideas -> `variants.json`), rules written first in `research/structure/DESIGN.md`.

## Verdict
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

## The base rates (what the market does; NQ, 3 spans: 2021-25 / Jan-Jun 2026 / Jul 2026-now)
**Expansion days** (range >= 1.5x the prior 14-session ATR): 13% / 17% / 13% of sessions.
- **Compression does NOT lead to expansion on NQ.** After a quiet day (< 0.7 ATR): 5% / 6% / 5% expansion days. A small
  overnight range (< 0.35 ATR): 3% / 0% / 0%. NR7 day before: 8% / 18% / 6% (mixed). Inside day before: 15% / 21% / 0% (mixed).
- **Expansion follows expansion (volatility clusters).** After a big day: 18% / 27% / 25%. Big overnight (0.6+ ATR): 26% / 27% / 21%
  (partly mechanical: the overnight range is part of the day).
- **Time of day.** The session's RTH high or low prints in the 09:00 hour 31% / 35% / 34% of the time and in the 15:00 hour
  23% / 20% / 19%; expansion legs most often START 09:00-11:00 ET (~30% of legs). 5m displacement candles: ~9 a session, the
  09:30 half hour alone 13-16% of them.
- **First-hour drive.** When 09:30-10:30 drives 0.5+ ATR from the open, price comes back to the open by 16:00 only 30% / 15% / 25%.

**Expansion legs** (zigzag swing >= 0.75 ATR; ~23% of swings, median 0.97 ATR long):
- **Retracement depth:** median 0.52 / 0.53 / 0.51 of the leg. Share by depth: < 0.382 ~22%, 0.382-0.5 ~23%, 0.5-0.618 ~16%,
  0.618-0.79 ~15%, 0.79-1.0 ~9%, full reversal (> 1.0) 12% / 16% / 11%.
- **Continuation vs reversal (new extreme after the pullback):** 0.382-0.5 pullback 57% / 75% / 59%; 0.5-0.618 43% / 36% / 50%;
  0.79-1.0 only 20% / 31% / 20%. **The deeper the pullback, the less likely the trend resumes.**
- **Measured move is rare:** the next leg reaches 0.618x the expansion 33% / 40% / 35%, a full 1.0x only 12% / 8% / 12%,
  1.618x 2% / 1% / 4%.
- Legs with a displacement candle in them reverse less (12% / 14% / 9%) than legs without (13% / 24% / 21%).
- **Fib levels alone are not an edge:** a limit at 0.5 / 0.618 / 0.705 / 0.79 of a confirmed expansion leg, stop beyond its
  start, target the extreme: average -0.11 to +0.07 R BEFORE costs in every span (`C_fib_limit_trades`).
- **FVGs:** 80% of 5m displacement candles leave an FVG; 53-55% are filled within an hour, 80-83% the same session.

## How the pillars sit in structure (`D_pillars`; hindsight story + causal tags)
- **LIT wins came at the start of expansion:** 56% (Jan-Jun) / 36% (Jul-Oct) / 28% (2021-25) of LIT winners were entered in the
  first quarter of an expansion leg that went their way. **LIT losses fought an expansion:** 52% / 50% / 42% of LIT losers were
  entered against a big leg that kept going (the sweep was not the end of the move). 49% / 60% / 43% of LIT losers came in 0.79+ deep (or past 1.0) into
  the last swing.
- ATLAS: losers fought an expansion leg 31% / 36% / 33% of the time; winners 16-27% at the start of one.
- BLITZ: ~60% of its winners ride INSIDE an expansion leg (momentum), its losers mostly in small swings.
- None of the causal tags (range used, place in the range, swing phase, late displacement, compression day) holds on the same
  side for LIT in all three spans strongly enough to trade (F1-F3 above). Hindsight tags can't be traded: they say WHY, not WHEN.

## Continuous learning (the part the owner can see)
`engine/market_learn.py` now has a STRUCTURE lens (st_used / st_pos / st_swing / st_disp / st_comp) in the same lesson
machine as the context tags, and writes `research/learn/journal.json` (dated: what each pillar noticed, evidence, status) +
`research/learn/brain_state.json` (per pillar confidence, lessons, last learned, what it tests next, the market read now:
regime, VIX, expansion / retracement phase, where price sits in today's range, the continuation odds for that spot).
Nightly: `python -X utf8 tools/market_learn_weekly.py --nightly` (6 s). Shape: `research/learn/BRAIN_FEED.md`.
