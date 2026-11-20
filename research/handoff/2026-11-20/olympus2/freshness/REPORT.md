# Data freshness: report (day-archive, 2026-11-20, job from the lead 14:18 ET)

| What | Before | After |
|---|---|---|
| PC quiet over 70 min (today: silent since 9:30 ET) | every page using the PC feed fell back to its DEMO copy (Demeter: BLITZ, $1,420 sample) | pages show the PC's last real post with its age ("PC report 4 h 53 min ago"): `pc_feed.js` also asks ntfy's last 12 h. bots_back 71/71 |
| Payout plan (Hera / Demeter / Ledger) | Hera: only the Nov 4 study (BLITZ, ATLAS as an eval) | Hera "First payouts, now": ATLAS funded: GOAL $1,000 at $27,100 (you get $800), $1,699 to go; earliest $250 at $26,350 ($949 to go); 2 days, best day <= 50%; Zlarior 50K $3,807 to pass then $2,600; 25K #2 $1,500 then $1,350. Study labelled 16 days old. Ledger: "next payout needs $949, ask at $26,350". Demeter: real $1,025 room. hera 39/40 (= pc) |
| Fates (pass odds) | Nov 3 build on hard-coded fallback numbers (old-repo URL): Zlarior -$726, ATLAS an eval at -$254 | rebuilt from the PC's post: Zlarior 72% to pass from $3,807 to go; ATLAS funded = passed (100%). test_fates 77/79 (= pc) |
| Pantheon (Forum, Cities) | Nov 3 | rebuilt today (earlier commit); refreshed at every build once LEAD_WIRES 1 is in |
| Odeon trades (Kronos, Journal, Trading reels, NQ past days) | Oct 28, no date shown in Kronos / Journal | still Oct 28 (needs the PC's `data` branch: LEAD_WIRES 2); Kronos and Journal say "As of Oct 28 ... (N days ago)". kronos 54/54, journal 86/86 |
| LIT replays | Oct 25 build | rebuilt on NQ data to Nov 19 (no new LIT backtest trade after Oct 14) |
| Build wiring | CRONOS branch gone, nothing refreshed | `tools/site_refresh.py --site <out>` (Pantheon + Fates, never fatal, never writes the checkout), one block for build_web_dashboard (LEAD_WIRES 1); tests.test_site_refresh 5/5 |

Still older than 7 days (owned elsewhere or by design): datacity/city.json (Nov 10) and kalshicity/* (Nov 5): their Actions don't run
on this repo; pythia/events.json (Nov 10, correct, 5 suites pin it); pheme/stats.json (Nov 10, its test pins numbers); people / polis /
herald / ergasterion / pinakes repo copies are rebuilt by the site build already; hermes / arena use demo stories.
