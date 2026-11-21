# research-hub-city: what the lead wires

1. After the Research Hub session pushes `tools/web_public/research/hub.json`: rebuild the World on the landing:
   `python -X utf8 tools/world_build.py` (then `python -X utf8 -m tests.test_world_build`).
2. The hub page's "See it in the city" link: `../cities/world/?fly=<id>` (relative to `research/`).
3. `tools/web_public/sw.js`: bump `CACHE` (cities/world: ow-main w9, ow-core w7, world.css w5).
