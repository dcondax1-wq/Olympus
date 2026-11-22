# web / SHOWCASE: lead wires

1. **Branch:** this session may only push to `day-cities3`; the showcase commits are there (on top of pc 4f637df3). Merge `origin/day-cities3`
   (it also carries my earlier HOME + CITIES commits after b267d97c: 42cc3d20 / 7b960d4d).
2. **Hub link (agency/index.html is the hub team's):** a card or button "Your website (what clients see)" -> `showcase/`.
3. **Demos contract (demos team):** the showcase links `../demos/#<slug>` for the 8 slugs in brand.json (restaurant, salon, home-services,
   dentist, gym, real-estate, landscaping, auto). If the demos team uses other paths, change only `demoHref()` in showcase.js (one line) or the slugs in brand.json.
4. Optional: `sw.js` needs nothing (agency/ is an own folder). If the agency site is ever published on its own domain, set `site_url` + canonical
   + og:image absolute URL in brand.json / index.html.
