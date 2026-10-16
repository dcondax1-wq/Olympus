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
2. **Parity check against the Python engine.** Strategy Tester > *List of trades* > Export (CSV). Set the chart
   timezone to New York first. Then:
   ```
   python -X utf8 tools/pine_parity.py "%USERPROFILE%\Downloads\<export>.csv"
   ```
   The tool prints every trade side by side (entry time within 10 min, side, exit class, R) plus a parity score.
   The Python CSVs are Yahoo NQ=F and TradingView uses CME MNQ1!: expect most, not all, trades to match. Treat any
   `PY ONLY` / `TV ONLY` row inside an entry window as something to look at before going live.
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
   stop/target fills* ON, *Send a breakeven stop modification* ON. News group: paste this week's high-impact USD
   releases, one per line, e.g.
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

Source of truth: `engine/model.py` DEFAULTS, `_plan`, `_grade`, `_size`, `run()` exit block.

### Closed in this revision
1. **Grade sizing** A+..D replaces conviction sizing. Every checklist item with a non-zero weight is ported: 1H
   structure (+2/-1), 1H discount/premium (x`g_pd`=2, +/-), VWAP side (+/-2), volume climax on the raid (-2,
   exact definition: max volume from the sweep bar to the extreme >= 1.5x the 20-bar average before the sweep),
   LRL/HRL (+1/-2), opening hour (-1), 15m already aligned (-1), Q2 sweep (+1), raid beyond the 90-min true open
   (+/-1), day stretched >= 1.2x ADR (-1), first 45 min of the session (-`g_early`=2), Q3 entry (-`g_q3`=1).
2. **Trending-regime half size** (10-day efficiency of daily closes > 0.45), plus the `skip` mode.
3. **MLL-aware risk cap** (`dd_aware`, 25% of the cushion above the EOD trailing $2,000 MLL, locks at $50,100).
4. **Day-range filter** (`day_range_max` 1.6x the 20-day average range).
5. **News blackout**: pasted release list, 15 min before / 30 after, FOMC afternoon off, flatten 5 min before.
6. **1H / 15m structure** is now built from the chart's own 5m bars and processed on the 5m bar that completes the
   HTF candle, as Python does. The old `request.security(..., lookahead_on)[1]` saw it one 5m bar late. It also
   adds Python's protected-low/high trend flips, which were missing.
7. **Equal highs/lows** (within 6 pts) are now major pools / draw-on-liquidity targets (they were missing).
8. **Path obstacles** count 1H swings as well as 15m swings (Python `ITH/ITL/H1H/H1L`).
9. **Pool merging** follows Python's strength order (the stronger kind decides lifetime / swing / EQ eligibility).
10. **CISD level**: the run is only extended when the extreme candle itself closed down (it was always extended),
    and it stops one bar short of the leg origin (off-by-one). CISD may also fire on the extreme bar itself.
11. **Leg origin tie-break**: on equal highs the oldest bar wins (np.argmax), not the newest.
12. **Setup consumption**: a too-wide stop or a size below 1 contract disarms the setup, as in Python.
13. **Bracket live on the fill bar**: `strategy.exit` is placed with the entry. Before, the fill bar had no
    stop/target in the backtest.
14. **Giveback** may fire on the entry bar (Python does).
15. **Target fills** need a 1-tick trade-through (`touch_ticks` 1) via `backtest_fill_limits_assumption=1`.
16. **PDH/PDL** are not added when the first bar of the new day already traded through them.
17. **Exit precedence**: one exit per bar in Python's order (flat time > news flat > time stop > giveback, then
    BE). Time stop is counted in bars, so it is correct on any chart timeframe.

### Remaining (Pine cannot do it, or it is deliberate)
1. **Walk-forward exit learner** (`exit_learn`, seeded from `data/memory.db`): Python may start acting on another
   exit signal once its counterfactual gain is proven. Pine only has the fixed `giveback` rule. Same trades as long
   as `engine.backtest.run(...)["exit_signals"]` shows no `learned: true` row.
2. **News source**: Python reads the archived Forex Factory calendar automatically. Pine only knows what you paste
   and needs the alert re-created each week.
3. **Fill model**: Python fills entries at the next open +1 tick and bot exits at the signal-bar close -1 tick.
   TradingView fills market exits at the next bar's open (+1 tick). This is usually a few ticks; the parity tool
   compares R with a 0.3R tolerance.
4. **Gap through stop/target at the fill bar's open**: Python cancels the order, TradingView fills it.
5. **Data**: Python bars are Yahoo NQ=F (60-day window), Pine uses CME MNQ1! with full history. Different prints
   create or remove a sweep now and then. This is the main source of PY ONLY / TV ONLY rows.
6. **Contract split**: Python routes 12 micros as 1 NQ + 2 MNQ. Pine sends 12 MNQ (same risk, slightly higher
   commission).
7. **SMT, protected-level, AMT, MTF, gamma, VIX and news-day context**: weight 0 in DEFAULTS, so no effect. Not ported.
8. **Account state is simulated**: daily stop, stop-after-win and the MLL cushion use TradingView's strategy
   equity, not the broker's (true of the Python bot too).
9. **Partials, trailing, trend-day model, learner gate**: all off in DEFAULTS, not ported.
