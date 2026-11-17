# Zlarior on the funded 25K (OFF until you say)

ATLAS's 25K showed **$26,946.10** on 2026-11-17 (target $26,500): the eval passed and MFFU locked it.
This switch lets Zlarior (LIT) trade the new **funded** 25K next to ATLAS. It is **OFF**.

## What it would do (6 months, Monte Carlo on real 2026 trades, costs in)

| Funded 25K | 1st payout ask | No payout in 6 months | $ a month to you |
|---|---|---|---|
| ATLAS alone (today) | 18 / **26** trading days | 5.0% / **5.5%** | $592 / **$497** |
| LIT + ATLAS $250 | 14 / **18** trading days | 7.5% / **12.2%** | $599 / **$529** |
| 2021-25 (no edge) | 17 vs 20 | 78% vs 82% | $48 vs $35 |

Jan-Jun 2026 / **Jul-Oct 2026**. Faster first payout in both halves, a little more $, but more 6-month "no payout"
(a big LIT winner trips the 50% best-day rule) and slightly worse in 2021-25. Your call.

## Step 1: when MFFU gives you the funded 25K (one line)

Copy the new account's Name from NinjaTrader (Accounts tab). With the bot stopped, on the PC:

```
python -X utf8 -m engine.lit25 --funded "PASTE-THE-FUNDED-NAME" --start 2026-11-18
```

(the same as the Start page button "Passed -> funded" on ATLAS's row). ATLAS moves to the funded account, not armed.

## Step 2: turn Zlarior on there (only if you want it)

```
python -X utf8 -m engine.lit25 --on
```

## Step 3: START BOT

Type `I ACCEPT LIVE RISK` yourself. Zlarior's lane on the 25K is armed only together with ATLAS's 25K.
Check: `python -X utf8 -m engine.lit25 --status`. Off again: `python -X utf8 -m engine.lit25 --off` (then STOP / START BOT).

| Rule on that account | |
|---|---|
| Never two trades at once | LIT goes first: ATLAS waits while LIT is in a trade; LIT entering closes ATLAS first |
| LIT size | the 25K funded rule: 60% of the room, at most $750 risk, a winner at most $1,000 |
| ATLAS size | $250 risk (or 30% of the room if smaller), the $600 soft daily loss |
| One balance | both count against the same $1,000 trailing floor and the same day |

Sim-test first if you can (a Sim account Name in step 1). The bot never arms anything by itself.
