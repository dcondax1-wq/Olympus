# Kalshi City: a richer skyline and a usable GPU-free city

| What | Result |
|---|---|
| 3D skyline | Six concentrated supertall clusters replace the random wall. Stepped metallic crowns and a lit orbital promenade give the city a stronger silhouette. All are explicitly scenery. |
| No graphics support | A dense isometric city atlas shows the actual edge districts, Lab pads, roads and edge towers, surrounded by 650 decorative towers. District buttons and tower picking open the existing research cards. |
| Readability | Responsive desktop split layout; mobile canvas labels find free positions with leader lines. Long 3D names shrink to their canvas; district labels remain visible on the Off tier. |
| Risk wording | The same existing number now says “Lose-half bound” with a visible explanation that it is a lifetime upper bound. Risk still shows the original assumptions and figures. |

Changed files: `tools/web_public/kalshicity/{cityatlas.js,skylineports.js,citylayout.js,cityscene.js,kalshicity.js,kalshicity.css,index.html}`, `tests/test_kalshicity_skyline.py`, this report. No trading, raw data, financial calculations, shared kit, registry, or worker edits.

Validation: five JavaScript syntax checks pass. Existing `KC_NO_BROWSER=1 python tests/test_kalshicity_page.py` passes 37/37 static and pure-model checks. `python tests/test_kalshicity_skyline.py` passes 2/2, including actual three.js instanced geometry, finite transforms, identical tier prefixes, promenade clearance, source preservation, and two-batch crown/rail construction.

CUA preview verifies the automatic no-GPU fallback on the normal page, explicit `?view=atlas`, actual Bitcoin detail, Risk assumptions, and the Board. Desktop screenshot checked at 1363x936. Phone-CSS harness checked 390px and 360px; fixed label collisions found during QA. At 360px body clientWidth and scrollWidth are both 360px. Board and Risk remain readable and scrollable.

Limits: cloud browser WebGL is disabled, so actual GPU rendering, device performance, GPU tier screenshots/counts and real iPhone behavior remain unverified. Existing 3D effects/motion code is unchanged. The atlas has no animation loop; it redraws only on resize. Added 3D scenery is two batched calls; crown instance counts follow the existing scenery caps, and the promenade hides on Off. No new external assets or network sources.

Wiring needed: none. Page CSS/script tags bump k2 to k3; dynamic scene and atlas imports use `?v=skyline1`. Lead owns worker cache release; new nested scene dependency has no preexisting version tag. Publish this app separately from Data City.

## Recovered continuation: usable city scale and district exploration

On phone widths the GPU-free atlas now occupies at least 340px in a naturally scrolling page, rather than being compressed between a fixed statistics panel and dock. Existing Board, Risk and detail sheets stay fixed above the dock. Desktop split layout is retained.

District chips now open a native modal listing every edge in that district, with name/status search and an explicit empty state. Selecting any row opens the existing evidence card; the list reports raw published sample counts and warns that overlapping slices are not added together. Escape/Close returns to the atlas. No feed, calculation, order action or 3D geometry changes.

`python tests/test_kalshicity_skyline.py`: 3/3 PASS, including actual tier geometry plus minimal-DOM interaction across 72 edges, last-edge selection, search, empty state, modal closure and input-data preservation. The existing `KC_NO_BROWSER=1 python tests/test_kalshicity_page.py` remains 37/37 PASS. Page style/script tags are k4 and atlas dependency skyline2. New mobile CSS/modal layout requires the coordinator's current browser QA; these Node DOM checks do not establish real-device layout or GPU performance.


## Nov 5 390px release review

Final branch tip (before this note) `fd5ff2cf248835ca948aa4cf8366b82a1097843f` has exact staged Git blob parity. Chromium at 390×844 rendered software HIGH with `?gpu=1` (three passes, 2,600 scenery instances), plus LITE, OFF and no-WebGL fallback. The Risk sheet and fallback Help opened; no runtime errors or sideways scroll occurred. Darker colors, amber/green low-rise blocks and quieter analysis arcs improved the screenshot, but this remains a distinct Kalshi City scene and physical Safari has not been checked. The published Kalshi feed is stale, so the UI says Status unverified; it does not claim an active bot. Focused checks 6/6, static page checks 37/37 and changed JS syntax pass. The branch must not be described as live before merge, dashboard publication, and a live-site check.
