# LIT on MES for the setups MNQ cannot size (2026-11-27 night). Pre-registration, written BEFORE any variant ran

PAPER RESEARCH ONLY: no live file touched. Futures data only (data/NQ_5m.csv + NQ_1m.csv, data/ES_5m.csv + ES_1d.csv).
Idea (lead, from research/lit/drought-2026-11-27 on origin/day-litdrought): in high ATR LIT's stop passes ~89 pts and `qty_for` gives
0 MNQ (and the live stop range is 8-80 pts), so LIT is starved (drought: 40% of candidates killed by the stop range Oct 15-Nov 26,
56% Nov 17-26). A MES contract is $5 per ES point = about $1.35 per NQ point (ES/NQ ~0.27), so one MES risks ~0.68 of one MNQ and
MES can be sized to the same $ risk where 1 MNQ cannot. Different from the rejected "ES/MES filler on days NQ has not traded"
(litedge): here the setup IS LIT's NQ setup, only its stop is too wide for MNQ.

DATA LIMIT (stated up front): ES bars start 2025-04-14 (5m / 15m / 1h / 1d, no 1m, nothing before). So the ES path of V3 exists only
from 2025-04-14; the "2021-25" check of V3 = 2025-04-14..2025-12-31 (about 9 months), NOT five years. V1 / V2 map the NQ path to MES by the
ES/NQ ratio and run on the whole NQ history; before 2025-04-14 the ratio is a flat 0.30 (no ES data; +-10% = sensitivity, below).

## Variants (3, counted; Holm over 3)
All keep every other live rule (live_model.json "lit": window, depth, idm, disp, 1m execution, stop 1 tick beyond the sweep extreme, VIX-band
target banked at 8R, BE, one trade a day), costs in. Baseline = live LIT as is (stop 8-80 pts, MNQ, $1.40 engine commission).
Wide setup = a candidate that passes every live rule except the stop range, NQ stop 80 < risk <= 150 pts.
- V1 mes_same_risk: wide setups are taken on MES, same signal / timing / NQ fill and exit path, stop and target mapped by the ES/NQ ratio
  at entry (ES points = NQ points x ratio; ratio = prior-day ES close / NQ close from data/ES_1d + NQ_1d, flat 0.30 before 2025-04-14).
  Size = the live $ risk rule (800 up to a 20-pt stop, then 800 x 20 / stop NQ pts) divided by one MES's stop risk (stop ES pts x $5),
  rounded down, NO floor: a setup that rounds to 0 MES is not taken (it stays skipped and leaves the day free). Cost per MES: $1.90 round
  trip + one ES tick ($1.25) of slippage on the entry and on every stop / market exit, instead of the NQ tick already in the path.
- V2 mes_floor1: V1 with a 1-MES floor (the same "1 micro minimum" the drought variants use): a wide setup is always taken with at least
  1 MES (1 MES at a 150-pt NQ stop risks about $203).
- V3 es_detect: LIT's own detection run on ES 5m bars (engine/lit_markets.use with an ES spec: tick 0.25, $5, $1.90; stop range 8 / 80 NQ pts
  x k, k = median ES 5m ATR / NQ's, 1 tick stop buffer, buildup tolerance scaled by k, 5m execution because ES has no 1m) on days NQ had a
  wide setup; its MES size = V1's rule at the ES stop's NQ-equivalent (stop ES / ratio). The day's one trade = the earlier entry of the live NQ
  trade and the ES trade (one position, one trade a day).
Sensitivity (reported, not a variant): ratio +-10%, +1 ES tick more, the NQ path on 5m execution only.

## Judge (fixed now; the lead's rule, same shape as the drought study)
- Pick on 2026 Jan-Jun (H1); check on 2026 Jul 1 - Nov 26 (JulNov; also shown: Jul 1 - Oct 14 and the drought window Oct 15 - Nov 26,
  the window that suggested the idea = post hoc, information only); plus 2021-25 (V3: Apr 14 - Dec 31 2025 only).
- PASS only if, vs live, in H1 AND JulNov AND 2021-25: net $ higher, PF not lower by more than 0.05, max DD not worse by more than 25%, and
  trades / week stays 2-4 in H1 and JulNov. Significance: one-sided sign-flip permutation (10,000) on the per-session $ difference
  (variant - live) in H1, Holm over the 3 variants at 0.05. A PASS without Holm = "candidate, not proven". The 50K eval
  pass rate (Builder 50K, 60-session horizon, lit_final.pass_rate) must not fall in any span.
- Report per span: trades / week and trades added, PF, net $, $ / month, max DD, 50K eval pass rate, and how many wide trades were taken.
- Expected answer: NO or noise: wide-stop setups cluster in high-ATR weeks, are sized to ~$130 of risk (16,000 / stop), so even at full
  mapping they add little $; and every one that takes the day's slot can displace a normal setup.
