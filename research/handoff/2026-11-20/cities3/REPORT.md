# cities3 REPORT (2026-11-20, branch day-cities3): modern cities, Home money row, intro, sounds, bigger widget, bottom-bar fix

Nothing in engine/, server.py, live models, accounts, scripts or lead-only files was touched. Paper only; no orders, no keys.

## What changed (plain words)
1. **Home: one-glance money row.** Right now shows a swipeable card per account: Zlarior 50K, ATLAS 25K (funded), Zlarior 25K #2 (and Rapid
   when the PC reports it). Each card: balance, a drawdown-room bar ("Room $1,025 of 2K"), "$3,807 to pass" or "$1,963 to payout",
   today's $. A Kalshi card (balance, today) follows. The total for the day sits above. Every card is a tap to the detail (Aegis / MFFU page / Kalshi).
   It counts up on arrival and springs on press. Layout shift stays 0 (placeholders hold the space); Right now and "Your six" still start on
   the first iPhone 13 screen. The trade window is now one slim line.
2. **Home intro under 1.2 s and skippable.** The stagger ends 1.18 s after page start (was ~1.6 s); the first tap, key or scroll finishes it at
   once (no page restyle, so no lag spike).
3. **The World: sky from the real New York sun.** Day, sunrise/sunset (golden), blue hour, night, computed from the sun's height over NYC
   (sunrise 6:50 / sunset 16:31 today). New daylight look: blue-grey glass, stone, bright water and streets, white clouds, sun glow; lamps,
   searchlights and traffic fade in daylight. The header says it: "Day · 10:12 ET · 4 districts ...". `?sky=night|blue|dusk|day` forces one.
4. **The World: live billboards.** Real text pinned over the ZEUS tower (NQ price + each account's balance and today), the Kalshi tower
   (balance, today, all time, bot on) and the Business tower (today's $ for all accounts, room per account, $ to pass). Numbers come from
   the PC's 15-minute feed and kalshi.json; a missing number is left out, never made up. Labels step aside so they never overlap.
5. **Glitch fixed: the "LED displays" were black rings.** A code line had slipped inside a comment, so the bands had no colour since the last
   revamp. They now glow with the live lines (72 letters a row).
6. **Sounds, honouring the Settings switch.** The World used to play taps even with Sound off; now every World sound (open, swipe, a soft
   chime on arrival, a quiet city bed) plays only when the owner turned Sound ON, never while Jarvis talks. Home money cards use the
   existing soft tap (already gated).
7. **Bigger widget (Scriptable, w2).** Large shows every account (rich rows up to 3, compact one-line rows past that), medium now shows all
   accounts instead of "+1 more", iPad extra-large up to 6; Kalshi line shows the real balance + today from kalshi.json; a guard stops a
   duplicate account when one copy's balance is off. Glance page shows Kalshi's balance too.
8. **Bottom of the screen (iPhone 13 / 15 Pro Max).** Inside the Jarvis frame iOS reports a 0 safe area, so the World / Cities / Data City
   docks sat on the home-bar line. New `cities/frame-safe.js` (+ Data City's own copy) borrows the parent's real bottom inset when the frame
   reaches the screen bottom: dock 10 px -> 44 px off the edge with a 34 px home bar (checked in Chromium with a faked inset).
9. **Speed.** Sun direction and light colour now worked out once a frame on the CPU; the daylight sun glow only on the sky dome; no blur
   behind the billboards (it re-blurs every frame over a live canvas).
10. **Tests fixed on the way:** Data City node suites 4/9 -> 7/9 green (frozen version pins -> "is versioned").

## What did NOT change / honest notes
- The per-app 2.4 s film (olympus/intro-app.js) is unchanged (plays once per app per launch, tap skips it). Say the word and it goes to ~1.2 s.
- Payout line on the Home uses the PC's `to_ask` when present, else the card's to_target (same number the widget calls "to payout").
- Software-GL timing: in this sandbox every World frame is GPU work done on the CPU (SwiftShader). At 4x CPU slowdown a frame is ~1.4 s on
  the base commit and ~1.8 s now (noisy, +/-0.2 s between runs); that is the software GPU, not phone JavaScript. The "no task > 200 ms"
  rule cannot be met by any 3D build here, base included. JavaScript per frame stays tiny (median 1.7 ms, test_world_page).
- 2 Data City node checks still fail on old markup words (map_rescue, satellite_network), same on the base commit.

## Numbers (390 x 844 @2x)
| Page | Measure | Result |
|---|---|---|
| Home (4x CPU) | load event / long tasks / worst / CLS | 418 ms / 3 / 91 ms / 0 |
| Home | intro ends / tap skips | 1.18 s after page start / yes (0 running after a tap) |
| World | first frame after module / draw calls / instanced buildings | 250 ms / 12 / 12,080 |
| World | JS per frame (median, low tier) | 1.7 ms |

## Tests
smoke 8/8 · test_gate_page 85/85 · test_home_fx 18/18 · test_world_page 29/29 (+3 new pins: real-sun sky, billboards, sound switch / frame safe
area / LED colour) · test_cities_page 257/257 · test_datacity 194/194 (phone triangle caps kept) · test_widget 34/34 · node test_datacity_*.mjs 7/9
(2 pre-existing). Not run: test_warp, test_app_intro (warp.* and intro-app.js untouched), test_win_scripts (never).

## Files
Shots (390x844 @2x unless named): home-1-money-row, home-2-iphone15promax (430x932), world-1-night, world-2-sunset, world-3-day,
world-4-nq-district, world-5-money-district-day, widget-glance. Videos: world-flyin.webm (16 s, the fly-in at sunset), home-intro.webm (4 s).
Lead: LEAD_WIRES.md (nothing required).
