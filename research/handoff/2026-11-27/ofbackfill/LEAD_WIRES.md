# night-of-backfill: lead wires (2026-11-27)

Branch `night-of-backfill` off origin/pc. Plumbing only (no strategy, no live change, nothing in the live loop imports it).

## Red team (bot-side files touched)
- engine/datafeed.py: parse_request accepts what "bf" (+ hb/hb0 bitmap, pages <= 12); post_request(extra=); answer() dispatches
  "bf" to engine/ofbackfill.answer_bf; send() keeps the new meta keys when trimming; maybe_answer() reads ntfy's count
  (GET /v1/account, not a message) at most every 15 min outside the session (LE_DATAFEED_BF=0 = off) to learn the real post rate.
- NEW engine/ofbackfill.py (PC budget + pages), engine/ofpack.py (lossless packer, stdlib), tools/of_backfill.py (cloud).
- tools/learn_night.py: new step `backfill` after `pull` (`--skip backfill` to leave it out; `--no-pull` skips it too).
- tests/test_datafeed.py check a. now allows the one /v1/account read.

## After landing
1. Nothing for the owner. It works once the PC has this code (the one-time unblock / auto-update).
2. The backfill runs inside learn_night. For the FIRST weekend, extra cloud runs help: the PC's 20 MiB / 3 h attachment room
   (~10 full pages) is the weekend limit, so one run every >= 3 h while the market is closed gets ~200+ days a run:
   `python tools/of_backfill.py --push` at e.g. Fri 19:30 ET, Fri 23:00, Sat 10:00, Sat 14:00 ET (a scheduled task in a cloud
   session; each run: restore -> ask -> 25 min wait -> push). Stop once the line says the PC holds no more.
3. Any research session first: `python tools/of_backfill.py --restore-only` (unpacks branch of-store into data/pc_days).
4. Branch `of-store` = data only (~2 MB a month packed). The first push creates it.
