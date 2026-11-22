# Lead-only wires (ARM fixer 2026-11-22)
- `engine/brain_glance.py` now adds a small optional `nar` string to the lit / atlas glance bot ("ATLAS is NOT armed: <reason>", only when not armed and the last START saved a reason in data/arm_status.json). `tools/web_public/nq/braincore.js` shows it in the Bot row.
- Trading Home "Today" line (jarvis/apps.js, not edited here): when `pc.glance.bots[i].nar` exists, show it instead of the bare "armed false".
