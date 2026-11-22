---
tags:
  - zeus/research
  - family/other
  - verdict/info
  - bot/zlarior
type: "research"
date: "2026-10-18"
status: "info"
source: "research/writeups/lit-launch-audit.md"
aliases:
  - "LIT launch audit"
---

# LIT launch audit

> [!note] Verdict: info
> info

**Full title:** LIT launch audit - is anything missing for day trading? (2026-10-18)

## Summary

End-to-end launch check of the LIT bot before the 18:00 ET Sunday open. Real MFFU eval at 21:00 ET - go only after the five checks in section 0 (Sim101 round trip on the Surface first; the code itself is sound). Paper - ready tonight. Needs the contract-roll fix before Wed 2026-12-09, and the cloud heartbeat alert moved to the London session this week. Fixed today - Windows Update restart hours and the PC wake time (both were set for the old 08:00 strategy, while LIT trades from 02:00). Calendar, DST, holidays, early closes and the Sunday open are handled. A news blackout would change 1 of 120 trades in 2026 (H1 +$207, H2 $0), so no news rule.

## Money first

**Paper: ready tonight (18:00 ET).** The rules, the clock and the order route work, and the self-tests pass
(see the table at the end). Three things need doing before a set date:

| # | What | Before | Who / where |
|---|------|--------|-------------|
| 1 | **Contract roll fix** (December to March). Otherwise the bot's levels are about 300 pts off for weeks, and on the PC the stop and target could land in the wrong place. | **Wed 2026-12-09** | code: `engine/live.py` (patch below) |
| 2 | **"PC silent" alert from 01:50 ET.** It only watches 08:00-16:30 ET today, while 95 of 120 LIT trades enter before 08:00. | this week | code: `tools/cloud_monitor.py`, one number |
| 3 | **Cloud end-of-day summary is hit-or-miss** on the :02/:32 schedule. It needs 16:05 or later, the guard stops at 16:25, and the runs come at 16:02 and 16:32. So it only goes out when GitHub starts the 16:02 run 3+ minutes late. | this week | `.github/workflows/cloud-monitor.yml` or `tools/cloud_monitor.py`, one number |

Fixed today (scripts and docs only, no strategy change):
- `scripts/setup_dedicated_pc.ps1`: Windows Update "active hours" were 08:00-17:00 on the PC's clock, so a forced restart
  could land at 02:00-08:00 ET, LIT's busiest time. Now 01:00-17:00 **New York time**, converted to the PC's own clock.
  It also sets "no automatic restart while you are signed in" and tells you to restart by hand on Friday after 17:00 ET.
- `scripts/schedule_pc.ps1` (option B, PC wakes itself): the wake time was 07:50 ET and missed London. It is now 01:30 ET.
  `scripts/PC_OFF_OPTIONS.md` is updated to match.
- `ninjatrader/SETUP.md`: the roll step now says when to switch the chart (Wed 12-09 after 17:00 ET) and why it matters.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-18]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[lit-report-tests|LIT report tests]]
- Runs: `lit_live`
- Source: `research/writeups/lit-launch-audit.md`
- Back to [[ZEUS Home]]
