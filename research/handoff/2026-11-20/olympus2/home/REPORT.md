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

## Round 3 (DATA TRUTH ask, ~11:00 ET): one "to payout" number everywhere
- Widget (Scriptable + Glance) and the Home cockpit used the PC card's raw `to_target` (the $750-ping line, e.g. $1,449) as "to payout".
  Now both run the payout coach (business/payoutcoach.js, the same inputs as pc_feed.js payoutLines) -> e.g. $949 at $25,401.38 / room $1,401.38,
  the number NQ / Trading / Board show. Scriptable has no coach: it says "payout: see Olympus" instead of a different number. Glance drops the
  "% of the way to the payout" bar for funded accounts (it was built on the raw number).
- Tags: widget w3, glance.html loads ../business/payoutcoach.js?v=1, glance.js 3; gate.js g14 (+ payoutcoach.js in the Home's script list).
- Tests: test_widget 37/37 (+ parity with pc_feed payoutLines on the fixture: $1,462.80 both, raw line $1,962.80 never shown), test_gate_page 88/88
  (+ funded ATLAS shows "$949 to payout", never $1,449). Shot: glance-payout-coach.jpg.
- Not adopted: age.js / age.css (they are on day-nqdash3 only, not on pc yet; loading them now would 404). Once they land on pc, the Home's
  "Last report X ago" line can switch to OLY_AGE.chip(..., 'pc').

## Round 4 (PERF ask, ~12:00 ET): the Cities front's long tasks
PERF measured `cities/` (the island map) with a 4.1 s worst task. Profiled at 4x CPU, 390 px: the 2D map (cities/agoramap.js) repainted its
whole cached "still" layer ~45 times while loading (the opening camera flight + ~500 data updates as the cities stream in) and kept redrawing a
phone-size canvas ~33 times a second forever. Fixes (agoramap.js g7):
- during a camera flight the cached picture is moved / zoomed to the new camera (one drawImage), repainted only past 0.8-1.5x zoom;
- new data repaints once it has been quiet for 0.3 s (2 s at most), not on every update;
- 3 s after the last touch / flight the map holds still (the sea and boats are decoration) until the next touch, flight or data.
Result (15 s after open, 4x CPU): long tasks 99 -> 26, their total 10.7 s -> 2.7 s, full repaints 45 -> 3. Left: two ~0.35 s tasks at boot
(three.js parse + building the 3D hub), not changed today. test_cities_page 257/257.

## Round 5 (A11Y FOR_home.md, ~12:30 ET): all 7 items
A11Y sweep (`tools/a11y_sweep.py --quick`, their branch, my files): **gate 82 -> 100, widget 82 -> 96, cities 85 -> 92** (datacity 85, not in the list).
1. cities live chip contrast: dark ink on the olive fill, light ink on the Ivory dark-green fill (both >= 4.5:1).
2. gate facts 44 px tall (compact mode too).
3. gate focus ring (`:focus-visible` on every link / button / the search) + gate now loads olympus/a11y.js (Dynamic Type, labels).
4. money strip: no list roles (they were half set).
5. cities `#chips` and widget `#code`: `tabindex="0"` + a name; #chips 44 px tall.
6. small text: gate door lines / hints / footer / hub lines / look names / cockpit lines 15 px, sub-lines >= 12 px; widget body in rem,
   code 12 px, FREE tag 12 px; cities dock labels (and Data City's) 12 px, World card subtitle 15 px, network labels 12 px.
7. Dynamic Type: the gate loads a11y.js; widget text moved to rem.
Left: cities filter chips' 13 px labels (short labels), the quality button's "LITE" 11.3 px (drawn by the kit), widget code block 12 px.
Tests: gate 88/88, widget 37/37, cities 257/257, datacity 194/194. Tags: gate.js g15, gate.css g17 (+ olympus/a11y.js in the Home's list).
