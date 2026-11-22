# RED TESTS SWEEP: lead wires (day-a11y 2026-11-22)

## 1. `tools/web_public/jarvis/sw.js` (the Jarvis worker: lead-only), fixes tests.test_jarvis_shell 2/3 -> 3/3
Root cause: product, not a stale test. The Jarvis page and its scripts load 4 files the worker's offline copy does not hold, so offline Jarvis
loses the answers that need them (biz.js `import('../nq/nqbars.js?v=b1')` = "is ATLAS in a trade?", `import('../agency/expert/expertcore.js?v=1')`
= the web answers) and the OLYMPUS NIGHT glass (index.html line 123, dashfx). All 4 files exist.

In `const SHELL = [ ... ]` append, before `'./three.module.min.js'`:

    '../nq/nqbars.js?v=b1', '../agency/expert/expertcore.js?v=1', '../olympus/dashfx.css?v=d1', '../olympus/dashfx.js?v=d1',

and bump `const CACHE = 'jarvis-v93';` -> `'jarvis-v94'` (+ the pinned CACHE strings your landing usually updates).
(dashfx stays `async` in index.html: being in SHELL only makes it come from the saved copy, it never holds the start.)
Keep the ?v tags in step: when nqbars / expertcore / dashfx get a new tag, the SHELL entry changes with it (the test compares exact URLs).

## 2. cache tags to bump at landing
- `mind/index.html` `mind.css?v=m5g` -> next tag (the #top column fix).
- `gate/index.html` `gate.css` tag (colours moved into tokens; the look is the same).
