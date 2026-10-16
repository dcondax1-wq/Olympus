# Liquidity Engine · Morning report · Friday 2026-10-16, 05:00 ET

Launch target: 05:15 ET. Status: **ready for the demo checklist; live arming is yours to do.**
Paper bot has run all night on real (delayed) data: ~7 hours, 0 errors, state persisted every poll.

## 1. What was built tonight

**Dashboard**
- New look: Space Grotesk (text) / Oxanium (numerals, labels) / Unbounded (wordmark, titles). New logo: hexagonal aperture, glowing liquidity sweep, candle wick piercing the level; phone icons regenerated from it. Glass panels, grid backdrop, corner-bracket card headers, glowing nav, gradient KPI edges; all 10 skins retuned; phone layout kept (bottom tabs, safe areas).
- **Ctrl+K command palette** (or the ⌘ button): jump to any page, run actions, "explain <term>" glossary.
- **Command Center**: what-if sliders (risk, trades/day → days-to-pass, worst day, Monte Carlo odds), edge-decay monitor (rolling expectancy vs full sample, HEALTHY / WATCH / DEGRADED), three MFFU gauges (daily stop, MLL cushion, consistency).
- **Briefing**: 🔊 Listen reads the game plan aloud.
- **Weekly Review** page: per-week stats, exit/grade mix, auto takeaways, monthly P&L heatmap, copy button.
- Exit-signal warnings on the chart (⚠ / ✕) and a "Warning signs" column in Daily Reports.
- Live page: feed-health rows (source, data age, revised bars, DESYNC, entries blocked).
- Backtest presets: **LIVE · Day 1 (conservative)** ($250 risk, 2 trades/day, $500 daily stop, skip D grades) and **LIVE · Steady** ($350).
- Playbook step 10: the pre-committed kill rule (below).

**Live trading layer (Tradovate = the platform behind MFFU)**
- `engine/tradovate.py`: token cache + back-off (Tradovate allows 5 logins/hour), account and front-month lookup, bracket entry via `placeOSO` with `isAutomated: true`, stop modify (breakeven), cancel, liquidate, kill; size caps refuse >40 micros / >4 minis. Offline self-test of the whole order lifecycle: **PASS**.
- Real-time bars from the Tradovate market-data socket (`TradovateData`); Yahoo stays paper-only (measured ~10 min delayed).
- `engine/golive.py` checklist: credentials, auth, account + balance, contracts + expiry, feed freshness, clock drift, risk vs MFFU 50K, news blackout, live gate, presence acknowledgement, optional demo round-trip (far limit order placed and cancelled).
- Live page: adapter and bar-source selectors, checklist with Re-run, arm flow (type `I ACCEPT LIVE RISK`), hold-to-confirm kill switch.
- Hard gates: live URL only with `TRADOVATE_ENV=live` AND armed AND the phrase; entries refused after 15:55 ET and anything open flattened then.

**Live-loop QA**: `python -X utf8 -m tests.test_live_dryrun` → **44/44 pass**. Three real sessions replayed bar by bar reproduce the backtest's trades exactly; stale feed, bad bars, duplicates, clock jumps, failing alerts, restarts, kill switch, daily limits, news blackout all hold. New: state persistence (`data/live_state.json`), clock-based safety flatten, stale-feed entry block, DESYNC detection, `data_source` yahoo|tradovate with fallback. Ranked risks in `tests/README_LIVE_QA.md`.

## 2. Research (research/NIGHT_REPORT.md + full-2024 re-run)

| Period (flat $350 risk) | Trades | /week | Avg R | Net | PF | Max DD |
|---|---|---|---|---|---|---|
| NQ futures Aug–Oct 2026 (tuning) | 29 | 2.8 | +1.22R | **+$12,642** | 9.87 | −$372 |
| Nasdaq CFD Q4 2023 (unseen) | 33 | 6.6 | −0.29R | −$2,438 | 0.19 | −$2,438 |
| **Nasdaq CFD full year 2024 (unseen, landed 23:35)** | 175 | 3.7 | +0.14R | **+$5,259** | 1.52 | −$1,880 |
| Nasdaq CFD Q4 2025 (unseen) | 26 | 2.9 | −0.21R | −$1,100 | 0.37 | −$1,228 |
| **Four-period total** | | | | **≈ +$14,400** | | |

- **Giveback exit** (was +0.5R, closes back below entry → leave) holds walk-forward and on the full 2024 year (+$1,337 there; without it 2024 is +$3,922, PF 1.34). Keep 0.5R; never lower.
- **No entry filter and no sizing change** passes the four-period rule (better total AND no loss on NQ 2026 AND ≥2.5 trades/week). `lock_boost` and cushion sizing breach a $1,000 worst day. Defaults unchanged.
- "BE off" would raise the total to ≈ +$16.4k but loses more in both losing periods: a candidate to study with live data, not a launch-day change.
- Discovery on 334 candidates in 2024: VWAP value-side is stable-positive (already in the grade); London-range raids stable-negative (penalising them did not help taken trades).
- **First-week odds** of a $1,000+ hole in the first 10 trades: **4%** if the market behaves like NQ 2026, **21%** under the full four-period record at $350 (9% at $250). Median trade is a small loss; profit comes from a few 3–5R runners.

**Pre-committed kill rule (Playbook step 10):** $300 risk for the first 10 trades, then $350. Stop and re-validate if down more than $1,000 from peak after 10 trades, or win rate under 25% over 15 trades.

## 3. Launch runbook (your steps, in order)

0. Confirm the MFFU account runs on **Tradovate** (not Rithmic/NinjaTrader). If not, stop here and tell me.
1. **API key**: Tradovate → Settings → API Access → generate; note the **CID** and **secret**.
2. **Credentials in the environment only.** Create `.env.local.ps1` next to `server.py`:
   ```powershell
   $env:TRADOVATE_USER   = "your_tradovate_login"
   $env:TRADOVATE_PASS   = "your_tradovate_password"
   $env:TRADOVATE_CID    = "12345"
   $env:TRADOVATE_SECRET = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
   $env:TRADOVATE_ENV    = "demo"
   ```
   Then in PowerShell from the `nqbot` folder: `. .\.env.local.ps1; python server.py` (this replaces the dev server the app started).
3. **Live page → checklist on DEMO.** Every row green except "present" until you tick it. Press **Round-trip test (demo)**; Tradovate's order log must show the limit order placed and cancelled.
4. **Shadow run on demo**: Execution = Tradovate DEMO, Bar source = Tradovate market data, tick present, Start. Let it complete one full signal (entry, bracket, exit). On the first live bar, check the bar time matches the clock (the adapter assumes close-stamped bars; if it is off by 5 minutes, tell me and I flip one constant).
5. **Switch to live**: stop the server, set `$env:TRADOVATE_ENV = "live"`, restart, re-run the checklist, type `I ACCEPT LIVE RISK`, press ARM LIVE (pill turns red).
6. Load the **LIVE · Day 1** preset in the Backtest form (that is what the live bot trades with), select Tradovate LIVE, Start. Stay at the screen; the kill switch is the red hold button.

## 4. Risks, stated plainly
- The strategy **lost in 2 of 4 historical periods**; the 2024 year is encouraging but the loss regimes are real.
- The Tradovate adapter has **never touched a real endpoint**: response field names come from the docs. The demo round-trip and the demo shadow signal are the real test; do not skip them.
- Bar-timestamp convention (close- vs open-stamped) must be confirmed on the first live bar.
- No broker read-back yet: rejections or manual trades on the account are invisible to the bot. Keep a hard stop at the broker too.
- MFFU allows automation only with you **present and monitoring**; unattended runs risk the account and payouts.
- Yahoo data is paper-only (10-minute delay, bar revisions).

## 5. Files
`research/NIGHT_REPORT.md`, `research/NIGHT_LOG.md`, `research/study_be_full2024.txt`, `research/exitsig_full2024.txt`, `research/discovery_full2024.txt`, `tests/README_LIVE_QA.md`, README section "Going live (Tradovate / MFFU)". Phone snapshot: https://claude.ai/artifact/6qKctxuaB6eTejKwG6vL5f (updated with the 2024 row).
