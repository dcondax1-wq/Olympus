# The playbook: how each bot trades, written like a trader would

This is the rule book the bots follow, in plain words. It is the same rules as the code; nothing here changes how a bot
trades. Each rule has an id (Z = Zlarior / LIT, A = ATLAS, B = BLITZ). The bot quotes these ids when it says what it is
doing ("Z6: limit working at 29,945 until 04:12"); the machine-readable copy is `engine/playbook.py`.

Paper only. The owner arms live trading himself (`docs/GO_LIVE_TONIGHT.md`); no rule here routes an order.

**About "discretion" (owner 2026-10-28).** A person would say: "after that strong reversal I'd have moved to breakeven".
Every such idea is tested before it becomes a rule. The "structure" lines (Z-S, A-S, B-S) are what a structure trader
would notice; the bot shows them as **advice next to the trade, never as an order**. The discretion advisor
(`engine/advisor.py`) writes down what each structure rule would have done on every real and paper trade and keeps the score
in dollars, so the rule earns its place with evidence or stays a note. Tonight's test of the structure rules on the real LIT
trades is in `research/writeups/structure-management.md` (verdict at the end of this page).

---

## Zlarior (LIT, the 50K eval): sweep, trap, shift, then one clean target

The idea: price runs a pool of stops (a level everybody watches), traps the traders who chased it, then turns hard. We take
the turn with the stop just past the trap and aim for the day's expected move.

### What a good setup looks like (in order)
- **Z1 Know the liquidity.** Before anything, mark the levels: Asia (18:00/19:00/20:00 to midnight), London (02:00-05:00,
  03:00-04:00, 02:00-03:00), New York (08:00-09:00, 08:30-09:30, 09:30-10:00, 09:30-10:30) and premarket boxes, the previous
  day / week / month high and low, the weekly and daily opening gaps, and equal highs / lows (build-ups). A box is a level
  only after it closed.
- **Z2 The sweep.** A new 2-hour extreme takes out a level nobody traded through yet, and runs at least **half an ATR**
  past it. A swept low sets up a long, a swept high a short.
- **Z3 The trap (inducement).** Before the sweep, a small 5m swing sat between the level and the extreme (within 1 ATR,
  at most 3 hours old) and the final push ran through it: early traders got trapped.
- **Z4 The shove (displacement).** Between the extreme and the shift, one 5m candle body of **0.8 ATR or more**.
- **Z5 The shift (5m CISD).** A 5m close back through the open of the last run of candles into the extreme.
- **Z6 Entry at our price.** A limit at the CISD level for **30 minutes**. When price taps it, wait up to **20 one-minute
  candles** for a 1m CISD, then buy / sell at the next 1m open.
- **Z7 Time and count.** Entries 02:00-15:30 ET only. **One trade a day.** On Monday, once the session took Friday's high
  only shorts, Friday's low only longs.

### What kills it
- **Z8** The sweep extreme breaks before the fill (the trap was not the turn).
- **Z9** The target trades before the tap (the move is gone), 30 minutes pass without a tap, or 20 minutes without the 1m
  confirmation.
- **Z10** The stop would be under 8 or over 80 points, or the target is under 1.5R away.
- **Z11** It is 15:55, a trade already filled today, or the NinjaTrader feed is stale (FEED STALE blocks new entries).

### How it is managed (what a disciplined person does)
- **Z12 Stop at the protected extreme.** 1 tick beyond the sweep extreme, never a fixed distance. If that is wrong, the idea
  is wrong.
- **Z13 Size follows the stop.** A wide stop buys fewer micros, a tight one more; on the eval "one winner passes" (two_week
  sizing), capped at 80% of the room and the $1,000 soft daily loss.
- **Z14 One clear target.** The 18:00 open +/- one VIX day move, banked at 8R. No greed, no second target.
- **Z15 Protect at +1R.** At +1R the stop goes to entry + 1.25 (costs covered).
- **Z16 Cut the dead trade.** 15 minutes after the fill, a trade that never reached +0.5R and closes more than 0.3R under
  water is closed at the next 1m open.
- **Z17 Flat by 15:55.** Always.
- **Z18 No improvising.** No trailing, no early exit on a scary candle, no tighter stop. Each was tested on the real trades
  (`lit-reversal-exit.md`, 103 variants, and `structure-management.md`) and cost money in at least one half of 2026: LIT
  winners also snap back hard before they run. The 2026-10-28 trade (0.95R, then four big green candles, -$437) is the
  rare case; the rules that fix it cut real winners every month.

### What structure says (advice, shown next to the trade)
- **Z-S1** The 1h trend and whether price is in the premium or discount half of the 15m dealing range. In 2026 LIT trades
  with the 1h trend paid $492 a trade, against it $292: both pay, so LIT takes both (skipping the "against" ones cost $22k).
- **Z-S2** The nearest opposing liquidity pool in front of the trade (where a person would expect price to slow down).
- **Z-S3** A 5m CHoCH against an open trade after +1R: a person might move to breakeven. Advice only; the advisor scores it.
- **Z-S4** A 5m BOS in the trade's favour: the new protected swing is where a structure trader would trail. Advice only.

---

## ATLAS (the 25K eval): three members on their own account

EMA, MACD and S/R pooled on account B. LIT goes first; ATLAS never fights an open LIT trade. Paper unless the owner
switches routing on.

### What a good setup looks like
- **A1 EMA trend pullback (London 03:00-09:30 ET, no Mondays).** 15m and 1h EMA 21 above the 50 (longs; below for shorts);
  price pulls back to the 5m EMA 50, sweeps a swing low, and a 5m CISD closes back up.
- **A2 MACD divergence at a sweep (02:00-05:00 and 09:30-11:00 ET).** A LIT level is swept by 0.5 ATR and a 5m CISD
  closes back with MACD-line divergence. Market entry.
- **A3 S/R sweep-and-reclaim (NY 09:30-12:00 ET).** A level of the day (yesterday's RTH high / low, overnight, Asia /
  London box, last week, opening range) is swept after an inducement and a strong 5m close reclaims it. Market entry, one
  a day.

### What kills it
- **A4** Outside the member's hours, Monday for EMA, the trends disagree (EMA), no divergence (MACD), no reclaim close (S/R).
- **A5** LIT holds the other side or has an opposite setup armed: no ATLAS entry (no hedge); LIT entering the other side
  closes ATLAS at market. One position, at most 2 trades a day, the 25K's $600 soft daily loss.

### How it is managed
- **A6 Stop beyond the sweep extreme** (the wick that took the liquidity), size follows the stop ($500 a trade in research;
  need-based on the 25K eval).
- **A7 Targets:** VIX band for EMA and MACD, 2R for S/R. **A8** EMA: breakeven + 1.25 at 1R; MACD and S/R: the 15-minute
  check. Flat 15:55.

### What structure says (advice)
- **A-S1** 15m and 1h structure: ATLAS earns on pullbacks. Its trades paid most when the 15m structure was still against
  the 1h trend ($526-561 a trade in 2026) and least when 15m and 1h already agreed with the trade ($23 a trade in 2026,
  -$25 in 2021-25). Shown as context, not a filter.
- **A-S2** The protected swing of the 5m trend: where a structure trader's stop would sit (shown, not used).

---

## BLITZ (the scalper, paper shadow; a 25K next week)

The noise-area momentum scalp: when NQ breaks out of its normal intraday noise, it tends to keep going for a while.

### What a good setup looks like
- **B1 Only on lively days.** Yesterday's 09:30-16:00 range at least 0.8 x its 14-day mean; else no trades today.
- **B2 The noise band.** 09:30 open x (1 +/- sigma), sigma = the 14-session mean move at that minute.
- **B3 Checks on the half hour.** At the 1m closes 11:00, 11:30 ... 15:30: a close above the band = long, below = short,
  market at the next open.

### What kills it
- **B4** Six trades today, or the day is down 3R, or no clean 1m bars (stale feed).

### How it is managed
- **B5 Stop 1.5 x ATR(14) of 5m** from the signal close. **B6** After +1R the stop trails 1.5R behind the best price.
  **B7** Out after 30 bars or at 15:55. No fixed target.
- **B8** Next to LIT on a 50K: never while LIT holds a trade or has a setup armed; closed when LIT enters (LIT first) or
  ATLAS enters the other side.

### What structure says (advice)
- **B-S1** The 5m trend and its last BOS / CHoCH. Most BLITZ breakouts already go with it (262 of 330 in 2026); with or
  against, they paid about the same (0.16R vs 0.13R a trade): context only.

---

## Where to see it
- **Live View** (PC and phone): the "structure" block (5m / 15m / 1h trend, last BOS / CHoCH, protected swings, pools,
  premium / discount) and one structure line per strategy in the thinking panel; the narrator posts structure changes
  ("5m CHoCH down at 29,950").
- **Learning page**: the advisor's tally per rule ("BE on a 5m CHoCH would have saved $X over N trades") as suggestions.
  Nothing switches on by itself; a rule that keeps earning goes to the owner with its numbers.

## Tonight's verdict (2026-10-29, `research/writeups/structure-management.md`)
95 LIT and 24 ATLAS structure ideas were tested on the real trades. None makes more money than the live rules in both
halves of 2026 on both sizings, so Zlarior keeps Z12-Z18 and ATLAS keeps A6-A8 unchanged.
- The owner's "breakeven after a strong reversal" (BE on a 5m CHoCH against after +0.75R): H1 -$1,442, H2 -$775. It would
  not have fired on the 2026-10-28 trade.
- Targets at the next liquidity pool: H1 -$6.6k to -$17.4k. Skipping trades against the 1h trend: H1 -$15.0k, H2 -$7.5k,
  about 1 trade a week (it would have skipped the 2026-10-28 short).
- The one lead (watched by the advisor, not switched on): after a 15m break in the trade's favour once +1R, the stop to the
  15m protected swing: H1 +$467, H2 +$13 at the LIT size, eval path +$1,019 / +$3,762, but one more 2-week fail in H1 and
  only 7 trades changed in 2026.
- ATLAS: the stop at the 15m protected swing looks better on the 25K account (H1 +$3.6k) but its trades are worse at a fixed
  risk in every span: rejected.
