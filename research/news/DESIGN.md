# News-day playbook. Pre-registration (2026-11-26 ~12:30 ET, BEFORE any measurement or run below)

PAPER RESEARCH ONLY, no live file touched. Code `research/news/news.py` -> `research/news/results.json`; write-up
`research/writeups/news-playbook-2026-11-26.md`. Futures bars only: NQ 5m 2021-11 .. 2026-11-20 (the same 5m bars everywhere
so every year is comparable; 1m exists only for 2026 and is used for the +1-minute stats only).

Calendar (`data/news/events.csv`, honest coverage): FOMC statement 14:00 + presser 14:30 complete 2021-26; CPI / NFP / PPI
08:30 complete 2024-26, 3 each in 2023, none 2021-22. NFP 2021-23 gaps are filled ONLY by the BLS first-Friday rule (known
in advance; flagged "rule"); CPI / PPI are not guessed. PCE, GDP, retail sales, ISM are in the file only for late 2026 (n < 3):
reported as "too few", not traded. Tier-1 08:30 = CPI, NFP, PPI; FOMC = rate decision days.

(1) Measurement per type: range of the first hour after the release vs the same window on the prior 20 non-event days;
first 5m bar's direction and the % of events where price at +15 / +30 / +60 min is further in that direction (continuation)
vs back through the release-bar open (reversal); mean move in the first-bar direction in ATR5 units; % of events that break
the overnight (18:00-08:30) high or low / the prior RTH high-low in the first 30 min, and % of those breaks closing back
inside by +60. FOMC: the same around 14:00, with the pre-release range = the day's 09:30-14:00 range.

(2) Playbooks (8, counted). Defined risk, $250 a trade, one trade per event, entries >= 5 min after the release (MFFU Rapid
funded bans -2 / +2 min; Builder / evals allow news, docs/ACCOUNT_RULES.md), stop 1 tick beyond the named extreme:
- N1 08:30 first-5m-range break: a 5m close beyond the 08:30-08:35 bar's high / low (08:35-09:25) -> market next open; stop
  1 tick beyond the other side; target 2R; flat 10:30
- N2 08:30 first-15m-range break: range 08:30-08:45, closes 08:45-09:45, stop other side, 2R, flat 11:30
- N3 08:30 spike fade: the first 15 min takes the overnight high (low) and a 5m close 08:45-09:30 is back inside the overnight
  range -> short (long) at the next open; stop 1 tick beyond the spike extreme; target the overnight midpoint, capped 3R; flat 11:30
- N4 08:30 first-move hold: the 08:30-08:35 bar body >= 0.5 x ATR5 -> enter its direction at 08:35's open; stop 1 tick beyond
  that bar's other extreme; out at 09:30 (or the stop)
- N5 FOMC presser break: range 14:00-14:30, a 5m close beyond it 14:30-15:15 -> next open, stop other side, 2R, flat 15:55
- N6 FOMC spike fade: 14:00-14:30 takes the 09:30-14:00 high (low), a 5m close 14:30-15:15 back inside -> fade, stop 1 tick
  beyond the spike extreme, target the 09:30-14:00 midpoint capped 3R, flat 15:55
- N7 LIT news filter: today's live LIT, skipping Tier-1 08:30 / FOMC days (vs LIT as is)
- N8 ATLAS news filter: the 3 live ATLAS members, skipping the same days
Costs (news fills are worse; batch5 measured ATLAS entries 11.7 ticks off the 5m open on NORMAL days, uncalibrated, n = 3):
base = 6 ticks on every market entry + 2 ticks on stop / market exits (targets = limits, 0) + $1.90 a micro; stress = 12 + 4.
Placebo: N1-N6 run on the same clock times on NON-event days (is it the news or just the time?).
Judge (fixed now): a playbook card only if PF >= 1.2 at base costs in 2021-25 AND 2026 H1 AND 2026 Jul-Nov, PF > 1.0 at the stress,
beats its own non-event placebo in all three, walk-forward (6-month windows every 3 months) positive in >= 60% of windows
with trades, AND as an add-on to the LIT + ATLAS 50K path (one position) it does not lower 2026 pass / raise fail in either
half or 2021-25. N7 / N8 card only if skipping beats "as is" in all three spans on $ and on the 50K path.
