export function renderPlaybook(el) {
  const steps = [
    ['01', 'Mark the liquidity', 'Major pools: prior day H/L, prior week H/L, overnight H/L, London (02:00–05:00) and Asia (20:00–00:00) H/L, 1H swing highs/lows, equal highs/lows (two levels within 6 pts). Minor pools: 15m swing highs/lows.'],
    ['02', 'Wait for the sweep', 'From 08:00 ET price trades at least 1 tick through a pool. A swept low arms a long; a swept high arms a short. The sweep extreme follows price if it keeps running, and the setup expires 60 min after the last new extreme. No sweep, no trade.'],
    ['03', 'Entry trigger in the killzones', 'Only 09:30–11:30 and 13:30–15:30 ET. IFVG: the first gap of at least 3 pts in the leg that ran into the sweep; the trigger is the first candle body closing back through it. With no gap in the leg, CISD: a close back through the open of the candles that made the extreme. Fill at the next 5m open.'],
    ['04', 'Confluence score of at least 1', '+1 when the 1H trend agrees (−1 against). +1 for a sweep in discount for longs or premium for shorts (1H range). +1 for a clean path (at most 1 unswept swing to target), −1 for 3 or more. −1 when 15m has already turned the trade\'s way (late).'],
    ['05', 'Stop', 'Beyond the sweep extreme + 2 pts. Minimum 10 pts. Wider than 60 pts: use the far side of the inverted gap if that is 10–60 pts, otherwise skip the trade.'],
    ['06', 'Target the draw on liquidity', 'The nearest untaken MAJOR pool at least 1.5R away, exit order 1 tick in front of it, capped at 5R. No major pool in range: 2R.'],
    ['07', 'Manage the trade', 'Breakeven at +1R. Close if it has not reached +0.5R within 30 min. Once it has been +0.5R, a candle closing back through entry closes it (giveback). Flat by 15:55 ET; close 5 min before high-impact news.'],
    ['08', 'Risk', '$350 per trade in MNQ micros: $350 ÷ (stop pts × $2), max 40; half size when the market is trending (10-day efficiency above 0.45); never more than 25% of the cushion above the trailing max loss. 1 trade a day; done after a winner or at −$600. No entries from 15 min before to 30 min after high-impact US news, after 13:00 on FOMC days, or once the day\'s range is 1.6× the 20-day average.'],
    ['09', 'Cold-streak filter (owner pick, locked)', 'Every signal from steps 1–8 goes into a shadow record, traded or not. A trade is taken only if the last 15 finished signals add up above 0R. Otherwise the bot sits out, keeps tracking every setup on paper, and starts trading again by itself the moment the record turns positive. Lookback chosen on 2021–24 only and confirmed on 2025 and 2026.'],
  ];
  const gloss = [
    ['Liquidity pool', 'A price where resting stop and limit orders cluster, typically just beyond obvious highs and lows.'],
    ['BSL / SSL', 'Buy-side liquidity (stops above highs) and sell-side liquidity (stops below lows).'],
    ['Draw on liquidity (DOL)', 'The pool price is most likely reaching for next. The trade target.'],
    ['Sweep / raid', 'Price runs through a pool, fills the resting orders, then reverses.'],
    ['FVG', 'Fair value gap: a 3-candle imbalance where candle 1 and candle 3 wicks do not overlap.'],
    ['IFVG', 'Inverse FVG: a gap that price closes through. Its role flips (support becomes resistance and vice versa).'],
    ['CISD', 'Change in state of delivery: a close through the open of the candles that drove the last leg.'],
    ['LRL vs HRL', 'Low-resistance liquidity: a clear path with few unswept swings, so price travels fast. High-resistance: many fresh swings in the way, so the move chops.'],
    ['Protected high / low', 'The swing that launched a break of structure. While it holds, the trend holds; if it breaks, the bias flips.'],
    ['AMT', 'Auction Market Theory: markets auction between balance (value) and imbalance. POC is the fairest price; VAH and VAL bound 70% of volume.'],
    ['80% rule', 'Open outside value, then accept back inside for two 30-minute periods: high odds of travel to the other side of value.'],
    ['SMT divergence', 'NQ sweeps a low but ES does not (or vice versa). That correlated-index divergence betrays the real hand.'],
    ['Killzone', 'High-volume windows: London 02:00–05:00, NY AM 09:30–11:30, NY PM 13:30–15:30 ET.'],
    ['EOD trailing MLL', "MFFU's max-loss level trails your best end-of-day balance by $2,000 and locks at $50,100."],
  ];
  el.innerHTML = `<div class="pb">
    <h2>The Model · Liquidity Sweep → IFVG → Draw on Liquidity + Cold-Streak Filter</h2>
    <p class="lead">The strategy the bot trades, locked in by the owner on Oct 17 2026: the original Liquidity Engine (1 trade a day, fixed $350 risk) plus the cold-streak filter. Each rule below is code (<span class="mono">engine/model.py</span>, <span class="mono">engine/equity_filter.py</span>, settings in <span class="mono">live_model.json</span>), written out in <span class="mono">STRATEGY.md</span>, and the bot narrates every decision live.</p>
    <div class="steps">${steps.map(([n, h, p]) => `<div class="step"><div class="n">STEP ${n}</div><h4>${h}</h4><p>${p}</p></div>`).join('')}</div>
    <div class="grid cols-2">
      <div class="card"><div class="card-h"><h3>Cold-streak filter</h3></div>
        <ul class="check">
          <li><b>Rule:</b> trade only while the last 15 finished signals sum above 0R.</li>
          <li><b>While paused:</b> no real trades, but every setup is still logged and scored on paper. You get an alert when it pauses and when it resumes.</li>
          <li><b>Why it works here:</b> this model's losing stretches come in runs (Apr–Jul 2026, Sep–Dec 2025). The filter steps aside after a run of losers and comes back once the setups start paying again.</li>
          <li><b>Cost:</b> it misses the first part of each comeback, so total profit is a little lower, and it can go weeks without a real trade.</li>
          <li><span class="muted">Live page, Position &amp; risk guard: "Cold-streak filter" shows TRADING or SITTING OUT with the current 15-signal total.</span></li>
        </ul></div>
      <div class="card"><div class="card-h"><h3>Pre-trade checklist</h3></div>
        <ul class="check">
          <li>☐ Cold-streak filter says TRADING (last 15 signals above 0R)</li>
          <li>☐ Inside a killzone (09:30–11:30 or 13:30–15:30 ET)</li>
          <li>☐ A marked pool was clearly swept (trade-through, not a touch)</li>
          <li>☐ Body close back through a gap in the sweep leg (or CISD)</li>
          <li>☐ Major pool at least 1.5R away, confluence score at least 1</li>
          <li>☐ Stop 10–60 NQ pts beyond the sweep extreme</li>
          <li>☐ No trade yet today, day P&amp;L above −$600</li>
          <li>☐ High-impact news checked; you are at the screen supervising</li>
        </ul></div>
    </div>
    <div class="grid cols-2">
      <div class="card"><div class="card-h"><h3>Research findings (honest)</h3></div>
        <ul class="check">
          <li>All numbers: TradingView NQ1! futures data, commissions and slippage included, $350 risk.</li>
          <li><b>2026 (Jan 2 – Oct 16):</b> 59 trades, 32% win, avg win +2.76R vs avg loss −0.45R, PF 2.99, +$10,339, max DD −$1,174. Without the filter: 93 trades, 26% win, PF 2.41, +$11,630, max DD −$3,147.</li>
          <li><b>MFFU 50K eval, starting any 2026 day:</b> 83 passed, 0 failed with the filter (45 passed, 38 failed without).</li>
          <li><b>Apr–Dec 2025:</b> +$3,525, PF 1.74, max DD −$1,227 (without: +$1,751, PF 1.18, −$3,362).</li>
          <li><b>Oct 2021 – Dec 2024:</b> +$5,005, PF 1.18 (without: −$1,923, PF 0.96). The edge depends on the market regime; the filter is what keeps the losing years small.</li>
          <li><b>Trade frequency:</b> about 2 a week while trading, but it paused May 1 – Aug 6 2026 (about 14 weeks). Overall 1.4 a week.</li>
          <li>Tested and rejected: ICT 2022, Silver Bullet, Mech/IFVG, continuation and ATM models as taught; 92 confluences; 6 daily-bias methods; grade-based sizing; partials and trailing stops.</li>
          <li>Backtests are not a promise. Paper trade first.</li>
        </ul></div>
      <div class="card"><div class="card-h"><h3>MFFU Builder 50K constraints baked in</h3></div>
        <ul class="check">
          <li>$3,000 target · $2,000 EOD trailing MLL (locks at $50,100) · $1,000 soft daily loss</li>
          <li>Max 4 minis / 40 micros: the sizer caps at 40 micros. The worst 2026 drawdown with the filter ($1,174) stayed inside the $2,000 MLL</li>
          <li>No eval consistency rule; funded payouts require best day ≤ 50% of cycle profit</li>
          <li>Flat before session close: the bot flattens at 15:55 ET</li>
          <li>Automation: MFFU permits automated strategies with <b>active oversight</b>; no HFT, no sim-fill exploitation. Confirm the current policy with MFFU.</li>
        </ul></div>
    </div>
    <h2 style="margin-top:20px">Glossary</h2>
    <div class="gloss">${gloss.map(([k, v]) => `<div><b>${k}</b>${v}</div>`).join('')}</div>
    <p class="muted small" style="margin-top:16px">Not financial advice. Backtests are hypothetical and do not include every real-world cost or fill problem. Futures trading carries substantial risk of loss.</p>
  </div>`;
}
