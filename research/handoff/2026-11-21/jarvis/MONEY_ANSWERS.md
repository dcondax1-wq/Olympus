# Jarvis money answers (lead QA 2026-11-21), day-jarvis

60 questions the owner asks by voice (payout, room, pass, trades, week / month, 7-day inactivity, which account next, taxes, Kalshi, the PC,
armed, rules) with what the TRUE answer must say, for two fixtures of the PC's status post: **live** (reported 2 min ago; Zlarior 50K eval
$49,193, Zlarior 25K #2 eval $25,000, ATLAS 25K sim funded at **+$401** in MFFU terms) and **PC silent** (the same post, 2 days old).
Truth: docs/ACCOUNT_RULES.md + research/lit/mffu_rules.json. The real Jarvis page answers each one (Chromium; typed, the reply read back).
`python -X utf8 -m tests.test_jarvis_money_answers` (~30 s; `--dump` prints every answer). In run_area jarvis.

| | before (pc 7adf312d) | after |
|---|---|---|
| live: the answer has the true numbers, never $27,100 / $25,401 | 40 / 60 | **60 / 60** |
| PC silent: live numbers carry their age ("2 days ago, the PC may be off") | 41 / 60 | **60 / 60** |
| total checks (+ no page errors) | 82 / 121 | **121 / 121** |

What was wrong (read by hand, not only the checks) and what Jarvis says now:
- **Payout** (when / how much / eligible / how far / earliest / how many left / split / what I keep): 8 of 10 gave only the date
  estimate. Now: "ATLAS 25K funded: +$401 ... Earliest payout at $1,350 ($949 to go); goal $1,000 at $2,100 (you get $800), $1,699 to
  go. Eligible now? Not yet: $949 more to the earliest ($250 at +$1,350) ... The rules: $250 min, $1,000 max; 80% ($800, $560 after the
  30% tax pot); 2 traded days, best day <= 50%, 48 h after the first funded trade; 5 sim payouts, then live", then the dates.
- **Room**: ATLAS was "$1,401 of the $1,000 max loss (140%)". Now "ATLAS 25K funded: $1,401 above its floor (the floor is -$1,000 in
  MFFU terms, +$401 now; it rises with new highs and stops at +$100); today it can still lose $600 (a pause, never a fail)". Generic
  "how much room / can I lose today / daily loss / max loss / floor" now answered with every account (the 25K #2 was missing) + age.
- **Pass**: "how far am I from passing" said "ATLAS: $1,850 to the target" (ATLAS is funded). Now only the evals, with dates.
- **Last trade**: came from the 25-day-old replay file (Oct 28). Now from the PC's report (ATLAS, Tue Nov 17).
- **7-day inactivity**: nothing answered it. Now the rule + each account's last trade and "trade by" date (or "check MFFU" when the
  report does not carry it).
- **Which account next / this month / live or paper / contracts / news / consistency**: new answers (the contract question used to
  answer with Kalshi bet sizing, the news question with the calendar).
- **Stale**: every live answer ends with "Source: PC report, 2 days ago. Old: the PC may be off." when the PC is silent.

Other suites: jarvis_biz 130/130 (generic "how much room" is now answered here, not by the brain: its answer was the misleading one),
jarvis_zeus 125/125, jarvis_skills 85/85, jarvis_hub 272/272 (its BLITZ room check takes the new wording), smoke 10/11 (worker_tag below).
