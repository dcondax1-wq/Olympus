# LEAD_WIRES (day-litedge)

No lead-only file edits needed: no sw.js, no build_web_dashboard.py, no apps.js, no APPS table, no ?v= tags, no cache names.

After merging, two shared indexes (left untouched here to avoid merge clashes with the other day helpers):

1. Re-generate the write-up index: `python tools/writeups_index.py` (adds research/writeups/lit-edge-2026-11-20.md).
2. Paste at the top of the list in `docs/TESTED_AND_REJECTED.md`:

```
- **Zlarior edge, 5 pre-registered ideas (2026-11-20, `lit-edge-2026-11-20.md`, `tools/research/litedge.py`,
  `research/lit/litedge.json`, design `research/lit/litedge_design_2026-11-20.md`):** LIT $/month H1 / H2 / 2021-25 vs
  today $5,562 / $2,670 / $25: limit 2 ticks better than the model fill for 1 min, else market $5,184 / $2,585 / $26;
  skip a setup when the 1m entry is > 60 min after the sweep bar $849 / $824 / $119 (1.2 / 0.8 trades a week); Tier-1
  day target capped at 4R $4,997 / $2,616 / $89; MES instead of MNQ when ES's planned target R >= 1.25 x NQ's $5,069 /
  $9,656 / $198 (fails Jan-Jun, eval -$10.6k / +$7.0k; paper lead, forward only); no +1R breakeven in the first 10 min
  $5,068 / $2,670 / $25. 0 pass. Fill map: limits 10-50% of the risk better fill 0-60% and miss $17-34k of Jan-Jun
  winners. +10 ticks a trade: $5,176 / $2,447 / -$353. Cold run (7 twin trades -4.2R) = 8.8% of 2026 7-trade windows.
```

3. STATE.md: one line under Zlarior if wanted: "2026-11-20 litedge: 5 new ideas, 0 pass; cold run is normal variance
   (wide stops, small size); ES-room switch is a forward-watch paper lead only."
