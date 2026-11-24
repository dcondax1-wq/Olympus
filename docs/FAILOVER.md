# Failover to a second machine (design only, day-zeroerr 2026-11-24)

Question from the lead: the whole business runs on ONE home Windows PC. Can the owner's Surface (it ran the bot once,
2026-10-25, and overheated on 2026-11-04) be a standby that takes over only when the main PC is silent and provably not trading,
never two bots on one account? No code was written for this; this page is the design and the recommendation.

## Short answer
**Not an automatic failover now. A ready "warm spare" that the owner starts by hand, yes, but only after the "PC silent"
alarm actually works (docs/FAILURE_MAP.md gap G8).** Why:
1. **The money we lose is small next to the risk.** Missed trades cost about $250 each at Jul-Oct's rate (livegap). Two bots on
   one account cost the eval: two entries = double the size, or one bot's stop closing the other bot's position, then the
   other bot "re-protecting" a position that is gone (a naked opposite position). MFFU also bars a long and a short across your
   own accounts at the same time.
2. **"Silent" does not prove "not trading".** The main PC goes silent to the cloud when its *reporting* path fails (GitHub,
   ntfy, the report task) while NinjaTrader and the bot still trade fine. Nov 7-17 was "silent" because the report task was not
   installed, not because the bot was off. A standby that takes over on silence alone would have doubled every trade.
3. **The only lock we have is per machine.** `engine/ninjatrader._acquire_lock` holds `<NinjaTrader 8>\le_locks\<account>.lock`:
   an OS file lock on THAT PC's disk. A second PC never sees it.
4. **Nobody hears that the main PC is off today** (G8: no workflow runs on the repo, so the cloud PC-silent alarm is not live).
   A standby that waits for that signal has no signal.
5. **MFFU's rule on logging in from two devices / a VPS is not in our rules file** (`research/lit/mffu_rules.json` has nothing
   on devices or IPs). Ask MFFU before a second machine ever connects to a real account.

## What would make a double order impossible (if it is ever automated)
All four, not one of them:
| Guard | What it does | Why one alone is not enough |
|---|---|---|
| A. Lease | One writer per account. A small file on the control branch (`control/lease.json`: holder, account, expires) that only a fast-forward push can change. The main PC renews it every 5 min; a machine routes an entry only while it holds an unexpired lease | Git / GitHub down = no lease renewal. The main PC must keep trading without GitHub (the PC must never stop because GitHub is down), so it cannot be the only guard |
| B. Broker truth | Before taking over, the standby's own NinjaTrader must show the account **FLAT with no working orders** for 10+ minutes in the entry window, and no fill on the account since the main PC's last heartbeat (le_feed accounts.csv + outgoing position files) | Flat between trades proves nothing about the next entry: the main PC can still enter one minute later |
| C. Fencing at the source | The main PC, on reconnect, reads the lease; if another machine holds it, the main PC goes **read-only** (no entries; manages only an open trade it already owns) and says so on the phone | Needs the main PC to be able to read the lease; covers "it came back" |
| D. The owner | The standby never arms by itself: it sends ONE phone line "Main PC silent N min, account flat, no orders: take over? reply YES SURFACE" and arms only on that reply (the owner already types the live phrase; this is the same rule) | Without D, A-C still leave the "silent but trading" case (point 2 above) to code |
Even with A-D, an entry in flight while the lease moves is possible. That is why D (a human who knows the main PC is really
off) is the real guard, and why "automatic" is not recommended.

## Recommended now: a warm spare, started by hand
What the Surface needs (one time):
1. The repo the same way the main PC has it: `SETUP_EVERYTHING.bat` (it connects the auto-update to `dcondax1-wq/olympus`,
   branch pc). Do NOT install the START task / auto-resume there: it must never start on its own.
2. NinjaTrader 8 with the LE_BarFeed indicator and the MFFU connection saved, **logged out**. (Ask MFFU first whether a second
   device is allowed.)
3. Plugged in, Sleep "Never", lid "Do nothing" (it overheated in November: a cooling pad).
How the owner switches (only when the phone says the main PC is off, and he can't fix it):
1. Make sure the main PC is really off (power button, or unplug it). This is the step that prevents a double order.
2. On the Surface: open NinjaTrader, log in to MFFU, check the account is flat, then START BOT and type the live phrase.
3. When the main PC is back: STOP BOT on the Surface first, close NinjaTrader there, then start the main PC.

## Before any of this
- Fix G8 (the PC-silent alarm on the phone): without it the owner does not know when to switch.
- The main PC is still on old code, blocked by an old edited tracked file. The auto-park (day-zerotouch2) and this branch's 3 h
  "update stuck" alarm only help once they are installed; day-unstick is clearing the file now.
- Cheaper than a second machine: keep the main PC healthy (UPS for power blips, Windows Update active hours outside 01:30-16:00
  ET, the self-heal + alarms on this branch). Every miss in the last 5 weeks was "PC not there / not armed", not hardware.

## Verdict
| Option | Worth it? |
|---|---|
| Automatic failover to the Surface | **No** (now): the double-order risk can cost an eval; "silent" cannot prove "not trading"; MFFU device rule unknown |
| Warm spare started by hand | **Yes, later**: after G8 works and MFFU says a second device is OK; about 1 hour of setup |
| Make the main PC harder to lose (UPS, update hours, alarms) | **Yes, first** |
