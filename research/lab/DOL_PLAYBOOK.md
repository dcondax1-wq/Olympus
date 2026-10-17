# DOL PLAYBOOK: how discretionary ICT/SMC futures traders pick targets, place stops and manage trades (mechanical version)

Written 2026-10-16, 18:15–19:00 ET, for the builder agents. Data: TradingView CME futures NQ1!/MNQ1!, 5m OHLCV.

**Scope.** This playbook covers what happens after an entry signal:

- where the target is (the draw on liquidity)
- where the stop is (invalidation)
- how big the position is
- how the trade is managed

Entry triggers are not covered here; see MECH_RULES.md, SB_RULES.md and CONT_RULES.md. The goal is to replace a fixed R target and fixed break-even with the structure-based logic a person uses.

**How to read it.**

- Every rule has an ID.
- **Default** is the most common published version. **Alt** lists documented alternatives.
- **(ours)** marks a number we chose because no source gives one. These are starting values, not tuned values.
- Sources are listed at the bottom as [L1], [V3] and so on.

**Honesty note.**

- ICT has no written rulebook. Most sources are secondary: the LuxAlgo concept library, AI summaries of ICT videos, TradingView script descriptions and prop-firm blogs.
- The innercircletrader.net pages were not machine-readable (base64 images), so only their search-result summaries were used.
- No source gives a win rate or statistic we could verify. Nothing here is proven. Every rule must be tested as a variant on all periods.

---

## 0. Build ground rules (causality)

- **C1. Bars.** 5m bars use ET timestamps labeled by bar open. A bar is known at its open time + 5 minutes. All decisions use closed bars only.
- **C2. Timing.** Anything computed at the close of bar t (a new stop, an exit, an order) acts from bar t+1.
- **C3. Higher-timeframe (HTF) bars** are built by aggregating 5m bars:
  - 15m and 1H are aligned to the clock.
  - 4H is aligned to the 18:00 ET session open (18, 22, 02, 06, 10, 14). This is TradingView's CME convention; check it against the export.
  - Daily = one CME day, 18:00 to 17:00 ET, labeled by the date it ends.
  - Weekly = Sunday 18:00 to Friday 17:00.
  - An HTF bar is usable only after its last 5m bar has closed. Never use a forming HTF bar's high/low as a level. The one exception is the running CME-day high/low, which is used only by `reach`.
- **C4. Contract specs.** NQ tick = 0.25 pt. NQ = $20/pt; MNQ = $2/pt.
- **C5. Volatility.**
  - `ATR_tf` = Wilder ATR(14) on closed bars of timeframe tf.
  - `ADR10` = mean high−low of the last 10 completed CME days.
- **C6. Backtest fills.**
  - Stop before target when both are touched in the same bar.
  - A limit target needs a 1-tick trade-through.
  - A stop fills at the stop price ± 1 tick of slippage.
  - These match the existing house conventions in `strategy_lab.make_trade`.

---

## 1. Shared definitions (every later rule uses these)

**D1. Swing high/low (fractal).**

- On bars of timeframe tf, bar i is a swing high of strength k if both hold:
  - `high[i] > max(high[i-k .. i-1])`
  - `high[i] >= max(high[i+1 .. i+k])`
- A swing low is the mirror.
- It becomes usable at the close of bar i+k.
- Default k:
  - 5m: k=2 (structure, BOS, trailing).
  - 15m, 1H, 4H, Daily: k=1, the 3-candle fractal, for liquidity pools. This is the same as MECH_RULES.
- Alt: k=1 everywhere (ICT's 3-bar swing). LuxAlgo SMC uses 5 bars for internal structure and 50 for swing structure.

**D2. Displacement candle (tf).**

- Its body is `|close−open|`. A candle is a displacement candle when all of these hold:
  - body ≥ 1.0 × ATR_tf
  - body / (high−low) ≥ 0.6
  - it closes in the direction of the move
- A *displacement leg* is 1–3 consecutive same-direction candles that include at least one displacement candle.
- Source: [L8] gives no fixed threshold, only a large body compared with recent bars and little wick at either end. It treats a fair value gap as supporting evidence, not a requirement. The numbers are ours. The body ≥ 0.6 filter follows CISD scripts that require body ≥ 50% of range [T2].
- Alt: body ≥ 1.5 × the mean body of the last 20 bars. ATR multiples of 0.7–1.5 are also used.

**D3. Fair value gap (FVG), 3-candle, any tf.** The three candles are c1, c2 (the displacement candle) and c3.

- Bullish FVG: `low[c3] > high[c1]`. The zone runs from bottom = `high[c1]` to top = `low[c3]`.
- Bearish FVG: `high[c3] < low[c1]`. The zone runs from bottom = `high[c3]` to top = `low[c1]`.
- Consequent encroachment (CE) = (top + bottom) / 2.
- The gap is known at the close of c3.
- Minimum size: on 5m, top − bottom ≥ max(1 tick, 0.1 × ATR_5m) (ours). On 15m and up, ≥ 1 tick.
- Sources: [L9], [L6].

**D4. Volume imbalance (VI).** Two consecutive candles whose bodies do not overlap but whose wicks do.

- Bullish VI at bar i, when both hold:
  - `min(open[i],close[i]) > max(open[i-1],close[i-1])`
  - `low[i] <= high[i-1]`
- The zone runs from `max(open,close)[i-1]` to `min(open,close)[i]`. The bearish VI is the mirror.
- It uses the same state machine as an FVG (D6) but ranks lower.
- Source: [L9].

**D5. Opening gaps.**

- NDOG: the zone between the close of the 16:55 ET bar (the CME daily close) and the open of the 18:00 bar.
- NWOG: the same, between Friday's 16:55 close and Sunday's 18:00 open.
- Mark each gap's high, low and CE.
- Retention:
  - Keep the last 5 NWOGs. This is the ICT convention [L7].
  - NDOGs fade within a session or two [L7]. Keep the last 2 (ours).

**D6. Gap state machine (FVG, VI, NDOG, NWOG).** Evaluate on every 5m bar after the gap is created. The bullish gap is shown; the bearish gap is the mirror.

| state | condition, checked on any 5m bar after c3 |
|---|---|
| live (unmitigated) | no low ≤ top yet |
| tapped | some low ≤ top (a wick entered the zone) |
| CE-tagged | some low ≤ CE |
| filled | some low ≤ bottom |
| inverted | some 5m **close** < bottom (a body close beyond the far edge) |

- **As a draw (target):**
  - Default: the gap stays a target until it is CE-tagged. A touch of the midpoint is commonly treated as "filled enough", a partial fill [L6, L9].
  - Alt: drop it at the first tap (strict).
  - Alt: drop it only when filled (lenient).
  - Alt: indicator modes wick-filled, body-filled, wick-half and body-half [T6].
- **As support/resistance (an entry zone or holding zone):**
  - respected while no close beyond CE
  - weakened after a close beyond CE [L6]
  - void after a close beyond the far edge. That is an inversion: the zone flips role, and it is the MECH IFVG trigger.
- **Expiry as a draw (ours; no source gives a lifespan):**
  - 5m gap: end of the next CME day.
  - 15m: 5 days.
  - 1H: 10 days.
  - 4H and Daily: never. Keep the 10 nearest per side.

**D7. External-range liquidity pools (ERL), and when each exists (causal).**

| pool | level | first usable |
|---|---|---|
| PDH / PDL | high / low of the previous CME day | 18:00 ET |
| PWH / PWL | high / low of the previous week | Sunday 18:00 |
| Asia H/L | 20:00–00:00 | 00:00 |
| London H/L | 02:00–05:00 | 05:00 |
| Overnight (Globex) H/L | 18:00–09:30 | 09:30 |
| Prior RTH H/L | the previous day's 09:30–16:00 | 16:00 |
| 4H / Daily / 1H / 15m swing H/L | D1, k=1 | close of the confirming bar |
| 5m swing H/L | D1, k=2 | close of the confirming bar |
| EQH / EQL | D8 | when the 2nd swing confirms |

Sources: prior day, week and session highs/lows, equal highs/lows and gaps as the pre-session inventory [L2]; session times as in MECH_RULES.

**D8. Relative equal highs (EQH) / equal lows (EQL).** Two or more confirmed swing highs on the same timeframe form an EQH when all of these hold:

- `|h_a − h_b| ≤ tol`, where `tol = max(2 ticks, 0.1 × ATR_tf)`.
- They are at least 3 bars apart.
- The lowest low between them is ≤ `min(h_a,h_b) − 1.0 × ATR_tf`. This is the "meaningful pullback".

The pool level is `max(h_a, h_b, ...)`, because the stops sit above the highest one. EQL is the mirror.

Sources:

- [L3] says the highs are within a few ticks or a small fraction of ATR, there is no fixed tolerance, and two or more swings are needed with a meaningful pullback between them.
- LuxAlgo SMC uses an ATR-scaled sensitivity threshold [L11]. Its exact default was not verified here.
- The numbers above are ours.

**D9. Pool status.**

- A buy-side pool is **taken** when a 5m high ≥ level + 1 tick. A sell-side pool is taken when a 5m low ≤ level − 1 tick.
- A taken pool leaves the target lists immediately.
- Each take is classified for the rotation state (DOL-2):
  - **Swept (raid):** a 5m close back on the original side, on the taking bar or within the next 2 bars.
  - **Run (accepted):** 2 consecutive 5m closes beyond the level, or one 1H close beyond it.
  - **Neither:** classify it at the 3rd bar by its close.
- Sources: [L10] describes the classic sweep as a wick through and a close back inside. Some traders require the close back on the sweep candle itself; others accept any tag-and-reject that resolves within a few bars. A close that holds beyond the level with follow-through is a breakout, not a sweep.

**D10. Structure, BOS and the protected low/high.**

- A **BOS up** is a 5m close above the most recent confirmed, not yet broken 5m swing high (k=2).
- At each BOS up, the **protected low** PL = the lowest low from the bar of the broken swing high through the BOS bar, inclusive. This is the SMC "strong low": the low that produced the break.
- PL only moves up, at the next BOS up.
- A 5m close below PL is a bearish market structure shift (MSS/CHoCH): the long thesis is void.
- Shorts are the mirror: protected high (PH), BOS down.
- Default is close-based. In [T1], BOS is based on the protected highs/lows and the candle close. Alt: wick-based (LuxAlgo SMC offers both).

**D11. CISD (change in state of delivery), on 5m.**

- Track the latest bullish delivery series: the maximal run of consecutive 5m candles with close > open.
- A **bearish CISD** is a 5m close below the **open of the first candle of that series**.
- Only bodies count; wicks do not [L5]. The bullish CISD is the mirror.
- Alt: use the open of the last (nearest) candle of the series [L5]. This is more sensitive, and most scripts use it [T2].
- Alt: [T3] uses a close beyond the open AND beyond the previous candle's high/low.
- Filter: the CISD candle's body must be ≥ 50% of its range [T2].

**D12. Dealing range and premium/discount.**

- DR = from the most recent confirmed 1H swing low below price to the most recent confirmed 1H swing high above price.
- EQ = the midpoint. Below EQ is discount; above EQ is premium.
- If price is beyond every confirmed swing on one side, use the running CME-day extreme for that side.
- Source: [L4] defines the dealing range as the most recent significant swing range containing price, set one or two timeframes above the execution chart.

---

## 2. Draw on liquidity: where price is going next (targets)

**DOL-1. Inventory.** Rebuild at every 5m close. Keep two lists sorted by distance from price:

- **Above price (buy-side):**
  - every live ERL high from D7/D8
  - every live **bearish** FVG, VI, NDOG or NWOG zone above price. Only bearish gaps can still be unmitigated above price.
- **Below price:** the mirror, with **bullish** gaps.
- For a long, an internal-range (IRL) target is a live bearish gap above, and first contact is its bottom edge. For a short, it is a live bullish gap below, with first contact at its top edge.

Sources: [L2], [L4], [V1].

**DOL-2. Rotation state (ERL → IRL → ERL).** Keep `last_event` with its side and time. Price usually alternates: after an external pool is purged the next draw is often internal, and the reverse [L2, L4, V1].

- **ERL swept** (D9) → the next draw is the IRL in the reversal direction: the nearest live opposing gap on 15m or higher (else 5m) between price and the opposite ERL. After that, the opposite ERL.
  - This is the project's case. A sell-side sweep becomes a long. TP1 is the first bearish gap above; the runner goes to the buy-side ERL.
- **ERL run** (accepted) → the next draw is a retrace into the nearest live gap the run left behind (with-trend IRL), then the next ERL in the run direction.
  - Do not fade an accepted run: a reversal entry needs a *sweep*.
- **IRL reached** → the next draw is the nearest Tier-A ERL away from the gap. IRL counts as reached when both hold:
  - a gap on 15m or higher is CE-tagged
  - within 6 bars, a CISD or BOS away from it prints, with no close beyond its far edge
- [L4] calls the rotation a framing device, not a law. A real breakout takes ERL and keeps going; ERL run covers that case.

**DOL-3. Target tiers.**

| tier | what is in it |
|---|---|
| **A** (obvious external liquidity) | PWH/PWL, PDH/PDL, prior RTH H/L, overnight H/L, Asia H/L, London H/L, 4H/Daily swings, EQH/EQL on 15m or higher |
| **B** | 1H swings, EQH/EQL on 5m, NWOG CE, live 1H/4H/Daily gaps (HTF IRL) |
| **C** | 15m and 5m swings, live 5m and 15m gaps, volume imbalances, NDOGs |

Ranking inside a tier:

1. Never-probed beats probed. *Probed* = price came within 2 ticks without taking it.
2. Then the higher timeframe.
3. Then the nearer pool.

Sources:

- [L2]: higher-timeframe pools outrank lower ones; engineered equal highs/lows outrank single swings; an untapped weekly extreme pulls harder than a probed one.
- [L3]: the cleaner and more obvious the level, the bigger the pool.
- The tier boundaries are ours.

**DOL-4. Final target T (the draw, and the runner's exit).** For entry E and stop S, with R = |E − S|:

- `T_level` = the **nearest Tier-A** pool on the trade side whose distance is ≥ `minRR × R` and ≤ `reach`.
- If none qualifies, take the nearest Tier-B pool with the same limits.
- If none qualifies, use the DOL-9 fallback.
- `minRR`: Default 2.0.
  - Alt 1.0: PB/MECH.
  - Alt 3.0: the innercircletrader 2022 guide calls 1:3 realistic [I2].
  - TTrades notes use a minimum of 2R [T5].
- `reach` (ours) = `max(0.5 × ADR10, ADR10 − (running CME-day high − running CME-day low))`.
- Exit price: `T = T_level − 2 ticks` for longs, + 2 ticks for shorts. Exits go *into* the pool, not beyond it, because delivery often stalls once the liquidity is taken [L2].
- Alt (PB/MECH): the nearest pool of any tier ≥ 1R, capped at 3R.

**DOL-5. First internal draw (TP1, the partial).**

- `TP1_level` = the nearest candidate whose distance is in [1.0R, dist(T)). Candidates:
  - a live opposing gap edge, on 15m or higher preferred, 5m allowed
  - a Tier-B or Tier-C pool
- Tie-break when candidates are within 0.25R of each other: HTF gap, then EQH/EQL, then swing, then 5m gap.
- Exit price:
  - for a gap, its near edge (a long's TP1 is the bottom of a bearish gap)
  - for a pool, the level ∓ 2 ticks
- Alt: the gap's CE. A touch of CE is a partial fill [L6].
- If no candidate qualifies, there is no partial.
- Sources:
  - [V3]: take the first partial at an order block or FVG, the second at another high/low, and take partials at equal highs/lows.
  - [I4]: older highs as partial levels.

**DOL-6. Path resistance: low-resistance (LRLR) vs high-resistance (HRLR) liquidity run.** Computed at entry over the corridor between E and T_level.

- `n_res` = (number of fresh 5m (k=2) and 15m (k=1) swing highs inside the corridor that are not part of the target pool) + (number of live opposing gaps on 15m or higher inside the corridor). For a long these are bearish gaps above. Count each price zone once.
- Classify (thresholds are ours; [L1] gives no numbers):
  - **LRLR** if `n_res ≤ 1`
  - neutral if 2
  - **HRLR** if `n_res ≥ 3`
- Use:
  - LRLR or neutral → the normal plan: partial at TP1, runner to T.
  - HRLR → the **whole position exits at TP1** (the first opposing structure). Require TP1 ≥ minRR, else skip.
  - Alt for HRLR: keep the plan at half size. [L1] says to take profit at the first opposing structure, use smaller size, or skip.
- **Blocking array** (ours): skip the trade if the near edge of a live opposing 1H or 4H gap lies within 1.0R of E. [L1] prefers targets reachable through cleared territory.
- **Delivery check** after entry: `overlap6` = Σ overlap(range_i, range_{i−1}) / Σ range_i over the last 6 bars of 5m. Above 0.6 means slow, overlapping, high-resistance delivery, and it feeds MGMT-7. [L1] says to act before the stop if a planned clean run starts printing slow, overlapping candles.
- What counts as resistance in the corridor: unswept swings and opposing imbalances [L1]; intermediate highs and lows, order blocks and PD arrays [H1]. LRLR = a fast move with little retracement [V2].

**DOL-7. When a gap is "mitigated" (recap of D6).**

- Default: a gap stops being a target once a wick touches its CE.
- It stops being support/resistance once a body closes beyond the far edge. It inverts, flips role, and can become an entry trigger.
- A close beyond CE downgrades it [L6].
- The alternatives are listed in D6. Indicators differ, so this is a parameter (`gap_mitigation` ∈ {tap, CE, fill}).

**DOL-8. HTF bias (optional filter).**

- Run DOL-2 on the 4H/Daily lists. The bias points toward the next draw implied by the last HTF event.
  - Example: PDL swept and the 4H closes back above it → bias up, toward the nearest Tier-A buy-side pool or live bearish 4H/Daily gap above.
- Take only trades whose T is on the bias side. [L2] says to name one working draw and skip setups against it.
- Warning: the project's discovery scans found HTF and premium/discount filters unstable across periods. Test this; do not assume it.

**DOL-9. No-pool fallback** (for example, at all-time highs).

- Default: T = E + 2R (ours).
- Alt: a projection of the displacement leg: `T = leg_high + 2.0 × (leg_high − leg_low)` for longs. This is the "−2 SD", with staged exits at −2 and −2.5 [I3, I5, T3].
- Alt: TTrades notes use −2 and −4 of the manipulation leg [T5].

---

## 3. Stops: invalidation, not points

**STOP-1. Candidates.** Described for a long; shorts are the mirror. All are computed at the close of the entry bar.

| id | price | when it is the default |
|---|---|---|
| `S_sweep` | lowest low from the sweep bar through the entry bar (the raid extreme) | **reversal** setups (sweep → shift/IFVG). The project's model. |
| `S_origin` | protected low PL at entry (D10): the swing the displacement launched from | **continuation** setups (a retrace into a with-trend FVG after a BOS) |
| `S_c1` | low of candle 1 of the entry FVG | tight Alt ("beyond FVG candle 1") |
| `S_edge` | the entry FVG's bottom (= `high[c1]`) or its CE | very tight Alt ("strict respect") |

Sources:

- Stops go beyond the swept extreme [L5].
- The stop belongs beyond the sweep wick, where the exit line is unambiguous [L10].
- Beyond the sweep candle's wick, with a small buffer [I2].
- A stop just beyond the FVG [V3].
- The stop sits below the C1 liquidity low [T3].
- [L6] warns against entering at CE with a stop beyond the far edge, because it mixes two models into neither. Keep the entry model and the stop model consistent.

**STOP-2. Buffer.** `stop = candidate − buf` for longs, + for shorts.

- `buf = max(2 ticks, 0.1 × ATR_5m)` (ours).
- Alt: 1 tick (PB/MECH). Alt: a fixed 2–5 NQ points.
- [I2] notes that a stop just past the swing tends to get hit. Use a buffer, not zero.

**STOP-3. Veto, never stretch.**

1. Compute R and n (RISK-2). If n < 1, **skip**: the stop is too wide for the risk.
2. If `dist(E, T_level) < minRR × R`, **skip**. Do not move the stop closer to make the numbers work: a tighter stop is not invalidation. The project tested tighter stops and they were worse. If the technical stop needs more risk than the cap allows, skip the trade [P3].
3. If HRLR and TP1 < minRR, skip (DOL-6).
- Alt (person refining on a lower timeframe): use `S_c1` when it still gives ≥ minRR and is ≥ 0.5 × ATR_5m from E. A 5m-only build cannot refine properly, so this is a variant only.
- **Frequency guard:** each veto removes trades. After adding any veto, re-check that trades per week stays within the user's hard constraint of 1–4.

**STOP-4. Monotonic.** The stop only moves in the trade's favor (`max(old,new)` for longs) and never widens.

---

## 4. Position sizing and risk

**RISK-1. Fixed dollar risk per trade.**

- Default: $350, the house default.
  - That is 17.5% of the $2,000 maximum loss limit (MLL).
  - Two losers = $700, which is less than MFFU's $1,000 soft daily loss limit (DLL).
- Alt: 0.5–1% of the account size, which is $250–$500 on 50K.
- Prop blogs say to size from the drawdown, not the 50K balance, so that 2–3 losers fit inside the DLL. With a $1,000 DLL and $400 risk, two losers end the day [P3].
- Some firms cap loss per trade (2% at some), or forbid risking the whole DLL on one trade [P3].

**RISK-2. Contracts.**

```
n = floor( risk$ / ((R + 2 ticks) × $/pt) )
```

- Use MNQ ($2/pt) for granularity.
- n < 1 → skip.
- Cap n at the account's maximum position (check the MFFU plan limit).
- The 2 ticks cover stop slippage.

**RISK-3. Daily limits.**

- At most 2 trades a day, one position at a time.
- **Done for the day after a winner.** A TP1 fill followed by the runner stopped at break-even counts as a winner.
- Done after 2 losers, or when the day's P&L ≤ −2R (−$700).
- Never let (open risk + realized day loss) exceed 70% of the DLL.
- Flat at 15:55 ET.
- Sources: PB (done after a win, at most 1–2 trades a day) [R1]; Topstep 50K DLL $1,000 [P1]; MFFU soft DLL $1,000 and $2,000 EOD-trailing MLL [P2].

**RISK-4. Drawdown throttle** (ours, standard prop practice). If `balance − MLL_floor < 3 × risk$`, halve risk$. Restore it once the cushion is above 4 × risk$.

**RISK-5. Same risk every trade.**

- No grade sizing. PB uses the same risk on every trade [R1].
- The project's five-year test found grades A–D do not rank trades.

---

## 5. Trade management like a person

**The plan at entry.**

- n contracts, initial stop S0.
- TP1 (DOL-5) for q1 contracts.
- A runner of n − q1 contracts to T (DOL-4).
- Every order is placed at entry, so management is deterministic.

**MGMT-1. Partial at the first internal draw.**

- `q1 = min(n − 1, ceil(n / 2))`. Default ≈ 50%.
- If n = 1, there is no partial and one exit:
  - at T when LRLR or neutral
  - at TP1 when HRLR
- HRLR → q1 = n: everything exits at TP1.
- Alt: thirds, with a second partial at the next pool [V3, M1].
- Alt: [T3] shows break-even at −1×, 50% at −2× and the rest at −2.5×.

**MGMT-2. Break-even (BE).**

- At the close of the bar where the **first** of these happens, set stop = E + 2 ticks (covers costs):
  - (a) TP1 fills
  - (b) MFE ≥ +1.0R (high ≥ E + R)
- **Not earlier.** Community ICT scripts warn against moving the stop to break-even too early, and move the stop to entry after TP1 [T4]. The project's test found BE at 0.5R worse in all periods.
- Alt: break-even at 1:1 only (older PB) [R1].
- Alt: *structure BE* (MGMT-3 active from entry). The stop reaches break-even only when a BOS up creates a protected low above E.

**MGMT-3. Structure trail.** Active once MGMT-2 has fired.

- At every 5m BOS up (D10), `stop = max(stop, PL_new − buf)`.
- Alt A, the FVG trail (tighter): `stop = max(stop, low[c1] − buf)` of the newest bullish 5m FVG formed after entry.
- Alt B, a 15m swing trail (k=1, looser), for the runner only.
- Sources: [M1] (trailing starts only after the Nth partial); [T5] notes (trail at new swing points).
- Warning: the old engine found trailing hurt. Adopt only if it improves every period.

**MGMT-4. Runner to the external draw.**

- Hold the remainder until T, the trailed stop, or an MGMT-5/6/7 exit.
- At T, close everything. Do not extend: delivery often stalls once the pool is taken [L2].
- Alt (rare, not default): if T is taken by a displacement candle and the next Tier-A pool is within `reach`, keep 1 contract with the stop at TP1.

**MGMT-5. Early exit on opposing CISD with displacement.**

- Exit at the bar close when a **bearish CISD (D11)** fires and **both** hold:
  - the breaking candle is a displacement candle (D2), or it creates a bearish 5m FVG
  - the up-series it breaks started after entry
- Active from entry (Default).
- Rationale: a CISD fires earlier and closer to the extreme than an MSS [L5]. [L1] says to act before the stop when the premise fails.
- Alt: active only after MFE ≥ +0.5R.
- Alt: exit only on an MSS, a close below PL. That is close to the stop anyway.

**MGMT-6. Giveback** (existing project rule; keep it).

- Once MFE ≥ +0.5R, a 5m close below E → exit at that close.
- Adopted 2026-10-15; it improved all 4 periods.

**MGMT-7. Time exits.**

- **Stall:** 12 bars (60 min) after entry, if MFE < +0.5R → exit at the close.
  - The numbers are ours. Alt: 6–18 bars.
  - "If it doesn't work quickly it is wrong" is common lore, but we found no source for it.
- **Premise:** if `overlap6 > 0.6` at bar 6 after entry and MFE < +0.5R → exit (DOL-6). This is an Alt to Stall.
- **Session:** at 12:00 ET (the start of NY lunch), exit if the stop is still below E (the trade is unprotected).
  - A protected runner (stop ≥ E) may run until the 15:55 ET hard flat.
  - Sources disagree [K1]. One says close before 11:00. Another says use the NY PM killzone mainly to close AM positions whose targets were not reached.
- No new entries 12:00–13:30.

**MGMT-8. Precedence on each bar.**

- Intrabar: stop, then TP1, then T. If the stop and a target are both touched in the same bar, the stop counts.
- At the close: MGMT-5, then MGMT-6, then MGMT-7, then MGMT-2, then MGMT-3.
- Every change takes effect on the next bar.

**MGMT-9. Fixed plan.**

- T and TP1 are fixed at entry.
- New pools that form in the path later are ignored (ours). Re-targeting mid-trade is where look-ahead bugs creep in.

---

## 6. Procedure (pseudo-code; long side, shorts mirror)

```
on close of 5m bar t:
    update closed HTF bars; swings (D1); pools and status (D7-D9); gaps and states (D3-D6);
    BOS / PL (D10); CISD series (D11); rotation state (DOL-2)

    if in_trade:
        # intrabar fills on bar t were already resolved: stop -> TP1 -> T (stop wins ties)
        if CISD_exit (MGMT-5) or giveback (MGMT-6) or time_exit (MGMT-7): exit at close[t]
        if not be_done and (tp1_filled or high_since_entry >= E + R): stop = max(stop, E + 2 ticks)  # MGMT-2
        if be_done and new BOS up at t: stop = max(stop, PL - buf)                                 # MGMT-3
        return

    if flat and entry_signal(t) and day_limits_ok (RISK-3):
        E  = close[t]
        S  = S_sweep - buf  (reversal)  |  PL - buf  (continuation)                   # STOP-1/2
        R  = E - S
        n  = floor(risk$ / ((R + 0.5) * 2.0))   # MNQ; 0.5 pt = 2 ticks              # RISK-2
        if n < 1: skip
        T_level = nearest Tier-A buy-side pool with minRR*R <= dist <= reach
                  else nearest Tier-B pool (same limits)
                  else fallback (DOL-9) or skip                                        # DOL-4
        if T_level - E < minRR * R: skip                                               # STOP-3
        TP1 = nearest internal draw with 1R <= dist < dist(T_level)                    # DOL-5
        if live opposing 1H/4H gap near edge < E + 1R: skip                            # DOL-6 blocking
        n_res = count resistance in (E, T_level)                                       # DOL-6
        if n_res >= 3: (no TP1 or TP1 - E < minRR*R) -> skip, else target = TP1, q1 = n
        else: q1 = (n == 1) ? 0 : min(n-1, ceil(n/2))
        place stop S, limit TP1 for q1, limit T_level - 2 ticks for n - q1
```

**Worked example** (numbers invented to show the arithmetic, with buf = 2 pt):

- London low 20,100 is swept at 09:50; the low prints 20,092. The IFVG trigger closes at E = 20,140 at 10:05.
- Stop: S = 20,092 − 2.0 = 20,090. R = 50 pts.
- Size: n = floor(350 / (50.5 × 2)) = **3 MNQ**.
- Above price:
  - a 5m swing high at 20,175 (0.7R: too close to be TP1)
  - a bearish 15m FVG at 20,198–20,214 (1.16R to its bottom)
  - the overnight high at 20,262 (Tier A, 2.44R)
- Targets: TP1 = 20,198 and T = 20,261.50.
- Path: n_res = 2 (one swing, one gap) → neutral.
- Plan: 2 MNQ exit at 20,198 and 1 runner targets 20,261.50. After TP1 fills, the stop goes to 20,140.50, then trails PL − 2 at each 5m BOS up.

---

## 7. Parameter table (starting values; tune as variants only, on all periods)

| param | default | alternatives | source |
|---|---|---|---|
| swing k, 5m / HTF | 2 / 1 | 1 everywhere; 3–5 | D1, MECH |
| displacement | body ≥ 1.0 ATR, body/range ≥ 0.6 | 0.7–1.5 ATR; 1.5 × mean body(20) | L8 (no number), T2 |
| FVG minimum, 5m | max(1 tick, 0.1 ATR_5m) | 1 tick; 0.25 ATR | L9 (no number) |
| gap mitigation (as a draw) | CE touched | first tap; full fill; body-based | L6, L9, T6 |
| EQH tolerance | max(2 ticks, 0.1 ATR_tf) | fixed ticks; ATR(200) × 0.1 | L3, L11 |
| sweep vs run | close back inside within 3 bars / 2 closes beyond | same-bar reclaim only | L10 |
| CISD reference | open of the first candle of the series | open of the last candle; close beyond the previous high/low | L5, T2, T3 |
| minRR to T | 2.0 | 1.0 (PB), 3.0 (ICT 2022 guide) | R1, I2, T5 |
| TP1 minimum distance | 1.0R | 0.5R; none | R1 (PB ignores closer levels) |
| partial size | 50% (ceil(n/2), keep ≥1 runner) | thirds; 100% when HRLR | V3, M1, T3 |
| BE trigger | TP1 or +1R | structure BE; +1R only | T4, R1, project tests |
| trail | 5m BOS → PL − buf | last-FVG c1; 15m swings | M1, T5 |
| early exit | CISD + displacement | CISD only after +0.5R; MSS | L5, L1 |
| giveback | +0.5R then close < E | n/a | project |
| stall exit | 12 bars, MFE < 0.5R | 6–18 bars; overlap6 > 0.6 | ours, L1 |
| session exit | 12:00 if unprotected; 15:55 hard flat | 11:00 | K1, MFFU |
| LRLR / HRLR | n_res ≤ 1 / ≥ 3 | weighted score | L1 (no number) |
| reach | max(0.5 ADR10, ADR10 − today's range) | none; 1.0 ADR10 | ours |
| stop buffer | max(2 ticks, 0.1 ATR_5m) | 1 tick; 2–5 pts | I2, MECH |
| risk per trade | $350 | 0.5–1% of 50K | P3, R1 |
| day limits | 2 trades; done after a win / 2 losses / −2R | 1 trade | R1, P1, P2 |

---

## 8. Where sources disagree, and what we picked

| topic | versions | picked |
|---|---|---|
| final target | nearest pool ≥1R capped at 3R (PB) / HTF draw (ICT, L2) / SD projections (I3, T3, T5) | nearest **Tier-A** pool ≥ 2R within reach. HTF beats LTF, but the *nearest* obvious one, as most people do. |
| "mitigated" | first tap / CE / full fill / body close | CE for targets; body close beyond the far edge for support |
| CISD level | first candle of the series (L5) / last candle (most scripts) / close beyond the previous high (T3) | first candle (fewer false exits). The others are Alts. |
| stop | sweep extreme / displacement origin / FVG candle 1 / FVG edge / CE | sweep extreme for reversals, protected low for continuations |
| BE | after TP1 / at 1:1 / after a BOS / never too early | first of TP1 or +1R |
| partials | 50% at the first FVG or pool (V3) / thirds (M1) / none, one and done (a search summary of one 2022 mentorship video describes a fixed 4-pt stop and no partials; not verified) | 50% at TP1, runner to T |
| time exits | before 11:00 / in the PM killzone if targets not hit (K1) | 12:00 if unprotected, 15:55 hard flat |
| equal highs tolerance | a few ticks / fraction of ATR / no fixed tolerance (L3) | max(2 ticks, 0.1 ATR_tf) |
| sweep reclaim | same candle / within a few bars (L10) | within 3 bars |

---

## 9. What this project already learned (do not re-learn it)

- **Earlier tests.** In the old engine, partials and trailing stops hurt. BE at 0.5R, profit locks, tighter stops and the IFVG-failure exit all lost on the 4-period total.
  - The *giveback* rule (MGMT-6) won and is adopted.
  - So test MGMT-1/3/5/7 one at a time against the current defaults, on every period.
  - Note: the old partials were R-based. DOL-based partials (TP1 at a real internal draw) are a different test.
- **Candidate lift ≠ taken-trade lift.** A filter that looks good on shadow trades can fail on the trades actually taken. Re-score on all periods.
- **Trade frequency is a hard constraint: 1–4 trades a week.** Vetoes (STOP-3, DOL-6 blocking/HRLR, DOL-8 bias) cut trades. Report trades per week with every variant.
- **Five-year verdict:** no proven edge yet. These rules change *exits*; they cannot create entry edge on their own.

**Suggested build order** (one variant each): DOL-4 target → DOL-5 + MGMT-1/2 → MGMT-3 → MGMT-5 → MGMT-7 → DOL-6 vetoes.

---

## 10. Sources

Read in full this session (LuxAlgo concept library; secondary, and partly subjective by its own admission):

- [L1] Low-resistance vs high-resistance liquidity runs: https://www.luxalgo.com/library/concept/low-resistance-vs-high-resistance-liquidity-runs/
- [L2] Draw on liquidity: https://www.luxalgo.com/library/concept/draw-on-liquidity/
- [L3] Equal highs/lows as liquidity: https://www.luxalgo.com/library/concept/equal-highs-lows-as-liquidity/
- [L4] Internal vs external range liquidity: https://www.luxalgo.com/library/concept/internal-vs-external-range-liquidity/
- [L5] Change in state of delivery: https://www.luxalgo.com/library/concept/change-in-state-of-delivery/
- [L6] Consequent encroachment: https://www.luxalgo.com/library/concept/consequent-encroachment/
- [L7] New week opening gap (NWOG/NDOG): https://www.luxalgo.com/library/concept/new-week-opening-gap/
- [L8] Displacement: https://www.luxalgo.com/library/concept/displacement/
- [L9] Fair value gap (also volume imbalance and liquidity void): https://www.luxalgo.com/library/concept/fair-value-gap/
- [L10] Liquidity sweep: https://www.luxalgo.com/library/concept/liquidity-sweep/
- [L11] Smart Money Concepts indicator (ATR-scaled EQH/EQL threshold; defaults not shown): https://www.luxalgo.com/library/indicator/SRsr9SLs-smart-money-concepts

ICT video summaries (AI-generated, read; not verbatim):

- [V1] Internal & External Liquidity (Daily Bias), ICT Concepts: https://videohighlight.com/v/3OivsP1j_UE
- [V2] Low Resistance Liquidity Runs: https://videohighlight.com/v/Yq3Qb7-HcuI
- [V3] A+ ICT Entry Checklist (stops just beyond the FVG; partials at an FVG/order block, then at the next high/low or equal highs/lows): https://videohighlight.com/v/lpam8F-N3EM

Search-result summaries only. The page bodies were images/base64 or not fetched, so treat these as weak:

- [I1] innercircletrader.net, IRL & ERL guide: https://innercircletrader.net/tutorials/ict-internal-external-liquidity/
- [I2] innercircletrader.net, Complete ICT Trading Strategy 2022 (stop beyond the sweep wick with a small buffer; 1:3): https://innercircletrader.net/tutorials/complete-ict-trading-strategy-2022/
- [I3] innercircletrader.net, ICT 2024 Mentorship Lecture 2 (−2/−2.5 staged exits; stop beyond the post-07:00 swing): https://innercircletrader.net/tutorials/ict-2024/mentorship-lecture-2/
- [I4] innercircletrader.net, Market Maker Buy Model (older highs as partials): https://innercircletrader.net/tutorials/ict-market-maker-buy-model/
- [I5] innercircletrader.net, Market Maker Sell Model (scale-outs at −1/−1.5, finals at −2/−2.5): https://innercircletrader.net/tutorials/ict-market-maker-sell-model/
- [K1] Killzone exit timing:
  - https://innercircletrader.net/tutorials/master-ict-kill-zones/
  - https://quantamentaltrader.substack.com/p/unlocking-ict-kill-zones-the-secret
  - https://www.eltraderfinanciado.com/ar/blog/killzones-ict
- [H1] HRLR & LRLR thread (MetalsMine): https://www.metalsmine.com/thread/1344693-mastering-liquidity-runs-with-hrlr-lrlr

Implementations (TradingView / vendors):

- [T1] SMC Structure Identifier (protected highs/lows; close-based BOS): https://jp.tradingview.com/script/wsjq882z-SMC-Structure-Identifier/
- [T2] CISD scripts (open of the last opposing candle vs the whole run; body ≥ 50% filter):
  - https://www.tradingview.com/script/uSaRPnJ8
  - listing incl. cephxs CISD [base]: https://cn.tradingview.com/scripts/fib/
- [T3] Fractal Structure Model [Pro] (BE at −1×, 50% at −2×, rest at −2.5×; stop below the C1 liquidity low): https://tw.tradingview.com/script/70aYMnxa-Fractal-Structure-Model-Pro/
- [T4] Community ICT scripts (stop beyond the swing + ATR buffer, BE after TP1; "don't move the stop to break-even too early"). The exact script was not pinned down:
  - https://tr.tradingview.com/scripts/search/fair%20value%20gap/page-19
  - https://www.tradingview.com/script/ABYnIcdl/
- [T5] TTrades Fractal Model (HTF close + LTF CISD): https://tradingview.com/script/XdwK9qQQ-Fractal-Model-Pro-TTrades. Third-party notes (min 2R, −2/−4 projections, trail at new swings): https://www.scribd.com/document/809576453/tt
- [T6] FVG/IFVG mitigation modes and close-through inversion:
  - https://www.tradingview.com/scripts/fairvaluegap/
  - https://ar.tradingview.com/script/VDuT2dJF-Inverse-Fair-Value-Gaps-HuntsPip
- [M1] MQL5 "No Risk PropFirm" EA (up to 4 partials, BE, trailing only after the Nth partial): https://www.mql5.com/ja/market/product/185364

Prop firms and risk:

- [P1] Topstep rules (50K DLL $1,000): https://tradingfunder.com/topstep-rules ; Topstep vs Apex: https://www.futureshive.com/blog/topstep-vs-apex-2026
- [P2] MFFU Builder 50K (soft DLL $1,000; MLL $2,000 EOD-trailing). Checked on help.myfundedfutures.com 2026-10-15; see project memory.
- [P3] Size from the drawdown, not the balance; skip when the technical stop needs more than the cap:
  - https://proptradingvibes.com/blog/position-sizing-prop-firms
  - https://nexusfi.com/a/prop-firms/prop-firm-risk-rules (403 here; search summary)
  - Max-loss-per-trade rules: https://tradingfunder.com/concepts/maximum-loss-per-trade-rule/
- [R1] research/lab/MECH_RULES.md (PB Blake: done after a win, 1–2 trades a day, nearest liquidity 1–3R, BE at 1:1)
