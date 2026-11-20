# Kalshi K8: ready for Monday 2026-11-23 (day-kalshi, 2026-11-20)

## $ first
| What | Result |
|---|---|
| The plan | $2.50 a bet, 3 bets a weekday (gold DOWN 05:15, gold UP + silver UP 16:45 ET), $55, no more deposits |
| Kalshi's public record, Aug 3-Nov 20, at $2.50 (refreshed today, 397 markets) | 234 bets, 170 won (73%), **+$205.79** (~+$13 a week) |
| Last 4 weeks | 58 bets, 42 won, +$48.00 |
| Nov 16-19 + Nov 20 morning | 4 of 13 won, about -$11.66 |
| Worst a week can cost (coded stop) | -$13.75; whole account OFF at -$19.25 from its best point |

## Bad week: noise or the edge dying? (pre-registered: research/kalshi_k8_day/PREREG_noise.md, committed before the data was read)
**Verdict: WARNING, not dying.** In the good months (Aug 3-Nov 13, 75% won) a 4-day stretch as bad as Nov 16-19 came up
**1.0% of the time (about 1 in 99)**; none of the 72 real 4-day runs was that bad. So it is an unusual streak. But there is no sign
the edge is fading: the weekly win rate is not falling (p 0.74), prices are not creeping up (p 0.46, avg still ~51c), and the
week before (Nov 9-13) won 14 of 15. The last 60 bets still won 73% (chance the true rate is below break-even 54%: 0.1%).
By the pre-registered rule: **go live Monday at $2.50 as planned, the stops guard it, and check again after 20 live bets.**
Plain odds: roughly 99-to-1 against this being "normal luck" for a 4-day window, but no other evidence of decay; most likely a bad
patch in a still-working edge. If the next 20 live bets win under ~55%, Claude should recommend OFF.

## What was built
1. **Monday rehearsal through the real bot** (`research/kalshi_k8_day/rehearsal.py` -> rehearsal.json): Monday's real tickers,
   books rebuilt from recorded public trades of 6 real days, paper + live (fake key, no network), bot restarted at 12:00 ET.
   Live: exactly 3 orders a day, right side, 4-6 contracts within $2.50, good till +40 s; results match the Nov 16-19 dry run to the cent.
2. **Tests** `tests/test_kalshi_k8_day.py` 43/43: every stop on the $55 settings fires at the right cent (day -$8, week -$13.75,
   peak -$19.25, 3 a day, one per market, 70c cap, $2.50 max, win-rate 58% after 60 / not before, price creep 58c on 30 / not under 30);
   fees (4 contracts 7c = 1.75c each, 1-3 contracts 2c each); restarts mid-day and mid-window keep the counters and never send twice;
   no order with a wrong/lower-case phrase, a hand-made arm file, no key, the kill switch, or LE_KALSHI_LIVE=0; one order call in the code, behind the gate.
3. **Dashboard** (helper): Kalshi page K8 card = today's windows with countdowns (Thanksgiving evening "skipped"), price vs fair,
   last 5 bets, day/week/peak bars, edge health Healthy/Watch/OFF; Dionysus "K8 today" panel. `tests/test_kalshi_k8_dash.py` 36/36.
   PC card gained `dy`, `e`, `lg` (`engine/kalshi_clock.card_k8`); `tools/pc_report.py` trims them before ever cutting the Kalshi block.
4. **Data**: `research/kalshi_k8_day/fetch.py` (public GET, 1/s, 809 calls, 0 errors) -> data/tape.jsonl; `tools/kalshi_k8_feed.py`
   -> `tools/web_public/kalshi/k8.json` (3 KB, per-leg win rate, fair price, last 30/60, creep, last 8 weeks).
5. **Audit 404s**: forward.json / scan.json came from the retired kalshi-feed: the page no longer requests them (forward strip says
   retired). kit.json is written by the site build (exists on the real site; a source copy is forbidden by test_kalshi_page): no change.
6. **One doc**: `docs/KALSHI.md` (what runs where, files, 3 Monday steps + the phrase line, what each push says, calendar).
7. **Lead's 05:36 ET finding fixed** ("From the peak (OFF) -$30.65 of -$19.25", "Next window 4:00 PM"): display only. While nothing
   is live the card showed the PAPER ledger, which still held the old $15 paper bets of Nov 19 + the 2 paper-only legs. No stop ever
   reads paper (kill_state and the order gate read clock_live.json, which is empty): paper never stopped and live starts clean Monday.
   Now the paper card shows only the 3 live legs at today's $2.50 size, and the next window is the next LIVE one (16:45, not the
   paper-only 16:00). Tests p1-p3. Owner action: none (no reset needed).
8. Small fix: pushes said "on 1 bets" -> "on 1 bet".

## Tests
`python tests/run_area.py kalshi`: 756 passed, 1 failed. The 1 = test_kalshi_page "sw.js CACHE == ?v" (clears with the lead's sw.js
wire, LEAD_WIRES_dashboard.md). kalshicity_page / browser parts of kalshi_page + dionysus could not run: Python Playwright is not
installed in this container (node Playwright is; kalshi_k8_dash ran on it). Smoke 7/8 (test_zenith_mode, same Python Playwright reason).

## Not done / honest notes
- The PC's own paper ledger since Nov 19 cannot be seen from here (`python -X utf8 -m engine.kalshi_live --clock-report` on the PC).
- k8.json is refreshed by Claude (fetch + feed), not by the PC (a tracked file the PC rewrites breaks its git pull).
- Screenshots use the test fixture numbers, not the PC's live card.
