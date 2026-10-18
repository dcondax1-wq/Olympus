# Phone notifications: one for every trade, in your app

**What you get.** Your Home Screen app (Liquidity, https://demetrades2000-coder.github.io/nq-dashboard/) shows:

| When | Title | Text |
|---|---|---|
| a trade is entered | `LONG · MFFU 50K` | `Entered 4 MNQ` |
| the trade ends (the same notification is replaced) | `LONG · MFFU 50K` | `+$1,812` (win), `−$366` (loss), `$0 breakeven`, `+$212 closed 15:55` |

The account name says who traded: **Paper** = the cloud paper bot (PC off), the NinjaTrader account (for example
**Sim101**) = the PC bot, the name in `live_model.json` `"account": {"name": ...}` (default **MFFU 50K**) = a real account.
Each trade is notified once, even when the cloud and the PC both trade it. Nothing else pushes: the PC bot going silent and
eval-timing changes appear in the app's **Activity** page (System -> Activity, and a card on Today), next to every
entry and result with its details (prices, stop, target, R, eval balance). The app icon shows a badge with the new ones.

Free. Telegram and Discord are off.

How fast: the cloud paper bot checks every 30 minutes on market days (02:00-16:25 ET), so its notices arrive up to ~30
minutes after the fill (GitHub can add a few minutes). The PC bot's arrive a few seconds after the fill.

Paper only, as always: notifications never place or change an order.

---

## Setup: tap Allow (that is all)

You need iOS 16.4 or later, and the app must be opened **from the Home Screen** (notifications do not work in a Safari tab).

1. If the app is not on your Home Screen yet: open the link above in Safari -> **Share** -> **Add to Home Screen** -> **Add**,
   then open **Liquidity** from the Home Screen.
2. On **Today**, tap **Turn on** in the "Get a notification for every trade" card (or System -> Settings -> **Turn on
   notifications**), then **Allow**.

Done. The app tells the cloud bot by itself. Its card says **waiting for the cloud** until the next cloud run (market days,
every 30 min) and **on** after it. If you allow notifications on a weekend, open the app once on Monday so it can remind
the cloud (the relay forgets after about 12 hours; the app re-sends by itself whenever it opens until the cloud has it).

Optional check: GitHub -> **Actions** -> **cloud-monitor** -> **Run workflow** -> tick **Send a test notification**.

The PC bot (optional) links by itself too, as long as its heartbeat is on (`LE_HEARTBEAT=1`, the always-on PC setup): the
next cloud run hands it the notification key, sealed so only that PC can open it. PC dashboard -> Alerts -> Phone app
notifications shows **linked** and has a **Send test** button.

---

## When something is off

| The app says | Do this |
|---|---|
| "On iPhone, notifications work in the Home Screen app" | Open Liquidity from the Home Screen, not from Safari. |
| **blocked** | iPhone Settings -> Notifications -> Liquidity -> Allow Notifications, then tap Turn on again. |
| **waiting for the cloud** for more than a market day | Open the app again (it re-sends); check that the cloud-monitor workflow runs (Actions tab). |
| **tap to finish** | Tap Turn on once more (the phone wanted a tap to finish the subscription). |

If the cloud's key ever changes (its cache is lost), the app subscribes again on its next open, by itself.

## Settings you can change (optional)

| What | Where |
|---|---|
| Account name in the notices | `live_model.json`: `"account": {"name": "MFFU 50K", "paper": "Paper"}` |
| Also push PC-silent / eval-timing / NinjaTrader trouble | repository variable `LE_PUSH_EXTRA` = `1` (PC: start the server with `LE_PUSH_EXTRA=1`) |
| Your own key instead of the automatic one | GitHub Secret `LE_VAPID_PRIVATE` (make one with `python tools/push_keys.py`); phones re-subscribe by themselves |
| Telegram / Discord back on | repository variable `LE_ALERTS_CHAT` = `1` (PC: `LE_ALERTS_CHAT=1`, or `"alerts": {"chat": true}` in `live_model.json`) |

Secrets live at https://github.com/demetrades2000-coder/nq-liquidity-engine/settings/secrets/actions (variables: the
Variables tab next to it). None is needed for the normal setup.

## How it works (for the curious)

- **Relay**: a free ntfy.sh topic named in `tools/web_public/push_relay.json` (not secret). When you allow notifications the
  app posts its push subscription there. A subscription alone cannot send anything: sending needs the private key.
- **Key**: with no `LE_VAPID_PRIVATE` secret, the workflow makes a key pair on its first run and keeps the private key in the
  GitHub Actions cache (`.le_push/vapid.json`, refreshed every run; never committed, never printed). The public key goes
  into data.json, the app subscribes with it.
- **Cloud** (`tools/cloud_monitor.py`): every run reads the relay, keeps the subscriptions in `state.json` on the private
  `dashboard` branch, and sends an entry notice for each new fill and an outcome notice for each finished trade (nothing
  older than 2 days). Keys already sent are kept in `state.json`; a "sent" marker on the relay tells the PC.
- **PC** (`engine/live.py`, `engine/ninjatrader.py`): the heartbeat publishes the PC's own public key
  (`data/push_pc_key.json` holds the private part, gitignored); the cloud seals the notification key to it in `state.json`;
  the PC opens it and sends the same two notices (NinjaTrader: when NinjaTrader reports the fill and when the bracket's stop
  or target fills). Before sending it checks the relay, so a trade the cloud already notified is not sent twice (and the
  other way round). Same notification tag per trade, so at worst a notice is replaced, never doubled.
- **App** (`tools/web_public/index.html`, `sw.js`): shows each push, counts it on the badge, opens the app at the trade when
  tapped, and keeps the subscription current on every open.
- Tests: `python -X utf8 -m tests.test_push` (payloads, relay, keys, de-dup, encryption).
