# LEAD_WIRES (day-edge2, 2026-11-21): engine/shadow_leads.py

Observe only. Not called from the trading loop (test e enforces: engine/live.py, account_b, rapid, lit_live, multi_account,
ninjatrader, sizing, server.py never reference it). It reads the data pipe's packed day (logs/datapipe/days/<day>/) after the
close and appends data/shadow_leads.jsonl (gitignored, .gitignore updated). Off: data/shadow_leads.json {"on": false}.

## 1. The nightly call (one line, engine/datapipe.py, at the end of run() after the days are packed and the review ran)
    try:
        from . import shadow_leads as _sl
        _sl.maybe_run(days_dir=os.path.join(w, "days") if w else None)   # w = the pipe's work dir
    except Exception:
        pass
(maybe_run never raises anyway; the try/except is belt and braces.) Or from the PC's 15-minute report task after 16:30 ET: maybe_run() only
shadows packed days, so calling it often is cheap and idempotent (rows de-duplicated by lead/src/entry_t).

## 2. The weekly line on the board / Jarvis
    from engine import shadow_leads; s = shadow_leads.summary(days=7)   # s["line"], s["A3"], s["ES"]
e.g. "A3 shadow: 9 signals, 6 would fill, +1.4R vs live | ES shadow: 2 of 8 Zlarior trades would be MES, -0.6R vs live (last 7 days)".
Board card / Jarvis: show s["line"] on Sundays (or in the weekly review, engine/zeus_review) - lead's choice of page.

## 3. Tests: add "shadow_leads" to tests/run_area.py "nq" list. `python -X utf8 -m tests.test_shadow_leads` (12/12, f = three
LiveBot paper replays, ~11 min) / `--quick` (11/11, seconds).

## 4. Nothing else: no ?v= tags, no sw.js, no apps.js change. No Decide card (paper leads only).

## Proof (2026-11-21)
- tests.test_shadow_leads 12/12 (f: LiveBot paper replay 2026-10-13/14 x3 - off, on, on after the shadow ran on the replay's
  own ledger - ledger + trades byte-identical).
- tools/update_gate.py --base origin/pc (7adf312d) --candidate 81784f94 --sessions 3: **SAME**, no trade differs on 2,304
  polls (2026-11-17 / 18 / 19).
- python tests/smoke.py: 10/11 (test_zenith_mode: no playwright in the container only).
