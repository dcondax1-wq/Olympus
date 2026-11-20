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
