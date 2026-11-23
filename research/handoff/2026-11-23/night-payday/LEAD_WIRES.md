# night-payday: lead wires

1. tools/web_public/gate/index.html line 63: `business/payoutcoach.js?v=2` -> `?v=3` (and the same string in tests/test_gate_page.py
   line 74). Left out here on purpose: night-seedata edits the same line (gate.js g20 -> g21), so one edit at landing avoids a conflict.
   Every other page that loads payoutcoach.js is bumped to v=3 on this branch.
2. After landing night-seedata too, two short phone words can match the new wording (optional, same branch as the lead likes):
   business/mffu.js goalBit "payout ready $X" -> "REQUEST PAYOUT TODAY $X"; gate/arenas.js "Payout ready: ask MFFU" -> "REQUEST PAYOUT TODAY".
Nothing else lead-only: no sw.js, apps.js, APPS table or build_web_dashboard.py edits.
