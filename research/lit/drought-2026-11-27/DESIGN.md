# LIT drought 2026-11-27: pre-registered variants (written BEFORE any variant was run)

Funnel (funnel.py, funnel.json) named the choke: the **stop-size rule**. Share of candidates killed by the stop range
(8-80 pts): 2021-25 13.7%, 2026 H1 24.0%, Jul-Oct 22.5%, Oct 15-Nov 26 40.2%, Nov 17-26 56.0%. Median 5m ATR at the
candidates: 14.8 / 25.9 / 24.8 / 36.6 / 47.4 pts. Displacement fail rate is flat (30-36% everywhere) = not the choke.
Second gate on the same thing: `qty_for` gives 0 micros above ~89 pts (800 x 20 / stop / ($2 x stop) < 1), so a wider
cap does nothing unless one micro is allowed.

## Variants (4, Holm-corrected over 4)
All keep every other live rule (live_model.json "lit"), costs in (engine commission + 1 tick), stop 1 tick beyond the
sweep extreme, size follows the stop, one target (VIX band, banked 8R). Each variant = a new stop cap + a 1-micro floor
for stops above 80 pts (1 micro = $2/pt: a 120-pt stop risks ~$241, 150 pts ~$301). Stops <= 80 pts size exactly as live.
- **V1 pts120**: cap 120 pts (points).
- **V2 atr_floor**: cap = max(80, 3.0 x 5m ATR at the sweep extreme), never above 150 pts.
- **V3 vix_band**: cap 80 pts when the prior VIX close < 22, 120 pts when >= 22.
- **V4 atr_only**: cap = 3.2 x 5m ATR at the extreme (also tighter in calm markets), clamped to [40, 150] pts.

## Judge (owner's rule, fixed now)
- Pick on 2026 Jan-Jun (H1), check on 2026 Jul 1 - Oct 14 (JulOct), plus 2021-25 (data starts 2021-10-18).
- PASS only if, vs live, in H1 AND JulOct AND 2021-25: net $ higher, PF not lower by more than 0.05, max DD not worse by
  more than 25%; and trades/week stays 2-4 in H1 and JulOct.
- Significance: one-sided sign-flip permutation (10,000) on per-session pnl difference (variant - live) on H1; Holm over
  the 4 variants at 0.05. A PASS on the split rule without Holm = "candidate, not proven".
- Oct 15-Nov 26 (the drought) is reported for information only: it is the data that suggested the idea (post hoc).
- Report: trades/week, PF, net $, $/month, max DD, eval pass rate (Builder 50K, 60-session horizon) per span.
- Expected answer: NO (wide-stop trades are 1-micro, small $; they mostly appear in high-VIX weeks).
