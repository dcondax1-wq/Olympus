# STATE (read first in every chat, update at the end; owner's words in quotes)

Updated 2026-11-16 ~04:00 ET (night teams A-E + W1 + W2 merged, shipped beaafb7; bot checks green: lit_live --quick OK, NT selftest OK, ATLAS 47/47).

## Live
| What | State |
|---|---|
| Zlarior (LIT, MFFU Builder 50K eval) | Arming tonight 19:00 ET by the owner (SETUP_EVERYTHING.bat). Sizing two_week room_f 0.4 kept to session 80 ("yes 40%"). Last known drawdown left $1,145 of $2,000 |
| ATLAS (MFFU 25K eval) | Arming tonight with Zlarior. Zombie-eval rule ON ("Fix atlas"): give up under $200 room, 1-micro last shot. Last known $822 of $1,000 left |
| BLITZ | Hidden on every dashboard and silent ("Zlarior and ATLAS only for now"); still runs on paper. Switch: dashboard_view.json hidden_bots |
| Kalshi | Paused ("Kalshi paused for now"): no edge found |
| PC updates | Backup repo dcondax1-wq/olympus branch pc; the PC joins at tonight's setup (sign in as dcondax1-wq), then updates itself when flat; evals only update Fri/Sat |
| Phone dashboard | Netlify site moonlit-scone-08afe5 (private). Updates itself once the owner pastes a Netlify key at tonight's setup |

## Waiting on the owner
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
- Business: fill agency/config.json (name, city, phone, address), then AGENCY_DAY.bat; list the 8 products, the 4 trading ones first (docs/BUSINESS_LISTING_KIT.md). $0 earned so far.
- Money (2026-11-16 night B): the Business page is the ONE money place (every dollar, this week's money moves, payout planner, ready-to-upload tick lists, ideas, costs; docs/BUSINESS.md). New: 3 products (bundle $29, risk calculator $12, rules cheat sheet $7), 2 new models (AI training tasks, paid website tests). Plan (ESTIMATE): first payout ~late Dec ($1,200 LIT / $600 ATLAS to you), account #4 the day it is in the bank.

## Built, waiting for the PC
- Obsidian living sync (tools/obsidian_sync.py, docs/OBSIDIAN_SYNC.md): the PC report writes <vault>/OLYMPUS/Sync every 15 min (bots' day, trades + pictures,
  nightly learning, business checklist, STATE). Needs ONE line on the PC: python tools/obsidian_sync.py --setup "<vault folder>".
- Jarvis: Classic Jarvis look back (violet HUD, opt-in: ⋯ → Look → Jarvis look, or say "classic Jarvis"); AGORA stays default. Jarvis, the Gate
  and the hubs now all take the PC's ntfy report when newer (same drawdown / today's $ / age as NQ, Aegis, Zenith). Gate leads with Bots + Money.
- Nightly self-learning loop is built (engine/learn_loop.py, research/learn_queue.json, docs/LEARN_LOOP.md): starts on the PC by itself after tonight; first cloud run rejected all 8 seed ideas.

## Prop money plan (team E, 2026-11-16; research/lab/payout_plan.json, Business page card)
- H2 replay, $ to the owner after fees: 2 accounts $1,050/mo year 1 ($1,200 months 7-12), 3 $1,630 ($2,130), 4 $2,100
  ($2,980), 6 $2,780 ($4,290). Worst month = fees only (-$227 to -$446). About 4 months in 10 still pay $0 even at 6
  accounts (one signal, correlation ~0.94). 2021-25 (no edge): about $0. Zlarior: pass about Dec 8, first payout about
  Jan 29 ($1,600 to him), #3 about Feb 3, #4 Mar 24, #5 Apr 29, #6 May 21.
- Fleet: `--plan mffu_builder_50k` copy is one command and Sim-tested (tests.test_fleet_mffu); the guards count Zlarior's /
  ATLAS's own funded accounts against MFFU's limits; `--held <plan>=0` when one ended. MFFU copy trading: allowed (help center).

## Recent findings (don't redo)
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

- Test gate (night team D, 2026-11-16, branch night-d): `run_gate.py --fast` now also runs the engine / PC core first (dst, pcdash,
  account_c, fleet, lit_live --quick, rehearsal --quick ...). All old reds fixed except two that need others: jarvis/sw.js SHELL is
  missing 6 files + 3 version bumps (lead's file), and test_lit_oif 117/120 = a real finding (the research 1m cleaner drops genuine
  windows on 2026-03-23 / 05-05 that the live feed sees: live would enter differently there; changing it changes the backtest, so
  it needs a proper strategy check). After adding research runs / write-ups: `python tools/refresh_indexes.py`.

- Night W2 (2026-11-16): phone e2e 268/268, olympus_kit perf budgets green (phone Oracle city sparser), Jarvis worker v45,
  test_jarvis_apps 95/95. Still red, old: cities_page 6, datacity phone overview 67 vs 60 calls, oracle_page dead-export check
  vs ?v= imports, planner .oly-home 36 px, test_jarvis_hub 260/262 (intro timing, same on 321db96). Netlify phone site ships
  the AGORA Planner without a worker (blank offline inside Jarvis; GitHub Pages site fine) - not fixed.

## How to work cheaply
python tests/smoke.py (2 min) -> touched area's tests -> python tools/ship.py. At most 2-3 helpers. No new apps unless they make money.
- 2026-11-17 KALSHI REWARDS PAPER running (owner: "try kalshi rewards in paper"): tools/kalshi_rewards_paper.py, ledger research/kalshi_edge_K5/paper/rewards_paper.json; 9 rewarded markets (RT/Panama/Babel), virtual bids both sides at the reward reference, conservative back-of-queue fills. GET only, never an order. Runs in the cloud container (2h chunks); first read ~2.3 $/market-day. Judge after a few days: reward minus fill losses.
