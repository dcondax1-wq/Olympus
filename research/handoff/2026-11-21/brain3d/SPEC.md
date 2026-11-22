# Bot Brains in 3D - spec (owner 2026-11-20 19:50 ET)

Owner: "a brain for each bot, a cool way to see them, a 3D brain, very 3D, very high quality, lots of effects. The brain describes
everything that's going on: the steps in order for a trade, and figure out tons more to add, for Zlarior and ATLAS."

## Where
NQ Bot arena -> a "Brain" tab (nq/brain.html), one brain per bot: Zlarior (LIT) and ATLAS (EMA / MACD / S/R). Also reachable from Jarvis
("show me Zlarior's brain"). OLYMPUS NIGHT look (black, violet glow #9d59ee, lavender, small gold accents, mint / red for $ only).

## The 3D brain (three.js, lazy-loaded, phone-first)
- A translucent glass brain with glowing regions = the stages of a trade, in order. Synapse particles flow along the path from stage to
  stage. The CURRENT stage pulses; passed stages glow mint, waiting stages lavender, blocked stages red with the reason.
- Slow auto-orbit, swipe to rotate, pinch to zoom, tap a region -> a glass card: "what I'm doing now / why / what would change my mind".
- Bloom + depth + soft particles; 30 fps cap on phones, DPR <= 2, paused off-screen, reduced motion = a still frame with the same info.
  First paint is a 2D fallback (the steps as a list) so the page is useful before three.js arrives.

## The steps in order (data already exists)
Zlarior (LIT, engine/accounts.STAGES + brain_glance 'stage (n/10)'):
1 market data in (bars, VIX band) -> 2 entry window open (02:00-15:30 ET) -> 3 liquidity map (Asia hi/lo, NY 1st hour, equal highs/lows,
PDH/PDL; distances in points and $) -> 4 sweep (price takes a level, >= 0.5 ATR deep) -> 5 inducement -> 6 CISD / shift -> 7 limit order
placed -> 8 1-minute CISD confirm -> 9 trade (stop 1 tick beyond the sweep extreme, size follows the stop, one target from the VIX band,
banked at 8R) -> 10 done / journal.
ATLAS: three lobes (EMA, MACD, S/R), each with its own hours and "1 trade a day"; a shared risk gate; today's armed setup with entry / stop
/ target (brain_glance 'arm').

## The risk gate (a ring around the brain stem)
MFFU rules live: drawdown left ($), daily loss used, best-day consistency, 7-day inactivity clock, news ban (Rapid funded), the 2% price
limit, the hand-trade hedge guard, the cross-account hedge. Each a node: green / amber / red with the number.

## "Tons more" (each a small module around the brain)
- Thought stream: the plain-English log (brain_glance 'log'), newest first, typed in like a terminal.
- What I watch: the live levels with distance to price, and what happens if price touches each one ("if NQ sweeps 26,547 by 0.5 ATR, I look
  for a short").
- Memory: the last 10 trades (win/loss, R, $), streak, PF last 40 sessions (the edge chip GREEN / AMBER), the cold-run note.
- Confidence: the setup grade (engine setup_grade) for the armed setup.
- Plan for today: entry windows, news events, early closes (Thanksgiving week), countdown to the next window.
- Fill quality: ticks past the backtest per trade (tools/fill_speed.py, after the weekend landing).
- Accounts it trades: Zlarior -> 50K, 25K #2, Rapid; ATLAS -> funded 25K (+ the Rapid lane); each account's room.
- Learning: the nightly scorecard (engine/zeus_learn) - "edge GREEN, nothing to change".
- Payout path: ATLAS's ring to $2,100 (the payout coach).
- Health: PC heartbeat, data freshness, NinjaTrader connected, bot armed / stopped.
- Replay: scrub today's trade through the stages (the chart + the brain light up in sync).
- Voice: "Jarvis, what is Zlarior thinking?" reads the current card.

## Data
v1 = site-only, from what the PC already posts (pc.glance bots: stage, wait, why, lv, arm, log, day, room; board; mf; at; life). Anything
missing goes to LEAD_WIRES as a PC-side addition for a weekend landing (bot code only after a red-team).

## Done when
Both brains render at 390x844 with real data, FCP < 1 s with the 2D fallback, no CLS > 0.05, tests (static + browser at 390 px, reduced
motion, offline), phone shots, and the NQ page perf budget unchanged (three.js loads only on the Brain tab).
