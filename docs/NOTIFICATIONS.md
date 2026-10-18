# Phone notifications: every fill and every outcome, in your app

**What it does.** Your Home Screen app (Liquidity, https://demetrades2000-coder.github.io/nq-dashboard/) gets a notification:

- when a trade **fills**: side, micros, entry, stop, target, $ at risk and the setup (what was swept, the target);
- when a trade **ends**: target, stop, breakeven or end of day, with R, $ and the MFFU eval balance after it (half size from
  the weekly stop is noted);
- when the always-on PC bot **goes silent** during a session, and when **eval timing** changes.

It is free (Web Push: Apple delivers it, like any app notification). Telegram and Discord are no longer needed and are
off. Every notice also lands in the app's **Activity** page (System -> Activity, and a card on Today), which works even
before notifications are on. The app icon shows a badge with the number of new ones.

Who sends what:

| Notice says | Comes from | How fast |
|---|---|---|
| **Cloud paper** | the cloud paper bot (GitHub Actions, PC off) | at its next check, every 30 min on market days 02:00-16:25 ET (so up to ~30 min after the fill; GitHub can add a few minutes) |
| **PC paper** / **PC NinjaTrader Sim** | the PC bot, while the PC is on | a few seconds after the fill (NinjaTrader: when NinjaTrader reports the fill) |

Each notice is sent once. When both the cloud and the PC trade the same strategy you get both, each clearly labelled.
To have only the PC's while the PC bot runs: add the repository **variable** (not secret) `LE_PUSH_DEFER_TO_PC` = `1`.

Paper only, as always: notifications never place or change an order.

---

## One-time setup (about 5 minutes, all from the iPhone)

You need iOS 16.4 or later, and the app must be opened **from the Home Screen** (notifications do not work in a Safari tab).

### Step 1. Put the app on the Home Screen (skip if it is already there)

1. Open https://demetrades2000-coder.github.io/nq-dashboard/ in Safari.
2. Tap **Share** -> **Add to Home Screen** -> **Add**.
3. Close Safari and open **Liquidity** from the Home Screen.

### Step 2. Turn notifications on in the app

1. In the app: **System** -> **Settings** (or the "Get a notification for every fill" card on Today -> **Set up**).
2. If you see **Make the keys on this phone**, tap it once. This makes the key pair on your phone. (The other way: run
   `python tools/push_keys.py` on the PC; see "Keys made on the PC" below.)
3. Tap **Turn on notifications**, then **Allow**.
4. The card now shows one or two boxes with a **Copy** button:
   - **Key · secret LE_VAPID_PRIVATE**: only when you made the keys on the phone. Private: it goes only into GitHub.
   - **This phone's code · secret LE_PUSH_SUBS**: always.

### Step 3. Paste them into two GitHub Secrets

Open https://github.com/demetrades2000-coder/nq-liquidity-engine/settings/secrets/actions (the app links there too) and
tap **New repository secret**:

| Name | Secret (paste) |
|---|---|
| `LE_VAPID_PRIVATE` | the key from the app's first box (or from `tools/push_keys.py`) |
| `LE_PUSH_SUBS` | the code from the app's "This phone's code" box |

Tap **Add secret** after each. Then, back in the app, tap **I saved it: forget the key here** (the phone does not need
the private key any more).

### Step 4. Check it

- Wait for the next cloud run (every 30 min on market days), or start one now: GitHub -> **Actions** -> **cloud-monitor**
  -> **Run workflow** -> tick **Send a test notification** -> **Run workflow**. A "Test notification" arrives in about a
  minute.
- The app's notification card then says **on** (the cloud lists this phone). The dashboard branch README shows
  "Notifications: app notifications on: 1 device(s)".

### The PC bot too (optional, when the PC is on)

PC dashboard (http://localhost:8766) -> **Alerts** -> **Phone app notifications**: paste the same private key and the
same phone code -> **Save** -> **Send test**. They are stored only on the PC, in `data/push.json` (never committed).

---

## Keys made on the PC instead of the phone

```
python tools/push_keys.py
```

It prints the **private key** (put it in the GitHub Secret `LE_VAPID_PRIVATE`; never in a chat or a file in the repo),
writes the public key to `tools/web_public/push_key.json` (not secret: commit it so the app finds it before the first
cloud run) and saves both in `data/push.json` for the PC bot. Then do step 2 (the app shows only the phone code) and
add the phone to the PC bot with `python tools/push_keys.py --add-sub '<the code>'` or the PC dashboard card.

## More phones

Do step 2 on the other phone and save its code as a new secret `LE_PUSH_SUBS_2` (a third: `LE_PUSH_SUBS_3`). A GitHub
Secret cannot be read back, so each phone gets its own. (One secret can also hold several codes one after another.)

## When something is off

| The app says | Do this |
|---|---|
| "On iPhone, notifications work in the Home Screen app" | Open Liquidity from the Home Screen, not from Safari. |
| **blocked** | iPhone Settings -> Notifications -> Liquidity -> Allow Notifications, then tap Turn on again. |
| **waiting for the code** | The secret `LE_PUSH_SUBS` is missing or holds another code: paste this phone's code again (Update secret). It turns **on** after the next cloud run. |
| **expired** | Apple renewed the phone's subscription. Tap **Turn on again** and update `LE_PUSH_SUBS` with the new code. |
| "The cloud uses a different key" | The keys changed. Tap **Turn on again** and update `LE_PUSH_SUBS`. |

## Telegram / Discord

Off since 2026-10-18 (the app replaces them). The code stays: set the repository variable `LE_ALERTS_CHAT` = `1` (cloud)
or start the PC server with `LE_ALERTS_CHAT=1` (or add `"alerts": {"chat": true}` to `live_model.json`) to turn them back on.

## How it works (for the curious)

- `engine/push.py`: builds the notices, keeps each one to a single send (de-dup keys), and sends Web Push (pywebpush when
  installed, else a small built-in sender that needs only `cryptography`). Nothing configured = it does nothing.
- `tools/cloud_monitor.py`: after each run, a notice for every new fill (from the model's entry and open position) and
  every new outcome (from the paper ledger, with the eval balance). Keys already sent are kept in `state.json` on the
  `dashboard` branch, with the last 80 notices for the app's Activity page. Nothing older than 2 days is ever sent.
- `engine/live.py` (PC paper fills and every routed outcome) and `engine/ninjatrader.py` (NinjaTrader's reported fill and the
  bracket's stop / target fill): sent in the background so routing never waits; keys in `data/push_sent.json`.
- `tools/web_public/sw.js`: shows each push, counts it on the badge and opens the app at that notice when tapped.
- Tests: `python -X utf8 -m tests.test_push`.
