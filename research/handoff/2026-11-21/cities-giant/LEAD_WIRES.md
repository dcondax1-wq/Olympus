# cities-giant: what the lead wires

1. `tools/web_public/sw.js`: bump `CACHE` to the next number (cities/world changed: ow-main w8, ow-scene w6, ow-core w6, ow-shaders w5,
   world.css w4, world.json rebuilt with six districts).
2. `tools/perf_budgets.json` "cities": today's pc already breaks `lt_max` 2530 / `tbt` 5480 on this machine (2,715 / 6,100: one
   software-GL frame). Keep the guard and re-baseline after landing (`python -X utf8 tools/perf_sweep.py --lock --compare`), or raise
   to lt_max 3100 / tbt 6800 if the landing sweep agrees.
3. If `tools/world_build.py` runs on the PC's nightly build, nothing else: it now writes six districts and reads
   `tools/web_public/agency/factory/sites.json` (counts only).
4. docs: `docs/OLYMPUS_MAP.md` World row "four districts" -> "six arena districts" (rebuild with tools/olympus_map_build.py).
