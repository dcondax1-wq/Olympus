# A PERSONAL futures account vs the MFFU path: pre-registration (written 2026-11-24 BEFORE any number below was computed)

PAPER RESEARCH ONLY. Owner: "run full tests with our current strategies and see what we would have made on a live account".
Code `research/ownacct/ownacct.py` -> `results.json`; write-up `research/writeups/ownacct-2026-11-24.md`.

Strategies exactly as coded (their stored trade units, futures data only):
- **LIT** = run lit_live units (tools/stops_targets_time.units(): live entry, stop 1 tick beyond the sweep, target, BE 1R,
  15-min check, flat 15:55); 2021-25 on 5m bars (no 1m data then), 2026 on 1m.
- **ATLAS book** = tools/atlas.account_units(BASE) (EMA + MACD + S/R pooled, LIT's blocks / hedge as live), one position at a
  time, max 2 trades a day (tools/second_mix.play_day's rule).
- **BLITZ** (paper) = its live rule (tools/scalp_na_lib.lines, prng >= 0.8), shown separately.
- **LIT + ATLAS** on one account (both at the same risk %, shared equity), the realistic "book".
Each unit's points already include 1 tick of slippage on stop / time / flat exits (the research executors); entries as coded.
Costs (stated): **$0.62 per micro per side = $1.24 a round trip** (a discount futures broker ~$0.25 + CME MNQ exchange ~$0.35 +
NFA $0.02); sensitivity at **$0.85 / side ($1.70 RT)**. Intraday margin **$100 per MNQ** (typical discount-broker day margin;
no trade is held past 15:55), so micros <= floor(equity / $100).
Sizing: fixed fractional, **risk 0.5% / 1% / 2% of the equity at the start of each calendar month** (monthly compounding); micros
= floor(risk $ / (stop pts x $2 + RT cost)); 0 micros -> the trade is skipped (whole micros only); no other cap.
Capital: $5k / $10k / $25k / $50k. Periods (each starts fresh): **2021-11 .. 2025-12** (~5 years), **2025**, **Jan-Jun 2026**,
**Jul-Oct 2026** (the stored units end Oct 16).
Per strategy x capital x risk x period: net $, CAGR, $ a month, max DD $ and % (closed-trade daily equity), worst month, % losing
months, longest drawdown in months (peak to new peak), trades taken / skipped. Risk of ruin = P(equity ever <= 50% of the
start) in 12 months, 1,000 paths, 5-session block bootstrap of the period's sessions (2021-25 pool and 2026 pool).
Minimum capital: the smallest capital at which LIT's 1-micro stop fits the risk % for 90% / 100% of its trades.
Head-to-head: the MFFU path from research/badcase/results.json (rank.py engine, owner's prices, payouts after the 80% split,
eval fees, re-buys): $ a month net and its 10th percentile, per market, vs the personal account at the same market.
Verdict: "personal is better" at a capital x risk when its $/month beats one Builder 50K slot in the 2026-like markets AND it
loses less than the slot's fees in the 2025-like / 2021-25 markets; with the 2022-style drawdown in $ stated plainly.
