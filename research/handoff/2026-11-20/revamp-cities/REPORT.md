# revamp-cities REPORT (2026-11-20, branch night-revamp-cities; helpers night-introwarp + night-revamp-datacity merged in)

1. **Olympus World rebuilt** (cities/world): varied towers (octagons, setbacks, spires, caps) in 2 draws + reflections; clean lit floors at phone size; a downtown skyline; street lamps, light-trail traffic, 18 satellite towns + a far shore, clouds, moon, aircraft.
2. **Sky on the market clock** (ET): NQ cash session = golden hour, the hour round it = blue hour, else night (`?sky=night|blue|dusk` forces it).
3. **Displays**: scrolling LED rings on the Gate, ZEUS, Kalshi bot and Business towers show the live learning line, PC / trade status, district counts.
4. **Cities front**: island towers are night stone + lit windows (not clay); the World door is a card with a real frame of the 3D city; the World loads behind a photo of itself.
5. **Data City** (helper): blue-hour sky, horizon fog (the old fog was near-black from a colour-space bug), dark glass with window grids, sodium streets, head/tail lights, calmer bloom, clock no longer shows day during Asia.
6. **Intro + jump** (helper): night skyline whose windows switch on in waves, then OLYMPUS; the jump flies through city lights. entry.js 51 -> 44.5 KB (budget 56).
7. **Speed** (World): JS per frame median 0.3 ms, worst 15 ms, 0 long tasks > 50 ms in 300 frames after load; GPU ~1.1-1.5x the old World (software GL); DPR <= 2, auto step-down; reduced motion = no flights, still LEDs, no aircraft.
8. **Bug fixed**: white/rainbow blobs in reflections on the phone tier (exp overflow -> NaN in bloom).
9. **Tests**: smoke 8/8, world_page 27/27 (+5 new look pins), warp 33/33, cities_page 228 pass / 0 fail then crashes in section l (Hellas villager talk) - SAME crash on the base commit, not ours.
10. datacity 193/194: the 1 fail (phone triangle budget 250,134 > 250,000) and 7 node-suite fails are pre-existing on base (stale version pins, NEON undefined). app_intro 318/320 (2 timing checks under load, intro-app.js untouched).
11. **Lead**: LEAD_WIRES.md (sw cache bump, entry e2 + warp w3 bumps with test pins, recommended: Cities door opens the World).

Shots (390x844 @2x): world-0-before, world-1-night, world-2-golden-hour, world-3-street, world-4-led-display, cities-0-before, cities-1-world-door, datacity-before, datacity-after-1/-2, intro-1/-2, warp-1/-2.
Videos: world.mp4 (7 s: intro dive, warps to NQ and Kalshi), intro-warp.mp4 (6.6 s).
