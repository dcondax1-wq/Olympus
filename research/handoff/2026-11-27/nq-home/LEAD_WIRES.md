# night-nq-home 2026-11-27: what the lead wires (files I may not touch)

## 1. PC report: send the 4 health facts the page shows grey today (tools/pc_report.py `full()`, engine side)
PC Health (nq/pchealth.html) already reads an `al` block when it is present: no page change needed.
```python
# in the full status post, next to "ck" / "sh":
out["al"] = {
    "tg": bool(snap.get("alerts_pc")),             # Telegram alerts set up (token + chat id present) -> green / amber "Not set up"
    "od": "onedrive" in ROOT.lower(),              # bot folder inside OneDrive -> amber "syncing can lock files"
    "ut": last_update_unix,                        # when the auto-update last INSTALLED a new version (logs/auto_update*.json) -> "Last update 3.2 h ago"
}
```
Optional later: hang-guard last trip (`hg`: unix time + reason) -> one more check.

## 2. Links (sw.js / apps tables are yours)
- sw.js precache: `nq/pchealth.html`, `nq/pchealth.js`, `nq/pchealth.css`, `nq/pchealth_core.js` (trading_home.html now also loads pchealth_core.js + news_week.json).
- Optional: a "PC Health" entry in the NQ app nav / Jarvis switcher -> `nq/pchealth.html`. Trading Home already links it (red tile first when something needs the owner).

## 3. tests/run_area.py
I added one line: `AREAS["nq"].append("nq_home")` (tests/test_nq_home.py, 64 checks, ~20 s). Drop it if you prefer to wire it yourself.

## 4. For the money side (seen in the real post)
- `tr`: 312 tick days on the PC, backfill DONE, oldest 2025-11-28: the order-flow battery + mill can run on real days now (tools/of_send_now.py on the PC after 16:05 ET, then `python tools/data_pull.py --of`).
- Ready check says NOT READY (ATLAS 25K not armed) while `ck.acc` says all 4 armed: the two disagree on the PC. The page shows both honestly; worth a look in engine/readiness vs pc_checklist.
- NinjaTrader "Connect on startup" is off: after a PC restart nothing trades until the owner logs in.
