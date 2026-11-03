"""ARENA, Olympian Ranks: XP, ranks, the 12 Labours, daily quests and streaks from verifiable events across OLYMPUS.

  events.py   the trading events from the published site data (data.json / home.json)
  score.py    the rules engine (rules.json), the Python twin of tools/web_public/arena/rules.js
  fixture.py  the demo
  build.py    events.json + jarvis.json for the site (python -m tools.arena.build --site site | --demo)
Paper only and read-only: nothing here touches a bot. Test: python -X utf8 -m tests.test_arena
"""
