# Kalshi K8: your Monday (Nov 23) checklist, one page

Goal: real bets start on **Monday's 4:45 PM ET window** ($55, $2.50 a bet). Expect about **+$12 a week** if it works like its
history (+$6 if it is weaker). The bot stops itself before a bad day passes -$8, a bad week -$13.75, or a dip of -$19.25 from its best point.

## Before 4:30 PM ET Monday (10 minutes, at the PC or on your phone)

| # | You do | You should see |
|---|---|---|
| 1 | PC on, awake, internet on (the bot runs there) | the phone's Olympus Kalshi page: "K8 today" card, **PAPER**, next window 4:45 PM |
| 2 | kalshi.com > Account > Profile Settings > API Keys > **Create New API Key** | a Key ID and a private key (keep the page open; never send them to anyone, not even Claude) |
| 3 | phone: open your PC link with **`:8444/kalshi-live/`** at the end, paste the Key ID + the key, tap **Save** | "Key OK · balance $55.00" |
| 4 | bet size: tap **$2.50** (marked "the rule") | $2.50 picked (the stops stay -$8 a day, -$13.75 a week, -$19.25 from the best point) |
| 5 | type exactly `I ACCEPT KALSHI LIVE RISK` and tap **Start LIVE** | the page says live is ON; within 15 minutes the Olympus Kalshi page shows **LIVE** instead of PAPER |

If it says "the executor was updated since you armed it" or "the plan changed", just type the phrase again (step 5). That is the
safety lock, not an error.

## At 4:45 PM ET

| When | You should see |
|---|---|
| 4:45:20 PM | a push: **"Kalshi LIVE 16:45 ET: 2 bets in"** (gold UP, silver UP, about 4-5 contracts at 45-58c, about $2.30-2.50 each) |
| about 5:01 PM | a push with the results (e.g. "gold WON +$2.06, silver LOST -$2.57") and today's $ |
| about 5:05 PM | the day summary push |
| Tuesday 5:15 AM | the gold DOWN bet (one push), result about 5:31 AM |

On kalshi.com > Portfolio you see the same bets. Nothing else should appear there.

## If something looks wrong

- **Tap STOP** on the `:8444/kalshi-live/` page. Live is OFF at once, open bets just settle by themselves within 15 minutes.
- A **"STOPPED"** push means a stop or a safety check did its job (the push says which). Don't restart it alone: tell Claude.
- A push saying **"no clear answer on the order"** means Kalshi's reply was lost. The bet is counted as placed (the stops
  assume it lost) and booked from Kalshi's fills after the result. Nothing to do.
- Never add money for a while (the rule is sized for $55). Never pick $8 / $10 / $15: the day stop would block those bets anyway.

Detail: `docs/KALSHI.md` (what runs where), `research/writeups/kalshi-k8-live-2026-11-21.md` (the safety check + the numbers).
