# Lead wires: K8 day dashboard (day-kalshi 2026-11-20)

The helper bumped `tools/web_public/kalshi/index.html` from `?v=k44` to `?v=k47` on BOTH `kalshi.css` and `kalshi.js` (they changed).
`kalshi/sw.js` is lead-only, so it still says k44. Make these three exact edits in `tools/web_public/kalshi/sw.js`:

```
-const CACHE = 'kalshi-k44';                      // = 'kalshi-' + the ?v= of kalshi.css / kalshi.js (index.html, SHELL): a new version, a new cache
+const CACHE = 'kalshi-k47';                      // = 'kalshi-' + the ?v= of kalshi.css / kalshi.js (index.html, SHELL): a new version, a new cache
```
```
-const SHELL = ['./', './index.html', './kalshi.css?v=k44', './kalshi.js?v=k44', './kfx.js?v=k26', './kit.json', '../olympus/warp.css?v=w3', '../olympus/warp.js?v=w3'];
+const SHELL = ['./', './index.html', './kalshi.css?v=k47', './kalshi.js?v=k47', './kfx.js?v=k26', './kit.json', '../olympus/warp.css?v=w3', '../olympus/warp.js?v=w3'];
```
(one-liner: `sed -i "s/kalshi-k44/kalshi-k47/; s/kalshi.css?v=k44/kalshi.css?v=k47/; s/kalshi.js?v=k44/kalshi.js?v=k47/" tools/web_public/kalshi/sw.js`)

`./k8.json` needs NO sw.js change: it has no `?v=`, so the worker already answers it network first (the saved copy only when the
site fails), exactly like kit.json. Do not add it to SHELL (it changes every day).

Tests that see this:
- `tests/test_kalshi_page.py` part a, check "kalshi/sw.js: its own 'kalshi-*' cache ... the page's versions" requires
  `const CACHE = 'kalshi-<v>'` and `'./kalshi.css?v=<v>'` / `'./kalshi.js?v=<v>'` in sw.js with `<v>` read from index.html.
  It FAILS until the sw.js edit above is made (it fails only because sw.js is lead-only). Every other part-a check passes (26/27).
- `tests/test_kalshi_k8_dash.py` (new) pins `k47` in index.html only.

Other version bumps made by the helper (no worker involved): `dionysus/index.html` dionysus.css a1q -> a1r, dionysus.js a2 -> a3;
`observatory/index.html` app.js 7 -> 8.
