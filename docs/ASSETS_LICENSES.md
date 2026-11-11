# Asset licences (OLYMPUS site, `tools/web_public/assets/`)

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
