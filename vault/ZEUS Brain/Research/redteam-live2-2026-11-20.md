---
tags:
  - zeus/research
  - family/other
  - verdict/finding
type: "research"
date: "2026-11-20"
status: "finding - 2 alarms built with failing-first tests (half-day halt with a trade open; a trade with no stop after a restart); 1 low patch for the lead; no bot file, strategy, sizing or live_model*.json ..."
source: "research/writeups/redteam-live2-2026-11-20.md"
aliases:
  - "Red team 2 of the live bot"
---

# Red team 2 of the live bot

> [!info] Verdict: finding
> finding - 2 alarms built with failing-first tests (half-day halt with a trade open; a trade with no stop after a restart); 1 low patch for the lead; no bot file, strategy, sizing or live_model*.json touched

**Full title:** Red team 2 of the live bot (2026-11-20) - Thanksgiving / Christmas half days, restarts mid-trade, a 4th account added live, MFFU rules in code

## Summary

MFFU does not auto-close at a CME half-day halt (Thanksgiving 11-26 13:00 ET, 11-27 and 12-24 13:15 ET) and the bot's own flat at halt - 5 min runs only while the bot runs; a STOP, crash or restart without resume left a trade open into the halt = the account fails, with no warning. New engine/fast_alarm halt_open rings the phone from 10 min before the halt (bot stopped) or 4 min (bot running, its close did not land). New no_stop rings when the bot is stopped and a real account holds an entry whose bracket never went out (restart between fill and bracket). Christmas / New Year closures, every MFFU rule (16:10, contracts, Rapid $500 DLL, news, best day, floor) and the day-kalshi diff checked fine.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-11-20]]
- Runs: `tests.test_redteam2_live (15/15, 9 red on pc), tests.test_redteam2_wires (L2, 1/2 before), tests.test_nq_live_reliability 119/119, engine.ninjatrader --selftest, tests.test_holiday_replay 9/9, tests.test_holidays 19/19, tests.test_account_box 40/40, tests.test_multi_account --quick 49/49, tests.test`
- Source: `research/writeups/redteam-live2-2026-11-20.md`
- Back to [[ZEUS Home]]
