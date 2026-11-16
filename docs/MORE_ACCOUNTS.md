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
| LucidPro 50K (`lucid_pro_50k`), LucidFlex 50K (`lucid_flex_50k`) | verified from Lucid's own help center, 2026-11-14 (`research/props/firm_research.json`) |
| FundedNext Rapid Daily 50K (`fn_rapid_daily_50k`) | verified except the payout cap; **on hold** until FundedNext says yes in writing to one signal on two accounts |
| Bulenox EOD 50K (`bulenox_eod_50k`) | filled 2026-11-14, mostly third-party (unverified); **on hold** until Bulenox approves the bot in writing |
| Tradeify Growth 50K, a new firm 50K | **placeholders**: they never trade until the max loss is filled in (Tradeify is ruled out) |

Account #4 (the LucidPro 50K, when to buy it and the 3 steps): `docs/ACCOUNT_4.md`.

## A second MFFU 50K (re-read 2026-11-16)

MFFU's help center: copying between **your own** MFFU accounts is allowed, but MFFU funds only **one Builder 50K per
person** at a time (2 Builder 25K; at most 5 sim-funded accounts in all). So a second Builder 50K can run and pass its eval
next to Zlarior, but MFFU will not fund it while Zlarior's funded Builder 50K is active. It only pays once Zlarior's funded
account has ended (lost, or moved to live after 5 payouts). For more money now, the next account is a LucidPro 50K (`docs/ACCOUNT_4.md`).

The one line (Sim Name first; a real Name is saved NOT armed):

```
python -X utf8 -m engine.fleet --add --id mffu50b --lead zlarior --plan mffu_builder_50k --account "<Name>" --start today
```

The bot then counts Zlarior's own funded account: `--to-funded mffu50b` is refused while Zlarior holds the funded 50K. When
it has ended: `python -X utf8 -m engine.fleet --held mffu_builder_50k=0`, then `--to-funded`. Tested on Sim:
`python -X utf8 -m tests.test_fleet_mffu`. The payout plan (when to buy #3, #4 from the payouts): the Business page,
`python -X utf8 tools/money/payout_plan.py`.

See a profile: `python -X utf8 -m engine.copy_accounts --show mffu_builder_50k` (`--stage funded`).
What is still missing: `python -X utf8 -m engine.copy_accounts --unfilled`.

## Honest limits

- MFFU's help center (read through web search 2026-11-16) allows copy trading across your own MFFU accounts; MFFU gives no
  help or reset for a copier mistake. A one-line written yes from support is still the safest record.
- Lucid allows bots and trade copiers in its help center; it bans opposite positions across your accounts AND other
  firms' accounts (the bot never does that).
- MFFU funded accounts: 1 Builder 50K, 2 Builder 25K, 5 in all (3 once you hold a 100K / 150K). The Builder page's headline
  says "one active Builder account per user": a conflict with the 25K table, ask support before a second funded 25K.
- Copies are tested on replays and Sim, not yet on a real second account.
- Long on one account and short on another is never allowed (MFFU rule across all your accounts).
