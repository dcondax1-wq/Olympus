# A4: eval replay, risk invariants, LIT + ATLAS router (pre-launch audit 2026-10-25)

Agent 4 of 5. Paper only. Nothing was armed or routed. `live_model*.json` and `second_model.json` were not touched.
Labels used: **BASELINE** = today's live rules measured as they are; **BUG_FIX** = a demonstrated defect, fixed, with a
regression test; **RESEARCH_VARIANT** = not live, shown for comparison only.

## Result first

- **No breach anywhere.** LIT on the 50K and ATLAS on the 25K had 0 breaches in 2026, in every starting state, with both
  overlapping and non-overlapping windows. That includes the owner's real snapshot and the combined router.
- **Two-week pass (BASELINE, fresh 50K, LIT):**
  - H1 57.1%, H2 **50.7%** (35 of 69).
  - The stored `research/hq/switch.json` figure of 52.2% for H2 was computed before the 2026-10-24 cap fix. Today's code is
    one start lower. Quote 50.7.
- **The owner's real 50K** (balance $49,710.80, floor $48,168.20, needs $3,289.20, room $1,542.60):
  - Within 10 sessions: pass H1 40.3%, H2 31.9%.
  - By eval session 10 (5 more sessions): pass H1 27.7%, H2 21.7%.
  - Stuck (room under $200): H1 13.4%, H2 0%.
  - Breach: 0 in both halves.
- **Combined LIT 50K + ATLAS 25K:**
  - LIT is identical with or without ATLAS, as designed (LIT has priority).
  - The router rules remove 12 of ATLAS's 175 trades in 2026 and cut 11 more short. This *raises* ATLAS's H1 pass from 60.5%
    to 65.5%; H2 is unchanged at 43.5%.
  - Both accounts pass in the same 10 sessions: H1 37.0%, H2 23.2%.
  - Across 914 simulated ATLAS trade instances: no ATLAS position opposite a LIT trade or an armed LIT setup.
- **Two BUG_FIXes**, both fail-open sizing paths that live LIT does not reach today:
  1. `sizing.ceilings`: a stop distance that is unknown, 0 or NaN in an eval mode used to route the model's micros with no
     cap. Before: 10 micros on a $60 room. It now skips the trade (0).
  2. `multi_account.qty_for`: an extra eval account with no `eval_start` used to trade with no room cap. Before: 20 micros on
     a 25K. It now returns 0.
- **One router FINDING, not fixed** (account B is OFF; fix it before switching B on): if the broker refuses ATLAS's HEDGE
  close, B still marks itself flat and LIT's opposite order still goes out.
- **Commission gap** (`engine/lit.py` books $1.40 a micro, MFFU charges $1.90):
  - Normal sizing: $318 over 2026 ($32 a month), at most $17 a trade.
  - Eval path: at most $33.50 per 10-session window.
  - It never flips a fresh-eval result. On the owner snapshot it turns 3 of 69 H2 windows from "unfinished" into "stuck".
  - Not changed tonight (changing it would alter the 120/120 replay's P&L). Recommendation below.

## 1. Evaluation windows (BASELINE)

**Definitions.**
- **"Two weeks" = 10 trading sessions.** Sessions are TradingView CME sessions (18:00 to 17:00 ET). Holiday Globex sessions
  count as sessions.
- A window starts on one session and runs up to 10 sessions. It never crosses its half:
  - H1 = 2026-01-02 to 06-30, 128 sessions.
  - H2 = 07-01 to 10-16, 78 sessions.
- `full_window=0` marks a window that cannot see 10 sessions. Those are left out of every rate.
- **rolling**: one window per session. These **overlap**: neighbours share up to 9 sessions and the same few winning days.
  For example, H2's 35 LIT passes end on only 9 distinct sessions. `overlap_group` names the block a start falls in.
- **block**: non-overlapping 10-session blocks from the first session of each half. These are independent in time, but
  there are only 12 (H1) and 7 (H2) of them.

**Equity treatment.**
- The trailing floor moves only on **end-of-day** balances: MFFU's EOD trail, locked at start + $100.
- A breach is checked **intraday**: the day's closed P&L plus each trade's worst open point (1m bars, capped at the stop
  + 1 tick). It is also checked against the EOD balance.
- The soft daily loss pauses the day and is not a breach. A trade that would cross it is cut at the limit.
- Pass = the EOD balance reaches the target. No 2nd-day minimum is applied, because MFFU's minimum is listed as "conflict".
- Stuck = not passed, and room under $200 (LIT 50K, the `EVAL STUCK` push) or under $100 (ATLAS 25K, account B `MIN_ROOM`).
- Costs: $1.90 a micro round trip, plus 1 tick on market entries and on stop / BE / time exits.

**Sizing = what the bot routes.**
- LIT: `sizing.lit_qty` on the full live `lit_sizing`: two_week, room_f 0.55, soft daily loss cap, `wk_loss_usd` 1200 on
  the eval's ISO-week P&L, and safe_eval after session 10. The 120 trades of the live LIT replay = run `lit_live`.
- ATLAS: `account_b.qty` "need" on the 25K preset. Members are EMA, MACD and S/R, taken from the stored research trades.

| State | Account | Half | Kind | Windows | Pass | Breach | Stuck | Unfin. | Pass ≤5 | Median sessions | Min headroom | Worst day |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A fresh | LIT 50K | H1 | rolling | 119 | 57.1 | 0 | 5.0 | 37.8 | 37.0 | 4 | $83 | -$1,008 |
| A fresh | LIT 50K | H1 | block | 12 | 58.3 | 0 | 0 | 41.7 | 50.0 | 3 | $260 | -$687 |
| A fresh | LIT 50K | H2 | rolling | 69 | **50.7** | 0 | 0 | 49.3 | 36.2 | 4 | $237 | -$1,005 |
| A fresh | LIT 50K | H2 | block | 7 | 57.1 | 0 | 0 | 42.9 | 42.9 | 3 | $237 | -$1,004 |
| A fresh | ATLAS 25K (alone) | H1 | rolling | 119 | 60.5 | 0 | 3.4 | 36.1 | 44.5 | 3 | $60 | -$586 |
| A fresh | ATLAS 25K (alone) | H1 | block | 12 | 75.0 | 0 | 8.3 | 16.7 | 58.3 | 4 | $60 | -$586 |
| A fresh | ATLAS 25K (alone) | H2 | rolling | 69 | 43.5 | 0 | 0 | 56.5 | 30.4 | 4 | $122 | -$481 |
| A fresh | ATLAS 25K (alone) | H2 | block | 7 | 42.9 | 0 | 0 | 57.1 | 28.6 | 5 | $122 | -$481 |
| B owner | LIT 50K | H1 | rolling | 119 | 40.3 | 0 | 13.4 | 46.2 | 27.7 | 3 | $84 | -$841 |
| B owner | LIT 50K | H1 | block | 12 | 58.3 | 0 | 0 | 41.7 | 50.0 | 3 | $139 | -$800 |
| B owner | LIT 50K | H2 | rolling | 69 | 31.9 | 0 | 0 | 68.1 | 21.7 | 4 | $142 | -$1,006 |
| B owner | LIT 50K | H2 | block | 7 | 28.6 | 0 | 0 | 71.4 | 28.6 | 3 | $142 | -$815 |
| C fresh | ATLAS 25K (router) | H1 | rolling | 119 | 65.5 | 0 | 0.8 | 33.6 | 42.0 | 4 | $74 | -$586 |
| C fresh | ATLAS 25K (router) | H2 | rolling | 69 | 43.5 | 0 | 0 | 56.5 | 30.4 | 4 | $175 | -$481 |

Notes on the table:
- C's LIT rows are identical to A (fresh) and B (owner). C_owner's ATLAS rows are identical to C_fresh.
- Both accounts pass in the same window (C fresh): H1 37.0% rolling / 50.0% blocks; H2 23.2% / 28.6%.
- With LIT at the owner snapshot (C owner): H1 26.1% / 50.0%; H2 15.9% / 14.3%.
- "Pass ≤5" = passed within 5 sessions. For B this is the owner's real deadline: the eval clock is at session 6 of 10
  tonight.
- Worst days a few dollars past -$1,000 are the soft-loss cut plus 1 tick of slippage. That is a pause, not a breach.
- Reading the rates:
  - The rolling rates are not independent trials. The blocks are independent, but there are very few of them.
  - Read H2 as "about half of fresh evals pass inside two weeks, none failed".
  - The owner's own eval has a smaller room ($1,543 against $2,000) and needs $289 more. Read it as "about 1 in 3 within 10
    sessions; about 1 in 5 to 1 in 4 by its session 10".

**Reproduction.** On today's code, `tools/a4_eval_windows.py` LIT A-fresh matches `tools/hq_lit.run_eval_hq` start by start,
with 0 differences on H2. The 120 trade units are identical to `hq_lit.engine_units` (risk, target, points, worst point).

## 2. Risk invariants (tests/test_risk_invariants.py, 27/27)

| Invariant | Status | Evidence |
|---|---|---|
| qty < 1 after **all** caps → skip, on every path | holds | 3,000-state sweeps on the live `lit_sizing` (every eval mode, incl. `wk_loss_usd`), ATLAS on LIT's account, account B 25K / 50K need / safe, extra accounts 25K / 50K. qty × (stop + 1 tick, $1.90) stays inside the room (strict), the soft daily loss and the weekly loss. When 1 micro does not fit, the result is 0 |
| Worst-case contract cap | holds | A model asking for 100 micros gets at most 40 (50K) / 20 (25K). ATLAS's adapter cfg caps 20 / 40. The NinjaTrader adapter refuses more (`_split`) |
| Pending-order reservations | holds by construction | No account ever holds two exposures, so the one-position rule is the reservation. LIT's account blocks a second strategy while LIT holds / enters / has a limit armed / waits for its 1m CISD / has a routed position. B does not probe while its own entry is sent, pending or open. Extra accounts take 1 entry a day, and a sent-but-unconfirmed entry counts |
| Commission + 1-tick reserve | holds | Every cap prices 1 micro at (stop + 0.25) × $2 + $1.90. Example: safe_eval with a $100 room and a 20-pt stop gives 1 micro, not 2 |
| Tick rounding | holds | Stops round to the nearest tick. 0 of 282,363 2026 1m bars are off the 0.25 grid, so a stop 1 tick beyond a sweep extreme is never moved. Targets round toward the entry |
| Structural stop never widened | holds | A broker stop move only tightens, long and short. All 39 2026 STOP exits (19 long / 20 short) lost exactly the sized stop + 1 tick + costs |
| Short BE direction | holds | BE = entry − 1.25 for a short. All 35 BE exits (15 long / 20 short) made +1.0 pt a micro. The short modify is accepted and labelled BE. A live-loop poll on 2026-03-17 shows a short at 25,633.75 with its stop at 25,632.50 |
| Post-pass lock | holds | +target → 0 on LIT (every eval mode, also after session 10), ATLAS on LIT's account, account B, extra accounts. The 1-micro minimum-days trade is taken only when it fits |
| Unknown inputs → unresolved | **2 BUG_FIXes** | See below. Also: account B without state → 0; ATLAS without room → 0; a sizing exception on LIT's eval → 0 (`_equity_qty` fails closed); the live LIT path always prices the room (`eval_room()` is a number) |

**BUG_FIX 1, `engine/sizing.py` `ceilings()`.** In an eval mode, a stop distance that is unknown, 0 or NaN now gives qty 0
with the reason "skip: stop distance unknown ... (unresolved)". Before, it logged "not checked" and routed the model's
micros uncapped. Demonstrated on the pre-fix code: `lit_qty(10, {"tgt_pts": 60}, two_week, room $60)` gave 10 micros; it
now gives 0. Live LIT entries always carry entry and stop, so 2026 trading is unchanged. Mode normal is unchanged.

**BUG_FIX 2, `engine/multi_account.py` `qty_for()`.** An extra account in an eval / funded / auto mode with no state
(`eval_start` missing) now returns 0 and logs it, as `account_b.qty` already does. Before, it fell back to eval mode with no
room cap. Demonstrated on the pre-fix code: 20 micros on a 25K with a 10-pt stop, which is $458 of risk on a room nobody
knows. Extra accounts are off by default.

**Findings, not changed:**
- **Unknown room in display callers.** `lit_qty` with neither a room nor a state, in mode eval / safe_eval, still means "no
  room cap". This is relied on by `sizing.selftest` and by display callers (`lit_brief`, `brain`). The live paths always
  pass a numeric room, and account B / ATLAS fail closed. Recommendation (after launch): add an explicit `require_room` flag
  for routing callers.
- **NaN inputs.** NaN in profit, cum, wk_pnl or session raises inside `lit_qty`. Every routing caller catches the
  exception and routes 0. This is fail-closed, but noisy.
- **LIT guards fail open.** `LiveBot._guard_entry` returns None (the entry is routed) when `guards.entry_block` itself
  throws. This is the documented design ("backstops; the adapter keeps its own caps"). Account B's guards fail closed.
- **Commission gap (KNOWN GAP).** Quantified in `COMMISSION_DRIFT.csv` and `EVALUATION_META.json`:
  - Run `lit_live` 2026: 636 micros, booked +$43,820 against +$43,502 at MFFU's price. H1 +$33,901 → +$33,666; H2 +$9,919 →
    +$9,836 (PF 2.91 → 2.88).
  - Drift: $318 total, $32 a month, at most $17 a trade.
  - Eval path: a median of $10.50 and at most $33.50 per 10-session window.
  - A $1.40 book with a $1.90 broker flips 0 fresh-eval windows. On the owner snapshot, 3 of 69 H2 windows move from
    unfinished to stuck, because the bot sizes off a room overstated by up to $33.
  - **Recommendation:**
    - Tonight: keep the replay as is, and refresh the eval anchor from the MFFU dashboard daily
      (`python -m engine.eval_life --anchor`). That removes the drift from the room and the need.
    - After launch: book routed LIT P&L at `sizing.TW_COMM` in `engine/live.py _routed_pnl` / `engine/lit_live.py`. This
      changes 120/120's P&L by $0.50 a micro, not its trades. Re-baseline `tests.test_lit_live`. Or set `engine/lit.py COMM
      = 1.90` and rebuild run `lit_live`.

## 3. Router determinism (tests/test_router_determinism.py, 26/26 + 2 notes)

What holds:
- **ATLAS never opposes LIT.** A B entry is blocked while LIT holds, is entering, has a limit armed, is waiting for its 1m
  CISD, or has a routed position in the other direction. This holds in both directions. With both LIT setups armed, B is
  blocked both ways. An extra account on the other side blocks B too. The same direction is allowed.
- **Fixed order in one poll.** LIT routes first, the state is saved, then the routed second strategies run, then account B.
  Inside LIT's entry the order is: second-strategy pre-empt, then B's HEDGE close, then LIT's order. Checked in the source
  and functionally: the recorded order of the two adapters is `B exit HEDGE`, then `LIT sell`.
- **Simultaneous signals.** LIT entering SHORT, or tapped and waiting, in the same poll as an EMA LONG at the 5m open: no
  ATLAS order. Same direction: the ATLAS order is routed.
- **Cancel / fill races.** A sent-but-unconfirmed B entry blocks any 2nd probe.
- **No duplicate position.** When 2 or 3 members signal on the same 5m open, B sends ONE order, from the first member in
  the configured order (EMA > MACD > S/R). A 2nd poll on the same bar sends nothing.
- **Counters survive a restart.** B's entries today (max 2), its soft-loss lock (same day only) and LIT's account ledger
  (the 1-a-day second-strategy slot, day P&L) all come back from the state files.
- **Day and week boundaries.**
  - The day changes at 18:00 ET (17:59:59 → today; 18:00 → next day; Sunday 18:00 → Monday; both DST weekends).
    `live`, `account_b` and `multi_account` agree.
  - Eval sessions skip Christmas.
  - The eval week resets on Monday.
  - The calendar guard blocks Christmas, the weekend, the 17:00-18:00 break, and entries within 15 min of the 13:15 early
    close (Nov 27, Dec 24).
- **Shipped state.** `account_b` is null and nothing is routed.

Findings:
- **FINDING 4b (fix before switching account B on).** `AccountB.flatten` ignores the broker's answer. If the HEDGE close is
  refused, B sets `open_t = None`, books the P&L, and LIT's opposite order still goes out. B's position would then sit
  unmanaged, opposite LIT. That breaks MFFU's no-hedging rule across your own accounts.
  - Fix: keep `open_t` and retry / alert on a refused close, and consider holding LIT's entry until B confirms flat.
  - Even when the close is accepted, the two orders are not confirmation-sequenced: there can be a millisecond overlap
    between B's close fill and LIT's fill.
- **Priority = the first member with a signal, not the first allowed one.** If EMA's signal is blocked (for example by
  LIT's armed opposite setup), MACD's signal on the same bar is not taken. The research executor (`tools/atlas`) drops the
  blocked unit first and takes the next member. Only 3 opens in 2026 had 2+ members signalling (6 of 175 signals), so the
  impact is negligible, but research and live differ on those bars.
- **Minor.**
  - `AccountB.blob` keeps `list(self.seen)[-600:]` of a *set*, so which de-dup keys survive a save is arbitrary once there
    are more than 600 (probe keys add about 288 a day). Exits are de-duplicated by `open_t` / `prov.final` (persisted), so
    only same-bar probe de-dup is at stake. Fix: keep an ordered list.
  - `guards.full_closure` (New Year, Christmas; Sunday → Monday only) and `sizing._full_closures` (+ Good Friday; Saturday →
    Friday) disagree on Good Friday and on a Saturday holiday. None falls in the rest of 2026 (Christmas and New Year are
    both on a Friday).

## Files

- `research/handoff/2026-10-25/EVALUATION_WINDOWS.csv`: 1,589 windows. The requested columns come first: window_start,
  window_end, starting_state, overlap_group, result, time_to_pass, min_headroom, largest_daily_loss, rule_profile. Then:
  account, half, window_kind, full_window, sessions, trades, net, worst_intraday_day, paired_result (C rows),
  booked_comm_drift.
- `research/handoff/2026-10-25/EVALUATION_SUMMARY.csv`: the rates above, per state / account / half / kind.
- `research/handoff/2026-10-25/EVALUATION_META.json`: the reproduction check, the hedge check, the owner state in profit
  space (−289.20 / −1,831.80 / EOD high +168.20, session 5 done), the LIT cfg, and the commission study.
- `research/handoff/2026-10-25/COMMISSION_DRIFT.csv`: the 120 trades of 2026 `lit_live` at $1.40 and at $1.90.
- `tools/a4_eval_windows.py` (new, research only), `tests/test_risk_invariants.py` (new),
  `tests/test_router_determinism.py` (new).
- `engine/sizing.py` (BUG_FIX 1), `engine/multi_account.py` (BUG_FIX 2).

## Commands

```
python -X utf8 tools/second_mix.py units          # unit cache (gitignored, ~20 s)
python -X utf8 tools/atlas_lit_armed.py           # LIT armed-window cache (~6 s)
python -X utf8 tools/a4_eval_windows.py           # the CSVs above (~1 min)
python -X utf8 -m tests.test_risk_invariants      # 27/27
python -X utf8 -m tests.test_router_determinism   # 26/26
python -X utf8 -m tests.test_sizing_caps          # 41/41 (unchanged)
python -X utf8 -m tests.test_multi_account --quick  # 48/48
python -X utf8 -m tests.test_eval_anchor          # 43/43
python -X utf8 -m tests.test_mffu_rules           # 55 ok, 3 WARN (unchanged)
python -X utf8 -m tests.test_lit_live --days --bot  # the 120/120 replay (see the hand-off note for the result)
```

## Uncertainties

- **Trades.** ATLAS uses the stored research trades, entered at the 5m open. Live, B probes about 2 s after the open and
  skips a probe more than 45 s late; that is not simulated.
- **Armed windows.** LIT's armed windows come from a walker that disagrees with `simulate_x` on 66 of 1,957 setups ("CISD
  confirmed, trade dropped"). `tests/test_atlas_armed.py` covers this.
- **Intraday breach timing.** The breach check uses each trade's worst point on top of closed P&L, at 1m resolution.
  Real-time MFFU enforcement on ticks could be slightly worse. One position at a time means no cross-trade overlap.
- **Minimum days.** MFFU's minimum trading days are "conflict" (1 or 2). Passes are counted on the day the target is
  reached.
- **Owner snapshot.**
  - Each window's weekly P&L starts at $0 (tonight starts a new ISO week, so this is right for the real start).
  - `eval_prior_pnl` / anchor are not re-applied: the snapshot is used directly.
  - It assumes the balance and floor quoted in the brief are tonight's broker numbers.
- **Sample size.** H2 is 78 sessions, and its passes concentrate on 9 sessions. Treat the H2 rates as ±10 points.
