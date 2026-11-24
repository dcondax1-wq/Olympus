# day-zerotouch2 (2026-11-24): lead wires

Helper did NOT touch sw.js, build_web_dashboard.py, jarvis/apps.js or the olympus.js APPS table. To wire:

1. Link the new page **`pc/control.html`** ("PC Control": live checklist + 5 safe buttons) from the Olympus switcher / Jarvis
   apps and the NQ page (suggested title "PC Control", icon radar, one line "Run the PC from the phone"). `pc/` is already copied
   by the build (the STATUS / FRESH_START downloads live there), so the page publishes without a build change; add its files
   (control.html, pc.css, pc.js, pccore.js, control.webmanifest, the 4 icons) to the root sw precache if that list is explicit.
2. docs/OLYMPUS_MAP.md row: PC Control (`pc/control.html`) | trading | the PC checklist + phone buttons | `../status_feed.json`
   (the PC post's `ck` block) | `tests.test_zerotouch2`.
3. The control branch needs nothing new: the inbox folder `control/inbox/` is created by the first one-tap commit.

What changed (engine side, ships with the branch):
- engine/self_heal.park_local + autoupdate.fast_forward(park=) + run_update(park=None -> daily/hourly) + remote update park=True.
- engine/pc_checklist.py (new) -> tools/pc_report.py: ext block `ck`, core `p4` (4 pillar states), and `tr` is now actually posted
  (it was gathered since day-pillars but never put in the post).
- engine/remote_ctl.read_inbox (control/inbox/<id>.json).
- engine/go.autoresume_line (START prints it after the opt-in); engine/monday.boot_lines (NinjaTrader start/connect, auto-sign-in).
- tests: test_zerotouch2 (new, 50/50); test_self_heal_pc b3 now expects "would park"; test_autorun's 3 checks fixed (they failed on
  pc already since day-updfix: their hand edit was in a file the update did not touch).
