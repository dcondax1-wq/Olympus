---
title: Red team 2 of the live bot (2026-11-20) - Thanksgiving / Christmas half days, restarts mid-trade, a 4th account added live, MFFU rules in code
family: other
date: 2026-11-20
status: finding - 2 alarms built with failing-first tests (half-day halt with a trade open; a trade with no stop after a restart); 1 low patch for the lead; no bot file, strategy, sizing or live_model*.json touched
summary: MFFU does not auto-close at a CME half-day halt (Thanksgiving 11-26 13:00 ET, 11-27 and 12-24 13:15 ET) and the bot's own flat at halt - 5 min runs only while the bot runs; a STOP, crash or restart without resume left a trade open into the halt = the account fails, with no warning. New engine/fast_alarm halt_open rings the phone from 10 min before the halt (bot stopped) or 4 min (bot running, its close did not land). New no_stop rings when the bot is stopped and a real account holds an entry whose bracket never went out (restart between fill and bracket). Christmas / New Year closures, every MFFU rule (16:10, contracts, Rapid $500 DLL, news, best day, floor) and the day-kalshi diff checked fine.
runs: tests.test_redteam2_live (15/15, 9 red on pc), tests.test_redteam2_wires (L2, 1/2 before), tests.test_nq_live_reliability 119/119, engine.ninjatrader --selftest, tests.test_holiday_replay 9/9, tests.test_holidays 19/19, tests.test_account_box 40/40, tests.test_multi_account --quick 49/49, tests.test_rapid 60/60, tests.test_rapid25 94/94, tests.test_mffu_rules, tests.test_lit_live --quick OK (120/120 identical), tests.test_kalshi_k8_day 43/43 (day-kalshi worktree)
---

# Red team 2 of the live bot (2026-11-20)

Owner summary and ranked table: research/handoff/2026-11-20/redteam2/REPORT.md. Patches: LEAD_WIRES.md next to it.

## Official facts used (fetched today)

| Fact | Source |
|---|---|
| MFFU auto-flat 4:10 PM ET on regular days; "During holiday trading hours, auto-liquidation will not occur at the half-time market close, and the trader is responsible for closing the positions. Failure to close the positions before the market closes will result in breaching of the account unless otherwise notified." | help.myfundedfutures.com 9558251 Permitted Times to Trade |
| Tier-1 news (FOMC, minutes, jobs, CPI): no position / order -2/+2 min for Rapid Sim Funded and Pro Sim Funded; permitted for all evaluations and Builder plans | help.myfundedfutures.com 8230009 News Trading Policy |
| Rapid EOD 25K: target $1,500, EOD MLL $1,000, 2 minis / 20 micros, 30% consistency (eval only), 4 days, inactivity 7 days; DLL add-on $500 = soft pause, not a breach, resets 18:00 ET | myfundedfutures.com/plans/rapid-eod; help 18337038 Rapid EOD with DLL |
| CME holiday hours | cmegroup.com answered 503 (both pages, twice). The dates are the bars' (2021-2025) and engine/cme_calendar's: Thu 11-26 halt 13:00 ET, Fri 11-27 13:15, Thu 12-24 13:15, Fri 12-25 closed, Thu 12-31 full, Fri 1-1 closed. Re-check on cmegroup.com the week before. |

## 1. Holidays through the live code paths

Already right (tests.test_holiday_replay replays all 7 routed lanes on Sim adapters + the fake NinjaTrader): entry at halt - 16
taken, halt - 15 refused, flat with nothing working at halt - 5, a hand position on the account closed too; 12-25 and 1-1 every
lane refuses ("CME holiday"); 12-31 normal 15:55 flat; the 7-day inactivity squeeze over the holiday weeks warns in time. The
LIT model itself treats a halt as the session end (lit_live._session_over); ATLAS (second._session_open) too. Auto-update /
restart: the 01:50-16:00 weekday blackout covers every half day's session; after the halt nothing trades until 18:00.

**The gap (H1, CRITICAL):** every one of those flats needs the bot running. LiveBot.stop() only releases the NinjaTrader locks
(the bracket stays at the broker, by design); a crashed server without the auto-resume opt-in stays stopped; a CLOSEPOSITION
NinjaTrader refuses leaves the position. On a normal day MFFU's 16:10 auto-flat is the safety net. On a half day there is none,
and the fast alarm (in_hours) and the 15-minute report both treat the time after the halt as closed. Fix: engine/fast_alarm
`halt_open` (read-only): inside the last 10 minutes before an early close it reads NinjaTrader's position files of every
non-Sim account; stopped bot -> push from halt - 10, running bot -> from halt - 4 (its own flat is at halt - 5). Title "CLOSE THE
TRADE NOW", the account id cut to its last 4, never held by the 6-a-day cap, no "back to normal" once the halt passed (it would
read as "closed"). Outside those 10 minutes it reads nothing (200 evaluations < 50 ms in the test).

## 2. Restart with an open position

Proven fine (adapter selftest + tests r1-r5): brackets live at the broker, so a restart / reboot / NinjaTrader disconnect does
not remove the stop of a protected trade; the restarted adapter restores the legs (same trading day), places a missing bracket
once (write-ahead S1), never sends a second entry (open-bracket refusal + entries_day restored), and cancels an OCO leftover. An
update / remote restart never lands with a trade open (C6, blackout).

**The gap (H2, HIGH):** a crash in the 1-5 s between the entry fill and the bracket, with no resume, leaves a position with no stop
until the owner starts the bot; the "Bot stopped" alarm did not say so. Fix: `no_stop` (bot not running, a same-day
data/ninjatrader_state*.json leg in entry_sent / pending / unprotected sent > 60 s ago, NinjaTrader shows that real account in a
position) -> "TRADE HAS NO STOP".

## 3. A 4th account added live (Rapid EOD 25K, :8444/add-account/)

Checked: the box runs engine/account_cli.add (a Name already used by any account refused, size from the balance, the MFFU slot limit), adds
it DISARMED; "Start trading" = onboard.rearm (phrase, flat on every account incl. extras, STOP, START BOT arm step). A trade that
ended before the account joined is skipped (night-nqlive), the shared-account flatten guard (C3) holds, alerts carry the account
key (`:acctr` / `:<id>`), sizing is per account (its own preset: 20 micros, $500 day, 30% best day). tests.test_account_box 40/40,
test_multi_account --quick 49/49, test_rapid 60/60, test_rapid25 94/94.
L1 (low): the Re-arm mid-session stops the bot and may restart the server (go.step_arm: server_stale / env change) plus up to
90 s of checklist: 1-3 min without polls in the entry window. Advice: arm after 16:00 ET. L2 (low): the old
`engine.rapid --account` CLI checks the Name only against Zlarior's 50K and ATLAS's 25K (patch + test for the lead).

## 4. MFFU rules: where each is enforced

| Rule | Where | Test |
|---|---|---|
| Flat by 16:10 ET (bot 15:55; half day halt - 5) | engine/ninjatrader._tick_flat_time / _flat_today, cme_calendar.flat_cut | holiday_replay, ninjatrader selftest |
| No new order 16:10-18:00 | ninjatrader._gate (entries only to 15:55 / halt - 15; the 17:00-18:00 halt shut for all-hours lanes) | selftest, holiday_replay |
| Max contracts (50K 40 micros, 25K / Rapid 25K 20, Rapid 50K 30) | multi_account.qty_for `min(q, max_micros)`, account_b adapter cfg max_micros, ninjatrader._split | multi_account, rapid25 |
| Rapid DLL $500 (soft pause) | multi_account.qty_for (full stop-out fits the day left, both lanes' closes) + check_lock; rapid.stack_qty; LIT resizes after ATLAS's forced close (multi_account L979) | rapid25, multi_account |
| Funded news ban (Rapid / Pro funded only) | multi_account presets news_ban "funded", NEWS_PRE_S 180 / POST_S 150; ATLAS Builder funded may trade news | multi_account, nq_live_reliability |
| Consistency (Rapid eval 30%) | multi_account best-day cap (0.3 x target x 0.95, incl. ATLAS's closed $) | rapid25 |
| Drawdown floor / lock | multi_account room + eval_min_room, account_b min_room | multi_account, account_b_min_room |
| Inactivity 7 days | cme_calendar.idle_plan + the ops / account_b pushes | holiday_replay part 2 |

L3 (low): with the $500 DLL add-on a fill worse than 2 ticks at the stop can touch MFFU's DLL at about the stop: a pause for the
day, never a fail.

## 5. day-kalshi diff (engine/kalshi_clock.py, kalshi_live.py, tools/pc_report.py)

Safe for server.py: server.py does not import the Kalshi modules; tools/pc_report (its own process) calls card_k8 inside a
try/except that returns None; paper_like_live / edge_health / bet_log are pure list work on the ledger rows (card_k8 x20 in 2 ms);
cfg always has live_legs / stake_usd (load_config fills them); CARD_MAX 320 -> 480 and pc_report's new k8 cuts pop extras before
the whole block is cut. The display-only claim holds: kill_state and the order gate read clock_live.json, not the filtered paper
rows. tests.test_kalshi_k8_day 43/43 on the branch.

## Not fixed / open

- A refused entry on a half day (a model signal inside halt - 15) is logged as refused; if any model ever signals there it would
  ring as a MISSED TRADE (a false alarm, no money). Not measured here.
- If the PC itself is off at the halt nothing local can ring: the cloud's "PC stopped reporting" (20 min) is the only alarm.
