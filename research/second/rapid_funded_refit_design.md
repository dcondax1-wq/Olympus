# Rapid EOD funded refit - design (pre-registered 2026-11-21, committed before any run)

Question: the Rapid funded presets (engine/multi_account mffu_rapid_eod_25k / _50k sizing.funded, = tools/uprisk UP25 / UP50)
copied the Builder's winner cap (max_win $1,000 / $2,000: a trade's winner sized to stay inside the Builder's 50% consistency
and $2,000 payout cap). MFFU Rapid EOD funded has neither (research/lit/mffu_rules.json: no funded consistency, no payout cap).
Does a bigger cap, a bigger cushion kept in the account, or a smaller room share make more money without losing more
accounts?

HARD LIMIT (never tested past it): the 50K is never uncapped: one $10,000 day moves an MFFU Rapid to LIVE and suspends every
sim account (mffu_rules rapid_eod_50k.live / live path). The 50K cap stays <= $7,500 a trade.

Engine: tools/money/rapid25_launch.life_row (money_plan.RSeat: eval -> funded -> lost / stuck -> re-buy, fees in, 90%), 1,000
paths a market, H1 Jan-Jun 2026 / H2 Jul-Oct 2026 / REF 2021-25, same seeds. ATLAS 10 ticks a side and ATLAS sized on a
10-tick stop (the live preset since the owner's yes, card rapid-atlas-size-10t). Eval = today's preset (LIT skip; the
rapid25-lit-bank lane is a separate card). Only the FUNDED stage changes.

Grid (fixed now):
  25K  cap {$1,000 today, $2,000 (= 2x = the lead's 25K value)} x cushion kept above the buffer {$500 today, $1,000}
       x room share {0.6 today, 0.4}                                                                     = 8 rows
  50K  cap {$2,000 today, $4,000 (2x), $7,500} x cushion {$1,000 today, $2,000} x room {0.6 today, 0.4}  = 12 rows
  (pct_max_usd, the $ risk cap per trade, stays $750 / $1,500.)

Measured per row and market: $ a month to the owner over 6 months, funded lost in 6 months %, first payout median, no
payout in 6 months %.

Decision (fixed now), per size: candidates = rows with $/month > today's in H1 (pick) AND in H2 (check) AND funded lost <=
today's + 2 pts in H1 and H2. Winner = the candidate with the most H1 $/month; report REF (2021-25) for it. Also reported as
two single levers: cap alone (cushion and room today) and cushion alone (cap and room today). No candidate = keep today.
A winner -> Decide card "rapid-funded-refit" (owner yes before any preset change); keep-1000-rapid re-valued from the
cushion-alone row. Nothing live changes.
