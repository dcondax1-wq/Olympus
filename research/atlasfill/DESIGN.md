# ATLAS fill forensics + the cheapest entry. Pre-registration (2026-11-26, written BEFORE any variant was run)

PAPER RESEARCH ONLY: no live file, size, arming or routing change; the prototype is Sim101-only behind a switch that is OFF.
Code: research/atlasfill/forensics.py (part 1), research/atlasfill/entries.py (part 2), engine/atlas_exec.py (part 3, the paper
prototype). Results: research/atlasfill/forensics.json, entries.json. Write-up: research/writeups/atlasfill-2026-11-26.md.

## Part 1: forensics (no choices: what the real fills say)
Every real fill in the cloud: data/pc_days/*/trades.jsonl.gz live entry rows (signal price "entry", fill "legs[].fill_px",
ledger time "t"), the PC's own MNQ 1m bars (data/pc_days/*/bars), research/second/atlas_fills_why.json, research/livegap. Per
fill: ticks vs the model and vs the MNQ 1m open, latency (ledger t - bar open; the ledger row is written after the fill comes
back, so it is an upper bound on send + fill), the first 1m bar's run in the trade's direction ("fav1"), the share of fav1 the
fill gave away. Split of the cost: spread (1 tick, already in the model), size impact (1-2 micros against NQ's book: about 0), and the
rest = the price move during the latency (bar-close crowd + our seconds). No tick data exists in the cloud (LE_TickRec has not
been pulled), so the split rests on 1m bars and the fills we have, and says so.

## Part 2: the cheapest entry (8 variants max; 7 counted)
Cost model fixed here: a market order gives away **s x fav1** (s = the mean share in the real ATLAS fills, measured in part 1)
on the 2026 1m bars; before 2026 (5m bars only) s x r x fav5, with r = mean(fav1) / mean(fav5) over the 2026 ATLAS signals.
Exit costs as atlas2: stop / market 2 ticks, target 0; $1.90 a round trip. Reference rows (not variants): flat 12 and flat 14 ticks.
- X0 market today (s).
- X1 fast send: engine/fast_entry ON + the order pre-built at the bar close: latency 4 s -> ~1.5 s, s x sqrt(1.5 / 4)
  (a diffusive move). NOT provable on bars; shown as a scenario, with s x 0.8 (a front-loaded burst) as its bad case.
- X2 marketable limit capped 4 ticks past the open, resting 5 min. If the arrival give-away is <= the cap: filled at it.
  Otherwise it rests at the cap, and fills only if price trades 1 tick back through it (minute 0: its close; later minutes:
  their low / high; 5m bars before 2026). A target reached before the fill = no trade. A stored exit before the fill = no trade.
- X3 cap 8 ticks, 5 min.  X4 cap 8 ticks, 15 min.  X5 cap 12 ticks, 15 min.  X6 X1 + cap 8 ticks, 15 min.
- Not testable here: a stop-limit at a trigger inside the bar. ATLAS's members fire on the 5m CLOSE (EMA / MACD / S/R values of
  the closed bar). An intrabar trigger is a different strategy (it fills before the bar confirms) and needs its own pre-registration.

Scoring = atlas2's: fixed $250 (trades/wk, PF, net, $/mo, max DD) for 2021-25, 2026 H1 and 2026 Jul-Oct, plus walk-forward years
2022-2025. Real engines: funded 25K payout path, Rapid 25K LIT + ATLAS, Builder 50K / 25K LIT + ATLAS lanes.
**Winner gate:**
- fixed net better than X0 in all 3 spans;
- funded 25K $/mo not lower than X0 in H1 and H2;
- Builder 50K 6-month net not lower than X0 in H1 and H2;
- 1.5-4.1 trades/wk.

Among the passers, the highest funded H2 $/mo wins. X1 / X6 can win only as "worth a Sim101 measurement", never as proven.

## Part 3: the paper prototype
The winner's order logic as engine/atlas_exec.py: turns ATLAS's MARKET entry into the chosen order. It is
PAPER_ONLY (non-Sim accounts refused), OFF by default (data/atlas_exec.json {"on": true} or LE_ATLAS_EXEC=1), and has tests
on the NinjaTrader adapter's own order simulator. It logs one row per entry with the zeroerr field names (lane, side, qty,
intended, filled, ticks, order_type, signal_t, send_t, ack_t, fill_t). The lead wires it; the owner gates it.
