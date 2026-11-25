# Hands-free PC (day-handsfree 2026-11-25)

Owner: "I don't want to go on my PC and restart it every single time, put code in. I want an easier process."

After tonight's ONE line at the PC (`git stash push -m "owner park" -- research/orderflow/results.json && UPDATE.bat`, STATE.md
"PC update BLOCKED") the PC runs today's code and the list below is how it stays hands-free. Paper rules unchanged: nothing here
arms an account, places an order or changes sizing / strategy; the live phrase stays the owner's, at the PC.

## Every reason you touched the PC in the last 3 weeks
| Reason (when) | Automatic now? | How / what is left |
|---|---|---|
| Update blocked by a file (Oct 27 lit_journal, Nov 23-25 results.json) | **yes** | Bot-made files are git-ignored or in `engine/generated_files`; proved by `tests.test_handsfree` b (the PC's own writers in a temp copy leave `git status` clean). A hand edit is parked (git stash) by the hourly update; tracked market data in `data/` is parkable now. Still stuck 1 h later: Telegram says so, the fix is a reply: **/update** (or **/update force** for a strategy / account file: parked too, nothing lost) |
| Restart the bot / server | **yes** (phone) | Telegram **/restart** or PC Control > Restart: after 16:00 ET and flat; your eval comes back armed (auto-resume) and Telegram replies "PC is back up" |
| Install new code now | **yes** (phone) | Telegram **/update** or PC Control > Update now (otherwise it installs by itself within the hour, outside 01:50-16:00 ET) |
| Pause / resume entries | **yes** (phone) | Telegram **/pause** [HH:MM \| tomorrow] and **/resume** |
| Server crash | **yes** | run_bot.ps1 restarts it in 5-60 s; a crash-loop after an update rolls back by itself |
| Windows Update / power-cut reboot | **yes, after 2 one-time settings** | Boot -> sign-in -> logon task starts the server -> NinjaTrader opened -> connects -> the opted-in eval resumes ARMED (tests.test_handsfree g1). One-time: Windows auto sign-in (Autologon / netplwiz, docs/PC_ALWAYS_ON.md step 2) and NinjaTrader "Connect on startup" |
| Windows restarting in trading hours | **one-time setting** | Active hours 00:00-18:00 + "no restart while signed in" (scripts/one_time_setup.ps1 step c, already done if you ran it) |
| PC asleep / hibernated | **yes** | keepawake while the bot runs + the power plan (finish_tonight / tools/pc_always_on.py --apply); weekday 01:30 ET wake task if it hibernates |
| NinjaTrader closed | **yes** | self-heal reopens it (at most 2x a day; never right after you closed it again) |
| NinjaTrader disconnected (MFFU / Tradovate) | **yes** | NinjaTrader reconnects by itself; the bot sends no entry while disconnected and the phone hears within ~2 min |
| Clock drift | **one-time setting** | FIX_CLOCK.bat once as administrator (task OlympusClock syncs every 15 min + at boot); without it the bot still blocks entries and alerts |
| Unarmed after START (an account missed) | **yes (check) / your phrase** | START + the ONE phrase arms every account and turns auto-resume + keep-alive on for each; the 01:55 / 09:00 ET line says which account is NOT ready. Arming itself is yours by rule |
| 7-day keep-alive switch | **yes** | part of the START phrase since Nov 23 (no KEEPALIVE_ON.bat) |
| New account | **phone + your phrase** | PC Control > Add account (held, never armed); it joins your next START + phrase. Arming a real account is never remote |
| BLITZ / combo switch | **phone + your phrase** | PC Control queues it; your next START + phrase applies it (BLITZ stays paper, owner Nov 24) |
| Order-flow add-on F5 (LE_TickRec.cs) | **copy: yes; compile: probably** | Self-heal copies a new build into NinjaTrader's AddOns after 16:00 ET when flat. NinjaTrader normally compiles a changed file by itself while it runs (not yet seen on your PC). The add-on now reports its build, so if NinjaTrader still runs the old one 30 min later you get ONE line per new build: NinjaScript Editor > F5. There is no way to compile without NinjaTrader's own window |
| Contract roll (Dec 10) | **no, unless no-chart mode** | With the LE_BarFeed chart: switch the chart to 03-27 (docs/ROLL_DEC_2026.md; the bot blocks entries until then and reminds you). With NO_CHART_MODE (LE_Feed add-on) the roll needs no click |
| Missing pip packages | **yes** | self-heal installs them after 16:00 ET when flat |

## Phone control
- **Telegram** (fastest): reply to your Olympus alert bot. `/status`, `/update`, `/update force`, `/restart`, `/pause [HH:MM|tomorrow]`,
  `/resume`, `/help`. Only YOUR private chat (the chat id ALERTS_SETUP saved); anyone else gets no answer. Never from Telegram: kill,
  stop, flatten, start, arming, sizing, strategy. Receipts come back as a reply in ~15 s. Same gates as the phone page: update /
  restart only flat and outside 01:50-16:00 ET on a weekday. Off: `LE_TG_CMD=0`. Code: engine/tg_cmd.py -> engine/remote_ctl.py.
- **PC Control page** (`pc/control.html`): the same commands through one GitHub Commit tap (docs/REMOTE_CONTROL.md).

## The one-time settings (do once, then never again)
1. **Windows auto sign-in** (your choice; without it a reboot waits at the sign-in screen): docs/PC_ALWAYS_ON.md step 2 (Autologon or netplwiz).
2. **NinjaTrader > Connections > Configure > your MFFU connection > tick "Connect on startup"** (MONDAY_SETUP prints whether it is on).
3. **Windows Update active hours** 00:00-18:00 + no restart while signed in (scripts/one_time_setup.ps1 step c).
4. **FIX_CLOCK.bat** once, right-click > Run as administrator.
5. **A UPS** (a small battery box under the desk, ~$60-90): a power blip no longer reboots the PC mid-trade. Plus BIOS "restore on AC power
   loss" = On (docs/PC_ALWAYS_ON.md step 3), so a long cut switches the PC back on by itself.
6. **ALERTS_SETUP.bat** (Telegram) if not done: Telegram commands need it.

## Tests
`python -X utf8 -m tests.test_handsfree` (44 checks; `--fast` skips the ~1 min sandbox). Also tests.test_remote_ctl, test_zerotouch2,
test_self_heal_pc, test_chaos_live (all in `run_area.py pc`).
