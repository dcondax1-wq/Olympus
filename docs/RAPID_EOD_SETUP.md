# Rapid EOD 50K: 3 steps

Zlarior (LIT) and ATLAS trade the Rapid EOD 50K together. The bot does the rest.
It stays OFF until you do step 1.

## 1. Put in the account name (one line)

When MFFU sends the account, open NinjaTrader and copy its account name.
On the PC, open PowerShell in the bot folder and paste (put your name between the quotes):

```
python -X utf8 -m engine.rapid --account "PASTE-THE-RAPID-NAME-HERE"
```

It says `[OK] Rapid EOD = ... NOT armed`. Nothing trades yet.

## 2. START BOT

If the bot is running: wait until it is flat, STOP BOT.
Then double-click START BOT. When it asks, type `I ACCEPT LIVE RISK` yourself.
Only that arms the Rapid. The window then says `Rapid EOD (LIT + ATLAS): armed`.

## 3. Check it

```
python -X utf8 -m engine.rapid --status
```

It shows the balance, days traded (4 needed) and your best day.

## What the bot does on it

| What | Rule |
|---|---|
| Eval goal | +$3,000, at least 4 days |
| Floor | $2,000 below the best end-of-day balance |
| Best day | a winning day is kept under $855 (30% rule) |
| LIT + ATLAS | never two trades at once; LIT goes first |
| Daily loss | the bot stops for the day at -$1,000 |
| Funded news | flat 2 min before to 2 min after big news (CPI, jobs, Fed) |
| Funded payout | it tells you what to take: only above $53,100 ($1,000 kept), $500 minimum |

Expected (Jul-Oct 2026 replay, not a promise): pass in about 20 trading days.

## Later

- Passed: MFFU gives a new funded name. Paste:
  `python -X utf8 -m engine.rapid --to-funded --account "FUNDED-NAME" --start YYYY-MM-DD`, then START BOT and type the phrase again.
- After MFFU pays you: `python -X utf8 -m engine.rapid --payout YYYY-MM-DD=AMOUNT`
- Turn it off: `python -X utf8 -m engine.rapid --off`

Details for Claude: `engine/rapid.py`, test `python -X utf8 -m tests.test_rapid`, replay `python -X utf8 tools/money/rapid_replay.py`.
