---
name: block-live-arming
enabled: true
event: bash
pattern: NINJATRADER_LIVE\s*=\s*1|setx\s+NINJATRADER_LIVE|\$env:NINJATRADER_LIVE\s*=
action: block
---

🛑 **Blocked: this would arm live trading.**

Hard rule: paper only. Never arm live trading or place real orders. The owner goes live on the eval himself
(`docs/GO_LIVE_TONIGHT.md`). Tell the owner what you wanted to do instead.
