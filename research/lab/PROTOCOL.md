# Strategy Lab protocol: build a solid 2026 strategy by Sunday 2026-10-18 18:00 ET

**Owner's brief:** one strategy with plain fixed rules. About **2–5 setups a week**, **profitable through 2026**, built only from
concepts the bot already uses:
- liquidity pools and sweeps (prior day/week H/L, Asia/London/overnight H/L, 1H/15m swings, equal highs/lows)
- IFVG / CISD triggers, killzones, draw on liquidity
- HTF/MTF bias and dealing range (premium/discount), AMT value area / VWAP
- PO3 / sessions, SMT vs ES, Quarterly Theory

Consistency in 2025 or earlier is **not** required.

## Fixed protocol (tools/strategy_lab.py; never edit it to make a candidate look better)
| period | dates | use |
|---|---|---|
| dev | 2026-01-02 .. 2026-06-30 | build and tune here, as often as you like |
| confirm | 2026-07-01 .. 2026-10-16 | final check. **At most 3 confirm runs per track**; each one is logged in `research/lab/confirm_log.csv`. Don't tune on it. |
| ytd | 2026-01-02 .. 2026-10-16 | headline number for the owner |

**Gate (must hold on dev AND confirm):**
- net > 0
- profit factor >= 1.3
- 2.0–5.0 trades a week
- max drawdown under $2,000 (the eval's trailing max loss)
- rolling MFFU 50K pass rate at least 10 points above the zero-edge baseline

**Prefer:**
- few rules
- no losing quarter
- most weeks inside 2–5 trades
- low worst-day loss

**Costs and sizing (rule modules):**
- MNQ at $2 a point
- $1.40 round-trip commission per micro
- 1 tick of slippage on market and stop fills
- fixed $350 risk per trade, max 40 micros, no grade sizing

The Liquidity Engine applies its own, equivalent costs.

**No lookahead:** decide on closed 5m bars only. The entry is the signal bar's close (or a later bar). Same-bar stop/target ambiguity: assume the stop fills first.

## Plug-in interface for a new rule module (so it can go live Sunday)
File `tools/lab_models/<name>.py`:
```python
NAME = "short_name"
PARAMS = {...}                 # defaults = the final rules
def run(bars5, params=None, es5=None):
    """Causal simulation over bars5 (DataFrame from strategy_lab.bars(..., warmup_days=...)).
    Returns a list of trades built with strategy_lab.make_trade(...). An unfinished last trade has exit_kind='open'."""
def state(bars5, params=None, es5=None):
    """Optional: dict for the dashboard (bias, key levels, armed setup, what it's waiting for)."""
```
- Score it with `strategy_lab.score(trades, "<TRACK>_<name>", "dev")`.
- Write the rules as plain English in `research/lab/<TRACK>_RULES.md` (5–12 numbered rules a trader could follow by hand, and that can be ported to Pine).

## House rules for the parallel sessions
- Only write your own files: `tools/lab_models/<yours>.py`, `tools/lab_<track>_*.py`, `research/lab/<TRACK>_*`.
- `tools/strategy_lab.py` and this file are shared and **read-only**. If you need a change, message the lead session.
- **No git commands** (the lead commits). Don't touch `server.py`, `engine/**` (Track A may read engine code and pass params only), `web/**`, `data/**`.
- **Memory is tight** (about 1.8 GB free): use at most 4 worker processes.
- **Never** restart the running server on :8766, arm anything live, or use CFD data (`data/_cfd_archive`, Dukascopy).
- **Deadline: Saturday 2026-10-17 12:00 ET.** Deliver your best 1–2 candidates with dev + confirm scorecards, the rules file, and a short honest note. "Nothing clears the gate" is an acceptable answer; a fitted one isn't.
