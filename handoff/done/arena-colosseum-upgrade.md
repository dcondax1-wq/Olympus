# ARENA: the Olympian colosseum

| What | Result |
| --- | --- |
| 3D architecture | Upper colonnade, four victory gates, distant city skyline and gilded radial floor inlays |
| GPU-free arena | Complete self-contained illustrated stadium: three vaulted galleries, imperial banners, moonlit city, stepped altar, crown and torch pools |
| Campaign scoreboard | Quest completion, labours and trophies read from the existing score and verification results |
| Controls | Warmer readable rank panel and quest sheets; phone tabs remain at least 44px tall |
| Effects off | Uses the illustrated arena immediately, without importing or creating the 3D scene |

Changed files: `tools/web_public/arena/index.html`, `arena.css`, `main.js`, `scene.js`, new `colosseum.js`, new `illustration.js`; new `tests/test_arena_colosseum_upgrade.mjs`; this handoff. Existing rules, XP calculation, local ledger, quest verification and account/bot files are untouched.

Validation:
- Four JavaScript syntax checks passed (`main.js`, `scene.js`, `colosseum.js`, `illustration.js`).
- `node tests/test_arena_colosseum_upgrade.mjs` passes. Actual CPU geometry: 232 architecture instances, six draw batches / 4,608 triangles high; five / 3,216 LITE. Quality restores without rebuilding and every geometry disposes. These are additions to the existing scene; the shared 150 calls / 75k phone budget is unchanged.
- Generated 12,595-byte SVG parses as valid XML; inert local artwork, no runtime image fetch or animation loop.
- CUA desktop screenshot reviewed. Actual 390px and 360px CSS viewport checked through `qa-phone-preview.html`: illustrated arena, real demo progress and controls visible. At 360px, all five tabs are 44px high, widths 46.39–46.41px, no clipped tab labels and no page horizontal overflow. Quest sheet opens and readable quest content remains available above the campaign/footer.

GPU scene appearance and total renderer draw budget cannot be confirmed in the provided browser because WebGL is Disabled. CPU geometry limits and unchanged renderer/pass/light counts were checked; real-device GPU QA remains necessary. This agent did not modify shared-kit files during this task. Local resource version tags were bumped. Lead handles worker cache invalidation and publication.
