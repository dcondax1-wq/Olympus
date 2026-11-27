# day-sharecard: lead wires (helper did not touch sw.js / build_web_dashboard / apps tables)

1. `tests/run_area.py` nq: add `tests.test_sharecard` (26 checks; `--shots` writes cards to this folder's shots/, gitignored).
2. sw.js precache (optional): `nq/share.html`, `share.js`, `share.css`, `sharecard.js`, `sharebtn.js`.
3. week_review / replay pages: link a day to `share.html?day=YYYY-MM-DD` (past days come from replay/<day>.json and are
   stamped "BACKTEST · not a live result" on the image; only Today is a live result).
4. Button: index.html + accounts.html load `sharebtn.js?v=1`; it shows "📸 Make Insta card · +$N today" only when the PC's
   post is today (ET, < 6 h old) and the real accounts' today $ > 0 (BLITZ excluded). Red day: no button; share.html still works.
Privacy: card text = account display names only (ids / emails / "...1234" / firm-prefixed numbers stripped by cleanName; test-checked).
