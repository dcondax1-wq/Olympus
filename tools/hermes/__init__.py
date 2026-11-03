"""HERMES, the messenger god: "OLYMPUS Wrapped", a story-style recap of the week / month / all time (owner 2026-11-03).

  wrapped.py   the pure core: data.json (+ home.json, live.json) -> wrapped.json and the Jarvis card. No I/O, no clock.
  fixture.py   a deterministic demo data.json (the page's demo, and the tests' input).
  build.py     the CLI and publish(site): reads the built site, writes <site>/hermes/wrapped.json + jarvis.json.

The page is tools/web_public/hermes/ (published at <site>/hermes/ by tools/build_web_dashboard.py). Read-only: it never
touches trading logic or live_model*.json.
"""
