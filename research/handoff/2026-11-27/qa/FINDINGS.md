# NQ quality + truth audit (night-nq-qa, 2026-11-27 ~00:10 ET)

Live site https://dcondax1-wq.github.io/ (nq/, nq/live, nq/accounts, nq/brain, nq/trading_home, brain/, brain/learned), Chromium
390x844 (mobile, dark) + 1440x900, 8 s after load, full-page shots (`shots/`, phone slices = one screen each). Truth = `tools/board.py
read` + `tools/truth_check.py` + the PC's newest ntfy post at 00:02 ET (Zlarior 50K $49,177.52, 25K #2 $25,019.24, ATLAS +$401.38,
Rapid $24,995.24, all armed, PC price 26,745.25).

Clean (no work needed): every tap target >= 44 px on all 7 pages (37 on nq/), no JS error except one 404, no cyan / brown / olive
colours found by the colour sampler, load 0.25-1.8 s, no NaN / undefined / null text, the 4 balances match the PC on every page.

Owner = main (index/nq/nqtheme/nqscene/nqland/nqdesk), chart (nqchart*/nqbars), live (live*), accounts (accounts*/acctcore/payready*/
nqgoals*), of (orderflow*), brain (brain*/braincore), home (trading_home*/pchealth*).

## Ranked by how bad it looks to the owner

| # | Page | What the owner sees | Cause | Owner | Shot |
|---|---|---|---|---|---|
| 1 | nq/trading_home | **"NOT READY for 02:00: ATLAS 25K is not armed"** at the top, while Live ("ATLAS: running, armed") and Accounts ("ATLAS · ARMED") say armed. The text is also cut mid-word ("(Claud") and says "press 2" while its own button line says "press 1" | the card shows the PC's readiness line (rd block) verbatim, truncated; the readiness and the heartbeat disagree about ATLAS (the PC's preflight reads ATLAS's kind/label; check after tonight's PC update) | home (+ lead: engine readiness) | phone-nq_trading_home_0 |
| 2 | nq/ Live chart vs brain/ | **Two NQ prices 496 pts apart**: the chart's last bar 26,249.25 "Thu 12:15 ET, 11 hours 45 minutes ago" vs the Brain header "NQ 26,745.25 · PC just now". The chart looks frozen while Globex trades | the chart only gets bars "about every hour 01:50-16:10 ET"; evenings never refresh, and it never says which price is current | chart (+ live for the label) | phone-nq_index_1, phone-brain_index_0 |
| 3 | nq/ "ATLAS first payout" | **a big empty black box** (the 3D scene never draws) above the payout text | the card's canvas stays blank (other WebGL scenes on the page draw fine) | accounts (nqgoals / payready) | phone-nq_index_2 |
| 4 | nq/ + nq/accounts | **Payout numbers disagree**: NQ "$800 to you ... about Dec 18-31" vs Accounts "1st payout ~Dec 17 (~$747 to you)" | nq.js:346 hard-codes 80% of $1,000; acctcore.js:169 uses the forecast's first_pay_usd; two date sources | accounts + main (one source) | phone-nq_index_2, phone-nq_accounts_0 |
| 5 | nq/ | **14 phone screens long (11,700 px)**: the 4 accounts appear 4 times (Accounts grid, The numbers, GO/WAIT, the per-bot drawdown cards), 4 identical 7-day boxes all "Fine." | each block was added on its own | main | phone-nq_index_3..9 |
| 6 | brain/learned, nq/ Quality checks, nq/ Replay | **Old data everywhere**: "No new trading days scored yet (the bars end Nov 20)", Site data home.json 7 h old with trades to 11-20, Edge check 8 days old, "Replay a past day" newest = **Oct 28** (the Nov 17/18/20 trades missing) | the cloud's bar / trade copies stopped at Nov 20 (the PC's evening push was on held-back code until tonight); Replay reads an older list | lead (data push) + brain + main (Replay list) | phone-brain_learned_0, phone-nq_index_11 |
| 7 | nq/ GO / WAIT / HALT | the **ATLAS** row says "Before 02:00 ET: **LIT** takes no real entry yet" (wrong bot); all 4 rows identical | nqdesk.js:452 uses one LIT sentence for every account | main | phone-nq_index_6 |
| 8 | nq/ The plan for today | "flat by **15:55** ET" right above "next entry window Fri 02:00-**13:00** ET" (today is the half day) | the plan card ignores the early close | main | phone-nq_index_7 |
| 9 | nq/, brain/, nq/brain | **floating round buttons** (a gold ring at left, an "O" at right) sit on top of the 3D pillars / the brain on the phone and float mid-screen on desktop | two round controls are position:fixed at mid-height (find them in nqtheme / nqscene / brain css) | main (nqtheme / nqscene), brain | phone-nq_index_0, phone-nq_brain_0, desk |
| 10 | nq/ header | **7 nav pills wrap into 3 rows**, then "Main copy:" + a pill that runs to the screen edge | too many pills for 390 px | main | phone-nq_index_0 |
| 11 | nq/ pillars + brain/ | "**312/60 tick d...**" (cut) and "Collecting · 100% · **312 of 60** tick days" | collected days > target is shown as a ratio; should read "ready: 312 days" | brain + main (pillar chip) | phone-nq_index_1, phone-brain_index_0 |
| 12 | nq/accounts (phone) | the page is **411 px wide on a 390 px phone** (it zooms out a little / pans sideways) | something is wider than the screen while it loads (layout viewport grows to 411) | accounts | phone-nq_accounts_0 |
| 13 | all NQ pages (desktop) | everything in a **~600 px column**, ~60% of a 1440 screen black | single-column phone layout only | main / accounts / live | desk shots |
| 14 | nq/ (every load) | console **404 ../hub/learned.json** | nq.js:441 fetches a file the site does not publish | main (or lead: publish it) | - |
| 15 | nq/, live, learned | **cut / tiny text**: account names cut in the grid ("Zlarior" without "50K"), money-goal card cut ("+$3,8"), "Waiting for: ...(1.05...", the chart's "06:00" axis label clipped; 33 text runs under 11.5 px on nq/ (9.5-10.5 px pills "3/3 armed", "LIVE"), 77 on learned | fixed-width cards, ellipsis, small pill fonts | main, live, brain | phone-nq_index_1, phone-nq_index_3, phone-nq_live_1 |

## Also seen (lower)
- nq/ "Key levels: not in this report (the PC sends them with its brain glance)" twice: reads like an unfinished page (hide when empty). main
- nq/ "Today's market in 3D" is a flat 2D purple line; its caption still says "**cyan** an open one". main / chart
- nq/live "ATLAS **?**/5" placeholder in Setup progress. live
- nq/ "The bots" card: cream / marble columns with candle flames (owner: never marble). main
- nq/ Eval progress on the Rapid: "$1,505 to go to the $1,500 target (0% done)": reads odd (below start). main
- nq/brain 3D brain "Displacement" label overlaps the nodes. brain

## Not owned by the NQ pages (lead)
- The PC's board line "Self-heal could not fix: weekly encrypted backup made (5 files)" (23:47 ET): a SUCCESS reported as "could
  not fix" (engine/self_heal.fix_backup returns "need" on the first backup so START shows the recovery code). Mine (day-ops2):
  fix = status "fixed" + the code line stays in START. Engine change, not web: separate tiny branch on request.

## Second sweep (2026-11-27 ~04:25 ET): the live site after tonight's landing (pc 27e55f77 = live, all night-nq-* branches merged)

Same audit (`shots2/`), truth at 04:15 ET: balances unchanged ($49,177.52 / $25,019.24 / +$401.38 / $24,995.24), PC on 7c812f6,
NQ 26,837.75, readiness rd = ok. Clean again: 0 small taps, 0 cyan / brown, 0 NaN, 0 http errors, console = browser WebGL notes only.

| # | First-sweep finding | Now |
|---|---|---|
| 1 | Trading Home "ATLAS 25K is not armed" | **FIXED** (night-atlasarmed live on the PC at 01:01; Trading Home now leads with a real step: NinjaTrader connect-on-startup OFF) |
| 2 | chart 26,249 frozen vs brain 26,745 | **FIXED** on the chart ("LIVE · last bar 7 min ago", 26,832) and the brain (26,837.75); **NEW gap, see N1** |
| 3 | ATLAS first payout: empty black box | **STILL** (shots2/phone-nq_index_7) |
| 4 | payout $800 vs ~$747 | nq/ now "$800 to you at 80% ... earliest $250 at $1,350"; Accounts no longer shows the ATLAS ~$747 line: **mostly fixed** (one wording now) |
| 5 | nq/ 14 screens, accounts 4x | **PARTLY**: 3 blocks folded (Account details, Drawdown per account, Checks/replays), but the battle plan, odds and a calendar were added: still ~13 phone screens (11,199 px) |
| 6 | stale data (learned, replay) | learned **FIXED** (4 new days scored, Nov 23-26); Replay still "Loading when you get here..." inside the folded Checks block |
| 7 | GO/WAIT ATLAS row says "LIT" | moved into the folded Account details (not seen by default); text not re-checked |
| 8 | "flat by 15:55" on a half day | **STILL** in "The plan for today" ("...flat by 15:55 ET. entry window open until 13:00 ET"); the new battle plan says "the CME halts at 13:15 ET; every bot is flat before it" (the two cards now disagree on one screen) |
| 9 | floating round controls | **STILL**: the gold ring (left, mid-height) overlaps account cards on the phone; desktop still has a ring at the left and an "O" at the right edge |
| 10 | nav wraps into 3 rows | **FIXED** (one scrolling row); "Main copy:" pill still there |
| 11 | 312/60 tick days | brain **FIXED** ("Ready · 313 tick days collected (needed 60)"); nq/ pillar chip **STILL** "313/60 tick d..." |
| 12 | Accounts 411 px wide | **FIXED** (390) |
| 13 | desktop 600 px column | **FIXED** (wide hero + 4 account cards in a row) |
| 14 | 404 hub/learned.json | **FIXED** |
| 15 | tiny / cut text | **WORSE on live + accounts**: text runs < 11.5 px nq/ 33 -> 37, live 18 -> 33, accounts 8 -> 38 (10.5 px labels: "Today, all accounts", "Room left, all", "Balance", "ARMED"); learned 77 -> 0 |

### New since the first sweep
| # | Page | What the owner sees | Cause | Owner |
|---|---|---|---|---|
| N1 | nq/ Today's battle plan + What the bots are thinking | **"Price 26,228.75 — now"** while NQ is 26,837 (609 pts off, labelled now); **PWH 28,279 (+2,050 pts)** is implausible (NQ never traded there last week) | the levels table reads the cloud brief (bars to 2026-11-26 12:55) and calls its last close "now"; PWH looks like a bad weekly bar | main (battle plan) + chart/brief data |
| N2 | desktop nq/ | the new **bottom dock + "PC 8m · 4 armed" pill float in the MIDDLE of the hero card** (over the 4 account cards) | the dock is position:fixed bottom inside a short desktop viewport (900 px) and overlays content | main (nqtheme / dock) |
| N3 | phone, every NQ page | three floating things stacked at the bottom: the dock, the "PC 11m · 4 armed" pill above it, and the Olympus "Home" button (44x44 at 328,738) next to the pill | three separate fixed layers | main + lead (oly-home is the shared shell) |
| N4 | nq/ hero | "LONDON ENTRIES · Next: New York morning 08:00 in 3 h 38 min" while the London window is open | the next-window line ignores the window that is open now | main |
