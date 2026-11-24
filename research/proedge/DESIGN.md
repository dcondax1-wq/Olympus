# Pro-edge round (2026-11-24) - pre-registered design (written BEFORE any scored run)

Research only, paper. Nothing live changes. Branch `day-proedge`.
Question (owner): "There HAS to be something in LIT or unknown strategies or something stock brokers know that will make us win."
Five documented professional / institutional edges that are NOT in `docs/TESTED_AND_REJECTED.md` in this form.

## Common rules (all ideas)
- Data: `data/NQ_5m.csv` (TV NQ1!, roll-adjusted via `data/NQ_rolls.json`, 2021-10-18 -> 2026-11-20), `data/ES_5m.csv`
  (ES1!, only from 2025-04-14), `data/GEX_1d.csv`, `data/VXN_1d.csv`, LIT trades `research/lab/backtest_live.json`
  (2021-11-09 -> 2026-10-14). Futures only. Prices are 5m bar OPENS (`tools/quant_anoms.Bars.px`), so every entry is causal.
- Costs: 1 tick slippage each way + $1.90 commission per micro round trip (`tools/pub_strats.COST_PTS`); stop wins a same-bar tie;
  a gap through the stop fills at the bar open.
- Size: the LIT rule ($800 risk up to a 20-pt stop, then $16,000 / stop pts; micros 1..40). 25K / Rapid 25K at half size (20 micro cap).
- Splits: 2026 Jan-Jun (H1, the only place a setting is PICKED), 2026 Jul-Oct (H2), 2021-25 (2021-11-08 -> 2025-12-31).
  Idea 5 has no 2021-24 ES data: its "old" span is 2025-04-14 -> 2025-12-31 and that is said in the result.
- Pass bar (CLAUDE.md): net > 0 AND PF > 1.1 in ALL THREE spans, 2-4 trades / week (or a LIT filter that improves LIT in H1 AND H2
  AND does not hurt 2021-25 by more than $100 / month), placebo p < 0.10 in H1 and H2. Any pass = an owner yes/no card, never live.
- Eval: start an eval on every session of the span, 20-session horizon: Builder 50K (+$3,000, $2,000 EOD trailing, lock +$100),
  Builder 25K (+$1,500, $1,000 trailing), Rapid 25K (25K + best day <= 30% of profit at the pass). Pass %, fail %, median days.
- Placebo: same number of trades on random sessions of the span, same entry/exit clock, directions shuffled (3,000 draws);
  LIT filter: skip the same number of random LIT trades in the span (3,000 draws). p = share of draws >= the observed net.
- Every variant is logged; total count reported (the noise check: a 1-in-20 win is noise).

## Idea 1 - End-of-day rebalancing flow (Cheng-Madhavan LETF rebalancing; Baltussen-Da-Lammers-Martens 2021)
Leveraged / inverse ETFs and short-gamma hedgers must trade WITH the day's move into the close, size ~ move.
- Signal at the 15:30 bar open: M = px(15:30) - px(09:30). If |M| > k x ATR (ATR = mean of the prior 20 sessions' 18:00-17:00 range).
- Trade sign(M) at the 15:30 open; flat at the 15:55 bar open (before 15:58). Stop 1 tick beyond the 14:30-15:30 extreme against
  the trade (min 8 pts). No target.
- Variants (3): k = 0.25, 0.50, 0.75. Pick k on H1 only.
- Not a repeat of edge C "last30_momentum_15:25-15:55" (sign of 09:30->15:00 on EVERY day): this trades only big-move days, which is
  where the rebalancing flow is forced (it scales with the move squared).

## Idea 2 - Hedging-demand (gamma sign) momentum (Baltussen 2021: market intraday momentum is driven by short-gamma hedging)
Idea 1's trade with k fixed at the idea-1 H1 pick, only when dealers are likely SHORT gamma:
- 2a prior-day GEX_1d < 0 (SPX dealer gamma, prior close; GEX used before only as an ORB day-type switch and a LIT size dial)
- 2b prior-day GEX below its trailing 250-day median
- 2c prior-day VXN close above its trailing 60-day median (no GEX: options-implied hedging pressure proxy)
3 variants. Also logged: the complement (long gamma) for each, as a sign check (not counted as a pick).

## Idea 3 - Overnight vs intraday asymmetry (Lou-Polk-Skouras "tug of war"; Kelly-Clark overnight drift)
Overnight leg ON = px(09:25 bar open... i.e. 09:30 open) - px(18:00 open) of the same session (the Globex leg only, NOT the gap to the
prior 16:00 close that the gap tests used). If |ON| > k x ATR: trade at the 10:00 open, FOLLOW or FADE sign(ON), flat 15:55,
stop 1 tick beyond the 09:30-10:00 extreme against the trade (min 8 pts), no target.
- Variants (6): k in {0.25, 0.50, 0.75} x {follow, fade}. Direction AND k picked on H1 only.
- Diagnostic (not a variant): correlation of ON with the 10:00->15:55 move per span.
- Overlap warning: gap fade / gap-and-go were rejected; this is the 18:00->09:30 Globex drift, which only partly overlaps the gap.

## Idea 4 - "Something in LIT": causal expansion-leg skip
Hindsight finding (2026-11-23): LIT losers often fought an expansion leg; winners entered at the start of one. Real-time version:
- At LIT's entry time, take the last N = 4 CLOSED 15m bars (from 5m bars, the hour before entry). Opposite displacement =
  the largest 15m candle body AGAINST the trade (bearish body for a long, bullish for a short) / ATR15, ATR15 = mean 15m true range of
  the prior 20 closed 15m bars.
- Skip the LIT trade when opposite displacement >= x.
- Variants (3): x = 1.5, 2.0, 2.5. Pick x on 2026 Jan-Jun LIT trades; check Jul-Oct (to 2026-10-14) and 2021-25.
- Bar: LIT net up in H1 AND H2, 2021-25 not worse by > $100 / month, trades/week stays >= 2, skip-placebo p < 0.10 in H1 and H2.

## Idea 5 - NQ vs ES relative value (intraday pair mean reversion)
Not a repeat: edge B tested ES/NQ relative strength AT A SWEEP as a direction trigger; nobody traded the spread itself.
- Spread s = ln(NQ close) - ln(ES close) on matched 5m bars; z = (s - mean) / std over the last W bars (rolling, prior bars only).
- Entry 09:35-15:00 at the next bar open when |z| > 2.5: z > 2.5 -> short NQ / long ES, z < -2.5 -> long NQ / short ES.
  Legs dollar-neutral: per unit 1 MNQ vs round(MNQ notional / MES notional) MES (about 2 MNQ : 3 MES at today's prices; we use
  q_nq micros and q_es = round(q_nq x NQ x 2 / (ES x 5)) micros).
- Exit: z back through 0, OR hard stop at |z| >= 4.0 (checked on bar closes, filled at the next open), OR 15:55. One trade at a time,
  max 2 a day. Size: risk $500 to the z=4 stop (stop distance = 1.5 x std of s, in $ of the NQ leg notional); costs on both legs.
- Variants (2): W = 48 bars (4 h), W = 96 bars (8 h). Pick W on H1.

## Total pre-registered variants: 3 + 3 + 6 + 3 + 2 = 17 (17 scored picks max; anything else is logged as a diagnostic).
