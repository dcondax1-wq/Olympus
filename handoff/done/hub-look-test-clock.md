# hub-look-test-clock

- Scope: tests only; no dashboard runtime, worker, bot, model, or routing files changed.
- Change: the Jarvis hub `look` run now switches scheduled bot cards off before its What's New page opens, matching the isolation already used by `test_jarvis_talk.py`.
- Reason: the 01:45 plan and 09:15 pre-market clock windows could put a scheduled bot card ahead of the What's New card and make the assertion depend on wall-clock time.
- Verification:
  - `python -X utf8 -m py_compile tests/test_jarvis_hub.py tests/test_jarvis_talk.py` — PASS.
  - Static clock-isolation check — PASS: the hub test uses the same `jarvis.bots.set` value as the talk test and applies it after creating the What's New context but before navigation.
  - `python tools/chatgpt_guard.py --files tests/test_jarvis_hub.py handoff/done/hub-look-test-clock.md` — PASS (`2 changed file(s)`, `OK`).
  - Current-main merge on `af57c110`; `chatgpt-guard` run `42239972741` — PASS. The full browser suite remains unrun in this connector-only checkout; this change affects the test harness only.
