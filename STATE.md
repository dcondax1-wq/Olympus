# STATE (read first in every chat, update at the end; owner's words in quotes)

Updated 2026-11-17. Older detail and superseded lines: docs/STATE_HISTORY.md (full previous STATE.md verbatim, 2026-11-16 snapshot).
Owner wants SHORT replies ("be simple and to the point. You send too much info."): a few lines, one small table max.
**Start every chat:** 1. `python tools/board.py read` (accounts, newest events, owner notes not answered, PC last report / STALE;
docs/BOARD.md). 2. Read this file. 3. Answer owner notes with `python tools/board.py note "..." --answers all`.
Updated 2026-11-16 ~04:00 ET (night teams A-E + W1 + W2 merged, shipped beaafb7; bot checks green: lit_live --quick OK, NT selftest OK, ATLAS 47/47).

## Live now
| What | State |
|---|---|
| Zlarior (LIT, MFFU Builder 50K eval) | $49,192.78 (2026-11-17): about $3,807 to pass, about $1,025 room (floor $48,168.20). Sizing two_week room_f 0.4 kept to session 80 ("yes 40%") |
| ATLAS (MFFU Builder 25K) | $26,946.10 = +$1,946 > $1,500 target: PASSED, awaiting MFFU's funded 25K account name (likely why an order said 'Limit 0'). Zombie-eval rule ON ("Fix atlas") |
| Rapid EOD 50K | Built (engine/rapid.py, docs/RAPID_EOD_SETUP.md), OFF until the owner pastes the account line; NOT bought yet. ONE only ("I'll stick with 1 rapid") |
| BLITZ | Hidden on every dashboard, silent ("Zlarior and ATLAS only for now"); runs on paper. Switch: dashboard_view.json hidden_bots |
| Kalshi | Paused ("Kalshi paused for now"). Rewards PAPER test running (tools/kalshi_rewards_paper.py, ledger research/kalshi_edge_K5/paper/rewards_paper.json): 9 rewarded markets, GET only, never an order; first read ~2.3 $/market-day |
| PC | Has NOT reported since 2026-11-07 (heartbeat branch, ntfy empty). Updates itself from backup dcondax1-wq/olympus branch pc when flat; evals only update Fri/Sat; restart window 17:00-18:00 ET |
| Phone dashboard | Netlify site moonlit-scone-08afe5 (private); updates itself once the owner pastes a Netlify key |
| Notifications | Built: $-first alerts (notify_settings.json) + cloud PC-SILENT check. Cloud monitor runs from `main`, not updated since Nov 7, so not live yet |

Rules: MFFU ONLY ("We stick with MFFU"). Limits: max 5 sim-funded, Builder 1x50K + 2x25K, Rapid EOD 3x50K, 10 evals; Zlarior 50K + ATLAS 25K funded together ALLOWED. Funded news ban (-2/+2 min Tier-1) on Rapid.
- night-bot 2026-11-17: ATLAS 25K PASSED ($26,946.10; Zlarior 50K $49,192.78). Funded 25K: LIT + ATLAS $250 = 1st payout 14/18 vs 18/26 sessions, $599/$529 vs $592/$497 a month, but no-payout-6m 7.5/12.2% vs 5.0/5.5%, 2021-25 a bit worse: owner yes/no; built OFF (engine/lit25.py, docs/LIT25_FUNDED.md; new funded Name: `python -X utf8 -m engine.lit25 --funded "<Name>" --start <day>`). PC silent: PC_DOCTOR.bat (docs/PC_DOCTOR.md); likely cause = report task OlympusPCReport never installed + auto-update never connected (BOTS_BACK's credential.interactive=never blocked the sign-in; fixed in autoupdate.fetch_interactive); heartbeat branch silent on purpose (GitHub suspended 11-08).
- MFFU rules re-checked 2026-11-17 (night-rules, research/writeups/mffu-rules-audit-2026-11-17.md): nothing voids money; fixed Rapid funded news window (-3/+2.5 min, Dec CPI/jobs added) + 7-day inactivity push on ATLAS/Rapid; copy trading on own accounts ALLOWED; Rapid EOD 50K now $275 list / $165 with CLUB (not ~$94); missing: 2% price-limit rule (stand aside on a 5% crash day).
- New accounts (night-acct 2026-11-17): ONE line per account, added NOT armed, MFFU limits checked (10 evals; funded 50K 1 / 25K 2 / Rapid 3, 5 in all): `python -X utf8 -m engine.accounts add --plan builder25k|builder50k|rapideod --name "<Name>"`, then START BOT + phrase (docs/NEW_ACCOUNT.md). 25K = LIT (ATLAS $250 once funded: saved yes, lane not wired yet); 50K = LIT; Rapid = LIT + ATLAS.
- Rapid EOD 50K READY, OFF (night-rapid): LIT + ATLAS on one account; owner pastes ONE line (docs/RAPID_EOD_SETUP.md) then START BOT + phrase. Jul-Oct live-code replay: pass median 20 sessions, 0 fails.
- Owner 2026-11-17: "be simple and to the point. You send too much info." Replies: a few lines, one small table max.
- Owner 2026-11-17: ONE Rapid EOD 50K only ("I'll stick with 1 rapid"): LIT + ATLAS $500 from day one, 30% best-day guard,
  funded keep $1,000 above the buffer. PC has not reported since 2026-11-07 (heartbeat branch, ntfy empty): fix first.
- ONE PAGE for accounts (2026-11-16, owner: "trading is getting very confusing"): Business -> My Accounts
  (tools/web_public/business/accounts.html). Plan in business/accounts.json: KEEP IT CURRENT on every account / plan change.
- Obsidian (optional, 1 min on the PC): python tools/obsidian_sync.py --setup "C:\path\to\your\vault" (docs/OBSIDIAN_SYNC.md).
- Yes/no (W1 2026-11-16): make the backtest use the same 1m bars as the live bot (branch night-w1-clean1m 94b955a)? Live orders
  unchanged; backtest Jan-Jun $33,901 -> $33,171 (PF 4.98 -> 4.85); Jul-Oct + 2021-25 identical; live == backtest 120/120. On yes:
  merge, refresh STRATEGY.md / research/lit/final_results.json headline numbers.
- To load tonight's fixes before Friday: when both bots are flat, STOP BOT then START BOT.
- Kalshi pause sentence in the kalshi-server chat (if not done).
- Yes/no: lock the PC bot page to his own devices (Tailscale only; anyone on home WiFi can reach Stop today).
- Yes/no: delete ~7 GB of old test leftovers in the container (python tools/disk_clean.py --apply; blocked for Claude by the safety check).
- MFFU ONLY ("We stick with MFFU", 2026-11-16). Help center limits: max 5 sim-funded (25K/50K sizes), Builder 1x50K + 2x25K,
  Rapid EOD 3x50K, 10 evals. So Zlarior 50K + ATLAS 25K funded together is ALLOWED (support question answered). Next buys:
  Rapid EOD 50K (code FIFTYOFF/CLUB at checkout, ~$94): +$660/mo each on Jul-Oct trades but its eval takes ~2 months (30% best-day
  rule, LIT ~0.8 winners/week), first payout ~14 sessions after funding, daily payouts, 90%, funded news ban (-2/+2 min Tier-1).
  Rapid (intraday floor) rejected: loses funded 16-22% in 6 months. Builder 25K #2: +$286/mo, cheap ($63/$43). Detail:
  research/writeups/lit-mffu-rapid-stack.md. Fleet presets exist (engine/multi_account mffu_rapid_eod_50k); Sim-test before arming.
- Taxes (2026-11-17, "study taxes"): Business -> Taxes page (tools/web_public/business/taxes.html; the lead adds its card to business/index.html).
  Rule: move 30% of every payout to a tax pot (Oikos + Ledger defaults now 30%, were 25%). Next federal estimated payment Jan 15, 2027. Education, not advice: research/writeups/taxes-2026-11-17.md.
- More work (2026-11-17, "find more work"): Business -> More Work page (tools/web_public/business/work.html; the lead adds its card to business/index.html).
  Ranked: 1 agency websites ($500-$2,000/mo by month 2-3), 2 Google profile fix $149 ($150-$600/mo), 3 small freelance jobs ($300-$1,000/mo by month 3-6); DoorDash = floor. First $1,000 plan: 15 contacts a weekday. research/writeups/more-work-2026-11-17.md.
- Business: fill agency/config.json (name, city, phone, address), then AGENCY_DAY.bat; list the 8 products, the 4 trading ones first (docs/BUSINESS_LISTING_KIT.md). $0 earned so far.
- Words wave 2 (2026-11-17 night-words2): plainer $-first words on Aegis, Chrysos, Oikos (tax stays 30%), Ledger, phone Money card, Kalshi (new PAUSED banner: no real bets, rewards test on paper), ATLAS page, Live View. Text only, no logic changed.
- Business pages (2026-11-17 night-pages): new Security tick list (business/security.html, never asks for a password) and Work week (business/schedule.html: PC checks 08:45 / 12:00 / 16:15 ET, Fri 16:30 review + payout check, tax dates, side-work blocks, one-tap phone calendar file); 4 doors on Business; plainer words on Business, My Accounts, Hestia, Planner, Zenith menu. Owner: do the Security list once (~1 hour).
- Plain words (2026-11-17 night-w-life): first line of 23 Money + Life apps now says what the app is for and what to tap, in $ (estimates labelled); Kalshi apps say "paused"; Tyche title tag fixed. Text only, ids kept.
- Money (2026-11-16 night B): the Business page is the ONE money place (every dollar, this week's money moves, payout planner, ready-to-upload tick lists, ideas, costs; docs/BUSINESS.md). New: 3 products (bundle $29, risk calculator $12, rules cheat sheet $7), 2 new models (AI training tasks, paid website tests). Plan (ESTIMATE): first payout ~late Dec ($1,200 LIT / $600 ATLAS to you), account #4 the day it is in the bank.

## Waiting on the owner (newest first)
1. PC has not reported since 2026-11-07: restart/check it (fix first; nothing new reaches the PC until it does).
2. Rapid EOD 50K: buy (code FIFTYOFF/CLUB, ~$94), paste ONE line (docs/RAPID_EOD_SETUP.md), START BOT + phrase. LIT + ATLAS $500 from day one, 30% best-day guard, funded keep $1,000 above the buffer. Jul-Oct replay: pass median 20 sessions, 0 fails.
3. Tell MFFU's funded 25K account name for ATLAS (passed).
4. Add GitHub secret LE_NTFY_TOPIC = ntfy alert topic (else alerts go to the public status topic); merge/update `main` so the cloud monitor runs the new checks.
5. Business: do the Security list once (~1 hour, business/security.html); fill agency/config.json then AGENCY_DAY.bat; list the 8 products (docs/BUSINESS_LISTING_KIT.md). $0 earned so far.
6. Yes/no (W1): backtest on same 1m bars as live (branch night-w1-clean1m 94b955a): Jan-Jun $33,901 -> $33,171 (PF 4.98 -> 4.85); Jul-Oct + 2021-25 identical; live == backtest 120/120. On yes: merge, refresh STRATEGY.md / research/lit/final_results.json.
7. Yes/no: lock the PC bot page to his devices (Tailscale only; anyone on home WiFi can reach Stop today).
8. Yes/no: delete ~7 GB old test leftovers (python tools/disk_clean.py --apply; blocked for Claude).
9. Optional: Obsidian sync, 1 min on the PC: python tools/obsidian_sync.py --setup "C:\path\to\your\vault" (docs/OBSIDIAN_SYNC.md).
10. To load fixes: when both bots are flat, STOP BOT then START BOT. Kalshi pause sentence in the kalshi-server chat (if not done).
11. Owner yes/no, older (details in history): Builder levers (fresh 50K / 2nd 25K), Rapid $1,000 keep, stack-on-one-account.
- Trading page (2026-11-17 night-trading, tools/web_public/trading/, wired 2026-11-17): today per account + 16:10 ET flat clock, Mon-Fri calendar of daily $, last 30 trades (-> Odeon replay), 2026 H1 vs H2 stats, 50%/30% payout rules check, hour/weekday bars, live vs twin, equity curve, "order rejected (Limit 0)" help; every number says LIVE / PAPER / BACKTEST + "Last live data: <date>". Data: python tools/trading_export.py (rerun after new trades; --check). Test: tests/run_area.py trading.
## Built, waiting for the PC
- Board (2026-11-17 night-board, "a communication board so you and the bot know what's happening"): one event log the bot (engine/board_events.emit, heartbeat "board", ntfy "brd", /site/board/), you (Board page note box / POST /inbox/board) and Claude (tools/board.py read / note) all share; new Board app (tools/web_public/board/, lead wires it). ATLAS pass + lock recorded.
- Phone alerts v2 (2026-11-17 night-notify): $-first trade / milestone / room-low / 16:15 summary pushes, one settings file notify_settings.json; cloud PC-SILENT check every monitor run (20 min, 1 push + 1 reminder after 2 h). Owner: add GitHub secret LE_NTFY_TOPIC = your ntfy alert topic (else it posts to the public status topic).
- Plain words, MARKET apps (2026-11-17 night-w-market): every Market app's first line now says what it is for and what to do, in $ (Archive, Ares, Chronos, Cities, Colosseum, Compass, Delphi, Ergasterion, Forum, Helios, Kairos, Kronos, NQ, Odeon, Oracle, Pantheon, Pheme, Pinakes, Pythia); NQ no longer says "three bots" / BLITZ.
- Obsidian living sync (tools/obsidian_sync.py, docs/OBSIDIAN_SYNC.md): the PC report writes <vault>/OLYMPUS/Sync every 15 min (bots' day, trades + pictures,
  nightly learning, business checklist, STATE). Needs ONE line on the PC: python tools/obsidian_sync.py --setup "<vault folder>".
- Jarvis: Classic Jarvis look back (violet HUD, opt-in: ⋯ → Look → Jarvis look, or say "classic Jarvis"); AGORA stays default. Jarvis, the Gate
  and the hubs now all take the PC's ntfy report when newer (same drawdown / today's $ / age as NQ, Aegis, Zenith). Gate leads with Bots + Money.
- Nightly self-learning loop is built (engine/learn_loop.py, research/learn_queue.json, docs/LEARN_LOOP.md): starts on the PC by itself after tonight; first cloud run rejected all 8 seed ideas.

## Next for Claude
- Update this file and keep "My Accounts" (business/accounts.html, plan in business/accounts.json) current on every account / plan change.
- Wire card links for new Business pages (taxes, security, schedule, work) in business/index.html; sw.js CACHE bump (lead); Data City still 3 red.
- Build the 25K LIT lane OFF (+LIT at $250) once today's balance is used; PC doctor. Judge Kalshi rewards paper after a few days (reward minus fill losses).
- Paper only for Claude: never arm live. After adding research/write-ups run `python tools/refresh_indexes.py`.

## Recent findings (don't redo)
- 2026-11-17 LIT walk-forward re-tuning (refit monthly/quarterly): REJECTED; 2022-25 +$511/mo vs $16 but noise (mostly 2025), 2026 -$11k/-$3k a half; 2023 loses at all 27 settings. `lit-walkforward-2026-11-17.md`
- 2026-11-17 LIT regime sizing (gamma / VIX / VXN-VIX / VIX term / prior range, 124 cells): REJECTED, flat size stays. `lit-regime-sizing-2026-11-17.md`
- 2026-11-17 LIT smart entries: 31 rules, NONE better in both halves; today's entry stays. `research/writeups/lit-smart-entries-2026-11-17.md`
- 2026-11-17 Famous public strategies: 22 cells, none holds; LIT the only strategy. `public-strategies-2026-11-17.md`
- 2026-11-17 Rule-native layer: no change (only Rapid + BLITZ $300 3/day passes, post hoc, paper lead). `rule-native-2026-11-17.md`
- 2026-11-17 Drift switch: REJECTED.
- 2026-11-17 Kalshi K5: no taker edge; rewards makers +3% to +7% per $1 (paper test running). `kalshi-edge-K5-2026-11-17.md`
- 2026-11-17 Kalshi K4: NO EDGE (Polymarket copy, sports, longshots). `kalshi-edge-K4-2026-11-17.md`
- 2026-11-17 Taxes: move 30% of every payout to a tax pot; next federal estimate Jan 15, 2027. `taxes-2026-11-17.md`
- 2026-11-17 More work: agency websites, Google profile fix $149, freelance; first $1,000 plan. `more-work-2026-11-17.md`
- 2026-11-16 Rapid EOD levers: keep $1,000 in funded Rapid = $6,014 / $2,824 a month (H1/H2). `rapid-levers-2026-11-16.md`
- 2026-11-16 Builder levers / stack on one account / MFFU stack: `builder-levers-2026-11-16.md`, `stack-one-account-2026-11-16.md`, `lit-mffu-rapid-stack.md`
(All in research/writeups/. Older findings in docs/STATE_HISTORY.md: LIT no new edge, ATLAS only zombie rule, Safety S1 merged.)
- 2026-11-17 edge health (`edge-health-2026-11-17.md`, `tools/edge_health.py` -> research/lab/edge_health.json, Business card data `edge`): light GREEN (LIT last 40 sessions to Nov 6: 2.3R/wk, PF 3.84, ~$3,440/mo vs 2026 H1 PF 3.91) but fading (Oct 19-Nov 6: 3-4 trades, ~-1.5R); Jul-Oct false alarm (RED) 8.6%; no market feature works as a warning (overnight share only marks the calendar). Data: TradingView to Oct 16, PC bars to Nov 6, 6 sessions missing: owner exports NQ1! 1m from Oct 16. Card for the lead: business.json `edge.line`.
- 2026-11-17 smart entries (`lit-smart-entries-2026-11-17.md`, `tools/lit_smart_entries.py`): 31 new entry rules on the same LIT setups (conditional pullback limits, 1m CISD + BOS / strong close / reclaim combos, wait 5-15 min for proof, half now + half at minute 15): NONE better in both halves (pullback limits cut Jul-Oct to $225-1,236/mo of $2,670; staged halves 2-week pass 44.5 -> 15%). Today's entry stays; nothing changed.
- 2026-11-17 night-ui: Prometheus arena framed between the top bar and the dock + shorter money banner (live flame tappable, Verdict opens); Settings in Jarvis: title, Inside Jarvis card, then "On this page"; Daphne banner shows "Holds up X% of the time on new data" again. Data City still 3 red (clear-night 706k tris > 700k, phone far view 68 calls vs < 60 needs a real draw-call merge, LITE towers check order-dependent). sw.js CACHE bumped to v109 by bump_versions.
- 2026-11-17 night-reds: old test reds fixed at the cause: stale data rebuilt with each app's own builder (Archive, Ergasterion, Pinakes, Herald, Ares rules = room_f 0.4, Athena, Prometheus forge, Colosseum card); test sites now carry assets/ (ui.ogg 404s); the public PC status feed is the one allowed outside address in AK.page; home seal no longer shrinks under 44 px; Arena SVG without innerHTML; Nemesis view strip lets taps through. Still red: Daphne verdict hides its hold-rate line (design call), Prometheus money banner covers the live flame. Needs sw.js CACHE bump (lead).
- 2026-11-17 night-w-cmd: plainer first screens (one line: what it is for + what to do, $ and ESTIMATE labels) on Argo, Argus, Bridge, Inbox, Kratos, Settings, Stoa, Clio, Daphne, Data City, Fates, Hephaestus, Moirai, Nemesis, Observatory, Prometheus and the Jarvis hub. Words only; ids/classes/data keys unchanged.
- 2026-11-17 famous public strategies (`public-strategies-2026-11-17.md`, `tools/pub_strats.py`): Gao, pre-FOMC, turn of month, overnight drift, Connors RSI(2), trend following 12m / 20-60d, Crabel NR7: 22 cells, NONE holds in 2021-25 + both 2026 halves; best-looking ones need overnight holds (MFFU forbids) and lost in H2. LIT stays the only strategy.
- 2026-11-17 Kalshi K5 (`kalshi-edge-K5-2026-11-17.md`): slow 'public number' markets (gas, TSA week, YouTube views, Truth Social, App/Spotify #1): no taker edge worth money; gas nowcast -45%, Spotify persistence -24%. One weak paper rule (late favourite when the answer is public, +4.4%/$1 test but -1.3% train, ~$3/mo) in `research/lab/kalshi_live_candidate.json`, nothing armed. Rewards program (ends Jan 1 2027, ~$106k/day): RT / Panama / Babel-el-Mandeb makers net +3% to +7% per $1 filled incl. pool; est. +$150-470/mo on 3 markets but needs real resting orders (owner's call, Kalshi still paused).
- 2026-11-17 Kalshi K4 (`kalshi-edge-K4-2026-11-17.md`): NO EDGE. Copying Polymarket on 15-min crypto loses ~7-9%/$1 (a +18-32% version was lookahead, caught by a live check); sports favourites +1.8% test, range incl. 0; longshots -43%; 854 crypto coin x hour slices = luck. Kalshi stays paused, no paper rule.
- 2026-11-17: drift switch REJECTED; rule-native layer: no change (BLITZ 3/day on Rapid = paper lead only).
- Rule-native search (2026-11-17, `rule-native-2026-11-17.md`, `tools/money/rule_native.py`): 36 variants scored on days to 1st payout +
  P(no payout 6m). LIT 2nd target / ATLAS 1R / high-win scalp / add-on profit lock: no faster in both halves (cut $). Only pass: Rapid +
  BLITZ $300 max 3/day (50/62 -> 42/57 days, +$822/+$313/mo) but cap post hoc, 2021-25 2-wk eval fails 2.9 -> 6.0%: paper lead only.
- Rapid EOD levers (2026-11-16, `rapid-levers-2026-11-16.md`, `tools/money/rapid_levers.py`): keep $1,000 in the funded Rapid
  (take only above $3,100) = $6,014 / $2,824 vs $5,022 / $2,301 a month (H1/H2), first payout 2-4 sessions later: candidate,
  owner yes/no. Different mixes per account: less $ (2x: -$500/mo H2) but "no account pays in 6m" 7.6% -> 1.4-1.6% (owner
  choice). Asia slot $300: small 2026 plus, worse 2021-25, not built. Give-up/re-buy and day caps: no (keep the 30% guard).
- Builder levers (2026-11-16, `builder-levers-2026-11-16.md`, `tools/money/builder_levers.py --z-room --z-togo --a-room --a-togo`):
  a FRESH Builder 50K now next to Zlarior's hole (both trade, first pass kept) = first payout 53/50 -> 46.5/44 sessions
  (~Feb 1 -> ~Jan 20), +$38/+$45 a month after the $91.80; pays whenever room < ~$1,200. ATLAS + fresh 25K ($43): 35/56 -> 31/47.
  With ATLAS $500 on the funded 50K too: ~Jan 4. Rescue sizes (bigger/smaller) rejected (18-30% 2-week fails / slower).
  2nd Builder 25K: LIT eval then + ATLAS $250 funded = $553/$456 vs LIT copy $346/$298, 1st payout 33/34 vs 45/44.
  Payout ask $500/$1,000/$2,000/cycle-timed and a best-day day stop: no gain in both halves (keep ask $1,500). Owner yes/no.
- Stack on ONE account (2026-11-16, `stack-one-account-2026-11-16.md`, `tools/money/stack_one_account.py`): Builder 50K, LIT eval then
  LIT + ATLAS $500 once funded: first payout 26/23.5 -> 17/15 sessions, account $779/$753 -> $1,202/$1,205 a month (H1/H2), 2021-25 ~$0.
  ATLAS in the eval too: faster pass but more 2-week fails (2021-25 20% vs 0.6%) = rejected. Rapid EOD + ATLAS: eval 40 -> 22 sessions
  (still ~1 month). Owner yes/no needed; nothing built live.
- Why the first payout is ~2 months (2026-11-16, owner asked): the planner's MFFU rules match the help center ($2,100 buffer +
  $500 min, 50% best day, 2 days). Time = eval still $3,687 to go (Nov 7 numbers, stale) ~3 weeks + funded needs $2,600 above
  start = ~24 sessions (12-16 trade days; LIT 2.46 trades/week). Funded sizing sweep (60/80% room, $1,500/$2,000 max, win caps
  $1,300-$2,600): first payout 22-36 sessions, no faster; holds (consistency/line) ~0. Only real speed-up: start the next
  account NOW instead of from the payout (FundedNext Rapid Daily: daily payouts, ~17 sessions after funding; needs FN's written OK).
- LIT: no new edge (S2 sizing tilts, E-LIT 16 skip rules + missed setups). H2 weaker = lower VIX + wider stops, not a broken edge.
- ATLAS: only the zombie-eval rule helped (+$60/month); filters/trend/overlap rejected.
- Safety S1: missing-stop close, save-before-send, no duplicate bracket after crash, 8 entries/day cap (all merged).

## Known reds / environment notes
- Data City 3 red (706k tris > 700k, phone far view 68 calls vs < 60, LITE towers order-dependent); Daphne verdict hides hold-rate line (design call); Prometheus money banner covers live flame.
- test_lit_oif 117/120: research 1m cleaner drops real windows on 2026-03-23 / 05-05 (needs a strategy check). Old reds: cities_page 6, oracle_page dead-export, planner .oly-home 36 px, test_jarvis_hub 260/262.
- Netlify phone site ships AGORA Planner without a worker (blank offline inside Jarvis); GitHub Pages fine.
- Last bot checks green (2026-11-16): lit_live --quick OK, NT selftest OK, ATLAS 47/47.
- Work cheaply: python tests/smoke.py -> touched area -> python tools/ship.py; at most 2-3 helpers.

## Pointers
- Money: Business page (docs/BUSINESS.md), payout plan research/lab/payout_plan.json; fleet `--plan mffu_builder_50k` (engine/multi_account).
- Accounts: tools/web_public/business/accounts.html; new pages taxes/security/schedule/work in tools/web_public/business/.
- Learn loop: engine/learn_loop.py, docs/LEARN_LOOP.md. Obsidian: tools/obsidian_sync.py. Writeups: research/writeups/.
- Full previous STATE.md (prop money plan, all older findings and waves): docs/STATE_HISTORY.md.
