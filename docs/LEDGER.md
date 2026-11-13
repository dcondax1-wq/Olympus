# LEDGER

The owner's REAL money, tracked on his phone (`tools/web_public/ledger/`). Plutus projects what could happen; Ledger records what did. Nothing here moves money, gives tax
advice or sends data anywhere.

| Piece | File | What it does |
|---|---|---|
| The numbers | `ledgercore.js` | pure maths: entries, recurring items, income / costs / pending / net, the Kalshi result, auto entries, accounts and payback, break-even, tax set-aside, payout split, waterfall, day map, CSV, export / import |
| The page | `ledger.js`, `ledger.css`, `index.html` | glass cards over the vault, five tabs (Overview, Accounts, Cash, Taxes, Entries), the gold + quick add (amount, what, date; More: category, account, note, repeats), edit / delete / clear with Undo |
| The vault | `ledgerscene.js` | a golden vault on the OLYMPUS render core: one instanced pile of coins that grows with net profit (1 coin = $5 to $500 by size), no coins below zero, a coin shower on a payout, god rays from the fx library on a profit |
| The facts | `rules.json` (`tools/ledger_rules.py`) | the owner's real eval prices ($91.80 50K, $63 25K, $43 ATLAS 25K, $0 activation) and when he paid, MFFU's payout rules; made from `research/lit/mffu_rules.json` |
| Demo | `fixture.json` | example numbers (DEMO tag) until the first entry |
| Tests | `tests/test_ledger_page.py` | static rules, the maths by hand in node (34), the page at 390 x 844 (downloads, import, undo, auto entries, tiers) |

## What counts
Net profit = payouts RECEIVED + other income - eval fees - resets - activation - expenses + the Kalshi result. A payout only requested is pending (matched by a payout received
for that account, the full amount or the 80% split). Simulated eval P&L is shown on the account cards as performance, never as cash. Kalshi result = balance + withdrawals -
deposits when deposits are recorded, else the bot's own total P&L from the public feed. Tax paid is tracked for the set-aside, not a cost.

## What is auto-filled
`home.json` goals.accounts + `rules.json`: each known account gets an eval-fee entry at the owner's real price and date (marked AUTO). It stops counting when the owner enters a fee
for that account himself, taps Not mine, or taps Keep (which makes it his own). Reset prices are not published, so resets are manual.

## Storage and privacy
Everything entered is in `localStorage['ledger.v1']` (entries, tax %, hidden auto keys). Export JSON / Import JSON / CSV are downloads he starts. The page fetches only `../home.json`, `rules.json`,
`fixture.json` and the public Kalshi feed (read only); nothing is sent.

## The Scoreboard card (2026-11-13)
The first card after "Your money in three numbers" on Overview. It reads the site's `../money/scoreboard.json` (built by `tools/money_scoreboard.py`
from every money source: accounts, bot payouts, Kalshi, second strategies, money machines, eval prices, the Plutus plan) and shows week / month /
all-time cash, ROI on eval fees, the run-rate, the next milestone and its ETA, each source's net, the paper results (never cash) and every source
with a status chip and its age. No file (or a file of another kind) = a plain "not on the site yet" line; nothing is invented. What you enter on
this phone stays here: the card does not add it, so the hero above and the card can differ. On the PC, a Ledger "Export JSON" saved as
`data/money_ledger.json` feeds the scoreboard and the Sunday report (`tools/weekly_money_report.py`); it reaches the public copy only with
`"publish": true` in that file. Pure maths in `scoreboardcore.js` (`tests/test_scoreboard_card.py`).

## Wiring the lead does (this job added files only)
1. `jarvis/apps.js` money group: `app('ledger', 'Ledger', 'money', '#ffcf5a', 'Your real money: fees, payouts, net profit', { glyph: 'L' })`
2. `olympus/olympus.js` APPS: `ledger: ['Ledger', 'L', '#ffcf5a']`
3. `tools/build_web_dashboard.py` app tuple (~line 1212): add `"ledger"`
4. root `sw.js` OTHER_APPS: add `ledger`
