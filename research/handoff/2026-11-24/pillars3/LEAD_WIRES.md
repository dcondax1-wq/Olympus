# day-pillars3: lead-only wiring

1. Root `tools/web_public/sw.js`: CACHE `le-public-v212` -> `le-public-v213` (the only item `python tools/bump_versions.py --check --base origin/pc` flags:
   pillars-data.json, cities/world/index.html, and the harmonia / helios / widget / world manifests have no ?v=).
   Do NOT run `bump_versions.py --apply` without `--base origin/pc`: with no base it also bumps jarvis/kalshi/web_next caches that this branch did not touch.

## What changed
- `tools/build_pillars.py` reads the real day-marketlearn shape (`pillars.<id>.lessons` strings + `read`); pillars-data.json rebuilt:
  LIT 5, ATLAS 4, BLITZ 5 lessons (one "Now:" line from today's market read + the lessons, each with its z / weak label as the file gives it),
  ORDER FLOW none -> the panel says "Waiting". SAMPLE banner gone. pillars.js ?v=p4, mind.js ?v=m8.
- test_homescreen 6/6 (all four reds were pre-existing on pc 66e4ddd5):
  cities (app path cities/world/) had no manifest -> added cities/world/manifest.webmanifest + link;
  harmonia + helios manifests listed PNGs that never existed -> now point at the shared jarvis/icon-*.png (same as their apple-touch-icon;
  their own icon.svg is brown, so not rasterized); widget lacked mobile-web-app-capable + manifest link, and its manifest lacked a maskable PNG -> added.
