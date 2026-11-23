# night-roll red team (2026-11-23): b2b2fd0ec -> night-roll-rt

| # | Finding | Sev | Fixed |
|---|---|---|---|
| 1 | TRADE_HOME R: tools/roll_now.py exits 1 (a click for you) or 2 (not now: too early / a trade open), and run_bat returns 1 for a missing file too; every non-zero showed "[FIX] ROLL.bat did not open. Tell Claude." (a false alarm in a trade) | LOW | exit 2 = "Not now ... nothing was switched"; else the roll's own re-read line |
| 2 | Landing with night-cleanup: ROLL.bat moves to tools/bat; R's run_bat("ROLL.bat") and the readiness text name it at the old place | MED (landing) | merge_notify.py (night-cleanup-rt) rewrites them in this branch's files after the merge |

Checked OK: readiness "roll" NOT READY only when the chart month != the order month (roll_watch level "bad": exactly when
place_bracket refuses entries), never on the new contract, continuous / unknown = no alarm, the chart switched the evening before
after 15:55 = "early" (fine), WARN only the day before (WARN never pushes); R only runs ROLL.bat (tools/roll_now.py acts only
from the evening before after 15:55 / after the roll, and only with no NinjaTrader MNQ / NQ position and no heartbeat trade; it
never places / changes / cancels an order); the Thu Dec 10 00:00 order switch: the NinjaTrader adapter's place_bracket refuses
every entry while the chart contract differs (_contract_mismatch), and the keep-alive sends through the same adapter (ad.send ->
place_bracket): the gap to CME's Mon Dec 14 roll is missed trades at most, never a wrong-contract order.
Tests: roll_rt 3/3 (new), roll_dec_audit 24/24, dec_roll 37/37, roll 23/23, nt_roll_guard 10/10, roll_now 43/43, ready 36/36,
ready_rt 27/27, trading_home 46/46, ops 114/114, alerts_plus 92/92, ninjatrader --selftest 80/80.
