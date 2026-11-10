# The Money Machine, in plain words (2026-11-10)

Five small helpers look for small, honest ways to save or make money. A hub page, **Mint**, shows all five on one screen. A second page, **Stoa**, shows what needs you right now. **Everything is paper only: nothing here buys, sells, trades or moves money.** Every dollar is an **estimate** with a low and a high number, never a promise.

## The five streams

| Stream | What it really does | Status in the repo |
|---|---|---|
| **Mercury** (deals) | Reads public prop-firm, data and platform pages (MFFU, Apex, Topstep, TPT, NinjaTrader, TradingView). Picks out sales, codes, free resets and rule changes, and prices each against YOUR real prices (Builder 25K $63, ATLAS 25K $43, Builder 50K $91.80). Never logs in, never buys. | Built (`tools/money/mercury.py`) |
| **Chrysos** | Planned as the prop-firm money stream (savings and payouts). | Not in the repo when this was written. The Mint card text is a placeholder until it lands. |
| **Sibyl** | Planned as the prediction-market stream (paper only). | Same: placeholder until the scanner lands. |
| **Oikos** | Planned as the household-savings stream. | Same: placeholder until the scanner lands. |
| **Arbiter** | Planned as the referee that ranks what to do first. | Same: placeholder until the scanner lands. |

Until a scanner exists, Mint shows a clearly marked **Example** card (sample numbers, "not real") so the page is never blank. When a scanner lands, its row in this table and the one-line `ROLES` text in `tools/money_engine.py` and `tools/web_public/mint/mintcore.js` must be set to what it really does.

## What is automatic and what is you

| Automatic | You |
|---|---|
| Fetching public pages (one polite request per page), scoring, writing the JSON, building the Mint estimate. | Reading "What to do today" (max 3 things). |
| Marking data **Old** when it is more than 6 hours old. | Double-clicking `RUN_MONEY.bat` if Mint says data is old. |
| Showing Examples when a scanner is missing or broken. | Checking any deal or code on the firm's own page before you pay. Mercury only reports; you decide. |

## Put it on a schedule (PC, one line)

Open a normal Command Prompt once and paste:

`schtasks /Create /SC MINUTE /MO 30 /TN "LE Money Engine" /TR "\"C:\path\to\bot\RUN_MONEY.bat\" auto" /F`

(Use the real folder of the bot.) It then runs every 30 minutes by itself. Remove it with `schtasks /Delete /TN "LE Money Engine" /F`. The log is `money_out_log.txt`, the result is `money_out\index.json`.

The free GitHub Actions copy (`money-engine.yml`) runs every 3 hours and keeps the JSON as a 7-day download. It does not publish to the site by itself.

To show the result on the site, the site build runs `python tools/money_publish.py --site <site folder>`. It copies the engine's files to `<site>/money/`, or a clearly labelled sample when the engine has not run.

## Honest limits

- The total is a **range** (live streams: 30% to 150% of the base guess; old data 0% to 120%; examples 0% to 200%). The middle number is a guess, not a forecast.
- Most savings are **one-time** (a cheaper eval fee), not monthly income. A monthly figure here means "if this kept happening".
- A scanner reads public pages. A page can change its layout, so a scanner can find nothing or the wrong line. Check before you act.
- Sample numbers are never counted as real: the total shows how much comes from live streams.
- The history line on Mint is saved on your phone only and shows the estimate moving, which is not income moving.

## What could go wrong

- **A deal ends or was misread**: always confirm on the firm's own page. Worst case you skip a saving.
- **A scanner crashes or is slow**: the engine stops it after its timeout, keeps the last good file and marks it Old, then falls back to the sample.
- **A site blocks the request**: that stream goes Old. Nothing else is affected.
- **Two runs at once**: a lock file makes the second one skip.
- **You act on an estimate that was wrong**: the numbers are estimates; never spend money you need because Mint said "about $X".
- Nothing here touches the trading bot, its settings or any key.
