# LEAD_WIRES: human caller pack (day-caller2, 2026-11-21, base pc 7adf312d)

New files only: `agency/dnc_scrub.py`, `tests/test_dnc_scrub.py`, `docs/HUMAN_CALLER.md`, `research/handoff/2026-11-21/caller/*`.
Nothing existing edited (not agency/portal.py, not the portal page, not run_area).

1. **run_area:** `AREAS["agency"].append("dnc_scrub")   # day-caller2 2026-11-21: the caller list vs the DNC registry`
2. **The publish order** (whoever runs the portal build: AGENCY_DAY / the PC job): `python -m agency.portal build` then
   `python -m agency.dnc_scrub` then publish. The scrub exits 1 and marks the list `"dnc": "STALE"` with no or an old registry copy.
3. **day-a11y (the portal page), please:** show a red "Not checked against Do-Not-Call: don't dial" banner when calllist.json has
   `dnc` != "scrubbed". Show the `dnc_date` in the list header. The pack tells callers to stop on that banner.
4. **day-a11y, commissions:** `agency.portal commissions` sums won x $300 + showed x $40 together. The pack says each caller picks ONE
   plan. Please add a per-caller plan (`sale` or `booked_show`) so "owed" counts only the chosen one.
5. **STATE "Waiting on the owner":** "Hire the caller: Monday 15 min (research/handoff/2026-11-21/caller/README.md); the DNC sign-up
   (10 min) before the first dial."
6. Placeholders `<Agency>`, `<agency email>`, `<Owner>`, `<postal address>`, `<agency phone>` in the pack: fill them once the owner names the agency.

Checks run: `python -X utf8 -m tests.test_dnc_scrub` 9/9.
