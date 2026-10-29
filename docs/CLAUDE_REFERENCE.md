# NQ Liquidity Engine: full reference for Claude sessions

> Moved out of CLAUDE.md on 2026-10-24 so it is not loaded into every message. CLAUDE.md keeps the hard rules and an index;
> read the section you need here. Keep this file current when you change what a section describes.


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
  micros so the target covers what is left to +$3,000, capped at **80% of the eval room** (`two_week.room_f 0.8`, owner
  2026-10-25 "evals: one hit, make it quick"; 0.55 on 2026-10-24, 0.6 before) and the $1,000 soft daily loss, max 40,
  min 1, **no eval weekly loss stop** (`wk_loss_usd null` since 2026-10-25; uprisk.md MC: 2-week pass/fail H1 52.9/17.8, H2
  58.6/20.9 vs 53.0/3.6, 53.7/2.2 at room 0.55 + $1,200 weekly stop; dashboards read the matching row of
  `research/lit/uprisk_eval.json` via `tools/build_web_dashboard._live_eval_odds`), the weekly half size off (config C, run `lit_2wk_rec`, `lit-two-week-eval.md`: 2-week pass H1 52.9% / H2 50.7%, fail 8.4 / 2.9,
  $174 / $181 per 2-week pass, max risk ~$990 a trade); sessions from `lit_sizing.eval_start` (PC start cfg `eval_start`
  overrides); **no reset (owner 2026-10-18):** after session 10 the eval goes on in safe_eval (`two_week_until 10`, `after_mode`;
  `tools/lit_eventual.py`: eventual pass ~80/77%); $1.90 commission; min-days 1-micro trade after an early target; mode
  `funded` wired on the funded extra account (multi_account, OFF until `--to-funded`; `lit-funded-sizing.md`); missing target / eval state -> eval mode.
  **Eval lifecycle (2026-10-20, `engine/eval_life.py`, `tests/test_eval_lifecycle.py`):** pass ($53,000) -> no new trade on
  that eval in every eval mode (`sizing.eval_lock`; was missing after session 10), 1-micro min-days trade if < 2 traded days,
  push "EVAL PASSED 🎉 next steps"; fail (room <= 0) -> no trade, push "EVAL FAILED"; funded switch = `python -m
  engine.eval_life --to-funded --account "<Name>" --start <day>` (extra account, mode funded, disarmed; `--plan builder25k`
  for a passed 25K, id mffu25k_funded), payouts `--payout`. **Funded path (2026-10-25, `research/writeups/funded-path.md`,
  `tests/test_funded_life.py`):** `engine/funded_life.py` = the MFFU Builder Sim Funded tracker per funded account (buffer
  $2,100 / $1,100, ask line $53,600 / $26,850, cycle profit, best day vs 50%, 2 days a cycle, 48 h first payout, request
  $500-2,000 / $250-1,000, MLL at start + $100 after the 1st payout, payouts n/5; pushes "PAYOUT READY: request $X",
  "consistency: best day is N%...", lost, graduated; never requests a payout), run by `LiveBot._funded_life_tick`, data.json
  "funded_life", phone Money > Funded & payouts (hub.js v8, sw le-public-v35), PC Goals (cc.js, sw le-shell-next-v19).
  **Funded sizing (owner 2026-10-25, `research/writeups/uprisk.md`):** `lit_sizing.funded` + preset mffu_builder_50k = 60% of
  the room, <= $1,500 (x20/stop beyond 20 pts), a winner <= $2,000, skip_breach (H1/H2 $929 / $915 a month to you vs $889 /
  $835, first payout ~23-26 sessions vs 33, 0% lost); 25K preset 60% / <= $750 / winner <= $1,000 ($445 / $405).
  `funded.cons_aware` (built, OFF: -$76/mo H1). Sizing tests pin the old values in `tests/sizing_pins.py` (PINNED) and check
  the live ones there (`live_checks`): a switch change = update OWNER there + the docs. Money plan `tools/funded_path.py`
  (runs funded_path_*): Zlarior 50K funded $835/mo H2 ($889 H1), 0% lost, first payout median 33 sessions; ATLAS 25K
  $318 / $622, 13.6% lost H2 (superseded: account-B rules + live preset in `atlas-funded.md`, $517 / $582, 0% lost,
  8.5% stuck H2); Zlarior 25K $389 / $329.
  Eval weekly loss stop wired, OFF since 2026-10-25 (`"wk_loss_usd": null`; `1200` switches it back on, both model files). Other modes:
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
- **Live money at the real commission (2026-10-26, audit follow-up of 2026-10-25):** one constant `engine/sizing.LIVE_COMM`
  = $1.90 a micro round trip (MFFU / Tradovate). Every live booking uses it: `lit_live.live_booked` (trades, open position,
  days, day_pnl, `comm_rt`), `live.py` (routed exits, scale-in adds, kill flatten + its mark), the cloud paper ledger
  (`lit_add_usd`), `multi_account`, hence the eval room / anchor / pass-fail (`eval_life`, `sizing.eval_state`); the sizing
  ceilings (`TW_COMM`), guards, Bot Brain, fill audit and day brief alias it. Research keeps `lit.COMM` $1.40 (every stored
  run, `tools/lit_final.py`, `research/runs/`); a research trade books live $0.50 less per micro: run `lit_live` 2026
  +$43,820 -> +$43,502 (-$318 over 636 micros, -$33/mo, mean -$2.65 / max -$17 a trade, no trade changes sign), H1 +$33,901
  -> +$33,666, H2 +$9,919 PF 2.91 -> +$9,836 PF 2.88 (~$2,650/mo). Trades, micros, times unchanged (`tests.test_lit_live`
  compares the research $ re-priced by `booked()`; `test_lit_exit_route` / `test_lit_scale_in` / the NinjaTrader self-test
  likewise). Ledger rows booked before stay at $1.40 (finished paper trades are never rewritten); refresh the anchor
  (`python -m engine.eval_life --anchor`). On the eval the room / need now see the true balance, so a two_week size can be
  1 micro smaller in a rare case (A4: room overstated by up to $33 per 10 sessions before).
- **Shadow:** the cloud monitor also runs the old engine (`live_model_engine.json`) as a paper ledger, state key `shadow`,
  README "Old strategy (shadow, paper)", no alerts. The PC bot runs the old engine with `"model": "engine"` in its start cfg.
- **Apps on LIT (2026-10-18):** both dashboards show LIT everywhere; `tools/lit_dash_data.py` rebuilds the LIT Monte Carlo
  (`research/lab/montecarlo.json`) and intraday heat; `engine/lab_scope.py` scopes the Lab to LIT runs (reference `lit_live`).
  The old engine lives under an **Archive** group on both apps and in `research/archive/engine-2026-10-17/` (README with its
  numbers and the switch-back steps; old Monte Carlo/heat files; `tools/research_mc.py` / `research_intra.py` write there).
- `tools/runlib.py`, `tools/pine_parity.py`, `tests/test_live_dryrun.py` read the engine lock from `live_model_engine.json`
  (engine.lab_adapter.engine_config_raw) while live_model.json says lit.
- **Live learning (2026-10-25, `engine/live_learning.py`, `research/writeups/live-learning.md`, `tests/test_learning_live.py`):**
  owner order "learn like a human trader without emotion". (1) Execution learning per bot (lit / atlas) from the PC's real
  fills (`fill_audit.live_trades` + the ledger's `src`): entry / stop / target slippage ticks, signal->order / fill latency,
  commission from `broker_balance` daily real cash; `reserve_ticks` = ceil(p75 adverse slippage of the last 30 broker fills,
  >= 5 obs), clipped 1..4; comm clipped $1.90..$4.00 -> `logs/learning/costs.json` (PC fill-audit Watcher after each audit;
  heartbeat block `learn`). `lit_sizing.learn_costs` (false in both live_model files): true = `sizing.cost_reserve` re-prices
  every cap (room strict, two_week room_f / safe_cap share, soft daily loss, wk_loss_usd) at (stop + reserve x 0.25) x $2 +
  comm, never more micros (also `second_qty` with the atlas reserve); "scale" also shrinks every size in proportion
  (rejected: 2026 journal +$48.7k -> +$43.5k). Eval MC: neutral (p10 H1 51.5 = 51.5, H2 52.2 = 52.2, f10 0). (2) Review
  journal: every finished Zlarior (paper ledger + PC trades vs this run's lit_live twin), ATLAS (paper ledger vs this run's
  second.run, `_LIT_IN["second_run"]`) and ATLAS v2 (vs the member trade) trade -> state `learning_live.reviews` (matched /
  missed / extra, diff, gap $ / R, exec $, cause code, MFE / MAE; PC adds brain rule checks after the session,
  `logs/learning/reviews.jsonl`). Weekly summary Mon-Fri with the health band (lit) / scorecard (atlas), pushed Sunday
  >= 17:00 ET (kind weekly, key learnweek:<monday>). (3) `suggestions()`: lit_learn shadow knobs with "would have changed $X"
  (lit_learn.simulate) + the approve / revert command; the cost reserve card. UI: phone `learning.js` + `learncore.js`
  (pages learning / atlearn in clean.js Results), PC `web_next/js/next/learning.js` (learnlit / learnatlas), learncore.js
  byte-identical in both; `GET /api/next/pc/learning`; data.json `learning_live`.

- **Prop-firm prices: use the owner's real prices, not list prices.** MFFU runs discount codes; the owner pays Builder 25K $63 and Builder 50K $91.80 (2026-10-18, one-time, $0 activation). Look for current codes before quoting any firm's price. LIT on 60 plans: `research/writeups/lit-prop-firms.md` (eval best-day rules fail LIT; Builder 50K ~$116 per funded account).

## Second strategies (paper, 2026-10-22): `engine/second.py` + `second_model.json`
- **Name: ATLAS (owner 2026-10-22 evening: "LIT on the 50K, the new one on the 25K, then we scale")** = EMA + MACD + S/R pooled
  on account B. Display name only (internal keys stay `second` / `account_b`): phone bottom tab ATLAS (Home · Brain · ATLAS ·
  Trades · Money · More; Strategy folded into More), PC top-level ATLAS, Home/Today two cards "LIT · 50K" / "ATLAS · 25K",
  `SecondUI.atlas` / `twoCards` (secondcore.js v5), data `second.atlas` = `research/second/atlas.json` else the account-B 25K
  research (`engine/second.atlas_info`), README "ATLAS (paper)", pushes "ATLAS PAPER ...", account label "ATLAS <NT name>".
  Test `python -X utf8 -m tests.test_atlas_ui [--shots <dir>]`.
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
- **Stop-hunt candidates (2026-10-23, PAPER, `research/writeups/stophunt.md`):** `sh_asia` (Asia resweep hunt, 18:00-02:00,
  pick sh_asia_resweep) and `sh_trend` (trend inducement hunt, any hour, sh_trend_idm5), plugin kind `stop_hunt` =
  `tools/stophunt.live` (the research pipeline on LIT's window, cut data, OPEN mode; `engine/stophunt.bars` / `build_pools(types=)`;
  numba optional, not in requirements-cloud). `"candidate": true`: never routed (load_cfg / set_route refuse), not on account
  B, not ATLAS members; ATLAS page "Candidate members (paper)" (secondcore.js v6 `candCard`, phone sw le-public-v28),
  own scorecard bands (`second_scorecard.CANDIDATES`). Evening: the PC bot runs them every bar 24/5 (heartbeat / live.json);
  the cloud cron has no evening runs (01:32 ET is the first), so it books the night's trades at its next run. Test `python
  -X utf8 -m tests.test_second_stophunt [--quick]` (2026 replay 78/78 + 59/59).
- **ATLAS v2 PAPER SHADOW (2026-10-25, `engine/atlas_v2.py`, `research/writeups/atlas-v2.md` candidate 1b):** ATLAS +
  sh_asia + sh_trend at weight 0.5 + a new eval when room < $200, on a simulated Builder 25K next to the live ATLAS
  (= tools/atlas_v2.score on the members' paper trades: need size via `account_b.qty(key=)`, one position, max 2 a day,
  no-hedge vs LIT trades + armed setups, HEDGE cut, $600 soft loss). Never routed. Cloud: state key `atlas_v2` (own frozen
  ledger + eval tracker, from state `second` ledgers + LIT's run); PC: `LiveBot._second_tick` paper thread ->
  `data/live_state_atlas_v2.json` (gitignored), heartbeat `second.atlas_v2`. Scorecard bands
  `research/second/atlas_v2_scorecard.json` (`python -m engine.atlas_v2 build`; hunts: decide after 20+ hunt trades).
  Pushes kind `second` "ATLAS v2 PAPER ...", OFF by default (`second_model.json` `"atlas_v2": {"push": false}`). Card: ATLAS
  page (secondcore.js v8 `atlasV2Card`, data.json second.atlas_v2, /api/next/second atlas_v2; phone sw le-public-v31).
  `account_b` keys `"weights"` / `"min_room"` are built but OFF (absent = today's sizing / $100 stuck). Test `python -X utf8
  -m tests.test_atlas_v2_shadow [--no-cloud]` (2026 replay = the research executor exactly; the stored run file was scored
  on an older unit cache: 206/207 trades identical, $ within 0.1%).
- **BLITZ, the scalper (strategy 3) PAPER SHADOW (2026-10-28, `engine/blitz.py`, `research/writeups/scalp-na-mffu.md`):**
  the noise-area 1m scalp + the prior-day range filter (`prng>=0.8`: trade a day only if yesterday's 09:30-16:00 range >=
  0.8 x the mean of the last 14 such ranges, yesterday's included, as `tools/scalp_na_lib._day_ctx`); band = 09:30 open x
  (1 +/- sigma), sigma = 14-session mean of |close / 09:30 open - 1| at that minute; checks at the 1m closes 11:00, 11:30 ...
  15:30 (research window 10:30-15:30, every 30 bars from 09:30: the first is 11:00); close above / below = long / short at the
  next open + 1 tick; stop 1.5 x ATR(14) of 5m; trail 1.5R after +1R (20R limit never reached); out after 30 bars / 15:55;
  one position, 6 a day, -3R day stop; $1.90 + 1 tick per market / stop fill. Option (off): `second_model.json` `"blitz":
  {"unfiltered": true}` = the plain NA of `scalp-momentum.md` (30% eval size). Two PAPER ledgers, never routed (no adapter /
  order import; `live_model*.json`, `second_model.json` untouched; optional read-only `"blitz": {"on": false}` / `{"push": true}`):
  (1) simulated Builder 25K eval at 40% of the room, <= $600 (na_sizing pick), stuck room $249.56, new eval $63 after pass /
  fail / stuck = `tools/scalp_na_lib.run_eval` back-to-back path; (2) **BLITZ on a funded 50K next to LIT**: its own Engine
  where a candidate is dropped while LIT holds a trade or has a setup armed at the signal close; skipped when LIT is in a trade
  or ATLAS holds the other side at the entry; closed at the bar open of LIT's entry (LIT FIRST) / an opposite ATLAS entry
  (HEDGE); size `div_stack.na_q` (20% of the room, <= $450, the $1,000 DLL left, 40 micros), up to 6 a day; simulated funded
  50K ($2,000 EOD trailing, lock start + $100) with BLITZ's own P&L only, no payouts. LIT = the bot's lit_live run (trades,
  position / enter_now, armed setups + pending signals, windows kept in `lit_armed`); ATLAS = the members' paper trades (EMA /
  MACD / S/R) + account B's open trade (`LiveBot._blitz_atlas_open`). Parity: `backtest(df)` and `Engine` (one closed bar at a
  time, JSON state; a half day's last bar found by the next bar or the clock at 16:00) = `research/scalp/na_best_trades.json`
  330/330 (unfiltered = `mo_best_trades.json` 481/481); the 50K ledger on the research's LIT / armed / ATLAS trades =
  `tools/scalp_na_combo` units (lit_flat -> cut_on -> yield_to) 312/312. PC: `LiveBot._second_tick` paper job (bg_worker
  `job_second` after `second.run` / thread) -> `pc_step(<state dir>/blitz_state.json, df1, now, res, second, atlas_open)`
  (gitignored, in memory between polls, ~2 ms a new bar) -> `LiveBot.blitz`, heartbeat `blitz` (compact: state, 25K eval,
  `funded50`), Live View purple layer (`liveview_api.blitz_layer`: band lines, signals, PAPER positions of both ledgers;
  the chart JS does not draw `scalp.lines` yet), narrator kind `blitz` (strat scalp, never pushed by default). Cloud: state
  key `blitz` next to `atlas_v2` with LIT's run + the ATLAS ledgers (cold start warms 35 days of data/NQ_1m.csv + PC bars),
  pushes kind `second` "BLITZ PAPER ..." recorded unless `blitz.push`, README lines. Replay H1 / H2: 221 / 109 trades, PF
  1.63 / 1.49, $150 a trade +$5,560 / +$2,143; 25K eval path +$7,193 / +$4,726 (4/2, 3/2 pass / fail+stuck), after fees
  +$6,752 / +$4,411 (~$1,108 / $1,188 a month), 2-week pass / fail 31.1/10.1, 34.8/2.9; 50K next to LIT (research LIT /
  ATLAS trades) 207 / 105 trades, +$11,750 / +$7,923 trading P&L (~$1.9k / $2.1k a month at $400-450 risk, no payouts: the
  research's whole-slot gain after MFFU payout limits is +$301 / +$290 a month). Test `python -X utf8 -m tests.test_blitz
  [--cloud]` (~65 s).
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
- **Account B funded (2026-10-26, `research/writeups/atlas-funded.md`, `tests/test_account_b_funded.py`):** a pass only
  stops the eval and pushes "EVAL PASSED ... run the funded switch" (never automatic). Switch (MFFU gives a NEW Name):
  `python -X utf8 -m engine.account_b --to-funded --account "<funded Name>" --start <day> [--balance 25000]` or the
  Start page's "Passed → funded" on ATLAS's row (`go._b_to_funded`; data/start_bot.json "atlas" follows, prepped kept):
  the local block gets `"stage": "funded"`, `funded_start`, `funded_balance` (above / below the plan start = P&L before
  the bot), `payouts`, `eval_account`, `funded_set`; armed / eval_anchor / prior_pnl dropped (DISARMED); the funded Name
  allowlisted; the eval's state kept as `live_state_acctb.eval_<Name>.json`. `set_account_b` on the same Name (arm_b,
  launch prep) keeps the funded stage. Funded B: `account_b.funded_qty` = `sizing.funded_qty` on the 25K preset (60% of
  the room, <= $750, winner <= $1,000, $600 DLL, 20 micros, skip_breach) + dll_guard, weights never raise it; state =
  `multi_account.sizing_state("funded")` since funded_start (+ prior, payouts; floor at start + $100 after the 1st
  payout); no broker anchor; lost / stuck (room < $100) / graduated = no new entry; tracker `funded_life.track` (new arg
  `prior`; `notices` takes `record_cmd`) -> pushes PAYOUT READY (record: `engine.account_b --payout <day>=<$>`),
  consistency, lost, graduated + B's own "funded account stuck"; `--funded-status`. Views: info() adds stage / funded
  (eval info unchanged byte for byte), heartbeat second.route.account_b, live board atlas_now + boardcore.js, ATLAS page
  secondcore.js fundedB, Goals, scale plan (phone sw le-public-v38). Research `tools/atlas_funded.py` (runs
  atlas_funded_live / _old, research/second/atlas_funded.json; trades tools/atlas.account_units, size = account_b.qty):
  H1 / H2 $582 / $517 a month to the owner, 0.73 / 0.65 payouts a month, first payout median 18 / 24 sessions, 0% lost,
  8.2 / 8.5% stuck; 2025 / 2021-24 $64 / $39, 89 / 96% stuck (no edge there); per eval bought $3,178 / $3,057 at $43.
  mffu_rules.json builder_25k checked vs the owner's screenshots 2026-10-26 (all match; DLL confirmed).
- **Account B pre-launch (2026-10-22, `second-prelaunch.md`):** stress test `tools/second_robust.py` (runs sb_robust_*,
  research/second/robust.json): noise / slippage / 10-20% missed keep ~80-104% of 2026 $, 25K 2-week pass ~61-68 / 41-43;
  **1 bar late is the weak spot** (25K 49.6 / 31.9, EMA H2 4%, S/R H2 negative): never chase a late entry (MAX_AGE_S 45).
  **Go / no-go scorecard** `engine/second_scorecard.py` (bands = bootstrap of 2026 H2 trades + 2025, research/second/
  scorecard.json, rebuild `python -m engine.second_scorecard build`): go live only after 20+ finished paper trades at or
  above the expected p10; under p5 = don't go live; shown in data.json / `/api/next/second` "scorecard", secondcore.js v4
  (phone sw le-public-v25), cloud README. Test `tests/test_second_scorecard.py`. Bad-market brake (`tools/second_brake.py`,
  57 rules, runs sb_brake_*): none adopted, none built (cuts dead evals but also passes; real money within +/-$1.6k / 5 y).
- **Account B entry the broker never took (2026-10-27, `tests/test_acctb_not_placed.py` 24/24):** the 03:30 MACD LONG 3 on
  the 25K answered NOT OK (heartbeat `entries_today` 0), yet B kept it "open" (other B entries blocked, its paper P&L would
  be booked on B's eval, the phone showed a trade that never existed). Now `AccountB.never_placed` (answer NOT OK, no leg
  filled / open / pending, NinjaTrader shows no position on B's contracts; a leg still working counts only once the
  adapter retired it unfilled; anything unclear = kept) -> `_drop_unplaced`: B flat, no exit routed or booked, a close an
  older version booked is voided (once per process), push "order NOT placed" + NinjaTrader's reason. A NOT OK answer that
  may still be open -> kept + push "order NOT confirmed". Checked at the entry, every poll (`reconcile_unplaced`) and
  before LIT's hedge close. Heartbeat `second.route.account_b.routed` rows carry `ok`, `error` (paths removed), `void`.
  The rule is `engine/ninjatrader.entry_never_placed`, shared with LIT (`engine/live.py`): a refused LIT entry pushes
  "order NOT placed" + the reason (or "NOT confirmed" when it may be open), and its model exit books $0 on the eval (was
  the backtest's $: test part 7 replays 2026-10-13, a +$3,169 day). An exit for an entry never routed (bot off) also books
  $0 now (the +$0.10 BE "missed" 08:37 trade booked on the 50K at 23:08 ET 2026-10-26).
  Same day 06:12 ET Zlarior's SELL 7 answered "fill not reported yet" and was never filled (adapter: cancel never
  confirmed, account flat): the old code booked -$965.30 on the 50K, B's phantom HEDGE close +$525.30. After a restart
  the adapter's retired legs are gone, so `_no_trace`: 10 min after the entry, no outgoing\ file with LE<entry_t> and a
  FLAT position file for every contract = never placed. `LiveBot._void_unplaced_exits` (once per process) sets such
  booked exits to $0 (`pnl_void` keeps the old figure) + push; B's once-per-process scan voids its closes. Tests
  `test_acctb_not_placed` 41/41. Why NinjaTrader never answered the MFFU orders: heartbeat `nt_log` (`engine/nt_log.py`,
  the Log-tab lines with our LE ids / rejects / ATI / errors, paths and e-mails removed).
- **Start (owner 2026-10-27 "no PowerShell", "PC on = it runs"):** one Run / Stop switch at the top of every PC
  dashboard page (`web_next/js/next/runswitch.js`, Run = `/api/next/start/go`, Stop = `/api/live/stop`; tests
  `test_run_switch`). The bot server runs hidden. After a reboot `autoresume.resume_live(still_on=, open_nt=)` opens
  NinjaTrader and waits for it with no time limit while the switch is on Run (autostart record present).
  `engine/fsutil.replace` retries state-file replaces on Windows file locks.

## Trade pictures (2026-10-23, `engine/trade_chart.py`, read-only)
- One renderer for every strategy's trades (LIT, LIT+Asia, ema / macd / sr, sh_asia / sh_trend): 1600x900 dark PNG (~90 KB),
  5m from ~2 h before the setup to the exit + 1m entry panel, "Why it entered" rule checks, legend, ET axis, sessions.
  Markups come from the strategies' own code: LIT = `lit_live.run(keep=)` + `tools/lit_chart_data.record_of` +
  `brain._checks`; second strategies = `second.run` with cfg `"_marks"` (`engine/second.py` `_ema/_md/_sr/_sh_marks`; off =
  trades unchanged). Bright (`k:`) = closed bars / marks known at the entry, `plan:` from the entry, faded (`a:`) after.
- Where: cloud `cloud_hook` (new trade at entry, redrawn at exit, max 10 a run / 50 s, newest 60 per strategy in
  `<dash>/charts/` + index.json, restored by the workflow) -> site `charts/` + data.json `charts` (`site_copy`); PC
  `LiveBot._chart_tick` -> `PcCharts` background thread -> `logs/charts/`, `/api/next/charts`, `/api/next/chart/<key>.<tid>`
  (`engine/chart_api.py`); examples `python -m engine.trade_chart backfill --strategy all --since 2026-07-01` ->
  `research/lab/chart_examples/` (~20 each, 12 MB). One trade: `python -m engine.trade_chart one --strategy X --day D`.
- Shown by `tradepics.js` (phone = PC copy, byte-identical; full screen, pinch / double-tap zoom, swipe): ATLAS brain cards +
  "Trade pictures" strip + candidate cards (secondcore.js v7), LIT Bot Brain + Trades (phone sw le-public-v29).
  Test `python -X utf8 -m tests.test_trade_chart [--shots <dir>]` (78 checks incl. look-ahead, cloud dry run, Playwright).

## AI watch (2026-10-22, `engine/ai_watch.py`, `research/writeups/ai-features.md`; alerts on, blocks OFF)
- Per poll after routing (`LiveBot._alerts_tick`, real bot only), LIT + account B: anomaly pushes (bad tick / 1m spike /
  jump, entry routed 30+ s after its signal), **feed frozen in a trade** (critical, repeats until Got it), drift per
  strategy (LIT health band H2, account B bootstrap of run `acctb_<plan>_<sizing>`, fill-audit execution), both accounts'
  P&L today / this week (push at -$1,500 / -$3,000), rule-change push (`engine/rulelog.py`: git who / when / why ->
  `research/lab/rule_log.json`, runtime `logs/rule_changes.jsonl`). Kinds anomaly / freeze / drift / loss_cap /
  rules_change (phone alert levels). Pre-session push adds news / account B room / blocks on; weekly push a self-review.
- **OFF switches** (`live_model.json` "guards", via `guards._owner_blocks` = LIT and B): `"anomaly_pause": true` (15 min
  after a spike, while frozen in a trade), `"combined_loss": true` (`combined_day_usd` 1500, `combined_week_usd` 3000).
- Restore: `python -X utf8 -m engine.ops_checks --restore latest [--yes]` (refused while running / in a trade). Phone System >
  AI watch (`tools/web_public/ai.js`), PC System card (`/api/next/ai`). Test `python -X utf8 -m tests.test_ai_features`.

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
- **B-holds (2026-10-27, `b-holds-vs-lit-priority.md`, `tools/bholds.py`, runs `bholds_*`):** while ATLAS (account B) holds a trade, skip
  LIT's opposite entry instead of closing B (HEDGE). Both accounts 2026 +$52.3k -> +$53.6k, 2021-25 -$3.2k -> -$5.0k; ATLAS 25K
  2-week pass H1 65.5 -> 60.5 (stuck 0.8 -> 3.4); 9 clashes in 2026, 35 in 2021-25. Rejected: LIT priority stays.
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
  backtest; two safety reviews: safe only after the owner's `--sim-roundtrip-add` on Sim101 (since 2026-10-26 it proves the size itself: step 5 moves the target under the market, it must fill 2 micros and end flat, then prints SCALE-IN READY; `tests/test_sim_add_proof.py`) shows stop + target qty 2 at the
  right prices). All three on the eval path (run `lit_adopt_all3_eval`): H1 +$53.1k / H2 +$17.3k vs live now +$34.2k /
  +$9.1k, 2-week pass/fail 58.0/2.5 and 52.2/0.0 (live now 57.1/5.9, 52.2/0.0); scale-in alone makes more in H2 (+$26.0k)
  but fails more. Thin samples (13 cuts, 52 adds); the cut route is still untested on a real NinjaTrader install (watch the
  first week on Sim). `idm_size` (inducement-count size) helps the LIT size rule but not the
  eval path: keep it off for evals (`lit-new-entries.md`). Funded plan: MFFU Builder + LucidPro 50K + FundedNext
  Rapid Daily 50K (`lit-funded-firms.md`, ~$1,750-2,300/mo for three); one bot can now route to several accounts
  (`engine/multi_account.py`, off by default, `data/accounts.json`).
- **Reversal exits after the first live trade (2026-10-28, `lit-reversal-exit.md`, `tools/lit_rev_exit.py`, runs `lit_rev_*`):**
  exit / BE on a violent reversal once +0.5-0.9R (ATR candles, 2-3 candles, profit giveback), 1m/5m swing trails after
  +0.5-1R, BE at 0.75/0.9R, stop at the first 1m/5m highs: 103 variants, none better in both 2026 halves (the 2-ATR candle exit
  after 0.9R: today +$168 vs -$437 but H1 -$9.1k / H2 -$2.3k; first 1m highs H1 +$29k / H2 -$13k PF 0.75). 2026 had 0
  trades that went 0.9-1R then stopped before 2026-10-28. Nothing changes.
- **Diversifier search (2026-10-26, `diversifier-search.md`, `tools/div_search.py` / `div_stack.py`, runs `div_*`):** the
  VXN-normalised initial-balance breakout is dead (0/24 settings positive in all four spans). The noise-area intraday momentum
  (Zarattini 2024) is REAL as futures trading (paper rule and joint pick `na_vm125_1000_n99_fixed` positive in H1 / H2 / 2025 /
  2021-24, placebo p 0.007 in 2026, daily corr with LIT ~0) but NOT a prop strategy alone (MFFU eval p10 <= 22%, funded
  $13-117/mo: 27% winners, 18-23R drawdowns vs the 50% best-day rule and the $2,000 floor). Only as a small add-on on LIT's
  funded accounts (3-4% of the room, <= $150, never while LIT holds): +$54-83/mo per 50K in 2026, +$7-12 in 2021-25; paper only.
- **Payout / eval mechanics (2026-10-26, `payout-policy.md`, `eval-cost.md`):** ask line $1,000 / $2,000 vs $1,500,
  cons_aware, stack payout reserves (cap a month) and pre-buying the next eval at the 4th payout: see the write-ups before
  redoing. Eval: keeping two_week after session 10 (`two_week_until` 999) is the one change that held in H1, H2 and 2021-25
  (+$14-21/mo per slot; owner decides, not switched).

## Key commands (run from the repo root)
- **START BOT (owner's one start, 2026-10-26):** the owner now starts from the dashboard only (desktop **LE START** -> the
  Start page's **Start trading**, `go.step_auto`; Infrastructure, "Start & Accounts page"). `START_BOT.bat` -> `engine/go.py`
  stays for the console: the update (`autoupdate.pull`, bot stopped), names asked once (`data/start_bot.json`,
  gitignored), `launch_prep` once, both Sim101 roundtrips until passed once (market open only), owner types the LIVE
  phrase -> `arm_b` (`data/account_b.json` `"armed": true`, other fields kept), the live line in `.env.local.ps1`, server
  (re)started when that file is newer than the supervisor or the server runs older code (`go.server_stale`),
  `ninjatrader --start` on the 50K, launch checklist, dashboard. Wrong phrase = nothing armed. Tests `tests.test_go`.
- `python -X utf8 -m engine.autoupdate --pull`: the update now with the bot stopped (UPDATE.bat, START BOT); the same
  fast-forward as the auto-update. `python -X utf8 -m engine.account_b --migrate`: move ATLAS's block out of
  second_model.json by hand (the server does it at start).
- `python -X utf8 -m tests.test_poll_timing [--full]`: the poll stage timer and the outgoing-folder cache (`--full` replays
  test_lit_live's LiveBot with and without the timer, ~15 min).
- `python -X utf8 -m tests.test_poll_speed [--quick] [--compare]`: the LIT path of the poll (health.lit_ms) with every
  background feature on vs off (gate: median <= 1.6 x off + 150 ms, p90 <= 2 x off + 300 ms, median <= 3 s); worker =
  threads (orders, second run, ATLAS v2, pictures byte for byte); bar-frame deltas; worker deaths / hangs; news / ES off the
  poll path (~3 min; `--compare` also runs the old threads and checks the gate catches them).
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
- **Dashboard 2026-10-28 (owner: "50 useful features", "what the bot is thinking", "very 3D"):** registry
  `web_next/FEATURES.md` (status of all 50). Home "Today · real accounts" (`realcore.js`, `cc.js`; phone
  `tools/web_public/realcore.js`): one card per REAL account (ledger + NinjaTrader fills only, never paper $), gauges, health
  score, ledger check (`engine/live_board.py` flags an eval day booking $ with no real trade). Real results page (`real.js`,
  `#/real`, CSV export). AI Insights (`insight.js`, `engine/insight_api.py` `GET /api/next/insight[?day&hm]`, features 21-30).
  Live View (`liveview*.js`, `engine/liveview_api.py` `GET /api/next/liveview?tf=1m|5m`): full-screen chart, per-strategy
  colour layers (Zlarior blue, ATLAS orange, BLITZ purple), "what the bot is thinking" panel, feed.
  **Phone Live View (2026-10-28, `tools/web_public/liveview.js`, `#/liveview`, Home button under the plan line, More > Today):**
  the same page on the phone. The PC pushes `liveview.json` (`liveview_api.phone_view`: 1m bars of the last 8 h + the 5m
  session as `bars5`, the three layers, thinking, feed 60; < 240 KB) in the same orphan commit as live.json on branch `live`
  (`live_publish.push(extra=)`, `Publisher.extra`). Phone reads it via the GitHub API (raw fallback, shares `LIVE.apiUntil`),
  every 30-60 s while open; live.js waits ~3 min on that page. `liveviewchart.js` / `liveview.css` byte-identical copies;
  full screen = Fullscreen API, else the root moves to `<body>` with `lv-max` (iPhone); sideways = chart-only bar.
  Banner when the PC has not sent for 20 min. Sw `le-public-v42`. Test `tests.test_phone_liveview` (37, Playwright). Narrator
  (`engine/narrator.py`, hooked in `LiveBot._alerts_tick`, real bot only, never raises): plain-language feed,
  `logs/narrator/<day>.jsonl`; phone pushes only for armed / entry / exit / refused (`data/narrator.json`, `LE_NARRATOR_PUSH=0`).
  Tests: test_real_ui, test_insight_api, test_liveview_api, test_narrator.
- **Deep space + Mission Control (2026-10-29, owner: "make it look cooler ... almost like 3D space"; read-only):** the default
  look of both dashboards. 3D: `tools/web_public/fx/src/space.js` (in fx.js; `FX.init({ level, bg: 'space' | 'galaxy' })`):
  Earth (continents / clouds / city lights baked once from noise into textures, then texture reads + lighting), the Moon
  crossing the Sun (a real sphere over the corona; glare + lens ghosts dim with the cover) and its soft shadow sliding over
  the lit side (city lights come on inside it), analytic atmosphere rim, 3-layer parallax stars + baked Milky Way, one
  satellite per bot (`FX.bots({ lit, atlas, scalp: 'trade' | 'armed' | 'idle' | 'off' })`), a shooting star per newly closed
  trade (`FX.shoot('win' | 'loss')`), the aurora / rim tint from today's real P&L (`FX.pnl(usd)`), warp streaks on a page
  change, `FX.stats()`. Cost: DPR cap 1.5 phone / 2 PC, phones <= 30 fps, everything 30 fps after 20 s idle, nothing while
  hidden or under a full-screen view (Live View), reduced motion = one still frame, software GPU = small bakes, a phone below
  17 fps drops to ~16 fps; no backdrop blur over it on phones; name tags ride next to the satellites (`FX.labels(on)`). 3D is ON by
  default again (one-time reset of a stored Off: `clean.fx2` phone, `nx.fx2` PC); automated browsers (`navigator.webdriver`)
  start Off unless the URL says `?fx=max|lite`. Off / no WebGL 2 = the static CSS sky (`space.css`, painted at first load).
  Harness: `fx/space.html?lit=trade&atlas=armed&pnl=300&eclipse=0&fxfixed`. Mission Control: shared renderer
  `missioncore.js` (window.MissionUI, byte-identical copies like boardcore.js; `mission.css`, `space.css` too, copied by the fx
  build) reads only the live board (+ Live View data for BLITZ's line, the news); renders every account-shaped board block
  generically (lit, atlas, a third one such as `blitz` / `scalp` or `board.accounts`; a BLITZ placeholder "paper / not live
  yet" otherwise). Phone `mission.js` (Home strip on top + `#/mission`, More > Today); PC `js/next/mission.js` (Main >
  Mission Control after Home; `initMissionSync()` drives the satellites / stars / aurora every 15 s). Features 51-67 in
  `web_next/FEATURES.md` (stop-out now, why no trade yet, session timeline, alerts center, health constellation, eval runway,
  streaks & consistency, daily loss & week pace, next news). Live View draws `view()["structure"]` when present (zone, pools,
  swings, BOS / CHoCH, protected; a Structure switch + a "Market structure" thinking card). Caches le-public-v43 /
  le-shell-next-v25. Test `python -X utf8 -m tests.test_space_ui [--shots <dir>]` (static, node render, phone + PC Playwright).
- **Start & Accounts page (2026-10-26, PC dashboard sidebar "Start", page `start`):** START BOT as one checklist, one button
  per red line: NinjaTrader connected · live bars from NinjaTrader (`go.feed_problem`, fix "right-click the MNQ 5-minute chart > Reload NinjaScript (or re-add LE_BarFeed)"; the Sim job is refused while stale) · accounts set (50K -> Zlarior, 25K -> ATLAS) · setup done · Sim tests passed · armed ·
  running and routes verified, plus the plain line `Zlarior -> 50K <name> · ATLAS -> 25K <name> · both armed · running`.
  Same code as the console: `engine/go.py` is split into `step_prep` / `step_nt` / `step_sims` / `step_arm` (+ `arm_problem`,
  `slot_problem`, `mixup`, `verify_routes`); `run()` calls them for START_BOT.bat, the page calls them through
  `engine/start_api.py` (`/api/next/start/*`, mounted by next_api). Sim test and arm run as a detached job
  (`python -m engine.go --step sims|arm`, `logs/start_job.json` + `.log`) because they stop / start the server the page runs
  on; the page polls and reconnects. A failed Sim test is retried with `--write-mode direct` (saved as `write_mode` in `data/start_bot.json`, then passed to every `--start` / `--enable-auto-resume`, console and page alike). Arm: the owner types `I ACCEPT LIVE RISK` in the page (checked by the endpoint, the
  job's `step_arm` and `ninjatrader --start`); the phrase reaches the job in env `LE_START_CONFIRM`, never argv or the log.
  Accounts panel (`go.accounts` / `add_account` / `remove_account` / `set_anchor` / `to_funded`): balance (NinjaTrader
  accounts.csv, else the MFFU anchor, else the plan start), floor, bot, eval / funded, armed; add (name, Builder 50K / 25K,
  Zlarior or ATLAS, start day: first 50K = Zlarior's main in `data/start_bot.json`, ATLAS = account B via
  `account_b.set_account_b`, others = extra Zlarior accounts in `data/accounts.json`, disarmed, allowlisted), change balance /
  floor / as of (`eval_life.set_anchor`), passed -> funded (`eval_life.to_funded`), remove (off the allowlist when unused).
  START BOT's mix-up checks on every write; one account is never both Zlarior's and ATLAS's (`go.role_of`); adds / removes
  / names refused while the bot runs. Pick list of names from `broker_balance.read()` rows + `outgoing\*_<acct>_Position.txt`.
  **Local only:** every POST is in `cloud_guard.CLOUD_BLOCKED` (`START_WRITES`) and checked by `cloud_guard.local_only`
  (client 127.0.0.1 / ::1, no proxy / tunnel header, Host and Origin localhost, not LE_CLOUD): the phone sees the page
  read-only. UI `web_next/js/next/start.js` + `css/start.css` (sw `le-shell-next-v20`). Tests `python -X utf8 -m
  tests.test_start_api` (88 checks, temp files only; phone / Tailscale / tunnel / rebind / origin / cloud refused) +
  `tests.test_go`. Shots `research/handoff/2026-10-26/ui_start/`. Untested on the real PC: the detached job window
  (`cmd /c start`), the server restart during the job, opening NinjaTrader from the page.
  **One button "Start trading" (2026-10-26 PM, owner: "automatic through the dashboard ONLY"):** `POST /api/next/start/go`
  -> job `python -m engine.go --step auto` (`go.step_auto`): update if behind (`go.update` = `autoupdate.pull`; then the
  server restarts and the job re-runs itself `--after-update`), the ATLAS block migration, names (the only owner input,
  once), setup, NinjaTrader opened + its log-in waited for (re-checked every 10 s), live bars waited for (every 15 s, the
  exact chart click shown), the Sim test once (market open), then the start. **No phrase** when `go.resume_problem` is None
  (the auto-resume opt-in is valid for exactly the 50K, the live switch on, the 25K armed): the job asks the server
  (`POST /api/next/start/resume` -> `go.resume_now`), which starts through the auto-resume gate (`autoresume.decide`:
  NINJATRADER_LIVE=1 in the server, no kill / daily loss today, NinjaTrader CONNECTED) with Bot Control's start (autostart
  record saved) and checks the routes (stops the bot when wrong). Otherwise status `need_phrase` shows the phrase box
  (any capitals) and the job runs `step_arm`. Every stop is one plain sentence in the job file (`stage`, `say`, `need`
  names / phrase / market / stop, `retry_s`); the page retries a `retry_s` stop by itself while open (30 tries max, never for
  names / phrase). PC clock row (`status.clock`, `guards.clock_probe` in a thread, every 10 min) + "Sync the clock"
  (`POST /api/next/start/clock` -> `go.sync_clock`: `w32tm /resync`; refused -> the Windows Settings steps; then the bot's
  clock guard probes again). The dashboard opens on Start when the bot is not running (`app.js`, `/api/health/ping`
  bot_running). Tests `tests.test_start_api` (117); shots `python -X utf8 -m tests.shots_start --pc <url>` ->
  `research/handoff/2026-10-26/ui_start_auto/` (sw `le-shell-next-v21`).
  **At PC boot (2026-10-26):** Startup folder (`go.startup_shortcuts`): NinjaTrader + "LE bot server" -> START_DASHBOARD.bat
  (starts run_bot.ps1 when the server is down, waits up to 5 min, opens `/?page=start`); the server's autostart resumes the
  bot through the opt-in (`autoresume.resume_live`, waits 30 min for NinjaTrader CONNECTED; after that "Start trading"
  resumes it without the phrase). NinjaTrader connects by itself only with Connections > Configure > "Connect on startup".
  Desktop: two icons, **LE START** (START_DASHBOARD.bat = the Start page) and **LE STOP BOT**; make_shortcuts.ps1 deletes
  the older LE START BOT / LE UPDATE / LE DASHBOARD / LE HEALTH CHECK (the .bat files stay). The server runs
  `go.ensure_shortcuts` at start (Windows, once per `SHORTCUTS_V`, mark `data/shortcuts.json`), so an update brings the new
  icons and Startup shortcuts without a click. Tests: test_win_scripts (pwsh sandbox: 2 icons, old ones removed),
  test_ops, test_go.
- **Live board (2026-10-26, read-only, both dashboards):** `engine/live_board.py` `build(inp)` turns heartbeat-shaped blocks
  (health, brain, second, acct, crit, live_pub) + accounts / goals / odds into: **Right now** per account (balance, room to
  the floor, $ to go, today, session X of 10, what it waits for = brain stage / each ATLAS member's state, the next entry
  windows as absolute ET times (`next_windows`: weekends, CME full closures, early close = halt - 15 min, EMA no Monday),
  Zlarior's size now from `brain.sizing`, ATLAS's last `account_b.size` else the rule in words, every guard blocking
  entries with a one-line fix: clock / feed / NinjaTrader / startup / kill / stopped / silent / eval / account B), **today's
  map** (brain levels + VIX objective up / down + 18:00 open, points and $ per micro and $ at the size now), **health strip**
  (poll_ms amber above 5 s, last poll, feed 1m / 5m, NinjaTrader, clock drift (red when the guard blocks), last error
  (red only when recent), heartbeat, phone feed), **week and eval** (goals week vs 2-4 / 3-4, session bar 10 / 15, 2-week
  odds from `uprisk_eval.json` at the live switches and `research/second/atlas.json` eval25k, $ a month expected = health
  band H2 usd_eval_per_session x 21 / ATLAS H2 per_month vs the actual pace) and a **trade log** of both accounts (PC
  trades, account-B entry + exit paired and filled from the member's paper trade, paper rows marked). Sources: PC `GET
  /api/next/board` (`engine/board_api.py`, mounted by next_api, cached 4 s, from the running bot via the heartbeat
  helpers); data.json / home.json `board` (`site_block`, build_web_dashboard); live.json `board` (`live_publish.build`,
  every 60 s, ~15 KB, its trades trimmed first by `fit`). UI: shared `boardcore.js` (window.BoardUI, byte-identical in
  `tools/web_public/` and `web_next/js/next/`); PC page `board` ("Live board", Advanced > Accounts; Main stays 6 items) +
  the Command center "Right now" row (`cc.js` `#ccBoard` -> `board.js` fillBoardHome); phone `board.js` (after clean.js:
  wraps Home with the Right now cut, page `#/board`, prefers live.json's newer board), sw `le-public-v37`. Pictures via
  TradePics (bot pictures + exact-match backtest examples), CSV export. Tests `python -X utf8 -m tests.test_live_board`
  (71 checks, incl. a node render); shots `python -X utf8 -m tests.shots_board --fresh --site <built site> --out
  research/handoff/2026-10-26/ui_live` (restores the files the server refreshes).
- **PC paper bot + dashboard:** `server.py` on http://localhost:8766, supervised by `scripts/run_bot.ps1` (Windows; runs only while
  the PC is on). The UI is the ES-module SPA in `web_next/` layered over `web/`, with the API in `engine/dash_*.py` and
  `engine/next_api.py`.
  **Command center (2026-10-25, read-only):** home page `cc` (both accounts LIT 50K / ATLAS 25K, 9 health lights: feed,
  NinjaTrader, clock, STARTUP RECONCILED, allowlist, one-bot lock, heartbeat, kill, loop; what the bot waits for; early
  close / DST / news) plus Goals (reads `/api/next/goals`, falls back when it 404s), Eval timeline, Session calendar,
  Trade log, ATLAS per setup, Runbook, Audit evidence, All features (61 new features). API `engine/pc_cc_api.py`
  (`/api/next/cc/*`, GET only), UI `web_next/js/next/cc.js` + `css/cc.css`, grouped sidebar `routes.js` GROUPS.
  Tests `python -X utf8 -m tests.test_pc_command_center`; shots `tests/shots_pc_cc.py` -> `research/handoff/2026-10-25/ui_pc/`.
  **"Zlarior" (owner 2026-10-25 PM): the display name of the LIT bot only** (like ATLAS for "second"): every key, file,
  config, push kind and route id stays `lit`; "LIT" stays where it names the method ("Zlarior trades the LIT method").
  Phone (`tools/web_public/clean.js` v2): tabs Home · Zlarior · ATLAS · Money · More; the Zlarior tab (group `lit`, page
  `#/lit`) has sections Today (+ 50K eval pages) · Brain · Trades · Plan · Results · Strategy (ZL_SEGS), the ATLAS tab
  Today · Brain · Trades · Setups · Results = the one ATLAS page cut into parts (`#/atlas/<part>`, atlasTag). PC
  (`routes.js` BOTS): sidebar Home · Zlarior · ATLAS · Results · All tools; `zlarior` is a virtual entry that opens its last
  section page (`zlSub`), the ATLAS part sits in `nx.atPart` (shell.js / second.js). Old links (#/trades, #/brain, #/second)
  still open. Push titles say "Zlarior setup armed" (kind `armed` unchanged). Shots `research/handoff/2026-10-25/ui_zlarior/`.
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
- **MNQ feed vs NQ backtest + the NQ signal chart (2026-10-26, `research/writeups/mnq-vs-nq-feed.md`, OFF by default):**
  the PC's MNQ bars, collected from the heartbeat branch's history (`tools/hb_bars.py`: the branch is one force-pushed
  commit, older ones fetched by SHA from GitHub's activity API -> `research/feed/nt_mnq_{5m,1m}.csv.gz`; 5m from 09-17,
  1m from 10-18 = no 1m overlap with NQ_1m.csv) vs NQ1! (`tools/mnq_vs_nq.py`, `research/feed/mnq_vs_nq.json`):
  NinjaTrader MNQ = TradingView MNQ1! on 95.4% of bars (A1's sample is the live feed); MNQ vs NQ within 1 tick on
  54-62%, 1 pt on 92-94%; LIT setups 36% on one feed only (40 sessions Aug 24 - Oct 16), trade days 60% differ, 5m-exec
  net NQ +$2,362 vs MNQ +$367; whole-2026 MNQ-noise study (40 draws, 1m exec): 2026 median $32.8k vs $43.8k, H2 $9.1k vs
  $9.9k (-$229/mo), only ~28% of trades identical; vendor-noise control: no change. Runs `lit_feed_mnq_noise`,
  `lit_feed_mnq_live_5m`, `lit_feed_nq_same_5m`. **Switch `signal_root`** (top level of live_model.json +
  live_model_lit.json, "MNQ"; `LE_SIGNAL_ROOT` / start cfg `nt_feed_roots` override): "NQ" = `NinjaTraderBars` reads an
  NQ chart's LE_BarFeed files (NQ_5m / NQ_1m / NQ_1m_open / NQ_instrument; LE_BarFeed names files by the chart's root, so
  no clash and nothing to untick) for every decision, orders / stops / targets / size stay MNQ. One root per symbol
  (`root_for`: never NQ 5m with MNQ 1m); no NQ file -> MNQ as before; a stale NQ chart blocks (no silent switch). The
  roll guard, `--status`, HEALTH CHECK feed lines, the heartbeat bars follow that chart. Archive caveat: data/nt_bars
  keeps its MNQ bars from before a switch (no shift, ~1 tick; gone from the LIT window within ~2 months). Owner steps:
  SETUP.md 4c. Test `python -X utf8 -m tests.test_signal_root` (22).
- **December roll safety (2026-10-26, `engine/roll_watch.py`, `tests/test_dec_roll.py` 23, `docs/ROLL_DEC_2026.md`):**
  the roll guard (`ninjatrader.contract_problem`, chart month vs order month, root-free) already refused entries
  (`tests.test_nt_roll_guard`); now the chart vs order contract is also: a launch-checklist line `roll` (red after the
  roll day while the chart is old, good when equal or switched the evening before, info a week before / unknown), the
  Start page's "Live bars from NinjaTrader" line (`go.feed_problem` -> "Contract roll: ..." with its own fix), pushes
  (7 days / 1 day before: `ops_checks.roll_notice` keys; "Chart still on MNQ 12-26: no new entries" once a trading day:
  `ops_checks.roll_late_notice` at 01:40 ET, and the cloud monitor `roll_watch.cloud_notices` when the PC's ops tick is
  older than 1 h). The test simulates the roll with a constant 301.25-pt offset (TradingView export + archive old, chart
  switched Wed 17:00): on every session after the switch the LIT window = the adjusted series bar for bar and LIT's
  signals / trades are identical (MNQ and NQ charts).
- **Execution audit (2026-10-25, `research/handoff/2026-10-25/A5_execution.md`, test `tests/test_nt_exec_audit.py`):** kill is
  account-scoped (CLOSEPOSITION + CANCEL by id) unless the action carries `"scope": "global"` (only `LiveBot.kill_switch`,
  the owner's kill -> FLATTENEVERYTHING); the OIF writer refuses FLATTENEVERYTHING / CANCELALLORDERS outside that, a line
  for another account and a CANCEL/CHANGE of a non-`LE` id. A real account also needs the account allowlist
  (`--allow-account`, `data/nt_accounts_allow.json` or `NINJATRADER_ALLOW`). One process per account (`le_locks\<acct>.lock`
  in the NinjaTrader folder, released by `LiveBot.stop`). Startup DISARMED for entries until `guards.startup_problems`
  passes once (guard 0 `startup_reconcile`). Unreadable `ninjatrader_state.json` -> `.corrupt-*`, entries blocked until
  the account is flat (orphan bot orders from the audit log cancelled) or `--confirm-reset`. Order files are published
  with no overwrite (`_publish`); stale `le_outbox` files are deleted at start. Runbook: `.../STARTUP_AND_RECOVERY_RUNBOOK.md`.
- **PC off, free:** `scripts/PC_OFF_OPTIONS.md` (A: TradingView brain + one tap on the phone; B: the PC wakes itself at 07:50 ET,
  trades through NinjaTrader, hibernates at 16:35: `scripts/schedule_pc.ps1`; E: a spare Surface on 24/7: `scripts/setup_dedicated_pc.ps1`;
  paid bridges / VPS only as options C-D). The always-on PC pushes a heartbeat (`engine/heartbeat.py`, branch `heartbeat`,
  on with `LE_HEARTBEAT=1`); the cloud monitor alerts when it goes silent in a session.
- **Heartbeat push made robust (2026-10-26, `tests/test_heartbeat.py` 36 checks, temp bare repos):** the Surface went
  silent 22:38 -> 05:20 ET on 2026-10-25/26 (GitHub activity API of the branch). Cause found: the PC was offline / asleep,
  not the push code: NinjaTrader's own 1m bars (pushed `bars_1m.csv.gz`) have the same hole 22:42 -> 05:17, the only one
  inside a session in 40 days, and the thread resumed on its 5-min rhythm (05:20:08, 05:25:15); live.json stopped too at
  05:27. The 50-min gap 21:13 -> 22:04 the same evening has bars, so the push itself may have hung there. Latent bugs fixed
  anyway: on Windows `subprocess.run(timeout=)` waits forever for the pipes after killing git when git-remote-https / the
  credential manager hang (reproduced in the test) -> `heartbeat.run_cmd` (temp files, process tree killed); no prompts
  (`GIT_TERMINAL_PROMPT=0`, `GCM_INTERACTIVE=never`); the commit is built and pushed from the private scratch dir
  `data/heartbeat_pub.git` (gitignored, like live.json's), so the project's shallow / OneDrive / locked `.git` is never
  written (and ~1,000 loose objects a day no longer pile up in it); `--force-with-lease` on the last pushed commit
  (scratch ref `refs/hb/last`), refused or failed -> `git ls-remote` tip, one retry; only `heartbeat` (`_BRANCH_RE`, main
  is refused); any exception stays inside the beat; watchdog thread (60 s) restarts a dead push thread or a beat hung
  > 10 min (new lock; the hung one exits quietly), notices a frozen process (PC asleep) and pushes at once; after a
  failure the next try in 60 s. `health.hb` (heartbeat + live.json) and `/api/health/ping` "heartbeat.health": last push,
  last error (redacted), fails in a row, restarts, last frozen stretch, console line "[heartbeat] the PC was asleep ...".
  Keep the Surface awake: plugged in, Sleep "Never", lid "Do nothing" (HEALTH CHECK's "Power / sleep" line).
- **Goals + phone features (2026-10-25, read-only):** `engine/goals.py` `build(data)` (pure: data.json blocks accounts / live /
  second / scale / perf -> per account eval progress vs target / floor / 10 sessions, week trades vs 2-4 LIT and 3-4 ATLAS,
  month $ vs the health_band H2 band, ATLAS scorecard 0/20, payout, scale step, news / early-close / clock calendar, plain
  `lines`). data.json + home.json `goals` (build_web_dashboard), PC `/api/next/goals` (`next_api.goals_data` from the bot).
  Phone: `goals.js` (Home Goals card under the Surface line + Today's plan card, `#/goals`), `features.js` (More hub in six
  sections + search, `#/features` 142 features with NEW badges, `#/weekcal`, `#/last10`, `#/lights`, `#/evaltl`,
  `#/atstats`, offline badge, haptics, scroll-to-top); sw.js v30. Tests `tests/test_goals.py`; screenshots
  `python -X utf8 -m tests.shots_goals --site <site>` (research/handoff/2026-10-25/ui_phone). New feature -> add a `feat(...)` line.
- **Road to $10K / Stingray 3LT (2026-10-26, read-only to trading, `engine/money_goal.py`, `tests/test_money_goal.py`):** the
  owner's money goals, part `money` of goals.build. Card: next action (payout ready > passed eval to switch > buy the next
  runnable evals in plan order, 2 at a time, with the price + code > wait), the stack = 9 planned slots (MFFU Builder 50K x1
  Zlarior, MFFU Builder 25K x2 ATLAS (the bot runs ATLAS on one 25K: slot 2 noted), LucidPro 50K x4, FundedNext Rapid Daily
  50K x2) with states not bought / eval / passed / funded / paying from goals._lit_account, data.json accounts (extras /
  funded, `funded.payouts`), account B, then business.json via the scale block (`scale_plan.status` rows now carry `start`);
  $ a month once funded = `research/second/money_goal_rates.json` (H2 2026, to you, live funded sizing: 50K $915, 25K ATLAS
  $517, LucidPro $938, FundedNext $629 = $6,959 for all 9; 2021-25 ref $404), rebuilt by `tools/money_goal_rates.py` from
  uprisk_wincap / atlas_funded / funded_combo t15_be_off (test checks the file = the sources). Then **"My goals" at the
  bottom**: $10K month by Feb 2027 (bar jobs / Kalshi / prop payouts to you this month, + the plan line), 2024 Stingray 3LT
  before he turns 19 (2027-02-22: target $38,000 = 40% of ~$78K + $7K cushion, stretch marker $46,000, days left, $ a week
  needed, on pace / behind by $X at the current pace = the savings slope since the $20,000 start of 2026-10-26, needs two
  balances 7+ days apart), C8 Z06 bar ($60,000, no date). Owner figures: gitignored `data/goals_money.json` (savings
  history, month jobs / Kalshi, every target / date / name editable, `publish`), written only by the PC Goals page form
  (`engine/money_api.py` GET/POST `/api/next/money`, POST in `cloud_guard.MONEY_WRITES` / CLOUD_BLOCKED + `local_only`).
  Heartbeat `money` (heartbeat_block; publish off = targets only) -> cloud state pc.money -> data.json / home.json
  goals.money; live.json `money` (`money_goal.from_heartbeat`, ~7 KB, dropped first by `fit`). UI `moneycore.js` (MoneyUI,
  byte-identical phone / PC): phone goals.js v3 (#/goals bottom; the old Goals card on Full overview), PC `money.js` from
  cc.js Goals (form only when local); sw le-public-v39. The public dashboard site shows the figures only while publish is on (default OFF since 2026-10-26: the site is public; the owner switches it on in the PC form).
  Shots research/handoff/2026-10-26/ui_money_goal/.
- **Phone live feed (2026-10-21, `engine/live_publish.py`, `tools/web_public/live.js`, `tests/test_live_publish.py`):** the PC
  force-pushes one `live.json` (verdict, PC account / eval / position, feed ages, health, check-in time) to branch `live` of the
  PUBLIC Pages repo `nq-dashboard` every 60 s while the bot runs (5 min otherwise; orphan commit, scratch git dir
  `data/live_pub.git`, never main = no Pages build). The phone polls it every 30-60 s via api.github.com (raw fallback) and lays
  it over data.json. No extra Actions minutes. Auto-update also checks hourly outside trading time (weekdays 16:00-01:20 ET,
  weekends) when flat, nothing armed and a restart is safe (`engine/autoupdate.py` mode `hourly`).
- **Poll speed diagnostics (2026-10-26, `engine/poll_timing.py`, read-only):** the Surface polled in ~32,300 ms every poll
  (heartbeat 2026-10-25) against ~0.8 s here. server.py installs a stage timer (LE_POLL_TIMING=0 = off) that wraps
  LiveBot's stage methods and the few module functions poll_once calls, so `engine/live.py` stays byte-identical (the PC's
  hand-patched copy must keep fast-forwarding). Each poll -> `bot.health["poll_stages"]` (total / CPU / waiting, every
  stage in order with nested "a > b", other threads' CPU during the poll via psutil) -> heartbeat `health.poll.stages`
  (`accounts.poll_stages_block`) -> Home "Bot loop" light (`pc_cc_api.poll_line`) and the Start page's Bot loop card.
  Findings here: the 20,000-row MNQ_1m.csv parse is 56 ms (`engine="python"`; the C engine gives the same frame in 41 ms:
  not the cause, left alone); a busy background thread slows a poll ~1.5x (GIL), not 30x; NinjaTrader's `outgoing`
  holds one file per order and `connections()` opened every one of them twice a poll per adapter (604 reads with 300 orders;
  every open on the PC passes OneDrive's sync filter) -> now read only when size / time changed (`_CONN_SEEN`, shared by
  every adapter: 2 reads a poll). The constant ~32 s (= ~2 s of work + one 30 s wait?) is still unproven: the first
  heartbeat with `health.poll.stages` names the stage (wall >> CPU = waiting on disk / network / a lock). Tests
  `tests.test_poll_timing` (15; `--full` also replays test_lit_live's LiveBot with and without the timer).
- **Poll speed fix (2026-10-26, `engine/bg_worker.py`, `tests/test_poll_speed.py`):** measured cause = the GIL: the paper
  work the bot ran in threads after routing (second.run ~0.8 s + ATLAS v2 `pc_step` ~2.4 s a minute, pictures ~0.5 s each,
  here) overlapped the next poll; its LIT part (poll start -> routed, new `health.lit_ms`, heartbeat `health.poll.lit_ms`,
  Bot loop line) went 0.57 s -> 2.5 s median / 5 s p90 (1 core: 1.4 / 3.5 s), lit_live.run wall 0.49 -> 3.6 s at the
  same CPU. Now: (1) that work runs in ONE child process `python -m engine.bg_worker` at BELOW_NORMAL priority (nice 10):
  jobs "second" (second.run + stop-hunt candidates + `atlas_v2.pc_step`) and "charts" (`PcCharts.draw`), length-prefixed
  pickles on stdin / stdout, bars sent as deltas (`frame_packet`: exact prefix check, last 2,000 rows; the 5-year history
  goes once), args pickled at submit, one job per kind (busy = skip), results set `bot.second` / `bot.atlas_v2` /
  `_charts_drawn` from a receiver thread; pictures only sent when `trade_chart.pending` (keep only for a stale LIT
  picture). Dies / hangs (600 s) -> callback error + restart (20 s gap); 3 deaths in a row or `LE_BG_WORKER=0` -> the old
  threads. Child watches the parent pid, imports no adapter module. Account B and the routed second strategies stay in
  the loop (they route); B's `second.run` no longer waits on second.py's `_LOCK` held by the paper thread. (2) news / VIX
  downloads (15-30 s timeouts, every 15-30 min, before routing) -> `news.background_refresh(True)` (real bot only: stale
  copy served, one refresh thread; the archive is rewritten only when changed so `historical_events` keeps its parse).
  (3) the ES learning merge (5-year frame, every 5 min, before routing) -> refreshed after the state save. (4)
  `data._tag` one strftime per day, not per bar (12x, identical): lit_live.run 0.46 -> 0.32 s. (5) dashboard: board /
  goals 250 -> 20 ms (`second.backtest` memo 300 s, `hub_data.business_raw` cached by file stats). Result here (4 cores,
  back-to-back polls): LIT path 0.41 s off / 0.40-0.53 s on (was 2.5 s); 1 core 0.43 s (was 1.37 s). Identity: test_lit_live
  120/120 + bot 2/2, account_b --quick 45/45, worker == threads (orders, second run, ATLAS v2 state, PNG bytes). Next win
  (not done, feed code owned elsewhere): `lit_live.feed_1m` iterates all 10k 5m groups in pandas (~130 ms a poll).
- **Updates never blocked by the PC's own files (2026-10-26):** ATLAS's account (the account_b block) lives in the
  gitignored `data/account_b.json`; `second_model.json` ships `"account_b": null` and is never written for it
  (`account_b.raw_cfg`: local first, else the tracked block; `set_account_b` / `arm_b` / launch prep / the Start page write
  the local file). `account_b.migrate_local` moves an older version's block out of the tracked file (local written and read
  back first, then `git checkout HEAD -- second_model.json`); run at server start, START BOT, and before every update's
  dirty check. Every update path is `autoupdate.fast_forward` (auto-update, phone "update", UPDATE.bat and START BOT via
  `python -m engine.autoupdate --pull`, the Start page): bot-made files and files checked out from main by hand
  (`from_main`: their blob came in with HEAD..main) go back to HEAD first, a shallow history is deepened (`is_ancestor`:
  `--deepen=300`, then `--unshallow`; the Surface said "refusing to merge unrelated histories" 2026-10-25), a refused
  `merge --ff-only` to a proven descendant is `reset --keep`; a rollback puts hand-checked-out files back. Any other local
  edit still blocks. A server older than the checkout (`go.server_stale`, `/api/next/start/boot`) is restarted before the
  bot starts. Tests `tests.test_account_b_local` (migration + same ATLAS / LIT routes), `tests.test_autorun` (the Surface case
  on real temp repos).
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
- **Real balance from NinjaTrader (2026-10-25, `engine/broker_balance.py`, `tests/test_broker_balance.py`):** LE_BarFeed
  also writes `le_feed\accounts.csv` (name,time,cash,realized,unrealized,netliq; once a minute + on account updates;
  C# UNTESTED on a real install, steps in `ninjatrader/SETUP.md` 4b). Fresh (< 3 min), sane, non-Sim row of the
  account -> (a) day-close auto-anchor: balance = real cash, floor = max(prev floor, EOD - MLL) locked at start+$100,
  stored in `data/broker_balance.json` (gitignored) and fed to `newest_anchor` (LiveBot / account B / extra accounts,
  each by its own NinjaTrader Name); (b) room = min(ledger room, real equity - floor) in `eval_state` / `eval_room`;
  (c) > $50 apart for 5 min -> one "balance differs" push a day; (d) missing / stale -> identical to before. Switch
  `"broker_balance"` (start cfg or lit_sizing): unset = on for the real bot only. Bot Brain step "Real balance", launch
  checklist line "Real balance from NinjaTrader" (green when fresh, else info). `python -m engine.broker_balance`.

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
     `city.js` month city; 2026-10-29: `space.js` deep-space background, the default, see Infrastructure). Build with `cd tools/web_public/fx && npm install && npm run build`: it writes the one bundle
     `tools/web_public/fx.js`, copies it to `web_next/js/fx.js` and stamps its hash into both import URLs (commit all of it). Lazy-loaded after first paint; Settings has
     Max / Lite / Off; off or no WebGL2 leaves the 2D page. `fx/dev.html?view=orb|galaxy|city|candles` is a test harness;
     add `?fxfixed` to a page URL to stop the auto resolution drop in screenshots. PC side: `web_next/js/next/fx3d.js`.
3. Pine port done 2026-10-17 (see TradingView above). Open: compile check on TradingView (6 constructs listed in BRIDGE_SETUP.md), optionally read signals from NQ1! so both feeds agree.
4. Optional: test "smaller size when inducement was taken first" when more data exists.
5. **Before the Dec 2026 roll:** the live LIT window mixes the TradingView file with NinjaTrader MNQ bars. Since no_yahoo every
   merge checks the overlap (`pcbars.merge_basis`): a constant offset (a roll) back-adjusts the older bars; same contract = no
   shift. Untested on a real roll: the chart switch to MNQ 03-27 must leave an overlap (load 30 days). See `lit-report-tests.md` audit. The cloud paper ledger now freezes finished trades (`tests/test_ledger_freeze.py`).
   2026-10-26: simulated December roll (`tests/test_dec_roll.py`), reminders + red lines (`engine/roll_watch.py`); owner
   steps (3) at the top of `docs/ROLL_DEC_2026.md`.
6. **NQ signal chart** (`signal_root`, built, OFF): recommended in `research/writeups/mnq-vs-nq-feed.md`; needs the
   owner's NQ 12-26 chart with LE_BarFeed (SETUP.md 4c). Untested: NinjaTrader NQ vs TradingView NQ1! (expected ~equal,
   as NinjaTrader MNQ = TradingView MNQ1! on 95% of bars), whether the MFFU connection carries NQ data.
