# Payout autopilot red team (2026-11-23): night-payout a9bfa0745 (payout commit 81f52a4e9; "98d5db10" is not in the repo) -> night-payout-rt

| # | Finding | Sev | Fixed |
|---|---|---|---|
| 1 | "Do not take payout #5" key was payout5:stop:<slot> (e.g. "atlas"), kept for good: the NEXT funded ATLAS (new eval -> new funded account, same slot) never got the #5 guard alert after its 4th payout | MED | key = slot + the funded account's start day |
| 2 | record() counted every ledger row of the slot ever: the 2nd funded ATLAS's FIRST payout printed "That was payout #5: MFFU moves you to live ... Tell Claude now" (false alarm; and its real 4th said nothing) | MED | counts THIS account's payouts (its own record: account_b / funded_life tracker payouts_n after recording); the ledger only as a fallback |
| 3 | The #5 guard trusts the payouts the owner recorded (TRADE_HOME P): one unrecorded payout makes "payout #4, the LAST" really the 5th (live move, every sim account sleeps) | LOW | payout #4's alert now says: check MFFU's Payouts page shows exactly 3 paid; if it shows 4, do NOT request |
| 4 | Payouts 1-4: two phone alerts for one event (engine/lifecycle "PAYOUT READY: up to $X" when the stage changes, then the autopilot after the close) | LOW | not changed (same facts, different moment) |

Checked OK: never requests a payout, never arms / routes / sizes (no trade path: account_b only gains 3 tracker keys, rapid.status
gains today_net + label; STOP_STATUSES unchanged, "stop" is not a trading stop); MFFU math = research/lit/mffu_rules.json (Builder
25K buffer $1,100, $250-$1,000, 80%, 50% best day, 2 days, 48 h; 50K $2,100, $500-$2,000; plan ask at the max = $2,100 / $4,100;
Rapid 90%, $500 min, no max, $250 (25K) / $500 (50K) since the last payout; the 5-payout live move is Builder only); after 4
payouts funded_life says "stop", lifecycle never PAYOUT READY (habit_ready = status "ready"); Rapid $6,000+ day = one alert
(MFFU: a plain Rapid goes live at $10,000 net in one day; Rapid EOD's path unpublished, so the warning is the right side);
sends via alert_bus.send_critical, a failed send retried next 15-min run (nothing delivered = no buzz); half days use the CME halt.
Tests: test_payout_rt 5/5 (4 fail on a9bfa0745), payout_autopilot 56/56, funded_life 44/44, alert_map 62/62, notify 99/99,
trading_home 46/46, lifecycle 30/30, rapid 60/60, money_goal 86/86, pc_report_sign 21/21, account_b_local 28/28,
account_b_funded 65/71 = the same 6 failures as origin/pc.
