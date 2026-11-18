# ZEUS on other markets: gold (MGC), crude (MCL), Russell (M2K)

**Why:** Zlarior (LIT) on markets that don't move with NQ = more winning days on the account, which the MFFU
consistency / best-day rules like. Paper research only: nothing changes live until the owner says yes.
ES was already tested and rejected (`docs/TESTED_AND_REJECTED.md`, "E3 same edge, more markets").

## Owner: export the data (once per market, about 10 min)

Do it on the PC, in NinjaTrader 8, any time the market is open or closed. Gold first, then crude, then Russell.

1. **Check the merge policy (already right for the bot):** Control Center > **Tools > Options > Market data** >
   **Merge policy = "Merge back adjusted"**. If it says something else, stop and tell Claude (the bot needs this one).
2. **Get the history onto the PC:** Control Center > **New > Chart**, instrument **`MGC ##-##`** (type `MGC`, pick the
   one ending `##-##`), Type **Minute**, Value **1**, Load data based on **Days**, Days to load **2000**, OK.
   Wait until the chart stops loading, then close it (NinjaTrader keeps the bars).
3. **Export:** Control Center > **Tools > Historical Data** > the **Export** part:
   - Instrument: **`MGC ##-##`**
   - Data type: **Last** - Interval: **Minute** (1)
   - Start date: **01/01/2021** - End date: **today**
   - Click **Export** and save the file in the bot folder's **`data`** folder (the same folder as `NQ_1m.csv`). Keep the
     name NinjaTrader offers (it starts with `MGC`, e.g. `MGC ##-##.Last.txt`).
4. Same for **`MCL ##-##`** and **`M2K ##-##`**.
5. In the bot folder (once the PC has updated to this code), one line per market:

```
python -X utf8 tools/other_markets.py MGC
```

   It imports the file, runs the whole proof (a few minutes) and ends with a short table and **VERDICT**. Send Claude the
   last lines (or the file `research\other_markets\MGC.json`).

If NinjaTrader will not take `##-##` in step 3: export each contract instead (e.g. `MGC 02-26`, `MGC 04-26`, ...) into
`data\nt_export\MGC\`; the tool stitches them and works out the rolls itself. If NinjaTrader gives less than 2021: fine,
2026 is the must-have (both halves); 2021-25 is then shown as "not in the export".

## What the one command does

`tools/other_markets.py <SYM>`: imports the export if it is newer than `data/<SYM>_1m.csv`, then the full proof, then one
short table and a verdict. Results: `research/other_markets/<SYM>.json`. `--n 300` = quicker, `--comm 2.10` = MFFU's real
commission for that micro (see "Costs"). `python -X utf8 tools/other_markets.py selftest` runs the whole chain on a fake
export (works today, no real data needed). Test: `python -X utf8 -m tests.test_other_markets` (nq area, ~1 min).

| Step | What |
|---|---|
| Import (`tools/nt_import.py`) | NinjaTrader `yyyyMMdd HHmmss;open;high;low;close;volume` (bar CLOSE stamp) -> open-stamped UTC `data/<SYM>_1m/5m/15m/1h.csv` (reuses `data/import_futures.py`). Time zone found from the data (every market here halts 17:00-18:00 ET; the zone that puts no bar in that hour wins: PC Eastern, exchange Chicago, UTC all work; `--tz` forces one). Continuous `##-##` = already back-adjusted by NinjaTrader, `data/<SYM>_rolls.json` says so with no gaps. Per-contract files = volume roll (the session after the next contract trades more), gap at the last common minute, additive back-adjustment to the newest contract, written in the `NQ_rolls.json` shape. Also `data/<SYM>_rv_1d.csv` (20-day realized vol, the gold / crude target band) and `data/<SYM>_import.json`. A run rebuilds the market's files from the export. |
| Strategy | `engine/lit.py` exactly as live (`live_model.json` "lit": 1m CISD entry, VIX-band target banked at 8R, 15-min check, Monday rule, weekly stop), with the market's tick, $ per point, commission and 1-tick slippage (`engine/lit_markets.py`). |
| Money | LIT rule size ($800 risk, max 40 micros, weekly stop) in $: trades/week, win %, PF, net $, $/month, max DD, costs as % of R; 2026 Jan-Jun, Jul-Dec, 2021-25 when present. |
| Eval | Its own Builder 50K at the live eval sizing (two_week room_f 0.4 to session 80): 2-week pass / fail, median days (`tools/uprisk.eval_mc`). |
| Together | Daily $ correlation with LIT-NQ (the live ledger) + LIT-NQ and LIT-<SYM> on ONE Builder 50K, same Monte Carlo paths: eval speed, funded $/month, first payout, sessions held by the 50% best-day rule, account lost in 6 months, winning days a month (`tools/uprisk.funded_mc`, fleet preset UP50). |
| Verdict | Pass = both 2026 halves positive with PF > 1 at 2-4 trades/week, 2021-25 positive if present, and together better than NQ alone on eval AND funded $ in both halves. A pass goes to the lead / owner; nothing is switched on. |

## Decisions (pre-registered: nothing is tuned on the results)

- **Contracts:** MGC tick 0.10 = $1, $10/pt (COMEX); MCL tick 0.01 = $1, $100/pt (NYMEX); M2K tick 0.10 = $0.50, $5/pt (CME).
- **Costs:** MFFU's MNQ is $1.90 a micro round trip. M2K = $1.90 (same CME equity-micro fees). **MGC / MCL = $2.40 is an
  ESTIMATE** (higher COMEX / NYMEX fees): check MFFU's commission table and re-run with `--comm`. Slippage 1 tick on
  market entries and stop / breakeven / end-of-day exits, like NQ. The ES failure was costs (7-13% of R); the report
  prints this market's cost share so it is visible at once.
- **Point settings re-scaled by volatility, not price:** k = the market's median 5m ATR / NQ's over the same 2026
  Jan-Jun days (crude at $70 vs NQ at 25,000 makes a price ratio meaningless). Min / max stop 8 / 80 NQ pts x k on the
  tick grid, build-up tolerance 1.5 x k. Stop **1 tick** beyond the sweep extreme (the rule). Breakeven = 1 tick + the
  commission in whole ticks (NQ's live 1.25 comes out of the same formula; MGC 0.40, MCL 0.04, M2K 0.50). Sizing in
  NQ-equivalent points ($ per point / $2) so the $800 rule, the eval and the funded sizing stay the live ones and every
  trade's $ is exact.
- **Session levels (Asia / London / NY boxes, PDH/PDL, PWH/PWL, gaps):** kept as NQ's for all three. They are
  clock-time liquidity pools of the three regions, and gold and crude trade all three on CME Globex 18:00-17:00 ET with
  the same 17:00 halt (gold is London-centred, so the London box matters most there; crude is NY-centred). Gold and
  crude have their own pit / day sessions (COMEX gold 08:20-13:30 ET, NYMEX crude 09:00-14:30 ET) and liquidity thins
  after the settle, so ONE pre-registered "pit" variant stops new entries 30 min before the settle and goes flat 5 min
  before it (gold entries to 13:00 / flat 13:25, crude 14:00 / 14:25). No new "pit open" box is added (that would be a
  search); possible later as a lit EXTRA_BOXES entry with its own proof.
- **Target band:** NQ and M2K use the VIX move (equity index, as live). Gold and crude use their own 20-day realized vol
  from the futures bars (no GVZ / OVX file, no web data); the VIX band is shown as a neighbour.
- **Variants are neighbours, not a search:** main, stops x0.8, stops x1.25 (+ pit and VIX band for gold / crude). The
  one used for the eval / together test is picked on 2026 Jan-Jun only (trades/week 2-4 first) and checked on Jul-Oct.
- **Not modelled yet:** crude's Wednesday 10:30 ET inventory report and gold's 08:30 data releases (the backtest has no
  news filter, like NQ's research runs); the 1m export means 1m execution in every year (NQ before 2026 was 5m).
- **Safety:** `engine/lit_markets.use()` swaps lit.py's market numbers only inside one research block, always restores
  NQ's (also on an error) and refuses to run in a process with the live loop loaded. NQ output is byte-identical
  (checked: all NQ setups + live trades hash, `tests.test_lit_live --quick`, and the test re-runs NQ after each market).
