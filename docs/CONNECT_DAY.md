# Connect your day (2026-11-14)

Your calendars, work shifts, weather and the market news in the Planner and Jarvis, so they can say
"You work 9-5 today: the bot trades alone; check at lunch 12:30."

## Your 3 steps
1. **On the PC** double-click `CONNECT_DAY.bat` in the bot folder. Paste each calendar's private link (where to find it: the table below), then type your city and your pay an hour when it asks.
2. **On the iPhone** open your PC link (the one `LIVE_LINK.bat` gave you, docs/LIVE_DASHBOARD.md) and tap the Planner or Jarvis: "Your work day" is on Today, and the 01:45 / 10:45 / 16:05 cards have a Work line.
3. **Optional:** make the two iPhone Shortcuts below ("Add to my day", "What's my day").

| What | Result |
|---|---|
| Calendars | Google, iCloud, Outlook and the shift apps (When I Work, Deputy, 7shifts, Homebase, Sling, HotSchedules), read every 15 minutes by the PC |
| Work shifts | flagged by themselves (a shift app's link is work; "Open shift" and "Time off" are not), shown next to the bot's entry window 02:00-15:30 ET |
| One sentence a day | "You work 9-5 today: the bot trades alone; check at lunch 12:30." + news during your shift, early closes, which copilot card you miss at work |
| Free time | the gaps between your entries, 7 am - 11 pm |
| Hours vs money | "This week: 40 h at work, about $740 pay. Trading: $0 cash this week ... To quit: the paycheck is about $3,207 a month; trading cash covers 0%." |
| Weather | api.weather.gov for your city: today's forecast, rain chance, alerts |
| Headlines | the Fed's and the BLS's own news feeds, only FOMC / rates / CPI / jobs / PPI / GDP |
| From the iPhone | "Add to my day" puts a task or a note in the Planner |
| Cost | free: no account, no key, no paid service |
| Trading | unchanged: this only reads calendars and adds notes; nothing can start, stop or arm a bot |

## Where to find each calendar link (read-only, no password)
| Calendar | Where |
|---|---|
| Google | calendar.google.com on a computer, the gear, Settings, click the calendar on the left, **Integrate calendar**, copy **Secret address in iCal format** |
| iCloud | iPhone Calendar app, Calendars, the (i) next to the calendar, turn on **Public Calendar**, **Share Link**, Copy (it starts with webcal://) |
| Outlook / Office 365 | outlook.com, Settings, Calendar, **Shared calendars**, **Publish a calendar**, Can view all details, Publish, copy the **ICS** link |
| When I Work | My Schedule, **Sync calendar** (iCal link) |
| Deputy | Profile, **Calendar sync** (iCal feed) |
| 7shifts | Profile, **Calendar sync**, copy the link |
| Homebase | Schedule, **Sync to calendar**, copy the link |
| Sling | Profile, **Calendar subscription** (iCal link) |
| HotSchedules | Settings, **Calendar subscription** (iCal / webcal link) |

Menu names change in these apps; look for "sync", "subscribe", "iCal" or "ICS". A link that asks you to sign in is not the right one: CONNECT_DAY says so.

## The iPhone Shortcuts (no app to install)
Both need the Tailscale VPN on (the same as your PC link). Replace `YOUR-PC.YOUR-TAILNET.ts.net` with your link's address.

**Add to my day** (a task or a note into the Planner):
1. Shortcuts app, **+**, Add Action, **Ask for Input** (Text), prompt: `Add to my day`.
2. Add Action **Get Contents of URL**. URL: `https://YOUR-PC.YOUR-TAILNET.ts.net/inbox/day`. Tap the arrow: Method **POST**; Headers: add `X-Olympus-Inbox` = `1`; Request Body **JSON**: add `text` = *Provided Input*, `type` = `task` (or `note`), optional `due` = `tomorrow`.
3. Add Action **Show Notification** with *Contents of URL* (it says "Added to your day: ..."). Name the Shortcut `Add to my day` ("Hey Siri, add to my day").

The Planner adds each item once, to Today's tasks (a note goes to Notes with the tag `inbox`), the next time it opens.

**What's my day** (opens the Planner on Today):
1. Shortcuts app, **+**, Add Action, **Open URLs**: `https://YOUR-PC.YOUR-TAILNET.ts.net/site/planner/`.
2. Name it `What's my day`. Or ask Jarvis "what's my day" / "hours worked vs trading".

## Private on purpose
- **The links are secrets** (anyone with one can read that calendar), so they are kept only in `%USERPROFILE%\.olympus\calendars.json` on the PC: never in the bot folder, never in git, never in the phone files, never printed in full (`python tools/calendar_sync.py --list` shows the host only). No password is ever asked or stored.
- **Your day file** (`data/day/day.json`, gitignored) is served only by the PC's own link at `/site/day/day.json`. It is never copied into a site folder, so PUBLISH_NQ, Netlify and the public GitHub site never carry it. It has titles and times only: no address, no description, no attendee, no link; e-mail addresses in a title are blanked.
- **The one thing the phone may send**: `POST /inbox/day` appends a line to `data/inbox/day.jsonl` (gitignored) and nothing else. It needs the `X-Olympus-Inbox: 1` header (so a web page cannot post behind your back), is refused from the internet (Funnel), is capped at 200 characters, 30 a 10 minutes and 5,000 lines.
- **What goes out**: GETs of your own calendar links; api.weather.gov with your city's numbers; your city name once to Open-Meteo's geocoder if you typed a name (not numbers); the Fed and BLS news feeds. A generic User-Agent, no cookie, no name.

## Honest limits
- **PC off = no fresh day.** The phone shows the last file with its age; after 36 hours it says the PC may be off.
- **Read only.** Change a shift in your own calendar or shift app; the Planner never writes to a calendar.
- **Google and Outlook links refresh on their side** every few minutes to a few hours: a shift changed a minute ago may show later.
- **Shift titles vary by app.** A shift app's link is work automatically; on a personal calendar only titles like "Work", "Shift ..." count. `CONNECT_DAY.bat` asks "Is this your WORK schedule?" for each link.
- **Rare repeat rules** (by week number, by hour, by year-day) show their first time only; the counts are in day.json (`skipped_rules`).
- **Weather is US only** (api.weather.gov). The pay line uses your typed wage until the money team's import (Ledger income tagged paycheck, or `POST /inbox/money` with `type: paycheck`) has paychecks.
- **"The bot trades alone"** is about the eval / Sim account it runs today. A live account needs you present (MFFU); the sentence says so when the board shows a funded account, and the bot never arms live by itself.
- **The Shortcut needs one line on the PC first** (the lead wires `day_inbox.install(app)` into server.py); until then the link stays fully read-only and "Add to my day" gets "read only over the phone link".

## How it is built (for Claude)
| Piece | File | Notes |
|---|---|---|
| ICS reader | `tools/ics_parse.py` | stdlib; folding, TZID (IANA, Outlook Windows names, mozilla style), VTIMEZONE fallback, a US-rule zone when Python has no tzdata, RRULE DAILY / WEEKLY / MONTHLY / YEARLY (INTERVAL, COUNT, UNTIL, BYDAY incl. 2TU / -1FR, BYMONTHDAY incl. negative, BYMONTH, BYSETPOS), EXDATE, RDATE, RECURRENCE-ID, CANCELLED, TRANSPARENT; wall-clock repeats through DST |
| Calendar sync | `tools/calendar_sync.py` | `--setup`, `--add`, `--list`, `--remove`, `--city`, `--wage`, `--print`; `maybe_run()` from `tools/pc_report.py` every 15 min (throttle 14 min, `LE_CALENDAR=0` off); shifts per NY day, `advise()` = the sentence + notes, `free_blocks()`, `week_line()` (hours, pay from `paychecks()` else the wage, trading cash from `tools/money_scoreboard.py`); last good copy per calendar in `data/day/cache/<hash>.ics` |
| Feeds | `tools/day_feeds.py` | weather.gov points -> forecast -> alerts, Fed + BLS RSS filtered by `TAGS`, once an hour each, `data/day/feeds.json`; entity / DOCTYPE feeds refused |
| The PC route | `engine/live_site.py` | `/site/day/day.json`, `/site/day/inbox.json` from `data/day/` only (`DAY_FILES`, `LE_DAY_DIR`); `POST_ALLOW` + `allow_post()`: the guard's only POST exception |
| The inbox | `engine/day_inbox.py` | `POST /inbox/{kind}` (`KINDS`, `register()`: the money inbox of team X1 shares the shape), `accept()` pure, appends `data/inbox/<kind>.jsonl`, `data/day/inbox.json` snapshot; `install(app)` |
| Phone core | `tools/web_public/olympus/day.js` | pure: `norm`, `today`, `copilotRow`, `briefLine`, `weatherLine`, `headlines`, `inboxItems`, `demo` |
| Planner | `planner/planner.js` (v=b2) | "Your work day" card after the trading day; inbox items added once (`planner.inbox.v1`) |
| Jarvis | `jarvis/copilot.js`, `jdata.js` (XFILES `day`), `briefing.js`, `copilot-card.js` (`__jarvisCopilot.sources`) | Work line on the 01:45 / 10:45 / 16:05 cards, `my_day` intent ("what's my day", "hours worked vs trading"), briefing lines Work / Weather / Headlines |
| Tests | `tests/test_calendar_sync.py` (+ `tests/connect_day_harness.mjs`, fixtures `tests/fixtures/calendar/`) | a-k static / node; `flock -w 2400 /tmp/olympus_browser.lock python -X utf8 -m tests.test_calendar_sync --only=l` = Chromium (Planner + Jarvis) |

Wiring the lead does (agents do not edit these): `server.py` `from engine import day_inbox; day_inbox.install(app)` right after `live_site.install(...)`;
`jarvis/sw.js` SHELL += `../olympus/day.js` and the new tags `briefing.js?v=r2`, `copilot-card.js?v=cp2` (bump them in `jarvis/index.html` with the worker).
