# Kalshi: what the bot should stop doing

Suggestions only. Nothing here touches the bot. You decide.

## The table (the bot's own 1,836 bets, Kalshi fees already inside the dollars)

| bet kind | bets | result | verdict |
|---|---|---|---|
| Buying at 90 to 95 cents | 581 | -$248.30 (-4.7% of stake, range -7.9% to -1.6%) | **Stop** |
| XRP bets | 192 | -$106.63 (-6.1%, range -10.9% to -1.2%) | **Stop** |
| 15-minute favourites strategy | 1,131 | -$88.77 (wins 95.0%, needs 96.6%) | **Stop** (already off: keep it off) |
| Value strategy | 40 | -$13.04 (wins 75%) | Pause (few bets) |
| Solana, HYPE, BNB, Ethereum, Dogecoin | 142 / 122 / 77 / 165 / 165 | -$13 / -$12 / -$8 / -$5 / -$1 | Watch (could be luck) |
| Flip-exit, Sniper, arb, arbx | 16 / 14 / 4 / 5 | -$8 / -$5 / -$3 / -$1 | Keep off (too few bets to judge) |
| Bitcoin bets | 623 | +$51.82 (+0.7%) | Keep |
| Late favourite (BTC hourly) | 182 (3 losses) | +$16.26 | Keep (positive, not proven) |

Same list as data: `research/kalshi_edge_B/bot_suggestions.json` (built by `python tools/kalshi_suggestions_build.py`); shown in Sibyl as "What your Kalshi bot should stop doing".

## What the bot's settings would need to change (plain words)

1. Do not buy anything priced 90 to 95 cents (a minimum price of 95 cents).
2. Turn off XRP markets.
3. Leave the 15-minute favourites strategy off, and pause the Value strategy.
4. Optional: cap every bet at about 2% of the balance. The two big losses were larger-than-average bets.

On the bot's history, skipping 90 to 95 cents alone turns -$63 into +$185 (the city's what-if, `whatif.json`). That is a look back on the same bets, not a promise: the band was picked after looking.

## What this does NOT prove

- Kalshi pays you on average only when the market misprices something. We tested about 28,000 crypto markets (two months of minute quotes): ladders consistent, prices match a volatility model better than our model did, resting orders get filled only when the price moves against you. **The market mostly does not misprice.**
- One pocket looked good (15-minute favourites at 95-97 cents, 8 minutes before the end). On data it had never seen it gave +0.5 cent per dollar with a range of -1.4 to +2.0: nothing.
- So the realistic goal is **losing less**, not winning more. The stop list makes that likely; it does not make the bot profitable. A small number of bets can be luck either way.
- Real money is at stake: balance was $55.81 and the bot is paused.

## Message to send in your "kalshi-server" chat (only if you decide to)

Copy and paste:

```
Please do these four things in the bot's config and then report back what you changed and the new settings. Do not turn anything on. Do not change anything else. (1) Stop buying contracts priced 90 to 95 cents (minimum price 95 cents). (2) Turn off XRP markets. (3) Keep the 15-minute favourites strategy off and pause the Value strategy. (4) Tell me whether a cap of 2% of the balance per bet is already in place. Leave the bot paused; I will decide when to restart it.
```

You can also reply "no" and nothing changes.
