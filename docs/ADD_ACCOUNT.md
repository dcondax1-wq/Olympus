# Add an account to the fleet (copy trading)

The fleet copies what one of your bots does (Zlarior, ATLAS or BLITZ) to more accounts: another prop-firm eval, a funded
account, a Sim account, or your own live account. Each account gets its own size from its own room and its firm's rules.
It is **off** until you add an account, and it never arms anything for you.

## 3 steps

1. **Buy the account.** Use your own price with the firm's current code (never the list price). Check first that the firm
   allows a bot on NinjaTrader (the table below).
2. **Log it in NinjaTrader 8.** Its Name shows in the Accounts tab. Test on a Sim account first if you like (Sim101, Sim102 ...).
3. **Add it on the PC** with one line (put in your account's Name, the plan from the table, and the first day):

```
python -X utf8 -m engine.fleet --add --id lucid50k --lead zlarior --plan lucid_pro_50k --account "<Name>" --start 2026-11-02
```

For your **own live account** use `--plan live` with your balance and your limits:
`python -X utf8 -m engine.fleet --add --id mylive --lead zlarior --plan live --account "<Name>" --start 2026-11-02 --balance 10000 --max-risk 150 --daily-stop 300 --weekly-stop 600 --max-micros 5`

A real (non-Sim) account copies only after **you** arm it (`--arm <id>`) **and** you type `I ACCEPT LIVE RISK` when the bot
starts, as for ATLAS and BLITZ. The fleet never turns on live trading on its own.

## What the bot does for each account

- It copies only what the lead account really did (an order the broker took), same side, same stop and target, the stop
  moves, the exit. It never adds a trade of its own.
- It sizes each copy from that account's own room to its floor and the firm's limits. Evals use the bot's two-week eval
  size, funded accounts the funded size, your live account a small fixed $ risk.
- It never goes long on one account and short on another (MFFU bans it across all your accounts). If a stronger bot enters
  the other way, the copy is closed first. Zlarior is stronger than ATLAS, and ATLAS is stronger than BLITZ.
- If one broker refuses an order, nothing is booked there and the other accounts keep trading.
- Phone pushes for each account: copy not placed, eval passed (then you switch it to funded), failed, payout ready.

## Other lines (on the PC)

| What | Line |
|---|---|
| See every account | `python -X utf8 -m engine.fleet --status` |
| Stop one account / all now | `python -X utf8 -m engine.fleet --kill <id>` / `--kill all` (`--unkill` to undo) |
| Switch one off / on | `--off <id>` / `--on <id>` |
| Passed: now funded | `--to-funded <id> --account "<funded Name>" --start <day>` |
| Record a payout | `--payout <id> 2026-12-01=1000` |
| Try a past day on paper | `--dry-run 2026-10-13` |
| A firm's rules | `python -X utf8 -m engine.firms --show <plan>` (`--stage funded`) |

The Fleet page (phone: System > Fleet, or open `#/fleet`; PC: All tools > Fleet, or open `#fleet`) shows every account: balance, room, today, the open
copy, slippage vs the lead, why a copy was skipped, and rules we could not verify.

## The firms' rules in plain words

Words used below:
- **Max loss, end-of-day trailing (EOD):** the floor follows your best *closing* balance. It moves up only at the session
  close. An open loss still counts against it during the day.
- **Max loss, intraday trailing:** the floor follows your best balance *including open profit*. A trade that runs up and
  comes back moves the floor up anyway. This is the strictest kind.
- **Static:** the floor never moves.
- **Lock:** the trailing floor stops moving once it reaches start + this amount.
- **Daily loss, soft:** hit it and trading pauses for the rest of the day; the account stays alive. **Hard:** hit it and
  the account fails.
- **Best day (consistency):** no single day may be more than this share of your profit. A big day is not a breach, but you
  must trade more days before you pass or get paid.

"Verified" means the repo's research read it on the firm's own help or plan page (or your own MFFU screenshots). Anything
else is a third-party summary: check it on the firm's site. "Unknown" is never guessed; the bot then picks the safe
reading (an unknown lock = the floor keeps trailing; an unknown drawdown type = intraday).

| Firm | Bot on NinjaTrader? | The plans' rules (50K unless named) | Verified |
|---|---|---|---|
| **MFFU** Builder 50K | yes, set to your own settings | target $3,000; max loss $2,000 EOD, locks at $50,100; daily loss $1,000 soft; 40 micros; no best-day rule in the eval; flat by 16:10 ET; no long + short across your accounts; funded: buffer $2,100, $500-$2,000 a payout, best day 50% of the cycle, 80% split, 5 payouts then live. Your price $91.80 | yes (min days is a conflict, 1 vs 2) |
| **MFFU** Builder 25K | same | target $1,500; $1,000 EOD, locks at $25,100; $600 soft; 20 micros; funded buffer $1,100, $250-$1,000. Your price $63 ($43 on 2026-10-26) | yes |
| MFFU Rapid / Rapid EOD / Pro | same | Rapid funded = intraday trailing and flat 2 min around big news; Rapid EOD best day 30% in the eval | partly |
| **Lucid** LucidPro 50K | yes, bots and copiers allowed | target $3,000; $2,000 EOD, locks at +$100; daily loss $1,200 soft (optional); 40 micros; payouts up to $2,000, 90% split | mostly |
| **FundedNext** Rapid Daily 50K | yes (own accounts only for copying) | target $3,000; $2,000 EOD, locks at +$100; $1,000 soft; no best-day rule; $250-$1,200 a payout, ends after 5 | mostly |
| Apex 4.0 EOD | **no**: bans automated trading | paper only in the fleet | no |
| Topstep Combine | **no**: NinjaTrader not offered to new sign-ups | XFA payout cap $2,000, $125 minimum, 90% split | partly |
| Take Profit Trader Test | unknown: ask first | EOD in the test, intraday trailing when funded (PRO); best day 50%; min days 3 or 5 | no |
| Alpha Futures | **no**: semi-automated only, no NinjaTrader for new accounts | paper only in the fleet | no |

Prices: only your own MFFU prices are stored. For any other firm, look up the current discount code before you buy.
All values: `research/props/firm_rules.json` (rebuilt by `python tools/build_firm_rules.py`).
