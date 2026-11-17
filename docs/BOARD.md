# The Board (2026-11-17)

Owner: "make a communication board so you and the bot know what's happening ... I don't want to keep being a middleman between you
and the bot. Like the eval pass, I should have known that."

One event log that the bot, the owner and Claude all write and all read.

| Who | Writes | Reads |
|---|---|---|
| Bot (PC) | `engine/board_events.emit(kind, account_key, text, data=None)` -> `data/board/events.jsonl` (gitignored); `order_rejected()` also logs `account_locked` on "Limit 0" | the shared notes it pulls with the repo |
| Owner | Board page note box, or an iPhone Shortcut: `POST /inbox/board` (header `X-Olympus-Inbox: 1`, `{"text": "ATLAS passed"}`) -> `data/inbox/board.jsonl`. A typed balance updates that account's row ("owner, typed, date") | the Board page |
| Claude | `python tools/board.py note "..."` / `owner "..."` -> `data/board/shared.jsonl` (TRACKED: ships to the PC with the next update) | `python tools/board.py read` (under 40 lines) |

Kinds: eval_passed, eval_failed, account_locked, order_rejected, payout_ready, payout_requested, balance, bot_started, bot_stopped,
pc_silent, owner_note, claude_note, plan_changed.

How it travels (all privacy-passed: broker ids to the last 4 digits, no PC name, no folder, no email; BLITZ hidden):
- heartbeat.json `"board"` (every beat, <= 6 KB; `bot_started` / `bot_stopped` noted there)
- ntfy status `"brd"` (tools/pc_report.py, ~700 bytes: account rows + newest events)
- `/site/board/board.json` on the PC (built live), `/site/board/` = the page over Tailscale
- `tools/web_public/board/board.json`, the published copy (`python tools/board.py publish`)

Account rows start from the plan (`tools/web_public/business/accounts.json`, labelled PLAN), then events, then the PC's live numbers
(newest wins). A balance over the target shows PASSED even before MFFU says so. The page takes the PC feed when fresh (30 min),
else the published copy, else the plan; `?demo=1` shows `fixture.json`. PC silent over 30 min = big red banner.

Tests: `python -X utf8 -m tests.test_board` (BOARD_NO_BROWSER=1 skips the 390 px browser check). Area: `python tests/run_area.py board`.
