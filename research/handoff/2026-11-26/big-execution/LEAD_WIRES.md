# big-execution: what the lead wires (2026-11-26)

Write-up: research/writeups/execution-2026-11-26.md. Verdict: stay on NinjaTrader (MFFU has no API route: Tradovate-only, no
API keys for prop accounts, no Rithmic/CQG/ProjectX); move the ORDER TRANSPORT from OIF files to a socket add-on after a Sim week.

Nothing here touches the live bot. Paper only (PAPER_ONLY in engine/nt_socket.py and ninjatrader/LE_Bridge.cs).

1. Red team first: engine/nt_socket.py (subclass of NinjaTraderAdapter, transport only) + ninjatrader/LE_Bridge.cs (5 unverified
   NT API assumptions at the top of the file).
2. Then (lead only, not done here): `"nt-socket": NtSocketAdapter` in engine/live.py ADAPTERS; self-heal copies LE_Bridge.cs into
   AddOns like LE_TickRec (after 16:00 ET, flat).
3. Owner: one F5 at the PC; `python -m engine.nt_socket --ping`; then the comparison week (`tools/exec_compare.py --pc`).
Tests: `python -X utf8 -m tests.test_nt_socket` (17), `python -X utf8 -m tests.test_le_bridge_cs` (14, needs mono; skips on Windows),
both in run_area.py pc. engine.ninjatrader --selftest unchanged (81 PASS). smoke 11/11.
