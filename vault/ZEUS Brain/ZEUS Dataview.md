---
tags:
  - zeus/hub
  - zeus/dataview
type: "hub"
---

# ZEUS Dataview

> [!info] Only for the Dataview plugin
> Every note has front matter (type, bot, date, pnl, cause, week ...). With the free Dataview community plugin on, these tables fill themselves. Without it, use the hub notes: [[ZEUS Trades]], [[ZEUS Weeks]], [[ZEUS Lessons]].

## Live and paper trades

```dataview
TABLE date, time, bot, src, exit, r, pnl, cause
FROM "ZEUS Brain/Trades"
WHERE src != "backtest"
SORT date DESC, time DESC
```

## Losers by reason code

```dataview
TABLE length(rows) AS losers, sum(rows.pnl) AS dollars
FROM "ZEUS Brain/Trades"
WHERE result = "loss"
GROUP BY cause
SORT sum(rows.pnl) ASC
```

## Each bot by week

```dataview
TABLE sum(rows.pnl) AS dollars, length(rows) AS trades
FROM "ZEUS Brain/Trades"
GROUP BY week + " " + bot AS wb
SORT wb DESC
LIMIT 40
```

## Open Decide cards

```dataview
TABLE usd_month AS "$ a month", recommend, added
FROM "ZEUS Brain/Decide"
WHERE status = "open"
```

## Weeks

```dataview
TABLE trades, pnl
FROM "ZEUS Brain/Weeks"
SORT week DESC
```

## Research rejected lately

```dataview
TABLE date, status
FROM "ZEUS Brain/Research"
WHERE contains(file.tags, "verdict/rejected")
SORT date DESC
LIMIT 25
```

_Inside the PC vault the folder is OLYMPUS/ZEUS Brain: change the FROM lines there if a table stays empty._

Back to [[ZEUS Home]]
