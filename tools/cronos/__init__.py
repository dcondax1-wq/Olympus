"""CRONOS: the nightly refresh that keeps OLYMPUS alive (research and paper only; never touches trading logic or live_model*.json).

    python -X utf8 -m tools.cronos --all --out pub            # every task CRONOS runs itself (nightly + weekly)
    python -X utf8 -m tools.cronos --group nightly --out pub  # what .github/workflows/cronos.yml runs after the CME close
    python -X utf8 -m tools.cronos --task fates --out pub     # one task
    python -X utf8 -m tools.cronos --list                     # the registry

  registry.py  the tasks: app, cadence, timeout, max age, the files it publishes, its inputs
  run.py       the orchestrator: each task in a subprocess with its own timeout; a failure is recorded, never raised;
               writes <out>/cronos/status.json and a Markdown log for the Actions run summary
  fresh.py     the honest freshness of each app's Jarvis card (fresh / stale / failed -> the card fields)
  site.py      the site build's side (tools/build_web_dashboard.py): pull the `cronos` and `datacity` branches' JSON into the
               site when newer than the page's copy, then stamp every research app's jarvis.json

<out> mirrors the site: <out>/fates/fates.json, <out>/odeon/trades.json, ... + <out>/cronos/status.json. The workflow
force-pushes it as ONE commit to the `cronos` branch (main never gets bot commits); the site build reads it from there.
Docs: docs/CRONOS.md. Tests: python -X utf8 -m tests.test_cronos
"""
