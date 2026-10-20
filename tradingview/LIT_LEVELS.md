# LIT Levels: the bot's eyes on your TradingView chart

`tradingview/lit_levels.pine` is a TradingView **indicator**. It draws what the LIT bot (`engine/lit.py`, `STRATEGY.md`)
sees on a 5-minute NQ chart: the levels, the sweep, the inducement, the displacement candle, the CISD level, the planned
stop and target, the entry window and whether today's one trade is used.

**It is visual only.** It never places, sends or bridges an order. Its alerts are plain text, or one JSON line you can
compare with the bot's own signal log later.

## Checked against the bot (2026)

Pine can't run here, so `tools/pine_lit_check.py` holds a bar-by-bar Python copy of the indicator. That copy has the
same steps in the same order. It was run on `data/NQ_5m.csv` for **every 2026 trading day (Jan 2 to Oct 16, 206 days)**
and compared with `engine/lit.py`:

| What | Match |
|---|---|
| Levels (11 session boxes, PDH/PDL, PWH/PWL, PMH/PML, NWOG/NDOG) | 6,576 / 6,576 = **100%** (206/206 days identical) |
| Build-ups (equal highs / lows) | 2,636 / 2,636 = **100%** |
| Sweeps that reach a 5m CISD close | 1,325 / 1,325 = **100%** |
| ... swept levels, sweep extreme, sweep bar, CISD level | **100%** each |
| ... depth >= 0.5 ATR, displacement >= 0.8 ATR, inducement taken / count | **100%** each |
| Setups that pass every bot filter (the "armed" ones) | 330 / 330 = **100%** |
| ... planned stop, planned target | **100%** each |
| 5m entries and exits vs the bot's own 5m mode (run_x on 5m bars) | 77 / 77 = **100%**, same exit on all 77 |
| The live bot's 120 trades of 2026 (1m entries, run `lit_live`) | a setup is drawn on **120 / 120** of those day + direction; the 5m entry approximation also fills on 68 / 120 (57%) |

Run it again with `python -X utf8 tools/pine_lit_check.py` (about 5 min; `--days 20` for a quick run; `--lint` for the static
check only). The lint checks balanced brackets, Pine's 4-space blocks and wrapped lines, that only known v5 built-ins are
used, the drawing limits, that `request.security` never looks ahead without a `[1]` (or the guarded VIX read), and that
alerts fire only on closed bars.

**Not verified (no TradingView compiler here):** the file has never been compiled. The Python copy checks the logic, not
the Pine syntax. On first load, look for these 5 things: (1) it compiles with no error, (2) the VIX band in the panel matches
`STRATEGY.md` rule 7 for today, (3) PMH/PML appear early in a month, (4) the 15m/1h order-block and SMT tags appear at all,
(5) the script doesn't time out on a long chart. If it does time out, use a shorter chart history.

## How to add it (2 minutes)

1. Open TradingView, chart **CME_MINI:NQ1!** (or **MNQ1!**), timeframe **5 minutes**, regular **ETH session** (the
   default for futures; the bot uses 18:00-17:00 ET days).
2. At the bottom, click **Pine Editor** → **Open** → **New blank indicator**. Delete everything in it.
3. Open `tradingview/lit_levels.pine` from this repo (on GitHub: the file → **Raw**), select all, copy, and paste it into
   the Pine Editor.
4. Click **Save** (name it "LIT Levels"), then **Add to chart**.
5. Optional: chart settings → Symbol → turn on **back-adjustment** ("Adjust for contract changes"). The bot's files are
   back-adjusted. Inside one contract it makes no difference. Across a roll, PWH/PMH can differ without it.

The chart's time zone doesn't matter. The script works in New York time by itself.

## What you see (default view: clean)

The default shows only the key levels and the active setup. Everything else is behind a toggle in the settings
(gear icon → Inputs).

**Levels** (solid line while untouched; it turns **dotted and stops** at the candle that first trades through it):
- **PDH / PDL** (orange): previous day high / low (trading day 18:00-17:00 ET).
- **PWH / PWL** (purple), **PMH / PML** (blue): previous week / month high and low.
- **Asia box** (yellow, default 20:00-00:00) and **London box** (light blue, default 02:00-05:00). After the box closes, its
  high and low become levels ("Asia20 H", "Lon25 L").
- Off by default: New York boxes (08-09, 08:30-09:30, 09:30-10:00, 09:30-10:30), premarket (04:00-09:30), NWOG / NDOG gap
  edges (grey), build-ups **EQH / EQL** (grey: two swing highs/lows within 0.15 ATR, untouched in between).
- **The bot always uses every one of these as liquidity**, whether it's drawn or not, and so does the indicator.
  Toggles only hide lines.

**Sweep markers** (small tag "x PDL" under or over a candle): a level has just been run **at least 0.5 ATR** by a fresh
2-hour extreme. This is the early warning. Nothing is valid yet; the bot waits for the 5m CISD close.

**An armed setup** (the bot would place its limit now):
- **SWEEP** triangle on the extreme candle (the protected low or high).
- **IDM** dotted line: the inducement swing that sat above the swept level (below it for shorts). The final push into
  the extreme took it out, trapping the early buyers. "IDM x2" = two or more of them.
- **D 1.3**: the displacement candle, the biggest body between the extreme and the trigger, in ATR (needs 0.8+).
- **CISD** white line: the open of the last run of down candles into the extreme (up candles for shorts). The trigger is
  the first 5m close beyond it. **This is the limit price**, and it works for 30 minutes (the line's length).
- **SL** red dashed line: 1 tick beyond the sweep extreme. The bot needs 8 to 80 points.
- **TP** green dashed line: the VIX band, i.e. 18:00 open ± one VIX one-day move. It must be 1.5R or more away and is
  banked at 8R.
- The setup label: "LIT LONG · PDL+Asia20 L / CISD 26510.25 · SL 42p · 3.1R / A+ 5: 2IDM FVG SMT KZ DISC". Hover over it for
  every number.
- When the setup ends without a fill, its lines turn grey. The hover text on the label says why (30 min with no tap, extreme
  broken, target traded first, ...).

**5m entry / exit** ("BUY 26512.50 (5m)", then "TARGET +3.1R" / "STOP -1.0R" / "BE +0.0R" / "EOD"): what the bot's own
5m mode would do (tap of the limit, then a 5m CISD close within 4 candles, enter at the next open, breakeven at 1R, flat
15:55). **The live bot confirms on 1-minute candles**, so its real entry is usually earlier and sometimes on a day the 5m
version skips. Read these labels as "about here", not as the bot's fills.

**Grey shading**: the entry window 02:00-15:30 ET. The candle after the trigger must open inside it.

**Rejected sweeps** (off by default): a grey dot where a sweep got its CISD close but failed a bot filter. Hover over it
for the reason.

## The step panel (top right)

| Row | What it says |
|---|---|
| LIT | LONG bias (green) / SHORT bias (red): the direction of the latest sweep or setup |
| 1 Sweep | which level, how deep in ATR, ✓ when >= 0.5 |
| 2 Inducement | how many swings were taken first, ✓ when 1+ |
| 3 Displacement | the biggest body in ATR, ✓ when >= 0.8 |
| 4 CISD close | the level the 5m close broke |
| 5 Stop / target | stop in points, target in R, ✓ when the VIX band is 1.5R+ away |
| 6 Limit | armed (price, 30 min) / tapped, waiting for the confirmation / filled / dropped: reason |
| Entry window | open or closed |
| Trade today | free / in a trade / used: result (one trade a day) |
| Monday rule | on Mondays: "Friday high taken: shorts only" or "Friday low taken: longs only" |
| Next level up / down | the nearest untouched level above and below the price, with the distance: **what to watch next** |
| VIX band | today's long and short targets |
| A+ score | the number of confluence tags on the latest setup, with the tags |

## How to read a setup (step by step)

Picture a long at 03:40 ET:
1. At 03:05 the price drops through the **Asia 20:00 low** and keeps going. At 03:15 a tag **"x Asia20 L"** appears:
   it ran 0.6 ATR below the box low. The panel says *1 Sweep: Asia20 L 0.6 ATR*, *4 CISD close: waiting*.
2. On the way down it took out a small swing low that sat just above the Asia low (the **IDM** line). The early buyers
   are trapped, and their stops are now the fuel.
3. At 03:35 a big green candle (**D 1.1**) closes above the open of the last red run into the low (**CISD**). The setup
   label appears, the white CISD line runs 30 minutes to the right, the red SL sits 1 tick under the low (say 38 points),
   and the green TP is at the VIX band (say 3.4R). Alert: *LIT setup armed*.
4. The bot now waits for the price to come back to the CISD line, then for a 1-minute CISD close, and buys at the next
   1-minute open. The indicator shows the 5-minute version of that.
5. Breakeven at +1R, target or 15:55 ET, and then today's trade is used. The panel says so. No second trade today.

Things that make the bot skip a setup (shown in the hover text / panel "not armed: ..."): sweep under 0.5 ATR,
displacement under 0.8 ATR, no inducement, stop under 8 or over 80 points, VIX band under 1.5R, entry bar outside
02:00-15:30, the Monday rule, today's trade already used.

## Confluence tags (shown only; they never block a setup)

The bot doesn't use these. They are here to help you judge a setup and to collect data. The **A+ score** counts them
(14 possible).

| Tag | Means |
|---|---|
| 2IDM | two or more inducement swings taken (research: those trades earned more) |
| EQL | an equal-highs / equal-lows build-up was among the swept levels |
| HTF-LVL | a previous day / week / month level was swept |
| FVG | a fair value gap in the trade's direction between the extreme and the trigger |
| IFVG | an opposite gap from just before the extreme that the trigger closed back through (inversion) |
| OB15 / OB1h | the extreme sits in the last 15m / 1h order block (last opposite candle before a close beyond its high/low; previous closed HTF bar, no repaint) |
| RND0 / RND50 | the extreme is within 5 pts (input) of a 00 or 50 handle |
| SMT | NQ made the new 2-hour extreme but ES (input symbol) did not |
| D-BIAS | yesterday's daily candle closed in the trade's direction |
| DISC / PREM | a long below / short above the middle of yesterday's range |
| DOL | an untouched PDH/PWH (PDL/PWL for shorts) lies between the entry and the target: a draw on liquidity |
| KZ | entry in a killzone: London 02:00-05:00, NY AM 07:00-10:00, NY PM 13:30-15:30 |
| MACRO | entry in an ICT macro: 02:33-03:00, 04:03-04:30, 08:50-09:10, 09:50-10:10, 10:50-11:10, 11:50-12:10, 13:10-13:40, 15:15-15:45 |
| VIX3R+ | the VIX-band target is 3R or more away |

Day context (not scored): **OPEX** (third Friday), **NFP?** (first Friday, a guess; check the calendar), **NEWS** (a date you
typed in the "News days" input, e.g. `2026-10-28,2026-11-07`).

The tags are simple, published-style definitions written for this indicator. The repo's research (`research/writeups/
lit-htf-confluences.md`, `lit-order-blocks.md`) found none of them good enough to become a bot filter.

## Alerts

Two alerts, both fire once at the close of the 5m candle:
- **LIT setup armed**: the bot would place its limit now (direction, swept levels, limit, stop, target, R).
- **LIT sweep**: a level was run 0.5+ ATR (early warning, before the CISD close).

To set them up: Alerts → Create → Condition **LIT Levels** → either the named condition ("LIT setup armed" / "LIT sweep",
fixed text) or **"Any alert() function call"**, which carries the full message. Pick "Once per bar close".

Input **alert() message**:
- **Text** (default): a short sentence for the phone.
- **JSON**: one line with the fields the bot logs for its signals (`engine/lit.py` run_live "signals"):
  `{"src":"tv_lit","ev":"armed","sym":"NQ1!","day":"2026-10-16","t":1792138800,"dir":1,"swept":["asia20_l","bu_l"],
  "sweep_ext":26472,"cisd_px":26510.25,"limit_px":26510.25,"stop_px":26471.75,"target_px":26641.5,"risk_pts":38.5,
  "rr":3.41,"depth":0.62,"disp":1.12,"ind":2,"tags":["2IDM","EQL","FVG","KZ"],"score":4}` (example numbers).
  `t` is the entry candle's open time in unix seconds, the same as the bot's signal `t`. `dir` is 1 (long) or -1 (short),
  like the bot. The sweep alert sends `{"ev":"sweep","level":...,"level_px":...,"ext":...,"depth":...}`.
  This is for comparing later. Nothing in the repo reads it today, and there is no order bridge.

## Known differences from the bot

- **1m entry.** The bot confirms and enters on 1-minute candles (a 1m CISD close within 20 minutes of the tap, then the
  next 1m open). The indicator draws the bot's 5m fallback (a 5m CISD close within 4 candles). The setup, limit, stop and
  target are the same. The fill time and price, and on about 4 in 10 of the bot's trade days whether there is a fill at
  all, differ. The bot can also fill a setup the 5m version drops, and then the day is used.
- **VIX timing.** The bot uses the last CBOE VIX close dated before the trading day (CBOE's own file). The indicator reads
  `CBOE:VIX` daily on TradingView and takes the latest daily bar that has already closed at the 18:00 candle, else the one
  before. On a normal day both give yesterday's 16:15 close. Around holidays, or if TradingView's VIX session times
  differ, the band can be one day off. Compare the panel's VIX band with the bot's day brief.
- **History.** PWH/PWL and PMH/PML come from the chart's own candles once a full week or month is loaded. Before that, on
  the oldest days of the chart, they come from TradingView's weekly/monthly bars of the same symbol. Without
  back-adjustment, those can differ across a roll.
- **Several setups at once.** The indicator keeps up to 3 limits working. Like the live bot, the first one to fill is the
  day's trade. The plain backtest takes the first setup in order that fills. In 2026 the two never disagreed (77/77).
- **Size, weekly stop, two-week eval sizing.** These are not shown. They change the micros, not the setup.
- **Contract.** MNQ1! and NQ1! prices are almost always equal. Where they differ by a tick, a level or a sweep can
  differ (the bot trades MNQ bars from NinjaTrader and the NQ1! file).
- **Short days.** On CME early-close days the indicator drops a setup when the next candle would not come. The bot does
  the same.
- **Pine limits.** Up to 500 lines, 200 boxes and 500 labels: the oldest drawings disappear first. History lookups reach
  back 1,000 candles. Loops are short (24-bar extreme, about 100 bars for inducement, 288 bars for build-ups).
