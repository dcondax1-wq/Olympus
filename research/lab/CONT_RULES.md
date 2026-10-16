# CONT: ICT / smart-money continuation model, written as published

Written **before** any backtest (Fri 2026-10-16, about 18:15 ET). Module: `tools/lab_models/continuation.py`.
The 3 variants below were fixed here, before testing. No other variants or parameter values were run.

## What the public sources agree on
In the taught sequence, price leaves **internal range liquidity** (an FVG inside the last impulse leg) and goes to **external range
liquidity** (the leg's old high or low) in the direction of the higher-timeframe structure:

1. Read the HTF structure.
2. Wait for a pullback into the discount (or premium) half of the impulse leg, at a PD array (FVG / IFVG / order block / breaker).
3. Enter inside a killzone, either on a resting limit at the array or on a lower-timeframe confirmation.
4. Put the stop beyond the swing.
5. Target the old high or low, taking the trade only if it pays at least 1:2.

## Rules (long side shown; shorts are the mirror image)
1. **HTF trend: 1H market structure.** Build 1H bars (clock hours, ET) from 5m bars. A 1H bar counts only after it has closed.
   - A swing high is a 1H candle with a lower high on each side (ICT's 3-candle swing). It is confirmed when the next 1H candle closes. Swing lows mirror this.
   - The trend is **up** after a 1H candle **closes above** the latest confirmed, unbroken swing high (a bullish break of structure, BOS). It stays up until a 1H candle closes below the latest confirmed, unbroken swing low (then it turns down).
   - Longs only in an up trend.
2. **Impulse leg (dealing range).** At a bullish BOS, the leg low is the lowest price between the broken swing high and the BOS candle. The leg high is the highest price traded since then; it extends as price makes new highs.
   - Equilibrium (EQ) = 50% of the leg. Below EQ is discount.
   - A new BOS starts a new leg. If price trades below the leg low, the leg is void.
3. **Killzone.** All entries happen in the **NY AM killzone, 09:30–11:00 ET**.
   - Variant `IFVG_AMPM` adds the **NY PM killzone, 13:30–15:00 ET** (entries; positions still go flat at 15:55).
4. **Internal liquidity (PD array).** A bullish FVG is a three-candle 5m gap, where candle 3's low is above candle 1's high.
   - It must form inside the leg (between the leg-low bar and the leg-high bar) and be at least 3.0 pts on NQ or 0.75 pt on ES. This noise floor is the same for every variant; NQ is about 3.8x ES in points.
   - A **discount FVG** has its midpoint (consequent encroachment, CE) at or below EQ.
5. **Pullback requirement.** After the leg high, the pullback low (lowest low since the leg-high bar) must be **at or below EQ**, must have **traded into a discount FVG** of the leg (low at or below the FVG's top), and must stay above the leg low.
6. **Entry, variant `FVG` (classic resting limit).** During the killzone, rest a buy limit at the **CE of the highest untouched discount FVG** of the leg. "Untouched" means no bar has traded down to the CE since the gap formed.
   - The order fills only if a later 5m bar trades at least 1 tick through the CE.
   - Stop: 2 ticks beyond the FVG's far edge (its bottom).
7. **Entry, variants `IFVG` / `IFVG_AMPM` (confirmation).**
   - The pullback leaves bearish 5m FVGs. These form after the leg high, are at least the minimum size, and their high is below candle 1's low.
   - Once rule 5 holds, the first 5m candle that **closes above the top of such a bearish FVG** (an inversion, IFVG; a change in state of delivery) is the signal.
   - Entry is at market, at that candle's close.
   - Stop: 2 ticks below the pullback swing low.
8. **Target: external liquidity.** The target is a limit at the **leg high** (the old high, buy-side liquidity). It fills only if price trades 1 tick through it.
   - Skip the signal if the target pays **less than 2R** (counted from the entry price).
   - No breakeven, partials or trailing.
9. **Flat at 15:55 ET.** An unfinished trade at the end of the data is marked `open`.
10. **Same-bar rule.** If the stop and the target are both touched in one bar, the stop fills first. On a limit fill bar, only the stop can fill.

## Risk management (owner defaults; the research found nothing that contradicts them)
- Fixed **$350 risk** per trade: MNQ $2/pt, MES $5/pt, at most 40 micros. Costs: $1.40 per micro round trip, plus 1 tick of slippage on market entries and on stop and flat exits.
- **At most 2 trades a day.** Stop for the day after a **winner** or after **2 losers**.
- **Daily stop −$700** (realized): no new trade after that.
- One position at a time.

Taught prop-firm advice matches these defaults. Daxton teaches "one trade per day". Prop-eval guides teach a small fixed risk, few trades, and a daily cap well inside the firm's DLL (MFFU 50K DLL $1,000 is a soft pause; MLL $2,000 EOD trailing).

## Variants (fixed in advance; every one is reported)
| name | bias | killzone | entry | stop |
|---|---|---|---|---|
| `FVG` | 1H BOS | 09:30–11:00 | limit at CE of the discount FVG | beyond FVG far edge |
| `IFVG` | 1H BOS | 09:30–11:00 | 5m close through a bearish pullback FVG | beyond pullback swing |
| `IFVG_AMPM` | 1H BOS | 09:30–11:00 + 13:30–15:00 | as `IFVG` | as `IFVG` |

All three variants run on both NQ and ES with identical rules (only the FVG size floor is scaled). Scored names: `CONT_NQ_<variant>`, `CONT_ES_<variant>`.

## Where the sources disagree, and what was picked (the most common version)
- **Bias.** The most common is 1H/4H structure (BOS), used by TradeZella/Cutler and eltraderfinanciado. Others use HTF EMAs (Daxton), HTF candle closures (TTrades) or a daily close vs. PDH/PDL. **Picked: 1H BOS**, the HTF in TTrades' 5m–1H pairing.
- **Swing size.** ICT's 3-candle swing vs. larger pivots in indicator code. **Picked: ICT's 3-candle swing**.
- **Killzone.** ICT's index killzone is 08:30–11:00; most NQ educators trade from the 09:30 open. PM 13:30–16:00 is optional. **Picked: 09:30–11:00**; the PM session is variant 3.
- **Pullback depth.** Discount (<50%) is the most common; OTE (62–79%) is stricter. **Picked: discount plus an FVG tap**.
- **PD array.** FVG is the most common. Order blocks and breakers are used less, and the breaker (Unicorn = breaker + FVG) needs a sweep-and-break sequence that is more discretionary. **Breakers were not tested**.
- **Confirmation.** Options are none (limit at the CE), LTF MSS/CHoCH, CISD, or IFVG. **Tested: none (`FVG`) and IFVG**, the most common confirmation in 2024–26 NQ content.
- **Stop.** Options are beyond the FVG's far edge (limit entries), beyond the pullback swing (confirmation entries), or beyond the leg origin (OTE). Each variant uses the stop its source pairs with it.
- **Target.** The leg's old high is the most common; some use the next HTF pool or fixed R. Minimum 1:2 (TradeZella ICT models).

## Sources
- eltraderfinanciado, FVG models table. Continuation row: pullback to the FVG, often at the CE; stop beyond the far edge; target the next liquidity in the trend direction; NY or London session. https://www.eltraderfinanciado.com/en/blog/fair-value-gap
- LuxAlgo Library: optimal trade entry (impulse leg with displacement BOS; 62–79%; resting limit vs. LTF confirmation; stop beyond the anchoring swing). https://www.luxalgo.com/library/concept/optimal-trade-entry/
- LuxAlgo Library: premium and discount (dealing range = the leg that broke structure; EQ 50%; longs in discount). https://www.luxalgo.com/library/concept/premium-and-discount/
- LuxAlgo Library: PD arrays (an HTF array sets the zone, the LTF refines it; buy discount arrays, target premium arrays and the range extreme). https://www.luxalgo.com/library/concept/pd-arrays/
- LuxAlgo Library: draw on liquidity (external vs. internal range liquidity alternate). https://www.luxalgo.com/library/concept/draw-on-liquidity/
- LuxAlgo Library: breaker block. https://www.luxalgo.com/library/concept/breaker-block/
- TradeZella / Joshua Cutler (CutlerTrades), IFVG model: 4H/1H bias, NQ/ES NY session from 09:30, a close through the FVG makes the IFVG, stop beyond the swing, target internal then major liquidity. https://www.tradezella.com/strategies/ifvg-trading-model
- Daxton Trades, "Stupid Simple NQ Strategy" transcript: HTF EMA bias, an FVG formed on the pullback against bias, a 5m inversion close as entry, stop below the swing, target the previous liquidity, NY session, one trade a day. https://sozai.app/transcript/stupid-simple-nq-strategy-4000-day/
- TradeZella ICT models 2/4/5: stop beyond the liquidity grab, target external liquidity or an HTF level, minimum 1:2. https://www.tradezella.com/learning-items/ict-model-2 , https://www.tradezella.com/learning-items/ict-model-4 , https://www.tradezella.com/learning-items/ict-model-5
- TTrades Fractal Model (HTF closure + LTF CISD; 5m–1H and 15m–4H pairings). https://www.tradingview.com/script/XdwK9qQQ-Fractal-Model-Pro-TTrades/
- ChartingLens, killzones: NY AM about 08:30–11:00 for indices, NY PM 13:30–16:00; a pullback into an FVG/OB in NY AM counts as continuation. https://chartinglens.com/blog/ict-kill-zones-guide
- Independent prior, Backtrex NAS100 10-year test of a 1H-FVG / 4H-EMA setup: PF 1.08, 27% wins, 2025 −4.6%. https://backtrex.com/en/backtests/ict-fair-value-gap-nasdaq
