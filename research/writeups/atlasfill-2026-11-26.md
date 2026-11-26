# ATLAS fill forensics + the cheapest entry (big-atlasfill, 2026-11-26)

PAPER RESEARCH ONLY: no live file, size, arming or routing change. The pre-registration is `research/atlasfill/DESIGN.md` (commit 9e574345, written before any run).
- Code: `research/atlasfill/forensics.py` and `entries.py` (`all` takes about 3 min).
- Prototype: `engine/atlas_exec.py` (OFF, Sim only). Tests: `tests/test_atlas_exec.py`.
- Lead wiring: `research/handoff/2026-11-26/big-atlasfill/LEAD_WIRES.md`.

## The short answer
| Question | Answer |
|---|---|
| Is "12 ticks" real? | **Yes, and slightly worse: 4 real ATLAS fills cost 9 / 11 / 15 / 21 ticks vs the model (mean 14), all of them in the trade's own direction.** LIT's 1 fill cost 3 ticks |
| Where does it go? | Almost all of it is **the price running in the 3-5 s between the 5m close and the fill**. Spread is 1 tick (already in the model); 1-2 micros have no size impact. Each fill gave away **~36% of the first minute's run** (0.29 / 0.50 / 0.38 / 0.28): the faster the minute, the bigger the slippage (Nov 20: a 20-pt minute cost 21 ticks). This is the bar-close crowd plus our own seconds |
| How do we know it is latency, not spread? | The fills sit inside the first minute's range, at about a third of the way along its run. A spread or size cost would be about 1 tick whatever the minute does. Without tick data (LE_TickRec has not been pulled) the split rests on 1m bars |
| Does that change the ATLAS v2 verdict? | **Partly. A flat 12 ticks overstated the quiet years.** The give-away scales with the minute's run, which is smaller in 2021-25. The same calibrated model gives **6.5 ticks in 2021-25, 11.6 in 2026 H1 and 9.9 in Jul-Oct**. At that cost, **today's ATLAS is break-even in 2021-25 (PF 1.00, +$747; PF 0.97-1.02 across the observed share range 0.28-0.50)**, not -$18.5k |
| Cheapest entry? | **Send faster, don't cap.** Capped marketable limits (4 / 8 / 12 ticks) are worse on every span and every engine. The trades that run past the cap are the winners (adverse selection: 2021-25 PF 0.73-0.92). **Fast send** (poll on NinjaTrader's first tick + ATLAS's entry right after LIT's) is best everywhere in the model: 2021-25 PF 1.04 (+$5.8k), funded 25K +$21 / +$25 a month, Builder 50K +$180 / +$219 over 6 months, and the funded 2021-25 loss rate falls from 4.5% to 1.7%. It is **not provable on bars**: it needs the Sim101 week |
| Gate result | **No winner by the pre-registered gate.** X1 (fast send) passes every money test but fails the 1.5-4.1 trades/wk rule, because ATLAS already trades 4.57/wk in 2021-25 (its trades are the same as today's). Per the design it can only ever be "worth a Sim101 measurement", and that is the recommendation |

## Part 1: the real fills (all in the cloud)
| day | bot | member | side × qty | intended | filled | ticks worse | ledger s after open | 1st-minute run | share given away | result |
|---|---|---|---|---|---|---|---|---|---|---|
| Nov 6 | ATLAS | EMA | sell × 2 | 27,037.75 | 27,035.50 | 9 | 5 | 8.5 pts | 0.29 | STOP -$169 |
| Nov 16 | LIT | | buy × 1 | 27,798.75 | 27,799.50 | 3 | 4 | 12.0 pts | 0.08 | STOP -$129 |
| Nov 17 | ATLAS | EMA | sell × 2 | 27,367.50 | 27,364.75 | 11 | 4 | 6.0 pts | 0.50 | TARGET +$1,792 |
| Nov 18 | ATLAS | MACD | sell × 2 | 27,395.50 | 27,391.75 | 15 | 3 | 10.5 pts | 0.38 | STOP -$113 |
| Nov 20 | ATLAS | EMA | sell × 1 | 26,380.75 | 26,375.50 | 21 | 3 | 20.0 pts | 0.28 | TARGET +$514 |

- **Where the seconds go (engine/live.py, read only).** The poll wakes at the minute + 2 s (engine/fast_entry, OFF today, wakes on the first tick instead). Then the order of work is: LIT, the state save, account C, the Rapid BLITZ, the ES learning refresh, the Brain, the second route, and only then **account B = ATLAS**.
- **What is missing.** Exit fills are not recorded (the ledger books exits at the model's prices). The adapter's send / ack / fill times are not in the PC ledger either. Both are needed before the split can be measured instead of inferred.

## Part 2: entries at the calibrated cost (s = 0.363 of the first minute's run; before 2026, 0.399 × the 5m run)
| var | entry | mean entry ticks 21-25 / H1 / Jul-Oct | 2021-25 /wk · PF · net | 2026 H1 /wk · PF · net | Jul-Oct /wk · PF · net |
|---|---|---|---|---|---|
| X0 | market today (give-away s x first-minute run) | 6.48 / 11.62 / 9.92 | 4.57 · 1.0 · $747 | 4.04 · 2.68 · $22,038 | 3.01 · 2.43 · $6,945 |
| X1 | fast send (fast_entry ON + pre-built order): s x sqrt(1.5/4) | 4.02 / 7.21 / 6.06 | 4.57 · 1.04 · $5,786 | 4.04 · 2.78 · $22,727 | 3.01 · 2.55 · $7,209 |
| X1b | fast send, bad case: s x 0.8 | 5.24 / 9.34 / 7.96 | 4.57 · 1.02 · $3,291 | 4.04 · 2.73 · $22,394 | 3.01 · 2.49 · $7,077 |
| X2 | marketable limit cap 4 ticks, rest 5 min | 2.43 / 3.05 / 3.42 | 3.19 · 0.73 · $-34,427 | 3.46 · 2.1 · $13,204 | 2.62 · 2.15 · $4,932 |
| X3 | marketable limit cap 8 ticks, rest 5 min | 3.55 / 4.85 / 5.79 | 3.77 · 0.77 · $-32,589 | 3.62 · 2.59 · $19,332 | 2.81 · 2.11 · $4,890 |
| X4 | marketable limit cap 8 ticks, rest 15 min | 4.01 / 4.97 / 5.88 | 4.13 · 0.83 · $-26,551 | 3.77 · 2.6 · $20,352 | 2.94 · 2.17 · $5,492 |
| X5 | marketable limit cap 12 ticks, rest 15 min | 4.77 / 6.34 / 7.16 | 4.3 · 0.92 · $-12,808 | 3.81 · 2.58 · $20,307 | 3.01 · 2.13 · $5,393 |
| X6 | fast send + cap 8 ticks, rest 15 min | 3.07 / 4.11 / 4.47 | 4.34 · 0.96 · $-6,080 | 3.81 · 2.63 · $20,687 | 2.94 · 2.22 · $5,603 |
| F12 | reference: flat 12 ticks (atlas2 base) | 12 flat | 4.57 · 0.9 · $-18,516 | 4.04 · 2.57 · $21,573 | 3.01 · 2.35 · $6,708 |
| F14 | reference: flat 14 ticks (the 4 real fills' mean) | 14 flat | 4.57 · 0.87 · $-23,980 | 4.04 · 2.51 · $21,189 | 3.01 · 2.29 · $6,556 |

| var | funded 25K $/mo H1 · H2 · 2021-25 (lost %) | Rapid 25K $/mo H1 · H2 · 2021-25 | Builder 50K pass% · net 6m H1 / H2 / 2021-25 | Builder 25K net 6m H1 / H2 / 2021-25 |
|---|---|---|---|---|
| X0 | $552 · $443 · $34 (4.5%) | $2025 · $837 · $-18 | 86.5% $7,558 / 86.0% $7,917 / 23.7% $-277 | $3,513 / $3,041 / $-160 |
| X1 | $573 · $468 · $38 (1.7%) | $2155 · $888 · $-16 | 86.8% $7,738 / 86.5% $8,136 / 25.0% $-196 | $3,603 / $3,185 / $-152 |
| X1b | $567 · $451 · $36 (4.3%) | $2095 · $875 · $-13 | 86.8% $7,656 / 85.8% $8,024 / 24.8% $-214 | $3,540 / $3,128 / $-163 |
| X2 | $292 · $341 · $7 (2.2%) | $991 · $714 · $-43 | 80.8% $5,465 / 83.2% $6,963 / 18.5% $-538 | $2,524 / $2,742 / $-261 |
| X3 | $440 · $336 · $10 (3.3%) | $1580 · $726 · $-43 | 83.2% $6,556 / 85.2% $7,573 / 18.0% $-524 | $3,090 / $2,925 / $-268 |
| X4 | $463 · $372 · $13 (4.2%) | $1535 · $725 · $-40 | 84.5% $6,868 / 84.3% $7,248 / 19.5% $-489 | $3,173 / $2,796 / $-253 |
| X5 | $461 · $367 · $22 (3.8%) | $1510 · $711 · $-31 | 83.8% $6,845 / 83.7% $7,138 / 21.7% $-360 | $3,183 / $2,721 / $-202 |
| X6 | $471 · $385 · $28 (2.3%) | $1560 · $739 · $-28 | 85.2% $6,994 / 85.2% $7,313 / 23.0% $-311 | $3,219 / $2,859 / $-175 |
| F14 | $537 · $412 · $22 (21.5%) | $1940 · $773 · $-34 | 84.8% $7,362 / 83.7% $7,563 / 20.7% $-519 | $3,332 / $2,927 / $-280 |

- Reference rows F12 / F14 are flat 12 / 14 ticks (atlas2's assumption).
- X1b is the fast-send bad case (the burst is front-loaded): it still beats X0 everywhere.
- A stop-limit "at the trigger" is not testable for ATLAS. Its members fire on the 5m close, so an intrabar trigger is a different strategy and would need its own pre-registration.

## Part 3: the Sim101 prototype (engine/atlas_exec.py)
- **Default OFF.** It is turned on by env `LE_ATLAS_EXEC=1` or `data/atlas_exec.json`.
- **What it does when ON.** It runs account B's poll right after LIT's routing on a 5m close (first 20 s of the bar). It does this **only when account B and every Rapid ATLAS lane are Sim accounts**; a real account keeps today's order.
- **How it is wired.** Two lines in engine/live.py, which the lead wires. A `done()` guard stops the regular call from running twice in the minute.
- **What it logs.** It writes fill rows with the zeroerr names (lane, side, qty, intended, filled, ticks, order_type, signal_t, send_t, ack_t, fill_t).
- **The report.** `--report` back-fills from the PC ledger: today 4 ATLAS fills, mean 14 ticks, 3.75 s signal-to-ack.
- **The Sim101 week.** Turn fast_entry and atlas_exec on, collect at least 10 fills, then re-run forensics + entries. If the measured give-away comes in at 7 ticks or less in 2026-like minutes, fast send becomes the live proposal (owner yes).
- Tests: 11/11.

## Update (same day): every-lane timing audit. The "routes last" lead was mostly wrong
Instrumented replay: `research/atlasfill/lane_offsets.py` → `lane_offsets.json`.
- It runs the real LiveBot, paper, on Nov 17 with ATLAS on account B. There were 768 polls, 0 errors and 2 ATLAS trades.
- Each lane's start is stamped in ms after the poll begins, on 5m-close polls, on this machine.

| lane | median start | p90 |
|---|---|---|
| LIT (50K + the extra accounts' LIT lanes) | 252 ms | 305 ms |
| BLITZ account C / Rapid BLITZ / Brain | 254 ms | 307 ms |
| second route (LIT account) | 257 ms | 311 ms |
| **ATLAS account B + Rapid ATLAS + combo lanes** | **257 ms** | **311 ms** |
| fleet / paper second strategies | 517 ms | 634 ms |

**Reading.** The read-only work between LIT and ATLAS costs about 5 ms here: account C and the Brain are quick when off, and the ES refresh has already run. So moving ATLAS forward (engine/atlas_exec) gains milliseconds, not seconds. That leaves three causes of the 3-5 s:
1. **The fixed +2 s wake after the boundary.** engine/fast_entry, built and OFF, wakes on NinjaTrader's first tick instead and saves up to ~1.8 s. It moves LIT too, and LIT also lost 3 ticks.
2. **ATLAS's own tick, about 0.26 s here.** That includes second.run on the closed bars, and the PC is slower.
3. **The order-file → NinjaTrader → Tradovate round trip and the fill confirmation** before the ledger row is written.

The real ledger agrees: Zlarior, which routes first, was 4 s after its open, and ATLAS was 3-5 s.

**Revised recommendation.**
- The Sim101 week should measure **fast_entry ON**, together with the zeroerr send / ack / fill times. That is the lever.
- atlas_exec stays as the measuring tool: the `--report` line, the fill rows and the Sim-only refusals. Its reorder is harmless but worth only milliseconds.
- **On the other lanes in the real ledger:** the pulled PC days hold 5 live entries (ATLAS 4, Zlarior 50K 1). There are **0 for the 25K #2, the Rapid (LIT + ATLAS) and the keep-alive**, so their send times cannot be measured yet.
- In the replay every account lane starts within ~5 ms of LIT. Nothing else is routed materially late in the poll order.
