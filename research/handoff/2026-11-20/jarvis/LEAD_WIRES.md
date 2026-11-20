# day-jarvis: lines for the lead (files I may not edit)

Only `tools/web_public/jarvis/sw.js` needs a change. Nothing in apps.js, olympus.js, build_web_dashboard.py or root sw.js.

## tools/web_public/jarvis/sw.js

1. Cache name (new parts + changed parts must reach phones that already have Jarvis):

```
const CACHE = 'jarvis-v77';
```
and put `'jarvis-v76'` first in the `OLD` list.

2. In the `SHELL` list, add the new module (so the business answers work offline on a cold start):

```
'./biz.js?v=b1',
```

3. In the `SHELL` list, `./backdrop.js?v=b5` becomes `./backdrop.js?v=b6` (index.html now asks for `?v=b6`: the 3D sky waits for
   a quiet moment on a phone and is never built with effects off).

That is all. Everything else is inside `tools/web_public/jarvis/` (index.html, biz.js, backdrop.js, data.js) and `tests/test_jarvis_biz.mjs`.

## Optional (not required)

- `tests/run_area.py`: add `node tests/test_jarvis_biz.mjs` to the jarvis area (node only, 1 s).
