# Art assets and their licences

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
