# Rapid EOD 25K: the fastest rule-legal pass - design (pre-registered 2026-11-21, committed before any run)

Why: the red team's fleet replay (day-redteam3, tools/fleet_dryrun.py, Nov 6-19) routed 0 of 5 LIT trades and 1 of 9 ATLAS
signals on the Rapid 25K eval: the bot's 30% best-day guard caps a winning day at $428 and one micro's winner is bigger.
MFFU's rule (research/lit/mffu_rules.json rapid_eod_25k.eval: best day <= 30% of the profit, "not a breach, trade more
days"; target $1,500, MLL $1,000 EOD, DLL $500 soft, 4 days, 20 micros) does not forbid a big day: it delays the pass.
Already tested (do not redo as new): rapid25-lit-lane-2026-11-18 (LIT lanes at 1 tick), rapid-launch-2026-11-20 (bank1 at
10 ticks -> NO on eval fails).

Engine: tools/money/rapid25_lit_lane.LaneEv (the eval) + money_plan.RSeat (eval -> funded -> lost -> re-buy, $97.20 fee),
ATLAS re-priced at 10 ticks a side (tools/atlas_risk.T_at(10)), LIT unchanged; 1,000 paths a market (H1 Jan-Jun 2026, H2
Jul-Oct 2026, REF 2021-25), 2,000 eval paths; same seeds as rapid25_launch. Funded stage unchanged in every row.

Rows (fixed now; LIT lane rule + ATLAS lane rule, eval only):
  A0 today: LIT skip, ATLAS guard (size down to the cap, skip at 0)
  A1 LIT bank1 (1 micro, limit at the day's cap), ATLAS guard
  A2 LIT bankq (its full size, limit at the cap), ATLAS guard
  A3 LIT over1 (1 micro, normal target, day may break 30%), ATLAS guard
  A4 LIT skip, ATLAS bank1 (when the guard says 0: 1 micro, limit at the cap)
  A5 LIT bank1, ATLAS bank1
  A6 no guard (LIT + ATLAS full size, normal targets; pass when profit >= $1,500 and best day <= 30% of it)
  A7 ATLAS only in the eval (LIT off), ATLAS guard
  ATLAS has no recorded best excursion: its bank fills only when the trade's own result reached the bank level
  (conservative: a trade that touched the bank and then lost is counted as lost).

Measured: eval pass % in 60 sessions, median sessions to pass, eval fail % in 60, inactivity risk (% of eval runs with 5+
trading days in a row without a trade before passing = MFFU's 7-day rule), $ a month to the owner over 6 months (fees +
re-buys in, 90%, before tax), first payout median, funded lost %.

Decision (fixed now): among A1-A7, the winner is the one with the lowest median sessions to pass in H1 AND H2, provided
(i) $/month >= 95% of A0's in H1 and H2, (ii) eval fail in 60 <= A0 + 1 pt in H1 and H2, (iii) REF $/month >= A0 - $10,
(iv) it passes at least 2 sessions faster than A0 in both halves OR cuts inactivity risk by >= 5 pts in both. None qualifies =
A0 stays, report the best trade-off. A winner -> Decide card (recommend yes) + OFF code; never live.

## Amendment (2026-11-21, after a 100-path pilot of A0-A7, BEFORE the full run; disclosed in the write-up)
  A8 balance-aware guard ("loose", rapid_levers.Ev): a winning day may reach max(30% x $1,500, 30/70 x the profit already
     made) x 0.95, so the best day stays <= 30% of the total at every close (no pass delay). Tested once on the Rapid 50K at
     1 tick (rapid-levers-2026-11-16: +$45 / +$7 a month, "noise", TESTED_AND_REJECTED line 277); re-tested here because the
     25K's cap ($428) bites twice as hard as the 50K's ($855). Same decision rule as A1-A7.
