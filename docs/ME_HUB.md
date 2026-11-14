# The Me hub (2026-11-14)

Owner: *"get a certain dashboard or area for personal stuff. Make everything very organized, easy to access: connecting to my finances, cards,
spending, WiFi, health, Apple Watch. Find more."*

**Me** is the second tile on the home (right under Today). One page, `hub/?h=me`: four status tiles on top, then eight areas, each a short stack
of cards; one tap on a card opens its detail. Every tile and area says where its numbers come from and how old they are; an empty one says, in one
line, how to connect it.

| What | Result |
|---|---|
| The 4 tiles on top | **Money left this month** · **Health today** · **Home** (OK or the problem) · **Next important date**; each with its source and age |
| Money | spending this month vs last by category, subscriptions with their next charge, bills due in the next 14 days, net worth (your bank exports) |
| Cards | use % per card and in total (under 30% fine, under 10% best), due and statement dates, interest if you carry the balance; phone reminders 5 days and 1 day before each due date |
| Health (Apple Watch) | today with rings-style goals, last night's sleep, the week, resting heart rate and HRV against your own normal, workouts, "recovered?" |
| Home & WiFi | internet speed every 4 hours, outages, every device on your Wi-Fi (with a "new device" phone alert), this PC's disk / uptime / memory |
| Freedom (new) | side income (prop-firm payouts minus fees + the agency's MRR) against your paycheck: % covered, months to quit, how long savings last |
| Dates (new) | birthdays and important days from what you type + your calendars; reminders 7 days and 1 day before a birthday |
| Car (new) | oil change by miles or months, registration / insurance / inspection dates, mileage; reminders before each |
| Streaks (new) | days in a row at your steps / move / exercise / stand / sleep goals, counted for you (no typing) |
| Jarvis | "how did I sleep", "steps this week", "am I recovered" |
| Privacy | your numbers live on your PC and reach the phone ONLY through your private Tailscale link; the public site shows the empty layout |
| Cost | $0. No app to install, no account, no key |
| Trading | untouched: nothing here can trade, pay or change a bot |

Why these four extras (the "find more"): **Freedom** answers the question behind the trading (when can I quit the job), from money you already
import. **Dates** fills the "next important date" tile and never lets a birthday slip. **Car** costs money when forgotten (a missed oil change or
registration). **Streaks** turns the watch data into motivation with zero typing.

## Connect your money
Already built: the 3 steps of `docs/CONNECT_MONEY.md` (a bank CSV in `%USERPROFILE%\.olympus\money_inbox\`, then `RUN_MONEY.bat`).
The Money area and the "Money left this month" tile read the same summary.

## Connect your cards
1. On the PC, in a Command Prompt in the bot folder, paste: `python tools\me_cards.py --add`
2. Answer per card: a nickname (like "Chase Freedom", never the card number or its last 4), the limit, the balance, the statement day, the due day, the APR, autopay yes / no. Enter on an empty nickname ends.
3. Open **Me** on the iPhone through your live link. Due reminders come by themselves.

Change one later: `python tools\me_cards.py --set "Chase Freedom" balance=900`. When your balances file of the money import
(`%USERPROFILE%\.olympus\money\balances.json`) lists the card by the same name as a debt (`"kind": "debt"`), the card takes that balance.

## Connect your Apple Watch
1. Make the Shortcut **Health to PC** below (about 5 minutes, once).
2. Shortcuts app, **Automation**, **+**, **Time of Day**, 21:30, **Daily**, **Run Immediately**, choose **Health to PC**.
3. Optional, once, for your history: Health app, your picture, **Export All Health Data**, save `export.zip` to the PC, then paste: `python tools\me_health.py --import "%USERPROFILE%\Downloads\export.zip"`

### The Shortcut "Health to PC" (no app to install)
Needs the Tailscale VPN on (the same as your PC link). Replace `YOUR-PC.YOUR-TAILNET.ts.net` with your link's address.

1. Shortcuts app, **+**, name it `Health to PC`.
2. **Find Health Samples** where Type is **Steps** and Start Date is **Today**. Then **Calculate Statistics**: **Sum**. Then **Set Variable** `Steps`.
3. The same three actions for **Active Energy** (Sum, variable `Energy`) and **Exercise Minutes** (Sum, variable `Exercise`).
4. **Find Health Samples** where Type is **Resting Heart Rate**, Start Date is Today, Sort by Start Date, Latest First, Limit 1. **Set Variable** `RHR`.
5. **Find Health Samples** where Type is **Heart Rate Variability**, Start Date is in the last 1 day. **Calculate Statistics**: **Average**. **Set Variable** `HRV`.
6. **Find Health Samples** where Type is **Sleep** (Sleep Analysis), Value is **Asleep**, Start Date is in the last 1 day. **Get Details of Health Sample**: **Duration**. **Calculate Statistics**: **Sum**. **Set Variable** `Sleep`.
7. Optional: **Stand Hours** (Find, Start Date Today, then **Count**, variable `Stand`) and **Weight** (Find, Latest First, Limit 1, variable `Weight`).
8. **Get Contents of URL**: `https://YOUR-PC.YOUR-TAILNET.ts.net/inbox/health`. Tap the arrow: Method **POST**; Headers: add `X-Olympus-Inbox` = `1`; Request Body **JSON**, each field of type **Number**:
   `steps` = Steps, `active_kcal` = Energy, `exercise_min` = Exercise, `rhr` = RHR, `hrv_ms` = HRV, `sleep_s` = Sleep, and if you made them `stand_h` = Stand, `weight_lb` = Weight.
9. **Show Notification** with **Contents of URL**: it says what the PC kept ("Saved your health for 2026-11-14: 8,432 steps, slept 7.2 h ...") or why it refused a value.

Run it once by hand to see the notification. Action names move a little between iOS versions; look for the closest one. Any field can be left
out: the PC keeps what arrives, and the full export fills the history.

The fields the PC accepts (anything else is refused with a plain reason): `date` (yyyy-MM-dd, empty = today), `steps`, `active_kcal` (or `active_kj`),
`exercise_min`, `stand_h`, `rhr`, `hrv_ms`, `sleep_h` (or `sleep_min`, `sleep_s`, or "7:12"), `sleep_deep_h`, `sleep_rem_h`, `weight_lb` (or `weight_kg`),
`workouts` (a short text or a list of `{type, min, kcal, km}`).

## Connect Home & WiFi
1. Nothing to type: the PC report (the task `BOTS_BACK.bat` set up) checks every 15 minutes once the PC has this update.
2. Optional, to name a device: `python tools\me_home.py --devices`, then `python tools\me_home.py --name 3f2a91="Mom's iPad"` (the id from the list).

## Connect dates, car and freedom
1. A date: `python tools\me_life.py --date "Mom's birthday=03-14"` (every year; a one-off is `--date "Passport renewal=2027-05-01"`). Calendars connected with `CONNECT_DAY.bat` count too.
2. The car: `python tools\me_life.py --car-miles 48210 --car-date registration=2027-03-31` (after an oil change: `--car-oil-done`).
3. Freedom: `python tools\me_life.py --paycheck 3200 --agency 800` (else the paycheck comes from your calendar wage or the bank's paychecks, the agency from `data/agency/`).

## Private on purpose
- **Where it lives.** What you type is in `%USERPROFILE%\.olympus\me\` (cards, car, dates, device names, your health history), outside the bot folder,
  owner-only. What the phone reads is in `data/me/` (`me.json`, `health.json`, `home.json`, gitignored).
- **Who can read it.** Only the PC's own link serves `data/me/` (`engine/live_site.py`, `/site/me/`): never a site folder, never PUBLISH_NQ, Netlify or
  GitHub Pages. On the public site the Me hub is the empty layout with the "how to connect" lines.
- **Cards: nicknames only.** A nickname with 4 or more digits in a row (a card number, a last 4) is refused. Nothing asks for or keeps a number from a card.
- **Pushes carry little.** A reminder says the nickname and the date ("Gas card is due Sun Nov 15"), never a balance; a new-device alert says the maker,
  never the address. They go through ntfy.sh on your private topic (the PC report's own).
- **The one write from the phone** is the Shortcut's `POST /inbox/health`: strict (known fields, numbers in human ranges, a date in the last 10 days, 2 KB),
  the `X-Olympus-Inbox: 1` header, refused from the internet, and it only appends one line to `data/inbox/health.jsonl`.
- **What goes out from the PC:** two tiny connection checks (Microsoft's and Cloudflare's), a light speed test to speed.cloudflare.com every 4 hours
  (2-25 MB down, 1-4 MB up, a generic User-Agent, no name), and one empty UDP packet to each address of your own home network so devices answer.

## Honest limits
- **PC off = no fresh numbers.** The phone shows the last file with its age; after 36 hours it says the PC may be off.
- **The Shortcut is not tested on a phone here.** It is built from the standard Shortcuts actions; if a value arrives in another unit (sleep in hours
  where seconds are asked), the PC refuses it and the notification says which. Sleep needs the watch on at night (or another sleep app writing to Health).
- **Health once a day.** The Shortcut runs in the evening, so in the morning "Health today" shows yesterday until the next run (add a second automation at
  noon if you want). No live heart rate: Apple gives no free way to stream it to a PC.
- **The bot server must run this update** for `/inbox/health` (it registers the new kind on start): restart it once when flat and the market is closed.
- **Home checks are coarse.** Every 15 minutes while the PC is on: a short drop can be missed, and the speed test is light (often a bit below a full test on a
  fast line). Devices show up when they answer; a phone with a private Wi-Fi address can look new when it changes it. CPU temperature: Windows often
  hides it without admin ("not given").
- **Money is as fresh as your last bank export** (once a month is fine); the Money area says when it is stale. Card balances you typed are as old as you
  typed them (the area flags those over 35 days).
- **Freedom is a straight line** through lumpy payouts: it moves a lot month to month. Taxes and health insurance are not in it.
- **Estimates and plain numbers, not financial or medical advice.**

## How it is built (for Claude)
| Piece | File | Notes |
|---|---|---|
| The hub page | `tools/web_public/hub/me.js` (`OLYMPUS_ME_PAGE`: `view()` pure, `mount()`), `hub/me.css`; `hub/hub.js` hands a page hub to it | reads `../me/me.json` only; ES5; text only; `<details>` cards; tokens only |
| The hub in the IA | `olympus/gate-catalog.js` (hub `me`: `page: 'me'`, `areas`, `size`, `findHubs`), `olympus/hub-status.js` (`meOf`, `hubLine('me')`), `gate/index.html` + `gate.js` (the wide tile, its line, the search), `olympus/gate-nav.js` (Go to shows `size`) | Mix: the hub page is `data-oly-page="hub-me"`, so the Gate's Mix gives it its own look |
| The hub file | `tools/me_hub.py` (`build()` -> `data/me/me.json`: 4 tiles + 8 sections; `reminders()`, `send()`, `maybe_run()`) | called by `tools/pc_report.py` every 15 min (soft); `LE_ME=0` off |
| Cards | `tools/me_cards.py` | `%USERPROFILE%\.olympus\me\cards.json`; `summary()`, `section()`, `reminders()` |
| Health | `tools/me_health.py`, `engine/day_inbox.py` (`validate_health`, kind `health`) | expat-streamed export, `health_history.json` (private), `data/me/health.json` with the Jarvis lines |
| Home & WiFi | `tools/me_home.py`, `tools/me_oui.json` (IEEE list, home vendors only; `--oui-build oui.csv` rebuilds it) | `home_state.json` (private), `data/me/home.json` (no full MAC); `LE_ME_HOME=0` off |
| Freedom, dates, car, streaks | `tools/me_life.py` | `freedom.json`, `dates.json`, `car.json` (private) |
| The private route | `engine/live_site.py` `/site/me/<me|health|home>.json` (`ME_FILES`, `LE_ME_DIR`) | like `/site/day/`: data/me only, before any site folder |
| Jarvis | `jarvis/jdata.js` (XFILES `health`), `router.js` (`health_sleep`, `health_steps`, `health_recovered`, group Health), `skills.js` | answers from health.json's `jarvis` lines with the source and its age |
| Tests | `tests/test_me_hub.py` (a-i static / node; `flock -w 2400 /tmp/olympus_browser.lock python -X utf8 -m tests.test_me_hub` = + Chromium), `tests/test_hubs.py`, `tests/test_gate_page.py`, `tests/test_jarvis_skills.py` | fixture `tests/fixtures/me_health/export.xml` |

## Wiring the lead does (agents do not edit these)
- `tools/web_public/sw.js`: add `'me/'` to `OTHER_APPS`, so the root worker never keeps a copy of the private `me/*.json` (it does not cache `hub/` already),
  then bump `CACHE`.
- `tools/web_public/jarvis/sw.js`: bump `CACHE` (router.js, jdata.js and skills.js changed; they have no `?v`).
- Nothing in `tools/build_web_dashboard.py` (it already copies every file of `hub/`, and there is no `me/` folder to copy) or `jarvis/apps.js`
  (Me is a hub, not an app).
