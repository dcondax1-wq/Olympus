# ChatGPT research dossier 2026-10-24: testable ideas (verbatim specs, condensed)

Source: owner's ChatGPT dossier pasted 2026-10-24. All thresholds are ChatGPT's hypotheses (no evidence). P = primary, A1/A2 = alternatives. Long rules; shorts mirrored.
Shared: s = first completed 1m bar breaching the selected outer level L; I = the selected inducement; b = LIT's own displacement bar (5m); A = feature-only Wilder ATR(14) on completed 5m, frozen before s; q = 0.25 pt. Missing/zero denominators = UNKNOWN (no trade change). Every rule is a skip/cancel filter on LIT's existing setups (stop/target unchanged).

## 20 LIT filters (ChatGPT's rank in brackets)
- L01 [8] displacement body efficiency |C-O|/(H-L) of b >= k. k 0.7 / 0.6 / 0.8
- L02 [9] displacement close location (C-L)/(H-L) >= k (short mirrored). k 0.85 / 0.75 / 0.95
- L03 [4] prompt reclaim: first favorable 1m close back through L within k 1m bars of s (same bar = 0). k 2 / 1 / 3
- L04 [5] prompt displacement: qualifying displacement closes within k 1m bars of s. k 3 / 1 / 5
- L05 [7] prompt 5m CISD: CISD known_at - breach known_at <= k min. k 10 / 5 / 15
- L06 [2] inducement prominence: min(max highs left window, max highs right window) - pivot low, / A >= k. k 0.25 / 0.125 / 0.5
- L07 [1] inner/outer separation (I - L)/A >= k. k 0.25 / 0.125 / 0.5
- L08 [12] inducement recency: breach time - I known time <= k min. k 30 / 15 / 60
- L09 [13] prior touches of L since active <= k (episodes reset after N non-contact bars). (1,1) / (0,2) / (2,3)
- L10 [16] isolated raid: extra distinct known levels crossed by the sweep bar <= k. k 1 / 0 / 2
- L11 [14] approach efficiency over N 1m closes before s: |C_last-C_first| / sum|dC| >= k. (5,0.65) / (3,0.5) / (8,0.8)
- L12 [15] approach overlap: mean overlap of consecutive 1m ranges over N bars <= k. (5,0.5) / (3,0.35) / (8,0.65)
- L13 [3] displacement closes beyond the opposite extreme of the last N 1m bars before s by >= k ticks. (3,1) / (2,0) / (5,2)
- L14 [6] 5m CISD close clears the latest opposite 5m pivot known before s by >= k ticks. k 1 / 0 / 2
- L15 [10] CISD run age: 5m bars from run start to the CISD close <= k. k 6 / 3 / 12
- L16 [17] after the 5m CISD wait N consecutive 1m closes on the favorable side before arming (deadline unchanged). N 2 / 1 / 3
- L17 [18] cancel pending entry if a 1m adverse body / A > k while unfilled. k 0.6 / 0.4 / 0.8
- L18 [19] cancel the waiting entry k min after the 5m CISD. k 15 / 10 / 20
- L19 [11] (entry - stop) / (sweep penetration beyond L) <= k. k 3 / 2 / 4
- L20 [20] cancel pending entry after N consecutive 1m closes beyond an opposite 1m CISD level. N 2 / 1 / 3
Rank order: L07,L06,L13,L03,L04,L14,L05,L01,L02,L15,L19,L08,L09,L11,L12,L10,L16,L17,L18,L20. Correlated groups: L01/L02; L03/L04/L05; L11/L12; L16-L20.
Required report: net $ change, fills/week, and TAIL RETENTION = kept baseline trades with MFE >= 4R / all baseline trades with MFE >= 4R (also 3R, 5R).

## 10 ATLAS templates (25K, breakouts; stop 1 tick beyond the structural level; target 3R (alt 2R/4R); one attempt/day each, max 2/day combined; flat 15:55; entries until 15:30; never opposite LIT)
Sizing: q = floor(min(500, day budget, floor room) / (stop_pts x 2 + $1.90 + 1-tick reserve)); q < 1 -> skip.
- A01 1-min opening range (09:30-09:31) breakout: first later 1m close beyond by buffer; next bar. (1m,1t,3R)/(2m,2t,2R)/(3m,4t,4R). Stop = opposite range extreme.
- A02 5-min OR (09:30-09:35) breakout. (5,1,3R)/(10,2,2R)/(20,4,4R). Stop opposite extreme.
- A03 overnight box (18:00-02:00) breakout, freeze 02:00 (alt 03:00/04:00), buffer 1/2/4. Stop latest opposite 5m pivot.
- A04 previous RTH (09:30-16:00) range breakout on a 5m close, buffer 1/2/4. Stop opposite 5m pivot.
- A05 previous week high/low breakout on a 1m close. Stop opposite 5m pivot. (low frequency)
- A06 inside prior session (inside the one before) -> breakout of the prior session range. (low frequency)
- A07 1m narrowest of last N bars -> breakout of its range within M bars. (7,5,1t)/(4,3,2t)/(10,8,4t). Stop opposite narrow-bar extreme.
- A08 5m inside bar -> 1m close beyond the mother bar within M min. M 15/10/20. Stop opposite mother extreme.
- A09 5m close beyond the prior N 5m bars' range. N 12/6/24. Stop opposite 5m pivot.
- A10 symmetrical compression (K falling pivot highs + rising lows, width <= k x oldest) -> breakout within M min. (3,0.5,30)/(2,0.65,20)/(4,0.35,40).
Published reference: Tsai et al. IEEE Access 2019 (TORB, 1-min opening range on E-mini NASDAQ 2001-2013, full-sample pick).
Pivot: strict 2-left/2-right (alt 1/3), most recent opposite pivot within 12 5m bars (alt 6/24); none -> skip.

## Volatility-target research (V1-V4, target-only clones)
- V3 VXN instead of VIX for the target band (multipliers 1.0/0.9/1.1). V4 VIX9D instead of VIX. V1/V2 strata only (VIX9D/VIX >= 1.05; VIX/VIX3M >= 1.0). CBOE files: VXN_History.csv, VIX9D_History.csv, VIX3M_History.csv at cdn.cboe.com/api/global/us_indices/daily_prices/.
