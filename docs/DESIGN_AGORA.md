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

## v2 (2026-11-11): the design system (`olympus/agora.css` + `olympus/agora-ui.js`, lab page `olympus/agora-lab.html`)
Owner: "it's like 5% done ... on every aspect you can do better". v2 turns the AGORA look into a system every app shares, so an app looks like a
premium iPhone app without its own CSS. Open `/olympus/agora-lab.html` at 390 x 844 to see every piece; check a change there before it reaches 60 apps.

**Tokens (`:root` in agora.css).** Everything below is a variable; use the token, never a raw value.
| Group | Tokens | Notes |
|---|---|---|
| Type | `--ag-fs-cap` 12, `-foot` 13, `-sub` 14, `-body` 15, `-lead` 17, `-h3` 18, `-h2` 22, `-h1` 30, `-stat` 28, `-hero` 44 (in rem) | Serif for titles (`--ag-serif`), sans for text (`--ag-sans`), rounded tabular figures for every number (`--ag-num` + `font-variant-numeric: tabular-nums`). rem, so the phone's text size setting scales it. Nothing under 12 px. |
| Space | `--ag-sp-1` 4 ... `--ag-sp-8` 40 (a 4 px grid), `--ag-gutter` 16 | Page side gutter 16 + safe area. |
| Surfaces | `--ag-s0` night ... `--ag-s4`, `--ag-line`, `--ag-line-soft`, `--ag-line-gold` | Warm dark, never #000. |
| Ink | `--ag-text` (16:1), `--ag-soft` (10:1), `--ag-muted` #a89c88 (>= 5.1:1 on every surface, was #9a8f7d), `--ag-olive-text`, `--ag-terra-text`, `--ag-aegean-text`, `--ag-sun` | All AA (4.5:1) on `--ag-s4`, the lightest surface. |
| Elevation | `--ag-e1` (controls), `--ag-e2` (cards), `--ag-e3` (hero, sheets, toasts) | Layered dark shadows with a 1 px warm top light; no glow. |
| Shape | `--ag-radius-xs` 8, `-s` 12, `--ag-radius` 16, `-l` 22 | Cards 20 in the page shell, controls 12-13, chips round. |
| Motion | `--ag-ease` (ease-out), `--ag-d1` 200 / `-d2` 260 / `-d3` 340 ms, `--ag-stagger` 45 ms | Press = `scale: .97` in 200 ms. Reduced motion and `data-fx="off"` turn every animation off. |

**Components (classes in agora.css).** `.ag-card` (+ `.ag-hero` hero stat card, `.ag-listcard`, `.ag-chartcard`, `.flat`, `.tap`), `.ag-cardhead`,
`.ag-hero-label / -num / -sub`, `.ag-stats` + `.ag-stat` (label / value / sub) + `.ag-delta.up|down`, `.ag-list` + `.ag-row` (icon, title + sub, value, chevron),
`.ag-btn` (`.primary`, `.ghost`, `.quiet`, `.danger`, `.block`, `.lg`), `.ag-iconbtn`, `.ag-chip`, `.ag-seg` (segmented control), `.ag-tabs` / `.ag-tab`,
`.ag-field`, `.ag-bar`, `.ag-badge` (`.ok`, `.warn`, `.bad`, `.info`, `.demo`), `.ag-banner`, `.ag-toast`, `.ag-skel` (calm breathing skeleton, no moving sheen),
`.ag-state` (empty / error), `.ag-sheet` (+ `.ag-scrim`, `.ag-grab`), `.ag-appbar`, `.ag-navback`, `.ag-tabbar` (a floating capsule that stays clear of
Jarvis's orb corner), `.ag-ptr` (pull to refresh), `.ag-chart`, `.ag-ic`, `.ag-enter` / `.ag-stagger`.

**Behaviour (`olympus/agora-ui.js`, `window.AGORA`).** `icon(name)` (one original 24 px line set, 1.75 stroke; `AGORA.ICONS` lists the 68 names,
`[data-ag-icon="name"]` elements get theirs on load), `chart(el, {type: 'line' | 'area' | 'bar' | 'spark', values, labels, fmt, tone})` (one mini chart style:
three nice gridlines with labels, a zero line, first / middle / last x labels, the last point marked, bars with their values, an aria label),
`toast(text, {kind})`, `sheet({title, body})` (drag the grabber down, the scrim or Escape closes it; focus returns), `state(el, {kind: 'empty' | 'error' | 'loading', ...})`,
`pull(onRefresh)` (touch screens, top of page), `morph(update)` (a view transition where the browser has one: the list -> detail feel), `shell()`.
Everything is built with createElement / createElementNS + textContent: no markup from data, no network, no storage.

**The page shell (no markup change).** Every app on the AGORA app base (`main#app > header.top > .brand + .tags`, then `p#status.note`, then cards) gets:
a back row (`< Olympus`, only when opened alone, not inside Jarvis) with the Demo / Lite chips on the right; a 52 px icon tile, a 30 px serif title with the gold rule,
a one-line purpose; the live status as a quiet line with a gold dot; cards on the layered surface with 18 px serif titles; the hero card gold-warmed; status pills as
badges; buttons with one shape and a press; a compact blurred bar (back, title, Demo) that fades in once the large title scrolls away; a 30-220 ms page-enter stagger.
The rules use `#app` so they dress the base block each app copied; an app that needs something else overrides with `#app` too. Load `agora-ui.js` deferred after
`a11y.js` (`<script src="../olympus/agora-ui.js?v=1" defer></script>`) for the back row and the compact bar; without it the page still looks right.
Opt out of the shell: `<html data-ag-noshell>`.

**Rules of thumb.** One hero number per screen (the $ that matters, rounded figures, 30-44 px). Labels above values, muted, 13 px. Every number tabular.
Every R next to its $. Status = a badge with a dot, never a coloured stripe across a card. "Demo" is one small chip, not a banner on every card. Text in olive or terracotta uses `--ag-olive-text` / `--ag-terra-text` (the fills `--ag-olive` / `--ag-terra` are 3-4:1 as text: bars only); the shell maps `.pos / .up / .neg / .dn` and the status pills to the text-safe ink.
An `<svg>` has no `.hidden` property: toggle the attribute (`toggleAttribute('hidden', ...)`), or the flat fallback stays invisible.
