# 3 questions for the firms (night-asks, 2026-11-23)

Each one blocks a money decision. Copy the grey box and paste it into the firm's support chat or contact form. There are no
account numbers, names or emails in them, so add nothing personal. Keep each answer **in writing** (a screenshot of the chat
is enough) and tell Claude the answer.

## 8 AM report (3 lines)

1. MFFU: does the Risk team move a Rapid EOD account to live before a $10,000 day (their example is $7,000), and does the
   $5,000 Reserve pay out? This decides when to close each Rapid: a $7,000 move cuts the $300 plan from ~$44.7k to ~$27.5k in 6 months.
2. FundedNext: does a bot that only *sends us* Telegram alerts break their "no EA with Telegram" rule? It is the first $150 buy in
   the fleet plan, blocked until they say yes.
3. Lucid: is the same bot on Lucid and at MFFU (never opposite sides) allowed, does LucidPro 50K run on NinjaTrader, and what
   is the price? About +$790/month per account in the model, and nothing gets bought before a written yes.

---

## 1. MFFU (Rapid EOD going live)

**Where:** the chat on help.myfundedfutures.com (or Discord support).

**Why it matters ($):** any live move suspends every MFFU sim account, the Builders included. The fleet plan
(`research/writeups/fleet-plan-2026-11-22.md`) makes ~$44,726 in 6 months on the $300 plan (Jul-Oct-like). If the Risk team
moves a Rapid at $7,000, the same plan makes ~$27,500. Closing each Rapid at $6,500 paid keeps ~$35,320. Their answer picks
the rule.

**Their rule text (`research/lit/mffu_rules.json`, rapid_eod_50k / 25k, checked 2026-11-22):**
- Rapid live move: "automatic at $10,000 net profit in ONE session (profit above $10,000 that day forfeited) or the Risk
  Management Team's sole discretion (their example: approved at $7,000 total profit)". For Rapid: "Consistent payout
  performance reviewed and approved by our Risk Management Team".
  https://help.myfundedfutures.com/en/articles/13134718-understanding-rapid-live
- Reserve: "up to $5,000 of sim profits to a Reserve at the move (used if the live account is breached, or paid as a bonus)".
- "All simulated trading accounts and additional purchases are suspended during Live account operation".
  https://help.myfundedfutures.com/en/articles/13745661-payout-policy-overview-best-and-fastest-prop-firm-payouts

**Paste this:**
```
Hi, a few questions about Rapid EOD sim-funded accounts moving to Live:

1. Apart from the automatic move after a $10,000 net profit session, is there a total-profit or total-payout amount at which
   the Risk Management Team usually reviews a Rapid EOD account for Live (your page mentions an example at $7,000)? Is it
   per account or across all my accounts?
2. Is the move at a $10,000 single session fully automatic, and is anything above $10,000 that day forfeited?
3. The up to $5,000 Reserve: when and how is it paid out to the trader (for example after a number of live payouts),
   and is it lost if the live account is breached?
4. If one Rapid EOD account goes Live, are my other sim-funded accounts (Builder, Rapid) only paused, and do they come
   back if the live account ends?

Thank you!
```

## 2. FundedNext Futures (alerts through Telegram)

**Where:** the chat on helpfutures.fundednext.com.

**Why it matters ($):** FundedNext 50K is the **first** buy in the fleet plan's $150 pick, ahead of the Rapid EOD 50K
(`research/writeups/fleet-plan-2026-11-22.md`). It stays OFF (`docs/LUCID_SETUP.md`, `engine/trade_home.py`: "needs your
written yes") because our phone alerts use Telegram.

**Their rule text:** "Using an EA that incorporates third-party applications such as Telegram or WhatsApp is strictly
prohibited". https://helpfutures.fundednext.com/en/articles/17225788-fundednext-futures-most-frequently-asked-questions
(quoted in `research/writeups/corvette-plan-2026-11-21.md`). Their copying-to-other-firms rule is clear, so it is not asked
again here.

**Paste this:**
```
Hi, a question about your FAQ line "Using an EA that incorporates third-party applications such as Telegram or WhatsApp is
strictly prohibited".

I trade my own automated NQ strategy through NinjaTrader. It decides and places its own orders on my account. Separately it
SENDS me a notification on Telegram when it enters or exits (one-way, to my own phone only). Telegram cannot send it
commands, nothing is copied from or to anyone through Telegram, and no signal service is involved.

Is that allowed on a FundedNext Futures account? If not, would the same notifications be fine through email or a phone
push app instead of Telegram?

Thank you!
```

## 3. Lucid Trading (same bot at two firms, NinjaTrader, price)

**Where:** the chat or contact form on support.lucidtrading.com.

**Why it matters ($):** the model puts LucidPro 50K at about **+$790/month per account**, the best second firm
(`docs/LUCID_SETUP.md`). The bot is built and OFF. Step 1 there is "Buy nothing until they answer yes in writing".

**Their rule text (`research/lit/lucid_rules.json`, read 2026-11-22):**
- "Automated trading systems and trade copiers are permitted".
  https://support.lucidtrading.com/en/articles/11404728-other-trading-activities
- Hedging banned, including "Hedging between different firms or funded platforms".
  https://support.lucidtrading.com/en/articles/11404734-prohibited-hedging
- Same strategy at other firms: covered by "Trade with Integrity", which our reader could not read.
  https://support.lucidtrading.com/en/articles/11404732-trade-with-integrity
- Platform: the pages read name Tradovate / Rithmic only for LucidLive. NinjaTrader for LucidPro is **unverified**.
  https://support.lucidtrading.com/en/articles/11404729-allowed-trading-times
- Price: **unverified**. lucidtrading.com blocks our reader, and ~$126 with a code is a third-party number.

**Paste this:**
```
Hi, before I buy a LucidPro 50K I have three questions:

1. I run my own automated NQ strategy (my own code, not a purchased or shared bot). Your rules say automated systems and
   trade copiers are permitted. Is it allowed to run the SAME strategy on a LucidPro account and, at the same time, on
   my accounts at another prop firm? It always takes the same direction on every account: never opposite sides, never
   hedged, and I would not copy anyone else's trades.
2. Does LucidPro 50K connect to NinjaTrader 8 (for example through a Tradovate login), so orders can come from
   NinjaTrader?
3. What is the current price of the LucidPro 50K evaluation with the daily loss limit ON, and is there a current
   discount code?

Thank you!
```

---

**After the answers (for Claude):** MFFU's goes into `research/lit/mffu_rules.json` (rapid_eod_* live_rules) and the fleet plan's
close-at rule. FundedNext's yes, or "email/push only", decides the alert channel and its `trade_home` OFF line. Lucid's yes goes in
through `engine.accounts lucid-ok` (owner only), and the real price goes in `docs/LUCID_SETUP.md` (CLAUDE.md: real prices only).
