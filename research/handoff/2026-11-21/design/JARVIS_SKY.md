# Jarvis sky: poster first, 3D after idle (DESIGN, day-arenas 2026-11-21)

QA: Jarvis's phone TBT (time the page is frozen) was 5.1 s. The 3D sky built inside the first seconds after load: one 1.5-2.2 s freeze on a
phone-speed CPU with software GL.

## What changed (jarvis/index.html, jarvis/backdrop.js, new jarvis/sky-poster.webp)

- **Poster:** `sky-poster.webp` (702 bytes, a blurred still of the 3D sky) is the first layer of `.bgfx`, painted by CSS alone from the first
  frame. It fades out (0.9 s) as the 3D sky fades in over it (`html[data-bg3d=on]`). At 35% under an OLYMPUS style, like the canvases.
  It has too little detail to count as the page's "main content" (LCP unchanged).
- **3D only when it is worth it:** never built for effects Off or Low (LITE), reduced motion (Jarvis starts those on Low), Save-Data, a
  2G/3G line, or a phone with <= 2 GB. `__jarvisBackdrop.why` says which. If the owner later raises effects to High, it is built then.
- **Later on a phone:** the 6 s wait now counts from `load`, not from the first byte, so on a slow line the build no longer lands right as
  the page arrives. Still after 2.5 s without a touch, then an idle moment.

## Numbers (perf_sweep jarvis: 390 x 844, 4x CPU, Fast 3G, 2 runs each)

| | Before | After |
|---|---|---|
| TBT (frozen time) | 4.8 / 6.5 s | **3.2 / 3.6 s** |
| Longest task | 1.5 / 2.1 s | **1.1 / 1.1 s** |
| LCP | 1.8 / 1.6 s | 1.7 / 1.7 s |
| CLS | 0.039 / 0.043 | 0.039 / 0.043 |

On the sweep's Fast 3G line the 3D is skipped (a 3G line). On 4G (no line limit, 4x CPU) the page loads at 2.0 s and the 3D builds at
10.6 s, after the quiet wait. The remaining ~3 s TBT is Jarvis's own start-up scripts (a 1.1 s task near load), not the sky.

## LEAD_WIRES (jarvis/sw.js is yours)

In `SHELL`: `'./backdrop.js?v=b6'` -> `'./backdrop.js?v=b7'`, add `'./sky-poster.webp?v=2'`, bump `CACHE` (`jarvis-v86` -> next).

## Tests

`tests/test_jarvis_sky.py` (new; static + Chromium: poster at first paint, 3D on and the poster faded on a computer, none under reduced
motion or on 3G, Low -> High builds it). `test_jarvis_hub` 272/272. Jarvis browser suites: see the commit message.
