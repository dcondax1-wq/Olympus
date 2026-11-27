---
tags:
  - zeus/strategy
  - lane/combo50k
  - market/nq
type: "strategy"
key: "combo"
---

# 50K combo

> [!abstract] ATLAS + Zlarior on ONE Builder 50K (engine/combo50k.py). Built, OFF by default.
> ATLAS + Zlarior on ONE account: the Builder 50K Zlarior (LIT) trades (owner 2026-11-19, Decide card zlarior-atlas-50k). BUILT, OFF BY DEFAULT. Study: research/writeups/one-account-combo-2026-11-19.md (tools/money/combo_account.py = the reference simulator); red team: research/writeups/one-account-combo-redteam-2026-11-19.md section 6 (what the live build must do).

## Performance by period

_No period table published for this one yet; see the write-ups._

## Tested and rejected

> [!failure]- BLITZ v2 rebuild
> 8 structural versions (noise-area band/VWAP exit, no time exit, cost gate stop >= 0.25% of price, opening-drive checks, limit at the band, first break only, 2 combos) vs today $912 / $688 / $89 a month (H1 / Jul-Nov / 2021-25). Best = V1 noise-area exit: 2021-25 PF 1.34, $352/mo, every year +, walk-forward 14/19, but 2026 $671 / $231 and on the shared 50K with LIT + ATLAS the 2026 pass falls 95 -> 87 / 88 -> 82. BLITZ today on the shared 50K: Jul-Nov pass 88.2 -> 82.5. Correlation ~0 does not help. 25K at $400: fail 43-76%; Rapid pass 0-28%. Verdict: retire BLITZ as a pillar; V1 is the only base worth reviving.
> Write-ups: [[blitz-v2-2026-11-26|BLITZ v2]]

> [!failure]- 2026-11-27 Builder 50K LIT room_f 0.5 / 0.6 / 0.7
> 2026-11-27 Builder 50K LIT room_f 0.5 / 0.6 / 0.7 (owner "upsize the 50Ks", day-50ksize, combo_account engine, 12 cells pre-registered): +$37..+$63/mo H1, +$41..+$99 Jul-Oct for fresh fails 3 -> 4-8% / 9 -> 15-22%; same answer as evalsizer. room_f stays 0.4. ATLAS eval share x1.0 (room 0.4) = +$183 / +$111 / +$44 a month (H1 / Jul-Oct / 2021-25) for fails 3 -> 9% / 9 -> 13%: owner 2026-11-27: "Wait until more room" = later, revisit when the 50K room > $2,000. research/lit/size50k-2026-11-27/RESULT.md


## Write-ups

| Date | Write-up | Verdict |
|---|---|---|
| 2026-11-19 | [[one-account-combo-redteam-2026-11-19\|Red team]] | research |
| 2026-11-19 | [[one-account-combo-final-2026-11-19\|One account, Zlarior + ATLAS on the Builder 50K]] | research |
| 2026-11-19 | [[one-account-combo-2026-11-19\|ONE account, several bots]] | research |
| 2026-11-17 | [[lit-smart-entries-2026-11-17\|LIT smart entries]] | rejected |
| 2026-10-20 | [[lit-gap-audit\|LIT gap audit]] | rejected |
| 2026-10-20 | [[lit-funded-combo\|LIT funded accounts on the new live LIT]] | adopt-candidate |
| 2026-10-20 | [[lit-batch3b\|LIT batch 3b]] | adopt-candidate |

## Links

- Combines [[Zlarior (LIT)]] and [[ATLAS]]
- [[ZEUS Lessons]] · [[ZEUS Decisions]] · [[ZEUS Home]]
