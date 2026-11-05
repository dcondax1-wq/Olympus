# arena-citadel

Added a deterministic 3D skyline around the Arena colosseum: 176 instanced towers, illuminated facades, rooftop crowns, four roads and a stone outer ground. LITE uses 80 towers; high uses all 176. The city is decorative and does not claim that a building represents user data.

Checks: node --check passed for citadel.js and dress.js. The public dashboard mirror was sparse-cloned for a local preview, but Chromium is not installed in this environment, so a 390x844 screenshot was not produced. No live trading, bot, publisher, or shared kit files changed.

Wiring: after merge, publish the updated arena files and bump the site's service-worker cache if its deploy process requires it.