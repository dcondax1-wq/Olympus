# day-manual: the owner manual (2026-11-20)

Owner (2026-11-19): "It's getting confusing ... I need this simplified, data accurate ... I need to know exactly what's happening,
how much, or what I need to do."

| What | Result |
|---|---|
| Phone page | `tools/web_public/hub/manual.html` (+ manual.css, manual.js, manual-sw.js). One page, 5 tabs: **SOS** (10 emergency cards), **Who** (4 accounts with $, 5 bots with hours), **Day** (normal day + week), **Money** (payout, 80/90%, 30% tax pot), **Words** (24-word glossary; words in the cards link to it) |
| Doc | `docs/OWNER_MANUAL.md` = the same facts (tables) |
| Dark / light | Dark like the hub pages; light follows the phone; Auto / Dark / Light switch kept on the phone |
| Offline | Works with no network after one visit (own worker scoped to `hub/manual` only; proved: with workers blocked the offline reload fails, with it the page + css + js load) |
| Works without JS | Yes: plain HTML; JS only adds Copy, the switch, `#sos-<n>` deep links |
| Test | `tests/test_owner_manual.py` (area board): 29/29. Facts: every copy line in both page and doc, each a real engine module + flag; every .bat exists; prices / payout / hours / phrases match; kill switch as coded (`/api/live/kill` turns auto-resume off; phone KILL reaches Kalshi). Links: 33 resolve. Browser 390x844 dark + light: 0 console errors, CLS 0, no sideways scroll, taps >= 44 px, offline reload OK |
| smoke | 8/8 green |
| Shots | 12 PNGs here (top, kill card, cast, day, money, words x dark/light), deviceScaleFactor 2 |

## The 10 emergency cards (each <= 3 steps, checked in the code)
1 PC off / PC SILENT -> stops at broker; Tradovate/MFFU app Flatten; PC_DOCTOR.bat. 2 Trade open, bot stuck -> do nothing first;
`:8444/safety/` FLATTEN; MFFU app. 3 NinjaTrader disconnected -> Connections; LE_BarFeed chart; MFFU app. 4 Alert says wrong ->
read it; HEALTH_CHECK.bat; send Claude. 5 Daily loss limit -> pause not fail, Limit 0, back after 18:00. 6 Update blocked -> old
code keeps trading; send Claude the line; UPDATE.bat after 16:00 (+ `engine.autoupdate --source-status`). 7 Old numbers on phone
-> "PC reported X min ago" < 30 min = live; PC SILENT = card 1; reopen the app. 8 Stop everything -> HOLD TO KILL at
localhost:8766; phone `:8444/safety/` KILL (also Kalshi); MFFU app (+ `engine.phone_safety --on` once). 9 Add account ->
`/add-account/` + I ACCEPT LIVE RISK (+ `engine.accounts status`). 10 Kalshi off -> it is paper; `:8444/kalshi-live/` STOP;
KALSHI_STOP.bat.

## Commands given to the owner, as run here
- `python -X utf8 -m engine.accounts status` -> here (no accounts file): "No accounts yet. / MFFU slots: evals 0 of 10 · funded 0 of 5 ... / Disarmed until START BOT + you type I ACCEPT LIVE RISK." On the PC it lists his accounts.
- `python -X utf8 -m engine.autoupdate --source-status` -> here: "[..] Auto-update from <backup> (pc) is not connected yet." (read only).
- `python -X utf8 -m engine.phone_safety --on` -> argparse checked (`--on / --off / --status`); turns the phone buttons on (data/phone_safety.json). Not run here (it writes PC state).
- `python -X utf8 -m engine.account_b --payout YYYY-MM-DD=1000` -> flag checked in `--help`; from help.json (already owner-facing).
- `.bat`s named: PC_DOCTOR, HEALTH_CHECK, UPDATE, KALSHI_STOP (runs `engine.kalshi_live --stop`), LIVE_LINK: all exist; contents read.

## Honest notes
- Account $ are a snapshot of the PC report Nov 20 6:00 ET, labelled so; live $ stay on ZEUS. Rapid EOD 25K shown as "bought, not on the PC yet" (board: PLAN ONLY).
- Phone FLATTEN / KILL only work after `engine.phone_safety --on` was run once at the PC; I could not see whether it is on (PC state). The card says so.
- `engine.ops_checks --translate` did not recognise the common lines I tried ("Not a known error"), so it is not in the manual.
- I did not edit help.json / help.html / doors.js / zeus.html (other owners): exact lines in LEAD_WIRES.md.
