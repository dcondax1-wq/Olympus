# Connect the money (2026-11-14)

Your own bank and card exports, on your PC, free and private. No paid aggregator, no bank password anywhere, nothing logs in to a bank.

## Your 3 steps
1. On your bank's website (or app), download the last 3 months as **CSV** (or OFX / QFX) and save it in `%USERPROFILE%\.olympus\money_inbox\` (the folder is made the first time tools/bat/RUN_MONEY.bat runs). Do the same for each card or app you use.
2. On the PC, double-click `tools/bat/RUN_MONEY.bat`.
3. Open **Oikos** on the iPhone through your live link: the "Your bank money" card shows it. Ask Jarvis "how much did I spend on food this month".

Repeat step 1 once a month (overlapping files are fine: nothing counts twice).

| What | Result |
|---|---|
| Banks it reads by itself | Chase (checking + card), Bank of America (checking + card), Wells Fargo, Capital One (card + 360), Apple Card, Discover, Amex, Cash App, PayPal, Venmo, any OFX / QFX, any "date, description, amount" CSV |
| What you get | money in / out each month, by category, subscriptions and bills ($ a month + next date), prop-firm fees vs payouts (ROI), Kalshi deposits / withdrawals, net cash flow, how long your savings last, money leaks, net worth over time |
| Where it shows | Oikos ("Your bank money"), Jarvis (5 new questions), the money scoreboard with `--private`, the Oikos leak finder (it now reads your bank data) |
| Privacy | account and card numbers are never kept (number columns dropped, 4+ digit runs masked); the phone copy has no merchant names unless you turn them on; it reaches the phone only over your private Tailscale link, never the public site |
| Cost | $0 |
| Trading | untouched. Paper only: nothing here can trade, arm or move money |

## Jarvis questions
"How much did I spend on food this month", "what did I spend on gas last month", "what subscriptions do I have", "how long can I live on my savings", "how much did I spend this month", "what's my net worth". Without the file Jarvis says "I don't have that".

## Net worth
Your balances live in `%USERPROFILE%\.olympus\money\balances.json` (made the first time). Put each balance in (a name, no account number), or from a Command Prompt in the bot folder:
`python tools\money_import.py --balance "Checking=2500" --balance "Savings=6000"`. Kalshi fills itself from the Kalshi feed when you leave it empty. Debts (cards, loans) go in as `"kind": "debt"`. One point is kept each day, so the phone shows the change over 30 days.

## Your rules (optional)
`python tools\money_import.py --init-rules` writes `data\money_rules.json` (gitignored) with the default rules: first match wins, add words to `match`, change a `category`. Categories: rent, food, gas, subscriptions, trading_tools, utilities, transport, shopping, health, bank_fees, cash, people, prop_fees, other, income, prop_payout, income_other, kalshi_deposit, kalshi_withdrawal, transfer (ignored). `"privacy": {"publish_merchants": true}` shows merchant names on the phone. `"overrides": {"<row id>": "food"}` fixes one row (the id is in the private ledger).

## iPhone: log a cash expense (no app to install)
Needs the live link (`tools/bat/LIVE_LINK.bat`, docs/LIVE_DASHBOARD.md) and, once, `tools/bat/MONEY_INBOX.bat` on the PC. That starts a tiny separate inbox (not the bot server) that can only add a line to `money_inbox\cash.jsonl`, reachable at `https://<your-pc>.<tailnet>.ts.net:8443/inbox` from your own Tailscale devices only.

Shortcut "Cash spent" (Shortcuts app, + , add these actions in order):
1. **Ask for Input** (Number, "How much?"), then **Set Variable** `Amount`
2. **Ask for Input** (Text, "What for?"), then **Set Variable** `What`
3. **Choose from Menu** ("Category"): food, gas, transport, shopping, health, people, other; in each item **Text** with that word, after the menu **Set Variable** `Cat`
4. **Get Contents of URL**: `https://<your-pc>.<tailnet>.ts.net:8443/inbox`, Method **POST**, Request Body **JSON**: `amount` (Number) = Amount, `what` = What, `cat` = Cat, `kind` = `expense`
5. **Get Dictionary Value** `saved` from Contents of URL, then **Show Notification** with it ("Saved: $12.50 Tacos (food)")

Shortcut "Update balance": the same, with `kind` = `balance`, `name` = "Checking" (or Savings ...), `amount` = the balance. Optional allow-list: `%USERPROFILE%\.olympus\money\inbox.json` = `{"allow": ["you@your-tailscale-login"]}`.

## How it is built (for Claude)
| Piece | File | Notes |
|---|---|---|
| The importer | `tools/money_import.py` | stdlib; layouts `LAYOUTS` + Wells Fargo (no header) + OFX/QFX; `scrub()` masks numbers; fingerprint de-dup (date, cents, description, n-th in its file); rules `DEFAULT_RULES_DOC` (whole words, direction); `subscriptions()` (weekly / monthly / quarterly / yearly, a store must charge the same amount); `build()` = the summary; `oikos_ledger()` = Ledger-format entries at category level |
| Private files | `%USERPROFILE%\.olympus\money\` | `ledger.json`, `balances.json`, `networth_history.json`, `household.json`, `oikos_ledger.json` (outside the repo) |
| Phone summary | `money_out/household.json` | served by `engine/live_site.py` (`MONEY_KEEP` + household) over the private link only; `tools/money_publish.py` never copies it |
| Feeds | `tools/money/oikos.py` (reads `oikos_ledger.json` when no `--ledger`), `tools/money_scoreboard.py` (`household` block with `--private`, never in the cash totals), Oikos card `oikos/householdcore.js` + `household.js`, Jarvis `jdata.js` XFILES + `router.js` household_* + `skills.js` |
| Inbox | `tools/money_inbox_server.py`, `tools/bat/MONEY_INBOX.bat` | 127.0.0.1:8767, POST /inbox append-only, Funnel refused, Tailscale user required through the proxy, 2 KB, 30 a minute |
| Schedule | `tools/bat/RUN_MONEY.bat` | runs the importer before the scanners (every 30 minutes with its task) |
| Tests | `tests.test_money_import` (+ `test_money_import_node.mjs`), `tests.test_money_inbox`, `tests.test_oikos_household` (browser, under flock) | fixtures `tests/fixtures/money_import/` (one per bank layout, fake numbers) |

## Honest limits
- **Not automatic from the bank.** You download the export yourself (free sync services need a paid aggregator or your bank password, which this never uses). Once a month is enough.
- **Bank layouts change.** A new export layout from your bank may need a new entry in `LAYOUTS`; the run then says "not a bank export I know" and imports nothing from that file. A plain "date, description, amount" CSV always works.
- **Categories are rules, not magic.** Unknown shops land in "Other spending"; add their words to your rules. Payments to people (Zelle, Venmo) are "Sent to people" unless the note says what it was (e.g. "rent").
- **Subscriptions need 2-3 months** of data before they are found; a yearly one needs two charges a year apart.
- **One format per account.** The same account imported as CSV and as OFX can count twice (their descriptions differ); pick one.
- **Runway and net worth need your balances** (balances.json or `--balance`); without them the card says so.
- **The phone sees it only through the live link** (PC on, Tailscale on). The public site shows "Not connected".
- **Estimates, not advice.** Not tax or financial advice.
