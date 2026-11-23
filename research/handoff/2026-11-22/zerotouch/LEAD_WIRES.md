# night-zerotouch: lead wires + notes (2026-11-22)

Branch `night-zerotouch` (from origin/land-fixes). No lead-only file was touched (sw.js, build_web_dashboard.py,
jarvis/apps.js, the APPS table): nothing to wire there.

## What changed
- engine/keepalive.py: `start_consent(phrase, armed)` - the exact live phrase at a START turns the keep-alive ON for exactly
  the armed real accounts; writes only `{"consent": {t, day, accounts, via: "start_phrase"}}` (never the phrase). Sim / not
  armed / owner-OFF accounts untouched. `--off` / `--off all` record `owner_off` (sticks against later STARTs); `--on` clears it.
- engine/go.py: `armed_accounts()`, `keepalive_consent()` (end of `_step_arm`, success path only), `keepalive_missing()`
  (a running bot: START offers the phrase once for an account still off; Enter = nothing), `keepalive_view()` in `status()`
  (`"keepalive": {"on", "off", "consent_day"}`; the Start page can show it - optional JS later). The keep-alive file follows
  `CFG`'s folder (`_ka_path`), so test harnesses never write the real data/keepalive.json. `resume_now` (no phrase) never
  touches it. START window + Start page text say the phrase also turns the keep-alive on.
- MONDAY_SETUP.bat + engine/monday.py: update -> clock (UAC for the clock only; skipped when OlympusClock exists) -> START ->
  alert test -> engine/recovery lines. Deliberately a NORMAL double-click, not "Run as administrator": an elevated window
  would start the bot server / NinjaTrader elevated (files written as admin lock the normal account out). Run as admin
  anyway = clock + alert test only, with one line to double-click again.
- engine/recovery.py: the recovery matrix (read-only), `python -X utf8 -m engine.recovery`.
- engine/self_heal.py: new remedy `nt` - NinjaTrader.exe not running while data/autostart.json says run -> opened (never logs
  in / arms). Hourly cadence.
- engine/trade_home.py: keep-alive line names the accounts; the off fix points at START (menu 2); new menu `k` = KEEPALIVE_OFF.bat.
- engine/readiness.py: the 7-day card's fix says MONDAY_SETUP / START with the phrase.
- tests/test_zerotouch.py (50 checks, area pc); tests/test_trading_home a3 updated (menu 2 now); tests/test_arm_rt run_path now
  fakes rapid.arm / account_cli.arm / resume_optin (PRE-EXISTING HAZARD: its happy-path START armed the owner's REAL
  data/rapid.json and data/accounts.json when run on the PC).

## Audit findings (honest)
- Auto-resume has NO 7-day validity window (the brief assumed one): it lasts until the kill switch / HOLD TO KILL /
  --disable-auto-resume / STOP BOT. Limits kept as they are and written in plain words in the manual.
- Already automatic before tonight: supervisor restart + back-off, update/rollback restart (exit 75), keep-awake, reboot via
  logon task + Startup shortcuts + auto-resume (opens NinjaTrader, waits), self-heal stale pid / git lock / clock.
- Gap fixed: NinjaTrader closed mid-week while the bot runs stayed closed (only alerted) -> self-heal `nt`.
- Gap left for the owner's hands (cannot be automated safely): auto-login after a power cut (netplwiz, docs/PC_ALWAYS_ON.md),
  NinjaTrader's saved log-in.

## Optional lead follow-ups
- Start page JS: show `status().keepalive.on` under the Armed step.
- Owner's step count: weekly = 1 double-click + 1 Windows "Yes" (first time only) + type the phrase once. Was: START_BOT,
  phrase, KEEPALIVE_ON, KEEP ALIVE ON, FIX_CLOCK (admin), TEST_ALERT, UPDATE = 7 actions / 2 phrases.
