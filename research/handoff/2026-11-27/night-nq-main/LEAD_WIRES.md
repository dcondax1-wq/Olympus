# night-nq-main: what the lead wires (2026-11-27)

Branch night-nq-main (off origin/pc). Only my files changed: nq/index.html, nq.css, nq.js, nqdesk.js, nqdesk.css, nqscene.js,
nqland.js, the NEW nq/nqhero.css, and tests/test_nq_desk.py (hero checks). Web only; no engine change.

1. **sw.js precache:** add `nq/nqhero.css` (new file, loaded render-blocking by nq/index.html).
   - The bumped versions: nq.css a11, nqdesk.css 13, nqhero.css 1, nqtheme.css 10, nq.js r34 (imports nqdesk.js v9), nqscene.js q7, nqland.js 4.
   - nqgoals.css is now loaded non-blocking (`media=print` onload), the same pattern as ../nqdeep.css.
2. **A real "setup step N of 4" for LIT** (asked for in the brief) needs a field in the PC's glance. Today engine/brain_glance only posts
   `arm` (side + "forming" / armed text). Suggested: `glance.bots[].step = [n, of, "words"]` in engine/brain_glance.py.
   - nqdesk.botState already shows SETUP FORMING / SETUP ARMED / IN TRADE / DONE TODAY / WATCHING / OFF / NO REPORT.
   - It would then add "step 3 of 4". I did not touch engine files.
3. **Perf.**
   - perf_sweep --static is green: nq block 305 KB (was over at 312 before nqgoals.css went non-blocking), trading 283 KB.
   - The hero canvas is 2D: no three.js, paused off screen / hidden tab, one still frame under prefers-reduced-motion.
   - The bots' 3D scene now uses the palette's gradient light instead of the dusk HDR: -293 KB on a desktop.
4. **Pre-existing on pc, not mine:**
   - test_nq_goals 23/25: 2 date / VIX checks on live data.
   - tests/test_nqfx needs Python Playwright, which is absent in this container.
   - nqdesk.css's 7-day-clock rules had bare hex colours that broke test_nq_desk's token check; fixed here (tokens with fallbacks).
5. **Two "to payout" numbers for ATLAS on the same page (pre-existing).**
   - The hero tile and the vault follow the owner rule: the first payout = the $1,000 ask at $2,100, so $1,890 to go at $210.
   - The older Accounts card (nqdesk.accounts goalText) shows the board's own `to_target` ($1,290 in the DEMO).
   - Suggest the Accounts card reads the same goals model (nqgoals.goals) so one number shows. I left that card's logic alone.
6. **New: a sticky "jump to" bar under the hero** (Chart / Goals / Accounts / Bots / Trades / News / Checks), 44 px taps, below the kit's compact bar.
7. **Light scheme:** styled (tokens flip) but not screenshot-checked tonight: my forced-attribute script failed. The page is dark-first.

## QA pass (2026-11-27 ~03:00 ET)
8. **ONE goals model:** `nq/goals_model.js` (+ tests/test_goals_model.py, in the nq + trading areas).
   - The hero and the vault read it. The accounts helper has the API, to switch acctcore.
   - sw.js: precache nq/goals_model.js too.
9. **hub/learned.json** is written by learn_night but never published: a 404 on every nq/ load.
   - I dropped the fetch, and test_nq_page's reads list follows.
   - Publish the file (and restore one getJSON line) if you want the per-bot slippage line back.
10. **perf_sweep nq block is AT the 310 KB budget** (309.x).
    - I trimmed comments from nqtheme.css / nqhero.css / index.html to fit.
    - The next CSS added to nq/ needs a budget bump or a non-blocking load.
11. **Not mine, still open from QA:**
    - #11 the pillars chip "312/60 tick d..." (pillars/hero.js);
    - #6 the stale cloud data (bars / trades to Nov 20);
    - #1 trading_home readiness; #2 chart vs brain price; #3 the blank vault (accounts); #12 accounts 411 px.
    - #10: the nav is now one rail (checked at 390 px).
12. **Folds (QA #5):** the Accounts grid + 7-day clock + numbers + GO / WAIT, the per-bot cards, and the checks / replay / backtest are in `<details>` (closed). All ids are kept and the jump bar opens a fold.
    - The phone page is 11,820 -> 8,149 px.
    - The Python-Playwright browser suite (test_nq_page part c) could not run here: please run it on landing.

## Battle plan + alert history (2026-11-27 ~01:30 ET)
13. **New files.**
    - nq/plancore.js (pure models), nq/plan.js (its own deferred module), nq/plan.css (non-blocking).
    - Test: tests/test_nq_plan.py, in the nq area; its fixture is tests/fixtures/brief/nq_brief_2026-11-26.json.
    - sw.js: precache plancore.js, plan.js, plan.css.
14. **nqfeed.js (night-nq-speed):** tagged `<script defer src="nqfeed.js?v=1">` right after pc_feed.js, NOT the blocking tag the spec asks for.
    - A blocking 15 KB script puts nq/ over the 310 KB perf budget.
    - `defer` still runs before nq.js (document order: deferred classic scripts before later modules), so its fetchLatest wrap is in place before nq.js asks.
    - The head start is lost; the NQ_EARLY prefetch in the head still starts status_feed.json at once.
    - nq.js re-draws on the `nq-feed` event.
    - On this branch alone the tag 404s until night-nq-speed is merged.
15. **Alert history sources.**
    - The PC post's `brd.ev` (up to ~6 newest), the published ../board/board.json events, and the board trades (entries / exits).
    - It shows what the PC LOGGED, not the push messages: there is no copy of the actual Telegram / ntfy texts on the site.
    - If you want those, the PC would need to post a small "sent alerts" list (e.g. in the brd block).
16. **The battle plan uses nq/brief.json** (tools/premarket_brief.py).
    - Tonight's brief is Thu's, so the card says "Plan from Thu, Nov 26 - today's (Fri, Nov 27) is not built yet".
    - When the PC glance has live levels, the ladder uses them and the market read is labelled "From the brief of ..." so two prices never pose as one.

## Weight pass (2026-11-27 ~02:00 ET)
17. **nq block 310 -> 262 KB** (perf_sweep --static).
    - `../pc_feed.js` and `../business/payoutcoach.js` are now `defer` on nq/. Only nq.js (a module, after them in document order) and pillars/hero.js (imported after load) use them.
    - plan.js is code-split: nq.js adds it near its card or when the browser is idle.
    - **nqfeed.js stays `defer`:** it must run after pc_feed.js (it wraps PC_FEED), so it cannot be blocking while pc_feed is deferred. Making all three blocking again = 262 + 37.5 + 15 = 315 KB.
    - What is left blocking is the kit: themes.js 77, agora.css 50, olympus.js 47, olympus.css 14 = 188 KB of the 262.
    - Further cuts need the kit (not mine): split themes.js, lazy-load agora.css's below-the-fold parts.
    - Timings (Chromium, CPU x4, 4G-like 150 ms + 500 KB/s per file, served from disk, DEMO, median of 5): first $ on screen 2,049 -> 1,995 ms, first paint 1,032 -> 1,008 ms.
    - The wall-clock gain is small because the blocking files load in parallel and the kit dominates. The byte budget headroom is the real win: 48 KB.
18. **Tablet / landscape.** 768x1024: an odd last account tile spans the row. 900-1099 px: page 960 px wide, the accounts 3 across. No sideways scroll at 768 / 1024.

## 19. BRIEF ME + SUNLIGHT MODE (2026-11-27, after the weight pass)
- sw.js precache (lead only): add `nq/briefcore.js`, `nq/briefme.js`, `nq/sun.css` (all three are lazy: briefme at idle / first tap, sun.css only
  when on or prefers-contrast: more). Without them, an offline phone just loses the voice / sunlight; nothing breaks.
- The hero model now carries `ageS`, `nowS`, `demo` and each bot's `ageS` (numbers behind the existing words). Jarvis could read
  `window.NQ_BRIEF.text()` for the same spoken summary.
- Also fixed: tests/test_nq_live.py + tests/test_accounts_screen.py harnesses copy goals_model.js (nqdesk.js imports it since 39a3f555's parent;
  both were red on HEAD).

## 20. The December card (2026-11-27)
- Needs `tools/web_public/nq/december.json` from night-of-december f118818a (not on this branch: you land both). Until it is there the card
  shows "NOT PUBLISHED" + an honest line. Fixture copy for the test: tests/fixtures/december/december_2026-12.json.
- sw.js precache (lead only): add `nq/decore.js`, `nq/december.js`, `nq/december.css` (+ `nq/december.json` once landed).
- tests/run_area.py: both branches append one line under the `AREAS["nq"]` block (nq_december here, december_plan there): keep both.
- tests/test_nq_page.py: the kit's "no browser storage" check now allows exactly one key, `nq.sun` (SUNLIGHT MODE), and checks the try/catch.
