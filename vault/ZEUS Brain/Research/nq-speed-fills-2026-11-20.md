---
tags:
  - zeus/research
  - family/other
  - verdict/finding
type: "research"
date: "2026-11-20"
status: "finding - 2 read-only speed-up patches for the lead (same ledger, same LIT state on 2,304 replayed polls); fast entry stays OFF (pre-registered rule - $ low end is $0); 4 real fills, all timing ..."
source: "research/writeups/nq-speed-fills-2026-11-20.md"
aliases:
  - "NQ bot speed and fills"
---

# NQ bot speed and fills

> [!info] Verdict: finding
> finding - 2 read-only speed-up patches for the lead (same ledger, same LIT state on 2,304 replayed polls); fast entry stays OFF (pre-registered rule - $ low end is $0); 4 real fills, all timing slippage

**Full title:** NQ bot speed and fills - where the 2.7 s from bar open to order go, 2 free speed-ups (-56% bot work, same trades), fast entry not provable from 1-minute bars

## Summary

Owner - "NQ bot to its max - read data faster, better fills, timing." A replay harness runs the real LiveBot (paper, frozen clock) on LE_BarFeed-format files that grow bar by bar, through the real NinjaTrader read, history merge, clean and LIT model, on 2026-11-16..18 (reproduces the Nov 16 06:16 Zlarior BUY with its real stop). An entry leaves ~2.65 s after the fill bar opens - 2.0 s is the poll offset by design, ~0.5 s the bot's poll (1m bars 240 ms, 5m bars 155 ms, LIT 62 ms), ~0.15 s NinjaTrader / broker; the ledger's 3-5 s stamp is taken after the fill + bracket. Patch 1 (parse only the appended tail of the bar file) -68 ms, patch 2 (history cut to 150 days before the per-poll merges; LIT / ATLAS read <= ~70) -193 ms, together 493 -> 219 ms median, identical decisions. Fast entry ON - same trades, order 2 s earlier; worth $0 to ~$160 a month depending on the unknown price path in the first seconds, so no card. Fills - ATLAS 10 / 12 / 16 ticks past the open, Zlarior 4: almost all of it timing, ~1 tick spread.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-11-20]]
- Runs: `research/speed/replay_harness.py (base / tail / cap / both / fast, 2,304 polls each -> research/handoff/2026-11-20/speed/replay_results.json); research/speed/fast_entry_value.py (-> research/speed/fast_entry_value.json); tools/research/fill_timing.py; tests/test_speed_tail_load.py; pre-registration `
- Source: `research/writeups/nq-speed-fills-2026-11-20.md`
- Back to [[ZEUS Home]]
