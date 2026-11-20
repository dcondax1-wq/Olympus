# olympus2 HOME + CITIES (2026-11-20, branch day-cities3, on top of pc 7b2bf6a2)

## What changed (plain words)
1. **Home = the daily cockpit, money first.** "Right now" sits right under the search, before the four doors, and holds on the first iPhone 13
   screen: PC status badge + age; the **open trade** if any ("Zlarior LONG 2 micros +$86 now · stop 21,380 · target 21,650", from the board
   card's position); a card per account (balance, $ to pass / to payout, today); **Drawdown left $X of $Y max loss** per account; **Today**;
   the trade window; **Decide** = the top open Decide card (business/decisions.json) with Claude's pick, else "Nothing waiting on you";
   **Kalshi K8** today (live legs won / lost today + the next live window in ET, from kalshi/k8.json). The doors start right below.
2. **Stale / missing data:** tested with a 5-minute report, quiet, stopped, 3 days old ("Old numbers", "last day", Bring the bots back),
   home.json missing or broken ("No numbers", window + decide + K8 still shown), and the last copy this phone saw ("Saved ... ago").
3. **Intros:** the Home intro plays once per New York day (`oly.homefx.day`), ends in 1.18 s, a tap/scroll skips it. The app intro
   (olympus/intro-app.js) is now 1.15 s (was 2.4 s), once per app per New York day (`oly.intro.d.<app>`), nothing on a repeat visit that day.
4. **Widget:** medium and large show every account + today, with an "Updated hh:mm" line (plus the source tag and age).
5. **World:** stops its 3D loop the instant you leave (any link, Home, Go to, the warp, the back button), so the jump out is not fighting
   the GPU; it resumes if you come back through the back button. Districts keep their live billboards (NQ / Kalshi / Money).

## Numbers (390 x 844 @2x)
| Check | Result |
|---|---|
| Home intro end / skip | 1.18 s after page start / a tap finishes it |
| Home 4x CPU: load, long tasks, worst, CLS | 418 ms, 3, 91 ms, 0 (earlier today; cockpit adds 2 small JSON reads) |
| World JS per frame (median / p95), low tier | 1.8 ms / 7.7 ms |
| World triangles / draw calls | 156,219 / 12 |
| App intro film | 1.15 s (< 1.2 s) |

## Tests (merged tree)
test_gate_page 86/86 (+ cockpit check: open trade, Decide, K8, Right now before the doors) · test_home_fx 19/19 (+ no intro on a repeat
visit the same day) · test_live_link 78/78 · test_world_page 30/30 (+ JS p95 and triangle cap) · test_app_intro 319/320 -> the 1 fail was the
40 KB size cap (now 39,743 B) · test_widget 36/36 (+ 'Updated hh:mm') · smoke 8/8 (earlier today).

## Not done / honest
- World frame time on a real iPhone 13 GPU cannot be measured here (software GL); JS per frame is the part we can measure.
- 73 app pages load intro-app.js as `?v=i10`; they belong to other slices, so the bump is in ASKS.md (works without it once caches refresh).

Shots: cockpit-1-live, cockpit-2-in-a-trade-decide, cockpit-3-light, cockpit-4-stale-3-days, cockpit-5-no-data. Video: home-first-then-repeat.webm
(first open with the intro, then the same-day repeat without it).

## Round 2 (lead priorities, ~10:00-10:30 ET)
- **4 accounts + trades on several accounts at once:** the Rapid EOD 25K (PC id "rapid") gets its card, drawdown tile and open-trade line
  (from its own account row's position); with 3+ accounts or 2+ trades the cockpit goes compact (one line a trade, the account's name on top
  of its drawdown tile) and all money stays on the first iPhone 13 screen (test: 4 accounts + 3 trades, bottom <= 844 px). gate g13 / css g15.
- **Ivory / light:** the cockpit was checked for contrast in dark and Ivory (no text under 4.5:1 in #now); the Cities front's Olympus World
  card now has a light version. The World itself stays a dark HUD over the 3D city (the sky follows the real sun).
- **World billboards:** the Rapid account reads "Rapid 25K".
- Tests: test_gate_page 87/87, test_world_page --static 14/14.
- Shots: cockpit-6-four-accounts-three-trades, cockpit-7-four-accounts-light, cities-ivory-world-card.
- Waiting on: A11Y FOR_home.md (day-a11y) and PERF ASKS.md (day-quality); not on GitHub yet at 10:30 ET.
