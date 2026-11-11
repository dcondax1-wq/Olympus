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
