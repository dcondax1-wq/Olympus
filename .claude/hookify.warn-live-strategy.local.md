---
name: warn-live-strategy
enabled: true
event: file
action: warn
conditions:
  - field: file_path
    operator: regex_match
    pattern: live_model(_lit|_engine)?\.json$|research/lit/lit_final\.json$|engine/(ninjatrader|tradovate|lit_live|live)\.py$
---

⚠️ **This edit changes the live strategy or order routing.**

Before keeping it: the owner must have asked for this change, the result must show net $ and $/month with the 2026
H1 (pick) and H2 (check) numbers, it must keep 2-4 trades a week, and everything stays paper only.
If the owner didn't ask for it, undo the edit and ask first.
