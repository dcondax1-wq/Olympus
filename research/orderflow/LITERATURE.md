# Order flow in index futures: what is actually documented (2026-11-26, day-oflearn)

Free public sources only (journal articles and their public working-paper versions). Purpose: decide what order flow can
realistically do for US at our scale, 1 micro (MNQ) on MFFU accounts, decisions on a 5m bar close with 1-5 minutes of
latency, no co-location, NinjaTrader ticks (price / size / bid / ask) and top-10 depth forward only. Effect sizes below are the
papers' own numbers as best recalled from the published versions; treat them as order-of-magnitude, and check the source
before quoting one. Every "can it work for us" line is our judgment, not the paper's.

## The one-paragraph answer
Almost all of the robust, peer-reviewed order-flow predictability lives at horizons of **seconds to a few minutes** and is
**contemporaneous or very short-lived** (order-flow imbalance explains price changes over the SAME 10 s window; queue imbalance
predicts the NEXT tick). At a 5-minute decision clock with 1-5 min latency, that alpha is gone before we can act. What survives
to our horizon is weaker and mostly about **size of the move, not direction** (toxicity / lambda -> volatility and slippage),
plus one structural idea that matches LIT's own thesis and has real (FX) evidence: **order clusters at levels produce either a
cascade (stops) or a reversal (resting orders absorb)** (Osler). So the realistic uses, ranked, are: (1) execution / fill cost,
(2) a context filter at LIT's swept level (absorbed vs cascade), (3) a risk / volatility read. Not: a stand-alone direction edge.

## Feature by feature

| Feature | What is measured | Horizon it predicts | Typical effect (literature) | At our scale (1 micro, 1-5 min latency)? |
|---|---|---|---|---|
| Order-flow imbalance (OFI) | Net change of best-bid queue minus best-ask queue (adds, cancels, trades), Cont-Kukanov-Stoikov | Same 10 s - 5 min window (contemporaneous); lagged OFI only seconds | Linear impact dP = beta x OFI, beta ~ 1 / depth; R^2 ~ 65% on average for 50 US stocks at 10 s (CKS 2014). Lagged / forward R^2 small (Kolm et al. 2023: alpha decays within tens of events / seconds) | **No for direction** (gone before our bar closes). Useful as a live "who is winning right now" read and for entry timing inside the minute. Needs depth (forward only). -> v3 L2, expected ~ chance at 5m |
| Queue imbalance at the touch | (q_bid - q_ask) / (q_bid + q_ask) at the best quotes | Direction of the NEXT mid-price move (ms - s) | Strong, monotone for large-tick assets (Gould-Bonart 2016); weaker for small-tick | **No** at 5m. NQ is a relatively small-tick contract (0.25 on ~20,000), which weakens it further. Execution only. -> v3 L1 |
| Micro-price | Imbalance-adjusted fair price between bid and ask (Stoikov 2018) | Next few ticks | Better short-term forecaster than mid / weighted mid | Execution only (limit vs market choice). |
| Trade-sign autocorrelation | ACF of +1 / -1 aggressor signs | Next trades: decays as a power law (long memory) | ACF ~ tau^-0.5 on LSE stocks (Lillo-Farmer 2004); origin = metaorder splitting (Toth et al. 2015). Prices stay ~ unpredictable because liquidity adapts (Bouchaud et al. 2004) | **No** for P&L: signs are predictable, returns are not (the market is efficient to that). Info only. -> v3 J3 / J4, expected ~ chance |
| VPIN / flow toxicity | Volume-synchronized |buy - sell| / volume over N buckets (Easley-Lopez de Prado-O'Hara 2012) | Claimed: short-term volatility / liquidity crises (Flash Crash) | Contested: Andersen-Bondarenko (2014) find VPIN's warning mostly mechanical (trade classification, volume, volatility already known) and no incremental forecast of volatility. | **Maybe, for size not direction**: a volatility / slippage read (skip or widen on toxic minutes). Our prior regime levers all failed; expect the same unless it beats VIX band + range. -> v3 J1 / J2 |
| Kyle's lambda / price impact | Slope of price change on signed volume (Kyle 1985; Hasbrouck 1991 VAR) | Liquidity state over minutes-hours | Impact is concave in size (square-root law, Toth et al. 2011; Bouchaud-Bonart-Donier-Gould 2018); lambda high = thin book | Our 1 micro has ~zero impact. Lambda matters for **our slippage** (ATLAS fills 10-16 ticks past the open) and as a thin-market flag. -> v3 I1 / I3 |
| Order imbalance -> returns (daily) | Signed volume over a day | Next day | Positive same-day, small next-day continuation then reversal (Chordia-Roll-Subrahmanyam 2002; Chordia-Subrahmanyam 2004, stocks) | Weak; index futures absorb it fast (E-mini leads price discovery, Hasbrouck 2003). Covered by v2 H-group. |
| Footprint / diagonal imbalance, stacked imbalances | Ask volume at p vs bid volume at p-1 inside a bar | Practitioner claim: next bars | **No peer-reviewed effect size found.** Mechanically it is a high-resolution delta, i.e. OFI with trades only | Unproven; tested in v2 (B-group). Prior BAR-proxy versions lost money (TESTED_AND_REJECTED, 2026-11-23). |
| Absorption | Heavy aggressive volume into a price with little price progress | Next minutes at that level | No direct academic test. Closest: negative impact residual (price moved less than flow implied, CKS-style), hidden / iceberg liquidity (below), Osler's resting-order clusters | **Plausible at our horizon** because it is about a LEVEL holding, which is LIT's thesis. -> v2 B10 / B11 / F2, OF1, OF4, OF5; v3 I2, K2-K4 |
| Iceberg / hidden liquidity | Volume traded at a price > displayed size there, or a refill after a fill | Persistence of that level; who is patient | CME Globex icebergs are predictable to a degree from book + trade data (Christensen-Woodmansey 2013, E-mini); icebergs are used by patient, often informed traders (Frey-Sandas 2017, mixed on direction) | Needs depth (forward only) -> v2 G7. Plausible as a confirmation of absorption, weak on its own. |
| Delta divergence | Price new high / low while cumulative delta is not | Practitioner: reversal | No peer-reviewed test in index futures found | Unproven; v2 A5 / A6 / H5, battery OF6. |
| Large-trader prints | Single aggressor fills >= N lots | Practitioner: direction of "smart money" | Block-trade literature (stocks) shows temporary impact that partly reverts. In futures one aggressor order is matched against many resting orders and big players split orders (Toth et al. 2015), so "a big print" is a weak identifier | Weak. v2 C-group, battery OF2. Expect ~ chance. |
| Stop-run dynamics at swept levels | Price crossing a level where stops cluster | Minutes - hours | FX order book data: take-profit orders cluster AT round numbers -> reversals there; stop-loss orders cluster just BEYOND -> once crossed, moves accelerate (cascades) (Osler 2003, 2005). Effects are economically meaningful at intraday horizons in FX | **The best fit for us**: LIT trades the sweep. The order-flow question "did stops run and get absorbed (reversal) or keep cascading?" is measurable on a 5m footprint and matches Osler's two cases. -> v3 K1-K4, OF1 |
| Trade classification | Lee-Ready / tick rule / bulk volume | - | Tick-rule errors matter for VPIN (Andersen-Bondarenko 2014; Easley-Lopez de Prado-O'Hara 2016 on bulk classification) | Our ofsum labels the share of quote-rule vs tick-rule sides; the battery refuses a pass when sides disagree. |

## What this means for us, ranked (realistic $ for a 1-micro account)
1. **Execution, not prediction.** ATLAS's real fills are ~10-16 ticks past the 5m open (`atlas-fills-2026-11-20.md`), ~$5 a micro a
   trade. Queue imbalance / micro-price / OFI are exactly what the literature says predicts the next seconds: an entry that waits
   for the book to lean our way inside the first minute could recover a few ticks. Needs depth recording (forward only) and a
   live test; worth more than any filter below because it applies to every trade. (Not in v3's gates: it is an execution study.)
2. **LIT sweep context (absorbed vs cascade).** Osler + the absorption read. If it works, it is a filter that skips some losers;
   LIT has ~2-4 trades a week, so a +20-point win-rate difference needs ~100 trades per side to show (~1 year). The learner will
   say "too few" for months; that is the honest answer.
3. **Volatility / slippage read** (toxicity, lambda): might help size the stop or skip toxic minutes; must beat the VIX band and
   range we already use. Prior regime levers failed (TESTED_AND_REJECTED 2026-11-22), so low prior.
4. **Everything else** (trade-sign persistence, big prints, delta divergence, footprint stacks as stand-alone signals): the
   literature gives no reason to expect net-of-cost edge at a 5m clock; they are in the mill only so the data can say no.

## Sources (free public versions exist for all)
- Cont, R., Kukanov, A., Stoikov, S. (2014). The price impact of order book events. *Journal of Financial Econometrics* 12(1), 47-88. (arXiv 1011.6402)
- Kolm, P., Turiel, J., Westray, N. (2023). Deep order flow imbalance: extracting alpha at multiple horizons from the limit order book. *Mathematical Finance* 33(4). (SSRN 3900141)
- Gould, M. D., Bonart, J. (2016). Queue imbalance as a one-tick-ahead price predictor in a limit order book. *Market Microstructure and Liquidity* 2(2). (arXiv 1512.03492)
- Stoikov, S. (2018). The micro-price: a high-frequency estimator of future prices. *Quantitative Finance* 18(12). (SSRN 2970694)
- Lillo, F., Farmer, J. D. (2004). The long memory of the efficient market. *Studies in Nonlinear Dynamics & Econometrics* 8(3). (arXiv cond-mat/0311053)
- Bouchaud, J.-P., Gefen, Y., Potters, M., Wyart, M. (2004). Fluctuations and response in financial markets: the subtle nature of 'random' price changes. *Quantitative Finance* 4(2). (arXiv cond-mat/0307332)
- Toth, B., Palit, I., Lillo, F., Farmer, J. D. (2015). Why is equity order flow so persistent? *Journal of Economic Dynamics and Control* 51. (arXiv 1108.1632)
- Toth, B., Lemperiere, Y., Deremble, C., de Lataillade, J., Kockelkoren, J., Bouchaud, J.-P. (2011). Anomalous price impact and the critical nature of liquidity in financial markets. *Physical Review X* 1. (arXiv 1105.1694)
- Bouchaud, J.-P., Bonart, J., Donier, J., Gould, M. (2018). *Trades, Quotes and Prices*. Cambridge University Press.
- Easley, D., Lopez de Prado, M., O'Hara, M. (2012). Flow toxicity and liquidity in a high-frequency world. *Review of Financial Studies* 25(5), 1457-1493. (SSRN 1695596)
- Andersen, T. G., Bondarenko, O. (2014). VPIN and the flash crash. *Journal of Financial Markets* 17, 1-46. (SSRN 1881731)
- Easley, D., Lopez de Prado, M., O'Hara, M. (2016). Discerning information from trade data. *Journal of Financial Economics* 120(2). (SSRN 1989555)
- Kyle, A. S. (1985). Continuous auctions and insider trading. *Econometrica* 53(6), 1315-1335.
- Hasbrouck, J. (1991). Measuring the information content of stock trades. *Journal of Finance* 46(1), 179-207.
- Hasbrouck, J. (2003). Intraday price formation in U.S. equity index markets. *Journal of Finance* 58(6), 2375-2400.
- Chordia, T., Roll, R., Subrahmanyam, A. (2002). Order imbalance, liquidity, and market returns. *Journal of Financial Economics* 65(1).
- Chordia, T., Subrahmanyam, A. (2004). Order imbalance and individual stock returns. *Journal of Financial Economics* 72(3).
- Osler, C. L. (2003). Currency orders and exchange rate dynamics: an explanation for the predictive success of technical analysis. *Journal of Finance* 58(5), 1791-1819. (NY Fed Staff Report 125)
- Osler, C. L. (2005). Stop-loss orders and price cascades in currency markets. *Journal of International Money and Finance* 24(2), 219-241. (NY Fed Staff Report 150)
- Christensen, H. L., Woodmansey, R. (2013). Prediction of hidden liquidity in the limit order book of GLOBEX futures. *Journal of Trading* 8(3).
- Frey, S., Sandas, P. (2017). The impact of iceberg orders in limit order books. *Quarterly Journal of Finance* 7(3). (SSRN 1108485)
- Lee, C. M. C., Ready, M. J. (1991). Inferring trade direction from intraday data. *Journal of Finance* 46(2), 733-746.

Not cited as evidence: vendor / trading-education material on footprints, "absorption", "stacked imbalances" and delta divergence.
It describes the reads (v2 uses them) but publishes no out-of-sample effect sizes.
