# Live on TradingView with the computer OFF

The strategy runs as a Pine v5 **strategy** on TradingView's servers, on an **MNQ1! 5-minute** chart. Your PC, the
Python bot and the dashboard are not needed. There are two ways to get its orders into the MFFU account:

- **Automatic (main route):** every order the strategy makes fires a webhook alert to a bridge (**TradersPost** or
  **PickMyTrade**). The bridge is connected to the MFFU Tradovate account and places the order there.
- **Phone text (free fallback):** the same alert arrives as a plain-text push in the TradingView app, e.g.
  `LONG 12 MNQ at market · stop 29,880.25 · target 29,990.50 · risk $780`, and you place the order yourself in
  Tradovate.

```
MNQ1! 5m chart on TradingView's servers --order--> ONE alert, message {{strategy.order.alert_message}}
     ├─ Bridge JSON --webhook--> TradersPost / PickMyTrade --> Tradovate (MFFU)
     └─ Phone text  --push-->    TradingView app on your phone --> you, in the Tradovate app
```

Tradovate does not issue API keys for prop/evaluation accounts, so the direct REST adapter (`engine/tradovate.py`)
cannot be used here. This is preparation only: nothing in this repo places orders or holds a password, token or
webhook URL. You type those into TradingView / the bridge yourself.

Legend:
- **[verified]**: checked against the vendor's own docs page on 2026-10-16. The vendor sites could not be opened from
  the 2026-10-17 session, so nothing new was verified that day.
- **[UNVERIFIED]**: check it yourself before trading money.

Read the vendor guides first:
- TradersPost for MFFU: https://blog.traderspost.io/article/automate-my-funded-futures-with-traderspost
- PickMyTrade webhooks: https://blog.pickmytrade.io/tradingview-webhook-automation-trading-alerts/

Where their steps differ from mine, follow theirs.

---

## What changed on 2026-10-17 (evening lock)

The script now trades the **locked strategy**, the same rules as the Python bot (`live_model.json`, `STRATEGY.md`,
locked 2026-10-17 evening for Monday 2026-10-19):

| Setting (Inputs tab) | Old | **New default** |
|---|---|---|
| Risk per trade ($) | 350 | **800** |
| Full risk up to a stop of (pts) | (none) | **20**: wider stops risk less, $800 x 20 / stop (a 40-pt stop risks $400) |
| Max trades / day | 2 | **1** |
| Cap risk at a fraction of the MLL cushion | on | **off** (under "Old rules") |
| Grade sizing A+..D | on | **off** (under "Old rules") |
| No major pool in range: fixed-R target | on (2R) | **off**: no target = no trade |
| Size in a cold streak | (none) | **0.25**: if the last 15 closed trades add up to 0R or less, the trade is still taken at a **quarter** of the size (the morning lock had half) |
| Size on a late entry | (none) | **0.5**: when the 15-minute structure had already turned the trade's way at the signal, **half size** |
| Breakeven at (R) on trending days | (none: 1R every day) | **3**: on a trending day (10-day efficiency above 0.45, the same test that halves the size) the stop moves to breakeven at +3R instead of +1R |
| Alert format | bridge JSON | **choice: Bridge JSON or Phone text** |

Also new:
- A **status box** (top right) shows the version ("eval mode 2026-10-17 evening"), the risk rule ("late entry x0.5 · BE
  1R (3R trending)"), the cold-streak state and today's trades.
- Entry labels show the size, "cold" and "late" when the size was cut.

Size = micros = risk ÷ (stop points × $2), rounded down, max 40, halved in a trending market. Then the cuts: cold
streak × 0.25, late entry × 0.5, multiplied and rounded down once, never below 1 micro (`engine/sizing.py`). A
40-micro trade in a cold streak that is also late becomes 5.

**Cold streak on TradingView.** TradingView only knows the trades on the loaded chart (about 8 weeks, roughly 15-25
trades), so it is at full size until 15 trades have closed there ("warming up" in the status box). The Python bot uses
its own record. Once the chart holds 15 closed trades, both look at the same last 15 trades. If the box disagrees with
the Python dashboard, use input *Override* (Always full size / Always cold), then re-create the alert.

Parity proof (research/PINE_PARITY.md):
- On the same bars, the script's replica and the Python engine agree on every trade, size and dollar: 22/22 in the
  8-week TradingView window, 780/780 over 5 years, the quarter-size cut on the same 373 trades and the late-entry cut on
  the same 102.
- TradingView trades **MNQ1!** prices and the Python bot **NQ1!** prices. Those differ by a tick or two, so now and
  then one of them takes a different trade or size (3 of 22 trades in the 8-week window, plus one late-entry flag).

---

## Sunday checklist (before Globex opens, 18:00 ET)

1. **MFFU's written OK first.** Ask MFFU support in writing, before anything can touch the eval account: *"Is
   TradersPost (or PickMyTrade) through Tradovate allowed on the Builder 50K, and is fully automated execution OK if I am
   present and monitoring?"* Keep the reply. No OK = use the phone-text route (you place every order yourself).
2. **Paste the script.**
   - TradingView > Pine Editor > open your saved "Liquidity Engine - Sweep IFVG DOL" (or New > Strategy).
   - Select all, paste the whole of `tradingview/liquidity_engine.pine`, Save.
   - If it shows an error, see "If the script does not compile" at the end.
3. **Chart:**
   - Symbol **MNQ1!** (CME micro Nasdaq), **5 minutes**, extended hours **on** (ETH).
   - Chart timezone **New York**.
   - Add the strategy to the chart. Leave every input at its default.
4. **Strategy Tester check.**
   - The status box must read "Liquidity Engine eval mode 2026-10-17 evening".
   - Then compare the List of trades with `research/pine_parity/expected_tv_trades_locked_2026-10-16.csv`. From about
     Aug 26 to Oct 13, every trade should be there with the same time, side, size and exit:
     - 08-27 11:20 short 33 micros, target, +$3,910.50
     - 08-31 09:40 short 5 micros (label "late": half size), stop, -$290.00
     - 09-17 14:45 long 29 micros, target, +$3,973.00
     - 10-12 14:15 long 16 micros, stop, -$736.00
     - the full list is in research/PINE_PARITY.md
   - With history starting Aug 23 18:00, the totals are 22 trades, **+$13,733.50**, profit factor **7.33**, 45.45% winners,
     commission $288.00. (The morning lock's script gave +$13,190.50 and PF 5.86 here.)
   - Your chart starts a little later (TradingView keeps a fixed number of bars), so the first 1-3 trades may be
     missing. Totals then shrink, but the remaining trades stay identical.
   - The Oct 16 afternoon should add no trade.
   - Optional exact check: Strategy Tester > List of trades > Export, then on the PC
     `python -X utf8 tools/pine_parity.py <export>.csv --from <first day on the chart> --py-bars data/tv_mnq_5m_2026-10-16.csv`.
5. **Choose the route** (section 1) and set the *Alerts* inputs:
   - **Bridge JSON** + *Bridge* TradersPost or PickMyTrade (PickMyTrade also needs its token and account_id), or
   - **Phone text**.
6. **Create the ONE alert** (section 3). For a bridge, use its **paper / Tradovate demo** connection first, never the
   eval account.
7. **Test on the sim first.**
   - Let Monday's first signal run on the bridge's paper account or the Tradovate / MFFU sim.
   - Check the whole cycle: entry with stop and target visible in Tradovate, the breakeven move, the exit, and nothing
     left working afterwards.
   - Phone text: practise placing one bracket order on the sim from a push.
8. **Only then, with MFFU's OK and while you are present:** switch the bridge subscription to the MFFU eval account
   (section 4).
9. **Every weekend:**
   - Refresh the news list (section 3).
   - Re-create the alert after **any** input change. An alert keeps the inputs it was created with.

---

## 1. Choose the route

| | TradersPost | PickMyTrade | Phone text |
|---|---|---|---|
| Cost | Starter $41.65/mo, Basic $84.15, Pro $169.15, Premium $254.15 (billed yearly); 7-day trial. Only Premium is listed with "all" asset classes: check that your plan includes **futures** [verified: traderspost.io/pricing] | Flat $50/mo, 7-day trial, no card [verified: pickmytrade.io/pricing] | **free** (TradingView Plus is enough) |
| MFFU | MFFU-specific guide (link above) [content UNVERIFIED] | Tradovate prop-firm focus; MFFU not named in its 2026-10-16 docs [UNVERIFIED] | always allowed: you place the order |
| Orders | market entry with bracket (`stopLoss.stopPrice` + `takeProfit.limitPrice`) [verified]; breakeven = `"action":"breakeven"` [verified]; exit = `"action":"exit"` [verified] | `sl` / `tp` prices (pick "Price from TradingView" in its alert generator) [partly verified]; stop move = `update_sl: true` [key verified]; close = `"data":"close"` [keys verified, whole payload UNVERIFIED] | you type them in Tradovate |
| Paper mode | paper accounts on every plan [verified] | use the Tradovate demo / MFFU sim [UNVERIFIED] | Tradovate sim |
| Needs you there | MFFU requires presence for automation | same | yes, for every order |
| Script input | *Alert format* Bridge JSON, *Bridge* TradersPost | *Alert format* Bridge JSON, *Bridge* PickMyTrade + token + account_id | *Alert format* Phone text |

**Recommendation: TradersPost**:
- its signal format (bracket prices, `breakeven`, `exit`) is fully documented and is the script's default;
- it has an MFFU guide.

Pick **PickMyTrade** if it is cheaper for you or MFFU names it. Compare one alert the script makes (section 6) with the
JSON from PickMyTrade's own "Generate Alert" button before trusting it.

Keep **phone text** as the free fallback for days the bridge is down, or before MFFU's OK arrives.

## 2. Connect the bridge to MFFU / Tradovate

**TradersPost** (from its docs; follow its MFFU guide where it differs):
1. Sign up at traderspost.io and choose a plan that includes futures.
2. *Brokers* > *Add broker* > **Tradovate**:
   - choose **Demo** first;
   - log in with your **MFFU Tradovate** credentials on Tradovate's own page (TradersPost never sees the password).
   - Later repeat for the account your MFFU eval actually lives in [UNVERIFIED whether that is Tradovate "demo" or
     "live"; the MFFU guide says].
3. *Strategies* > *New strategy* > "Liquidity Engine" > copy the **webhook URL**. It is a secret: put it only into the
   TradingView alert.
4. *Subscriptions* > subscribe the strategy to the **paper / demo** account first. In the subscription settings:
   - let the signal set quantity, stop and target ("signal override"; the exact name may differ) [UNVERIFIED];
   - set futures, with ticker MNQ.
   - TradersPost maps continuous symbols on its own roll schedule. For full control, set the script input *Ticker* to
     the contract, e.g. `MNQZ2026`, and change it at each quarterly roll, about 8 days before the 3rd-Friday expiry
     (Dec 2026: 2026-12-10).

**PickMyTrade:**
1. Sign up and connect Tradovate (demo / sim first).
2. *Generate Alert* for MNQ: quantity from TradingView, SL/TP "Price from TradingView".
3. Copy:
   - the **webhook URL** into the TradingView alert;
   - the **token** and **account_id** into the script inputs *PickMyTrade token* / *account_id* (on TradingView only,
     never in the repo or a chat).

## 3. The strategy inputs and the ONE alert

1. **Inputs.**
   - Leave *Risk and size*, *Cold-streak filter*, *Old rules* and *Model* at their defaults: they equal the Python bot
     (risk $800 to a 20-pt stop, late entry x0.5, cold streak x0.25, breakeven at 1R or 3R on trending days).
   - *Alerts*:
     - *Alert format* (Bridge JSON / Phone text);
     - *Bridge* (TradersPost / PickMyTrade);
     - *Ticker* (`MNQ` or the explicit contract);
     - *Alert when TradingView's own stop/target fills* ON;
     - *Alert the breakeven stop move* ON.
   - *Model*: *Shift remembered levels at contract rolls* ON.
   - *News blackout*: the release list comes prefilled from the engine's calendar. It is complete through mid-November
     2026, then FOMC only. Refresh it every weekend on the PC (one line per release; `;` also works):
     ```
     python -X utf8 tools/pine_news.py --from 2026-08-01
     ```
     Paste the output over the old list. Starting at 2026-08-01 keeps the backtest window's releases, so the Strategy
     Tester stays comparable.
2. **Create the alert:** Alerts > **+**.
   - Condition: *Liquidity Engine - Sweep IFVG DOL* > **Order fills and alert() function calls**. The breakeven message
     uses `alert()`.
   - Expiration: as long as your plan allows (open-ended if offered) [UNVERIFIED for Plus]. An expired alert stops
     trading without warning.
   - Message: exactly
     ```
     {{strategy.order.alert_message}}
     ```
   - Notifications:
     - **Bridge:** tick **Webhook URL** and paste the bridge URL. Also tick *Notify in app*, so your phone shows every
       order.
     - **Phone text:** tick **Notify in app** (the TradingView app on your phone, logged in, notifications allowed).
       Email is a good backup.
   - Create.
3. **TradingView account:**
   - Webhooks need a paid plan (Plus is fine).
   - TradingView requires **two-factor authentication** before it sends to a webhook URL [UNVERIFIED: long-standing
     rule]. Turn it on: Profile > Settings > Security.
4. **An alert is a snapshot of the script and its inputs.** After *any* change (an input, the news list, a new version
   of the script), delete the alert and create it again. Otherwise the old settings keep trading.

## 4. Sim first, then MFFU

1. Run on the bridge's **paper / Tradovate demo** connection (or by hand on the Tradovate sim for phone text) for at
   least one full signal. Check:
   - the entry with its stop and target in Tradovate;
   - the breakeven move;
   - the exit: bracket fill, time stop, giveback or the 15:55 flat.
2. After every exit, check in Tradovate that **no stop or limit order is left working**. Every exit sends `"cancel":
   true` (TradersPost); whether the remaining bracket leg is always cancelled is [UNVERIFIED]. A leftover stop can open
   a new position.
3. With MFFU's written OK, switch the subscription to the MFFU eval account (or add a second subscription and pause the
   paper one). Nothing changes in TradingView.

**Trading the phone texts by hand:**
- **Entry:** place it within a minute of the push: market order + stop + target at the prices in the text (a bracket /
  OSO order in Tradovate). If price is already beyond the stop or the target, skip it.
- **"MOVE STOP to ... (breakeven)":** move your stop to that price.
- **"CLOSE ... at market":** close the whole position (time stop, giveback, 15:55, news).
- **"STOP HIT" / "TARGET HIT":** TradingView's copy closed. Check that your broker position is flat too, and that no
  order is left.

## 5. Pause, kill switch, oversight

- **Pause (no new trades):** TradingView > Alerts > the alert > **Pause**.
  - An open position keeps its broker bracket.
  - Pausing also stops the bot's exit messages (time stop, giveback, 15:55 flat), so close any open trade yourself.
- **Kill switch:** do all three; any one alone leaves a path for a new order.
  1. In Tradovate (web or app): **Exit at Mkt & Cxl**, i.e. flatten MNQ and cancel all working orders.
  2. Pause or delete the TradingView alert.
  3. Pause the subscription in the bridge.
- **MFFU oversight:** automation is allowed only while you are **present and actively monitoring** (README, "MFFU
  Builder 50K notes").
  - Computer-off means the bot does not *need* your PC; it does not mean unattended.
  - Keep the Tradovate app with notifications on.
  - Keep the $1,000 DLL and the $2,000 EOD trailing MLL in mind. The script's $600 daily stop uses TradingView's
    simulated fills, not the broker's.

## 6. What the alerts send

Real messages from the replica, for the 2026-09-17 14:45 long:
- 29 micros, stop 29,703.25, target 29,785.75, risk $798;
- breakeven at 15:05;
- target filled at 15:50.

**TradersPost** (default)
```json
{"ticker":"MNQ","action":"buy","quantity":29,"orderType":"market","signalPrice":29717,"stopLoss":{"type":"stop","stopPrice":29703.25},"takeProfit":{"limitPrice":29785.75}}
{"ticker":"MNQ","action":"breakeven","orderType":"stop"}
{"ticker":"MNQ","action":"exit","orderType":"market","cancel":true,"extras":{"reason":"bracket"}}
```
`reason` is one of:
- `TIME STOP`, `GIVEBACK`, `FLAT` (15:55), `NEWS FLAT`;
- `bracket`: TradingView's own stop/target filled; sent so the broker is flat too, and harmless if the broker bracket
  already closed the trade.

**PickMyTrade** (*Bridge* = PickMyTrade; field set taken from docs.pickmytrade.trade, **UNVERIFIED as a whole**; token
and account_id come from your inputs, empty here)
```json
{"symbol":"MNQ","date":"2026-09-17T18:45:00Z","data":"buy","quantity":29,"risk_percentage":0,"price":29717,"tp":29785.75,"percentage_tp":0,"dollar_tp":0,"sl":29703.25,"dollar_sl":0,"percentage_sl":0,"trail":0,"trail_stop":0,"trail_trigger":0,"trail_freq":0,"update_tp":false,"update_sl":false,"token":"","pyramid":false,"same_direction_ignore":true,"reverse_order_close":false,"account_id":""}
{"symbol":"MNQ","date":"2026-09-17T19:05:00Z","data":"buy","quantity":29,...,"sl":29716.75,...,"update_sl":true,...}
{"symbol":"MNQ","date":"2026-09-17T19:50:00Z","data":"close","quantity":29,...,"sl":0,...,"full_closed":true,"account_id":""}
```

**Phone text**
```
LONG 29 MNQ at market · stop 29,703.25 · target 29,785.75 · risk $798
MOVE STOP to 29,716.75 (breakeven) · LONG 29 MNQ · target 29,785.75 stays
TARGET HIT · LONG 29 MNQ closed at 29,785.75 · check your broker: flat, no orders left
```

Other phone texts:
```
SHORT 5 MNQ at market · stop 29,426.25 · target 29,273.75 · risk $278 · half size (late entry)
LONG 1 MNQ at market · stop 30,844.50 · target 31,086.25 · risk $116 · quarter size (cold streak)
LONG 1 MNQ at market · stop 31,147.00 · target 31,263.50 · risk $84 · quarter size (cold streak) · half size (trending market)
SHORT 1 MNQ at market · stop 31,213.50 · target 30,965.75 · risk $116 · half size (trending market)
CLOSE SHORT 1 MNQ at market · giveback: was +0.5R, closed back through the entry
CLOSE LONG 12 MNQ at market · time stop: not +0.5R after 30 min
CLOSE LONG 12 MNQ at market · end of day: be flat by 15:55
BREAKEVEN STOP HIT · SHORT 5 MNQ closed at 30,579.00 · check your broker: flat, no orders left
```
"risk $" is the dollars at risk at the size sent (after the cuts).

**Breakeven.** At +1R (+3R on a trending day) the strategy moves its own stop to entry ± 1 tick (Python rule) and sends
the breakeven message once.
- TradersPost's `breakeven` puts the broker stop **at** the average entry, one tick looser than the model.
- If the bridge ignores the message, TradingView's own breakeven stop still fills when price returns to entry + 1 tick,
  and the synced exit closes the broker position with a market `exit`. That exit goes out when TradingView sees the
  fill, so expect a few ticks of slippage.
- Exactly when a strategy fill alert fires in real time (on the tick or at the bar close) is [UNVERIFIED].

**Sizing.** `quantity` is in MNQ contracts (micros), sized like the Python bot (see "What changed on 2026-10-17").
On an NQ1! chart the same code would size in NQ minis: use **MNQ1!**.

---

## 7. Pine vs Python differences

Source of truth: `engine/model.py` and `live_model.json`. Parity is measured, not assumed:
- `tools/pine_sim.py` replays the script bar by bar, including TradingView's fill model;
- `tools/pine_parity.py` diffs a TradingView trade list against `engine.backtest`.

Details and numbers: `research/PINE_PARITY.md`.

**Status 2026-10-17 evening (locked strategy).**
- **Same bars, both sides:**
  - 8-week MNQ1! window: 22/22 trades, sizes and dollars equal (+$13,733.50).
  - 5 years: 780/780, the quarter-size cut on the same 373 trades and the late-entry cut on the same 102, net equal to
    the cent (+$37,362.00 with MNQ commissions).
- **Replaying the unadjusted contract with the roll shift** (what TradingView sees, 20 rolls) gives the identical 780
  trades.
- **Against the official baseline** (`research/runs/baseline.json`, the live-loop replay):
  - 2026: 89 trades, PF 3.86 vs 3.94, +$20,110 vs +$20,487, the same eval odds (1 month: 31.6% pass, 0% fail).
  - 2021-25: PF 1.24 vs 1.27, +$15,001 vs +$16,379.
  - 5 years: PF 1.50 vs 1.54.

### Remaining differences (Pine cannot do it, or it is deliberate)
1. **Data feed (the main one).** TradingView trades MNQ1! prints; the Python bot uses NQ1! (`data/NQ_5m.csv`, NinjaTrader
   MNQ live). A tick or two apart, so a trigger, a stop distance or the 15m "late entry" flag can change.
   - In the 8-week window: 3 of 22 trades differ, 4 sizes differ by 1-3 micros, and one trade is a late entry on
     MNQ but not on NQ (2 micros vs 4).
   - On identical bars there is no difference.
2. **Cold-streak record.** TradingView only counts the trades on the loaded chart, so it is at full size until 15
   trades have closed there. The Python bot reads its shadow ledger.
   - R per trade differs by commission only: at most 0.05R per trade, never a different full/cold decision in 5 years.
   - Use input *Override* if the two disagree.
3. **Commission.** Python books 10+ micros as NQ minis ($4.50 round turn per mini vs $1.50 per micro). Pine and the
   bridge trade MNQ only: same risk, about $1.9k more commission over 5 years.
4. **News source.** Python reads the archived Forex Factory calendar automatically. Pine only knows the list in its
   input:
   - prefilled to mid-November 2026, then FOMC only;
   - refresh it weekly (section 3) and re-create the alert after every change;
   - this is the item most likely to break live parity.
5. **Walk-forward exit learner** (`exit_learn`, Python only). Python may start acting on another exit signal once it has
   proven itself (>= 20 cases and >= +0.2R).
   - With the live settings it never acted in 5 years.
   - Check `engine.backtest.run(...)["exit_signals"]`: any `learned: true` row means Python now exits differently from
     TradingView.
6. **Live-loop window.** The live Python bot re-runs the engine on the last 20 days at every poll (its 20-day average
   range sees about 14 sessions). TradingView runs straight through its chart. Over 5 years, 766 of 768 entries are the
   same.
7. **Roll in real time [UNVERIFIED].**
   - In a backtest, or whenever TradingView recalculates the script, the roll shift reproduces the engine exactly.
   - Whether a *running* alert sees the back-adjusted series restated at the next roll (MNQZ26 -> MNQH27, around Dec
     10-14 2026) is not verified. If it does not, pre-roll levels and the regime flag are off by the gap for up to ~10
     trading days.
   - Re-create the alert on the first evening after the roll; that recalculates the history.
8. **Gap through stop/target at the fill bar's open.** Python cancels the order; TradingView fills it and the bracket
   closes it at the open. Never happened in the tested windows.
9. **Stop and target touched in the same bar.** Python assumes the stop first; TradingView follows its OHLC path rule.
   No difference in the tested windows.
10. **Holiday early closes.** In backtests Python flattens on the last bar of the trading day; Pine uses
    `session.islastbar`. Whether TradingView flags a holiday's early last bar in real time is [UNVERIFIED].
11. **Live fills.** Everything above compares backtest with backtest. Live, entries are market orders sent at the bar
    close, and the bridge, Tradovate and slippage add their own differences.
12. **Account state is simulated.** The daily stop and stop-after-win use TradingView's strategy equity, not the
    broker's (true of the Python bot too).
13. **Weight-0 or switched-off features are not ported** (no effect): SMT, protected level, AMT, MTF, gamma, VIX,
    news-day context, partials, trailing, the trend-day model, the learner gate.

---

## If the script does not compile

There is no Pine compiler outside TradingView, so the 2026-10-17 script has not been compiled yet. Everything it uses
already compiled on 2026-10-16 except the items below (the evening changes only add inputs, one more element to a tuple
that already compiled with nine, and plain arithmetic). TradingView's editor names the line; fix only that line.

| Error mentions | Fix |
|---|---|
| `alert_profit` or `alert_loss` (4 `strategy.exit` calls) | Delete the `alert_profit=...` and `alert_loss=...` arguments. Bridge JSON is unchanged; phone text then says "STOP OR TARGET HIT" instead of naming which |
| `math.round` with two arguments (in `f_tradeR`, `f_coldState`) | Replace `math.round(x, 3)` with `math.round(x * 1000) / 1000` and `math.round(x, 2)` with `math.round(x * 100) / 100` |
| `table` / `text_halign` (status box at the end) | Delete the status-box block (from `var table stBox` to the end), or turn off input *Show the status box* |
| Odd characters in the phone text (`·`) | Replace `·` with `-` in the strings |
| Numbers like `29,880.25` look wrong | Change `"#,##0.00"` to `"#.00"` and `"#,##0"` to `"#"` in `f_px` / `f_usd` |

After any fix:
- check the Strategy Tester against the checklist numbers;
- tell the next session which line you changed, so `tools/pine_sim.py` stays in sync.
