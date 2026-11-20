# NQ live chart glow-up + 3D + Olympus Night (day-nqdash3, 2026-11-20)

Owner 15:50 ET: "The chart looks terrible. It needs some 3D, it needs some effects."
Owner 16:00 ET: the Olympus Night palette from the Jarvis switcher (black, violet, gold accents).

| What | Result |
|---|---|
| Palette | `nq/nqtheme.css` re-pointed to OLYMPUS NIGHT. Base pure black. Cards #16131e -> #020204 with #3e255e outlines. Violet #9d59ee glows with lavender #dacbf0 highlights. Bright gold #f1c14b only as small accents: the last-price tag, the 3D toggle, CTA text. Mint #77db89 / red #ef4444 for $ and R. The 3D landscape, the columns, bursts and the 2D picture follow. |
| 2D chart | A violet line + soft violet fill under the day's closes. Mint / red candles with a soft violet glow. A faint violet grid that fades to black at the edges. A lavender crosshair. The last price is a GOLD axis tag with a dotted gold line and a pulsing gold dot (DOM + CSS: nothing repaints the chart). The light trail is lavender. The chart sweeps in on first load. Reduced motion: no sweep, no pulse. |
| 3D toggle | A `3D` button on the chart card loads `nq/nqchart3d.js` (three.js) only when tapped. It shows glowing mint / red 3D candles, a lavender close ribbon, trade beacons and a gold last-price marker. The camera orbits slowly; swipe to turn it. Tapping `2D` frees it. The choice is kept on the phone (`nq.chart.view`). Default 2D. |
| Speed | perf_sweep nq at 4x CPU: FCP 428 ms, LCP 1.4 s, CLS 0.025, TBT 671 ms, three.js NOT loaded at start. DESIGN's payout vault 3D now waits until its card is on screen; it was a 1.7 s long task on load. Static budgets: block CSS 292 KB (nqdeep.css no longer render-blocking), eager JS ~501 KB. |
| Tests | nq_chart 48 (new: the glow-up, 3D toggle load / free / remembered, the one storage key), nq_goals 34, nq_page 70 (black body), nq_desk 33, trading_page 71, smoke 10/10. |

Shots:
- `night-phone-screen1/2/3.png`: the new page.
- `night-phone-chart2d.png` / `night-phone-chart3d.png`: the chart card in 2D and 3D.
- `chart3d-box-390x300.png`: the 3D box alone.
- `before-gold-phone-screen1.png` / `before-after-phone-screen1.png`: the gold v4 and the cyan look before.
