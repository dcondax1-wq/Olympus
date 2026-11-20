# The city look (revamp-cities, 2026-11-20): one direction for every city page

Owner: "the quality looks like a 2000's computer built it" / "not some 2000's looking play-doh". Target: a modern premium
night city (think Apple Maps 3D at dusk, a film's establishing shot), not neon soup and not clay.

**Sky and air**
- Blue hour to night: zenith #05080f-#0a1022, mid #14203a, a warm low horizon glow (#ff9a5a at ~15%) from the city's own light.
- Stars (tiny, sparse, twinkle slowly), a soft moon with halo; thin clouds lit from below by the city (orange underside).
- Height fog: distance fades INTO the horizon colour (exponential, denser near the ground), so the skyline has real depth layers.
- Day/night follows the market clock (ET): RTH 9:30-16:00 = dusk/golden blue hour, after hours = night, weekend = deep night.

**Buildings**
- Silhouettes vary: setback tiers, slim towers, podiums, crowns/spires on the tallest, rooftop boxes; never a field of equal cubes.
- Facades dark and cool (#0d121c to #1a2230), glass with a fresnel sky reflection (brighter at grazing angles), edges catch the moon.
- Windows: an emissive grid per floor/bay in the shader, each window randomly on/off/dim, warm (#ffcf8f) homes / cool (#cfe3ff)
  offices, a slow random flicker of a few; a brighter lobby band at street level; mullions; tops darker than lower floors at night.
- District colour only as an ACCENT (roof crown line, a sign, the light pool on the ground), never the whole building tinted.
- Base ambient occlusion (darker near the ground), aviation red blinkers on the tallest tops.

**Streets and motion**
- Asphalt with faint lane lines, pavements, warm sodium street-light pools (#ffb46b) along avenues.
- Traffic: white head-light / red tail-light streaks moving along the roads (instanced, GPU-animated).
- Camera: slow, gentle, eased; idle drift. Reduced motion = no flights, just fades.

**Glow**
- Bloom only on what is really bright (windows' hot spots, lights, trails); threshold high, strength low-moderate. No fat
  searchlight beams or big glowing rings as decoration; if kept, thin and faint.

**Phone performance (iPhone 13 class)**
- Instancing (a few draw calls for hundreds/thousands of buildings), DPR <= 2 (1.5 on low), quality tiers stepped down
  automatically from FPS (olympus/render.js already does this), frustum culling or a cheap bounding sphere, no per-frame
  allocation, no long task over 50 ms after load. Software GL in headless Chromium is slow: prove no long tasks, report fps.
- three.js r160 from the site (../jarvis/three.module.min.js) through olympus/render.js; no CDN unless there is no other way.
