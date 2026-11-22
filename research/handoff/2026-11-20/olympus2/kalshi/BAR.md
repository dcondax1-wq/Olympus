# Dionysus, Sibyl, Kalshi City against the Olympus bar (day-kalshi helper, 2026-11-20)

How measured: `bar_measure.js` (node Playwright, Chromium swiftshader, 390 x 844, external hosts blocked, tools/web_public served locally),
4 runs per page: normal (dark, dpr 2), light colour scheme, every data file 404 ("no data"), every data file junk JSON.
"404s" = optional data files not in the repo locally (kalshi.json, money/sibyl*.json are published by the PC, gitignored here): the page handles them.
Long tasks are swiftshader (software GL) numbers: a phone GPU is much faster, but the ranking holds.

| Page | Bar item | Before | After |
|---|---|---|---|
| Dionysus | 5 s use: first card | old bot's $55.81 balance, pill "Paused" | **K8 today** card first, status line "K8 today: Healthy (won 67% of the last 30). Old crypto bot: retired 2026-11-19, last balance $55.81, history only." |
| Dionysus | true (old bot) | pill "Paused"/"Running", source "Live feed", headings "Bets" / "Open now" / "Where the money is" | pill "Retired", "The old bot's last feed" / "site's copy of the old bot's numbers", "The old bot's guard", "The old bot's bets (history)", "Open when it stopped", "Where the old bot's money was" |
| Dionysus | robust: no data / junk | "Something went wrong: no numbers" + fail veil | plain sentence, old-bot cards hide, K8 + study cards still show when they can; offline says "You are offline." |
| Dionysus | JS errors / long tasks / sideways / unnamed / taps < 44 / blur | 0 / 0 / no / 0 / 0 / 1 (kit nav) | 0 / 0 / no / 0 / 0 / 1 (kit nav) |
| Sibyl | archive banner | none ("Kalshi is paused: look only") | ag-banner "Archive: this page is history (the old crypto bot, retired 2026-11-19). Today's Kalshi bot is K8 ->" + 44 px links K8 -> Kalshi, Kalshi desk (Dionysus) |
| Sibyl | true | hero "Today", "What your Kalshi bot should stop doing", "the bot is untouched" | "The old bot's last study", "What the old bot should have stopped", "History of the old crypto bot (retired 2026-11-19)" |
| Sibyl | robust: no data / junk | "Something went wrong: no numbers" + fail veil | plain sentence, data cards hide, banner + links stay |
| Sibyl | JS errors / sideways / unnamed / taps < 44 | 0 / no / 0 / 0 | 0 / no / 0 / 0 |
| Sibyl | long tasks (3D ball) | 5 tasks, max 1493 ms | 3-11 tasks, max ~1.5 s (unchanged: the ball starts after the cards are drawn; ?q=off = flat twin) |
| Kalshi City | backdrop blurs | 10 visible (12 in css) | **0** (one rule in agora-kalshicity.css; panels were already opaque) |
| Kalshi City | archive banner | none ("Kalshi is paused ...") | header line "Archive: this page is history (the old crypto bot, retired 2026-11-19)." + one-row banner "Today's Kalshi bot is K8 ->" [Kalshi page] [Kalshi desk], 44 px |
| Kalshi City | true | bot line "Kalshi Edge v2: Status unverified ..." | "Old bot (retired 2026-11-19) · Kalshi Edge v2: last said ..." |
| Kalshi City | robust: no data / junk | stuck on "Reading the city..." forever (fail veil only) | plain sentence in the verdict card + "No data" in every slot; main() errors caught |
| Kalshi City | long tasks (3D) | 4 tasks, max 3482 ms, sum 5155 | 6 tasks, max ~2.5 s, sum ~5.0 s; load 12.8 s -> 11.1 s |
| Kalshi City | JS errors / sideways / unnamed / taps < 44 | 0 / no / 0 / 0 | 0 / no / 0 / 0 |
| all 3 | light mode | dark-only by design (color-scheme dark, agora tokens) | same; new banners use agora tokens / the page's own warm palette |

Not done (kept honest): Kalshi City's 3D still starts on load (lazy start behind a tap would break ~40 of its 94 browser checks; see ASKS.md).
Sibyl's 3D ball unchanged. Screenshots: <page>-before.png, <page>-after.png, <page>-after-light.png (390 x 844, dpr 2).
