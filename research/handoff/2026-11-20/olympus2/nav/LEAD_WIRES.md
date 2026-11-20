# NAV lead wires (2026-11-20, day-manual)

1. **olympus/doors.js** (lead-only), the More door, right after the Help row (line ~64):
```js
        { label: 'Owner manual: SOS, who is who, money, words', greek: 'Manual', href: 'hub/manual.html', app: '', words: 'manual sos emergency kill stop everything glossary words room drawdown dll eod pf twin edge who accounts bots hours payout tax' },
        { label: 'Your steps: what is left to do', greek: 'Steps', href: 'hub/steps.html', app: '', words: 'steps todo to do waiting list next need' },
```
2. **olympus/doors.js**, the ZEUS door's first shortcuts (so the Doors page and the launcher show the owner's top checks one tap away):
```js
        { label: 'Room left on each account', greek: 'MFFU view', href: 'business/mffu.html', app: '', words: 'room drawdown left lose floor open trade live' },
        { label: 'Decide cards', greek: 'Board · Decide', href: 'board/index.html#decide', app: '', words: 'decide decisions yes no questions' },
```
3. **launcher.js / jarvis/apps.js**: the launcher's search should call `OLYMPUS_GATE.findAll(q)` (as the Gate and Go to do) so "how much can
   I lose" works there too; if it only uses `OLYMPUS_DOORS.find`, plain questions still find nothing there.
4. **help.json** (if not done from the morning list): item `manual` -> manual.html (text in ../manual/LEAD_WIRES.md #1).
5. Publish: the catalog is a shared file; bump its `?v=` (hub/index.html + gate-nav.js are at nv6 already; gate/index.html line 55 + tests/test_gate_page.py line 74: nv5 -> nv6) wherever pages load `olympus/gate-catalog.js` (gate/index.html, gate-nav.js
   loads it by itself) so cached phones get the new search: `grep -rn "gate-catalog.js?v=" tools/web_public`.
