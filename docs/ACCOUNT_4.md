# Account #4: a LucidPro 50K that copies Zlarior

Buy it **when your first MFFU payout is in your bank**. If that lands in the Black Friday week (about Nov 19 - Dec 1),
buy in the sale; never wait more than a month for a code. Paper research, 2026-11-14 (team A4); full study:
`research/writeups/account-4-2026-11-14.md`.

| What | Answer |
|---|---|
| Which account | **LucidPro 50K**, Daily Loss Limit **ON**, platform **TDV/NT** (Tradovate / NinjaTrader). Not LucidFlex, not the Rithmic version |
| Price | list $172-192, about **$120-135 with a 30% code** (VAULT, ETFPROMO, PFT or DGT seen in Nov 2026; check at checkout). One-time, no activation fee |
| What it adds (Jul-Oct 2026 trades) | about **$810 a month** on its own (6 months, after its fee); **$1,750 a month** for the pair with Zlarior funded |
| Pass within 2 weeks | **47% pass, 0.2% fail**, median 9 sessions: the same days as Zlarior's eval (same signal, same size) |
| $ per eval | about **$4,450 back** for a $134 eval (6 months) |
| Worst case for the pair | worst day -$1,690 (firm money, no account lost); worst 6 months -$403 (fees); 2 paths in 100 lose money |
| Same bet | it wins and loses with Zlarior (daily correlation 0.94): one bad week hits both |
| Sizing | **the same as Zlarior**, nothing to set: eval 40% of the room; funded 60% of the room, at most $1,500, a winner at most $2,000 |
| Lucid's rules (its own help center) | $3,000 target; $2,000 max loss at the day's close, locks at $50,100; $1,200 daily loss (pauses the day); 40 micros; pass in 1 day. Payouts any day: $500 over $52,100, $500 profit in the cycle, best day at most 40% of the cycle; $2,000 then $2,500; 90% to you; 5 payouts. Flat by 4:45 PM ET. No trade for 30 days = the account is deleted |
| Bots and copying | **allowed** in Lucid's help center. Never long on one account and short on another (Lucid bans it across firms too; the bot never does it) |

## 3 steps (at the PC)

1. Buy the LucidPro 50K on lucidtrading.com: Daily Loss Limit ON, TDV/NT, the code at checkout.
2. NinjaTrader: Tools > Options > General > tick Multi-provider, restart, then Connections > Configure > add a NinjaTrader
   (Tradovate) connection with your Lucid login, connect, and copy the new account's Name from the Accounts tab.
3. Paste this with the Name in it, then type `I ACCEPT LIVE RISK` when it asks:

```
python -X utf8 -m engine.fleet --add --id lucid50k --lead zlarior --plan lucid_pro_50k --account "<Lucid Name>" --start today --arm lucid50k
```

## The first week: what to watch

| Check | Where | Good |
|---|---|---|
| Every Zlarior trade appears twice | Fleet page / phone: the Lucid row | same side, stop and target, about the same micros |
| The copy's fill vs Zlarior's | Fleet page, slippage column | 0-2 ticks |
| Both NinjaTrader connections stay green | NinjaTrader Control Center | no "connection lost" |
| No "firm rule" skips | Fleet page, last skip | only on a day the daily loss is used up |
| Room to floor | Fleet page | $2,000 at the start; a trade never risks more than 40% of it |

Stop the copy for today: `python -X utf8 -m engine.fleet --stop-today lucid50k`. Kill it: `--kill lucid50k`.
