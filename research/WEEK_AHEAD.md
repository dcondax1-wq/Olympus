# Week-ahead risk brief: Mon 19 Oct to Fri 30 Oct 2026

_Generated 2026-10-16 15:06 ET by `python -m engine.calendar_week --write`. All times are New York time (ET)._

## How the bot handles news

- No new entries from 15 minutes before to 30 minutes after any high-impact US release. An open trade is closed 5 minutes before the release.
- On FOMC days there are no entries after 13:00 ET, so the afternoon killzone is off.
- The bot only enters inside the killzones (09:30-11:30 and 13:30-15:30 ET). An 08:30 release's blackout (08:15-09:00) ends before the morning killzone opens, so it does not stop the bot trading the open. It does shape the open: the 08:30 move sets the overnight levels that get swept.
- 10:00 releases (ISM, JOLTS, Conference Board) fall inside the morning killzone: entries pause 09:45-10:30.
- In the backtests, news days were not where the strategy lost money. The losing stretches came from trending regimes. The blackout is a safety net, not an edge, so sitting out whole days costs trade count (the target is 1-4 trades a week).

## Clock changes

- **Sun 25 Oct**: UK and EU clocks go back. For Oct 26-30, European data and the London open come one hour later in ET than usual.
- **Sun 1 Nov**: US daylight saving ends (EDT to EST). Release times, killzones and the 18:00 ET Globex open stay the same in ET. TradingView (America/New_York) and the Python bot (zoneinfo) both follow ET wall-clock time automatically. Any tool that runs on UTC moves one hour that night.

## Week of Mon 19 Oct

### Mon 19 Oct: risk LOW

- No scheduled medium or high-impact US releases.
- Note: Fed speaker blackout in force (no Fed chair/governor remarks expected until after Oct 28).

**Action:** NORMAL.

### Tue 20 Oct: risk LOW

- No scheduled medium or high-impact US releases.

**Action:** NORMAL.

### Wed 21 Oct: risk LOW

- No scheduled medium or high-impact US releases.

**Action:** NORMAL.

### Thu 22 Oct: risk LOW

- 08:30 Unemployment Claims (medium) _(confidence: inferred)_

**Action:** NORMAL.

### Fri 23 Oct: risk LOW

- 09:45 S&P Global Flash PMIs (medium) _(confidence: inferred)_
- 10:00 UMich Consumer Sentiment (final Oct) (medium) _(confidence: inferred)_

**Action:** NORMAL.

## Week of Mon 26 Oct

### Mon 26 Oct: risk LOW

- No scheduled medium or high-impact US releases.
- Note: UK/EU clocks went back Sun Oct 25: London data and the London open are one hour later in ET this week.

**Action:** NORMAL.

### Tue 27 Oct: risk ELEVATED

- 08:30 Durable Goods Orders (medium)
- 10:00 CB Consumer Confidence (**HIGH**) | blackout 09:45-10:30, flatten 09:55 | hits: NY AM killzone 09:30-11:30 _(confidence: inferred)_
- 10:00 New Home Sales (medium)

**Action:** NORMAL. The bot pauses entries 09:45-10:30 for the 10:00 release, inside the AM killzone.

### Wed 28 Oct: risk HIGH

- 14:00 FOMC rate decision (**HIGH**) | blackout 13:45-14:30, flatten 13:55 | hits: NY PM killzone 13:30-15:30
- 14:30 FOMC press conference (**HIGH**) | blackout 14:15-15:00, flatten 14:25 | hits: NY PM killzone 13:30-15:30
- Note: Mega-cap earnings cluster this week (MSFT/GOOGL/META/AAPL/AMZN typically report the last week of October, after the close): overnight gaps possible. Dates not confirmed here.

**Action:** NO PM SESSION. This is automatic: no entries after 13:00 ET, and any open trade is closed by 13:55. The AM session runs as normal, but pre-FOMC mornings are often range-bound. Half size is reasonable.

### Thu 29 Oct: risk ELEVATED

- 08:30 GDP Q3 advance estimate (**HIGH**) | blackout 08:15-09:00, flatten 08:25 | hits: no killzone
- 08:30 Personal Income & Outlays / Core PCE (Sep) (**HIGH**) | blackout 08:15-09:00, flatten 08:25 | hits: no killzone
- 08:30 Unemployment Claims (medium) _(confidence: inferred)_

**Action:** NORMAL. The 08:30 print sets up the first sweep at the open. The bot's blackout ends at 09:00.

### Fri 30 Oct: risk LOW

- 08:30 Employment Cost Index Q3 (medium)

**Action:** NORMAL.

## Look-ahead: 31 Oct to 08 Nov (high impact only; the next run's Pine string will include these)

- Mon 2026-11-02 10:00 ISM Manufacturing PMI _(confidence: official-search)_ | hits: NY AM killzone 09:30-11:30
- Tue 2026-11-03 10:00 JOLTS Job Openings (Sep) | hits: NY AM killzone 09:30-11:30
- Wed 2026-11-04 08:15 ADP Non-Farm Employment (Oct) _(confidence: inferred)_
- Wed 2026-11-04 10:00 ISM Services PMI _(confidence: official-search)_ | hits: NY AM killzone 09:30-11:30
- Fri 2026-11-06 08:30 Non-Farm Payrolls (jobs report)
- Note: First session on EST (US clocks went back Sun Nov 1). CME still opens 18:00 ET; killzones unchanged in ET. (2026-11-02)
- Note: US midterm elections: results arrive overnight into Wed Nov 4 (no scheduled time). (2026-11-03)
- Note: Post-election session: overnight gap / trend risk from the results, plus ADP and ISM Services. (2026-11-04)

## Not confirmed from the publisher's own page

- 2026-10-27 10:00 CB Consumer Confidence (inferred, conference-board.org)
- 2026-11-02 10:00 ISM Manufacturing PMI (official-search, ismworld.org)
- 2026-11-04 08:15 ADP Non-Farm Employment (Oct) (inferred, adp.com)
- 2026-11-04 10:00 ISM Services PMI (official-search, ismworld.org)
- Fed speeches: neither the Fed's October nor its November calendar lists any speeches. Fed speakers are in their pre-FOMC blackout from Oct 17 to Oct 29. A chair speech added later appears on the Forex Factory feed the week it happens. Re-run this command on Sunday.
- Weekly jobless claims are medium-impact on Forex Factory, so they get no blackout.

## Weekly routine

1. Sunday afternoon: `python -m engine.calendar_week --weeks 2 --write` (pulls the new Forex Factory week).
2. Paste the block from `tradingview/blackouts.txt` into the Pine strategy's blackout input.
3. Read this file and note any day marked HIGH.
