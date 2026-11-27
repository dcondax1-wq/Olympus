# night-of-exec: what the lead wires (2026-11-27)

Write-up: research/writeups/ofexec-2026-11-27.md. Research only. The helper edited no engine / live / dashboard file.

1. engine/costs.py: add an order-flow lane A entry ("OFA") next to LIT / ATLAS (research and money pages only):
       ENTRY_SLIP_TICKS["OFA"] = 18        # market at decision, today's 2.75 s delay (modelled: ATLAS share x first-minute run)
       OFA_ENTRY = "limit_at_level_5m_then_market"   # recommended style (E5): 0 slip at the level (needs 1 tick through),
                                                      # fallback market after 5 min at ENTRY_SLIP_TICKS["OFA"]
       STOP_SLIP_TICKS_BY["OFA"] = 2       # base, as LIT; stress 10 (exec_results.json X2); no real stop fill yet
       # targets: TARGET_THR_TICKS = 1 is right for OFA too (0 of 28 target hits were touch-only); COMM_RT 1.90
2. engine/of_paper.py lane A fill (needs a NEW dated design file, DESIGN_paper.md is frozen): score paper fills as E5
   (resting limit at level_px for 5 min, 1 tick through; else the first trade after +5 min with the market slip), and keep
   the old open + 1 tick fill as a second column so the forward harness can compare.
3. PC (owner, later): log real stop fills (fills.jsonl.gz exit_slip_ticks) before any live use; the stop cost (2 vs 10 vs 41
   ticks) is the open question. Lane C (book timing) on the PC replay is the next measurement.
Tests: python -X utf8 research/orderflow/exec_study.py --selftest (no area suite touched).
