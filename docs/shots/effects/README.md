# Effects pass: before / after (2026-11-11)

390 x 844 phone shots (`<scene>-<tier>-before.jpg` = agora-release before the pass, `-after.jpg` = with olympus/fx-cine.js hooked in).
Numbers are WHOLE-FRAME WebGL draw calls and triangles on the page (every canvas, post passes included), median of the frames
seen in 5 s, SwiftShader at 390 x 844. LITE in Symposium, Ergasterion and Colosseum is their flat 2D page (no WebGL at all).

| Scene | Tier | Draws before -> after | Triangles before -> after | What the hook adds |
|---|---|---|---|---|
| Symposium hall | high | 39 -> 44 (46 on a shadow-map frame) | 38.8k -> 102k (People v2 figures merged in between, not the effects) | clock light, sky, shafts, dust, brazier embers + smoke + fire light, 1024 shadow map (columns, couches), crowd contact blobs, speaker focus, calmer skin tones |
| Ergasterion | high | 64 -> 72 | 188k -> 188k | clock light, shafts, dust, camp embers + fire light, sand, sparks off working smiths |
| Colosseum | high | 36 -> 38 | 107.6k -> 107.6k | golden grade, dust, birds; sparks on a clash, laurel + confetti on a verdict |
| Athens | high / low | 32 -> 33 / 27 -> 28 | 115.8k -> 115.8k / 61.3k -> 61.3k | gulls over the harbour |
| Hellas | high / low | 12 -> 14 / 10 -> 12 | 107.8k -> 107.8k / 58.4k -> 58.4k | gulls over the Aegean, sand off the desert |
| Jarvis home | high / low | 37 -> 37 / 24 -> 24 | 6.1k -> 6.1k | the time-of-day colour grade (birds / fireflies only on a real GPU, not on software GL) |
| fx-lab, whole stack | high / low | 31 / 16 | 37k / 13k | everything at once |

Ergasterion was already above 45 whole-page draws before the pass (its own test counts the floor's render core only); the hook adds 4 draws there.
