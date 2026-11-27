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
