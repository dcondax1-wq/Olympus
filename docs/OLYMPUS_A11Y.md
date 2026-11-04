# OLYMPUS accessibility + readability layer (2026-11-04)

One shared layer in the kit, so no app has to carry its own: `tools/web_public/olympus/a11y.js` (+ `a11y.css`, loaded by the script itself).
Add ONE tag to a page (path from an app folder; use `olympus/a11y.js` from the site root, e.g. Zenith's `index.html`):

    <script src="../olympus/a11y.js" defer></script>

Optional second tag (no flash of unstyled rules; the script adds it anyway): `<link rel="stylesheet" href="../olympus/a11y.css">`.
Demo / test page: `olympus/a11y-demo.html`; test `python -X utf8 -m tests.test_olympus_a11y` (`--static` = no browser).

| Feature | How |
|---|---|
| Text size | Dynamic Type read from `font: -apple-system-body`; `--oly-text-scale`; ONE mechanism: iOS `text-size-adjust` on a touch phone (scales px and rem text), the root font size elsewhere. Never both (they would multiply). |
| Big text toggle | `OLYMPUS_A11Y.toggleBig()` or any element with `data-oly-a11y="big-text"` (kept `aria-pressed`); x1.25, saved in `localStorage['olympus.a11y']`, every tab follows. Same for `more-contrast` and `reduce-motion`. |
| Ink | `--oly-dim` is lifted to 4.5:1 on the page background when a theme or token makes it weaker (inline on `<html>`, ours only); `prefers-contrast: more` or the choice: full-strength ink, stronger lines, no glass blur. |
| Focus | a 3 px accent ring with a dark halo for keyboard / VoiceOver focus (`!important`, beats `outline: none`); never on a tap. |
| Names | icon-only buttons, links, `role=button` and fields get an `aria-label` (title, glyph, class / id / data-* words, `data-oly-label`), watched by a MutationObserver; `data-oly-skip` opts out; what cannot be named is listed in `OLYMPUS_A11Y.unlabeled`, never invented. |
| Live regions | `.toast`, `#toast`, `[class*=toast]`, `.oly-toast`: `role=status` + `aria-live=polite`; error ones and `.oly-err`: `role=alert`. |
| Motion | `prefers-reduced-motion` or the choice: `html[data-oly-motion=reduce]`, loops stop, moves become cuts (`data-oly-skip` keeps one running). |

## Contrast audit (tests/test_olympus_a11y.py, 122 theme pairs + every app stylesheet's muted ink token)

Worst offenders found and fixed: `tree/tree.css` `--faint` 2.09 (now 4.9) and `--dim` 4.19 (now 6.2); Zenith `index.html` `--muted` 4.19 on
`--surface` (now 5.3); Athena theme `accent2` 4.19 on marble (now 4.78). Not ink (dark fills, left as they are): Jarvis `--dim`, Kalshi `--dim`.
Decorative edges (the 1px glass rim, `--oly-edge`) are below 3:1 by design and not text.
