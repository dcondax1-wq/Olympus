# NAV asks for other slices (2026-11-20)

1. **DESIGN (olympus/zeus_core.js, acctRow)**: add the account's room to the row, so ZEUS shows "$1,025 room before the floor" (zeus.js v=7
   already draws it; nothing shows until this lands). In `acctRow`, the return object, after `planOnly: !!c.planOnly`:
   `, room: c.room && okN(c.room.v) ? c.room.v : null`
   (c.room = {v, src, t} from business/mffumodel.js line 164). The Jarvis / Zenith ZEUS cards can use r.room the same way.
2. **HOME (gate/gate.js)**: a deep link that opens Home with the search filled: `gate/index.html?find=<words>` -> put the words in #q and
   call drawResults(). Then Help, the manual and Jarvis can send "search for X" links. (Q already parses the query string, line 25.)
3. **HOME (gate/)**: the ZEUS door tile opens `hub/zeus.html` directly (today `hub/doors.html#zeus`, then "Open ZEUS"): -1 tap for room,
   today's $, open trade, Decide, PC status. tests/test_gate_page.py line 88 pins `data-to="hub/doors.html#zeus"`: change it with the tile.
