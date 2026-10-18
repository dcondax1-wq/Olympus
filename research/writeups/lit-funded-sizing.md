---
title: LIT funded sizing - how big to trade once the MFFU eval is passed
family: risk
date: 2026-10-18
status: adopt-candidate
summary: After the MFFU Builder 50K eval passes, the goal changes from speed to payouts without losing the account. The exact live LIT trades of 2026 were replayed on a modelled MFFU funded account (EOD trailing $2,000 locking at +$100, $1,000 soft daily loss, payouts above a $2,100 buffer, $500-$2,000 a request, best day at most 50% of the cycle, 5 sim payouts, 80% split). Keeping today's normal or eval size on a funded account loses 20% (Jan-Jun) / 27% (Jul-Oct) of accounts within 6 months. The new mode "funded" risks 40% of the room to the floor (at most $800, so a fresh account trades the normal LIT size), sizes so a winner pays at most $1,500 (the 50% best-day payout rule), keeps the weekly stop, and skips a trade when even 1 micro could reach the floor. It loses 1.2% / 2.2% of accounts in 6 months and pays $4,660 / $4,479 in 6 months ($777 / $746 a month) vs $3,459 / $3,080 for normal size. The best-day cap is the lever that matters; fixed $ tiers, fractional Kelly and % of the room all sit on the same plateau once it is on. Paper only; live_model.json is unchanged.
runs: lit_funded_rec, lit_funded_normal, lit_funded_tiers
---

## In one minute

- **The question:** once the eval is passed, how big should LIT trade on the funded account so the owner takes out the most
  money and does not lose the account?
- **The trades are the real LIT trades:** the 120 trades of 2026 the live loop takes (same signals, 1m entries, stops 1 tick
  beyond the sweep extreme). Only the size changes.
- **The answer (mode `funded`, recommended):**
  1. Risk **40% of the room** to the max-loss floor, never more than **$800** (so a fresh funded account with $2,000 room
     trades the normal LIT size, and size shrinks as the room shrinks).
  2. **Wide stop means less risk:** $ risk up to a 20-pt stop, then x 20 / stop (the LIT rule).
  3. **Best-day cap:** micros so the trade's target pays at most **$1,500**. MFFU pays out only when no single day is more than
     50% of the cycle's profit; LIT's big winners otherwise lock the payout until the account earns that day again.
  4. **Weekly stop on** (half size after 2 stop-outs in a week).
  5. **Never risk the account on 1 micro:** if even 1 micro's stop-out (stop + 2 ticks + commission) would reach the floor,
     no trade.
- **Results (Monte Carlo, 1,000 funded accounts of 6 months each, H1 = Jan-Jun picked / H2 = Jul-Oct check):**

  | Funded sizing | Account lost 3 mo / 6 mo | Paid to you 3 mo / 6 mo | $ a month | Median first payout | 5 payouts within 6 mo | Max DD (median) |
  |---|---|---|---|---|---|---|
  | Today's normal size ($800 up to 20 pts) | 19.3 / 19.7% · 25.1 / 27.2% | $1,653 / $3,459 · $1,492 / $3,080 | $576 · $513 | session 31 · 29 | 5.4% · 4.4% | −$2,113 |
  | Today's eval mode ($800 up to 25 pts, 60% room) | 20.6 / 22.0% · 25.8 / 28.0% | $1,595 / $3,369 · $1,647 / $3,292 | $562 · $549 | 31 · 27 | 5.1% · 5.5% | −$2,627 |
  | Normal size + 60% room cap + floor guard | 3.3 / 4.4% · 2.8 / 4.4% | $1,701 / $3,649 · $1,516 / $3,246 | $608 · $541 | 33 · 30 | 5.3% · 4.3% | −$2,174 |
  | Tiers ($400 under $2,000 room, $800 above) + $1,500 best-day cap | 0.9 / 1.6% · 1.2 / 3.0% | $1,932 / $4,623 · $1,523 / $3,953 | $771 · $659 | 29 · 34 | 23.1% · 16.9% | −$1,404 |
  | **Recommended: 40% of the room (max $800) + $1,500 best-day cap** | **0.7 / 1.2% · 0.9 / 2.2%** | **$2,031 / $4,660 · $1,933 / $4,479** | **$777 · $746** | **27 · 26** | **24.9% · 24.1%** | **−$1,480** |

  - "Paid to you" is the 80% share, within the 3 or 6 months. The cap is 5 sim payouts x $2,000 x 80% = $8,000, then MFFU moves
    the account to live (not modelled: the path stops there as "graduated").
  - 3 months: 87% / 82% of accounts have had a payout; 6 months 97% / 94%. The worst 10% of accounts paid $1,599 / $813 in 6
    months.
  - Max risk on one trade in the recommended mode: about $340-410 (the best-day cap keeps size small on far targets).

- **What does not matter much:** once the best-day cap is on, fixed $ tiers, tiers by the floor's lock, % of the room
  (0.15-0.6) and a $800-1,200 maximum all land on a plateau of $4,300-4,850 in 6 months with 0.3-4% accounts lost. The
  difference between them is noise (1,000 paths, overlapping 2026 blocks). The recommended one is picked because it has the
  lowest loss rate near the top of H1 and it is the easiest to explain.
- **Kelly:** full Kelly on the 2026 LIT trades is 22% (H1) / 20% (H2) of the bankroll per trade, with the room as the
  bankroll. 40% of the room is about 2x Kelly, but Kelly is not the right yardstick here: the payouts are capped ($2,000 a
  request, 5 requests) and every payout resets the room to $2,000, so growth past the cap is worthless and a smaller size
  only slows the payouts. Half Kelly (10%) paid $3,588 in H1 with 0.1% lost.
- **Holding back more than the buffer** (asking for $1,000 less each time) lowers the payouts by $200-300 in 6 months and
  barely moves the loss rate (it is already 1-2%): not worth it.
- **2021-25 (reference only, 5m entries, LIT PF 1.01 there):** no sizing makes LIT pay there; normal size loses 22 of 23
  back-to-back funded accounts, the recommended mode loses far fewer because it shrinks with the room (numbers in the run).
- **Nothing live changed.** To switch it on after a pass: see "The config" below.

## How it was measured

- **Account rules modelled (MFFU Builder 50K funded / sim-funded; MFFU help-center summaries via search 2026-10-18, partly
  unconfirmed, see `lit-prop-firms.md`):**
  - Max loss $2,000 trailing the end-of-day high, locks at start + $100 ($50,100). Checked against the worst open loss inside
    the day.
  - $1,000 soft daily loss: the position is flattened, the day ends.
  - Payout request at a session's end when: balance − $2,100 buffer >= $500; at most $2,000 a request; at least 2 traded days
    in the cycle; best day <= 50% of the cycle's profit; first after 2 sessions; 5 sim payouts. 80% to the trader. A payout
    lowers the balance, never the floor (so after a payout the room is back to $2,000).
  - $1.40 a micro, 1 tick of slippage on market entries and stop exits, max 40 micros.
- **Samples:** 1,000 Monte Carlo accounts of 126 sessions (6 months; 63 = 3 months) in 5-session blocks from the half; the
  same paths for every config. Back to back on real history (a new account the session after one is lost or reaches 5
  payouts) is in each run's verdict; real H1 / H2 is only one account long, so it is a sanity check, not a score.
- **Pick on H1, check on H2.** The recommended config is in the top group of H1 and holds in H2 (loss 2.2%, $4,479).
- Code: `tools/lit_funded.py` (grid, `research/lit/funded.json`), stage 2 / 3 grids `research/lit/funded_stage2.json`,
  `funded_stage3.json`. Sizing: `engine/sizing.funded_qty` (the same function the live loop calls).

## Why today's sizes lose funded accounts

- On a fresh funded account the room is $2,000 and does not grow until the floor locks (the floor trails the end-of-day high
  until +$2,100). Three $800 stop-outs before the first good winner end the account.
- Every payout takes the balance back to the $2,100 buffer, so the room is back at $2,000 after each payout: the account is
  "fresh" again five times.
- The recommended mode risks 40% of what is left: $800, then about $480, $290 ... A losing run shrinks the size instead of
  ending the account, and the floor guard never lets 1 micro reach the floor.

## The config (do not switch on without the owner)

```json
"lit_sizing": {"mode": "funded",
               "funded": {"pct": 0.4, "pct_min_usd": 100, "pct_max_usd": 800, "ref": 20, "wk": true,
                          "room_f": null, "max_win": 1500, "slip_ticks": 2, "skip_breach": true},
               "guard": {}}
```

- The room comes from the funded account: `engine.sizing.funded_state(day_pnl, today_cum, payouts)` (payouts lower the
  balance, never the floor). The callers (engine/live.py `_equity_qty`, tools/cloud_monitor.py `paper_size`) must pass
  `state=funded_state(...)` when the mode is "funded"; without it the mode trades the smallest size ($100) and logs why.
- The eval stays on `two_week`. Switch to `funded` on the first session of the funded account.

## Risk guard audit (2026-10-18)

| Guard | Where it is today | Finding | Fix |
|---|---|---|---|
| Max 1 trade a day | the model only (`engine/lit.py` max_per_day) | the router (`engine/live.py`) routes any new model entry_t; a feed revision that drops the day's first trade and creates a later one routes a 2nd trade | `lit_sizing.guard.max_per_day` (sizing.py, done); live.py must pass `n_today = self.trades_today()` in the state |
| No new trade once the eval target is reached | `two_week` only (`stop_at_target`) | eval / safe_eval / fast_eval keep trading a passed eval | `guard.stop_at_target` (done) for every eval mode, needs `profit`/`cum` in the state |
| Stop-out inside the floor / DLL with 2 ticks and the ~88-pt 1m stop | two_week: 1 tick, no commission in the room cap; safe_eval / eval: no slip or commission | with the 60% room cap it only fails near an empty account; with all-room configs (A0) it can pass the floor | `guard` worst case = (stop + 2 ticks [+ 2 pts when the stop is an estimate]) x $2 + $1.40 per micro, must stay below the room and the daily loss left (done) |
| Min 1 micro when the cap says 0 | every mode | 1 micro can still breach: a 47-pt stop at $50 room loses $96 | `guard.breach = "skip"` (default when the guard is on); `"one"` keeps the old rule. Funded mode always skips |
| Sized from an estimate (1m CISD close) | live.py `_confirm_provisional` only warns | the real open can widen the stop after the size is fixed | pass `est: true` with the trade (done in sizing: +2 pts in the worst case) |
| Max 40 micros | sizing (min(q, 40)) + NinjaTrader refuses > 40 | ok | guard re-checks 40 |
| Sizing error | live.py `_equity_qty` routes the engine's size on an exception | fail-open: the room caps are skipped | fail closed (0) when the mode is an eval or funded mode |
| Kill switch | live.py, saved in live_state.json | restored only on the same trading day: a restart the next day re-arms it silently | keep the flag until cleared by hand |
