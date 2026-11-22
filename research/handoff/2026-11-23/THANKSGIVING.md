# Thanksgiving week 2026 (Nov 23-27): readiness (day-thanks, paper)

| Day (ET) | Market | What the bots do | Owner action |
|---|---|---|---|
| **Sun 11-22** | Globex opens 18:00 | normal | **before 6 PM:** KEEPALIVE_ON.bat + `KEEP ALIVE ON` (MFFU's 7-day rule keeps counting over the holiday); STOP BOT -> START BOT -> `I ACCEPT LIVE RISK` (Rapid 25K armed) |
| Mon 11-23 / Tue 11-24 | full sessions | normal (LIT 02:00-15:30 entries, flat 15:55; ATLAS as usual). No Tier-1 news (the Fed minutes were Nov 18) | nothing |
| **Wed 11-25** | full session | normal. **08:30 GDP (2nd estimate, Q3) + PCE / personal income (Oct)** (bea.gov schedule, read today); weekly jobless claims usually move to Wednesday this week (DOL page did not load: unconfirmed). None is an MFFU Tier-1 event (CPI / jobs / FOMC), so no news ban applies; the bots trade through 08:30 as on any day | none (expect a fast 08:30) |
| **Thu 11-26 Thanksgiving** | overnight session from Wed 18:00, **halt 13:00 ET** (12:00 CT), no afternoon | entries allowed until **12:45**, every account **flat by 12:55** (engine/cme_calendar: entry_cut 765, flat_cut 775); nothing after the halt | none. MFFU does NOT flatten at a half-day halt (an open position = breach): the bot does it at 12:55 |
| **Fri 11-27** | reopens Thu 18:00, **halt 13:15 ET** (12:15 CT) | entries until **13:00**, **flat by 13:10** (entry_cut 780, flat_cut 790) | none |
| Sat-Sun | closed | - | the keep-alive (if on) acts on the last full session before its 7-day deadline; a half day uses 12:33-12:43 ET (engine/keepalive.window) |

## Checked
- **Calendar in code** (engine/cme_calendar.py): Thu 2026-11-26 early close 13:00, Fri 11-27 13:15, Wed 11-25 / Mon 11-30 full days. The same
  13:00 / 13:15 halts are in the TradingView CME bars on every Thanksgiving / day after 2021-2025. **CME's own page could not be read
  from the cloud (cmegroup.com HTTP 503 today)**; third-party schedules agree on Thu 12:00 CT, Fri 12:15 CT (one says ~12:00 CT).
- **Rehearsal** (tools/rehearse_day.py --rapid, real LiveBot on a simulated NinjaTrader, the PC's 4-account set-up) on the same days of
  2025 (Wed 11-26, Thu 11-27 Thanksgiving, Fri 11-28): **53/53 checks passed**: flat on every account from 12:55 (Thu) / 13:10 (Fri)
  to 16:10, no entry in the last 15 min before either halt, never opposite positions, sizes inside every plan.
  Rehearsal-only note: on 2025 dates the fake broker fills at the 2025 contract (MNQ 12-25) while the bars are back-adjusted to today's
  contract (~1,200-1,450 pts apart), so the bot's "fill far from the chart price -> flatten" safety fired; that shows the guard works and
  does not happen live (the PC's bars and fills are the same contract).
- tests: test_holiday_replay 9/9, test_keepalive 116/116 (test_holidays needs fastapi: not installed in this container).
- **MFFU on holiday sessions** (research/lit/mffu_rules.json, help article 9558251): no auto-liquidation at an early halt, an open position
  = breach (the bot flattens 5 min before). MFFU publishes the hours before each holiday. Whether a half day counts as a trading day is
  not stated separately: the bot counts any day with a closed trade (eval min days, Rapid 4 days, payout day counts), as MFFU's
  "trading day" wording implies - Thu and Fri count only if a trade closes.

## Bugs
None found in the bot. No code changed.
