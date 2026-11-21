# Funded 25K playbook (ATLAS passed, 2026-11-17)

Short version: **upgrade in MFFU, run one line, START BOT, trade every week, ask for $1,000 at $27,100.**

## 1. What changes after the pass

| | Eval (before) | Funded 25K (now) |
|---|---|---|
| How you get it | | MFFU dashboard: Stats > the passed eval > **Upgrade** (one tap, same day; review under 24 h) |
| Account name | ...EV... | a **new** Name that contains **"SIM"** (copy it from NinjaTrader > Accounts) |
| Cost | paid | **$0** activation, nothing monthly |
| Start balance | | **$25,000** |
| Max loss | $1,000 EOD trailing | $1,000 EOD trailing; the floor stops at **$25,100** and stays there after the 1st payout |
| Daily loss | $600 soft | $600 soft (trading pauses for the day) |
| Size | 2 minis / 20 micros | 2 minis / 20 micros |
| Payouts | none | above the **$1,100 buffer**, $250 min, **$1,000 max**, you keep **80%**, 5 sim payouts then live |
| Payout rules | | 2 traded days in the cycle; best day **no more than half** the cycle's profit; first one 2 days after the first trade |
| Inactivity | 7 days | **7 calendar days without a filled trade: MFFU can close the account (a breach) and the profits are lost** |

## 2. The one line (on the PC, bot stopped)

```
python -X utf8 -m engine.account_b --to-funded --account "PASTE-THE-SIM-NAME" --start 2026-11-19
```

(Or Start page > Accounts > ATLAS > "Passed -> funded".) Then **START BOT** and type the live phrase yourself. Claude never arms it.

## 3. What the bot does

* Trades ATLAS on the funded 25K: 60% of the room to the floor, at most $750 a trade, a winner at most $1,000.
* Stops new trades if the room falls under $100.
* Pushes **PAYOUT READY** (it never asks MFFU for you), the 50% best-day warning, and "no trade for 5 days".
* Zlarior (LIT) on the same 25K is a separate switch, **OFF** (docs/LIT25_FUNDED.md).

## 4. What you do each week (Friday after 16:10 ET, 5 minutes)

1. Open **Business > My Accounts** (or the **Board**): the **Payout coach** card.
2. If the PC is silent, type the MFFU numbers into the card (balance, balance at the cycle start, best day, days traded, last trade).
3. Check the inactivity line. If no trade for 5+ days: place 1 MNQ in and out by hand.
4. If it says **PAYOUT READY**: do step 5.

## 5. Payout steps

1. Wait for **balance $27,100 or more** (= $1,000 above the buffer), 2+ traded days, best day under half. (Tested: asking for
   the full $1,000 each time pays a little more and loses fewer accounts than asking early: research/writeups/payout-policy-funded25-2026-11-17.md.)
2. In the MFFU dashboard, request a payout of **$1,000** (do it after the close, no open trade).
3. Move **30%** of what lands ($240 of $800) to the tax pot. Net to you about **$560**.
4. Record it on the PC: `python -X utf8 -m engine.account_b --payout 2026-12-16=1000` (your date).
5. A new cycle starts: the coach counts from the balance after the payout ($26,100).

## Money (estimates, 6 months, real 2026 trades, costs in)

| ATLAS alone | Jan-Jun pace | Jul-Oct pace |
|---|---|---|
| $ a month to you (before tax) | $594 | $498 |
| First $1,000 request | ~Dec 16 | ~Dec 29 |
| Account lost in 6 months | 5% | 6% |

In 2021-25 (no clear edge) it paid about $47 a month: treat the numbers as a maybe.
