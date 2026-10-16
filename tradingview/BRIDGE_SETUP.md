# Live via TradingView + a webhook bridge (computer OFF)

The strategy runs as a Pine v5 **strategy** on TradingView's servers. Every order fill in the strategy fires a
webhook alert to a bridge (TradersPost or PickMyTrade). The bridge is connected to the MFFU Tradovate account by
OAuth and places the order there. Your PC, the Python bot and the dashboard are not involved. Tradovate does not
issue API keys for prop/evaluation accounts, so the direct REST adapter (`engine/tradovate.py`) cannot be used here.

```
MNQ1! 5m chart (TradingView servers) --order fill--> alert {{strategy.order.alert_message}} --webhook--> bridge --OAuth--> Tradovate (MFFU)
```

Legend: **[verified]** = checked against the vendor's own docs page on 2026-10-16 (link given).
**[UNVERIFIED]** = could not be confirmed from the vendor docs: check it yourself before trading money.

---

## 0. Before Sunday: one-time checks (about 1 hour)

1. **Compile the script.** I could not compile Pine here (TradingView has no offline compiler). Open TradingView >
   Pine Editor > New > paste `tradingview/liquidity_engine.pine` > Save > *Add to chart* on **MNQ1! 5m**.
   Parameters that are newer Pine features and the most likely to error if your editor is older:
   `strategy.exit(comment_profit=, comment_loss=, disable_alert=)` and `strategy(backtest_fill_limits_assumption=)`.
   If one of these errors, delete that argument; the only effect is weaker labels in the trade list (the parity
   tool falls back to inferring the exit class from the result).
2. **Parity check against the Python engine.** Done on 2026-10-16 for Aug 24 - Oct 16 (research/PINE_PARITY.md):
   the Strategy Tester shows 25 trades, +$8,784.50, PF 6.76, and all 25 match Python's entries, exit classes and
   R. To repeat it after any change: Strategy Tester > *List of trades* > Export (CSV), with the chart timezone
   set to New York. Then:
   ```
   python -X utf8 tools/pine_parity.py "%USERPROFILE%\Downloads\<export>.csv"
   ```
   The tool prints every trade side by side (entry time within 10 min, side, exit class, R) plus a parity score.
   Expect 100%. Any `PY ONLY` / `TV ONLY` row means the script on the chart is not the repo version, or one of
   the section 7 differences fired. `tools/pine_sim.py` replays the script bar by bar to find out which.
3. **TradingView plan + 2FA.** Webhook alerts need a paid TradingView plan, and TradingView requires
   **two-factor authentication** on the account before it will send to a webhook URL **[UNVERIFIED: I could not
   load TradingView's help pages; this is TradingView's long-standing rule]**. Profile > Settings > Security >
   Two-factor authentication > enable (authenticator app). Also check how long alerts stay active on your plan
   **[UNVERIFIED]**. An expired alert stops trading without any warning.

## 1. Choose a bridge

| | TradersPost | PickMyTrade |
|---|---|---|
| Price | Starter $41.65/mo, Basic $84.15, Pro $169.15, Premium $254.15 (billed yearly); 7-day trial. Only Premium is listed with "all" asset classes, so check that your plan includes **futures** [verified: traderspost.io/pricing] | Flat $50/mo, 7-day trial, no card [verified: pickmytrade.io/pricing] |
| Tradovate | Supported for prop firms that clear through Tradovate (blog lists Take Profit Trader, Legends, Alpha Futures). **MFFU not named** [UNVERIFIED] | Tradovate listed; prop firms listed: Apex, Topstep, TPT, FundedNext, E8, Tradeify. **MFFU not named** [UNVERIFIED] |
| Bracket on entry | `stopLoss.stopPrice` + `takeProfit.limitPrice` in the signal [verified: docs.traderspost.io webhooks] | `sl` / `tp` fields; docs describe `sl` as ticks/points from entry unless "Price from TradingView" is chosen in the alert generator [partly verified: docs.pickmytrade.trade] |
| Breakeven | `"action":"breakeven"` moves the stop to the average entry price (needs `orderType` stop) [verified] | `update_sl: true` with a new `sl` replaces the stop [verified that the key exists; full payload UNVERIFIED] |
| Exit | `"action":"exit"`; no quantity = close everything [verified] | `"data":"close"`, `reverse_order_close:false`, `full_closed:true` [keys verified, combination UNVERIFIED] |
| Paper mode | Paper accounts on every plan [verified] | **[UNVERIFIED]**: use the MFFU/Tradovate demo or sim account |

**Recommendation: TradersPost.** Its signal schema (bracket prices, `breakeven`, `exit`) is fully documented and is
the default schema in the script. Pick PickMyTrade only if MFFU confirms it and TradersPost does not. Then switch
the script input *Bridge JSON schema* to `PickMyTrade` and compare one generated alert with the JSON PickMyTrade's
own "Generate Alert" button produces before trusting it.

Ask MFFU support in writing: "Is TradersPost (or PickMyTrade) via Tradovate OAuth allowed on the Builder 50K, and
is fully automated execution OK if I am present and monitoring?" Keep the reply.

## 2. Connect the bridge to MFFU / Tradovate

TradersPost (from its docs; the screens may differ slightly):
1. Sign up at traderspost.io, choose a plan that includes futures.
2. *Brokers* > *Add broker* > **Tradovate** > choose **Demo** first > log in with your **MFFU Tradovate**
   credentials on Tradovate's own OAuth page (TradersPost never sees the password). Repeat later for **Live**
   (the MFFU account is a Tradovate "live" connection even though it is an evaluation) **[UNVERIFIED which of
   demo/live MFFU eval accounts appear under]**.
3. *Strategies* > *New strategy* > name it "Liquidity Engine" > copy the **webhook URL**.
4. *Subscriptions* > subscribe the strategy to the Tradovate **paper/demo** account first. In the subscription
   settings: **Allow signal override ON** (so the quantity and bracket prices in the JSON are used), futures,
   ticker mapping MNQ1!/MNQ -> the front month (TradersPost says continuous symbols are mapped on *its* rollover
   schedule; for full control set the script input *Bridge ticker* to the explicit contract, e.g. `MNQZ2026`, and
   change it at each quarterly roll, about 8 days before the 3rd-Friday expiry: Dec 2026 -> 2026-12-10).

PickMyTrade: sign up > connect Tradovate (OAuth) > *Generate Alert* for MNQ, quantity from TradingView, SL/TP
"Price from TradingView" > copy the webhook URL, the `token` and the `account_id` into the script inputs.

## 3. Strategy + the ONE alert

1. Chart: **MNQ1!**, **5 minutes**, regular CME data. Add *Liquidity Engine - Sweep IFVG DOL*.
2. Inputs: leave the Risk/Model defaults (they equal `engine/model.py` DEFAULTS). Alerts/bridge group:
   *Bridge JSON schema*, *Bridge ticker* (`MNQ` or the explicit contract), *Send an exit when TradingView's own
   stop/target fills* ON, *Send a breakeven stop modification* ON. *Shift remembered levels at contract rolls* ON.
   News group: the release list comes prefilled from the engine's calendar. It is complete through mid-November
   2026 and has only FOMC dates after that. Refresh it every weekend (one line per release, `;` also works):
   ```
   python -X utf8 tools/pine_news.py --from 2026-08-01
   ```
   and paste the output over the old list. Starting at 2026-08-01 keeps the backtest window's releases, so the
   Strategy Tester stays comparable. Lines look like:
   ```
   2026-10-21 08:30 CPI
   2026-10-29 14:00 FOMC
   ```
3. Create the alert: Alerts > **+** > Condition: *Liquidity Engine - Sweep IFVG DOL* > **Order fills and alert()
   function calls** (the breakeven modification uses `alert()`) > Expiration: as long as your plan allows >
   Message: exactly
   ```
   {{strategy.order.alert_message}}
   ```
   > Notifications: **Webhook URL** = the bridge URL (also tick app notification so your phone shows every order)
   > Create.
4. **An alert is a snapshot of the script and its inputs at creation time.** After *any* input change (including
   the weekly news list) delete the alert and create it again, otherwise the old settings keep trading.

## 4. Paper first, then MFFU

1. Run on the bridge's **paper / Tradovate demo** subscription for at least one full signal: entry with stop and
   target visible in Tradovate, then either the bracket fill or a bot exit (time stop / giveback / 15:55 flat).
2. Check in Tradovate after every exit that **no stop or limit order is left working** (`"cancel": true` is sent
   with every exit; whether TradersPost cancels the remaining bracket leg on an `exit` is **[UNVERIFIED]**. A
   leftover stop can open a new position.)
3. Switch the TradersPost subscription to the MFFU account (or create a second subscription and pause the paper
   one). Nothing changes in TradingView.

## 5. Pause, kill switch, oversight

- **Pause (no new trades):** TradingView > Alerts > the alert > **Pause**. An open position keeps its broker bracket.
  Pausing also stops the bot's exit messages (time stop, giveback, 15:55 flat), so close any open trade yourself.
- **Kill switch:** (1) in Tradovate (web or app) **Exit at Mkt & Cxl** / flatten the MNQ position and cancel all
  working orders; (2) pause/delete the TradingView alert; (3) optionally pause the subscription in the bridge.
  Do all three; any one alone leaves a path for a new order.
- **MFFU oversight:** automation is allowed only while you are **present and actively monitoring** (README, "MFFU
  Builder 50K notes"). Computer-off means the bot does not *need* your PC; it does not mean unattended. Keep the
  Tradovate app with notifications on, and keep the $1,000 DLL / $2,000 EOD trailing MLL in mind: the script's
  $600 daily stop and MLL cushion use TradingView's simulated fills, not the broker's.

## 6. What the alerts send

Market entry with an attached bracket, prices tick-rounded (example: long 2 MNQ, stop 24990.25, target 25080):

TradersPost (default)
```json
{"ticker":"MNQ","action":"buy","quantity":2,"orderType":"market","signalPrice":25020,"stopLoss":{"type":"stop","stopPrice":24990.25},"takeProfit":{"limitPrice":25080}}
{"ticker":"MNQ","action":"exit","orderType":"market","cancel":true,"extras":{"reason":"GIVEBACK"}}
{"ticker":"MNQ","action":"breakeven","orderType":"stop"}
```
`reason` is one of `TIME STOP`, `GIVEBACK`, `FLAT` (15:55), `NEWS FLAT`, `bracket` (TradingView's own stop/target
filled: sent so the broker is flat too; harmless if the broker bracket already closed the trade).

PickMyTrade (input *Bridge JSON schema* = PickMyTrade; field set taken from docs.pickmytrade.trade, **UNVERIFIED as a whole**)
```json
{"symbol":"MNQ","date":"2026-10-21T14:05:00Z","data":"buy","quantity":2,"risk_percentage":0,"price":25020,"tp":25080,"percentage_tp":0,"dollar_tp":0,"sl":24990.25,"dollar_sl":0,"percentage_sl":0,"trail":0,"trail_stop":0,"trail_trigger":0,"trail_freq":0,"update_tp":false,"update_sl":false,"token":"<token>","pyramid":false,"same_direction_ignore":true,"reverse_order_close":false,"account_id":"<account>"}
{"symbol":"MNQ","date":"...","data":"close","quantity":2,...,"sl":0,"tp":0,...,"reverse_order_close":false,"full_closed":true,"account_id":"<account>"}
{"symbol":"MNQ","date":"...","data":"buy","quantity":2,...,"sl":25020.25,"tp":25080,"update_sl":true,...}
```

**Breakeven.** At +1R the strategy moves its own stop to entry +/- 1 tick (Python rule) and sends the breakeven
message once. TradersPost's `breakeven` puts the broker stop **at** the average entry (one tick looser than the
model). If the bridge ignores the modification, the fallback still protects the trade: TradingView's own BE stop
fills when price returns to entry +1 tick and *sync exits* sends a market `exit`. That exit is sent when
TradingView sees the fill, so expect a few ticks of slippage beyond breakeven. Exactly when a strategy fill alert
fires in real time (on the tick or at bar close) is **[UNVERIFIED]**.

**Sizing.** `quantity` is in MNQ contracts = micros, computed the way the Python bot does it: $350 x grade
multiplier (A+ 1.5, A 1.25, B 1.0, C 0.75, D 0.5), capped at 25% of the cushion above the trailing MLL, halved in a
trending regime, max 40. On an NQ1! chart the same code would size in NQ minis: use **MNQ1!**.

---

## 7. Pine vs Python differences

Source of truth: `engine/model.py` DEFAULTS, `_plan`, `_grade`, `_size`, `run()` exit block. Parity is measured, not
assumed. `tools/pine_sim.py` replays this script bar by bar, including TradingView's fill model, and
`tools/pine_parity.py` diffs a TradingView trade list against `engine.backtest`. Details: `research/PINE_PARITY.md`.

**Status 2026-10-16.**
- **TradingView Strategy Tester** (MNQ1! 5m ETH, Aug 23 - Oct 16 2026): 25 trades, +$8,784.50, PF 6.76, max
  drawdown $380.
- **Python on the same bars:** the same 25 entries, same exit classes, R equal to 0.01. P&L is equal to the cent
  with Python on micro commissions.
- **Five one-year windows, 2021-11 .. 2026-10 (504 trades), replica vs engine:** 100% identical, with remaining
  items 1-3 below switched off on the Python side.

### Fixed 2026-10-16 (TradingView took 8 trades vs Python 25)
1. **1H/15m structure never ran on TradingView (root cause).** It was built with a user-defined type and methods
   (`Struct` / `Agg.feed`), and on TradingView those updates never took effect. The effects:
   - no 1H trend, discount/premium or 15m trend, so every trade scored exactly 1 and grades fell;
   - no 15m/1H swing pools, so 52 setups were armed instead of Python's 144.

   Now it is plain `var` state with the same algorithm.
2. **Pool retirement order.** Stale pools are retired before the prior-day / prior-week pools are added, as in the
   engine. A new prior-week high that landed on an older level used to be merged into it and deleted on the same
   bar.
3. **Contract roll.** At a roll of the continuous contract every remembered level is shifted by the roll gap. That
   covers pools, day/week/session highs and lows, the 1H/15m structure, the regime closes and the armed setups. The
   gap is read from the back-adjusted copy of the symbol
   (`ticker.modify(syminfo.tickerid, backadjustment = backadjustment.on)`). Input *Shift remembered levels at
   contract rolls*. Without the shift, the Sep 14 roll left pre-roll levels 295.5 pts off and set the trending
   half-size flag for days.
4. **Rule exits fill at the signal close.** TIME STOP, GIVEBACK, FLAT and NEWS FLAT use
   `strategy.close_all(immediately = true)`; they used to fill at the next open. They are handled before new
   entries, so a new trigger on the exit bar can be taken, as in the engine. The bot also flattens on
   `session.islastbar` (holiday early closes). The daily stop uses realized P&L.
5. **Swing pools are born at the 1H/15m candle close** (the engine's `t0`). This decides whether a level survives
   a retirement boundary.
6. **News list prefilled** from the engine's calendar (`tools/pine_news.py`). The old default was empty, and over a
   year that alone moves Pine to 71% parity.
7. **Entry comment** carries `sl=` so the parity tool computes R from the actual fill.

Earlier port (commit fdaea88), unchanged: grade sizing A+..D with every non-zero checklist weight, trending-regime
half size / skip, MLL-aware risk cap, day-range filter, news blackout rules, equal highs/lows as major pools, path
obstacles from 1H and 15m swings, pool merging by strength, CISD level and leg-origin tie-break, setup consumption
(too-wide stop, size below 1 contract), bracket live on the fill bar, giveback on the entry bar, 1-tick limit
trade-through, PDH/PDL not added when already traded through, and Python's exit precedence.

### Remaining differences (Pine cannot do it, or it is deliberate)
1. **Walk-forward exit learner** (`exit_learn`, seeded from `data/memory.db`). Python starts acting on another exit
   signal once its counterfactual gain is proven: >= 20 cases and >= +0.2R. Pine only has the fixed `giveback`
   rule. It never fired in the 8-week window. On 2025-10..2026-10 it acted on 12 Python trades (zone_reentry 8,
   opp_fvg 3, two_against 1). Check `engine.backtest.run(...)["exit_signals"]`: any `learned: true` row means
   Python now exits differently from TradingView.
2. **Account reset (backtest only).** After a simulated blown eval (cushion below $250) Python starts a fresh $50k
   account. Pine keeps the dead account and cannot size 1 micro. This only matters in multi-month backtests.
   Live, the eval is simply over.
3. **Mini/micro split.** Python routes 10 or more micros as minis (21 micros = 2 NQ + 1 MNQ) and books mini
   commissions ($4.50 round turn per mini vs $1.50 per micro). Pine and the bridge trade MNQ only: same risk,
   slightly higher commission ($31.50 over the 8-week window). Over long runs near the MLL, that small P&L gap can
   flip a 1-micro sizing decision.
4. **News source.** Python reads the archived Forex Factory calendar automatically. Pine only knows the list in
   its input: prefilled to mid-November 2026, then FOMC only. Refresh it weekly (section 3) and re-create the
   alert after every change. This is the item most likely to break live parity.
5. **Roll in real time [UNVERIFIED].** In a backtest, or whenever TradingView recalculates the script, the roll
   shift reproduces the engine exactly (the Sep 14 2026 roll in this window). Whether a *running* alert sees the
   back-adjusted series restated at the moment of the next roll (MNQZ26 -> MNQH27, around Dec 10-14 2026) is not
   verified. If it does not, the shift is skipped and for up to ~10 trading days pre-roll levels and the regime
   flag are off by the gap. Re-create the alert on the first evening after the roll; that recalculates the history.
   TradingView's own gap may also differ by a few ticks from `data/NQ_rolls.json`.
6. **Gap through stop/target at the fill bar's open.** Python cancels the order; TradingView fills it and the
   bracket closes it at the open. This did not happen in any tested window.
7. **Stop and target touched in the same bar.** Python assumes the stop first; TradingView follows its OHLC path
   rule. This did not produce a difference in any tested window.
8. **Holiday early closes.** In backtests Python flattens on the last bar of the trading day; Pine uses
   `session.islastbar`. Whether TradingView flags a holiday's early last bar in real time is [UNVERIFIED]. A live
   Python bot would not know either.
9. **History.** TradingView loads about 8 weeks; Python warms the 1H structure from years of history. Starting
   Python cold on 2026-08-24 gives the same 25 trades, so this does not matter here.
10. **Live fills.** Everything above compares backtest with backtest. Live, entries are market orders sent when the
    bar closes, and the bridge, Tradovate and slippage add their own differences.
11. **Account state is simulated.** The daily stop, stop-after-win and MLL cushion use TradingView's strategy
    equity, not the broker's (true of the Python bot too).
12. **Weight-0 features and features that are off in DEFAULTS** are not ported: SMT, protected level, AMT, MTF,
    gamma, VIX, news-day context, partials, trailing, the trend-day model and the learner gate. They have no
    effect.
