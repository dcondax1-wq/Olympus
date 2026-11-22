# Lead wires for day-manual (owner manual), 2026-11-20

Nothing below is needed for the page to work: `hub/manual.html` opens and works offline on its own. These make it findable.
After wiring, run `MANUAL_NO_BROWSER=1 python -X utf8 -m tests.test_owner_manual` (16/16) and the help / doors suites you touch.

1. **help.json** (`tools/web_public/hub/help.json`): add this item right after the `"steps"` item (the Help page lists it, its
   search finds "manual", "emergency", "glossary", "kill"):
```json
  {
   "id": "manual",
   "q": "The owner manual: who is who, money, words, emergencies",
   "words": "manual guide emergency sos kill switch stop everything glossary words room drawdown dll eod pf twin edge accounts bots zlarior atlas k8 blitz day week payout tax",
   "where": "Phone: the Owner manual page (works offline)",
   "steps": [
    "Open the Owner manual. SOS = 10 emergency cards, each 3 steps or less.",
    "Who = every account and bot, with its hours. Day = what the PC does by itself and when the phone pings you.",
    "Money = payouts and the tax pot. Words = every word the pages use."
   ],
   "copy": "",
   "copy_note": "",
   "link": {"href": "manual.html", "label": "Owner manual"},
   "src": "docs/OWNER_MANUAL.md, hub/manual.html"
  },
```
   Then bump `help.js?v=7` only if test_help_page pins an item count (it counted 16+; check `tests/test_help_page.py`).

2. **Help page footer links** (`tools/web_public/hub/help.html`), in `<nav class="hp-links">` first:
   `<a href="manual.html">Owner manual</a>`

3. **ZEUS page nav** (`tools/web_public/hub/zeus.html` line ~139), after the Help link:
   `<a href="manual.html" id="manualBtn">Manual</a>` (if the 390 px nav row gets crowded, skip this one; Help links it).

4. **Doors shortcut** (`tools/web_public/olympus/doors.js` line ~64, next to the Help row):
```js
        { label: 'Owner manual: SOS, who is who, money, words', greek: 'Manual', href: 'hub/manual.html', app: '', words: 'manual sos emergency kill stop everything glossary words room drawdown dll eod pf twin edge who accounts bots hours payout tax' },
```

5. **Launcher / apps.js** (lead only): optional row `manual` -> `hub/manual.html`, title "Owner manual", icon the hub's `icon.svg`.

6. **Offline**: no change to any sw.js. The page registers its own tiny worker `hub/manual-sw.js` with scope `hub/manual`
   (covers manual.html / .css / .js only; the site sw.js skips `hub/`, the Jarvis worker covers `jarvis/` only). Network first,
   saved copy when offline or after 3 s. When you change manual.css / manual.js: bump `?v=m1` in manual.html AND `VER` in
   manual-sw.js together. To drop it: delete manual-sw.js and the `register` try-block in manual.js.

7. **Publish**: `python tools/gh_publish.py` picks the new files up with the next site build (no privacy hit: the test greps
   for ids, emails, tailnet names, IPs, the account name).

8. **Keep it true**: when an account, price, hour or emergency step changes, change docs/OWNER_MANUAL.md and hub/manual.html
   together; `tests.test_owner_manual` fails if a copy line is in one and not the other, or names a module flag / .bat that
   does not exist. The account numbers are a dated snapshot ("Nov 20, 6:00 ET"); live numbers stay on ZEUS.
