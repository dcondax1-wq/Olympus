# Findings ledger (the finder loop's memory: never repeat an item)

Owner 2026-11-20: "every time I talk to you, I feel like there's always more you find... just keep finding stuff."
A scheduled round runs every 3 hours (trigger "Finder loop: keep finding and fixing"): 6 lenses find, an adversarial check
refutes, survivors land here. Status: FIXED (commit), BRANCH (built, waits for a red-team / weekend landing), CARD (owner yes/no),
WATCH (not actionable yet), REFUTED (checked, not real). Already-known ideas: research/handoff/2026-11-20/TOP25_IDEAS.txt (25).

| Date | Finding | $ / risk | Status |
|---|---|---|---|
| 2026-11-20 | ntfy per-IP daily cap (250) hit 09:45 ET: PC went silent, alerts lost | lost alerts on live days | FIXED 58d8d701 (ext every 3rd run, quota reserve) |
| 2026-11-20 | Zlarior 50K + 25K #2: MFFU 7-day inactivity (last fill Mon 11-16 / never) | account closure | owner hand trades 11-20; keep-alive BRANCH wf-keepalive |
| 2026-11-20 | ATLAS entry/exit alerts never reached the phone (Web Push 'accepted' hid ntfy) | missed alerts | BRANCH wf-alert-fix (round 2 review) |
| 2026-11-20 | Hedge guard blind to hand trades | cross-account hedge = every account | BRANCH day-redteam2 (TOP25 #1) |
| 2026-11-20 | Every site push restarts the bot; no crash rollback | lost London trades | BRANCH day-security2 (TOP25 #4) |
| 2026-11-20 | AccountB.start TypeError without eval_start (ATLAS silently off) | ATLAS not trading | BRANCH wf-atlas-start |
| 2026-11-20 | Home/Glance/Helios showed the cloud paper twin ($49,900) as Zlarior | wrong numbers | FIXED (day-nqdash3 36097a11, day-arenas) |
| 2026-11-20 | Data City black on drag (pixel-ratio step wiped the canvas) | broken screen | FIXED day-cities3 b267d97c |
| 2026-11-20 | Ask Jarvis button covered text / Planner Save | broken taps | FIXED 4f637df3 |
| 2026-11-20 | Agency pages: Back-to-Jarvis link 404 at agency/offers/, owner pages indexable | broken link, exposure | FIXED a3d214dd |
| 2026-11-20 | MFFU sim-funded balances start at $0 (owner); pages showed $25,401 for ATLAS funded | wrong numbers on every page | FIX in flight (pc_feed mffuView, widget 48fb8f96, NQ goals, Jarvis) + CLAUDE.md 2f7310fb |
| 2026-11-20 | MFFU pages conflict: Builder 50K guide (2026-10-21) "only one Sim Funded account per user on the Builder Plan" vs the limits article (50K x1 + 25K x2) | Zlarior's 50K might not go funded while ATLAS's 25K is (~Dec 24) | WATCH (we follow the newer limits article; check the MFFU dashboard when Zlarior passes) |
| 2026-11-20 | engine/lit.py backtest COMM $1.40 vs MFFU's $1.90 MNQ round turn | backtests ~$310-350 a year too rosy | BRANCH next (research cost fix, no live change) |
| 2026-11-20 | No inactivity guard in engine/live.py / cloud_monitor (2026 replay: 3 gaps of 7+ days) | 7-day rule forfeits sim profits | BRANCH wf-keepalive |
| 2026-11-20 | rapid_eod_25k block was missing from mffu_rules.json | Rapid rules unchecked | FIXED day-taxes ef9965ed (+ tests/test_account_rules.py 35/35) |
| 2026-11-20 | ATLAS real fills vs the 1m open: today 22 ticks worse (26,375.50 vs 26,381.00), median 14 ticks over 4 fills | ~$7 a trade on 1 MNQ (~$30-60/month) | WATCH; day-speed proposes datapipe stamps sent_at / fill_mtime in the day bundle (data only, weekend landing) so fast entry can be measured |
| 2026-11-20 | Update gate replay: day-speed vs pc on today's real 03:45 ATLAS short = SAME (SELL 1, +$514.28; PC booked +$514.18), poll 413 -> 237 ms | proof the speed-up trades identically | BRANCH day-speed 97dea895 (weekend landing) |
| 2026-11-20 | Site pages polled the old suspended GitHub account (2 x 404 a page) | slow pages, noise | FIXED day-nqdash3 4c191810 (DEV_ONLY gate + test_repo_secrets c); jarvis/data.js fallback still left (only when ntfy is empty) WATCH |
| 2026-11-20 | Jarvis FX push f39745cd turned the switcher cyan, the very look the owner picked (black/violet/gold) | owner's chosen look lost | HELD back; Jarvis team re-pointing to OLYMPUS NIGHT by 18:30 |
| 2026-11-20 | Keep-alive warnings told the owner to ask MFFU support (he will not contact MFFU) | owner stuck at day 6 | FIXED wf-keepalive c4717b5a (KEEPALIVE_ON.bat, owner said YES) |
