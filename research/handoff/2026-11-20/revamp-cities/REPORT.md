# revamp-cities REPORT (2026-11-20, branch night-revamp-cities)

1. **Olympus World rebuilt** (cities/world): real towers (octagons, setbacks, spires, pyramid caps) in 2 draws + their reflections; lit floors that stay clean at phone size; a downtown skyline; street lamps, light-trail traffic, 18 satellite towns + a far shore of cities, clouds, moon, aircraft.
2. **Sky follows the market clock** (ET): NQ cash session = golden hour, the hour round it = blue hour, else night (`?sky=night|blue|dusk` to force).
3. **Displays**: LED ticker rings round the Gate, ZEUS, Kalshi bot and Business show the live learning line, the PC / trade status and district counts.
4. **Cities front**: the "Olympus World" door is now a card with a real frame of the 3D city; the World's loading screen is a photo of the city (push-in).
5. **Speed**: JS per frame median 0.3 ms, worst 15 ms, 0 long tasks over 50 ms in 300 frames after load (two ~70 ms during load); GPU about 1.1-1.5x the old World in software GL; DPR <= 2, auto quality step-down, reduced motion = no flights, still LEDs, no aircraft.
6. **Bug found and fixed**: reflections made white/rainbow blobs (exp() overflow -> NaN in bloom) on the high tier.
7. Tests: test_world_page static 12/12 (5 new pins for the look); browser run: see bottom. Data City + intro/warp: see below.
8. Lead to wire: LEAD_WIRES.md (cache bump; recommended: Cities door opens the World).

Shots (390x844 @2x): world-0-before, world-1-night, world-2-golden-hour, world-3-street, world-4-led-display, cities-0-before, cities-1-world-door. Video: world.mp4.
