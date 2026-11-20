# Rapid EOD 25K (or 50K): 3 steps

Zlarior (LIT) and ATLAS trade the Rapid together, one trade at a time. Nothing trades until step 2.
One Rapid at a time (a 25K or a 50K). Checked end to end on a test PC 2026-11-20 (night-rapidready).

## 1. Add it (1 minute)

Copy the account Name from NinjaTrader (Accounts tab). Double-click **ADD_ACCOUNT.bat**, type **5**, paste the Name. Easiest: on the PC open **http://localhost:8766/add-account/**, pick Rapid EOD 25K, type or tap the Name, type I ACCEPT LIVE RISK, press **Add + start trading** (one press: adds it, waits for flat, re-arms, trades). Works the same on the phone over your Tailscale link + `/add-account/`.

Good: the window says
`[OK] Rapid EOD 25K = <Name> ... NOT armed` and
`Rapid EOD 25K: target +$1,500, floor $1,000 below the best close, max 20 micros, a winning day <= $427 (30% rule), ATLAS <= $250 a trade`.

Stop and tell Claude if it says **50K**, **[NOT ADDED]** or **CHECK THE NAME** (then copy the Name again). Nothing changed.

(No .bat? PowerShell in the bot folder: `python -X utf8 -m engine.accounts add --plan rapideod25 --name "PASTE-NAME"`.
50K: type 3, or `--plan rapideod`.)

## 2. START BOT

Bot running? Wait until it is flat, then STOP BOT. Double-click START BOT.

At **3/4 Real money** it lists every account the phrase arms. Check this line is there:
`Zlarior + ATLAS ->  Rapid EOD 25K  <Name>`. Then type `I ACCEPT LIVE RISK` yourself.

It then says `Rapid EOD 25K (LIT + ATLAS): armed <Name>`, and the launch checklist at the end shows
`[OK] Rapid EOD 25K (LIT + ATLAS): ... both lanes running, armed`. A `..` on that line: send Claude a photo.

## 3. Check it

```
python -X utf8 -m engine.rapid --status
```

Good: `Rapid EOD 25K eval <Name>: balance $25,000 (target $26,500), 0 of 4 days, best day $0; ARMED`.

## MFFU's rules vs the bot (25K; MFFU help center + plan page, read 2026-11-19)

| Rule | MFFU Rapid EOD 25K | The bot |
|---|---|---|
| Price | $162, **$97.20** with CLUB | - |
| Pass | +$1,500, at least 4 trading days | stops new trades at +$1,500 |
| Best day | no day over 30% of the profit ($450) | keeps a winning day under $427 (LIT + ATLAS together) |
| Max loss | $1,000 below the best end-of-day balance, stops at $25,100 | sizes every trade to fit the room |
| Size | 2 minis / 20 micros | max 20 micros, never 2 trades at once |
| Daily loss | none | stops for the day at -$500 |
| Flat | by 4:10 PM ET | flat 3:55 PM ET; 5 min before a holiday halt |
| News | allowed in the eval; funded: none 2 min before / after CPI, jobs, Fed | funded: flat 3 min before, back 2.5 min after |
| Inactivity | 7 days without a trade closes it | warns you from day 5 |
| Other accounts | no long + short at the same time | never opposite your 50K / 25K accounts |
| Payout (funded) | after $1,100 profit, $500 min, $250 profit between payouts, 90% | tells you when: what is above $26,600, from $500 |

50K: $3,000 / $2,000 floor / 3 minis (30 micros) / day under $855 / ATLAS <= $500 / payouts above $53,100; price $165 (CLUB).

Expected (Money plan, a Jul-Oct 2026-like market, not a promise): passes in about 25 trading days (about Dec 23),
first payout about early February (about $690 to you), about $1,000 a month after that. Business > Money plan.

## If something looks wrong

- MFFU shows the target reached but no pass (a day was over 30%): tell Claude (the bot stops at the target).
- The Board shows "Rapid EOD 25K | planned": the PC has not reported it yet (it does every 15 min after START BOT).

## Later

- Passed: MFFU gives a funded Name. Paste
  `python -X utf8 -m engine.rapid --to-funded --account "FUNDED-NAME" --start YYYY-MM-DD`, then START BOT + the phrase
  (it keeps the 25K rules).
- After MFFU pays you: `python -X utf8 -m engine.rapid --payout YYYY-MM-DD=AMOUNT`
- Turn it off: `python -X utf8 -m engine.rapid --off`

Details for Claude: `engine/rapid.py` (PLANS: the 25K and 50K numbers), `engine/multi_account.py` presets
`mffu_rapid_eod_25k` / `_50k`, tests `python -X utf8 -m tests.test_rapid` and `python -X utf8 -m tests.test_rapid25`,
replay `python -X utf8 tools/rehearse_day.py --rapid` (any `--days`, the newest bars too) and `tools/money/rapid_replay.py`.
