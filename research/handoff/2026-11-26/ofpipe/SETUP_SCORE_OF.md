# Order flow -> the LIVE SETUP SCORE (for big-setupscore), big-ofpipe 2026-11-26

One input field per LIT setup: OF1's read at the setup's sweep extreme (research/orderflow/PREREG_ticks.md constants: 8 ticks,
delta INTO the extreme >= 20% of the zone volume = absorbed; >= 50 lots in the zone or "not tested yet"). Read only, paper.

## Live (stdlib only, cheap: reads the tail of the live LE_TickRec file)
```python
from engine import oflive
f = oflive.setup_of(setup)          # setup = the Brain's setup row: {"side": "LONG"|"SHORT", "plan": {"stop": <price>}}
# -> {"of1": "absorbed" | "not absorbed" | "not tested yet" | None,
#     "of_vz": lots in the zone, "of_dz": buy - sell in the zone, "of_d15": 15-min delta, "of_age_s": tick-file age, "of_level": price}
```
`of1 None` = no live tick file / older than 15 min / no stop: score it as **no OF read** (neutral), never as a "no".
The level = the plan's stop + 1 tick toward the trade (the stop sits 1 tick beyond the sweep extreme).

## History (to backtest the score on the pulled real days)
```python
oflive.setup_of_hist(day, t_entry, d, stop)   # from logs/datapipe/days/<day>/of (engine/ofsum summary): {"of1", "of_vz", "of_dz", "of_d15"}
```
Cloud copies of the days: data/pc_days/<day>/of (pass root= the folder above `logs/` or symlink).

## What the evidence says (do not overweight)
- Pre-registered tests: research/orderflow/DESIGN.md OF1 (LIT only when absorbed), first real look = tools/of_realday_verdict.py
  -> research/orderflow/real_verdict.json "of1_decider". Until that says PASS, give `of1` **zero weight** in any live score
  (show it, do not score it), or the score is a new untested filter.
- Literature (research/orderflow/LITERATURE.md): sweep context is the only directional OF idea that fits a 5-minute clock; effect
  sizes are small; LIT's 2-4 trades a week need ~1 year for a +20-point win-rate gap to show.
