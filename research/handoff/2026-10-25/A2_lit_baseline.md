# A2: LIT baseline reproduction, ledgers, signal ledger, robustness (pre-launch audit 2026-10-25)

Paper only. No engine file, no `live_model*.json`, no stored run was changed. Everything below is produced by one
read-only script, `tools/a2_lit_audit.py`.

Labels used here:
- **BASELINE**: the two configs as they are stored.
- **RESEARCH_VARIANT**: every robustness row.
- **BUG_FIX**: none. No rule defect was shown, so no code fix was made.

## 1. Reproduce

```
python -X utf8 tools/a2_lit_audit.py base     # ~10 s with a warm candidate cache: both configs, both ledgers, the signal ledger
python -X utf8 tools/a2_lit_audit.py robust   # ~10 s: the robustness table
```

Output files: `A2_reproduce.json` (every number in sections 1-2), `COMPLETE_TRADE_LEDGER.csv`, `SIGNAL_LEDGER_LIT.csv`,
`A2_robustness.csv` / `.json`.

### Hashes

**Config hash** = `sha1(json.dumps({"lit": lit, "lit_sizing": lit_sizing}, sort_keys=True))`, the same spelling as
`launch_evidence.md`:

| Config | Source | config_hash |
|---|---|---|
| pre-switch (cisd1m 20, room_f 0.6, no wk_loss_usd) | `git show 4a6f7f3^:live_model.json` | `8731a81ac0541ec0f92c7e6ed6b7de572443c714` (= launch_evidence.md) |
| current (cisd1m 22, room_f 0.55, wk_loss_usd 1200) | `live_model.json` today; `live_model_lit.json` has identical `lit` and `lit_sizing` | `2a346184de690e807b835085b79d2cc122fe5c1d` |

**Data hash** = `5m:17519777-21380e2635:1|1m:13967504-d6ffd3ecfe|VIX:e5c621f32b|VXN:313484bd7e`. The parts:
- `tools/runlib._data_key()`: the NQ_5m.csv size, its sha1[:10] and ENGINE_EPOCH. This key covers the 5m file only.
- NQ_1m.csv: size and sha1[:10].
- VIX_1d.csv and VXN_1d.csv: sha1[:10] of each.
- Data commit `aeb9d10` (2026-10-23).

### Reproduced vs expected

**LIT size rule** (engine `run_x`, $1.40 a micro + 1 tick). Both configs reproduce the stored run **trade for trade**:
631 / 631 trades, matched on day, entry time, P&L to the cent, exit and micros.

| Config | Stored run | 2026 | H1 | H2 | 2021-25 (reference) |
|---|---|---|---|---|---|
| pre-switch | `lit_adopt_t15_be_off` ✔ | 120 tr, PF 4.07, +$43,394, DD -$2,196 | +$33,901, PF 4.98 | +$9,493, PF 2.69 | 511 tr, PF 1.01, +$1,265 |
| current | `lit_live` ✔ | 120 tr, PF 4.19, **+$43,820**, DD -$2,196, 2.91/wk | +$33,901, PF 4.98 | **+$9,919, PF 2.91** ($2,670/mo) | 511 tr, PF 1.01, +$1,265 |
| current at $1.90 | (re-costed) | PF 4.15, +$43,502 | +$33,666 | +$9,836 | PF 0.99, -$664 |

- The 2021-25 line is the same for both configs: those years have no 1m bars, so cisd1m becomes 22 // 5 = 20 // 5 = 4 five-minute bars either way.
- Between the configs, cisd1m 22 changes one H2 day and nothing in H1. On 2026-08-28 the earlier setup now gets its 1m CISD inside the longer window and fills (BE, +$3), where cisd1m 20 took a later setup that stopped out (-$422). That is the whole +$426.

**Eval path, two_week sizing** ($1.90 a micro). This is a **discrepancy**:

| Config | Stored eval run (built) | Stored H1 / H2 | Today's code, no stuck rule | Today's code, stuck rule (room < $200 ends the eval) |
|---|---|---|---|---|
| pre-switch | `lit_adopt_t15_be_off_eval` (before 10-24) | +$34,253 / +$9,059 | +$27,164 / **-$1,940** (= `sizing_cap_lit_eval` ✔ exact) | +$28,482 / +$14,771 (= `sizing_cap_lit_eval_stuck200` ✔ exact) |
| current | `hq_lit_sw_c22_r55_wk12_eval` (2026-10-23 23:24) | +$29,827 / +$9,780 | +$20,156 / **-$1,944** | **+$31,036 PF 4.28 / +$9,331 PF 2.26** (DD -$2,040 / -$3,390) |

- **Why the eval numbers moved.** Commit `15cb560` (2026-10-24 19:28, the sizing cap invariant) changed the sizing: if not even 1 micro fits a cap, the entry is now skipped. The stored current-config eval run is older than that commit, so the published eval-path figures for the live config **do not reproduce** with today's `engine/sizing.py`.
- **Example from the first trade that differs.** On 2026-01-14 the stored run has 11 micros; today's code gives 7.
- **How an eval gets stuck.** Without a stuck rule, a drained eval keeps going until the data ends and trades nothing:
  - H2-E01 of the current config reaches -$1,944 by 2026-09-15.
  - The room is then $56. A 1-micro stop-out costs $89-165, so every later setup is skipped.
  - The writeup `research/writeups/sizing-caps.md` already describes this ("EVAL STUCK" push at room < $200).
- **Fresh-eval rates, current config, today's code** (one eval started on every session; only starts that see the full window count):

| Window | Half | Pass | Fail | Stuck (stuck rule only) |
|---|---|---:|---:|---:|
| 2 weeks | H1 | 57.1 | 0.0 | 5.0 |
| 2 weeks | H2 | **50.7** (stored run: 52.2) | 0.0 | 0.0 |
| 1 month | H1 | 73.4 | 0.0 | 11.9 |
| 1 month | H2 | 50.8 | 0.0 | 0.0 |

- **Back-to-back path with the stuck rule:** H1 8 pass / 0 fail / 1 stuck / 1 open. H2 3 pass / 0 fail / 1 stuck / 1 open.
- **Read "0% fail" with care:** a stuck eval is a dead eval, and it is not counted as a fail. Under the stuck rule, 5% of H1 2-week starts and 11.9% of H1 1-month starts end stuck.
- **Simulator start balance:** it starts each eval at $0. The live eval started at -$100 (`eval_prior_pnl`).

### Other discrepancy notes

- **8-80 pt stop rule: checked on the planned risk, not the fill.**
  - `lit.py:1499-1503` checks the risk measured from the 5m limit price (`min(ref_d, trig_c)`). The trade itself fills at the 1m CISD market entry, so the real risk is different.
  - In 2026, 10 trades had a real risk above 80 pts (80.25 to 84.0). Their P&L: +$990, +$986, -$54, +$0.60, +$0.60, -$103, -$165, +$192, -$164, +$359.
  - 6 armed setups were dropped as `qty_zero`: their real risk was above ~89 pts, so `qty_for` gives 0 micros.
  - Sizing follows the real risk (`lit.py:1059`), so the $ risk stays capped.
- **02:00-15:30 window:** it applies to the bar where the limit is placed (`z["mod"]`, `lit.py:1272`), not to the fill. A fill can come up to the flat time. In 2026, 0 trades filled at or after 15:30.
- **One 2026 trade used 5m bars:** that day did not have full 1m coverage.
- **Prices in the ledger:** entry, exit and stop prices are TradingView NQ1! continuous **back-adjusted** prices, not the prices that traded in the MNQ contract.

## 2. Rule check against the code (`engine/lit.py` unless named)

| Owner rule | Code | Verdict |
|---|---|---|
| 5m structure, 1m entry | setups from 5m bars in `candidates()` l.382-535; the executor uses 1m bars when the day has ≥97% 1m coverage (`use1` l.1524, `bars_1m` l.885-931, `full` l.930), else 5m | OK. In 2026, 119 trades on 1m bars and 1 on 5m |
| Wilder ATR14 | `atr()` l.61-68: RMA `out[i-1] + (tr-out[i-1])/14`, seeded with `tr[0]` (not an SMA of the first 14), one continuous series over the history | OK (Wilder RMA). The seed only matters at the start of the series |
| London at fixed ET times | `SESSIONS` l.39-51: `lon25` 02:00-05:00, `lon34` 03:00-04:00, `lon23` 02:00-03:00 in ET minutes; bar minutes from `America/New_York` (`engine/data.py` l.48-56) | OK, fixed ET. No UK-DST shift, so London open is 1 h off in ET during the Mar / Oct-Nov DST-gap weeks |
| Boxes used only after they close | a box level is `(hi, lo, index of its last bar)` (l.263). A sweep needs `level index < extreme` and the first breach is searched from index+1 (l.422, l.455, `_first_breach` l.346-352). Targets need `ki <= i` (l.500) | OK. A box with fewer than 2 bars is not a level (l.262) |
| Sweep ≥ 0.5 ATR | `depth_atr = (nearest swept level - extreme) / ATR[extreme]` (l.524), gate `< depth` (l.1275, depth 0.5) | OK. "Nearest" = the shallowest swept level. The sweep must also trade strictly beyond the level (l.350, l.455) |
| Inducement | `idm_a` gate `[1.0, 36, 1]` (l.1285-1288): ≥1 fractal low above the swept level, ≤1.0 ATR[sweep bar] away, ≤36 bars before the sweep, still untouched until the final run (leg top → extreme) took it (l.474-483) | OK |
| Displacement direction | body = (c-o)/ATR in direction space (shorts negated, l.416, l.489); `disp = max(body[1:])` (l.525); gate 0.8 (l.1281) | OK. An opposite candle has a negative body and cannot pass (launch_evidence F2) |
| CISD = open of the run | `_cisd_level` l.355-366: the last down-close bar within ee-3..ee, then back to the first bar of that unbroken down-close run (≤30 bars); level = that bar's **open**. 5m trigger = first close strictly above it (l.452) | OK |
| Virtual limit, then 1m CISD | limit = `min(CISD level, trigger close)` (l.1499). On a tap (`lo <= limit`, l.1004-1007), the tap is recorded. Entry = the first 1m close above the 1m CISD level of the low since the tap (l.1014-1029), at the next 1m open + 1 tick | OK |
| Stop 1 tick beyond the extreme | `stop = ext_d - stop_buf` (l.1500), stop_buf 0.25; ext_d = the 5m leg extreme (lowest low of 24 bars, l.437) | OK |
| 8-80 pts | l.1502 on the planned risk from the limit | see the discrepancy note above (real risk up to 84 pts) |
| VIX target from the prior day | VIX close of the last date strictly before the trading date (`bisect_left(...)-1`, l.250-253). Move = VIX/100/√252 × the 18:00 open; target = open18 ± 1 × move (l.1389-1393) | OK |
| 1.5R minimum / 8R cap | nearest target ≥1.5R from the limit (l.1513), capped at 8R (l.1523). Re-checked from the real 1m fill: below 1.5R → no trade (l.1053), capped at 8R from the fill (l.1055) | OK. 2 setups in 2026 were dropped by the after-fill check |
| 1 trade a day | `per_day >= max_per_day` (l.1458) and one position at a time (`busy`, l.1456) | OK |
| Entries 02:00-15:30 | window `[[120, 930]]` on the limit-placement bar (l.1272) | OK as coded (see the note above) |
| Flat 15:55 | `B.mod[k] >= 955` → exit at that bar's **close** − 1 tick (l.1154). The candidate entry bar must be before 15:55 (l.494) | The exit is at 15:56 on 1m bars and at 16:00 on 5m bars, not 15:55:00 |
| BE at +1R, with the ±1.25 sign for shorts | when `hi_d >= entry + 1R`, the stop moves to `entry + 1.25` in direction space (l.1135-1136), i.e. entry - 1.25 for shorts. It takes effect from the next bar, because the stop is checked first (l.1128) | OK (launch_evidence F3) |
| 15-minute cut | at the close of the 1m bar with `round((t_k - t_fill)/60) + 1 == 15`; condition: no BE yet, MFE < 0.5R, close < entry - 0.3R. Exit at the next 1m open − 1 tick (l.1183-1186, l.1103-1104). 1m bars only (l.1086) | OK. Edge: if the 15th-minute bar is missing from the cleaned 1m data, the check never fires |
| Monday rule, incl. both sides taken | `monday_block` l.1296-1307: only on the Monday trading day. Friday high taken only → no longs; Friday low taken only → no shorts; **both or neither → no rule** (l.1305). State read at the trigger bar. A blocked setup leaves the day free (l.1494) | OK |
| Weekly rule modes | **LIT size rule:** `wk_stop [2, 0.5]`, after 2 STOP exits in the ISO week the rest of the week trades at half size (l.1567-1572, `week_stops` l.1363-1381). **two_week:** no weekly multiplier (`two_week.wk false`, `sizing.py` l.706; units undo it, `lit_adopt_combo.units`). Eval weekly loss stop `wk_loss_usd 1200` (`sizing.py` l.173-181: no entry once the eval's ISO-week P&L ≤ -$1,200; ceiling l.256-258). After session 10 the eval switches to safe_eval (`sizing.py` l.428-431) | OK |
| scale_in off | `"scale_in": null` → `si = None` (l.1090), no adds | OK |

**Doji and equal-price edge cases:**
- **Doji:** a doji (c == o) is not a down-close bar (strict `<`, l.359 / l.364). It ends a CISD run, and it can be neither the run's start nor its last bar.
- **Equal lows / highs at the leg extreme:** `argmin` takes the **earliest** bar (l.437). A trigger bar can never be the extreme (l.438).
- **Equal fractal highs / lows:** the left side needs a strictly higher high; the right side allows an equal one (l.89, l.91). So of two equal highs, the first is the swing.
- **Touches:** a touch counts for the limit tap (`<=`), the stop (`<=`), the target (`>=`, no trade-through needed), the BE trigger (`>=`) and the pre-tap target cancel (`>=`). A sweep, though, needs a strict break (`<`).

**Pivot origin vs confirmation time:**
- A fractal at bar j is confirmed at the close of j+2.
- Build-up liquidity is known at the second fractal's j+2 (l.114).
- An inducement needs `m + 2 <= sweep bar` (l.466).
- An idm_a inducement must be taken at or after m+3 (l.481).
- The CISD level uses no pivot: it is built from closed bars ≤ the extreme < the trigger.

**Timeout anchors:**
- **Limit:** valid while `t < t0 + 6 × 300 s`. t0 is the open of the bar after the trigger, which is the trigger close (l.997). The 30-minute limit applies only before the tap.
- **1m CISD window:** counted in **bar indices** after the tap bar (`k - tapped > 22`, l.1011). A missing 1m bar therefore stretches it in clock time. On 5m days the window is 22 // 5 = 4 bars (l.981).
- **15-minute check:** anchored on the fill bar's **time** (l.1183).

## 3. Ledgers

### `COMPLETE_TRADE_LEDGER.csv`

The current config, 837 rows. Each `account_profile` value:

| account_profile | Rows | Net | What it is |
|---|---:|---:|---|
| `LIT_size_rule($1.40 engine commission)` | 120 | +$43,819.78 | the 2026 trades (= `lit_live`) |
| `…|REF_2021-25_5m_only` | 511 | +$1,264.94 | 2021-25 reference, trade_id `REF-…`, 5m bars only |
| `two_week_eval_path_b2b_stuck200($1.90)|<eval id>|<result>` | 116 | +$40,366.62 | the live eval sizing, back to back, with the stuck rule |
| `two_week_eval_path_b2b_no_stuck_rule($1.90)|…` | 90 | +$18,212.10 | the same without the stuck rule |

How the columns are filled:
- `signal_known_at` = the 5m trigger close. `entry_submit_at` = `entry_fill_at` = the open of the fill bar (a market order on the CISD close; the limit is virtual and never routed).
- `exit_time`:
  - EOD: the bar close.
  - CUT_T15: the fill-bar open.
  - STOP / BE / TARGET: the bar end, marked "intrabar time UNKNOWN".
- `exit_price` comes from the P&L, so it is exact to the tick. In 3 eval-path rows the soft-daily-loss clamp set the P&L instead, so their `exit_price` is UNKNOWN and the exit reason is `+DLL_CLAMP`.
- `gross_pnl - commissions = net_pnl` on every row (checked).
- `mfe_r` / `mae_r` are the engine's own, the same for every sizing.

### `SIGNAL_LEDGER_LIT.csv`

Every 2026 candidate the 5m detector found, both directions: 1,325 rows. Each row has:
- `setup_id` = `LIT-<day>-i<5m trigger bar index>-<L|S>`, which joins to the trade ledger.
- `first_failing_rule`, in the order the engine checks (`_run_core`). The filter keys come from `engine/brain._checks`.
- `filter_first_fail`: for skipped setups, the filter that would also have failed.

| Status | n | First failing rule |
|---|---:|---|
| TRADE | 120 | — |
| skipped | 479 | day already traded 397, busy (a trade open) 82 |
| rejected | 626 | disp 216, idm 145, window 98, stop 8-80 71, depth 64, monday 26, target <1.5R 6 |
| armed, no trade | 100 | limit expired (30 min) 55, extreme broken after the tap before the 1m CISD 20, no 1m CISD within 22 bars 12, qty 0 (real risk >89 pts) 6, target touched before the tap 3, <1.5R after the fill 2, extreme broken before the tap 2 |

The pre-fill classifier is a mirror of `simulate_x`. It agrees with the engine on every armed setup: 0 mismatches (filled ⇔ trade).

## 4. Robustness (current config, LIT size rule, **$1.90 a micro**, 2026)

How the table was made:
- **Base costs:** $1.90 a micro, plus 1 tick on the market entry and on STOP / BE / EOD / CUT exits. These are in the base already, and nothing below counts them a second time.
- **Tick rows:** post-hoc and exact in $, but the trade paths are left unchanged.
- **Latency and neighbour rows:** full engine re-simulations, on a 2026 window that equals `lit_live` exactly.
- **CI:** chronological block bootstrap. Each ISO week is one block that keeps its trades in order; 5,000 draws; 90% interval.
- **MFE ≥ 4R kept:** of the 23 base trades that reached +4R at some point, how many the variant still takes (same day and direction) and how many still reach 4R.

| Variant | Label | n | /wk | PF | Net 2026 | $/mo | Max DD | H1 net (PF) | H2 net (PF) | Net 90% CI | PF 90% CI | MFE≥4R kept |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---:|
| Base, live current | BASELINE | 120 | 2.91 | 4.15 | +43,502 | 4,435 | -2,213 | +33,666 (4.92) | +9,836 (2.88) | 19,993 to 69,393 | 2.21-7.24 | 23/23 |
| +1 tick per affected fill | RV | 120 | 2.91 | 4.02 | +42,948 | 4,378 | -2,247 | +33,258 (4.74) | +9,690 (2.81) | 19,399 to 68,861 | 2.15-6.99 | 23/23 |
| +2 ticks per affected fill | RV | 120 | 2.91 | 3.89 | +42,395 | 4,322 | -2,281 | +32,851 (4.56) | +9,544 (2.75) | 18,893 to 68,258 | 2.09-6.73 | 23/23 |
| +4 ticks per affected fill | RV | 120 | 2.91 | 3.65 | +41,288 | 4,209 | -2,349 | +32,036 (4.25) | +9,252 (2.63) | 17,771 to 66,990 | 1.98-6.30 | 23/23 |
| +1 tick on every fill incl. targets | RV | 120 | 2.91 | 4.01 | +42,866 | 4,370 | -2,247 | +33,196 (4.73) | +9,670 (2.81) | 19,359 to 68,714 | 2.15-6.98 | 23/23 |
| +2 ticks on every fill incl. targets | RV | 120 | 2.91 | 3.88 | +42,230 | 4,305 | -2,281 | +32,726 (4.55) | +9,504 (2.74) | 18,810 to 68,004 | 2.08-6.71 | 23/23 |
| Entry latency 1 min | RV | 120 | 2.91 | 3.97 | +40,001 | 4,078 | -2,029 | +27,371 (4.20) | +12,629 (3.57) | 18,222 to 63,007 | 2.16-6.77 | 17/23 |
| **Entry latency 2 min** | RV | 118 | 2.86 | **3.04** | **+29,594** | 3,017 | -3,633 | +25,649 (3.78) | **+3,945 (1.75)** | 8,868 to 53,229 | 1.54-5.30 | 17/23 |
| Fee +$0.50 ($2.40 round trip) | RV | 120 | 2.91 | 4.08 | +43,184 | 4,402 | -2,230 | +33,431 (4.83) | +9,753 (2.84) | 19,622 to 69,047 | 2.18-7.11 | 23/23 |
| Longs only | split | 55 | 1.33 | 4.45 | +20,422 | 2,082 | -1,429 | +18,118 (5.78) | +2,304 (2.08) | 5,250 to 37,985 | 1.76-9.36 | 8/23 |
| Shorts only | split | 65 | 1.58 | 3.92 | +23,080 | 2,353 | -1,660 | +15,548 (4.24) | +7,532 (3.42) | 9,000 to 39,391 | 1.97-7.58 | 15/23 |
| London fills 02:00-07:59 | split | 95 | 2.31 | 4.15 | +37,268 | 3,799 | -2,137 | +27,303 (4.53) | +9,965 (3.44) | 14,733 to 62,383 | 2.05-7.53 | 20/23 |
| NY AM fills 08:00-11:59 | split | 21 | 0.51 | 2.93 | +3,886 | 396 | -1,187 | +4,514 (6.31) | **-628 (0.46)** | -621 to 9,205 | 0.74-10.09 | 2/23 |
| NY PM fills 12:00-15:55 | split | 4 | 0.10 | — (no loser) | +2,348 | 239 | 0 | +1,849 | +499 | 382 to 4,712 | — | 1/23 |
| Top-1 winner removed | RV | 119 | 2.89 | 3.70 | +37,289 | 3,801 | -2,213 | +27,453 (4.20) | +9,836 (2.88) | 16,410 to 61,643 | 2.01-6.50 | 22/23 |
| Top-3 winners removed | RV | 117 | 2.84 | 2.99 | +27,508 | 2,804 | -2,213 | +17,673 (3.06) | +9,836 (2.88) | 11,479 to 44,427 | 1.70-5.03 | 20/23 |
| **Top-5 winners removed** | RV | 115 | 2.79 | **2.41** | **+19,450** | 1,983 | -2,213 | +9,614 (2.12) | +9,836 (2.88) | 6,672 to 33,023 | 1.41-3.96 | 18/23 |
| disp 0.7 (live 0.8) | RV | 134 | 3.25 | 3.65 | +41,446 | 4,225 | -2,751 | +32,879 (4.48) | +8,567 (2.38) | 18,334 to 66,561 | 2.00-6.18 | 23/23 |
| disp 0.9 | RV | 108 | 2.62 | 3.84 | +34,856 | 3,553 | -2,074 | +28,328 (4.61) | +6,528 (2.48) | 11,981 to 60,214 | 1.85-6.96 | 20/23 |
| disp 1.0 | RV | 92 | 2.23 | 3.48 | +26,365 | 2,688 | -2,007 | +23,515 (4.56) | +2,850 (1.71) | 5,831 to 50,179 | 1.48-6.78 | 15/23 |
| depth 0.4 (live 0.5) | RV | 121 | 2.94 | 4.15 | +43,502 | 4,435 | -2,213 | +33,666 (4.92) | +9,836 (2.88) | 19,993 to 69,393 | 2.21-7.24 | 23/23 |
| depth 0.6 | RV | 118 | 2.86 | 4.32 | +44,061 | 4,492 | -1,858 | +34,226 (5.26) | +9,835 (2.88) | 20,554 to 69,786 | 2.33-7.48 | 23/23 |
| **cisd1m 18** (live 22) | RV | 116 | 2.82 | **3.14** | **+31,307** | 3,192 | -2,121 | +24,112 (3.85) | +7,195 (2.17) | 10,656 to 55,303 | 1.63-5.52 | 19/23 |
| cisd1m 20 (= pre-switch) | RV | 120 | 2.91 | 4.02 | +43,076 | 4,391 | -2,213 | +33,666 (4.92) | +9,410 (2.66) | 19,733 to 68,712 | 2.18-6.95 | 23/23 |
| cisd1m 24 | RV | 122 | 2.96 | 4.07 | +43,244 | 4,408 | -2,213 | +33,407 (4.78) | +9,837 (2.88) | 19,616 to 69,121 | 2.17-7.16 | 23/23 |
| cisd1m 26 | RV | 124 | 3.01 | 4.07 | +43,315 | 4,416 | -2,213 | +33,407 (4.78) | +9,908 (2.89) | 19,662 to 69,197 | 2.17-7.17 | 23/23 |
| idm age 24 (live 36) | RV | 115 | 2.79 | 4.69 | +48,501 | 4,944 | -2,213 | +33,847 (5.03) | +14,654 (4.10) | 24,693 to 73,732 | 2.60-8.07 | 23/23 |
| idm age 48 | RV | 120 | 2.91 | 4.15 | +43,502 | 4,435 | -2,213 | +33,666 (4.92) | +9,836 (2.88) | 19,993 to 69,393 | 2.21-7.24 | 23/23 |
| idm dist 0.75 ATR (live 1.0) | RV | 110 | 2.67 | 3.53 | +35,315 | 3,600 | -2,592 | +32,943 (4.96) | **+2,372 (1.42)** | 12,191 to 61,074 | 1.75-6.39 | 19/23 |
| idm dist 1.25 ATR | RV | 126 | 3.06 | 3.73 | +41,540 | 4,235 | -3,470 | +30,549 (4.38) | +10,991 (2.77) | 17,763 to 66,946 | 1.98-6.52 | 22/23 |

RV = RESEARCH_VARIANT. Months at $1.90 (net, PF):

| Month | Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct (to 16th) |
|---|---|---|---|---|---|---|---|---|---|---|
| Net, PF | +9,973, 5.67 | +2,278, 2.05 | +7,418, 14.3 | +6,652, 7.04 | +5,064, 3.78 | +2,282, 3.87 | +882, 1.83 | +430, 1.30 | +1,882, 1.95 | +6,643, 9.55 |

Every month is positive. Jul-Sep together make +$3,194.

What the table says:
- **Costs barely matter.** Positions are small (about 5.3 micros on average), so +4 ticks on every affected fill, or a $2.40 fee, costs ≤5% of the 2026 $.
- **Latency is the real execution risk.**
  - 1 minute late is about neutral: H1 -$6.3k, H2 +$2.8k.
  - **2 minutes late cuts 2026 to +$29.6k and H2 to +$3.9k (PF 1.75)**, and drops 6 of the 23 +4R runners.
  - The bot must route the 1m-CISD market order within the first minute.
- **The result rests on a few big winners.**
  - The top 5 winners (all in H1) are 55% of the 2026 $. Without them: PF 2.41, +$19.5k.
  - **H2's winners are smaller:** its best trade is +$3.2k, against +$6.2k in H1. Its 5 best trades make +$9,960 at $1.40, about the same as H2's whole net (+$9,919 at $1.40): the other 35 trades net out to about zero.
  - The 2026 CI's lower end (+$20k) is carried by H1.
- **Most of the money is London.** London fills make 86% of the $. NY AM fills lost money in H2 (6 trades, -$628 at $1.90). That is a split, not a rule proposal.
- **Parameter neighbours, live values on a plateau:**
  - depth 0.4-0.6, cisd1m 20-26 and idm age 36-48 stay within ±2% of the live $.
  - **cisd1m 18 is a cliff edge (-28%).** 22 sits 2 steps above it: fine, but do not go lower.
- **Parameter neighbours that cut H2:**
  - disp 1.0: H2 -71%.
  - idm dist 0.75: H2 -76%.
  - Tighter setup filters shrink H2 sharply, so H2's profit depends on the marginal setups.
- **idm age 24 is better in both halves** (+$4.8k in H2). It is a lead only: it was found on the full 2026 data with H2 visible, so it is **not** for adoption before launch.

## Uncertainties

- **Eval path, H2:** the published two_week eval figures for the live config (+$29.8k / +$9.8k, 2-week pass H2 52.2%) are older than the 2026-10-24 cap invariant.
  - Today's code gives +$31.0k / +$9.3k with the stuck rule and H2 pass 50.7%.
  - Without the stuck rule, H2 is -$1.9k: a stuck eval that waits forever.
  - The owner-facing numbers should quote the stuck-rule path and count stuck evals as fails. No run was re-stored here.
- **Stop / BE fills:** they are filled at the stop level − 1 tick even when the bar gapped through it (`launch_evidence` F3: 1 case in 2026). The tick rows bound this; they do not model it.
- **Ledger precision:** the ledger's exit times for STOP / BE / TARGET are bar ends, so the exact intrabar time is unknown. Prices are back-adjusted NQ1!.
- **What the bootstrap captures:** only the variation between weeks in one regime-specific year (2026). The 2021-25 reference on 5m bars only is PF 1.01 at $1.40 and 0.99 at $1.90: no edge.
- **Live-loop equality test:** `python -X utf8 -m tests.test_lit_live` did **not** finish here. It hit a 15-minute timeout while other audit agents shared the CPU, so there is no pass or fail result. This audit changed no engine code, so the stored equality (`launch_evidence.md`) still applies, but it was not re-checked here.
