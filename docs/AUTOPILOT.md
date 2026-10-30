# Autopilot: what you still do by hand, and the plan to get to zero

Goal (owner, 2026-10-28): "automatic by a few weeks in". The bot trades on its own; this page lists every step a normal
week still asks of you, which ones are automatic now, and the plan for the rest.

**The score.** The bot counts your manual steps every week (Monday to Sunday, New York time): every write on the
Start page (Start trading, the live phrase, names, balances, account changes, clock sync) and every time you step in
(stop, kill, pause, flatten, settings changed by hand, a trade or close in NinjaTrader). Score = 100 minus 10 per step;
0 steps = **hands-free**. It rides in the heartbeat next to the hands-off score (`engine/autopilot.py`,
heartbeat `remote.autopilot`), so the phone sees it. The Start page's own reads do not count, and neither does the bot
resuming itself.

## A normal week

| # | Step | Now | How / what is left |
|---|---|---|---|
| 1 | Start the bot after a reboot or a Windows update | **automatic** | Startup shortcuts open NinjaTrader and the bot server; with the Run switch on, auto-resume restarts the bot (it keeps waiting for NinjaTrader to connect, no time limit) |
| 2 | NinjaTrader log-in / connect | **automatic** | NinjaTrader's *Connect on startup*; the bot waits and retries every 10 s |
| 3 | Weekend disconnect, Sunday 18:00 reconnect | **automatic** | entries wait while NinjaTrader reports every connection DISCONNECTED and resume by themselves when it reconnects (`tests/test_selfheal.py`) |
| 4 | Install updates | **automatic** | hourly / daily auto-update outside 01:50-16:00 ET, only when flat; a dirty file no longer blocks it; the PC self-test runs on the new version first and a regression holds it back ("Update held back: <check>", the old version keeps trading) |
| 5 | Clock change (Sun 2026-11-01, Sun 2027-03-14) | **automatic** | every time is New York time; the cloud's UTC crons were checked on both sides (`tests/test_dst.py`) |
| 6 | Holiday hours (Thanksgiving 11-26 13:00, 11-27 13:15, Christmas Eve 13:15, Christmas + New Year closed) | **automatic** | no entry 15 min before an early close, flat 5 min before, no entry on a closed day, for Zlarior, ATLAS, the extra accounts and a BLITZ router; no false "feed stale" alarms on those afternoons (`engine/cme_calendar.py`, `tests/test_holidays.py`) |
| 7 | Remove a fake P&L after NinjaTrader refused every order | **automatic** | at start the bot voids an earlier day that NinjaTrader's log proves filled nothing (50K since 10-28, ATLAS since 10-29) |
| 8 | File locks (OneDrive / antivirus) on state saves | **automatic** | every state file save retries the lock for ~2 s |
| 9 | Log / disk growth | **automatic** | logs gzipped after a day, deleted after 30; the narrator's feeds after 3 / 120 days; the bar archive keeps 40 / 120 days; the pre-session check warns on low disk |
| 10 | GitHub Actions minutes running out | **automatic** | near 85% of the free 2,000 the cloud monitor drops to one run an hour (night check kept) until the month resets; the PC's trading never depends on it |
| 11 | Check the MFFU balance (17:05 push "Check MFFU: bot thinks ...") | manual, a glance | becomes automatic once LE_BarFeed's account writer is compiled on the PC (it reads the real balance from NinjaTrader: `engine/broker_balance.py`); until then type the MFFU numbers on the Start page only when they differ |
| 12 | Reload the NinjaTrader chart when the bars stop | manual, rare | a push and a red Start page line with the exact click; no bars = no new entries |
| 13 | Sync the PC clock | manual, rare | one tap (Sync the clock) only when the clock guard turns red |
| 14 | Windows Update pause (every 5 weeks) + a NinjaTrader restart once a week | manual, optional | the HEALTH CHECK line turns yellow when the pause runs out; a restart outside 00:00-18:00 ET is resumed by item 1; the PC health line "NinjaTrader" turns amber when its memory grows past 2.5 GB |
| 15 | Weekly check-up before the open | **automatic** | Sunday 15:30 ET the PC self-test (27 of the repo's own suites + 3 checks, ~1-3 min at low priority; one push if anything fails, else a short "all green"); Sunday 17:30 ET one "Ready for Monday" push: version, self-test, Run switch, both accounts' room and eval day, BLITZ's account, the week's big US news, early closes, the clock change; "Run self-test" on the Start page any time |
| 16 | Watch the PC itself | **automatic** | CPU, RAM, disk, NinjaTrader running + its memory, the bot's memory growth, OneDrive conflict copies, clock drift, poll time: green / amber / red in the heartbeat, a push once a day per red line (`python -X utf8 -m engine.pc_health` shows them) |

## When an eval ends

| Step | Now | How / what is left |
|---|---|---|
| Pass / fail detected, trading on it stops, phone push | **automatic** | `engine/eval_life.py` |
| MFFU issues the new account (funded after a pass, a new eval after a fail) | manual at MFFU | sign the funded agreement / buy the new eval at your price |
| The new account Name shows up in NinjaTrader | **detected (new)** | one push "New MFFU account: <Name>"; the Start page shows one line: **Use as Zlarior's funded account** after a pass (funded sizing), **Use for Zlarior / ATLAS (new eval)** otherwise, **Not for the bot** (`engine/new_accounts.py`) |
| Arm the new account | manual, by rule | MFFU requires you to be present: the tap never arms; **Start trading** asks for `I ACCEPT LIVE RISK` once for the new Name |
| Payouts | manual at MFFU | request when the PAYOUT READY push says so, then record it (`python -X utf8 -m engine.eval_life --payout <day>=<$>`) |

## Once a quarter
- **Contract roll** (next: Thu 2026-12-10, MNQ 12-26 -> MNQ 03-27): switch the NinjaTrader chart on Wednesday evening.
  Pushes 7 days and 1 day before; entries are refused on every account while the chart and the order contract differ,
  and an order contract pinned in a config is refused after its roll (`docs/ROLL_DEC_2026.md`).

## The plan for the rest (in order)
1. **Balance from NinjaTrader** (item 11): compile LE_BarFeed's account writer on the PC (ninjatrader/SETUP.md 4b) ->
   the daily MFFU check and the typed balances go away.
2. **Payout record on the Start page**: a "Payout received" button next to the funded account (the CLI line today).
3. **Chart reload** (item 12): LE_BarFeed reconnects its own data series after a NinjaTrader reconnect (C#, needs a
   compile on the PC); the bot keeps refusing entries on stale bars either way.
4. **BLITZ's own 25K** (next week): its slot registers `new_accounts.ROLE_SETTERS["blitz"]` so the new-account line can
   offer "Use for BLITZ"; its router uses the NinjaTrader adapter (holiday cut-offs and the roll guard come with it;
   `engine/cme_calendar.route_limits` gives the same limits for its own checks).
5. Watch the score: a week at 100 (hands-free) is the target; every manual step it lists is the next thing to automate.
