# LUCID SETUP: the second firm (one page)

The bot can copy Zlarior's LIT trades onto a **LucidPro 50K** next to your MFFU accounts. It is built and tested, and it stays **OFF**
until you do the steps below. Claude never arms it and never places a real order.

| What | Lucid's rule (read 2026-11-22 on support.lucidtrading.com, links in `research/lit/lucid_rules.json`) | What the bot does |
|---|---|---|
| Pass | $3,000 profit, no time limit, no eval best-day rule | LIT's normal eval size: 40% of the room, at most $1,000 at risk |
| Max loss | $2,000, end-of-day trailing, stops at $50,100 | the same floor the bot uses for your MFFU 50K |
| Daily loss | $1,200 if you pick **DLL ON** at checkout (it pauses you for the day, never fails you) | a full stop-out always fits inside the $1,200 left today |
| Size | 4 minis / 40 micros | never more than 40 micros |
| News | allowed on LucidPro | trades through news like on the Builder |
| Flat by | 4:45 PM ET | LIT is flat by 3:55 PM |
| Hedging | **banned, also across accounts and across firms** | one rule over every account at every firm: never long on one and short on another |
| Inactive | a trade netting at least $1 every 30 days, else the account is deleted | LIT trades 2-4 times a week; the NQ page's 7-day clock shows Lucid's 30 days |
| Funded payouts | 90% to you; $500 profit a cycle; biggest day at most 40% of the cycle; $2,000 then $2,500 max; buffer $52,100 | funded size: 60% of the room, at most $800 at risk, a winner at most $1,500 |
| Accounts | 10 evals, 5 funded per household | the add refuses more |

Not checked (Lucid's main site blocks our reader): the **price**, whether LucidPro runs on NinjaTrader through Tradovate, and the
"Trade with Integrity" page. That is why step 1 asks Lucid in writing.

## Why Lucid, and the next-best fits (from research/writeups/corvette-plan-2026-11-21.md; nobody has paid a real price yet)

| Firm | Bots + copier allowed in writing | NinjaTrader | Account cap | Payouts | Price (not a real price paid) | Verdict |
|---|---|---|---|---|---|---|
| **Lucid (LucidPro 50K)** | yes: "Automated trading systems and trade copiers are permitted"; the same bot at another firm is NOT confirmed (ask, step 1) | via Tradovate (to confirm) | 10 evals, 5 funded | any day once eligible, paid within 2 business days; $2,000 then $2,500 | ~$126 with a code (list $180, third-party) | **best by $**: about +$790 a month per account in the model |
| FundedNext (Rapid Daily 50K) | yes, and copying to other firms in your name is explicitly allowed | yes | the 15th payout triggers a live review | $1,000 each | $149.99-$179.99 with code RAPID | **backup**: the clearest rules, but it caps out (~+$9,480 total for 5 accounts). It bans EAs that use Telegram, and our alert bus sends Telegram |
| Tradeify | the agreement says using it across multiple firms is against policy (s6.6) | - | - | - | - | **no**: we run the same bot at MFFU |
| Apex | bots banned in the user agreement | - | - | - | - | **no** |

No firm clearly beats Lucid for our bots. FundedNext is the fallback if Lucid says no in writing.

## Your steps (hands only)

1. **Email Lucid first** (support@lucidtrading.com or the chat on their site), in your own words:
   "I run my own automated NQ strategy through NinjaTrader. I would run the same bot on a LucidPro 50K and on accounts at another
   firm (never opposite sides, never hedged). Is that allowed, and does LucidPro connect to NinjaTrader through Tradovate?"
   Buy nothing until they answer **yes in writing**.
2. **Buy** a LucidPro 50K with **DLL ON** (cheaper, and it cannot be changed later). Write down the real price you paid.
3. **Connect it in NinjaTrader** (Lucid's emailed Tradovate login). Copy the account **Name** from NinjaTrader's Accounts tab.
4. **Add it** (disarmed): on the PC, in the bot folder:
   `python -X utf8 -m engine.accounts add --plan lucidpro50k --name "<the Name>"`
   (or the phone's Add account page: pick **LucidPro 50K**).
5. **Record Lucid's written yes** (this alone never arms anything):
   `python -X utf8 -m engine.accounts lucid-ok --name "<the Name>"`
6. **STOP BOT, then START BOT** and type your live phrase yourself. Only then does the Lucid account trade. Until step 5,
   START BOT says "NOT armed (no written OK from Lucid recorded yet)" and skips it.

To take it off: `python -X utf8 -m engine.accounts remove --name "<the Name>"`.

## For Claude

- Code: preset `lucid_pro_50k` (engine/multi_account.py), plan `lucidpro50k` (engine/account_cli.py: Lucid caps, `lucid_ok`, the
  arm hold), engine/account_box.py (the page's plan list), engine/clock7.py + nq/clock7.js (Lucid = 30 days, no MFFU keep-alive).
- Proof: `python -X utf8 -m tests.test_lucid` (rules = the cited file, add / caps / arm hold, a sizing grid inside the $1,200 DLL, the
  hedge guard across firms, the 30-day clock); `python -X utf8 tools/lucid_dryrun.py --days ... --quick --out ...` (the whole fleet
  rehearsed without and with a Lucid lane: every existing lane's trades identical).
- Open: ATLAS on Lucid is not wired (LIT only); the price is unverified.
