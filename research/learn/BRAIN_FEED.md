# BRAIN FEED: the two files the Brain app reads (shape v1, 2026-11-24)

Written by `engine/market_learn.nightly` (called by `tools/market_learn_weekly.py`, both the weekly run and `--nightly`).
Research and reporting only: nothing in them changes a live rule. A fix only goes live after the owner says yes on the Decide
card AND Claude runs the full CLAUDE.md proof.

Refresh:
- cloud / any checkout: `python -X utf8 tools/market_learn_weekly.py --nightly` (< 2 min, ~6 s today, no numba, no backtest)
- the PC (keeps its git tree clean for auto-update): `python -X utf8 tools/market_learn_weekly.py --nightly --out logs/learning`
- Sunday weekly (cloud): `python -X utf8 tools/market_learn_weekly.py` (rebuilds the backtests, tests <= 2 pre-registered fixes
  a pillar, then refreshes these two files too)

## research/learn/journal.json = a dated list (oldest first, max 400 entries)
```json
[{"date": "2026-11-24", "pillar": "lit|atlas|blitz|orderflow|market", "lens": "structure|context|fix test|structure test|expansion|retracement",
  "noticed": "plain words: what it noticed, with the numbers",
  "evidence": {"n": 297, "usd": -13997, "z": -2.1, "...": "optional extra keys (p, pf_h2, avg_r, lift)"},
  "status": "watching|confirmed|rejected|adopted-needs-owner-yes",
  "key": "stable id (lesson|lit|st_pos=chase, trial|..., variant|..., market|...)",
  "was": "previous status (only on a status-change entry)", "checked": "last day the same status was re-confirmed"}]
```
Statuses:
- **watching**: the same side in all 3 spans (Jan-Jun 2026, Jul-Oct 2026, 2021-25) but weak (|z| 1-2), or a market base rate
  that is not the same in every span, or a fix registered and not yet tested.
- **confirmed**: same side in all 3 spans and strong (|z| >= 2); for `market`, the base rate holds in all 3 spans.
- **rejected**: a fix / variant that failed its pre-registered test, or a lesson that FADED (no longer the same side in all 3).
- **adopted-needs-owner-yes**: passed every gate; it is on the Decide card. Nothing changes until the owner says yes.
How it learns over time: a NEW key adds a dated line; a status CHANGE adds a new dated line with `was`; the same status only
refreshes `evidence` + `checked` (no new line). So "what did it learn this week" = entries with `date` in the week.

## research/learn/brain_state.json = one object
```json
{"v": 1, "kind": "brain-state", "built": "2026-11-24 15:42 UTC", "paper_only": true, "added_today": 31,
 "market": {"regime": "trend", "regime_er5": 0.96, "vix": 26.6, "vix_band": "VIX 25+", "prior_day": "big", "as_of": "2026-11-20",
            "session": "2026-11-20", "bar_et": "2026-11-20 16:55", "price": 25288.25,
            "range_used_atr": 1.62, "pos_in_range_pct": 19,
            "phase": "shallow pullback of the down leg (0.20)", "retrace_depth": 0.204,
            "continuation_odds_pct": 80.3, "continuation_note": "history: ... new down extreme 80.3% of the time",
            "last_swing": {"dir": "down", "size_atr": 1.52, "expansion": true, "from": 26504.75, "to": 24976.0},
            "words": "one plain line for the header"},
 "pillars": {"lit|atlas|blitz|orderflow|market": {
     "name": "LIT (Zlarior)", "confidence": 70, "lessons": 0, "watching": 1, "rejected": 3, "needs_owner_yes": 0,
     "last_learned": {"date": "2026-11-24", "what": "plain words", "status": "rejected"},
     "testing_next": "plain words: the next pre-registered fix, or the strongest 'watching' lesson",
     "market_read": "plain words: how this pillar did in today's regime + VIX band", "trades": 631}}}
```
- `confidence` (0-100) for LIT / ATLAS / BLITZ / ORDER FLOW = 30 x sample (2026 trades / 100, max 1) + 40 x edge still holding
  (Jul-Oct PF: 1.0 -> 0, 2.0+ -> full) + 30 x learning quality (confirmed / (confirmed + rejected); 0.5 when nothing judged yet).
  No trades = 0. For `market` = the share of its base rates confirmed in all 3 spans.
- `lessons` = journal keys whose latest status is confirmed. `phase` words: shallow pullback (< 0.382) / retracing (0.382-0.79)
  / deep retrace (0.79-1.0) / fully retraced = reversal (>= 1.0) / expanding (the move off the last swing point >= 0.75 ATR).
- Structure rules (zigzag 0.3 ATR, expansion leg >= 0.75 ATR, ATR = prior 14 sessions): `research/structure/study.py`.
