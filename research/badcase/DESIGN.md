# The BAD case business plan: pre-registration (written 2026-11-24 BEFORE any number below was computed)

PAPER RESEARCH ONLY (nothing bought, no setting changed). Code `research/badcase/badcase.py` -> `results.json`; write-up
`research/writeups/badcase-2026-11-24.md`.

Engine = research/plans/rank.py, unchanged: the real eval sizing (two_week 40% of room = owner-approved) + ATLAS's lane, MFFU
funded payout logic, one slot per plan, a failed eval / lost funded account re-bought the next session, 126 sessions,
5-session block bootstrap. Prices: Builder 50K $91.80, Builder 25K $63, Rapid EOD 25K $97.20.
Markets (block pools): **2025-like** = 2025-01-01 .. 2025-12-31 (added here as span "Y25"), **2021-25 mix** = REF,
**2026-like** = H1 (Jan-Jun) and H2 (Jul-Oct). 500 paths each (eval paths seed 7, slot paths seed 23).

Per plan x market: eval pass / fail % (60 sessions), $ to the owner in 6 months, fees, net, $ per eval bought
(= net / evals bought), payouts a month, worst-case eval spend a month (90th percentile of fees / 6), funded accounts lost,
and the BREAK-EVEN pass rate = price / (owner $ per passed eval in that market). "Worth buying in a 2025 market" = net > 0 in
Y25 AND net >= -2 x price in REF.

(2) ATLAS funded 25K (funded-only runs from a fresh funded start, ATLAS trades only, ATLAS's lane): today ($250 a trade,
first payout ask = the cap) vs smaller ($150) vs payout rhythm (ask the minimum each time). Report owner $ / 6 months, payouts,
chance of losing the account, first payout median, per market.

(3) Early-warning rule, fixed now: LIT's rolling 20-trade average R (each trade's $ / its own risk, run lit_live) below
**the 10th percentile of all 20-trade windows in Jan-Jun 2026** = "BAD regime: stop buying evals" until it is back above the
Jan-Jun 2026 MEDIAN. Tested on 2021-25 and Jul-Oct 2026: on each session, the 40-session Builder 50K eval outcome of the
stored eval-path LIT daily series (run lit_adopt_t15_be_off_eval, daily rules of research/portfolio/portfolio.evals) started
that session, split by signal on / off; $ per eval bought = P(pass) x the plan's owner $ per pass (from (1), REF) - price.
Useful = pass % with the signal ON clearly below OFF in 2021-25 (difference > 10 pts) and the signal does not fire on more than
20% of Jul-Oct 2026 sessions.

(4) BLITZ $150 on the Rapid EOD 25K: research/pillars/blitz_rapid.py variant "V5 BLITZ $150" vs "V0 today LIT+ATLAS", rerun on
the same 4 markets. +EV across regimes = net 6 months higher than V0 in Y25, REF, H1 and H2.
