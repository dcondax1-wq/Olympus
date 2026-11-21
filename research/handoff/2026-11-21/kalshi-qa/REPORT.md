# Kalshi page QA for Monday's LIVE day (2026-11-21, day-kalshi)

The Kalshi page (tools/web_public/kalshi/) checked as the owner will use it Monday during live trading, iPhone 390 x 844, dark.

| Checked | Was | Now |
|---|---|---|
| Bot state after K8 stops ITSELF (drawdown, win rate, 3 errors) | **PAPER, no reason** (the card read the retired maker's state file, not K8's arm record) | **STOPPED + the reason** (engine/kalshi_live.card reads arm.json `stopped` / the kill switch) |
| The phone PAUSE | LIVE (K8's pause lives in clock_state.json) | **PAUSED** |
| Armed but the K8 loop not running | could read LIVE (the idle test used the maker's heartbeat; an arm record with no ledger yet fell through to the maker card) | **ARMED, PC off** (K8's own loop heartbeat; read_card uses K8 when the maker loop is not running) |
| PC silent > 60 min while LIVE | an old LIVE looked current (only a small "(late)") | **PC SILENT** pill on the header, the top card and the status card + "PC silent: last news 2 h ago" + "is it on?" |
| The status line while LIVE | the retired maker's words: fills, resting orders, "stop at -$25 a day" | K8's own: today's live bets + $, **stops used: $x of $8 today, $x of $13.75 this week, $x of $19.25 from the best point** |
| Bankroll | always "$55.00" | live: **$58.50 (started $55.00)** from the live P&L; paper: $55.00 |
| Armed, no live bet yet | "Paper $: ..." next to a LIVE pill | "No live bets yet · paper $: ..." (paper $ never added to the bankroll) |
| A bet whose answer from Kalshi was lost (new 'check' state) | (did not exist) | card code `c`; today's row "counted as in, result 17:00"; the bet log "open (Kalshi's answer was lost: counted as placed)"; counted in today's stop |
| Not published | "no PC data yet" | "not published yet: no PC data" |
| The Monday checklist | one tap: "Monday go-live checklist n of 6" on the top card -> #kgo | unchanged (checked) |

Tests: tests/test_kalshi_clock.py 49/49 (r1b, r7, r8 new: the card's states), tests/kalshi_k8_dash.cjs 65/65 (q1-q6 new),
run_area kalshi 17/18 then kalshicity_page alone 105/105 (it fails only inside the full run, at the same page-load step both times
today; the kalshicity page was not touched).
Screenshots (390 x 844 @2x): qa-live.png (LIVE Monday 16:50, a 'check' bet), qa-silent.png (the PC silent 2 h).
Lead: kalshi/sw.js to k58 (LEAD_WIRES_dashboard.md Update 9).
