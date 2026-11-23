# Rapid EOD 50K: what the bot does on it the day you buy it, and the one change waiting for your yes

Card: **plan-rapid50k-max2-rebuys** (open). Buy it on MFFU with the CLUB code: **$165** ($275 list). At most 2 re-buys.

## The day you buy it (what is already built)
1. MFFU shows it in NinjaTrader as a new account (same name shape as your Rapid 25K, $50,000).
2. The PC's Start page says **"New Rapid EOD 50K eval ...: Zlarior + ATLAS?"**. Tap it once. That works because your Rapid 25K
   already taught the bot the name code. It goes into the 2nd Rapid slot, **NOT armed**.
3. **START BOT** -> you type the live phrase yourself -> it is armed. Nothing else arms it.
4. Keep-alive, readiness (NOT READY / not armed), the payout autopilot and the alerts list it as its own account.

## Sizing on it today (approved, unchanged)
| Lane | Today's setting |
|---|---|
| Zlarior (LIT) | eval: LIT's live two_week sizing (live_model.json lit_sizing, no override), max 30 micros, the bot's own $1,000 soft day, a winning day kept under 30% x $3,000 x 0.95 (MFFU's best-day rule); funded: 60% of the room, <= $1,500 a trade, a winner <= $2,000 (engine/multi_account PRESETS mffu_rapid_eod_50k) |
| ATLAS | $500 a trade, at most 30% of the room |
| Both on one account | never opposite positions; **LIT has priority** (an ATLAS position is closed at market first when LIT enters) |

## The proposed change (NOT applied: needs your yes)
From research/writeups/one-account-book-2026-11-22.md (the best one-account book):
- **LIT at half size (x0.5) while the Rapid 50K is an eval**, full size once it passes. It fails fewer evals (1.7% vs 2.5% Jan-Jun-like),
  and costs about $78 a month (Jul-Oct-like).
- **First in keeps the account** instead of "LIT has priority". The book was tested with first-come; today's code closes ATLAS when
  LIT enters.
- Why it is not a Decide card: the book is WORSE in a 2021-25-like market (-$529 vs -$374 over 6 months). The research's own rule
  says no card. So only say yes if you accept that.
- What Claude changes on a yes: a Rapid-eval-only LIT multiplier 0.5 in engine/rapid.lane_spec (eval stage only), and the
  first-come rule on the Rapid's shared account. Proof first per CLAUDE.md (both 2026 halves + 2021-25, trades/week, PF, net $, max DD).

Reply **"Rapid 50K: half-size LIT in the eval, yes"** or **"no"**. Until then the bot runs the table above.

## Other builders
- engine/go.py `role_of` for the Rapid slots is night-startfix's change; nothing here depends on it, and START's arm step already
  arms both Rapid slots (engine/account_cli.arm).
