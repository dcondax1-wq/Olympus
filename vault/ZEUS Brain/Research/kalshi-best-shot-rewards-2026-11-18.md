---
tags:
  - zeus/research
  - family/kalshi
  - verdict/rejected
  - bot/kalshi
type: "research"
date: "2026-11-18"
status: "REJECTED for real money. Best idea found ($10 bids at 1c on thin reward sides) looks good on a model but is not proven; agrees with the red team"
source: "research/writeups/kalshi-best-shot-rewards-2026-11-18.md"
aliases:
  - "Kalshi best shot"
---

# Kalshi best shot

> [!failure] Verdict: rejected
> REJECTED for real money. Best idea found ($10 bids at 1c on thin reward sides) looks good on a model but is not proven; agrees with the red team

**Full title:** Kalshi best shot - the liquidity-rewards maker, scored the way Kalshi actually pays

## Summary

**Do not put money in.** Kalshi really pays a daily pot to resting orders, but nothing shows a small account keeps more than the fills take away:

## Money first

**Do not put money in.** Kalshi really pays a daily pot to resting orders, but nothing shows a small account keeps more than
the fills take away:

- **The only real forward test lost.** The PC paper test ran 0.93 days: +$12.93 rewards, -$13.54 on 3 fills = **-$0.61**
  (-$0.03 a day per $100). Days up vs down: not enough days to count.
- **The broad rule is about a coin flip.** On 32 days of public tape (6 shipping-strait series, Kalshi's real scoring, $10 bids):
  +$5.31 / +$3.85 a day per $100 in the two halves, but those rewards assume today's order books; days up vs down 17 vs 15;
  worst day -$11.81 on about $250 parked. The red team found the same kind of rule **lost $3.06 a day per $100** on the 43 hours
  of new data after the window.
- **The best idea is too small and too unproven.** A $10 bid at 1c (1,000 contracts) on the cheap side, only where the live book
  says it earns at least $1.50 a reward period: replay +$28.65 / +$31.39 a day per $100 with 0 fills and 29 up days, 0 down. But
  only about **$14-18 was ever in play** (1-2 such bids at a time, about **$4.80 a day in total**), the rewards are built on today's
  books (no history exists), it was watched forward for only half an hour, only 3 of about 40 tested cells passed (chance can do
  that), and no real payout was ever checked.
- **Expected if the owner tried $100 anyway:** realistic -$3 to +$2 a day, centred near $0 (red team range; my broad-rule replay
  sits at the top of it only because its rewards assume today's depth). **Worst case:** a 1c bid loses its whole $10 when it fills;
  five bids = -$50. The program also **ends Jan 1, 2027**.

Plan file: `research/lab/kalshi_live_plan.json`, **status "rejected"** (paper only, reasons inside). Nothing armed; Kalshi stays paused.

## Links

- Family: [[Family kalshi]]
- Day: [[Day 2026-11-18]]
- Strategies: [[Kalshi K8]]
- Source: `research/writeups/kalshi-best-shot-rewards-2026-11-18.md`
- Back to [[ZEUS Home]]
