# AGORA: the new OLYMPUS look (owner 2026-11-09: "I don't like the cyborg / future-tech theme, it looks like shit, remove it")

Classical Greece, warm and calm: marble, bronze, gold, olive, terracotta. Premium and readable on an iPhone. NOT sci-fi.

## BANNED everywhere (remove it when you see it)
- Neon colours and glow (cyan/mint/violet/magenta neon, text-shadow glow, big bloom), HUD frames, scanlines, grids-as-decoration, "cyber" corner brackets.
- Orbitron / Rajdhani / any techno or monospace-looking display font; wide letter-spaced ALL-CAPS micro labels (letter-spacing > .06em on body UI).
- Words like cyber, neural, quantum, holographic, matrix, terminal, scanner, uplink as decoration.
- Pure black (#000) backgrounds and pure white text.

## The look
- Fonts (no downloads, they are on every iPhone): headings `'Iowan Old Style','Palatino Linotype',Palatino,Georgia,serif`; body `-apple-system,'SF Pro Text',system-ui,sans-serif`; numbers `'SF Pro Rounded',-apple-system,sans-serif` with `font-variant-numeric: tabular-nums`.
- Colours (tokens in `olympus/agora.css`): ivory text `#f3ece0`, soft text `#cfc4b2`, muted `#9a8f7d` (>= 4.5:1 on the panels), night `#14110e`, marble panel `#1d1914`, raised panel `#26211b`, line `#3a3228`,
  gold `#c8a24a` (primary / good highlights), bronze `#9c6b3c`, olive `#7f8a52` (gains), terracotta `#c96a4a` (losses), aegean `#4b7a99` (info), sunrise `#e0b060` (warnings).
- Shapes: 16 px radius cards, 12 px controls, 1 px warm lines, soft shadow `0 6px 18px rgba(0,0,0,.35)`, a thin gold rule under titles. No glow, no gradients except very subtle marble/bronze.
- 3D scenes keep their geometry but change the mood: marble, bronze, warm torch/sun light (colour temperature 2700-3500 K), warm fog, no neon emissive, no cyan/violet bloom, no neon rim lights.
  Bloom strength <= 0.25, only on fire/gold. Skies: dawn/dusk gradients (indigo to amber), not black with neon stars.
- Motion: slow and smooth (200-450 ms ease-out). No flicker, glitch, scan or typing effects.
- Money wording rules still apply: "Drawdown left $X of $max loss", every R next to its $, plain words, never blank, taps >= 44 px, 390x844 first.
- Icons/glyphs: simple Greek-flavoured marks (laurel, column, amphora, owl, wave, lyre, shield); the OLYMPUS logo stays.

## How to apply it
1. Link `../olympus/agora.css` in the app page (after `olympus.css`); the app's own CSS then only sets what is specific to it. Delete the app's neon/HUD/techno-font rules instead of overriding them.
2. Set `data-theme="agora"` on `<html>` (default for every app; `olympus/themes.js` has the `agora` theme and it is the default).
3. In `*.js` scenes replace neon palettes with the AGORA colours above (use `OLYMPUS_AGORA` from `olympus/agora.js` if present).
4. Check: `?demo=1` at 390x844 in `?q=high` and `?q=low`; screenshots before/after; no console errors; the app's own test passes.
5. Commit on YOUR worktree branch (git is local only: GitHub is suspended, never try to push).
