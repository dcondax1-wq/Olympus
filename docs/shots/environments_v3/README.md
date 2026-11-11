# Environment art v3: before / after (2026-11-11)

390 x 844 phone shots. `-before` = agora-release before this pass, `-after` = with `olympus/env-kit.js` (CC0 scans, HDRI light,
KayKit + Poly Haven props, the Doric kit). After shots of the 3D scenes use `?gpu=1` (full surfaces: this machine is a software
GL, where the kit falls back to one-tap surfaces and no hero models to keep frame times close to before). Numbers: the scene's own
draw / triangle counters (Symposium `drawCalls()` / `triangles()`, Ergasterion `floor().stats()`, the env lab `measure()`).

| Scene | Before | After |
|---|---|---|
| Symposium hall (high) | flat brown floor, plain cylinders, box couches, a brown torus beam; 31 draws, 102k tris | marble floor with a mosaic ring and Greek-key borders, mosaic medallion, 15 fluted Doric columns, painted triglyph frieze, timber ceiling, round wall with oxblood dado, key band, Pompeian red frescoes, bronze shields, 3 stone doorways, marble busts on plinths, terracotta amphorae, klinai with linen mattresses and bolsters, bronze tripod braziers, bronze cups, plates of food, an ewer, wall torches, golden HDRI; 29 draws, 156k tris (<= 160k) |
| Ergasterion (high) | untextured boxes, plain cylinders, cone tents | marble-slab walls and floors (scan, per-hall tints), fluted columns, forged anvils, props in every hall (gold chest + coins, banners, sword and shield, crates, barrels, shelves of bottles, candles, trunks, bookshelves), KayKit tents + supplies + rocks + trees in the camp, sand scan; 42 draws (<= 45), 135k tris (<= 150k) |
| Athens / Hellas | flat vertex colours | stone, plaster and roof-tile scans (one tap, Lambert look kept), rocky ground; same draws |
| Colosseum | flat sand and stands | raked sand scan, sandstone ashlar stands, plaster podium, marble arcade, HDRI; same draws |
| Jarvis home doorways | plain boxes | marble scan on the doorways, paving scan, fluted columns (same draws). Note: on this machine the 3D courtyard window shows almost nothing at 390 px both before and after (framing, not the materials) |
| Env lab (high / LITE) | - | a temple, a house, couches, braziers, an anvil, props: 27 / 20 draws, 41k / 16k tris, 23 / 4.3 MB textures |
