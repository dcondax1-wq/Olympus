# Make the human caller convert (day-caller2, 2026-11-22)

| File | What |
|---|---|
| `TRADE_SCRIPTS.md` | the 8 trades (roofing, HVAC, plumbing, electrical, landscaping, remodeling, auto repair, restaurants) + any other business: a 15-second opener (no site / site down / old site), 3 questions, the yes-close with the deposit link, not-now, voicemail; and the 2-week follow-up |
| `TARGET_SHEET.md` | the caller's daily target sheet: 50 dials, 10 talks, 2 links, 1 booked (training days 30 / 6 / 1 / 0), the rates to watch |
| `FIRST_DAY.md` | the owner trains the caller in 15 minutes: rules, portal, 2 role-plays, voicemail + "no", targets + pay, red flags |
| `agency/trade_scripts.json` + `.py` | the one source; `python -m agency.trade_scripts --md ... --json ...` regenerates the sheet and the portal copy |
| `agency/portal.py scorecard` | `python -m agency.portal scorecard [--days 1/5/10]`: per caller dials, talks, links, booked vs targets, sold, $ owed / pending / clawback |
| `tests/test_trade_scripts.py` | 12 checks |
