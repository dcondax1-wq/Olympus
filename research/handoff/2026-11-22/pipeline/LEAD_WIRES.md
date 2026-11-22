# MONEY PIPELINE: lead wires (day-a11y 2026-11-22)

The page (tools/web_public/business/pipeline.html) already works without these: it counts the phone's own caller log and the trading payouts.
These lines make the PC's cleared website $ reach it.

1. **pc_report ext "ap"** (the PC report's ext block, next to the others):
   - add `"ap"` to `EXT_ORDER`
   - where the ext snapshot is built: `from agency import pipeline as _ap; snap["ap"] = _ap.read_card()` (None when the PC has no card yet)
   - in the lite output: `out["ap"] = snap.get("ap")` (counts + $ only: no names, no phones, no ids; tests/test_money_pipeline.py checks the card keys)
2. **PC task**: run `python -m agency.pipeline` before the report (it writes data/agency_pipeline/summary.json, gitignored).
3. **sw.js**: precache `business/pipeline.html`, `pipeline.css`, `pipeline.js`, `pipelinecore.js` (all ?v=1).
4. **APPS table / apps.js** (optional): a "Pipeline" entry under Money -> `business/pipeline.html`. Home's Money tile already links it (it replaced "Taxes"; Taxes stays under More / Money door).
