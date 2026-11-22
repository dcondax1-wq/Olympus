# NQ Liquidity Engine: one-page brief (loaded every message: keep it short)

Owner trades MFFU evals (Zlarior = LIT on the Builder 50K, ATLAS on a 25K; BLITZ hidden, paper). Not a coder, writes from a phone.
**Reply:** one short table (what / result), plain words, $ not just R, then at most 3 numbered steps with one copy-paste line.
Do the work instead of asking; be honest when something doesn't work. Fix what you find as you go, unasked (owner 2026-11-19); bring him only
live-money / strategy yes-no and hands-only steps (his to-do = STATE.md 'Waiting on the owner', max 5). **Start every chat with `python tools/board.py read` (live accounts, events, owner notes), then read `STATE.md`** (what's live,
what's waiting, what's next) and update it at the end. Full detail: `docs/CLAUDE_REFERENCE.md` (read the section before touching
an area; the old long brief is its last section).

## Hard rules
- **Paper only for Claude:** never arm live, never place real orders; the owner types the live phrase himself.
- **No secrets** in repo or chat. **No paid services.** Treat the owner's name/email/account ids as private.
- **Futures data only** (TradingView NQ1!/ES1! exports in `data/`, NinjaTrader bars); never Yahoo, never CFD.
- **Strategy changes** only with proof: LIT picked on 2026 Jan-Jun, checked on Jul-Oct (both better); others both 2026 halves
  and 2021-25; 2-4 trades/week; costs in; report trades/week, PF, net $, $/month, max DD, eval pass/fail speed. Check
  "Tested and rejected" first. Change `live_model.json` + `live_model_lit.json` together, then `python tools/lit_losses.py live`
  and `python tools/model_versions.py`. Owner-approved sizing: eval two_week room_f 0.4 kept to session 80.
- **Stops** 1 tick beyond the sweep extreme, size follows the stop; one target (VIX band, banked at 8R).
- Prop prices: owner's real prices (Builder 50K $91.80, 25K $63 / $43), never list prices.
- Olympus look (owner 2026-11-20, liked the Jarvis switcher sheet): "OLYMPUS NIGHT" = black #000, cards #16131e, violet outlines #3e255e/#4d2e76 + glow #9d59ee, bright gold ACCENTS #f1c14b, mint #77db89; never brown/olive/marble cards. 3D + effects on dashboards.
- MFFU sim-funded accounts START AT $0: MFFU shows profit as the balance (ATLAS funded "$401", not $25,401); show them that way. Every account's rules: `docs/ACCOUNT_RULES.md` (source `research/lit/mffu_rules.json`). First payout goal = the max request ($1,000 on a 25K at $2,100), only 5 sim payouts.
- Helpers never edit `sw.js`, `tools/build_web_dashboard.py`, `jarvis/apps.js`, the `olympus.js` APPS table; the lead wires.

## Saving usage (owner 2026-11-15)
- At most 2-3 helpers, only for real work; cheaper models for mechanical jobs; never re-run a huge finished helper.
- Run only the touched area's tests: `python tests/smoke.py` first (2 min), then `python tests/run_area.py <area>`.
  Browser suites only when screens changed; run_area takes the browser lock itself (landing: `run_area.py <area> --changed <base>`). Never run test_win_scripts.
- Ship with one command: `python tools/ship.py` (tests touched areas, pushes Olympus pc only, optional zip).
- Free disk weekly: `python tools/disk_clean.py` (dry run first).

## Where things are
- Live strategy LIT: `engine/lit.py`, `engine/lit_live.py`, `STRATEGY.md`. PC bot: `server.py` + `engine/live.py` -> NinjaTrader
  via `engine/ninjatrader.py`. ATLAS: `engine/second.py`, `engine/account_b.py`. Apps: `tools/web_public/<id>/` (map: `docs/OLYMPUS_MAP.md`).
- Home (owner 2026-11-20): **`dcondax1-wq/Olympus` branch `pc`** is the one main repo. Commit and push only there (`git push
  origin HEAD:pc`, or `python tools/ship.py`); the PC updates itself from it (`docs/AUTO_UPDATE.md`). Never use the old
  `demetrades2000-coder/nq-liquidity-engine` repo or its `claude/clever-heisenberg-51zwcr` branch.
- Key checks: `python -X utf8 -m tests.test_lit_live` (live loop = backtest), `python -m engine.ninjatrader --selftest`.
