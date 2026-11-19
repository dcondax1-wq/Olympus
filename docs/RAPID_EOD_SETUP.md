# Rapid EOD (25K or 50K): 3 steps

Zlarior (LIT) and ATLAS trade the Rapid EOD together. The bot does the rest.
It stays OFF until you do step 1. One Rapid at a time (a 25K or a 50K).

## 1. Put in the account name (one step)

When MFFU sends the account, open NinjaTrader and copy its account name.

**Easiest:** double-click **ADD_ACCOUNT.bat**, type **5** (Rapid EOD 25K) or **3** (Rapid EOD 50K), paste the name.

Or on the PC, open PowerShell in the bot folder and paste one line (your name between the quotes):

```
python -X utf8 -m engine.accounts add --plan rapideod25 --name "PASTE-THE-RAPID-NAME-HERE"
```

(`--plan rapideod` for the 50K.) It says `[OK] Rapid EOD 25K = ... NOT armed` and then the rules it will use:
`Rapid EOD 25K: target +$1,500, floor $1,000 below the best close, max 20 micros, a winning day <= $427 (30% rule), ATLAS <= $250 a trade`.
If that line says 50K for your 25K, stop and tell Claude. Nothing trades yet.

A refused line says `[NOT ADDED]` (wrong name, wrong size, or a Rapid is already set): nothing changed, no restart needed.

(The older line `python -X utf8 -m engine.rapid --account "NAME"` still works: it now reads the size from NinjaTrader's
balance or the name, and refuses when it cannot tell. Add `--size 25k` or `--size 50k` to say it yourself.)

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

| What | Rapid EOD 25K | Rapid EOD 50K |
|---|---|---|
| Price (CLUB) | $97.20 | $165 |
| Eval goal | +$1,500, at least 4 days | +$3,000, at least 4 days |
| Floor | $1,000 below the best end-of-day balance | $2,000 below |
| Best day | a winning day is kept under $427 (MFFU's 30% = $450) | under $855 |
| Size | max 20 micros (2 minis) | max 30 micros |
| LIT + ATLAS | never two trades at once; LIT goes first; ATLAS <= $250 a trade | same; ATLAS <= $500 |
| Daily loss | the bot stops for the day at -$500 | at -$1,000 |
| Funded news | flat 3 min before to 2.5 min after big news (CPI, jobs, Fed) | same |
| Funded payout | it tells you what to take: only above $26,600 ($1,100 buffer + $500 kept), $500 minimum, $250 profit since the last one | only above $53,100 ($1,000 kept) |

Expected (Money plan, Jul-Oct 2026-like market, not a promise): the 25K passes in about 25 trading days (9 in 10 runs within
3 months), first payout about 2 months after you buy it, about $1,000 a month to you after that. Details: Business > Money plan.

## Later

- Passed: MFFU gives a new funded name. Paste:
  `python -X utf8 -m engine.rapid --to-funded --account "FUNDED-NAME" --start YYYY-MM-DD`, then START BOT and type the phrase again
  (it keeps the 25K or 50K rules of the eval).
- After MFFU pays you: `python -X utf8 -m engine.rapid --payout YYYY-MM-DD=AMOUNT`
- Turn it off: `python -X utf8 -m engine.rapid --off`

Details for Claude: `engine/rapid.py` (PLANS: the 25K and 50K numbers), tests `python -X utf8 -m tests.test_rapid` and
`python -X utf8 -m tests.test_rapid25`, replay `python -X utf8 tools/money/rapid_replay.py`.
