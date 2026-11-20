# LEAD WIRES: day-fleet (2026-11-20)

Branch `day-fleet`. Nothing live touched (no engine/, server.py, live_model*, accounts/, sw.js, build_web_dashboard, apps.js, APPS).

## Already on the branch (just merge)
- New: tools/money/fleet_months.py, tests/test_fleet_months.py, research/lab/fleet_months.json,
  tools/web_public/business/fleet_plan.json (day-fleet owns it), research/writeups/fleet-plan-2026-11-20.md, this folder.
- tests/run_area.py: one own line under the money_ideas line:
  `AREAS["money"].append("fleet_months")  # day-fleet 2026-11-20: ...`
  If it clashes in the merge, keep both lines.

## For day-arenas (hera/ shows fleet_plan.json if present): what to show
Read `../business/fleet_plan.json` (relative to hera/). The fields are stable (v 1):
- `months[]`: `{m: "2027-01", median, bad, median_half, median_ref}`. Show one row per month Dec-Jun: "Normal $median",
  "Bad month $bad". Hide the 2026-11 row, or fold it into Dec.
- `total`: `{median, bad, median_half, median_ref, median_stress}`. Headline: "By June: $total.median (bad case
  $total.bad)", with a small line under it: "if the edge halves $median_half, 2021-25-like $median_ref".
- `next_buy`: `{what, price, code, when_med, when_p10, when_p90, chance, from}`. Line: "Next buy: Rapid EOD 50K $165
  (CLUB), about Jan 5 (Dec 14 - Feb 12), from payouts only".
- `top_cards[]`: `{id, what, yes_usd_month, yes_usd_month_half, yes_usd_month_ref}`. Show the 3 rows with links to the
  Decide card id.
- `tax_note`: always print it under the table (the 35% is a placeholder).
If hera/ has a service worker cache list, it needs a bump so phones fetch the new JSON (that is the lead's or day-arenas'
file, not mine).

## For day-taxes
When the exact Maryland-inclusive % is published: set `TAX` in tools/money/fleet_months.py (today 0.35), then run
`python -X utf8 tools/money/fleet_months.py` (~5 min) and `python -X utf8 -m tests.test_fleet_months`. The test follows
`FM.TAX`, so no test edit is needed.

## Optional (lead's call)
- Decide cards (tools/web_public/business/decisions.json): add a line to the 3 top cards' impact text from
  fleet_months.json `ranked_cards` ("whole fleet, after a 35% set-aside: +$390 / +$33 / -$32 a month"). I did not edit
  decisions.json (money_plan.py writes its value fields).
- STATE.md line (Live now / Waiting):
  `- Fleet to June 2027 (day-fleet 2026-11-20, research/writeups/fleet-plan-2026-11-20.md, tools/money/fleet_months.py): all 5 slots + K8, 1,000 paths, after fees + 35% tax set-aside (placeholder): Jul-Oct-like median Dec $74 / Jan $572 / Feb $1,523 / Mar $2,731 / Apr $3,434 / May $3,548 / Jun $3,874, total $19,510 (bad 1-in-10 $6,886); half edge ~$0 a month (total $1,987); 2021-25-like -$1,347 (re-buys). Next buy Rapid EOD 50K $165 ~Jan 5 (Dec 14-Feb 12) from payouts. Top cards: atlas-on-rapid +$390, zlarior-funded25 +$159 (+ in all 3 markets), zlarior-atlas-50k +$209. Phone: business/fleet_plan.json.`
