# New strategy: research lane to live switch in hours (day-zerotouch2, 2026-11-24)

Owner: "anything we could ever need again, whether adding strategies or such, should all be done way quicker".

| Step | Who | What | Time |
|---|---|---|---|
| 1 | Claude | `python -X utf8 tools/new_strategy.py <id> --label "one plain line"`: lane switch (OFF), proof script, test, Decide card | 1 min |
| 2 | Claude | Fill `research/lanes/<id>/proof.py` `run()` by the strategy-test protocol (futures data only, costs in, both 2026 halves + 2021-25, 2-4 trades/week; check "Tested and rejected" in STATE first). Run it: `PROOF.json` says passed or not | hours |
| 3 | Claude | `python -X utf8 -m tests.test_lane_<id>` green; fill `signal()`; the lead wires it into a bot behind `is_on()` and ships | 1 h |
| 4 | Lead | Add `research/lanes/<id>/decide_card.json` to the Decide cards | 1 min |
| 5 | Owner | Phone: YES on the card, or PC Control page, "Switch on at my next START" (queues `lane:<id>`) | 10 s |
| 6 | Owner | His normal START + I ACCEPT LIVE RISK: START shows the queued switch FIRST and the same phrase turns it on | 0 extra |

Rules that never bend: the switch only turns on with the typed live phrase AND a passed PROOF.json; nothing remote arms;
`live_model*.json` / `second_model.json` are never touched by the scaffold; a lane stays OFF until both are true.

Pieces: `engine/lanes/` (the registry: `ids()`, `load()`), `engine/pending_switch.py` (the queue; also `combo_on`, `blitz_on`),
`engine/remote_ctl` commands `switch` and `add_account`, `engine/go` (START's first line + apply after the phrase),
the phone page `tools/web_public/pc/control.html`. Tests: `tests/test_zerotouch2.py` f-g.
