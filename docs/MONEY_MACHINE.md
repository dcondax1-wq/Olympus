# The Money Machine, in plain words (2026-11-10)

Five small helpers look for honest ways to save or make money. A hub page, **Mint**, shows all five on one screen; **Mint City** shows them as a 3D city; **Stoa** shows what needs you right now. **Everything is paper only: nothing here buys, sells, trades or moves money.** Every dollar is an **estimate** with a low and a high number, never a promise.

## The five streams (what each scanner really does)

| Stream | What it really does | Where the numbers come from |
|---|---|---|
| **Chrysos** (the gold) | The prop-firm eval and payout planner. For Builder 50K, Builder 25K and ATLAS 25K at YOUR prices ($91.80, $63, $43) it turns the stored LIT backtests into pass / fail odds, how many accounts you would buy per funded one, time to the first payout, a payout calendar, break-even month and a 6- and 12-month net, each as a worst / base / best case. It never buys anything. | `research/lit/*.json` (your own backtests). All accounts take the same signals, so they win and lose together. |
| **Mercury** (deals) | Reads public prop-firm, data and platform pages (MFFU, Apex, Topstep, TPT, NinjaTrader, TradingView) for sales, codes, free resets and rule changes, and prices each against your prices. Dated deals carry their end date. Never logs in, never buys. | Public web pages, one polite request per page. A discount is only a saving if you would have bought anyway; it is not monthly income. |
| **Sibyl** | A prediction-market edge scanner. Reads the Kalshi study files the site already publishes and lists the kinds of bet whose win rate beat the break-even price after fees, using the cautious end of the range, with a small paper stake (a quarter of Kelly, capped) and ruin odds. Suggestions only: it places no bet and never touches the Kalshi bot. | `kalshicity/edges.json`, `whatif.json`, `forward.json` (read only). Past bets do not promise future wins. |
| **Oikos** (household) | Reads your Ledger export and finds where money leaks: resets that did not pay back, accounts that never covered their cost, and similar. Also a generic set-aside line (not tax advice). | Only what you recorded in the Ledger. Without an export it shows a sample. |
| **Arbiter** | A spread and funding finder. Lists market-neutral "carry" ideas with a net yearly rate after fees and lock-up time: hold a coin and short its perpetual to collect funding, a stablecoin below one dollar, the same event priced differently on two prediction venues. Paper only; asks for no key. | Free public price and funding endpoints; works offline from a bundled sample. Funding rates change every few hours and exchange risk is real. |

When a stream's file is a sample (`--fixture`, or a scanner failed), Mint marks the card **Example** and the total says how much is example money.

## What is automatic and what is you

| Automatic | You |
|---|---|
| Fetching public pages, scoring, writing the JSON, building the Mint estimate, keeping each scanner's own memory between runs. | Reading "What to do today" (max 3 things) or the cards Stoa lights up. |
| Marking data **Old** after 6 hours. | Double-clicking `RUN_MONEY.bat` if Mint or Stoa say data is old. |
| Showing Examples when a scanner is missing or broken. | Checking any deal or code on the firm's own page before you pay. Mercury only reports; you decide. |
| Mercury's `expires` date lets Stoa warn "Deal ends in 20 h". | Keeping your Ledger up to date so Oikos has real entries. |

## Put it on a schedule (PC, one line)

Open a normal Command Prompt once and paste:

`schtasks /Create /SC MINUTE /MO 30 /TN "LE Money Engine" /TR "\"C:\path\to\bot\RUN_MONEY.bat\" auto" /F`

(Use the real folder of the bot.) It runs every 30 minutes by itself. Remove it with `schtasks /Delete /TN "LE Money Engine" /F`. The log is `money_out_log.txt`, the result is `money_out\index.json` plus one whole file per stream.

The free GitHub Actions copy (`money-engine.yml`) runs every 3 hours and keeps the JSON as a 7-day download. It does not publish to the site by itself. The site build runs `python tools/money_publish.py --site <site folder>` to copy the files to `<site>/money/`.

## Sibyl's own paper picks: where the memory lives (2026-11-10)

Sibyl (`tools/money/sibyl.py`) ranks kinds of Kalshi bet and writes `sibyl.json`. Three small steps turn that into a track record, all paper only:

1. **Record**: `python tools/money/sibyl_ledger.py --sibyl <folder>\sibyl.json --state <folder>\sibyl_forward.json` adds each day's picks once, with the stake in $ and in R. The first run freezes the **start day**. Nothing before it is counted and nothing is back-filled.
2. **Settle**: `python tools/money/sibyl_results.py --state <folder>\sibyl_forward.json --out <folder>\sibyl_results.json` builds the results file from the bot's real settled bets (`kalshicity/ledger.json`). It is a **proxy**: a pick is a kind of bet ("95-97 cent", "Bitcoin", "buying NO"), not one named market, so it is settled by the real result of the bot's first settled bet of that kind on or after the pick's day (each real bet used once). No matching bet yet means the pick stays open: nothing is invented. If the ledger file is missing the script says so and exits cleanly.
3. **Count**: `python tools/money/sibyl_ledger.py ... --results <folder>\sibyl_results.json` settles the open picks (won = the paper win, lost = minus the paper stake) and rewrites `sibyl_forward.json`. The Sibyl page shows n, and hides net and win rate until 30 bets have settled.

**`sibyl_forward.json` is the memory, so it must survive between runs.** If it is lost, the start day restarts and the count begins again.

- **On the PC (the plain way): `RUN_MONEY.bat` keeps it in a local folder on the PC**, next to the bot (`money_keep\`, made by the script; `RUN_MONEY.bat` now runs steps 2 and 3 after the money engine, reading `money_out\sibyl.json`). That folder is not synced anywhere: back it up if you care about the record, and do not delete it. A damaged file is refused (the script stops and says so) rather than restarted, because the start day is frozen.
- **In the cloud**: the free GitHub Actions copy only keeps its JSON as a 7-day download, so it would restart the count every run unless the file is saved on a state branch. Until that is set up, the PC folder is the only place the record is kept.
- The Sibyl page reads `money/sibyl_forward.json` on the site; without it the card says "Not started". Nothing here touches the Kalshi bot, a key or an order.

## Honest limits

- The total is a **range** (live streams 30% to 150% of the base guess; old data 0% to 120%; examples 0% to 200%). The middle number is a guess, not a forecast. Chrysos's items are 12-month nets for a purchase, Mercury's are one-time savings, so the cards say "estimate" and what the number means; do not add them up in your head as income.
- A scanner reads public pages or your own files. A page can change its layout, so a scanner can find nothing or the wrong line. Check before you act.
- Sample numbers are never counted as real: the total shows how much comes from live streams.
- The history line on Mint is saved on your phone only and shows the estimate moving, which is not income moving.

## What could go wrong

- **A deal ends or was misread**: confirm on the firm's own page. Worst case you skip a saving.
- **You buy accounts because the planner looks good**: Chrysos is built from backtests; real results differ and every fee can be lost. Never buy an account only because of a discount.
- **A scanner crashes or is slow**: the engine stops it after its timeout, keeps the last good file marked Old, then falls back to the sample.
- **A site blocks the request**: that stream goes Old. Nothing else is affected.
- **Two runs at once**: a lock file makes the second one skip.
- **Carry ideas (Arbiter) look safe and are not**: funding flips sign, a peg can break, an exchange can freeze withdrawals. Paper only.
- Nothing here touches the trading bot, its settings or any key.
