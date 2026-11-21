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
| 2026-11-20 | Owner ran ADD_ACCOUNT 5 (Rapid EOD 25K, ...6020) + STOP/START BOT ~16:27 ET: 16:42 report = Rapid connected but 'Off: LIVE account ...6020 refused: start config is not armed' (Zlarior armed, ATLAS on, 25K #2 connected) | Rapid trades nothing until fixed (no loss before Sun 18:00) | OPEN: check after tonight's pc push restart (accounts.json may already hold armed=True if the phrase was typed: possible race = server auto-resume starts the bot before account_cli.arm writes); else owner re-runs START BOT Sat. Weekend landing: root-cause + fix START BOT so a newly added account is armed in the same run |
| 2026-11-20 | PC auto-update rolled back every hour since ~01:01 ET: 2 screenshots named 'hub_?h=bots-*.png' (Windows refuses '?'), so NO landing since then reached the PC (ntfy-cap fix, add-account box ...) | every fix stuck off the PC; ntfy silence could repeat Mon | FIXED pc ef2862c2 (renamed) + guard tools/win_paths.py in smoke + ship.py (6c67974b, lands 19:05) |
| 2026-11-20 | Payout pushes disagree: lifecycle says 'PAYOUT READY up to $250' at $1,350, funded_life says 'request $750' at $1,850; the plan (CLAUDE.md, phone goal) is $1,000 at $2,100; ACCOUNT_RULES.md:56 '$26,850' is the $750 line | ~$10-13/mo if followed every time + lost trust in payout numbers | BRANCH weekend landing (funded_life ask_above 1000/2000, payout_ready only when funded_life ready, consistency push only above buffer) + docs fix |
| 2026-11-20 | board.py / truth_check read a STOPPED bot's paper numbers as live 'fresh' truth (50K room $1,771 vs real $1,025) | wrong numbers while the bot is stopped | FIX tonight (NQ team) |
| 2026-11-20 | ZEUS card stays green ('PC reported 7 min ago') while the bot is stopped; shows ATLAS as an unfunded passed eval $26,946 | a stopped bot in trading hours looks fine | FIX tonight (NQ team) |
| 2026-11-20 | ATLAS's passed-EVAL trades booked as 'ATLAS funded 25K': Trading page +$2,024, Friday push +$2,193, real funded profit $401; payout consistency advice off ~$930-2,555 | wrong $ on screens + wrong payout advice | FIX tonight (NQ team) |
| 2026-11-20 | Pass / payout dates contradict across Goals, Accounts, Payday (two Monte Carlo runs mixed; pass dates 9-14 days early) | confusing plan dates | FIX (taxes/money team) |
| 2026-11-20 | Payout #5 on any Builder moves him to live and parks every other MFFU sim account; the PAYOUT READY push gives no warning | ~$1,000-2,500/mo in a good 2027 if tapped by reflex | CARD later (2027); warning text in the weekend landing |
| 2026-11-20 | Finder loop: no quiet hours (8 rounds a day, 8-12 agents each, 1.7M tokens this round) | usage quota | FIXED: cadence 9:30/12:30/15:30/18:30/21:30 ET only |
| 2026-11-20 | Taxes: a payout possible Dec 24-31 should be taken in December, not 'ask on Jan 1' (writeup) | ~$113-162 per $800 payout if no day job | FIX taxes page/writeup (taxes team) |
| 2026-11-20 | Taxes page says pay the whole tax pot by Jan 15 as a 2026 payment, even for payouts landing in Jan 2027 | mis-filed payment | FIX (taxes team) |
| 2026-11-20 | Parents' plan: if it is an HSA-type high-deductible plan and he is NOT their tax dependent, he can fund the FAMILY HSA limit ($9,000 in 2027) himself | ~$1,600-2,300/yr from 2027 if both true | CARD: owner question (HDHP? dependent?) |
| 2026-11-20 | Paid through Rise (stablecoin): likely 'Yes' on the 1040 digital-asset question; the page never says so | compliance only, $0 tax | FIX taxes page note (or choose MFFU ACH/Plaid) |
| 2026-11-20 | REFUTED: a one-day MFFU soft pause read as a permanent LOCK (needs a hand-trade loss to the soft limit + a later bot entry; <1%/wk; LOCKED push + --clear) | ~$20-50 if it ever happens | REFUTED (low); note for the weekend red-team |
| 2026-11-20 | REFUTED: ATLAS on the idle 25K #2 eval too (real fills -> +$50-150/mo at best, more eval deaths, links to ATLAS funded) | - | REFUTED |
| 2026-11-20 | The olympus repo is PUBLIC (GitHub API private=false) though the owner asked 11-19 to make it private | STATE, notes and any branch readable by anyone | OWNER STEP Sat (Settings -> Change visibility -> Private, then GITHUB_SIGNIN.bat); every agency-inbox push gated on repo_private (day-a11y d91d706a, day-caller) |
| 2026-11-20 | Night look + effects made some apps slower (4x CPU): zenith LCP 1.8 -> 4.7 s, jarvis TBT 2.8 -> 5.1 s (and it loads the full 128 KB trades.json), board LCP 3.0 -> 5.0 s, nq TBT 525 -> 880 ms | slower phone opens | Sat speed list (DESIGN, Jarvis, day-archive, NQ) |
| 2026-11-20 | Jarvis's payout answer quotes the NinjaTrader number ($27,100) instead of MFFU's ($2,100) | confusing numbers | Sat (Jarvis team; jarvis_skills 84/85) |
| 2026-11-20 | Rapid EOD 25K still 'refused: start config is not armed' after the PC's 18:01 update restart -> the phrase never reached its config | the Rapid trades nothing | OWNER Sat: STOP BOT, START BOT, phrase; weekend landing fixes START BOT arming |
| 2026-11-21 12:31 ET | Finder round skipped: the weekend bot landing (red-team of 9 branches, 2 fixers, 10-day replay gate) was running; it covers the same ground | - | SKIPPED (landing running) |
| 2026-11-21 15:31 ET | 7-day clocks (engine.keepalive.plan, PC silent since Fri 21:00 so last fills are the 11-20 notes): Zlarior 50K last fill Mon 11-16 -> MFFU hard day Mon 11-23 (the keep-alive, if ON, acts only that day 15:33); 25K #2 hard Tue 11-24; Rapid hard Wed 11-25; ATLAS hard Fri 11-27. Unless the owner's Friday hand trades happened, the 50K has ONE session left | the 50K eval ($91.80 + its progress) | OWNER: 1 MNQ in and out by hand on the 50K Sun after 18:00 ET while every account is flat, or KEEPALIVE_ON.bat before Sun 18:00 |
