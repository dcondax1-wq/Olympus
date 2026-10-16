export function renderPlaybook(el) {
  const steps = [
    ['01', 'Map the liquidity', 'Before the open, mark every pool resting orders sit behind: prior day H/L, prior week H/L, Asia, London and overnight H/L, 1H swing points, 15m ITH/ITL. Equal highs/lows (EQH/EQL) are the juiciest; stops cluster there.'],
    ['02', 'Read the auction (AMT)', "Build the prior RTH volume profile: POC, value-area high and low. Note where the 9:30 open sits vs value. Inside = balance (rotate edge to edge); outside = imbalance (watch for acceptance or an 80%-rule return)."],
    ['03', 'Frame structure', '1H and 15m swing structure: BOS/CHoCH and the protected low (bullish) or protected high (bearish), the swing that must hold for the trend to stay intact.'],
    ['04', 'Wait for the sweep', 'Price must trade through a pool. Buy-side taken → look for shorts; sell-side taken → look for longs. No sweep, no trade. Sweeps from 08:00 ET can arm a setup for the killzones.'],
    ['05', 'Find the manipulation leg', 'The leg runs from the last swing into the sweep extreme. That leg holds the fair value gaps that delivered price into the liquidity grab.'],
    ['06', 'IFVG confirmation', 'Enter when a candle body closes through an FVG from that leg; the gap is "inverted" and order flow has flipped. If the leg has no FVG, a CISD close through the down-close sequence open stands in.'],
    ['07', 'Target MAJOR liquidity', 'Target the nearest MAJOR untaken pool that pays ≥1.5R (prior day/week H-L, Asia/London/overnight H-L, 1H swings, equal highs/lows), capped at 5R. Minor 15m swings in between get run through. Draw on liquidity beat fixed-R targets in every test.'],
    ['10', 'Size by conviction', 'Every valid setup is taken (≈3 per week), but size tilts with the confluences that proved sign-stable: ×1.33 when entering on the discount/premium side of session VWAP, ×0.67 for a volume-climax raid or a first-hour (09:30–10:30) entry. Same trades, higher PF, lower drawdown.'],
    ['08', 'Manage like a prop trader', 'Stop 1× buffer beyond the sweep extreme. No partials, no trailing (both cut the runners). Breakeven at +1R; exit if not +0.5R within 30 min; leave at the close if the trade was +0.5R and closes back below entry (giveback: improved every test period). Nine other in-trade warning signs are logged with their counterfactual and acted on only once proven. Size ~15–20% of the $2,000 MLL per loss, max 2 trades/day, stop after a winner, flat 15:55 ET.'],
    ['10', 'Live: pre-committed kill rule', 'Overnight research (research/NIGHT_REPORT.md): the money comes from a few 3–5R runners and the median trade is a small loss, so a losing regime looks like a normal week at first. Live on the eval: $300 risk for the first 10 trades, then $350. Stop and re-validate if the account is down more than $1,000 from its peak after 10 trades, or the win rate is under 25% over 15 trades: that is the CFD-period signature, not noise. Odds of a $1,000+ hole in the first 10 trades: 4% if the market behaves like NQ 2026, 21% under the full four-period record.'],
    ['09', 'Read every timeframe', '1D / 4H / 1H / 15m FVG respect-disrespect sets order flow per timeframe; the 1H swing range sets premium/discount; 1D/4H/1H gaps are HTF key levels. The bot scores location (discount for longs, premium for shorts) and penalises entries where 15m structure has already turned (late).'],
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
    <h2>The Model · Liquidity Sweep → IFVG → Draw on Liquidity</h2>
    <p class="lead">A fully mechanical take on the Blake-style "mech model" (HTF bias → key level → manipulation-leg IFVG → entry), with AMT and ICT liquidity concepts as scored confluence. Each rule below is code in <span class="mono">engine/model.py</span>, and the bot narrates every decision live.</p>
    <div class="steps">${steps.map(([n, h, p]) => `<div class="step"><div class="n">STEP ${n}</div><h4>${h}</h4><p>${p}</p></div>`).join('')}</div>
    <div class="grid cols-2">
      <div class="card"><div class="card-h"><h3>Confluence score (lean, evidence-based)</h3></div>
        <ul class="check">
          <li><b>+1 HTF trend:</b> 1H structure agrees with the trade (−1 if counter-trend). Edge held in both halves.</li>
          <li><b>+1 Premium/discount:</b> long sweeps in the lower half of the 1H dealing range, shorts in the upper half. Edge held in both halves, NQ and ES.</li>
          <li><b>±1 Path:</b> +1 low-resistance (≤1 unswept swing to target), −1 high-resistance (≥3).</li>
          <li><b>−1 Late entry:</b> 15m structure has already flipped your way, so the move is underway.</li>
          <li><span class="muted">Cut (no edge on the data): protected H/L, SMT, pool quality and AMT location points. Still shown as tags and tracked in the Confluence Lab.</span></li>
          <li><span class="muted">Shown, not required: 1D/4H/1H/15m FVG order-flow alignment. Hard alignment gates removed the best reversals.</span></li>
        </ul><div class="note">Minimum score 1. Every candidate is logged as a shadow trade so the Confluence Lab can re-check these edges as data grows.</div></div>
      <div class="card"><div class="card-h"><h3>Pre-trade checklist</h3></div>
        <ul class="check">
          <li>☐ Inside a killzone (09:30–11:30 or 13:30–15:30 ET)</li>
          <li>☐ A marked pool was clearly swept (trade-through, not a touch)</li>
          <li>☐ Body close through an FVG inside the manipulation leg</li>
          <li>☐ Opposing liquidity ≥ 1.5R away, path mostly clear</li>
          <li>☐ Stop beyond the sweep extreme fits the risk budget (10–60 NQ pts)</li>
          <li>☐ Fewer than 2 trades today, no winner banked yet, day loss &gt; −$600</li>
          <li>☐ High-impact news checked; you are at the screen supervising</li>
        </ul></div>
    </div>
    <div class="grid cols-2">
      <div class="card"><div class="card-h"><h3>Research findings (honest)</h3></div>
        <ul class="check">
          <li>NQ 5m, Aug 6 → Oct 15 2026: 33 trades (3.3/week), 48.5% win, +1.06R/trade, PF 5.27, +$12.7k on $350 base risk, max DD −$1.07k, worst day −$468.</li>
          <li>MFFU eval: 36/36 rolling starts passed, avg 11 days. Monte Carlo 99% pass. Eval Sprint ($450): avg 9.3 days, 97% pass, 0 rolling failures.</li>
          <li>All 384 grid configs profitable out-of-sample on NQ; every walk-forward fold positive; robust to 3-tick slippage. Without the 5 best trades PF is still 1.9.</li>
          <li>Exit study: major-pool DOL targets beat fixed R; partials and trailing stops lose money (they cut the 4R+ runners); BE at 1R and a 30-min time stop help.</li>
          <li>Cut for having no edge: AMT-location points, protected H/L, SMT, pool quality, London session, hard MTF alignment gates, partials, trails.</li>
          <li><b>ES did not work</b> (0/384 configs profitable OOS), and the same model on 1m bars lost money. Trade NQ on 5m.</li>
          <li>Only ~50 sessions of real futures intraday data exist for free. Treat the results as promising, not proven. Paper trade first.</li>
        </ul></div>
      <div class="card"><div class="card-h"><h3>MFFU Builder 50K constraints baked in</h3></div>
        <ul class="check">
          <li>$3,000 target · $2,000 EOD trailing MLL (locks at $50,100) · $1,000 soft daily loss</li>
          <li>Max 4 minis / 40 micros: the sizer caps at 40 micros</li>
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
