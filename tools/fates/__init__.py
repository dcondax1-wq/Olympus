"""FATES (2026-11-03): a Monte Carlo of the owner's MFFU evals and money, drawn as threads of fate on
tools/web_public/fates/ (research/writeups/2026-11-03-fates.md).

  rules.py    MFFU's eval rules as plain state (floor, daily loss, target + min days, 7 quiet days, keep-alive)
  sources.py  the bots' real per-session trades and their live sizing (Zlarior via tools/uprisk.py, ATLAS via tools/atx_edge.py)
  live.py     today's eval state from the PC's published live.json (fallbacks: the owner's numbers)
  sim.py      the block bootstrap, one eval from today, a book of 1-6 account slots (eval -> funded -> payouts -> next eval)
  export.py   the page's JSON (schema + checks) and Jarvis's card
  build.py    python -X utf8 -m tools.fates.build   -> tools/web_public/fates/fates.json + jarvis.json

Paper only: reads replays and the live feed, never trades or changes a live setting. Tests: python -X utf8 -m tests.test_fates
"""
