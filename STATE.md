# STATE (read first in every chat, update at the end; owner's words in quotes)

Updated 2026-11-17. Older detail and superseded lines: docs/STATE_HISTORY.md (full previous STATE.md verbatim, 2026-11-16 snapshot).
Owner wants SHORT replies ("be simple and to the point. You send too much info."): a few lines, one small table max.

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

## Next for Claude
- Update this file and keep "My Accounts" (business/accounts.html, plan in business/accounts.json) current on every account / plan change.
- Wire card links for new Business pages (taxes, security, schedule, work) in business/index.html; sw.js CACHE bump (lead); Data City still 3 red.
- Build the 25K LIT lane OFF (+LIT at $250) once today's balance is used; PC doctor. Judge Kalshi rewards paper after a few days (reward minus fill losses).
- Paper only for Claude: never arm live. After adding research/write-ups run `python tools/refresh_indexes.py`.

## Recent findings (don't redo)
- 2026-11-17 LIT walk-forward re-tuning (refit monthly/quarterly): REJECTED; 2022-25 +$511/mo vs $16 but noise (mostly 2025), 2026 -$11k/-$3k a half; 2023 loses at all 27 settings. `lit-walkforward-2026-11-17.md`
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
