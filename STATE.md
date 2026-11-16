# STATE (read first in every chat, update at the end; owner's words in quotes)

Updated 2026-11-15 ~16:30 ET (money lines 2026-11-16 night B).

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
- Account #4: buy after the first MFFU payout (docs/ACCOUNT_4.md; another MFFU 50K = easiest, LucidPro 50K = second firm).
- Business: fill agency/config.json (name, city, phone, address), then AGENCY_DAY.bat; list the 8 products, the 4 trading ones first (docs/BUSINESS_LISTING_KIT.md). $0 earned so far.
- Money (2026-11-16 night B): the Business page is the ONE money place (every dollar, this week's money moves, payout planner, ready-to-upload tick lists, ideas, costs; docs/BUSINESS.md). New: 3 products (bundle $29, risk calculator $12, rules cheat sheet $7), 2 new models (AI training tasks, paid website tests). Plan (ESTIMATE): first payout ~late Dec ($1,200 LIT / $600 ATLAS to you), account #4 the day it is in the bank.

## Built, waiting for the PC
- Nightly self-learning loop is built (engine/learn_loop.py, research/learn_queue.json, docs/LEARN_LOOP.md): starts on the PC by itself after tonight; first cloud run rejected all 8 seed ideas.

## Recent findings (don't redo)
- LIT: no new edge (S2 sizing tilts, E-LIT 16 skip rules + missed setups). H2 weaker = lower VIX + wider stops, not a broken edge.
- ATLAS: only the zombie-eval rule helped (+$60/month); filters/trend/overlap rejected.
- Safety S1: missing-stop close, save-before-send, no duplicate bracket after crash, 8 entries/day cap (all merged).

## How to work cheaply
python tests/smoke.py (2 min) -> touched area's tests -> python tools/ship.py. At most 2-3 helpers. No new apps unless they make money.
