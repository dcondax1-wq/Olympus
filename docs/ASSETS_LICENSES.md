# Asset licences

Every downloaded asset in OLYMPUS is CC0 (public domain) and listed here (docs/NIGHT_BRIEF.md Round 5).

<!-- AUDIO:BEGIN (tools/audio_build.py writes this block) -->
## Audio (sound engine, olympus/sfx.js)

Licence checked on each source page (opengameart.org shows "License(s): CC0"; VCSL's README says CC0 1.0). Processed (trimmed, cleaned, normalised, looped, re-encoded) by tools/audio_build.py.

| asset | author | source | licence | files (tools/web_public/assets/audio/, .ogg + .m4a) |
|---|---|---|---|---|
| fantozzis footsteps grasssand stone | Fantozzi (submitted by qubodup) | https://opengameart.org/content/fantozzis-footsteps-grasssand-stone | CC0 | steps |
| different steps on wood stone leaves gravel and mud | TinyWorlds | https://opengameart.org/content/different-steps-on-wood-stone-leaves-gravel-and-mud | CC0 | steps |
| 51 ui sound effects buttons switches and clicks | Kenney | https://opengameart.org/content/51-ui-sound-effects-buttons-switches-and-clicks | CC0 | ui |
| 10 book page flips | StarNinjas | https://opengameart.org/content/10-book-page-flips | CC0 | scribe, ui |
| opening and closing a map sounds | Spring Spring | https://opengameart.org/content/opening-and-closing-a-map-sounds | CC0 | scribe, ui |
| rpg sound pack | artisticdude | https://opengameart.org/content/rpg-sound-pack | CC0 | coins, gear, ui |
| fantasy accessory sfx library | Vehicle (Jan Schupke) | https://opengameart.org/content/fantasy-accessory-sfx-library | CC0 | coins, gear, ui |
| 100 cc0 metal and wood sfx | rubberduck | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | CC0 | forge, gear, house |
| blacksmiths hammer | VishwaJai | https://opengameart.org/content/blacksmiths-hammer | CC0 | forge |
| sack of gold | Amarikah | https://opengameart.org/content/sack-of-gold | CC0 | coins |
| crowd shoutingspeaking ambience | StarNinjas | https://opengameart.org/content/crowd-shoutingspeaking-ambience | CC0 | arena, loop-crowd |
| applause in a large hall or church | eXpl0it3r | https://opengameart.org/content/applause-in-a-large-hall-or-church | CC0 | arena, loop-applause |
| fireplace sound loop | PagDev | https://opengameart.org/content/fireplace-sound-loop | CC0 | loop-fire |
| catching fire | themightyglider | https://opengameart.org/content/catching-fire | CC0 | house |
| windy ambient noise | Some Weirdo | https://opengameart.org/content/windy-ambient-noise | CC0 | loop-wind |
| park ambiences | Thimras | https://opengameart.org/content/park-ambiences | CC0 | loop-brook, loop-gusts |
| sea and river wave sounds | RandomMind | https://opengameart.org/content/sea-and-river-wave-sounds | CC0 | loop-sea |
| beach ocean waves | jasinski (submitted by qubodup) | https://opengameart.org/content/beach-ocean-waves | CC0 | nature |
| solo seagull sound effects | Rango Mango | https://opengameart.org/content/solo-seagull-sound-effects | CC0 | nature |
| bird chirping sounds | syncopika | https://opengameart.org/content/bird-chirping-sounds | CC0 | nature |
| amb morning sounds perfect loop | Kresiek The Furry | https://opengameart.org/content/amb-morning-sounds-perfect-loop | CC0 | loop-birds |
| crickets ambient noise loopable | Wolfgang_ | https://opengameart.org/content/crickets-ambient-noise-loopable | CC0 | loop-crickets |
| door open door close set | qubodup | https://opengameart.org/content/door-open-door-close-set | CC0 | house |
| pencil sounds | AntumDeluge | https://opengameart.org/content/pencil-sounds | CC0 | scribe |
| 20 rustles dry leaves | qubodup | https://opengameart.org/content/20-rustles-dry-leaves | CC0 | gear |
| VCSL: folk harp, anvil, hand chimes, bells, claps, frame drum, woodblock | Versilian Studios (VCSL, Versilian Community Sample Library) | https://github.com/sgossner/VCSL (README: CC0 1.0) | CC0 | arena, bells, forge, gear, harp, harp-lo, ui |
<!-- AUDIO:END -->
## 3D models and images (`tools/web_public/assets/`)

Only free assets: CC0 (public domain) art, or code under MIT. Every file under `tools/web_public/assets/` has a row here; `tests/test_people.py` checks
that every file in `assets/people/` is listed. Raw source packs are never committed, only the optimised files we use.

| Asset | Author | Source URL | Licence | Files |
|---|---|---|---|---|
| KayKit Character Pack: Adventurers 1.0 (Knight, Barbarian, Mage, Rogue, Rogue_Hooded bodies, heads, capes, helmet, round shield, mug, spellbook; 22 of its 76 animations) | Kay Lousberg (www.kaylousberg.com) | https://github.com/KayKit-Game-Assets/KayKit-Character-Pack-Adventures-1.0 (via https://cdn.jsdelivr.net/gh/KayKit-Game-Assets/KayKit-Character-Pack-Adventures-1.0@main/) | CC0 1.0 (http://creativecommons.org/publicdomain/zero/1.0/), pack file `LICENSE.txt` | `tools/web_public/assets/people/cast.glb` |

## Notes
- `cast.glb` is our rebuild of the pack (`tools/people_cast_build.mjs`): the five characters' parts on one shared skeleton, the colour atlas baked into vertex
  colours with a per-vertex slot so every Olympus person gets their own Greek colours (bronze, olive, terracotta, marble, gold, ink), the IK helper bones
  dropped, meshopt + quantised (EXT_meshopt_compression, KHR_mesh_quantization). Our own faces (mouth, blink, brows), Greek accessories (laurel, hammer,
  scroll, coin pouch, lantern, owl) and the extra animations (wave, talk, nod, shrug, think, slump and the work loops) are made in code (`olympus/people-rig.js`).
- The pack's licence text (KayKit Adventurers 1.0, `LICENSE.txt`): "License: (Creative Commons Zero, CC0) http://creativecommons.org/publicdomain/zero/1.0/
  This content is free to use in personal, educational and commercial projects. Support me by using a brand resource provided in this pack or by crediting
  Kay Lousberg, www.kaylousberg.com (this is not mandatory)". We credit Kay Lousberg in the People lab and here.
- Code: three.js r160 add-ons vendored in `olympus/three-addons/` (GLTFLoader.js, SkeletonUtils.js, BufferGeometryUtils.js: MIT, three.js authors;
  meshopt_decoder.module.js: MIT, Arseny Kapoulkine). See `olympus/three-addons/LICENSE`.

## UI icons (AGORA v2 design system, olympus/agora-ui.js)

| asset | author | source | licence | files |
|---|---|---|---|---|
| AGORA line icons (68: back, chevron, temple, column, laurel, amphora, owl, lyre, wave, chart, wallet, ...) | OLYMPUS (drawn for this project, 2026-11-11) | original work, `window.AGORA.ICONS` | our own work, dedicated CC0 | `tools/web_public/olympus/agora-ui.js` (path data inline, no files) |
## Art assets and their licences

Every file under `tools/web_public/assets/` is public domain (CC0 1.0, https://creativecommons.org/publicdomain/zero/1.0/).
No credit is required; we credit the authors here anyway. Only the optimised files we use are committed (never the raw packs).
Loader: `tools/web_public/olympus/env-kit.js` (every file is optional: a scene builds with plain colours when one fails).
How they were made: textures resized to 512 px webp (albedo normalised to a mean of 0.5 with AO in alpha; normal xy + roughness;
a 256 px LITE albedo), HDRIs box-filtered to 256 x 128 RGBE, models packed with gltf-transform (weld, simplify, 256-512 px webp
textures, quantize, meshopt). The three.js loaders vendored for them (`olympus/three-addons/GLTFLoader.js`, `RGBELoader.js`,
`BufferGeometryUtils.js`, `meshopt_decoder.module.js`) are three.js r160 (MIT, see `three-addons/LICENSE`).

## Tests

`tests/test_olympus_fx.py` (section "env-kit") checks that every file under `assets/` has a row below, that each row says CC0,
and that the whole folder stays inside the size budget (<= 25 MB for the site, <= 6 MB for any one scene's first load).

## Surfaces (Poly Haven textures, CC0) -> `assets/tex/<name>_c.webp`, `<name>_n.webp`, `<name>_l.webp`

| Asset | Author | Source | Licence | Files |
|---|---|---|---|---|
| marble (Marble 01) | Rob Tuytel | https://polyhaven.com/a/marble_01 | CC0 | assets/tex/marble_c.webp, marble_n.webp, marble_l.webp |
| mosaic (Marble Mosaic Tiles) | Amal Kumar | https://polyhaven.com/a/marble_mosaic_tiles | CC0 | assets/tex/mosaic_c.webp, mosaic_n.webp, mosaic_l.webp |
| plaster (Painted Plaster Wall) | Amal Kumar | https://polyhaven.com/a/painted_plaster_wall | CC0 | assets/tex/plaster_c.webp, plaster_n.webp, plaster_l.webp |
| roof (Clay Roof Tiles 02) | Amal Kumar | https://polyhaven.com/a/clay_roof_tiles_02 | CC0 | assets/tex/roof_c.webp, roof_n.webp, roof_l.webp |
| terracotta (Terracotta Floor Tiles) | Dimitrios Savva | https://polyhaven.com/a/terracotta_floor_tiles | CC0 | assets/tex/terracotta_c.webp, terracotta_n.webp, terracotta_l.webp |
| cobble (Cobblestone Floor 01) | Rob Tuytel | https://polyhaven.com/a/cobblestone_floor_01 | CC0 | assets/tex/cobble_c.webp, cobble_n.webp, cobble_l.webp |
| paving (Seaworn Stone Tiles) | Dimitrios Savva | https://polyhaven.com/a/seaworn_stone_tiles | CC0 | assets/tex/paving_c.webp, paving_n.webp, paving_l.webp |
| ashlar (White Sandstone Blocks 02) | Rob Tuytel | https://polyhaven.com/a/white_sandstone_blocks_02 | CC0 | assets/tex/ashlar_c.webp, ashlar_n.webp, ashlar_l.webp |
| sand (Sand 01) | Rob Tuytel | https://polyhaven.com/a/sand_01 | CC0 | assets/tex/sand_c.webp, sand_n.webp, sand_l.webp |
| ground (Rock Ground) | Rob Tuytel | https://polyhaven.com/a/rock_ground | CC0 | assets/tex/ground_c.webp, ground_n.webp, ground_l.webp |
| wood (Oak Wood Planks) | Dimitrios Savva | https://polyhaven.com/a/oak_wood_planks | CC0 | assets/tex/wood_c.webp, wood_n.webp, wood_l.webp |
| cloth (Rough Linen) | colormass, Rico Cilliers | https://polyhaven.com/a/rough_linen | CC0 | assets/tex/cloth_c.webp, cloth_n.webp, cloth_l.webp |
| grass (Sparse Grass) | Amal Kumar | https://polyhaven.com/a/sparse_grass | CC0 | assets/tex/grass_c.webp, grass_n.webp, grass_l.webp |
| texture table (made here from the scans above) | OLYMPUS | tools/web_public/assets/tex/tex.json | CC0 | assets/tex/tex.json |

## Light (Poly Haven HDRIs, CC0) -> `assets/env/hdri/<time>.hdr`

| Asset | Author | Source | Licence | Files |
|---|---|---|---|---|
| golden (Qwantani Late Afternoon, pure sky) | Greg Zaal, Jarod Guest | https://polyhaven.com/a/qwantani_late_afternoon_puresky | CC0 | assets/env/hdri/golden.hdr |
| day (Kloofendal 48d Partly Cloudy, pure sky) | Greg Zaal, Jarod Guest | https://polyhaven.com/a/kloofendal_48d_partly_cloudy_puresky | CC0 | assets/env/hdri/day.hdr |
| overcast (Kloofendal Overcast, pure sky) | Greg Zaal | https://polyhaven.com/a/kloofendal_overcast_puresky | CC0 | assets/env/hdri/overcast.hdr |
| dusk (Qwantani Dusk 2, pure sky) | Greg Zaal, Jarod Guest | https://polyhaven.com/a/qwantani_dusk_2_puresky | CC0 | assets/env/hdri/dusk.hdr |
| night (Qwantani Night, pure sky) | Greg Zaal, Jarod Guest | https://polyhaven.com/a/qwantani_night_puresky | CC0 | assets/env/hdri/night.hdr |

## Props (KayKit by Kay Lousberg, www.kaylousberg.com, CC0) -> `assets/env/kay_*.glb`

| Asset | Author | Source | Licence | Files |
|---|---|---|---|---|
| KayKit Dungeon Remastered 1.0 (barrels, boxes, crates, candles, chair, chests, coin stacks, kegs, shelves, stool, tables, torches, trunks, bottles, plates, sword and shield, banners, rubble) | Kay Lousberg | https://github.com/KayKit-Game-Assets/KayKit-Dungeon-Remastered-1.0 (Assets/LICENSE.txt: CC0) | CC0 | assets/env/kay_dungeon.glb |
| KayKit Medieval Hexagon Pack 1.0 (tent, barrel, crates, sack, wheelbarrow, bucket, pallet, lumber, stone, flags, weapon rack, ladder, trees, rocks) | Kay Lousberg | https://github.com/KayKit-Game-Assets/KayKit-Medieval-Hexagon-Pack-1.0 (LICENSE.txt: CC0) | CC0 | assets/env/kay_camp.glb |

## Hero models (Poly Haven, CC0) -> `assets/env/ph_*.glb`

| Asset | Author | Source | Licence | Files |
|---|---|---|---|---|
| Marble Bust 01 | Rico Cilliers | https://polyhaven.com/a/marble_bust_01 | CC0 | assets/env/ph_marble_bust_01.glb |
| Ceramic Vase 02 (amphora, tinted terracotta) | James Ray Cock | https://polyhaven.com/a/ceramic_vase_02 | CC0 | assets/env/ph_ceramic_vase_02.glb |
| Ceramic Vase 04 (jug) | James Ray Cock | https://polyhaven.com/a/ceramic_vase_04 | CC0 | assets/env/ph_ceramic_vase_04.glb |
| Brass Goblets | Tina | https://polyhaven.com/a/brass_goblets | CC0 | assets/env/ph_brass_goblets.glb |
| Pomegranate 01 | Oliver Harries | https://polyhaven.com/a/food_pomegranate_01 | CC0 | assets/env/ph_food_pomegranate_01.glb |
| Brass Vase 02 (ewer) | Rico Cilliers | https://polyhaven.com/a/brass_vase_02 | CC0 | assets/env/ph_brass_vase_02.glb |
| Clay Planter Pot | Amal Kumar | https://polyhaven.com/a/planter_pot_clay | CC0 | assets/env/ph_planter_pot_clay.glb |
| Stone Fire Pit | Sebastian Platen | https://polyhaven.com/a/stone_fire_pit | CC0 | assets/env/ph_stone_fire_pit.glb |
| Carved Wooden Plate | Jan Martens | https://polyhaven.com/a/carved_wooden_plate | CC0 | assets/env/ph_carved_wooden_plate.glb |
| Worn Wooden Bookshelf | Ulan Cabanilla | https://polyhaven.com/a/wooden_bookshelf_worn | CC0 | assets/env/ph_wooden_bookshelf_worn.glb |
| Horse Statue 01 | Rico Cilliers | https://polyhaven.com/a/horse_statue_01 | CC0 | assets/env/ph_horse_statue_01.glb |
| Lion Head | Tina | https://polyhaven.com/a/lion_head | CC0 | assets/env/ph_lion_head.glb |
