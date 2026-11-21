# Dashboard FX: one tag, every dashboard gets 3D + glow (DESIGN kit, day-arenas 2026-11-20)

For the 6 app teams. Files are kit-side (`tools/web_public/olympus/dashfx.js` + `dashfx.css`); you add two tags and data attributes.
Live demo of every effect: **`/olympus/dashfx-lab.html`**. Tests: `python -X utf8 -m tests.test_dashfx`.

## Switch it on (two tags)

```html
<link rel="stylesheet" href="../olympus/dashfx.css?v=d1">   <!-- in <head>: reserved sizes from the first frame (no layout jump) -->
<script src="../olympus/dashfx.js?v=d1" defer></script>      <!-- wires every [data-dfx], now and when added later -->
```

## The effects (data attributes; several at once: `data-dfx="glass tilt reveal"`)

| Attribute | What it does | Notes |
|---|---|---|
| `data-dfx="glass"` | glass card: near-black violet gradient (`#16131e` -> `#020204`), deep violet outline, a slow travelling violet / gold edge light, a soft violet glow under it | CSS only; paused when off screen; uses the card's `::before` (leave `::before` free on that element) |
| `data-dfx="tilt"` | a gentle 3D lean (max ~6 deg): the mouse / pen on a computer; on a phone only if motion access was already given | never asks for permission; transform only (never layout); back to flat on leave |
| `data-dfx="reveal"` | a section below the fold rises in (translate + fade) when scrolled to | sections on screen at load are never hidden; no size change |
| `data-dfx="roll"` | the number counts up when it comes into view, keeping `$ , . % -`; the final text is put back exactly | only on a plain number box (no child elements); the box keeps its final width while counting |
| `data-dfx="spark"` on an `<svg>` | its first `<path>` / `<polyline>` glows, a violet gradient fills under it | recolours the line only if it has no stroke of its own (keep green / red lines); follows your redraws |
| `data-dfx="bar"` + `data-dfx-value="0.72"` (or `data-value`) | a glowing progress bar: violet, **gold at 100%**, animates in when seen | the CSS gives the track its height (`--dfx-bar-h`, 8 px); `role="progressbar"` + `aria-valuenow` added; update: `OLYMPUS_DASHFX.bar(el, 0.8)` |
| `data-dfx="bg"` on a box, or `<body data-dfx-bg>` | an aurora (3 slow colour blobs) + up to 60 drifting dots on one 2D canvas behind the content | 30 fps, pixel ratio <= 1.5, stops when the tab is hidden or the box is off screen; none under reduced motion / Save-Data. On `<body>` give `<html>` the page background (the canvas sits under the content) |

## The API (`window.OLYMPUS_DASHFX`)

```js
OLYMPUS_DASHFX.wire(scope)                       // wire [data-dfx] under scope (automatic for the page and for added nodes)
OLYMPUS_DASHFX.bar(el, 0.8)                      // set a bar's value
OLYMPUS_DASHFX.theme({ glow: '#9d59ee', gold: '#f1c14b' })   // override palette colours (hex only); returns the palette
OLYMPUS_DASHFX.palette()                         // the current colours
OLYMPUS_DASHFX.chart.svg(pathEl, { color, fill, fillOpacity, blur })   // glow + gradient area under an SVG line; returns { stop(), sync() }
OLYMPUS_DASHFX.chart.canvas(ctx2d, [[x, y], ...], { color, bottom, width, blur })   // draw a glowing line + gradient fill on a 2D canvas
OLYMPUS_DASHFX.chart.lwc(series, { color, width })  // lightweight-charts: applies + returns { lineColor, topColor, bottomColor, lineWidth, ... }
OLYMPUS_DASHFX.stats()                           // { wired, frames, maxFrameMs, bgRunning, rolls, reduced }
OLYMPUS_DASHFX.stop()                            // everything off: listeners, canvases, classes, inline styles, SVG nodes; texts restored
```

## The palette: OLYMPUS NIGHT (CSS variables, override any on your page)

| Variable | Default | Use |
|---|---|---|
| `--dfx-base` | `#000000` | page background |
| `--dfx-card-a` / `--dfx-card-b` | `#16131e` / `#020204` | card gradient (top -> bottom) |
| `--dfx-warm` | `#231d16` | the faint warm glow at a card's top |
| `--dfx-line` / `--dfx-line-2` / `--dfx-line-3` | `#3e255e` / `#462a6a` / `#4d2e76` | outlines |
| `--dfx-glow` | `#9d59ee` | glows, rings, arcs, chart lines |
| `--dfx-hi` | `#dacbf0` | highlights (lavender) |
| `--dfx-dim` | `#483081` | inactive dots, empty tracks |
| `--dfx-gold` | `#f1c14b` | the accent: active chip border, CTA text, selected item, a full bar |
| `--dfx-gold-text` | `#ebbf4f` | gold text |
| `--dfx-gold-muted` | `#ac8a36` | thin decorative rings only |
| `--dfx-good` / `--dfx-good-line` | `#77db89` / `#557b61` | profit / its border |
| `--dfx-bad` | `#ef4444` | loss |
| `--dfx-text` / `--dfx-muted` | `#ebe9f1` / `#898497` | text |

Gold is a **small bright accent on black**: never a card background, never brown / olive / marble surfaces (the old "gold-ish" look the owner disliked).

## Example (a dashboard hero card)

```html
<section class="card" data-dfx="glass tilt">
  <span class="k">Today</span>
  <b class="v good" data-dfx="roll">+$1,284.50</b>
  <svg data-dfx="spark" viewBox="0 0 300 72" preserveAspectRatio="none"><path d="M0 60 L60 52 L120 40 ..." fill="none"/></svg>
  <div data-dfx="bar" data-dfx-value="0.72"></div>
</section>
<section class="card" data-dfx="glass reveal">... below the fold ...</section>
<body data-dfx-bg>  <!-- the aurora behind the page -->
```

## The rules it keeps

- **No layout jump**: transforms and opacity only; bars and every reserved size come from `dashfx.css` (load it in `<head>`); numbers keep their
  final width while counting. Tested: layout shift 0 over load + a full scroll.
- **Reduced motion = nothing moves**: no edge light, tilt, reveal, count or bar animation, no background canvas; every final state shows at once.
- **Fast**: no WebGL; one 2D canvas at 30 fps (< 1 ms a frame in the lab), paused off screen and in a hidden tab; no long task over 50 ms.
- **Taps unaffected**: every layer is `pointer-events: none`.
- **Stoppable**: `stop()` removes everything it made (tested).
