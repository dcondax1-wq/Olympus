# LIT deep skip map: pre-registered design (2026-11-23, written and committed before any result)

Question (owner): "LIT has MORE profitable setups the bot doesn't take." Map every LIT setup the bot skips today, then test each
skipped family as an ADD-ON to today's LIT (live_model.json "lit" exactly, run lit_live).

## Base
Today's LIT (rules 1-11, scale-in off), the live trades of run lit_live (tools/lit_edge.ctx()["T"]), on the cached CISD
candidate list (tools/lit_final.market("cisd")). Costs in ($1.40 a micro + 1 tick on market entries / stop / BE / EOD exits).

## Add-on mechanics (same for every family)
- The family's extra setups get their own daily slot: at most 1 live-rule trade + 1 family trade a day (engine `src_cap 1`,
  `max_per_day 2`), never two positions at once (first in time wins: an extra trade that is still open when a live setup
  enters blocks it, exactly as the live loop would; the live setup that follows is then free to trade).
- Extras of a gate family = setups that FAIL today's rule only because of that gate and occur on a no-trade day or before the
  day's live trade (setups after the day's live trade belong to the 2nd-trade families). The family's override applies to
  the extras only (engine `kz` override on an offset minute; the extras skip setup_ok because they were pre-screened).
- Weekly stop, Monday rule (except family monday_off), 15-minute check, BE + costs, VIX band target, stop 1 tick beyond the
  sweep extreme: unchanged for every trade.

## Families (ONE pre-set version each, no grid)
| id | family | definition of the extra setups |
|---|---|---|
| second_any | 2nd setup of the day | after the day's first trade exits (any exit), the next setup that passes every live gate, any side |
| opp_after_stop | opposite side after a stop-out | after a STOP or 15-minute cut, the next setup on the OTHER side that passes every live gate |
| continuation | continuation LIT | after a TARGET or BE exit, the next setup on the SAME side (a pullback sweep in the direction the first trade proved) |
| htf_liq | other liquidity: multi-day swing points | new setups that appear when the prior 5-day and 20-day highs / lows are added as liquidity (Market extra_levels d5, d20); every other gate live |
| idm_none | inducement variant | setups with NO qualifying inducement (today: >= 1 swing within 1 ATR above the level, <= 36 bars old); gate off |
| small_sweep | smaller sweep | sweep depth 0.25 to 0.5 ATR past the nearest level (today >= 0.5) |
| disp_low | weaker displacement | biggest body between extreme and trigger 0.5 to 0.8 ATR (today >= 0.8) |
| hours_out | outside the hours window | trigger on the all-hours detector, entry 18:30-02:00 ET or 15:30-15:45 ET (today 02:00-15:30) |
| cisd5_only | 5m CISD without the 1m confirmation | the 5m CISD limit is tapped but no 1m CISD prints in 22 min: take the limit fill (cisd1m off for the extras) |
| vix_near | setups the VIX band filters out | VIX band target 1.0 to 1.5R from the fill (today >= 1.5R) |
| stop_wide | planned stop outside 8-80 pts | planned stop 5-8 or 80-120 pts (size still follows the stop) |
| wait_long | late tap | limit valid 60 min instead of 30 |
| monday_off | Monday rule | setups the Monday rule blocked |

## Spans and pick rule
- Pick on 2026 Jan-Jun (H1). Then reported untouched: 2026 Jul-Oct (H2, to the last session of run baseline) and 2021-25
  (5m entries, no 1m bars). Numbers per span for the add-on total: trades / week, win %, PF, $ / month, max DD at the LIT size
  rule; eval path (live two_week sizing, room_f 0.4 to session 80): net, 2-week pass / fail, median sessions to pass.
- PASS (all must hold): (1) LIT-size net $ above today in H1, H2 AND 2021-25; (2) eval-path net $ above today in H1 and H2 and
  2-week fails not higher in either; (3) trades a week <= 4.0 in both 2026 halves; (4) multiple-testing: one-sided sign-flip
  test (10,000 draws) of the daily $ change vs today on the untouched spans pooled (H2 + 2021-25), Holm-corrected across the
  13 families, adjusted p <= 0.05.
