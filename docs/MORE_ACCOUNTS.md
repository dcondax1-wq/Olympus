# More accounts: one signal, many accounts

One bot's trade (Zlarior = LIT, or ATLAS) is copied to more NinjaTrader accounts. Each account follows **its own firm's
rules**. It is **off** until you add an account, and it **never arms itself**. (The full fleet guide is `docs/ADD_ACCOUNT.md`.)

| What each account gets | How |
|---|---|
| Its own size | from its own room to its floor (eval: two-week size, funded: funded size) |
| Never more contracts than the firm allows | the firm's max micros / minis, always |
| Its own daily loss | the firm's daily loss, or your own day stop if smaller |
| Its own stop for today | `--stop-today <id>` (resumes by itself next session) |
| Its own kill switch | `--kill <id>` (`--unkill <id>` to undo) |
| Consistency / best-day rule | the firm's rule, checked before every copy |
| Firm account limit | no copy past the number of funded accounts the firm allows |
| Your own limits | only ever **stricter** than the firm's: a looser value is refused |
| Arming a real account | only by you typing `I ACCEPT LIVE RISK` for **that** account Name |

## 3 steps

1. Log the new account in NinjaTrader 8 (its Name is in the Accounts tab). A Sim account (Sim102 ...) needs no arming.
2. Add it on the PC (change the id, plan, Name and day; `--daily-stop` and `--max-micros` are optional, only stricter):

```
python -X utf8 -m engine.fleet --add --id b25a --lead zlarior --plan mffu_builder_25k --account "<Name>" --start 2026-11-16 --daily-stop 300 --max-micros 8
```

3. Only for a real (non-Sim) account, when you are at the PC: `python -X utf8 -m engine.fleet --arm b25a`, type
   `I ACCEPT LIVE RISK`, then start the bot with the live phrase as always.

## Firm profiles (data: `research/props/copy_profiles.json` + `research/props/firm_rules.json`)

| Plan | State |
|---|---|
| MFFU Builder 25K / 50K (`mffu_builder_25k`, `mffu_builder_50k`) | verified rules (firm_rules.json) |
| Tradeify Growth 50K, Bulenox EOD 50K, a new firm 50K | **placeholders**: they never trade until the max loss is filled in |

See a profile: `python -X utf8 -m engine.copy_accounts --show mffu_builder_50k` (`--stage funded`).
What is still missing: `python -X utf8 -m engine.copy_accounts --unfilled`.

## Honest limits

- MFFU has not confirmed in writing that copying between your own accounts is allowed: ask support first.
- How many funded accounts MFFU allows in total is not verified (per plan: 1 Builder 50K, 2 Builder 25K).
- Copies are tested on replays and Sim, not yet on a real second account.
- Long on one account and short on another is never allowed (MFFU rule across all your accounts).
