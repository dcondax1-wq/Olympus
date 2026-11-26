# S1 as a FORWARD hold-out: "ATLAS only when S1 is ON". Pre-registration (2026-11-26, before any forward session is scored)

PAPER ONLY, cloud side. No bot, size, arming or live-file change. S1 is research/regime2026/regime.py S1_RV:
- the 20-session mean daily range % of NQ1!, read at the previous session's close,
- compared with its own trailing 252-session median;
- ON when above.

It was chosen with 2021-26 in view (regime2026-2026-11-26.md), so ONLY sessions from 2026-11-23 on count here.

**Recorded nightly** by tools/forward_paper.py (the learn_night "forward" step), for every ET session from 2026-11-23:
- **research/regime2026/s1_forward.json** — one row a day:
  - S1 on / off;
  - ATLAS's REAL result that day (PC live ledger exits, $);
  - ATLAS's TWIN trades (tools/livegap.atlas_twin). **The judged R is at the calibrated fills S1 was found at:** entry 12 ticks, stop / market exit 2, target 0, $1.90. The 1-tick R is recorded too.
  - the Asia-slot PAPER trades (the litasia variant's 18:00-02:00 trades through the twin LIT engine, R at the engine's costs and at +2 ticks a side).
- **forward.json rule `atlas_s1_gate`** (kind skip): one event per ATLAS twin trade on an S1-OFF day, value = -R (what skipping it would have added). It is scored against its own 2021-11..2026-11-20 band like every forward rule. That band is at the harness's 1-tick cost, and there the S1-OFF trades were slightly POSITIVE (band mean of the skip -0.03R). So this rule is informational: the judged numbers are in s1_forward.json at calibrated costs.
- **The Brain's journal** (research/learn/journal.json): key `regime2026|s1_forward`, status watching, "n / 60 sessions".

**Re-judge: on 2027-02-26, or the first night with >= 60 forward sessions, whichever is LATER.**
- **ADOPT-CANDIDATE** (→ the lead writes an owner yes / no card; never automatic) only if ALL of these hold:
  1. at least 10 ATLAS twin trades fell on S1-OFF days (R at the calibrated fills in all four checks);
  2. their sum R < 0 (skipping them would have helped);
  3. the S1-ON twin trades' mean R > the S1-OFF mean R;
  4. the gated twin keeps >= 80% of the ungated twin's R when the ungated twin is positive (or loses less when it is negative).
- **Otherwise REJECTED,** and S1 goes to "Tested and rejected".
- The Asia-slot rows are recorded for the same judgement on the Asia idea, but they adopt nothing on their own.
