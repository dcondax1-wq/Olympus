# day-jarvis 2026-11-20: Jarvis that knows the business, and loads fast

Branch `day-jarvis`. Files: `tools/web_public/jarvis/biz.js` (new), `jarvis/index.html`, `jarvis/backdrop.js`, `jarvis/data.js`,
`tests/test_jarvis_biz.mjs` (new). Lead wires: `LEAD_WIRES.md` (jarvis/sw.js only: cache v77, biz.js in SHELL, backdrop ?v=b6).

## 1. What Jarvis answers now (biz.js, before the brain)

Nine one-tap chips under the mic (in the HTML, so they are there at first paint), and the same questions typed or spoken.
Every answer: dollars first, then one line `Source: <feed>, <age>`. Voice reads the answer without the source line.

| Question (chip) | Feed | Example answer (the real PC post of 2026-11-20 ~07:30 ET replayed) |
|---|---|---|
| How are my accounts? (Accounts) | PC report (ntfy, via data.js) | 3 accounts (1 funded, 2 in eval). Zlarior 50K $49,193, $1,025 room, $3,807 to pass; ATLAS 25K $24,887, $887 room, funded; Zlarior 25K #2 $25,000 ... |
| Is ATLAS in a trade? (In a trade?) | board card position + chart feed open trades | ATLAS 25K: YES, short 1 micro from 26,380.75, about +$214 open right now (+2.7R). Stop 26,379.5 (past the entry: this trade can no longer lose), target 26,122.75 |
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

Harness: Playwright Chromium, `isMobile` + touch, 4x CPU slowdown (CDP), the real PC post replayed for the feeds. "First tap" =
tap the first chip (old page: the first suggestion) ~1 s after Jarvis is ready, until the answer bubble shows.

| Measure | Before (pc) | After (day-jarvis) |
|---|---|---|
| First text on screen (FCP) | 280-380 ms | 190-330 ms |
| Jarvis ready | 630-910 ms | 730-830 ms |
| **First tap -> answer** | **4.6-5.3 s** | **0.5-0.9 s** |
| Later tap -> answer (3D running) | 1.1-1.3 s | 1.1-1.4 s (same) |
| JS downloaded before the first tap | 2.66 MB | 1.90 MB |
| JS over the first 15 s (3D included) | 2.79 MB | 2.82 MB (+ biz.js 25 KB) |
| Long tasks > 200 ms in the first 6 s | 5-6, one of ~2.0 s | 4, all 0.2-0.4 s |

What did it: (1) on a phone (coarse pointer) the 3D sky and the 3D core are built only after 6 s from the start AND 2.5 s with
no touch, checked again before each heavy step (three.js parse, renderer, scene), so the owner's first taps never queue behind
the ~2 s shader compile; on a computer nothing changed. (2) With effects Off the 3D sky is no longer built at all (it was, for one
still frame). (3) The ~40 app status cards load 6 per idle slice with one redraw per batch (was all at once, ~0.5 s). (4) The star
loop's layout read once a second (was every frame); the phone check reads matchMedia once. (5) A business chip skips the old 220 ms
pause and the double fetch.

Honest limits: the 3D still costs ~2 s of main thread in headless Chromium (software WebGL; on an iPhone the shaders compile in
the background through KHR_parallel_shader_compile, see olympus/render.js) and its frames are 200-500 ms long tasks in software GL
only. Still over 200 ms at 4x: three start-up tasks of 0.2-0.4 s (the shell module, apps.js building the app list; apps.js is not
mine to change). I did NOT lazy-load the voice: voice-out / tts / the AI voice must be loaded at the first touch for the iPhone audio
unlock that George needs, and the brain captures memory / tools / modes when it is made (tried it, reverted: the brain came late
and the hub test's idle-line check failed). Ideas for the lead: memoise apps.js listApps() inside remember() (O(n^2) per status card).


## 3. Fixed on the way

- Kalshi K8 card was invisible to Jarvis: the PC posts `kalshi_live.st = "paper"`, which data.js's kalshiLive() drops; biz.js reads
  the raw post (and keeps the last card for offline).
- data.js slim() dropped a trade's `src` / `member`: paper ATLAS trades looked like real money. Now kept (labelled "paper", out of the $).
- Static sweep of the 33 id'd buttons: none dead (bootFix uses an inline onclick). No page errors in the screenshot runs. The only
  console errors left on a local copy are 404s for files the real site build writes (money/index.json) or that are unpublished on
  purpose (kalshi.json, asked once per open).
- Not fixed (not mine): 3 search failures in tests/test_jarvis_brain3.mjs are on `pc` too (search-index.json ranking).

## 4. Tests

| Suite | Result |
|---|---|
| `python tests/smoke.py` | 8/8 green |
| `python -X utf8 -m tests.test_jarvis_hub` | 271/272. Run 2: only fail = 'hide my balance' caught by biz.js (fixed). Run 3: only fail = o. intro frame timing on a loaded machine ("cuts to the reveal early": ms 3517 vs 3.1 s); it passed in run 2 with the same intro code, so I read it as timing-flaky. Not touched by this branch |
| `python -X utf8 -m tests.test_jarvis_apps` | 97/97 |
| `node tests/test_jarvis_biz.mjs` (new) | 32/32 |
| node: copilot / skills / tradeday / zeus | 149 / 276 / 41 / 124, all pass |
| node: brain3 | 346 passed, 3 failed: the same 3 search failures on `pc` (not this branch) |

Deliverables here: REPORT.md, LEAD_WIRES.md, 01-12 PNG at 390x844 @2x (answers.json = the exact texts), jarvis-5-questions.webm
(Accounts, In a trade?, Payout, Today, Kalshi). Python Playwright was missing in this container: `pip install playwright==1.63.0`
+ `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers` (matches the pre-installed Chromium).
