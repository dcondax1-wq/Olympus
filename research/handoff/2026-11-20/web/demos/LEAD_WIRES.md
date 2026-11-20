# WEB · demos: what only the lead can wire

1. **Agency hub link** (agency/index.html is the hub team's): add a card / link "3D website demos" -> `demos/` (the gallery). The
   gallery's back link goes to `../` (the Agency app). `agency/demos/summary.json` is there for the HQ tile (n, label, next, t).
2. **Publish**: nothing to add. `tools/build_web_dashboard.py` already copies `agency/` with its sub-folders, so `agency/demos/**` ships.
3. **sw.js**: optional. The demos are meant to work offline in front of a prospect with no signal; if you want that, pre-cache
   `agency/demos/` + the 5 demo folders (html, scene.js, thumb.jpg), `demo.css`, `demo.js`, `stage.js`, `olympus/lazy3d.js`,
   `jarvis/three.module.min.js`, `olympus/three-addons/RoomEnvironment.js`. Otherwise no change.
4. **Prices**: done from offers.json; the 10 `data-price` values in `agency/demos/index.html` are the only place to change them.
5. Branch: everything is on `day-arenas` (this session can only push that branch), based on pc 4f637df3.
