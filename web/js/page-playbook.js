export function renderPlaybook(el) {
  const steps = [
    ['01', 'Mark the liquidity', 'Major pools: prior day H/L, prior week H/L, overnight H/L, London (02:00–05:00) and Asia (20:00–00:00) H/L, 1H swing highs/lows, equal highs/lows (two levels within 6 pts). Minor pools: 15m swing highs/lows.'],
    ['02', 'Wait for the sweep', 'From 08:00 ET price trades at least 1 tick through a pool. A swept low arms a long; a swept high arms a short. The sweep extreme follows price if it keeps running, and the setup expires 60 min after the last new extreme. No sweep, no trade.'],
    ['03', 'Entry trigger in the killzones', 'Only 09:30–11:30 and 13:30–15:30 ET. IFVG: the first gap of at least 3 pts in the leg that ran into the sweep; the trigger is the first candle body closing back through it. With no gap in the leg, CISD: a close back through the open of the candles that made the extreme. Fill at the next 5m open.'],
    ['04', 'Confluence score of at least 1', '+1 when the 1H trend agrees (−1 against). +1 for a sweep in discount for longs or premium for shorts (1H range). +1 for a clean path (at most 1 unswept swing to target), −1 for 3 or more. −1 when 15m has already turned the trade\'s way (late).'],
    ['05', 'Stop', 'Beyond the sweep extreme + 2 pts. Minimum 10 pts. Wider than 60 pts: use the far side of the inverted gap if that is 10–60 pts, otherwise skip the trade.'],
    ['06', 'Target the draw on liquidity', 'The nearest untaken MAJOR pool at least 1.5R away, exit order 1 tick in front of it, capped at 5R. No major pool in range: 2R.'],
    ['07', 'Manage the trade', 'Breakeven at +1R. Close if it has not reached +0.5R within 30 min. Once it has been +0.5R, a candle closing back through entry closes it (giveback). Flat by 15:55 ET; close 5 min before high-impact news.'],
    ['08', 'Risk', '$650 per trade in MNQ micros: $650 ÷ (stop pts × $2), max 40. Typical stop 44 pts × 7 micros ≈ $616. Half size when the market is trending (10-day efficiency above 0.45). 1 trade a day; done after a winner. No entries from 15 min before to 30 min after high-impact US news, after 13:00 on FOMC days, or once the day\'s range is 1.6× the 20-day average.'],
    ['09', 'Cold-streak filter: half size (owner pick, locked)', 'Every signal from steps 1–8 goes into a shadow record. If the last 15 finished signals add up to 0R or less, the bot still takes every setup but at half size, and goes back to full size by itself the moment the record turns positive. Every setup is traded, so it keeps 2+ a week.'],
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
    <p class="lead">The strategy the bot trades, locked in by the owner on Oct 17 2026: the Liquidity Engine in eval mode (1 trade a day, $650 risk, every setup taken, half size in cold streaks). Each rule below is code (<span class="mono">engine/model.py</span>, <span class="mono">engine/equity_filter.py</span>, settings in <span class="mono">live_model.json</span>), written out in <span class="mono">STRATEGY.md</span>, and the bot narrates every decision live.</p>
    <div class="steps">${steps.map(([n, h, p]) => `<div class="step"><div class="n">STEP ${n}</div><h4>${h}</h4><p>${p}</p></div>`).join('')}</div>
    <div class="grid cols-2">
      <div class="card"><div class="card-h"><h3>Cold-streak filter</h3></div>
        <ul class="check">
          <li><b>Rule:</b> full size while the last 15 finished signals sum above 0R; half size when they don't.</li>
          <li><b>In a cold streak:</b> every setup is still taken, at half size. You get an alert when it drops to half size and when it goes back to full.</li>
          <li><b>Why it works here:</b> this model's losing stretches come in runs (Apr–Jul 2026, Sep–Dec 2025). Half size after a run of losers keeps the damage smaller until the setups start paying again.</li>
          <li><b>Cost:</b> the first winners of each comeback are at half size.</li>
          <li><span class="muted">Live page, Position &amp; risk guard: "Cold-streak filter" shows FULL SIZE or HALF SIZE with the current 15-signal total.</span></li>
        </ul></div>
      <div class="card"><div class="card-h"><h3>Pre-trade checklist</h3></div>
        <ul class="check">
          <li>☐ Size: full, or half if the cold-streak filter says HALF SIZE</li>
          <li>☐ Inside a killzone (09:30–11:30 or 13:30–15:30 ET)</li>
          <li>☐ A marked pool was clearly swept (trade-through, not a touch)</li>
          <li>☐ Body close back through a gap in the sweep leg (or CISD)</li>
          <li>☐ Major pool at least 1.5R away, confluence score at least 1</li>
          <li>☐ Stop 10–60 NQ pts beyond the sweep extreme</li>
          <li>☐ No trade yet today</li>
          <li>☐ High-impact news checked; you are at the screen supervising</li>
        </ul></div>
    </div>
    <div class="grid cols-2">
      <div class="card"><div class="card-h"><h3>Research findings (honest)</h3></div>
        <ul class="check">
          <li>All numbers: TradingView NQ1! futures data, commissions and slippage included, $350 risk.</li>
          <li><b>2026 (Jan 2 – Oct 16):</b> 97 trades (2.4 a week, 2+ in 74% of weeks), 26% win, PF 2.55, +$21,359, max DD −$4,379, worst day −$651.</li>
          <li><b>MFFU 50K eval, new start every 2026 day:</b> 25% passed within 2 weeks (0% failed), 37% within a month (1% failed). Back to back in 2026: 6 passed, 2 failed.</li>
          <li><b>All 5 years:</b> 824 trades, PF 1.30, +$38,194, max DD −$13,389. Eval within 2 weeks: 12% pass / 6% fail; back to back: 20 passed, 31 failed. 2026 was a good year for this model.</li>
          <li>No setting passes for sure in 2 weeks: $3k is about 5R at $650 and the $2k limit is about 3 full losses.</li>
          <li>Tested and rejected: ICT 2022, Silver Bullet, Mech/IFVG, continuation and ATM models as taught; 92 confluences; 6 daily-bias methods; grade-based sizing; partials and trailing stops.</li>
          <li>Backtests are not a promise. Paper trade first.</li>
        </ul></div>
      <div class="card"><div class="card-h"><h3>MFFU Builder 50K constraints baked in</h3></div>
        <ul class="check">
          <li>$3,000 target · $2,000 EOD trailing MLL (locks at $50,100) · $1,000 soft daily loss</li>
          <li>Max 4 minis / 40 micros: the sizer caps at 40 micros. At $650 risk the $2,000 MLL is about 3 full losses</li>
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
