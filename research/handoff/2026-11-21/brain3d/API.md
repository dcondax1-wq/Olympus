# Brain 3D: the renderer API (DESIGN, day-arenas 2026-11-21)

The 3D bot brain as a kit module, for `nq/brain.html` (the NQ team wires the data). Demo with fake data for both bots:
`/olympus/brain3d-lab.html`. Tests: `python -X utf8 -m tests.test_brain3d` (static + Chromium at 390 x 844). Shots: `shots/`.

| File | What | Size |
|---|---|---|
| `olympus/brain3d.css` | the box, the 2D first paint, the steps list, the ring chips | 4 KB |
| `olympus/brain3d.js` | classic script, `window.Brain3D`; draws the 2D at once, imports the 3D later | 13 KB |
| `olympus/brain3d-scene.js` | ES module, the three.js scene (local `jarvis/three.module.min.js` r160 + `olympus/three-addons/`) | 19 KB + three.js |

three.js is never in the page's first load: `brain3d.js` imports the scene only after `load`, once the box is on screen (50% margin) and the
page is idle. The NQ page's perf budget does not change as long as `brain3d.js` is loaded only by `nq/brain.html`.

## 1. Load

```html
<link rel="stylesheet" href="../olympus/brain3d.css?v=b1">
<script src="../olympus/brain3d.js?v=b1"></script>   <!-- in <head>, NOT defer: mount in the body before the first paint = no layout shift -->
```

If you must `defer` it, give the host a fixed height first (the box is square by default, plus the list), or the page will shift (CLS ~0.3
in the lab).

## 2. Mount

```js
const zl = Brain3D.mount(document.getElementById('zlBrain'), {
  stages: [{ id: 'data', name: 'Market data in' }, /* ... 10 in order ... */ { id: 'done', name: 'Done / journal' }],
  ring:   [{ id: 'dd', name: 'Drawdown left' }, { id: 'daily', name: 'Daily loss' }, /* ... */],
  layout: 'path',          // 'path' = steps along one curve through the brain (Zlarior); 'lobes' = 2-5 regions meeting at the stem (ATLAS)
  title:  'Zlarior',       // the caption when nothing is current, and the aria label
  list:   true,            // the steps-in-order list under the brain (default true; also the screen reader / no-WebGL view)
  ratio:  '1 / 1',         // the box's aspect ratio (default square)
  palette: {},             // optional overrides, keys below, '#rrggbb' only
  currentId: 'sweep',      // optional; default = the first stage is current
  lazy: true,              // false = start the 3D at once (tests); default waits for load + on screen + idle
});
```

Returns the api right away with `mode === '2d'`. `mode` turns `'loading'` and then `'3d'` (the canvas fades in over the schematic). It stays
`'2d'` with no WebGL, with Save-Data, on a 2G/3G line, or after a lost GPU context.

## 3. Update (merge, call as often as the data changes)

```js
zl.update({
  stageStates: { data: 'passed', window: 'passed', map: 'passed', sweep: 'current' },  // passed | current | waiting | blocked
  currentId: 'sweep',                       // pulses violet / gold, big gold name label in 3D, "Now:" caption
  reasons: { sweep: 'Waiting for price to take a level by 0.5 ATR (11 pts).' },        // the grey line under each step
  now: 'Waiting for a 0.5 ATR sweep of 26,547 (38 pts, $760 on 1 NQ).',                // the caption under the brain
  ringStates: { daily: 'warn' },            // ok (mint) | warn (gold) | bad (red)
  ringValues: { dd: '$1,025', daily: '$620 of $1,000' },  // shown on the ring chips
  pulse: 0.6,                               // 0..1, synapse speed (e.g. how close price is to the next step)
});
```

Only the keys you pass change. Passing `currentId` without `stageStates` marks that step current (a blocked step stays blocked).
Mapping from `pc.glance` bots: `stage (n/10)` -> `currentId = STAGES[n-1]`, the steps before it `passed`; `why` -> `now`; `wait` -> `reasons[current]`;
a `blocked`/news flag -> `stageStates[current] = 'blocked'` and `now = the reason`; `room` / `mf` -> `ringValues` + `ringStates`.

## 4. Events and helpers

```js
zl.on('tap', (id, kind) => openCard(id, kind));   // kind 'stage' | 'ring'; a tapped region in 3D OR a tapped / Enter-ed row in the list
zl.where('sweep')            // { x, y, front } CSS px on the canvas (3D only, else null): to pin your own glass card next to a region
zl.where('dd', 'ring')       // a ring node
zl.stats()                   // { regions, ring, synapses, bloom, reduce, dpr, running, frames } or null in 2D
zl.state                     // a copy of the merged state
zl.dispose()                 // removes the canvas, GPU objects, listeners and the 2D nodes (call when leaving the tab)
```

Ids can repeat between stages and ring (`limit` is both in Zlarior): `kind` tells them apart. The "what I'm doing now / why / what would
change my mind" card is the page's job: `on('tap')` gives the id, `where()` gives the spot.

## 5. Ids from the SPEC

Zlarior stages (`layout: 'path'`): `data, window, map, sweep, induce, cisd, limit, confirm, trade, done`.
ATLAS lobes (`layout: 'lobes'`): `ema, macd, sr` (passed = done for today, current = armed, waiting = outside its hours, blocked = rule).
Risk ring (both, ATLAS may take the first 6): `dd` drawdown left, `daily` daily loss, `best` best-day consistency, `idle` 7-day clock,
`news` news ban, `limit` 2% price limit, `hedge` hand-trade hedge guard, `cross` cross-account hedge.

## 6. Palette keys (OLYMPUS NIGHT defaults)

`bg #000000, glow #9d59ee, hi #dacbf0 (waiting), gold #f1c14b (current), ok #77db89 (passed / ring ok), bad #ef4444 (blocked), text #ebe9f1,
muted #898497, line #3e255e, dim #483081`. `Brain3D.palette()` returns a copy.

## 7. Phone budget

- 30 fps cap, pixel ratio <= 2 (1.5 and no bloom on a small-memory or Data-Saver phone; an iPhone gets full quality with bloom).
- Paused off screen (IntersectionObserver) and in a hidden tab. Auto-orbit starts 2.5 s after the last touch.
- Reduced motion: no synapses, no orbit, no pulse; a still frame redrawn on each `update()` (same information).
- Drag = turn, pinch / wheel = zoom (3 to 8.5), a short tap (< 8 px, < 450 ms) = the region under the finger.
- Lab numbers (Chromium, SwiftShader): Zlarior 10 regions, 8 ring nodes, 220 synapses, bloom on, CLS 0.
