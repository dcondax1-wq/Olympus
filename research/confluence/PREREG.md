# Confluence tags - pre-registration (written 2026-11-23 BEFORE any outcome was looked at)

Research only. Paper. No live file, no engine/ change. Each tag is ONE yes/no definition, never tuned after this file.
Read at the signal from closed bars only (LIT: the 5m CISD trigger bar i, the sweep bar ext_i; ATLAS: the 5m signal bar j
before the entry open). "d" = +1 long / -1 short. Extreme = LIT's sweep extreme (ext_d); ATLAS: the lowest low (long) /
highest high (short) of the last 6 closed 5m bars up to j.

| id | tag fires (= confluence present) when |
|---|---|
| smt | ES/NQ SMT at the sweep: NQ's extreme over [extreme bar-5 .. extreme bar] took the low (long) / high (short) of the 12 5m bars before that window, and ES did NOT (ES low over the same window > ES low of the same 12 prior bars, long; mirror short). ES 5m exists from 2025-04-14; before that the tag is "unknown" and counts as not present. |
| htf_pda | a 1h or 4h FVG or order block at the entry: an unfilled bullish (long) / bearish (short) 1h or 4h FVG (3-candle gap, formed in the prior 3 sessions, from closed HTF bars) or 1h order block (last opposite-close 1h candle whose high (long) / low (short) the next 1h candle closes beyond, not closed through since) whose zone overlaps the span between the extreme and the entry. 1h bars on the clock hour, 4h bars anchored 18:00 ET (18, 22, 02, 06, 10, 14), built from data/NQ_5m.csv. |
| key_sweep | the sweep took a previous-day or previous-week high/low or the Asia (18:00-00:00) / London (02:00-05:00) high/low. LIT: the engine's swept list contains pdh/pdl/pwh/pwl/asia18/lon25 on the trade's side. ATLAS: the extreme went beyond one of those levels (formed before the window) and the entry is back on the other side of it. |
| killzone | entry time (ET) in 02:00-05:00 or 08:30-11:00. |
| bias | daily bias agrees: the prior session (18:00-17:00) closed beyond its open in the trade's direction AND the 4h trend agrees (last closed 4h close beyond the close 6 4h bars earlier, in the trade's direction). |
| vol_spike | volume spike on the CISD bar (ATLAS: the signal bar): its 5m volume >= 1.5x the mean of the 20 bars before. (No tick data: delta is not available, volume only.) |
| vix_hi | VIX regime: the prior VIX close >= 20. |
| on_tight | overnight range size: the 18:00-02:00 range is below the median of the same range over the prior 20 sessions (a tight overnight). |
| round | round / quarter number: the extreme is within 5 points of a multiple of 50 (the 00 and 50 levels). |
| pd_side | premium / discount of the prior day: long with the entry below the prior day's 50% (midpoint of pdh/pdl), short above it. |

Comparisons (each tag, each bot): tagged vs untagged executed trades: count, win %, avg R (costs in), PF ($ at the bot's
research size) on 2026 Jan-Jun, 2026 Jul-Oct, 2021-25. Test: Welch t on R, pooled 2026 and 2021-25 separately; Holm
(family-wise) and Benjamini-Hochberg across all 20 tag x bot tests (2026 pooled), plus a sign-consistency requirement
(tagged better in all three spans).

Uses, fixed here:
 (a) skip every setup WITHOUT the tag (LIT: engine skip_keys, the day stays free for a later setup; ATLAS: weight 0, the slot
     stays free).
 (b) count the 10 tags; 2+ present = x1.5 size, else x1 (LIT: through tools/lit_edge.evaluate mfn, inside the size-follows-stop
     rule, the MFFU caps and the eval drawdown rule; ATLAS: through the account-B need size and the funded 25K Monte Carlo).
     Plus a leverage control: x1.5 on the same number of randomly chosen trades (luck test, 100 draws LIT / 30 ATLAS).
Money: $/month, max DD, trades/week, eval 2-week pass / fail and median pass session (LIT: live two_week room 0.4 to session
80; ATLAS: 25K eval path), the gate of tools/setup_grade (lit_gate / atlas_gate). A use passes only if it clears the gate AND
the luck test p <= 0.05 after Holm across the uses tried.
