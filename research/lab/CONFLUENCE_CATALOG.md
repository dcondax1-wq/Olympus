# Confluence catalog: what traders stack on an entry, and how we compute it (16 Oct 2026)

This catalog covers 46 popular confluences, split into 92 tested booleans, plus 8 that need data we don't have. For
each one it gives:

1. the definition as taught,
2. the exact mechanical, causal rule in `tools/lab_confluences.py` (the key in `features()`),
3. what educators claim it does,
4. sources.

Test results are in `research/lab/CONFLUENCE_RESULTS.md`.

**How to read the sources.** Most of them are secondary. innercircletrader.net is a follower site (Ayub Rana), not
Michael Huddleston's own; his site is theinnercircletrader.com. The others are vendor or education pages: LuxAlgo,
TradingView scripts, NinjaTrader, NexusFi. Original ICT video transcripts could not be fetched. "(sr)" means the page
was seen in search results but not opened. No ICT source publishes a backtest. The few independent numbers come from
nqstats.com (NQ 2016-2025) and academic papers (ORB, intraday momentum, FOMC drift).

**Rules every feature follows.** Rules are written for a long; shorts are the mirror image.

- **Causality.** Only 5m bars whose close is at or before `entry_t` are used (open time + 300 s <= `entry_t`).
- **Higher timeframes.** 15m and 1H bars are built from those 5m bars (clock hours anchored at 18:00 ET). One is used
  only once its last 5m bar has closed.
- **Context.** Day and week context comes from completed sessions, plus today's closed bars.
- **Session windows** (Asia, London, CBDR, IB, OR, opens) are used only after their last bar has closed. Before that
  the feature is `None`, which counts as "not present".
- **Entry price.** The reference price is the trade's own fill when it is given (rule-module trades). Otherwise it is
  the open of the 5m bar that starts at `entry_t`, which is known at that instant (engine trades). Failing both, it
  is the last close.
- **Time of day** comes from `entry_t` as the bed reports it. Modules that enter at the signal bar's close report that
  bar's open time, 5 minutes before the fill. The "first-bar open known at its open" case (an entry at exactly 09:30)
  is the only difference the no-lookahead check finds: `python -X utf8 tools/lab_confluences.py lookahead 120`.
- **Session windows** count as finished by the clock (IB at 10:30, OR at 10:00, Asia at 00:00, London at 05:00, CBDR
  at 20:00). So `features()` gives the same answer live, on a frame that ends at the last closed bar.
- **ATR** is a 14-bar simple mean of the 5m true range. **ADR** is the mean full-session (18:00-17:00) high-low over
  the prior 20 sessions.
- **Round numbers** use unadjusted prices. The back-adjustment offsets come from `data/NQ_rolls.json` and
  `data/ES_rolls.json`.
- **Data.** Futures only: `data/NQ_5m.csv` (NQ1!) and `data/ES_5m.csv` (ES1!, from 2025-04-13). No CFD data.

## A. ICT core: premium/discount and OTE

**1. Premium / discount and equilibrium.**
- **Definition:** Take a dealing range between an established swing high and swing low. 50% is equilibrium; above it
  is premium, below it is discount.
- **Claimed:** Buy only discount PD arrays under bullish bias, and sell only premium ones. Educators disagree on
  which range to use (trade-timeframe swing, daily/weekly, IPDA 20/40/60-day).
- **We compute four ranges.** Each is True when the long entry is below the range's 50%:
  - `pd_disc_pdr`: the prior day's full-session range.
  - `pd_disc_day`: today's range so far.
  - `pd_disc_h1`: the 1H dealing range, from the last confirmed 1H 3-candle swing high and swing low.
  - `pd_disc_week`: the prior week's range.
- **Sources:** innercircletrader.net/tutorials/ict-premium-and-discount-zone-identification/ (sr);
  innercircletrader.net/tutorials/ict-pd-array-key-to-trade-execution/ (sr); luxalgo.com/library/concept/premium-and-discount/ (sr);
  innercircletrader.net/tutorials/ict-ipda/ (sr)

**2. Equilibrium as a no-trade zone.** `near_eq_pdr` is True when the entry lies within 10% of the prior-day range
around its 50%.
- **Claimed:** Equilibrium is fair value; edges are better than the middle.
- **Source:** as item 1.

**3. OTE, optimal trade entry.**
- **Definition:** The 62-79% retracement (70.5% sweet spot) of the impulse leg being traded.
- **We compute** `ote_5m`. The leg runs from the lowest low of the last 36 bars (3 h) to the highest high since. It
  must be at least 1.5 ATR. The feature is True when (leg high - entry) / leg is in [0.62, 0.79].
- **Claimed:** A continuation entry with defined risk. It needs a rejection or a lower-timeframe MSS in the zone.
- **Variants:** 61.8 vs 62 and 78.6 vs 79. Some sources require a prior sweep plus MSS.
- **Sources:** innercircletrader.net/tutorials/ict-optimal-trade-entry-ote-pattern/; innercircletrader.net/tutorials/ict-fibonacci-levels/ (sr);
  luxalgo.com/library/concept/optimal-trade-entry/ (sr)

## B. ICT PD arrays

**4. Fair value gap (FVG) and consequent encroachment.**
- **Definition:** A bullish FVG is the gap between candle 1's high and candle 3's low; the bearish one is the mirror.
  CE is its 50% level.
- **We compute:**
  - `in_fvg_5m`: the entry is inside an unfilled bullish 5m FVG (± 0.1 ATR) formed in the last 24 bars (2 h).
    "Unfilled" means no close below its bottom since it formed.
  - `fvg_1h_leg`: a bullish FVG of at least 0.25 ATR formed in the last 12 bars (the displacement left a gap).
- **Claimed:** Price returns to rebalance the gap before continuing. Entries are at the edge or CE.
- **Variants:** Invalidation on a body close beyond CE, or only on a full fill.
- **Sources:** innercircletrader.net/tutorials/fair-value-gap-trading-strategy/; innercircletrader.net/tutorials/ict-consequent-encroachment/;
  luxalgo.com/library/concept/consequent-encroachment/ (sr)

**5. Inversion FVG (IFVG).**
- **Definition:** An FVG that price body-closes through the wrong way. A closed-through bearish FVG becomes support.
- **We compute** `ifvg_5m`: a bearish 5m FVG from the last 36 bars was closed above its top within the last 12 bars.
- **Claimed:** The flipped gap acts as support on the retest, which makes it a reversal trigger.
- **Sources:** innercircletrader.net/tutorials/ict-inversion-fair-value-gap/ (sr); luxalgo.com/library/concept/inversion-fvg/ (sr)

**6. Order block (OB).**
- **Definition:** The last down-close candle before an impulsive up move. The mean threshold is its 50%.
- **We compute** `in_ob_5m`, in three steps:
  1. A displacement candle has a body of at least 1.0 × ATR, within the last 36 bars.
  2. The OB is the last down candle among the 5 before it.
  3. True when there has been no close below the OB low since, and the entry is inside the OB high-low ± 0.1 ATR.
- **Claimed:** An institutional zone. Enter on the first clean retest with an LTF confirmation.
- **Variants:** Body vs full range, and how invalidation is defined.
- **Sources:** innercircletrader.net/tutorials/ict-order-block/; luxalgo.com/library/indicator/oObsuObl-ict-order-block-pro/;
  tradingview.com/script/1M4FG5X2-ICT-Order-Blocks-v2-Debug (sr)

**7. Breaker block.**
- **Definition:** A failed OB after a sweep. Price makes a lower low, then closes above the swing high's up-close
  candle(s), which then act as support.
- **We compute** `in_breaker_5m`, in three steps:
  1. A confirmed 5m swing high falls in the last 48 bars.
  2. The dip after it undercuts the low of the 12 bars before it.
  3. A close above the swing high follows. True when the entry is back inside the last up candle at the swing
     high ± 0.1 ATR, and there has been no close below that candle since.
- **Claimed:** A clean reversal trigger on the retrace.
- **Sources:** innercircletrader.net/tutorials/ict-breaker-block-trading/; fxnx.com/en/blog/master-breaker-blocks-ict-guide-2026-trading (sr)

**8. Mitigation block.**
- **Definition:** As a breaker, but the dip made a higher low (a failure swing with no sweep).
- **We compute** `in_mitig_5m`, using the same code as item 7 with the higher-low branch.
- **Claimed:** Unfilled orders get "mitigated" on the return. innercircletrader also uses the term for a retested OB,
  so sources conflict.
- **Sources:** innercircletrader.net/tutorials/ict-mitigation-block-explained/; it.tradingview.com/script/w0lG96Ua-Breaker-Mitigation-Blocks (sr)

**9. Rejection block.**
- **Definition:** A long wick at a swing extreme that swept an old low. The zone runs from the body to the wick low.
- **We compute:**
  - `rejection_wick`: the lowest bar of the last 6 has a lower wick of at least 50% of its range.
  - `in_rejection_blk`: the lowest bar of the last 24 has a wick of at least 50% of its range and at least 0.5 ATR,
    the entry is inside its wick zone ± 0.1 ATR, and that low is unbroken. These are LuxAlgo's thresholds.
- **Claimed:** The wick marks a raid; the reversal repeats on the revisit, with a tighter entry than an OB.
- **Sources:** innercircletrader.net/tutorials/ict-rejection-block/; luxalgo.com/library/indicator/rejection-block/ (sr)

**10. Balanced price range (BPR).**
- **Definition:** The overlap of a bearish FVG and a later bullish FVG.
- **We compute** `in_bpr_5m`: the entry is inside that overlap ± 0.1 ATR, with both gaps formed in the last 24 bars.
- **Claimed:** A stronger flip zone than an IFVG alone.
- **Sources:** innercircletrader.net/tutorials/ict-balanced-price-range-bpr/ (sr); innercircletrader.net/tutorials/powerful-ict-reversal-patterns/ (sr)

**11. Volume imbalance (VI).**
- **Definition:** Two consecutive candles whose bodies don't touch while their wicks overlap.
- **We compute** `vol_imb_5m`: in the last 6 bars there are two up candles, the second opening at least 0.5 pt above
  the first's close, with its low at or below the first's high.
- **Claimed:** Minor support/resistance that refines OB/FVG edges.
- **Sources:** luxalgo.com/library/concept/volume-imbalance/; innercircletrader.net/tutorials/ict-enigma-fair-value-gap/ (sr)

**12. Liquidity void.**
- **Definition:** A fast one-way run with little overlap, which price is drawn back to fill.
- **We compute** `liq_void_draw`, True when all of these hold:
  - a bearish candle of at least 2 ATR range exists in the last 72 bars (6 h);
  - its high is above the entry;
  - price has not traded back to that high since.

  So an unfilled void sits above the long entry, acting as a draw.
- **Claimed:** Price rebalances voids. Only one source was found.
- **Source:** innercircletrader.net/tutorials/master-ict-liquidity-void/ (sr)

## C. ICT structure and liquidity

**13. MSS / BOS / CHoCH with displacement.**
- **Definitions:**
  - BOS is a break in the trend's direction.
  - CHoCH is the first break against the trend.
  - ICT's MSS is a break of the recent swing, after a sweep, with displacement: large bodies that leave an FVG.
- **We compute** these from 5m fractal swings (2 bars each side, confirmed 2 bars later):
  - `mss_disp`: a close through the latest unbroken swing high within the last 12 bars, on a bar whose body is at
    least 0.8 ATR or that left an FVG.
  - `choch_5m`: such a break where that swing high was a lower high.
  - `trend_5m_with`: the last 5m break was upward.
- **Claimed:** The 2022 model is sweep, then MSS with displacement, then FVG entry. A slow drift through a level
  doesn't count.
- **Sources:** fxopen.com/blog/en/market-structure-shift-meaning-and-use-in-ict-trading/ (sr); luxalgo.com/library/concept/displacement/ (sr);
  innercircletrader.net/tutorials/ict-displacement-move/ (sr); tradingview.com/script/uMi5os2q-ICT-2022-Mentorship-Model-TFO (sr)

**14. HTF trend / bias.**
- **Definition:** Trade with the higher-timeframe order flow.
- **We compute:**
  - `trend_15m_with` and `trend_1h_with`: the last close through a confirmed 3-candle swing on closed 15m / 1H bars
    was upward.
  - `daily_bias_with`: the ICT 2022 daily draw. Up if the prior day closed above the day before's high, or swept that
    day's low and closed back inside it; mirror for down; otherwise no bias.
- **Claimed:** HTF bias picks the side and the draw.
- **Sources:** the ICT 2022 model rules in `research/lab/M22_RULES.md`; item 13 sources.

**15. Internal vs external range liquidity (IRL / ERL).**
- **Definition:** ERL is old highs and lows at the range edges (PDH/PDL, PWH/PWL, session H/L). IRL is FVGs and OBs
  inside the range. Price alternates between them.
- **We compute:**
  - `erl_swept`: a sell-side external level was traded through within the last 36 bars. The levels are PDL, PWL, the
    Asia low and the London low, each only once formed, and the level must have been untaken earlier that day.
  - `erl_to_irl`: `erl_swept` and `in_fvg_5m` are both true.
- **Claimed:** After an ERL raid, expect a retrace to IRL and a run to the opposite ERL.
- **Sources:** innercircletrader.net/tutorials/ict-internal-external-liquidity/ (sr); luxalgo.com/library/indicator/rm5Q63nM-ict-irl-erl-zones-v2/ (sr)

**16. Inducement (IDM).**
- **Definition:** An SMC rather than core ICT idea. It is a minor pullback in front of the point of interest, whose
  stops form bait; the POI is valid only after the IDM is swept.
- **We compute** `inducement`: in the down-leg (from the highest high of the 24 bars before the last-hour low to that
  low), a confirmed 5m swing low sits above the final low and was taken before it. This is the "staircase" leg.
- **Claimed:** Wait for the IDM sweep, then enter at the POI.
- **Already tested** as noise on the old engine (`research/ICT_REPORT.md`).
- **Sources:** luxalgo.com/library/concept/inducement/ (sr); kr.tradingview.com/script/wl2qV9eC-Structure-TradingHub (sr)

**17. CISD, change in state of delivery.**
- **Definition:** A body close above the opening price of the down-close candle run that made the low.
- **We compute** `cisd`. Take the lowest bar of the last 12, walk back through the consecutive down candles ending
  there, and record the open of the first one. True when a later close is above that open.
- **Claimed:** An earlier reversal trigger than the MSS, with tighter risk and more false signals.
- **Sources:** innercircletrader.net/tutorials/ict-change-in-the-state-of-delivery/; innercircletrader.net/tutorials/ict-cisd-and-ict-mss/ (sr)

**18. SMT divergence, NQ vs ES.**
- **Definition:** Correlated indices disagree at the same swing: one makes a lower low and the other does not.
- **We compute**, on the same clock windows for NQ and ES, a 4-hour reference (bars j-47..j-6) against the last 30
  minutes:
  - `smt_es`: exactly one index swept its reference low.
  - `es_confirms`: both did.
- **Claimed:** A confirmation layer at an HTF PD array, not a stand-alone trigger.
- **Already tested** as noise (`research/ICT_REPORT.md`).
- **Sources:** innercircletrader.net/tutorials/ict-smt-divergence-smart-money-technique/ (sr); luxalgo.com/library/concept/smart-money-technique-divergence/ (sr)

## D. ICT time and opening prices

**19. ICT macros.**
- **Definition:** Short algorithmic windows: 02:33-03:00, 04:03-04:30, 08:50-09:10, 09:50-10:10, 10:50-11:10,
  11:50-12:10, 13:10-13:40 and 15:15-15:45 ET. 15:50-16:00 is a separate MOC macro.
- **We compute** `in_macro`: the entry time falls inside any of the eight windows.
- **Claimed:** Price seeks liquidity or rebalances an FVG inside them; 09:50-10:10 is called best for indices.
- **Variants:** One page describes macros as the last 10 minutes of each hour plus the first 10 of the next.
- **Sources:** innercircletrader.net/tutorials/ict-macro-time-based-strategy/; luxalgo.com/library/indicator/ict-macros/ (sr)

**20. Silver Bullet hours.**
- **Definition:** 03:00-04:00, 10:00-11:00 and 14:00-15:00 ET. Inside the hour, look for an MSS toward the draw and
  take the FVG it leaves.
- **We compute** `in_sb_hour`.
- **Claimed:** A one-shot setup per window, with NY AM the strongest.
- **Sources:** innercircletrader.net/tutorials/ict-silver-bullet-strategy/; luxalgo.com/library/indicator/ict-silver-bullet/ (sr)

**21. Killzones.**
- **Definition:** Futures defaults are London 02:00-05:00, NY AM 08:30-11:00 (some use 09:30-11:00 or 07:00-10:00)
  and NY PM 13:30-16:00.
- **We compute** `kz_london`, `kz_ny_am` (08:30-11:00), `kz_ny_pm` and `first_hour_rth` (09:30-10:30).
- **Claimed:** These are the windows where institutional flow arrives; don't enter outside them.
- **Sources:** innercircletrader.net/tutorials/master-ict-kill-zones/; tradingview.com/script/2vzFMAWU-Zero-Noise-Killzones/

**22. Quarterly Theory (Daye).**
- **Definition:**
  - The day splits into quarters: Q1 18-00, Q2 00-06, Q3 06-12, Q4 12-18.
  - Each quarter splits into four 90-minute cycles (NY AM: 06:00, 07:30, 09:00, 10:30).
  - Each cycle splits into four 22.5-minute micro quarters.
  - The "true open" is the open of Q2; AMDX is the phase sequence.
- **We compute:**
  - `qt_ny_q3`: entry in 09:00-10:30, the Q3 of NY AM.
  - `qt_micro_23`: entry in the 2nd or 3rd micro quarter of its 90-minute cycle.
  - `below_tso`: entry below the true session open, the open of Q2 of the current 6-hour session (07:30 for NY AM).
- **Claimed:** A Q2 raid around the true open is the manipulation; trade the Q3 distribution.
- **Sources:** tradingview.com/script/n2aeO1GB-Daye-Quarterly-Theory-by-toodegrees/; luxalgo.com/library/concept/quarterly-theory/

**23. Opening prices: midnight open (the "true day"), 18:00 Globex open, 08:30 and 09:30 opens, weekly open.**
- **Definition:** On a bullish day the low forms below the opening price, so buy below the open in a bullish day.
- **We compute** `below_mo`, `below_globex_open`, `below_0830`, `below_rth_open` and `below_week_open` (Sunday
  18:00): the entry is below that open.
- **Claimed:** Price returns to and respects the midnight open. A LuxAlgo vendor claim, unverified, puts the return
  rate at 63-74%.
- **Sources:** luxalgo.com/library/indicator/y5sLA4Ls-ict-ny-midnight-open-and-divider/; innercircletrader.net/tutorials/ict-2024/ict-2024-mentorship-lecture-4/;
  innercircletrader.net/tutorials/ict-power-of-3/

**24. NWOG / NDOG opening gaps.**
- **Definitions:**
  - NWOG: Friday's 17:00 close vs Sunday's 18:00 open.
  - NDOG: the 17:00 close vs the 18:00 reopen each day.
  - CE is 50% of the gap.
- **We compute:**
  - `nwog_draw` / `ndog_draw`: the gap's CE is above the long entry by more than 0.1 ATR (the gap is a draw). Gaps of
    at least 1 tick only.
  - `in_nwog`: the entry is inside the NWOG ± 0.1 ATR.
- **Claimed:** Gaps act as magnets and as support/resistance; CE and quarter levels react most.
- **Sources:** innercircletrader.net/tutorials/ict-new-week-opening-gap-nwog/; innercircletrader.net/tutorials/ict-new-day-opening-gap-ndog/ (sr);
  luxalgo.com/library/indicator/iZiHlcag-ict-opening-gaps/ (sr)

**25. Judas swing.**
- **Definition:** A false move against the daily bias at the session open, measured from the midnight open. It
  counts only once price returns through the open. The window is 00:00-05:00; some extend it to 09:30.
- **We compute:**
  - `judas_mo`: after midnight, price ran at least 0.1 ADR below the midnight open, and the entry is back above it.
  - `judas_rth`: the same around the 09:30 open, for entries from 09:45 to 12:00.
- **Claimed:** Expect the opposite of the early move.
- **Sources:** innercircletrader.net/tutorials/ict-judas-swing-complete-guide/; luxalgo.com/library/concept/judas-swing/ (sr)

## E. Ranges and profiles

**26. Daily-candle Power of 3 (AMD).**
- **Definition:** The day opens, makes a manipulation wick below the open, then distributes to a close near the high.
- **We compute** `po3_daily`: today's low so far is at least 0.15 ADR below the 18:00 open, and the entry is no more
  than 0.15 ADR above that open (buying the manipulation, before distribution).
- **Claimed:** On a bullish day, buy in discount below the open; trade only the distribution.
- **Variants:** The open is 00:00 for some, 18:00 for others.
- **Already tested** as noise or slightly negative on the old engine.
- **Sources:** innercircletrader.net/tutorials/ict-power-of-3/; tradingview.com/ideas/powerofthree/ (sr)

**27. ICT weekly profiles.**
- **Definition:** Twelve templates, including classic Tuesday low of week, Wednesday low of week, consolidation
  Thursday reversal and seek-and-destroy Friday.
- **We compute** `wk_profile_early`: Mon-Wed, the week's range so far is at least 0.5 ADR, and the entry is in its
  bottom 30% (buying a low of week that is forming early). Day of week is also tested alone: `dow_*`.
- **Claimed:** Once the Tue/Wed extreme is in, trade away from it. No frequencies are published.
- **Sources:** innercircletrader.net/tutorials/ict-weekly-range-profiles/; de.tradingview.com/chart/GC1%21/vVKtluBi-Master-ICT-Weekly-Profiles

**28. CBDR and Asia range standard-deviation projections.**
- **Definition:** CBDR is the 14:00-20:00 NY range. Range-height multiples ("SDs") stacked beyond it project the
  day's extremes: the low of a buy day near -1 to -3 SD. The Asia range (20:00-00:00) is used when the CBDR is too
  wide. CBDR is said to be valid only when small.
- **We compute:**
  - `cbdr_ext`: the day's low since 20:00 is 1 to 4 CBDR heights below the CBDR low.
  - `asia_ext`: the day's low since 00:00 is 2 to 4 Asia heights below the Asia low.
- **Claimed:** The day's extreme forms at a projected level, often at London close.
- **Sources:** innercircletrader.net/tutorials/ict-central-bank-dealers-range/; my.tradingview.com/script/5mCuGUSR-Range-Projections-TFO/

**29. Asia range as accumulation.**
- **Definition:** A tight Asia range is the accumulation that London and NY raid.
- **We compute** `asia_small`: the Asia range is at most 40% of the 20-day ADR.
- **Claimed:** The Asia extremes are the first targets, and the London raid often sets the day's extreme.
- **Independent data:** nqstats (NQ 2016-25) reports NY breaking the London high 80.8% of the time after London
  partly engulfs Asia upward. It has no Asia-size split.
- **Sources:** nqstats.com/aln_sessions.html; luxalgo.com/library/indicator/k1qv9OWl-ict-asian-range-and-killzones-power-of-3/ (sr)

## F. Auction market theory and volume

**30. Session VWAP and SD bands.**
- **Definition:** VWAP = Σ(typical price × volume) / Σvolume from the anchor. The bands sit at ±1/2/3 volume-weighted
  SD.
- **We compute** with typical price (H+L+C)/3 and 5m volume:
  - `vwap_rth_with`: entry above the 09:30 VWAP.
  - `vwap_eth_with`: entry above the 18:00 VWAP.
  - `vwap_2sd_fade`: entry below the session VWAP - 2 SD.
  - `vwap_1sd_inside`: entry within ±1 SD.
- **Claimed:** On rotational days, fade the outer bands back to VWAP. On trend days, buy pullbacks to VWAP or 1 SD
  and don't fade.
- **Variants:** Desks anchor at RTH, while some scripts anchor at Globex 18:00.
- **Sources:** luxalgo.com/library/concept/vwap-bands; tradingview.com/script/mthvTwSg-VWAP-Intraday-Weekly-Monthly/;
  sfi.ch (Barbon, Zarattini, Aziz: intraday momentum with a VWAP stop) (sr)

**31. Prior-day value area (VAH / VAL / POC) and the 80% rule.**
- **Definition:** POC is the highest-volume price; the value area is about 70% of volume around it. The 80% rule:
  open outside value, re-enter and hold, and price runs to the other edge.
- **We compute** a prior RTH profile, with each 5m bar's volume spread evenly over its range in 1-pt (NQ) / 0.25 (ES)
  bins and a 70% value area grown out from the POC. Two features come from it:
  - `in_prior_value`: entry inside VAL..VAH.
  - `poc_side_with`: entry above the POC.
- **Claimed:** VAH/VAL are acceptance/rejection pivots, and the POC is a magnet.
- **Variants:** 68% vs 70%, volume vs TPO, RTH vs full session.
- **Sources:** luxalgo.com/library/concept/80-percent-rule; ninjatrader.com/futures/blogs/how-to-trade-futures-use-volume-profile-to-reveal-significant-price-level/;
  nexusfi.com/a/concepts/80-percent-rule (sr)

**32. Open in / out of value (Dalton open location).**
- **Definition:** Where the 09:30 open sits against prior value. Inside value means acceptance, so trade rotation;
  outside means imbalance, so expect range extension or a return to value.
- **We compute** `open_in_value` (09:30 open inside the prior VA) and `open_out_value_with` (opened above VAH, for a
  long).
- **Claimed:** An out-of-range open plus a drive is the strongest continuation read.
- **Sources:** luxalgo.com/library/concept/open-types/; Dalton, *Mind Over Markets* (book contents, sr); nexusfi.com/showthread.php?p=636636 (sr)

**33. Initial balance (IB, 09:30-10:30).**
- **Definition:** The first RTH hour's range. Extensions are measured in multiples of it.
- **We compute** these only after 10:30:
  - `ib_narrow`: IB is under 30% of ADR.
  - `ib_break_with`: a 5m close above the IB high came before the entry.
- **Claimed:** A narrow IB favours trend or normal-variation days; a wide one contains the day.
- **Independent data:** nqstats (NQ 2016-25): one side of the IB breaks by the close 96.1% of the time, and when the
  10:30 close is above the IB mid, the IB high breaks 82.3% of the time.
- **Sources:** nqstats.com/ib_breaks.html; luxalgo.com/library/concept/initial-balance

**34. Opening range (09:30-10:00) and ORB.**
- **Definition:** The high/low of the first N minutes; trade the breakout.
- **We compute** these only after 10:00:
  - `orb_with`: entry above the 30-minute OR high.
  - `in_or`: entry inside the OR.
- **Claimed:**
  - Zarattini and Aziz report strong QQQ results for a 5-minute ORB.
  - Gao et al. (JFE 2018) find the first half hour predicts the last half hour.
  - A replication on CFD index data is about breakeven after costs. CFD data is not used here.
- **Sources:** papers.ssrn.com/abstract=4416622 (sr); concretumgroup.com/can-day-trading-really-be-profitable/; mql5.com/en/blogs/post/776235

**35. HVN / LVN.**
- **Definition:** Thick and thin rows of a volume profile.
- **We compute** a 2-pt-bin profile of the prior 5 sessions:
  - `at_lvn`: the entry's bin is under 0.5x the median nonzero bin.
  - `at_hvn`: the entry's bin is over 1.5x.
- **Claimed:** HVNs slow price and act as support/resistance; price travels fast through LVNs. Sources disagree on
  whether an LVN is itself support/resistance.
- **Sources:** ninjatrader.com/futures/blogs/how-to-trade-futures-use-volume-profile-to-reveal-significant-price-level/; tradezella.com/learning-items/volume-profile (sr)

**36. Day type: trend day vs range day.**
- **Definition:** Dalton day types are normal, normal variation, trend, double distribution and neutral. A trend day
  shows a narrow IB, early extension, one-timeframing and a close at the extreme.
- **We compute:**
  - `trend_day_with`: price is at least 0.4 ADR above the 18:00 open and in the top 25% of today's range so far.
  - `trend_day_against`: the mirror.
- **Claimed:** Spot trend days early and stop fading them.
- **Sources:** luxalgo.com/library/concept/day-type-taxonomy; linnsoft.com/techind/day-types-rtx (sr)

## G. Classic levels, calendar and volatility

**37. Round numbers.**
- **Definition:** 00/50 handles (and 25/75 quarters; NQ 100s) cluster orders: take-profits at the number, stops just
  beyond it.
- **We compute** on unadjusted price:
  - `round_big`: the lowest low of the last 6 bars is within 0.15 ATR (at least 0.5 pt) of a 100-pt (NQ) / 50-pt (ES)
    level.
  - `round_q`: the same for 25-pt levels.
- **Evidence:** Osler (NY Fed SR125) found this in FX order books. No ES/NQ-specific study was found.
- **Sources:** newyorkfed.org/medialibrary/media/research/staff_reports/sr125.pdf (sr); atas.net/blog/the-magic-of-round-numbers/

**38. Prior-day and prior-week high/low.**
- **Definition:** These are buy-side and sell-side liquidity; a sweep plus displacement signals a reversal.
- **We compute:**
  - `pdl_swept` / `pwl_swept`: the prior-day / prior-week low was traded through within the last 12 bars, and was
    untaken earlier.
  - `in_pw_range`: entry inside the prior week's range.
- **Independent data:** nqstats (NQ RTH 2016-25): an open above the prior high closes above it 69.9% of the time.
- **Sources:** nqstats.com/rth_breaks.html; luxalgo.com/library/indicator/rtO4R9cQ-pdh-pdl-pwh-pwl-ict-bias-filter/ (sr)

**39. Day of week.**
- **We compute** `dow_mon` .. `dow_fri`, using the trading day.
- **Claimed:** "Turnaround Tuesday" after a down Monday. Monday has the smallest NY range and Friday the largest
  (Edgeful). Academic work finds weekday effects swamped by volatility.
- **Sources:** edgeful.com/blog/posts/best-day-of-week-trading-strategy; cxoadvisory.com/calendar-effects/any-recent-day-of-the-week-anomalies (sr)

**40. High-impact news days.**
- **We compute** from `data/news/events.csv`, high impact only:
  - `news_day`: CPI, NFP or FOMC today.
  - `fomc_day`.
  - `cpi_nfp_day`.
- **Claimed:**
  - Liquidity is pulled at the release. Educators split between fading and following.
  - Intraday momentum is stronger on news days (Gao et al.).
  - The pre-FOMC drift (Lucca and Moench) faded after 2015 (Kurov et al.).
- **Data gap:** The archive has no 08:30/10:00 releases before 2023 (see `research/FIVE_YEAR_REPORT.md`). That is
  fine for 2025-26.
- **Sources:** newyorkfed.org/medialibrary/media/research/staff_reports/sr512.pdf (sr); skidmore.edu Kurov-Wolfe-Gilbert (sr)

**41. ADR used / remaining.**
- **Definition:** % of the average daily range already used. Stand aside at 85-100%.
- **We compute:**
  - `adr_room`: low so far + ADR - entry >= 0.5 ADR (half an ADR still available upward).
  - `adr_exhausted`: today's range so far is at least 100% of ADR.
- **Variants:** 5-day vs 20-day ADR, and the cutoff. No backtest supports any cutoff.
- **Sources:** luxalgo.com/library/indicator/QHC110xU-5-day-adr-ict-intraday-tracker/ (sr); ar.tradingview.com/script/rH2pZylf-Daily-Range-Exhaustion-ADR-Probability-Map/ (sr)

**42. ATR / volatility expansion; NR4.**
- **Definition:** Crabel's contraction-expansion alternation. NR4/NR7 is the narrowest bar of the last 4/7; Raschke
  adds WR7.
- **We compute:**
  - `atr_expanding`: the mean 5m true range of the last 6 bars is at least 1.3x the 10-day average true range of
    the same 5-minute slots.
  - `nr4_prev`: the prior session was the narrowest of the last 4.
- **Claimed:** Breakouts after contraction follow through better. Direction-free.
- **Sources:** luxalgo.com/library/concept/nr4-nr7-narrow-range-bars; swopec.hhs.se/umnees/abs/umnees0948.htm (sr)

**43. Gap size.**
- **Definition:** The 09:30 open minus the prior 16:00 close. Small gaps tend to fill; big gaps go.
- **We compute:**
  - `gap_big`: |gap| >= 0.25 ADR.
  - `gap_with`: a gap up of at least 0.1 ADR, for a long.
  - `gap_against`: a gap down of at least 0.1 ADR, for a long.
- **Independent data:** NexusFi ladders put ES fill odds at over 90% for gaps under 2 pts and under 20% for gaps over
  30 pts (method not stated).
- **Sources:** nexusfi.com/a/strategies/gap-trading-futures (sr); nqstats.com/rth_breaks.html

## H. Intermarket

**44. NQ vs ES relative strength.**
- **Definition:** Long the stronger index, short the weaker.
- **We compute** `nq_rs_with`: NQ's % change minus ES's % change since the 09:30 open is above 0 for a long. Before
  09:30 the 18:00 open is used, on aligned bars.
- **Claimed:** NQ leads when mega-cap tech leads. This conflicts with the SMT reading.
- **Sources:** bookmap.com/blog/nq-vs-es-why-they-move-together-until-they-dont (sr); nexusfi.com/a/strategies/relative-strength-analysis-futures-day-trading (sr)

**45. ES confirming the sweep vs SMT.** We compute `es_confirms` and `smt_es` (see item 18).
- **Claimed:** An unconfirmed sweep is a stop raid, so reversal is likely; a confirmed one is a genuine move.
- **Source:** luxalgo.com/library/concept/smart-money-technique-divergence

**46. ES trend and ES VWAP.**
- **We compute** `es_trend_with` (ES up since its 18:00 open) and `es_vwap_with` (ES above its session VWAP).
- **Claimed:** The broad market confirms the trade's side.
- **Sources:** as item 44.

## I. Needs data we do not have (listed, skipped)

| confluence | what educators claim | missing data | source |
|---|---|---|---|
| DXY | moves mostly inverse to NQ/ES; its daily bias is used as confluence | DXY / 6E futures | tradingview.com/chart/DXY/ewHnLfqC-Tracking-DXY-for-NQ-ES-Futures (sr) |
| Bond yields (ZN / 10Y) | yields up means growth stocks down; used as a context filter | ZN futures 5m | in.tradingview.com/script/UJFlWowq-Intermarket-Correlation-Table (sr) |
| NYSE TICK | ±1000 extremes mark exhaustion; persistent one-sided extremes mean a trend day | $TICK | luxalgo.com/library/concept/tick-index (sr) |
| ADD / VOLD internals | ADD hugging zero suggests a non-trend day; one-way ADD/VOLD suggests a trend day | $ADD, $VOLD | cn.tradingview.com/script/pxwtjlkC-Market-Internals-Makit0 (sr) |
| Cumulative delta / footprint / absorption | delta divergence at highs/lows | bid/ask tick data | nexusfi.com/a/concepts/cumulative-delta (sr) |
| VIX term structure | VIX/VIX3M above 1 is a stress regime | VIX3M (only daily VIX/VXN exist in `data/`) | luxalgo.com/library/concept/vix-term-structure/ (sr) |
| Options gamma (GEX) levels | positive dealer gamma dampens moves, negative amplifies them | intraday GEX levels (`data/GEX_1d.csv` is daily and was tested by the engine's own search) | spotgamma.com/gamma-exposure-explained/ (sr) |
| True TPO / volume-at-price profile | exact VAH/VAL/POC, single prints, poor highs/lows | tick or 1-tick volume-at-price (5m bars only approximate it) | ninjatrader.com volume profile blog |

## Notes on items not implemented as separate features

- **Mean threshold** of an OB and **CE** of an FVG are sub-levels of items 4 and 6. Entries at the zone edge vs its
  50% are a model parameter (SB/M22 `entry: edge|ce`), not a filter.
- The **80% rule** needs 30-minute TPO acceptance inside value. It is approximated by `in_prior_value` together with
  `open_in_value` / `open_out_value_with`.
- **Inducement, PO3, SMT and wick traps** were already tested on the old engine as noise (`research/ICT_REPORT.md`).
  They are re-tested here on the new test beds, using the simpler definitions above.
