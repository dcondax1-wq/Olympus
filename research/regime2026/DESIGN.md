# A trustworthy "market is 2026-like" switch? Pre-registration (2026-11-26, written BEFORE any run)

PAPER RESEARCH ONLY: nothing live changes. Code research/regime2026/regime.py (signals + weekly test) and engines.py (the 3
variants on the real engines) -> results.json; write-up research/writeups/regime2026-2026-11-26.md.

**Why.** Three rejected ideas each worked in 2026 and failed in 2021-25:
- ATLAS V6 (atlas2), at the calibrated fills;
- the Asia slot (litasia);
- the eval-only Asia slot on the Rapid.

Each needs a switch that is ON in 2026-like weeks and OFF in the others.

## Streams (fixed, stored)
- **ATLAS:** atlas2 V0, every trade at market entry 12 ticks / exit 2 / target 0 + $1.90.
- **ASIA:** the Asia-slot trades only (asia.py variant, entries 18:00-02:00 ET), at +2 ticks a side.

## Signals (daily, known at the PREVIOUS session's close: the switch for session d uses data through d-1)
Data: NQ_1d (NQ1!), VIX_1d, CBOE_vol_1d (vix3m), and each stream's own closed trades.
Every threshold is fixed below or is the feature's OWN trailing 252-session median, which is causal and fitted to no outcome.
Hypothesis fixed in advance (sweep / breakout strategies need movement): ON = more movement / stress / trend.
- **S1 RV:** 20-session mean daily range % (high - low) / close > its trailing 252-session median.
- **S2 VIX:** VIX close > its trailing 252-session median.
- **S3 VIX20:** VIX close >= 20 (the conventional "elevated" line).
- **S4 TERM:** VIX / VIX3M > its trailing 252-session median (the curve flatter / inverted = stress).
- **S5 TREND:** 20-session efficiency ratio |C(d-1) - C(d-21)| / sum |dC| > its trailing 252-session median.
- **S6 EXPAND:** 5-session mean range / 60-session mean range > 1.
- **S7 OWN:** the stream's own last 40 closed trades' mean R > 0 (= atlas2 V6; the stream's own lag).
- **S8 VOTE:** >= 3 of S1, S2, S4, S5, S6.

Not built: "sweep follow-through rate". It needs LIT's internal sweep list per day, and S7 already carries the strategy's own
recent success.

## Weekly test (no engine; the switch's value on its own)
For each rule x stream, on 2021-11..2025-12 (by year) and 2026 by month:
- share of sessions ON;
- mean R a trade ON vs OFF;
- net $ at $250 risk with the gate vs without;
- the 2026 money kept (%);
- the 2021-25 loss avoided.

**Lag cost** both ways: the same rule decided with a 5-session-old reading (late ON, late OFF) vs the 1-session base.

**Selection.** Pick on 2021-11..2023-12 + 2026 Jan-Jun; check on 2024-2025 + 2026 Jul-Oct (16 Oct).
- **Score:** the sum over the 2 streams of (gated - ungated net $) in the pick spans.
- **Keep-2026 condition:** each stream must keep >= 80% of its 2026 H1 money.
- **The winner** is the best score in the pick spans. It is then judged on the check spans only.
- "No reliable switch" if the winner does not also improve the check spans for both streams, while keeping >= 80% of Jul-Oct.

## The 3 variants on the real engines (with the winner only, or with the best rule if none is reliable, labelled so)
- **A. ATLAS V6-style:** ATLAS trades only when S7 (own R) AND the regime rule are ON.
- **B. ATLAS on/off:** ATLAS trades only when the regime rule is ON.
- **C. Rapid eval-Asia:** the Asia trade only while in eval AND the regime rule is ON (eval_only.py machinery).

**Engines.**
- A / B: atlas2's engines (funded 25K, Rapid 25K, Builder 50K / 25K lanes) + the fixed table.
- C: the Rapid eval engine in the five markets (H1, H2, REF, MIX25, BAD).

**Card only if 2021-25 is no longer worse than today in all three:**
- A / B: fixed 2021-25 net >= today's and funded 2021-25 $/mo >= today's;
- C: the Rapid 2021-25 30-day fail % <= today's and its pass % >= today's.

**Also needed for a card:** 2026 H1 and Jul-Oct money / pass at least 90% of the ungated variant's gain.
