# Day hunt 2026-11-23: pre-registration (written before any result)

Goal: ONE addition that raises trades/week without cutting PF or raising max DD. Paper research only.

Coverage check (why the owner's three example ideas are not re-run as asked):
- LIT second session window (London close / NY lunch reclaim): already covered by lit-all-hours (1sess, 2day, rearm,
  _sal), lit-more-entries (498 variants incl. `lonny_c120` = 1 London + 1 NY trade 2 h after the first exit, after-win /
  after-BE / cool-down 2nd trades) and win-rate-and-sessions (lunch 11:30-13:30 alone / add / 1 AM + 1 PM). All rejected.
- ES-confirmed trades on days LIT skips: `es_filler` (ES LIT as MES on NQ-free days) and `smt_filter` / `smt_pick`
  rejected 2026-11-19.
- ATLAS member re-tune: atlas-members, atlas-more-money, atlas-health, walk-forward re-tunes rejected; no new hypothesis.

The one new idea (single fixed version, no grid):
**ESD = ES-confirmed displacement.** A LIT NQ setup that passes every live filter EXCEPT displacement, with its largest
displacement body in [0.6, 0.8) NQ-ATR, is kept only if ES (CME ES1! 5m) printed a body >= 0.8 ES-ATR(14, 5m) in the
setup direction on a 5m bar from NQ's sweep-extreme bar to NQ's trigger bar (inclusive, closed bars only). Everything
else = live LIT (1 trade a day, entries 02:00-15:30, 1m CISD entry, stop 1 tick past extreme, VIX band, BE+1.25,
15-min check, Monday rule, weekly stop). A day keeps at most 1 trade (an ESD setup can take the day's slot).

Gates (same as tools/lit_more_money.py G1-G6): LIT $ up in 2026 H1 AND H2; eval path $ up and 2-week fails not up in both
halves; 2021-25 LIT $ >= -600 vs base (NOTE: ES 5m exists only from 2025-04-14, so the "2021-25" check is effectively
Apr-Dec 2025; before that no ESD trades can exist, which is a data limit, not a pass); 2-4 trades/week; week-block
bootstrap P(change <= 0) <= 10%; funded $/month >= -10 both halves. Also required by the owner's bar: PF not lower and
max DD not worse in both 2026 halves.
