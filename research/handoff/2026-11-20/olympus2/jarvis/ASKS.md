# Team JARVIS: asks to other teams (2026-11-20)

## DESIGN (olympus/ kit): the Ask Jarvis button on every app

`tools/web_public/jarvis/ask.js` is ready and self-contained (classic script, ~12 KB, no dependencies, no network until tapped).
One line per page, or one line in the kit loader:

```html
<script src="../jarvis/ask.js" defer data-app="nq"></script>
```

- `data-app` = the page's app id (optional: the folder name is used). It picks the page's questions (NQ: In a trade?, Room left,
  Today...; Money: First payout, Payout now?, Taxes...; Kalshi: Kalshi, News...; Hub: To-do, Decide, PC OK?).
- The kit can mount it itself: `<script ... data-auto="off">` then `OLY_ASK.mount({ app: 'nq', host: someElement })`.
- Restyle with `.oly-ask-btn` / `.oly-ask-sheet` and `--oly-ask-accent`, `--oly-ask-bg`, `--oly-ask-text`. Default place: bottom left,
  84 px above the bottom (clear of the dock / tab bars); move it with CSS if a page has something there.
- It never mounts on Jarvis itself. Tested: `python -X utf8 -m tests.test_jarvis_ask` (15 checks: 44 px target, dialog + focus trap,
  Escape, offline, ?ask= into Jarvis).

## PERF / lead
- `jarvis/apps.js` remember(): calls listApps() for every status card (O(n^2), ~0.5 s at 4x CPU on Jarvis's start). A memo there is
  the biggest start-up win left in Jarvis; it is lead-only.
