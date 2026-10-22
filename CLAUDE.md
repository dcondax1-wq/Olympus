# NQ Liquidity Engine: brief for Claude sessions (local or cloud)

The owner trades a **MyFundedFutures (MFFU) Builder 50K** eval and is building this NQ futures bot. They are not a coder and
usually write from a phone. Reply short, plain and result-first: what changed, the numbers, what's next. Do the work instead of
asking; show evidence (backtest numbers, charts) and be honest when something doesn't work.
**Steps for the owner (2026-10-20): at most 3 numbered steps, one copy-paste line, no options or side notes; do every other
part yourself or fold it into a script.**

## Hard rules (never break)
- **Futures data only:** TradingView CME `NQ1!` / `ES1!` exports in `data/` (5m 2021-11 → 2026-10-16; 1m for 2026). Never CFD,
  never Yahoo for testing. **No Yahoo live either (owner 2026-10-19, `live_model.json` `"no_yahoo": true`, `engine/pcbars.py`):**
  the PC bot trades on NinjaTrader MNQ bars (LE_BarFeed) + the TradingView exports + its own archive `data/nt_bars/`
  (gitignored); a stale NinjaTrader feed blocks new entries (FEED STALE), never a Yahoo fallback. The cloud monitor and
  watcher trade on the bars the PC pushes with its heartbeat (`heartbeat` branch: `bars_1m.csv.gz`, `bars_5m.csv.gz`); PC
  bars missing/stale -> no new paper entries ("waiting for NinjaTrader bars from the PC"). VIX/VXN from CBOE's own file.
- **No paid services.** The free PC-off path is the GitHub Actions cloud monitor (`.github/workflows/cloud-monitor.yml`); since
  no_yahoo it needs the PC's bars, so with the PC off it only waits (no paper entries).
- **Paper only.** Never arm live trading or place real orders. MFFU requires the owner to be present for live trading.
- **No secrets in the repo or chat.** `data/alerts.json`, `tv.json`, `tv_device.json`, `autostart.json`, `live_state.json`, `memory.db`
  and `.env*` are gitignored. Telegram/Discord keys live in GitHub Secrets only.
- **Frequency:** **2-4 trades a week** (owner, 2026-10-17; before: at least 2). Never make a filter that pauses trading for weeks the
  default; prefer size changes over skipping.
- **Owner requirements (2026-10-17), keep them in every report and on the dashboard:**
  - Implement what the research proves (better in 2026 AND 2021-25, 2-4 trades a week); store every experiment with its data
    (`tools/runlib.py` → `research/runs/`) and write it up in plain language (`research/writeups/`).
  - **Money, not only R:** every result shows net $ and $ per month next to PF / R.
  - **Eval speed on the MFFU 50K:** an eval should be passed or failed within **2 weeks** and never take more than **3 weeks** to
    pass. Scored as `p10/f10` (pass/fail within 10 sessions), `dec10` (% decided in 10), `p15/f15`, `slow_pass` (% of passes
    slower than 15 sessions) and `pass_med` (median sessions to pass) in every run. The live strategy as of 2026-10-17 decides
    only 19% of evals in 2 weeks (2026) and 6% (2021-25): a fast-eval sizing mode is open work.
  - The strategy is written in plain language in its own area of the dashboard (Strategy page, versioned, with its numbers).
- **Stops** go beyond the sweep extreme, i.e. the high/low made before the IFVG, never at a fixed distance. **Wide stop means less
  risk**: size follows the stop.
- **Owner's trading principles (2026-10-18, keep them):** the stop sits at the protected low/high (1 tick beyond the
  sweep extreme), never a random or fixed distance; a bigger stop means fewer micros (de-risk), a small stop allows more;
  one clear target (the VIX-band objective, banked at 8R), no greed; size follows the stop and the target. Under two_week
  sizing (fresh eval, 2026) micros fall from a median 14 at <20-pt stops to 4 at 60+ pts; $ at risk stays $450-$660 median,
  capped near $1,000 by the 60% room and the soft daily loss.
- Every result is judged on 2026 **and** on 2021-25 (5 years). A change is adopted only if it holds in both and keeps 2+/week.
  Report trades/week, % weeks with 2+, PF, net, max DD, and MFFU eval pass/fail within 2 weeks and 1 month.

## Live strategy (locked 2026-10-18): LIT, `live_model.json` (= `live_model_lit.json`) + `STRATEGY.md`
- **Owner's order (2026-10-18): LIT is the strategy, tuned and judged on 2026 only** (Jan 2 - Oct 16). Pick on Jan-Jun 2026,
  check on Jul-Oct 2026, report both halves; 2021-25 is a reference line, never a gate. This replaces "better in 2026 AND
  2021-25" for LIT changes only; every other hard rule stays.
- **Rules** (`engine/lit.py` run_x, params in `live_model.json` "lit" = `research/lit/lit_final.json`): sweep of any LIT level
  (session boxes, PDH/PDL, PWH/PWL, PMH/PML, NWOG/NDOG, build-ups), >= 0.5 ATR deep, inducement swing taken first (<= 1 ATR,
  <= 36 bars), displacement body >= 0.8 ATR, 5m CISD close; limit at the CISD level for 30 min, then a 1m CISD within 20 bars
  -> next 1m open; stop 1 tick beyond the sweep extreme (planned 8-80 pts; the 1m fill can widen it to ~88); target 18:00 open +/- 1 VIX one-day move, >= 1.5R, banked
  at 8R; BE at 1R, flat 15:55, 1 trade/day, entries 02:00-15:30. Size $800 up to 20 pts, 800x20/stop, max 40 micros; no
  cold-streak filter. Eval-safe switch (off): `how_out 0.5`.
- **Loss pack (on, 2026-10-18, `research/writeups/lit-losses.md`):** weekly stop (after 2 stop-outs in a calendar week, half
  size for the rest of it: `wk_stop`) and the Monday rule (once Monday took Friday's high only shorts, Friday's low only longs:
  `monday`). Sizing `lit_sizing.mode` **two_week (ON 2026-10-18, owner: pass evals within 2 weeks)** = "one winner passes":
  micros so the target covers what is left to +$3,000, capped at 60% of the eval room and the $1,000 soft daily loss, max 40,
  min 1, no weekly stop (config C, run `lit_2wk_rec`, `lit-two-week-eval.md`: 2-week pass H1 52.9% / H2 50.7%, fail 8.4 / 2.9,
  $174 / $181 per 2-week pass, max risk ~$990 a trade); sessions from `lit_sizing.eval_start` (PC start cfg `eval_start`
  overrides); **no reset (owner 2026-10-18):** after session 10 the eval goes on in safe_eval (`two_week_until 10`, `after_mode`;
  `tools/lit_eventual.py`: eventual pass ~80/77%); $1.90 commission; min-days 1-micro trade after an early target; mode
  `funded` exists but is off until funded_state is wired (`lit-funded-sizing.md`); missing target / eval state -> eval mode.
  **Eval lifecycle (2026-10-20, `engine/eval_life.py`, `tests/test_eval_lifecycle.py`):** pass ($53,000) -> no new trade on
  that eval in every eval mode (`sizing.eval_lock`; was missing after session 10), 1-micro min-days trade if < 2 traded days,
  push "EVAL PASSED 🎉 next steps"; fail (room <= 0) -> no trade, push "EVAL FAILED"; funded switch = `python -m
  engine.eval_life --to-funded --account "<Name>" --start <day>` (extra account, mode funded, disarmed), payouts `--payout`.
  Eval weekly loss stop wired, OFF: switch `"wk_loss_usd": 1200` in lit_sizing (both model files). Other modes:
  eval ($800 up to a 25-pt stop + 60% room cap, run lit_tight_eval_800_25_room60) | normal | fast_eval ($800 up to a 40-pt
  stop) | safe_eval (micros capped at 60% of the eval room); see `lit-experiments.md`.
- **Upgrades (2026-10-20, STRATEGY.md rule 11): 15-minute check + BE+costs ON** (owner approved): `t_check
  {"at":15,"x":0.3,"mfe":0.5}` (15-minute cut), `be_off 1.25` (BE = entry + 1.25). **Scale-in built and safety-reviewed,
  OFF** (`"scale_in": null`) until the owner's Sim roundtrip passes (`python -m engine.ninjatrader --sim-roundtrip-add` on
  Sim101, market open; the OIF quantity-only CHANGE `CHANGE;;;;N;;0;0;;;id;;` is unconfirmed on a real install;
  `docs/DAILY_CHECKLIST.md` "Switch on scale-in"; on = `{"pb":0.25,"f":1.0,"rat_k":1.0,"min_rk":2.0,"n":1}` in both files).
  Switch one off/on in live_model.json / live_model_lit.json "lit", rerun `tools/lit_losses.py live` (checks the trades
  against the stored run of the switch set) + dashboard data.
- **Results LIT + pack + t_check + be_off** (run `lit_live`, rebuilt 2026-10-20 = `lit_adopt_t15_be_off`; the 2026-10-18
  version is run `lit_live_2026-10-18`; costs in, LIT size rule): 2026 120 trades, 2.91/wk, win 55.0%, PF 4.07, +$43,385
  ($4,423/mo), DD -$2,196, eval 2 wk 31.6/1.0, 1 mo 57.3/4.9, pass rate 90.8%; H1 (picked) PF 4.98 +$33,891; **H2 (check)
  PF 2.69 +$9,493 (~$2,550/mo): quote the H2 rate**; eval path (two_week, runs `lit_adopt_t15_be_off_eval` /
  `lit_idm_eval_t15_be_off`) H1 PF 4.02 +$34,234 / H2 PF 2.20 +$9,059, 2-week pass/fail 57.1/5.9 and 52.2/0.0; 2021-25
  reference PF 1.01 +$1,211 DD -$19,436. Thin sample (13 cuts). **With scale-in (after the Sim check**, run `lit_adopt_all3`):
  2026 PF 4.43 +$59,698, H1 PF 4.94 +$44,507, H2 PF 3.48 +$15,192; eval path H1 +$53.1k / H2 +$17.3k, 2-week 58.0/2.5 and
  52.2/0.0. **Before** (2026-10-18
  pack only): 2026 PF 3.66, +$41,734 ($4,254/mo), DD -$2,315, eval 2 wk 26.7/1.9, 1 mo 55.3/3.9, pass rate 95.5%; H1 PF 4.44
  +$32,773; H2 PF 2.46 +$8,962; eval path 2-week 52.9/9.2, 50.7/2.9; 2021-25 PF 1.01 +$1,275 DD -$20,462 (no 1m data there). Needs 1m bars
  (5m only: +$6.6k in 2026). 95 of 120 trades enter 02:00-08:00 ET: NinjaTrader and the PC must be running from ~01:55 ET. **PC timing fix (2026-10-18):**
  the PC bot decides on the 1m CISD close and routes ~3 s later (was ~95 s; `tests/test_lit_timing.py`, `tests/test_lit_oif.py`,
  `lit-live-fills.md`); sizes from the forming bar's open (`le_feed\MNQ_1m_open.csv`, LE_BarFeed OnMarketData). Owner goes live
  on the eval himself (`docs/GO_LIVE_TONIGHT.md`); never arm it for him.
- **Live loop:** `engine/lit_live.py` (PC `engine/live.py`, cloud `tools/cloud_monitor.py`) on the bars from the previous
  month's first day + 1m bars (data/NQ_1m.csv + NinjaTrader 1m on the PC / the PC's pushed bars in the cloud; no Yahoo). `python -X utf8 -m tests.test_lit_live` replays every
  2026 session through it (120/120 trades identical with the pack; `python tools/lit_losses.py live` stores run `lit_live`). `tools/export_backtest.py` exports the LIT replay when the model is lit.
- **Shadow:** the cloud monitor also runs the old engine (`live_model_engine.json`) as a paper ledger, state key `shadow`,
  README "Old strategy (shadow, paper)", no alerts. The PC bot runs the old engine with `"model": "engine"` in its start cfg.
- **Apps on LIT (2026-10-18):** both dashboards show LIT everywhere; `tools/lit_dash_data.py` rebuilds the LIT Monte Carlo
  (`research/lab/montecarlo.json`) and intraday heat; `engine/lab_scope.py` scopes the Lab to LIT runs (reference `lit_live`).
  The old engine lives under an **Archive** group on both apps and in `research/archive/engine-2026-10-17/` (README with its
  numbers and the switch-back steps; old Monte Carlo/heat files; `tools/research_mc.py` / `research_intra.py` write there).
- `tools/runlib.py`, `tools/pine_parity.py`, `tests/test_live_dryrun.py` read the engine lock from `live_model_engine.json`
  (engine.lab_adapter.engine_config_raw) while live_model.json says lit.

- **Prop-firm prices: use the owner's real prices, not list prices.** MFFU runs discount codes; the owner pays Builder 25K $63 and Builder 50K $91.80 (2026-10-18, one-time, $0 activation). Look for current codes before quoting any firm's price. LIT on 60 plans: `research/writeups/lit-prop-firms.md` (eval best-day rules fail LIT; Builder 50K ~$116 per funded account).

## Second strategies (paper, 2026-10-22): `engine/second.py` + `second_model.json`
- Three research winners run next to LIT, **paper only** (no adapter / NinjaTrader import, `tests/test_second.py` checks
  it; `live_model*.json` untouched): `ema_lon_vix` (London EMA pullback, `second-ema.md`, run ema2_lon_vix), `macd_sweep`
  (MACD divergence at a sweep, `second-md.md`, md2_best), `sr_nyreclaim` (S/R NY sweep-and-reclaim, `second-sr.md`,
  sr2_nyreclaim_*; "own account recommended": with LIT it slightly worsens LIT's H2 eval path). $500 risk a trade each.
  Fourth, cloud only (`"cloud_only": true`, never on the PC route): `lit_asia` = LIT + Asia slot paper shadow
  (`lit-more-entries.md` lead 1, run lit_more_ent_asia_slot_rr3: lit_live.run with live_model.json "lit" + all hours,
  2 a day, 1 per session, Asia banked at 3R; LIT size rule), also under state key `lit_asia`.
  **PC route for the Asia slot: fixed 2026-10-22, still OFF** (owner's switch, JSON in `lit-more-entries.md`): with LIT
  `all_hours` on, guards / NinjaTrader gate + flat watch / safety flatten / autoupdate hourly follow the CME day 18:00->17:00;
  `lit.candidates(evening=True)` no longer skips the forming day before its 50th bar (was: evening entries seen at 22:10).
- Same code as the research: engine/second.py calls tools/second_ema.py / second_md.py / second_sr.py on LIT's live
  window (retail_standalone.load_frame live_cut, the simulators' live/OPEN mode). "With LIT" view = LIT first, no entry
  while LIT is in a trade, max 2 a day (MACD closed when LIT enters).
- Wiring: cloud monitor state key `second` (frozen paper ledger, README "Second strategies (paper)", pushes kind
  `second` titled "PAPER ..."); PC bot `LiveBot._second_tick` (background thread after LIT's routing, once per new bar)
  -> heartbeat / live.json `second`; dashboards: phone System > Second strategies (`second.js` + `secondcore.js`), PC
  Data > Second strategies (`/api/next/second`, `web_next/js/next/second.js`; `secondcore.js` byte-identical copy).
- Switch one off: `"on": false` in `second_model.json`. A fourth: a `second_model.json` entry with `"module"` whose
  `live_run(df5, one_min, cfg, now, lit)` returns {"trades", "state"} (or `@plugin` in engine/second.py).
- Test: `python -X utf8 -m tests.test_second` (2026 day-end replay identical to research/second/*_best.json, intraday,
  look-ahead, imports, cloud dry run, second brain checks vs real decisions); `--quick` ~1 min.
- **Routed on LIT's account (2026-10-22, owner "I want the bot to search for both"), built, OFF:** `"route": false` per
  strategy in second_model.json; switch `python -m engine.second --route <key> on|off` (refuses if
  `engine.ninjatrader --selftest` fails; never cloud_only). Routing lives in engine/live.py (`LiveBot._second_route_tick`,
  after LIT's routing; engine/second.py stays adapter-free): probe at each 5m open with the real open -> MARKET + OCO
  bracket via guards / `_route`, check once the fill bar closed (else NO TRADE flat), its BE stop CHANGE, 15-minute cut
  and 15:55 flat, `open_src` in live_state.json (restart / reconcile safe). Rules: one position; LIT first (no second
  entry while LIT is in a trade / entering / limit armed / 1m-CISD wait; an open second trade is closed at market when
  LIT enters = "LIT PRIORITY"); guards max_per_day 2 when any is routed, max 1 second strategy, LIT keeps its 1; size
  `engine/sizing.second_qty` (= research eval-safe: $500 capped at 0.6 x room and the shared $1,000 soft daily loss,
  pass / fail lock). Eval path with these rules (`tools/second_route_eval.py`, `second-route.md`): EMA H1 2-wk 55.5/10.9,
  H2 69.6/0.0, path +$36.8k / +$11.2k (research 61.3/5.0, 69.6/2.9, +$39.7k / +$23.0k; LIT alone 57.1/5.9, 52.2/0.0,
  +$34.2k / +$9.1k): keep it off on the eval. Not mirrored to extra accounts. Test `python -X utf8 -m
  tests.test_second_route [--quick] [--suites]`. Second brain: engine/second.py `brain` per strategy (checks in engine
  order, plan, log) -> heartbeat `second`, `/api/next/brain/second`, Bot Brain "Second-strategy brain" tab (phone + PC,
  `secondcore.js` SecondUI.brain).
- **Account B (2026-10-22, owner "trade it on another 50K or a 25K"), built, OFF:** `second_model.json` `"account_b": null`;
  on = `python -m engine.second --account-b "<NT Name>" --plan builder25k|builder50k --start <day> [--sizing need|safe]`
  (refused if the self-test fails), `--account-b off`. `engine/account_b.py` (LiveBot.acct_b, `_account_b_tick` after
  LIT's routing): own NinjaTrader account (OIF tag `acctb_`, own NT state, `live_state_acctb.json`), own guards, own eval
  (balance / EOD floor / room / sessions / pass-fail-stuck lock + pushes / plan soft daily loss), size
  `account_b.qty` (need = LIT two_week on the plan preset: 25K 50% room, 20 micros, $600; 50K 60%, 40, $1,000), max 2 a
  day, one position, never opposite to LIT (blocked while LIT holds / enters / has an armed setup the other way; LIT
  entering opposite closes B first = HEDGE); B's strategies never routed on LIT's account. Research
  (`tools/second_account_b.py`, `second-account-b.md`, runs `acctb_*`): 25K need 2-wk H1 68.9/0.0 H2 43.5/0.0, path
  +$19.7k/+$5.4k, +$1,549 per eval; 50K 72.3/2.5, 53.6/0.0, +$44.4k/+$7.6k, +$3,347; 2025/2021-24 ~35-39% dead in 2 wks.
  Pick: Builder 25K (MFFU: 1 funded Builder 50K per person, up to 2 funded 25Ks). Card "Account B <name>" in
  `secondcore.js` v3 (phone + PC + Bot Brain). Test `python -X utf8 -m tests.test_second_account_b [--quick]`.

## Previous strategy (shadow): Liquidity Engine, eval mode (`live_model_engine.json`, locked 2026-10-17)
- **Liquidity Engine, eval mode** (`engine/model.py`):
  1. Sweep of a liquidity pool from 08:00 ET.
  2. IFVG/CISD trigger in the killzones (09:30–11:30, 13:30–15:30).
  3. Stop beyond the sweep extreme (10–60 pts).
  4. Target the nearest **major** pool ≥1.5R away, banking 5R on the way when the draw is farther. No major pool means no trade
     (`use_fallback: false`).
  5. BE at 1R, 30-min time stop, giveback exit, max 1 trade/day.
- **Size:** `risk_usd 800` up to a 20-pt stop, then scaled down by `risk_ref_stop 20` (risk = 800×20/stop); `dd_aware false`.
- **Cold-streak filter** (`engine/equity_filter.py`): if the last 15 finished signals sum ≤ 0R, trade at **a quarter of the size**
  (`cold_mode: half`, `cold_size: 0.25`; was 0.5 until the 2026-10-17 evening lock).
- **Late entries** (15m structure already turned the trade's way) trade at **half size** (`sizing.late_mult 0.5`); **breakeven at
  +3R on trending days** (`be_at_r_trending 3.0`); `memory_seed false` (PC and cloud identical). One shared multiplier:
  `engine/sizing.py` (cold × late, rounded once, floor 1 micro). The fast-eval press (`sizing.press`) exists and is OFF.
- **Results** (live-loop replay, costs included, lock of 2026-10-17 evening):
  - 2026 YTD: 89 trades, 2.16/wk, PF 3.94, +$20,487 ($2,088/mo), max DD −$2,249; eval within 2 weeks 20.4% pass / 0.0% fail,
    within 1 month 34.0% / 0.0%.
  - 2021-25: PF 1.27, +$16,379 ($321/mo), max DD −$9,265; 1 month 8.8% / 5.2%; back-to-back 8/10.
  - 5 years: PF 1.54, +$36,866, max DD −$9,265; back-to-back evals 12 passed / 11 failed. 2026 was an unusually good year.
  - Before the lock: 2026 PF 3.48 +$20.1k; 2021-25 PF 1.09 +$6.5k DD −$11.4k; 5 years PF 1.32 +$26.6k, b2b 11/19.
  - Honest range (sensitivity study): the cold lookback 15 is a ridge (14 → +$13.3k, 13 → +$7.8k, 17 → +$10.7k over 2021-25);
    quote 2021-25 as +$8k to +$17k. Every neighbour of the lock is profitable in both periods. 2 extra ticks of slippage keep
    80-86% of 2021-25; no calendar rule is worth having.
- **Eval timing (Monte Carlo + eval-game study):** buy/reset the MFFU eval when the filter shows full size (1-month pass 22% /
  fail 8%), best within 5 sessions of the switch back from a cold streak (26% / 4.5% in 2021-25, 50% in 2026), weakest after
  20+ sessions at full size (7% / 12%), never in a cold streak (4% / 2%). `equity_filter.eval_timing(status, sessions_since_flip)`
  → cloud state `eval_timing` (verdict go/wait, state warmed/full/stale/cold), README row, flip alert, PC Cold-Streak page,
  phone Today page. The MFFU Builder 50K is the right plan; best-day-rule plans (Topstep etc.) would take 2-17 months.

## Tested and rejected (don't redo without a new idea)
- Published models as taught: ICT 2022, Silver Bullet, Mech/IFVG, continuation, ATM 5m/1m with a sharp V (0.2–1.5 trades/wk,
  PF ~1).
- 92 confluences; 6 daily-bias methods; grade/confidence sizing; partials and trails.
- Fixed 10–15 pt stops: wicked out, lose money. Structural stops are rarely ≤15 pts.
- Target variants: no cap / draw mode / "last real pool" all worse (2026 PF 1.6–2.2 vs 3.48).
- Re-sweep, inducement, FBOS, RBOS: recorded as engine features `x_resweep`, `x_inducement`, `x_fbos`, `x_rbos`; no edge that
  held in both periods. "No inducement" looked better, but the sample is thin.
- The skip-mode cold-streak filter: best PF, but it paused for 14 weeks, which the owner rejected.
- All variants with numbers: `research/lab/variant_results.json`.
- The owner's LIT Complete Report (2026-10-18, `research/writeups/lit-report-tests.md`, `tools/lit_report.py`, runs `lit_rep_*`):
  reclaim, confirmation deadline, acceptance, displacement quality (top-quarter close, 1.5-3x median body, FVG), 2+
  inducements, inducement room, 2+ levels swept, leg premium/discount, double-sided sweep, first obstacle (0.5R = lone spike),
  continuation / flip 2nd trade, costs inside the $800, Berlin-time London boxes (no 2026 change, 2021-25 +$5.8k): none adopted.
  The report's ch.21 model makes 0 trades in 2026. Beginner guide: `research/writeups/lit-playbook.md`.

- **LIT studies of 2026-10-18/19 (none adopted unless noted; write-ups in research/writeups/):** HTF confluences (75,
  chance level, `lit-htf-confluences.md`); order blocks incl. HTF OB entries and the owner's mitigation notes (84,
  `lit-order-blocks.md`); entry precision (43, today's entry is best, `lit-entry-precision.md`); all-hours / Asia /
  per-session / re-arm / F-BoS build-up (30, `lit-all-hours.md`); report-2 continuation, sessions, Smart Money Trap,
  inducement speed/hierarchy (176, `lit-adv-continuation.md`); BE/partials/targets (`lit-adv-management.md`: BE at
  entry + 1.25 pts is a small candidate); backtest honesty audit (-$500 of $41.7k, `lit-adv-audit-smt.md`); NQ/ES
  divergence; more setups: ES/MES, 15m/30m/1h, missed fills, looser filters (95, `lit-more-setups.md`); trend-day mode,
  volatility sizing, news setups (`lit-big-ideas.md`). **Of the three adopt-candidates, two are ON since 2026-10-20**
  (owner approved; numbers in "Results" above): the 15-minute check (`t_check {"at":15,"x":0.3,"mfe":0.5}`,
  `lit-loss-learning.md`; route fixed: all 13 2026 cuts routed 2 s after the check-bar close, priced from the forming bar's
  open, `tests/test_lit_exit_route.py`) and BE + costs (`be_off 1.25`). **Scale-in after BE is OFF** (`"scale_in": null`,
  `lit-big-ideas.md`; NinjaTrader MARKET add + resize of the one OCO bracket, `add_to_position`, 52/52 2026 adds match the
  backtest; two safety reviews: safe only after the owner's `--sim-roundtrip-add` on Sim101 shows stop + target qty 2 at the
  right prices). All three on the eval path (run `lit_adopt_all3_eval`): H1 +$53.1k / H2 +$17.3k vs live now +$34.2k /
  +$9.1k, 2-week pass/fail 58.0/2.5 and 52.2/0.0 (live now 57.1/5.9, 52.2/0.0); scale-in alone makes more in H2 (+$26.0k)
  but fails more. Thin samples (13 cuts, 52 adds); the cut route is still untested on a real NinjaTrader install (watch the
  first week on Sim). `idm_size` (inducement-count size) helps the LIT size rule but not the
  eval path: keep it off for evals (`lit-new-entries.md`). Funded plan: MFFU Builder + LucidPro 50K + FundedNext
  Rapid Daily 50K (`lit-funded-firms.md`, ~$1,750-2,300/mo for three); one bot can now route to several accounts
  (`engine/multi_account.py`, off by default, `data/accounts.json`).

## Key commands (run from the repo root)
- `python tools/export_backtest.py`: the live-settings 5-year replay → `research/lab/backtest_live.json`. Contains periods, months,
  stop buckets, eval odds, **per-trade reports** (why it entered / plan / result / lessons) and **lessons** (wins vs losses).
  About 1 min on 11 processes.
- `python tools/strategy_lab.py engine --name X --period ytd --params '{...}'`: score a variant. `tools/five_year.py live_jobs`
  is the exact live-loop replay.
- **Research run library** (`tools/runlib.py`, 2026-10-17): every experiment is stored with all its trades and days in
  `research/runs/<id>.json` (+ `index.json`), scored like the live results (2026 / 2021-25 / all, MFFU evals). `rl.replay(params)`
  is the exact live-loop replay (~1.5 min on 4 cores, cached in `research/runs/_cache`), `rl.size(raw, rule=...)` re-sizes
  after the fact (exact), `rl.save(...)` stores a run. `python tools/runlib.py baseline` stores the live strategy. Write-ups go in
  `research/writeups/*.md` (front matter: title, family, date, status, summary, runs). Both dashboards show runs and write-ups
  (Lab). New engine options must default to today's behaviour; bump `ENGINE_EPOCH` in runlib if an existing option changes.
- `python tools/trade_gallery.py --trades <json> --name <n> --all`: annotated trade charts → `research/lab/gallery/` (gitignored).
  Study trades the owner is reviewing are in `research/study/`.
- `python -X utf8 -m tests.test_live_dryrun --quick`: the live-loop harness. Expected 41/44 (pinned to the old engine); known fails:
  - replay entries/exits vs plain backtest
  - restart exit routing
  - kill switch later-route
  - "hygiene" (only when the PC bot is running)
- `python tools/cloud_monitor.py --out <tmpdir>`: dry run of the PC-off monitor (README + chart for the `dashboard` branch).
- `python -X utf8 tools/trade_intel.py`: Trade intel (2026-10-21) -> `research/lab/trade_intel.json`: every LIT trade (run
  lit_live + cloud paper + PC live) with ~60 entry / outcome facts and the win-loss signs (terciles on H1, checked on H2;
  8/50 "consistent" vs 13.4 by chance: descriptive only, `lit-trade-intel.md`). Rebuilds only when lit_live changes; the
  cloud build appends paper / live rows (site `intel.json`). PC Data → Trade intel, phone Trades → Trade intel. Tests:
  `tests/test_trade_intel.py` (no look-ahead on cut data), `tests/test_pcdash_api.py`.
- **Bot Brain (2026-10-21, read-only, `engine/brain.py`, `engine/brain_api.py`):** after every LIT poll (after routing and the
  state save) the PC bot builds `BOT.brain` from that poll's own market (`lit_live.run(keep=)`): stage pipeline + "waiting
  for" sentence, every level, every setup today with each rule check vs its threshold (engine order; first ✗ = why), sizing
  math, trade management, guards, thought log (`data/brain/YYYY-MM-DD.jsonl`, gitignored). API `/api/next/brain`,
  `/brain/log`, `/brain/days`, `/brain/day/<date>?t=` (any 2026 day replayed). PC: top-level "Bot Brain" (`web_next/js/next/brain.js`);
  phone: Home → Bot Brain + Home tile (`tools/web_public/brain.js`) from `live.pc.brain` (heartbeat + live.json, `brain.compact`
  < 16 KB), else the cloud's `live.brain`. Tests: `python -X utf8 -m tests.test_brain [--quick]` (filled = backtest trades
  on every 2026 day, rejected = the engine's rule, no look-ahead, sizes); screenshots `tests/shots_brain.py`.
- **Performance page (2026-10-21, competitor-features #6/7/9/11-14, read-only, `lit-robust.md`):** PC Data > Performance,
  phone Money > Performance (one renderer `tools/web_public/perfcore.js` = `web_next/js/next/perfcore.js`, view
  `engine/perf.py`, `/api/next/perf`, data.json `perf`). Range = `engine/health_band.py` (H2 bootstrap of lit_live, rebuild
  `python -m engine.health_band build`); live vs backtest = fill-audit curve (heartbeat `exec.curve`); exit efficiency =
  `tools/trade_intel.py --exit-eff`; robustness = `tools/lit_robust.py` (2026: +/-1 tick 92%, 0-3 ticks slip 98%, 20%
  missed 80%, 2 min late 68%); months = `tools/lit_walkforward.py` (re-picking loses: +$29.3k vs fixed +$33.3k);
  status = `engine/uptime.py` (cloud state `uptime`, PC `logs/uptime_pc.json`); look-ahead = `tools/lookahead_audit.py`
  (499 LIT runs, 0 flagged; `LE_LOOKAHEAD=1` checks each `rl.save`). Rerun the research tools weekly on the PC and commit
  the JSON. Tests: `tests/test_perf.py`.
- `python -X utf8 -m tests.test_no_yahoo`: no Yahoo / yfinance call in the PC loop or the cloud monitor (yfinance replaced by a
  raising stub), FEED STALE blocks entries, PC bars push/read roundtrip, roll back-adjustment, CBOE VIX (23 checks, ~10 s).

## Infrastructure
- **PC paper bot + dashboard:** `server.py` on http://localhost:8766, supervised by `scripts/run_bot.ps1` (Windows; runs only while
  the PC is on). The UI is the ES-module SPA in `web_next/` layered over `web/`, with the API in `engine/dash_*.py` and
  `engine/next_api.py`.
- **PC-off:** the GitHub Actions cloud monitor runs every 15 min on market days. It is the same engine and settings as
  `live_model.json`, keeps a paper ledger plus an MFFU eval tracker, sends phone push notifications (`engine/push.py`, `docs/NOTIFICATIONS.md`: entries, outcomes, PC silent; Telegram/Discord off
  unless `LE_ALERTS_CHAT=1`), runs the fast-entry watcher (`tools/lit_watch.py`) and the LIT day brief (`engine/lit_brief.py`), and publishes README.md and
  chart.png to the `dashboard` branch (read in the GitHub app).
- **NinjaTrader 8 route (2026-10-17, untested on a real install):** `engine/ninjatrader.py` writes Order Instruction Files into
  NinjaTrader's `incoming` folder (bracket entry, breakeven, flatten, kill) and reads fills/positions from `outgoing`;
  `ninjatrader/LE_BarFeed.cs` writes MNQ 5m bars to `le_feed\*.csv` (`data_source: "ninjatrader"`; stale -> FEED STALE,
  entries blocked; Yahoo only with `"no_yahoo": false`). Sim accounts by default; a real account needs armed + the LIVE phrase + `NINJATRADER_LIVE=1`. Self-test:
  `python -m engine.ninjatrader --selftest` (55 checks, incl. cancel-pending entries, partial exit fills and the CME early-close flat (5 min before the halt; entries stop 15 min before) added 2026-10-18; `LE_BarFeed.cs` also writes `le_feed\MNQ_1m.csv` for LIT, not yet compiled on a real install). Setup for a non-coder: `ninjatrader/SETUP.md`. Known gap: the
  Tradovate adapter never received breakeven moves or non-TIME exits (the NinjaTrader flags `route_all_exits`,
  `route_stop_moves` fix it; apply the same to Tradovate before ever using it).
- **PC off, free:** `scripts/PC_OFF_OPTIONS.md` (A: TradingView brain + one tap on the phone; B: the PC wakes itself at 07:50 ET,
  trades through NinjaTrader, hibernates at 16:35: `scripts/schedule_pc.ps1`; E: a spare Surface on 24/7: `scripts/setup_dedicated_pc.ps1`;
  paid bridges / VPS only as options C-D). The always-on PC pushes a heartbeat (`engine/heartbeat.py`, branch `heartbeat`,
  on with `LE_HEARTBEAT=1`); the cloud monitor alerts when it goes silent in a session.
- **Phone live feed (2026-10-21, `engine/live_publish.py`, `tools/web_public/live.js`, `tests/test_live_publish.py`):** the PC
  force-pushes one `live.json` (verdict, PC account / eval / position, feed ages, health, check-in time) to branch `live` of the
  PUBLIC Pages repo `nq-dashboard` every 60 s while the bot runs (5 min otherwise; orphan commit, scratch git dir
  `data/live_pub.git`, never main = no Pages build). The phone polls it every 30-60 s via api.github.com (raw fallback) and lays
  it over data.json. No extra Actions minutes. Auto-update also checks hourly outside trading time (weekdays 16:00-01:20 ET,
  weekends) when flat, nothing armed and a restart is safe (`engine/autoupdate.py` mode `hourly`).
- **Alerts plus (2026-10-21, `engine/alerts_plus.py`, `tests/test_alerts_plus.py`, `docs/NOTIFICATIONS.md`):** "LIT setup armed"
  / "Setup expired" pushes (PC `LiveBot._alerts_tick` after routing + cloud, same keys, relay de-dup); critical alerts repeat
  every 10 min (max 6) until "Got it" (phone `tools/web_public/alerts.js` #/ack posts `{"le":"ack"}` to the ntfy relay) or
  they clear (PC: heartbeat "crit" -> ops tick; cloud: Surface offline); stale-cloud alarm in the ops tick (`git ls-remote`
  of `dashboard`, 45 min); PC-vs-cloud rules hash in the heartbeat / cloud state ("rules"); on/silent/off per kind
  (`{"le":"prefs"}`). Read-only: never changes what the bot trades.
- **TradingView:** Pine port in `tradingview/liquidity_engine.pine` (parity notes in `research/PINE_PARITY.md`). Since 2026-10-17 it
  carries the locked rules ($800/20-pt sizing, 1 trade/day, no fallback target, cold-streak filter with a `cold size` input)
  and an "Alert format" input: bridge JSON (TradersPost / PickMyTrade) or phone text. `tools/pine_sim.py` is its bar-by-bar
  replica: 780/780 trades equal to the engine on the same bars; TradingView trades MNQ1! prices (the engine NQ1!), so a few
  trades a year differ. Expected Strategy Tester numbers and the Sunday checklist: `tradingview/BRIDGE_SETUP.md`.
- Refreshing `data/*.csv` needs the owner's TradingView export (tools/grab_tv_export.py on the PC). Cloud sessions can't do it.

## Open work
1. **Dashboard revamp: shipped 2026-10-17** (`web_next/`, served by default; `LE_UI=classic` serves the old `web/`).
   - `web_next/` overlays `web/`: server.py serves a file from `web_next/` if it exists, else from `web/`, so every page module
     in `web/js` is shared. Overrides: `index.html` (shell), `js/app.js` (router), `js/skins.js` (Obsidian default skin),
     `css/next.css` (design system + every control), `sw.js`, `manifest.webmanifest`.
   - New code in `web_next/js/next/`: `routes.js` (Today · Chart · Trades · Data · Modules · Settings), `shell.js` (sidebar,
     phone tab bar, Data tabs, Modules grid), `controls.js` (custom dropdowns replace every `<select>`, glyphs become SVG icons),
     `icons.js`, `viz.js` (SVG charts), `trades.js`, `datahub.js` (Results, Variants, Lessons, Study), `modpages.js` (Rules,
     Cold-Streak, Risk & Sizing). API: `engine/next_api.py` (`/api/next/*`, read-only, from research/lab + research/study).
   - The Today page hero is the 3D Live Oracle (see the 3D layer below). Next: polish ideas only (per-module live badges).
2. **PC-off web dashboard (done 2026-10-17):** https://demetrades2000-coder.github.io/nq-dashboard/, a Home Screen app (PWA) in the
   same dark design. One static page `tools/web_public/index.html` (+ manifest, sw.js) reads only `data.json`, built by
   `tools/build_web_dashboard.py` on every cloud-monitor run: live state + recent bars + pools, results, every replay trade with
   its report, replays (`tools/export_replays.py` → `research/lab/replays.json`, rerun after a new export), variants, lessons,
   study trades. The scheduled run uses the workflow on the default branch, so merge changes there.
   - **3D layer (2026-10-17):** three.js source in `tools/web_public/fx/src/` (`core.js` loop + quality, `field.js` galaxy background,
     `aura.js` card glow, `taps.js` tap sparks, `orb.js` Live Oracle, `candles.js` 3D chart + replay, `galaxy.js` trade galaxy,
     `city.js` month city). Build with `cd tools/web_public/fx && npm install && npm run build`: it writes the one bundle
     `tools/web_public/fx.js`, copies it to `web_next/js/fx.js` and stamps its hash into both import URLs (commit all of it). Lazy-loaded after first paint; Settings has
     Max / Lite / Off; off or no WebGL2 leaves the 2D page. `fx/dev.html?view=orb|galaxy|city|candles` is a test harness;
     add `?fxfixed` to a page URL to stop the auto resolution drop in screenshots. PC side: `web_next/js/next/fx3d.js`.
3. Pine port done 2026-10-17 (see TradingView above). Open: compile check on TradingView (6 constructs listed in BRIDGE_SETUP.md), optionally read signals from NQ1! so both feeds agree.
4. Optional: test "smaller size when inducement was taken first" when more data exists.
5. **Before the Dec 2026 roll:** the live LIT window mixes the TradingView file with NinjaTrader MNQ bars. Since no_yahoo every
   merge checks the overlap (`pcbars.merge_basis`): a constant offset (a roll) back-adjusts the older bars; same contract = no
   shift. Untested on a real roll: the chart switch to MNQ 03-27 must leave an overlap (load 30 days). See `lit-report-tests.md` audit. The cloud paper ledger now freezes finished trades (`tests/test_ledger_freeze.py`).
