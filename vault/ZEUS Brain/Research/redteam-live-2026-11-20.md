---
tags:
  - zeus/research
  - family/other
  - verdict/finding
type: "research"
date: "2026-11-20"
status: "finding - 10 real bugs fixed with failing-first tests on night-redteam; strategy rules, sizing and live_model*.json untouched"
source: "research/writeups/redteam-live-2026-11-20.md"
aliases:
  - "Red team of tonight's live code"
---

# Red team of tonight's live code

> [!info] Verdict: finding
> finding - 10 real bugs fixed with failing-first tests on night-redteam; strategy rules, sizing and live_model*.json untouched

**Full title:** Red team of tonight's live code (2026-11-20) - what could stop the bot, slow an order, send a wrong order or ring at night

## Summary

Independent second pair of eyes on git log 3848045b..cab5247c (combo50k hooks, fast alarm, fast entry, fill audit, multi_account join-time fix, autoupdate flat check, notify / trade alerts, phone_link, remote_ctl control_source, self_heal, account_box). Found and fixed - a phone 'Start trading' that re-armed after the owner's STOP, an old remote stop that could stop Friday's bot, a false 'not polling' push after every START / Re-arm, an alarm storm with no limit that could also eat ntfy's daily room the trade alerts need; the hourly self-heal resetting / moving files in the trading hours and with a trade open; a CLOSEPOSITION that could close ATLAS's trade on the shared Rapid account; designed rule holds ringing as MISSED TRADE at 03:00 ET; plus night-selfheal's pre-merge proposal landed. Nothing found that stops the bot, blocks a poll or slows an order.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-11-20]]
- Runs: `tests.test_lit_live (full, heavy.sh), tests.test_nq_live_reliability, tests.test_self_heal_pc, tests.test_notify, tests.test_trade_alerts, tests.test_fill_audit, tests.test_multi_account, tests.test_autoupdate_source, tests.test_autorun, tests.test_update_from_zip and the rest listed at the end`
- Source: `research/writeups/redteam-live-2026-11-20.md`
- Back to [[ZEUS Home]]
