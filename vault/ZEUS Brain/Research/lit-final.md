---
tags:
  - zeus/research
  - family/other
  - verdict/promising
  - bot/zlarior
type: "research"
date: "2026-10-18"
status: "promising"
source: "research/writeups/lit-final.md"
aliases:
  - "LIT final"
---

# LIT final

> [!tip] Verdict: promising
> promising

**Full title:** LIT final - one LIT strategy built from the four 2026 studies

## Summary

The four LIT studies (entry, sessions, risk, filters) were merged into one strategy and judged on 2026 only, picked on Jan-Jun and checked on Jul-Oct. The final, LIT final, combines the entry study's CISD entry with a 1-minute confirmation and the risk study's VIX-band target banked at 8R. In 2026 it makes +$38,873 (PF 3.06, 3.1 trades a week, max DD -$3,097), against +$20,487 for the old bot. Almost all of the extra money comes from Jan-Jun, the half the parts were tuned on. In Jul-Oct it makes +$8,212 (PF 2.19), while the old bot made +$15,568 over the same months. It only works on true 1-minute bars, most trades come in the London morning (02:00-08:00 ET), and it has no edge in 2021-25 (PF 1.03). Paper only. Since 2026-10-18 it is the paper bot's strategy (live_model.json, engine/lit_live.py; the old bot runs on as a shadow ledger).

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-18]]
- Strategies: [[Zlarior (LIT)]]
- Runs: `lit_final, baseline, lit_A, lit_entry_best, lit_risk_vix_bank8, lit_sessions_A, lit_filters_na_how`
- Source: `research/writeups/lit-final.md`
- Back to [[ZEUS Home]]
