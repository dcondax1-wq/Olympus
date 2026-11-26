# Optimal eval sizing policy (big-evalsizer, 2026-11-26): pre-registered design, committed BEFORE any scored run

PAPER RESEARCH ONLY. Nothing live, no live_model*.json change, no orders. Question (lead): today's eval sizing is a fixed rule
(two_week "one winner passes", room_f 0.4, kept to session 80). Is there a state-dependent sizing POLICY that earns more $ per
eval bought (pass prob x payouts - fees) and/or passes faster, on Builder 50K, Builder 25K and Rapid EOD 25K, without blowing
up in bad markets?

## Engine (reused, not rebuilt)
research/plans/rank.py exactly as research/badcase used it: eval = RL.Ev (LIT via engine/sizing.lit_qty two_week on the plan's
numbers + ATLAS lane via rapid_levers.q_add, 30% best-day guard on the Rapid eval, soft day $1,000 / $500 / $500, stuck line,
min days), funded = rank.Funded (plan payout rules, buffer, caps, 5 payouts Builder, daily Rapid + $500 keep, news ban),
re-buy on fail / stuck / lost / graduated. ATLAS at real fills (atlas_risk.T_at(10)). Owner prices $91.80 / $63 / $97.20.
ONLY the LIT eval sizing call (SZ.lit_qty inside the eval) is replaced by the policy under test. ATLAS eval lane, funded
sizing, everything else unchanged. Paths: 1,000 x 60 sessions (seed 7) for the eval, 1,000 x 126 sessions (seed 23) for the
6-month slot, 5-session week blocks, as rank.py. Markets: H1 = 2026 Jan-Jun, H2 = 2026 Jul-Oct, REF = 2021-11..2025,
Y25 = 2025 (badcase's span).

## Policy interface (every family)
At each LIT eval entry the policy sees: balance b (profit), today's P&L cum, room = b + cum - floor, session s, the trade's stop
(risk pts) and target (tgt pts), the plan (tgt, mll, lock, dll, maxq). It returns a $ risk budget B. Micros
q = floor(B / loss1), loss1 = (stop + 1 tick) x $2 + $1.90 (engine/sizing's cap invariant). Then the SAME hard ceilings as
today for every family: q <= need-cap (ceil(need / (tgt x $2 - $1.90)): never size past what passes with one winner),
q x loss1 < room (strict), q x loss1 <= soft day + cum, q <= maxq, no trade once today reached the target, min-days
1-micro trade as today. q = 0 when 1 micro does not fit. After session two_week_until (80) every family keeps its own rule
(the 60-session eval window never reaches it; the 6-month slot rarely does).

## Variants (pre-registered, 18 per plan, 54 counted; count typo "19 / 57" fixed before the scored run, no variant changed)
| id | family | rule (B = $ risk budget) |
|---|---|---|
| T0 | today | engine/sizing two_week, room_f 0.4 (the real call, untouched) |
| R25 R30 R50 R60 | today's need rule, other room cap | room_f 0.25 / 0.30 / 0.50 / 0.60 |
| F10 F15 F20 F30 | fixed fraction of room | B = f x room, f = 0.10 / 0.15 / 0.20 / 0.30 (need-cap kept) |
| K25 K50 | Kelly fraction of edge | B = k x f* x room, f* = Kelly fraction of the LIT net-R pool of the pick split (H1 2026), k = 0.25 / 0.5, capped at room_f 0.6 |
| BP6 BP8 | bold play near the target | today, but room_f 0.6 / 0.8 once need <= 50% of the target |
| PR1 PR2 | protect near the floor | today, but room_f 0.25 / 0.15 once room < 50% of the max loss |
| BPR | bold + protect | room_f 0.6 when need <= 50% target, 0.25 when room < 50% mll, else 0.4 |
| D1 | DP policy, pick-split pool | value iteration below on the H1 2026 LIT net-R pool |
| D2 | DP policy, all-history pool | the same on the whole 2021-11..2026-10 LIT pool (robust to a bad market) |

## DP (D1 / D2), fixed now
State (b, floor) on a $25 grid (b from floor to target; floor from -mll to lock) + trades left n. Action = $ risk a on a
grid of 0..min(room, soft day) in $25 steps (0 = skip). Outcome: a x Rnet, Rnet = (pts x $2 - $1.90) / loss1 of a pool LIT
trade (empirical, equal weight). Fail if b + a x Rnet <= floor. Floor update after each trade: floor = min(max(floor,
b - mll), lock) (EOD trailing ~ one LIT trade a day). Pass if b >= target. Terminal value: 1 for a pass, 0 otherwise =
maximise P(pass within N) (with a constant funded value V per pass, max $ per eval = max P(pass)). N = LIT trades in 60
sessions at the pool's rate. Policy table = a*(b, floor, n) / room; the engine looks it up at the nearest grid point with
n = round((60 - s) x LIT trades per session), n >= 1. ATLAS is not in the DP (its lane stays as today).
Daily P&L (cum) enters only through the soft-day ceiling (same as today).

## Reported per plan x variant x market
eval: pass % / fail % in 60 sessions, median days to pass; 6-month slot: net $ (owner $ - fees), net $ per eval bought,
p10 net, payouts / month, evals bought. Also the DP policy table (fraction of room by need / room / trades left).

## Pick rule (fixed now)
1. Per plan, eligible = H1 eval fail % <= T0's H1 fail % + 2 points.
2. Pick = the highest H1 6-month slot net $ among eligible variants (pick on Jan-Jun 2026 only).
3. Card (needs-owner-yes) only if the pick beats T0 on 6-month slot net $ in ALL of H2, REF and Y25 AND its 60-session
   pass % is >= T0's - 2 points in every market (must not blow up in a bad market). Otherwise: today stays, REJECTED line.
4. Secondary (reported, not a pick): the "robust" variant = the max over variants of min over the 4 markets of
   (net $ - T0 net $), and the per-market best. 54 variants: a win in one market of one variant is noise.
