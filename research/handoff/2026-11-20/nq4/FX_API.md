# NQ FX: the effects kit for the NQ dashboard (from DESIGN, day-arenas 2026-11-20)

For the nqdash3 team. Files are kit-side (`tools/web_public/olympus/`); you only add one tag and call the verbs from `nq/`.
Live demo of every effect: **`/olympus/nqfx-lab.html`** (`?tier=ultra|high|low|off` to force a tier). Tests: `python -X utf8 -m tests.test_nqfx`.

## Load it

```html
<script src="../olympus/nqfx.js?v=n1" defer></script>   <!-- loads fx-core / fx-text / fx-burst itself if the page has not -->
```
```js
await OLYMPUS_NQFX.ready();          // resolves to OLYMPUS_FX (or null if the kit could not load: every verb is then a harmless no-op)
const NQFX = window.OLYMPUS_NQFX;
```

## The verbs (each returns an FX handle: `h.stop()`, `h.call('set', ...)`, `h.tier`)

| Call | What it does | Notes |
|---|---|---|
| `NQFX.win(el, { usd, bigAt: 500, text: 'Win' })` | sparks fly from `el`, a green toast "Win +$180"; confetti too when `usd >= bigAt` | call it when a trade closes green |
| `NQFX.loss(el, { usd, text: 'Loss' })` | a calm red toast "Loss -$95", no celebration | |
| `NQFX.milestone(el, { text })` | confetti from `el` + a toast | eval passed, payout ready, new equity high |
| `NQFX.ring(host, { value: 0..1, stroke: 8, color })` | the glowing goal ring with a comet tip; `h.call('set', 0.8)` glides on | `host` must have a size; put the % text inside it (z-index above 2) |
| `NQFX.roll(el, { to, from: 0, duration: 1.2 })` | the number rolls up, `$ , . %` kept; `h.call('set', v)` rolls on | write the final text yourself too (screen readers, no-JS) |
| `NQFX.trail(pathEl, { color, seconds: 2.6, rest: 1.2, width, tail: .14 })` | a light runs along an SVG chart line, a soft glow under it | `<path>` or `<polyline>`; it follows your redraws (watches `d` / `points`) |
| `NQFX.vault(host, { value: 0..1, label: '$1,860 of $3,000', aria: 'Payout goal' })` | the payout hero: a drawn vault at once, then (after load + idle) a 3D steel vault door that opens as `value` grows, gold coins stacking up behind it, a coin shower at 100% | `host` needs a fixed size (e.g. `aspect-ratio: 4 / 3`) so nothing moves; `h.call('set', v, label)` |

## The rules it keeps (so you do not have to)

- **Tiers** follow the owner's one quality setting (`OLYMPUS.fx()`): ultra / high / **low = phone tier** (30 fps, pixel ratio 1, fewer coins and
  particles, no reflections) / off. **Reduced motion = off**: nothing moves, and the ring, number and vault show their final state still.
- **No WebGL**, a lost GPU context, Save-Data or a 2G / 3G line: the vault stays its drawn 2D picture (same size, same labels).
- **Fast**: the 3D (three.js, already cached by Jarvis) is imported only after `load` + idle, never on the first paint. The test checks that no long
  task over 200 ms happens before that. One shared frame loop for every effect; it sleeps off screen and in a hidden tab.
- **Clean**: `h.stop()` (or `OLYMPUS_FX.stopAll()`) removes every canvas, node, listener and GPU object it made (tested).
- **Accessible**: the vault host gets `role="img"` and an `aria-label` with the % and your label; toasts are text.
- **Colours**: the ring and the trail take the page's accent (`--oly-accent-rgb`); pass `color` to pick another.

## Example (the NQ hero)

```html
<div id="payout" style="aspect-ratio: 4 / 3; border-radius: 16px"></div>
<div id="goal" style="width: 120px; height: 120px; display: grid; place-items: center"><b id="goalPct">0%</b></div>
<svg viewBox="0 0 320 160"><path id="equity" d="..." stroke="var(--ag-gold)" fill="none"/></svg>
```
```js
await OLYMPUS_NQFX.ready();
const vault = NQFX.vault(payout, { value: room / target, label: `$${room} of $${target}` });
const ring = NQFX.ring(goal, { value: pct }); NQFX.roll(goalPct, { to: Math.round(pct * 100) });
NQFX.trail(equity);
// on a new fill: NQFX.win(card, { usd: +pnl }) or NQFX.loss(card, { usd: pnl }); on pass: NQFX.milestone(card, { text: 'Eval passed' })
// on new numbers: vault.call('set', room / target, label); ring.call('set', pct)
```
