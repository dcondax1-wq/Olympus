# Human commission caller: ready to hire Monday (day-caller2, 2026-11-21)

The plan of record (research/writeups/cold-calling-plan-2026-11-20.md): a real person dials Maryland businesses by hand (legal), we pay
only on results ($300 per sale or $40 per booked call that shows), and Claude does everything else.

| File | What |
|---|---|
| `JOB_POSTS.md` | the ad + exact steps for the 3 free places (Indeed, Facebook groups, LinkedIn); Craigslist is paid in the US, college boards mostly refuse commission-only |
| `CALLER_PACK.md` | what the caller reads: the rules, the script + 10 objections, voicemail, follow-up email (CAN-SPAM), the portal, how commission is paid |
| `CONTRACTOR_TERMS.md` | one page the caller answers "I agree" to by email (1099 contractor, commission only, the rules, privacy) |
| `DNC.md` | the free registry (5 area codes: 301, 240, 227, 410, 443; 667 is the 6th at $85/yr), the sign-up, the scrub step, business vs personal lines |
| `TARGETS.md` | 2-week model with sources: middle case 340 dials -> ~1 sale = **$1,120 + $79/mo** to you after the commission; low 0, high 3 sales |
| `agency/dnc_scrub.py` + `tests/test_dnc_scrub.py` | the new scrub step (9/9) |

## Your time (honest count)

**Monday, about 15 minutes:**
1. (1 min) Tell Claude the agency name and the agency Gmail, if not chosen yet. Claude fills every `<Agency>` in the pack.
2. (12 min) Paste the ad on Indeed, 2-3 Facebook groups, and LinkedIn (JOB_POSTS.md, exact steps). Choose "free" on every pay screen.
3. (2 min) On the PC: `python -m agency.portal pass` (the callers' passphrase) and `python -m agency.portal setup` (agency name, Gmail, postal address).

**Before the first dial (Tue-Wed), about 10 minutes:** the Do-Not-Call sign-up and download (DNC.md steps 1-5).
**Then:** forward the replies to Claude, listen to the top 2 voice notes (2 min), pick one, send the pack + terms + passphrase.
Every 31 days: re-download the registry (2 min).
