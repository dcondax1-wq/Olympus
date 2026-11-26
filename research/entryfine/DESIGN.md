# LIT entry refinement on 1m bars. Pre-registration (written 2026-11-26 ~11:20 ET, BEFORE any run)

PAPER RESEARCH ONLY, no live_model*.json change. Code `research/entryfine/entryfine.py` -> `results.json`; write-up
`research/writeups/entry-fine-2026-11-26.md`. Engine = engine/lit.run_x (the live loop's code) with live_model.json "lit";
the only change per variant is the price the 5m-CISD limit "taps" / fills at, done by wrapping engine.lit.simulate_x (the
engine file is not edited). Stop (1 tick beyond the sweep extreme), size-from-stop, VIX-band target / 8R bank, costs: unchanged.

Live today: limit at the 5m CISD level ("the edge" of the zone between that level and the sweep extreme); a touch = tapped;
then a 1m CISD within 22 bars -> market at the next 1m open + 1 tick.
Variants (5, counted; the 45 / 60-min expiries were run 2026-11-25 in research/moretrades, cited not re-run):
- E1 tap must trade 1 tick THROUGH the level (a bare touch does not count), then the live 1m CISD entry
- E2 tap at 50% of the zone (level <-> sweep extreme), then the live 1m CISD entry
- E3 limit expiry 20 min (wait 4) instead of 30, live entry
- E4 plain LIMIT entry at 50% of the zone, no 1m CISD (fills at min(limit, bar open), stop unchanged -> smaller stop, more micros)
- E5 plain LIMIT entry at the level, no 1m CISD, filled only when price trades 1 tick through (touch = no fill = the partial /
  queue-risk handling), filled at the level (the 1-tick price edge the wrapper gives is taken back: -0.25 pt a micro)
Judge (LIT rule): pick on 2026 Jan-Jun, check Jul-Oct 16 (both better on $ AND Builder 50K two_week 2-week pass), 2021-25
(5m, reference; the 1m steps fall back to 5m there) not worse; also fresh Oct 19 - Nov 20. Report trades/week, PF, net $,
$/month, max DD, 2-week pass / fail / median sessions, 40-session 50K / 25K / Rapid pass-fail. 5 tries: one half-win = noise.
