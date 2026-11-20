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
| Compass | **Fix:** it said "Bot not connected" while the PC was live (it read the old cloud copy); it now reads the PC's own status like Aegis and Helios. Today strip, bots and every account added. Light mode fixed. Stoa, Hestia, Inbox linked. |
| Fates | Stays a dark 3D stage by design (light theme keeps its dark stage). Moirai and Labyrinth linked inside its Lab sheet. |
| Zenith (Home) | **Fix:** Home jumped twice on open (the NQ strip grew to a 2-line "PC silent" banner from the old cloud copy, then shrank when the PC's live status arrived): layout shift 0.30 -> 0. The honest banner still shows if the PC really is silent after 4 s. |

Also: the shared design layer `olympus/shell.css` now loads last on all 9 apps (no live blur behind scrolling cards on a phone, reduced motion stops all animation). Subtle tap sounds on every button / tab of these apps through the existing Sound switch (Settings): silent before the first tap, in LITE, with reduced motion, and when the iPhone ringer switch is off.

## Not done / honest notes
- Ledger and Fates still have one long task (about 1.1 s and 1.7 s in the headless browser) when their 3D scene starts; headless software rendering inflates this a lot, a real iPhone GPU is much faster. I did not change the 3D scenes today (risk).
- Win rate by setup / weekday comes from the 2026 replay (295 trades) and says so on the card: there are only 4 real + paper trades so far. It switches to real trades by itself at 20.
- Ledger's `money/scoreboard.json` and `kalshi.json` 404 only on a local build (the publisher writes them on the real site). Clio's `writeups/index.json` exists in a real build: not a kit issue.
- The merged apps are linked, not deleted: every old URL still works.

## Tests
- `python tests/smoke.py`: 8/8 green.
- New `tests.test_pulse` (in `run_area.py olympus`): 80/80 (kit logic in node, every mounted app in Chromium dark + Ivory: cards fill, layout shift < 0.01, no page error, links >= 44 px, dark ink on light pages).
- App suites: aegis 53/53, demeter 41/41, hera 40/40, ledger 88/88, business 85/85, compass 57/57, helios 55/55, journal 86/86, journal_edge 42/42, fates 79/79, zenith_nq 20/20, zenith_mode 70/70 (smoke).
- Test pins updated for the new `<html>` attributes: `tests/agora_kit.py` (accepts `data-oly-shell="app"`), `tests/test_journal_page.py`.

## Screenshots
`shots/before-<app>-dark|light.jpg` and `shots/after-<app>-dark|light.jpg`, 390x844 at 2x, for zenith, business, ledger, aegis, demeter, fates, hera, journal, helios, compass. Numbers (layout shift, long tasks, 404s): `shots/before-numbers.json`, `shots/after-numbers.json`.
