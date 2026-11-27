# night-nq-chart: what the lead wires (2026-11-27)

Owned + changed: tools/web_public/nq/nqchart.js, nqchart3d.js, nqbars.js, NEW nq/chart.css (nqchart.js adds its own <link>: no page edit
needed). New test: tests/test_nq_chart_pro.py (28 checks). tests/test_nq_chart.py: 2 colour expectations aegean -> lav (the night palette).

1. tests/run_area.py: `AREAS["trading"].append("nq_chart_pro")` (next to nq_chart) - and/or the nq area if the lead prefers.
2. index.html: bump `nqchart.js?v=c9` -> `?v=d1` (cache), and if sw.js precaches nq files, add `nq/chart.css` (I never edit sw.js).
3. PC levels (optional, makes the chart show prior-day + Globex levels): tools/pc_report.pack_bars can add `"lv": {"pdh", "pdl", "onh", "onl"}`
   (prices) from the bot's own bars; nqbars.js shows them gold ("PD high", "Globex low"...) only when sent and sane. Until then the chart
   shows only what the 180 bars hold: the finished sessions' highs / lows ("(part)" when the feed starts mid-session) and their sweeps.
4. PRE-EXISTING (not this branch; same on origin/pc): tests.test_nq_chart "c. big on the phone ... wholly on the first 390 x 844 screen"
   fails: the chart card's top is at ~1,058 px because the goals card sits above it in index.html. Either move #chartCard up or relax the check.
5. Playwright for Python was not installed in this container: `pip install playwright==1.63.0` (matches the preinstalled node 1.63 /
   chromium-1243; no `playwright install`) made the browser suites run.
6. QA 2026-11-27 #2 (two prices 496 pts apart) FIXED here: the chart also reads the PC's status post (pc_feed.js fetchLatest, shared with
   the page) and, when its price is newer than the last bar, says "Chart stopped HH:MM ET · NQ now <price> (+diff), PC <age>" in gold, draws
   a dashed gold "NQ now (PC)" line, names the old close's tag "last bar HH:MM" and stops the pulsing "live" dot. Shot: shots/stopped-390.png.
   QA #15 "06:00 axis label clipped": not reproduced on the fixture at 390 / 1440 (labels read whole); readout / badge text raised to
   >= 11.5 px. If it shows again on the owner's phone, a QA shot of it would let me pin it.
7. Not mine (QA "also seen"): "Today's market in 3D" caption says "cyan" (nqscene.js / index.html: main).
