# Kalshi bot: the risk guard on the server

Your Kalshi bot runs on its own server (the Oracle VM). This update puts a **risk guard** in front of every order it
sends: your limits, a kill switch, paper / dry run / live, and phone alerts. It starts on **paper** (no real orders).
Real money only starts when **you** type the live phrase.

| what | result |
|---|---|
| Limits on every order | $5 per order, $10 per market, $25 a day, stop at -$10 a day, $25 open in total, 40 orders a day |
| Never pays too much | price must be under the bot's fair value, with at least 1 cent of edge after Kalshi's fee |
| Not in the last minute | no new buys in the last 60 seconds before a market closes (unless you allow a strategy) |
| Kill switch | one command stops every order and turns live off |
| Paper / dry run / live | paper by default; dry run logs the exact orders it would send; live needs your typed phrase |
| Phone alerts | fills, losses, kill switch, daily stop hit, live on / off, any order that skipped the guard |
| Kalshi page | a "Risk guard" card: the mode, today's room, what it blocked |
| Tests | 116 guard checks, 32 PC-to-server checks, 113 feed checks, 12 page checks: all pass |

## Your 3 steps
1. On the PC, open a terminal in the `nq-liquidity-engine` folder and paste:
   `python tools/kalshi_kit/send_to_vm.py`
   It copies the guard to the server, keeps the bot on paper, turns on Kalshi alerts on your phone, and prints one sentence.
2. Paste that sentence into the **kalshi-server** chat. It connects every order to the guard and shows you the change;
   reply OK to restart the bot. Still paper.
3. When you want real money, type `python tools/kalshi_kit/send_to_vm.py --live` in the same terminal, then type the
   phrase it shows (`GO LIVE <today's date> STOP <your daily stop>`).

## Your limits
Change any of them from the PC, for example:
`python tools/kalshi_kit/send_to_vm.py --limits max_order_usd=5 daily_stop_usd=10`

| name | default | what it means |
|---|---|---|
| `max_order_usd` | 5 | most one order may cost, fee included |
| `max_order_pct_balance` | 0.10 | ... and at most this share of the balance |
| `max_market_usd` | 10 | most money in one market |
| `max_day_usd` | 25 | most money spent on buys in one day (ET) |
| `daily_stop_usd` | 10 | after losing this much in a day, no new buys until tomorrow |
| `max_open_usd` | 25 | most money open across all markets |
| `max_orders_day` | 40 | most orders in one day |
| `no_trade_last_s` | 60 | no new buys this many seconds before a market closes |
| `late_ok_strategies` | none | strategies allowed in that last minute, e.g. `late_ok_strategies=latefav` |
| `min_edge_cents` | 1 | edge needed after Kalshi's fee, in cents per contract |
| `max_over_fair_cents` | 0 | never pay more than the bot's fair value plus this |
| `require_fair` | true | block orders that come without the bot's fair value |

Changing a limit turns live off: type the phrase again (step 3). Lowering limits never needs the phrase.

## The switches (from the PC)
- `--kill`: stops every order now and turns live off. `--unkill` lifts it; the bot stays on paper.
- `--paper` or `--dry-run`: no real orders. Dry run logs the exact orders the bot would send.
- `--status`: the guard's card (mode, limits, today's room).
- On the server itself (kalshi-server chat): `python3 ~/kalshi_jarvis/kalshi_guard.py status`. The chat may use the
  kill switch if something looks wrong; it never turns live on.

## Honest limits
- **The guard only protects the orders the bot sends through it.** Step 2 is what connects them. Until then the page
  says "the bot has not asked it about an order yet". If a real order ever skips the guard, you get an urgent alert.
- **Strategies with no fair value are blocked** (`require_fair`). The kalshi-server chat tells you which ones; only you
  decide whether to set `require_fair=false` for them. The guard checks the price; it does not make the bot profitable
  (see `docs/KALSHI_STOP_LIST.md`).
- **The phrase stops accidents, not a determined program on the server.** Anything on the server could edit the guard's
  files. The chat's rules forbid it, and every switch shows on the page and as a phone alert.
- **Fees:** counted as 0.07 × price × (1 − price) per contract, rounded up to the cent. That is a little more than Kalshi
  charges on bigger orders, so the guard is on the safe side.
- **Step 1 needs the PC's server helper** (`srv.py`, the one the Kalshi feed already uses). If it says srv.py was not
  found, tell Claude in our lead chat.
- The Kalshi page shows the Risk guard card after the next site publish.

Files: `tools/kalshi_kit/public/kalshi_guard.py` (the guard), `GUARD_SETUP.md` (for the kalshi-server chat),
`kalshi_status_vm.py` (the status feed, now with the guard's block), `tools/kalshi_kit/send_to_vm.py` (the PC side),
`tools/kalshi_pc_link.py` (the PC reads the status). Tests: `tests.test_kalshi_guard`, `tests.test_kalshi_vm_update`,
`tests.test_kalshi_publish`, `tests.test_kalshi_page --only=risk`.
