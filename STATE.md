# STATE (read first in every chat, update at the end; owner's words in quotes)

Updated 2026-11-16 night (team E: prop money plan).

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
- Tonight 19:00 ET: newest zip in Downloads -> SETUP_EVERYTHING.bat -> GitHub sign-in, Netlify key, YES + live phrase.
- Kalshi pause sentence in the kalshi-server chat (if not done).
- Yes/no: lock the PC bot page to his own devices (Tailscale only; anyone on home WiFi can reach Stop today).
- Yes/no: delete ~7 GB of old test leftovers in the container (python tools/disk_clean.py --apply; blocked for Claude by the safety check).
- Next account: a LucidPro 50K copy of Zlarior, bought from the first payout (docs/ACCOUNT_4.md). NOT a second MFFU 50K:
  MFFU funds only one Builder 50K a person (help center, re-read 2026-11-16). Then one more Lucid copy per payout (plan below).
- Ask MFFU support once (one line, in writing): "Builder page says one active Builder account per user: can I hold a funded
  Builder 50K and a funded Builder 25K at once?" (Zlarior + ATLAS both funded depends on it).
- Business: fill agency/config.json (name, city, phone, address), then AGENCY_DAY.bat; list the 5 products (docs/BUSINESS_LISTING_KIT.md). $0 earned so far.

## Built, waiting for the PC
- Nightly self-learning loop is built (engine/learn_loop.py, research/learn_queue.json, docs/LEARN_LOOP.md): starts on the PC by itself after tonight; first cloud run rejected all 8 seed ideas.

## Prop money plan (team E, 2026-11-16; research/lab/payout_plan.json, Business page card)
- H2 replay, $ to the owner after fees: 2 accounts $1,050/mo year 1 ($1,200 months 7-12), 3 $1,630 ($2,130), 4 $2,100
  ($2,980), 6 $2,780 ($4,290). Worst month = fees only (-$227 to -$446). About 4 months in 10 still pay $0 even at 6
  accounts (one signal, correlation ~0.94). 2021-25 (no edge): about $0. Zlarior: pass about Dec 8, first payout about
  Jan 29 ($1,600 to him), #3 about Feb 3, #4 Mar 24, #5 Apr 29, #6 May 21.
- Fleet: `--plan mffu_builder_50k` copy is one command and Sim-tested (tests.test_fleet_mffu); the guards count Zlarior's /
  ATLAS's own funded accounts against MFFU's limits; `--held <plan>=0` when one ended. MFFU copy trading: allowed (help center).

## Recent findings (don't redo)
- LIT: no new edge (S2 sizing tilts, E-LIT 16 skip rules + missed setups). H2 weaker = lower VIX + wider stops, not a broken edge.
- ATLAS: only the zombie-eval rule helped (+$60/month); filters/trend/overlap rejected.
- Safety S1: missing-stop close, save-before-send, no duplicate bracket after crash, 8 entries/day cap (all merged).

## How to work cheaply
python tests/smoke.py (2 min) -> touched area's tests -> python tools/ship.py. At most 2-3 helpers. No new apps unless they make money.
