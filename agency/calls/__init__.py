"""Call copilot, PC side (team B2, 2026-11-14): turns team B1's leads into a call list the phone page imports.

    python -m agency.calls.build                      # finds B1's lead files under agency/, writes agency/calls/out/call_list.json + .csv
    python -m agency.calls.build --dnc dnc_813.txt    # marks every lead on the National Do Not Call download (see docs/COLD_CALLING_RULES.md part 3)
    python -m agency.calls.build --merge export.json  # the phone's export: its "do not call" numbers join the master opt-out list for good

core.py is the twin of tools/web_public/agency/callcore.js (same rules file, same answers; tests/test_cold_calls.py checks both).
Everything stays on this PC (agency/calls/out/ is git-ignored); nothing here dials, texts, emails or uploads anything.
"""
