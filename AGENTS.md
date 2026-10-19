# Rules for any AI coding agent (ChatGPT / Codex and others)

Read `CLAUDE.md` first: it is the project brief and its **Hard rules** apply to every agent, not only Claude.

The short version:
- **Paper only.** Never arm live trading, never place orders, never set `NINJATRADER_LIVE` or use the live confirm phrase.
  The owner switches the real account on himself.
- **LIT is the strategy** (`engine/lit.py`, `live_model.json`, `STRATEGY.md`). Don't change live trading or sizing settings
  in `live_model.json` / `live_model_lit.json` unless the owner asks and the change passes the LIT rule: better in both
  Jan-Jun 2026 and Jul-Oct 2026 (net $ and the MFFU 2-week pass rate), 2-4 trades a week.
- **Futures data only** (TradingView NQ1!/ES1! exports in `data/`, NinjaTrader live bars). No Yahoo, no CFDs.
- **No secrets** in the repo or in chat.
- **Work on your own branch and open a pull request into `main`.** Never push to `main`, and never to a `claude/...` branch
  (Claude works there; two agents on one branch overwrite each other).
- Before opening a PR run: `python -m engine.ninjatrader --selftest` (55/55), `python -X utf8 -m engine.sizing`,
  `python -X utf8 -m tests.test_lit_live --days --bot` (120/120), and the tests for what you touched (`tests/`).
- Never commit `cache/dash/*`, `data/VIX_1d.csv`, `data/VXN_1d.csv`.
- Good, safe jobs: dashboard pages (`tools/web_public/`, `web_next/`), docs, research tools that only read files
  (`tools/`, `research/`), new tests.
