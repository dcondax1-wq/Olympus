# day-arenas: the main apps revamp (2026-11-20)

Branch `day-arenas`. Nothing in the bot, the engine, the live files or the lead-only files was touched. Paper only, nothing armed.

## What changed, per app

| App | What you see now |
|---|---|
| **All 8 money/eval apps** | New shared cards ("pulse", `olympus/pulse.js` + `pulse.css`) with live numbers from the PC: today $ across all real accounts, drawdown left on the tightest account, $ to pass, every account in one list (room, to pass or what the payout still needs), what each bot is waiting for (window open / in a trade), streak and last trade, win rate by setup and by weekday, next payout and $ to you, fees paid vs payouts, net. Reserved height: the page never jumps while they fill (layout shift 0). Dark and light. |
| Aegis | Headline is now one big number: **drawdown left** on the tightest account, then Today / Drawdown / To pass. Bots card above the rules. "Zlarior 25K #2 25K" label fixed. |
| Demeter | Headline: **$ to pass** (nearest eval). Payouts + fees and bots cards at the end. Now works in light (the dial and tiles were dark-only). |
| Hera | Next payout headline card ($1,463 more for ATLAS's first payout) + payouts/fees. Light mode fixed (tiles, chart labels, payout calendar). Plutus and Argo linked as "folded in". |
| Ledger | Payouts/fees + today strip. **Fix:** Ledger now counts the Zlarior 25K #2 fee from the PC's account list, so net is **-$197.80** everywhere (it said -$134.80 while Hera said $198). |
| Business | Today strip + payouts/fees on top. **Fix:** the loading veil sat 12 s on every open (the page never told the kit it was ready); now it lifts at once. **Fix:** the public site no longer asks for the private `business.json` (the audit's 404). Harmonia, Mint linked as folded in. |
| Journal | Last trade headline + streak / setups / weekdays card. Light mode checked. Apollo, Epilogue, Kratos, Nemesis linked as folded in (Journal already had their week review and habit cost). |
| Helios | Today strip, the bots, the trades card, and **Pythia's market-risk calendar for the next 5 trading days** (red / amber / calm, the biggest release and its time). Pythia, Delphi, Forum linked as folded in. |
| Helios (lead's ask) | New card **NQ before the open**: reads `nq/brief.json` (day-brief, docs/BRIEF.md v1): headline, where price sits, the 4 nearest levels, today's news, next Tier-1 release, the day bias shown grey as context (no better than a coin), stale-data warning. Without the file: "the brief is on its way". |
| Hera (lead's ask) | New card **The fleet, month by month**: reads `business/fleet_plan.json` (day-fleet) loosely (months with median / bad case, next buy, top 3 Decide cards by $). The file is not on day-fleet yet, so today it shows "Plan coming"; checked with a sample file too. |
| Compass | **Fix:** it said "Bot not connected" while the PC was live (it read the old cloud copy); it now reads the PC's own status like Aegis and Helios. Today strip, bots and every account added. Light mode fixed. Stoa, Hestia, Inbox linked. |
| Fates | Stays a dark 3D stage by design (light theme keeps its dark stage). Moirai and Labyrinth linked inside its Lab sheet. |
| Zenith (Home) | **Fix:** Home jumped twice on open (the NQ strip grew to a 2-line "PC silent" banner from the old cloud copy, then shrank when the PC's live status arrived): layout shift 0.30 -> 0. The honest banner still shows if the PC really is silent after 4 s. |

Also: the shared design layer `olympus/shell.css` now loads last on all 9 apps (no live blur behind scrolling cards on a phone, reduced motion stops all animation). Subtle tap sounds on every button / tab of these apps through the existing Sound switch (Settings): silent before the first tap, in LITE, with reduced motion, and when the iPhone ringer switch is off.

## Not done / honest notes
- Ledger and Fates still have one long task (about 1.1 s and 1.7 s in the headless browser) when their 3D scene starts; headless software rendering inflates this a lot, a real iPhone GPU is much faster. I did not change the 3D scenes today (risk).
- Win rate by setup / weekday comes from the 2026 replay (295 trades) and says so on the card: there are only 4 real + paper trades so far. It switches to real trades by itself at 20.
- Ledger's `money/scoreboard.json` and `kalshi.json` 404 only on a local build (the publisher writes them on the real site). Clio's `writeups/index.json` exists in a real build: not a kit issue.
- I did not touch `business/taxes.html` or `business/keep.html` (day-taxes owns them).
- The merged apps are linked, not deleted: every old URL still works.

## Tests
- `python tests/smoke.py`: 8/8 green.
- New `tests.test_pulse` (in `run_area.py olympus`): 80/80 (kit logic in node, every mounted app in Chromium dark + Ivory: cards fill, layout shift < 0.01, no page error, links >= 44 px, dark ink on light pages).
- App suites: aegis 53/53, demeter 41/41, hera 40/40, ledger 88/88, business 85/85, compass 57/57, helios 55/55, journal 86/86, journal_edge 42/42, fates 79/79, zenith_nq 20/20, zenith_mode 70/70 (smoke).
- Test pins updated for the new `<html>` attributes: `tests/agora_kit.py` (accepts `data-oly-shell="app"`), `tests/test_journal_page.py`.

## Screenshots
`shots/before-<app>-dark|light.jpg` and `shots/after-<app>-dark|light.jpg`, 390x844 at 2x, for zenith, business, ledger, aegis, demeter, fates, hera, journal, helios, compass. Numbers (layout shift, long tasks, 404s): `shots/before-numbers.json`, `shots/after-numbers.json`.

## Round 2 (lead's ask, after merging pc): the rest of the KEEP apps

| App | What changed |
|---|---|
| Kronos (P&L calendar) | Today / drawdown left / to pass strip at the top; the streak, setups and weekdays card above "Which weekday pays". Light mode (the calendar's green / red days, bars and band follow the look). |
| Pnyx (rules + size calculator) | Today / drawdown / to pass strip at the top, every account at the end, light mode. Labyrinth (eval sizing) linked as folded in. The 0.15 layout shift seen once in the before run did not come back in 6 runs after (0 every time). |
| Chrysos (fees vs payouts) | The REAL payouts and fees card (next payout, fees paid, net so far) right under its 12-month estimate, so the estimate sits next to what really happened. Light mode (the warning box was dark-only). |
| Mercury (prop sales) | Real payouts / fees card at the end (is a deal worth it: what you already paid). Light mode. |
| Oikos (household) | New **Tax pot 30%** card (Maryland: 30% for the expected year, 40% with a day job, next due Jan 15, 2027) that opens Business > Taxes; prop payouts / fees card. The public site no longer asks for the private `money/household.json` (it was a 404 on every open; the PC's private link still reads it). |
| Planner | Today strip + what each bot is waiting for, above the day. |
| Clio (research library) | It downloaded the 8 MB `data.json` on every open next to the small `writeups/index.json`; now `data.json` is only the fallback (long task 84 ms -> 0). The audit's `writeups/index.json` 404 only happens on the raw folder: a real build writes it (checked). Archive and Pinakes linked as folded in. Light mode. |
| Settings | No change needed: the Sound switch (Auto / On / Off, volume, haptics) is already there and drives the new tap cues. Shots use `?tour=0` (the first-visit tour hid the page). |
| Atlas | "What needs me now" listed 6 archived research rooms (Odeon, Data City, Daphne, Pantheon...): it now skips the rooms folded under Archive (2 real ones left: Fates' and Kalshi City's feeds are old). Atlas keeps its own dark look (it does not load the AGORA kit). |

The shared design layer `olympus/shell.css` is now on these apps too, and the tap sounds work on every one with pulse cards.
Merges still open, all in folders other helpers own: Odeon / Why -> trading, Ares / Chronos / Kairos -> nq, Sibyl / Kalshi City -> dionysus.

Round 2 numbers (before -> after, 390x844): layout shift 0 on all 9 after (Pnyx 0.15 once before); Clio's longest task 84 ms -> 0; Kronos keeps
a ~1.5 s long task when its 3D sundial starts in the headless browser (software WebGL; not changed today).
Tests: pulse 128/128 (14 apps, dark + Ivory), kronos 54/54, pnyx 51/51, chrysos 61/61, mercury 40/40, oikos 65/65 + household 11/11,
planner 170/170, clio 47/47, atlas_ui 36/36 + node atlas hub 4/4.
Shots: `shots/before-<app>-*.jpg` and `shots/after-<app>-*.jpg` for kronos, pnyx, chrysos, mercury, oikos, planner, clio, settings, atlas.
LEAD_WIRES: nothing new for round 2 (every folder is in the root worker's OTHER_APPS; `?v=` tags bumped; `pulse.css` / `pulse.js` are now `?v=p2` everywhere).
