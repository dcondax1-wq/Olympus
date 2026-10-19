# Proposed engine/lit.py change: the 15-minute check (NOT applied; off by default)

Research: research/writeups/lit-loss-learning.md, run lit_ll_t15, tools/lit_loss_learn.py.
Apply only AFTER the 21:00 ET launch, with tests. Default None = today's behaviour exactly.

## 1. Default (in the LIT defaults dict, after "wk_stop")

```python
    "t_check": None,             # 15-minute check (research/writeups/lit-loss-learning.md, run lit_ll_t15; off by default):
                                 # {"at": 15, "x": 0.3, "mfe": 0.5} = at the close of the 1m bar that ends `at` minutes after the
                                 # fill, if the trade never reached +mfe R and that close is x R or more below the entry (and the
                                 # breakeven has not moved the stop), exit at the next 1m open - 1 tick ("CUT_T15"). 1m bars only.
```

## 2. simulate_x management loop

Replace

```python
    be_r = P["be_r"]
    cur, be_done, mfe, mae, worst = stop, False, 0.0, 0.0, 0.0
    k = fill
    exit_px = kind = None
    while k < B.n:
        if B.day[k] != s_day or (not ev and B.mod[k] >= 1080):
            k -= 1; exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        mae = max(mae, (entry - lo_d[k]) / risk)
```

with

```python
    be_r = P["be_r"]
    tc = P.get("t_check") if B.secs == 60 else None
    cur, be_done, mfe, mae, worst = stop, False, 0.0, 0.0, 0.0
    k = fill
    exit_px = kind = None
    cut = None                               # the 15-minute check fired at the close of the previous bar
    while k < B.n:
        if B.day[k] != s_day or (not ev and B.mod[k] >= 1080):
            k -= 1; exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        if cut is not None:
            exit_px, kind = float(o_d[k]) - SLIP, cut; break
        mae = max(mae, (entry - lo_d[k]) / risk)
```

and after the flat check (`exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break`), before `k += 1`:

```python
        if tc and not be_done and (B.t[k] - B.t[fill]) / 60.0 + 1.0 == float(tc.get("at", 15)) \
                and mfe < float(tc.get("mfe", 0.5)) and c_d[k] < entry - float(tc.get("x", 0.3)) * risk:
            if k + 1 < B.n and B.day[k + 1] == s_day:
                cut = "CUT_T15"              # exit at the next 1m open
            elif live:                       # live: the check bar is the last closed bar -> exit at market now
                exit_px, kind = float(c_d[k]) - SLIP, "CUT_T15"; break
```

This is exactly the study's rule (tools/lit_loss_learn.py psim, rule "ts" with upto = at): close strictly below entry - x R.

## 3. Before switching it on

- `python -X utf8 -m tests.test_lit_live` must stay 120/120 with t_check None.
- A new test: with `t_check {"at": 15, "x": 0.3, "mfe": 0.5}` the engine's 2026 trades must equal
  `tools/lit_loss_learn.py variant(T15)` (13 CUT_T15 exits: 2026-01-13, 01-16, 01-29, 01-30, 03-04, 03-31, 04-28, 05-07, 05-12,
  07-03, 07-07, 09-02, 10-06).
- Live wiring: CUT_T15 is a market exit. The PC/NinjaTrader route needs `route_all_exits`; the cloud paper ledger must accept
  the new exit kind. The weekly stop (`wk_stop`) counts "STOP" exits only; under two_week config C it is off anyway.
- live_model.json change (coordinator): `"lit": {..., "t_check": {"at": 15, "x": 0.3, "mfe": 0.5}}`.
