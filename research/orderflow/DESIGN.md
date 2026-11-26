# Order-flow battery - pre-registered design (written 2026-11-24, BEFORE any tick data reaches the cloud)

Research only, paper. Nothing here can trade, arm or change a live setting. Runner: `research/orderflow/of_battery.py`.
Data: per-5m order-flow summaries the PC builds from its own tick files (`engine/ofsum.py`, see "Data" below). Frozen with
this commit; **no rule, constant or threshold below changes after the first look.** A failed test goes to
`docs/TESTED_AND_REJECTED.md`; a new idea needs a new dated pre-registration and days the first look never saw.

Relation to `PREREG_ticks.md` (2026-11-23): OF1, OF2, OF3A are **copied unchanged** (same constants: zone 8 ticks, absorbed share
0.20, block = 99.5th pct of trade size over the 5 prior tick days, LVN rules). What is new here: (a) the split (the tick days
start 2026-09-14, so "2026 H1 vs H2" is empty at first; this battery splits the tick days in time), (b) three new tests
OF4-OF6, (c) the bar-proxy twin of every test on the same days, (d) a 40-day first look.

## Data (what the PC sends; built by engine/ofsum.py from data/ticks, NQ only)
Per CME day (18:00 -> 17:00 ET), into `days/<day>/of/`:
- `NQ_bars5m.csv.gz`  one row per 5m bar: t (bar open, unix s), o h l c (first/max/min/last trade), vol, buy (lifted the ask),
  sell (hit the bid), unk (no side), n (trades).
- `NQ_fp5m.csv.gz`    the footprint: bar (row number in NQ_bars5m), k (ticks above that bar's low), b (sell volume at that
  price), a (buy volume), u (no-side volume). Every traded price of every bar.
- `NQ_prints.csv.gz`  every single trade of >= 10 contracts: ms (ms since the day's first trade), k (ticks above the day's
  low), size, side.
- `NQ_meta.json`      day, first/last trade time, rows, the low price (tick base), a trade-size histogram (1..199, 200+),
  side source shares (quote rule / tick rule / unknown, by volume), `filled_in` (NinjaTrader history quotes = Last).
Everything above is exactly what OF1-OF6 need: zone volume/delta at a bar extreme (footprint), block prints from the sweep
bar to the entry (prints; the 99.5th pct comes from the histogram; if it is < 10 the OF2 result is flagged "approx"),
tick volume profile (footprint summed), bar delta and CVD (bars). Raw ticks never leave the PC.

## Days, split, looks
- Tick days = NQ days with `NQ_meta.json` and >= 50,000 trades (a thin / half day is dropped, listed).
- **Discovery** = the older half of the tick days (ceil(n/2)), **Confirm** = the newer half. Settings of OF5 / OF6 are picked on
  Discovery only; OF1-OF4 have no setting to pick.
- **Looks (max 3):** first at >= 40 tick days, second at >= 60 (the PC's own PREREG_ticks run happens there too), final when the
  backfill reports done (or 120 days). Each look re-splits all days available then. A PASS must hold at every later look.
- Sample floor: a half with < 8 trades (filters: < 8 LIT/ATLAS trades in that half; stand-alones: < 8 signals) -> "TOO FEW",
  never a pass; it waits for the next look.

## Common
- LIT trades: `tools/lit_losses.run2(..., sessions=None)` = the live LIT replay with costs, all days the bars cover (identical to
  `lit_losses.run()` up to 2026-10-14, checked 2026-11-24: 127 = 127 trades in 2026). Needs `data/NQ_5m/1m` to cover the tick
  days (`python tools/data_pull.py --latest`); a tick day without bars has no LIT trades and is listed.
- Stand-alone sim (OF3, OF5, OF6, as `of_study._sim_df`): entry next 5m open + 1 tick, stop 1 tick beyond the signal bar,
  target 2R, flat 15:55, $500 risk (micros = 500 / (risk x $2), 1..40), $1.40 a micro round trip + 1 tick slippage each way.
- Placebos: filters = skip the same number of random trades in the same half (3,000 draws), p = share >= the observed gain;
  stand-alones = coin-flip direction on the same signals (3,000 draws).
- Side quality: if < 50% of the volume has a quote-rule side (history = tick rule), the result is labelled "tick-rule sides".
  Once >= 20 forward-recorded (quote-rule) days exist, their own gain must have the same sign, else "sides disagree" (no pass).

## The six tests
| # | What | Rule (frozen) | Pass (both halves unless said) |
|---|---|---|---|
| OF1 | LIT entry only when the sweep was ABSORBED | sweep-extreme 5m bar of the LIT trade; zone = prices within 8 ticks of that bar's tick extreme; vz = zone volume, dz = zone buy - sell; absorbed = dz x dir < 0 and abs(dz) >= 0.20 x vz. Skip trades not absorbed | kept net $ > all-trades net $ in Discovery AND Confirm; keeps >= 50% of trades; skip-placebo p < 0.10 (all days) |
| OF2 | LIT skip when block prints are against it | block = one trade >= 99.5th pct of size over the 5 prior tick days; signed block volume from the sweep-extreme bar open to the entry; skip when x dir < 0 | as OF1 |
| OF3A | LVN rejection on the real tick profile (stand-alone) | PREREG_ticks OF3 rule A unchanged (prior-day RTH 2-pt profile, LVN <= 35% POC between >= 60% bins, 10:00-15:00 touch + close back + top/bottom half + bar delta with the trade, first of the day) | PF >= 1.15 and net > 0 in each half, >= 0.5 trades/wk, coin-flip p < 0.10 |
| OF4 | ATLAS MACD-at-sweep (member MD) only when absorbed | the MD trade's sweep-extreme bar = the closed 5m bar with the lowest low (long) / highest high (short) of the 6 bars before entry; OF1's absorption rule, same constants. Skip not absorbed. $ = R x $250 (ATLAS size), R = pts / risk from the MD units | as OF1 (ATLAS MD trades) |
| OF5 | Absorption reversal at prior-day RTH high/low and Globex (18:00-09:30) high/low (stand-alone) | 09:45-15:00 ET, a 5m bar trades >= 1 tick beyond the level and closes back inside; zone (8 ticks from the bar's extreme) delta WITH the push (buyers at a high, sellers at a low) and abs(dz) >= s x vz -> fade at the next open; first signal of the day. **s in {0.20, 0.35}, picked on Discovery** | PF >= 1.15, net > 0 in each half, >= 0.5/wk, coin-flip p < 0.10, AND more net $ than its bar-proxy twin over all days |
| OF6 | CVD divergence at a new RTH high / low (stand-alone) | 10:00-15:00 ET, bar k makes a new RTH high (09:30 on); the previous RTH high was set >= G bars earlier; RTH CVD at k's close < CVD at the close of the bar that set the previous high -> short at the next open (mirror for lows); first of the day. **G in {6, 12}, picked on Discovery** | as OF5 |

Bar-proxy twins (info, same days, same code path): delta = volume x CLV (CLV = (2c - h - l) / (h - l)), zone stats from the
bar's own volume and CLV. They show whether real ticks add anything over what was already rejected on bars
(`orderflow-program-2026-11-23.md`: every bar version of OF1/OF2 cost LIT money in 2026).

Counted variants: OF1, OF2, OF3A, OF4 = 1 each; OF5 = 2, OF6 = 2 -> **8 scored variants**. Any PASS is a candidate only:
3 months of forward-recorded days that agree, then the normal LIT/ATLAS change process and the owner's yes. Nothing is armed.

## Note added 2026-11-24 (same day, before any data; transport only, no rule changed)
The trade-level `NQ_prints.csv.gz` file is dropped: the PC now computes OF2's frozen block threshold itself (99.5th pct of size
over the 5 previous tick days, >= 3 needed) and ships per-bar signed block volume `bth` (plus fixed b10/b20/b50) in
`NQ_bars5m.csv.gz`, with `block_th` in the meta. OF2's window (sweep-extreme bar open -> entry, both on the 5m grid) is whole
bars, so the result is identical (selftest: parity with `of_study.prereg` on raw ticks). No trade-level tape leaves the PC.

## Note added 2026-11-25 (day-ofmax, before any tick data reached the cloud; no rule changed)
A 4th look at **250 tick days** is added (looks 40 / 60 / 120 / 250; `--final` = the 250 look, or when the backfill reports
done). This can only make a PASS harder: a test that passed earlier must still pass at every later look. The PC also runs the
battery itself at each look (`engine/tickrec.autopilot`, results under `logs/orderflow/`, one phone line), so the first look
happens the night the 40th day is in, not when the cloud next pulls.

## Note added 2026-11-26 (day-oflearn, before any tick data reached the cloud; code bug, no rule changed)
`filter_report` / `standalone_report` (and `of_study.prereg`) read the placebo p as `(p or 1) < 0.10`. With 3,000 draws a very
strong result rounds to p = 0.0, which that test read as 1, so the strongest possible pass was REJECTED. Found by the planted-tick
proof (`of_sim.py`, `tests/test_oflearn.py`): OF1 kept +$9.9k / +$6.3k in both halves with p 0.0 and still said REJECTED. Now
`p is None` alone means "no placebo". The frozen rule (p < 0.10) is unchanged.
