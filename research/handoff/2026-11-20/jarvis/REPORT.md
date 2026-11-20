# day-jarvis 2026-11-20: Jarvis that knows the business, and loads fast

Branch `day-jarvis`. Files: `tools/web_public/jarvis/biz.js` (new), `jarvis/index.html`, `jarvis/backdrop.js`, `jarvis/data.js`,
`tests/test_jarvis_biz.mjs` (new). Lead wires: `LEAD_WIRES.md` (jarvis/sw.js only: cache v77, biz.js in SHELL, backdrop ?v=b6).

## 1. What Jarvis answers now (biz.js, before the brain)

Nine one-tap chips under the mic (in the HTML, so they are there at first paint), and the same questions typed or spoken.
Every answer: dollars first, then one line `Source: <feed>, <age>`. Voice reads the answer without the source line.

| Question (chip) | Feed | Example answer (the real PC post of 2026-11-20 ~07:30 ET replayed) |
|---|---|---|
| How are my accounts? (Accounts) | PC report (ntfy, via data.js) | 3 accounts (1 funded, 2 in eval). Zlarior 50K $49,193, $1,025 room, $3,807 to pass; ATLAS 25K $24,887, $887 room, funded; Zlarior 25K #2 $25,000 ... |
| Is ATLAS in a trade? (In a trade?) | board card position + chart feed open trades | ATLAS 25K: YES, short 1 micro from 26,380.75, about +$X open right now (+2.7R). Stop 26,379.5 (past the entry: this trade can no longer lose), target 26,122.75 |
| How much room does Zlarior have? (Room left) | PC report | Zlarior 50K: $1,025 of $2,000 drawdown left (51%); today it can still lose $1,000 before the daily limit. Zlarior 25K #2: ... |
| When is my first payout? (Payout) | business/payday.json | ATLAS 25K: about $800 around Mon Jan 4 2027 (as early as Dec 8; 50% by Dec 31), then the others. "Estimates ..., not a promise" |
| What did the bots do today? / this week? (Today / This week) | PC report trades + card P&L | Today: closed trades in $, open ones with R; paper trades labelled and kept out of the $ |
| What's on the news today? (News) | nq/news_week.json + pythia/events.json | Today's releases (big ones first), then the next big one (NFP Fri Dec 4 08:30 ET) |
| What should I do today? (To-do) | hub/steps.json (+ Done ticks) + business/decisions.json | 6 things waiting on you. First: Add the Rapid EOD 25K (Phone) ... 10 yes/no questions on the Decide card |
| How's Kalshi? (Kalshi) | PC report K8 card (kalshi_live.k8) | Kalshi K8 is on PAPER. Today 2 bets, 0 won, -$5.08. So far 7 bets, 43% won. Bankroll $55, $2.50 a bet; next window ... |

Offline: every file biz.js reads is kept on the phone (slimmed, ~13 KB) and used with its age ("saved copy from 3 h ago (offline)");
the PC report's last copy comes from data.js ("PC report, 2 h ago (saved copy, offline)"). Nothing is ever made up: a missing feed
is said to be missing. Read only: no orders, no arming, no settings.
Left to the old brain on purpose: "how much room do I have" / "how far to target" with no account named, BLITZ questions, Kalshi
when no K8 card exists (it answers from kalshi.json or says "not connected"), anything with why / explain / strategy / chart.

## 2. Speed (390 x 844, mobile + touch, 4x CPU slowdown, no service worker, local server; 3 runs each)

FILL

## 3. Fixed on the way

FILL

## 4. Tests

FILL
