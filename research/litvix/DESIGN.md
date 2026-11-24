# LIT in high-VIX falling markets: pre-registration (written 2026-11-24 BEFORE any number below was computed)

PAPER RESEARCH ONLY. Lead's question: live LIT had 0 winners in 7 twin trades (Oct 19 - Nov 20, VIX 25+, NQ 31k -> 25k).
Is that normal bad luck or a regime LIT loses in?

Trades: the live LIT rules (run lit_live = `tools/stops_targets_time.units()`, 2021-10 .. 2026-10-16) + the twin after Oct 16
(`tools/livegap.lit_twin`, PC bars to Nov 20), risk-matched $ (`stops_targets_time.size_matched`), costs in.
Tags, all known before the entry:
- VIX band = the PRIOR session's VIX close (data/VIX_1d.csv): < 15 / 15-20 / 20-25 / 25+.
- 20-day trend = NQ daily close of the prior session vs 20 sessions before it (data/NQ_1d.csv): down < -3%, up > +3%, else flat.
- With / against: long in an uptrend or short in a downtrend = with; long in a downtrend or short in an uptrend = against.
Descriptive tables: trades, win %, PF, $ a month, longest run without a winner, per span (2021-25, Jan-Jun 2026, Jul 2026-now).
Streak question: (a) how often the real 2021-26 sequence has 7+ trades in a row without a winner (win = $ > 0); (b) chance of
7 straight non-winners from a fresh start at the 2026 win rate, and of at least one such run in a year of trades
(10,000 shuffles of the real trades).

Rules (2, and only these):
- **V1 longs off** when the prior VIX close > 25 AND the 20-day trend is down.
- **V2 all LIT off** when the prior VIX close > 25 AND the 20-day trend is down.
Gate (the lead's bar = stricter than the LIT rule): net $ higher in Jan-Jun 2026 AND Jul-Oct 2026 AND 2021-25, PF not lower in
any, >= 2 trades a week, 50K eval path (tools/lit_edge.eval_path) net not lower and 2-week fails not higher in both halves,
random-skip placebo (same count, 2,000 draws) p < 0.05 / 2 pooled over the three spans. Pass = "needs owner yes", else variance.
