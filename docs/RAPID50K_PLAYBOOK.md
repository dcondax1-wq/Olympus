# Rapid EOD 50K: day-one playbook ("max 2 re-buys", card plan-rapid50k-max2-rebuys)

Paper / planning doc (2026-11-22). Nothing here arms anything: you type the live phrase yourself at START BOT. Rules: MFFU help
center, read 2026-11-22 (research/lit/mffu_rules.json `rapid_eod_50k.live_rules_2026_11_22`); bot numbers: engine/rapid.py.

## The money in one table (research/writeups/plan-ranking-2026-11-22.md, ATLAS at real fills, 6 months, after MFFU's 90%)

| Market | $ to you a month | Worst case (3 evals) | First payout |
|---|---|---|---|
| like Jul-Oct 2026 | about **+$2,282** | -$495 | ~9 weeks after the buy (median) |
| like Jan-Jun 2026 | about +$5,001 | -$495 | sooner |
| like 2021-25 | about -$52 (-$311 over 6 months) | -$495 | usually none |

## Day one (about 10 minutes)

1. **Buy** the MFFU Rapid EOD 50K with code **CLUB** (**$165**). Write the date down: it is purchase #1 of at most 3.
2. **Add it to the bot** (it runs NEXT to your Rapid 25K: the bot has two Rapid slots, the 50K goes in slot 2 by itself).
   PC: **http://localhost:8766/add-account/** -> pick **Rapid EOD 50K** -> type or tap the NinjaTrader account Name -> type
   `I ACCEPT LIVE RISK` -> **Add + start trading**. (PowerShell: `python -X utf8 -m engine.accounts add --plan rapideod --name "PASTE-NAME"`.)
3. **Check the line it prints:** `Rapid EOD 50K: target +$3,000, floor $2,000 below the best close, max 30 micros, a winning day
   <= $855 (30% rule), ATLAS <= $500 a trade` and `(Rapid #2)`. Anything else (25K, [NOT ADDED], CHECK THE NAME): stop, tell Claude.
4. **START BOT** (only when flat): at "3/4 Real money" the list must show `Zlarior + ATLAS -> Rapid EOD 50K <Name>`; then you type
   the phrase. Check: `python -X utf8 -m engine.rapid --status` shows both Rapids, the 50K at 0 of 4 days, ARMED.

## The preset the bot trades (engine/rapid.py, nothing to set by hand)

| | Eval | Funded |
|---|---|---|
| Zlarior (LIT) | the live two_week size on the 50K's numbers ($3,000 target, $2,000 floor, 30 micros) | 60% of the room, at most $1,500 risk, a winner at most $2,000 |
| ATLAS | min($500, 30% of the room, what is left of today's $1,000) a trade | same |
| Best day (eval) | a winning day stays under 30% x $3,000 x 0.95 = **$855** (LIT + ATLAS together) | no rule |
| Day stop | -$1,000 (the bot's soft day; MFFU's DLL only if you bought that version) | -$1,000 |
| One book | never two positions at once on the account; ATLAS closes first when Zlarior enters the other way | same |
| News | allowed | flat 3 min before CPI / jobs / Fed, back 2.5 min after (MFFU: none 2 min before / after) |
| Flat | 3:55 PM ET (5 min before a holiday halt) | same |

Note for the lead: the 25K's ATLAS lane already sizes on stop + 10 ticks (its real fills, card rapid-atlas-size-10t). The 50K does
not yet: `PLANS["mffu_rapid_eod_50k"]` has no `atlas_slip` (day-rapid LEAD_WIRES R2-3 passed its bar: lost 26.6 -> 22.7% for
-$21 a month Jul-Oct-like). Add `"atlas_slip": 2.5` only with the owner's yes.

## Passing the eval
- Pass = **+$3,000**, at least **4 traded days**, and **no day over 30% of the total profit**. The bot stops new trades at +$3,000.
- Expect about 22 trading sessions (median; 92% pass within 60 sessions in a Jul-Oct-like market).
- After the pass: MFFU's paperwork (about 2 sessions), then `python -X utf8 -m engine.accounts add --plan rapideod --name "<funded Name>"
  --funded --start <first funded day>` (the add page does the same with "funded").

## Payouts: the buffer math (MFFU Rapid EOD 50K: buffer $2,100, $500 minimum, daily, 90%, no cap, no consistency)
MFFU shows a sim-funded account from **$0** (its profit is the balance).
1. **First payout unlocks** at $2,100 profit (the buffer). The bot keeps a **$1,000 cushion** above it, so it tells you to ask only
   for what is above **$3,100**, and only when that is at least **$500**: first ask at **$3,600** profit -> request $500, you get **$450**.
2. **Every later payout** unlocks once you made **$500 net since the last payout** (MFFU's rule) and the amount above $3,100 is
   >= $500 again.
3. Requests are yours (the bot never asks MFFU for money). Same day, one request. Money lands about 3 sessions later.
4. Example: profit $4,400 -> ask $1,300 (above $3,100) -> $1,170 to you; the account is back at $3,100, next ask after +$500.

## The trap: a Builder's 5th payout pauses this Rapid
MFFU (help 13745661 / 13134718): Builder accounts move to a live account after **5 payouts**. At ANY live move "all simulated trading
accounts and additional purchases are suspended" - both Rapids, the Builders, the evals go dormant; up to $5,000 of sim profit goes
to a Reserve; you cannot say no. Rapid EOD itself has **no payout cap**; it moves live only at **$10,000 in one day** (the bot's
caps make that near impossible) or when MFFU's risk team picks it.
**Rule:** before you request a Builder's **5th** payout (Zlarior 50K or the ATLAS 25K), first take every Rapid payout that is
ready that day, then decide on purpose - a Decide card comes at the Builder's 4th payout. Until then, count Builder payouts.

## Re-buys: at most 2 (3 accounts in all, max $495)
| Event | What to do | Paid from |
|---|---|---|
| Eval fails (floor touched) or the funded account dies (floor touched, or less than $200 of room left = stuck) | **Re-buy #1** the same night: Rapid EOD 50K, CLUB $165, add it the same way (`--plan rapideod`) | banked payouts if there are any, else pocket |
| The 2nd account ends the same way | **Re-buy #2** the same night (only if the edge light is not RED: `python -X utf8 tools/edge_health.py`) | banked payouts, else pocket |
| The 3rd account ends | **Stop** this slot. Do not buy a 4th: in a 2021-25-like market this plan loses about $311 in 6 months | - |
| A funded account reaches 5 payouts, or MFFU moves you live | not a re-buy: that slot did its job (see the trap above) | - |

Claude keeps the count in the money book (purchases 1/3, 2/3, 3/3) once you say yes on the card.

## Checks if something looks off
- `python -X utf8 -m engine.rapid --status` (both Rapids, balances, days, best day, armed).
- Phone alerts are named **"Rapid EOD 50K"**; no trade for 5 days = the bot warns you (MFFU closes after 7 without a filled trade).
- A target hit without a pass (a day over 30%): tell Claude; the bot already stops at the target.
