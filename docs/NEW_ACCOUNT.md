# New MFFU account: 3 steps

**Easiest:** double-click `ADD_ACCOUNT.bat` in the bot folder, type 1-4, paste the account Name. Then STOP BOT / START BOT + the phrase.

One pasted line per account. It is added **NOT armed**. Nothing trades until START BOT and you type the phrase.

| Plan | Price (CLUB code, 40% off) | Who trades it |
|---|---|---|
| Builder 25K | $63 | Zlarior (LIT). ATLAS $250 joins only once it is funded and you say yes |
| Builder 50K | $91.80 | Zlarior (LIT). Next to Zlarior's eval: whichever passes first is kept |
| Rapid EOD 50K | $165 ($275 list) | Zlarior + ATLAS together. One Rapid only |

## 1. Paste the line

Buy the account, open NinjaTrader, copy its Name (Accounts tab). On the PC, open PowerShell in the bot folder and paste
the line for your plan (put the Name between the quotes):

```
python -X utf8 -m engine.accounts add --plan builder25k --name "PASTE-NAME-HERE"
```
```
python -X utf8 -m engine.accounts add --plan builder50k --name "PASTE-NAME-HERE"
```
```
python -X utf8 -m engine.accounts add --plan rapideod --name "PASTE-NAME-HERE"
```

It says `[OK] ... NOT armed` and how many MFFU slots you use. If MFFU would not allow it (more than 10 evals, more
than 5 funded, or the plan's funded limit), it says `[NOT ADDED]` and why.

## 2. START BOT

When the bot is flat: STOP BOT, then double-click START BOT. When it asks, type `I ACCEPT LIVE RISK` yourself.
Only that arms the new account.

## 3. Check it

```
python -X utf8 -m engine.accounts status
```

One line per account: plan, who trades it, armed or not, balance. Then your MFFU slots.

## Rules on every account

- Never long on one account and short on another (MFFU bans hedging). Every account takes the same side.
- Zlarior (LIT) goes first. On a shared account ATLAS is closed before LIT enters.
- MFFU limits: 10 evals, 5 funded (Builder 50K 1, Builder 25K 2, Rapid EOD 3). Sim accounts never count.

## Later

- Passed: MFFU gives a funded Name. Remove the eval, then add the funded one:
  `python -X utf8 -m engine.accounts remove --name "EVAL-NAME"`, then
  `python -X utf8 -m engine.accounts add --plan builder25k --funded --start YYYY-MM-DD --name "FUNDED-NAME"`.
  The Rapid keeps its own line: `python -X utf8 -m engine.rapid --to-funded --account "FUNDED-NAME" --start YYYY-MM-DD`.
- ATLAS on a funded 2nd 25K: say yes to Claude. Claude wires it (it is not on yet).
- Take one off: `python -X utf8 -m engine.accounts remove --name "NAME"`.
- Test first on Sim: use `Sim102` as the Name (no arming needed, never counted).

Details for Claude: `engine/account_cli.py` (entry `python -m engine.accounts`), test `python -X utf8 -m tests.test_accounts_cli`.
