# LEAD_WIRES: trade scripts, cadence, scorecard, first day (day-caller2, 2026-11-22)

New: `agency/trade_scripts.json`, `agency/trade_scripts.py`, `tools/web_public/agency/portal/scripts.json` (portal copy, generated),
`tests/test_trade_scripts.py`, `research/handoff/2026-11-22/caller/*`. Changed: `agency/portal.py` (a `scorecard` command and a `sold` count
in commissions), `agency/pricebook.py` (the new sheets join the price sync).

1. **run_area:** `AREAS["agency"].append("trade_scripts")   # day-caller2 2026-11-22: per-trade scripts + the caller scorecard`
2. **day-a11y (portal page), please:** read `portal/scripts.json` and, for each lead, show the trade's opener by `lead.kind`, using the
   same first-match rule as `agency.trade_scripts.trade_for`: a kind containing " store" (not a restaurant) uses the generic script. Use
   `lead.lane` for the no-site / site-down opener and fill `{me} {agency} {name} {owner} {day} {my_number}`. Until then the caller reads
   TRADE_SCRIPTS.md beside the portal; the portal's own opener stays as it is (it is legal and short).
3. **day-a11y (email autopilot), please:** the cadence's day-7 and day-14 emails come from you. A portal log line `interested` or
   `voicemail` with no reply -> day 7 "did you get a chance to look?", day 14 "closing your file, the link stays up 30 days". Never after
   no / dnc. These are the caller's emails, so `inbox_id` is "" and the `kind` is demo.
4. **Texts:** only by hand from the caller's Google Voice number after the business said "text it to me" on the call. Nothing automated.
   Business texting at volume needs 10DLC registration; we don't do it.
5. **Pricebook:** `TRADE_SCRIPTS.md` and `FIRST_DAY.md` are in `python -m agency.pricebook --check` now, so a price change flags them.

Tests here: trade_scripts 12/12, web_portal 38/38, pricebook 5/5, smoke 10/11 (zenith_mode: no Python Playwright in this container).
