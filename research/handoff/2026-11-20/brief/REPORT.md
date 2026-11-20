# REPORT: day-brief (2026-11-20) - the "thinking before the trade" engine

| What | Result |
|---|---|
| Contract | `docs/BRIEF.md` v 1 pushed first (commit f9019f82, ~45 min in), then v 1.1 additive (`prev_recap`, `alt_call`; `bars_age_min` dropped: it churned) |
| Tool | `tools/premarket_brief.py` -> `tools/web_public/nq/brief.json`, ~8-9 KB, stdlib only, deterministic, no churn (only `built_at`; no rewrite when nothing else changed) |
| Market block | prior CME day H/L/C, prior 16:00 close, overnight H/L, RTH open, gap (pts + ATRs), ATR14, VIX + VXN with band + 1-day move, where price sits, sorted levels incl. LIT's two target lines |
| News block | today + this week (Tier 1 = high, 2 = medium, ET time, source), next Tier-1, what each bot does (read from the code: Zlarior + ATLAS trade through news; funded Rapid flat -2/+2 min) |
| Bots block | Zlarior, ATLAS EMA / MACD / S/R, Rapid: today's windows (early close + Mondays applied), state, max trades, the setup in plain words, levels watched, size rule |
| Bias | Pre-registered BEFORE measuring (`research/lab/brief_bias_prereg_2026-11-20.md`). B1 overnight drift: 47.1% of 442 (2021-25), 59.4% of 69 (H1), 44.6% of 56 (H2). B2 fade yesterday: 49.7% / 47.7% / 39.8%. **No better than a coin** -> `context_only: true` |
| Recap | after 16:00 ET: body, levels taken, did B1 / B2 hold, the day's trades (live wins over its paper twin); `prev_recap` = yesterday, every morning |
| Tests | `tests/test_premarket_brief.py` 74/74; smoke 7/8 (red = no Python Playwright in this container, browser suite, not this branch) |
| Samples | `brief_today.json` (2026-11-20 06:xx: no overnight in the cloud yet, says so), `brief_tier1.json` (CPI day 2026-11-10 08:05), `brief_tier1_recap.json` (same day 16:30) |
| Wiring | `LEAD_WIRES.md`: 4 exact edits (cloud build call, GENERATED line, run_area line, STATE line) |

## Money view
- The day bias is worth $0: right 47-50% of days over 5 years. Using any day bias to skip or size LIT trades was already
  rejected (bias-filters.md, lit-bias-discretion.md, hq-bias.md). Nothing about the bots changes.
- The value is discipline: one page that shows, the same way every day, the levels the bots trade from, the news and what
  the bots do about it, and what each bot needs before it may enter. It stops "the market looks bullish, let me help the
  bot" thinking, which is how evals get blown.

## Honest limits
1. VIX / VXN in the cloud stop at 2026-10-16 (flagged in `data.stale`; LIT target lines use that close).
2. The cloud's NQ bars end at the PC's 17:05 push: a morning brief has no overnight session until fresher bars arrive.
3. Recap trades come from `trades.json` (last refresh 2026-10-28 in this checkout), so most days say "no trade data yet".

## Files
`tools/premarket_brief.py`, `tests/test_premarket_brief.py`, `docs/BRIEF.md`, `research/lab/brief_bias_prereg_2026-11-20.md`,
`research/lab/brief_bias.json` (stored measurement; `--measure` rebuilds it, a test checks stored = fresh),
`tools/web_public/nq/brief.json`, `research/writeups/premarket-brief-2026-11-20.md` (+ INDEX), this folder.
